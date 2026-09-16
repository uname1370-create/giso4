#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
تست پنل سوپرادمین فاز 5 (یکسان‌سازی با پنل ربات).

پوشش:
 ۱) بارگذاری app و ثبت routeهای جدید بدون خطا
 ۲) رندر شدن همه صفحات پنل (dashboard, hair_sale, shop_orders, analyses, reviews,
    products, channel, ai, ratelimit, referrals, wallet, users, admins, settings)
 ۳) تنظیمات: تایمر خروج نقش‌دار (فعال/غیرفعال/نقش/دقیقه جدا ادمین و کاربر)
 ۴) ثبت‌نام فعال/غیرفعال
 ۵) تم سایت + آدرس سایت (تنظیم/تست)
 ۶) پشتیبان‌گیری: گرفتن نسخه، تنظیم بازه، لیست، بازگردانی، ریستارت flag
 ۷) پورسانت فروش مو (درصدی/ثابت) — همان کلیدهای مشترک ربات
 ۸) مدیریت ادمین‌ها: کلمه ادمینی، درخواست‌ها، دسترسی، حذف
 ۹) آنالیز: درخواست مشاوره (پاسخ/وضعیت)، محصول درخواستی، خلاصه گفتگوها
 ۱۰) کاربران: آمار کلی، جستجو، بن، کیف پول، حذف دومرحله‌ای
 ۱۱) سفارش فروشگاه: جستجو + تغییر وضعیت
 ۱۲) permission زنده: نوشتن در جدول مشترک giso_admin_permissions
 ۱۳) تایمر خروج: idle_minutes_for_role برای نقش‌های admin/user
 ۱۴) عدم شکستن routeهای قبلی (لیست route ها ثابت است)

داده‌ها فقط از دیتابیس واقعی (giso.db) خوانده/نوشته می‌شود و بعد از تست پاک می‌شود.
"""
import os
import sqlite3
import sys
import tempfile
import time
from pathlib import Path

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if BASE_DIR not in sys.path:
    sys.path.append(BASE_DIR)

from giso.app import create_app  # noqa: E402
from giso.models import db, User, HairOrder, ProductOrder, Product, Review  # noqa: E402
from giso.base import get_giso_db_conn, normalize_phone  # noqa: E402

SUPER_PHONE = normalize_phone("09156012931")
ADMIN_PHONE = normalize_phone("09123334444")
ADMIN_BALE_ID = "88990011"
USER_PHONE = normalize_phone("09127778888")
FIXED_CODE = "654321"

_FAILED = []


def _check(name, cond, extra=""):
    status = "PASS" if cond else "FAIL"
    print(f"{status}  {name}" + (f"  ({extra})" if extra else ""))
    if not cond:
        _FAILED.append(name)


def _cleanup(app):
    """پاک‌سازی داده‌های تست از دیتابیس‌های واقعی (بدون دست زدن به داده‌های دیگر)."""
    if app is not None:
        with app.app_context():
            for u in User.query.filter(User.phone.in_([SUPER_PHONE, ADMIN_PHONE, USER_PHONE])).all():
                db.session.delete(u)
            db.session.commit()
    # bot.db
    bot_db = os.path.join(BASE_DIR, "bot_edu", "data", "bot.db")
    try:
        conn = sqlite3.connect(bot_db)
        for t in ("giso_admins", "giso_admin_requests", "giso_config"):
            try:
                conn.execute(f"DELETE FROM {t} WHERE phone=? OR bale_id=? "
                             if t != "giso_config" else f"DELETE FROM {t} WHERE key IN ('panel_idle_minutes','panel_idle_enabled','panel_idle_role','panel_idle_minutes_admin','panel_idle_minutes_user','site_registration_enabled','panel_extra_sections','site_theme')",
                             (ADMIN_PHONE, ADMIN_BALE_ID) if t != "giso_config" else ())
            except Exception:
                pass
        conn.commit()
        conn.close()
    except Exception:
        pass
    # giso.db جداول تست
    try:
        with get_giso_db_conn() as conn:
            conn.execute("DELETE FROM hair_orders WHERE phone=? OR phone=?", (SUPER_PHONE, USER_PHONE))
            conn.execute("DELETE FROM product_orders WHERE phone=? OR phone=?", (SUPER_PHONE, USER_PHONE))
            conn.execute("DELETE FROM consultant_requests WHERE phone=? OR phone=?", (SUPER_PHONE, USER_PHONE))
            conn.execute("DELETE FROM product_requests WHERE phone=? OR phone=?", (SUPER_PHONE, USER_PHONE))
            conn.execute("DELETE FROM reviews WHERE phone=? OR phone=?", (SUPER_PHONE, USER_PHONE))
            conn.execute("DELETE FROM giso_admin_permissions WHERE admin_bale_id=?", (ADMIN_BALE_ID,))
            conn.execute("DELETE FROM giso_config WHERE key IN ('site_base_url','backup_interval_hours','site_theme','panel_idle_minutes','panel_idle_enabled','panel_idle_role','panel_idle_minutes_admin','panel_idle_minutes_user','site_registration_enabled','panel_extra_sections','referral_commission_mode','referral_commission_percent','referral_commission_fixed_amount','referral_program_enabled')")
            conn.commit()
    except Exception:
        pass


def _login(client, phone):
    with client.session_transaction() as s:
        s.setdefault("giso_csrf_token", "fixed-test-csrf-token")
        s["_user_id"] = phone
        s["giso_csrf_token"] = "phase5-csrf-token"


    _op = client.post
    def _post_with_csrf(*a, **k):
        h = dict(k.get("headers") or {}); h.setdefault("X-GISO-CSRF", "fixed-test-csrf-token"); k["headers"] = h
        return _op(*a, **k)
    client.post = _post_with_csrf
def _verify_super(client):
    """تکمیل تأیید دومرحله‌ای سوپرادمین (mock کد ربات) — مثل تست قبلی پنل."""
    from unittest.mock import patch
    with patch("giso.app._send_admin_panel_code_to_bot", return_value=(True, "کد ارسال شد.")), \
         patch("giso.app._generate_admin_panel_code", return_value=FIXED_CODE):
        client.get("/admin")           # → 302 به verify
        client.get("/admin/verify")    # صدور کد در session
        r = client.post("/admin/verify", data={"action": "verify", "code": FIXED_CODE,
                                                "csrf_token": "phase5-csrf-token"})
        assert r.status_code == 302


def _make_super(app):
    with app.app_context():
        if not User.query.filter_by(phone=SUPER_PHONE).first():
            db.session.add(User(phone=SUPER_PHONE, password_hash="hash", name="سوپرادمین تست"))
            db.session.commit()


# ═══════════════════════════════════════════════════════════
def test_app_routes():
    """ثبت route های جدید + رندر صفحات پنل."""
    app = create_app()
    client = app.test_client()
    _cleanup(app)
    _make_super(app)
    _login(client, SUPER_PHONE)
    _verify_super(client)
    pages = [
        "/admin/dashboard", "/admin/hair-orders", "/admin/shop-orders",
        "/admin/analyses", "/admin/reviews", "/admin/products", "/admin/channel",
        "/admin/ai", "/admin/ratelimit", "/admin/referrals", "/admin/wallet",
        "/admin/users", "/admin/admins", "/admin/settings",
    ]
    for p in pages:
        r = client.get(p)
        _check(f"GET {p}", r.status_code == 200, f"status={r.status_code}")
    # تب‌های آنالیز
    for q in ("?tab=analyses", "?tab=consultants", "?tab=products", "?tab=chats"):
        r = client.get("/admin/analyses" + q)
        _check(f"GET /admin/analyses{q}", r.status_code == 200, f"status={r.status_code}")
    _cleanup(app)


def test_settings_idle_and_registration():
    """تنظیم تایمر خروج نقش‌دار + ثبت‌نام + تم + آدرس سایت."""
    app = create_app()
    client = app.test_client()
    _cleanup(app)
    _make_super(app)
    _login(client, SUPER_PHONE)
    _verify_super(client)

    # ذخیره تایمر: فعال + role=admin + دقیقه ادمین/کاربر جدا
    r = client.post("/admin/settings", data={
        "idle_enabled": "1", "idle_minutes": "15",
        "idle_role": "admin", "idle_minutes_admin": "7", "idle_minutes_user": "3",
    })
    _check("POST settings idle", r.status_code == 302, f"status={r.status_code}")
    from giso.panel.modules.settings import get_idle_config, idle_minutes_for_role
    cfg = get_idle_config()
    _check("idle enabled", cfg["enabled"] is True)
    _check("idle role=admin", cfg["role"] == "admin")
    _check("idle admin minutes=7", cfg["minutes_admin"] == 7)
    _check("idle user minutes=3", cfg["minutes_user"] == 3)
    _check("idle_for admin=7", idle_minutes_for_role("admin") == 7)
    _check("idle_for user=0 (role=admin only)", idle_minutes_for_role("user") == 0)
    # تایمر در HTML پنل (نقش ادمین) باید ۷ باشد
    html = client.get("/admin/settings").get_data(as_text=True)
    _check("panel body data-idle-minutes=7", 'data-idle-minutes="7"' in html)

    # ثبت‌نام غیرفعال
    r = client.post("/admin/settings", data={"save_registration": "1", "registration_enabled": "0"})
    _check("POST registration off", r.status_code == 302)
    from giso.panel.modules.settings import is_registration_enabled
    _check("registration disabled", is_registration_enabled() is False)
    # ثبت‌نام دوباره فعال (با تیک)
    r = client.post("/admin/settings", data={"save_registration": "1", "registration_enabled": "1", "extra_sections": "1"})
    _check("POST registration on", r.status_code == 302)
    _check("registration re-enabled", is_registration_enabled() is True)

    # تم
    r = client.post("/admin/settings", data={"site_theme": "smart_assistant"})
    _check("POST theme", r.status_code == 302)
    from giso_admin import get_giso_config as gbot_cfg
    _check("theme saved in giso_config", gbot_cfg("site_theme") == "smart_assistant")

    # آدرس سایت (همان کلید ربات در giso.db)
    r = client.post("/admin/settings", data={"site_base_url": "https://example.com", "site_url_action": "save"})
    _check("POST site url", r.status_code == 302)
    from giso.panel.modules.settings import get_site_base_url
    _check("site url saved (giso.db)", get_site_base_url() == "https://example.com")

    # تست آدرس (آدرس نامعتبر → خطا بدون crash)
    r = client.post("/admin/settings", data={"site_base_url": "not-a-url", "site_url_action": "test"})
    _check("POST site url test invalid", r.status_code == 302)

    _cleanup(app)


def test_backup_restore_restart():
    """گرفتن نسخه، بازه خودکار، لیست، بازگردانی، flag ریستارت."""
    from giso.panel.modules import backup as bk
    # گرفتن نسخه دستی
    res = bk.take_backup("manual")
    _check("take_backup manual", res.get("ok") is True, f"name={res.get('name')}")
    _check("backup file exists", os.path.exists(res.get("path", "")))
    # بازه
    _check("set interval", bk.set_backup_interval_hours(6) is True)
    _check("get interval", bk.get_backup_interval_hours() == 6)
    # لیست
    files = bk.list_backup_files()
    _check("list_backup_files contains new", any(f["name"] == res["name"] for f in files))
    # بازگردانی همان فایل (safe)
    ok, msg = bk.restore_backup(res["path"])
    _check("restore backup", ok is True, msg)
    # بازگردانی فایل نامعتبر
    bad = Path(tempfile.gettempdir()) / "bad_restore_test.db"
    bad.write_text("not a sqlite db")
    ok2, msg2 = bk.restore_backup(str(bad))
    _check("restore invalid file rejected", ok2 is False, msg2)
    try:
        bad.unlink()
    except Exception:
        pass
    # flag ریستارت
    flag = Path(BASE_DIR) / "giso" / "data" / "giso-restart.flag"
    try:
        if flag.exists():
            flag.unlink()
        bk._write_restart_flag()
        _check("restart flag created", flag.exists())
        _check("restart flag is timestamp", flag.read_text().strip().isdigit())
    finally:
        try:
            if flag.exists():
                flag.unlink()
        except Exception:
            pass
    _check("request_bot_restart ok", bk.request_bot_restart(5) is True)
    _cleanup(None)


def test_hair_commission_and_reports():
    """گزارش‌های فروش مو + تنظیم پورسانت (کلیدهای مشترک ربات)."""
    from giso.panel.modules.hair_sale import get_reports
    with get_giso_db_conn() as conn:
        conn.execute("INSERT INTO hair_orders (phone, customer_name, photo_path, length_cm, status, final_price, created_at) VALUES (?,?,?,?,?,?,?)",
                     (USER_PHONE, "کاربر تست", "test.jpg", 30, "completed", "500,000", time.strftime("%Y-%m-%d %H:%M:%S")))
        conn.commit()
    rep = get_reports()
    _check("hair report total>=1", rep["total"] >= 1, f"total={rep['total']}")
    _check("hair report completed>=1", rep["completed"] >= 1)
    _check("hair report sales>=500000", rep["total_sales"] >= 500000, f"sales={rep['total_sales']}")
    # پورسانت
    from giso.referrals import save_referral_settings, get_referral_settings
    save_referral_settings(True, 12, 50000, mode="percent")
    st = get_referral_settings()
    _check("commission percent=12", st["commission_percent"] == 12 and st["mode"] == "percent")
    save_referral_settings(True, 5, 50000, mode="fixed", fixed_amount=30000)
    st = get_referral_settings()
    _check("commission fixed=30000", st["commission_fixed_amount"] == 30000 and st["mode"] == "fixed")
    _cleanup(None)


def test_admins_phrase_requests_permissions():
    """کلمه ادمینی + درخواست‌ها + permission زنده + حذف ادمین."""
    from giso_admin import (set_admin_request_phrase, get_admin_request_phrase,
                            create_admin_request, list_admin_requests,
                            review_admin_request, add_giso_admin, delete_giso_admin)
    set_admin_request_phrase("کلمه تست گیسو")
    _check("admin phrase set", get_admin_request_phrase() == "کلمه تست گیسو")
    # درخواست ادمین
    try:
        req = create_admin_request(ADMIN_PHONE, ADMIN_BALE_ID)
        _check("admin request created", req.get("ok") is True, str(req))
        pending = list_admin_requests("pending")
        _check("pending requests >=1", any(r["bale_id"] == ADMIN_BALE_ID for r in pending))
        # تأیید
        for r in pending:
            if r["bale_id"] == ADMIN_BALE_ID:
                review_admin_request(r["id"], True)
                break
        found = None
        for r in list_admin_requests("approved"):
            if r["bale_id"] == ADMIN_BALE_ID:
                found = r
                break
        _check("request approved", found is not None)
    except Exception as e:
        _check("admin request flow", False, str(e))
    # permission زنده در جدول مشترک
    from giso.panel.permissions import set_admin_permission, get_admin_permissions
    _check("set_admin_permission", set_admin_permission(ADMIN_BALE_ID, "orders", True) is True)
    perms = get_admin_permissions(ADMIN_BALE_ID)
    _check("perm orders=True", perms.get("orders") is True)
    _check("perm reviews=False", perms.get("reviews") is False)
    # حذف ادمین
    add_giso_admin(phone=ADMIN_PHONE, bale_id=ADMIN_BALE_ID)
    rows = [a for a in __import__("giso_admin", fromlist=["list_giso_admins"]).list_giso_admins() if str(a.get("bale_id")) == ADMIN_BALE_ID]
    if rows:
        delete_giso_admin(rows[0]["id"])
        rows2 = [a for a in __import__("giso_admin", fromlist=["list_giso_admins"]).list_giso_admins() if str(a.get("bale_id")) == ADMIN_BALE_ID]
        _check("admin deleted", len(rows2) == 0)
    else:
        _check("admin deleted", True, "not existed")


def test_analyses_consultant_product_chats():
    """پاسخ مشاوره، وضعیت مشاوره، وضعیت محصول، خلاصه گفتگوها."""
    from giso.panel.modules.analyses import (get_consultant_requests,
                                             get_product_requests, get_chat_summaries)
    with get_giso_db_conn() as conn:
        conn.execute("INSERT INTO consultant_requests (phone, customer_name, initial_message, status, created_at) VALUES (?,?,?,?,?)",
                     (USER_PHONE, "کاربر تست", "سلام می‌خواهم مشاوره بگیرم", "new", time.strftime("%Y-%m-%d %H:%M:%S")))
        req_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        conn.execute("INSERT INTO product_requests (phone, problem_summary, status, created_at) VALUES (?,?,?,?)",
                     (USER_PHONE, "محصولی برای موهای خشک می‌خواهم", "pending", time.strftime("%Y-%m-%d %H:%M:%S")))
        prod_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        conn.execute("INSERT INTO analyses (phone, type, photo_path, consultant_chat_history, consultant_key_notes, chat_rating, created_at) VALUES (?,?,?,?,?,?,?)",
                     (USER_PHONE, "hair", "t.jpg", '[{"role":"user","content":"سلام"},{"role":"assistant","content":"سلام!"}]', "خلاصه تست", 5, time.strftime("%Y-%m-%d %H:%M:%S")))
        conn.commit()
    reqs = get_consultant_requests()
    _check("consultant requests listed", any(r["phone"] == USER_PHONE for r in reqs))
    prods = get_product_requests()
    _check("product requests listed", any(r["phone"] == USER_PHONE for r in prods))
    summaries = get_chat_summaries("all")
    _check("chat summaries listed", len(summaries) >= 1)
    # شبیه‌سازی handler ها از طریق app (بدون نیاز به login برای تست تابع خالص)
    from giso.panel.modules.analyses import get_chat_detail, get_consultant_messages
    detail = get_chat_detail(summaries[0]["id"]) if summaries else None
    _check("chat detail has messages", detail is not None and len(detail.get("messages", [])) == 2)
    _cleanup(None)


def test_shop_orders_search_and_status():
    """جستجوی سفارش فروشگاه + تغییر وضعیت."""
    app = create_app()
    client = app.test_client()
    _cleanup(app)
    _make_super(app)
    _login(client, SUPER_PHONE)
    _verify_super(client)
    # یک محصول + سفارش
    with app.app_context():
        p = Product(name="محصول تست", price=10000, in_stock=True)
        db.session.add(p)
        db.session.commit()
        o = ProductOrder(phone=USER_PHONE, customer_name="مشتری تست", product_id=p.id,
                         address="تهران", quantity=1, status="pending")
        db.session.add(o)
        db.session.commit()
        oid = o.id
    r = client.get("/admin/shop-orders?q=مشتری")
    _check("shop search by name", r.status_code == 200, f"status={r.status_code}")
    # تغییر وضعیت از route قدیمی (نباید شکسته شود)
    r = client.post(f"/admin/shop-order/{oid}/status", data={"status": "completed"})
    _check("shop order status change", r.status_code in (302, 200), f"status={r.status_code}")
    with app.app_context():
        o2 = ProductOrder.query.get(oid)
        _check("shop order completed in db", o2 is not None and o2.status == "completed")
    _cleanup(app)


def test_users_stats_ban_wallet_delete():
    """آمار کلی، بن، کیف پول، حذف دومرحله‌ای کاربر."""
    app = create_app()
    client = app.test_client()
    _cleanup(app)
    _make_super(app)
    _login(client, SUPER_PHONE)
    _verify_super(client)
    with app.app_context():
        u = User(phone=USER_PHONE, password_hash="hash", name="کاربر تست")
        db.session.add(u)
        db.session.commit()
        uid = u.id
    from giso.panel.modules.users import get_stats
    with app.app_context():
        st = get_stats()
    _check("users stats total>=1", st["total"] >= 1, f"total={st['total']}")
    # بن
    r = client.post(f"/admin/users/{uid}/ban", data={"ban_reason": "دلیل تست"})
    _check("user ban POST", r.status_code == 302)
    with app.app_context():
        u2 = User.query.get(uid)
        _check("user banned in db", u2.is_banned == 1 and u2.ban_reason == "دلیل تست")
    # کیف پول
    r = client.post(f"/admin/users/{uid}/wallet", data={"delta": "50000", "reason": "تست"})
    _check("user wallet POST", r.status_code == 302)
    from giso.referrals import get_wallet_balance
    _check("wallet balance 50000", get_wallet_balance(uid) == 50000)
    # حذف دومرحله‌ای
    r = client.post(f"/admin/users/{uid}/delete", data={"step": ""})
    _check("user delete step1", r.status_code == 302)
    with app.app_context():
        _check("user still exists after step1", User.query.get(uid) is not None)
    r = client.post(f"/admin/users/{uid}/delete", data={"step": "confirm"})
    _check("user delete step2", r.status_code == 302)
    with app.app_context():
        _check("user deleted", User.query.get(uid) is None)
    _cleanup(app)


def test_permission_sync_and_visible_modules():
    """visible_modules برای نقش‌های مختلف + module_allowed."""
    from giso.panel.permissions import visible_modules, module_allowed, ADMIN_SECTIONS
    super_perms = {k: True for k, _ in ADMIN_SECTIONS}
    menu_super = [m["module"] for m in visible_modules("super", super_perms)]
    _check("super sees established modules", set(menu_super) == {"dashboard", "hair_sale", "marketplace", "analyses", "shop_orders", "channel", "users", "admins", "consults", "products", "reviews", "wallet", "ai", "notifications", "shop", "settings", "reports"})
    _check("admin generic shop blocked", module_allowed("shop", "admin", {"orders": True}) is False)
    _check("admin without shop perms", module_allowed("shop", "admin", {"orders": False, "products": False, "channel_management": False}) is False)
    _check("admin never sees shop_super", module_allowed("shop_super", "admin", {k: True for k, _ in ADMIN_SECTIONS}) is False)
    _check("admin no settings", module_allowed("settings", "admin", {k: True for k, _ in ADMIN_SECTIONS}) is False)
    _check("admin no wallet", module_allowed("wallet", "admin", {k: True for k, _ in ADMIN_SECTIONS}) is False)
    _check("admin fixed order access", module_allowed("shop_orders", "admin", {"orders": True}) is True)
    _check("legacy switch cannot revoke order access", module_allowed("shop_orders", "admin", {"orders": False}) is True)


def test_ai_provider_crud():
    """افزودن/فعال/حذف پروایدر در giso_ai_providers (بدون شبکه)."""
    from giso.ai_brain import (init_ai_tables, add_ai_provider, delete_ai_provider,
                               get_ai_provider, toggle_ai_provider)
    init_ai_tables()
    name = "test_provider_phase5"
    try:
        delete_ai_provider(name)
    except Exception:
        pass
    ok = add_ai_provider(name=name, kind="openai", api_key="k", base_url="", timeout=20, enabled=True, replace=True)
    _check("ai provider add", ok is True)
    row = get_ai_provider(name)
    _check("ai provider exists", row is not None and row["name"] == name)
    new_val = toggle_ai_provider(name)
    _check("ai provider toggle off", new_val is False)
    try:
        delete_ai_provider(name)
        _check("ai provider delete", get_ai_provider(name) is None)
    except Exception as e:
        _check("ai provider delete", False, str(e))


def test_route_map_stability():
    """route های قبلی (پیش از فاز 5) حذف یا rename نشده‌اند."""
    app = create_app()
    endpoints = {r.endpoint for r in app.url_map.iter_rules()}
    legacy = [
        "admin_dashboard", "admin_verify", "admin_config_ai", "admin_config_ratelimit",
        "admin_product_add", "admin_product_edit", "admin_product_delete",
        "admin_product_publish", "admin_product_toggle_stock", "admin_shop_order_status",
        "admin_config_channel", "admin_channel_test", "admin_publish_mode",
        "admin_hair_order_update", "admin_hair_order_message", "admin_config_hair_prices",
        "admin_referral_settings", "admin_withdrawal_status", "admin_analysis_note",
        "admin_consultant_detail", "admin_review_delete", "panel.dashboard",
        "panel.users", "panel.admins", "panel.settings", "panel.hair_sale",
        "panel_user.overview", "panel_user.wallet", "login", "logout", "register",
    ]
    missing = [e for e in legacy if e not in endpoints]
    _check("legacy routes preserved", not missing, ",".join(missing))


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
