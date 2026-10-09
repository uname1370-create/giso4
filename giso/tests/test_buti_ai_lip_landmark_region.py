"""Lip region detection from MediaPipe FaceMesh + mock-provider round trip.

- Fail-closed without MediaPipe: always runs.
- Real close-up lip photo tests: run only when MediaPipe is installed and the photo
  exists (set GISO_TEST_LIP_CLOSEUP to a local image path). They are skipped, not passed,
  otherwise.
- The provider round trip uses a LOCAL MOCK Cloudflare-compatible HTTP server. It proves
  the request/response/composite/save/validation chain only; it is NOT a live model call.
"""
import io
import json
import os
import shutil
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import numpy as np
import pytest
from PIL import Image

from giso.buti_ai import mediapipe_landmarks
from giso.buti_ai.eyebrow import image_generation as shared_image
from giso.buti_ai.lip import final_design as lip_final
from giso.buti_ai import service_image_generation

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
LIP_SAMPLE = os.path.join(ROOT, "giso", "buti_ai", "static", "services", "lip_shading", "upload_sample.jpg")
LIP_CLOSEUP = os.environ.get(
    "GISO_TEST_LIP_CLOSEUP",
    "/home/user/buti_ai_audit/photos/close-up-woman-lips-applying-lip-gloss-f-2.jpg",
)
needs_mediapipe = pytest.mark.skipif(not mediapipe_landmarks.available(), reason="mediapipe not installed")
needs_closeup = pytest.mark.skipif(not os.path.exists(LIP_CLOSEUP), reason="close-up lip photo not available")


def _copy(tmp_path, src, name="lip_customer.jpg"):
    dst = tmp_path / name
    shutil.copy(src, dst)
    return str(dst)


def test_lip_region_is_untrusted_when_facemesh_is_unavailable(tmp_path, monkeypatch):
    """Without a FaceMesh face the colour-only lip guess must never be trusted (fail-closed)."""
    monkeypatch.setattr(mediapipe_landmarks, "face_mesh_points", lambda path: None)
    path = _copy(tmp_path, LIP_SAMPLE)
    detection = lip_final.detect_regions(path, allow_fallback=True)
    assert detection.get("detection_reliable") is not True
    assert detection.get("method") != "facemesh_lip_polygon_v1"


@needs_mediapipe
@needs_closeup
def test_lip_facemesh_region_is_trusted_and_limited_to_the_mouth(tmp_path, monkeypatch):
    path = _copy(tmp_path, LIP_CLOSEUP)
    detection = lip_final.detect_regions(path, allow_fallback=False)
    assert detection["method"] == "facemesh_lip_polygon_v1"
    assert detection["detection_reliable"] is True
    mask_info = detection["mask"]
    assert mask_info["real_mask"] is True and mask_info["ok"] is True
    assert 0.0008 <= mask_info["coverage_ratio"] <= 0.075
    region = detection["regions"][0]
    w, h = detection["image_width"], detection["image_height"]
    # Mouth-only: a small band, far from the whole face.
    assert region["width"] < 0.35 * w and region["height"] < 0.25 * h
    # The edit mask is not a solid box: the mouth opening inside the lip ring is cut out.
    mask = np.asarray(Image.open(mask_info["path"]).convert("L")) > 127
    box = mask[region["y"]:region["y"] + region["height"], region["x"]:region["x"] + region["width"]]
    assert 0.2 < float(box.mean()) < 0.95


class _MockCloudflareHandler(BaseHTTPRequestHandler):
    received = {}

    def log_message(self, *args):
        pass

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        body = json.loads(self.rfile.read(length))
        _MockCloudflareHandler.received = body
        img = Image.open(io.BytesIO(bytes(body["image"]))).convert("RGB")
        msk = np.asarray(Image.open(io.BytesIO(bytes(body["mask"]))).convert("L")) > 127
        arr = np.asarray(img).astype(np.float32)
        arr[msk] = arr[msk] * 0.35 + np.array([200, 30, 60], np.float32) * 0.65
        out = io.BytesIO()
        Image.fromarray(arr.clip(0, 255).astype(np.uint8)).save(out, "PNG")
        data = out.getvalue()
        self.send_response(200)
        self.send_header("Content-Type", "image/png")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


@pytest.fixture
def mock_cloudflare():
    server = HTTPServer(("127.0.0.1", 0), _MockCloudflareHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{server.server_address[1]}/accounts/mock/ai/run/@cf/runwayml/stable-diffusion-v1-5-inpainting"
    server.shutdown()


@needs_mediapipe
@needs_closeup
def test_lip_mock_provider_round_trip_changes_only_the_lip_mask(tmp_path, monkeypatch, mock_cloudflare):
    """Mock provider (not a live model): payload shape, receipt, composite, save and validation."""
    upload = tmp_path / "uploads"
    final = upload / "final"
    final.mkdir(parents=True)
    shutil.copy(LIP_CLOSEUP, upload / "face.jpg")
    monkeypatch.setattr(lip_final, "UPLOAD_DIR", str(upload))
    monkeypatch.setattr(lip_final, "FINAL_DIR", str(final))
    detection = lip_final.detect_regions(str(upload / "face.jpg"), allow_fallback=False)
    candidate = {
        "service_key": "lip_shading",
        "photo_filename": "face.jpg",
        "final_style": "soft_pink_tint",
        "final_label": lip_final.STYLES["soft_pink_tint"]["label"],
        "change_key": "medium",
        "detection": detection,
    }
    provider = shared_image.ImageProviderConfig(
        id="mock_cf", label="mock cloudflare", kind="cloudflare_inpainting",
        endpoint=mock_cloudflare, model=shared_image.CLOUDFLARE_INPAINTING_MODEL, api_key="mock-key",
    )
    monkeypatch.setattr(shared_image, "configured_image_providers", lambda env=None, service_key="": [provider])

    result = service_image_generation.generate_final_design("lip_shading", lip_final, candidate, env={})

    assert result["ok"] is True, result.get("message")
    assert result["is_ai_generated"] is True
    assert result["model"] == shared_image.CLOUDFLARE_INPAINTING_MODEL
    received = _MockCloudflareHandler.received
    assert {"prompt", "image", "mask", "width", "height", "num_steps", "strength", "guidance"} <= set(received)
    assert "lip" in received["prompt"].lower()
    saved = Image.open(upload / result["filename"]).convert("RGB")
    base = Image.open(upload / "face.jpg").convert("RGB").resize(saved.size)
    mask = np.asarray(Image.open(detection["mask"]["path"]).convert("L").resize(saved.size)) > 0
    diff = np.abs(np.asarray(base).astype(int) - np.asarray(saved).astype(int)).sum(axis=2)
    assert int(diff[~mask].max()) == 0, "pixels outside the lip mask must be preserved exactly"
    assert float(diff[mask].mean()) > 5, "the lip mask must visibly change"
