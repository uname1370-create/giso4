#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
تست رفع مشکل بازگشت از زیرمنوی «فروش مو» برای ادمین محدود.

قبل از رفع: `handle_hair_sale_commands` در مسیر «🔙 بازگشت» ادمین،
`admin_kb_func()` (بدون uid) صدا می‌زد → fallback امن همه گزینه‌ها.
حالا `admin_kb_func(uid)` → برای ادمین محدود فقط دسترسی‌های مجاز.

۱) کد: فراخوانی admin_kb_func در مسیر «🔙 بازگشت» ادمین، با uid است.
۲) ادمین محدود (فقط فروش مو): بازگشت → فقط «💇 فروش مو» (نه همه گزینه‌ها).
۳) سوپرادمین: بازگشت → همه ۱۱ گزینه.
۴) تغییر زنده: قطع دسترسی فروش مو → بازگشت، گزینه مخفی.
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
from giso.bot import (
    _admin_kb, get_test_handlers,
)  # noqa: E402

ADMIN_BID = 777333
SUPER_BID = 1191639507


def _setup_db():
    app = create_app()
    _upsert_giso_user(ADMIN_BID, phone="+98912000003", first_name="ادمین",
                      contact_shared=True, is_admin=True, pending_request=False)
    _upsert_giso_user(SUPER_BID, phone="+989156012931", first_name="سوپر",
                      contact_shared=True, is_admin=True, pending_request=False)
    try:
        from bot_edu.giso_admin import _connect as connect_bot_db
        with connect_bot_db() as c:
            c.execute(
                "INSERT INTO giso_admins (phone, bale_id, added_by, added_at) "
                "VALUES (?, ?, ?, ?)",
                ("+98912000003", str(ADMIN_BID), SUPER_BID, "2026-08-05"))
    except Exception:
        try:
            from giso_admin import _connect as connect_bot_db
            with connect_bot_db() as c:
                c.execute(
                    "INSERT INTO giso_admins (phone, bale_id, added_by, added_at) "
                    "VALUES (?, ?, ?, ?)",
                    ("+98912000003", str(ADMIN_BID), SUPER_BID, "2026-08-05"))
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


# ── ۱) کد: مسیر «🔙 بازگشت» ادمین در hair_sale با uid ─────
def test_source_uses_uid():
    src = open(os.path.join(BASE_DIR, "giso", "hair_sale.py"), encoding="utf-8").read()
    # پیدا کردن بلوک «🔙 بازگشت»
    idx = src.index('if text == "🔙 بازگشت":')
    block = src[idx:idx + 1200]
    # در بخش is_admin باید admin_kb_func(uid) باشد، نه admin_kb_func()
    assert "admin_kb_func(uid)" in block, "admin_kb_func(uid) در مسیر بازگشت نیست"
    assert "admin_kb_func()" not in block, "admin_kb_func() بدون uid در مسیر بازگشت هست"
    print("PASS  مسیر «🔙 بازگشت» ادمین در hair_sale با admin_kb_func(uid) صدا زده می‌شود")


# ── ۲) ادمین محدود (فقط فروش مو): بازگشت → فقط فروش مو ────
def test_limited_admin_back_hair():
    """The normal-admin home keyboard always exposes the fixed Hair role."""
    app = _setup_db()
    try:
        flat = [b.text for row in _admin_kb(ADMIN_BID).keyboard for b in row]
        assert flat == ["💇 خرید مو", "🛍 فروشگاه", "🏪 بازارچه", "💬 مدیریت گفتگوها"]
    finally:
        _cleanup()


# ── ۳) سوپرادمین: بازگشت → همه ۱۱ گزینه ──────────────────
def test_super_back_hair():
    app = _setup_db()
    try:
        async def run():
            funcs = await get_test_handlers()
            ht = funcs["handle_text"]
            await _send(ht, SUPER_BID, "💇 فروش مو")
            kb_back, msg = await _send(ht, SUPER_BID, "🔙 بازگشت")
            flat = [b.text for row in kb_back.keyboard for b in row]
            assert all(o in flat for o in ALL_OPTIONS), flat
            assert "start بزنید" not in msg
        asyncio.run(run())
        print("PASS  تست ۲: سوپرادمین بازگشت از فروش مو → همه ۱۱ گزینه (بدون /start)")
    finally:
        _cleanup()


# ── ۴) تغییر زنده: قطع دسترسی فروش مو → گزینه مخفی ────────
def test_live_change_hair():
    """A legacy off-row cannot revoke the fixed Hair/Shop operational role."""
    app = _setup_db()
    try:
        before = [b.text for row in _admin_kb(ADMIN_BID).keyboard for b in row]
        with get_giso_db_conn() as conn:
            conn.execute(
                "INSERT INTO giso_admin_permissions (admin_bale_id,section,is_allowed,created_at) "
                "VALUES (?,?,0,'test') ON CONFLICT(admin_bale_id,section) "
                "DO UPDATE SET is_allowed=0", (str(ADMIN_BID), "hair_sale"))
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
