#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
تست بازیابی رمز برای شماره‌های حساس با کد ربات
"""
import os
import sys
from unittest.mock import patch
from werkzeug.security import generate_password_hash, check_password_hash

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if BASE_DIR not in sys.path:
    sys.path.append(BASE_DIR)

from giso.app import create_app  # noqa: E402
from giso.models import db, User  # noqa: E402
from giso.base import normalize_phone  # noqa: E402

SUPER_PHONE = normalize_phone("09156012931")
FIXED_CODE = "135790"


def _cleanup(app):
    with app.app_context():
        User.query.filter_by(phone=SUPER_PHONE).delete(synchronize_session=False)
        db.session.commit()


def _csrf(client, path="/register"):
    import re as _re
    m = _re.search(r'name="csrf_token" value="([^"]+)"', client.get(path).get_data(as_text=True))
    return m.group(1) if m else ""

def test_sensitive_forgot_password_requires_bot_code():
    app = create_app()
    client = app.test_client()
    _cleanup(app)
    with app.app_context():
        db.session.add(User(
            phone=SUPER_PHONE,
            password_hash=generate_password_hash('old-pass', method='pbkdf2:sha256'),
            name='سوپر',
            security_question='نام شهر محل تولد شما چیست؟',
            security_answer='تهران',
        ))
        db.session.commit()

    first = client.post('/forgot-password', data={'step': 'phone', 'phone': SUPER_PHONE, 'csrf_token': _csrf(client, '/forgot-password')}, follow_redirects=True)
    assert 'سوال امنیتی' in first.get_data(as_text=True)

    with patch('giso.app._send_admin_panel_code_to_bot', return_value=(True, 'کد ارسال شد')), \
         patch('giso.app._generate_admin_panel_code', return_value=FIXED_CODE):
        second = client.post('/forgot-password', data={'step': 'answer', 'security_answer': 'تهران', 'csrf_token': _csrf(client, '/forgot-password')}, follow_redirects=True)
        html = second.get_data(as_text=True)
        assert 'کد تأیید ربات' in html

        third = client.post('/forgot-password', data={'step': 'bot', 'bot_code': FIXED_CODE, 'csrf_token': _csrf(client, '/forgot-password')}, follow_redirects=True)
        assert 'رمز عبور جدید' in third.get_data(as_text=True)

    final = client.post('/forgot-password', data={'step': 'password', 'password': 'new-pass1', 'password2': 'new-pass1', 'csrf_token': _csrf(client, '/forgot-password')}, follow_redirects=False)
    assert final.status_code == 302
    with app.app_context():
        user = User.query.filter_by(phone=SUPER_PHONE).first()
        assert user is not None and check_password_hash(user.password_hash, 'new-pass1')
    print('PASS  بازیابی رمز شماره حساس فقط بعد از کد ربات کامل می‌شود')


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
