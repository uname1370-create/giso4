# -*- coding: utf-8 -*-
"""Guided final design for آینه رنگ و لایت مو گیسو."""
from __future__ import annotations

import os
import uuid
from datetime import datetime
from typing import Any, Dict, Tuple

from giso.config import Config

SERVICE_KEY = "hair_color"
UPLOAD_DIR = os.path.join(Config.GISO_DIR, "data", "uploads", "buti_ai", SERVICE_KEY)
FINAL_DIR = os.path.join(UPLOAD_DIR, "final")

DEFAULT_STYLE = "chocolate_nescafe"
STYLES: Dict[str, Dict[str, Any]] = {
    "chocolate_nescafe": {
        "label": "قهوه‌ای شکلاتی / نسکافه‌ای",
        "icon": "🍫",
        "summary": "تناژ گرم، طبیعی و کم‌ریسک برای تغییر رنگ مو.",
        "why": "برای شروع امن و قابل اجرا در سالن‌های رنگ مو مناسب است.",
        "color": (96, 58, 38),
        "mode": "full_tone",
        "do": ["تناژ طبیعی حفظ شود", "بافت مو دیده شود", "صورت تغییر نکند"],
        "avoid": ["رنگ تخت و مصنوعی", "تغییر پوست", "دکلره شدید"],
    },
    "caramel_balayage": {
        "label": "بالیاژ کاراملی",
        "icon": "✨",
        "summary": "لایت‌های گرم کاراملی روی ساقه و نوک مو.",
        "why": "برای بازار رنگ و لایت، خروجی جذاب و قابل فروش دارد.",
        "color": (190, 126, 64),
        "mode": "balayage",
        "do": ["ریشه طبیعی بماند", "گذار رنگ نرم باشد", "نوک مو روشن‌تر شود"],
        "avoid": ["بلوند کامل", "خط‌های تیز", "تغییر چهره"],
    },
    "natural_highlight": {
        "label": "هایلایت طبیعی",
        "icon": "🌤️",
        "summary": "رگه‌های روشن ظریف بدون تغییر سنگین کل مو.",
        "why": "برای کاربر مردد، تغییر قابل مشاهده اما امن ایجاد می‌کند.",
        "color": (176, 135, 82),
        "mode": "strands",
        "do": ["رگه‌ها باریک باشند", "رنگ پایه حفظ شود", "جهت تار مو رعایت شود"],
        "avoid": ["راه‌راه مصنوعی", "پوشاندن صورت", "تغییر مدل مو"],
    },
    "face_frame": {
        "label": "فیس‌فریم / مانی‌پیس",
        "icon": "🖼️",
        "summary": "روشن‌تر شدن دسته‌های جلوی صورت بدون تغییر کل مو.",
        "why": "برای قبل/بعد واضح و فروش‌پذیر، ولی کنترل‌شده مناسب است.",
        "color": (214, 164, 86),
        "mode": "face_frame",
        "do": ["فقط دسته‌های جلویی روشن شوند", "چهره پوشانده نشود", "رنگ با پایه مو blend شود"],
        "avoid": ["روشن کردن کل مو", "تغییر صورت", "رگه‌های ضخیم"],
    },
    "ash_olive": {
        "label": "دودی زیتونی ملایم",
        "icon": "🫒",
        "summary": "تناژ سرد و شیک بدون سبزی یا خاکستری غیرواقعی.",
        "why": "برای کاربرانی که تغییر شیک اما ملایم می‌خواهند مناسب است.",
        "color": (92, 94, 76),
        "mode": "full_tone",
        "do": ["تناژ سرد ملایم باشد", "عمق و سایه مو حفظ شود", "چهره دست‌نخورده بماند"],
        "avoid": ["سبز شدن شدید", "خاکستری مصنوعی", "تغییر نور عکس"],
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
    ok = bool(w >= 220 and h >= 220)
    return {
        "status": "local_checked",
        "ok": ok,
        "message": "عکس مو دریافت شد و برای طراحی رنگ/لایت آماده است." if ok else "عکس کوچک است؛ عکس واضح‌تری از مو بفرست.",
        "checks": {"hair_visible": None, "lighting": None, "sharpness": None},
    }


def detect_regions(image_path: str, allow_fallback: bool = True) -> Dict[str, Any]:
    w, h = _image_size(image_path)
    if not w or not h:
        return {"ok": False, "method": "invalid_image", "regions": [], "mask": {"ok": False, "reason": "invalid_image"}}
    detection = {
        "ok": True,
        "method": "proportional_hair_guide",
        "confidence": 0.24,
        "detection_reliable": False,
        "is_fallback": True,
        "image_width": w,
        "image_height": h,
        "regions": [{"side": "hair", "x": int(w * 0.18), "y": int(h * 0.05), "width": int(w * 0.64), "height": int(h * 0.48), "source": "proportional_hair_guide"}],
    }
    return ensure_mask(image_path, detection)


def ensure_mask(image_path: str, detection: Dict[str, Any]) -> Dict[str, Any]:
    try:
        from PIL import Image, ImageDraw, ImageFilter
        w = int(detection.get("image_width") or 0)
        h = int(detection.get("image_height") or 0)
        mask = Image.new("L", (w, h), 0)
        draw = ImageDraw.Draw(mask)
        # A conservative upper-head hair ellipse; non-AI fallback only.
        draw.ellipse((int(w * 0.15), int(h * 0.02), int(w * 0.85), int(h * 0.58)), fill=255)
        # remove central face area to avoid coloring skin in the guided fallback.
        draw.ellipse((int(w * 0.30), int(h * 0.23), int(w * 0.70), int(h * 0.77)), fill=0)
        mask = mask.filter(ImageFilter.GaussianBlur(radius=max(2, int(min(w, h) * 0.006))))
        mask_dir = os.path.join(os.path.dirname(os.path.abspath(image_path)), "masks")
        os.makedirs(mask_dir, exist_ok=True)
        mask_path = os.path.join(mask_dir, os.path.splitext(os.path.basename(image_path))[0] + "_hair_mask.png")
        mask.save(mask_path, "PNG", optimize=True)
        pixels = sum(1 for px in mask.getdata() if px > 8)
        detection["mask"] = {
            "ok": pixels > 0,
            "kind": "hair_guided_mask",
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
    from PIL import Image, ImageFilter
    mask_path = str((detection.get("mask") or {}).get("path") or detection.get("mask_path") or "")
    if mask_path and os.path.exists(mask_path):
        mask = Image.open(mask_path).convert("L")
    else:
        mask = Image.new("L", size, 0)
    resample = Image.Resampling.LANCZOS if hasattr(Image, "Resampling") else Image.LANCZOS
    return mask.resize(size, resample).filter(ImageFilter.GaussianBlur(radius=1.2))


def generate_guided_design(candidate: Dict[str, Any]) -> Dict[str, Any]:
    src = _source_path(candidate)
    if not src:
        return {"ok": False, "status": "missing_photo", "message": "برای طراحی رنگ مو، عکس واقعی لازم است."}
    try:
        from PIL import Image, ImageDraw, ImageEnhance
        base = Image.open(src).convert("RGB")
        base.thumbnail((1400, 1400))
        style_key = str(candidate.get("final_style") or DEFAULT_STYLE)
        style = STYLES.get(style_key, STYLES[DEFAULT_STYLE])
        detection = candidate.get("detection") if isinstance(candidate.get("detection"), dict) else detect_regions(src, allow_fallback=True)
        mask = _mask_for_size(detection, base.size)
        color = tuple(style.get("color") or (120, 80, 48))
        tint = Image.new("RGB", base.size, color)
        # Preserve texture by blending color layer with original contrast.
        colored = Image.blend(base, tint, 0.34)
        colored = ImageEnhance.Contrast(colored).enhance(1.04)
        overlay = Image.new("RGBA", base.size, (0, 0, 0, 0))
        draw = ImageDraw.Draw(overlay)
        mode = style.get("mode")
        if mode in {"strands", "balayage", "face_frame"}:
            w, h = base.size
            line_color = color + (145,)
            if mode == "face_frame":
                xs = [int(w * 0.34), int(w * 0.66)]
                for x in xs:
                    draw.line((x, int(h * 0.10), x + (16 if x < w / 2 else -16), int(h * 0.58)), fill=line_color, width=max(5, w // 42))
            else:
                for idx, x in enumerate(range(int(w * 0.25), int(w * 0.78), max(18, w // 14))):
                    y0 = int(h * (0.18 + (idx % 3) * 0.03))
                    y1 = int(h * (0.52 + (idx % 2) * 0.04))
                    if mode == "balayage":
                        y0 = int(h * 0.30)
                    draw.line((x, y0, x + int(w * 0.04), y1), fill=line_color, width=max(3, w // 75))
            colored = Image.alpha_composite(colored.convert("RGBA"), overlay).convert("RGB")
        composed = Image.composite(colored, base, mask).convert("RGB")
        os.makedirs(FINAL_DIR, exist_ok=True)
        filename = f"final/final_hair_color_{datetime.utcnow().strftime('%Y%m%d%H%M%S')}_{uuid.uuid4().hex[:10]}.png"
        out_path = os.path.join(UPLOAD_DIR, filename)
        composed.save(out_path, "PNG", optimize=True)
        return {
            "ok": True,
            "filename": filename,
            "provider": "python_guided_composite",
            "model": "pillow_hair_color_overlay_v1",
            "status": "non_ai_guided_preview_ready",
            "is_ai_generated": False,
            "ai_inpainting": False,
            "fallback_type": "non_ai_guided_fallback",
            "service_key": SERVICE_KEY,
            "detection": detection,
            "mask_used": bool((detection.get("mask") or {}).get("ok")),
            "mask_filename": os.path.relpath((detection.get("mask") or {}).get("path"), UPLOAD_DIR).replace(os.sep, "/") if (detection.get("mask") or {}).get("path") else "",
            "message": "طراحی راهنمای رنگ مو آماده شد؛ این نسخه AI واقعی نیست و فقط برای تصمیم‌گیری اولیه است.",
        }
    except Exception as exc:
        return {"ok": False, "status": "generate_failed", "message": f"ساخت طراحی رنگ مو انجام نشد: {str(exc)[:120]}"}
