from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
def test_overview_and_ai_contracts():
 s=(ROOT/'giso/monitoring_ai.py').read_text();h=(ROOT/'giso/panel/templates/modules/monitoring.html').read_text();b=(ROOT/'giso/bot.py').read_text();e=(ROOT/'giso/monitoring_errors.py').read_text();r=(ROOT/'giso/panel/routes.py').read_text()
 for x in ('open_errors','suspicious_24h','events_24h','campaigns_sending','ai_providers_ok'):assert x in s
 # پایش مرحلهٔ جدید: بازهٔ N ساعتهٔ تنظیم‌شده (get_ai_interval_hours) به‌جای ۲۴ ساعت ثابت.
 assert 'get_ai_interval_hours' in s and "-5 minutes" in s and 'int(busy or 0)<50' in s
 assert 'هیچ اقدام' in s and '_init_monitoring_ai(app)' in b
 assert 'build_error_report_text' in e and '/monitoring/errors-report.txt' in r
 assert 'monitoring_ai_hour' in h and 'اجرای دستی گزارش' in h
 assert 'گزارش‌های دستی' in h
if __name__=='__main__':test_overview_and_ai_contracts()
