# -*- coding: utf-8 -*-
"""Guided final design for آینه رنگ و لایت مو گیسو."""
from __future__ import annotations

import os
import uuid
from datetime import datetime
from typing import Any, Dict, Tuple

from giso.config import Config
from giso.buti_ai.hair_color.prompts import HAIR_COLOR_PROMPTS

CHANGE_LEVEL_PROMPT = {
    "very_natural": "very subtle",
    "medium": "medium",
    "clear": "clear and more visible",
}

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


def _call_vision_json(image_path: str, prompt: str, max_tokens: int = 800) -> Dict[str, Any]:
    try:
        from giso.async_compat import run_async_safe
        from giso.ai_brain import ask_ai_vision
        from giso.analysis import _is_ai_refusal, _parse_ai_json
        from giso.buti_ai.ai_models import configured_vision_chain
        chain = configured_vision_chain()
        if not chain:
            return {"ok": False, "error": "no_vision_chain"}
        errors = []
        for item in chain:
            provider = item.get("provider_name") or ""
            model = item.get("model_name") or ""
            if not provider or not model:
                continue
            try:
                result = run_async_safe(ask_ai_vision(provider, image_path, prompt, model=model, max_tokens=max_tokens))
            except Exception as exc:
                result = {"ok": False, "error": f"{type(exc).__name__}: {exc}"}
            if result and result.get("ok"):
                text = result.get("text", "") or ""
                if _is_ai_refusal(text):
                    errors.append(f"{provider}/{model}: refused")
                    continue
                parsed = _parse_ai_json(text)
                if parsed is not None:
                    return {"ok": True, "provider": provider, "model": model, "data": parsed, "text": text}
                errors.append(f"{provider}/{model}: json")
            else:
                errors.append(f"{provider}/{model}: {(result or {}).get('error', 'error')}")
        return {"ok": False, "error": "; ".join(errors[-3:]) or "vision_failed"}
    except Exception as exc:
        return {"ok": False, "error": f"{type(exc).__name__}: {str(exc)[:120]}"}


def check_photo_quality(image_path: str) -> Dict[str, Any]:
    if not image_path:
        return {"status": "missing", "ok": False, "message": "عکسی برای بررسی دریافت نشد.", "checks": {}, "reasons": ["no_image"]}
    try:
        from giso.buti_ai.hair_color.prompts import PHOTO_QUALITY_PROMPT
        result = _call_vision_json(image_path, PHOTO_QUALITY_PROMPT, max_tokens=700)
        if result.get("ok"):
            data = result.get("data") or {}
            ok = bool(data.get("ok"))
            return {
                "status": "ai_checked",
                "ok": ok,
                "message": data.get("message") or ("عکس مو مناسب است." if ok else "این عکس برای رنگ مو مناسب نیست."),
                "checks": {
                    "hair_visible": data.get("hair_visible"),
                    "hair_coverage": data.get("hair_coverage"),
                    "lighting": data.get("lighting"),
                    "angle": data.get("angle"),
                    "sharpness": data.get("sharpness"),
                },
                "reasons": data.get("reasons") or [],
                "provider": result.get("provider"),
                "model": result.get("model"),
            }
    except Exception:
        pass
    return local_quality_report(image_path)


def analyze_hair_color_photo(image_path: str, selected_style_key: str, change_level_key: str) -> Dict[str, Any]:
    if not image_path:
        return {"status": "missing", "ok": False, "message": "برای تحلیل مو عکس لازم است.", "data": {}}
    try:
        from giso.buti_ai.hair_color.prompts import hair_color_analysis_prompt
        style_label = STYLES.get(str(selected_style_key or DEFAULT_STYLE), STYLES[DEFAULT_STYLE]).get("label") or selected_style_key
        change_label = str(change_level_key or "medium")
        prompt = hair_color_analysis_prompt(style_label, change_label)
        result = _call_vision_json(image_path, prompt, max_tokens=900)
        if not result.get("ok"):
            return {"status": "ai_unavailable", "ok": None, "message": "تحلیل هوشمند مو فعلاً در دسترس نیست.", "data": {}, "error": result.get("error")}
        data = result.get("data") or {}
        return {"status": "ai_analyzed", "ok": True, "message": "تحلیل مو انجام شد.", "data": data, "provider": result.get("provider"), "model": result.get("model")}
    except Exception as exc:
        return {"status": "ai_unavailable", "ok": None, "message": "تحلیل هوشمند در دسترس نیست.", "data": {}, "error": str(exc)[:120]}


def local_quality_report(path: str) -> Dict[str, Any]:
    w, h = _image_size(path)
    ok = bool(w >= 220 and h >= 220)
    return {
        "status": "local_checked",
        "ok": ok,
        "message": "عکس مو دریافت شد و برای طراحی رنگ/لایت آماده است." if ok else "عکس کوچک است؛ عکس واضح‌تری از مو بفرست.",
        "checks": {"hair_visible": None, "lighting": None, "sharpness": None},
    }


def _fallback_hair_detection(w: int, h: int) -> Dict[str, Any]:
    return {
        "ok": True,
        "method": "proportional_hair_guide",
        "confidence": 0.24,
        "detection_reliable": False,
        "is_fallback": True,
        "image_width": w,
        "image_height": h,
        "regions": [{"side": "hair", "x": int(w * 0.18), "y": int(h * 0.05), "width": int(w * 0.64), "height": int(h * 0.48), "source": "proportional_hair_guide"}],
    }


def _detect_face_anchor(image):
    """Return a conservative face box in original-image coordinates, or None.

    Hair-color pixels are not enough to distinguish dark clothes from hair. An
    optional OpenCV Haar face anchor narrows the edit search to hair near a
    detected head; failure to find one is handled as an unverified mask, not a
    reason to label an arbitrary dark region as hair.
    """
    try:
        import cv2
        import numpy as np

        rgb = np.asarray(image.convert("RGB"))
        h, w = rgb.shape[:2]
        scale = min(1.0, 640.0 / float(max(w, h)))
        small = rgb if scale >= 1.0 else cv2.resize(
            rgb, (max(1, int(w * scale)), max(1, int(h * scale))), interpolation=cv2.INTER_AREA
        )
        sh, sw = small.shape[:2]
        gray = cv2.cvtColor(small, cv2.COLOR_RGB2GRAY)
        candidates = []
        cascade_names = (
            "haarcascade_frontalface_alt2.xml",
            "haarcascade_frontalface_default.xml",
        )
        for cascade_name in cascade_names:
            cascade = cv2.CascadeClassifier(os.path.join(cv2.data.haarcascades, cascade_name))
            if cascade.empty():
                continue
            boxes = cascade.detectMultiScale(
                gray,
                scaleFactor=1.1,
                minNeighbors=4,
                minSize=(max(24, int(sw * 0.07)), max(24, int(sh * 0.07))),
            )
            for raw_x, raw_y, raw_w, raw_h in boxes:
                x, y, fw, fh = map(int, (raw_x, raw_y, raw_w, raw_h))
                aspect = fw / float(max(1, fh))
                if not (0 <= x < sw and 0 <= y < sh):
                    continue
                if not (0.5 <= aspect <= 1.65):
                    continue
                # Lower-frame clothing/hand false positives are not a head anchor.
                if y > sh * 0.48 or x + fw > sw or y + fh > sh * 0.92:
                    continue
                sx = w / float(max(1, sw))
                sy = h / float(max(1, sh))
                box = (int(x * sx), int(y * sy), max(1, int(fw * sx)), max(1, int(fh * sy)))
                cx = (box[0] + box[2] / 2.0) / float(max(1, w))
                y_norm = box[1] / float(max(1, h))
                center_score = max(0.55, 1.0 - abs(cx - 0.5) * 0.8)
                upper_score = max(0.60, 1.0 - max(0.0, y_norm - 0.30) * 0.8)
                candidates.append((box[2] * box[3] * center_score * upper_score, box))
        return max(candidates, key=lambda item: item[0])[1] if candidates else None
    except Exception:
        return None


def _try_detect_hair_by_color(image_path: str) -> Dict[str, Any]:
    """Conservative hair-color ROI for portraits.

    Dark/brown color candidates are constrained around a detected face when one
    is available. Blonde, cropped, or ambiguous photos use the explicitly
    non-AI guided fallback rather than claiming an unverified hair mask.
    """
    from PIL import Image, ImageFilter
    image = Image.open(image_path).convert("RGB")
    w, h = image.size
    px = image.load()
    mask = Image.new("L", (w, h), 0)
    face_anchor = _detect_face_anchor(image)
    if not face_anchor:
        # Without a frontal face anchor, dark hair cannot be safely separated
        # from salon clothing, hands, or another person's hair.
        raise ValueError("hair_face_anchor_not_detected")
    fx, fy, fw, fh = face_anchor
    roi = (
        max(0, int(fx - fw * 1.35)),
        max(0, int(fy - fh * 1.15)),
        min(w, int(fx + fw * 2.35)),
        min(h, int(fy + fh * 2.25)),
    )
    face = (
        max(0, int(fx - fw * 0.12)),
        max(0, int(fy - fh * 0.08)),
        min(w, int(fx + fw * 1.12)),
        min(h, int(fy + fh * 1.12)),
    )
    protect_face_ellipse = True
    face_cx = (face[0] + face[2]) / 2.0
    face_cy = (face[1] + face[3]) / 2.0
    face_rx = max(1.0, (face[2] - face[0]) / 2.0)
    face_ry = max(1.0, (face[3] - face[1]) / 2.0)
    for y in range(roi[1], roi[3]):
        for x in range(roi[0], roi[2]):
            if protect_face_ellipse and ((x - face_cx) / face_rx) ** 2 + ((y - face_cy) / face_ry) ** 2 <= 1.0:
                continue
            r, g, b = px[x, y]
            brightness = (r + g + b) / 3.0
            sat = max(r, g, b) - min(r, g, b)
            brown_dark = brightness < 118 and sat >= 8
            warm_hair = r > g > b and brightness < 155 and sat >= 22
            if brown_dark or warm_hair:
                mask.putpixel((x, y), 255)
    mask = mask.filter(ImageFilter.MedianFilter(size=5)).filter(ImageFilter.MaxFilter(size=7)).filter(ImageFilter.MinFilter(size=5))
    # Keep cohesive hair components close to the subject, not blurred side/background
    # patches. This prevents face-frame from painting vertical bars on the scene.
    raw_px = mask.load()
    visited = [[False] * w for _ in range(h)]
    components = []
    for yy in range(roi[1], roi[3]):
        for xx in range(roi[0], roi[2]):
            if visited[yy][xx] or raw_px[xx, yy] <= 0:
                continue
            stack = [(xx, yy)]
            visited[yy][xx] = True
            xs_comp, ys_comp = [], []
            while stack:
                cx, cy = stack.pop()
                xs_comp.append(cx); ys_comp.append(cy)
                for nx, ny in ((cx - 1, cy), (cx + 1, cy), (cx, cy - 1), (cx, cy + 1)):
                    if nx < roi[0] or nx >= roi[2] or ny < roi[1] or ny >= roi[3] or visited[ny][nx]:
                        continue
                    visited[ny][nx] = True
                    if raw_px[nx, ny] > 0:
                        stack.append((nx, ny))
            area = len(xs_comp)
            if area < max(20, int(w * h * 0.00035)):
                continue
            x0c, x1c, y0c, y1c = min(xs_comp), max(xs_comp), min(ys_comp), max(ys_comp)
            cx_norm = ((x0c + x1c) / 2.0) / float(max(1, w))
            edge_penalty = 0.45 if (x0c <= roi[0] + 2 or x1c >= roi[2] - 2) else 1.0
            center_score = max(0.15, 1.0 - abs(cx_norm - 0.5) * 1.45)
            score = area * center_score * edge_penalty
            components.append({"area": area, "score": score, "bbox": (x0c, y0c, x1c, y1c), "points": list(zip(xs_comp, ys_comp))})
    if components:
        components.sort(key=lambda item: item["score"], reverse=True)
        best_score = float(components[0]["score"] or 1)
        kept = [c for c in components if c["score"] >= best_score * 0.34][:3]
        component_mask = Image.new("L", (w, h), 0)
        for comp in kept:
            for xx, yy in comp["points"]:
                component_mask.putpixel((xx, yy), 255)
        mask = component_mask.filter(ImageFilter.MaxFilter(size=5)).filter(ImageFilter.MinFilter(size=3))
    pixels_xy = [(x, y) for y in range(roi[1], roi[3]) for x in range(roi[0], roi[2]) if mask.getpixel((x, y)) > 0]
    if not pixels_xy:
        raise ValueError("hair_pixels_empty")
    xs = [p[0] for p in pixels_xy]
    ys = [p[1] for p in pixels_xy]
    x0, x1 = max(0, min(xs) - int(w * 0.02)), min(w - 1, max(xs) + int(w * 0.02))
    y0, y1 = max(0, min(ys) - int(h * 0.02)), min(h - 1, max(ys) + int(h * 0.02))
    coverage = len(pixels_xy) / float(max(1, w * h))
    if not (0.025 <= coverage <= 0.42 and (x1 - x0) >= w * 0.20 and (y1 - y0) >= h * 0.16 and y0 <= h * 0.22):
        raise ValueError("hair_geometry_not_plausible")
    mask = mask.filter(ImageFilter.GaussianBlur(radius=max(1, int(min(w, h) * 0.003))))
    return {
        "ok": True,
        "method": "color_hair_segmentation_v1",
        "confidence": 0.68,
        # Colour-only hair mask spills onto neck/clothes on real photos; not trusted.
        "detection_reliable": False,
        "untrusted_reason": "color_hair_segmentation_v1: spills onto neck/clothes on real photos",
        "is_fallback": False,
        "image_width": w,
        "image_height": h,
        "regions": [{"side": "hair", "x": x0, "y": y0, "width": x1 - x0 + 1, "height": y1 - y0 + 1, "source": "color_hair_segmentation_v1", "confidence": 0.68}],
        "face_anchor_detected": bool(face_anchor),
        "face_protection_applied": bool(protect_face_ellipse),
        "_mask_image": mask,
    }


def _try_detect_hair_by_segmentation(image_path: str) -> Dict[str, Any]:
    """Model-based hair mask, trusted only when the segmentation gate passes.

    Raises HairSegmentationError (with a reason code) when the image or mask
    does not pass validation; the caller then falls back to the untrusted path.
    """
    from PIL import Image
    from giso.buti_ai.hair_color import segmentation

    image = Image.open(image_path).convert("RGB")
    w, h = image.size
    face_box = _detect_face_anchor(image)
    result = segmentation.segment_hair(image, face_box)
    bx, by, bw, bh = result["stats"]["bbox"]
    return {
        "ok": True,
        "method": "segmentation_hair_v1",
        "confidence": 0.8,
        "detection_reliable": True,
        "untrusted_reason": "",
        "is_fallback": False,
        "image_width": w,
        "image_height": h,
        "face_anchor_detected": True,
        "face_protection_applied": True,
        "segmentation_stats": result["stats"],
        "regions": [{"side": "hair", "x": bx, "y": by, "width": bw, "height": bh,
                     "source": "segmentation_hair_v1", "confidence": 0.8}],
        "_mask_image": result["mask"],
    }


def detect_regions(image_path: str, allow_fallback: bool = True) -> Dict[str, Any]:
    w, h = _image_size(image_path)
    if not w or not h:
        return {"ok": False, "method": "invalid_image", "regions": [], "mask": {"ok": False, "reason": "invalid_image"}}
    seg_reason = ""
    try:
        return ensure_mask(image_path, _try_detect_hair_by_segmentation(image_path))
    except Exception as seg_exc:
        seg_reason = getattr(seg_exc, "reason", "") or type(seg_exc).__name__
    try:
        detection = ensure_mask(image_path, _try_detect_hair_by_color(image_path))
        detection["segmentation_rejected"] = seg_reason
        return detection
    except Exception:
        if not allow_fallback:
            return {"ok": False, "method": "hair_not_detected", "regions": [], "mask": {"ok": False, "reason": "hair_not_detected"}}
    detection = ensure_mask(image_path, _fallback_hair_detection(w, h))
    detection["segmentation_rejected"] = seg_reason
    return detection


def ensure_mask(image_path: str, detection: Dict[str, Any]) -> Dict[str, Any]:
    try:
        from PIL import Image, ImageDraw, ImageFilter
        w = int(detection.get("image_width") or 0)
        h = int(detection.get("image_height") or 0)
        supplied = detection.pop("_mask_image", None)
        if supplied is not None:
            mask = supplied.convert("L")
        else:
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
        is_fallback = bool(detection.get("is_fallback")) or str(detection.get("method") or "").startswith("proportional")
        detection["mask"] = {
            "ok": pixels > 0,
            "kind": "hair_color_mask" if not is_fallback else "hair_guided_mask",
            "format": "png_luminance",
            "path": mask_path,
            "width": w,
            "height": h,
            "coverage_ratio": round(pixels / float(max(1, w * h)), 6),
            "pixel_count": pixels,
            "real_mask": not is_fallback,
            "is_fallback": is_fallback,
            "polarity": "white_edit_black_keep",
        }
        detection["mask_path"] = mask_path
        return detection
    except Exception as exc:
        detection["mask"] = {"ok": False, "reason": "mask_failed", "error": str(exc)[:120]}
        return detection


def refine_detection_for_style(image_path: str, detection: Dict[str, Any], style_key: str = "") -> Dict[str, Any]:
    """Return a style-specific edit mask for provider-backed generation.

    Face-frame/مانی‌پیس must not recolor the whole hair mass; it only gets two
    narrow side lock masks. Other styles keep the service hair mask.
    """
    style = STYLES.get(str(style_key or DEFAULT_STYLE), STYLES[DEFAULT_STYLE])
    if style.get("mode") != "face_frame":
        return detection
    # Idempotent: the same detection can reach this twice (generator + guided fallback).
    # A second pass would shrink the already-narrow side strips to almost nothing.
    if detection.get("style_mask") == "face_frame":
        return detection
    try:
        from PIL import Image, ImageDraw, ImageChops, ImageFilter
        detection = dict(detection or {})
        mask_info = dict(detection.get("mask") or {})
        src_mask = str(mask_info.get("path") or detection.get("mask_path") or "")
        if not src_mask or not os.path.exists(src_mask):
            return detection
        mask = Image.open(src_mask).convert("L")
        w, h = mask.size
        frame_mask = Image.new("L", (w, h), 0)
        draw = ImageDraw.Draw(frame_mask)
        regions = detection.get("regions") if isinstance(detection.get("regions"), list) else []
        if regions:
            r = regions[0]
            x = int(r.get("x") or w * 0.18)
            y = int(r.get("y") or h * 0.05)
            rw = int(r.get("width") or w * 0.64)
            rh = int(r.get("height") or h * 0.55)
        else:
            x, y, rw, rh = int(w * 0.18), int(h * 0.05), int(w * 0.64), int(h * 0.55)
        strip_w = max(8, int(rw * 0.11))
        for bx in (x + int(rw * 0.22), x + int(rw * 0.67)):
            draw.rounded_rectangle(
                (bx, y + int(rh * 0.05), bx + strip_w, y + int(rh * 0.96)),
                radius=max(8, strip_w // 2),
                fill=255,
            )
        frame_mask = frame_mask.filter(ImageFilter.GaussianBlur(radius=max(1, int(min(w, h) * 0.004))))
        refined = ImageChops.multiply(mask, frame_mask).point(lambda px: 255 if int(px) > 12 else 0)
        pixels = sum(1 for px in refined.getdata() if px > 0)
        if pixels <= 0:
            return detection
        mask_dir = os.path.join(os.path.dirname(os.path.abspath(image_path)), "masks")
        os.makedirs(mask_dir, exist_ok=True)
        mask_path = os.path.join(mask_dir, os.path.splitext(os.path.basename(image_path))[0] + "_hair_face_frame_mask.png")
        refined.save(mask_path, "PNG", optimize=True)
        mask_info.update({
            "path": mask_path,
            "kind": "hair_face_frame_mask",
            "coverage_ratio": round(pixels / float(max(1, w * h)), 6),
            "pixel_count": pixels,
            "width": w,
            "height": h,
        })
        detection["mask"] = mask_info
        detection["mask_path"] = mask_path
        detection["style_mask"] = "face_frame"
        detection["regions"] = [{
            "side": "face_frame",
            "x": x + int(rw * 0.22),
            "y": y + int(rh * 0.05),
            "width": int(rw * 0.56),
            "height": int(rh * 0.91),
            "source": "style_refined_face_frame_mask",
            "confidence": detection.get("confidence") or 0.62,
        }]
        return detection
    except Exception:
        return detection


def _source_path(candidate: Dict[str, Any]) -> str:
    filename = os.path.basename(str(candidate.get("photo_filename") or ""))
    if not filename:
        return ""
    root = os.path.abspath(UPLOAD_DIR)
    path = os.path.abspath(os.path.join(root, filename))
    return path if path.startswith(root + os.sep) and os.path.exists(path) else ""


def _mask_for_size(detection: Dict[str, Any], size):
    from PIL import Image, ImageChops, ImageFilter
    mask_path = str((detection.get("mask") or {}).get("path") or detection.get("mask_path") or "")
    if mask_path and os.path.exists(mask_path):
        mask = Image.open(mask_path).convert("L")
    else:
        mask = Image.new("L", size, 0)
    resample = Image.Resampling.LANCZOS if hasattr(Image, "Resampling") else Image.LANCZOS
    resized = mask.resize(size, resample)
    editable = resized.point(lambda px: 255 if int(px) > 0 else 0)
    softened = resized.filter(ImageFilter.GaussianBlur(radius=1.2))
    return ImageChops.multiply(softened, editable)


def build_design_prompt(candidate: Dict[str, Any]) -> str:
    """CLIP-budgeted prompt (SD 1.5 reads only ~77 tokens).

    The selected model's English instruction comes first, then the mask polarity
    and change level, so the user's choices survive truncation. The Persian
    labels and long do/avoid lists are intentionally not sent to the model.
    """
    style_key = str((candidate or {}).get("final_style") or DEFAULT_STYLE)
    base = HAIR_COLOR_PROMPTS.get(style_key) or HAIR_COLOR_PROMPTS[DEFAULT_STYLE]
    change = CHANGE_LEVEL_PROMPT.get(str((candidate or {}).get("change_key") or ""), CHANGE_LEVEL_PROMPT["medium"])
    return f"{base} Edit only inside the white mask; black pixels stay unchanged. Change level: {change}."


def generate_guided_design(candidate: Dict[str, Any]) -> Dict[str, Any]:
    src = _source_path(candidate)
    if not src:
        return {"ok": False, "status": "missing_photo", "message": "برای طراحی رنگ مو، عکس واقعی لازم است."}
    try:
        from PIL import Image, ImageDraw, ImageEnhance, ImageChops, ImageFilter
        base = Image.open(src).convert("RGB")
        base.thumbnail((1400, 1400))
        style_key = str(candidate.get("final_style") or DEFAULT_STYLE)
        style = STYLES.get(style_key, STYLES[DEFAULT_STYLE])
        detection = candidate.get("detection") if isinstance(candidate.get("detection"), dict) else detect_regions(src, allow_fallback=True)
        detection = refine_detection_for_style(src, detection, style_key)
        mask = _mask_for_size(detection, base.size)
        color = tuple(style.get("color") or (120, 80, 48))
        mode = style.get("mode")
        blend_alpha = 0.32 if mode == "full_tone" else (0.24 if mode in {"strands", "balayage"} else 0.42)
        tint = Image.new("RGB", base.size, color)
        # Preserve texture by blending color layer with original contrast.
        colored = Image.blend(base, tint, blend_alpha)
        colored = ImageEnhance.Contrast(colored).enhance(1.05)
        overlay = Image.new("RGBA", base.size, (0, 0, 0, 0))
        draw = ImageDraw.Draw(overlay)
        effect_mask = mask
        w, h = base.size
        if mode in {"strands", "balayage", "face_frame"}:
            line_color = color + (155,)
            if mode == "face_frame":
                # Only side/front strands should change. On back-view photos this
                # prevents the selected face-frame model from becoming a full wig.
                frame_mask = Image.new("L", base.size, 0)
                frame_draw = ImageDraw.Draw(frame_mask)
                regions = detection.get("regions") if isinstance(detection.get("regions"), list) else []
                if regions:
                    r = regions[0]
                    sx = w / float(max(1, detection.get("image_width") or w))
                    sy = h / float(max(1, detection.get("image_height") or h))
                    x = int(float(r.get("x") or w * 0.2) * sx)
                    y = int(float(r.get("y") or h * 0.05) * sy)
                    rw = int(float(r.get("width") or w * 0.6) * sx)
                    rh = int(float(r.get("height") or h * 0.5) * sy)
                else:
                    x, y, rw, rh = int(w * 0.18), int(h * 0.05), int(w * 0.64), int(h * 0.55)
                strip_w = max(8, int(rw * 0.16))
                for bx in (x + int(rw * 0.06), x + int(rw * 0.78)):
                    frame_draw.rounded_rectangle((bx, y + int(rh * 0.08), bx + strip_w, y + rh), radius=max(8, strip_w // 2), fill=235)
                    draw.line((bx + strip_w // 2, y + int(rh * 0.05), bx + strip_w // 3, y + int(rh * 0.94)), fill=line_color, width=max(4, strip_w // 3))
                effect_mask = ImageChops.multiply(mask, frame_mask.filter(ImageFilter.GaussianBlur(radius=2.0)))
            else:
                for idx, x in enumerate(range(int(w * 0.25), int(w * 0.78), max(18, w // 14))):
                    y0 = int(h * (0.18 + (idx % 3) * 0.03))
                    y1 = int(h * (0.56 + (idx % 2) * 0.05))
                    if mode == "balayage":
                        y0 = int(h * 0.32)
                    draw.line((x, y0, x + int(w * 0.04), y1), fill=line_color, width=max(3, w // 82))
            colored = Image.alpha_composite(colored.convert("RGBA"), overlay).convert("RGB")
        composed = Image.composite(colored, base, effect_mask).convert("RGB")
        os.makedirs(FINAL_DIR, exist_ok=True)
        from giso.buti_ai.image_validation import save_lossless_webp, validate_masked_output
        filename = f"final/final_hair_color_{datetime.utcnow().strftime('%Y%m%d%H%M%S')}_{uuid.uuid4().hex[:10]}.webp"
        out_path = os.path.join(UPLOAD_DIR, filename)
        save_lossless_webp(composed, out_path)
        try:
            validation = validate_masked_output(src, out_path, (detection.get("mask") or {}).get("path") or "", service_key=SERVICE_KEY)
        except Exception:
            validation = {}
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
            "validation": validation,
            "visible_in_mask_change": bool(validation.get("visible_in_mask_change")) if isinstance(validation, dict) else False,
            "outside_preserved": bool(validation.get("outside_preserved")) if isinstance(validation, dict) else False,
            "message": "طراحی راهنمای رنگ مو آماده شد؛ این نسخه AI واقعی نیست و فقط برای تصمیم‌گیری اولیه است.",
        }
    except Exception as exc:
        return {"ok": False, "status": "generate_failed", "message": f"ساخت طراحی رنگ مو انجام نشد: {str(exc)[:120]}"}
