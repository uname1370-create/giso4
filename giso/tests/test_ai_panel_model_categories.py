#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os
import sys

os.environ.setdefault("SECRET_KEY", "arena-test-secret-for-buti-ai-tests-32chars")
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if BASE_DIR not in sys.path:
    sys.path.append(BASE_DIR)

"""برچسب قیمت، نقشهٔ مصرف‌کننده‌ها و ترتیب مسیر متنی سریع.

تست دسته‌بندی تب حذف‌شدهٔ آینه گیسو دیگر لازم نیست؛ دسته‌ها در «مدیریت مدل‌های هوش مصنوعی» تست می‌شوند.
"""
from giso.ai_models_registry import PRICE_FREE  # noqa: E402
import giso.panel.modules.ai_categories as cats  # noqa: E402
import giso.ai_runtime as runtime  # noqa: E402
from giso.ai_consumer_map import (  # noqa: E402
    CATEGORIES, CONSUMERS, PIXEL_ONLY, consumer_counts,
)


def test_price_label_never_shows_unknown_as_free():
    assert cats.price_label(PRICE_FREE) == "رایگان"
    assert cats.price_label("unknown") == "قیمت نامشخص"
    assert cats.price_label("nonsense") == "قیمت نامشخص"


def test_ai_consumer_map():
    import os

    base = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    assert set(c["category"] for c in CONSUMERS) <= set(CATEGORIES)
    for item in CONSUMERS + PIXEL_ONLY:
        assert os.path.exists(os.path.join(base, item["file"])), item["file"]
    counts = consumer_counts()
    assert counts["output_evaluation"] == 2  # ابرو و لب
    assert counts["image_generation"] == 2
    assert counts["image_analysis"] == 6
    keys = {p["key"] for p in PIXEL_ONLY}
    assert {"pixel.nail_output_check", "pixel.hair_output_check"} <= keys
    # ناخن و رنگ مو در خروجی AI داور ندارند
    assert all("nail" not in c["key"] and "hair" not in c["key"]
               for c in CONSUMERS if c["category"] == "output_evaluation")


def test_ai_consumer_text_order(monkeypatch):
    from giso.ai_brain import _fast_provider_order
    rows = [
        {"name": "a", "is_iranian": False},
        {"name": "b", "is_iranian": True},
        {"name": "c", "is_iranian": False},
    ]
    monkeypatch.setattr(runtime, "get_failover_chain", lambda: ["b", "a"])
    assert [r["name"] for r in _fast_provider_order(rows)] == ["b", "a", "c"]

    # بدون زنجیره: خارجی‌ها قبل از ایرانی‌ها (رفتار قبلی)
    monkeypatch.setattr(runtime, "get_failover_chain", lambda: [])
    assert [r["name"] for r in _fast_provider_order(rows)] == ["a", "c", "b"]
