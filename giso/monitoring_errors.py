import hashlib,re
from giso.base import get_giso_db_conn
SCHEMA="""CREATE TABLE IF NOT EXISTS giso_system_errors(id INTEGER PRIMARY KEY, fingerprint TEXT UNIQUE,service TEXT,section TEXT,severity TEXT,summary TEXT,count INTEGER DEFAULT 1,first_seen TEXT,last_seen TEXT,status TEXT DEFAULT 'open');CREATE INDEX IF NOT EXISTS idx_system_errors_last ON giso_system_errors(last_seen,status);"""
def ensure():
 with get_giso_db_conn() as c:c.executescript(SCHEMA);c.commit()
def record(service,section,error,severity='error'):
 try:
  from giso.monitoring_settings import enabled
  if not enabled('errors'):return
 except Exception:pass
 text=str(error or 'خطای نامشخص');text=re.sub(r'(?i)(token|password|api[_-]?key)\s*[=:]\s*\S+',r'\1=[حذف‌شده]',text)[:500];fp=hashlib.sha256(f'{service}|{section}|{type(error).__name__}|{text}'.encode()).hexdigest()
 try:
  with get_giso_db_conn() as c:
   c.executescript(SCHEMA);c.execute("INSERT INTO giso_system_errors(fingerprint,service,section,severity,summary,first_seen,last_seen) VALUES(?,?,?,?,?,datetime('now','localtime'),datetime('now','localtime')) ON CONFLICT(fingerprint) DO UPDATE SET count=count+1,last_seen=datetime('now','localtime')",(fp,str(service)[:50],str(section)[:160],str(severity)[:20],text));c.commit()
 except Exception:pass
MANUAL_SCHEMA="""CREATE TABLE IF NOT EXISTS giso_manual_error_reports(
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 reporter TEXT DEFAULT '',
 audience TEXT DEFAULT '',
 problem TEXT DEFAULT '',
 error_source TEXT DEFAULT '',
 cause TEXT DEFAULT '',
 why TEXT DEFAULT '',
 severity TEXT DEFAULT 'error',
 status TEXT DEFAULT 'open',
 created_at TEXT DEFAULT ''
);"""

def list_errors(limit=200):
 ensure()
 with get_giso_db_conn() as c:return [dict(r) for r in c.execute('SELECT * FROM giso_system_errors ORDER BY last_seen DESC LIMIT ?',(limit,)).fetchall()]


def record_manual(reporter='', audience='', problem='', error_source='', cause='', why='', severity='error'):
 """ثبت گزارش دستی خطا توسط سوپرادمین/ادمین: مردم/مشکل/منبع خطا/علت/چرایی.

 هم در جدول جزئیات دستی ذخیره می‌شود و هم به‌صورت یک ردیف تجمیعی در
 giso_system_errors (با فینگرپرینت ثابت per-problem) تا در «خطاهای مرکزی» دیده شود.
 """
 try:
  ensure()
  with get_giso_db_conn() as c:
   c.executescript(MANUAL_SCHEMA)
   problem_s=str(problem or '').strip()[:500]
   if not problem_s:return False,'متن مشکل الزامی است.'
   now=datetime_now()
   c.execute("INSERT INTO giso_manual_error_reports(reporter,audience,problem,error_source,cause,why,severity,status,created_at) VALUES(?,?,?,?,?,?,?, 'open', ?)",
    (str(reporter or '')[:40], str(audience or '')[:200], problem_s, str(error_source or '')[:300], str(cause or '')[:500], str(why or '')[:500], str(severity or 'error')[:20], now))
   # انعکاس تجمیعی در جدول خطاها (هر گزارش دستی فینگرپرینت یکتا دارد)
   fp=hashlib.sha256(f'manual|{problem_s}|{now}'.encode()).hexdigest()
   c.execute("INSERT INTO giso_system_errors(fingerprint,service,section,severity,summary,first_seen,last_seen) VALUES(?,?,?,?,?,?,?) "
             "ON CONFLICT(fingerprint) DO UPDATE SET count=count+1,last_seen=excluded.last_seen",
    (fp,'گزارش دستی','گزارش دستی', str(severity or 'error')[:20], problem_s[:500], now, now))
   c.commit()
  return True,'گزارش دستی خطا ثبت شد.'
 except Exception as exc:
  return False,f'ثبت گزارش دستی ناموفق بود: {str(exc)[:120]}'


def list_manual_reports(limit=100):
 ensure()
 with get_giso_db_conn() as c:
  try:c.executescript(MANUAL_SCHEMA);c.commit()
  except Exception:pass
  return [dict(r) for r in c.execute('SELECT * FROM giso_manual_error_reports ORDER BY id DESC LIMIT ?',(int(limit),)).fetchall()]


def datetime_now():
 import datetime as _dt
 return _dt.datetime.now().strftime('%Y-%m-%d %H:%M:%S')


def build_error_report_text(hours=24):
 """گزارش متنی کامل سیستم: خطاها، ورودهای مشکوک/ناموفق، کمپین‌ها، وضعیت AI و تنظیمات."""
 import datetime as _dt
 ensure()
 now_s=datetime_now()
 lines=[]
 lines.append('════════════════════════════════════════')
 lines.append('  گزارش خطا و وضعیت سیستم گیسو (متنی)')
 lines.append(f'  زمان تولید: {now_s}')
 lines.append(f'  بازهٔ بررسی: {int(hours)} ساعت اخیر')
 lines.append('════════════════════════════════════════')
 lines.append('')
 try:
  with get_giso_db_conn() as c:
   tables={r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'")}
   def safe(sql,params=()):
    try:return c.execute(sql,params).fetchall()
    except Exception:return []
   # ── خطاهای مرکزی ──
   rows=safe("SELECT service,section,severity,summary,count,first_seen,last_seen,status FROM giso_system_errors ORDER BY last_seen DESC LIMIT 300")
   open_n=sum(1 for r in rows if (r['status'] or 'open')=='open')
   lines.append(f'▌ خطاهای مرکزی (ثبت‌شده): {len(rows)} مورد — باز: {open_n}')
   lines.append('  (خطاها فقط خطاهای داخلی ثبت‌شدهٔ سامانه‌اند؛ خالی‌بودن یعنی خطای ۵۰۰ رخ نداده)')
   if rows:
    for r in rows[:100]:
     lines.append(f"  • [{r['severity'] or 'error'}] {r['section'] or ''} | تکرار: {r['count']} | آخرین: {r['last_seen']} | وضعیت: {r['status'] or 'open'}")
     lines.append(f"    {r['summary'] or ''}")
   else:
    lines.append('  ✅ هیچ خطای داخلی‌ای ثبت نشده است.')
   lines.append('')
   # ── گزارش‌های دستی ──
   if 'giso_manual_error_reports' in tables:
    mr=safe("SELECT created_at,audience,problem,error_source,cause,why,severity FROM giso_manual_error_reports ORDER BY id DESC LIMIT 50")
    lines.append(f'▌ گزارش‌های دستی خطا: {len(mr)} مورد')
    for r in mr:
     lines.append(f"  • [{r['severity'] or 'error'}] {r['created_at']}")
     lines.append(f"    مخاطب/بخش: {r['audience'] or '—'}")
     lines.append(f"    مشکل: {r['problem'] or '—'}")
     lines.append(f"    منبع خطا: {r['error_source'] or '—'}")
     lines.append(f"    علت احتمالی: {r['cause'] or '—'}")
     lines.append(f"    چرا/اثر: {r['why'] or '—'}")
   lines.append('')
   # ── ورودهای مشکوک/ناموفق ──
   sus=safe("SELECT COUNT(*) FROM giso_login_events WHERE suspicious=1 AND created_at>=datetime('now','localtime',?)",(f'-{int(hours)} hours',))
   fail=safe("SELECT COUNT(*) FROM giso_login_events WHERE success=0 AND created_at>=datetime('now','localtime',?)",(f'-{int(hours)} hours',))
   lines.append(f'▌ امنیت و ورود ({int(hours)} ساعت اخیر): ورود مشکوک {int(sus[0][0] if sus else 0)} | ورود ناموفق {int(fail[0][0] if fail else 0)}')
   lines.append('')
   # ── کمپین‌ها ──
   sending=safe("SELECT COUNT(*) FROM giso_broadcast_campaigns WHERE status IN ('queued','sending')")
   bfailed=safe("SELECT COALESCE(SUM(bot_failed),0) FROM giso_broadcast_campaigns WHERE created_at>=datetime('now','localtime',?)",(f'-{int(hours)} hours',))
   lines.append(f'▌ پیام‌های سراسری: در حال ارسال {int(sending[0][0] if sending else 0)} | ارسال ناموفق بله {int(bfailed[0][0] if bfailed else 0)}')
   lines.append('')
   # ── AI ──
   aiok=safe("SELECT COUNT(*) FROM giso_ai_providers WHERE enabled=1 AND lower(COALESCE(last_status,'')) LIKE 'ok%'")
   aitot=safe("SELECT COUNT(*) FROM giso_ai_providers WHERE enabled=1")
   lines.append(f'▌ هوش مصنوعی: پروایدر فعال {int(aitot[0][0] if aitot else 0)} | سالم {int(aiok[0][0] if aiok else 0)}')
   lines.append('')
   # ── آمار کلی ──
   for label,sql in (
     ('کاربران سایت',"SELECT COUNT(*) FROM giso_web_auth"),
     ('سفارش‌های فروشگاه (باز)',"SELECT COUNT(*) FROM product_orders WHERE status='pending'"),
     ('درخواست فروش مو (در انتظار)',"SELECT COUNT(*) FROM hair_orders WHERE status IN ('pending','reviewing')"),
     ('تیکت‌های باز',"SELECT COUNT(*) FROM giso_support_tickets WHERE status IN ('new','reviewing')"),
     ('مشاوره‌های باز',"SELECT COUNT(*) FROM consultant_requests WHERE status IN ('new','reviewing','pending','active')"),
   ):
    row=safe(sql)
    lines.append(f'  - {label}: {int(row[0][0] if row else 0)}')
   lines.append('')
   lines.append('── پایان گزارش. این فایل هر چند ساعت یک‌بار (قابل تنظیم در «تنظیمات پایش») تازه می‌شود.')
 except Exception as exc:
  lines.append(f'خطا در ساخت گزارش: {str(exc)[:200]}')
 return '\n'.join(lines)


REPORT_SCHEMA="CREATE TABLE IF NOT EXISTS giso_system_reports(id INTEGER PRIMARY KEY AUTOINCREMENT, kind TEXT, body TEXT, generated_at TEXT, hours INTEGER)"

def get_or_refresh_text_report(force=False, hours=24):
 """گزارش متنی کش‌شده؛ اگر از بازهٔ تنظیم‌شده قدیمی‌تر بود (یا force) تازه ساخته می‌شود.

 خروجی: (text, generated_at, refreshed:bool)
 """
 ensure()
 try:
  from giso.monitoring_settings import get_report_refresh_hours
  refresh_hours=get_report_refresh_hours()
 except Exception:
  refresh_hours=3
 with get_giso_db_conn() as c:
  try:c.executescript(REPORT_SCHEMA);c.commit()
  except Exception:pass
  row=c.execute("SELECT body,generated_at FROM giso_system_reports WHERE kind='errors_text' ORDER BY id DESC LIMIT 1").fetchone()
  stale=True
  if row and not force:
   r=c.execute("SELECT datetime(?)<=datetime('now','localtime',?)",(row['generated_at'],f'-{int(refresh_hours)} hours')).fetchone()
   stale=bool(r and r[0])
  if row and not stale and not force:
   return str(row['body'] or ''), str(row['generated_at'] or ''), False
  text=build_error_report_text(int(hours))
  gen=datetime_now()
  c.execute("INSERT INTO giso_system_reports(kind,body,generated_at,hours) VALUES('errors_text',?,?,?)",(text,gen,int(hours)))
  c.commit()
  return text, gen, True
