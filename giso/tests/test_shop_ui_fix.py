#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
تست فاز اصلاحی UI فروشگاه — هم‌سبک‌سازی گرم + رفع عملکرد گزینه‌ها

پوشش:
 ۱) هم‌سبک‌سازی: giso-brand.css + hero برنددار + کارت شیشه گرم
 ۲) جست‌وجو و فیلترها: input ها و چک‌باکس‌ها در صفحه هستند و به گرید متصل‌اند
 ۳) سبد شناور: محتوای واقعی از session (آیتم + جمع در drawer)
 ۴) شمارنده واقعی: endpoint /api/cart-count
 ۵) تغییر تعداد در drawer (فرم cart_update)
 ۶) صفحه محصول: خرید فوری فقط لینک به /shop/buy/<id> (بدون فرم داخل جزئیات)
 ۷) /shop/buy/<id> هنوز فرم خرید با فیلدهای قبلی را رندر می‌کند
 ۸) راهنمای مهمان (بدون ورود) + فرم تسویه intact
 ۹) تسویه + اعلان ادمین
۱۰) SEO/JSON-LD/robots/sitemap + route های قبلی intact
"""
import os
import sys
import time
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
            for p in Product.query.filter(Product.name.like("UI%")).all():
                ProductOrder.query.filter_by(product_id=p.id).delete()
            for p in Product.query.filter(Product.name.like("UI%")).all():
                db.session.delete(p)
            db.session.commit()
        except Exception:
            db.session.rollback()


def _add_products(app):
    with app.app_context():
        p1 = Product(name="UI شامپو مو", description="شامپو گرم UI", price=120000,
                     in_stock=True, category="hair", source="site", publish_status="published",
                     created_at="2026-08-01 10:00:00", updated_at="2026-08-01 10:00:00")
        p2 = Product(name="UI ماسک پوست", description="ماسک UI", price=220000,
                     in_stock=True, category="face", source="site", publish_status="published",
                     created_at="2026-08-02 10:00:00", updated_at="2026-08-02 10:00:00")
        p3 = Product(name="UI سرم", description="سرم UI", price=150000,
                     in_stock=False, category="hair", source="site", publish_status="published",
                     created_at="2026-08-03 10:00:00", updated_at="2026-08-03 10:00:00")
        db.session.add_all([p1, p2, p3])
        db.session.commit()
        ids = (p1.id, p2.id, p3.id)
        db.session.expunge_all()
        return ids


def test_1_warm_style():
    app = create_app()
    client = app.test_client()
    _cleanup(app)
    _add_products(app)
    try:
        html = client.get("/shop").get_data(as_text=True)
        _check("giso-brand.css linked", "giso-brand.css" in html)
        _check("warm hero", "giso-shop-hero" in html and "giso-shop-hero-badge" in html)
        _check("hero gold CTA text", "پرداخت در محل" in html)
        css = open(os.path.join(BASE_DIR, "giso", "shop", "static", "css", "shop.css"), encoding="utf-8").read()
        _check("warm glass", "rgba(255, 249, 240, .72)" in css or "giso-glass" in css)
        _check("gold gradient", "var(--giso-gold)" in css or "#D4AF37" in css)
        _check("warm bg", "#FFF9F0" in css and "#FFF5E9" in css)
        _check("warm badge", "rgba(212,175,55,.18)" in css or "giso-chip-cat" in css)
    finally:
        _cleanup(app)


def test_2_search_and_filters_wired():
    app = create_app()
    client = app.test_client()
    _cleanup(app)
    _add_products(app)
    try:
        html = client.get("/shop").get_data(as_text=True)
        _check("search input", 'id="shopSearch"' in html)
        _check("category filter inputs", 'class="giso-f-cat"' in html)
        _check("price filter inputs", 'class="giso-f-price"' in html)
        _check("stock filter inputs", 'class="giso-f-stock"' in html)
        _check("tag filter inputs", 'class="giso-f-tag"' in html)
        _check("clear filters btn", "giso-filter-clear" in html)
        _check("cards have data attrs", 'data-price=' in html and 'data-tags=' in html)
    finally:
        _cleanup(app)


def test_3_4_drawer_real_content_and_count():
    app = create_app()
    client = app.test_client()
    _cleanup(app)
    pid1, pid2, pid3 = _add_products(app)
    try:
        # بدون آیتم
        r0 = client.get("/api/cart-count")
        _check("cart-count endpoint 0", r0.status_code == 200 and r0.get_json().get("count") == 0,
               str(r0.get_json()))
        client.post(f"/shop/cart/add/{pid1}")
        client.post(f"/shop/cart/add/{pid2}")
        client.post(f"/shop/cart/add/{pid2}")
        r = client.get("/api/cart-count")
        _check("cart-count real (3)", r.get_json().get("count") == 3, str(r.get_json()))
        # drawer محتوای واقعی
        html = client.get("/shop").get_data(as_text=True)
        _check("drawer shows item 1", "UI شامپو مو" in html)
        _check("drawer shows item 2", "UI ماسک پوست" in html)
        _check("drawer total", "560,000" in html or "۵۶۰٬۰۰۰" in html, "drawer total")
        _check("drawer qty form", "/shop/cart/update/" in html)
        _check("drawer remove form", "/shop/cart/remove/" in html)
        _check("drawer checkout btn", "#checkout" in html and "تسویه سفارش" in html)
        _check("drawer view full btn", "/shop/cart" in html)
    finally:
        _cleanup(app)


def test_5_qty_change_in_drawer():
    app = create_app()
    client = app.test_client()
    _cleanup(app)
    pid1, pid2, pid3 = _add_products(app)
    try:
        client.post(f"/shop/cart/add/{pid1}")
        # تغییر تعداد در drawer از طریق همان route cart_update
        r = client.post(f"/shop/cart/update/{pid1}", data={"qty": "4"}, follow_redirects=True)
        _check("qty update ok", r.status_code in (200, 302))
        with client.session_transaction() as s:
            cart = s.get("giso_cart") or {}
        _check("qty updated to 4", cart.get(str(pid1)) == 4, str(cart))
    finally:
        _cleanup(app)


def test_6_7_product_page_buy_link_only_and_buy_banner():
    app = create_app()
    client = app.test_client()
    _cleanup(app)
    pid1, pid2, pid3 = _add_products(app)
    try:
        html = client.get(f"/shop/product/{pid1}").get_data(as_text=True)
        _check("buy-now is link", f'href="/shop/buy/{pid1}"' in html, "buy link")
        _check("no inline buy form on product", 'name="customer_name"' not in html,
               "form removed from detail")
        _check("add-to-cart form on product", f"/shop/cart/add/{pid1}" in html)
        _check("wishlist btn", "giso-wishlist-btn" in html)
        _check("guest note", "وارد حساب" in html)
        # /shop/buy/<id> همچنان فرم خرید را رندر می‌کند
        html2 = client.get(f"/shop/buy/{pid1}").get_data(as_text=True)
        _check("buy page form fields", 'name="customer_name"' in html2 and 'name="phone"' in html2 and 'name="address"' in html2)
        _check("buy page has product name", "UI شامپو مو" in html2)
    finally:
        _cleanup(app)


def test_8_9_checkout_and_notify():
    app = create_app()
    client = app.test_client()
    _cleanup(app)
    pid1, pid2, pid3 = _add_products(app)
    try:
        html0 = client.get("/shop/cart").get_data(as_text=True)
        client.post(f"/shop/cart/add/{pid1}")
        html = client.get("/shop/cart").get_data(as_text=True)
        _check("guest hint on cart", "وارد حساب" in html)
        client.post(f"/shop/cart/add/{pid2}")
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
                "customer_name": "مشتری UI", "phone": "09120000002", "address": "تهران"
            }, follow_redirects=True)
            _check("checkout ok", r.status_code in (200, 302))
            _check("admin notified", m.call_count == 1)
        with app.app_context():
            orders = ProductOrder.query.filter_by(phone="+989120000002").all()
            _check("orders created", len([o for o in orders if o.customer_name == "مشتری UI"]) == 2)
    finally:
        _cleanup(app)


def test_10_seo_routes_regression():
    app = create_app()
    client = app.test_client()
    _cleanup(app)
    pid1, pid2, pid3 = _add_products(app)
    try:
        h = client.get("/shop").get_data(as_text=True)
        _check("shop JSON-LD", '"@type": "ItemList"' in h)
        h2 = client.get(f"/shop/product/{pid1}").get_data(as_text=True)
        _check("product JSON-LD+OG", '"@type": "Product"' in h2 and "og:title" in h2)
        rb = client.get("/robots.txt").get_data(as_text=True)
        _check("robots", "Disallow: /admin" in rb and "sitemap.xml" in rb)
        sm = client.get("/sitemap.xml").get_data(as_text=True)
        _check("sitemap", "changefreq" in sm)
        rules = {r.rule for r in app.url_map.iter_rules()}
        for need in ("/shop", "/shop/cart", "/shop/cart/checkout", "/shop/buy/<int:product_id>",
                     "/shop/product/<int:product_id>", "/api/cart-count"):
            _check(f"route {need}", need in rules)
        _check("widget on shop", "ai_widget" in h or "aiWidget" in h or "widget" in h)
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
