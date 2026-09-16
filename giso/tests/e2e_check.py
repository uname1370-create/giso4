#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""E2E real-flow test: user / admin / superadmin / special; site + panel; buttons/commands."""
import os
import sys
import sqlite3
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent.parent  # ریشهٔ پروژه
sys.path.insert(0, str(BASE))
os.environ.setdefault("SECRET_KEY", "e2e-" + os.urandom(16).hex())

from giso.app import create_app  # noqa: E402
from giso.models import db, User  # noqa: E402
from giso.base import normalize_phone  # noqa: E402
from werkzeug.security import generate_password_hash  # noqa: E402

app = create_app()
client = app.test_client()
RESULTS = []
ADMIN_VERIFY_CODE = "654321"


def ok(name, cond, detail=""):
    RESULTS.append((name, bool(cond), detail))
    print(("PASS" if cond else "FAIL") + " :: " + name + (" :: " + str(detail) if detail else ""))


def csrf():
    with client.session_transaction() as s:
        return s.get("giso_csrf_token", "")


def post_form(path, data=None):
    d = dict(data or {})
    d.setdefault("csrf_token", csrf())
    return client.post(path, data=d)


def post_json(path, body, headers=None):
    h = {"X-GISO-CSRF": csrf()}
    h.update(headers or {})
    return client.post(path, json=body, headers=h)


def verify_admin():
    """step-up: GET /admin/verify issues code (sender mocked), then POST code."""
    r = client.get("/admin/verify", follow_redirects=False)
    if r.status_code not in (200, 302):
        return r
    r = post_form("/admin/verify", {"action": "verify", "code": ADMIN_VERIFY_CODE})
    return r


# init session + CSRF first (real browser behavior: first page load)
client.get("/register")

# ---------------------------------------------------------------- seed
NORMAL_USER = normalize_phone("09123456789")
ADMIN_USER = normalize_phone("09123456780")
ADMIN_BALE = "999000111"
SUPER_USER = normalize_phone("09156012931")
SPECIAL_USER = normalize_phone("09353258836")

with app.app_context():
    for phone in (ADMIN_USER, SUPER_USER, SPECIAL_USER):
        if not User.query.filter_by(phone=phone).first():
            db.session.add(User(phone=phone, password_hash=generate_password_hash("pass1234"), name="E2E"))
    db.session.commit()
    from bot_edu.giso_admin import add_giso_admin
    add_giso_admin(phone=ADMIN_USER, bale_id=ADMIN_BALE, added_by=1191639507)

# mock step-up code (same approach as real tests)
import giso.app as _app_mod  # noqa: E402
_orig_gen = _app_mod._generate_admin_panel_code
def _fixed(phone_norm=None):
    return ADMIN_VERIFY_CODE
_app_mod._generate_admin_panel_code = _fixed
import giso.stepup as _st
def _sender_ok(*a, **k):
    return True, "sent"
_st._send_admin_panel_code_to_bot = _sender_ok
_app_mod._send_admin_panel_code_to_bot = _sender_ok

# ---------------------------------------------------------------- register user
r = post_form("/register", {"action": "register", "phone": "09123456789", "password": "pass1234",
                            "password2": "pass1234", "security_question": "مادر؟",
                            "security_answer": "مریم", "site_terms_accepted": "1"})
ok("ثبت‌نام کاربر عادی", r.status_code == 302, r.status_code)

# login user
r = post_form("/login", {"phone": "09123456789", "password": "pass1234"})
ok("ورود کاربر عادی", r.status_code == 302, r.status_code)
r = client.get("/dashboard", follow_redirects=True)
ok("پنل کاربری (پس از redirect) 200", r.status_code == 200, r.status_code)

# ---------------------------------------------------------------- public pages (no auth needed)
for p, label in [("/", "خانه"), ("/shop", "فروشگاه"), ("/analysis", "آنالیز"),
                 ("/analysis/hair", "آنالیز مو"), ("/beauty-centers", "مراکز زیبایی"),
                 ("/hair-sale", "فروش مو"), ("/sitemap.xml", "sitemap (SEO)"), ("/robots.txt", "robots (SEO)")]:
    r = client.get(p)
    ok(label, r.status_code == 200, r.status_code)

# hair estimate API (real JSON + CSRF header)
r = post_json("/api/hair-estimate", {"hair_type": "raw", "length_cm": "60", "hair_health": "خوب", "hair_weight": "300"})
b = r.get_json(silent=True) or {}
ok("API برآورد قیمت مو", r.status_code == 200 and "price_range" in b, (r.status_code, b))

# buyer request (real user panel marketplace)
r = post_form("/hair-sale/buyer-request", {"buyer_name": "تست", "buyer_phone": "09123456789",
                                           "buyer_city": "مشهد", "buyer_type": "personal",
                                           "buyer_description": "تست", "budget_min": "1000000",
                                           "budget_max": "2000000", "buyer_terms": "1"})
ok("درخواست خریدار (بازارچه)", r.status_code == 302, r.status_code)

# shop buy
with app.app_context():
    conn = sqlite3.connect("giso/data/giso.db")
    row = None
    if conn.execute("SELECT count(*) FROM sqlite_master WHERE type='table' AND name='products'").fetchone()[0]:
        row = conn.execute("SELECT id FROM products ORDER BY id LIMIT 1").fetchone()
    conn.close()
if row:
    pid = row[0]
    r = client.get(f"/shop/product/{pid}")
    ok("صفحه محصول", r.status_code == 200, r.status_code)
    r = post_form(f"/shop/buy/{pid}", {"customer_name": "تست", "phone": "09123456789",
                                       "address": "مشهد، تست", "courier_note": "",
                                       "contact_day": "شنبه", "contact_time": "10-12"})
    ok("ثبت سفارش فروشگاه", r.status_code in (200, 302), r.status_code)
    r = post_form(f"/shop/notify/{pid}", {"phone": "09123456789"})
    ok("اعلان موجودی کالا", r.status_code in (200, 302), r.status_code)
else:
    ok("صفحه محصول", False, "no products seeded")

# notifications / widget
r = client.get("/api/notifications/poll")
ok("API اعلان‌ها", r.status_code == 200 and r.is_json, r.status_code)
r = client.get("/api/ai-widget/init")
w = r.get_json(silent=True) or {}
ok("ویجت AI init", r.status_code == 200 and isinstance(w, dict), r.status_code)
wcsrf = w.get("csrf_token") or w.get("csrf") or csrf()
r = post_json("/api/ai-widget/chat", {"message": "سلام"}, {"X-GISO-CSRF": wcsrf})
ok("ویجت AI چت (بدون کلید → بدون 500)", r.status_code != 500, r.status_code)

# ---------------------------------------------------------------- ADMIN (عادی)
client.get("/logout")
r = post_form("/login", {"phone": "09123456780", "password": "pass1234"})
ok("ورود ادمین عادی", r.status_code in (301, 302), r.status_code)
r = verify_admin()
ok("تأیید دومرحله‌ای ادمین", r.status_code in (301, 302), r.status_code)
for p in ["/admin/dashboard", "/admin/analyses", "/admin/hair-orders", "/admin/marketplace",
          "/admin/reviews", "/admin/consults", "/admin/beauty-centers", "/admin/shop/stats"]:
    rr = client.get(p, follow_redirects=True)
    ok(f"پنل ادمین عادی {p}", rr.status_code == 200, rr.status_code)
rr = client.get("/admin/ai", follow_redirects=False)
ok("ادمین عادی: AI بسته (302 طراحی)", rr.status_code in (301, 302), rr.status_code)
rr = client.get("/admin/settings", follow_redirects=False)
ok("ادمین عادی: تنظیمات بسته (302 طراحی)", rr.status_code in (301, 302), rr.status_code)

# ---------------------------------------------------------------- SUPER
client.get("/logout")
r = post_form("/login", {"phone": "09156012931", "password": "pass1234"})
ok("ورود سوپرادمین", r.status_code in (301, 302), r.status_code)
r = verify_admin()
ok("تأیید دومرحله‌ای سوپر", r.status_code in (301, 302), r.status_code)
for p in ["/admin/dashboard", "/admin/settings", "/admin/admins", "/admin/ai", "/admin/monitoring",
          "/admin/notifications", "/admin/shop/stats", "/admin/wallet", "/admin/super-assistant",
          "/admin/account", "/admin/beauty-centers"]:
    rr = client.get(p, follow_redirects=True)
    ok(f"پنل سوپر {p}", rr.status_code == 200, rr.status_code)

# super buttons (POST + real CSRF)
r = post_form("/admin/settings/backup-now", {})
ok("دکمه بکاپ فوری", r.status_code in (301, 302, 200), r.status_code)
r = post_form("/admin/config/analysis-ratelimit", {"rate_limit_enabled": "1", "rate_limit_minutes": "7", "rate_limit_type": "both"})
ok("دکمه rate-limit", r.status_code in (301, 302, 200), r.status_code)
r = post_form("/admin/config/hair-prices", {"raw_50": "800000", "raw_60": "950000"})
ok("دکمه قیمت مو", r.status_code in (301, 302, 200), r.status_code)
r = post_form("/admin/settings/recovery-create", {})
ok("دکمه ساخت Recovery", r.status_code in (301, 302, 200), r.status_code)

from giso.base import read_rate_limit_config  # noqa: E402
cfg = read_rate_limit_config()
ok("rate-limit واقعاً ذخیره شد (7 دقیقه)", cfg.get("minutes") == 7 and cfg.get("ok") is True, cfg)

# ---------------------------------------------------------------- SPECIAL
client.get("/logout")
r = post_form("/login", {"phone": "09353258836", "password": "pass1234"})
ok("ورود ادمین ویژه", r.status_code in (301, 302), r.status_code)
r = verify_admin()
ok("تأیید دومرحله‌ای ادمین ویژه", r.status_code in (301, 302), r.status_code)
r = client.get("/admin/dashboard", follow_redirects=True)
ok("داشبورد ادمین ویژه", r.status_code == 200, r.status_code)
r = client.get("/admin/settings", follow_redirects=False)
ok("ادمین ویژه: تنظیمات بسته (302 طراحی)", r.status_code in (301, 302), r.status_code)

fails = [n for n, c, _ in RESULTS if not c]
print(f"\n=== E2E: {len(RESULTS)} checks | PASS {len(RESULTS) - len(fails)} | FAIL {len(fails)} ===")
if fails:
    print("FAILED:", fails)
sys.exit(1 if fails else 0)
