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
        return "تغییر واضح‌تر انتخاب شده؛ بهتر است فرم نهایی با متخصص کنترل شود."
    if change_key == "medium":
        return "تغییر متوسط یعنی قوس و دم ابرو اصلاح شود، اما تاج ابرو نرم بماند."
    return "برای نتیجه طبیعی، نظم، تقارن و پرکردن نقاط خالی مهم‌تر است."


def _clean_list(value, fallback):
    if isinstance(value, list):
        cleaned = [str(item).strip() for item in value if str(item).strip()]
        if cleaned:
            return cleaned[:5]
    return fallback


def _tone_from_bool(value):
    if value is True:
        return "good"
    if value is False:
        return "bad"
    return "warn"


def _bool_value_label(value, ok_text="خوب", bad_text="نیاز به عکس بهتر"):
    if value is True:
        return ok_text
    if value is False:
        return bad_text
    return "نامشخص"


def _clean_score_cards(value):
    if not isinstance(value, list):
        return []
    cards = []
    for item in value:
        if not isinstance(item, dict):
            continue
        label = str(item.get("label") or "").strip()
        result = str(item.get("value") or item.get("result") or "").strip()
        tone = str(item.get("tone") or "warn").strip()
        if label and result:
            cards.append({
                "label": label[:42],
                "value": result[:72],
                "tone": tone if tone in {"good", "warn", "bad"} else "warn",
            })
        if len(cards) >= 6:
            break
    return cards


def _build_score_cards(style, selected_style_key, recommended_style_key, change_label, quality_report, ai_data):
    ai_cards = _clean_score_cards(ai_data.get("score_cards"))
    if ai_cards:
        return ai_cards

    checks = (quality_report or {}).get("checks") or {}
    quality_ok = (quality_report or {}).get("ok")
    model_value = "همین مدل خوب است" if selected_style_key == recommended_style_key else "پیشنهاد بهتر دارد"
    model_tone = "good" if selected_style_key == recommended_style_key else "warn"

    return [
        {
            "label": "کیفیت عکس",
            "value": _bool_value_label(quality_ok, "مناسب", "نامناسب"),
            "tone": _tone_from_bool(quality_ok),
        },
        {
            "label": "وضوح ابرو",
            "value": _bool_value_label(checks.get("eyebrows_visible"), "واضح", "نامشخص"),
            "tone": _tone_from_bool(checks.get("eyebrows_visible")),
        },
        {
            "label": "تناسب انتخاب",
            "value": model_value,
            "tone": model_tone,
        },
        {
            "label": "مدل پیشنهادی",
            "value": style.get("label", ""),
            "tone": "good",
        },
        {
            "label": "میزان تغییر",
            "value": change_label,
            "tone": "warn",
        },
    ]


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
    score_cards = _build_score_cards(
        style,
        selected_style_key,
        recommended_style_key,
        change_label,
        quality_report or {},
        ai_data,
    )

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
        "score_cards": score_cards,
        "confidence": ai_data.get("confidence") or ("medium" if ai_is_real else "guide"),
        "mvp_notice": (
            "عکس تحلیل شد؛ این پیشنهاد بر اساس چهره و انتخاب شماست."
            if ai_is_real else
            "این یک راهنمای اولیه است؛ با عکس واضح، پیشنهاد دقیق‌تر می‌شود."
        ),
    }
