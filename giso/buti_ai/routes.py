# -*- coding: utf-8 -*-
"""
giso/buti_ai/routes.py — کنترلرهای وب و ای‌پی‌آی آینه زیبایی گیسو.

قانون مرز کد: منطق اختصاصی Buti AI داخل همین ماژول می‌ماند. این فایل فقط
route/controller است و منطق سناریوی ابرو در `giso/buti_ai/eyebrow/` قرار دارد.
"""
import os
import shutil
import tempfile

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
from giso.buti_ai.eyebrow.options import normalize_change_level, normalize_style_key
from giso.buti_ai.eyebrow.centers import (
    BEAUTY_CENTER_BROW_SERVICE,
    BUTI_EYEBROW_SERVICE,
    active_eyebrow_centers,
    enrich_eyebrow_center_suggestions,
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
from giso.buti_ai.eyebrow.ai import check_photo_quality
from giso.buti_ai.eyebrow.upload import EYEBROW_UPLOAD_DIR, save_eyebrow_photo
from giso.buti_ai.schema import init_buti_ai_db
from giso.buti_ai.services import (
    record_service_demand,
    save_final_design,
    save_service_waitlist,
    total_service_interest_count,
)



EYEBROW_SELECTION_SESSION_KEY = "buti_ai_eyebrow_selection"


def _selection_from_form(form):
    form = form or {}
    return {
        "style": normalize_style_key(form.get("style")),
        "change_level": normalize_change_level(form.get("change_level")),
    }


def _current_selection():
    selection = session.get(EYEBROW_SELECTION_SESSION_KEY)
    if not isinstance(selection, dict):
        selection = initial_form_values()
    return {
        "style": normalize_style_key(selection.get("style")),
        "change_level": normalize_change_level(selection.get("change_level")),
    }


def _state_with_selection(step="model", error_message=""):
    return {
        "result": None,
        "form_values": _current_selection(),
        "error_message": error_message or "",
        "flow_step": step,
    }


def _render_eyebrow_wizard(state):
    return render_template(
        "buti_ai/eyebrow_wizard.html",
        styles=EYEBROW_STYLES,
        change_levels=CHANGE_LEVELS,
        form_values=state["form_values"],
        result=state["result"],
        error_message=state["error_message"],
        flow_step=state.get("flow_step") or ("result" if state.get("result") else "model"),
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
    """مرحله انتخاب مدل ابرو؛ آپلود عکس در route جدا انجام می‌شود."""
    init_buti_ai_db()
    if request.method == "POST":
        # سازگاری با فرم/تست‌های قدیمی: اگر عکس مستقیم ارسال شد، همان‌جا تحلیل شود.
        selection = _selection_from_form(request.form)
        session[EYEBROW_SELECTION_SESSION_KEY] = selection
        session.modified = True
        merged_form = dict(request.form)
        merged_form.update(selection)
        state = process_eyebrow_submission(
            merged_form,
            request.files,
            user_id=_safe_current_user_id(),
        )
        state["flow_step"] = "result" if state.get("result") else "upload"
        if state.get("result"):
            store_final_candidate(session, state.get("result"), state.get("photo_status"))
        if state.get("flash_message"):
            flash(state["flash_message"], state.get("flash_category") or "info")
        return _render_eyebrow_wizard(state)

    session[EYEBROW_SELECTION_SESSION_KEY] = initial_form_values()
    session.modified = True
    return _render_eyebrow_wizard(_state_with_selection("model"))


@buti_ai_bp.route("/eyebrow/model", methods=["POST"])
def eyebrow_model_selection():
    """ثبت مرحله انتخاب مدل/شدت تغییر و رفتن به آپلود عکس."""
    init_buti_ai_db()
    selection = _selection_from_form(request.form)
    session[EYEBROW_SELECTION_SESSION_KEY] = selection
    session.modified = True
    return redirect(url_for("buti_ai.eyebrow_upload"))


@buti_ai_bp.route("/eyebrow/upload", methods=["GET", "POST"])
def eyebrow_upload():
    """مرحله مستقل آپلود عکس و تحلیل آینه ابرو."""
    init_buti_ai_db()
    selection = _current_selection()
    if request.method == "GET":
        return _render_eyebrow_wizard(_state_with_selection("upload"))

    merged_form = dict(request.form)
    merged_form["style"] = selection["style"]
    merged_form["change_level"] = selection["change_level"]
    state = process_eyebrow_submission(
        merged_form,
        request.files,
        user_id=_safe_current_user_id(),
    )
    state["flow_step"] = "result" if state.get("result") else "upload"
    if state.get("result"):
        store_final_candidate(session, state.get("result"), state.get("photo_status"))
    if state.get("flash_message"):
        flash(state["flash_message"], state.get("flash_category") or "info")
    return _render_eyebrow_wizard(state)


@buti_ai_bp.route("/eyebrow/validate-photo", methods=["POST"])
def eyebrow_validate_photo():
    """بررسی اولیه عکس آپلود ابرو برای پیش‌نمایش همان صفحه، مشابه مسیر مو/پوست."""
    init_buti_ai_db()
    tmp_dir = tempfile.mkdtemp(prefix="buti_eyebrow_validate_")
    try:
        photo = request.files.get("photo") or request.files.get("image")
        saved = save_eyebrow_photo(photo, upload_dir=tmp_dir)
        if not saved.get("ok"):
            return jsonify({
                "valid": False,
                "reason_code": saved.get("reason") or "invalid_image",
                "message": saved.get("message") or "عکس مناسب نیست.",
                "checks": {},
            }), 400
        quality = check_photo_quality(saved.get("path"))
        q_ok = quality.get("ok")
        valid = q_ok is not False
        warnings = []
        if q_ok is None:
            warnings.append("بررسی هوشمند کامل در دسترس نبود؛ عکس دریافت شد و می‌توانی ادامه بدهی.")
        checks = quality.get("checks") or {}
        return jsonify({
            "valid": bool(valid),
            "status": quality.get("status"),
            "message": quality.get("message") or ("عکس برای تحلیل مناسب است." if valid else "این عکس برای تحلیل دقیق مناسب نیست."),
            "warnings": warnings,
            "checks": {
                "face_visible": checks.get("face_visible"),
                "eyebrows_visible": checks.get("eyebrows_visible"),
                "lighting": checks.get("lighting"),
                "angle": checks.get("angle"),
                "sharpness": checks.get("sharpness"),
            },
        }), (200 if valid else 422)
    finally:
        try:
            shutil.rmtree(tmp_dir, ignore_errors=True)
        except Exception:
            pass


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
    center_suggestions = enrich_eyebrow_center_suggestions(
        active_eyebrow_centers(city=center_city, limit=3),
        candidate=candidate,
        city=center_city,
    )
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
