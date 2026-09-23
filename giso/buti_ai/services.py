# -*- coding: utf-8 -*-
"""
giso/buti_ai/services.py — منطق ذخیره‌سازی نشست‌ها و ثبت در لیست انتظار آینه جادویی.
"""
import logging
from datetime import datetime
from giso.base import get_giso_db_conn, normalize_phone

logger = logging.getLogger("giso_buti_ai_services")


def save_mirror_session(user_id, service_type, city="مشهد", center_id=None,
                        conversation_id=None, status="completed"):
    """ثبت جلسه پیش‌نمایش آینه جادویی در دیتابیس."""
    try:
        conn = get_giso_db_conn()
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cur = conn.execute(
            """
            INSERT INTO buti_ai_sessions (user_id, service_type, city, center_id, conversation_id, status, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (user_id, service_type, city, center_id, conversation_id, status, now_str)
        )
        conn.commit()
        return cur.lastrowid
    except Exception as e:
        logger.error("Error saving buti_ai session: %s", e)
        return None


def add_to_waitlist(phone_number, city, service_type):
    """ثبت شماره و تقاضای کاربر در لیست انتظار شهرستان‌ها."""
    try:
        clean_phone = normalize_phone(phone_number)
        conn = get_giso_db_conn()
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cur = conn.execute(
            """
            INSERT INTO buti_ai_waitlist (phone_number, city, service_type, created_at)
            VALUES (?, ?, ?, ?)
            """,
            (clean_phone, city.strip(), service_type.strip(), now_str)
        )
        conn.commit()
        return cur.lastrowid
    except Exception as e:
        logger.error("Error adding to buti_ai waitlist: %s", e)
        return None
