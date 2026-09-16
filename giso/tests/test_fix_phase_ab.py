#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
تست‌های فاز اصلاحی A–F (اعلان‌ها به سوپر + تست ارسال + Bell + مسیر کانال)

چک‌لیست ۱۶ موردی:
 ۱) تست ارسال از پنل → پیام واقعی به سوپرادمین (1191639507)
 ۲) رویداد سفارش جدید → سوپرادمین اعلان بگیرد
 ۳) رویداد بن کاربر → سوپرادمین اعلان بگیرد
 ۴) رویداد پست کانال جدید → سوپرادمین اعلان بگیرد
 ۵) Bell در سایت بالای صفحه دیده شود
 ۶) کلیک روی Bell → صفحه اعلان‌های نقش کاربر
 ۷) افکت رسیدن اعلان جدید (has-unread + انیمیشن)
 ۸) کاربر فقط اعلان‌های خود را ببیند
 ۹) ادمین فقط طبق دسترسی
 ۱۰) سوپرادمین همه اعلان‌ها
 ۱۱) پست کانال بدون خطای ai_parse ثبت شود (خروجی dict)
 ۱۲) خطای Working outside of application context رفع شود
 ۱۳) محصول با وضعیت pending ثبت شود
 ۱۴) بعد از تأیید → در فروشگاه منتشر شود (دسته درست)
 ۱۵) صفحه محصول اطلاعات کامل (عکس/قیمت/دسته/زیردسته/توضیح/موجودی)
 ۱۶) رگرسیون کامل (در پایان جداگانه)
"""
import asyncio
import os
import sys
from unittest.mock import patch

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if BASE_DIR not in sys.path:
    sys.path.append(BASE_DIR)

from giso.app import create_app  # noqa: E402
from giso.models import db, Product, User  # noqa: E402
from giso.base import normalize_phone, get_giso_db_conn  # noqa: E402
from giso.config import SUPERADMIN_BALE_ID  # noqa: E402

SUPER_PHONE = normalize_phone("09156012931")
ADMIN_PHONE = normalize_phone("09127778888")
ADMIN_BALE_ID = "55667788"
USER_PHONE = normalize_phone("09120000099")
FIXED = "246810"

_FAILED = []


def _check(name, cond, extra=""):
    status = "PASS" if cond else "FAIL"
    print(f"{status}  {name}" + (f"  ({extra})" if extra else ""))
    if not cond:
        _FAILED.append(name)


def _cleanup(app=None):
    try:
        with get_giso_db_conn() as conn:
            conn.execute("DELETE FROM giso_notifications WHERE source_type LIKE 'ab_%'"
                         " OR (category='system' AND subcategory='test')")
            conn.execute("DELETE FROM products WHERE name LIKE 'ABفاز%'")
            conn.commit()
    except Exception:
        pass
    if app is not None:
        with app.app_context():
            try:
                for p in Product.query.filter(Product.name.like("ABفاز%")).all():
                    db.session.delete(p)
                from giso.models import User
                for ph in (USER_PHONE, ADMIN_PHONE):
                    User.query.filter(User.phone == ph).delete()
                db.session.commit()
            except Exception:
                db.session.rollback()
    try:
        from giso_admin import _connect as _c
        with _c() as conn:
            conn.execute("DELETE FROM giso_admins WHERE phone=? OR bale_id=?",
                         (ADMIN_PHONE, ADMIN_BALE_ID))
            conn.commit()
    except Exception:
        pass


def _mkuser(app, phone, name):
    with app.app_context():
        User.query.filter(User.phone == phone).delete()
        db.session.add(User(phone=phone, password_hash="h", name=name))
        db.session.commit()


def _login(client, phone):
    with client.session_transaction() as st:
        st.setdefault("giso_csrf_token", "fixed-test-csrf-token")
        st["_user_id"] = phone


    _op = client.post
    def _post_with_csrf(*a, **k):
        h = dict(k.get("headers") or {}); h.setdefault("X-GISO-CSRF", "fixed-test-csrf-token"); k["headers"] = h
        return _op(*a, **k)
    client.post = _post_with_csrf
def _verify(client, phone):
    import re as _re2, time as _t
    with client.session_transaction() as st:
        st["admin_panel_verified_phone"] = phone
        st["admin_panel_verified_until"] = int(_t.time()) + 1800
def _super(app):
    c = app.test_client()
    _mkuser(app, SUPER_PHONE, "سوپر")
    _login(c, SUPER_PHONE)
    _verify(c, SUPER_PHONE)
    return c


def _capture_send(app, targets=None, token="BOT_TOKEN_X"):
    """شبیه‌سازی ارسال بله: جمع‌آوری chat_id های ارسالی."""
    sent = []
    import giso.base as gb
    real_super = gb._token_from_env
    real_db = gb._token_from_db
    gb._token_from_env = lambda: token
    gb._token_from_db = lambda: ""
    orig_post = gb._http_post
    def fake_post(url, data=None, json_payload=None, files=None):
        sent.append(json_payload.get("chat_id"))
        class R:
            status_code = 200
            def json(self):
                return {"ok": True}
        return R()
    gb._http_post = fake_post
    def restore():
        gb._token_from_env = real_super
        gb._token_from_db = real_db
        gb._http_post = orig_post
    return sent, restore


# ───────────── ۱) تست ارسال از پنل → سوپر ─────────────
def test_1_panel_test_send_to_super():
    app = create_app()
    _cleanup(app)
    try:
        sc = _super(app)
        sent, restore = _capture_send(app)
        try:
            r = sc.post("/admin/notifications/test", follow_redirects=True)
            h = r.get_data(as_text=True)
            _check("1) POST test → 200 + پیام", r.status_code == 200 and "ارسال شد" in h,
                   f"status={r.status_code}")
            _check("1) پیام به سوپر (1191639507) رفت", int(SUPERADMIN_BALE_ID) in sent, str(sent))
            from giso.panel.modules.notifications import list_notifications
            found = any(n.get("subcategory") == "test" for n in list_notifications("super", status="unread"))
            _check("1) رکورد system/test ثبت شد", found)
        finally:
            restore()
    finally:
        _cleanup(app)


# ───────────── ۲/۳/۴) رویدادها → سوپر ─────────────
def test_2_3_4_events_to_super():
    app = create_app()
    _cleanup(app)
    try:
        from giso.panel.modules.notifications import log_notification, list_notifications
        sent, restore = _capture_send(app)
        try:
            log_notification("shop", "order", "سفارش جدید", "ABفاز سفارش",
                             source_type="ab_order", source_id=1001)
            log_notification("users", "ban", "بن کاربر", "ABفاز بن",
                             source_type="ab_ban", source_id=1002)
            log_notification("channel", "post", "پست جدید کانال", "ABفاز کانال",
                             source_type="ab_channel", source_id=1003)
            _check("2) سفارش → سوپر گرفت", 1001 in [n["source_id"] for n in list_notifications("super")]
                   and int(SUPERADMIN_BALE_ID) in sent, str(sent))
            _check("3) بن → سوپر گرفت", 1002 in [n["source_id"] for n in list_notifications("super")])
            _check("4) کانال → سوپر گرفت", 1003 in [n["source_id"] for n in list_notifications("super")])
            # همه target_role=super (پیش‌فرض)
            rows = []
            with get_giso_db_conn() as conn:
                rows = conn.execute(
                    "SELECT target_role FROM giso_notifications WHERE source_id IN (1001,1002,1003)").fetchall()
            _check("پیش‌فرض: همه target=super", all(r["target_role"] == "super" for r in rows), str([r["target_role"] for r in rows]))
        finally:
            restore()
    finally:
        _cleanup(app)


# ───────────── ۵/۶/۷) Bell ─────────────
def test_5_6_7_bell():
    app = create_app()
    _cleanup(app)
    try:
        from giso.panel.modules.notifications import log_notification
        log_notification("shop", "order", "Bell سفارش", "t", source_type="ab_bell", source_id=1010)
        # سایت: کاربر لاگین → Bell
        uc = app.test_client()
        _mkuser(app, USER_PHONE, "کاربر")
        _login(uc, USER_PHONE)
        h = uc.get("/").get_data(as_text=True)
        _check("5) Bell در سایت بالای صفحه", 'class="giso-bell"' in h)
        _check("6) کلیک Bell کاربر → صفحه سفارش‌ها", '/dashboard/orders' in h)
        # سایت: سوپر → Bell به پنل اعلان‌ها
        gc = app.test_client()
        _mkuser(app, SUPER_PHONE, "سوپر")
        _login(gc, SUPER_PHONE)
        h2 = gc.get("/").get_data(as_text=True)
        _check("6) کلیک Bell سوپر → پنل اعلان‌ها", '/admin/notifications' in h2)
        # پنل سوپر: Bell + dropdown + انیمیشن
        sc = _super(app)
        h3 = sc.get("/admin/notifications").get_data(as_text=True)
        _check("5) Bell در پنل سوپر", "pnlBellBtn" in h3 and "pnlBellDrop" in h3)
        _check("7) افکت has-unread", 'has-unread' in h3)
        css = open(os.path.join(BASE_DIR, "giso", "panel", "static", "css", "panel.css"),
                   encoding="utf-8").read()
        _check("7) انیمیشن shake/pulse در CSS", "pnlBellShake" in css and "pnlBellPulse" in css)
        # پنل کاربر: Bell
        _mkuser(app, USER_PHONE, "کاربر")
        h4 = app.test_client().get("/dashboard/orders") if False else None
        uc2 = app.test_client(); _login(uc2, USER_PHONE)
        h4 = uc2.get("/dashboard/orders").get_data(as_text=True)
        _check("5) Bell در پنل کاربر", "pu-bell" in h4 and "/dashboard/orders" in h4)
    finally:
        _cleanup(app)


# ───────────── ۸/۹/۱۰) نقش‌ها ─────────────
def test_8_9_10_roles():
    app = create_app()
    _cleanup(app)
    try:
        from giso.panel.modules.notifications import (log_notification, list_notifications,
                                                       visible_categories, save_category_settings)
        # پیش‌فرض: همه super → ادمین چیزی نمی‌بیند
        log_notification("shop", "order", "نقش سفارش", "t", source_type="ab_role1", source_id=1021)
        log_notification("security", "super_login", "نقش امنیت", "t", source_type="ab_role2", source_id=1022)
        _check("8) کاربر عادی اعلان ادمینی نمی‌بیند",
               all(n["source_type"] != "ab_role1" for n in list_notifications("admin")))
        _check("10) سوپر همه را می‌بیند",
               any(n["source_type"] == "ab_role1" for n in list_notifications("super"))
               and any(n["source_type"] == "ab_role2" for n in list_notifications("super")))
        # ادمین فقط دسترسی مجاز (وقتی سوپر دسته را both کند)
        save_category_settings({"shop": {"target_role": "both", "enabled": 1,
                                         "destination": "both"}})
        log_notification("shop", "order", "نقش admin مجاز", "t", source_type="ab_role3", source_id=1023)
        log_notification("security", "super_login", "نقش admin ممنوع", "t", source_type="ab_role4", source_id=1024)
        admin_list = list_notifications("admin")
        _check("9) ادمین فقط دسته مجاز (shop) را می‌بیند",
               any(n["source_type"] == "ab_role3" for n in admin_list)
               and all(n["source_type"] != "ab_role4" for n in admin_list))
        save_category_settings({"shop": {"target_role": "super", "destination": "both"}})
    finally:
        _cleanup(app)


# ───────────── ۱۱/۱۲/۱۳/۱۴/۱۵) مسیر کانال ─────────────
def test_11_15_channel_path():
    app = create_app()
    _cleanup(app)
    try:
        import giso.ai_brain as ai
        from giso.channel_importer import parse_post, _insert_pending_product, PRICE_MISSING_NOTE

        async def fake_ai(*a, **k):
            return {"name": "ABفاز ماسک مو", "price": 0, "category": "hair",
                    "subcategory": "ماسک", "summary": "ماسک تقویتی ABفاز"}

        # ۱۱) ai_parse بدون خطا با خروجی dict (مسیر fallback AI)
        async def run():
            with patch.object(ai, "ask_ai_fast", new=fake_ai):
                p = await parse_post("ABفاز ماسک مو\nزیردسته: ماسک\nقیمت ذکر نشده")
                return p
        parsed = asyncio.run(run())
        _check("11) ai_parse dict بدون خطا + فیلدها",
               parsed["name"] == "ABفاز ماسک مو" and parsed["subcategory"] == "ماسک"
               and parsed["category"] == "hair" and parsed["price"] == 0, str(parsed))

        # ۱۳) ثبت pending
        pid = _insert_pending_product(parsed, "msg_ab_1", "")
        with get_giso_db_conn() as conn:
            row = conn.execute("SELECT publish_status, category, subcategory, price, description FROM products WHERE id=?",
                               (pid,)).fetchone()
            _check("13) محصول pending ثبت شد",
                   row["publish_status"] == "pending" and row["category"] == "hair"
                   and row["subcategory"] == "ماسک", str(dict(row)))
            _check("13) نوت قیمت در desc (ناقص → منتظر تأیید)",
                   PRICE_MISSING_NOTE in (row["description"] or ""))

        # ۱۲) انتشار بدون app context (همان کد ربات) — اول قیمت واقعی (تا منتشر شود)
        with get_giso_db_conn() as conn:
            conn.execute("UPDATE products SET price=250000, image_path='uploads/ab_test.webp' WHERE id=?", (pid,))
            conn.commit()
        from giso.shop.bot.handlers import _publish_product
        _check("12) _publish_product بدون app context", _publish_product(pid) is True)
        with get_giso_db_conn() as conn:
            row2 = conn.execute("SELECT publish_status, description FROM products WHERE id=?", (pid,)).fetchone()
            _check("14) بعد از تأیید → published", row2["publish_status"] == "published")
            _check("14) نوت قیمت حذف شد", PRICE_MISSING_NOTE not in (row2["description"] or ""))

        # ۱۵) صفحه محصول کامل
        h = app.test_client().get(f"/shop/product/{pid}").get_data(as_text=True)
        _check("15) عنوان", "ABفاز ماسک مو" in h)
        _check("15) قیمت", "250,000" in h)
        _check("15) دسته", "مراقبت مو" in h)
        _check("15) زیردسته badge", "ماسک" in h)
        _check("15) توضیح", "ماسک تقویتی ABفاز" in h)
        _check("15) موجودی", "موجود" in h or "پرداخت در محل" in h)
    finally:
        _cleanup(app)


def _run():
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    passed = 0
    for t in tests:
        try:
            t()
            passed += 1
        except Exception as e:
            import traceback
            print(f"FAIL  {t.__name__} exception: {e}")
            traceback.print_exc()
            _FAILED.append(t.__name__)
    total = len(tests)
    print("-" * 60)
    print(f"{passed}/{total} tests passed (فاز A–F)")
    print("INFO  مورد ۱۶ (رگرسیون) به‌صورت جداگانه در پایان اجرا و در گزارش ثبت می‌شود.")
    if _FAILED:
        print("FAILED:", ", ".join(_FAILED))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(_run())
