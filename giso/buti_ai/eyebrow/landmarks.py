# -*- coding: utf-8 -*-
"""تشخیص محدوده ابرو و ساخت mask واقعی برای طراحی نهایی آینه ابرو.

خروجی این ماژول علاوه بر ROI قدیمی، polygon هر ابرو و یک pixel mask واقعی
(تصویر خاکستری PNG: سفید=ناحیه قابل ویرایش، سیاه=ناحیه محفوظ) می‌سازد تا
providerهای inpainting بتوانند فقط خود ابرو را تغییر دهند. وابستگی سنگین اجباری
نیست: اگر MediaPipe نصب باشد از FaceMesh استفاده می‌شود؛ در غیر این صورت مسیرهای
fallback تصویرمحور با confidence پایین‌تر حفظ می‌شوند. fallback نسبتی فقط با
درخواست صریح فعال است و هرگز به‌عنوان detection واقعی علامت‌گذاری نمی‌شود.
"""
from __future__ import annotations

import os
from typing import Any, Dict, Iterable, List, Optional, Tuple


# FaceMesh indices around both eyebrow ridges. These are used only when
# mediapipe is installed in the runtime; the project does not require it.
_FACE_MESH_LEFT_BROW = (70, 63, 105, 66, 107, 46, 53, 52, 65, 55)
_FACE_MESH_RIGHT_BROW = (336, 296, 334, 293, 300, 285, 295, 282, 283, 276)

MASK_EDIT_VALUE = 255
MASK_KEEP_VALUE = 0
MASK_POLARITY = "white_edit_black_keep"


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
    # برگ ابرو: بالای قوس‌دار + پایین نرم، محدود داخل box تا چشم/پلک درگیر نشود.
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
    # FaceMesh نقاط ridge ابرو را می‌دهد؛ برای inpainting یک band بسیار محدود دور آن می‌سازیم.
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
    margin_px: float = 5.0,
    margin_percent: float = 0.08,
) -> List[List[int]]:
    """ساخت polygon دقیق فقط از landmarkهای واقعی ابرو — بدون حاشیه بزرگ.

    MediaPipe برای هر ابرو 10 نقطه می‌دهد که دو قوس بالا/پایین ابرو هستند.
    اینجا مستقیم از خود نقاط یک polygon تنگ می‌سازیم:
    - مرکز ابرو حساب می‌شود
    - نقاط بر اساس زاویه دور مرکز مرتب می‌شوند تا یک حلقه بسته بسازند
    - فقط یک حاشیه کوچک (5px + 8%) در امتداد خود ابرو اضافه می‌شود
    - چشم، پلک، پوست اطراف وارد نمی‌شود
    """
    pts = [(float(x), float(y)) for x, y in points or []]
    if len(pts) < 3:
        return []
    cx = sum(x for x, y in pts) / len(pts)
    cy = sum(y for x, y in pts) / len(pts)
    import math

    def _angle(p: Tuple[float, float]) -> float:
        return math.atan2(p[1] - cy, p[0] - cx)

    sorted_pts = sorted(pts, key=_angle)
    expanded: List[List[int]] = []
    for x, y in sorted_pts:
        dx = x - cx
        dy = y - cy
        dist = math.hypot(dx, dy) or 1.0
        scale = 1.0 + margin_percent + (margin_px / dist)
        nx = cx + dx * scale
        ny = cy + dy * scale
        expanded.append(_clamp_point(nx, ny, image_w, image_h))
    if len(expanded) < 3 or _polygon_area(expanded) < 8.0:
        return [_clamp_point(x, y, image_w, image_h) for x, y in sorted_pts]
    return expanded


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
        pts, image_w, image_h, margin_px=2.5, margin_percent=0.04
    )
    if not precise_polygon:
        return _box_from_points_fallback(pts, image_w, image_h, side, source, confidence)

    min_x = min(p[0] for p in precise_polygon)
    max_x = max(p[0] for p in precise_polygon)
    min_y = min(p[1] for p in precise_polygon)
    max_y = max(p[1] for p in precise_polygon)
    bw = max(1.0, float(max_x - min_x))
    bh = max(1.0, float(max_y - min_y))
    small_margin = 2.0
    region = _box(
        float(min_x - small_margin),
        float(min_y - small_margin),
        float(bw + small_margin * 2),
        float(bh + small_margin * 2),
        image_w,
        image_h,
        side,
        confidence,
        source,
    )
    region["landmark_points"] = [_clamp_point(px, py, image_w, image_h) for px, py in pts]
    region["polygon"] = precise_polygon
    region["polygon_source"] = "mediapipe_precise_10_landmarks_tight"
    return _ensure_region_polygon(region, image_w, image_h)


def _box_from_points_fallback(
    points: Iterable[Tuple[float, float]],
    image_w: int,
    image_h: int,
    side: str,
    source: str,
    confidence: float,
) -> Dict[str, Any]:
    """نسخه قدیمی با حاشیه بزرگ — فقط برای fallbackهای غیر MediaPipe."""
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
    region["polygon_source"] = "facemesh_landmark_band_fallback"
    return _ensure_region_polygon(region, image_w, image_h)


def _box_from_points(points: Iterable[Tuple[float, float]], image_w: int, image_h: int,
                     side: str, source: str, confidence: float) -> Dict[str, Any]:
    """Wrapper — اگر source mediapipe باشد نسخه دقیق، وگرنه fallback قدیمی."""
    if str(source or "").startswith("mediapipe"):
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


def _is_plausible_eyebrow_pair(regions: List[Dict[str, Any]], image_w: int, image_h: int) -> bool:
    """بررسی سریع که دو ROI ابرو از نظر هندسی معقول هستند و چشم را درگیر نمی‌کنند.

    برای polygon دقیق MediaPipe (tight) کمی بازتر می‌کنیم چون mask کوچک‌تر و دقیق‌تر است
    و نباید به خاطر زاویه صورت یا حجاب رد شود.
    """
    if len(regions) < 2 or image_w <= 0 or image_h <= 0:
        return False
    try:
        ordered = sorted(regions, key=lambda r: r.get("cx", 0))
        left, right = ordered[0], ordered[1]
        lx, ly, lw, lh = float(left.get("x") or 0), float(left.get("y") or 0), float(left.get("width") or 0), float(left.get("height") or 0)
        rx, ry, rw, rh = float(right.get("x") or 0), float(right.get("y") or 0), float(right.get("width") or 0), float(right.get("height") or 0)
        lcx, lcy = float(left.get("cx") or (lx + lw/2)), float(left.get("cy") or (ly + lh/2))
        rcx, rcy = float(right.get("cx") or (rx + rw/2)), float(right.get("cy") or (ry + rh/2))

        # تشخیص اینکه آیا این detection از نسخه دقیق mediapipe است
        is_precise = any("precise" in str(r.get("polygon_source") or "") or "tight" in str(r.get("polygon_source") or "") for r in ordered)
        # برای precise، بازتر چون mask کوچک و دقیق است و زاویه صورت/حجاب نباید رد شود
        max_cy_ratio = 0.60 if is_precise else 0.45
        max_y_ratio = 0.55 if is_precise else 0.42
        max_h_ratio = 0.32 if is_precise else 0.13
        max_v_sym_ratio = 0.25 if is_precise else 0.08

        # باید در نیمه بالایی تصویر باشند (ابرو بالای چشم است)
        if lcy > image_h * max_cy_ratio or rcy > image_h * max_cy_ratio:
            return False
        if ly > image_h * max_y_ratio or ry > image_h * max_y_ratio:
            return False
        # نباید خیلی بالا هم باشند (حجاب/پیشانی)
        if lcy < image_h * 0.12 or rcy < image_h * 0.12:
            return False

        # چپ باید چپ وسط باشد، راست راست وسط
        if lcx >= image_w * 0.5 or rcx <= image_w * 0.5:
            return False

        # فاصله افقی معقول
        dist = abs(rcx - lcx)
        if dist < image_w * 0.15 or dist > image_w * 0.6:
            return False

        # تقارن عمودی — برای precise بازتر چون زاویه صورت ممکن است ابروها را ناهم‌تراز کند
        if abs(lcy - rcy) > image_h * max_v_sym_ratio:
            return False

        # اندازه معقول — برای precise ارتفاع تا 22% مجاز چون با حاشیه کوچک باز هم دقیق است
        for w, h in ((lw, lh), (rw, rh)):
            if w < image_w * 0.04 or w > image_w * 0.42:
                return False
            if h < image_h * 0.008 or h > image_h * max_h_ratio:
                return False

        # نباید خیلی هم‌پوشانی داشته باشند
        if not (rx > lx + lw * 0.15 or lx > rx + rw * 0.15):
            if abs(lcx - rcx) < image_w * 0.12:
                return False

        return True
    except Exception:
        return False


def _ok(method: str, image_w: int, image_h: int, regions: List[Dict[str, Any]], confidence: float) -> Dict[str, Any]:
    ordered = sorted(regions, key=lambda r: r.get("cx", 0))
    for idx, region in enumerate(ordered):
        region["side"] = "left" if idx == 0 else "right"
        _ensure_region_polygon(region, image_w, image_h)
    fallback_only = method == "proportional_fallback"
    plausible = _is_plausible_eyebrow_pair(ordered[:2], image_w, image_h) if len(ordered) >= 2 else False
    # اگر fallback نیست و plausible نیست، ok=False تا detector بعدی امتحان شود
    ok_flag = len(ordered) >= 2 and (fallback_only or plausible)
    return {
        "ok": ok_flag,
        "method": method if ok_flag else f"{method}_implausible",
        "confidence": round(float(confidence), 3),
        "confidence_label": _method_confidence_label(method),
        "detection_reliable": not fallback_only and ok_flag and plausible,
        "is_fallback": fallback_only,
        "plausible": plausible,
        "image_width": int(image_w),
        "image_height": int(image_h),
        "regions": ordered[:2] if ok_flag else [],
        "mask": {"ok": False, "reason": "not_generated" if ok_flag else "implausible_regions"},
        "mask_width": 0,
        "mask_height": 0,
        "mask_path": "",
    }


def ensure_eyebrow_mask(image_path: str, detection: Optional[Dict[str, Any]] = None,
                        output_path: str = "") -> Dict[str, Any]:
    """برای detection موجود یک PNG mask واقعی و قابل ارسال به provider می‌سازد.

    Mask دودویی است: سفید (255) یعنی ناحیه‌ای که inpainting اجازه ویرایش دارد،
    سیاه (0) یعنی بقیه تصویر باید حفظ شود. اگر detection نسبتی باشد، mask ساخته
    می‌شود اما `real_mask=False` می‌ماند تا به‌عنوان detection واقعی استفاده نشود.
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
            region = _ensure_region_polygon(dict(raw_region or {}), image_w, image_h)
            polygon = [tuple(point) for point in region.get("polygon") or []]
            if len(polygon) < 4:
                continue
            region_mask = Image.new("L", (image_w, image_h), MASK_KEEP_VALUE)
            region_draw = ImageDraw.Draw(region_mask)
            region_draw.polygon(polygon, fill=MASK_EDIT_VALUE)
            pixel_count = sum(1 for px in region_mask.getdata() if px > 0)
            region["mask_pixel_count"] = int(pixel_count)
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
            mask_path = os.path.join(mask_dir, f"{stem}_eyebrow_mask.png")
        os.makedirs(os.path.dirname(mask_path), exist_ok=True)
        mask.save(mask_path, "PNG", optimize=True)

        union_pixels = sum(1 for px in mask.getdata() if px > 0)
        bbox_area_sum = sum(max(1, int(r.get("width") or 1) * int(r.get("height") or 1)) for r in updated_regions)
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
            "is_rectangle_mask": False,
            "real_mask": not fallback_only,
            "is_fallback": fallback_only,
        }
        detection["mask_width"] = int(image_w)
        detection["mask_height"] = int(image_h)
        detection["mask_path"] = mask_path
        detection["has_real_mask"] = not fallback_only
        return detection
    except Exception as exc:
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


def _detect_with_mediapipe(image_path: str) -> Optional[Dict[str, Any]]:
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
            return ensure_eyebrow_mask(image_path, _ok("mediapipe_face_mesh", image_w, image_h, regions, 0.94))
    except Exception:
        return None
    return None


def _detect_with_opencv(image_path: str) -> Optional[Dict[str, Any]]:
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
        return ensure_eyebrow_mask(image_path, _ok("opencv_haar_eye", image_w, image_h, regions, 0.58))
    except Exception:
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
    # Smooth rows to favor eyebrow-like horizontal bands over isolated dark pixels.
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
    # Brow usually is the first strong dark band in upper face crop; keep plausible height.
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
    region["pixel_threshold"] = int(threshold)
    region["polygon_source"] = "dark_pixel_band_curved_polygon"
    return _ensure_region_polygon(region, image_w, image_h)


def _detect_with_dark_pixels(image_path: str) -> Optional[Dict[str, Any]]:
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
    # فقط پنجره جستجو ثابت است؛ خود محدوده ابرو از تاریکی/بافت داخل عکس کشف می‌شود.
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
        return ensure_eyebrow_mask(image_path, _ok("dark_pixel_band", image_w, image_h, regions, confidence))
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


def detect_eyebrow_regions(image_path: str, allow_fallback: bool = False) -> Dict[str, Any]:
    """تشخیص دو ROI ابرو، polygon و pixel mask از روی عکس کاربر.

    ترتیب روش‌ها:
    1. MediaPipe FaceMesh اگر نصب باشد (اعتماد بالا)
    2. OpenCV Haar face/eye اگر نصب باشد (fallback تصویرمحور با اعتماد پایین‌تر)
    3. تشخیص سبک مبتنی بر باندهای تیره داخل عکس (fallback تصویرمحور با اعتماد پایین)
    4. fallback نسبتی فقط در صورت درخواست صریح؛ detection واقعی محسوب نمی‌شود
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
    for detector in (_detect_with_mediapipe, _detect_with_opencv, _detect_with_dark_pixels):
        result = detector(image_path)
        if result and result.get("ok") and len(result.get("regions") or []) >= 2:
            return result
    if allow_fallback:
        fallback = proportional_fallback_regions(image_w, image_h)
        return ensure_eyebrow_mask(image_path, fallback)
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
