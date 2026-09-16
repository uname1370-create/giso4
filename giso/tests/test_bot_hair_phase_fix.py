#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
تست فاز 5.1 ربات — اصلاح تجربه ادمین فروش مو در ربات + نمایش/عدم نمایش پورسانت در سایت

پوشش (مطابق تست‌های اجباری):
 ۱) نمایش درخواست‌ها تک‌به‌تک با عکس و شمارگر
 ۲) دکمه قبلی/بعدی درست کار می‌کند
 ۳) لیست کاربران فقط فعال‌ها + تعداد درخواست فعال
 ۴) کلیک روی کاربر → درخواست‌های او صفحه‌بندی‌شده
 ۵) اکشن‌های ثبت قیمت/رد/در حال بررسی/گفتگو کار می‌کنند
 ۶) هر اکشن پیام مناسب به کاربر می‌فرستد
 ۷) گزارش‌های «نمایش در حال بررسی» و «نمایش رد شده» صفحه‌بندی ۵تایی
 ۸) کلیک روی هر شماره → اطلاعات درخواست کاربر
 ۹) «اعتراض‌ها» → «گفتگوها» (گفتگوهای در جریان، جدیدترین بالا)
۱۰) گزینه سوم پورسانت «نمایش پورسانت در سایت» اضافه و toggle می‌شود
۱۱) سایت: فعال → پورسانت در کیف پول نمایش داده می‌شود
۱۲) سایت: غیرفعال → پورسانت مخفی می‌شود
۱۳) رگرسیون صفحات/منوها (فایل‌های قبلی جدا اجرا می‌شوند)
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
from giso.base import get_giso_db_conn, _upsert_giso_user, _fa_num  # noqa: E402

ADMIN_BID = 778001
ADMIN_PHONE = "+989120000031"
SUPER_BID = 1191639507
USER_BID = 778002
USER_BID2 = 778003
USER_PHONE = "+989120000032"
USER_PHONE2 = "+989120000033"

_CREATED_IDS = []

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
    _upsert_giso_user(USER_BID2, phone=USER_PHONE2, first_name="کاربر تست ۲",
                      contact_shared=True, is_admin=False, pending_request=False)
    try:
        from giso_admin import _connect as connect_bot_db
        with connect_bot_db() as c:
            c.execute("DELETE FROM giso_admins WHERE bale_id=? OR phone=?", (str(ADMIN_BID), ADMIN_PHONE))
            c.execute("INSERT INTO giso_admins (phone, bale_id, added_by, added_at) VALUES (?, ?, ?, ?)",
                      (ADMIN_PHONE, str(ADMIN_BID), SUPER_BID, time.strftime("%Y-%m-%d %H:%M:%S")))
    except Exception:
        pass
    with get_giso_db_conn() as conn:
        for sec in ("dashboard", "orders", "analysis_management", "reviews", "products",
                    "channel_management", "users", "admins", "site_bot_settings", "ai_management"):
            conn.execute(
                "INSERT INTO giso_admin_permissions (admin_bale_id, section, is_allowed, created_at) "
                "VALUES (?,?,?,?) ON CONFLICT(admin_bale_id, section) DO UPDATE SET is_allowed=excluded.is_allowed",
                (str(ADMIN_BID), sec, 0, time.strftime("%Y-%m-%d %H:%M:%S")))
        conn.execute(
            "INSERT INTO giso_admin_permissions (admin_bale_id, section, is_allowed, created_at) "
            "VALUES (?,?,?,?) ON CONFLICT(admin_bale_id, section) DO UPDATE SET is_allowed=excluded.is_allowed",
            (str(ADMIN_BID), "hair_sale", 1, time.strftime("%Y-%m-%d %H:%M:%S")))
        conn.commit()
    return app


def _cleanup():
    try:
        with get_giso_db_conn() as conn:
            for bid in (str(ADMIN_BID), str(SUPER_BID)):
                conn.execute("DELETE FROM giso_users WHERE bale_id=?", (bid,))
                conn.execute("DELETE FROM giso_admin_permissions WHERE admin_bale_id=?", (bid,))
            # دیتابیس تست سندباکس: حذف کامل سفارش‌ها/پیام‌های تست برای تعیین‌پذیری
            conn.execute("DELETE FROM hair_messages")
            conn.execute("DELETE FROM hair_orders")
            _CREATED_IDS.clear()
            conn.commit()
    except Exception:
        pass
    try:
        from giso_admin import _connect as connect_bot_db
        with connect_bot_db() as c:
            c.execute("DELETE FROM giso_admins WHERE bale_id=? OR phone=?", (str(ADMIN_BID), ADMIN_PHONE))
            c.execute("DELETE FROM giso_config WHERE key='referral_show_commission_site'")
            c.commit()
    except Exception:
        pass


def _add_order(phone=USER_PHONE, status="pending", final_price="", length=30, name="کاربر تست"):
    with get_giso_db_conn() as conn:
        conn.execute(
            "INSERT INTO hair_orders (phone, customer_name, photo_path, length_cm, hair_type, hair_color, "
            "hair_weight, hair_health, estimated_price, final_price, status, created_at) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
            (phone, name, "", length, "نرم", "مشکی", "سبک", "خوب", "20,000,000", final_price, status,
             time.strftime("%Y-%m-%d %H:%M:%S")))
        oid = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        conn.commit()
    _CREATED_IDS.append(int(oid))
    return oid


def _add_msg(order_id, sender, text):
    with get_giso_db_conn() as conn:
        conn.execute("INSERT INTO hair_messages (order_id, sender, message, is_read, created_at) "
                     "VALUES (?,?,?,0,?)", (order_id, sender, text, time.strftime("%Y-%m-%d %H:%M:%S")))
        conn.commit()


async def _send_text(ht, bid, text):
    msg = MagicMock()
    msg.reply_text = AsyncMock()
    msg.text = text
    msg.chat_id = bid
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
    query.message.chat_id = bid
    query.edit_message_text = AsyncMock()
    update = MagicMock()
    update.callback_query = query
    update.effective_user.id = bid
    context = MagicMock()
    context.bot.send_message = AsyncMock()
    context.user_data = {}
    await hc(update, context)
    return query, context


def _flat_kb(kb):
    try:
        return [b.text for row in kb.keyboard for b in row]
    except Exception:
        try:
            return [b.text for row in kb.inline_keyboard for b in row]
        except Exception:
            return []


def _cb_flat(kb):
    try:
        return [(b.text, b.callback_data) for row in kb.inline_keyboard for b in row]
    except Exception:
        return []


# ═══════════════════════════════════════════════════════════
def test_1_2_requests_paged_with_photo_and_nav():
    """نمایش تک‌به‌تک + شمارگر + قبلی/بعدی."""
    _setup_db()
    try:
        # o1 آخر ساخته می‌شود تا جدیدترین (اولین نمایش) باشد
        o2 = _add_order(phone=USER_PHONE2, status="reviewing")
        o1 = _add_order(phone=USER_PHONE, status="pending")

        async def run():
            funcs = await __import__("giso.bot", fromlist=["get_test_handlers"]).get_test_handlers()
            ht, hc = funcs["handle_text"], funcs["handle_callback"]
            # لیست درخواست‌ها → فقط درخواست اول (تک‌به‌تک) + شمارگر «۱ از ۲»
            texts, kb, _ = await _send_text(ht, ADMIN_BID, "📋 درخواست‌های فروش مو")
            joined = " | ".join(texts)
            _check("single request shown (not all)", joined.count("درخواست فروش مو") == 1, str(joined)[:200])
            _check("counter 1 of 2", "۱ از ۲" in joined, joined[:200])
            _check("order 1 shown first", f"درخواست فروش مو #{_fa_num(o1)}" in joined, joined[:220])
            # ناوبری: بعدی → درخواست دوم
            q, _c = await _send_cb(hc, ADMIN_BID, f"hair_pg|req|1")
            texts2 = [c.args[0] if c.args else "" for c in q.message.reply_text.call_args_list]
            joined2 = " | ".join(texts2)
            _check("next shows order 2", f"درخواست فروش مو #{_fa_num(o2)}" in joined2, joined2[:220])
            _check("counter 2 of 2", "۲ از ۲" in joined2, joined2[:200])
            # قبلی → برگشت به درخواست اول
            q2, _c2 = await _send_cb(hc, ADMIN_BID, "hair_pg|req|0")
            texts3 = [c.args[0] if c.args else "" for c in q2.message.reply_text.call_args_list]
            _check("prev returns to order 1", f"درخواست فروش مو #{_fa_num(o1)}" in " | ".join(texts3))
            # پیام پایان لیست وقتی هیچ درخواستی نیست
            with get_giso_db_conn() as conn:
                conn.execute("DELETE FROM hair_orders")
                conn.commit()
            texts4, kb4, _c4 = await _send_text(ht, ADMIN_BID, "📋 درخواست‌های فروش مو")
            _check("empty message when none", any("درخواست‌ها تمام شد" in t for t in texts4), str(texts4)[:120])
        asyncio.run(run())
    finally:
        _cleanup()


def test_3_4_users_active_only_with_counts_and_orders():
    """لیست کاربران فقط فعال‌ها + تعداد + ورود به درخواست‌ها."""
    _setup_db()
    try:
        # کاربر۲ اول ساخته می‌شود تا کاربر۱ (با ۲ درخواست فعال) جدیدترین باشد
        o2 = _add_order(phone=USER_PHONE2, status="pending")
        _add_order(phone=USER_PHONE, status="pending")
        _add_order(phone=USER_PHONE, status="reviewing")
        _add_order(phone=USER_PHONE, status="rejected")   # فعال نیست

        async def run():
            funcs = await __import__("giso.bot", fromlist=["get_test_handlers"]).get_test_handlers()
            ht, hc = funcs["handle_text"], funcs["handle_callback"]
            texts, kb, _ = await _send_text(ht, ADMIN_BID, "👥 لیست کاربران فروش مو")
            joined = " | ".join(texts)
            _check("user1 with 2 active", "۲ درخواست فعال" in joined, joined[:250])
            _check("user list counter 1 of 2", "۱ از ۲" in joined, joined[:250])
            # بعدی → کاربر دوم
            q, _c = await _send_cb(hc, ADMIN_BID, "hair_pg|usr|1")
            t2 = [c.args[0] if c.args else "" for c in q.message.reply_text.call_args_list]
            joined2 = " | ".join(t2)
            _check("next user shown", USER_PHONE2 in joined2 and "۱ درخواست فعال" in joined2, joined2[:250])
            # کلیک روی کاربر → درخواست‌های او
            q2, _c2 = await _send_cb(hc, ADMIN_BID, f"hair_pg|uo|{USER_PHONE2}|0")
            t3 = [c.args[0] if c.args else "" for c in q2.message.reply_text.call_args_list]
            joined3 = " | ".join(t3)
            _check("user orders shown", f"درخواست فروش مو #{_fa_num(o2)}" in joined3, joined3[:220])
            _check("user orders counter", "۱ از ۱" in joined3, joined3[:200])
        asyncio.run(run())
    finally:
        _cleanup()


def test_5_6_actions_and_user_messages():
    """اکشن‌های ۴ گانه کار می‌کنند و هرکدام پیام مناسب به کاربر می‌فرستند."""
    _setup_db()
    try:
        oid = _add_order(status="pending")

        async def run():
            funcs = await __import__("giso.bot", fromlist=["get_test_handlers"]).get_test_handlers()
            ht, hc = funcs["handle_text"], funcs["handle_callback"]
            # در حال بررسی
            q, c = await _send_cb(hc, ADMIN_BID, f"hair_review|{oid}")
            with get_giso_db_conn() as conn:
                st = conn.execute("SELECT status FROM hair_orders WHERE id=?", (oid,)).fetchone()[0]
            _check("review -> reviewing", st == "reviewing", st)
            _check("review notified user", c.bot.send_message.call_count > 0)
            # ثبت قیمت → پیام فوری
            await _send_cb(hc, ADMIN_BID, f"hair_price|{oid}")
            _t, _kb, c2 = await _send_text(ht, ADMIN_BID, "25 میلیون تومان")
            with get_giso_db_conn() as conn:
                row = conn.execute("SELECT final_price, status FROM hair_orders WHERE id=?", (oid,)).fetchone()
            _check("price saved", row[0] == "25 میلیون تومان" and row[1] == "priced")
            user_texts = [c.kwargs.get("text", "") or "" for c in c2.bot.send_message.call_args_list]
            _check("price notified user with price", any("25 میلیون تومان" in t for t in user_texts), str(user_texts)[:160])
            # گفتگو
            await _send_cb(hc, ADMIN_BID, f"hair_msg|{oid}")
            _t2, _kb2, c3 = await _send_text(ht, ADMIN_BID, "سلام، عکس بهتری بفرستید")
            with get_giso_db_conn() as conn:
                row = conn.execute("SELECT sender, message FROM hair_messages WHERE order_id=? ORDER BY id DESC LIMIT 1", (oid,)).fetchone()
            _check("chat stored", row is not None and row[0] == "admin", str(row))
            _check("chat notified user", c3.bot.send_message.call_count > 0)
            # رد سفارش → پیام مؤدبانه
            q4, c4 = await _send_cb(hc, ADMIN_BID, f"hair_rej|{oid}")
            with get_giso_db_conn() as conn:
                st = conn.execute("SELECT status FROM hair_orders WHERE id=?", (oid,)).fetchone()[0]
            _check("reject -> rejected", st == "rejected", st)
            _check("reject notified user", c4.bot.send_message.call_count > 0)
        asyncio.run(run())
    finally:
        _cleanup()


def test_7_8_reports_paged_and_phone_view():
    """گزارش‌های «نمایش در حال بررسی/رد شده»: شمار کلی + شماره‌های ۵تایی + کلیک روی شماره."""
    _setup_db()
    try:
        # ۶ درخواست در حال بررسی (برای صفحه‌بندی ۵تایی)
        ids = []
        for i in range(6):
            ids.append(_add_order(status="reviewing", phone=USER_PHONE if i % 2 == 0 else USER_PHONE2))
        _add_order(status="rejected", phone=USER_PHONE)

        async def run():
            funcs = await __import__("giso.bot", fromlist=["get_test_handlers"]).get_test_handlers()
            ht, hc = funcs["handle_text"], funcs["handle_callback"]
            # ورود به گزارش‌ها
            _t, kb, _c = await _send_text(ht, ADMIN_BID, "📊 گزارش‌ها")
            flat = _flat_kb(kb)
            _check("reports menu new labels", "🔍 نمایش در حال بررسی" in flat and "❌ نمایش رد شده" in flat, str(flat))
            # نمایش در حال بررسی → شمار کلی ۲ (۲ کاربر) + شماره‌ها
            texts, kb2, _c2 = await _send_text(ht, ADMIN_BID, "🔍 نمایش در حال بررسی")
            joined = " | ".join(texts)
            _check("report total count", "شمار کلی:" in joined and "۲" in joined, joined[:200])
            cbs = _cb_flat(kb2)
            _check("phones listed", any("📱" in t for t, _ in cbs), str(cbs)[:200])
            # کلیک روی شماره → درخواست همان کاربر
            phone_btn = [cb for t, cb in cbs if t.startswith("📱")][0]
            q, _c3 = await _send_cb(hc, ADMIN_BID, phone_btn)
            t2 = [c.args[0] if c.args else "" for c in q.message.reply_text.call_args_list]
            joined2 = " | ".join(t2)
            _check("phone view shows order card", "درخواست فروش مو" in joined2, joined2[:200])
            _check("phone view counter", "۱ از" in joined2, joined2[:200])
            # نمایش رد شده → ۱ شماره
            texts3, kb3, _c4 = await _send_text(ht, ADMIN_BID, "❌ نمایش رد شده")
            joined3 = " | ".join(texts3)
            _check("rejected report total", "شمار کلی:" in joined3 and "۱" in joined3, joined3[:200])
        asyncio.run(run())
    finally:
        _cleanup()


def test_9_conversations_replaces_objections():
    """«اعتراض‌ها» → «گفتگوها»: گفتگوهای در جریان جدیدترین بالا."""
    _setup_db()
    try:
        o1 = _add_order(status="reviewing", phone=USER_PHONE)
        o2 = _add_order(status="pending", phone=USER_PHONE2)
        _add_msg(o1, "user", "اولین پیام کاربر ۱")
        _add_msg(o2, "user", "پیام کاربر ۲")

        async def run():
            funcs = await __import__("giso.bot", fromlist=["get_test_handlers"]).get_test_handlers()
            ht = funcs["handle_text"]
            texts, kb, _ = await _send_text(ht, ADMIN_BID, "💬 گفتگوها")
            joined = " | ".join(texts)
            _check("conversations label", "گفتگوهای در جریان" in joined, joined[:200])
            _check("conversation 2 first (newest)", joined.find(f"گفتگو #{_fa_num(o2)}") < joined.find(f"گفتگو #{_fa_num(o1)}"),
                   joined[:250])
            _check("reply button per conversation", "پاسخ" in joined)
        asyncio.run(run())
    finally:
        _cleanup()


def test_10_commission_third_option():
    """گزینه سوم «نمایش پورسانت در سایت» + toggle در giso_config."""
    _setup_db()
    try:
        async def run():
            funcs = await __import__("giso.bot", fromlist=["get_test_handlers"]).get_test_handlers()
            ht = funcs["handle_text"]
            # سوپر → منوی پورسانت شامل گزینه سوم
            _t, kb, _c = await _send_text(ht, SUPER_BID, "⚙️ تنظیم پورسانت")
            flat = _flat_kb(kb)
            _check("commission menu keeps options", "درصدی" in flat and "مبلغ ثابت" in flat, str(flat))
            _check("third option present", "🌐 نمایش پورسانت در سایت" in flat, str(flat))
            # toggle (پیش‌فرض: فعال)
            from giso.referrals import get_show_commission_site
            _check("default show", get_show_commission_site() is True)
            texts, kb2, _c2 = await _send_text(ht, SUPER_BID, "🌐 نمایش پورسانت در سایت")
            _check("toggle reply", any("غیرفعال" in t for t in texts), str(texts)[:160])
            _check("stored off", get_show_commission_site() is False)
            texts2, _kb3, _c3 = await _send_text(ht, SUPER_BID, "🌐 نمایش پورسانت در سایت")
            _check("toggle back on", get_show_commission_site() is True)
            # ادمین معمولی نمی‌تواند
            texts3, _kb4, _c4 = await _send_text(ht, ADMIN_BID, "🌐 نمایش پورسانت در سایت")
            _check("non-super blocked", any("فقط سوپرادمین" in t for t in texts3))
        asyncio.run(run())
    finally:
        _cleanup()


def test_11_12_site_wallet_show_hide():
    """UI پورسانت Hair Sale soft-deprecated و کیف پول واحد همیشه نمایش داده می‌شود."""
    from giso.referrals import set_show_commission_site
    app = create_app()
    client = app.test_client()
    _cleanup()
    from giso.models import db, User
    from giso.base import normalize_phone
    USER_SITE = normalize_phone("09127778888")
    with app.app_context():
        User.query.filter(User.phone == USER_SITE).delete()
        db.session.commit()
        u = User(phone=USER_SITE, password_hash="h", name="کاربر سایت")
        db.session.add(u)
        db.session.commit()
    with client.session_transaction() as session:
        session["_user_id"] = USER_SITE

    for flag in (True, False):
        set_show_commission_site(flag)  # کلید قدیمی نباید UI مالی جدید را تغییر دهد.
        response = client.get("/dashboard/wallet")
        _check("wallet page 200", response.status_code == 200, f"status={response.status_code}")
        html = response.get_data(as_text=True)
        _check("legacy commission hidden", "پورسانت این ماه" not in html and "دعوت دوستان" not in html)
        _check("unified balances visible", "موجودی نقدی" in html and "اعتبار مصرفی" in html)
        _check("four wallet tabs", all(label in html for label in ("خلاصه", "ماموریت‌های من", "افزایش موجودی", "تسویه")))
    with app.app_context():
        User.query.filter(User.phone == USER_SITE).delete()
        db.session.commit()
    set_show_commission_site(True)


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
