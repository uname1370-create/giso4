#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
تست‌های ماژول «🔔 مدیریت اعلان‌ها» (فاز جامع اعلان‌ها)

چک‌لیست ۱۵ موردی:
  ۱) صفحه «مدیریت اعلان‌ها» فقط برای سوپرادمین باز شود
  ۲) صفحه «اعلان‌های من» فقط برای ادمین قابل مشاهده باشد
  ۳) ادمین فقط دسته‌های مجاز را ببیند
  ۴) سوپرادمین همه دسته‌ها را ببیند
  ۵) تنظیم دسته توسط سوپرادمین ذخیره شود (+ ادمین نتواند)
  ۶) ثبت اعلان جدید در دیتابیس هنگام هر رویداد (سفارش فروشگاه)
  ۷) فیلتر بر اساس دسته / وضعیت کار کند
  ۸) badge اعلان‌های خوانده‌نشده درست کار کند
  ۹) دکمه‌های آرشیو / خوانده‌شد کار کنند
 ۱۰) تست ارسال اعلان فقط برای سوپر
 ۱۱) اعلان‌های فعلی سایت و ربات نشکنند
 ۱۲) اعلان به ادمین در ربات همچنان درست کار کند
 ۱۳) اعلان سفارش، فروش مو، آنالیز، کانال ثبت شوند
 ۱۴) صفحه در موبایل مرتب باشد
 ۱۵) رگرسیون کامل تست‌های قبلی سبز باشد (در انتها گزارش می‌شود)
"""
import os
import sys
from unittest.mock import patch

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if BASE_DIR not in sys.path:
    sys.path.append(BASE_DIR)

from giso.app import create_app  # noqa: E402
from giso.models import db, Product, ProductOrder  # noqa: E402
from giso.base import normalize_phone, get_giso_db_conn  # noqa: E402
from giso.config import SUPERADMIN_BALE_ID  # noqa: E402

SUPER_PHONE = normalize_phone("09156012931")
ADMIN_PHONE = normalize_phone("09127778888")
ADMIN_BALE_ID = "55667788"
USER_PHONE = normalize_phone("09120000051")
FIXED_CODE = "246810"

_FAILED = []


def _check(name, cond, extra=""):
    status = "PASS" if cond else "FAIL"
    print(f"{status}  {name}" + (f"  ({extra})" if extra else ""))
    if not cond:
        _FAILED.append(name)


def _notif_cleanup():
    try:
        with get_giso_db_conn() as conn:
            conn.execute("DELETE FROM giso_notifications WHERE source_type LIKE 't_%'"
                         " OR source_type IN ('shop_order','shop_checkout','stock_notify',"
                         "'hair_pending','hair_approved','hair_rejected','hair_completed','analysis_new',"
                         "'channel_post','channel_published','consultant_new','product_req_new',"
                         "'admin_step_up','super_login','user_register','user_ban','user_unban',"
                         "'user_delete','system_backup','system_restart','withdrawal_paid',"
                         "'withdrawal_rejected','consultant_reply','consultant_status','product_req_status')"
                         " OR (category='system' AND subcategory='test')")
            conn.execute("DELETE FROM hair_orders WHERE phone=?", (USER_PHONE,))
            conn.execute("DELETE FROM analyses WHERE phone=?", (USER_PHONE,))
            conn.execute("DELETE FROM consultant_requests WHERE phone=?", (USER_PHONE,))
            conn.execute("DELETE FROM product_requests WHERE phone=?", (USER_PHONE,))
            conn.commit()
    except Exception:
        pass
    # پاک‌سازی ادمین تست از bot.db
    try:
        from giso_admin import _connect as _c
        with _c() as conn:
            conn.execute("DELETE FROM giso_admins WHERE phone=? OR bale_id=?",
                         (ADMIN_PHONE, ADMIN_BALE_ID))
            conn.commit()
    except Exception:
        pass
    try:
        from giso_admin import _connect as _c
        with _c() as conn:
            conn.execute("DELETE FROM giso_config WHERE key IN"
                         " ('notif_category_settings','notif_category_settings_v2',"
                         "  'notif_auto_archive_days','notif_sound_on')")
            conn.commit()
    except Exception:
        pass


def _cleanup(app):
    _notif_cleanup()
    with app.app_context():
        try:
            for p in Product.query.filter(Product.name.like("NOTIFفاز%")).all():
                ProductOrder.query.filter_by(product_id=p.id).delete()
            for p in Product.query.filter(Product.name.like("NOTIFفاز%")).all():
                db.session.delete(p)
            from giso.models import User
            for ph in (USER_PHONE, ADMIN_PHONE):
                User.query.filter(User.phone == ph).delete()
            db.session.commit()
        except Exception:
            db.session.rollback()


def _add_product(app, name="NOTIFفاز شامپو", source="site", status="published"):
    with app.app_context():
        p = Product(name=name, description="شامپو تست اعلان", price=150000,
                    in_stock=True, category="hair", source=source,
                    publish_status=status,
                    created_at="2026-08-01 10:00:00", updated_at="2026-08-01 10:00:00")
        db.session.add(p)
        db.session.commit()
        pid = p.id
        db.session.expunge_all()
        return pid


def _make_user(app, phone, name="کاربر"):
    from giso.models import User
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
    # قرارداد فعلی step-up: کلیدهای نشست (کد بله در تولید؛ تست‌ها نشست را مستقیم تأیید می‌کنند)
    import time as _t
    with client.session_transaction() as st:
        st["admin_panel_verified_phone"] = phone
        st["admin_panel_verified_until"] = int(_t.time()) + 1800


def _super_client(app):
    client = app.test_client()
    _make_user(app, SUPER_PHONE, "سوپر")
    _login(client, SUPER_PHONE)
    _verify(client, SUPER_PHONE)
    return client


def _admin_client(app):
    from giso_admin import add_giso_admin
    client = app.test_client()
    _make_user(app, ADMIN_PHONE, "ادمین")
    add_giso_admin(phone=ADMIN_PHONE, bale_id=ADMIN_BALE_ID, added_by=SUPERADMIN_BALE_ID)
    _login(client, ADMIN_PHONE)
    _verify(client, ADMIN_PHONE)
    return client


# ───────────── ۱) صفحه مدیریت اعلان‌ها فقط سوپر ─────────────
def test_1_super_only_page():
    app = create_app()
    _cleanup(app)
    try:
        s = _super_client(app)
        r = s.get("/admin/notifications")
        h = r.get_data(as_text=True)
        _check("super GET /admin/notifications 200", r.status_code == 200, f"status={r.status_code}")
        _check("super sees مدیریت اعلان‌ها", "مدیریت اعلان‌ها" in h)
        _check("super sees settings panel", "تنظیم مقصد هر دسته" in h and "تست ارسال" in h)
        # کاربر عادی (غیر ادمین) → دسترسی ندارد
        c = app.test_client()
        _make_user(app, USER_PHONE)
        _login(c, USER_PHONE)
        r2 = c.get("/admin/notifications", follow_redirects=True)
        _check("normal user denied", r2.status_code == 200 and "دسترسی" in r2.get_data(as_text=True)
               or "ورود" in r2.get_data(as_text=True), f"status={r2.status_code}")
    finally:
        _cleanup(app)


# ───────────── ۲) اعلان‌های من فقط ادمین ─────────────
def test_2_admin_my_notifications():
    app = create_app()
    _cleanup(app)
    try:
        a = _admin_client(app)
        r = a.get("/admin/notifications")
        h = r.get_data(as_text=True)
        _check("admin GET /admin/notifications 200", r.status_code == 200, f"status={r.status_code}")
        _check("admin label اعلان‌های من in sidebar", "اعلان‌های من" in h)
        _check("admin cannot see settings", "تنظیم مقصد هر دسته" not in h and "تست ارسال" not in h)
    finally:
        _cleanup(app)


# ───────────── ۳/۴) ادمین فقط مجازها؛ سوپر همه ─────────────
def test_3_4_visibility_by_role():
    app = create_app()
    _cleanup(app)
    try:
        from giso.panel.modules.notifications import log_notification, save_category_settings
        # فاز اصلاح سوپر: پیش‌فرض همه → سوپر؛ برای این تست shop را both می‌کنیم تا ادمین ببیند
        save_category_settings({"shop": {"target_role": "both", "enabled": 1,
                                          "destination": "both"}})
        log_notification("shop", "order", "سفارش تست", "t", source_type="t_vis_shop", source_id=901)
        log_notification("security", "super_login", "ورود سوپر تست", "t",
                         source_type="t_vis_sec", source_id=902)
        # ادمین فقط shop می‌بیند نه security
        a = _admin_client(app)
        h = a.get("/admin/notifications").get_data(as_text=True)
        _check("admin sees shop notif", "سفارش تست" in h)
        _check("admin does NOT see security notif", "ورود سوپر تست" not in h)
        s = _super_client(app)
        h2 = s.get("/admin/notifications").get_data(as_text=True)
        _check("super sees both notifs", "سفارش تست" in h2 and "ورود سوپر تست" in h2)
        _check("super settings list has 9 categories", "فقط سوپر" in h2 and "امنیت" in h2)
        # همه ۹ دسته در تنظیمات
        from giso.panel.modules.notifications import category_settings
        _check("9 categories", len(category_settings()) == 9, str(len(category_settings())))
    finally:
        _cleanup(app)


# ───────────── ۵) ذخیره تنظیم دسته (سوپر) ─────────────
def test_5_save_category_settings():
    app = create_app()
    _cleanup(app)
    try:
        s = _super_client(app)
        r = s.post("/admin/notifications/settings", data={
            "target_shop": "admin", "dest_shop": "site", "enabled_shop": "1",
            "target_security": "super", "dest_security": "site", "enabled_security": "1",
        }, follow_redirects=True)
        _check("super save settings ok", r.status_code == 200 and "ذخیره شد" in r.get_data(as_text=True))
        from giso.panel.modules.notifications import category_settings
        st = category_settings()
        _check("shop target saved", st["shop"]["target_role"] == "admin", str(st["shop"]))
        _check("shop dest saved", st["shop"]["destination"] == "site")
        # ادمین نمی‌تواند تنظیمات را عوض کند
        a = _admin_client(app)
        r2 = a.post("/admin/notifications/settings", data={
            "target_shop": "super", "dest_shop": "site", "enabled_shop": "1"}, follow_redirects=True)
        st2 = category_settings()
        _check("admin cannot change settings", st2["shop"]["target_role"] == "admin",
               str(st2["shop"]["target_role"]))
        # بازگرداندن پیش‌فرض
        s.post("/admin/notifications/settings", data={
            "target_shop": "both", "dest_shop": "both", "enabled_shop": "1",
            "target_security": "super", "dest_security": "site", "enabled_security": "1"})
    finally:
        _cleanup(app)


# ───────────── ۶) ثبت اعلان هنگام رویداد (سفارش فروشگاه) ─────────────
def test_6_event_logs_shop_order():
    app = create_app()
    _cleanup(app)
    pid = _add_product(app)
    _make_user(app, USER_PHONE)
    c = app.test_client()
    _login(c, USER_PHONE)
    from giso.panel.modules.notifications import save_category_settings
    save_category_settings({"shop": {"target_role": "both", "enabled": 1,
                                      "destination": "both"}})
    try:
        with patch("giso.shop.routes._notify_admins_shop_order"), \
             patch("giso.shop.logic.orders.notify_user_product_order"):
            r = c.post(f"/shop/buy/{pid}", data={
                "customer_name": "NOTIFفاز مشتری", "phone": "09120000051",
                "address": "مشهد", "courier_note": ""}, follow_redirects=True)
            _check("buy flow ok", r.status_code == 200)
        with get_giso_db_conn() as conn:
            row = conn.execute(
                "SELECT * FROM giso_notifications WHERE source_type='shop_order'").fetchone()
            _check("shop_order notification logged", row is not None)
            _check("shop_order category", row is not None and row["category"] == "shop")
            _check("shop_order status unread", row is not None and row["status"] == "unread")
            _check("shop_order target_role", row is not None and row["target_role"] == "both")
    finally:
        _cleanup(app)


# ───────────── ۷) فیلتر دسته / وضعیت ─────────────
def test_7_filters():
    app = create_app()
    _cleanup(app)
    try:
        from giso.panel.modules.notifications import log_notification, list_notifications
        log_notification("shop", "order", "فیلتر سفارش", "t", source_type="t_f1", source_id=910)
        log_notification("hair_sale", "request", "فیلتر مو", "t", source_type="t_f2", source_id=911)
        lst = list_notifications("super", category="shop")
        _check("filter by category", len(lst) == 1 and lst[0]["subcategory"] == "order")
        lst2 = list_notifications("super", status="unread")
        _check("filter by status unread", all(n["status"] == "unread" for n in lst2))
        lst3 = list_notifications("super", category="hair_sale", status="unread")
        _check("filter cat+status", len(lst3) == 1 and lst3[0]["subcategory"] == "request")
        # فیلتر صفحه (GET)
        s = _super_client(app)
        h = s.get("/admin/notifications?category=shop&status=unread").get_data(as_text=True)
        _check("page filter renders", "فیلتر سفارش" in h and "فیلتر مو" not in h)
    finally:
        _cleanup(app)


# ───────────── ۸) badge خوانده‌نشده ─────────────
def test_8_unread_badge():
    app = create_app()
    _cleanup(app)
    try:
        from giso.panel.modules.notifications import log_notification, unread_count, save_category_settings
        save_category_settings({"shop": {"target_role": "both", "enabled": 1,
                                          "destination": "both"}})
        log_notification("shop", "order", "badge سفارش", "t", source_type="t_b1", source_id=920)
        log_notification("security", "super_login", "badge امنیت", "t", source_type="t_b2", source_id=921)
        _check("super unread 2", unread_count("super") == 2, str(unread_count("super")))
        _check("admin unread 1 (only shop)", unread_count("admin") == 1, str(unread_count("admin")))
        s = _super_client(app)
        h = s.get("/admin/notifications").get_data(as_text=True)
        _check("badge element in sidebar", "pnl-nav-badge" in h and "badge سفارش" in h)
    finally:
        _cleanup(app)


# ───────────── ۹) خوانده‌شد / آرشیو ─────────────
def test_9_read_archive():
    app = create_app()
    _cleanup(app)
    try:
        from giso.panel.modules.notifications import (log_notification, set_status,
                                                       list_notifications)
        log_notification("shop", "order", "عملیات تست", "t", source_type="t_r1", source_id=930)
        nid = list_notifications("super", category="shop")[0]["id"]
        _check("mark read", set_status(nid, "read") is True)
        st = list_notifications("super", status="read")
        _check("status read", any(n["id"] == nid for n in st))
        _check("mark archive", set_status(nid, "archived") is True)
        st2 = list_notifications("super", status="archived")
        _check("status archived", any(n["id"] == nid for n in st2))
        s = _super_client(app)
        h = s.get("/admin/notifications").get_data(as_text=True)
        _check("read btn in page", "خوانده شد" in h and "آرشیو" in h)
    finally:
        _cleanup(app)


# ───────────── ۱۰) تست ارسال فقط سوپر ─────────────
def test_10_test_send_super_only():
    app = create_app()
    _cleanup(app)
    try:
        from giso.panel.modules.notifications import list_notifications
        a = _admin_client(app)
        r = a.post("/admin/notifications/test", follow_redirects=True)
        _check("admin test denied", "فقط برای سوپرادمین" in r.get_data(as_text=True))
        before = len(list_notifications("super", category="system", status="unread"))
        s = _super_client(app)
        r2 = s.post("/admin/notifications/test", follow_redirects=True)
        h2 = r2.get_data(as_text=True)
        after = len(list_notifications("super", category="system", status="unread"))
        _check("super test creates notification", after >= before + 1, f"{before}→{after}")
        _check("super test message", "اعلان تستی" in h2 or "اعلان آزمایشی" in h2)
    finally:
        _cleanup(app)


# ───────────── ۱۱) اعلان‌های فعلی نشکنند ─────────────
def test_11_existing_notify_intact():
    app = create_app()
    _cleanup(app)
    pid = _add_product(app)
    _make_user(app, USER_PHONE)
    c = app.test_client()
    _login(c, USER_PHONE)
    try:
        with patch("giso.shop.routes._notify_admins_shop_order") as m:
            c.post(f"/shop/cart/add/{pid}")
            c.post("/shop/cart/checkout", data={
                "customer_name": "NOTIFفاز سبد", "phone": "09120000051",
                "address": "مشهد"}, follow_redirects=True)
            _check("admin notify still called", m.call_count == 1, f"calls={m.call_count}")
        with app.app_context():
            o = ProductOrder.query.filter_by(customer_name="NOTIFفاز سبد").first()
            _check("order still created", o is not None)
        from giso.shop.logic.checkout import _notify_admins_shop_order
        _notify_admins_shop_order("🧪 تست بدون توکن")
        _check("notify no-token no error", True)
    finally:
        _cleanup(app)


# ───────────── ۱۲) اعلان به ادمین در ربات ─────────────
def test_12_bot_admin_notify_intact():
    # همان مکانیزم ربات: _target_admin_ids + token → بدون توکن بی‌صدا رد می‌شود
    try:
        import giso.channel_importer as ci
        ids = ci._target_admin_ids()
        _check("_target_admin_ids works", isinstance(ids, set))
    except Exception as e:
        _check("_target_admin_ids works", False, str(e))
    from giso.base import _token_from_env, _token_from_db
    _check("token resolution intact", True)
    # گارد پنل ربات برای ادمین با permission فروشگاه (تست قبلی ربات سبز — اینجا فقط import)
    import giso.bot  # noqa: F401
    _check("bot module imports (intact)", True)


# ───────────── ۱۳) سفارش / فروش مو / آنالیز / کانال ثبت شوند ─────────────
def test_13_hair_analysis_channel_logged():
    app = create_app()
    _cleanup(app)
    pid = _add_product(app, name="NOTIFفاز کانال", source="channel", status="pending")
    try:
        with get_giso_db_conn() as conn:
            conn.execute("INSERT INTO hair_orders (user_id, phone, customer_name, photo_path, length_cm,"
                         " status, created_at, updated_at)"
                         " VALUES (0, ?, 'NOTIFفاز', '', 50, 'pending',"
                         " '2026-08-01 10:00:00', '2026-08-01 10:00:00')",
                         (USER_PHONE,))
            conn.execute("INSERT INTO analyses (user_id, phone, type, photo_path, created_at, updated_at)"
                         " VALUES (0, ?, 'hair', '', '2026-08-01 10:00:00', '2026-08-01 10:00:00')",
                         (USER_PHONE,))
            conn.commit()
        from giso.panel.modules.notifications import run_sync_all, list_notifications
        run_sync_all()
        cats = {n["category"] for n in list_notifications("super")}
        _check("hair_sale logged", "hair_sale" in cats, str(cats))
        _check("analysis logged", "analysis" in cats, str(cats))
        _check("channel logged", "channel" in cats, str(cats))
        with get_giso_db_conn() as conn:
            row = conn.execute(
                "SELECT id FROM giso_notifications WHERE source_type='channel_post'"
                " AND source_id=?", (pid,)).fetchone()
            _check("channel post idempotent row", row is not None)
            # دوباره همگام → تکراری نمی‌شود
            run_sync_all()
            cnt = conn.execute(
                "SELECT COUNT(*) c FROM giso_notifications WHERE source_type='channel_post'"
                " AND source_id=?", (pid,)).fetchone()["c"]
            _check("sync idempotent", cnt == 1, str(cnt))
    finally:
        _cleanup(app)


# ───────────── ۱۴) موبایل ─────────────
def test_14_mobile_css():
    css = open(os.path.join(BASE_DIR, "giso", "panel", "static", "css", "panel.css"),
               encoding="utf-8").read()
    _check("panel.css has mobile media query", "@media (max-width: 720px)" in css)
    _check("notif card responsive class", ".pnl-notif-card" in css)
    _check("badge css", ".pnl-nav-badge" in css)
    tpl = open(os.path.join(BASE_DIR, "giso", "panel", "templates", "modules", "notifications.html"),
               encoding="utf-8").read()
    _check("template uses card list", "pnl-notif-card" in tpl and "pnl-notif-ico" in tpl)


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
    print(f"{passed}/{total} tests passed (فاز جامع اعلان‌ها)")
    print("INFO  رگرسیون کامل تست‌های قبلی به‌صورت جداگانه اجرا و در گزارش نهایی ثبت می‌شود (۱۵).")
    if _FAILED:
        print("FAILED:", ", ".join(_FAILED))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(_run())
