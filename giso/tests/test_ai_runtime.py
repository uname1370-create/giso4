#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
تست مستقل لایهٔ giso.ai_runtime

۱) جدول‌های runtime ساخته می‌شوند
۲) get/set setting کار می‌کند
۳) get/set policy کار می‌کند
۴) daily limit فقط امروز را می‌شمارد
۵) record_usage درست ثبت می‌شود
۶) chat_with_managed_ai پیام‌های خاموش/دسترسی/سهمیه را درست برمی‌گرداند
۷) سوپرادمین همیشه نامحدود است
۸) مسیرهای هستهٔ آنالیز همچنان با mock کار می‌کنند و تحت تأثیر runtime نیستند
"""
import asyncio
import os
import sys
from datetime import datetime, timedelta
from unittest.mock import patch

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if BASE_DIR not in sys.path:
    sys.path.append(BASE_DIR)

import giso.ai_runtime as ai_runtime_module

from giso.base import get_giso_db_conn, _giso_init_db  # noqa: E402
from giso.ai_brain import add_ai_provider, delete_ai_provider, update_ai_provider_field, init_ai_tables  # noqa: E402
from giso.ai_runtime import (  # noqa: E402
    OFF_MESSAGE, NO_ACCESS_MESSAGE, LIMIT_MESSAGE, OUT_OF_SCOPE_MESSAGE,
    init_ai_runtime_tables, get_setting, set_setting,
    get_last_activity, get_last_welcome, touch_user_activity, mark_welcome_shown,
    get_welcome_inactive_hours, should_show_welcome, get_smart_welcome_context,
    get_active_provider, set_active_provider, get_failover_chain, set_failover_chain,
    is_widget_enabled, set_widget_enabled, get_widget_position, set_widget_position,
    get_widget_welcome_message, set_widget_welcome_message, get_widget_primary_color, set_widget_primary_color,
    get_role_policy, set_role_policy, get_context_scope,
    check_daily_limit, record_usage, chat_with_managed_ai, chat_with_failover,
    build_status_report, process_superadmin_request,
    execute_pending_action, cancel_pending_action, rollback_action_log,
    build_capability_guide, get_widget_config,
)
from giso.analysis import _call_text_ai_raw, validate_uploaded_image  # noqa: E402
from giso.models import migrate_giso_tables  # noqa: E402

TEST_PROVIDER = "runtime_test_ai"
TEST_PROVIDER_2 = "runtime_test_ai_2"


def _safe_delete(conn, table):
    try:
        conn.execute(f"DELETE FROM {table}")
    except Exception:
        pass


def _reset_runtime_tables():
    _giso_init_db()
    migrate_giso_tables()
    init_ai_tables()
    init_ai_runtime_tables()
    with get_giso_db_conn() as conn:
        # اتصال تازه و صرفاً برای پاک‌سازی: FK خاموش می‌شود تا DELETE والدها در
        # اجرای suite (وقتی جداول marketplace/beauty و ... رکورد دارند) بلاک نشود.
        try:
            conn.execute("PRAGMA foreign_keys=OFF")
        except Exception:
            pass
        for table in (
            "giso_ai_usage_stats", "giso_ai_permissions", "giso_ai_settings", "giso_user_activity",
            "giso_ai_pending_actions", "giso_ai_action_logs", "giso_ai_health",
            "consultant_requests", "giso_support_tickets", "hair_orders",
            "product_orders", "products", "analyses",
            "giso_users", "giso_web_auth",
        ):
            _safe_delete(conn, table)
        conn.commit()
    init_ai_runtime_tables()


def _setup_provider():
    init_ai_tables()
    add_ai_provider(
        name=TEST_PROVIDER,
        kind="openai",
        api_key="dummy-key",
        base_url="https://example.com/v1",
        api_root="",
        timeout=20,
        enabled=True,
        use_proxy=False,
        replace=True,
    )
    add_ai_provider(
        name=TEST_PROVIDER_2,
        kind="openai",
        api_key="dummy-key-2",
        base_url="https://example2.com/v1",
        api_root="",
        timeout=20,
        enabled=True,
        use_proxy=False,
        replace=True,
    )
    update_ai_provider_field(TEST_PROVIDER, "selected_model", "gpt-4o-mini")
    update_ai_provider_field(TEST_PROVIDER_2, "selected_model", "llama3-8b-8192")
    ok, _ = set_active_provider(TEST_PROVIDER)
    assert ok, "active provider should be set"


def _cleanup():
    try:
        _giso_init_db()
        migrate_giso_tables()
        init_ai_tables()
        init_ai_runtime_tables()
        with get_giso_db_conn() as conn:
            for table in (
                "giso_ai_usage_stats", "giso_ai_permissions", "giso_ai_settings", "giso_user_activity",
                "giso_ai_pending_actions", "giso_ai_action_logs",
                "giso_users", "giso_web_auth", "analyses", "product_orders", "products", "hair_orders",
                "giso_support_tickets", "consultant_requests",
            ):
                _safe_delete(conn, table)
            conn.commit()
    except Exception:
        pass
    try:
        delete_ai_provider(TEST_PROVIDER)
    except Exception:
        pass
    try:
        delete_ai_provider(TEST_PROVIDER_2)
    except Exception:
        pass
    try:
        ai_runtime_module._PROVIDER_FAIL_COOLDOWNS.clear()
    except Exception:
        pass


def test_init_ai_runtime_tables():
    _reset_runtime_tables()
    with get_giso_db_conn() as conn:
        tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
    assert "giso_ai_settings" in tables
    assert "giso_ai_permissions" in tables
    assert "giso_ai_usage_stats" in tables
    assert "giso_ai_pending_actions" in tables
    assert "giso_ai_action_logs" in tables
    print("PASS  init_ai_runtime_tables جدول‌ها را ساخت")


def test_activity_tracking_and_welcome_gap():
    _reset_runtime_tables()
    with get_giso_db_conn() as conn:
        tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
    assert "giso_user_activity" in tables
    now = int(datetime.now().timestamp())
    touch_user_activity(9001, ts=now - 8 * 3600)
    mark_welcome_shown(9001, ts=now - 7 * 3600)
    assert get_last_activity(9001) == now - 8 * 3600
    assert get_last_welcome(9001) == now - 7 * 3600
    assert should_show_welcome(9001) is True
    touch_user_activity(9001, ts=now - 60)
    assert should_show_welcome(9001) is False
    assert get_welcome_inactive_hours() == 6
    print("PASS  giso_user_activity + فاصله ۶ ساعته welcome درست کار می‌کند")


def test_settings_roundtrip():
    _reset_runtime_tables()
    assert set_setting("chat_display_name", "همراه گیسو") is True
    assert get_setting("chat_display_name") == "همراه گیسو"
    print("PASS  set_setting / get_setting کار می‌کند")


def test_widget_settings_roundtrip():
    _reset_runtime_tables()
    assert set_widget_enabled(False) is True
    ok, _ = set_widget_position('left-top')
    assert ok is True
    ok, _ = set_widget_welcome_message('سلام از ویجت')
    assert ok is True
    ok, _ = set_widget_primary_color('#112233')
    assert ok is True
    cfg = get_widget_config()
    assert cfg['enabled'] is False
    assert cfg['position'] == 'left-top'
    assert cfg['welcome_message'] == 'سلام از ویجت'
    assert cfg['primary_color'] == '#112233'
    print('PASS  تنظیمات Widget ذخیره و خوانده می‌شود')


def test_failover_chain_roundtrip():
    _reset_runtime_tables()
    _setup_provider()
    ok, _ = set_failover_chain([TEST_PROVIDER_2, TEST_PROVIDER])
    assert ok is True
    chain = get_failover_chain()
    assert chain[0] == TEST_PROVIDER_2
    assert TEST_PROVIDER in chain
    print('PASS  زنجیره failover ذخیره و خوانده می‌شود')


def test_failover_cooldown_skips_recently_failed_provider():
    _reset_runtime_tables()
    _setup_provider()
    ai_runtime_module._PROVIDER_FAIL_COOLDOWNS.clear()
    ok, _ = set_failover_chain([TEST_PROVIDER, TEST_PROVIDER_2])
    assert ok is True
    attempts = []

    async def _fake_ask_ai(provider_name, messages, model=None, temperature=0.7, max_tokens=1200, **kwargs):
        attempts.append(provider_name)
        if provider_name == TEST_PROVIDER:
            return {"ok": False, "provider": provider_name, "model": model or '', "error": "HTTP 500"}
        return {"ok": True, "provider": provider_name, "model": model or 'llama3-8b-8192', "text": "پاسخ پشتیبان", "raw": {"usage": {"total_tokens": 8}}}

    with patch("giso.ai_brain.ask_ai", side_effect=_fake_ask_ai):
        first = asyncio.run(chat_with_failover(
            [{"role": "user", "content": "سلام"}],
            preferred_provider=TEST_PROVIDER,
            role="user",
            max_tokens=80,
        ))
        assert first["ok"] is True
        assert attempts[:2] == [TEST_PROVIDER, TEST_PROVIDER_2]
        attempts.clear()
        second = asyncio.run(chat_with_failover(
            [{"role": "user", "content": "سلام دوباره"}],
            preferred_provider=TEST_PROVIDER,
            role="user",
            max_tokens=80,
        ))
    assert second["ok"] is True
    assert attempts == [TEST_PROVIDER_2]
    print('PASS  provider خراب برای مدت کوتاه از ابتدای زنجیره failover کنار گذاشته می‌شود')


def test_role_policy_roundtrip():
    _reset_runtime_tables()
    ok, _ = set_role_policy("user", access_level=1, sections=["consultant_chat", "analysis", "plan"], daily_limit=7)
    assert ok is True
    pol = get_role_policy("user")
    assert pol["access_level"] == 1
    assert "analysis" in pol["sections"]
    assert pol["daily_limit"] == 7
    scope = get_context_scope("user")
    assert scope["include_analysis"] is True
    assert scope["include_products"] is False
    print("PASS  set_role_policy / get_role_policy / get_context_scope درست کار می‌کنند")


def test_check_daily_limit_resets_on_new_day():
    _reset_runtime_tables()
    ok, _ = set_role_policy("user", access_level=2, sections=["consultant_chat", "analysis", "plan", "products", "orders"], daily_limit=1)
    assert ok is True
    yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d %H:%M:%S")
    with get_giso_db_conn() as conn:
        conn.execute(
            "INSERT INTO giso_ai_usage_stats (actor_key, user_role, channel, action, section, tokens_used, provider_name, model_name, question_text, created_at) VALUES (?,?,?,?,?,?,?,?,?,?)",
            ("actor-old", "user", "site", "chat", "consultant_chat", 12, TEST_PROVIDER, "gpt-4o-mini", "دیروز", yesterday),
        )
        conn.commit()
    res = check_daily_limit("actor-old", "user")
    assert res["allowed"] is True
    assert res["used"] == 0
    print("PASS  check_daily_limit فقط مصرف امروز را می‌شمارد")


def test_record_usage_and_report():
    _reset_runtime_tables()
    _setup_provider()
    record_usage("actor-1", "user", "site", "chat", 33, TEST_PROVIDER, "gpt-4o-mini", "سوال تستی")
    with get_giso_db_conn() as conn:
        row = conn.execute("SELECT actor_key, tokens_used, question_text FROM giso_ai_usage_stats WHERE actor_key='actor-1'").fetchone()
    assert row is not None
    assert row[1] == 33
    report = build_status_report()
    assert TEST_PROVIDER in report
    assert "سوال تستی" in report
    print("PASS  record_usage ثبت می‌شود و build_status_report داده را می‌بیند")


def test_smart_welcome_context_user_and_admin():
    _reset_runtime_tables()
    with get_giso_db_conn() as conn:
        conn.execute("INSERT INTO giso_users (bale_id, phone, first_name, username, is_admin, contact_shared, pending_request, created_at, last_active) VALUES (?,?,?,?,?,?,?,?,?)",
                     ("9101", "+989111111111", "مهسا", "", 0, 1, 0, "2026-08-01 10:00:00", "2026-08-01 10:00:00"))
        conn.execute("INSERT INTO giso_web_auth (phone, name, region, contact_time, password_hash, security_question, security_answer, created_at, last_login) VALUES (?,?,?,?,?,?,?,?,?)",
                     ("+989111111111", "مهسا", "تهران", "صبح", "hash", "q", "a", "2026-08-01 10:00:00", ""))
        conn.execute("INSERT INTO analyses (user_id, phone, type, photo_path, ai_report_json, plan_json, checklist_progress, created_at, updated_at) VALUES (?,?,?,?,?,?,?,?,?)",
                     (1, "+989111111111", "hair", "analysis/", '{"summary":"موخوره"}', '{"duration_weeks":4}', '{"1": true, "2": false}', datetime.now().strftime('%Y-%m-%d %H:%M:%S'), ""))
        conn.execute("INSERT INTO giso_users (bale_id, phone, first_name, username, is_admin, contact_shared, pending_request, created_at, last_active) VALUES (?,?,?,?,?,?,?,?,?)",
                     ("9102", "+989122222222", "ادمین", "", 1, 1, 0, "2026-08-01 10:00:00", "2026-08-01 10:00:00"))
        conn.execute("INSERT INTO consultant_requests (user_id, phone, city, customer_name, analysis_id, initial_message, status, admin_id, created_at, updated_at) VALUES (?,?,?,?,?,?,?,?,?,?)",
                     (1, "+989111111111", "تهران", "مهسا", 1, "سلام", "new", 0, datetime.now().strftime('%Y-%m-%d %H:%M:%S'), datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
        conn.commit()
    user_ctx = get_smart_welcome_context(9101, "user")
    admin_ctx = get_smart_welcome_context(9102, "admin")
    assert user_ctx["scenario"] in ("recent_analysis", "returning_user")
    assert "مهسا" in user_ctx["text"]
    assert admin_ctx["scenario"] == "admin"
    assert "وضعیت کاری" in admin_ctx["text"]
    print("PASS  get_smart_welcome_context برای کاربر و ادمین سناریو مناسب می‌سازد")


def test_superadmin_action_reports_and_confirm_flow():
    _reset_runtime_tables()
    with get_giso_db_conn() as conn:
        conn.execute("INSERT INTO products (id, name, description, price, image_path, in_stock, category) VALUES (1, 'شامپو تست', '', 100000, '', 1, 'hair')")
        conn.execute("INSERT INTO product_orders (id, user_id, phone, customer_name, product_id, address, status, created_at) VALUES (1, 0, '+989111111111', 'مینا', 1, 'تهران', 'pending', ?)",
                     (datetime.now().strftime('%Y-%m-%d %H:%M:%S'),))
        conn.commit()
    rep = process_superadmin_request(1191639507, '+989156012931', 'گزارش سفارش‌ها را بده')
    assert rep['handled'] is True and rep['mode'] == 'report'
    assert 'سفارش' in rep['text']

    pending = process_superadmin_request(1191639507, '+989156012931', 'وضعیت سفارش 1 را به پردازش تغییر بده')
    assert pending['handled'] is True and pending['mode'] == 'pending'
    pending_id = pending['pending_id']
    res = execute_pending_action(pending_id, 1191639507)
    assert res['ok'] is True
    with get_giso_db_conn() as conn:
        st = conn.execute("SELECT status FROM product_orders WHERE id=1").fetchone()[0]
        log = conn.execute("SELECT id FROM giso_ai_action_logs ORDER BY id DESC LIMIT 1").fetchone()[0]
    assert st == 'processing'
    undo = rollback_action_log(log, 1191639507)
    assert undo['ok'] is True
    with get_giso_db_conn() as conn:
        st2 = conn.execute("SELECT status FROM product_orders WHERE id=1").fetchone()[0]
    assert st2 == 'pending'
    print('PASS  گزارش، تأیید دو مرحله‌ای، اجرا و rollback برای سوپرادمین کار می‌کند')


def test_pending_action_expiry_blocks_late_execution():
    _reset_runtime_tables()
    with get_giso_db_conn() as conn:
        conn.execute("INSERT INTO products (id, name, description, price, image_path, in_stock, category) VALUES (1, 'شامپو تست', '', 100000, '', 1, 'hair')")
        conn.execute("INSERT INTO product_orders (id, user_id, phone, customer_name, product_id, address, status, created_at) VALUES (1, 0, '+989111111111', 'مینا', 1, 'تهران', 'pending', ?)",
                     (datetime.now().strftime('%Y-%m-%d %H:%M:%S'),))
        conn.commit()
    pending = process_superadmin_request(1191639507, '+989156012931', 'وضعیت سفارش 1 را به پردازش تغییر بده')
    assert pending['handled'] is True and pending['mode'] == 'pending'
    pending_id = int(pending['pending_id'])
    with get_giso_db_conn() as conn:
        conn.execute("UPDATE giso_ai_pending_actions SET expires_at=? WHERE id=?", ('2000-01-01 00:00:00', pending_id))
        conn.commit()
    res = execute_pending_action(pending_id, 1191639507)
    assert res['ok'] is False
    assert 'منقضی' in res['text']
    with get_giso_db_conn() as conn:
        status = conn.execute("SELECT status FROM giso_ai_pending_actions WHERE id=?", (pending_id,)).fetchone()[0]
        order_status = conn.execute("SELECT status FROM product_orders WHERE id=1").fetchone()[0]
    assert status == 'expired'
    assert order_status == 'pending'
    print('PASS  اقدام منقضی‌شده دیگر اجرا نمی‌شود')


def test_superadmin_action_scope_guards():
    _reset_runtime_tables()
    out = process_superadmin_request(1191639507, '+989156012931', 'طرز تهیه کباب را بگو')
    assert out['handled'] is False
    bad = process_superadmin_request(1191639507, '+989156012931', 'کاربر را بلاک کن')
    assert bad['handled'] is True and 'فیلد مسدودسازی' in bad['text']
    print('PASS  سوپرادمین برای متن‌های آزاد به چت برمی‌گردد و برای بلاک توضیح دقیق می‌گیرد')


def test_superadmin_smalltalk_falls_back_to_chat():
    _reset_runtime_tables()
    hello = process_superadmin_request(1191639507, '+989156012931', 'سلام')
    strategy = process_superadmin_request(1191639507, '+989156012931', 'به نظرت اولویت رسیدگی امروز چی باشه؟')
    why_limit = process_superadmin_request(1191639507, '+989156012931', 'چرا محدودیت داری')
    assert hello['handled'] is False
    assert strategy['handled'] is False
    assert why_limit['handled'] is False
    print('PASS  سلام و گفتگوی مدیریتی عمومی برای سوپرادمین به چت عادی برمی‌گردد')


def test_capability_guides_by_role():
    _reset_runtime_tables()
    super_guide = build_capability_guide('super')
    admin_guide = build_capability_guide('admin')
    user_guide = build_capability_guide('user')
    assert 'تأیید دو مرحله‌ای' in super_guide
    assert 'حذف اطلاعات کاربر' in super_guide
    assert 'هیچ تغییری روی داده‌ها انجام نمی‌دم' in admin_guide
    assert 'همراه مهربون' in user_guide
    print('PASS  راهنمای قابلیت‌ها برای user/admin/super متناسب با سطح ساخته می‌شود')


def test_user_service_snapshot_ignores_completed_hair_orders():
    _reset_runtime_tables()
    with get_giso_db_conn() as conn:
        conn.execute("INSERT INTO giso_web_auth (id, phone, name, region, contact_time, password_hash, security_question, security_answer, created_at, last_login) VALUES (1, '+989111111111', 'مینا', '', '', 'h', '', '', '2026-08-01 10:00:00', '')")
        conn.execute("INSERT INTO hair_orders (id, user_id, phone, customer_name, photo_path, length_cm, status, created_at, updated_at) VALUES (1, 1, '+989111111111', 'مینا', 'hair/test.jpg', 55, 'completed', '2026-08-01 10:00:00', '2026-08-01 12:00:00')")
        conn.commit()
    snap = ai_runtime_module._user_service_snapshot(phone='+989111111111', site_user_id=1)
    assert snap['has_active_hair_order'] is False
    assert snap['latest_hair_status'] == ''
    with get_giso_db_conn() as conn:
        conn.execute("INSERT INTO hair_orders (id, user_id, phone, customer_name, photo_path, length_cm, status, created_at, updated_at) VALUES (2, 1, '+989111111111', 'مینا', 'hair/test2.jpg', 60, 'reviewing', '2026-08-02 10:00:00', '2026-08-02 12:00:00')")
        conn.commit()
    snap2 = ai_runtime_module._user_service_snapshot(phone='+989111111111', site_user_id=1)
    assert snap2['has_active_hair_order'] is True
    assert 'در حال بررسی' in snap2['latest_hair_status']
    print('PASS  snapshot کاربر سفارش فروش موی تکمیل‌شده را active حساب نمی‌کند')


def test_superadmin_ai_setting_actions_and_user_delete():
    _reset_runtime_tables()
    _setup_provider()
    with get_giso_db_conn() as conn:
        conn.execute("INSERT INTO giso_web_auth (id, phone, name, region, contact_time, password_hash, security_question, security_answer, created_at, last_login) VALUES (1, '+989111111111', 'مینا', '', '', 'h', '', '', '2026-08-01 10:00:00', '')")
        conn.execute("INSERT INTO giso_users (bale_id, phone, first_name, username, is_admin, contact_shared, pending_request, created_at, last_active) VALUES ('5001', '+989111111111', 'مینا', '', 0, 1, 0, '2026-08-01 10:00:00', '2026-08-01 10:00:00')")
        conn.commit()

    p1 = process_superadmin_request(1191639507, '+989156012931', 'هوش مصنوعی را خاموش کن')
    assert p1['handled'] is True and p1['mode'] == 'pending'
    r1 = execute_pending_action(p1['pending_id'], 1191639507)
    assert r1['ok'] is True
    assert get_setting('chat_enabled') == '0'

    p2 = process_superadmin_request(1191639507, '+989156012931', 'اسم مشاور را به گیسو یار تغییر بده')
    assert p2['handled'] is True and p2['mode'] == 'pending'
    r2 = execute_pending_action(p2['pending_id'], 1191639507)
    assert r2['ok'] is True
    assert get_setting('chat_display_name') == 'گیسو یار'

    p3 = process_superadmin_request(1191639507, '+989156012931', 'AI فعال را روی groq بگذار')
    assert p3['handled'] is True and p3['mode'] == 'pending'
    r3 = execute_pending_action(p3['pending_id'], 1191639507)
    assert r3['ok'] is True
    assert get_setting('chat_active_provider') == 'groq'

    p4 = process_superadmin_request(1191639507, '+989156012931', 'حذف کاربر 09111111111')
    assert p4['handled'] is True and p4['mode'] == 'pending'
    r4 = execute_pending_action(p4['pending_id'], 1191639507)
    assert r4['ok'] is True
    with get_giso_db_conn() as conn:
        row = conn.execute("SELECT COUNT(*) FROM giso_web_auth WHERE phone='+989111111111'").fetchone()[0]
    assert row == 0
    undo = rollback_action_log(r4['log_id'], 1191639507)
    assert undo['ok'] is True
    with get_giso_db_conn() as conn:
        row2 = conn.execute("SELECT COUNT(*) FROM giso_web_auth WHERE phone='+989111111111'").fetchone()[0]
    assert row2 == 1
    print('PASS  اکشن‌های AI setting و حذف کاربر برای سوپرادمین با تأیید و rollback کار می‌کنند')


async def _run_chat_success():
    async def _fake_ask_ai(*args, **kwargs):
        return {
            "ok": True,
            "provider": TEST_PROVIDER,
            "model": "gpt-4o-mini",
            "text": "سلام! این پاسخ تستی است.",
            "raw": {"usage": {"total_tokens": 42}},
        }

    with patch("giso.ai_brain.ask_ai", side_effect=_fake_ask_ai):
        return await chat_with_managed_ai(
            [{"role": "user", "content": "سلام"}],
            actor_key="actor-success",
            role="user",
            channel="site",
            section="consultant_chat",
            question_text="سلام",
            max_tokens=200,
        )


async def _run_failover_chat():
    attempts = []

    async def _fake_ask_ai(provider_name, messages, model=None, temperature=0.7, max_tokens=1200, **kwargs):
        attempts.append(provider_name)
        if provider_name == TEST_PROVIDER:
            return {"ok": False, "provider": provider_name, "model": model or '', "error": "HTTP 500"}
        return {"ok": True, "provider": provider_name, "model": model or 'llama3-8b-8192', "text": "پاسخ از پشتیبان", "raw": {"usage": {"total_tokens": 11}}}

    with patch("giso.ai_brain.ask_ai", side_effect=_fake_ask_ai):
        res = await chat_with_failover(
            [{"role": "user", "content": "سلام"}],
            preferred_provider=TEST_PROVIDER,
            role="user",
            max_tokens=100,
        )
    return res, attempts


def test_chat_with_failover_uses_backup():
    _reset_runtime_tables()
    _setup_provider()
    ok, _ = set_failover_chain([TEST_PROVIDER, TEST_PROVIDER_2])
    assert ok is True
    res, attempts = asyncio.run(_run_failover_chat())
    assert res['ok'] is True
    assert res['provider'] == TEST_PROVIDER_2
    assert attempts[:2] == [TEST_PROVIDER, TEST_PROVIDER_2]
    print('PASS  chat_with_failover بعد از خطای AI اصلی از پشتیبان استفاده می‌کند')


def test_chat_with_managed_ai_disabled():
    _reset_runtime_tables()
    _setup_provider()
    set_setting("chat_enabled", "0")
    res = asyncio.run(chat_with_managed_ai(
        [{"role": "user", "content": "سلام"}],
        actor_key="actor-disabled",
        role="user",
        channel="site",
        section="consultant_chat",
        question_text="سلام",
    ))
    assert res["ok"] is False
    assert res["text"] == OFF_MESSAGE
    print("PASS  chat_with_managed_ai در حالت خاموش پیام مناسب می‌دهد")


def test_chat_with_managed_ai_access_denied():
    _reset_runtime_tables()
    _setup_provider()
    ok, _ = set_role_policy("user", access_level=0, sections=["consultant_chat"], daily_limit=10)
    assert ok is True
    res = asyncio.run(chat_with_managed_ai(
        [{"role": "user", "content": "سلام"}],
        actor_key="actor-no-access",
        role="user",
        channel="site",
        section="consultant_chat",
        question_text="سلام",
    ))
    assert res["ok"] is False
    assert res["text"] == NO_ACCESS_MESSAGE
    print("PASS  chat_with_managed_ai در سطح ۰ پیام دسترسی می‌دهد")


def test_chat_with_managed_ai_daily_limit():
    _reset_runtime_tables()
    _setup_provider()
    ok, _ = set_role_policy("user", access_level=2, sections=["consultant_chat", "analysis", "plan", "products", "orders"], daily_limit=1)
    assert ok is True
    record_usage("actor-limit", "user", "site", "chat", 10, TEST_PROVIDER, "gpt-4o-mini", "سلام")
    res = asyncio.run(chat_with_managed_ai(
        [{"role": "user", "content": "سلام دوباره"}],
        actor_key="actor-limit",
        role="user",
        channel="site",
        section="consultant_chat",
        question_text="سلام دوباره",
    ))
    assert res["ok"] is False
    assert res["text"] == LIMIT_MESSAGE
    print("PASS  chat_with_managed_ai در سقف روزانه پیام مناسب می‌دهد")


def test_chat_with_managed_ai_success():
    _reset_runtime_tables()
    _setup_provider()
    set_setting("chat_enabled", "1")
    ok, _ = set_role_policy("user", access_level=2, sections=["consultant_chat", "analysis", "plan", "products", "orders"], daily_limit=10)
    assert ok is True
    res = asyncio.run(_run_chat_success())
    assert res["ok"] is True
    assert "پاسخ تستی" in res["text"]
    with get_giso_db_conn() as conn:
        row = conn.execute("SELECT tokens_used FROM giso_ai_usage_stats WHERE actor_key='actor-success' ORDER BY id DESC LIMIT 1").fetchone()
    assert row is not None and row[0] == 42
    print("PASS  chat_with_managed_ai در حالت سالم پاسخ AI را برمی‌گرداند")


def test_superadmin_always_unlimited():
    _reset_runtime_tables()
    _setup_provider()
    for _ in range(5):
        record_usage("actor-super", "super", "admin_test", "chat", 11, TEST_PROVIDER, "gpt-4o-mini", "گزارش")
    res = check_daily_limit("actor-super", "super")
    assert res["allowed"] is True
    assert res["limit"] == 0
    pol = get_role_policy("super")
    assert pol["access_level"] == 3
    print("PASS  سوپرادمین همیشه نامحدود و سطح ۳ است")


def test_analysis_core_paths_unaffected_with_mock():
    async def _fake_fast(*args, **kwargs):
        return {"ok": True, "text": "سلام تست"}

    with patch("giso.analysis.ask_ai_fast", side_effect=_fake_fast):
        raw = _call_text_ai_raw("سلام", max_tokens=50)
    assert raw["ok"] is True
    assert "سلام تست" in raw["text"]

    with patch("giso.analysis.call_vision_with_fallback", return_value={"ok": True, "data": {"valid": True, "message": "ok"}}):
        res_hair = validate_uploaded_image("dummy.jpg", "hair")
        res_skin = validate_uploaded_image("dummy.jpg", "skin")
    assert res_hair["valid"] is True
    assert res_skin["valid"] is True
    print("PASS  مسیرهای هسته آنالیز (متنی/vision) تحت تأثیر runtime نیستند")


def test_super_capabilities_upgraded_with_migration():
    """مرحله ۴: پرامپت سوپرادمین تقویت شده و سرورهای دست‌نخورده مهاجرت می‌کنند."""
    from giso.ai_runtime_policy import DEFAULT_SUPER_CAPABILITIES, LEGACY_SUPER_CAPABILITIES
    from giso.ai_runtime import get_role_capabilities, set_setting, init_ai_runtime_tables
    assert "ساختگی" in DEFAULT_SUPER_CAPABILITIES, "پرامپت جدید باید جواب ساختگی را ممنوع کند"
    assert "دادهٔ زنده" in DEFAULT_SUPER_CAPABILITIES, "پرامپت جدید باید مبتنی بر دادهٔ زنده باشد"
    assert DEFAULT_SUPER_CAPABILITIES != LEGACY_SUPER_CAPABILITIES
    set_setting("chat_capabilities_super", LEGACY_SUPER_CAPABILITIES)
    init_ai_runtime_tables()
    assert get_role_capabilities("super").strip() == DEFAULT_SUPER_CAPABILITIES.strip(), "مهاجرت متن قدیمی انجام نشد"
    print("PASS  پرامپت سوپرادمین تقویت شد + مهاجرت DB کار می‌کند")


def test_superadmin_open_tickets_and_pending_consults_filter():
    _reset_runtime_tables()
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with get_giso_db_conn() as conn:
        conn.execute(
            "INSERT INTO giso_support_tickets (id, user_bale_id, user_name, phone, message, status, created_at) "
            "VALUES (1, 'u1', 'باز', '+989111111111', 'm', 'new', ?)",
            (now,),
        )
        conn.execute(
            "INSERT INTO giso_support_tickets (id, user_bale_id, user_name, phone, message, status, created_at) "
            "VALUES (2, 'u2', 'بسته', '+989122222222', 'm', 'closed', ?)",
            (now,),
        )
        conn.execute(
            "INSERT INTO consultant_requests (id, user_id, phone, city, customer_name, analysis_id, initial_message, status, admin_id, created_at, updated_at) "
            "VALUES (1, 0, '+989111111111', 'تهران', 'معطل', 0, 'سلام', 'pending', 0, ?, ?)",
            (now, now),
        )
        conn.execute(
            "INSERT INTO consultant_requests (id, user_id, phone, city, customer_name, analysis_id, initial_message, status, admin_id, created_at, updated_at) "
            "VALUES (2, 0, '+989122222222', 'تهران', 'بسته', 0, 'سلام', 'closed', 0, ?, ?)",
            (now, now),
        )
        conn.commit()
    tickets = process_superadmin_request(1191639507, "+989156012931", "تیکت‌های باز رو لیست کن")
    assert tickets["handled"] is True and tickets["mode"] == "report"
    assert "تیکت‌های باز" in tickets["text"]
    assert "بسته" not in tickets["text"]
    consults = process_superadmin_request(1191639507, "+989156012931", "درخواست‌های مشاوره معطل رو لیست کن")
    assert consults["handled"] is True and consults["mode"] == "report"
    assert "معطل" in consults["text"]
    assert "بسته" not in consults["text"]
    print("PASS  چیپ تیکت باز و مشاوره معطل فقط وضعیت درست را می‌آورد")


def test_force_refresh_and_generation_params_and_sanitize():
    from giso.ai_runtime_policy import detect_force_refresh
    from giso.ai_runtime import super_chat_generation_params, _sanitize_ai_reply
    assert detect_force_refresh("گزارش امروز رو همین الان بده") is True
    assert detect_force_refresh("کش رو نادیده بگیر") is True
    assert detect_force_refresh("سلام الان چطوری") is False
    t, tok = super_chat_generation_params("کوتاه؟")
    assert t == 0.2 and tok == 280
    t2, tok2 = super_chat_generation_params("س" * 200, requested_max_tokens=800)
    assert t2 == 0.2 and tok2 == 800
    fake = _sanitize_ai_reply("اقدام اجرا شد و همه کاربران ۱۰۰٪ راضی‌اند", role="super")
    assert "ادعای اجرای اقدام" in fake
    assert "عدد/آمار" in fake
    seo = process_superadmin_request(1191639507, "+989156012931", "وضعیت سئو و sitemap چیست؟")
    assert seo["handled"] is True and "sitemap" in seo["text"].lower()
    print("PASS  force_refresh + temp/tokens + sanitize + seo feasibility")


def _run():
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    passed = 0
    for t in tests:
        try:
            _cleanup()
            t()
            passed += 1
        except AssertionError as e:
            print(f"FAIL  {t.__name__}: {e}")
        except Exception as e:  # noqa: BLE001
            print(f"ERROR {t.__name__}: {type(e).__name__}: {e}")
        finally:
            _cleanup()
    print(f"\n{passed}/{len(tests)} passed")
    return passed == len(tests)


if __name__ == "__main__":
    sys.exit(0 if _run() else 1)
