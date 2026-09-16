#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
تست فاز layout اختصاصی فروشگاه — همه صفحات فروشگاه از shop_layout.html ارث می‌برند

پوشش (مطابق تست‌های اجباری):
 ۱) /shop لوکس باز شود
 ۲) /shop/product/<id> با layout جدید هماهنگ باشد
 ۳) /shop/product/<id>/<slug> هم‌سبک باز شود
 ۴) /shop/cart با layout جدید نمایش داده شود
 ۵) /shop/buy/<id> با layout جدید نمایش داده شود
 ۶) سبد شناور در همه صفحات فروشگاه
 ۷) شمارنده از /api/cart-count واقعی
 ۸) drawer باز/بسته (JS موجود — وجود عناصر)
 ۹) افزودن به سبد
۱۰) تسویه سفارش
۱۱) اعلان ادمین بله
۱۲) ایمپورت کانال intact
۱۳) ویجت روی همه صفحات
۱۴) SEO/JSON-LD/robots/sitemap
۱۵) موبایل (media queries)
۱۶) رگرسیون route ها/فرم‌ها + همه صفحات extend = shop_layout
"""
import os
import sys
from unittest.mock import patch

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if BASE_DIR not in sys.path:
    sys.path.append(BASE_DIR)

from giso.app import create_app  # noqa: E402
from giso.models import db, Product, ProductOrder  # noqa: E402

_FAILED = []


def _check(name, cond, extra=""):
    status = "PASS" if cond else "FAIL"
    print(f"{status}  {name}" + (f"  ({extra})" if extra else ""))
    if not cond:
        _FAILED.append(name)


def _cleanup(app):
    with app.app_context():
        try:
            for p in Product.query.filter(Product.name.like("LAY%")).all():
                ProductOrder.query.filter_by(product_id=p.id).delete()
            for p in Product.query.filter(Product.name.like("LAY%")).all():
                db.session.delete(p)
            db.session.commit()
        except Exception:
            db.session.rollback()


def _add_product(app):
    with app.app_context():
        p = Product(name="LAY شامپو", description="شامپو تست layout", price=150000,
                    in_stock=True, category="hair", source="site", publish_status="published",
                    created_at="2026-08-01 10:00:00", updated_at="2026-08-01 10:00:00")
        db.session.add(p)
        db.session.commit()
        pid = p.id
        db.session.expunge_all()
        return pid


def _shop_marks(h):
    return {"wrap": "giso-shop-wrap" in h, "widget": "gisoCartWidget" in h,
            "drawer": "gisoCartDrawer" in h, "hero": "giso-shop-hero" in h,
            "brand": "giso-brand.css" in h, "js": "shop.js?v=" in h}


def test_1_5_all_pages_use_shop_layout():
    app = create_app()
    client = app.test_client()
    _cleanup(app)
    pid = _add_product(app)
    try:
        pages = ["/shop", f"/shop/product/{pid}", f"/shop/product/{pid}/slug-test",
                 "/shop/cart", f"/shop/buy/{pid}"]
        for path in pages:
            r = client.get(path)
            _check(f"GET {path} 200", r.status_code == 200, f"status={r.status_code}")
            marks = _shop_marks(r.get_data(as_text=True))
            _check(f"  {path}: layout+widget+drawer", marks["wrap"] and marks["widget"] and marks["drawer"],
                   str(marks))
        # همه قالب‌های فروشگاه از shop_layout ارث می‌برند
        for tpl in ("shop.html", "product_detail.html", "cart.html"):
            src = open(os.path.join(BASE_DIR, "giso", "shop", "templates", tpl), encoding="utf-8").read()
            _check(f"template {tpl} extends shop_layout", '{% extends "shop_layout.html" %}' in src)
    finally:
        _cleanup(app)


def test_6_8_floating_cart_and_drawer():
    app = create_app()
    client = app.test_client()
    _cleanup(app)
    pid = _add_product(app)
    try:
        for path in ("/shop", f"/shop/product/{pid}", "/shop/cart", f"/shop/buy/{pid}"):
            h = client.get(path).get_data(as_text=True)
            _check(f"cart widget on {path}", "gisoCartWidget" in h and "gisoCartCount" in h)
            _check(f"drawer shell on {path}", "gisoCartDrawer" in h)
        # بعد از افزودن آیتم: drawer محتوای واقعی + qty + اکشن‌ها در همه صفحات
        client.post(f"/shop/cart/add/{pid}")
        for path in ("/shop", f"/shop/product/{pid}", "/shop/cart", f"/shop/buy/{pid}"):
            h = client.get(path).get_data(as_text=True)
            _check(f"drawer qty+actions on {path}",
                   "data-qty-form" in h and "#checkout" in h and "/shop/cart" in h)
        # شمارنده واقعی
        r1 = client.get("/api/cart-count")
        _check("cart-count 1", r1.get_json().get("count") == 1, str(r1.get_json()))
    finally:
        _cleanup(app)


def test_9_11_add_checkout_notify():
    app = create_app()
    client = app.test_client()
    _cleanup(app)
    pid = _add_product(app)
    try:
        client.post(f"/shop/cart/add/{pid}")
        with client.session_transaction() as s:
            cart = s.get("giso_cart") or {}
        _check("cart add works", str(pid) in cart)
        # فاز جامع: تسویه فقط با عضویت → ورود کاربر تست
        with app.app_context():
            from giso.models import User
            User.query.filter(User.phone == "+989120000002").delete()
            db.session.add(User(phone="+989120000002", password_hash="h", name="کاربر"))
            db.session.commit()
        with client.session_transaction() as st:
            st["_user_id"] = "+989120000002"
        with patch("giso.shop.routes._notify_admins_shop_order") as m:
            r = client.post("/shop/cart/checkout", data={
                "customer_name": "مشتری LAY", "phone": "09120000002", "address": "تهران"
            }, follow_redirects=True)
            _check("checkout ok", r.status_code in (200, 302))
            _check("admin notified", m.call_count == 1)
        with app.app_context():
            orders = ProductOrder.query.filter_by(phone="+989120000002").all()
            _check("order created", len([o for o in orders if o.customer_name == "مشتری LAY"]) >= 1)
    finally:
        _cleanup(app)


def test_12_13_channel_and_widget():
    app = create_app()
    client = app.test_client()
    _cleanup(app)
    pid = _add_product(app)
    try:
        try:
            import giso.channel_importer as ci
            _check("channel_importer intact", hasattr(ci, "parse_post"))
        except Exception as e:
            _check("channel_importer intact", False, str(e))
        for path in ("/shop", f"/shop/product/{pid}", "/shop/cart", f"/shop/buy/{pid}"):
            h = client.get(path).get_data(as_text=True)
            _check(f"widget on {path}", "ai_widget" in h or "aiWidget" in h or "widget" in h)
    finally:
        _cleanup(app)


def test_14_seo_robots_sitemap():
    app = create_app()
    client = app.test_client()
    _cleanup(app)
    pid = _add_product(app)
    try:
        h = client.get("/shop").get_data(as_text=True)
        _check("shop JSON-LD", '"@type": "ItemList"' in h)
        h2 = client.get(f"/shop/product/{pid}").get_data(as_text=True)
        _check("product JSON-LD+OG", '"@type": "Product"' in h2 and "og:title" in h2 and "BreadcrumbList" in h2)
        rb = client.get("/robots.txt").get_data(as_text=True)
        _check("robots", "Disallow: /admin" in rb and "sitemap.xml" in rb)
        sm = client.get("/sitemap.xml").get_data(as_text=True)
        _check("sitemap", "changefreq" in sm)
    finally:
        _cleanup(app)


def test_15_mobile():
    css = open(os.path.join(BASE_DIR, "giso", "shop", "static", "css", "shop.css"), encoding="utf-8").read()
    _check("mobile media", "@media (max-width: 900px)" in css and "@media (max-width: 640px)" in css)
    _check("1 col", "grid-template-columns: 1fr" in css)


def test_16_routes_forms_regression():
    app = create_app()
    client = app.test_client()
    _cleanup(app)
    pid = _add_product(app)
    try:
        rules = {r.rule for r in app.url_map.iter_rules()}
        for need in ("/shop", "/shop/cart", "/shop/cart/add/<int:product_id>",
                     "/shop/cart/remove/<int:product_id>", "/shop/cart/update/<int:product_id>",
                     "/shop/cart/checkout", "/shop/buy/<int:product_id>", "/shop/notify/<int:product_id>",
                     "/shop/product/<int:product_id>", "/shop/product/<int:product_id>/<path:slug>",
                     "/api/cart-count"):
            _check(f"route {need}", need in rules)
        # فرم‌ها intact
        h = client.get(f"/shop/buy/{pid}").get_data(as_text=True)
        _check("buy form fields", 'name="customer_name"' in h and 'name="phone"' in h and 'name="address"' in h)
        client.post(f"/shop/cart/add/{pid}")
        hc = client.get("/shop/cart").get_data(as_text=True)
        _check("cart form intact", "/shop/cart/checkout" in hc and 'name="qty"' in hc)
    finally:
        _cleanup(app)


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
