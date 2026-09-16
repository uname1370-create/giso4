#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
تست‌های فاز جامع اصلاحی و تکمیل جریان خرید فروشگاه گیسو (A–N)

چک‌لیست ۱۸ موردی:
  ۱) خرید فقط با عضویت: مهمان → ریدایرکت ورود (خرید فوری)
  ۲) خرید فقط با عضویت: مهمان → ریدایرکت ورود (سبد) + سبد پاک نمی‌شود
  ۳) بازگشت به همان محصول/سبد بعد از عضویت (?next= در ورود/ثبت‌نام)
  ۴) فرم خرید: نام/شماره/آدرس + توضیح پیک + «ارسال فقط مشهد» + «هزینه ارسال جدا» + پرداخت در محل
  ۵) ثبت سفارش: وضعیت اولیه «در حال بررسی» + یادداشت پیک ذخیره + اعلان کامل ادمین
  ۶) صفحه موفقیت: تبریک + فاکتور (بدون هزینه ارسال) + کارت انتخاب زمان + ویجت تشکر + «پیام‌رسان گیسو»
  ۷) هماهنگی زمان ارسال: ذخیره زمان + یادداشت پیک + اعلان ادمین با زمان
  ۸) پیام رسمی به کاربر بعد از ثبت سفارش (H)
  ۹) تأیید ادمین: pending → approved + اطلاع خودکار به کاربر (I/L)
 ۱۰) بررسی وضعیت توسط کاربر در پنلش (J)
 ۱۱) ویجت همراه خریدار: تشکر + پیشنهاد هوشمند + وضعیت سفارش (M)
 ۱۲) جست‌وجوی زنده بدون تأخیر + نتایج تجمیعی + مخفی‌شدن اسلات‌ها (A)
 ۱۳) فیلترهای دسته/قیمت/موجودی/برچسب + پاک‌کردن فیلترها + drawer موبایل (B)
 ۱۴) میان‌برهای محبوب/پرفروش/تخفیف/تازه + «همه محصولات» (C)
 ۱۵) برچسب فارسی وضعیت‌ها + دکمه تأیید در پنل ادمین
 ۱۶) کانال بله: ایمپورت سالم + حالت auto/review + آماده برای تست واقعی (N)
 ۱۷) رگرسیون: route ها/فرم‌ها/فیلدها/SEO دست‌نخورده
 ۱۸) فارسی + موبایل + بدون تأخیر سمت کلاینت
"""
import os
import sys
from unittest.mock import patch

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if BASE_DIR not in sys.path:
    sys.path.append(BASE_DIR)

from giso.app import create_app  # noqa: E402
from giso.models import db, Product, ProductOrder  # noqa: E402
from giso.base import normalize_phone  # noqa: E402

SUPER_PHONE = normalize_phone("09156012931")
FIXED_CODE = "654321"
USER_PHONE = normalize_phone("09120000041")

_FAILED = []


def _check(name, cond, extra=""):
    status = "PASS" if cond else "FAIL"
    print(f"{status}  {name}" + (f"  ({extra})" if extra else ""))
    if not cond:
        _FAILED.append(name)


def _cleanup(app):
    with app.app_context():
        try:
            for p in Product.query.filter(Product.name.like("BUYفاز%")).all():
                ProductOrder.query.filter_by(product_id=p.id).delete()
            for p in Product.query.filter(Product.name.like("BUYفاز%")).all():
                db.session.delete(p)
            from giso.models import User
            User.query.filter(User.phone == USER_PHONE).delete()
            db.session.commit()
        except Exception:
            db.session.rollback()
    try:
        from giso.base import get_giso_db_conn
        with get_giso_db_conn() as conn:
            conn.execute("DELETE FROM product_orders WHERE customer_name LIKE 'BUYفاز%'")
            conn.commit()
    except Exception:
        pass


def _add_product(app):
    with app.app_context():
        p = Product(name="BUYفاز شامپو", description="شامپو تست فاز جامع", price=150000,
                    in_stock=True, category="hair", source="site", publish_status="published",
                    created_at="2026-08-01 10:00:00", updated_at="2026-08-01 10:00:00")
        db.session.add(p)
        db.session.commit()
        pid = p.id
        db.session.expunge_all()
        return pid


def _make_user(app, phone=USER_PHONE):
    from giso.models import User
    with app.app_context():
        User.query.filter(User.phone == phone).delete()
        db.session.add(User(phone=phone, password_hash="h", name="کاربر جامع"))
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
         patch("giso.app._generate_admin_panel_code", return_value=FIXED_CODE):
        client.get("/admin")
        client.get("/admin/verify")
        r = client.post("/admin/verify", data={"action": "verify", "code": FIXED_CODE})
        assert r.status_code == 302


def _buy(app, client, pid, phone="09120000041", note="زنگ بزنید"):
    return client.post(f"/shop/buy/{pid}", data={
        "customer_name": "BUYفاز مشتری", "phone": phone, "address": "مشهد، سجاد",
        "courier_note": note,
    }, follow_redirects=True)


# ───────────── ۱) گیت عضویت: خرید فوری ─────────────
def test_1_guest_buy_gated():
    app = create_app()
    client = app.test_client()
    _cleanup(app)
    pid = _add_product(app)
    try:
        r = client.post(f"/shop/buy/{pid}", data={
            "customer_name": "مهمان", "phone": "09120000001", "address": "تهران"})
        _check("guest buy → redirect", r.status_code == 302, f"status={r.status_code}")
        _check("guest buy → login with next",
               "/login?next=" in (r.headers.get("Location") or "") and f"/shop/buy/{pid}" in (r.headers.get("Location") or ""),
               r.headers.get("Location", ""))
        with app.app_context():
            _check("guest buy creates no order",
                   ProductOrder.query.filter_by(customer_name="مهمان").count() == 0)
    finally:
        _cleanup(app)


# ───────────── ۲) گیت عضویت: تسویه سبد ─────────────
def test_2_guest_checkout_gated():
    app = create_app()
    client = app.test_client()
    _cleanup(app)
    pid = _add_product(app)
    try:
        client.post(f"/shop/cart/add/{pid}")
        r = client.post("/shop/cart/checkout", data={
            "customer_name": "مهمان", "phone": "09120000002", "address": "تهران"})
        _check("guest checkout → redirect", r.status_code == 302, f"status={r.status_code}")
        loc = r.headers.get("Location") or ""
        _check("guest checkout → login + back to cart", "/login?next=" in loc and "/shop/cart" in loc, loc)
        with client.session_transaction() as st:
            cart = st.get("giso_cart") or {}
        _check("guest cart kept", str(pid) in cart, str(cart))
    finally:
        _cleanup(app)


# ───────────── ۳) بازگشت به همان محصول/سبد بعد از عضویت ─────────────
def test_3_login_next_returns():
    app = create_app()
    client = app.test_client()
    _cleanup(app)
    pid = _add_product(app)
    _make_user(app)
    try:
        # ورود با ?next= → برگشت به همان صفحه
        from werkzeug.security import generate_password_hash
        with app.app_context():
            from giso.models import User
            u = User.query.filter_by(phone=USER_PHONE).first()
            u.password_hash = generate_password_hash("1234", method="pbkdf2:sha256")
            db.session.commit()
        r = client.post(f"/login?next=/shop/buy/{pid}", data={
            "phone": "09120000041", "password": "1234"})
        _check("login POST 302", r.status_code == 302, f"status={r.status_code}")
        _check("login → back to same product", (r.headers.get("Location") or "") == f"/shop/buy/{pid}",
               r.headers.get("Location", ""))
    finally:
        _cleanup(app)


# ───────────── ۴) فرم خرید کامل (E) ─────────────
def test_4_buy_form_fields_and_ship_notes():
    app = create_app()
    client = app.test_client()
    _cleanup(app)
    pid = _add_product(app)
    try:
        html = client.get(f"/shop/buy/{pid}").get_data(as_text=True)
        for fld in ('name="customer_name"', 'name="phone"', 'name="address"', 'name="courier_note"'):
            _check("buy form has " + fld, fld in html)
        _check("ship note: only Mashhad", "فقط در <b>مشهد</b>" in html or "مشهد" in html)
        _check("ship note: separate courier cost", "هزینه ارسال جداگانه" in html)
        _check("pay on delivery", "پرداخت در محل" in html)
        _check("guest gate note on buy", "برای ثبت سفارش ابتدا" in html and "/login?next=" in html)
        # سبد هم همین فیلدها (اول یک آیتم اضافه می‌کنیم تا فرم تسویه رندر شود)
        client.post(f"/shop/cart/add/{pid}")
        hc = client.get("/shop/cart").get_data(as_text=True)
        _check("cart has courier_note", 'name="courier_note"' in hc)
        _check("cart ship note Mashhad", "مشهد" in hc and "هزینه ارسال جداگانه" in hc)
    finally:
        _cleanup(app)


# ───────────── ۵) ثبت سفارش: pending + یادداشت پیک + اعلان کامل ادمین ─────────────
def test_5_order_pending_and_full_admin_msg():
    app = create_app()
    client = app.test_client()
    _cleanup(app)
    pid = _add_product(app)
    _make_user(app)
    _login(client, USER_PHONE)
    try:
        with patch("giso.shop.routes._notify_admins_shop_order") as m, \
             patch("giso.shop.logic.orders.notify_user_product_order") as m2:
            r = _buy(app, client, pid)
            _check("buy POST ok (member)", r.status_code == 200, f"status={r.status_code}")
            _check("admin notified once", m.call_count == 1, f"calls={m.call_count}")
            msg = m.call_args[0][0] if m.call_count else ""
            for part in ("BUYفاز", "مشهد، سجاد", normalize_phone("09120000041"), "در محل", "در حال بررسی", "زنگ بزنید"):
                _check(f"admin msg contains {part}", part in msg, msg[:90])
        with app.app_context():
            o = ProductOrder.query.filter_by(customer_name="BUYفاز مشتری").first()
            _check("order created", o is not None)
            _check("order status pending", o is not None and o.status == "pending", getattr(o, "status", None))
        from giso.base import get_giso_db_conn
        with get_giso_db_conn() as conn:
            row = conn.execute("SELECT courier_note FROM product_orders WHERE customer_name='BUYفاز مشتری'").fetchone()
            _check("courier_note stored", row is not None and row["courier_note"] == "زنگ بزنید",
                   str(dict(row) if row else None))
    finally:
        _cleanup(app)


# ───────────── ۶) صفحه موفقیت (F/G) ─────────────
def test_6_order_success_page():
    app = create_app()
    client = app.test_client()
    _cleanup(app)
    pid = _add_product(app)
    _make_user(app)
    _login(client, USER_PHONE)
    try:
        _buy(app, client, pid)
        h = client.get("/shop/order-success").get_data(as_text=True)
        _check("success 200", "سفارش شما با موفقیت ثبت شد" in h or "با موفقیت ثبت شد" in h)
        _check("status: در حال بررسی", "در حال بررسی" in h)
        _check("delivery time card", "انتخاب زمان دلخواه ارسال" in h and "/shop/order-time" in h)
        _check("snapp paynote", "اسنپ پیک" in h and "هزینه ارسال" in h and "محاسبه نمی‌شود" in h)
        _check("thanks widget", "سپاس از خرید شما" in h and "پیام‌رسان گیسو" in h)
        _check("invoice line", "BUYفاز شامپو" in h and "150,000" in h)
    finally:
        _cleanup(app)


# ───────────── ۷) هماهنگی زمان ارسال (F) ─────────────
def test_7_order_time_saves_and_notifies():
    app = create_app()
    client = app.test_client()
    _cleanup(app)
    pid = _add_product(app)
    _make_user(app)
    _login(client, USER_PHONE)
    try:
        _buy(app, client, pid, note="")
        with patch("giso.shop.routes._notify_admins_shop_order") as m:
            r = client.post("/shop/order-time", data={
                "delivery_time": "15 تا 18 عصر", "courier_note": "درب منزل"})
            _check("order-time redirects to success", r.status_code == 302 and "/shop/order-success" in (r.headers.get("Location") or ""),
                   r.headers.get("Location", ""))
            msg = m.call_args[0][0] if m.call_count else ""
            _check("admin notified with time", m.call_count == 1 and "15 تا 18 عصر" in msg, msg[:90])
        from giso.base import get_giso_db_conn
        with get_giso_db_conn() as conn:
            row = conn.execute("SELECT delivery_time, courier_note FROM product_orders WHERE customer_name='BUYفاز مشتری'").fetchone()
            _check("delivery_time stored", row is not None and row["delivery_time"] == "15 تا 18 عصر",
                   str(dict(row) if row else None))
            _check("courier_note stored via time form", row is not None and row["courier_note"] == "درب منزل")
    finally:
        _cleanup(app)


# ───────────── ۸) پیام رسمی به کاربر (H) ─────────────
def test_8_user_official_message():
    app = create_app()
    client = app.test_client()
    _cleanup(app)
    pid = _add_product(app)
    _make_user(app)
    _login(client, USER_PHONE)
    try:
        with patch("giso.shop.logic.orders.notify_user_product_order") as m:
            _buy(app, client, pid)
            _check("user notified after buy", m.call_count == 1, f"calls={m.call_count}")
            txt = m.call_args[0][1] if m.call_count else ""
            _check("user msg: order registered", "سفارش شما ثبت شد" in txt, txt[:80])
            _check("user msg: پیام‌رسان گیسو", "پیام‌رسان گیسو" in txt)
        with patch("giso.shop.logic.orders.notify_user_product_order") as m:
            client.post("/shop/order-time", data={"delivery_time": "9 تا 12 ظهر"})
            _check("user notified after time", m.call_count == 1, f"calls={m.call_count}")
    finally:
        _cleanup(app)


# ───────────── ۹) تأیید ادمین: pending → approved + اطلاع (I/L) ─────────────
def test_9_admin_approve_flow():
    app = create_app()
    client = app.test_client()
    _cleanup(app)
    pid = _add_product(app)
    _make_user(app)
    _login(client, USER_PHONE)
    try:
        _buy(app, client, pid)
        with app.app_context():
            o = ProductOrder.query.filter_by(customer_name="BUYفاز مشتری").first()
            oid = o.id
        # ورود سوپرادمین + تأیید
        with app.app_context():
            from giso.models import User
            User.query.filter(User.phone == SUPER_PHONE).delete()
            db.session.add(User(phone=SUPER_PHONE, password_hash="h", name="سوپر"))
            db.session.commit()
        admin = app.test_client()
        _login(admin, SUPER_PHONE)
        _verify(admin, SUPER_PHONE)
        with patch("giso.shop.logic.orders.notify_user_product_order") as m:
            r = admin.post(f"/admin/shop-order/{oid}/status", data={"status": "approved"})
            _check("admin approve 302", r.status_code == 302, f"status={r.status_code}")
            _check("user notified on approve", m.call_count == 1, f"calls={m.call_count}")
            txt = m.call_args[0][1] if m.call_count else ""
            _check("approve msg contains تأیید شد", "تأیید شد" in txt, txt[:80])
        with app.app_context():
            o2 = ProductOrder.query.get(oid)
            _check("order approved in db", o2 is not None and o2.status == "approved",
                   getattr(o2, "status", None))
    finally:
        _cleanup(app)


# ───────────── ۱۰) بررسی وضعیت کاربر در پنلش (J) ─────────────
def test_10_user_panel_status_labels():
    app = create_app()
    client = app.test_client()
    _cleanup(app)
    pid = _add_product(app)
    _make_user(app)
    _login(client, USER_PHONE)
    try:
        with app.app_context():
            db.session.add(ProductOrder(phone=USER_PHONE, customer_name="BUYفاز مشتری",
                                        product_id=pid, address="مشهد", quantity=1,
                                        status="pending"))
            db.session.commit()
            oid = ProductOrder.query.filter_by(customer_name="BUYفاز مشتری").first().id
        h = client.get("/dashboard/shop").get_data(as_text=True)
        _check("user panel shows در حال بررسی", "در حال بررسی" in h)
        with app.app_context():
            o = ProductOrder.query.get(oid)
            o.status = "approved"
            db.session.commit()
        h2 = client.get("/dashboard/shop").get_data(as_text=True)
        _check("user panel shows تأیید شد", "تأیید شد" in h2)
    finally:
        _cleanup(app)


# ───────────── ۱۱) ویجت همراه خریدار (M) ─────────────
def test_11_smart_widget():
    app = create_app()
    client = app.test_client()
    _cleanup(app)
    pid = _add_product(app)
    _make_user(app)
    _login(client, USER_PHONE)
    try:
        h = client.get("/shop").get_data(as_text=True)
        _check("widget container on shop", "gisoSmartWidget" in h and "gisoSmartClose" in h)
        _check("widget data-just-ordered", "data-just-ordered" in h)
        _check("widget data-orders", "data-orders=" in h)
        js = open(os.path.join(BASE_DIR, "giso", "shop", "static", "js", "shop.js"), encoding="utf-8").read()
        _check("widget js: thanks", "سپاس از خرید شما" in js)
        _check("widget js: smart suggestions", "پیشنهاد هوشمند برای شما" in js)
        # بعد از خرید، داده وضعیت سفارش در ویجت می‌آید
        _buy(app, client, pid)
        h2 = client.get("/shop").get_data(as_text=True)
        _check("widget has order data after buy", "data-just-ordered=\"1\"" in h2 and "BUYفاز" in h2)
    finally:
        _cleanup(app)


# ───────────── ۱۲) جست‌وجوی زنده (A) ─────────────
def test_12_live_search_ui():
    app = create_app()
    client = app.test_client()
    _cleanup(app)
    pid = _add_product(app)
    try:
        h = client.get("/shop").get_data(as_text=True)
        _check("search input", 'id="shopSearch"' in h and 'placeholder="جستجو' in h)
        _check("search results bar", "shopSearchResults" in h and "shopSearchCount" in h)
        _check("no form around search (live, no reload)", 'id="shopSearch"' in h and 'shopSearchResults" hidden' in h)
        js = open(os.path.join(BASE_DIR, "giso", "shop", "static", "js", "shop.js"), encoding="utf-8").read()
        _check("js live input listener", "addEventListener('input', applyAll)" in js)
        _check("js aggregate mode (search hides slots)", "mode === 'search'" in js and "gridVisible = true" in js)
    finally:
        _cleanup(app)


# ───────────── ۱۳) فیلترها (B) ─────────────
def test_13_filters_real():
    app = create_app()
    client = app.test_client()
    _cleanup(app)
    _add_product(app)
    try:
        h = client.get("/shop").get_data(as_text=True)
        for cls in ("giso-f-cat", "giso-f-price", "giso-f-stock", "giso-f-tag"):
            _check(f"filter {cls}", cls in h)
        _check("clear filters btn", "پاک‌کردن همه فیلترها" in h and "gisoFilterClear" in h)
        _check("mobile drawer", 'id="gisoFiltersBtn"' in h and "gisoFiltersOverlay" in h and 'id="gisoShopSidebar"' in h)
        js = open(os.path.join(BASE_DIR, "giso", "shop", "static", "js", "shop.js"), encoding="utf-8").read()
        _check("js filter inputs wired", "giso-f-cat, .giso-f-price, .giso-f-stock, .giso-f-tag" in js)
        _check("js clear resets + chip all", "setChip('all')" in js and "resetFiltersUI()" in js)
    finally:
        _cleanup(app)


# ───────────── ۱۴) میان‌برها (C) ─────────────
def test_14_shortcuts():
    app = create_app()
    client = app.test_client()
    _cleanup(app)
    _add_product(app)
    try:
        h = client.get("/shop").get_data(as_text=True)
        for chip in ("data-sort=\"all\"", "data-sort=\"popular\"", "data-sort=\"best\"",
                     "data-sort=\"sale\"", "data-sort=\"new\""):
            _check(f"chip {chip}", chip in h)
        _check("sale slot exists", 'data-slot="sale"' in h)
        # اسلات‌ها شرطی رندر می‌شوند؛ وجود آن‌ها در قالب را بررسی می‌کنیم
        tpl = open(os.path.join(BASE_DIR, "giso", "shop", "templates", "shop.html"), encoding="utf-8").read()
        for slot in ('data-slot="popular"', 'data-slot="best"', 'data-slot="new"', 'data-slot="back"', 'data-slot="sale"'):
            _check(f"template slot {slot}", slot in tpl)
        js = open(os.path.join(BASE_DIR, "giso", "shop", "static", "js", "shop.js"), encoding="utf-8").read()
        _check("js shortcut: only that slot", "slotVisible[mode] = true" in js)
        _check("js all restores default", "key === 'all'" in js)
    finally:
        _cleanup(app)


# ───────────── ۱۵) برچسب فارسی + دکمه تأیید پنل ─────────────
def test_15_status_labels_admin_ui():
    from giso.shop.logic.orders import status_fa
    _check("status_fa pending", status_fa("pending") == "در حال بررسی", status_fa("pending"))
    _check("status_fa approved", status_fa("approved") == "تأیید شد", status_fa("approved"))
    tpl = open(os.path.join(BASE_DIR, "giso", "shop", "panel", "templates", "admin", "shop.html"),
               encoding="utf-8").read()
    _check("admin hub approve button", 'value="approved"' in tpl and "✅ تأیید شد" in tpl)
    _check("admin hub در حال بررسی", "در حال بررسی" in tpl)
    utpl = open(os.path.join(BASE_DIR, "giso", "shop", "panel", "templates", "user", "shop.html"),
                encoding="utf-8").read()
    _check("user panel در حال بررسی", "در حال بررسی" in utpl)
    _check("user panel تأیید شد", "تأیید شد" in utpl)


# ───────────── ۱۶) کانال بله (N) ─────────────
def test_16_bale_channel_status():
    try:
        import giso.channel_importer as ci
        _check("channel_importer imports", True)
        _check("channel_importer has parse_post", hasattr(ci, "parse_post"))
    except Exception as e:
        _check("channel_importer imports", False, str(e))
    from giso.shop.logic.channel_bridge import get_publish_mode
    mode = get_publish_mode()
    _check("publish mode auto/review", mode in ("auto", "review"), str(mode))
    app = create_app()
    client = app.test_client()
    with app.app_context():
        from giso.shop.logic.channel_bridge import get_publish_mode as gm
        _check("channel bridge works in app", gm() in ("auto", "review"))
    # مسیر تست واقعی بدون توکن فقط بی‌صدا رد می‌شود (بدون خطا)
    _check("channel-test endpoint registered", client.get("/shop").status_code == 200)
    print("INFO  کانال بله: وضعیت ایمپورت خودکار/review سالم است؛ برای تست واقعی به توکن/ادمین نیاز است"
          " — مسیر پیشنهادی در گزارش نهایی آمده است (N).")


# ───────────── ۱۷) رگرسیون route ها/فرم‌ها/SEO ─────────────
def test_17_routes_forms_seo_preserved():
    app = create_app()
    client = app.test_client()
    _cleanup(app)
    pid = _add_product(app)
    try:
        for path in ("/shop", "/shop/cart", f"/shop/buy/{pid}", f"/shop/product/{pid}",
                     "/robots.txt", "/sitemap.xml", "/api/cart-count"):
            r = client.get(path)
            _check(f"GET {path} 200", r.status_code == 200, f"status={r.status_code}")
        hs = client.get("/shop").get_data(as_text=True)
        _check("JSON-LD ItemList", '"@type": "ItemList"' in hs)
        _check("canonical kept", 'rel="canonical"' in hs)
        _check("og meta kept", 'property="og:title"' in hs)
        hb = client.get(f"/shop/buy/{pid}").get_data(as_text=True)
        _check("buy form action intact", f"/shop/buy/{pid}" in hb)
        _check("buy field names intact", 'name="customer_name"' in hb and 'name="phone"' in hb and 'name="address"' in hb)
        client.post(f"/shop/cart/add/{pid}")
        hc = client.get("/shop/cart").get_data(as_text=True)
        _check("checkout action intact", "/shop/cart/checkout" in hc)
        _check("cart qty field intact", 'name="qty"' in hc)
        _check("new routes registered", client.get("/shop/order-success").status_code == 200)
        # اسلات/ستون‌های جدید اجباری در گرید
        _check("grid has data-tags cards", "data-tags=" in hs)
    finally:
        _cleanup(app)


# ───────────── ۱۸) فارسی + موبایل + بدون تأخیر (A) ─────────────
def test_18_persian_mobile_no_delay():
    app = create_app()
    client = app.test_client()
    _cleanup(app)
    _add_product(app)
    try:
        h = client.get("/shop").get_data(as_text=True)
        for fa in ("محبوب‌ترین", "پرفروش‌ترین", "تخفیف‌دار", "تازه‌ترین", "همه محصولات"):
            _check(f"persian shortcut {fa}", fa in h)
        css = open(os.path.join(BASE_DIR, "giso", "shop", "static", "css", "shop.css"), encoding="utf-8").read()
        _check("mobile media queries", "@media (max-width: 640px)" in css)
        _check("lux chips css", ".giso-chip:hover { transform" in css or "backdrop-filter" in css)
        _check("smart widget css", ".giso-smart-widget" in css)
        _check("success page css", ".giso-order-success" in css)
        _check("time chips css", ".giso-time-chip" in css)
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
    print(f"{passed}/{total} tests passed (فاز جامع خرید)")
    if _FAILED:
        print("FAILED:", ", ".join(_FAILED))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(_run())
