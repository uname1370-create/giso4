#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
تست تأیید دومرحله‌ای پنل ادمین وب با کد ربات

۱) ادمین سایت قبل از تأیید، به /admin راه پیدا نمی‌کند
۲) کد تأیید به ربات ادمین ارسال می‌شود و بعد از ورود کد، پنل باز می‌شود
۳) تا قبل از تأیید، role سایت برای widget ادمین/سوپرادمین لو نمی‌رود
۴) سوپرادمین وب هم با همین مسیر تأیید می‌شود
"""
import os
import sys
import re
from unittest.mock import patch

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if BASE_DIR not in sys.path:
    sys.path.append(BASE_DIR)

from giso.app import create_app  # noqa: E402
from giso.models import db, User  # noqa: E402
from giso.base import normalize_phone  # noqa: E402
from giso.config import SUPERADMIN_BALE_ID  # noqa: E402
from bot_edu.giso_admin import add_giso_admin  # noqa: E402

ADMIN_PHONE = normalize_phone("09123334444")
ADMIN_BALE_ID = "88990011"
SUPER_PHONE = normalize_phone("09156012931")
FIXED_CODE = "654321"


def _cleanup(app):
    with app.app_context():
        for phone in (ADMIN_PHONE, SUPER_PHONE):
            for u in User.query.filter_by(phone=phone).all():
                db.session.delete(u)
        db.session.commit()
    import sqlite3
    bot_db = os.path.join(BASE_DIR, "bot_edu", "data", "bot.db")
    conn = sqlite3.connect(bot_db)
    try:
        conn.execute("DELETE FROM giso_admins WHERE phone=? OR bale_id=?", (ADMIN_PHONE, ADMIN_BALE_ID))
        conn.commit()
    finally:
        conn.close()


def _login(client, phone):
    with client.session_transaction() as s:
        s.setdefault("giso_csrf_token", "fixed-test-csrf-token")
        s['_user_id'] = phone


    _op = client.post
    def _post_with_csrf(*a, **k):
        h = dict(k.get("headers") or {}); h.setdefault("X-GISO-CSRF", "fixed-test-csrf-token"); k["headers"] = h
        return _op(*a, **k)
    client.post = _post_with_csrf
def test_admin_panel_verify_flow_for_admin():
    app = create_app()
    client = app.test_client()
    _cleanup(app)
    with app.app_context():
        db.session.add(User(phone=ADMIN_PHONE, password_hash='hash', name='ادمین سایت'))
        db.session.commit()
    add_giso_admin(phone=ADMIN_PHONE, bale_id=ADMIN_BALE_ID, added_by=SUPERADMIN_BALE_ID)
    _login(client, ADMIN_PHONE)

    with patch('giso.app._send_admin_panel_code_to_bot', return_value=(True, 'کد به ربات ارسال شد.')), \
         patch('giso.app._generate_admin_panel_code', return_value=FIXED_CODE):
        r = client.get('/admin')
        assert r.status_code == 302
        assert '/admin/verify' in (r.headers.get('Location') or '')

        init_before = client.get('/api/ai-widget/init?page=/admin').get_json()
        assert init_before['role'] == 'user'

        r2 = client.get('/admin/verify')
        assert r2.status_code == 200
        assert 'کد تأیید' in r2.get_data(as_text=True)

        tok = re.search(r'name="csrf_token" value="([^"]+)"', r2.get_data(as_text=True)).group(1)
        r3 = client.post('/admin/verify', data={'action': 'verify', 'code': FIXED_CODE, 'csrf_token': tok})
        assert r3.status_code == 302

    init_after = client.get('/api/ai-widget/init?page=/admin').get_json()
    assert init_after['role'] == 'admin'
    r4 = client.get('/admin', follow_redirects=True)
    assert r4.status_code == 200 and 'پنل مدیریت' in r4.get_data(as_text=True)
    print('PASS  ادمین وب فقط بعد از کد ربات وارد پنل می‌شود')


def test_admin_panel_verify_flow_for_superadmin():
    app = create_app()
    client = app.test_client()
    _cleanup(app)
    with app.app_context():
        db.session.add(User(phone=SUPER_PHONE, password_hash='hash', name='سوپر سایت'))
        db.session.commit()
    _login(client, SUPER_PHONE)

    with patch('giso.app._send_admin_panel_code_to_bot', return_value=(True, 'کد به ربات ارسال شد.')), \
         patch('giso.app._generate_admin_panel_code', return_value=FIXED_CODE):
        r = client.get('/admin')
        assert r.status_code == 302
        assert '/admin/verify' in (r.headers.get('Location') or '')

        init_before = client.get('/api/ai-widget/init?page=/admin').get_json()
        assert init_before['role'] == 'user'

        client.get('/admin/verify')
        tok = re.search(r'name="csrf_token" value="([^"]+)"', client.get('/admin/verify').get_data(as_text=True)).group(1)
        r2 = client.post('/admin/verify', data={'action': 'verify', 'code': FIXED_CODE, 'csrf_token': tok})
        assert r2.status_code == 302

    init_after = client.get('/api/ai-widget/init?page=/admin').get_json()
    assert init_after['role'] == 'super'
    r3 = client.get('/admin', follow_redirects=True)
    assert r3.status_code == 200 and 'پنل مدیریت' in r3.get_data(as_text=True)
    print('PASS  سوپرادمین وب هم قبل از پنل باید کد ربات را تأیید کند')


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
