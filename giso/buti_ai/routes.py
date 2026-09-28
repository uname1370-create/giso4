# -*- coding: utf-8 -*-
"""
giso/buti_ai/routes.py — کنترلرهای وب و ای‌پی‌آی آینه زیبایی گیسو.

قانون مرز کد: منطق اختصاصی Buti AI داخل همین ماژول می‌ماند. این فایل فقط
route/controller است و منطق سناریوی ابرو در `giso/buti_ai/eyebrow/` قرار دارد.
"""
from flask import flash, jsonify, redirect, render_template, request, send_from_directory, session, url_for
from flask_login import current_user

from giso.buti_ai import buti_ai_bp
from giso.buti_ai.eyebrow import (
    CHANGE_LEVELS,
    EYEBROW_STYLES,
    get_mirror_services,
    initial_form_values,
    process_eyebrow_submission,
)
from giso.buti_ai.eyebrow.final_design import (
    FINAL_DESIGN_SESSION_KEY,
    generate_python_guided_design,
    get_final_candidate,
    store_final_candidate,
    update_final_selection,
)
from giso.buti_ai.eyebrow.upload import EYEBROW_UPLOAD_DIR
from giso.buti_ai.schema import init_buti_ai_db
from giso.buti_ai.services import save_final_design


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
        if state.get("result"):
            store_final_candidate(session, state.get("result"), state.get("photo_status"))
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


@buti_ai_bp.route("/eyebrow/finalize", methods=["POST"])
def eyebrow_finalize_choice():
    """ثبت انتخاب نهایی مدل ابرو و ورود به مرحله طراحی نهایی."""
    init_buti_ai_db()
    candidate = get_final_candidate(session)
    if not candidate:
        flash("اول عکس را تحلیل کن، بعد مدل نهایی را انتخاب کن.", "warning")
        return redirect(url_for("buti_ai.eyebrow_wizard"))

    candidate = update_final_selection(session, request.form.get("final_style"))
    if not candidate.get("photo_filename"):
        flash("برای طراحی نهایی، عکس واقعی لازم است.", "warning")
        return redirect(url_for("buti_ai.eyebrow_wizard"))

    return redirect(url_for("buti_ai.eyebrow_final_design"))


@buti_ai_bp.route("/eyebrow/final", methods=["GET"])
def eyebrow_final_design():
    """صفحه طراحی نهایی: گیت ورود و ساخت طرح راهنمای پایتونی."""
    init_buti_ai_db()
    candidate = get_final_candidate(session)
    if not candidate:
        flash("برای طراحی نهایی، اول تحلیل ابرو را انجام بده.", "warning")
        return redirect(url_for("buti_ai.eyebrow_wizard"))

    final_url = url_for("buti_ai.eyebrow_final_design")
    if not getattr(current_user, "is_authenticated", False):
        return render_template(
            "buti_ai/eyebrow_final_auth.html",
            candidate=candidate,
            login_url=url_for("login", next=final_url),
            register_url=url_for("register", next=final_url),
        )

    generation = candidate.get("generation") if isinstance(candidate.get("generation"), dict) else {}
    if not generation or not generation.get("ok"):
        generation = generate_python_guided_design(candidate)
        candidate["generation"] = generation
        if generation.get("ok") and not candidate.get("final_design_id"):
            design_id = save_final_design(_safe_current_user_id(), candidate, generation)
            candidate["final_design_id"] = design_id
        session[FINAL_DESIGN_SESSION_KEY] = candidate
        session.modified = True

    return render_template(
        "buti_ai/eyebrow_final_design.html",
        candidate=candidate,
        generation=generation,
    )


@buti_ai_bp.route("/eyebrow/uploads/<path:filename>", methods=["GET"])
def eyebrow_uploaded_file(filename):
    """نمایش امن عکس‌های runtime آینه ابرو برای پیش‌نمایش همان صفحه."""
    return send_from_directory(EYEBROW_UPLOAD_DIR, filename)


@buti_ai_bp.route("/eyebrow/centers", methods=["GET"])
def eyebrow_centers():
    """اتصال نازک به مراکز زیبایی؛ مالک منطق مرکز همچنان beauty_centers است."""
    return redirect(url_for("beauty_centers.list_centers", service="eyebrow"))
