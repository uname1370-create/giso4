# -*- coding: utf-8 -*-
"""
Override امن برای _final_analysis — بدون بازنویسی کل analysis.py
اعمال از wsgi.py / create_app پس از ثبت روت‌ها.
"""
import json
import logging

from flask import request, redirect, url_for, flash, session
from flask_login import current_user

from giso.models import Analysis

logger = logging.getLogger("giso_analysis_override")


def _final_analysis_fixed(analysis_type):
    """نسخه اصلاح‌شده: session + auth قبل از نیاز به ana + تشخیص صحیح گزارش نهایی."""
    # import محلی برای دسترسی به توابع همان ماژول (rate limit, vision, ...)
    from giso import analysis as m

    # 1) همیشه پاسخ POST را نگه دار تا بعد از لاگین از دست نرود
    if request.method == "POST":
        try:
            session["pending_analysis_answers"] = request.form.to_dict()
            form_aid = (request.form.get("analysis_id") or "").strip()
            if form_aid.isdigit():
                session["current_analysis_id"] = int(form_aid)
        except Exception:
            pass

    # 2) لاگین نبود → ثبت‌نام (نه صفحه انتخاب آنالیز)
    if not current_user.is_authenticated:
        return redirect(url_for("analysis_register"))

    # 3) پیدا کردن رکورد آنالیز
    aid = session.get("current_analysis_id")
    ana = None
    if aid:
        try:
            ana = Analysis.query.get(int(aid))
        except Exception:
            ana = None
    if not ana or (ana.type or "hair") != analysis_type:
        try:
            phone = getattr(current_user, "phone", "") or ""
            q = Analysis.query.filter_by(type=analysis_type)
            if phone:
                q = q.filter_by(phone=phone)
            else:
                q = q.filter_by(user_id=getattr(current_user, "id", None))
            cand = q.order_by(Analysis.id.desc()).limit(5).all()
            for c in cand:
                qa = (c.questions_answers or "").strip()
                if not qa or qa in ("{}", "null"):
                    ana = c
                    session["current_analysis_id"] = c.id
                    break
            if not ana and cand:
                ana = cand[0]
                session["current_analysis_id"] = ana.id
        except Exception as e:
            logger.error("recover analysis: %s", e)
    if not ana or (ana.type or "hair") != analysis_type:
        flash("⚠️ جلسه آنالیز منقضی شده. لطفاً دوباره از آپلود عکس شروع کن.", "warning")
        return redirect(url_for("analysis"))

    # 4) گزارش نهایی واقعاً تمام شده؟
    try:
        _existing_report = json.loads(ana.ai_report_json or "{}")
    except Exception:
        _existing_report = {}
    qa_done = bool((ana.questions_answers or "").strip()) and (ana.questions_answers or "").strip() not in ("{}", "null")
    final_markers = ("immediate_actions", "condition", "main_problems")
    if qa_done and isinstance(_existing_report, dict) and any(k in _existing_report for k in final_markers):
        if analysis_type == "hair":
            return redirect(url_for("analysis_report_hair"))
        return redirect(url_for("analysis_report_skin"))

    # A2: GET بدون answers ذخیره‌شده → شروع مجدد
    if request.method == "GET" and not session.get("pending_analysis_answers"):
        flash("⚠️ لطفاً سوالات را از ابتدا پاسخ دهید.", "warning")
        return redirect(url_for("analysis"))

    phone = getattr(current_user, "phone", "") or ""
    ip = request.remote_addr or ""
    rl = m.check_rate_limit(ip, phone, analysis_type)
    if not rl.get("allowed"):
        wait = rl.get("wait_minutes", 0)
        flash(
            f"⏱ برای تحلیل بعدی، {wait} دقیقه دیگه تلاش کن. تحلیل قبلی‌ت هنوز معتبره و می‌تونی دوباره ببینیش.",
            "warning",
        )
        return redirect(url_for("analysis"))

    initial = {}
    try:
        initial = json.loads(ana.ai_report_json or "{}")
    except Exception:
        initial = {}
    if request.method == "POST":
        answers = request.form.to_dict()
    elif session.get("pending_analysis_answers"):
        answers = session.pop("pending_analysis_answers")
    else:
        answers = {}
    try:
        ana.questions_answers = json.dumps(answers, ensure_ascii=False)
    except Exception:
        pass
    user_name = getattr(current_user, "name", "") or "دوست عزیز"
    user_city = getattr(current_user, "city", "") or getattr(current_user, "region", "") or ""

    prompt_name = "hair_final_analysis.txt" if analysis_type == "hair" else "skin_final_analysis.txt"
    prompt = m._load_prompt(prompt_name)
    context = json.dumps(
        {
            "initial_analysis": initial,
            "user_answers": answers,
            "user_name": user_name,
            "user_city": user_city,
        },
        ensure_ascii=False,
    )
    full_prompt = prompt + "\n\n" + context

    images = []
    try:
        images = json.loads(ana.image_paths or "[]")
    except Exception:
        images = []
    result = m.call_vision_with_fallback(images, full_prompt, max_tokens=2000)

    if not result.get("ok"):
        m._cleanup_files(images)
        flash(result.get("error", "⚠️ سرویس تحلیل تصویر موقتاً در دسترس نیست."), "danger")
        return redirect(url_for("analysis"))

    data = result.get("data") or {}
    is_valid, missing = m._validate_structured_output(data, analysis_type)
    if not is_valid:
        logger.warning("AI output missing structured fields: %s", missing)
        data = m._ensure_structured_fallback(data, analysis_type)
    try:
        from giso.models import db

        photo_path = ""
        first_img = images[0] if images else ""
        if first_img:
            photo_path = first_img.split("uploads/")[-1] if "uploads/" in first_img else first_img
        ana.phone = phone or ana.phone
        ana.user_id = getattr(current_user, "id", None) or ana.user_id
        ana.photo_path = photo_path or "analysis/"
        ana.ai_report_json = json.dumps(data, ensure_ascii=False)
        db.session.commit()
        data["_analysis_id"] = ana.id
    except Exception as e:
        logger.error("update analysis final: %s", e)

    m._record_rate_limit(ip, phone, analysis_type)

    try:
        m._cleanup_files(images)
        session.pop("current_analysis_id", None)
        session.pop("pending_analysis_answers", None)
    except Exception:
        pass

    if analysis_type == "hair":
        return redirect(url_for("analysis_report_hair"))
    return redirect(url_for("analysis_report_skin"))


def install():
    """جایگزینی _final_analysis در ماژول analysis (lookup در زمان فراخوانی)."""
    try:
        from giso import analysis as m

        m._final_analysis = _final_analysis_fixed
        logger.info("analysis_final_override: _final_analysis patched")
        return True
    except Exception as e:
        logger.error("analysis_final_override install failed: %s", e)
        return False
