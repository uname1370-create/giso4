# -*- coding: utf-8 -*-
"""Stage 8: Admin/SuperAdmin Bale integration and fail-closed callbacks."""
import asyncio
from pathlib import Path

from giso.beauty_centers import bot_handlers

ROOT = Path(__file__).resolve().parents[2]


class FakeMessage:
    def __init__(self):
        self.replies = []

    async def reply_text(self, text, **kwargs):
        self.replies.append((text, kwargs))


class FakeQuery:
    def __init__(self):
        self.message = FakeMessage()
        self.answers = []

    async def answer(self, text="", **kwargs):
        self.answers.append((text, kwargs))


def _labels(markup):
    return [button.text for row in markup.keyboard for button in row]


def test_admin_and_super_menus_have_exact_role_scopes():
    regular = _labels(bot_handlers.beauty_admin_menu_kb(False))
    super_labels = _labels(bot_handlers.beauty_admin_menu_kb(True))
    for label in ("📥 درخواست‌های جدید مرکز", "🏢 مراکز منتشرشده", "⏸ مراکز متوقف", "🚩 گزارش‌های مراکز"):
        assert label in regular and label in super_labels
    assert "⭐ معرفی ویژه مراکز" not in regular
    assert "⚙️ تنظیمات مراکز" not in regular
    assert "⭐ معرفی ویژه مراکز" in super_labels
    assert "⚙️ تنظیمات مراکز" in super_labels


def test_admin_text_handler_fails_closed_and_super_options_are_protected():
    guest = FakeMessage()
    handled = asyncio.run(bot_handlers.handle_beauty_admin_text(guest, "🏥 مراکز زیبایی"))
    assert handled and "فقط برای مدیران" in guest.replies[-1][0]

    admin = FakeMessage()
    handled = asyncio.run(bot_handlers.handle_beauty_admin_text(
        admin, "⭐ معرفی ویژه مراکز", is_admin=True,
    ))
    assert handled and "فقط برای سوپرادمین" in admin.replies[-1][0]

    super_message = FakeMessage()
    handled = asyncio.run(bot_handlers.handle_beauty_admin_text(
        super_message, "⚙️ تنظیمات مراکز", is_super=True,
    ))
    assert handled and "فاز تبلیغات آینده" in super_message.replies[-1][0]


def test_admin_callback_rejects_guest_and_malformed_payload(monkeypatch):
    calls = []
    monkeypatch.setattr(bot_handlers, "admin_set_status", lambda *args: calls.append(args))

    guest = FakeQuery()
    asyncio.run(bot_handlers.handle_beauty_admin_callback(guest, "bc_act|12|publish|0"))
    assert guest.answers and "فقط مدیران" in guest.answers[-1][0]
    assert not calls

    malformed = FakeQuery()
    asyncio.run(bot_handlers.handle_beauty_admin_callback(
        malformed, "bc_act|oops|publish|0", is_admin=True,
    ))
    assert malformed.answers and "نامعتبر" in malformed.answers[-1][0]
    assert not calls


def test_bot_dispatch_has_staff_guard_and_module_hooks():
    source = (ROOT / "giso/bot.py").read_text(encoding="utf-8")
    assert 'if data.startswith("bc_")' in source
    assert 'if not (_is_giso_admin(uid) or _is_super_admin(uid, phone))' in source
    assert "handle_beauty_admin_callback" in source
    assert "handle_beauty_admin_text" in source
    service = (ROOT / "giso/beauty_centers/services.py").read_text(encoding="utf-8")
    assert "notify_center_owner(updated" in service
    assert "category=\"beauty_centers\"" in service
