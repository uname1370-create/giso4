# -*- coding: utf-8 -*-
"""panel_user/modules/profile.py — حساب من (Beauty Profile + ویرایش + تغییر رمز)."""
from flask_login import current_user
from datetime import datetime, timedelta
from giso.base import get_giso_db_conn


def context():
    """Enhanced profile context with beauty data from real DB."""
    user = current_user
    beauty = {
        "last_analysis": None,
        "hair_type": "",
        "hair_health": "",
        "analysis_count": 0,
        "order_count": 0,
        "hair_sale_count": 0,
        "score_level": "cold",
        "score_value": 0,
    }
    try:
        phone = getattr(user, "phone", "") or ""
        if phone:
            with get_giso_db_conn() as conn:
                # آخرین آنالیز
                ana = conn.execute(
                    "SELECT type, ai_report_json, created_at FROM analyses WHERE phone=? ORDER BY created_at DESC LIMIT 1",
                    (phone,)
                ).fetchone()
                if ana:
                    beauty["last_analysis"] = {"type": ana[0], "created_at": ana[2]}
                    try:
                        import json
                        report = json.loads(ana[1] or "{}")
                        if isinstance(report, dict):
                            beauty["last_analysis"]["metrics"] = report.get("radar_metrics") or {}
                    except Exception:
                        pass

                # پروفایل مو
                hair = conn.execute(
                    "SELECT hair_type, hair_health FROM hair_orders WHERE phone=? ORDER BY created_at DESC LIMIT 1",
                    (phone,)
                ).fetchone()
                if hair:
                    beauty["hair_type"] = str(hair[0] or "")
                    beauty["hair_health"] = str(hair[1] or "")

                # تعدادها
                beauty["analysis_count"] = conn.execute("SELECT COUNT(*) FROM analyses WHERE phone=?", (phone,)).fetchone()[0]
                beauty["order_count"] = conn.execute("SELECT COUNT(*) FROM product_orders WHERE phone=?", (phone,)).fetchone()[0]
                beauty["hair_sale_count"] = conn.execute("SELECT COUNT(*) FROM hair_orders WHERE phone=?", (phone,)).fetchone()[0]

                # امتیاز مشتری
                score_row = conn.execute(
                    "SELECT score, level FROM customer_scores WHERE phone=? ORDER BY updated_at DESC LIMIT 1",
                    (phone,)
                ).fetchone()
                if score_row:
                    beauty["score_value"] = score_row[0] or 0
                    beauty["score_level"] = score_row[1] or "cold"
    except Exception:
        pass

    try:
        from giso.panel.modules.notifications import list_user_notifications, user_unread_count
        user_notifications = list_user_notifications(getattr(user, "phone", "") or "", limit=50)
        notification_unread = user_unread_count(getattr(user, "phone", "") or "")
    except Exception:
        user_notifications = []
        notification_unread = 0

    try:
        from giso.user_profile_service import get_user_activity_summary
        activity = get_user_activity_summary(getattr(user, "phone", "") or "")
    except Exception:
        activity = {}
    try:
        from giso.beauty_centers.services import get_owner_center
        beauty_center = get_owner_center(int(getattr(user, "id", 0) or 0))
    except Exception:
        beauty_center = {}

    profile_can_edit=True;profile_next_edit=""
    if getattr(user,"last_profile_edit_at",""):
        try:
            allowed=datetime.fromisoformat(user.last_profile_edit_at)+timedelta(days=15)
            profile_can_edit=datetime.now()>=allowed;profile_next_edit=allowed.strftime("%Y-%m-%d %H:%M")
        except (TypeError,ValueError): pass
    try:
        from giso.ai_credits import get_ai_credit
        ai_credit = get_ai_credit(getattr(user, "phone", "") or "", create=True)
    except Exception:
        ai_credit = {"balance": 0, "total_used": 0, "available": False}
    try:
        from giso.login_history import recent
        login_events=recent(int(getattr(user,'id',0) or 0),limit=10)
    except Exception:login_events=[]
    return {
        "user": user, "login_events":login_events, "profile_can_edit":profile_can_edit, "profile_next_edit":profile_next_edit,
        "ai_credit": ai_credit,
        "beauty": beauty,
        "activity": activity,
        "beauty_center": beauty_center,
        "profile_notifications": user_notifications,
        "profile_notification_unread": notification_unread,
    }
