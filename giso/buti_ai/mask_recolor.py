"""Mask-confined colour transfer for the hair and nail guided previews.

The engine shifts the CIELAB channels by a constant offset inside a mask.
Constant offsets keep local differences (strands, shading, texture, specular
detail) intact, and pixels outside the mask are copied back byte-for-byte.
The engine does not decide whether a mask is trustworthy; callers must gate
on a validated detection before using it.
"""
from __future__ import annotations

from typing import Sequence

import numpy as np

MIN_REGION_PIXELS = 64
EDGE_FEATHER_PX = 3.0


def _lab_of_rgb(rgb: Sequence[int]) -> np.ndarray:
    import cv2

    px = np.array([[[int(v) for v in rgb]]], dtype=np.uint8)
    return cv2.cvtColor(px, cv2.COLOR_RGB2LAB).astype(np.float32)[0, 0]


def recolor_masked_region(
    rgb: np.ndarray,
    mask: np.ndarray,
    target_rgb: Sequence[int],
    strength: float = 1.0,
    protect_highlights: bool = False,
) -> np.ndarray:
    """Return a copy of ``rgb`` with the masked region moved toward ``target_rgb``.

    rgb: HxWx3 uint8 RGB image.
    mask: HxW uint8; pixels >0 are editable, >=128 also count for region statistics.
    target_rgb: 3 ints 0..255.
    strength: 0..1 scale on the offset (0 returns an unchanged copy).
    protect_highlights: roll the lightness offset off above L≈200 so glints stay bright.
    """
    import cv2

    rgb = np.asarray(rgb)
    if rgb.dtype != np.uint8 or rgb.ndim != 3 or rgb.shape[2] != 3:
        raise ValueError("rgb_invalid")
    mask = np.asarray(mask)
    if mask.ndim != 2 or mask.shape != rgb.shape[:2]:
        raise ValueError("mask_shape_mismatch")
    target = [int(v) for v in target_rgb]
    if len(target) != 3 or any(v < 0 or v > 255 for v in target):
        raise ValueError("target_invalid")
    strength = float(strength)
    if not 0.0 <= strength <= 1.0:
        raise ValueError("strength_out_of_range")

    region = mask >= 128
    if int(region.sum()) < MIN_REGION_PIXELS:
        raise ValueError("mask_too_small")

    lab = cv2.cvtColor(np.ascontiguousarray(rgb), cv2.COLOR_RGB2LAB).astype(np.float32)
    target_lab = _lab_of_rgb(target)
    med_l = float(np.median(lab[..., 0][region]))
    mean_a = float(lab[..., 1][region].mean())
    mean_b = float(lab[..., 2][region].mean())
    d_l = float(target_lab[0]) - med_l
    d_a = float(target_lab[1]) - mean_a
    d_b = float(target_lab[2]) - mean_b

    # Ramp the offset down over the first EDGE_FEATHER_PX pixels inside the mask so the
    # mask boundary does not show a step/halo. Outside the mask alpha stays exactly 0.
    inside = (mask > 0).astype(np.uint8)
    dist = cv2.distanceTransform(inside, cv2.DIST_L2, 3)
    ramp = np.clip(dist / float(EDGE_FEATHER_PX), 0.0, 1.0).astype(np.float32)
    alpha = (mask.astype(np.float32) / 255.0) * strength * ramp
    alpha_l = alpha
    if protect_highlights:
        roll = np.clip((lab[..., 0] - 200.0) / 55.0, 0.0, 1.0)
        alpha_l = alpha * (1.0 - roll)

    out = lab.copy()
    out[..., 0] = np.clip(lab[..., 0] + alpha_l * d_l, 0.0, 255.0)
    out[..., 1] = np.clip(lab[..., 1] + alpha * d_a, 0.0, 255.0)
    out[..., 2] = np.clip(lab[..., 2] + alpha * d_b, 0.0, 255.0)
    converted = cv2.cvtColor(np.round(out).astype(np.uint8), cv2.COLOR_LAB2RGB)

    # Copy back only where the offset is non-zero: pixels with alpha 0 (outside the mask,
    # or any pixel at strength 0) keep their exact original values, avoiding LAB round-trip drift.
    result = rgb.copy()
    editable = alpha > 0
    result[editable] = converted[editable]
    return result


__all__ = ["recolor_masked_region", "MIN_REGION_PIXELS"]
