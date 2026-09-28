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
    monkeypatch.setattr(eyebrow_flow, "analyze_eyebrow_photo", lambda path, style, change: {
        "status": "ai_analyzed",
        "ok": True,
        "message": "تحلیل هوشمند ابرو انجام شد.",
        "data": {
            "recommended_style": "microblading",
            "change_level": "medium",
            "short_reason": "برای تست مسیر واقعی مناسب است.",
            "why": "فرم ابرو با تغییر متوسط بهتر دیده می‌شود.",
            "do": ["قوس ملایم"],
            "avoid": ["تیره‌کردن زیاد"],
            "style_scores": [],
            "score_cards": [],
            "face_analysis": {},
        },
        "provider": "test-provider",
        "model": "test-model",
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
    )
    assert response.status_code == 200
    text = response.get_data(as_text=True)
    assert "پیشنهاد گیسو" in text
    assert "میکروبلیدینگ ظریف" in text
    assert "تأیید اولیه عکس" in text
    assert "طراحی عکس نهایی" in text

    _cleanup_buti_ai_sessions()




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
    assert "تحلیل و پیشنهاد" in text
    assert "تحلیل و پیشنهاد" in text
    assert "جزئیات کوتاه عکس" in text
    assert "کامبینیشن" in text
    assert "انتخاب نهایی" in text
    assert "طراحی عکس نهایی" in text
    assert "91٪ تناسب با عکس" in text
    assert "عکس اصلی شما" not in text
    assert "امتیاز مدل‌ها" not in text

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
        assert "Edit ONLY the two eyebrow regions" in data["prompt"]
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
    assert "این تصویر، راهنمای هوشمند/پیش‌نمایش طراحی عکس نهایی است" in html
    assert "طراحی راهنمای امن آماده شد" in html


def test_final_design_template_shows_inline_waitlist_when_no_centers():
    html = _render_final_design_template([])

    assert "فعلاً مرکز فعال برای این خدمت ثبت نشده" in html
    assert "ثبت درخواست اطلاع‌رسانی" in html
    assert "تقاضای ثبت‌شده مشهد برای ابرو: 4" in html
    assert "ثبت مرکز زیبایی برای خدمت ابرو" in html
    assert "راهنمای هوشمند قبل از انتخاب مرکز" in html


def test_cloudflare_cf_alias_and_account_root_builder():
    from giso.ai_models_registry import normalize_provider_name
    from giso.ai_brain import (
        cloudflare_account_id_from_url,
        normalize_cloudflare_api_root,
    )

    assert normalize_provider_name("cf") == "cloudflare"
    assert normalize_provider_name("Cloudflare Workers AI") == "cloudflare"
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
                "endpoint": "https://api.cloudflare.com/client/v4/accounts/acct-1/ai/run/@cf/test-image",
                "model": "@cf/test-image",
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
        calls.append({"url": url, "headers": headers or {}, "files": files or {}})
        return FakeResponse()

    monkeypatch.setattr(image_generation.requests, "post", fake_post)

    result = image_generation.generate_final_design(_sample_final_candidate(), env=None)

    assert calls
    assert calls[0]["url"].endswith("/ai/run/@cf/test-image")
    assert result["ok"] is True
    assert result["provider"] == "ai_mirror_cloudflare_1"
    assert result["model"] == "@cf/test-image"
    assert result["fallback_used"] is False
    assert (tmp_path / result["filename"]).exists()


def test_final_design_template_uses_drag_compare_slider():
    from pathlib import Path

    tpl = Path("giso/buti_ai/templates/buti_ai/eyebrow_final_design.html").read_text(encoding="utf-8")
    assert "data-bti-compare" in tpl
    assert "bti-compare-handle" in tpl
    assert "bti-before-after bti-final-before-after" not in tpl
    assert "eyebrow_final_retry" in tpl


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
    assert result["added"] == 4
    rows = ai_models.list_model_assignments()
    assert len(rows) == 4
    analysis = [r for r in rows if r["task_key"] == ai_models.TASK_EYEBROW_ANALYSIS]
    images = [r for r in rows if r["task_key"] == ai_models.TASK_EYEBROW_IMAGE_DESIGN]
    assert analysis[0]["provider_name"] == "cloudflare"
    assert "vision" in analysis[0]["model_name"]
    assert [int(r["priority"]) for r in images] == [1, 2, 3]
    assert all(r["image_kind"] == "cloudflare" for r in images)

    second = ai_models.auto_configure_for_provider("cloudflare")
    assert second["added"] == 0


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
    ai_models.save_model_assignment(ai_models.TASK_EYEBROW_IMAGE_DESIGN, 1, "cloudflare", "@cf/black-forest-labs/flux-2-klein-4b", image_kind="cloudflare")

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
    assert ready["image_ready_count"] == 1
    assert ready["warnings"]
