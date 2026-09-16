# -*- coding: utf-8 -*-
"""مرکز پیام و اعلان انبوه — لایه دامنه (جداول، مخاطبان، صف و گزارش).

مستقل از giso/broadcasts.py قدیمی؛ جداول اختصاصی giso_bc_*؛
کانال‌ها: اعلان داخل سایت (giso_notifications) + پوش بله (send_bot_push).
ارسال انبوه هرگز داخل HTTP request انجام نمی‌شود؛ worker پس‌زمینه صف را می‌کشد.
"""
import time
from datetime import datetime

from giso.base import get_giso_db_conn, normalize_phone, send_bot_push

AUDIENCES = ("all", "buyers", "sellers", "centers", "regular")
CHANNELS = ("site", "bale", "both")

SCHEMA = """
CREATE TABLE IF NOT EXISTS giso_bc_campaigns(
 id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT NOT NULL DEFAULT '',
 message TEXT NOT NULL DEFAULT '', audience TEXT NOT NULL DEFAULT 'all',
 channels TEXT NOT NULL DEFAULT 'site', status TEXT NOT NULL DEFAULT 'queued',
 scheduled_at TEXT NOT NULL DEFAULT '', created_by TEXT NOT NULL DEFAULT '',
 created_at TEXT NOT NULL DEFAULT '', finished_at TEXT NOT NULL DEFAULT '');
CREATE TABLE IF NOT EXISTS giso_bc_deliveries(
 id INTEGER PRIMARY KEY AUTOINCREMENT, campaign_id INTEGER NOT NULL,
 user_id INTEGER NOT NULL DEFAULT 0, phone TEXT NOT NULL DEFAULT '',
 bale_id TEXT NOT NULL DEFAULT '', site_status TEXT NOT NULL DEFAULT 'none',
 bale_status TEXT NOT NULL DEFAULT 'none', attempts INTEGER NOT NULL DEFAULT 0,
 last_error TEXT NOT NULL DEFAULT '');
CREATE INDEX IF NOT EXISTS idx_bc_deliv_campaign ON giso_bc_deliveries(campaign_id);
CREATE INDEX IF NOT EXISTS idx_bc_deliv_pending ON giso_bc_deliveries(site_status, bale_status);
"""
_SCHEMA_READY = False


def _now():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def ensure_tables(conn=None):
    global _SCHEMA_READY
    if _SCHEMA_READY and conn is None:
        return
    own = conn is None
    if own:
        conn = get_giso_db_conn()
    try:
        conn.executescript(SCHEMA)
        if own:
            conn.commit()
        _SCHEMA_READY = True
    finally:
        if own:
            conn.close()


def audience_users(conn, target):
    """فهرست مخاطبان گروه هدف — کوئسی قابل‌حمل، مستقل از ماژول قدیمی."""
    where = ""
    if target == "centers":
        where = "WHERE EXISTS(SELECT 1 FROM beauty_centers c WHERE c.owner_user_id=u.id)"
    elif target == "buyers":
        where = "WHERE EXISTS(SELECT 1 FROM buyer_profiles b WHERE b.user_id=u.id)"
    elif target == "sellers":
        where = ("WHERE EXISTS(SELECT 1 FROM hair_listings l WHERE l.seller_user_id=u.id"
                 " AND COALESCE(l.deleted_at,'')='')")
    elif target == "regular":
        where = ("WHERE NOT EXISTS(SELECT 1 FROM buyer_profiles b WHERE b.user_id=u.id)"
                 " AND NOT EXISTS(SELECT 1 FROM hair_listings l WHERE l.seller_user_id=u.id"
                 " AND COALESCE(l.deleted_at,'')='')"
                 " AND NOT EXISTS(SELECT 1 FROM beauty_centers c WHERE c.owner_user_id=u.id)")
    # جدول giso_users (کلید اصلی bale_id) را سایت/بات می‌سازد؛ ممکن است نباشد → resilient
    has_gu = conn.execute("SELECT name FROM sqlite_master WHERE type='table'"
                          " AND name='giso_users'").fetchone()
    bale_sel = ("(SELECT gu.bale_id FROM giso_users gu WHERE gu.phone=u.phone"
                " AND COALESCE(gu.bale_id,'')<>'' LIMIT 1)"
                if has_gu else "''")
    rows = conn.execute(
        "SELECT u.id,u.phone,%s bale_id FROM giso_web_auth u %s ORDER BY u.id"
        % (bale_sel, where)).fetchall()
    return [{"id": r[0], "phone": normalize_phone(r[1] or ""), "bale_id": str(r[2] or "")}
            for r in rows]


def create_campaign(title, message, audience, channels, mode="now",
                    scheduled_at="", actor=""):
    title = " ".join(str(title or "").split())[:160]
    message = str(message or "").strip()[:3000]
    if not title or not message:
        return False, "عنوان و متن پیام لازم است.", 0
    if audience not in AUDIENCES:
        return False, "گروه مخاطب نامعتبر است.", 0
    if channels not in CHANNELS:
        return False, "کانال ارسال نامعتبر است.", 0
    status = "queued"
    sched = ""
    if str(mode) == "schedule":
        sched = str(scheduled_at or "").strip()[:19]
        if len(sched) < 11:
            return False, "زمان‌بندی نامعتبر است.", 0
        status = "scheduled"
    with get_giso_db_conn() as conn:
        ensure_tables(conn)
        users = audience_users(conn, audience)
        cur = conn.execute(
            "INSERT INTO giso_bc_campaigns(title,message,audience,channels,status,"
            "scheduled_at,created_by,created_at) VALUES(?,?,?,?,?,?,?,?)",
            (title, message, audience, channels, status, sched, str(actor), _now()))
        cid = int(cur.lastrowid)
        for u in users:
            site = "pending" if channels in ("site", "both") else "none"
            bale = "pending" if channels in ("bale", "both") and u["bale_id"].isdigit() else "none"
            conn.execute(
                "INSERT INTO giso_bc_deliveries(campaign_id,user_id,phone,bale_id,"
                "site_status,bale_status) VALUES(?,?,?,?,?,?)",
                (cid, u["id"], u["phone"], u["bale_id"], site, bale))
        conn.commit()
    return True, "کمپین ثبت شد و در صف ارسال است.", cid


def _push_site_notification(conn, title, message, phone, cid):
    try:
        from giso.panel.modules.notifications import ensure_notifications_table
        ensure_notifications_table()
    except Exception:
        pass
    conn.execute(
        "INSERT INTO giso_notifications(category,subcategory,title,message,target_role,"
        "source_type,source_id,recipient_id,status,created_at) VALUES(?,?,?,?,?,?,?,?,?,?)",
        ("system", "admin_broadcast", "📣 %s" % title, message, "user",
         "broadcast", cid, phone, "unread", _now()))


def process_batch(limit=5):
    """یک批次 از صف: سایت فوری، بله با retry تا ۳ بار. خارج از HTTP request."""
    sent = 0
    with get_giso_db_conn() as conn:
        ensure_tables(conn)
        conn.execute("UPDATE giso_bc_campaigns SET status='queued' WHERE status='scheduled'"
                     " AND scheduled_at<>'' AND scheduled_at<=?", (_now(),))
        conn.execute("UPDATE giso_bc_deliveries SET site_status='pending' WHERE site_status='processing'")
        conn.execute("UPDATE giso_bc_deliveries SET bale_status='pending' WHERE bale_status='processing'")
        rows = conn.execute(
            "SELECT d.id,d.campaign_id,d.phone,d.bale_id,d.site_status,d.bale_status,"
            "d.attempts,c.title,c.message FROM giso_bc_deliveries d"
            " JOIN giso_bc_campaigns c ON c.id=d.campaign_id"
            " WHERE c.status='queued' AND (d.site_status='pending' OR d.bale_status='pending')"
            " ORDER BY d.id LIMIT ?", (max(1, min(10, int(limit))),)).fetchall()
        if rows:
            ids = ",".join("?" for _ in rows)
            conn.execute("UPDATE giso_bc_deliveries SET"
                         " site_status=CASE WHEN site_status='pending' THEN 'processing' ELSE site_status END,"
                         " bale_status=CASE WHEN bale_status='pending' THEN 'processing' ELSE bale_status END"
                         " WHERE id IN (%s)" % ids, tuple(r[0] for r in rows))
        conn.commit()
    for r in rows:
        err = ""
        with get_giso_db_conn() as conn:
            if r["site_status"] == "pending":
                try:
                    _push_site_notification(conn, r["title"], r["message"], r["phone"], r["campaign_id"])
                    conn.execute("UPDATE giso_bc_deliveries SET site_status='sent' WHERE id=?", (r["id"],))
                    sent += 1
                except Exception as exc:
                    conn.execute("UPDATE giso_bc_deliveries SET site_status='failed',last_error=? WHERE id=?",
                                 (type(exc).__name__[:80], r["id"]))
            if r["bale_status"] == "pending":
                ok = False
                try:
                    ok = bool(send_bot_push(int(r["bale_id"]),
                                            "📣 %s\n──────────\n%s" % (r["title"], r["message"])))
                except Exception as exc:
                    err = type(exc).__name__[:80]
                attempts = int(r["attempts"] or 0) + 1
                if ok:
                    conn.execute("UPDATE giso_bc_deliveries SET bale_status='sent',attempts=? WHERE id=?",
                                 (attempts, r["id"]))
                    sent += 1
                else:
                    st = "failed" if attempts >= 3 else "pending"
                    conn.execute("UPDATE giso_bc_deliveries SET bale_status=?,attempts=?,last_error=? WHERE id=?",
                                 (st, attempts, err, r["id"]))
            conn.execute("UPDATE giso_bc_campaigns SET status='completed',finished_at=?"
                         " WHERE id=? AND NOT EXISTS(SELECT 1 FROM giso_bc_deliveries d"
                         " WHERE d.campaign_id=? AND (d.site_status IN ('pending','processing')"
                         " OR d.bale_status IN ('pending','processing')))",
                         (_now(), r["campaign_id"], r["campaign_id"]))
            conn.commit()
        time.sleep(0.1)
    return sent


def campaign_list(limit=30):
    with get_giso_db_conn() as conn:
        ensure_tables(conn)
        rows = conn.execute(
            "SELECT c.id,c.title,c.audience,c.channels,c.status,c.scheduled_at,c.created_at,"
            " (SELECT COUNT(*) FROM giso_bc_deliveries d WHERE d.campaign_id=c.id) total,"
            " (SELECT COUNT(*) FROM giso_bc_deliveries d WHERE d.campaign_id=c.id"
            "  AND (d.site_status='sent' OR d.bale_status='sent')) ok,"
            " (SELECT COUNT(*) FROM giso_bc_deliveries d WHERE d.campaign_id=c.id"
            "  AND (d.site_status='failed' OR d.bale_status='failed')) failed,"
            " (SELECT COUNT(*) FROM giso_bc_deliveries d WHERE d.campaign_id=c.id"
            "  AND (d.site_status IN ('pending','processing') OR d.bale_status IN ('pending','processing')))"
            " pending, (SELECT COALESCE(NULLIF(d.last_error,''),'—') FROM giso_bc_deliveries d"
            "  WHERE d.campaign_id=c.id AND d.last_error<>'' ORDER BY d.id DESC LIMIT 1) last_error"
            " FROM giso_bc_campaigns c ORDER BY c.id DESC LIMIT ?", (int(limit),)).fetchall()
        return [dict(r) for r in rows]


def queue_size():
    try:
        with get_giso_db_conn() as conn:
            ensure_tables(conn)
            return conn.execute("SELECT COUNT(*) FROM giso_bc_deliveries WHERE"
                                " site_status IN ('pending','processing') OR"
                                " bale_status IN ('pending','processing')").fetchone()[0]
    except Exception:
        return 0
