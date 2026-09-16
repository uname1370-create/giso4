# -*- coding: utf-8 -*-
"""giso/shop/bot/admin_menu.py — منوی فروشگاه در ربات ادمین (فاز B)."""
from giso.base import _fa_num, get_giso_db_conn, to_shamsi
from giso.money import format_toman


def shop_admin_menu_text() -> str:
    return (
        "🛍 فروشگاه گیسو — پنل ادمین\n"
        "━━━━━━━━━━━━━━━━\n"
        "🧾 سفارش‌های جدید\n"
        "🔍 جستجوی کد پیگیری\n"
        "━━━━━━━━━━━━━━━━\n"
        "گزینه مورد نظر را انتخاب کنید:"
    )


def shop_admin_menu_kb():
    from telegram import KeyboardButton, ReplyKeyboardMarkup
    return ReplyKeyboardMarkup(
        [
            [KeyboardButton("🧾 سفارش‌های جدید"), KeyboardButton("🔍 جستجوی کد پیگیری")],
            [KeyboardButton("🔙 بازگشت")],
        ],
        resize_keyboard=True,
    )


def new_orders_text(limit: int = 10) -> str:
    """🧾 فقط سفارش‌های جدید/در حال بررسی؛ سفارش‌های قدیمی در این منو نمایش داده نمی‌شوند."""
    try:
        with get_giso_db_conn() as conn:
            rows = conn.execute(
                "SELECT po.id, po.customer_name, po.phone, po.status, po.created_at, "
                "p.name AS pname, p.price "
                "FROM product_orders po LEFT JOIN products p ON po.product_id=p.id "
                "WHERE po.status='pending' ORDER BY po.id DESC LIMIT ?", (int(limit),)).fetchall()
    except Exception:
        return "❌ خطا در دریافت سفارش‌ها."
    if not rows:
        return "🧾 سفارش جدیدی در انتظار بررسی نیست."
    st_fa = {"pending": "⏳ در حال بررسی", "shipped": "🚚 در حال ارسال", "delivered": "📦 ارسال شده"}
    lines = [f"🧾 سفارش‌های جدید فروشگاه ({_fa_num(len(rows))} مورد):", "━━━━━━━━━━━━━━━━"]
    for r in rows:
        lines.append(
            f"\n🔹 سفارش #{_fa_num(r['id'])} | {r['pname'] or '—'}"
            f"\n   👤 {r['customer_name'] or '—'} | 📱 {r['phone'] or '—'}"
            f"\n   📌 {st_fa.get(r['status'], r['status'])} | 💰 {format_toman(r['price'] or 0)}"
            f"\n   📅 {to_shamsi(r['created_at'])}"
        )
    return "\n".join(lines)


def get_pending_products(channel_only: bool = False) -> list:
    """Pending products; normal-admin callers can constrain this to channel imports."""
    try:
        with get_giso_db_conn() as conn:
            where = "publish_status='pending'"
            if channel_only:
                where += " AND source='channel'"
            rows = conn.execute(
                "SELECT id, name, description, price, category, image_path, in_stock "
                f"FROM products WHERE {where} ORDER BY id DESC").fetchall()
        return [dict(r) for r in rows]
    except Exception:
        return []


def pending_card_text(p: dict, idx: int, total: int) -> str:
    desc = (p.get("description") or "").strip()
    if len(desc) > 300:
        desc = desc[:300] + "…"
    stock = "✅ موجود" if p.get("in_stock") else "❌ ناموجود"
    if (p.get("image_path") or "").strip():
        photo_txt = "🖼 عکس: ✅ دارد"
    else:
        photo_txt = "🖼 عکس: ⚠️ ندارد — از دکمه «🖼 تعویض عکس» اضافه کنید"
    return (
        f"⏳ محصول منتظر تأیید {_fa_num(idx + 1)} از {_fa_num(total)}\n"
        "━━━━━━━━━━━━━━━━\n"
        f"📦 {p.get('name') or '—'} (#{_fa_num(p.get('id') or 0)})\n"
        f"💰 قیمت: {format_toman(p.get('price') or 0)}\n"
        f"🏷 دسته: {p.get('category') or '—'} | {stock}\n"
        f"{photo_txt}\n"
        + (f"\n📝 توضیحات:\n{desc}\n" if desc else "")
        + "━━━━━━━━━━━━━━━━\n"
        "یک عمل را انتخاب کنید یا با دکمه‌های قبلی/بعدی مرور کنید:"
    )


def pending_card_kb(pid: int, idx: int, total: int, restricted: bool = False):
    from telegram import InlineKeyboardButton, InlineKeyboardMarkup
    prev_i = (idx - 1) % total
    next_i = (idx + 1) % total
    if restricted:
        return InlineKeyboardMarkup([
            [InlineKeyboardButton("✅ انتشار", callback_data=f"shop_pen|pub|{pid}|{idx}"),
             InlineKeyboardButton("❌ رد", callback_data=f"shop_pen|rej|{pid}|{idx}")],
            [InlineKeyboardButton("⬅️ قبلی", callback_data=f"shop_pen|nav|{prev_i}"),
             InlineKeyboardButton(f"{_fa_num(idx + 1)}/{_fa_num(total)}", callback_data="shop_pen|noop"),
             InlineKeyboardButton("بعدی ➡️", callback_data=f"shop_pen|nav|{next_i}")],
        ])
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("✏️ ویرایش اطلاعات", callback_data=f"shop_pen|edit|{pid}|{idx}"),
         InlineKeyboardButton("💰 ویرایش قیمت", callback_data=f"shop_pen|editprice|{pid}|{idx}")],
        [InlineKeyboardButton("📝 توضیحات", callback_data=f"shop_pen|editdesc|{pid}|{idx}"),
         InlineKeyboardButton("🖼 تعویض عکس", callback_data=f"shop_pen|editphoto|{pid}|{idx}")],
        [InlineKeyboardButton("✅ انتشار", callback_data=f"shop_pen|pub|{pid}|{idx}"),
         InlineKeyboardButton("❌ رد", callback_data=f"shop_pen|rej|{pid}|{idx}")],
        [InlineKeyboardButton("⬅️ قبلی", callback_data=f"shop_pen|nav|{prev_i}"),
         InlineKeyboardButton(f"{_fa_num(idx + 1)}/{_fa_num(total)}", callback_data="shop_pen|noop"),
         InlineKeyboardButton("بعدی ➡️", callback_data=f"shop_pen|nav|{next_i}")],
    ])


def products_summary_text() -> str:
    try:
        with get_giso_db_conn() as conn:
            total = conn.execute("SELECT COUNT(*) FROM products").fetchone()[0] or 0
            published = conn.execute(
                "SELECT COUNT(*) FROM products WHERE publish_status IN ('published','',NULL)"
            ).fetchone()[0] or 0
            pending = conn.execute(
                "SELECT COUNT(*) FROM products WHERE publish_status='pending'"
            ).fetchone()[0] or 0
            rows = conn.execute(
                "SELECT id, name, price, in_stock FROM products ORDER BY id DESC LIMIT 10"
            ).fetchall()
    except Exception:
        return "❌ خطا در دریافت محصولات."
    lines = [
        "📦 محصولات فروشگاه",
        "━━━━━━━━━━━━━━━━",
        f"🧾 کل: {_fa_num(total)} | منتشر: {_fa_num(published)} | در انتظار: {_fa_num(pending)}",
    ]
    return "\n".join(lines), rows


def product_card_with_actions(product_id):
    """کارت محصول با دکمه‌های ویرایش/حذف/موجودی."""
    from telegram import InlineKeyboardButton, InlineKeyboardMarkup
    try:
        with get_giso_db_conn() as conn:
            row = conn.execute("SELECT * FROM products WHERE id=?", (int(product_id),)).fetchone()
        if not row:
            return None, None
        p = dict(row)
        stock_icon = "✅ موجود" if p.get("in_stock") else "❌ ناموجود"
        lines = [
            f"📦 محصول #{p['id']}",
            "━━━━━━━━━━━━━━━━",
            f"📝 نام: {p['name']}",
            f"💰 قیمت: {format_toman(p['price'])}",
            f"📂 دسته: {p.get('category') or '—'}",
            f"📌 وضعیت: {stock_icon}",
            f"📊 انتشار: {p.get('publish_status') or 'published'}",
        ]
        if p.get("description"):
            lines.append(f"📄 توضیح: {p['description'][:100]}")
        # طبق مشخصات: ویرایش تفکیکی مثل «محصولات منتظر تأیید» — هر فیلد گزینه جدا
        kb = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("✏️ نام/قیمت", callback_data=f"shop_pedit|fast|{p['id']}"),
                InlineKeyboardButton("💰 قیمت", callback_data=f"shop_pedit|price|{p['id']}"),
            ],
            [
                InlineKeyboardButton("📝 توضیحات", callback_data=f"shop_pedit|desc|{p['id']}"),
                InlineKeyboardButton("🖼 تعویض عکس", callback_data=f"shop_pedit|photo|{p['id']}"),
            ],
            [
                InlineKeyboardButton(
                    "❌ ناموجود کردن" if p.get("in_stock") else "✅ موجود کردن",
                    callback_data=f"shop_stock|{p['id']}"
                ),
                InlineKeyboardButton("🗑 حذف", callback_data=f"shop_del|{p['id']}"),
            ],
            [InlineKeyboardButton("🔙 بازگشت به لیست", callback_data="shop_prod_back")],
        ])
        return "\n".join(lines), kb
    except Exception:
        return None, None


def channel_pending_text() -> str:
    try:
        with get_giso_db_conn() as conn:
            rows = conn.execute(
                "SELECT id, name, price FROM products WHERE publish_status='pending' "
                "ORDER BY id DESC LIMIT 10").fetchall()
    except Exception:
        return "❌ خطا در دریافت محصولات کانال."
    if not rows:
        return "✅ محصول در انتظار تأییدی از کانال وجود ندارد."
    lines = ["✅ محصولات کانال در انتظار تأیید:", "━━━━━━━━━━━━━━━━"]
    for r in rows:
        lines.append(f"#{_fa_num(r['id'])} • {r['name']} — {format_toman(r['price'] or 0)}")
    return "\n".join(lines)


def sales_report_text() -> str:
    try:
        with get_giso_db_conn() as conn:
            total = conn.execute("SELECT COUNT(*) FROM product_orders").fetchone()[0] or 0
            completed = conn.execute(
                "SELECT COUNT(*) FROM product_orders WHERE status='delivered'"
            ).fetchone()[0] or 0
            revenue = conn.execute(
                "SELECT COALESCE(SUM(po.quantity * p.price),0) FROM product_orders po "
                "LEFT JOIN products p ON p.id=po.product_id WHERE po.status='delivered'"
            ).fetchone()[0] or 0
            top = conn.execute(
                "SELECT p.name, COALESCE(SUM(po.quantity),0) AS q FROM product_orders po "
                "LEFT JOIN products p ON p.id=po.product_id "
                "GROUP BY p.id ORDER BY q DESC LIMIT 3").fetchall()
    except Exception:
        return "❌ خطا در دریافت گزارش."
    lines = [
        "📊 گزارش فروش فروشگاه",
        "━━━━━━━━━━━━━━━━",
        f"🧾 کل سفارش‌ها: {_fa_num(total)}",
        f"📦 ارسال‌شده: {_fa_num(completed)}",
        f"💰 فروش ارسال‌شده: {format_toman(revenue)}",
    ]
    if top:
        lines.append("━━━━━━━━━━━━━━━━")
        lines.append("🏆 پرفروش‌ترین‌ها:")
        for r in top:
            lines.append(f"• {r['name']} — {_fa_num(r['q'])} عدد")
    return "\n".join(lines)
