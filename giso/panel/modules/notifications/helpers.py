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



def notification_url(cat: str, source_type: str = "", source_id=None) -> str:
    """لینک عمیق اعلان: از دسته + مرجع (source_type/source_id) به صفحه‌ی درست پنل."""
    try:
        from flask import url_for
        st = (source_type or "").strip()
        sid = int(source_id or 0)
        # مراجع خاص → لینک دقیق‌تر
        if st in ("bug_report",) or (cat == "security" and "bug" in st):
            return url_for("panel.monitoring", tab="errors") + "#bug-reports"
        if st in ("consultant_reply", "consultant_request") and sid:
            return url_for("panel.consults", cons=sid)
        if st.startswith("channel") and sid:
            return url_for("panel.shop") + "#pane-pending"
        if st in ("hair_order", "hair_request") and sid:
            return url_for("panel.hair_sale")
        if st in ("shop_order", "order") and sid:
            return url_for("panel.shop_orders")
        if cat == "marketplace":
            if "review" in st:
                return url_for("panel.marketplace", tab="reviews")
            if "buyer" in st and "offer" not in st:
                return url_for("panel.marketplace", tab="buyers")
            return url_for("panel.marketplace", tab="listings")
        ep = CATEGORY_ROUTES.get(cat, "panel.notifications")
        return url_for(ep)
    except Exception:
        return ""

def _normalize_target_role(value):
    """Preserve the explicit super/admin/both routing contract."""
    value = (value or "").strip().lower()
    return value if value in VALID_TARGETS else "none"

def ensure_notifications_table():
    """ساخت جدول giso_notifications + ایندکس‌ها — idempotent، جداول قبلی دست نمی‌خورد."""
    try:
        with get_giso_db_conn() as conn:
            conn.execute(
                "CREATE TABLE IF NOT EXISTS %s ("
                " id INTEGER PRIMARY KEY AUTOINCREMENT,"
                " category TEXT NOT NULL DEFAULT 'system',"
                " subcategory TEXT NOT NULL DEFAULT '',"
                " title TEXT NOT NULL DEFAULT '',"
                " message TEXT NOT NULL DEFAULT '',"
                " target_role TEXT NOT NULL DEFAULT 'both',"
                " source_type TEXT NOT NULL DEFAULT '',"
                " source_id INTEGER DEFAULT 0,"
                " recipient_id TEXT NOT NULL DEFAULT '',"
                " status TEXT NOT NULL DEFAULT 'unread',"
                " created_at TEXT NOT NULL DEFAULT '')" % TABLE)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_notif_status ON %s(status)" % TABLE)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_notif_cat ON %s(category)" % TABLE)
            cols = {r[1] for r in conn.execute("PRAGMA table_info(%s)" % TABLE).fetchall()}
            if "recipient_id" not in cols:
                conn.execute("ALTER TABLE %s ADD COLUMN recipient_id TEXT NOT NULL DEFAULT ''" % TABLE)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_notif_recipient ON %s(recipient_id)" % TABLE)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_notif_created ON %s(created_at)" % TABLE)
            # جدول delivery برای گزارش واقعی ارسال بله
            conn.execute("""
                CREATE TABLE IF NOT EXISTS giso_notification_deliveries (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    notification_id INTEGER DEFAULT 0, destination TEXT DEFAULT 'bale',
                    recipient_id TEXT DEFAULT '', status TEXT DEFAULT 'queued',
                    http_status INTEGER DEFAULT 0, error_code TEXT DEFAULT '',
                    error_message TEXT DEFAULT '', sent_at TEXT DEFAULT ''
                )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_delivery_notif ON giso_notification_deliveries(notification_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_delivery_status ON giso_notification_deliveries(status)")
            conn.commit()
    except Exception as e:
        logger.debug(f"ensure_notifications_table: {e}")

def category_settings() -> dict:
    """تنظیمات همه دسته‌ها: پیش‌فرض + ذخیره‌شده در giso_config (JSON)."""
    out = {c: dict(v) for c, v in DEFAULT_CATEGORY_SETTINGS.items()}
    try:
        from giso_admin import get_giso_config
        raw = get_giso_config(CONFIG_KEY, "")
        if raw:
            data = json.loads(raw)
            for cat, vals in data.items():
                if cat in out and isinstance(vals, dict):
                    out[cat]["target_role"] = _normalize_target_role(vals.get("target_role"))
                    if vals.get("enabled") in (0, 1, "0", "1"):
                        out[cat]["enabled"] = int(vals["enabled"])
                    if vals.get("destination") in VALID_DESTINATIONS:
                        out[cat]["destination"] = vals["destination"]
    except Exception as e:
        logger.debug(f"category_settings: {e}")
    return out

def save_category_settings(updates: dict) -> tuple:
    """ذخیره تنظیمات دسته‌ها (فقط سوپرادمین — در route گارد می‌شود)."""
    try:
        cur = category_settings()
        for cat, vals in (updates or {}).items():
            if cat not in cur or not isinstance(vals, dict):
                continue
            cur[cat]["target_role"] = _normalize_target_role(vals.get("target_role"))
            if vals.get("enabled") in (0, 1, "0", "1"):
                cur[cat]["enabled"] = int(vals["enabled"])
            if vals.get("destination") in VALID_DESTINATIONS:
                cur[cat]["destination"] = vals["destination"]
        from giso_admin import set_giso_config
        set_giso_config(CONFIG_KEY, json.dumps(cur, ensure_ascii=False))
        return True, "تنظیمات اعلان‌ها ذخیره شد."
    except Exception as e:
        logger.warning(f"save_category_settings: {e}")
        return False, "خطا در ذخیره تنظیمات."

def get_archive_days() -> int:
    try:
        from giso_admin import get_giso_config
        raw = get_giso_config(CONFIG_ARCHIVE_DAYS, str(DEFAULT_ARCHIVE_DAYS))
        return max(1, min(60, int(raw or DEFAULT_ARCHIVE_DAYS)))
    except Exception:
        return DEFAULT_ARCHIVE_DAYS

def set_archive_days(days: int) -> bool:
    try:
        from giso_admin import set_giso_config
        set_giso_config(CONFIG_ARCHIVE_DAYS, str(max(1, min(60, int(days)))))
        return True
    except Exception:
        return False

def get_sound_on() -> bool:
    try:
        from giso_admin import get_giso_config
        return get_giso_config(CONFIG_SOUND, "1") not in ("0", "", "false", "False")
    except Exception:
        return True

def set_sound_on(flag: bool) -> bool:
    try:
        from giso_admin import set_giso_config
        set_giso_config(CONFIG_SOUND, "1" if flag else "0")
        return True
    except Exception:
        return False

def _now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def _exists(source_type: str, source_id, recipient_id="") -> bool:
    try:
        with get_giso_db_conn() as conn:
            row = conn.execute(
                "SELECT id FROM %s WHERE source_type=? AND source_id=? AND recipient_id=? LIMIT 1" % TABLE,
                (source_type, int(source_id or 0), str(recipient_id or ""))).fetchone()
            return row is not None
    except Exception:
        return False

def _regular_admin_ids() -> set:
    """فقط ادمین‌های معمولی (بدون سوپرادمین) — برای ارسال بله با target=admin.

    هر رکورد giso_admins که با هویت متمرکز سوپر (is_super_admin بر اساس بله یا موبایل)
    مطابقت داشته باشد حذف می‌شود — مستقل از env.
    """
    ids = set()
    try:
        from giso_admin import list_giso_admins
        from giso.config import is_super_admin
        for a in list_giso_admins():
            bid = str(a.get("bale_id") or a.get("telegram_id") or "").strip()
            if not bid.isdigit():
                continue
            try:
                if is_super_admin(uid=int(bid)):
                    continue
            except (TypeError, ValueError):
                pass
            phone = (a.get("phone") or "").strip()
            if phone and is_super_admin(phone=phone):
                continue
            ids.add(int(bid))
    except Exception as e:
        logger.debug(f"_regular_admin_ids: {e}")
    return ids

def _super_admin_ids() -> set:
    """سوپرادمین‌ها — همیشه بر اساس هویت متمرکز giso/config.py (بدون وابستگی به env).

    منبع اصلی: SUPERADMIN_BALE_ID در giso/config.py (بله: 1191639507، موبایل: 09156012931).
    ADMIN_IDS از bot_edu/config.py فقط به‌عنوان مکمل (با تأیید is_super_admin) اضافه می‌شود
    تا اگر env مقدار را override کرده باشد، هویت واقعی سوپر از دست نرود.
    """
    ids = set()
    try:
        from giso.config import SUPERADMIN_BALE_ID
        ids.add(int(SUPERADMIN_BALE_ID))
    except Exception:
        pass
    try:
        from giso.base import _load_main_admin_ids
        from giso.config import is_super_admin
        for x in _load_main_admin_ids():
            try:
                if is_super_admin(uid=x):
                    ids.add(int(str(x).strip()))
            except (TypeError, ValueError):
                pass
    except Exception:
        pass
    return ids

def _send_bot_destination(message: str, target_role: str, notification_id: int = 0) -> str:
    """ارسال کوتاه به ادمین‌های بله — غیرمسدودکننده.

    ارسال واقعی (با retry و backoff) به thread pool سپرده می‌شود تا پاسخ Flask
    فوراً برگردد و event loop ربات قفل نشود.

    فاز P1: تفکیک سوپر/ادمین در مقصد ارسال:
      - target=super  → فقط سوپرادمین‌های اصلی
      - target=admin  → فقط ادمین‌های معمولی (سوپر نمی‌گیرد)
      - target=both   → هر دو
      - target=none   → هیچ‌کس (این تابع برای none صدا زده نمی‌شود)
    """
    try:
        _NOTIFY_POOL.submit(_send_bot_destination_worker, message, target_role, notification_id)
    except Exception as exc:
        logger.debug(f"_send_bot_destination submit: {exc}")
        try:
            _send_bot_destination_worker(message, target_role, notification_id)
        except Exception:
            pass
    return "queued"

def _send_bot_destination_worker(message: str, target_role: str, notification_id: int = 0) -> str:
    try:
        from giso.base import _token_from_env, _token_from_db, _http_post
        from giso.security import record_delivery
        token = _token_from_env() or _token_from_db() or ""
        if not token:
            for cid in (_super_admin_ids() | _regular_admin_ids()):
                record_delivery(notification_id, cid, "failed", error_code="missing_token", error_message="Bale bot token is not configured")
            return "no_token"
        # مدل Super-first: سوپرادمین همیشه دریافت‌کننده اعلان سیستمی است.
        # سوپرادمین همیشه دریافت‌کننده است؛ none فقط ادمین معمولی را حذف می‌کند.
        targets = _super_admin_ids()
        if target_role in ("admin", "both"):
            targets |= _regular_admin_ids()
        if not targets:
            return "no_targets"
        url = f"https://tapi.bale.ai/bot{token}/sendMessage"
        sent_ok = 0
        backoff = (0.5, 1.0, 2.0)
        for cid in targets:
            final_ok = False
            last_code = 0
            last_error = ""
            for attempt in range(1, 4):
                try:
                    resp = _http_post(url, json_payload={"chat_id": int(cid), "text": message,
                                                         "parse_mode": "HTML"})
                    code = getattr(resp, "status_code", None) if resp is not None else None
                    last_code = code or 0
                    final_ok = bool(resp is not None and code in (200, 201, 202, 204))
                    if final_ok:
                        break
                    last_error = "Bale returned HTTP %s" % code
                    logger.warning("notif sendMessage to %s attempt %s/3: %s", cid, attempt, last_error)
                except Exception as e_one:
                    last_error = str(e_one)
                    logger.warning("notif sendMessage to %s attempt %s/3: %s", cid, attempt, e_one)
                if attempt < 3:
                    time.sleep(backoff[attempt - 1])
            if final_ok:
                sent_ok += 1
                record_delivery(notification_id, cid, "sent", http_status=last_code)
            else:
                record_delivery(notification_id, cid, "failed", http_status=last_code,
                                error_code="network_error" if last_code == 0 else "http_error",
                                error_message=last_error[:300])
            logger.info("notif sendMessage to %s: %s after up to 3 attempts", cid, "OK" if final_ok else "FAIL")
        if sent_ok:
            logger.info(f"notif sendMessage: {sent_ok}/{len(targets)} delivered")
        return "sent" if sent_ok else "failed"
    except Exception as e:
        logger.debug(f"_send_bot_destination_worker: {e}")
        return "failed"

def _site_base_url() -> str:
    """آدرس پایهٔ پنل برای لینک اعلان‌ها.

    مورد ۱۸ help.md: اگر مقدار ذخیره‌شده یک آدرس لوکال/غیرعمومی باشد
    (مثلاً از اجرای محلی روی سرور مانده باشد) هرگز به اعلان بله نرود —
    کاربر روی گوشی نمی‌تواند 127.0.0.1 را باز کند؛ fallback به آدرس رسمی.
    """
    try:
        with get_giso_db_conn() as conn:
            row = conn.execute(
                "SELECT value FROM giso_config WHERE key='site_base_url'").fetchone()
        if row and row[0]:
            val = str(row[0]).strip().rstrip("/")
            from urllib.parse import urlparse
            host = (urlparse(val).hostname or "").lower()
            if host and not any(x in host for x in ("127.", "localhost", "0.0.0.0", "::1", "10.", "192.168.")):
                return val
    except Exception:
        pass
    return "https://gisosadeghi.ir"

def _styled_bot_message(category: str, title: str, message: str,
                        source_type: str = "", source_id=None,
                        subcategory: str = "") -> str:
    """پیام بله استایل‌دار: آیکن دسته + عنوان + متن + لینک مستقیم به بخش پنل."""
    st = _CATEGORY_STYLE.get(category, {"emoji": "🔔", "link": "/admin/dashboard"})
    cat_title = DEFAULT_CATEGORY_SETTINGS.get(category, {}).get("title", category)
    # گزارش باگ: اعلان مستقیم به بخش پایش ← خطاها ← گزارش‌های باگ کاربران
    if str(source_type or "").strip() == "bug_report" or "bug_report" in str(subcategory or ""):
        base_link = "/admin/monitoring?tab=errors#bug-reports"
    else:
        base_link = st["link"]
    link = _site_base_url() + base_link
    ref = ""
    if source_type:
        # مورد ۱۸ help2: خط «موضوع» هرگز حذف نشود؛ برچسب ناشناخته = «اعلان سیستم»
        fa = _SOURCE_LABELS.get(str(source_type).strip()) or "اعلان سیستم"
        ref = f"\n🔖 موضوع: {fa}"
    msg = (message or "").strip()
    if len(msg) > 420:
        msg = msg[:420] + "…"
    parts = [
        f"{st['emoji']} {title or cat_title}",
        "━━━━━━━━━━━━━━━━",
    ]
    if cat_title:
        parts.append(f"🏷 بخش: {cat_title}")
    if msg:
        parts.append(f"📝 {msg}")
    if ref:
        parts.append(ref.lstrip("\n"))
    parts.append("━━━━━━━━━━━━━━━━")
    parts.append(f"🔗 مشاهده در پنل:\n{link}")
    out = "\n".join(parts)
    return out[:900]

VALID_TARGETS = ("super", "admin", "both", "none")
VALID_DESTINATIONS = ("site", "bot", "both", "none")

_CATEGORY_STYLE = {
    "shop":      {"emoji": "🛍", "link": "/admin/shop-orders"},
    "beauty_centers": {"emoji": "🏥", "link": "/admin/beauty-centers"},
    "hair_sale": {"emoji": "💇", "link": "/admin/hair-orders"},
    "analysis":  {"emoji": "🔬", "link": "/admin/analyses"},
    "users":     {"emoji": "👥", "link": "/admin/users"},
    "wallet":    {"emoji": "💳", "link": "/admin/wallet"},
    "channel":   {"emoji": "📢", "link": "/admin/channel"},
    "bot":       {"emoji": "🤖", "link": "/admin/settings"},
    "security":  {"emoji": "🛡", "link": "/admin/dashboard"},
    "system":    {"emoji": "⚙️", "link": "/admin/reports"},
}

_SOURCE_LABELS = {
    "super_login": "ورود سوپرادمین به پنل",
    "admin_step_up": "ورود دومرحله‌ای ادمین",
    "user_register": "ثبت‌نام کاربر جدید",
    "user_ban": "بن‌شدن کاربر",
    "user_unban": "رفع بن کاربر",
    "bug_report": "گزارش باگ کاربر",
    "consultant_request": "درخواست مشاورهٔ جدید",
    "consultant_reply": "پاسخ جدید مشاور",
    "hair_order": "درخواست فروش مو",
    "shop_order": "سفارش جدید فروشگاه",
    "order": "سفارش جدید",
    "password_reset": "تغییر رمز کاربر توسط سوپرادمین",
    "analysis": "آنالیز جدید",
    "backup": "بکاپ/ریستور",
}
