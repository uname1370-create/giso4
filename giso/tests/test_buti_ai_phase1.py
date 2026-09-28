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
    assert "گزینه آینه از ماژول مستقل Buti AI" in analysis_text
    assert "buti_ai/_analysis_mirror_card.html" not in analysis_text

    mirror = client.get("/analysis/mirror")
    assert mirror.status_code == 200
    assert "آینه ابرو گیسو" in mirror.get_data(as_text=True)

    eyebrow = client.get("/analysis/mirror/eyebrow")
    assert eyebrow.status_code == 200
    eyebrow_text = eyebrow.get_data(as_text=True)
    assert "چه مدل ابرویی بیشتر به سلیقه‌ات نزدیک است؟" in eyebrow_text
    assert "میکروبلیدینگ ظریف" in eyebrow_text
    assert "شیدینگ پودری" in eyebrow_text
    assert "بررسی کیفیت عکس" in eyebrow_text

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
    assert "نتیجه آینه ابرو" in text
    assert "میکروبلیدینگ ظریف" in text
    assert "کیفیت عکس" in text
    assert "مشاهده مراکز مرتبط با ابرو" in text

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
                "why": "فرم طبیعی با چهره هماهنگ‌تر است.",
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
                "why": "ترکیب تارهای ظریف و سایه سبک تعادل بهتری می‌دهد.",
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
    assert "پیش‌نمایش قبل و بعد" in text
    assert "عکس اصلی شما" in text
    assert "کامبینیشن" in text

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
