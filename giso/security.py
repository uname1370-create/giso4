# -*- coding: utf-8 -*-
"""لایه امنیتی مشترک Giso: CSRF سبک، rate-limit و audit log.

این ماژول به منطق کسب‌وکار وابسته نیست و برای حفظ route/sessionهای قبلی افزایشی است.
"""
import hashlib
import hmac
import logging
import secrets
import threading
import time
from collections import defaultdict, deque
from datetime import datetime

try:
    from flask import abort, current_app, request, session
except ImportError:  # اجازه می‌دهد ابزارهای static/test بدون Flask هم import شوند
    class _RequestFallback:
        method = "GET"
        path = ""
        is_json = False
        form = {}
        headers = {}
        remote_addr = ""
    request = _RequestFallback()
    session = {}
    current_app = None
    def abort(code, description=""):
        raise RuntimeError(description or "HTTP %s" % code)

from giso.base import get_giso_db_conn, _fa_num

logger = logging.getLogger("giso_security")

_TOKEN_KEY = "giso_csrf_token"
_rate_lock = threading.Lock()
_rate_hits = defaultdict(deque)

# ═══ محافظت سه‌مرحله‌ای ورود از brute-force (بر پایه‌ی شماره‌ی تلفن) ═══
# ۳ تلاش ناموفق -> قفل ۵ دقیقه | ۶ تلاش -> قفل ۱۰ دقیقه | ۱۰ تلاش -> قفل ۱ ساعت
LOGIN_LOCKOUT_TIERS = ((3, 300), (6, 600), (10, 3600))
_login_fail_lock = threading.Lock()
_login_fail_state = {}  # phone -> {"count": int, "locked_until": float}


def _login_state_get(phone):
    with _login_fail_lock:
        st = _login_fail_state.get(phone)
        if not st:
            return None
        if st.get("locked_until", 0) and st["locked_until"] <= time.monotonic():
            # قفل گذشته: شمارنده صفر می‌شود (پنجره‌ی جدید)
            _login_fail_state.pop(phone, None)
            return None
        return dict(st)


def login_lock_status(phone: str) -> dict:
    """وضعیت فعلی قفل: locked/remaining(ثانیه)/count."""
    st = _login_state_get(phone)
    if not st:
        return {"locked": False, "remaining": 0, "count": 0}
    remaining = max(0, int(st["locked_until"] - time.monotonic()) + 1) if st.get("locked_until") else 0
    return {"locked": bool(st.get("locked_until")), "remaining": remaining, "count": st.get("count", 0)}


def login_failed(phone: str) -> dict:
    """ثبت یک تلاش ناموفق؛ در صورت رسیدن به آستانه، قفل را فعال/شدت‌تر می‌کند."""
    now = time.monotonic()
    with _login_fail_lock:
        st = _login_fail_state.get(phone) or {"count": 0, "locked_until": 0}
        if st.get("locked_until", 0) and st["locked_until"] <= now:
            st = {"count": 0, "locked_until": 0}
        st["count"] = int(st.get("count", 0)) + 1
        lock_secs = 0
        for threshold, secs in LOGIN_LOCKOUT_TIERS:
            if st["count"] >= threshold:
                lock_secs = secs
        if lock_secs:
            st["locked_until"] = now + lock_secs
            if st["count"] >= LOGIN_LOCKOUT_TIERS[-1][0]:
                # پس از قفل ۱ ساعت، شمارنده صفر می‌شود تا قفل دائمی نسازد
                st = {"count": 0, "locked_until": now + lock_secs}
            _login_fail_state[phone] = st
            return {"locked": True, "remaining": lock_secs, "count": st["count"]}
        _login_fail_state[phone] = st
        return {
            "locked": False,
            "remaining": 0,
            "count": st["count"],
            "remaining_attempts": max(0, LOGIN_LOCKOUT_TIERS[0][0] - st["count"]),
        }


def login_succeeded(phone: str) -> None:
    """پس از ورود موفق، شمارنده‌ی شکست‌ها پاک می‌شود."""
    with _login_fail_lock:
        _login_fail_state.pop(phone, None)


def login_lockout_message(remaining_secs: int) -> str:
    """پیام فارسی صریح برای کاربر قفل‌شده (با نمایش مدت دقیق مسدودی)."""
    remaining_secs = int(max(0, remaining_secs))
    if remaining_secs >= 3600:
        return "⛔ به دلیل تلاش‌های مکرر ناموفق، ورود برای ۱ ساعت مسدود شده است. لطفاً یک ساعت دیگر تلاش کنید."
    minutes = (remaining_secs + 59) // 60
    return f"⛔ به دلیل تلاش‌های مکرر ناموفق، ورود برای {_fa_num(minutes)} دقیقه دیگر مسدود است. لطفاً صبر کنید و دوباره تلاش کنید."


def login_failed_message(result: dict) -> str:
    """پیام فارسی بعد از یک تلاش ناموفق (تلاش‌های باقی‌مانده تا قفل ۵ دقیقه‌ای)."""
    if result.get("locked"):
        return login_lockout_message(result.get("remaining", 0))
    left = result.get("remaining_attempts", 0)
    if left > 0:
        return f"شماره یا رمز اشتباه است. {_fa_num(left)} تلاش تا قفل موقت ۵ دقیقه‌ای."
    return "شماره یا رمز اشتباه است."


def password_strength(password: str) -> str:
    """weak | medium | strong — فقط برای نمایش؛ پذیرش جدا در validate_new_password."""
    pw = str(password or "")
    n = len(pw)
    has_letter = any(c.isalpha() for c in pw)
    has_digit = any(c.isdigit() for c in pw)
    has_upper = any(c.isupper() for c in pw)
    has_lower = any(c.islower() for c in pw)
    has_special = any(not c.isalnum() for c in pw)
    if n > 8 and has_upper and has_lower and has_digit and has_special:
        return "strong"
    if has_letter and has_digit and n >= 6:
        return "medium"
    return "weak"


def validate_new_password(password: str):
    """سیاست ساخت/تغییر رمز: حداقل ۶ + حرف + عدد. ورود کاربران فعلی را محدود نمی‌کند."""
    pw = str(password or "")
    if len(pw) < 6:
        return False, "رمز عبور باید حداقل ۶ کاراکتر باشد."
    if not any(c.isalpha() for c in pw) or not any(c.isdigit() for c in pw):
        return False, "رمز باید ترکیبی از حروف و عدد باشد."
    return True, ""


def csrf_token():
    """توکن پایدار در session فعلی؛ کلیدهای session قبلی دست‌نخورده می‌مانند."""
    token = session.get(_TOKEN_KEY)
    if not token:
        token = secrets.token_urlsafe(32)
        session[_TOKEN_KEY] = token
        session.modified = True
    return token


def csrf_input():
    return '<input type="hidden" name="csrf_token" value="%s">' % csrf_token()


def validate_csrf():
    supplied = (
        request.form.get("csrf_token", "")
        or request.headers.get("X-GISO-CSRF", "")
        or request.headers.get("X-CSRF-Token", "")
    )
    expected = session.get(_TOKEN_KEY, "")
    return bool(expected and supplied and hmac.compare_digest(str(expected), str(supplied)))


def csrf_failure():
    # برای API پاسخ JSON، برای فرم رفتار flash/redirect نمی‌سازیم تا routeها نشکنند.
    if request.is_json or request.path.startswith("/api/"):
        abort(400, description="CSRF token missing or invalid")
    abort(400, description="درخواست امنیتی نامعتبر است؛ صفحه را تازه‌سازی کنید.")


def client_key():
    forwarded = request.headers.get("X-Forwarded-For", "").split(",")[0].strip()
    return forwarded or request.remote_addr or "unknown"


def rate_limit(bucket, limit, window_seconds, identifier=None):
    """rate-limit in-process؛ برای multi-worker باید بعداً به Redis منتقل شود."""
    key = (bucket, str(identifier or client_key()))
    now = time.monotonic()
    with _rate_lock:
        q = _rate_hits[key]
        while q and now - q[0] >= window_seconds:
            q.popleft()
        if len(q) >= limit:
            retry = max(1, int(window_seconds - (now - q[0])))
            return False, retry
        q.append(now)
    return True, 0


def ensure_security_tables():
    with get_giso_db_conn() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS giso_audit_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                actor_phone TEXT DEFAULT '', actor_bale_id TEXT DEFAULT '',
                actor_role TEXT DEFAULT '', action TEXT NOT NULL DEFAULT '',
                target TEXT DEFAULT '', method TEXT DEFAULT '', path TEXT DEFAULT '',
                outcome TEXT DEFAULT '', details TEXT DEFAULT '', ip_address TEXT DEFAULT '',
                user_agent TEXT DEFAULT '', created_at TEXT DEFAULT ''
            )
        """)
        audit_cols = {r[1] for r in conn.execute("PRAGMA table_info(giso_audit_log)").fetchall()}
        if "ip_address" not in audit_cols:
            conn.execute("ALTER TABLE giso_audit_log ADD COLUMN ip_address TEXT DEFAULT ''")
        if "user_agent" not in audit_cols:
            conn.execute("ALTER TABLE giso_audit_log ADD COLUMN user_agent TEXT DEFAULT ''")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_audit_created ON giso_audit_log(created_at)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_audit_action ON giso_audit_log(action)")
        conn.execute("""
            CREATE TABLE IF NOT EXISTS giso_notification_deliveries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                notification_id INTEGER DEFAULT 0, destination TEXT DEFAULT 'bale',
                recipient_id TEXT DEFAULT '', status TEXT DEFAULT 'queued',
                http_status INTEGER DEFAULT 0, error_code TEXT DEFAULT '',
                error_message TEXT DEFAULT '', sent_at TEXT DEFAULT ''
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_delivery_notif ON giso_notification_deliveries(notification_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_delivery_status ON giso_notification_deliveries(status)")
        conn.commit()


def audit_event(action, outcome="success", target="", details="", actor=None):
    try:
        ensure_security_tables()
        user = actor
        if user is None:
            try:
                from flask_login import current_user
                user = current_user if getattr(current_user, "is_authenticated", False) else None
            except Exception:
                user = None
        phone = getattr(user, "phone", "") if user else ""
        role = ""
        try:
            from giso.config import is_super_admin
            role = "super" if is_super_admin(phone=phone) else ("authenticated" if phone else "guest")
        except Exception:
            role = "authenticated" if phone else "guest"
        with get_giso_db_conn() as conn:
            conn.execute(
                "INSERT INTO giso_audit_log "
                "(actor_phone, actor_bale_id, actor_role, action, target, method, path, outcome, details, ip_address, user_agent, created_at) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                (str(phone or ""), "", role, str(action)[:100], str(target)[:200],
                 request.method if request else "", request.path if request else "",
                 str(outcome)[:30], str(details)[:500],
                 (request.remote_addr if request else ""),
                 (request.headers.get("User-Agent", "")[:300] if request else ""),
                 datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
            )
            conn.commit()
    except Exception as exc:
        logger.warning("audit log failed for %s: %s", action, exc)


def record_delivery(notification_id, recipient_id, status, http_status=0, error_code="", error_message=""):
    try:
        ensure_security_tables()
        with get_giso_db_conn() as conn:
            conn.execute(
                "INSERT INTO giso_notification_deliveries "
                "(notification_id,destination,recipient_id,status,http_status,error_code,error_message,sent_at) "
                "VALUES (?,?,?,?,?,?,?,?)",
                (int(notification_id or 0), "bale", str(recipient_id), str(status), int(http_status or 0),
                 str(error_code or "")[:80], str(error_message or "")[:300],
                 datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
            )
            conn.commit()
    except Exception as exc:
        logger.warning("delivery log failed: %s", exc)


def security_startup_warnings(app, step_up_ttl_seconds=1800):
    """هشدارهای امنیتی startup؛ هیچ secret یا TTL را خودکار تغییر نمی‌دهد."""
    secret = str(app.config.get("SECRET_KEY") or "")
    weak_defaults = {"giso-default-secret-key-change", "secret", "changeme", "dev"}
    if secret in weak_defaults or len(secret) < 32:
        logger.warning("SECURITY: SECRET_KEY is missing/default/short; set a random value of at least 32 characters.")
    ttl = step_up_ttl_seconds
    if ttl is None or ttl <= 0:
        logger.warning("SECURITY: step-up verification TTL is unlimited or invalid; use a finite TTL.")
    elif ttl > 1800:
        logger.warning("SECURITY: step-up verification TTL is %s seconds; recommended maximum is 1800 seconds.", ttl)
    if str(app.config.get("SESSION_COOKIE_SAMESITE", "")).lower() != "lax":
        logger.warning("SECURITY: SESSION_COOKIE_SAMESITE is not Lax.")
    if not app.config.get("SESSION_COOKIE_HTTPONLY", False):
        logger.warning("SECURITY: SESSION_COOKIE_HTTPONLY is disabled.")
    if str(app.config.get("FLASK_ENV", "")).lower() == "production" and not app.config.get("SESSION_COOKIE_SECURE", False):
        logger.warning("SECURITY: production session cookie is not Secure; HTTPS is required.")
    try:
        import redis  # optional; no dependency is added in this phase
        logger.info("SECURITY: Redis client is available; rate-limit migration can be planned.")
    except Exception:
        logger.info("SECURITY: Redis is not available; keeping in-process rate limiting for now.")


def install_security(app):
    @app.context_processor
    def inject_security_helpers():
        return {"csrf_token": csrf_token, "csrf_input": csrf_input}

    @app.before_request
    def security_gate():
        if request.method != "POST":
            return None
        path = request.path or ""
        # widget توکن اختصاصی خودش را دارد و ربات/کانال خارج از Flask هستند.
        if path.startswith("/api/ai-widget/"):
            return None
        if not validate_csrf():
            csrf_failure()

        rules = {
            "/login": (10, 300, "login"),
            "/register": (5, 600, "register"),
            "/forgot-password": (5, 600, "forgot_password"),
            "/admin/verify": (8, 300, "otp"),
            "/analysis/validate-image": (20, 300, "validate_image"),
            "/api/consultant-chat/message": (30, 300, "consultant_chat"),
            "/api/consultant-chat/rate": (20, 300, "consultant_rate"),
        }
        rule = rules.get(path)
        if path.startswith("/shop/cart/add/"):
            rule = (30, 60, "cart_add")
        if path == "/dashboard/wallet/topup":
            rule = (8, 3600, "wallet_topup")
        elif path == "/dashboard/wallet/withdraw":
            rule = (5, 3600, "wallet_withdrawal")
        # بازارچه: در کنار سقف روزانه دامنه، burst پیشنهاد و پیام نیز مهار می‌شود.
        if path.startswith("/marketplace/"):
            if path.endswith("/offer"):
                rule = (12, 300, "marketplace_offer")
            elif path.endswith("/chat"):
                rule = (60, 300, "marketplace_chat")
        if rule:
            ok, retry = rate_limit(rule[2], rule[0], rule[1])
            if not ok:
                from flask import jsonify
                if request.is_json or path.startswith("/api/"):
                    return jsonify({"ok": False, "error": "rate_limited", "retry_after": retry}), 429
                abort(429, description="تعداد درخواست‌ها زیاد است؛ کمی بعد دوباره تلاش کنید.")
        return None

    if hasattr(app, "after_request"):
        @app.after_request
        def security_headers(response):
            response.headers.setdefault("X-Content-Type-Options", "nosniff")
            response.headers.setdefault("X-Frame-Options", "SAMEORIGIN")
            response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
            response.headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
            response.headers.setdefault(
                "Content-Security-Policy",
                "default-src 'self'; img-src 'self' data: https:; "
                "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com https://cdnjs.cloudflare.com; "
                "font-src 'self' https://fonts.gstatic.com https://cdnjs.cloudflare.com data:; "
                "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net https://cdnjs.cloudflare.com; "
                "connect-src 'self' https:; frame-ancestors 'self';"
            )
            if str(app.config.get("FLASK_ENV", "")).lower() == "production":
                response.headers.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
            return response

        @app.after_request
        def security_audit_response(response):
            try:
                if request.method == "POST":
                    path = request.path or ""
                    sensitive = (
                        "/admin/" in path or path.startswith("/dashboard/wallet/")
                        or path.startswith("/shop/order-time") or path.startswith("/shop/cart/checkout")
                        or path.startswith("/shop/cart/add/") or path.startswith("/admin/config/publish-mode")
                    )
                    if sensitive:
                        action = path.strip("/").replace("/", ".") or "post"
                        audit_event(action, "success" if response.status_code < 400 else "failed",
                                    target=path, details="HTTP %s" % response.status_code)
            except Exception:
                pass
            return response

    return app


__all__ = ["csrf_token", "csrf_input", "validate_csrf", "install_security", "audit_event", "record_delivery", "ensure_security_tables", "rate_limit", "password_strength", "validate_new_password"]
