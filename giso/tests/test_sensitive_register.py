#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
تست ثبت‌نام شماره‌های حساس با کد ربات

۱) ثبت‌نام شماره سوپرادمین بدون کد کامل نمی‌شود و فقط کد ربات صادر می‌شود
۲) ثبت‌نام شماره سوپرادمین با کد صحیح کامل می‌شود
۳) ثبت‌نام شماره ادمین ثبت‌شده هم همین قاعده را دارد
"""
import os
import sys
from unittest.mock import patch

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if BASE_DIR not in sys.path:
    sys.path.append(BASE_DIR)

from giso.app import create_app  # noqa: E402
from giso.models import db, User  # noqa: E402
from giso.base import normalize_phone  # noqa: E402
from giso.config import SUPERADMIN_BALE_ID  # noqa: E402
from bot_edu.giso_admin import add_giso_admin  # noqa: E402

SUPER_PHONE = normalize_phone("09156012931")
ADMIN_PHONE = normalize_phone("09127778888")
ADMIN_BALE_ID = "55667788"
FIXED_CODE = "246810"


def _cleanup(app):
    with app.app_context():
        for phone in (SUPER_PHONE, ADMIN_PHONE):
            User.query.filter_by(phone=phone).delete(synchronize_session=False)
        db.session.commit()
    import sqlite3
    bot_db = os.path.join(BASE_DIR, "bot_edu", "data", "bot.db")
    conn = sqlite3.connect(bot_db)
    try:
        conn.execute("DELETE FROM giso_admins WHERE phone=? OR bale_id=?", (ADMIN_PHONE, ADMIN_BALE_ID))
        conn.commit()
    finally:
        conn.close()


def _csrf(client, path="/register"):
    import re as _re
    m = _re.search(r'name="csrf_token" value="([^"]+)"', client.get(path).get_data(as_text=True))
    return m.group(1) if m else ""


def _register_payload(phone, code=""):
    return {
        "phone": phone,
        "password": "secret-pass1",
        "password2": "secret-pass1",
        "security_question": "نام شهر محل تولد شما چیست؟",
        "security_answer": "تهران",
        "site_terms_accepted": "1",
        "bot_code": code,
    }


def test_super_sensitive_register_requires_bot_code():
    app = create_app()
    client = app.test_client()
    _cleanup(app)

    with patch('giso.app._send_admin_panel_code_to_bot', return_value=(True, 'کد ارسال شد')), \
         patch('giso.app._generate_admin_panel_code', return_value=FIXED_CODE):
        first = client.post('/register', data={**_register_payload(SUPER_PHONE), 'csrf_token': _csrf(client)}, follow_redirects=True)
        html = first.get_data(as_text=True)
        assert 'کد تأیید ربات' in html
        with app.app_context():
            assert User.query.filter_by(phone=SUPER_PHONE).first() is None

        second = client.post('/register', data={**_register_payload(SUPER_PHONE, code=FIXED_CODE), 'action': 'verify_sensitive', 'csrf_token': _csrf(client)}, follow_redirects=False)
        assert second.status_code == 302
        with app.app_context():
            assert User.query.filter_by(phone=SUPER_PHONE).first() is not None
    print('PASS  ثبت‌نام شماره سوپرادمین فقط بعد از کد ربات کامل می‌شود')


def test_admin_sensitive_register_requires_bot_code():
    app = create_app()
    client = app.test_client()
    _cleanup(app)
    add_giso_admin(phone=ADMIN_PHONE, bale_id=ADMIN_BALE_ID, added_by=SUPERADMIN_BALE_ID)

    with patch('giso.app._send_admin_panel_code_to_bot', return_value=(True, 'کد ارسال شد')), \
         patch('giso.app._generate_admin_panel_code', return_value=FIXED_CODE):
        first = client.post('/register', data={**_register_payload(ADMIN_PHONE), 'csrf_token': _csrf(client)}, follow_redirects=True)
        html = first.get_data(as_text=True)
        assert 'کد تأیید ربات' in html
        with app.app_context():
            assert User.query.filter_by(phone=ADMIN_PHONE).first() is None

        second = client.post('/register', data={**_register_payload(ADMIN_PHONE, code=FIXED_CODE), 'action': 'verify_sensitive', 'csrf_token': _csrf(client)}, follow_redirects=False)
        assert second.status_code == 302
        with app.app_context():
            assert User.query.filter_by(phone=ADMIN_PHONE).first() is not None
    print('PASS  ثبت‌نام شماره ادمین ثبت‌شده هم فقط بعد از کد ربات کامل می‌شود')


def _run():
    tests = [v for k, v in sorted(globals().items()) if k.startswith('test_')]
    passed = 0
    for t in tests:
        try:
            t()
            passed += 1
        except AssertionError as e:
            print(f'FAIL  {t.__name__}: {e}')
        except Exception as e:
            print(f'ERROR {t.__name__}: {type(e).__name__}: {e}')
    print(f"\n{passed}/{len(tests)} passed")
    return passed == len(tests)


if __name__ == '__main__':
    sys.exit(0 if _run() else 1)
