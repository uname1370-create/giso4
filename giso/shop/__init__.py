# -*- coding: utf-8 -*-
"""giso/shop — پکیج ماژولار فروشگاه گیسو (فاز B).

ساختار:
  - routes.py        : همه route های سایت (همان مسیر/endpoint قبلی)
  - logic/           : منطق خالص (cart/checkout/inventory/discount/suggestions/channel_bridge)
  - panel/           : ماژول‌های پنل (admin/super/user) + قالب‌ها
  - bot/             : منوها و هندلرهای ربات (user/admin/super)
  - templates/       : قالب‌های عمومی فروشگاه
  - static/          : css/js فروشگاه

fallback: giso/shop.py قدیمی فقط wrapper است (route ها fail نمی‌شوند).
"""
from flask import Blueprint  # noqa: F401

from giso.shop.routes import *  # noqa: F401,F403
from giso.shop.routes import (  # noqa: F401
    shop_routes, shop_mod_static, register_shop_routes, seed_sample_products,
    shop, _shop_context, buy_product, notify_stock,
    admin_product_add, admin_product_edit, admin_product_toggle_stock,
    admin_product_delete, admin_shop_order_status, admin_config_channel,
    product_detail, cart_add, cart_remove, cart_update, cart_page, cart_checkout,
    admin_product_publish, admin_product_reject, admin_publish_mode, admin_channel_test, admin_shop_stats,
    get_publish_mode, _notify_admins_shop_order, robots_txt, sitemap_xml,
    _make_slug, _save_product_image,
)

__all__ = [
    "shop_routes", "shop_mod_static", "register_shop_routes", "seed_sample_products",
    "shop", "_shop_context", "buy_product", "notify_stock",
    "admin_product_add", "admin_product_edit", "admin_product_toggle_stock",
    "admin_product_delete", "admin_shop_order_status", "admin_config_channel",
    "product_detail", "cart_add", "cart_remove", "cart_update", "cart_page", "cart_checkout",
    "admin_product_publish", "admin_product_reject", "admin_publish_mode", "admin_channel_test", "admin_shop_stats",
    "get_publish_mode", "_notify_admins_shop_order", "robots_txt", "sitemap_xml",
    "_make_slug", "_save_product_image",
]
