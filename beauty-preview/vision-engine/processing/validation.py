import cv2
import numpy as np

def _decode(data: bytes) -> np.ndarray:
    arr = np.frombuffer(data, dtype=np.uint8)
    image = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    if image is None:
        raise ValueError("invalid image")
    return image

def validate_non_target_preservation(original_data: bytes, result_data: bytes, mask: np.ndarray) -> float:
    original = _decode(original_data)
    result = _decode(result_data)
    if original.shape[:2] != result.shape[:2]:
        result = cv2.resize(result, (original.shape[1], original.shape[0]), interpolation=cv2.INTER_AREA)
    outside = mask < 32
    if not np.any(outside):
        return 0.0
    diff = np.abs(original.astype(np.int16) - result.astype(np.int16)).mean(axis=2)
    mean_diff = float(diff[outside].mean())
    return max(0.0, 1.0 - mean_diff / 12.0)
