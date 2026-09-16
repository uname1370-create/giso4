# -*- coding: utf-8 -*-
"""
giso/stepup.py — تأیید دومرحله‌ای (Step-up) پنل ادمین + ثبت‌نام شماره‌های حساس (Phase 2, Unit U3)
استخراج‌شده از giso/app.py بدون تغییر رفتار؛ همه نام‌ها در giso.app re-export می‌شوند.
"""
import hashlib
import logging
import secrets
import time
from flask import session

from giso.config import Config, SUPERADMIN_BALE_ID, is_super_admin, is_special_admin
from giso.base import (get_bot_db_conn, normalize_phone, _phone_variants,
                       is_admin_demoted)

logger = logging.getLogger("giso_stepup")

_ADMIN_PANEL_CODE_TTL_SECONDS = 300
_ADMIN_PANEL_SESSION_TTL_SECONDS = 1800
_ADMIN_PANEL_MAX_ATTEMPTS = 5
_ADMIN_PANEL_RESEND_GAP_SECONDS = 45

_SENSITIVE_REGISTER_CODE_TTL_SECONDS = 300
_SENSITIVE_REGISTER_MAX_ATTEMPTS = 5
_SENSITIVE_REGISTER_RESEND_GAP_SECONDS = 45


def _admin_panel_clear_state(clear_verified: bool = True, clear_next: bool = True):
    for key in (
        "admin_panel_code_hash",
        "admin_panel_code_expires_at",
        "admin_panel_attempts",
        "admin_panel_verify_phone",
        "admin_panel_bale_id",
        "admin_panel_last_sent_at",
    ):
        session.pop(key, None)
    if clear_next:
        session.pop("admin_panel_next", None)
    if clear_verified:
        session.pop("admin_panel_verified_until", None)
        session.pop("admin_panel_verified_phone", None)
    session.modified = True


def _admin_panel_hash_code(phone_norm: str, code: str) -> str:
    raw = f"{Config.SECRET_KEY}|{phone_norm}|{code}".encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _admin_panel_target(phone_norm: str) -> dict | None:
    phone_norm = normalize_phone(phone_norm)
    if not phone_norm:
        return None
    if is_super_admin(phone=phone_norm):
        return {"role": "super", "bale_id": str(SUPERADMIN_BALE_ID), "phone": phone_norm}
    if is_special_admin(phone=phone_norm):
        # نقش سایت «special» حتی اگر شماره در giso_admins هم باشد؛ ورود پنل و
        # سایدبار اختصاصی به این نقش وابسته‌اند (ربات از این تابع استفاده نمی‌کند).
        return {"role": "special", "bale_id": "", "phone": phone_norm}
    try:
        from giso_admin import find_giso_admin_by_phone
        from giso.base import _phone_variants
        row = None
        for candidate in _phone_variants(phone_norm):
            row = find_giso_admin_by_phone(candidate)
            if row:
                break
    except Exception as exc:
        logger.error("admin target lookup failed: %s", exc)
        row = None
    # fallback مستقیم به bot.db؛ lookup ماژول ربات نباید ورود پنل وب را بشکند.
    if not row:
        try:
            candidates = list(_phone_variants(phone_norm))
            conn = get_bot_db_conn()
            try:
                marks = ",".join("?" for _ in candidates)
                row = conn.execute(
                    f"SELECT * FROM giso_admins WHERE phone IN ({marks}) LIMIT 1", candidates
                ).fetchone()
                row = dict(row) if row else None
            finally:
                conn.close()
        except Exception as exc:
            logger.error("admin target DB fallback failed: %s", exc)
    if not row:
        return None
    bale_id = str(row.get("bale_id") or row.get("telegram_id") or "").strip()
    # لیست سیاه: ادمینِ حذف‌شده نباید به پنل مدیریت دسترسی داشته باشد
    try:
        from giso.base import is_admin_demoted
        if is_admin_demoted(bale_id=bale_id, phone=phone_norm):
            return None
    except Exception:
        pass
    if not bale_id.isdigit():
        return {"role": "admin", "bale_id": "", "phone": phone_norm}
    return {"role": "admin", "bale_id": bale_id, "phone": phone_norm}


def _admin_panel_is_verified(phone_norm: str) -> bool:
    phone_norm = normalize_phone(phone_norm)
    verified_phone = normalize_phone(session.get("admin_panel_verified_phone", "") or "")
    try:
        verified_until = int(session.get("admin_panel_verified_until") or 0)
    except (TypeError, ValueError):
        verified_until = 0
    now_ts = int(time.time())
    if phone_norm and verified_phone == phone_norm and verified_until > now_ts:
        return True
    if verified_until and verified_until <= now_ts:
        session.pop("admin_panel_verified_until", None)
        session.pop("admin_panel_verified_phone", None)
        session.modified = True
    return False


def _generate_admin_panel_code() -> str:
    return f"{secrets.randbelow(900000) + 100000}"


# ───────────────── پیام امنیتی حساب اختصاصی (خانم مهندس صادقی) ─────────────────
# مدیریت این دو کلید: پنل سوپرادمین ← مدیریت کاربران ← کارت «امنیت حساب اختصاصی».
# همان ذخیرهٔ مشترک giso_config (bot.db) است؛ ربات هم می‌تواند بخواند.
_SPECIAL_STEPUP_ENABLED_KEY = "special_admin_stepup_enabled"
_SPECIAL_FIXED_CODE_KEY = "special_admin_fixed_code"
_SPECIAL_DEFAULT_FIXED_CODE = "1370"


def _special_admin_security_cfg() -> dict:
    """وضعیت «پیام امنیتی» ورود پنل برای حساب اختصاصی.

    enabled=True  → هنگام ورود به پنل، کد تأیید به بلهٔ سوپرادمین ارسال می‌شود
                    (تأیید دومرحله‌ای با دسترسیِ موجود مدیر ارشد).
    enabled=False → رمز امنیتی ثابت (پیش‌فرض 1370) مستقیم پذیرفته می‌شود تا تست
                    بدون بله ممکن باشد.
    """
    enabled, code = True, _SPECIAL_DEFAULT_FIXED_CODE
    try:
        from giso.base import cached_giso_config
        raw = str(cached_giso_config(_SPECIAL_STEPUP_ENABLED_KEY, "1", ttl_seconds=15) or "1").strip()
        enabled = raw not in ("0", "false", "off", "خاموش")
        candidate = str(cached_giso_config(_SPECIAL_FIXED_CODE_KEY, _SPECIAL_DEFAULT_FIXED_CODE, ttl_seconds=15) or "").strip()
        if candidate.isdigit() and 4 <= len(candidate) <= 12:
            code = candidate
    except Exception:
        pass
    return {"enabled": enabled, "code": code}


def _send_admin_panel_code_to_bot(bale_id: str, code: str, phone_norm: str) -> tuple[bool, str]:
    bid = str(bale_id or "").strip()
    if not bid.isdigit():
        return False, "شناسه رباتی ادمین برای ارسال کد ثبت نشده است."
    try:
        from giso.base import _token_from_env, _token_from_db
        import requests as _req
        token = _token_from_env() or _token_from_db() or ""
        if not token:
            return False, "توکن ربات برای ارسال کد تأیید در دسترس نیست."
        text = (
            "🔐 کد تأیید پنل مدیریت سایت گیسو\n\n"
            f"کد ورود: {code}\n"
            f"اعتبار: {int(_ADMIN_PANEL_CODE_TTL_SECONDS // 60)} دقیقه\n"
            f"شماره حساب سایت: {phone_norm}\n\n"
            "اگر خودت درخواست ندادی، این کد را نادیده بگیر."
        )
        resp = _req.post(
            f"https://tapi.bale.ai/bot{token}/sendMessage",
            json={"chat_id": int(bid), "text": text},
            timeout=12,
        )
        if int(getattr(resp, "status_code", 500) or 500) >= 400:
            return False, "ارسال کد به ربات ناموفق بود."
        return True, "کد تأیید به ربات شما ارسال شد."
    except Exception as e:
        logger.warning(f"_send_admin_panel_code_to_bot: {e}")
        return False, "در ارسال کد تأیید به ربات خطا رخ داد."


def _admin_panel_issue_code_via(phone_norm: str, force: bool, code_generator, code_sender) -> tuple[bool, str]:
    """منطق مشترک صدور کد؛ مولد/ارسال‌کننده تزریق‌پذیر تا سطح re-export در giso.app
    قابل patch/testing بماند (همان قرارداد قبل از استخراج U3)."""
    phone_norm = normalize_phone(phone_norm)
    target = _admin_panel_target(phone_norm)
    if not target:
        return False, "این حساب دسترسی به پنل مدیریت ندارد."
    special_mode = is_special_admin(phone=phone_norm)
    now_ts = int(time.time())
    try:
        last_sent = int(session.get("admin_panel_last_sent_at") or 0)
    except (TypeError, ValueError):
        last_sent = 0
    if not force and last_sent and (now_ts - last_sent) < _ADMIN_PANEL_RESEND_GAP_SECONDS:
        wait_left = _ADMIN_PANEL_RESEND_GAP_SECONDS - (now_ts - last_sent)
        return False, f"کد قبلاً ارسال شده؛ لطفاً {wait_left} ثانیه دیگر دوباره تلاش کن."

    # ── حساب اختصاصی «خانم مهندس»: پیام امنیتی قابل‌تنظیم از پنل سوپرادمین ──
    if special_mode:
        cfg = _special_admin_security_cfg()
        if not cfg["enabled"]:
            # کد پیش‌فرض قابل‌حدس است؛ تا زمانی که سوپرادمین کد جدید تنظیم نکرده،
            # ورود با پیام امنیتی خاموش کلاً رد می‌شود (رفع باگ 🟡 آئودیت).
            if str(cfg["code"]) == _SPECIAL_DEFAULT_FIXED_CODE:
                return False, "کد پیش‌فرض قابل استفاده نیست. لطفاً کد جدید تنظیم کنید."
            # تیک پیام امنیتی خاموش: ورود فقط با رمز امنیتی ثابت؛ هیچ پیامی به بله نمی‌رود.
            session["admin_panel_code_hash"] = _admin_panel_hash_code(phone_norm, cfg["code"])
            session["admin_panel_code_expires_at"] = now_ts + _ADMIN_PANEL_CODE_TTL_SECONDS
            session["admin_panel_attempts"] = 0
            session["admin_panel_verify_phone"] = phone_norm
            session["admin_panel_bale_id"] = ""
            session["admin_panel_last_sent_at"] = now_ts
            session.modified = True
            return True, "پیام امنیتی این حساب غیرفعال است؛ رمز امنیتی تعیین‌شده توسط سوپرادمین را وارد کن."
        # تیک پیام امنیتی روشن: به‌سبب نبود بلهٔ فعال روی این شماره، کد تأیید به
        # بلهٔ «سوپرادمین» می‌رود تا تأیید دومرحله‌ای با دسترسی موجود انجام شود.
        delivery_bid = str(SUPERADMIN_BALE_ID)
        sent_notice = "پیام امنیتی به بلهٔ سوپرادمین ارسال شد؛ کد تأیید را از مدیر ارشد بگیر."
    else:
        if not target.get("bale_id"):
            return False, "برای این ادمین شناسه رباتی ثبت نشده؛ اول ربات را /start کن و شماره‌ات را در ربات ثبت کن."
        delivery_bid = str(target["bale_id"])
        sent_notice = ""

    code = code_generator()
    ok, msg = code_sender(delivery_bid, code, phone_norm)
    if not ok:
        return False, msg
    session["admin_panel_code_hash"] = _admin_panel_hash_code(phone_norm, code)
    session["admin_panel_code_expires_at"] = now_ts + _ADMIN_PANEL_CODE_TTL_SECONDS
    session["admin_panel_attempts"] = 0
    session["admin_panel_verify_phone"] = phone_norm
    session["admin_panel_bale_id"] = str(delivery_bid)
    session["admin_panel_last_sent_at"] = now_ts
    session.modified = True
    return True, (sent_notice or msg)


def _admin_panel_issue_code(phone_norm: str, force: bool = False) -> tuple[bool, str]:
    return _admin_panel_issue_code_via(
        phone_norm, force, _generate_admin_panel_code, _send_admin_panel_code_to_bot,
    )


def _admin_panel_verify_code(phone_norm: str, code: str) -> tuple[bool, str]:
    phone_norm = normalize_phone(phone_norm)
    code = str(code or "").strip()
    if not phone_norm or not code:
        return False, "کد تأیید را کامل وارد کن."
    pending_phone = normalize_phone(session.get("admin_panel_verify_phone", "") or "")
    if pending_phone != phone_norm:
        return False, "درخواست تأیید معتبر نیست. دوباره از اول اقدام کن."
    try:
        expires_at = int(session.get("admin_panel_code_expires_at") or 0)
        attempts = int(session.get("admin_panel_attempts") or 0)
    except (TypeError, ValueError):
        expires_at = 0
        attempts = 0
    now_ts = int(time.time())
    if not expires_at or expires_at <= now_ts:
        return False, "زمان اعتبار کد تمام شده است. کد جدید بگیر."
    if attempts >= _ADMIN_PANEL_MAX_ATTEMPTS:
        return False, "تعداد تلاش مجاز تمام شده است. کد جدید بگیر."
    session["admin_panel_attempts"] = attempts + 1
    session.modified = True
    expected_hash = session.get("admin_panel_code_hash", "") or ""
    if expected_hash != _admin_panel_hash_code(phone_norm, code):
        return False, "کد واردشده صحیح نیست."
    session["admin_panel_verified_until"] = now_ts + _ADMIN_PANEL_SESSION_TTL_SECONDS
    session["admin_panel_verified_phone"] = phone_norm
    _admin_panel_clear_state(clear_verified=False, clear_next=False)
    return True, "تأیید با موفقیت انجام شد."


def _admin_panel_current_stepup_status(phone_norm: str) -> dict:
    phone_norm = normalize_phone(phone_norm)
    now_ts = int(time.time())
    pending_phone = normalize_phone(session.get("admin_panel_verify_phone", "") or "")
    try:
        expires_at = int(session.get("admin_panel_code_expires_at") or 0)
        attempts = int(session.get("admin_panel_attempts") or 0)
        last_sent = int(session.get("admin_panel_last_sent_at") or 0)
    except (TypeError, ValueError):
        expires_at = attempts = last_sent = 0
    return {
        "verified": _admin_panel_is_verified(phone_norm),
        "pending": pending_phone == phone_norm and expires_at > now_ts,
        "expires_in": max(0, expires_at - now_ts),
        "attempts_left": max(0, _ADMIN_PANEL_MAX_ATTEMPTS - attempts),
        "resend_in": max(0, _ADMIN_PANEL_RESEND_GAP_SECONDS - max(0, now_ts - last_sent)) if last_sent else 0,
    }


def _sensitive_register_clear_state() -> None:
    for key in (
        "sreg_code_hash",
        "sreg_code_expires_at",
        "sreg_attempts",
        "sreg_phone",
        "sreg_last_sent_at",
    ):
        session.pop(key, None)
    session.modified = True


def _sensitive_register_requires_bot_code(phone_norm: str) -> bool:
    return bool(_admin_panel_target(phone_norm))


def _sensitive_register_issue_code_via(phone_norm: str, force: bool, code_generator, code_sender) -> tuple[bool, str]:
    """منطق مشترک صدور کد ثبت‌نام حساس؛ تزریق‌پذیر جهت re-export در giso.app."""
    phone_norm = normalize_phone(phone_norm)
    target = _admin_panel_target(phone_norm)
    if not target:
        return False, "این شماره نیاز به تأیید رباتی ندارد."
    if not target.get("bale_id"):
        return False, "برای این شماره شناسه رباتی ثبت نشده؛ اول در ربات /start بزن و شماره را ثبت کن."
    now_ts = int(time.time())
    try:
        last_sent = int(session.get("sreg_last_sent_at") or 0)
    except (TypeError, ValueError):
        last_sent = 0
    if not force and last_sent and (now_ts - last_sent) < _SENSITIVE_REGISTER_RESEND_GAP_SECONDS:
        wait_left = _SENSITIVE_REGISTER_RESEND_GAP_SECONDS - (now_ts - last_sent)
        return False, f"کد قبلاً ارسال شده؛ لطفاً {wait_left} ثانیه دیگر دوباره تلاش کن."
    code = code_generator()
    ok, _ = code_sender(target["bale_id"], code, phone_norm)
    if not ok:
        return False, "ارسال کد تأیید به ربات این شماره ناموفق بود."
    session["sreg_code_hash"] = _admin_panel_hash_code(phone_norm, code)
    session["sreg_code_expires_at"] = now_ts + _SENSITIVE_REGISTER_CODE_TTL_SECONDS
    session["sreg_attempts"] = 0
    session["sreg_phone"] = phone_norm
    session["sreg_last_sent_at"] = now_ts
    session.modified = True
    return True, "برای تکمیل ثبت‌نام این شماره، کد تأیید به ربات متصل ارسال شد."


def _sensitive_register_issue_code(phone_norm: str, force: bool = False) -> tuple[bool, str]:
    return _sensitive_register_issue_code_via(
        phone_norm, force, _generate_admin_panel_code, _send_admin_panel_code_to_bot,
    )


def _sensitive_register_verify_code(phone_norm: str, code: str) -> tuple[bool, str]:
    phone_norm = normalize_phone(phone_norm)
    code = str(code or "").strip()
    if not phone_norm or not code:
        return False, "کد تأیید را کامل وارد کن."
    pending_phone = normalize_phone(session.get("sreg_phone", "") or "")
    if pending_phone != phone_norm:
        return False, "درخواست ثبت‌نام حساس معتبر نیست. دوباره از اول اقدام کن."
    try:
        expires_at = int(session.get("sreg_code_expires_at") or 0)
        attempts = int(session.get("sreg_attempts") or 0)
    except (TypeError, ValueError):
        expires_at = 0
        attempts = 0
    now_ts = int(time.time())
    if not expires_at or expires_at <= now_ts:
        return False, "زمان اعتبار کد تمام شده است. کد جدید بگیر."
    if attempts >= _SENSITIVE_REGISTER_MAX_ATTEMPTS:
        return False, "تعداد تلاش مجاز تمام شده است. کد جدید بگیر."
    session["sreg_attempts"] = attempts + 1
    session.modified = True
    expected_hash = session.get("sreg_code_hash", "") or ""
    if expected_hash != _admin_panel_hash_code(phone_norm, code):
        return False, "کد واردشده صحیح نیست."
    _sensitive_register_clear_state()
    return True, "تأیید رباتی ثبت‌نام انجام شد."


def render_register_view(phone: str = "", security_question: str = "",
                         require_bot_code: bool = False, info_message: str = "",
                         referral_code: str = "", referral_hint: str = ""):
    """رندر قالب ثبت‌نام (با حالت گام تأیید حساس) — از giso/app.py منتقل شد."""
    from flask import render_template
    status = _sensitive_register_status(phone) if phone else {
        "pending": False, "expires_in": 0, "attempts_left": _SENSITIVE_REGISTER_MAX_ATTEMPTS,
        "resend_in": 0,
    }
    return render_template(
        "register.html",
        phone=phone,
        security_question=security_question,
        require_bot_code=require_bot_code,
        info_message=info_message,
        referral_code=referral_code,
        referral_hint=referral_hint,
        code_pending=bool(status.get("pending")),
        expires_in=int(status.get("expires_in") or 0),
        attempts_left=int(status.get("attempts_left") or 0),
        resend_in=int(status.get("resend_in") or 0),
    )


def _sensitive_register_status(phone_norm: str) -> dict:
    phone_norm = normalize_phone(phone_norm)
    now_ts = int(time.time())
    pending_phone = normalize_phone(session.get("sreg_phone", "") or "")
    try:
        expires_at = int(session.get("sreg_code_expires_at") or 0)
        attempts = int(session.get("sreg_attempts") or 0)
        last_sent = int(session.get("sreg_last_sent_at") or 0)
    except (TypeError, ValueError):
        expires_at = attempts = last_sent = 0
    return {
        "pending": pending_phone == phone_norm and expires_at > now_ts,
        "expires_in": max(0, expires_at - now_ts),
        "attempts_left": max(0, _SENSITIVE_REGISTER_MAX_ATTEMPTS - attempts),
        "resend_in": max(0, _SENSITIVE_REGISTER_RESEND_GAP_SECONDS - max(0, now_ts - last_sent)) if last_sent else 0,
    }


