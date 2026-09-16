# -*- coding: utf-8 -*-
"""giso/shop/panel/_shared.py — کانتکست مشترک ماژول‌های پنل فروشگاه (فاز B)."""
import logging

from giso.models import Product, ProductOrder, StockNotify
from giso.base import get_giso_db_conn
from giso.shop.logic.channel_bridge import get_publish_mode
from giso.shop.logic.inventory import _get_giso_config_safe

logger = logging.getLogger("giso_shop_panel_shared")


def build_admin_shop_context():
    """داده‌های صفحه فروشگاه ادمین (همه از دیتابیس واقعی)."""
    ctx = {
        "products_count": 0, "orders_count": 0, "pending_channel_count": 0,
        "stock_notifies_count": 0, "revenue": 0, "month_revenue": 0, "today_orders": 0,
        "pending_products": [], "stock_notifies": [], "recent_orders": [],
        "publish_mode": "review", "bale_channel_id": "",
    }
    try:
        from datetime import datetime, timedelta
        from giso.models import db as _db
        from sqlalchemy import func as _sf
        _cut = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d %H:%M:%S")
        ctx["month_revenue"] = int((_db.session.query(
            _sf.coalesce(_sf.sum(ProductOrder.quantity * Product.price), 0))
            .select_from(ProductOrder)
            .join(Product, Product.id == ProductOrder.product_id)
            .filter(ProductOrder.status == "completed", ProductOrder.created_at >= _cut).scalar()) or 0)
        ctx["today_orders"] = ProductOrder.query.filter(
            ProductOrder.created_at >= datetime.now().strftime("%Y-%m-%d 00:00:00")).count()
    except Exception as e:
        logger.debug(f"admin shop month stats: {e}")
    try:
        ctx["products_count"] = Product.query.count()
        ctx["orders_count"] = ProductOrder.query.count()
        ctx["pending_channel_count"] = Product.query.filter(Product.publish_status == "pending").count()
        ctx["stock_notifies_count"] = StockNotify.query.count()
    except Exception as e:
        logger.debug(f"admin shop counts: {e}")
    try:
        ctx["pending_products"] = [
            {"id": p.id, "name": p.name, "price": p.price or 0, "old_price": p.old_price or 0,
             "category": p.category or "", "subcategory": p.subcategory or "",
             "description": p.description or "", "in_stock": bool(p.in_stock),
             "image_path": p.image_path or "", "created_at": p.created_at or "",
             "source": p.source or ""}
            for p in Product.query.filter(Product.publish_status == "pending")
            .order_by(Product.id.desc()).limit(30).all()
        ]
    except Exception as e:
        logger.debug(f"admin shop pending: {e}")
    try:
        ctx["stock_notifies"] = [
            {"id": n.id, "phone": n.phone, "product_id": n.product_id,
             "product_name": (Product.query.get(n.product_id).name if Product.query.get(n.product_id) else "—"),
             "created_at": n.created_at or ""}
            for n in StockNotify.query.order_by(StockNotify.id.desc()).limit(10).all()
        ]
    except Exception as e:
        logger.debug(f"admin shop notifies: {e}")
    try:
        ctx["recent_orders"] = [
            {"id": o.id, "customer_name": o.customer_name or "—", "phone": o.phone or "",
             "product_name": (o.product.name if o.product else f"محصول #{o.product_id}"),
             "quantity": o.quantity or 1, "status": o.status or "pending", "created_at": o.created_at or ""}
            for o in ProductOrder.query.order_by(ProductOrder.id.desc()).limit(8).all()
        ]
    except Exception as e:
        logger.debug(f"admin shop orders: {e}")
    try:
        from sqlalchemy import func as _f
        ctx["revenue"] = int((db_session_revenue(_f)) or 0)
    except Exception as e:
        logger.debug(f"admin shop revenue: {e}")
    try:
        ctx["publish_mode"] = get_publish_mode()
        ctx["bale_channel_id"] = _get_giso_config_safe("bale_channel_id", "")
    except Exception:
        pass
    return ctx


def db_session_revenue(_f):
    from giso.models import db
    return (db.session.query(_f.coalesce(_f.sum(ProductOrder.quantity * Product.price), 0))
            .select_from(ProductOrder)
            .join(Product, Product.id == ProductOrder.product_id)
            .filter(ProductOrder.status == "completed").scalar())


def build_super_shop_context():
    """داده‌های صفحه «تنظیمات فروشگاه» (فقط سوپرادمین)."""
    ctx = {
        "publish_mode": "review", "bale_channel_id": "",
        "products_count": 0, "orders_count": 0, "pending_channel_count": 0,
    }
    try:
        ctx["publish_mode"] = get_publish_mode()
        ctx["bale_channel_id"] = _get_giso_config_safe("bale_channel_id", "")
        ctx["products_count"] = Product.query.count()
        ctx["orders_count"] = ProductOrder.query.count()
        ctx["pending_channel_count"] = Product.query.filter(Product.publish_status == "pending").count()
    except Exception as e:
        logger.debug(f"super shop ctx: {e}")
    return ctx


def build_user_shop_context(phone):
    """داده‌های صفحه «فروشگاه من» پنل کاربر (فقط داده‌های خود کاربر)."""
    ctx = {"orders": [], "stock_notifies": [], "wishlist_note": True}
    try:
        ctx["orders"] = [
            {"id": o.id, "product_name": (o.product.name if o.product else f"محصول #{o.product_id}"),
             "quantity": o.quantity or 1, "price": (o.product.price if o.product else 0),
             "status": o.status or "pending", "created_at": o.created_at or ""}
            for o in ProductOrder.query.filter(ProductOrder.phone == phone)
            .order_by(ProductOrder.id.desc()).limit(20).all()
        ]
    except Exception as e:
        logger.debug(f"user shop orders: {e}")
    try:
        ctx["stock_notifies"] = [
            {"id": n.id, "product_id": n.product_id,
             "product_name": (Product.query.get(n.product_id).name if Product.query.get(n.product_id) else "—"),
             "created_at": n.created_at or ""}
            for n in StockNotify.query.filter(StockNotify.phone == phone)
            .order_by(StockNotify.id.desc()).limit(20).all()
        ]
    except Exception as e:
        logger.debug(f"user shop notifies: {e}")
    return ctx
