# -*- coding: utf-8 -*-
"""Phase 1/1.5/2 contract for modular Buti AI eyebrow mirror."""
import os
import re
from io import BytesIO
from pathlib import Path

os.environ.setdefault("SECRET_KEY", "arena-test-secret-for-buti-ai-tests-32chars")
ROOT = Path(__file__).resolve().parents[2]

from giso.app import create_app
from giso.base import get_giso_db_conn
from giso.buti_ai.eyebrow import ai as eyebrow_ai
from giso.buti_ai.eyebrow import flow as eyebrow_flow
from giso.buti_ai.eyebrow.flow import get_mirror_services
from giso.buti_ai.eyebrow.options import (
    DEFAULT_CHANGE_LEVEL,
    DEFAULT_STYLE,
    normalize_change_level,
    normalize_style_key,
)
from giso.buti_ai.eyebrow.preview import build_before_after_preview
from giso.buti_ai.eyebrow.result import build_eyebrow_result
from giso.buti_ai.schema import init_buti_ai_db


def _cleanup_buti_ai_sessions():
    init_buti_ai_db()
    with get_giso_db_conn() as conn:
        conn.execute(
            "DELETE FROM buti_ai_sessions WHERE service_type=? AND status IN (?, ?, ?, ?, ?)",
            ("eyebrow", "mvp_demo", "mvp_photo_received", "mvp_guided_preview", "photo_ready_final_design", "ai_analyzed"),
        )
        conn.commit()


def test_eyebrow_module_keeps_product_options_out_of_routes():
    assert normalize_style_key("microblading") == "microblading"
    assert normalize_style_key("bad-value") == DEFAULT_STYLE
    assert normalize_change_level("medium") == "medium"
    assert normalize_change_level("bad-value") == DEFAULT_CHANGE_LEVEL

    services = get_mirror_services("/analysis/mirror/eyebrow")
    assert services[0]["key"] == "eyebrow"
    assert services[0]["href"] == "/analysis/mirror/eyebrow"

    result = build_eyebrow_result(
        "microblading",
        "medium",
        {"ok": False, "reason": "demo"},
        demo_mode=True,
    )
    assert result["style_key"] == "microblading"
    assert result["change_key"] == "medium"
    assert result["demo_mode"] is True
    assert "میکروبلیدینگ" in result["style"]["label"]


def test_buti_ai_routes_and_analysis_card_are_rendered_from_module():
    app = create_app()
    client = app.test_client()

    analysis = client.get("/analysis")
    assert analysis.status_code == 200
    analysis_text = analysis.get_data(as_text=True)
    assert "آینه زیبایی گیسو" in analysis_text
    assert "مسیر انتخاب خدمت، مدل، آپلود عکس و طراحی عکس نهایی" in analysis_text
    assert "buti_ai/_analysis_mirror_card.html" not in analysis_text

    mirror = client.get("/analysis/mirror")
    assert mirror.status_code == 200
    assert "آینه ابرو گیسو" in mirror.get_data(as_text=True)

    eyebrow = client.get("/analysis/mirror/eyebrow")
    assert eyebrow.status_code == 200
    eyebrow_text = eyebrow.get_data(as_text=True)
    assert "کدام مدل به سلیقه‌ات نزدیک‌تر است؟" in eyebrow_text
    assert "میکروبلیدینگ ظریف" in eyebrow_text
    assert "شیدینگ پودری" in eyebrow_text
    assert "اول کیفیت عکس بررسی می‌شود" not in eyebrow_text
    assert "نمونه بدون عکس" not in eyebrow_text
    assert "bti-eyebrow-hero-photo" not in eyebrow_text
    assert "bti-eyebrow-hero-copy" not in eyebrow_text

    token = re.search(r'name="csrf_token" value="([^"]+)"', eyebrow_text).group(1)
    selected = client.post(
        "/analysis/mirror/eyebrow/model",
        data={"csrf_token": token, "style": "natural", "change_level": "medium"},
        follow_redirects=True,
    )
    upload_text = selected.get_data(as_text=True)
    assert selected.status_code == 200
    assert "عکس واضح صورت را بفرست" in upload_text
    assert "اول کیفیت عکس بررسی می‌شود" in upload_text
    assert "نمونه بدون عکس" not in upload_text
    assert upload_text.find("bti-upload-action-card") < upload_text.find("bti-upload-sample-card")

    ping = client.get("/analysis/mirror/ping")
    assert ping.status_code == 200
    assert ping.get_json()["module"] == "buti_ai_ready"


def test_buti_ai_eyebrow_real_photo_step_flow_with_csrf(monkeypatch):
    app = create_app()
    _cleanup_buti_ai_sessions()
    client = app.test_client()

    monkeypatch.setattr(eyebrow_flow, "check_photo_quality", lambda path: {
        "status": "ai_checked", "ok": True, "message": "عکس مناسب است.", "checks": {}, "reasons": []
    })
    monkeypatch.setattr(eyebrow_flow, "detect_eyebrow_regions", lambda path, allow_fallback=False: {
        "ok": True,
        "method": "pytest_roi",
        "confidence": 0.9,
        "image_width": 640,
        "image_height": 820,
        "regions": [
            {"side": "left", "x": 190, "y": 250, "width": 95, "height": 30},
            {"side": "right", "x": 350, "y": 250, "width": 95, "height": 30},
        ],
    })

    page = client.get("/analysis/mirror/eyebrow")
    assert page.status_code == 200
    token = re.search(r'name="csrf_token" value="([^"]+)"', page.get_data(as_text=True)).group(1)
    step = client.post(
        "/analysis/mirror/eyebrow/model",
        data={"csrf_token": token, "style": "microblading", "change_level": "medium"},
        follow_redirects=True,
    )
    assert step.status_code == 200
    upload_text = step.get_data(as_text=True)
    assert "انتخاب شما" in upload_text
    assert "میکروبلیدینگ ظریف" in upload_text
    token = re.search(r'name="csrf_token" value="([^"]+)"', upload_text).group(1)
    photo = (ROOT / "giso/buti_ai/static/brows/upload_face_sample.jpg").read_bytes()

    response = client.post(
        "/analysis/mirror/eyebrow/upload",
        data={"csrf_token": token, "photo": (BytesIO(photo), "real-face.jpg")},
        content_type="multipart/form-data",
        follow_redirects=True,
    )
    assert response.status_code == 200
    text = response.get_data(as_text=True)
    assert "همان مدل انتخابی آماده طراحی است" in text
    assert "عکس واقعی شما" in text
    assert "میکروبلیدینگ ظریف" in text
    assert "/analysis/mirror/eyebrow/uploads/" in text

    final_token = re.findall(r'name="csrf_token" value="([^"]+)"', text)[-1]
    final_response = client.post(
        "/analysis/mirror/eyebrow/finalize",
        data={"csrf_token": final_token, "final_style": "microblading"},
        follow_redirects=True,
    )
    assert final_response.status_code == 200
    final_text = final_response.get_data(as_text=True)
    assert "ورود لازم است" in final_text
    assert "میکروبلیدینگ ظریف" in final_text
    assert "طراحی عکس نهایی" in final_text

    _cleanup_buti_ai_sessions()





def test_eyebrow_upload_preserves_every_selected_model_as_final_source(tmp_path, monkeypatch):
    """هر مدل انتخابی کاربر بعد از آپلود عکس، تنها منبع طراحی نهایی می‌ماند."""
    from giso.buti_ai.eyebrow import upload as eyebrow_upload
    from giso.buti_ai.eyebrow.final_design import FINAL_DESIGN_SESSION_KEY
    from giso.buti_ai.eyebrow.options import EYEBROW_STYLES

    app = create_app()
    _cleanup_buti_ai_sessions()
    client = app.test_client()

    monkeypatch.setattr(eyebrow_flow, "check_photo_quality", lambda path: {
        "status": "ai_checked", "ok": True, "message": "عکس مناسب است.", "checks": {}, "reasons": []
    })
    monkeypatch.setattr(eyebrow_flow, "detect_eyebrow_regions", lambda path, allow_fallback=False: {
        "ok": True,
        "method": "pytest_roi",
        "confidence": 0.9,
        "image_width": 640,
        "image_height": 820,
        "regions": [
            {"side": "left", "x": 190, "y": 250, "width": 95, "height": 30},
            {"side": "right", "x": 350, "y": 250, "width": 95, "height": 30},
        ],
    })
    monkeypatch.setattr(
        eyebrow_flow,
        "save_eyebrow_photo",
        lambda file_storage: eyebrow_upload.save_eyebrow_photo(file_storage, upload_dir=str(tmp_path)),
    )

    photo = (ROOT / "giso/buti_ai/static/brows/upload_face_sample.jpg").read_bytes()
    for style_key, style_meta in EYEBROW_STYLES.items():
        page = client.get("/analysis/mirror/eyebrow")
        token = re.search(r'name="csrf_token" value="([^"]+)"', page.get_data(as_text=True)).group(1)
        step = client.post(
            "/analysis/mirror/eyebrow/model",
            data={"csrf_token": token, "style": style_key, "change_level": "medium"},
            follow_redirects=True,
        )
        assert step.status_code == 200
        upload_text = step.get_data(as_text=True)
        assert style_meta["label"] in upload_text
        upload_token = re.search(r'name="csrf_token" value="([^"]+)"', upload_text).group(1)
        response = client.post(
            "/analysis/mirror/eyebrow/upload",
            data={"csrf_token": upload_token, "photo": (BytesIO(photo), f"{style_key}.jpg", "image/jpg")},
            content_type="multipart/form-data",
            follow_redirects=False,
        )
        assert response.status_code == 200
        response_text = response.get_data(as_text=True)
        assert "عکس واقعی شما" in response_text
        assert "همین عکس وارد طراحی عکس نهایی می‌شود" in response_text
        assert style_meta["label"] in response_text
        with client.session_transaction() as sess:
            candidate = dict(sess[FINAL_DESIGN_SESSION_KEY])
        assert candidate["selected_style"] == style_key
        assert candidate["recommended_style"] == style_key
        assert candidate["final_style"] == style_key
        assert candidate["selected_label"] == style_meta["label"]
        assert candidate["final_label"] == style_meta["label"]
        assert candidate["change_key"] == "medium"
        assert candidate["photo_filename"].endswith(".jpg")
        assert (tmp_path / candidate["photo_filename"]).exists()
        assert candidate["eyebrow_detection"]["method"] == "pytest_roi"

    _cleanup_buti_ai_sessions()


def test_photo_quality_falls_back_from_cf1_to_next_ai_management_vision(monkeypatch):
    """اگر cf1 در تحلیل عکس خطا بدهد، اسلات بعدی مدیریت AI عکس را بررسی می‌کند."""
    from giso import ai_brain
    from giso.buti_ai import ai_models

    calls = []

    monkeypatch.setattr(ai_models, "configured_vision_chain", lambda: [
        {"provider_name": "cf1", "model_name": "@cf/meta/llama-3.2-11b-vision-instruct"},
        {"provider_name": "cf2", "model_name": "@cf/meta/llama-3.2-11b-vision-instruct"},
        {"provider_name": "openrouter", "model_name": "google/gemma-4-31b-it:free"},
    ])

    async def fake_ask_ai_vision(provider, image_path, prompt, model=None, max_tokens=1200, timeout_override=None):
        calls.append((provider, model))
        if provider == "cf1":
            return {"ok": False, "provider": provider, "model": model, "error": "HTTP 500"}
        return {
            "ok": True,
            "provider": provider,
            "model": model,
            "text": '{"ok": true, "face_visible": true, "eyebrows_visible": true, "lighting": true, "angle": true, "sharpness": true, "message": "عکس مناسب است."}',
            "raw": {},
            "error": "",
        }

    monkeypatch.setattr(ai_brain, "ask_ai_vision", fake_ask_ai_vision)
    report = eyebrow_ai.check_photo_quality("/tmp/fake-face.jpg")

    assert report["status"] == "ai_checked"
    assert report["ok"] is True
    assert report["provider"] == "cf2"
    assert calls[:2] == [
        ("cf1", "@cf/meta/llama-3.2-11b-vision-instruct"),
        ("cf2", "@cf/meta/llama-3.2-11b-vision-instruct"),
    ]

def test_eyebrow_upload_rejects_fake_and_large_files(tmp_path):
    from werkzeug.datastructures import FileStorage
    from giso.buti_ai.eyebrow import upload

    fake = FileStorage(stream=BytesIO(b"not a real image"), filename="face.jpg", content_type="image/jpeg")
    bad = upload.save_eyebrow_photo(fake, upload_dir=str(tmp_path))
    assert bad["ok"] is False
    assert bad["reason"] == "bad_content"

    large = FileStorage(
        stream=BytesIO(b"x" * (upload.MAX_UPLOAD_BYTES + 1)),
        filename="face.jpg",
        content_type="image/jpeg",
    )
    too_large = upload.save_eyebrow_photo(large, upload_dir=str(tmp_path))
    assert too_large["ok"] is False
    assert too_large["reason"] == "too_large"

    valid = FileStorage(
        stream=BytesIO((ROOT / "giso/buti_ai/static/brows/upload_face_sample.jpg").read_bytes()),
        filename="face.jpg",
        content_type="image/jpeg",
    )
    saved = upload.save_eyebrow_photo(valid, upload_dir=str(tmp_path))
    assert saved["ok"] is True
    assert saved["filename"].endswith(".jpg")
    assert (tmp_path / saved["filename"]).exists()


def test_eyebrow_ai_helpers_parse_quality_and_analysis(monkeypatch):
    calls = []

    def fake_vision(image_path, prompt, max_tokens=1000):
        calls.append((image_path, prompt, max_tokens))
        if "کیفیت عکس" in prompt:
            return {
                "ok": True,
                "provider": "test-provider",
                "model": "test-vision",
                "data": {
                    "ok": True,
                    "face_visible": True,
                    "eyebrows_visible": True,
                    "lighting": "good",
                    "angle": "front",
                    "sharpness": "good",
                    "reasons": [],
                    "message": "عکس مناسب است.",
                },
            }
        return {
            "ok": True,
            "provider": "test-provider",
            "model": "test-vision",
            "data": {
                "face_shape": "بیضی",
                "current_brow_summary": "ابروها کمی نامتقارن هستند.",
                "recommended_style": "natural",
                "change_level": "very_natural",
                "short_reason": "نچرال برای این چهره امن‌تر است.",
                "why": "فرم طبیعی با چهره هماهنگ‌تر است.",
                "face_analysis": {
                    "face_shape": "بیضی",
                    "eye_balance": "هماهنگ",
                    "brow_density": "متوسط",
                    "brow_symmetry": "متوسط",
                    "brow_arch": "ملایم",
                    "tail_position": "متعادل",
                },
                "style_scores": [
                    {"style": "natural", "score": 88, "reason": "هماهنگ‌ترین گزینه است."},
                    {"style": "microblading", "score": 72, "reason": "برای نقاط خالی خوب است."},
                    {"style": "powder", "score": 55, "reason": "ممکن است سنگین دیده شود."},
                    {"style": "combination", "score": 74, "reason": "قابل بررسی است."},
                    {"style": "giso_suggested", "score": 80, "reason": "گزینه امن است."},
                ],
                "do": ["تاج ابرو نرم بماند"],
                "avoid": ["قوس خیلی تیز"],
                "alternative_styles": ["شیدینگ خیلی سبک"],
                "confidence": "high",
            },
        }

    monkeypatch.setattr(eyebrow_ai, "_call_vision_json", fake_vision)

    quality = eyebrow_ai.check_photo_quality("/tmp/face.jpg")
    analysis = eyebrow_ai.analyze_eyebrow_photo("/tmp/face.jpg", "microblading", "clear")
    result = build_eyebrow_result(
        "microblading",
        "clear",
        {"ok": True, "filename": "face.jpg"},
        quality_report=quality,
        ai_analysis=analysis,
    )
    preview = build_before_after_preview({"ok": True, "filename": "face.jpg"}, result)

    assert quality["status"] == "ai_checked"
    assert quality["ok"] is True
    assert analysis["status"] == "ai_analyzed"
    assert result["ai_is_real"] is True
    assert result["style_key"] == "microblading"
    assert result["ai_recommended_style_key"] == "natural"
    assert result["face_shape"] == "بیضی"
    assert result["face_analysis"]["brow_density"] == "متوسط"
    assert result["style_scores"][0]["style_key"] == "microblading"
    assert result["style_scores"][0]["score"] == 72
    assert "میکروبلیدینگ" in result["short_reason"]
    assert preview["available"] is True
    assert preview["mode"] == "guided_before_after"
    assert len(calls) == 2


def test_final_candidate_uses_selected_style_even_if_ai_recommends_other():
    from giso.buti_ai.eyebrow.final_design import build_final_candidate, build_design_prompt

    result = build_eyebrow_result(
        "powder",
        "clear",
        {"ok": True, "filename": "face.jpg"},
        quality_report={"status": "ai_checked", "ok": True, "message": "عکس مناسب است."},
        ai_analysis={
            "status": "ai_analyzed",
            "ok": True,
            "data": {
                "recommended_style": "natural",
                "change_level": "very_natural",
                "short_reason": "نچرال را پیشنهاد می‌کنم.",
                "style_scores": [{"style": "natural", "score": 99, "reason": "AI"}],
            },
        },
    )
    candidate = build_final_candidate(result, {"ok": True, "filename": "face.jpg"})

    assert result["style_key"] == "powder"
    assert result["ai_recommended_style_key"] == "natural"
    assert candidate["selected_style"] == "powder"
    assert candidate["final_style"] == "powder"
    assert candidate["recommended_style"] == "powder"
    assert candidate["final_label"] == "شیدینگ پودری"
    prompt = build_design_prompt(candidate)
    assert "Selected eyebrow model: شیدینگ پودری" in prompt
    assert "Recommendation to follow" not in prompt
    assert "طبیعی و نچرال" not in prompt




def test_reference_image_comes_from_selected_final_style():
    from giso.buti_ai.eyebrow import image_generation

    candidate = {
        "selected_style": "powder",
        "selected_label": "شیدینگ پودری",
        "recommended_style": "natural",
        "final_style": "powder",
        "final_label": "شیدینگ پودری",
    }

    reference = image_generation._reference_image_path(candidate)

    assert reference.endswith("powder.jpg")
    assert Path(reference).exists()


def test_selected_model_a_and_b_stay_exactly_in_final_candidate(monkeypatch):
    from giso.buti_ai.eyebrow.final_design import build_final_candidate, build_design_prompt

    monkeypatch.setattr(eyebrow_flow, "save_eyebrow_photo", lambda file_storage: {
        "ok": True,
        "path": "/tmp/fake-face.jpg",
        "filename": "fake-face.jpg",
        "message": "عکس دریافت شد.",
    })
    monkeypatch.setattr(eyebrow_flow, "check_photo_quality", lambda path: {
        "status": "ai_checked", "ok": True, "message": "عکس مناسب است.", "checks": {}, "reasons": []
    })
    monkeypatch.setattr(eyebrow_flow, "detect_eyebrow_regions", lambda path, allow_fallback=False: {
        "ok": True,
        "method": "pytest_roi",
        "confidence": 0.9,
        "image_width": 640,
        "image_height": 820,
        "regions": [
            {"side": "left", "x": 190, "y": 250, "width": 95, "height": 30},
            {"side": "right", "x": 350, "y": 250, "width": 95, "height": 30},
        ],
    })
    monkeypatch.setattr(eyebrow_flow, "save_mirror_session", lambda **kwargs: 101)

    for style_key, label in (("natural", "طبیعی و نچرال"), ("powder", "شیدینگ پودری")):
        state = eyebrow_flow.process_eyebrow_submission(
            {"style": style_key, "change_level": "medium"},
            {"photo": object()},
        )
        assert state["result"]["style_key"] == style_key
        candidate = build_final_candidate(state["result"], state["photo_status"])
        assert candidate["selected_style"] == style_key
        assert candidate["final_style"] == style_key
        assert candidate["final_label"] == label
        assert f"Selected eyebrow model: {label}" in build_design_prompt(candidate)



def test_eyebrow_photo_post_goes_directly_to_final_auth_with_selected_model(monkeypatch):
    app = create_app()
    _cleanup_buti_ai_sessions()
    client = app.test_client()

    def fake_save(file_storage):
        assert file_storage.filename == "face.jpg"
        return {
            "ok": True,
            "path": "/tmp/buti-ai-face.jpg",
            "filename": "face.jpg",
            "message": "عکس دریافت شد.",
        }

    def fake_vision(image_path, prompt, max_tokens=1000):
        assert "کیفیت عکس" in prompt
        return {"ok": True, "data": {"ok": True, "message": "عکس مناسب است."}}

    monkeypatch.setattr(eyebrow_flow, "save_eyebrow_photo", fake_save)
    monkeypatch.setattr(eyebrow_flow, "detect_eyebrow_regions", lambda path, allow_fallback=False: {
        "ok": True,
        "method": "pytest_roi",
        "confidence": 0.9,
        "image_width": 640,
        "image_height": 820,
        "regions": [
            {"side": "left", "x": 190, "y": 250, "width": 95, "height": 30},
            {"side": "right", "x": 350, "y": 250, "width": 95, "height": 30},
        ],
    })
    monkeypatch.setattr(eyebrow_ai, "_call_vision_json", fake_vision)

    page = client.get("/analysis/mirror/eyebrow")
    token = re.search(r'name="csrf_token" value="([^"]+)"', page.get_data(as_text=True)).group(1)
    response = client.post(
        "/analysis/mirror/eyebrow",
        data={
            "csrf_token": token,
            "style": "natural",
            "change_level": "medium",
            "photo": (BytesIO(b"not-a-real-image-but-not-used"), "face.jpg"),
        },
        content_type="multipart/form-data",
        follow_redirects=True,
    )

    assert response.status_code == 200
    text = response.get_data(as_text=True)
    assert "ورود لازم است" in text
    assert "طبیعی و نچرال" in text
    assert "کامبینیشن" not in text
    assert "ثبت‌نام سریع" in text

    with client.session_transaction() as sess:
        candidate = sess["buti_ai_eyebrow_final_candidate"]
    assert candidate["selected_style"] == "natural"
    assert candidate["final_style"] == "natural"
    assert candidate["eyebrow_detection"]["method"] == "pytest_roi"

    _cleanup_buti_ai_sessions()


def test_eyebrow_quality_rejects_bad_photo(monkeypatch):
    def fake_save(file_storage):
        return {"ok": True, "path": "/tmp/bad.jpg", "filename": "bad.jpg", "message": "عکس دریافت شد."}

    def fake_vision(image_path, prompt, max_tokens=1000):
        assert "کیفیت عکس" in prompt
        return {
            "ok": True,
            "data": {
                "ok": False,
                "message": "ابروها در عکس واضح نیستند.",
                "reasons": ["eyebrows_not_visible"],
            },
        }

    monkeypatch.setattr(eyebrow_flow, "save_eyebrow_photo", fake_save)
    monkeypatch.setattr(eyebrow_ai, "_call_vision_json", fake_vision)

    state = eyebrow_flow.process_eyebrow_submission(
        {"style": "natural", "change_level": "medium"},
        {"photo": object()},
    )
    assert state["result"] is None
    assert state["error_message"] == "ابروها در عکس واضح نیستند."
    assert state["quality_report"]["status"] == "ai_checked"


def test_eyebrow_region_detector_finds_drawn_brow_bands(tmp_path):
    from PIL import Image, ImageDraw
    from giso.buti_ai.eyebrow.landmarks import detect_eyebrow_regions

    path = tmp_path / "drawn-face.jpg"
    image = Image.new("RGB", (640, 820), (218, 178, 148))
    draw = ImageDraw.Draw(image)
    draw.ellipse((140, 170, 500, 720), fill=(222, 182, 150))
    draw.rounded_rectangle((205, 265, 285, 282), radius=8, fill=(48, 32, 24))
    draw.rounded_rectangle((355, 265, 435, 282), radius=8, fill=(48, 32, 24))
    image.save(path, "JPEG")

    detection = detect_eyebrow_regions(str(path), allow_fallback=False)

    assert detection["ok"] is True
    assert detection["method"] in {"dark_pixel_band", "opencv_haar_eye", "mediapipe_face_mesh"}
    assert len(detection["regions"]) == 2
    assert detection["regions"][0]["x"] < detection["regions"][1]["x"]
    assert detection["mask"]["ok"] is True
    assert detection["mask_width"] == 640
    assert detection["mask_height"] == 820
    assert Path(detection["mask_path"]).exists()
    with Image.open(detection["mask_path"]) as mask_image:
        assert mask_image.mode == "L"
        assert mask_image.size == (640, 820)
    assert detection["mask"]["format"] == "png_luminance"
    assert detection["mask"]["polarity"] == "white_edit_black_keep"
    assert detection["mask"]["is_rectangle_mask"] is False
    assert detection["mask"]["pixel_count"] < detection["mask"]["bbox_area_sum"]
    left, right = detection["regions"]
    assert left["side"] == "left"
    assert right["side"] == "right"
    assert left["mask_pixel_count"] > 0
    assert right["mask_pixel_count"] > 0
    assert len(left["polygon"]) >= 4
    assert len(right["polygon"]) >= 4



def test_python_guided_final_design_generates_output_file(tmp_path, monkeypatch):
    from PIL import Image
    from giso.buti_ai.eyebrow import final_design

    original = tmp_path / "face.jpg"
    Image.new("RGB", (640, 820), (218, 178, 148)).save(original, "JPEG")
    monkeypatch.setattr(final_design, "EYEBROW_UPLOAD_DIR", str(tmp_path))
    monkeypatch.setattr(final_design, "FINAL_DESIGN_DIR", str(tmp_path / "final"))

    candidate = {
        "photo_filename": "face.jpg",
        "final_style": "combination",
        "final_label": "کامبینیشن",
        "change_label": "کمی تغییر",
        "short_reason": "دم ابرو کمی کامل‌تر شود.",
    }
    result = final_design.generate_python_guided_design(candidate)

    assert result["ok"] is True
    assert result["provider"] == "python_guided_composite"
    assert result["ai_inpainting"] is False
    assert result["is_ai_generated"] is False
    assert result["status"] == "non_ai_guided_preview_ready"
    assert result["filename"].startswith("final/final_eyebrow_")
    assert result["eyebrow_detection_method"] == "proportional_fallback"
    assert (tmp_path / result["filename"]).exists()


def _sample_final_candidate(filename="face.jpg"):
    return {
        "photo_filename": filename,
        "final_style": "combination",
        "final_label": "کامبینیشن",
        "recommended_style": "combination",
        "recommended_label": "کامبینیشن",
        "selected_style": "combination",
        "selected_label": "کامبینیشن",
        "service_label": "آینه ابرو گیسو / طراحی هوشمند ابرو",
        "change_key": "medium",
        "change_label": "کمی تغییر",
        "current_brow_summary": "دم ابرو کم‌پشت و قوس ملایم است.",
        "face_analysis": {"face_shape": "oval", "fit": "قوس نرم بهتر است"},
        "eyebrow_detection": {
            "ok": True,
            "method": "pytest_roi",
            "confidence": 0.9,
            "image_width": 640,
            "image_height": 820,
            "regions": [
                {"side": "left", "x": 190, "y": 250, "width": 95, "height": 30},
                {"side": "right", "x": 350, "y": 250, "width": 95, "height": 30},
            ],
        },
        "short_reason": "دم ابرو کمی کامل‌تر شود.",
        "do": ["دم ابرو مرتب شود"],
        "avoid": ["تاج ابرو خیلی تیره نشود"],
    }


def test_final_design_provider_chain_falls_back_when_not_configured(tmp_path, monkeypatch):
    from PIL import Image
    from giso.buti_ai.eyebrow import final_design, image_generation

    original = tmp_path / "face.jpg"
    Image.new("RGB", (640, 820), (218, 178, 148)).save(original, "JPEG")
    monkeypatch.setattr(final_design, "EYEBROW_UPLOAD_DIR", str(tmp_path))
    monkeypatch.setattr(final_design, "FINAL_DESIGN_DIR", str(tmp_path / "final"))

    result = image_generation.generate_final_design(_sample_final_candidate(), env={})

    assert result["ok"] is True
    assert result["provider"] == "python_guided_composite"
    assert result["configured_provider_count"] == 0
    assert result["fallback_used"] is False
    assert result["status"] == "non_ai_guided_preview_ready"
    assert result["ai_inpainting"] is False
    assert result["is_ai_generated"] is False
    assert "تنظیم نشده" in result["message"]
    assert (tmp_path / result["filename"]).exists()


def test_final_design_cloudflare_provider_success_saves_ai_output(tmp_path, monkeypatch):
    import base64
    import json
    from io import BytesIO as _BytesIO
    from PIL import Image
    from giso.buti_ai.eyebrow import final_design, image_generation

    original = tmp_path / "face.jpg"
    Image.new("RGB", (640, 820), (218, 178, 148)).save(original, "JPEG")
    output = _BytesIO()
    Image.new("RGB", (360, 460), (205, 160, 132)).save(output, "PNG")
    output_b64 = base64.b64encode(output.getvalue()).decode("ascii")

    monkeypatch.setattr(final_design, "EYEBROW_UPLOAD_DIR", str(tmp_path))
    monkeypatch.setattr(final_design, "FINAL_DESIGN_DIR", str(tmp_path / "final"))

    class FakeResponse:
        ok = True
        status_code = 200
        headers = {"content-type": "application/json"}
        text = ""
        content = b""

        def __init__(self):
            self._payload = {"result": {"image": output_b64}}
            self.text = json.dumps(self._payload)

        def json(self):
            return self._payload

    calls = []

    def fake_post(url, headers=None, data=None, files=None, timeout=None, json=None):
        calls.append({"url": url, "headers": headers or {}, "data": data or {}, "files": files or {}, "timeout": timeout})
        assert "acct-1" in url
        assert headers["Authorization"] == "Bearer secret-token"
        assert "input_image_0" in files
        assert "mask" not in files
        assert json is None
        assert "Edit ONLY the two eyebrow regions" in data["prompt"]
        assert "Selected service: آینه ابرو گیسو / طراحی هوشمند ابرو" in data["prompt"]
        assert "Selected eyebrow model: کامبینیشن" in data["prompt"]
        assert "Current eyebrow notes: دم ابرو کم‌پشت" in data["prompt"]
        assert "Real eyebrow location: Detected eyebrow polygon regions" in data["prompt"]
        assert "Do not change identity" in data["prompt"]
        return FakeResponse()

    monkeypatch.setattr(image_generation.requests, "post", fake_post)
    env = {
        "CLOUDFLARE_API_TOKEN_1": "secret-token",
        "CLOUDFLARE_ACCOUNT_ID_1": "acct-1",
        "CLOUDFLARE_MODEL": "@cf/black-forest-labs/flux-2-klein-4b",
        "BUTI_AI_IMAGE_TIMEOUT_SECONDS": "5",
    }

    result = image_generation.generate_final_design(_sample_final_candidate(), env=env)

    assert calls
    assert result["ok"] is True
    assert result["provider"] == "cloudflare_1"
    assert result["provider_label"] == "Cloudflare 1"
    assert result["model"] == "@cf/black-forest-labs/flux-2-klein-4b"
    assert result["status"] == "ai_final_ready"
    assert result["fallback_used"] is False
    assert result["attempts"][0]["ok"] is True
    assert result["filename"].startswith("final/ai_eyebrow_")
    assert (tmp_path / result["filename"]).exists()




def test_ai_provider_output_changes_only_eyebrow_mask_area(tmp_path, monkeypatch):
    """حتی اگر provider کل عکس را تغییر بدهد، ذخیره نهایی فقط mask ابرو را روی عکس اصلی اعمال می‌کند."""
    import base64
    from io import BytesIO as _BytesIO
    from PIL import Image
    from giso.buti_ai.eyebrow import final_design, image_generation

    original = tmp_path / "face.jpg"
    base_color = (218, 178, 148)
    ai_color = (28, 88, 226)
    Image.new("RGB", (640, 820), base_color).save(original, "JPEG")
    output = _BytesIO()
    Image.new("RGB", (640, 820), ai_color).save(output, "PNG")
    output_value = "data:image/png;base64," + base64.b64encode(output.getvalue()).decode("ascii")

    monkeypatch.setattr(final_design, "EYEBROW_UPLOAD_DIR", str(tmp_path))
    monkeypatch.setattr(final_design, "FINAL_DESIGN_DIR", str(tmp_path / "final"))
    monkeypatch.setattr(
        image_generation,
        "configured_image_providers",
        lambda env=None: [image_generation.ImageProviderConfig(
            id="mock_ai_provider",
            label="Mock AI Provider",
            kind="json_image",
            endpoint="https://mock.invalid/image",
            model="mock-full-face-output",
            api_key="fake",
        )],
    )
    monkeypatch.setattr(image_generation, "_call_provider", lambda *args, **kwargs: output_value)

    result = image_generation.generate_final_design(_sample_final_candidate(), env={})

    assert result["ok"] is True
    assert result["provider_output_constrained_to_eyebrow_mask"] is True
    assert result["mask_used"] is True
    assert result["mask_coverage_ratio"] < 0.08
    out_path = tmp_path / result["filename"]
    assert out_path.exists()

    saved = Image.open(out_path).convert("RGB")
    source = Image.open(original).convert("RGB").resize(saved.size)
    mask = Image.open(tmp_path / result["mask_filename"]).convert("L").resize(saved.size)

    outside_deltas = []
    inside_deltas = []
    # نمونه‌برداری شبکه‌ای: دور از mask باید تقریباً همان عکس اصلی بماند؛ داخل mask باید تغییر واضح بگیرد.
    step = 8
    for y in range(0, saved.height, step):
        for x in range(0, saved.width, step):
            s = source.getpixel((x, y))
            o = saved.getpixel((x, y))
            delta = sum(abs(int(o[i]) - int(s[i])) for i in range(3)) / 3.0
            if mask.getpixel((x, y)) < 8:
                outside_deltas.append(delta)
            elif mask.getpixel((x, y)) > 220:
                inside_deltas.append(delta)
    assert outside_deltas
    assert inside_deltas
    outside_sorted = sorted(outside_deltas)
    assert sum(outside_deltas) / len(outside_deltas) < 4.5
    assert outside_sorted[int(len(outside_sorted) * 0.99)] < 8
    assert sum(inside_deltas) / len(inside_deltas) > 40

    # نقاط حساس غیرابرو مثل گوشه‌ها و مرکز پایین صورت نباید رنگ خروجی provider را بگیرند.
    for point in ((20, 20), (saved.width - 25, 25), (saved.width // 2, saved.height - 60), (saved.width // 2, saved.height // 2)):
        sx, sy = point
        pixel = saved.getpixel((sx, sy))
        assert sum(abs(int(pixel[i]) - base_color[i]) for i in range(3)) / 3.0 < 8


def test_ai_provider_no_visible_eyebrow_change_is_rejected_and_falls_back(tmp_path, monkeypatch):
    """HTTP 200/provider image is not success unless eyebrow ROI visibly changes."""
    import base64
    from io import BytesIO as _BytesIO
    from PIL import Image
    from giso.buti_ai.eyebrow import final_design, image_generation

    original = tmp_path / "face.jpg"
    base = Image.new("RGB", (640, 820), (218, 178, 148))
    base.save(original, "JPEG")
    decoded_original = Image.open(original).convert("RGB")
    output = _BytesIO()
    decoded_original.save(output, "PNG")
    output_value = "data:image/png;base64," + base64.b64encode(output.getvalue()).decode("ascii")

    monkeypatch.setattr(final_design, "EYEBROW_UPLOAD_DIR", str(tmp_path))
    monkeypatch.setattr(final_design, "FINAL_DESIGN_DIR", str(tmp_path / "final"))
    monkeypatch.setattr(
        image_generation,
        "configured_image_providers",
        lambda env=None: [image_generation.ImageProviderConfig(
            id="mock_unchanged_provider",
            label="Mock Unchanged Provider",
            kind="json_image",
            endpoint="https://mock.invalid/image",
            model="mock-unchanged-output",
            api_key="fake",
        )],
    )
    monkeypatch.setattr(image_generation, "_call_provider", lambda *args, **kwargs: output_value)

    result = image_generation.generate_final_design(_sample_final_candidate(), env={})

    assert result["ok"] is True
    assert result["is_ai_generated"] is False
    assert result["provider"] == "python_guided_composite"
    assert result["fallback_used"] is True
    assert result["attempts"][0]["ok"] is False
    assert "تغییر قابل مشاهده" in result["attempts"][0]["error"]
    assert (tmp_path / result["filename"]).exists()


def test_cloudflare_inpainting_request_uses_real_eyebrow_mask(tmp_path, monkeypatch):
    import json
    from io import BytesIO as _BytesIO
    from PIL import Image, ImageDraw
    from giso.buti_ai import ai_models as mirror_ai_models
    from giso.buti_ai.eyebrow import final_design, image_generation

    original = tmp_path / "face.jpg"
    image = Image.new("RGB", (640, 820), (218, 178, 148))
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((205, 265, 285, 282), radius=8, fill=(48, 32, 24))
    draw.rounded_rectangle((355, 265, 435, 282), radius=8, fill=(48, 32, 24))
    image.save(original, "JPEG")
    output = _BytesIO()
    Image.new("RGB", (360, 460), (205, 160, 132)).save(output, "PNG")

    monkeypatch.setattr(final_design, "EYEBROW_UPLOAD_DIR", str(tmp_path))
    monkeypatch.setattr(final_design, "FINAL_DESIGN_DIR", str(tmp_path / "final"))

    class FakeResponse:
        ok = True
        status_code = 200
        headers = {"content-type": "image/png"}
        text = ""
        content = output.getvalue()

        def json(self):
            return {}

    calls = []

    def fake_post(url, headers=None, data=None, files=None, timeout=None, json=None):
        calls.append({"url": url, "headers": headers or {}, "data": data, "files": files, "json": json or {}})
        return FakeResponse()

    monkeypatch.setattr(image_generation.requests, "post", fake_post)
    monkeypatch.setattr(
        mirror_ai_models,
        "configured_image_provider_dicts",
        lambda limit=3: [
            {
                "id": "ai_mirror_cloudflare_1",
                "label": "مدیریت AI: cloudflare #1",
                "kind": "cloudflare_inpainting",
                "endpoint": "https://api.cloudflare.com/client/v4/accounts/acct-1/ai/run/@cf/runwayml/stable-diffusion-v1-5-inpainting",
                "model": "@cf/runwayml/stable-diffusion-v1-5-inpainting",
                "api_key": "secret-token",
                "headers": {},
                "extra": {"source": "ai_management", "priority": 1},
            }
        ],
    )

    result = image_generation.generate_final_design(_sample_final_candidate(), env=None)

    assert calls
    call = calls[0]
    assert call["url"].endswith("/ai/run/@cf/runwayml/stable-diffusion-v1-5-inpainting")
    assert call["files"] is None
    payload = call["json"]
    assert "mask" in payload
    assert "image" in payload
    assert isinstance(payload["mask"], list)
    assert isinstance(payload["image"], list)
    assert "mask_image" not in payload
    assert "input_mask" not in payload
    mask_bytes = bytes(payload["mask"])
    with Image.open(_BytesIO(mask_bytes)) as mask_image:
        mask = mask_image.convert("L")
        assert mask.size == (payload["width"], payload["height"])
        nonzero = sum(1 for px in mask.getdata() if px > 0)
        assert nonzero > 0
        assert nonzero < payload["width"] * payload["height"] * 0.18
    assert "Prompt text and ROI coordinates are only descriptive metadata" in payload["prompt"]
    assert "white pixels are editable eyebrow pixels" in payload["prompt"]
    assert result["ok"] is True
    assert result["status"] == "ai_inpainting_ready"
    assert result["ai_inpainting"] is True
    assert result["mask_used"] is True
    assert result["mask_width"] == payload["width"]
    assert result["mask_height"] == payload["height"]
    assert result["mask_polarity"] == "white_edit_black_keep"
    assert result["provider"] == "ai_mirror_cloudflare_1"
    assert result["model"] == "@cf/runwayml/stable-diffusion-v1-5-inpainting"
    assert (tmp_path / result["filename"]).exists()


def test_final_selection_keeps_selected_style_as_source_of_truth():
    from flask import session
    from giso.buti_ai.eyebrow.final_design import (
        FINAL_DESIGN_SESSION_KEY,
        update_final_selection,
    )

    app = create_app()
    with app.test_request_context("/analysis/mirror/eyebrow/finalize", method="POST"):
        session[FINAL_DESIGN_SESSION_KEY] = {
            "selected_style": "combination",
            "recommended_style": "natural",
            "final_style": "combination",
            "generation": {"ok": True, "filename": "final/old.jpg"},
            "final_design_id": 123,
        }
        candidate = update_final_selection(session, "natural")
        assert candidate["selected_style"] == "combination"
        assert candidate["recommended_style"] == "combination"
        assert candidate["final_style"] == "combination"
        assert candidate["generation"]["filename"] == "final/old.jpg"
        assert candidate["final_design_id"] == 123


def _cleanup_buti_ai_waitlist():
    init_buti_ai_db()
    with get_giso_db_conn() as conn:
        conn.execute("DELETE FROM buti_ai_waitlist WHERE service_type=?", ("eyebrow",))
        conn.commit()


def test_eyebrow_centers_redirects_to_active_brow_centers(monkeypatch):
    from giso.buti_ai import routes as buti_routes

    app = create_app()
    client = app.test_client()
    monkeypatch.setattr(buti_routes, "active_eyebrow_centers", lambda city="", limit=1: [{"id": 7}])

    response = client.get("/analysis/mirror/eyebrow/centers?city=مشهد", follow_redirects=False)

    assert response.status_code in (302, 303)
    assert "/beauty-centers" in response.headers["Location"]
    assert "service=brow" in response.headers["Location"]


def test_eyebrow_centers_no_active_center_shows_waitlist(monkeypatch):
    from giso.buti_ai import routes as buti_routes

    app = create_app()
    client = app.test_client()
    monkeypatch.setattr(buti_routes, "active_eyebrow_centers", lambda city="", limit=1: [])
    _cleanup_buti_ai_waitlist()

    response = client.get("/analysis/mirror/eyebrow/centers?city=مشهد")

    assert response.status_code == 200
    text = response.get_data(as_text=True)
    assert "فعلاً مرکز فعال ابرو پیدا نکردیم" in text
    assert "ثبت درخواست ابرو" in text
    assert "ثبت مرکز زیبایی برای خدمت ابرو" in text


def test_eyebrow_centers_waitlist_post_saves_interest(monkeypatch):
    from giso.buti_ai import routes as buti_routes

    app = create_app()
    client = app.test_client()
    monkeypatch.setattr(buti_routes, "active_eyebrow_centers", lambda city="", limit=1: [])
    _cleanup_buti_ai_waitlist()

    page = client.get("/analysis/mirror/eyebrow/centers?city=مشهد")
    token = re.search(r'name="csrf_token" value="([^"]+)"', page.get_data(as_text=True)).group(1)
    response = client.post(
        "/analysis/mirror/eyebrow/centers",
        data={"csrf_token": token, "city": "مشهد", "phone": "09123456789"},
    )

    assert response.status_code == 200
    text = response.get_data(as_text=True)
    assert "درخواستت ثبت شد" in text
    with get_giso_db_conn() as conn:
        row = conn.execute(
            "SELECT phone_number, city, service_type, source, status FROM buti_ai_waitlist WHERE service_type=? ORDER BY id DESC LIMIT 1",
            ("eyebrow",),
        ).fetchone()
    assert row is not None
    assert row["phone_number"] == "+989123456789"
    assert row["city"] == "مشهد"
    assert row["source"] == "eyebrow_no_active_center"
    assert row["status"] == "open"
    _cleanup_buti_ai_waitlist()


def test_service_demand_records_pre_need_without_phone():
    from giso.buti_ai.services import record_service_demand, service_demand_count, total_service_interest_count

    city = "شهر تست تقاضا"
    init_buti_ai_db()
    with get_giso_db_conn() as conn:
        conn.execute("DELETE FROM buti_ai_service_demand WHERE city=? AND service_type=?", (city, "eyebrow"))
        conn.execute("DELETE FROM buti_ai_waitlist WHERE city=? AND service_type=?", (city, "eyebrow"))
        conn.commit()

    ok, row_id = record_service_demand(
        None,
        city,
        "eyebrow",
        source="pytest_no_center",
        dedupe_key="pytest-no-center-demand",
        payload={"final_style": "natural"},
    )
    ok2, row_id2 = record_service_demand(
        None,
        city,
        "eyebrow",
        source="pytest_no_center",
        dedupe_key="pytest-no-center-demand",
        payload={"final_style": "natural"},
    )

    assert ok is True
    assert ok2 is True
    assert row_id == row_id2
    assert service_demand_count("eyebrow", city=city) == 1
    assert total_service_interest_count("eyebrow", city=city) == 1

    with get_giso_db_conn() as conn:
        conn.execute("DELETE FROM buti_ai_service_demand WHERE city=? AND service_type=?", (city, "eyebrow"))
        conn.commit()



def test_eyebrow_center_suggestions_are_ranked_and_explain_reservation():
    from giso.buti_ai.eyebrow.centers import enrich_eyebrow_center_suggestions

    centers = [
        {"name": "عمومی", "city": "تهران", "services": [], "service_labels": [], "feedback": {}},
        {"name": "ابرو مشهد", "city": "مشهد", "services": ["brow"], "service_labels": ["خدمات ابرو"], "feedback": {"score100": 90, "label": "عالی"}},
    ]
    result = enrich_eyebrow_center_suggestions(centers, {"final_label": "میکروبلیدینگ ظریف"}, city="مشهد")
    assert result[0]["name"] == "ابرو مشهد"
    assert "خدمات ابرو" in result[0]["mirror_tags"]
    assert "میکروبلیدینگ ظریف" in result[0]["mirror_match_reason"]

def _render_final_design_template(center_suggestions):
    from flask import render_template
    from giso.buti_ai.eyebrow.centers import enrich_eyebrow_center_suggestions

    app = create_app()
    candidate = _sample_final_candidate()
    with app.test_request_context("/analysis/mirror/eyebrow/final"):
        return render_template(
            "buti_ai/eyebrow_final_design.html",
            candidate=candidate,
            generation={
                "ok": True,
                "filename": "final/final_eyebrow_test.jpg",
                "provider": "python_guided_composite",
                "model": "pillow_brow_overlay_v1",
                "message": "طراحی عکس نهایی راهنما آماده شد.",
            },
            center_city="مشهد",
            center_suggestions=enrich_eyebrow_center_suggestions(center_suggestions, candidate=candidate, city="مشهد"),
            center_demand_count=4,
            centers_url="/beauty-centers?service=brow&city=مشهد",
            register_center_url="/beauty-centers/register",
            default_phone="09123456789",
        )


def test_final_design_template_shows_inline_center_suggestions():
    html = _render_final_design_template([
        {
            "name": "مرکز ابروی تست",
            "slug": "test-brow-center",
            "city": "مشهد",
            "region": "سجاد",
            "type_label": "سالن زیبایی",
            "image_path": "",
            "price_level_label": "متعادل",
            "feedback": {"label": "رضایت خوب", "score100": 85},
            "services": ["brow"],
            "service_labels": ["خدمات ابرو"],
        }
    ])

    assert "مراکز پیشنهادی برای خدمات ابرو" in html
    assert "مرکز ابروی تست" in html
    assert "رزرو/بررسی زمان" in html
    assert "مشاهده مرکز" in html
    assert "مشاهده همه مراکز ابرو" in html
    assert "برای اجرای" in html
    assert "راهنمای هوشمند قبل از انتخاب مرکز" in html
    assert "این تصویر، راهنمای غیر AI برای طراحی عکس نهایی است" in html
    assert "طراحی راهنمای غیر AI آماده شد" in html


def test_final_design_template_shows_inline_waitlist_when_no_centers():
    html = _render_final_design_template([])

    assert "فعلاً مرکز فعال برای این خدمت ثبت نشده" in html
    assert "ثبت درخواست اطلاع‌رسانی" in html
    assert "تقاضای ثبت‌شده مشهد برای ابرو: 4" in html
    assert "ثبت مرکز زیبایی برای خدمت ابرو" in html
    assert "راهنمای هوشمند قبل از انتخاب مرکز" in html


def test_cloudflare_cf_alias_and_account_root_builder():
    from giso.ai_models_registry import get_image_models, normalize_provider_name
    from giso.ai_brain import (
        cloudflare_account_id_from_url,
        normalize_cloudflare_api_root,
    )

    assert normalize_provider_name("cf") == "cloudflare"
    assert normalize_provider_name("Cloudflare Workers AI") == "cloudflare"
    cf_images = get_image_models("cf")
    assert cf_images[0]["id"] == "@cf/black-forest-labs/flux-2-klein-4b"
    assert any(
        m["id"] == "@cf/runwayml/stable-diffusion-v1-5-inpainting"
        and m.get("image_kind") == "cloudflare_inpainting"
        and m.get("auto_assign") is False
        for m in cf_images
    )
    root = normalize_cloudflare_api_root("", "ba0fec1e8a6deda27719c582e4d8eb9d", require_account=True)
    assert root == "https://api.cloudflare.com/client/v4/accounts/ba0fec1e8a6deda27719c582e4d8eb9d/ai/run"
    assert cloudflare_account_id_from_url(root) == "ba0fec1e8a6deda27719c582e4d8eb9d"
    assert normalize_cloudflare_api_root("", root, require_account=True) == root
    assert normalize_cloudflare_api_root("https://api.cloudflare.com/client/v4/accounts/acct/ai", "") == "https://api.cloudflare.com/client/v4/accounts/acct/ai/run"


def test_final_design_reads_ai_management_image_provider(tmp_path, monkeypatch):
    import base64
    import json
    from io import BytesIO as _BytesIO
    from PIL import Image
    from giso.buti_ai.eyebrow import final_design, image_generation
    from giso.buti_ai import ai_models as mirror_ai_models

    original = tmp_path / "face.jpg"
    Image.new("RGB", (640, 820), (218, 178, 148)).save(original, "JPEG")
    output = _BytesIO()
    Image.new("RGB", (360, 460), (205, 160, 132)).save(output, "PNG")
    output_b64 = base64.b64encode(output.getvalue()).decode("ascii")

    monkeypatch.setattr(final_design, "EYEBROW_UPLOAD_DIR", str(tmp_path))
    monkeypatch.setattr(final_design, "FINAL_DESIGN_DIR", str(tmp_path / "final"))
    monkeypatch.setattr(
        mirror_ai_models,
        "configured_image_provider_dicts",
        lambda limit=3: [
            {
                "id": "ai_mirror_cloudflare_1",
                "label": "مدیریت AI: cloudflare #1",
                "kind": "cloudflare",
                "endpoint": "https://api.cloudflare.com/client/v4/accounts/acct-1/ai/run/@cf/black-forest-labs/flux-2-klein-4b",
                "model": "@cf/black-forest-labs/flux-2-klein-4b",
                "api_key": "secret-token",
                "headers": {},
                "extra": {"source": "ai_management"},
            }
        ],
    )

    class FakeResponse:
        ok = True
        status_code = 200
        headers = {"content-type": "application/json"}
        content = b""

        def __init__(self):
            self._payload = {"result": {"image": output_b64}}
            self.text = json.dumps(self._payload)

        def json(self):
            return self._payload

    calls = []

    def fake_post(url, headers=None, data=None, files=None, timeout=None, json=None):
        calls.append({"url": url, "headers": headers or {}, "data": data or {}, "files": files or {}})
        return FakeResponse()

    monkeypatch.setattr(image_generation.requests, "post", fake_post)

    result = image_generation.generate_final_design(_sample_final_candidate(), env=None)

    assert calls
    assert calls[0]["url"].endswith("/ai/run/@cf/black-forest-labs/flux-2-klein-4b")
    assert "input_image_0" in calls[0]["files"]
    assert "input_image_1" not in calls[0]["files"]
    assert "mask" not in calls[0]["files"]
    assert int(calls[0]["data"]["width"]) <= 1024
    assert int(calls[0]["data"]["height"]) <= 1024
    assert "Selected eyebrow model: کامبینیشن" in calls[0]["data"]["prompt"]
    assert "Edit ONLY the two eyebrow regions" in calls[0]["data"]["prompt"]
    assert result["ok"] is True
    assert result["provider"] == "ai_mirror_cloudflare_1"
    assert result["model"] == "@cf/black-forest-labs/flux-2-klein-4b"
    assert result["fallback_used"] is False
    assert (tmp_path / result["filename"]).exists()




def test_ai_provider_output_is_constrained_to_eyebrow_mask(tmp_path, monkeypatch):
    import base64
    import json
    from io import BytesIO as _BytesIO
    from PIL import Image
    from giso.buti_ai.eyebrow import final_design, image_generation
    from giso.buti_ai import ai_models as mirror_ai_models

    original = tmp_path / "face.jpg"
    source_color = (218, 178, 148)
    Image.new("RGB", (640, 820), source_color).save(original, "JPEG")
    output = _BytesIO()
    Image.new("RGB", (640, 820), (0, 0, 0)).save(output, "PNG")
    output_b64 = base64.b64encode(output.getvalue()).decode("ascii")

    monkeypatch.setattr(final_design, "EYEBROW_UPLOAD_DIR", str(tmp_path))
    monkeypatch.setattr(final_design, "FINAL_DESIGN_DIR", str(tmp_path / "final"))
    monkeypatch.setattr(
        mirror_ai_models,
        "configured_image_provider_dicts",
        lambda limit=3: [
            {
                "id": "ai_mirror_cf1_1",
                "label": "مدیریت AI: cf1 #1",
                "kind": "cloudflare",
                "endpoint": "https://api.cloudflare.com/client/v4/accounts/acct-1/ai/run/@cf/black-forest-labs/flux-2-klein-4b",
                "model": "@cf/black-forest-labs/flux-2-klein-4b",
                "api_key": "secret-token",
                "headers": {},
                "extra": {"source": "ai_management"},
            }
        ],
    )

    class FakeResponse:
        ok = True
        status_code = 200
        headers = {"content-type": "application/json"}
        content = b""

        def __init__(self):
            self._payload = {"result": {"image": output_b64}}
            self.text = json.dumps(self._payload)

        def json(self):
            return self._payload

    monkeypatch.setattr(image_generation.requests, "post", lambda *a, **k: FakeResponse())

    result = image_generation.generate_final_design(_sample_final_candidate(), env=None)

    assert result["ok"] is True
    assert result["provider_output_constrained_to_eyebrow_mask"] is True
    assert result["mask_used"] is True
    assert result["mask_filename"].startswith("masks/")
    saved = Image.open(tmp_path / result["filename"]).convert("RGB")
    outside = saved.getpixel((20, 20))
    inside = saved.getpixel((238, 266))
    assert all(abs(outside[i] - source_color[i]) < 18 for i in range(3))
    assert sum(inside) < 80


def test_cloudflare_non_photo_edit_models_are_not_called_with_multipart():
    import pytest
    from giso.buti_ai.eyebrow import image_generation

    provider = image_generation.ImageProviderConfig(
        id="bad_cf_sdxl",
        label="SDXL",
        kind="cloudflare",
        endpoint="https://api.cloudflare.com/client/v4/accounts/acct/ai/run/@cf/stabilityai/stable-diffusion-xl-base-1.0",
        model="@cf/stabilityai/stable-diffusion-xl-base-1.0",
        api_key="secret",
    )
    with pytest.raises(image_generation.ImageProviderError) as exc:
        image_generation._call_provider(provider, "missing.jpg", "", {}, "prompt", 5)
    assert "flux-2-klein-4b" in str(exc.value)


def test_final_design_template_uses_drag_compare_slider():
    from pathlib import Path

    tpl = Path("giso/buti_ai/templates/buti_ai/eyebrow_final_design.html").read_text(encoding="utf-8")
    assert "data-bti-compare" in tpl
    assert "bti-compare-handle" in tpl
    assert "بزرگنمایی طراحی" in tpl
    assert "مشاهده ماسک ابرو" in tpl
    assert "provider_output_constrained_to_eyebrow_mask" in tpl
    assert "attempt.error" in tpl
    assert "bti-before-after bti-final-before-after" not in tpl
    assert "eyebrow_final_retry" not in tpl
    assert "تلاش دوباره با مدل‌های AI" not in tpl

    css = Path("giso/buti_ai/static/buti_ai.css").read_text(encoding="utf-8")
    assert "width: min(100%, 780px)" in css
    assert "object-fit: contain" in css
    assert "direction: ltr" in css
    assert "bti-mask-debug-link" in css
    assert "bti-retry-ai-form" not in css


def test_auto_configure_cloudflare_populates_empty_beauty_mirror_slots(tmp_path, monkeypatch):
    import sqlite3
    from giso.buti_ai import ai_models

    db_path = tmp_path / "mirror_models.db"

    def connect():
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        return conn

    monkeypatch.setattr(ai_models, "get_giso_db_conn", connect)
    ai_models.init_buti_ai_model_assignments()

    result = ai_models.auto_configure_for_provider("cf")

    assert result["ok"] is True
    assert result["added"] == 6
    rows = ai_models.list_model_assignments()
    assert len(rows) == 6
    analysis = [r for r in rows if r["task_key"] == ai_models.TASK_EYEBROW_ANALYSIS]
    validation = [r for r in rows if r["task_key"] == ai_models.TASK_MIRROR_OUTPUT_VALIDATION]
    images = [r for r in rows if r["task_key"] in ai_models.IMAGE_DESIGN_TASK_KEYS]
    assert analysis[0]["provider_name"] == "cloudflare"
    assert validation[0]["provider_name"] == "cloudflare"
    assert "vision" in analysis[0]["model_name"]
    assert "vision" in validation[0]["model_name"]
    assert len(images) == len(ai_models.IMAGE_DESIGN_TASK_KEYS)
    assert [int(r["priority"]) for r in images] == [1, 1, 1, 1]
    assert all(r["model_name"] == "@cf/black-forest-labs/flux-2-klein-4b" for r in images)
    assert all(r["image_kind"] == "cloudflare" for r in images)
    assert "@cf/runwayml/stable-diffusion-v1-5-inpainting" not in [r["model_name"] for r in images]

    second = ai_models.auto_configure_for_provider("cloudflare")
    assert second["added"] == 0




def test_repair_legacy_cloudflare_slots_replaces_json_only_models(tmp_path, monkeypatch):
    import sqlite3
    from giso.buti_ai import ai_models
    import giso.ai_brain as ai_brain

    db_path = tmp_path / "mirror_repair_slots.db"

    def connect():
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        return conn

    monkeypatch.setattr(ai_models, "get_giso_db_conn", connect)
    providers = {
        "cloudflare": {"name": "cloudflare", "kind": "cloudflare", "api_key": "t1", "enabled": 1, "base_url": "https://api.cloudflare.com/client/v4/accounts/a1/ai/run"},
        "cf2": {"name": "cf2", "kind": "cloudflare", "api_key": "t2", "enabled": 1, "base_url": "https://api.cloudflare.com/client/v4/accounts/a2/ai/run"},
        "cf3": {"name": "cf3", "kind": "cloudflare", "api_key": "t3", "enabled": 1, "base_url": "https://api.cloudflare.com/client/v4/accounts/a3/ai/run"},
    }
    monkeypatch.setattr(ai_brain, "get_ai_provider", lambda name: providers.get(str(name or "").lower()))

    ai_models.init_buti_ai_model_assignments()
    ai_models.save_model_assignment(ai_models.TASK_EYEBROW_IMAGE_DESIGN, 1, "cloudflare", "@cf/black-forest-labs/flux-2-klein-4b", image_kind="cloudflare")
    ai_models.save_model_assignment(ai_models.TASK_EYEBROW_IMAGE_DESIGN, 2, "cloudflare", "@cf/black-forest-labs/flux-1-schnell", image_kind="cloudflare")
    ai_models.save_model_assignment(ai_models.TASK_EYEBROW_IMAGE_DESIGN, 3, "cloudflare", "@cf/stabilityai/stable-diffusion-xl-base-1.0", image_kind="cloudflare")

    repaired = ai_models.repair_legacy_cloudflare_eyebrow_image_slots()

    assert repaired["ok"] is True
    assert repaired["changed"] == 2
    rows = ai_models.list_model_assignments(ai_models.TASK_EYEBROW_IMAGE_DESIGN, only_enabled=True)
    assert [(int(r["priority"]), r["provider_name"], r["model_name"]) for r in rows] == [
        (1, "cloudflare", "@cf/black-forest-labs/flux-2-klein-4b"),
        (2, "cf2", "@cf/black-forest-labs/flux-2-klein-4b"),
        (3, "cf3", "@cf/black-forest-labs/flux-2-klein-4b"),
    ]


def test_auto_configure_cf1_cf2_cf3_use_separate_cloudflare_accounts(tmp_path, monkeypatch):
    import sqlite3
    from giso.buti_ai import ai_models

    db_path = tmp_path / "mirror_cf_accounts.db"

    def connect():
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        return conn

    monkeypatch.setattr(ai_models, "get_giso_db_conn", connect)
    ai_models.init_buti_ai_model_assignments()

    r1 = ai_models.auto_configure_for_provider("cf1")
    r2 = ai_models.auto_configure_for_provider("cf2")
    r3 = ai_models.auto_configure_for_provider("cf3")

    assert r1["added"] == 6  # analysis + validation + 4 service image slots at priority 1
    assert r2["added"] == 6  # analysis + validation + 4 service image slots at priority 2
    assert r3["added"] == 6  # analysis + validation + 4 service image slots at priority 3
    rows = ai_models.list_model_assignments()
    analysis = [r for r in rows if r["task_key"] == ai_models.TASK_EYEBROW_ANALYSIS]
    validation = [r for r in rows if r["task_key"] == ai_models.TASK_MIRROR_OUTPUT_VALIDATION]
    assert [int(r["priority"]) for r in analysis] == [1, 2, 3]
    assert [r["provider_name"] for r in analysis] == ["cf1", "cf2", "cf3"]
    assert [int(r["priority"]) for r in validation] == [1, 2, 3]
    assert [r["provider_name"] for r in validation] == ["cf1", "cf2", "cf3"]
    assert all("vision" in r["model_name"] for r in analysis + validation)
    for task_key in ai_models.IMAGE_DESIGN_TASK_KEYS:
        images = [r for r in rows if r["task_key"] == task_key]
        assert [int(r["priority"]) for r in images] == [1, 2, 3]
        assert [r["provider_name"] for r in images] == ["cf1", "cf2", "cf3"]
        assert all(r["model_name"] == "@cf/black-forest-labs/flux-2-klein-4b" for r in images)
        assert all(r["image_kind"] == "cloudflare" for r in images)

    ok, _ = ai_models.save_model_assignment(
        ai_models.TASK_EYEBROW_IMAGE_DESIGN,
        2,
        "cloudflare",
        "@cf/stabilityai/stable-diffusion-xl-base-1.0",
        image_kind="cloudflare",
    )
    assert ok is True
    over = ai_models.auto_configure_for_provider("cf2", overwrite=True)
    assert over["added"] == 6
    analysis_rows = ai_models.list_model_assignments(ai_models.TASK_EYEBROW_ANALYSIS)
    analysis_slot2 = [r for r in analysis_rows if int(r["priority"]) == 2][0]
    assert analysis_slot2["provider_name"] == "cf2"
    validation_rows = ai_models.list_model_assignments(ai_models.TASK_MIRROR_OUTPUT_VALIDATION)
    validation_slot2 = [r for r in validation_rows if int(r["priority"]) == 2][0]
    assert validation_slot2["provider_name"] == "cf2"
    rows = ai_models.list_model_assignments(ai_models.TASK_EYEBROW_IMAGE_DESIGN)
    slot2 = [r for r in rows if int(r["priority"]) == 2][0]
    assert slot2["provider_name"] == "cf2"
    assert slot2["model_name"] == "@cf/black-forest-labs/flux-2-klein-4b"



def test_ai_management_preserves_cloudflare_inpainting_image_kind(tmp_path, monkeypatch):
    import sqlite3
    from giso import ai_brain
    from giso.buti_ai import ai_models

    db_path = tmp_path / "mirror_inpainting_models.db"

    def connect():
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        return conn

    monkeypatch.setattr(ai_models, "get_giso_db_conn", connect)
    ai_models.init_buti_ai_model_assignments()
    ok, _message = ai_models.save_model_assignment(
        ai_models.TASK_EYEBROW_IMAGE_DESIGN,
        1,
        "cloudflare",
        "@cf/runwayml/stable-diffusion-v1-5-inpainting",
        image_kind="cloudflare_inpainting",
    )
    assert ok is True

    def fake_provider(name):
        return {
            "name": name,
            "enabled": 1,
            "kind": "cloudflare",
            "api_key": "secret",
            "api_root": "https://api.cloudflare.com/client/v4/accounts/acct/ai/run",
            "base_url": "https://api.cloudflare.com/client/v4/accounts/acct/ai/run",
        }

    monkeypatch.setattr(ai_brain, "get_ai_provider", fake_provider)
    providers = ai_models.configured_image_provider_dicts(limit=3)

    assert len(providers) == 1
    assert providers[0]["kind"] == "cloudflare_inpainting"
    assert providers[0]["model"] == "@cf/runwayml/stable-diffusion-v1-5-inpainting"
    assert providers[0]["endpoint"].endswith("/ai/run/@cf/runwayml/stable-diffusion-v1-5-inpainting")


def test_beauty_mirror_readiness_reports_missing_and_ready(tmp_path, monkeypatch):
    import sqlite3
    from giso import ai_brain
    from giso.buti_ai import ai_models

    db_path = tmp_path / "mirror_ready.db"

    def connect():
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        return conn

    monkeypatch.setattr(ai_models, "get_giso_db_conn", connect)
    ai_models.init_buti_ai_model_assignments()

    missing = ai_models.readiness_status()
    assert missing["ready"] is False
    assert missing["analysis_ready"] is False
    assert missing["image_ready"] is False

    ai_models.save_model_assignment(ai_models.TASK_EYEBROW_ANALYSIS, 1, "cloudflare", "@cf/meta/llama-3.2-11b-vision-instruct")
    for task_key in ai_models.IMAGE_DESIGN_TASK_KEYS:
        ai_models.save_model_assignment(task_key, 1, "cloudflare", "@cf/black-forest-labs/flux-2-klein-4b", image_kind="cloudflare")

    def placeholder_provider(name):
        return {
            "name": name,
            "enabled": 1,
            "kind": "cloudflare",
            "api_key": "secret",
            "api_root": "https://api.cloudflare.com/client/v4/accounts/{account_id}/ai/run",
            "base_url": "https://api.cloudflare.com/client/v4/accounts/{account_id}/ai/run",
        }

    monkeypatch.setattr(ai_brain, "get_ai_provider", placeholder_provider)
    not_ready = ai_models.readiness_status()
    assert not_ready["image_ready"] is False
    assert any("Cloudflare" in item for item in not_ready["issues"])

    def fake_provider(name):
        return {
            "name": name,
            "enabled": 1,
            "kind": "cloudflare",
            "api_key": "secret",
            "api_root": "https://api.cloudflare.com/client/v4/accounts/acct/ai/run",
            "base_url": "https://api.cloudflare.com/client/v4/accounts/acct/ai/run",
        }

    monkeypatch.setattr(ai_brain, "get_ai_provider", fake_provider)
    ready = ai_models.readiness_status()
    assert ready["ready"] is True
    assert ready["analysis_ready"] is True
    assert ready["image_ready"] is True
    assert ready["image_ready_count"] == len(ai_models.IMAGE_DESIGN_TASK_KEYS)
    assert all(item["ready"] for item in ready["service_image_status"].values())
    assert ready["warnings"]
