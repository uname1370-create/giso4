from __future__ import annotations

from functools import lru_cache
import cv2
import mediapipe as mp
import numpy as np
from PIL import Image, ImageFilter

# Full MediaPipe eyebrow contours. The previous five-point polygons were too
# sparse and could make the feathered mask reach the upper eyelid/under-eye area.
LEFT_BROW = (70, 63, 105, 66, 107, 55, 65, 52, 53, 46)
RIGHT_BROW = (300, 293, 334, 296, 336, 285, 295, 282, 283, 276)

# Stable facial anchors used only to undo provider-wide translation/scale/rotation.
# They deliberately avoid eyebrow landmarks so the target edit itself cannot
# determine the alignment transform.
ALIGN_ANCHORS = (33, 263, 168, 1, 61, 291)


@lru_cache(maxsize=1)
def _mesh():
    return mp.solutions.face_mesh.FaceMesh(
        static_image_mode=True,
        max_num_faces=1,
        refine_landmarks=True,
        min_detection_confidence=0.60,
        min_tracking_confidence=0.60,
    )


def _decode(data: bytes) -> np.ndarray:
    arr = np.frombuffer(data, dtype=np.uint8)
    image = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    if image is None:
        raise ValueError("invalid image")
    return image


def _landmark_points(result, indices, width: int, height: int) -> np.ndarray:
    points = []
    for index in indices:
        lm = result.multi_face_landmarks[0].landmark[index]
        x = min(width - 1, max(0, int(round(lm.x * width))))
        y = min(height - 1, max(0, int(round(lm.y * height))))
        points.append((x, y))
    return np.asarray(points, dtype=np.float32)


def _detect_landmarks(image: np.ndarray) -> object:
    height, width = image.shape[:2]
    scale = min(1.0, 1400.0 / max(width, height))
    work = image if scale == 1.0 else cv2.resize(
        image, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA
    )
    result = _mesh().process(cv2.cvtColor(work, cv2.COLOR_BGR2RGB))
    if not result.multi_face_landmarks:
        raise ValueError("face not detected")
    return result, work.shape[1], work.shape[0]


def build_target_mask(data: bytes, service: str) -> np.ndarray:
    if service != "eyebrows":
        raise ValueError("unsupported service")

    image = _decode(data)
    height, width = image.shape[:2]
    result, ww, wh = _detect_landmarks(image)

    left = _landmark_points(result, LEFT_BROW, ww, wh)
    right = _landmark_points(result, RIGHT_BROW, ww, wh)
    mask_small = np.zeros((wh, ww), dtype=np.uint8)

    # Convex hull around the complete eyebrow contour. Keep a small edit margin
    # so sparse PMU strokes can extend naturally from a thin existing brow.
    for pts in (left, right):
        hull = cv2.convexHull(np.round(pts).astype(np.int32))
        center = pts.mean(axis=0)
        expanded = center + (hull.reshape(-1, 2).astype(np.float32) - center) * 1.06
        cv2.fillPoly(mask_small, [np.round(expanded).astype(np.int32)], 255)

    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
    mask_small = cv2.dilate(mask_small, kernel, iterations=1)
    mask = cv2.resize(mask_small, (width, height), interpolation=cv2.INTER_LINEAR)

    # Keep the transition local. The old 0.6% radius was unnecessarily broad
    # on phone photos and could blend into the upper eyelid/under-eye area.
    radius = max(1, min(9, int(round(min(width, height) * 0.0025))))
    mask = np.asarray(
        Image.fromarray(mask).filter(ImageFilter.GaussianBlur(radius=radius)),
        dtype=np.uint8,
    )

    coverage = float(np.count_nonzero(mask > 32)) / float(width * height)
    if coverage > 0.08:
        raise ValueError("eyebrow mask is unexpectedly large")
    return mask


def align_edited_to_original(original_data: bytes, edited_data: bytes) -> bytes:
    """
    Correct provider-wide geometry drift before compositing.

    Cloud image editors can return the same face slightly translated/scaled or
    rotated. We estimate a similarity transform from stable eye/nose/mouth
    landmarks and warp ONLY the edited image back to the original coordinate
    system. Eyebrow landmarks are intentionally excluded.
    """
    original = _decode(original_data)
    edited = _decode(edited_data)
    oh, ow = original.shape[:2]

    original_result, oww, owh = _detect_landmarks(original)
    edited_result, eww, ehh = _detect_landmarks(edited)

    src = _landmark_points(edited_result, ALIGN_ANCHORS, eww, ehh)
    dst = _landmark_points(original_result, ALIGN_ANCHORS, oww, owh)

    # RANSAC protects the transform from an occasional unstable facial point.
    transform, inliers = cv2.estimateAffinePartial2D(
        src,
        dst,
        method=cv2.RANSAC,
        ransacReprojThreshold=max(2.0, min(ow, oh) * 0.008),
        maxIters=2000,
        confidence=0.995,
    )
    if transform is None or inliers is None or int(inliers.sum()) < 4:
        raise ValueError("could not align provider output to original face geometry")

    aligned = cv2.warpAffine(
        edited,
        transform,
        (ow, oh),
        flags=cv2.INTER_LANCZOS4,
        borderMode=cv2.BORDER_REPLICATE,
    )
    ok, encoded = cv2.imencode(".png", aligned, [cv2.IMWRITE_PNG_COMPRESSION, 6])
    if not ok:
        raise ValueError("could not encode aligned image")
    return encoded.tobytes()


def analyze_brow_photo(data: bytes) -> dict:
    """Deterministic customer brow profile using the same MediaPipe geometry as masking."""
    image = _decode(data)
    height, width = image.shape[:2]
    result, ww, wh = _detect_landmarks(image)

    left = _landmark_points(result, LEFT_BROW, ww, wh)
    right = _landmark_points(result, RIGHT_BROW, ww, wh)
    if ww != width or wh != height:
        scale_x, scale_y = width / ww, height / wh
        left = left * np.asarray([scale_x, scale_y], dtype=np.float32)
        right = right * np.asarray([scale_x, scale_y], dtype=np.float32)

    def side_profile(points: np.ndarray) -> dict:
        x_min, y_min = points.min(axis=0)
        x_max, y_max = points.max(axis=0)
        width_px = max(1.0, float(x_max - x_min))
        height_px = max(1.0, float(y_max - y_min))
        thickness_ratio = height_px / width_px
        thickness = "thin" if thickness_ratio < 0.20 else "thick" if thickness_ratio > 0.32 else "medium"

        # Brow contour is ordered from inner to outer. The vertical change gives
        # a conservative growth-direction estimate without inventing anatomy.
        dy = float(points[-1][1] - points[0][1])
        growth = "upward_to_tail" if dy < -2 else "downward_to_tail" if dy > 2 else "mostly_horizontal"
        arch_y = float(points[:, 1].min())
        mean_y = float(points[:, 1].mean())
        arch = "defined" if arch_y < mean_y - max(1.0, height_px * 0.16) else "soft"

        return {
            "start": "customer_existing_position",
            "arch": arch,
            "tail": "customer_existing_position",
            "thickness": thickness,
            "density": "measured_from_customer_pixels",
            "growthDirection": growth,
            "asymmetry": "preserve_customer_asymmetry",
            "bbox": {
                "x": round(x_min / width * 1000) / 1000,
                "y": round(y_min / height * 1000) / 1000,
                "width": round(width_px / width * 1000) / 1000,
                "height": round(height_px / height * 1000) / 1000,
            },
        }

    # Face shape is intentionally coarse. It is a routing hint, not a biometric claim.
    face_points = _landmark_points(result, (10, 152, 234, 454), ww, wh)
    if ww != width or wh != height:
        face_points = face_points * np.asarray([width / ww, height / wh], dtype=np.float32)
    face_w = max(1.0, float(face_points[:, 0].max() - face_points[:, 0].min()))
    face_h = max(1.0, float(face_points[:, 1].max() - face_points[:, 1].min()))
    ratio = face_h / face_w
    face_shape = "long" if ratio > 1.55 else "wide" if ratio < 1.20 else "oval"

    mask = build_target_mask(data, "eyebrows")
    mask_bool = mask > 32
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    brow_pixels = gray[mask_bool]
    if brow_pixels.size < 20:
        raise ValueError("eyebrows not sufficiently visible")

    # Compare brow-region darkness to a narrow local ring. This is used only for
    # coarse density/tone classification, never to invent a precise pigment color.
    ring = cv2.dilate(mask, np.ones((9, 9), np.uint8), iterations=1) > 32
    ring = np.logical_and(ring, ~mask_bool)
    skin_pixels = gray[ring]
    darkness = float(np.median(skin_pixels) - np.median(brow_pixels)) if skin_pixels.size else 20.0
    density = "low" if darkness < 22 else "medium" if darkness < 42 else "high"

    brow_bgr = image[mask_bool]
    median_bgr = np.median(brow_bgr, axis=0)
    median_rgb = median_bgr[::-1]
    r_mean, g_mean, b_mean = [float(x) for x in median_rgb]
    if max(r_mean, g_mean, b_mean) < 65:
        brow_tone = "very_dark"
    elif r_mean > b_mean * 1.18 and g_mean > b_mean * 1.05:
        brow_tone = "warm_brown"
    elif abs(r_mean - b_mean) < 18:
        brow_tone = "cool_neutral_brown"
    else:
        brow_tone = "natural_brown"

    # Sample cheek-area pixels from stable face landmarks to estimate only a coarse
    # undertone. It is deliberately broad because camera white balance is unknown.
    cheek_points = _landmark_points(result, (50, 205, 280, 425), ww, wh)
    samples = []
    for x, y in cheek_points.astype(int):
        x0, x1 = max(0, x - 8), min(width, x + 9)
        y0, y1 = max(0, y - 8), min(height, y + 9)
        samples.append(image[y0:y1, x0:x1].reshape(-1, 3))
    skin = np.concatenate(samples, axis=0) if samples else np.empty((0, 3))
    if skin.size:
        sr, sg, sb = np.median(skin[:, ::-1], axis=0)
        if sr > sb * 1.10 and sg >= sb * 0.98:
            undertone = "warm"
        elif sb > sr * 1.06:
            undertone = "cool"
        else:
            undertone = "neutral"
    else:
        undertone = "neutral"

    temperature = "warm" if undertone == "warm" or brow_tone == "warm_brown" else "cool" if undertone == "cool" else "neutral"
    pigment_family = "natural_brown" if brow_tone != "very_dark" else "deep_natural_brown"
    pigment_depth = "deep" if brow_tone == "very_dark" else "medium"

    return {
        "acceptable": True,
        "reason": "good_photo",
        "message": "عکس برای پیش‌نمایش مناسب است.",
        "faceVisible": True,
        "eyebrowsVisible": True,
        "imageQuality": "good",
        "faceShape": face_shape,
        "browDensity": density,
        "browThickness": side_profile(left)["thickness"],
        "browArch": side_profile(left)["arch"],
        "browSymmetry": "natural_asymmetry_preserved",
        "hairTone": "inferred_from_visible_brow",
        "browTone": brow_tone,
        "skinUndertone": undertone,
        "pigmentFamily": pigment_family,
        "pigmentTemperature": temperature,
        "pigmentDepth": pigment_depth,
        "avoidPigments": ["pure_black", "strong_orange", "strong_red"],
        "leftBrow": side_profile(left),
        "rightBrow": side_profile(right),
        "browEditZone": "existing_brow_plus_small_natural_margin",
    }
