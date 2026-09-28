# -*- coding: utf-8 -*-
"""Phase 1/1.5 contract for modular Buti AI eyebrow mirror."""
import os
import re

os.environ.setdefault("SECRET_KEY", "arena-test-secret-for-buti-ai-tests-32chars")

from giso.app import create_app
from giso.base import get_giso_db_conn
from giso.buti_ai.eyebrow.flow import get_mirror_services
from giso.buti_ai.eyebrow.options import (
    DEFAULT_CHANGE_LEVEL,
    DEFAULT_STYLE,
    normalize_change_level,
    normalize_style_key,
)
from giso.buti_ai.eyebrow.result import build_eyebrow_result
from giso.buti_ai.schema import init_buti_ai_db


def _cleanup_buti_ai_sessions():
    init_buti_ai_db()
    with get_giso_db_conn() as conn:
        conn.execute(
            "DELETE FROM buti_ai_sessions WHERE service_type=? AND status IN (?, ?)",
            ("eyebrow", "mvp_demo", "mvp_photo_received"),
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
    assert "چه مدل ابرویی بیشتر دوست داری" in eyebrow_text
    assert "میکروبلیدینگ ظریف" in eyebrow_text
    assert "شیدینگ پودری" in eyebrow_text

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
    assert "مشاهده مراکز مرتبط با ابرو" in text

    _cleanup_buti_ai_sessions()
