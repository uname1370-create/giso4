import cv2
import numpy as np


def _decode(data: bytes) -> np.ndarray:
    arr = np.frombuffer(data, dtype=np.uint8)
    image = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    if image is None:
        raise ValueError("invalid image")
    return image


def _fit(image: np.ndarray, width: int, height: int) -> np.ndarray:
    if image.shape[:2] == (height, width):
        return image

    target_ratio = width / height
    image_ratio = image.shape[1] / image.shape[0]
    if abs(target_ratio - image_ratio) > 0.02:
        raise ValueError("provider output aspect ratio differs from original")

    return cv2.resize(image, (width, height), interpolation=cv2.INTER_LANCZOS4)


def validate_provider_isolation(original_data: bytes, edited_data: bytes, mask: np.ndarray) -> float:
    original = _decode(original_data)
    edited = _fit(_decode(edited_data), original.shape[1], original.shape[0])
    outside = mask < 32
    if not np.any(outside):
        return 0.0

    diff = np.abs(original.astype(np.int16) - edited.astype(np.int16)).mean(axis=2)
    mean_diff = float(diff[outside].mean())
    return max(0.0, 1.0 - mean_diff / 40.0)


def validate_non_target_preservation(original_data: bytes, result_data: bytes, mask: np.ndarray) -> float:
    original = _decode(original_data)
    result = _fit(_decode(result_data), original.shape[1], original.shape[0])
    outside = mask < 32
    if not np.any(outside):
        return 0.0

    diff = np.abs(original.astype(np.int16) - result.astype(np.int16)).mean(axis=2)
    mean_diff = float(diff[outside].mean())
    return max(0.0, 1.0 - mean_diff / 12.0)
