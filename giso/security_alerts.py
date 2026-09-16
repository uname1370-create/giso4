# -*- coding: utf-8 -*-
"""Durable, privacy-safe notifications for suspicious login events."""
import logging
from concurrent.futures import ThreadPoolExecutor

from giso.base import get_giso_db_conn, normalize_phone, to_shamsi

logger = logging.getLogger(__name__)
_POOL = ThreadPoolExecutor(max_workers=2, thread_name_prefix="giso_security_alert")


def _claim(event_id: int) -> bool:
    """Idempotently claim an event before any site/Bale delivery is attempted."""
    try:
        with get_giso_db_conn() as conn:
            conn.execute("""CREATE TABLE IF NOT EXISTS giso_security_alerts(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                login_event_id INTEGER NOT NULL UNIQUE,
                created_at TEXT DEFAULT '', user_notified INTEGER DEFAULT 0,
                admin_notified INTEGER DEFAULT 0)""")
            cur = conn.execute(
                "INSERT INTO giso_security_alerts(login_event_id,created_at) "
                "VALUES(?,datetime('now','localtime')) ON CONFLICT DO NOTHING", (int(event_id),))
            conn.commit()
            return cur.rowcount == 1
    except Exception as exc:
        logger.warning("security alert claim failed: %s", exc)
        return False


def _mark(event_id, column):
    if column not in {"user_notified", "admin_notified"}:
        return
    try:
        with get_giso_db_conn() as conn:
            conn.execute(f"UPDATE giso_security_alerts SET {column}=1 WHERE login_event_id=?",
                         (int(event_id),))
            conn.commit()
    except Exception:
        pass


def _send_user_bale(phone: str, text: str):
    """Best-effort plain-text Bale alert; delivery outcome is recorded."""
    try:
        from giso.base import _token_from_env, _token_from_db, _http_post
        from giso.security import record_delivery
        with get_giso_db_conn() as conn:
            row = conn.execute(
                "SELECT bale_id FROM giso_users WHERE phone=? AND contact_shared=1 LIMIT 1",
                (normalize_phone(phone),)).fetchone()
        if not row or not str(row["bale_id"] or "").isdigit():
            return
        recipient = int(row["bale_id"])
        token = (_token_from_env() or _token_from_db() or "").strip()
        if not token:
            record_delivery(0, recipient, "failed", error_code="missing_token",
                            error_message="Bale token is not configured")
            return
        response = _http_post(f"https://tapi.bale.ai/bot{token}/sendMessage",
                              json_payload={"chat_id": recipient, "text": text[:4000]})
        code = int(getattr(response, "status_code", 0) or 0)
        ok = code in (200, 201, 202, 204)
        record_delivery(0, recipient, "sent" if ok else "failed", http_status=code,
                        error_code="" if ok else "http_error")
    except Exception as exc:
        logger.warning("user security Bale alert failed: %s", exc)


def notify_suspicious_login(event: dict) -> bool:
    """Create user + superadmin alerts once. Never includes raw IP/UA/hash."""
    event_id = int(event.get("id") or 0)
    if not event_id or not event.get("suspicious") or not _claim(event_id):
        return False
    phone = normalize_phone(event.get("phone") or "")
    success = bool(event.get("success"))
    device = str(event.get("device_label") or "دستگاه ناشناس")[:40]
    when = to_shamsi(event.get("created_at") or "") or str(event.get("created_at") or "")
    kind = "ورود موفق از دستگاه جدید" if success else "تلاش‌های ناموفق پیاپی برای ورود"
    user_text = (f"هشدار امنیتی گیسو\n{kind}\nدستگاه: {device}\nزمان: {when}\n"
                 "اگر این فعالیت متعلق به شما نیست، رمز عبور را فوراً تغییر دهید و با پشتیبانی تماس بگیرید.")
    try:
        if phone:
            from giso.panel.modules.notifications import log_user_notification
            log_user_notification(phone, "suspicious_login", "هشدار امنیتی ورود",
                                  user_text, source_type="login_security", source_id=event_id,
                                  category="security")
            _POOL.submit(_send_user_bale, phone, user_text)
            _mark(event_id, "user_notified")
    except Exception as exc:
        logger.warning("user security site alert failed: %s", exc)
    try:
        from giso.panel.modules.notifications import safe_log
        masked = (phone[:6] + "***" + phone[-2:]) if len(phone) > 9 else "کاربر ناشناس"
        safe_log("security", "suspicious_login", "هشدار ورود مشکوک",
                 f"{kind} برای {masked} · {device} · {when}",
                 source_type="login_security", source_id=event_id)
        _mark(event_id, "admin_notified")
    except Exception as exc:
        logger.warning("admin security alert failed: %s", exc)
    return True
