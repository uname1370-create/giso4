"""Unit tests for the mask-confined recolour engine (giso/buti_ai/mask_recolor.py).

These are internal-logic checks on synthetic images. Real-photo evaluation lives outside
the repo (see the round-6 report); nothing here claims AI output quality.
"""
import numpy as np
import pytest

from giso.buti_ai.mask_recolor import MIN_REGION_PIXELS, recolor_masked_region


def _textured(h=120, w=160, seed=3):
    rng = np.random.default_rng(seed)
    base = np.full((h, w, 3), 120, np.uint8)
    noise = rng.integers(-18, 19, size=(h, w, 1))
    return np.clip(base.astype(int) + noise, 0, 255).astype(np.uint8)


def _rect_mask(h, w, x0, y0, x1, y1):
    m = np.zeros((h, w), np.uint8)
    m[y0:y1, x0:x1] = 255
    return m


def test_outside_mask_pixels_are_byte_identical():
    img = _textured()
    mask = _rect_mask(*img.shape[:2], 40, 30, 110, 90)
    out = recolor_masked_region(img, mask, (214, 164, 86), strength=0.9)
    outside = mask == 0
    assert np.array_equal(out[outside], img[outside])
    assert not np.array_equal(out[~outside], img[~outside])


def test_zero_strength_returns_identical_image():
    img = _textured()
    mask = _rect_mask(*img.shape[:2], 40, 30, 110, 90)
    assert np.array_equal(recolor_masked_region(img, mask, (20, 200, 30), strength=0.0), img)


def test_local_texture_is_preserved_inside_mask():
    img = _textured()
    mask = _rect_mask(*img.shape[:2], 30, 20, 130, 100)
    out = recolor_masked_region(img, mask, (96, 58, 38), strength=0.85)
    from PIL import Image, ImageFilter

    def highpass_std(arr):
        gray = np.asarray(Image.fromarray(arr).convert("L").filter(ImageFilter.GaussianBlur(3)), np.float32)
        raw = np.asarray(Image.fromarray(arr).convert("L"), np.float32)
        inner = (slice(40, 80), slice(50, 110))  # well inside the mask, away from the feather
        return float((raw - gray)[inner].std())

    ratio = highpass_std(out) / highpass_std(img)
    assert 0.8 <= ratio <= 1.2


def test_colour_moves_toward_target_chroma():
    img = np.full((80, 80, 3), 128, np.uint8)  # neutral grey
    mask = _rect_mask(80, 80, 10, 10, 70, 70)
    out = recolor_masked_region(img, mask, (30, 60, 200), strength=1.0)
    region = mask >= 128
    before_blue = img[region].astype(int)[:, 2].mean() - img[region].astype(int)[:, 0].mean()
    after_blue = out[region].astype(int)[:, 2].mean() - out[region].astype(int)[:, 0].mean()
    assert after_blue > before_blue + 30


def test_highlight_protection_keeps_glints_brighter():
    img = np.full((80, 80, 3), 90, np.uint8)
    img[20:60, 20:60] = 250  # glint inside the mask
    mask = _rect_mask(80, 80, 10, 10, 70, 70)
    plain = recolor_masked_region(img, mask, (40, 40, 40), strength=1.0, protect_highlights=False)
    protected = recolor_masked_region(img, mask, (40, 40, 40), strength=1.0, protect_highlights=True)
    glint = (slice(25, 55), slice(25, 55))
    assert protected[glint].astype(int).mean() > plain[glint].astype(int).mean() + 15


@pytest.mark.parametrize(
    "kwargs, reason",
    [
        ({"rgb": np.zeros((10, 10), np.uint8)}, "rgb_invalid"),
        ({"mask": np.zeros((9, 10), np.uint8)}, "mask_shape_mismatch"),
        ({"target_rgb": (1, 2)}, "target_invalid"),
        ({"target_rgb": (300, 0, 0)}, "target_invalid"),
        ({"strength": 1.5}, "strength_out_of_range"),
    ],
)
def test_invalid_inputs_are_rejected(kwargs, reason):
    img = _textured(40, 40)
    args = {"rgb": img, "mask": _rect_mask(40, 40, 5, 5, 35, 35), "target_rgb": (10, 10, 10), "strength": 0.5}
    args.update(kwargs)
    with pytest.raises(ValueError, match=reason):
        recolor_masked_region(args["rgb"], args["mask"], args["target_rgb"], strength=args["strength"])


def test_tiny_mask_is_refused():
    img = _textured(40, 40)
    mask = np.zeros((40, 40), np.uint8)
    side = int(MIN_REGION_PIXELS ** 0.5) - 3
    mask[5:5 + side, 5:5 + side] = 255
    with pytest.raises(ValueError, match="mask_too_small"):
        recolor_masked_region(img, mask, (10, 10, 10))
