# -*- coding: utf-8 -*-
"""Stage 12: responsive public navigation and uncluttered owner navigation."""
from pathlib import Path

from giso.app import create_app

ROOT = Path(__file__).resolve().parents[2]


def test_public_menu_link_is_server_rendered_and_marked_current_on_directory():
    app = create_app()
    with app.test_client() as client:
        home = client.get("/").get_data(as_text=True)
        directory = client.get("/beauty-centers").get_data(as_text=True)
    assert 'href="/beauty-centers"' in home
    assert "مراکز زیبایی" in home
    assert 'href="/beauty-centers" aria-current="page"' in directory


def test_public_link_uses_the_same_responsive_navigation_container():
    base = (ROOT / "giso/templates/base.html").read_text(encoding="utf-8")
    start = base.index('<div class="giso-nav-links" id="gisoNav">')
    end = base.index("</div>", start)
    nav = base[start:end]
    assert "beauty_centers.list_centers" in nav
    assert "request.blueprint == 'beauty_centers'" in nav
    assert 'onclick="document.getElementById(\'gisoNav\').classList.toggle(\'active\')"' in base


def test_owner_sidebar_is_conditional_and_pre_registration_cta_stays_in_profile():
    routes = (ROOT / "giso/panel_user/routes.py").read_text(encoding="utf-8")
    sidebar = (ROOT / "giso/panel_user/templates/partials/user_sidebar.html").read_text(encoding="utf-8")
    profile = (ROOT / "giso/panel_user/templates/user_modules/profile.html").read_text(encoding="utf-8")
    # قرارداد جدید §۷: مرکز زیبایی فقط برای صاحبان، داخل گروه «خدمات»
    assert "get_owner_center" in routes
    perms = (ROOT / "giso/panel_user/permissions.py").read_text(encoding="utf-8")
    assert '"خدمات"' in perms and '"beauty_center"' in perms
    assert "m == 'beauty_center'" in sidebar
    assert "ثبت رایگان مرکز زیبایی" in profile
    assert "if beauty_center" in profile


def test_active_menu_style_remains_inside_feature_module():
    css = (ROOT / "giso/beauty_centers/static/beauty_centers.css").read_text(encoding="utf-8")
    assert '.giso-nav-links a[aria-current="page"]' in css
