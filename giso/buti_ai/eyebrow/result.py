# -*- coding: utf-8 -*-
"""ساخت خروجی متنی و هوشمند MVP برای آینه ابرو."""
from giso.buti_ai.eyebrow.options import (
    CHANGE_LEVELS,
    DEFAULT_CHANGE_LEVEL,
    EYEBROW_STYLES,
    normalize_change_level,
    normalize_style_key,
)


def change_note(change_key):
    change_key = normalize_change_level(change_key)
    if change_key == "clear":
        return "چون تغییر واضح‌تر انتخاب شده، فرم نهایی بهتر است حتماً با متخصص کنترل شود تا حالت چهره عوض نشود."
    if change_key == "medium":
        return "برای تغییر متوسط، بهتر است قوس و دم ابرو کمی اصلاح شود اما تاج ابرو نرم بماند."
    return "برای نتیجه طبیعی، بهتر است فقط نظم، تقارن و پرکردن نقاط خالی در اولویت باشد."


def _clean_list(value, fallback):
    if isinstance(value, list):
        cleaned = [str(item).strip() for item in value if str(item).strip()]
        if cleaned:
            return cleaned[:5]
    return fallback


def build_eyebrow_result(style_key, change_key, photo_status, demo_mode=False,
                         quality_report=None, ai_analysis=None):
    selected_style_key = normalize_style_key(style_key)
    selected_change_key = normalize_change_level(change_key)
    ai_data = (ai_analysis or {}).get("data") or {}

    recommended_style_key = normalize_style_key(ai_data.get("recommended_style") or selected_style_key)
    result_change_key = normalize_change_level(ai_data.get("change_level") or selected_change_key)
    style = EYEBROW_STYLES[recommended_style_key]
    change_label = CHANGE_LEVELS.get(result_change_key, CHANGE_LEVELS[DEFAULT_CHANGE_LEVEL])

    fallback_do = style.get("do", [])
    fallback_avoid = style.get("avoid", [])
    ai_is_real = (ai_analysis or {}).get("status") == "ai_analyzed"

    return {
        "style_key": recommended_style_key,
        "selected_style_key": selected_style_key,
        "style": style,
        "change_key": result_change_key,
        "selected_change_key": selected_change_key,
        "change_label": change_label,
        "change_note": change_note(result_change_key),
        "photo_received": bool((photo_status or {}).get("ok")),
        "demo_mode": bool(demo_mode),
        "quality": quality_report or {},
        "ai_analysis": ai_analysis or {},
        "ai_is_real": ai_is_real,
        "face_shape": ai_data.get("face_shape") or "در نسخه راهنما مشخص نشده",
        "current_brow_summary": ai_data.get("current_brow_summary") or "برای تحلیل دقیق‌تر، عکس واضح روبه‌رو و نور مناسب لازم است.",
        "why": ai_data.get("why") or style.get("why", ""),
        "do": _clean_list(ai_data.get("do"), fallback_do),
        "avoid": _clean_list(ai_data.get("avoid"), fallback_avoid),
        "alternative_styles": _clean_list(ai_data.get("alternative_styles"), []),
        "confidence": ai_data.get("confidence") or ("medium" if ai_is_real else "guide"),
        "mvp_notice": (
            "تحلیل هوشمند ابرو انجام شد و نتیجه زیر بر اساس عکس شماست."
            if ai_is_real else
            "این نتیجه راهنمای اولیه است؛ اگر سرویس هوش مصنوعی تصویر فعال باشد، تحلیل دقیق‌تر نمایش داده می‌شود."
        ),
    }
