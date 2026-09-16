# -*- coding: utf-8 -*-
from werkzeug.security import generate_password_hash,check_password_hash
from giso.app import create_app
from giso.models import db,User
from giso.user_profile_service import update_user_profile

PHONE='+989120005511'

# سیاست رمز جدید: حداقل ۶ کاراکتر + حرف + عدد (ورود کاربران فعلی تغییر نمی‌کند)

def test_profile_edit_locks_for_fifteen_days_and_password_uses_min4_policy():
    app=create_app()
    with app.app_context():
        old=User.query.filter_by(phone=PHONE).first()
        if old:db.session.delete(old);db.session.commit()
        user=User(phone=PHONE,name='امن',password_hash=generate_password_hash('old-password'),last_profile_edit_at='')
        db.session.add(user);db.session.commit();uid=user.id
        assert update_user_profile(PHONE,{'first_name':'مینا'},actor='site')[0]
        ok,message,_=update_user_profile(PHONE,{'city':'مشهد'},actor='site')
        assert not ok and '۱۵ روز' in message
    client=app.test_client()
    with client.session_transaction() as s:s['_user_id']=PHONE;s['_fresh']=True;s['giso_csrf_token']='t'
    bad=client.post('/dashboard/password/change',data={'csrf_token':'t','current_password':'old-password','new_password':'12','new_password2':'12'})
    assert bad.status_code==302
    good=client.post('/dashboard/password/change',data={'csrf_token':'t','current_password':'old-password','new_password':'new-password-123','new_password2':'new-password-123'})
    assert good.status_code==302
    with app.app_context():
        row=db.session.get(User,uid);assert check_password_hash(row.password_hash,'new-password-123');db.session.delete(row);db.session.commit()
