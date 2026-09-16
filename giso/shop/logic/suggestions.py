# -*- coding: utf-8 -*-
"""giso/shop/logic/suggestions.py — کانتکست فروشگاه + پیشنهادها + اسلات‌های UI — فاز B.

فاز A فروشگاه: سه اسلات UI سبک (همه با LIMIT محدود و بدون کش پیچیده):
  - top_sellers: پرفروش‌ترین‌ها بر اساس تعداد سفارش (quantity)
  - newest: تازه‌ترین‌ها بر اساس تاریخ ایجاد
  - back_in_stock: کالاهایی که تازه موجود شده‌اند (in_stock و مرتب‌شده بر اساس به‌روزرسانی)
"""
import logging

from flask import session

from giso.models import db, Product, ProductOrder
from giso.shop.logic.inventory import _published_products

logger = logging.getLogger("giso_shop_logic_suggestions")

PAGE_SIZE = 12  # تعداد محصول در هر صفحه فروشگاه (سرعت + سئو)

def _shop_context(buy=None, page=1, query=""):
    """ساخت کانتکست مشترک صفحه فروشگاه: محصولات، دسته‌بندی‌ها، پیشنهادی‌ها و صفحه‌بندی.

    فاز A فروشگاه: سه اسلات UI سبک (همه با LIMIT محدود و بدون کش پیچیده):
      - top_sellers: پرفروش‌ترین‌ها بر اساس تعداد سفارش (quantity)
      - newest: تازه‌ترین‌ها بر اساس تاریخ ایجاد
      - back_in_stock: کالاهایی که تازه موجود شده‌اند (in_stock و مرتب‌شده بر اساس به‌روزرسانی)
    """
    from sqlalchemy import func as _f
    query = (query or "").strip()[:100]
    if query:
        like = f"%{query}%"
        products = (Product.query
                    .filter(Product.publish_status.in_(("published", "", None)))
                    .filter((Product.name.ilike(like)) |
                            (Product.category.ilike(like)) |
                            (Product.subcategory.ilike(like)) |
                            (Product.description.ilike(like)))
                    .order_by(Product.id.desc()).all())
    else:
        products = _published_products()
    categories = []
    for p in products:
        if p.category and p.category not in categories:
            categories.append(p.category)
    suggested_ids = []
    try:
        raw = session.get("suggested_product_ids") or []
        suggested_ids = [int(x) for x in raw if str(x).strip().lstrip("-").isdigit()]
    except Exception:
        pass
    suggested = [p for p in products if p.id in suggested_ids]
    rest = [p for p in products if p.id not in suggested_ids]
    total = len(rest)
    pages = max(1, (total + PAGE_SIZE - 1) // PAGE_SIZE)
    page = max(1, min(page or 1, pages))
    start = (page - 1) * PAGE_SIZE

    # ── فاز A فروشگاه: اسلات‌های UI (سبک و محدود) ──
    top_sellers = []
    newest = []
    back_in_stock = []
    discounted = []
    try:
        discounted = [p for p in products if (p.old_price or 0) > (p.price or 0)][:4]
    except Exception as e:
        logger.debug(f"shop discounted: {e}")
    try:
        # پرفروش‌ترین‌ها: جمع تعداد سفارش هر محصول (فقط منتشرشده) — LIMIT 4
        top_ids = [r[0] for r in (
            db.session.query(Product.id)
            .join(ProductOrder, ProductOrder.product_id == Product.id)
            .filter(Product.publish_status.in_(("published", "", None)))
            .group_by(Product.id)
            .order_by(_f.coalesce(_f.sum(ProductOrder.quantity), 0).desc(), Product.id.desc())
            .limit(4).all())]
        top_map = {p.id: p for p in products if p.id in top_ids}
        top_sellers = [top_map[i] for i in top_ids if i in top_map]
    except Exception as e:
        logger.debug(f"shop top_sellers: {e}")
    try:
        # تازه‌ترین‌ها: مرتب بر اساس created_at نزولی — LIMIT 4 (بدون تکرار پرفروش‌ها)
        newest = [p for p in sorted(products, key=lambda x: (x.created_at or ""), reverse=True)
                  if p not in top_sellers][:4]
    except Exception as e:
        logger.debug(f"shop newest: {e}")
    try:
        # موجود شد: in_stock و به‌تازگی به‌روزرسانی‌شده (updated_at) — LIMIT 4
        rest_back = [p for p in products if p.in_stock and p not in top_sellers and p not in newest]
        back_in_stock = sorted(rest_back, key=lambda x: (x.updated_at or x.created_at or ""), reverse=True)[:4]
    except Exception as e:
        logger.debug(f"shop back_in_stock: {e}")

    return dict(products=rest[start:start + PAGE_SIZE], suggested=suggested,
                categories=categories, buy_product=buy,
                page=page, pages=pages, total_products=total, search_query=query,
                top_sellers=top_sellers, newest=newest, back_in_stock=back_in_stock, discounted=discounted)


__all__ = ["_shop_context", "PAGE_SIZE"]
