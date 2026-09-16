#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
تست مرحله ۷ از ۹: پنل ادمین آنالیز در ربات

۱) توابع کمکی admin (module-level) کار می‌کنند:
   _is_giso_admin, _get_admin_analysis_stats, _get_recent_analyses,
   _get_recent_consultant_requests, _get_recent_product_requests.
۲) زیرمنوی «🔬 مدیریت آنالیز» برای ادمین نمایش داده می‌شود و badge جدید دارد.
۳) callbacks: adm_ana_menu, adm_ana_stats, adm_ana_list, adm_ana_consultants,
   adm_ana_products, adm_ana_ratelimit.
۴) کاربر غیر ادمین دسترسی ندارد.
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
from giso.base import normalize_phone, get_giso_db_conn  # noqa: E402
from giso.bot import (
    _is_giso_admin, _get_admin_analysis_stats, _get_recent_analyses,
    _get_recent_consultant_requests, _get_recent_product_requests,
    SITE_BASE_URL, get_test_handlers,
)  # noqa: E402

PHONE = "09190000888"
ADMIN_BID = 555001
USER_BID = 555002
SUPER_BID = 1191639507


def _setup_db():
    app = create_app()
    with app.app_context():
        user = User.query.filter_by(phone=normalize_phone(PHONE)).first()
        if not user:
            user = User(phone=normalize_phone(PHONE),
                        password_hash="pbkdf2:sha256:260000$test$hash", name="مریم")
            db.session.add(user)
            db.session.commit()
        # پاکسازی قبلی
        for a in Analysis.query.filter_by(user_id=user.id).all():
            db.session.delete(a)
        db.session.commit()
        a = Analysis(phone=normalize_phone(PHONE), user_id=user.id, type="hair",
                     photo_path="analysis/",
                     ai_report_json=json.dumps({"status_label": "خوب"}),
                     chat_rating=5)
        db.session.add(a)
        db.session.commit()
        aid = a.id

        # ربات: ادمین + کاربر عادی
        from giso.base import _upsert_giso_user
        _upsert_giso_user(ADMIN_BID, phone=normalize_phone("09120000002"),
                          first_name="ادمین", contact_shared=True,
                          is_admin=True, pending_request=False)
        _upsert_giso_user(USER_BID, phone=normalize_phone("09350000003"),
                          first_name="کاربر", contact_shared=True,
                          is_admin=False, pending_request=False)
        # درخواست مشاوره جدید
        try:
            with get_giso_db_conn() as conn:
                conn.execute(
                    "INSERT INTO consultant_requests (user_id, phone, city, customer_name, analysis_id, "
                    "initial_message, status, created_at, updated_at) "
                    "VALUES (?,?,?,?,?,?, 'new', ?, ?)",
                    (user.id, normalize_phone(PHONE), "تهران", "مریم", aid, "سلام مشاور",
                     "2026-08-05 05:00:00", "2026-08-05 05:00:00"))
                conn.commit()
        except Exception:
            pass
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
            for bid in (ADMIN_BID, USER_BID):
                conn.execute("DELETE FROM giso_users WHERE bale_id=?", (str(bid),))
            conn.execute("DELETE FROM consultant_requests WHERE customer_name='مریم'")
            conn.commit()
    except Exception:
        pass


# ── ۱) توابع کمکی ───────────────────────────────────────────
def test_admin_helpers():
    app, aid = _setup_db()
    try:
        assert _is_giso_admin(ADMIN_BID) is True
        assert _is_giso_admin(USER_BID) is False

        stats = _get_admin_analysis_stats()
        assert stats['total'] >= 1
        assert stats['hair_count'] >= 1
        assert stats['total_consultants'] >= 1
        assert stats['pending_consultants'] >= 1
        assert stats['avg_rating'] == 5

        analyses = _get_recent_analyses(limit=5)
        assert any(x['id'] == aid for x in analyses)
        assert analyses[0]['user_name'] == 'مریم'

        cons = _get_recent_consultant_requests(limit=5)
        assert cons and cons[0]['status'] == 'new'

        prods = _get_recent_product_requests(limit=5)
        assert isinstance(prods, list)
        print("PASS  توابع کمکی پنل ادمین آنالیز")
    finally:
        _cleanup(app)


# ── ۲) callbacks ────────────────────────────────────────────
async def _run_callbacks():
    bot_funcs = await get_test_handlers()
    handle_callback = bot_funcs["handle_callback"]

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
        await handle_callback(update, context)
        return cb

    # ۲) adm_ana_menu (ادمین) → منو با badge جدید
    cb = await make_cb("adm_ana_menu", ADMIN_BID)
    txt, kwargs = cb.edit_message_text.call_args
    assert "مدیریت آنالیز" in txt[0]
    assert "آمار سریع" in txt[0]
    labels = [b.text for row in kwargs["reply_markup"].inline_keyboard for b in row]
    assert "📊 آمار کامل" in labels
    assert "📋 لیست ۱۰ تحلیل آخر" in labels
    assert any("درخواست‌های مشاوره" in l and "(" in l for l in labels)  # badge
    assert "⏱ تنظیمات محدودیت زمانی" not in labels
    urls = [b.url for row in kwargs["reply_markup"].inline_keyboard for b in row if b.url]
    assert any("admin/analyses" in u for u in urls)
    print("PASS  منوی مدیریت آنالیز + آمار سریع + badge + لینک سایت")

    # ۳) adm_ana_stats
    cb = await make_cb("adm_ana_stats", ADMIN_BID)
    txt, kwargs = cb.edit_message_text.call_args
    assert "آمار کامل آنالیز گیسو" in txt[0]
    assert "کل تحلیل" in txt[0]
    assert "میانگین امتیاز" in txt[0]
    print("PASS  آمار کامل")

    # ۴) adm_ana_list
    cb = await make_cb("adm_ana_list", ADMIN_BID)
    txt, kwargs = cb.edit_message_text.call_args
    assert "تحلیل آخر" in txt[0]
    assert "مریم" in txt[0]
    assert "📱" in txt[0]
    urls = [b.url for row in kwargs["reply_markup"].inline_keyboard for b in row if b.url]
    assert any("admin/analyses" in u for u in urls)
    print("PASS  لیست ۱۰ تحلیل آخر با اطلاعات کاربر")

    # ۵) adm_ana_consultants → هر درخواست کلیک‌پذیر (cons_view_)
    cb = await make_cb("adm_ana_consultants", ADMIN_BID)
    txt, kwargs = cb.edit_message_text.call_args
    assert "درخواست‌های مشاوره" in txt[0]
    labels = [b.text for row in kwargs["reply_markup"].inline_keyboard for b in row]
    assert any("مریم" in l for l in labels)
    callbacks = [b.callback_data for row in kwargs["reply_markup"].inline_keyboard for b in row if b.callback_data]
    assert any(c.startswith("cons_view_") for c in callbacks)
    print("PASS  درخواست‌های مشاوره کلیک‌پذیر")

    # ۶) adm_ana_products (بدون درخواست → پیام خالی)
    cb = await make_cb("adm_ana_products", ADMIN_BID)
    txt, kwargs = cb.edit_message_text.call_args
    assert "محصول درخواستی" in txt[0]
    labels = [b.text for row in kwargs["reply_markup"].inline_keyboard for b in row]
    assert "🔙 بازگشت" in labels
    print("PASS  محصولات درخواستی")

    # ۷) محدودیت زمانی فقط برای سوپرادمین
    cb = await make_cb("adm_ana_ratelimit", ADMIN_BID)
    txt, _ = cb.edit_message_text.call_args
    assert "فقط برای سوپرادمین" in txt[0]

    cb = await make_cb("adm_ana_menu", SUPER_BID)
    _, kwargs = cb.edit_message_text.call_args
    labels = [b.text for row in kwargs["reply_markup"].inline_keyboard for b in row]
    assert "⏱ تنظیمات محدودیت زمانی" in labels

    cb = await make_cb("adm_ana_ratelimit", SUPER_BID)
    txt, kwargs = cb.edit_message_text.call_args
    assert "محدودیت زمانی" in txt[0]
    urls = [b.url for row in kwargs["reply_markup"].inline_keyboard for b in row if b.url]
    assert any("analysis-ratelimit" in u for u in urls)
    print("PASS  تنظیمات محدودیت زمانی فقط برای سوپرادمین")

    # ۸) کاربر غیر ادمین → دسترسی ندارد
    cb = await make_cb("adm_ana_stats", USER_BID)
    txt, _ = cb.edit_message_text.call_args
    assert "دسترسی ندارید" in txt[0]
    print("PASS  کاربر غیر ادمین دسترسی ندارد")


def test_admin_callbacks():
    app, aid = _setup_db()
    try:
        asyncio.run(_run_callbacks())
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
