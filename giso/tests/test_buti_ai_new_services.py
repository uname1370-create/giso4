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
from giso.buti_ai.schema import init_buti_ai_db


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
    assert response.status_code == 200
    result_text = response.get_data(as_text=True)
    assert "همان مدل انتخابی آماده طراحی است" in result_text
    assert "عکس واقعی شما" in result_text
    assert "فرنچ کلاسیک" in result_text
    assert "/analysis/mirror/nail/uploads/" in result_text

    with client.session_transaction() as sess:
        candidate = dict(sess["buti_ai_nail_final_candidate"])
    assert candidate["service_key"] == "nail"
    assert candidate["service_type"] == "nail"
    assert candidate["selected_style"] == "classic_french"
    assert candidate["final_style"] == "classic_french"
    assert candidate["final_label"] == "فرنچ کلاسیک"
    assert candidate["change_key"] == "clear"
    assert candidate["photo_filename"].startswith("nail_")

    generation = nail_final.generate_guided_design(candidate)
    assert generation["ok"] is True
    assert generation["is_ai_generated"] is False
    assert generation["filename"].startswith("final/final_nail_")
    assert (Path(nail_final.UPLOAD_DIR) / generation["filename"]).exists()

    final_token = re.findall(r'name="csrf_token" value="([^"]+)"', result_text)[-1]
    final_response = client.post(
        "/analysis/mirror/nail/finalize",
        data={"csrf_token": final_token, "final_style": "cat_eye"},
        follow_redirects=True,
    )
    assert final_response.status_code == 200
    final_text = final_response.get_data(as_text=True)
    assert "ورود لازم است" in final_text
    assert "فرنچ کلاسیک" in final_text
    assert "کت‌آی" not in final_text

    with client.session_transaction() as sess:
        candidate_after = dict(sess["buti_ai_nail_final_candidate"])
    assert candidate_after["final_style"] == "classic_french"
    assert candidate_after["final_label"] == "فرنچ کلاسیک"

    _cleanup_service("nail")


def test_planned_new_services_are_visible_but_not_publicly_active_yet():
    app = create_app()
    client = app.test_client()

    home = client.get("/analysis/mirror")
    assert home.status_code == 200
    text = home.get_data(as_text=True)
    assert "آینه رنگ و لایت مو گیسو" in text
    assert "آینه لب و شیدینگ گیسو" in text
    assert "در حال آماده‌سازی" in text

    hair = client.get("/analysis/mirror/hair-color", follow_redirects=True)
    assert hair.status_code == 200
    assert "این خدمت هنوز برای استفاده عمومی فعال نشده است" in hair.get_data(as_text=True)
