# -*- coding: utf-8 -*-
"""
giso/panel/modules/notifications.py — ماژول «🔔 مدیریت اعلان‌ها» (فاز جامع اعلان‌ها)

مرکز واحد مدیریت اعلان‌های سایت / ربات / فروشگاه / آنالیز / فروش مو:

- جدول `giso_notifications` در giso.db (migration idempotent — جداول قبلی دست نمی‌خورد)
- تنظیمات هر دسته در `giso_config` (bot.db) — target_role / enabled / destination
- سوپرادمین همه‌چیز را می‌بیند و مدیریت می‌کند؛ ادمین معمولی فقط دسته‌های مجاز خودش
- `log_notification()` مرکز ثبت همه رویدادها (hook های حداقلی از ماژول‌های فعلی)
- ارسال به بله با همان الگوی موجود (HTTP مستقیم + `_target_admin_ids`) — فقط برای دسته‌های
  با destination شامل bot؛ بدون توکن بی‌صدا رد می‌شود
- همگام‌سازی (sync) برای رویدادهایی که از ربات/کانال می‌آیند (بدون دست‌زدن به
  channel_importer / bot): پست‌های کانال، سفارش‌های فروش مو، آنالیزهای جدید
- آرشیو خودکار بعد از چند روز (پیش‌فرض ۷ روز، قابل تنظیم از پنل)
"""
import json
import logging
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta

from giso.base import get_giso_db_conn

logger = logging.getLogger("giso_panel_notifications")

# ارسال اعلان‌های بله در پس‌زمینه (غیرمسدودکننده برای درخواست Flask / event loop ربات)
_NOTIFY_POOL = ThreadPoolExecutor(max_workers=4, thread_name_prefix="giso_notify")

TABLE = "giso_notifications"
CONFIG_KEY = "notif_category_settings_v2"
CONFIG_ARCHIVE_DAYS = "notif_auto_archive_days"
CONFIG_SOUND = "notif_sound_on"
DEFAULT_ARCHIVE_DAYS = 7
USER_NOTIFICATION_RETENTION_HOURS = 24 * 7

# ───────────────────── دسته‌ها و پیش‌فرض‌ها ─────────────────────
# target_role: admin / super / both / none
# destination: site / bot / both  (bot = ارسال در ربات بله به ادمین‌ها)
DEFAULT_CATEGORY_SETTINGS = {
    # بیشتر دسته‌ها پیش‌فرض فقط سوپر هستند؛ اعلان‌های عملیاتی بازارچه نیز بدون
    # افزودن جریان قضاوتی، به نقش‌های مدیر مجاز می‌رسند. مقصد پیش‌فرض سایت + بله است.
    "shop":      {"target_role": "admin", "enabled": 1, "destination": "both", "title": "فروشگاه"},
    "hair_sale": {"target_role": "admin", "enabled": 1, "destination": "both", "title": "فروش مو"},
    "marketplace": {"target_role": "both", "enabled": 1, "destination": "both", "title": "بازارچه مو"},
    "beauty_centers": {"target_role": "both", "enabled": 1, "destination": "both", "title": "مراکز زیبایی"},
    "analysis":  {"target_role": "super", "enabled": 1, "destination": "both", "title": "آنالیز"},
    "users":     {"target_role": "super", "enabled": 1, "destination": "both", "title": "کاربران"},
    "wallet":    {"target_role": "super", "enabled": 1, "destination": "both", "title": "کیف پول"},
    "channel":   {"target_role": "admin", "enabled": 1, "destination": "both", "title": "کانال بله"},
    "bot":       {"target_role": "super", "enabled": 1, "destination": "both", "title": "ربات"},
    "security":  {"target_role": "super", "enabled": 1, "destination": "both", "title": "امنیت"},
    "system":    {"target_role": "super", "enabled": 1, "destination": "both", "title": "سیستم"},
}

# ردیف‌های پیش‌فرض اعلان (مطابق جدول فاز) — برای مستندات/تست و هماهنگی subcategory ها
DEFAULT_ROWS = [
    # (اعلان، category، subcategory، admin، super)
    ("سفارش جدید فروشگاه",       "shop",      "order",         1, 1),
    ("تسویه سبد خرید",           "shop",      "checkout",      1, 1),
    ("اعلان موجودی",             "shop",      "stock_notify",  1, 1),
    ("تسویه کیف پول",            "wallet",    "settlement",    0, 1),
    ("بن کاربر",                 "users",     "ban",           0, 1),
    ("حذف کاربر",                "users",     "delete",        0, 1),
    ("ثبت‌نام کاربر",            "users",     "register",      0, 1),
    ("ورود سوپرادمین",           "security",  "super_login",   0, 1),
    ("ورود دومرحله‌ای (step-up)", "security",  "step_up",       0, 1),
    ("ریستارت ربات",             "system",    "restart",       0, 1),
    ("بکاپ خودکار",              "system",    "backup",        0, 1),
    ("خطای سیستم",               "system",    "error",         0, 1),
    ("درخواست فروش مو",          "hair_sale", "request",       1, 1),
    ("تأیید فروش مو",            "hair_sale", "approved",      1, 1),
    ("رد فروش مو",               "hair_sale", "rejected",      1, 1),
    ("پیام کاربر",               "hair_sale", "message",       1, 1),
    ("اعتراض",                   "hair_sale", "complaint",     1, 1),
    ("آگهی جدید بازارچه",        "marketplace", "listing_new", 1, 1),
    ("درخواست خرید مو",          "marketplace", "buyer_request", 1, 1),
    ("تغییر وضعیت آگهی",         "marketplace", "listing_status", 1, 1),
    ("پیشنهاد جدید",             "marketplace", "offer_new", 1, 1),
    ("تغییر وضعیت پیشنهاد",      "marketplace", "offer_status", 1, 1),
    ("بسته‌شدن گفتگو",           "marketplace", "chat_closed", 1, 1),
    ("امتیاز ستاره‌ای جدید",     "marketplace", "review_created", 1, 1),
    ("حذف نرم آگهی",             "marketplace", "listing_deleted", 0, 1),
    ("درخواست مرکز زیبایی",       "beauty_centers", "center_new", 1, 1),
    ("تغییر وضعیت مرکز",          "beauty_centers", "center_status", 1, 1),
    ("گزارش مرکز زیبایی",         "beauty_centers", "report", 1, 1),
    ("آنالیز جدید",              "analysis",  "new",           1, 1),
    ("درخواست مشاوره",           "analysis",  "consultant",    1, 1),
    ("درخواست محصول",            "analysis",  "product_request", 1, 1),
    ("پست جدید کانال",           "channel",   "post",          1, 1),
    ("تأیید محصول کانال",        "channel",   "product_approved", 1, 1),
    ("خطای ربات",                "bot",       "error",         0, 1),
    ("رویداد ربات",              "bot",       "event",         0, 1),
]

CATEGORY_ICONS = {
    "shop": "🛍", "hair_sale": "💇", "marketplace": "🏪", "beauty_centers": "🏥", "analysis": "🔬", "users": "👥",
    "wallet": "💳", "channel": "📢", "bot": "🤖", "security": "🔐", "system": "⚙️",
}

# فاز جامع UX: هر اعلان باید لینک مستقیم به بخش خودش داشته باشد
# نگاشت category → (نام فارسی، endpoint پنل)؛ برای sourceهای خاص، پارامتر عمیق‌تر می‌سازیم
CATEGORY_FA = {k: v["title"] for k, v in DEFAULT_CATEGORY_SETTINGS.items()}

CATEGORY_ROUTES = {
    "shop": "panel.shop",
    "hair_sale": "panel.hair_sale",
    "marketplace": "panel.marketplace",
    "beauty_centers": "panel.beauty_centers",
    "analysis": "panel.analyses",
    "users": "panel.users",
    "wallet": "panel.wallet",
    "channel": "panel.channel",
    "bot": "panel.settings",
    "security": "panel.settings",
    "system": "panel.notifications",
}


from giso.panel.modules import notifications as _npkg
from .helpers import *  # noqa: F401,F403
from .helpers import _exists, _now, _styled_bot_message  # noqa: F401


def log_notification(category, subcategory="", title="", message="",
                     target_role=None, source_type="", source_id=None, recipient_id="",
                     destination=None):
    """ثبت event اعلان؛ recipient_id برای اعلان per-user استفاده می‌شود."""
    """
    ثبت یک رکورد اعلان — مرکز همه رویدادها.

    - اگر دسته غیرفعال باشد ثبت نمی‌شود (هیچ اعلان قبلی حذف نمی‌شود)
    - اگر source_type+source_id داده شود idempotent است (تک‌رکورد برای هر رویداد)
    - اگر destination شامل bot باشد، پیام کوتاه به ادمین‌های بله هم می‌رود (بی‌صدا در نبود توکن)
    - فاز P1: اگر target_role='none' باشد فقط در جدول با وضعیت archived ذخیره می‌شود
      (نه در هیچ لیستی نمایش داده می‌شود و نه به بله ارسال می‌شود)
    - destination (اختیاری): override مقصد ارسال فقط برای همین رخداد
      (مثلاً 'site' تا پیام بله ارسال نشود ولی رکورد در مرکز اعلان بماند)
    """
    try:
        ensure_notifications_table()
        if category not in DEFAULT_CATEGORY_SETTINGS:
            category = "system"
        st = category_settings().get(category, {})
        if not st.get("enabled", 1):
            return
        if source_type and source_id is not None:
            if _exists(source_type, source_id, recipient_id):
                return
        role = target_role or st.get("target_role", "both")
        if role not in VALID_TARGETS:
            role = "both"
        # target=none: فقط ثبت با وضعیت archived — بدون نمایش و بدون ارسال
        status = "archived" if role == "none" else "unread"
        with get_giso_db_conn() as conn:
            cur = conn.execute(
                "INSERT INTO %s (category, subcategory, title, message, target_role,"
                " source_type, source_id, recipient_id, status, created_at)"
                " VALUES (?,?,?,?,?,?,?,?,?,?)" % TABLE,
                (category, (subcategory or ""), (title or "")[:120], (message or "")[:400],
                 role, (source_type or ""), int(source_id or 0), str(recipient_id or ""), status, _now()))
            notification_id = cur.lastrowid or 0
            conn.commit()
        _dest = destination if destination else st.get("destination")
        if _dest in ("bot", "both"):
            # فاز P1: پیام بله استایل‌دار با آیکن دسته + deep link به بخش مربوطه در پنل
            _npkg._send_bot_destination(
                _styled_bot_message(category, title, message, source_type, source_id, subcategory),
                role, notification_id=notification_id)
    except Exception as e:
        logger.error(f"log_notification failed: {e}", exc_info=True)
        try:
            from giso.security import audit_event
            audit_event("notification_log_failed", "failed", target=category, details=str(e))
        except Exception as audit_exc:
            logger.error("notification failure audit failed: %s", audit_exc)

def safe_log(*args, **kwargs):
    """hook حداقلی: خطا را نمی‌شکند، اما حتماً لاگ و audit می‌کند."""
    try:
        log_notification(*args, **kwargs)
    except Exception as exc:
        logger.error("safe notification hook failed: %s", exc, exc_info=True)
        try:
            from giso.security import audit_event
            audit_event("notification_hook_failed", "failed", details=str(exc))
        except Exception as audit_exc:
            logger.error("notification hook audit failed: %s", audit_exc)

def log_user_notification(phone, subcategory, title, message, source_type="", source_id=None,
                          category="shop"):
    """ثبت اعلان اختصاصی کاربر در همان جدول مشترک سایت/ربات.

    source_type+source_id برای idempotency است؛ برای تغییر وضعیت‌ها بهتر است
    source_type شامل خود وضعیت باشد تا هر تغییر یک اعلان بسازد.
    """
    phone = str(phone or "").strip()
    if not phone:
        return False
    if category not in DEFAULT_CATEGORY_SETTINGS:
        category = "shop"
    try:
        ensure_notifications_table()
        if source_type and source_id is not None and _exists(source_type, source_id, phone):
            return False
        with get_giso_db_conn() as conn:
            conn.execute(
                "INSERT INTO %s (category, subcategory, title, message, target_role, source_type, source_id, recipient_id, status, created_at) "
                "VALUES (?,?,?,?,?,?,?,?,?,?)" % TABLE,
                (category, subcategory or "user", title or "اعلان گیسو", message or "", "user",
                 source_type or "user_event", int(source_id or 0), phone, "unread", _now())
            )
            conn.commit()
        return True
    except Exception as exc:
        logger.exception("user notification failed: %s", exc)
        return False

def purge_old_user_notifications(hours=USER_NOTIFICATION_RETENTION_HOURS):
    """حذف تاریخچه اعلان کاربر قدیمی‌تر از N ساعت."""
    try:
        cutoff = (datetime.now() - timedelta(hours=max(1, int(hours or 4)))).strftime("%Y-%m-%d %H:%M:%S")
        ensure_notifications_table()
        with get_giso_db_conn() as conn:
            conn.execute(
                "DELETE FROM %s WHERE target_role='user' AND created_at < ?" % TABLE, (cutoff,))
            conn.commit()
    except Exception as exc:
        logger.debug("purge_old_user_notifications: %s", exc)

def list_user_notifications(phone, limit=20):
    try:
        ensure_notifications_table()
        purge_old_user_notifications(USER_NOTIFICATION_RETENTION_HOURS)
        with get_giso_db_conn() as conn:
            rows = conn.execute(
                "SELECT * FROM %s WHERE target_role='user' AND recipient_id=? ORDER BY id DESC LIMIT ?" % TABLE,
                (str(phone or ""), int(limit))).fetchall()
            out = []
            for r in rows:
                item = dict(r)
                item["title"] = _strip_html(item.get("title"))
                item["message"] = _strip_html(item.get("message"))
                out.append(item)
            return out
    except Exception as exc:
        logger.exception("list user notifications failed: %s", exc)
        return []

def user_unread_count(phone):
    try:
        with get_giso_db_conn() as conn:
            row = conn.execute(
                "SELECT COUNT(*) AS c FROM %s WHERE target_role='user' AND recipient_id=? AND status='unread'" % TABLE,
                (str(phone or ""),)).fetchone()
            return int(row["c"] or 0) if row else 0
    except Exception:
        return 0

def mark_user_notifications_read(phone, notification_id=None):
    try:
        with get_giso_db_conn() as conn:
            if notification_id:
                conn.execute("UPDATE %s SET status='read' WHERE id=? AND target_role='user' AND recipient_id=?" % TABLE,
                             (int(notification_id), str(phone or "")))
            else:
                conn.execute("UPDATE %s SET status='read' WHERE target_role='user' AND recipient_id=? AND status='unread'" % TABLE,
                             (str(phone or ""),))
            conn.commit()
        return True
    except Exception as exc:
        logger.exception("mark user notifications failed: %s", exc)
        return False

def visible_categories(role: str) -> list:
    """دسته‌های قابل مشاهده برای نقش: super همه؛ admin فقط دسته‌های مجاز+فعال.

    فاز P1: دسته‌های با target_role='none' برای هیچ نقشی نمایش داده نمی‌شوند.

    رفع R2: قبلاً اینجا فقط `target_role == "admin"` بررسی می‌شد، در حالی که
    سایر نقاط (مثل archive_all در route) دسته‌های `both` را هم متعلق به ادمین
    می‌دانستند. همین ناهماهنگی باعث می‌شد ادمین دسته‌های `both` را نبیند ولی
    بتواند تغییرشان دهد. اکنون همین تابع هم از سیاست متمرکز پیروی می‌کند.
    """
    st = category_settings()
    if role == "super":
        return list(st.keys())
    allowed = get_allowed_notification_roles_for_user(role)
    return [c for c, v in st.items()
            if v.get("enabled") and v.get("target_role") in allowed]

def get_allowed_notification_roles_for_user(role: str) -> tuple:
    """target_roleهایی که این نقش اجازه دیدن/تغییرشان را دارد."""
    if role == "super":
        # سوپرادمین همه‌چیز به‌جز اعلان‌های اختصاصی کاربر سایت
        return ("super", "admin", "both")
    # ادمین معمولی: فقط اعلان‌هایی که صراحتاً برای ادمین یا هر دو نقش‌اند
    return ("admin", "both")

def _role_scope_sql(role: str, alias: str = "") -> tuple:
    """(قطعه SQL, پارامترها) برای محدودسازی نقش — منبع واحد حقیقت."""
    prefix = f"{alias}." if alias else ""
    roles = get_allowed_notification_roles_for_user(role)
    placeholders = ",".join("?" * len(roles))
    return f"{prefix}target_role IN ({placeholders})", list(roles)

def can_modify_notification(role: str, notification_row) -> bool:
    """آیا این نقش اجازه تغییر وضعیت این اعلان مشخص را دارد؟ (object-level)."""
    if not notification_row:
        return False
    try:
        target = str(notification_row["target_role"] or "").strip().lower()
        category = str(notification_row["category"] or "").strip()
    except (KeyError, TypeError, IndexError):
        return False
    if target not in get_allowed_notification_roles_for_user(role):
        return False
    # دستهٔ اعلان هم باید برای این نقش قابل مشاهده باشد
    return category in visible_categories(role)

def auto_archive(days=None):
    """آرشیو خودکار اعلان‌های قدیمی (پیش‌فرض ۷ روز)."""
    try:
        days = days or get_archive_days()
        cutoff = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d %H:%M:%S")
        with get_giso_db_conn() as conn:
            conn.execute(
                "UPDATE %s SET status='archived' WHERE status IN ('unread','read')"
                " AND created_at < ?" % TABLE, (cutoff,))
            conn.commit()
    except Exception as e:
        logger.debug(f"auto_archive: {e}")

def list_notifications(role="super", category=None, status=None, limit=200) -> list:
    """لیست اعلان‌ها (ادمین → فقط دسته‌های مجاز؛ سوپر → همه)."""
    ensure_notifications_table()
    auto_archive()
    out = []
    try:
        cats = visible_categories(role)
        if not cats:
            return out
        role_filter, role_params = _role_scope_sql(role)
        sql = "SELECT * FROM %s WHERE category IN (%s) AND %s" % (
            TABLE, ",".join("?" * len(cats)), role_filter)
        params = list(cats) + role_params
        if category and category in cats:
            sql += " AND category=?"
            params.append(category)
        if status and status in ("unread", "read", "archived"):
            sql += " AND status=?"
            params.append(status)
        sql += " ORDER BY id DESC LIMIT ?"
        params.append(int(limit))
        with get_giso_db_conn() as conn:
            for row in conn.execute(sql, params).fetchall():
                d = dict(row)
                d["icon"] = CATEGORY_ICONS.get(d.get("category"), "🔔")
                d["cat_fa"] = CATEGORY_FA.get(d.get("category"), "")
                d["url"] = notification_url(d.get("category"), d.get("source_type"), d.get("source_id"))
                try:
                    delivery = conn.execute(
                        "SELECT status, COUNT(*) AS c FROM giso_notification_deliveries "
                        "WHERE notification_id=? GROUP BY status", (int(d.get("id") or 0),)
                    ).fetchall()
                    d["delivery_status"] = ", ".join(f"{r['status']}:{r['c']}" for r in delivery) or "not_sent"
                except Exception:
                    d["delivery_status"] = "unknown"
                out.append(d)
    except Exception as e:
        logger.debug(f"list_notifications: {e}")
    return out

def unread_count(role="super") -> int:
    """تعداد خوانده‌نشده برای نقش (badge سایدبار)."""
    ensure_notifications_table()
    try:
        cats = visible_categories(role)
        if not cats:
            return 0
        with get_giso_db_conn() as conn:
            role_filter, role_params = _role_scope_sql(role)
            row = conn.execute(
                "SELECT COUNT(*) AS c FROM %s WHERE status='unread' AND category IN (%s) AND %s"
                % (TABLE, ",".join("?" * len(cats)), role_filter),
                list(cats) + role_params).fetchone()
            return int(row["c"] or 0) if row else 0
    except Exception:
        return 0

def set_status(nid: int, status: str, role: str = "super") -> bool:
    """خوانده‌شد / آرشیو — با گارد authorization در سطح رکورد (رفع R1).

    قبلاً این تابع فقط `UPDATE ... WHERE id=?` بود؛ یعنی هر ادمین احرازهویت‌شده
    می‌توانست اعلان مخصوص سوپرادمین را (که در UI نمی‌بیند) آرشیو یا خوانده کند.
    اکنون رکورد ابتدا خوانده و با سیاست نقش سنجیده می‌شود، و شرط نقش در خودِ
    UPDATE هم تکرار می‌شود تا در برابر race condition امن بماند.

    خروجی False یعنی «اجازه نداشت یا رکورد نبود» — فراخوان باید آن را خطا بداند.
    """
    if status not in ("read", "archived"):
        return False
    try:
        ensure_notifications_table()
        with get_giso_db_conn() as conn:
            row = conn.execute(
                "SELECT id, category, target_role FROM %s WHERE id=?" % TABLE,
                (int(nid),)).fetchone()
            if not row:
                return False
            if not can_modify_notification(role, row):
                logger.warning(
                    "notification mutation denied: role=%s nid=%s target=%s",
                    role, nid, row["target_role"])
                return False
            role_filter, role_params = _role_scope_sql(role)
            cur = conn.execute(
                "UPDATE %s SET status=? WHERE id=? AND %s" % (TABLE, role_filter),
                [status, int(nid)] + role_params)
            conn.commit()
            return (cur.rowcount or 0) > 0
    except Exception as exc:
        logger.error("set_status failed: %s", exc)
        return False

def mark_all_read(role="super") -> int:
    """همه خوانده‌نشده‌های این نقش → خوانده شد (با فیلتر نقش — رفع R2)."""
    ensure_notifications_table()
    n = 0
    try:
        cats = visible_categories(role)
        if not cats:
            return 0
        role_filter, role_params = _role_scope_sql(role)
        with get_giso_db_conn() as conn:
            cur = conn.execute(
                "UPDATE %s SET status='read' WHERE status='unread' AND category IN (%s) AND %s"
                % (TABLE, ",".join("?" * len(cats)), role_filter),
                list(cats) + role_params)
            conn.commit()
            n = cur.rowcount or 0
    except Exception as exc:
        logger.debug("mark_all_read: %s", exc)
    return n

def delete_all(role="super") -> int:
    """حذف کامل اعلان‌های قابل‌مشاهدهٔ این نقش (نه آرشیو)."""
    ensure_notifications_table()
    try:
        cats = visible_categories(role)
        if not cats:
            return 0
        role_filter, role_params = _role_scope_sql(role)
        with get_giso_db_conn() as conn:
            cur = conn.execute(
                "DELETE FROM %s WHERE category IN (%s) AND %s"
                % (TABLE, ",".join("?" * len(cats)), role_filter),
                list(cats) + role_params)
            conn.commit()
            return cur.rowcount or 0
    except Exception as exc:
        logger.error("delete_all failed: %s", exc)
        return 0

def archive_all(role="super") -> int:
    """آرشیو گروهی — با همان سیاست نقشِ لیست/شمارش (رفع R2).

    قبلاً این منطق داخل route با فیلتر متفاوتی نوشته شده بود.
    """
    ensure_notifications_table()
    try:
        cats = visible_categories(role)
        if not cats:
            return 0
        role_filter, role_params = _role_scope_sql(role)
        with get_giso_db_conn() as conn:
            cur = conn.execute(
                "UPDATE %s SET status='archived' WHERE status != 'archived' "
                "AND category IN (%s) AND %s"
                % (TABLE, ",".join("?" * len(cats)), role_filter),
                list(cats) + role_params)
            conn.commit()
            return cur.rowcount or 0
    except Exception as exc:
        logger.error("archive_all failed: %s", exc)
        return 0

def test_send() -> tuple:
    """تست ارسال (فقط سوپر — در route گارد می‌شود): ثبت رکورد + ارسال واقعی به بله.

    - target=super/both → پیام به بله سوپر/همه طبق مقصد دسته می‌رود
    - target=admin → فقط ادمین‌های معمولی
    - target=none → فقط ثبت (archived) بدون ارسال
    - در نبود توکن بله: فقط در لیست ثبت می‌شود (پیام صریح)
    """
    try:
        title = "تست سامانه اعلان‌ها ✅"
        msg = "این یک اعلان آزمایشی از پنل مدیریت گیسو است."
        log_notification("system", "test", title, msg,
                         target_role="both", source_type="", source_id=None)
        try:
            from giso.base import _token_from_env, _token_from_db
            token = _token_from_env() or _token_from_db() or ""
        except Exception:
            token = ""
        if not token:
            return True, "اعلان تستی ثبت شد؛ توکن بله تنظیم نشده — ارسال واقعی انجام نشد (فقط در لیست)."
        # system در پیش‌فرض → super + destination=both → ارسال به سوپر انجام شده
        return True, "اعلان تستی ثبت و از طریق بله به مقصدهای تنظیم‌شده ارسال شد (لاگ sendMessage را ببینید)."
    except Exception as e:
        logger.warning(f"test_send: {e}")
        return False, "خطا در تست ارسال."

def sync_channel_events():
    """پست‌های جدید کانال و محصولات تأییدشده کانال → اعلان (idempotent با source_id).

    از SQL خام استفاده می‌شود تا بدون نیاز به app context (هر context ربات/پنل) کار کند
    و channel_importer دست نخورد (فقط خواندن جدول products).
    """
    try:
        ensure_notifications_table()
        with get_giso_db_conn() as conn:
            rows = conn.execute(
                "SELECT id, name, publish_status FROM products WHERE source='channel'"
                " ORDER BY id DESC LIMIT 300").fetchall()
            for r in rows:
                if (r["publish_status"] or "pending") == "pending":
                    safe_log("channel", "post", "پست جدید کانال",
                             f"«{r['name']}» در انتظار تأیید است.",
                             source_type="channel_post", source_id=r["id"])
                else:
                    safe_log("channel", "product_approved", "تأیید محصول کانال",
                             f"«{r['name']}» منتشر شد.",
                             source_type="channel_published", source_id=r["id"])
    except Exception as e:
        logger.debug(f"sync_channel_events: {e}")

def sync_hair_events():
    """وضعیت سفارش‌های فروش مو (درخواست/تأیید/رد/تکمیل) → اعلان (idempotent)."""
    try:
        ensure_notifications_table()
        with get_giso_db_conn() as conn:
            rows = conn.execute(
                "SELECT id, phone, status FROM hair_orders ORDER BY id DESC LIMIT 300").fetchall()
            for r in rows:
                st = (r["status"] or "").lower()
                sub, title = {
                    "pending": ("request", "درخواست فروش مو"),
                    "approved": ("approved", "تأیید فروش مو"),
                    "rejected": ("rejected", "رد فروش مو"),
                    "completed": ("completed", "تکمیل فروش مو"),
                }.get(st, (None, None))
                if not sub:
                    continue
                safe_log("hair_sale", sub, title,
                         f"سفارش #{r['id']} ({r['phone'] or '—'})",
                         source_type=f"hair_{st}", source_id=r["id"])
    except Exception as e:
        logger.debug(f"sync_hair_events: {e}")

def sync_analysis_events():
    """آنالیزهای جدید / درخواست مشاوره / درخواست محصول → اعلان (idempotent)."""
    try:
        ensure_notifications_table()
        with get_giso_db_conn() as conn:
            rows = conn.execute(
                "SELECT id, phone FROM analyses ORDER BY id DESC LIMIT 300").fetchall()
            for r in rows:
                safe_log("analysis", "new", "آنالیز جدید",
                         f"کاربر {r['phone'] or '—'} آنالیز ثبت کرد.",
                         source_type="analysis_new", source_id=r["id"])
            rows = conn.execute(
                "SELECT id, phone FROM consultant_requests ORDER BY id DESC LIMIT 200").fetchall()
            for r in rows:
                safe_log("analysis", "consultant", "درخواست مشاوره",
                         f"کاربر {r['phone'] or '—'} درخواست مشاوره دارد.",
                         source_type="consultant_new", source_id=r["id"])
            rows = conn.execute(
                "SELECT id, phone FROM product_requests ORDER BY id DESC LIMIT 200").fetchall()
            for r in rows:
                safe_log("analysis", "product_request", "درخواست محصول",
                         f"کاربر {r['phone'] or '—'} درخواست محصول دارد.",
                         source_type="product_req_new", source_id=r["id"])
    except Exception as e:
        logger.debug(f"sync_analysis_events: {e}")

def run_sync_all():
    """اجرای همه همگام‌سازها — هنگام باز شدن صفحه اعلان‌ها."""
    sync_channel_events()
    sync_hair_events()
    sync_analysis_events()

def context(role="super", category=None, status=None):
    """داده صفحه «مدیریت اعلان‌ها / اعلان‌های من»."""
    # رویدادها در محل وقوع ثبت می‌شوند؛ باز کردن صفحه نباید sync یا اعلان جدید بسازد.
    return {
        "notifications": list_notifications(role, category=category, status=status),
        "all_categories": category_settings(),
        "visible_categories": visible_categories(role),
        "category_icons": CATEGORY_ICONS,
        "archive_days": get_archive_days(),
        "sound_on": get_sound_on(),
        "filter_category": category or "",
        "filter_status": status or "",
        "unread_total": unread_count(role),
        "default_rows": DEFAULT_ROWS,
    }

def _strip_html(text) -> str:
    """حذف تگ‌های markup بله از متن اعلان سایت (پیام بله جدا نگه داشته می‌شود)."""
    import re as _re
    return _re.sub(r"</?(?:b|strong|i|em|u|code|br|p|div|span)[^>]*>", " ", str(text or "")).strip()

def delete_read_user_notifications(phone) -> int:
    """حذف فقط اعلان‌های خوانده‌شدهٔ کاربر؛ ناخوانده‌ها دست‌نخورده می‌مانند."""
    try:
        ensure_notifications_table()
        with get_giso_db_conn() as conn:
            cur = conn.execute(
                "DELETE FROM %s WHERE target_role='user' AND recipient_id=? AND status='read'" % TABLE,
                (str(phone or ""),))
            conn.commit()
            return int(cur.rowcount or 0)
    except Exception as exc:
        logger.exception("delete read user notifications failed: %s", exc)
        return 0
