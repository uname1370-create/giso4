# -*- coding: utf-8 -*-
"""End-to-end MVP contract for modular Beauty Centers."""
import io
import json
from pathlib import Path

from PIL import Image
from werkzeug.datastructures import FileStorage
from werkzeug.security import generate_password_hash

from giso.app import create_app
from giso.base import get_giso_db_conn
from giso.beauty_centers.services import (
    admin_set_status, create_center, get_center, get_owner_center,
    recommended_centers, reveal_contact, save_center_image,
)
from giso.models import Analysis, User, db
from giso.panel.permissions import module_allowed, visible_modules

PHONE = "+989120009971"
ROOT = Path(__file__).resolve().parents[2]


def _cleanup(app):
    with app.app_context():
        user = User.query.filter_by(phone=PHONE).first()
        if user:
            with get_giso_db_conn() as conn:
                center_ids = [row[0] for row in conn.execute("SELECT id FROM beauty_centers WHERE owner_user_id=?", (user.id,)).fetchall()]
                for center_id in center_ids:
                    conn.execute("DELETE FROM beauty_center_reports WHERE center_id=?", (center_id,))
                conn.execute("DELETE FROM beauty_centers WHERE owner_user_id=?", (user.id,))
                conn.execute("DELETE FROM analyses WHERE user_id=?", (user.id,))
                placeholders = ",".join("?" for _ in center_ids) or "0"
                conn.execute(f"DELETE FROM giso_notifications WHERE source_type LIKE 'beauty_center_%' AND source_id IN ({placeholders})", center_ids)
                conn.commit()
            db.session.delete(user)
            db.session.commit()


def _user(app):
    with app.app_context():
        user = User(phone=PHONE, name="مالک تست", first_name="مالک", last_name="تست",
                    city="مشهد", region="سجاد", password_hash=generate_password_hash("test-pass"))
        db.session.add(user); db.session.commit(); return user.id


def test_schema_public_seo_and_guest_gates():
    app = create_app()
    with app.test_client() as client:
        page = client.get("/beauty-centers")
        assert page.status_code == 200
        text = page.get_data(as_text=True)
        assert "مراکز زیبایی گیسو" in text
        assert 'application/ld+json' in text
        assert "گیسو فقط بستر معرفی" in text
        assert client.get("/beauty-centers/register").status_code == 302
        assert client.get("/dashboard/beauty-center").status_code == 302
        assert "/beauty-centers" in client.get("/sitemap.xml").get_data(as_text=True)
    with app.app_context(), get_giso_db_conn() as conn:
        tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
        assert {"beauty_centers", "beauty_center_reports"} <= tables


def test_center_lifecycle_matching_contact_and_owner_panel():
    app = create_app(); _cleanup(app); user_id = _user(app)
    try:
        with app.app_context():
            ok, message, center = create_center(user_id, {
                "name": "سالن تست گیسو", "category": "hair", "center_type": "salon", "city": "مشهد", "region": "سجاد",
                "business_phone": "09120009971", "contact_time": "۱۰ تا ۲۰",
                "description": "مرکز تست خدمات ترمیم مو", "services": ["hair_repair", "haircut"],
                "terms_accepted": True,
            }, "uploads/hair_20260810140337.jpg")
            assert ok, message
            assert center["status"] == "pending_review"
            assert get_owner_center(user_id)["id"] == center["id"]
            assert all(row["id"] != center["id"] for row in __import__("giso.beauty_centers.services", fromlist=["list_public_centers"]).list_public_centers())
            ok, _message, center = admin_set_status(center["id"], "published")
            assert ok and center["status"] == "published"
            analysis = Analysis(user_id=user_id, phone=PHONE, type="hair", photo_path="uploads/hair_20260810140337.jpg",
                                ai_report_json=json.dumps({"main_problems": [{"name": "آسیب و خشکی مو"}]}, ensure_ascii=False))
            db.session.add(analysis); db.session.commit()
            matched = recommended_centers(analysis.id, user_id, city="مشهد")
            assert matched and matched[0]["id"] == center["id"]
            ok, number = reveal_contact(center["id"], user_id + 999)
            assert ok and number == "+989120009971"
            assert get_center(center["id"])["contact_clicks"] == 1

        client = app.test_client()
        detail = client.get(f"/beauty-centers/{center['slug']}")
        assert detail.status_code == 200
        assert "LocalBusiness" in detail.get_data(as_text=True)
        assert client.get(f"/beauty-centers/media/{center['id']}").status_code == 200
        with client.session_transaction() as session:
            session["_user_id"] = PHONE; session["_fresh"] = True
        owner = client.get("/dashboard/beauty-center")
        assert owner.status_code == 200
        assert "وضعیت مرکز" in owner.get_data(as_text=True)
    finally:
        _cleanup(app)


def test_authenticated_registration_form_creates_pending_center():
    import re
    app = create_app(); _cleanup(app); user_id = _user(app)
    created_path = ""
    try:
        client = app.test_client()
        with client.session_transaction() as session:
            session["_user_id"] = PHONE; session["_fresh"] = True
        page = client.get("/beauty-centers/register")
        assert page.status_code == 200
        token = re.search(r'name="csrf_token" value="([^"]+)"', page.get_data(as_text=True)).group(1)
        image = Image.new("RGB", (120, 90), "#c85873")
        payload = io.BytesIO(); image.save(payload, "JPEG"); payload.seek(0)
        response = client.post(
            "/beauty-centers/register",
            data={
                "csrf_token": token, "name": "مرکز فرم تست", "category": "hair", "center_type": "hair_center",
                "business_phone": "09120009971", "city": "مشهد", "region": "سجاد",
                "contact_time": "۱۰ تا ۲۰", "description": "توضیح واقعی مرکز",
                "services": ["hair_repair", "haircut"], "terms_accepted": "1",
                "image": (payload, "center.jpg"),
            },
            content_type="multipart/form-data", follow_redirects=False,
        )
        assert response.status_code == 302 and "/dashboard/beauty-center" in response.headers["Location"]
        with app.app_context():
            center = get_owner_center(user_id)
            assert center["status"] == "pending_review"
            created_path = center["image_path"]
        dashboard = client.get("/dashboard/beauty-center")
        assert dashboard.status_code == 200
        assert "مرکز زیبایی من" in dashboard.get_data(as_text=True)
        profile_page = client.get("/dashboard/profile")
        assert profile_page.status_code == 200
        assert "مرکز زیبایی من" in profile_page.get_data(as_text=True)
    finally:
        if created_path:
            path = ROOT / "giso/static" / created_path
            if path.exists(): path.unlink()
        _cleanup(app)


def test_real_image_validation_reencodes_to_public_webp():
    image = Image.new("RGB", (80, 60), "#d86f8a")
    payload = io.BytesIO(); image.save(payload, "JPEG"); payload.seek(0)
    storage = FileStorage(stream=payload, filename="center.jpg", content_type="image/jpeg")
    path, error = save_center_image(storage)
    assert not error and path.startswith("uploads/beauty_centers/") and path.endswith(".webp")
    output = ROOT / "giso/static" / path
    assert output.exists()
    output.unlink()


def test_admin_and_bot_contracts_and_ai_safety():
    from giso.bot import _admin_kb
    from giso.panel.modules.notifications import DEFAULT_CATEGORY_SETTINGS
    assert DEFAULT_CATEGORY_SETTINGS["beauty_centers"] == {
        "target_role": "both", "enabled": 1, "destination": "both", "title": "مراکز زیبایی"
    }
    assert module_allowed("beauty_centers", "admin", {})
    assert any(item["module"] == "beauty_centers" for item in visible_modules("admin", {}))
    assert any(item["module"] == "beauty_centers" for item in visible_modules("super", {}))
    # ادمین محدود: چهار دکمه عملیاتی ثابت (مدیریت مراکز از پنل سایت، نه ربات)
    assert [button.text for row in _admin_kb(777001).keyboard for button in row] == [
        "💇 خرید مو", "🛍 فروشگاه", "🏪 بازارچه", "💬 مدیریت گفتگوها",
    ]
    assert "🏥 مراکز زیبایی" in [button.text for row in _admin_kb(1191639507).keyboard for button in row]
    bot = (ROOT / "giso/beauty_centers/bot_handlers.py").read_text(encoding="utf-8")
    for callback in ("bc_act|{center_id}|review", "bc_act|{center_id}|publish", "bc_act|{center_id}|reject"):
        assert callback in bot
    analysis = (ROOT / "giso/analysis.py").read_text(encoding="utf-8")
    ai_policy = (ROOT / "giso/beauty_centers/ai_prompt.py").read_text(encoding="utf-8")
    assert "هیچ نام، نشانی، امتیاز یا خدمتی اختراع نکن" in ai_policy
    assert "هرگز عبارت بهترین مرکز را به کار نبر" in ai_policy
    assert "build_beauty_centers_prompt" in analysis
    assert "recommended_centers(" in analysis
    for template in ("analysis_report_hair.html", "analysis_report_skin.html", "analysis_plan.html", "analysis_quick_solution.html"):
        assert "beauty_centers/_analysis_cta.html" in (ROOT / "giso/templates" / template).read_text(encoding="utf-8")
