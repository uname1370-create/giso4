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

    # Do not stretch a provider image to arbitrary dimensions. This fallback is
    # aspect-preserving and only crops/centers if a provider violates the
    # requested geometry contract.
    target_ratio = width / height
    edited_ratio = edited.shape[1] / edited.shape[0]

    if abs(target_ratio - edited_ratio) > 0.02:
        if edited_ratio > target_ratio:
            new_width = max(1, int(round(edited.shape[0] * target_ratio)))
            left = max(0, (edited.shape[1] - new_width) // 2)
            edited = edited[:, left:left + new_width]
        else:
            new_height = max(1, int(round(edited.shape[1] / target_ratio)))
            top = max(0, (edited.shape[0] - new_height) // 2)
            edited = edited[top:top + new_height, :]

    return cv2.resize(edited, (width, height), interpolation=cv2.INTER_LANCZOS4)


def composite_target(
    original_data: bytes,
    edited_data: bytes,
    mask: np.ndarray,
) -> tuple[bytes, float]:
    original = _decode(original_data)
    edited = _fit_edited(_decode(edited_data), original.shape[1], original.shape[0])

    if mask.shape[:2] != original.shape[:2]:
        raise ValueError("target mask geometry does not match original image")

    # Outside the mask the output is literally the original image. This is the
    # hard guarantee that prevents provider-wide skin/eye/background changes.
    alpha = (mask.astype(np.float32) / 255.0)[..., None]
    result = (
        original.astype(np.float32) * (1.0 - alpha)
        + edited.astype(np.float32) * alpha
    ).clip(0, 255).astype(np.uint8)

    coverage = float(np.count_nonzero(mask > 32)) / float(mask.shape[0] * mask.shape[1])
    return _encode_png(result), coverage
