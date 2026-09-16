# Phase P0 bot_db sync verification — ensure table sync with giso.db
# -*- coding: utf-8 -*-
"""
giso_admin.py — توابع مدیریت ربات گیسو از پنل ادمین ربات اصلی

منطق ادمین بودن در گیسو:
  1) هر ادمین اصلی ربات (config.ADMIN_IDS) خودبه‌خود ادمین گیسو است.
  2) یا اینکه رکورد giso_admins دارای phone نرمال‌شده و bale_id معتبر باشد
     و هر دو فیلد با کاربر مطابقت کند (هر دو فیلد الزامی).

جدول giso_admin_requests:
  - درخواست‌های ادمین‌شدن کاربران که از درون ربات گیسو با عبارت مشخص‌شده ارسال می‌شود.
  - وضعیت‌ها: pending / approved / rejected

جدول giso_config:
  - کلید admin_request_phrase: عبارت درخواست ادمین (قابل تنظیم از پنل)
  - کلید bot_token / bot_username / ...

مالک business:
  - جدول‌های giso_* در bot_edu/data/bot.db هستند.
  - داده‌های کسب‌وکاری گیسو (سفارش مو، محصولات و...) در giso/data/giso.db باقی می‌مانند.
"""
import os
import re
import sqlite3
import logging
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

# ادمین‌های اصلی را به‌صورت lazy از config می‌خوانیم تا از circular import جلوگیری شود
_ADMIN_IDS_CACHE = None


def _get_main_admin_ids():
    global _ADMIN_IDS_CACHE
    if _ADMIN_IDS_CACHE is None:
        try:
            from config import ADMIN_IDS
            _ADMIN_IDS_CACHE = [int(x) for x in ADMIN_IDS]
        except Exception:
            _ADMIN_IDS_CACHE = []
    return _ADMIN_IDS_CACHE


def _connect():
    """اتصال به دیتابیس اصلی ربات (bot.db).

    ⏱ busy_timeout=۱۵ ثانیه + WAL: bot.db بین سه پروسه مشترک است (ربات edu،
    ربات گیسو، پنل وب گیسو). بدون این پارامترها، نوشتن هم‌زمان خطای
    «database is locked» می‌دهد و چون get_giso_config خطا را قورت می‌دهد و
    مقدار پیش‌فرض برمی‌گرداند، تنظیم‌ها به‌صورت خاموش «ریست/قطع» به نظر
    می‌رسیدند. (هم‌راستا با giso/db_core._set_db_performance)
    """
    db_path = os.path.join(os.path.dirname(__file__), 'data', 'bot.db')
    conn = sqlite3.connect(db_path, timeout=15)
    conn.row_factory = sqlite3.Row
    try:
        conn.execute("PRAGMA busy_timeout = 15000")
        conn.execute("PRAGMA journal_mode = WAL")
    except Exception:
        pass
    return conn


# ── کلیدهای مشترک سایت در giso.db (منبع اصلی) ──────────────────────
# طبق GISO_GUIDE: کلیدهای محلی گیسو (site_base_url و …) مالکیت giso.db هستند؛
# نسخهٔ bot.db فقط برای سازگاریِ پنل edu نگه داشته می‌شود. این دو helper هر دو
# سمت را با یک منبع هم‌قیمت نگه می‌دارند تا «ذخیره شد ولی اعمال نشد» رخ ندهد.
GISO_DB_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    'giso', 'data', 'giso.db',
)


def _connect_giso_db():
    """اتصال به giso.db برای کلیدهای مشترک سایت — با busy_timeout/WAL."""
    conn = sqlite3.connect(GISO_DB_PATH, timeout=15)
    conn.row_factory = sqlite3.Row
    try:
        conn.execute("PRAGMA busy_timeout = 15000")
        conn.execute("PRAGMA journal_mode = WAL")
    except Exception:
        pass
    return conn


def _giso_db_config_table_ready(conn) -> bool:
    """اگر جدول giso_config در giso.db هست True (بدون قفل‌گرفتن اضافه)."""
    try:
        return conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='giso_config'"
        ).fetchone() is not None
    except Exception:
        return False


def _init_giso_db_config_table(conn):
    """ساخت جدول giso_config در giso.db فقط وقتی وجود ندارد (بدون نوشتن اضافه)."""
    if _giso_db_config_table_ready(conn):
        return
    conn.execute("""
        CREATE TABLE IF NOT EXISTS giso_config (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            key TEXT UNIQUE NOT NULL,
            value TEXT DEFAULT '',
            updated_at TEXT DEFAULT ''
        )
    """)
    conn.commit()


def get_giso_site_config(key: str, default: str = '') -> str:
    """خواندن کلید سایت از giso_config در giso.db (منبع اصلی)."""
    conn = _connect_giso_db()
    try:
        _init_giso_db_config_table(conn)
        row = conn.execute(
            "SELECT value FROM giso_config WHERE key=?", (key,)
        ).fetchone()
        val = str(row['value']) if (row and row['value'] is not None) else ''
        return val if val != '' else default
    except Exception as e:
        logger.warning(f"get_giso_site_config({key}): {e}")
        return default
    finally:
        conn.close()


def set_giso_site_config(key: str, value: str) -> bool:
    """نوشتن کلید سایت در giso_config در giso.db (منبع اصلی)."""
    conn = _connect_giso_db()
    try:
        _init_giso_db_config_table(conn)
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        conn.execute(
            "INSERT INTO giso_config (key, value, updated_at) VALUES (?, ?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value, "
            "updated_at=excluded.updated_at",
            (key, value, now),
        )
        conn.commit()
        return True
    except Exception as e:
        logger.warning(f"set_giso_site_config({key}): {e}")
        return False
    finally:
        conn.close()


# ===================== جدول‌ها =====================

def init_giso_tables(conn=None):
    """ساخت/به‌روزرسانی جدول‌های giso_config، giso_admins و giso_admin_requests."""
    close = False
    if conn is None:
        conn = _connect()
        close = True
    try:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS giso_config (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                key TEXT UNIQUE NOT NULL,
                value TEXT DEFAULT '',
                updated_at TEXT DEFAULT ''
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS giso_admins (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                phone TEXT DEFAULT '',
                bale_id TEXT DEFAULT '',
                added_by INTEGER DEFAULT 0,
                added_at TEXT DEFAULT ''
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS giso_admin_requests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                phone TEXT DEFAULT '',
                bale_id TEXT DEFAULT '',
                status TEXT DEFAULT 'pending',
                requested_at TEXT DEFAULT '',
                reviewed_by INTEGER DEFAULT 0,
                reviewed_at TEXT DEFAULT '',
                note TEXT DEFAULT ''
            )
        """)
        # ایندکس‌ها
        conn.execute("CREATE INDEX IF NOT EXISTS idx_giso_admin_req_phone "
                     "ON giso_admin_requests(phone)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_giso_admin_req_bale "
                     "ON giso_admin_requests(bale_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_giso_admin_req_status "
                     "ON giso_admin_requests(status)")

        # مهاجرت: telegram_id → bale_id
        try:
            cols = [r[1] for r in conn.execute("PRAGMA table_info(giso_admins)").fetchall()]
            if "telegram_id" in cols and "bale_id" not in cols:
                conn.execute("ALTER TABLE giso_admins RENAME COLUMN telegram_id TO bale_id")
        except Exception as e:
            logger.debug(f"migrate giso_admins columns: {e}")

        # اصلاح (2026-08-22): حذف تکراری‌های تاریخی + ایندکس یکتا (idempotent).
        # بدون UNIQUE، «INSERT OR IGNORE» هیچ ردیف تکراری را نادیده نمی‌گرفت.
        # تکراری‌ها قبل از ساخت ایندکس پاک می‌شوند (قدیمی‌ترین id هر جفت
        # (phone, bale_id) نگه می‌ماند) تا CREATE UNIQUE INDEX شکست نخورد.
        try:
            conn.execute(
                "DELETE FROM giso_admins WHERE id NOT IN "
                "(SELECT MIN(id) FROM giso_admins GROUP BY phone, bale_id)"
            )
            conn.execute(
                "CREATE UNIQUE INDEX IF NOT EXISTS ux_giso_admins_phone_bale "
                "ON giso_admins(phone, bale_id)"
            )
        except Exception as e:
            logger.debug(f"migrate giso_admins unique index: {e}")

        # مقدار پیش‌فرض عبارت درخواست ادمین
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        conn.execute("""
            INSERT INTO giso_config (key, value, updated_at)
            VALUES ('admin_request_phrase', 'درخواست ادمین گیسو', ?) ON CONFLICT DO NOTHING""", (now,))
        conn.commit()
        logger.debug("جدول‌های giso_config / giso_admins / giso_admin_requests آماده شدند")
        # P10.4 — Safe idempotent sync: insert admin records from giso.db to bot.db only if missing
        # اصلاح P0 امنیتی (2026-08-22): فقط ادمین‌های تأییدشده (is_admin=1) همگام می‌شوند.
        # شرط قبلی (OR bale_id IS NOT NULL) هر کاربر ربات را خودکار در giso_admins
        # درج و به ادمین تبدیل می‌کرد (bypass جریان «درخواست → تأیید سوپرادمین»).
        try:
            import sqlite3, os
            giso_db_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "giso", "data", "giso.db")
            if os.path.exists(giso_db_path):
                g_conn = sqlite3.connect(giso_db_path)
                b_conn = sqlite3.connect(str(os.path.join(os.path.dirname(__file__), "data", "bot.db")))
                # فقط ادمین‌های تأییدشده؛ درج تکراری با ON CONFLICT نادیده گرفته می‌شود
                admins = g_conn.execute("SELECT phone, bale_id FROM giso_users WHERE is_admin = 1").fetchall()
                for phone, bale_id in admins:
                    b_conn.execute("INSERT INTO giso_admins (phone, bale_id, added_by, added_at) VALUES (?, ?, 1, datetime('now')) ON CONFLICT DO NOTHING", (str(phone or ''), str(bale_id or '')))
                b_conn.commit()
                g_conn.close(); b_conn.close()
        except Exception as sync_err:
            logger.warning(f"bot_db sync (P10.4) skipped due to error: {sync_err}")
    finally:
        if close:
            conn.close()


# ====================== نرمال‌سازی ======================

_DIGIT_MAP = str.maketrans(
    "۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩",
    "01234567890123456789",
)


def normalize_phone(raw):
    """نرمال‌سازی شماره موبایل ایران → +989xxxxxxxxx یا ''."""
    try:
        from phoneutil import normalize_phone as _np
        return _np(raw)
    except Exception:
        pass
    if not raw:
        return ""
    s = str(raw).strip().translate(_DIGIT_MAP)
    s = re.sub(r"[\s\-()]", "", s)
    if not s:
        return ""
    if s.startswith("0098"):
        s = "+98" + s[4:]
    if s.startswith("+98"):
        rest = s[3:]
    elif s.startswith("98") and len(s) == 12:
        rest = s[2:]
    elif s.startswith("0"):
        rest = s[1:]
    else:
        rest = s
    if len(rest) == 10 and rest.isdigit() and rest.startswith("9"):
        return "+98" + rest
    return ""


def normalize_bale_id(raw):
    """نرمال‌سازی شناسه عددی بله → str(int) یا ''."""
    if raw is None:
        return ""
    s = str(raw).strip()
    if s.lstrip("-").isdigit():
        return str(int(s))
    return ""


def _phone_display(norm_phone: str) -> str:
    s = normalize_phone(norm_phone)
    if not s:
        return norm_phone or ""
    return "0" + s[3:]


# ====================== Config ======================

def get_giso_config(key: str, default: str = '') -> str:
    conn = _connect()
    try:
        init_giso_tables(conn)
        row = conn.execute("SELECT value FROM giso_config WHERE key=?", (key,)).fetchone()
        return row['value'] if row else default
    except Exception as e:
        logger.warning(f"get_giso_config({key}): {e}")
        return default
    finally:
        conn.close()


def set_giso_config(key: str, value: str):
    conn = _connect()
    try:
        init_giso_tables(conn)
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        conn.execute("""
            INSERT INTO giso_config (key, value, updated_at)
            VALUES (?, ?, ?)
            ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_at=excluded.updated_at
        """, (key, value, now))
        conn.commit()
    finally:
        conn.close()


# ====================== Lookup در هویت مشترک ======================

def find_known_bale_id_by_phone(norm_phone: str) -> str:
    """سعی در پیدا کردن شناسه بله از روی شماره در پلتفرم‌لینک‌ها (platform_links).

    چون canonical user_id ربات همان شناسهٔ بله است، از روی platform_links
    (platform='bale') یا users.user_id وقتی phone مطابقت دارد برمی‌گردانیم.
    """
    np = normalize_phone(norm_phone)
    if not np:
        return ""
    conn = _connect()
    try:
        # اول با phone در users → user_id (canonical == bale_id)
        row = conn.execute(
            "SELECT user_id FROM users WHERE phone=?", (np,)
        ).fetchone()
        if row and row["user_id"]:
            return str(int(row["user_id"]))
        # پلتفرم‌لینک برای بله
        row = conn.execute(
            """SELECT pl.platform_user_id FROM platform_links pl
               JOIN users u ON u.user_id = pl.user_id
               WHERE pl.platform='bale' AND u.phone=?""",
            (np,),
        ).fetchone()
        if row and row["platform_user_id"]:
            return str(row["platform_user_id"])
        return ""
    except Exception as e:
        logger.debug("find_known_bale_id_by_phone: %s", e)
        return ""
    finally:
        conn.close()


def find_giso_admin_by_phone(norm_phone: str) -> dict | None:
    np = normalize_phone(norm_phone)
    if not np:
        return None
    conn = _connect()
    try:
        init_giso_tables(conn)
        row = conn.execute(
            "SELECT * FROM giso_admins WHERE phone=?", (np,)
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


# ====================== ادمین‌ها ======================

class AdminAddCheck:
    """نتیجهٔ بررسی قبل از افزودن ادمین."""
    ALREADY_MAIN_ADMIN = "already_main_admin"
    ALREADY_GISO_ADMIN = "already_giso_admin"
    CONFLICT_BALE_ID = "conflict_bale_id"
    CAN_SUGGEST_KNOWN_ID = "can_suggest_known_id"
    NEED_BOTH = "need_both"
    OK = "ok"


def check_admin_candidate(phone: str, bale_id: str = "") -> dict:
    """بررسی وضعیت کاندیدای ادمین گیسو (پیش از ذخیره).

    خروجی دیکشنری با کلیدها:
      status, message, known_bale_id, existing_record
    """
    np = normalize_phone(phone)
    nb = normalize_bale_id(bale_id)
    if not np:
        return {"status": "invalid_phone", "message": "شماره نامعتبر",
                "known_bale_id": "", "existing_record": None}

    # آیا در ADMIN_IDS است؟
    if nb:
        try:
            if int(nb) in _get_main_admin_ids():
                return {
                    "status": AdminAddCheck.ALREADY_MAIN_ADMIN,
                    "message": "⚠️ این شناسه در فهرست ادمین‌های اصلی ربات قرار دارد و به‌صورت پیش‌فرض ادمین گیسو می‌باشد؛ نیازی به ثبت دستی نیست.",
                    "known_bale_id": nb, "existing_record": None,
                }
        except Exception:
            pass

    # آیا قبلاً با همین (phone, bale_id) ثبت شده؟
    existing = find_giso_admin(phone=np, bale_id=nb) if nb else find_giso_admin_by_phone(np)
    if existing:
        if nb and str(existing.get("bale_id")) == nb:
            return {
                "status": AdminAddCheck.ALREADY_GISO_ADMIN,
                "message": f"این کاربر قبلاً به‌عنوان ادمین گیسو ثبت شده است (شماره {_phone_display(np)}).",
                "known_bale_id": str(existing.get("bale_id") or ""),
                "existing_record": existing,
            }
        # phone هست ولی bale_id فرق داره
        if nb and str(existing.get("bale_id")) and str(existing.get("bale_id")) != nb:
            return {
                "status": AdminAddCheck.CONFLICT_BALE_ID,
                "message": (f"⚠️ تعارض: این شماره قبلاً با شناسه بله "
                            f"{existing.get('bale_id')} ثبت شده، نه {nb}. "
                            f"لطفاً بررسی کنید."),
                "known_bale_id": str(existing.get("bale_id") or ""),
                "existing_record": existing,
            }

    # آیا شماره در سیستم مشترک شناخته شده و bale_id دارد؟
    known_id = find_known_bale_id_by_phone(np)
    if known_id:
        if nb and known_id != nb:
            return {
                "status": AdminAddCheck.CONFLICT_BALE_ID,
                "message": (f"⚠️ تعارض: این شماره در سیستم با شناسه {known_id} "
                            f"شناخته می‌شود، نه {nb}. لطفاً بررسی کنید."),
                "known_bale_id": known_id, "existing_record": existing,
            }
        return {
            "status": AdminAddCheck.CAN_SUGGEST_KNOWN_ID,
            "message": (f"ℹ️ این شماره در سیستم با شناسه بله {known_id} شناخته "
                        f"می‌شود. می‌توانید همین شناسه را تأیید کنید."),
            "known_bale_id": known_id, "existing_record": existing,
        }

    if not nb:
        return {
            "status": AdminAddCheck.NEED_BOTH,
            "message": ("شناسه بله از روی مخاطب در دسترس نیست. از کاربر بخواهید "
                        "ربات را /start کند و «ارسال شماره تماس» را بزند، یا دستور /myid "
                        "را در چت خصوصی بله با ربات بفرستد تا شناسه‌اش ثبت شود."),
            "known_bale_id": "", "existing_record": existing,
        }

    return {
        "status": AdminAddCheck.OK,
        "message": "",
        "known_bale_id": nb, "existing_record": existing,
    }


def add_giso_admin(phone: str = '', bale_id: str = '', added_by: int = 0):
    """افزودن ادمین جدید گیسو. هر دو فیلد باید معتبر باشند."""
    norm_phone = normalize_phone(phone)
    norm_bale = normalize_bale_id(bale_id)
    if not norm_phone or not norm_bale:
        raise ValueError("phone_and_bale_id_required")
    # جلوگیری از ثبت ادمین اصلی
    try:
        if int(norm_bale) in _get_main_admin_ids():
            return False
    except Exception:
        pass
    # تکراری exact؟
    if find_giso_admin(phone=norm_phone, bale_id=norm_bale):
        return False
    # تعارض؟ (فقط همان phone با bale_id متفاوت)
    same_phone = find_giso_admin_by_phone(norm_phone)
    if same_phone and str(same_phone.get("bale_id")) != norm_bale:
        raise ValueError("bale_id_conflict")
    conn = _connect()
    try:
        init_giso_tables(conn)
        # اگر phone هست و bale_id خالی بود، آن را به‌روز کن
        if same_phone and not str(same_phone.get("bale_id") or ""):
            now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            conn.execute(
                "UPDATE giso_admins SET bale_id=?, added_by=?, added_at=? WHERE id=?",
                (norm_bale, int(added_by or 0), now, same_phone["id"]),
            )
        else:
            now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            conn.execute("""
                INSERT INTO giso_admins (phone, bale_id, added_by, added_at)
                VALUES (?, ?, ?, ?)
            """, (norm_phone, norm_bale, int(added_by or 0), now))
        conn.commit()
        return True
    finally:
        conn.close()


def list_giso_admins() -> list:
    """لیست ادمین‌های تاییدشده (بدون سوپرادمین اصلی)."""
    conn = _connect()
    try:
        init_giso_tables(conn)
        rows = conn.execute("SELECT * FROM giso_admins ORDER BY id DESC").fetchall()
        main_ids = _get_main_admin_ids()
        out = []
        for r in rows:
            d = dict(r)
            d.setdefault('bale_id', d.get('telegram_id', ''))
            # حذف سوپرادمین اصلی از لیست
            try:
                bid = int(d.get('bale_id', 0) or 0)
                if bid in main_ids:
                    continue
            except (ValueError, TypeError):
                pass
            phone = str(d.get('phone', '') or '')
            if phone in ('09156012931', '+989156012931'):
                continue
            out.append(d)
        return out
    finally:
        conn.close()


def delete_giso_admin(admin_id: int):
    conn = _connect()
    try:
        conn.execute("DELETE FROM giso_admins WHERE id=?", (admin_id,))
        conn.commit()
    finally:
        conn.close()


def find_giso_admin(phone: str = '', bale_id: str = '') -> dict | None:
    """پیدا کردن یک ادمین ثبت‌شده با phone و/یا bale_id نرمال.

    اگر هر دو داده شود فقط جفت exact را برمی‌گرداند.
    """
    np = normalize_phone(phone)
    nb = normalize_bale_id(bale_id)
    conn = _connect()
    try:
        init_giso_tables(conn)
        if np and nb:
            row = conn.execute(
                "SELECT * FROM giso_admins WHERE phone=? AND bale_id=?",
                (np, nb),
            ).fetchone()
        elif np:
            row = conn.execute(
                "SELECT * FROM giso_admins WHERE phone=?", (np,)
            ).fetchone()
        elif nb:
            row = conn.execute(
                "SELECT * FROM giso_admins WHERE bale_id=?", (nb,)
            ).fetchone()
        else:
            return None
        if not row:
            return None
        d = dict(row)
        d.setdefault('bale_id', d.get('telegram_id', ''))
        return d
    finally:
        conn.close()


def is_giso_admin(user_id=None, phone: str = '') -> bool:
    """تشخیص ادمین گیسو (برای runtime ربات و سایت)."""
    if user_id is not None:
        try:
            if int(user_id) in _get_main_admin_ids():
                return True
        except Exception:
            pass
    np = normalize_phone(phone)
    nb = normalize_bale_id(user_id) if user_id is not None else ""
    if np and nb:
        return find_giso_admin(phone=np, bale_id=nb) is not None
    return False


# ====================== درخواست‌های ادمین ======================

def get_admin_request_phrase() -> str:
    return get_giso_config('admin_request_phrase', 'درخواست ادمین گیسو')


def set_admin_request_phrase(phrase: str):
    phrase = (phrase or '').strip()
    if not phrase:
        phrase = 'درخواست ادمین گیسو'
    set_giso_config('admin_request_phrase', phrase)


def create_admin_request(phone: str, bale_id: str) -> dict:
    """ایجاد درخواست ادمین توسط کاربر (از ربات گیسو).

    - اگر درخواست باز (pending) همین کاربر قبلاً هست، همان را برمی‌گرداند.
    - اگر قبلاً ادمین است، برمی‌گرداند {already_admin: True}.
    """
    np = normalize_phone(phone)
    nb = normalize_bale_id(bale_id)
    if not np or not nb:
        return {"ok": False, "reason": "invalid"}
    if is_giso_admin(user_id=nb, phone=np):
        return {"ok": False, "reason": "already_admin"}
    conn = _connect()
    try:
        init_giso_tables(conn)
        # درخواست باز قبلی؟
        existing = conn.execute(
            """SELECT * FROM giso_admin_requests
               WHERE phone=? AND bale_id=? AND status='pending'
               ORDER BY id DESC LIMIT 1""",
            (np, nb),
        ).fetchone()
        if existing:
            return {"ok": True, "already_pending": True, "id": existing["id"],
                    "requested_at": existing["requested_at"]}
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        cur = conn.execute(
            """INSERT INTO giso_admin_requests
               (phone, bale_id, status, requested_at)
               VALUES (?, ?, 'pending', ?)""",
            (np, nb, now),
        )
        conn.commit()
        return {"ok": True, "already_pending": False, "id": cur.lastrowid,
                "requested_at": now}
    finally:
        conn.close()


def has_pending_admin_request(phone: str, bale_id: str) -> bool:
    np = normalize_phone(phone)
    nb = normalize_bale_id(bale_id)
    if not np or not nb:
        return False
    conn = _connect()
    try:
        init_giso_tables(conn)
        row = conn.execute(
            """SELECT id FROM giso_admin_requests
               WHERE phone=? AND bale_id=? AND status='pending'
               LIMIT 1""",
            (np, nb),
        ).fetchone()
        return row is not None
    finally:
        conn.close()


def list_admin_requests(status: str = "pending") -> list:
    conn = _connect()
    try:
        init_giso_tables(conn)
        if status and status != "all":
            rows = conn.execute(
                "SELECT * FROM giso_admin_requests WHERE status=? ORDER BY id DESC",
                (status,),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM giso_admin_requests ORDER BY id DESC"
            ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def review_admin_request(req_id: int, approve: bool, reviewer_id: int = 0, note: str = ""):
    """تأیید یا رد درخواست ادمین. در حالت approve کاربر به giso_admins اضافه می‌شود."""
    conn = _connect()
    try:
        init_giso_tables(conn)
        row = conn.execute(
            "SELECT * FROM giso_admin_requests WHERE id=?", (int(req_id),)
        ).fetchone()
        if not row:
            raise ValueError("request_not_found")
        if row["status"] != "pending":
            raise ValueError("already_reviewed")
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        new_status = "approved" if approve else "rejected"
        conn.execute(
            """UPDATE giso_admin_requests
               SET status=?, reviewed_by=?, reviewed_at=?, note=?
               WHERE id=?""",
            (new_status, int(reviewer_id or 0), now, note or "", int(req_id)),
        )
        if approve:
            # اضافه‌کردن به ادمین‌ها (اگر نبود)
            existing = conn.execute(
                "SELECT id FROM giso_admins WHERE phone=? AND bale_id=?",
                (row["phone"], str(row["bale_id"])),
            ).fetchone()
            if not existing:
                try:
                    is_main = int(row["bale_id"]) in _get_main_admin_ids()
                except Exception:
                    is_main = False
                if not is_main:
                    conn.execute("""
                        INSERT INTO giso_admins (phone, bale_id, added_by, added_at)
                        VALUES (?, ?, ?, ?)
                    """, (row["phone"], str(row["bale_id"]), int(reviewer_id or 0), now))
        conn.commit()
        return {"ok": True, "status": new_status, "phone": row["phone"], "bale_id": str(row["bale_id"])}
    finally:
        conn.close()


# ====================== PID / وضعیت اجرا ======================

def _giso_pid_file() -> str:
    return str(Path(__file__).resolve().parent.parent / 'giso' / 'data' / 'giso-bot.pid')


def is_giso_bot_running() -> tuple:
    """بررسی زنده‌بودن پردازش گیسوبات. خروجی (running, pid, note)."""
    import os as _os
    pid_file = _giso_pid_file()
    if not _os.path.exists(pid_file):
        return False, None, 'PID file not found'
    try:
        with open(pid_file, 'r') as f:
            pid = int(f.read().strip())
    except Exception:
        return False, None, 'PID file corrupt'
    try:
        if _os.name == 'nt':
            out = _os.popen(f'tasklist /FI "PID eq {pid}"').read()
            running = str(pid) in out
        else:
            _os.kill(pid, 0)
            running = True
        if running:
            return True, pid, 'running'
        return False, pid, 'PID not alive'
    except ProcessLookupError:
        return False, pid, 'PID not alive'
    except PermissionError:
        return True, pid, 'running'
    except Exception as e:
        return False, pid, str(e)


def get_giso_stats() -> dict:
    conn = _connect()
    try:
        init_giso_tables(conn)
        stats = {}
        admins_row = conn.execute("SELECT COUNT(*) FROM giso_admins").fetchone()
        stats['admins'] = admins_row[0] if admins_row else 0
        pending_row = conn.execute(
            "SELECT COUNT(*) FROM giso_admin_requests WHERE status='pending'"
        ).fetchone()
        stats['pending_requests'] = pending_row[0] if pending_row else 0
        token = get_giso_config('bot_token', '')
        stats['token_set'] = bool(token)
        stats['token_masked'] = (token[:8] + '...' + token[-4:]
                                if len(token) > 12 else (token[:3] + '***' if token else '—'))
        stats['bot_username'] = get_giso_config('bot_username', '—')
        stats['admin_request_phrase'] = get_admin_request_phrase()

        running, pid, note = is_giso_bot_running()
        stats['running'] = running
        stats['pid'] = pid
        stats['note'] = note
        if stats['token_set'] and running:
            stats['status_label'] = '✅ فعال'
        elif stats['token_set'] and not running:
            stats['status_label'] = '⚠️ توکن ثبت شده ولی ربات اجرا نشده'
        else:
            stats['status_label'] = '❌ غیرفعال (توکن ثبت نشده)'
        return stats
    finally:
        conn.close()


if __name__ == '__main__':
    init_giso_tables()
    print("جدول‌های گیسو آماده شدند.")
    print("توکن فعلی:", get_giso_config('bot_token') or '(ثبت نشده)')
    print("ادمین‌ها:", list_giso_admins())
    print("درخواست‌های باز:", list_admin_requests('pending'))
# Phase 10.3 Super Admin Bot
# Phase 3 Loop Prevention: sync only called once per status-change event; never inside load/loop
