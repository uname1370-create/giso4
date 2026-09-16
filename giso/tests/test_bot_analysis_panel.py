#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
تست مرحله ۶ از ۹: پنل کاربر آنالیز در ربات

۱) توابع کمکی اتصال به سایت (module-level) کار می‌کنند:
   _check_site_user_info, _get_user_phone, _get_user_analyses, _get_analysis_by_id,
   _get_latest_analysis, _get_latest_analysis_with_plan.
۲) پیام خوش‌آمد سایت (_build_welcome_from_site / _default_welcome_message).
۳) زیرمنوی آنالیز (analysis_menu) با دکمه‌های inline نمایش داده می‌شود.
۴) لیست آنالیزها (analysis_list)، جزئیات (analysis_view_<id>)، چک‌لیست
   (analysis_checklist)، مشاور (analysis_consultant)، محصولات (analysis_products).
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
from giso.base import normalize_phone  # noqa: E402
from giso.bot import (
    _check_site_user_info, _build_welcome_from_site, _default_welcome_message,
    _get_user_phone, _get_user_analyses, _get_analysis_by_id,
    _get_latest_analysis, _get_latest_analysis_with_plan, SITE_BASE_URL,
    get_test_handlers,
)  # noqa: E402

PHONE = "09190000444"
BALE_ID = 777001

PLAN_JSON = {
    "duration_weeks": 4,
    "consultant_intro": "سلام",
    "checklist": {"weeks": [
        {"week_number": 1, "items": ["ماسک آبرسان", "خواب کافی"]},
        {"week_number": 2, "items": ["ماسک ترمیم"]},
    ]},
}


def _setup_db():
    app = create_app()
    with app.app_context():
        user = User.query.filter_by(phone=normalize_phone(PHONE)).first()
        if not user:
            user = User(phone=normalize_phone(PHONE),
                        password_hash="pbkdf2:sha256:260000$test$hash", name="مریم",
                        city="تهران")
            db.session.add(user)
            db.session.commit()
        # پاکسازی تحلیل‌های قبلی
        for a in Analysis.query.filter_by(user_id=user.id).all():
            db.session.delete(a)
        db.session.commit()
        a1 = Analysis(phone=normalize_phone(PHONE), user_id=user.id, type="hair",
                      photo_path="analysis/",
                      ai_report_json=json.dumps(
                          {"status_label": "خوب", "overall_status": "خوب",
                           "summary": "موهای شما نیاز به آبرسانی دارد"}, ensure_ascii=False),
                      plan_json=json.dumps(PLAN_JSON, ensure_ascii=False),
                      checklist_progress=json.dumps({"w1-0": True}, ensure_ascii=False))
        db.session.add(a1)
        db.session.commit()
        aid = a1.id

        # ربات: ثبت giso_users برای کاربر
        from giso.base import _upsert_giso_user
        _upsert_giso_user(BALE_ID, phone=normalize_phone(PHONE), first_name="مریم",
                          contact_shared=True, is_admin=False, pending_request=False)
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
        from giso.base import get_giso_db_conn
        with get_giso_db_conn() as conn:
            conn.execute("DELETE FROM giso_users WHERE bale_id=?", (str(BALE_ID),))
            conn.commit()
    except Exception:
        pass


# ── ۱) توابع کمکی ───────────────────────────────────────────
def test_helpers():
    app, aid = _setup_db()
    try:
        # _check_site_user_info
        info = _check_site_user_info(normalize_phone(PHONE))
        assert info['has_account'] is True
        assert info['analyses_count'] == 1
        assert info['has_hair_analysis'] is True
        assert info['last_analysis_id'] == aid
        assert info['has_active_checklist'] is True
        assert info['city'] == 'تهران'

        # _get_user_phone
        assert _get_user_phone(str(BALE_ID)) == normalize_phone(PHONE)

        # _get_user_analyses
        analyses = _get_user_analyses(normalize_phone(PHONE), limit=5)
        assert len(analyses) == 1
        assert analyses[0]['id'] == aid
        assert analyses[0]['type'] == 'hair'

        # _get_analysis_by_id
        a = _get_analysis_by_id(aid, normalize_phone(PHONE))
        assert a is not None and a['id'] == aid
        # مالکیت اشتباه
        assert _get_analysis_by_id(aid, "09120000000") is None

        # _get_latest_analysis / _get_latest_analysis_with_plan
        assert _get_latest_analysis(normalize_phone(PHONE))['id'] == aid
        la = _get_latest_analysis_with_plan(normalize_phone(PHONE))
        assert la is not None and la['id'] == aid

        # پیام‌های خوش‌آمد (کاربر با تحلیل → بدون لینک، فقط منو)
        w = _build_welcome_from_site(info, "کاربر")
        assert "مریم" in w
        assert "تحلیل" in w
        assert "آنالیز هوشمند" in w
        # کاربر بدون تحلیل → حاوی لینک سایت
        w0 = _build_welcome_from_site({"has_account": True, "analyses_count": 0}, "کاربر")
        assert SITE_BASE_URL in w0
        d = _default_welcome_message("علی")
        assert "علی" in d and SITE_BASE_URL in d
        print("PASS  توابع کمکی اتصال به سایت کار می‌کنند")
    finally:
        _cleanup(app)


# ── ۲) زیرمنوی آنالیز و callbacks ────────────────────────────
async def _run_callbacks(aid):
    bot_funcs = await get_test_handlers()
    handle_callback = bot_funcs["handle_callback"]

    async def make_cb(data):
        cb = MagicMock()
        cb.data = data
        cb.edit_message_text = AsyncMock()
        cb.answer = AsyncMock()
        cb.from_user.id = BALE_ID
        update = MagicMock()
        update.callback_query = cb
        update.effective_user.id = BALE_ID
        context = MagicMock()
        context.bot.send_message = AsyncMock()
        await handle_callback(update, context)
        return cb

    # ۲) analysis_menu
    cb = await make_cb("analysis_menu")
    txt, kwargs = cb.edit_message_text.call_args
    assert "آنالیز هوشمند گیسو" in txt[0]
    assert kwargs["reply_markup"] is not None
    btn_labels = [b.text for row in kwargs["reply_markup"].inline_keyboard for b in row]
    assert "📋 آنالیزهای من" in btn_labels
    assert "✅ چک‌لیست پیشرفت من" in btn_labels
    assert "💬 گفتگو با مشاور" in btn_labels
    assert "🛒 محصولات پیشنهادی من" in btn_labels
    assert "🌐 تحلیل جدید در سایت" in btn_labels
    print("PASS  زیرمنوی آنالیز با ۴ گزینه + چک‌لیست + لینک سایت")

    # ۳) analysis_list
    cb = await make_cb("analysis_list")
    txt, kwargs = cb.edit_message_text.call_args
    assert "آنالیزهای شما" in txt[0]
    labels = [b.text for row in kwargs["reply_markup"].inline_keyboard for b in row]
    assert any("تحلیل مو" in l for l in labels)
    print("PASS  لیست آنالیزهای من")

    # ۴) analysis_view_<id>
    cb = await make_cb(f"analysis_view_{aid}")
    txt, kwargs = cb.edit_message_text.call_args
    assert "تحلیل مو" in txt[0]
    assert "آبرسانی" in txt[0]
    urls = [b.url for row in kwargs["reply_markup"].inline_keyboard for b in row if b.url]
    assert any(SITE_BASE_URL in u for u in urls)
    print("PASS  جزئیات تحلیل + لینک به سایت")

    # ۵) analysis_checklist
    cb = await make_cb("analysis_checklist")
    txt, kwargs = cb.edit_message_text.call_args
    assert "چک‌لیست پیشرفت شما" in txt[0]
    assert "پیشرفت" in txt[0]
    assert "ماسک آبرسان" in txt[0]
    assert "✅" in txt[0]  # آیتم تیک‌خورده
    print("PASS  چک‌لیست با درصد پیشرفت")

    # ۶) analysis_consultant → شروع چت در خود ربات
    cb = await make_cb("analysis_consultant")
    txt, kwargs = cb.edit_message_text.call_args
    assert "عالیه" in txt[0]
    assert "برای پایان گفتگو /end" in txt[0]
    labels = [b.text for row in kwargs["reply_markup"].inline_keyboard for b in row]
    assert "❌ پایان گفتگو" in labels
    print("PASS  مشاور با شروع چت در ربات")

    # ۷) analysis_products
    cb = await make_cb("analysis_products")
    txt, kwargs = cb.edit_message_text.call_args
    assert "محصولات پیشنهادی" in txt[0]
    urls = [b.url for row in kwargs["reply_markup"].inline_keyboard for b in row if b.url]
    assert any("shop" in u for u in urls)
    print("PASS  محصولات با لینک به فروشگاه")


def test_analysis_callbacks():
    app, aid = _setup_db()
    try:
        asyncio.run(_run_callbacks(aid))
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
