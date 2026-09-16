# -*- coding: utf-8 -*-
"""Privacy-minimal UX events. Never stores field values, chat text, URLs with query strings or IPs."""
from giso.base import get_giso_db_conn
ALLOWED={'page_view','action_click','form_start','form_error','form_submit'}
_SCHEMA_READY=False
SCHEMA="""CREATE TABLE IF NOT EXISTS giso_ux_events(id INTEGER PRIMARY KEY AUTOINCREMENT,event_type TEXT NOT NULL,page_path TEXT NOT NULL DEFAULT '/',element_key TEXT DEFAULT '',actor_type TEXT DEFAULT 'guest',actor_id TEXT DEFAULT '',device_type TEXT DEFAULT '',created_at TEXT DEFAULT '');CREATE INDEX IF NOT EXISTS idx_ux_event_date ON giso_ux_events(event_type,created_at);CREATE INDEX IF NOT EXISTS idx_ux_event_page ON giso_ux_events(page_path,created_at);"""
def ensure(conn=None):
 global _SCHEMA_READY
 if _SCHEMA_READY:return
 own=conn is None
 if own:conn=get_giso_db_conn()
 try:
  conn.executescript(SCHEMA)
  if own:conn.commit()
  _SCHEMA_READY=True
 finally:
  if own:conn.close()
def record_batch(events,actor_type='guest',actor_id=''):
 try:
  from giso.monitoring_settings import enabled
  if not enabled('behavior'):return 0
 except Exception:return 0
 clean=[]
 for e in list(events or [])[:20]:
  kind=str(e.get('type') or '')
  if kind not in ALLOWED:continue
  path=str(e.get('page') or '/').split('?',1)[0][:180]
  if not path.startswith('/'):path='/'
  key=str(e.get('key') or '')[:80]
  device=str(e.get('device') or '')[:20]
  clean.append((kind,path,key,str(actor_type)[:20],str(actor_id)[:80],device))
 if not clean:return 0
 with get_giso_db_conn() as c:
  ensure(c);c.executemany("INSERT INTO giso_ux_events(event_type,page_path,element_key,actor_type,actor_id,device_type,created_at) VALUES(?,?,?,?,?,?,datetime('now','localtime'))",clean);c.execute("DELETE FROM giso_ux_events WHERE created_at<datetime('now','localtime','-30 days')");c.commit()
 return len(clean)
def report():
 with get_giso_db_conn() as c:
  ensure(c)
  totals=[dict(r) for r in c.execute("SELECT event_type,COUNT(*) count FROM giso_ux_events WHERE created_at>=datetime('now','localtime','-24 hours') GROUP BY event_type ORDER BY count DESC").fetchall()]
  pages=[dict(r) for r in c.execute("SELECT page_path,COUNT(*) views FROM giso_ux_events WHERE event_type='page_view' AND created_at>=datetime('now','localtime','-7 days') GROUP BY page_path ORDER BY views DESC LIMIT 30").fetchall()]
  forms=[dict(r) for r in c.execute("SELECT page_path,SUM(event_type='form_start') starts,SUM(event_type='form_submit') submits,SUM(event_type='form_error') errors FROM giso_ux_events WHERE event_type IN ('form_start','form_submit','form_error') AND created_at>=datetime('now','localtime','-7 days') GROUP BY page_path ORDER BY starts DESC LIMIT 30").fetchall()]
 return {'totals':totals,'pages':pages,'forms':forms}
