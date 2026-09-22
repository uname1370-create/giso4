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

    # Convex hull around the complete eyebrow contour. A small geometric
    # expansion covers the hair strokes without reaching the eyelid.
    for pts in (left, right):
        hull = cv2.convexHull(np.round(pts).astype(np.int32))
        center = pts.mean(axis=0)
        expanded = center + (hull.reshape(-1, 2).astype(np.float32) - center) * 1.035
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
