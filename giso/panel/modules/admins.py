# -*- coding: utf-8 -*-
"""panel/modules/admins.py — مدیریت ادمین‌ها (فقط سوپرادمین): فهرست، درخواست‌ها، کلمه ادمینی و حذف.

فاز 5:
  - کلمه ادمینی (همان giso_config.admin_request_phrase ربات)
  - درخواست‌های ادمینی (تأیید/رد — همان giso_admin_requests ربات)
  - حذف ادمین دومرحله‌ای (بدون تایپ)

"""
import logging
import re

from flask import request, redirect, url_for, flash, session

from giso.panel.permissions import current_role_and_perms

logger = logging.getLogger("giso_panel_admins")


def _fetch_admin_request_identity(req_id: int) -> tuple:
    """خواندن phone/bale_id یک درخواست ادمینی از bot.db (برای پاک‌کردن لیست سیاه)."""
    try:
        from giso.base import get_bot_db_conn
        conn = get_bot_db_conn()
        try:
            row = conn.execute(
                "SELECT phone, bale_id FROM giso_admin_requests WHERE id=?", (int(req_id),)
            ).fetchone()
        finally:
            conn.close()
        if not row:
            return "", ""
        return str(row["bale_id"] or "").strip(), str(row["phone"] or "").strip()
    except Exception:
        return "", ""


def list_active_giso_admins() -> list:
    """لیست ادمین‌های تأییدشدهٔ فعال — بدون ادمین‌های تنزل‌یافته (لیست سیاه).

    چون sync سمت bot_edu (P10.4) ادمینِ حذف‌شده را دوباره به giso_admins
    برمی‌گرداند، این wrapper آن‌ها را از نمایش حذف می‌کند تا «حذف» واقعاً معنا داشته باشد.
    """
    try:
        from giso_admin import list_giso_admins
        from giso.base import is_admin_demoted
        out = []
        for a in list_giso_admins():
            bid = str(a.get("bale_id") or a.get("telegram_id") or "").strip()
            phone = str(a.get("phone") or "").strip()
            try:
                if is_admin_demoted(bale_id=bid, phone=phone):
                    continue
            except Exception:
                pass
            out.append(a)
        return out
    except Exception as e:
        logger.error(f"list_active_giso_admins: {e}")
        try:
            from giso_admin import list_giso_admins
            return list_giso_admins()
        except Exception:
            return []


def remove_giso_admin_completely(admin_id: int) -> bool:
    """حذف کامل ادمین از bot.db (جدول giso_admins) و تنزل is_admin در giso_users.

    برخلاف نسخه قبلی که فقط با id حذف می‌کرد، اینجا همه ردیف‌های منطبق (با همه
    فرمت‌های شماره + bale_id) پاک می‌شوند تا ردیف تکراری باقی نماند و commit
    صریح روی bot.db انجام می‌شود.
    """
    try:
        admin_id = int(admin_id or 0)
    except (TypeError, ValueError):
        return False
    if not admin_id:
        return False
    bale_id = ""
    phone = ""
    try:
        from giso.base import _phone_variants, get_bot_db_conn
        conn = get_bot_db_conn()
        try:
            # اطمینان از وجود جدول در bot.db
            conn.execute(
                "CREATE TABLE IF NOT EXISTS giso_admins ("
                "id INTEGER PRIMARY KEY AUTOINCREMENT, phone TEXT DEFAULT '', "
                "bale_id TEXT DEFAULT '', added_by INTEGER DEFAULT 0, added_at TEXT DEFAULT '')"
            )
            row = conn.execute("SELECT * FROM giso_admins WHERE id=?", (admin_id,)).fetchone()
            if not row:
                return False
            bale_id = str(row["bale_id"] or "").strip()
            phone = str(row["phone"] or "").strip()
            # محافظت از سوپرادمین اصلی
            if bale_id == "1191639507":
                return False
            digits = re.sub(r"\D", "", phone)
            if digits.endswith("9156012931"):
                return False
            # حذف همه ردیف‌های منطبق (id یا همه فرمت‌های شماره یا bale_id)
            variants = [v for v in _phone_variants(phone) if v]
            conds = ["id=?"]
            params = [admin_id]
            if bale_id:
                conds.append("bale_id=?")
                params.append(bale_id)
            if variants:
                marks = ",".join("?" * len(variants))
                conds.append(f"phone IN ({marks})")
                params.extend(variants)
            cur = conn.execute(f"DELETE FROM giso_admins WHERE {' OR '.join(conds)}", params)
            conn.commit()
            if cur.rowcount <= 0:
                return False
        finally:
            conn.close()
        # ── تبدیل به کاربر عادی (نه حذف کامل) + لیست سیاه ضد re-sync ──
        # ۱) تنزل is_admin در giso_users و نگه‌داشتن ردیف (کاربر عادی می‌شود).
        # ۲) ثبت در giso_demoted_admins تا sync سمت bot_edu (P10.4) که هر
        #    `bale_id IS NOT NULL` را به giso_admins برمی‌گرداند، نتواند او را
        #    دوباره ادمین کند.
        from giso.base import get_giso_db_conn, mark_admin_demoted
        variants = [v for v in _phone_variants(phone) if v]
        with get_giso_db_conn() as gconn:
            if bale_id:
                gconn.execute(
                    "UPDATE giso_users SET is_admin=0, pending_request=0 WHERE bale_id=?", (bale_id,)
                )
            if variants:
                marks = ",".join("?" * len(variants))
                gconn.execute(
                    f"UPDATE giso_users SET is_admin=0, pending_request=0 WHERE phone IN ({marks})",
                    variants,
                )
            gconn.commit()
        # لیست سیاه با بله‌آیدی (دقیق‌ترین) + شماره
        mark_admin_demoted(bale_id=bale_id, phone=phone)
        return True
    except Exception as exc:
        logger.error("remove_giso_admin_completely: %s", exc)
        return False


def _require_super():
    role, perms, bale_id = current_role_and_perms()
    if role != "super":
        flash("فقط سوپرادمین می‌تواند ادمین‌ها را مدیریت کند.", "warning")
        return redirect(url_for("panel.dashboard"))
    return None


def handle_post():
    """پردازش POST — فقط سوپرادمین (کلمه / درخواست / حذف)."""
    g = _require_super()
    if g:
        return g
    action = (request.form.get("action") or "").strip().lower()

    # فرم‌های نسخه‌های قدیمی دیگر حق تغییر permission ندارند.
    if action in {"refresh_sections", "save_permissions", "perm"}:
        flash("این تنظیمات ساده‌سازی شده است", "info")
        return redirect(url_for("panel.admins"))

    if action == "set_phrase":
        phrase = (request.form.get("phrase") or "").strip()
        # فاز جامع UX: پیام خطای واقعی + راستی‌آزمایی محلی قبل از ذخیره
        if len(phrase) < 4:
            flash("⚠️ کلمه ادمینی باید حداقل ۴ کاراکتر باشد (مثل عبارت مخفی که کاربر در ربات می‌فرستد).", "danger")
            return redirect(url_for("panel.admins") + "#pane-admins")
        if len(phrase) > 100:
            flash("⚠️ کلمه ادمینی بیش از حد طولانی است (حداکثر ۱۰۰ کاراکتر).", "danger")
            return redirect(url_for("panel.admins") + "#pane-admins")
        try:
            from giso_admin import set_admin_request_phrase, get_admin_request_phrase
            set_admin_request_phrase(phrase)
            from giso.base import invalidate_giso_config_cache
            invalidate_giso_config_cache("admin_request_phrase")
            saved = get_admin_request_phrase()
            if saved != phrase:
                flash("⚠️ کلمه ذخیره نشد — مقدار بازخوانی‌شده با مقدار واردشده یکی نیست. دوباره تلاش کنید.", "danger")
                return redirect(url_for("panel.admins") + "#pane-admins")
            flash("✅ کلمه ادمینی به‌روزرسانی شد و در ربات هم اعمال شد (برگشت به همین صفحه).", "success")
        except Exception as e:
            logger.error(f"panel set phrase: {e}")
            flash(f"❌ خطای واقعی در ذخیره کلمه ادمینی: {e}", "danger")
        return redirect(url_for("panel.admins") + "#pane-admins")

    # ── بررسی درخواست ادمینی (تأیید/رد) ──
    if action == "review_request":
        try:
            req_id = int(request.form.get("req_id", "0") or "0")
            approve = request.form.get("approve") == "1"
        except (TypeError, ValueError):
            req_id = 0
        try:
            from giso_admin import review_admin_request
            # اگر تأیید شود و قبلاً در لیست سیاه بود، باید آزاد شود تا ادمین شود
            if approve:
                _req_bid, _req_phone = _fetch_admin_request_identity(req_id)
                if _req_bid or _req_phone:
                    from giso.base import clear_admin_demoted
                    clear_admin_demoted(bale_id=_req_bid, phone=_req_phone)
            review_admin_request(req_id, approve)
            flash("درخواست ادمینی با موفقیت بررسی شد (وضعیت در ربات هم اعمال شد).", "success")
        except Exception as e:
            logger.error(f"panel review request: {e}")
            flash("خطا در بررسی درخواست.", "danger")
        return redirect(url_for("panel.admins"))

    # ── حذف همه درخواست‌های ادمینی + ادمین‌های فعال (بجز سوپر) ──
    if action == "delete_all_requests":
        try:
            from giso_admin import _connect, list_giso_admins
            conn = _connect()
            req_before = conn.execute("SELECT COUNT(*) FROM giso_admin_requests").fetchone()[0]
            conn.execute("DELETE FROM giso_admin_requests")
            conn.commit()
            conn.close()
            # حذف ادمین‌های فعال (بجز سوپرادمین)
            admins = list_giso_admins()
            removed = 0
            for a in admins:
                a_bid = str(a.get("bale_id", "") or a.get("telegram_id", "") or "")
                a_phone = str(a.get("phone", "") or "")
                if a_bid == "1191639507" or a_phone in ("09156012931", "+989156012931"):
                    continue
                try:
                    if remove_giso_admin_completely(a.get("id", 0)):
                        removed += 1
                except Exception:
                    pass
            flash(f"✅ {req_before} درخواست + {removed} ادمین حذف شد. سوپرادمین حفظ شد.", "success")
        except Exception as e:
            logger.error(f"delete_all_requests: {e}")
            flash("خطا در حذف.", "danger")
        return redirect(url_for("panel.admins"))

    # ── حذف ادمین (دومرحله‌ای) ──
    if action == "delete_admin":
        step = (request.form.get("step") or "").strip()
        try:
            admin_id = int(request.form.get("admin_id", "0") or "0")
        except (TypeError, ValueError):
            admin_id = 0
        if not admin_id:
            flash("شناسه ادمین نامعتبر است.", "danger")
            return redirect(url_for("panel.admins"))
        if step == "confirm":
            try:
                ok = remove_giso_admin_completely(admin_id)
                session.pop("panel_delete_admin_id", None)
                if ok:
                    flash("ادمین از سایت و ربات حذف شد.", "success")
                else:
                    flash("حذف ادمین انجام نشد.", "danger")
            except Exception as e:
                logger.error(f"panel delete admin: {e}")
                flash("خطا در حذف ادمین.", "danger")
            return redirect(url_for("panel.admins"))
        # مرحله اول
        session["panel_delete_admin_id"] = admin_id
        session.modified = True
        flash("⚠️ برای حذف نهایی، دوباره دکمه «حذف» را بزنید.", "warning")
        return redirect(url_for("panel.admins"))

    flash("عملیات نامعتبر است.", "warning")
    return redirect(url_for("panel.admins"))


def context():
    admins = []
    try:
        from giso_admin import list_giso_admins, _get_main_admin_ids
        rows = list_giso_admins()  # list_giso_admins حالا سوپرادمین رو حذف می‌کنه
        main_ids = _get_main_admin_ids()
        for a in rows:
            bid = str(a.get("bale_id") or a.get("telegram_id") or "").strip()
            # فیلتر نهایی: سوپرادمین نمایش داده نشود
            try:
                if int(bid) in main_ids:
                    continue
            except (ValueError, TypeError):
                pass
            phone = str(a.get("phone", "") or "")
            if phone in ("09156012931", "+989156012931"):
                continue
            # لیست سیاه: ادمینِ حذف‌شده نباید در لیست نمایش داده شود
            try:
                from giso.base import is_admin_demoted
                if is_admin_demoted(bale_id=bid, phone=phone):
                    continue
            except Exception:
                pass
            admins.append({
                "id": a.get("id"),
                "phone": a.get("phone") or "",
                "bale_id": bid,
                "added_at": a.get("added_at") or "",
            })
    except Exception as e:
        logger.error(f"panel admins: {e}")

    phrase = ""
    requests_list = []
    try:
        from giso_admin import get_admin_request_phrase, list_admin_requests
        phrase = get_admin_request_phrase()
        requests_list = list_admin_requests("pending")
    except Exception as e:
        logger.error(f"panel admins meta: {e}")

    pending_delete = ""
    try:
        pending_delete = str(session.get("panel_delete_admin_id") or "")
    except Exception:
        pass

    return {
        "admins": admins,
        "phrase": phrase,
        "requests": requests_list,
        "pending_delete": pending_delete,
    }