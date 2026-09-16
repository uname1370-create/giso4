#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""اعتبار مصرفی اولیهٔ رایگان: تنظیم سوپرادمین + اعطای ایدمپوتنت + کارت‌های هدر."""
import os, sys, time, sqlite3
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if BASE_DIR not in sys.path:
    sys.path.append(BASE_DIR)
from giso.app import create_app  # noqa: E402
from giso.models import db, User  # noqa: E402
from giso.base import normalize_phone  # noqa: E402
from giso.wallet_core import grant_initial_spend_credit, get_wallet_balances, get_financial_settings  # noqa: E402
from giso_admin import set_giso_config  # noqa: E402

PHONE = normalize_phone("09127778888")
SUPER = normalize_phone("09156012931")


def _cleanup(app):
    with app.app_context():
        User.query.filter_by(phone=PHONE).delete(synchronize_session=False)
        db.session.commit()


def test_initial_spend_credit_grant_idempotent_and_visible():
    app = create_app(); client = app.test_client()
    _cleanup(app)
    set_giso_config("wallet_initial_spend_credit", "2500")
    try:
        with app.app_context():
            db.session.add(User(phone=PHONE, password_hash="h", name="تست اعتبار"))
            db.session.commit()
            uid = User.query.filter_by(phone=PHONE).first().id
        assert get_financial_settings()["initial_spend_credit"] == 2500
        assert grant_initial_spend_credit(uid) is True, "بار اول باید اعطا کند"
        assert grant_initial_spend_credit(uid) is False, "بار دوم باید ایدمپوتنت باشد"
        bal = get_wallet_balances(uid)
        assert bal.get("spend") == 2500, f"اعتبار مصرفی باید ۲۵۰ باشد: {bal}"
        with client.session_transaction() as s:
            s['_user_id'] = PHONE
            s['user_panel_verified_phone'] = PHONE
            s['user_panel_verified_until'] = int(time.time()) + 1800
        r = client.get("/user/wallet")
        html = r.get_data(as_text=True)
        if r.status_code == 200:
            assert "pu-chip-spend" in html and "pu-chip-cash" in html, "دو کارت اعتبار در هدر لازم است"
        print("PASS  اعتبار مصرفی اولیه: تنظیم + اعطای یک‌باره + کارت‌های هدر")
    finally:
        set_giso_config("wallet_initial_spend_credit", "0")
        _cleanup(app)
