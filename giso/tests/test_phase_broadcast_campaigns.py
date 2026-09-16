from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
def test_durable_queue_contract():
 s=(ROOT/'giso/broadcasts.py').read_text(encoding='utf-8')
 for x in ('giso_broadcast_campaigns','giso_broadcast_recipients','UNIQUE(campaign_id,user_id)',"LIMIT ?",'attempts>=3','await asyncio.sleep(.15)',"bot_status='processing'",'BEGIN IMMEDIATE'):assert x in s
 assert "min(10,max(1,int(limit)))" in s
def test_superadmin_preview_and_filters():
 r=(ROOT/'giso/panel/routes.py').read_text(encoding='utf-8');h=(ROOT/'giso/panel/templates/modules/monitoring.html').read_text(encoding='utf-8')
 assert '@require_super\ndef monitoring_broadcast_prepare' in r
 assert '@require_super\ndef monitoring_broadcast_send' in r
 for x in ('همه کاربران','مالکان مراکز','خریداران بازارچه','فروشندگان بازارچه','تأیید نهایی'):assert x in h
def test_jobqueue_batch_worker():
 s=(ROOT/'giso/bot.py').read_text(encoding='utf-8');assert '_init_broadcast_queue(app)' in s and "limit=10" in s

def test_site_campaign_deduplicates_recipients(tmp_path=None):
 import sqlite3,tempfile
 from pathlib import Path
 import giso.broadcasts as b
 path=Path(tempfile.gettempdir())/'giso_broadcast_test.db'
 if path.exists():path.unlink()
 def conn():
  c=sqlite3.connect(path);c.row_factory=sqlite3.Row;return c
 with conn() as c:
  c.executescript("CREATE TABLE giso_web_auth(id INTEGER PRIMARY KEY,phone TEXT,name TEXT);CREATE TABLE giso_users(bale_id TEXT PRIMARY KEY,phone TEXT,created_at TEXT);CREATE TABLE beauty_centers(owner_user_id INTEGER);CREATE TABLE buyer_profiles(user_id INTEGER);CREATE TABLE hair_listings(seller_user_id INTEGER,deleted_at TEXT);CREATE TABLE giso_notifications(id INTEGER PRIMARY KEY AUTOINCREMENT,category TEXT,subcategory TEXT,title TEXT,message TEXT,target_role TEXT,source_type TEXT,source_id INTEGER,recipient_id TEXT,status TEXT,created_at TEXT);INSERT INTO giso_web_auth VALUES(1,'+989120000001','الف'),(2,'+989120000002','ب');")
 b.get_giso_db_conn=conn
 import giso.panel.modules.notifications as n;n.ensure_notifications_table=lambda:None
 import giso.monitoring_settings as ms;ms.enabled=lambda key:True
 ok,_,cid=b.create_campaign('عنوان','پیام','','site','all','super');assert ok and cid
 with conn() as c:
  assert c.execute('SELECT COUNT(*) FROM giso_broadcast_recipients').fetchone()[0]==2
  assert c.execute('SELECT COUNT(*) FROM giso_notifications').fetchone()[0]==2
 path.unlink(missing_ok=True)

if __name__=='__main__':test_durable_queue_contract();test_superadmin_preview_and_filters();test_jobqueue_batch_worker();test_site_campaign_deduplicates_recipients()
