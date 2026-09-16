#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
تست گروه B - چت مشاور + پشتیبانی + تعاملی پنل ادمین + رفع باگ بازگشت

۱) _get_user_full_context اطلاعات واقعی کاربر (تحلیل/برنامه/چک‌لیست/سفارش‌ها) را می‌سازد
۲) _ask_consultant_bot با AI پاسخ می‌دهد (mock شده)
۳) جریان چت مشاور در ربات (analysis_consultant → پیام → ذخیره تاریخچه)
۴) سیستم پشتیبانی: ثبت تیکت + اطلاع به ادمین + لیست تیکت‌های من
۵) پاسخ ادمین به تیکت (replying_ticket) → آپدیت + ارسال به کاربر
۶) پاسخ ادمین به درخواست مشاوره (replying_consultant) → ثبت پیام + آپدیت وضعیت
۷) مدیریت محصول درخواستی (prod_view_ + prod_add_ + prod_reject_)
"""
import asyncio
import json
import os
import sys
from unittest.mock import MagicMock, AsyncMock, patch

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if BASE_DIR not in sys.path:
    sys.path.append(BASE_DIR)

import giso.bot as bot_mod  # noqa: E402
from giso import bot_admin_utils  # noqa: E402
from giso.app import create_app  # noqa: E402
from giso.models import db, User, Analysis  # noqa: E402
from giso.base import normalize_phone, get_giso_db_conn, _upsert_giso_user  # noqa: E402
from giso.ai_runtime import set_setting, touch_user_activity, mark_welcome_shown  # noqa: E402
from giso.bot import (
    CONSULTANT_AI_LABEL,
    _get_user_full_context, _ask_consultant_bot, _save_bot_chat_message,
    _get_bot_chat_history, _create_support_ticket, _get_bale_id_by_phone,
    get_test_handlers, _admin_kb, _user_kb,
)  # noqa: E402

USER_PHONE = "09190001111"
ADMIN_BID = 777011
USER_BID = 777012
SUPPORT_USER_BID = 777013
RESTRICTED_AI_ADMIN_BID = 777014
RESTRICTED_AI_ADMIN_PHONE = normalize_phone("09120000012")
SUPER_BID = 1191639507


def _setup_db():
    app = create_app()
    with app.app_context():
        user = User.query.filter_by(phone=normalize_phone(USER_PHONE)).first()
        if not user:
            user = User(phone=normalize_phone(USER_PHONE),
                        password_hash="pbkdf2:sha256:260000$test$hash",
                        name="نگار", city="تهران")
            db.session.add(user)
            db.session.commit()
        for a in Analysis.query.filter_by(user_id=user.id).all():
            db.session.delete(a)
        db.session.commit()

        plan = {
            "duration_weeks": 4,
            "checklist": {
                "weeks": [
                    {"week_number": 1, "items": ["ماسک آبرسان", "کرم مراقبت"]},
                    {"week_number": 2, "items": ["شامپو ملایم"]},
                ]
            },
        }
        a = Analysis(phone=normalize_phone(USER_PHONE), user_id=user.id, type="hair",
                     photo_path="analysis/",
                     ai_report_json=json.dumps({"overall_score": 78, "summary": "خوب"}),
                     plan_json=json.dumps(plan),
                     checklist_progress=json.dumps({"w1-0": True, "w1-1": False}),
                     consultant_key_notes="خلاصه گفتگو قبلی")
        db.session.add(a)
        db.session.commit()
        aid = a.id

        _upsert_giso_user(ADMIN_BID, phone=normalize_phone("09120000002"),
                          first_name="ادمین", contact_shared=True,
                          is_admin=True, pending_request=False)
        _upsert_giso_user(USER_BID, phone=normalize_phone(USER_PHONE),
                          first_name="نگار", contact_shared=True,
                          is_admin=False, pending_request=False)
        _upsert_giso_user(SUPPORT_USER_BID, phone=normalize_phone("09130000003"),
                          first_name="کیان", contact_shared=True,
                          is_admin=False, pending_request=False)
        _upsert_giso_user(SUPER_BID, phone=normalize_phone("09156012931"),
                          first_name="سوپر", contact_shared=True,
                          is_admin=True, pending_request=False)

        # درخواست مشاوره + درخواست محصول
        with get_giso_db_conn() as conn:
            conn.execute(
                "INSERT INTO consultant_requests (user_id, phone, city, customer_name, analysis_id, "
                "initial_message, status, created_at, updated_at) "
                "VALUES (?,?,?,?,?,?, 'new', ?, ?)",
                (user.id, normalize_phone(USER_PHONE), "تهران", "نگار", aid, "سلام",
                 "2026-08-05 05:00:00", "2026-08-05 05:00:00"))
            conn.execute(
                "INSERT INTO product_requests (user_id, phone, city, analysis_id, "
                "problem_summary, status, created_at) "
                "VALUES (?,?,?,?,?, 'pending', ?)",
                (user.id, normalize_phone(USER_PHONE), "تهران", aid, "موی خشک",
                 "2026-08-05 05:00:00"))
            conn.commit()
    return app, aid


def _cleanup(app):
    try:
        with app.app_context():
            for u in User.query.filter_by(phone=normalize_phone(USER_PHONE)).all():
                for a in Analysis.query.filter_by(phone=u.phone).all():
                    db.session.delete(a)
                db.session.delete(u)
            db.session.commit()
    except Exception:
        pass
    try:
        with get_giso_db_conn() as conn:
            for bid in (ADMIN_BID, USER_BID, SUPPORT_USER_BID, RESTRICTED_AI_ADMIN_BID, SUPER_BID):
                conn.execute("DELETE FROM giso_users WHERE bale_id=?", (str(bid),))
                conn.execute("DELETE FROM giso_admin_permissions WHERE admin_bale_id=?", (str(bid),))
            conn.execute("DELETE FROM giso_support_tickets")
            conn.execute("DELETE FROM giso_bot_consultant_chat")
            conn.execute("DELETE FROM consultant_messages")
            conn.execute("DELETE FROM consultant_requests")
            conn.execute("DELETE FROM product_requests")
            conn.execute("DELETE FROM giso_user_activity")
            conn.execute("DELETE FROM giso_ai_usage_stats")
            conn.execute("DELETE FROM giso_ai_permissions")
            conn.execute("DELETE FROM giso_ai_settings")
            conn.commit()
    except Exception:
        pass
    try:
        import sqlite3
        conn = sqlite3.connect(str(bot_mod.BOT_DB))
        conn.execute("DELETE FROM giso_admins WHERE bale_id=? OR phone=?", (str(RESTRICTED_AI_ADMIN_BID), RESTRICTED_AI_ADMIN_PHONE))
        conn.commit()
        conn.close()
    except Exception:
        pass


# ── ۱) context کامل کاربر ───────────────────────────────────
def test_user_full_context():
    app, aid = _setup_db()
    try:
        ctx = _get_user_full_context(normalize_phone(USER_PHONE), USER_BID)
        assert ctx['user_name'] == 'نگار'
        assert ctx['user_city'] == 'تهران'
        assert 'تحلیل مو' in ctx['last_analysis_info']
        assert 'امتیاز: 78' in ctx['last_analysis_info']
        assert 'برنامه 4 هفته‌ای' in ctx['active_plan_info']
        assert ctx['checklist_info'].startswith('1 از 2')
        assert ctx['product_requests_info'].startswith('1 درخواست')
        assert 'خلاصه گفتگو قبلی' in ctx['key_notes']
        print("PASS  _get_user_full_context اطلاعات واقعی کاربر را می‌سازد")
    finally:
        _cleanup(app)


# ── ۲) _ask_consultant_bot ──────────────────────────────────
def test_ask_consultant_bot():
    app, aid = _setup_db()
    try:
        async def run():
            with patch.object(bot_admin_utils, 'chat_with_managed_ai', new=AsyncMock(return_value={
                "ok": True, "text": "سلام نگار عزیز! برنامه شما عالیه.",
                "provider": "llm7", "model": "gpt-4o-mini"
            })):
                reply = await _ask_consultant_bot(USER_BID, normalize_phone(USER_PHONE),
                                                  "چطوری از موهام مراقبت کنم؟")
            return reply
        reply = asyncio.run(run())
        assert "سلام نگار عزیز" in reply
        print("PASS  _ask_consultant_bot پاسخ هوشمند مشاور را می‌دهد")
    finally:
        _cleanup(app)


def test_ask_consultant_bot_super_role():
    app, aid = _setup_db()
    try:
        captured = {}

        async def fake_chat(messages, **kwargs):
            captured['messages'] = messages
            captured['kwargs'] = kwargs
            return {"ok": True, "text": "گزارش مدیریتی آماده است.", "provider": "llm7", "model": "gpt-4o-mini"}

        async def run():
            with patch.object(bot_admin_utils, 'chat_with_managed_ai', side_effect=fake_chat):
                reply = await _ask_consultant_bot(SUPER_BID, normalize_phone("09156012931"),
                                                  "گزارش امروز رو بده", role="super")
            return reply

        reply = asyncio.run(run())
        assert "گزارش مدیریتی" in reply
        assert captured['kwargs']['role'] == 'super'
        prompt_text = captured['messages'][0]['content']
        assert "سوپرادمین" in prompt_text
        assert "خلاصه وضعیت امروز" in prompt_text
        assert "هنوز تحلیلی انجام نداده" not in prompt_text
        print("PASS  _ask_consultant_bot برای سوپرادمین نقش و context مدیریتی می‌سازد")
    finally:
        _cleanup(app)


# ── ۳) ذخیره و خواندن تاریخچه چت ───────────────────────────
def test_chat_history_roundtrip():
    _save_bot_chat_message(USER_BID, 'user', 'سلام')
    _save_bot_chat_message(USER_BID, 'assistant', 'سلام عزیز')
    hist = _get_bot_chat_history(USER_BID, limit=6)
    assert len(hist) == 2
    assert hist[0]['role'] == 'user'
    assert hist[1]['role'] == 'assistant'
    # پاکسازی
    with get_giso_db_conn() as conn:
        conn.execute("DELETE FROM giso_bot_consultant_chat WHERE bale_id=?", (str(USER_BID),))
        conn.commit()
    print("PASS  ذخیره و خواندن تاریخچه چت مشاور")


# ── ۴) جریان چت مشاور در ربات ──────────────────────────────
async def _consultant_chat_flow():
    funcs = await get_test_handlers()
    handle_callback = funcs["handle_callback"]
    handle_text = funcs["handle_text"]

    # شروع چت از طریق callback
    cb = MagicMock()
    cb.data = "analysis_consultant"
    cb.edit_message_text = AsyncMock()
    cb.answer = AsyncMock()
    cb.from_user.id = USER_BID
    update = MagicMock()
    update.callback_query = cb
    update.effective_user.id = USER_BID
    context = MagicMock()
    context.bot.send_message = AsyncMock()
    context.user_data = {}
    await handle_callback(update, context)
    assert context.user_data.get('consultant_ai_active') is True
    txt, kwargs = cb.edit_message_text.call_args
    assert "عالیه" in txt[0]
    assert "برای پایان گفتگو /end" in txt[0]

    # ارسال پیام در حالت فعال
    with patch.object(bot_admin_utils, 'chat_with_managed_ai', new=AsyncMock(return_value={
        "ok": True, "text": "پاسخ مشاور برای شما",
        "provider": "llm7", "model": "gpt-4o-mini"
    })):
        msg = MagicMock()
        msg.reply_text = AsyncMock()
        msg.text = "چه روتینی پیشنهاد می‌دی؟"
        update2 = MagicMock()
        update2.effective_user.id = USER_BID
        update2.effective_message = msg
        update2.message = msg
        update2.effective_chat.id = USER_BID
        ctx2 = MagicMock()
        ctx2.bot.send_message = AsyncMock()
        ctx2.user_data = context.user_data  # state منتقل می‌شود
        await handle_text(update2, ctx2)

    msg.reply_text.assert_called()
    args, kwargs2 = msg.reply_text.call_args
    assert "پاسخ مشاور برای شما" in args[0]
    # تاریخچه ذخیره شده
    hist = _get_bot_chat_history(USER_BID, limit=6)
    assert any(m['role'] == 'user' and 'روتین' in m['message'] for m in hist)
    assert any(m['role'] == 'assistant' for m in hist)
    print("PASS  جریان کامل چت مشاور در ربات")


def test_consultant_chat_flow():
    app, aid = _setup_db()
    try:
        asyncio.run(_consultant_chat_flow())
    finally:
        _cleanup(app)


# ── ۴ب) دکمه مشاور از rootهای ساده‌شده حذف است ───────────
def test_consultant_ai_menu_button_hidden_from_reduced_roots():
    app, aid = _setup_db()
    try:
        user_flat = [b.text for row in _user_kb().keyboard for b in row]
        assert CONSULTANT_AI_LABEL not in user_flat
        admin_flat = [b.text for row in _admin_kb(ADMIN_BID).keyboard for b in row]
        assert CONSULTANT_AI_LABEL not in admin_flat
    finally:
        _cleanup(app)


# ── ۴پ) callback consultant_ai_start چت را فعال می‌کند ──────
async def _consultant_ai_callback_flow():
    funcs = await get_test_handlers()
    handle_callback = funcs["handle_callback"]

    cb = MagicMock()
    cb.data = "consultant_ai_start"
    cb.edit_message_text = AsyncMock()
    cb.answer = AsyncMock()
    cb.from_user.id = USER_BID
    update = MagicMock()
    update.callback_query = cb
    update.effective_user.id = USER_BID
    context = MagicMock()
    context.bot.send_message = AsyncMock()
    context.user_data = {}

    await handle_callback(update, context)
    assert context.user_data.get('consultant_ai_active') is True
    args, kwargs = cb.edit_message_text.call_args
    assert "عالیه" in args[0]


def test_consultant_ai_callback_flow():
    app, aid = _setup_db()
    try:
        asyncio.run(_consultant_ai_callback_flow())
        print("PASS  callback consultant_ai_start چت هوشمند را فعال می‌کند")
    finally:
        _cleanup(app)


# ── ۴پ-۲) دکمه منویی سوپرادمین نباید به fallback برسد ───────
async def _super_menu_button_flow():
    funcs = await get_test_handlers()
    handle_text = funcs["handle_text"]

    msg = MagicMock()
    msg.reply_text = AsyncMock()
    msg.text = CONSULTANT_AI_LABEL
    update = MagicMock()
    update.effective_user.id = SUPER_BID
    update.effective_message = msg
    update.message = msg
    update.effective_chat.id = SUPER_BID
    context = MagicMock()
    context.bot.send_message = AsyncMock()
    context.user_data = {}

    await handle_text(update, context)
    args, kwargs = msg.reply_text.call_args
    assert "در حال تکمیل" not in args[0]
    assert "همکار همراه" in args[0]
    assert "پایان گفتگو /end" in args[0]


def test_super_menu_button_flow():
    app, aid = _setup_db()
    try:
        asyncio.run(_super_menu_button_flow())
        print("PASS  دکمه منویی سوپرادمین مستقیماً چت مدیریتی را باز می‌کند")
    finally:
        _cleanup(app)


# ── ۴ث) بدون کلیک روی دکمه، راهنما نمایش داده می‌شود ────────
async def _consultant_ai_guard_flow():
    funcs = await get_test_handlers()
    handle_text = funcs["handle_text"]

    import time as _time
    touch_user_activity(USER_BID, ts=int(_time.time()))
    msg = MagicMock()
    msg.reply_text = AsyncMock()
    msg.text = "سلام معمولی"
    update = MagicMock()
    update.effective_user.id = USER_BID
    update.effective_message = msg
    update.message = msg
    update.effective_chat.id = USER_BID
    context = MagicMock()
    context.bot.send_message = AsyncMock()
    context.user_data = {}

    await handle_text(update, context)
    args, kwargs = msg.reply_text.call_args
    assert "برای صحبت با مشاور هوشمند گیسو" in args[0]
    assert kwargs.get("reply_markup") is not None


def test_consultant_ai_guard_flow():
    app, aid = _setup_db()
    try:
        asyncio.run(_consultant_ai_guard_flow())
        print("PASS  بدون فعال‌سازی، AI پاسخ نمی‌دهد و فقط راهنما نشان می‌دهد")
    finally:
        _cleanup(app)


# ── ۴ث-۲) ادمین محدود نباید با متن مخفی وارد منوی قدیمی AI شود ──
async def _restricted_admin_hidden_ai_text_flow():
    funcs = await get_test_handlers()
    handle_text = funcs["handle_text"]

    msg = MagicMock()
    msg.reply_text = AsyncMock()
    msg.text = "📋 فهرست پروایدرها"
    update = MagicMock()
    update.effective_user.id = RESTRICTED_AI_ADMIN_BID
    update.effective_message = msg
    update.message = msg
    update.effective_chat.id = RESTRICTED_AI_ADMIN_BID
    context = MagicMock()
    context.bot.send_message = AsyncMock()
    context.user_data = {}

    await handle_text(update, context)
    args, kwargs = msg.reply_text.call_args
    assert "دسترسی ندارید" in args[0]


def test_restricted_admin_hidden_ai_text_flow():
    app, aid = _setup_db()
    try:
        from bot_edu.giso_admin import add_giso_admin
        try:
            add_giso_admin(phone=RESTRICTED_AI_ADMIN_PHONE, bale_id=str(RESTRICTED_AI_ADMIN_BID), added_by=SUPER_BID)
        except Exception:
            pass
        _upsert_giso_user(RESTRICTED_AI_ADMIN_BID, phone=RESTRICTED_AI_ADMIN_PHONE,
                          first_name="ادمین محدود", contact_shared=True,
                          is_admin=True, pending_request=False)
        asyncio.run(_restricted_admin_hidden_ai_text_flow())
        print("PASS  ادمین محدود با متن مخفی وارد منوی قدیمی Provider/Proxy نمی‌شود")
    finally:
        _cleanup(app)


# ── ۴ث-۳) ادمین محدود نباید با callback مخفی وارد منوی قدیمی AI شود ─
async def _restricted_admin_hidden_ai_callback_flow():
    funcs = await get_test_handlers()
    handle_callback = funcs["handle_callback"]

    cb = MagicMock()
    cb.data = "ai_edit_back"
    cb.edit_message_text = AsyncMock()
    cb.answer = AsyncMock()
    cb.from_user.id = RESTRICTED_AI_ADMIN_BID
    update = MagicMock()
    update.callback_query = cb
    update.effective_user.id = RESTRICTED_AI_ADMIN_BID
    context = MagicMock()
    context.bot.send_message = AsyncMock()
    context.user_data = {}

    await handle_callback(update, context)
    args, kwargs = cb.edit_message_text.call_args
    assert "دسترسی ندارید" in args[0]


def test_restricted_admin_hidden_ai_callback_flow():
    app, aid = _setup_db()
    try:
        from bot_edu.giso_admin import add_giso_admin
        try:
            add_giso_admin(phone=RESTRICTED_AI_ADMIN_PHONE, bale_id=str(RESTRICTED_AI_ADMIN_BID), added_by=SUPER_BID)
        except Exception:
            pass
        _upsert_giso_user(RESTRICTED_AI_ADMIN_BID, phone=RESTRICTED_AI_ADMIN_PHONE,
                          first_name="ادمین محدود", contact_shared=True,
                          is_admin=True, pending_request=False)
        asyncio.run(_restricted_admin_hidden_ai_callback_flow())
        print("PASS  ادمین محدود با callback مخفی هم به منوی قدیمی Provider/Proxy دسترسی ندارد")
    finally:
        _cleanup(app)


# ── ۴ت) بازگشت بعد از ۶ ساعت → پیام خوش‌آمد هوشمند ─────────
async def _smart_welcome_after_gap_flow():
    funcs = await get_test_handlers()
    handle_text = funcs["handle_text"]

    old_ts = int(__import__('time').time()) - (7 * 3600)
    touch_user_activity(USER_BID, ts=old_ts)
    mark_welcome_shown(USER_BID, ts=old_ts)
    msg = MagicMock()
    msg.reply_text = AsyncMock()
    msg.text = "سلام بعد از وقفه"
    update = MagicMock()
    update.effective_user.id = USER_BID
    update.effective_message = msg
    update.message = msg
    update.effective_chat.id = USER_BID
    context = MagicMock()
    context.bot.send_message = AsyncMock()
    context.user_data = {}

    await handle_text(update, context)
    first_args, first_kwargs = msg.reply_text.call_args_list[0]
    assert "سلام" in first_args[0]
    assert first_kwargs.get("reply_markup") is not None


def test_smart_welcome_after_gap_flow():
    app, aid = _setup_db()
    try:
        asyncio.run(_smart_welcome_after_gap_flow())
        print("PASS  بعد از ۶ ساعت بی‌فعالیتی، پیام خوش‌آمد هوشمند نمایش داده می‌شود")
    finally:
        _cleanup(app)


# ── ۴چ) سوپرادمین در چت، درخواست مدیریتی را به flow اقدام می‌برد ─
async def _superadmin_action_flow():
    funcs = await get_test_handlers()
    handle_text = funcs["handle_text"]

    msg = MagicMock()
    msg.reply_text = AsyncMock()
    msg.text = "گزارش سفارش‌ها را بده"
    update = MagicMock()
    update.effective_user.id = SUPER_BID
    update.effective_message = msg
    update.message = msg
    update.effective_chat.id = SUPER_BID
    context = MagicMock()
    context.bot.send_message = AsyncMock()
    context.user_data = {'consultant_ai_active': True}

    with patch.object(bot_mod, 'process_superadmin_request', return_value={
        'handled': True,
        'mode': 'report',
        'text': '📊 گزارش سفارش‌ها آماده است'
    }):
        await handle_text(update, context)

    args, kwargs = msg.reply_text.call_args
    assert 'گزارش سفارش‌ها آماده است' in args[0]


def test_superadmin_action_flow():
    app, aid = _setup_db()
    try:
        asyncio.run(_superadmin_action_flow())
        print("PASS  چت سوپرادمین درخواست مدیریتی را از مسیر اقدام هوشمند عبور می‌دهد")
    finally:
        _cleanup(app)


# ── ۴چ-۲) سلام سوپرادمین باید وارد چت دوستانه شود ──────────
async def _superadmin_smalltalk_flow():
    funcs = await get_test_handlers()
    handle_text = funcs["handle_text"]

    msg = MagicMock()
    msg.reply_text = AsyncMock()
    msg.text = "سلام"
    update = MagicMock()
    update.effective_user.id = SUPER_BID
    update.effective_message = msg
    update.message = msg
    update.effective_chat.id = SUPER_BID
    context = MagicMock()
    context.bot.send_message = AsyncMock()
    context.user_data = {'consultant_ai_active': True}

    with patch.object(bot_mod, 'process_superadmin_request', return_value={'handled': False}), \
         patch.object(bot_mod, '_ask_consultant_bot', new=AsyncMock(return_value='سلام صادق جان 🌷 در خدمتم.')):
        await handle_text(update, context)

    args, kwargs = msg.reply_text.call_args
    assert 'سلام صادق جان' in args[0]
    assert 'خارج از محدوده' not in args[0]


def test_superadmin_smalltalk_flow():
    app, aid = _setup_db()
    try:
        asyncio.run(_superadmin_smalltalk_flow())
        print("PASS  سلام سوپرادمین دیگر به خطای خارج از محدوده نمی‌خورد")
    finally:
        _cleanup(app)


# ── ۴ج) /end چت را پایان می‌دهد ─────────────────────────────
async def _consultant_ai_end_flow():
    funcs = await get_test_handlers()
    handle_text = funcs["handle_text"]

    msg = MagicMock()
    msg.reply_text = AsyncMock()
    msg.text = "/end"
    update = MagicMock()
    update.effective_user.id = USER_BID
    update.effective_message = msg
    update.message = msg
    update.effective_chat.id = USER_BID
    context = MagicMock()
    context.bot.send_message = AsyncMock()
    context.user_data = {'consultant_ai_active': True}

    await handle_text(update, context)
    assert context.user_data.get('consultant_ai_active') is None
    args, kwargs = msg.reply_text.call_args
    assert "گفتگو پایان یافت" in args[0]


def test_consultant_ai_end_flow():
    app, aid = _setup_db()
    try:
        asyncio.run(_consultant_ai_end_flow())
        print("PASS  /end وضعیت consultant_ai_active را می‌بندد")
    finally:
        _cleanup(app)


# ── ۵) ثبت تیکت پشتیبانی + اطلاع به ادمین ──────────────────
async def _support_ticket_flow():
    funcs = await get_test_handlers()
    handle_text = funcs["handle_text"]

    msg = MagicMock()
    msg.reply_text = AsyncMock()
    msg.text = "مشکلی در پرداخت دارم"
    update = MagicMock()
    update.effective_user.id = SUPPORT_USER_BID
    update.effective_message = msg
    update.message = msg
    update.effective_chat.id = SUPPORT_USER_BID
    context = MagicMock()
    context.bot.send_message = AsyncMock()
    context.user_data = {'awaiting_support_message': True}

    await handle_text(update, context)

    msg.reply_text.assert_called()
    args, kwargs = msg.reply_text.call_args
    assert "پیامت ثبت شد" in args[0]
    assert "شماره تیکت" in args[0]
    # اطلاع به ادمین ارسال شد
    assert context.bot.send_message.called

    # بررسی در دیتابیس
    with get_giso_db_conn() as conn:
        row = conn.execute(
            "SELECT user_bale_id, message, status FROM giso_support_tickets "
            "WHERE user_bale_id=?", (str(SUPPORT_USER_BID),)).fetchone()
    assert row is not None and row[1] == "مشکلی در پرداخت دارم" and row[2] == 'new'
    print("PASS  ثبت تیکت پشتیبانی + اطلاع به ادمین")


def test_support_ticket_flow():
    app, aid = _setup_db()
    try:
        asyncio.run(_support_ticket_flow())
    finally:
        _cleanup(app)


# ── ۵ب) لیست «تیکت‌های من» ──────────────────────────────────
def test_support_my_tickets():
    app, aid = _setup_db()
    try:
        _create_support_ticket(SUPPORT_USER_BID, "کیان", normalize_phone("09130000003"),
                               "سفارشم نرسیده")
        funcs = asyncio.run(get_test_handlers())
        handle_callback = funcs["handle_callback"]

        async def run():
            cb = MagicMock()
            cb.data = "support_my_tickets"
            cb.edit_message_text = AsyncMock()
            cb.answer = AsyncMock()
            cb.from_user.id = SUPPORT_USER_BID
            update = MagicMock()
            update.callback_query = cb
            update.effective_user.id = SUPPORT_USER_BID
            context = MagicMock()
            context.bot.send_message = AsyncMock()
            context.user_data = {}
            await handle_callback(update, context)
            txt, kwargs = cb.edit_message_text.call_args
            assert "تیکت‌های شما" in txt[0]
            assert "سفارشم نرسیده" in txt[0]

        asyncio.run(run())
        print("PASS  لیست تیکت‌های من")
    finally:
        _cleanup(app)


# ── ۷ب) مشاهده جزئیات درخواست مشاوره (cons_view_) ──────────
def test_consultant_view():
    app, aid = _setup_db()
    try:
        funcs = asyncio.run(get_test_handlers())
        handle_callback = funcs["handle_callback"]

        with get_giso_db_conn() as conn:
            req_id = conn.execute("SELECT id FROM consultant_requests ORDER BY id DESC LIMIT 1").fetchone()[0]

        async def run():
            cb = MagicMock()
            cb.data = f"cons_view_{req_id}"
            cb.edit_message_text = AsyncMock()
            cb.answer = AsyncMock()
            cb.from_user.id = ADMIN_BID
            update = MagicMock()
            update.callback_query = cb
            update.effective_user.id = ADMIN_BID
            context = MagicMock()
            context.bot.send_message = AsyncMock()
            context.user_data = {}
            await handle_callback(update, context)
            txt, kwargs = cb.edit_message_text.call_args
            assert "درخواست مشاوره" in txt[0]
            assert "نگار" in txt[0]
            labels = [b.text for row in kwargs["reply_markup"].inline_keyboard for b in row]
            assert "💬 پاسخ دادن" in labels
            assert "✅ بستن" in labels

        asyncio.run(run())
        print("PASS  مشاهده جزئیات درخواست مشاوره")
    finally:
        _cleanup(app)


# ── ۶) پاسخ ادمین به تیکت ───────────────────────────────────
async def _admin_reply_ticket():
    funcs = await get_test_handlers()
    handle_text = funcs["handle_text"]

    # کاربر تیکت ایجاد می‌کند
    from giso.bot import _create_support_ticket
    ticket_id = _create_support_ticket(SUPPORT_USER_BID, "کیان", normalize_phone("09130000003"),
                                       "سفارشم نرسیده")

    # ادمین پاسخ می‌دهد
    msg = MagicMock()
    msg.reply_text = AsyncMock()
    msg.text = "سفارش شما در مسیر ارسال است."
    update = MagicMock()
    update.effective_user.id = ADMIN_BID
    update.effective_message = msg
    update.message = msg
    update.effective_chat.id = ADMIN_BID
    context = MagicMock()
    context.bot.send_message = AsyncMock()
    context.user_data = {'replying_ticket': ticket_id}

    await handle_text(update, context)

    msg.reply_text.assert_called()
    args, kwargs = msg.reply_text.call_args
    assert "پاسخ برای کاربر ارسال شد" in args[0]
    # وضعیت تیکت replied شد
    with get_giso_db_conn() as conn:
        row = conn.execute("SELECT status, admin_reply FROM giso_support_tickets WHERE id=?",
                           (ticket_id,)).fetchone()
    assert row[0] == 'replied' and row[1] == "سفارش شما در مسیر ارسال است."
    # به کاربر ارسال شد
    sent = [c.args for c in context.bot.send_message.call_args_list]
    assert any(kw['chat_id'] == SUPPORT_USER_BID for _, kw in context.bot.send_message.call_args_list)
    print("PASS  پاسخ ادمین به تیکت (آپدیت + ارسال به کاربر)")


def test_admin_reply_ticket():
    app, aid = _setup_db()
    try:
        asyncio.run(_admin_reply_ticket())
    finally:
        _cleanup(app)


# ── ۷) پاسخ ادمین به درخواست مشاوره ─────────────────────────
async def _admin_consultant_reply():
    funcs = await get_test_handlers()
    handle_callback = funcs["handle_callback"]
    handle_text = funcs["handle_text"]

    # پیدا کردن req id
    with get_giso_db_conn() as conn:
        row = conn.execute("SELECT id FROM consultant_requests ORDER BY id DESC LIMIT 1").fetchone()
        req_id = row[0]

    # callback cons_reply_<id>
    cb = MagicMock()
    cb.data = f"cons_reply_{req_id}"
    cb.answer = AsyncMock()
    cb.from_user.id = ADMIN_BID
    cb.message = MagicMock()
    cb.message.reply_text = AsyncMock()
    update = MagicMock()
    update.callback_query = cb
    update.effective_user.id = ADMIN_BID
    context = MagicMock()
    context.bot.send_message = AsyncMock()
    context.user_data = {}
    await handle_callback(update, context)
    assert context.user_data.get('replying_consultant') == req_id

    # ادمین پاسخ می‌دهد
    msg = MagicMock()
    msg.reply_text = AsyncMock()
    msg.text = "سلام نگار، با شما تماس می‌گیریم."
    update2 = MagicMock()
    update2.effective_user.id = ADMIN_BID
    update2.effective_message = msg
    update2.message = msg
    update2.effective_chat.id = ADMIN_BID
    ctx2 = MagicMock()
    ctx2.bot.send_message = AsyncMock()
    ctx2.user_data = context.user_data
    await handle_text(update2, ctx2)

    msg.reply_text.assert_called()
    args, kwargs = msg.reply_text.call_args
    assert "پاسخ ثبت شد" in args[0]
    with get_giso_db_conn() as conn:
        st = conn.execute("SELECT status FROM consultant_requests WHERE id=?", (req_id,)).fetchone()
        msgs = conn.execute("SELECT sender, message FROM consultant_messages WHERE request_id=?",
                            (req_id,)).fetchall()
    assert st[0] == 'chatting'
    assert any(m[0] == 'admin' and 'تماس می‌گیریم' in m[1] for m in msgs)
    print("PASS  پاسخ ادمین به درخواست مشاوره")


def test_admin_consultant_reply():
    app, aid = _setup_db()
    try:
        asyncio.run(_admin_consultant_reply())
    finally:
        _cleanup(app)


# ── ۸) مدیریت محصول درخواستی ───────────────────────────────
async def _product_action():
    funcs = await get_test_handlers()
    handle_callback = funcs["handle_callback"]

    with get_giso_db_conn() as conn:
        row = conn.execute("SELECT id FROM product_requests ORDER BY id DESC LIMIT 1").fetchone()
        prod_id = row[0]

    # prod_view_
    cb = MagicMock()
    cb.data = f"prod_view_{prod_id}"
    cb.edit_message_text = AsyncMock()
    cb.answer = AsyncMock()
    cb.from_user.id = ADMIN_BID
    update = MagicMock()
    update.callback_query = cb
    update.effective_user.id = ADMIN_BID
    context = MagicMock()
    context.bot.send_message = AsyncMock()
    context.user_data = {}
    await handle_callback(update, context)
    txt, kwargs = cb.edit_message_text.call_args
    assert "درخواست محصول" in txt[0]

    # prod_add_
    cb2 = MagicMock()
    cb2.data = f"prod_add_{prod_id}"
    cb2.edit_message_text = AsyncMock()
    cb2.answer = AsyncMock()
    cb2.from_user.id = ADMIN_BID
    cb2.message = MagicMock()
    cb2.message.text = "قبلی"
    update2 = MagicMock()
    update2.callback_query = cb2
    update2.effective_user.id = ADMIN_BID
    ctx2 = MagicMock()
    ctx2.bot.send_message = AsyncMock()
    ctx2.user_data = {}
    await handle_callback(update2, ctx2)
    with get_giso_db_conn() as conn:
        st = conn.execute("SELECT status FROM product_requests WHERE id=?", (prod_id,)).fetchone()
    assert st[0] == 'added'
    print("PASS  مدیریت محصول درخواستی (نمایش + اضافه شد)")


def test_product_action():
    app, aid = _setup_db()
    try:
        asyncio.run(_product_action())
    finally:
        _cleanup(app)


# ── ۹) باگ بازگشت: ادمین محدود → خانه → کیبورد فیلتر شده ───
def test_back_bug_fixed():
    app = create_app()
    try:
        _upsert_giso_user(ADMIN_BID, phone=normalize_phone("09120000002"),
                          first_name="ادمین", contact_shared=True,
                          is_admin=True, pending_request=False)
        kb = _admin_kb(ADMIN_BID)
        flat = [b.text for row in kb.keyboard for b in row]
        assert flat == ["💇 خرید مو", "🛍 فروشگاه", "🏪 بازارچه", "💬 مدیریت گفتگوها"]
        assert "🏠 خانه" not in flat
        # بدون user_id → همه گزینه‌ها (رفتار امن پیش‌فرض، نه پیام /start)
        kb_empty = _admin_kb()
        flat_empty = [b.text for row in kb_empty.keyboard for b in row]
        assert "🔬 آنالیز" in flat_empty
        assert "📊 پیشخوان" in flat_empty
        assert "🏠 خانه" not in flat_empty
        print("PASS  باگ بازگشت: ادمین محدود گزینه‌های مجازش را حفظ می‌کند + بدون user_id همه گزینه‌ها")
    finally:
        _cleanup(app)


def _run():
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    passed = 0
    for t in tests:
        try:
            t()
            passed += 1
        except AssertionError as e:
            print(f"FAIL  {t.__name__}: {e}")
        except Exception as e:  # noqa: BLE001
            print(f"ERROR {t.__name__}: {type(e).__name__}: {e}")
    print(f"\n{passed}/{len(tests)} passed")
    return passed == len(tests)


if __name__ == "__main__":
    sys.exit(0 if _run() else 1)
