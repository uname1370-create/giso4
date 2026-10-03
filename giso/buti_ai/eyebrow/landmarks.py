# -*- coding: utf-8 -*-
"""تشخیص محدوده ابرو و ساخت mask واقعی برای طراحی نهایی آینه ابرو.

خروجی این ماژول علاوه بر ROI قدیمی، polygon هر ابرو و یک pixel mask واقعی
(تصویر خاکستری PNG: سفید=ناحیه قابل ویرایش، سیاه=ناحیه محفوظ) می‌سازد تا
providerهای inpainting بتوانند فقط خود ابرو را تغییر دهند. وابستگی سنگین اجباری
نیست: اگر MediaPipe نصب باشد از FaceMesh استفاده می‌شود؛ در غیر این صورت مسیرهای
fallback تصویرمحور با confidence پایین‌تر حفظ می‌شوند. fallback نسبتی فقط با
درخواست صریح فعال است و هرگز به‌عنوان detection واقعی علامت‌گذاری نمی‌شود.

Design Region: برای بازطراحی واقعی ابرو، mask باید بزرگتر از ابروی موجود باشد
تا ضخامت/قوس/دم قابل تغییر باشد. این ماژول existing_bbox (تنگ، ابروی فعلی) و
design_bbox (گسترده‌تر، قابل ویرایش بر اساس style) را می‌سازد.
"""
from __future__ import annotations

import logging
import os
from typing import Any, Dict, Iterable, List, Optional, Tuple

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


# FaceMesh indices – closed loop: upper ridge outer->inner, then lower ridge inner->outer
_FACE_MESH_LEFT_BROW = (70, 63, 105, 66, 107, 55, 65, 52, 53, 46)
_FACE_MESH_RIGHT_BROW = (300, 293, 334, 296, 336, 285, 295, 282, 283, 276)

MASK_EDIT_VALUE = 255
MASK_KEEP_VALUE = 0
MASK_POLARITY = "white_edit_black_keep"

# Design Region expansion factors per style – tuned to avoid eye/eyelid intrusion but ensure full brow coverage
# Increased vs previous to fix "mask area small" issue – user image showed partial brow
_DESIGN_EXPANSION = {
    "natural": {"top": 0.45, "bottom": 0.42, "left": 0.18, "right": 0.20, "tail_extra": 0.12},
    "microblading": {"top": 0.68, "bottom": 0.55, "left": 0.22, "right": 0.26, "tail_extra": 0.20},
    "powder": {"top": 0.75, "bottom": 0.68, "left": 0.26, "right": 0.28, "tail_extra": 0.16},
    "combination": {"top": 0.72, "bottom": 0.62, "left": 0.24, "right": 0.26, "tail_extra": 0.18},
    "giso_suggested": {"top": 0.55, "bottom": 0.48, "left": 0.20, "right": 0.22, "tail_extra": 0.14},
}

def _design_expansion_for_style(style_key: str) -> Dict[str, float]:
    key = str(style_key or "giso_suggested").strip().lower()
    return dict(_DESIGN_EXPANSION.get(key, _DESIGN_EXPANSION["giso_suggested"]))


def _clamp_design_bbox(x: float, y: float, w: float, h: float, image_w: int, image_h: int, is_precise: bool = True) -> Tuple[float, float, float, float]:
    """Clamp expanded bbox to safe face limits – never enter eye/eyelid/hijab."""
    min_x_ratio = 0.01
    max_x_ratio = 0.99
    min_y_ratio = 0.04 if is_precise else 0.06
    max_y_ratio = 0.58 if is_precise else 0.55
    max_w_ratio = 0.58 if is_precise else 0.52
    max_h_ratio = 0.48 if is_precise else 0.42

    x = max(image_w * min_x_ratio, x)
    y = max(image_h * min_y_ratio, y)
    if x + w > image_w * max_x_ratio:
        w = image_w * max_x_ratio - x
    if y + h > image_h * max_y_ratio:
        h = image_h * max_y_ratio - y

    w = max(8.0, min(float(w), image_w * max_w_ratio))
    h = max(8.0, min(float(h), image_h * max_h_ratio))

    x = max(image_w * min_x_ratio, min(x, image_w * max_x_ratio - w))
    y = max(image_h * min_y_ratio, min(y, image_h * max_y_ratio - h))

    return float(x), float(y), float(w), float(h)


def _build_design_region_from_existing(region: Dict[str, Any], image_w: int, image_h: int, style_key: str, side: str) -> Dict[str, Any]:
    """Build Eyebrow Design Region bbox from existing tight region + style."""
    exp = _design_expansion_for_style(style_key)
    x = float(region.get("x") or 0)
    y = float(region.get("y") or 0)
    w = max(1.0, float(region.get("width") or 1))
    h = max(1.0, float(region.get("height") or 1))

    top_exp = h * float(exp.get("top") or 0.32)
    bottom_exp = h * float(exp.get("bottom") or 0.28)
    left_exp = w * float(exp.get("left") or 0.12)
    right_exp = w * float(exp.get("right") or 0.14)
    tail_extra = w * float(exp.get("tail_extra") or 0.08)

    if side == "left":
        left_exp += tail_extra * 0.7
        right_exp += tail_extra * 0.3
    else:
        left_exp += tail_extra * 0.3
        right_exp += tail_extra * 0.7

    new_x = x - left_exp
    new_y = y - top_exp
    new_w = w + left_exp + right_exp
    new_h = h + top_exp + bottom_exp

    is_precise = "precise" in str(region.get("polygon_source") or "") or "tight" in str(region.get("polygon_source") or "")
    new_x, new_y, new_w, new_h = _clamp_design_bbox(new_x, new_y, new_w, new_h, image_w, image_h, is_precise=is_precise)

    return {
        "x": float(new_x),
        "y": float(new_y),
        "width": float(new_w),
        "height": float(new_h),
        "expansion": exp,
        "style_key": style_key,
    }


def _build_design_polygon_from_region(design_bbox: Dict[str, Any], image_w: int, image_h: int) -> List[List[int]]:
    """Build curved leaf polygon inside design bbox – larger than existing brow."""
    return _brow_polygon_from_box(design_bbox, image_w, image_h)


def _image_size(image_path: str) -> Tuple[int, int]:
    try:
        from PIL import Image
        with Image.open(image_path) as image:
            return image.size
    except Exception:
        return 0, 0


def _clamp_point(x: float, y: float, image_w: int, image_h: int) -> List[int]:
    max_x = max(0, int(image_w) - 1)
    max_y = max(0, int(image_h) - 1)
    return [int(round(max(0.0, min(float(max_x), float(x))))), int(round(max(0.0, min(float(max_y), float(y)))))]


def _polygon_area(points: Iterable[Iterable[Any]]) -> float:
    pts: List[Tuple[float, float]] = []
    for item in points or []:
        try:
            x, y = item  # type: ignore[misc]
            pts.append((float(x), float(y)))
        except Exception:
            continue
    if len(pts) < 3:
        return 0.0
    area = 0.0
    for idx, (x1, y1) in enumerate(pts):
        x2, y2 = pts[(idx + 1) % len(pts)]
        area += x1 * y2 - x2 * y1
    return abs(area) / 2.0


def _brow_polygon_from_box(region: Dict[str, Any], image_w: int, image_h: int) -> List[List[int]]:
    """ساخت polygon خمیده و باریک داخل ROI؛ عمداً rectangle نیست."""
    x = float(region.get("x") or 0)
    y = float(region.get("y") or 0)
    w = max(1.0, float(region.get("width") or 1))
    h = max(1.0, float(region.get("height") or 1))
    raw = [
        (x + w * 0.03, y + h * 0.58),
        (x + w * 0.11, y + h * 0.40),
        (x + w * 0.25, y + h * 0.27),
        (x + w * 0.46, y + h * 0.18),
        (x + w * 0.67, y + h * 0.22),
        (x + w * 0.86, y + h * 0.34),
        (x + w * 0.98, y + h * 0.48),
        (x + w * 0.91, y + h * 0.62),
        (x + w * 0.70, y + h * 0.72),
        (x + w * 0.47, y + h * 0.78),
        (x + w * 0.23, y + h * 0.74),
        (x + w * 0.07, y + h * 0.66),
    ]
    return [_clamp_point(px, py, image_w, image_h) for px, py in raw]


def _polygon_from_points(points: Iterable[Tuple[float, float]], region: Dict[str, Any], image_w: int, image_h: int) -> List[List[int]]:
    """ساخت polygon امن از landmarkهای FaceMesh؛ در صورت ناکافی بودن از ROI خمیده استفاده می‌شود."""
    pts = [(float(x), float(y)) for x, y in points or []]
    if len(pts) < 4:
        return _brow_polygon_from_box(region, image_w, image_h)

    min_x = min(x for x, _ in pts)
    max_x = max(x for x, _ in pts)
    min_y = min(y for _, y in pts)
    max_y = max(y for _, y in pts)
    bw = max(8.0, max_x - min_x)
    bh = max(4.0, max_y - min_y)
    top = min_y - max(3.0, bh * 0.55)
    bottom = max_y + max(4.0, bh * 0.9)
    left = min_x - bw * 0.16
    right = max_x + bw * 0.16
    pseudo_region = {
        "x": left,
        "y": top,
        "width": right - left,
        "height": bottom - top,
    }
    return _brow_polygon_from_box(pseudo_region, image_w, image_h)


def _ensure_region_polygon(region: Dict[str, Any], image_w: int, image_h: int) -> Dict[str, Any]:
    polygon = region.get("polygon")
    clean_polygon: List[List[int]] = []
    if isinstance(polygon, list):
        for point in polygon:
            try:
                px, py = point  # type: ignore[misc]
                clean_polygon.append(_clamp_point(float(px), float(py), image_w, image_h))
            except Exception:
                continue
    if len(clean_polygon) < 4 or _polygon_area(clean_polygon) <= 0:
        clean_polygon = _brow_polygon_from_box(region, image_w, image_h)
        region["polygon_source"] = region.get("polygon_source") or "roi_curved_polygon"
    region["polygon"] = clean_polygon
    bbox_area = max(1.0, float(region.get("width") or 1) * float(region.get("height") or 1))
    region["polygon_area"] = round(_polygon_area(clean_polygon), 2)
    region["mask_shape"] = "polygon"
    region["is_rectangle_mask"] = False
    region["polygon_to_bbox_ratio"] = round(min(1.0, float(region["polygon_area"]) / bbox_area), 4)
    return region


def _box(x: float, y: float, w: float, h: float, image_w: int, image_h: int, side: str,
         confidence: float, source: str) -> Dict[str, Any]:
    x = max(0.0, min(float(image_w - 1), float(x))) if image_w > 1 else 0.0
    y = max(0.0, min(float(image_h - 1), float(y))) if image_h > 1 else 0.0
    w = max(1.0, min(float(image_w) - x, float(w))) if image_w > 0 else max(1.0, float(w))
    h = max(1.0, min(float(image_h) - y, float(h))) if image_h > 0 else max(1.0, float(h))
    region = {
        "side": side,
        "x": int(round(x)),
        "y": int(round(y)),
        "width": int(round(w)),
        "height": int(round(h)),
        "cx": int(round(x + w / 2.0)),
        "cy": int(round(y + h / 2.0)),
        "confidence": round(float(confidence), 3),
        "source": source,
    }
    return _ensure_region_polygon(region, image_w, image_h)


def _precise_eyebrow_polygon_from_landmarks(
    points: Iterable[Tuple[float, float]],
    image_w: int,
    image_h: int,
    margin_px: float = 0.0,
    margin_percent: float = 0.0,
) -> List[List[int]]:
    """ساخت polygon دقیق فقط از landmarkهای واقعی ابرو — بدون حاشیه بزرگ."""
    pts = [(float(x), float(y)) for x, y in points or []]
    if len(pts) < 3:
        return []
    import math

    def _area(poly):
        return _polygon_area(poly)

    def _has_intersection(poly):
        def _orient(a, b, c):
            v = (b[1] - a[1]) * (c[0] - b[0]) - (b[0] - a[0]) * (c[1] - b[1])
            if v == 0:
                return 0
            return 1 if v > 0 else 2

        def _intersect(p1, p2, q1, q2):
            o1 = _orient(p1, p2, q1)
            o2 = _orient(p1, p2, q2)
            o3 = _orient(q1, q2, p1)
            o4 = _orient(q1, q2, p2)
            return o1 != o2 and o3 != o4

        n = len(poly)
        if n < 4:
            return False
        for i in range(n):
            for j in range(i + 2, n):
                if j == n - 1 and i == 0:
                    continue
                if _intersect(poly[i], poly[(i + 1) % n], poly[j], poly[(j + 1) % n]):
                    return True
        return False

    cx = sum(x for x, y in pts) / len(pts)
    cy = sum(y for x, y in pts) / len(pts)

    def _angle(p):
        return math.atan2(p[1] - cy, p[0] - cx)

    candidates: List[List[Tuple[float, float]]] = []
    candidates.append(pts)

    if _has_intersection(pts) or _area(pts) < 8.0:
        candidates.append(sorted(pts, key=_angle))
        if len(pts) >= 10:
            upper = pts[:5]
            lower = pts[5:10]
            candidates.append(upper + lower)
            candidates.append(upper + list(reversed(lower)))
            candidates.append(list(reversed(upper)) + lower)
            candidates.append(list(reversed(upper)) + list(reversed(lower)))
            upper_sorted = sorted(upper, key=lambda p: p[0])
            lower_sorted = sorted(lower, key=lambda p: p[0])
            candidates.append(upper_sorted + list(reversed(lower_sorted)))

    best = None
    best_area = -1.0
    for cand in candidates:
        if len(cand) < 3:
            continue
        if _has_intersection(cand):
            continue
        a = _area(cand)
        if a < 8.0:
            continue
        if best is None:
            best = cand
            best_area = a
        elif cand is not pts and a > best_area:
            best_area = a
            best = cand
        if best is pts:
            break

    if best is None:
        best = sorted(pts, key=_angle)

    if margin_px == 0 and margin_percent == 0:
        result = [_clamp_point(x, y, image_w, image_h) for x, y in best]
    else:
        expanded: List[List[int]] = []
        for x, y in best:
            dx = x - cx
            dy = y - cy
            dist = math.hypot(dx, dy) or 1.0
            scale = 1.0 + margin_percent + (margin_px / dist)
            nx = cx + dx * scale
            ny = cy + dy * scale
            expanded.append(_clamp_point(nx, ny, image_w, image_h))
        result = expanded

    if len(result) < 3 or _polygon_area(result) < 8.0:
        return [_clamp_point(x, y, image_w, image_h) for x, y in best]
    return result


def _box_from_points_fallback(points: Iterable[Tuple[float, float]], image_w: int, image_h: int,
                              side: str, source: str, confidence: float) -> Dict[str, Any]:
    pts = [(float(x), float(y)) for x, y in points]
    if not pts:
        return {}
    min_x = min(x for x, _ in pts)
    max_x = max(x for x, _ in pts)
    min_y = min(y for _, y in pts)
    max_y = max(y for _, y in pts)
    bw = max(12.0, max_x - min_x)
    bh = max(8.0, max_y - min_y)
    expand_x = bw * 0.28
    expand_top = max(6.0, bh * 1.0)
    expand_bottom = max(7.0, bh * 1.15)
    region = _box(
        min_x - expand_x,
        min_y - expand_top,
        bw + expand_x * 2,
        bh + expand_top + expand_bottom,
        image_w,
        image_h,
        side,
        confidence,
        source,
    )
    region["landmark_points"] = [_clamp_point(px, py, image_w, image_h) for px, py in pts]
    region["polygon"] = _polygon_from_points(pts, region, image_w, image_h)
    region["polygon_source"] = "facemesh_landmark_band"
    return _ensure_region_polygon(region, image_w, image_h)


def _box_from_points_precise(
    points: Iterable[Tuple[float, float]],
    image_w: int,
    image_h: int,
    side: str,
    source: str,
    confidence: float,
) -> Dict[str, Any]:
    """نسخه دقیق برای MediaPipe — بدون حاشیه بزرگ، فقط polygon واقعی."""
    pts = [(float(x), float(y)) for x, y in points or []]
    if not pts:
        return {}
    precise_polygon = _precise_eyebrow_polygon_from_landmarks(
        pts, image_w, image_h, margin_px=0.0, margin_percent=0.0
    )
    if not precise_polygon:
        return _box_from_points_fallback(pts, image_w, image_h, side, source, confidence)

    min_x = min(p[0] for p in precise_polygon)
    max_x = max(p[0] for p in precise_polygon)
    min_y = min(p[1] for p in precise_polygon)
    max_y = max(p[1] for p in precise_polygon)
    bw = max(1.0, float(max_x - min_x))
    bh = max(1.0, float(max_y - min_y))

    region = {
        "side": side,
        "x": int(round(min_x)),
        "y": int(round(min_y)),
        "width": int(round(bw)),
        "height": int(round(bh)),
        "cx": int(round(min_x + bw / 2.0)),
        "cy": int(round(min_y + bh / 2.0)),
        "confidence": round(float(confidence), 3),
        "source": source,
        "landmark_points": [_clamp_point(px, py, image_w, image_h) for px, py in pts],
        "polygon": precise_polygon,
        "polygon_source": "mediapipe_precise_tight",
        "existing_bbox": {
            "x": int(round(min_x)),
            "y": int(round(min_y)),
            "width": int(round(bw)),
            "height": int(round(bh)),
        },
        "existing_polygon": precise_polygon,
        "existing_mask_pixel_count": 0,
    }
    return _ensure_region_polygon(region, image_w, image_h)


def _box_from_points(points: Iterable[Tuple[float, float]], image_w: int, image_h: int,
                     side: str, source: str, confidence: float) -> Dict[str, Any]:
    # Use precise version for mediapipe sources
    if "mediapipe" in str(source):
        return _box_from_points_precise(points, image_w, image_h, side, source, confidence)
    return _box_from_points_fallback(points, image_w, image_h, side, source, confidence)


def _method_confidence_label(method: str) -> str:
    if method == "mediapipe_face_mesh":
        return "high"
    if method == "opencv_haar_eye":
        return "medium_low"
    if method == "dark_pixel_band":
        return "low"
    if method == "proportional_fallback":
        return "fallback_only"
    return "unknown"


def _ok(method: str, image_w: int, image_h: int, regions: List[Dict[str, Any]], confidence: float) -> Dict[str, Any]:
    ordered = sorted(regions, key=lambda r: r.get("cx", 0))
    for idx, region in enumerate(ordered):
        region["side"] = "left" if idx == 0 else "right"
        _ensure_region_polygon(region, image_w, image_h)
    fallback_only = method == "proportional_fallback"
    return {
        "ok": len(ordered) >= 2,
        "method": method,
        "confidence": round(float(confidence), 3),
        "confidence_label": _method_confidence_label(method),
        "detection_reliable": not fallback_only and len(ordered) >= 2,
        "is_fallback": fallback_only,
        "image_width": int(image_w),
        "image_height": int(image_h),
        "regions": ordered[:2],
        "mask": {"ok": False, "reason": "not_generated"},
        "mask_width": 0,
        "mask_height": 0,
        "mask_path": "",
    }


def ensure_eyebrow_mask(image_path: str, detection: Optional[Dict[str, Any]] = None,
                        output_path: str = "", style_key: str = "giso_suggested",
                        design_mode: bool = True) -> Dict[str, Any]:
    """برای detection موجود یک PNG mask واقعی و قابل ارسال به provider می‌سازد.

    design_mode=True: mask بر اساس Design Region (بزرگتر از ابروی موجود) ساخته می‌شود
    تا ضخامت/قوس/دم قابل تغییر باشد. existing_bbox/polygon همچنان حفظ می‌شود برای
    گزارش و validation.
    style_key: مدل انتخابی برای تعیین میزان expansion
    """
    detection = dict(detection or {})
    image_w = int(detection.get("image_width") or 0)
    image_h = int(detection.get("image_height") or 0)
    if not image_w or not image_h:
        image_w, image_h = _image_size(image_path)
        detection["image_width"] = int(image_w)
        detection["image_height"] = int(image_h)
    regions = detection.get("regions") if isinstance(detection.get("regions"), list) else []
    if not image_w or not image_h or len(regions) < 2:
        detection["mask"] = {"ok": False, "reason": "missing_regions", "width": int(image_w), "height": int(image_h)}
        detection["mask_width"] = int(image_w or 0)
        detection["mask_height"] = int(image_h or 0)
        detection["mask_path"] = ""
        return detection

    try:
        from PIL import Image, ImageDraw

        mask = Image.new("L", (image_w, image_h), MASK_KEEP_VALUE)
        draw = ImageDraw.Draw(mask)
        total_pixels = 0
        updated_regions: List[Dict[str, Any]] = []
        for raw_region in regions[:2]:
            region = dict(raw_region or {})
            # Preserve existing tight region for reporting
            existing_bbox = region.get("existing_bbox")
            existing_polygon = region.get("existing_polygon")
            if not existing_bbox:
                existing_bbox = {
                    "x": int(region.get("x") or 0),
                    "y": int(region.get("y") or 0),
                    "width": int(region.get("width") or 0),
                    "height": int(region.get("height") or 0),
                }
                region["existing_bbox"] = existing_bbox
            if not existing_polygon:
                # current polygon is existing
                ep = region.get("polygon") or []
                region["existing_polygon"] = ep
                existing_polygon = ep

            side = str(region.get("side") or "left")

            # Build design region
            if design_mode:
                try:
                    design_bbox_dict = _build_design_region_from_existing(
                        {"x": float(existing_bbox.get("x") or region.get("x") or 0),
                         "y": float(existing_bbox.get("y") or region.get("y") or 0),
                         "width": float(existing_bbox.get("width") or region.get("width") or 1),
                         "height": float(existing_bbox.get("height") or region.get("height") or 1),
                         "polygon_source": region.get("polygon_source") or ""},
                        image_w, image_h, style_key, side
                    )
                    design_polygon = _build_design_polygon_from_region(design_bbox_dict, image_w, image_h)
                    region["design_bbox"] = {
                        "x": int(round(design_bbox_dict["x"])),
                        "y": int(round(design_bbox_dict["y"])),
                        "width": int(round(design_bbox_dict["width"])),
                        "height": int(round(design_bbox_dict["height"])),
                        "expansion": design_bbox_dict.get("expansion"),
                        "style_key": style_key,
                    }
                    region["design_polygon"] = design_polygon
                    region["design_expansion"] = design_bbox_dict.get("expansion")
                    region["polygon"] = design_polygon
                    region["x"] = region["design_bbox"]["x"]
                    region["y"] = region["design_bbox"]["y"]
                    region["width"] = region["design_bbox"]["width"]
                    region["height"] = region["design_bbox"]["height"]
                    region["cx"] = int(round(region["x"] + region["width"] / 2.0))
                    region["cy"] = int(round(region["y"] + region["height"] / 2.0))
                    region["polygon_source"] = f"{region.get('polygon_source') or 'mediapipe'}_design_{style_key}"
                    polygon_for_mask = [tuple(p) for p in design_polygon]
                except Exception as de:
                    _trace_log("04", "design_region_failed_fallback_tight", error=str(de)[:120], side=side)
                    polygon_for_mask = [tuple(p) for p in (existing_polygon or region.get("polygon") or [])]
                    region["design_polygon"] = [list(p) for p in polygon_for_mask]
                    region["design_bbox"] = region["existing_bbox"]
            else:
                polygon_for_mask = [tuple(p) for p in (region.get("polygon") or [])]

            # Ensure polygon valid
            region = _ensure_region_polygon(region, image_w, image_h)
            if design_mode:
                # _ensure_region_polygon may overwrite polygon with roi_curved – restore design if needed
                # but keep validation that polygon is valid
                pass

            polygon = [tuple(point) for point in polygon_for_mask]
            if len(polygon) < 4:
                continue
            region_mask = Image.new("L", (image_w, image_h), MASK_KEEP_VALUE)
            region_draw = ImageDraw.Draw(region_mask)
            region_draw.polygon(polygon, fill=MASK_EDIT_VALUE)
            pixel_count = sum(1 for px in region_mask.getdata() if px > 0)
            region["mask_pixel_count"] = int(pixel_count)
            # existing count for comparison
            try:
                existing_mask = Image.new("L", (image_w, image_h), MASK_KEEP_VALUE)
                existing_draw = ImageDraw.Draw(existing_mask)
                ex_poly = [tuple(p) for p in (existing_polygon or [])]
                if len(ex_poly) >= 4:
                    existing_draw.polygon(ex_poly, fill=MASK_EDIT_VALUE)
                    region["existing_mask_pixel_count"] = sum(1 for px in existing_mask.getdata() if px > 0)
            except Exception:
                region["existing_mask_pixel_count"] = 0
            total_pixels += int(pixel_count)
            draw.polygon(polygon, fill=MASK_EDIT_VALUE)
            updated_regions.append(region)

        if len(updated_regions) < 2 or total_pixels <= 0:
            detection["mask"] = {"ok": False, "reason": "empty_polygon_mask", "width": int(image_w), "height": int(image_h)}
            detection["regions"] = updated_regions
            detection["mask_width"] = int(image_w)
            detection["mask_height"] = int(image_h)
            detection["mask_path"] = ""
            return detection

        if output_path:
            mask_path = os.path.abspath(output_path)
        else:
            base_dir = os.path.dirname(os.path.abspath(image_path)) or os.getcwd()
            stem = os.path.splitext(os.path.basename(str(image_path or "eyebrow")))[0] or "eyebrow"
            mask_dir = os.path.join(base_dir, "masks")
            os.makedirs(mask_dir, exist_ok=True)
            mask_path = os.path.join(mask_dir, f"{stem}_eyebrow_mask_{style_key}.png")
        os.makedirs(os.path.dirname(mask_path), exist_ok=True)
        # Ensure binary mask: 0 or 255 only
        mask = mask.point(lambda px: 255 if int(px) >= 128 else 0)
        mask.save(mask_path, "PNG", optimize=True)

        union_pixels = sum(1 for px in mask.getdata() if px > 0)
        bbox_area_sum = sum(max(1, int(r.get("width") or 1) * int(r.get("height") or 1)) for r in updated_regions)
        existing_pixels_sum = sum(int(r.get("existing_mask_pixel_count") or 0) for r in updated_regions)
        expansion_ratio = round(float(union_pixels) / max(1.0, float(existing_pixels_sum)), 3) if existing_pixels_sum > 0 else 1.0
        fallback_only = str(detection.get("method") or "") == "proportional_fallback" or bool(detection.get("is_fallback"))
        detection["regions"] = updated_regions
        detection["mask"] = {
            "ok": True,
            "kind": "eyebrow_pixel_polygon_mask",
            "format": "png_luminance",
            "path": mask_path,
            "width": int(image_w),
            "height": int(image_h),
            "polarity": MASK_POLARITY,
            "edit_value": MASK_EDIT_VALUE,
            "keep_value": MASK_KEEP_VALUE,
            "coverage_ratio": round(float(union_pixels) / float(max(1, image_w * image_h)), 6),
            "pixel_count": int(union_pixels),
            "bbox_area_sum": int(bbox_area_sum),
            "existing_pixel_count": int(existing_pixels_sum),
            "expansion_ratio": expansion_ratio,
            "is_rectangle_mask": False,
            "real_mask": not fallback_only,
            "is_fallback": fallback_only,
            "design_mode": bool(design_mode),
            "style_key": str(style_key),
        }
        detection["mask_width"] = int(image_w)
        detection["mask_height"] = int(image_h)
        detection["mask_path"] = mask_path
        detection["has_real_mask"] = not fallback_only
        _trace_log("04", "ensure_eyebrow_mask_done", ok=True, design_mode=design_mode, style_key=style_key,
                   coverage=detection["mask"]["coverage_ratio"], expansion=expansion_ratio, method=detection.get("method"))
        return detection
    except Exception as exc:
        _trace_log("04", "ensure_eyebrow_mask_failed", error=str(exc)[:200])
        detection["mask"] = {
            "ok": False,
            "reason": "mask_generation_failed",
            "error": str(exc)[:120],
            "width": int(image_w),
            "height": int(image_h),
        }
        detection["mask_width"] = int(image_w)
        detection["mask_height"] = int(image_h)
        detection["mask_path"] = ""
        return detection


def _detect_with_mediapipe(image_path: str, style_key: str = "giso_suggested", design_mode: bool = True) -> Optional[Dict[str, Any]]:
    try:
        from PIL import Image
        import mediapipe as mp  # type: ignore
        import numpy as np  # type: ignore
    except Exception:
        return None

    try:
        with Image.open(image_path) as image:
            image = image.convert("RGB")
            image_w, image_h = image.size
            array = np.asarray(image)
        with mp.solutions.face_mesh.FaceMesh(
            static_image_mode=True,
            max_num_faces=1,
            refine_landmarks=True,
            min_detection_confidence=0.5,
        ) as face_mesh:
            results = face_mesh.process(array)
        if not results.multi_face_landmarks:
            return None
        landmarks = results.multi_face_landmarks[0].landmark

        def points(indices: Iterable[int]) -> List[Tuple[float, float]]:
            pts: List[Tuple[float, float]] = []
            for idx in indices:
                if idx >= len(landmarks):
                    continue
                lm = landmarks[idx]
                pts.append((lm.x * image_w, lm.y * image_h))
            return pts

        regions = [
            _box_from_points(points(_FACE_MESH_LEFT_BROW), image_w, image_h, "left", "mediapipe_face_mesh", 0.94),
            _box_from_points(points(_FACE_MESH_RIGHT_BROW), image_w, image_h, "right", "mediapipe_face_mesh", 0.94),
        ]
        regions = [r for r in regions if r]
        if len(regions) >= 2:
            return ensure_eyebrow_mask(image_path, _ok("mediapipe_face_mesh", image_w, image_h, regions, 0.94),
                                       style_key=style_key, design_mode=design_mode)
    except Exception as e:
        _trace_log("02", "mediapipe_failed", error=str(e)[:120])
        return None
    return None


def _detect_with_opencv(image_path: str, style_key: str = "giso_suggested", design_mode: bool = True) -> Optional[Dict[str, Any]]:
    try:
        import cv2  # type: ignore
    except Exception:
        return None
    try:
        image = cv2.imread(image_path)
        if image is None:
            return None
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        image_h, image_w = gray.shape[:2]
        face_xml = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
        eye_xml = cv2.data.haarcascades + "haarcascade_eye.xml"
        face_cascade = cv2.CascadeClassifier(face_xml)
        eye_cascade = cv2.CascadeClassifier(eye_xml)
        faces = face_cascade.detectMultiScale(gray, scaleFactor=1.08, minNeighbors=5, minSize=(80, 80))
        if len(faces) == 0:
            return None
        center_x = image_w / 2.0
        faces = sorted(faces, key=lambda f: (abs((f[0] + f[2] / 2.0) - center_x), -f[2] * f[3]))
        fx, fy, fw, fh = [int(v) for v in faces[0]]
        face_gray = gray[fy:fy + fh, fx:fx + fw]
        eyes = eye_cascade.detectMultiScale(face_gray, scaleFactor=1.08, minNeighbors=5, minSize=(20, 12))
        usable = []
        for ex, ey, ew, eh in eyes:
            if ey > fh * 0.62:
                continue
            usable.append((int(ex), int(ey), int(ew), int(eh)))
        usable = sorted(usable, key=lambda e: e[2] * e[3], reverse=True)[:2]
        if len(usable) < 2:
            return None
        usable = sorted(usable, key=lambda e: e[0])
        regions: List[Dict[str, Any]] = []
        for idx, (ex, ey, ew, eh) in enumerate(usable):
            brow_w = ew * 1.38
            brow_h = max(10.0, eh * 0.48)
            x = fx + ex + ew / 2.0 - brow_w / 2.0
            y = fy + ey - eh * 0.62
            regions.append(_box(x, y, brow_w, brow_h, image_w, image_h, "left" if idx == 0 else "right", 0.58, "opencv_haar_eye"))
        return ensure_eyebrow_mask(image_path, _ok("opencv_haar_eye", image_w, image_h, regions, 0.58),
                                   style_key=style_key, design_mode=design_mode)
    except Exception as e:
        _trace_log("02", "opencv_failed", error=str(e)[:120])
        return None


def _hist_quantile(hist: List[int], q: float, total: int) -> int:
    target = max(1, int(total * q))
    running = 0
    for idx, count in enumerate(hist):
        running += count
        if running >= target:
            return idx
    return 255


def _dark_band_region(gray, image_w: int, image_h: int, half: Tuple[int, int, int, int], side: str) -> Dict[str, Any]:
    hx0, hy0, hx1, hy1 = half
    crop = gray.crop((hx0, hy0, hx1, hy1))
    width, height = crop.size
    if width < 20 or height < 12:
        return {}
    hist = crop.histogram()
    total = width * height
    q02 = _hist_quantile(hist, 0.02, total)
    q55 = _hist_quantile(hist, 0.55, total)
    if q55 - q02 < 18:
        return {}
    threshold = max(35, min(145, q02 + 24))
    pix = crop.load()
    row_scores = []
    for y in range(height):
        count = 0
        for x in range(width):
            if pix[x, y] <= threshold:
                count += 1
        row_scores.append(count)
    if not row_scores or max(row_scores) < max(4, width * 0.035):
        return {}
    smooth = []
    for y in range(height):
        smooth.append(sum(row_scores[max(0, y - 2):min(height, y + 3)]))
    peak = max(smooth)
    band_min_score = max(5, int(peak * 0.42))
    bands: List[Tuple[int, int, int]] = []
    start = None
    score_sum = 0
    for y, score in enumerate(smooth):
        if score >= band_min_score:
            if start is None:
                start = y
                score_sum = 0
            score_sum += score
        elif start is not None:
            if y - start >= 2:
                bands.append((start, y - 1, score_sum))
            start = None
            score_sum = 0
    if start is not None and height - start >= 2:
        bands.append((start, height - 1, score_sum))
    if not bands:
        return {}
    bands = [b for b in bands if 2 <= (b[1] - b[0] + 1) <= max(24, int(height * 0.36))]
    if not bands:
        return {}
    bands = sorted(bands, key=lambda b: (b[0], -b[2]))
    by0, by1, _ = bands[0]
    xs: List[int] = []
    ys: List[int] = []
    pad_y = 3
    for y in range(max(0, by0 - pad_y), min(height, by1 + pad_y + 1)):
        for x in range(width):
            if pix[x, y] <= threshold:
                xs.append(x)
                ys.append(y)
    if len(xs) < max(8, width * 0.04):
        return {}
    min_x = max(0, min(xs) - 4)
    max_x = min(width - 1, max(xs) + 4)
    min_y = max(0, min(ys) - 5)
    max_y = min(height - 1, max(ys) + 8)
    brow_w = max(18, max_x - min_x + 1)
    brow_h = max(10, max_y - min_y + 1)
    confidence = min(0.58, 0.38 + (len(xs) / float(width * max(1, brow_h))) * 0.18)
    region = _box(hx0 + min_x, hy0 + min_y, brow_w, brow_h, image_w, image_h, side, confidence, "dark_pixel_band")
    region["polygon_source"] = "dark_pixel_band_curved_polygon"
    return _ensure_region_polygon(region, image_w, image_h)


def _detect_with_dark_pixels(image_path: str, style_key: str = "giso_suggested", design_mode: bool = True) -> Optional[Dict[str, Any]]:
    try:
        from PIL import Image, ImageFilter
        with Image.open(image_path) as image:
            image = image.convert("L")
            image_w, image_h = image.size
            gray = image.filter(ImageFilter.GaussianBlur(radius=0.8))
    except Exception:
        return None
    if image_w < 80 or image_h < 80:
        return None
    x0 = int(image_w * 0.16)
    x1 = int(image_w * 0.84)
    y0 = int(image_h * 0.19)
    y1 = int(image_h * 0.52)
    mid = int((x0 + x1) / 2)
    gap = max(6, int(image_w * 0.025))
    left = (x0, y0, max(x0 + 1, mid - gap), y1)
    right = (min(x1 - 1, mid + gap), y0, x1, y1)
    regions = [
        _dark_band_region(gray, image_w, image_h, left, "left"),
        _dark_band_region(gray, image_w, image_h, right, "right"),
    ]
    regions = [r for r in regions if r]
    if len(regions) >= 2:
        confidence = sum(float(r.get("confidence") or 0.5) for r in regions) / len(regions)
        return ensure_eyebrow_mask(image_path, _ok("dark_pixel_band", image_w, image_h, regions, confidence),
                                   style_key=style_key, design_mode=design_mode)
    return None


def proportional_fallback_regions(image_w: int, image_h: int) -> Dict[str, Any]:
    """آخرین fallback غیر AI؛ فقط برای قطع‌نشدن تجربه، نه تشخیص واقعی."""
    face_w = min(image_w * 0.58, image_h * 0.46)
    brow_len = max(58, face_w * 0.27)
    brow_h = max(22, image_h * 0.042)
    y = image_h * 0.335
    regions = [
        _box(image_w * 0.385 - brow_len / 2, y, brow_len, brow_h, image_w, image_h, "left", 0.18, "proportional_fallback"),
        _box(image_w * 0.615 - brow_len / 2, y, brow_len, brow_h, image_w, image_h, "right", 0.18, "proportional_fallback"),
    ]
    result = _ok("proportional_fallback", image_w, image_h, regions, 0.18)
    result["detection_reliable"] = False
    result["is_fallback"] = True
    result["fallback_notice"] = "proportional coordinates only; not a real eyebrow detection"
    return result


def detect_eyebrow_regions(image_path: str, allow_fallback: bool = False, style_key: str = "giso_suggested", design_mode: bool = True) -> Dict[str, Any]:
    """تشخیص دو ROI ابرو، polygon و pixel mask از روی عکس کاربر.

    style_key: مدل انتخابی برای ساخت Design Region
    design_mode: اگر True، mask بر اساس Design Region بزرگتر ساخته می‌شود
    """
    image_w, image_h = _image_size(image_path)
    if not image_w or not image_h:
        return {
            "ok": False,
            "method": "invalid_image",
            "confidence": 0.0,
            "confidence_label": "none",
            "detection_reliable": False,
            "is_fallback": False,
            "image_width": 0,
            "image_height": 0,
            "regions": [],
            "mask": {"ok": False, "reason": "invalid_image"},
            "mask_width": 0,
            "mask_height": 0,
            "mask_path": "",
        }
    _trace_log("02", "detect_eyebrow_regions_start", style_key=style_key, design_mode=design_mode, image=f"{image_w}x{image_h}")
    for detector in (_detect_with_mediapipe, _detect_with_opencv, _detect_with_dark_pixels):
        try:
            result = detector(image_path, style_key=style_key, design_mode=design_mode)
        except TypeError:
            # backward compat with old signature without style_key
            result = detector(image_path)
        if result and result.get("ok") and len(result.get("regions") or []) >= 2:
            _trace_log("02", "detect_eyebrow_regions_found", method=result.get("method"), style_key=style_key)
            return result
    if allow_fallback:
        fallback = proportional_fallback_regions(image_w, image_h)
        return ensure_eyebrow_mask(image_path, fallback, style_key=style_key, design_mode=design_mode)
    return {
        "ok": False,
        "method": "not_detected",
        "confidence": 0.0,
        "confidence_label": "none",
        "detection_reliable": False,
        "is_fallback": False,
        "image_width": int(image_w),
        "image_height": int(image_h),
        "regions": [],
        "mask": {"ok": False, "reason": "not_detected", "width": int(image_w), "height": int(image_h)},
        "mask_width": int(image_w),
        "mask_height": int(image_h),
        "mask_path": "",
    }


__all__ = [
    "MASK_POLARITY",
    "detect_eyebrow_regions",
    "ensure_eyebrow_mask",
    "proportional_fallback_regions",
]
