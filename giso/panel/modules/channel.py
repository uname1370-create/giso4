# -*- coding: utf-8 -*-
"""panel/modules/channel.py — تنظیم کانال فروشگاه."""
import logging


logger = logging.getLogger("giso_panel_channel")


def _get_config(key, default=""):
    try:
        from giso_admin import get_giso_config
        return get_giso_config(key, default) or default
    except Exception:
        return default


def context():
    try:
        bale_channel_id = _get_config("bale_channel_id", "")
    except Exception:
        bale_channel_id = ""
    try:
        from giso.shop import get_publish_mode
        publish_mode = get_publish_mode()
    except Exception:
        publish_mode = "review"
    return {"bale_channel_id": bale_channel_id, "publish_mode": publish_mode}
