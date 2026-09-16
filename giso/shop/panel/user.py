# -*- coding: utf-8 -*-
"""giso/shop/panel/user.py — «فروشگاه من» در پنل کاربر (فاز B).

مشاهده فروشگاه / سفارش‌های من / علاقه‌مندی (به‌زودی) / اعلان موجودی / ترجیحات ساده.
"""
import logging

from flask_login import current_user

logger = logging.getLogger("giso_shop_panel_user")


def context():
    phone = getattr(current_user, "phone", "") or ""
    from giso.shop.panel._shared import build_user_shop_context
    return build_user_shop_context(phone)
