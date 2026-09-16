# -*- coding: utf-8 -*-
from werkzeug.security import generate_password_hash
from giso.app import create_app
from giso.models import db,User,BuyerProfile
PHONE='+989120004400'

def test_changed_user_panel_pages_render_without_template_errors():
    app=create_app()
    with app.app_context():
        old=User.query.filter_by(phone=PHONE).first()
        if old:BuyerProfile.query.filter_by(user_id=old.id).delete();db.session.delete(old);db.session.commit()
        user=User(phone=PHONE,name='نمایش آزمایشی',password_hash=generate_password_hash('password'),last_profile_edit_at='')
        db.session.add(user);db.session.commit();uid=user.id
    client=app.test_client()
    with client.session_transaction() as s:s['_user_id']=PHONE;s['_fresh']=True
    for url in ('/dashboard/hair-sale','/dashboard/marketplace?tab=listings','/dashboard/marketplace?tab=promotion','/dashboard/hair/buyer-request?tab=features','/dashboard/orders','/dashboard/analyses?tab=overview','/dashboard/profile'):
        response=client.get(url)
        assert response.status_code==200,(url,response.status_code)
    with app.app_context():BuyerProfile.query.filter_by(user_id=uid).delete();User.query.filter_by(id=uid).delete();db.session.commit()
