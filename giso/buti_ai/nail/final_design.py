# -*- coding: utf-8 -*-
"""Guided final design for آینه ناخن گیسو.

MVP output is a truthful non-AI guided try-on constrained to nail masks. It is
kept in this service folder so the Beauty Mirror architecture stays modular.
"""
from __future__ import annotations

import os
import uuid
from datetime import datetime
from typing import Any, Dict, List, Tuple

from giso.config import Config

SERVICE_KEY = "nail"
UPLOAD_DIR = os.path.join(Config.GISO_DIR, "data", "uploads", "buti_ai", SERVICE_KEY)
FINAL_DIR = os.path.join(UPLOAD_DIR, "final")

DEFAULT_STYLE = "nude_minimal"
STYLES: Dict[str, Dict[str, Any]] = {
    "nude_minimal": {
        "label": "نود و مینیمال",
        "icon": "💅",
        "summary": "رنگ نود شیک، تمیز و روزمره روی ناخن‌های خودت.",
        "why": "برای انتخاب امن و قابل اجرا در بیشتر سالن‌ها مناسب است.",
        "color": (224, 174, 160),
        "do": ["فرم طبیعی ناخن حفظ شود", "رنگ نود نرم انتخاب شود", "سطح ناخن براق و مرتب باشد"],
        "avoid": ["رنگ خیلی تیره", "طراحی شلوغ", "بلند کردن غیرواقعی ناخن"],
    },
    "classic_french": {
        "label": "فرنچ کلاسیک",
        "icon": "🤍",
        "summary": "پایه طبیعی با نوک سفید تمیز و قابل اجرا.",
        "why": "برای کاربرانی که ظاهر مرتب و کلاسیک می‌خواهند مناسب است.",
        "color": (236, 194, 184),
        "tip_color": (250, 250, 246),
        "do": ["خط فرنچ با قوس ناخن هماهنگ باشد", "پایه ناخن طبیعی بماند", "نوک سفید زیاد پهن نشود"],
        "avoid": ["سفیدی ضخیم", "فرم خیلی بلند", "تغییر رنگ پوست دست"],
    },
    "baby_boomer": {
        "label": "بیبی‌بومر",
        "icon": "🌸",
        "summary": "گرادیان نرم صورتی به سفید برای ظاهر عروس‌پسند.",
        "why": "برای خروجی ظریف، تمیز و پرطرفدار سالن‌ها مناسب است.",
        "color": (238, 184, 198),
        "tip_color": (252, 248, 246),
        "do": ["گرادیان نرم باشد", "مرز رنگ‌ها دیده نشود", "براقیت طبیعی حفظ شود"],
        "avoid": ["سفیدی گچی", "رنگ تخت", "تغییر فرم انگشت"],
    },
    "glazed_chrome": {
        "label": "کروم / گلیزد",
        "icon": "✨",
        "summary": "براقیت مرواریدی و شیک بدون طراحی سنگین.",
        "why": "برای کاربرانی که مدل مدرن اما قابل استفاده می‌خواهند جذاب است.",
        "color": (226, 206, 198),
        "do": ["درخشش با نور عکس هماهنگ باشد", "رنگ کروم ملایم باشد", "طراحی شلوغ نشود"],
        "avoid": ["فلز خیلی شدید", "بازتاب غیرواقعی", "تغییر پوست"],
    },
    "cat_eye": {
        "label": "کت‌آی",
        "icon": "🐈",
        "summary": "لاک مغناطیسی براق با خط نور ظریف روی ناخن.",
        "why": "برای انتخاب خاص‌تر و فروش‌پذیر در سالن ناخن مناسب است.",
        "color": (92, 40, 88),
        "do": ["خط نور روی هر ناخن با زاویه آن هماهنگ باشد", "رنگ عمیق و براق باشد", "اثر مغناطیسی ظریف بماند"],
        "avoid": ["خط نور کارتونی", "رنگ بیش از حد تیره", "تغییر انگشت‌ها"],
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
    ok = bool(w >= 160 and h >= 160)
    return {
        "status": "local_checked",
        "ok": ok,
        "message": "عکس دست/ناخن دریافت شد و برای پیش‌نمایش آماده است." if ok else "عکس خیلی کوچک است؛ عکس واضح‌تری از دست و ناخن بفرست.",
        "checks": {"nails_visible": None, "lighting": None, "sharpness": None},
    }


def _nail_boxes(w: int, h: int) -> List[Dict[str, Any]]:
    # Proportional hand/nail guide for non-AI MVP. Not marked as real AI mask.
    y = int(h * 0.33)
    box_w = max(14, int(w * 0.055))
    box_h = max(22, int(h * 0.075))
    xs = [0.30, 0.40, 0.50, 0.60, 0.70]
    boxes = []
    for idx, frac in enumerate(xs):
        boxes.append({
            "side": f"nail_{idx + 1}",
            "x": int(w * frac - box_w / 2),
            "y": y + int(abs(idx - 2) * h * 0.012),
            "width": box_w,
            "height": box_h,
            "confidence": 0.28,
            "source": "proportional_nail_guide",
        })
    return boxes


def _detect_nail_boxes_by_color(image_path: str) -> List[Dict[str, Any]]:
    """Find visible nail plates/tips in real hand photos using conservative color blobs."""
    try:
        from PIL import Image
        image = Image.open(image_path).convert("RGB")
        w, h = image.size
        # Work on a smaller copy for cheap connected components.
        max_side = 420
        scale = min(1.0, float(max_side) / float(max(w, h)))
        sw, sh = max(1, int(w * scale)), max(1, int(h * scale))
        small = image.resize((sw, sh), Image.Resampling.LANCZOS if hasattr(Image, "Resampling") else Image.LANCZOS)
        px = small.load()
        visited = [[False] * sw for _ in range(sh)]

        def is_nail_pixel(x: int, y: int) -> bool:
            # Nails/tips in salon photos are usually brighter/smoother than skin.
            r, g, b = px[x, y]
            mx, mn = max(r, g, b), min(r, g, b)
            sat = mx - mn
            bright_tip = r >= 205 and g >= 190 and b >= 178 and sat <= 72
            pink_plate = r >= 172 and g >= 115 and b >= 112 and (r - g) >= 18 and (g - b) <= 42 and sat >= 18
            glossy_light = mx >= 218 and sat <= 38
            upper_hand_area = y <= int(sh * 0.72)
            return upper_hand_area and (bright_tip or pink_plate or glossy_light)

        comps = []
        for y in range(0, sh):
            for x in range(0, sw):
                if visited[y][x] or not is_nail_pixel(x, y):
                    continue
                stack = [(x, y)]
                visited[y][x] = True
                xs, ys = [], []
                while stack:
                    cx, cy = stack.pop()
                    xs.append(cx); ys.append(cy)
                    for nx in (cx - 1, cx, cx + 1):
                        for ny in (cy - 1, cy, cy + 1):
                            if nx < 0 or ny < 0 or nx >= sw or ny >= sh or visited[ny][nx]:
                                continue
                            visited[ny][nx] = True
                            if is_nail_pixel(nx, ny):
                                stack.append((nx, ny))
                area = len(xs)
                if area < max(10, int(sw * sh * 0.00012)):
                    continue
                x0, x1, y0, y1 = min(xs), max(xs), min(ys), max(ys)
                bw, bh = x1 - x0 + 1, y1 - y0 + 1
                if bw < 4 or bh < 5:
                    continue
                aspect = bw / float(max(1, bh))
                if not (0.18 <= aspect <= 2.8):
                    continue
                if area > sw * sh * 0.035:
                    continue
                comps.append((area, x0, y0, x1, y1))

        # Merge nearby tip/plate components belonging to the same nail.
        comps = sorted(comps, key=lambda c: c[0], reverse=True)[:12]
        boxes = []
        for area, x0, y0, x1, y1 in comps:
            fx0, fy0 = int(x0 / scale), int(y0 / scale)
            fx1, fy1 = int((x1 + 1) / scale), int((y1 + 1) / scale)
            bw, bh = max(8, fx1 - fx0), max(10, fy1 - fy0)
            # Expand from bright tip to full nail bed; keep it small enough not to paint fingers.
            pad_x = max(3, int(bw * 0.24))
            pad_top = max(2, int(bh * 0.15))
            pad_bottom = max(12, int(bh * 1.75))
            bx = max(0, fx0 - pad_x)
            by = max(0, fy0 - pad_top)
            bx2 = min(w - 1, fx1 + pad_x)
            by2 = min(h - 1, fy1 + pad_bottom)
            if (bx2 - bx) * (by2 - by) > w * h * 0.045:
                continue
            # De-duplicate overlapping boxes.
            duplicate = False
            for existing in boxes:
                ex0, ey0 = existing["x"], existing["y"]
                ex1, ey1 = ex0 + existing["width"], ey0 + existing["height"]
                ix = max(0, min(bx2, ex1) - max(bx, ex0))
                iy = max(0, min(by2, ey1) - max(by, ey0))
                if ix * iy > 0.45 * min(max(1, (bx2 - bx) * (by2 - by)), max(1, existing["width"] * existing["height"])):
                    duplicate = True
                    break
            if duplicate:
                continue
            boxes.append({
                "side": f"nail_{len(boxes) + 1}",
                "x": int(bx),
                "y": int(by),
                "width": int(max(8, bx2 - bx)),
                "height": int(max(10, by2 - by)),
                "confidence": 0.70,
                "source": "color_nail_plate_mask_v1",
            })
        boxes.sort(key=lambda r: (r["x"], r["y"]))
        return boxes[:5]
    except Exception:
        return []


def _nail_contrast_score(image_path: str, regions: List[Dict[str, Any]]) -> float:
    """Validate the proportional nail plates against the actual image.

    This stays conservative: if the expected small nail regions are not visibly
    different from the surrounding finger/hand area, the mask remains fallback
    and is never used to claim real AI output.
    """
    try:
        from PIL import Image
        image = Image.open(image_path).convert("RGB")
        w, h = image.size
        px = image.load()
        scores: List[float] = []
        for r in regions:
            x = max(0, int(r["x"]))
            y = max(0, int(r["y"]))
            rw = max(3, int(r["width"]))
            rh = max(4, int(r["height"]))
            inside = []
            ring = []
            for yy in range(max(0, y - rh // 2), min(h, y + rh + rh // 2)):
                for xx in range(max(0, x - rw // 2), min(w, x + rw + rw // 2)):
                    val = px[xx, yy]
                    brightness = sum(val) / 3.0
                    sat = max(val) - min(val)
                    if x <= xx <= x + rw and y <= yy <= y + rh:
                        inside.append((brightness, sat))
                    else:
                        ring.append((brightness, sat))
            if not inside or not ring:
                continue
            in_b = sum(v[0] for v in inside) / len(inside)
            out_b = sum(v[0] for v in ring) / len(ring)
            in_s = sum(v[1] for v in inside) / len(inside)
            out_s = sum(v[1] for v in ring) / len(ring)
            scores.append(max(abs(in_b - out_b), abs(in_s - out_s) * 0.8))
        if not scores:
            return 0.0
        passed = [s for s in scores if s >= 7.5]
        return len(passed) / float(max(1, len(regions)))
    except Exception:
        return 0.0


def detect_regions(image_path: str, allow_fallback: bool = True) -> Dict[str, Any]:
    w, h = _image_size(image_path)
    if not w or not h:
        return {"ok": False, "method": "invalid_image", "regions": [], "mask": {"ok": False, "reason": "invalid_image"}}
    color_regions = _detect_nail_boxes_by_color(image_path)
    if len(color_regions) >= 3:
        regions = color_regions
        reliable = True
        contrast_score = 1.0
    else:
        regions = _nail_boxes(w, h)
        contrast_score = _nail_contrast_score(image_path, regions)
        reliable = contrast_score >= 0.8
    if not reliable and not allow_fallback:
        return {"ok": False, "method": "nail_plate_not_detected", "regions": [], "mask": {"ok": False, "reason": "nail_plate_not_detected"}}
    detection = {
        "ok": True,
        "method": "color_nail_plate_mask_v1" if len(color_regions) >= 3 else ("color_validated_nail_plate_mask_v1" if reliable else "proportional_nail_guide"),
        "confidence": 0.72 if len(color_regions) >= 3 else (0.66 if reliable else 0.28),
        "detection_reliable": bool(reliable),
        "is_fallback": not bool(reliable),
        "image_width": w,
        "image_height": h,
        "contrast_score": round(float(contrast_score), 4),
        "regions": regions,
    }
    return ensure_mask(image_path, detection)


def ensure_mask(image_path: str, detection: Dict[str, Any]) -> Dict[str, Any]:
    try:
        from PIL import Image, ImageDraw
        w = int(detection.get("image_width") or 0)
        h = int(detection.get("image_height") or 0)
        mask = Image.new("L", (w, h), 0)
        draw = ImageDraw.Draw(mask)
        for r in detection.get("regions") or []:
            x, y = int(r["x"]), int(r["y"])
            rw, rh = int(r["width"]), int(r["height"])
            draw.rounded_rectangle((x, y, x + rw, y + rh), radius=max(4, rw // 3), fill=255)
        mask_dir = os.path.join(os.path.dirname(os.path.abspath(image_path)), "masks")
        os.makedirs(mask_dir, exist_ok=True)
        mask_path = os.path.join(mask_dir, os.path.splitext(os.path.basename(image_path))[0] + "_nail_mask.png")
        mask.save(mask_path, "PNG", optimize=True)
        pixels = sum(1 for px in mask.getdata() if px > 0)
        detection["mask"] = {
            "ok": pixels > 0,
            "kind": "nail_plate_guided_mask",
            "format": "png_luminance",
            "path": mask_path,
            "width": w,
            "height": h,
            "coverage_ratio": round(pixels / float(max(1, w * h)), 6),
            "pixel_count": pixels,
            "real_mask": not bool(detection.get("is_fallback")),
            "is_fallback": bool(detection.get("is_fallback")),
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


def _draw_style_overlay(base, style_key: str, detection: Dict[str, Any]):
    from PIL import Image, ImageDraw, ImageFilter
    style = STYLES.get(style_key, STYLES[DEFAULT_STYLE])
    overlay = Image.new("RGBA", base.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    sx = base.size[0] / float(max(1, detection.get("image_width") or base.size[0]))
    sy = base.size[1] / float(max(1, detection.get("image_height") or base.size[1]))
    color = tuple(style.get("color") or (224, 174, 160))
    for r in detection.get("regions") or []:
        x = int(float(r["x"]) * sx)
        y = int(float(r["y"]) * sy)
        rw = max(4, int(float(r["width"]) * sx))
        rh = max(6, int(float(r["height"]) * sy))
        radius = max(4, rw // 3)
        draw.rounded_rectangle((x, y, x + rw, y + rh), radius=radius, fill=color + (178,))
        draw.rounded_rectangle((x + 2, y + 2, x + rw - 2, y + rh - 2), radius=radius, outline=(255, 255, 255, 78), width=1)
        if style_key == "classic_french":
            tip = tuple(style.get("tip_color") or (250, 250, 246))
            draw.rounded_rectangle((x, y, x + rw, y + max(y + 5, y + int(rh * 0.28))), radius=radius, fill=tip + (230,))
        elif style_key == "baby_boomer":
            tip = tuple(style.get("tip_color") or (252, 248, 246))
            for i in range(max(1, rh)):
                alpha = int(120 * (1 - i / max(1, rh)))
                draw.line((x + 2, y + i, x + rw - 2, y + i), fill=tip + (alpha,), width=1)
        elif style_key == "glazed_chrome":
            draw.arc((x + 3, y + 3, x + rw - 3, y + rh - 3), 200, 330, fill=(255, 255, 255, 150), width=2)
        elif style_key == "cat_eye":
            draw.line((x + 4, y + rh - 5, x + rw - 4, y + 5), fill=(255, 220, 255, 190), width=max(1, rw // 9))
    return overlay.filter(ImageFilter.GaussianBlur(radius=0.25))


def build_design_prompt(candidate: Dict[str, Any]) -> str:
    style_key = str((candidate or {}).get("final_style") or DEFAULT_STYLE)
    style = STYLES.get(style_key, STYLES[DEFAULT_STYLE])
    detection = (candidate or {}).get("detection") if isinstance((candidate or {}).get("detection"), dict) else {}
    mask = detection.get("mask") if isinstance(detection.get("mask"), dict) else {}
    return (
        "Photorealistic edit of the original customer hand photo for nail try-on. "
        "Apply the selected nail design ONLY inside the provided nail-plate mask; white mask pixels are editable nail plates and black pixels must remain unchanged. "
        "Do not change fingers, skin tone, cuticles, hand shape, jewelry, background, lighting, camera angle, or nail length outside the existing nail plate. "
        "Keep natural reflections and anatomy; no extra fingers, no artificial hand, no cartoon polish. "
        f"Selected service: آینه ناخن گیسو. Selected model: {style.get('label')}. Change level: {(candidate or {}).get('change_label') or ''}. "
        f"Style goal: {style.get('summary')}. Do: {'; '.join(style.get('do') or [])}. Avoid: {'; '.join(style.get('avoid') or [])}. "
        f"ROI method: {detection.get('method') or 'unknown'}, real_mask={mask.get('real_mask')}, coverage={mask.get('coverage_ratio')}. "
        "The result should look like the same hand after a professional nail-color consultation preview."
    )


def generate_guided_design(candidate: Dict[str, Any]) -> Dict[str, Any]:
    src = _source_path(candidate)
    if not src:
        return {"ok": False, "status": "missing_photo", "message": "برای طراحی ناخن، عکس واقعی لازم است."}
    try:
        from PIL import Image
        base = Image.open(src).convert("RGB")
        base.thumbnail((1400, 1400))
        detection = candidate.get("detection") if isinstance(candidate.get("detection"), dict) else detect_regions(src, allow_fallback=True)
        overlay = _draw_style_overlay(base, str(candidate.get("final_style") or DEFAULT_STYLE), detection)
        composed = Image.alpha_composite(base.convert("RGBA"), overlay).convert("RGB")
        os.makedirs(FINAL_DIR, exist_ok=True)
        filename = f"final/final_nail_{datetime.utcnow().strftime('%Y%m%d%H%M%S')}_{uuid.uuid4().hex[:10]}.png"
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
            "model": "pillow_nail_overlay_v1",
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
            "message": "طراحی راهنمای ناخن آماده شد؛ این نسخه AI واقعی نیست اما روی عکس خودت ساخته شده است.",
        }
    except Exception as exc:
        return {"ok": False, "status": "generate_failed", "message": f"ساخت طراحی ناخن انجام نشد: {str(exc)[:120]}"}
