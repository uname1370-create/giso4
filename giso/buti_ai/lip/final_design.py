# -*- coding: utf-8 -*-
"""Guided final design for آینه لب و شیدینگ گیسو."""
from __future__ import annotations

import os
import uuid
from datetime import datetime
from typing import Any, Dict, Tuple

from giso.config import Config

SERVICE_KEY = "lip_shading"
UPLOAD_DIR = os.path.join(Config.GISO_DIR, "data", "uploads", "buti_ai", SERVICE_KEY)
FINAL_DIR = os.path.join(UPLOAD_DIR, "final")

DEFAULT_STYLE = "natural_shading"
STYLES: Dict[str, Dict[str, Any]] = {
    "natural_shading": {
        "label": "شیدینگ لب طبیعی",
        "icon": "💋",
        "summary": "رنگ طبیعی و یکدست برای لب بدون ظاهر رژ سنگین.",
        "why": "برای کاربرانی که نتیجه PMU ملایم می‌خواهند مناسب است.",
        "color": (184, 84, 98),
        "alpha": 88,
        "do": ["بافت لب حفظ شود", "رنگ خیلی سنگین نشود", "فرم لب عوض نشود"],
        "avoid": ["بزرگ کردن غیرواقعی", "رنگ خارج لب", "تغییر پوست اطراف لب"],
    },
    "soft_pink_tint": {
        "label": "تینت صورتی ملایم",
        "icon": "🌷",
        "summary": "صورتی نرم و شاداب برای ظاهر روزانه.",
        "why": "برای قبل/بعد ملایم و قابل فهم برای مشتری مناسب است.",
        "color": (220, 102, 132),
        "alpha": 92,
        "do": ["صورتی ملایم باشد", "هایلایت طبیعی لب بماند", "پوست تغییر نکند"],
        "avoid": ["رژ فانتزی", "خط لب بیرون‌زده", "تغییر دندان"],
    },
    "peach_nude": {
        "label": "نود گلبهی",
        "icon": "🍑",
        "summary": "رنگ نود گرم و طبیعی برای سبک روزانه.",
        "why": "برای کاربران علاقه‌مند به رنگ طبیعی و شیک مناسب است.",
        "color": (202, 112, 92),
        "alpha": 84,
        "do": ["نود گرم و طبیعی باشد", "حجم لب اغراق نشود", "بافت حفظ شود"],
        "avoid": ["رنگ خیلی نارنجی", "مات و تخت شدن", "تغییر صورت"],
    },
    "natural_contour": {
        "label": "کانتور لب طبیعی",
        "icon": "✍️",
        "summary": "مرز لب کمی مرتب‌تر و متقارن‌تر دیده می‌شود.",
        "why": "برای نمایش ارزش کار PMU بدون اغراق مناسب است.",
        "color": (156, 62, 78),
        "alpha": 74,
        "contour": True,
        "do": ["خط لب نرم باشد", "تقارن کمی بهتر شود", "مرکز لب طبیعی بماند"],
        "avoid": ["overline زیاد", "بزرگ‌نمایی لب", "تغییر دندان/پوست"],
    },
    "dark_tone_neutralize": {
        "label": "رفع تیرگی و یکدست‌سازی رنگ لب",
        "icon": "🩷",
        "summary": "تیرگی لب نرم‌تر و رنگ کلی لب یکدست‌تر می‌شود.",
        "why": "برای بازار شیدینگ و اصلاح رنگ لب گزینه قابل فروش است.",
        "color": (190, 96, 112),
        "alpha": 78,
        "do": ["یکدست‌سازی ملایم باشد", "رنگ طبیعی بماند", "تیرگی خیلی مصنوعی حذف نشود"],
        "avoid": ["روشن شدن غیرواقعی", "لب تخت و بی‌بافت", "تغییر پوست اطراف"],
    },
}


def _image_size(path: str) -> Tuple[int, int]:
    try:
        from PIL import Image
        with Image.open(path) as image:
            return int(image.width), int(image.height)
    except Exception:
        return 0, 0


def local_quality_report(path: str) -> Dict[str, Any]:
    w, h = _image_size(path)
    ok = bool(w >= 180 and h >= 180)
    return {
        "status": "local_checked",
        "ok": ok,
        "message": "عکس صورت/لب دریافت شد و برای طراحی لب آماده است." if ok else "عکس کوچک است؛ عکس واضح‌تری از صورت یا لب بفرست.",
        "checks": {"lips_visible": None, "lighting": None, "sharpness": None},
    }


def detect_regions(image_path: str, allow_fallback: bool = True) -> Dict[str, Any]:
    w, h = _image_size(image_path)
    if not w or not h:
        return {"ok": False, "method": "invalid_image", "regions": [], "mask": {"ok": False, "reason": "invalid_image"}}
    detection = {
        "ok": True,
        "method": "proportional_lip_guide",
        "confidence": 0.26,
        "detection_reliable": False,
        "is_fallback": True,
        "image_width": w,
        "image_height": h,
        "regions": [{"side": "mouth", "x": int(w * 0.36), "y": int(h * 0.60), "width": int(w * 0.28), "height": int(h * 0.075), "source": "proportional_lip_guide"}],
    }
    return ensure_mask(image_path, detection)


def ensure_mask(image_path: str, detection: Dict[str, Any]) -> Dict[str, Any]:
    try:
        from PIL import Image, ImageDraw, ImageFilter
        w = int(detection.get("image_width") or 0)
        h = int(detection.get("image_height") or 0)
        mask = Image.new("L", (w, h), 0)
        draw = ImageDraw.Draw(mask)
        x0 = int(w * 0.36)
        x1 = int(w * 0.64)
        y0 = int(h * 0.595)
        y1 = int(h * 0.675)
        draw.ellipse((x0, y0, x1, int((y0 + y1) / 2) + 3), fill=210)
        draw.ellipse((x0 + int(w * 0.015), int((y0 + y1) / 2) - 5, x1 - int(w * 0.015), y1), fill=255)
        # Soft center gap to avoid teeth if mouth is slightly open.
        draw.ellipse((int(w * 0.43), int(h * 0.625), int(w * 0.57), int(h * 0.652)), fill=60)
        mask = mask.filter(ImageFilter.GaussianBlur(radius=max(1, int(min(w, h) * 0.003))))
        mask_dir = os.path.join(os.path.dirname(os.path.abspath(image_path)), "masks")
        os.makedirs(mask_dir, exist_ok=True)
        mask_path = os.path.join(mask_dir, os.path.splitext(os.path.basename(image_path))[0] + "_lip_mask.png")
        mask.save(mask_path, "PNG", optimize=True)
        pixels = sum(1 for px in mask.getdata() if px > 8)
        detection["mask"] = {
            "ok": pixels > 0,
            "kind": "lip_guided_mask",
            "format": "png_luminance",
            "path": mask_path,
            "width": w,
            "height": h,
            "coverage_ratio": round(pixels / float(max(1, w * h)), 6),
            "pixel_count": pixels,
            "real_mask": False,
            "is_fallback": True,
            "polarity": "white_edit_black_keep",
        }
        detection["mask_path"] = mask_path
        return detection
    except Exception as exc:
        detection["mask"] = {"ok": False, "reason": "mask_failed", "error": str(exc)[:120]}
        return detection


def _source_path(candidate: Dict[str, Any]) -> str:
    filename = os.path.basename(str(candidate.get("photo_filename") or ""))
    if not filename:
        return ""
    root = os.path.abspath(UPLOAD_DIR)
    path = os.path.abspath(os.path.join(root, filename))
    return path if path.startswith(root + os.sep) and os.path.exists(path) else ""


def _mask_for_size(detection: Dict[str, Any], size):
    from PIL import Image
    mask_path = str((detection.get("mask") or {}).get("path") or detection.get("mask_path") or "")
    if mask_path and os.path.exists(mask_path):
        mask = Image.open(mask_path).convert("L")
    else:
        mask = Image.new("L", size, 0)
    resample = Image.Resampling.LANCZOS if hasattr(Image, "Resampling") else Image.LANCZOS
    return mask.resize(size, resample)


def generate_guided_design(candidate: Dict[str, Any]) -> Dict[str, Any]:
    src = _source_path(candidate)
    if not src:
        return {"ok": False, "status": "missing_photo", "message": "برای طراحی لب، عکس واقعی لازم است."}
    try:
        from PIL import Image, ImageDraw, ImageFilter
        base = Image.open(src).convert("RGB")
        base.thumbnail((1400, 1400))
        style_key = str(candidate.get("final_style") or DEFAULT_STYLE)
        style = STYLES.get(style_key, STYLES[DEFAULT_STYLE])
        detection = candidate.get("detection") if isinstance(candidate.get("detection"), dict) else detect_regions(src, allow_fallback=True)
        mask = _mask_for_size(detection, base.size).filter(ImageFilter.GaussianBlur(radius=0.7))
        color = tuple(style.get("color") or (190, 90, 110))
        alpha = int(style.get("alpha") or 84)
        tint = Image.new("RGB", base.size, color)
        colored = Image.blend(base, tint, min(0.45, alpha / 255.0))
        if style.get("contour"):
            overlay = Image.new("RGBA", base.size, (0, 0, 0, 0))
            draw = ImageDraw.Draw(overlay)
            w, h = base.size
            draw.arc((int(w * 0.36), int(h * 0.59), int(w * 0.64), int(h * 0.68)), 190, 350, fill=color + (130,), width=max(1, w // 260))
            colored = Image.alpha_composite(colored.convert("RGBA"), overlay).convert("RGB")
        composed = Image.composite(colored, base, mask).convert("RGB")
        os.makedirs(FINAL_DIR, exist_ok=True)
        filename = f"final/final_lip_{datetime.utcnow().strftime('%Y%m%d%H%M%S')}_{uuid.uuid4().hex[:10]}.png"
        out_path = os.path.join(UPLOAD_DIR, filename)
        composed.save(out_path, "PNG", optimize=True)
        return {
            "ok": True,
            "filename": filename,
            "provider": "python_guided_composite",
            "model": "pillow_lip_overlay_v1",
            "status": "non_ai_guided_preview_ready",
            "is_ai_generated": False,
            "ai_inpainting": False,
            "fallback_type": "non_ai_guided_fallback",
            "service_key": SERVICE_KEY,
            "detection": detection,
            "mask_used": bool((detection.get("mask") or {}).get("ok")),
            "mask_filename": os.path.relpath((detection.get("mask") or {}).get("path"), UPLOAD_DIR).replace(os.sep, "/") if (detection.get("mask") or {}).get("path") else "",
            "message": "طراحی راهنمای لب آماده شد؛ این نسخه AI واقعی نیست و فقط داخل محدوده لب اعمال شده است.",
        }
    except Exception as exc:
        return {"ok": False, "status": "generate_failed", "message": f"ساخت طراحی لب انجام نشد: {str(exc)[:120]}"}
