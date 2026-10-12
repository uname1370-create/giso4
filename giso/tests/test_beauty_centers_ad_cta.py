# -*- coding: utf-8 -*-
"""Stage 1: clear, service-aware beauty-center discovery and booking CTAs."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MODULE = ROOT / "giso/beauty_centers"


def test_directory_card_has_one_clear_primary_action_and_preserves_context():
    card = (MODULE / "templates/beauty_centers/_card.html").read_text(encoding="utf-8")
    assert "مشاهده خدمات و رزرو" in card
    assert "_center_href" in card
    for key in ("service", "service_key", "final_design_id", "selected_style"):
        assert f"request.args.get('{key}')" in card
    assert "مرکز منتشرشده" in card
    assert "پاسخ‌گویی سریع" not in card
    assert "رزرو فعال" not in card


def test_selected_service_uses_server_resolved_name_price_duration_and_booking_id():
    detail = (MODULE / "templates/beauty_centers/detail.html").read_text(encoding="utf-8")
    routes = (MODULE / "routes.py").read_text(encoding="utf-8")
    assert "خدمت انتخاب‌شده: {{ selected_service.name }}" in detail
    assert "{{ selected_service.price_label }}" in detail
    assert "{{ selected_service.duration_label }}" in detail
    assert "service_id=selected_service.id" in detail
    assert "خدمت و قیمت از فهرست فعال همین مرکز خوانده شده است" in detail
    # A requested ID/key is only highlighted after resolving it against this center's services.
    assert "for svc in center_services" in routes
    assert "int(svc.get(\"id\") or 0) == int(selected_service_id)" in routes


def test_mobile_sticky_action_tracks_selected_service_without_breaking_legacy_anchor():
    detail = (MODULE / "templates/beauty_centers/detail.html").read_text(encoding="utf-8")
    assert "رزرو همین خدمت" in detail
    assert "مشاهده خدمات و رزرو" in detail
    assert 'href="#bcServices"' in detail
