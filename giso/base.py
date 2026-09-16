# -*- coding: utf-8 -*-
"""
giso/base.py — لایه پایه و مشترک تمام ماژول‌های گیسو (دیتابیس، احراز هویت، نرمال‌سازی، اعلان‌ها).
"""
import asyncio
import logging
import os
import re
import sqlite3
import sys
import threading
import time
from pathlib import Path

logger = logging.getLogger("giso_base")

BASE_DIR = Path(__file__).resolve().parent

# فقط append مجاز است تا اولویت با ماژول‌های محلی giso باشد
sys.path.append(str(BASE_DIR.parent / "bot_edu"))

from giso.db_core import (BASE_DIR, BOT_DB_PATH, GISO_DB_PATH, _set_db_performance,
                          checkpoint_giso_db, get_bot_db_conn, get_giso_db_conn,
                          get_site_url, get_user_site_data, send_bot_push)
from giso.phones import (_DIGIT_MAP, normalize_phone, _phone_variants,
                          _fa_num, display_phone, gregorian_to_jalali, to_shamsi)

_CONFIG_CACHE = {}
_CONFIG_CACHE_LOCK = threading.Lock()


def cached_giso_config(key: str, default: str = "", ttl_seconds: int = 60):
    """خواندن تنظیم giso_config از bot.db با کش TTL (کاهش باز شدن bot.db در هر request)."""
    now = time.monotonic()
    with _CONFIG_CACHE_LOCK:
        item = _CONFIG_CACHE.get(key)
        if item and (now - item[1]) < ttl_seconds:
            return item[0]
    value = default
    try:
        from giso_admin import get_giso_config
        value = get_giso_config(key, default)
    except Exception:
        value = default
    if value is None:
        value = default
    with _CONFIG_CACHE_LOCK:
        _CONFIG_CACHE[key] = (value, now)
    return value


def invalidate_giso_config_cache(key: str = None):
    """پاک‌کردن کش تنظیمات (در صورت None کل کش پاک می‌شود)."""
    with _CONFIG_CACHE_LOCK:
        if key is None:
            _CONFIG_CACHE.clear()
        else:
            _CONFIG_CACHE.pop(key, None)


def read_giso_config_checked(key: str, default: str = "") -> tuple[str, bool]:
    """خواندن یک کلید giso_config از bot.db با تشخیص سلامتِ خواندن.

    خروجی (value, ok):
      - ok=True  → خواندن موفق بود (مقدار یا پیش‌فرض).
      - ok=False → bot.db خراب/قفل/در دسترس نبود؛ مقدار قابل اعتماد نیست.
    """
    try:
        conn = get_bot_db_conn()
        if conn is None:
            return default, False
        try:
            try:
                from giso_admin import init_giso_tables
                init_giso_tables(conn)
            except Exception:
                pass
            row = conn.execute(
                "SELECT value FROM giso_config WHERE key=?", (key,)
            ).fetchone()
            return (str(row[0]) if row else default), True
        finally:
            conn.close()
    except Exception as exc:
        logger.warning("read_giso_config_checked(%s) failed: %s", key, exc)
        return default, False


def read_rate_limit_config() -> dict:
    """خواندن تنظیمات محدودیت تحلیل (rate_limit_*) از bot.db.

    حالت سالم: مقادیر واقعی (یا پیش‌فرض‌های جاری: غیرفعال / ۶۰ دقیقه / هر دو).
    حالت خطا (bot.db خراب/قفل/حذف یا جدول ناقص): مقدار محافظه‌کارانهٔ fail-closed
      (فعال + هر ۵ دقیقه + هر دو) برمی‌گردد — نه بی‌محدود.
    """
    try:
        vals = {}
        ok = True
        for key, default in (
            ("rate_limit_enabled", "0"),
            ("rate_limit_minutes", "60"),
            ("rate_limit_type", "both"),
        ):
            v, k_ok = read_giso_config_checked(key, default)
            vals[key] = v
            ok = ok and k_ok
        if not ok:
            logger.warning(
                "rate_limit config unreadable → conservative default: enabled, 5 min, both"
            )
            return {"enabled": True, "minutes": 5, "limit_type": "both", "ok": False}
        enabled = str(vals["rate_limit_enabled"] or "0").strip().lower() in (
            "1", "true", "on", "yes",
        )
        try:
            minutes = max(1, int(vals["rate_limit_minutes"] or 60))
        except (TypeError, ValueError):
            minutes = 60
        limit_type = str(vals["rate_limit_type"] or "both").strip().lower()
        if limit_type not in ("ip", "phone", "both"):
            limit_type = "both"
        return {"enabled": enabled, "minutes": minutes,
                "limit_type": limit_type, "ok": True}
    except Exception as exc:
        logger.warning("read_rate_limit_config failed: %s", exc)
        return {"enabled": True, "minutes": 5, "limit_type": "both", "ok": False}


def _token_from_env() -> str:
    return (os.environ.get("GISO_BOT_TOKEN") or "").strip()


def _token_from_db() -> str:
    if not BOT_DB_PATH.exists():
        return ""
    try:
        if (conn := get_bot_db_conn()) is None:
            return ""  # bot.db موقتاً در دسترس نیست؛ توکن env/خالی مسیر امن
        row = conn.execute(
            "SELECT value FROM giso_config WHERE key='bot_token'"
        ).fetchone()
        conn.close()
        return (row[0] if row else "").strip()
    except Exception as e:
        logger.warning("Could not read token from bot.db: %s", e)
        return ""


def _admin_request_phrase() -> str:
    """عبارت درخواست ادمین با کش کوتاه؛ از Migration تکراری در هر پیام جلوگیری می‌کند."""
    value = str(cached_giso_config("admin_request_phrase", "درخواست ادمین گیسو", ttl_seconds=10) or "").strip()
    return value or "درخواست ادمین گیسو"


def _load_main_admin_ids() -> list:
    ids = []
    try:
        import config as _bot_config
        ids = [int(x) for x in getattr(_bot_config, "ADMIN_IDS", [])]
    except Exception:
        pass
    return ids


def _is_super_admin(uid, phone: str = "") -> bool:
    """بررسی سوپرادمین اصلی گیسو (1191639507 یا 09156012931)."""
    from giso.config import is_super_admin
    return is_super_admin(uid, phone)


is_super_admin = _is_super_admin


def _giso_lookup(bale_user_id, phone: str) -> dict:
    """وضعیت کاربر در سیستم ادمین گیسو."""
    out = {"is_admin": False, "is_pending": False, "reason": "", "bale_col": "bale_id"}
    if _is_super_admin(bale_user_id, phone):
        out["is_admin"] = True
        out["reason"] = "super_admin"
        return out
    norm = normalize_phone(phone)
    bid = ""
    try:
        bid = str(int(bale_user_id))
    except Exception:
        bid = str(bale_user_id or "")
    if not bid.isdigit():
        return out
    if int(bid) in _load_main_admin_ids():
        out["is_admin"] = True
        out["reason"] = "main_admin"
        return out
    if not BOT_DB_PATH.exists():
        return out
    try:
        if (conn := get_bot_db_conn()) is None:
            return out  # bot.db موقتاً در دسترس نیست؛ دسترسی بدون ارتقای ادمین
        from giso_admin import init_giso_tables, is_giso_admin, has_pending_admin_request
        init_giso_tables(conn)
        out["is_admin"] = bool(is_giso_admin(user_id=int(bid), phone=norm))
        out["is_pending"] = (not out["is_admin"]) and bool(
            has_pending_admin_request(phone=norm, bale_id=bid)
        )
        conn.close()
        # لیست سیاه: ادمینِ حذف‌شده با اشتراک مجدد شماره نباید دوباره ادمین شود
        if out["is_admin"] and is_admin_demoted(bale_id=bid, phone=norm):
            out["is_admin"] = False
            out["is_pending"] = False
            out["reason"] = "demoted"
    except Exception as e:
        logger.debug("giso_lookup: %s", e)
    return out


def _giso_init_db():
    conn = get_giso_db_conn()
    try:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS giso_users (
                bale_id   TEXT PRIMARY KEY,
                phone     TEXT NOT NULL DEFAULT '',
                first_name TEXT DEFAULT '',
                username  TEXT DEFAULT '',
                is_admin  INTEGER DEFAULT 0,
                contact_shared INTEGER DEFAULT 0,
                pending_request INTEGER DEFAULT 0,
                created_at TEXT DEFAULT '',
                last_active TEXT DEFAULT ''
            );
            CREATE TABLE IF NOT EXISTS giso_web_auth (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                phone TEXT UNIQUE NOT NULL,
                name TEXT DEFAULT '',
                region TEXT DEFAULT '',
                contact_time TEXT DEFAULT '',
                password_hash TEXT DEFAULT '',
                security_question TEXT DEFAULT '',
                security_answer TEXT DEFAULT '',
                created_at TEXT DEFAULT '',
                last_login TEXT DEFAULT ''
            );
            CREATE TABLE IF NOT EXISTS hair_orders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                phone TEXT NOT NULL DEFAULT '',
                customer_name TEXT DEFAULT '',
                photo_path TEXT DEFAULT '',
                length_cm INTEGER DEFAULT 50,
                hair_type TEXT DEFAULT 'raw',
                hair_color TEXT DEFAULT 'خام طبیعی',
                color_history TEXT DEFAULT '',
                hair_weight TEXT DEFAULT 'متوسط',
                hair_health TEXT DEFAULT 'خیلی سالم و طبیعی',
                region TEXT DEFAULT '',
                contact_time TEXT DEFAULT '',
                description TEXT DEFAULT '',
                estimated_price TEXT DEFAULT '',
                final_price TEXT DEFAULT '',
                admin_note TEXT DEFAULT '',
                status TEXT DEFAULT 'pending',
                created_at TEXT DEFAULT '',
                updated_at TEXT DEFAULT ''
            );
            CREATE TABLE IF NOT EXISTS analyses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                phone TEXT NOT NULL DEFAULT '',
                type TEXT DEFAULT 'hair',
                photo_path TEXT DEFAULT '',
                ai_report_json TEXT DEFAULT '{}',
                admin_note TEXT DEFAULT '',
                created_at TEXT DEFAULT ''
            );
            CREATE TABLE IF NOT EXISTS reviews (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                phone TEXT NOT NULL DEFAULT '',
                review_type TEXT DEFAULT 'shop_order',
                order_id INTEGER DEFAULT 0,
                rating INTEGER DEFAULT 5,
                comment TEXT DEFAULT '',
                created_at TEXT DEFAULT ''
            );
            CREATE TABLE IF NOT EXISTS products (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                price INTEGER DEFAULT 0,
                category TEXT DEFAULT 'hair',
                description TEXT DEFAULT '',
                in_stock INTEGER DEFAULT 1,
                image_path TEXT DEFAULT ''
            );
            CREATE TABLE IF NOT EXISTS product_orders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                phone TEXT NOT NULL DEFAULT '',
                customer_name TEXT DEFAULT '',
                product_id INTEGER,
                address TEXT DEFAULT '',
                status TEXT DEFAULT 'pending',
                created_at TEXT DEFAULT ''
            );
            CREATE TABLE IF NOT EXISTS stock_notifies (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                product_id INTEGER,
                phone TEXT NOT NULL DEFAULT ''
            );
        """)
        # مهاجرت افزایشی برای دیتابیس‌های قدیمی؛ گزارش کاربران و پروفایل ربات
        # نباید به‌علت نبود یکی از ستون‌های نسخه‌های جدید از کار بیفتد.
        user_columns = (
            ("first_name", "TEXT DEFAULT ''"), ("username", "TEXT DEFAULT ''"),
            ("is_admin", "INTEGER DEFAULT 0"), ("contact_shared", "INTEGER DEFAULT 0"),
            ("pending_request", "INTEGER DEFAULT 0"), ("created_at", "TEXT DEFAULT ''"),
            ("last_active", "TEXT DEFAULT ''"),
        )
        try:
            cols = {r[1] for r in conn.execute("PRAGMA table_info(giso_users)").fetchall()}
            for col, ddl in user_columns:
                if col not in cols:
                    conn.execute(f"ALTER TABLE giso_users ADD COLUMN {col} {ddl}")
        except Exception:
            pass
        conn.commit()
    finally:
        conn.close()
    try:
        from giso.ai_brain import init_ai_tables
        init_ai_tables()
    except Exception as e:
        logger.debug(f"init_ai_tables error in _giso_init_db: {e}")
    try:
        from giso.hair_sale import init_hair_tables
        init_hair_tables()
    except Exception as e:
        logger.debug(f"init_hair_tables error in _giso_init_db: {e}")

    # ═══ بخش جدید: sync از .env اگر دیتابیس خالی است (fallback دو لایه) ═══
    try:
        from giso.ai_brain import sync_env_providers_to_db
        sync_env_providers_to_db()
    except Exception as e:
        logger.debug(f"sync_env_providers_to_db in _giso_init_db: {e}")

    # ═══ فاز ۲ بازنویسی AI: کاشت پروایدرهای جدید رجیستری + غیرفعال‌سازی llm7 ═══
    try:
        from giso.ai_brain import seed_registry_providers
        seed_registry_providers()
    except Exception as e:
        logger.debug(f"seed_registry_providers in _giso_init_db: {e}")


def _get_giso_user(bale_id: str) -> dict | None:
    try:
        with get_giso_db_conn() as conn:
            row = conn.execute(
                "SELECT * FROM giso_users WHERE bale_id=?", (str(bale_id),)
            ).fetchone()
            return dict(row) if row else None
    except Exception:
        return None


def _upsert_giso_user(bale_id, phone: str = "", first_name: str = "",
                      username: str = "", is_admin: bool = None,
                      contact_shared: bool = None, pending_request: bool = None):
    _giso_init_db()
    now = time.strftime("%Y-%m-%d %H:%M:%S")
    existing = _get_giso_user(bale_id)
    with get_giso_db_conn() as conn:
        if existing is None:
            conn.execute(
                """INSERT INTO giso_users
                   (bale_id, phone, first_name, username, is_admin,
                    contact_shared, pending_request, created_at, last_active)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (str(bale_id), phone, first_name or "", username or "",
                 1 if is_admin else 0,
                 1 if contact_shared else 0,
                 1 if pending_request else 0,
                 now, now),
            )
        else:
            fields = []
            vals = []
            if phone:
                fields.append("phone=?"); vals.append(phone)
            if first_name:
                fields.append("first_name=?"); vals.append(first_name)
            if username is not None:
                fields.append("username=?"); vals.append(username)
            if is_admin is not None:
                fields.append("is_admin=?"); vals.append(1 if is_admin else 0)
            if contact_shared is not None:
                fields.append("contact_shared=?"); vals.append(1 if contact_shared else 0)
            if pending_request is not None:
                fields.append("pending_request=?"); vals.append(1 if pending_request else 0)
            fields.append("last_active=?"); vals.append(now)
            vals.append(str(bale_id))
            conn.execute(
                f"UPDATE giso_users SET {', '.join(fields)} WHERE bale_id=?",
                vals,
            )
        conn.commit()
    if contact_shared is True:
        try:
            from giso.wallet import complete_bale_connection_mission
            complete_bale_connection_mission(bale_id)
        except Exception:
            pass


def _demote_giso_user_admin(bale_id=None, phone: str = ""):
    _giso_init_db()
    with get_giso_db_conn() as conn:
        if bale_id and str(bale_id).strip():
            conn.execute("UPDATE giso_users SET is_admin=0, pending_request=0 WHERE bale_id=?", (str(bale_id),))
        if phone and str(phone).strip():
            conn.execute("UPDATE giso_users SET is_admin=0, pending_request=0 WHERE phone=?", (phone,))
        conn.commit()


# ═══════════════ لیست سیاه ادمین‌های تنزل‌یافته (ضد re-sync) ═══════════════
# bot_edu/giso_admin.py در init_giso_tables یک sync دارد که هر giso_users با
# `bale_id IS NOT NULL` را دوباره به giso_admins اضافه می‌کند. برای اینکه ادمینِ
# حذف‌شده با اشتراک دوباره شماره «خودبه‌خود ادمین» نشود، بله‌آیدی/شماره او را
# اینجا سیاه‌فهرست می‌کنیم و لایه role-resolution گیسو آن را در نظر می‌گیرد.

def _ensure_demoted_admins_table(conn):
    conn.execute(
        "CREATE TABLE IF NOT EXISTS giso_demoted_admins ("
        "bale_id TEXT PRIMARY KEY, phone TEXT DEFAULT '', demoted_at TEXT DEFAULT '')"
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_demoted_phone ON giso_demoted_admins(phone)")


def mark_admin_demoted(bale_id: str = "", phone: str = "") -> bool:
    """ثبت ادمین تنزل‌یافته در لیست سیاه تا sync ربات او را دوباره ادمین نکند."""
    try:
        with get_giso_db_conn() as conn:
            _ensure_demoted_admins_table(conn)
            conn.execute(
                "INSERT INTO giso_demoted_admins (bale_id, phone, demoted_at) VALUES (?,?,?) ON CONFLICT(bale_id) DO UPDATE SET phone=excluded.phone, demoted_at=excluded.demoted_at",
                (str(bale_id or "").strip(), str(phone or "").strip(),
                 time.strftime("%Y-%m-%d %H:%M:%S")),
            )
            conn.commit()
        return True
    except Exception as e:
        logger.warning("mark_admin_demoted: %s", e)
        return False


def clear_admin_demoted(bale_id: str = "", phone: str = "") -> bool:
    """حذف از لیست سیاه (در تأیید مجدد درخواست ادمینی توسط سوپرادمین)."""
    try:
        with get_giso_db_conn() as conn:
            _ensure_demoted_admins_table(conn)
            if str(bale_id or "").strip():
                conn.execute("DELETE FROM giso_demoted_admins WHERE bale_id=?", (str(bale_id).strip(),))
            if str(phone or "").strip():
                variants = [v for v in _phone_variants(phone) if v]
                if variants:
                    marks = ",".join("?" * len(variants))
                    conn.execute(f"DELETE FROM giso_demoted_admins WHERE phone IN ({marks})", variants)
            conn.commit()
        return True
    except Exception as e:
        logger.warning("clear_admin_demoted: %s", e)
        return False


def is_admin_demoted(bale_id: str = "", phone: str = "") -> bool:
    """آیا این بله‌آیدی/شماره توسط سوپرادمین تنزل یافته است؟"""
    try:
        with get_giso_db_conn() as conn:
            _ensure_demoted_admins_table(conn)
            if str(bale_id or "").strip():
                row = conn.execute(
                    "SELECT 1 FROM giso_demoted_admins WHERE bale_id=?", (str(bale_id).strip(),)
                ).fetchone()
                if row:
                    return True
            if str(phone or "").strip():
                variants = [v for v in _phone_variants(phone) if v]
                if variants:
                    marks = ",".join("?" * len(variants))
                    row = conn.execute(
                        f"SELECT 1 FROM giso_demoted_admins WHERE phone IN ({marks})", variants
                    ).fetchone()
                    if row:
                        return True
            return False
    except Exception:
        return False


# ═══ حذف کامل داده‌های کاربر (دکمه‌های «حذف کاربر» در ربات و پنل) ═══
# ترتیب مهم است: با foreign_keys=ON، ابتدا جدول‌های فرزند (FK) باید خالی شوند،
# سپس جدول‌های تجاری و در آخر ردیف‌های هویتی. ترتیب بر اساس FKهای واقعی دیتابیس:
#   marketplace_messages/reviews -> buyer_offers/hair_listings
#   buyer_offers -> buyer_profiles/hair_listings
#   shop_invoices -> shop_checkouts
_ERASE_FK_CHILD_TABLES = (
    ("marketplace_messages", "sender_user_id"),
    ("marketplace_reviews", "reviewer_user_id"),
    ("marketplace_reviews", "reviewee_user_id"),
    ("listing_reports", "reporter_user_id"),
    ("buyer_offers", "buyer_user_id"),
    ("buyer_offers", "chat_closed_by_user_id"),
    ("marketplace_listing_device_claims", "buyer_user_id"),
    ("hair_listings", "seller_user_id"),
    ("buyer_profiles", "user_id"),
    ("shop_invoices", "user_id"),
    ("shop_checkouts", "user_id"),
    ("wallet_topup_requests", "user_id"),
    ("marketplace_device_links", "user_id"),
    ("marketplace_phone_observations", "user_id"),
    ("marketplace_risk_events", "user_id"),
    ("marketplace_user_ratings", "user_id"),
    ("marketplace_saved_searches", "user_id"),
    ("wallet_mission_completions", "user_id"),
)
_ERASE_USERID_TABLES = (
    "analyses", "customer_scores", "giso_user_activity", "giso_wishlist",
    "hair_orders", "product_orders", "product_requests", "reviews",
    "wallet_transactions", "withdrawal_requests",
)
_ERASE_PHONE_TABLES = (
    "analysis_rate_limits", "giso_widget_chats", "stock_notifies",
)


def erase_user_data(phone: str, bale_id: str = "") -> dict:
    """حذف کامل داده‌های یک کاربر (سایت + ربات) در یک transaction اتمیک.

    - اول جدول‌های فرزند (FK) تا IntegrityError ایجاد نشود
    - بعد جدول‌های تجاری (user_id / phone / bale_id)
    - در آخر ردیف‌های هویتی: giso_web_auth (سایت) و giso_users (ربات)

    سوپرادمین حذف نمی‌شود؛ هر خطا کل transaction را roll back می‌کند.
    """
    result = {"ok": False, "deleted": {}, "reason": ""}
    np = normalize_phone(phone)
    bid = str(bale_id or "").strip()
    if not np and not bid:
        result["reason"] = "invalid"
        return result
    digits = re.sub(r"[^\d]", "", np or "")
    # گارد سوپرادمین (همان شناسه‌های ثابت پروژه)
    if bid == "1191639507" or (digits and digits.endswith("9156012931")):
        result["reason"] = "super_admin"
        return result
    variants = [v for v in _phone_variants(np) if v] if np else []
    try:
        with get_giso_db_conn() as conn:
            deleted = {}

            def _del(sql, params, key):
                try:
                    cur = conn.execute(sql, params)
                except Exception:
                    # جدول/ستون ممکن است در نسخه‌ی قدیمی‌تر موجود نباشد
                    return
                deleted[key] = deleted.get(key, 0) + max(cur.rowcount or 0, 0)

            # ۱) شناسه‌ی کاربر سایت (برای پاک‌کردن جدول‌های فرزند)
            uid = None
            if variants:
                marks = ",".join("?" * len(variants))
                row = conn.execute(
                    f"SELECT id FROM giso_web_auth WHERE phone IN ({marks}) LIMIT 1", variants
                ).fetchone()
                uid = row["id"] if row else None

            if uid:
                for t, col in _ERASE_FK_CHILD_TABLES:
                    _del(f"DELETE FROM {t} WHERE {col}=?", (uid,), t)
                for t in _ERASE_USERID_TABLES:
                    _del(f"DELETE FROM {t} WHERE user_id=?", (uid,), t)

            if variants:
                marks = ",".join("?" * len(variants))
                # پیام‌های زیرمجموعه (به‌صورت منطقی پیش از جدول والد)
                _del(
                    "DELETE FROM hair_messages WHERE order_id IN "
                    "(SELECT id FROM hair_orders WHERE phone IN (%s))" % marks,
                    variants, "hair_messages")
                _del(
                    "DELETE FROM consultant_messages WHERE request_id IN "
                    "(SELECT id FROM consultant_requests WHERE phone IN (%s))" % marks,
                    variants, "consultant_messages")
                for t in _ERASE_PHONE_TABLES:
                    _del(f"DELETE FROM {t} WHERE phone IN ({marks})", variants, t)
                for t in ("hair_orders", "product_orders", "reviews", "analyses"):
                    _del(f"DELETE FROM {t} WHERE phone IN ({marks})", variants, t)
                _del(f"DELETE FROM giso_support_tickets WHERE phone IN ({marks})",
                     variants, "giso_support_tickets")
                _del(f"DELETE FROM consultant_requests WHERE phone IN ({marks})",
                     variants, "consultant_requests")
                # ردیف‌های هویتی
                _del(f"DELETE FROM giso_web_auth WHERE phone IN ({marks})", variants, "giso_web_auth")
                _del(f"DELETE FROM giso_users WHERE phone IN ({marks})", variants, "giso_users")

            if bid:
                _del("DELETE FROM giso_bot_consultant_chat WHERE bale_id=?", (bid,),
                     "giso_bot_consultant_chat")
                _del("DELETE FROM giso_support_tickets WHERE user_bale_id=?", (bid,),
                     "giso_support_tickets")
                _del("DELETE FROM giso_users WHERE bale_id=?", (bid,), "giso_users")

        result.update(ok=True, deleted=deleted)
    except Exception as e:
        logger.error(f"erase_user_data failed (rolled back): {e}")
        result["reason"] = str(e)
    return result


def _http_post(url, data=None, json_payload=None, files=None):
    try:
        import requests
        if files:
            return requests.post(url, data=data, files=files, timeout=10)
        return requests.post(url, json=json_payload, timeout=5)
    except ImportError:
        import urllib.request, json as _json
        if json_payload:
            req = urllib.request.Request(
                url,
                data=_json.dumps(json_payload).encode("utf-8"),
                headers={"Content-Type": "application/json"}
            )
            try:
                urllib.request.urlopen(req, timeout=5)
            except Exception:
                pass
        return None


def get_persian_status(status: str) -> str:
    """تبدیل وضعیت انگلیسی مو به فارسی."""
    st = (status or "").lower().strip()
    mapping = {
        "pending": "در انتظار بررسی 🆕",
        "reviewing": "در حال بررسی 🔍",
        "priced": "قیمت‌گذاری شد 💰",
        "approved": "تایید شد ✅",
        "rejected": "رد شد ❌",
        "completed": "تکمیل شد 📦",
    }
    return mapping.get(st, status or "نامشخص")


def match_user_across_systems(phone_raw: str) -> dict:
    """
    بررسی و انطباق کاربر در دو جدول giso_web_auth (سایت) و giso_users (ربات).
    """
    out = {
        "phone_norm": "",
        "in_site": False,
        "in_bot": False,
        "site_user": None,
        "bot_user": None,
        "history": {
            "hair_orders_count": 0,
            "analyses_count": 0,
            "shop_orders_count": 0,
            "reviews_count": 0,
            "latest_hair_order": None
        }
    }
    norm = normalize_phone(phone_raw)
    if not norm:
        return out
    out["phone_norm"] = norm
    local_norm = "0" + norm[3:] if norm.startswith("+98") else norm

    try:
        with get_giso_db_conn() as conn:
            site_row = conn.execute(
                "SELECT * FROM giso_web_auth WHERE phone=? OR phone=? LIMIT 1",
                (norm, local_norm)
            ).fetchone()
            if site_row:
                out["in_site"] = True
                out["site_user"] = dict(site_row)

            bot_row = conn.execute(
                "SELECT * FROM giso_users WHERE phone=? OR phone=? LIMIT 1",
                (norm, local_norm)
            ).fetchone()
            if bot_row:
                out["in_bot"] = True
                out["bot_user"] = dict(bot_row)

            h_cnt = conn.execute(
                "SELECT COUNT(*) as c FROM hair_orders WHERE phone=? OR phone=?",
                (norm, local_norm)
            ).fetchone()
            out["history"]["hair_orders_count"] = int(h_cnt["c"]) if h_cnt else 0

            a_cnt = conn.execute(
                "SELECT COUNT(*) as c FROM analyses WHERE phone=? OR phone=?",
                (norm, local_norm)
            ).fetchone()
            out["history"]["analyses_count"] = int(a_cnt["c"]) if a_cnt else 0

            try:
                s_cnt = conn.execute(
                    "SELECT COUNT(*) as c FROM product_orders WHERE phone=? OR phone=?",
                    (norm, local_norm)
                ).fetchone()
                out["history"]["shop_orders_count"] = int(s_cnt["c"]) if s_cnt else 0
            except Exception:
                pass

            try:
                r_cnt = conn.execute(
                    "SELECT COUNT(*) as c FROM reviews WHERE phone=? OR phone=?",
                    (norm, local_norm)
                ).fetchone()
                out["history"]["reviews_count"] = int(r_cnt["c"]) if r_cnt else 0
            except Exception:
                pass

            latest = conn.execute(
                "SELECT id, status, final_price, estimated_price, created_at FROM hair_orders WHERE phone=? OR phone=? ORDER BY id DESC LIMIT 1",
                (norm, local_norm)
            ).fetchone()
            if latest:
                out["history"]["latest_hair_order"] = dict(latest)
    except Exception as e:
        logger.warning(f"match_user_across_systems error: {e}")
    return out


def send_hair_order_notification_to_admins(order_dict: dict, full_buttons: bool = True):
    """ارسال اعلان کامل درخواست جدید فروش مو همراه با عکس برای ادمین‌ها در بله."""
    try:
        from giso.hair_sale import send_hair_order_notification_to_admins as _sho
        _sho(order_dict, full_buttons=full_buttons)
    except Exception as e:
        logger.warning(f"send_hair_order_notification_to_admins error: {e}")


def notify_user_bot_by_order(context, order_id, text_msg="", reply_markup=None):
    """ارسال پیام به کاربر ربات در بله + آینهٔ اعلان در پنل کاربر سایت (توسط ادمین یا رویداد سفارش)."""
    try:
        with get_giso_db_conn() as conn:
            order_row = conn.execute("SELECT * FROM hair_orders WHERE id=?", (order_id,)).fetchone()
        if not (order_row and order_row["phone"]):
            return
        np = normalize_phone(order_row["phone"])
        # ─── آینهٔ پنل کاربر سایت: مستقل از اینکه کاربر در بله هست یا نه ───
        try:
            from giso.panel.modules.notifications import log_user_notification as _logu
            if (text_msg or "").lstrip().startswith("💬"):
                import hashlib as _h
                _mkey = int(_h.sha1(f"{order_id}|{text_msg}".encode("utf-8")).hexdigest()[:12], 16)
                _logu(np, "hair_message", "پیام کارشناس فروش مو",
                      text_msg, source_type=f"hair_notify:{order_id}:{_mkey}",
                      source_id=int(order_id or 0), category="hair_sale")
            else:
                _st = order_row["status"] or ""
                _st_fa = get_persian_status(_st)
                _body = f"وضعیت درخواست فروش مو #{order_id} به «{_st_fa}» تغییر کرد."
                if text_msg:
                    _body += f"\n{text_msg}"
                _logu(np, "hair_status", "به‌روزرسانی درخواست فروش مو",
                      _body, source_type=f"hair_status:{_st}",
                      source_id=int(order_id or 0), category="hair_sale")
        except Exception as _e_mirror:
            logger.debug(f"user panel hair mirror failed: {_e_mirror}")
        with get_giso_db_conn() as conn:
            user_row = conn.execute("SELECT bale_id FROM giso_users WHERE phone=?", (np,)).fetchone()
            if user_row and user_row["bale_id"] and str(user_row["bale_id"]).isdigit():
                st_fa = get_persian_status(order_row["status"])
                fp = order_row["final_price"]
                note = order_row["admin_note"]
                lines = [
                    f"🔔 بروزرسانی درخواست فروش مو #{_fa_num(order_id)}",
                    f"📌 وضعیت جدید: {st_fa}",
                ]
                if fp:
                    lines.append(f"💰 قیمت نهایی کارشناس: {fp}")
                if note:
                    lines.append(f"📝 یادداشت ادمین: {note}")
                if text_msg:
                    lines.append(f"\n{text_msg}")
                body = "\n".join(lines)
                if context and hasattr(context, "bot"):
                    if reply_markup:
                        asyncio.create_task(context.bot.send_message(
                            chat_id=int(user_row["bale_id"]), text=body,
                            reply_markup=reply_markup
                        ))
                    else:
                        asyncio.create_task(context.bot.send_message(
                            chat_id=int(user_row["bale_id"]), text=body
                        ))
                else:
                    token = _token_from_env() or _token_from_db() or ""
                    if token:
                        url = f"https://tapi.bale.ai/bot{token}/sendMessage"
                        payload = {"chat_id": int(user_row["bale_id"]), "text": body, "parse_mode": "HTML"}
                        if reply_markup:
                            import json as _json
                            try:
                                payload["reply_markup"] = _json.loads(reply_markup.to_json())
                            except Exception:
                                pass
                        _http_post(url, json_payload=payload)
    except Exception as e:
        logger.debug(f"notify_user_bot_by_order error: {e}")


__all__ = [
    "get_giso_db_conn",
    "get_bot_db_conn",
    "read_giso_config_checked",
    "read_rate_limit_config",
    "normalize_phone",
    "display_phone",
    "gregorian_to_jalali",
    "to_shamsi",
    "_phone_variants",
    "_fa_num",
    "fa_num",
    "_token_from_env",
    "_token_from_db",
    "_admin_request_phrase",
    "_load_main_admin_ids",
    "_is_super_admin",
    "is_super_admin",
    "_giso_lookup",
    "_giso_init_db",
    "_get_giso_user",
    "_upsert_giso_user",
    "_demote_giso_user_admin",
    "get_persian_status",
    "match_user_across_systems",
    "send_hair_order_notification_to_admins",
    "notify_user_bot_by_order",
    "get_site_url", "send_bot_push", "get_user_site_data",
]
# P1-Sync: unified notification sync for order/hair/analysis to Bale
