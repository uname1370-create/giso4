# -*- coding: utf-8 -*-
"""panel/modules/dashboard.py — پیشخوان تعاملی (فاز 4.9): KPI ها + لیست هر بخش."""
from giso.models import db, User, Product, ProductOrder, HairOrder, Analysis, Review
from giso.base import get_giso_db_conn


def _q1(sql, params=()):
    try:
        with get_giso_db_conn() as conn:
            row = conn.execute(sql, params).fetchone()
            return int((row[0] if row else 0) or 0)
    except Exception:
        return 0


def _recent(sql, limit=5):
    try:
        with get_giso_db_conn() as conn:
            # اگر کوئری خودش LIMIT صریح داشت (سقف دفاعی)، فقط همان را اعمال کن
            # و LIMIT دومی اضافه نکن (جلوگیری از خطای «... LIMIT 50 LIMIT 5»).
            if "limit" not in sql.lower():
                sql = sql + f" LIMIT {int(limit)}"
            rows = conn.execute(sql).fetchall()
            return [dict(r) for r in rows]
    except Exception:
        return []


def work_context():
    """Open operational queues only, for approved normal admins."""
    queues = [
        {"module": "hair_sale", "icon": "💇‍♀️", "label": "درخواست‌های خرید مو در انتظار", "count": _q1(
            "SELECT COUNT(*) FROM hair_orders WHERE status IN ('pending','reviewing')")},
        {"module": "marketplace", "icon": "🏪", "label": "آگهی‌های بازارچه در انتظار", "count": _q1(
            "SELECT COUNT(*) FROM hair_listings WHERE status='pending_review' AND COALESCE(deleted_at,'')='' ")},
        {"module": "marketplace", "icon": "🚩", "label": "گزارش‌های باز بازارچه", "count": _q1(
            "SELECT COUNT(*) FROM listing_reports WHERE status='open'")},
        {"module": "marketplace", "icon": "🧑‍💼", "label": "درخواست‌های خرید مو", "count": _q1(
            "SELECT COUNT(*) FROM buyer_profiles WHERE verification_status='pending'")},
        {"module": "shop_orders", "icon": "🛒", "label": "سفارش‌های باز فروشگاه", "count": _q1(
            "SELECT COUNT(*) FROM product_orders WHERE status IN ('pending','approved','shipped')")},
        {"module": "reviews", "icon": "⭐", "label": "نظرات منتظر تصمیم", "count": _q1(
            "SELECT COUNT(*) FROM reviews WHERE status='hidden'")},
        {"module": "consults", "icon": "💬", "label": "گفتگوها و تیکت‌های باز", "count": (
            _q1("SELECT COUNT(*) FROM consultant_requests WHERE status IN ('new','reviewing','chatting','pending','active')")
            + _q1("SELECT COUNT(*) FROM giso_support_tickets WHERE status IN ('new','reviewing')")
        )},
    ]
    notes = []
    try:
        from giso.panel.modules.notifications import list_notifications
        notes = list_notifications("admin", limit=8)
    except Exception:
        notes = []
    return {
        "work_queues": queues,
        "work_open_total": sum(item["count"] for item in queues),
        "work_notifications": notes,
    }


def context():
    counts = {}
    try:
        counts["users"] = User.query.count()
    except Exception:
        counts["users"] = 0
    try:
        counts["products"] = Product.query.count()
    except Exception:
        counts["products"] = 0
    try:
        counts["orders"] = ProductOrder.query.count()
    except Exception:
        counts["orders"] = 0
    try:
        counts["hair"] = HairOrder.query.count()
    except Exception:
        counts["hair"] = 0
    try:
        counts["analyses"] = Analysis.query.count()
    except Exception:
        counts["analyses"] = 0
    try:
        counts["reviews"] = Review.query.count()
    except Exception:
        counts["reviews"] = 0
    counts["pending_hair"] = _q1("SELECT COUNT(*) FROM hair_orders WHERE status='pending'")
    counts["pending_orders"] = _q1("SELECT COUNT(*) FROM product_orders WHERE status='pending'")
    counts["pending_withdrawals"] = _q1("SELECT COUNT(*) FROM withdrawal_requests WHERE status='pending'")
    try:
        revenue = (db.session.query(db.func.coalesce(
            db.func.sum(ProductOrder.quantity * Product.price), 0))
            .select_from(ProductOrder)
            .join(Product, Product.id == ProductOrder.product_id)
            .filter(ProductOrder.status == "completed").scalar()) or 0
        counts["revenue"] = int(revenue)
    except Exception:
        counts["revenue"] = 0

    # لیست‌های هر بخش (برای کلیک روی کارت — فاز 4.9)
    lists = {
        "users": _recent("SELECT id, phone, name, created_at FROM giso_web_auth ORDER BY id DESC LIMIT 50"),
        "hair": _recent("SELECT id, customer_name, phone, length_cm, status, created_at FROM hair_orders ORDER BY id DESC LIMIT 50"),
        "orders": _recent("SELECT id, customer_name, phone, status, created_at FROM product_orders ORDER BY id DESC LIMIT 50"),
        "analyses": _recent("SELECT id, type, phone, created_at FROM analyses ORDER BY id DESC LIMIT 50"),
        "reviews": _recent("SELECT id, review_type, phone, rating, status, created_at FROM reviews ORDER BY id DESC LIMIT 50"),
        "withdrawals": _recent("SELECT id, user_id, amount, status, created_at FROM withdrawal_requests ORDER BY id DESC LIMIT 50"),
    }
    # فاز جامع UX: گزارش ماهانه (۳۰ روز اخیر) — همان مبنای گزارش‌های فروش مو (درآمد واقعی)
    monthly = {"hair_revenue": 0, "hair_count": 0, "shop_revenue": 0,
               "shop_count": 0, "analyses": 0, "new_users": 0, "reviews": 0}
    try:
        from datetime import datetime as _dt, timedelta as _td
        month_ago = (_dt.now() - _td(days=30)).strftime("%Y-%m-%d")
        with get_giso_db_conn() as conn:
            r = conn.execute(
                "SELECT COUNT(*), COALESCE(SUM(CAST(final_price AS INTEGER)),0) FROM hair_orders "
                "WHERE status IN ('priced','approved','completed') AND created_at >= ?", (month_ago,)).fetchone()
            monthly["hair_count"] = int(r[0] or 0)
            monthly["hair_revenue"] = int(r[1] or 0)
            monthly["analyses"] = int(conn.execute(
                "SELECT COUNT(*) FROM analyses WHERE created_at >= ?", (month_ago,)).fetchone()[0] or 0)
            monthly["new_users"] = int(conn.execute(
                "SELECT COUNT(*) FROM giso_web_auth WHERE created_at >= ?", (month_ago,)).fetchone()[0] or 0)
            monthly["reviews"] = int(conn.execute(
                "SELECT COUNT(*) FROM reviews WHERE created_at >= ?", (month_ago,)).fetchone()[0] or 0)
        try:
            r2 = (db.session.query(
                db.func.count(ProductOrder.id),
                db.func.coalesce(db.func.sum(ProductOrder.quantity * Product.price), 0))
                .select_from(ProductOrder)
                .join(Product, Product.id == ProductOrder.product_id)
                .filter(ProductOrder.status == "completed")
                .filter(ProductOrder.created_at >= month_ago)).first()
            monthly["shop_count"] = int(r2[0] or 0)
            monthly["shop_revenue"] = int(r2[1] or 0)
        except Exception:
            pass
    except Exception:
        pass
    return {"counts": counts, "lists": lists, "monthly": monthly}
