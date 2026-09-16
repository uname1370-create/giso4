# -*- coding: utf-8 -*-
"""قرارداد منوی تفکیک‌شده و امنیت مدیریت راه دور گیسو."""
from pathlib import Path
import ast

ROOT=Path(__file__).resolve().parents[2]


def test_site_management_is_split_without_removing_legacy_entry():
    ui=(ROOT/'bot_edu/ui.py').read_text(encoding='utf-8')
    handlers=(ROOT/'bot_edu/handlers.py').read_text(encoding='utf-8')
    for marker in ('مدیریت سایت اصلی','مدیریت سایت گیسو','web_main_manage_kb','web_giso_manage_kb'):
        assert marker in ui
    assert 'elif d == "a_web_manage"' in handlers
    assert 'elif d == "a_web_main_manage"' in handlers
    assert 'elif d == "a_web_giso_manage"' in handlers


def test_giso_reports_are_read_only_and_cleanup_is_two_step_primary_admin_only():
    source=(ROOT/'bot_edu/handlers.py').read_text(encoding='utf-8')
    ai=source[source.index('elif d == "site_giso_ai_report"'):source.index('elif d == "site_giso_health"')]
    assert 'edit_message_text(_giso_ai_report_text()' in ai
    assert 'set_giso_config' not in ai and 'DELETE ' not in ai and 'UPDATE ' not in ai
    cleanup=source[source.index('elif d == "site_giso_cleanup"'):source.index('elif d == "site_maint_menu"')]
    assert 'int(user.id) not in ADMIN_IDS' in cleanup
    assert 'site_giso_cleanup_confirm' in cleanup
    assert 'giso_cleanup_preview_at' in cleanup and '>300' in cleanup
    helper=source[source.index('def _safe_giso_cleanup_candidates'):source.index('def _site_backup_kb')]
    for forbidden in ('giso.db-wal','giso.db-shm','wallet_receipts','.env'):
        assert forbidden not in helper
    assert 'uploads"/"temp' in helper.replace(' ','') and 'is_symlink()' in helper


def test_maintenance_image_upload_has_file_guards_and_defaults_exist():
    source=(ROOT/'bot_edu/handlers.py').read_text(encoding='utf-8')
    assert '5*1024*1024' in source and '20_000_000' in source
    assert "int(user.id) not in ADMIN_IDS" in source
    assert (ROOT/'web/static/images/maintenance-default.svg').is_file()
    assert (ROOT/'giso/static/images/maintenance-default.svg').is_file()
    assert 'maintenance_custom.webp' in (ROOT/'web/templates/maintenance.html').read_text(encoding='utf-8')
    assert 'maintenance_custom.webp' in (ROOT/'giso/templates/maintenance.html').read_text(encoding='utf-8')


def test_giso_admin_can_reach_login_during_maintenance():
    source=(ROOT/'giso/app.py').read_text(encoding='utf-8')
    gate=source[source.index('def giso_maintenance_gate'):]
    # بعد از refactor سقف خط، hook گزارش روزانه به giso/site_jobs.py منتقل شد
    jobs=(ROOT/'giso/site_jobs.py').read_text(encoding='utf-8')
    assert 'def giso_daily_marketing_digest' in jobs
    for route in ('/login','/logout','/admin/verify'):
        assert route in gate


def test_giso_maintenance_serves_branded_page_but_keeps_login_open():
    import sys,os
    sys.path.insert(0,str(ROOT/'bot_edu'))
    from services.admin_service import set_maintenance_flag
    from giso.app import create_app
    app=create_app();set_maintenance_flag('giso',True)
    try:
        # پاک‌کردن کش خواندن فلگ برای شبیه‌سازی تغییر از ربات اصلی
        import giso.app as app_module
        app_module._BOT_FLAG_CACHE.clear()
        client=app.test_client()
        page=client.get('/')
        body=page.get_data(as_text=True)
        # قرارداد جدید صفحهٔ به‌روزرسانی (بازنویسی طبق دستورالعمل): نشانگر برند +
        # پیام اطمینان‌بخش + انیمیشن چرخان؛ تیتر قدیمی بازنشسته شده است.
        assert page.status_code==503
        assert 'گیسو کمی صبر می‌خواهد تا درخشان‌تر برگردد' in body
        assert 'سفارش‌ها، کیف پول و حساب شما سر جایشان می‌مانند' in body
        assert 'spinner' in body
        assert client.get('/login').status_code==200
    finally:
        set_maintenance_flag('giso',False)
        # کش ده‌ثانیه‌ای فلگ در giso.app بعد از restore ممکن است مقدار True را نگه دارد
        # و تست‌های بعدی را 503 کند؛ آن را هم پاک کن.
        app_module._BOT_FLAG_CACHE.clear()


def test_changed_python_files_parse():
    for relative in ('bot_edu/handlers.py','bot_edu/ui.py','giso/app.py'):
        ast.parse((ROOT/relative).read_text(encoding='utf-8'))
