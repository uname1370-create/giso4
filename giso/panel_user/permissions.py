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
USER_MODULES = [
    ("overview", "پیشخوان (خلاصه من)", "🏠"),
    ("hair_sale", "مدیریت مو", "💇‍♀️"),
    ("orders", "خریدهای من از فروشگاه", "🛍️"),
    ("analyses", "آنالیزها و برنامه من", "🔬"),
    ("reservations", "نوبت‌های من", "📅"),
    ("center_chats", "پیام‌های مرکز", "💌"),
    ("wallet", "کیف پول و اعتبار", "💰"),
    ("chats", "پیام‌ها و پشتیبانی", "💬"),
    ("profile", "پروفایل", "👤"),
]

# گروه‌بندی منو بر اساس سفر کاربر (سناریوی Master Guide §۷)
USER_MODULE_GROUPS = {
    "اصلی": ["overview", "orders", "notifications"],
    "خدمات": ["hair_sale", "marketplace", "buyer_request", "analyses", "beauty_center", "reservations", "center_chats"],
    "پشتیبانی": ["chats", "ai_assistant"],
    "حساب کاربری": ["wallet", "profile"],
}

MODULES_META = {
    **{m: (label, icon) for m, label, icon in USER_MODULES},
    "marketplace": ("بازارچه مو", "🏪"),
    "buyer_request": ("خریدار مو", "🧑‍💼"),
    "beauty_center": ("مرکز زیبایی من", "🏥"),
    "shop": ("فروشگاه من", "🛒"),
    "notifies": ("اعلان موجودی", "🔔"),
    "wishlist": ("علاقه‌مندی‌ها", "❤️"),
    "notifications": ("اعلان‌های من", "📣"),
    "reviews": ("نظرها و امتیازها", "⭐"),
    "reservations": ("نوبت‌های من", "📅"),
    "center_chats": ("پیام‌های مرکز", "💌"),
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
