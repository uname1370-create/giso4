#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
تست رفع فوری گروه A (۳ مشکل) در ربات گیسو

۱) تنظیم آدرس سایت گیسو (_get_giso_site_url / _set_giso_site_url / _test_giso_site_url)
۲) نمایش درست مشخصات کاربر در «۱۰ تحلیل آخر» (_get_recent_analyses + helpers)
۳) مخفی کردن گزینه‌های بدون دسترسی برای ادمین‌های محدود (_admin_kb)
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
    _get_giso_site_url, _set_giso_site_url, _test_giso_site_url,
    _get_recent_analyses, _format_persian_date, _extract_analysis_topic,
    _extract_analysis_score, _admin_kb,
    get_test_handlers, DEFAULT_SITE_BASE_URL,
)  # noqa: E402

PHONE = "09190000999"
ADMIN_BID = 666001
LIMITED_BID = 666002
SUPER_BID = 1191639507


def _setup_db():
    app = create_app()
    with app.app_context():
        user = User.query.filter_by(phone=normalize_phone(PHONE)).first()
        if not user:
            user = User(phone=normalize_phone(PHONE),
                        password_hash="pbkdf2:sha256:260000$test$hash", name="زهرا")
            db.session.add(user)
            db.session.commit()
        for a in Analysis.query.filter_by(user_id=user.id).all():
            db.session.delete(a)
        db.session.commit()
        a = Analysis(phone=normalize_phone(PHONE), user_id=user.id, type="hair",
                     photo_path="analysis/",
                     ai_report_json=json.dumps({
                         "overall_score": 78, "main_problems": ["ریزش مو"],
                         "overall_status": "خوب"}, ensure_ascii=False),
                     chat_rating=4)
        db.session.add(a)
        db.session.commit()

        from giso.base import _upsert_giso_user
        _upsert_giso_user(ADMIN_BID, phone=normalize_phone("09120000004"),
                          first_name="ادمین", contact_shared=True,
                          is_admin=True, pending_request=False)
        _upsert_giso_user(LIMITED_BID, phone=normalize_phone("09350000005"),
                          first_name="محدود", contact_shared=True,
                          is_admin=True, pending_request=False)
        _upsert_giso_user(SUPER_BID, phone="+989156012931",
                          first_name="سوپر", contact_shared=True,
                          is_admin=True, pending_request=False)
    return app


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
            for bid in (ADMIN_BID, LIMITED_BID, SUPER_BID):
                conn.execute("DELETE FROM giso_users WHERE bale_id=?", (str(bid),))
            conn.execute("DELETE FROM giso_admin_permissions WHERE admin_bale_id=?", (str(LIMITED_BID),))
            conn.execute("DELETE FROM giso_config WHERE key='site_base_url'")
            conn.commit()
    except Exception:
        pass


# ── ۱) تنظیم آدرس سایت ───────────────────────────────────────
def test_site_url():
    app = _setup_db()
    try:
        # پیش‌فرض
        assert _get_giso_site_url() == DEFAULT_SITE_BASE_URL

        # ست کردن
        ok, msg = _set_giso_site_url("https://giso.sadeghiai.ir/")
        assert ok is True, msg
        assert _get_giso_site_url() == "https://giso.sadeghiai.ir"

        # اعتبارسنجی: بدون http
        ok2, _ = _set_giso_site_url("giso.example.com")
        assert ok2 is False

        # اعتبارسنجی: خالی
        ok3, _ = _set_giso_site_url("   ")
        assert ok3 is False

        # تست آدرس (آدرس بی‌معنی → success False ولی ساختار درست)
        r = _test_giso_site_url("https://nonexistent-giso-test.invalid")
        assert isinstance(r, dict)
        assert 'success' in r and 'status_code' in r and 'message' in r

        # بازگشت به پیش‌فرض
        ok4, _ = _set_giso_site_url(DEFAULT_SITE_BASE_URL)
        assert ok4 is True
        assert _get_giso_site_url() == DEFAULT_SITE_BASE_URL
        print("PASS  تنظیم آدرس سایت (get/set/validation/test/reset)")
    finally:
        _cleanup(app)


# ── ۲) نمایش درست مشخصات در ۱۰ تحلیل آخر ─────────────────────
def test_recent_analyses():
    app = _setup_db()
    try:
        analyses = _get_recent_analyses(limit=10)
        assert analyses, "تحلیل‌ها باید پیدا شوند"
        a = analyses[0]
        assert a['user_name'] == 'زهرا'
        assert a['type'] == 'hair'
        assert 'ریزش مو' in a['topic']
        assert a['score'] == 78
        assert a['phone'] == normalize_phone(PHONE)

        # _extract_analysis_topic با داده‌های مختلف
        assert 'تحلیل مو' in _extract_analysis_topic('{"main_problems":["ریزش"]}', 'hair')
        assert _extract_analysis_topic(None, 'skin') == 'تحلیل صورت'
        assert _extract_analysis_topic('{"overall_status":"خوب"}', 'hair') == 'تحلیل مو - خوب'

        # _extract_analysis_score
        assert _extract_analysis_score('{"overall_score": 90}') == 90
        assert _extract_analysis_score('{}') is None
        assert _extract_analysis_score('{"score":"80"}') == 80

        # تاریخ فارسی
        from datetime import datetime, timedelta
        today = datetime.now().strftime('%Y-%m-%d')
        assert "امروز" in _format_persian_date(today + " 12:30")
        assert "دیروز" in _format_persian_date(
            (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d') + " 10:00")
        assert _format_persian_date('') == 'نامشخص'
        print("PASS  نمایش درست مشخصات کاربر در ۱۰ تحلیل آخر")
    finally:
        _cleanup(app)


# ── ۳) مخفی کردن گزینه‌های بدون دسترسی ───────────────────────
def test_admin_kb_permissions():
    app = _setup_db()
    try:
        super_flat = [btn.text for row in _admin_kb(SUPER_BID).keyboard for btn in row]
        assert "🛠 مدیریت" in super_flat
        assert "⚙️ تنظیمات سایت" in super_flat
        assert "🔬 آنالیز" in super_flat

        regular_flat = [btn.text for row in _admin_kb(LIMITED_BID).keyboard for btn in row]
        assert regular_flat == ["💇 خرید مو", "🛍 فروشگاه", "🏪 بازارچه", "💬 مدیریت گفتگوها"]
    finally:
        _cleanup(app)


# ── ADMIN_SECTIONS: دقیقاً ۱۱ بخش، بدون analysis_requests ──
def test_admin_sections():
    from giso.bot import _BOT_OPERATIONAL_SECTIONS
    assert _BOT_OPERATIONAL_SECTIONS == {
        "dashboard", "orders", "hair_sale", "analysis_management", "reviews", "products",
    }


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
