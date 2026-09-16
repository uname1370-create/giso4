#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
تست ساختار منوی فروش مو (فاز 3.2).

۱) منوی AI (سوپرادمین): «📊 گزارش وضعیت» → گزارش AI (نه گزارش کلی گیسو/فروش مو).
۲) منوی فروش مو: «📊 گزارش‌ها» → «📊 گزارش کلی» → گزارش خرید مو.
۳) منوی اصلی: «⭐ نظرات» (در منوی اصلی ادمین) دست‌نخورده.
۴) منوی فروش مو: گزینه «نظرات» حذف شده است.
۵) کد: منوی فروش مو دقیقاً ۵ گزینه است + منوی AI/اصلی دست‌نخورده.
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
from giso.bot import get_test_handlers  # noqa: E402

SUPER_BID = 1191639507


def _setup_db():
    app = create_app()
    _upsert_giso_user(SUPER_BID, phone="+989156012931", first_name="سوپر",
                      contact_shared=True, is_admin=True, pending_request=False)
    return app


def _cleanup():
    try:
        with get_giso_db_conn() as conn:
            conn.execute("DELETE FROM giso_users WHERE bale_id=?", (str(SUPER_BID),))
            conn.execute("DELETE FROM giso_admin_permissions WHERE admin_bale_id=?", (str(SUPER_BID),))
            conn.commit()
    except Exception:
        pass


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
    if msg.reply_text.called:
        args, kwargs = msg.reply_text.call_args
        return kwargs.get("reply_markup"), (args[0] if args else "")
    return None, ""


# ── ۱) منوی AI: «📊 گزارش وضعیت» → گزارش AI ────────────────
def test_ai_report_status_not_hijacked():
    app = _setup_db()
    try:
        async def run():
            funcs = await get_test_handlers()
            ht = funcs["handle_text"]
            kb, msg = await _send(ht, SUPER_BID, "📊 گزارش وضعیت")
            assert "گزارش وضعیت پروایدرها" in msg or "هیچ پروایدری" in msg, msg
            assert "گزارش کلی گیسو" not in msg, "گزارش کلی گیسو (فروش مو) به اشتباه آمد"
            assert "کل کاربران سایت" not in msg, "آمار فروش مو به اشتباه آمد"
        asyncio.run(run())
        print("PASS  تست ۱: منوی AI «📊 گزارش وضعیت» → گزارش AI (نه فروش مو)")
    finally:
        _cleanup()


# ── ۲) منوی فروش مو: «📊 گزارش‌ها» → «📊 گزارش کلی» → گزارش خرید مو ───
def test_hair_sale_report_new_name():
    app = _setup_db()
    try:
        async def run():
            funcs = await get_test_handlers()
            ht = funcs["handle_text"]
            await _send(ht, SUPER_BID, "💇 فروش مو")
            kb, msg = await _send(ht, SUPER_BID, "📊 گزارش‌ها")
            assert "گزارش‌های خرید مو" in msg, msg
            kb2, msg2 = await _send(ht, SUPER_BID, "📊 گزارش کلی")
            assert "گزارش کلی خرید مو" in msg2, msg2
            assert "کل درخواست‌ها" in msg2, msg2
            assert "وضعیت پورسانت" in msg2, msg2
        asyncio.run(run())
        print("PASS  تست ۲: منوی فروش مو «📊 گزارش‌ها» → گزارش کلی خرید مو")
    finally:
        _cleanup()


# ── ۳) منوی اصلی: «⭐ نظرات» ────────────────────────────────
def test_main_reviews_button():
    app = _setup_db()
    try:
        async def run():
            funcs = await get_test_handlers()
            ht = funcs["handle_text"]
            kb, _ = await _send(ht, SUPER_BID, "/start")
            flat = [b.text for row in kb.keyboard for b in row]
            assert "⭐ نظرات" in flat, "دکمه «⭐ نظرات» در منوی اصلی ادمین نیست"
        asyncio.run(run())
        print("PASS  تست ۳: منوی اصلی «⭐ نظرات» دست‌نخورده است")
    finally:
        _cleanup()


# ── ۴) منوی فروش مو: منوی هوشمند جدید (فاز ۵ نهایی) ─────────
def test_hair_sale_reviews_removed():
    app = _setup_db()
    try:
        async def run():
            funcs = await get_test_handlers()
            ht = funcs["handle_text"]
            kb, _ = await _send(ht, SUPER_BID, "💇 فروش مو")
            flat = [b.text for row in kb.keyboard for b in row]
            assert "⭐ نظرات فروش مو" not in flat, "گزینه «⭐ نظرات فروش مو» هنوز در منوی فروش مو هست"
            assert "📊 گزارش فروش مو" not in flat, "گزینه «📊 گزارش فروش مو» هنوز در منوی فروش مو هست"
            assert "✅ تأیید سفارش" not in flat, "گزینه قدیمی «✅ تأیید سفارش» هنوز هست (منوی هوشمند جایگزین شد)"
            assert "❌ رد سفارش" not in flat, "گزینه قدیمی «❌ رد سفارش» هنوز هست (منوی هوشمند جایگزین شد)"
            assert "💰 ثبت قیمت نهایی" not in flat, "گزینه قدیمی «💰 ثبت قیمت نهایی» هنوز هست (منوی هوشمند جایگزین شد)"
            # گزینه‌های منوی هوشمند جدید (بدون «⚙️ تنظیم پورسانت» برای سوپر؟ سوپر دارد)
            for expected in ["📋 درخواست‌های فروش مو", "📱 ویرایش با شماره کاربر",
                             "👥 لیست کاربران فروش مو", "📊 گزارش‌ها", "💬 گفتگوها"]:
                assert expected in flat, f"گزینه «{expected}» در منوی هوشمند فروش مو نیست"
        asyncio.run(run())
        print("PASS  تست ۴: منوی هوشمند فروش مو (فاز ۵ نهایی) + حذف نظرات/منوی قدیمی")
    finally:
        _cleanup()


# ── ۵) کد: ساختار منوی هوشمند فروش مو + منوی AI/اصلی دست‌نخورده ───────
def test_source_renames():
    bot_src = open(os.path.join(BASE_DIR, "giso", "bot.py"), encoding="utf-8").read()
    # منوی هوشمند جدید فروش مو (گزینه‌ها در bot_hair_admin.py + هدایت گزینه‌های قدیمی)
    for btn in ['"📋 درخواست‌های فروش مو"', '"📱 ویرایش با شماره کاربر"', '"👥 لیست کاربران فروش مو"']:
        assert btn in bot_src, f"bot.py: {btn} نیست"
    # گزینه‌های قدیمی به منوی جدید هدایت می‌شوند (نه حذف بی‌صدا)
    assert '"✅ تأیید سفارش"' in bot_src, "هدایت گزینه قدیمی «✅ تأیید سفارش» نیست"
    assert '"❌ رد سفارش"' in bot_src, "هدایت گزینه قدیمی «❌ رد سفارش» نیست"
    assert '"💰 ثبت قیمت نهایی"' in bot_src, "هدایت گزینه قدیمی «💰 ثبت قیمت نهایی» نیست"
    # گزینه نظرات از منوی فروش مو حذف شده
    assert '"⭐ نظرات فروش مو"' not in bot_src, "گزینه نظرات هنوز در منوی فروش مو هست"
    # منوی AI (bot.py) دست‌نخورده: «📊 گزارش وضعیت» همان‌طور باقی است
    assert '"📊 گزارش وضعیت"' in bot_src, "منوی AI «📊 گزارش وضعیت» باید دست‌نخورده باشد"
    # منوی اصلی ادمین: «⭐ نظرات» دست‌نخورده
    assert '"⭐ نظرات"' in bot_src, "منوی اصلی «⭐ نظرات» باید دست‌نخورده باشد"
    print("PASS  کد: منوی هوشمند فروش مو + هدایت گزینه‌های قدیمی + منوی AI/اصلی دست‌نخورده")


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
