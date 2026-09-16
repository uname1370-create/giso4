# -*- coding: utf-8 -*-
"""Server-side action guards for operational Hair and Shop mutations.

Approved normal admins use a fixed operational role.  Financial, site/channel
configuration and other sensitive actions remain superadmin-only; legacy
``sub_options`` are not consulted.
"""
import logging
from functools import wraps

from flask import flash, redirect, url_for, request

from giso.panel.permissions import (
    current_role_and_perms, REGULAR_ADMIN_SECTIONS,
)

logger = logging.getLogger("giso_panel_authz")


# نگاشت اکشن پنل به بخش عملیاتی ثابت. مقدار دوم فقط یک کلید معناییِ
# سازگاری است و دیگر از تنظیمات یا schema دسترسی خوانده نمی‌شود.
PANEL_ACTIONS = {
    # ── خرید مو ──
    "hair.update_status": ("hair_sale", "change_status"),
    "hair.set_price":     ("hair_sale", "set_price"),
    "hair.set_note":      ("hair_sale", "set_note"),
    "hair.message":       ("hair_sale", "view_chat"),
    "hair.prices_config": ("hair_sale", "set_price"),
    "hair.commission":    ("hair_sale", "commission"),
    # ── فروشگاه ──
    "shop.product_add":    ("products", "add"),
    "shop.product_edit":   ("products", "edit"),
    "shop.product_delete": ("products", "delete"),
    "shop.product_stock":  ("products", "stock"),
    "shop.product_publish": ("products", "publish"),
    "shop.product_reject":  ("products", "reject_import"),
    "shop.order_status":   ("orders", "change_status"),
    "shop.stats":          ("orders", "view_list"),
    "shop.channel_config": ("channel_management", "channel_id"),
    "shop.publish_mode":   ("channel_management", "publish_mode"),
}

# اکشن‌هایی که ذاتاً فقط سوپرادمین‌اند (طبق ساختار فعلی پروژه):
#  - تنظیم پورسانت: قبلاً هم در پنل و هم در ربات فقط سوپر بود.
SUPER_ONLY_ACTIONS = {
    "hair.commission", "hair.prices_config",
    "shop.product_add", "shop.product_edit", "shop.product_delete", "shop.product_stock",
    "shop.channel_config", "shop.publish_mode", "shop.stats",
}

# Normal admins may process Hair work, change Shop order status and decide
# whether an already-imported channel post is published.  Resource-level checks
# in the product handlers additionally require source=channel + pending.
REGULAR_ADMIN_ACTIONS = frozenset({
    "hair.update_status", "hair.set_price", "hair.set_note", "hair.message",
    "shop.order_status", "shop.product_publish", "shop.product_reject",
})


def _action_meta(action_key: str):
    return PANEL_ACTIONS.get(action_key, (None, None))


def can_admin_access_section(section: str, role: str = None, perms: dict = None) -> bool:
    """Fixed role policy: approved normal admins can use operational sections."""
    if role is None:
        role, _perms, _ = current_role_and_perms()
    if role == "super":
        return True
    return bool(section and section in REGULAR_ADMIN_SECTIONS)


def can_admin_access_option(section: str, option_key: str,
                            role: str = None, perms: dict = None,
                            bale_id: str = None) -> bool:
    """Per-option switches were removed; section policy is the only gate."""
    return can_admin_access_section(section, role, perms)


def can_execute_panel_action(action_key: str) -> tuple:
    """آیا نقش جاری اجازه اجرای این اکشن پنل را دارد؟

    خروجی: (allowed: bool, reason: str)
    """
    role, perms, bale_id = current_role_and_perms()
    if role == "super":
        return True, ""
    if action_key in SUPER_ONLY_ACTIONS:
        return False, "این عملیات فقط برای سوپرادمین مجاز است."
    if action_key not in REGULAR_ADMIN_ACTIONS:
        return False, "این عملیات در نقش ادمین عادی مجاز نیست."
    section, option_key = _action_meta(action_key)
    if section is None or not can_admin_access_section(section, role, perms):
        return False, "شما به این بخش دسترسی ندارید."
    return True, ""


def _audit_denied(action_key: str, reason: str):
    try:
        from giso.security import audit_event
        role, _p, bale_id = current_role_and_perms()
        audit_event("panel_action_denied", "denied", target=action_key,
                    details=f"role={role} bale_id={bale_id} path={request.path} reason={reason}")
    except Exception as exc:
        logger.debug("audit denied failed: %s", exc)


def require_panel_action(action_key: str, redirect_endpoint: str = "panel.dashboard"):
    """دکوراتور enforcement در لایه handler (نه فقط UI).

    نکته مهم: این دکوراتور جایگزین `_check_giso_admin_access()` نیست؛ آن لایه
    احراز هویت + step-up است و همچنان اول اجرا می‌شود. این لایه «تفویض اختیار»
    را اضافه می‌کند تا نمایش و اجرا از یک منبع تبعیت کنند.
    """
    def _decorator(view):
        @wraps(view)
        def _wrapped(*args, **kwargs):
            # ۱) احراز هویت/step-up — همان گارد موجود پروژه
            try:
                from giso.app import _check_giso_admin_access
                if _r := _check_giso_admin_access():
                    return _r
            except Exception as exc:
                logger.exception("auth guard failed for %s: %s", action_key, exc)
                flash("خطا در بررسی دسترسی.", "danger")
                return redirect(url_for("login"))
            # ۲) تفویض اختیار سطح اکشن
            allowed, reason = can_execute_panel_action(action_key)
            if not allowed:
                _audit_denied(action_key, reason)
                flash(f"⛔ {reason}", "warning")
                try:
                    return redirect(url_for(redirect_endpoint))
                except Exception:
                    return redirect(url_for("panel.dashboard"))
            return view(*args, **kwargs)
        return _wrapped
    return _decorator


def visible_hair_actions() -> dict:
    """وضعیت اکشن‌های فروش مو برای قالب — تا UI و اجرا یکی باشند."""
    return {k.split(".", 1)[1]: can_execute_panel_action(k)[0]
            for k in PANEL_ACTIONS if k.startswith("hair.")}


def visible_shop_actions() -> dict:
    return {k.split(".", 1)[1]: can_execute_panel_action(k)[0]
            for k in PANEL_ACTIONS if k.startswith("shop.")}


__all__ = [
    "PANEL_ACTIONS", "SUPER_ONLY_ACTIONS", "REGULAR_ADMIN_ACTIONS",
    "can_admin_access_section", "can_admin_access_option", "can_execute_panel_action",
    "require_panel_action", "visible_hair_actions", "visible_shop_actions",
]
