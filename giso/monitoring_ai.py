# -*- coding: utf-8 -*-
"""Aggregated monitoring overview and read-only daily AI summaries."""
import json
from giso.base import get_giso_db_conn
SCHEMA="""CREATE TABLE IF NOT EXISTS giso_monitoring_ai_reports(id INTEGER PRIMARY KEY AUTOINCREMENT,period_start TEXT,period_end TEXT,summary TEXT,provider TEXT DEFAULT '',status TEXT DEFAULT 'ready',created_at TEXT DEFAULT '');CREATE UNIQUE INDEX IF NOT EXISTS ux_monitoring_ai_day ON giso_monitoring_ai_reports(period_end);"""
def ensure(conn=None):
 own=conn is None
 if own:conn=get_giso_db_conn()
 try:
  conn.executescript(SCHEMA)
  if own:conn.commit()
 finally:
  if own:conn.close()
def aggregate():
 with get_giso_db_conn() as c:
  ensure(c)
  one=lambda sql:int((c.execute(sql).fetchone()[0] or 0))
  tables={r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'")}
  def safe(table,sql):return one(sql) if table in tables else 0
  return {'open_errors':safe('giso_system_errors',"SELECT COUNT(*) FROM giso_system_errors WHERE status='open'"),'errors_24h':safe('giso_system_errors',"SELECT COALESCE(SUM(count),0) FROM giso_system_errors WHERE last_seen>=datetime('now','localtime','-1 day')"),'suspicious_24h':safe('giso_login_events',"SELECT COUNT(*) FROM giso_login_events WHERE suspicious=1 AND created_at>=datetime('now','localtime','-1 day')"),'events_24h':safe('giso_ux_events',"SELECT COUNT(*) FROM giso_ux_events WHERE created_at>=datetime('now','localtime','-1 day')"),'campaigns_sending':safe('giso_broadcast_campaigns',"SELECT COUNT(*) FROM giso_broadcast_campaigns WHERE status IN ('queued','sending')"),'bot_sent_24h':safe('giso_broadcast_campaigns',"SELECT COALESCE(SUM(bot_sent),0) FROM giso_broadcast_campaigns WHERE created_at>=datetime('now','localtime','-1 day')"),'bot_failed_24h':safe('giso_broadcast_campaigns',"SELECT COALESCE(SUM(bot_failed),0) FROM giso_broadcast_campaigns WHERE created_at>=datetime('now','localtime','-1 day')"),'ai_providers_ok':safe('giso_ai_providers',"SELECT COUNT(*) FROM giso_ai_providers WHERE enabled=1 AND lower(COALESCE(last_status,'')) LIKE 'ok%'")}
def list_reports(limit=30):
 with get_giso_db_conn() as c:ensure(c);return [dict(r) for r in c.execute('SELECT * FROM giso_monitoring_ai_reports ORDER BY id DESC LIMIT ?',(limit,)).fetchall()]
def due_state():
 from giso.monitoring_settings import get_ai_hour, get_ai_interval_hours
 with get_giso_db_conn() as c:
  ensure(c);last=c.execute('SELECT created_at FROM giso_monitoring_ai_reports ORDER BY id DESC LIMIT 1').fetchone();busy=c.execute("SELECT COUNT(*) FROM giso_ux_events WHERE created_at>=datetime('now','localtime','-5 minutes')").fetchone()[0] if c.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='giso_ux_events'").fetchone() else 0;hour=int(c.execute("SELECT strftime('%H','now','localtime')").fetchone()[0])
  hours=get_ai_interval_hours()
  due=not last or c.execute("SELECT datetime(?)<=datetime('now','localtime',?)",(last['created_at'],f'-{int(hours)} hours')).fetchone()[0]
 return bool(due and hour==get_ai_hour() and int(busy or 0)<50)
async def generate(force=False):
 from giso.monitoring_settings import enabled
 if not enabled('ai_reports'):return False,'گزارش هوشمند غیرفعال است.'
 if not force and not due_state():return False,'هنوز زمان اجرای گزارش نرسیده یا سامانه شلوغ است.'
 data=aggregate();prompt=("فقط بر اساس آمار تجمیعی زیر، یک گزارش کوتاه فارسی در ۴ تا ۷ خط بنویس. هیچ اقدام، حدس هویتی یا تغییر تنظیمات پیشنهاد نده. داده خصوصی وجود ندارد.\n"+json.dumps(data,ensure_ascii=False))
 try:
  from giso.ai_runtime import chat_with_managed_ai
  result=await chat_with_managed_ai([{'role':'user','content':prompt}],actor_key='monitoring:daily',role='super',channel='monitoring',section='reports',question_text='daily monitoring summary',max_tokens=450)
  if not result.get('ok'):return False,result.get('text') or 'پاسخ AI دریافت نشد.'
  text=str(result.get('text') or '')[:4000];provider=str(result.get('provider') or '')[:80]
 except Exception as exc:return False,f'خطا: {type(exc).__name__}'
 with get_giso_db_conn() as c:
  ensure(c);day=c.execute("SELECT date('now','localtime')").fetchone()[0];c.execute("INSERT INTO giso_monitoring_ai_reports(period_start,period_end,summary,provider,created_at) VALUES(date('now','localtime','-1 day'),?,?,?,datetime('now','localtime')) ON CONFLICT DO NOTHING",(day,text,provider));c.commit()
 return True,'گزارش روزانه ساخته شد.'
