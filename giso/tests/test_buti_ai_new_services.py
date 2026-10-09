# -*- coding: utf-8 -*-
"""Contracts for the expanded Buti AI mirror services."""
import os
import re
from io import BytesIO
from pathlib import Path

os.environ.setdefault("SECRET_KEY", "arena-test-secret-for-buti-ai-tests-32chars")
ROOT = Path(__file__).resolve().parents[2]

from giso.app import create_app
from giso.base import get_giso_db_conn
from giso.buti_ai.nail import final_design as nail_final
from giso.buti_ai.lip import final_design as lip_final
from giso.buti_ai.hair_color import final_design as hair_color_final
from giso.buti_ai import generic_service
from giso.buti_ai.schema import init_buti_ai_db
from giso.buti_ai.service_catalog import SERVICE_HAIR_COLOR, SERVICE_LIP, SERVICE_NAIL, slug_for_service


def _cleanup_service(service_type="nail"):
    init_buti_ai_db()
    with get_giso_db_conn() as conn:
        conn.execute("DELETE FROM buti_ai_sessions WHERE service_type=?", (service_type,))
        conn.execute("DELETE FROM buti_ai_service_demand WHERE service_type=?", (service_type,))
        conn.execute("DELETE FROM buti_ai_waitlist WHERE service_type=?", (service_type,))
        conn.execute("DELETE FROM buti_ai_final_designs WHERE service_type=?", (service_type,))
        conn.commit()


def _csrf(html):
    return re.search(r'name="csrf_token" value="([^"]+)"', html).group(1)


def _assert_guest_final_preview(client, final_page, service_slug, service_key, session_key):
    text = final_page.get_data(as_text=True)
    assert "ورود لازم است" not in text
    assert "طراحی راهنمای غیر AI آماده شد" in text
    assert f"/analysis/mirror/{service_slug}/uploads/final/" in text
    cookie = final_page.headers.get("Set-Cookie", "")
    assert not cookie or len(cookie) < 4093

    with client.session_transaction() as sess:
        candidate = dict(sess[session_key])
    generation = candidate.get("generation") or {}
    assert generation.get("ok") is True
    assert generation.get("is_ai_generated") is False
    assert generation.get("filename", "").startswith("final/")
    assert candidate.get("final_design_id") is None

    final_file = client.get(f"/analysis/mirror/{service_slug}/uploads/{generation['filename']}")
    assert final_file.status_code == 200
    assert final_file.mimetype == "image/webp"
    with get_giso_db_conn() as conn:
        count = conn.execute(
            "SELECT COUNT(*) FROM buti_ai_final_designs WHERE service_type=? AND user_id IS NULL",
            (service_key,),
        ).fetchone()[0]
    assert count == 0
    return candidate, generation


def test_nail_mirror_uses_staged_flow_and_preserves_selected_model():
    app = create_app()
    _cleanup_service("nail")
    client = app.test_client()

    home = client.get("/analysis/mirror")
    assert home.status_code == 200
    home_text = home.get_data(as_text=True)
    assert "آینه ناخن گیسو" in home_text
    assert "/analysis/mirror/nail" in home_text

    page = client.get("/analysis/mirror/nail")
    assert page.status_code == 200
    text = page.get_data(as_text=True)
    assert "آماده طراحی" not in text
    assert "<b>۴</b> طراحی نهایی و رزرو" in text
    assert "کدام مدل را می‌خواهی روی عکس خودت ببینی؟" in text
    assert "فرنچ کلاسیک" in text
    assert "کت‌آی" in text
    token = _csrf(text)

    selected = client.post(
        "/analysis/mirror/nail/model",
        data={"csrf_token": token, "style": "classic_french", "change_level": "clear"},
        follow_redirects=True,
    )
    assert selected.status_code == 200
    upload_text = selected.get_data(as_text=True)
    assert "عکس واضح و واقعی را بفرست" in upload_text
    assert "فرنچ کلاسیک" in upload_text
    assert "نمونه بدون عکس" not in upload_text
    upload_token = _csrf(upload_text)

    photo = (ROOT / "giso/buti_ai/static/services/nail/upload_sample.jpg").read_bytes()
    response = client.post(
        "/analysis/mirror/nail/upload",
        data={"csrf_token": upload_token, "photo": (BytesIO(photo), "hand.jpg", "image/jpeg")},
        content_type="multipart/form-data",
        follow_redirects=False,
    )
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/analysis/mirror/nail/final")
    final_page = client.get(response.headers["Location"])
    assert final_page.status_code == 200
    result_text = final_page.get_data(as_text=True)
    assert "فرنچ کلاسیک" in result_text
    candidate, route_generation = _assert_guest_final_preview(
        client, final_page, "nail", "nail", "buti_ai_nail_final_candidate"
    )
    assert candidate["service_key"] == "nail"
    assert candidate["service_type"] == "nail"
    assert candidate["selected_style"] == "classic_french"
    assert candidate["final_style"] == "classic_french"
    assert candidate["final_label"] == "فرنچ کلاسیک"
    assert candidate["change_key"] == "clear"
    assert candidate["photo_filename"].startswith("nail_")

    generation = route_generation
    assert generation["ok"] is True
    assert generation["is_ai_generated"] is False
    assert generation["filename"].startswith("final/final_nail_")
    assert (Path(nail_final.UPLOAD_DIR) / generation["filename"]).exists()

    _cleanup_service("nail")


def test_lip_shading_mirror_uses_staged_flow_and_truthful_guided_output():
    app = create_app()
    _cleanup_service("lip_shading")
    client = app.test_client()

    home = client.get("/analysis/mirror")
    assert home.status_code == 200
    home_text = home.get_data(as_text=True)
    assert "آینه لب و شیدینگ گیسو" in home_text
    assert "/analysis/mirror/lip-shading" in home_text

    page = client.get("/analysis/mirror/lip-shading")
    assert page.status_code == 200
    text = page.get_data(as_text=True)
    assert "کدام مدل را می‌خواهی روی عکس خودت ببینی؟" in text
    assert "تینت صورتی ملایم" in text
    assert "رفع تیرگی و یکدست‌سازی رنگ لب" in text
    token = _csrf(text)

    selected = client.post(
        "/analysis/mirror/lip-shading/model",
        data={"csrf_token": token, "style": "soft_pink_tint", "change_level": "very_natural"},
        follow_redirects=True,
    )
    assert selected.status_code == 200
    upload_text = selected.get_data(as_text=True)
    assert "عکس واضح و واقعی را بفرست" in upload_text
    assert "تینت صورتی ملایم" in upload_text
    upload_token = _csrf(upload_text)

    photo = (ROOT / "giso/buti_ai/static/services/lip_shading/upload_sample.jpg").read_bytes()
    response = client.post(
        "/analysis/mirror/lip-shading/upload",
        data={"csrf_token": upload_token, "photo": (BytesIO(photo), "face.jpg", "image/jpeg")},
        content_type="multipart/form-data",
        follow_redirects=False,
    )
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/analysis/mirror/lip-shading/final")
    final_page = client.get(response.headers["Location"])
    assert final_page.status_code == 200
    result_text = final_page.get_data(as_text=True)
    assert "تینت صورتی ملایم" in result_text
    candidate, route_generation = _assert_guest_final_preview(
        client, final_page, "lip-shading", "lip_shading", "buti_ai_lip_shading_final_candidate"
    )
    assert candidate["service_key"] == "lip_shading"
    assert candidate["service_type"] == "lip_shading"
    assert candidate["beauty_center_service"] == "lip_shading"
    assert candidate["selected_style"] == "soft_pink_tint"
    assert candidate["final_style"] == "soft_pink_tint"
    assert candidate["final_label"] == "تینت صورتی ملایم"
    assert candidate["change_key"] == "very_natural"
    assert candidate["photo_filename"].startswith("lip_shading_")

    generation = route_generation
    assert generation["ok"] is True
    assert generation["is_ai_generated"] is False
    assert generation["filename"].startswith("final/final_lip_")
    assert (Path(lip_final.UPLOAD_DIR) / generation["filename"]).exists()

    _cleanup_service("lip_shading")


def test_hair_color_mirror_uses_staged_flow_and_truthful_guided_output():
    app = create_app()
    _cleanup_service("hair_color")
    client = app.test_client()

    home = client.get("/analysis/mirror")
    assert home.status_code == 200
    home_text = home.get_data(as_text=True)
    assert "آینه رنگ و لایت مو گیسو" in home_text
    assert "/analysis/mirror/hair-color" in home_text

    page = client.get("/analysis/mirror/hair-color")
    assert page.status_code == 200
    text = page.get_data(as_text=True)
    assert "کدام مدل را می‌خواهی روی عکس خودت ببینی؟" in text
    assert "بالیاژ کاراملی" in text
    assert "دودی زیتونی ملایم" in text
    token = _csrf(text)

    selected = client.post(
        "/analysis/mirror/hair-color/model",
        data={"csrf_token": token, "style": "caramel_balayage", "change_level": "medium"},
        follow_redirects=True,
    )
    assert selected.status_code == 200
    upload_text = selected.get_data(as_text=True)
    assert "عکس واضح و واقعی را بفرست" in upload_text
    assert "بالیاژ کاراملی" in upload_text
    upload_token = _csrf(upload_text)

    photo = (ROOT / "giso/buti_ai/static/services/hair_color/upload_sample.jpg").read_bytes()
    response = client.post(
        "/analysis/mirror/hair-color/upload",
        data={"csrf_token": upload_token, "photo": (BytesIO(photo), "hair.jpg", "image/jpeg")},
        content_type="multipart/form-data",
        follow_redirects=False,
    )
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/analysis/mirror/hair-color/final")
    final_page = client.get(response.headers["Location"])
    assert final_page.status_code == 200
    result_text = final_page.get_data(as_text=True)
    assert "بالیاژ کاراملی" in result_text
    candidate, route_generation = _assert_guest_final_preview(
        client, final_page, "hair-color", "hair_color", "buti_ai_hair_color_final_candidate"
    )
    assert candidate["service_key"] == "hair_color"
    assert candidate["service_type"] == "hair_color"
    assert candidate["beauty_center_service"] == "hair_color"
    assert candidate["selected_style"] == "caramel_balayage"
    assert candidate["final_style"] == "caramel_balayage"
    assert candidate["final_label"] == "بالیاژ کاراملی"
    assert candidate["photo_filename"].startswith("hair_color_")

    generation = route_generation
    assert generation["ok"] is True
    assert generation["is_ai_generated"] is False
    assert generation["filename"].startswith("final/final_hair_color_")
    assert (Path(hair_color_final.UPLOAD_DIR) / generation["filename"]).exists()

    _cleanup_service("hair_color")


def test_hair_mask_needs_a_face_anchor_or_a_substantial_back_view_region(tmp_path, monkeypatch):
    """A dark salon apron must not be accepted as a real hair mask."""
    from PIL import Image, ImageDraw

    salon_photo = tmp_path / "salon-sample.jpg"
    salon_photo.write_bytes((ROOT / "giso/buti_ai/static/services/hair_color/upload_sample.jpg").read_bytes())
    strict = hair_color_final.detect_regions(str(salon_photo), allow_fallback=False)
    assert strict["ok"] is False
    assert strict["method"] == "hair_not_detected"

    guided = hair_color_final.detect_regions(str(salon_photo), allow_fallback=True)
    assert guided["ok"] is True
    assert guided["is_fallback"] is True
    assert guided["mask"]["real_mask"] is False

    # A face-anchored dark-hair region remains eligible for a real mask.
    portrait = Image.new("RGB", (320, 320), (235, 235, 235))
    draw = ImageDraw.Draw(portrait)
    draw.ellipse((58, 8, 258, 292), fill=(62, 38, 24))
    draw.ellipse((118, 66, 202, 190), fill=(220, 170, 140))
    portrait_path = tmp_path / "anchored-portrait.jpg"
    portrait.save(portrait_path, "JPEG", quality=95)
    monkeypatch.setattr(hair_color_final, "_detect_face_anchor", lambda _image: (118, 66, 84, 124))
    anchored = hair_color_final.detect_regions(str(portrait_path), allow_fallback=False)
    assert anchored["ok"] is True
    assert anchored["face_anchor_detected"] is True
    assert anchored["mask"]["real_mask"] is True


def test_every_new_service_model_selection_survives_upload_and_generation():
    """هر مدل در هر خدمت باید دقیقاً همان انتخاب کاربر بماند و خروجی راهنما بسازد."""
    app = create_app()
    client = app.test_client()
    sample_paths = {
        SERVICE_NAIL: ROOT / "giso/buti_ai/static/services/nail/upload_sample.jpg",
        SERVICE_LIP: ROOT / "giso/buti_ai/static/services/lip_shading/upload_sample.jpg",
        SERVICE_HAIR_COLOR: ROOT / "giso/buti_ai/static/services/hair_color/upload_sample.jpg",
    }
    session_keys = {
        SERVICE_NAIL: "buti_ai_nail_final_candidate",
        SERVICE_LIP: "buti_ai_lip_shading_final_candidate",
        SERVICE_HAIR_COLOR: "buti_ai_hair_color_final_candidate",
    }

    for service_key in (SERVICE_NAIL, SERVICE_LIP, SERVICE_HAIR_COLOR):
        _cleanup_service(service_key)
        slug = slug_for_service(service_key)
        module = generic_service.service_module(service_key)
        sample_bytes = sample_paths[service_key].read_bytes()
        for style_key, style_meta in module.STYLES.items():
            page = client.get(f"/analysis/mirror/{slug}")
            assert page.status_code == 200
            token = _csrf(page.get_data(as_text=True))
            selected = client.post(
                f"/analysis/mirror/{slug}/model",
                data={"csrf_token": token, "style": style_key, "change_level": "medium"},
                follow_redirects=True,
            )
            assert selected.status_code == 200
            upload_text = selected.get_data(as_text=True)
            assert style_meta["label"] in upload_text
            upload_token = _csrf(upload_text)
            response = client.post(
                f"/analysis/mirror/{slug}/upload",
                data={
                    "csrf_token": upload_token,
                    "photo": (BytesIO(sample_bytes), f"{service_key}-{style_key}.jpg", "image/jpeg"),
                },
                content_type="multipart/form-data",
                follow_redirects=False,
            )
            assert response.status_code == 302
            assert response.headers["Location"].endswith(f"/analysis/mirror/{slug}/final")
            final_page = client.get(response.headers["Location"])
            assert final_page.status_code == 200
            result_text = final_page.get_data(as_text=True)
            assert style_meta["label"] in result_text
            candidate, generation = _assert_guest_final_preview(
                client, final_page, slug, service_key, session_keys[service_key]
            )
            assert candidate["service_key"] == service_key
            assert candidate["service_type"] == service_key
            assert candidate["selected_style"] == style_key
            assert candidate["final_style"] == style_key
            assert candidate["selected_label"] == style_meta["label"]
            assert candidate["final_label"] == style_meta["label"]
            assert generation["mask_used"] is True
            assert (Path(module.UPLOAD_DIR) / generation["filename"]).exists()

        _cleanup_service(service_key)


def test_all_remaining_new_services_are_publicly_active():
    app = create_app()
    client = app.test_client()

    home = client.get("/analysis/mirror")
    assert home.status_code == 200
    text = home.get_data(as_text=True)
    assert "آماده طراحی" not in text
    assert "انتخاب روز و نوبت" in text
    assert "آینه رنگ و لایت مو گیسو" in text
    assert "آینه لب و شیدینگ گیسو" in text
    assert "پیش‌نمایش رنگ مو" in text
    assert "پیش‌نمایش لب" in text
    assert "به‌زودی" not in text


def test_lip_real_ai_requires_real_mask_and_preserves_outside_mask(tmp_path, monkeypatch):
    """Provider success is truthful only when a lip-specific real mask and saved diff validation pass."""
    import base64
    from io import BytesIO as _BytesIO
    from PIL import Image, ImageDraw
    from giso.buti_ai.eyebrow import image_generation as shared_image
    from giso.buti_ai import service_image_generation

    upload_dir = tmp_path / "lip_uploads"
    final_dir = upload_dir / "final"
    upload_dir.mkdir(parents=True)
    monkeypatch.setattr(lip_final, "UPLOAD_DIR", str(upload_dir))
    monkeypatch.setattr(lip_final, "FINAL_DIR", str(final_dir))

    photo_path = upload_dir / "lip_customer.jpg"
    image = Image.new("RGB", (640, 820), (220, 178, 150))
    draw = ImageDraw.Draw(image)
    # Strong but plausible lip chroma inside the lower-face band so the local
    # detector creates a non-fallback real mask.
    draw.ellipse((230, 485, 410, 535), fill=(176, 64, 84))
    draw.ellipse((250, 520, 390, 565), fill=(198, 78, 102))
    image.save(photo_path, "JPEG", quality=94)

    detection = lip_final.detect_regions(str(photo_path), allow_fallback=False)
    assert detection["ok"] is True
    assert detection["mask"]["real_mask"] is True

    candidate = {
        "service_key": SERVICE_LIP,
        "photo_filename": photo_path.name,
        "final_style": "soft_pink_tint",
        "final_label": lip_final.STYLES["soft_pink_tint"]["label"],
        "change_label": "خیلی طبیعی",
        "detection": detection,
    }
    provider = shared_image.ImageProviderConfig(
        id="mock_lip_ai",
        label="Mock Lip AI",
        kind="json_image",
        endpoint="https://mock.invalid/lip",
        model="mock-lip-model",
        api_key="fake",
    )
    monkeypatch.setattr(
        shared_image,
        "configured_image_providers",
        lambda env=None, service_key="eyebrow": [provider],
    )
    provider_output = _BytesIO()
    Image.new("RGB", (640, 820), (60, 20, 210)).save(provider_output, "PNG")
    output_value = "data:image/png;base64," + base64.b64encode(provider_output.getvalue()).decode("ascii")
    monkeypatch.setattr(service_image_generation, "_call_provider", lambda *args, **kwargs: output_value)

    result = service_image_generation.generate_final_design(SERVICE_LIP, lip_final, candidate, env={})

    assert result["ok"] is True
    assert result["is_ai_generated"] is True
    assert result["status"] == "ai_lip_shading_ready"
    assert result["provider"] == "mock_lip_ai"
    assert result["provider_output_constrained_to_service_mask"] is True
    assert result["visible_in_mask_change"] is True
    assert result["outside_preserved"] is True
    assert result["validation"]["outside_mask_diff_ratio"] <= 0.04
    assert (upload_dir / result["filename"]).exists()


def test_lip_finalize_does_not_recover_an_unowned_upload_from_client_filename():
    """A filename alone must not rebuild a private Mirror candidate after session loss."""
    app = create_app()
    _cleanup_service("lip_shading")
    client = app.test_client()

    page = client.get("/analysis/mirror/lip-shading")
    token = _csrf(page.get_data(as_text=True))
    selected = client.post(
        "/analysis/mirror/lip-shading/model",
        data={"csrf_token": token, "style": "peach_nude", "change_level": "medium"},
        follow_redirects=True,
    )
    upload_token = _csrf(selected.get_data(as_text=True))
    photo = (ROOT / "giso/buti_ai/static/services/lip_shading/upload_sample.jpg").read_bytes()
    response = client.post(
        "/analysis/mirror/lip-shading/upload",
        data={"csrf_token": upload_token, "photo": (BytesIO(photo), "face.jpg", "image/jpeg")},
        content_type="multipart/form-data",
        follow_redirects=False,
    )
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/analysis/mirror/lip-shading/final")
    final_page = client.get(response.headers["Location"])
    assert final_page.status_code == 200
    candidate, _generation = _assert_guest_final_preview(
        client, final_page, "lip-shading", "lip_shading", "buti_ai_lip_shading_final_candidate"
    )
    with client.session_transaction() as sess:
        del sess["buti_ai_lip_shading_final_candidate"]

    final_response = client.post(
        "/analysis/mirror/lip-shading/finalize",
        data={
            "csrf_token": upload_token,
            "final_style": "peach_nude",
            "selected_style": "peach_nude",
            "change_level": "medium",
            "photo_filename": candidate["photo_filename"],
        },
        follow_redirects=True,
    )
    assert final_response.status_code == 200
    final_text = final_response.get_data(as_text=True)
    assert "اول مدل را انتخاب کن" in final_text
    assert "ورود لازم است" not in final_text

    direct_final = client.get(
        f"/analysis/mirror/lip-shading/final?photo_filename={candidate['photo_filename']}&selected_style=peach_nude&change_level=medium",
        follow_redirects=True,
    )
    assert direct_final.status_code == 200
    assert "اول مدل را انتخاب کن" in direct_final.get_data(as_text=True)

    blocked_file = client.get(f"/analysis/mirror/lip-shading/uploads/{candidate['photo_filename']}")
    assert blocked_file.status_code == 404
    with client.session_transaction() as sess:
        assert "buti_ai_lip_shading_final_candidate" not in sess

    _cleanup_service("lip_shading")
