# -*- coding: utf-8 -*-
"""giso/shop/logic/channel_bridge.py — اتصال به channel_importer بدون تغییر آن — فاز B فروشگاه."""
import logging

from giso.shop.logic.inventory import _get_giso_config_safe  # noqa: F401

logger = logging.getLogger("giso_shop_logic_channel_bridge")

def get_publish_mode() -> str:
    """حالت انتشار محصولات کانال: review (با تأیید) یا auto (خودکار). پیش‌فرض امن = review."""
    return ( _get_giso_config_safe("shop_publish_mode", "review") or "review" ).strip().lower()


__all__ = ["get_publish_mode"]
