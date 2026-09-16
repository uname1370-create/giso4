# -*- coding: utf-8 -*-
"""panel_user/modules/_base.py — داده‌های مشترک کاربر از دیتابیس واقعی."""
import logging

from flask_login import current_user

from giso.models import db, User, Analysis, ProductOrder, HairOrder, StockNotify, Review
from giso.base import get_giso_db_conn, normalize_phone

logger = logging.getLogger("giso_panel_user_base")


def get_analyses():
    try:
        return (Analysis.query.filter_by(phone=current_user.phone)
                .order_by(Analysis.id.desc()).all())
    except Exception as e:
        logger.error(f"pu analyses: {e}")
        return []


def get_shop_orders():
    try:
        # user_id منبع اصلی مالکیت است؛ phone برای سفارش‌های تاریخی حفظ می‌شود.
        return (ProductOrder.query.filter(
                    db.or_(ProductOrder.user_id == current_user.id,
                           ProductOrder.phone == normalize_phone(current_user.phone)))
                .order_by(ProductOrder.id.desc()).all())
    except Exception as e:
        logger.error(f"pu orders: {e}")
        return []


def get_hair_orders():
    try:
        return (HairOrder.query.filter_by(phone=current_user.phone)
                .order_by(HairOrder.id.desc()).all())
    except Exception as e:
        logger.error(f"pu hair: {e}")
        return []


def get_stock_notifies():
    try:
        return (StockNotify.query.filter_by(phone=current_user.phone)
                .order_by(StockNotify.id.desc()).all())
    except Exception as e:
        logger.error(f"pu notifies: {e}")
        return []


def get_reviews():
    try:
        # فاز 4.6: فقط نظرات visible به کاربر نمایش داده می‌شود
        return (Review.query
                .filter(Review.phone == current_user.phone,
                        Review.status.in_(("visible", "", None)))
                .order_by(Review.id.desc()).all())
    except Exception as e:
        logger.error(f"pu reviews: {e}")
        return []


def get_chats_count():
    try:
        with get_giso_db_conn() as conn:
            row = conn.execute(
                "SELECT COUNT(*) AS c FROM consultant_requests WHERE phone=?",
                (current_user.phone,)
            ).fetchone()
            return int(row["c"] or 0) if row else 0
    except Exception:
        return 0


def _missions_with_progress(uid):
    """مأموریت‌ها + پیشرفت نمایشی (مورد ۱۶ help.md)."""
    from giso.wallet import list_missions_for_user
    missions = list_missions_for_user(uid)
    try:
        from giso.wallet_missions import mission_progress
        for m in missions:
            m["progress"] = mission_progress(uid, m.get("code"))
    except Exception:
        pass
    return missions

def get_wallet():
    """نمای واحد cash/spend بدون وابستگی به UI یا پورسانت referral."""
    try:
        from giso.wallet import (
            get_wallet_balances, get_user_transactions, get_financial_settings,
            list_missions_for_user, list_user_topups, list_user_withdrawals,
        )
        uid = getattr(current_user, "id", None)
        if not uid:
            return {}
        balances = get_wallet_balances(uid)
        return {
            "summary": balances,
            "transactions": get_user_transactions(uid),
            "settings": get_financial_settings(),
            "missions": _missions_with_progress(uid),
            "topups": list_user_topups(uid),
            "withdrawals": list_user_withdrawals(uid),
        }
    except Exception as e:
        logger.warning(f"pu wallet: {e}")
        return {}
