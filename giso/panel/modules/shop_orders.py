# -*- coding: utf-8 -*-
"""panel/modules/shop_orders.py — سفارش‌های فروشگاه + جستجو + حذف سوپر."""
import logging

from flask import request, redirect, url_for, flash

from giso.models import db, ProductOrder
from giso.base import normalize_phone, get_giso_db_conn
from giso.panel.permissions import current_role_and_perms

logger = logging.getLogger("giso_panel_shop")

VALID_STATUSES = ("pending", "approved", "shipped", "delivered", "rejected", "completed", "cancelled")


def _require_super():
    role, _perms, _bid = current_role_and_perms()
    if role != "super":
        flash("فقط سوپرادمین می‌تواند سفارش را حذف کند.", "warning")
        return redirect(url_for("panel.shop_orders"))
    return None


def handle_delete(order_id: int):
    g = _require_super()
    if g:
        return g
    try:
        with get_giso_db_conn() as conn:
            conn.execute("DELETE FROM shop_invoice_items WHERE order_id=?", (int(order_id),))
            try:
                conn.execute("DELETE FROM shop_order_messages WHERE order_id=?", (int(order_id),))
            except Exception:
                pass
            conn.execute("DELETE FROM product_orders WHERE id=?", (int(order_id),))
            conn.commit()
        flash(f"سفارش #{order_id} حذف شد.", "success")
    except Exception as exc:
        logger.error("delete shop order: %s", exc)
        flash("خطا در حذف سفارش.", "danger")
    return redirect(url_for("panel.shop_orders", status=request.form.get("status") or "all", q=request.form.get("q") or ""))


def handle_delete_by_status():
    g = _require_super()
    if g:
        return g
    status = (request.form.get("status") or "").strip().lower()
    if status not in VALID_STATUSES:
        flash("وضعیت نامعتبر است.", "warning")
        return redirect(url_for("panel.shop_orders"))
    try:
        with get_giso_db_conn() as conn:
            rows = conn.execute("SELECT id FROM product_orders WHERE status=?", (status,)).fetchall()
            ids = [int(r[0]) for r in rows]
            if ids:
                marks = ",".join("?" * len(ids))
                conn.execute(f"DELETE FROM shop_invoice_items WHERE order_id IN ({marks})", ids)
                try:
                    conn.execute(f"DELETE FROM shop_order_messages WHERE order_id IN ({marks})", ids)
                except Exception:
                    pass
                conn.execute("DELETE FROM product_orders WHERE status=?", (status,))
            conn.commit()
        flash(f"{len(ids)} سفارش با وضعیت «{status}» حذف شد.", "success")
    except Exception as exc:
        logger.error("delete shop orders by status: %s", exc)
        flash("خطا در حذف گروهی سفارش‌ها.", "danger")
    return redirect(url_for("panel.shop_orders", status=status))


def context():
    q = (request.args.get("q") or "").strip()
    status = (request.args.get("status") or "all").strip().lower()
    orders = []
    try:
        query = ProductOrder.query
        if q:
            qn = normalize_phone(q)
            if qn:
                query = query.filter(
                    db.or_(ProductOrder.phone == qn,
                           ProductOrder.customer_name.like(f"%{q}%")))
            else:
                query = query.filter(ProductOrder.customer_name.like(f"%{q}%"))
        valid_statuses = VALID_STATUSES
        if status in valid_statuses:
            query = query.filter(ProductOrder.status == status)
        else:
            status = "all"
        orders = query.order_by(ProductOrder.id.desc()).limit(200).all()
    except Exception as e:
        logger.error(f"panel shop_orders: {e}")
    return {"orders": orders, "q": q, "status": status}
