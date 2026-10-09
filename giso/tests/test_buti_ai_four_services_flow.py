# -*- coding: utf-8 -*-
"""End-to-end contracts for the four Mirror final-image services.

Services: eyebrow (brow), nail, lip shading, hair colour.

The real central Aineh Giso provider/model tables are used (rows are snapshotted
and restored). Only the outbound HTTP call to Cloudflare is replaced by a local
fake model that paints the whole image, so the composite/mask guard is exercised.
No network access is required.
"""
import json
import os
import re
from io import BytesIO
from pathlib import Path

os.environ.setdefault("SECRET_KEY", "arena-test-secret-for-buti-ai-tests-32chars")
ROOT = Path(__file__).resolve().parents[2]

import pytest
from PIL import Image, ImageChops, ImageDraw, ImageOps

from giso.app import create_app
from giso.base import get_giso_db_conn
from giso.buti_ai import ai_models
from giso.buti_ai.hair_color import final_design as hair_final
from giso.buti_ai.lip import final_design as lip_final
from giso.buti_ai.nail import final_design as nail_final
from giso.buti_ai import service_image_generation
from giso.buti_ai.schema import init_buti_ai_db

INPAINT = "@cf/runwayml/stable-diffusion-v1-5-inpainting"
SAMPLES = ROOT / "giso/buti_ai/static/services"
STYLE_PHRASE = {
    "nail": ("classic_french", "classic French manicure"),
    "lip_shading": ("natural_shading", "natural lip shading"),
    "hair_color": ("chocolate_nescafe", "chocolate"),
}


# ---------------------------------------------------------------- helpers ----

def _csrf(html):
    return re.search(r'name="csrf_token" value="([^"]+)"', html).group(1)


def _clean_service_rows(service_type):
    init_buti_ai_db()
    with get_giso_db_conn() as conn:
        conn.execute("DELETE FROM buti_ai_sessions WHERE service_type=?", (service_type,))
        conn.execute("DELETE FROM buti_ai_service_demand WHERE service_type=?", (service_type,))
        conn.execute("DELETE FROM buti_ai_waitlist WHERE service_type=?", (service_type,))
        conn.execute("DELETE FROM buti_ai_final_designs WHERE service_type=?", (service_type,))
        conn.commit()


@pytest.fixture
def central_inpainting_config():
    """Enable the central Cloudflare provider with the inpainting model as slot 1.

    Snapshots and restores the provider row and all mirror-image assignments.
    """
    init_buti_ai_db()
    ai_models.init_buti_ai_model_assignments()
    with get_giso_db_conn() as conn:
        conn.row_factory = None
        cf_before = conn.execute("SELECT * FROM giso_ai_providers WHERE name='cloudflare'").fetchone()
        cols = [d[0] for d in conn.execute("SELECT * FROM giso_ai_providers LIMIT 0").description]
        assign_before = conn.execute(
            "SELECT * FROM buti_ai_model_assignments WHERE task_key=?", (ai_models.TASK_MIRROR_IMAGE_DESIGN,)
        ).fetchall()
        assign_cols = [d[0] for d in conn.execute("SELECT * FROM buti_ai_model_assignments LIMIT 0").description]
        conn.execute(
            "UPDATE giso_ai_providers SET enabled=1, api_key='test-cf-token', "
            "api_root='https://api.cloudflare.com/client/v4/accounts/test-account-123/ai/run' WHERE name='cloudflare'"
        )
        conn.execute("DELETE FROM buti_ai_model_assignments WHERE task_key=?", (ai_models.TASK_MIRROR_IMAGE_DESIGN,))
        conn.commit()
    ai_models.save_model_assignment(ai_models.TASK_MIRROR_IMAGE_DESIGN, 1, "cloudflare", INPAINT, enabled=True)
    yield
    with get_giso_db_conn() as conn:
        conn.execute("DELETE FROM buti_ai_model_assignments WHERE task_key=?", (ai_models.TASK_MIRROR_IMAGE_DESIGN,))
        for row in assign_before:
            conn.execute(
                f"INSERT INTO buti_ai_model_assignments ({','.join(assign_cols)}) VALUES ({','.join('?' for _ in assign_cols)})",
                tuple(row),
            )
        if cf_before is not None:
            conn.execute(
                "UPDATE giso_ai_providers SET enabled=?, api_key=?, api_root=? WHERE name='cloudflare'",
                (cf_before[cols.index("enabled")], cf_before[cols.index("api_key")], cf_before[cols.index("api_root")]),
            )
        conn.commit()


class FakeInpaintingModel:
    """Stands in for Cloudflare SD 1.5 inpainting. Records requests, returns a PNG
    that changes EVERY pixel (inverted), so the caller must composite it back
    outside the mask."""

    def __init__(self):
        self.calls = []

    def __call__(self, url, **kwargs):
        self.calls.append({"url": url, "json": kwargs.get("json"), "data": kwargs.get("data")})
        payload = kwargs.get("json") or {}
        raw = bytes(payload["image"])
        image = Image.open(BytesIO(raw)).convert("RGB")
        out = BytesIO()
        ImageOps.invert(image).save(out, "PNG")

        class Resp:
            ok = True
            status_code = 200
            headers = {"content-type": "image/png"}
            content = out.getvalue()
            text = ""

            def json(self):
                raise ValueError("binary")

        return Resp()


def _trust_nail_region(monkeypatch):
    """Mechanism-only: the colour nail detector is untrusted (see audit). This swaps in a
    synthetic, trusted mask so the route -> AI -> composite -> final page path can run.
    It does NOT validate nail detection on real photos."""
    def fake_detect(image_path, allow_fallback=True):
        w, h = Image.open(image_path).size
        det = {
            "ok": True, "method": "synthetic_test_mask", "is_fallback": False, "detection_reliable": True,
            "confidence": 0.9, "image_width": w, "image_height": h,
            "regions": [{"side": "nail_1", "x": int(w * 0.55), "y": int(h * 0.10),
                         "width": int(w * 0.17), "height": int(h * 0.35), "source": "synthetic_test_mask"}],
        }
        return nail_final.ensure_mask(image_path, det)

    monkeypatch.setattr(nail_final, "detect_regions", fake_detect)


@pytest.fixture
def fake_model(monkeypatch):
    model = FakeInpaintingModel()
    import requests

    monkeypatch.setattr(requests, "post", model)
    return model


def _load_final_candidate(client, session_key):
    with client.session_transaction() as sess:
        return dict(sess[session_key])


def _assert_real_ai_output(client, slug, candidate, generation, module, base_name):
    """Final file must be a valid WebP, changed inside the mask, preserved outside it."""
    assert generation["ok"] is True
    assert generation["is_ai_generated"] is True
    assert generation["ai_inpainting"] is True
    assert generation["provider_output_constrained_to_service_mask"] is True
    final_url = f"/analysis/mirror/{slug}/uploads/{generation['filename']}"
    resp = client.get(final_url)
    assert resp.status_code == 200
    assert resp.mimetype == "image/webp"

    base = Image.open(Path(module.UPLOAD_DIR) / candidate["photo_filename"]).convert("RGB")
    final = Image.open(BytesIO(resp.data)).convert("RGB")
    assert final.size == base.size
    mask = Image.open(candidate["detection"]["mask"]["path"]).convert("L")
    if mask.size != base.size:
        mask = mask.resize(base.size)
    outside = mask.point(lambda v: 0 if int(v) >= 18 else 255)  # 255 = must stay unchanged
    inside = mask.point(lambda v: 255 if int(v) >= 18 else 0)
    diff = ImageChops.difference(base, final).convert("L")
    assert ImageChops.multiply(diff, outside).getbbox() is None, "pixels outside the mask changed"
    assert ImageChops.multiply(diff, inside).getbbox() is not None, "nothing changed inside the mask"
    return final_url


# ------------------------------------------------------- prompt contracts ----

@pytest.mark.parametrize("module", [nail_final, lip_final, hair_final])
def test_service_prompt_is_short_and_carries_model_and_mask_rule(module):
    """SD 1.5 reads only 77 CLIP tokens. Measured with the CLIP BPE tokenizer:
    every style x change-level prompt is <= 68 tokens (incl. BOS/EOS), so the
    selected model and the mask-polarity rule are not truncated."""
    for style in module.STYLES:
        for change in ("very_natural", "medium", "clear"):
            prompt = module.build_design_prompt({
                "final_style": style,
                "change_key": change,
                "detection": {"mask": {"real_mask": True, "coverage_ratio": 0.05}},
            })
            assert len(prompt.split()) <= 62, prompt
            assert "white mask" in prompt and "black pixels stay unchanged" in prompt
            assert "Change level:" in prompt
            assert "آینه" not in prompt  # no Persian text reaches the CLIP encoder
    assert module.build_design_prompt({"final_style": "nope"}).startswith(
        module.build_design_prompt({"final_style": module.DEFAULT_STYLE}).split(".")[0]
    )


def test_selected_model_is_first_sentence_of_prompt():
    prompt = nail_final.build_design_prompt({"final_style": "classic_french", "change_key": "clear"})
    assert prompt.startswith("Edit the original hand photo with classic French manicure.")
    assert "clear and more visible" in prompt


def test_inpainting_payload_does_not_append_truncated_suffix(monkeypatch, tmp_path):
    captured = {}

    def fake_post(url, **kwargs):
        captured.update(kwargs.get("json") or {})
        raise RuntimeError("stop after payload")

    import requests

    monkeypatch.setattr(requests, "post", fake_post)
    provider = service_image_generation.shared_image.ImageProviderConfig(
        id="cf", label="cf", kind="cloudflare_inpainting", endpoint="https://x", model=INPAINT, api_key="k"
    )
    src = SAMPLES / "nail/upload_sample.jpg"
    mask = tmp_path / "m.png"
    mask_img = Image.new("L", Image.open(src).size, 0)
    ImageDraw.Draw(mask_img).rectangle((150, 150, 230, 210), fill=255)  # empty masks are rejected; nail cap is 0.09
    mask_img.save(mask)
    with pytest.raises(RuntimeError):
        service_image_generation._call_cloudflare_inpainting(
            provider, "nail", str(src), str(mask), {"detection": {}}, "PROMPT_HEAD.", 5
        )
    assert captured["prompt"] == "PROMPT_HEAD."


# ----------------------------------------------------- hair mask stability ----

def test_face_frame_refinement_is_idempotent(tmp_path):
    src = tmp_path / "hair.jpg"
    src.write_bytes((SAMPLES / "hair_color/upload_sample.jpg").read_bytes())
    d0 = hair_final.detect_regions(str(src), allow_fallback=True)
    once = hair_final.refine_detection_for_style(str(src), d0, "face_frame")
    twice = hair_final.refine_detection_for_style(str(src), once, "face_frame")
    assert once["mask"]["coverage_ratio"] > 0
    assert twice["mask"]["coverage_ratio"] == once["mask"]["coverage_ratio"]
    assert twice["regions"] == once["regions"]


# ---------------------------------------- route-level flow with central config ----

def test_nail_trusted_region_reaches_model_and_final_page(central_inpainting_config, fake_model, monkeypatch):
    """Pipeline check with a trusted (synthetic) nail mask: model called with central
    settings, output composited outside the mask, final page serves the file."""
    _trust_nail_region(monkeypatch)
    _clean_service_rows("nail")
    app = create_app()
    client = app.test_client()
    token = _csrf(client.get("/analysis/mirror/nail").get_data(as_text=True))
    client.post("/analysis/mirror/nail/model", data={"csrf_token": token, "style": "classic_french", "change_level": "clear"})
    upload_token = _csrf(client.get("/analysis/mirror/nail/upload").get_data(as_text=True))
    photo = (SAMPLES / "nail/upload_sample.jpg").read_bytes()
    resp = client.post(
        "/analysis/mirror/nail/upload",
        data={"csrf_token": upload_token, "photo": (BytesIO(photo), "hand.jpg", "image/jpeg")},
        content_type="multipart/form-data",
    )
    assert resp.status_code == 302
    final = client.get("/analysis/mirror/nail/final")
    assert final.status_code == 200
    candidate = _load_final_candidate(client, "buti_ai_nail_final_candidate")
    generation = candidate["generation"]

    assert fake_model.calls, "central inpainting model was never called"
    call = fake_model.calls[0]
    assert INPAINT in call["url"]
    assert "classic French manicure" in call["json"]["prompt"]
    assert "Change level: clear and more visible." in call["json"]["prompt"]
    assert generation["model"] == INPAINT

    _assert_real_ai_output(client, "nail", candidate, generation, nail_final, "nail")
    _clean_service_rows("nail")


def test_lip_sample_region_untrusted_is_explicit_error_without_model(central_inpainting_config, fake_model):
    """Colour lip mask on the sample includes chin skin and a fingertip. It is untrusted:
    no provider call, no guided preview, explicit error on the final page."""
    _clean_service_rows("lip_shading")
    app = create_app()
    client = app.test_client()
    token = _csrf(client.get("/analysis/mirror/lip-shading").get_data(as_text=True))
    client.post("/analysis/mirror/lip-shading/model", data={"csrf_token": token, "style": "natural_shading", "change_level": "medium"})
    upload_token = _csrf(client.get("/analysis/mirror/lip-shading/upload").get_data(as_text=True))
    photo = (SAMPLES / "lip_shading/upload_sample.jpg").read_bytes()
    client.post(
        "/analysis/mirror/lip-shading/upload",
        data={"csrf_token": upload_token, "photo": (BytesIO(photo), "lip.jpg", "image/jpeg")},
        content_type="multipart/form-data",
    )
    page = client.get("/analysis/mirror/lip-shading/final")
    assert page.status_code == 200
    assert "ناحیه لب روی این عکس با اطمینان کافی شناسایی نشد" in page.get_data(as_text=True)
    candidate = _load_final_candidate(client, "buti_ai_lip_shading_final_candidate")
    generation = candidate["generation"]
    assert fake_model.calls == []
    assert generation["ok"] is False
    assert generation["status"] == "region_detection_unreliable"
    assert generation["is_ai_generated"] is False
    _clean_service_rows("lip_shading")


def test_hair_positive_ai_path_with_real_mask(central_inpainting_config, fake_model, monkeypatch, tmp_path):
    """Hair's real colour mask needs a face anchor; the sample profile has none, so the
    route correctly falls back. The provider path itself is exercised with a real-ish
    hair mask built from the sample image, to prove the model is called and the output
    is composited back outside the hair mask."""
    monkeypatch.setattr(hair_final, "UPLOAD_DIR", str(tmp_path / "hair"))
    monkeypatch.setattr(hair_final, "FINAL_DIR", str(tmp_path / "hair" / "final"))
    os.makedirs(hair_final.UPLOAD_DIR, exist_ok=True)
    name = "hair_test_source.jpg"
    Image.open(SAMPLES / "hair_color/upload_sample.jpg").convert("RGB").save(Path(hair_final.UPLOAD_DIR) / name, "JPEG")
    w, h = Image.open(Path(hair_final.UPLOAD_DIR) / name).size
    hair_mask = Image.new("L", (w, h), 0)
    ImageDraw.Draw(hair_mask).ellipse((int(w * 0.20), int(h * 0.0), int(w * 0.62), int(h * 0.30)), fill=255)
    detection = {
        "ok": True, "method": "color_hair_segmentation_v1", "is_fallback": False, "detection_reliable": True,
        "image_width": w, "image_height": h, "_mask_image": hair_mask,
        "regions": [{"side": "hair", "x": int(w * 0.2), "y": 0, "width": int(w * 0.42), "height": int(h * 0.3)}],
    }
    detection = hair_final.ensure_mask(str(Path(hair_final.UPLOAD_DIR) / name), detection)
    assert detection["mask"]["real_mask"] is True

    candidate = {
        "service_key": "hair_color", "photo_filename": name, "final_style": "chocolate_nescafe",
        "change_key": "medium", "detection": detection,
    }
    generation = service_image_generation.generate_final_design("hair_color", hair_final, candidate)
    assert fake_model.calls and INPAINT in fake_model.calls[0]["url"]
    assert "chocolate" in fake_model.calls[0]["json"]["prompt"]
    assert generation["is_ai_generated"] is True
    assert generation["filename"].startswith("final/ai_hair_")
    final = Image.open(Path(hair_final.UPLOAD_DIR) / generation["filename"]).convert("RGB")
    base = Image.open(Path(hair_final.UPLOAD_DIR) / name).convert("RGB")
    outside = hair_mask.point(lambda v: 0 if int(v) >= 18 else 255)
    assert ImageChops.multiply(ImageChops.difference(base, final).convert("L"), outside).getbbox() is None


def test_provider_failure_is_not_reported_as_success(central_inpainting_config, monkeypatch, tmp_path):
    """A provider HTTP error must surface as a recorded failed attempt and a truthful
    non-AI result, never as is_ai_generated=True. Uses a trusted (synthetic) nail mask."""
    import requests
    _trust_nail_region(monkeypatch)

    class Bad:
        ok = False
        status_code = 500
        headers = {"content-type": "application/json"}
        content = b"{}"
        text = '{"errors":[{"message":"model overloaded"}]}'

        def json(self):
            return {"errors": [{"message": "model overloaded"}]}

    monkeypatch.setattr(requests, "post", lambda *a, **k: Bad())
    _clean_service_rows("nail")
    app = create_app()
    client = app.test_client()
    token = _csrf(client.get("/analysis/mirror/nail").get_data(as_text=True))
    client.post("/analysis/mirror/nail/model", data={"csrf_token": token, "style": "nude_minimal", "change_level": "medium"})
    upload_token = _csrf(client.get("/analysis/mirror/nail/upload").get_data(as_text=True))
    photo = (SAMPLES / "nail/upload_sample.jpg").read_bytes()
    client.post(
        "/analysis/mirror/nail/upload",
        data={"csrf_token": upload_token, "photo": (BytesIO(photo), "hand.jpg", "image/jpeg")},
        content_type="multipart/form-data",
    )
    client.get("/analysis/mirror/nail/final")
    candidate = _load_final_candidate(client, "buti_ai_nail_final_candidate")
    generation = candidate["generation"]
    assert generation["is_ai_generated"] is False
    assert generation["fallback_used"] is True
    assert any(a.get("ok") is False and "overloaded" in str(a.get("error", "")) for a in generation.get("attempts", []))
    _clean_service_rows("nail")


# ----------------------------------------------- untrusted region: never call model ----

@pytest.mark.parametrize("service_key,module,sample,upload_attr", [
    ("nail", nail_final, "nail/upload_sample.jpg", "UPLOAD_DIR"),
    ("lip_shading", lip_final, "lip_shading/upload_sample.jpg", "UPLOAD_DIR"),
    ("hair_color", hair_final, "hair_color/upload_sample.jpg", "UPLOAD_DIR"),
])
def test_untrusted_region_is_explicit_error_for_every_service(service_key, module, sample, upload_attr,
                                                              fake_model, central_inpainting_config,
                                                              monkeypatch, tmp_path):
    """Real photos: colour detectors are untrusted, so the service must return an explicit
    region error and must not call the provider or produce a guided preview."""
    up = tmp_path / service_key
    up.mkdir()
    name = "src.jpg"
    Image.open(SAMPLES / sample).convert("RGB").save(up / name, "JPEG")
    monkeypatch.setattr(module, upload_attr, str(up))
    candidate = {"service_key": service_key, "photo_filename": name, "final_style": module.DEFAULT_STYLE,
                 "change_key": "medium"}
    generation = service_image_generation.generate_final_design(service_key, module, candidate)
    assert generation["ok"] is False
    assert generation["status"] == "region_detection_unreliable"
    assert generation["is_ai_generated"] is False
    assert generation["fallback_used"] is False
    assert generation["message"]
    assert fake_model.calls == []


# ----------------------------------------------- eyebrow: prompt budget and guard ----

def test_eyebrow_inpainting_prompt_carries_style_change_and_mask_rule():
    from giso.buti_ai.eyebrow import final_design as eyebrow_final
    from giso.buti_ai.eyebrow.final_design import INPAINT_STYLE_EN, INPAINT_CHANGE_EN
    for style in INPAINT_STYLE_EN:
        for change in INPAINT_CHANGE_EN:
            prompt = eyebrow_final.build_inpainting_prompt({"final_style": style, "selected_style": style, "change_key": change})
            assert INPAINT_STYLE_EN[style] in prompt
            assert f"Change level: {INPAINT_CHANGE_EN[change]}." in prompt
            assert "white pixels are editable eyebrow pixels, black pixels must remain unchanged." in prompt
            # Measured with the CLIP BPE tokenizer: max 66 tokens (<= 77 incl. BOS/EOS).
            assert len(prompt.split()) <= 60, prompt


def test_eyebrow_guard_rejects_solid_replacement_and_accepts_moderate_change():
    """Policy check: a solid colour replacement of the brow area is rejected (not reported as success)."""
    from PIL import Image
    from giso.buti_ai.eyebrow import image_generation as eyebrow_ai
    base = Image.new("RGB", (200, 200), (218, 178, 148))
    mask = Image.new("L", (200, 200), 0)
    ImageDraw.Draw(mask).rectangle((60, 80, 140, 110), fill=255)
    solid = Image.new("RGB", (200, 200), (28, 88, 226))
    moderate = Image.new("RGB", (200, 200), (242, 202, 172))
    # The guard runs on the composite (provider output outside the mask is discarded first).
    solid_composite = Image.composite(solid, base, mask)
    moderate_composite = Image.composite(moderate, base, mask)
    with pytest.raises(eyebrow_ai.ImageProviderError):
        eyebrow_ai._validate_provider_visible_change(base, solid_composite, mask)
    metrics = eyebrow_ai._validate_provider_visible_change(base, moderate_composite, mask)
    assert metrics["eyebrow_roi_changed"] is True
    assert metrics["outside_mask_preserved"] is True
