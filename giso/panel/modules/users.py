# -*- coding: utf-8 -*-
"""panel/modules/users.py — مدیریت کامل کاربران (فاز 4.5): جستجو/بن/اعتبار/حذف دومرحله‌ای."""
import logging

from flask import request, redirect, url_for, flash, session
from flask_login import current_user

from giso.models import db, User
from giso.base import get_giso_db_conn, normalize_phone
from giso.config import is_super_admin
from giso.panel.permissions import current_role_and_perms
from giso.account_password_vault import (
    remember_account_password,
    load_stored_password,
    current_password_if_matches,
)

logger = logging.getLogger("giso_panel_users")


def _require_super():
    role, perms, bale_id = current_role_and_perms()
    if role != "super":
        flash("فقط سوپرادمین می‌تواند این عملیات را انجام دهد.", "warning")
        return redirect(url_for("panel.dashboard"))
    return None


def handle_ban(user_id):
    g = _require_super()
    if g:
        return g
    try:
        u = User.query.get_or_404(user_id)
        if is_super_admin(phone=u.phone):
            flash("نمی‌توانید سوپرادمین را بن کنید.", "danger")
            return redirect(url_for("panel.users"))
        u.is_banned = 1
        u.ban_reason = (request.form.get("ban_reason") or "").strip()
        db.session.commit()
        try:
            from giso.panel.modules.notifications import safe_log as _nlog
            _nlog("users", "ban", "بن کاربر", f"{u.phone} — {u.ban_reason or ''}",
                  source_type="user_ban", source_id=u.id)
        except Exception:
            pass
        flash(f"کاربر {u.phone} بن شد.", "success")
    except Exception as e:
        logger.error(f"panel user ban: {e}")
        flash("خطا در بن کاربر.", "danger")
    return redirect(url_for("panel.users"))


def handle_unban(user_id):
    g = _require_super()
    if g:
        return g
    try:
        u = User.query.get_or_404(user_id)
        u.is_banned = 0
        u.ban_reason = ""
        db.session.commit()
        try:
            from giso.panel.modules.notifications import safe_log as _nlog
            _nlog("users", "unban", "رفع بن کاربر", f"{u.phone}",
                  source_type="user_unban", source_id=u.id)
        except Exception:
            pass
        flash(f"بن کاربر {u.phone} برداشته شد.", "success")
    except Exception as e:
        logger.error(f"panel user unban: {e}")
        flash("خطا در رفع بن.", "danger")
    return redirect(url_for("panel.users"))


def handle_update(user_id):
    """ویرایش نام (فقط سوپرادمین)."""
    g = _require_super()
    if g:
        return g
    try:
        u = User.query.get_or_404(user_id)
        new_name = (request.form.get("name") or "").strip()[:150]
        if new_name:
            u.name = new_name
            if not (u.first_name or ""):
                u.first_name = new_name.split()[0] if new_name.split() else new_name
        db.session.commit()
        flash("نام کاربر به‌روزرسانی شد.", "success")
    except Exception as e:
        logger.error(f"panel user update: {e}")
        flash("خطا در به‌روزرسانی.", "danger")
    return redirect(url_for("panel.users", q=request.form.get("phone", "")))


def handle_wallet(user_id):
    """اصلاح cash/spend؛ route و سرویس هر دو مجوز سوپرادمین را enforce می‌کنند."""
    g = _require_super()
    if g:
        return g
    try:
        u = User.query.get_or_404(user_id)
        from giso.wallet import manual_adjust
        ok, message = manual_adjust(
            user_id,
            request.form.get("delta", ""),
            request.form.get("balance_scope", "cash"),
            request.form.get("reason", "") or "اصلاح مانده از پنل سوپرادمین",
        )
        flash(message, "success" if ok else "danger")
        phone = u.phone
    except Exception as e:
        logger.error(f"panel user wallet: {e}")
        flash("خطا در تغییر مانده کیف پول.", "danger")
        phone = ""
    return redirect(url_for("panel.users", q=phone))


def handle_reset_password(user_id):
    """مورد ۱۳ help.md: تغییر رمز کاربر توسط سوپرادمین (با ثبت رویداد امنیتی)."""
    g = _require_super()
    if g:
        return g
    new_pass = (request.form.get("new_password") or "").strip()
    from giso.security import validate_new_password
    _ok, _msg = validate_new_password(new_pass)
    if not _ok:
        flash(_msg, "danger")
        return redirect(url_for("panel.users"))
    u = User.query.get_or_404(user_id)
    from werkzeug.security import generate_password_hash
    u.password_hash = generate_password_hash(new_pass, method="pbkdf2:sha256")
    db.session.commit()
    remember_account_password(u.id, new_pass)
    try:
        from giso.panel.modules.notifications import log_notification
        log_notification("security", "admin_password_reset", "تغییر رمز کاربر توسط سوپرادمین",
                         f"کاربر {u.phone}", source_type="password_reset", source_id=int(user_id))
    except Exception:
        pass
    flash("رمز عبور کاربر با موفقیت تغییر کرد.", "success")
    return redirect(url_for("panel.users", q=u.phone))


def handle_delete(user_id):
    """حذف کامل کاربر — فقط سوپرادمین (یک‌مرحله‌ای).

    اصلاح 2026-08-23: فرم پنل در همان ارسال اول step=confirm می‌فرستاد درحالی‌که
    منطق قدیمی انتظار session دو‌مرحله‌ای («panel_delete_user_id») را داشت که هرگز
    مقدار نگرفته بود → همیشه «درخواست حذف نامعتبر است» نمایش داده می‌شد.
    لایه‌های محافظت: require_super (فقط سوپرادمین) + CSRF (همه‌ی POSTها) +
    دیالوگ تأیید جاوااسکریپت سمت فرانت — بنابراین حذف مستقیم در همین ارسال امن است.
    """
    g = _require_super()
    if g:
        return g
    try:
        u = User.query.get_or_404(user_id)
    except Exception:
        flash("کاربر موردنظر پیدا نشد.", "danger")
        return redirect(url_for("panel.users"))
    # سوپرادمین اصلی هرگز قابل حذف نیست (گارد دوم، مستقل از require_super)
    if is_super_admin(phone=u.phone):
        flash("نمی‌توانید سوپرادمین را حذف کنید.", "danger")
        return redirect(url_for("panel.users"))
    phone = u.phone
    # حذف کامل (سایت + ربات + داده‌های وابسته) در یک transaction اتمیک
    from giso.base import erase_user_data
    er = erase_user_data(phone)
    if not er.get("ok"):
        flash(f"خطا در حذف کاربر: {er.get('reason') or 'خطای دیتابیس'}", "danger")
        return redirect(url_for("panel.users"))
    db.session.expire_all()
    # پاک‌سازی هر باقی‌مانده‌ی احتمالی از منطق قدیمی دو‌مرحله‌ای
    session.pop("panel_delete_user_id", None)
    session.modified = True
    try:
        from giso.panel.modules.notifications import safe_log as _nlog
        _nlog("users", "delete", "حذف کاربر", f"{phone}",
              source_type="user_delete", source_id=user_id)
    except Exception:
        pass
    flash("✅ کاربر با موفقیت حذف شد.", "success")
    return redirect(url_for("panel.users"))


# ───────────────── امنیت حساب اختصاصی «خانم مهندس صادقی» ─────────────────
# فقط سوپرادمین: تیک پیام امنیتی (ارسال کد تأیید ورود پنل به بلهٔ سوپرادمین) +
# رمز امنیتی ثابت (پیش‌فرض 1370) + ساخت/بازنشانی حساب سایت با همان رمز.

def get_special_security() -> dict:
    """وضعیت فعلی کارت «امنیت حساب اختصاصی» برای صفحهٔ کاربران (فقط super)."""
    from giso.stepup import (_special_admin_security_cfg, _SPECIAL_STEPUP_ENABLED_KEY,
                             _SPECIAL_FIXED_CODE_KEY)
    from giso.config import SPECIAL_ADMIN_PROFILE
    cfg = _special_admin_security_cfg()
    phone = (SPECIAL_ADMIN_PROFILE.get("phone") or "").strip()
    norm_phone = normalize_phone(phone) or phone
    user_row = None
    try:
        from giso.base import _phone_variants
        variants = list(_phone_variants(phone)) or [norm_phone]
        user_row = User.query.filter(User.phone.in_(variants)).first()
    except Exception as e:
        logger.error("special admin lookup: %s", e)
    return {
        "enabled": cfg["enabled"],
        "code": cfg["code"],
        "phone": phone,
        "full_name": SPECIAL_ADMIN_PROFILE.get("full_name", "خانم مهندس صادقی"),
        "account_exists": bool(user_row),
        "account_last_login": (user_row.last_login if user_row else "") or "—",
        "keys_hint": f"{_SPECIAL_STEPUP_ENABLED_KEY} / {_SPECIAL_FIXED_CODE_KEY}",
    }


def handle_special_security():
    """ذخیرهٔ تیک پیام امنیتی + رمز امنیتی + (اختیاری) ساخت/بازنشانی رمز حساب سایت."""
    g = _require_super()
    if g:
        return g
    from giso.stepup import _SPECIAL_STEPUP_ENABLED_KEY, _SPECIAL_FIXED_CODE_KEY
    from giso.config import SPECIAL_ADMIN_PROFILE

    phone = (SPECIAL_ADMIN_PROFILE.get("phone") or "").strip()
    enabled = "1" if request.form.get("security_enabled") == "1" else "0"
    code = (request.form.get("fixed_code") or "").strip() or "1370"
    apply_password = request.form.get("apply_password") == "1"
    if not code.isdigit():
        flash("رمز امنیتی باید فقط عدد باشد (۴ تا ۱۲ رقم).", "danger")
        return redirect(url_for("panel.users"))
    if not 4 <= len(code) <= 12:
        flash("رمز امنیتی باید بین ۴ تا ۱۲ رقم باشد.", "danger")
        return redirect(url_for("panel.users"))
    try:
        from giso_admin import set_giso_config
        from giso.base import invalidate_giso_config_cache
        set_giso_config(_SPECIAL_STEPUP_ENABLED_KEY, enabled)
        set_giso_config(_SPECIAL_FIXED_CODE_KEY, code)
        invalidate_giso_config_cache(_SPECIAL_STEPUP_ENABLED_KEY)
        invalidate_giso_config_cache(_SPECIAL_FIXED_CODE_KEY)
    except Exception as e:
        logger.error("special security save: %s", e)
        flash("ذخیرهٔ تنظیمات پیام امنیتی ناموفق بود.", "danger")
        return redirect(url_for("panel.users"))

    account_note = ""
    if apply_password:
        try:
            from werkzeug.security import generate_password_hash
            from giso.base import _phone_variants
            norm = normalize_phone(phone) or phone
            variants = list(_phone_variants(phone)) or [norm]
            u = User.query.filter(User.phone.in_(variants)).first()
            if not u:
                # ساخت حساب پیش‌فرض سایت با رمز امنیتی تا تست بدون بله ممکن شود
                u = User(
                    phone=norm,
                    name=SPECIAL_ADMIN_PROFILE.get("full_name", ""),
                    first_name=SPECIAL_ADMIN_PROFILE.get("first_name", ""),
                    last_name=SPECIAL_ADMIN_PROFILE.get("last_name", ""),
                    city=SPECIAL_ADMIN_PROFILE.get("city", ""),
                    password_hash=generate_password_hash(code, method="pbkdf2:sha256"),
                )
                db.session.add(u)
                account_note = " و حساب سایت با همین رمز ساخته شد"
            else:
                u.password_hash = generate_password_hash(code, method="pbkdf2:sha256")
                account_note = " و رمز ورود سایت تنظیم شد"
            db.session.commit()
            remember_account_password(u.id, code)
        except Exception as e:
            logger.error("special account provision: %s", e)
            db.session.rollback()
            flash("تنظیمات ذخیره شد ولی ساخت/بازنشانی حساب سایت ناموفق بود.", "warning")
            return redirect(url_for("panel.users", q=phone))

    try:
        from giso.panel.modules.notifications import log_notification
        log_notification(
            "security", "special_admin_security",
            "تغییر پیام امنیتی حساب اختصاصی",
            f"فعال={enabled} | ساخت/تغییر رمز={'بله' if apply_password else 'خیر'}",
            source_type="special_admin", source_id=0,
        )
    except Exception:
        pass
    flash(
        ("✅ پیام امنیتی فعال است — کد تأیید ورود پنل به بلهٔ سوپرادمین ارسال می‌شود."
         if enabled == "1" else
         "ℹ️ پیام امنیتی خاموش شد — ورود پنل فقط با رمز امنیتی ثابت انجام می‌شود.")
        + account_note + ".",
        "success",
    )
    return redirect(url_for("panel.users", q=SPECIAL_ADMIN_PROFILE.get("phone", "")))


def get_stats():
    """گزارش کلی کاربران (دیتابیس واقعی) — فاز 5."""
    stats = {"total": 0, "today": 0, "this_month": 0, "banned": 0, "admins": 0}
    try:
        from datetime import datetime, timedelta
        from giso_admin import list_giso_admins
        stats["admins"] = len(list_giso_admins())
        today = datetime.now().strftime("%Y-%m-%d")
        month_ago = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
        with get_giso_db_conn() as conn:
            stats["total"] = int(conn.execute("SELECT COUNT(*) FROM giso_web_auth").fetchone()[0] or 0)
            stats["today"] = int(conn.execute(
                "SELECT COUNT(*) FROM giso_web_auth WHERE created_at LIKE ?", (f"{today}%",)).fetchone()[0] or 0)
            stats["this_month"] = int(conn.execute(
                "SELECT COUNT(*) FROM giso_web_auth WHERE created_at >= ?", (month_ago,)).fetchone()[0] or 0)
        stats["banned"] = int(User.query.filter_by(is_banned=1).count())
    except Exception as e:
        logger.error(f"panel users stats: {e}")
    return stats


def context():
    q = (request.args.get("q") or "").strip()
    users = []
    try:
        if q:
            from sqlalchemy import or_
            qn = normalize_phone(q)
            conds = []
            if qn:
                conds.append(User.phone == qn)
            conds.append(User.name.like(f"%{q}%"))
            users = User.query.filter(or_(*conds)).order_by(User.id.desc()).limit(50).all()
        else:
            users = User.query.order_by(User.id.desc()).limit(30).all()
    except Exception as e:
        logger.error(f"panel users: {e}")
    rows = []
    role, _perms, _bale_id = current_role_and_perms()
    can_view_finance = role == "super"

    # ── رفع N+1: مانده‌ها و تراکنش‌ها با دو کوئری گروهی (به‌جای ۳ اتصال به‌ازای هر کاربر) ──
    balances_map = {}
    txn_map = {}
    user_ids = [u.id for u in users]
    if user_ids and can_view_finance:
        try:
            marks = ",".join("?" * len(user_ids))
            with get_giso_db_conn() as conn:
                # ۱) مانده cash/spend برای همه کاربران صفحه در یک کوئری
                bal_rows = conn.execute(
                    f"SELECT user_id, COALESCE(NULLIF(balance_scope,''),'cash') AS scope, "
                    f"COALESCE(SUM(amount),0) AS amt "
                    f"FROM wallet_transactions WHERE user_id IN ({marks}) "
                    f"AND status IN ('available','used','pending','paid') "
                    f"GROUP BY user_id, scope",
                    user_ids,
                ).fetchall()
                raw = {}
                for r in bal_rows:
                    raw.setdefault(r["user_id"], {"cash": 0, "spend": 0})
                    scope = r["scope"] if r["scope"] in ("cash", "spend") else "cash"
                    raw[r["user_id"]][scope] += int(r["amt"] or 0)
                for uid, v in raw.items():
                    cash = max(0, v["cash"]); spend = max(0, v["spend"])
                    balances_map[uid] = {"cash": cash, "spend": spend, "usable": cash + spend}
                # ۲) آخرین تراکنش‌ها برای همه کاربران صفحه در یک کوئری (۶ تراکنش اخیر هر کاربر)
                tx_rows = conn.execute(
                    f"SELECT user_id, id, kind, amount, status, source_type, source_id, "
                    f"balance_scope, description, created_at "
                    f"FROM wallet_transactions WHERE user_id IN ({marks}) "
                    f"ORDER BY id DESC LIMIT 2000",
                    user_ids,
                ).fetchall()
                txn_map = {uid: [] for uid in user_ids}
                for t in tx_rows:
                    if len(txn_map[t["user_id"]]) < 6:
                        txn_map[t["user_id"]].append(dict(t))
        except Exception as e:
            logger.error(f"panel users batch finance: {e}")

    for u in users:
        bal = balances_map.get(u.id, {"usable": 0, "cash": 0, "spend": 0})
        rows.append({
            "id": u.id,
            "phone": u.phone,
            "name": (u.name or "").strip() or (u.first_name or ""),
            "created_at": u.created_at or "",
            "last_login": u.last_login or "",
            "is_banned": bool(getattr(u, "is_banned", 0)),
            "ban_reason": getattr(u, "ban_reason", "") or "",
            "balance": bal["usable"],
            "cash_balance": bal["cash"],
            "spend_balance": bal["spend"],
            "transactions": txn_map.get(u.id, []) if can_view_finance else [],
        })
    revealed = {}
    try:
        bag = session.pop("giso_reveal_passwords", None) or {}
        session.modified = True
        if isinstance(bag, dict):
            revealed = {str(k): str(v) for k, v in bag.items() if v}
    except Exception:
        revealed = {}
    for row in rows:
        row["revealed_password"] = revealed.get(str(row["id"]), "")
    ctx = {"users": rows, "q": q, "stats": get_stats()}
    if can_view_finance:  # یعنی سوپرادمین — کارت امنیت حساب اختصاصی بدانان نمایش داده می‌شود
        try:
            ctx["special_security"] = get_special_security()
        except Exception as e:
            logger.error("special security context: %s", e)
    return ctx


def _save_visible_pass(user_id, password: str) -> None:
    remember_account_password(user_id, password)


def _clear_visible_pass(user_id) -> None:
    """مسیر قدیمی پاک‌کردن خزانه دیگر استفاده نمی‌شود؛ رمز فعلی باید بماند."""
    return


def handle_show_password(user_id):
    """نمایش رمز فعلی روی حساب — فقط سوپرادمین؛ فقط اگر با هش ورود یکی باشد."""
    g = _require_super()
    if g:
        return g
    u = User.query.get_or_404(user_id)
    try:
        from giso.security import rate_limit, audit_event
        allowed, retry = rate_limit(
            "super_show_password", 20, 3600,
            identifier=f"{getattr(current_user, 'id', '')}:{user_id}",
        )
        if not allowed:
            flash(f"تعداد نمایش رمز زیاد است؛ {retry} ثانیه دیگر.", "warning")
            return redirect(url_for("panel.users", q=u.phone))
        candidate = load_stored_password(u.id)
        current = current_password_if_matches(u.password_hash or "", candidate)
        if current:
            bag = session.get("giso_reveal_passwords") or {}
            if not isinstance(bag, dict):
                bag = {}
            bag[str(u.id)] = current
            session["giso_reveal_passwords"] = bag
            session.modified = True
            try:
                audit_event("show_password", "success", target=str(u.id),
                            details="revealed current hash-matched password")
            except Exception:
                pass
            flash("رمز فعلی همین حساب در کارت کاربر نمایش داده شد (فقط همین بار).", "success")
        else:
            try:
                audit_event("show_password", "failed", target=str(u.id),
                            details="no hash-matched current password")
            except Exception:
                pass
            flash(
                "رمز فعلی این حساب یک‌طرفه هش شده و قابل بازیابی نیست. "
                "با «تغییر رمز» یک رمز جدید روی همین حساب می‌نشیند و همان رمز فعلی می‌شود.",
                "warning",
            )
    except Exception as e:
        flash("خطا در نمایش رمز.", "danger")
        logger.error("show password: %s", e)
    return redirect(url_for("panel.users", q=u.phone))

