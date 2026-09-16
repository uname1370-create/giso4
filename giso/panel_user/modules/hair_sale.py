# -*- coding: utf-8 -*-
"""پنل کاربر: فقط درخواست‌های فروش مستقیم مو؛ بازارچه ماژول مستقل دارد."""
from giso.marketplace.services import format_amount
from giso.panel_user.modules._base import get_hair_orders


def context():
    hair = get_hair_orders()
    return {
        "hair_orders": hair,
        "active_order": hair[0] if hair else None,
        "fmt_market_amount": format_amount,
    }
