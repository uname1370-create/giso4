# -*- coding: utf-8 -*-
"""ساخت خروجی متنی MVP برای آینه ابرو."""
from giso.buti_ai.eyebrow.options import CHANGE_LEVELS, DEFAULT_CHANGE_LEVEL, EYEBROW_STYLES, normalize_change_level, normalize_style_key


def change_note(change_key):
    change_key = normalize_change_level(change_key)
    if change_key == "clear":
        return "چون تغییر واضح‌تر انتخاب شده، پیشنهاد MVP این است که فرم نهایی حتماً با متخصص کنترل شود تا حالت چهره عوض نشود."
    if change_key == "medium":
        return "برای تغییر متوسط، بهتر است قوس و دم ابرو کمی اصلاح شود اما تاج ابرو نرم بماند."
    return "برای نتیجه طبیعی، بهتر است فقط نظم، تقارن و پرکردن نقاط خالی در اولویت باشد."


def build_eyebrow_result(style_key, change_key, photo_status, demo_mode=False):
    style_key = normalize_style_key(style_key)
    change_key = normalize_change_level(change_key)
    style = EYEBROW_STYLES[style_key]
    change_label = CHANGE_LEVELS.get(change_key, CHANGE_LEVELS[DEFAULT_CHANGE_LEVEL])

    return {
        "style_key": style_key,
        "style": style,
        "change_key": change_key,
        "change_label": change_label,
        "change_note": change_note(change_key),
        "photo_received": bool((photo_status or {}).get("ok")),
        "demo_mode": bool(demo_mode),
        "mvp_notice": "این نتیجه نسخه اول آینه ابرو است. تحلیل دقیق AI و پیش‌نمایش تصویری در فاز بعد اضافه می‌شود.",
    }
