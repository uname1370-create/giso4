# -*- coding: utf-8 -*-
"""اتصال کنترل‌شده آینه ابرو به موتور بینایی فعلی گیسو.

این فایل منطق محصول را داخل Buti AI نگه می‌دارد و فقط از موتور مشترک
vision به عنوان اتصال نازک استفاده می‌کند.
"""
import logging

from giso.buti_ai.eyebrow.options import CHANGE_LEVELS, EYEBROW_STYLES, normalize_change_level, normalize_style_key
from giso.buti_ai.eyebrow.prompts import PHOTO_QUALITY_PROMPT, eyebrow_analysis_prompt

logger = logging.getLogger("giso_buti_ai_eyebrow_ai")


def _call_assigned_vision_json(image_path, prompt, max_tokens=1000, limit=None):
    """اولویت اختصاصی آینه ابرو از مدیریت AI؛ اگر خالی بود None.

    اگر یک سرویس مثل cf1 خطا بدهد، بقیه اسلات‌های همین زنجیره (cf2/cf3 یا
    پروایدرهای دیگر مدیریت AI) امتحان می‌شوند و بعد fallback عمومی vision اجرا می‌شود.
    """
    try:
        from giso.async_compat import run_async_safe
        from giso.ai_brain import ask_ai_vision
        from giso.analysis import _is_ai_refusal, _parse_ai_json
        from giso.buti_ai.ai_models import configured_vision_chain
    except Exception as exc:
        logger.debug("Buti AI assigned vision unavailable: %s", exc)
        return None

    chain = configured_vision_chain()
    if not chain:
        return None

    errors = []
    tried = 0
    for item in chain:
        provider = item.get("provider_name") or ""
        model = item.get("model_name") or ""
        if not provider or not model:
            continue
        if limit is not None and tried >= int(limit or 1):
            break
        tried += 1
        try:
            result = run_async_safe(ask_ai_vision(provider, image_path, prompt, model=model, max_tokens=max_tokens))
        except Exception as exc:
            result = {"ok": False, "error": f"{type(exc).__name__}: {exc}"}
        if result and result.get("ok"):
            text = result.get("text", "") or ""
            if _is_ai_refusal(text):
                errors.append(f"{provider}/{model}: refused")
                continue
            parsed = _parse_ai_json(text)
            if parsed is not None:
                return {"ok": True, "provider": provider, "model": model, "data": parsed, "text": text}
            errors.append(f"{provider}/{model}: json")
        else:
            errors.append(f"{provider}/{model}: {(result or {}).get('error', 'error')}")
    return {"ok": False, "error": "؛ ".join(errors[-3:]) or "assigned_vision_failed"}


def _call_vision_json(image_path, prompt, max_tokens=1000, assigned_limit=None, global_fallback=True):
    """فراخوانی موتور vision موجود با اولویت مدل اختصاصی آینه ابرو."""
    try:
        assigned = _call_assigned_vision_json(image_path, prompt, max_tokens=max_tokens, limit=assigned_limit)
        if assigned and assigned.get("ok"):
            return assigned
        if assigned and not global_fallback:
            return assigned
    except Exception as exc:
        logger.debug("Buti AI assigned vision failed before fallback: %s", exc)
        if not global_fallback:
            return {"ok": False, "error": f"{type(exc).__name__}: {str(exc)[:180]}"}
    if not global_fallback:
        return {"ok": False, "error": "assigned_vision_unavailable"}
    try:
        from giso.analysis import call_vision_with_fallback

        return call_vision_with_fallback([image_path], prompt, max_tokens=max_tokens)
    except Exception as exc:
        logger.warning("Buti AI vision call failed: %s", exc)
        return {"ok": False, "error": f"{type(exc).__name__}: {str(exc)[:180]}"}


def check_photo_quality(image_path):
    """بررسی کیفیت عکس با AI؛ اگر provider آماده نبود، fallback شفاف برمی‌گردد."""
    if not image_path:
        return {
            "status": "missing",
            "ok": False,
            "message": "عکسی برای بررسی دریافت نشد.",
            "checks": {},
            "reasons": ["no_image"],
        }

    try:
        result = _call_vision_json(image_path, PHOTO_QUALITY_PROMPT, max_tokens=700, assigned_limit=None, global_fallback=True)
    except TypeError:
        # تست‌های قدیمی این تابع داخلی را با امضای ساده monkeypatch می‌کنند.
        result = _call_vision_json(image_path, PHOTO_QUALITY_PROMPT, max_tokens=700)
    if not result.get("ok"):
        return {
            "status": "ai_unavailable",
            "ok": None,
            "message": "بررسی هوشمند عکس فعلاً در دسترس نیست؛ اگر عکس واضح است می‌توانی وارد طراحی شوی.",
            "checks": {},
            "reasons": [result.get("error", "ai_unavailable")],
        }

    data = result.get("data") or {}
    ok = bool(data.get("ok"))
    return {
        "status": "ai_checked",
        "ok": ok,
        "message": data.get("message") or ("عکس برای طراحی مناسب است." if ok else "این عکس برای طراحی دقیق مناسب نیست."),
        "checks": {
            "face_visible": data.get("face_visible"),
            "eyebrows_visible": data.get("eyebrows_visible"),
            "lighting": data.get("lighting"),
            "angle": data.get("angle"),
            "sharpness": data.get("sharpness"),
        },
        "reasons": data.get("reasons") or [],
        "provider": result.get("provider"),
        "model": result.get("model"),
    }


def analyze_eyebrow_photo(image_path, selected_style_key, change_level_key):
    """تحلیل ابرو با AI؛ در نبود provider، fallback شفاف می‌دهد."""
    selected_style_key = normalize_style_key(selected_style_key)
    change_level_key = normalize_change_level(change_level_key)
    selected_style = EYEBROW_STYLES[selected_style_key]["label"]
    change_level = CHANGE_LEVELS[change_level_key]

    if not image_path:
        return {
            "status": "missing",
            "ok": False,
            "message": "برای تحلیل واقعی ابرو، عکس واضح لازم است.",
            "data": {},
        }

    prompt = eyebrow_analysis_prompt(selected_style, change_level)
    result = _call_vision_json(image_path, prompt, max_tokens=1300)
    if not result.get("ok"):
        return {
            "status": "ai_unavailable",
            "ok": None,
            "message": "تحلیل هوشمند ابرو فعلاً در دسترس نیست؛ نتیجه راهنمای اولیه نمایش داده می‌شود.",
            "data": {},
            "error": result.get("error", "ai_unavailable"),
        }

    data = result.get("data") or {}
    if not isinstance(data, dict):
        data = {}
    data["recommended_style"] = normalize_style_key(data.get("recommended_style") or selected_style_key)
    data["change_level"] = normalize_change_level(data.get("recommended_change_level") or data.get("change_level") or change_level_key)
    for key in ("do", "avoid", "alternative_styles", "style_scores", "score_cards"):
        if not isinstance(data.get(key), list):
            data[key] = []
    if not isinstance(data.get("face_analysis"), dict):
        data["face_analysis"] = {}
    return {
        "status": "ai_analyzed",
        "ok": True,
        "message": "تحلیل هوشمند ابرو انجام شد.",
        "data": data,
        "provider": result.get("provider"),
        "model": result.get("model"),
    }
