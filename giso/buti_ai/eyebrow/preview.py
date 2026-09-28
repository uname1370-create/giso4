# -*- coding: utf-8 -*-
"""ساخت داده پیش‌نمایش قبل/بعد برای آینه ابرو.

فعلاً تولید تصویر واقعی ابرو در Giso فعال نیست؛ بنابراین پیش‌نمایش به شکل
قبل/بعد راهنما و امن نمایش داده می‌شود، بدون تغییر واقعی چهره کاربر.
"""


def build_before_after_preview(photo_status, result):
    filename = (photo_status or {}).get("filename")
    if not filename:
        return {
            "available": False,
            "mode": "no_photo",
            "title": "پیش‌نمایش تصویری نیاز به عکس دارد",
            "note": "برای نمایش قبل/بعد، یک عکس واضح از صورت آپلود کن.",
        }

    style = (result or {}).get("style") or {}
    return {
        "available": True,
        "mode": "guided_before_after",
        "before_filename": filename,
        "after_filename": None,
        "style_label": style.get("label", "مدل پیشنهادی"),
        "title": "پیش‌نمایش قبل و بعد",
        "note": "این پیش‌نمایش راهنماست؛ تولید تصویر واقعی ابرو با مدل تصویر در مرحله بعد فعال می‌شود.",
        "generated": False,
    }
