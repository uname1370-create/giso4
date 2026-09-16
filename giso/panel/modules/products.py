# -*- coding: utf-8 -*-
"""panel/modules/products.py — مدیریت محصولات فروشگاه."""
import logging

from giso.models import Product

logger = logging.getLogger("giso_panel_products")


def context():
    products = []
    try:
        products = Product.query.order_by(Product.id.desc()).all()
    except Exception as e:
        logger.error(f"panel products: {e}")
    return {"products": products}


def channel_context():
    """Only imported Bale posts awaiting an approve/reject decision."""
    products = []
    try:
        products = Product.query.filter_by(
            source="channel", publish_status="pending"
        ).order_by(Product.id.desc()).all()
    except Exception as e:
        logger.error("panel pending channel products: %s", e)
    return {"products": products}
