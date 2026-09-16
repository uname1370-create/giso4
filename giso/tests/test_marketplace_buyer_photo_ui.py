# -*- coding: utf-8 -*-
"""Regression coverage for buyer routing and Marketplace media/layout contracts."""
from pathlib import Path

from giso.app import create_app

ROOT = Path(__file__).resolve().parents[2]


def test_guest_buyer_request_redirects_to_login_with_return_path():
    app = create_app()
    client = app.test_client()
    response = client.get("/dashboard/hair/buyer-request", follow_redirects=False)
    assert response.status_code == 302
    location = response.headers["Location"]
    assert "/login" in location
    assert "next=" in location
    assert "buyer-request" in location

    legacy = client.get("/dashboard/marketplace?tab=buyer-request", follow_redirects=False)
    assert legacy.status_code == 302
    assert "tab%3Dbuyer-request" in legacy.headers["Location"] or "tab=buyer-request" in legacy.headers["Location"]


def test_authenticated_member_reaches_buyer_request_page():
    from werkzeug.security import generate_password_hash
    from giso.models import BuyerProfile, User, db

    app = create_app()
    phone = "+989120009991"
    with app.app_context():
        existing = User.query.filter_by(phone=phone).first()
        if existing:
            BuyerProfile.query.filter_by(user_id=existing.id).delete()
            db.session.delete(existing)
            db.session.commit()
        user = User(phone=phone, name="buyer route test", password_hash=generate_password_hash("test-pass"))
        db.session.add(user)
        db.session.commit()
        user_id = user.id
    try:
        client = app.test_client()
        with client.session_transaction() as session:
            session["_user_id"] = phone
            session["_fresh"] = True
        response = client.get("/dashboard/hair/buyer-request", follow_redirects=False)
        assert response.status_code == 200
        assert "ثبت درخواست خرید مو" in response.get_data(as_text=True)
    finally:
        with app.app_context():
            BuyerProfile.query.filter_by(user_id=user_id).delete()
            User.query.filter_by(id=user_id).delete()
            db.session.commit()


def test_marketplace_templates_use_compatibility_media_route():
    for relative in (
        "giso/templates/marketplace_list.html",
        "giso/templates/marketplace_detail.html",
        "giso/templates/marketplace_chat.html",
        "giso/panel_user/templates/user_modules/marketplace.html",
        "giso/panel_user/templates/user_modules/_buyer_offers_tab.html",
        "giso/panel_user/templates/user_modules/_buyer_conversations_tab.html",
    ):
        source = (ROOT / relative).read_text(encoding="utf-8")
        assert "marketplace.listing_photo" in source, relative


def test_listing_media_route_normalizes_legacy_static_prefix():
    from werkzeug.security import generate_password_hash
    from giso.models import HairListing, User, db

    app = create_app()
    phone = "+989120009992"
    with app.app_context():
        user = User(phone=phone, name="media route test", password_hash=generate_password_hash("test-pass"))
        db.session.add(user)
        db.session.flush()
        listing = HairListing(
            slug="media-route-test", seller_user_id=user.id,
            photo_path="static/uploads/hair_20260810140337.jpg", hair_type="raw",
            length_cm=40, seller_asking_price=1000000, status="published", deleted_at="",
        )
        db.session.add(listing)
        db.session.commit()
        listing_id, user_id = listing.id, user.id
    try:
        response = app.test_client().get(f"/marketplace/media/{listing_id}")
        assert response.status_code == 200
        assert response.mimetype in ("image/jpeg", "image/jpg")
    finally:
        with app.app_context():
            HairListing.query.filter_by(id=listing_id).delete()
            User.query.filter_by(id=user_id).delete()
            db.session.commit()


def test_detail_media_and_listing_cards_have_bounded_final_css():
    # §17: marketplace.css مینیفای شد؛ assertions باید نسبت به فاصله مستقل باشند
    import re as _re
    css = (ROOT / "giso/static/css/marketplace.css").read_text(encoding="utf-8")
    flat = _re.sub(r"\s+", " ", css)
    assert ".giso-market-detail-page .giso-market-detail-main" in flat
    assert ".giso-market-list-page .mkt-card-media" in flat
    props = flat.replace(" ", "")
    for prop in ("flex-direction:column", "max-height:360px",
                 "object-fit:cover!important", "aspect-ratio:1/1"):
        assert prop in props, prop


def test_marketplace_admin_bot_actions_remain_wired():
    source = (ROOT / "giso/bot_market_admin.py").read_text(encoding="utf-8")
    for callback in ("mkt_act|{listing_id}|review", "mkt_act|{listing_id}|publish", "mkt_act|{listing_id}|reject"):
        assert callback in source
    assert "notify_listing_status" in source
