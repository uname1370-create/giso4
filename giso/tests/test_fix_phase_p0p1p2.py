#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
تست‌های فاز اصلاحی P0/P1/P2

P0) رفع تداخل sidebar بین فروشگاه و پنل (panel_sidebar / shop_sidebar)
P1) مسیریابی اعلان‌ها: none → نه نمایش نه ارسال؛ admin → فقط ادمین؛ super → فقط سوپر
P2) زیردسته محصول: مدل + migration idempotent + پارس کانال + نمایش (پنل/ربات/سایت)

چک‌لیست ۱۷ موردی:
 ۱) پنل سوپرادمین بدون خرابی باز شود
 ۲) پنل ادمین معمولی بدون خرابی باز شود
 ۳) فروشگاه سایت بدون 500 باز شود
 ۴) فرقی نکند اول کجا باز شده باشد (هر دو ترتیب)
 ۵) sidebar پنل درست دیده شود
 ۶) sidebar فروشگاه درست دیده شود
 ۷) دکمه فروشگاه در navbar درست کار کند
 ۸) اعلان‌های target=none نه در سایت نه در ربات نمایش داده نشوند
 ۹) اعلان‌های target=admin به سوپرادمین در بله نروند
۱۰) اعلان‌های target=super فقط سوپرادمین بگیرد
۱۱) اعلان‌های target=both هر دو بگیرند
۱۲) migration idempotent subcategory اجرا شود
۱۳) پست کانال با subcategory درست پارس شود
۱۴) پیش‌نمایش تأیید ربات subcategory را نمایش دهد
۱۵) پنل ادمین محصول subcategory را نشان دهد
۱۶) صفحه محصول سایت subcategory را نمایش دهد
۱۷) رگرسیون کامل تست‌های قبلی سبز باشد (در انتها جداگانه اجرا می‌شود)
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
USER_PHONE = normalize_phone("09120000088")
FIXED = "246810"
SUPER_BALE = SUPERADMIN_BALE_ID  # آیدی بله سوپر اصلی

_FAILED = []


def _check(name, cond, extra=""):
    status = "PASS" if cond else "FAIL"
    print(f"{status}  {name}" + (f"  ({extra})" if extra else ""))
    if not cond:
        _FAILED.append(name)


def _cleanup(app):
    with app.app_context():
        try:
            for p in Product.query.filter(Product.name.like("P2فاز%")).all():
                ProductOrder_q = None
                from giso.models import ProductOrder
                ProductOrder.query.filter_by(product_id=p.id).delete()
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
    try:
        with get_giso_db_conn() as conn:
            conn.execute("DELETE FROM giso_notifications WHERE source_type LIKE 'p2_%'")
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
    with patch("giso.app._send_admin_panel_code_to_bot", return_value=(True, "ok")), \
         patch("giso.app._generate_admin_panel_code", return_value=FIXED):
        client.get("/admin")
        client.get("/admin/verify")
        r = client.post("/admin/verify", data={"action": "verify", "code": FIXED})
        assert r.status_code == 302


def _super(app):
    c = app.test_client()
    _mkuser(app, SUPER_PHONE, "سوپر")
    _login(c, SUPER_PHONE)
    _verify(c, SUPER_PHONE)
    return c


def _admin(app):
    from giso_admin import add_giso_admin
    c = app.test_client()
    _mkuser(app, ADMIN_PHONE, "ادمین")
    add_giso_admin(phone=ADMIN_PHONE, bale_id=ADMIN_BALE_ID, added_by=SUPERADMIN_BALE_ID)
    _login(c, ADMIN_PHONE)
    _verify(c, ADMIN_PHONE)
    return c


def _add_product(app, subcategory=""):
    with app.app_context():
        p = Product(name="P2فاز شامپو", description="تست", price=120000, in_stock=True,
                    category="hair", subcategory=subcategory, source="site",
                    publish_status="published",
                    created_at="2026-08-01 10:00:00", updated_at="2026-08-01 10:00:00")
        db.session.add(p)
        db.session.commit()
        pid = p.id
        db.session.expunge_all()
        return pid


# ───────────── P0: ۱ تا ۷ ─────────────
def test_1_7_sidebar_collision_fixed():
    app = create_app()
    _cleanup(app)
    pid = _add_product(app)
    try:
        # ترتیب A: اول فروشگاه، بعد پنل سوپر
        g = app.test_client()
        r = g.get("/shop")
        h_shop = r.get_data(as_text=True)
        _check("3) /shop باز شد (اول)", r.status_code == 200, f"status={r.status_code}")
        _check("6) sidebar فروشگاه (gisoShopSidebar) در /shop", "gisoShopSidebar" in h_shop)
        _check("5) sidebar پنل در /shop نیست", "pnl-sidebar" not in h_shop)

        sc = _super(app)
        r2 = sc.get("/admin/dashboard")
        h_panel = r2.get_data(as_text=True)
        _check("1) پنل سوپر بدون خرابی (بعد از /shop)", r2.status_code == 200
               and "pnl-sidebar" in h_panel and "pnl-nav" in h_panel,
               f"status={r2.status_code} sidebar={'pnl-sidebar' in h_panel}")
        _check("5) sidebar پنل درست (منوی پیشخوان)", "پیشخوان" in h_panel and "pnl-nav-item" in h_panel)
        _check("6) sidebar فروشگاه در پنل نیست", "gisoShopSidebar" not in h_panel)

        # ترتیب B: اول پنل (سوپر)، بعد فروشگاه
        app2 = create_app()
        sc2 = _super(app2)
        r3 = sc2.get("/admin/dashboard")
        _check("1) پنل سوپر سالم (اول)", r3.status_code == 200 and "pnl-sidebar" in r3.get_data(as_text=True))
        r4 = app2.test_client().get("/shop")
        h4 = r4.get_data(as_text=True)
        _check("3) /shop بدون 500 (بعد از پنل)", r4.status_code == 200, f"status={r4.status_code}")
        _check("6) sidebar فروشگاه درست بعد از پنل", "gisoShopSidebar" in h4)

        # ادمین معمولی
        ac = _admin(app)
        r5 = ac.get("/admin/dashboard")
        h5 = r5.get_data(as_text=True)
        _check("2) پنل ادمین بدون خرابی", r5.status_code == 200 and "pnl-sidebar" in h5
               and "اعلان" in h5, f"status={r5.status_code}")

        # دکمه فروشگاه در navbar
        r6 = app2.test_client().get("/")
        h6 = r6.get_data(as_text=True)
        _check("7) دکمه فروشگاه در navbar", 'href="/shop"' in h6 and "فروشگاه" in h6)

        # جزئیات محصول + سبد سالم
        r7 = app2.test_client().get(f"/shop/product/{pid}")
        _check("ساختار: جزئیات محصول 200", r7.status_code == 200)
        r8 = app2.test_client().get("/shop/cart")
        _check("ساختار: سبد 200", r8.status_code == 200)
    finally:
        _cleanup(app)


# ───────────── P1: ۸ تا ۱۱ ─────────────
def test_8_11_notification_routing():
    from giso.panel.modules.notifications import (
        log_notification, list_notifications, unread_count, visible_categories,
        save_category_settings, category_settings, _send_bot_destination,
        _regular_admin_ids, _super_admin_ids)
    with get_giso_db_conn() as conn:
        conn.execute("DELETE FROM giso_notifications")
        conn.commit()
    try:
        # ۸) target=none → فقط در جدول با archived، نه در هیچ لیستی
        ok, _ = save_category_settings({"system": {"target_role": "none", "enabled": 1,
                                                    "destination": "both"}})
        _check("save none ok", ok)
        with patch("giso.panel.modules.notifications._send_bot_destination") as m:
            log_notification("system", "test", "none تست", "t", source_type="p2_none", source_id=1)
            _check("8) none → بله ارسال نشد", m.call_count == 0, f"calls={m.call_count}")
        with get_giso_db_conn() as conn:
            row = conn.execute("SELECT status, target_role FROM giso_notifications"
                               " WHERE source_type='p2_none'").fetchone()
            _check("8) none → در جدول با archived", row is not None and row["status"] == "archived"
                   and row["target_role"] == "none", str(dict(row) if row else None))
        for st in ("unread", "read", "archived"):
            lst = list_notifications("super", status=st)
            _check(f"8) none در لیست {st} نیست", all(n["source_type"] != "p2_none" for n in lst))
        _check("8) none در visible_categories نیست", "system" not in visible_categories("super"))

        # بازگردانی پیش‌فرض system
        save_category_settings({"system": {"target_role": "super", "destination": "site"}})

        # ۹/۱۰/۱۱) مقصد ارسال بله — شبیه‌سازی بدون ارسال واقعی
        #   سوپر بله = 1191639507 (SUPER_BALE) — ادمین عادی = ADMIN_BALE_ID
        with patch("giso.panel.modules.notifications._regular_admin_ids",
                   return_value={int(ADMIN_BALE_ID)}), \
             patch("giso.panel.modules.notifications._super_admin_ids",
                   return_value={int(SUPER_BALE)}):
            sent = []
            def fake_post(url, json_payload=None, **kw):
                sent.append(json_payload.get("chat_id"))
            with patch("giso.base._token_from_env", return_value="T"), \
                 patch("giso.base._token_from_db", return_value=""), \
                 patch("giso.base._http_post", side_effect=fake_post):
                _send_bot_destination("t", "admin")
                _check("9) admin → فقط ادمین عادی، سوپر نه",
                       set(sent) == {int(ADMIN_BALE_ID)}, str(sent))
                sent.clear()
                _send_bot_destination("t", "super")
                _check("10) super → فقط سوپر", set(sent) == {int(SUPER_BALE)}, str(sent))
                sent.clear()
                _send_bot_destination("t", "both")
                _check("11) both → هر دو", set(sent) == {int(SUPER_BALE), int(ADMIN_BALE_ID)}, str(sent))
                sent.clear()
                _send_bot_destination("t", "none")
                _check("8) none → ارسال نشد (شبیه‌سازی)", sent == [], str(sent))

        # ساختار واقعی: ادمین عادی جدا از سوپر
        _check("واقعی: سوپر بله در لیست ادمین‌های عادی نیست",
               int(SUPER_BALE) not in _regular_admin_ids())
        _check("واقعی: سوپر بله در لیست سوپر هست", int(SUPER_BALE) in _super_admin_ids())

        # badge برای none نباید شمرده شود
        save_category_settings({"system": {"target_role": "none", "enabled": 1, "destination": "site"}})
        log_notification("system", "test", "none2", "t", source_type="p2_none2", source_id=2)
        _check("8) none در badge خوانده‌نشده شمرده نمی‌شود", unread_count("super") == 0,
               str(unread_count("super")))
        save_category_settings({"system": {"target_role": "super", "destination": "site"}})
        # تنظیمات category را پاک کن تا پیش‌فرض برگردد
        from giso_admin import _connect as _c
        with _c() as conn:
            conn.execute("DELETE FROM giso_config WHERE key IN"
                         " ('notif_category_settings','notif_category_settings_v2')")
            conn.commit()
    finally:
        with get_giso_db_conn() as conn:
            conn.execute("DELETE FROM giso_notifications")
            conn.commit()


# ───────────── P2: ۱۲ تا ۱۶ ─────────────
def test_12_16_subcategory():
    # ۱۲) migration idempotent
    from giso.models import migrate_giso_tables
    from giso.config import _DB_GISO
    migrate_giso_tables(str(_DB_GISO))
    migrate_giso_tables(str(_DB_GISO))  # دوبار — باید بی‌ضرر باشد
    with get_giso_db_conn() as conn:
        cols = {r[1] for r in conn.execute("PRAGMA table_info(products)").fetchall()}
        _check("12) ستون subcategory در products", "subcategory" in cols)
        # اجرای دوباره migration — باید idempotent باشد (بدون خطا و بدون ستون تکراری)
        migrate_giso_tables(str(_DB_GISO))
        cols2 = {r[1] for r in conn.execute("PRAGMA table_info(products)").fetchall()}
        _check("12) migration idempotent (بدون ستون تکراری/خطا)", "subcategory" in cols2
               and len(cols2) == len(cols))

    # ۱۳) پارس کپشن با زیردسته
    import asyncio as _asyncio
    from giso.channel_importer import parse_post, _insert_pending_product
    caption = ("🌿 ماسک مو تقویتی\n"
               "زیردسته: ماسک\n"
               "ماسک ترمیم‌کننده با روغن آرگان\n"
               "قیمت: 420,000 تومان\n"
               "#فروشگاه_گیسو")
    parsed = _asyncio.run(parse_post(caption))
    _check("13) subcategory از کپشن پارس شد", parsed.get("subcategory") == "ماسک",
           repr(parsed.get("subcategory")))
    _check("13) سایر فیلدها intact", parsed["name"] and parsed["price"] == 420000
           and parsed["category"] == "hair")
    pid = _insert_pending_product(parsed, "msg_p2_1", "")
    with get_giso_db_conn() as conn:
        row = conn.execute("SELECT subcategory, category, publish_status FROM products WHERE id=?",
                           (pid,)).fetchone()
        _check("13) subcategory در DB ذخیره شد", row is not None and row["subcategory"] == "ماسک"
               and row["publish_status"] == "pending", str(dict(row) if row else None))

    # ۱۴) پیش‌نمایش ربات subcategory را نمایش دهد
    from giso.channel_importer import _send_preview_to_admins
    captured = {}
    class _FakeBot:
        async def send_message(self, chat_id, text, parse_mode=None, reply_markup=None):
            captured["text"] = text
            captured["chat_id"] = chat_id
    class _Ctx:
        bot = _FakeBot()
    with patch("giso.channel_importer._target_admin_ids", return_value={123456}):
        _asyncio.run(_send_preview_to_admins(_Ctx(), pid, parsed, ""))
    _check("14) پیش‌نمایش ربات زیردسته دارد", "زیردسته: ماسک" in captured.get("text", ""),
           repr(captured.get("text", "")[:200]))

    # ۱۵) پنل ادمین محصول زیردسته را نشان دهد
    app = create_app()
    sc = _super(app)
    h = sc.get("/admin/products").get_data(as_text=True)
    _check("15) پنل ادمین زیردسته را نشان می‌دهد", "ماسک" in h and "دسته / زیردسته" in h)

    # ۱۶) صفحه محصول سایت badge زیردسته
    with get_giso_db_conn() as conn:
        conn.execute("UPDATE products SET publish_status='published', subcategory='ماسک' WHERE id=?",
                     (pid,))
        conn.commit()
    h2 = app.test_client().get(f"/shop/product/{pid}").get_data(as_text=True)
    _check("16) صفحه محصول سایت زیردسته را نشان می‌دهد", "ماسک" in h2
           and "giso-chip-sub" in h2, "badge")

    # پاکسازی
    with get_giso_db_conn() as conn:
        conn.execute("DELETE FROM products WHERE id=?", (pid,))
        conn.execute("DELETE FROM giso_notifications WHERE source_type LIKE 'p2_%'")
        conn.commit()


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
    print(f"{passed}/{total} tests passed (فاز P0/P1/P2)")
    print("INFO  مورد ۱۷ (رگرسیون کامل) به‌صورت جداگانه در پایان اجرا و در گزارش ثبت می‌شود.")
    if _FAILED:
        print("FAILED:", ", ".join(_FAILED))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(_run())
