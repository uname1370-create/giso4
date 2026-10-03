# -*- coding: utf-8 -*-
"""AI Consultant context for Beauty Mirror – minimal implementation.

Context:
  Service + Selected Style + Analysis + Preview Result

This consultant is not a generic chat – it talks about the same result.
"""
from __future__ import annotations

from typing import Any, Dict


def build_consultant_context(service_key: str, candidate: Dict[str, Any], generation: Dict[str, Any] | None = None) -> Dict[str, Any]:
    service_key = str(service_key or "").strip().lower()
    candidate = candidate or {}
    generation = generation or {}
    service_label = str(candidate.get("service_label") or candidate.get("service_type") or service_key)
    style_label = str(candidate.get("final_label") or candidate.get("selected_label") or candidate.get("final_style") or "")
    change_label = str(candidate.get("change_label") or "")
    short_reason = str(candidate.get("short_reason") or "")
    do_list = list(candidate.get("do") or [])[:3]
    avoid_list = list(candidate.get("avoid") or [])[:3]
    detection = candidate.get("detection") if isinstance(candidate.get("detection"), dict) else {}
    mask = detection.get("mask") if isinstance(detection.get("mask"), dict) else {}
    is_ai = bool(generation.get("is_ai_generated"))
    return {
        "service_key": service_key,
        "service_label": service_label,
        "style_label": style_label,
        "change_label": change_label,
        "short_reason": short_reason,
        "do": do_list,
        "avoid": avoid_list,
        "detection_method": detection.get("method") or "unknown",
        "mask_real": bool(mask.get("real_mask")),
        "mask_coverage": mask.get("coverage_ratio"),
        "is_ai_generated": is_ai,
        "generation_status": generation.get("status") or "",
        "final_filename": generation.get("filename") or "",
        "prompt": (
            f"تو مشاور هوشمند {service_label} در گیسو هستی. "
            f"کاربر خدمت {service_label} با مدل {style_label} و شدت {change_label} را انتخاب کرده. "
            f"تحلیل: {short_reason}. "
            f"باید: {'; '.join(do_list)}. نباید: {'; '.join(avoid_list)}. "
            f"نتیجه Preview: {'AI واقعی' if is_ai else 'راهنمای غیر AI'} – روش تشخیص ناحیه: {detection.get('method')}. "
            f"فقط درباره همین نتیجه صحبت کن، قیمت سالن تعیین نکن، تصمیم پزشکی قطعی نده."
        ),
    }


def consultant_invite_text(context: Dict[str, Any]) -> str:
    service_label = context.get("service_label") or "این خدمت"
    style_label = context.get("style_label") or "مدل انتخابی"
    return f"نتیجه {service_label} با مدل {style_label} آماده است. سوالی درباره اجرا، مراقبت یا انتخاب مرکز داری؟ از مشاور گیسو بپرس."


__all__ = ["build_consultant_context", "consultant_invite_text"]
