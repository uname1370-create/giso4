# -*- coding: utf-8 -*-
"""Manual bug-bounty workflow; submission never pays automatically."""
import hashlib
import logging
import re
from datetime import datetime

from giso.base import get_giso_db_conn

logger = logging.getLogger("giso_bug_reports")


def _ensure_reward_mission(conn=None):
    """تضمین وجود مأموریت پاداش گزارش باگ (idempotent، مستقل از مجوز فلَسک).

    مأموریت‌های پاداشی باید از قبل وجود داشته باشند تا complete_mission پاداش بدهد؛
    اما گزارش باگ فقط با تأیید دستی سوپرادمین پاداش می‌گیرد، پس این صرفاً ساخت
    سطر تعریف مأموریت است (هیچ پرداختی در این مرحله رخ نمی‌دهد).
    """
    own = conn is None
    if own:
        conn = get_giso_db_conn()
    try:
        conn.execute(
            "INSERT INTO wallet_missions "
            "(code,title,description,reward_amount,reward_scope,"
            "is_active,is_deleted,sort_order,created_at,updated_at) "
            "SELECT 'bug_report_approved','گزارش باگ تأییدشده',"
            "'پاداش گزارش باگ معتبرِ تأییدشده توسط سوپرادمین.',150,'spend',"
            "1,0,150,datetime('now','localtime'),datetime('now','localtime') "
            "WHERE NOT EXISTS (SELECT 1 FROM wallet_missions WHERE code='bug_report_approved')"
        )
        if own:
            conn.commit()
    except Exception as exc:
        logger.warning("ensure bug-report mission: %s", exc)
        if own:
            try:
                conn.rollback()
            except Exception:
                pass
    finally:
        if own:
            try:
                conn.close()
            except Exception:
                pass

SCHEMA = """
CREATE TABLE IF NOT EXISTS giso_bug_reports(
 id INTEGER PRIMARY KEY AUTOINCREMENT,user_id INTEGER NOT NULL,phone TEXT DEFAULT '',
 title TEXT NOT NULL,details TEXT NOT NULL,page_path TEXT DEFAULT '',fingerprint TEXT NOT NULL,
 status TEXT NOT NULL DEFAULT 'pending',duplicate_of INTEGER DEFAULT 0,admin_note TEXT DEFAULT '',
 reviewed_by TEXT DEFAULT '',reward_amount INTEGER DEFAULT 0,reward_transaction_id INTEGER DEFAULT 0,
 created_at TEXT NOT NULL,reviewed_at TEXT DEFAULT '');
CREATE INDEX IF NOT EXISTS idx_bug_reports_status ON giso_bug_reports(status,created_at);
CREATE INDEX IF NOT EXISTS idx_bug_reports_fingerprint ON giso_bug_reports(fingerprint);
"""


def _clean(value, limit):
    return " ".join(str(value or "").replace("\x00", " ").split())[:limit].strip()


def _fingerprint(title, details, page_path):
    normalized = re.sub(r"\d+", "#", f"{title}|{details[:300]}|{page_path}".lower())
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def submit(user_id, phone, title, details, page_path=""):
    title = _clean(title, 160); details = _clean(details, 3000)
    page_path = _clean(page_path, 300)
    if len(title) < 5 or len(details) < 20:
        return False, "عنوان و توضیح کامل‌تری برای بازتولید مشکل بنویسید.", 0
    if page_path and (not page_path.startswith("/") or "://" in page_path):
        return False, "مسیر صفحه باید یک مسیر داخلی مانند /shop باشد.", 0
    fp = _fingerprint(title, details, page_path)
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with get_giso_db_conn() as conn:
        conn.executescript(SCHEMA)
        duplicate = conn.execute(
            "SELECT id FROM giso_bug_reports WHERE fingerprint=? AND status IN ('pending','approved') ORDER BY id LIMIT 1",
            (fp,)).fetchone()
        # Similarity is only a review hint; automation must never make the final
        # reward decision or suppress a potentially valid report.
        status = "pending"
        cur = conn.execute(
            "INSERT INTO giso_bug_reports(user_id,phone,title,details,page_path,fingerprint,status,duplicate_of,created_at) "
            "VALUES(?,?,?,?,?,?,?,?,?)", (int(user_id), str(phone or "")[:30], title, details,
            page_path, fp, status, int(duplicate["id"]) if duplicate else 0, now))
        conn.commit(); report_id = int(cur.lastrowid)
    try:
        from giso.panel.modules.notifications import safe_log
        safe_log("security", "bug_report", "گزارش باگ جدید",
                 f"گزارش #{report_id}: {title}" + (" (تکراری)" if duplicate else ""),
                 source_type="bug_report", source_id=report_id)
    except Exception:
        pass
    message = ("گزارش ثبت شد و به‌عنوان مشابه گزارش قبلی برای تصمیم دستی سوپرادمین علامت خورد."
               if duplicate else "گزارش ثبت شد و پس از بررسی دستی سوپرادمین نتیجه اعلام می‌شود.")
    return True, message, report_id


def list_reports(limit=200):
    with get_giso_db_conn() as conn:
        conn.executescript(SCHEMA)
        return [dict(r) for r in conn.execute(
            "SELECT * FROM giso_bug_reports ORDER BY CASE status WHEN 'pending' THEN 0 ELSE 1 END,id DESC LIMIT ?",
            (max(1, min(500, int(limit))),)).fetchall()]


def list_user_reports(user_id, limit=30):
    with get_giso_db_conn() as conn:
        conn.executescript(SCHEMA)
        return [dict(r) for r in conn.execute(
            "SELECT id,title,page_path,status,duplicate_of,reward_amount,created_at,reviewed_at,admin_note "
            "FROM giso_bug_reports WHERE user_id=? ORDER BY id DESC LIMIT ?",
            (int(user_id), max(1, min(100, int(limit))))).fetchall()]


def review(report_id, decision, admin_id, note=""):
    """Claim once, then award through wallet's idempotent Spend transaction."""
    if decision not in {"approved", "rejected", "duplicate"}:
        return False, "تصمیم نامعتبر است."
    with get_giso_db_conn() as conn:
        conn.executescript(SCHEMA); conn.execute("BEGIN IMMEDIATE")
        row = conn.execute("SELECT * FROM giso_bug_reports WHERE id=?", (int(report_id),)).fetchone()
        if not row:
            conn.rollback(); return False, "گزارش پیدا نشد."
        if row["status"] != "pending":
            conn.rollback(); return False, "این گزارش قبلاً بررسی شده است."
        conn.execute("UPDATE giso_bug_reports SET status=?,admin_note=?,reviewed_by=?,reviewed_at=datetime('now','localtime') WHERE id=? AND status='pending'",
                     (decision, _clean(note, 500), str(admin_id)[:80], int(report_id)))
        conn.commit()
    if decision == "approved":
        # اطمینان از وجود مأموریت پاداش گزارش باگ (ممکن است ادمین آن را دستی نساخته باشد).
        try:
            _ensure_reward_mission()
        except Exception as _seed_ex:
            logger.warning("bug report mission seed: %s", _seed_ex)
        from giso.wallet import complete_mission
        ok, message = complete_mission(int(row["user_id"]), "bug_report_approved", event_key=f"bug:{report_id}")
        # Capture the immutable actual transaction amount for the report view.
        with get_giso_db_conn() as conn:
            tx = conn.execute("SELECT id,amount FROM wallet_transactions WHERE idempotency_key=(SELECT 'mission:'||mission_id||':user:'||user_id FROM wallet_mission_completions WHERE event_key=? LIMIT 1)",
                              (f"bug:{report_id}",)).fetchone()
            if tx:
                conn.execute("UPDATE giso_bug_reports SET reward_amount=?,reward_transaction_id=? WHERE id=?",
                             (int(tx["amount"] or 0), int(tx["id"]), int(report_id))); conn.commit()
        if not ok:
            with get_giso_db_conn() as conn:
                conn.execute("UPDATE giso_bug_reports SET status='pending',reviewed_at='',reviewed_by='' WHERE id=? AND reward_transaction_id=0", (int(report_id),)); conn.commit()
            return False, "تأیید نهایی نشد؛ مأموریت پاداش فعال نیست و گزارشی پرداخت‌نشده باقی نماند."
        return True, message
    return True, "نتیجه بررسی ثبت شد؛ پاداشی پرداخت نشد."
