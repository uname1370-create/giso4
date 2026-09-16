# -*- coding: utf-8 -*-
"""panel/modules/ratelimit.py — محدودیت زمان تحلیل."""
import logging

logger = logging.getLogger("giso_panel_ratelimit")


def _get_config(key, default=""):
    try:
        from giso_admin import get_giso_config
        return get_giso_config(key, default) or default
    except Exception:
        return default


def context():
    """تنظیمات محدودیت تحلیل؛ در صورت ناسالم بودن bot.db مقدار fail-closed
    (فعال + ۵ دقیقه + هر دو) برمی‌گردد، نه بی‌محدود."""
    try:
        from giso.base import read_rate_limit_config
        cfg = read_rate_limit_config()
        return {
            "rate_limit_enabled": cfg["enabled"],
            "rate_limit_minutes": cfg["minutes"],
            "rate_limit_type": cfg["limit_type"],
        }
    except Exception:
        return {
            "rate_limit_enabled": True,
            "rate_limit_minutes": 5,
            "rate_limit_type": "both",
        }
