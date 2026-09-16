# -*- coding: utf-8 -*-
"""Role-based access policy for the modular admin panel.

Normal admins are approved through the existing admin-request workflow and then
receive the fixed set of day-to-day operational modules below.  Per-admin
checkboxes and ``sub_options`` are intentionally no longer consulted.
"""
import logging

from giso.base import normalize_phone
from giso.config import SUPERADMIN_BALE_ID, is_super_admin, is_special_admin

logger = logging.getLogger("giso_panel_permissions")

# Kept as a compatibility registry for callers that display section names.
ADMIN_SECTIONS = [
    ("dashboard", "📊 پیشخوان"),
    ("orders", "🛒 سفارش‌ها"),
    ("hair_sale", "💇 فروش مو"),
    ("beauty_centers", "🏥 مراکز زیبایی"),
    ("analysis_management", "🔬 مدیریت آنالیز"),
    ("reviews", "⭐ نظرات"),
    ("products", "📦 محصولات"),
    ("channel_management", "📢 مدیریت کانال"),
    ("users", "👥 مدیریت کاربران سایت"),
    ("admins", "👑 مدیریت ادمین‌ها"),
    ("site_bot_settings", "⚙️ مدیریت سایت و ربات"),
    ("ai_management", "🤖 مدیریت AI"),
]

# Fixed day-to-day policy for every approved normal admin (site + bot):
# hair_sale, marketplace, beauty_centers, shop_orders, reviews, consults.
# Channel/product catalog, sales stats, and analysis stay superadmin-only.
REGULAR_ADMIN_SECTIONS = frozenset({
    "dashboard", "orders", "hair_sale", "marketplace", "beauty_centers", "reviews",
    "consults", "account",
})
REGULAR_ADMIN_MODULES = frozenset({
    "dashboard", "hair_sale", "marketplace", "beauty_centers", "shop_orders",
    "reviews", "consults", "account",
})

# This is a separate normal-role navigation contract so the existing
# superadmin metadata and its ordering remain untouched.
REGULAR_ADMIN_NAV = (
    ("dashboard", "پیشخوان کار من", "📊"),
    ("hair_sale", "مدیریت خرید مو", "💇‍♀️"),
    ("marketplace", "مدیریت بازارچه مو", "🏪"),
    ("beauty_centers", "مدیریت مراکز زیبایی", "🏥"),
    ("shop_orders", "سفارش‌های فروشگاه", "🛒"),
    ("reviews", "نظرات عمومی", "⭐"),
    ("consults", "مدیریت گفتگوها", "💬"),
    ("account", "حساب کاربری", "👤"),
)

# نقش سوم سایت (خانم مهندس صادقی): عملیاتی + آقا رضا + گزارش شخصی.
# مالی همه، کاربران، ادمین‌ها، AI، تنظیمات، کاتالوگ فروشگاه، آنالیز، بکاپ — خارج از این لیست.
SPECIAL_ADMIN_NAV = (
    ("dashboard", "پیشخوان اختصاصی", "🏠"),
    ("aga_reza", "آقا رضا (دستیار AI اختصاصی)", "🤖"),
    ("hair_sale", "خرید مو", "💇"),
    ("shop_orders", "فروشگاه (مشاهده + مدیریت سفارش)", "🛍"),
    ("marketplace", "بازارچه مو", "🏪"),
    ("beauty_centers", "مراکز زیبایی", "🏥"),
    ("consults", "گفتگوها و مشاوره‌ها", "💬"),
    ("special_reports", "گزارش‌های شخصی", "📊"),
    ("account", "پروفایل من", "👤"),
)
SPECIAL_ADMIN_MODULES = frozenset(module for module, _label, _icon in SPECIAL_ADMIN_NAV)

MODULE_TO_SECTION = {
    "dashboard": "dashboard",
    "users": "users",
    "admins": "admins",
    "products": "products",
    "shop_orders": "orders",
    "hair_sale": "hair_sale",
    "marketplace": "marketplace",
    "beauty_centers": "beauty_centers",
    "analyses": "analysis_management",
    "reviews": "reviews",
    "consults": "consults",
    "account": "account",
    "channel": "channel_management",
    "ai": "ai_management",
    "ratelimit": "site_bot_settings",
    "referrals": "admins",
    "wallet": "admins",
    "shop": "products",
    "shop_super": "site_bot_settings",
    "monitoring": "site_bot_settings",
}

# Sensitive/configuration modules remain superadmin-only.  The normal-role
# module allowlist above is authoritative; this set also documents high-risk
# legacy URLs that must fail closed.
SUPER_ONLY_MODULES = {
    "referrals", "wallet", "admins", "settings", "shop_super", "reports",
    "ai", "ratelimit", "users", "channel", "analyses", "notifications", "shop", "monitoring",
    "super_assistant",
}


def get_admin_target(phone_norm: str) -> dict:
    """Resolve an approved admin using the existing shared admin registry."""
    phone_norm = normalize_phone(phone_norm)
    if not phone_norm:
        return {}
    if is_super_admin(phone=phone_norm):
        return {"role": "super", "bale_id": str(SUPERADMIN_BALE_ID), "phone": phone_norm}
    if is_special_admin(phone=phone_norm):
        return {"role": "special", "bale_id": "", "phone": phone_norm}
    try:
        from giso_admin import find_giso_admin_by_phone
        from giso.base import _phone_variants
        row = None
        for candidate in _phone_variants(phone_norm):
            row = find_giso_admin_by_phone(candidate)
            if row:
                break
    except Exception as exc:
        logger.error("panel admin target lookup failed: %s", exc)
        row = None
    if not row:
        try:
            from giso.base import _phone_variants, get_bot_db_conn
            candidates = list(_phone_variants(phone_norm))
            conn = get_bot_db_conn()
            try:
                marks = ",".join("?" for _ in candidates)
                row = conn.execute(
                    f"SELECT * FROM giso_admins WHERE phone IN ({marks}) LIMIT 1", candidates
                ).fetchone()
                row = dict(row) if row else None
            finally:
                conn.close()
        except Exception as exc:
            logger.error("panel admin target DB fallback failed: %s", exc)
    if not row:
        return {}
    bale_id = str(row.get("bale_id") or row.get("telegram_id") or "").strip()
    # لیست سیاه: ادمینِ حذف‌شده نباید در پنل به‌عنوان ادمین شناخته شود
    try:
        from giso.base import is_admin_demoted
        if is_admin_demoted(bale_id=bale_id, phone=phone_norm):
            return {}
    except Exception:
        pass
    return {"role": "admin", "bale_id": bale_id, "phone": phone_norm}


def is_suboption_visible(admin_id, section: str, subkey: str, channel: str = "site") -> bool:
    """Compatibility bypass: approved admins no longer have per-option switches."""
    return True


def _fixed_permissions(is_super: bool = False) -> dict:
    return {key: bool(is_super or key in REGULAR_ADMIN_SECTIONS) for key, _ in ADMIN_SECTIONS}


def get_admin_permissions(bale_id: str) -> dict:
    """Return the fixed normal-admin policy; stored legacy switches are inert."""
    return _fixed_permissions(False)


def set_admin_permission(bale_id: str, section: str, allowed: bool) -> bool:
    """Deprecated compatibility no-op; permission configuration was removed."""
    return False


DEFAULT_ADMIN_GRANTS = tuple(sorted(REGULAR_ADMIN_SECTIONS - {"dashboard"}))


def grant_default_admin_sections(bale_id: str) -> int:
    """Compatibility hook: approval alone now grants the fixed operational role."""
    return 0


def migrate_existing_admins_default_grants() -> int:
    """No migration is needed for the fixed role policy."""
    return 0


def current_role_and_perms():
    """Return ``(role, fixed_permissions, bale_id)`` for the current admin."""
    try:
        from flask_login import current_user
    except Exception:
        return "admin", _fixed_permissions(False), ""
    try:
        phone_norm = normalize_phone(getattr(current_user, "phone", "") or "")
        target = get_admin_target(phone_norm)
        role = target.get("role") or "admin"
        bale_id = target.get("bale_id") or ""
        return role, _fixed_permissions(role == "super"), bale_id
    except Exception as exc:
        logger.debug("panel current_role_and_perms: %s", exc)
        return "admin", _fixed_permissions(False), ""


def module_allowed(module: str, role: str, perms: dict) -> bool:
    """Apply the fixed role policy; no per-admin database switches are read."""
    if role == "super":
        return True
    if module in SUPER_ONLY_MODULES:
        return False
    if role == "special":
        return module in SPECIAL_ADMIN_MODULES
    return module in REGULAR_ADMIN_MODULES


def visible_modules(role: str, perms: dict, bale_id: str = ""):
    """Return the role-specific sidebar without changing superadmin output."""
    if role == "special":
        return [
            {"module": module, "label": label, "icon": icon, "group": ""}
            for module, label, icon in SPECIAL_ADMIN_NAV
            if module_allowed(module, role, perms)
        ]
    if role != "super":
        return [
            {"module": module, "label": label, "icon": icon, "group": ""}
            for module, label, icon in REGULAR_ADMIN_NAV
            if module_allowed(module, role, perms)
        ]
    # Keep the established superadmin menu labels, ordering and grouping.
    return [
        {"module": module, "label": label, "icon": icon,
         "group": MODULE_GROUPS.get(module, "")}
        for module, label, icon in MODULES_META
        if module_allowed(module, role, perms)
    ]


# منوی سوپرادمین: محصولات/سفارش/کانال داخل «🛍 مدیریت فروشگاه» و اعلان/نظرات داخل
# «💬 مدیریت گفتگوها» و گزارشات داخل «🛡 پایش هوشمند» تجمیع شده‌اند تا منو سبک و سریع‌تر
# پیدا شود. route و handler این ماژول‌ها کاملاً دست‌نخورده می‌ماند (فقط ورودی سایدبار حذف شد).
# منوی سوپرادمین — بازچینش سبک: دستیار هوشمند اول؛ کارهای روزمره در «صندوق کارها»؛
# پیکربندی‌ها در «تنظیمات پیشرفته». ماژول «پایش» از سایدبار حذف و کامل به دستیار
# هوشمند سپرده شد (🐞 خطایابی / 💡 بهبود / 📊 سلامت)؛ route و صفحه‌اش فعال می‌ماند
# و با لینک مستقیم/بوکمارک در دسترس است.
MODULES_META = [
    ("super_assistant", "دستیار هوشمند", "🤖"),
    ("dashboard", "پیشخوان", "📊"),
    ("hair_sale", "فروش مو", "💇"),
    ("marketplace", "بازارچه مو", "🏪"),
    ("beauty_centers", "مراکز زیبایی", "🏥"),
    ("analyses", "آنالیزها", "🔬"),
    ("shop", "فروشگاه", "🛍"),
    ("consults", "گفتگوها و تیکت‌ها", "💬"),
    ("broadcasts_center", "مرکز پیام و اعلان", "📣"),
    ("wallet", "مرکز مالی", "💳"),
    ("users", "کاربران", "👥"),
    ("admins", "ادمین‌ها", "👑"),
    ("ai", "مدیریت AI", "🧠"),
    ("settings", "تنظیمات سایت", "⚙️"),
]
# ماژول‌هایی که از منو حذف شده ولی صفحه/route آن‌ها فعال و از داخل ماژول میزبان/
# دستیار هوشمند در دسترس است:
#   monitoring (پایش و گزارش هوشمند) → کاملاً در دستیار هوشمند (خطایابی/بهبود/سلامت)
#   notifications و reviews → از داخل «💬 گفتگوها و تیکت‌ها» لینک می‌شوند.
#   reports (گزارشات) → در دستیار هوشمند.
#   backup/recovery، ratelimit، channel → با لینک مستقیم/بوکمارک و داخل تنظیمات فعال‌اند.

MODULE_GROUPS = {
    "super_assistant": "",
    "broadcasts_center": "",
    "dashboard": "",
    "hair_sale": "📥 صندوق کارها", "marketplace": "📥 صندوق کارها",
    "beauty_centers": "📥 صندوق کارها", "analyses": "📥 صندوق کارها",
    "shop": "📥 صندوق کارها", "consults": "📥 صندوق کارها", "shop_orders": "📥 صندوق کارها",
    "channel": "📥 صندوق کارها",
    "wallet": "💳 مالی",
    "users": "⚙️ تنظیمات پیشرفته", "admins": "⚙️ تنظیمات پیشرفته",
    "ai": "⚙️ تنظیمات پیشرفته", "settings": "⚙️ تنظیمات پیشرفته",
    "products": "⚙️ تنظیمات پیشرفته", "reviews": "⚙️ تنظیمات پیشرفته",
    "notifications": "⚙️ تنظیمات پیشرفته", "shop_super": "⚙️ تنظیمات پیشرفته",
    "ratelimit": "⚙️ تنظیمات پیشرفته",
    # این‌ها route فعال دارند ولی از سایدبار حذف شده‌اند (در دستیار/لینک مستقیم)
    "reports": "", "monitoring": "",
}

__all__ = [
    "ADMIN_SECTIONS", "REGULAR_ADMIN_SECTIONS", "REGULAR_ADMIN_MODULES", "REGULAR_ADMIN_NAV",
    "SPECIAL_ADMIN_NAV", "SPECIAL_ADMIN_MODULES",
    "MODULE_TO_SECTION", "SUPER_ONLY_MODULES", "MODULES_META",
    "get_admin_target", "get_admin_permissions", "set_admin_permission",
    "grant_default_admin_sections", "migrate_existing_admins_default_grants",
    "current_role_and_perms", "module_allowed", "visible_modules", "is_suboption_visible",
]
