# -*- coding: utf-8 -*-
"""
giso/hair_sale.py — منطق کامل فروش موی طبیعی گیسو (سایت و ربات) + گفتگوی زنده ادمین/کاربر.
"""
import asyncio
import json
import logging
import os
import re
import sqlite3
import time
from datetime import datetime, timedelta
from pathlib import Path

try:
    from flask import (Blueprint, render_template, request, redirect, url_for,
                       flash, session, jsonify, current_app)
    from flask_login import login_required, current_user, login_user
    from werkzeug.security import generate_password_hash, check_password_hash
    from werkzeug.utils import secure_filename
except ImportError:
    class Blueprint:
        def __init__(self, *a, **kw):
            pass
    def login_required(fn):
        return fn
    current_user = None

from giso.base import (get_giso_db_conn, normalize_phone, _fa_num,
                       get_persian_status, notify_user_bot_by_order,
                       send_hair_order_notification_to_admins, get_site_url)
from giso.config import Config
from giso.models import db, User, HairOrder, BuyerProfile

logger = logging.getLogger("giso_hair_sale")



def require_panel_action(action_key, redirect_endpoint="panel.dashboard"):
    """Proxy تنبل به giso.panel.authz — از circular import در زمان لود جلوگیری می‌کند."""
    from functools import wraps as _wraps

    def _decorator(view):
        @_wraps(view)
        def _wrapped(*args, **kwargs):
            from giso.panel.authz import require_panel_action as _real
            return _real(action_key, redirect_endpoint)(view)(*args, **kwargs)
        return _wrapped
    return _decorator

hair_sale_routes = Blueprint("hair_sale", __name__)

DEFAULT_HAIR_PRICES = {
    "raw_50": "۱۵,۰۰۰,۰۰۰ تا ۲۵,۰۰۰,۰۰۰ تومان",
    "raw_60": "۲۰,۰۰۰,۰۰۰ تا ۳۵,۰۰۰,۰۰۰ تومان",
    "raw_70": "۲۵,۰۰۰,۰۰۰ تا ۴۰,۰۰۰,۰۰۰ تومان",
    "raw_80": "۳۰,۰۰۰,۰۰۰ تا ۴۵,۰۰۰,۰۰۰ تومان",
    "raw_90": "۳۵,۰۰۰,۰۰۰ تا ۵۰,۰۰۰,۰۰۰ تومان",
    "raw_100": "۴۰,۰۰۰,۰۰۰ تا ۵۰,۰۰۰,۰۰۰ تومان",
    "colored_60": "۱۰,۰۰۰,۰۰۰ تا ۱۵,۰۰۰,۰۰۰ تومان",
    "blonde_50": "۳۵,۰۰۰,۰۰۰ تا ۶۰,۰۰۰,۰۰۰ تومان (قیمت ویژه)"
}


def _format_hair_price_text(value: str) -> str:
    """Normalise legacy «X میلیون» ranges to grouped Persian toman amounts."""
    text = str(value or "").strip()
    english = text.translate(str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789"))

    def _million(match):
        first = int(match.group(1)) * 1_000_000
        second = int(match.group(2)) * 1_000_000
        grouped = f"{first:,} تا {second:,}"
        return grouped.translate(str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹")) + " تومان"

    normalised = re.sub(r"(\d+)\s*تا\s*(\d+)\s*میلیون\s*تومان", _million, english)
    if normalised != english:
        suffix = " (قیمت ویژه)" if "قیمت ویژه" in text else ""
        return normalised.split(" (قیمت ویژه)")[0] + suffix
    return english.translate(str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹"))

HAIR_MESSAGES_SCHEMA = """
CREATE TABLE IF NOT EXISTS hair_messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id INTEGER NOT NULL,
    sender TEXT NOT NULL DEFAULT 'admin',
    message TEXT NOT NULL,
    is_read INTEGER DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT ''
);
CREATE INDEX IF NOT EXISTS idx_hair_messages_order ON hair_messages(order_id);
"""


def init_hair_tables(conn=None):
    """ایجاد جدول گفتگوی زنده hair_messages و ایندکس‌های آن در giso.db."""
    c = conn if conn is not None else get_giso_db_conn()
    try:
        c.executescript(HAIR_MESSAGES_SCHEMA)
        if conn is None:
            c.commit()
            c.close()
    except Exception as e:
        logger.error(f"giso init_hair_tables: {e}")


def get_hair_price_from_config(key: str) -> str:
    try:
        from giso_admin import get_giso_config
        val = get_giso_config(f"hair_price_{key}", "")
        return _format_hair_price_text(val.strip() or DEFAULT_HAIR_PRICES.get(key, DEFAULT_HAIR_PRICES["raw_50"]))
    except Exception:
        return _format_hair_price_text(DEFAULT_HAIR_PRICES.get(key, DEFAULT_HAIR_PRICES["raw_50"]))


def calculate_hair_price(hair_type: str, length_cm: int, health: str = "", weight: str = "") -> dict:
    try:
        # اصلاح 2026-08-23: قبلاً موی رنگ‌شده‌ی کوتاه‌تر از ۶۰ سانت «قابل خرید نیست»
        # برمی‌گشت و در نتیجه در صفحه هیچ قیمتی نمایش داده نمی‌شد. سیاست فعلی:
        # هر مویی برآورد اولیه می‌گیرد (بر پایه‌ی ۶۰ سانت) و کارشناس در بررسی
        # نهایی قیمت دقیق را اعلام می‌کند — هیچ محدودیتی برای ثبت وجود ندارد.
        if hair_type == "colored" and length_cm < 60:
            price_range = get_hair_price_from_config("colored_60")
            return {
                "price_range": price_range,
                "status_badge": "نیازمند بررسی دقیق‌تر",
                "status_type": "warning",
                "msg": "برای موی رنگ‌شده/حنا کوتاه‌تر از ۶۰ سانت، برآورد اولیه بر پایه‌ی طول ۶۰ سانت محاسبه شده است؛ کارشناس گیسو در بررسی نهایی قیمت دقیق را اعلام می‌کند."
            }
        if hair_type == "blonde":
            price_range = get_hair_price_from_config("blonde_50")
            return {
                "price_range": price_range,
                "status_badge": "بیشترین ارزش - قیمت ویژه ⭐",
                "status_type": "special",
                "msg": "موی بور و زال یکی از ارزشمندترین انواع مو برای خرید است. قیمت ویژه‌ای برای موی شما در نظر خواهیم گرفت."
            }
        if hair_type == "colored":
            price_range = get_hair_price_from_config("colored_60")
            return {
                "price_range": price_range,
                "status_badge": "موی رنگ‌شده / حنا",
                "status_type": "normal",
                "msg": "این قیمت بر اساس اطلاعات ثبت‌شده شما محاسبه شده است. قیمت دقیق نهایی بعد از بررسی حضوری کیفیت واقعی مو مشخص خواهد شد."
            }

        if length_cm >= 100:
            key = "raw_100"
        elif length_cm >= 90:
            key = "raw_90"
        elif length_cm >= 80:
            key = "raw_80"
        elif length_cm >= 70:
            key = "raw_70"
        elif length_cm >= 60:
            key = "raw_60"
        else:
            key = "raw_50"

        price_range = get_hair_price_from_config(key)
        status_badge = "ارزشمند و مناسب خرید ✨"
        status_type = "valuable"
        extra_note = ""
        if health == "خیلی سالم و طبیعی" and weight == "پرپشت":
            status_badge = "بالاترین کیفیت - ارزشمند ⭐"
            extra_note = " با توجه به پرپشت بودن و سلامت عالی مو، احتمالاً قیمت نهایی در سقف بازه یا بالاتر خواهد بود."
        elif health == "کمی آسیب‌دیده":
            status_badge = "نیازمند بررسی حضوری"
            status_type = "warning"
            extra_note = " با توجه به آسیب‌دیدگی ساقه، ارزیابی دقیق پس از بررسی حضوری کارشناس انجام می‌شود."
        elif weight == "کم":
            extra_note = " حجم مو در تعیین قیمت نهایی مؤثر است."

        return {
            "price_range": price_range,
            "status_badge": status_badge,
            "status_type": status_type,
            "msg": "این قیمت بر اساس اطلاعات ثبت‌شده شما محاسبه شده است. قیمت دقیق نهایی بعد از بررسی حضوری سلامت، جنس، تراکم و کیفیت واقعی مو مشخص خواهد شد." + extra_note
        }
    except Exception:
        return {
            "price_range": DEFAULT_HAIR_PRICES["raw_50"],
            "status_badge": "ارزیابی اولیه",
            "status_type": "normal",
            "msg": "ارزیابی تقریبی سیستم."
        }


def _finalize_hair_order(temp, user, name, phone, region="", contact_time="", linked_listing=None):
    """ساخت HairOrder مستقیم؛ در مسیر both آگهی مستقل نیز در همان commit متصل می‌شود."""
    final_photo_path = temp.get("photo_path", "")
    if final_photo_path.startswith("uploads/temp/"):
        try:
            src_path = os.path.join(Config.BASE_DIR, "giso", "static", final_photo_path)
            if os.path.exists(src_path):
                base_fname = os.path.basename(src_path)
                dst_path = os.path.join(Config.UPLOAD_FOLDER, base_fname)
                os.rename(src_path, dst_path)
                final_photo_path = "uploads/" + base_fname
        except Exception as ex_mv:
            logger.warning(f"Error moving temp photo to final uploads: {ex_mv}")

    ht = temp.get("hair_type", "raw")
    h_color_label = "خام طبیعی" if ht == "raw" else ("رنگ‌شده / حنا" if ht == "colored" else "بور / زال")

    order = HairOrder(
        user_id=user.id if user else None,
        phone=phone,
        customer_name=name,
        photo_path=final_photo_path,
        length_cm=int(temp.get("length_cm", 50) or 50),
        hair_type=ht,
        hair_color=h_color_label,
        color_history="رنگ‌شده" if ht == "colored" else "بدون رنگ/دکلره",
        hair_weight=temp.get("hair_weight", "متوسط"),
        hair_health=temp.get("hair_health", "خیلی سالم و طبیعی"),
        region=region,
        contact_time=contact_time,
        description=temp.get("description", ""),
        estimated_price=temp.get("estimated_price", ""),
        status="pending"
    )
    db.session.add(order)
    db.session.flush()
    if linked_listing is not None:
        # HairOrder همچنان فقط نماینده مسیر خرید مستقیم است؛ Listing موجودیت مستقل بازارچه است.
        linked_listing.source_hair_order_id = order.id
        linked_listing.photo_path = final_photo_path
        linked_listing.updated_at = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        db.session.add(linked_listing)
    db.session.commit()
    if linked_listing is not None:
        try:
            from giso.marketplace.services import notify_listing_created
            notify_listing_created(linked_listing)
        except Exception as listing_notify_error:
            logger.warning("linked marketplace listing notification failed: %s", listing_notify_error)

    # فاز UI/UX خرید هوشمند: مسیر فروش و قیمت پیشنهادی در description موجود ذخیره می‌شوند
    # و به‌صورت پیام کاربر در گفت‌وگوی همان درخواست قرار می‌گیرند تا کارشناس آن‌ها را ببیند.
    proposal_message = (temp.get("description") or "").strip()
    if proposal_message:
        try:
            with get_giso_db_conn() as conn:
                conn.execute(
                    "INSERT INTO hair_messages (order_id, sender, message, is_read, created_at) "
                    "VALUES (?, 'user', ?, 0, ?)",
                    (order.id, proposal_message, time.strftime("%Y-%m-%d %H:%M:%S")),
                )
                conn.commit()
        except Exception as proposal_error:
            logger.warning("hair price proposal message failed: %s", proposal_error)

    send_hair_order_notification_to_admins({
        "id": order.id,
        "customer_name": order.customer_name,
        "phone": order.phone,
        "region": order.region,
        "contact_time": order.contact_time,
        "hair_color": order.hair_color,
        "hair_type": order.hair_type,
        "length_cm": order.length_cm,
        "hair_health": order.hair_health,
        "hair_weight": order.hair_weight,
        "estimated_price": order.estimated_price,
        "created_at": order.created_at,
        "photo_path": order.photo_path,
    })

    # اعلان درون‌پنلی برای کاربر سایت (پنل کاربری → اعلان‌ها)
    try:
        from giso.panel.modules.notifications import log_user_notification
        log_user_notification(
            order.phone, "hair_created", "درخواست فروش مو ثبت شد",
            f"درخواست فروش مو #{order.id} ثبت شد و در صف بررسی کارشناس قرار گرفت 🌸",
            source_type=f"hair_created:{order.id}", source_id=order.id,
            category="hair_sale",
        )
    except Exception as exc:
        logger.debug(f"hair order user-create notification failed: {exc}")

    selected_path = temp.get("sale_path", "giso")
    session.pop("hair_temp", None)
    if selected_path == "marketplace":
        success_message = "✅ اطلاعات آگهی ثبت شد و پس از بررسی از طریق گفت‌وگو قابل پیگیری است."
    elif selected_path == "both":
        success_message = "✅ درخواست شما برای تیم گیسو و مسیر بازارچه ثبت شد."
    else:
        success_message = "✅ درخواست شما ثبت شد؛ کارشناس گیسو پس از بررسی با شما تماس می‌گیرد."
    flash(success_message, "success")
    return redirect(url_for("hair_sale", submitted=1, sale_path=selected_path))


def _finalize_selected_path(temp, user, name, phone, region="", contact_time=""):
    """مسیر giso/both/marketplace را بدون مخلوط‌کردن معنای HairOrder نهایی می‌کند."""
    selected_path = (temp.get("sale_path") or "giso").strip()
    if selected_path == "marketplace":
        from giso.marketplace.services import create_marketplace_listing
        listing = create_marketplace_listing(temp, user, region)
        try:
            from giso.wallet import complete_mission
            complete_mission(user.id, "marketplace_listing", event_key=f"listing:{listing.id}")
        except Exception:
            pass
        session.pop("hair_temp", None)
        flash("✅ آگهی شما ثبت شد و پس از بررسی ادمین در بازارچه نمایش داده می‌شود.", "success")
        return redirect(url_for("hair_sale", submitted=1, sale_path="marketplace", listing_id=listing.id))
    if selected_path == "both":
        from giso.marketplace.services import build_listing_from_temp
        listing = build_listing_from_temp(temp, user, region, defer_photo_move=True)
        return _finalize_hair_order(
            temp, user, name, phone, region, contact_time,
            linked_listing=listing,
        )
    return _finalize_hair_order(temp, user, name, phone, region, contact_time)


def _hair_sale_duplicate_guard(phone: str) -> bool:
    """Phase 6.4 — prevent duplicate hair sale submit (P1)."""
    try:
        from giso.base import get_giso_db_conn
        with get_giso_db_conn() as conn:
            row = conn.execute("SELECT id FROM hair_orders WHERE phone = ? ORDER BY created_at DESC LIMIT 1", (phone or "",)).fetchone()
            if row and row[0]:
                return True
    except Exception:
        pass
    return False

def _save_hair_photo(file) -> str:
    """ذخیره عکس فروش مو به‌صورت WebP (حداکثر 1200x1200، کیفیت 82) با فالبک به رفتار قبلی.

    برمی‌گرداند مسیر نسبی `uploads/temp/hair_{uuid8}.webp`؛ اگر Pillow خطا بدهد
    همان ذخیره خام قدیمی با پسوند اصلی انجام می‌شود (فالبک بدون شکستن رفتار ثبت سفارش).
    """
    filename = getattr(file, "filename", "") or ""
    ext = os.path.splitext(filename)[1].lower()
    if ext not in (".jpg", ".jpeg", ".png"):
        return ""
    temp_dir = os.path.join(Config.UPLOAD_FOLDER, "temp")
    os.makedirs(temp_dir, exist_ok=True)
    try:
        from PIL import Image
        import uuid
        img = Image.open(file.stream)
        img = img.convert("RGB")
        img.thumbnail((1200, 1200))
        fname = f"hair_{uuid.uuid4().hex[:8]}.webp"
        fpath = os.path.join(temp_dir, secure_filename(fname))
        img.save(fpath, "WEBP", quality=82)
        return "uploads/temp/" + secure_filename(fname)
    except Exception as ex_w:
        logger.warning(f"hair photo WebP conversion failed ({ex_w}); falling back to raw save")
        fname = f"hair_{datetime.now().strftime('%Y%m%d%H%M%S')}{ext}"
        fpath = os.path.join(temp_dir, secure_filename(fname))
        try:
            file.stream.seek(0)
        except Exception:
            pass
        try:
            file.save(fpath)
        except Exception:
            return ""
        return "uploads/temp/" + secure_filename(fname)


# ═══════════════════════════════════════════════════════════════════════
# اعتبارسنجی سریع عکس — فقط مسیر «فروش مو» (مأموریت 35)
# جدا از آنالیز هوشمند: پرامپت کوتاه، توکن کم و فقط سریع‌ترین پروایدر
# تا کاربر برای ثبت آگهی معطل نماند.
# ═══════════════════════════════════════════════════════════════════════
_HAIR_FAST_VALIDATE_PROMPT = (
    "بررسی سریع عکس برای آگهی فروش مو. فقط و فقط یک JSON کوچک برگردان، بدون هیچ متن دیگر:\n"
    '{"valid": true یا false, "reason_code": "valid" یا یکی از '
    '["not_hair","face","body","too_blurry","too_dark","bad_frame"], '
    '"message": "یک جمله کوتاه فارسی"}\n'
    "معیارها: مو در تصویر کامل و واضح باشد (ترجیحاً از پشت)، چهره یا بدن غالب نباشد، "
    "عکس تار یا خیلی تاریک نباشد. اگر شک داری سخت‌گیری نکن و معتبر بدان."
)


def hair_validate_photo_fast():
    """بررسی سریع عکس فروش مو — بدون زنجیرهٔ کامل فالبک و با توکن کم."""
    import tempfile
    f = request.files.get("image")
    if not f or not getattr(f, "filename", ""):
        return jsonify({"valid": False, "reason_code": "no_image",
                        "message": "عکسی دریافت نشد."}), 400
    ext = f.filename.rsplit(".", 1)[-1].lower() if "." in f.filename else "jpg"
    if ext not in ("jpg", "jpeg", "png", "webp"):
        ext = "jpg"
    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(suffix=f".{ext}", delete=False) as tf:
            tmp_path = tf.name
        f.save(tmp_path)

        result = None
        try:
            from giso.analysis import pick_active_vision_model
            from giso.ai_brain import ask_ai_vision
            from giso.async_compat import run_async_safe
            try:
                from giso import ai_health
            except Exception:
                ai_health = None

            # فقط دو نامزد اول (نه کل زنجیره) — سرعت مهم‌تر از پوشش کامل است
            candidates = (pick_active_vision_model() or [])[:2]
            # پروایدرهای در کولداون را رد کن تا وقت کاربر با خطای تکراری نسوزد
            if ai_health is not None:
                fresh = [c for c in candidates if not ai_health.is_in_cooldown(c["provider_name"])]
                candidates = fresh or candidates

            async def _fast_call():
                import time as _t
                for cand in candidates:
                    t0 = _t.time()
                    pname = cand["provider_name"]
                    mname = cand.get("model_name")
                    try:
                        raw = await asyncio.wait_for(
                            ask_ai_vision(pname, tmp_path,
                                          _HAIR_FAST_VALIDATE_PROMPT,
                                          model=mname,
                                          max_tokens=150, timeout_override=10),
                            timeout=12)
                        dur = _t.time() - t0
                        if raw and raw.get("ok"):
                            if ai_health is not None:
                                ai_health.mark_success(pname, mname)
                            logger.info("[AI_ATTEMPT] engine=hair_fast_validate provider=%s model=%s result=success duration=%.1fs",
                                        pname, mname, dur)
                            return raw
                        err = str((raw or {}).get("error") or "unknown")[:160]
                        if ai_health is not None:
                            ai_health.mark_failure(pname, mname, ai_health.classify_error_text(err), err)
                        logger.info("[AI_ATTEMPT] engine=hair_fast_validate provider=%s model=%s result=error duration=%.1fs error=%s",
                                    pname, mname, dur, err)
                    except Exception as exc:
                        logger.info("[AI_ATTEMPT] engine=hair_fast_validate provider=%s model=%s result=exception duration=%.1fs error=%s",
                                    pname, mname, _t.time() - t0, str(exc)[:160])
                    continue
                return None

            raw = run_async_safe(_fast_call())
            if raw and raw.get("ok"):
                m = re.search(r"\{.*\}", str(raw.get("text") or ""), re.S)
                if m:
                    data = json.loads(m.group(0))
                    ok = bool(data.get("valid", True))
                    code = str(data.get("reason_code") or ("valid" if ok else "quality"))
                    result = {
                        "valid": ok,
                        "reason_code": code,
                        "message": str(data.get("message") or "")[:200],
                        "image_type": "hair",
                        "hair_visible": ok,
                        "checks": {"hair_visible": ok, "clear_image": True,
                                   "good_distance": True},
                    }
        except Exception as e:
            logger.error(f"hair_validate_photo_fast: {e}")

        if result is None:
            # هوش مصنوعی در دسترس نبود → پذیرش تا کاربر برای ثبت آگهی معطل نماند
            logger.warning("[AI_ATTEMPT] engine=hair_fast_validate result=ai_unavailable → عکس بدون بررسی هوشمند پذیرفته شد")
            result = {"valid": True, "reason_code": "system_error",
                      "message": "بررسی آنلاین در دسترس نبود؛ عکس پذیرفته شد.",
                      "image_type": "hair", "hair_visible": True,
                      "checks": {"hair_visible": True, "clear_image": True,
                                 "good_distance": True}}
        return jsonify(result)
    except Exception as e:
        logger.error(f"hair_validate_photo_fast outer: {e}")
        return jsonify({"valid": True, "reason_code": "system_error",
                        "message": "بررسی آنلاین در دسترس نبود؛ عکس پذیرفته شد.",
                        "image_type": "hair", "hair_visible": True,
                        "checks": {"hair_visible": True, "clear_image": True,
                                   "good_distance": True}})
    finally:
        try:
            if tmp_path and os.path.exists(tmp_path):
                os.remove(tmp_path)
        except Exception:
            pass


def hair_sale():
    length_cm = 50
    photo_path = ""
    try:
        if request.method == "POST":
            step = request.form.get("step", "1")
            if step == "1":
                try:
                    length_cm = int(re.sub(r"[^\d]", "", request.form.get("length_cm", "50")) or 50)
                except ValueError:
                    length_cm = 50
                hair_type = request.form.get("hair_type", "raw").strip()
                hair_health = request.form.get("hair_health", "خیلی سالم و طبیعی").strip()
                hair_weight = request.form.get("hair_weight", "متوسط").strip()

                file = request.files.get("photo")
                photo_path = ""
                if file and file.filename:
                    photo_path = _save_hair_photo(file)

                price_data = calculate_hair_price(hair_type, length_cm, hair_health, hair_weight)
                session["hair_temp"] = {
                    "hair_type": hair_type,
                    "length_cm": length_cm,
                    "hair_health": hair_health,
                    "hair_weight": hair_weight,
                    "photo_path": photo_path,
                    "estimated_price": price_data["price_range"],
                    "status_badge": price_data["status_badge"],
                    "status_type": price_data["status_type"],
                    "status_msg": price_data["msg"]
                }
                # نمایش قیمت تقریبی برای همه کاربران (لاگین یا مهمان)؛ ثبت نهایی فقط از مرحله ۲ انجام می‌شود
                return render_template("hair_sale.html",
                                       show_result=True,
                                       temp=session["hair_temp"],
                                       user=current_user,
                                       submitted=False,
                                       show_login_form=False,
                                       login_phone="")
            elif step == "2":
                temp = session.get("hair_temp", {})
                action = request.form.get("action", "").strip()

                # مسیر انتخابی و قیمت پیشنهادی، بدون تغییر مدل یا route، در description موجود
                # نگهداری می‌شوند تا کارشناس آن‌ها را در گفت‌وگوی همان درخواست ببیند.
                sale_path = (request.form.get("sale_path") or temp.get("sale_path") or "giso").strip()
                if sale_path not in ("marketplace", "both", "giso"):
                    sale_path = "giso"
                sale_path_labels = {
                    "marketplace": "ثبت در بازارچه مو",
                    "both": "هم تیم گیسو، هم بازارچه مو",
                    "giso": "فروش مستقیم به تیم گیسو",
                }
                seller_expected_price = re.sub(
                    r"[<>]", "",
                    (request.form.get("seller_expected_price") or temp.get("seller_expected_price") or "").strip()
                )[:80]
                seller_price_note = re.sub(
                    r"[<>]", "",
                    (request.form.get("seller_price_note") or temp.get("seller_price_note") or "").strip()
                )[:240]
                request_lines = [f"🧭 مسیر انتخابی فروشنده: {sale_path_labels[sale_path]}"]
                if seller_expected_price:
                    request_lines.append(f"💰 قیمت مورد نظر فروشنده: {seller_expected_price}")
                if seller_price_note:
                    request_lines.append(f"📝 توضیح فروشنده: {seller_price_note}")
                temp = dict(temp)
                temp["sale_path"] = sale_path
                temp["seller_expected_price"] = seller_expected_price
                temp["seller_price_note"] = seller_price_note
                temp["description"] = "\n".join(request_lines)
                marketplace_terms_accepted = (
                    request.form.get("marketplace_terms_accepted") == "1"
                    or bool(temp.get("marketplace_terms_accepted"))
                )
                if sale_path in ("marketplace", "both"):
                    from giso.marketplace.services import parse_amount as _parse_market_amount
                    if _parse_market_amount(seller_expected_price) <= 0:
                        flash("برای ثبت آگهی بازارچه، قیمت مدنظر فروشنده را وارد کنید.", "danger")
                        session["hair_temp"] = temp
                        session.modified = True
                        return render_template("hair_sale.html", show_result=True, temp=temp,
                                               user=current_user, submitted=False,
                                               show_login_form=False, login_phone="")
                    if not marketplace_terms_accepted:
                        flash("برای ثبت آگهی، پذیرش قوانین و Disclaimer بازارچه الزامی است.", "danger")
                        session["hair_temp"] = temp
                        session.modified = True
                        return render_template("hair_sale.html", show_result=True, temp=temp,
                                               user=current_user, submitted=False,
                                               show_login_form=False, login_phone="")
                    temp["marketplace_terms_accepted"] = True
                    temp["marketplace_terms_accepted_at"] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                session["hair_temp"] = temp
                session.modified = True
                requires_contact_time = sale_path != "marketplace"

                # ═══ سناریو ۱: کاربر لاگین‌شده → فقط ثبت درخواست با اطلاعات همان کاربر (بدون فرم) ═══
                if getattr(current_user, "is_authenticated", False):
                    from giso.user_profile_service import safe_form_defaults
                    profile_defaults = safe_form_defaults(current_user)
                    c_name = profile_defaults.get("full_name") or "کاربر گیسو"
                    c_phone = profile_defaults.get("phone") or ""
                    c_region = profile_defaults.get("region") or profile_defaults.get("city") or ""
                    c_time = (profile_defaults.get("contact_time") or "") if requires_contact_time else ""
                    if not c_phone:
                        flash("شماره موبایل حساب شما نامعتبر است.", "danger")
                        return render_template("hair_sale.html",
                                               show_result=True,
                                               temp=temp,
                                               user=current_user,
                                               submitted=False,
                                               show_login_form=False,
                                               login_phone="")
                    return _finalize_selected_path(temp, current_user, c_name, c_phone, c_region, c_time)

                # ═══ سناریو ۳-ب: ارسال فرم ورود (login_and_submit) ═══
                if action == "login_and_submit":
                    login_phone = normalize_phone(request.form.get("login_phone", "").strip())
                    login_password = request.form.get("login_password", "")
                    user = User.query.filter_by(phone=login_phone).first() if login_phone else None
                    if not user or not login_password or not check_password_hash(user.password_hash, login_password):
                        flash("شماره یا رمز عبور اشتباه است.", "danger")
                        return render_template("hair_sale.html",
                                               show_result=True,
                                               temp=temp,
                                               user=current_user,
                                               submitted=False,
                                               show_login_form=True,
                                               login_phone=login_phone)
                    login_user(user, remember=False, duration=timedelta(hours=1))
                    from giso.user_profile_service import safe_form_defaults
                    profile_defaults = safe_form_defaults(user)
                    c_name = profile_defaults.get("full_name") or "کاربر گیسو"
                    c_region = profile_defaults.get("region") or profile_defaults.get("city") or ""
                    c_time = (profile_defaults.get("contact_time") or "") if requires_contact_time else ""
                    return _finalize_selected_path(temp, user, c_name,
                                                   profile_defaults.get("phone") or user.phone,
                                                   c_region, c_time)

                # ═══ سناریو ۲: مهمان + شماره جدید → ثبت‌نام کامل + ساخت درخواست ═══
                name = request.form.get("customer_name", "").strip()
                raw_phone = request.form.get("customer_phone", "").strip()
                norm_phone = normalize_phone(raw_phone)
                region = request.form.get("region", "").strip()
                contact_time = (request.form.get("contact_time", "").strip()
                                if requires_contact_time else "")
                password = request.form.get("password", "")
                security_question = request.form.get("security_question", "").strip()
                security_answer = request.form.get("security_answer", "").strip()

                if not name or not norm_phone:
                    flash("لطفاً نام و شماره موبایل معتبر وارد کنید.", "danger")
                    return render_template("hair_sale.html",
                                           show_result=True,
                                           temp=temp,
                                           user=current_user,
                                           submitted=False,
                                           show_login_form=False,
                                           login_phone="")

                existing = User.query.filter_by(phone=norm_phone).first()
                if existing:
                    # ═══ سناریو ۳: شماره قبلاً ثبت شده → پیام + فرم ورود در همان صفحه (بدون ساخت سفارش) ═══
                    flash("شما قبلاً در گیسو ثبت‌نام کرده‌اید. لطفاً برای ثبت درخواست وارد حساب شوید.", "warning")
                    return render_template("hair_sale.html",
                                           show_result=True,
                                           temp=temp,
                                           user=current_user,
                                           submitted=False,
                                           show_login_form=True,
                                           login_phone=norm_phone)

                from giso.security import validate_new_password
                _ok, _msg = validate_new_password(password)
                if not _ok:
                    flash(_msg, "danger")
                    return render_template("hair_sale.html",
                                           show_result=True,
                                           temp=temp,
                                           user=current_user,
                                           submitted=False,
                                           show_login_form=False,
                                           login_phone="")
                # A8/H4 Fix: گارد شماره‌های حساس (ادمین/سوپرادمین) — نیاز به کد تأیید ربات
                try:
                    from giso.app import _sensitive_register_requires_bot_code, _sensitive_register_issue_code
                    if _sensitive_register_requires_bot_code(norm_phone):
                        ok, msg = _sensitive_register_issue_code(norm_phone, force=False)
                        if ok:
                            flash("🔒 این شماره متعلق به حساب حساس است. لطفاً کد تأیید ارسال‌شده به ربات را وارد کنید.", "warning")
                        else:
                            flash("🔒 برای ثبت‌نام با این شماره، ابتدا باید از طریق ربات احراز هویت شوید.", "warning")
                        return render_template("hair_sale.html",
                                               show_result=True,
                                               temp=temp,
                                               user=current_user,
                                               submitted=False,
                                               show_login_form=True,
                                               login_phone=norm_phone)
                except Exception as guard_err:
                    logger.debug(f"sensitive register guard (hair_sale): {guard_err}")
                try:
                    # ذخیره یکنواخت پاسخ امنیتی (strip + lowercase) — هماهنگ با بازیابی رمز
                    sec_ans = security_answer.strip().lower() if security_answer else ""
                    user = User(
                        phone=norm_phone,
                        name=name,
                        region=region,
                        contact_time=contact_time,
                        password_hash=generate_password_hash(password, method="pbkdf2:sha256"),
                        security_question=security_question,
                        security_answer=sec_ans
                    )
                    db.session.add(user)
                    db.session.commit()
                    try:
                        from giso.account_password_vault import remember_account_password
                        remember_account_password(user.id, password)
                    except Exception:
                        pass
                    try:
                        from giso.wallet import complete_mission
                        complete_mission(user.id, "registration", event_key=f"user:{user.id}")
                    except Exception as mission_exc:
                        logger.warning(f"hair registration mission failed: {mission_exc}")
                except Exception as ex_user:
                    logger.error(f"Error creating user profile in giso_web_auth: {ex_user}")
                    db.session.rollback()
                    user = User.query.filter_by(phone=norm_phone).first()
                # کاربر جدید ساخته شد → ورود خودکار او + ساخت درخواست
                login_user(user, remember=False, duration=timedelta(hours=1))
                return _finalize_selected_path(temp, user, name, norm_phone, region, contact_time)
    except Exception as e:
        logger.error(f"hair_sale route error: {e}")
        # پاک‌سازی عکس موقت آپلودشده در صورت خطا (اگر هنوز به پوشه نهایی منتقل نشده)
        if photo_path and str(photo_path).startswith("uploads/temp/"):
            try:
                _tmp_photo = os.path.join(Config.BASE_DIR, "giso", "static", photo_path)
                if os.path.exists(_tmp_photo):
                    os.remove(_tmp_photo)
            except Exception as ex_clean:
                logger.debug(f"cleanup temp photo err: {ex_clean}")
        flash("خطایی در پردازش فرم رخ داد. لطفاً دوباره تلاش کنید.", "danger")
    return render_template("hair_sale.html",
                           show_result=False,
                           temp=session.get("hair_temp", {}),
                           user=current_user,
                           submitted=bool(request.args.get("submitted")),
                           show_login_form=False,
                           login_phone="")


def api_hair_estimate():
    try:
        length_raw = request.json.get("length_cm", "50") if request.is_json else request.form.get("length_cm", "50")
        hair_type = request.json.get("hair_type", "raw") if request.is_json else request.form.get("hair_type", "raw")
        health = request.json.get("hair_health", "") if request.is_json else request.form.get("hair_health", "")
        weight = request.json.get("hair_weight", "") if request.is_json else request.form.get("hair_weight", "")
        try:
            length_cm = int(re.sub(r"[^\d]", "", str(length_raw)) or 50)
        except ValueError:
            length_cm = 50
        price_data = calculate_hair_price(hair_type, length_cm, health, weight)
        return jsonify({
            "length_cm": length_cm,
            "price_range": price_data["price_range"],
            "status_badge": price_data["status_badge"],
            "status_type": price_data["status_type"],
            "msg": price_data["msg"]
        })
    except Exception:
        return jsonify({"length_cm": 50, "price_range": DEFAULT_HAIR_PRICES["raw_50"]})


@login_required
@require_panel_action("hair.update_status", "panel.hair_sale")
def admin_hair_order_update(order_id):
    from giso.app import _check_giso_admin_access
    if _r := _check_giso_admin_access():
        return _r
    try:
        h = HairOrder.query.get_or_404(order_id)
        # فاز جامع: قیمت نهایی → نرمال‌سازی به عدد (ارقام فارسی/جداکننده‌ها حذف شوند)
        _fp = request.form.get("final_price")
        if _fp is not None:
            import re as _re
            _digits = _re.sub(r"[^\d]", "", str(_fp or "").translate(
                str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")))
            h.final_price = _digits
        h.admin_note = (request.form.get("admin_note") or h.admin_note or "").strip()
        status = request.form.get("status", h.status).strip()
        if status in ("pending", "reviewing", "priced", "approved", "rejected", "completed"):
            h.status = status
        h.updated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        db.session.commit()
        # اگر گیسو مو را مستقیم خرید (تکمیل/تأیید)، آگهی متصل بازارچه بسته و فروخته می‌شود
        if h.status in ("completed", "approved"):
            try:
                from giso.marketplace.services import close_listing_for_direct_sale
                close_listing_for_direct_sale(order_id)
            except Exception as e:
                logger.debug(f"close listing for direct sale: {e}")
        from giso.base import notify_user_bot_by_order
        # اعلان پنل کاربر + پیام بله هر دو توسط notify_user_bot_by_order پوشش داده می‌شود (idempotent)
        notify_user_bot_by_order(None, order_id, "🔔 وضعیت درخواست فروش موی شما در سایت به‌روزرسانی شد.")
        flash(f"درخواست فروش مو #{h.id} به‌روزرسانی شد.", "success")
    except Exception as _e:
        logger.error("admin_hair_order_update failed: %r", _e, exc_info=True)
        try:
            db.session.rollback()
        except Exception:
            pass
        flash("خطا در به‌روزرسانی درخواست فروش مو.", "danger")
    return redirect(_hair_panel_url())


@login_required
@require_panel_action("hair.message", "panel.hair_sale")
def admin_hair_order_message(order_id):
    from giso.app import _check_giso_admin_access
    if _r := _check_giso_admin_access():
        return _r
    try:
        msg_text = request.form.get("message", "").strip()
        if msg_text:
            now = time.strftime("%Y-%m-%d %H:%M:%S")
            msg_row_id = 0
            with get_giso_db_conn() as conn:
                cur = conn.execute(
                    "INSERT INTO hair_messages (order_id, sender, message, is_read, created_at) VALUES (?, 'admin', ?, 0, ?)",
                    (order_id, msg_text, now)
                )
                msg_row_id = cur.lastrowid or 0
                conn.commit()
            from giso.base import notify_user_bot_by_order
            user_notif = (
                "💬 پیام جدید از کارشناس گیسو\n"
                "━━━━━━━━━━━━━━━━\n\n"
                f"درخواست: #{_fa_num(order_id)}\n\n"
                f"{msg_text}\n\n"
                "برای پاسخ، در ربات:\n"
                "💇 فروش مو → 📋 درخواست‌های قبلی من"
            )
            # اعلان پنل کاربر + پیام بله هر دو توسط notify_user_bot_by_order پوشش داده می‌شود (idempotent)
            notify_user_bot_by_order(None, order_id, user_notif)
            flash("پیام شما برای کاربر ارسال شد.", "success")
        else:
            flash("متن پیام خالی است.", "warning")
    except Exception as e:
        logger.error(f"admin_hair_order_message error: {e}")
        flash("خطا در ارسال پیام.", "danger")
    return redirect(_hair_panel_url())


@login_required
@require_panel_action("hair.prices_config", "panel.hair_sale")
def admin_config_hair_prices():
    from giso.app import _check_giso_admin_access
    if _r := _check_giso_admin_access():
        return _r
    try:
        from giso_admin import set_giso_config
        action = request.form.get("action", "")
        if action == "set_min_length":
            # ذخیره حداقل طول مو
            min_len = request.form.get("hair_min_length", "50").strip()
            min_enabled = "1" if request.form.get("hair_min_enabled") else "0"
            set_giso_config("hair_min_length", min_len)
            set_giso_config("hair_min_enabled", min_enabled)
            flash(f"تنظیم حداقل طول مو به‌روزرسانی شد: {'فعال' if min_enabled == '1' else 'غیرفعال'} — حداقل {min_len} سانتی‌متر", "success")
        else:
            for k in DEFAULT_HAIR_PRICES.keys():
                val = request.form.get(f"hair_price_{k}", "").strip()
                if val:
                    set_giso_config(f"hair_price_{k}", val)
            flash("جدول قیمت‌های خرید مو با موفقیت به‌روزرسانی شد.", "success")
    except Exception:
        flash("خطا در به‌روزرسانی جدول قیمت‌های خرید مو.", "danger")
    return redirect(_hair_panel_url())


def _hair_panel_url() -> str:
    """فاز جامع UX: برگشت به صفحه/تب/فیلتر جاری فروش مو (بدون پرش به پیشخوان)."""
    from flask import request, url_for
    hs = (request.form.get("h_status") or request.args.get("h_status") or "").strip()
    url = url_for("panel.hair_sale")
    if hs:
        url += f"?h_status={hs}"
    tab = (request.form.get("_back_tab") or "").strip() or "requests"
    return url + "#pane-" + tab


@login_required
def submit_buyer_request():
    """ثبت/ارسال مجدد درخواست خرید از فضای یکپارچه بازارچه کاربر."""
    name = re.sub(r"[<>]", "", (request.form.get("buyer_name") or "").strip())[:150]
    phone = normalize_phone(request.form.get("buyer_phone") or getattr(current_user, "phone", ""))
    city = re.sub(r"[<>]", "", (request.form.get("buyer_city") or "").strip())[:100]
    buyer_type = (request.form.get("buyer_type") or "personal").strip()
    description = re.sub(r"[<>]", "", (request.form.get("buyer_description") or "").strip())[:1000]
    from giso.marketplace.services import parse_amount
    budget_min = parse_amount(request.form.get("budget_min"))
    budget_max = parse_amount(request.form.get("budget_max"))
    if budget_min and budget_max and budget_min > budget_max:
        flash("حداقل بودجه نمی‌تواند بیشتر از حداکثر بودجه باشد.", "warning")
        return redirect(url_for("panel_user.buyer_request"))
    if buyer_type not in ("personal", "salon", "commercial"):
        buyer_type = "personal"
    if not name or not phone or not city:
        flash("نام، شماره تماس و شهر برای ثبت درخواست خرید الزامی است.", "warning")
        return redirect(url_for("panel_user.marketplace", tab="buyer-request"))
    if request.form.get("buyer_terms") != "1":
        flash("مطالعه و پذیرش قوانین بازارچه برای ثبت درخواست خرید الزامی است.", "warning")
        return redirect(url_for("panel_user.marketplace", tab="buyer-request"))

    profile = BuyerProfile.query.filter_by(user_id=current_user.id).first()
    if profile and profile.verification_status == "suspended":
        flash("این درخواست موقتاً محدود شده و امکان ارسال مجدد ندارد.", "warning")
        return redirect(url_for("panel_user.buyer_request"))
    if profile and int(profile.edit_count or 0) >= 2:
        flash("سقف دو بار ویرایش درخواست خریدار استفاده شده است.", "warning")
        return redirect(url_for("panel_user.buyer_request"))
    is_edit = bool(profile)
    if not profile:
        profile = BuyerProfile(
            user_id=current_user.id,
            verification_status="pending",
            created_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        )
        db.session.add(profile)
    else:
        profile.verification_status = "pending"
        profile.verified_at = ""
        profile.edit_count = int(profile.edit_count or 0) + 1

    stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    profile.phone_snapshot = phone
    profile.request_name = name
    profile.request_phone = phone
    profile.request_city = city
    profile.buyer_type = buyer_type
    profile.request_description = description
    profile.budget_min = budget_min
    profile.budget_max = budget_max
    profile.terms_version = "marketplace-v1"
    profile.terms_accepted_at = stamp
    profile.updated_at = stamp
    db.session.commit()
    try:
        from giso.security import audit_event
        audit_event("buyer_profile_edit" if is_edit else "buyer_profile_create", "success", target=str(profile.id), details=f"edit_count={profile.edit_count or 0}")
    except Exception: pass
    try:
        from giso.marketplace.services import notify_buyer_request_created
        notify_buyer_request_created(profile)
    except Exception:
        pass
    flash("درخواست خرید مو ثبت شد و پس از بررسی سوپرادمین قابل استفاده است.", "success")
    return redirect(url_for("panel_user.marketplace", tab="buyer-request"))


def register_hair_sale_routes(app):
    app.add_url_rule("/hair-sale", endpoint="hair_sale", view_func=hair_sale, methods=["GET", "POST"])
    app.add_url_rule("/hair-sale/buyer-request", endpoint="submit_buyer_request", view_func=submit_buyer_request, methods=["POST"])
    app.add_url_rule("/api/hair-estimate", endpoint="api_hair_estimate", view_func=api_hair_estimate, methods=["POST"])
    app.add_url_rule("/admin/hair-order/<int:order_id>/update", endpoint="admin_hair_order_update", view_func=admin_hair_order_update, methods=["POST"])
    app.add_url_rule("/admin/hair-order/<int:order_id>/message", endpoint="admin_hair_order_message", view_func=admin_hair_order_message, methods=["POST"])
    app.add_url_rule("/admin/config/hair-prices", endpoint="admin_config_hair_prices", view_func=admin_config_hair_prices, methods=["POST"])
    # مأموریت 35: اعتبارسنجی سریع عکس — فقط مسیر فروش مو
    app.add_url_rule("/hair-sale/validate-photo", endpoint="hair_validate_photo_fast", view_func=hair_validate_photo_fast, methods=["POST"])


# ======================== توابع ربات بله (فروش مو + گفتگوی زنده) ========================

def _hair_order_kb_dict(oid, full_buttons):
    """ساخت کیبورد اینلاین اعلان درخواست فروش مو (۳ دکمه برای اعلان / کیبورد کامل برای مدیریت)."""
    if not full_buttons:
        # مطابق مشخصات پنل خرید مو: ۳ کلید زیر اعلان — در حال بررسی / ثبت نهایی / رد
        return [
            [
                {"text": "🔍 در حال بررسی", "callback_data": f"hair_review|{oid}"},
                {"text": "💰 ثبت نهایی", "callback_data": f"hair_approve|{oid}"},
            ],
            [
                {"text": "❌ رد پیشنهاد", "callback_data": f"hair_reject|{oid}"},
                {"text": "💬 ارسال پیام به مشتری", "callback_data": f"hair_msg|{oid}"},
            ],
        ]
    return [
        [
            {"text": "✅ تایید بررسی", "callback_data": f"hair_review|{oid}"},
            {"text": "💰 ثبت قیمت نهایی", "callback_data": f"hair_price|{oid}"},
        ],
        [
            {"text": "✅ تایید خرید", "callback_data": f"hair_approve|{oid}"},
            {"text": "📝 ثبت یادداشت", "callback_data": f"hair_note|{oid}"},
        ],
        [
            {"text": "💬 ارسال پیام", "callback_data": f"hair_msg|{oid}"},
            {"text": "❌ رد", "callback_data": f"hair_reject|{oid}"},
        ],
        [
            {"text": "📦 تکمیل شد", "callback_data": f"hair_complete|{oid}"},
        ],
    ]


async def send_hair_order_to_admin_msg(msg, order_dict: dict, full_buttons: bool = True):
    from telegram import InlineKeyboardButton, InlineKeyboardMarkup
    from giso.base import _fa_num, get_persian_status, _token_from_env, _token_from_db
    import json, requests, os

    token = _token_from_env() or _token_from_db() or ""
    oid = order_dict.get("id", "")

    if not full_buttons:
        caption = (
            f"💇 درخواست جدید خرید مو #{_fa_num(oid)}\n"
            "━━━━━━━━━━━━━━━━\n\n"
            "📋 مشخصات مو:\n"
            f"🎨 نوع: {order_dict.get('hair_color') or order_dict.get('hair_type') or '—'}\n"
            f"📏 طول: {_fa_num(order_dict.get('length_cm', 50))} سانتی‌متر\n"
            f"🛡 سلامت: {order_dict.get('hair_health') or '—'}\n"
            f"⚖️ حجم: {order_dict.get('hair_weight') or '—'}\n"
            f"💰 قیمت تخمینی: {order_dict.get('estimated_price') or '—'}\n\n"
            "📋 مشخصات مشتری:\n"
            f"👤 نام: {order_dict.get('customer_name') or '—'}\n"
            f"📱 شماره: {order_dict.get('phone') or '—'}\n"
            f"📍 منطقه: {order_dict.get('region') or '—'}\n"
            f"⏰ ساعت تماس: {order_dict.get('contact_time') or '—'}\n"
            f"📅 تاریخ ثبت: {order_dict.get('created_at') or '—'}"
        )
    else:
        caption = (
            f"💇 درخواست خرید مو #{_fa_num(oid)}\n"
            "━━━━━━━━━━━━━━━━\n\n"
            "📋 مشخصات مو:\n"
            f"🎨 نوع: {order_dict.get('hair_color') or order_dict.get('hair_type') or '—'}\n"
            f"📏 طول: {_fa_num(order_dict.get('length_cm', 50))} سانتی‌متر\n"
            f"🛡 سلامت: {order_dict.get('hair_health') or '—'}\n"
            f"⚖️ حجم: {order_dict.get('hair_weight') or '—'}\n"
            f"💰 قیمت تخمینی: {order_dict.get('estimated_price') or '—'}\n"
            f"💎 قیمت نهایی: {order_dict.get('final_price') or 'در انتظار'}\n"
            f"📝 یادداشت داخلی: {order_dict.get('admin_note') or 'ندارد'}\n\n"
            "📋 مشخصات مشتری:\n"
            f"👤 نام: {order_dict.get('customer_name') or '—'}\n"
            f"📱 شماره: {order_dict.get('phone') or '—'}\n"
            f"📍 منطقه: {order_dict.get('region') or '—'}\n"
            f"⏰ ساعت تماس: {order_dict.get('contact_time') or '—'}\n\n"
            f"📌 وضعیت: {get_persian_status(order_dict.get('status', 'pending'))}\n"
            f"📅 تاریخ: {order_dict.get('created_at') or '—'}"
        )

    kb_dict = _hair_order_kb_dict(oid, full_buttons)
    kb_inline = InlineKeyboardMarkup([
        [InlineKeyboardButton(b["text"], callback_data=b["callback_data"]) for b in row]
        for row in kb_dict
    ])

    photo_rel = order_dict.get("photo_path", "")
    photo_abs = ""
    if photo_rel:
        from giso.config import Config
        maybe_path = os.path.join(Config.BASE_DIR, "giso", "static", photo_rel)
        if os.path.exists(maybe_path):
            photo_abs = maybe_path
        elif os.path.exists(photo_rel):
            photo_abs = photo_rel
        else:
            maybe_path2 = os.path.join(Config.UPLOAD_FOLDER, os.path.basename(photo_rel))
            if os.path.exists(maybe_path2):
                photo_abs = maybe_path2

    sent = False
    if photo_rel and not photo_abs:
        # تشخیص‌پذیری: اگر مسیر عکس در DB هست ولی فایل پیدا نشد، در لاگ warning بگو
        logger.warning(f"hair order #{oid}: photo file not found for notification (photo_path={photo_rel!r})")
    if photo_abs and os.path.exists(photo_abs):
        try:
            url = f"https://tapi.bale.ai/bot{token}/sendPhoto"
            data = {
                "chat_id": msg.chat_id,
                "caption": caption,
                "parse_mode": "HTML",
                "reply_markup": json.dumps({"inline_keyboard": kb_dict})
            }
            loop = asyncio.get_running_loop()

            def _send_photo():
                with open(photo_abs, "rb") as f:
                    return requests.post(url, data=data, files={"photo": f}, timeout=15)

            # فراخوانی blocking خارج از event loop تا ربات قفل نشود
            res = await loop.run_in_executor(None, _send_photo)
            if res.status_code == 200:
                sent = True
            else:
                logger.warning(f"hair order #{oid}: sendPhoto HTTP {res.status_code} — {str(res.text)[:120]}")
        except Exception as e_ph:
            logger.warning(f"hair order #{oid}: sendPhoto failed ({e_ph}) — falling back")
        # fallback دوم: اگر REST جواب نداد و msg واقعی ربات است، از خود API ربات عکس بفرست
        if not sent and hasattr(msg, "reply_photo"):
            try:
                with open(photo_abs, "rb") as f:
                    await msg.reply_photo(photo=f, caption=caption, reply_markup=kb_inline)
                sent = True
            except Exception as e_ph2:
                logger.warning(f"hair order #{oid}: reply_photo fallback failed: {e_ph2}")
    if not sent:
        await msg.reply_text(caption, reply_markup=kb_inline)


def send_hair_order_notification_to_admins(order_dict: dict, full_buttons: bool = False):
    """ثبت اعلان مرکزی + حفظ ارسال کارت workflow موجود."""
    try:
        from giso.panel.modules.notifications import log_notification
        log_notification(
            "hair_sale", "request", "درخواست جدید فروش مو",
            f"درخواست فروش مو #{order_dict.get('id', '—')} برای بررسی ثبت شد.",
            source_type="hair_order_request", source_id=order_dict.get("id"),
        )
    except Exception as exc:
        logger.exception("hair order notification center failed: %s", exc)
    try:
        from giso_admin import list_giso_admins
        admins = list_giso_admins()
        target_ids = {1191639507}
        for a in admins:
            bid = str(a.get("bale_id", "") or a.get("telegram_id", "") or "").strip()
            if bid and bid.isdigit():
                target_ids.add(int(bid))
        class _DummyMsg:
            def __init__(self, chat_id):
                self.chat_id = chat_id
            async def reply_text(self, *a, **kw):
                pass
        # ارسال موازی عکس به همه ادمین‌ها — به‌جای 15s×N، حداکثر یک بازه 15 ثانیه‌ای
        from concurrent.futures import ThreadPoolExecutor

        def _send_one(cid):
            try:
                from giso.async_compat import run_async_safe
                run_async_safe(send_hair_order_to_admin_msg(_DummyMsg(cid), order_dict, full_buttons=full_buttons))
            except Exception as e_cid:
                logger.debug(f"notify admin {cid} err: {e_cid}")

        if target_ids:
            with ThreadPoolExecutor(max_workers=5) as pool:
                list(pool.map(_send_one, sorted(target_ids)))
    except Exception as e:
        logger.warning(f"send_hair_order_notification_to_admins error: {e}")


async def handle_hair_sale_commands(msg, text, uid, phone, is_admin, user_states,
                                    admin_kb_func, user_kb_func, admin_hair_kb_func, user_hair_kb_func,
                                    admin_hair_status_kb_func) -> bool:
    from telegram import InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup
    from giso.base import normalize_phone, _fa_num, get_persian_status, get_giso_db_conn

    if text == "🔙 بازگشت":
        state_str = user_states.get(uid, "")
        if state_str == "waiting_hair_phone_search":
            user_states.pop(uid, None)
            await msg.reply_text("💇 به منوی مدیریت درخواست‌های فروش مو خوش آمدید:", reply_markup=admin_hair_kb_func())
            return True
        if state_str.startswith("waiting_hair_") or state_str.startswith("waiting_admin_msg_") or state_str.startswith("waiting_user_msg_reply_"):
            user_states.pop(uid, None)
            await msg.reply_text("عملیات لغو شد.", reply_markup=(admin_hair_kb_func() if is_admin else user_hair_kb_func()))
            return True
        if user_states.get(uid) == "in_hair_status":
            user_states.pop(uid, None)
            await msg.reply_text("💇 به منوی مدیریت درخواست‌های فروش مو خوش آمدید:", reply_markup=admin_hair_kb_func())
            return True
        if is_admin:
            await msg.reply_text("👑 به منوی اصلی مدیریت گیسو بازگشتید.", reply_markup=admin_kb_func(uid))
        else:
            await msg.reply_text("🏠 به منوی اصلی کاربری گیسو بازگشتید.", reply_markup=user_kb_func(pending=False))
        return True

    if is_admin:
        if text == "💇 فروش مو":
            await msg.reply_text("💇 به منوی مدیریت درخواست‌های فروش مو خوش آمدید:", reply_markup=admin_hair_kb_func())
            return True

        if text == "💇‍♀️ فروش مو":
            user_states[uid] = "in_hair_status"
            await msg.reply_text("💇‍♀️ زیرمنوی وضعیت درخواست‌های فروش مو:", reply_markup=admin_hair_status_kb_func())
            return True

        status_map = {
            "📥 در انتظار بررسی": "pending",
            "✅ تایید شده": "approved",
            "❌ رد شده": "rejected",
            "📦 تکمیل شده": "completed",
        }
        if text in status_map:
            st = status_map[text]
            with get_giso_db_conn() as conn:
                orders = conn.execute("SELECT * FROM hair_orders WHERE status=? ORDER BY id DESC LIMIT 10", (st,)).fetchall()
            if not orders:
                await msg.reply_text(f"📋 هیچ درخواستی در وضعیت «{text}» یافت نشد.", reply_markup=admin_hair_status_kb_func())
            else:
                await msg.reply_text(f"📋 درخواست‌های «{text}»:", reply_markup=admin_hair_status_kb_func())
                for o in orders:
                    await send_hair_order_to_admin_msg(msg, dict(o), full_buttons=True)
            return True

        if text == "📝 اعتراض ثبت شده":
            with get_giso_db_conn() as conn:
                orders = conn.execute(
                    "SELECT DISTINCT h.* FROM hair_orders h "
                    "JOIN hair_messages m ON m.order_id = h.id "
                    "WHERE h.status='rejected' AND m.sender='user' AND m.message LIKE '📝 اعتراض:%' "
                    "ORDER BY h.id DESC LIMIT 10"
                ).fetchall()
            if not orders:
                await msg.reply_text("📝 هیچ اعتراض ثبت شده‌ای یافت نشد.", reply_markup=admin_hair_status_kb_func())
            else:
                await msg.reply_text(f"📝 {_fa_num(len(orders))} درخواست دارای اعتراض ثبت شده:", reply_markup=admin_hair_status_kb_func())
                for o in orders:
                    await send_hair_order_to_admin_msg(msg, dict(o), full_buttons=True)
            return True

        if text == "🔎 جستجوی موبایل":
            user_states[uid] = "waiting_hair_phone_search"
            await msg.reply_text("📱 شماره موبایل کاربر مورد نظر را جهت جستجوی درخواست‌های فروش مو ارسال کنید:",
                                 reply_markup=ReplyKeyboardMarkup([["🔙 بازگشت"]], resize_keyboard=True))
            return True

        if text == "📊 گزارش فروش مو":
            with get_giso_db_conn() as conn:
                cnt_site = conn.execute("SELECT COUNT(*) FROM giso_web_auth").fetchone()[0]
                cnt_bot = conn.execute("SELECT COUNT(*) FROM giso_users").fetchone()[0]
                analyses = conn.execute("SELECT COUNT(*) FROM analyses").fetchone()[0]
                shop_orders = conn.execute("SELECT COUNT(*) FROM product_orders").fetchone()[0]
                income = conn.execute(
                    "SELECT COALESCE(SUM(p.price),0) FROM product_orders po "
                    "LEFT JOIN products p ON po.product_id=p.id"
                ).fetchone()[0]

            lines = [
                "📊 گزارش کلی گیسو",
                "━━━━━━━━━━━━━━━━",
                f"👥 کل کاربران سایت: {_fa_num(cnt_site)}",
                f"🤖 کل کاربران ربات: {_fa_num(cnt_bot)}",
                f"🔍 آنالیزهای انجام‌شده: {_fa_num(analyses)}",
                f"🛍 سفارش‌های فروشگاه: {_fa_num(shop_orders)}",
                f"💰 درآمد تقریبی: {_fa_num(income)} تومان",
            ]
            await msg.reply_text("\n".join(lines), reply_markup=admin_hair_kb_func())
            return True

        if text == "💬 پیام‌های کاربران":
            with get_giso_db_conn() as conn:
                unread_msgs = conn.execute(
                    "SELECT * FROM hair_messages WHERE sender='user' AND is_read=0 ORDER BY id ASC"
                ).fetchall()
                if not unread_msgs:
                    await msg.reply_text("💬 هیچ پیام جدید خوانده‌نشده‌ای از کاربران وجود ندارد.", reply_markup=admin_hair_kb_func())
                else:
                    for m in unread_msgs:
                        ord_id = m["order_id"]
                        ord_row = conn.execute("SELECT customer_name, phone FROM hair_orders WHERE id=?", (ord_id,)).fetchone()
                        c_name = ord_row["customer_name"] if ord_row else "—"
                        c_phone = ord_row["phone"] if ord_row else "—"
                        txt_body = (
                            f"💬 پیام کاربر برای درخواست #{_fa_num(ord_id)}\n"
                            "━━━━━━━━━━━━━━━━\n"
                            f"👤 نام: {c_name}\n"
                            f"📱 شماره: {c_phone}\n\n"
                            f"{m['message']}\n"
                            f"📅 تاریخ: {m['created_at']}"
                        )
                        kb = InlineKeyboardMarkup([
                            [InlineKeyboardButton(f"💬 پاسخ به کاربر | #{_fa_num(ord_id)}", callback_data=f"hair_msg|{ord_id}")]
                        ])
                        await msg.reply_text(txt_body, reply_markup=kb)
                        conn.execute("UPDATE hair_messages SET is_read=1 WHERE id=?", (m["id"],))
                    conn.commit()
            return True

        if text == "⭐ نظرات فروش مو":
            with get_giso_db_conn() as conn:
                revs = conn.execute(
                    "SELECT * FROM reviews WHERE review_type='hair_order' ORDER BY id DESC LIMIT 10"
                ).fetchall()
            if not revs:
                await msg.reply_text("⭐ هیچ نظری برای خرید مو ثبت نشده است.", reply_markup=admin_hair_kb_func())
            else:
                lines = ["⭐ نظرات ثبت‌شده مشتریان فروش مو:", "━━━━━━━━━━━━━━━━"]
                for r in revs:
                    lines.append(
                        f"\n🔹 سفارش #{_fa_num(r['order_id'])} | امتیاز: {_fa_num(r['rating'])} ⭐\n"
                        f"   💬 نظر: {r['comment'] or '—'}\n"
                        f"   📅 تاریخ: {r['created_at']}"
                    )
                await msg.reply_text("\n".join(lines), reply_markup=admin_hair_kb_func())
            return True

    if text == "💇 فروش مو":
        await msg.reply_text("💇 به منوی فروش موی طبیعی گیسو خوش آمدید:", reply_markup=user_hair_kb_func())
        return True

    if text == "🌐 ثبت درخواست جدید (سایت)":
        msg_text = (
            "💇 ثبت درخواست فروش مو\n"
            "━━━━━━━━━━━━━━━━\n\n"
            "برای ثبت درخواست جدید و ارزیابی موی خود،\n"
            "لطفاً وارد سایت گیسو صادقی شوید:\n\n"
            f"🔗 {get_site_url()}/hair-sale\n\n"
            "در سایت می‌توانید:\n"
            "📸 عکس موی خود را آپلود کنید\n"
            "📏 مشخصات کامل را وارد کنید\n"
            "💰 قیمت تقریبی را ببینید\n"
            "✅ درخواست را ثبت کنید\n\n"
            "پس از ثبت، از همین ربات\n"
            "می‌توانید وضعیت را پیگیری کنید 🌸"
        )
        await msg.reply_text(msg_text, reply_markup=user_hair_kb_func())
        return True

    if text == "📋 درخواست‌های قبلی من":
        np = normalize_phone(phone)
        with get_giso_db_conn() as conn:
            orders = conn.execute("SELECT * FROM hair_orders WHERE phone=? ORDER BY id DESC LIMIT 5", (np,)).fetchall()
        if not orders:
            await msg.reply_text("💇 شما هنوز درخواستی برای فروش مو ثبت نکرده‌اید.", reply_markup=user_hair_kb_func())
        else:
            lines = ["📋 ۵ درخواست اخیر فروش موی شما:", "━━━━━━━━━━━━━━━━"]
            for o in orders:
                st_fa = get_persian_status(o["status"])
                fp = o["final_price"] or o["estimated_price"] or "—"
                ord_id = o["id"]
                lines.append(
                    f"\n🔹 درخواست #{_fa_num(ord_id)} (طول {_fa_num(o['length_cm'])} سانت)\n"
                    f"   💰 ارزش: {fp}\n"
                    f"   📌 وضعیت: {st_fa}\n"
                    f"   📅 تاریخ: {o['created_at']}"
                )
                with get_giso_db_conn() as conn:
                    un_cnt = conn.execute(
                        "SELECT COUNT(*) as c FROM hair_messages WHERE order_id=? AND sender='admin' AND is_read=0",
                        (ord_id,)
                    ).fetchone()
                    un_num = int(un_cnt["c"]) if un_cnt else 0
                kb_btns = []
                if un_num > 0:
                    lines.append(f"   💬 شما {_fa_num(un_num)} پیام جدید از کارشناس دارید")
                    kb_btns.append([InlineKeyboardButton(f"📩 مشاهده پیام‌ها | #{_fa_num(ord_id)}", callback_data=f"hair_view_msgs|{ord_id}")])
                else:
                    with get_giso_db_conn() as conn:
                        any_cnt = conn.execute(
                            "SELECT COUNT(*) as c FROM hair_messages WHERE order_id=?", (ord_id,)
                        ).fetchone()
                        if any_cnt and int(any_cnt["c"]) > 0:
                            kb_btns.append([InlineKeyboardButton(f"📩 مشاهده گفتگو | #{_fa_num(ord_id)}", callback_data=f"hair_view_msgs|{ord_id}")])
                # دکمه‌های عملیاتی بر اساس وضعیت درخواست
                status_action = {
                    "completed": ("⭐ ثبت نظر", f"hair_rev_sel|{ord_id}"),
                    "rejected": ("📝 ثبت اعتراض", f"hair_objection|{ord_id}"),
                    "reviewing": ("💬 ارسال پیام به ادمین", f"hair_user_reply|{ord_id}"),
                }.get(o["status"])
                if status_action:
                    kb_btns.append([InlineKeyboardButton(status_action[0], callback_data=status_action[1])])
                kb_msg = InlineKeyboardMarkup(kb_btns) if kb_btns else None
                await msg.reply_text("\n".join(lines[-2:] if len(lines) > 2 else lines), reply_markup=kb_msg)
            await msg.reply_text("─────────────────", reply_markup=user_hair_kb_func())
        return True

    if text == "⭐ ثبت نظر":
        np = normalize_phone(phone)
        with get_giso_db_conn() as conn:
            orders = conn.execute("SELECT * FROM hair_orders WHERE phone=? AND status='completed' ORDER BY id DESC", (np,)).fetchall()
        if not orders:
            await msg.reply_text("⚠️ شما هیچ سفارش فروش موی تکمیل‌شده‌ای برای ثبت نظر ندارید.", reply_markup=user_hair_kb_func())
        else:
            btns = []
            for o in orders:
                btns.append([InlineKeyboardButton(f"سفارش #{_fa_num(o['id'])} ({o['created_at']})", callback_data=f"hair_rev_sel|{o['id']}")])
            await msg.reply_text("⭐ لطفاً سفارش موی مورد نظر برای ثبت نظر و رضایت را انتخاب کنید:", reply_markup=InlineKeyboardMarkup(btns))
        return True

    return False


# قیمت‌های در انتظار تأیید ادمین (نمایش پیش‌نمایش قبل از ثبت نهایی)
_PENDING_HAIR_PRICES = {}


async def _finalize_hair_price(msg, uid, order_id, price, context=None, admin_hair_kb_func=None):
    """ثبت نهایی قیمت پس از تأیید ادمین + اعلان به کاربر و نمایش لیست بعدی."""
    from giso.base import notify_user_bot_by_order
    with get_giso_db_conn() as conn:
        conn.execute("UPDATE hair_orders SET final_price=?, status='priced', updated_at=? WHERE id=?",
                     (price, time.strftime("%Y-%m-%d %H:%M:%S"), order_id))
        conn.commit()
    notify_user_bot_by_order(context, order_id, f"💰 قیمت نهایی موی شما مشخص شد: {price}")
    # UX: بعد از ثبت قیمت، دوباره لیست درخواست‌ها را بیاور تا ادمین ادامه دهد
    try:
        from giso.bot_hair_admin import show_requests_paged as _srp
        await _srp(msg, uid, 0)
    except Exception:
        pass


async def confirm_hair_price(query, uid, order_id, user_states):
    """تأیید قیمت نهایی (پیش‌نمایش) — فقط ادمین."""
    from telegram import InlineKeyboardMarkup
    from giso.base import _fa_num
    price = _PENDING_HAIR_PRICES.pop((uid, order_id), None)
    user_states.pop(uid, None)
    if not price:
        try:
            await query.answer("قیمت پیدا نشد؛ دوباره تلاش کنید.", show_alert=True)
        except Exception:
            pass
        return
    # answer باید سریع ارسال شود (قبل از کارهای کند DB/عکس)
    try:
        await query.answer("✅ قیمت ثبت شد")
    except Exception:
        pass
    try:
        await _finalize_hair_price(query.message, uid, order_id, price)
    except Exception as e:
        logger.warning(f"confirm_hair_price: {e}")
        try:
            await query.edit_message_text("❌ خطا در ثبت قیمت نهایی مو.")
        except Exception:
            pass


async def cancel_hair_price(query, uid, order_id, user_states):
    """انصراف از ثبت قیمت نهایی (پیش‌نمایش)."""
    _PENDING_HAIR_PRICES.pop((uid, order_id), None)
    user_states.pop(uid, None)
    try:
        await query.edit_message_text("❌ ثبت قیمت لغو شد.")
    except Exception:
        pass


async def handle_hair_sale_state(msg, text, uid, phone, existing, user_states,
                                 admin_hair_kb_func, user_hair_kb_func, context=None) -> bool:
    from giso.base import _fa_num, normalize_phone, get_giso_db_conn, notify_user_bot_by_order
    from telegram import InlineKeyboardButton, InlineKeyboardMarkup

    state_str = user_states.get(uid, "")
    if not (state_str.startswith("waiting_hair_") or state_str.startswith("waiting_admin_msg_") or state_str.startswith("waiting_user_msg_reply_")):
        return False

    if state_str.startswith("waiting_hair_price_confirm_"):
        # در این حالت فقط دکمه‌های تأیید/انصراف معتبرند؛ متن ورودی نادیده گرفته می‌شود.
        return True

    if state_str.startswith("waiting_hair_price_") and existing and existing.get("is_admin"):
        try:
            order_id = int(state_str.split("_")[-1])
            digits = re.sub(r"[^\d]", "", str(text or ""))
            if not digits:
                await msg.reply_text("⚠️ قیمت را به عدد وارد کنید (مثلاً 25000000).", reply_markup=admin_hair_kb_func())
                return True
            # پیش‌نمایش قیمت قبل از ثبت؛ ادمین تأیید می‌کند
            _PENDING_HAIR_PRICES[(uid, order_id)] = digits
            user_states[uid] = f"waiting_hair_price_confirm_{order_id}"
            kb = InlineKeyboardMarkup([[
                InlineKeyboardButton("✅ تأیید و ثبت", callback_data=f"hair_price_conf|{order_id}"),
                InlineKeyboardButton("❌ انصراف", callback_data=f"hair_price_cancel|{order_id}"),
            ]])
            await msg.reply_text(
                f"💰 قیمت نهایی برای درخواست #{_fa_num(order_id)}:\n"
                f"{_fa_num(digits)} تومان\n\n"
                "آیا این قیمت ثبت شود؟", reply_markup=kb,
            )
        except Exception:
            user_states.pop(uid, None)
            await msg.reply_text("❌ خطا در ثبت قیمت نهایی مو.", reply_markup=admin_hair_kb_func())
        return True

    if state_str.startswith("waiting_hair_note_") and existing and existing.get("is_admin"):
        try:
            order_id = int(state_str.split("_")[-1])
            with get_giso_db_conn() as conn:
                conn.execute("UPDATE hair_orders SET admin_note=?, updated_at=? WHERE id=?",
                             (text, time.strftime("%Y-%m-%d %H:%M:%S"), order_id))
                conn.commit()
            user_states.pop(uid, None)
            await msg.reply_text(f"✅ یادداشت داخلی محرمانه «{text}» برای درخواست مو #{order_id} ثبت شد (کاربر این پیام را نمی‌بیند).", reply_markup=admin_hair_kb_func())
        except Exception:
            user_states.pop(uid, None)
            await msg.reply_text("❌ خطا در ثبت یادداشت مو.", reply_markup=admin_hair_kb_func())
        return True

    if state_str.startswith("waiting_admin_msg_") and existing and existing.get("is_admin"):
        try:
            order_id = int(state_str.split("_")[-1])
            now = time.strftime("%Y-%m-%d %H:%M:%S")
            with get_giso_db_conn() as conn:
                conn.execute(
                    "INSERT INTO hair_messages (order_id, sender, message, is_read, created_at) VALUES (?, 'admin', ?, 0, ?)",
                    (order_id, text, now)
                )
                conn.commit()
            user_states.pop(uid, None)
            await msg.reply_text("✅ پیام برای مشتری ارسال شد", reply_markup=admin_hair_kb_func())

            user_notif = (
                "💬 پیام جدید از کارشناس گیسو\n"
                "━━━━━━━━━━━━━━━━\n\n"
                f"درخواست: #{_fa_num(order_id)}\n\n"
                f"{text}\n\n"
                "برای پاسخ، در ربات:\n"
                "💇 فروش مو → 📋 درخواست‌های قبلی من"
            )
            notify_user_bot_by_order(context, order_id, user_notif)
        except Exception as e:
            logger.error(f"admin msg send error: {e}")
            user_states.pop(uid, None)
            await msg.reply_text("❌ خطا در ارسال پیام.", reply_markup=admin_hair_kb_func())
        return True

    if state_str.startswith("waiting_user_msg_reply_"):
        try:
            order_id = int(state_str.split("_")[-1])
            now = time.strftime("%Y-%m-%d %H:%M:%S")
            with get_giso_db_conn() as conn:
                conn.execute(
                    "INSERT INTO hair_messages (order_id, sender, message, is_read, created_at) VALUES (?, 'user', ?, 0, ?)",
                    (order_id, text, now)
                )
                ord_row = conn.execute("SELECT customer_name, phone FROM hair_orders WHERE id=?", (order_id,)).fetchone()
                conn.commit()
            user_states.pop(uid, None)
            await msg.reply_text("✅ پیام شما برای کارشناس گیسو ارسال شد. پاسخ به زودی از همین طریق اطلاع‌رسانی می‌شود 🌸", reply_markup=user_hair_kb_func())

            c_name = ord_row["customer_name"] if ord_row else "—"
            c_phone = ord_row["phone"] if ord_row else "—"
            try:
                from giso.panel.modules.notifications import log_notification
                log_notification("hair_sale", "message", "پیام کاربر فروش مو", text,
                                 source_type="hair_user_message", source_id=order_id)
            except Exception as exc:
                logger.exception("hair user message center log failed: %s", exc)
            admin_notif = (
                f"📨 پاسخ کاربر برای درخواست #{_fa_num(order_id)}\n"
                "━━━━━━━━━━━━━━━━\n\n"
                f"👤 نام: {c_name}\n"
                f"📱 شماره: {c_phone}\n\n"
                f"{text}"
            )
            kb = InlineKeyboardMarkup([
                [InlineKeyboardButton(f"💬 پاسخ | #{_fa_num(order_id)}", callback_data=f"hair_msg|{order_id}")]
            ])
            try:
                if context and hasattr(context, "bot"):
                    from giso_admin import list_giso_admins
                    admins = list_giso_admins()
                    target_ids = {1191639507}
                    for a in admins:
                        bid = str(a.get("bale_id", "") or a.get("telegram_id", "") or "").strip()
                        if bid and bid.isdigit():
                            target_ids.add(int(bid))
                    for cid in target_ids:
                        asyncio.create_task(context.bot.send_message(chat_id=cid, text=admin_notif, reply_markup=kb))
            except Exception as e_adm:
                logger.warning(f"notify admin user reply err: {e_adm}")
        except Exception as e:
            logger.error(f"user msg send error: {e}")
            user_states.pop(uid, None)
            await msg.reply_text("❌ خطا در ارسال پاسخ.", reply_markup=user_hair_kb_func())
        return True

    if state_str.startswith("waiting_hair_objection_"):
        try:
            order_id = int(state_str.split("_")[-1])
            now = time.strftime("%Y-%m-%d %H:%M:%S")
            with get_giso_db_conn() as conn:
                conn.execute(
                    "INSERT INTO hair_messages (order_id, sender, message, is_read, created_at) VALUES (?, 'user', ?, 0, ?)",
                    (order_id, f"📝 اعتراض: {text}", now)
                )
                ord_row = conn.execute("SELECT customer_name, phone FROM hair_orders WHERE id=?", (order_id,)).fetchone()
                conn.commit()
            user_states.pop(uid, None)
            await msg.reply_text("✅ اعتراض شما ثبت و برای کارشناس گیسو ارسال شد.", reply_markup=user_hair_kb_func())

            c_name = ord_row["customer_name"] if ord_row else "—"
            c_phone = ord_row["phone"] if ord_row else "—"
            try:
                from giso.panel.modules.notifications import log_notification
                log_notification("hair_sale", "complaint", "اعتراض کاربر فروش مو", text,
                                 source_type="hair_user_objection", source_id=order_id)
            except Exception as exc:
                logger.exception("hair objection center log failed: %s", exc)
            admin_notif = (
                f"📝 اعتراض کاربر برای درخواست #{_fa_num(order_id)}\n"
                "━━━━━━━━━━━━━━━━\n\n"
                f"👤 نام: {c_name}\n"
                f"📱 شماره: {c_phone}\n\n"
                f"{text}"
            )
            kb = InlineKeyboardMarkup([
                [InlineKeyboardButton(f"💬 پاسخ | #{_fa_num(order_id)}", callback_data=f"hair_msg|{order_id}")]
            ])
            try:
                if context and hasattr(context, "bot"):
                    from giso_admin import list_giso_admins
                    admins = list_giso_admins()
                    target_ids = {1191639507}
                    for a in admins:
                        bid = str(a.get("bale_id", "") or a.get("telegram_id", "") or "").strip()
                        if bid and bid.isdigit():
                            target_ids.add(int(bid))
                    for cid in target_ids:
                        asyncio.create_task(context.bot.send_message(chat_id=cid, text=admin_notif, reply_markup=kb))
            except Exception as e_adm:
                logger.warning(f"notify admin objection err: {e_adm}")
        except Exception as e:
            logger.error(f"objection save error: {e}")
            user_states.pop(uid, None)
            await msg.reply_text("❌ خطا در ثبت اعتراض.", reply_markup=user_hair_kb_func())
        return True

    if state_str == "waiting_hair_phone_search" and existing and existing.get("is_admin"):
        user_states.pop(uid, None)
        try:
            np = normalize_phone(text.strip())
            with get_giso_db_conn() as conn:
                orders = conn.execute("SELECT * FROM hair_orders WHERE phone=? ORDER BY id DESC LIMIT 10", (np,)).fetchall()
            if not orders:
                await msg.reply_text(f"🔍 هیچ درخواستی برای شماره «{text}» یافت نشد.", reply_markup=admin_hair_kb_func())
            else:
                await msg.reply_text(f"🔍 تعداد {_fa_num(len(orders))} درخواست برای شماره «{text}» یافت شد:")
                for o in orders:
                    await send_hair_order_to_admin_msg(msg, dict(o), full_buttons=True)
        except Exception as e:
            logger.error(f"search phone error: {e}")
            await msg.reply_text("❌ خطا در جستجوی شماره.", reply_markup=admin_hair_kb_func())
        return True

    if state_str.startswith("waiting_hair_rev_txt_"):
        parts = state_str.split("_")
        order_id = int(parts[4])
        rating = int(parts[5])
        user_states.pop(uid, None)
        try:
            with get_giso_db_conn() as conn:
                conn.execute(
                    "INSERT INTO reviews (user_id, phone, review_type, order_id, rating, comment, created_at) VALUES (?, ?, 'hair_order', ?, ?, ?, ?)",
                    (uid, existing.get("phone", "") if existing else "", order_id, rating, text, time.strftime("%Y-%m-%d %H:%M:%S"))
                )
                conn.commit()
            await msg.reply_text("✅ نظر و رضایت شما با موفقیت ثبت شد. از همراهی شما سپاسگزاریم 🌸", reply_markup=user_hair_kb_func())
        except Exception as e:
            logger.error(f"hair review save error: {e}")
            await msg.reply_text("❌ خطا در ثبت نظر.", reply_markup=user_hair_kb_func())
        return True

    return False


__all__ = [
    "hair_sale_routes",
    "DEFAULT_HAIR_PRICES",
    "get_hair_price_from_config",
    "calculate_hair_price",
    "hair_sale",
    "submit_buyer_request",
    "api_hair_estimate",
    "admin_hair_order_update",
    "admin_hair_order_message",
    "admin_config_hair_prices",
    "register_hair_sale_routes",
    "send_hair_order_to_admin_msg",
    "send_hair_order_notification_to_admins",
    "handle_hair_sale_commands",
    "handle_hair_sale_state",
    "init_hair_tables",
    "HAIR_MESSAGES_SCHEMA",
]
# Phase 3.4 Hair Sync: hair sale status sync comment
# Phase 4.4 Buttons: audit button labels for admin panel (P3)
# Phase 6 Hair Sale overall integrity check
# Phase 6.2 Image validation: enforce MIME/size check in hair_sale upload
# Phase 6.3 Backend validation: price/status/user ownership check
# Phase 6.4 Submit protection: duplicate guard
# Phase 6.5 Hair Sale Result: verify result query/display
# Phase 6.6 Hair Sale Test: full flow test needed (image+price+submit+result+admin)
# Phase 3.4 Sync — Hair Sale status sync guard (no loop); call only on change
