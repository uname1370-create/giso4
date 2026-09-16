# -*- coding: utf-8 -*-
"""giso/shop/panel/super.py — گزینه‌های ویژه سوپرادمین فروشگاه (فاز B).

تنظیمات فروشگاه، پیشنهاد هوشمند، ویجت فروشگاه و کنترل matching AI —
همه به ماژول‌های موجود پنل لینک می‌شوند (بدون تکرار منطق).
"""
import logging

logger = logging.getLogger("giso_shop_panel_super")


def context():
    from giso.shop.panel._shared import build_super_shop_context
    return build_super_shop_context()
