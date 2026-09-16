#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
تست نمای مدیریتی AI در پنل وب

۱) ادمین تأییدشده می‌تواند تب AI را ببیند
۲) محتوای read-only مدیریت AI در HTML رندر می‌شود
"""
import os
import sys
import time
import sqlite3

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if BASE_DIR not in sys.path:
    sys.path.append(BASE_DIR)

import re
from giso.app import create_app  # noqa: E402
from giso.models import db, User  # noqa: E402
from giso.base import normalize_phone  # noqa: E402
from giso.config import SUPERADMIN_BALE_ID  # noqa: E402
from giso.ai_runtime import get_setting, set_display_name  # noqa: E402
from bot_edu.giso_admin import add_giso_admin  # noqa: E402

ADMIN_PHONE = normalize_phone("09124445555")
ADMIN_BALE_ID = "77889900"
SUPER_PHONE = normalize_phone("09156012931")


def _cleanup(app):
    with app.app_context():
        for phone in (ADMIN_PHONE, SUPER_PHONE):
            User.query.filter_by(phone=phone).delete(synchronize_session=False)
        db.session.commit()
    bot_db = os.path.join(BASE_DIR, "bot_edu", "data", "bot.db")
    conn = sqlite3.connect(bot_db)
    try:
        conn.execute("DELETE FROM giso_admins WHERE phone=? OR bale_id=?", (ADMIN_PHONE, ADMIN_BALE_ID))
        conn.commit()
    finally:
        conn.close()


def _login_and_verify(client, phone=ADMIN_PHONE):
    with client.session_transaction() as s:
        s.setdefault("giso_csrf_token", "fixed-test-csrf-token")
        s['_user_id'] = phone
        s['admin_panel_verified_phone'] = phone
        s['admin_panel_verified_until'] = int(time.time()) + 1800


    _op = client.post
    def _post_with_csrf(*a, **k):
        h = dict(k.get("headers") or {}); h.setdefault("X-GISO-CSRF", "fixed-test-csrf-token"); k["headers"] = h
        return _op(*a, **k)
    client.post = _post_with_csrf
def test_admin_ai_panel_read_only_view():
    """قرارداد فعلی: صفحه AI فقط برای سوپرادمین؛ ادمین عادی redirect می‌شود."""
    app = create_app()
    client = app.test_client()
    _cleanup(app)
    with app.app_context():
        db.session.add(User(phone=ADMIN_PHONE, password_hash='hash', name='ادمین وب'))
        db.session.commit()
    add_giso_admin(phone=ADMIN_PHONE, bale_id=ADMIN_BALE_ID, added_by=SUPERADMIN_BALE_ID)
    _login_and_verify(client)
    r = client.get('/admin/ai')
    assert r.status_code == 302  # ادمین عادی دسترسی ندارد
    sup = app.test_client()
    with app.app_context():
        db.session.add(User(phone=SUPER_PHONE, password_hash='hash', name='سوپر وب'))
        db.session.commit()
    _login_and_verify(sup, phone=SUPER_PHONE)
    r2 = sup.get('/admin/ai')
    assert r2.status_code == 200
    html = r2.get_data(as_text=True)
    assert 'مدیریت هوش مصنوعی' in html
    assert 'اسم نمایشی مشاور هوشمند' in html
    print('PASS  نمای AI برای سوپرادمین کامل و برای ادمین مسدود است')



def test_superadmin_ai_panel_can_update_display_name_from_web():
    app = create_app()
    client = app.test_client()
    _cleanup(app)
    original = get_setting('chat_display_name', 'مشاور صادقی') or 'مشاور صادقی'
    with app.app_context():
        db.session.add(User(phone=SUPER_PHONE, password_hash='hash', name='سوپر وب'))
        db.session.commit()
    _login_and_verify(client, phone=SUPER_PHONE)
    try:
        tok = re.search(r'name="csrf_token" value="([^"]+)"',
                        client.get('/admin/ai').get_data(as_text=True)).group(1)
        r = client.post('/admin/ai/config', data={'ai_action': 'set_display_name',
                                                  'display_name': 'همراه ویژه',
                                                  'csrf_token': tok}, follow_redirects=False)
        assert r.status_code == 302
        assert get_setting('chat_display_name') == 'همراه ویژه'
        print('PASS  سوپرادمین از پنل وب می‌تواند اسم نمایشی AI را تغییر دهد')
    finally:
        set_display_name(original)



def test_superadmin_can_add_ai_provider_from_web():
    """رگرسیون: handle_provider_add به‌دلیل باگ تورفتگی None برمی‌گرداند → 500."""
    import re as _re
    import tempfile as _tf
    from pathlib import Path as _P
    import giso.ai_brain as _ab
    app = create_app()
    client = app.test_client()
    _cleanup(app)
    with app.app_context():
        db.session.add(User(phone=SUPER_PHONE, password_hash="hash", name="سوپر وب"))
        db.session.commit()
    _login_and_verify(client, phone=SUPER_PHONE)
    html = client.get('/admin/ai').get_data(as_text=True)
    m2 = _re.search(r'name="csrf_token" value="([^"]+)"', html)
    _tmp_env = _P(_tf.mkdtemp()) / ".env"
    _orig_env = _ab._ENV_PATH
    _ab._ENV_PATH = _tmp_env
    try:
        r = client.post('/admin/ai/provider/add', data={
            'csrf_token': m2.group(1) if m2 else '', 'name': 'gemini-regress', 'kind': 'openai',
            'api_key': 'FAKE_KEY_FOR_TEST',
            'base_url': 'https://generativelanguage.googleapis.com/v1beta/openai',
            'selected_model': 'gemini-2.0-flash', 'timeout': '20'})
        assert r.status_code == 302, f"provider add باید 302 شود، شد {r.status_code}"
        from giso.ai_runtime import list_provider_options
        grouped = list_provider_options() or {}
        names = [str(p2.get('name')) for rows in grouped.values() for p2 in (rows or [])]
        assert 'gemini-regress' in names, f"پروایدر ثبت نشد: {names}"
        print('PASS  سوپرادمین از پنل می‌تواند پروایدر AI اضافه کند (رگرسیون ۵۰۰)')
    finally:
        _ab._ENV_PATH = _orig_env
        try:
            _tmp_env.unlink()
        except Exception:
            pass



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
