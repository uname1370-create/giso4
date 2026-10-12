# -*- coding: utf-8 -*-
"""ارکستریشن سناریوی آینه ابرو؛ بدون وابستگی مستقیم به Flask routeها."""
from giso.buti_ai.eyebrow.ai import analyze_eyebrow_photo, check_photo_quality
from giso.buti_ai.eyebrow.options import initial_form_values, normalize_change_level, normalize_style_key
from giso.buti_ai.eyebrow.preview import build_before_after_preview
from giso.buti_ai.eyebrow.result import build_eyebrow_result
from giso.buti_ai.eyebrow.upload import missing_photo_status, save_eyebrow_photo
from giso.buti_ai.services import save_mirror_session


def get_mirror_services(eyebrow_href):
    """فهرست سازگار قدیمی خدمات آینه زیبایی برای صفحه اصلی Buti AI."""
    return [
        {
            "key": "eyebrow",
            "title": "آینه ابرو گیسو",
            "icon": "🪞",
            "badge": "پرطرفدار",
            "tag": "فعال",
            "description": "قبل از هزینه، مدل ابروی دلخواهت را روی عکس خودت برای طراحی نهایی ببین.",
            "meta": ["۲ تا ۵ دقیقه", "نیاز: عکس واضح", "طراحی قبل از مراجعه"],
            "image": "brows/eyebrow_ai_mirror.jpg",
            "image_blueprint": "buti_ai",
            "href": eyebrow_href,
            "status": "active",
        },
        {
            "key": "hair_color",
            "title": "آینه رنگ مو",
            "icon": "🎨",
            "badge": "به‌زودی",
            "tag": "مرحله بعد",
            "description": "پیش‌نمایش رنگ مو و تناسب رنگ با پوست و چهره.",
            "meta": ["تمرکز: رنگ و تناژ", "وضعیت: در صف توسعه"],
            "image": "images/analysis_hair.webp",
            "href": "#coming-soon",
            "status": "soon",
        },
        {
            "key": "face_beauty",
            "title": "آینه پوست و چهره",
            "icon": "✨",
            "badge": "به‌زودی",
            "tag": "هوشمند",
            "description": "تحلیل زیبایی چهره، پوست و پیشنهادهای مراقبتی/میکاپ.",
            "meta": ["تمرکز: پوست و تناسب", "وضعیت: طراحی سناریو"],
            "image": "images/sample_skin.webp",
            "href": "#coming-soon",
            "status": "soon",
        },
        {
            "key": "lip_contour",
            "title": "آینه لب و کانتور",
            "icon": "💋",
            "badge": "به‌زودی",
            "tag": "PMU",
            "description": "بررسی فرم لب، کانتور ملایم و تناسب رنگ با چهره.",
            "meta": ["تمرکز: فرم و رنگ", "وضعیت: ایده‌پردازی"],
            "image": "images/catalog/lipstick-argan-nika.jpg",
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
    """ذخیرهٔ عکس، بررسی کیفیت و تحلیل پیش از تأیید نهایی کاربر.

    این تابع عمداً generation یا mask نهایی را اجرا نمی‌کند. route باید candidate
    را نگه دارد و فقط بعد از ``analysis_confirmed=1`` به صفحهٔ final برود.
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
    quality_report = {}
    ai_analysis = {}
    eyebrow_detection = {}

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
            if quality_report.get("ok") is False:
                error_message = quality_report.get("message") or "این عکس برای تحلیل دقیق مناسب نیست."
            else:
                ai_analysis = analyze_eyebrow_photo(
                    photo_status.get("path"), style_key, change_key
                )
                result = build_eyebrow_result(
                    style_key,
                    change_key,
                    photo_status,
                    demo_mode=False,
                    quality_report=quality_report,
                    ai_analysis=ai_analysis,
                )
                # Mask detection/generation is intentionally deferred until the
                # user confirms one of the offered styles.
                result["eyebrow_detection"] = eyebrow_detection

    if result:
        result["preview"] = build_before_after_preview(photo_status, result)
        analysis_status = str(ai_analysis.get("status") or "").strip()
        session_id = save_mirror_session(
            user_id=user_id,
            service_type="eyebrow",
            city="مشهد",
            status="mvp_demo" if demo_mode else (
                "ai_analyzed" if analysis_status == "ai_analyzed" else "photo_checked"
            ),
        )
        result["session_id"] = session_id
        if demo_mode:
            flash_message = "نتیجه نمونه بدون عکس نمایش داده شد."
            flash_category = "info"
        elif analysis_status == "ai_analyzed":
            flash_message = "عکس و تحلیل آماده است؛ یکی از دو گزینه را تأیید کن."
            flash_category = "success"
        else:
            flash_message = "عکس بررسی شد؛ تحلیل هوشمند در دسترس نبود و انتخاب مدل خودت حفظ شده است."
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
        "eyebrow_detection": eyebrow_detection,
        "demo_mode": demo_mode,
    }
