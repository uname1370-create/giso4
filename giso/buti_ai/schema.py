# -*- coding: utf-8 -*-
"""
giso/buti_ai/schema.py — جدول‌های پایگاه داده ماژول آینه جادویی در giso.db.
"""
import logging
from giso.base import get_giso_db_conn

logger = logging.getLogger("giso_buti_ai_schema")

BUTI_AI_TABLES_SQL = """
CREATE TABLE IF NOT EXISTS buti_ai_sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    service_type TEXT NOT NULL,
    city TEXT DEFAULT 'مشهد',
    center_id INTEGER,
    conversation_id INTEGER,
    status TEXT DEFAULT 'completed',
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_buti_ai_sessions_user ON buti_ai_sessions(user_id);
CREATE INDEX IF NOT EXISTS idx_buti_ai_sessions_created ON buti_ai_sessions(created_at DESC);

CREATE TABLE IF NOT EXISTS buti_ai_waitlist (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    phone_number TEXT NOT NULL,
    city TEXT NOT NULL,
    service_type TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_buti_ai_waitlist_city ON buti_ai_waitlist(city, service_type);
"""


def init_buti_ai_db():
    """ایجاد امن و خودکار جدول‌های آینه جادویی در پایگاه داده اصلی giso.db."""
    try:
        conn = get_giso_db_conn()
        conn.executescript(BUTI_AI_TABLES_SQL)
        conn.commit()
    except Exception as e:
        logger.error("Failed to initialize buti_ai tables: %s", e)
