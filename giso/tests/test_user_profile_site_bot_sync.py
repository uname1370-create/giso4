# -*- coding: utf-8 -*-
"""Shared site/bot profile and user notification controls."""
from pathlib import Path

from werkzeug.security import generate_password_hash

from giso.app import create_app
from giso.base import get_giso_db_conn
from giso.bot import _user_kb
from giso.models import User, db
from giso.user_profile_service import PROFILE_FIELDS, get_user_activity_summary, get_user_profile, update_user_profile

ROOT = Path(__file__).resolve().parents[2]
PHONE = "+989120009981"
BALE_ID = "88009981"


def _cleanup(app):
    with app.app_context():
        User.query.filter_by(phone=PHONE).delete()
        db.session.commit()
        with get_giso_db_conn() as conn:
            conn.execute("DELETE FROM giso_users WHERE phone=? OR bale_id=?", (PHONE, BALE_ID))
            conn.commit()


def test_site_and_bot_write_the_same_profile_record_and_mirror_name():
    app = create_app()
    _cleanup(app)
    try:
        with app.app_context():
            user = User(phone=PHONE, password_hash=generate_password_hash("test-pass"))
            db.session.add(user)
            db.session.commit()
            with get_giso_db_conn() as conn:
                conn.execute(
                    "INSERT INTO giso_users(bale_id,phone,first_name,is_admin,contact_shared,created_at) "
                    "VALUES (?,?,?,0,1,'test')",
                    (BALE_ID, PHONE, "قدیمی"),
                )
                conn.commit()

            ok, _message, profile = update_user_profile(
                PHONE,
                {"first_name": "سارا", "city": "مشهد", "contact_time": "عصرها", "forbidden": "x"},
                actor="bot",
            )
            assert ok
            assert profile["first_name"] == "سارا"
            assert profile["city"] == "مشهد"
            assert "forbidden" not in profile
            with get_giso_db_conn() as conn:
                bot_row = conn.execute("SELECT first_name FROM giso_users WHERE bale_id=?", (BALE_ID,)).fetchone()
            assert bot_row["first_name"] == "سارا"

            # شبیه‌سازی پایان دوره محدودیت برای پوشش نوشتن از کانال دوم.
            with get_giso_db_conn() as conn:
                conn.execute("UPDATE giso_web_auth SET last_profile_edit_at='' WHERE phone=?", (PHONE,)); conn.commit()
            ok, _message, profile = update_user_profile(
                PHONE, {"last_name": "احمدی", "region": "سجاد"}, actor="site"
            )
            assert ok
            assert profile["name"] == "سارا احمدی"
            assert profile["region"] == "سجاد"
            assert profile["phone"] == PHONE
            assert get_user_profile(PHONE)["name"] == "سارا احمدی"
            assert get_user_activity_summary(PHONE)["bot_connected"] is True
    finally:
        _cleanup(app)


def test_site_profile_form_persists_all_shared_fields_end_to_end():
    import re

    app = create_app()
    _cleanup(app)
    try:
        with app.app_context():
            user = User(phone=PHONE, password_hash=generate_password_hash("test-pass"))
            db.session.add(user)
            db.session.commit()
        client = app.test_client()
        with client.session_transaction() as session:
            session["_user_id"] = PHONE
            session["_fresh"] = True
        page = client.get("/dashboard/profile")
        assert page.status_code == 200
        html = page.get_data(as_text=True)
        token_match = re.search(r'name="csrf_token" value="([^"]+)"', html)
        assert token_match
        response = client.post(
            "/dashboard/profile/update",
            data={
                "csrf_token": token_match.group(1), "first_name": "مینا", "last_name": "رضایی",
                "city": "تهران", "region": "ونک", "contact_time": "صبح‌ها",
            },
            follow_redirects=False,
        )
        assert response.status_code == 302
        with app.app_context():
            saved = get_user_profile(PHONE)
            assert saved["name"] == "مینا رضایی"
            assert saved["city"] == "تهران"
            assert saved["region"] == "ونک"
            assert saved["contact_time"] == "صبح‌ها"
    finally:
        _cleanup(app)


def test_profile_contract_and_site_form_include_all_editable_fields():
    assert set(PROFILE_FIELDS) == {"first_name", "last_name", "city", "region", "contact_time"}
    html = (ROOT / "giso/panel_user/templates/user_modules/profile.html").read_text(encoding="utf-8")
    for field in PROFILE_FIELDS:
        assert f'name="{field}"' in html
    assert 'name="phone"' not in html


def test_notification_buttons_can_only_mark_the_current_users_rows():
    from giso.panel.modules.notifications import log_user_notification, mark_user_notifications_read

    source_id = 88009981
    with get_giso_db_conn() as conn:
        conn.execute("DELETE FROM giso_notifications WHERE source_type='profile_sync_test' AND source_id=?", (source_id,))
        conn.commit()
    try:
        assert log_user_notification(
            PHONE, "profile_test", "اعلان تست پروفایل", "متن تست",
            source_type="profile_sync_test", source_id=source_id, category="system",
        )
        with get_giso_db_conn() as conn:
            row = conn.execute(
                "SELECT id,status FROM giso_notifications WHERE source_type='profile_sync_test' AND source_id=?",
                (source_id,),
            ).fetchone()
        assert row and row["status"] == "unread"
        notification_id = row["id"]
        mark_user_notifications_read("+989120000000", notification_id)
        with get_giso_db_conn() as conn:
            assert conn.execute("SELECT status FROM giso_notifications WHERE id=?", (notification_id,)).fetchone()[0] == "unread"
        mark_user_notifications_read(PHONE, notification_id)
        with get_giso_db_conn() as conn:
            assert conn.execute("SELECT status FROM giso_notifications WHERE id=?", (notification_id,)).fetchone()[0] == "read"
    finally:
        with get_giso_db_conn() as conn:
            conn.execute("DELETE FROM giso_notifications WHERE source_type='profile_sync_test' AND source_id=?", (source_id,))
            conn.commit()


def test_bot_menu_and_callbacks_expose_profile_and_notifications():
    labels = [button.text for row in _user_kb().keyboard for button in row]
    assert "👤 پروفایل" in labels
    assert "📖 راهنما" in labels
    source = (ROOT / "giso/bot.py").read_text(encoding="utf-8")
    for callback in ("upro|edit|first_name", "upro|edit|last_name", "upro|edit|city",
                     "upro|edit|region", "upro|edit|contact_time", "unotif|show",
                     "unotif|all", "unotif|read|"):
        assert callback in source
    assert "update_user_profile(phone" in source
    assert "mark_user_notifications_read(phone" in source
