# -*- coding: utf-8 -*-
"""ارکستریشن سناریوی آینه ابرو؛ بدون وابستگی مستقیم به Flask routeها."""
from giso.buti_ai.eyebrow.ai import analyze_eyebrow_photo, check_photo_quality
from giso.buti_ai.eyebrow.options import initial_form_values, normalize_change_level, normalize_style_key
from giso.buti_ai.eyebrow.preview import build_before_after_preview
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


def _demo_quality_report():
    return {
        "status": "demo",
        "ok": None,
        "message": "در حالت نمونه، عکس بررسی نمی‌شود.",
        "checks": {},
        "reasons": [],
    }


def _demo_analysis_report():
    return {
        "status": "demo",
        "ok": None,
        "message": "در حالت نمونه، تحلیل واقعی روی عکس انجام نمی‌شود.",
        "data": {},
    }


def process_eyebrow_submission(form, files, user_id=None):
    """پردازش POST آینه ابرو و تولید state لازم برای template."""
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
    quality_report = {}
    ai_analysis = {}

    if demo_mode:
        quality_report = _demo_quality_report()
        ai_analysis = _demo_analysis_report()
        result = build_eyebrow_result(
            style_key,
            change_key,
            photo_status,
            demo_mode=True,
            quality_report=quality_report,
            ai_analysis=ai_analysis,
        )
    else:
        photo_status = save_eyebrow_photo(files.get("photo") if hasattr(files, "get") else None)
        if not photo_status.get("ok"):
            error_message = photo_status.get("message") or "عکس دریافت نشد."
        else:
            quality_report = check_photo_quality(photo_status.get("path"))
            if quality_report.get("status") == "ai_checked" and quality_report.get("ok") is False:
                error_message = quality_report.get("message") or "این عکس برای تحلیل دقیق مناسب نیست."
            else:
                ai_analysis = analyze_eyebrow_photo(photo_status.get("path"), style_key, change_key)
                result = build_eyebrow_result(
                    style_key,
                    change_key,
                    photo_status,
                    demo_mode=False,
                    quality_report=quality_report,
                    ai_analysis=ai_analysis,
                )

    if result:
        result["preview"] = build_before_after_preview(photo_status, result)
        session_id = save_mirror_session(
            user_id=user_id,
            service_type="eyebrow",
            city="مشهد",
            status="ai_analyzed" if result.get("ai_is_real") else ("mvp_demo" if demo_mode else "mvp_guided_preview"),
        )
        result["session_id"] = session_id
        if demo_mode:
            flash_message = "نتیجه نمونه بدون عکس نمایش داده شد."
            flash_category = "info"
        elif result.get("ai_is_real"):
            flash_message = "عکس بررسی شد و تحلیل هوشمند ابرو آماده است."
            flash_category = "success"
        else:
            flash_message = "عکس دریافت شد؛ نتیجه راهنما و پیش‌نمایش قبل/بعد آماده است."
            flash_category = "info"

    return {
        "form_values": form_values,
        "result": result,
        "error_message": error_message,
        "flash_message": flash_message,
        "flash_category": flash_category,
        "photo_status": photo_status,
        "quality_report": quality_report,
        "ai_analysis": ai_analysis,
        "demo_mode": demo_mode,
    }
