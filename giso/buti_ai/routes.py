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
from giso.buti_ai.eyebrow.centers import (
    BEAUTY_CENTER_BROW_SERVICE,
    BUTI_EYEBROW_SERVICE,
    active_eyebrow_centers,
    user_default_city,
    user_default_phone,
)
from giso.buti_ai.eyebrow.final_design import (
    FINAL_DESIGN_SESSION_KEY,
    get_final_candidate,
    store_final_candidate,
    update_final_selection,
)
from giso.buti_ai.eyebrow.image_generation import generate_final_design
from giso.buti_ai.eyebrow.upload import EYEBROW_UPLOAD_DIR
from giso.buti_ai.schema import init_buti_ai_db
from giso.buti_ai.services import (
    record_service_demand,
    save_final_design,
    save_service_waitlist,
    total_service_interest_count,
)


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


@buti_ai_bp.route("/eyebrow/final/retry", methods=["POST"])
def eyebrow_final_retry():
    """تلاش دوباره برای ساخت طراحی نهایی بدون از دست دادن عکس و انتخاب کاربر."""
    init_buti_ai_db()
    candidate = get_final_candidate(session)
    if not candidate:
        flash("برای تلاش دوباره، اول عکس را تحلیل کن.", "warning")
        return redirect(url_for("buti_ai.eyebrow_wizard"))
    candidate.pop("generation", None)
    candidate.pop("final_design_id", None)
    session[FINAL_DESIGN_SESSION_KEY] = candidate
    session.modified = True
    flash("عکس و انتخابت حفظ شد؛ دوباره سراغ مدل‌های طراحی نهایی می‌رویم.", "info")
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
        generation = generate_final_design(candidate)
        candidate["generation"] = generation
        if generation.get("ok") and not candidate.get("final_design_id"):
            design_id = save_final_design(_safe_current_user_id(), candidate, generation)
            candidate["final_design_id"] = design_id
        session[FINAL_DESIGN_SESSION_KEY] = candidate
        session.modified = True

    center_city = (request.args.get("city") or user_default_city(current_user)).strip() or "مشهد"
    center_suggestions = active_eyebrow_centers(city=center_city, limit=3)
    if not center_suggestions:
        demand_key = ":".join([
            "eyebrow_final_no_center",
            str(_safe_current_user_id() or "guest"),
            str(candidate.get("final_design_id") or candidate.get("session_id") or candidate.get("created_at") or candidate.get("photo_filename") or "draft"),
            center_city,
        ])
        ok_demand, demand_id = record_service_demand(
            _safe_current_user_id(),
            center_city,
            BUTI_EYEBROW_SERVICE,
            source="eyebrow_final_no_active_center",
            dedupe_key=demand_key,
            payload={
                "final_design_id": candidate.get("final_design_id"),
                "final_style": candidate.get("final_style"),
                "has_generation": bool(candidate.get("generation")),
            },
        )
        if ok_demand:
            recorded = candidate.get("center_demand_recorded")
            if not isinstance(recorded, dict):
                recorded = {}
            recorded[center_city] = demand_id
            candidate["center_demand_recorded"] = recorded
            session[FINAL_DESIGN_SESSION_KEY] = candidate
            session.modified = True
    center_demand_count = total_service_interest_count(BUTI_EYEBROW_SERVICE, city=center_city)
    centers_url = url_for("beauty_centers.list_centers", service=BEAUTY_CENTER_BROW_SERVICE, city=center_city)
    register_center_url = (
        url_for("beauty_centers.register_center")
        if getattr(current_user, "is_authenticated", False)
        else url_for("login", next=url_for("beauty_centers.register_center"))
    )

    return render_template(
        "buti_ai/eyebrow_final_design.html",
        candidate=candidate,
        generation=generation,
        center_city=center_city,
        center_suggestions=center_suggestions,
        center_demand_count=center_demand_count,
        centers_url=centers_url,
        register_center_url=register_center_url,
        default_phone=user_default_phone(current_user),
    )


@buti_ai_bp.route("/eyebrow/uploads/<path:filename>", methods=["GET"])
def eyebrow_uploaded_file(filename):
    """نمایش امن عکس‌های runtime آینه ابرو برای پیش‌نمایش همان صفحه."""
    return send_from_directory(EYEBROW_UPLOAD_DIR, filename)


@buti_ai_bp.route("/eyebrow/centers", methods=["GET", "POST"])
def eyebrow_centers():
    """بعد از طراحی نهایی: مرکز فعال ابرو یا ثبت درخواست انتظار.

    اگر مرکز فعال برای خدمت ابرو داریم، کاربر را به لیست مراکز با فیلتر صحیح
    `brow` می‌فرستیم. اگر نداریم، کاربر به صفحه خالی نمی‌رسد؛ درخواستش ثبت
    می‌شود تا بعداً برای جذب/فعال‌سازی مرکز و اطلاع‌رسانی استفاده شود.
    """
    init_buti_ai_db()
    city = (request.values.get("city") or user_default_city(current_user)).strip() or "مشهد"
    centers = active_eyebrow_centers(city=city, limit=1)
    if request.method == "GET" and centers:
        return redirect(url_for("beauty_centers.list_centers", service=BEAUTY_CENTER_BROW_SERVICE, city=city))

    candidate = get_final_candidate(session)
    saved = False
    waitlist_message = ""
    waitlist_error = ""
    if request.method == "POST":
        phone = request.form.get("phone") or user_default_phone(current_user)
        payload = {
            "candidate": candidate,
            "final_design_id": candidate.get("final_design_id") if isinstance(candidate, dict) else None,
            "has_generation": bool(isinstance(candidate, dict) and candidate.get("generation")),
        }
        ok, message, _row_id = save_service_waitlist(
            _safe_current_user_id(),
            phone,
            city,
            BUTI_EYEBROW_SERVICE,
            source="eyebrow_no_active_center",
            payload=payload,
        )
        if ok:
            saved = True
            waitlist_message = message
        else:
            waitlist_error = message

    demand_count = total_service_interest_count(BUTI_EYEBROW_SERVICE, city=city)
    return render_template(
        "buti_ai/eyebrow_centers_empty.html",
        candidate=candidate,
        city=city,
        default_phone=user_default_phone(current_user),
        saved=saved,
        waitlist_message=waitlist_message,
        waitlist_error=waitlist_error,
        demand_count=demand_count,
        register_center_url=url_for("beauty_centers.register_center")
        if getattr(current_user, "is_authenticated", False)
        else url_for("login", next=url_for("beauty_centers.register_center")),
        centers_url=url_for("beauty_centers.list_centers", service=BEAUTY_CENTER_BROW_SERVICE, city=city),
    )
