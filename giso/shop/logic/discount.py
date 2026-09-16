# -*- coding: utf-8 -*-
"""giso/shop/logic/discount.py — سیستم کد تخفیف فروشگاه.

- ساخت/ویرایش/حذف کد تخفیف توسط سوپرادمین
- اعمال کد تخفیف هنگام تسویه
- پشتیبانی از درصدی و مبلغ ثابت
"""
import logging
from datetime import datetime

from giso.money import format_toman

logger = logging.getLogger("giso_discount")

DISCOUNT_SCHEMA = """
CREATE TABLE IF NOT EXISTS discount_codes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    code TEXT NOT NULL UNIQUE,
    discount_type TEXT DEFAULT 'percent',
    discount_value INTEGER DEFAULT 0,
    min_order_amount INTEGER DEFAULT 0,
    max_uses INTEGER DEFAULT 0,
    used_count INTEGER DEFAULT 0,
    is_active INTEGER DEFAULT 1,
    expires_at TEXT DEFAULT '',
    created_at TEXT DEFAULT ''
);
CREATE INDEX IF NOT EXISTS idx_discount_code ON discount_codes(code);
"""


def init_discount_tables(conn):
    """ایجاد جدول کدهای تخفیف."""
    try:
        conn.executescript(DISCOUNT_SCHEMA)
        conn.commit()
    except Exception as e:
        logger.error(f"init_discount_tables: {e}")


def create_discount_code(code, discount_type="percent", discount_value=0,
                         min_order_amount=0, max_uses=0, expires_at=""):
    """ساخت کد تخفیف جدید."""
    try:
        from giso.base import get_giso_db_conn
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        with get_giso_db_conn() as conn:
            conn.execute(
                "INSERT INTO discount_codes (code, discount_type, discount_value, min_order_amount, max_uses, expires_at, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (code.upper().strip(), discount_type, int(discount_value),
                 int(min_order_amount), int(max_uses), expires_at, now)
            )
            conn.commit()
        return {"ok": True}
    except Exception as e:
        logger.error(f"create_discount_code: {e}")
        return {"ok": False, "error": str(e)}


def validate_discount_code(code, order_total=0):
    """اعتبارسنجی کد تخفیف. خروجی: {ok, discount_type, discount_value, message}"""
    try:
        from giso.base import get_giso_db_conn
        with get_giso_db_conn() as conn:
            row = conn.execute(
                "SELECT * FROM discount_codes WHERE code=? AND is_active=1",
                (code.upper().strip(),)
            ).fetchone()
        if not row:
            return {"ok": False, "message": "کد تخفیف نامعتبر است"}
        row = dict(row)
        # بررسی انقضا
        if row.get("expires_at"):
            try:
                exp = datetime.strptime(row["expires_at"], "%Y-%m-%d %H:%M:%S")
                if datetime.now() > exp:
                    return {"ok": False, "message": "کد تخفیف منقضی شده است"}
            except Exception:
                pass
        # بررسی تعداد استفاده
        if row.get("max_uses", 0) > 0 and row.get("used_count", 0) >= row["max_uses"]:
            return {"ok": False, "message": "کد تخفیف به حداکثر استفاده رسیده است"}
        # بررسی حداقل مبلغ سفارش
        if row.get("min_order_amount", 0) > 0 and order_total < row["min_order_amount"]:
            return {"ok": False, "message": f"حداقل مبلغ سفارش برای این کد: {format_toman(row['min_order_amount'])}"}
        # محاسبه تخفیف
        dtype = row.get("discount_type", "percent")
        dvalue = row.get("discount_value", 0)
        if dtype == "percent":
            discount_amount = int(order_total * dvalue / 100)
        else:
            discount_amount = min(dvalue, order_total)
        return {
            "ok": True,
            "discount_type": dtype,
            "discount_value": dvalue,
            "discount_amount": discount_amount,
            "message": f"کد تخفیف اعمال شد: {'{}٪'.format(dvalue) if dtype == 'percent' else format_toman(dvalue)}"
        }
    except Exception as e:
        logger.error(f"validate_discount_code: {e}")
        return {"ok": False, "message": "خطا در بررسی کد تخفیف"}


def apply_discount_code(code):
    """افزایش تعداد استفاده از کد تخفیف."""
    try:
        from giso.base import get_giso_db_conn
        with get_giso_db_conn() as conn:
            conn.execute(
                "UPDATE discount_codes SET used_count = used_count + 1 WHERE code=?",
                (code.upper().strip(),)
            )
            conn.commit()
    except Exception as e:
        logger.error(f"apply_discount_code: {e}")


def list_discount_codes():
    """لیست همه کدهای تخفیف."""
    try:
        from giso.base import get_giso_db_conn
        with get_giso_db_conn() as conn:
            rows = conn.execute("SELECT * FROM discount_codes ORDER BY id DESC").fetchall()
        return [dict(r) for r in rows]
    except Exception as e:
        logger.error(f"list_discount_codes: {e}")
        return []


def toggle_discount_code(code_id):
    """فعال/غیرفعال کردن کد تخفیف."""
    try:
        from giso.base import get_giso_db_conn
        with get_giso_db_conn() as conn:
            row = conn.execute("SELECT is_active FROM discount_codes WHERE id=?", (int(code_id),)).fetchone()
            if row:
                new_val = 0 if row[0] else 1
                conn.execute("UPDATE discount_codes SET is_active=? WHERE id=?", (new_val, int(code_id)))
                conn.commit()
                return {"ok": True, "is_active": new_val}
    except Exception as e:
        logger.error(f"toggle_discount_code: {e}")
    return {"ok": False}


def delete_discount_code(code_id):
    """حذف کد تخفیف."""
    try:
        from giso.base import get_giso_db_conn
        with get_giso_db_conn() as conn:
            conn.execute("DELETE FROM discount_codes WHERE id=?", (int(code_id),))
            conn.commit()
        return {"ok": True}
    except Exception as e:
        logger.error(f"delete_discount_code: {e}")
        return {"ok": False}
