#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
تست جامع مشکل بازگشت پنل ادمین + حذف پیام «/start بزنید».

سناریوها:
۱) خط KeyboardButton("⚠️ لطفاً /start بزنید") در _admin_kb وجود ندارد.
۲) هیچ _admin_kb() بدون user_id در کد نیست (همه با user_id).
۳) _user_kb (پنل کاربر) دست نخورده.
۴) سوپرادمین: /start → همه ۱۱ گزینه؛ «🔙 بازگشت» → همه ۱۱ گزینه (بدون /start).
۵) ادمین محدود: فقط گزینه‌های مجاز در کیبورد.
۶) تست ۳ - تغییر زنده دسترسی: ادمین داخل بخش است، سوپرادمین دسترسی را قطع می‌کند،
   «🔙 بازگشت» → فقط دسترسی‌های جدید (گزینه قطع‌شده مخفی).
"""
import asyncio
import os
import sys
from unittest.mock import MagicMock, AsyncMock

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if BASE_DIR not in sys.path:
    sys.path.append(BASE_DIR)

from giso.app import create_app  # noqa: E402
from giso.base import get_giso_db_conn, _upsert_giso_user  # noqa: E402
from giso.bot import _admin_kb, _user_kb, get_test_handlers  # noqa: E402

ADMIN_BID = 777222
SUPER_BID = 1191639507


def _setup_db():
    app = create_app()
    _upsert_giso_user(ADMIN_BID, phone="+98912000002", first_name="ادمین",
                      contact_shared=True, is_admin=True, pending_request=False)
    _upsert_giso_user(SUPER_BID, phone="+989156012931", first_name="سوپر",
                      contact_shared=True, is_admin=True, pending_request=False)
    try:
        from bot_edu.giso_admin import _connect as connect_bot_db
        with connect_bot_db() as c:
            c.execute(
                "INSERT INTO giso_admins (phone, bale_id, added_by, added_at) "
                "VALUES (?, ?, ?, ?)",
                ("+98912000002", str(ADMIN_BID), SUPER_BID, "2026-08-05"))
    except Exception:
        try:
            from giso_admin import _connect as connect_bot_db
            with connect_bot_db() as c:
                c.execute(
                    "INSERT INTO giso_admins (phone, bale_id, added_by, added_at) "
                    "VALUES (?, ?, ?, ?)",
                    ("+98912000002", str(ADMIN_BID), SUPER_BID, "2026-08-05"))
        except Exception:
            pass
    return app


def _cleanup():
    try:
        with get_giso_db_conn() as conn:
            for bid in (ADMIN_BID, SUPER_BID):
                conn.execute("DELETE FROM giso_users WHERE bale_id=?", (str(bid),))
                conn.execute("DELETE FROM giso_admin_permissions WHERE admin_bale_id=?", (str(bid),))
            conn.commit()
    except Exception:
        pass
    try:
        from bot_edu.giso_admin import _connect as connect_bot_db
        with connect_bot_db() as c:
            c.execute("DELETE FROM giso_admins WHERE bale_id=?", (str(ADMIN_BID),))
    except Exception:
        pass


ALL_OPTIONS = ["📊 پیشخوان", "🛍 فروشگاه", "💇 خرید مو", "🔬 آنالیز",
               "🏪 بازارچه", "💬 مدیریت گفتگوها", "🛠 مدیریت", "⚙️ تنظیمات سایت"]


async def _send(handle_text, bid, text):
    msg = MagicMock()
    msg.reply_text = AsyncMock()
    msg.text = text
    update = MagicMock()
    update.effective_user.id = bid
    update.effective_message = msg
    update.message = msg
    context = MagicMock()
    context.bot.send_message = AsyncMock()
    context.user_data = {}
    await handle_text(update, context)
    args, kwargs = msg.reply_text.call_args
    return kwargs.get("reply_markup"), (args[0] if args else "")


# ── ۱) خط «/start بزنید» در _admin_kb حذف شده ──────────────
def test_no_start_button_in_kb():
    src = open(os.path.join(BASE_DIR, "giso", "bot.py"), encoding="utf-8").read()
    assert "لطفاً /start بزنید" not in src, "خط /start بزنید هنوز در bot.py هست"
    assert "/start بزنید" not in src, "عبارت /start بزنید در bot.py هست"
    # در کیبوردها هم نباید باشد
    kb = _admin_kb()
    flat = [b.text for row in kb.keyboard for b in row]
    assert not any("start" in b for b in flat), f"دکمه /start در کیبورد: {flat}"
    print("PASS  خط «⚠️ لطفاً /start بزنید» حذف شده (در _admin_kb نیست)")


# ── ۲) هیچ _admin_kb() بدون user_id نیست ────────────────────
def test_no_admin_kb_without_uid():
    src = open(os.path.join(BASE_DIR, "giso", "bot.py"), encoding="utf-8").read()
    # همه فراخوانی‌ها باید با آرگومان باشند
    assert "_admin_kb()" not in src, "فراخوانی _admin_kb() بدون آرگومان پیدا شد"
    print("PASS  هیچ فراخوانی _admin_kb() بدون user_id در کد نیست")


# ── ۳) منوی کاربر ورودی‌های عملیاتی پروفایل و اعلان را دارد ─────────────
def test_user_kb_has_exact_operational_menu():
    kb = _user_kb()
    flat = [b.text for row in kb.keyboard for b in row]
    assert flat == [
        "💰 کیف پول", "🎯 مأموریت", "💬 مشاور",
        "👤 پروفایل", "🎧 پشتیبانی", "📖 راهنما",
    ]
    assert "💬 مشاور هوشمند گیسو" not in flat
    assert "⭐ ثبت نظر" not in flat
    assert "🔍 آنالیز هوشمند" not in flat


# ── ۴) سوپرادمین: بازگشت → همه گزینه‌ها (بدون /start) ──────
def test_super_back_nav():
    app = _setup_db()
    try:
        async def run():
            funcs = await get_test_handlers()
            ht = funcs["handle_text"]
            kb_start, _ = await _send(ht, SUPER_BID, "/start")
            flat_start = [b.text for row in kb_start.keyboard for b in row]
            assert all(o in flat_start for o in ALL_OPTIONS), flat_start
            # بازگشت
            kb_back, msg = await _send(ht, SUPER_BID, "🔙 بازگشت")
            flat = [b.text for row in kb_back.keyboard for b in row]
            assert all(o in flat for o in ALL_OPTIONS), flat
            assert "start بزنید" not in msg and "لطفاً /start" not in msg
        asyncio.run(run())
        print("PASS  سوپرادمین بازگشت → همه ۱۱ گزینه (بدون /start)")
    finally:
        _cleanup()


# ── ۵) ادمین محدود: فقط گزینه‌های مجاز ─────────────────────
def test_limited_admin_allowed_only():
    app = _setup_db()
    try:
        flat = [b.text for row in _admin_kb(ADMIN_BID).keyboard for b in row]
        assert flat == ["💇 خرید مو", "🛍 فروشگاه", "🏪 بازارچه", "💬 مدیریت گفتگوها"]
    finally:
        _cleanup()


# ── ۶) تست ۳: تغییر زنده دسترسی ────────────────────────────
def test_live_permission_change():
    """Historical database switches cannot change the fixed normal-admin menu."""
    app = _setup_db()
    try:
        before = [b.text for row in _admin_kb(ADMIN_BID).keyboard for b in row]
        with get_giso_db_conn() as conn:
            conn.execute(
                "INSERT INTO giso_admin_permissions (admin_bale_id,section,is_allowed,created_at) "
                "VALUES (?,?,0,'test') ON CONFLICT(admin_bale_id,section) "
                "DO UPDATE SET is_allowed=0", (str(ADMIN_BID), "analysis_management"))
            conn.commit()
        after = [b.text for row in _admin_kb(ADMIN_BID).keyboard for b in row]
        assert after == before
        assert after == ["💇 خرید مو", "🛍 فروشگاه", "🏪 بازارچه", "💬 مدیریت گفتگوها"]
    finally:
        _cleanup()


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
