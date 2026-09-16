# -*- coding: utf-8 -*-
"""سه باگ حیاتی دسترسی ادمین عادی: stub مرده، فروشگاه، آنالیز."""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BOT = (ROOT / "giso/bot.py").read_text(encoding="utf-8")
HANDLERS_SRC = (ROOT / "giso/shop/bot/handlers.py").read_text(encoding="utf-8")
ADMIN_MENU_SRC = (ROOT / "giso/shop/bot/admin_menu.py").read_text(encoding="utf-8")
PERMS = (ROOT / "giso/panel/permissions.py").read_text(encoding="utf-8")
SUPER_MENU_SRC = (ROOT / "giso/shop/bot/super_menu.py").read_text(encoding="utf-8")


def test_bug1_deleted_inbox_stub_before_any_live_handler():
    stub = BOT.find('if text in ("📬 صندوق اعلان کار من", "✅ اقدام سریع", "💬 پاسخ به کاربر")')
    assert stub != -1
    assert 'await msg.reply_text("این گزینه حذف شده است."' in BOT[stub:stub + 280]
    assert 'if runtime_role == "admin" and text == "📬 صندوق اعلان کار من"' not in BOT
    assert 'if runtime_role == "admin" and text == "✅ اقدام سریع"' not in BOT
    assert 'if runtime_role == "admin" and text == "💬 پاسخ به کاربر"' not in BOT
    kb_fn = BOT[BOT.find("def _admin_kb"):BOT.find("def _admin_analysis_group_kb")]
    assert 'KeyboardButton("📬 صندوق اعلان کار من")' not in kb_fn
    assert 'KeyboardButton("✅ اقدام سریع")' not in kb_fn
    assert 'KeyboardButton("💬 پاسخ به کاربر")' not in kb_fn
    assert 'KeyboardButton("💇 خرید مو")' in kb_fn
    assert 'KeyboardButton("🛍 فروشگاه")' in kb_fn
    assert 'KeyboardButton("🏪 بازارچه")' in kb_fn
    assert 'KeyboardButton("💬 مدیریت گفتگوها")' in kb_fn


def test_bug2_regular_admin_shop_menu_has_no_catalog_or_stats():
    assert 'KeyboardButton("📦 محصولات")' not in ADMIN_MENU_SRC
    assert 'KeyboardButton("📊 گزارش فروش")' not in ADMIN_MENU_SRC
    assert 'KeyboardButton("🧾 سفارش‌های جدید")' in ADMIN_MENU_SRC
    assert 'KeyboardButton("🔍 جستجوی کد پیگیری")' in ADMIN_MENU_SRC
    assert '"📦 محصولات\\n"' not in ADMIN_MENU_SRC
    assert '"📊 گزارش فروش\\n"' not in ADMIN_MENU_SRC
    assert 'KeyboardButton("📦 محصولات")' in SUPER_MENU_SRC or '"📦 محصولات"' in SUPER_MENU_SRC
    assert '📊 گزارش فروش' in SUPER_MENU_SRC
    assert '"📦 محصولات", "📊 گزارش فروش"' in HANDLERS_SRC
    assert '"shop_rep|"' in HANDLERS_SRC
    assert 'REGULAR_ADMIN_SECTIONS = frozenset({\n    "dashboard", "orders", "hair_sale", "marketplace", "beauty_centers", "reviews",\n    "consults", "account",\n})' in PERMS
    assert '"products"' not in PERMS[PERMS.find("REGULAR_ADMIN_SECTIONS"):PERMS.find("REGULAR_ADMIN_MODULES")]
    assert '"shop"' in PERMS[PERMS.find("SUPER_ONLY_MODULES"):PERMS.find("def get_admin_target")]
    assert '"analyses"' in PERMS[PERMS.find("SUPER_ONLY_MODULES"):PERMS.find("def get_admin_target")]


def test_bug3_analysis_is_super_only_on_bot_and_site():
    body = BOT[BOT.find("def _admin_has_analysis_access"):BOT.find("async def handle_admin_analysis_menu")]
    assert "return bool(_is_super_admin(uid))" in body
    assert "_is_giso_admin(uid)" not in body
    kb_fn = BOT[BOT.find("def _admin_kb"):BOT.find("def _admin_analysis_group_kb")]
    # آنالیز فقط در شاخه سوپر
    super_part, _, regular_part = kb_fn.partition("keyboard = [")
    regular_block = regular_part  # second assignment is regular admin
    # first keyboard after if super
    first_kb = kb_fn.split("keyboard = [", 1)[1]
    super_kb, _, rest = first_kb.partition("keyboard = [")
    assert 'KeyboardButton("🔬 آنالیز")' in super_kb
    assert 'KeyboardButton("🔬 آنالیز")' not in rest
    assert '"analyses"' in PERMS[PERMS.find("SUPER_ONLY_MODULES"):PERMS.find("def get_admin_target")]
