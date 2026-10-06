# -*- coding: utf-8 -*-
"""Navigation and role policy for the normal-user dashboard.

Only ``USER_MODULES`` is visible in the sidebar.  Extra metadata is retained so
bookmarked legacy routes continue to render without becoming separate menu
entries again.
"""
import logging

from giso.base import normalize_phone
from giso.config import is_super_admin

logger = logging.getLogger("giso_panel_user_permissions")

# Seven visible top-level choices. Hair tools are stacked as sibling links
# (فروش مو / بازارچه / خریدار) without a drawer.
# FINBUTI — Beauty Ecosystem 4-Panel: Customer → پیشخوان → زیبایی من → سالن‌های زیبایی/نوبت‌ها/گفتگوها/آنالیزها
# Owner → مدیریت سالن زیبایی جدا از زیبایی من (مالک همزمان Customer است)
USER_MODULES = [
    ("overview", "پیشخوان (خلاصه من)", "🏠"),
    ("beauty_centers_list", "سالن‌های زیبایی", "🏥"),
    ("reservations", "نوبت‌های من", "📅"),
    ("center_chats", "گفتگوهای من", "💌"),
    ("analyses", "آنالیزهای من", "🔬"),
    ("beauty_center", "مدیریت سالن زیبایی", "🏢"),
    ("hair_sale", "مدیریت مو", "💇‍♀️"),
    ("orders", "خریدهای من از فروشگاه", "🛍️"),
    ("marketplace", "بازارچه مو", "🏪"),
    ("wallet", "کیف پول و اعتبار", "💰"),
    ("chats", "پیام‌ها و پشتیبانی", "💬"),
    ("profile", "پروفایل", "👤"),
]

# گروه‌بندی منو بر اساس سفر کاربر (سناریوی Master Guide §۷ + FINBUTI)
# FINBUTI final menu: پیشخوان → زیبایی من [سالن‌ها/نوبت‌ها/گفتگوها/آنالیزها] → مدیریت سالن (فقط مالک) → فروش مو → خریدها → کیف پول → پیام‌ها → پروفایل
USER_MODULE_GROUPS = {
    "اصلی": ["overview"],
    "زیبایی من": ["beauty_centers_list", "reservations", "center_chats", "analyses"],
    "مدیریت سالن زیبایی": ["beauty_center"],
    "فروش مو": ["hair_sale", "marketplace", "buyer_request"],
    "خریدها": ["orders"],
    "کیف پول و اعتبار": ["wallet"],
    "پیام‌ها و پشتیبانی": ["chats", "ai_assistant", "notifications"],
    "حساب کاربری": ["profile"],
}

MODULES_META = {
    **{m: (label, icon) for m, label, icon in USER_MODULES},
    "marketplace": ("بازارچه مو", "🏪"),
    "buyer_request": ("خریدار مو", "🧑‍💼"),
    "beauty_center": ("مدیریت سالن زیبایی", "🏢"),
    "beauty_centers_list": ("سالن‌های زیبایی", "🏥"),
    "shop": ("فروشگاه من", "🛒"),
    "notifies": ("اعلان موجودی", "🔔"),
    "wishlist": ("علاقه‌مندی‌ها", "❤️"),
    "notifications": ("اعلان‌های من", "📣"),
    "reviews": ("نظرها و امتیازها", "⭐"),
    "reservations": ("نوبت‌های من", "📅"),
    "center_chats": ("گفتگوهای من", "💌"),
    # دستیار هوشمند سایت در پنل کاربر؛ فقط متادیتا — به USER_MODULES اضافه نشده تا
    # طیف اصلی منو حفظ شود و لینک آن از سایدبار به‌صورت اختصاصی داده شود.
    "ai_assistant": ("دستیار هوشمند گیسو", "🤖"),
}
# برچسب روایت‌محور سایدبار برای گروه خدمات (§۷)
MODULES_META["hair_sale"] = ("فروش مو به گیسو", "💇‍♀️")


def is_admin_user(phone_norm: str) -> bool:
    """آیا این شماره ادمین/سوپرادمین است؟"""
    phone_norm = normalize_phone(phone_norm)
    if not phone_norm:
        return False
    if is_super_admin(phone=phone_norm):
        return True
    try:
        from giso_admin import find_giso_admin_by_phone
        return bool(find_giso_admin_by_phone(phone_norm))
    except Exception:
        return False


def current_user_role():
    """نقش کاربر جاری: 'user' | 'admin' | 'super'."""
    try:
        from flask_login import current_user
        if not current_user or not current_user.is_authenticated:
            return "guest"
        phone = normalize_phone(getattr(current_user, "phone", "") or "")
        if is_super_admin(phone=phone):
            return "super"
        try:
            from giso_admin import find_giso_admin_by_phone
            if find_giso_admin_by_phone(phone):
                return "admin"
        except Exception:
            pass
        return "user"
    except Exception:
        return "guest"


__all__ = ["USER_MODULES", "USER_MODULE_GROUPS", "MODULES_META", "is_admin_user", "current_user_role"]
