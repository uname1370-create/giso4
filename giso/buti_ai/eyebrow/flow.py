# -*- coding: utf-8 -*-
"""ارکستریشن سبک سناریوی آینه ابرو؛ بدون وابستگی مستقیم به Flask routeها."""
from giso.buti_ai.eyebrow.options import initial_form_values, normalize_change_level, normalize_style_key
from giso.buti_ai.eyebrow.result import build_eyebrow_result
from giso.buti_ai.eyebrow.upload import missing_photo_status, save_eyebrow_photo
from giso.buti_ai.services import save_mirror_session


def get_mirror_services(eyebrow_href):
    """لیست خدمات آینه زیبایی برای صفحه اصلی Buti AI."""
    return [
        {
            "key": "eyebrow",
            "title": "آینه ابرو گیسو",
            "icon": "🪞",
            "description": "فرم مناسب ابرو را قبل از انجام، ساده و قابل فهم بررسی کن.",
            "href": eyebrow_href,
            "status": "active",
        },
        {
            "key": "hair_color",
            "title": "رنگ مو",
            "icon": "🎨",
            "description": "پیش‌نمایش رنگ مو در مرحله‌های بعدی اضافه می‌شود.",
            "href": "#coming-soon",
            "status": "soon",
        },
        {
            "key": "face_beauty",
            "title": "زیبایی چهره",
            "icon": "✨",
            "description": "سناریوهای بعدی مثل لب، پوست و میکاپ بعداً زیر همین ماژول می‌آیند.",
            "href": "#coming-soon",
            "status": "soon",
        },
    ]


def process_eyebrow_submission(form, files, user_id=None):
    """پردازش POST آینه ابرو و تولید state لازم برای template.

    خروجی عمداً dict ساده است تا route فقط نمایش/flash را مدیریت کند.
    """
    form = form or {}
    files = files or {}
    style_key = normalize_style_key(form.get("style"))
    change_key = normalize_change_level(form.get("change_level"))
    demo_mode = form.get("demo_mode") == "1"
    form_values = {"style": style_key, "change_level": change_key}

    result = None
    error_message = ""
    flash_message = ""
    flash_category = "info"
    photo_status = missing_photo_status()

    if not demo_mode:
        photo_status = save_eyebrow_photo(files.get("photo") if hasattr(files, "get") else None)
        if not photo_status.get("ok"):
            error_message = photo_status.get("message") or "عکس دریافت نشد."

    if demo_mode or photo_status.get("ok"):
        result = build_eyebrow_result(style_key, change_key, photo_status, demo_mode=demo_mode)
        session_id = save_mirror_session(
            user_id=user_id,
            service_type="eyebrow",
            city="مشهد",
            status="mvp_demo" if demo_mode else "mvp_photo_received",
        )
        result["session_id"] = session_id
        if demo_mode:
            flash_message = "نتیجه نمونه بدون عکس نمایش داده شد. برای تحلیل دقیق‌تر، در فاز بعد عکس بررسی می‌شود."
            flash_category = "info"
        else:
            flash_message = "عکس دریافت شد و نتیجه MVP آماده است."
            flash_category = "success"

    return {
        "form_values": form_values,
        "result": result,
        "error_message": error_message,
        "flash_message": flash_message,
        "flash_category": flash_category,
        "photo_status": photo_status,
        "demo_mode": demo_mode,
    }
