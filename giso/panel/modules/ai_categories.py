# -*- coding: utf-8 -*-
"""برچسب قیمت مدل‌های AI برای پنل مدیریت.

این ماژول فقط برچسب قیمت را می‌سازد و هیچ پروایدر، مدل، اسلات یا وضعیت فعالی را تغییر نمی‌دهد.
برچسب قیمت از طبقه‌بند مشترک می‌آید؛ قیمت نامشخص هرگز «رایگان» نشان داده نمی‌شود.
"""
from __future__ import annotations

from giso.ai_models_registry import PRICE_FREE, PRICE_PAID, PRICE_UNKNOWN  # noqa: F401

PRICE_LABELS = {
    PRICE_FREE: "رایگان",
    PRICE_PAID: "پولی",
    PRICE_UNKNOWN: "قیمت نامشخص",
}


def price_label(status: str) -> str:
    return PRICE_LABELS.get(status, PRICE_LABELS[PRICE_UNKNOWN])
