# -*- coding: utf-8 -*-
"""giso/shop/bot/super_menu.py — منوی فروشگاه در ربات سوپرادمین (فاز B).

همه گزینه‌های ادمین + تنظیمات فروشگاه — بدون تکرار (reuse admin_menu).
"""
from giso.shop.bot.admin_menu import shop_admin_menu_text  # noqa: F401


def publish_toggle_label() -> str:
    """برچسب حالت انتشار AI/کانال؛ داخل «تنظیمات فروشگاه» مدیریت می‌شود، نه منوی اصلی."""
    try:
        from giso.shop.logic.channel_bridge import get_publish_mode
        mode = get_publish_mode()
    except Exception:
        mode = "review"
    return "🤖 تأیید محصول هوش مصنوعی: خودکار ⚡" if mode == "auto" else "🤖 تأیید محصول هوش مصنوعی: با تأیید ادمین ✋"


def shop_super_menu_text() -> str:
    return (
        "🛍 فروشگاه گیسو — پنل سوپرادمین\n"
        "━━━━━━━━━━━━━━━━\n"
        "🧾 سفارش‌های جدید\n"
        "📦 محصولات\n"
        "⏳ لیست محصولات منتظر تأیید\n"
        "📊 گزارش فروش\n"
        "🔍 جستجوی کد پیگیری\n"
        "━━━━━━━━━━━━━━━━\n"
        "گزینه مورد نظر را انتخاب کنید:"
    )


def shop_super_menu_kb():
    from telegram import KeyboardButton, ReplyKeyboardMarkup
    return ReplyKeyboardMarkup(
        [
            [KeyboardButton("🧾 سفارش‌های جدید"), KeyboardButton("📦 محصولات")],
            [KeyboardButton("⏳ لیست محصولات منتظر تأیید"), KeyboardButton("📊 گزارش فروش")],
            [KeyboardButton("🔍 جستجوی کد پیگیری")],
            [KeyboardButton("🔙 بازگشت")],
        ],
        resize_keyboard=True,
    )


def settings_text() -> str:
    from giso.shop.logic.channel_bridge import get_publish_mode
    from giso.shop.logic.inventory import _get_giso_config_safe
    mode = get_publish_mode()
    ch = _get_giso_config_safe("bale_channel_id", "")
    mode_fa = "🟢 خودکار" if mode == "auto" else "🔶 با تأیید ادمین"
    return (
        "⚙️ تنظیمات فروشگاه\n"
        "━━━━━━━━━━━━━━━━\n"
        f"📢 آیدی کانال بله: {ch or '—'}\n"
        f"🤖 حالت تأیید محصول هوش مصنوعی: {mode_fa}\n"
        "━━━━━━━━━━━━━━━━\n"
        "تنظیمات مدیریتی فروشگاه را از گزینه‌های زیر انجام دهید:"
    )


def settings_kb():
    """تنظیمات فروشگاه مطابق راهنمای Giso."""
    from telegram import InlineKeyboardButton, InlineKeyboardMarkup
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🤖 تأیید محصول هوش مصنوعی", callback_data="shop_cfg_pub")],
        [InlineKeyboardButton("📢 مدیریت کانال", callback_data="shop_cfg_channel")],
        [InlineKeyboardButton("🎁 کد تخفیف", callback_data="shop_cfg_discount")],
        [InlineKeyboardButton("🔙 بازگشت", callback_data="shop_back_menu")],
    ])


def referral_settings_text():
    """سازگاری عقب‌رو برای callbackهای ذخیره‌شده قدیمی."""
    return "ℹ️ برنامه معرفی و پورسانت متوقف شده است؛ هیچ اعتبار جدیدی از این مسیر ایجاد نمی‌شود."


def referral_settings_kb():
    """سازگاری عقب‌رو برای importهای قدیمی."""
    from telegram import InlineKeyboardButton, InlineKeyboardMarkup
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔙 بازگشت به تنظیمات", callback_data="shop_cfg_back")],
    ])


def channel_settings_text():
    """تنظیمات کانال فروشگاه."""
    from giso.shop.logic.inventory import _get_giso_config_safe
    ch = _get_giso_config_safe("bale_channel_id", "")
    return (
        "📢 تنظیمات کانال فروشگاه\n"
        "━━━━━━━━━━━━━━━━\n"
        f"آیدی فعلی کانال: {ch or 'تنظیم نشده'}\n"
        "━━━━━━━━━━━━━━━━\n"
        "برای تغییر، آیدی کانال بله را ارسال کنید:\n"
        "(مثال: @giso_shop یا -100123456)\n"
        "━━━━━━━━━━━━━━━━\n"
        "💡 ربات باید در کانال ادمین باشد."
    )


def discount_menu_text() -> str:
    """منوی کد تخفیف."""
    try:
        from giso.shop.logic.discount import list_discount_codes
        codes = list_discount_codes()
        active = sum(1 for c in codes if c.get("is_active"))
    except Exception:
        codes = []
        active = 0
    lines = [
        "🎁 مدیریت کد تخفیف",
        "━━━━━━━━━━━━━━━━",
        f"کل کدها: {len(codes)} | فعال: {active}",
        "━━━━━━━━━━━━━━━━",
        "از دکمه‌های زیر استفاده کنید:",
    ]
    return "\n".join(lines)


def discount_kb():
    """کیبورد مدیریت کد تخفیف."""
    from telegram import InlineKeyboardButton, InlineKeyboardMarkup
    try:
        from giso.shop.logic.discount import list_discount_codes
        codes = list_discount_codes()
    except Exception:
        codes = []
    rows = []
    for c in codes[:8]:
        status = "✅" if c.get("is_active") else "❌"
        dtype = "٪" if c.get("discount_type") == "percent" else "ت"
        rows.append([InlineKeyboardButton(
            f"{status} {c['code']} — {c.get('discount_value',0)}{dtype}",
            callback_data=f"shop_disc_toggle|{c['id']}"
        )])
    rows.append([InlineKeyboardButton("➕ افزودن کد تخفیف", callback_data="shop_disc_add")])
    rows.append([InlineKeyboardButton("🔙 بازگشت به تنظیمات", callback_data="shop_cfg_back")])
    return InlineKeyboardMarkup(rows)
