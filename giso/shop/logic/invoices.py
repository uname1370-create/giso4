# -*- coding: utf-8 -*-
"""فاکتور رسمی سفارش‌های فروشگاه و backfill ایمن سفارش‌های تاریخی."""
import logging
import sqlite3

from giso.base import get_giso_db_conn
from giso.wallet import get_financial_settings

logger = logging.getLogger("giso_shop_invoices")


def _payment_status(wallet_paid: int, cod_amount: int) -> str:
    if int(cod_amount or 0) == 0:
        return "settled"
    return "split_due" if int(wallet_paid or 0) > 0 else "cod_due"


def _date_token(created_at: str) -> str:
    digits = "".join(ch for ch in str(created_at or "")[:10] if ch.isdigit())
    return digits or "LEGACY"


def ensure_invoice_for_order(order_id: int):
    """برگرداندن invoice_id؛ برای سفارش قدیمی فاقد snapshot، یک فاکتور legacy می‌سازد."""
    conn = get_giso_db_conn()
    try:
        conn.execute("BEGIN IMMEDIATE")
        order = conn.execute(
            "SELECT po.*,COALESCE(p.name,'محصول #' || po.product_id) AS product_name,"
            "COALESCE(p.price,0) AS current_price FROM product_orders po "
            "LEFT JOIN products p ON p.id=po.product_id WHERE po.id=?",
            (int(order_id),),
        ).fetchone()
        if not order:
            conn.rollback()
            return None
        if order["invoice_id"]:
            found = conn.execute("SELECT id FROM shop_invoices WHERE id=?", (int(order["invoice_id"]),)).fetchone()
            if found:
                conn.commit()
                return int(found["id"])

        checkout_id = int(order["checkout_id"] or 0)
        if checkout_id:
            found = conn.execute("SELECT id FROM shop_invoices WHERE checkout_id=?", (checkout_id,)).fetchone()
            if found:
                invoice_id = int(found["id"])
                conn.execute("UPDATE product_orders SET invoice_id=? WHERE checkout_id=?", (invoice_id, checkout_id))
                conn.commit()
                return invoice_id
            grouped = conn.execute(
                "SELECT po.*,COALESCE(p.name,'محصول #' || po.product_id) AS product_name,"
                "COALESCE(p.price,0) AS current_price FROM product_orders po "
                "LEFT JOIN products p ON p.id=po.product_id WHERE po.checkout_id=? ORDER BY po.id",
                (checkout_id,),
            ).fetchall()
            checkout = conn.execute("SELECT * FROM shop_checkouts WHERE id=?", (checkout_id,)).fetchone()
        else:
            grouped = [order]
            checkout = None

        calculated_gross = sum(max(0, int(row["current_price"] or 0)) * max(1, int(row["quantity"] or 1)) for row in grouped)
        gross = max(0, int(checkout["gross_amount"] or 0)) if checkout else calculated_gross
        discount = max(0, int(checkout["discount_amount"] or 0)) if checkout else 0
        payable = max(0, gross - discount)
        wallet_paid = max(0, int(checkout["wallet_used"] or 0)) if checkout else 0
        cod_amount = max(0, int(checkout["cod_amount"] or 0)) if checkout else payable
        status = _payment_status(wallet_paid, cod_amount)
        created_at = str((checkout["created_at"] if checkout else order["created_at"]) or "")
        key = checkout_id if checkout_id else int(order_id)
        kind = "C" if checkout_id else "O"
        invoice_number = f"GSO-{_date_token(created_at)}-{kind}{key:06d}"
        cur = conn.execute(
            "INSERT INTO shop_invoices "
            "(invoice_number,checkout_id,user_id,customer_name,customer_phone,customer_address,"
            "gross_amount,discount_amount,payable_amount,wallet_paid_amount,cod_amount,payment_status,created_at) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (invoice_number, checkout_id or None, int(order["user_id"] or 0), order["customer_name"],
             order["phone"], order["address"], gross, discount, payable, wallet_paid, cod_amount,
             status, created_at),
        )
        invoice_id = int(cur.lastrowid)
        for row in grouped:
            unit_price = max(0, int(row["current_price"] or 0))
            quantity = max(1, int(row["quantity"] or 1))
            conn.execute(
                "INSERT INTO shop_invoice_items "
                "(invoice_id,order_id,product_id,product_name,unit_price,quantity,line_total) "
                "VALUES (?,?,?,?,?,?,?)",
                (invoice_id, int(row["id"]), int(row["product_id"]), row["product_name"],
                 unit_price, quantity, unit_price * quantity),
            )
            conn.execute("UPDATE product_orders SET invoice_id=? WHERE id=?", (invoice_id, int(row["id"])))
        conn.commit()
        return invoice_id
    except sqlite3.IntegrityError:
        conn.rollback()
        # race-safe: checkout invoice may have been created by another request.
        try:
            row = conn.execute(
                "SELECT si.id FROM shop_invoices si JOIN product_orders po "
                "ON po.invoice_id=si.id OR (po.checkout_id IS NOT NULL AND po.checkout_id=si.checkout_id) "
                "WHERE po.id=? LIMIT 1", (int(order_id),)
            ).fetchone()
            return int(row["id"]) if row else None
        except Exception:
            return None
    except Exception as exc:
        conn.rollback()
        logger.exception("ensure invoice for order %s failed: %s", order_id, exc)
        return None
    finally:
        conn.close()


def get_invoice_for_order(order_id: int):
    invoice_id = ensure_invoice_for_order(order_id)
    if not invoice_id:
        return None
    try:
        with get_giso_db_conn() as conn:
            invoice = conn.execute("SELECT * FROM shop_invoices WHERE id=?", (invoice_id,)).fetchone()
            items = conn.execute(
                "SELECT * FROM shop_invoice_items WHERE invoice_id=? ORDER BY id", (invoice_id,)
            ).fetchall()
            order_ids = conn.execute(
                "SELECT id,tracking_code,status FROM product_orders WHERE invoice_id=? ORDER BY id", (invoice_id,)
            ).fetchall()
        if not invoice:
            return None
        return {
            "invoice": dict(invoice),
            "items": [dict(row) for row in items],
            "orders": [dict(row) for row in order_ids],
        }
    except Exception as exc:
        logger.exception("read invoice %s failed: %s", invoice_id, exc)
        return None


def get_invoice_seller() -> dict:
    settings = get_financial_settings()
    return {
        "name": settings.get("invoice_seller_name") or "گیسو صادقی",
        "phone": settings.get("invoice_seller_phone") or "پشتیبانی از طریق پیام‌رسان گیسو",
        "address": settings.get("invoice_seller_address") or "مشهد",
        "logo": "images/giso-original-artwork.svg",
    }


__all__ = ["ensure_invoice_for_order", "get_invoice_for_order", "get_invoice_seller"]
