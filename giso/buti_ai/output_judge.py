# -*- coding: utf-8 -*-
"""داور خروجی AI برای آینه گیسو (ابرو و لب).

این ماژول دستهٔ «ارزیابی خروجی» پنل مدیریت AI (TASK_MIRROR_OUTPUT_VALIDATION) را مصرف می‌کند.

قواعد:
- بررسی پیکسلی (validate_masked_output) همچنان گیت اصلی است؛ این داور یک لایهٔ اضافه است.
- اگر برای دستهٔ ارزیابی مدلی فعال نباشد، بررسی AI انجام نمی‌شود (checked=False).
- اگر همهٔ مدل‌ها خطا بدهند یا پاسخ خوانا ندهند، بررسی «انجام نشده» ثبت می‌شود و خروجی
  به‌خاطر خطای داور رد نمی‌شود (گزارش می‌شود).
- فقط وقتی مدل صریحاً تغییر ناخواسته خارج از ناحیهٔ هدف ببیند، خروجی رد می‌شود.
- حداکثر MAX_JUDGE_ATTEMPTS مدل امتحان می‌شود تا تأخیر تولید محدود بماند.
"""
from __future__ import annotations

import logging
import os
import tempfile
from typing import Any, Dict

logger = logging.getLogger(__name__)

# خدمت‌های دارای داور AI (فقط ابرو و لب، طبق درخواست)
JUDGE_SERVICES = ("eyebrow", "lip_shading")
MAX_JUDGE_ATTEMPTS = 2
JUDGE_MAX_TOKENS = 300

_TARGET_LABEL = {"eyebrow": "eyebrow", "lip_shading": "lips"}


def _as_bool(value: Any) -> bool:
    if isinstance(value, str):
        return value.strip().lower() in {"true", "yes", "1", "y"}
    return bool(value)


def _judge_prompt(service_key: str) -> str:
    target = _TARGET_LABEL.get(service_key, "target area")
    return (
        "The image is a side-by-side pair: LEFT = original photo, RIGHT = edited photo. "
        f"The only intended change is the {target}. "
        "Check whether anything else changed visibly (face identity, skin, hair, background, "
        "clothing, glasses, eyes, teeth). "
        'Reply ONLY with JSON: {"only_target_changed": true or false, "unwanted_changes": "short text or empty"}'
    )


def _side_by_side_jpeg(before, after) -> str:
    """دو تصویر کنار هم در یک فایل موقت JPEG؛ مسیر فایل برمی‌گردد."""
    from PIL import Image

    left = before.convert("RGB")
    right = after.convert("RGB")
    if right.size != left.size:
        right = right.resize(left.size)
    canvas = Image.new("RGB", (left.width * 2, left.height), (255, 255, 255))
    canvas.paste(left, (0, 0))
    canvas.paste(right, (left.width, 0))
    fd, path = tempfile.mkstemp(prefix="output_judge_", suffix=".jpg")
    os.close(fd)
    canvas.save(path, "JPEG", quality=90)
    return path


def judge_output(service_key: str, before, after) -> Dict[str, Any]:
    """خروجی تولیدشده را با مدل‌های دستهٔ «ارزیابی خروجی» بررسی می‌کند.

    خروجی: {checked, ok, provider, model, reason, errors}
    - checked=False یعنی داور AI اجرا نشد (دلیل در reason).
    - checked=True و ok=False یعنی تغییر ناخواسته تشخیص داده شد.
    """
    result: Dict[str, Any] = {"checked": False, "ok": None, "provider": "", "model": "",
                              "reason": "", "errors": []}
    if service_key not in JUDGE_SERVICES:
        result["reason"] = "service_out_of_scope"
        return result

    try:
        from giso.buti_ai.ai_models import TASK_MIRROR_OUTPUT_VALIDATION, configured_vision_chain
        chain = configured_vision_chain(TASK_MIRROR_OUTPUT_VALIDATION)[:MAX_JUDGE_ATTEMPTS]
    except Exception as exc:
        result["reason"] = f"chain_unavailable:{type(exc).__name__}"
        return result
    if not chain:
        result["reason"] = "no_output_validation_model"
        return result

    path = ""
    try:
        from giso.ai_brain import ask_ai_vision
        from giso.analysis import _is_ai_refusal, _parse_ai_json
        from giso.async_compat import run_async_safe

        path = _side_by_side_jpeg(before, after)
        prompt = _judge_prompt(service_key)
        for item in chain:
            provider = str(item.get("provider_name") or "")
            model = str(item.get("model_name") or "")
            if not provider or not model:
                continue
            try:
                res = run_async_safe(ask_ai_vision(provider, path, prompt, model=model,
                                                   max_tokens=JUDGE_MAX_TOKENS))
            except Exception as exc:
                res = {"ok": False, "error": f"{type(exc).__name__}: {exc}"}
            if not (res and res.get("ok")):
                result["errors"].append(f"{provider}/{model}: {(res or {}).get('error', 'error')}"[:160])
                continue
            text = res.get("text") or ""
            if _is_ai_refusal(text):
                result["errors"].append(f"{provider}/{model}: refused")
                continue
            parsed = _parse_ai_json(text)
            if not isinstance(parsed, dict) or "only_target_changed" not in parsed:
                result["errors"].append(f"{provider}/{model}: json")
                continue
            result.update({
                "checked": True,
                "ok": _as_bool(parsed.get("only_target_changed")),
                "provider": provider,
                "model": model,
                "reason": str(parsed.get("unwanted_changes") or "")[:200],
            })
            return result
        result["reason"] = "all_output_validation_models_failed"
        return result
    except Exception as exc:
        logger.warning("output judge skipped service=%s error=%s", service_key, type(exc).__name__)
        result["reason"] = f"judge_error:{type(exc).__name__}"
        return result
    finally:
        if path:
            try:
                os.remove(path)
            except Exception:
                pass


def judge_saved_file(service_key: str, before, after_path: str) -> Dict[str, Any]:
    """نسخهٔ فایلی: خروجی ذخیره‌نشدهٔ موقت را باز می‌کند و با تصویر قبل مقایسه می‌کند."""
    if service_key not in JUDGE_SERVICES:
        return {"checked": False, "ok": None, "provider": "", "model": "",
                "reason": "service_out_of_scope", "errors": []}
    if before is None or not after_path:
        return {"checked": False, "ok": None, "provider": "", "model": "",
                "reason": "no_before_image", "errors": []}
    try:
        from PIL import Image

        with Image.open(after_path) as opened:
            after = opened.convert("RGB").copy()
    except Exception as exc:
        return {"checked": False, "ok": None, "provider": "", "model": "",
                "reason": f"after_unreadable:{type(exc).__name__}", "errors": []}
    return judge_output(service_key, before, after)
