# -*- coding: utf-8 -*-
"""Generic orchestration helpers for the three new Buti AI services.

The owner module remains `giso/buti_ai/`; service-specific options, prompts,
masking and guided renderers live in each service folder.
"""
from __future__ import annotations

import importlib
import os
from datetime import datetime
from typing import Any, Dict

from giso.buti_ai.eyebrow.upload import missing_photo_status, save_eyebrow_photo
from giso.buti_ai.service_catalog import SERVICE_HAIR_COLOR, SERVICE_LIP, SERVICE_NAIL, get_service_meta
from giso.buti_ai.services import save_mirror_session

SERVICE_MODULES = {
    SERVICE_NAIL: "giso.buti_ai.nail.final_design",
    SERVICE_HAIR_COLOR: "giso.buti_ai.hair_color.final_design",
    SERVICE_LIP: "giso.buti_ai.lip.final_design",
}

CHANGE_LEVELS = {
    "very_natural": "خیلی طبیعی",
    "medium": "تغییر متوسط",
    "clear": "تغییر واضح‌تر",
}
DEFAULT_CHANGE_LEVEL = "medium"


def service_module(service_key: str):
    path = SERVICE_MODULES.get(str(service_key or "").strip().lower())
    if not path:
        raise KeyError(f"unsupported Buti AI service: {service_key}")
    return importlib.import_module(path)


def normalize_change_level(value: Any) -> str:
    value = str(value or "").strip().lower()
    return value if value in CHANGE_LEVELS else DEFAULT_CHANGE_LEVEL


def normalize_model_key(service_key: str, value: Any) -> str:
    module = service_module(service_key)
    styles = getattr(module, "STYLES", {})
    default = getattr(module, "DEFAULT_STYLE", next(iter(styles), ""))
    value = str(value or "").strip().lower()
    return value if value in styles else default


def initial_form_values(service_key: str) -> Dict[str, str]:
    module = service_module(service_key)
    return {
        "style": getattr(module, "DEFAULT_STYLE", ""),
        "change_level": DEFAULT_CHANGE_LEVEL,
    }


def build_result(service_key: str, style_key: str, change_key: str, photo_status: Dict[str, Any],
                 detection: Dict[str, Any] | None = None, quality_report: Dict[str, Any] | None = None) -> Dict[str, Any]:
    module = service_module(service_key)
    styles = getattr(module, "STYLES", {})
    style_key = normalize_model_key(service_key, style_key)
    change_key = normalize_change_level(change_key)
    style = styles[style_key]
    meta = get_service_meta(service_key)
    return {
        "service_key": service_key,
        "service_slug": meta.get("slug"),
        "service_label": meta.get("title"),
        "style_key": style_key,
        "selected_style_key": style_key,
        "style": style,
        "change_key": change_key,
        "selected_change_key": change_key,
        "change_label": CHANGE_LEVELS.get(change_key, CHANGE_LEVELS[DEFAULT_CHANGE_LEVEL]),
        "photo_received": bool((photo_status or {}).get("ok")),
        "quality": quality_report or {"status": "local_checked", "ok": True, "message": "عکس دریافت شد."},
        "detection": detection or {},
        "short_reason": style.get("why") or style.get("summary") or "این مدل برای پیش‌نمایش قبل/بعد آماده شد.",
        "do": list(style.get("do") or [])[:3],
        "avoid": list(style.get("avoid") or [])[:3],
        "preview": {
            "available": bool((photo_status or {}).get("filename")),
            "before_filename": (photo_status or {}).get("filename"),
            "generated": False,
            "mode": "service_photo_ready",
        },
    }


def process_service_submission(service_key: str, form, files, user_id=None) -> Dict[str, Any]:
    module = service_module(service_key)
    form = form or {}
    files = files or {}
    style_key = normalize_model_key(service_key, form.get("style"))
    change_key = normalize_change_level(form.get("change_level"))
    form_values = {"style": style_key, "change_level": change_key}
    photo_status = missing_photo_status()
    result = None
    error_message = ""
    flash_message = ""
    flash_category = "info"
    detection: Dict[str, Any] = {}
    quality_report: Dict[str, Any] = {}

    photo = files.get("photo") if hasattr(files, "get") else None
    photo_status = save_eyebrow_photo(photo, upload_dir=getattr(module, "UPLOAD_DIR"), prefix=service_key)
    if not photo_status.get("ok"):
        error_message = photo_status.get("message") or "عکس دریافت نشد."
    else:
        quality_fn = getattr(module, "check_photo_quality", None) or getattr(module, "local_quality_report", None)
        try:
            quality_report = quality_fn(photo_status.get("path")) if quality_fn else {"ok": True, "status": "local_checked", "message": "عکس دریافت شد."}
        except Exception:
            quality_report = module.local_quality_report(photo_status.get("path")) if hasattr(module, "local_quality_report") else {"ok": True, "status": "local_checked"}
        if quality_report.get("ok") is False:
            error_message = quality_report.get("message") or "این عکس برای طراحی دقیق مناسب نیست."
        else:
            detection = module.detect_regions(photo_status.get("path"), allow_fallback=True)
            analysis_data = {}
            try:
                analysis_fn_name = {
                    "nail": "analyze_nail_photo",
                    "hair_color": "analyze_hair_color_photo",
                    "lip_shading": "analyze_lip_photo",
                }.get(service_key, "")
                analysis_fn = getattr(module, analysis_fn_name, None) if analysis_fn_name else None
                if callable(analysis_fn):
                    analysis_result = analysis_fn(photo_status.get("path"), style_key, change_key)
                    if isinstance(analysis_result, dict) and analysis_result.get("data"):
                        analysis_data = analysis_result.get("data") or {}
            except Exception:
                analysis_data = {}
            result = build_result(service_key, style_key, change_key, photo_status, detection=detection, quality_report=quality_report)
            if analysis_data:
                result["ai_analysis"] = analysis_data
                if analysis_data.get("short_reason"):
                    result["short_reason"] = analysis_data.get("short_reason")
                if analysis_data.get("do"):
                    result["do"] = list(analysis_data.get("do") or [])[:3]
                if analysis_data.get("avoid"):
                    result["avoid"] = list(analysis_data.get("avoid") or [])[:3]
            session_id = save_mirror_session(
                user_id=user_id,
                service_type=str(get_service_meta(service_key).get("service_type") or service_key),
                city="مشهد",
                status=f"{service_key}_photo_ready_final_design",
            )
            result["session_id"] = session_id
            flash_message = "عکس دریافت شد؛ همین مدل وارد طراحی عکس نهایی می‌شود."
            flash_category = "success"

    return {
        "service_key": service_key,
        "service_meta": get_service_meta(service_key),
        "styles": getattr(module, "STYLES", {}),
        "change_levels": CHANGE_LEVELS,
        "form_values": form_values,
        "result": result,
        "error_message": error_message,
        "flash_message": flash_message,
        "flash_category": flash_category,
        "photo_status": photo_status,
        "quality_report": quality_report,
        "detection": detection,
    }


def build_final_candidate(service_key: str, result: Dict[str, Any], photo_status: Dict[str, Any]) -> Dict[str, Any]:
    module = service_module(service_key)
    result = result or {}
    photo_status = photo_status or {}
    style_key = normalize_model_key(service_key, result.get("selected_style_key") or result.get("style_key"))
    change_key = normalize_change_level(result.get("selected_change_key") or result.get("change_key"))
    styles = getattr(module, "STYLES", {})
    meta = get_service_meta(service_key)
    filename = os.path.basename(str(photo_status.get("filename") or (result.get("preview") or {}).get("before_filename") or ""))
    created_at = datetime.utcnow().isoformat(timespec="seconds")
    return {
        "service_key": service_key,
        "service_slug": meta.get("slug"),
        "service_label": meta.get("title"),
        "service_type": meta.get("service_type") or service_key,
        "beauty_center_service": meta.get("beauty_center_service") or "",
        "session_id": result.get("session_id"),
        "photo_filename": filename,
        "selected_style": style_key,
        "selected_label": styles[style_key]["label"],
        "final_style": style_key,
        "final_label": styles[style_key]["label"],
        "change_key": change_key,
        "change_label": CHANGE_LEVELS.get(change_key, CHANGE_LEVELS[DEFAULT_CHANGE_LEVEL]),
        "short_reason": result.get("short_reason") or styles[style_key].get("why") or styles[style_key].get("summary") or "",
        "do": list(result.get("do") or styles[style_key].get("do") or [])[:3],
        "avoid": list(result.get("avoid") or styles[style_key].get("avoid") or [])[:3],
        "detection": result.get("detection") or {},
        "created_at": created_at,
        "cache_key": f"{filename}-{created_at}" if filename else created_at,
    }


def source_image_path(service_key: str, candidate: Dict[str, Any]) -> str:
    module = service_module(service_key)
    filename = os.path.basename(str((candidate or {}).get("photo_filename") or ""))
    if not filename:
        return ""
    root = os.path.abspath(getattr(module, "UPLOAD_DIR"))
    path = os.path.abspath(os.path.join(root, filename))
    if not path.startswith(root + os.sep):
        return ""
    return path if os.path.exists(path) else ""


def generate_final_design(service_key: str, candidate: Dict[str, Any]) -> Dict[str, Any]:
    module = service_module(service_key)
    try:
        from giso.buti_ai.service_image_generation import generate_final_design as generate_service_image
        return generate_service_image(service_key, module, candidate or {})
    except Exception:
        return module.generate_guided_design(candidate or {})


def uploaded_root(service_key: str) -> str:
    return str(getattr(service_module(service_key), "UPLOAD_DIR"))
