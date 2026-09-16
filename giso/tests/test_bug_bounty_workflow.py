import sqlite3
from pathlib import Path
from giso import bug_reports, wallet
from giso import wallet_missions


def factory(path):
 def connect():
  c=sqlite3.connect(path);c.row_factory=sqlite3.Row;return c
 return connect

def seed(path):
 with sqlite3.connect(path) as c:
  c.executescript("""CREATE TABLE giso_web_auth(id INTEGER PRIMARY KEY,phone TEXT);INSERT INTO giso_web_auth VALUES(1,'+98912');
CREATE TABLE wallet_missions(id INTEGER PRIMARY KEY,code TEXT,title TEXT,reward_amount INTEGER,reward_scope TEXT,reward_points INTEGER DEFAULT 0,mission_type TEXT DEFAULT 'once',is_active INTEGER,is_deleted INTEGER);INSERT INTO wallet_missions VALUES(9,'bug_report_approved','باگ',30000,'spend',0,'once',1,0);
CREATE TABLE wallet_mission_completions(id INTEGER PRIMARY KEY,mission_id INTEGER,user_id INTEGER,event_key TEXT,reward_amount INTEGER,reward_scope TEXT,reward_transaction_id INTEGER,completed_at TEXT,UNIQUE(mission_id,user_id));
CREATE TABLE wallet_transactions(id INTEGER PRIMARY KEY,user_id INTEGER,kind TEXT,amount INTEGER,status TEXT,source_type TEXT,source_id INTEGER,balance_scope TEXT,idempotency_key TEXT UNIQUE,description TEXT,created_at TEXT);""")

def test_submission_never_pays_and_duplicate_is_detected(monkeypatch,tmp_path):
 db=tmp_path/'x.db';seed(db);connect=factory(db)
 monkeypatch.setattr(bug_reports,'get_giso_db_conn',connect);monkeypatch.setattr(wallet,'get_giso_db_conn',connect);monkeypatch.setattr(wallet_missions,'get_giso_db_conn',connect)
 ok,_,first=bug_reports.submit(1,'+98912','خطای دکمه خرید','پس از زدن دکمه خرید هیچ اتفاقی رخ نمی‌دهد و صفحه ثابت می‌ماند','/shop')
 assert ok
 ok,_,second=bug_reports.submit(1,'+98912','خطای دکمه خرید','پس از زدن دکمه خرید هیچ اتفاقی رخ نمی‌دهد و صفحه ثابت می‌ماند','/shop')
 with sqlite3.connect(db) as c:
  assert c.execute('select count(*) from wallet_transactions').fetchone()[0]==0
  assert c.execute('select status,duplicate_of from giso_bug_reports where id=?',(second,)).fetchone()==('pending',first)

def test_only_manual_approval_pays_spend_once(monkeypatch,tmp_path):
 db=tmp_path/'x.db';seed(db);connect=factory(db)
 monkeypatch.setattr(bug_reports,'get_giso_db_conn',connect);monkeypatch.setattr(wallet,'get_giso_db_conn',connect);monkeypatch.setattr(wallet_missions,'get_giso_db_conn',connect)
 _,_,rid=bug_reports.submit(1,'+98912','خرابی فرم پرداخت','فرم پرداخت پس از تکمیل همه فیلدها پیام خطای نامشخص نشان می‌دهد','/shop/cart')
 ok,_=bug_reports.review(rid,'approved','super-1','بازتولید و تأیید شد')
 assert ok
 assert bug_reports.review(rid,'approved','super-1')[0] is False
 with sqlite3.connect(db) as c:
  assert c.execute('select amount,balance_scope from wallet_transactions').fetchone()==(30000,'spend')
  assert c.execute('select reward_amount,status from giso_bug_reports where id=?',(rid,)).fetchone()==(30000,'approved')

def test_invalid_external_path_rejected(monkeypatch,tmp_path):
 db=tmp_path/'x.db';seed(db);monkeypatch.setattr(bug_reports,'get_giso_db_conn',factory(db))
 assert bug_reports.submit(1,'+98912','عنوان معتبر باگ','این توضیح به اندازه کافی برای گزارش معتبر طولانی است','https://evil.test')[0] is False

def test_ui_routes_require_super_and_explicit_decision():
 root=Path(__file__).resolve().parents[2]
 routes=(root/'giso/panel/routes.py').read_text(); user=(root/'giso/panel_user/routes.py').read_text()
 assert '@require_super\ndef monitoring_bug_review' in routes
 assert 'decision = (request.form.get("decision")' in routes
 assert 'bug_report_create' in user
