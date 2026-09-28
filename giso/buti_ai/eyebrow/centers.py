# -*- coding: utf-8 -*-
"""اتصال نازک آینه ابرو به مراکز زیبایی گیسو.

مالک سناریو همچنان Buti AI است؛ برای فهرست مرکز فقط از API عمومی
`giso.beauty_centers.services.list_public_centers` استفاده می‌کنیم.
"""
from __future__ import annotations

import logging

logger = logging.getLogger("giso_buti_ai_eyebrow_centers")

BUTI_EYEBROW_SERVICE = "eyebrow"
BEAUTY_CENTER_BROW_SERVICE = "brow"
DEFAULT_CITY = "مشهد"


def active_eyebrow_centers(city: str = "", limit: int = 3) -> list[dict]:
    """مراکز فعال منتشرشده که خدمت ابرو را ارائه می‌کنند."""
    try:
        from giso.beauty_centers.services import list_public_centers

        return list_public_centers(
            city=str(city or "").strip(),
            service=BEAUTY_CENTER_BROW_SERVICE,
            limit=max(1, min(12, int(limit or 3))),
        )
    except Exception as exc:
        logger.warning("Buti AI eyebrow centers lookup failed: %s", str(exc)[:160])
        return []


def has_active_eyebrow_centers(city: str = "") -> bool:
    return bool(active_eyebrow_centers(city=city, limit=1))


def user_default_city(current_user) -> str:
    """شهر پیش‌فرض برای فرم انتظار؛ بدون وابستگی سخت به مدل کاربر."""
    try:
        city = str(getattr(current_user, "city", "") or "").strip()
        return city or DEFAULT_CITY
    except Exception:
        return DEFAULT_CITY


def user_default_phone(current_user) -> str:
    try:
        return str(getattr(current_user, "phone", "") or "").strip()
    except Exception:
        return ""


__all__ = [
    "BEAUTY_CENTER_BROW_SERVICE",
    "BUTI_EYEBROW_SERVICE",
    "DEFAULT_CITY",
    "active_eyebrow_centers",
    "has_active_eyebrow_centers",
    "user_default_city",
    "user_default_phone",
]
