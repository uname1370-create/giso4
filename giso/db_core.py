# -*- coding: utf-8 -*-
"""
giso/db_core.py — لایهٔ اتصال به دیتابیس گیسو (Phase 2, Unit U2)
استخراج‌شده از giso/base.py بدون تغییر رفتار؛ نام‌ها در giso.base re-export می‌شوند.
فقط استاندارد lib در سطح ماژول؛ وابستگی داخلی (giso.phones/giso.base) فقط lazy
داخل توابع است تا حلقهٔ import ایجاد نشود.
"""
import json
import logging
import os
import sqlite3
import time
from pathlib import Path

logger = logging.getLogger("giso_db_core")

BASE_DIR = Path(__file__).resolve().parent
GISO_DB_PATH = BASE_DIR / "data" / "giso.db"
BOT_DB_PATH = BASE_DIR.parent / "bot_edu" / "data" / "bot.db"


class _ManagedConnection(sqlite3.Connection):
    """اتصال SQLite که در پایان بلوک ``with`` خودش بسته می‌شود.

    ``sqlite3.Connection.__exit__`` فقط commit/rollback می‌کند و فایل‌دسکریپتور
    را باز نگه می‌دارد؛ به همین دلیل ۳۶۸ نقطهٔ مصرف الگوی
    ``with get_giso_db_conn() as conn:`` در giso/ اتصالات را رها می‌کردند
    (تست اندازه‌گیری: ۳۰۰۰ بلوک → ۷ به ۱۴۱ FD).
    این wrapper همان سمنتیک تراکنش را حفظ می‌کند (commit بدون خطا / rollback
    با خطا) و در هر دو حالت اتصال را می‌بندد؛ پس نشت متوقف می‌شود بدون آن‌که
    هیچ نقطهٔ مصرفی تغییر کند. بستن دوباره (close صریح بعد از with) هم بی‌اثر است.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._giso_closed = False

    def close(self):
        try:
            super().close()
        finally:
            self._giso_closed = True

    def __exit__(self, exc_type, exc_value, traceback):
        try:
            if not self._giso_closed:
                if exc_type is None:
                    self.commit()
                else:
                    self.rollback()
        except sqlite3.Error:
            pass
        finally:
            if not self._giso_closed:
                self.close()
        return False

DEFAULT_SITE_BASE_URL = "https://gisosadeghi.ir"



def sync_site_config_to_bot_db(key: str, value: str) -> bool:
    """همگام‌سازی best-effort یک کلید giso_config با نسخهٔ bot.db.

    کلیدهای سایت (مثل site_base_url) منبع اصلی‌شان giso.db است، اما پنل ربات
    edu همان کلید را از bot.db می‌خواند؛ بدون این همگام‌سازی مقدارِ ذخیره‌شده
    در سمت گیسو در پنل edu «اعمال‌نشده» دیده می‌شد. هیچ خطایی به بالا نشت
    نمی‌کند (اگر bot.db قفل/در دسترس نبود، صرفاً False برمی‌گردد).
    """
    try:
        conn = get_bot_db_conn()
        if conn is None:
            return False
        try:
            conn.execute(
                "INSERT INTO giso_config (key, value, updated_at) VALUES (?, ?, ?) "
                "ON CONFLICT(key) DO UPDATE SET value=excluded.value, "
                "updated_at=excluded.updated_at",
                (key, value, time.strftime("%Y-%m-%d %H:%M:%S")),
            )
            conn.commit()
            return True
        finally:
            conn.close()
    except Exception as e:
        logger.warning(f"sync_site_config_to_bot_db({key}): {e}")
        return False



def _set_db_performance(conn):
    """Phase 11 — set SQLite performance guard (busy timeout + WAL).

    busy_timeout از ۵ به ۱۵ ثانیه افزایش یافت: bot.db بین ربات آموزش و گیسو
    مشترک است و در لحظه‌های نوشتن هم‌زمان (set_giso_config کنار نوشتن‌های
    ربات edu)، ۱۵ ثانیه فرصت آزادشدن قفل به‌جای خطای «database is locked» داده
    می‌شود. روی هر دو اتصال giso.db و bot.db اعمال می‌شود.
    """
    try:
        conn.execute("PRAGMA busy_timeout = 15000")
        conn.execute("PRAGMA journal_mode = WAL")
    except Exception:
        pass


def get_giso_db_conn() -> sqlite3.Connection:
    """اتصال مرکزی به giso.db با WAL و foreign_keys فعال.

    اتصال‌ها از نوع ``_ManagedConnection`` هستند: در پایان هر بلوک ``with``
    خودکار بسته می‌شوند (نشتی FD که قبلاً در ۳۶۸ نقطه‌ی مصرف وجود داشت).

    اگر GISO_DB_ENGINE=postgres باشد، اتصال PostgreSQL با همان API برمی‌گردد
    (مرز دوانجینه در giso/db_engine.py؛ sqlite برای توسعه/تست دست‌نخورده است).
    """
    from giso import db_engine
    if db_engine.is_pg("giso"):
        return db_engine.connect_pg("giso", close_on_exit=True)
    GISO_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(GISO_DB_PATH), check_same_thread=False, factory=_ManagedConnection)
    conn.row_factory = sqlite3.Row
    try:
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        conn.execute("PRAGMA synchronous=NORMAL")
        _set_db_performance(conn)
    except Exception:
        pass
    return conn


def get_bot_db_conn() -> sqlite3.Connection | None:
    """اتصال مرکزی به bot.db (دیتابیس مشترک با ربات آموزش) — همان سخت‌سازی get_giso_db_conn.

    busy_timeout برای جلوگیری از «database is locked» هنگام نوشتن‌های هم‌زمان
    (مثلاً set_giso_config از سمت گیسو در کنار نوشتن‌های ربات edu) و WAL برای
    خواندن‌های هم‌زمان. foreign_keys عمداً فعال نمی‌شود: اسکیمای bot.db متعلق به
    bot_edu است و ماژول‌های گیسو فقط جدول‌های giso_* (بدون FK) را می‌نویسند تا
    رفتار ربات آموزش دست‌نخورده بماند.
    """
    try:
        from giso import db_engine
        if db_engine.is_pg("bot"):
            return db_engine.connect_pg("bot", close_on_exit=True)
        BOT_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(
            str(BOT_DB_PATH), check_same_thread=False, timeout=15,
            factory=_ManagedConnection,
        )
        conn.row_factory = sqlite3.Row
        try:
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA synchronous=NORMAL")
            _set_db_performance(conn)
        except Exception:
            pass
        return conn
    except Exception as exc:
        # ربات آموزش دیتابیس را قفل کرده / فایل موقتاً در دسترس نیست:
        # به‌جای کرش، None برگردانده می‌شود. همهٔ نقاط مصرف (app.py، پنل)
        # در try/except با مقدار پیش‌فرض امن، None را handle می‌کنند.
        logger.warning("bot.db در دسترس نیست، از مسیر امن/کش استفاده می‌شود: %s", exc)
        return None


def get_site_url(path: str = "") -> str:
    """خواندن آدرس پایه‌ی سایت از giso_config (key='site_base_url') و الحاق مسیر.

    هیچ آدرسی hardcode نمی‌شود؛ مقدار پیش‌فرض فقط fallback ایمن است. اتصال با
    context-manager بسته می‌شود تا نشتی connection رخ ندهد. خروجی همیشه بدون
    اسلش انتهاییِ اضافه است.
    """
    base = DEFAULT_SITE_BASE_URL
    try:
        with get_giso_db_conn() as conn:
            row = conn.execute(
                "SELECT value FROM giso_config WHERE key='site_base_url'"
            ).fetchone()
        if row and row[0]:
            base = str(row[0]).strip().rstrip("/") or DEFAULT_SITE_BASE_URL
    except Exception as e:
        logger.debug(f"get_site_url: {e}")
    if path:
        return f"{base}/{str(path).lstrip('/')}"
    return base


def get_user_site_data(phone: str) -> dict:
    """خلاصه‌ی وضعیت کاربر در سایت بر اساس شماره موبایل نرمال‌شده.

    اسکیمای واقعی giso.db را می‌خواند (کاربر/سفارش/آگهی/پیشنهاد/آنالیز/اعلان/
    کیف پول/مرکز). همه کوئری‌ها best-effort و در try مستقل هستند تا خطای یک
    جدول کل نتیجه را خراب نکند.
    """
    from giso.phones import normalize_phone

    data = {
        "phone": phone,
        "site_user_id": None,
        "has_site_account": False,
        "orders_count": 0,
        "latest_order_status": None,
        "active_listings": 0,
        "pending_buy_offers": 0,
        "latest_analysis": None,
        "unread_notifications": 0,
        "wallet_cash": 0,
        "wallet_spend": 0,
        "hair_orders_count": 0,
        "hair_pending_count": 0,
        "has_center": False,
        "center_status": None,
    }
    try:
        np = normalize_phone(phone or "")
        if not np:
            return data
        conn = get_giso_db_conn()
        try:
            cur = conn.cursor()

            row = cur.execute(
                "SELECT id FROM giso_web_auth WHERE phone=? LIMIT 1", (np,)
            ).fetchone()
            uid = int(row[0]) if row and row[0] is not None else None
            data["has_site_account"] = uid is not None
            data["site_user_id"] = uid

            row = cur.execute(
                "SELECT COUNT(*), COALESCE((SELECT status FROM product_orders "
                "WHERE phone=? ORDER BY id DESC LIMIT 1),'') FROM product_orders WHERE phone=?",
                (np, np),
            ).fetchone()
            if row:
                data["orders_count"] = int(row[0] or 0)
                data["latest_order_status"] = row[1] or None

            row = cur.execute(
                "SELECT COUNT(*), SUM(CASE WHEN status IN ('pending','reviewing') THEN 1 ELSE 0 END) "
                "FROM hair_orders WHERE phone=?",
                (np,),
            ).fetchone()
            if row:
                data["hair_orders_count"] = int(row[0] or 0)
                data["hair_pending_count"] = int(row[1] or 0)

            if uid is not None:
                row = cur.execute(
                    "SELECT COUNT(*) FROM hair_listings "
                    "WHERE seller_user_id=? AND status='published' AND COALESCE(deleted_at,'')=''",
                    (uid,),
                ).fetchone()
                data["active_listings"] = int(row[0] or 0) if row else 0

                row = cur.execute(
                    "SELECT COUNT(*) FROM buyer_offers WHERE buyer_user_id=? AND status='pending'",
                    (uid,),
                ).fetchone()
                data["pending_buy_offers"] = int(row[0] or 0) if row else 0

            row = cur.execute(
                "SELECT ai_report_json, plan_json, type, created_at FROM analyses "
                "WHERE (user_id=? OR phone=?) ORDER BY id DESC LIMIT 1",
                (uid if uid is not None else -1, np),
            ).fetchone()
            if row:
                data["latest_analysis"] = {
                    "report_json": row[0] or "{}",
                    "plan_json": row[1] or "",
                    "type": row[2] or "hair",
                    "date": row[3] or "",
                }

            try:
                row = cur.execute(
                    "SELECT COUNT(*) FROM giso_notifications "
                    "WHERE target_role='user' AND recipient_id=? AND status='unread'",
                    (np,),
                ).fetchone()
                data["unread_notifications"] = int(row[0] or 0) if row else 0
            except Exception:
                pass  # ممکن است جدول/migration هنوز نباشد

            if uid is not None:
                try:
                    rows = cur.execute(
                        "SELECT COALESCE(NULLIF(balance_scope,''),'cash') AS scope, "
                        "COALESCE(SUM(amount),0) FROM wallet_transactions "
                        "WHERE user_id=? AND status IN ('available','used','pending','paid') "
                        "GROUP BY scope",
                        (uid,),
                    ).fetchall()
                    for r in rows or []:
                        scope = (r[0] or "cash")
                        val = int(r[1] or 0)
                        if scope == "spend":
                            data["wallet_spend"] = val
                        else:
                            data["wallet_cash"] += val
                except Exception:
                    pass

            if uid is not None:
                row = cur.execute(
                    "SELECT status FROM beauty_centers WHERE owner_user_id=? ORDER BY id DESC LIMIT 1",
                    (uid,),
                ).fetchone()
                if row:
                    data["has_center"] = True
                    data["center_status"] = row[0]
        finally:
            try:
                conn.close()
            except Exception:
                pass
    except Exception as e:
        logger.error(f"get_user_site_data error: {e}")
    return data


def send_bot_push(bale_id, text: str, reply_markup=None) -> bool:
    """ارسال یک پیام بله به یک chat_id با حداکثر ۲ تلاش (best-effort، امن برای
    فراخوانی از سرویس‌های سایت/بات). توکن از env یا bot.db خوانده می‌شود؛ هیچ
    خطایی جریان را نمی‌شکند. خروجی True فقط در صورت تحویل موفق است."""
    try:
        recipient = 0
        try:
            recipient = int(str(bale_id).strip())
        except (TypeError, ValueError):
            return False
        if not recipient or not (text or "").strip():
            return False
        from giso.base import _http_post, _token_from_db, _token_from_env

        token = _token_from_env() or _token_from_db() or ""
        if not token:
            logger.debug("send_bot_push: no token configured")
            return False
        url = f"https://tapi.bale.ai/bot{token}/sendMessage"
        payload = {"chat_id": recipient, "text": str(text)[:4000], "parse_mode": "HTML"}
        if reply_markup is not None:
            try:
                payload["reply_markup"] = json.loads(reply_markup.to_json())
            except Exception:
                try:
                    payload["reply_markup"] = reply_markup
                except Exception:
                    pass
        for attempt in range(1, 3):  # حداکثر ۲ تلاش
            resp = _http_post(url, json_payload=payload)
            code = getattr(resp, "status_code", None) if resp is not None else None
            if code in (200, 201, 202, 204):
                return True
            logger.info("send_bot_push to %s attempt %s/2 failed: code=%s", recipient, attempt, code)
            if attempt < 2:
                time.sleep(0.6)
        return False
    except Exception as e:
        logger.debug(f"send_bot_push error: {e}")
        return False


def checkpoint_giso_db():
    """
    انتقال همه اطلاعات از WAL به دیتابیس اصلی (TRUNCATE).
    باید قبل از هر backup و هنگام بسته شدن ربات صدا زده شود.
    سرعت خواندن عادی را تحت تأثیر قرار نمی‌دهد.
    """
    try:
        conn = get_giso_db_conn()
        try:
            conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        finally:
            conn.close()
        logger.info("checkpoint انجام شد: اطلاعات WAL به DB منتقل شد")
        return True
    except Exception as e:
        logger.error(f"checkpoint_giso_db error: {e}")
        return False


