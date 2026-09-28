# -*- coding: utf-8 -*-
"""Phase 1/1.5/2 contract for modular Buti AI eyebrow mirror."""
import os
import re
from io import BytesIO

os.environ.setdefault("SECRET_KEY", "arena-test-secret-for-buti-ai-tests-32chars")

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
            "DELETE FROM buti_ai_sessions WHERE service_type=? AND status IN (?, ?, ?, ?)",
            ("eyebrow", "mvp_demo", "mvp_photo_received", "mvp_guided_preview", "ai_analyzed"),
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
    assert "فعلاً مسیر ابرو فعال است" in analysis_text
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
    assert "کیفیت عکس بررسی می‌شود" in eyebrow_text

    ping = client.get("/analysis/mirror/ping")
    assert ping.status_code == 200
    assert ping.get_json()["module"] == "buti_ai_ready"


def test_buti_ai_eyebrow_demo_post_with_csrf():
    app = create_app()
    _cleanup_buti_ai_sessions()
    client = app.test_client()

    page = client.get("/analysis/mirror/eyebrow")
    assert page.status_code == 200
    token = re.search(r'name="csrf_token" value="([^"]+)"', page.get_data(as_text=True)).group(1)

    response = client.post(
        "/analysis/mirror/eyebrow",
        data={
            "csrf_token": token,
            "style": "microblading",
            "change_level": "medium",
            "demo_mode": "1",
        },
    )
    assert response.status_code == 200
    text = response.get_data(as_text=True)
    assert "پیشنهاد گیسو" in text
    assert "میکروبلیدینگ ظریف" in text
    assert "کیفیت عکس" in text
    assert "مرحله ۵: مراکز و رزرو" in text

    _cleanup_buti_ai_sessions()


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
    assert result["style_key"] == "natural"
    assert result["face_shape"] == "بیضی"
    assert result["face_analysis"]["brow_density"] == "متوسط"
    assert result["style_scores"][0]["style_key"] == "natural"
    assert result["style_scores"][0]["score"] == 88
    assert result["short_reason"] == "نچرال برای این چهره امن‌تر است."
    assert preview["available"] is True
    assert preview["mode"] == "guided_before_after"
    assert len(calls) == 2


def test_eyebrow_photo_post_builds_ai_preview(monkeypatch):
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
        if "کیفیت عکس" in prompt:
            return {"ok": True, "data": {"ok": True, "message": "عکس مناسب است."}}
        return {
            "ok": True,
            "data": {
                "face_shape": "کشیده",
                "current_brow_summary": "دم ابرو کمی پایین است.",
                "recommended_style": "combination",
                "change_level": "medium",
                "short_reason": "کامبینیشن ملایم برای دم ابرو بهتر است.",
                "why": "ترکیب تارهای ظریف و سایه سبک تعادل بهتری می‌دهد.",
                "face_analysis": {
                    "face_shape": "کشیده",
                    "eye_balance": "هماهنگ",
                    "brow_density": "متوسط",
                    "brow_symmetry": "نیاز به اصلاح",
                    "brow_arch": "ملایم",
                    "tail_position": "کمی افتاده",
                },
                "style_scores": [
                    {"style": "combination", "score": 91, "reason": "دم ابرو را کامل‌تر می‌کند."},
                    {"style": "natural", "score": 78, "reason": "گزینه کم‌ریسک است."},
                    {"style": "microblading", "score": 76, "reason": "برای پر کردن جای خالی خوب است."},
                    {"style": "powder", "score": 61, "reason": "ممکن است کمی سنگین شود."},
                    {"style": "giso_suggested", "score": 84, "reason": "پیشنهاد متعادل است."},
                ],
                "do": ["دم ابرو کمی مرتب شود"],
                "avoid": ["تیره کردن تاج ابرو"],
                "alternative_styles": ["نچرال"],
                "confidence": "medium",
            },
        }

    monkeypatch.setattr(eyebrow_flow, "save_eyebrow_photo", fake_save)
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
    )

    assert response.status_code == 200
    text = response.get_data(as_text=True)
    assert "تحلیل هوشمند ابرو انجام شد" in text
    assert "طرح پیشنهادی" in text
    assert "عکس اصلی شما" in text
    assert "کامبینیشن" in text
    assert "امتیاز مدل‌ها" in text
    assert "تحلیل چهره و ابرو" in text
    assert "انتخاب نهایی" in text
    assert "ادامه به طراحی نهایی" in text
    assert "91٪" in text

    final_choice = client.post(
        "/analysis/mirror/eyebrow/finalize",
        data={"csrf_token": token, "final_style": "combination"},
        follow_redirects=False,
    )
    assert final_choice.status_code in (302, 303)
    assert final_choice.headers["Location"].endswith("/analysis/mirror/eyebrow/final")

    auth_gate = client.get("/analysis/mirror/eyebrow/final")
    assert auth_gate.status_code == 200
    auth_text = auth_gate.get_data(as_text=True)
    assert "ورود لازم است" in auth_text
    assert "ثبت‌نام سریع" in auth_text

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
    assert result["filename"].startswith("final/final_eyebrow_")
    assert (tmp_path / result["filename"]).exists()


def _sample_final_candidate(filename="face.jpg"):
    return {
        "photo_filename": filename,
        "final_style": "combination",
        "final_label": "کامبینیشن",
        "recommended_style": "combination",
        "recommended_label": "کامبینیشن",
        "change_key": "medium",
        "change_label": "کمی تغییر",
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
    assert result["status"] == "guided_final_ready"
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
        assert data["prompt"].startswith("Edit only the two eyebrow regions")
        return FakeResponse()

    monkeypatch.setattr(image_generation.requests, "post", fake_post)
    env = {
        "CLOUDFLARE_API_TOKEN_1": "secret-token",
        "CLOUDFLARE_ACCOUNT_ID_1": "acct-1",
        "CLOUDFLARE_MODEL": "@cf/test-model",
        "BUTI_AI_IMAGE_TIMEOUT_SECONDS": "5",
    }

    result = image_generation.generate_final_design(_sample_final_candidate(), env=env)

    assert calls
    assert result["ok"] is True
    assert result["provider"] == "cloudflare_1"
    assert result["provider_label"] == "Cloudflare 1"
    assert result["model"] == "@cf/test-model"
    assert result["status"] == "ai_final_ready"
    assert result["fallback_used"] is False
    assert result["attempts"][0]["ok"] is True
    assert result["filename"].startswith("final/ai_eyebrow_")
    assert (tmp_path / result["filename"]).exists()


def test_final_selection_change_clears_cached_generation():
    from flask import session
    from giso.buti_ai.eyebrow.final_design import (
        FINAL_DESIGN_SESSION_KEY,
        update_final_selection,
    )

    app = create_app()
    with app.test_request_context("/analysis/mirror/eyebrow/finalize", method="POST"):
        session[FINAL_DESIGN_SESSION_KEY] = {
            "recommended_style": "combination",
            "final_style": "combination",
            "generation": {"ok": True, "filename": "final/old.jpg"},
            "final_design_id": 123,
        }
        candidate = update_final_selection(session, "natural")
        assert candidate["final_style"] == "natural"
        assert "generation" not in candidate
        assert "final_design_id" not in candidate


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
