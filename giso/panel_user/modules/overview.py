# -*- coding: utf-8 -*-
"""panel_user/modules/overview.py — پیشخوان کاربر (KPI واقعی + آخرین درخواست فروش مو)."""
from flask_login import current_user

from giso.panel_user.modules._base import (
    get_analyses, get_shop_orders, get_hair_orders,
    get_stock_notifies, get_reviews, get_chats_count, get_wallet,
)


def context():
    analyses = get_analyses()
    orders = get_shop_orders()
    hair = get_hair_orders()
    notifies = get_stock_notifies()
    reviews = get_reviews()
    chats = get_chats_count()
    wallet = get_wallet()
    counts = {
        "analyses": len(analyses),
        "orders": len(orders),
        "hair": len(hair),
        "notifies": len(notifies),
        "reviews": len(reviews),
        "chats": chats,
        "balance": (wallet.get("summary") or {}).get("usable", 0),
        "cash_balance": (wallet.get("summary") or {}).get("cash", 0),
        "spend_balance": (wallet.get("summary") or {}).get("spend", 0),
    }
    # وضعیت آخرین درخواست فروش مو
    last_hair = hair[0] if hair else None

    notes = []
    try:
        from giso.panel.modules.notifications import list_user_notifications
        notes = list_user_notifications(getattr(current_user, "phone", "") or "", limit=8)
    except Exception:
        notes = []
    return {
        "user": current_user,
        "counts": counts,
        "last_hair": last_hair,
        "overview_notifications": notes,
    }
