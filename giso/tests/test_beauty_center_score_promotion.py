# -*- coding: utf-8 -*-
"""Contracts for deterministic center score and discount-service promotion."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_score_mapping_is_deterministic():
    from giso.beauty_centers.services import _feedback_label
    assert _feedback_label(5) == "بسیار خوب"
    assert _feedback_label(4) == "خوب"
    assert _feedback_label(3) == "متوسط"
    assert _feedback_label(1) == "نیازمند بهبود"


def test_feedback_ui_has_one_choice_and_no_comment():
    html = (ROOT / "giso/beauty_centers/templates/beauty_centers/chat.html").read_text(encoding="utf-8")
    assert 'name="overall_level"' in html
    assert 'name="comment"' not in html
    assert 'name="response_level"' not in html


def test_public_card_badge_priority_and_score():
    html = (ROOT / "giso/beauty_centers/templates/beauty_centers/_card.html").read_text(encoding="utf-8")
    selected = html.index("منتخب گیسو")
    featured = html.index("آگهی ویژه")
    discount = html.index("تخفیف خدمات")
    assert selected < featured < discount
    # Empty feedback dict must not resolve `.count` as an undefined attribute in Jinja.
    assert "center.feedback.get('count', 0) >= 3" in html
    assert "center.feedback.get('score100', 0)" in html


def test_discount_is_fixed_paid_package():
    owner = (ROOT / "giso/beauty_centers/templates/beauty_centers/owner_dashboard.html").read_text(encoding="utf-8")
    admin = (ROOT / "giso/beauty_centers/templates/beauty_centers/admin.html").read_text(encoding="utf-8")
    services = (ROOT / "giso/beauty_centers/services.py").read_text(encoding="utf-8")
    assert "purchase_nonces.discount" in owner
    assert 'value="discount"' in owner
    assert "bc-discount-form" not in owner
    for setting in ("beauty_discount_price", "beauty_discount_enabled"):
        assert setting in admin
    assert "مدت ثابت: ۲۴ ساعت" in admin
    assert "package_key=='discount'" in services


def test_promotion_cooldown_contracts():
    services = (ROOT / "giso/beauty_centers/services.py").read_text(encoding="utf-8")
    owner = (ROOT / "giso/beauty_centers/templates/beauty_centers/owner_dashboard.html").read_text(encoding="utf-8")
    assert "'+24 hours'" in services
    assert "package_key in ('featured','discount')" in services
    assert "remaining>10" in services
    assert "datetime(listing_expires_at,'+30 days')" in services
    assert "elif package_key=='discount':days=1" in services
    assert "'discount':'تخفیف خدمات'" in owner
    for key in ("bump", "featured", "discount", "renew"):
        assert f"promotion_availability.{key}.message" in owner
        assert f"promotion_availability.{key}.allowed" in owner


if __name__ == "__main__":
    test_score_mapping_is_deterministic()
    test_feedback_ui_has_one_choice_and_no_comment()
    test_public_card_badge_priority_and_score()
    test_discount_is_fixed_paid_package()
    test_promotion_cooldown_contracts()
