# -*- coding: utf-8 -*-
"""Stage 4: validated Instagram profile links and aggregate referral clicks."""
import sqlite3
from pathlib import Path

from giso.app import create_app
from giso.beauty_centers import schema
from giso.beauty_centers import routes as center_routes
from giso.beauty_centers import services as center_services

ROOT = Path(__file__).resolve().parents[2]


def test_instagram_username_and_profile_url_normalize_to_canonical_target():
    normalize = center_services.normalize_instagram_url
    assert normalize("@giso.beauty") == "https://www.instagram.com/giso.beauty/"
    assert normalize("giso_beauty") == "https://www.instagram.com/giso_beauty/"
    assert normalize("https://instagram.com/giso.beauty/") == "https://www.instagram.com/giso.beauty/"
    assert normalize("") == ""


def test_instagram_normalizer_rejects_open_redirect_and_non_profile_paths():
    normalize = center_services.normalize_instagram_url
    for candidate in (
        "https://instagram.com.evil.example/user",
        "https://evil.example/instagram.com/user",
        "https://instagram.com/user?next=https://evil.example",
        "https://instagram.com/p/abc123/",
        "https://instagram.com/user/path",
        "javascript:alert(1)",
        "@bad..name",
    ):
        try:
            normalize(candidate)
        except ValueError:
            continue
        raise AssertionError(f"unsafe/non-profile Instagram target accepted: {candidate}")


def test_center_profile_normalization_validates_instagram_field():
    values = {
        "name": "سالن نمونه", "category": "beauty", "center_type": "salon",
        "city": "مشهد", "business_phone": "09123456789", "display_phone_choice": "business",
        "services": ["brow"], "instagram_url": "@salon.sample",
    }
    fields, error = center_services._normalize_fields(values)
    assert not error
    assert fields["instagram_url"] == "https://www.instagram.com/salon.sample/"

    values["instagram_url"] = "https://evil.example/instagram"
    fields, error = center_services._normalize_fields(values)
    assert not fields
    assert "Instagram" in error


def test_event_migration_adds_instagram_fields_without_replacing_legacy_events(monkeypatch):
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute(
        "CREATE TABLE beauty_center_events (id INTEGER PRIMARY KEY,center_id INTEGER,event_type TEXT NOT NULL,user_id INTEGER DEFAULT 0,created_at TEXT DEFAULT '')"
    )
    conn.execute("INSERT INTO beauty_center_events(id,center_id,event_type) VALUES (1,7,'view')")
    conn.commit()
    monkeypatch.setattr(schema, "get_giso_db_conn", lambda: conn)
    import giso.beauty_centers.pricing.schema as pricing_schema
    monkeypatch.setattr(pricing_schema, "migrate_pricing_tables", lambda: None)

    schema.migrate_beauty_center_tables()
    schema.migrate_beauty_center_tables()

    center_columns = {row[1] for row in conn.execute("PRAGMA table_info(beauty_centers)")}
    event_columns = {row[1] for row in conn.execute("PRAGMA table_info(beauty_center_events)")}
    assert "instagram_url" in center_columns
    assert {"service_id", "campaign_key"} <= event_columns
    assert conn.execute("SELECT event_type FROM beauty_center_events WHERE id=1").fetchone()[0] == "view"
    conn.close()


def test_instagram_redirect_uses_center_saved_url_and_ignores_user_redirect_target(monkeypatch):
    app = create_app()
    seen = {}
    monkeypatch.setattr(center_routes, "get_center_by_slug", lambda slug: {
        "id": 12, "slug": slug, "owner_user_id": 999, "status": "published", "is_active": 1,
    })

    def fake_track(center_id, *, service_id=0, campaign_key="", suppress_tracking=False):
        seen.update(center_id=center_id, service_id=service_id, campaign_key=campaign_key)
        return "https://www.instagram.com/salon.example/"

    monkeypatch.setattr(center_routes, "track_instagram_click", fake_track)
    response = app.test_client().get(
        "/beauty-centers/salon-12/instagram?service_id=77&campaign=service_card&next=https://evil.example"
    )
    assert response.status_code == 302
    assert response.headers["Location"] == "https://www.instagram.com/salon.example/"
    assert seen == {"center_id": 12, "service_id": 77, "campaign_key": "service_card"}
    invalid = app.test_client().get("/beauty-centers/salon-12/instagram?service_id=not-an-id")
    assert invalid.status_code == 404
    assert seen["service_id"] == 77


def test_instagram_click_tracking_is_aggregate_and_service_scoped(monkeypatch):
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript("""
        CREATE TABLE beauty_centers(id INTEGER PRIMARY KEY,owner_user_id INTEGER,status TEXT,is_active INTEGER,listing_expires_at TEXT,instagram_url TEXT);
        CREATE TABLE beauty_center_services(id INTEGER PRIMARY KEY,center_id INTEGER,is_active INTEGER);
        CREATE TABLE beauty_center_events(id INTEGER PRIMARY KEY,center_id INTEGER,event_type TEXT,user_id INTEGER,created_at TEXT,service_id INTEGER,campaign_key TEXT);
        INSERT INTO beauty_centers VALUES (12,99,'published',1,'','@salon.example');
        INSERT INTO beauty_center_services VALUES (77,12,1);
    """)
    monkeypatch.setattr(center_services, "get_giso_db_conn", lambda: conn)

    target = center_services.track_instagram_click(12, service_id=77, campaign_key="service_card")
    assert target == "https://www.instagram.com/salon.example/"
    event = conn.execute("SELECT * FROM beauty_center_events").fetchone()
    assert event["center_id"] == 12
    assert event["event_type"] == "instagram_click"
    assert event["user_id"] == 0  # aggregate only; no visitor identity stored
    assert event["service_id"] == 77
    assert event["campaign_key"] == "service_card"
    assert center_services.instagram_click_count(12) == 1

    assert center_services.track_instagram_click(12, service_id=999) == ""
    assert conn.execute("SELECT COUNT(*) FROM beauty_center_events").fetchone()[0] == 1
    assert center_services.track_instagram_click(12, suppress_tracking=True) == target
    assert conn.execute("SELECT COUNT(*) FROM beauty_center_events").fetchone()[0] == 1
    conn.close()


def test_instagram_owner_field_cta_and_dashboard_click_metric_are_wired():
    owner_template = (ROOT / "giso/beauty_centers/templates/beauty_centers/owner_dashboard.html").read_text(encoding="utf-8")
    detail_template = (ROOT / "giso/beauty_centers/templates/beauty_centers/detail.html").read_text(encoding="utf-8")
    routes = (ROOT / "giso/beauty_centers/routes.py").read_text(encoding="utf-8")
    assert 'name="instagram_url"' in owner_template
    assert "ثبت کلیک ارجاعی" in owner_template
    assert "کلیک خروجی Instagram" in owner_template
    assert "center_instagram_redirect" in detail_template
    assert "service_id=(selected_service.id" in detail_template
    assert "def center_instagram_redirect" in routes
    assert '"instagram_url": request.form.get("instagram_url")' in routes
