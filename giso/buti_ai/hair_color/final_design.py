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


def _try_detect_hair_by_color(image_path: str) -> Dict[str, Any]:
    """Conservative hair-color ROI for portraits.

    The mask looks for cohesive dark/brown hair pixels around the upper head and
    explicitly removes the face ellipse. Blonde/ambiguous photos fall back to the
    non-AI guide rather than claiming real AI readiness.
    """
    from PIL import Image, ImageDraw, ImageFilter
    image = Image.open(image_path).convert("RGB")
    w, h = image.size
    px = image.load()
    mask = Image.new("L", (w, h), 0)
    roi = (int(w * 0.12), int(h * 0.02), int(w * 0.88), int(h * 0.76))
    face = (int(w * 0.31), int(h * 0.18), int(w * 0.69), int(h * 0.77))
    face_cx = (face[0] + face[2]) / 2.0
    face_cy = (face[1] + face[3]) / 2.0
    face_rx = max(1.0, (face[2] - face[0]) / 2.0)
    face_ry = max(1.0, (face[3] - face[1]) / 2.0)
    skin_like = 0
    sampled = 0
    step = max(3, min(w, h) // 90)
    for yy in range(face[1], face[3], step):
        for xx in range(face[0], face[2], step):
            if xx < 0 or yy < 0 or xx >= w or yy >= h:
                continue
            rr, gg, bb = px[xx, yy]
            sampled += 1
            if rr > 95 and gg > 55 and bb > 35 and rr > bb and (max(rr, gg, bb) - min(rr, gg, bb)) > 14:
                skin_like += 1
    protect_face_ellipse = sampled > 0 and (skin_like / float(sampled)) >= 0.18
    for y in range(roi[1], roi[3]):
        for x in range(roi[0], roi[2]):
            # protect central face/neck area only when a skin-like face is visible;
            # back-view hair photos should keep the central hair mass editable.
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
        "detection_reliable": True,
        "is_fallback": False,
        "image_width": w,
        "image_height": h,
        "regions": [{"side": "hair", "x": x0, "y": y0, "width": x1 - x0 + 1, "height": y1 - y0 + 1, "source": "color_hair_segmentation_v1", "confidence": 0.68}],
        "face_protection_applied": bool(protect_face_ellipse),
        "_mask_image": mask,
    }


def detect_regions(image_path: str, allow_fallback: bool = True) -> Dict[str, Any]:
    w, h = _image_size(image_path)
    if not w or not h:
        return {"ok": False, "method": "invalid_image", "regions": [], "mask": {"ok": False, "reason": "invalid_image"}}
    try:
        return ensure_mask(image_path, _try_detect_hair_by_color(image_path))
    except Exception:
        if not allow_fallback:
            return {"ok": False, "method": "hair_not_detected", "regions": [], "mask": {"ok": False, "reason": "hair_not_detected"}}
    return ensure_mask(image_path, _fallback_hair_detection(w, h))


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
    from PIL import Image, ImageFilter
    mask_path = str((detection.get("mask") or {}).get("path") or detection.get("mask_path") or "")
    if mask_path and os.path.exists(mask_path):
        mask = Image.open(mask_path).convert("L")
    else:
        mask = Image.new("L", size, 0)
    resample = Image.Resampling.LANCZOS if hasattr(Image, "Resampling") else Image.LANCZOS
    return mask.resize(size, resample).filter(ImageFilter.GaussianBlur(radius=1.2))


def build_design_prompt(candidate: Dict[str, Any]) -> str:
    style_key = str((candidate or {}).get("final_style") or DEFAULT_STYLE)
    style = STYLES.get(style_key, STYLES[DEFAULT_STYLE])
    detection = (candidate or {}).get("detection") if isinstance((candidate or {}).get("detection"), dict) else {}
    mask = detection.get("mask") if isinstance(detection.get("mask"), dict) else {}
    return (
        "Photorealistic edit of the original customer portrait for hair color and highlights. "
        "Apply the selected hair color/light ONLY inside the provided hair mask; white mask pixels are editable hair and black pixels must remain unchanged. "
        "Do not change face, skin, eyes, lips, eyebrows, clothes, neck, background, lighting, hairstyle shape, camera angle, or identity. "
        "Preserve hair texture, shadows, strands, roots, and natural depth; no plastic wig, no beauty filter, no face retouching. "
        f"Selected service: آینه رنگ و لایت مو گیسو. Selected model: {style.get('label')}. Change level: {(candidate or {}).get('change_label') or ''}. "
        f"Style goal: {style.get('summary')}. Do: {'; '.join(style.get('do') or [])}. Avoid: {'; '.join(style.get('avoid') or [])}. "
        f"ROI method: {detection.get('method') or 'unknown'}, real_mask={mask.get('real_mask')}, coverage={mask.get('coverage_ratio')}. "
        "The result should look like the same person after a professional salon color consultation preview."
    )


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
        filename = f"final/final_hair_color_{datetime.utcnow().strftime('%Y%m%d%H%M%S')}_{uuid.uuid4().hex[:10]}.png"
        out_path = os.path.join(UPLOAD_DIR, filename)
        composed.save(out_path, "PNG", optimize=True)
        try:
            from giso.buti_ai.image_validation import validate_masked_output
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
