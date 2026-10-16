# -*- coding: utf-8 -*-
"""Stage 5 smart-analytics tests: dynamic services and aggregate-only metrics."""
from contextlib import contextmanager
import sqlite3
from pathlib import Path

from giso.beauty_centers import services as bc_services
from giso.beauty_centers.reservations import routes as reservation_routes
from giso.app import create_app

ROOT = Path(__file__).resolve().parents[2]


def _db(monkeypatch):
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript("""
        CREATE TABLE beauty_centers (
            id INTEGER PRIMARY KEY, status TEXT, is_active INTEGER,
            listing_expires_at TEXT DEFAULT '', owner_user_id INTEGER DEFAULT 0, city TEXT DEFAULT ''
        );
        CREATE TABLE beauty_center_services (
            id INTEGER PRIMARY KEY, center_id INTEGER, name TEXT, service_key TEXT DEFAULT '',
            is_active INTEGER DEFAULT 1, sort_order INTEGER DEFAULT 0
        );
        CREATE TABLE beauty_center_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT, center_id INTEGER, event_type TEXT,
            user_id INTEGER DEFAULT 0, created_at TEXT, service_id INTEGER DEFAULT 0,
            campaign_key TEXT DEFAULT ''
        );
        CREATE TABLE beauty_center_reservations (
            id INTEGER PRIMARY KEY AUTOINCREMENT, center_id INTEGER, service_id INTEGER,
            status TEXT, created_at TEXT
        );
        INSERT INTO beauty_centers(id,status,is_active,listing_expires_at,owner_user_id,city)
            VALUES (1,'published',1,'',11,'مشهد'),(2,'published',1,'',22,'تهران'),(3,'paused',1,'',33,'مشهد');
    """)

    @contextmanager
    def fake_connection():
        yield conn

    monkeypatch.setattr(bc_services, "get_giso_db_conn", fake_connection)
    return conn


def test_public_demand_follows_active_inventory_and_suppresses_small_samples(monkeypatch):
    conn = _db(monkeypatch)
    conn.executescript("""
        INSERT INTO beauty_center_services(id,center_id,name,service_key,is_active) VALUES
            (101,1,'خدمت آزمایشی تازه','',1),
            (201,2,'خدمت آزمایشی تازه','',1),
            (301,3,'خدمت مرکز متوقف','',1),
            (102,1,'خدمت غیرفعال','',0);
        INSERT INTO beauty_center_events(center_id,event_type,created_at,service_id) VALUES
            (1,'booking_start',datetime('now','localtime','-1 day'),101),
            (2,'booking_start',datetime('now','localtime','-2 day'),201),
            (1,'booking_start',datetime('now','localtime','-31 day'),101),
            (1,'view',datetime('now','localtime'),101);
    """)

    rows = bc_services.public_service_demand(days=30, limit=10)
    assert len(rows) == 1
    assert rows[0]["service_name"] == "خدمت آزمایشی تازه"
    assert rows[0]["provider_count"] == 2
    assert rows[0]["booking_starts"] == 2
    assert rows[0]["has_reliable_sample"] is False
    assert bc_services.public_service_demand(days=30, limit=10, min_sample=2)[0]["has_reliable_sample"] is True


def test_public_demand_groups_by_live_service_key_and_hides_inactive_centers(monkeypatch):
    conn = _db(monkeypatch)
    conn.executescript("""
        INSERT INTO beauty_center_services(id,center_id,name,service_key,is_active) VALUES
            (110,1,'نام اول','future_key',1),(210,2,'نام دوم','future_key',1),
            (310,3,'نام پنهان','private_key',1);
        INSERT INTO beauty_center_events(center_id,event_type,created_at,service_id)
            VALUES (1,'booking_start',datetime('now','localtime'),110),
                   (2,'booking_start',datetime('now','localtime'),210);
    """)
    rows = bc_services.public_service_demand(days=30, limit=10)
    assert len(rows) == 1
    assert rows[0]["demand_key"] == "key:future_key"
    assert rows[0]["provider_count"] == 2
    assert rows[0]["booking_starts"] == 2


def test_admin_service_demand_can_group_by_city_and_current_service(monkeypatch):
    conn = _db(monkeypatch)
    conn.executescript("""
        INSERT INTO beauty_center_services(id,center_id,name,service_key,is_active) VALUES
            (110,1,'خدمت جدید','future_key',1),(210,2,'خدمت جدید','future_key',1);
        INSERT INTO beauty_center_events(center_id,event_type,created_at,service_id)
            VALUES (1,'booking_start',datetime('now','localtime'),110),
                   (2,'booking_start',datetime('now','localtime'),210);
    """)
    rows = bc_services.public_service_demand(days=30, limit=10, by_city=True)
    assert {(row["city"], row["service_name"], row["booking_starts"]) for row in rows} == {
        ("مشهد", "خدمت جدید", 1), ("تهران", "خدمت جدید", 1),
    }


def test_booking_start_requires_published_center_and_active_owned_service(monkeypatch):
    conn = _db(monkeypatch)
    conn.execute("INSERT INTO beauty_center_services(id,center_id,name,is_active) VALUES (101,1,'خدمت',1),(102,2,'خدمت دیگر',1),(103,1,'غیرفعال',0)")
    assert bc_services.track_booking_start(1, 101, campaign_key="mirror") is True
    assert bc_services.track_booking_start(1, 102, campaign_key="mirror") is False
    assert bc_services.track_booking_start(1, 103, campaign_key="mirror") is False
    assert bc_services.track_booking_start(3, 101) is False
    assert conn.execute("SELECT COUNT(*) FROM beauty_center_events WHERE event_type='booking_start'").fetchone()[0] == 1
    event = conn.execute("SELECT user_id,service_id,campaign_key FROM beauty_center_events").fetchone()
    assert tuple(event) == (0, 101, "mirror")


def test_owner_analytics_are_scoped_to_one_center_and_include_reservation_states(monkeypatch):
    conn = _db(monkeypatch)
    conn.executescript("""
        INSERT INTO beauty_center_services(id,center_id,name,is_active) VALUES (101,1,'خدمت الف',1),(201,2,'خدمت ب',1);
        INSERT INTO beauty_center_events(center_id,event_type,created_at,service_id) VALUES
            (1,'view',datetime('now','localtime'),0),
            (1,'booking_start',datetime('now','localtime'),101),
            (2,'view',datetime('now','localtime'),0),
            (2,'booking_start',datetime('now','localtime'),201),
            (1,'view',datetime('now','localtime','-31 day'),0);
        INSERT INTO beauty_center_reservations(center_id,service_id,status,created_at) VALUES
            (1,101,'pending',datetime('now','localtime')),
            (1,101,'confirmed',datetime('now','localtime')),
            (2,201,'completed',datetime('now','localtime'));
    """)
    data = bc_services.center_smart_analytics(1, 30)
    assert data["events"]["view"] == 1
    assert data["events"]["booking_start"] == 1
    assert data["reservations"] == {
        "total": 2, "pending": 1, "confirmed": 1, "completed": 0,
        "cancelled_user": 0, "cancelled_center": 0,
    }
    assert data["services"] == [{
        "id": 101, "name": "خدمت الف", "service_key": "", "is_active": 1,
        "booking_starts": 1, "reservation_requests": 2, "confirmed": 1, "completed": 0,
    }]


def test_booking_form_start_is_deduplicated_in_session_and_owner_is_excluded(monkeypatch):
    app = create_app()
    calls = []
    monkeypatch.setattr(reservation_routes, "track_booking_start", lambda center_id, service_id, **kw: calls.append((center_id, service_id, kw)) or True)
    with app.test_request_context("/beauty-centers/sample/reserve"):
        assert reservation_routes._record_booking_start_once(
            {"id": 1, "owner_user_id": 9}, {"id": 101}, from_mirror=True
        ) is True
        assert reservation_routes._record_booking_start_once(
            {"id": 1, "owner_user_id": 9}, {"id": 101}, from_mirror=True
        ) is False
        assert len(calls) == 1
        assert calls[0][2]["campaign_key"] == "mirror"
    with app.test_request_context("/beauty-centers/sample/reserve"):
        # Owner comparison is tested by a lightweight proxy.
        monkeypatch.setattr(reservation_routes, "current_user", type("Owner", (), {"id": 9})())
        assert reservation_routes._record_booking_start_once(
            {"id": 1, "owner_user_id": 9}, {"id": 101}
        ) is False


def test_public_and_owner_templates_explain_dynamic_and_non_unique_metrics():
    public = (ROOT / "giso/beauty_centers/templates/beauty_centers/list.html").read_text(encoding="utf-8") + (ROOT / "giso/beauty_centers/templates/beauty_centers/_list_content.html").read_text(encoding="utf-8")
    owner = (ROOT / "giso/beauty_centers/templates/beauty_centers/owner_dashboard.html").read_text(encoding="utf-8")
    assert "for item in service_demand" in public
    assert "تعداد افراد یکتا" in public
    assert "for item in center_analytics.services" in owner
    assert "آمار هوشمند" in owner
    assert "tab='analytics'" in owner
    demand_block = public.split('<section class="bc-demand"', 1)[1].split("</section>", 1)[0]
    assert "ابرو" not in demand_block and "لب" not in demand_block and "مو" not in demand_block
    assert "در حال حاضر خدمت فعالی برای نمایش تقاضا ثبت نشده است" in demand_block
