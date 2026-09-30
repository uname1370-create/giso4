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
    user_id INTEGER,
    phone_number TEXT NOT NULL,
    city TEXT NOT NULL,
    service_type TEXT NOT NULL,
    source TEXT DEFAULT '',
    status TEXT DEFAULT 'open',
    payload_json TEXT DEFAULT '',
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_buti_ai_waitlist_city ON buti_ai_waitlist(city, service_type);
CREATE INDEX IF NOT EXISTS idx_buti_ai_waitlist_status ON buti_ai_waitlist(service_type, status, created_at DESC);

CREATE TABLE IF NOT EXISTS buti_ai_service_demand (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    city TEXT NOT NULL,
    service_type TEXT NOT NULL,
    source TEXT DEFAULT '',
    status TEXT DEFAULT 'open',
    dedupe_key TEXT DEFAULT '',
    payload_json TEXT DEFAULT '',
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_buti_ai_service_demand_city ON buti_ai_service_demand(city, service_type);
CREATE INDEX IF NOT EXISTS idx_buti_ai_service_demand_status ON buti_ai_service_demand(service_type, status, created_at DESC);
CREATE UNIQUE INDEX IF NOT EXISTS idx_buti_ai_service_demand_dedupe ON buti_ai_service_demand(dedupe_key) WHERE dedupe_key <> '';

CREATE TABLE IF NOT EXISTS buti_ai_final_designs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id INTEGER,
    user_id INTEGER,
    service_type TEXT NOT NULL DEFAULT 'eyebrow',
    original_filename TEXT,
    final_filename TEXT,
    selected_style TEXT,
    recommended_style TEXT,
    change_level TEXT,
    provider TEXT,
    model TEXT,
    status TEXT DEFAULT 'created',
    prompt_json TEXT,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_buti_ai_final_designs_user ON buti_ai_final_designs(user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_buti_ai_final_designs_session ON buti_ai_final_designs(session_id);
"""


def _ensure_column(conn, table_name, column_name, column_sql):
    columns = {row[1] for row in conn.execute(f"PRAGMA table_info({table_name})").fetchall()}
    if column_name not in columns:
        conn.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_sql}")


def init_buti_ai_db():
    """ایجاد امن و خودکار جدول‌های آینه جادویی در پایگاه داده اصلی giso.db."""
    try:
        conn = get_giso_db_conn()
        conn.executescript(BUTI_AI_TABLES_SQL)
        _ensure_column(conn, "buti_ai_waitlist", "user_id", "user_id INTEGER")
        _ensure_column(conn, "buti_ai_waitlist", "source", "source TEXT DEFAULT ''")
        _ensure_column(conn, "buti_ai_waitlist", "status", "status TEXT DEFAULT 'open'")
        _ensure_column(conn, "buti_ai_waitlist", "payload_json", "payload_json TEXT DEFAULT ''")
        for _col, _ddl in (
            ("user_id", "user_id INTEGER"),
            ("source", "source TEXT DEFAULT ''"),
            ("status", "status TEXT DEFAULT 'open'"),
            ("dedupe_key", "dedupe_key TEXT DEFAULT ''"),
            ("payload_json", "payload_json TEXT DEFAULT ''"),
        ):
            _ensure_column(conn, "buti_ai_service_demand", _col, _ddl)
        try:
            from giso.buti_ai.ai_models import init_buti_ai_model_assignments

            init_buti_ai_model_assignments(conn)
        except Exception as model_exc:
            logger.error("Failed to initialize buti_ai model assignments: %s", model_exc)
        conn.commit()
    except Exception as e:
        logger.error("Failed to initialize buti_ai tables: %s", e)
