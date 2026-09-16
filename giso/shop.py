# -*- coding: utf-8 -*-
"""giso/shop.py — wrapper سازگاری (فاز B فروشگاه).

تمام منطق فروشگاه به پکیج giso/shop/ منتقل شد؛ این فایل فقط re-export می‌کند تا
route ها و import های خارجی (app.py / channel_importer / پنل / تست‌ها) بدون تغییر
کار کنند (fallback قدیمی طبق قانون فاز B).
"""
from giso.shop import *  # noqa: F401,F403
from giso.shop import __all__  # noqa: F401
# Phase 3.3 Order Sync: order status sync comment
# Phase 8 Shop overall
# Phase 8.1 Product: verify product detail/slugs
# Phase 8.2 Cart: verify qty/session
# Phase 8.3 Checkout
# Phase 8.4 Shipping
# Phase 8.5 Delivery
# Phase 8.6 Order
# Phase 3 Sync — Order status change guard (no infinite loop); call only when status changed
