# -*- coding: utf-8 -*-
"""Idempotent additive schema for the introduction-only Beauty Centers MVP."""
import logging

from giso.base import get_giso_db_conn

logger = logging.getLogger("giso_beauty_centers_schema")

SCHEMA = """
CREATE TABLE IF NOT EXISTS beauty_centers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    owner_user_id INTEGER NOT NULL UNIQUE,
    name TEXT NOT NULL,
    slug TEXT NOT NULL UNIQUE,
    category TEXT NOT NULL DEFAULT 'hair',
    center_type TEXT NOT NULL DEFAULT 'salon',
    city TEXT DEFAULT '',
    region TEXT DEFAULT '',
    address_summary TEXT DEFAULT '',
    business_phone TEXT DEFAULT '',
    contact_time TEXT DEFAULT '',
    description TEXT DEFAULT '',
    services_json TEXT DEFAULT '[]',
    image_path TEXT DEFAULT '',
    status TEXT NOT NULL DEFAULT 'pending_review',
    admin_note TEXT DEFAULT '',
    is_active INTEGER NOT NULL DEFAULT 1,
    is_featured INTEGER NOT NULL DEFAULT 0,
    sort_order INTEGER NOT NULL DEFAULT 0,
    terms_version TEXT DEFAULT 'beauty-centers-v1',
    terms_accepted_at TEXT DEFAULT '',
    views_count INTEGER NOT NULL DEFAULT 0,
    contact_clicks INTEGER NOT NULL DEFAULT 0,
    analysis_impressions INTEGER NOT NULL DEFAULT 0,
    price_level TEXT NOT NULL DEFAULT 'on_request',
    starting_price INTEGER NOT NULL DEFAULT 0,
    price_inquiry_clicks INTEGER NOT NULL DEFAULT 0,
    created_at TEXT DEFAULT '',
    updated_at TEXT DEFAULT '',
    published_at TEXT DEFAULT '',
    listing_expires_at TEXT DEFAULT '',
    promotion_type TEXT DEFAULT '',
    promotion_expires_at TEXT DEFAULT '',
    promotion_bumped_at TEXT DEFAULT '',
    FOREIGN KEY(owner_user_id) REFERENCES giso_web_auth(id)
);
CREATE INDEX IF NOT EXISTS idx_beauty_centers_status ON beauty_centers(status,is_active);
CREATE INDEX IF NOT EXISTS idx_beauty_centers_city ON beauty_centers(city);
CREATE INDEX IF NOT EXISTS idx_beauty_centers_type ON beauty_centers(center_type);
CREATE INDEX IF NOT EXISTS idx_beauty_centers_featured ON beauty_centers(is_featured,sort_order);

CREATE TABLE IF NOT EXISTS beauty_center_reports (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    center_id INTEGER NOT NULL,
    reporter_user_id INTEGER NOT NULL,
    reason TEXT DEFAULT '',
    message TEXT DEFAULT '',
    status TEXT NOT NULL DEFAULT 'open',
    created_at TEXT DEFAULT '',
    updated_at TEXT DEFAULT '',
    FOREIGN KEY(center_id) REFERENCES beauty_centers(id),
    FOREIGN KEY(reporter_user_id) REFERENCES giso_web_auth(id)
);
CREATE INDEX IF NOT EXISTS idx_beauty_reports_center ON beauty_center_reports(center_id,status);
CREATE INDEX IF NOT EXISTS idx_beauty_reports_status ON beauty_center_reports(status,created_at);

CREATE TABLE IF NOT EXISTS beauty_center_images (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    center_id INTEGER NOT NULL,
    image_path TEXT NOT NULL,
    sort_order INTEGER NOT NULL DEFAULT 0,
    created_at TEXT DEFAULT '',
    FOREIGN KEY(center_id) REFERENCES beauty_centers(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_beauty_center_images ON beauty_center_images(center_id,sort_order,id);

CREATE TABLE IF NOT EXISTS beauty_center_conversations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    center_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    status TEXT NOT NULL DEFAULT 'active',
    last_message_at TEXT DEFAULT '',
    created_at TEXT DEFAULT '',
    closed_at TEXT DEFAULT '',
    UNIQUE(center_id,user_id),
    FOREIGN KEY(center_id) REFERENCES beauty_centers(id),
    FOREIGN KEY(user_id) REFERENCES giso_web_auth(id)
);
CREATE INDEX IF NOT EXISTS idx_beauty_conversations_center ON beauty_center_conversations(center_id,status,last_message_at);
CREATE INDEX IF NOT EXISTS idx_beauty_conversations_user ON beauty_center_conversations(user_id,status,last_message_at);

CREATE TABLE IF NOT EXISTS beauty_center_messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    conversation_id INTEGER NOT NULL,
    sender_user_id INTEGER NOT NULL,
    message_text TEXT NOT NULL,
    is_read INTEGER NOT NULL DEFAULT 0,
    is_reported INTEGER NOT NULL DEFAULT 0,
    created_at TEXT DEFAULT '',
    FOREIGN KEY(conversation_id) REFERENCES beauty_center_conversations(id),
    FOREIGN KEY(sender_user_id) REFERENCES giso_web_auth(id)
);
CREATE INDEX IF NOT EXISTS idx_beauty_messages_conversation ON beauty_center_messages(conversation_id,id);
CREATE INDEX IF NOT EXISTS idx_beauty_messages_unread ON beauty_center_messages(conversation_id,is_read);

CREATE TABLE IF NOT EXISTS beauty_center_feedback (
 id INTEGER PRIMARY KEY AUTOINCREMENT, center_id INTEGER NOT NULL,conversation_id INTEGER NOT NULL,user_id INTEGER NOT NULL,
 response_level TEXT NOT NULL,price_level TEXT NOT NULL,overall_level TEXT NOT NULL,comment TEXT DEFAULT '',status TEXT DEFAULT 'pending',created_at TEXT DEFAULT '',
 UNIQUE(conversation_id,user_id),FOREIGN KEY(center_id) REFERENCES beauty_centers(id),FOREIGN KEY(conversation_id) REFERENCES beauty_center_conversations(id)
);
CREATE INDEX IF NOT EXISTS idx_beauty_feedback_center ON beauty_center_feedback(center_id,status,created_at);
CREATE TABLE IF NOT EXISTS beauty_center_promotions (
 id INTEGER PRIMARY KEY AUTOINCREMENT,center_id INTEGER NOT NULL,owner_user_id INTEGER NOT NULL,package_key TEXT NOT NULL,amount INTEGER NOT NULL,
 starts_at TEXT DEFAULT '',expires_at TEXT DEFAULT '',transaction_key TEXT UNIQUE NOT NULL,status TEXT DEFAULT 'active',created_at TEXT DEFAULT ''
);
CREATE INDEX IF NOT EXISTS idx_beauty_promotions_active ON beauty_center_promotions(center_id,status,expires_at);
CREATE TABLE IF NOT EXISTS beauty_center_discounts (
 id INTEGER PRIMARY KEY AUTOINCREMENT,center_id INTEGER NOT NULL,title TEXT NOT NULL,description TEXT DEFAULT '',discount_value TEXT DEFAULT '',expires_at TEXT NOT NULL,status TEXT DEFAULT 'pending',created_at TEXT DEFAULT ''
);
CREATE INDEX IF NOT EXISTS idx_beauty_discounts_active ON beauty_center_discounts(center_id,status,expires_at);
CREATE TABLE IF NOT EXISTS beauty_center_events (
 id INTEGER PRIMARY KEY AUTOINCREMENT,center_id INTEGER DEFAULT 0,event_type TEXT NOT NULL,user_id INTEGER DEFAULT 0,created_at TEXT DEFAULT ''
);
CREATE INDEX IF NOT EXISTS idx_beauty_events_date ON beauty_center_events(event_type,created_at);
CREATE TABLE IF NOT EXISTS beauty_center_expiry_notices (
 id INTEGER PRIMARY KEY AUTOINCREMENT,center_id INTEGER NOT NULL,notice_key TEXT NOT NULL,created_at TEXT DEFAULT '',UNIQUE(center_id,notice_key)
);
"""


def migrate_beauty_center_tables():
    try:
        with get_giso_db_conn() as conn:
            conn.executescript(SCHEMA)
            columns = {row[1] for row in conn.execute("PRAGMA table_info(beauty_centers)").fetchall()}
            if "category" not in columns:
                conn.execute("ALTER TABLE beauty_centers ADD COLUMN category TEXT NOT NULL DEFAULT 'hair'")
            if "price_level" not in columns:
                conn.execute("ALTER TABLE beauty_centers ADD COLUMN price_level TEXT NOT NULL DEFAULT 'on_request'")
            if "starting_price" not in columns:
                conn.execute("ALTER TABLE beauty_centers ADD COLUMN starting_price INTEGER NOT NULL DEFAULT 0")
            if "price_inquiry_clicks" not in columns:
                conn.execute("ALTER TABLE beauty_centers ADD COLUMN price_inquiry_clicks INTEGER NOT NULL DEFAULT 0")
            for column in ("listing_expires_at", "promotion_type", "promotion_expires_at", "promotion_bumped_at",
                           "salon_phone", "display_phone_choice", "last_edit_at"):
                if column not in columns:
                    conn.execute(f"ALTER TABLE beauty_centers ADD COLUMN {column} TEXT DEFAULT ''")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_beauty_centers_category ON beauty_centers(category,status,is_active)")
            conn.commit()
    except Exception as exc:
        logger.exception("beauty center schema migration failed: %s", exc)
        raise
    # Phase A pricing tables (services + working hours) — additive only.
    from giso.beauty_centers.pricing.schema import migrate_pricing_tables
    migrate_pricing_tables()


__all__ = ["migrate_beauty_center_tables"]
