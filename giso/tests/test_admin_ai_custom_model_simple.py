# -*- coding: utf-8 -*-
"""گزینه‌های «افزودن سرویس» در پنل AI سایت.

۱) Cloudflare: نام (cf / cf1 / cf2 / cf3)، کلید API و Account ID.
۲) مدل دلخواه: نام پروایدر، کلید API و آدرس بیس؛ مدل‌ها بعد از ذخیره
   خودکار از /models شناسایی و اولین مدل پیداشده انتخاب می‌شود.

شناسایی /models با مرز شبکه جایگزین شده است؛ هیچ درخواست واقعی ارسال نمی‌شود.
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
BASE = "https://api.mtest-alpha.example/v1"
NAMES = ("mtest-alpha", "mtest-beta", "mtest-host-check", "mtest-missing")


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


def _post(client, path, data):
    data = dict(data)
    data["csrf_token"] = CSRF
    return client.post(path, data=data, headers={"X-GISO-CSRF": CSRF}, follow_redirects=False)


def _custom(client, data):
    return _post(client, "/admin/ai/custom-model/add", data)


def _row(name):
    return ai_brain.get_ai_provider(name)


def _cleanup():
    for name in NAMES:
        if _row(name):
            ai_brain.delete_ai_provider(name)


def _fake_fetch(items=None, ok=True, error=""):
    async def _fetch(row):
        if not ok:
            return {"ok": False, "error": error or "HTTP 404"}
        return {"ok": True, "items": list(items or [])}
    return _fetch


def _setup(monkeypatch, phone=SUPER_PHONE):
    app = create_app()
    _ensure_user(app, phone)
    client = app.test_client()
    _login(client, phone)
    _cleanup()
    return client


# ── گزینه مدل دلخواه ─────────────────────────────────────────

def test_custom_provider_saved_and_discovered_models_picked(monkeypatch):
    client = _setup(monkeypatch)
    monkeypatch.setattr(ai_brain, "_fetch_remote_models", _fake_fetch(
        items=[{"id": "plain-text-one"}, {"id": "llava-vision-two"}]))
    try:
        r = _custom(client, {"provider_name": "mtest-alpha", "api_key": "FAKE-ALPHA-KEY-0001", "base_url": BASE})
        assert r.status_code == 302
        row = _row("mtest-alpha")
        assert row is not None
        assert row["kind"] == "openai"
        assert row["base_url"] == BASE
        assert row["api_key"] == "FAKE-ALPHA-KEY-0001"
        assert int(row["enabled"]) == 1
        assert row["models_source"] == "discovered"
        assert row["selected_model"] == "llava-vision-two"  # Vision اول
        assert "llava-vision-two" in row["vision_models_json"]
        assert "plain-text-one" in row["text_models_json"]
    finally:
        _cleanup()


def test_discovery_failure_still_saves_and_warns(monkeypatch):
    client = _setup(monkeypatch)
    monkeypatch.setattr(ai_brain, "_fetch_remote_models", _fake_fetch(ok=False, error="HTTP 404"))
    try:
        r = _custom(client, {"provider_name": "mtest-beta", "api_key": "FAKE-BETA-KEY-0002", "base_url": BASE})
        assert r.status_code == 302
        row = _row("mtest-beta")
        assert row is not None
        assert row["selected_model"] == ""
        with client.session_transaction() as s:
            flashes = " ".join(m for _, m in s.get("_flashes", []))
        assert "شناسایی مدل‌ها انجام نشد" in flashes
    finally:
        _cleanup()


def test_existing_name_is_never_overwritten(monkeypatch):
    client = _setup(monkeypatch)
    monkeypatch.setattr(ai_brain, "_fetch_remote_models", _fake_fetch(items=[{"id": "plain-text-one"}]))
    try:
        _custom(client, {"provider_name": "mtest-alpha", "api_key": "FAKE-FIRST-KEY-0003", "base_url": BASE})
        _custom(client, {"provider_name": "mtest-alpha", "api_key": "FAKE-SECOND-KEY-0004",
                         "base_url": "https://api.other-host.example/v1"})
        row = _row("mtest-alpha")
        assert row["api_key"] == "FAKE-FIRST-KEY-0003"
        assert row["base_url"] == BASE
    finally:
        _cleanup()


def test_reserved_and_registry_names_are_rejected(monkeypatch):
    client = _setup(monkeypatch)
    try:
        for reserved in ("cf", "cf1", "cloudflare", "groq", "gemini", "Bad Name!"):
            before = _row(reserved)
            before_key = before["api_key"] if before else None
            key = f"FAKE-RESERVED-{reserved}-0005"
            r = _custom(client, {"provider_name": reserved, "api_key": key, "base_url": BASE})
            assert r.status_code == 302
            after = _row(reserved)
            assert (after["api_key"] if after else None) == before_key
            assert after is None or key not in str(after["api_key"])
    finally:
        _cleanup()


def test_plain_http_and_cloudflare_host_are_rejected(monkeypatch):
    client = _setup(monkeypatch)
    try:
        _custom(client, {"provider_name": "mtest-missing", "api_key": "FAKE-HTTP-KEY-0006",
                         "base_url": "http://api.mtest-missing.example/v1"})
        assert _row("mtest-missing") is None
        cf = "https://api.cloudflare.com/client/v4/accounts/1234567890abcdef1234567890abcdef/ai/run"
        _custom(client, {"provider_name": "mtest-host-check", "api_key": "FAKE-CF-HOST-0007", "base_url": cf})
        assert _row("mtest-host-check") is None
    finally:
        _cleanup()


def test_missing_fields_are_rejected(monkeypatch):
    client = _setup(monkeypatch)
    try:
        _custom(client, {"provider_name": "mtest-missing", "api_key": "", "base_url": BASE})
        _custom(client, {"provider_name": "", "api_key": "FAKE-MISS-KEY-0008", "base_url": BASE})
        _custom(client, {"provider_name": "mtest-missing", "api_key": "FAKE-MISS-KEY-0008", "base_url": ""})
        assert _row("mtest-missing") is None
    finally:
        _cleanup()


def test_non_super_admin_cannot_add(monkeypatch):
    client = _setup(monkeypatch, phone=ADMIN_PHONE)
    try:
        r = _custom(client, {"provider_name": "mtest-alpha", "api_key": "FAKE-ADMIN-KEY-0009", "base_url": BASE})
        assert r.status_code == 302
        assert _row("mtest-alpha") is None
    finally:
        _cleanup()


# ── صفحه ───────────────────────────────────────────────────────

def test_page_has_two_options_and_no_old_three_field_card(monkeypatch):
    client = _setup(monkeypatch)
    html = client.get("/admin/ai").get_data(as_text=True)
    assert "data-add-chooser" in html
    assert 'value="cf"' in html and 'value="custom"' in html
    assert "افزودن مدل Cloudflare" in html
    assert "مدل دلخواه (هر سرویس سازگار با OpenAI)" in html
    assert 'name="provider_name"' in html
    assert "نام مدل* — مثلاً my-model-v1" not in html  # فرم قدیمی سه‌فیلدی حذف شده
    assert "افزودن سرویس پیشرفته" in html  # فرم پیشرفته باقی مانده


def test_cloudflare_option_posts_to_provider_add_with_account_field(monkeypatch):
    client = _setup(monkeypatch)
    html = client.get("/admin/ai").get_data(as_text=True)
    cf_start = html.index('data-add-panel="cf"')
    cf_block = html[html.rindex("<form", 0, cf_start):html.index("</form>", cf_start)]
    assert 'name="account_id"' in cf_block
    assert 'name="api_key"' in cf_block
    assert '<option value="cf1">' in cf_block
    import re
    action = re.search(r'action="([^"]+)"', cf_block).group(1)
    assert "provider" in action and "custom-model" not in action


def test_provider_card_lists_discovered_models(monkeypatch):
    client = _setup(monkeypatch)
    monkeypatch.setattr(ai_brain, "_fetch_remote_models", _fake_fetch(
        items=[{"id": "plain-text-one"}, {"id": "llava-vision-two"}]))
    try:
        _custom(client, {"provider_name": "mtest-alpha", "api_key": "FAKE-ALPHA-KEY-0010", "base_url": BASE})
        html = client.get("/admin/ai").get_data(as_text=True)
        assert '<option value="llava-vision-two" selected>' in html
        assert '<option value="plain-text-one"' in html
    finally:
        _cleanup()
