# -*- coding: utf-8 -*-
"""giso/marketing.py — گزارش بازاریابی روزانه (فاز P2)

یک منبع مشترک برای ساخت «خلاصه بازاریابی روزانه» که هم در ویجت سایت
(دستور ادمین «گزارش بازاریابی») و هم در ارسال روزانه به بله سوپرادمین استفاده می‌شود.
"""
from __future__ import annotations

import time

from giso.base import get_giso_db_conn, _fa_num


def _q1(conn, sql, params=()):
    try:
        row = conn.execute(sql, params).fetchone()
        return int((row[0] if row else 0) or 0)
    except Exception:
        return 0


def daily_digest_text(date: str | None = None, html: bool = True) -> str:
    """متن خلاصه بازاریابی یک روز — اعداد واقعی از دیتابیس."""
    today = date or time.strftime("%Y-%m-%d")
    week = time.strftime("%Y-%m-%d", time.localtime(time.time() - 6 * 86400))
    with get_giso_db_conn() as conn:
        users_today = _q1(conn, "SELECT COUNT(*) FROM giso_web_auth WHERE created_at >= ?", (today,))
        users_week = _q1(conn, "SELECT COUNT(*) FROM giso_web_auth WHERE created_at >= ?", (week,))
        analyses_today = _q1(conn, "SELECT COUNT(*) FROM analyses WHERE created_at >= ?", (today,))
        orders_today = _q1(conn, "SELECT COUNT(*) FROM product_orders WHERE created_at >= ?", (today,))
        orders_done_today = _q1(
            conn, "SELECT COUNT(*) FROM product_orders WHERE status='completed' AND created_at >= ?", (today,))
        rev_today = 0
        try:
            row = conn.execute(
                "SELECT COALESCE(SUM(p.price * o.quantity),0) FROM product_orders o "
                "JOIN products p ON p.id=o.product_id "
                "WHERE o.status='completed' AND o.created_at >= ?", (today,)).fetchone()
            rev_today = int((row[0] if row else 0) or 0)
        except Exception:
            rev_today = 0
        hair_today = _q1(conn, "SELECT COUNT(*) FROM hair_orders WHERE created_at >= ?", (today,))
        hair_wait = _q1(conn, "SELECT COUNT(*) FROM hair_orders WHERE status IN ('pending','reviewing')")
        pend_orders = _q1(conn, "SELECT COUNT(*) FROM product_orders WHERE status='pending'")
        pend_products = _q1(conn, "SELECT COUNT(*) FROM products WHERE publish_status='pending'")
        reviews_today = _q1(conn, "SELECT COUNT(*) FROM reviews WHERE created_at >= ?", (today,))
        widget_msgs_today = 0
        try:
            widget_msgs_today = _q1(
                conn, "SELECT COUNT(*) FROM giso_widget_chats WHERE message_role='user' AND created_at >= ?", (today,))
        except Exception:
            pass
        top_pages = []
        try:
            top_pages = [
                (r[0], r[1]) for r in conn.execute(
                    "SELECT page_path, COUNT(*) FROM giso_widget_chats "
                    "WHERE message_role='user' AND created_at >= ? GROUP BY page_path ORDER BY COUNT(*) DESC LIMIT 3",
                    (week,)).fetchall()
            ]
        except Exception:
            pass
    lines = [
        f"📣 گزارش بازاریابی روزانه گیسو | {today}",
        "━━━━━━━━━━━━━━━━",
        f"👥 عضو جدید: {_fa_num(users_today)} امروز ({_fa_num(users_week)} در ۷ روز)",
        f"🔬 آنالیز جدید: {_fa_num(analyses_today)} | ⭐ نظر جدید: {_fa_num(reviews_today)}",
        f"💇 درخواست فروش مو امروز: {_fa_num(hair_today)} (در انتظار بررسی: {_fa_num(hair_wait)})",
        "━━━━━━━━━━━━━━━━",
        f"🛍 سفارش امروز: {_fa_num(orders_today)} (تکمیل‌شده: {_fa_num(orders_done_today)})",
        f"💰 درآمد امروز: {_fa_num(rev_today)} تومان",
        f"⏳ سفارش در انتظار: {_fa_num(pend_orders)} | 📦 محصول منتظر تأیید: {_fa_num(pend_products)}",
    ]
    if widget_msgs_today:
        lines.insert(4, f"💬 گفتگوی ویجت امروز: {_fa_num(widget_msgs_today)}")
    if top_pages:
        lines.append("━━━━━━━━━━━━━━━━")
        lines.append("📄 صفحات پرتقاضای ۷ روز اخیر (ویجت):")
        for p, c in top_pages:
            lines.append(f"• {p or '—'} ({_fa_num(c)})")
    lines.append("━━━━━━━━━━━━━━━━")
    lines.append("🔗 پنل: /admin/reports")
    out = "\n".join(lines)
    if not html:
        out = out.replace("", "").replace("", "")
    return out


CONFIG_KEY_LAST = "marketing_digest_last_date"
CONFIG_KEY_ENABLED = "marketing_digest_enabled"


def is_digest_enabled() -> bool:
    try:
        with get_giso_db_conn() as conn:
            row = conn.execute(
                "SELECT value FROM giso_config WHERE key=?", (CONFIG_KEY_ENABLED,)).fetchone()
        return True if not row else str(row[0]) != "0"
    except Exception:
        return True


def maybe_send_daily_digest(force: bool = False) -> bool:
    """ارسال روزانه به بله سوپرادمین — حداکثر یک‌بار در روز (lazy، بدون scheduler).

    با force=True بدون توجه به تاریخ ارسال می‌کند (برای تست/دستور دستی).
    در نبود توکن یا خطای شبکه بی‌صدا False برمی‌گرداند.
    """
    if not is_digest_enabled() and not force:
        return False
    today = time.strftime("%Y-%m-%d")
    try:
        with get_giso_db_conn() as conn:
            row = conn.execute(
                "SELECT value FROM giso_config WHERE key=?", (CONFIG_KEY_LAST,)).fetchone()
            if row and row[0] == today and not force:
                return False
    except Exception:
        return False
    try:
        from giso.panel.modules.notifications import _send_bot_destination
        text = daily_digest_text(today)
        send_status = _send_bot_destination(text, "super", notification_id=0)
    except Exception:
        return False
    # علامت‌گذاری تاریخ فقط وقتی: ارسال موفق بوده، یا توکن تنظیم نشده (تا اسپم retry نشود).
    # در خطای شبکه، تلاش بعدی یک ساعت بعد دوباره انجام می‌شود.
    if send_status in ("sent", "no_token", "no_targets"):
        try:
            with get_giso_db_conn() as conn:
                conn.execute(
                    "INSERT INTO giso_config (key, value) VALUES (?, ?) "
                    "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                    (CONFIG_KEY_LAST, today))
                conn.commit()
        except Exception:
            pass
    return send_status == "sent"
