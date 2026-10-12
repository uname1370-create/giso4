# -*- coding: utf-8 -*-
"""Contract tests for upload → analysis → explicit final-style confirmation."""
import os
import re
from io import BytesIO
from pathlib import Path

os.environ.setdefault("SECRET_KEY", "arena-test-secret-for-buti-ai-tests-32chars")
ROOT = Path(__file__).resolve().parents[2]

from giso.app import create_app
from giso.buti_ai import routes as buti_routes
from giso.buti_ai.eyebrow import flow as eyebrow_flow
from giso.buti_ai.eyebrow.final_design import FINAL_DESIGN_SESSION_KEY, build_inpainting_prompt
from giso.buti_ai.lip import final_design as lip_final


def _csrf(response_or_text):
    text = response_or_text if isinstance(response_or_text, str) else response_or_text.get_data(as_text=True)
    return re.search(r'name="csrf_token" value="([^"]+)"', text).group(1)


def _eyebrow_photo():
    return (ROOT / "giso/buti_ai/static/brows/upload_face_sample.jpg").read_bytes()


def _lip_photo():
    return (ROOT / "giso/buti_ai/static/services/lip_shading/upload_sample.jpg").read_bytes()


def _select_eyebrow(client, style="powder", change_level="medium"):
    page = client.get("/analysis/mirror/eyebrow")
    return client.post(
        "/analysis/mirror/eyebrow/model",
        data={"csrf_token": _csrf(page), "style": style, "change_level": change_level},
        follow_redirects=True,
    )


def _select_lip(client, style="soft_pink_tint", change_level="medium"):
    page = client.get("/analysis/mirror/lip-shading")
    return client.post(
        "/analysis/mirror/lip-shading/model",
        data={"csrf_token": _csrf(page), "style": style, "change_level": change_level},
        follow_redirects=True,
    )


def test_eyebrow_validate_returns_normalized_ai_recommendation(monkeypatch):
    app = create_app()
    client = app.test_client()
    _select_eyebrow(client, style="powder", change_level="medium")

    monkeypatch.setattr(buti_routes, "check_photo_quality", lambda _path: {
        "status": "ai_checked", "ok": True, "message": "عکس مناسب است.",
        "checks": {"face_visible": True, "eyebrows_visible": True, "lighting": "good", "angle": "frontal", "sharpness": "good"},
    })
    monkeypatch.setattr(buti_routes, "analyze_eyebrow_photo", lambda *_args: {
        "status": "ai_analyzed", "ok": True,
        "data": {"recommended_style": "natural", "short_reason": "برای فرم فعلی، ظاهر طبیعی متعادل‌تر است.", "alternative_styles": ["powder"]},
    })

    upload = client.get("/analysis/mirror/eyebrow/upload")
    response = client.post(
        "/analysis/mirror/eyebrow/validate-photo",
        data={"csrf_token": _csrf(upload), "photo": (BytesIO(_eyebrow_photo()), "face.jpg", "image/jpeg")},
        content_type="multipart/form-data",
    )
    assert response.status_code == 200
    payload = response.get_json()
    assert payload["valid"] is True
    assert payload["recommendation"] == {
        "status": "ai_analyzed",
        "style": "natural",
        "label": "طبیعی و نچرال",
        "reason": "برای فرم فعلی، ظاهر طبیعی متعادل‌تر است.",
        "alternatives": ["powder"],
    }


def test_lip_validate_returns_ai_recommendation_and_unavailable_is_honest(monkeypatch):
    app = create_app()
    client = app.test_client()
    _select_lip(client, style="soft_pink_tint", change_level="clear")
    monkeypatch.setattr(lip_final, "check_photo_quality", lambda _path: {
        "status": "ai_checked", "ok": True, "message": "عکس لب مناسب است.", "checks": {"lips_visible": True},
    })
    monkeypatch.setattr(lip_final, "analyze_lip_photo", lambda *_args: {
        "status": "ai_analyzed", "ok": True,
        "data": {"recommended_style": "peach_nude", "short_reason": "تناژ گرم‌تر برای این عکس متعادل‌تر است.", "alternative_styles": ["natural_shading"]},
    })
    upload = client.get("/analysis/mirror/lip-shading/upload")
    response = client.post(
        "/analysis/mirror/lip-shading/validate-photo",
        data={"csrf_token": _csrf(upload), "photo": (BytesIO(_lip_photo()), "face.jpg", "image/jpeg")},
        content_type="multipart/form-data",
    )
    assert response.status_code == 200
    payload = response.get_json()
    assert payload["recommendation"]["status"] == "ai_analyzed"
    assert payload["recommendation"]["style"] == "peach_nude"
    assert payload["recommendation"]["label"] == "نود گلبهی"

    monkeypatch.setattr(lip_final, "analyze_lip_photo", lambda *_args: {
        "status": "ai_unavailable", "ok": None, "data": {}, "error": "provider_offline",
    })
    response = client.post(
        "/analysis/mirror/lip-shading/validate-photo",
        data={"csrf_token": _csrf(upload), "photo": (BytesIO(_lip_photo()), "face.jpg", "image/jpeg")},
        content_type="multipart/form-data",
    )
    assert response.status_code == 200
    payload = response.get_json()
    assert payload["recommendation"]["status"] == "ai_unavailable"
    assert payload["recommendation"]["style"] == "soft_pink_tint"
    assert "فعلاً در دسترس نیست" in payload["recommendation"]["reason"]


def test_first_eyebrow_upload_keeps_candidate_and_final_choice_controls_prompt(monkeypatch):
    app = create_app()
    client = app.test_client()
    upload = _select_eyebrow(client, style="powder", change_level="medium")
    monkeypatch.setattr(eyebrow_flow, "check_photo_quality", lambda _path: {
        "status": "ai_checked", "ok": True, "message": "عکس مناسب است.", "checks": {},
    })
    monkeypatch.setattr(eyebrow_flow, "analyze_eyebrow_photo", lambda *_args: {
        "status": "ai_analyzed", "ok": True,
        "data": {"recommended_style": "natural", "short_reason": "فرم نرم‌تر پیشنهاد می‌شود.", "alternative_styles": ["powder"]},
    })

    first_post = client.post(
        "/analysis/mirror/eyebrow/upload",
        data={"csrf_token": _csrf(upload), "photo": (BytesIO(_eyebrow_photo()), "face.jpg", "image/jpeg")},
        content_type="multipart/form-data",
    )
    assert first_post.status_code == 200
    assert "پیشنهاد گیسو: طبیعی و نچرال" in first_post.get_data(as_text=True)
    with client.session_transaction() as sess:
        candidate = dict(sess[FINAL_DESIGN_SESSION_KEY])
    assert candidate["selected_style"] == "powder"
    assert candidate["recommended_style"] == "natural"
    assert candidate["final_style"] == "powder"
    assert "generation" not in candidate

    final = client.post(
        "/analysis/mirror/eyebrow/finalize",
        data={"csrf_token": _csrf(first_post), "analysis_confirmed": "1", "final_style": "natural"},
        follow_redirects=False,
    )
    assert final.status_code == 302
    with client.session_transaction() as sess:
        candidate = dict(sess[FINAL_DESIGN_SESSION_KEY])
    assert candidate["selected_style"] == "powder"
    assert candidate["recommended_style"] == "natural"
    assert candidate["final_style"] == "natural"
    assert candidate["analysis_confirmed"] is True
    assert "natural soft eyebrows" in build_inpainting_prompt(candidate)
    assert "powder ombre shading" not in build_inpainting_prompt(candidate)


def test_finalize_rejects_missing_confirmation_or_foreign_candidate():
    app = create_app()
    client = app.test_client()
    upload = _select_eyebrow(client)
    no_candidate = client.post(
        "/analysis/mirror/eyebrow/finalize",
        data={"csrf_token": _csrf(upload), "analysis_confirmed": "1", "final_style": "natural"},
        follow_redirects=False,
    )
    assert no_candidate.status_code == 302
    assert no_candidate.headers["Location"].endswith("/analysis/mirror/eyebrow")

    with client.session_transaction() as sess:
        sess[FINAL_DESIGN_SESSION_KEY] = {"photo_filename": "face.jpg", "_owner_user_id": 919, "selected_style": "natural"}
    foreign = client.post(
        "/analysis/mirror/eyebrow/finalize",
        data={"csrf_token": _csrf(upload), "analysis_confirmed": "1", "final_style": "natural"},
        follow_redirects=False,
    )
    assert foreign.status_code == 302
    assert foreign.headers["Location"].endswith("/analysis/mirror/eyebrow")


def test_private_final_downloads_need_owned_candidate_and_create_pdf(tmp_path, monkeypatch):
    from PIL import Image

    source = tmp_path / "source.jpg"
    final_dir = tmp_path / "final"
    final_dir.mkdir()
    final = final_dir / "output.webp"
    Image.new("RGB", (240, 180), (225, 180, 160)).save(source, "JPEG")
    Image.new("RGB", (240, 180), (180, 80, 100)).save(final, "WEBP")
    monkeypatch.setattr(buti_routes, "EYEBROW_UPLOAD_DIR", str(tmp_path))

    app = create_app()
    owner = app.test_client()
    with owner.session_transaction() as sess:
        sess[FINAL_DESIGN_SESSION_KEY] = {
            "photo_filename": "source.jpg", "selected_style": "natural", "selected_label": "طبیعی و نچرال",
            "final_style": "natural", "final_label": "طبیعی و نچرال", "change_label": "تغییر متوسط",
            "generation": {"ok": True, "filename": "final/output.webp", "is_ai_generated": False, "message": "راهنمای غیر AI"},
        }
    image = owner.get("/analysis/mirror/eyebrow/download/image")
    assert image.status_code == 200
    assert image.headers["Content-Disposition"].startswith("attachment;")
    pdf = owner.get("/analysis/mirror/eyebrow/download/report.pdf")
    assert pdf.status_code == 200
    assert pdf.mimetype == "application/pdf"
    assert pdf.data.startswith(b"%PDF")
    assert app.test_client().get("/analysis/mirror/eyebrow/download/image").status_code == 404


def test_private_lip_downloads_need_owned_candidate_and_create_pdf(tmp_path, monkeypatch):
    from PIL import Image
    from giso.buti_ai import generic_service

    source = tmp_path / "source.jpg"
    final_dir = tmp_path / "final"
    final_dir.mkdir()
    final = final_dir / "output.webp"
    Image.new("RGB", (220, 160), (210, 160, 145)).save(source, "JPEG")
    Image.new("RGB", (220, 160), (165, 70, 90)).save(final, "WEBP")
    monkeypatch.setattr(generic_service, "uploaded_root", lambda _service_key: str(tmp_path))

    app = create_app()
    owner = app.test_client()
    with owner.session_transaction() as sess:
        sess["buti_ai_lip_shading_final_candidate"] = {
            "photo_filename": "source.jpg", "selected_style": "natural_shading", "selected_label": "شیدینگ طبیعی",
            "final_style": "natural_shading", "final_label": "شیدینگ طبیعی", "change_label": "تغییر متوسط",
            "generation": {"ok": True, "filename": "final/output.webp", "is_ai_generated": False, "message": "راهنمای غیر AI"},
        }
    image = owner.get("/analysis/mirror/lip-shading/download/image")
    assert image.status_code == 200
    assert image.headers["Content-Disposition"].startswith("attachment;")
    pdf = owner.get("/analysis/mirror/lip-shading/download/report.pdf")
    assert pdf.status_code == 200
    assert pdf.mimetype == "application/pdf"
    assert pdf.data.startswith(b"%PDF")
    assert app.test_client().get("/analysis/mirror/lip-shading/download/report.pdf").status_code == 404
