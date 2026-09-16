#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
تست فاز ۵ نهایی ربات — منوی هوشمند فروش مو ادمین + زیرگزینه‌های sub_options + هماهنگی با سایت

پوشش (مطابق تست‌های اجباری):
 ۱) ادمین معمولی فقط بخش‌های مجاز را می‌بیند (منو + دسترسی)
 ۲) سوپرادمین همه گزینه‌ها را می‌بیند (از جمله «⚙️ تنظیم پورسانت» در منوی فروش مو)
 ۳) لیست درخواست‌های فروش مو با تعداد
 ۴) اکشن‌های ۴ گانه هر درخواست کار می‌کنند (رد/قیمت/بررسی/گفتگو)
 ۵) ثبت قیمت → پیام فوری به کاربر
 ۶) گفتگو ادمین ↔ کاربر دوطرفه (hair_messages)
 ۷) ویرایش با شماره کاربر
 ۸) لیست کاربران فروش مو
 ۹) گزارش‌ها با پنل سایت هماهنگ‌اند (منبع داده مشترک)
۱۰) sub_options در ربات خوانده و اعمال می‌شود (منو + گارد callback)
۱۱) permission زنده بین سایت و ربات
۱۲) هوک‌های completed/reject کیف پول شکسته نشده‌اند
۱۳/۱۴) رگرسیون (فایل‌های تست قبلی جدا اجرا می‌شوند)
"""
import asyncio
import json
import os
import sys
import time
from unittest.mock import MagicMock, AsyncMock

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if BASE_DIR not in sys.path:
    sys.path.append(BASE_DIR)

from giso.app import create_app  # noqa: E402
from giso.base import get_giso_db_conn, _upsert_giso_user, normalize_phone, _fa_num  # noqa: E402

ADMIN_BID = 777331
ADMIN_PHONE = "+989120000031"   # فرمت نرمال‌شده (09120000031)
SUPER_BID = 1191639507
USER_BID = 777332
USER_PHONE = "+989120000032"    # فرمت نرمال‌شده (09120000032)

_FAILED = []


def _check(name, cond, extra=""):
    status = "PASS" if cond else "FAIL"
    print(f"{status}  {name}" + (f"  ({extra})" if extra else ""))
    if not cond:
        _FAILED.append(name)


def _setup_db():
    app = create_app()
    _upsert_giso_user(ADMIN_BID, phone=ADMIN_PHONE, first_name="ادمین تست",
                      contact_shared=True, is_admin=True, pending_request=False)
    _upsert_giso_user(SUPER_BID, phone="+989156012931", first_name="سوپر",
                      contact_shared=True, is_admin=True, pending_request=False)
    _upsert_giso_user(USER_BID, phone=USER_PHONE, first_name="کاربر تست",
                      contact_shared=True, is_admin=False, pending_request=False)
    try:
        from giso_admin import _connect as connect_bot_db
        with connect_bot_db() as c:
            c.execute("DELETE FROM giso_admins WHERE bale_id=? OR phone=?", (str(ADMIN_BID), ADMIN_PHONE))
            c.execute("INSERT INTO giso_admins (phone, bale_id, added_by, added_at) VALUES (?, ?, ?, ?)",
                      (ADMIN_PHONE, str(ADMIN_BID), SUPER_BID, time.strftime("%Y-%m-%d %H:%M:%S")))
    except Exception:
        pass
    return app


def _cleanup():
    try:
        with get_giso_db_conn() as conn:
            for bid in (str(ADMIN_BID), str(SUPER_BID), str(USER_BID)):
                conn.execute("DELETE FROM giso_users WHERE bale_id=?", (bid,))
            conn.execute("DELETE FROM hair_orders WHERE phone IN (?, ?)", (ADMIN_PHONE, USER_PHONE))
            conn.execute("DELETE FROM hair_messages WHERE order_id NOT IN (SELECT id FROM hair_orders)")
            conn.execute("DELETE FROM referrals WHERE referred_phone=? OR referred_phone=?",
                         (ADMIN_PHONE, USER_PHONE))
            conn.commit()
    except Exception:
        pass
    try:
        from giso_admin import _connect as connect_bot_db
        with connect_bot_db() as c:
            c.execute("DELETE FROM giso_admins WHERE bale_id=? OR phone=?", (str(ADMIN_BID), ADMIN_PHONE))
    except Exception:
        pass


def _add_order(phone=USER_PHONE, status="pending", final_price="", name="کاربر تست", length=30):
    with get_giso_db_conn() as conn:
        conn.execute(
            "INSERT INTO hair_orders (phone, customer_name, photo_path, length_cm, hair_type, hair_color, "
            "hair_weight, hair_health, estimated_price, final_price, status, created_at) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
            (phone, name, "", length, "نرم", "مشکی", "سبک", "خوب", "20,000,000", final_price, status,
             time.strftime("%Y-%m-%d %H:%M:%S")))
        oid = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        conn.commit()
    return oid


async def _send_text(ht, bid, text):
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
    await ht(update, context)
    calls = msg.reply_text.call_args_list
    texts = [c.args[0] if c.args else "" for c in calls]
    last_kb = calls[-1].kwargs.get("reply_markup") if calls else None
    return texts, last_kb, context


async def _send_cb(hc, bid, data):
    query = MagicMock()
    query.data = data
    query.answer = AsyncMock()
    query.message = MagicMock()
    query.message.reply_text = AsyncMock()
    query.message.text = "old"
    query.edit_message_text = AsyncMock()
    update = MagicMock()
    update.callback_query = query
    update.effective_user.id = bid
    context = MagicMock()
    context.bot.send_message = AsyncMock()
    context.user_data = {}
    await hc(update, context)
    return query, context


def _get_cb_texts(query):
    return [c.args[0] if c.args else "" for c in query.message.reply_text.call_args_list]


# ═══════════════════════════════════════════════════════════
def test_1_2_menus_admin_vs_super():
    """ادمین معمولی فقط مجازها؛ سوپرادمین همه گزینه‌ها (از جمله پورسانت در منوی فروش مو)."""
    _setup_db()
    try:
        async def run():
            funcs = await __import__("giso.bot", fromlist=["get_test_handlers"]).get_test_handlers()
            ht = funcs["handle_text"]
            # ورود ادمین محدود به فروش مو → منوی هوشمند (بدون گزارش/اعتراض؟ پیش‌فرض همه فعال)
            texts, kb, _ctx = await _send_text(ht, ADMIN_BID, "💇 فروش مو")
            flat = [b.text for row in kb.keyboard for b in row]
            _check("admin smart menu items", "📋 درخواست‌های فروش مو" in flat and "📱 ویرایش با شماره کاربر" in flat, str(flat))
            _check("admin menu has گزارش‌ها", "📊 گزارش‌ها" in flat)
            _check("admin menu NO پورسانت", "⚙️ تنظیم پورسانت" not in flat)
            # سوپرادمین → منوی هوشمند + پورسانت
            _texts2, kb2, _c2 = await _send_text(ht, SUPER_BID, "💇 فروش مو")
            flat2 = [b.text for row in kb2.keyboard for b in row]
            _check("super menu has پورسانت", "⚙️ تنظیم پورسانت" in flat2, str(flat2))
            # منوی اصلی ادمین محدود فقط فروش مو (سایر بخش‌ها مخفی)
            _texts3, kb3, _c3 = await _send_text(ht, ADMIN_BID, "🔙 بازگشت")
            flat3 = [b.text for row in kb3.keyboard for b in row]
            _check("limited admin main menu", "💇 فروش مو" in flat3 and "👑 مدیریت ادمین‌ها" not in flat3, str(flat3))
        asyncio.run(run())
    finally:
        _cleanup()


def test_3_4_request_list_and_4_actions():
    """لیست درخواست‌ها + ۴ اکشن: رد / قیمت / بررسی / گفتگو."""
    _setup_db()
    try:
        oid = _add_order(status="pending")

        async def run():
            funcs = await __import__("giso.bot", fromlist=["get_test_handlers"]).get_test_handlers()
            ht, hc = funcs["handle_text"], funcs["handle_callback"]

            # ۳) لیست درخواست‌ها
            texts, kb, _ = await _send_text(ht, ADMIN_BID, "📋 درخواست‌های فروش مو")
            joined = " | ".join(texts)
            _check("request list shows order", f"درخواست فروش مو #{_fa_num(oid)}" in joined, joined[:180])
            _check("request list tail", "قبلی/بعدی" in joined, joined[:160])

            # ۴-الف) در حال بررسی (hair_review)
            q, _c = await _send_cb(hc, ADMIN_BID, f"hair_review|{oid}")
            with get_giso_db_conn() as conn:
                st = conn.execute("SELECT status FROM hair_orders WHERE id=?", (oid,)).fetchone()[0]
            _check("review action -> reviewing", st == "reviewing", st)

            # ۴-ب) رد سفارش (hair_rej)
            q2, c2 = await _send_cb(hc, ADMIN_BID, f"hair_rej|{oid}")
            with get_giso_db_conn() as conn:
                st = conn.execute("SELECT status FROM hair_orders WHERE id=?", (oid,)).fetchone()[0]
            _check("reject action -> rejected", st == "rejected", st)
            _check("reject notified user", c2.bot.send_message.call_count > 0)

            # ۴-ج) ثبت قیمت (hair_price → state → متن)
            q3, c3 = await _send_cb(hc, ADMIN_BID, f"hair_price|{oid}")
            _check("price prompts admin", funcs["user_states"].get(ADMIN_BID, "").startswith("waiting_hair_price_"),
                   funcs["user_states"].get(str(ADMIN_BID), ""))
            texts4, kb4, c4 = await _send_text(ht, ADMIN_BID, "25 میلیون تومان")
            with get_giso_db_conn() as conn:
                row = conn.execute("SELECT final_price, status FROM hair_orders WHERE id=?", (oid,)).fetchone()
            _check("price saved", row[0] == "25 میلیون تومان" and row[1] == "priced", str(tuple(row)))
            _check("price notified user", c4.bot.send_message.call_count > 0, f"count={c4.bot.send_message.call_count}")

            # ۴-د) گفتگو (hair_msg → state → متن)
            q5, _c5 = await _send_cb(hc, ADMIN_BID, f"hair_msg|{oid}")
            _check("chat prompts admin", funcs["user_states"].get(ADMIN_BID, "").startswith("waiting_admin_msg_"))
            _texts6, _kb6, c6 = await _send_text(ht, ADMIN_BID, "سلام، عکس مو واضح‌تر بفرستید")
            with get_giso_db_conn() as conn:
                row = conn.execute(
                    "SELECT sender, message FROM hair_messages WHERE order_id=? ORDER BY id DESC LIMIT 1", (oid,)).fetchone()
            _check("chat message stored", row is not None and row[0] == "admin" and "سلام" in (row[1] or ""), str(row))
            _check("chat notified user", c6.bot.send_message.call_count > 0)
        asyncio.run(run())
    finally:
        _cleanup()


def test_5_6_price_notify_and_two_way_chat():
    """ثبت قیمت → پیام فوری کاربر؛ گفتگو دوطرفه (پاسخ کاربر → اعلان ادمین)."""
    _setup_db()
    try:
        oid = _add_order(status="pending")

        async def run():
            funcs = await __import__("giso.bot", fromlist=["get_test_handlers"]).get_test_handlers()
            ht, hc = funcs["handle_text"], funcs["handle_callback"]
            # ادمین قیمت ثبت می‌کند → پیام به کاربر (از طریق context.bot)
            await _send_cb(hc, ADMIN_BID, f"hair_price|{oid}")
            _t, _kb, c1 = await _send_text(ht, ADMIN_BID, "30 میلیون تومان")
            texts_user = [c.kwargs.get("text", "") or "" for c in c1.bot.send_message.call_args_list]
            _check("price notification contains price", any("30 میلیون تومان" in t for t in texts_user), str(texts_user)[:200])
            # کاربر پاسخ می‌دهد (state waiting_user_msg_reply_)
            funcs["user_states"][USER_BID] = f"waiting_user_msg_reply_{oid}"
            _t2, _kb2, c2 = await _send_text(ht, USER_BID, "ممنون، قیمت مناسبه")
            with get_giso_db_conn() as conn:
                row = conn.execute(
                    "SELECT sender, message FROM hair_messages WHERE order_id=? AND sender='user' ORDER BY id DESC LIMIT 1",
                    (oid,)).fetchone()
            _check("user reply stored", row is not None and row[1] == "ممنون، قیمت مناسبه", str(row))
            _check("admin notified of user reply", c2.bot.send_message.call_count > 0,
                   f"count={c2.bot.send_message.call_count}")
        asyncio.run(run())
    finally:
        _cleanup()


def test_7_8_phone_edit_and_user_list():
    """ویرایش با شماره کاربر + لیست کاربران فروش مو."""
    _setup_db()
    try:
        oid = _add_order(phone=USER_PHONE, status="pending")

        async def run():
            funcs = await __import__("giso.bot", fromlist=["get_test_handlers"]).get_test_handlers()
            ht = funcs["handle_text"]
            # ۷) ویرایش با شماره
            texts, kb, _ = await _send_text(ht, ADMIN_BID, "📱 ویرایش با شماره کاربر")
            _check("phone prompt", any("شماره موبایل کاربر" in t for t in texts), str(texts)[:100])
            _check("state set", funcs["user_states"].get(ADMIN_BID) == "hair_admin_phone")
            texts2, kb2, _c2 = await _send_text(ht, ADMIN_BID, "0912-0000-032")
            joined = " | ".join(texts2)
            _check("orders shown for phone", f"درخواست فروش مو #{_fa_num(oid)}" in joined, joined[:180])
            _check("back to menu after phone", any("منوی هوشمند" in t for t in texts2))
            # ۸) لیست کاربران
            texts3, kb3, _c3 = await _send_text(ht, ADMIN_BID, "👥 لیست کاربران فروش مو")
            joined3 = " | ".join(texts3)
            _check("user list shows phone", USER_PHONE in joined3, joined3[:150])
            _check("user list tail", "قبلی/بعدی" in joined3, joined3[:150])
        asyncio.run(run())
    finally:
        _cleanup()


def test_9_reports_aligned_with_panel():
    """گزارش ربات و پنل سایت از یک منبع داده — اعداد یکسان."""
    _setup_db()
    try:
        _add_order(status="completed", final_price="40,000,000")
        from giso.bot_reports import hair_sale_reports_text
        from giso.panel.modules.hair_sale import get_reports
        text = hair_sale_reports_text("sales")
        rep = get_reports()
        _check("panel sales matches", rep["total_sales"] >= 40000000, f"panel={rep['total_sales']}")
        from giso.base import _fa_num
        _check("bot report contains panel sales number", _fa_num(rep["total_sales"]) in text, text[:220])
        _check("bot report has title", "فروش کلی خرید مو" in text)
    finally:
        _cleanup()


def test_10_sub_options_applied_in_bot():
    """Legacy false sub-options cannot hide or block Hair operations."""
    _setup_db()
    try:
        oid = _add_order(status="pending")
        payload = json.dumps({"reject": "0", "reports": "0", "price": "0", "message": "0"})
        with get_giso_db_conn() as conn:
            conn.execute(
                "INSERT INTO giso_admin_permissions (admin_bale_id,section,is_allowed,sub_options,created_at) "
                "VALUES (?,?,0,?,?) ON CONFLICT(admin_bale_id,section) DO UPDATE SET "
                "is_allowed=0,sub_options=excluded.sub_options",
                (str(ADMIN_BID), "hair_sale", payload, time.strftime("%Y-%m-%d %H:%M:%S")))
            conn.commit()

        async def run():
            funcs = await __import__("giso.bot", fromlist=["get_test_handlers"]).get_test_handlers()
            ht, hc = funcs["handle_text"], funcs["handle_callback"]
            _t, kb, _ = await _send_text(ht, ADMIN_BID, "💇 فروش مو")
            flat = [b.text for row in kb.keyboard for b in row]
            _check("reports remain visible", "📊 گزارش‌ها" in flat, str(flat))
            q, _ctx = await _send_cb(hc, ADMIN_BID, f"hair_rej|{oid}")
            with get_giso_db_conn() as conn:
                status = conn.execute("SELECT status FROM hair_orders WHERE id=?", (oid,)).fetchone()[0]
            _check("reject remains operational", status == "rejected", status)
        asyncio.run(run())
    finally:
        _cleanup()


def test_11_live_permission_sync():
    """Stored permission rows are intentionally inert under the fixed role."""
    _setup_db()
    try:
        from giso.bot import _admin_kb
        from giso.bot_hair_admin import get_admin_sub_options
        before = [b.text for row in _admin_kb(ADMIN_BID).keyboard for b in row]
        with get_giso_db_conn() as conn:
            conn.execute(
                "INSERT INTO giso_admin_permissions (admin_bale_id,section,is_allowed,sub_options,created_at) "
                "VALUES (?,?,0,?,?) ON CONFLICT(admin_bale_id,section) DO UPDATE SET "
                "is_allowed=0,sub_options=excluded.sub_options",
                (str(ADMIN_BID), "products", json.dumps({"price": "0"}),
                 time.strftime("%Y-%m-%d %H:%M:%S")))
            conn.commit()
        after = [b.text for row in _admin_kb(ADMIN_BID).keyboard for b in row]
        _check("legacy row does not change fixed menu", after == before)
        _check("hair/shop remain operational", "💇 خرید مو" in after and "🛍 فروشگاه" in after)
        _check("Hair options remain enabled", all(get_admin_sub_options(str(ADMIN_BID)).values()))
    finally:
        _cleanup()


def test_12_wallet_hooks_not_broken():
    """هوک legacy سالم است اما پس از soft-deprecation اعتبار تازه ایجاد نمی‌کند."""
    app = _setup_db()
    try:
        from giso.referrals import register_referral, on_hair_order_status_change, get_wallet_balance
        with app.app_context():
            # یک معرف + یک کاربر معرفی‌شده + پورسانت در انتظار
            with get_giso_db_conn() as conn:
                conn.execute("DELETE FROM giso_web_auth WHERE phone IN ('+98912000041','+98912000042')")
                conn.execute("INSERT INTO giso_web_auth (phone, password_hash, name) VALUES ('+98912000041','h','معرف')")
                r1 = conn.execute("SELECT id FROM giso_web_auth WHERE phone='+98912000041'").fetchone()[0]
                conn.execute("INSERT INTO giso_web_auth (phone, password_hash, name) VALUES ('+98912000042','h','معرفی‌شده')")
                r2 = conn.execute("SELECT id FROM giso_web_auth WHERE phone='+98912000042'").fetchone()[0]
                conn.commit()
            register_referral(r1, r2, "TESTCODE99", "+98912000042")
            oid = _add_order(phone="+98912000042", status="completed", final_price="10,000,000")
            with get_giso_db_conn() as conn:
                conn.execute("UPDATE referrals SET status='hair_request_submitted', hair_order_id=? WHERE referred_user_id=?",
                             (oid, r2))
                conn.commit()
            # completed → رابطه برای ممیزی می‌ماند، ولی پورسانت Hair Sale جدید ممنوع است.
            ok = on_hair_order_status_change(oid, "completed")
            _check("completed hook ok", ok is not False)
            bal = get_wallet_balance(r1)
            _check("commission soft-deprecated", bal == 0, f"balance={bal}")
            # reject → بدون پورسانت (hook بدون خطا)
            oid2 = _add_order(phone="+98912000042", status="pending")
            ok2 = on_hair_order_status_change(oid2, "rejected")
            _check("reject hook ok", ok2 is not False)
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
            _FAILED.append(t.__name__)
        except Exception as e:  # noqa: BLE001
            print(f"ERROR {t.__name__}: {type(e).__name__}: {e}")
            _FAILED.append(t.__name__)
    total = len(tests)
    print(f"\n{passed}/{total} tests passed")
    if _FAILED:
        print("Failed:", ", ".join(_FAILED))
        return False
    return True


if __name__ == "__main__":
    sys.exit(0 if _run() else 1)
