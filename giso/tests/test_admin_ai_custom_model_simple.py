# -*- coding: utf-8 -*-
"""فرم واحد «افزودن سرویس» در پنل AI سایت — مسیر سرویس دلخواه و قراردادهای کلی.

- سرویس دلخواه: نام نمایشی، API Key و Base URL؛ «تست اتصال و کشف مدل‌ها».
- تأیید اتصال فقط با نتیجهٔ ok ثبت می‌شود؛ شکست هرگز موفقیت ثبت نمی‌کند.
- کشف مدل‌ها هرگز selected_model را تغییر نمی‌دهد.
- هر ثبت یک نمونهٔ مستقل است و نمونه‌های قبلی بازنویسی نمی‌شوند.

هیچ درخواست شبکهٔ واقعی ارسال نمی‌شود: تست اتصال و /models با مرز شبکه جایگزین شده‌اند.
"""
import os
import re
import sys
import time
import tempfile
from pathlib import Path
from unittest import mock

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if BASE_DIR not in sys.path:
    sys.path.append(BASE_DIR)

from giso.app import create_app  # noqa: E402
from giso.models import db, User  # noqa: E402
from giso.base import normalize_phone  # noqa: E402
from giso import ai_brain  # noqa: E402
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ai_db_snapshot as _snap  # noqa: E402

SUPER_PHONE = normalize_phone("09156012931")
CSRF = "fixed-test-csrf-token"
BASE = "https://api.mtest-alpha.example/v1"
BASE2 = "https://api.mtest-beta.example/v1"
TEST_DISPLAYS = ("مدل تست الفا", "مدل تست بتا", "مدل تست تکراری")


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


def _post(client, path, data, follow=False):
    data = dict(data)
    data["csrf_token"] = CSRF
    return client.post(path, data=data, headers={"X-GISO-CSRF": CSRF}, follow_redirects=follow)


def _add(client, data, follow=False):
    return _post(client, "/admin/ai/provider/add", data, follow=follow)


def _rows_by_display(display):
    return [r for r in ai_brain.list_ai_providers() if str(r["display_name"] or "") == display]


_STATE = None


def _cleanup():
    """جدول‌های Provider و تخصیص را به وضعیت قبل از تست برمی‌گرداند."""
    global _STATE
    if _STATE is not None:
        _snap.restore(_STATE)
        _STATE = None


def _fake_check(status="ok", selected="llava-vision-two", models=(), error=""):
    async def _check(row):
        return {"status": status, "error": error, "models": list(models), "selected": selected}
    return _check


def _fake_fetch(items=None, ok=True, error=""):
    async def _fetch(row):
        if not ok:
            return {"ok": False, "error": error or "HTTP 404"}
        return {"ok": True, "items": list(items or [])}
    return _fetch


def _setup():
    global _STATE
    app = create_app()
    _ensure_user(app, SUPER_PHONE)
    _STATE = _snap.snapshot()
    client = app.test_client()
    _login(client, SUPER_PHONE)
    return app, client


def _env_guard():
    """بازنویسی .env واقعی را در تست متوقف می‌کند."""
    tmp = Path(tempfile.mkdtemp()) / ".env"
    orig = ai_brain._ENV_PATH
    ai_brain._ENV_PATH = tmp
    return orig


def test_custom_verified_discovers_models_and_keeps_selected_from_check():
    app, client = _setup()
    orig_env = _env_guard()
    try:
        with mock.patch.object(ai_brain, "_ai_check_openai",
                               _fake_check("ok", "llava-vision-two",
                                           ["plain-text-one", "llava-vision-two"])), \
                mock.patch.object(ai_brain, "_fetch_remote_models",
                                  _fake_fetch(items=[{"id": "plain-text-one"}, {"id": "llava-vision-two"}])):
            r = _add(client, {"provider": "custom", "display_name": "مدل تست الفا",
                              "api_key": "FAKE-ALPHA-KEY-0010", "base_url": BASE})
        assert r.status_code == 302
        rows = _rows_by_display("مدل تست الفا")
        assert len(rows) == 1
        row = rows[0]
        assert row["kind"] == "openai"
        assert row["base_url"] == BASE
        assert int(row["enabled"]) == 1 and row["last_status"] == "ok"
        assert row["selected_model"] == "llava-vision-two"  # از تست واقعی، نه از کشف
        assert "llava-vision-two" in row["vision_models_json"]
        assert "plain-text-one" in row["text_models_json"]
        print("PASS  سرویس دلخواه موفق: کشف مدل و selected از تست واقعی")
    finally:
        ai_brain._ENV_PATH = orig_env
        _cleanup()


def test_custom_failed_check_is_saved_disabled_and_never_reported_as_success():
    app, client = _setup()
    orig_env = _env_guard()
    try:
        with mock.patch.object(ai_brain, "_ai_check_openai",
                               _fake_check("error", "", [], "/models HTTP 404 (API سازگار با OpenAI نیست)")):
            r = _add(client, {"provider": "custom", "display_name": "مدل تست الفا",
                              "api_key": "FAKE-ALPHA-KEY-0010", "base_url": BASE}, follow=True)
        html = r.get_data(as_text=True)
        rows = _rows_by_display("مدل تست الفا")
        assert len(rows) == 1
        assert int(rows[0]["enabled"]) == 0
        assert rows[0]["last_status"] == "error"
        assert "تأیید نشد" in html and "HTTP 404" in html
        assert "متصل و تأیید شد" not in html
        print("PASS  شکست تست اتصال: ذخیره با وضعیت غیرفعال و بدون پیام موفقیت")
    finally:
        ai_brain._ENV_PATH = orig_env
        _cleanup()


def test_two_custom_instances_with_same_display_name_do_not_overwrite():
    app, client = _setup()
    orig_env = _env_guard()
    try:
        with mock.patch.object(ai_brain, "_ai_check_openai", _fake_check("ok", "m-one", ["m-one"])), \
                mock.patch.object(ai_brain, "_fetch_remote_models", _fake_fetch(items=[{"id": "m-one"}])):
            _add(client, {"provider": "custom", "display_name": "مدل تست الفا",
                          "api_key": "FAKE-KEY-FIRST", "base_url": BASE})
        first = _rows_by_display("مدل تست الفا")[0]
        with mock.patch.object(ai_brain, "_ai_check_openai", _fake_check("ok", "m-two", ["m-two"])), \
                mock.patch.object(ai_brain, "_fetch_remote_models", _fake_fetch(items=[{"id": "m-two"}])):
            _add(client, {"provider": "custom", "display_name": "مدل تست تکراری",
                          "api_key": "FAKE-KEY-SECOND", "base_url": BASE2})
        rows = _rows_by_display("مدل تست تکراری")
        assert len(rows) == 1 and rows[0]["name"] != first["name"]
        first_after = ai_brain.get_ai_provider(first["name"])
        assert first_after["api_key"] == "FAKE-KEY-FIRST"
        assert first_after["base_url"] == BASE
        assert first_after["selected_model"] == "m-one"
        assert rows[0]["api_key"] == "FAKE-KEY-SECOND" and rows[0]["base_url"] == BASE2
        print("PASS  دو نمونهٔ سرویس دلخواه مستقل هستند")
    finally:
        ai_brain._ENV_PATH = orig_env
        _cleanup()


def test_custom_invalid_input_creates_no_row():
    app, client = _setup()
    orig_env = _env_guard()
    try:
        cases = (
            {"provider": "custom", "display_name": "مدل تست الفا", "api_key": "K", "base_url": ""},
            {"provider": "custom", "display_name": "مدل تست الفا", "api_key": "K", "base_url": "http://plain.example/v1"},
            {"provider": "custom", "display_name": "مدل تست الفا", "api_key": "K",
             "base_url": "https://api.cloudflare.com/client/v4/accounts/abc/ai/v1"},
            {"provider": "custom", "display_name": "", "api_key": "K", "base_url": BASE},
            {"provider": "cloudflare", "display_name": "مدل تست الفا", "api_key": "K", "account_id": ""},
        )
        for data in cases:
            r = _add(client, data)
            assert r.status_code == 302
            assert _rows_by_display("مدل تست الفا") == [], data
        print("PASS  ورودی‌های نامعتبر هیچ ردیفی نمی‌سازند")
    finally:
        ai_brain._ENV_PATH = orig_env
        _cleanup()


def test_anonymous_cannot_add_provider():
    app, _client = _setup()
    anon = app.test_client()
    with anon.session_transaction() as s:
        s["giso_csrf_token"] = CSRF  # CSRF معتبر است؛ فقط نبود ورود باعث رد می‌شود
    orig_env = _env_guard()
    try:
        with mock.patch.object(ai_brain, "_ai_check_openai", _fake_check("ok", "m", ["m"])):
            r = anon.post("/admin/ai/provider/add", data={
                "csrf_token": CSRF, "provider": "custom", "display_name": "مدل تست الفا",
                "api_key": "K", "base_url": BASE}, headers={"X-GISO-CSRF": CSRF})
        assert r.status_code in (302, 401, 403)
        assert _rows_by_display("مدل تست الفا") == []
        print("PASS  کاربر غیرمجاز نمی‌تواند سرویس اضافه کند")
    finally:
        ai_brain._ENV_PATH = orig_env
        _cleanup()


def test_page_has_single_add_form_with_registry_choices_only():
    app, client = _setup()
    try:
        html = client.get("/admin/ai").get_data(as_text=True)
    finally:
        _cleanup()
    assert html.count("data-ai-provider-add-form>") == 1  # یک فرم واحد؛ JS هم این صفت را جستجو می‌کند
    start = html.index('data-provider-choice')
    select_html = html[start:html.index("</select>", start)]
    values = set(re.findall(r'<option value="([^"]*)"', select_html)) - {""}
    expected = {"cloudflare", "custom", "groq", "openrouter", "mistral", "gemini", "gapgpt", "avalai"}
    assert values == expected, values
    assert "value=\"cf\"" not in select_html and "value=\"cf1\"" not in html
    assert "سرویس دلخواه" in select_html
    for label in ("بررسی اتصال و افزودن حساب", "بررسی اتصال و افزودن سرویس", "تست اتصال و کشف مدل‌ها"):
        assert label in html, label
    assert 'name="account_id"' in html and 'name="base_url"' in html
    print("PASS  فرم واحد: فقط گزینه‌های رجیستری و سرویس دلخواه")


def test_cloudflare_without_account_id_is_rejected():
    app, client = _setup()
    orig_env = _env_guard()
    try:
        _add(client, {"provider": "cloudflare", "display_name": "مدل تست الفا", "api_key": "FAKE-CF-TOKEN"})
        assert _rows_by_display("مدل تست الفا") == []
        print("PASS  Cloudflare بدون Account ID ثبت نمی‌شود")
    finally:
        ai_brain._ENV_PATH = orig_env
        _cleanup()


def _run():
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    passed = 0
    for t in tests:
        try:
            t()
            passed += 1
        except AssertionError as e:
            print(f"FAIL  {t.__name__}: {e}")
        except Exception as e:
            print(f"ERROR {t.__name__}: {type(e).__name__}: {e}")
    print(f"\n{passed}/{len(tests)} passed")
    return passed == len(tests)


if __name__ == "__main__":
    sys.exit(0 if _run() else 1)
