# -*- coding: utf-8 -*-
"""giso/shop/routes.py — route های سایت فروشگاه (فاز B).

همه route ها با **همان مسیر و endpoint قبلی** ثبت می‌شوند (fallback قدیمی shop.py هم intact).
view های ادمین در giso/shop/panel/admin.py هستند و منطق خالص در giso/shop/logic/.
"""
import logging
import os
import secrets
from pathlib import Path

try:
    from flask import (Blueprint, render_template, request, redirect, url_for,
                       flash, abort, Response, session)
    from flask_login import login_required, current_user
    from werkzeug.utils import secure_filename
except ImportError:
    class Blueprint:
        def __init__(self, *a, **kw):
            pass
    def login_required(fn):
        return fn
    current_user = None

from giso.base import get_giso_db_conn, normalize_phone
from giso.security import audit_event
from giso.config import Config
from giso.models import db, Product, ProductOrder, StockNotify
from giso.shop.logic.cart import _get_cart, _save_cart, _cart_items, cart_count  # noqa: F401
from giso.shop.logic.checkout import _notify_admins_shop_order, _send_super_order_photo
from giso.shop.logic import orders as _orders
from giso.shop.logic.inventory import (_published_products, _make_slug, _save_product_image,
    _get_giso_config_safe, notify_stock)
from giso.shop.logic.suggestions import _shop_context, PAGE_SIZE
from giso.shop.logic.channel_bridge import get_publish_mode
from giso.shop.panel.admin import (
    admin_product_add, admin_product_edit, admin_product_toggle_stock, admin_product_delete,
    admin_shop_order_status, admin_config_channel, admin_product_publish, admin_product_reject,
    admin_publish_mode, admin_channel_test, admin_shop_stats,
)

logger = logging.getLogger("giso_shop_routes")


def _new_tracking_code():
    return "GSO-" + secrets.token_hex(4).upper()

from flask import Blueprint as _BP
shop_routes = _BP("shop", __name__)
shop_mod_static = _BP("shop_mod", __name__, static_folder="static", static_url_path="/shop-static")


def ensure_shop_template_paths(app):
    try:
        if getattr(app, "config", {}).get("_SHOP_TPL_READY"):
            return
        from jinja2 import FileSystemLoader, ChoiceLoader
        base = Path(__file__).resolve().parent
        dirs = [str(base / "templates"), str(base / "panel" / "templates")]
        loader = getattr(app, "jinja_loader", None)
        if isinstance(loader, FileSystemLoader):
            for d in dirs:
                if os.path.isdir(d) and d not in loader.searchpath:
                    loader.searchpath.append(d)
            app.config["_SHOP_TPL_READY"] = True
            return
        if isinstance(loader, ChoiceLoader):
            targets = list(loader.loaders)
            for d in dirs:
                if not os.path.isdir(d):
                    continue
                if any(isinstance(t, FileSystemLoader) and d in t.searchpath for t in targets):
                    continue
                loader.loaders.insert(0, FileSystemLoader(d))
            app.config["_SHOP_TPL_READY"] = True
    except Exception as e:
        logger.warning(f"ensure_shop_template_paths: {e}")


def _shop_render(template, **ctx):
    # One privacy-minimal source for all quick-buy/cart forms. POST values in the
    # template take precedence so validation errors never erase user corrections.
    if "profile_defaults" not in ctx:
        try:
            from giso.user_profile_service import safe_form_defaults
            ctx["profile_defaults"] = safe_form_defaults(current_user)
        except Exception:
            ctx["profile_defaults"] = {"full_name": "", "phone": "", "city": "", "region": "", "contact_time": ""}
    try:
        from flask import current_app
        ensure_shop_template_paths(current_app._get_current_object())
    except Exception:
        pass
    if "drawer_items" not in ctx:
        try:
            _cart = _get_cart()
            _items, _total = _cart_items(_cart)
            ctx["drawer_items"] = _items
            ctx["drawer_total"] = _total
            ctx["drawer_count"] = cart_count(_cart)
        except Exception:
            ctx["drawer_items"] = []
            ctx["drawer_total"] = 0
            ctx["drawer_count"] = 0
    if "contact_days" not in ctx:
        try:
            from giso.shop.logic.checkout import CONTACT_DAYS, CONTACT_TIME_SLOTS
            ctx["contact_days"] = list(CONTACT_DAYS)
            ctx["contact_times"] = list(CONTACT_TIME_SLOTS)
        except Exception:
            ctx["contact_days"] = []
            ctx["contact_times"] = []
    return render_template(template, **ctx)


def cart_count_api():
    try:
        from flask import jsonify
        _cart = _get_cart()
        return jsonify({"count": cart_count(_cart)})
    except Exception:
        return jsonify({"count": 0})


def shop():
    try:
        page = int(request.args.get("page", 1) or 1)
    except (TypeError, ValueError):
        page = 1
    query = (request.args.get("q") or "").strip()
    ctx = _shop_context(page=page, query=query)
    # SEO: جست‌وجو (q) و صفحه‌بندی عمیق (page>1) ریسک محتوای تکراری دارند و
    # ایندکس نمی‌شوند؛ خودِ /shop و فیلترهای معنادار indexable می‌مانند.
    ctx["noindex"] = bool(query) or page > 1
    try:
        ids = [int(x) for x in (session.get("shop_last_orders") or [])]
        ctx["widget_orders"] = _orders.get_orders_for_ids(ids)
        ctx["just_ordered"] = bool(ids)
    except Exception:
        ctx["widget_orders"] = []
        ctx["just_ordered"] = False
    return _shop_render("shop.html", **ctx)


def _assert_product_published(product):
    status = getattr(product, "publish_status", None) or "published"
    if status != "published":
        try:
            from giso.app import _check_giso_admin_access
            denied = _check_giso_admin_access()
        except Exception:
            denied = True
        if denied:
            return abort(404)
    return None


def buy_product(product_id):
    product = Product.query.get_or_404(product_id)
    denied = _assert_product_published(product)
    if denied is not None:
        return denied
    if request.method == "POST":
        if not getattr(current_user, "is_authenticated", False):
            flash("برای خرید، ابتدا وارد حساب‌تان شوید یا ثبت‌نام کنید.", "warning")
            return redirect(url_for("login", next=request.path))
        name = request.form.get("customer_name", "").strip()
        phone = normalize_phone(request.form.get("phone", ""))
        address = request.form.get("address", "").strip()
        courier_note = request.form.get("courier_note", "").strip()
        contact_day = request.form.get("contact_day", "").strip()
        contact_time = request.form.get("contact_time", "").strip()
        contact_slot = " — ".join(x for x in (contact_day, contact_time) if x)
        if not name or not phone or not address:
            flash("لطفاً همه فیلدها را تکمیل کنید.", "danger")
            return _shop_render("shop.html", **_shop_context(buy=product))
        # خرید فوری نیز از همان هسته اتمیک سبد عبور می‌کند تا سفارش، checkout و
        # فاکتور COD با snapshot قیمت در یک transaction ساخته شوند.
        product_name = product.name
        product_description = product.description or ""
        try:
            db.session.rollback()
        except Exception:
            pass
        try:
            from giso.wallet import create_shop_checkout_atomic, WalletCheckoutError
            checkout = create_shop_checkout_atomic(
                current_user.id,
                [{"product_id": product_id, "quantity": 1, "tracking_code": _new_tracking_code()}],
                {"name": name, "phone": phone, "address": address,
                 "courier_note": courier_note, "delivery_time": contact_slot},
                pay_with_wallet=False,
            )
        except WalletCheckoutError as exc:
            flash(str(exc), "danger")
            return _shop_render("shop.html", **_shop_context(buy=product))
        order_id = checkout["order_ids"][0]
        total = checkout["gross_amount"]
        try:
            from giso.wallet import complete_mission
            complete_mission(current_user.id, "first_purchase", event_key=f"checkout:{checkout['checkout_id']}")
        except Exception as exc:
            logger.warning("direct first-purchase mission failed: %s", exc)
        from giso.money import format_toman
        try:
            note_txt = f"\n📝 یادداشت خریدار: {courier_note}" if courier_note else ""
            time_txt = f"\n🕒 تماس/تحویل: {contact_slot}" if contact_slot else ""
            _notify_admins_shop_order(
                f"🛒 <b>سفارش جدید فروشگاه #{order_id}</b>\n"
                f"🏷 {product_name} × ۱\n"
                f"💰 {format_toman(total)}\n"
                f"👤 {name}\n📱 {phone}\n"
                f"📍 {address}\n"
                f"💳 کیف پول: {format_toman(0)}\n"
                f"💵 قابل پرداخت به پیک: {format_toman(total)}\n"
                f"⏱ وضعیت: در حال بررسی{time_txt}{note_txt}",
                order_ids=[order_id],
            )
            _send_super_order_photo(
                product,
                f"🛒 <b>سفارش جدید فروشگاه #{order_id}</b>\n"
                f"━━━━━━━━━━━━━━\n"
                f"🏷 محصول: <b>{product_name}</b>\n"
                + (f"📄 توضیحات: {product_description[:180]}\n" if product_description.strip() else "")
                + f"🔢 تعداد: ۱\n"
                f"💰 مبلغ کل فاکتور: {format_toman(total)}\n"
                f"💳 پرداخت کیف پول: {format_toman(0)}\n"
                f"💵 قابل پرداخت به پیک: {format_toman(total)}\n"
                f"━━━━━━━━━━━━━━\n"
                f"👤 خریدار: {name}\n"
                f"📱 تماس: {phone}\n"
                f"📍 آدرس: {address}\n"
                + (f"🕒 روز/ساعت تماس: {contact_slot}\n" if contact_slot else "")
                + (f"📝 یادداشت خریدار: {courier_note}\n" if courier_note else "")
                + "⏱ وضعیت: در حال بررسی",
                order_ids=[order_id],
            )
        except Exception:
            pass
        try:
            _orders.notify_user_product_order(
                phone,
                f"🛍 <b>سفارش شما ثبت شد ✅</b>\n"
                f"🏷 {product_name} × ۱ — {format_toman(total)}\n"
                f"📌 وضعیت: در حال بررسی\n"
                f"💵 پرداخت به پیک: {format_toman(total)}\n"
                + (f"🕒 در روز/ساعت انتخابی ({contact_slot}) برای هماهنگی ارسال تماس می‌گیریم.\n" if contact_slot else "")
                + "\nفاکتور رسمی در بخش سفارش‌های من در دسترس است 🌸"
            )
        except Exception:
            pass
        try:
            session["shop_last_orders"] = [order_id]
            session["shop_last_checkout"] = checkout["checkout_id"]
            session.modified = True
        except Exception:
            pass
        flash("سفارش شما با موفقیت ثبت شد ✅ کد پیگیری در ادامه نمایش داده شده است.", "success")
        return redirect(url_for("order_success"))
    return _shop_render("shop.html", **_shop_context(buy=product))


def cart_add(product_id):
    p = Product.query.get_or_404(product_id)
    if not p.in_stock:
        flash(f"«{p.name}» فعلاً ناموجود است؛ می‌توانید اطلاع‌رسانی فعال کنید.", "warning")
        return redirect(request.referrer or url_for("shop"))
    if _assert_product_published(p) is not None:
        return abort(404)
    cart = _get_cart()
    cart[str(product_id)] = cart.get(str(product_id), 0) + 1
    _save_cart(cart)
    flash(f"«{p.name}» به سبد اضافه شد.", "success")
    return redirect(request.referrer or url_for("shop"))


def cart_remove(product_id):
    cart = _get_cart()
    if str(product_id) in cart:
        cart.pop(str(product_id))
        _save_cart(cart)
        flash("آیتم از سبد حذف شد.", "info")
    return redirect(url_for("cart_page"))


def cart_update(product_id):
    try:
        qty = int(request.form.get("qty", 1) or 1)
    except (TypeError, ValueError):
        qty = 1
    cart = _get_cart()
    if qty <= 0:
        cart.pop(str(product_id), None)
    else:
        p = Product.query.get(product_id)
        if not p or _assert_product_published(p) is not None:
            return abort(404)
        cart[str(product_id)] = min(qty, 99)
    _save_cart(cart)
    return redirect(url_for("cart_page"))


def cart_page():
    cart = _get_cart()
    items, total = _cart_items(cart)
    wallet_summary = {"cash": 0, "spend": 0, "usable": 0, "settleable": 0}
    if getattr(current_user, "is_authenticated", False):
        try:
            from giso.wallet import get_wallet_balances
            wallet_summary = get_wallet_balances(current_user.id)
        except Exception as exc:
            logger.warning("cart wallet summary failed: %s", exc)
    wallet_summary["usable_for_cart"] = min(int(wallet_summary.get("usable", 0)), int(total or 0))
    wallet_summary["remaining_cod"] = max(0, int(total or 0) - wallet_summary["usable_for_cart"])
    return _shop_render("cart.html", items=items, total=total, wallet_summary=wallet_summary)


def cart_checkout():
    cart = _get_cart()
    items, _display_total = _cart_items(cart)
    if not items:
        flash("سبد خرید شما خالی است.", "warning")
        return redirect(url_for("shop"))
    if not getattr(current_user, "is_authenticated", False):
        flash("برای ثبت سفارش، ابتدا وارد حساب‌تان شوید یا ثبت‌نام کنید.", "warning")
        _back = (request.referrer or "").split("?")[0]
        _next = _back if (_back.startswith("/") and not _back.startswith("//")) else url_for("cart_page")
        return redirect(url_for("login", next=_next))

    # اعتبارسنجی اطلاعات مشتری باید پیش از هر عملیات مالی انجام شود.
    name = request.form.get("customer_name", "").strip()
    phone = normalize_phone(request.form.get("phone", ""))
    address = request.form.get("address", "").strip()
    courier_note = request.form.get("courier_note", "").strip()
    contact_day = request.form.get("contact_day", "").strip()
    contact_time = request.form.get("contact_time", "").strip()
    contact_slot = " — ".join(x for x in (contact_day, contact_time) if x)
    if not name or not phone or not address:
        flash("لطفاً نام، شماره تماس و آدرس را تکمیل کنید.", "danger")
        return redirect(url_for("cart_page"))

    atomic_items = []
    shared_tracking = _new_tracking_code()
    for item in items:
        product = item.get("product")
        if not product or _assert_product_published(product) is not None:
            flash("یکی از محصولات این سبد دیگر برای خرید عمومی منتشر نیست.", "warning")
            return redirect(url_for("cart_page"))
        atomic_items.append({
            "product_id": product.id,
            "quantity": item["qty"],
            "tracking_code": shared_tracking,
        })

    # خواندن‌های ORM بالا ممکن است transaction خواندن باز کرده باشند؛ قبل از
    # BEGIN IMMEDIATE سرویس مرکزی آن را آزاد می‌کنیم. هیچ writeای تا اینجا نیست.
    try:
        db.session.rollback()
    except Exception:
        pass
    try:
        from giso.wallet import create_shop_checkout_atomic, WalletCheckoutError
        checkout = create_shop_checkout_atomic(
            current_user.id,
            atomic_items,
            {
                "name": name,
                "phone": phone,
                "address": address,
                "courier_note": courier_note,
                "delivery_time": contact_slot,
            },
            pay_with_wallet=request.form.get("pay_with_wallet") == "1",
            discount_code=request.form.get("discount_code", "").strip(),
        )
    except WalletCheckoutError as exc:
        flash(str(exc), "danger")
        return redirect(url_for("cart_page"))
    except Exception as exc:
        logger.exception("checkout failed before commit: %s", exc)
        flash("ثبت سفارش ناموفق بود؛ هیچ مبلغی از کیف پول کسر نشد.", "danger")
        return redirect(url_for("cart_page"))

    placed_ids = checkout["order_ids"]
    total = checkout["gross_amount"]
    discount_amount = checkout["discount_amount"]
    wallet_used = checkout["wallet_used"]
    cod_amount = checkout["cod_amount"]
    _save_cart({})

    # مأموریت idempotent است؛ retry یا checkout بعدی پاداش را دوباره نمی‌دهد.
    try:
        from giso.wallet import complete_mission
        complete_mission(current_user.id, "first_purchase", event_key=f"checkout:{checkout['checkout_id']}")
        complete_mission(current_user.id, "shop_order", event_key=f"shop-order:{checkout['checkout_id']}")
    except Exception as exc:
        logger.warning("cart-checkout mission failed: %s", exc)

    from giso.money import format_toman
    payment_lines = (
        f"💳 پرداخت‌شده از کیف پول: {format_toman(wallet_used)}\n"
        f"💵 قابل پرداخت به پیک: {format_toman(cod_amount)}"
    )
    try:
        items_txt = "\n".join(
            f"  • {it['name']} × {it['quantity']} ({format_toman(it['line_total'])})"
            for it in checkout["items"][:6]
        )
        note_txt = f"\n📝 یادداشت خریدار: {courier_note}" if courier_note else ""
        time_txt = f"\n🕒 تماس/تحویل: {contact_slot}" if contact_slot else ""
        discount_txt = f"\n🏷 تخفیف: {format_toman(discount_amount)}" if discount_amount else ""
        _notify_admins_shop_order(
            f"🧺 <b>سفارش سبد جدید فروشگاه — checkout #{checkout['checkout_id']}</b>\n{items_txt}\n"
            f"💰 مبلغ کل فاکتور: {format_toman(total)}{discount_txt}\n👤 {name}\n📱 {phone}\n"
            f"📍 {address}\n{payment_lines}\n"
            f"⏱ وضعیت: در حال بررسی{time_txt}{note_txt}",
            order_ids=placed_ids,
        )
        _photo_product = next(
            (it["product"] for it in items if getattr(it["product"], "image_path", None)),
            items[0]["product"] if items else None,
        )
        if _photo_product:
            _send_super_order_photo(
                _photo_product,
                f"🧺 <b>سفارش سبد جدید فروشگاه</b>\n"
                f"━━━━━━━━━━━━━━\n{items_txt}\n"
                f"💰 مبلغ کل فاکتور: {format_toman(total)} ({len(placed_ids)} قلم)\n"
                + (f"🏷 تخفیف: {format_toman(discount_amount)}\n" if discount_amount else "")
                + f"{payment_lines}\n━━━━━━━━━━━━━━\n"
                f"👤 خریدار: {name}\n📱 تماس: {phone}\n📍 آدرس: {address}\n"
                + (f"🕒 روز/ساعت تماس: {contact_slot}\n" if contact_slot else "")
                + (f"📝 یادداشت خریدار: {courier_note}\n" if courier_note else "")
                + "⏱ وضعیت: در حال بررسی",
                order_ids=placed_ids,
            )
    except Exception:
        pass
    try:
        _orders.notify_user_product_order(
            phone,
            f"🛍 <b>سفارش شما ثبت شد ✅</b>\n"
            f"🧾 یک سفارش با {len(placed_ids)} قلم — مبلغ کل {format_toman(total)}\n"
            + (f"🏷 تخفیف: {format_toman(discount_amount)}\n" if discount_amount else "")
            + f"💳 پرداخت‌شده از کیف پول: {format_toman(wallet_used)}\n"
            f"💵 قابل پرداخت به پیک: {format_toman(cod_amount)}\n"
            f"📌 وضعیت: در حال بررسی\n"
            + (f"🕒 در روز/ساعت انتخابی ({contact_slot}) برای هماهنگی ارسال تماس می‌گیریم.\n" if contact_slot else "")
            + "\nفاکتور رسمی و مسیر پیگیری در بخش سفارش‌های من در دسترس است 🌸"
        )
    except Exception:
        pass
    try:
        session["shop_last_orders"] = placed_ids
        session["shop_last_checkout"] = checkout["checkout_id"]
        session.modified = True
    except Exception:
        pass
    detail = f" ({format_toman(wallet_used)} از کیف پول و {format_toman(cod_amount)} قابل پرداخت به پیک)" if wallet_used else ""
    flash(f"سفارش شما با موفقیت ثبت شد ✅{detail}", "success")
    return redirect(url_for("order_success"))


def order_success():
    if not getattr(current_user, "is_authenticated", False):
        return redirect(url_for("login", next=request.path))
    try:
        ids = [int(x) for x in (session.get("shop_last_orders") or [])]
    except Exception:
        ids = []
    orders = _orders.get_orders_for_ids(ids, user_id=getattr(current_user, "id", None))
    total = sum(int(o.get("price") or 0) * int(o.get("quantity") or 1) for o in orders)
    invoice = None
    if orders:
        try:
            from giso.shop.logic.invoices import get_invoice_for_order
            payload = get_invoice_for_order(int(orders[0]["id"]))
            invoice = payload["invoice"] if payload else None
            if invoice:
                total = int(invoice.get("gross_amount") or total)
        except Exception as exc:
            logger.warning("order-success invoice read failed: %s", exc)
    return _shop_render("order_success.html", orders=orders, total=total, invoice=invoice)


def order_invoice(order_id):
    """نمایش فاکتور snapshot فقط برای مالک سفارش یا سوپرادمین مالی."""
    if not getattr(current_user, "is_authenticated", False):
        return redirect(url_for("login", next=request.path))
    # مالکیت پیش از backfill بررسی می‌شود تا کاربر نامرتبط نتواند با حدس شناسه
    # برای سفارش دیگران نوشتن دیتابیس ایجاد کند.
    with get_giso_db_conn() as conn:
        order_owner = conn.execute(
            "SELECT user_id,phone FROM product_orders WHERE id=?", (int(order_id),)
        ).fetchone()
    if not order_owner:
        return abort(404)
    owner = (
        int(order_owner["user_id"] or 0) == int(getattr(current_user, "id", 0) or 0)
        or normalize_phone(order_owner["phone"] or "")
        == normalize_phone(getattr(current_user, "phone", "") or "")
    )
    if not owner:
        from giso.wallet import is_financial_superadmin
        if not is_financial_superadmin():
            return abort(403)
    from giso.shop.logic.invoices import get_invoice_for_order, get_invoice_seller
    payload = get_invoice_for_order(order_id)
    if not payload:
        return abort(404)
    return _shop_render(
        "invoice.html", invoice=payload["invoice"], invoice_items=payload["items"],
        invoice_orders=payload["orders"], invoice_seller=get_invoice_seller(),
    )


def order_time():
    if not getattr(current_user, "is_authenticated", False):
        flash("برای ادامه، ابتدا وارد حساب‌تان شوید.", "warning")
        return redirect(url_for("login", next=request.path))
    try:
        ids = [int(x) for x in (session.get("shop_last_orders") or [])]
    except Exception:
        ids = []
    if not ids:
        flash("سفارشی برای زمان‌بندی یافت نشد.", "warning")
        return redirect(url_for("shop"))
    owned_orders = _orders.get_orders_for_ids(ids, user_id=getattr(current_user, "id", None))
    if len(owned_orders) != len(ids):
        audit_event("order_time_ownership_denied", "failed", target=str(ids), details="order does not belong to current user")
        flash("دسترسی به این سفارش امکان‌پذیر نیست.", "danger")
        return redirect(url_for("panel_user.shop"))
    delivery_time = request.form.get("delivery_time", "").strip()
    courier_note = request.form.get("courier_note", "").strip()
    _orders.set_order_fields(ids, courier_note=courier_note, delivery_time=delivery_time)
    try:
        orders = _orders.get_orders_for_ids(ids, user_id=getattr(current_user, "id", None))
        names = "، ".join(o.get("pname", "—") for o in orders[:5])
        _notify_admins_shop_order(
            f"🕒 <b>زمان ارسال انتخاب شد</b>\n"
            f"🧾 سفارش‌ها: {names}\n"
            f"⏱ زمان دلخواه: {delivery_time or '—'}\n"
            f"📝 یادداشت پیک: {courier_note or '—'}"
        )
    except Exception as exc:
        logger.error("order-time admin notification failed: %s", exc)
        audit_event("order_time_notification_failed", "failed", target=str(ids), details=str(exc))
    try:
        phone = normalize_phone(getattr(current_user, "phone", "") or "")
        if phone:
            _orders.notify_user_product_order(
                phone,
                f"🕒 زمان ارسال شما ثبت شد: {delivery_time or '—'} ✅\n"
                f"کارشناس گیسو برای هماهنگی نهایی با شما تماس می‌گیرد 🌸"
            )
    except Exception as exc:
        logger.error("order-time user notification failed: %s", exc)
        audit_event("order_time_user_notification_failed", "failed", target=str(ids), details=str(exc))
    flash("زمان ارسال و یادداشت پیک ثبت شد. کارشناس گیسو برای هماهنگی نهایی پیام می‌دهد.", "success")
    return redirect(url_for("order_success"))


def product_detail(product_id, slug=None):
    product = Product.query.get_or_404(product_id)
    denied = _assert_product_published(product)
    if denied is not None:
        return denied
    try:
        product.views = (product.views or 0) + 1
        db.session.commit()
    except Exception as exc:
        logger.error("product view counter commit failed: %s", exc)
        audit_event("product_view_counter_failed", "failed", target=str(product_id), details=str(exc))
        try:
            db.session.rollback()
        except Exception as rollback_exc:
            logger.error("product view counter rollback failed: %s", rollback_exc)
    if getattr(current_user, "is_authenticated", False):
        try:
            from giso.wallet import record_product_mission_view
            record_product_mission_view(int(current_user.id), int(product.id))
        except Exception as exc:
            logger.debug("product mission progress failed: %s", exc)
    related = (Product.query
               .filter(Product.publish_status.in_(("published", "", None)))
               .filter(Product.id != product.id)
               .filter(Product.category == product.category if product.category else True)
               .order_by(Product.id.desc()).limit(3).all())
    recommendation_data = {"recommendations": [], "personalized": False}
    recommendation_reason = ""
    try:
        from giso.recommendation_service import get_product_recommendation, get_product_reason
        from flask_login import current_user as _cu
        user_phone = getattr(_cu, "phone", "") if getattr(_cu, "is_authenticated", False) else ""
        recommendation_data = get_product_recommendation(product_id, user_phone, max_items=4)
        if user_phone:
            recommendation_reason = get_product_reason(product_id, user_phone)
    except Exception as _rec_err:
        logger.debug(f"product recommendation error: {_rec_err}")
    meta_desc = (product.description or "").replace("\n", " ").strip()[:155]
    if not meta_desc:
        meta_desc = f"خرید {product.name} با پرداخت در محل از فروشگاه گیسو"
    return _shop_render(
        "product_detail.html", product=product, related=related,
        product_slug=_make_slug(product.name), meta_desc=meta_desc,
        smart_recommendations=recommendation_data.get("recommendations", []),
        recommendation_reason=recommendation_reason,
    )


def robots_txt():
    base = request.host_url.rstrip("/")
    body = (
        "User-agent: *\n"
        "Disallow: /admin\n"
        "Disallow: /admin/\n"
        "Disallow: /dashboard\n"
        "Disallow: /dashboard/\n"
        "Disallow: /api/\n"
        "Disallow: /static/uploads/\n"
        "Disallow: /my\n"
        "Allow: /$\n"
        "Allow: /shop\n"
        "Allow: /analysis\n"
        "Allow: /beauty-centers\n"
        "Allow: /hair-sale\n"
        "Allow: /marketplace\n"
        "Allow: /marketplace/\n"
        "Allow: /hair-marketplace\n"
        "Allow: /hair-marketplace/\n"
        "Allow: /static/\n\n"
        f"Sitemap: {base}/sitemap.xml\n"
    )
    resp = Response(body, mimetype="text/plain; charset=utf-8")
    resp.headers["Cache-Control"] = "public, max-age=3600"
    return resp


def sitemap_xml():
    try:
        import html as _html
    except Exception:
        _html = None
    base = request.host_url.rstrip("/")
    static_paths = [("/", 1.0, "daily"), ("/shop", 0.9, "daily"),
                    ("/analysis", 0.8, "weekly"), ("/beauty-centers", 0.8, "daily"),
                    ("/hair-sale", 0.8, "weekly")]
    urls = []
    for path, prio, freq in static_paths:
        urls.append(f"  <url><loc>{base}{path}</loc><changefreq>{freq}</changefreq><priority>{prio}</priority></url>")
    try:
        for p in _published_products():
            lastmod = (getattr(p, "updated_at", "") or getattr(p, "created_at", "") or "")[:10]
            loc = f"{base}/shop/product/{p.id}/{_make_slug(p.name)}"
            s = f"  <url><loc>{loc}</loc>"
            if lastmod:
                s += f"<lastmod>{lastmod}</lastmod>"
            s += "<priority>0.7</priority></url>"
            urls.append(s)
    except Exception as e:
        logger.warning(f"sitemap products error: {e}")
    try:
        # Beauty Centers owns the indexability query; this is only the global sitemap hook.
        from giso.beauty_centers.services import sitemap_centers
        for center in sitemap_centers():
            loc = url_for("beauty_centers.center_detail", slug=center.get("slug") or "", _external=True)
            loc = _html.escape(loc, quote=True) if _html else loc
            lastmod = str(center.get("updated_at") or center.get("published_at") or "")[:10]
            item = f"  <url><loc>{loc}</loc>"
            if lastmod:
                item += f"<lastmod>{lastmod}</lastmod>"
            item += "<changefreq>weekly</changefreq><priority>0.7</priority></url>"
            urls.append(item)
    except Exception as e:
        logger.warning(f"sitemap beauty centers error: {e}")
    xml = ("<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n"
           "<urlset xmlns=\"http://www.sitemaps.org/schemas/sitemap/0.9\">\n"
           + "\n".join(urls) + "\n</urlset>\n")
    resp = Response(xml, mimetype="application/xml; charset=utf-8")
    resp.headers["Cache-Control"] = "public, max-age=3600"
    return resp


def seed_sample_products():
    if Product.query.count() == 0:
        sample = [
            Product(name="شامپو آبرسان مخصوص موهای خشک", description="شامپو ملایم آبرسان", price=285000, in_stock=True, category="hair"),
            Product(name="ماسک مو تقویتی آرگان", description="ماسک ترمیم‌کننده با روغن آرگان", price=420000, in_stock=True, category="hair"),
            Product(name="سرم ضد موخوره", description="سرم محافظ نوک مو", price=195000, in_stock=True, category="hair"),
            Product(name="روغن آرگان خالص", description="روغن آرگان ۱۰۰٪ طبیعی", price=520000, in_stock=False, category="hair"),
            Product(name="فوم شستشوی صورت ملایم", description="مناسب انواع پوست", price=175000, in_stock=True, category="face"),
            Product(name="کرم آبرسان ۲۴ ساعته", description="آبرسان قوی با هیالورونیک اسید", price=310000, in_stock=True, category="face"),
            Product(name="ضدآفتاب SPF50", description="فاقد چربی مناسب پوست چرب", price=245000, in_stock=True, category="face"),
        ]
        for p in sample:
            db.session.add(p)
        db.session.commit()


def register_shop_routes(app):
    try:
        app.register_blueprint(shop_mod_static)
    except Exception as e:
        logger.warning(f"register shop static bp: {e}")
    app.add_url_rule("/shop", endpoint="shop", view_func=shop, methods=["GET"])
    app.add_url_rule("/shop/product/<int:product_id>", endpoint="product_detail", view_func=product_detail, methods=["GET"])
    app.add_url_rule("/shop/product/<int:product_id>/<path:slug>", endpoint="product_detail_slug", view_func=product_detail, methods=["GET"])
    app.add_url_rule("/robots.txt", endpoint="robots_txt", view_func=robots_txt, methods=["GET"])
    app.add_url_rule("/sitemap.xml", endpoint="sitemap_xml", view_func=sitemap_xml, methods=["GET"])
    app.add_url_rule("/shop/buy/<int:product_id>", endpoint="buy_product", view_func=buy_product, methods=["GET", "POST"])
    app.add_url_rule("/shop/notify/<int:product_id>", endpoint="notify_stock", view_func=notify_stock, methods=["POST"])
    app.add_url_rule("/admin/product/add", endpoint="admin_product_add", view_func=admin_product_add, methods=["POST"])
    app.add_url_rule("/admin/product/<int:product_id>/edit", endpoint="admin_product_edit", view_func=admin_product_edit, methods=["POST"])
    app.add_url_rule("/admin/product/<int:product_id>/toggle-stock", endpoint="admin_product_toggle_stock", view_func=admin_product_toggle_stock, methods=["POST"])
    app.add_url_rule("/admin/product/<int:product_id>/delete", endpoint="admin_product_delete", view_func=admin_product_delete, methods=["POST"])
    app.add_url_rule("/admin/shop-order/<int:order_id>/status", endpoint="admin_shop_order_status", view_func=admin_shop_order_status, methods=["POST"])
    app.add_url_rule("/admin/config/channel", endpoint="admin_config_channel", view_func=admin_config_channel, methods=["POST"])
    app.add_url_rule("/shop/cart/add/<int:product_id>", endpoint="cart_add", view_func=cart_add, methods=["POST"])
    app.add_url_rule("/shop/cart/remove/<int:product_id>", endpoint="cart_remove", view_func=cart_remove, methods=["POST"])
    app.add_url_rule("/shop/cart/update/<int:product_id>", endpoint="cart_update", view_func=cart_update, methods=["POST"])
    app.add_url_rule("/shop/cart", endpoint="cart_page", view_func=cart_page, methods=["GET"])
    app.add_url_rule("/api/cart-count", endpoint="cart_count_api", view_func=cart_count_api, methods=["GET"])

    @app.route("/api/recommendations", methods=["GET"])
    def recommendations_api():
        from flask import jsonify, request as _req
        from flask_login import current_user as _cu
        try:
            from giso.recommendation_service import get_recommendation_for_user, get_product_recommendation
            user_phone = getattr(_cu, "phone", "") if getattr(_cu, "is_authenticated", False) else ""
            product_id = _req.args.get("product_id", type=int)
            max_items = _req.args.get("limit", 4, type=int)
            if product_id:
                result = get_product_recommendation(product_id, user_phone, max_items)
            else:
                result = get_recommendation_for_user(user_phone, max_items)
            return jsonify(result)
        except Exception:
            return jsonify({"status": "error", "recommendations": []}), 500

    app.add_url_rule("/shop/cart/checkout", endpoint="cart_checkout", view_func=cart_checkout, methods=["POST"])
    app.add_url_rule("/shop/order-success", endpoint="order_success", view_func=order_success, methods=["GET"])
    app.add_url_rule("/shop/orders/<int:order_id>/invoice", endpoint="order_invoice", view_func=order_invoice, methods=["GET"])
    app.add_url_rule("/shop/order-time", endpoint="order_time", view_func=order_time, methods=["POST"])
    app.add_url_rule("/admin/product/<int:product_id>/publish", endpoint="admin_product_publish", view_func=admin_product_publish, methods=["POST"])
    app.add_url_rule("/admin/product/<int:product_id>/reject-import", endpoint="admin_product_reject", view_func=admin_product_reject, methods=["POST"])
    app.add_url_rule("/admin/config/publish-mode", endpoint="admin_publish_mode", view_func=admin_publish_mode, methods=["POST"])
    app.add_url_rule("/admin/config/channel-test", endpoint="admin_channel_test", view_func=admin_channel_test, methods=["POST"])
    app.add_url_rule("/admin/shop/stats", endpoint="admin_shop_stats", view_func=admin_shop_stats, methods=["GET"])


__all__ = [
    "shop_routes", "shop_mod_static", "register_shop_routes",
    "shop", "_shop_context", "buy_product", "notify_stock",
    "admin_product_add", "admin_product_edit", "admin_product_toggle_stock",
    "admin_product_delete", "admin_shop_order_status", "admin_config_channel",
    "product_detail", "cart_add", "cart_remove", "cart_update", "cart_page", "cart_checkout",
    "admin_product_publish", "admin_product_reject", "admin_publish_mode", "admin_channel_test", "admin_shop_stats",
    "get_publish_mode", "_notify_admins_shop_order", "robots_txt", "sitemap_xml",
    "_make_slug", "_save_product_image", "seed_sample_products",
    "order_success", "order_invoice", "order_time",
]
