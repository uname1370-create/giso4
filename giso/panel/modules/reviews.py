# -*- coding: utf-8 -*-
"""panel/modules/reviews.py — مدیریت نظرات (فاز 4.6): مخفی/نمایش/حذف دومرحله‌ای."""
import logging

from flask import request, redirect, url_for, flash

from giso.models import db, Review
from giso.panel.permissions import current_role_and_perms

logger = logging.getLogger("giso_panel_reviews")


def _require_moderator():
    role, perms, bale_id = current_role_and_perms()
    if role not in ("admin", "super"):
        flash("فقط مدیر تأییدشده می‌تواند وضعیت نظر را تغییر دهد.", "warning")
        return redirect(url_for("panel.dashboard"))
    return None


def _require_super():
    role, perms, bale_id = current_role_and_perms()
    if role != "super":
        flash("فقط سوپرادمین می‌تواند نظر را حذف کند.", "warning")
        return redirect(url_for("panel.dashboard"))
    return None


def _rv_query():
    """بازگشت query string فیلتر فعلی نظرات."""
    rv = (request.args.get("rv") or "").strip()
    return f"?rv={rv}" if rv else ""


def handle_toggle(review_id):
    """مخفی/نمایش نظر."""
    g = _require_moderator()
    if g:
        return g
    try:
        r = Review.query.get_or_404(review_id)
        if r.status == "hidden":
            r.status = "visible"
            flash("نظر دوباره نمایش داده شد.", "success")
        else:
            r.status = "hidden"
            flash("نظر مخفی شد.", "success")
        db.session.commit()
    except Exception as e:
        logger.error(f"panel review toggle: {e}")
        flash("خطا در تغییر وضعیت نظر.", "danger")
    return redirect(url_for("panel.reviews") + _rv_query())


def handle_delete(review_id):
    """حذف کامل (دومرحله‌ای — بدون تایپ کلمه)."""
    g = _require_super()
    if g:
        return g
    step = (request.form.get("step") or "").strip()
    try:
        r = Review.query.get_or_404(review_id)
        if step == "confirm":
            r.status = "deleted"
            db.session.commit()
            flash("نظر حذف شد (از نمایش خارج شد).", "success")
        else:
            flash("⚠️ برای حذف نهایی، دوباره دکمه حذف را بزنید.", "warning")
    except Exception as e:
        logger.error(f"panel review delete: {e}")
        flash("خطا در حذف نظر.", "danger")
    return redirect(url_for("panel.reviews") + _rv_query())


def context():
    reviews = []
    try:
        reviews = Review.query.order_by(Review.id.desc()).all()
    except Exception as e:
        logger.error(f"panel reviews: {e}")
    # فاز جامع UX: دو حالت کاری (نمایش / مخفی) + فیلتر چیپی
    rv_filter = (request.args.get("rv") or "all").strip().lower()
    counts = {"visible": 0, "hidden": 0, "deleted": 0}
    for r in reviews:
        s = r.status if r.status in counts else "visible"
        counts[s] += 1
    filtered = [r for r in reviews
                if r.status != "deleted"
                and (rv_filter == "all"
                     or (rv_filter == "visible" and r.status == "visible")
                     or (rv_filter == "hidden" and r.status == "hidden"))]
    if rv_filter not in ("all", "visible", "hidden"):
        rv_filter = "all"
    return {"reviews": filtered, "rv_filter": rv_filter, "rv_counts": counts}
