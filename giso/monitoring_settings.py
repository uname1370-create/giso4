import threading,time
from giso.base import get_giso_db_conn
KEYS=('master','errors','login_history','suspicious_login','broadcasts','behavior','ai_reports')
_CACHE={"at":0.0,"data":None};_LOCK=threading.Lock();TTL=45

def _load():
 with get_giso_db_conn() as c:
  c.execute("CREATE TABLE IF NOT EXISTS giso_config(id INTEGER PRIMARY KEY,key TEXT UNIQUE,value TEXT,updated_at TEXT)")
  rows={r['key']:r['value'] for r in c.execute("SELECT key,value FROM giso_config WHERE key LIKE 'monitoring_%'")}
 return {k:rows.get('monitoring_'+k,'1')=='1' for k in KEYS}

def get_settings(force=False):
 now=time.monotonic()
 with _LOCK:
  if not force and _CACHE['data'] is not None and now-_CACHE['at']<TTL:return dict(_CACHE['data'])
  data=_load();_CACHE.update(at=now,data=data);return dict(data)

def enabled(key):
 data=get_settings();return bool(data.get('master',True) and data.get(key,False))

def get_ai_hour():
 with get_giso_db_conn() as c:
  c.execute("CREATE TABLE IF NOT EXISTS giso_config(id INTEGER PRIMARY KEY,key TEXT UNIQUE,value TEXT,updated_at TEXT)")
  row=c.execute("SELECT value FROM giso_config WHERE key='monitoring_ai_hour'").fetchone()
 try:return max(0,min(23,int(row[0] if row else 4)))
 except Exception:return 4

def get_ai_interval_hours():
 """بازهٔ تولید گزارش دوره‌ای هوشمند، به ساعت (پیش‌فرض ۲۴)."""
 with get_giso_db_conn() as c:
  c.execute("CREATE TABLE IF NOT EXISTS giso_config(id INTEGER PRIMARY KEY,key TEXT UNIQUE,value TEXT,updated_at TEXT)")
  row=c.execute("SELECT value FROM giso_config WHERE key='monitoring_ai_interval_hours'").fetchone()
 try:return max(1,min(168,int(row[0] if row else 24)))
 except Exception:return 24

def get_report_refresh_hours():
 """بازهٔ تازه‌سازی فایل گزارش متنی خطاها، به ساعت (پیش‌فرض ۳)."""
 with get_giso_db_conn() as c:
  c.execute("CREATE TABLE IF NOT EXISTS giso_config(id INTEGER PRIMARY KEY,key TEXT UNIQUE,value TEXT,updated_at TEXT)")
  row=c.execute("SELECT value FROM giso_config WHERE key='monitoring_report_refresh_hours'").fetchone()
 try:return max(1,min(168,int(row[0] if row else 3)))
 except Exception:return 3

def save(values,ai_hour=None,interval_hours=None,report_refresh_hours=None):
 with get_giso_db_conn() as c:
  c.execute("CREATE TABLE IF NOT EXISTS giso_config(id INTEGER PRIMARY KEY,key TEXT UNIQUE,value TEXT,updated_at TEXT)")
  for k in KEYS:c.execute("INSERT INTO giso_config(key,value,updated_at) VALUES(?,?,datetime('now','localtime')) ON CONFLICT(key) DO UPDATE SET value=excluded.value,updated_at=excluded.updated_at",('monitoring_'+k,'1' if values.get(k) else '0'))
  if ai_hour is not None:
   try:h=max(0,min(23,int(ai_hour)))
   except Exception:h=4
   c.execute("INSERT INTO giso_config(key,value,updated_at) VALUES('monitoring_ai_hour',?,datetime('now','localtime')) ON CONFLICT(key) DO UPDATE SET value=excluded.value,updated_at=excluded.updated_at",(str(h),))
  if interval_hours is not None:
   try:ih=max(1,min(168,int(interval_hours)))
   except Exception:ih=24
   c.execute("INSERT INTO giso_config(key,value,updated_at) VALUES('monitoring_ai_interval_hours',?,datetime('now','localtime')) ON CONFLICT(key) DO UPDATE SET value=excluded.value,updated_at=excluded.updated_at",(str(ih),))
  if report_refresh_hours is not None:
   try:rh=max(1,min(168,int(report_refresh_hours)))
   except Exception:rh=3
   c.execute("INSERT INTO giso_config(key,value,updated_at) VALUES('monitoring_report_refresh_hours',?,datetime('now','localtime')) ON CONFLICT(key) DO UPDATE SET value=excluded.value,updated_at=excluded.updated_at",(str(rh),))
  c.commit()
 with _LOCK:_CACHE.update(at=0.0,data=None)
