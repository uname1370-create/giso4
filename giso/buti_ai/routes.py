# -*- coding: utf-8 -*-
"""
giso/buti_ai/routes.py — کنترلرهای وب و ای‌پی‌آی آینه زیبایی گیسو.

قانون مرز کد: منطق اختصاصی Buti AI داخل همین ماژول می‌ماند. اتصال به
بخش‌های دیگر Giso فقط نازک و ضروری است.
"""
import logging
import os
import uuid
from datetime import datetime

from flask import flash, jsonify, redirect, render_template, request, url_for
from flask_login import current_user

from giso.buti_ai import buti_ai_bp
from giso.buti_ai.schema import init_buti_ai_db
from giso.buti_ai.services import save_mirror_session
from giso.config import Config

logger = logging.getLogger("giso_buti_ai_routes")

ALLOWED_IMAGE_EXTENSIONS = {"jpg", "jpeg", "png", "webp"}
BUTI_UPLOAD_DIR = os.path.join(Config.GISO_DIR, "data", "uploads", "buti_ai", "eyebrow")

EYEBROW_STYLES = {
    "natural": {
        "label": "طبیعی و نچرال",
        "icon": "🌿",
        "summary": "فرم ملایم و نزدیک به حالت طبیعی ابرو؛ مناسب کسی که تغییر کم و شیک می‌خواهد.",
        "why": "این انتخاب ظاهر چهره را تازه‌تر می‌کند، بدون اینکه حالت صورت مصنوعی یا خیلی آرایش‌شده دیده شود.",
        "do": ["قوس خیلی ملایم", "حفظ ضخامت طبیعی", "مرتب‌سازی تاج ابرو", "پر کردن فاصله‌های کم با اجرای ظریف"],
        "avoid": ["قوس تیز", "تیره‌کردن زیاد", "نازک‌کردن بیش از حد"],
    },
    "microblading": {
        "label": "میکروبلیدینگ ظریف",
        "icon": "✍️",
        "summary": "ظاهر تاربه‌تار و طبیعی‌تر برای ابروهای کم‌پشت یا نامنظم.",
        "why": "میکروبلیدینگ وقتی خوب است که هدف، پرتر دیده‌شدن ابرو بدون سایه سنگین باشد.",
        "do": ["تارهای خیلی ظریف", "رنگ نزدیک به موی ابرو", "تمرکز روی قسمت‌های خالی", "حفظ شروع نرم ابرو"],
        "avoid": ["رنگ خیلی تیره", "کادر تیز", "پر کردن یکدست مثل تتوی قدیمی"],
    },
    "powder": {
        "label": "شیدینگ پودری",
        "icon": "☁️",
        "summary": "فرم مرتب‌تر و کمی آرایش‌شده‌تر؛ مناسب ظاهر منظم و پرتر.",
        "why": "شیدینگ پودری برای کسانی مناسب است که ابروی مرتب، یکدست و کمی میکاپ‌شده دوست دارند.",
        "do": ["گرادیان نرم", "دم ابرو کمی مشخص‌تر", "رنگ ملایم", "حفظ تقارن"],
        "avoid": ["سایه خیلی پررنگ", "ابتدای ابروی بلوکی", "تغییر زیاد در فرم طبیعی"],
    },
    "combination": {
        "label": "کامبینیشن",
        "icon": "✨",
        "summary": "ترکیب تاربه‌تار و شیدینگ برای نتیجه کامل‌تر اما همچنان قابل کنترل.",
        "why": "کامبینیشن وقتی مناسب است که هم جاهای خالی ابرو نیاز به تار دارد، هم انتهای ابرو کمی حجم و نظم می‌خواهد.",
        "do": ["تارهای ظریف در تاج", "شیدینگ سبک در انتها", "قوس متعادل", "اجرای مرحله‌ای"],
        "avoid": ["ترکیب بیش از حد سنگین", "تیره‌کردن کل ابرو", "قوس غیرطبیعی"],
    },
    "giso_suggested": {
        "label": "نمی‌دانم؛ گیسو پیشنهاد بدهد",
        "icon": "🪞",
        "summary": "انتخاب امن برای شروع؛ گیسو یک فرم طبیعی و متعادل را پیشنهاد می‌دهد.",
        "why": "وقتی هنوز مطمئن نیستی چه تکنیکی می‌خواهی، بهتر است با فرم طبیعی و قابل اصلاح شروع شود.",
        "do": ["شروع با تغییر کم", "تمرکز روی تقارن", "حفظ هویت چهره", "مشاوره با متخصص قبل از اجرای نهایی"],
        "avoid": ["تصمیم عجولانه برای تغییر زیاد", "انتخاب تکنیک فقط براساس اسم", "کپی‌کردن فرم ابروی فرد دیگر"],
    },
}

CHANGE_LEVELS = {
    "very_natural": "خیلی طبیعی",
    "medium": "کمی تغییر",
    "clear": "تغییر واضح‌تر",
}


def _safe_current_user_id():
    try:
        if getattr(current_user, "is_authenticated", False):
            return getattr(current_user, "id", None)
    except Exception:
        return None
    return None


def _selected_or_default(value, allowed, default):
    value = (value or "").strip()
    return value if value in allowed else default


def _save_eyebrow_photo(file_storage):
    """ذخیره امن عکس MVP داخل محدوده runtime Buti AI؛ خروجی برای UI ساده است."""
    if not file_storage or not getattr(file_storage, "filename", ""):
        return {"ok": False, "reason": "empty", "message": "عکسی انتخاب نشده است."}

    filename = file_storage.filename or ""
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if ext not in ALLOWED_IMAGE_EXTENSIONS:
        return {
            "ok": False,
            "reason": "bad_extension",
            "message": "فرمت عکس باید jpg، png یا webp باشد.",
        }

    try:
        os.makedirs(BUTI_UPLOAD_DIR, exist_ok=True)
        safe_name = f"eyebrow_{datetime.utcnow().strftime('%Y%m%d%H%M%S')}_{uuid.uuid4().hex[:12]}.{ext}"
        path = os.path.join(BUTI_UPLOAD_DIR, safe_name)
        file_storage.save(path)

        # فشرده‌سازی سبک، مشابه مسیر آنالیز، ولی مستقل داخل Buti AI.
        try:
            from PIL import Image

            img = Image.open(path)
            img.thumbnail((1200, 1200))
            if ext in ("jpg", "jpeg"):
                if img.mode not in ("RGB", "L"):
                    img = img.convert("RGB")
                img.save(path, "JPEG", quality=86)
            elif ext == "png":
                img.save(path, "PNG")
            elif ext == "webp":
                img.save(path, "WEBP", quality=86)
        except Exception as exc:
            logger.debug("buti_ai eyebrow image resize skipped: %s", exc)

        return {"ok": True, "path": path, "filename": safe_name, "message": "عکس دریافت شد."}
    except Exception as exc:
        logger.error("Buti AI eyebrow photo save failed: %s", exc)
        return {"ok": False, "reason": "save_failed", "message": "ذخیره عکس انجام نشد. لطفاً دوباره تلاش کنید."}


def _build_eyebrow_result(style_key, change_key, photo_status, demo_mode=False):
    style = EYEBROW_STYLES.get(style_key) or EYEBROW_STYLES["giso_suggested"]
    change_label = CHANGE_LEVELS.get(change_key, CHANGE_LEVELS["very_natural"])

    if change_key == "clear":
        change_note = "چون تغییر واضح‌تر انتخاب شده، پیشنهاد MVP این است که فرم نهایی حتماً با متخصص کنترل شود تا حالت چهره عوض نشود."
    elif change_key == "medium":
        change_note = "برای تغییر متوسط، بهتر است قوس و دم ابرو کمی اصلاح شود اما تاج ابرو نرم بماند."
    else:
        change_note = "برای نتیجه طبیعی، بهتر است فقط نظم، تقارن و پرکردن نقاط خالی در اولویت باشد."

    return {
        "style_key": style_key,
        "style": style,
        "change_key": change_key,
        "change_label": change_label,
        "change_note": change_note,
        "photo_received": bool(photo_status.get("ok")),
        "demo_mode": demo_mode,
        "mvp_notice": "این نتیجه نسخه اول آینه ابرو است. تحلیل دقیق AI و پیش‌نمایش تصویری در فاز بعد اضافه می‌شود.",
    }


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
    services = [
        {
            "key": "eyebrow",
            "title": "آینه ابرو گیسو",
            "icon": "🪞",
            "description": "فرم مناسب ابرو را قبل از انجام، ساده و قابل فهم بررسی کن.",
            "href": url_for("buti_ai.eyebrow_wizard"),
            "status": "active",
        },
        {
            "key": "hair_color",
            "title": "رنگ مو",
            "icon": "🎨",
            "description": "پیش‌نمایش رنگ مو در مرحله‌های بعدی اضافه می‌شود.",
            "href": "#coming-soon",
            "status": "soon",
        },
        {
            "key": "face_beauty",
            "title": "زیبایی چهره",
            "icon": "✨",
            "description": "سناریوهای بعدی مثل لب، پوست و میکاپ بعداً زیر همین ماژول می‌آیند.",
            "href": "#coming-soon",
            "status": "soon",
        },
    ]
    return render_template("buti_ai/mirror_home.html", services=services)


@buti_ai_bp.route("/eyebrow", methods=["GET", "POST"])
def eyebrow_wizard():
    """MVP فاز ۱ آینه ابرو: انتخاب سبک، آپلود/دمو و نتیجه متنی امن."""
    init_buti_ai_db()
    result = None
    form_values = {"style": "giso_suggested", "change_level": "very_natural"}
    error_message = ""

    if request.method == "POST":
        style_key = _selected_or_default(request.form.get("style"), EYEBROW_STYLES, "giso_suggested")
        change_key = _selected_or_default(request.form.get("change_level"), CHANGE_LEVELS, "very_natural")
        demo_mode = request.form.get("demo_mode") == "1"
        form_values = {"style": style_key, "change_level": change_key}

        photo_status = {"ok": False, "reason": "empty", "message": "عکسی انتخاب نشده است."}
        if not demo_mode:
            photo_status = _save_eyebrow_photo(request.files.get("photo"))
            if not photo_status.get("ok"):
                error_message = photo_status.get("message") or "عکس دریافت نشد."
        if demo_mode or photo_status.get("ok"):
            result = _build_eyebrow_result(style_key, change_key, photo_status, demo_mode=demo_mode)
            session_id = save_mirror_session(
                user_id=_safe_current_user_id(),
                service_type="eyebrow",
                city="مشهد",
                status="mvp_demo" if demo_mode else "mvp_photo_received",
            )
            result["session_id"] = session_id
            if demo_mode:
                flash("نتیجه نمونه بدون عکس نمایش داده شد. برای تحلیل دقیق‌تر، در فاز بعد عکس بررسی می‌شود.", "info")
            else:
                flash("عکس دریافت شد و نتیجه MVP آماده است.", "success")

    return render_template(
        "buti_ai/eyebrow_wizard.html",
        styles=EYEBROW_STYLES,
        change_levels=CHANGE_LEVELS,
        form_values=form_values,
        result=result,
        error_message=error_message,
    )


@buti_ai_bp.route("/eyebrow/centers", methods=["GET"])
def eyebrow_centers():
    """اتصال نازک به مراکز زیبایی؛ مالک منطق مرکز همچنان beauty_centers است."""
    return redirect(url_for("beauty_centers.list_centers", service="eyebrow"))
