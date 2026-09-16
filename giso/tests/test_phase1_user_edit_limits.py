# -*- coding: utf-8 -*-
"""Phase 1: user-owned edit limits and safe withdrawal."""
from werkzeug.security import generate_password_hash

from giso.app import create_app
from giso.models import db, User, HairOrder, HairListing, BuyerProfile, BuyerOffer

PHONE = "+989120008877"


def _client(app):
    client = app.test_client()
    with client.session_transaction() as session:
        session["_user_id"] = PHONE
        session["_fresh"] = True
        session["giso_csrf_token"] = "phase1-token"
    return client


def _post(client, url, data):
    return client.post(url, data={"csrf_token": "phase1-token", **data}, follow_redirects=False)


def test_two_edit_limits_and_safe_hair_withdrawal():
    app = create_app()
    with app.app_context():
        old = User.query.filter_by(phone=PHONE).first()
        if old:
            BuyerOffer.query.filter_by(buyer_user_id=old.id).delete()
            HairListing.query.filter_by(seller_user_id=old.id).delete()
            BuyerProfile.query.filter_by(user_id=old.id).delete()
            HairOrder.query.filter_by(user_id=old.id).delete()
            db.session.delete(old); db.session.commit()
        user = User(phone=PHONE, name="کاربر ویرایش", password_hash=generate_password_hash("pass"))
        db.session.add(user); db.session.flush()
        hair = HairOrder(user_id=user.id, phone=PHONE, photo_path="uploads/test.jpg", length_cm=40, status="pending")
        listing = HairListing(slug="phase-one-edit", seller_user_id=user.id, photo_path="uploads/test.jpg", length_cm=40, seller_asking_price=1000000, status="published", deleted_at="")
        db.session.add_all([hair, listing]); db.session.commit()
        user_id, hair_id, listing_id = user.id, hair.id, listing.id
    client = _client(app)
    for length in (41, 42):
        assert _post(client, f"/dashboard/hair-sale/{hair_id}/edit", {"length_cm": str(length)}).status_code == 302
    assert _post(client, f"/dashboard/hair-sale/{hair_id}/edit", {"length_cm": "43"}).status_code == 302
    with app.app_context():
        row = db.session.get(HairOrder, hair_id)
        assert row.length_cm == 42 and row.user_edit_count == 2
    for price in (1100000, 1200000):
        assert _post(client, f"/marketplace/seller/listings/{listing_id}/status", {"action":"edit", "seller_asking_price":str(price), "city":"مشهد"}).status_code == 302
    _post(client, f"/marketplace/seller/listings/{listing_id}/status", {"action":"edit", "seller_asking_price":"1300000", "city":"مشهد"})
    with app.app_context():
        row = db.session.get(HairListing, listing_id)
        assert row.seller_asking_price == 1200000 and row.edit_count == 2
        # A fresh pending order can be withdrawn without deleting its audit row.
        row = db.session.get(HairOrder, hair_id); row.status="pending"; db.session.commit()
    _post(client, f"/dashboard/hair-sale/{hair_id}/withdraw", {})
    with app.app_context():
        assert db.session.get(HairOrder, hair_id).status == "withdrawn"
        HairListing.query.filter_by(id=listing_id).delete(); HairOrder.query.filter_by(id=hair_id).delete(); User.query.filter_by(id=user_id).delete(); db.session.commit()


def test_buyer_request_two_edits_then_locks():
    app=create_app()
    with app.app_context():
        user=User.query.filter_by(phone=PHONE).first()
        if not user:
            user=User(phone=PHONE,name="خریدار",password_hash=generate_password_hash("pass"));db.session.add(user);db.session.commit()
        user_id=user.id
        BuyerProfile.query.filter_by(user_id=user_id).delete();db.session.commit()
    client=_client(app)
    payload={"buyer_name":"خریدار تست","buyer_phone":PHONE,"buyer_city":"مشهد","buyer_type":"personal","buyer_description":"نیاز تست","budget_min":"1000000","budget_max":"3000000","buyer_terms":"1"}
    _post(client,"/hair-sale/buyer-request",payload)  # creation
    payload["buyer_description"]="ویرایش اول";_post(client,"/hair-sale/buyer-request",payload)
    payload["buyer_description"]="ویرایش دوم";_post(client,"/hair-sale/buyer-request",payload)
    payload["buyer_description"]="نباید ذخیره شود";_post(client,"/hair-sale/buyer-request",payload)
    with app.app_context():
        profile=BuyerProfile.query.filter_by(user_id=user_id).first()
        assert profile.edit_count==2 and profile.request_description=="ویرایش دوم"
        assert profile.budget_min==1000000 and profile.budget_max==3000000
        db.session.delete(profile);User.query.filter_by(id=user_id).delete();db.session.commit()
