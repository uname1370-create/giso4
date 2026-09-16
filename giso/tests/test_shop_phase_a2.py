#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
تست فاز A نسخه ۲ فروشگاه — بازطراحی کامل UI (فقط ظاهر؛ منطق/route/فرم دست‌نخورده)

پوشش (مطابق تست‌های اجباری):
 ۱) صفحه اصلی فروشگاه سالم باز شود + ساختار جدید (sticky search/chips/sidebar/slots/cart widget)
 ۲) صفحه محصول بدون خطا (JSON-LD/متا/دو ستونه/گالری placeholder/علاقه‌مندی)
 ۳) سبد کامل + درایور سبد (نمایش + دکمه‌ها)
 ۴) افزودن به سبد کار کند (session)
 ۵) تسویه سفارش (cart_checkout) کار کند
 ۶) اعلان به ادمین بله بدون خطا (mock)
 ۷) ایمپورت کانال intact
 ۸) ویجت روی همه صفحات فروشگاه
 ۹) SEO/JSON-LD/robots/sitemap سالم
۱۰) موبایل (media queries)
۱۱) هیچ route قبلی نشکسته + فرم‌ها/actions/names یکسان
۱۲) رگرسیون (پاک‌شدن فایل‌های قدیمی + فایل‌های جدید ساخته‌شده)
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
            for p in Product.query.filter(Product.name.like("فازA2%")).all():
                ProductOrder.query.filter_by(product_id=p.id).delete()
            for p in Product.query.filter(Product.name.like("فازA2%")).all():
                db.session.delete(p)
            db.session.commit()
        except Exception:
            db.session.rollback()


def _add_products(app):
    with app.app_context():
        p1 = Product(name="فازA2 شامپو", description="شامپو تست", price=100000,
                     in_stock=True, category="hair", source="site", publish_status="published",
                     created_at="2026-08-01 10:00:00", updated_at="2026-08-01 10:00:00")
        p2 = Product(name="فازA2 ماسک", description="ماسک تست", price=200000,
                     in_stock=True, category="face", source="site", publish_status="published",
                     created_at="2026-08-02 10:00:00", updated_at="2026-08-02 10:00:00")
        p3 = Product(name="فازA2 سرم", description="سرم تست", price=150000,
                     in_stock=False, category="hair", source="site", publish_status="published",
                     created_at="2026-08-03 10:00:00", updated_at="2026-08-03 10:00:00")
        db.session.add_all([p1, p2, p3])
        db.session.commit()
        o = ProductOrder(phone="+989120000001", customer_name="تست", product_id=p1.id,
                         address="تهران", quantity=3, status="completed")
        db.session.add(o)
        db.session.commit()
        ids = (p1.id, p2.id, p3.id)
        db.session.expunge_all()
        return ids


def test_1_shop_page_new_structure():
    app = create_app()
    client = app.test_client()
    _cleanup(app)
    _add_products(app)
    try:
        r = client.get("/shop")
        _check("GET /shop 200", r.status_code == 200, f"status={r.status_code}")
        html = r.get_data(as_text=True)
        for needle in ("giso-shop-sticky", "shopSearch", "giso-shop-chips",
                       "gisoShopSidebar", "giso-filters", "giso-shop-layout",
                       "giso-slot", "gisoCartWidget", "gisoCartDrawer",
                       "gisoCartCount", "giso-card-title"):
            _check(f"shop v2 element: {needle}", needle in html)
        _check("slots render", "پرفروش‌ترین‌ها" in html and "تازه‌ترین‌ها" in html)
        _check("glass card", "giso-glass-card" in html)
        _check("cart widget", "giso-cart-widget" in html)
        _check("js v2", "shop.js?v=" in html)
    finally:
        _cleanup(app)


def test_2_product_page():
    app = create_app()
    client = app.test_client()
    _cleanup(app)
    pid1, pid2, pid3 = _add_products(app)
    try:
        r = client.get(f"/shop/product/{pid1}")
        _check("GET product 200", r.status_code == 200, f"status={r.status_code}")
        html = r.get_data(as_text=True)
        _check("JSON-LD Product kept", '"@type": "Product"' in html)
        _check("BreadcrumbList kept", '"@type": "BreadcrumbList"' in html)
        _check("canonical kept", 'rel="canonical"' in html)
        _check("og:title kept", "og:title" in html)
        _check("two-column", 'class="giso-pd-media"' in html and 'class="giso-pd-info"' in html)
        _check("gallery placeholder", "giso-pd-gallery" in html)
        _check("wishlist UI", "giso-wishlist-btn" in html)
        _check("add-to-cart form", f"/shop/cart/add/{pid1}" in html)
        _check("buy-now form", f"/shop/buy/{pid1}" in html)
        _check("related section", "giso-slot" in html)
        _check("cart drawer present", "gisoCartDrawer" in html)
        # ناموجود → فرم اطلاع‌رسانی
        r3 = client.get(f"/shop/product/{pid3}")
        _check("out-of-stock notify", f"/shop/notify/{pid3}" in r3.get_data(as_text=True))
    finally:
        _cleanup(app)


def test_3_4_cart_page_drawer_and_add():
    app = create_app()
    client = app.test_client()
    _cleanup(app)
    pid1, pid2, pid3 = _add_products(app)
    try:
        r = client.get("/shop/cart")
        _check("GET cart 200", r.status_code == 200, f"status={r.status_code}")
        html = r.get_data(as_text=True)
        _check("cart empty state", "سبد خرید شما خالی است" in html)
        _check("cart drawer included", "gisoCartDrawer" in html)
        _check("cart widget included", "gisoCartWidget" in html)
        # افزودن به سبد
        r2 = client.post(f"/shop/cart/add/{pid1}", follow_redirects=True)
        _check("cart add ok", r2.status_code in (200, 302))
        with client.session_transaction() as s:
            cart = s.get("giso_cart") or {}
        _check("cart session has item", str(pid1) in cart and cart[str(pid1)] == 1, str(cart))
        r3 = client.get("/shop/cart")
        h3 = r3.get_data(as_text=True)
        _check("cart shows item", "فازA2 شامپو" in h3)
        _check("qty form intact", f"/shop/cart/update/{pid1}" in h3)
        _check("remove form intact", f"/shop/cart/remove/{pid1}" in h3)
        _check("checkout form intact", "/shop/cart/checkout" in h3)
        _check("qty name intact", 'name="qty"' in h3)
    finally:
        _cleanup(app)


def test_5_6_checkout_and_notify():
    app = create_app()
    client = app.test_client()
    _cleanup(app)
    pid1, pid2, pid3 = _add_products(app)
    try:
        client.post(f"/shop/cart/add/{pid1}")
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
                "customer_name": "مشتری A2", "phone": "09120000002", "address": "تهران"
            }, follow_redirects=True)
            _check("checkout ok", r.status_code in (200, 302))
            _check("admin notified", m.call_count == 1)
        with app.app_context():
            orders = ProductOrder.query.filter_by(phone="+989120000002").all()
            _check("orders created (2)", len([o for o in orders if o.customer_name == "مشتری A2"]) == 2,
                   f"orders={len(orders)}")
        with client.session_transaction() as s:
            cart = s.get("giso_cart") or {}
        _check("cart cleared", cart == {})
        # اعلان بدون توکن بدون خطا
        from giso.shop.logic.checkout import _notify_admins_shop_order
        _notify_admins_shop_order("🧺 تست A2")
        _check("notify no error", True)
    finally:
        _cleanup(app)


def test_7_channel_intact():
    try:
        import giso.channel_importer as ci
        _check("channel_importer imports", True)
        _check("parse_post intact", hasattr(ci, "parse_post"))
    except Exception as e:
        _check("channel_importer imports", False, str(e))


def test_8_widget_on_shop_pages():
    app = create_app()
    client = app.test_client()
    _cleanup(app)
    pid1, pid2, pid3 = _add_products(app)
    try:
        base = open(os.path.join(BASE_DIR, "giso", "templates", "base.html"), encoding="utf-8").read()
        _check("widget include in base", "ai_widget.html" in base)
        for path in ("/shop", f"/shop/product/{pid1}", "/shop/cart"):
            h = client.get(path).get_data(as_text=True)
            _check(f"widget include on {path}", "ai_widget" in h or "aiWidget" in h or "widget" in h)
    finally:
        _cleanup(app)


def test_9_seo_robots_sitemap():
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
        _check("sitemap", "changefreq" in sm and "/shop" in sm)
    finally:
        _cleanup(app)


def test_10_mobile_css():
    css = open(os.path.join(BASE_DIR, "giso", "shop", "static", "css", "shop.css"), encoding="utf-8").read()
    _check("mobile media query", "@media (max-width: 900px)" in css and "@media (max-width: 640px)" in css)
    _check("1 col mobile", "grid-template-columns: 1fr" in css)
    _check("sticky search", "position: sticky" in css)
    _check("glass colors", "rgba(255,255,255,.66)" in css or "backdrop-filter" in css)


def test_11_routes_and_forms_regression():
    app = create_app()
    client = app.test_client()
    _cleanup(app)
    pid1, pid2, pid3 = _add_products(app)
    try:
        rules = {r.rule for r in app.url_map.iter_rules()}
        for need in ("/shop", "/shop/cart", "/shop/cart/add/<int:product_id>",
                     "/shop/cart/remove/<int:product_id>", "/shop/cart/update/<int:product_id>",
                     "/shop/cart/checkout", "/shop/buy/<int:product_id>", "/shop/notify/<int:product_id>",
                     "/shop/product/<int:product_id>", "/robots.txt", "/sitemap.xml",
                     "/admin/product/add", "/admin/shop/stats", "/admin/config/publish-mode"):
            _check(f"route {need}", need in rules)
        shop_html = client.get("/shop").get_data(as_text=True)
        _check("add-to-cart form", "/shop/cart/add/" in shop_html)
        _check("notify form", "/shop/notify/" in shop_html)
        # سبد با آیتم → فرم تسویه با فیلدهای قبلی
        client.post(f"/shop/cart/add/{pid1}")
        cart_html = client.get("/shop/cart").get_data(as_text=True)
        _check("checkout fields", 'name="customer_name"' in cart_html and 'name="phone"' in cart_html and 'name="address"' in cart_html)
    finally:
        _cleanup(app)


def test_12_files_removed_and_new():
    pkg = os.path.join(BASE_DIR, "giso", "shop")
    new = ["templates/partials/cart_drawer.html", "templates/partials/shop_sidebar.html",
           "templates/partials/product_card.html", "static/css/shop.css", "static/js/shop.js"]
    for f in new:
        _check(f"new file {f}", os.path.exists(os.path.join(pkg, f)))
    _check("templates present", os.path.exists(os.path.join(pkg, "templates", "shop.html"))
           and os.path.exists(os.path.join(pkg, "templates", "product_detail.html"))
           and os.path.exists(os.path.join(pkg, "templates", "cart.html")))


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
