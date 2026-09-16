# -*- coding: utf-8 -*-
"""giso/panel/modules/reports.py — ماژول «📈 گزارشات» یک‌صفحه‌ای (فاز P0 سایت)

خلاصه عملکرد همه بخش‌ها در یک صفحه:
- شمارش‌های امروز / ۷ روز اخیر / ۳۰ روز اخیر (کاربران، آنالیز، فروش مو، سفارش‌ها، نظرات)
- درآمد سفارش‌های تکمیل‌شده (۷ و ۳۰ روز)
- پرفروش‌ترین محصولات (۳۰ روز اخیر)
- روند ۷ روز گذشته به تفکیک روز (برای نگاه یک‌طرفه)
- آخرین رویدادهای مهم (اعلان‌های امروز) — اگر جدول اعلان‌ها موجود باشد
"""
from __future__ import annotations

import time

from giso.base import get_giso_db_conn


def _q1(sql, params=()):
    try:
        with get_giso_db_conn() as conn:
            row = conn.execute(sql, params).fetchone()
            return int((row[0] if row else 0) or 0)
    except Exception:
        return 0


def _rows(sql, params=()):
    try:
        with get_giso_db_conn() as conn:
            return [dict(r) for r in conn.execute(sql, params).fetchall()]
    except Exception:
        return []


def context():
    today = time.strftime("%Y-%m-%d")
    day7_ago = time.strftime("%Y-%m-%d", time.localtime(time.time() - 7 * 86400))
    day30_ago = time.strftime("%Y-%m-%d", time.localtime(time.time() - 30 * 86400))

    def _cnt(table, col, since):
        return _q1(f"SELECT COUNT(*) FROM {table} WHERE {col} >= ?", (since,))

    ctx = {
        "kpis_today": {
            "users": _cnt("giso_web_auth", "created_at", today + " 00:00:00"),
            "analyses": _cnt("analyses", "created_at", today + " 00:00:00"),
            "hair": _cnt("hair_orders", "created_at", today + " 00:00:00"),
            "orders": _cnt("product_orders", "created_at", today + " 00:00:00"),
            "reviews": _cnt("reviews", "created_at", today + " 00:00:00"),
        },
        "kpis_7d": {
            "users": _cnt("giso_web_auth", "created_at", day7_ago),
            "analyses": _cnt("analyses", "created_at", day7_ago),
            "hair": _cnt("hair_orders", "created_at", day7_ago),
            "orders": _cnt("product_orders", "created_at", day7_ago),
            "reviews": _cnt("reviews", "created_at", day7_ago),
        },
        "kpis_30d": {
            "users": _cnt("giso_web_auth", "created_at", day30_ago),
            "analyses": _cnt("analyses", "created_at", day30_ago),
            "hair": _cnt("hair_orders", "created_at", day30_ago),
            "orders": _cnt("product_orders", "created_at", day30_ago),
            "reviews": _cnt("reviews", "created_at", day30_ago),
        },
        "revenue_7d": _q1(
            "SELECT COALESCE(SUM(p.price),0) FROM product_orders po "
            "JOIN products p ON p.id=po.product_id "
            "WHERE po.status='completed' AND po.created_at >= ?", (day7_ago,)),
        "revenue_30d": _q1(
            "SELECT COALESCE(SUM(p.price),0) FROM product_orders po "
            "JOIN products p ON p.id=po.product_id "
            "WHERE po.status='completed' AND po.created_at >= ?", (day30_ago,)),
        "top_products": _rows(
            "SELECT p.name AS محصول, COALESCE(SUM(po.quantity),0) AS فروش "
            "FROM product_orders po JOIN products p ON p.id=po.product_id "
            "WHERE po.created_at >= ? "
            "GROUP BY p.id ORDER BY فروش DESC LIMIT 5", (day30_ago,)),
        "pending_now": {
            "hair": _q1("SELECT COUNT(*) FROM hair_orders WHERE status='pending'"),
            "orders": _q1("SELECT COUNT(*) FROM product_orders WHERE status='pending'"),
            "products_pending": _q1("SELECT COUNT(*) FROM products WHERE publish_status='pending'"),
            "withdrawals": _q1("SELECT COUNT(*) FROM referral_withdrawals WHERE status='pending'"),
        },
        # روند ۷ روز اخیر به تفکیک روز
        "trend_hair": _rows(
            "SELECT SUBSTR(created_at,1,10) AS روز, COUNT(*) AS تعداد FROM hair_orders "
            "WHERE created_at >= ? GROUP BY روز ORDER BY روز", (day7_ago,)),
        "trend_orders": _rows(
            "SELECT SUBSTR(created_at,1,10) AS روز, COUNT(*) AS تعداد FROM product_orders "
            "WHERE created_at >= ? GROUP BY روز ORDER BY روز", (day7_ago,)),
        "trend_analyses": _rows(
            "SELECT SUBSTR(created_at,1,10) AS روز, COUNT(*) AS تعداد FROM analyses "
            "WHERE created_at >= ? GROUP BY روز ORDER BY روز", (day7_ago,)),
        # رویدادهای مهم امروز (از مرکز اعلان‌ها اگر موجود باشد)
        "today_events": _rows(
            "SELECT category AS بخش, title AS عنوان, created_at AS زمان FROM giso_notifications "
            "WHERE created_at >= ? ORDER BY id DESC LIMIT 12", (today + " 00:00:00",)),
    }
    return ctx
