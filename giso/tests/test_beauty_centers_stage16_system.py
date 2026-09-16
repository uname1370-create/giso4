# -*- coding: utf-8 -*-
"""Stage 16: whole-feature architecture, route and legal regression audit."""
from pathlib import Path

from giso.app import create_app
from giso.beauty_centers.services import DISCLAIMER

ROOT = Path(__file__).resolve().parents[2]
MODULE = ROOT / "giso/beauty_centers"


def test_complete_route_surface_has_safe_http_methods_and_no_commerce_endpoint():
    app = create_app()
    rules = {
        rule.rule: set(rule.methods) - {"HEAD", "OPTIONS"}
        for rule in app.url_map.iter_rules()
        if rule.endpoint.startswith("beauty_centers.")
    }
    expected = {
        "/beauty-centers": {"GET"},
        "/beauty-centers/register": {"GET", "POST"},
        "/beauty-centers/<path:slug>": {"GET"},
        "/beauty-centers/<int:center_id>/contact": {"POST"},
        "/beauty-centers/chat/<int:conversation_id>/feedback": {"POST"},
        "/beauty-centers/<path:slug>/chat": {"GET"},
        "/beauty-centers/chat/<int:conversation_id>/message": {"POST"},
        "/beauty-centers/chat/<int:conversation_id>/close": {"POST"},
        "/dashboard/beauty-center": {"GET"},
        "/dashboard/beauty-center/update": {"POST"},
        "/dashboard/beauty-center/visibility": {"POST"},
        "/dashboard/beauty-center/gallery": {"POST"},
        "/dashboard/beauty-center/gallery/<int:image_id>/delete": {"POST"},
        "/beauty-centers/gallery/<int:image_id>": {"GET"},
        "/beauty-centers/media/<int:center_id>": {"GET"},
    }
    for path, methods in expected.items():
        assert rules.get(path) == methods
    assert not any(any(word in path.lower() for word in ("payment", "checkout", "reserve", "booking"))
                   for path in rules)


def test_feature_remains_modular_with_only_explicit_core_hooks():
    files = {item.relative_to(MODULE).as_posix() for item in MODULE.rglob("*") if item.is_file() and "__pycache__" not in item.parts}
    required = {
        "__init__.py", "schema.py", "services.py", "routes.py", "panel_admin.py",
        "bot_handlers.py", "ai_prompt.py", "static/beauty_centers.css",
        "static/beauty_centers.js", "templates/beauty_centers/list.html",
        "templates/beauty_centers/detail.html", "templates/beauty_centers/chat.html",
        "templates/beauty_centers/register.html", "templates/beauty_centers/owner_dashboard.html",
    }
    assert required <= files
    app_source = (ROOT / "giso/app.py").read_text(encoding="utf-8")
    bot_source = (ROOT / "giso/bot.py").read_text(encoding="utf-8")
    analysis_source = (ROOT / "giso/analysis.py").read_text(encoding="utf-8")
    assert "app.register_blueprint(beauty_centers_bp)" in app_source
    assert "handle_beauty_admin_callback" in bot_source and "handle_beauty_owner_callback" in bot_source
    assert "build_beauty_centers_prompt" in analysis_source


def test_legal_boundary_is_present_across_public_price_chat_and_ai_surfaces():
    assert "ارائه خدمات، تعیین قیمت، پرداخت، کیفیت، نتیجه کار یا اختلاف" in DISCLAIMER
    templates = MODULE / "templates/beauty_centers"
    list_page = (templates / "list.html").read_text(encoding="utf-8")
    detail = (templates / "detail.html").read_text(encoding="utf-8")
    chat = (templates / "chat.html").read_text(encoding="utf-8")
    card = (templates / "_card.html").read_text(encoding="utf-8")
    prompt = (MODULE / "ai_prompt.py").read_text(encoding="utf-8")
    assert "{{ disclaimer }}" in list_page and "{{ disclaimer }}" in detail
    assert "قیمت نهایی نیست" in detail and "قیمت نهایی" in chat
    assert "رزرو، پرداخت و ارائه خدمت خارج از گیسو" in chat
    assert "اطلاعات هزینه توسط مرکز اعلام شده است" in card
    assert "رزرو، پرداخت، توافق بر قیمت نهایی و ارائه خدمت خارج از گیسو" in prompt


def test_all_mutating_html_forms_carry_csrf_and_routes_require_authenticated_parties():
    templates = MODULE / "templates/beauty_centers"
    for name in ("register.html", "detail.html", "chat.html", "owner_dashboard.html", "admin.html"):
        source = (templates / name).read_text(encoding="utf-8")
        assert source.count("<form") == source.count('name="csrf_token"')
    routes = (MODULE / "routes.py").read_text(encoding="utf-8")
    for function in (
        "center_contact", "center_chat_feedback", "register_center", "owner_dashboard", "owner_update",
        "owner_visibility", "owner_gallery_upload", "owner_gallery_delete", "center_chat", "center_chat_message", "center_chat_close",
    ):
        marker = f"def {function}"
        position = routes.index(marker)
        assert "@login_required" in routes[max(0, position - 180):position]
    service = (MODULE / "services.py").read_text(encoding="utf-8")
    assert "UNIQUE(center_id,user_id)" in (MODULE / "schema.py").read_text(encoding="utf-8")
    assert "recent >= 10" in service
    assert "conversation_for_party" in service


def test_public_smoke_pages_and_private_gates_are_operational():
    app = create_app()
    with app.test_client() as client:
        directory = client.get("/beauty-centers")
        assert directory.status_code == 200
        body = directory.get_data(as_text=True)
        assert "مراکز زیبایی گیسو" in body and "گیسو فقط بستر معرفی" in body
        assert client.get("/beauty-centers/register").status_code == 302
        assert client.get("/dashboard/beauty-center").status_code == 302
        # CSRF rejects the mutation before authentication/ownership logic is reached.
        assert client.post("/beauty-centers/1/contact").status_code == 400
        assert client.get("/sitemap.xml").status_code == 200
        assert client.get("/robots.txt").status_code == 200
