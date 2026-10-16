# -*- coding: utf-8 -*-
"""نمونه‌های مستقل Provider: هر ثبت شناسهٔ داخلی یکتا دارد و نمونه‌های دیگر را تغییر نمی‌دهد.

پوشش:
- خانواده (family) از روی شناسهٔ داخلی؛ Cloudflare چند حساب زیر یک خانواده.
- سرویس رجیستری با نام نمایشی جدا از شناسهٔ داخلی؛ ویرایش و حذف فقط یک نمونه را تغییر می‌دهد.
- شکست تأیید اتصال هرگز ردیف را فعال یا موفق ثبت نمی‌کند.
- کشف مدل‌ها (refresh) هرگز selected_model را تغییر نمی‌دهد.
- Cloudflare در کشف، قیمت رایگان ادعا نمی‌کند (price_status = unknown).

هیچ درخواست شبکهٔ واقعی ارسال نمی‌شود؛ تماس‌های شبکه با mock جایگزین شده‌اند.
هر تست وضعیت جدول‌های Provider را قبل از اجرا ذخیره و بعد از آن بازمی‌گرداند.
"""
import asyncio
import json
import os
import sys
import tempfile
import time
from pathlib import Path
from unittest import mock

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if BASE_DIR not in sys.path:
    sys.path.append(BASE_DIR)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import ai_db_snapshot as _snap  # noqa: E402
from giso.app import create_app  # noqa: E402
from giso.models import db, User  # noqa: E402
from giso.base import normalize_phone  # noqa: E402
from giso import ai_brain  # noqa: E402
from giso.ai_brain import (  # noqa: E402
    create_provider_instance, finalize_provider_instance, provider_family_of,
    list_ai_providers, get_ai_provider, delete_ai_provider, check_ai_provider,
    refresh_models,
)
from giso.buti_ai.ai_models import _is_cloudflare_provider_name  # noqa: E402

SUPER_PHONE = normalize_phone("09156012931")
CSRF = "fixed-test-csrf-token"
GROQ_BASE = "https://api.groq.com/openai/v1"
CF_RUN = "https://api.cloudflare.com/client/v4/accounts/{account_id}/ai/run"
CF_ACC_A = "acctaaaa0001"
CF_ACC_B = "acctbbbb0002"
CUSTOM_BASE = "https://api.instances-test.example/v1"


def _fake_check(status="ok", selected="", models=(), error=""):
    async def _check(row):
        return {"status": status, "error": error, "models": list(models), "selected": selected}
    return _check


def _fake_fetch(items=None):
    async def _fetch(row):
        return {"ok": True, "items": list(items or [])}
    return _fetch


class _Guard:
    """مسیر .env را به فایل موقت می‌برد تا فایل واقعی هرگز تغییر نکند."""

    def __enter__(self):
        self._orig = ai_brain._ENV_PATH
        ai_brain._ENV_PATH = Path(tempfile.mkdtemp()) / ".env"
        self._state = _snap.snapshot()
        return self

    def __exit__(self, *exc):
        ai_brain._ENV_PATH = self._orig
        _snap.restore(self._state)
        return False


def _run(coro):
    return asyncio.new_event_loop().run_until_complete(coro)


def _login(client):
    with client.session_transaction() as s:
        s["giso_csrf_token"] = CSRF
        s["_user_id"] = SUPER_PHONE
        s["admin_panel_verified_phone"] = SUPER_PHONE
        s["admin_panel_verified_until"] = int(time.time()) + 1800


def test_family_is_derived_from_internal_id():
    with _Guard():
        name = create_provider_instance("custom", "نمونه تست یک", "FAKE-CUSTOM-KEY", CUSTOM_BASE,
                                        kind="openai", models_source="discovered")
        assert provider_family_of(name) == "custom"
        assert provider_family_of("cf") == "cloudflare"
        assert provider_family_of("cf2") == "cloudflare"
        assert provider_family_of("cloudflare") == "cloudflare"
        assert provider_family_of("groq") == "groq"
        assert provider_family_of("my-private-service") == "my-private-service"
        print("PASS  خانواده از شناسهٔ داخلی به‌درستی استخراج می‌شود")


def test_registry_instances_have_separate_display_names_and_keys():
    with _Guard():
        first = create_provider_instance("groq", "نمونه تست یک", "FAKE-GROQ-KEY-ONE", GROQ_BASE,
                                         kind="openai", models_source="registry")
        second = create_provider_instance("groq", "نمونه تست دو", "FAKE-GROQ-KEY-TWO", GROQ_BASE,
                                          kind="openai", models_source="registry")
        assert first != second, "نمونهٔ دوم نباید اولی را بازنویسی کند"
        a, b = get_ai_provider(first), get_ai_provider(second)
        assert a["display_name"] == "نمونه تست یک" and b["display_name"] == "نمونه تست دو"
        assert a["api_key"] == "FAKE-GROQ-KEY-ONE" and b["api_key"] == "FAKE-GROQ-KEY-TWO"
        assert a["base_url"] == GROQ_BASE and b["base_url"] == GROQ_BASE  # از رجیستری
        assert provider_family_of(first) == provider_family_of(second) == "groq"
        assert int(a["enabled"]) == 0 and int(b["enabled"]) == 0  # تا تأیید اتصال فعال نمی‌شود
        print("PASS  دو نمونهٔ رجیستری با نام و کلید جدا ساخته شدند")


def test_edit_and_delete_touch_only_one_instance():
    with _Guard():
        a = create_provider_instance("groq", "نمونه تست یک", "FAKE-A", GROQ_BASE, kind="openai",
                                     models_source="registry")
        b = create_provider_instance("groq", "نمونه تست دو", "FAKE-B", GROQ_BASE, kind="openai",
                                     models_source="registry")
        assert ai_brain.update_ai_provider_field(a, "api_key", "FAKE-A-CHANGED") is True
        assert get_ai_provider(a)["api_key"] == "FAKE-A-CHANGED"
        assert get_ai_provider(b)["api_key"] == "FAKE-B", "ویرایش نمونهٔ A نباید B را تغییر دهد"
        assert delete_ai_provider(a) is True
        assert get_ai_provider(a) is None
        assert get_ai_provider(b) is not None and get_ai_provider(b)["api_key"] == "FAKE-B"
        print("PASS  ویرایش و حذف فقط روی یک نمونه اثر دارند")


def test_cloudflare_accounts_group_under_one_family_with_own_account():
    with _Guard():
        a = create_provider_instance("cloudflare", "CF تست A", "FAKE-CF-A",
                                     CF_RUN.format(account_id=CF_ACC_A), kind="cloudflare",
                                     models_source="registry")
        b = create_provider_instance("cloudflare", "CF تست B", "FAKE-CF-B",
                                     CF_RUN.format(account_id=CF_ACC_B), kind="cloudflare",
                                     models_source="registry")
        assert a != b and not {a, b} & {"cf", "cf1", "cf2", "cf3"}
        assert provider_family_of(a) == provider_family_of(b) == "cloudflare"
        assert _is_cloudflare_provider_name(a) and _is_cloudflare_provider_name(b)
        assert CF_ACC_A in get_ai_provider(a)["base_url"] and CF_ACC_B in get_ai_provider(b)["base_url"]
        assert get_ai_provider(a)["api_key"] == "FAKE-CF-A" and get_ai_provider(b)["api_key"] == "FAKE-CF-B"
        print("PASS  چند حساب Cloudflare هر کدام شناسه، توکن و Account ID خودشان را دارند")


def test_failed_verification_never_enables_or_marks_success():
    with _Guard():
        name = create_provider_instance("custom", "نمونه تست یک", "FAKE-KEY", CUSTOM_BASE,
                                        kind="openai", models_source="discovered")
        with mock.patch.object(ai_brain, "_ai_check_openai",
                               _fake_check("error", "", [], "HTTP 401: invalid key")):
            res = _run(check_ai_provider(name))
        row = get_ai_provider(name)
        assert res["status"] == "error"
        assert int(row["enabled"]) == 0
        assert row["last_status"] == "error"
        assert row["selected_model"] in ("", None)
        finalize_provider_instance(name, False, "")
        assert int(get_ai_provider(name)["enabled"]) == 0
        print("PASS  شکست تأیید هرگز ردیف را فعال یا موفق ثبت نمی‌کند")


def test_successful_verification_sets_selected_only_from_real_answer():
    with _Guard():
        name = create_provider_instance("custom", "نمونه تست یک", "FAKE-KEY", CUSTOM_BASE,
                                        kind="openai", models_source="discovered")
        with mock.patch.object(ai_brain, "_ai_check_openai",
                               _fake_check("ok", "answering-model", ["answering-model"])):
            res = _run(check_ai_provider(name))
        finalize_provider_instance(name, res["status"].startswith("ok"), res.get("selected") or "")
        row = get_ai_provider(name)
        assert int(row["enabled"]) == 1 and row["last_status"] == "ok"
        assert row["selected_model"] == "answering-model"
        print("PASS  موفقیت فقط با پاسخ واقعی ثبت می‌شود")


def test_discovery_never_changes_selected_model():
    with _Guard():
        name = create_provider_instance("custom", "نمونه تست یک", "FAKE-KEY", CUSTOM_BASE,
                                        kind="openai", models_source="discovered")
        ai_brain.update_ai_provider_field(name, "selected_model", "manual-pick")
        with mock.patch.object(ai_brain, "_fetch_remote_models",
                               _fake_fetch(items=[{"id": "discovered-vision-x"}, {"id": "discovered-text-y"}])):
            res = refresh_models(name)
        assert res.get("ok") is True, res
        row = get_ai_provider(name)
        assert row["selected_model"] == "manual-pick", "کشف مدل نباید selected_model را تغییر دهد"
        assert "discovered-vision-x" in (row["vision_models_json"] or "")
        assert "discovered-text-y" in (row["text_models_json"] or "")
        print("PASS  کشف مدل‌ها selected_model را تغییر نمی‌دهد")


def test_cloudflare_discovery_does_not_claim_free():
    with _Guard():
        name = create_provider_instance("cloudflare", "CF تست A", "FAKE-CF-A",
                                        CF_RUN.format(account_id=CF_ACC_A), kind="cloudflare",
                                        models_source="registry")
        res = refresh_models(name)
        assert res.get("ok") is True, res
        row = get_ai_provider(name)
        entries = json.loads(row["vision_models_json"] or "[]") + json.loads(row["text_models_json"] or "[]")
        assert entries, "فهرست مدل Cloudflare خالی است"
        for item in entries:
            assert isinstance(item, dict) and item.get("price_status") == "unknown", item
        print("PASS  Cloudflare قیمت رایگان ادعا نمی‌کند")


def test_duplicate_cloudflare_account_is_refused_from_panel():
    app = create_app()
    with app.app_context():
        if not User.query.filter_by(phone=SUPER_PHONE).first():
            db.session.add(User(phone=SUPER_PHONE, password_hash="hash", name="تست"))
            db.session.commit()
    client = app.test_client()
    _login(client)
    with _Guard():
        name = create_provider_instance("cloudflare", "CF تست A", "FAKE-CF-A",
                                        CF_RUN.format(account_id=CF_ACC_A), kind="cloudflare",
                                        models_source="registry")
        before = len(list_ai_providers())
        with mock.patch.object(ai_brain, "_ai_check_cloudflare", _fake_check("ok", "m", ["m"])):
            r = client.post("/admin/ai/provider/add", data={
                "csrf_token": CSRF, "provider": "cloudflare", "display_name": "CF تست B",
                "api_key": "FAKE-CF-DUP", "account_id": CF_ACC_A},
                headers={"X-GISO-CSRF": CSRF}, follow_redirects=True)
        html = r.get_data(as_text=True)
        assert len(list_ai_providers()) == before, "Account ID تکراری نباید ردیف بسازد"
        assert "قبلاً" in html
        assert get_ai_provider(name)["api_key"] == "FAKE-CF-A"
        print("PASS  Account ID تکراری از پنل رد می‌شود")


def test_panel_cards_show_display_name_and_internal_id():
    app = create_app()
    with app.app_context():
        if not User.query.filter_by(phone=SUPER_PHONE).first():
            db.session.add(User(phone=SUPER_PHONE, password_hash="hash", name="تست"))
            db.session.commit()
    client = app.test_client()
    _login(client)
    with _Guard():
        name = create_provider_instance("custom", "نمونه تست صفحه", "FAKE-KEY", CUSTOM_BASE,
                                        kind="openai", models_source="discovered")
        html = client.get("/admin/ai").get_data(as_text=True)
        assert "نمونه تست صفحه" in html
        assert f"[{name}]" in html
        print("PASS  کارت Provider نام نمایشی و شناسهٔ داخلی را جدا نشان می‌دهد")


def test_every_registry_provider_add_uses_registry_defaults():
    """هر سرویس رجیستری از فرم واحد با تنظیمات رجیستری ثبت می‌شود (شبکه mock است؛ تست زنده نیست)."""
    from unittest import mock
    from giso.ai_models_registry import get_provider as _reg_get
    app = create_app()
    with app.app_context():
        if not User.query.filter_by(phone=SUPER_PHONE).first():
            db.session.add(User(phone=SUPER_PHONE, password_hash="hash", name="تست"))
            db.session.commit()
    client = app.test_client()
    _login(client)
    with _Guard():
        for key in ("groq", "openrouter", "mistral", "gemini", "gapgpt", "avalai"):
            reg = _reg_get(key)
            expected_base = ai_brain._normalize_gemini_base_url(reg["base_url"]) if key == "gemini" else reg["base_url"]
            label = f"تست {key}"
            with mock.patch.object(ai_brain, "_ai_check_openai", _fake_check("ok", "reg-model", ["reg-model"])), \
                    mock.patch.object(ai_brain, "_fetch_remote_models", _fake_fetch(items=[])):
                client.post("/admin/ai/provider/add", data={
                    "csrf_token": CSRF, "provider": key, "display_name": label,
                    "api_key": f"FAKE-{key}-KEY"}, headers={"X-GISO-CSRF": CSRF})
            rows = [x for x in list_ai_providers() if x["display_name"] == label]
            assert len(rows) == 1, (key, len(rows))
            row = rows[0]
            assert provider_family_of(row["name"]) == key, row["name"]
            assert row["base_url"] == expected_base, (key, row["base_url"])
            assert row["api_key"] == f"FAKE-{key}-KEY"
            assert int(row["enabled"]) == 1 and row["last_status"] == "ok", key
            assert row["selected_model"] == "reg-model"
    print("PASS  هر ۶ سرویس غیر-Cloudflare رجیستری با مقادیر رجیستری ثبت شدند")


def _run_tests():
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
    sys.exit(0 if _run_tests() else 1)
