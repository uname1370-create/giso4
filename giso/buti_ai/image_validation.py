# -*- coding: utf-8 -*-
"""Local image-output validation helpers for آینه گیسو.

These checks are intentionally conservative and do not claim real AI success.
They quantify whether a guided/AI output changed the intended mask area while
preserving the outside area. Real AI output can only be marked true by the
service-specific generator after provider-backed generation and these checks.
"""
from __future__ import annotations

import os
from typing import Any, Dict


def save_lossless_webp(image, output_path: str) -> None:
    """Save a display-ready RGB WebP without changing any composed pixel values."""
    image.convert("RGB").save(
        output_path, format="WEBP", lossless=True, quality=100, method=6
    )


def outside_mask_pixels_equal(before, after, mask) -> bool:
    """Return True only when every decoded pixel outside the binary mask is identical."""
    try:
        from PIL import ImageChops, ImageOps

        before = before.convert("RGB")
        after = after.convert("RGB")
        mask = mask.convert("L")
        if before.size != after.size or before.size != mask.size:
            return False
        # Any non-zero mask sample is inside the editable region. This keeps
        # anti-aliased edge samples from being misclassified as untouched pixels.
        binary_mask = mask.point(lambda value: 255 if int(value) > 0 else 0)
        difference = ImageChops.difference(before, after).convert("L")
        outside_difference = ImageChops.multiply(difference, ImageOps.invert(binary_mask))
        return outside_difference.getbbox() is None
    except Exception:
        return False


def validate_masked_output(before_path: str, after_path: str, mask_path: str = "", *, service_key: str = "") -> Dict[str, Any]:
    """Measure in-mask change and outside-mask preservation.

    Returns small numeric metrics safe for UI/logging. It never reads secrets and
    never decides provider authenticity; callers decide truthful `is_ai_generated`.
    """
    result: Dict[str, Any] = {
        "ok": False,
        "service_key": service_key or "",
        "in_mask_diff_ratio": 0.0,
        "outside_mask_diff_ratio": 0.0,
        "mask_coverage_ratio": 0.0,
        "visible_in_mask_change": False,
        "outside_preserved": False,
        "message": "اعتبارسنجی خروجی انجام نشد.",
    }
    try:
        from PIL import Image, ImageChops

        if not before_path or not after_path or not os.path.exists(before_path) or not os.path.exists(after_path):
            result["message"] = "فایل قبل/بعد برای اعتبارسنجی موجود نیست."
            return result
        before = Image.open(before_path).convert("RGB")
        after = Image.open(after_path).convert("RGB")
        resample = Image.Resampling.LANCZOS if hasattr(Image, "Resampling") else Image.LANCZOS
        # Final outputs are often thumbnails. Compare in final-output geometry so
        # outside-mask preservation is not penalized by upscaling artifacts.
        if before.size != after.size:
            before = before.resize(after.size, resample)
        if mask_path and os.path.exists(mask_path):
            mask = Image.open(mask_path).convert("L")
            if mask.size != before.size:
                mask = mask.resize(before.size, resample)
        else:
            mask = Image.new("L", before.size, 0)

        diff = ImageChops.difference(before, after).convert("L")
        mask_pixels = [px > 8 for px in mask.getdata()]
        diff_pixels = list(diff.getdata())
        total_pixels = max(1, len(diff_pixels))
        mask_count = max(1, sum(1 for item in mask_pixels if item))
        outside_count = max(1, total_pixels - mask_count)
        in_changed = sum(1 for changed, value in zip(mask_pixels, diff_pixels) if changed and value > 8)
        outside_changed = sum(1 for changed, value in zip(mask_pixels, diff_pixels) if (not changed) and value > 10)
        in_ratio = in_changed / float(mask_count)
        outside_ratio = outside_changed / float(outside_count)
        coverage = mask_count / float(total_pixels)
        result.update({
            "ok": coverage > 0,
            "in_mask_diff_ratio": round(in_ratio, 6),
            "outside_mask_diff_ratio": round(outside_ratio, 6),
            "mask_coverage_ratio": round(coverage, 6),
            "visible_in_mask_change": in_ratio >= 0.005,
            "outside_preserved": outside_ratio <= 0.035,
            "message": "تغییر داخل محدوده و حفظ بیرون محدوده بررسی شد.",
        })
        return result
    except Exception as exc:
        result["message"] = f"اعتبارسنجی خروجی ناموفق بود: {str(exc)[:120]}"
        return result
