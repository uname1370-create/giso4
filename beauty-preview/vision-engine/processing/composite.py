import cv2
import numpy as np

def _decode(data: bytes) -> np.ndarray:
    arr = np.frombuffer(data, dtype=np.uint8)
    image = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    if image is None:
        raise ValueError("invalid image")
    return image

def _encode_png(image: np.ndarray) -> bytes:
    ok, encoded = cv2.imencode(".png", image, [cv2.IMWRITE_PNG_COMPRESSION, 6])
    if not ok:
        raise ValueError("could not encode output")
    return encoded.tobytes()

def _fit_edited(edited: np.ndarray, width: int, height: int) -> np.ndarray:
    if edited.shape[1] == width and edited.shape[0] == height:
        return edited
    return cv2.resize(edited, (width, height), interpolation=cv2.INTER_LANCZOS4)

def composite_target(original_data: bytes, edited_data: bytes, mask: np.ndarray) -> tuple[bytes, float]:
    original = _decode(original_data)
    edited = _fit_edited(_decode(edited_data), original.shape[1], original.shape[0])
    alpha = (mask.astype(np.float32) / 255.0)[..., None]
    result = (original.astype(np.float32) * (1.0 - alpha) + edited.astype(np.float32) * alpha).clip(0, 255).astype(np.uint8)
    coverage = float(np.count_nonzero(mask > 32)) / float(mask.shape[0] * mask.shape[1])
    return _encode_png(result), coverage
