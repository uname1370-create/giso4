# -*- coding: utf-8 -*-
"""تست‌های اصلاح دو مورد: حفظ انتخاب مدیر در add_ai_provider(replace=True) و مشاور آینه.

همه‌چیز با دیتابیس موقت و فیک انجام می‌شود؛ هیچ تماس HTTP زنده‌ای وجود ندارد.
"""
import os
import sqlite3
import sys

os.environ.setdefault("SECRET_KEY", "arena-test-secret-for-buti-ai-tests-32chars")
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if BASE_DIR not in sys.path:
    sys.path.append(BASE_DIR)

import pytest  # noqa: E402

from giso import ai_brain  # noqa: E402


@pytest.fixture
def temp_ai_db(tmp_path, monkeypatch):
    db_path = tmp_path / "ai.db"

    def connect():
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        return conn

    monkeypatch.setattr(ai_brain, "get_conn", connect)
    ai_brain.init_ai_tables()
    return db_path


def _add(replace, **extra):
    base = dict(name="acme", kind="openai", api_key="key-one", base_url="https://example.invalid/v1",
                api_root="https://example.invalid/v1", enabled=True, replace=replace)
    base.update(extra)
    return ai_brain.add_ai_provider(**base)


def test_replace_without_model_keeps_admin_selection(temp_ai_db):
    assert _add(False, selected_model="admin-chosen-model") is True
    assert ai_brain.get_ai_provider("acme")["selected_model"] == "admin-chosen-model"

    # جایگزینی (مثل مسیر ربات) بدون مدل نباید انتخاب مدیر را با پیش‌فرض رجیستری عوض کند
    assert _add(True, api_key="key-two") is True
    row = ai_brain.get_ai_provider("acme")
    assert row["selected_model"] == "admin-chosen-model"
    assert row["api_key"] == "key-two"


def test_replace_with_explicit_model_still_updates_selection(temp_ai_db):
    assert _add(False, selected_model="old-model") is True
    assert _add(True, selected_model="new-model") is True
    assert ai_brain.get_ai_provider("acme")["selected_model"] == "new-model"


def test_consultant_helper_uses_text_only_on_success(monkeypatch):
    import giso.ai_runtime as runtime
    from giso.buti_ai import routes

    calls = []

    async def ok_chat(messages, actor_key, **kwargs):
        calls.append((messages, actor_key))
        return {"ok": True, "text": "  پاسخ مشاور  ", "error": ""}

    monkeypatch.setattr(runtime, "chat_with_managed_ai", ok_chat)
    assert routes._consultant_managed_text("سؤال") == "پاسخ مشاور"
    assert calls and calls[0][1] == "beauty_mirror"

    async def failing_chat(messages, actor_key, **kwargs):
        return {"ok": False, "text": "پیام خطا", "error": "HTTP 401: nope"}

    monkeypatch.setattr(runtime, "chat_with_managed_ai", failing_chat)
    # خطا: رشتهٔ خالی تا caller پاسخ جایگزین با context بدهد (متن خطا به کاربر نمی‌رود)
    assert routes._consultant_managed_text("سؤال") == ""


# ---------------------------------------------------------------------------
# حفظ تنظیمات مدیریت مرکزی (انتخاب، ترتیب fallback، فعال بودن، فهرست مدل‌ها)
# ---------------------------------------------------------------------------
import json  # noqa: E402

from giso.buti_ai import ai_models  # noqa: E402
from giso import ai_discovery  # noqa: E402
from giso.ai_models_registry import get_provider as _reg_provider  # noqa: E402


def _row(name):
    return ai_brain.get_ai_provider(name)


def _registry_ids(name):
    reg = _reg_provider(name)
    return [m["id"] for m in reg.get("vision_models", []) + reg.get("text_models", []) if m.get("id")]


def test_replace_keeps_admin_policy_fields_on_bot_readd(temp_ai_db):
    # تنظیم‌های مدیر: غیرفعال، انتخاب، ترتیب fallback، فهرست، timeout، هدر، پروکسی
    assert _add(False, name="groq", selected_model="admin-model", enabled=False,
                fallback_json=json.dumps(["m-b", "m-a"]),
                models_json=json.dumps(["m-a", "m-b", "m-c"]),
                timeout=45, headers_json=json.dumps({"X-Team": "one"}),
                is_iranian=False, use_proxy=True) is True
    # همان آرگومان‌های مسیر ربات برای افزودن مجدد (بدون enabled/timeout/... )
    assert ai_brain.add_ai_provider(name="groq", kind="openai", api_key="key-new",
                                    base_url="https://g.invalid/v1", api_root="https://g.invalid/v1",
                                    replace=True) is True
    row = _row("groq")
    assert row["api_key"] == "key-new"          # کلید/آدرس جدید اعمال می‌شود
    assert row["selected_model"] == "admin-model"
    assert row["enabled"] == 0                  # غیرفعال ماندن حفظ می‌شود
    assert json.loads(row["fallback_json"]) == ["m-b", "m-a"]
    assert json.loads(row["models_json"]) == ["m-a", "m-b", "m-c"]
    assert row["timeout"] == 45
    assert json.loads(row["headers_json"]) == {"X-Team": "one"}
    assert row["use_proxy"] == 1


def test_explicit_admin_changes_are_applied_on_replace(temp_ai_db):
    assert _add(False, name="groq", selected_model="m-a", enabled=True,
                fallback_json=json.dumps(["m-a"])) is True
    assert _add(True, name="groq", enabled=False, selected_model="m-a",
                fallback_json=json.dumps(["m-b", "m-a"]), timeout=30) is True
    row = _row("groq")
    assert row["enabled"] == 0
    assert json.loads(row["fallback_json"]) == ["m-b", "m-a"]
    assert row["timeout"] == 30
    assert row["selected_model"] == "m-a"


def test_new_rows_get_registry_defaults_and_existing_rows_are_not_overwritten(temp_ai_db):
    assert ai_brain.add_ai_provider(name="groq", kind="openai", api_key="k-1",
                                    base_url="https://g.invalid/v1", api_root="https://g.invalid/v1") is True
    row = _row("groq")
    assert row["enabled"] == 1
    assert row["timeout"] == _reg_provider("groq")["timeout"]
    assert json.loads(row["fallback_json"]) == json.loads(row["models_json"])
    assert json.loads(row["fallback_json"]), "فهرست پیش‌فرض رجیستری باید پر باشد"
    assert row["selected_model"] == ai_brain.default_models_for_provider("groq")[1]
    # ردیف موجود با replace=False (مسیر seed) بازنویسی نمی‌شود
    assert ai_brain.add_ai_provider(name="groq", kind="openai", api_key="k-other",
                                    base_url="https://other.invalid/v1", api_root="https://other.invalid/v1",
                                    replace=False) is False
    assert _row("groq")["api_key"] == "k-1"


def test_merge_fallback_order_rules():
    merge = ai_brain._merge_fallback_order
    assert merge(json.dumps(["c", "a"]), ["a", "b", "c"]) == ["c", "a", "b"]   # ترتیب مدیر + جدیدها
    assert merge(json.dumps(["c", "gone"]), ["a", "c"]) == ["c", "a"]          # مدل حذف‌شده بیرون
    assert merge("", ["a", "b"]) == ["a", "b"]                                  # ترتیب قبلی خالی
    assert merge("not-json", ["a"]) == ["a"]                                    # JSON خراب
    assert merge(json.dumps([{"id": "b"}, "a"]), ["a", "b"]) == ["b", "a"]     # آیتم دیکشنری


def test_registry_refresh_keeps_admin_fallback_order_and_drops_dead_models(temp_ai_db):
    ids = _registry_ids("groq")
    assert len(ids) >= 2
    admin_order = list(reversed(ids))
    assert _add(False, name="groq", selected_model=ids[0], models_source="",
                fallback_json=json.dumps(admin_order + ["dead-model-x"])) is True
    ai_brain._refresh_registry_sourced_models()
    row = _row("groq")
    assert json.loads(row["fallback_json"]) == admin_order     # ترتیب مدیر حفظ، مدل مرده حذف
    assert row["selected_model"] == ids[0]                     # انتخاب مدیر دست‌نخورده


def test_discovery_keeps_admin_fallback_order_and_selection(temp_ai_db, monkeypatch):
    import asyncio

    async def fake_fetch(row):
        return {"ok": True, "items": [{"id": "alpha-chat"}, {"id": "beta-chat"}, {"id": "gamma-chat"}]}

    monkeypatch.setattr(ai_brain, "_fetch_remote_models", fake_fetch)
    monkeypatch.setattr(ai_discovery, "smart_filter_models",
                        lambda name, items: ([], [{"id": i["id"]} for i in items]))
    monkeypatch.setattr(ai_discovery, "unfiltered_chat_models", lambda name, items: ([], []))
    assert _add(False, name="acme", selected_model="beta-chat", models_source="",
                fallback_json=json.dumps(["gamma-chat", "alpha-chat"])) is True
    report = asyncio.run(ai_discovery.discover_provider("acme"))
    assert report.get("ok") is True, report
    row = _row("acme")
    assert json.loads(row["fallback_json"]) == ["gamma-chat", "alpha-chat", "beta-chat"]
    assert row["selected_model"] == "beta-chat"                # کشف انتخاب مدیر را عوض نمی‌کند


def test_central_chain_skips_disabled_provider_and_incompatible_model(temp_ai_db, monkeypatch):
    assert _add(False, name="groq", enabled=True, selected_model="m-ok") is True
    assert _add(False, name="mistral", enabled=False, selected_model="m-off") is True
    assert _add(False, name="openrouter", enabled=True, selected_model="m-bad") is True
    slots = [
        {"provider_name": "groq", "model_name": "m-ok"},
        {"provider_name": "mistral", "model_name": "m-off"},
        {"provider_name": "openrouter", "model_name": "m-bad"},
        {"provider_name": "groq", "model_name": "m-unknown"},
    ]
    monkeypatch.setattr(ai_models, "list_model_assignments", lambda *a, **k: slots)
    statuses = {("openrouter", "m-bad"): ai_discovery.STATUS_INCOMPATIBLE,
                ("groq", "m-unknown"): ai_discovery.STATUS_UNKNOWN}
    monkeypatch.setattr(ai_discovery, "model_capability_for_provider",
                        lambda provider, model, capability: {"status": statuses.get((provider, model),
                                                                                   ai_discovery.STATUS_CONFIRMED)})
    chain = ai_models.configured_vision_chain(ai_models.TASK_EYEBROW_ANALYSIS)
    # غیرفعال و ناسازگار کنار می‌روند؛ unknown هرگز «آماده» نمی‌شود اما ناسازگار هم نیست و می‌ماند
    assert [c["model_name"] for c in chain] == ["m-ok", "m-unknown"]
    assert all(c["provider_name"] != "mistral" for c in chain)


def test_capability_lookup_error_does_not_block_slot(temp_ai_db, monkeypatch):
    assert _add(False, name="groq", enabled=True, selected_model="m-ok") is True
    monkeypatch.setattr(ai_models, "list_model_assignments",
                        lambda *a, **k: [{"provider_name": "groq", "model_name": "m-ok"}])

    def broken(provider, model, capability):
        raise RuntimeError("checks table missing")

    monkeypatch.setattr(ai_discovery, "model_capability_for_provider", broken)
    chain = ai_models.configured_vision_chain(ai_models.TASK_EYEBROW_ANALYSIS)
    assert [c["model_name"] for c in chain] == ["m-ok"]        # خطای بررسی، اسلات را حذف نمی‌کند
