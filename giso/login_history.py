import hashlib
from giso.base import get_giso_db_conn, to_shamsi

SCHEMA = """
CREATE TABLE IF NOT EXISTS giso_login_events(
 id INTEGER PRIMARY KEY,user_id INTEGER DEFAULT 0,phone TEXT DEFAULT '',success INTEGER,
 device_hash TEXT,device_label TEXT,ip_hash TEXT,suspicious INTEGER DEFAULT 0,
 reason TEXT DEFAULT '',created_at TEXT);
CREATE INDEX IF NOT EXISTS idx_login_events_user ON giso_login_events(user_id,created_at);
"""


def record(phone, user_id, success, request, reason=""):
    try:
        from giso.monitoring_settings import enabled
        if not enabled('login_history'):
            return None
    except Exception:
        pass
    ua = str(request.headers.get("User-Agent", ""))[:300]
    ip = str(request.remote_addr or "")
    device = hashlib.sha256(ua.encode()).hexdigest()
    iph = hashlib.sha256(ip.encode()).hexdigest()
    label = "موبایل" if "mobile" in ua.lower() else "رایانه"
    event = None
    with get_giso_db_conn() as conn:
        conn.executescript(SCHEMA)
        known = (conn.execute(
            "SELECT 1 FROM giso_login_events WHERE user_id=? AND device_hash=? AND success=1",
            (user_id, device)).fetchone() if user_id else None)
        prior_success = (conn.execute(
            "SELECT 1 FROM giso_login_events WHERE user_id=? AND success=1 LIMIT 1",
            (user_id,)).fetchone() if user_id else None)
        failed = conn.execute(
            "SELECT COUNT(*) FROM giso_login_events WHERE phone=? AND success=0 "
            "AND created_at>=datetime('now','localtime','-1 hour')", (phone,)).fetchone()[0]
        try:
            from giso.monitoring_settings import enabled
            detect = enabled('suspicious_login')
        except Exception:
            detect = True
        # The first successful login establishes the trusted baseline. Alert once on
        # the fifth failed attempt, rather than spamming on every later attempt.
        new_device = bool(success and user_id and prior_success and not known)
        failed_threshold = bool(not success and user_id and int(failed or 0) == 4)
        suspicious = int(bool(detect and (new_device or failed_threshold)))
        cur = conn.execute(
            "INSERT INTO giso_login_events(user_id,phone,success,device_hash,device_label,"
            "ip_hash,suspicious,reason,created_at) VALUES(?,?,?,?,?,?,?,?,datetime('now','localtime'))",
            (user_id, phone, int(success), device, label, iph, suspicious, str(reason)[:120]))
        conn.execute("DELETE FROM giso_login_events WHERE created_at<datetime('now','localtime','-30 days')")
        conn.commit()
        row = conn.execute("SELECT * FROM giso_login_events WHERE id=?", (cur.lastrowid,)).fetchone()
        event = dict(row) if row else None
    # Notification happens after commit so notification writers never contend with
    # the login transaction. Alert failures cannot block authentication.
    if event and event.get("suspicious"):
        try:
            from giso.security_alerts import notify_suspicious_login
            notify_suspicious_login(event)
        except Exception:
            pass
    return event


def recent(user_id=0, limit=200):
    try:
        from giso.monitoring_settings import enabled
        if not enabled('login_history'):
            return []
    except Exception:
        return []
    with get_giso_db_conn() as conn:
        conn.executescript(SCHEMA)
        rows = conn.execute(
            "SELECT * FROM giso_login_events " + ("WHERE user_id=? " if user_id else "") +
            "ORDER BY id DESC LIMIT ?", ((user_id, limit) if user_id else (limit,))).fetchall()
    out = []
    for row in rows:
        item = dict(row)
        item["date_fa"] = to_shamsi(item.get("created_at"))
        out.append(item)
    return out

def clear(user_id=0) -> bool:
    """پاک‌کردن تاریخچهٔ ورودهای یک کاربر (به‌درخواست خود کاربر از پنل)."""
    try:
        with get_giso_db_conn() as conn:
            conn.executescript(SCHEMA)
            conn.execute("DELETE FROM giso_login_events WHERE user_id=?", (int(user_id or 0),))
            conn.commit()
        return True
    except Exception:
        return False
