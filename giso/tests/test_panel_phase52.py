#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
تست فاز 5.2 — رفع کامل باگ «GET /admin/settings توقف سرویس» + سوییچ‌های زیرگزینه دسترسی ادمین

پوشش (مطابق تست‌های اجباری):
 ۱) GET /admin/settings هرگز باعث توقف سرویس نمی‌شود (هیچ اجرای ریستارت در رندر)
 ۲) هیچ ریستارتی بدون کلیک واقعی روی دکمه اجرا نمی‌شود
 ۳) POST بدون فیلد seconds هرگز ریستارت را trigger نمی‌کند
 ۴) هر بخش دسترسی ادمین سوییچ کل دارد
 ۵) هر زیرگزینه سوییچ مستقل دارد
 ۶) کلیک روی سوییچ چیزی ذخیره نمی‌کند (سوییچ‌ها button هستند و GET بی‌اثر است)
 ۷) دکمه «ذخیره تغییرات» همه تغییرات (کل + زیرگزینه) را هم‌زمان ذخیره می‌کند
 ۸) تغییرات در ربات هم دیده می‌شوند (جدول مشترک + sub_options در همان جدول)
 ۹) رگرسیون صفحات قبلی + routeهای قبلی
۱۰) رگرسیون فازهای قبلی (فایل‌های تست جدا اجرا می‌شوند)
"""
import json
import os
import sqlite3
import sys
import time
from pathlib import Path

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if BASE_DIR not in sys.path:
    sys.path.append(BASE_DIR)

from giso.app import create_app  # noqa: E402
from giso.models import db, User  # noqa: E402
from giso.base import get_giso_db_conn, normalize_phone  # noqa: E402

SUPER_PHONE = normalize_phone("09156012931")
ADMIN_PHONE = normalize_phone("09123334444")
ADMIN_BALE_ID = "88990011"
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
            for u in User.query.filter(User.phone.in_([SUPER_PHONE, ADMIN_PHONE])).all():
                db.session.delete(u)
            db.session.commit()
    bot_db = os.path.join(BASE_DIR, "bot_edu", "data", "bot.db")
    try:
        conn = sqlite3.connect(bot_db)
        conn.execute("DELETE FROM giso_admins WHERE phone=? OR bale_id=?", (ADMIN_PHONE, ADMIN_BALE_ID))
        conn.execute("DELETE FROM giso_admin_requests WHERE bale_id=?", (ADMIN_BALE_ID,))
        conn.commit()
        conn.close()
    except Exception:
        pass
    try:
        with get_giso_db_conn() as conn:
            conn.execute("DELETE FROM giso_admin_permissions WHERE admin_bale_id=?", (ADMIN_BALE_ID,))
            conn.execute("DELETE FROM giso_config WHERE key IN "
                         "('panel_idle_minutes','panel_idle_enabled','panel_idle_role',"
                         "'panel_idle_minutes_admin','panel_idle_minutes_user',"
                         "'site_registration_enabled','panel_extra_sections','site_theme',"
                         "'site_base_url','backup_interval_hours')")
            conn.commit()
    except Exception:
        pass
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
        s["giso_csrf_token"] = "phase52-csrf-token"


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


# ═══════════════════════════════════════════════════════════
def test_1_get_settings_never_executes_restart():
    """**تست بحرانی:** GET /admin/settings با توابع ریستارتِ ممنوعه — اگر صدا زده شوند تست می‌شکند."""
    from unittest.mock import patch
    app = create_app()
    client = app.test_client()
    _cleanup(app)
    _make_super(app)
    _login(client, SUPER_PHONE)
    _verify_super(client)

    # هر تماس با توابع اجرای ریستارت در مسیر GET باید خطا بدهد → اگر GET آن‌ها را صدا بزند، 500 می‌شود
    def _boom(*a, **kw):
        raise AssertionError("ریستارت در مسیر GET اجرا شد!")

    with patch("giso.panel.modules.backup._write_restart_flag", side_effect=_boom), \
         patch("giso.panel.modules.backup._kill_giso_bot_if_running", side_effect=_boom), \
         patch("giso.panel.modules.backup.execute_pending_restart", side_effect=_boom), \
         patch("giso.panel.modules.backup._write_pending", side_effect=_boom), \
         patch("giso.panel.modules.backup.cancel_bot_restart", side_effect=_boom):
        r = client.get("/admin/settings")
        _check("GET settings 200 (no restart execution)", r.status_code == 200, f"status={r.status_code}")

    # حتی با pending/flag موجود در دیسک، GET نباید آن‌ها را لمس کند (فقط‌خواندنی)
    _pending_file().write_text(str(int(time.time()) + 30), encoding="utf-8")
    _flag_file().write_text("0", encoding="utf-8")
    r2 = client.get("/admin/settings")
    _check("GET settings with pending+flag still 200", r2.status_code == 200, f"status={r2.status_code}")
    _check("GET did not remove pending (read-only)", _pending_file().exists())
    _check("GET did not remove flag (read-only)", _flag_file().exists())
    _cleanup(app)


def test_2_no_restart_without_real_click():
    """بدون POST هدفمند هیچ ریستارتی اجرا نمی‌شود (فقط GET کافی نیست)."""
    from unittest.mock import patch
    app = create_app()
    client = app.test_client()
    _cleanup(app)
    _make_super(app)
    _login(client, SUPER_PHONE)
    _verify_super(client)
    boom = lambda *a, **kw: (_ for _ in ()).throw(AssertionError("اجرا نشد"))
    with patch("giso.panel.modules.backup._kill_giso_bot_if_running", side_effect=boom), \
         patch("giso.panel.modules.backup._write_restart_flag", side_effect=boom):
        # فقط مرور صفحات — هیچ چیزی نباید kill/write flag کند
        for p in ("/admin/settings", "/admin", "/admin/dashboard", "/admin/admins"):
            r = client.get(p)
            _check(f"GET {p} safe", r.status_code in (200, 302), f"status={r.status_code}")
        r = client.post("/admin/settings", data={"idle_enabled": "1", "idle_minutes": "10"})
        _check("POST timer safe (no restart)", r.status_code == 302)
    _check("no pending after page views", not _pending_file().exists())
    _check("no flag after page views", not _flag_file().exists())
    _cleanup(app)


def test_3_post_without_seconds_no_restart():
    """POST بدون فیلد seconds هرگز ریستارت را trigger نمی‌کند."""
    app = create_app()
    client = app.test_client()
    _cleanup(app)
    _make_super(app)
    _login(client, SUPER_PHONE)
    _verify_super(client)
    r = client.post("/admin/settings/restart", data={})
    _check("restart POST w/o seconds rejected", r.status_code == 302)
    _check("no pending after invalid POST", not _pending_file().exists())
    r = client.post("/admin/settings/restart", data={"seconds": "7"})
    _check("invalid seconds rejected (defaults blocked)", r.status_code == 302)
    _check("no pending for invalid seconds", not _pending_file().exists())
    _cleanup(app)


def test_4_5_section_and_suboption_switches():
    """The Website access tab and every section/sub-option switch are gone."""
    template = (Path(BASE_DIR) / "giso" / "panel" / "templates" / "modules" / "admins.html").read_text(encoding="utf-8")
    script = (Path(BASE_DIR) / "giso" / "panel" / "static" / "js" / "panel.js").read_text(encoding="utf-8")
    assert 'data-pane="access"' not in template
    assert 'id="pane-access"' not in template
    assert "save_permissions" not in template
    assert "pnl-perm-grid" not in template
    assert "pnl-subswitch" not in template
    assert "pnl-perm-grid" not in script
    assert "📥 درخواست‌ها" in template and "🔑 کلمه ادمینی" in template


def test_6_click_does_not_save():
    """The Website admins handler contains no permission-table reader/writer."""
    source = (Path(BASE_DIR) / "giso" / "panel" / "modules" / "admins.py").read_text(encoding="utf-8")
    assert "giso_admin_permissions" not in source
    assert "sub_options" not in source
    assert "set_admin_permission" not in source


def test_7_save_button_persists_sections_and_subs():
    """A cached old form fails closed instead of mutating historical rows."""
    from unittest.mock import patch
    from flask import Flask
    from giso.panel.modules import admins

    tiny = Flask(__name__)
    tiny.secret_key = "x"
    tiny.add_url_rule("/admin/admins", endpoint="panel.admins", view_func=lambda: "ok")
    with tiny.test_request_context("/admin/admins", method="POST",
                                   data={"action": "save_permissions", "bale_id": ADMIN_BALE_ID}):
        with patch("giso.panel.modules.admins.current_role_and_perms",
                   return_value=("super", {}, "")):
            response = admins.handle_post()
        assert response.status_code == 302
        flashes = __import__("flask").get_flashed_messages()
        assert "این تنظیمات ساده‌سازی شده است" in flashes


def test_8_bot_compatibility_and_live_sync():
    """Compatibility modules import safely but do not configure permissions."""
    from giso import admin_access_schema, bot_permissions
    from giso.panel.permissions import get_admin_permissions

    assert admin_access_schema.ADMIN_ACCESS_SCHEMA == {}
    assert bot_permissions.CONFIGURABLE_SECTIONS == ()
    fixed = get_admin_permissions(ADMIN_BALE_ID)
    assert fixed["orders"] is True
    assert fixed["products"] is True
    assert fixed["users"] is False
    # جدول legacy فقط برای سازگاری اسکیما در models.py مانده؛ تصمیم دسترسی نباید از آن بخواند
    perms_source = (Path(BASE_DIR) / "giso" / "panel" / "permissions.py").read_text(encoding="utf-8")
    assert "giso_admin_permissions" not in perms_source


def test_9_regression_pages_and_routes():
    """رگرسیون صفحات قبلی + routeهای قبلی."""
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
              "panel.restart_bot_cancel", "panel.backup_now", "panel.backup_restore",
              "admin_dashboard", "admin_config_ai", "admin_product_add",
              "admin_shop_order_status", "admin_verify", "panel_user.overview",
              "login", "logout", "register"]
    missing = [e for e in legacy if e not in endpoints]
    _check("legacy routes preserved", not missing, ",".join(missing))
    _cleanup(app)


def test_10_race_guard_double_arm():
    """جلوگیری از race: دو درخواست هم‌زمان ریستارت → فقط اولی ثبت می‌شود."""
    from giso.panel.modules import backup as bk
    _cleanup(None)
    ok1 = bk.request_bot_restart(60)
    _check("first arm ok", ok1 is True)
    ok2 = bk.request_bot_restart(5)
    _check("second arm blocked (race guard)", ok2 is False)
    info = bk.pending_restart_info()
    _check("pending still 60s", info is not None and info.get("remaining", 0) > 55, str(info))
    _check("cancel ok", bk.cancel_bot_restart() is True)
    ok3 = bk.request_bot_restart(60)
    _check("re-arm after cancel ok", ok3 is True)
    _check("cancel again ok", bk.cancel_bot_restart() is True)
    _cleanup(None)


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
