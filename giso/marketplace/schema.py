# -*- coding: utf-8 -*-
"""Idempotent additive schema for the Giso hair marketplace MVP."""
import logging
import sqlite3
from pathlib import Path

logger = logging.getLogger("giso_marketplace_schema")


MARKETPLACE_SCHEMA = """
CREATE TABLE IF NOT EXISTS hair_listings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    slug TEXT DEFAULT '',
    seller_user_id INTEGER NOT NULL,
    source_hair_order_id INTEGER,
    photo_path TEXT NOT NULL,
    hair_type TEXT DEFAULT '',
    length_cm INTEGER NOT NULL,
    hair_health TEXT DEFAULT '',
    hair_weight TEXT DEFAULT '',
    city TEXT DEFAULT '',
    region TEXT DEFAULT '',
    seller_asking_price INTEGER DEFAULT 0,
    seller_note TEXT DEFAULT '',
    estimated_price_snapshot TEXT DEFAULT '',
    status TEXT DEFAULT 'pending_review',
    views_count INTEGER DEFAULT 0,
    offers_count INTEGER DEFAULT 0,
    highest_offer_amount INTEGER DEFAULT 0,
    admin_note TEXT DEFAULT '',
    reject_reason TEXT DEFAULT '',
    terms_version TEXT DEFAULT 'marketplace-v1',
    terms_accepted_at TEXT DEFAULT '',
    created_at TEXT DEFAULT '',
    updated_at TEXT DEFAULT '',
    published_at TEXT DEFAULT '',
    deleted_at TEXT DEFAULT '',
    sold_at TEXT DEFAULT '',
    sold_offer_id INTEGER,
    FOREIGN KEY(seller_user_id) REFERENCES giso_web_auth(id),
    FOREIGN KEY(source_hair_order_id) REFERENCES hair_orders(id),
    FOREIGN KEY(sold_offer_id) REFERENCES buyer_offers(id)
);
CREATE INDEX IF NOT EXISTS idx_hair_listing_seller ON hair_listings(seller_user_id);
CREATE INDEX IF NOT EXISTS idx_hair_listing_slug ON hair_listings(slug);
CREATE INDEX IF NOT EXISTS idx_hair_listing_status ON hair_listings(status);
CREATE INDEX IF NOT EXISTS idx_hair_listing_city ON hair_listings(city);
CREATE INDEX IF NOT EXISTS idx_hair_listing_price ON hair_listings(seller_asking_price);
CREATE INDEX IF NOT EXISTS idx_hair_listing_created ON hair_listings(created_at);

CREATE TABLE IF NOT EXISTS marketplace_devices (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    device_key_hash TEXT NOT NULL UNIQUE,
    fingerprint_hash TEXT DEFAULT '',
    last_ip_hash TEXT DEFAULT '',
    first_seen_at TEXT DEFAULT '',
    last_seen_at TEXT DEFAULT '',
    linked_user_count INTEGER DEFAULT 0,
    linked_phone_count INTEGER DEFAULT 0,
    risk_level TEXT DEFAULT 'clean',
    correlation_flags TEXT DEFAULT '',
    correlation_evidence TEXT DEFAULT '',
    correlated_device_count INTEGER DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_market_device_key ON marketplace_devices(device_key_hash);
CREATE INDEX IF NOT EXISTS idx_market_device_fp ON marketplace_devices(fingerprint_hash);
CREATE INDEX IF NOT EXISTS idx_market_device_ip ON marketplace_devices(last_ip_hash);
CREATE INDEX IF NOT EXISTS idx_market_device_risk ON marketplace_devices(risk_level);

CREATE TABLE IF NOT EXISTS marketplace_device_links (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    device_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    phone_snapshot TEXT DEFAULT '',
    first_seen_at TEXT DEFAULT '',
    last_seen_at TEXT DEFAULT '',
    last_event TEXT DEFAULT 'visit',
    FOREIGN KEY(device_id) REFERENCES marketplace_devices(id),
    FOREIGN KEY(user_id) REFERENCES giso_web_auth(id),
    UNIQUE(device_id, user_id)
);
CREATE INDEX IF NOT EXISTS idx_market_device_link_device ON marketplace_device_links(device_id);
CREATE INDEX IF NOT EXISTS idx_market_device_link_user ON marketplace_device_links(user_id);
CREATE INDEX IF NOT EXISTS idx_market_device_link_phone ON marketplace_device_links(phone_snapshot);

CREATE TABLE IF NOT EXISTS marketplace_phone_observations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    device_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    phone_snapshot TEXT NOT NULL,
    first_seen_at TEXT DEFAULT '',
    last_seen_at TEXT DEFAULT '',
    observation_count INTEGER DEFAULT 1,
    last_event TEXT DEFAULT 'visit',
    FOREIGN KEY(device_id) REFERENCES marketplace_devices(id),
    FOREIGN KEY(user_id) REFERENCES giso_web_auth(id),
    UNIQUE(device_id, user_id, phone_snapshot)
);
CREATE INDEX IF NOT EXISTS idx_market_phone_obs_device ON marketplace_phone_observations(device_id);
CREATE INDEX IF NOT EXISTS idx_market_phone_obs_user ON marketplace_phone_observations(user_id);
CREATE INDEX IF NOT EXISTS idx_market_phone_obs_phone ON marketplace_phone_observations(phone_snapshot);

CREATE TABLE IF NOT EXISTS marketplace_listing_device_claims (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    listing_id INTEGER NOT NULL,
    device_id INTEGER NOT NULL,
    buyer_user_id INTEGER NOT NULL,
    phone_snapshot TEXT DEFAULT '',
    created_at TEXT DEFAULT '',
    updated_at TEXT DEFAULT '',
    FOREIGN KEY(listing_id) REFERENCES hair_listings(id),
    FOREIGN KEY(device_id) REFERENCES marketplace_devices(id),
    FOREIGN KEY(buyer_user_id) REFERENCES giso_web_auth(id),
    UNIQUE(listing_id, device_id)
);
CREATE INDEX IF NOT EXISTS idx_market_claim_listing ON marketplace_listing_device_claims(listing_id);
CREATE INDEX IF NOT EXISTS idx_market_claim_device ON marketplace_listing_device_claims(device_id);
CREATE INDEX IF NOT EXISTS idx_market_claim_user ON marketplace_listing_device_claims(buyer_user_id);

CREATE TABLE IF NOT EXISTS marketplace_risk_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_type TEXT NOT NULL,
    status TEXT DEFAULT 'flagged',
    listing_id INTEGER,
    user_id INTEGER,
    phone_snapshot TEXT DEFAULT '',
    device_id INTEGER,
    device_hash_short TEXT DEFAULT '',
    fingerprint_hash TEXT DEFAULT '',
    ip_hash TEXT DEFAULT '',
    risk_level TEXT DEFAULT 'clean',
    reason TEXT DEFAULT '',
    reason_detail TEXT DEFAULT '',
    offer_amount INTEGER DEFAULT 0,
    offer_note TEXT DEFAULT '',
    correlation_evidence TEXT DEFAULT '',
    created_at TEXT DEFAULT '',
    FOREIGN KEY(listing_id) REFERENCES hair_listings(id),
    FOREIGN KEY(user_id) REFERENCES giso_web_auth(id),
    FOREIGN KEY(device_id) REFERENCES marketplace_devices(id)
);
CREATE INDEX IF NOT EXISTS idx_market_risk_event_type ON marketplace_risk_events(event_type);
CREATE INDEX IF NOT EXISTS idx_market_risk_event_status ON marketplace_risk_events(status);
CREATE INDEX IF NOT EXISTS idx_market_risk_event_listing ON marketplace_risk_events(listing_id);
CREATE INDEX IF NOT EXISTS idx_market_risk_event_user ON marketplace_risk_events(user_id);
CREATE INDEX IF NOT EXISTS idx_market_risk_event_device ON marketplace_risk_events(device_id);
CREATE INDEX IF NOT EXISTS idx_market_risk_event_created ON marketplace_risk_events(created_at);

CREATE TABLE IF NOT EXISTS buyer_profiles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL UNIQUE,
    phone_snapshot TEXT DEFAULT '',
    latest_device_key TEXT DEFAULT '',
    verification_status TEXT DEFAULT 'pending',
    risk_flags TEXT DEFAULT '',
    admin_note TEXT DEFAULT '',
    verified_at TEXT DEFAULT '',
    terms_version TEXT DEFAULT 'marketplace-v1',
    terms_accepted_at TEXT DEFAULT '',
    request_name TEXT DEFAULT '',
    request_phone TEXT DEFAULT '',
    request_city TEXT DEFAULT '',
    buyer_type TEXT DEFAULT 'personal',
    request_description TEXT DEFAULT '',
    created_at TEXT DEFAULT '',
    updated_at TEXT DEFAULT '',
    FOREIGN KEY(user_id) REFERENCES giso_web_auth(id)
);
CREATE INDEX IF NOT EXISTS idx_buyer_profile_user ON buyer_profiles(user_id);
CREATE INDEX IF NOT EXISTS idx_buyer_profile_phone ON buyer_profiles(phone_snapshot);
CREATE INDEX IF NOT EXISTS idx_buyer_profile_status ON buyer_profiles(verification_status);
CREATE INDEX IF NOT EXISTS idx_buyer_profile_device ON buyer_profiles(latest_device_key);

CREATE TABLE IF NOT EXISTS buyer_offers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    listing_id INTEGER NOT NULL,
    buyer_user_id INTEGER NOT NULL,
    buyer_profile_id INTEGER NOT NULL,
    device_id INTEGER,
    offer_amount INTEGER NOT NULL,
    offer_note TEXT DEFAULT '',
    status TEXT DEFAULT 'pending',
    seller_response_note TEXT DEFAULT '',
    seller_counter_amount INTEGER DEFAULT 0,
    risk_snapshot TEXT DEFAULT 'clean',
    accepted_at TEXT DEFAULT '',
    rejected_at TEXT DEFAULT '',
    sold_at TEXT DEFAULT '',
    chat_closed INTEGER DEFAULT 0,
    chat_closed_at TEXT DEFAULT '',
    chat_closed_by_user_id INTEGER,
    created_at TEXT DEFAULT '',
    updated_at TEXT DEFAULT '',
    FOREIGN KEY(listing_id) REFERENCES hair_listings(id),
    FOREIGN KEY(buyer_user_id) REFERENCES giso_web_auth(id),
    FOREIGN KEY(buyer_profile_id) REFERENCES buyer_profiles(id),
    FOREIGN KEY(device_id) REFERENCES marketplace_devices(id),
    FOREIGN KEY(chat_closed_by_user_id) REFERENCES giso_web_auth(id)
);
CREATE INDEX IF NOT EXISTS idx_buyer_offer_listing ON buyer_offers(listing_id);
CREATE INDEX IF NOT EXISTS idx_buyer_offer_user ON buyer_offers(buyer_user_id);
CREATE INDEX IF NOT EXISTS idx_buyer_offer_profile ON buyer_offers(buyer_profile_id);
CREATE INDEX IF NOT EXISTS idx_buyer_offer_device ON buyer_offers(device_id);
CREATE INDEX IF NOT EXISTS idx_buyer_offer_status ON buyer_offers(status);
CREATE UNIQUE INDEX IF NOT EXISTS ux_buyer_offer_active_user_listing
    ON buyer_offers(listing_id, buyer_user_id)
    WHERE status IN ('pending', 'countered', 'accepted');
CREATE INDEX IF NOT EXISTS idx_buyer_offer_device_listing
    ON buyer_offers(listing_id, device_id, status);

CREATE TABLE IF NOT EXISTS marketplace_reviews (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    listing_id INTEGER NOT NULL,
    offer_id INTEGER NOT NULL,
    reviewer_user_id INTEGER NOT NULL,
    reviewee_user_id INTEGER NOT NULL,
    reviewer_role TEXT NOT NULL,
    rating INTEGER NOT NULL CHECK(rating BETWEEN 1 AND 5),
    comment TEXT DEFAULT '',
    status TEXT DEFAULT 'visible',
    created_at TEXT DEFAULT '',
    FOREIGN KEY(listing_id) REFERENCES hair_listings(id),
    FOREIGN KEY(offer_id) REFERENCES buyer_offers(id),
    FOREIGN KEY(reviewer_user_id) REFERENCES giso_web_auth(id),
    FOREIGN KEY(reviewee_user_id) REFERENCES giso_web_auth(id),
    UNIQUE(offer_id, reviewer_user_id)
);
CREATE INDEX IF NOT EXISTS idx_market_review_listing ON marketplace_reviews(listing_id);
CREATE INDEX IF NOT EXISTS idx_market_review_offer ON marketplace_reviews(offer_id);
CREATE INDEX IF NOT EXISTS idx_market_review_reviewer ON marketplace_reviews(reviewer_user_id);
CREATE INDEX IF NOT EXISTS idx_market_review_created ON marketplace_reviews(created_at);

CREATE TABLE IF NOT EXISTS marketplace_user_ratings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL UNIQUE,
    rating_avg REAL DEFAULT 0,
    rating_count INTEGER DEFAULT 0,
    updated_at TEXT DEFAULT ''
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_market_user_rating_user ON marketplace_user_ratings(user_id);

CREATE TABLE IF NOT EXISTS marketplace_price_stats (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    city TEXT NOT NULL,
    hair_type TEXT DEFAULT 'all',
    length_range TEXT DEFAULT 'all',
    min_price INTEGER DEFAULT 0,
    max_price INTEGER DEFAULT 0,
    avg_price INTEGER DEFAULT 0,
    sample_count INTEGER DEFAULT 0,
    source TEXT DEFAULT 'internal',
    updated_at TEXT DEFAULT '',
    UNIQUE(city, hair_type, length_range)
);
CREATE INDEX IF NOT EXISTS idx_market_price_stat_city ON marketplace_price_stats(city);
CREATE INDEX IF NOT EXISTS idx_market_price_stat_updated ON marketplace_price_stats(updated_at);

CREATE TABLE IF NOT EXISTS marketplace_price_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    city TEXT NOT NULL,
    date TEXT NOT NULL,
    avg_price INTEGER DEFAULT 0,
    max_price INTEGER DEFAULT 0,
    UNIQUE(city, date)
);
CREATE INDEX IF NOT EXISTS idx_market_price_history_city_date ON marketplace_price_history(city, date);

CREATE TABLE IF NOT EXISTS marketplace_saved_searches (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    filters TEXT DEFAULT '{}',
    alert_enabled INTEGER DEFAULT 1,
    created_at TEXT DEFAULT '',
    FOREIGN KEY(user_id) REFERENCES giso_web_auth(id)
);
CREATE INDEX IF NOT EXISTS idx_market_saved_search_user ON marketplace_saved_searches(user_id);
CREATE INDEX IF NOT EXISTS idx_market_saved_search_alert ON marketplace_saved_searches(alert_enabled);

CREATE TABLE IF NOT EXISTS marketplace_policies (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    key TEXT NOT NULL UNIQUE,
    value TEXT DEFAULT '',
    updated_at TEXT DEFAULT ''
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_market_policy_key ON marketplace_policies(key);

CREATE TABLE IF NOT EXISTS marketplace_event_stats (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date TEXT NOT NULL UNIQUE,
    listings_count INTEGER DEFAULT 0,
    offers_count INTEGER DEFAULT 0,
    deals_count INTEGER DEFAULT 0,
    active_users_count INTEGER DEFAULT 0,
    views_count INTEGER DEFAULT 0,
    updated_at TEXT DEFAULT ''
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_market_event_stat_date ON marketplace_event_stats(date);

CREATE TABLE IF NOT EXISTS marketplace_price_job_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    status TEXT DEFAULT 'started',
    source TEXT DEFAULT 'internal',
    sample_count INTEGER DEFAULT 0,
    ai_provider TEXT DEFAULT '',
    fallback_level TEXT DEFAULT 'internal',
    error_message TEXT DEFAULT '',
    started_at TEXT DEFAULT '',
    finished_at TEXT DEFAULT ''
);
CREATE INDEX IF NOT EXISTS idx_market_price_job_status ON marketplace_price_job_logs(status);
CREATE INDEX IF NOT EXISTS idx_market_price_job_finished ON marketplace_price_job_logs(finished_at);

CREATE TABLE IF NOT EXISTS marketplace_messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    offer_id INTEGER NOT NULL,
    sender_user_id INTEGER NOT NULL,
    sender_role TEXT NOT NULL,
    message_text TEXT NOT NULL,
    created_at TEXT DEFAULT '',
    is_reported INTEGER DEFAULT 0,
    is_deleted_for_moderation INTEGER DEFAULT 0,
    FOREIGN KEY(offer_id) REFERENCES buyer_offers(id),
    FOREIGN KEY(sender_user_id) REFERENCES giso_web_auth(id)
);
CREATE INDEX IF NOT EXISTS idx_market_message_offer ON marketplace_messages(offer_id);
CREATE INDEX IF NOT EXISTS idx_market_message_sender ON marketplace_messages(sender_user_id);
CREATE INDEX IF NOT EXISTS idx_market_message_created ON marketplace_messages(created_at);

CREATE TABLE IF NOT EXISTS listing_reports (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    listing_id INTEGER NOT NULL,
    offer_id INTEGER,
    reporter_user_id INTEGER NOT NULL,
    target_type TEXT DEFAULT 'listing',
    reason TEXT DEFAULT '',
    message TEXT DEFAULT '',
    status TEXT DEFAULT 'open',
    created_at TEXT DEFAULT '',
    updated_at TEXT DEFAULT '',
    FOREIGN KEY(listing_id) REFERENCES hair_listings(id),
    FOREIGN KEY(offer_id) REFERENCES buyer_offers(id),
    FOREIGN KEY(reporter_user_id) REFERENCES giso_web_auth(id)
);
CREATE INDEX IF NOT EXISTS idx_listing_report_listing ON listing_reports(listing_id);
CREATE INDEX IF NOT EXISTS idx_listing_report_offer ON listing_reports(offer_id);
CREATE INDEX IF NOT EXISTS idx_listing_report_reporter ON listing_reports(reporter_user_id);
CREATE INDEX IF NOT EXISTS idx_listing_report_status ON listing_reports(status);

CREATE TABLE IF NOT EXISTS marketplace_buyer_alerts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    min_length INTEGER DEFAULT 0,
    max_length INTEGER DEFAULT 0,
    hair_type TEXT DEFAULT '',
    city TEXT DEFAULT '',
    min_price INTEGER DEFAULT 0,
    max_price INTEGER DEFAULT 0,
    duration_days INTEGER NOT NULL DEFAULT 7,
    expires_at TEXT NOT NULL,
    is_active INTEGER NOT NULL DEFAULT 1,
    purchase_transaction_key TEXT UNIQUE,
    created_at TEXT DEFAULT '',
    FOREIGN KEY(user_id) REFERENCES giso_web_auth(id)
);
CREATE INDEX IF NOT EXISTS idx_buyer_alert_active ON marketplace_buyer_alerts(user_id,is_active,expires_at);

CREATE TABLE IF NOT EXISTS marketplace_offer_bonus_purchases (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    extra_offers INTEGER NOT NULL DEFAULT 5,
    expires_at TEXT NOT NULL,
    transaction_key TEXT UNIQUE NOT NULL,
    created_at TEXT DEFAULT '',
    FOREIGN KEY(user_id) REFERENCES giso_web_auth(id)
);
CREATE INDEX IF NOT EXISTS idx_offer_bonus_active ON marketplace_offer_bonus_purchases(user_id,expires_at);
"""


def _default_db_path() -> str:
    return str(Path(__file__).resolve().parents[1] / "data" / "giso.db")


def migrate_marketplace_tables(db_path: str = None) -> bool:
    """Create only additive marketplace tables/indexes; safe to run repeatedly."""
    path = db_path or _default_db_path()
    try:
        conn = sqlite3.connect(path)
        try:
            conn.executescript(MARKETPLACE_SCHEMA)
            # Additive guards keep repeated/partial Phase 2 deployments safe.
            listing_cols = {row[1] for row in conn.execute("PRAGMA table_info(hair_listings)").fetchall()}
            if "slug" not in listing_cols:
                conn.execute("ALTER TABLE hair_listings ADD COLUMN slug TEXT DEFAULT ''")
            if "deleted_at" not in listing_cols:
                conn.execute("ALTER TABLE hair_listings ADD COLUMN deleted_at TEXT DEFAULT ''")
            if "sold_at" not in listing_cols:
                conn.execute("ALTER TABLE hair_listings ADD COLUMN sold_at TEXT DEFAULT ''")
            if "sold_offer_id" not in listing_cols:
                conn.execute("ALTER TABLE hair_listings ADD COLUMN sold_offer_id INTEGER")
            for column, definition in {
                "promotion_type": "TEXT DEFAULT ''", "promotion_expires_at": "TEXT DEFAULT ''",
                "promotion_bumped_at": "TEXT DEFAULT ''", "edit_count": "INTEGER DEFAULT 0",
                "listing_expires_at": "TEXT DEFAULT ''",
            }.items():
                if column not in listing_cols:
                    conn.execute(f"ALTER TABLE hair_listings ADD COLUMN {column} {definition}")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_hair_listing_expires ON hair_listings(listing_expires_at)")
            conn.execute("CREATE TABLE IF NOT EXISTS marketplace_promotion_purchases (id INTEGER PRIMARY KEY AUTOINCREMENT,listing_id INTEGER NOT NULL,user_id INTEGER NOT NULL,package_key TEXT NOT NULL,amount INTEGER NOT NULL,spend_amount INTEGER DEFAULT 0,cash_amount INTEGER DEFAULT 0,starts_at TEXT DEFAULT '',expires_at TEXT DEFAULT '',transaction_key TEXT UNIQUE NOT NULL,status TEXT DEFAULT 'active',created_at TEXT DEFAULT '')")

            offer_cols = {row[1] for row in conn.execute("PRAGMA table_info(buyer_offers)").fetchall()}
            if "sold_at" not in offer_cols:
                conn.execute("ALTER TABLE buyer_offers ADD COLUMN sold_at TEXT DEFAULT ''")
            if "chat_closed" not in offer_cols:
                conn.execute("ALTER TABLE buyer_offers ADD COLUMN chat_closed INTEGER DEFAULT 0")
            if "chat_closed_at" not in offer_cols:
                conn.execute("ALTER TABLE buyer_offers ADD COLUMN chat_closed_at TEXT DEFAULT ''")
            if "chat_closed_by_user_id" not in offer_cols:
                conn.execute("ALTER TABLE buyer_offers ADD COLUMN chat_closed_by_user_id INTEGER")

            review_cols = {row[1] for row in conn.execute("PRAGMA table_info(marketplace_reviews)").fetchall()}
            if "status" not in review_cols:
                conn.execute("ALTER TABLE marketplace_reviews ADD COLUMN status TEXT DEFAULT 'visible'")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_hair_listing_slug ON hair_listings(slug)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_hair_listing_deleted ON hair_listings(deleted_at)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_hair_listing_sold ON hair_listings(sold_at)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_buyer_offer_chat_closed ON buyer_offers(chat_closed)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_market_review_reviewee ON marketplace_reviews(reviewee_user_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_market_review_status ON marketplace_reviews(status)")
            conn.execute(
                "UPDATE marketplace_user_ratings SET rating_avg=0,rating_count=0,updated_at=datetime('now')"
            )
            conn.execute(
                "INSERT INTO marketplace_user_ratings(user_id,rating_avg,rating_count,updated_at) "
                "SELECT r.reviewee_user_id,AVG(r.rating),COUNT(*),datetime('now') "
                "FROM marketplace_reviews r JOIN hair_listings l ON l.id=r.listing_id "
                "WHERE COALESCE(r.status,'visible')='visible' AND COALESCE(l.deleted_at,'')='' "
                "GROUP BY r.reviewee_user_id "
                "ON CONFLICT(user_id) DO UPDATE SET rating_avg=excluded.rating_avg, "
                "rating_count=excluded.rating_count, updated_at=excluded.updated_at"
            )

            buyer_cols = {row[1] for row in conn.execute("PRAGMA table_info(buyer_profiles)").fetchall()}
            if "terms_version" not in buyer_cols:
                conn.execute("ALTER TABLE buyer_profiles ADD COLUMN terms_version TEXT DEFAULT 'marketplace-v1'")
            if "terms_accepted_at" not in buyer_cols:
                conn.execute("ALTER TABLE buyer_profiles ADD COLUMN terms_accepted_at TEXT DEFAULT ''")
            buyer_request_columns = {
                "request_name": "TEXT DEFAULT ''",
                "request_phone": "TEXT DEFAULT ''",
                "request_city": "TEXT DEFAULT ''",
                "buyer_type": "TEXT DEFAULT 'personal'",
                "request_description": "TEXT DEFAULT ''",
                "budget_min": "INTEGER DEFAULT 0",
                "budget_max": "INTEGER DEFAULT 0",
                "edit_count": "INTEGER DEFAULT 0",
            }
            for column, definition in buyer_request_columns.items():
                if column not in buyer_cols:
                    conn.execute(f"ALTER TABLE buyer_profiles ADD COLUMN {column} {definition}")

            # Legacy device/report tables are intentionally preserved for old data,
            # but no new correlation, claim, risk or report workflow is run.
            conn.commit()
        finally:
            conn.close()
        return True
    except Exception as exc:
        logger.error("marketplace schema migration failed: %s", exc)
        return False


__all__ = ["migrate_marketplace_tables", "MARKETPLACE_SCHEMA"]
