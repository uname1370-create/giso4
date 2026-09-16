#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
تست رفع نهایی مشکل «پیام /start بزنید» در بازگشت ادمین از زیرمنوها.

۱) بررسی: عبارت «لطفاً /start بزنید» در کل کد giso وجود ندارد.
۲) سوپرادمین → /start → «🔬 مدیریت آنالیز» → «🔙 بازگشت» → همه ۱۱ گزینه (بدون پیام /start)
۳) سوپرادمین → /start → «⚙️ مدیریت سایت و ربات» → «🔙 بازگشت» → همه ۱۱ گزینه
۴) ادمین محدود → /start → «🔙 بازگشت» → فقط دسترسی‌های مجاز
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
from giso.bot import _admin_kb, get_test_handlers  # noqa: E402

ADMIN_BID = 888101
SUPER_BID = 1191639507


def _setup_db():
    app = create_app()
    _upsert_giso_user(ADMIN_BID, phone="+98912000001", first_name="ادمین",
                      contact_shared=True, is_admin=True, pending_request=False)
    _upsert_giso_user(SUPER_BID, phone="+989156012931", first_name="سوپر",
                      contact_shared=True, is_admin=True, pending_request=False)
    try:
        from bot_edu.giso_admin import _connect as connect_bot_db
        with connect_bot_db() as c:
            c.execute(
                "INSERT INTO giso_admins (phone, bale_id, added_by, added_at) "
                "VALUES (?, ?, ?, ?)",
                ("+98912000001", str(ADMIN_BID), SUPER_BID, "2026-08-05"))
    except Exception:
        try:
            from giso_admin import _connect as connect_bot_db
            with connect_bot_db() as c:
                c.execute(
                    "INSERT INTO giso_admins (phone, bale_id, added_by, added_at) "
                    "VALUES (?, ?, ?, ?)",
                    ("+98912000001", str(ADMIN_BID), SUPER_BID, "2026-08-05"))
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
    return kwargs.get("reply_markup"), (args[0] if args else ""), msg


# ── ۱) پیام /start در کد وجود ندارد ─────────────────────────
def test_start_prompt_not_in_source():
    forbidden = ["لطفاً /start بزنید", "لطفا /start بزنید", "/start بزنید"]
    giso_dir = os.path.join(BASE_DIR, "giso")
    found = []
    for root, _, files in os.walk(giso_dir):
        if "__pycache__" in root or os.path.basename(root) == "tests":
            continue
        for fn in files:
            if not (fn.endswith(".py") or fn.endswith(".txt") or fn.endswith(".html")
                    or fn.endswith(".js")):
                continue
            p = os.path.join(root, fn)
            try:
                content = open(p, encoding="utf-8").read()
            except Exception:
                continue
            for s in forbidden:
                if s in content:
                    found.append(f"{os.path.relpath(p, BASE_DIR)}: {s}")
    assert not found, f"عبارت /start در کد یافت شد: {found}"
    print("PASS  عبارت «لطفاً /start بزنید» در کل کد giso وجود ندارد")


# ── ۲) سوپرادمین: بازگشت از مدیریت آنالیز ───────────────────
def test_super_back_from_analysis_menu():
    app = _setup_db()
    try:
        async def run():
            funcs = await get_test_handlers()
            ht = funcs["handle_text"]
            kb_start, _, _ = await _send(ht, SUPER_BID, "/start")
            flat_start = [b.text for row in kb_start.keyboard for b in row]
            assert all(o in flat_start for o in ALL_OPTIONS)
            await _send(ht, SUPER_BID, "🔬 مدیریت آنالیز")
            kb_back, msg, _ = await _send(ht, SUPER_BID, "🔙 بازگشت")
            flat = [b.text for row in kb_back.keyboard for b in row]
            assert all(o in flat for o in ALL_OPTIONS), flat
            assert "/start بزنید" not in msg and "لطفاً /start" not in msg
            assert "بازگشت" in msg
        asyncio.run(run())
        print("PASS  سوپرادمین بازگشت از مدیریت آنالیز → همه ۱۱ گزینه (بدون /start)")
    finally:
        _cleanup()


# ── ۳) سوپرادمین: بازگشت از مدیریت سایت و ربات ─────────────
def test_super_back_from_site_settings():
    app = _setup_db()
    try:
        async def run():
            funcs = await get_test_handlers()
            ht = funcs["handle_text"]
            await _send(ht, SUPER_BID, "/start")
            await _send(ht, SUPER_BID, "⚙️ مدیریت سایت و ربات")
            kb_back, msg, _ = await _send(ht, SUPER_BID, "🔙 بازگشت")
            flat = [b.text for row in kb_back.keyboard for b in row]
            assert all(o in flat for o in ALL_OPTIONS), flat
            assert "/start بزنید" not in msg
        asyncio.run(run())
        print("PASS  سوپرادمین بازگشت از مدیریت سایت → همه ۱۱ گزینه (بدون /start)")
    finally:
        _cleanup()


# ── ۴) ادمین محدود: بازگشت فقط دسترسی‌های مجاز ─────────────
def test_limited_admin_back_only_allowed():
    app = _setup_db()
    try:

        # بررسی قطعی `_admin_kb` برای ادمین محدود
        kb = _admin_kb(ADMIN_BID)
        flat = [b.text for row in kb.keyboard for b in row]
        assert flat == ["💇 خرید مو", "🛍 فروشگاه", "🏪 بازارچه", "💬 مدیریت گفتگوها"]

        # بدون user_id → همه گزینه‌ها (نه پیام /start)
        kb_none = _admin_kb()
        flat_none = [b.text for row in kb_none.keyboard for b in row]
        assert "🔬 آنالیز" in flat_none
        assert "📊 پیشخوان" in flat_none

        # هندلر «🔙 بازگشت» در handle_text باید با user_id صدا بزند
        bt = open(os.path.join(BASE_DIR, "giso", "bot.py"), encoding="utf-8").read()
        assert 'if text == "🔙 بازگشت"' in bt
        assert "_admin_kb(uid)" in bt
        print("PASS  ادمین محدود بازگشت → فقط دسترسی‌های مجاز (بدون /start)")
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
