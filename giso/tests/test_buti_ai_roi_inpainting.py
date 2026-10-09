# -*- coding: utf-8 -*-
"""Contracts for the small-mask crop path of the shared service inpainting call.

Only the outbound HTTP call is replaced by a local fake model. No network is used.
These tests check the request shape and the composite contract. They do not prove
that a real Cloudflare model edits the region well; that needs a live run.
"""
import base64
import os
from io import BytesIO
from types import SimpleNamespace

os.environ.setdefault("SECRET_KEY", "arena-test-secret-for-buti-ai-tests-32chars")

import pytest
from PIL import Image, ImageDraw

from giso.buti_ai import service_image_generation as sig
from giso.buti_ai.eyebrow import image_generation as shared_image

INPAINT = "@cf/runwayml/stable-diffusion-v1-5-inpainting"
ENDPOINT = "https://api.cloudflare.com/client/v4/accounts/test-account/ai/run/" + INPAINT


class _FakeResponse:
    def __init__(self, png_bytes):
        self.headers = {"content-type": "image/png"}
        self.content = png_bytes
        self.ok = True
        self.status_code = 200
        self.text = ""

    def json(self):
        raise ValueError("binary response")


def _photo(path, size=(1200, 900)):
    img = Image.linear_gradient("L").resize(size).convert("RGB")
    img.save(path, "PNG")
    return str(path)


def _mask(path, size, box):
    mask = Image.new("L", size, 0)
    ImageDraw.Draw(mask).rectangle(box, fill=255)
    mask.save(path, "PNG")
    return str(path)


def _provider():
    return shared_image.ImageProviderConfig(
        id="test_cf", label="test cloudflare", kind="cloudflare_inpainting", endpoint=ENDPOINT,
        model=INPAINT, api_key="test-key-not-real", headers={}, extra={},
    )


def _module(tmp_path):
    upload = tmp_path / "uploads"
    final = upload / "final"
    final.mkdir(parents=True)
    return SimpleNamespace(UPLOAD_DIR=str(upload), FINAL_DIR=str(final))


def _fake_post(monkeypatch, captured, fill=(200, 40, 60)):
    def fake_post(url, disable_env_proxy=False, **kwargs):
        payload = kwargs["json"]
        captured["payload"] = payload
        # Fake model: a solid colour at the requested size.
        out = BytesIO()
        Image.new("RGB", (payload["width"], payload["height"]), fill).save(out, "PNG")
        return _FakeResponse(out.getvalue())

    monkeypatch.setattr(shared_image, "_post_request", fake_post)


def _white_ratio(png_ints):
    mask = Image.open(BytesIO(bytes(png_ints))).convert("L")
    hist = mask.histogram()
    return hist[255] / float(mask.width * mask.height)


def test_small_mask_is_sent_as_crop_and_composite_keeps_outside_pixels(monkeypatch, tmp_path):
    module = _module(tmp_path)
    source = _photo(tmp_path / "face.png")
    mask_path = _mask(tmp_path / "mask.png", (1200, 900), (700, 420, 760, 450))
    captured = {}
    _fake_post(monkeypatch, captured)

    value = sig._call_cloudflare_inpainting(
        _provider(), "lip_shading", source, mask_path, {"detection": {}}, "prompt", 30,
    )
    payload = captured["payload"]
    assert payload["width"] == payload["height"] == 512
    # A 60x30 px mask on a 1200x900 photo covers ~0.2% of the frame; in the crop it is far larger.
    assert _white_ratio(payload["mask"]) > 0.10
    assert value.startswith("data:image/png;base64,")

    filename, meta = sig._save_constrained_provider_output(
        value, 30, source, mask_path, module, "lip_shading",
        provider_endpoint=ENDPOINT, provider_extra={},
    )
    assert meta["outside_preserved"] is True
    assert meta["visible_in_mask_change"] is True
    base = Image.open(source).convert("RGB")
    saved = Image.open(os.path.join(module.UPLOAD_DIR, filename)).convert("RGB")
    assert saved.size == base.size
    # Outside the mask the saved file is pixel-identical to the photo.
    assert base.crop((0, 0, 700, 900)).tobytes() == saved.crop((0, 0, 700, 900)).tobytes()
    # Inside the mask the model colour lands.
    inside = saved.getpixel((730, 435))
    assert inside[0] > 150 and inside[1] < 120


def test_crop_request_records_roi_metadata(monkeypatch, tmp_path):
    source = _photo(tmp_path / "face.png")
    mask_path = _mask(tmp_path / "mask.png", (1200, 900), (700, 420, 760, 450))
    captured = {}
    _fake_post(monkeypatch, captured)
    provider = _provider()
    sig._call_cloudflare_inpainting(provider, "lip_shading", source, mask_path, {"detection": {}}, "p", 30)
    meta = provider.extra["_last_request_meta"]
    assert meta["roi_crop"] is True
    x0, y0, x1, y1 = meta["roi_box"]
    assert x0 <= 700 and x1 >= 760 and y0 <= 420 and y1 >= 450
    assert (x1 - x0) == (y1 - y0) == meta["roi_side"]
    assert meta["frame_mask_coverage_ratio"] < 0.01


def test_large_mask_falls_back_to_full_frame(monkeypatch, tmp_path):
    source = _photo(tmp_path / "small.png", size=(400, 300))
    # Band-shaped mask: its crop square would be >= the short side, so the full frame is used.
    mask_path = _mask(tmp_path / "band.png", (400, 300), (120, 120, 280, 180))
    captured = {}
    _fake_post(monkeypatch, captured)
    provider = _provider()
    sig._call_cloudflare_inpainting(provider, "hair_color", source, mask_path, {"detection": {}}, "p", 30)
    assert provider.extra["_last_request_meta"]["roi_crop"] is False
    assert captured["payload"]["width"] <= 512


def test_empty_mask_is_rejected_before_any_model_call(monkeypatch, tmp_path):
    source = _photo(tmp_path / "face.png")
    mask_path = str(tmp_path / "empty.png")
    Image.new("L", (1200, 900), 0).save(mask_path, "PNG")  # all black: nothing to edit
    captured = {}
    _fake_post(monkeypatch, captured)
    with pytest.raises(sig.ServiceImageGenerationError):
        sig._call_cloudflare_inpainting(_provider(), "lip_shading", source, mask_path, {"detection": {}}, "p", 30)
    assert "payload" not in captured


def test_roi_square_stays_inside_image_bounds():
    assert sig._roi_square((0, 0, 10, 10), 1000, 800) == (0, 0, 128, 128)
    assert sig._roi_square((990, 790, 1000, 800), 1000, 800) == (872, 672, 1000, 800)
    # A crop that would cover the whole short side is not useful: caller uses full frame.
    assert sig._roi_square((10, 10, 300, 300), 400, 300) is None


def test_landmarks_requirements_never_pull_opencv_contrib():
    """MediaPipe must be installed with --no-deps; the recipe must not add opencv-contrib."""
    from pathlib import Path

    root = Path(__file__).resolve().parents[2]
    lines = [ln.strip().lower() for ln in (root / "requirements-landmarks.txt").read_text(encoding="utf-8").splitlines()]
    requirements = [ln for ln in lines if ln and not ln.startswith("#")]
    assert not any(ln.startswith("opencv-contrib") for ln in requirements)
    assert "opencv-python-headless==4.11.0.86" in requirements
    assert not any(ln.startswith("mediapipe") for ln in requirements)  # installed separately with --no-deps
