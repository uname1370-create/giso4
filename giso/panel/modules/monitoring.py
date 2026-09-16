# -*- coding: utf-8 -*-
"""Superadmin monitoring context; expensive tabs load only their own data.

نمایش فارسی: نام صفحات رفتار کاربران و خلاصه‌ی خطاها به متن کوتاه فارسی تبدیل
می‌شوند (giso.monitoring_fa) تا گزارش دقیق، کوتاه و قابل‌فهم باشد؛ داده‌ی خام فنی
نیز به‌صورت محدود برای ارجاع باقی می‌ماند.
"""
from flask import request,session
TABS=("overview","errors","behavior","security","broadcasts","ai_reports","settings")
def context():
 tab=(request.args.get("tab") or "overview").strip().lower()
 if tab not in TABS:tab="overview"
 from giso.monitoring_settings import get_settings,get_ai_hour,get_ai_interval_hours,get_report_refresh_hours
 settings=get_settings()
 out={"monitoring_tab":tab,"monitoring_tabs":TABS,"monitoring_settings":settings,"monitoring_ai_hour":get_ai_hour(),"monitoring_interval_hours":get_ai_interval_hours(),"monitoring_report_refresh_hours":get_report_refresh_hours(),"monitoring_errors":[],"monitoring_manual_reports":[],"monitoring_bug_reports":[],"monitoring_logins":[],"monitoring_behavior":{"totals":[],"pages":[],"forms":[]},"monitoring_campaigns":[],"broadcast_preview":session.get('broadcast_preview'),"monitoring_overview":{},"monitoring_ai_reports":[],"monitoring_text_report_gen":""}
 # کلید اصلی فقط جمع‌آوری/پردازش را متوقف می‌کند؛ تنظیمات همیشه در دسترس است.
 if not settings.get('master',True) and tab!='settings':return out
 try:
  if tab=='errors':
   from giso.monitoring_errors import list_errors
   from giso.bug_reports import list_reports
   from giso.monitoring_fa import error_label, severity_label, page_label
   errs=[]
   for e in list_errors():
    e=dict(e)
    e['summary_fa']=error_label(e.get('summary',''), e.get('service',''), e.get('section',''))
    e['severity_fa']=severity_label(e.get('severity',''))
    e['section_fa']=page_label(e.get('section',''))
    errs.append(e)
   out['monitoring_errors']=errs
   out['monitoring_bug_reports']=list_reports()
   try:
    from giso.monitoring_errors import list_manual_reports, get_or_refresh_text_report
    out['monitoring_manual_reports']=list_manual_reports()
    _txt, gen, _ref = get_or_refresh_text_report(force=False, hours=24)
    out['monitoring_text_report_gen']=gen
   except Exception:
    out['monitoring_manual_reports']=[]
  elif tab=='security':
   from giso.login_history import recent
   out['monitoring_logins']=recent()
  elif tab=='behavior':
   from giso.monitoring_events import report
   from giso.monitoring_fa import page_label
   beh=report()
   beh['pages']=[dict(x, page_label=page_label(x.get('page_path',''))) for x in beh.get('pages',[])]
   beh['forms']=[dict(x, page_label=page_label(x.get('page_path',''))) for x in beh.get('forms',[])]
   out['monitoring_behavior']=beh
  elif tab=='broadcasts':
   from giso.broadcasts import campaign_list
   out['monitoring_campaigns']=campaign_list()
  elif tab in ('overview','ai_reports'):
   from giso.monitoring_ai import aggregate,list_reports
   if tab=='overview':out['monitoring_overview']=aggregate()
   else:out['monitoring_ai_reports']=list_reports()
 except Exception:pass
 return out
