# -*- coding: utf-8 -*-
"""panel_user/modules/reviews.py — ثبت نظر و لیست نظرات کاربر."""
from giso.panel_user.modules._base import get_reviews, get_shop_orders, get_hair_orders


def context():
    return {
        "reviews": get_reviews(),
        "shop_orders": get_shop_orders(),
        "hair_orders": get_hair_orders(),
    }
