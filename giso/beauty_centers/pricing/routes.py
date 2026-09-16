# -*- coding: utf-8 -*-
"""Phase A pricing routes: owner-facing service and working-hour endpoints.

Registers only the three Phase A endpoints on the existing beauty_centers_bp:
  POST /dashboard/beauty-center/services/add
  POST /dashboard/beauty-center/services/<int:service_id>/delete
  POST /dashboard/beauty-center/hours

Every handler is owner-scoped (get_owner_center), CSRF-protected by the global
guard, and returns to the «خدمات و ساعات» tab. No price is negotiated, charged
or guaranteed here; the owner only declares it.
"""
import logging

from flask import abort, flash, redirect, request, url_for
from flask_login import current_user, login_required

from giso.beauty_centers import beauty_centers_bp
from giso.beauty_centers.pricing.services import add_service, delete_service, save_working_hours
from giso.beauty_centers.services import get_owner_center

logger = logging.getLogger("giso_beauty_centers_pricing_routes")

WEEKDAY_COUNT = 7


def _user_id() -> int:
    return int(getattr(current_user, "id", 0) or 0) if getattr(current_user, "is_authenticated", False) else 0


def _owned_center() -> dict:
    center = get_owner_center(_user_id())
    if not center:
        abort(404)
    return center


def _back_to_services():
    return redirect(url_for("beauty_centers.owner_dashboard", tab="services"))


@beauty_centers_bp.route("/dashboard/beauty-center/services/add", methods=["POST"])
@login_required
def owner_service_add():
    center = _owned_center()
    try:
        add_service(center["id"], {
            "name": request.form.get("name"),
            "category": request.form.get("category"),
            "description": request.form.get("description"),
            "duration_minutes": request.form.get("duration_minutes"),
            "price_min": request.form.get("price_min"),
            "price_max": request.form.get("price_max"),
            "sort_order": request.form.get("sort_order"),
            "is_active": 1 if request.form.get("is_active") else 0,
        })
    except ValueError as exc:
        flash(str(exc), "warning")
    except Exception:
        logger.exception("add_service failed for center %s", center.get("id"))
        flash("ثبت خدمت انجام نشد؛ لطفاً دوباره تلاش کنید.", "danger")
    else:
        flash("خدمت جدید به فهرست خدمات مرکز اضافه شد.", "success")
    return _back_to_services()


@beauty_centers_bp.route("/dashboard/beauty-center/services/<int:service_id>/delete", methods=["POST"])
@login_required
def owner_service_delete(service_id):
    center = _owned_center()
    try:
        removed = delete_service(service_id, center["id"])
    except Exception:
        logger.exception("delete_service failed for center %s", center.get("id"))
        removed = False
    flash("خدمت از فهرست خدمات مرکز حذف شد." if removed else "خدمتی برای حذف پیدا نشد.",
          "success" if removed else "warning")
    return _back_to_services()


@beauty_centers_bp.route("/dashboard/beauty-center/hours", methods=["POST"])
@login_required
def owner_working_hours():
    center = _owned_center()
    hours = [{
        "day_of_week": day,
        "is_closed": 1 if request.form.get(f"closed_{day}") else 0,
        "open_time": request.form.get(f"open_{day}"),
        "close_time": request.form.get(f"close_{day}"),
        "slot_minutes": request.form.get(f"slot_{day}"),
    } for day in range(WEEKDAY_COUNT)]
    try:
        save_working_hours(center["id"], hours)
    except ValueError as exc:
        flash(str(exc), "warning")
    except Exception:
        logger.exception("save_working_hours failed for center %s", center.get("id"))
        flash("ذخیره ساعات کاری انجام نشد؛ لطفاً دوباره تلاش کنید.", "danger")
    else:
        flash("ساعات کاری و بازه نوبت‌دهی مرکز ذخیره شد.", "success")
    return _back_to_services()


__all__ = ["owner_service_add", "owner_service_delete", "owner_working_hours"]