# -*- coding: utf-8 -*-
"""Phase B reservation routes (per gisobu.md)."""
from flask import Blueprint, jsonify, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from datetime import datetime
from giso.base import get_giso_db_conn, gregorian_to_jalali
from giso.beauty_centers.reservations import services as rsv
from giso.beauty_centers.reservations.notifications import (
    notify_new_reservation,
    notify_user_confirmed,
    notify_user_rejected,
)
from giso.beauty_centers.pricing.services import get_center_services
from giso.money import format_toman, to_persian_digits

reservations_bp = Blueprint("beauty_reservations", __name__)


def _center_by_id(center_id):
    with get_giso_db_conn() as conn:
        row = conn.execute(
            "SELECT * FROM beauty_centers WHERE id=?", (int(center_id or 0),)
        ).fetchone()
    return dict(row) if row else None


def _center_by_slug(slug):
    with get_giso_db_conn() as conn:
        row = conn.execute(
            "SELECT * FROM beauty_centers WHERE slug=?", (str(slug or ""),)
        ).fetchone()
    return dict(row) if row else None


def _owner_center(center_id, owner_id):
    c = _center_by_id(center_id)
    if c and int(c.get("owner_user_id") or 0) == int(owner_id or 0):
        return c
    return None


@reservations_bp.get("/beauty-centers/<int:center_id>/slots")
def slots(center_id):
    date = request.args.get("date", "")
    service_id = request.args.get("service_id", "")
    try:
        data = rsv.get_available_slots(center_id, date, service_id)
    except ValueError as exc:
        return jsonify({"ok": False, "error": str(exc)}), 400
    data = dict(data)
    data["ok"] = True
    return jsonify(data)


@reservations_bp.get("/beauty-centers/<int:center_id>/calendar")
def calendar(center_id):
    try:
        year = int(request.args.get("year", 0))
        month = int(request.args.get("month", 0))
    except (TypeError, ValueError):
        return jsonify({"ok": False, "error": "سال/ماه نامعتبر است."}), 400
    try:
        data = rsv.get_calendar_month(center_id, year, month)
    except ValueError as exc:
        return jsonify({"ok": False, "error": str(exc)}), 400
    return jsonify({"ok": True, "days": data})


@reservations_bp.route("/beauty-centers/<slug>/reserve", methods=["GET", "POST"])
@login_required
def reserve(slug):
    center = _center_by_slug(slug)
    if not center:
        return jsonify({"ok": False, "error": "مرکز یافت نشد."}), 404
    if request.method == "GET":
        from giso.beauty_centers.routes import (
            _service_duration_label, _service_price_label,
        )
        service_id = request.args.get("service_id", "")
        date = request.args.get("date", "")
        service = None
        slots = []
        if service_id:
            for svc in get_center_services(center["id"]):
                if str(svc.get("id")) == str(service_id):
                    service = dict(svc)
                    service["price_label"] = _service_price_label(service)
                    service["duration_label"] = _service_duration_label(service)
                    break
            if service_id and not service:
                return jsonify({"ok": False, "error": "خدمت یافت نشد."}), 404
        if date and service:
            try:
                result = rsv.get_available_slots(center["id"], date, service_id)
                slots = result.get("slots", []) if isinstance(result, dict) else []
            except ValueError:
                slots = []
        _jy, _jm, _jd = gregorian_to_jalali(*datetime.now().date().timetuple()[:3])
        return render_template(
            "beauty_centers/reserve.html", center=center, service=service,
            available_slots=slots, default_date=date,
            today_jalali_year=_jy, today_jalali_month=_jm, today_jalali_day=_jd,
        )
    form = request.get_json(silent=True) or request.form
    try:
        rid = rsv.create_reservation(
            center["id"], getattr(current_user, "id", 0),
            service_id=form.get("service_id"),
            reservation_date=form.get("date") or form.get("reservation_date"),
            reservation_time=form.get("time") or form.get("reservation_time"),
            user_note=form.get("user_note", ""),
        )
    except ValueError as exc:
        return jsonify({"ok": False, "error": str(exc)}), 400
    rows = rsv.get_center_reservations(
        center["id"], form.get("date") or form.get("reservation_date"), "pending")
    reservation = next(
        (r for r in rows if int(r.get("id") or 0) == int(rid)), {"id": rid})
    try:
        notify_new_reservation(reservation, center)
    except Exception:
        pass
    if request.is_json:
        return jsonify({"ok": True, "id": rid})
    return redirect(url_for("beauty_reservations.my_reservations"))


@reservations_bp.get("/dashboard/beauty-center/reservations")
@login_required
def owner_list():
    center_id = request.args.get("center_id", "")
    date = request.args.get("date", "")
    status = request.args.get("status", "")
    center = _owner_center(center_id, getattr(current_user, "id", 0))
    if not center:
        return jsonify({"ok": False, "error": "دسترسی ندارید."}), 403
    return jsonify({"ok": True, "reservations": rsv.get_center_reservations(center["id"], date, status)})


@reservations_bp.post("/dashboard/beauty-center/reservations/<int:reservation_id>/action")
@login_required
def owner_action(reservation_id):
    form = request.get_json(silent=True) or request.form
    action = str(form.get("action") or "").strip()
    center_id = form.get("center_id", "")
    center = _owner_center(center_id, getattr(current_user, "id", 0))
    if not center:
        return jsonify({"ok": False, "error": "دسترسی ندارید."}), 403
    ok = False
    if action == "confirm":
        ok = bool(rsv.confirm_reservation(reservation_id, center["id"]))
    elif action == "reject":
        ok = bool(rsv.reject_reservation(reservation_id, center["id"], form.get("reason", "")))
    elif action == "complete":
        ok = bool(rsv.complete_reservation(reservation_id, center["id"]))
    if not ok:
        return jsonify({"ok": False, "error": "عملیات ناموفق بود."}), 400
    rows = rsv.get_center_reservations(center["id"], "", "")
    reservation = next((r for r in rows if int(r.get("id") or 0) == int(reservation_id)), {"id": reservation_id})
    try:
        if action == "confirm":
            notify_user_confirmed(reservation, center)
        elif action == "reject":
            notify_user_rejected(reservation, center)
    except Exception:
        pass
    return jsonify({"ok": True})


_MYRES_BADGE_CSS = {
    "pending": "is-pending",
    "confirmed": "is-confirmed",
    "completed": "is-completed",
    "cancelled_user": "is-cancelled",
    "cancelled_center": "is-cancelled",
}
_CANCELLABLE_STATUSES = ("pending", "confirmed")


@reservations_bp.get("/dashboard/my-reservations")
@login_required
def my_reservations():
    """HTML page of the logged-in user's reservations (was a JSON endpoint)."""
    rows = rsv.get_user_reservations(getattr(current_user, "id", 0))
    for row in rows:
        status = str(row.get("status") or "")
        row["status_css"] = _MYRES_BADGE_CSS.get(status, "is-pending")
        row["can_cancel"] = status in _CANCELLABLE_STATUSES
        row["weekday"] = rsv._date_weekday_label(row.get("reservation_date"))
    return render_template(
        "beauty_centers/my_reservations.html", reservations=rows)


@reservations_bp.post("/dashboard/reservations/<int:reservation_id>/cancel")
@login_required
def user_cancel(reservation_id):
    ok = bool(rsv.cancel_by_user(reservation_id, getattr(current_user, "id", 0)))
    if request.is_json:
        if not ok:
            return jsonify({"ok": False, "error": "لغو ناموفق بود."}), 400
        return jsonify({"ok": True})
    # HTML form submit from the my-reservations page → back to the same page.
    return redirect(url_for("beauty_reservations.my_reservations"))
