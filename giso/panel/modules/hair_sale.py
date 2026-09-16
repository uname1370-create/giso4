# -*- coding: utf-8 -*-
"""panel/modules/hair_sale.py — مدیریت فروش مو (فاز 4.8) + گزارش‌ها و پورسانت (فاز 5).

فاز 5:
  - گزارش‌ها: کلی / در حال بررسی / رد شده / در انتظار / فروش کلی / اعتراض‌ها (دیتابیس واقعی)
  - تنظیم پورسانت (درصدی / مبلغ ثابت / حالت فعال) — همان کلیدهای مشترک ربات (referral_commission_*)
"""
import logging
import re

from flask import request, redirect, url_for, flash

from giso.models import HairOrder
from giso.base import get_giso_db_conn
from giso.hair_sale import DEFAULT_HAIR_PRICES, get_hair_price_from_config
from giso.panel.permissions import current_role_and_perms

logger = logging.getLogger("giso_panel_hair")

_FA_EN_DIGITS = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")


def _extract_amount(text) -> int:
    """استخراج مبلغ تومان از متن قیمت (ارقام فارسی/انگلیسی) — مثل ربات."""
    digits = re.sub(r"[^\d]", "", str(text or "").translate(_FA_EN_DIGITS))
    try:
        return int(digits) if digits else 0
    except (TypeError, ValueError):
        return 0


def _q1(conn, sql, params=()):
    try:
        row = conn.execute(sql, params).fetchone()
        return int((row[0] if row else 0) or 0)
    except Exception:
        return 0


def get_reports() -> dict:
    """اعداد گزارش‌های فروش مو از دیتابیس واقعی."""
    out = {
        "total": 0, "pending": 0, "reviewing": 0, "priced": 0,
        "approved": 0, "completed": 0, "rejected": 0, "objections": 0,
        "total_sales": 0,
    }
    try:
        with get_giso_db_conn() as conn:
            out["total"] = _q1(conn, "SELECT COUNT(*) FROM hair_orders")
            out["pending"] = _q1(conn, "SELECT COUNT(*) FROM hair_orders WHERE status='pending'")
            out["reviewing"] = _q1(conn, "SELECT COUNT(*) FROM hair_orders WHERE status='reviewing'")
            out["priced"] = _q1(conn, "SELECT COUNT(*) FROM hair_orders WHERE status='priced'")
            out["approved"] = _q1(conn, "SELECT COUNT(*) FROM hair_orders WHERE status='approved'")
            out["completed"] = _q1(conn, "SELECT COUNT(*) FROM hair_orders WHERE status='completed'")
            out["rejected"] = _q1(conn, "SELECT COUNT(*) FROM hair_orders WHERE status='rejected'")
            out["objections"] = _q1(
                conn, "SELECT COUNT(*) FROM hair_messages WHERE sender='user' AND message LIKE '📝 اعتراض:%'")
            rows = conn.execute(
                "SELECT final_price FROM hair_orders "
                "WHERE status IN ('completed','approved') AND final_price != ''").fetchall()
            out["total_sales"] = sum(_extract_amount(r["final_price"]) for r in rows)
    except Exception as e:
        logger.error(f"panel hair reports: {e}")
    return out


def handle_commission():
    """مسیر سازگاری فرم‌های قدیمی؛ برنامه پورسانت متوقف است."""
    flash("برنامه معرفی و پورسانت متوقف شده است.", "info")
    return redirect(url_for("panel.hair_sale"))


HAIR_PAGE_SIZE = 25


def context():
    h_status = (request.args.get("h_status") or "all").strip().lower()
    try:
        page = max(1, int(request.args.get("page", 1) or 1))
    except (TypeError, ValueError):
        page = 1
    hair_orders = []
    total_orders = 0
    total_pages = 1
    try:
        # فاز جامع UX: فیلترهای ۳گروهی (در حال بررسی / قیمت ثبت‌شده / رد شد) روی وضعیت‌های دیتابیس
        q = HairOrder.query
        if h_status == "review":      # در انتظار + در حال بررسی
            q = q.filter(HairOrder.status.in_(["pending", "reviewing"]))
        elif h_status == "priced":    # قیمت نهایی ثبت‌شده (قیمت‌گذاری/تأیید/تکمیل)
            q = q.filter(HairOrder.status.in_(["priced", "approved", "completed"]))
        elif h_status == "rejected":  # رد شد
            q = q.filter_by(status="rejected")
        elif h_status in ("pending", "reviewing", "approved", "completed"):
            q = q.filter_by(status=h_status)
        else:
            h_status = "all"
        # ── Task C: صفحه‌بندی (قبلاً کل جدول رندر می‌شد) ──
        total_orders = q.count()
        total_pages = max(1, (total_orders + HAIR_PAGE_SIZE - 1) // HAIR_PAGE_SIZE)
        page = min(page, total_pages)
        hair_orders = (q.order_by(HairOrder.id.desc())
                        .limit(HAIR_PAGE_SIZE)
                        .offset((page - 1) * HAIR_PAGE_SIZE)
                        .all())
    except Exception as e:
        logger.error(f"panel hair_sale: {e}")
    # ── Task B: رفع N+1 ──
    # قبلاً به‌ازای هر سفارش یک کوئری جدا اجرا می‌شد (۱ + N).
    # اکنون پیام‌های همه سفارش‌های همین صفحه با یک کوئری گروهی خوانده می‌شوند.
    hair_messages_dict = {}
    try:
        order_ids = [ho.id for ho in hair_orders]
        hair_messages_dict = {oid: [] for oid in order_ids}
        if order_ids:
            marks = ",".join("?" * len(order_ids))
            with get_giso_db_conn() as conn:
                rows = conn.execute(
                    "SELECT * FROM hair_messages WHERE order_id IN (%s) ORDER BY order_id, id ASC" % marks,
                    order_ids).fetchall()
            for r in rows:
                hair_messages_dict.setdefault(r["order_id"], []).append(dict(r))
    except Exception as e:
        logger.debug(f"panel hair messages batch: {e}")
    hair_prices_dict = {}
    try:
        for k in DEFAULT_HAIR_PRICES.keys():
            hair_prices_dict[k] = get_hair_price_from_config(k)
    except Exception:
        hair_prices_dict = DEFAULT_HAIR_PRICES.copy()
    # حداقل طول مو + فعال/غیرفعال شرط
    hair_min_length = "50"
    hair_min_enabled = "1"
    try:
        from giso_admin import get_giso_config
        hair_min_length = get_giso_config("hair_min_length", "50") or "50"
        hair_min_enabled = get_giso_config("hair_min_enabled", "1") or "1"
    except Exception:
        pass
    role, perms, bale_id = current_role_and_perms()
    site_visible = {
        key: True
        for key in ("approve", "reject", "price", "note", "message", "reports", "objections")
    }
    site_visible["commission"] = role == "super"
    return {
        "hair_orders": hair_orders,
        "hair_messages_dict": hair_messages_dict,
        "hair_prices_dict": hair_prices_dict,
        "hair_prices_defaults": DEFAULT_HAIR_PRICES,
        "hair_min_length": hair_min_length,
        "hair_min_enabled": hair_min_enabled,
        "h_status": h_status,
        "report": get_reports(),
        "site_visible": site_visible,
        "fmt_amount": _fmt_amount,
        # ── Task C: داده‌های صفحه‌بندی برای قالب ──
        "page": page,
        "total_pages": total_pages,
        "total_orders": total_orders,
        "page_size": HAIR_PAGE_SIZE,
        "has_prev": page > 1,
        "has_next": page < total_pages,
        # ── Task A: UI و اجرا از یک منبع (نمایان = مجاز) ──
        "action_allowed": _hair_action_allowed(),
    }


def _hair_action_allowed() -> dict:
    """وضعیت مجاز بودن اکشن‌های فروش مو برای نقش جاری (همان منبعی که handler اجرا می‌کند)."""
    try:
        from giso.panel.authz import visible_hair_actions
        return visible_hair_actions()
    except Exception as exc:
        logger.debug(f"hair action_allowed: {exc}")
        return {}


def _fmt_amount(v) -> str:
    """نمایش مبلغ تومان با جداکننده سه‌رقمی (ورودی می‌تواند متن/عدد فارسی باشد)."""
    n = _extract_amount(v)
    return "{:,}".format(n) if n else (str(v or "—"))
