# -*- coding: utf-8 -*-
"""فرم ساده «مدل دلخواه» در پنل AI سایت.

فقط سه ورودی لازم است: نام مدل، کلید API و آدرس بیس.
"""
import os
import sys
import time

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if BASE_DIR not in sys.path:
    sys.path.append(BASE_DIR)

from giso.app import create_app  # noqa: E402
from giso.models import db, User  # noqa: E402
from giso.base import normalize_phone  # noqa: E402
from giso import ai_brain  # noqa: E402

SUPER_PHONE = normalize_phone("09156012931")
ADMIN_PHONE = normalize_phone("09124445566")
CSRF = "fixed-test-csrf-token"
HOST = "api.custom-model-simple-test.example"
URL = f"https://{HOST}/v1"


def _ensure_user(app, phone):
    with app.app_context():
        if not User.query.filter_by(phone=phone).first():
            db.session.add(User(phone=phone, password_hash="hash", name="تست"))
            db.session.commit()


def _login(client, phone):
    with client.session_transaction() as s:
        s["giso_csrf_token"] = CSRF
        s["_user_id"] = phone
        s["admin_panel_verified_phone"] = phone
        s["admin_panel_verified_until"] = int(time.time()) + 1800


def _post(client, data):
    return client.post("/admin/ai/custom-model/add", data=data,
                       headers={"X-GISO-CSRF": CSRF}, follow_redirects=False)


def _row(name):
    return ai_brain.get_ai_provider(name)


def _cleanup():
    for name in ("custom-api-custom-model-simple-test-example",
                 "custom-api-custom-model-simple-test-example-2"):
        if _row(name):
            ai_brain.delete_ai_provider(name)


def test_custom_model_saved_with_only_three_fields():
    app = create_app()
    _ensure_user(app, SUPER_PHONE)
    client = app.test_client()
    _login(client, SUPER_PHONE)
    _cleanup()
    try:
        r = _post(client, {"model_name": "my-model-v1", "api_key": "FAKE-SIMPLE-KEY-0001", "base_url": URL,
                           "csrf_token": CSRF})
        assert r.status_code == 302
        row = _row("custom-api-custom-model-simple-test-example")
        assert row is not None
        assert row["kind"] == "openai"
        assert row["base_url"] == URL
        assert row["api_root"] == URL
        assert row["selected_model"] == "my-model-v1"
        assert row["api_key"] == "FAKE-SIMPLE-KEY-0001"
        assert int(row["timeout"]) == 20
        assert int(row["is_iranian"]) == 0
        assert int(row["use_proxy"]) == 0
        assert int(row["enabled"]) == 1
        env_text = ai_brain._ENV_PATH.read_text(encoding="utf-8") if ai_brain._ENV_PATH.exists() else ""
        assert "custom-api-custom-model-simple-test-example" in env_text
    finally:
        _cleanup()


def test_same_domain_gets_new_name_and_never_overwrites():
    app = create_app()
    _ensure_user(app, SUPER_PHONE)
    client = app.test_client()
    _login(client, SUPER_PHONE)
    _cleanup()
    try:
        _post(client, {"model_name": "m-one", "api_key": "FAKE-FIRST-KEY-0002", "base_url": URL, "csrf_token": CSRF})
        _post(client, {"model_name": "m-two", "api_key": "FAKE-SECOND-KEY-0003", "base_url": URL, "csrf_token": CSRF})
        first = _row("custom-api-custom-model-simple-test-example")
        second = _row("custom-api-custom-model-simple-test-example-2")
        assert first["api_key"] == "FAKE-FIRST-KEY-0002"
        assert first["selected_model"] == "m-one"
        assert second is not None
        assert second["api_key"] == "FAKE-SECOND-KEY-0003"
        assert second["selected_model"] == "m-two"
    finally:
        _cleanup()


def test_unsafe_or_plain_http_base_url_is_rejected():
    app = create_app()
    _ensure_user(app, SUPER_PHONE)
    client = app.test_client()
    _login(client, SUPER_PHONE)
    _cleanup()
    try:
        for bad in ("https://127.0.0.1/v1", "https://localhost/v1", "http://api.custom-model-simple-test.example/v1"):
            _post(client, {"model_name": "x", "api_key": "FAKE-BAD-KEY-0004", "base_url": bad, "csrf_token": CSRF})
        assert _row("custom-api-custom-model-simple-test-example") is None
        assert _row("custom-127-0-0-1") is None
        assert _row("custom-localhost") is None
    finally:
        _cleanup()


def test_missing_fields_are_rejected():
    app = create_app()
    _ensure_user(app, SUPER_PHONE)
    client = app.test_client()
    _login(client, SUPER_PHONE)
    _cleanup()
    try:
        _post(client, {"model_name": "", "api_key": "FAKE-KEY-0005", "base_url": URL, "csrf_token": CSRF})
        _post(client, {"model_name": "m", "api_key": "", "base_url": URL, "csrf_token": CSRF})
        _post(client, {"model_name": "m", "api_key": "FAKE-KEY-0005", "base_url": "", "csrf_token": CSRF})
        _post(client, {"model_name": "has space", "api_key": "FAKE-KEY-0005", "base_url": URL, "csrf_token": CSRF})
        assert _row("custom-api-custom-model-simple-test-example") is None
    finally:
        _cleanup()


def test_non_super_admin_cannot_add():
    app = create_app()
    _ensure_user(app, ADMIN_PHONE)
    client = app.test_client()
    _login(client, ADMIN_PHONE)
    _cleanup()
    try:
        r = _post(client, {"model_name": "m", "api_key": "FAKE-KEY-0006", "base_url": URL, "csrf_token": CSRF})
        assert r.status_code == 302
        assert _row("custom-api-custom-model-simple-test-example") is None
    finally:
        _cleanup()


def test_simple_form_and_advanced_form_are_both_on_page():
    app = create_app()
    _ensure_user(app, SUPER_PHONE)
    client = app.test_client()
    _login(client, SUPER_PHONE)
    html = client.get("/admin/ai").get_data(as_text=True)
    assert "افزودن مدل دلخواه (ساده)" in html
    assert "افزودن سرویس پیشرفته" in html
    assert 'name="model_name"' in html
    assert "/admin/ai/custom-model/add" in html or "ai_custom_model_add" in html or "custom-model/add" in html


def test_cloudflare_url_is_refused_in_simple_form():
    app = create_app()
    _ensure_user(app, SUPER_PHONE)
    client = app.test_client()
    _login(client, SUPER_PHONE)
    _cleanup()
    try:
        cf = "https://api.cloudflare.com/client/v4/accounts/1234567890abcdef1234567890abcdef/ai/run"
        r = _post(client, {"model_name": "m", "api_key": "FAKE-CF-KEY-0007", "base_url": cf, "csrf_token": CSRF})
        assert r.status_code == 302
        assert _row("custom-cloudflare") is None
        assert _row("custom-api-cloudflare-com") is None
    finally:
        _cleanup()


def test_advanced_form_is_collapsed_by_default_and_simple_form_is_open():
    app = create_app()
    _ensure_user(app, SUPER_PHONE)
    client = app.test_client()
    _login(client, SUPER_PHONE)
    html = client.get("/admin/ai").get_data(as_text=True)
    adv = html.index("افزودن سرویس پیشرفته")
    assert '<details class="pnl-card" style="padding:0;">' in html
    assert html.index("افزودن مدل دلخواه (ساده)") < html.index('<details class="pnl-card" style="padding:0;">')
    assert "data-ai-provider-add-form" in html  # full form still exists inside the collapsed block
