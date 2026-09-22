from __future__ import annotations

from functools import lru_cache
import cv2
import mediapipe as mp
import numpy as np
from PIL import Image, ImageFilter

LEFT_BROW = (70, 63, 105, 66, 107)
RIGHT_BROW = (336, 296, 334, 293, 300)

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
    return np.asarray(points, dtype=np.int32)

def build_target_mask(data: bytes, service: str) -> np.ndarray:
    if service != "eyebrows":
        raise ValueError("unsupported service")

    image = _decode(data)
    height, width = image.shape[:2]
    scale = min(1.0, 1400.0 / max(width, height))
    work = image if scale == 1.0 else cv2.resize(image, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)
    wh, ww = work.shape[:2]
    result = _mesh().process(cv2.cvtColor(work, cv2.COLOR_BGR2RGB))

    if not result.multi_face_landmarks:
        raise ValueError("face not detected")

    left = _landmark_points(result, LEFT_BROW, ww, wh)
    right = _landmark_points(result, RIGHT_BROW, ww, wh)
    mask_small = np.zeros((wh, ww), dtype=np.uint8)

    for pts in (left, right):
        center = pts.mean(axis=0)
        expanded = center + (pts - center) * 1.08
        cv2.fillPoly(mask_small, [np.round(expanded).astype(np.int32)], 255)

    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (7, 5))
    mask_small = cv2.dilate(mask_small, kernel, iterations=1)
    mask = cv2.resize(mask_small, (width, height), interpolation=cv2.INTER_LINEAR)

    radius = max(3, int(round(min(width, height) * 0.006)))
    mask = np.asarray(Image.fromarray(mask).filter(ImageFilter.GaussianBlur(radius=radius)), dtype=np.uint8)

    coverage = float(np.count_nonzero(mask > 32)) / float(width * height)
    if coverage > 0.08:
        raise ValueError("eyebrow mask is unexpectedly large")
    return mask
