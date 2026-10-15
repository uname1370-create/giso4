#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os
import sys

os.environ.setdefault("SECRET_KEY", "arena-test-secret-for-buti-ai-tests-32chars")
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if BASE_DIR not in sys.path:
    sys.path.append(BASE_DIR)

"""طبقه‌بندی قیمت مدل‌ها: رایگان فقط با شاهد صریح؛ قیمت نامشخص هرگز رایگان نیست."""
from giso.ai_models_registry import (  # noqa: E402
    PRICE_FREE, PRICE_PAID, PRICE_UNKNOWN, classify_model_price,
)
from giso.ai_brain import _merge_discovered  # noqa: E402


def test_ai_model_price_classification():
    # پسوند :free شاهد صریح است
    info = classify_model_price({"id": "vendor/model:free"}, "openrouter")
    assert info["status"] == PRICE_FREE and info["verified"] is True

    # قیمت صفر برای prompt و completion
    info = classify_model_price({"id": "m", "pricing": {"prompt": "0", "completion": "0"}}, "openrouter")
    assert info["status"] == PRICE_FREE and info["source"] == "api_pricing"

    # هر قیمت مثبت یعنی پولی
    info = classify_model_price({"id": "m", "pricing": {"prompt": "0.000001", "completion": "0"}}, "openrouter")
    assert info["status"] == PRICE_PAID

    # ادعای رجیستری: رایگان ولی تأییدنشده
    info = classify_model_price({"id": "llama-3.3-70b-versatile"}, "groq")
    assert info["status"] == PRICE_FREE and info["source"] == "registry" and info["verified"] is False

    # بدون هیچ شاهدی: نامشخص، نه رایگان
    info = classify_model_price({"id": "some-unknown-model"}, "groq")
    assert info["status"] == PRICE_UNKNOWN
    assert info["status"] != PRICE_FREE

    # مدل دستی ادمین حذف نمی‌شود؛ مدل کشف‌شدهٔ ناپدید غیرفعال می‌شود
    existing = [
        {"id": "manual-x", "source": "manual"},
        {"id": "auto-y", "source": "discovered"},
    ]
    merged, _new = _merge_discovered(existing, set())
    by_id = {m["id"]: m for m in merged}
    assert "manual-x" in by_id and not by_id["manual-x"].get("disabled")
    assert by_id["auto-y"].get("disabled") is True
