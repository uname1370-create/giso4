#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os
import sys

os.environ.setdefault("SECRET_KEY", "arena-test-secret-for-buti-ai-tests-32chars")
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if BASE_DIR not in sys.path:
    sys.path.append(BASE_DIR)

"""چهار دستهٔ پنل مدل AI، برچسب قیمت، نقشهٔ مصرف‌کننده‌ها و ترتیب مسیر متنی سریع."""
from giso.ai_models_registry import PRICE_FREE  # noqa: E402
from giso.buti_ai.ai_models import (  # noqa: E402
    TASK_EYEBROW_ANALYSIS, TASK_MIRROR_IMAGE_DESIGN, TASK_MIRROR_OUTPUT_VALIDATION,
)
import giso.panel.modules.ai_categories as cats  # noqa: E402
import giso.ai_runtime as runtime  # noqa: E402
from giso.ai_consumer_map import (  # noqa: E402
    CATEGORIES, CONSUMERS, PIXEL_ONLY, consumer_counts,
)


def _index():
    return {
        "groq": {
            "vision": [{"id": "v1", "status": "unknown"}],
            "text": [{"id": "t1", "status": PRICE_FREE}],
            "enabled": True,
        },
        "paid": {
            "vision": [],
            "text": [{"id": "p1", "status": "paid"}],
            "enabled": True,
        },
    }


def test_ai_panel_model_categories(monkeypatch):
    monkeypatch.setattr(cats, "provider_model_index", _index)
    monkeypatch.setattr(runtime, "get_failover_chain", lambda: ["groq"])
    bm = {
        "slots": [
            {"task_key": TASK_EYEBROW_ANALYSIS, "priority": 1, "provider_name": "", "model_name": ""},
            {"task_key": TASK_MIRROR_OUTPUT_VALIDATION, "priority": 1, "provider_name": "", "model_name": ""},
        ],
        "providers": [{"name": "groq", "enabled": True, "selected_model": "t1"}],
        "image_candidates": [],
    }
    before = dict(bm)
    view = cats.build_category_view(bm)

    # ورودی تغییر نمی‌کند (باز کردن پنل بی‌اثر است)
    assert "categories" not in before and bm == before

    keys = [c["key"] for c in view["categories"]]
    assert keys == ["text", "image_analysis", "image_generation", "output_evaluation"]

    by_key = {c["key"]: c for c in view["categories"]}
    assert by_key["text"]["chain"][0]["name"] == "groq"
    assert by_key["text"]["chain"][0]["model"] == "t1"
    assert [s["category_key"] for s in by_key["image_analysis"]["slots"]] == ["image_analysis"]
    assert [s["category_key"] for s in by_key["output_evaluation"]["slots"]] == ["output_evaluation"]

    # قیمت نامشخص هرگز «رایگان» نشان داده نمی‌شود
    assert cats.price_label("unknown") == "قیمت نامشخص"
    assert cats.price_label("nonsense") == "قیمت نامشخص"
    vision_labels = {o["value"]: o["label"] for o in by_key["image_analysis"]["options"]}
    assert "رایگان" not in vision_labels["v1"]

    # فهرست کل: رایگان‌ها اول
    assert view["all_model_options"][0]["value"] == "t1"
    assert view["all_model_options"][0]["price_status"] == PRICE_FREE


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
