# -*- coding: utf-8 -*-
"""giso/shop/bot/user_menu.py — منوی فروشگاه در ربات کاربر (فاز B)."""
from giso.base import _fa_num, get_giso_db_conn, normalize_phone, to_shamsi


def shop_user_menu_text() -> str:
    return (
        "🛍 فروشگاه گیسو\n"
        "━━━━━━━━━━━━━━━━\n"
        "🛒 مشاهده فروشگاه\n"
        "📦 سفارش‌های من\n"
        "🔔 اعلان موجودی\n"
        "━━━━━━━━━━━━━━━━\n"
        "گزینه مورد نظر را انتخاب کنید:"
    )


def shop_user_kb():
    from telegram import KeyboardButton, ReplyKeyboardMarkup
    return ReplyKeyboardMarkup(
        [
            [KeyboardButton("🛒 مشاهده فروشگاه")],
            [KeyboardButton("📦 سفارش‌های من"), KeyboardButton("🔔 اعلان موجودی")],
            [KeyboardButton("🔙 بازگشت")],
        ],
        resize_keyboard=True,
    )


def user_orders_text(phone) -> str:
    np = normalize_phone(phone or "")
    try:
        with get_giso_db_conn() as conn:
            rows = conn.execute(
                "SELECT po.id,po.checkout_id,po.tracking_code,po.quantity,po.status,po.created_at, "
                "COALESCE(p.name, 'محصول #' || po.product_id) AS pname,p.price "
                "FROM product_orders po LEFT JOIN products p ON p.id=po.product_id "
                "WHERE po.phone=? ORDER BY po.id DESC LIMIT 50", (np,)).fetchall()
    except Exception:
        return "❌ خطا در دریافت سفارش‌ها."
    if not rows:
        return "📦 هنوز سفارشی از فروشگاه ثبت نکرده‌اید.\n🌐 از سایت گیسو می‌توانید خرید کنید."
    lines = ["📦 سفارش‌های فروشگاه شما:", "━━━━━━━━━━━━━━━━"]
    st_fa = {"pending": "در انتظار", "approved": "تأیید", "shipped": "در حال ارسال",
             "delivered": "تحویل", "completed": "تکمیل", "cancelled": "لغو", "rejected": "رد"}
    groups, by_key = [], {}
    for row in rows:
        item = dict(row)
        checkout_id = int(item.get("checkout_id") or 0)
        key = ("checkout", checkout_id) if checkout_id else ("legacy", int(item["id"]))
        if key not in by_key:
            by_key[key] = {"checkout_id": checkout_id,
                           "tracking_code": item.get("tracking_code") or f"#{item['id']}",
                           "status": item.get("status") or "pending",
                           "created_at": item.get("created_at") or "", "items": [], "total": 0}
            groups.append(by_key[key])
        by_key[key]["items"].append(item)
        by_key[key]["total"] += int(item.get("price") or 0) * int(item.get("quantity") or 1)
    for group in groups[:8]:
        title = f"سفارش #{_fa_num(group['checkout_id'])}" if group["checkout_id"] else "سفارش قدیمی"
        items_text = "\n".join(
            f"• {item['pname']} × {_fa_num(item['quantity'] or 1)}" for item in group["items"]
        )
        total = _fa_num(format(group["total"], ","))
        status = st_fa.get(group["status"], group["status"])
        lines.append(
            f"{title}\n{items_text}\n"
            f"💰 {total} تومان • {status}\n"
            f"🔑 {group['tracking_code']}\n📅 {to_shamsi(group['created_at'],with_time=False)}"
        )
    return "\n\n".join(lines)


def user_notifies_text(phone) -> str:
    np = normalize_phone(phone or "")
    try:
        with get_giso_db_conn() as conn:
            rows = conn.execute(
                "SELECT sn.id, sn.product_id, sn.created_at, "
                "COALESCE(p.name, 'محصول #' || sn.product_id) AS pname "
                "FROM stock_notifies sn LEFT JOIN products p ON p.id = sn.product_id "
                "WHERE sn.phone=? ORDER BY sn.id DESC LIMIT 8", (np,)).fetchall()
    except Exception:
        return "❌ خطا در دریافت اعلان‌ها."
    if not rows:
        return "🔔 اعلان موجودی فعالی ندارید."
    lines = ["🔔 اعلان موجودی شما:", "━━━━━━━━━━━━━━━━"]
    for r in rows:
        lines.append(f"• {r['pname']} — ثبت: {to_shamsi(r['created_at'],with_time=False)}")
    return "\n".join(lines)
