# -*- coding: utf-8 -*-
"""
giso/buti_ai/routes.py — کنترلرهای وب و ای‌پی‌آی آینه زیبایی گیسو.

قانون مرز کد: منطق اختصاصی Buti AI داخل همین ماژول می‌ماند. این فایل فقط
route/controller است و منطق سناریوی ابرو در `giso/buti_ai/eyebrow/` قرار دارد.
"""
import logging
import os
import shutil
import tempfile

from flask import flash, jsonify, redirect, render_template, request, send_from_directory, session, url_for
from flask_login import current_user

from giso.buti_ai import buti_ai_bp
from giso.buti_ai import generic_service
from giso.buti_ai.service_catalog import (
    get_service_meta,
    mirror_services,
    service_for_slug,
    slug_for_service,
    supported_service_keys,
)
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
logger = logging.getLogger("giso_buti_ai_routes")


def _beauty_route_log(tag, message="", **fields):
    safe_parts = []
    for key, value in fields.items():
        key_text = str(key or "").strip()
        if not key_text or any(secret in key_text.lower() for secret in ("token", "secret", "api_key", "authorization", "account_id")):
            continue
        text = str(value or "").replace("\n", " ").replace("\r", " ").strip()[:180]
        safe_parts.append(f"{key_text}={text}")
    logger.info("%s %s%s%s", tag, message or "", " " if safe_parts else "", " ".join(safe_parts))



def _log_preview_candidate(candidate, source="upload"):
    if not isinstance(candidate, dict):
        return
    filename = candidate.get("photo_filename") or ""
    path = os.path.join(EYEBROW_UPLOAD_DIR, os.path.basename(filename)) if filename else ""
    size_text = ""
    if path and os.path.exists(path):
        try:
            from PIL import Image

            with Image.open(path) as image:
                size_text = f"{image.width}x{image.height}"
        except Exception:
            size_text = "unreadable"
    _beauty_route_log(
        "[EYEBROW_PREVIEW]",
        "candidate_photo_ready",
        source=source,
        filename=filename,
        path=path,
        size=size_text,
        final_style=candidate.get("final_style"),
        cache_key=candidate.get("cache_key") or candidate.get("created_at"),
    )


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


def _compact_generation_for_session(generation):
    """Keep Flask cookie-session small; full generation is saved in DB/render context."""
    if not isinstance(generation, dict):
        return {}
    keep_keys = (
        "ok", "filename", "provider", "provider_label", "kind", "model", "status",
        "is_ai_generated", "ai_inpainting", "fallback_type", "service_key", "message",
        "mask_used", "mask_filename", "fallback_used", "configured_provider_count",
        "real_ai_blocked_reason", "saved", "readable", "final_width", "final_height",
        "provider_output_constrained_to_eyebrow_mask",
        "provider_output_constrained_to_service_mask",
        "visible_in_mask_change", "outside_preserved", "in_mask_diff_ratio",
        "outside_mask_diff_ratio", "mask_coverage_ratio",
    )
    compact = {key: generation.get(key) for key in keep_keys if key in generation}
    validation = generation.get("validation") if isinstance(generation.get("validation"), dict) else {}
    if validation:
        compact["validation"] = {
            key: validation.get(key)
            for key in (
                "ok", "service_key", "in_mask_diff_ratio", "outside_mask_diff_ratio",
                "mask_coverage_ratio", "visible_in_mask_change", "outside_preserved", "message"
            )
            if key in validation
        }
    attempts = generation.get("attempts") if isinstance(generation.get("attempts"), list) else []
    if attempts:
        small_attempts = []
        for item in attempts[:3]:
            if not isinstance(item, dict):
                continue
            small_attempts.append({
                key: item.get(key)
                for key in ("id", "label", "kind", "model", "ok", "ms", "error", "stage")
                if key in item
            })
        compact["attempts"] = small_attempts
    return compact


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
    service_hrefs = {
        key: url_for("buti_ai.generic_service_wizard", service_slug=slug_for_service(key))
        for key in supported_service_keys()
    }
    return render_template(
        "buti_ai/mirror_home.html",
        services=mirror_services(url_for("buti_ai.eyebrow_wizard"), service_hrefs),
    )


@buti_ai_bp.route("/eyebrow", methods=["GET", "POST"])
def eyebrow_wizard():
    """مرحله انتخاب مدل ابرو؛ آپلود عکس در route جدا انجام می‌شود."""
    init_buti_ai_db()
    if request.method == "POST":
        # سازگاری با فرم/تست‌های قدیمی: اگر عکس مستقیم ارسال شد، همان‌جا آماده طراحی نهایی شود.
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
        state["flow_step"] = "upload"
        if state.get("result"):
            store_final_candidate(session, state.get("result"), state.get("photo_status"))
            if state.get("flash_message"):
                flash(state["flash_message"], state.get("flash_category") or "info")
            return redirect(url_for("buti_ai.eyebrow_final_design"))
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
    """مرحله مستقل آپلود عکس؛ بعد از آپلود مستقیم به طراحی نهایی می‌رود (4 مرحله‌ای)."""
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
    # برای 4 مرحله‌ای شدن، دیگر flow_step=result نمایش داده نمی‌شود
    # بعد از آپلود موفق مستقیم به /eyebrow/final می‌رویم
    if state.get("result"):
        candidate = store_final_candidate(session, state.get("result"), state.get("photo_status"))
        _log_preview_candidate(candidate, source="upload_route")
        if state.get("flash_message"):
            flash(state["flash_message"], state.get("flash_category") or "info")
        return redirect(url_for("buti_ai.eyebrow_final_design"))
    if state.get("flash_message"):
        flash(state["flash_message"], state.get("flash_category") or "info")
    # در صورت خطا، همان صفحه آپلود با پیام خطا
    state["flow_step"] = "upload"
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
            "message": quality.get("message") or ("عکس برای طراحی مناسب است." if valid else "این عکس برای طراحی دقیق مناسب نیست."),
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
        flash("اول مدل را انتخاب کن و عکس را آپلود کن، بعد طراحی نهایی را بساز.", "warning")
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
        flash("برای تلاش دوباره، اول مدل را انتخاب کن و عکس را آپلود کن.", "warning")
        return redirect(url_for("buti_ai.eyebrow_wizard"))
    candidate.pop("generation", None)
    candidate.pop("final_design_id", None)
    session[FINAL_DESIGN_SESSION_KEY] = candidate
    session.modified = True
    flash("عکس و انتخابت حفظ شد؛ دوباره سراغ مدل‌های طراحی نهایی می‌رویم.", "info")
    return redirect(url_for("buti_ai.eyebrow_final_design"))


@buti_ai_bp.route("/eyebrow/final", methods=["GET"])
def eyebrow_final_design():
    """صفحه طراحی نهایی: بدون چک لاگین برای تست — مستقیم طراحی."""
    init_buti_ai_db()
    candidate = get_final_candidate(session)
    if not candidate:
        flash("برای طراحی نهایی، اول مدل ابرو را انتخاب کن و عکس را آپلود کن.", "warning")
        return redirect(url_for("buti_ai.eyebrow_wizard"))

    # لاگین غیرفعال برای تست

    generation = candidate.get("generation") if isinstance(candidate.get("generation"), dict) else {}
    if not generation or not generation.get("ok"):
        generation = generate_final_design(candidate)
        candidate["generation"] = generation
        _beauty_route_log(
            "[FINAL]",
            "route_generation_result",
            filename=generation.get("filename") if isinstance(generation, dict) else "",
            status=generation.get("status") if isinstance(generation, dict) else "",
            is_ai_generated=generation.get("is_ai_generated") if isinstance(generation, dict) else False,
            ok=generation.get("ok") if isinstance(generation, dict) else False,
        )
        if generation.get("ok") and not candidate.get("final_design_id"):
            design_id = save_final_design(_safe_current_user_id(), candidate, generation)
            candidate["final_design_id"] = design_id
        candidate["generation"] = _compact_generation_for_session(generation)
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
    # Phase 5 – AI Consultant context for eyebrow
    try:
        from giso.buti_ai.consultant import build_consultant_context, consultant_invite_text
        consultant_context = build_consultant_context("eyebrow", candidate, generation)
        consultant_invite = consultant_invite_text(consultant_context)
    except Exception:
        consultant_context = {}
        consultant_invite = ""

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
        consultant_context=consultant_context,
        consultant_invite=consultant_invite,
    )


@buti_ai_bp.route("/eyebrow/uploads/<path:filename>", methods=["GET"])
def eyebrow_uploaded_file(filename):
    """نمایش امن عکس‌های runtime آینه ابرو برای پیش‌نمایش همان صفحه."""
    safe_name = os.path.basename(str(filename or ""))
    _beauty_route_log("[EYEBROW_PREVIEW]", "serve_uploaded_file", filename=safe_name, cache_buster=request.args.get("v", ""))
    response = send_from_directory(EYEBROW_UPLOAD_DIR, filename)
    response.cache_control.no_cache = True
    response.cache_control.max_age = 0
    response.headers["Pragma"] = "no-cache"
    response.headers["X-Content-Type-Options"] = "nosniff"
    return response


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


# ---------------------------------------------------------------------------
# Generic staged flow for the new Buti AI mirror services (nail/lip/hair).
# Eyebrow keeps its dedicated implementation above; these routes intentionally
# reuse the same stage contract without changing the validated eyebrow path.
# ---------------------------------------------------------------------------


def _new_service_selection_key(service_key):
    return f"buti_ai_{service_key}_selection"


def _new_service_candidate_key(service_key):
    return f"buti_ai_{service_key}_final_candidate"


def _is_active_new_service(service_key):
    meta = get_service_meta(service_key)
    return bool(service_key and service_key in supported_service_keys() and meta.get("status") == "active")


def _active_service_from_slug(service_slug):
    service_key = service_for_slug(service_slug)
    if not _is_active_new_service(service_key):
        return ""
    return service_key


def _new_service_selection_from_form(service_key, form):
    form = form or {}
    return {
        "style": generic_service.normalize_model_key(service_key, form.get("style")),
        "change_level": generic_service.normalize_change_level(form.get("change_level")),
    }


def _current_new_service_selection(service_key):
    selection = session.get(_new_service_selection_key(service_key))
    if not isinstance(selection, dict):
        selection = generic_service.initial_form_values(service_key)
    return {
        "style": generic_service.normalize_model_key(service_key, selection.get("style")),
        "change_level": generic_service.normalize_change_level(selection.get("change_level")),
    }


def _new_service_state(service_key, step="model", error_message=""):
    return {
        "service_key": service_key,
        "service_meta": get_service_meta(service_key),
        "styles": getattr(generic_service.service_module(service_key), "STYLES", {}),
        "change_levels": generic_service.CHANGE_LEVELS,
        "form_values": _current_new_service_selection(service_key),
        "result": None,
        "error_message": error_message or "",
        "flow_step": step,
    }


def _render_new_service_wizard(service_key, state):
    return render_template(
        "buti_ai/generic_service_wizard.html",
        service_key=service_key,
        service_meta=get_service_meta(service_key),
        styles=state["styles"],
        change_levels=state["change_levels"],
        form_values=state["form_values"],
        result=state["result"],
        error_message=state["error_message"],
        flow_step=state.get("flow_step") or ("result" if state.get("result") else "model"),
    )


def _store_new_service_candidate(service_key, result, photo_status):
    candidate = generic_service.build_final_candidate(service_key, result or {}, photo_status or {})
    session[_new_service_candidate_key(service_key)] = candidate
    session.modified = True
    return candidate


def _get_new_service_candidate(service_key):
    candidate = session.get(_new_service_candidate_key(service_key))
    return candidate if isinstance(candidate, dict) else None


def _rebuild_new_service_candidate_from_finalize_form(service_key):
    """Recover final candidate from hidden upload result fields if session was lost/truncated."""
    form = request.values or {}
    filename = os.path.basename(str(form.get("photo_filename") or ""))
    if not filename:
        return None
    try:
        module = generic_service.service_module(service_key)
        upload_root = os.path.abspath(getattr(module, "UPLOAD_DIR"))
        photo_path = os.path.abspath(os.path.join(upload_root, filename))
        if not photo_path.startswith(upload_root + os.sep) or not os.path.exists(photo_path):
            return None
        style_key = generic_service.normalize_model_key(
            service_key,
            form.get("selected_style") or form.get("final_style") or form.get("style"),
        )
        change_key = generic_service.normalize_change_level(form.get("change_key") or form.get("change_level"))
        detection = module.detect_regions(photo_path, allow_fallback=True)
        photo_status = {"ok": True, "filename": filename, "path": photo_path}
        result = generic_service.build_result(
            service_key,
            style_key,
            change_key,
            photo_status,
            detection=detection,
            quality_report={
                "status": "session_recovered",
                "ok": True,
                "message": "عکس قبلاً دریافت شده بود و طراحی ادامه پیدا کرد.",
            },
        )
        return _store_new_service_candidate(service_key, result, photo_status)
    except Exception as exc:
        _beauty_route_log("[BUTI_SERVICE_FINAL]", "candidate_recovery_failed", service_key=service_key, error=str(exc)[:120])
        return None


def _update_new_service_final_selection(service_key):
    candidate = _get_new_service_candidate(service_key)
    if not candidate:
        return None
    # Single Source of Truth: the model chosen in stage ۲ remains final.
    style_key = generic_service.normalize_model_key(service_key, candidate.get("selected_style") or candidate.get("final_style"))
    styles = getattr(generic_service.service_module(service_key), "STYLES", {})
    style = styles[style_key]
    candidate["final_style"] = style_key
    candidate["final_label"] = style.get("label")
    candidate["selected_style"] = style_key
    candidate["selected_label"] = style.get("label")
    session[_new_service_candidate_key(service_key)] = candidate
    session.modified = True
    return candidate


def _new_service_uploaded_url(service_key, filename, cache=""):
    return url_for(
        "buti_ai.generic_service_uploaded_file",
        service_slug=slug_for_service(service_key),
        filename=filename,
        v=cache or "",
    )


def _active_generic_centers(service_key, city="", limit=3):
    try:
        from giso.beauty_centers.services import list_public_centers

        meta = get_service_meta(service_key)
        service_filter = str(meta.get("beauty_center_service") or "").strip()
        if not service_filter:
            return []
        return list_public_centers(
            city=str(city or "").strip(),
            service=service_filter,
            limit=max(1, min(12, int(limit or 3))),
        )
    except Exception as exc:
        _beauty_route_log("[BUTI_SERVICE_CENTERS]", "lookup_failed", service_key=service_key, error=str(exc)[:120])
        return []


def _service_center_label(service_key):
    try:
        from giso.beauty_centers.services import SERVICES

        service_filter = str(get_service_meta(service_key).get("beauty_center_service") or "").strip()
        return SERVICES.get(service_filter) or str(get_service_meta(service_key).get("short_title") or get_service_meta(service_key).get("title") or "این خدمت")
    except Exception:
        return str(get_service_meta(service_key).get("short_title") or "این خدمت")


def _enrich_generic_centers(service_key, centers, candidate=None, city=""):
    candidate = candidate or {}
    meta = get_service_meta(service_key)
    service_filter = str(meta.get("beauty_center_service") or "").strip()
    service_label = _service_center_label(service_key)
    final_label = str(candidate.get("final_label") or "مدل انتخابی").strip()
    target_city = str(city or "").strip()
    enriched = []
    for index, center in enumerate(centers or [], start=1):
        item = dict(center or {})
        services = item.get("services") if isinstance(item.get("services"), list) else []
        service_labels = item.get("service_labels") if isinstance(item.get("service_labels"), list) else []
        has_service = service_filter in services or any(service_label in str(label) for label in service_labels)
        city_match = bool(target_city and str(item.get("city") or "").strip() == target_city)
        score = 0
        score += 45 if has_service else 0
        score += 20 if city_match else 0
        score += 15 if item.get("is_featured") else 0
        try:
            score += min(20, int((item.get("feedback") or {}).get("score100") or 0) // 5)
        except Exception:
            pass
        item["mirror_rank"] = index
        item["mirror_score"] = max(0, min(100, score))
        item["mirror_match_reason"] = (
            f"برای اجرای {final_label}، این مرکز به‌عنوان ارائه‌دهنده {service_label} پیشنهاد شده است."
            if has_service else
            f"قبل از رزرو، از مرکز درباره اجرای {final_label} سؤال کن."
        )
        tags = [service_label] if has_service else []
        if city_match:
            tags.append("همان شهر")
        if item.get("feedback") and item.get("feedback", {}).get("label"):
            tags.append(str(item["feedback"]["label"]))
        item["mirror_tags"] = tags[:4]
        enriched.append(item)
    enriched.sort(key=lambda c: (-int(c.get("mirror_score") or 0), int(c.get("mirror_rank") or 0)))
    return enriched


@buti_ai_bp.route("/<service_slug>", methods=["GET", "POST"])
def generic_service_wizard(service_slug):
    """مرحله انتخاب مدل برای خدمات جدید آینه گیسو."""
    init_buti_ai_db()
    service_key = _active_service_from_slug(service_slug)
    if not service_key:
        flash("این خدمت هنوز برای استفاده عمومی فعال نشده است.", "info")
        return redirect(url_for("buti_ai.mirror_home"))

    if request.method == "POST":
        selection = _new_service_selection_from_form(service_key, request.form)
        session[_new_service_selection_key(service_key)] = selection
        session.modified = True
        merged_form = dict(request.form)
        merged_form.update(selection)
        state = generic_service.process_service_submission(
            service_key,
            merged_form,
            request.files,
            user_id=_safe_current_user_id(),
        )
        state["flow_step"] = "upload"
        if state.get("result"):
            _store_new_service_candidate(service_key, state.get("result"), state.get("photo_status"))
            if state.get("flash_message"):
                flash(state["flash_message"], state.get("flash_category") or "info")
            return redirect(url_for("buti_ai.generic_service_final_design", service_slug=slug_for_service(service_key)))
        if state.get("flash_message"):
            flash(state["flash_message"], state.get("flash_category") or "info")
        return _render_new_service_wizard(service_key, state)

    session[_new_service_selection_key(service_key)] = generic_service.initial_form_values(service_key)
    session.modified = True
    return _render_new_service_wizard(service_key, _new_service_state(service_key, "model"))


@buti_ai_bp.route("/<service_slug>/model", methods=["POST"])
def generic_service_model_selection(service_slug):
    init_buti_ai_db()
    service_key = _active_service_from_slug(service_slug)
    if not service_key:
        flash("این خدمت هنوز فعال نیست.", "info")
        return redirect(url_for("buti_ai.mirror_home"))
    selection = _new_service_selection_from_form(service_key, request.form)
    session[_new_service_selection_key(service_key)] = selection
    session.modified = True
    return redirect(url_for("buti_ai.generic_service_upload", service_slug=slug_for_service(service_key)))


@buti_ai_bp.route("/<service_slug>/upload", methods=["GET", "POST"])
def generic_service_upload(service_slug):
    init_buti_ai_db()
    service_key = _active_service_from_slug(service_slug)
    if not service_key:
        flash("این خدمت هنوز فعال نیست.", "info")
        return redirect(url_for("buti_ai.mirror_home"))
    selection = _current_new_service_selection(service_key)
    if request.method == "GET":
        return _render_new_service_wizard(service_key, _new_service_state(service_key, "upload"))

    merged_form = dict(request.form)
    merged_form["style"] = selection["style"]
    merged_form["change_level"] = selection["change_level"]
    state = generic_service.process_service_submission(
        service_key,
        merged_form,
        request.files,
        user_id=_safe_current_user_id(),
    )
    state["flow_step"] = "result" if state.get("result") else "upload"
    if state.get("result"):
        _store_new_service_candidate(service_key, state.get("result"), state.get("photo_status"))
        if state.get("flash_message"):
            flash(state["flash_message"], state.get("flash_category") or "info")
        return _render_new_service_wizard(service_key, state)
    if state.get("flash_message"):
        flash(state["flash_message"], state.get("flash_category") or "info")
    return _render_new_service_wizard(service_key, state)


@buti_ai_bp.route("/<service_slug>/validate-photo", methods=["POST"])
def generic_service_validate_photo(service_slug):
    init_buti_ai_db()
    service_key = _active_service_from_slug(service_slug)
    if not service_key:
        return jsonify({"valid": False, "message": "این خدمت هنوز فعال نیست.", "checks": {}}), 404
    module = generic_service.service_module(service_key)
    tmp_dir = tempfile.mkdtemp(prefix=f"buti_{service_key}_validate_")
    try:
        photo = request.files.get("photo") or request.files.get("image")
        saved = save_eyebrow_photo(photo, upload_dir=tmp_dir, prefix=service_key)
        if not saved.get("ok"):
            return jsonify({
                "valid": False,
                "reason_code": saved.get("reason") or "invalid_image",
                "message": saved.get("message") or "عکس مناسب نیست.",
                "checks": {},
            }), 400
        quality = module.local_quality_report(saved.get("path"))
        q_ok = quality.get("ok")
        valid = q_ok is not False
        warnings = []
        if q_ok is None:
            warnings.append("بررسی کامل در دسترس نبود؛ اگر عکس واضح است می‌توانی ادامه بدهی.")
        return jsonify({
            "valid": bool(valid),
            "status": quality.get("status"),
            "message": quality.get("message") or ("عکس برای طراحی مناسب است." if valid else "این عکس برای طراحی دقیق مناسب نیست."),
            "warnings": warnings,
            "checks": quality.get("checks") or {},
        }), (200 if valid else 422)
    finally:
        try:
            shutil.rmtree(tmp_dir, ignore_errors=True)
        except Exception:
            pass


@buti_ai_bp.route("/<service_slug>/finalize", methods=["POST"])
def generic_service_finalize_choice(service_slug):
    init_buti_ai_db()
    service_key = _active_service_from_slug(service_slug)
    if not service_key:
        flash("این خدمت هنوز فعال نیست.", "info")
        return redirect(url_for("buti_ai.mirror_home"))
    candidate = _get_new_service_candidate(service_key)
    if not candidate:
        candidate = _rebuild_new_service_candidate_from_finalize_form(service_key)
    if not candidate:
        flash("اول مدل را انتخاب کن و عکس را آپلود کن، بعد طراحی نهایی را بساز.", "warning")
        return redirect(url_for("buti_ai.generic_service_wizard", service_slug=slug_for_service(service_key)))
    candidate = _update_new_service_final_selection(service_key)
    if not candidate.get("photo_filename"):
        flash("برای طراحی نهایی، عکس واقعی لازم است.", "warning")
        return redirect(url_for("buti_ai.generic_service_wizard", service_slug=slug_for_service(service_key)))
    return redirect(url_for("buti_ai.generic_service_final_design", service_slug=slug_for_service(service_key)))


@buti_ai_bp.route("/<service_slug>/final", methods=["GET"])
def generic_service_final_design(service_slug):
    init_buti_ai_db()
    service_key = _active_service_from_slug(service_slug)
    if not service_key:
        flash("این خدمت هنوز فعال نیست.", "info")
        return redirect(url_for("buti_ai.mirror_home"))
    candidate = _get_new_service_candidate(service_key)
    if not candidate:
        candidate = _rebuild_new_service_candidate_from_finalize_form(service_key)
    if not candidate:
        flash("برای طراحی نهایی، اول مدل را انتخاب کن و عکس را آپلود کن.", "warning")
        return redirect(url_for("buti_ai.generic_service_wizard", service_slug=slug_for_service(service_key)))

    final_url = url_for(
        "buti_ai.generic_service_final_design",
        service_slug=slug_for_service(service_key),
        photo_filename=candidate.get("photo_filename") or "",
        selected_style=candidate.get("selected_style") or candidate.get("final_style") or "",
        change_level=candidate.get("change_key") or "",
    )
    if not getattr(current_user, "is_authenticated", False):
        return render_template(
            "buti_ai/generic_final_auth.html",
            service_key=service_key,
            service_meta=get_service_meta(service_key),
            candidate=candidate,
            uploaded_url_builder=_new_service_uploaded_url,
            login_url=url_for("login", next=final_url),
            register_url=url_for("register", next=final_url),
        )

    generation = candidate.get("generation") if isinstance(candidate.get("generation"), dict) else {}
    if not generation or not generation.get("ok"):
        generation = generic_service.generate_final_design(service_key, candidate)
        candidate["generation"] = generation
        _beauty_route_log(
            "[BUTI_SERVICE_FINAL]",
            "route_generation_result",
            service_key=service_key,
            filename=generation.get("filename") if isinstance(generation, dict) else "",
            status=generation.get("status") if isinstance(generation, dict) else "",
            is_ai_generated=generation.get("is_ai_generated") if isinstance(generation, dict) else False,
            ok=generation.get("ok") if isinstance(generation, dict) else False,
        )
        if generation.get("ok") and not candidate.get("final_design_id"):
            design_id = save_final_design(_safe_current_user_id(), candidate, generation)
            candidate["final_design_id"] = design_id
        candidate["generation"] = _compact_generation_for_session(generation)
        session[_new_service_candidate_key(service_key)] = candidate
        session.modified = True

    center_city = (request.args.get("city") or user_default_city(current_user)).strip() or "مشهد"
    center_suggestions = _enrich_generic_centers(
        service_key,
        _active_generic_centers(service_key, city=center_city, limit=3),
        candidate=candidate,
        city=center_city,
    )
    service_type = str(candidate.get("service_type") or get_service_meta(service_key).get("service_type") or service_key)
    if not center_suggestions:
        demand_key = ":".join([
            f"{service_key}_final_no_center",
            str(_safe_current_user_id() or "guest"),
            str(candidate.get("final_design_id") or candidate.get("session_id") or candidate.get("created_at") or candidate.get("photo_filename") or "draft"),
            center_city,
        ])
        ok_demand, demand_id = record_service_demand(
            _safe_current_user_id(),
            center_city,
            service_type,
            source=f"{service_key}_final_no_active_center",
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
            session[_new_service_candidate_key(service_key)] = candidate
            session.modified = True
    center_demand_count = total_service_interest_count(service_type, city=center_city)
    beauty_service = str(get_service_meta(service_key).get("beauty_center_service") or "").strip()
    centers_url = url_for("beauty_centers.list_centers", service=beauty_service, city=center_city) if beauty_service else url_for("beauty_centers.list_centers", city=center_city)
    register_center_url = (
        url_for("beauty_centers.register_center")
        if getattr(current_user, "is_authenticated", False)
        else url_for("login", next=url_for("beauty_centers.register_center"))
    )
    # Phase 5 – AI Consultant context
    try:
        from giso.buti_ai.consultant import build_consultant_context, consultant_invite_text
        consultant_context = build_consultant_context(service_key, candidate, generation)
        consultant_invite = consultant_invite_text(consultant_context)
    except Exception:
        consultant_context = {}
        consultant_invite = ""

    return render_template(
        "buti_ai/generic_final_design.html",
        service_key=service_key,
        service_meta=get_service_meta(service_key),
        candidate=candidate,
        generation=generation,
        center_city=center_city,
        center_suggestions=center_suggestions,
        center_demand_count=center_demand_count,
        centers_url=centers_url,
        register_center_url=register_center_url,
        default_phone=user_default_phone(current_user),
        service_center_label=_service_center_label(service_key),
        uploaded_url_builder=_new_service_uploaded_url,
        consultant_context=consultant_context,
        consultant_invite=consultant_invite,
    )


@buti_ai_bp.route("/<service_slug>/uploads/<path:filename>", methods=["GET"])
def generic_service_uploaded_file(service_slug, filename):
    service_key = _active_service_from_slug(service_slug)
    if not service_key:
        flash("این خدمت هنوز فعال نیست.", "info")
        return redirect(url_for("buti_ai.mirror_home"))
    safe_filename = str(filename or "").replace("\\", "/").lstrip("/")
    response = send_from_directory(generic_service.uploaded_root(service_key), safe_filename)
    response.cache_control.no_cache = True
    response.cache_control.max_age = 0
    response.headers["Pragma"] = "no-cache"
    response.headers["X-Content-Type-Options"] = "nosniff"
    return response


@buti_ai_bp.route("/<service_slug>/centers", methods=["GET", "POST"])
def generic_service_centers(service_slug):
    init_buti_ai_db()
    service_key = _active_service_from_slug(service_slug)
    if not service_key:
        flash("این خدمت هنوز فعال نیست.", "info")
        return redirect(url_for("buti_ai.mirror_home"))
    city = (request.values.get("city") or user_default_city(current_user)).strip() or "مشهد"
    beauty_service = str(get_service_meta(service_key).get("beauty_center_service") or "").strip()
    centers = _active_generic_centers(service_key, city=city, limit=1)
    if request.method == "GET" and centers:
        return redirect(url_for("beauty_centers.list_centers", service=beauty_service, city=city) if beauty_service else url_for("beauty_centers.list_centers", city=city))

    candidate = _get_new_service_candidate(service_key)
    saved = False
    waitlist_message = ""
    waitlist_error = ""
    service_type = str(get_service_meta(service_key).get("service_type") or service_key)
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
            service_type,
            source=f"{service_key}_no_active_center",
            payload=payload,
        )
        if ok:
            saved = True
            waitlist_message = message
        else:
            waitlist_error = message

    demand_count = total_service_interest_count(service_type, city=city)
    centers_url = url_for("beauty_centers.list_centers", service=beauty_service, city=city) if beauty_service else url_for("beauty_centers.list_centers", city=city)
    return render_template(
        "buti_ai/generic_centers_empty.html",
        service_key=service_key,
        service_meta=get_service_meta(service_key),
        service_center_label=_service_center_label(service_key),
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
        centers_url=centers_url,
    )

@buti_ai_bp.route("/<service_slug>/consultant", methods=["POST"])
def generic_service_consultant_chat(service_slug):
    """AI Consultant for generic services – context: Service+Style+Analysis+Preview"""
    init_buti_ai_db()
    service_key = _active_service_from_slug(service_slug)
    if not service_key:
        return {"ok": False, "error": "خدمت فعال نیست."}, 404
    candidate = _get_new_service_candidate(service_key)
    if not candidate:
        return {"ok": False, "error": "ابتدا مدل و عکس را انتخاب کن."}, 400
    try:
        from giso.buti_ai.consultant import build_consultant_context
        generation = candidate.get("generation") if isinstance(candidate.get("generation"), dict) else {}
        context = build_consultant_context(service_key, candidate, generation)
        user_message = (request.get_json(silent=True) or {}).get("message") or request.form.get("message") or ""
        user_message = str(user_message).strip()[:800]
        if not user_message:
            return {"ok": False, "error": "پیام خالی است."}, 400
        # Use ai_brain chat with context
        from giso.ai_brain import chat_with_managed_ai as _chat_managed
        # Build prompt with context
        system_prompt = context.get("prompt") or ""
        full_prompt = f"{system_prompt}\n\nکاربر: {user_message}\nمشاور:"
        try:
            reply = str(_chat_managed([{'role':'user','content':full_prompt}], actor_key='beauty_mirror') or {}).strip() or f"برای {context.get('service_label')} با مدل {context.get('style_label')}: {context.get('short_reason')}"
        except Exception:
            # Fallback to simple echo with context
            reply = f"برای {context.get('service_label')} با مدل {context.get('style_label')}: {context.get('short_reason')} – {user_message} – لطفاً برای اجرای دقیق به متخصص مراجعه کن."
        return {"ok": True, "reply": reply, "context": context}
    except Exception as exc:
        return {"ok": False, "error": f"خطای مشاور: {str(exc)[:200]}"}, 500


@buti_ai_bp.route("/eyebrow/consultant", methods=["POST"])
def eyebrow_consultant_chat():
    """AI Consultant for eyebrow – same context pattern"""
    init_buti_ai_db()
    candidate = get_final_candidate(session)
    if not candidate:
        return {"ok": False, "error": "ابتدا مدل و عکس ابرو را انتخاب کن."}, 400
    try:
        from giso.buti_ai.consultant import build_consultant_context
        generation = candidate.get("generation") if isinstance(candidate.get("generation"), dict) else {}
        context = build_consultant_context("eyebrow", candidate, generation)
        user_message = (request.get_json(silent=True) or {}).get("message") or request.form.get("message") or ""
        user_message = str(user_message).strip()[:800]
        if not user_message:
            return {"ok": False, "error": "پیام خالی است."}, 400
        from giso.ai_brain import chat_with_managed_ai as _chat_managed
        system_prompt = context.get("prompt") or ""
        full_prompt = f"{system_prompt}\n\nکاربر: {user_message}\nمشاور:"
        try:
            reply = str(_chat_managed([{'role':'user','content':full_prompt}], actor_key='beauty_mirror') or {}).strip() or f"برای ابرو با مدل {context.get('style_label')}: {context.get('short_reason')}"
        except Exception:
            reply = f"برای ابرو با مدل {context.get('style_label')}: {context.get('short_reason')} – {user_message}"
        return {"ok": True, "reply": reply, "context": context}
    except Exception as exc:
        return {"ok": False, "error": f"خطای مشاور ابرو: {str(exc)[:200]}"}, 500


