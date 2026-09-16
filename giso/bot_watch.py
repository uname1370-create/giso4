# -*- coding: utf-8 -*-
"""giso/bot_watch.py — متن‌های «👁 نظارت» سوپرادمین در ربات (فقط خواندنی).

هیچ عملیات تغییردهنده‌ای در این ماژول وجود ندارد؛ فقط آمار زنده و آخرین موارد
هر بخش (خرید مو / آنالیز / فروشگاه) از دیتابیس واقعی خوانده می‌شود.
"""
from __future__ import annotations

from giso.base import get_giso_db_conn, _fa_num


def _today() -> str:
    import time
    return time.strftime("%Y-%m-%d")


def watch_menu_text() -> str:
    return (
        "👁 نظارت زنده بر بخش‌ها\n"
        "━━━━━━━━━━━━━━━━\n"
        "یکی از بخش‌ها را انتخاب کنید تا وضعیت فعلی و آخرین موارد آن را ببینید.\n"
        "این بخش فقط نمایشی است و هیچ تغییری ایجاد نمی‌کند."
    )


def watch_hair_text() -> str:
    """💇 نظارت خرید مو — شمارش وضعیت‌ها + ۳ درخواست اخیر."""
    with get_giso_db_conn() as conn:
        c = conn.cursor()
        rows = c.execute(
            "SELECT status, COUNT(*) FROM hair_orders GROUP BY status"
        ).fetchall()
        counts = {r[0]: r[1] for r in rows}
        total = sum(counts.values())
        today = c.execute(
            "SELECT COUNT(*) FROM hair_orders WHERE created_at LIKE ?",
            (_today() + "%",)).fetchone()[0]
        latest = c.execute(
            "SELECT id, customer_name, phone, status, length_cm, final_price, created_at "
            "FROM hair_orders ORDER BY id DESC LIMIT 3"
        ).fetchall()
    st_label = {
        "pending": "🆕 در انتظار بررسی", "reviewing": "🔍 در حال بررسی",
        "approved": "✅ تأیید شده", "completed": "🏁 تکمیل شده",
        "rejected": "❌ رد شده", "paid": "💰 تسویه شده",
        "consented": "📝 رضایت ثبت‌شده", "priced": "💰 قیمت‌گذاری شده",
    }
    lines = [
        "💇 نظارت خرید مو",
        "━━━━━━━━━━━━━━━━",
        f"📦 کل درخواست‌ها: {_fa_num(total)} | 📅 امروز: {_fa_num(today)}",
        "",
    ]
    for k, lbl in st_label.items():
        if counts.get(k):
            lines.append(f"{lbl}: {_fa_num(counts[k])}")
    for k, v in counts.items():
        if k not in st_label:
            lines.append(f"📌 {k}: {_fa_num(v)}")
    lines.append("")
    lines.append("🕓 ۳ درخواست اخیر:")
    if not latest:
        lines.append("— هنوز درخواستی ثبت نشده است.")
    for r in latest:
        price = r[5] or "—"
        lines.append(
            f"\n🔹 #{_fa_num(r[0])} | {r[1] or '—'} | 📱 {r[2] or '—'}\n"
            f"   📏 {r[4] or '—'}cm | 💰 {price} | وضعیت: {r[3]}"
        )
    return "\n".join(lines)


def watch_analysis_text() -> str:
    """🔬 نظارت آنالیز — شمارش نوع‌ها + مشاوره/محصول + ۳ مورد اخیر."""
    with get_giso_db_conn() as conn:
        c = conn.cursor()
        total = c.execute("SELECT COUNT(*) FROM analyses").fetchone()[0]
        hair_n = c.execute("SELECT COUNT(*) FROM analyses WHERE type='hair'").fetchone()[0]
        skin_n = c.execute("SELECT COUNT(*) FROM analyses WHERE type='skin'").fetchone()[0]
        today = c.execute(
            "SELECT COUNT(*) FROM analyses WHERE created_at LIKE ?",
            (_today() + "%",)).fetchone()[0]
        latest = c.execute(
            "SELECT id, phone, type, created_at FROM analyses ORDER BY id DESC LIMIT 3"
        ).fetchall()
        # مشاوره و محصولات درخواستی (اگر جداول موجود باشند)
        consults = prods = 0
        try:
            consults = c.execute(
                "SELECT COUNT(*) FROM consultant_requests WHERE status='pending'"
            ).fetchone()[0]
        except Exception:
            pass
        try:
            prods = c.execute(
                "SELECT COUNT(*) FROM product_requests WHERE status='pending'"
            ).fetchone()[0]
        except Exception:
            pass
    lines = [
        "🔬 نظارت آنالیز هوشمند",
        "━━━━━━━━━━━━━━━━",
        f"📊 کل آنالیزها: {_fa_num(total)} | 📅 امروز: {_fa_num(today)}",
        f"💇 آنالیز مو: {_fa_num(hair_n)} | ✨ آنالیز پوست: {_fa_num(skin_n)}",
        f"💬 مشاوره‌های در انتظار: {_fa_num(consults)} | 🛒 محصول درخواستی در انتظار: {_fa_num(prods)}",
        "",
        "🕓 ۳ آنالیز اخیر:",
    ]
    if not latest:
        lines.append("— هنوز آنالیزی ثبت نشده است.")
    for r in latest:
        t_lbl = "💇 مو" if r[2] == "hair" else ("✨ پوست" if r[2] == "skin" else (r[2] or "—"))
        lines.append(f"🔹 #{_fa_num(r[0])} | {t_lbl} | 📱 {r[1] or '—'} | 📅 {r[3]}")
    return "\n".join(lines)


def watch_shop_text() -> str:
    """🛍 نظارت فروشگاه — محصولات/سفارش‌ها/انتظار تأیید + ۳ سفارش اخیر."""
    with get_giso_db_conn() as conn:
        c = conn.cursor()
        prod_total = c.execute("SELECT COUNT(*) FROM products").fetchone()[0]
        prod_pending = c.execute(
            "SELECT COUNT(*) FROM products WHERE publish_status='pending'").fetchone()[0]
        prod_pub = c.execute(
            "SELECT COUNT(*) FROM products WHERE publish_status='published'").fetchone()[0]
        o_rows = c.execute(
            "SELECT status, COUNT(*) FROM product_orders GROUP BY status").fetchall()
        o_counts = {r[0]: r[1] for r in o_rows}
        o_total = sum(o_counts.values())
        today_o = c.execute(
            "SELECT COUNT(*) FROM product_orders WHERE created_at LIKE ?",
            (_today() + "%",)).fetchone()[0]
        rev = c.execute(
            "SELECT COALESCE(SUM(p.price),0) FROM product_orders po "
            "JOIN products p ON po.product_id=p.id WHERE po.status IN ('approved','completed')"
        ).fetchone()[0]
        latest = c.execute(
            "SELECT po.id, po.customer_name, p.name, po.status, po.created_at "
            "FROM product_orders po LEFT JOIN products p ON po.product_id=p.id "
            "ORDER BY po.id DESC LIMIT 3"
        ).fetchall()
    lines = [
        "🛍 نظارت فروشگاه",
        "━━━━━━━━━━━━━━━━",
        f"📦 محصولات: {_fa_num(prod_total)} (منتشر: {_fa_num(prod_pub)} | ⏳ منتظر تأیید: {_fa_num(prod_pending)})",
        f"🧾 کل سفارش‌ها: {_fa_num(o_total)} | 📅 امروز: {_fa_num(today_o)}",
    ]
    o_label = {"pending": "🆕 در انتظار", "approved": "✅ تأیید شده",
               "completed": "🏁 تکمیل شده", "cancelled": "❌ لغو شده"}
    for k, lbl in o_label.items():
        if o_counts.get(k):
            lines.append(f"{lbl}: {_fa_num(o_counts[k])}")
    lines.append(f"💰 مجموع مبلغ سفارش‌های تأییدشده: {_fa_num(rev)} تومان")
    lines.append("")
    lines.append("🕓 ۳ سفارش اخیر:")
    if not latest:
        lines.append("— هنوز سفارشی ثبت نشده است.")
    for r in latest:
        lines.append(
            f"\n🔹 سفارش #{_fa_num(r[0])} | {r[2] or '—'}\n"
            f"   👤 {r[1] or '—'} | وضعیت: {r[3]} | 📅 {r[4]}"
        )
    return "\n".join(lines)
