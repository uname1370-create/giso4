# -*- coding: utf-8 -*-
import json
from werkzeug.security import generate_password_hash
from giso.app import create_app
from giso.models import db,User,Analysis

PHONE="+989120007733"

def test_analysis_hub_tabs_metrics_and_safe_archive():
    app=create_app()
    with app.app_context():
        user=User.query.filter_by(phone=PHONE).first() or User(phone=PHONE,name="تحلیل",password_hash=generate_password_hash("p"))
        db.session.add(user);db.session.flush()
        row=Analysis(user_id=user.id,phone=PHONE,type="hair",photo_path="uploads/test.jpg",ai_report_json=json.dumps({"main_problems":[{"name":"خشکی"}],"metrics":{"سلامت":72}},ensure_ascii=False),plan_json="{}",archived_at="")
        db.session.add(row);db.session.commit();uid,aid=user.id,row.id
    client=app.test_client()
    with client.session_transaction() as s:s["_user_id"]=PHONE;s["_fresh"]=True;s["giso_csrf_token"]="t"
    page=client.get("/dashboard/analyses?tab=hair")
    assert page.status_code==200
    text=page.get_data(as_text=True)
    assert "آنالیز مو" in text and "خشکی" in text and "72" in text  # fa_display.js آن را در مرورگر فارسی می‌کند
    response=client.post(f"/dashboard/analyses/{aid}/archive",data={"csrf_token":"t"})
    assert response.status_code==302
    with app.app_context():
        assert db.session.get(Analysis,aid).archived_at
        db.session.delete(db.session.get(Analysis,aid));User.query.filter_by(id=uid).delete();db.session.commit()


def test_analysis_template_has_no_redundant_history_tab():
    source=open("giso/panel_user/templates/user_modules/analyses.html",encoding="utf-8").read()
    assert "وضعیت کلی من" in source and "آنالیز مو" in source and "آنالیز پوست" in source and "گفتگو با مشاور" in source
    assert "تاریخچه کامل" not in source
