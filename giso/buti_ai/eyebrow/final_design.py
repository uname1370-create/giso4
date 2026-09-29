# -*- coding: utf-8 -*-
"""انتخاب نهایی و ساخت طراحی عکس نهایی راهنمای ابرو با Python.

این ماژول عمداً داخل Buti AI است. اگر در مدیریت AI مدل تصویرسازی فعال باشد،
خروجی provider-backed می‌سازد؛ در غیر این صورت خروجی راهنمای پایتونی امن
و بدون ادعای تولید واقعی ارائه می‌شود.
"""
import json
import math
import os
import uuid
from datetime import datetime

from giso.buti_ai.eyebrow.landmarks import detect_eyebrow_regions, ensure_eyebrow_mask, proportional_fallback_regions
from giso.buti_ai.eyebrow.options import CHANGE_LEVELS, EYEBROW_STYLES, normalize_change_level, normalize_style_key
from giso.buti_ai.eyebrow.upload import EYEBROW_UPLOAD_DIR

FINAL_DESIGN_SESSION_KEY = "buti_ai_eyebrow_final_candidate"
FINAL_DESIGN_DIR = os.path.join(EYEBROW_UPLOAD_DIR, "final")


STYLE_RENDER = {
    "natural": {"alpha": 112, "width": 6, "shade": 0.14, "strokes": 11, "blur": 0.9},
    "microblading": {"alpha": 140, "width": 3, "shade": 0.04, "strokes": 24, "blur": 0.4},
    "powder": {"alpha": 132, "width": 10, "shade": 0.26, "strokes": 4, "blur": 1.5},
    "combination": {"alpha": 142, "width": 8, "shade": 0.18, "strokes": 16, "blur": 0.85},
    "giso_suggested": {"alpha": 126, "width": 7, "shade": 0.15, "strokes": 14, "blur": 0.75},
}



def _render_params_for_candidate(candidate):
    final_style = normalize_style_key((candidate or {}).get("final_style"))
    params = dict(STYLE_RENDER.get(final_style, STYLE_RENDER["giso_suggested"]))
    change_key = normalize_change_level((candidate or {}).get("change_key"))
    if change_key == "very_natural":
        params["alpha"] = max(70, int(params["alpha"] * 0.82))
        params["width"] = max(2, int(params["width"] * 0.86))
        params["shade"] = float(params.get("shade") or 0) * 0.75
    elif change_key == "clear":
        params["alpha"] = min(165, int(params["alpha"] * 1.12))
        params["width"] = max(2, int(params["width"] * 1.08))
        params["shade"] = min(0.42, float(params.get("shade") or 0) * 1.18)
    return params

def _clean_text(value, fallback="", limit=220):
    text = str(value or "").strip() or fallback
    return text[:limit]


def _safe_filename(filename):
    filename = os.path.basename(str(filename or ""))
    if not filename or "/" in filename or "\\" in filename:
        return ""
    return filename


def _style_label(style_key):
    style_key = normalize_style_key(style_key)
    return EYEBROW_STYLES[style_key]["label"]


def _style_score_items(result):
    items = []
    for item in (result or {}).get("style_scores") or []:
        style_key = normalize_style_key(item.get("style_key") or item.get("style"))
        try:
            score = int(item.get("score") or 0)
        except Exception:
            score = 0
        items.append({
            "style_key": style_key,
            "label": _style_label(style_key),
            "score": max(0, min(100, score)),
            "reason": _clean_text(item.get("reason"), EYEBROW_STYLES[style_key].get("summary", ""), 130),
            "is_recommended": bool(item.get("is_recommended")),
            "is_selected": bool(item.get("is_selected")),
        })
    if not items:
        rec = normalize_style_key((result or {}).get("style_key"))
        for key in EYEBROW_STYLES:
            items.append({
                "style_key": key,
                "label": _style_label(key),
                "score": 88 if key == rec else 65,
                "reason": EYEBROW_STYLES[key].get("summary", ""),
                "is_recommended": key == rec,
                "is_selected": key == (result or {}).get("selected_style_key"),
            })
    return items


def build_final_candidate(result, photo_status):
    """خلاصه کوچک و امن برای نگهداری در session."""
    result = result or {}
    photo_status = photo_status or {}
    selected_style = normalize_style_key(result.get("selected_style_key") or result.get("style_key"))
    # مدل انتخاب‌شده کاربر تنها منبع حقیقت طراحی نهایی است؛ recommended فقط سازگاری قدیمی است.
    recommended_style = selected_style
    change_key = normalize_change_level(result.get("selected_change_key") or result.get("change_key"))
    filename = _safe_filename(photo_status.get("filename") or (result.get("preview") or {}).get("before_filename"))
    selected_meta = EYEBROW_STYLES[selected_style]
    eyebrow_detection = result.get("eyebrow_detection") if isinstance(result.get("eyebrow_detection"), dict) else {}
    created_at = datetime.utcnow().isoformat(timespec="seconds")
    cache_key = f"{filename}-{created_at}" if filename else created_at
    return {
        "session_id": result.get("session_id"),
        "photo_filename": filename,
        "recommended_style": recommended_style,
        "recommended_label": _style_label(recommended_style),
        "service_label": result.get("service_label") or "آینه ابرو گیسو / طراحی هوشمند ابرو",
        "selected_style": selected_style,
        "selected_label": _style_label(selected_style),
        "final_style": selected_style,
        "final_label": _style_label(selected_style),
        "change_key": change_key,
        "change_label": CHANGE_LEVELS.get(change_key, CHANGE_LEVELS["very_natural"]),
        "short_reason": _clean_text(result.get("short_reason") or result.get("why"), selected_meta.get("why", ""), 180),
        "why": _clean_text(result.get("why"), selected_meta.get("why", ""), 240),
        "current_brow_summary": _clean_text(result.get("current_brow_summary"), "", 180),
        "do": [str(x)[:90] for x in (result.get("do") or [])[:3]],
        "avoid": [str(x)[:90] for x in (result.get("avoid") or [])[:3]],
        "style_scores": _style_score_items(result),
        "face_analysis": result.get("face_analysis") or {},
        "eyebrow_detection": eyebrow_detection,
        "ai_is_real": bool(result.get("ai_is_real")),
        "created_at": created_at,
        "cache_key": cache_key,
    }


def store_final_candidate(session_obj, result, photo_status):
    candidate = build_final_candidate(result, photo_status)
    session_obj[FINAL_DESIGN_SESSION_KEY] = candidate
    session_obj.modified = True
    return candidate


def get_final_candidate(session_obj):
    candidate = session_obj.get(FINAL_DESIGN_SESSION_KEY) or {}
    return candidate if isinstance(candidate, dict) else {}


def update_final_selection(session_obj, final_style_key=None):
    """سازگاری با route قدیمی finalize؛ مدل نهایی از انتخاب اولیه کاربر می‌آید."""
    candidate = get_final_candidate(session_obj)
    previous_style = normalize_style_key(candidate.get("final_style") or candidate.get("selected_style"))
    final_style = normalize_style_key(candidate.get("selected_style") or final_style_key or candidate.get("recommended_style"))
    candidate["selected_style"] = final_style
    candidate["selected_label"] = _style_label(final_style)
    candidate["recommended_style"] = final_style
    candidate["recommended_label"] = _style_label(final_style)
    candidate["final_style"] = final_style
    candidate["final_label"] = _style_label(final_style)
    if final_style != previous_style:
        candidate.pop("generation", None)
        candidate.pop("final_design_id", None)
    session_obj[FINAL_DESIGN_SESSION_KEY] = candidate
    session_obj.modified = True
    return candidate


def _source_path(candidate):
    filename = _safe_filename(candidate.get("photo_filename"))
    if not filename:
        return ""
    path = os.path.abspath(os.path.join(EYEBROW_UPLOAD_DIR, filename))
    root = os.path.abspath(EYEBROW_UPLOAD_DIR)
    if not path.startswith(root + os.sep):
        return ""
    return path if os.path.exists(path) else ""


def source_image_path(candidate):
    """مسیر امن عکس اصلی برای مصرف providerهای تصویرسازی داخل Buti AI."""
    return _source_path(candidate or {})


def ensure_eyebrow_detection(candidate):
    """اگر ROI/polygon/mask ابرو در candidate نیست، از روی عکس آن را تشخیص می‌دهد."""
    candidate = candidate if isinstance(candidate, dict) else {}
    src = _source_path(candidate)
    existing = candidate.get("eyebrow_detection")
    if isinstance(existing, dict) and existing.get("regions"):
        mask = existing.get("mask") if isinstance(existing.get("mask"), dict) else {}
        if src and not (mask.get("ok") and mask.get("path")):
            existing = ensure_eyebrow_mask(src, existing)
            candidate["eyebrow_detection"] = existing
        return existing
    if not src:
        return {}
    detection = detect_eyebrow_regions(src, allow_fallback=False)
    if isinstance(detection, dict) and detection.get("regions"):
        detection = ensure_eyebrow_mask(src, detection)
    candidate["eyebrow_detection"] = detection
    return detection


def _eyebrow_region_text(candidate):
    detection = candidate.get("eyebrow_detection") if isinstance(candidate, dict) else {}
    if not isinstance(detection, dict) or not detection.get("regions"):
        return "No reliable eyebrow polygon/mask was detected; do not treat prompt coordinates as a mask and leave all non-eyebrow areas unchanged."
    image_w = detection.get("image_width") or "?"
    image_h = detection.get("image_height") or "?"
    mask = detection.get("mask") if isinstance(detection.get("mask"), dict) else {}
    chunks = []
    for region in (detection.get("regions") or [])[:2]:
        try:
            polygon_points = region.get("polygon") if isinstance(region.get("polygon"), list) else []
            chunks.append(
                f"{region.get('side')}: bbox x={int(region.get('x') or 0)}, y={int(region.get('y') or 0)}, "
                f"w={int(region.get('width') or 0)}, h={int(region.get('height') or 0)}, "
                f"polygon_points={len(polygon_points)}"
            )
        except Exception:
            continue
    method = detection.get("method") or "unknown"
    mask_text = ""
    if mask.get("ok"):
        mask_text = (
            f" Pixel eyebrow mask available {mask.get('width') or image_w}x{mask.get('height') or image_h}, "
            f"polarity={mask.get('polarity') or 'white_edit_black_keep'}, "
            f"coverage={mask.get('coverage_ratio')}."
        )
    return f"Detected eyebrow polygon regions on original image {image_w}x{image_h} using {method}: " + "; ".join(chunks) + mask_text


def _scaled_regions_for_image(candidate, image_w, image_h):
    detection = ensure_eyebrow_detection(candidate)
    method = str((detection or {}).get("method") or "not_detected")
    regions = (detection or {}).get("regions") or []
    source_w = float((detection or {}).get("image_width") or image_w or 1)
    source_h = float((detection or {}).get("image_height") or image_h or 1)
    if not regions:
        detection = proportional_fallback_regions(image_w, image_h)
        method = detection.get("method", "proportional_fallback")
        regions = detection.get("regions") or []
        source_w = float(image_w or 1)
        source_h = float(image_h or 1)
    sx = float(image_w or 1) / max(1.0, source_w)
    sy = float(image_h or 1) / max(1.0, source_h)
    scaled = []
    for region in regions[:2]:
        scaled.append({
            "side": region.get("side") or "",
            "x": float(region.get("x") or 0) * sx,
            "y": float(region.get("y") or 0) * sy,
            "width": max(8.0, float(region.get("width") or 0) * sx),
            "height": max(8.0, float(region.get("height") or 0) * sy),
            "confidence": float(region.get("confidence") or 0),
        })
    return scaled, method, detection


def _brow_curve(cx, cy, length, arch, flip=False, steps=30):
    points = []
    for i in range(steps):
        t = i / max(1, steps - 1)
        x = cx - length / 2 + length * t
        y = cy - arch * math.sin(math.pi * t) + (t - 0.5) * arch * 0.26
        if flip:
            x = cx + length / 2 - length * t
        points.append((x, y))
    return points


def _tapered_brow_shape(points, thickness):
    upper = []
    lower = []
    count = len(points)
    if count < 2:
        return []
    for idx, (x, y) in enumerate(points):
        prev_x, prev_y = points[max(0, idx - 1)]
        next_x, next_y = points[min(count - 1, idx + 1)]
        dx = float(next_x - prev_x)
        dy = float(next_y - prev_y)
        norm = math.sqrt(dx * dx + dy * dy) or 1.0
        nx = -dy / norm
        ny = dx / norm
        t = idx / max(1, count - 1)
        # Thicker through the body, thinner at head/tail to look like an eyebrow, not a marker stroke.
        profile = 0.38 + 0.72 * math.sin(math.pi * t)
        if t < 0.14:
            profile *= 0.72
        if t > 0.82:
            profile *= max(0.24, 1.0 - (t - 0.82) * 2.9)
        half = max(1.8, float(thickness) * profile)
        upper.append((x + nx * half, y + ny * half))
        lower.append((x - nx * half * 0.78, y - ny * half * 0.78))
    return upper + list(reversed(lower))


def _draw_brow(draw, cx, cy, length, arch, color, params, flip=False, mode="combination"):
    points = _brow_curve(cx, cy, length, arch, flip=flip)
    width = max(2, int(params["width"]))
    shade = float(params.get("shade") or 0)
    shape = _tapered_brow_shape(points, max(width + 2, width * (1.15 + shade)))
    if shape:
        fill_alpha = int(color[3] * (0.38 + min(0.36, shade)))
        fill_color = color[:3] + (max(36, min(178, fill_alpha)),)
        draw.polygon(shape, fill=fill_color)
    if params.get("shade", 0) > 0:
        shade_width = max(width + 6, int(width * 1.7))
        shade_color = color[:3] + (int(color[3] * params["shade"]),)
        draw.line(points, fill=shade_color, width=shade_width, joint="curve")
    draw.line(points, fill=color, width=max(1, int(width * 0.72)), joint="curve")

    stroke_count = int(params.get("strokes") or 0)
    if stroke_count <= 0:
        return
    for i in range(stroke_count):
        t = (i + 0.5) / stroke_count
        if mode == "combination" and t > 0.62:
            # در کامبینیشن، تاج تاربه‌تارتر و دم کمی سایه‌دارتر است.
            continue
        if mode == "powder" and i % 3:
            continue
        x = cx - length / 2 + length * t
        if flip:
            x = cx + length / 2 - length * t
        y = cy - arch * math.sin(math.pi * t) + (t - 0.5) * arch * 0.26
        slant = (-1 if flip else 1) * (arch * 0.36)
        stroke_len = max(7, length * 0.075)
        stroke_color = color[:3] + (min(210, int(color[3] * 1.12)),)
        draw.line(
            [(x - slant * 0.15, y + stroke_len * 0.35), (x + slant * 0.25, y - stroke_len * 0.65)],
            fill=stroke_color,
            width=max(1, int(width * 0.34)),
        )


def build_design_prompt(candidate):
    """پرامپت دقیق برای provider تصویر؛ فقط ناحیه ابرو و حفظ هویت کاربر."""
    style_label = candidate.get("final_label") or _style_label(candidate.get("final_style"))
    service_label = candidate.get("service_label") or "intelligent eyebrow design"
    model_label = candidate.get("selected_label") or style_label

    def _prompt_text(value):
        if isinstance(value, dict):
            return "; ".join(f"{k}: {v}" for k, v in value.items() if v)[:420]
        if isinstance(value, (list, tuple)):
            return "; ".join(str(x) for x in value if x)[:420]
        return str(value or "")[:420]

    face_notes = _prompt_text(candidate.get("face_analysis"))
    current_brows = _prompt_text(candidate.get("current_brow_summary"))
    style_instructions = _prompt_text(candidate.get("do") or candidate.get("short_reason"))
    avoid = _prompt_text(candidate.get("avoid"))
    region_text = _eyebrow_region_text(candidate)
    return (
        "Photorealistic image edit of the ORIGINAL customer face photo. "
        "The selected beauty service is intelligent eyebrow design preview; apply ONLY the user-selected eyebrow model to the natural brow location. "
        "Use the provided eyebrow pixel mask when the API request includes one; white mask pixels are the editable eyebrow area and black pixels must be preserved. "
        "Prompt text and ROI coordinates are only descriptive metadata, not a substitute for the mask. "
        "Edit ONLY the two eyebrow regions: brow hairs, shape, fill, tail, arch, and very local brow shadow if needed. "
        "Hard constraint: every pixel outside the two eyebrow hair regions must remain identical to the original photo. "
        "Do not change identity, face shape, eyes, eyelids, lashes, eye color, skin texture, hair, makeup, lips, nose, lighting, camera angle, background, jewelry, clothes, or expression. "
        "Do not add eyeliner, mascara, eye shadow, extra eyelashes, eye retouching, skin smoothing, or glam makeup. "
        "Keep pores, shadows and natural asymmetry realistic. No beauty filter, no new face, no illustration, no heavy retouching. "
        f"Selected service: {service_label}. "
        f"Selected eyebrow model: {model_label}. Final design label: {style_label}. "
        f"Requested change level: {candidate.get('change_label', '')}. "
        f"Real eyebrow location: {region_text}. "
        f"Current eyebrow notes: {current_brows}. "
        f"Face preservation notes: {face_notes}. "
        f"Selected-style instructions: {style_instructions}. "
        f"Avoid: {avoid}. "
        "The result should look like the same photo after a professional eyebrow consultation preview; subtle, wearable, and salon-realistic."
    )


def generate_python_guided_design(candidate):
    """ساخت تصویر راهنمای نهایی با Pillow روی ROI تشخیص‌داده‌شده ابرو."""
    src = _source_path(candidate)
    if not src:
        return {"ok": False, "message": "برای طراحی عکس نهایی، عکس واقعی لازم است.", "status": "missing_photo"}

    try:
        from PIL import Image, ImageChops, ImageDraw, ImageFilter
    except Exception:
        return {"ok": False, "message": "کتابخانه پردازش تصویر در دسترس نیست.", "status": "pillow_missing"}

    final_style = normalize_style_key(candidate.get("final_style"))
    params = _render_params_for_candidate(candidate)

    try:
        base = Image.open(src).convert("RGB")
        base.thumbnail((1400, 1400))
        w, h = base.size
        overlay = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        draw = ImageDraw.Draw(overlay)

        regions, detection_method, detection = _scaled_regions_for_image(candidate, w, h)
        alpha = int(params["alpha"])
        # رنگ و شفافیت عمداً ملایم است تا خروجی fallback شبیه راهنمای مشاوره بماند، نه اجرای قطعی.
        color = (46, 29, 21, alpha)
        mode = "combination" if final_style in ("combination", "giso_suggested") else final_style

        for idx, region in enumerate(regions[:2]):
            brow_len = max(42.0, float(region.get("width") or 0) * 0.96)
            arch = max(7.0, float(region.get("height") or 0) * 0.38)
            cx = float(region.get("x") or 0) + float(region.get("width") or 0) / 2.0
            cy = float(region.get("y") or 0) + float(region.get("height") or 0) * 0.52
            _draw_brow(draw, cx, cy, brow_len, arch, color, params, flip=(idx == 1), mode=mode)

        blur = float(params.get("blur") or 0)
        if blur > 0:
            overlay = overlay.filter(ImageFilter.GaussianBlur(radius=blur))

        # Safety gate: the guide stays around the brow ROI, but we dilate the
        # local design mask a little so the user sees a real selected style
        # (combination/powder/microblading), not just a thin debug mask line.
        try:
            guide_mask = Image.new("L", (w, h), 0)
            guide_draw = ImageDraw.Draw(guide_mask)
            for region in regions[:2]:
                x = float(region.get("x") or 0)
                y = float(region.get("y") or 0)
                rw = float(region.get("width") or 0)
                rh = float(region.get("height") or 0)
                pad_x = max(4.0, rw * 0.07)
                pad_top = max(2.0, rh * 0.18)
                pad_bottom = max(4.0, rh * 0.34)
                guide_draw.rounded_rectangle(
                    (int(x - pad_x), int(y - pad_top), int(x + rw + pad_x), int(y + rh + pad_bottom)),
                    radius=max(3, int(max(4.0, rh * 0.38))),
                    fill=255,
                )
            mask_info = detection.get("mask") if isinstance(detection.get("mask"), dict) else {}
            mask_path = str(mask_info.get("path") or detection.get("mask_path") or "").strip()
            if mask_info.get("ok") and mask_path and os.path.exists(mask_path):
                real_mask = Image.open(mask_path).convert("L").resize((w, h), Image.Resampling.LANCZOS if hasattr(Image, "Resampling") else Image.LANCZOS)
                real_mask = real_mask.point(lambda px: 255 if int(px) >= 96 else 0)
                # Dilation keeps it local while preventing a hairline-only result.
                real_mask = real_mask.filter(ImageFilter.MaxFilter(size=7))
                guide_mask = ImageChops.lighter(guide_mask, real_mask)
            guide_mask = guide_mask.filter(ImageFilter.GaussianBlur(radius=0.9))
            overlay.putalpha(ImageChops.multiply(overlay.getchannel("A"), guide_mask))
        except Exception:
            pass

        composed = Image.alpha_composite(base.convert("RGBA"), overlay).convert("RGB")
        os.makedirs(FINAL_DESIGN_DIR, exist_ok=True)
        out_name = f"final/final_eyebrow_{datetime.utcnow().strftime('%Y%m%d%H%M%S')}_{uuid.uuid4().hex[:10]}.jpg"
        out_path = os.path.join(EYEBROW_UPLOAD_DIR, out_name)
        composed.save(out_path, "JPEG", quality=88, optimize=True)
        mask_info = detection.get("mask") if isinstance(detection.get("mask"), dict) else {}
        mask_filename = ""
        raw_mask_path = ""
        try:
            mask_path = os.path.abspath(str(mask_info.get("path") or detection.get("mask_path") or ""))
            raw_mask_path = mask_path if os.path.exists(mask_path) else ""
            upload_root = os.path.abspath(EYEBROW_UPLOAD_DIR)
            if mask_path.startswith(upload_root + os.sep):
                mask_filename = os.path.relpath(mask_path, upload_root).replace(os.sep, "/")
        except Exception:
            mask_filename = ""
            raw_mask_path = ""
        try:
            from giso.buti_ai.image_validation import validate_masked_output
            validation = validate_masked_output(src, out_path, raw_mask_path, service_key="eyebrow")
        except Exception:
            validation = {}
        return {
            "ok": True,
            "filename": out_name,
            "provider": "python_guided_composite",
            "model": "pillow_brow_overlay_v1",
            "status": "non_ai_guided_preview_ready",
            "prompt": build_design_prompt(candidate),
            "eyebrow_detection_method": detection_method,
            "eyebrow_detection": detection,
            "mask_filename": mask_filename,
            "mask_used": bool(mask_filename),
            "validation": validation,
            "visible_in_mask_change": bool(validation.get("visible_in_mask_change")) if isinstance(validation, dict) else False,
            "outside_preserved": bool(validation.get("outside_preserved")) if isinstance(validation, dict) else False,
            "ai_inpainting": False,
            "is_ai_generated": False,
            "fallback_type": "non_ai_guided_fallback",
            "message": "طراحی راهنمای غیر AI آماده شد.",
        }
    except Exception as exc:
        return {"ok": False, "message": f"ساخت طراحی عکس نهایی انجام نشد: {str(exc)[:120]}", "status": "generate_failed"}


def candidate_to_json(candidate):
    try:
        return json.dumps(candidate or {}, ensure_ascii=False)
    except Exception:
        return "{}"
