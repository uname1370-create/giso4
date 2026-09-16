# -*- coding: utf-8 -*-
"""واریز روزانه‌ی اعتبار خرید بر اساس رتبه‌ی کاربر (مرحله ۵، نسخه‌ی مقاوم در بار بالا).

سیاست:
- هر شب به‌ازای هر کاربر، «اعتبار خرید (Spend)» برابر ``daily_credit`` رتبه‌ی او واریز
  می‌شود. ساعت مرجع ۲۳:۵۹ است؛ اگر در آن بازه تریگی نبود (ترافیک شب پایین)، اجرا تا
  بامداد روز بعد عقب نمی‌افتد بلکه به‌محض اولین تریگرِ بعد از ۲۳:۵۹ یا صبح روز بعد
  (تا ساعت ۰۸:۰۰، به‌عنوان جبران) انجام می‌شود. در هر صورت برای هر «تاریخ» فقط یک‌بار.
- واریز فقط وقتی انجام می‌شود که سوپرادمین در تب رتبه‌ها آن را فعال کرده باشد
  (کلید ``rank_daily_credit_enabled`` در giso_config؛ پیش‌فرض فعال).
- idempotency با ``wallet_transactions.idempotency_key = rank_daily:<user_id>:<YYYY-MM-DD>``
  تضمین می‌کند برای هر کاربر در هر روز حداکثر یک واریز ثبت شود (حتی با اجرای چندباره/همزمان).
- به کاربرانِ دارای حساب بله، اعلان کوتاه بله می‌رود (best-effort).

بار و همزمانی:
- تریگرهای lazy (``maybe_deposit_rank_credits``) هرگز درخواست/به‌روزرسانی کاربر را بلاک
  نمی‌کنند؛ کار سنگین داخل یک thread پس‌زمینه (daemon) اجرا می‌شود. یک قفل غیرمسدودکننده
  تضمین می‌کند در هر فرایند فقط یک کارگر اجرا شود؛ تاریخِ اجراشده در giso_config بین
  فرایندها هم یکتایی می‌دهد و تکرارِ کاملِ واریز را منتفی می‌کند.
"""
import logging
import threading
from datetime import datetime

from giso.base import get_giso_db_conn, normalize_phone
from giso.wallet import _rank_levels_config, rank_daily_credit_enabled

logger = logging.getLogger("giso_rank_daily")

# کلیدهای فلگِ تاریخِ آخرین واریز در giso_config (per-date تا جبران صبحگاهی ممکن باشد).
def _ran_key(date_str: str) -> str:
    return f"rank_daily_last_run:{date_str}"


# قفل درون‌فرایندی: فقط یک کارگر هم‌زمان در هر فرایند (non-blocking).
_WORKER_LOCK = threading.Lock()


def _today_str() -> str:
    return datetime.now().strftime("%Y-%m-%d")


def _yesterday_str() -> str:
    from datetime import timedelta
    return (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")


def _due_dates() -> list:
    """تاریخ‌هایی که اکنون باید واریز شوند: امروز (اگر ≥۲۳:۵۹) و/یا دیروز (جبران صبحگاهی <۰۸:۰۰)."""
    now = datetime.now()
    due = []
    if (now.hour, now.minute) >= (23, 59):
        due.append(now.strftime("%Y-%m-%d"))
    elif now.hour < 8:
        # پنجره‌ی جبران: اگر دیروز واریز نشده، همین صبح انجام شود.
        due.append(_yesterday_str())
    return due


def deposit_rank_credits_for_date(date_str: str | None = None, push: bool = True) -> dict:
    """واریز اعتبار روزانه‌ی رتبه برای همه‌ی کاربران برای یک تاریخ مشخص.

    «اجراکننده‌ی خالص»: مستقل از ساعت/روزِ جاری (مناسب تست و اجرای دستی جبرانی).
    idempotency کامل دارد؛ اجرای دوباره در همان روز هیچ واریز تکراری نمی‌سازد.
    """
    date_str = (date_str or _today_str()).strip()[:10]
    result = {"ok": True, "date": date_str, "deposited": 0, "skipped": 0, "pushed": 0}
    # تنظیمات bot.db پیش از باز کردن تراکنشِ giso.db خوانده می‌شوند (جلوگیری از قفل متقابل).
    try:
        enabled = rank_daily_credit_enabled()
        levels = _rank_levels_config()
    except Exception as exc:
        logger.warning("rank daily config read failed: %s", exc)
        enabled = True
        levels = []
    if not levels:
        from giso.wallet import _RANK_LEVELS_DEFAULT
        levels = [{"level": l, "name": n, "emoji": e, "threshold": t, "daily_credit": c}
                  for l, n, e, _, _, t, c in
                  sorted(_RANK_LEVELS_DEFAULT, key=lambda x: x[5], reverse=True)]
    if not enabled:
        result["ok"] = False
        result["reason"] = "disabled"
        return result
    conn = get_giso_db_conn()
    try:
        conn.execute("BEGIN IMMEDIATE")
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        # اگر همین تاریخ قبلاً پردازش شده، با یک کوئریِ سبک فهرست واریزشدگان را بگیر تا
        # مجدداً پیمایشِ امتیازِ هر کاربر تکرار نشود (اجرای هم‌زمان/جبرانی ارزان می‌ماند).
        done_rows = conn.execute(
            "SELECT user_id FROM wallet_transactions "
            "WHERE kind='rank_daily' AND idempotency_key LIKE ?",
            (f"rank_daily:%:{date_str}",),
        ).fetchall()
        done_users = {int(r["user_id"]) for r in done_rows}
        users = conn.execute(
            "SELECT id, name, phone FROM giso_web_auth WHERE COALESCE(phone,'')<>''"
        ).fetchall()
        push_targets = []
        for u in users:
            try:
                uid = int(u["id"])
                if uid in done_users:
                    result["skipped"] += 1
                    continue
                prow = conn.execute(
                    "SELECT COALESCE(SUM(COALESCE(m.reward_points,0)),0) "
                    "FROM wallet_mission_completions c "
                    "JOIN wallet_missions m ON m.id=c.mission_id "
                    "WHERE c.user_id=? AND COALESCE(m.is_deleted,0)=0",
                    (uid,),
                ).fetchone()
                score = int(prow[0] or 0) if prow else 0
                current = levels[-1]
                for lv in levels:  # مرتب از بیشترین به کمترین آستانه
                    if score >= lv["threshold"]:
                        current = lv
                        break
                credit = max(0, int(current.get("daily_credit") or 0))
                if credit <= 0:
                    result["skipped"] += 1
                    continue
                idem = f"rank_daily:{uid}:{date_str}"
                conn.execute(
                    "INSERT INTO wallet_transactions "
                    "(user_id,kind,amount,status,source_type,source_id,balance_scope,idempotency_key,description,created_at) "
                    "VALUES (?, 'rank_daily', ?, 'available', 'rank_daily', 0, 'spend', ?, ?, ?)",
                    (uid, credit, idem,
                     f"اعتبار روزانه‌ی رتبه {current['emoji']} {current['name']} — {date_str}", now),
                )
                result["deposited"] += 1
                np = normalize_phone(u["phone"] or "")
                bale_id = None
                if np:
                    brow = conn.execute(
                        "SELECT bale_id FROM giso_users WHERE phone=? ORDER BY rowid DESC LIMIT 1",
                        (np,),
                    ).fetchone()
                    if brow and brow["bale_id"] and str(brow["bale_id"]).strip().isdigit():
                        bale_id = str(brow["bale_id"]).strip()
                if bale_id:
                    push_targets.append((bale_id, current, credit))
            except Exception as exc:
                logger.warning("rank daily deposit failed for user %s: %s", u["id"], exc)
                result["skipped"] += 1
        conn.commit()
        if push:
            try:
                from giso.base import send_bot_push
                for bale_id, current, credit in push_targets:
                    try:
                        text = (f"🎁 {current['emoji']} اعتبار روزانه‌ی رتبه‌ی {current['name']} "
                                f"به کیف پول شما واریز شد.\n"
                                f"💰 مبلغ: {credit:,} تومان اعتبار خرید")
                        if send_bot_push(bale_id, text):
                            result["pushed"] += 1
                    except Exception as exc:
                        logger.debug("rank daily push failed: %s", exc)
            except Exception:
                pass
        return result
    except Exception as exc:
        try:
            conn.rollback()
        except Exception:
            pass
        logger.exception("rank daily deposit failed: %s", exc)
        return {"ok": False, "date": date_str, "deposited": 0, "skipped": 0,
                "pushed": 0, "reason": str(exc)}
    finally:
        conn.close()


def _run_background(force: bool = False):
    """کارگرِ پس‌زمینه: برای هر تاریخِ سررسیده واریز را اجرا و فلگ تاریخ را ثبت می‌کند."""
    dates = [_today_str()] if force else _due_dates()
    for date_str in dates:
        try:
            from giso_admin import get_giso_config
            if not force and str(get_giso_config(_ran_key(date_str), "") or "") == date_str:
                continue
        except Exception:
            pass
        try:
            res = deposit_rank_credits_for_date(date_str)
        except Exception as exc:
            logger.warning("rank daily worker error %s: %s", date_str, exc)
            continue
        if res.get("ok"):
            try:
                from giso_admin import set_giso_config
                set_giso_config(_ran_key(date_str), date_str)
            except Exception:
                pass


def maybe_deposit_rank_credits(force: bool = False, block: bool = False) -> dict | None:
    """تریگر lazy و سبک.

    - هرگز درخواست/به‌روزرسانی کاربر را بلاک نمی‌کند: کار سنگین در thread پس‌زمینه اجرا
      می‌شود (مگر block=True برای تست). قفل غیرمسدودکننده از اجرای هم‌زمانِ چند کارگر در
      یک فرایند جلوگیری می‌کند.
    - force=True فارغ از ساعت اجرا می‌کند (تست/اجرای دستی).
    - در نبودِ تاریخِ سررسیده (و بدون force) بی‌درخش None برمی‌گرداند.
    """
    try:
        if not force and not _due_dates():
            return None
        if block:
            _run_background(force=force)
            return {"ok": True, "spawned": False}
        if not _WORKER_LOCK.acquire(blocking=False):
            return None  # کارگری در همین فرایند مشغول است

        def _worker():
            try:
                _run_background(force=force)
            except Exception as exc:
                logger.warning("rank daily background worker failed: %s", exc)
            finally:
                try:
                    _WORKER_LOCK.release()
                except RuntimeError:
                    pass

        threading.Thread(target=_worker, name="rank-daily-deposit", daemon=True).start()
        return {"ok": True, "spawned": True}
    except Exception as exc:
        logger.warning("maybe_deposit_rank_credits failed: %s", exc)
        return None


__all__ = ["deposit_rank_credits_for_date", "maybe_deposit_rank_credits"]
