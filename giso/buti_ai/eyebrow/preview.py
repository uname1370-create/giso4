# -*- coding: utf-8 -*-
"""ساخت داده طرح راهنمای قبل/بعد برای آینه ابرو.

فعلاً تولید تصویر واقعی ابرو در Giso فعال نیست؛ بنابراین خروجی تصویری به شکل
طرح راهنما و امن نمایش داده می‌شود، بدون تغییر واقعی چهره کاربر.
"""


def build_before_after_preview(photo_status, result):
    filename = (photo_status or {}).get("filename")
    if not filename:
        return {
            "available": False,
            "mode": "no_photo",
            "title": "طرح پیشنهادی نیاز به عکس دارد",
            "note": "برای نمایش طرح راهنما، یک عکس واضح از صورت آپلود کن.",
        }

    style = (result or {}).get("style") or {}
    return {
        "available": True,
        "mode": "guided_before_after",
        "before_filename": filename,
        "after_filename": None,
        "style_label": style.get("label", "مدل پیشنهادی"),
        "title": "طرح پیشنهادی ابرو",
        "note": "این فقط طرح راهنماست؛ تولید تصویر واقعی ابرو در مرحله بعد فعال می‌شود.",
        "generated": False,
    }
