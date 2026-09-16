#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
تست فاز A فروشگاه — بازطراحی UI (فقط ظاهر؛ منطق/route/فرم دست‌نخورده)

پوشش (مطابق تست‌های اجباری):
 ۱) صفحه اصلی فروشگاه سالم باز شود + اسلات‌های جدید (پرفروش/تازه/موجود شد)
 ۲) صفحه محصول بدون خطا باز شود (JSON-LD/متا/بردکرامب حفظ)
 ۳) سبد خرید بدون خطا باز شود
 ۴) افزودن به سبد کار کند (session)
 ۵) خرید فوری کار کند (buy_product GET + POST)
 ۶) تسویه سفارش (cart_checkout) کار کند
 ۷) اعلان به ادمین بله بدون خطا (mock _notify_admins_shop_order)
 ۸) ایمپورت محصول از کانال بدون خطا (channel_importer مسیر intact — تست سبک)
 ۹) ویجت روی همه صفحات فروشگاه (ai_widget جزو base — وجود include)
۱۰) SEO/JSON-LD/robots/sitemap سالم
۱۱) موبایل تمیز (media queries در shop.css موجود است)
۱۲) رگرسیون مسیرهای قبلی (routes ثابت) + فرم‌های قدیمی (actions/names یکسان)
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
            # اول سفارش‌های مرتبط با محصولات تست حذف شوند (FK)
            for p in Product.query.filter(Product.name.like("فازA%")).all():
                ProductOrder.query.filter_by(product_id=p.id).delete()
            for p in Product.query.filter(Product.name.like("فازA%")).all():
                db.session.delete(p)
            db.session.commit()
        except Exception:
            db.session.rollback()



def _login_user(app, client, phone):
    """ورود به عنوان کاربر عضو (فاز جامع: خرید فقط با عضویت)."""
    from giso.models import User
    with app.app_context():
        User.query.filter(User.phone == phone).delete()
        db.session.add(User(phone=phone, password_hash="h", name="کاربر تست"))
        db.session.commit()
    with client.session_transaction() as st:
        st["_user_id"] = phone

def _add_products(app):
    with app.app_context():
        db.session.expire_all()
        p1 = Product(name="فازA شامپو مو", description="شامپو نرم‌کننده فازA", price=100000,
                     in_stock=True, category="hair", source="site", publish_status="published",
                     created_at="2026-08-01 10:00:00", updated_at="2026-08-01 10:00:00")
        p2 = Product(name="فازA ماسک پوست", description="ماسک آبرسان فازA", price=200000,
                     in_stock=True, category="face", source="site", publish_status="published",
                     created_at="2026-08-02 10:00:00", updated_at="2026-08-05 10:00:00")
        p3 = Product(name="فازA سرم مو", description="سرم ضدموخوره فازA", price=150000,
                     in_stock=False, category="hair", source="site", publish_status="published",
                     created_at="2026-08-03 10:00:00", updated_at="2026-08-03 10:00:00")
        p4 = Product(name="فازA روغن آرگان", description="روغن آرگان فازA", price=300000,
                     in_stock=True, category="hair", source="site", publish_status="published",
                     created_at="2026-08-04 10:00:00", updated_at="2026-08-04 10:00:00")
        db.session.add_all([p1, p2, p3, p4])
        db.session.commit()
        o = ProductOrder(phone="+989120000001", customer_name="تست", product_id=p1.id,
                         address="تهران", quantity=3, status="completed",
                         created_at=time.strftime("%Y-%m-%d %H:%M:%S"))
        db.session.add(o)
        db.session.commit()
        ids = (p1.id, p2.id, p3.id, p4.id)
        db.session.expunge_all()
        return ids


def test_1_shop_page_and_slots():
    app = create_app()
    client = app.test_client()
    _cleanup(app)
    pid1, pid2, pid3, pid4 = _add_products(app)
    try:
        r = client.get("/shop")
        _check("GET /shop 200", r.status_code == 200, f"status={r.status_code}")
        html = r.get_data(as_text=True)
        _check("top_sellers section", "پرفروش‌ترین‌ها" in html)
        _check("newest section", "تازه‌ترین‌ها" in html)
        _check("back_in_stock section", "تازه موجود شد" in html)
        _check("top seller is p1 (3 orders)", "فازA شامپو مو" in html)
        _check("fallback brand placeholder present", ("giso-card-fallback" in html or "giso-prod-fallback" in html) and "گیسو صادقی" in html)
        _check("cart float with count", 'id="gisoCartCount"' in html)
        _check("shop.css linked", "css/shop.css" in html)
    finally:
        _cleanup(app)


def test_2_product_page():
    app = create_app()
    client = app.test_client()
    _cleanup(app)
    pid1, pid2, pid3, pid4 = _add_products(app)
    try:
        r = client.get(f"/shop/product/{pid1}")
        _check("GET product 200", r.status_code == 200, f"status={r.status_code}")
        html = r.get_data(as_text=True)
        _check("JSON-LD Product kept", '"@type": "Product"' in html)
        _check("BreadcrumbList kept", '"@type": "BreadcrumbList"' in html)
        _check("canonical kept", 'rel="canonical"' in html)
        _check("og:title kept", "og:title" in html)
        _check("two-column classes", 'class="giso-pd-media"' in html and 'class="giso-pd-info"' in html)
        _check("wishlist UI button", 'giso-wishlist-btn' in html)
        _check("add-to-cart form action", f"/shop/cart/add/{pid1}" in html)
        _check("buy-now form action", f"/shop/buy/{pid1}" in html)
        # ناموجود → فرم اطلاع‌رسانی
        r3 = client.get(f"/shop/product/{pid3}")
        h3 = r3.get_data(as_text=True)
        _check("out-of-stock notify form", f"/shop/notify/{pid3}" in h3 and "موجود شد خبرم کن" in h3)
    finally:
        _cleanup(app)


def test_3_4_cart_page_and_add():
    app = create_app()
    client = app.test_client()
    _cleanup(app)
    pid1, pid2, pid3, pid4 = _add_products(app)
    try:
        r = client.get("/shop/cart")
        _check("GET cart 200", r.status_code == 200, f"status={r.status_code}")
        _check("cart empty state", "سبد خرید شما خالی است" in r.get_data(as_text=True))
        # افزودن به سبد
        r2 = client.post(f"/shop/cart/add/{pid1}", follow_redirects=True)
        _check("cart add 200/302", r2.status_code in (200, 302), f"status={r2.status_code}")
        with client.session_transaction() as s:
            cart = s.get("giso_cart") or {}
        _check("cart session has item", str(pid1) in cart and cart[str(pid1)] == 1, str(cart))
        r3 = client.get("/shop/cart")
        h3 = r3.get_data(as_text=True)
        _check("cart shows item", "فازA شامپو مو" in h3)
        _check("cart total", "100,000" in h3)
        _check("qty form intact", f"/shop/cart/update/{pid1}" in h3)
        _check("remove form intact", f"/shop/cart/remove/{pid1}" in h3)
        _check("checkout form intact", "/shop/cart/checkout" in h3)
        _check("qty name intact", 'name="qty"' in h3)
        _check("checkout fields intact",
               'name="customer_name"' in h3 and 'name="phone"' in h3 and 'name="address"' in h3)
    finally:
        _cleanup(app)


def test_5_buy_now():
    app = create_app()
    client = app.test_client()
    _cleanup(app)
    pid1, pid2, pid3, pid4 = _add_products(app)
    try:
        # GET → فرم خرید روی shop
        r = client.get(f"/shop/buy/{pid1}")
        _check("buy GET 200", r.status_code == 200, f"status={r.status_code}")
        html = r.get_data(as_text=True)
        _check("buy form renders", f"/shop/buy/{pid1}" in html and ("خرید:" in html or "خرید فوری" in html))
        _check("buy form fields intact", 'name="customer_name"' in html and 'name="phone"' in html and 'name="address"' in html)
        # POST با اعتبارسنجی شماره (شماره نرمال شود) — خرید فقط برای کاربر عضو
        _login_user(app, client, "09120000001")
        with patch("giso.shop.routes._notify_admins_shop_order") as mock_notify:
            r2 = client.post(f"/shop/buy/{pid1}", data={
                "customer_name": "مشتری فازA", "phone": "09120000001", "address": "تهران، تست"
            }, follow_redirects=True)
            _check("buy POST ok", r2.status_code in (200, 302), f"status={r2.status_code}")
            _check("admin notified", mock_notify.call_count == 1, f"calls={mock_notify.call_count}")
        with app.app_context():
            orders = ProductOrder.query.filter_by(phone="+989120000001").all()
            _check("order created", len(orders) >= 1, f"orders={len(orders)}")
            _check("order product", orders and orders[-1].product_id == pid1)
    finally:
        _cleanup(app)


def test_6_cart_checkout():
    app = create_app()
    client = app.test_client()
    _cleanup(app)
    pid1, pid2, pid3, pid4 = _add_products(app)
    try:
        client.post(f"/shop/cart/add/{pid1}")
        client.post(f"/shop/cart/add/{pid2}")
        _login_user(app, client, "09120000002")
        with patch("giso.shop.routes._notify_admins_shop_order") as mock_notify:
            r = client.post("/shop/cart/checkout", data={
                "customer_name": "مشتری سبد", "phone": "09120000002", "address": "تهران، تست سبد"
            }, follow_redirects=True)
            _check("checkout ok", r.status_code in (200, 302), f"status={r.status_code}")
            _check("admin notified for cart", mock_notify.call_count == 1)
        with app.app_context():
            orders = [o for o in ProductOrder.query.filter_by(phone="+989120000002").all()
                      if o.customer_name == "مشتری سبد"]
            _check("cart orders created (2)", len(orders) == 2, f"orders={len(orders)}")
        with client.session_transaction() as s:
            cart = s.get("giso_cart") or {}
        _check("cart cleared after checkout", cart == {}, str(cart))
    finally:
        _cleanup(app)


def test_7_admin_notify_no_error():
    """اعلان به ادمین بله بدون خطا — تست واقعی بدون توکن (باید بی‌صدا رد شود)."""
    app = create_app()
    client = app.test_client()
    _cleanup(app)
    pid1, pid2, pid3, pid4 = _add_products(app)
    try:
        # بدون توکن: _notify_admins_shop_order باید بدون exception برگردد
        from giso.shop import _notify_admins_shop_order
        _notify_admins_shop_order("🧺 تست اعلان فازA")
        _check("admin notify no error (no token)", True)
    finally:
        _cleanup(app)


def test_8_channel_import_intact():
    """channel_importer دست‌نخورده — ماژول import و مسیر ثبت پست کانال سالم است."""
    try:
        import giso.channel_importer as ci
        _check("channel_importer imports", True)
        _check("channel_importer has route hook", hasattr(ci, "parse_post") or hasattr(ci, "handle_channel_post") or hasattr(ci, "process_channel_post"))
    except Exception as e:
        _check("channel_importer imports", False, str(e))


def test_9_widget_on_all_shop_pages():
    app = create_app()
    client = app.test_client()
    _cleanup(app)
    pid1, pid2, pid3, pid4 = _add_products(app)
    try:
        base = open(os.path.join(BASE_DIR, "giso", "templates", "base.html"), encoding="utf-8").read()
        _check("widget include in base", "ai_widget.html" in base)
        for path in ("/shop", f"/shop/product/{pid1}", "/shop/cart"):
            r = client.get(path)
            h = r.get_data(as_text=True)
            _check(f"widget include on {path}", "ai_widget" in h or "aiWidget" in h or "widget" in h)
    finally:
        _cleanup(app)


def test_10_seo_robots_sitemap():
    app = create_app()
    client = app.test_client()
    _cleanup(app)
    pid1, pid2, pid3, pid4 = _add_products(app)
    try:
        r = client.get("/robots.txt")
        _check("robots 200", r.status_code == 200)
        rb = r.get_data(as_text=True)
        _check("robots disallow admin", "Disallow: /admin" in rb)
        _check("robots sitemap", "sitemap.xml" in rb)
        r2 = client.get("/sitemap.xml")
        _check("sitemap 200", r2.status_code == 200)
        sm = r2.get_data(as_text=True)
        _check("sitemap changefreq", "changefreq" in sm)
        _check("sitemap has shop", "<loc>" in sm and "/shop" in sm)
    finally:
        _cleanup(app)


def test_11_mobile_css():
    css = open(os.path.join(BASE_DIR, "giso", "shop", "static", "css", "shop.css"), encoding="utf-8").read()
    _check("shop.css exists", "shop.css" in css or len(css) > 100)
    _check("mobile media query", "@media (max-width: 640px)" in css and "grid-template-columns: 1fr" in css)
    _check("sticky mobile", "position: sticky" in css)
    _check("luxury palette", "rgba(255,255,255,.66)" in css or "backdrop-filter" in css or "#D4AF37" in css)


def test_12_routes_and_forms_regression():
    app = create_app()
    client = app.test_client()
    _cleanup(app)
    pid1, pid2, pid3, pid4 = _add_products(app)
    try:
        rules = {r.rule for r in app.url_map.iter_rules()}
        for need in ("/shop", "/shop/cart", "/shop/cart/add/<int:product_id>",
                     "/shop/cart/remove/<int:product_id>", "/shop/cart/update/<int:product_id>",
                     "/shop/cart/checkout", "/shop/buy/<int:product_id>", "/shop/notify/<int:product_id>",
                     "/shop/product/<int:product_id>", "/robots.txt", "/sitemap.xml",
                     "/admin/product/add", "/admin/product/<int:product_id>/publish",
                     "/admin/config/publish-mode", "/admin/config/channel-test"):
            _check(f"route {need}", need in rules)
        # فرم‌ها: actions و names قدیمی یکسان
        shop_html = client.get("/shop").get_data(as_text=True)
        _check("shop add-to-cart form action", "/shop/cart/add/" in shop_html)
        _check("shop notify form action", "/shop/notify/" in shop_html)
        _check("shop detail links", "/shop/product/" in shop_html)
        cart_html = client.get("/shop/cart").get_data(as_text=True)
        _check("cart page renders (empty)", "سبد خرید شما خالی است" in cart_html)
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
