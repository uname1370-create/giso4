#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
تست Widget هوشمند سایت گیسو

۱) init برای مهمان کار می‌کند و پیکربندی را می‌دهد
۲) init برای کاربر لاگین‌شده نقش user را می‌دهد
۳) init برای سوپرادمین نقش super را می‌دهد
۴) chat با CSRF و history کار می‌کند
۵) خاموش بودن widget خطا می‌دهد
"""
import os
import sys
from unittest.mock import patch

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if BASE_DIR not in sys.path:
    sys.path.append(BASE_DIR)

from giso.app import create_app  # noqa: E402
from giso.models import db, User  # noqa: E402
from giso.ai_runtime import set_widget_enabled, set_widget_position, set_widget_welcome_message  # noqa: E402
from giso.base import normalize_phone, get_giso_db_conn  # noqa: E402

PHONE = normalize_phone("09120001234")
SUPER_PHONE = normalize_phone("09156012931")


def _cleanup(app):
    with app.app_context():
        for phone in (PHONE, SUPER_PHONE):
            for u in User.query.filter_by(phone=phone).all():
                db.session.delete(u)
        db.session.commit()
    try:
        with get_giso_db_conn() as conn:
            conn.execute("DELETE FROM giso_ai_usage_stats")
            conn.commit()
    except Exception:
        pass


def _login(client, phone):
    with client.session_transaction() as s:
        s['_user_id'] = phone


def test_widget_init_guest():
    app = create_app()
    client = app.test_client()
    _cleanup(app)
    set_widget_enabled(True)
    set_widget_position('left-bottom')
    set_widget_welcome_message('سلام از ویجت تست')
    r = client.get('/api/ai-widget/init?page=/shop')
    assert r.status_code == 200
    data = r.get_json()
    assert data['ok'] is True
    assert data['enabled'] is True
    assert data['role'] == 'guest'
    assert data['position'] == 'left-bottom'
    assert 'سلام' in data['welcome']
    assert data['actions'] and any(a['url'] == '/register' for a in data['actions'])
    assert isinstance(data.get('starter_prompts'), list) and data['starter_prompts']
    assert data.get('input_placeholder')
    print('PASS  init ویجت برای مهمان کار می‌کند')


def test_widget_init_user_and_super():
    app = create_app()
    client = app.test_client()
    _cleanup(app)
    with app.app_context():
        db.session.add(User(phone=PHONE, password_hash='hash', name='مینا'))
        db.session.add(User(phone=SUPER_PHONE, password_hash='hash', name='صادق'))
        db.session.commit()

    _login(client, PHONE)
    r = client.get('/api/ai-widget/init?page=/analysis')
    data = r.get_json()
    assert data['role'] == 'user'
    assert 'آنالیز' in data['summary'] or 'سابقه' in data['summary'] or data['summary']
    assert isinstance(data.get('suggestions'), list)
    assert isinstance(data.get('starter_prompts'), list)
    assert isinstance(data.get('actions'), list)
    assert data.get('page_title')

    client2 = app.test_client()
    _login(client2, SUPER_PHONE)
    r2 = client2.get('/api/ai-widget/init?page=/admin')
    data2 = r2.get_json()
    assert data2['role'] == 'user'

    with client2.session_transaction() as s:
        import time as _time
        s['admin_panel_verified_phone'] = SUPER_PHONE
        s['admin_panel_verified_until'] = int(_time.time()) + 1800
    r3 = client2.get('/api/ai-widget/init?page=/admin')
    data3 = r3.get_json()
    assert data3['role'] == 'super'
    assert 'گزارش' in data3['welcome'] or 'مدیریتی' in data3['welcome']
    print('PASS  init ویجت قبل از تأیید، نقش مدیریتی را لو نمی‌دهد و بعد از تأیید super را برمی‌گرداند')


def test_widget_chat_history_and_csrf():
    app = create_app()
    client = app.test_client()
    _cleanup(app)
    r = client.get('/api/ai-widget/init?page=/')
    token = r.get_json()['csrf_token']

    async def fake_chat(messages, **kwargs):
        return {'ok': True, 'text': 'سلام از سمت ویجت', 'provider': 'groq', 'model': 'llama'}

    with patch('giso.app.chat_with_managed_ai', side_effect=fake_chat):
        r2 = client.post('/api/ai-widget/chat', json={'message': 'سلام', 'page': '/'}, headers={'X-AI-Widget-CSRF': token})
    assert r2.status_code == 200
    data = r2.get_json()
    assert data['ok'] is True
    assert 'سلام از سمت ویجت' in data['response']
    assert len(data['history']) >= 2
    assert 'suggestions' in data and isinstance(data['suggestions'], list)
    assert 'actions' in data and isinstance(data['actions'], list)

    r3 = client.post('/api/ai-widget/chat', json={'message': 'سلام', 'page': '/'})
    assert r3.status_code == 403
    print('PASS  چت ویجت با CSRF و history کار می‌کند')


def test_widget_chat_fallback_on_provider_error():
    app = create_app()
    client = app.test_client()
    _cleanup(app)
    r = client.get('/api/ai-widget/init?page=/analysis')
    token = r.get_json()['csrf_token']

    async def fake_chat(messages, **kwargs):
        return {'ok': False, 'reason': 'provider_error', 'text': 'خطای provider'}

    with patch('giso.app.chat_with_managed_ai', side_effect=fake_chat):
        r2 = client.post('/api/ai-widget/chat', json={'message': 'از کجا شروع کنم؟', 'page': '/analysis'}, headers={'X-AI-Widget-CSRF': token})
    assert r2.status_code == 200
    data = r2.get_json()
    assert data['ok'] is True
    assert data['fallback_used'] is True
    assert data['provider'] == 'runtime-fallback'
    assert data['response']
    assert isinstance(data.get('starter_prompts'), list)
    print('PASS  در خطای provider، ویجت با پاسخ fallback متوقف نمی‌شود')


def test_widget_disabled_blocks_chat():
    app = create_app()
    client = app.test_client()
    _cleanup(app)
    set_widget_enabled(False)
    r = client.get('/api/ai-widget/init?page=/')
    token = r.get_json()['csrf_token']
    r2 = client.post('/api/ai-widget/chat', json={'message': 'سلام', 'page': '/', 'csrf_token': token})
    assert r2.status_code == 503
    print('PASS  در حالت خاموش، ویجت چت را مسدود می‌کند')


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
