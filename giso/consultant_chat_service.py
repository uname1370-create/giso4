# -*- coding: utf-8 -*-
"""giso/consultant_chat_service.py — سرویس گفتگوی مشاور (پنل کاربر).

مورد ۶ img/help.md: دکمه‌های «تاریخچه گفتگو» و «پاک‌کردن لیست».
پاک‌کردن فقط نماِ کاربر را بایگانی می‌کند (cleared_by_user=1)؛
متن گفتگو در تاریخچه (و نمای ادمین) دست‌نخورده می‌ماند.
"""
import logging

from giso.base import get_giso_db_conn

logger = logging.getLogger("giso_consultant_chat_service")


def ensure_thread_schema() -> None:
    """ستون افزایشی بایگانی نماِ کاربر (بدون تغییر رفتار قدیمی)."""
    try:
        with get_giso_db_conn() as conn:
            cols = {r[1] for r in conn.execute("PRAGMA table_info(consultant_messages)")}
            if "cleared_by_user" not in cols:
                conn.execute("ALTER TABLE consultant_messages ADD COLUMN cleared_by_user INTEGER NOT NULL DEFAULT 0")
                conn.commit()
    except Exception as exc:
        logger.debug("ensure_thread_schema: %s", exc)


def is_owner(request_id: int, phone: str) -> bool:
    try:
        with get_giso_db_conn() as conn:
            row = conn.execute(
                "SELECT 1 FROM consultant_requests WHERE id=? AND phone=?",
                (int(request_id), str(phone or ""))).fetchone()
        return bool(row)
    except Exception:
        return False


def thread_messages(request_id: int, include_cleared: bool = False) -> list:
    ensure_thread_schema()
    try:
        with get_giso_db_conn() as conn:
            sql = "SELECT * FROM consultant_messages WHERE request_id=?"
            if not include_cleared:
                sql += " AND COALESCE(cleared_by_user,0)=0"
            sql += " ORDER BY id ASC"
            return [dict(m) for m in conn.execute(sql, (int(request_id),)).fetchall()]
    except Exception as exc:
        logger.error("thread_messages: %s", exc)
        return []


def clear_user_thread(request_id: int) -> int:
    """بایگانی نماِ کاربر برای کل رشته؛ تاریخچهٔ اصلی حفظ می‌شود."""
    ensure_thread_schema()
    try:
        with get_giso_db_conn() as conn:
            cur = conn.execute(
                "UPDATE consultant_messages SET cleared_by_user=1 WHERE request_id=?",
                (int(request_id),))
            conn.commit()
            return int(cur.rowcount or 0)
    except Exception as exc:
        logger.error("clear_user_thread: %s", exc)
        return 0
