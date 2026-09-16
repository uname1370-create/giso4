#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
تست سیاست مجوزدهی پنل وب برای «خرید مو» و «فروشگاه» + صفحه‌بندی + N+1 + اعلان‌ها.

سیاست تحت آزمون:
    ادمین معمولی تأییدشده یک نقش عملیاتی ثابت دارد.
    رکوردهای قدیمی section/sub_options دیگر مجوز عملیاتی را کم‌وزیاد نمی‌کنند.
    اکشن‌های حساس همچنان فقط برای سوپرادمین‌اند.

اجرا:  SECRET_KEY=xxx python giso/tests/test_panel_authz_hair_shop.py
"""
import json
import os
import sys
import time

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if BASE_DIR not in sys.path:
    sys.path.append(BASE_DIR)
os.environ.setdefault("SECRET_KEY", "x" * 40)

from giso.app import create_app                                    # noqa: E402
from giso.base import get_giso_db_conn, normalize_phone, _upsert_giso_user  # noqa: E402
from giso.models import db, User                                   # noqa: E402

SUPER_PHONE = "+989156012931"
REG_PHONE = "+989120000777"
REG_BID = 990777
CSRF = "t" * 32

app = create_app()
_FAILED = []


def setup_module(module):  # pytest hook — هم‌ارز _seed() در اجرای standalone
    _seed()


# ───────────────────── کمکی ─────────────────────
def _seed():
    with app.app_context():
        for ph, nm in ((SUPER_PHONE, "S"), (REG_PHONE, "R")):
            if not User.query.filter_by(phone=ph).first():
                db.session.add(User(phone=ph, name=nm, region="t", password_hash="x"))
        db.session.commit()
    _upsert_giso_user(bale_id=REG_BID, phone=REG_PHONE, first_name="R", username="r",
                      is_admin=True, contact_shared=True, pending_request=False)


def _client(phone):
    c = app.test_client()
    with c.session_transaction() as s:
        s["_user_id"] = phone
        s["_fresh"] = True
        s["giso_csrf_token"] = CSRF
        s["admin_panel_verified_phone"] = normalize_phone(phone)
        s["admin_panel_verified_until"] = int(time.time()) + 3600
    return c


def _post(c, url, data=None):
    d = dict(data or {})
    d["csrf_token"] = CSRF
    return c.post(url, data=d, follow_redirects=False)


def _set_sub(section, key, visible, bale_id=REG_BID, channel="site"):
    conn = get_giso_db_conn()
    try:
        row = conn.execute(
            "SELECT id, sub_options FROM giso_admin_permissions WHERE admin_bale_id=? AND section=?",
            (str(bale_id), section)).fetchone()
        data = json.loads((row["sub_options"] if row else "") or "{}") if row else {}
        data[f"{channel}_{key}_visible"] = "1" if visible else "0"
        payload = json.dumps(data, ensure_ascii=False)
        if row:
            conn.execute("UPDATE giso_admin_permissions SET sub_options=? WHERE id=?", (payload, row["id"]))
        else:
            conn.execute("INSERT INTO giso_admin_permissions (admin_bale_id,section,is_allowed,sub_options,created_at)"
                         " VALUES (?,?,1,?,datetime('now'))", (str(bale_id), section, payload))
        conn.commit()
    finally:
        conn.close()


def _q1(sql, params=()):
    conn = get_giso_db_conn()
    try:
        r = conn.execute(sql, params).fetchone()
        return r[0] if r else None
    finally:
        conn.close()


def _fixtures():
    conn = get_giso_db_conn()
    try:
        conn.execute("INSERT OR REPLACE INTO products (id,name,price,category,in_stock,publish_status)"
                     " VALUES (9500,'PolicyProd',1000,'t',1,'published')")
        conn.execute("INSERT OR REPLACE INTO hair_orders (id,customer_name,phone,status,length_cm,photo_path,created_at)"
                     " VALUES (9500,'C','+989120000555','pending',60,'x.jpg',datetime('now'))")
        conn.execute("INSERT OR REPLACE INTO product_orders (id,product_id,customer_name,phone,address,status,created_at)"
                     " VALUES (9500,9500,'C','+98912','a','pending',datetime('now'))")
        conn.commit()
    finally:
        conn.close()


# ───────────── ۱) گزینه فعال → مجاز ─────────────
def test_1_enabled_hair_action_allowed():
    _fixtures()
    _set_sub("hair_sale", "change_status", True)
    _post(_client(REG_PHONE), "/admin/hair-order/9500/update", {"status": "reviewing"})
    assert _q1("SELECT status FROM hair_orders WHERE id=9500") == "reviewing", \
        "ادمین معمولی با گزینه فعال باید بتواند وضعیت را تغییر دهد"


def test_2_enabled_shop_action_allowed():
    _fixtures()
    _set_sub("products", "edit", True)
    _post(_client(REG_PHONE), "/admin/product/9500/edit",
          {"name": "EditedByRegular", "price": "2000", "category": "t", "description": "d", "in_stock": "1"})
    assert _q1("SELECT name FROM products WHERE id=9500") == "PolicyProd", \
        "ادمین عادی نباید محصول عمومی را ویرایش کند"


def test_2b_normal_admin_can_only_moderate_pending_channel_imports():
    _fixtures()
    conn = get_giso_db_conn()
    try:
        conn.execute("INSERT OR REPLACE INTO products "
                     "(id,name,price,category,in_stock,publish_status,source) "
                     "VALUES (9504,'ChannelPending',2000,'t',1,'pending','channel')")
        conn.execute("INSERT OR REPLACE INTO products "
                     "(id,name,price,category,in_stock,publish_status,source) "
                     "VALUES (9505,'SitePending',2000,'t',1,'pending','site')")
        conn.commit()
    finally:
        conn.close()
    c = _client(REG_PHONE)
    _post(c, "/admin/product/9504/publish", {})
    assert _q1("SELECT publish_status FROM products WHERE id=9504") == "published"
    _post(c, "/admin/product/9505/publish", {})
    assert _q1("SELECT publish_status FROM products WHERE id=9505") == "pending"

    conn = get_giso_db_conn()
    try:
        conn.execute("UPDATE products SET publish_status='pending' WHERE id=9504")
        conn.commit()
    finally:
        conn.close()
    _post(c, "/admin/product/9504/reject-import", {})
    assert _q1("SELECT publish_status FROM products WHERE id=9504") == "rejected"


# ───────────── ۲) سوییچ‌های تاریخی بی‌اثرند ─────────────
def test_3_disabled_hair_switch_is_inert():
    _fixtures()
    _set_sub("hair_sale", "change_status", False)
    _post(_client(REG_PHONE), "/admin/hair-order/9500/update", {"status": "approved"})
    assert _q1("SELECT status FROM hair_orders WHERE id=9500") == "approved"


def test_4_disabled_shop_edit_switch_is_inert():
    _fixtures()
    _set_sub("products", "edit", False)
    _post(_client(REG_PHONE), "/admin/product/9500/edit",
          {"name": "EditedDespiteLegacyOff", "price": "9", "category": "t", "description": "d", "in_stock": "1"})
    assert _q1("SELECT name FROM products WHERE id=9500") == "PolicyProd", \
        "سوییچ قدیمی نباید ممنوعیت ویرایش محصول عمومی را دور بزند"


def test_5_disabled_shop_delete_switch_is_inert():
    _fixtures()
    conn = get_giso_db_conn()
    try:
        conn.execute("INSERT OR REPLACE INTO products (id,name,price,category,in_stock,publish_status)"
                     " VALUES (9503,'LegacyOffDelete',1000,'t',1,'published')")
        conn.commit()
    finally:
        conn.close()
    _set_sub("products", "delete", False)
    _post(_client(REG_PHONE), "/admin/product/9503/delete", {})
    assert _q1("SELECT COUNT(*) FROM products WHERE id=9503") == 1, \
        "ادمین عادی نباید محصول عمومی را حذف کند"


def test_6_revoked_legacy_section_is_inert():
    _fixtures()
    conn = get_giso_db_conn()
    try:
        conn.execute("UPDATE giso_admin_permissions SET is_allowed=0 "
                     "WHERE admin_bale_id=? AND section='orders'", (str(REG_BID),))
        conn.commit()
    finally:
        conn.close()
    _post(_client(REG_PHONE), "/admin/shop-order/9500/status", {"status": "approved"})
    assert _q1("SELECT status FROM product_orders WHERE id=9500") == "approved"


def test_6b_normal_admin_sidebar_and_sensitive_routes_are_restricted():
    c = _client(REG_PHONE)
    response = c.get("/admin/dashboard")
    assert response.status_code == 200
    body = response.get_data(as_text=True)
    for label in (
        "پیشخوان کار من", "مدیریت خرید مو", "مدیریت بازارچه مو", "سفارش‌های فروشگاه",
        "نظرات عمومی", "مدیریت گفتگوها", "حساب کاربری",
    ):
        assert label in body
    for forbidden in ("مرکز مالی و کیف پول", "مدیریت AI", "تنظیمات سایت", "کاربران", "ادمین‌ها"):
        assert forbidden not in body
    assert "درآمد تکمیل‌شده" not in body

    for path in (
        "/admin/wallet", "/admin/settings", "/admin/ai", "/admin/users",
        "/admin/admin-management", "/admin/analyses", "/admin/notifications", "/admin/shop",
    ):
        denied = c.get(path, follow_redirects=False)
        assert denied.status_code == 302, path
        assert "/admin/dashboard" in (denied.headers.get("Location") or ""), path


# ───────────── ۳) سوپرادمین ─────────────
def test_7_super_always_allowed():
    _fixtures()
    c = _client(SUPER_PHONE)
    _post(c, "/admin/hair-order/9500/update", {"status": "completed"})
    assert _q1("SELECT status FROM hair_orders WHERE id=9500") == "completed"
    _post(c, "/admin/product/9500/edit",
          {"name": "SuperEdited", "price": "3000", "category": "t", "description": "d", "in_stock": "1"})
    assert _q1("SELECT name FROM products WHERE id=9500") == "SuperEdited"
    # حذف روی محصولی بدون سفارش وابسته آزموده می‌شود (FK constraint مانع حذف است،
    # نه مجوزدهی — این محدودیت دیتابیس است و ربطی به نقش ندارد).
    conn = get_giso_db_conn()
    try:
        conn.execute("INSERT OR REPLACE INTO products (id,name,price,category,in_stock,publish_status)"
                     " VALUES (9502,'DeletableProd',1000,'t',1,'published')")
        conn.commit()
    finally:
        conn.close()
    _post(c, "/admin/product/9502/delete", {})
    assert _q1("SELECT COUNT(*) FROM products WHERE id=9502") == 0, \
        "سوپرادمین باید بتواند محصول بدون وابستگی را حذف کند"


# ───────────── ۴) رگرسیون باگ admin_note ─────────────
def test_8_status_update_with_null_admin_note():
    """باگ واقعی: admin_note=NULL باعث AttributeError و شکست کل به‌روزرسانی می‌شد."""
    conn = get_giso_db_conn()
    try:
        conn.execute("INSERT OR REPLACE INTO hair_orders (id,customer_name,phone,status,length_cm,photo_path,admin_note,created_at)"
                     " VALUES (9501,'C','+98912','pending',60,'x.jpg',NULL,datetime('now'))")
        conn.commit()
    finally:
        conn.close()
    _post(_client(SUPER_PHONE), "/admin/hair-order/9501/update", {"status": "reviewing"})
    assert _q1("SELECT status FROM hair_orders WHERE id=9501") == "reviewing", \
        "به‌روزرسانی وضعیت نباید به‌خاطر admin_note تهی شکست بخورد"


# ───────────── ۵) صفحه‌بندی ─────────────
def test_9_pagination_limits_volume():
    conn = get_giso_db_conn()
    try:
        for i in range(9600, 9660):
            conn.execute("INSERT OR REPLACE INTO hair_orders (id,customer_name,phone,status,length_cm,photo_path,created_at)"
                         " VALUES (?,?,?,'pending',60,'x.jpg',datetime('now'))",
                         (i, f"C{i}", "+98912" + str(i)))
        conn.commit()
    finally:
        conn.close()
    from giso.panel.modules.hair_sale import HAIR_PAGE_SIZE
    body = _client(SUPER_PHONE).get("/admin/hair-orders").get_data(as_text=True)
    assert body.count("pnl-hair-card") <= HAIR_PAGE_SIZE, "صفحه‌بندی باید حجم را محدود کند"
    assert "صفحه" in body


def test_10_pagination_preserves_filter():
    body = _client(SUPER_PHONE).get("/admin/hair-orders?h_status=review").get_data(as_text=True)
    if "page=2" in body:
        assert "h_status=review" in body, "فیلتر باید در لینک صفحه‌بندی حفظ شود"


# ───────────── ۶) N+1 ─────────────
def test_11_no_n_plus_one_in_hair_list():
    import giso.panel.modules.hair_sale as _hs
    real = _hs.get_giso_db_conn
    count = {"n": 0}

    class _W:
        def __init__(self, c): self._c = c
        def execute(self, *a, **k):
            count["n"] += 1
            return self._c.execute(*a, **k)
        def __getattr__(self, n): return getattr(self._c, n)
        def __enter__(self): self._c.__enter__(); return self
        def __exit__(self, *a): return self._c.__exit__(*a)

    _hs.get_giso_db_conn = lambda: _W(real())
    try:
        _client(SUPER_PHONE).get("/admin/hair-orders")
    finally:
        _hs.get_giso_db_conn = real
    assert count["n"] < 25, f"الگوی N+1 برگشته است (کوئری خام={count['n']})"


# ───────────── ۷) اعلان‌ها ─────────────
def test_12_notifications_scope_hair_shop():
    from giso.panel.modules import notifications as N
    N.ensure_notifications_table()
    N.save_category_settings({"hair_sale": {"target_role": "admin", "destination": "site", "enabled": 1},
                              "shop": {"target_role": "admin", "destination": "site", "enabled": 1}})

    def mk(cat, target):
        conn = get_giso_db_conn()
        try:
            cur = conn.execute("INSERT INTO giso_notifications (category,subcategory,title,message,target_role,status,created_at)"
                               " VALUES (?,?,?,?,?,'unread',datetime('now'))", (cat, "t", "x", "m", target))
            conn.commit()
            return cur.lastrowid
        finally:
            conn.close()

    n_ok = mk("hair_sale", "admin")
    n_no = mk("shop", "super")
    c = _client(REG_PHONE)
    _post(c, f"/admin/notifications/{n_ok}/read", {})
    assert _q1("SELECT status FROM giso_notifications WHERE id=?", (n_ok,)) == "unread", \
        "مرکز اعلان وب برای ادمین عادی بسته است؛ صندوق کاری او در ربات قرار دارد"
    _post(c, f"/admin/notifications/{n_no}/read", {})
    assert _q1("SELECT status FROM giso_notifications WHERE id=?", (n_no,)) == "unread", \
        "ادمین نباید اعلان خارج حوزه را تغییر دهد"


def test_13_archive_all_respects_scope():
    from giso.panel.modules import notifications as N
    N.ensure_notifications_table()
    conn = get_giso_db_conn()
    try:
        cur = conn.execute("INSERT INTO giso_notifications (category,subcategory,title,message,target_role,status,created_at)"
                           " VALUES ('system','t','x','m','super','unread',datetime('now'))")
        nid = cur.lastrowid
        conn.commit()
    finally:
        conn.close()
    _post(_client(REG_PHONE), "/admin/notifications/archive-all", {})
    assert _q1("SELECT status FROM giso_notifications WHERE id=?", (nid,)) == "unread"


# ───────────── ۸) ساختاری ─────────────
def test_14_all_sensitive_handlers_decorated():
    shop_src = open(os.path.join(BASE_DIR, "giso", "shop", "panel", "admin.py"), encoding="utf-8").read()
    for fn in ("admin_product_add", "admin_product_edit", "admin_product_delete",
               "admin_product_toggle_stock", "admin_shop_order_status", "admin_product_publish"):
        i = shop_src.find(f"def {fn}(")
        assert i > 0 and "@require_panel_action" in shop_src[max(0, i - 200):i], f"{fn} گارد ندارد"
    hair_src = open(os.path.join(BASE_DIR, "giso", "hair_sale.py"), encoding="utf-8").read()
    for fn in ("admin_hair_order_update", "admin_hair_order_message", "admin_config_hair_prices"):
        i = hair_src.find(f"def {fn}(")
        assert i > 0 and "@require_panel_action" in hair_src[max(0, i - 200):i], f"{fn} گارد ندارد"


def test_15_analysis_rate_limit_remains_super_only():
    from giso_admin import get_giso_config, set_giso_config

    old_value = str(get_giso_config("rate_limit_minutes", "60") or "60")
    try:
        set_giso_config("rate_limit_minutes", "37")
        c = _client(REG_PHONE)
        response = _post(c, "/admin/config/analysis-ratelimit", {
            "rate_limit_enabled": "1", "rate_limit_minutes": "99", "rate_limit_type": "ip",
        })
        assert response.status_code == 302
        assert str(get_giso_config("rate_limit_minutes", "")) == "37"
        c.get("/admin/analyses")  # consume the denial flash
        assert "tab=ratelimit" not in c.get("/admin/analyses").get_data(as_text=True)
        assert "tab=ratelimit" in _client(SUPER_PHONE).get("/admin/analyses").get_data(as_text=True)
    finally:
        set_giso_config("rate_limit_minutes", old_value)


def _run():
    tests = [test_1_enabled_hair_action_allowed, test_2_enabled_shop_action_allowed,
             test_3_disabled_hair_switch_is_inert, test_4_disabled_shop_edit_switch_is_inert,
             test_5_disabled_shop_delete_switch_is_inert, test_6_revoked_legacy_section_is_inert,
             test_7_super_always_allowed, test_8_status_update_with_null_admin_note,
             test_9_pagination_limits_volume, test_10_pagination_preserves_filter,
             test_11_no_n_plus_one_in_hair_list, test_12_notifications_scope_hair_shop,
             test_13_archive_all_respects_scope, test_14_all_sensitive_handlers_decorated,
             test_15_analysis_rate_limit_remains_super_only]
    _seed()
    passed = 0
    for t in tests:
        try:
            t()
            passed += 1
            print(f"PASS  {t.__name__}")
        except AssertionError as e:
            print(f"FAIL  {t.__name__}: {e}")
            _FAILED.append(t.__name__)
        except Exception as e:  # noqa: BLE001
            print(f"ERROR {t.__name__}: {type(e).__name__}: {e}")
            _FAILED.append(t.__name__)
    print(f"\n{passed}/{len(tests)} tests passed")
    if _FAILED:
        print("Failed:", ", ".join(_FAILED))
        return False
    return True


if __name__ == "__main__":
    sys.exit(0 if _run() else 1)
