# -*- coding: utf-8 -*-
"""Security contract for Buti AI final-design to beauty-center reservations."""
from giso.app import create_app
from giso.beauty_centers.reservations import routes as reservation_routes


def test_mirror_reservation_link_requires_owned_design_and_matching_active_service(monkeypatch):
    app = create_app()
    center = {"id": 11}
    form = {
        "final_design_id": "55",
        "service_id": "77",
        "service_key": "eyebrow",
        "selected_style": "combination",
    }
    monkeypatch.setattr(
        "giso.buti_ai.services.get_final_design_by_id",
        lambda design_id, user_id: {
            "id": design_id,
            "service_type": "eyebrow",
            "candidate": {"service_type": "eyebrow"},
        } if (design_id, user_id) == (55, 42) else None,
    )
    monkeypatch.setattr(
        reservation_routes,
        "get_center_services",
        lambda center_id: [{"id": 77, "is_active": 1, "service_key": "brow"}],
    )

    with app.test_request_context("/beauty-centers/test/reserve"):
        assert reservation_routes._valid_mirror_reservation_link(center, 42, form)
        assert not reservation_routes._valid_mirror_reservation_link(center, 99, form)

        wrong_service_id = dict(form, service_id="78")
        assert not reservation_routes._valid_mirror_reservation_link(center, 42, wrong_service_id)

        wrong_mirror_key = dict(form, service_key="nail")
        assert not reservation_routes._valid_mirror_reservation_link(center, 42, wrong_mirror_key)

        inactive_service = dict(form)
        monkeypatch.setattr(
            reservation_routes,
            "get_center_services",
            lambda center_id: [{"id": 77, "is_active": 0, "service_key": "brow"}],
        )
        assert not reservation_routes._valid_mirror_reservation_link(center, 42, inactive_service)


def test_ordinary_reservation_without_mirror_design_remains_valid():
    app = create_app()
    with app.test_request_context("/beauty-centers/test/reserve"):
        assert reservation_routes._valid_mirror_reservation_link(
            {"id": 11}, 42, {"service_id": "77"}
        )


def test_center_service_preview_mapping_and_return_target(monkeypatch):
    from flask import session
    from giso.buti_ai import routes as buti_routes

    assert buti_routes._mirror_key_for_center_service("brow") == "eyebrow"
    assert buti_routes._mirror_key_for_center_service("nail") == "nail"
    assert buti_routes._mirror_key_for_center_service("unknown") == ""

    app = create_app()
    monkeypatch.setattr(buti_routes, "_safe_current_user_id", lambda: 42)
    monkeypatch.setattr(buti_routes, "get_final_design_by_id", lambda design_id, user_id: {"id": design_id} if (design_id, user_id) == (55, 42) else None)
    monkeypatch.setattr("giso.beauty_centers.services.get_center_by_slug", lambda slug: {
        "id": 11, "slug": slug, "name": "سالن تست", "status": "published", "is_active": 1,
    })
    monkeypatch.setattr("giso.beauty_centers.pricing.services.get_center_services", lambda center_id: [
        {"id": 77, "name": "خدمت ابرو", "service_key": "brow", "is_active": 1},
    ])

    with app.test_request_context("/analysis/mirror/eyebrow/final"):
        session[buti_routes.CENTER_MIRROR_BOOKING_SESSION_KEY] = {
            "user_id": 42,
            "center_id": 11,
            "center_slug": "salon-test",
            "service_id": 77,
            "center_service_key": "brow",
            "mirror_service_key": "eyebrow",
            "created_at": int(buti_routes.time.time()),
        }
        result = buti_routes._center_mirror_booking_for_candidate(
            "eyebrow", {"final_design_id": 55}
        )
        assert result == {
            "center_id": 11,
            "center_name": "سالن تست",
            "center_slug": "salon-test",
            "service_id": 77,
            "service_name": "خدمت ابرو",
        }
