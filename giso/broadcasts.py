# -*- coding: utf-8 -*-
"""Durable broadcast campaigns: site inbox immediately, Bale in batches of ten."""
import asyncio
from giso.base import get_giso_db_conn, normalize_phone

SCHEMA = """
CREATE TABLE IF NOT EXISTS giso_broadcast_campaigns(
 id INTEGER PRIMARY KEY AUTOINCREMENT,title TEXT NOT NULL,message TEXT NOT NULL,link_url TEXT DEFAULT '',
 channel TEXT NOT NULL,target TEXT NOT NULL,status TEXT DEFAULT 'queued',created_by TEXT DEFAULT '',
 total_count INTEGER DEFAULT 0,site_count INTEGER DEFAULT 0,bot_sent INTEGER DEFAULT 0,
 bot_failed INTEGER DEFAULT 0,no_bale INTEGER DEFAULT 0,created_at TEXT DEFAULT '',finished_at TEXT DEFAULT '');
CREATE TABLE IF NOT EXISTS giso_broadcast_recipients(
 id INTEGER PRIMARY KEY AUTOINCREMENT,campaign_id INTEGER NOT NULL,user_id INTEGER NOT NULL,phone TEXT DEFAULT '',
 bale_id TEXT DEFAULT '',notification_id INTEGER DEFAULT 0,bot_status TEXT DEFAULT 'none',attempts INTEGER DEFAULT 0,
 last_error TEXT DEFAULT '',claimed_at TEXT DEFAULT '',sent_at TEXT DEFAULT '',UNIQUE(campaign_id,user_id));
CREATE INDEX IF NOT EXISTS idx_broadcast_queue ON giso_broadcast_recipients(bot_status,campaign_id,id);
"""
TARGETS=("all","centers","buyers","sellers")
CHANNELS=("site","bot","both")
_SCHEMA_READY=False

def ensure_tables(conn=None):
 global _SCHEMA_READY
 # با conn صریح همیشه مطمئن شو (تست/DB جدا)؛ بهینه‌سازی فقط برای اتصال خودکار است.
 if _SCHEMA_READY and conn is None:return
 own=conn is None
 if own:conn=get_giso_db_conn()
 try:
  conn.executescript(SCHEMA)
  cols={r[1] for r in conn.execute('PRAGMA table_info(giso_broadcast_recipients)').fetchall()}
  if 'claimed_at' not in cols:conn.execute("ALTER TABLE giso_broadcast_recipients ADD COLUMN claimed_at TEXT DEFAULT ''")
  if own:conn.commit()
  _SCHEMA_READY=True
 finally:
  if own:conn.close()

def _target_users(conn,target):
 where=""
 if target=='centers':where="WHERE EXISTS(SELECT 1 FROM beauty_centers c WHERE c.owner_user_id=u.id)"
 elif target=='buyers':where="WHERE EXISTS(SELECT 1 FROM buyer_profiles b WHERE b.user_id=u.id)"
 elif target=='sellers':where="WHERE EXISTS(SELECT 1 FROM hair_listings l WHERE l.seller_user_id=u.id AND COALESCE(l.deleted_at,'')='')"
 return conn.execute(f"SELECT u.id,u.phone,(SELECT gu.bale_id FROM giso_users gu WHERE gu.phone=u.phone AND COALESCE(gu.bale_id,'')<>'' ORDER BY gu.created_at DESC LIMIT 1) bale_id FROM giso_web_auth u {where} ORDER BY u.id").fetchall()

def create_campaign(title,message,link_url,channel,target,actor):
 title=" ".join(str(title or '').split())[:160];message=str(message or '').strip()[:3000];link_url=str(link_url or '').strip()[:500]
 if not title or not message:return False,"عنوان و متن پیام لازم است.",0
 if channel not in CHANNELS or target not in TARGETS:return False,"کانال یا مخاطب نامعتبر است.",0
 try:
  from giso.monitoring_settings import enabled
  if not enabled('broadcasts'):return False,"پیام‌های سراسری در تنظیمات پایش غیرفعال است.",0
 except Exception:pass
 try:
  from giso.panel.modules.notifications import ensure_notifications_table
  ensure_notifications_table()
 except Exception:pass
 with get_giso_db_conn() as conn:
  ensure_tables(conn);conn.execute('BEGIN IMMEDIATE');users=_target_users(conn,target)
  cur=conn.execute("INSERT INTO giso_broadcast_campaigns(title,message,link_url,channel,target,created_by,created_at,total_count) VALUES(?,?,?,?,?,?,datetime('now','localtime'),?)",(title,message,link_url,channel,target,str(actor),len(users)));cid=cur.lastrowid;site_count=no_bale=0
  for u in users:
   notification_id=0
   if channel in ('site','both'):
    n=conn.execute("INSERT INTO giso_notifications(category,subcategory,title,message,target_role,source_type,source_id,recipient_id,status,created_at) VALUES('system','admin_broadcast',?,?,'user','broadcast',?,?, 'unread',datetime('now','localtime'))",(f"📣 پیام مستقیم مدیریت گیسو — {title}",message,cid,normalize_phone(u['phone'])));notification_id=n.lastrowid;site_count+=1
   bale=str(u['bale_id'] or '')
   bot_status='pending' if channel in ('bot','both') and bale.isdigit() else 'none'
   if channel in ('bot','both') and not bale.isdigit():no_bale+=1
   conn.execute("INSERT INTO giso_broadcast_recipients(campaign_id,user_id,phone,bale_id,notification_id,bot_status) VALUES(?,?,?,?,?,?)",(cid,u['id'],normalize_phone(u['phone']),bale,notification_id,bot_status))
  status='sending' if channel in ('bot','both') and any(str(u['bale_id'] or '').isdigit() for u in users) else 'completed'
  conn.execute("UPDATE giso_broadcast_campaigns SET site_count=?,no_bale=?,status=?,finished_at=CASE WHEN ?='completed' THEN datetime('now','localtime') ELSE '' END WHERE id=?",(site_count,no_bale,status,status,cid));conn.commit()
 return True,"کمپین ثبت شد.",cid

async def process_bot_batch(bot,limit=10):
 try:
  from giso.monitoring_settings import enabled
  if not enabled('broadcasts'):return 0
 except Exception:return 0
 with get_giso_db_conn() as conn:
  ensure_tables(conn);conn.execute('BEGIN IMMEDIATE')
  conn.execute("UPDATE giso_broadcast_recipients SET bot_status='pending',claimed_at='' WHERE bot_status='processing' AND claimed_at<datetime('now','localtime','-5 minutes')")
  rows=conn.execute("SELECT r.*,c.title,c.message,c.link_url FROM giso_broadcast_recipients r JOIN giso_broadcast_campaigns c ON c.id=r.campaign_id WHERE r.bot_status='pending' AND r.attempts<3 ORDER BY r.id LIMIT ?",(min(10,max(1,int(limit))),)).fetchall()
  if rows:
   ids=','.join('?' for _ in rows);conn.execute(f"UPDATE giso_broadcast_recipients SET bot_status='processing',claimed_at=datetime('now','localtime') WHERE id IN ({ids})",tuple(r['id'] for r in rows))
  conn.commit()
 for row in rows:
  ok=False;err=''
  try:
   markup=None
   if row['link_url']:
    from telegram import InlineKeyboardButton,InlineKeyboardMarkup
    markup=InlineKeyboardMarkup([[InlineKeyboardButton('مشاهده',url=row['link_url'])]])
   await bot.send_message(chat_id=int(row['bale_id']),text=f"📣 پیام مستقیم مدیریت گیسو\n━━━━━━━━━━━━━━━━\n{row['title']}\n\n{row['message']}",reply_markup=markup);ok=True
  except Exception as exc:err=type(exc).__name__[:80]
  with get_giso_db_conn() as conn:
   attempts=int(row['attempts'] or 0)+1;status='sent' if ok else ('failed' if attempts>=3 else 'pending')
   conn.execute("UPDATE giso_broadcast_recipients SET bot_status=?,attempts=?,last_error=?,claimed_at='',sent_at=CASE WHEN ?='sent' THEN datetime('now','localtime') ELSE sent_at END WHERE id=?",(status,attempts,err,status,row['id']))
   conn.execute("UPDATE giso_broadcast_campaigns SET bot_sent=(SELECT COUNT(*) FROM giso_broadcast_recipients WHERE campaign_id=? AND bot_status='sent'),bot_failed=(SELECT COUNT(*) FROM giso_broadcast_recipients WHERE campaign_id=? AND bot_status='failed') WHERE id=?",(row['campaign_id'],row['campaign_id'],row['campaign_id']));conn.commit()
  await asyncio.sleep(.15)
 for cid in {int(r['campaign_id']) for r in rows}:
  with get_giso_db_conn() as conn:
   pending=conn.execute("SELECT COUNT(*) FROM giso_broadcast_recipients WHERE campaign_id=? AND bot_status IN ('pending','processing')",(cid,)).fetchone()[0]
   if not pending:conn.execute("UPDATE giso_broadcast_campaigns SET status='completed',finished_at=datetime('now','localtime') WHERE id=?",(cid,));conn.commit()
 return len(rows)

def campaign_list(limit=50):
 with get_giso_db_conn() as conn:
  ensure_tables(conn);rows=conn.execute("SELECT c.*,(SELECT COUNT(*) FROM giso_broadcast_recipients r JOIN giso_notifications n ON n.id=r.notification_id WHERE r.campaign_id=c.id AND n.status<>'unread') read_count FROM giso_broadcast_campaigns c ORDER BY c.id DESC LIMIT ?",(limit,)).fetchall()
 return [dict(r) for r in rows]


# ═══════════ تریگر سمت سایت (مستقل از ربات) — رفع وابستگی پیام سراسری به job بات ═══════════
def process_site_bot_batch(limit=5):
 """پردازش بخشِ بله‌ی صف پیام سراسری با send_bot_push سایت (بدون نیاز به ربات در حال اجرا).

 idempotent و امن: فقط رکوردهای pending با bale_id معتبر را پردازش می‌کند؛ همان
 رکوردهایی که worker بات هم می‌بیند. claim با UPDATE اتمیک از پردازش دوباره توسط
 بات/سایت جلوگیری می‌کند. شمارش کمپین پس از اتمام به‌روزرسانی می‌شود.
 خروجی: تعداد پیام‌های ارسال‌شده در این فراخوانی.
 """
 try:
  from giso.monitoring_settings import enabled
  if not enabled('broadcasts'):return 0
 except Exception:return 0
 sent=0
 with get_giso_db_conn() as conn:
  ensure_tables(conn);conn.execute('BEGIN IMMEDIATE')
  conn.execute("UPDATE giso_broadcast_recipients SET bot_status='pending',claimed_at='' WHERE bot_status='processing' AND claimed_at<datetime('now','localtime','-5 minutes')")
  rows=conn.execute("SELECT r.id,r.campaign_id,r.bale_id,c.title,c.message,c.link_url FROM giso_broadcast_recipients r JOIN giso_broadcast_campaigns c ON c.id=r.campaign_id WHERE r.bot_status='pending' AND r.attempts<3 AND r.bale_id GLOB '[0-9]*' ORDER BY r.id LIMIT ?",(min(5,max(1,int(limit))),)).fetchall()
  if rows:
   ids=','.join('?' for _ in rows);conn.execute(f"UPDATE giso_broadcast_recipients SET bot_status='processing',claimed_at=datetime('now','localtime') WHERE id IN ({ids})",tuple(r['id'] for r in rows))
  conn.commit()
 for row in rows:
  ok=False;err=''
  try:
   from giso.base import send_bot_push
   text=f"📣 پیام مستقیم مدیریت گیسو\n━━━━━━━━━━━━━━━━\n{row['title']}\n\n{row['message']}"
   ok=bool(send_bot_push(int(row['bale_id']),text))
  except Exception as exc:err=type(exc).__name__[:80]
  with get_giso_db_conn() as conn:
   attempts_field=conn.execute('SELECT attempts FROM giso_broadcast_recipients WHERE id=?',(row['id'],)).fetchone()
   attempts=int((attempts_field['attempts'] if attempts_field else 0) or 0)+1
   status='sent' if ok else ('failed' if attempts>=3 else 'pending')
   conn.execute("UPDATE giso_broadcast_recipients SET bot_status=?,attempts=?,last_error=?,claimed_at='',sent_at=CASE WHEN ?='sent' THEN datetime('now','localtime') ELSE sent_at END WHERE id=?",(status,attempts,err,status,row['id']))
   conn.execute("UPDATE giso_broadcast_campaigns SET bot_sent=(SELECT COUNT(*) FROM giso_broadcast_recipients WHERE campaign_id=? AND bot_status='sent'),bot_failed=(SELECT COUNT(*) FROM giso_broadcast_recipients WHERE campaign_id=? AND bot_status='failed') WHERE id=?",(row['campaign_id'],row['campaign_id'],row['campaign_id']))
   conn.commit()
  if ok:sent+=1
 for cid in {int(r['campaign_id']) for r in rows}:
  with get_giso_db_conn() as conn:
   pending=conn.execute("SELECT COUNT(*) FROM giso_broadcast_recipients WHERE campaign_id=? AND bot_status IN ('pending','processing')",(cid,)).fetchone()[0]
   if not pending:conn.execute("UPDATE giso_broadcast_campaigns SET status='completed',finished_at=datetime('now','localtime') WHERE id=?",(cid,));conn.commit()
 return sent
