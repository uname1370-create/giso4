# -*- coding: utf-8 -*-
"""Admin/SuperAdmin context and actions for Beauty Centers."""
from flask import flash, redirect, request, url_for

from giso.base import get_giso_db_conn
from giso.beauty_centers.services import STATUS_FA, admin_set_status, list_admin_centers

_SETTING_DEFAULTS = {
    "beauty_promotions_enabled": "1",
    "beauty_bump_enabled": "1",
    "beauty_featured_enabled": "1",
    "beauty_discount_enabled": "1",
    "beauty_renew_enabled": "1",
    "beauty_bump_price": "25000",
    "beauty_featured_price": "120000",
    "beauty_discount_price": "60000",
    "beauty_renew_price": "50000",
    "beauty_listing_days": "30",
    "beauty_registration_enabled": "1",
    "beauty_registration_intro": "اطلاعات مرکز را کامل و واقعی ثبت کنید تا پس از بررسی منتشر شود.",
    "beauty_terms_text": "گیسو فقط بستر معرفی و ارتباط است؛ قیمت، پرداخت، کیفیت و نتیجه خدمت مستقیماً میان کاربر و مرکز تعیین می‌شود.",
}


def _settings() -> dict:
    try:
        from giso_admin import get_giso_config
        return {key: str(get_giso_config(key, default) or default) for key, default in _SETTING_DEFAULTS.items()}
    except Exception:
        return dict(_SETTING_DEFAULTS)


def _dashboard(conn) -> dict:
    q1 = lambda sql, args=(): int((conn.execute(sql, args).fetchone()[0] or 0))
    totals = {
        "total": q1("SELECT COUNT(*) FROM beauty_centers"),
        "pending": q1("SELECT COUNT(*) FROM beauty_centers WHERE status IN ('pending_review','reviewing')"),
        "published": q1("SELECT COUNT(*) FROM beauty_centers WHERE status='published' AND is_active=1"),
        "expired": q1("SELECT COUNT(*) FROM beauty_centers WHERE listing_expires_at<>'' AND listing_expires_at<datetime('now','localtime')"),
        "conversations": q1("SELECT COUNT(*) FROM beauty_center_conversations"),
        "unanswered": q1("SELECT COUNT(*) FROM beauty_center_conversations c WHERE c.status='active' AND EXISTS(SELECT 1 FROM beauty_center_messages m WHERE m.conversation_id=c.id AND m.sender_user_id=c.user_id AND m.is_read=0)"),
        "active_promotions": q1("SELECT COUNT(*) FROM beauty_center_promotions WHERE status='active' AND (expires_at='' OR expires_at>datetime('now','localtime'))"),
        "promotion_revenue": q1("SELECT COALESCE(SUM(amount),0) FROM beauty_center_promotions WHERE status<>'cancelled'"),
    }
    performance = [dict(r) for r in conn.execute("""
        SELECT c.id,c.name,c.views_count,c.contact_clicks,c.price_inquiry_clicks,c.analysis_impressions,
               COUNT(DISTINCT cv.id) conversations,
               CASE WHEN c.views_count>0 THEN ROUND((COUNT(DISTINCT cv.id)+c.contact_clicks)*100.0/c.views_count,1) ELSE 0 END conversion_rate
        FROM beauty_centers c LEFT JOIN beauty_center_conversations cv ON cv.center_id=c.id
        GROUP BY c.id ORDER BY c.views_count DESC,c.id DESC LIMIT 20
    """).fetchall()]
    event_rows = [dict(r) for r in conn.execute("SELECT event_type,COUNT(*) count FROM beauty_center_events WHERE created_at>=datetime('now','localtime','-30 days') GROUP BY event_type ORDER BY count DESC").fetchall()]
    return {"totals": totals, "performance": performance, "events": event_rows}


def context(tab: str = "requests") -> dict:
    status_map = {"requests": "pending_review", "published": "published", "paused": "paused"}
    centers = list_admin_centers(status_map.get(tab, "")) if tab in status_map else (list_admin_centers("published") if tab == "promotions" else [])
    feedback_rows, promotion_rows, discount_rows = [], [], []
    dashboard = {"totals": {}, "performance": [], "events": []}
    counts = {}
    with get_giso_db_conn() as conn:
        if tab == "feedback":
            feedback_rows=[dict(r) for r in conn.execute("SELECT f.*,c.name center_name FROM beauty_center_feedback f JOIN beauty_centers c ON c.id=f.center_id ORDER BY f.id DESC LIMIT 200").fetchall()]
        if tab == "promotions":
            promotion_rows=[dict(r) for r in conn.execute("SELECT p.*,c.name center_name FROM beauty_center_promotions p JOIN beauty_centers c ON c.id=p.center_id ORDER BY p.id DESC LIMIT 200").fetchall()]
        if tab == "feedback":
            discount_rows=[dict(r) for r in conn.execute("SELECT d.*,c.name center_name FROM beauty_center_discounts d JOIN beauty_centers c ON c.id=d.center_id ORDER BY d.id DESC LIMIT 200").fetchall()]
        if tab == "dashboard":
            dashboard = _dashboard(conn)
        for status in STATUS_FA:
            counts[status] = conn.execute("SELECT COUNT(*) FROM beauty_centers WHERE status=?", (status,)).fetchone()[0]
    return {"centers": centers, "beauty_counts": counts, "beauty_dashboard": dashboard,
            "beauty_settings": _settings(), "beauty_tab": tab, "status_fa": STATUS_FA,
            "beauty_feedback": feedback_rows, "beauty_promotions": promotion_rows,
            "beauty_discounts": discount_rows}


def handle_settings():
    section=(request.form.get("settings_section") or "registration").strip()
    redirect_tab="promotions" if section=="promotion" else "settings"
    try:
        from giso_admin import set_giso_config
        if section=="promotion":
            for key in ("beauty_promotions_enabled", "beauty_bump_enabled", "beauty_featured_enabled", "beauty_discount_enabled", "beauty_renew_enabled"):
                set_giso_config(key, "1" if request.form.get(key) == "1" else "0")
            for key,default in (("beauty_bump_price",25000),("beauty_featured_price",120000),("beauty_discount_price",60000),("beauty_renew_price",50000)):
                try:value=max(0,min(100000000,int(request.form.get(key,default))))
                except (TypeError,ValueError):value=default
                set_giso_config(key,str(value))
            message="تنظیمات و قیمت‌های ارتقای آگهی ذخیره شد."
        else:
            set_giso_config("beauty_registration_enabled", "1" if request.form.get("beauty_registration_enabled") == "1" else "0")
            try:days=max(1,min(365,int(request.form.get("beauty_listing_days",30))))
            except (TypeError,ValueError):days=30
            set_giso_config("beauty_listing_days",str(days))
            set_giso_config("beauty_registration_intro", (request.form.get("beauty_registration_intro") or "").strip()[:1000])
            set_giso_config("beauty_terms_text", (request.form.get("beauty_terms_text") or "").strip()[:3000])
            message="تنظیمات ثبت مرکز و متن قوانین ذخیره شد."
        try:
            from giso.base import invalidate_giso_config_cache
            invalidate_giso_config_cache()
        except Exception: pass
        flash(message, "success")
    except Exception:
        flash("ذخیره تنظیمات مراکز ناموفق بود.", "danger")
    return redirect(url_for("panel.beauty_centers", tab=redirect_tab))


def handle_status(center_id: int, actor_id: int = 0):
    status = (request.form.get("status") or "").strip()
    note = (request.form.get("admin_note") or "").strip()
    ok, message, _center = admin_set_status(center_id, status, note, actor_id)
    flash(message, "success" if ok else "danger")
    return redirect(url_for("panel.beauty_centers", tab="requests"))


def handle_feature_selected():
    try:center_id=int(request.form.get("center_id") or 0)
    except (TypeError,ValueError):center_id=0
    if not center_id:
        flash("مرکز را انتخاب کنید.","warning")
        return redirect(url_for("panel.beauty_centers",tab="promotions"))
    return handle_feature(center_id,request.form.get("featured")=="1")


def handle_feature(center_id: int, featured: bool):
    """نشان منتخب گیسو مدیریتی و غیرقابل خرید است."""
    with get_giso_db_conn() as conn:
        row = conn.execute("SELECT id FROM beauty_centers WHERE id=?", (int(center_id),)).fetchone()
        if not row:
            flash("مرکز پیدا نشد.", "danger")
        else:
            conn.execute("UPDATE beauty_centers SET is_featured=?,updated_at=datetime('now','localtime') WHERE id=?",(1 if featured else 0,int(center_id)))
            conn.commit();flash("نشان مدیریتی منتخب گیسو تغییر کرد.", "success")
    return redirect(url_for("panel.beauty_centers", tab="promotions"))


def handle_discount(discount_id:int):
    status=(request.form.get('status') or 'visible').strip()
    if status not in ('visible','rejected'):status='rejected'
    with get_giso_db_conn() as conn:conn.execute("UPDATE beauty_center_discounts SET status=? WHERE id=?",(status,int(discount_id)));conn.commit()
    flash("وضعیت تخفیف ذخیره شد.","success");return redirect(url_for('panel.beauty_centers',tab='promotions'))


def handle_feedback(feedback_id:int):
    status=(request.form.get('status') or 'visible').strip()
    if status not in ('visible','rejected'): status='rejected'
    with get_giso_db_conn() as conn:
        conn.execute("UPDATE beauty_center_feedback SET status=? WHERE id=?",(status,int(feedback_id)));conn.commit()
    flash("وضعیت بازخورد ذخیره شد.","success")
    return redirect(url_for('panel.beauty_centers',tab='feedback'))
