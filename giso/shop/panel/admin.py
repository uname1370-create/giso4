# -*- coding: utf-8 -*-
"""giso/shop/panel/admin.py — ماژول ادمین فروشگاه (فاز B).

- view های ادمین (محصولات/سفارش‌ها/کانال/گزارش) — دقیقاً همان منطق قبلی giso/shop.py
- context() صفحه «🛍 فروشگاه» در پنل ادمین: داده واقعی + لینک به ماژول‌های موجود
"""
import logging
import os
import re
from datetime import datetime

from flask import render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user

from giso.base import normalize_phone
from giso.config import Config
from giso.models import db, Product, ProductOrder, StockNotify
from giso.shop.logic.inventory import _save_product_image, _make_slug, _get_giso_config_safe
from giso.shop.logic.channel_bridge import get_publish_mode
from giso.shop.logic.checkout import _notify_admins_shop_order
from giso.money import sale_price_from_cost

logger = logging.getLogger("giso_shop_panel_admin")


def require_panel_action(action_key, redirect_endpoint="panel.dashboard"):
    """Proxy تنبل به giso.panel.authz (جلوگیری از circular import)."""
    from functools import wraps as _wraps

    def _decorator(view):
        @_wraps(view)
        def _wrapped(*args, **kwargs):
            from giso.panel.authz import require_panel_action as _real
            return _real(action_key, redirect_endpoint)(view)(*args, **kwargs)
        return _wrapped
    return _decorator



def _same_tab_url(endpoint: str, default_tab: str = "") -> str:
    """فاز جامع UX: برگشت به همان صفحه/تب پس از اکشن (به‌جای پرش به پیشخوان)."""
    url = url_for(endpoint)
    tab = (request.form.get("_back_tab") or request.args.get("tab") or "").strip() or default_tab
    if tab:
        url = url + "#pane-" + tab
    return url



def context():
    """صفحه «🛍 فروشگاه» پنل ادمین — همه داده‌ها واقعی از دیتابیس."""
    from giso.shop.panel._shared import build_admin_shop_context
    return build_admin_shop_context()

@require_panel_action("shop.product_add", "panel.products")
def admin_product_add():
    from giso.app import _check_giso_admin_access
    if _r := _check_giso_admin_access():
        return _r
    try:
        name = request.form.get("name", "").strip()
        raw_price = int(request.form.get("price", 0) or 0)
        cost_price = int(request.form.get("cost_price", 0) or 0)
        # قابلیت A: اگر قیمت فاکتور (cost_price) وارد شد، قیمت فروش خودکار = فاکتور × ۱٫۵.
        price = sale_price_from_cost(cost_price) if cost_price > 0 else raw_price
        old_price = int(request.form.get("old_price", 0) or 0)
        category = request.form.get("category", "hair").strip()
        description = request.form.get("description", "").strip()
        in_stock = request.form.get("in_stock", "1") == "1"
        photo_path = ""
        file = request.files.get("image")
        if file and file.filename:
            ext = os.path.splitext(file.filename or "")[1].lower()
            if ext in [".jpg", ".jpeg", ".png", ".webp"]:
                photo_path = _save_product_image(file)
        p = Product(
            name=name,
            price=price,
            cost_price=cost_price,
            old_price=old_price,
            category=category,
            description=description,
            in_stock=in_stock,
            image_path=photo_path,
            slug=_make_slug(name),
            source="site",
            publish_status="published",
        )
        db.session.add(p)
        db.session.commit()
        flash("محصول جدید با موفقیت اضافه شد.", "success")
    except Exception:
        try:
            db.session.rollback()
        except Exception:
            pass
        flash("خطا در افزودن محصول.", "danger")
    return redirect(_same_tab_url("panel.products", "products"))

@require_panel_action("shop.product_edit", "panel.products")
def admin_product_edit(product_id):
    from giso.app import _check_giso_admin_access
    if _r := _check_giso_admin_access():
        return _r
    try:
        p = Product.query.get_or_404(product_id)
        p.name = request.form.get("name", p.name).strip()
        _cost_raw = (request.form.get("cost_price", "") or "").strip()
        _cost_price = int(_cost_raw) if _cost_raw.lstrip("-").isdigit() else int(getattr(p, "cost_price", 0) or 0)
        p.cost_price = max(0, _cost_price)
        # قابلیت A: فاکتور شرعی — اگر فاکتور وارد شد، قیمت فروش خودکار محاسبه می‌شود.
        if _cost_raw and _cost_price > 0:
            p.price = sale_price_from_cost(_cost_price)
        else:
            p.price = int(request.form.get("price", p.price) or 0)
        p.old_price = int(request.form.get("old_price", p.old_price or 0) or 0)
        p.category = request.form.get("category", p.category).strip()
        p.description = request.form.get("description", p.description).strip()
        _sub = request.form.get("subcategory")
        if _sub is not None:
            p.subcategory = _sub.strip()
        p.in_stock = request.form.get("in_stock", "1") == "1"
        # تعویض/افزودن عکس محصول (سوپرادمین در سایت)
        file = request.files.get("image")
        if file and file.filename:
            ext = os.path.splitext(file.filename or "")[1].lower()
            if ext in [".jpg", ".jpeg", ".png", ".webp"]:
                saved = _save_product_image(file)
                if saved:
                    p.image_path = saved
        p.updated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        db.session.commit()
        flash("اطلاعات محصول ویرایش شد.", "success")
    except Exception:
        try:
            db.session.rollback()
        except Exception:
            pass
        flash("خطا در ویرایش محصول.", "danger")
    return redirect(_same_tab_url("panel.products", "products"))

@require_panel_action("shop.product_stock", "panel.products")
def admin_product_toggle_stock(product_id):
    from giso.app import _check_giso_admin_access
    if _r := _check_giso_admin_access():
        return _r
    try:
        p = Product.query.get_or_404(product_id)
        was_in_stock = bool(p.in_stock)
        p.in_stock = not was_in_stock
        db.session.commit()
        if not was_in_stock and p.in_stock:
            try:
                from giso.shop.logic.inventory import notify_product_back_in_stock
                notify_product_back_in_stock(p.id)
            except Exception as exc:
                logger.exception("back-in-stock hook failed: %s", exc)
        flash(f"وضعیت موجودی «{p.name}» تغییر کرد.", "success")
    except Exception:
        try:
            db.session.rollback()
        except Exception:
            pass
        flash("خطا در تغییر موجودی محصول.", "danger")
    return redirect(_same_tab_url("panel.products", "products"))

@require_panel_action("shop.product_delete", "panel.products")
def admin_product_delete(product_id):
    from giso.app import _check_giso_admin_access
    if _r := _check_giso_admin_access():
        return _r
    try:
        p = Product.query.get_or_404(product_id)
        db.session.delete(p)
        db.session.commit()
        flash("محصول با موفقیت حذف شد.", "success")
    except Exception:
        try:
            db.session.rollback()
        except Exception:
            pass
        flash("خطا در حذف محصول.", "danger")
    return redirect(_same_tab_url("panel.products", "products"))

@require_panel_action("shop.order_status", "panel.shop_orders")
def admin_shop_order_status(order_id):
    from giso.app import _check_giso_admin_access
    if _r := _check_giso_admin_access():
        return _r
    try:
        o = ProductOrder.query.get_or_404(order_id)
        new_status = request.form.get("status", "pending").strip()
        # فیکس: UI (کشویی پنل + ربات) همه وضعیت‌های واقعی را می‌فرستد؛ قبلاً
        # shipped/delivered/rejected اینجا رد می‌شدند («وضعیت نامعتبر») و
        # عملاً تغییر وضعیت ارسال/تحویل/رد از پنل سایت کار نمی‌کرد.
        if new_status in ("pending", "approved", "shipped", "delivered",
                          "rejected", "completed", "cancelled"):
            o.status = new_status
            db.session.commit()
            from giso.shop.logic import orders as _ord
            fa = _ord.status_fa(new_status)
            flash(f"وضعیت سفارش #{o.id} به «{fa}» تغییر کرد.", "success")
            # اطلاع خودکار به کاربر (سایت/ربات/ویجت از یک منبع)
            try:
                _ord.notify_user_product_order(
                    o.phone or "",
                    f"🔔 <b>به‌روزرسانی سفارش فروشگاه #{o.id}</b>\n"
                    f"📌 وضعیت جدید: {fa}\n"
                    f"می‌توانید جزئیات را در «فروشگاه من → سفارش‌های من» ببینید 🌸"
                )
            except Exception:
                pass
        else:
            flash("وضعیت نامعتبر است.", "warning")
    except Exception:
        try:
            db.session.rollback()
        except Exception:
            pass
        flash("خطا در تغییر وضعیت سفارش.", "danger")
    return redirect(_same_tab_url("panel.shop_orders", "list"))

@require_panel_action("shop.channel_config", "panel.channel")
def admin_config_channel():
    from giso.app import _check_giso_admin_access
    if _r := _check_giso_admin_access():
        return _r
    try:
        from giso_admin import set_giso_config
        # فاز جامع UX: نرمال‌سازی + اعتبارسنجی با پیام خطای واقعی
        ch_id = (request.form.get("channel_id", "") or "").strip().lstrip("@")
        if not ch_id:
            flash("⚠️ آیدی کانال خالی است — آیدی کانال را بدون @ وارد کنید (مثلاً giso_shop_channel).", "warning")
            return redirect(_same_tab_url("panel.channel", "channel"))
        if not re.match(r"^[A-Za-z][A-Za-z0-9_]{2,64}$", ch_id):
            flash("⚠️ آیدی نامعتبر است — فقط حروف انگلیسی/عدد/زیرخط (بدون فاصله و @)، حداقل ۳ کاراکتر.", "danger")
            return redirect(_same_tab_url("panel.channel", "channel"))
        set_giso_config("bale_channel_id", ch_id)
        flash(f"✅ آیدی کانال «{ch_id}» با موفقیت ذخیره شد (bot.db).", "success")
    except Exception as e:
        logger.error(f"admin_config_channel: {e}")
        flash(f"❌ خطای واقعی در ذخیره آیدی کانال: {e}", "danger")
    return redirect(_same_tab_url("panel.channel", "channel"))

@require_panel_action("shop.product_publish", "panel.products")
def admin_product_publish(product_id):
    from giso.app import _check_giso_admin_access
    if _r := _check_giso_admin_access():
        return _r
    try:
        p = Product.query.get_or_404(product_id)
        from giso.panel.permissions import current_role_and_perms
        role, _perms, _bid = current_role_and_perms()
        if role != "super" and not (
            getattr(p, "source", "") == "channel" and p.publish_status == "pending"
        ):
            flash("⛔ ادمین عادی فقط می‌تواند پست واردشده و در انتظار کانال را تأیید کند.", "warning")
            return redirect(_same_tab_url("panel.products", "list"))
        if not p.price:
            flash(f"⚠️ قیمت «{p.name}» صفر است — اول قیمت را ویرایش کنید بعد منتشر کنید.", "warning")
            return redirect(_same_tab_url("panel.products", "products"))
        try:
            from giso.channel_importer import PRICE_MISSING_NOTE
            if PRICE_MISSING_NOTE in (p.description or ""):
                p.description = (p.description or "").replace(PRICE_MISSING_NOTE, "").strip()
        except Exception:
            pass
        p.publish_status = "published"
        p.updated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        db.session.commit()
        if getattr(p, "source", "") == "channel":
            try:
                from giso.panel.modules.notifications import safe_log as _nlog
                _nlog("channel", "product_approved", "تأیید محصول کانال",
                      f"«{p.name}» منتشر شد.",
                      source_type="channel_published", source_id=p.id)
            except Exception:
                pass
        flash(f"«{p.name}» در فروشگاه منتشر شد. ✅", "success")
    except Exception:
        try:
            db.session.rollback()
        except Exception:
            pass
        flash("خطا در انتشار محصول.", "danger")
    return redirect(_same_tab_url("panel.products", "products"))


@require_panel_action("shop.product_reject", "panel.products")
def admin_product_reject(product_id):
    """Reject an imported channel post without exposing generic deletion."""
    from giso.app import _check_giso_admin_access
    if _r := _check_giso_admin_access():
        return _r
    try:
        p = Product.query.get_or_404(product_id)
        from giso.panel.permissions import current_role_and_perms
        role, _perms, _bid = current_role_and_perms()
        if role != "super" and not (
            getattr(p, "source", "") == "channel" and p.publish_status == "pending"
        ):
            flash("⛔ این مورد یک پست کانالِ در انتظار نیست.", "warning")
            return redirect(_same_tab_url("panel.products", "list"))
        p.publish_status = "rejected"
        p.updated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        db.session.commit()
        flash(f"پست کانال «{p.name}» رد شد.", "success")
    except Exception:
        try:
            db.session.rollback()
        except Exception:
            pass
        flash("خطا در رد پست کانال.", "danger")
    return redirect(_same_tab_url("panel.products", "list"))


@require_panel_action("shop.publish_mode", "panel.channel")
def admin_publish_mode():
    from giso.app import _check_giso_admin_access
    if _r := _check_giso_admin_access():
        return _r
    try:
        from giso_admin import set_giso_config
        mode = (request.form.get("mode", "review") or "review").strip().lower()
        if mode not in ("review", "auto"):
            mode = "review"
        set_giso_config("shop_publish_mode", mode)
        if mode == "auto":
            flash("🟢 حالت انتشار: خودکار فعال شد — پست‌های کانال بلافاصله در فروشگاه منتشر می‌شوند.", "success")
        else:
            flash("🔶 حالت انتشار: با تأیید فعال شد — هر پست کانال ابتدا در ربات تأیید می‌شود.", "success")
    except Exception:
        flash("خطا در ذخیره حالت انتشار.", "danger")
    return redirect(_same_tab_url("panel.channel", "channel"))

@require_panel_action("shop.channel_config", "panel.channel")
def admin_channel_test():
    """تست زنده اتصال کانال: خواندن getChat از API بله با توکن موجود."""
    from giso.app import _check_giso_admin_access
    if _r := _check_giso_admin_access():
        return _r
    ch = _get_giso_config_safe("bale_channel_id", "")
    if not ch:
        flash("📢 ابتدا آیدی کانال را ذخیره کنید، بعد تست کنید.", "warning")
        return redirect(_same_tab_url("panel.channel", "channel"))
    try:
        from giso.base import _token_from_env, _token_from_db
        import requests as _req
        token = _token_from_env() or _token_from_db() or ""
        if not token:
            flash("⚠️ توکن ربات پیدا نشد (env/db خالی است).", "danger")
            return redirect(_same_tab_url("panel.channel", "channel"))
        chat_ref = ch if ch.lstrip("-").isdigit() else (ch if ch.startswith("@") else "@" + ch)
        resp = _req.get(
            f"https://tapi.bale.ai/bot{token}/getChat",
            params={"chat_id": chat_ref}, timeout=10,
        ).json()
        mode = get_publish_mode()
        mode_txt = "🟢 خودکار" if mode == "auto" else "🔶 با تأیید"
        if resp.get("ok"):
            title = resp.get("result", {}).get("title") or chat_ref
            flash(f"✅ اتصال OK — کانال «{title}» توسط ربات دیده می‌شود. حالت انتشار فعلی: {mode_txt}. هر پست جدید ایمپورت می‌شود.", "success")
        else:
            err = resp.get("description", "خطای نامشخص")
            flash(f"⚠️ ربات به کانال «{chat_ref}» دسترسی ندارد ({err}). ربات را ادمین کانال کنید و دوباره تست کنید.", "danger")
    except Exception as e:
        flash(f"⚠️ خطا در تست اتصال کانال: {e}", "danger")
    return redirect(_same_tab_url("panel.channel", "channel"))

@require_panel_action("shop.stats", "panel.dashboard")
def admin_shop_stats():
    """📊 گزارش فروش فروشگاه: سفارش‌ها، درآمد، پرفروش‌ترین‌ها، روند ۷ روز اخیر."""
    from giso.app import _check_giso_admin_access
    if _r := _check_giso_admin_access():
        return _r
    from sqlalchemy import func
    total_orders = ProductOrder.query.count()
    by_status = dict(
        ProductOrder.query.with_entities(ProductOrder.status, func.count())
        .group_by(ProductOrder.status).all()
    )
    revenue = (db.session.query(func.coalesce(func.sum(ProductOrder.quantity * Product.price), 0))
               .select_from(ProductOrder)
               .join(Product, Product.id == ProductOrder.product_id)
               .filter(ProductOrder.status == "completed").scalar()) or 0
    top_rows = (db.session.query(Product.id, Product.name,
                                 func.coalesce(func.sum(ProductOrder.quantity), 0).label("q"),
                                 func.count(ProductOrder.id).label("n"))
                .join(ProductOrder, ProductOrder.product_id == Product.id)
                .group_by(Product.id).order_by(func.sum(ProductOrder.quantity).desc())
                .limit(5).all())
    daily = (ProductOrder.query
             .with_entities(func.substr(ProductOrder.created_at, 1, 10), func.count())
             .group_by(func.substr(ProductOrder.created_at, 1, 10))
             .order_by(func.substr(ProductOrder.created_at, 1, 10).desc())
             .limit(7).all())
    pending_channel = (Product.query
                       .filter(Product.publish_status == "pending")
                       .count())
    stats = dict(
        total_orders=total_orders,
        by_status=by_status,
        revenue=int(revenue),
        top=[dict(id=r[0], name=r[1], q=int(r[2]), n=int(r[3])) for r in top_rows],
        daily=[dict(date=str(d[0]), n=int(d[1])) for d in daily],
        pending_channel=pending_channel,
        products=Product.query.count(),
        stock_notifies=StockNotify.query.count(),
    )
    # رفع باگ قدیمی: پوشهٔ قالب‌های پنل فروشگاه باید در loader ثبت شود (مثل بقیهٔ مسیرهای shop)
    from flask import current_app as _ca
    from giso.shop.routes import ensure_shop_template_paths
    ensure_shop_template_paths(_ca)
    return render_template("admin_shop_stats.html", **stats)
