#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
تست گروه C - پیام ورود هوشمند + خلاصه گفتگو + حذف دکمه خانه

۱) _get_user_dashboard_info: اطلاعات واقعی کاربر (تحلیل/برنامه/چک‌لیست/فعالیت)
۲) _build_smart_welcome_user: پیام خوش‌آمد کاربر با/بدون اکانت
۳) _get_admin_dashboard_stats: آمار واقعی امروز + در انتظار
۴) _build_smart_welcome_admin: پیام خوش‌آمد ادمین با اولویت‌ها
۵) _get_chat_summaries با فیلتر (all/today)
۶) callback adm_ana_chats + فیلترها در پنل ادمین آنالیز
۷) حذف دکمه «🏠 خانه» از _admin_kb و _user_kb
"""
import asyncio
import json
import os
import sys
from unittest.mock import MagicMock, AsyncMock

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if BASE_DIR not in sys.path:
    sys.path.append(BASE_DIR)

from giso.app import create_app  # noqa: E402
from giso.models import db, User, Analysis  # noqa: E402
from giso.base import normalize_phone, get_giso_db_conn, _upsert_giso_user  # noqa: E402
from giso.bot import (
    _get_user_dashboard_info, _build_smart_welcome_user,
    _get_admin_dashboard_stats, _build_smart_welcome_admin,
    _get_chat_summaries, _admin_kb, _user_kb,
    get_test_handlers,
)  # noqa: E402

PHONE = "09190001122"
USER_BID = 888001
ADMIN_BID = 888002
SUPPORT_BID = 888003


def _setup_db():
    app = create_app()
    with app.app_context():
        user = User.query.filter_by(phone=normalize_phone(PHONE)).first()
        if not user:
            user = User(phone=normalize_phone(PHONE),
                        password_hash="pbkdf2:sha256:260000$test$hash",
                        name="سارا", city="اصفهان")
            db.session.add(user)
            db.session.commit()
        for a in Analysis.query.filter_by(user_id=user.id).all():
            db.session.delete(a)
        db.session.commit()

        plan = {"duration_weeks": 6, "checklist": {"weeks": [
            {"week_number": 1, "items": ["ماسک آبرسان"]},
            {"week_number": 2, "items": ["شامپو ملایم"]},
        ]}}
        a = Analysis(phone=normalize_phone(PHONE), user_id=user.id, type="hair",
                     photo_path="analysis/",
                     ai_report_json=json.dumps({"overall_score": 82}),
                     plan_json=json.dumps(plan),
                     checklist_progress=json.dumps({"w1-0": True}),
                     consultant_key_notes="خلاصه گفتگو",
                     consultant_chat_history=json.dumps([
                         {"role": "user", "message": "سلام"},
                         {"role": "assistant", "message": "سلام عزیز"},
                     ]),
                     chat_rating=5)
        db.session.add(a)
        db.session.commit()
        aid = a.id

        _upsert_giso_user(USER_BID, phone=normalize_phone(PHONE),
                          first_name="سارا", contact_shared=True,
                          is_admin=False, pending_request=False)
        _upsert_giso_user(ADMIN_BID, phone=normalize_phone("09120000005"),
                          first_name="ادمین", contact_shared=True,
                          is_admin=True, pending_request=False)

        with get_giso_db_conn() as conn:
            conn.execute(
                "INSERT INTO consultant_requests (user_id, phone, city, customer_name, analysis_id, "
                "initial_message, status, created_at, updated_at) "
                "VALUES (?,?,?,?,?,?, 'new', ?, ?)",
                (user.id, normalize_phone(PHONE), "اصفهان", "سارا", aid, "سلام",
                 "2026-08-05 05:00:00", "2026-08-05 05:00:00"))
            conn.execute(
                "INSERT INTO product_requests (user_id, phone, city, analysis_id, "
                "problem_summary, status, created_at) "
                "VALUES (?,?,?,?,?, 'pending', ?)",
                (user.id, normalize_phone(PHONE), "اصفهان", aid, "خشکی", "2026-08-05 05:00:00"))
            conn.commit()
    return app, aid


def _cleanup(app):
    try:
        with app.app_context():
            for u in User.query.filter_by(phone=normalize_phone(PHONE)).all():
                for a in Analysis.query.filter_by(phone=u.phone).all():
                    db.session.delete(a)
                db.session.delete(u)
            db.session.commit()
    except Exception:
        pass
    try:
        with get_giso_db_conn() as conn:
            for bid in (USER_BID, ADMIN_BID, SUPPORT_BID):
                conn.execute("DELETE FROM giso_users WHERE bale_id=?", (str(bid),))
            conn.execute("DELETE FROM giso_support_tickets")
            conn.execute("DELETE FROM consultant_requests")
            conn.execute("DELETE FROM product_requests")
            conn.commit()
    except Exception:
        pass


# ── ۱) اطلاعات دشبورد کاربر ─────────────────────────────────
def test_user_dashboard_info():
    app, aid = _setup_db()
    try:
        info = _get_user_dashboard_info(normalize_phone(PHONE), USER_BID)
        assert info['has_account'] is True
        assert info['user_name'] == 'سارا'
        assert info['last_analysis']['type'] == 'مو'
        assert info['last_analysis']['score'] == 82
        assert info['active_plan']['weeks'] == 6
        assert info['checklist_progress']['done'] == 1
        assert info['checklist_progress']['total'] == 2
        assert info['pending_consultants'] == 1
        assert info['pending_products'] == 1
        assert info['has_new_activity'] is True
        print("PASS  _get_user_dashboard_info اطلاعات واقعی کاربر را می‌سازد")
    finally:
        _cleanup(app)


# ── ۲) پیام خوش‌آمد کاربر ───────────────────────────────────
def test_smart_welcome_user():
    app, aid = _setup_db()
    try:
        info = _get_user_dashboard_info(normalize_phone(PHONE), USER_BID)
        msg = _build_smart_welcome_user(info, "سارا")
        assert "سلام سارا عزیز" in msg
        assert "خلاصه وضعیت شما" in msg
        assert "آخرین تحلیل" in msg
        assert "برنامه فعال: 6 هفته‌ای" in msg
        assert "چک‌لیست: 1/2" in msg
        assert "چیزهای جدید" in msg
        assert "درخواست مشاوره" in msg

        # کاربر بدون اکانت
        no_acc = {'has_account': False, 'user_name': 'دوست عزیز'}
        msg2 = _build_smart_welcome_user(no_acc, "کاربر")
        assert "خوش اومدی" in msg2
        assert "سایت گیسو" in msg2
        print("PASS  _build_smart_welcome_user پیام خوش‌آمد کاربر (با/بدون اکانت)")
    finally:
        _cleanup(app)


# ── ۳) آمار دشبورد ادمین ────────────────────────────────────
def test_admin_dashboard_stats():
    app, aid = _setup_db()
    try:
        stats = _get_admin_dashboard_stats()
        assert isinstance(stats, dict)
        assert 'today_analyses' in stats
        assert 'priorities' in stats
        # حداقل یک درخواست مشاوره در انتظار ثبت شده → باید در اولویت‌ها باشد
        assert stats['pending_consultations'] >= 1
        assert any('درخواست مشاوره' in p for p in stats['priorities'])
        # هیچ شمارش منفی‌ای نباشد (از دیتابیس واقعی)
        for k, v in stats.items():
            if k != 'priorities':
                assert v >= 0, f"{k} نباید منفی باشد"
        print("PASS  _get_admin_dashboard_stats آمار واقعی را می‌سازد")
    finally:
        _cleanup(app)


# ── ۴) پیام خوش‌آمد ادمین ───────────────────────────────────
def test_smart_welcome_admin():
    app, aid = _setup_db()
    try:
        stats = _get_admin_dashboard_stats()
        msg_super = _build_smart_welcome_admin(stats, "علی", is_super=True)
        assert "مدیر" in msg_super
        assert "وضعیت امروز گیسو" in msg_super
        assert "آنالیز" in msg_super

        msg_admin = _build_smart_welcome_admin(stats, "مریم", is_super=False)
        assert "ادمین" in msg_admin
        assert "اولویت‌های شما" in msg_admin
        print("PASS  _build_smart_welcome_admin پیام خوش‌آمد ادمین با اولویت‌ها")
    finally:
        _cleanup(app)


# ── ۵) خلاصه گفتگوها ────────────────────────────────────────
def test_chat_summaries():
    app, aid = _setup_db()
    try:
        all_s = _get_chat_summaries(filter_type='all', limit=10)
        assert isinstance(all_s, list)
        assert len(all_s) >= 1
        s = all_s[0]
        assert s['user_name'] == 'سارا'
        assert s['message_count'] == 2
        assert s['summary'] == 'خلاصه گفتگو'
        assert s['rating'] == 5
        # فیلتر امروز هم باید بازگردد (چون created_at امروز است)
        today_s = _get_chat_summaries(filter_type='today', limit=10)
        assert isinstance(today_s, list)
        print("PASS  _get_chat_summaries با فیلتر خلاصه گفتگوها را می‌دهد")
    finally:
        _cleanup(app)


# ── ۶) callback خلاصه گفتگوها ───────────────────────────────
async def _run_chat_callback():
    funcs = await get_test_handlers()
    handle_callback = funcs["handle_callback"]

    async def make_cb(data, uid):
        cb = MagicMock()
        cb.data = data
        cb.edit_message_text = AsyncMock()
        cb.answer = AsyncMock()
        cb.from_user.id = uid
        update = MagicMock()
        update.callback_query = cb
        update.effective_user.id = uid
        context = MagicMock()
        context.bot.send_message = AsyncMock()
        context.user_data = {}
        await handle_callback(update, context)
        return cb, context

    # adm_ana_chats_all
    cb, _ = await make_cb("adm_ana_chats_all", ADMIN_BID)
    txt, kwargs = cb.edit_message_text.call_args
    assert "خلاصه گفتگوهای مشاور" in txt[0]
    assert "سارا" in txt[0]
    labels = [b.text for row in kwargs["reply_markup"].inline_keyboard for b in row]
    assert "📅 امروز" in labels
    assert "📆 هفته" in labels
    assert "🗓 ماه" in labels
    assert "📚 همه" in labels
    # امروز
    cb2, _ = await make_cb("adm_ana_chats_today", ADMIN_BID)
    txt2, _ = cb2.edit_message_text.call_args
    assert "فیلتر: امروز" in txt2[0]
    print("PASS  callback خلاصه گفتگوها با فیلتر")


def test_chat_callback():
    app, aid = _setup_db()
    try:
        asyncio.run(_run_chat_callback())
    finally:
        _cleanup(app)


# ── ۷) حذف دکمه «🏠 خانه» ───────────────────────────────────
def test_no_home_button():
    app = create_app()
    try:
        _upsert_giso_user(ADMIN_BID, phone=normalize_phone("09120000005"),
                          first_name="ادمین", contact_shared=True,
                          is_admin=True, pending_request=False)
        kb_admin = _admin_kb(ADMIN_BID)
        flat_admin = [b.text for row in kb_admin.keyboard for b in row]
        assert "🏠 خانه" not in flat_admin

        kb_super = _admin_kb()  # backward compatible
        flat_super = [b.text for row in kb_super.keyboard for b in row]
        assert "🏠 خانه" not in flat_super

        kb_user = _user_kb()
        flat_user = [b.text for row in kb_user.keyboard for b in row]
        assert "🏠 خانه" not in flat_user
        print("PASS  دکمه «🏠 خانه» از همه کیبوردها حذف شده")
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
