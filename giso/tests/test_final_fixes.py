#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
تست رفع ۴ مشکل حیاتی نهایی

۱) باگ کیبورد ادمین محدود: بدون user_id → کیبورد امن؛ سوپرادمین همه؛ ادمین محدود فقط مجازها
۲) خلاصه گفتگو → گفتگوی کامل قابل مشاهده (adm_chat_view_) + رفع «کاربر ناشناس» با COALESCE
۴) چیدمان بررسی عکس: دکمه‌های وسط حذف شده (فقط عنوان/نکات/تیک‌ها/دکمه‌های پایین)
"""
import asyncio
import io
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
    _admin_kb, _get_chat_summaries,
    get_test_handlers,
)  # noqa: E402

PHONE = "09190008888"
ADMIN_BID = 999001
SUPER_BID = 1191639507
USER_BID = 999002


def _setup():
    app = create_app()
    with app.app_context():
        user = User.query.filter_by(phone=normalize_phone(PHONE)).first()
        if not user:
            user = User(phone=normalize_phone(PHONE),
                        password_hash="pbkdf2:sha256:260000$test$hash", name="الهام")
            db.session.add(user)
            db.session.commit()
        for a in Analysis.query.filter_by(user_id=user.id).all():
            db.session.delete(a)
        db.session.commit()
        a = Analysis(phone=normalize_phone(PHONE), user_id=user.id, type="hair",
                     photo_path="analysis/",
                     consultant_chat_history=json.dumps([
                         {"role": "user", "content": "سلام موهام خشکه"},
                         {"role": "assistant", "content": "سلام الهام عزیز، برنامه مناسب"},
                     ]),
                     consultant_key_notes="خلاصه گفتگو",
                     chat_rating=5)
        db.session.add(a)
        db.session.commit()
        aid = a.id

        _upsert_giso_user(ADMIN_BID, phone=normalize_phone("09120000008"),
                          first_name="ادمین", contact_shared=True,
                          is_admin=True, pending_request=False)
        _upsert_giso_user(USER_BID, phone=normalize_phone(PHONE),
                          first_name="الهام", contact_shared=True,
                          is_admin=False, pending_request=False)
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
            conn.execute("DELETE FROM giso_admin_permissions WHERE admin_bale_id=?", (str(ADMIN_BID),))
            conn.commit()
    except Exception:
        pass


# ── ۱) باگ کیبورد ادمین محدود ──────────────────────────────
def test_admin_kb_fix():
    app, aid = _setup()
    try:
        # بدون user_id → همه گزینه‌ها (رفتار امن پیش‌فرض)
        kb_none = _admin_kb()
        flat_none = [b.text for row in kb_none.keyboard for b in row]
        assert "📊 پیشخوان" in flat_none
        assert "🔬 آنالیز" in flat_none

        # ادمین معمولی: نقش عملیاتی ثابت
        kb_lim = _admin_kb(ADMIN_BID)
        flat_lim = [b.text for row in kb_lim.keyboard for b in row]
        assert flat_lim == ["💇 خرید مو", "🛍 فروشگاه", "🏪 بازارچه", "💬 مدیریت گفتگوها"]

        # سوپرادمین → همه گزینه‌ها
        kb_super = _admin_kb(SUPER_BID)
        flat_super = [b.text for row in kb_super.keyboard for b in row]
        for opt in ("📊 پیشخوان", "🔬 آنالیز", "🛍 فروشگاه", "🛠 مدیریت"):
            assert opt in flat_super
        print("PASS  باگ کیبورد ادمین محدود رفع شد (بدون user_id همه گزینه‌ها + محدود فیلتر + سوپر همه)")
    finally:
        _cleanup(app)


# ── ۲) خلاصه گفتگو → گفتگوی کامل ───────────────────────────
def test_chat_summaries_coalesce():
    app, aid = _setup()
    try:
        summaries = _get_chat_summaries(filter_type='all', limit=10)
        assert isinstance(summaries, list)
        assert any(s['id'] == aid for s in summaries)
        found = [s for s in summaries if s['id'] == aid][0]
        assert found['user_name'] == 'الهام', f"کاربر ناشناس/نام درست نیست: {found['user_name']}"
        assert found['message_count'] == 2
        assert found['summary'] == 'خلاصه گفتگو'
        print("PASS  خلاصه گفتگو با نام واقعی کاربر (COALESCE) + تعداد پیام")
    finally:
        _cleanup(app)


async def _run_chat_view():
    funcs = await get_test_handlers()
    handle_callback = funcs["handle_callback"]
    with get_giso_db_conn() as conn:
        aid = conn.execute("SELECT id FROM analyses ORDER BY id DESC LIMIT 1").fetchone()[0]

    cb = MagicMock()
    cb.data = f"adm_chat_view_{aid}"
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
    assert "گفتگوی کامل" in txt[0]
    assert "الهام" in txt[0]
    assert "سلام موهام خشکه" in txt[0]  # پیام کاربر
    assert "برنامه مناسب" in txt[0]     # پاسخ مشاور
    labels = [b.text for row in kwargs["reply_markup"].inline_keyboard for b in row]
    assert "🔙 بازگشت" in labels


def test_chat_view_callback():
    app, aid = _setup()
    try:
        asyncio.run(_run_chat_view())
        print("PASS  مشاهده گفتگوی کامل مشاور (adm_chat_view_)")
    finally:
        _cleanup(app)

# ── ۴) چیدمان بررسی عکس ───────────────────────────────────
def test_image_checks_layout():
    # در JS تابع displayImageChecks نباید دکمه وسط (action-buttons) تولید کند
    import re
    for tpl in ("analysis_hair.html", "analysis_skin.html"):
        path = os.path.join(BASE_DIR, "giso", "templates", tpl)
        html = open(path, encoding="utf-8").read()
        # در JS displayImageChecks نباید action-buttons وسط وجود داشته باشد
        # (بخش JS بین <script> آخر)
        scripts = re.findall(r"<script>([\s\S]*?)</script>", html)
        js = " ".join(scripts)
        d_func = js[js.index("function displayImageChecks"):js.index("function displayImageChecks")+3000]
        assert "action-buttons" not in d_func, f"{tpl}: دکمه وسط در displayImageChecks یافت شد"
        # دکمه‌های پایین (check-actions) باید موجود باشند
        assert "check-actions" in html
        assert "resetUpload()" in html
        assert "proceedToInitial()" in html
        # عنوان + نکات
        assert "status-warning" in html
        assert "status-title" in html
    print("PASS  چیدمان بررسی عکس درست شد (بدون دکمه وسط، فقط دکمه‌های پایین)")

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
