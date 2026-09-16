# -*- coding: utf-8 -*-
"""giso/shop/logic/cart.py — منطق سبد خرید (session-based) — فاز B فروشگاه."""
import logging

from flask import session

from giso.models import Product

logger = logging.getLogger("giso_shop_logic_cart")

def _get_cart() -> dict:
    try:
        cart = session.get("giso_cart") or {}
        return {str(k): int(v) for k, v in cart.items() if str(v).isdigit() and int(v) > 0}
    except Exception:
        return {}

def _save_cart(cart: dict):
    session["giso_cart"] = cart
    session.modified = True

def _cart_items(cart: dict):
    """تبدیل دیکشنری سبد به لیست آیتم‌های قابل نمایش."""
    items = []
    total = 0
    for pid_s, qty in cart.items():
        try:
            prod = Product.query.get(int(pid_s))
        except (ValueError, TypeError):
            prod = None
        if not prod:
            continue
        line = prod.price * qty
        total += line
        items.append(dict(product=prod, qty=qty, line_total=line))
    return items, total


def cart_count(cart) -> int:
    """تعداد کل آیتم‌های سبد (جمع quantity) — برای شمارنده واقعی سبد شناور."""
    try:
        return sum(int(q) for q in (cart or {}).values() if str(q).isdigit() and int(q) > 0)
    except Exception:
        return 0


__all__ = ["_get_cart", "_save_cart", "_cart_items", "cart_count"]
