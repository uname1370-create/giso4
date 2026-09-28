# -*- coding: utf-8 -*-
"""
giso/buti_ai/routes.py — کنترلرهای وب و ای‌پی‌آی آینه زیبایی گیسو.

قانون مرز کد: منطق اختصاصی Buti AI داخل همین ماژول می‌ماند. این فایل فقط
route/controller است و منطق سناریوی ابرو در `giso/buti_ai/eyebrow/` قرار دارد.
"""
from flask import flash, jsonify, redirect, render_template, request, send_from_directory, url_for
from flask_login import current_user

from giso.buti_ai import buti_ai_bp
from giso.buti_ai.eyebrow import (
    CHANGE_LEVELS,
    EYEBROW_STYLES,
    get_mirror_services,
    initial_form_values,
    process_eyebrow_submission,
)
from giso.buti_ai.eyebrow.upload import EYEBROW_UPLOAD_DIR
from giso.buti_ai.schema import init_buti_ai_db


def _safe_current_user_id():
    """شناسه کاربر لاگین‌شده بدون وابستگی route به مدل کاربر."""
    try:
        if getattr(current_user, "is_authenticated", False):
            return getattr(current_user, "id", None)
    except Exception:
        return None
    return None


@buti_ai_bp.route("/ping", methods=["GET"])
def ping():
    """تست سلامت ماژول آینه زیبایی گیسو."""
    init_buti_ai_db()
    return jsonify({"status": "ok", "module": "buti_ai_ready"})


@buti_ai_bp.route("", methods=["GET"])
@buti_ai_bp.route("/", methods=["GET"])
def mirror_home():
    """روت اصلی ورودی آینه زیبایی گیسو."""
    init_buti_ai_db()
    return render_template(
        "buti_ai/mirror_home.html",
        services=get_mirror_services(url_for("buti_ai.eyebrow_wizard")),
    )


@buti_ai_bp.route("/eyebrow", methods=["GET", "POST"])
def eyebrow_wizard():
    """جریان آینه ابرو: انتخاب سبک، بررسی عکس، تحلیل هوشمند و پیش‌نمایش امن."""
    init_buti_ai_db()
    state = {
        "result": None,
        "form_values": initial_form_values(),
        "error_message": "",
    }

    if request.method == "POST":
        state = process_eyebrow_submission(
            request.form,
            request.files,
            user_id=_safe_current_user_id(),
        )
        if state.get("flash_message"):
            flash(state["flash_message"], state.get("flash_category") or "info")

    return render_template(
        "buti_ai/eyebrow_wizard.html",
        styles=EYEBROW_STYLES,
        change_levels=CHANGE_LEVELS,
        form_values=state["form_values"],
        result=state["result"],
        error_message=state["error_message"],
    )


@buti_ai_bp.route("/eyebrow/uploads/<path:filename>", methods=["GET"])
def eyebrow_uploaded_file(filename):
    """نمایش امن عکس‌های runtime آینه ابرو برای پیش‌نمایش همان صفحه."""
    return send_from_directory(EYEBROW_UPLOAD_DIR, filename)


@buti_ai_bp.route("/eyebrow/centers", methods=["GET"])
def eyebrow_centers():
    """اتصال نازک به مراکز زیبایی؛ مالک منطق مرکز همچنان beauty_centers است."""
    return redirect(url_for("beauty_centers.list_centers", service="eyebrow"))
