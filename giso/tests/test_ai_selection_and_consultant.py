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
