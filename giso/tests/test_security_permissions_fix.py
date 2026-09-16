#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
تست‌های امنیت و دسترسی — رفع R1/R2/R3/R5/R9 + سیستم زیرگزینه ادمین معمولی.

پوشش (مطابق Task 13):
  A) authorization اعلان‌ها — ادمین معمولی نتواند اعلان سوپر را تغییر دهد
  B) سازگاری سیاست نقش بین list / unread / mark_all / archive_all / set_status
  C) یکسانی callback بین سوپرادمین و ادمین معمولی
  D) تنظیم قدیمی خاموش → دکمه عملیاتی همچنان دیده شود
  E) callback عملیاتی با نقش ثابت ادمین اجرا شود
  F) happy path عملیاتی حفظ شود
  G) سوپرادمین همیشه همه‌چیز را می‌بیند و اجرا می‌کند
  H) گارد hair_review (R3)
  I) پاکسازی bot_states (R9)
  J) گارد سطح-route برای POSTهای حساس (R5)

اجرا:  python giso/tests/test_security_permissions_fix.py
"""
import os
import sys

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if BASE_DIR not in sys.path:
    sys.path.append(BASE_DIR)

SUPER_BID = 1191639507          # giso/config.py::SUPERADMIN_BALE_ID
REGULAR_BID = 990101            # ادمین معمولی تستی
SECTION = "hair_sale"

_FAILED = []


# ═══════════════════ کمکی ═══════════════════
def _seed_regular_admin():
    from giso.base import _upsert_giso_user
    _upsert_giso_user(bale_id=REGULAR_BID, phone="+989120000991",
                      first_name="AdminTest", username="admintest",
                      is_admin=True, contact_shared=True, pending_request=False)


def _reset_section(bale_id=REGULAR_BID, section=SECTION):
    from giso.base import get_giso_db_conn
    conn = get_giso_db_conn()
    try:
        conn.execute("DELETE FROM giso_admin_permissions WHERE admin_bale_id=? AND section=?",
                     (str(bale_id), section))
        conn.commit()
    finally:
        conn.close()


def _insert_notification(category, target_role, title="t", status="unread"):
    from giso.base import get_giso_db_conn
    from giso.panel.modules.notifications import ensure_notifications_table, TABLE
    ensure_notifications_table()
    conn = get_giso_db_conn()
    try:
        cur = conn.execute(
            "INSERT INTO %s (category, subcategory, title, message, target_role, status, created_at) "
            "VALUES (?,?,?,?,?,?,datetime('now'))" % TABLE,
            (category, "test", title, "m", target_role, status))
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def _notif_status(nid):
    from giso.base import get_giso_db_conn
    from giso.panel.modules.notifications import TABLE
    conn = get_giso_db_conn()
    try:
        row = conn.execute("SELECT status FROM %s WHERE id=?" % TABLE, (nid,)).fetchone()
        return row["status"] if row else None
    finally:
        conn.close()


def _force_category_visible_to_admin(category="hair_sale"):
    """دستهٔ تستی را برای نقش admin قابل مشاهده کن (پیش‌فرض پروژه super است)."""
    from giso.panel.modules.notifications import save_category_settings
    save_category_settings({category: {"target_role": "admin", "destination": "site", "enabled": 1}})


# ═══════════════════ A) authorization اعلان‌ها (R1) ═══════════════════
def test_A_regular_admin_cannot_mutate_super_notification():
    from giso.panel.modules.notifications import set_status
    nid = _insert_notification("system", "super", "super-only")
    assert _notif_status(nid) == "unread"

    ok = set_status(nid, "archived", role="admin")
    assert ok is False, "ادمین معمولی نباید بتواند اعلان سوپر را آرشیو کند"
    assert _notif_status(nid) == "unread", "وضعیت نباید تغییر کرده باشد"

    # سوپرادمین باید بتواند
    assert set_status(nid, "archived", role="super") is True
    assert _notif_status(nid) == "archived"


def test_A2_regular_admin_can_mutate_own_notification():
    from giso.panel.modules.notifications import set_status
    _force_category_visible_to_admin("hair_sale")
    nid = _insert_notification("hair_sale", "admin", "admin-visible")
    assert set_status(nid, "read", role="admin") is True
    assert _notif_status(nid) == "read"


# ═══════════════════ B) سازگاری سیاست نقش (R2) ═══════════════════
def test_B_role_policy_is_single_source():
    from giso.panel.modules.notifications import (
        get_allowed_notification_roles_for_user, can_modify_notification)
    assert set(get_allowed_notification_roles_for_user("super")) == {"super", "admin", "both"}
    assert set(get_allowed_notification_roles_for_user("admin")) == {"admin", "both"}
    assert "super" not in get_allowed_notification_roles_for_user("admin")

    row = {"target_role": "super", "category": "system"}
    assert can_modify_notification("admin", row) is False
    assert can_modify_notification("super", row) is True


def test_B2_list_and_mutate_scope_match():
    """آنچه ادمین می‌بیند باید دقیقاً همان چیزی باشد که می‌تواند تغییر دهد."""
    from giso.panel.modules.notifications import list_notifications, set_status
    _force_category_visible_to_admin("hair_sale")
    _insert_notification("hair_sale", "admin", "visible-a")
    _insert_notification("system", "super", "hidden-s")

    visible_ids = {n["id"] for n in list_notifications("admin", limit=500)}
    for n in list_notifications("super", limit=500):
        if n["target_role"] == "super":
            # هر اعلانی که ادمین نمی‌بیند، نباید بتواند تغییرش دهد
            assert n["id"] not in visible_ids
            assert set_status(n["id"], "read", role="admin") is False


def test_B3_archive_all_uses_same_policy():
    from giso.panel.modules.notifications import archive_all
    nid_super = _insert_notification("system", "super", "keep-me")
    archive_all("admin")
    assert _notif_status(nid_super) == "unread", \
        "archive_all(admin) نباید اعلان سوپر را آرشیو کند"


# ═══════════════════ C) یکسانی callback ═══════════════════
def test_C_callback_identical_for_both_roles():
    from giso.bot_hair_admin import order_action_kb
    all_on = {k: True for k in ("review", "reject", "price", "note", "message", "approve")}
    all_on.update({f"bot_{k}_visible": True for k in list(all_on)})

    kb_super = order_action_kb(42, all_on, idx=0, total=3, pager="req")
    kb_admin = order_action_kb(42, all_on, idx=0, total=3, pager="req")

    cb_super = [b.callback_data for row in kb_super.inline_keyboard for b in row]
    cb_admin = [b.callback_data for row in kb_admin.inline_keyboard for b in row]
    assert cb_super == cb_admin, "callback_data باید برای هر دو نقش یکسان باشد"
    assert "hair_review|42" in cb_super
    assert "hair_rej|42" in cb_super


# ═══════════════════ D) نمایش ═══════════════════
def test_D_hidden_option_not_in_keyboard():
    from giso.bot_permissions import set_option_visibility, get_visible_options
    from giso.bot_hair_admin import order_action_kb, get_admin_sub_options
    _seed_regular_admin()
    _reset_section()

    set_option_visibility(SECTION, "review", REGULAR_BID, False)
    assert "review" in get_visible_options(SECTION, REGULAR_BID)

    subs = get_admin_sub_options(str(REGULAR_BID), SECTION)
    subs["bot_review_visible"] = False
    subs["review"] = False
    kb = order_action_kb(7, subs)
    cbs = [b.callback_data for row in kb.inline_keyboard for b in row]
    assert any(c.startswith("hair_review|") for c in cbs), \
        "تنظیم تاریخی نباید دکمه عملیاتی را مخفی کند"


# ═══════════════════ E) گارد اجرا (ضد spoofing) ═══════════════════
def test_E_hidden_option_callback_blocked():
    from giso.bot_permissions import set_option_visibility, can_execute_callback
    _seed_regular_admin()
    _reset_section()
    set_option_visibility(SECTION, "review", REGULAR_BID, False)

    allowed, sec, key = can_execute_callback("hair_review|99", REGULAR_BID)
    assert allowed is True, "ادمین تأییدشده باید callback عملیاتی را اجرا کند"
    assert (sec, key) == (SECTION, "review")


def test_E2_other_options_still_work_when_one_hidden():
    from giso.bot_permissions import set_option_visibility, can_execute_callback
    _seed_regular_admin()
    _reset_section()
    set_option_visibility(SECTION, "review", REGULAR_BID, False)
    allowed, _, _ = can_execute_callback("hair_rej|99", REGULAR_BID)
    assert allowed is True, "خاموش کردن یک گزینه نباید بقیه را ببندد"


def test_E3_unregistered_callback_untouched():
    from giso.bot_permissions import can_execute_callback
    allowed, sec, key = can_execute_callback("some_unrelated_cb", REGULAR_BID)
    assert (allowed, sec, key) == (True, None, None), \
        "callback خارج از رجیستری باید رفتار قبلی را حفظ کند"


# ═══════════════════ F) happy path ═══════════════════
def test_F_enabled_option_visible_and_executable():
    from giso.bot_permissions import (set_option_visibility, get_visible_options,
                                      can_execute_callback)
    _seed_regular_admin()
    _reset_section()
    set_option_visibility(SECTION, "review", REGULAR_BID, True)

    assert "review" in get_visible_options(SECTION, REGULAR_BID)
    allowed, _, _ = can_execute_callback("hair_review|5", REGULAR_BID)
    assert allowed is True, "گزینه روشن باید اجرا شود — همان جریان اصلی"


def test_F2_default_is_permissive_backward_compatible():
    """بدون تنظیم صریح، رفتار باید دقیقاً مثل قبل (باز) باشد."""
    from giso.bot_permissions import can_execute_callback, get_visible_options
    _seed_regular_admin()
    _reset_section()
    assert can_execute_callback("hair_review|1", REGULAR_BID)[0] is True
    assert len(get_visible_options(SECTION, REGULAR_BID)) > 0


# ═══════════════════ G) سوپرادمین ═══════════════════
def test_G_super_admin_always_full_access():
    from giso.bot_permissions import (set_option_visibility, can_execute_callback,
                                      get_visible_options, section_options)
    # حتی اگر برای سوپر هم رکورد خاموش ثبت شود
    set_option_visibility(SECTION, "review", SUPER_BID, False)
    assert can_execute_callback("hair_review|1", SUPER_BID)[0] is True
    assert len(get_visible_options(SECTION, SUPER_BID)) == len(section_options(SECTION))


def test_G2_non_admin_has_no_access():
    from giso.bot_permissions import get_visible_options, can_access_option
    stranger = 424242
    assert get_visible_options(SECTION, stranger) == set()
    assert can_access_option(SECTION, "review", stranger) is False


# ═══════════════════ H) گارد hair_review (R3) ═══════════════════
def test_H_hair_review_in_callback_suboption_map():
    from giso.bot_hair_admin import CALLBACK_SUBOPTION, HAIR_SUBOPTIONS
    assert CALLBACK_SUBOPTION.get("hair_review") == "review", \
        "R3: hair_review باید در نگاشت گارد باشد"
    assert "review" in HAIR_SUBOPTIONS
    # alias قدیمی هم پوشش داده شود
    assert CALLBACK_SUBOPTION.get("hair_app") == "review"


# ═══════════════════ I) پاکسازی bot_states (R9) ═══════════════════
def test_I_bot_states_aligned_with_runtime():
    from giso.bot_states import CallbackPatterns, HairStates
    # الگوی نادرست قبلی نباید به‌عنوان «مقدار» برگردد.
    # (ذکر آن داخل کامنت توضیحی مجاز است — فقط انتساب نباید وجود داشته باشد.)
    src = open(os.path.join(BASE_DIR, "giso", "bot_states.py"), encoding="utf-8").read()
    code_lines = [ln.split("#")[0] for ln in src.splitlines()]
    code_only = "\n".join(ln for ln in code_lines if "•" not in ln)
    assert '"hair_pg|rep|' not in code_only, "R9: الگوی نادرست hair_pg|rep نباید مقداردهی شود"
    assert '"hair_pg|chat|' not in code_only, "R9: الگوی بدون handler نباید مقداردهی شود"
    assert CallbackPatterns.REPORT_PAGE == "hair_rep|{scope}|{page}"
    assert HairStates.PHONE_SEARCH == "waiting_hair_phone_search"
    assert HairStates.STATUS_MENU == "in_hair_status"


def test_I2_state_prefixes_match_live_code():
    """پیشوندهای state باید با آنچه bot.py واقعاً می‌سازد یکی باشند."""
    from giso.bot_states import HairStates
    live = open(os.path.join(BASE_DIR, "giso", "bot.py"), encoding="utf-8").read()
    for prefix in (HairStates.PRICE_INPUT, HairStates.NOTE_INPUT,
                   HairStates.ADMIN_MSG_INPUT, HairStates.OBJECTION_INPUT):
        assert f'"{prefix}_' in live or f"'{prefix}_" in live or f"{prefix}_{{" in live, \
            f"state {prefix} در کد زنده یافت نشد"


# ═══════════════════ J) گارد سطح-route (R5) ═══════════════════
def test_J_sensitive_routes_have_require_super():
    src = open(os.path.join(BASE_DIR, "giso", "panel", "routes.py"), encoding="utf-8").read()
    assert "def require_super(" in src, "R5: دکوراتور require_super باید تعریف شده باشد"
    for fn in ("backup_now", "restart_bot", "ai_provider_delete",
               "notification_settings", "ai_log_rollback"):
        idx = src.find(f"def {fn}(")
        assert idx > 0, f"route {fn} یافت نشد"
        assert "@require_super" in src[max(0, idx - 200):idx], \
            f"R5: route {fn} باید @require_super داشته باشد"


def test_J2_archive_all_no_inline_sql():
    src = open(os.path.join(BASE_DIR, "giso", "panel", "routes.py"), encoding="utf-8").read()
    assert "target_role IN ('admin','both')" not in src, \
        "R2: SQL درون-route با فیلتر متفاوت باید حذف شده باشد"
    assert "_notif.archive_all(role)" in src


# ═══════════════════ اجرا ═══════════════════
def _run():
    tests = [
        test_A_regular_admin_cannot_mutate_super_notification,
        test_A2_regular_admin_can_mutate_own_notification,
        test_B_role_policy_is_single_source,
        test_B2_list_and_mutate_scope_match,
        test_B3_archive_all_uses_same_policy,
        test_C_callback_identical_for_both_roles,
        test_D_hidden_option_not_in_keyboard,
        test_E_hidden_option_callback_blocked,
        test_E2_other_options_still_work_when_one_hidden,
        test_E3_unregistered_callback_untouched,
        test_F_enabled_option_visible_and_executable,
        test_F2_default_is_permissive_backward_compatible,
        test_G_super_admin_always_full_access,
        test_G2_non_admin_has_no_access,
        test_H_hair_review_in_callback_suboption_map,
        test_I_bot_states_aligned_with_runtime,
        test_I2_state_prefixes_match_live_code,
        test_J_sensitive_routes_have_require_super,
        test_J2_archive_all_no_inline_sql,
    ]
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
