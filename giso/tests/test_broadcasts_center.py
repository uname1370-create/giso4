# -*- coding: utf-8 -*-
"""تست مرکز پیام و اعلان انبوه — ماژول مستقل giso/broadcasts_center."""
import re
import time

from giso.app import create_app
from giso.base import get_giso_db_conn, normalize_phone
from giso.broadcasts_center import core, worker
from giso.models import BuyerProfile, User, db

SUPER_PHONE = normalize_phone("09156012931")


def _login_super(client):
    with client.session_transaction() as s:
        s.setdefault("giso_csrf_token", "fixed-test-csrf-token")
        s["_user_id"] = SUPER_PHONE
        s["admin_panel_verified_phone"] = SUPER_PHONE
        s["admin_panel_verified_until"] = int(time.time()) + 1800


    _op = client.post
    def _post_with_csrf(*a, **k):
        h = dict(k.get("headers") or {}); h.setdefault("X-GISO-CSRF", "fixed-test-csrf-token"); k["headers"] = h
        return _op(*a, **k)
    client.post = _post_with_csrf
def _cleanup(app):
    with app.app_context():
        with get_giso_db_conn() as conn:
            core.ensure_tables(conn)
            conn.execute("DELETE FROM giso_bc_deliveries")
            conn.execute("DELETE FROM giso_bc_campaigns")
            conn.commit()
        for phone in (normalize_phone("09120000071"), normalize_phone("09120000072")):
            u = User.query.filter_by(phone=phone).first()
            if u:
                db.session.delete(u)
        db.session.commit()


def _mk_users(app):
    phones = [normalize_phone("09120000071"), normalize_phone("09120000072")]
    with app.app_context():
        ids = []
        for ph in phones:
            u = User.query.filter_by(phone=ph).first()
            if not u:
                u = User(phone=ph, password_hash="h", name="تست پیام")
                db.session.add(u)
                db.session.commit()
            if not BuyerProfile.query.filter_by(user_id=u.id).first():
                db.session.add(BuyerProfile(user_id=u.id))
                db.session.commit()
            ids.append(u.id)
    return phones


def test_create_and_process_small_group():
    app = create_app()
    _cleanup(app)
    phones = _mk_users(app)
    ok, msg, cid = core.create_campaign("تست", "پیام تست گروه کوچک", "buyers", "site")
    assert ok and cid > 0, msg
    core.process_batch(10)
    with get_giso_db_conn() as conn:
        rows = conn.execute("SELECT d.phone,d.site_status FROM giso_bc_deliveries d"
                            " WHERE d.campaign_id=?", (cid,)).fetchall()
    mine = [r for r in rows if r[0] in phones]
    assert len(mine) == 2 and all(r[1] == "sent" for r in mine)
    cams = {c["id"]: c for c in core.campaign_list()}
    assert cams[cid]["status"] == "completed"
    assert cams[cid]["ok"] >= 2 and cams[cid]["pending"] == 0


def test_validation_rejects_bad_input():
    ok, _, _ = core.create_campaign("", "بدون عنوان", "all", "site")
    assert not ok
    ok, _, _ = core.create_campaign("ع", "م", "not-a-group", "site")
    assert not ok
    ok, _, _ = core.create_campaign("ع", "م", "all", "not-a-channel")
    assert not ok


def test_scheduled_campaign_not_sent_before_time():
    app = create_app()
    _cleanup(app)
    ok, msg, cid = core.create_campaign("زمانی", "بعداً", "buyers", "site",
                                        mode="schedule", scheduled_at="2999-01-01 10:00")
    assert ok, msg
    assert core.process_batch(10) == 0
    cams = {c["id"]: c for c in core.campaign_list()}
    assert cams[cid]["status"] == "scheduled"


def test_admin_ui_and_status_json():
    app = create_app()
    client = app.test_client()
    _cleanup(app)
    with app.app_context():
        if not User.query.filter_by(phone=SUPER_PHONE).first():
            db.session.add(User(phone=SUPER_PHONE, password_hash="h", name="سوپر وب"))
            db.session.commit()
    _login_super(client)
    r = client.get("/admin/broadcasts-center")
    assert r.status_code == 200
    html = r.get_data(as_text=True)
    assert "مرکز پیام و اعلان" in html
    tok = re.search(r'data-csrf="([^"]+)"', html).group(1)
    r2 = client.post("/admin/broadcasts-center/create",
                     json={"title": "ui", "message": "متن", "audience": "buyers",
                           "channels": "site", "mode": "now"},
                     headers={"X-CSRF-Token": tok})
    assert r2.status_code == 200 and r2.get_json()["ok"]
    r3 = client.get("/admin/broadcasts-center/status")
    data = r3.get_json()
    assert data["ok"] and len(data["campaigns"]) >= 1
    core.process_batch(10)


def test_worker_start_idempotent():
    t1 = worker.start()
    t2 = worker.start()
    assert t1 is t2 and t1.is_alive()
