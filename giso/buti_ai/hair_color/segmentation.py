"""Hair region segmentation for the hair_color service.

Model: Kazuhito00/Skin-Clothes-Hair-Segmentation-using-SMP (MIT, see
giso/buti_ai/models/LICENSE-hair_skin_clothes_Kazuhito00-MIT.txt).
Input: RGB, 512x512, ImageNet mean/std, NCHW float32.
Output channels (verified visually on real portraits and a lip close-up):
  0 = skin, 1 = clothes, 2 = hair.

The raw hair channel leaks onto background light spots, shoulders and clothing,
so the mask is only returned when the validation gate below passes. Any failure
raises ``HairSegmentationError`` with a stable reason code; callers must treat
that as an untrusted region and never send the image to a provider with it.
"""
from __future__ import annotations

import os
from typing import Any, Dict, Optional, Tuple

MODEL_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "models",
    "hair_skin_clothes_mobilenetv3_small.onnx",
)
INPUT_SIZE = 512
HAIR_THRESHOLD = 0.5
MIN_COVERAGE = 0.02
MAX_COVERAGE = 0.42
# Share of hair pixels allowed in the band directly below the chin, centred on
# the face. Hair falls beside the neck; a mask here means clothing/neck leakage.
MAX_BELOW_CHIN_CENTRE_SHARE = 0.10
# Minimum share of the hair mask that must sit above the top of the face box.
MIN_ABOVE_FACE_SHARE = 0.05

_session = None


class HairSegmentationError(Exception):
    def __init__(self, reason: str, detail: str = ""):
        super().__init__(f"{reason}: {detail}" if detail else reason)
        self.reason = reason
        self.detail = detail


def _get_session():
    global _session
    if _session is None:
        try:
            import onnxruntime as ort
        except Exception as exc:  # pragma: no cover - depends on deployment
            raise HairSegmentationError("onnxruntime_missing", str(exc)[:120])
        if not os.path.exists(MODEL_PATH):
            raise HairSegmentationError("model_file_missing", MODEL_PATH)
        _session = ort.InferenceSession(MODEL_PATH, providers=["CPUExecutionProvider"])
    return _session


def class_probabilities(rgb_image) -> Tuple[Any, Any, Any]:
    """Return (skin, clothes, hair) probability maps at the original image size."""
    import cv2
    import numpy as np

    rgb = np.asarray(rgb_image.convert("RGB"))
    h, w = rgb.shape[:2]
    small = cv2.resize(rgb, (INPUT_SIZE, INPUT_SIZE), interpolation=cv2.INTER_AREA).astype(np.float32) / 255.0
    mean = np.array([0.485, 0.456, 0.406], np.float32)
    std = np.array([0.229, 0.224, 0.225], np.float32)
    x = ((small - mean) / std).transpose(2, 0, 1)[None].astype(np.float32)
    sess = _get_session()
    out = sess.run(None, {sess.get_inputs()[0].name: x})[0][0]
    maps = []
    for c in range(3):
        maps.append(cv2.resize(out[c].astype(np.float32), (w, h), interpolation=cv2.INTER_LINEAR))
    skin, clothes, hair = maps
    return skin, clothes, hair


def segment_hair(rgb_image, face_box: Optional[Tuple[int, int, int, int]]) -> Dict[str, Any]:
    """Return {"mask": PIL L image, "stats": {...}} or raise HairSegmentationError."""
    import cv2
    import numpy as np
    from PIL import Image

    if not face_box:
        raise HairSegmentationError("face_anchor_missing", "hair mask needs a detected head")
    fx, fy, fw, fh = [int(v) for v in face_box]
    w, h = rgb_image.size
    skin, clothes, hair = class_probabilities(rgb_image)

    # A pixel is hair only when the hair channel wins and is confident.
    hair_bin = ((hair >= HAIR_THRESHOLD) & (hair >= skin) & (hair >= clothes)).astype(np.uint8)
    hair_bin = cv2.morphologyEx(hair_bin, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))

    # Keep only hair components that touch the head zone around the face box.
    head_zone = np.zeros((h, w), np.uint8)
    zx0 = max(0, int(fx - 0.9 * fw))
    zx1 = min(w, int(fx + 1.9 * fw))
    zy0 = max(0, int(fy - 0.6 * fh))
    zy1 = min(h, int(fy + 2.4 * fh))
    head_zone[zy0:zy1, zx0:zx1] = 1
    n, labels, stats, _ = cv2.connectedComponentsWithStats(hair_bin, connectivity=8)
    keep = np.zeros(n, bool)
    for idx in range(1, n):
        comp = labels == idx
        if (comp & (head_zone > 0)).any():
            keep[idx] = True
    mask_bin = keep[labels].astype(np.uint8)

    # The face interior is skin, never hair.
    face_core = np.zeros((h, w), np.uint8)
    cv2.ellipse(
        face_core,
        (int(fx + fw / 2), int(fy + fh * 0.55)),
        (max(1, int(fw * 0.42)), max(1, int(fh * 0.58))),
        0, 0, 360, 1, -1,
    )
    mask_bin[face_core > 0] = 0

    total = int(mask_bin.sum())
    coverage = total / float(max(1, w * h))
    if total == 0:
        raise HairSegmentationError("hair_not_detected", "no hair pixels touch the head zone")
    if not (MIN_COVERAGE <= coverage <= MAX_COVERAGE):
        raise HairSegmentationError("hair_geometry_not_plausible", f"coverage {coverage:.3f}")

    ys, xs = np.nonzero(mask_bin)
    above_share = float((ys < fy).sum()) / float(total)
    if above_share < MIN_ABOVE_FACE_SHARE:
        raise HairSegmentationError("hair_not_above_face", f"above-face share {above_share:.3f}")

    chin_y = fy + fh
    band = (ys > chin_y + 0.3 * fh) & (xs > fx + 0.2 * fw) & (xs < fx + 0.8 * fw)
    below_share = float(band.sum()) / float(total)
    if below_share > MAX_BELOW_CHIN_CENTRE_SHARE:
        raise HairSegmentationError("hair_on_neck_or_clothes", f"below-chin share {below_share:.3f}")

    mask = Image.fromarray((mask_bin * 255).astype(np.uint8), mode="L")
    bbox = (int(xs.min()), int(ys.min()), int(xs.max() - xs.min() + 1), int(ys.max() - ys.min() + 1))
    return {
        "mask": mask,
        "stats": {
            "bbox": bbox,
            "coverage": round(coverage, 6),
            "above_face_share": round(above_share, 4),
            "below_chin_centre_share": round(below_share, 4),
            "components_kept": int(keep.sum()),
            "model": os.path.basename(MODEL_PATH),
        },
    }
