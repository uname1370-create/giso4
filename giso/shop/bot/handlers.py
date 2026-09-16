# -*- coding: utf-8 -*-
"""giso/shop/bot/handlers.py — هندلرهای ربات فروشگاه (فاز B).

- منوی «🛍 فروشگاه» برای کاربر/ادمین/سوپرادمین (state های جدا)
- callback های نام‌فضای `shop_` (بدون تداخل با callback های موجود)
- همه داده‌ها از دیتابیس واقعی؛ هیچ دکمه بی‌عملی ساخته نمی‌شود
  گزینه‌های فروشگاه فقط وقتی در منو نمایش داده می‌شوند که رفتار واقعی داشته باشند.
"""
import logging
import time

from giso.base import get_giso_db_conn, normalize_phone, _fa_num, _is_super_admin, to_shamsi
from giso.money import format_toman

logger = logging.getLogger("giso_shop_bot_handlers")

SHOP_STATES = ("shop_user_menu", "shop_admin_menu", "shop_super_menu")
SHOP_ORDER_PAGE_SIZE = 5

# مرجع دیکشنری state ربات (توسط bot.py هنگام بوت رجیستر می‌شود؛ handle_shop_bot_text هم به‌روز نگه می‌دارد)
_BOT_USER_STATES = None


def register_user_states(states_dict):
    """ثبت مرجع _user_states ربات تا callbackهای stateدار فروشگاه کار کنند."""
    global _BOT_USER_STATES
    _BOT_USER_STATES = states_dict


# ═══════════════════ مدیریت سفارشات فروشگاه در ربات ═══════════════════

def _list_shop_orders(limit=100, status=None):
    """لیست سفارشات فروشگاه از دیتابیس (اختیاری: فیلتر وضعیت + آدرس کامل)."""
    try:
        with get_giso_db_conn() as conn:
            _where = "WHERE po.status=? " if status else ""
            _params = ([status, int(limit)] if status else [int(limit)])
            rows = conn.execute(
                "SELECT po.id, po.customer_name, po.phone, po.status, po.tracking_code, "
                "po.quantity, po.created_at, po.address, po.delivery_time, p.name AS pname, p.price "
                "FROM product_orders po LEFT JOIN products p ON po.product_id=p.id "
                + _where + "ORDER BY po.id DESC LIMIT ?", _params
            ).fetchall()
        return [dict(r) for r in rows]
    except Exception as e:
        logger.error(f"_list_shop_orders: {e}")
        return []


def _get_shop_order(order_id):
    """دریافت یک سفارش فروشگاه."""
    try:
        with get_giso_db_conn() as conn:
            row = conn.execute(
                "SELECT po.*, p.name AS pname, p.price FROM product_orders po "
                "LEFT JOIN products p ON po.product_id=p.id WHERE po.id=?",
                (int(order_id),)
            ).fetchone()
        return dict(row) if row else None
    except Exception as e:
        logger.error(f"_get_shop_order: {e}")
        return None


def _shop_order_card(order, idx=None, total=None):
    """کارت خلاصه یک سفارش فروشگاه."""
    status_fa = {
        "pending": "⏳ در حال بررسی",
        "approved": "✅ تأیید شد",
        "shipped": "🚚 در حال ارسال",
        "delivered": "📦 تحویل شد",
        "rejected": "❌ رد شد",
    }.get(order.get("status", ""), order.get("status", ""))
    lines = [
        f"🛍 سفارش فروشگاه #{_fa_num(order.get('id'))}",
        "━━━━━━━━━━━━━━━━",
    ]
    if idx is not None and total:
        lines.append(f"📄 {_fa_num(idx + 1)} از {_fa_num(total)}")
        lines.append("━━━━━━━━━━━━━━━━")
    lines += [
        f"📦 محصول: {order.get('pname') or '—'}",
        f"🔢 تعداد: {_fa_num(order.get('quantity', 1))}",
        f"💰 قیمت: {format_toman(order.get('price', 0))}",
        f"📌 وضعیت: {status_fa}",
        f"🔑 کد پیگیری: {order.get('tracking_code') or '—'}",
        "━━━━━━━━━━━━━━━━",
        f"👤 مشتری: {order.get('customer_name') or '—'}",
        f"📱 شماره: {order.get('phone') or '—'}",
        f"📍 آدرس: {order.get('address') or '—'}",
        f"⏰ زمان تحویل: {order.get('delivery_time') or '—'}",
        f"📅 تاریخ: {to_shamsi(order.get('created_at'))}",
    ]
    return "\n".join(lines)


async def _show_shop_orders_paged(msg, uid, idx=0, role="admin"):
    """نمایش سفارشات فروشگاه تک‌به‌تک با ۳ اکشن + صفحه‌بندی."""
    from telegram import InlineKeyboardButton, InlineKeyboardMarkup
    orders = _list_shop_orders()
    if not orders:
        await msg.reply_text("📭 هیچ سفارش فروشگاهی ثبت نشده است.")
        return 0
    idx = max(0, min(idx, len(orders) - 1))
    order = orders[idx]
    caption = _shop_order_card(order, idx=idx, total=len(orders))
    rows = [
        [InlineKeyboardButton("⏳ در حال بررسی", callback_data=f"shop_ord_st|{order['id']}|pending"), InlineKeyboardButton("🚚 ارسال شد", callback_data=f"shop_ord_st|{order['id']}|shipped")],
        [InlineKeyboardButton("✅ تحویل شد", callback_data=f"shop_ord_st|{order['id']}|delivered"), InlineKeyboardButton("❌ رد سفارش", callback_data=f"shop_ord_st|{order['id']}|rejected")],
    ]
    nav = []
    if idx > 0: nav.append(InlineKeyboardButton("◀️ قبلی", callback_data=f"shop_ord_pg|{idx - 1}"))
    if idx < len(orders) - 1: nav.append(InlineKeyboardButton("بعدی ▶️", callback_data=f"shop_ord_pg|{idx + 1}"))
    if nav: rows.append(nav)
    if role == "super":
        rows.append([InlineKeyboardButton("🔙 منوی فروشگاه", callback_data="shop_back_menu")])
    await msg.reply_text(caption, reply_markup=InlineKeyboardMarkup(rows))
    return len(orders)


_ADD_PRODUCT_GUIDE = (
    "➕ افزودن محصول جدید\n━━━━━━━━━━━━━━━━\n"
    "اطلاعات محصول را در یک پیام و هر مورد در یک خط بفرستید:\n\n"
    "نام محصول\nقیمت (تومان)\nدسته‌بندی\nتوضیحات\n\n"
    "مثال:\nشامپو تقویتی گیسو\n185000\nمراقبت مو\nشامپو گیاهی مناسب موهای خشک\n\n"
    "برای انصراف: «لغو»"
)

SHOP_PRODUCT_PAGE_SIZE = 10


async def _show_products_list(msg, menu_kb, page: int = 0):
    """لیست محصولات فروشگاه — صفحه‌بندی ۱۰تایی + دکمه ویرایش هر محصول (مطابق مشخصات)."""
    from telegram import InlineKeyboardButton, InlineKeyboardMarkup
    try:
        with get_giso_db_conn() as conn:
            total = conn.execute("SELECT COUNT(*) FROM products").fetchone()[0] or 0
            rows = conn.execute(
                "SELECT id, name, price, in_stock FROM products ORDER BY id DESC LIMIT ? OFFSET ?",
                (SHOP_PRODUCT_PAGE_SIZE, int(page) * SHOP_PRODUCT_PAGE_SIZE)).fetchall()
    except Exception as e:
        logger.error(f"_show_products_list: {e}")
        await msg.reply_text("❌ خطا در دریافت محصولات.", reply_markup=menu_kb)
        return
    if not rows:
        await msg.reply_text("📦 محصولی ثبت نشده است.", reply_markup=menu_kb)
        return
    pages = max(1, (total + SHOP_PRODUCT_PAGE_SIZE - 1) // SHOP_PRODUCT_PAGE_SIZE)
    kb_rows = []
    for r in rows:
        stock = "✅" if r["in_stock"] else "❌"
        kb_rows.append([InlineKeyboardButton(
            f"{stock} #{r['id']} — {(r['name'] or '')[:28]} — {format_toman(r['price'] or 0)}",
            callback_data=f"shop_edit|{r['id']}")])
    nav = []
    if page > 0: nav.append(InlineKeyboardButton("⬅️ قبلی", callback_data=f"shop_prod_pg|{page - 1}"))
    if page + 1 < pages: nav.append(InlineKeyboardButton("بعدی ➡️", callback_data=f"shop_prod_pg|{page + 1}"))
    if nav: kb_rows.append(nav)
    kb_rows.append([InlineKeyboardButton("🔙 منوی فروشگاه", callback_data="shop_back_menu")])
    await msg.reply_text(
        f"📦 محصولات فروشگاه\n━━━━━━━━━━━━━━━━\n"
        f"🧾 کل: {_fa_num(total)} | صفحه {_fa_num(page + 1)} از {_fa_num(pages)}\n"
        "برای ویرایش (توضیحات/قیمت/موجودی) روی محصول بزنید:", reply_markup=InlineKeyboardMarkup(kb_rows))


def _create_manual_product(raw: str) -> str:
    """ساخت محصول دستی از متن چندخطی؛ خروجی پیام نتیجه."""
    lines = [ln.strip() for ln in (raw or "").splitlines() if ln.strip()]
    if len(lines) < 2:
        return ""
    name = lines[0][:120]
    price_txt = lines[1].translate(str.maketrans("۰۱۲۳۴۵۶۷۸۹", "0123456789")).replace(",", "").replace("،", "")
    try:
        price = int("".join(ch for ch in price_txt if ch.isdigit()) or "0")
    except ValueError:
        price = 0
    if not name or price <= 0:
        return ""
    category = lines[2][:60] if len(lines) > 2 else ""
    description = "\n".join(lines[3:])[:1000] if len(lines) > 3 else ""
    try:
        now = time.strftime("%Y-%m-%d %H:%M:%S")
        with get_giso_db_conn() as conn:
            cur = conn.execute(
                "INSERT INTO products (name, price, category, description, in_stock, publish_status, source, created_at) "
                "VALUES (?, ?, ?, ?, 1, 'published', 'manual', ?)",
                (name, price, category, description, now))
            conn.commit()
            pid = cur.lastrowid
        return f"✅ محصول #{_fa_num(pid)} «{name}» با قیمت {format_toman(price)} در فروشگاه منتشر شد."
    except Exception as e:
        logger.error(f"_create_manual_product: {e}")
        return ""


def _create_discount_from_text(raw: str, product_id: str = "all") -> str:
    """ساخت کد تخفیف از متن «کد درصد»؛ عمومی یا مخصوص یک محصول."""
    parts = [p.strip() for p in (raw or "").replace("\n", " ").split() if p.strip()]
    if len(parts) < 2:
        return ""
    code = parts[0].upper()
    val_txt = parts[1].translate(str.maketrans("۰۱۲۳۴۵۶۷۸۹", "0123456789"))
    try:
        value = int("".join(ch for ch in val_txt if ch.isdigit()) or "0")
    except ValueError:
        value = 0
    if not code or not (0 < value <= 100):
        return ""
    try:
        from giso.shop.logic.discount import create_discount_code
        res = create_discount_code(code, discount_type="percent", discount_value=value)
        if not res.get("ok"):
            return ""
        scope_txt = "همه محصولات"
        # اتصال کد به محصول خاص (ستون product_id اگر نبود، اضافه می‌شود — idempotent)
        if product_id and product_id != "all" and str(product_id).isdigit():
            try:
                with get_giso_db_conn() as conn:
                    cols = [c[1] for c in conn.execute("PRAGMA table_info(discount_codes)").fetchall()]
                    if "product_id" not in cols:
                        conn.execute("ALTER TABLE discount_codes ADD COLUMN product_id INTEGER DEFAULT 0")
                    conn.execute("UPDATE discount_codes SET product_id=? WHERE code=?", (int(product_id), code))
                    _pn = conn.execute("SELECT name FROM products WHERE id=?", (int(product_id),)).fetchone()
                    conn.commit()
                scope_txt = f"محصول «{(_pn[0] if _pn else product_id)}»"
            except Exception as e_link:
                logger.warning(f"discount product link: {e_link}")
        return f"✅ کد تخفیف {code} با {_fa_num(value)}٪ تخفیف برای {scope_txt} ساخته و فعال شد."
    except Exception as e:
        logger.error(f"_create_discount_from_text: {e}")
        return ""


def _shop_reports_menu_kb():
    """منوی گزارش‌های فروشگاه — ۶ دکمه مطابق مشخصات (مثل قسمت خرید مو)."""
    from telegram import InlineKeyboardButton, InlineKeyboardMarkup
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("⏳ نمایش درخواست‌های در حال بررسی", callback_data="shop_rep|pending|0")],
        [InlineKeyboardButton("🚚 نمایش محصولات در حال ارسال", callback_data="shop_rep|shipped|0")],
        [InlineKeyboardButton("📦 نمایش سفارشات ارسال‌شده", callback_data="shop_rep|delivered|0")],
        [InlineKeyboardButton("❌ نمایش سفارشات رد شده", callback_data="shop_rep|rejected|0")],
        [InlineKeyboardButton("📊 گزارش کلی", callback_data="shop_rep|overall|0"),
         InlineKeyboardButton("💰 گزارش فروش", callback_data="shop_rep|sales|0")],
        [InlineKeyboardButton("🔙 منوی فروشگاه", callback_data="shop_back_menu")],
    ])


async def _show_shop_orders_by_status(msg, uid, status, idx=0):
    """نمایش تک‌به‌تک سفارشات یک وضعیت خاص با اکشن ویرایش وضعیت (مثل خرید مو)."""
    from telegram import InlineKeyboardButton, InlineKeyboardMarkup
    orders = _list_shop_orders(status=status)
    st_fa = {"pending": "در حال بررسی", "shipped": "در حال ارسال",
             "delivered": "ارسال‌شده", "rejected": "رد شده"}.get(status, status)
    if not orders:
        await msg.reply_text(f"📭 سفارشی با وضعیت «{st_fa}» وجود ندارد.",
                             reply_markup=_shop_reports_menu_kb())
        return 0
    idx = max(0, min(idx, len(orders) - 1))
    order = orders[idx]
    caption = _shop_order_card(order, idx=idx, total=len(orders))
    rows = [
        [InlineKeyboardButton("⏳ در حال بررسی", callback_data=f"shop_ord_st|{order['id']}|pending"),
         InlineKeyboardButton("🚚 در حال ارسال", callback_data=f"shop_ord_st|{order['id']}|shipped")],
        [InlineKeyboardButton("📦 ارسال شد", callback_data=f"shop_ord_st|{order['id']}|delivered"),
         InlineKeyboardButton("❌ رد سفارش", callback_data=f"shop_ord_st|{order['id']}|rejected")],
    ]
    nav = []
    if idx > 0: nav.append(InlineKeyboardButton("◀️ قبلی", callback_data=f"shop_rep|{status}|{idx - 1}"))
    if idx < len(orders) - 1: nav.append(InlineKeyboardButton("بعدی ▶️", callback_data=f"shop_rep|{status}|{idx + 1}"))
    if nav: rows.append(nav)
    rows.append([InlineKeyboardButton("🔙 بازگشت به گزارش‌ها", callback_data="shop_rep|menu|0")])
    await msg.reply_text(caption, reply_markup=InlineKeyboardMarkup(rows))
    return len(orders)


def _shop_sales_report_text() -> str:
    """گزارش فروش محصولات: فروش‌رفته، کل فروش، خریداران."""
    try:
        with get_giso_db_conn() as conn:
            sold_cnt = conn.execute("SELECT COALESCE(SUM(quantity),0) FROM product_orders WHERE status IN ('approved','shipped','delivered')").fetchone()[0] or 0
            total_sales = conn.execute("SELECT COALESCE(SUM(p.price*po.quantity),0) FROM product_orders po LEFT JOIN products p ON po.product_id=p.id WHERE po.status IN ('approved','shipped','delivered')").fetchone()[0] or 0
            buyers = conn.execute("SELECT COUNT(DISTINCT phone) FROM product_orders WHERE status IN ('approved','shipped','delivered')").fetchone()[0] or 0
    except Exception as e:
        logger.error(f"_shop_sales_report_text: {e}")
        sold_cnt = total_sales = buyers = 0
    return (
        "💰 گزارش فروش محصولات\n━━━━━━━━━━━━━━━━\n"
        f"📦 محصولات فروش‌رفته: {_fa_num(sold_cnt)}\n"
        f"🏦 کل فروش: {format_toman(total_sales)}\n"
        f"👥 کاربران خریدار: {_fa_num(buyers)}"
    )


async def _show_shop_report(msg, uid):
    try:
        with get_giso_db_conn() as conn:
            total_orders = conn.execute("SELECT COUNT(*) FROM product_orders").fetchone()[0]
            pending = conn.execute("SELECT COUNT(*) FROM product_orders WHERE status='pending'").fetchone()[0]
            approved = conn.execute("SELECT COUNT(*) FROM product_orders WHERE status='approved'").fetchone()[0]
            shipped = conn.execute("SELECT COUNT(*) FROM product_orders WHERE status='shipped'").fetchone()[0]
            delivered = conn.execute("SELECT COUNT(*) FROM product_orders WHERE status='delivered'").fetchone()[0]
            rejected = conn.execute("SELECT COUNT(*) FROM product_orders WHERE status='rejected'").fetchone()[0]
            total_products = conn.execute("SELECT COUNT(*) FROM products").fetchone()[0]
            in_stock = conn.execute("SELECT COUNT(*) FROM products WHERE in_stock=1").fetchone()[0]
            revenue = conn.execute("SELECT COALESCE(SUM(p.price * po.quantity), 0) FROM product_orders po LEFT JOIN products p ON po.product_id=p.id WHERE po.status IN ('approved','delivered')").fetchone()[0]
    except Exception:
        total_orders = pending = approved = shipped = delivered = rejected = total_products = in_stock = revenue = 0
    report = f"📊 گزارش کلی فروشگاه\n━━━━━━━━━━━━━━━━\n📦 کل سفارشات: {_fa_num(total_orders)}\n⏳ در حال بررسی: {_fa_num(pending)}\n🚚 در حال ارسال: {_fa_num(shipped)}\n✅ تحویل شده: {_fa_num(delivered)}\n❌ رد شده: {_fa_num(rejected)}\n━━━━━━━━━━━━━━━━\n🛍 کل محصولات: {_fa_num(total_products)}\n✅ موجود: {_fa_num(in_stock)}\n💰 درآمد تأییدشده: {format_toman(revenue)}\n"
    await msg.reply_text(report)


async def _search_tracking_code(msg, tracking_code):
    from telegram import InlineKeyboardButton, InlineKeyboardMarkup
    try:
        with get_giso_db_conn() as conn:
            rows = conn.execute(
                "SELECT po.*,p.name AS pname,p.price FROM product_orders po "
                "LEFT JOIN products p ON po.product_id=p.id "
                "WHERE po.tracking_code=? ORDER BY po.id", (tracking_code.strip(),)
            ).fetchall()
        if not rows:
            await msg.reply_text(f"🔍 هیچ سفارشی با کد پیگیری «{tracking_code}» یافت نشد.")
            return
        orders = [dict(row) for row in rows]
        first = orders[0]
        total = sum(int(order.get("price") or 0) * int(order.get("quantity") or 1) for order in orders)
        item_lines = "\n".join(
            f"• #{order['id']} — {order.get('pname') or 'محصول'} × {order.get('quantity') or 1}"
            for order in orders
        )
        text = (
            f"🔎 نتیجه کد پیگیری {tracking_code.strip()}\n"
            f"━━━━━━━━━━━━━━━━\n{item_lines}\n"
            f"━━━━━━━━━━━━━━━━\n💰 جمع اقلام: {format_toman(total)}\n"
            f"👤 {first.get('customer_name') or '—'}\n📱 {first.get('phone') or '—'}\n"
            f"📍 {first.get('address') or '—'}"
        )
        buttons = []
        for order in orders[:20]:
            oid = order["id"]
            buttons.extend([
                [InlineKeyboardButton(f"⏳ بررسی #{oid}", callback_data=f"shop_ord_st|{oid}|pending"),
                 InlineKeyboardButton(f"🚚 ارسال #{oid}", callback_data=f"shop_ord_st|{oid}|shipped")],
                [InlineKeyboardButton(f"📦 تحویل #{oid}", callback_data=f"shop_ord_st|{oid}|delivered"),
                 InlineKeyboardButton(f"❌ رد #{oid}", callback_data=f"shop_ord_st|{oid}|rejected")],
            ])
        buttons.append([InlineKeyboardButton("🔙 منوی فروشگاه", callback_data="shop_back_menu")])
        await msg.reply_text(text, reply_markup=InlineKeyboardMarkup(buttons))
    except Exception as e:
        logger.error(f"_search_tracking_code: {e}")
        await msg.reply_text("❌ خطا در جستجو.")

def _site_url() -> str:
    from giso.base import get_site_url
    return get_site_url()

def _shop_admin_allowed(uid) -> bool:
    """Every approved normal admin has the fixed operational Shop role."""
    try:
        with get_giso_db_conn() as conn:
            row = conn.execute(
                "SELECT is_admin FROM giso_users WHERE bale_id=?", (str(uid),)
            ).fetchone()
        return bool(row and row[0])
    except Exception:
        return False


def _publish_product(product_id) -> bool:
    try:
        from giso.base import get_giso_db_conn
        from giso.channel_importer import PRICE_MISSING_NOTE
        with get_giso_db_conn() as conn:
            row = conn.execute("SELECT id, description, price FROM products WHERE id=?", (int(product_id),)).fetchone()
            if not row or not row["price"]: return False
            desc = (row["description"] or "")
            if PRICE_MISSING_NOTE in desc: desc = desc.replace(PRICE_MISSING_NOTE, "").strip()
            conn.execute("UPDATE products SET publish_status='published', description=?, updated_at=? WHERE id=?", (desc, time.strftime("%Y-%m-%d %H:%M:%S"), int(product_id)))
            conn.commit()
        return True
    except Exception as e:
        logger.warning(f"shop bot publish product: {e}")
        return False

def _toggle_publish_mode() -> str:
    from giso.shop.logic.channel_bridge import get_publish_mode
    try:
        from giso_admin import set_giso_config
        new = "auto" if get_publish_mode() == "review" else "review"
        set_giso_config("shop_publish_mode", new)
        return new
    except Exception as e:
        logger.warning(f"shop bot toggle publish: {e}")
        return ""

_PENDING_EDIT = {}

def _product_image_file(image_path: str):
    import os
    if not image_path: return None
    cand = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "static", image_path)
    return cand if os.path.exists(cand) else None

async def _send_pending_card(msg, idx: int, restricted: bool = False):
    from giso.shop.bot.admin_menu import get_pending_products, pending_card_text, pending_card_kb
    items = get_pending_products(channel_only=restricted)
    if not items: return 0
    idx = max(0, min(idx, len(items) - 1)); p = items[idx]
    text = pending_card_text(p, idx, len(items)); kb = pending_card_kb(int(p["id"]), idx, len(items), restricted=restricted); img = _product_image_file(p.get("image_path") or "")
    if img:
        try:
            with open(img, "rb") as fh: await msg.reply_photo(photo=fh, caption=text, reply_markup=kb)
            return len(items)
        except Exception as e: logger.debug(f"pending card photo send failed: {e}")
    await msg.reply_text(text, reply_markup=kb); return len(items)

async def _edit_pending_card(query, idx: int, notice: str = "", restricted: bool = False):
    from giso.shop.bot.admin_menu import get_pending_products, pending_card_text, pending_card_kb
    items = get_pending_products(channel_only=restricted)
    if not items:
        try:
            if query.message and query.message.photo: await query.edit_message_caption(caption="✅ همه محصولات منتظر تأیید بررسی شدند.")
            else: await query.edit_message_text("✅ همه محصولات منتظر تأیید بررسی شدند.")
        except Exception: pass
        return
    idx = max(0, min(idx, len(items) - 1)); p = items[idx]; text = pending_card_text(p, idx, len(items))
    if notice: text = notice + "\n\n" + text
    kb = pending_card_kb(int(p["id"]), idx, len(items), restricted=restricted)
    try:
        if query.message and query.message.photo: await query.edit_message_caption(caption=text, reply_markup=kb)
        else: await query.edit_message_text(text, reply_markup=kb)
    except Exception as e: logger.debug(f"edit pending card: {e}")

def _is_pending_channel_product(product_id) -> bool:
    try:
        with get_giso_db_conn() as conn:
            row = conn.execute(
                "SELECT 1 FROM products WHERE id=? AND source='channel' AND publish_status='pending'",
                (int(product_id),),
            ).fetchone()
        return bool(row)
    except Exception:
        return False


def _reject_product(product_id) -> bool:
    try:
        with get_giso_db_conn() as conn:
            conn.execute("UPDATE products SET publish_status='rejected', updated_at=? WHERE id=?", (time.strftime("%Y-%m-%d %H:%M:%S"), int(product_id))); conn.commit()
        return True
    except Exception as e: logger.warning(f"shop bot reject product: {e}"); return False

def _apply_pending_edit(pid: int, raw: str) -> str:
    import re
    raw = (raw or "").strip()
    if not raw: return ""
    parts = [p.strip() for p in raw.split("|", 1)]; name = None; price = None
    if len(parts) == 2:
        name = parts[0] or None; digits = re.sub(r"[^\d]", "", parts[1].translate(str.maketrans("۰۱۲۳۴۵۶۷۸۹", "0123456789"))); price = int(digits) if digits else None
    else:
        digits = re.sub(r"[^\d]", "", raw.translate(str.maketrans("۰۱۲۳۴۵۶۷۸۹", "0123456789")))
        if digits and re.fullmatch(r"[\d۰-۹,\s]*(تومان)?", raw): price = int(digits)
        else: name = raw
    try:
        with get_giso_db_conn() as conn:
            if name and price is not None: conn.execute("UPDATE products SET name=?, price=?, updated_at=? WHERE id=?", (name, price, time.strftime("%Y-%m-%d %H:%M:%S"), pid))
            elif price is not None: conn.execute("UPDATE products SET price=?, updated_at=? WHERE id=?", (price, time.strftime("%Y-%m-%d %H:%M:%S"), pid))
            elif name: conn.execute("UPDATE products SET name=?, updated_at=? WHERE id=?", (name, time.strftime("%Y-%m-%d %H:%M:%S"), pid))
            else: return ""
            conn.commit()
        return "ok"
    except Exception as e: logger.warning(f"shop bot pending edit: {e}"); return ""

def _apply_pending_desc(pid: int, text: str) -> bool:
    text = (text or "").strip()
    if not text: return False
    try:
        with get_giso_db_conn() as conn: conn.execute("UPDATE products SET description=?, updated_at=? WHERE id=?", (text, time.strftime("%Y-%m-%d %H:%M:%S"), int(pid))); conn.commit()
        return True
    except Exception as e: logger.warning(f"shop bot pending desc: {e}"); return False

async def apply_pending_photo(bot, msg, pid: int) -> str:
    try:
        photos = getattr(msg, "photo", None) or []
        if not photos: return ""
        from giso.channel_importer import _download_photo_as_webp
        image_path = await _download_photo_as_webp(bot, photos[-1])
        if not image_path: return ""
        with get_giso_db_conn() as conn: conn.execute("UPDATE products SET image_path=?, updated_at=? WHERE id=?", (image_path, time.strftime("%Y-%m-%d %H:%M:%S"), int(pid))); conn.commit()
        return image_path
    except Exception as e: logger.warning(f"shop bot pending photo: {e}"); return ""

async def handle_shop_bot_photo(msg, uid, context=None) -> bool:
    key = uid if uid in _PENDING_EDIT else (str(uid) if str(uid) in _PENDING_EDIT else None); raw = _PENDING_EDIT.get(key) if key is not None else None
    if not raw or len(raw) < 3 or raw[2] != "photo": return False
    pid, idx = raw[0], raw[1]; saved = await apply_pending_photo(context.bot, msg, int(pid)); _PENDING_EDIT.pop(key, None)
    if saved: await msg.reply_text(f"🖼✅ عکس محصول #{_fa_num(pid)} تنظیم شد. کارت به‌روزرسانی شد:"); await _send_pending_card(msg, int(idx))
    else: await msg.reply_text("⚠️ ذخیره عکس ناموفق بود. دوباره عکس بفرستید یا «لغو»."); _PENDING_EDIT[key] = (pid, idx, "photo")
    return True

async def handle_shop_bot_text(msg, text, uid, phone, existing, user_states, context=None) -> bool:
    try:
        register_user_states(user_states)  # مرجع state برای callbackهای فروشگاه
        state = user_states.get(uid, "")
        is_super = _is_super_admin(uid, phone)
        is_normal_admin = bool(existing and existing.get("is_admin") and not is_super)
        _removed_shop = {
            "➕ افزودن محصول", "⚙️ تنظیمات فروشگاه", "🎁 کد تخفیف", "📢 مدیریت کانال",
        }
        if is_normal_admin:
            _removed_shop |= {
                "⏳ لیست محصولات منتظر تأیید", "✅ تأیید کانال",
                "📦 محصولات", "📊 گزارش فروش",
            }
        if text in _removed_shop:
            from giso.shop.bot.admin_menu import shop_admin_menu_kb
            from giso.shop.bot.super_menu import shop_super_menu_kb
            kb = shop_super_menu_kb() if is_super else shop_admin_menu_kb()
            await msg.reply_text("این گزینه حذف شده است.", reply_markup=kb)
            return True
        if state == "shop_super_menu" and not is_super:
            user_states.pop(uid, None)
            if existing and existing.get("is_admin"):
                from giso.shop.bot.admin_menu import shop_admin_menu_kb
                await msg.reply_text("⛔ تنظیمات فروشگاه فقط برای سوپرادمین است.",
                                     reply_markup=shop_admin_menu_kb())
            else:
                await msg.reply_text("⛔ فقط سوپرادمین")
            return True
        if state in SHOP_STATES:
            if text == "🔙 بازگشت":
                user_states.pop(uid, None)
                from giso.shop.bot.user_menu import shop_user_menu_text, shop_user_kb
                from giso.shop.bot.admin_menu import shop_admin_menu_text, shop_admin_menu_kb
                from giso.shop.bot.super_menu import shop_super_menu_text, shop_super_menu_kb
                if state == "shop_user_menu": await msg.reply_text(shop_user_menu_text(), reply_markup=shop_user_kb())
                elif state == "shop_admin_menu": await msg.reply_text(shop_admin_menu_text(), reply_markup=shop_admin_menu_kb())
                else: await msg.reply_text(shop_super_menu_text(), reply_markup=shop_super_menu_kb())
                return True
            if state == "shop_user_menu":
                from giso.shop.bot.user_menu import shop_user_kb, user_orders_text, user_notifies_text
                if text == "🛒 مشاهده فروشگاه": await msg.reply_text(f"🛍 فروشگاه گیسو\n━━━━━━━━━━━━━━━━\n🌐 {_site_url()}/shop\n\nخرید با پرداخت در محل 🛵 — از لینک زیر وارد شوید:"); return True
                if text == "📦 سفارش‌های من": await msg.reply_text(user_orders_text(phone), reply_markup=shop_user_kb()); return True
                if text == "🔔 اعلان موجودی": await msg.reply_text(user_notifies_text(phone), reply_markup=shop_user_kb()); return True
                return True
        if state == "shop_tracking_search": user_states.pop(uid, None); await _search_tracking_code(msg, text); return True
        if state == "shop_add_product":
            user_states.pop(uid, None)
            from giso.shop.bot.admin_menu import shop_admin_menu_kb
            from giso.shop.bot.super_menu import shop_super_menu_kb
            menu_kb = shop_super_menu_kb() if _is_super_admin(uid, phone) else shop_admin_menu_kb()
            if text.strip() in ("لغو", "❌ لغو", "🔙 بازگشت"):
                await msg.reply_text("➕ افزودن محصول لغو شد.", reply_markup=menu_kb); return True
            note = _create_manual_product(text)
            if note:
                await msg.reply_text(note, reply_markup=menu_kb)
            else:
                user_states[uid] = "shop_add_product"
                await msg.reply_text("❌ فرمت نامعتبر. حداقل «نام» و «قیمت معتبر» لازم است.\n" + _ADD_PRODUCT_GUIDE)
            return True
        if state == "shop_disc_add_input" or state.startswith("shop_disc_add_input|"):
            _disc_target = state.split("|", 1)[1] if "|" in state else "all"
            user_states.pop(uid, None)
            from giso.shop.bot.super_menu import shop_super_menu_kb
            if not _is_super_admin(uid, phone):
                return True
            if text.strip() in ("لغو", "❌ لغو", "🔙 بازگشت"):
                await msg.reply_text("🎁 افزودن کد تخفیف لغو شد.", reply_markup=shop_super_menu_kb()); return True
            note = _create_discount_from_text(text, product_id=_disc_target)
            if note:
                await msg.reply_text(note, reply_markup=shop_super_menu_kb())
            else:
                user_states[uid] = f"shop_disc_add_input|{_disc_target}"
                await msg.reply_text("❌ فرمت نامعتبر. مثال: GISO20 20 (کد و درصد ۱ تا ۱۰۰)")
            return True
        if state == "shop_channel_input":
            user_states.pop(uid, None)
            if not is_super:
                await msg.reply_text("⛔ تنظیمات کانال فقط برای سوپرادمین است.")
                return True
            channel_id = text.strip()
            try:
                from giso_admin import set_giso_config
                set_giso_config("bale_channel_id", channel_id)
                from giso.shop.bot.super_menu import settings_text, settings_kb
                await msg.reply_text(f"✅ آیدی کانال ذخیره شد: {channel_id}\n\n💡 ربات باید در کانال ادمین باشد تا پست‌ها خودکار وارد شوند.", reply_markup=settings_kb())
            except Exception as e: logger.error(f"shop_channel_input: {e}"); await msg.reply_text("❌ خطا در ذخیره آیدی کانال.")
            return True
        if state in ("shop_ref_amount_input", "shop_ref_max_input"):
            user_states.pop(uid, None)
            await msg.reply_text("ℹ️ برنامه معرفی و پورسانت متوقف شده است.")
            return True
        # ── ورودیِ ویرایش محصولِ در انتظار تأیید (نام/قیمت/توضیح/عکس) ──
        # فیکس موضعی: این بلوک قبلاً پشت return True گیر کرده بود و هرگز اجرا نمی‌شد.
        _edit_key = uid if uid in _PENDING_EDIT else (str(uid) if str(uid) in _PENDING_EDIT else None)
        if _edit_key is not None:
            _raw = _PENDING_EDIT.pop(_edit_key); pid, idx = _raw[0], _raw[1]; field = _raw[2] if len(_raw) > 2 else "fast"
            from giso.shop.bot.admin_menu import shop_admin_menu_kb, get_pending_products
            from giso.shop.bot.super_menu import shop_super_menu_kb
            menu_kb = shop_super_menu_kb() if state == "shop_super_menu" else shop_admin_menu_kb()
            if text in ("لغو", "❌ لغو", "🔙 بازگشت"): await msg.reply_text("✏️ ویرایش لغو شد.", reply_markup=menu_kb); return True
            if field == "photo": await msg.reply_text("🖼 لطفاً عکس محصول را به‌صورت پیام تصویری بفرستید (برای انصراف: لغو).", reply_markup=menu_kb); _PENDING_EDIT[_edit_key] = (pid, idx, "photo"); return True
            if field == "price":
                # فقط قیمت (تومان) — ارقام فارسی هم قبول
                _digits = "".join(ch for ch in text.translate(str.maketrans("۰۱۲۳۴۵۶۷۸۹", "0123456789")) if ch.isdigit())
                ok = False
                if _digits:
                    try:
                        with get_giso_db_conn() as conn:
                            conn.execute("UPDATE products SET price=?, updated_at=? WHERE id=?",
                                         (int(_digits), time.strftime("%Y-%m-%d %H:%M:%S"), int(pid)))
                            conn.commit()
                        ok = True
                    except Exception as _e_prc:
                        logger.warning(f"shop price edit: {_e_prc}")
            else:
                ok = _apply_pending_desc(int(pid), text) if field == "desc" else bool(_apply_pending_edit(int(pid), text))
            if ok:
                await msg.reply_text(f"✅ تغییرات روی محصول #{_fa_num(pid)} ذخیره شد.", reply_markup=menu_kb)
                # اگر محصول در صف تأیید است کارت pending، وگرنه کارت محصول منتشرشده را دوباره نشان بده
                items = get_pending_products()
                _is_pending = any(int(it.get("id") or 0) == int(pid) for it in items)
                if _is_pending and items:
                    await _send_pending_card(msg, max(0, min(idx, len(items) - 1)))
                else:
                    from giso.shop.bot.admin_menu import product_card_with_actions
                    _ptxt, _pkb = product_card_with_actions(int(pid))
                    if _ptxt and _pkb: await msg.reply_text(_ptxt, reply_markup=_pkb)
            else:
                await msg.reply_text("❌ ورودی نامعتبر بود.", reply_markup=menu_kb); _PENDING_EDIT[_edit_key] = _raw
            return True
        if state == "shop_admin_menu":
            from giso.shop.bot.admin_menu import shop_admin_menu_kb, products_summary_text, sales_report_text, get_pending_products
            if text == "🧾 سفارش‌های جدید": await _show_shop_orders_paged(msg, uid, 0, "admin"); return True
            if text == "📦 محصولات": await _show_products_list(msg, shop_admin_menu_kb()); return True
            if text == "🔍 جستجوی کد پیگیری":
                user_states[uid] = "shop_tracking_search"
                await msg.reply_text("🔍 کد پیگیری سفارش را وارد کنید:"); return True
            if text == "📊 گزارش فروش":
                await msg.reply_text("📊 گزارش‌های فروشگاه — یکی را انتخاب کنید:", reply_markup=_shop_reports_menu_kb()); return True
            return True
        if state == "shop_super_menu":
            from giso.shop.bot.admin_menu import get_pending_products
            from giso.shop.bot.super_menu import shop_super_menu_kb, settings_text
            if text == "🧾 سفارش‌های جدید": await _show_shop_orders_paged(msg, uid, 0, "super"); return True
            if text == "📦 محصولات": await _show_products_list(msg, shop_super_menu_kb()); return True
            if text in ("⏳ لیست محصولات منتظر تأیید", "✅ تأیید کانال"):
                if not get_pending_products(): await msg.reply_text("✅ محصول منتظر تأییدی وجود ندارد.", reply_markup=shop_super_menu_kb()); return True
                await msg.reply_text("⏳ محصولات منتظر تأیید — کارت‌ها را مرور کنید:", reply_markup=shop_super_menu_kb()); await _send_pending_card(msg, 0); return True
            # گزینه «⚖️ تأیید محصول دستی» طبق مشخصات Giso حذف شد؛ حالت تأیید فقط از «⚙️ تنظیمات فروشگاه» مدیریت می‌شود.
            if text == "📊 گزارش فروش":
                await msg.reply_text("📊 گزارش‌های فروشگاه — یکی را انتخاب کنید:", reply_markup=_shop_reports_menu_kb()); return True
            if text == "🔍 جستجوی کد پیگیری": user_states[uid] = "shop_tracking_search"; await msg.reply_text("🔍 کد پیگیری سفارش را وارد کنید:"); return True
            if text == "⚙️ تنظیمات فروشگاه":
                from giso.shop.bot.super_menu import settings_kb
                await msg.reply_text(settings_text(), reply_markup=settings_kb()); return True
            return True
        if text != "🛍 فروشگاه": return False
        is_admin = bool(existing and existing.get("is_admin"))
        if _is_super_admin(uid, phone):
            from giso.shop.bot.super_menu import shop_super_menu_text, shop_super_menu_kb
            user_states[uid] = "shop_super_menu"; await msg.reply_text(shop_super_menu_text(), reply_markup=shop_super_menu_kb()); return True
        if is_admin:
            if not _shop_admin_allowed(uid): await msg.reply_text("⛔ شما به بخش فروشگاه دسترسی ندارید."); return True
            from giso.shop.bot.admin_menu import shop_admin_menu_text, shop_admin_menu_kb
            user_states[uid] = "shop_admin_menu"; await msg.reply_text(shop_admin_menu_text(), reply_markup=shop_admin_menu_kb()); return True
        from giso.shop.bot.user_menu import shop_user_menu_text, shop_user_kb
        user_states[uid] = "shop_user_menu"; await msg.reply_text(shop_user_menu_text(), reply_markup=shop_user_kb()); return True
    except Exception as e: logger.warning(f"handle_shop_bot_text: {e}"); return False


async def handle_shop_bot_callback(query, uid, phone, context=None) -> bool:
    data = query.data or ""
    if data == "shop_cfg_visibility" or data.startswith("shop_vis_toggle|"):
        try:
            await query.answer("این تنظیمات ساده‌سازی شده است", show_alert=True)
        except Exception:
            pass
        return True
    if not data.startswith("shop_"): return False
    try:
        is_super = _is_super_admin(uid, phone)
        is_normal_admin = bool(not is_super and _shop_admin_allowed(uid))
        if is_normal_admin:
            if (
                data.startswith((
                    "shop_cfg", "shop_disc", "shop_pen|", "shop_ch_app|", "shop_vis_",
                    "shop_rep|", "shop_edit|", "shop_stock|", "shop_del|",
                    "shop_pedit|", "shop_prod_pg|",
                ))
                or data == "shop_prod_back"
            ):
                await query.answer("این گزینه حذف شده است.", show_alert=True)
                return True
        # فیکس موضعی: msg و user_states قبلاً تعریف نشده بودند → NameError خاموش در callbackهای stateدار
        msg = query.message
        user_states = _BOT_USER_STATES if _BOT_USER_STATES is not None else {}
        # dispatch سفارش‌ها (وضعیت/صفحه‌بندی/بازگشت) و محصولات (ویرایش/موجودی/حذف) — قبلاً هرگز صدا زده نمی‌شدند
        if data.startswith(("shop_ord_pg|", "shop_ord_st|")) or data == "shop_back_menu":
            if not (is_super or _shop_admin_allowed(uid)): return True
            if await _handle_shop_order_callbacks(query, data, uid, phone, msg, user_states): return True
        # ═══ گزارش‌های فروشگاه (۶ دکمه مثل خرید مو) ═══
        if data.startswith("shop_rep|"):
            if not (is_super or _shop_admin_allowed(uid)): return True
            parts = data.split("|"); scope = parts[1] if len(parts) > 1 else "menu"
            try: r_idx = int(parts[2]) if len(parts) > 2 else 0
            except (ValueError, IndexError): r_idx = 0
            if scope == "menu":
                await query.message.reply_text("📊 گزارش‌های فروشگاه — یکی را انتخاب کنید:", reply_markup=_shop_reports_menu_kb())
            elif scope == "overall":
                await _show_shop_report(msg, uid)
            elif scope == "sales":
                await query.message.reply_text(_shop_sales_report_text(), reply_markup=_shop_reports_menu_kb())
            elif scope in ("pending", "shipped", "delivered", "rejected"):
                await _show_shop_orders_by_status(msg, uid, scope, r_idx)
            return True
        # ═══ ویرایش تفکیکی محصول منتشرشده (مثل کارت‌های منتظر تأیید) ═══
        if data.startswith("shop_pedit|"):
            if not (is_super or _shop_admin_allowed(uid)): return True
            parts = data.split("|")
            field = parts[1] if len(parts) > 1 else "fast"
            try: pid = int(parts[2])
            except (ValueError, IndexError): return True
            _PENDING_EDIT[str(query.from_user.id)] = (pid, 0, field)
            guide = {
                "fast": "✏️ نام جدید یا «نام | قیمت» را بفرستید:",
                "price": "💰 قیمت جدید (تومان) را بفرستید:",
                "desc": "📝 توضیحات جدید محصول را بفرستید:",
                "photo": "🖼 عکس جدید محصول را به‌صورت پیام تصویری بفرستید:",
            }.get(field, "✏️ مقدار جدید را بفرستید:")
            try: await query.answer()
            except Exception: pass
            await query.message.reply_text(f"{guide}\n(برای انصراف: لغو)")
            return True
        if data.startswith(("shop_edit|", "shop_stock|", "shop_del|")) or data == "shop_prod_back":
            if not (is_super or _shop_admin_allowed(uid)): return True
            if await _handle_product_callbacks(query, data, uid, phone, msg, user_states): return True
        if data.startswith("shop_ch_app|"):
            if not (is_super or _shop_admin_allowed(uid)): return True
            try: pid = int(data.split("|", 1)[1])
            except (ValueError, IndexError): await query.answer("⚠️ داده نامعتبر.", show_alert=True); return True
            ok = _publish_product(pid)
            try: await query.edit_message_text(f"✅ محصول #{pid} در فروشگاه منتشر شد." if ok else f"⚠️ محصول #{pid} منتشر نشد")
            except Exception: pass
            return True
        if data == "shop_cfg_pub":
            if not is_super: return True
            new_mode = _toggle_publish_mode(); await query.edit_message_text(f"⚙️ حالت انتشار فروشگاه: {'🟢 خودکار' if new_mode == 'auto' else '🔶 با تأیید'}"); return True
        if data == "shop_cfg_channel":
            if not is_super: return True
            from giso.shop.bot.super_menu import channel_settings_text
            user_states[uid] = "shop_channel_input"; await query.edit_message_text(channel_settings_text()); return True
        if data == "shop_cfg_discount":
            if not is_super: return True
            from giso.shop.bot.super_menu import discount_menu_text, discount_kb
            await query.edit_message_text(discount_menu_text(), reply_markup=discount_kb()); return True
        if data == "shop_disc_add":
            if not is_super: return True
            # طبق مشخصات: دو گزینه مجزا — کد عمومی یا کد مخصوص یک محصول (با لیست محصولات)
            from telegram import InlineKeyboardButton, InlineKeyboardMarkup
            await query.edit_message_text(
                "🎁 افزودن کد تخفیف\n━━━━━━━━━━━━━━━━\n"
                "نوع کد تخفیف را انتخاب کنید:",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🌐 کد عمومی (همه محصولات)", callback_data="shop_disc_new|all")],
                    [InlineKeyboardButton("📦 کد برای محصول خاص (لیست محصولات)", callback_data="shop_disc_prodpg|0")],
                    [InlineKeyboardButton("🔙 بازگشت", callback_data="shop_cfg_discount")],
                ]))
            return True
        if data.startswith("shop_disc_prodpg|"):
            if not is_super: return True
            from telegram import InlineKeyboardButton, InlineKeyboardMarkup
            try: dpg = int(data.split("|")[1])
            except (ValueError, IndexError): dpg = 0
            _PP = 8
            with get_giso_db_conn() as conn:
                _total = conn.execute("SELECT COUNT(*) FROM products WHERE in_stock=1").fetchone()[0] or 0
                _prows = conn.execute(
                    "SELECT id, name, price FROM products WHERE in_stock=1 ORDER BY id DESC LIMIT ? OFFSET ?",
                    (_PP, dpg * _PP)).fetchall()
            if not _prows:
                await query.answer("📭 محصول موجودی برای تخفیف نیست.", show_alert=True); return True
            _rows_kb = [[InlineKeyboardButton(f"#{r['id']} — {(r['name'] or '')[:26]} — {format_toman(r['price'] or 0)}",
                                              callback_data=f"shop_disc_new|{r['id']}")] for r in _prows]
            _nav = []
            if dpg > 0: _nav.append(InlineKeyboardButton("⬅️ قبلی", callback_data=f"shop_disc_prodpg|{dpg - 1}"))
            if (dpg + 1) * _PP < _total: _nav.append(InlineKeyboardButton("بعدی ➡️", callback_data=f"shop_disc_prodpg|{dpg + 1}"))
            if _nav: _rows_kb.append(_nav)
            _rows_kb.append([InlineKeyboardButton("🔙 بازگشت", callback_data="shop_disc_add")])
            await query.edit_message_text(
                "📦 انتخاب محصول برای کد تخفیف\n━━━━━━━━━━━━━━━━\nروی محصول موردنظر بزنید:", reply_markup=InlineKeyboardMarkup(_rows_kb))
            return True
        if data.startswith("shop_disc_new|"):
            if not is_super: return True
            _target = data.split("|", 1)[1]
            user_states[uid] = f"shop_disc_add_input|{_target}"
            _scope_txt = "همه محصولات" if _target == "all" else f"محصول #{_target}"
            await query.edit_message_text(
                f"🎁 کد تخفیف برای {_scope_txt}\n━━━━━━━━━━━━━━━━\n"
                "کد و درصد تخفیف را در یک پیام بفرستید.\n"
                "مثال: GISO20 20\n"
                "برای انصراف: «لغو»")
            return True
        if data.startswith("shop_prod_pg|"):
            try: pg = int(data.split("|")[1])
            except (ValueError, IndexError): return True
            from giso.shop.bot.admin_menu import shop_admin_menu_kb
            from giso.shop.bot.super_menu import shop_super_menu_kb
            menu_kb = shop_super_menu_kb() if is_super else shop_admin_menu_kb()
            await _show_products_list(msg, menu_kb, pg)
            return True
        if data.startswith("shop_disc_toggle|"):
            if not is_super: return True
            try:
                disc_id = int(data.split("|")[1])
                from giso.shop.logic.discount import toggle_discount_code
                toggle_discount_code(disc_id)
                from giso.shop.bot.super_menu import discount_menu_text, discount_kb
                await query.edit_message_text(discount_menu_text(), reply_markup=discount_kb())
            except Exception: pass
            return True
        if data in ("shop_cfg_referral", "shop_ref_amount", "shop_ref_max"):
            if not is_super: return True
            await query.edit_message_text("ℹ️ برنامه معرفی و پورسانت متوقف شده است."); return True
        if data == "shop_cfg_back":
            if not is_super: return True
            from giso.shop.bot.super_menu import settings_kb, settings_text
            await query.edit_message_text(settings_text(), reply_markup=settings_kb()); return True
        if data.startswith("shop_pen|"):
            if not (is_super or _shop_admin_allowed(uid)): return True
            parts = data.split("|"); action = parts[1] if len(parts) > 1 else ""
            if action == "noop": await query.answer(); return True
            if action == "nav":
                try: idx = int(parts[2])
                except (ValueError, IndexError): idx = 0
                await _edit_pending_card(query, idx, restricted=is_normal_admin); await query.answer(); return True
            if action in ("pub", "rej"):
                try: pid, idx = int(parts[2]), int(parts[3])
                except (ValueError, IndexError): await query.answer("⚠️ داده نامعتبر.", show_alert=True); return True
                ok = _publish_product(pid) if action == "pub" else _reject_product(pid)
                if ok and action == "pub":
                    # طبق مشخصات: پیام واضح انتشار + نام/دسته محصول برای اطمینان از دسته‌بندی درست
                    _pname = _pcat = ""
                    try:
                        with get_giso_db_conn() as conn:
                            _pr = conn.execute("SELECT name, category FROM products WHERE id=?", (pid,)).fetchone()
                        if _pr: _pname, _pcat = (_pr[0] or ""), (_pr[1] or "—")
                    except Exception: pass
                    try:
                        await query.message.reply_text(
                            f"✅ محصول «{_pname or pid}» روی فروشگاه سایت منتشر شد.\n"
                            f"🏷 دسته‌بندی: {_pcat}\n🌐 {_site_url()}/shop")
                    except Exception: pass
                    await _edit_pending_card(query, idx, notice=f"✅ منتشر شد — محصول #{_fa_num(pid)}", restricted=is_normal_admin)
                elif ok:
                    await _edit_pending_card(query, idx, notice=f"❌ رد شد — محصول #{_fa_num(pid)}", restricted=is_normal_admin)
                return True
            if action in ("edit", "editdesc", "editphoto", "editprice"):
                try: pid, idx = int(parts[2]), int(parts[3])
                except (ValueError, IndexError): return True
                field = {"edit": "fast", "editdesc": "desc", "editphoto": "photo", "editprice": "price"}[action]
                _PENDING_EDIT[str(query.from_user.id)] = (pid, idx, field); await query.answer()
                guide = {
                    "fast": "✏️ نام جدید یا «نام | قیمت» را بفرستید:",
                    "price": "💰 قیمت جدید (تومان) را بفرستید:",
                    "desc": "📝 توضیحات جدید را بفرستید:",
                    "photo": "🖼 عکس جدید را به‌صورت پیام تصویری بفرستید:",
                }[field]
                await query.message.reply_text(f"{guide}\n(محصول #{_fa_num(pid)} — برای انصراف: لغو)")
                return True
            return True
        return True
    except Exception as e:
        logger.warning(f"handle_shop_bot_callback: {e}")
        return True


async def _handle_shop_order_callbacks(query, data, uid, phone, msg, user_states):
    if data.startswith("shop_ord_pg|"):
        try: idx = int(data.split("|")[1])
        except (ValueError, IndexError): idx = 0
        await _show_shop_orders_paged(msg, uid, idx, "super" if _is_super_admin(uid, phone) else "admin")
        return True
    if data.startswith("shop_ord_st|"):
        parts = data.split("|")
        if len(parts) >= 3:
            try: oid, new_status = int(parts[1]), parts[2]
            except (ValueError, IndexError): return True
            order_phone = ""
            try:
                with get_giso_db_conn() as conn:
                    row = conn.execute("SELECT phone FROM product_orders WHERE id=?", (oid,)).fetchone()
                    if row:
                        order_phone = str(row["phone"] or "")
                    conn.execute("UPDATE product_orders SET status=? WHERE id=?", (new_status, oid)); conn.commit()
            except Exception as e:
                logger.warning(f"shop_ord_st update: {e}")
            status_fa = {"pending":"⏳ در حال بررسی","approved":"✅ تأیید شد","shipped":"🚚 در حال ارسال","delivered":"📦 تحویل شد","rejected":"❌ رد شد","completed":"✅ تکمیل شد","cancelled":"⛔ لغو شد"}.get(new_status, new_status)
            # اطلاع‌رسانی به کاربر صاحب سفارش (هم‌راستا با پنل سایت)
            if order_phone:
                try:
                    from giso.shop.logic import orders as _ord
                    _ord.notify_user_product_order(
                        order_phone,
                        f"🔔 به‌روزرسانی سفارش فروشگاه #{oid}\n"
                        f"📌 وضعیت جدید: {status_fa}\n"
                        f"می‌توانید جزئیات را در «فروشگاه من → سفارش‌های من» ببینید 🌸"
                    )
                except Exception as _ne:
                    logger.debug(f"shop_ord_st notify: {_ne}")
            try: await query.edit_message_text(f"✅ وضعیت سفارش #{oid} به «{status_fa}» تغییر کرد.")
            except Exception: pass
        return True
    if data == "shop_back_menu":
        if _is_super_admin(uid, phone):
            from giso.shop.bot.super_menu import shop_super_menu_text, shop_super_menu_kb
            user_states[uid] = "shop_super_menu"; await msg.reply_text(shop_super_menu_text(), reply_markup=shop_super_menu_kb())
        else:
            from giso.shop.bot.admin_menu import shop_admin_menu_text, shop_admin_menu_kb
            user_states[uid] = "shop_admin_menu"; await msg.reply_text(shop_admin_menu_text(), reply_markup=shop_admin_menu_kb())
        return True
    return False

async def _handle_product_callbacks(query, data, uid, phone, msg, user_states):
    from giso.shop.bot.admin_menu import product_card_with_actions
    if data.startswith("shop_edit|"):
        try: pid = int(data.split("|")[1])
        except (ValueError, IndexError): return True
        text, kb = product_card_with_actions(pid)
        if text and kb: await msg.reply_text(text, reply_markup=kb)
        else: await msg.reply_text("❌ محصول پیدا نشد.")
        return True
    if data.startswith("shop_stock|"):
        try: pid = int(data.split("|")[1])
        except (ValueError, IndexError): return True
        with get_giso_db_conn() as conn:
            row = conn.execute("SELECT in_stock FROM products WHERE id=?", (pid,)).fetchone()
            if row:
                new_val = 0 if row[0] else 1; conn.execute("UPDATE products SET in_stock=? WHERE id=?", (new_val, pid)); conn.commit(); await query.edit_message_text(f"{'✅ موجود شد' if new_val else '❌ ناموجود شد'} — محصول #{pid}")
        return True
    if data.startswith("shop_del|"):
        try: pid = int(data.split("|")[1])
        except (ValueError, IndexError): return True
        with get_giso_db_conn() as conn: conn.execute("DELETE FROM products WHERE id=?", (pid,)); conn.commit(); await query.edit_message_text(f"🗑 محصول #{pid} حذف شد.")
        return True
    if data == "shop_prod_back":
        from giso.shop.bot.admin_menu import products_summary_text
        result = products_summary_text(); text, rows = result if isinstance(result, tuple) else (result, [])
        await msg.reply_text(text)
        if rows:
            from telegram import InlineKeyboardButton, InlineKeyboardMarkup
            for r in rows: await msg.reply_text(f"{'✅' if r[3] else '❌'} #{r[0]} — {r[1]} — {format_toman(r[2])}", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("✏️ ویرایش", callback_data=f"shop_edit|{r[0]}")]]))
        return True
    return False

__all__ = ["handle_shop_bot_text", "handle_shop_bot_callback", "handle_shop_bot_photo", "_show_shop_orders_paged", "_show_shop_report", "_search_tracking_code", "_handle_product_callbacks"]
