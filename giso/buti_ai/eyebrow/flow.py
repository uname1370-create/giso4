# -*- coding: utf-8 -*-
"""ارکستریشن سناریوی آینه ابرو؛ بدون وابستگی مستقیم به Flask routeها."""
import logging
import os
from typing import Any, Dict

from giso.buti_ai.eyebrow.ai import check_photo_quality
from giso.buti_ai.eyebrow.landmarks import detect_eyebrow_regions
from giso.buti_ai.eyebrow.options import initial_form_values, normalize_change_level, normalize_style_key
from giso.buti_ai.eyebrow.preview import build_before_after_preview
from giso.buti_ai.eyebrow.result import build_eyebrow_result
from giso.buti_ai.eyebrow.upload import missing_photo_status, save_eyebrow_photo
from giso.buti_ai.services import save_mirror_session

logger = logging.getLogger(__name__)
_SECRET_KEYS = {"api_key", "token", "secret", "password", "authorization", "cf_api_token", "openai_api_key"}

def _trace_log(step: str, message: str, **fields: Any) -> None:
    try:
        safe: Dict[str, Any] = {}
        for k, v in fields.items():
            lk = str(k).lower()
            if any(sk in lk for sk in _SECRET_KEYS):
                safe[k] = "***"
            elif isinstance(v, (bytes, bytearray)):
                safe[k] = f"<{len(v)} bytes>"
            else:
                safe[k] = v
        suffix = " ".join(f"{kk}={vv}" for kk, vv in safe.items()) if safe else ""
        line = f"[EYEBROW_TRACE][{step}] {message}" + (f" {suffix}" if suffix else "")
        logger.info(line)
    except Exception:
        try:
            logger.info(f"[EYEBROW_TRACE][{step}] {message}")
        except Exception:
            pass


def get_mirror_services(eyebrow_href):
    """لیست خدمات آینه زیبایی برای صفحه اصلی Buti AI."""
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
    """پردازش POST آینه ابرو و تولید state لازم برای template."""
    _trace_log("01", "process_eyebrow_submission_start", file="flow.py", func="process_eyebrow_submission", user_id=user_id)
    form = form or {}
    files = files or {}
    style_key = normalize_style_key(form.get("style"))
    change_key = normalize_change_level(form.get("change_level"))
    demo_mode = form.get("demo_mode") == "1"
    _trace_log("01", "submission_params", style=style_key, change_level=change_key, demo_mode=demo_mode)
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
        _trace_log("02", "input_photo_saved", ok=photo_status.get("ok"), filename=photo_status.get("filename",""), photo_message=str(photo_status.get("message",""))[:80])
        if not photo_status.get("ok"):
            error_message = photo_status.get("message") or "عکس دریافت نشد."
        else:
            try:
                _pfile = photo_status.get("filename","")
                _ppath = photo_status.get("path","")
                _exists = os.path.exists(_ppath) if _ppath else False
                _fsize = os.path.getsize(_ppath) if _exists else 0
            except Exception:
                _exists, _fsize = False, 0
            _trace_log("02", "input_image_flow", filename=photo_status.get("filename",""), exists=_exists, file_size=_fsize)
            quality_report = check_photo_quality(photo_status.get("path"))
            _trace_log("03", "quality_check_done", ok=quality_report.get("ok"), status=quality_report.get("status"))
            if quality_report.get("status") == "ai_checked" and quality_report.get("ok") is False:
                error_message = quality_report.get("message") or "این عکس برای طراحی دقیق مناسب نیست."
                _trace_log("03", "quality_check_failed", error_msg=str(error_message)[:120])
            else:
                try:
                    eyebrow_detection = detect_eyebrow_regions(photo_status.get("path"), allow_fallback=False, style_key=style_key)
                except TypeError:
                    eyebrow_detection = detect_eyebrow_regions(photo_status.get("path"), allow_fallback=False)
                _trace_log("03", "eyebrow_detection_flow", ok=eyebrow_detection.get("ok"), method=eyebrow_detection.get("method"), regions=len(eyebrow_detection.get("regions") or []), style_key=style_key)
                result = build_eyebrow_result(
                    style_key,
                    change_key,
                    photo_status,
                    demo_mode=False,
                    quality_report=quality_report,
                    ai_analysis=ai_analysis,
                )
                result["eyebrow_detection"] = eyebrow_detection

    if result:
        result["preview"] = build_before_after_preview(photo_status, result)
        session_id = save_mirror_session(
            user_id=user_id,
            service_type="eyebrow",
            city="مشهد",
            status="mvp_demo" if demo_mode else "photo_ready_final_design",
        )
        result["session_id"] = session_id
        _trace_log("01", "submission_done", session_id=session_id, has_preview=bool(result.get("preview")))
        if demo_mode:
            flash_message = "نتیجه نمونه بدون عکس نمایش داده شد."
            flash_category = "info"
        else:
            flash_message = "عکس دریافت شد؛ با همان مدل انتخابی وارد طراحی عکس نهایی می‌شویم."
            flash_category = "success"

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
