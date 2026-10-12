# -*- coding: utf-8 -*-
"""Stage 6: fair, same-city/service-key, aggregate price comparisons."""
import sqlite3
from pathlib import Path

from giso.beauty_centers.pricing import services as pricing

ROOT = Path(__file__).resolve().parents[2]


def _db(monkeypatch):
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(
        """
        CREATE TABLE beauty_centers (
            id INTEGER PRIMARY KEY, status TEXT NOT NULL, is_active INTEGER NOT NULL,
            city TEXT NOT NULL
        );
        CREATE TABLE beauty_center_services (
            id INTEGER PRIMARY KEY, center_id INTEGER NOT NULL, name TEXT NOT NULL,
            service_key TEXT NOT NULL DEFAULT '', is_active INTEGER NOT NULL DEFAULT 1,
            price_min INTEGER NOT NULL DEFAULT 0, price_max INTEGER NOT NULL DEFAULT 0
        );
        """
    )
    monkeypatch.setattr(pricing, "get_giso_db_conn", lambda: conn)
    return conn


def _center(conn, center_id, city="مشهد", status="published", active=1):
    conn.execute(
        "INSERT INTO beauty_centers(id,status,is_active,city) VALUES(?,?,?,?)",
        (center_id, status, active, city),
    )


def _offer(conn, center_id, key="hair_color", name="رنگ مو", low=100, high=200, active=1):
    conn.execute(
        "INSERT INTO beauty_center_services(center_id,name,service_key,is_active,price_min,price_max) "
        "VALUES(?,?,?,?,?,?)",
        (center_id, name, key, active, low, high),
    )


def test_benchmark_uses_same_city_key_active_published_peers_and_excludes_subject(monkeypatch):
    conn = _db(monkeypatch)
    _center(conn, 1)  # center whose own page is being viewed
    _offer(conn, 1, low=900, high=1200)
    ranges = [(100, 200), (200, 300), (300, 400), (400, 500), (500, 600)]
    for center_id, (low, high) in enumerate(ranges, start=2):
        _center(conn, center_id)
        _offer(conn, center_id, low=low, high=high)
    # A duplicate offer still counts only as one comparison center.
    _offer(conn, 2, low=150, high=250)
    # Ineligible peers: different city, different key, inactive service/center, or unpublished.
    _center(conn, 20, city="تهران"); _offer(conn, 20, low=1, high=2)
    _center(conn, 21); _offer(conn, 21, key="keratin", name="کراتین", low=1, high=2)
    _center(conn, 22, active=0); _offer(conn, 22, low=1, high=2)
    _center(conn, 23, status="pending_review"); _offer(conn, 23, low=1, high=2)
    _center(conn, 24); _offer(conn, 24, active=0, low=1, high=2)
    conn.commit()

    result = pricing.get_service_price_benchmarks(
        "مشهد", ["hair_color"], exclude_center_id=1, min_centers=5
    )["hair_color"]
    assert result["available"] is True
    assert result["provider_count"] == 5
    assert result["median_min"] == 300
    assert result["median_max"] == 400
    assert result["observed_min"] == 100
    assert result["observed_max"] == 600
    assert result["service_name"] == "رنگ مو"
    assert result["calculated_at"]
    # Benchmarking is read-only: the viewed salon's offered range stays unchanged.
    own = conn.execute(
        "SELECT price_min,price_max FROM beauty_center_services WHERE center_id=1"
    ).fetchone()
    assert tuple(own) == (900, 1200)


def test_insufficient_sample_hides_counts_and_price_statistics(monkeypatch):
    conn = _db(monkeypatch)
    _center(conn, 1, city="کاشان")
    _center(conn, 2, city="كاشان")  # Arabic kaf is normalized to Persian kaf.
    _offer(conn, 2, low=300, high=500)
    conn.commit()

    result = pricing.get_service_price_benchmarks(
        "کاشان", ["hair_color"], exclude_center_id=1, min_centers=2
    )["hair_color"]
    assert result["available"] is False
    assert result["min_centers"] == 2
    assert "provider_count" not in result
    assert "median_min" not in result


def test_sample_threshold_is_configurable_bounded_and_invalid_values_fall_back(monkeypatch):
    conn = _db(monkeypatch)
    for center_id in (1, 2):
        _center(conn, center_id, city="شیراز")
        _offer(conn, center_id, low=500, high=700)
    conn.commit()

    monkeypatch.setenv("BEAUTY_PRICE_BENCHMARK_MIN_CENTERS", "1")
    assert pricing.get_price_benchmark_min_centers() == 1
    assert pricing.get_service_price_benchmarks("شیراز")["hair_color"]["available"] is True
    monkeypatch.setenv("BEAUTY_PRICE_BENCHMARK_MIN_CENTERS", "101")
    assert pricing.get_price_benchmark_min_centers() == 100
    monkeypatch.setenv("BEAUTY_PRICE_BENCHMARK_MIN_CENTERS", "invalid")
    assert pricing.get_price_benchmark_min_centers() == 5


def test_overview_limit_keeps_available_keys_and_blank_city_or_key_fails_closed(monkeypatch):
    conn = _db(monkeypatch)
    # Alpha is alphabetically first but lacks the default five peer centers.
    for center_id in range(1, 7):
        _center(conn, center_id, city="تبریز")
        _offer(conn, center_id, key="zeta", name="خدمت زتا", low=100, high=150)
    _center(conn, 10, city="تبریز")
    _offer(conn, 10, key="alpha", name="خدمت آلفا", low=100, high=150)
    conn.commit()

    result = pricing.get_service_price_benchmarks("تبریز", limit=1)
    assert list(result) == ["zeta"]
    assert pricing.get_service_price_benchmarks("", ["zeta"]) == {}
    assert pricing.get_service_price_benchmarks("تبریز", [""]) == {}


def test_templates_keep_price_benchmark_separate_from_owner_price_and_require_same_city():
    listing = (ROOT / "giso/beauty_centers/templates/beauty_centers/list.html").read_text(encoding="utf-8")
    detail = (ROOT / "giso/beauty_centers/templates/beauty_centers/detail.html").read_text(encoding="utf-8")
    assert "برای مقایسهٔ منصفانه، شهر را در فیلترهای زیر انتخاب کنید" in listing
    assert "provider_count" in listing and "calculated_at" in listing
    assert "price_benchmarks.get(svc_key)" in detail
    assert "median_min" in detail and "median_max" in detail
    assert "price_label" in detail and "duration_label" in detail
    assert "قیمت نهایی" in detail


def _detail_response(monkeypatch, benchmark):
    from giso.app import create_app
    from giso.beauty_centers import routes as center_routes

    center = {
        "id": 501, "slug": "stage6-salon", "name": "سالن نمونه", "status": "published",
        "is_active": 1, "owner_user_id": 987654, "city": "مشهد", "region": "سجاد",
        "description": "", "category_label": "مو", "type_label": "سالن زیبایی",
        "price_level_label": "متعادل", "starting_price": 900000,
        "instagram_url": "", "is_featured": 0, "promotion_active": 0,
        "views_count": 0, "contact_clicks": 0, "address_summary": "",
        "business_phone": "", "contact_time": "", "display_phone_choice": "",
        "salon_phone": "", "service_labels": [],
    }
    service = {
        "id": 77, "center_id": 501, "name": "رنگ مو", "service_key": "hair_color",
        "is_active": 1, "is_featured_service": 0, "category": "مو", "description": "",
        "price_min": 900000, "price_max": 1200000,
        "price_label": "از ۹۰۰٬۰۰۰ تا ۱٬۲۰۰٬۰۰۰ تومان", "duration_label": "۲ ساعت",
    }
    calls = []
    monkeypatch.setattr(center_routes, "get_center_by_slug", lambda _slug: dict(center))
    monkeypatch.setattr(center_routes, "increment_view", lambda _center_id: None)
    monkeypatch.setattr(center_routes, "_center_services_for_display", lambda _center_id: [dict(service)])
    monkeypatch.setattr(center_routes, "center_feedback_summary", lambda _center_id: {})
    monkeypatch.setattr(center_routes, "_center_hours_for_display", lambda _center_id: [])
    monkeypatch.setattr(
        center_routes, "get_service_price_benchmarks",
        lambda city, service_keys, **kwargs: calls.append((city, service_keys, kwargs)) or {"hair_color": benchmark},
    )
    monkeypatch.setattr(
        center_routes, "get_giso_db_conn",
        lambda: sqlite3.connect(":memory:"),
    )
    app = create_app()
    with app.test_client() as client:
        response = client.get("/beauty-centers/stage6-salon")
    return response, calls


def test_detail_renders_same_city_service_benchmark_sample_date_and_keeps_own_quote(monkeypatch):
    benchmark = {
        "service_key": "hair_color", "available": True, "min_centers": 5,
        "provider_count": 6, "median_min": 700000, "median_max": 1000000,
        "observed_min": 500000, "observed_max": 1500000,
        "calculated_at": "2026-10-12 20:00",
    }
    response, calls = _detail_response(monkeypatch, benchmark)
    body = response.get_data(as_text=True)
    assert response.status_code == 200
    assert "میانهٔ بازهٔ اعلامی" in body
    assert "2026-10-12 20:00" in body
    assert "۶ مرکز دیگر" in body or "6 مرکز دیگر" in body
    assert "از ۹۰۰٬۰۰۰ تا ۱٬۲۰۰٬۰۰۰ تومان" in body
    assert "۲ ساعت" in body
    assert calls and calls[0][0] == "مشهد"
    assert calls[0][1] == ["hair_color"]
    assert calls[0][2]["exclude_center_id"] == 501


def test_detail_does_not_render_benchmark_values_below_threshold(monkeypatch):
    benchmark = {
        "service_key": "hair_color", "available": False, "min_centers": 5,
        "calculated_at": "2026-10-12 20:00",
    }
    response, _calls = _detail_response(monkeypatch, benchmark)
    body = response.get_data(as_text=True)
    assert response.status_code == 200
    assert "هنوز دادهٔ کافی از مراکز دیگر وجود ندارد" in body
    assert "میانهٔ بازهٔ اعلامی" not in body
    assert "۹۰۰٬۰۰۰" in body


def test_single_bound_fixed_quotes_are_compared_as_point_prices(monkeypatch):
    conn = _db(monkeypatch)
    for center_id in (1, 2):
        _center(conn, center_id, city="کرمان")
    _offer(conn, 1, low=0, high=500000)
    _offer(conn, 2, low=600000, high=0)
    conn.commit()

    result = pricing.get_service_price_benchmarks("کرمان", ["hair_color"], min_centers=2)["hair_color"]
    assert result["available"] is True
    assert result["median_min"] == 550000
    assert result["median_max"] == 550000
    assert result["observed_min"] == 500000
    assert result["observed_max"] == 600000
