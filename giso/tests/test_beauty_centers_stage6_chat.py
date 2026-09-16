# -*- coding: utf-8 -*-
from werkzeug.security import generate_password_hash
from giso.app import create_app
from giso.base import get_giso_db_conn
from giso.beauty_centers.services import (admin_set_status, close_conversation, conversation_for_party,
 conversation_messages, create_center, get_or_create_conversation,
 send_conversation_message)
from giso.models import User,db
OWNER_PHONE='+989120008861'; USER_PHONE='+989120008862'

def _cleanup(app):
 with app.app_context():
  users=User.query.filter(User.phone.in_((OWNER_PHONE,USER_PHONE))).all();ids=[u.id for u in users]
  with get_giso_db_conn() as c:
   centers=[r[0] for r in c.execute('SELECT id FROM beauty_centers WHERE owner_user_id IN (%s)'%(','.join('?'*len(ids)) or '0'),ids).fetchall()]
   convs=[r[0] for r in c.execute('SELECT id FROM beauty_center_conversations WHERE center_id IN (%s)'%(','.join('?'*len(centers)) or '0'),centers).fetchall()]
   if convs:c.execute('DELETE FROM beauty_center_messages WHERE conversation_id IN (%s)'%','.join('?'*len(convs)),convs)
   if centers:c.execute('DELETE FROM beauty_center_conversations WHERE center_id IN (%s)'%','.join('?'*len(centers)),centers);c.execute('DELETE FROM beauty_centers WHERE id IN (%s)'%','.join('?'*len(centers)),centers)
   c.execute("DELETE FROM giso_notifications WHERE source_type='beauty_center_message' AND recipient_id IN (?,?)",(OWNER_PHONE,USER_PHONE))
   c.commit()
  for u in users:db.session.delete(u)
  db.session.commit()

def test_lightweight_chat_ownership_read_report_and_close():
 app=create_app();_cleanup(app)
 try:
  with app.app_context():
   owner=User(phone=OWNER_PHONE,password_hash=generate_password_hash('x'));user=User(phone=USER_PHONE,password_hash=generate_password_hash('x'));db.session.add_all([owner,user]);db.session.commit()
   ok,msg,center=create_center(owner.id,{'name':'مرکز چت','category':'hair','center_type':'hair_center','city':'مشهد','business_phone':'09120008861','services':['haircut'],'terms_accepted':True},'uploads/hair_20260810140337.jpg');assert ok,msg
   assert admin_set_status(center['id'],'published')[0]
   ok,msg,conv=get_or_create_conversation(center['id'],user.id);assert ok,msg
   assert get_or_create_conversation(center['id'],user.id)[2]['id']==conv['id']
   assert send_conversation_message(conv['id'],user.id,'هزینه تقریبی چقدر است؟')[0]
   assert send_conversation_message(conv['id'],owner.id,'پس از بررسی شرایط اعلام می‌شود.')[0]
   with get_giso_db_conn() as c:
    notifications=c.execute("SELECT recipient_id FROM giso_notifications WHERE source_type='beauty_center_message' ORDER BY id").fetchall()
   assert {row['recipient_id'] for row in notifications} == {OWNER_PHONE,USER_PHONE}
   messages=conversation_messages(conv['id'],user.id);assert len(messages)==2 and messages[-1]['is_read']==1
   assert not conversation_for_party(conv['id'],owner.id+999)[0]
   assert close_conversation(conv['id'],owner.id)[0]
   assert not send_conversation_message(conv['id'],user.id,'بعدی')[0]
 finally:_cleanup(app)

def test_chat_ui_has_safety_and_no_payment_or_booking_form():
 from pathlib import Path
 html=(Path(__file__).resolve().parents[2]/'giso/beauty_centers/templates/beauty_centers/chat.html').read_text(encoding='utf-8')
 assert 'قیمت نهایی، رزرو، پرداخت و ارائه خدمت خارج از گیسو' in html
 assert 'name="message_text"' in html
 assert 'ارسال فایل' not in html and 'پرداخت آنلاین' not in html
