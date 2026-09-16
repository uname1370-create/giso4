# -*- coding: utf-8 -*-
"""Site-only Special role: get_admin_target + sidebar + module allowlist.

Loads permissions.py by path so giso.panel.__init__ (Flask) is not imported.
Does not touch bot keyboards.
"""
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SPECIAL_PHONE = "09353258836"
SUPER_PHONE = "09156012931"


def _load_permissions():
    path = ROOT / "giso/panel/permissions.py"
    spec = importlib.util.spec_from_file_location("giso_panel_permissions_iso", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_get_admin_target_returns_special_for_sadeghi_phone():
    mod = _load_permissions()
    target = mod.get_admin_target(SPECIAL_PHONE)
    assert target.get("role") == "special"
    assert target.get("phone")
    super_target = mod.get_admin_target(SUPER_PHONE)
    assert super_target.get("role") == "super"


def test_special_sidebar_is_the_requested_nav():
    mod = _load_permissions()
    menu = mod.visible_modules("special", {})
    assert [(item["module"], item["label"], item["icon"]) for item in menu] == list(mod.SPECIAL_ADMIN_NAV)
    modules = [item["module"] for item in menu]
    assert modules == [
        "dashboard", "aga_reza", "hair_sale", "shop_orders", "marketplace",
        "beauty_centers", "consults", "special_reports", "account",
    ]
    assert "wallet" not in modules
    assert "users" not in modules
    assert "reviews" not in modules
    assert "shop" not in modules


def test_special_cannot_open_finance_users_security_ai():
    mod = _load_permissions()
    blocked = {
        "wallet", "users", "admins", "ai", "settings", "shop", "analyses",
        "reports", "monitoring", "channel", "ratelimit", "notifications",
        "super_assistant", "referrals",
    }
    assert blocked <= mod.SUPER_ONLY_MODULES
    for module in blocked:
        assert mod.module_allowed(module, "special", {}) is False
    for module in mod.SPECIAL_ADMIN_MODULES:
        assert mod.module_allowed(module, "special", {}) is True
    assert mod.module_allowed("reviews", "special", {}) is False


def test_regular_admin_and_super_menus_unchanged():
    mod = _load_permissions()
    admin_menu = [(item["module"], item["label"], item["icon"]) for item in mod.visible_modules("admin", {})]
    assert admin_menu == list(mod.REGULAR_ADMIN_NAV)
    assert "aga_reza" not in [item["module"] for item in mod.visible_modules("admin", {})]
    assert "special_reports" not in [item["module"] for item in mod.visible_modules("admin", {})]
    super_menu = [item["module"] for item in mod.visible_modules("super", {})]
    assert super_menu == [module for module, _label, _icon in mod.MODULES_META]
    assert mod.module_allowed("wallet", "super", {}) is True
    assert mod.module_allowed("reviews", "admin", {}) is True
    assert mod.module_allowed("aga_reza", "admin", {}) is False
    assert mod.module_allowed("wallet", "admin", {}) is False


def test_sidebar_template_has_special_role_branch():
    sidebar = (ROOT / "giso/panel/templates/partials/panel_sidebar.html").read_text(encoding="utf-8")
    assert "role == 'special'" in sidebar
    routes = (ROOT / "giso/panel/routes.py").read_text(encoding="utf-8")
    assert "def require_special" in routes
    assert "def aga_reza():" in routes
    assert "def special_reports():" in routes
    assert "@require_manage" in routes
    perms = (ROOT / "giso/panel/permissions.py").read_text(encoding="utf-8")
    body = perms[perms.find("def get_admin_target"):]
    assert "if is_special_admin(phone=phone_norm):" in body
    assert 'return {"role": "special"' in body
    stepup = (ROOT / "giso/stepup.py").read_text(encoding="utf-8")
    target_fn = stepup[stepup.find("def _admin_panel_target"):stepup.find("def _admin_panel_is_verified")]
    assert "is_special_admin(phone=phone_norm)" in target_fn
    assert '"special"' in target_fn
    assert target_fn.find("is_special_admin") < target_fn.find("find_giso_admin_by_phone")
