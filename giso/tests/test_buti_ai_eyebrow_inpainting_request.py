"""Contract checks for the eyebrow Cloudflare inpainting request body.

These tests capture the outgoing JSON with a stub. They prove the request shape and size,
NOT the AI output. Live model output needs a real Cloudflare call (tools/eyebrow_live_check.py).
"""
from __future__ import annotations

import base64
import json
import shutil
from io import BytesIO
from pathlib import Path

import pytest
import requests
from PIL import Image

from giso.buti_ai.eyebrow import final_design, image_generation as ig

REPO = Path(__file__).resolve().parents[1]
FACE_SAMPLE = REPO / "buti_ai" / "static" / "brows" / "upload_face_sample.jpg"


class _Resp:
    def __init__(self, png_bytes):
        self.headers = {"content-type": "image/png"}
        self.content = png_bytes
        self.status_code = 200
        self.ok = True
        self.text = ""

    def json(self):
        raise ValueError("binary")


def _candidate(filename):
    return {
        "photo_filename": filename,
        "final_style": "natural",
        "selected_style": "natural",
        "change_key": "medium",
        "final_label": "طبیعی",
        "selected_label": "طبیعی",
        "service_label": "آینه ابرو گیسو",
    }


def _provider():
    return ig.ImageProviderConfig(
        id="cf_test",
        label="Cloudflare test",
        kind="cloudflare_inpainting",
        endpoint="https://api.cloudflare.com/client/v4/accounts/x/ai/run/@cf/runwayml/stable-diffusion-v1-5-inpainting",
        model="@cf/runwayml/stable-diffusion-v1-5-inpainting",
        api_key="test-key",
        extra={},
    )


@pytest.fixture
def face_upload(tmp_path, monkeypatch):
    if not FACE_SAMPLE.exists():
        pytest.skip("repo face sample missing")
    shutil.copy(FACE_SAMPLE, tmp_path / "face.jpg")
    monkeypatch.setattr(final_design, "EYEBROW_UPLOAD_DIR", str(tmp_path))
    monkeypatch.setattr(final_design, "FINAL_DESIGN_DIR", str(tmp_path / "final"))
    return tmp_path


def _capture_payload(monkeypatch, png_bytes):
    captured = {}

    def fake_post(url, **kwargs):
        captured["payload"] = kwargs["json"]
        captured["timeout"] = kwargs["timeout"]
        return _Resp(png_bytes)

    monkeypatch.setattr(ig, "_post_request", fake_post)
    return captured


def _output_png(size):
    out = BytesIO()
    Image.new("RGB", size, (200, 170, 150)).save(out, "PNG")
    return out.getvalue()


def test_inpainting_request_matches_documented_schema(face_upload, monkeypatch):
    candidate = _candidate("face.jpg")
    source = str(face_upload / "face.jpg")
    detection, mask_path = ig._real_eyebrow_mask_for_candidate(source, candidate)
    assert detection.get("regions"), "real eyebrow regions must be detected on the face sample"

    captured = _capture_payload(monkeypatch, _output_png((384, 512)))
    ig._call_cloudflare_inpainting(_provider(), source, candidate, "prompt", 60)
    payload = captured["payload"]

    # schema: prompt required; image/mask are arrays of 0..255 ints; size 256..2048, multiple of 8
    assert isinstance(payload["prompt"], str) and payload["prompt"]
    assert isinstance(payload["image"], list) and isinstance(payload["mask"], list)
    assert all(isinstance(v, int) and 0 <= v <= 255 for v in payload["image"][:5000])
    assert all(isinstance(v, int) and 0 <= v <= 255 for v in payload["mask"])
    assert 256 <= payload["width"] <= 2048 and payload["width"] % 8 == 0
    assert 256 <= payload["height"] <= 2048 and payload["height"] % 8 == 0
    assert 1 <= payload["num_steps"] <= 20

    # image bytes are a real JPEG, mask bytes are a real PNG
    img_bytes = bytes(payload["image"])
    mask_bytes = bytes(payload["mask"])
    assert img_bytes[:3] == b"\xff\xd8\xff"
    assert mask_bytes[:8] == b"\x89PNG\r\n\x1a\n"
    assert Image.open(BytesIO(img_bytes)).size == (payload["width"], payload["height"])
    assert Image.open(BytesIO(mask_bytes)).size == (payload["width"], payload["height"])


def test_request_body_is_smaller_than_png_array_version(face_upload, monkeypatch):
    candidate = _candidate("face.jpg")
    source = str(face_upload / "face.jpg")
    captured = _capture_payload(monkeypatch, _output_png((384, 512)))
    ig._call_cloudflare_inpainting(_provider(), source, candidate, "prompt", 60)
    payload = captured["payload"]

    png_image, _, _, _, _, _ = ig._prepare_cloudflare_inpainting_assets(source, ig._real_eyebrow_mask_for_candidate(source, candidate)[1])
    png_body = len(json.dumps({**payload, "image": list(png_image)}))
    jpeg_body = len(json.dumps(payload))
    assert jpeg_body < png_body / 2, (jpeg_body, png_body)


def test_connection_drop_becomes_explicit_error_with_size(face_upload, monkeypatch):
    candidate = _candidate("face.jpg")
    source = str(face_upload / "face.jpg")

    def dropped(url, **kwargs):
        from urllib3.exceptions import ProtocolError
        from http.client import RemoteDisconnected
        raise requests.exceptions.ConnectionError(
            ProtocolError("Connection aborted.", RemoteDisconnected("Remote end closed connection without response"))
        )

    monkeypatch.setattr(ig, "_post_request", dropped)
    with pytest.raises(ig.ImageProviderError) as info:
        ig._call_cloudflare_inpainting(_provider(), source, candidate, "prompt", 60)
    message = str(info.value)
    assert "RemoteDisconnected" in message or "Connection aborted" in message
    assert "حجم بدنه" in message and "KB" in message
