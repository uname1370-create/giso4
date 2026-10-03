# -*- coding: utf-8 -*-
"""انتخاب نهایی و ساخت طراحی عکس نهایی راهنمای ابرو با Python.

این ماژول عمداً داخل Buti AI است. اگر در مدیریت AI مدل تصویرسازی فعال باشد،
خروجی provider-backed می‌سازد؛ در غیر این صورت خروجی راهنمای پایتونی امن
و بدون ادعای تولید واقعی ارائه می‌شود.
"""
import json
import logging
import math
import os
import uuid
from datetime import datetime
from typing import Any, Dict

from giso.buti_ai.eyebrow.landmarks import detect_eyebrow_regions, ensure_eyebrow_mask, proportional_fallback_regions
from giso.buti_ai.eyebrow.options import CHANGE_LEVELS, EYEBROW_STYLES, normalize_change_level, normalize_style_key
from giso.buti_ai.eyebrow.upload import EYEBROW_UPLOAD_DIR

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

FINAL_DESIGN_SESSION_KEY = "buti_ai_eyebrow_final_candidate"
FINAL_DESIGN_DIR = os.path.join(EYEBROW_UPLOAD_DIR, "final")


STYLE_RENDER = {
    # Increased thickness/alpha for real visible redesign – fix "abro kamel doros nashod" + mask small
    "natural": {"alpha": 145, "width": 8, "shade": 0.18, "strokes": 18, "blur": 0.5},
    "microblading": {"alpha": 165, "width": 4, "shade": 0.08, "strokes": 34, "blur": 0.25},
    "powder": {"alpha": 155, "width": 12, "shade": 0.32, "strokes": 8, "blur": 0.9},
    "combination": {"alpha": 160, "width": 10, "shade": 0.24, "strokes": 24, "blur": 0.5},
    "giso_suggested": {"alpha": 150, "width": 9, "shade": 0.20, "strokes": 20, "blur": 0.5},
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

def _sample_skin_color(image, regions):
    try:
        w, h = image.size
        samples = []
        for region in regions[:2]:
            x = int(region.get("x") or 0)
            y = int(region.get("y") or 0)
            rw = int(region.get("width") or 0)
            rh = int(region.get("height") or 0)
            for dx, dy in [(rw*0.3, -rh*0.8), (rw*0.7, -rh*0.8), (rw*0.5, rh*1.5)]:
                sx = max(0, min(w-1, int(x + dx)))
                sy = max(0, min(h-1, int(y + dy)))
                try:
                    r, g, b = image.getpixel((sx, sy))[:3]
                    if 60 < r < 230 and 40 < g < 210 and 30 < b < 200:
                        samples.append((r, g, b))
                except Exception:
                    continue
        if not samples:
            return (195, 165, 135)
        avg_r = sum(s[0] for s in samples) // len(samples)
        avg_g = sum(s[1] for s in samples) // len(samples)
        avg_b = sum(s[2] for s in samples) // len(samples)
        return (avg_r, avg_g, avg_b)
    except Exception:
        return (195, 165, 135)

def _brow_color_for_skin(skin_rgb, style_key):
    sr, sg, sb = skin_rgb
    brightness = (sr + sg + sb) / 3.0
    if brightness > 180:
        base = (58, 38, 28)
    elif brightness > 130:
        base = (46, 29, 21)
    else:
        base = (38, 24, 18)
    if style_key == "microblading":
        base = (base[0]+8, base[1]+6, base[2]+4)
    elif style_key == "powder":
        base = (max(0, base[0]-4), max(0, base[1]-4), max(0, base[2]-3))
    return base

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
    _trace_log("01", "build_final_candidate_start", func="build_final_candidate",
               selected_style_key=(result or {}).get("selected_style_key"), style_key=(result or {}).get("style_key"),
               photo_filename=(photo_status or {}).get("filename") or ((result or {}).get("preview") or {}).get("before_filename",""))
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


def ensure_eyebrow_detection(candidate, style_key: str = ""):
    """اگر ROI/polygon/mask ابرو در candidate نیست، از روی عکس آن را تشخیص می‌دهد.

    style_key: برای ساخت Design Region بر اساس مدل انتخابی
    """
    _trace_log("03", "ensure_eyebrow_detection_start", func="ensure_eyebrow_detection",
               has_existing=bool((candidate or {}).get("eyebrow_detection") if isinstance(candidate, dict) else False),
               style_key=style_key)
    candidate = candidate if isinstance(candidate, dict) else {}
    src = _source_path(candidate)

    # Resolve style_key from candidate if not provided
    if not style_key:
        try:
            style_key = normalize_style_key(candidate.get("final_style") or candidate.get("selected_style") or "giso_suggested")
        except Exception:
            style_key = "giso_suggested"

    existing = candidate.get("eyebrow_detection")
    if isinstance(existing, dict) and existing.get("regions"):
        mask = existing.get("mask") if isinstance(existing.get("mask"), dict) else {}
        # Rebuild mask if missing or style changed (design region depends on style)
        existing_style = (mask.get("style_key") or existing.get("mask", {}).get("style_key") or "") if isinstance(existing, dict) else ""
        needs_rebuild = not (mask.get("ok") and mask.get("path")) or (existing_style and existing_style != style_key)
        if src and needs_rebuild:
            _trace_log("03", "ensure_eyebrow_detection_rebuild_mask", has_mask=bool(mask.get("ok")), existing_style=existing_style, new_style=style_key)
            existing = ensure_eyebrow_mask(src, existing, style_key=style_key, design_mode=True)
            candidate["eyebrow_detection"] = existing
        _trace_log("03", "ensure_eyebrow_detection_existing_ok", method=existing.get("method"), regions=len(existing.get("regions") or []), style_key=style_key)
        return existing
    if not src:
        _trace_log("03", "ensure_eyebrow_detection_no_source")
        return {}
    # اول سعی با تشخیص واقعی، اگر نشد با fallback نسبتی تا پیش‌نمایش قطع نشود
    try:
        detection = detect_eyebrow_regions(src, allow_fallback=False, style_key=style_key)
    except TypeError:
        detection = detect_eyebrow_regions(src, allow_fallback=False)
    _trace_log("03", "ensure_eyebrow_detection_first_try", ok=bool(detection.get("ok")) if isinstance(detection, dict) else False,
               method=detection.get("method") if isinstance(detection, dict) else "", style_key=style_key)
    if not (isinstance(detection, dict) and detection.get("regions")):
        # برای پیش‌نمایش راهنما، fallback مجاز است تا کاربر عکس خالی نبیند
        _trace_log("03", "ensure_eyebrow_detection_retry_fallback")
        try:
            detection = detect_eyebrow_regions(src, allow_fallback=True, style_key=style_key)
        except TypeError:
            detection = detect_eyebrow_regions(src, allow_fallback=True)
    if isinstance(detection, dict) and detection.get("regions"):
        _trace_log("04", "ensure_eyebrow_detection_build_mask", method=detection.get("method"), style_key=style_key)
        detection = ensure_eyebrow_mask(src, detection, style_key=style_key, design_mode=True)
    candidate["eyebrow_detection"] = detection
    _trace_log("03", "ensure_eyebrow_detection_done", method=detection.get("method") if isinstance(detection, dict) else "",
               ok=bool(detection.get("ok")) if isinstance(detection, dict) else False,
               mask_ok=bool((detection.get("mask") or {}).get("ok")) if isinstance(detection, dict) else False,
               style_key=style_key)
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
            design_polygon = region.get("design_polygon") if isinstance(region.get("design_polygon"), list) else []
            existing_polygon = region.get("existing_polygon") if isinstance(region.get("existing_polygon"), list) else []
            # Prefer design bbox for new architecture
            design_bbox = region.get("design_bbox") if isinstance(region.get("design_bbox"), dict) else {}
            if design_bbox:
                bx = int(design_bbox.get("x") or region.get("x") or 0)
                by = int(design_bbox.get("y") or region.get("y") or 0)
                bw = int(design_bbox.get("width") or region.get("width") or 0)
                bh = int(design_bbox.get("height") or region.get("height") or 0)
            else:
                bx = int(region.get("x") or 0)
                by = int(region.get("y") or 0)
                bw = int(region.get("width") or 0)
                bh = int(region.get("height") or 0)
            chunks.append(
                f"{region.get('side')}: existing_brow bbox x={int((region.get('existing_bbox') or {}).get('x') or bx)}, y={int((region.get('existing_bbox') or {}).get('y') or by)}, "
                f"w={int((region.get('existing_bbox') or {}).get('width') or bw)}, h={int((region.get('existing_bbox') or {}).get('height') or bh)}, "
                f"design_region bbox x={bx}, y={by}, w={bw}, h={bh}, "
                f"existing_points={len(existing_polygon) or len(polygon_points)}, design_points={len(design_polygon) or len(polygon_points)}, "
                f"style={mask.get('style_key') or candidate.get('final_style') or 'giso_suggested'}"
            )
        except Exception:
            continue
    method = detection.get("method") or "unknown"
    mask_text = ""
    if mask.get("ok"):
        mask_text = (
            f" Pixel eyebrow DESIGN mask available {mask.get('width') or image_w}x{mask.get('height') or image_h}, "
            f"polarity={mask.get('polarity') or 'white_edit_black_keep'}, "
            f"design_mode={mask.get('design_mode')}, style={mask.get('style_key')}, "
            f"expansion_ratio={mask.get('expansion_ratio')}, "
            f"coverage={mask.get('coverage_ratio')}."
        )
    return f"Detected eyebrow polygon regions on original image {image_w}x{image_h} using {method}: " + "; ".join(chunks) + mask_text


def _scaled_regions_for_image(candidate, image_w, image_h):
    try:
        style_key = normalize_style_key(candidate.get("final_style") or candidate.get("selected_style") or "giso_suggested")
    except Exception:
        style_key = "giso_suggested"
    detection = ensure_eyebrow_detection(candidate, style_key=style_key)
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
    """Draw realistic filled brow – no white halo, full coverage, natural.
    
    Fix for user image showing stitching/outline: now solid fill + subtle texture.
    """
    points = _brow_curve(cx, cy, length, arch, flip=flip)
    width = max(4, int(params["width"]))
    shade = float(params.get("shade") or 0)
    # Thicker base shape for full coverage
    base_thickness = max(width + 4, width * (1.35 + shade * 0.5))
    shape = _tapered_brow_shape(points, base_thickness)
    if shape:
        # Solid fill – high alpha for visible redesign, not faint
        # For powder: more solid, for microblading: slightly translucent to allow strokes
        if mode == "microblading":
            fill_alpha = int(color[3] * 0.72)
        elif mode == "powder":
            fill_alpha = int(color[3] * 0.88)
        else:
            fill_alpha = int(color[3] * 0.82)
        fill_alpha = max(110, min(230, fill_alpha))
        fill_color = color[:3] + (fill_alpha,)
        draw.polygon(shape, fill=fill_color)
    
    # For powder/combination: soft shading under
    if params.get("shade", 0) > 0.15 and mode in ("powder", "combination", "giso_suggested"):
        shade_width = max(width + 8, int(width * 1.9))
        shade_alpha = int(color[3] * params["shade"] * 0.65)
        shade_alpha = max(30, min(120, shade_alpha))
        shade_color = color[:3] + (shade_alpha,)
        draw.line(points, fill=shade_color, width=shade_width, joint="curve")
    
    # Main spine – slightly thinner, natural
    spine_width = max(2, int(width * 0.55))
    draw.line(points, fill=color, width=spine_width, joint="curve")

    stroke_count = int(params.get("strokes") or 0)
    if stroke_count <= 0:
        return
    # Strokes: only for microblading/combination, subtle and inside fill, not outline stitching
    if mode not in ("microblading", "combination", "giso_suggested"):
        # natural/powder: no visible stitching, just soft texture
        return
    for i in range(stroke_count):
        t = (i + 0.5) / stroke_count
        # Skip tail for combination front strokes
        if mode == "combination" and t > 0.68:
            continue
        # Powder: very sparse strokes
        if mode == "powder" and i % 4 != 0:
            continue
        x = cx - length / 2 + length * t
        if flip:
            x = cx + length / 2 - length * t
        y = cy - arch * math.sin(math.pi * t) + (t - 0.5) * arch * 0.26
        # More natural slant, shorter length
        slant = (-1 if flip else 1) * (arch * 0.28)
        stroke_len = max(5, length * 0.055)
        # Subtle stroke color – slightly darker than fill, low alpha
        stroke_alpha = min(190, int(color[3] * 0.85))
        stroke_color = (max(0, color[0]-8), max(0, color[1]-6), max(0, color[2]-4), stroke_alpha)
        draw.line(
            [(x - slant * 0.12, y + stroke_len * 0.28), (x + slant * 0.18, y - stroke_len * 0.52)],
            fill=stroke_color,
            width=max(1, int(width * 0.28)),
        )


def build_design_prompt(candidate):
    """پرامپت دقیق برای provider تصویر — بازطراحی واقعی ابرو داخل Design Region."""
    final_style_key = normalize_style_key(candidate.get("final_style"))
    style_label = candidate.get("final_label") or _style_label(final_style_key)
    model_label = candidate.get("selected_label") or style_label
    selected_style_key = normalize_style_key(candidate.get("selected_style") or final_style_key)
    change_key = candidate.get("change_key") or "very_natural"
    try:
        from giso.buti_ai.eyebrow.options import normalize_change_level
        change_key = normalize_change_level(change_key)
    except Exception:
        change_key = "very_natural"

    # New contracts – allow redesign inside Design Region, not just preserve
    # Key difference: we distinguish Existing Brow (customer's current) vs Design Region (editable area)
    STYLE_CONTRACTS = {
        "natural": (
            "STYLE CONTRACT: Natural soft eyebrow REDESIGN inside Design Region. "
            "You MAY slightly increase thickness (+20%), subtly lift arch (+3mm), refine tail, fill sparse gaps. "
            "Keep growth direction natural, preserve asymmetry gracefully, sparse soft front, natural density, tapered tail. "
            "Design Region is larger than existing brow and defines where you can draw. "
            "MUST be photorealistic filled brow, NO outline only, NO stitching lines, NO mapping marks, NO white background, NO powder fill, NO skin tint, NO shadow outside Design Region, NO halo, NO eye/lid change."
        ),
        "microblading": (
            "STYLE CONTRACT: Microblading REDESIGN – fine individual hair-stroke technique inside Design Region, PHOTOREALISTIC filled. "
            "You MAY increase thickness (+25%), lift arch (+3-4mm), extend tail (+6mm), fill sparse areas with realistic hair strokes that look like real hairs, not outline. "
            "Transfer ONLY hair-stroke technique from reference, not its face/position. "
            "Individual hairs, natural direction, medium density, tapered tail, MUST look like real eyebrow hairs, NOT stitching, NOT outline with ticks, NOT mapping. "
            "Design Region allows drawing beyond existing hair but clipped to safe face limits. "
            "NO powder fill, NO skin tint, NO shadow outside Design Region, NO eyelid makeup, NO halo, NO white background."
        ),
        "powder": (
            "STYLE CONTRACT: Powder ombre REDESIGN inside Design Region, PHOTOREALISTIC solid fill. "
            "You MAY increase thickness (+30%), create soft gradient powder shading, "
            "lightest at front, gradually deeper through body/tail, fill and shape inside Design Region as solid natural brow. "
            "Design Region is larger than existing brow, giving space for new shape. "
            "Preserve overall position but allow arch/tail refinement. "
            "MUST be filled natural brow, NO outline only, NO stitching, NO mapping lines, NO white halo, NO eyelid shadow, NO facial retouching, NO blocky fill."
        ),
        "combination": (
            "STYLE CONTRACT: Combination REDESIGN – strokes front + powder tail inside Design Region, PHOTOREALISTIC. "
            "You MAY increase thickness (+25-30%), lift arch, extend tail, "
            "fine natural hairstrokes at front plus soft translucent powder shading in tail, all inside Design Region as realistic filled brow. "
            "Design Region defines editable area, larger than existing brow but safe from eye. "
            "Keep natural growth direction, fill gaps, balance density. MUST be realistic, NOT outline with stitching, NOT mapping. "
            "NO pigment outside Design Region, NO under-brow shadow, NO eyelid makeup, NEVER blocky, NO halo, NO white background."
        ),
        "giso_suggested": (
            "STYLE CONTRACT: Balanced natural REDESIGN inside Design Region. "
            "You MAY moderately increase thickness (+15-20%), refine arch and tail, fill sparse areas, "
            "balanced density, natural finish, wearable salon result. "
            "Design Region is controlled expansion of existing brow, clipped to avoid eye/lid. "
            "NO heavy fill, NO skin tint, NO halo, NO change outside Design Region."
        ),
    }
    contract = STYLE_CONTRACTS.get(selected_style_key, STYLE_CONTRACTS.get(final_style_key, ""))

    # Change level modifiers
    CHANGE_MODIFIERS = {
        "very_natural": "CHANGE LEVEL: very_natural – subtle, keep close to original, minimal expansion, natural finish.",
        "medium": "CHANGE LEVEL: medium – noticeable improvement, moderate thickness/arch/tail change, balanced.",
        "clear": "CHANGE LEVEL: clear – obvious transformation, fuller, more defined arch and tail, but still realistic and wearable.",
    }
    change_modifier = CHANGE_MODIFIERS.get(change_key, CHANGE_MODIFIERS["very_natural"])

    STYLE_ENGLISH = {
        "natural": "natural soft eyebrow redesign, slightly thicker, refined arch",
        "microblading": "microblading fine hair strokes redesign, increased thickness, extended tail, filled gaps",
        "powder": "powder ombre redesign, fuller shading, soft gradient, refined shape",
        "combination": "combination redesign – hair strokes front + powder tail, fuller shape",
        "giso_suggested": "balanced natural redesign, moderate improvement",
    }
    style_en = STYLE_ENGLISH.get(selected_style_key, STYLE_ENGLISH.get(final_style_key, ""))

    region_text = _eyebrow_region_text(candidate)

    # SCOPE جدید: اجازه بازطراحی داخل Design Region، نه فقط حفظ
    # برای سازگاری با تست‌های قدیمی که عبارت descriptive metadata را چک می‌کنند، آن را حفظ می‌کنیم
    return (
        f"STYLE EDITING TASK — REDESIGN eyebrows inside DESIGN REGION on IMAGE 0 (customer photo). "
        f"Prompt text and ROI coordinates are only descriptive metadata, mask defines editable pixels. "
        f"EXISTING BROW = customer's current brow (tight polygon). DESIGN REGION = larger controlled area where you MUST draw new brow (expanded polygon, safe from eye). "
        f"Apply «{selected_style_key} ({style_en}) Label:{model_label}» onto IMAGE 0. IMAGE 1 if present is technique reference ONLY. "
        f"{contract} {change_modifier} "
        f"SCOPE: You MUST redesign BOTH eyebrows INSIDE Design Region as PHOTOREALISTIC FILLED natural brows; you MAY change thickness, arch, tail, density, fill gaps, but stay INSIDE Design Region bbox. MUST NOT be outline only, MUST NOT be stitching lines with ticks, MUST NOT be mapping marks, MUST NOT have white background inside mask. "
        f"Outside Design Region: ABSOLUTELY NO pigment, NO shadow, NO blur, NO smoothing, NO relighting, NO makeup, NO eye/eyelid/lash change, NO skin/hair/hijab/background change, NO white-balance shift. "
        f"Inside Design Region: create photorealistic, salon-quality FILLED brow with chosen style, realistic hair strokes or powder shading, natural dark brown/black from customer's own brow undertone (never pure white, never blonde, never fixed HEX). NO outline only, NO stitching. "
        f"IMAGE 1 is technique-only: never copy its face, skin, brow placement, lighting, color cast or background — transfer only stroke/shading technique, density and finish. "
        f"GOAL: Redesign eyebrow as realistic filled brow, not outline with stitching, not draw a few strokes over old eyebrow. The result must show clear change in thickness/form/arch/tail/density/style inside Design Region as natural filled brow. "
        f"FINAL: SAME original photograph after professional brow treatment, not a new face. Realistic, wearable, symmetric, NO white halo. "
        f"Location: {region_text} "
        f"Real eyebrow location: {region_text}. Edit ONLY the two eyebrow regions inside mask; keep everything else identical. "
        f"Selected eyebrow model: {model_label} Current eyebrow notes: design region expanded per style, must be filled natural brow."
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
        skin_rgb = _sample_skin_color(base, regions)
        brow_rgb = _brow_color_for_skin(skin_rgb, final_style)
        color = (brow_rgb[0], brow_rgb[1], brow_rgb[2], alpha)
        mode = "combination" if final_style in ("combination", "giso_suggested") else final_style

        for idx, region in enumerate(regions[:2]):
            # Fill almost entire design region to fix "mask area small" – use full width
            brow_len = max(48.0, float(region.get("width") or 0) * 1.02)
            arch = max(9.0, float(region.get("height") or 0) * 0.48)
            cx = float(region.get("x") or 0) + float(region.get("width") or 0) / 2.0
            cy = float(region.get("y") or 0) + float(region.get("height") or 0) * 0.55
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
                # Use NEAREST for binary mask to avoid feathered gray edges (step 6)
                real_mask = Image.open(mask_path).convert("L").resize((w, h), Image.Resampling.NEAREST if hasattr(Image, "Resampling") else Image.NEAREST)
                real_mask = real_mask.point(lambda px: 255 if int(px) >= 96 else 0)
                # For python guided, keep design region visible – no MaxFilter needed as design region already larger
                guide_mask = ImageChops.lighter(guide_mask, real_mask)
            # Slight feather for natural transition in python guided, but not for inpainting binary mask
            guide_mask = guide_mask.filter(ImageFilter.GaussianBlur(radius=0.6))
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
