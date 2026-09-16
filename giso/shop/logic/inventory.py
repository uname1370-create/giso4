# -*- coding: utf-8 -*-
"""giso/shop/logic/inventory.py — محصولات، تصویر، موجودی و اعلان موجودی — فاز B فروشگاه."""
import logging
import os
from datetime import datetime

from flask import flash, redirect, url_for, request, abort

from giso.base import normalize_phone
from giso.config import Config
from giso.models import db, Product, StockNotify

logger = logging.getLogger("giso_shop_logic_inventory")


def _published_products():
    """فقط محصولات منتشرشده — محصولات در انتظار تأیید کانال نمایش داده نمی‌شوند."""
    return (Product.query
            .filter(Product.publish_status.in_(("published", "", None)))
            .order_by(Product.id.desc())
            .all())


def _make_slug(name: str) -> str:
    """اسلاگ تمیز برای URL محصول (فقط حروف/عدد فارسی-لاتین و خط تیره)."""
    import re
    s = re.sub(r"[^\w\u0600-\u06FF]+", "-", (name or "").strip())
    return re.sub(r"-{2,}", "-", s).strip("-")[:120]


def _save_product_image(file_storage) -> str:
    """ذخیره عکس محصول با تبدیل به WebP و ریسایز (سرعت لود + Core Web Vitals)."""
    from werkzeug.utils import secure_filename
    os.makedirs(Config.UPLOAD_FOLDER, exist_ok=True)
    fname = f"prod_{datetime.now().strftime('%Y%m%d%H%M%S%f')}.webp"
    full = os.path.join(Config.UPLOAD_FOLDER, secure_filename(fname))
    try:
        from PIL import Image
        img = Image.open(file_storage.stream).convert("RGB")
        img.thumbnail((900, 900))
        img.save(full, "WEBP", quality=82, method=6)
    except Exception as e:
        logger.warning(f"webp convert failed, fallback raw save: {e}")
        raw_ext = os.path.splitext(file_storage.filename or "")[1].lower() or ".jpg"
        if raw_ext not in (".jpg", ".jpeg", ".png", ".webp"):
            raw_ext = ".jpg"
        fname = fname.replace(".webp", raw_ext)
        full = os.path.join(Config.UPLOAD_FOLDER, secure_filename(fname))
        file_storage.stream.seek(0)
        file_storage.save(full)
    return "uploads/" + secure_filename(fname)


def _get_giso_config_safe(key, default=""):
    try:
        from giso_admin import get_giso_config
        return (get_giso_config(key, default) or default)
    except Exception:
        return default


def notify_product_back_in_stock(product_id):
    """ثبت اعلان اختصاصی برای مشترکانی که موجودی محصول را دنبال کرده‌اند."""
    try:
        product = Product.query.get(int(product_id))
        if not product or not product.in_stock:
            return 0
        rows = StockNotify.query.filter_by(product_id=int(product_id)).all()
        from giso.panel.modules.notifications import log_user_notification
        count = 0
        for row in rows:
            if log_user_notification(
                normalize_phone(row.phone), "stock_available", "محصول موجود شد",
                f"«{product.name}» دوباره موجود شده است.",
                source_type="stock_available", source_id=product.id,
            ):
                count += 1
        return count
    except Exception as exc:
        logger.exception("back-in-stock notification failed: %s", exc)
        return 0


def notify_stock(product_id):
    """ثبت درخواست اعلان موجودی فقط برای محصول منتشرشده."""
    product = Product.query.get_or_404(product_id)
    status = getattr(product, "publish_status", None) or "published"
    if status != "published":
        # مهمان/کاربر نباید بتواند درباره محصولی که هنوز منتشر نشده subscription ثبت کند.
        abort(404)
    phone = normalize_phone(request.form.get("phone", ""))
    if not phone:
        flash("شماره موبایل را وارد کنید.", "danger")
        return redirect(url_for("shop"))
    db.session.add(StockNotify(product_id=product_id, phone=phone))
    db.session.commit()
    try:
        from giso.panel.modules.notifications import safe_log as _nlog
        _nlog("shop", "stock_notify", "اعلان موجودی",
              f"«{product.name}» — {phone}", source_type="stock_notify")
    except Exception:
        pass
    flash("به محض موجود شدن، با شما تماس گرفته می‌شود.", "success")
    return redirect(url_for("shop"))


__all__ = ["_published_products", "_make_slug", "_save_product_image", "_get_giso_config_safe", "notify_stock", "notify_product_back_in_stock"]
