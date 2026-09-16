# -*- coding: utf-8 -*-
"""Deprecated compatibility API for the removed bot permission menus.

Approved normal admins now have one fixed operational role.  This module keeps
old imports safe during rolling bot deployments, but it never reads or writes
``giso_admin_permissions.sub_options``.
"""
import logging

from giso.base import get_giso_db_conn
from giso.config import is_super_admin as _cfg_is_super_admin

logger = logging.getLogger("giso_bot_permissions")

SECTION_OPTION_REGISTRY = {
    "hair_sale": [
        {"key": "view_requests", "label": "📋 درخواست‌های فروش مو", "text_button": "📋 درخواست‌های فروش مو", "callback_prefix": "hair_pg|req|"},
        {"key": "edit_by_phone", "label": "📱 ویرایش با شماره کاربر", "text_button": "📱 ویرایش با شماره کاربر", "callback_prefix": "hair_pg|uo|"},
        {"key": "list_users", "label": "👥 لیست کاربران فروش مو", "text_button": "👥 لیست کاربران فروش مو", "callback_prefix": "hair_pg|usr|"},
        {"key": "reports", "label": "📊 گزارش‌ها", "text_button": "📊 گزارش‌ها", "callback_prefix": "hair_rep|"},
        {"key": "objections", "label": "💬 گفتگوها", "text_button": "💬 گفتگوها"},
        {"key": "review", "label": "🔍 در حال بررسی", "callback_prefix": "hair_review|"},
        {"key": "reject", "label": "❌ رد سفارش", "callback_prefix": "hair_rej|"},
        {"key": "price", "label": "💰 ثبت قیمت نهایی", "callback_prefix": "hair_price|"},
        {"key": "note", "label": "📝 ثبت یادداشت", "callback_prefix": "hair_note|"},
        {"key": "message", "label": "💬 گفتگو با کاربر", "callback_prefix": "hair_msg|"},
        {"key": "approve", "label": "✅ تأیید سفارش", "callback_prefix": "hair_approve|"},
    ],
    "shop": [
        {"key": "orders", "label": "🧾 سفارش‌های جدید", "text_button": "🧾 سفارش‌های جدید"},
        {"key": "products", "label": "📦 محصولات", "text_button": "📦 محصولات"},
        {"key": "pending_products", "label": "⏳ لیست محصولات منتظر تأیید", "text_button": "⏳ لیست محصولات منتظر تأیید", "callback_prefix": "shop_ch_app|"},
        {"key": "reports", "label": "📊 گزارش فروش", "text_button": "📊 گزارش فروش"},
    ],
    "analysis_management": [
        {"key": "stats", "label": "📊 آمار کامل", "callback": "adm_ana_stats"},
        {"key": "list", "label": "📋 لیست ۱۰ تحلیل آخر", "callback": "adm_ana_list"},
        {"key": "consultants", "label": "درخواست‌های مشاوره", "callback": "adm_ana_consultants"},
        {"key": "products", "label": "محصولات درخواستی", "callback": "adm_ana_products"},
        {"key": "chats", "label": "💬 خلاصه گفتگوهای مشاور", "callback": "adm_ana_chats"},
        {"key": "ratelimit", "label": "⏱ تنظیمات محدودیت زمانی", "callback": "adm_ana_ratelimit"},
    ],
}
CONFIGURABLE_SECTIONS = ()
SECTION_LABELS = {
    "hair_sale": "💇 فروش مو", "shop": "🛍 فروشگاه",
    "analysis_management": "🔬 مدیریت آنالیز",
}


def section_options(section: str) -> list:
    return list(SECTION_OPTION_REGISTRY.get(section, ()))


def option_meta(section: str, option_key: str):
    return next((item for item in section_options(section) if item["key"] == option_key), None)


def resolve_callback(data: str):
    if not data:
        return None
    for section, options in SECTION_OPTION_REGISTRY.items():
        for item in options:
            if item.get("callback") == data:
                return section, item["key"]
            prefix = item.get("callback_prefix")
            if prefix and data.startswith(prefix):
                return section, item["key"]
    return None


def resolve_text_button(section: str, text: str):
    item = next((item for item in section_options(section) if item.get("text_button") == text), None)
    return item["key"] if item else None


def is_super_admin(user_id, phone: str = "") -> bool:
    try:
        return bool(_cfg_is_super_admin(user_id, phone))
    except Exception:
        return False


def is_regular_admin(user_id, phone: str = "") -> bool:
    if not user_id or is_super_admin(user_id, phone):
        return False
    try:
        with get_giso_db_conn() as conn:
            row = conn.execute("SELECT is_admin FROM giso_users WHERE bale_id=?", (str(user_id),)).fetchone()
        return bool(row and row[0])
    except Exception as exc:
        logger.debug("regular admin lookup failed: %s", exc)
        return False


def get_visible_options(section: str, user_id, phone: str = "") -> set:
    if not (is_super_admin(user_id, phone) or is_regular_admin(user_id, phone)):
        return set()
    return {
        item["key"] for item in section_options(section)
        if can_access_option(section, item["key"], user_id, phone)
    }


def can_access_option(section: str, option_key: str, user_id, phone: str = "") -> bool:
    if (section, option_key) == ("analysis_management", "ratelimit"):
        return is_super_admin(user_id, phone)
    return bool(is_super_admin(user_id, phone) or is_regular_admin(user_id, phone))


def can_execute_callback(data: str, user_id, phone: str = ""):
    hit = resolve_callback(data)
    if not hit:
        return True, None, None
    section, option_key = hit
    return can_access_option(section, option_key, user_id, phone), section, option_key


def set_option_visibility(section: str, option_key: str, bale_id, visible: bool) -> bool:
    """Deprecated no-op; retained only so an old worker does not crash."""
    return False


def toggle_option_visibility(section: str, option_key: str, bale_id) -> bool:
    """Deprecated no-op; configuration callbacks are tombstoned by the bot."""
    return False


def list_regular_admins() -> list:
    out = []
    try:
        with get_giso_db_conn() as conn:
            rows = conn.execute(
                "SELECT bale_id,phone,first_name FROM giso_users WHERE is_admin=1 ORDER BY bale_id"
            ).fetchall()
        for row in rows:
            if not is_super_admin(row["bale_id"], row["phone"] or ""):
                out.append({"bale_id": str(row["bale_id"]), "phone": row["phone"] or "", "name": row["first_name"] or ""})
    except Exception as exc:
        logger.debug("list regular admins failed: %s", exc)
    return out


def options_state(section: str, bale_id) -> list:
    return [
        {"key": item["key"], "label": item["label"],
         "visible": can_access_option(section, item["key"], bale_id)}
        for item in section_options(section)
    ]


__all__ = [
    "SECTION_OPTION_REGISTRY", "CONFIGURABLE_SECTIONS", "SECTION_LABELS",
    "section_options", "option_meta", "resolve_callback", "resolve_text_button",
    "is_super_admin", "is_regular_admin", "get_visible_options", "can_access_option",
    "can_execute_callback", "set_option_visibility", "toggle_option_visibility",
    "list_regular_admins", "options_state",
]
