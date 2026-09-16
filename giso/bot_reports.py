# -*- coding: utf-8 -*-
"""
giso/bot_reports.py — گزارش‌های متنی ربات گیسو (فاز 3.2)

گزارش‌های «فروش مو» از دیتابیس واقعی giso.db خوانده می‌شوند و به‌صورت متن HTML ساده برای ارسال در ربات تولید می‌شوند.
"""
import re
import logging

from giso.base import get_giso_db_conn, _fa_num

logger = logging.getLogger("giso_bot_reports")

_FA_EN_DIGITS = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")


def _extract_amount(text) -> int:
    """استخراج عدد تومان از متن قیمت (پشتیبانی ارقام فارسی/انگلیسی)."""
    digits = re.sub(r"[^\d]", "", str(text or "").translate(_FA_EN_DIGITS))
    try:
        return int(digits) if digits else 0
    except (TypeError, ValueError):
        return 0


def hair_sale_reports_text(scope: str = "overall") -> str:
    """
    گزارش متنی فروش مو بر اساس scope:
      overall | reviewing | rejected | pending | objections | sales | commission
    """
    try:
        with get_giso_db_conn() as conn:
            total = conn.execute("SELECT COUNT(*) AS c FROM hair_orders").fetchone()["c"] or 0
            pending = conn.execute("SELECT COUNT(*) AS c FROM hair_orders WHERE status='pending'").fetchone()["c"] or 0
            reviewing = conn.execute("SELECT COUNT(*) AS c FROM hair_orders WHERE status='reviewing'").fetchone()["c"] or 0
            priced = conn.execute("SELECT COUNT(*) AS c FROM hair_orders WHERE status='priced'").fetchone()["c"] or 0
            approved = conn.execute("SELECT COUNT(*) AS c FROM hair_orders WHERE status='approved'").fetchone()["c"] or 0
            completed = conn.execute("SELECT COUNT(*) AS c FROM hair_orders WHERE status='completed'").fetchone()["c"] or 0
            rejected = conn.execute("SELECT COUNT(*) AS c FROM hair_orders WHERE status='rejected'").fetchone()["c"] or 0
            objections = conn.execute(
                "SELECT COUNT(*) AS c FROM hair_messages WHERE sender='user' AND message LIKE '📝 اعتراض:%'"
            ).fetchone()["c"] or 0
            price_rows = conn.execute(
                "SELECT final_price FROM hair_orders WHERE status IN ('completed','approved') AND final_price != ''"
            ).fetchall()

        total_sales = sum(_extract_amount(r["final_price"]) for r in price_rows)

        if scope == "overall":
            lines = [
                "📊 گزارش کلی خرید مو",
                "━━━━━━━━━━━━━━━━",
                f"🧾 کل درخواست‌ها: {_fa_num(total)}",
                f"⏳ در انتظار بررسی: {_fa_num(pending)}",
                f"🔍 در حال بررسی: {_fa_num(reviewing)}",
                f"💰 قیمت‌گذاری‌شده: {_fa_num(priced)}",
                f"✅ تاییدشده: {_fa_num(approved)}",
                f"📦 تکمیل‌شده: {_fa_num(completed)}",
                f"❌ ردشده: {_fa_num(rejected)}",
                f"📝 اعتراض‌ها: {_fa_num(objections)}",
                f"🏦 فروش کلی (تکمیل+تایید): {_fa_num(total_sales)} تومان",
            ]
        elif scope == "reviewing":
            lines = ["🔍 در حال بررسی‌ها (خرید مو)", f"تعداد: {_fa_num(reviewing)}"]
        elif scope == "rejected":
            lines = ["❌ رد شده‌ها (خرید مو)", f"تعداد: {_fa_num(rejected)}"]
        elif scope == "pending":
            lines = ["⏳ در انتظار (خرید مو)", f"تعداد: {_fa_num(pending)}"]
        elif scope == "objections":
            lines = ["📝 اعتراض‌ها (خرید مو)", f"تعداد: {_fa_num(objections)}"]
        elif scope == "sales":
            lines = [
                "💰 فروش کلی خرید مو",
                f"جمع قیمت نهایی (تکمیل+تایید): {_fa_num(total_sales)} تومان",
                f"تعداد سفارش‌های تکمیل‌شده: {_fa_num(completed)}",
                f"تعداد تاییدشده: {_fa_num(approved)}",
            ]
        elif scope == "commission":
            lines = ["ℹ️ برنامه معرفی و پورسانت متوقف شده است."]
        else:
            lines = ["❌ گزارش نامعتبر."]
        return "\n".join(lines)
    except Exception as e:
        logger.warning(f"hair_sale_reports_text: {e}")
        return "❌ خطا در تولید گزارش."


__all__ = ["hair_sale_reports_text"]
