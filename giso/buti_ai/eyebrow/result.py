# -*- coding: utf-8 -*-
"""ساخت خروجی متنی و هوشمند MVP برای آینه ابرو."""
from giso.buti_ai.eyebrow.options import (
    CHANGE_LEVELS,
    DEFAULT_CHANGE_LEVEL,
    DEFAULT_STYLE,
    EYEBROW_STYLES,
    normalize_change_level,
    normalize_style_key,
)

STYLE_SCORE_ORDER = ["natural", "microblading", "powder", "combination", DEFAULT_STYLE]
_ALLOWED_TONES = {"good", "warn", "bad"}


def change_note(change_key):
    change_key = normalize_change_level(change_key)
    if change_key == "clear":
        return "تغییر واضح‌تر انتخاب شده؛ بهتر است فرم نهایی با متخصص کنترل شود."
    if change_key == "medium":
        return "تغییر متوسط یعنی قوس و دم ابرو اصلاح شود، اما تاج ابرو نرم بماند."
    return "برای نتیجه طبیعی، نظم، تقارن و پرکردن نقاط خالی مهم‌تر است."


def _clean_text(value, fallback="", limit=160):
    text = str(value or "").strip()
    if not text:
        text = fallback
    return text[:limit]


def _clean_list(value, fallback, limit=5):
    if isinstance(value, list):
        cleaned = [_clean_text(item, limit=90) for item in value]
        cleaned = [item for item in cleaned if item]
        if cleaned:
            return cleaned[:limit]
    return list(fallback or [])[:limit]


def _tone_from_bool(value):
    if value is True:
        return "good"
    if value is False:
        return "bad"
    return "warn"


def _score_tone(score):
    try:
        score = int(score)
    except Exception:
        score = 0
    if score >= 80:
        return "good"
    if score >= 60:
        return "warn"
    return "bad"


def _bool_value_label(value, ok_text="خوب", bad_text="نیاز به عکس بهتر"):
    if value is True:
        return ok_text
    if value is False:
        return bad_text
    return "نامشخص"


def _clamp_score(value, default=50):
    try:
        if isinstance(value, str):
            value = value.strip().replace("٪", "").replace("%", "")
        score = int(round(float(value)))
    except Exception:
        score = default
    return max(0, min(100, score))


def _normalize_tone(value):
    value = str(value or "warn").strip().lower()
    return value if value in _ALLOWED_TONES else "warn"


def _style_label(style_key):
    style_key = normalize_style_key(style_key)
    return EYEBROW_STYLES[style_key]["label"]


def _clean_score_cards(value):
    if not isinstance(value, list):
        return []
    cards = []
    for item in value:
        if not isinstance(item, dict):
            continue
        label = _clean_text(item.get("label"), limit=42)
        result = _clean_text(item.get("value") or item.get("result"), limit=72)
        tone = _normalize_tone(item.get("tone"))
        if label and result:
            cards.append({"label": label, "value": result, "tone": tone})
        if len(cards) >= 6:
            break
    return cards


def _clean_face_analysis(ai_data):
    raw = ai_data.get("face_analysis") if isinstance(ai_data, dict) else None
    raw = raw if isinstance(raw, dict) else {}
    face_shape = _clean_text(raw.get("face_shape") or ai_data.get("face_shape"), "نامشخص", 40)
    return {
        "face_shape": face_shape,
        "eye_balance": _clean_text(raw.get("eye_balance"), "نامشخص", 40),
        "brow_density": _clean_text(raw.get("brow_density"), "نامشخص", 40),
        "brow_symmetry": _clean_text(raw.get("brow_symmetry"), "نامشخص", 40),
        "brow_arch": _clean_text(raw.get("brow_arch"), "نامشخص", 40),
        "tail_position": _clean_text(raw.get("tail_position"), "نامشخص", 40),
    }


def _default_score_for(style_key, recommended_style_key, selected_style_key):
    if style_key == recommended_style_key:
        return 86
    if style_key == selected_style_key:
        return 74
    defaults = {
        "natural": 72,
        "microblading": 68,
        "powder": 58,
        "combination": 70,
        DEFAULT_STYLE: 76,
    }
    return defaults.get(style_key, 60)


def _fallback_score_reason(style_key, recommended_style_key, selected_style_key):
    if style_key == recommended_style_key:
        return "بهترین جمع‌بندی برای فرم فعلی ابرو و میزان تغییر انتخابی."
    if style_key == selected_style_key:
        return "با سلیقه انتخابی شما نزدیک است، اما شاید نیاز به کنترل متخصص داشته باشد."
    return EYEBROW_STYLES[style_key].get("summary", "گزینه قابل بررسی برای فرم ابرو.")


def _clean_style_scores(value, recommended_style_key, selected_style_key):
    seen = {}
    if isinstance(value, list):
        for item in value:
            if not isinstance(item, dict):
                continue
            raw_style = item.get("style") or item.get("key")
            style_key = normalize_style_key(raw_style)
            score = _clamp_score(item.get("score"), _default_score_for(style_key, recommended_style_key, selected_style_key))
            reason = _clean_text(
                item.get("reason"),
                _fallback_score_reason(style_key, recommended_style_key, selected_style_key),
                120,
            )
            seen[style_key] = {"style_key": style_key, "score": score, "reason": reason}

    for style_key in STYLE_SCORE_ORDER:
        if style_key not in seen:
            seen[style_key] = {
                "style_key": style_key,
                "score": _default_score_for(style_key, recommended_style_key, selected_style_key),
                "reason": _fallback_score_reason(style_key, recommended_style_key, selected_style_key),
            }

    items = []
    for style_key in STYLE_SCORE_ORDER:
        item = seen[style_key]
        score = _clamp_score(item.get("score"), 50)
        items.append({
            "style_key": style_key,
            "label": _style_label(style_key),
            "score": score,
            "reason": _clean_text(item.get("reason"), limit=120),
            "tone": _score_tone(score),
            "is_recommended": style_key == recommended_style_key,
            "is_selected": style_key == selected_style_key,
        })
    return sorted(items, key=lambda item: (item["is_recommended"], item["score"]), reverse=True)


def _build_score_cards(style, selected_style_key, recommended_style_key, change_label, quality_report, ai_data, style_scores):
    ai_cards = _clean_score_cards(ai_data.get("score_cards"))
    if ai_cards:
        return ai_cards

    checks = (quality_report or {}).get("checks") or {}
    quality_ok = (quality_report or {}).get("ok")
    model_value = "همین مدل خوب است" if selected_style_key == recommended_style_key else "پیشنهاد بهتر دارد"
    model_tone = "good" if selected_style_key == recommended_style_key else "warn"
    top_score = style_scores[0]["score"] if style_scores else 0

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
            "label": "امتیاز پیشنهاد",
            "value": f"{top_score}٪",
            "tone": _score_tone(top_score),
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

    ai_recommended_style_key = normalize_style_key(ai_data.get("recommended_style") or selected_style_key)
    # مدل و شدت انتخاب‌شده کاربر Single Source of Truth هستند؛ AI دیگر مدل را عوض نمی‌کند.
    recommended_style_key = selected_style_key
    result_change_key = selected_change_key
    style = EYEBROW_STYLES[selected_style_key]
    change_label = CHANGE_LEVELS.get(result_change_key, CHANGE_LEVELS[DEFAULT_CHANGE_LEVEL])

    fallback_do = style.get("do", [])
    fallback_avoid = style.get("avoid", [])
    ai_is_real = (ai_analysis or {}).get("status") == "ai_analyzed"
    face_analysis = _clean_face_analysis(ai_data)
    style_scores = _clean_style_scores(ai_data.get("style_scores"), recommended_style_key, selected_style_key)
    score_cards = _build_score_cards(
        style,
        selected_style_key,
        recommended_style_key,
        change_label,
        quality_report or {},
        ai_data,
        style_scores,
    )
    ai_reason_allowed = ai_recommended_style_key == selected_style_key
    short_reason = _clean_text(
        (ai_data.get("short_reason") or ai_data.get("why")) if ai_reason_allowed else "",
        style.get("why", ""),
        180,
    )

    return {
        "style_key": recommended_style_key,
        "selected_style_key": selected_style_key,
        "ai_recommended_style_key": ai_recommended_style_key,
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
        "face_shape": face_analysis["face_shape"],
        "face_analysis": face_analysis,
        "current_brow_summary": _clean_text(
            ai_data.get("current_brow_summary"),
            "برای تحلیل دقیق‌تر، عکس واضح روبه‌رو و نور مناسب لازم است.",
            180,
        ),
        "why": _clean_text(ai_data.get("why") if ai_reason_allowed else "", style.get("why", ""), 220),
        "short_reason": short_reason,
        "do": _clean_list(ai_data.get("do") if ai_reason_allowed else [], fallback_do, limit=3),
        "avoid": _clean_list(ai_data.get("avoid") if ai_reason_allowed else [], fallback_avoid, limit=3),
        "alternative_styles": _clean_list(ai_data.get("alternative_styles"), [], limit=2),
        "score_cards": score_cards,
        "style_scores": style_scores,
        "top_style_score": style_scores[0]["score"] if style_scores else 0,
        "confidence": ai_data.get("confidence") or ("medium" if ai_is_real else "guide"),
        "mvp_notice": (
            "عکس تحلیل شد؛ این پیشنهاد بر اساس چهره و انتخاب شماست."
            if ai_is_real else
            "این یک راهنمای اولیه است؛ با عکس واضح، پیشنهاد دقیق‌تر می‌شود."
        ),
    }
