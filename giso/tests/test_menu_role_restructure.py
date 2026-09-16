# -*- coding: utf-8 -*-
"""Focused regression coverage for user/normal-admin navigation boundaries."""
from pathlib import Path

from giso.bot import _admin_kb, _user_kb
from giso.panel import authz
from giso.panel.permissions import MODULES_META, module_allowed, visible_modules
from giso.panel_user.permissions import USER_MODULES

ROOT = Path(__file__).resolve().parents[2]
REGULAR_ID = 777001
SUPER_ID = 1191639507


def _reply_labels(markup):
    return [button.text for row in markup.keyboard for button in row]


def test_normal_user_site_and_bot_roots_are_exact():
    assert USER_MODULES == [
        ("overview", "پیشخوان (خلاصه من)", "🏠"),
        ("hair_sale", "مدیریت مو", "💇‍♀️"),
        ("orders", "خریدهای من از فروشگاه", "🛍️"),
        ("analyses", "آنالیزها و برنامه من", "🔬"),
        ("wallet", "کیف پول و اعتبار", "💰"),
        ("chats", "پیام‌ها و پشتیبانی", "💬"),
        ("profile", "پروفایل", "👤"),
    ]
    assert _reply_labels(_user_kb()) == [
        "💰 کیف پول", "🎯 مأموریت", "💬 مشاور",
        "👤 پروفایل", "🎧 پشتیبانی", "📖 راهنما",
    ]

    # قرارداد جدید §۷: برچسب‌ها از MODULES_META رندر می‌شوند → بررسی روی خروجی واقعی
    from giso.app import create_app
    from giso.base import normalize_phone
    from giso.models import User, db
    app = create_app()
    client = app.test_client()
    ph = normalize_phone("09120000097")
    with app.app_context():
        if not User.query.filter_by(phone=ph).first():
            db.session.add(User(phone=ph, password_hash="h", name="تست منو"))
            db.session.commit()
    with client.session_transaction() as sess:
        sess["_user_id"] = ph
    sidebar = client.get("/dashboard/").get_data(as_text=True)
    for child in ("فروش مو به گیسو", "بازارچه مو", "خریدار مو"):
        assert child in sidebar
    for grp in ("اصلی", "خدمات", "پشتیبانی", "حساب کاربری"):
        assert ('pu-nav-group">%s</div>' % grp) in sidebar
    assert "pu-nav-tree" not in sidebar
    assert "<details" not in sidebar


def test_normal_admin_site_and_bot_roots_are_exact():
    menu = visible_modules("admin", {})
    assert [(item["module"], item["label"], item["icon"]) for item in menu] == [
        ("dashboard", "پیشخوان کار من", "📊"),
        ("hair_sale", "مدیریت خرید مو", "💇‍♀️"),
        ("marketplace", "مدیریت بازارچه مو", "🏪"),
        ("beauty_centers", "مدیریت مراکز زیبایی", "🏥"),
        ("shop_orders", "سفارش‌های فروشگاه", "🛒"),
        ("reviews", "نظرات عمومی", "⭐"),
        ("consults", "مدیریت گفتگوها", "💬"),
        ("account", "حساب کاربری", "👤"),
    ]
    assert _reply_labels(_admin_kb(REGULAR_ID)) == [
        "💇 خرید مو", "🛍 فروشگاه", "🏪 بازارچه", "💬 مدیریت گفتگوها",
    ]


def test_normal_admin_sensitive_modules_and_actions_fail_closed(monkeypatch):
    allowed_modules = {
            "dashboard", "hair_sale", "marketplace", "beauty_centers", "shop_orders",
            "reviews", "consults", "account",
    }
    blocked_modules = {
        "wallet", "referrals", "settings", "ai", "ratelimit", "users", "admins",
        "channel", "analyses", "notifications", "shop", "shop_super", "reports",
    }
    assert all(module_allowed(module, "admin", {}) for module in allowed_modules)
    assert not any(module_allowed(module, "admin", {}) for module in blocked_modules)

    monkeypatch.setattr(authz, "current_role_and_perms", lambda: ("admin", {}, "7"))
    allowed_actions = {
        "hair.update_status", "hair.set_price", "hair.set_note", "hair.message",
        "shop.order_status",
    }
    blocked_actions = {
        "hair.prices_config", "hair.commission", "shop.product_add", "shop.product_edit",
        "shop.product_stock", "shop.product_delete", "shop.channel_config",
        "shop.publish_mode", "shop.stats", "shop.product_publish", "shop.product_reject",
        "unknown.action",
    }
    assert all(authz.can_execute_panel_action(action)[0] for action in allowed_actions)
    assert not any(authz.can_execute_panel_action(action)[0] for action in blocked_actions)


def test_superadmin_menu_and_unrestricted_policy_are_preserved():
    expected_menu = [
        {"module": module, "label": label, "icon": icon,
         "group": __import__("giso.panel.permissions", fromlist=["MODULE_GROUPS"]).MODULE_GROUPS.get(module, "")}
        for module, label, icon in MODULES_META
    ]
    assert visible_modules("super", {}) == expected_menu
    assert _reply_labels(_admin_kb(SUPER_ID)) == [
        "📊 پیشخوان", "🛍 فروشگاه", "💇 خرید مو", "🔬 آنالیز",
        "🏪 بازارچه", "🏥 مراکز زیبایی", "💬 مدیریت گفتگوها", "🛠 مدیریت", "⚙️ تنظیمات سایت",
    ]
    for module in ("wallet", "settings", "users", "admins", "ai", "anything-new"):
        assert module_allowed(module, "super", {}) is True

    monkeypatch_role = authz.current_role_and_perms
    try:
        authz.current_role_and_perms = lambda: ("super", {}, str(SUPER_ID))
        for action in authz.PANEL_ACTIONS:
            assert authz.can_execute_panel_action(action) == (True, "")
    finally:
        authz.current_role_and_perms = monkeypatch_role


def test_channel_import_ui_has_only_approve_reject_and_generic_actions_are_guarded():
    restricted = (ROOT / "giso/panel/templates/modules/channel_products.html").read_text(encoding="utf-8")
    assert "admin_product_publish" in restricted
    assert "admin_product_reject" in restricted
    for forbidden in ("admin_product_add", "admin_product_edit", "admin_product_delete", "admin_product_toggle_stock"):
        assert forbidden not in restricted

    handler = (ROOT / "giso/shop/panel/admin.py").read_text(encoding="utf-8")
    assert "source\", \"\") == \"channel\"" in handler
    assert "p.publish_status == \"pending\"" in handler


def test_hair_and_marketplace_submission_notifications_stay_in_their_queues():
    hair_source = (ROOT / "giso/hair_sale.py").read_text(encoding="utf-8")
    selected = hair_source[hair_source.index("def _finalize_selected_path"):hair_source.index("def _hair_sale_duplicate_guard")]
    assert "create_marketplace_listing" in selected
    assert selected.count("_finalize_hair_order") == 2  # both + direct; never marketplace-only

    finalize = hair_source[hair_source.index("def _finalize_hair_order"):hair_source.index("def _finalize_selected_path")]
    assert finalize.count("send_hair_order_notification_to_admins(") == 1
    assert finalize.count("notify_listing_created(linked_listing)") == 1
    assert "if linked_listing is not None" in finalize

    market_source = (ROOT / "giso/marketplace/services.py").read_text(encoding="utf-8")
    create = market_source[market_source.index("def create_marketplace_listing"):market_source.index("def refresh_listing_offer_stats")]
    assert create.count("notify_listing_created(listing)") == 1
    notify = market_source[market_source.index("def notify_listing_created"):market_source.index("def notify_listing_status")]
    assert '"marketplace", "listing_new"' in notify
    assert "send_hair_order_notification_to_admins" not in notify


def test_selected_hair_sale_path_routes_to_exactly_the_requested_workflow(monkeypatch):
    """Behavioral regression: direct/Marketplace/both cannot cross-call a queue."""
    from flask import Flask, session
    from types import SimpleNamespace
    import giso.hair_sale as hair
    import giso.marketplace.services as market

    app = Flask(__name__)
    app.secret_key = "menu-routing-test-secret"
    app.add_url_rule("/hair-sale", endpoint="hair_sale", view_func=lambda: "ok")
    calls = []

    def fake_finalize(temp, user, name, phone, region="", contact_time="", linked_listing=None):
        calls.append(("hair", linked_listing))
        return "hair-result"

    def fake_create(temp, user, region=""):
        calls.append(("market", None))
        return SimpleNamespace(id=91)

    listing = SimpleNamespace(id=92)
    monkeypatch.setattr(hair, "_finalize_hair_order", fake_finalize)
    monkeypatch.setattr(market, "create_marketplace_listing", fake_create)
    monkeypatch.setattr(market, "build_listing_from_temp", lambda *a, **k: listing)

    with app.test_request_context("/hair-sale"):
        session["hair_temp"] = {"sale_path": "marketplace"}
        response = hair._finalize_selected_path(
            {"sale_path": "marketplace"}, SimpleNamespace(id=1), "کاربر", "09120000000"
        )
        assert response.status_code == 302
        assert calls == [("market", None)]

    calls.clear()
    with app.test_request_context("/hair-sale"):
        assert hair._finalize_selected_path(
            {"sale_path": "giso"}, SimpleNamespace(id=1), "کاربر", "09120000000"
        ) == "hair-result"
        assert calls == [("hair", None)]

    calls.clear()
    with app.test_request_context("/hair-sale"):
        assert hair._finalize_selected_path(
            {"sale_path": "both"}, SimpleNamespace(id=1), "کاربر", "09120000000"
        ) == "hair-result"
        assert calls == [("hair", listing)]


def test_direct_and_both_finalize_emit_each_admin_notification_once(monkeypatch):
    """Behavioral regression for the two notification calls after one commit."""
    from flask import Flask
    from types import SimpleNamespace
    import giso.hair_sale as hair
    import giso.marketplace.services as market
    import giso.panel.modules.notifications as notifications
    import giso.referrals as referrals

    class FakeSession:
        def add(self, _value):
            return None

        def flush(self):
            return None

        def commit(self):
            return None

    class FakeHairOrder:
        def __init__(self, **values):
            self.__dict__.update(values)
            self.id = 731
            self.created_at = "2026-08-20 00:00:00"

    emitted = {"hair": 0, "market": 0}
    monkeypatch.setattr(hair, "HairOrder", FakeHairOrder)
    monkeypatch.setattr(hair.db, "session", FakeSession())
    monkeypatch.setattr(hair, "send_hair_order_notification_to_admins",
                        lambda _order: emitted.__setitem__("hair", emitted["hair"] + 1))
    monkeypatch.setattr(market, "notify_listing_created",
                        lambda _listing: emitted.__setitem__("market", emitted["market"] + 1))
    monkeypatch.setattr(notifications, "log_user_notification", lambda *a, **k: True)
    monkeypatch.setattr(referrals, "on_hair_order_created", lambda _order_id: None)

    app = Flask(__name__)
    app.secret_key = "finalize-notification-test-secret"
    app.add_url_rule("/hair-sale", endpoint="hair_sale", view_func=lambda: "ok")
    temp = {
        "sale_path": "giso", "photo_path": "uploads/already-final.jpg",
        "description": "", "length_cm": 50,
    }
    user = SimpleNamespace(id=12)

    with app.test_request_context("/hair-sale"):
        hair._finalize_hair_order(temp, user, "کاربر", "09120000000")
    assert emitted == {"hair": 1, "market": 0}

    linked = SimpleNamespace(id=44, source_hair_order_id=None, photo_path="", updated_at="")
    with app.test_request_context("/hair-sale"):
        hair._finalize_hair_order(
            {**temp, "sale_path": "both"}, user, "کاربر", "09120000000",
            linked_listing=linked,
        )
    assert emitted == {"hair": 2, "market": 1}


def test_financial_notifications_remain_superadmin_only():
    from giso.panel.modules.notifications import (
        DEFAULT_CATEGORY_SETTINGS, _normalize_target_role,
        get_allowed_notification_roles_for_user,
    )

    assert _normalize_target_role("super") == "super"
    assert _normalize_target_role("both") == "both"
    assert DEFAULT_CATEGORY_SETTINGS["wallet"]["target_role"] == "super"
    assert DEFAULT_CATEGORY_SETTINGS["hair_sale"]["target_role"] == "admin"
    assert "super" not in get_allowed_notification_roles_for_user("admin")


def test_display_phone_is_eleven_digits_and_dates_are_shamsi():
    from giso.base import display_phone, to_shamsi, gregorian_to_jalali

    assert display_phone("+989156012931") == "09156012931"
    assert display_phone("989120000000") == "09120000000"
    assert display_phone("9120000000") == "09120000000"
    assert len(display_phone("09156012931")) == 11
    assert gregorian_to_jalali(2026, 3, 21) == (1405, 1, 1)
    jy, jm, jd = gregorian_to_jalali(2026, 8, 20)
    assert jy == 1405
    assert jm == 5
    shamsi = to_shamsi("2026-08-20 14:30:00", with_time=False)
    assert "۱۴۰۵" in shamsi


def test_market_and_chats_admin_modules_import_and_keyboards():
    from giso.bot_market_admin import market_menu_kb, market_menu_text, STATUS_FA
    from giso.bot_chats_admin import chats_menu_kb, chats_menu_text, KIND_LABEL

    mk = [b.text for row in market_menu_kb().keyboard for b in row]
    assert "📋 درخواست‌های بازارچه" in mk
    assert "🔙 بازگشت" in mk
    assert "انتشار" in market_menu_text() or "بازارچه" in market_menu_text()
    assert STATUS_FA["pending_review"]
    ck = [b.text for row in chats_menu_kb().keyboard for b in row]
    assert "💇 گفتگوی خرید مو" in ck
    assert "🛍 گفتگوی فروشگاه" in ck
    assert "🏪 گفتگوی بازارچه" in ck
    assert "💬 پشتیبانی" in ck
    assert set(KIND_LABEL) == {"hair", "shop", "market", "support"}
