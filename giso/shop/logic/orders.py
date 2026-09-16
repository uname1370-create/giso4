# -*- coding: utf-8 -*-
"""giso/shop/logic/orders.py — کمکی‌های سفارش فروشگاه (فاز جامع خرید)

- ستون‌های اختیاری سفارش (courier_note / delivery_time) با ALTER idempotent روی giso.db
- ذخیره یادداشت پیک و زمان ارسال برای سفارش‌های ثبت‌شده
- خواندن سفارش‌ها با نام محصول (برای صفحه موفقیت)
- پیام رسمی سیستم به کاربر (بله) — همان الگوی اعلان ادمین
- برچسب فارسی وضعیت‌ها (در حال بررسی / تأیید شد / در حال ارسال / تحویل شد / لغو)

هیچ جدول/مدل جدیدی ساخته نمی‌شود؛ فقط ستون‌های اختیاری (safe، idempotent).
"""
import logging
from concurrent.futures import ThreadPoolExecutor

from giso.base import get_giso_db_conn, normalize_phone

logger = logging.getLogger("giso_shop_logic_orders")

# ارسال بله برای کاربر در پس‌زمینه (غیرمسدودکننده برای Flask و event loop ربات)
_USER_NOTIFY_POOL = ThreadPoolExecutor(max_workers=4, thread_name_prefix="giso_user_notify")

STATUS_FA = {
    "pending": "در حال بررسی",
    "approved": "تأیید شد",
    "shipped": "در حال ارسال",
    "delivered": "تحویل شد",
    "rejected": "رد شد",
    "completed": "تکمیل شد",
    "cancelled": "لغو شد",
}


def status_fa(status) -> str:
    return STATUS_FA.get((status or "").lower(), status or "—")


def ensure_order_columns():
    """افزودن ستون‌های اختیاری courier_note و delivery_time به product_orders (idempotent)."""
    try:
        with get_giso_db_conn() as conn:
            cols = {r[1] for r in conn.execute("PRAGMA table_info(product_orders)").fetchall()}
            for col in ("courier_note", "delivery_time"):
                if col not in cols:
                    conn.execute("ALTER TABLE product_orders ADD COLUMN %s TEXT DEFAULT ''" % col)
            conn.commit()
    except Exception as e:
        logger.debug(f"ensure_order_columns: {e}")


def set_order_fields(order_ids, courier_note="", delivery_time=""):
    """ذخیره یادداشت پیک و/یا زمان ارسال برای سفارش‌ها (داده واقعی)."""
    try:
        ensure_order_columns()
        courier_note = (courier_note or "").strip()
        delivery_time = (delivery_time or "").strip()
        if not courier_note and not delivery_time:
            return
        with get_giso_db_conn() as conn:
            for oid in order_ids:
                if courier_note:
                    conn.execute("UPDATE product_orders SET courier_note=? WHERE id=?", (courier_note, int(oid)))
                if delivery_time:
                    conn.execute("UPDATE product_orders SET delivery_time=? WHERE id=?", (delivery_time, int(oid)))
            conn.commit()
    except Exception as e:
        logger.warning(f"set_order_fields: {e}")


def get_orders_for_ids(ids, phone=None, user_id=None):
    """خواندن سفارش‌ها + نام/قیمت محصول؛ در صورت ارائه مالک، فقط سفارش‌های او."""
    out = []
    try:
        with get_giso_db_conn() as conn:
            for oid in ids or []:
                sql = (
                    "SELECT po.*, COALESCE(p.name, 'محصول #' || po.product_id) AS pname, "
                    "COALESCE(p.price, 0) AS price "
                    "FROM product_orders po LEFT JOIN products p ON p.id = po.product_id "
                    "WHERE po.id=?"
                )
                params = [int(oid)]
                if user_id is not None:
                    sql += " AND po.user_id=?"
                    params.append(int(user_id))
                elif phone:
                    sql += " AND po.phone=?"
                    params.append(normalize_phone(phone))
                row = conn.execute(sql, tuple(params)).fetchone()
                if row:
                    out.append(dict(row))
    except Exception as e:
        logger.warning(f"get_orders_for_ids: {e}")
    return out


def _send_bale_to_user(recipient: int, text: str):
    """ارسال پیام بله به کاربر (پس‌زمینه)."""
    try:
        from giso.base import _token_from_env, _token_from_db, _http_post
        from giso.security import record_delivery
        token = _token_from_env() or _token_from_db() or ""
        if not token:
            record_delivery(0, recipient, "failed", error_code="missing_token", error_message="Bale token is not configured")
            return
        url = f"https://tapi.bale.ai/bot{token}/sendMessage"
        resp = _http_post(url, json_payload={"chat_id": recipient, "text": text, "parse_mode": "HTML"})
        code = getattr(resp, "status_code", 0) if resp is not None else 0
        if code in (200, 201, 202, 204):
            record_delivery(0, recipient, "sent", http_status=code)
        else:
            record_delivery(0, recipient, "failed", http_status=code, error_code="http_error", error_message="Bale returned HTTP %s" % code)
    except Exception as e:
        logger.debug(f"_send_bale_to_user: {e}")


def notify_user_product_order(phone, text):
    """پیام رسمی سیستم به کاربر در بله (مثل پشتیبانی رسمی خرید).

    اعلان پنل کاربر (DB) به‌صورت هم‌زمان ثبت می‌شود؛ ارسال بله در پس‌زمینه است.
    """
    try:
        np = normalize_phone(phone or "")
        if not np:
            return
        try:
            from giso.panel.modules.notifications import log_user_notification
            log_user_notification(np, "order_status", "به‌روزرسانی سفارش فروشگاه", text)
        except Exception as exc:
            logger.exception("user order notification record failed: %s", exc)
        with get_giso_db_conn() as conn:
            row = conn.execute(
                "SELECT bale_id FROM giso_users WHERE phone=? AND contact_shared=1",
                (np,)
            ).fetchone()
        if not row or not row["bale_id"] or not str(row["bale_id"]).isdigit():
            return
        recipient = int(row["bale_id"])
        _USER_NOTIFY_POOL.submit(_send_bale_to_user, recipient, text)
    except Exception as e:
        logger.debug(f"notify_user_product_order: {e}")


__all__ = [
    "status_fa", "ensure_order_columns", "set_order_fields",
    "get_orders_for_ids", "notify_user_product_order", "STATUS_FA",
]
