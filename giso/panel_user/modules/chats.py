# -*- coding: utf-8 -*-
"""Normal-user consultation messages and support tickets."""
from datetime import datetime

from flask_login import current_user

from giso.base import get_giso_db_conn
from giso.panel_user.modules._base import get_chats_count


def _ensure_support_tickets_table(conn):
    conn.execute(
        """CREATE TABLE IF NOT EXISTS giso_support_tickets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_bale_id TEXT,
            user_name TEXT,
            phone TEXT,
            message TEXT NOT NULL,
            status TEXT DEFAULT 'new',
            admin_reply TEXT DEFAULT '',
            admin_bale_id TEXT DEFAULT '',
            created_at TEXT,
            replied_at TEXT DEFAULT ''
        )"""
    )


def _support_tickets(phone):
    if not phone:
        return []
    try:
        with get_giso_db_conn() as conn:
            _ensure_support_tickets_table(conn)
            rows = conn.execute(
                "SELECT * FROM giso_support_tickets WHERE phone=? ORDER BY id DESC LIMIT 50",
                (phone,),
            ).fetchall()
            return [dict(row) for row in rows]
    except Exception:
        return []


def create_support_ticket(message: str):
    message = (message or "").strip()
    if len(message) < 5:
        return False, "لطفاً پیام خود را کامل‌تر بنویسید."
    phone = getattr(current_user, "phone", "") or ""
    name = (getattr(current_user, "name", "") or getattr(current_user, "first_name", "") or "کاربر")[:150]
    ticket_id = 0
    try:
        with get_giso_db_conn() as conn:
            _ensure_support_tickets_table(conn)
            bale = conn.execute(
                "SELECT bale_id FROM giso_users WHERE phone=? LIMIT 1", (phone,)
            ).fetchone()
            cur = conn.execute(
                "INSERT INTO giso_support_tickets "
                "(user_bale_id, user_name, phone, message, status, created_at) VALUES (?,?,?,?,?,?)",
                (str(bale[0]) if bale and bale[0] else "", name, phone, message[:2000], "new",
                 datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
            )
            conn.commit()
            ticket_id = int(cur.lastrowid or 0)
        # مرکز اعلان: تیکت جدید پشتیبانی (همان مسیر ربات — زنگوله پنل + بله طبق تنظیمات دسته)
        if ticket_id:
            try:
                from giso.panel.modules.notifications import safe_log
                safe_log("bot", "ticket", "تیکت جدید پشتیبانی",
                         f"تیکت #{ticket_id} — کاربر {name} ({phone or 'بدون شماره'}): {message[:200]}",
                         source_type="support_ticket_new", source_id=ticket_id)
            except Exception:
                pass
        return True, "پیام پشتیبانی شما ثبت شد."
    except Exception:
        return False, "ثبت پیام پشتیبانی انجام نشد؛ دوباره تلاش کنید."


def create_bug_report(title: str, details: str, page_path: str = ""):
    from giso.bug_reports import submit
    return submit(int(current_user.id), getattr(current_user, "phone", "") or "",
                  title, details, page_path)


def context():
    phone = getattr(current_user, "phone", "") or ""
    try:
        from giso.bug_reports import list_user_reports
        bugs = list_user_reports(int(current_user.id))
    except Exception:
        bugs = []
    return {
        "chats_count": get_chats_count(),
        "support_tickets": _support_tickets(phone),
        "bug_reports": bugs,
    }
