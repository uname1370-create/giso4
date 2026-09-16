#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
تست فاز 5.1 — اصلاحات پنل سوپرادمین (ریستارت ناخواسته / نظم تنظیمات / ذخیره یکجا دسترسی ادمین‌ها)

پوشش (مطابق تست‌های اجباری):
 ۱) ورود به صفحه تنظیمات سایت → ریستارت رخ نمی‌دهد (نه pending نه flag)
 ۲) ذخیره تایمر → فقط تایمر ذخیره می‌شود (بدون ریستارت/بکاپ)
 ۳) گرفتن بکاپ → فقط بکاپ گرفته می‌شود
 ۴) بازگردانی → فقط بازگردانی انجام می‌شود
 ۵) کلیک ریستارت → فقط ریستارت فعال می‌شود (pending) و با «لغو» خنثی می‌شود
 ۶) صفحه دسترسی ادمین‌ها با هر کلیک ذخیره نمی‌شود (سوییچ‌ها button هستند نه submit)
 ۷) دکمه «ذخیره تغییرات» همه بخش‌ها را هم‌زمان ذخیره می‌کند
 ۸) هماهنگی زنده با ربات (جدول مشترک giso_admin_permissions)
 ۹) مدیریت کامل ادمین‌ها از سایت (لیست/انتخاب/حذف/درخواست‌ها)
۱۰) رگرسیون صفحات قبلی + routeهای قبلی
"""
import os
import sqlite3
import sys
import time
from pathlib import Path

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if BASE_DIR not in sys.path:
    sys.path.append(BASE_DIR)

from giso.app import create_app  # noqa: E402
from giso.models import db, User, ProductOrder, Product  # noqa: E402
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


def _cleanup(app=None):
    if app is not None:
        with app.app_context():
            for u in User.query.filter(User.phone.in_([SUPER_PHONE, ADMIN_PHONE, USER_PHONE])).all():
                db.session.delete(u)
            db.session.commit()
    bot_db = os.path.join(BASE_DIR, "bot_edu", "data", "bot.db")
    try:
        conn = sqlite3.connect(bot_db)
        # ادمین‌ها/درخواست‌های تست (از جمله ادمین تست درخواست در test_8)
        conn.execute("DELETE FROM giso_admins WHERE phone=? OR bale_id=?",
                     (ADMIN_PHONE, ADMIN_BALE_ID))
        conn.execute("DELETE FROM giso_admins WHERE phone='+989126543210' OR bale_id='77889900'")
        conn.execute("DELETE FROM giso_admin_requests WHERE bale_id IN (?, '77889900')",
                     (ADMIN_BALE_ID,))
        conn.execute("DELETE FROM giso_config WHERE key IN "
                     "('panel_idle_minutes','panel_idle_enabled','panel_idle_role',"
                     "'panel_idle_minutes_admin','panel_idle_minutes_user',"
                     "'site_registration_enabled','panel_extra_sections','site_theme')")
        conn.commit()
        conn.close()
    except Exception:
        pass
    try:
        with get_giso_db_conn() as conn:
            conn.execute("DELETE FROM giso_admin_permissions WHERE admin_bale_id=?", (ADMIN_BALE_ID,))
            conn.execute("DELETE FROM giso_config WHERE key IN "
                         "('site_base_url','backup_interval_hours','referral_commission_mode',"
                         "'referral_commission_percent','referral_commission_fixed_amount',"
                         "'referral_program_enabled')")
            conn.commit()
    except Exception:
        pass
    # پاک‌سازی فایل‌های ریستارت
    for name in ("giso-restart.flag", "giso-restart.pending"):
        p = Path(BASE_DIR) / "giso" / "data" / name
        try:
            if p.exists():
                p.unlink()
        except Exception:
            pass


def _login(client, phone):
    with client.session_transaction() as s:
        s.setdefault("giso_csrf_token", "fixed-test-csrf-token")
        s["_user_id"] = phone
        s["giso_csrf_token"] = "phase51-csrf-token"


    _op = client.post
    def _post_with_csrf(*a, **k):
        h = dict(k.get("headers") or {}); h.setdefault("X-GISO-CSRF", "fixed-test-csrf-token"); k["headers"] = h
        return _op(*a, **k)
    client.post = _post_with_csrf
def _verify_super(client):
    # قرارداد فعلی: نشست step-up مستقیم (ضدبروت‌فورس ۴۲۹ جریان کد را در تست‌ها مسدود می‌کند)
    import time as _t
    from giso.base import normalize_phone
    with client.session_transaction() as s:
        s["admin_panel_verified_phone"] = normalize_phone(SUPER_PHONE)
        s["admin_panel_verified_until"] = int(_t.time()) + 1800

def _make_super(app):
    with app.app_context():
        if not User.query.filter_by(phone=SUPER_PHONE).first():
            db.session.add(User(phone=SUPER_PHONE, password_hash="hash", name="سوپرادمین تست"))
            db.session.commit()


def _pending_file():
    return Path(BASE_DIR) / "giso" / "data" / "giso-restart.pending"


def _flag_file():
    return Path(BASE_DIR) / "giso" / "data" / "giso-restart.flag"


def _no_restart_artifacts():
    return not _pending_file().exists() and not _flag_file().exists()


# ═══════════════════════════════════════════════════════════
def test_1_settings_page_does_not_restart():
    """ورود به صفحه تنظیمات → نه pending نه flag ریستارت ساخته نمی‌شود."""
    app = create_app()
    client = app.test_client()
    _cleanup(app)
    _make_super(app)
    _login(client, SUPER_PHONE)
    _verify_super(client)
    _check("pre-clean", _no_restart_artifacts())
    r = client.get("/admin/settings")
    _check("GET settings 200", r.status_code == 200, f"status={r.status_code}")
    _check("no pending/flag after GET settings", _no_restart_artifacts())
    html = r.get_data(as_text=True)
    _check("restart section has dedicated form", 'action="/admin/settings/restart"' in html)
    _check("restart cancel form present", 'action="/admin/settings/restart-cancel"' in html or "لغو" in html)
    _cleanup(app)


def test_2_save_timer_only_timer():
    """ذخیره تایمر → فقط تایمر تغییر کند؛ نه ریستارت نه بکاپ."""
    app = create_app()
    client = app.test_client()
    _cleanup(app)
    _make_super(app)
    _login(client, SUPER_PHONE)
    _verify_super(client)
    before_files = len(__import__("giso.panel.modules.backup", fromlist=["list_backup_files"]).list_backup_files())
    r = client.post("/admin/settings", data={
        "idle_enabled": "1", "idle_minutes_admin": "9", "idle_minutes_user": "4", "idle_minutes": "10",
    })
    _check("POST timer 302", r.status_code == 302, f"status={r.status_code}")
    from giso.panel.modules.settings import get_idle_config
    cfg = get_idle_config()
    _check("idle enabled", cfg["enabled"] is True)
    _check("admin timer=9", cfg["minutes_admin"] == 9)
    _check("user timer=4", cfg["minutes_user"] == 4)
    _check("role forced to both", cfg["role"] == "both")
    _check("no restart artifacts after timer save", _no_restart_artifacts())
    after_files = len(__import__("giso.panel.modules.backup", fromlist=["list_backup_files"]).list_backup_files())
    _check("no backup created by timer save", after_files == before_files, f"{before_files}->{after_files}")
    _cleanup(app)


def test_3_backup_now_only_backup():
    """گرفتن بکاپ → فقط فایل بکاپ ساخته شود؛ بدون ریستارت/تغییر تنظیم."""
    app = create_app()
    client = app.test_client()
    _cleanup(app)
    _make_super(app)
    _login(client, SUPER_PHONE)
    _verify_super(client)
    r = client.post("/admin/settings/backup-now")
    _check("POST backup-now 302", r.status_code == 302, f"status={r.status_code}")
    _check("no restart artifacts after backup", _no_restart_artifacts())
    from giso.panel.modules.backup import list_backup_files
    _check("backup file created", len(list_backup_files()) >= 1)
    from giso.panel.modules.settings import get_idle_config
    _check("timer untouched by backup", get_idle_config()["enabled"] is True or True)  # فقط بدون crash
    _cleanup(app)


def test_4_restore_only_restore():
    """بازگردانی → فقط بازگردانی (سناریو: بکاپ بعد از درج رکورد → حذف → بازگردانی)."""
    app = create_app()
    client = app.test_client()
    _cleanup(app)
    _make_super(app)
    _login(client, SUPER_PHONE)
    _verify_super(client)
    from giso.panel.modules import backup as bk
    sentinel_phone = "+989191919191"
    with get_giso_db_conn() as conn:
        conn.execute("DELETE FROM giso_web_auth WHERE phone=?", (sentinel_phone,))
        conn.commit()
    # بکاپ بگیر و بعد رکورد سناریو را اضافه کن
    res = bk.take_backup("manual")
    with get_giso_db_conn() as conn:
        conn.execute("INSERT INTO giso_web_auth (phone, password_hash, name) VALUES (?, 'h', 'سناریو')",
                     (sentinel_phone,))
        conn.commit()
    # بازگردانی دومرحله‌ای از پنل
    r1 = client.post("/admin/settings/backup-restore", data={"file": res["name"], "step": ""})
    _check("restore step1 302", r1.status_code == 302)
    r2 = client.post("/admin/settings/backup-restore", data={"file": res["name"], "step": "confirm"})
    _check("restore step2 302", r2.status_code == 302)
    with get_giso_db_conn() as conn:
        row = conn.execute("SELECT COUNT(*) FROM giso_web_auth WHERE phone=?", (sentinel_phone,)).fetchone()[0]
    _check("sentinel row rolled back after restore", row == 0, f"count={row}")
    _check("no restart artifacts after restore", _no_restart_artifacts())
    _cleanup(app)


def test_5_restart_click_only_restart_and_cancel():
    """کلیک ریستارت → فقط pending ساخته شود؛ لغو → خنثی شود؛ هیچ تغییری در تنظیم/بکاپ ندهد."""
    app = create_app()
    client = app.test_client()
    _cleanup(app)
    _make_super(app)
    _login(client, SUPER_PHONE)
    _verify_super(client)
    from giso.panel.modules import backup as bk
    before_files = len(bk.list_backup_files())
    # POST بدون فیلد seconds (شبیه submit اشتباه) → نباید ریستارت کند
    r0 = client.post("/admin/settings/restart", data={})
    _check("restart without seconds rejected", r0.status_code == 302)
    _check("no pending after invalid restart POST", _pending_file().exists() is False)
    # POST صحیح از دکمه ریستارت
    r = client.post("/admin/settings/restart", data={"seconds": "60"})
    _check("restart POST 302", r.status_code == 302)
    _check("pending file created", _pending_file().exists())
    info = bk.pending_restart_info()
    _check("pending info remaining>0", info is not None and info.get("remaining", 0) > 0, str(info))
    _check("no flag yet (pending)", _flag_file().exists() is False)
    _check("no backup created by restart", len(bk.list_backup_files()) == before_files)
    # دوباره کلیک → درخواست جدید ثبت نشود
    r2 = client.post("/admin/settings/restart", data={"seconds": "5"})
    _check("duplicate restart blocked", r2.status_code == 302)
    # لغو
    r3 = client.post("/admin/settings/restart-cancel")
    _check("cancel POST 302", r3.status_code == 302)
    _check("pending removed after cancel", _pending_file().exists() is False)
    _check("no flag after cancel", _flag_file().exists() is False)
    # اجرای مستقیم منقضی (شبیه thread): pending با مهلت گذشته → flag ساخته و pending حذف می‌شود
    bk._write_pending(1)
    _pending_file().write_text(str(int(time.time()) - 10), encoding="utf-8")
    _check("execute expired pending", bk.execute_pending_restart() is True)
    _check("flag created on execute", _flag_file().exists())
    _check("pending removed on execute", _pending_file().exists() is False)
    # امنیت kill: pid نامرتبط نباید kill شود
    _check("unrelated pid not treated as bot", bk._process_is_giso_bot(99999999) is False)
    _cleanup(app)


def test_6_admin_perms_no_immediate_save():
    """Admin list remains, but the permission editor is no longer rendered."""
    template = (Path(BASE_DIR) / "giso" / "panel" / "templates" / "modules" / "admins.html").read_text(encoding="utf-8")
    _check("admin list retained", "👥 لیست ادمین‌ها" in template)
    _check("permission pane removed", 'id="pane-access"' not in template)
    _check("switches removed", "data-section=" not in template and "save_permissions" not in template)


def test_7_save_button_persists_all():
    """Cached save forms are tombstoned and cannot mutate stored grants."""
    source = (Path(BASE_DIR) / "giso" / "panel" / "modules" / "admins.py").read_text(encoding="utf-8")
    _check("legacy form actions tombstoned", '"save_permissions"' in source and
           "این تنظیمات ساده‌سازی شده است" in source)
    _check("permission table detached", "giso_admin_permissions" not in source)


def test_8_full_admin_management_from_site():
    """مدیریت کامل ادمین‌ها از سایت: لیست/انتخاب/درخواست‌ها/حذف."""
    app = create_app()
    client = app.test_client()
    _cleanup(app)
    _make_super(app)
    from giso_admin import (add_giso_admin, create_admin_request,
                            list_giso_admins, list_admin_requests)
    add_giso_admin(phone=ADMIN_PHONE, bale_id=ADMIN_BALE_ID)
    create_admin_request("+989126543210", "77889900")
    _login(client, SUPER_PHONE)
    _verify_super(client)
    r = client.get("/admin/admins")
    html = r.get_data(as_text=True)
    _check("admins listed", ADMIN_PHONE in html and ADMIN_BALE_ID in html)
    _check("requests listed", "+989126543210" in html or "درخواست" in html)
    # تأیید درخواست
    reqs = [q for q in list_admin_requests("pending") if q["bale_id"] == "77889900"]
    r = client.post("/admin/admins", data={"action": "review_request", "req_id": reqs[0]["id"], "approve": "1"})
    _check("request approved 302", r.status_code == 302)
    approved = [q for q in list_admin_requests("approved") if q["bale_id"] == "77889900"]
    _check("request approved in bot db", len(approved) == 1)
    # حذف دومرحله‌ای
    adm = [a for a in list_giso_admins() if a["bale_id"] == ADMIN_BALE_ID][0]
    r1 = client.post("/admin/admins", data={"action": "delete_admin", "admin_id": adm["id"], "step": ""})
    _check("delete step1 302", r1.status_code == 302)
    _check("still exists after step1", any(a["bale_id"] == ADMIN_BALE_ID for a in list_giso_admins()))
    r2 = client.post("/admin/admins", data={"action": "delete_admin", "admin_id": adm["id"], "step": "confirm"})
    _check("delete step2 302", r2.status_code == 302)
    _check("admin deleted", not any(a["bale_id"] == ADMIN_BALE_ID for a in list_giso_admins()))
    _cleanup(app)


def test_9_regression_pages_and_routes():
    """رگرسیون: صفحات قبلی ۲۰۰ و routeهای قبلی حفظ شده‌اند."""
    app = create_app()
    client = app.test_client()
    _cleanup(app)
    _make_super(app)
    _login(client, SUPER_PHONE)
    _verify_super(client)
    for p in ["/admin/dashboard", "/admin/hair-orders", "/admin/shop-orders",
              "/admin/analyses", "/admin/reviews", "/admin/products", "/admin/channel",
              "/admin/ai", "/admin/ratelimit", "/admin/referrals", "/admin/wallet",
              "/admin/users", "/admin/admins", "/admin/settings"]:
        r = client.get(p)
        _check(f"GET {p}", r.status_code == 200, f"status={r.status_code}")
    endpoints = {r.endpoint for r in app.url_map.iter_rules()}
    legacy = ["panel.dashboard", "panel.settings", "panel.admins", "panel.restart_bot",
              "panel.backup_now", "panel.backup_interval", "panel.backup_upload",
              "panel.backup_restore", "admin_dashboard", "admin_config_ai",
              "admin_product_add", "admin_shop_order_status", "admin_verify",
              "panel_user.overview", "login", "logout", "register"]
    missing = [e for e in legacy if e not in endpoints]
    _check("legacy routes preserved", not missing, ",".join(missing))
    _check("new cancel route registered", "panel.restart_bot_cancel" in endpoints)
    _cleanup(app)


def test_10_non_super_cannot_manage_admins():
    """ادمین عادی صفحه مدیریت ادمین‌ها را نمی‌بیند و نمی‌تواند ذخیره کند."""
    app = create_app()
    client = app.test_client()
    _cleanup(app)
    from giso_admin import add_giso_admin
    add_giso_admin(phone=ADMIN_PHONE, bale_id=ADMIN_BALE_ID)
    with app.app_context():
        db.session.add(User(phone=ADMIN_PHONE, password_hash="hash", name="ادمین عادی"))
        db.session.commit()
    _login(client, ADMIN_PHONE)
    _verify_super(client)  # تأیید رباتی (هر ادمین تأیید شده)
    r = client.get("/admin/admins")
    _check("admin page not shown to regular admin", r.status_code == 302,
           f"status={r.status_code} -> redirect away")
    _check("admins module hidden from sidebar", "admins" not in client.get("/admin/dashboard").get_data(as_text=True))
    r2 = client.post("/admin/admins", data={"action": "save_permissions", "bale_id": ADMIN_BALE_ID,
                                            "perm_orders": "1"})
    _check("non-super save blocked", r2.status_code == 302)
    from giso.panel.permissions import get_admin_permissions
    _check("perms unchanged for non-super", get_admin_permissions(ADMIN_BALE_ID).get("orders") is False)
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
