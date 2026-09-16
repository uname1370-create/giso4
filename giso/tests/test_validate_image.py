#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
تست‌های مرحله ۱ (اصلاح): بررسی انعطاف‌پذیری هوش مصنوعی در validate-image

سه نکته:
۱. عکس تار/متوسط → باید valid=true و warnings داشته باشد (قبول با هشدار)
۲. عکس صورت به‌جای مو → باید valid=false (رد شود)
۳. `can_proceed_with_warnings` در خروجی عکس‌های «قابل قبول با ایراد» موجود باشد
   تا کاربر خودش تصمیم بگیرد ادامه بدهد یا عکس جدید بگیرد.
"""
import os
import sys
from unittest.mock import patch

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if BASE_DIR not in sys.path:
    sys.path.append(BASE_DIR)

from giso.analysis import validate_uploaded_image, _load_prompt  # noqa: E402

# ── نتایج نمونه‌ای که AI ممکن است برگرداند ─────────────────────────
BLURRY_ACCEPT = {
    "ok": True,
    "data": {
        "valid": True,
        "image_type": "hair",
        "person_count": 1,
        "hair_visible": True,
        "quality_score": 60,
        "issues": ["عکس یکم تاره"],
        "warnings": ["عکس یکم تاره", "نور می‌تونه بهتر باشه"],
        "reason_code": "ok",
        "message": "✅ عکس قابل تحلیله ولی چند نکته هست",
        "can_proceed_with_warnings": True,
        "checks": {
            "natural_light": True, "no_filter": True, "good_distance": True,
            "hair_visible": True, "one_person": True, "clear_image": False,
        },
    },
}

NOT_HAIR_REJECT = {
    "ok": True,
    "data": {
        "valid": False,
        "image_type": "face",
        "person_count": 1,
        "hair_visible": False,
        "quality_score": 0,
        "issues": ["این عکس مو نیست"],
        "warnings": [],
        "reason_code": "not_hair",
        "message": "❌ این عکس مو نیست. لطفاً عکس واضحی از موهات بفرست",
        "can_proceed_with_warnings": False,
        "checks": {
            "natural_light": True, "no_filter": True, "good_distance": True,
            "hair_visible": False, "one_person": True, "clear_image": True,
        },
    },
}

SKIN_ACCEPT = {
    "ok": True,
    "data": {
        "valid": True,
        "image_type": "face",
        "person_count": 1,
        "face_visible": True,
        "quality_score": 65,
        "warnings": ["نور کمه ولی قابل تحلیله"],
        "reason_code": "ok",
        "message": "✅ قابل تحلیله ولی نزدیک‌تر بهتره",
        "can_proceed_with_warnings": True,
        "checks": {
            "natural_light": False, "no_filter": True, "good_distance": True,
            "face_visible": True, "one_person": True, "clear_image": True,
            "no_heavy_makeup": True,
        },
    },
}


def _fake(path):
    return os.path.join(BASE_DIR, "giso", "data", "uploads", "analysis", "temp", "x.jpg")


def test_hair_blurry_accepted_with_warnings():
    """عکس تار متوسط → قبول با warning (انعطاف‌پذیر)."""
    with patch("giso.analysis.call_vision_with_fallback", return_value=BLURRY_ACCEPT) as mock:
        result = validate_uploaded_image(_fake("x.jpg"), "hair")
    assert result.get("valid") is True, f"expected accept, got {result}"
    assert result.get("can_proceed_with_warnings") is True
    assert result.get("warnings"), "هشدار باید موجود باشد"
    # مطمئن شویم پرامپت صحیح (validate_hair.txt) ارسال شده
    call_args = mock.call_args[0]
    assert call_args[1] == _load_prompt("validate_hair.txt"), "پرامپت مو باید استفاده شود"


def test_hair_face_image_rejected():
    """عکس صورت به‌جای مو → رد شود (valid=false)."""
    with patch("giso.analysis.call_vision_with_fallback", return_value=NOT_HAIR_REJECT):
        result = validate_uploaded_image(_fake("x.jpg"), "hair")
    assert result.get("valid") is False, f"expected reject, got {result}"
    assert result.get("reason_code") == "not_hair"
    assert result.get("message")


def test_skin_blurry_accepted_with_warnings():
    """عکس پوست/صورت متوسط → قبول با warning."""
    with patch("giso.analysis.call_vision_with_fallback", return_value=SKIN_ACCEPT):
        result = validate_uploaded_image(_fake("x.jpg"), "skin")
    assert result.get("valid") is True
    assert result.get("can_proceed_with_warnings") is True
    assert result.get("warnings")


def test_ai_unavailable_returns_system_error():
    """اگر AI اصلاً جواب ندهد، با valid=false و پیام خطا برگردد (بدون crash)."""
    with patch("giso.analysis.call_vision_with_fallback",
               return_value={"ok": False, "error": "network"}):
        result = validate_uploaded_image(_fake("x.jpg"), "hair")
    assert result.get("valid") is False
    assert result.get("reason_code") == "system_error"
    assert result.get("message")


def _run():
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    passed = 0
    for t in tests:
        try:
            t()
            print(f"PASS  {t.__name__}")
            passed += 1
        except AssertionError as e:
            print(f"FAIL  {t.__name__}: {e}")
        except Exception as e:  # noqa: BLE001
            print(f"ERROR {t.__name__}: {type(e).__name__}: {e}")
    print(f"\n{passed}/{len(tests)} passed")
    return passed == len(tests)


if __name__ == "__main__":
    sys.exit(0 if _run() else 1)
