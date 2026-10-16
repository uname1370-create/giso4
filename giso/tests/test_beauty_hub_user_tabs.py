# -*- coding: utf-8 -*-
"""«سالن زیبایی من»: یک صفحه با تب‌ها، یک آیتم منو، و partialهای مشترک بین هاب و صفحات مستقل."""
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from giso.app import create_app  # noqa: E402
from giso.models import db, User  # noqa: E402
from giso.base import normalize_phone  # noqa: E402
from giso.panel_user.permissions import (USER_MODULES, USER_MODULE_GROUPS, BEAUTY_TABS,  # noqa: E402
                                         build_user_menu)

PHONE = "0919000066554"
BC = ROOT / "giso" / "beauty_centers" / "templates" / "beauty_centers"
UM = ROOT / "giso" / "panel_user" / "templates" / "user_modules"


def test_menu_has_one_salon_entry_and_no_separate_beauty_items():
    keys = [m for m, _, _ in USER_MODULES]
    assert keys.count("beauty") == 1
    for old in ("beauty_centers_list", "reservations", "center_chats", "analyses", "beauty_center"):
        assert old not in keys
    grouped = [m for mods in USER_MODULE_GROUPS.values() for m in mods]
    assert "beauty" in grouped
    assert "analyses" not in grouped
    assert "beauty" in [m for m, _, _ in build_user_menu() if m != "__group"]


def test_beauty_tabs_are_the_five_sections_in_order():
    assert [key for key, _, _ in BEAUTY_TABS] == ["centers", "reservations", "chats", "analyses", "manage"]


def test_hub_and_standalone_pages_share_the_same_partials():
    list_html = (BC / "list.html").read_text(encoding="utf-8")
    assert '{% include "beauty_centers/_list_content.html" %}' in list_html
    assert '{% include "beauty_centers/_reservations_content.html" %}' in (BC / "my_reservations.html").read_text(encoding="utf-8")
    assert '{% include "user_modules/_center_chats_content.html" %}' in (UM / "center_chats.html").read_text(encoding="utf-8")
    analyses_html = (UM / "analyses.html").read_text(encoding="utf-8")
    assert '{% include "user_modules/_analyses_content.html" %}' in analyses_html
    hub = (UM / "beauty_hub.html").read_text(encoding="utf-8")
    for partial in ("beauty_centers/_list_content.html", "beauty_centers/_reservations_content.html",
                    "user_modules/_center_chats_content.html", "user_modules/_analyses_content.html",
                    "user_modules/_beauty_manage_content.html"):
        assert partial in hub
        assert (ROOT / "giso" / "beauty_centers" / "templates" / partial).exists() or \
            (ROOT / "giso" / "panel_user" / "templates" / partial).exists()


def _logged_in_client():
    app = create_app()
    with app.app_context():
        user = User.query.filter_by(phone=normalize_phone(PHONE)).first()
        if not user:
            user = User(phone=normalize_phone(PHONE), password_hash="pbkdf2:sha256:260000$test$hash",
                        name="سارا", city="اصفهان")
            db.session.add(user)
            db.session.commit()
    client = app.test_client()
    with client.session_transaction() as s:
        s["_user_id"] = normalize_phone(PHONE)
    return client


@pytest.mark.parametrize("tab", ["centers", "reservations", "chats", "analyses", "manage"])
def test_hub_renders_every_tab_on_one_page(tab):
    client = _logged_in_client()
    r = client.get(f"/dashboard/beauty?beauty_tab={tab}")
    assert r.status_code == 200, r.status_code
    html = r.get_data(as_text=True)
    assert html.count('role="tab"') == 5
    assert f'is-active" aria-selected="true" href="/dashboard/beauty?beauty_tab={tab}"' in html


def test_hub_falls_back_to_centers_for_unknown_tab():
    client = _logged_in_client()
    r = client.get("/dashboard/beauty?beauty_tab=unknown")
    assert r.status_code == 200
    assert 'bc-search' in r.get_data(as_text=True)
