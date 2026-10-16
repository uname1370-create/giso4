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
    for provider_name in ('groq', 'openrouter', 'mistral', 'cloudflare', 'gemini', 'gapgpt', 'avalai'):
        assert f'<strong>{provider_name}</strong>' in html, f'{provider_name} باید در کارت‌های Provider دیده شود'
    assert 'cf1 — Cloudflare اکانت ۱' not in html  # گزینه‌های cf1..cf3 حذف شده‌اند
    assert 'value="cloudflare"' in html
    assert '@cf/black-forest-labs/flux-2-klein-4b' in html
    assert 'data-field="account"' in html
    assert 'مدل‌های آینه گیسو' in html
    assert 'فقط آینه گیسو / Buti AI' in html
    # چهار دسته در پنل دیده شوند
    for heading in ('متن', 'تحلیل عکس', 'طراحی تصویر', 'ارزیابی خروجی'):
        assert f'<h4 style="margin:0 0 6px;">{heading}</h4>' in html, heading
    assert 'این اسلات‌ها روی مشاور عمومی' in html
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



def _fake_check_ok(selected):
    async def _check(row):
        return {"status": "ok", "error": "", "models": [selected], "selected": selected}
    return _check


def _fake_models_ok():
    async def _fetch(row):
        return {"ok": True, "items": [{"id": "fake-vision-model"}]}
    return _fetch


def _panel_state_guard():
    """وضعیت جدول‌های Provider/تخصیص و مسیر .env را برای تست نگه می‌دارد و بعد بازمی‌گرداند."""
    import tempfile as _tf
    from pathlib import Path as _P
    import giso.ai_brain as _ab
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import ai_db_snapshot as _snap

    class _G:
        def __enter__(self):
            self.state = _snap.snapshot()
            self.orig_env = _ab._ENV_PATH
            _ab._ENV_PATH = _P(_tf.mkdtemp()) / ".env"
            return self

        def __exit__(self, *exc):
            _ab._ENV_PATH = self.orig_env
            _snap.restore(self.state)
            return False
    return _G()


def test_superadmin_can_add_registry_service_from_web():
    """فرم واحد: سرویس رجیستری + نام نمایشی + API Key؛ تنظیمات از رجیستری و تأیید واقعی اتصال."""
    from unittest import mock
    import giso.ai_brain as _ab
    app = create_app()
    client = app.test_client()
    _cleanup(app)
    with app.app_context():
        db.session.add(User(phone=SUPER_PHONE, password_hash="hash", name="سوپر وب"))
        db.session.commit()
    _login_and_verify(client, phone=SUPER_PHONE)
    html = client.get('/admin/ai').get_data(as_text=True)
    token = re.search(r'name="csrf_token" value="([^"]+)"', html).group(1)
    with _panel_state_guard():
        with mock.patch.object(_ab, "_ai_check_openai", _fake_check_ok("llama-fake-text")), \
                mock.patch.object(_ab, "_fetch_remote_models", _fake_models_ok()):
            r = client.post('/admin/ai/provider/add', data={
                'csrf_token': token, 'provider': 'groq',
                'display_name': 'گروه تست آینه', 'api_key': 'FAKE_GROQ_KEY_FOR_TEST'})
        assert r.status_code == 302, f"provider add باید 302 شود، شد {r.status_code}"
        rows = [row for row in _ab.list_ai_providers() if row["display_name"] == "گروه تست آینه"]
        assert len(rows) == 1, len(rows)
        row = rows[0]
        assert row["kind"] == "openai"
        assert row["base_url"] == "https://api.groq.com/openai/v1"  # از رجیستری
        assert row["api_key"] == "FAKE_GROQ_KEY_FOR_TEST"
        assert int(row["enabled"]) == 1 and row["last_status"] == "ok"
        assert row["selected_model"] == "llama-fake-text"  # مدلی که واقعاً جواب داد
    print("PASS  سرویس رجیستری با نام نمایشی و تأیید واقعی ثبت شد")


def test_superadmin_can_add_two_cloudflare_accounts_from_web():
    """دو حساب Cloudflare با نام نمایشی متفاوت؛ حساب دوم حساب اول را بازنویسی نمی‌کند."""
    from unittest import mock
    import giso.ai_brain as _ab
    from giso.ai_brain import cloudflare_account_id_from_url
    app = create_app()
    client = app.test_client()
    _cleanup(app)
    with app.app_context():
        db.session.add(User(phone=SUPER_PHONE, password_hash="hash", name="سوپر وب"))
        db.session.commit()
    _login_and_verify(client, phone=SUPER_PHONE)
    html = client.get('/admin/ai').get_data(as_text=True)
    token = re.search(r'name="csrf_token" value="([^"]+)"', html).group(1)
    with _panel_state_guard():
        with mock.patch.object(_ab, "_ai_check_cloudflare",
                               _fake_check_ok("@cf/meta/llama-3.3-70b-instruct-fp8-fast")):
            for display, key, account in (("Cloudflare اصلی", "FAKE_CF_TOKEN_A", "acctaaaa0001"),
                                          ("Cloudflare دوم", "FAKE_CF_TOKEN_B", "acctbbbb0002")):
                r = client.post('/admin/ai/provider/add', data={
                    'csrf_token': token, 'provider': 'cloudflare', 'display_name': display,
                    'api_key': key, 'account_id': account})
                assert r.status_code == 302
        cf_rows = [row for row in _ab.list_ai_providers()
                   if str(row["kind"] or "").lower() == "cloudflare"
                   and str(row["display_name"] or "") in ("Cloudflare اصلی", "Cloudflare دوم")]
        assert len(cf_rows) == 2, len(cf_rows)
        names = [row["name"] for row in cf_rows]
        assert len(set(names)) == 2 and not set(names) & {"cf", "cf1", "cf2", "cf3"}
        by_display = {row["display_name"]: row for row in cf_rows}
        first, second = by_display["Cloudflare اصلی"], by_display["Cloudflare دوم"]
        assert first["api_key"] == "FAKE_CF_TOKEN_A" and second["api_key"] == "FAKE_CF_TOKEN_B"
        assert cloudflare_account_id_from_url(first["base_url"]) == "acctaaaa0001"
        assert cloudflare_account_id_from_url(second["base_url"]) == "acctbbbb0002"
        assert all(int(row["enabled"]) == 1 and row["last_status"] == "ok" for row in cf_rows)
    print("PASS  دو حساب Cloudflare مستقل ثبت شدند و حساب اول دست‌نخورده ماند")


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
