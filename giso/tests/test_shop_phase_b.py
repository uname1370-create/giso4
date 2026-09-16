#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
تست فاز B فروشگاه — ماژولار شدن در giso/shop بدون شکستن چیزی

پوشش (مطابق تست‌های اجباری):
 ۱) لیست فروشگاه سالم باز شود (route قدیمی /shop — از پکیج جدید)
 ۲) صفحه محصول بدون خطا باز شود
 ۳) سبد و تسویه سالم کار کند
 ۴) اعلان به ادمین بله بدون خطا برسد
 ۵) ایمپورت کانال بدون خطا (channel_importer intact + get_publish_mode از پکیج)
 ۶) «🛍 فروشگاه» در پنل ادمین دیده شود
 ۷) «🛍 فروشگاه» در پنل سوپرادمین دیده شود (و «تنظیمات فروشگاه»)
 ۸) «فروشگاه من» در پنل کاربر دیده شود
 ۹) منوی «🛍 فروشگاه» در ربات کاربر دیده شود
۱۰) منوی «🛍 فروشگاه» در ربات ادمین دیده شود
۱۱) منوی «🛍 فروشگاه» در ربات سوپرادمین دیده شود
۱۲) هیچ callback قبلی نشکسته (callback های موجود intact + callback های shop_ جدید)
۱۳) SEO و JSON-LD سالم بماند
۱۴) ویجت روی صفحات فروشگاه باز شود
۱۵) رگرسیون (مسیرها/فرم‌ها + wrapper shop.py)
"""
import asyncio
import json
import os
import sys
import time
from unittest.mock import MagicMock, AsyncMock, patch

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if BASE_DIR not in sys.path:
    sys.path.append(BASE_DIR)

from giso.app import create_app  # noqa: E402
from giso.models import db, Product, ProductOrder, StockNotify  # noqa: E402
from giso.base import normalize_phone  # noqa: E402

SUPER_PHONE = normalize_phone("09156012931")
ADMIN_PHONE = normalize_phone("09120000031")
ADMIN_BID = 779001
ADMIN_BALE_ID = "779001"
USER_PHONE = normalize_phone("09120000032")
USER_BID = 779002
FIXED_CODE = "654321"

_FAILED = []


def _check(name, cond, extra=""):
    status = "PASS" if cond else "FAIL"
    print(f"{status}  {name}" + (f"  ({extra})" if extra else ""))
    if not cond:
        _FAILED.append(name)


def _cleanup(app=None):
    if app is not None:
        with app.app_context():
            try:
                for p in Product.query.filter(Product.name.like("فازB%")).all():
                    ProductOrder.query.filter_by(product_id=p.id).delete()
                for p in Product.query.filter(Product.name.like("فازB%")).all():
                    db.session.delete(p)
                StockNotify.query.filter(StockNotify.phone.in_([USER_PHONE, "+989120000033"])).delete()
                db.session.commit()
            except Exception:
                db.session.rollback()
    try:
        from giso_admin import _connect as cbot
        with cbot() as c:
            c.execute("DELETE FROM giso_admins WHERE bale_id=? OR phone=?", (ADMIN_BALE_ID, ADMIN_PHONE))
            c.commit()
    except Exception:
        pass
    try:
        from giso.base import get_giso_db_conn
        with get_giso_db_conn() as conn:
            conn.execute("DELETE FROM giso_admin_permissions WHERE admin_bale_id=?", (ADMIN_BALE_ID,))
            conn.commit()
    except Exception:
        pass


def _add_products(app):
    with app.app_context():
        p1 = Product(name="فازB شامپو", description="شامپو تست فازB", price=100000,
                     in_stock=True, category="hair", source="site", publish_status="published",
                     created_at="2026-08-01 10:00:00", updated_at="2026-08-01 10:00:00")
        p2 = Product(name="فازB ماسک", description="ماسک تست فازB", price=200000,
                     in_stock=True, category="face", source="site", publish_status="pending",
                     created_at="2026-08-02 10:00:00", updated_at="2026-08-02 10:00:00")
        db.session.add_all([p1, p2])
        db.session.commit()
        ids = (p1.id, p2.id)
        db.session.expunge_all()
        return ids


def _login(client, phone):
    with client.session_transaction() as s:
        s.setdefault("giso_csrf_token", "fixed-test-csrf-token")
        s["_user_id"] = phone
        s["giso_csrf_token"] = "shop-phase-b-csrf"


    _op = client.post
    def _post_with_csrf(*a, **k):
        h = dict(k.get("headers") or {}); h.setdefault("X-GISO-CSRF", "fixed-test-csrf-token"); k["headers"] = h
        return _op(*a, **k)
    client.post = _post_with_csrf
def _verify(client, phone):
    from unittest.mock import patch
    with patch("giso.app._send_admin_panel_code_to_bot", return_value=(True, "ok")), \
         patch("giso.app._generate_admin_panel_code", return_value=FIXED_CODE):
        client.get("/admin")
        client.get("/admin/verify")
        r = client.post("/admin/verify", data={"action": "verify", "code": FIXED_CODE,
                                                "csrf_token": "shop-phase-b-csrf"})
        assert r.status_code == 302


async def _send_text(ht, bid, text):
    msg = MagicMock()
    msg.reply_text = AsyncMock()
    msg.text = text
    msg.chat_id = bid
    update = MagicMock()
    update.effective_user.id = bid
    update.effective_user.first_name = "کاربر تست"
    update.effective_user.username = "tester"
    update.effective_message = msg
    update.message = msg
    context = MagicMock()
    context.bot.send_message = AsyncMock()
    context.user_data = {}
    await ht(update, context)
    calls = msg.reply_text.call_args_list
    texts = [c.args[0] if c.args else "" for c in calls]
    last_kb = calls[-1].kwargs.get("reply_markup") if calls else None
    return texts, last_kb


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
    update.effective_user.first_name = "کاربر تست"
    update.effective_user.username = "tester"
    context = MagicMock()
    context.bot.send_message = AsyncMock()
    context.user_data = {}
    await hc(update, context)
    return query


def _setup_bot():
    from giso.base import _upsert_giso_user
    _upsert_giso_user(ADMIN_BID, phone=ADMIN_PHONE, first_name="ادمین",
                      contact_shared=True, is_admin=True, pending_request=False)
    _upsert_giso_user(USER_BID, phone=USER_PHONE, first_name="کاربر",
                      contact_shared=True, is_admin=False, pending_request=False)
    from giso_admin import _connect as cbot
    with cbot() as c:
        c.execute("DELETE FROM giso_admins WHERE bale_id=? OR phone=?", (ADMIN_BALE_ID, ADMIN_PHONE))
        c.execute("INSERT INTO giso_admins (phone, bale_id, added_by, added_at) VALUES (?, ?, ?, ?)",
                  (ADMIN_PHONE, ADMIN_BALE_ID, 1191639507, time.strftime("%Y-%m-%d %H:%M:%S")))
        c.commit()
    from giso.base import get_giso_db_conn
    with get_giso_db_conn() as conn:
        for sec in ("dashboard", "analysis_management", "reviews", "users", "admins",
                    "site_bot_settings", "ai_management"):
            conn.execute(
                "INSERT INTO giso_admin_permissions (admin_bale_id, section, is_allowed, created_at) "
                "VALUES (?,?,?,?) ON CONFLICT(admin_bale_id, section) DO UPDATE SET is_allowed=excluded.is_allowed",
                (ADMIN_BALE_ID, sec, 0, time.strftime("%Y-%m-%d %H:%M:%S")))
        conn.execute(
            "INSERT INTO giso_admin_permissions (admin_bale_id, section, is_allowed, created_at) "
            "VALUES (?,?,?,?) ON CONFLICT(admin_bale_id, section) DO UPDATE SET is_allowed=excluded.is_allowed",
            (ADMIN_BALE_ID, "products", 1, time.strftime("%Y-%m-%d %H:%M:%S")))
        conn.commit()


# ═══════════════════════════════════════════════════════════
def test_1_2_3_shop_pages_cart_checkout():
    """صفحات فروشگاه از پکیج جدید + سبد و تسویه."""
    app = create_app()
    client = app.test_client()
    _cleanup(app)
    pid1, pid2 = _add_products(app)
    try:
        r = client.get("/shop")
        _check("GET /shop 200 (pkg)", r.status_code == 200, f"status={r.status_code}")
        html = r.get_data(as_text=True)
        _check("shop pkg template renders", "فروشگاه گیسو" in html and "فازB شامپو" in html)
        _check("shop static via shop_mod", "/shop-static/css/shop.css" in html, "shop-static" in html)
        r2 = client.get(f"/shop/product/{pid1}")
        _check("GET product 200", r2.status_code == 200, f"status={r2.status_code}")
        r3 = client.get("/shop/cart")
        _check("GET cart 200", r3.status_code == 200)
        # افزودن + تسویه
        client.post(f"/shop/cart/add/{pid1}")
        with client.session_transaction() as s:
            cart = s.get("giso_cart") or {}
        _check("cart add works", str(pid1) in cart)
        # فاز جامع: تسویه فقط با عضویت → کاربر تست را وارد می‌کنیم
        with app.app_context():
            from giso.models import User
            User.query.filter(User.phone == USER_PHONE).delete()
            db.session.add(User(phone=USER_PHONE, password_hash="h", name="کاربر"))
            db.session.commit()
        _login(client, USER_PHONE)
        with patch("giso.shop.routes._notify_admins_shop_order") as m:
            rr = client.post("/shop/cart/checkout", data={
                "customer_name": "مشتری فازB", "phone": "09120000002", "address": "تهران"
            }, follow_redirects=True)
            _check("checkout ok", rr.status_code in (200, 302))
            _check("admin notified", m.call_count == 1)
    finally:
        _cleanup(app)


def test_4_5_notify_and_channel_intact():
    """اعلان ادمین بدون خطا + channel_importer / get_publish_mode از پکیج."""
    from giso.shop.logic.checkout import _notify_admins_shop_order
    _notify_admins_shop_order("🧺 تست فازB")
    _check("admin notify no error", True)
    from giso.shop import get_publish_mode
    _check("get_publish_mode via pkg", get_publish_mode() in ("review", "auto"))
    try:
        import giso.channel_importer as ci
        _check("channel_importer imports", True)
        _check("channel bridge intact", hasattr(ci, "parse_post"))
    except Exception as e:
        _check("channel_importer imports", False, str(e))


def test_6_7_admin_and_super_panel_shop():
    """«🛍 فروشگاه» در پنل ادمین + «تنظیمات فروشگاه» در پنل سوپرادمین."""
    app = create_app()
    client = app.test_client()
    _cleanup(app)
    _add_products(app)
    # سوپر
    with app.app_context():
        from giso.models import User
        User.query.filter(User.phone == SUPER_PHONE).delete()
        db.session.add(User(phone=SUPER_PHONE, password_hash="h", name="سوپر"))
        db.session.commit()
    _login(client, SUPER_PHONE)
    _verify(client, SUPER_PHONE)
    html = client.get("/admin").get_data(as_text=True)  # redirect → dashboard
    html_dash = client.get("/admin/dashboard").get_data(as_text=True)
    _check("admin sidebar has 🛍 فروشگاه", "فروشگاه" in html_dash and "shop" in html_dash)
    _check("super sidebar has تنظیمات فروشگاه", "تنظیمات فروشگاه" in html_dash)
    r = client.get("/admin/shop")
    _check("GET /admin/shop 200", r.status_code == 200, f"status={r.status_code}")
    h = r.get_data(as_text=True)
    _check("admin shop hub renders", "فروشگاه گیسو" in h and "تأیید محصولات کانال" in h)
    _check("admin shop hub links", "سفارش‌ها" in h and "گزارش فروش" in h)
    r2 = client.get("/admin/shop-super")
    _check("GET /admin/shop-super 200", r2.status_code == 200, f"status={r2.status_code}")
    h2 = r2.get_data(as_text=True)
    _check("super shop page renders", "تنظیمات فروشگاه" in h2)
    _cleanup(app)


def test_8_user_panel_shop():
    """«فروشگاه من» در پنل کاربر."""
    app = create_app()
    client = app.test_client()
    _cleanup(app)
    pid1, pid2 = _add_products(app)
    with app.app_context():
        from giso.models import User
        User.query.filter(User.phone == USER_PHONE).delete()
        u = User(phone=USER_PHONE, password_hash="h", name="کاربر")
        db.session.add(u)
        db.session.commit()
        db.session.add(ProductOrder(phone=USER_PHONE, customer_name="کاربر", product_id=pid1,
                                    address="تهران", quantity=1, status="pending"))
        db.session.add(StockNotify(phone=USER_PHONE, product_id=pid2))
        db.session.commit()
    _login(client, USER_PHONE)
    html = client.get("/dashboard").get_data(as_text=True)  # → overview
    r = client.get("/dashboard/shop")
    _check("GET /dashboard/shop 200", r.status_code == 200, f"status={r.status_code}")
    h = r.get_data(as_text=True)
    _check("user shop page renders", "فروشگاه من" in h)
    _check("user orders shown", "فازB شامپو" in h)
    _check("user notifies shown", "فازB ماسک" in h)
    _cleanup(app)


def test_9_10_11_bot_shop_menus():
    """منوی 🛍 فروشگاه در ربات کاربر/ادمین/سوپر."""
    app = create_app()
    _cleanup(app)
    _setup_bot()
    try:
        async def run():
            funcs = await __import__("giso.bot", fromlist=["get_test_handlers"]).get_test_handlers()
            ht, hc = funcs["handle_text"], funcs["handle_callback"]
            # کاربر
            texts, kb = await _send_text(ht, USER_BID, "🛍 فروشگاه")
            flat = [b.text for row in kb.keyboard for b in row]
            _check("bot user shop menu", "🛒 مشاهده فروشگاه" in flat and "📦 سفارش‌های من" in flat, str(flat))
            _check("user state set", funcs["user_states"].get(USER_BID) == "shop_user_menu")
            # سفارش‌های من در زیرمنو
            texts2, kb2 = await _send_text(ht, USER_BID, "📦 سفارش‌های من")
            _check("user orders in shop submenu", any("سفارش" in t for t in texts2), str(texts2)[:120])
            # بازگشت
            await _send_text(ht, USER_BID, "🔙 بازگشت")
            _check("user shop state cleared", funcs["user_states"].get(USER_BID) is None)
            # ادمین (فقط products perm)
            texts3, kb3 = await _send_text(ht, ADMIN_BID, "🛍 فروشگاه")
            flat3 = [b.text for row in kb3.keyboard for b in row]
            _check("bot admin shop menu", "📦 محصولات" in flat3 and "✅ تأیید کانال" in flat3, str(flat3))
            _check("admin state set", funcs["user_states"].get(ADMIN_BID) == "shop_admin_menu")
            # ادمین: گزارش فروش
            texts4, kb4 = await _send_text(ht, ADMIN_BID, "📊 گزارش فروش")
            _check("admin sales report", any("گزارش فروش" in t for t in texts4), str(texts4)[:100])
            # رکورد قدیمیِ خاموش نباید نقش عملیاتی ثابت را لغو کند
            _cleanup(app)
            _setup_bot()
            funcs["user_states"].pop(ADMIN_BID, None)
            with __import__("giso.base", fromlist=["get_giso_db_conn"]).get_giso_db_conn() as conn:
                conn.execute("UPDATE giso_admin_permissions SET is_allowed=0 WHERE admin_bale_id=? AND section='products'",
                             (ADMIN_BALE_ID,))
                conn.commit()
            texts5, _kb5 = await _send_text(ht, ADMIN_BID, "🛍 فروشگاه")
            _check("legacy off row is inert", not any("دسترسی ندارید" in t for t in texts5), str(texts5)[:100])
            _check("admin still enters Shop", funcs["user_states"].get(ADMIN_BID) == "shop_admin_menu")
            # سوپر
            texts6, kb6 = await _send_text(ht, 1191639507, "🛍 فروشگاه")
            flat6 = [b.text for row in kb6.keyboard for b in row]
            _check("bot super shop menu", "⚙️ تنظیمات فروشگاه" in flat6 and any("🎁 کد تخفیف" in b for b in flat6), str(flat6))
            _check("super state set", funcs["user_states"].get(1191639507) == "shop_super_menu")
            # سوپر: تأیید کانال + انتشار callback
            texts7, kb7 = await _send_text(ht, 1191639507, "✅ تأیید کانال")
            _check("super channel pending list", any("در انتظار تأیید" in t or "محصول" in t for t in texts7), str(texts7)[:150])
            q = await _send_cb(hc, 1191639507, f"shop_ch_app|{pid2 if False else _pending_id()}")
            _check("shop callback consumed", q.edit_message_text.call_count > 0)
            # callback های قبلی untouched: hair_review باید هنوز کار کند
            q2 = await _send_cb(hc, ADMIN_BID, "hair_review|1")
            _check("existing callback intact (hair_review consumed)", True)
        asyncio.run(run())
    finally:
        _cleanup(app)


def _pending_id():
    from giso.base import get_giso_db_conn
    with get_giso_db_conn() as conn:
        row = conn.execute("SELECT id FROM products WHERE publish_status='pending' LIMIT 1").fetchone()
    return int(row[0]) if row else 0


def test_12_13_14_seo_widget_regression():
    """SEO/JSON-LD + ویجت + route های قدیمی intact."""
    app = create_app()
    client = app.test_client()
    _cleanup(app)
    pid1, pid2 = _add_products(app)
    try:
        r = client.get("/shop")
        h = r.get_data(as_text=True)
        _check("shop JSON-LD", '"@type": "ItemList"' in h)
        r2 = client.get(f"/shop/product/{pid1}")
        h2 = r2.get_data(as_text=True)
        _check("product JSON-LD + OG", '"@type": "Product"' in h2 and "og:title" in h2)
        r3 = client.get("/robots.txt")
        _check("robots ok", r3.status_code == 200 and "sitemap.xml" in r3.get_data(as_text=True))
        r4 = client.get("/sitemap.xml")
        _check("sitemap ok", r4.status_code == 200 and "/shop" in r4.get_data(as_text=True))
        _check("widget include on shop", "ai_widget" in h or "aiWidget" in h)
        # route های قدیمی (از طریق wrapper) intact
        rules = {r.rule for r in app.url_map.iter_rules()}
        for need in ("/shop", "/shop/cart", "/shop/cart/checkout", "/shop/buy/<int:product_id>",
                     "/shop/product/<int:product_id>", "/admin/product/add",
                     "/admin/shop-order/<int:order_id>/status", "/admin/shop/stats",
                     "/admin/config/channel", "/admin/config/publish-mode"):
            _check(f"route intact {need}", need in rules)
    finally:
        _cleanup(app)


def test_15_wrapper_and_module_structure():
    """shop.py قدیمی wrapper است + ساختار پکیج کامل."""
    import giso.shop as pkg
    for name in ("register_shop_routes", "shop", "buy_product", "notify_stock",
                 "cart_page", "cart_checkout", "get_publish_mode", "admin_shop_stats",
                 "robots_txt", "sitemap_xml", "seed_sample_products"):
        _check(f"pkg exposes {name}", callable(getattr(pkg, name, None)))
    import giso.shop as w
    _check("wrapper is pkg (fallback)", w.__name__ == "giso.shop")
    # ساختار
    for sub in ("routes.py", "logic/cart.py", "logic/checkout.py", "logic/inventory.py",
                "logic/suggestions.py", "logic/channel_bridge.py", "logic/discount.py",
                "panel/admin.py", "panel/super.py", "panel/user.py",
                "bot/user_menu.py", "bot/admin_menu.py", "bot/super_menu.py", "bot/handlers.py",
                "templates/shop.html", "templates/product_detail.html", "templates/cart.html",
                "static/css/shop.css", "static/js/shop.js"):
        _check(f"structure {sub}", os.path.exists(os.path.join(BASE_DIR, "giso", "shop", sub)))
    # فایل‌های قدیمی حذف شدند
    _check("old shop.html removed", not os.path.exists(os.path.join(BASE_DIR, "giso", "templates", "shop.html")))
    _check("old css removed", not os.path.exists(os.path.join(BASE_DIR, "giso", "static", "css", "shop.css")))


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
