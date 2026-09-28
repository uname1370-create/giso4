# -*- coding: utf-8 -*-
"""تشخیص محدوده ابرو برای طراحی نهایی آینه ابرو.

این ماژول هیچ وابستگی سنگینی را اجباری نمی‌کند. اگر MediaPipe یا OpenCV در
محیط نصب باشد از آن‌ها استفاده می‌شود؛ در غیر این صورت یک تشخیص سبک مبتنی بر
پیکسل‌های تیره داخل ناحیه بالایی چهره انجام می‌شود. خروجی همیشه JSON-safe است
تا بتواند در session و prompt provider تصویرسازی ذخیره شود.
"""
from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional, Tuple


# FaceMesh indices around both eyebrow ridges. These are used only when
# mediapipe is installed in the runtime; the project does not require it.
_FACE_MESH_LEFT_BROW = (70, 63, 105, 66, 107, 46, 53, 52, 65, 55)
_FACE_MESH_RIGHT_BROW = (336, 296, 334, 293, 300, 285, 295, 282, 283, 276)


def _image_size(image_path: str) -> Tuple[int, int]:
    try:
        from PIL import Image

        with Image.open(image_path) as image:
            return image.size
    except Exception:
        return 0, 0


def _box(x: float, y: float, w: float, h: float, image_w: int, image_h: int, side: str,
         confidence: float, source: str) -> Dict[str, Any]:
    x = max(0.0, min(float(image_w - 1), float(x))) if image_w > 1 else 0.0
    y = max(0.0, min(float(image_h - 1), float(y))) if image_h > 1 else 0.0
    w = max(1.0, min(float(image_w) - x, float(w))) if image_w > 0 else max(1.0, float(w))
    h = max(1.0, min(float(image_h) - y, float(h))) if image_h > 0 else max(1.0, float(h))
    return {
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


def _box_from_points(points: Iterable[Tuple[float, float]], image_w: int, image_h: int,
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
    # ابرو باریک است؛ برای provider/mask کمی حاشیه امن می‌دهیم اما از چشم دور می‌مانیم.
    expand_x = bw * 0.34
    expand_top = max(8.0, bh * 1.4)
    expand_bottom = max(10.0, bh * 1.8)
    return _box(
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


def _ok(method: str, image_w: int, image_h: int, regions: List[Dict[str, Any]], confidence: float) -> Dict[str, Any]:
    ordered = sorted(regions, key=lambda r: r.get("cx", 0))
    for idx, region in enumerate(ordered):
        region["side"] = "left" if idx == 0 else "right"
    return {
        "ok": len(ordered) >= 2,
        "method": method,
        "confidence": round(float(confidence), 3),
        "image_width": int(image_w),
        "image_height": int(image_h),
        "regions": ordered[:2],
    }


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
            return _ok("mediapipe_face_mesh", image_w, image_h, regions, 0.94)
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
            regions.append(_box(x, y, brow_w, brow_h, image_w, image_h, "left" if idx == 0 else "right", 0.76, "opencv_haar_eye"))
        return _ok("opencv_haar_eye", image_w, image_h, regions, 0.76)
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
    confidence = min(0.72, 0.45 + (len(xs) / float(width * max(1, brow_h))) * 0.18)
    return _box(hx0 + min_x, hy0 + min_y, brow_w, brow_h, image_w, image_h, side, confidence, "dark_pixel_band")


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
        return _ok("dark_pixel_band", image_w, image_h, regions, confidence)
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
    return _ok("proportional_fallback", image_w, image_h, regions, 0.18)


def detect_eyebrow_regions(image_path: str, allow_fallback: bool = False) -> Dict[str, Any]:
    """تشخیص دو ROI ابرو از روی عکس کاربر.

    ترتیب روش‌ها:
    1. MediaPipe FaceMesh اگر نصب باشد
    2. OpenCV Haar face/eye اگر نصب باشد
    3. تشخیص سبک مبتنی بر باندهای تیره داخل عکس
    4. fallback نسبتی فقط در صورت درخواست صریح
    """
    image_w, image_h = _image_size(image_path)
    if not image_w or not image_h:
        return {"ok": False, "method": "invalid_image", "confidence": 0.0, "image_width": 0, "image_height": 0, "regions": []}
    for detector in (_detect_with_mediapipe, _detect_with_opencv, _detect_with_dark_pixels):
        result = detector(image_path)
        if result and result.get("ok") and len(result.get("regions") or []) >= 2:
            return result
    if allow_fallback:
        return proportional_fallback_regions(image_w, image_h)
    return {
        "ok": False,
        "method": "not_detected",
        "confidence": 0.0,
        "image_width": int(image_w),
        "image_height": int(image_h),
        "regions": [],
    }


__all__ = ["detect_eyebrow_regions", "proportional_fallback_regions"]
