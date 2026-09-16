#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Regression tests for removal of the four permission-configuration menus."""
import asyncio
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.append(str(ROOT))

from giso.bot import _admin_kb, _admin_mgmt_kb, get_test_handlers
from giso.bot_hair_admin import build_admin_hair_menu, order_action_kb
from giso.panel import authz
from giso.panel.permissions import module_allowed
from giso.shop.bot.super_menu import settings_kb

ROOT = Path(__file__).resolve().parents[2]
REGULAR_ID = 777001
SUPER_ID = 1191639507
SIMPLIFIED = "این تنظیمات ساده‌سازی شده است"


def _reply_labels(markup):
    return [button.text for row in markup.keyboard for button in row]


def _inline_labels(markup):
    return [button.text for row in markup.inline_keyboard for button in row]


def test_removed_configuration_buttons_and_preserved_admin_queue():
    assert "🛡 دسترسی ادمین‌ها" not in _reply_labels(_admin_mgmt_kb())
    admin_labels = _reply_labels(_admin_mgmt_kb())
    assert "🔑 تنظیم کلمه ادمینی" in admin_labels
    assert "📥 بررسی درخواست‌ها" in admin_labels
    assert "📋 لیست ادمین‌ها" in admin_labels

    assert "⚙️ تنظیمات دسترسی ادمین‌ها" not in _reply_labels(
        build_admin_hair_menu(REGULAR_ID)
    )
    assert "👁 دسترسی ادمین‌های معمولی" not in _inline_labels(settings_kb())

    html = (ROOT / "giso/panel/templates/modules/admins.html").read_text(encoding="utf-8")
    assert 'data-pane="access"' not in html
    assert 'id="pane-access"' not in html
    assert "save_permissions" not in html
    assert "📥 درخواست‌ها" in html
    assert "🔑 کلمه ادمینی" in html


def test_regular_admin_fixed_operational_menu_and_sensitive_absence():
    labels = _reply_labels(_admin_kb(REGULAR_ID))
    assert labels == ["💇 خرید مو", "🛍 فروشگاه", "🏪 بازارچه", "💬 مدیریت گفتگوها"]


def test_hair_operational_actions_ignore_legacy_visibility_payload():
    # A cached/legacy false payload must not hide day-to-day Hair actions.
    kb = order_action_kb(42, {
        "bot_review_visible": False,
        "bot_reject_visible": False,
        "bot_price_visible": False,
        "bot_message_visible": False,
    }, status="pending")
    labels = _inline_labels(kb)
    assert "🔍 در حال بررسی" in labels
    assert "❌ رد سفارش" in labels
    assert "💰 ثبت قیمت نهایی" in labels
    assert "💬 پیام به مشتری" in labels


async def _dispatch_stale(data):
    handlers = await get_test_handlers()
    query = MagicMock()
    query.data = data
    query.answer = AsyncMock()
    query.edit_message_text = AsyncMock()
    query.message = MagicMock()
    query.message.reply_text = AsyncMock()
    update = MagicMock()
    update.callback_query = query
    update.effective_user.id = REGULAR_ID
    context = MagicMock()
    context.user_data = {}
    context.bot.send_message = AsyncMock()
    await handlers["handle_callback"](update, context)
    return query


def test_stale_bot_permission_callbacks_fail_closed_with_exact_message():
    for data in ("adm_perm_toggle|7|orders", "badm|toggle|7|hair_sale|price",
                 "shop_cfg_visibility", "shop_vis_toggle|orders"):
        query = asyncio.run(_dispatch_stale(data))
        query.answer.assert_awaited_once_with(SIMPLIFIED, show_alert=True)
        query.edit_message_text.assert_not_awaited()


def test_stale_reply_keyboard_labels_fail_closed_with_exact_message():
    async def run_label(label):
        handlers = await get_test_handlers()
        msg = MagicMock()
        msg.text = label
        msg.reply_text = AsyncMock()
        update = MagicMock()
        update.effective_user.id = SUPER_ID
        update.effective_user.first_name = "سوپر"
        update.effective_user.username = "super"
        update.effective_message = msg
        update.message = msg
        update.effective_chat.id = SUPER_ID
        context = MagicMock()
        context.user_data = {}
        context.bot.send_message = AsyncMock()
        await handlers["handle_text"](update, context)
        assert any(call.args and call.args[0] == SIMPLIFIED for call in msg.reply_text.await_args_list)

    for label in ("🛡 دسترسی ادمین‌ها", "⚙️ تنظیمات دسترسی ادمین‌ها",
                  "👁 دسترسی ادمین‌های معمولی"):
        asyncio.run(run_label(label))


def test_stale_shop_sensitive_input_states_fail_closed_for_normal_admin():
    from giso.shop.bot.handlers import handle_shop_bot_text

    async def run_state(state, text):
        msg = MagicMock()
        msg.reply_text = AsyncMock()
        states = {REGULAR_ID: state}
        handled = await handle_shop_bot_text(
            msg, text, REGULAR_ID, "+989120000001", {"is_admin": True}, states, MagicMock()
        )
        return handled, msg, states

    for state in ("shop_channel_input", "shop_ref_amount_input", "shop_ref_max_input"):
        handled, msg, states = asyncio.run(run_state(state, "999"))
        assert handled is True
        assert REGULAR_ID not in states
        assert "منوی قدیمی" in msg.reply_text.await_args.args[0]


def test_fixed_panel_policy_allows_operations_and_blocks_sensitive_modules(monkeypatch):
    operational = {
        "dashboard", "hair_sale", "marketplace", "shop_orders",
        "products", "reviews", "consults", "account",
    }
    sensitive = {
        "referrals", "wallet", "admins", "settings", "shop_super", "reports",
        "ai", "ratelimit", "users", "channel", "analyses", "notifications", "shop",
    }
    for module in operational:
        assert module_allowed(module, "admin", {}) is True
    for module in sensitive:
        assert module_allowed(module, "admin", {}) is False

    monkeypatch.setattr(authz, "current_role_and_perms", lambda: ("admin", {}, "7"))
    for action in (
        "hair.update_status", "hair.set_price", "hair.set_note", "hair.message",
        "shop.order_status", "shop.product_publish", "shop.product_reject",
    ):
        assert authz.can_execute_panel_action(action)[0] is True
    for action in (
        "hair.commission", "hair.prices_config", "shop.channel_config", "shop.publish_mode",
        "shop.product_add", "shop.product_edit", "shop.product_stock", "shop.product_delete",
        "shop.stats",
    ):
        assert authz.can_execute_panel_action(action)[0] is False


def test_legacy_permission_modules_are_inert_and_startup_safe():
    import giso.admin_access_schema as access_schema
    import giso.bot_permissions as bot_permissions

    assert access_schema.ADMIN_ACCESS_SCHEMA == {}
    assert access_schema.section_options("hair_sale", "site") == []
    assert bot_permissions.CONFIGURABLE_SECTIONS == ()

    bot_source = (ROOT / "giso/bot.py").read_text(encoding="utf-8")
    app_source = (ROOT / "giso/app.py").read_text(encoding="utf-8")
    models_source = (ROOT / "giso/models.py").read_text(encoding="utf-8")
    assert "giso_admin_permissions" not in bot_source
    assert "giso_admin_permissions" not in app_source
    assert "giso_admin_permissions" not in models_source


def test_marketplace_normal_admin_has_status_work_but_no_permanent_delete():
    source = (ROOT / "giso/panel/modules/marketplace.py").read_text(encoding="utf-8")
    action_pos = source.index("def handle_listing_action")
    block = source[action_pos:action_pos + 1500]
    for action in ("approve", "reject", "pause", "close"):
        assert f'action == "{action}"' in block
    assert 'action == "delete"' not in block
    assert "listing.deleted_at =" not in block


if __name__ == "__main__":
    tests = [value for name, value in sorted(globals().items()) if name.startswith("test_")]
    for test in tests:
        if "monkeypatch" in test.__code__.co_varnames:
            continue
        test()
    print("permission-removal tests passed")
