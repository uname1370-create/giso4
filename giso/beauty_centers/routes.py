# -*- coding: utf-8 -*-
"""Public, owner and contact routes for Beauty Centers."""
from pathlib import Path
import threading
import time

from flask import abort, flash, redirect, render_template, request, send_file, session, url_for
from flask_login import current_user, login_required

from giso.beauty_centers import beauty_centers_bp
from giso.beauty_centers.services import (
    CENTER_CATEGORIES, CENTER_TYPES, CATEGORY_CENTER_TYPES, CATEGORY_SERVICES,
    DISCLAIMER, PRICE_LEVELS, SERVICES, STATUS_FA, close_conversation, conversation_for_party,
    conversation_messages, create_center, get_center, get_center_by_slug, get_or_create_conversation,
    get_owner_center, increment_view, list_public_centers, owner_conversations, owner_conversation_unread_count, recommended_centers,
    reveal_contact, save_center_image, send_conversation_message, set_owner_active, update_owner_center,
    center_feedback_summary, submit_center_feedback, purchase_center_promotion,
    center_promotion_availability, process_center_expiry_notifications, renew_center_listing,
)
from giso.beauty_centers.pricing.services import get_center_services, get_working_hours
from giso.config import Config
from giso.base import get_giso_db_conn
from giso.money import format_toman, to_persian_digits


_EXPIRY_CHECK_LOCK = threading.Lock()
_EXPIRY_CHECK_LAST = 0.0


def _run_expiry_checks_throttled():
    """حداکثر یک اجرای بررسی انقضا در هر worker طی ده دقیقه."""
    global _EXPIRY_CHECK_LAST
    now = time.monotonic()
    if now - _EXPIRY_CHECK_LAST < 600:
        return
    with _EXPIRY_CHECK_LOCK:
        now = time.monotonic()
        if now - _EXPIRY_CHECK_LAST < 600:
            return
        process_center_expiry_notifications()
        _EXPIRY_CHECK_LAST = now


def _user_id() -> int:
    return int(getattr(current_user, "id", 0) or 0) if getattr(current_user, "is_authenticated", False) else 0


def _is_staff() -> bool:
    if not getattr(current_user, "is_authenticated", False):
        return False
    try:
        from giso.panel_user.permissions import is_admin_user
        return is_admin_user(getattr(current_user, "phone", "") or "")
    except Exception:
        return False


BEAUTY_WEEKDAYS = ["شنبه", "یکشنبه", "دوشنبه", "سه‌شنبه", "چهارشنبه", "پنجشنبه", "جمعه"]


def _service_price_label(service: dict) -> str:
    """برچسب قیمت خدمت؛ مبلغ اعلامی مرکز است و گیسو آن را تعیین یا تضمین نمی‌کند."""
    price_min = int(service.get("price_min") or 0)
    price_max = int(service.get("price_max") or 0)
    if price_min and price_max > price_min:
        return f"از {format_toman(price_min)} تا {format_toman(price_max)}"
    if price_max:
        return format_toman(price_max)
    if price_min:
        return format_toman(price_min)
    return "قیمت پس از بررسی شرایط خدمت"


def _service_duration_label(service: dict) -> str:
    minutes = int(service.get("duration_minutes") or 0)
    if minutes <= 0:
        return "مدت اعلام نشده"
    hours, rest = divmod(minutes, 60)
    parts = []
    if hours:
        parts.append(f"{to_persian_digits(hours)} ساعت")
    if rest:
        parts.append(f"{to_persian_digits(rest)} دقیقه")
    return " و ".join(parts)


def _center_services_for_display(center_id: int) -> list:
    """خدمات ثبت‌شده مرکز همراه با برچسب قیمت و مدت، آمادهٔ نمایش در قالب."""
    rows = []
    for record in get_center_services(center_id):
        service = dict(record)
        service["price_label"] = _service_price_label(service)
        service["duration_label"] = _service_duration_label(service)
        rows.append(service)
    return rows


def _center_hours_for_display(center_id: int, *, fill_defaults: bool = False) -> list:
    """ساعات کاری هفته؛ در پنل مالک همهٔ روزها و در صفحه عمومی فقط روزهای ثبت‌شده."""
    saved = {int(row.get("day_of_week") or 0): row for row in get_working_hours(center_id)}
    rows = []
    for day, day_label in enumerate(BEAUTY_WEEKDAYS):
        record = saved.get(day) or {}
        is_saved = bool(record)
        if not is_saved and not fill_defaults:
            continue
        is_closed = bool(int(record.get("is_closed") or 0)) if is_saved else False
        open_time = str(record.get("open_time") or "") if is_saved else "09:00"
        close_time = str(record.get("close_time") or "") if is_saved else "20:00"
        if is_closed:
            time_label = "تعطیل"
        elif open_time and close_time:
            time_label = f"{to_persian_digits(open_time)} تا {to_persian_digits(close_time)}"
        else:
            time_label = "ساعت اعلام نشده"
        rows.append({
            "day_of_week": day, "day_label": day_label, "is_saved": is_saved,
            "is_closed": is_closed, "open_time": open_time, "close_time": close_time,
            "slot_minutes": int(record.get("slot_minutes") or 30) if is_saved else 30,
            "time_label": time_label,
        })
    return rows


def _owner_panel_context() -> dict:
    from giso.panel_user.permissions import USER_MODULES, current_user_role
    if current_user_role() in ("admin", "super"):
        return {"redirect_admin": True}
    from giso.panel.modules.notifications import list_user_notifications, user_unread_count
    from giso.wallet import get_wallet_balances
    phone = getattr(current_user, "phone", "") or ""
    menu = list(USER_MODULES) + [("beauty_center", "مرکز زیبایی من", "🏥")]
    return {
        "user": current_user, "menu": menu, "user_module_groups": {},
        "current_module": "beauty_center", "current_module_label": "مرکز زیبایی من",
        "current_module_icon": "🏥", "user_notifications": list_user_notifications(phone, limit=5),
        "user_notification_unread": user_unread_count(phone),
        "header_wallet_usable": get_wallet_balances(_user_id()).get("usable", 0),
        "header_wallet_cash": get_wallet_balances(_user_id()).get("cash", 0),
        "header_wallet_spend": get_wallet_balances(_user_id()).get("spend", 0),
    }


def _remove_saved_image(relative_path: str):
    try:
        path = (Path(Config.GISO_DIR) / "static" / str(relative_path or "")).resolve()
        root = (Path(Config.GISO_DIR) / "static" / "uploads" / "beauty_centers").resolve()
        if root in path.parents and path.is_file():
            path.unlink()
    except Exception:
        pass


def _owner_profile_defaults() -> dict:
    from giso.user_profile_service import safe_form_defaults
    profile = safe_form_defaults(current_user)
    return {
        "city": profile.get("city") or "مشهد",
        "region": profile.get("region") or "",
        "business_phone": profile.get("phone") or "",
        "contact_time": profile.get("contact_time") or "",
    }


@beauty_centers_bp.route("/beauty-centers")
def list_centers():
    try: _run_expiry_checks_throttled()
    except Exception: pass
    query = (request.args.get("q") or "").strip()
    city = (request.args.get("city") or "").strip()
    category = (request.args.get("category") or "").strip()
    center_type = (request.args.get("type") or "").strip()
    service = (request.args.get("service") or "").strip()
    price_level = (request.args.get("price_level") or "").strip()
    analysis_id = request.args.get("analysis_id", type=int) or 0
    centers = list_public_centers(query=query, city=city, category=category,
                                  center_type=center_type, service=service, price_level=price_level)
    featured = [row for row in centers if row.get("is_featured")][:6]
    related = []
    if analysis_id and _user_id():
        related = recommended_centers(analysis_id, _user_id(), city=getattr(current_user, "city", "") or city)
    cities = ["مشهد"]
    with get_giso_db_conn() as conn:
        beauty_stats={
          "centers":conn.execute("SELECT COUNT(*) FROM beauty_centers WHERE status='published' AND is_active=1").fetchone()[0],
          "views":conn.execute("SELECT COALESCE(SUM(views_count),0) FROM beauty_centers WHERE status='published'").fetchone()[0],
          "hair":conn.execute("SELECT COUNT(*) FROM analyses WHERE type='hair'").fetchone()[0],
          "skin":conn.execute("SELECT COUNT(*) FROM analyses WHERE type='skin'").fetchone()[0],
        }
    return render_template(
        "beauty_centers/list.html", centers=centers, featured=featured, related=related,
        query=query, city=city, category=category, center_type=center_type, service=service,
        price_level=price_level, analysis_id=analysis_id, price_levels=PRICE_LEVELS,
        cities=cities, center_categories=CENTER_CATEGORIES, center_types=CENTER_TYPES,
        category_center_types=CATEGORY_CENTER_TYPES, category_services=CATEGORY_SERVICES,
services=SERVICES, disclaimer=DISCLAIMER, beauty_stats=beauty_stats,
        # SEO: جست‌وجو (q) ایندکس نشود؛ فیلترهای معنادار (city/category/...) و
        # لیست پایه indexable می‌مانند (قرارداد stage14).
        noindex=bool(query),
    )


@beauty_centers_bp.route("/beauty-centers/<path:slug>")
def center_detail(slug):
    center = get_center_by_slug(slug)
    if not center:
        abort(404)
    is_owner = bool(_user_id() and int(center.get("owner_user_id") or 0) == _user_id())
    is_staff = _is_staff()
    if center.get("status") != "published" or not center.get("is_active"):
        if not (is_owner or is_staff):
            abort(404)
    if center.get("status") == "published" and not (is_owner or is_staff):
        increment_view(center["id"])
        center["views_count"] = int(center.get("views_count") or 0) + 1
    revealed = is_owner or is_staff or int(center["id"]) in set(session.get("revealed_beauty_centers") or [])
    with get_giso_db_conn() as conn:
        gallery_images = [dict(row) for row in conn.execute(
            "SELECT * FROM beauty_center_images WHERE center_id=? ORDER BY sort_order,id", (int(center["id"]),)
        ).fetchall()]
    return render_template(
        "beauty_centers/detail.html", center=center, gallery_images=gallery_images, feedback=center_feedback_summary(center['id']), center_categories=CENTER_CATEGORIES,
        center_types=CENTER_TYPES, services=SERVICES, disclaimer=DISCLAIMER, contact_revealed=revealed,
        center_services=_center_services_for_display(center["id"]),
        beauty_hours=_center_hours_for_display(center["id"]),
    )


@beauty_centers_bp.route("/beauty-centers/<int:center_id>/contact", methods=["POST"])
@login_required
def center_contact(center_id):
    ok, message = reveal_contact(center_id, _user_id(), price_inquiry=request.form.get("intent") == "price_inquiry")
    center = get_center(center_id)
    if not center:
        abort(404)
    if ok:
        revealed = {int(value) for value in (session.get("revealed_beauty_centers") or []) if str(value).isdigit()}
        revealed.add(int(center_id))
        session["revealed_beauty_centers"] = sorted(revealed)[-30:]
        session.modified = True
    else:
        flash(message, "warning")
    return redirect(url_for("beauty_centers.center_detail", slug=center["slug"]) + "#center-contact")


@beauty_centers_bp.route("/beauty-centers/register", methods=["GET", "POST"])
@login_required
def register_center():
    try:
        from giso_admin import get_giso_config
        registration_enabled=str(get_giso_config('beauty_registration_enabled','1') or '1')=='1'
        registration_intro=str(get_giso_config('beauty_registration_intro','') or '').strip()
        terms_text=str(get_giso_config('beauty_terms_text',DISCLAIMER) or DISCLAIMER).strip()
    except Exception:
        registration_enabled=True;registration_intro='';terms_text=DISCLAIMER
    if not registration_enabled:
        flash("ثبت مرکز زیبایی فعلاً غیرفعال است.", "warning")
        return redirect(url_for("beauty_centers.list_centers"))
    existing = get_owner_center(_user_id())
    if existing:
        flash('مرکز شما قبلاً ثبت شده است')
        return redirect(url_for("beauty_centers.owner_dashboard"))
    defaults = _owner_profile_defaults()
    if request.method == "POST":
        image_path, image_error = save_center_image(request.files.get("image"))
        if image_error:
            flash(image_error, "danger")
        else:
            ok, message, _center = create_center(
                _user_id(),
                {
                    "name": request.form.get("name"), "category": request.form.get("category"),
                    "center_type": request.form.get("center_type"),
                    "price_level": request.form.get("price_level"), "starting_price": request.form.get("starting_price"),
                    "city": "مشهد", "region": request.form.get("region"),
                    "address_summary": request.form.get("address_summary"),
                    "business_phone": request.form.get("business_phone"),
                    "contact_time": request.form.get("contact_time"),
                    "description": request.form.get("description"),
                    "services": request.form.getlist("services"),
                    "terms_accepted": request.form.get("terms_accepted") == "1",
                }, image_path,
            )
            flash(message, "success" if ok else "danger")
            if ok:
                return redirect(url_for("beauty_centers.owner_dashboard"))
            _remove_saved_image(image_path)
    return render_template(
        "beauty_centers/register.html", defaults=defaults,
        center_categories=CENTER_CATEGORIES, center_types=CENTER_TYPES,
        category_center_types=CATEGORY_CENTER_TYPES, category_services=CATEGORY_SERVICES,
        price_levels=PRICE_LEVELS, services=SERVICES, disclaimer=DISCLAIMER,
        registration_intro=registration_intro, terms_text=terms_text,
    )


@beauty_centers_bp.route("/dashboard/beauty-center")
@login_required
def owner_dashboard():
    center = get_owner_center(_user_id())
    if not center:
        return redirect(url_for("beauty_centers.register_center"))
    tab = (request.args.get("tab") or "status").strip()
    if tab not in ("status", "edit", "services", "messages", "promotion", "reservations"):
        tab = "status"
    panel_context = _owner_panel_context()
    if panel_context.pop("redirect_admin", False):
        return redirect(url_for("panel.dashboard"))
    conversations = owner_conversations(_user_id()) if tab == "messages" else []
    from giso.beauty_centers.reservations.services import get_center_reservations
    center_reservations = get_center_reservations(center["id"]) if tab == "reservations" else []
    with get_giso_db_conn() as conn:
        gallery_images = [dict(row) for row in conn.execute(
            "SELECT * FROM beauty_center_images WHERE center_id=? ORDER BY sort_order,id", (int(center["id"]),)
        ).fetchall()]
    profile_checks = [
        bool(center.get("name")), bool(center.get("category")), bool(center.get("center_type")),
        bool(center.get("city")), bool(center.get("business_phone")), bool(center.get("description")),
        bool(center.get("image_path")), bool(center.get("services")), bool(center.get("contact_time")),
        bool(center.get("address_summary")),
    ]
    profile_completion = round((sum(profile_checks) / len(profile_checks)) * 100)
    try:
        from giso_admin import get_giso_config
        promotion_prices={"bump":int(get_giso_config("beauty_bump_price","25000") or 25000),"featured":int(get_giso_config("beauty_featured_price","120000") or 120000),"discount":int(get_giso_config("beauty_discount_price","60000") or 60000),"renew":int(get_giso_config("beauty_renew_price","50000") or 50000)}
        promotion_enabled=str(get_giso_config("beauty_promotions_enabled","1") or "1")=="1"
        promotion_package_enabled={key:str(get_giso_config(f"beauty_{key}_enabled","1") or "1")=="1" for key in ("bump","featured","discount","renew")}
    except Exception:
        promotion_prices={"bump":25000,"featured":120000,"discount":60000,"renew":50000};promotion_enabled=True;promotion_package_enabled={"bump":True,"featured":True,"discount":True,"renew":True}
    if tab == "promotion" and not promotion_enabled:
        flash("بخش ارتقای آگهی فعلاً غیرفعال است.", "warning")
        return redirect(url_for("beauty_centers.owner_dashboard", tab="status"))
    import uuid
    purchase_nonces={key:uuid.uuid4().hex for key in ("bump","featured","discount","renew")}
    with get_giso_db_conn() as conn:
        promotion_history=[dict(r) for r in conn.execute("SELECT * FROM beauty_center_promotions WHERE center_id=? ORDER BY id DESC LIMIT 20",(int(center["id"]),)).fetchall()]
    return render_template(
        "beauty_centers/owner_dashboard.html", center=center, beauty_tab=tab,
        beauty_conversations=conversations, beauty_unread=owner_conversation_unread_count(_user_id()), profile_completion=profile_completion,
        gallery_images=gallery_images, promotion_prices=promotion_prices,
        center_services=_center_services_for_display(center["id"]),
        beauty_hours=_center_hours_for_display(center["id"], fill_defaults=True),
        promotion_enabled=promotion_enabled, promotion_package_enabled=promotion_package_enabled,
        purchase_nonces=purchase_nonces, promotion_history=promotion_history,
        promotion_availability=center_promotion_availability(center),
        owner_phone=(getattr(current_user, "phone", "") or ""),
        center_categories=CENTER_CATEGORIES, center_types=CENTER_TYPES,
        category_center_types=CATEGORY_CENTER_TYPES, category_services=CATEGORY_SERVICES,
        price_levels=PRICE_LEVELS, services=SERVICES, status_fa=STATUS_FA,
        disclaimer=DISCLAIMER, center_reservations=center_reservations, **panel_context,
    )


@beauty_centers_bp.route("/dashboard/beauty-center/update", methods=["POST"])
@login_required
def owner_update():
    center = get_owner_center(_user_id())
    if not center:
        abort(404)
    image_path = ""
    if request.files.get("image") and request.files["image"].filename:
        image_path, image_error = save_center_image(request.files["image"])
        if image_error:
            flash(image_error, "danger")
            return redirect(url_for("beauty_centers.owner_dashboard", tab="edit"))
    ok, message, _updated = update_owner_center(
        center["id"], _user_id(),
        {
            "name": request.form.get("name"), "category": request.form.get("category"),
            "center_type": request.form.get("center_type"),
            "price_level": request.form.get("price_level"), "starting_price": request.form.get("starting_price"),
            "city": "مشهد", "region": request.form.get("region"),
            "address_summary": request.form.get("address_summary"),
            "business_phone": request.form.get("business_phone"),
            "salon_phone": request.form.get("salon_phone"),
            "display_phone_choice": request.form.get("display_phone_choice"),
            "contact_time": request.form.get("contact_time"), "description": request.form.get("description"),
            "services": request.form.getlist("services"),
        }, image_path=image_path,
    )
    if not ok and image_path:
        _remove_saved_image(image_path)
    elif ok and image_path and center.get("image_path") and center.get("image_path") != image_path:
        _remove_saved_image(center.get("image_path"))
    flash(message, "success" if ok else "danger")
    return redirect(url_for("beauty_centers.owner_dashboard", tab="status" if ok else "edit"))


@beauty_centers_bp.route("/dashboard/beauty-center/visibility", methods=["POST"])
@login_required
def owner_visibility():
    center = get_owner_center(_user_id())
    if not center:
        abort(404)
    active = request.form.get("action") == "resume"
    ok, message = set_owner_active(center["id"], _user_id(), active)
    flash(message, "success" if ok else "warning")
    return redirect(url_for("beauty_centers.owner_dashboard"))


@beauty_centers_bp.route("/beauty-centers/<path:slug>/chat")
@login_required
def center_chat(slug):
    center = get_center_by_slug(slug)
    if not center:
        abort(404)
    owner = int(center.get("owner_user_id") or 0) == _user_id()
    conversation_id = request.args.get("conversation_id", type=int) or 0
    if conversation_id:
        conversation, linked_center = conversation_for_party(conversation_id, _user_id())
        if not conversation or int(conversation.get("center_id") or 0) != int(center["id"]):
            abort(404)
        center = linked_center or center
    elif owner:
        return redirect(url_for("beauty_centers.owner_dashboard", tab="messages"))
    else:
        if center.get("status") != "published" or not center.get("is_active"):
            abort(404)
        ok, message, conversation = get_or_create_conversation(center["id"], _user_id())
        if not ok:
            flash(message, "warning"); return redirect(url_for("beauty_centers.center_detail", slug=slug))
    if not conversation:
        abort(404)
    messages = conversation_messages(conversation["id"], _user_id())
    return render_template("beauty_centers/chat.html", center=center, conversation=conversation,
                           messages=messages, is_owner=owner, disclaimer=DISCLAIMER)


@beauty_centers_bp.route("/beauty-centers/chat/<int:conversation_id>/message", methods=["POST"])
@login_required
def center_chat_message(conversation_id):
    conversation, center = conversation_for_party(conversation_id, _user_id())
    if not conversation:
        abort(403)
    ok, message, _message_id = send_conversation_message(conversation_id, _user_id(), request.form.get("message_text"))
    flash(message, "success" if ok else "warning")
    return redirect(url_for("beauty_centers.center_chat", slug=center["slug"], conversation_id=conversation_id))


@beauty_centers_bp.route("/beauty-centers/chat/<int:conversation_id>/close", methods=["POST"])
@login_required
def center_chat_close(conversation_id):
    conversation, center = conversation_for_party(conversation_id, _user_id())
    if not conversation: abort(403)
    ok, message = close_conversation(conversation_id, _user_id()); flash(message, "success" if ok else "warning")
    return redirect(url_for("beauty_centers.owner_dashboard", tab="messages") if int(center["owner_user_id"])==_user_id() else url_for("beauty_centers.center_chat", slug=center["slug"], conversation_id=conversation_id))


@beauty_centers_bp.route("/dashboard/beauty-center/renew", methods=["POST"])
@login_required
def owner_renew():
    ok,message=renew_center_listing(_user_id(),request.form.get('purchase_nonce') or '');flash(message,"success" if ok else "warning")
    return redirect(url_for('beauty_centers.owner_dashboard'))


@beauty_centers_bp.route("/dashboard/beauty-center/discount", methods=["POST"])
@login_required
def owner_discount():
    center=get_owner_center(_user_id())
    title=(request.form.get('title') or '').strip()[:100];value=(request.form.get('discount_value') or '').strip()[:50];days=max(1,min(30,request.form.get('days',type=int) or 7))
    if not center or not title or not value:flash("عنوان و مقدار تخفیف را کامل کنید.","warning")
    else:
        with get_giso_db_conn() as conn:
            conn.execute("INSERT INTO beauty_center_discounts(center_id,title,description,discount_value,expires_at,status,created_at) VALUES (?,?,?,?,datetime('now','localtime',?),'pending',datetime('now','localtime'))",(center['id'],title,(request.form.get('description') or '')[:300],value,f'+{days} days'));conn.commit()
        flash("تخفیف برای بررسی مدیریت ثبت شد.","success")
    return redirect(url_for('beauty_centers.owner_dashboard',tab='promotion'))


@beauty_centers_bp.route("/dashboard/beauty-center/promote", methods=["POST"])
@login_required
def owner_promote():
    ok,message=purchase_center_promotion(_user_id(),(request.form.get('package_key') or '').strip(),request.form.get('purchase_nonce') or '')
    flash(message,"success" if ok else "warning")
    return redirect(url_for('beauty_centers.owner_dashboard',tab='promotion'))


@beauty_centers_bp.route("/dashboard/beauty-center/gallery", methods=["POST"])
@login_required
def owner_gallery_upload():
    center = get_owner_center(_user_id())
    if not center:
        abort(404)
    with get_giso_db_conn() as conn:
        count = int(conn.execute("SELECT COUNT(*) FROM beauty_center_images WHERE center_id=?", (int(center["id"]),)).fetchone()[0] or 0)
    total = count + (1 if center.get("image_path") else 0)
    if total >= 3:
        flash("حداکثر سه تصویر برای مرکز قابل ثبت است.", "warning")
        return redirect(url_for("beauty_centers.owner_dashboard", tab="edit"))
    image_path, image_error = save_center_image(request.files.get("center_image") or request.files.get("gallery_image"))
    if image_error:
        flash(image_error, "danger")
    else:
        with get_giso_db_conn() as conn:
            if not center.get("image_path"):
                conn.execute("UPDATE beauty_centers SET image_path=?,updated_at=datetime('now','localtime') WHERE id=? AND owner_user_id=?", (image_path, int(center["id"]), _user_id()))
            else:
                conn.execute("INSERT INTO beauty_center_images(center_id,image_path,sort_order,created_at) VALUES (?,?,?,datetime('now','localtime'))", (int(center["id"]), image_path, count + 1))
            conn.commit()
        flash("تصویر به اسلایدر مرکز اضافه شد.", "success")
    return redirect(url_for("beauty_centers.owner_dashboard", tab="edit"))


@beauty_centers_bp.route("/dashboard/beauty-center/image-main/delete", methods=["POST"])
@login_required
def owner_main_image_delete():
    center = get_owner_center(_user_id())
    if not center:
        abort(404)
    old_path = str(center.get("image_path") or "")
    if not old_path:
        flash("تصویر اولی برای حذف وجود ندارد.", "warning")
        return redirect(url_for("beauty_centers.owner_dashboard", tab="edit"))
    with get_giso_db_conn() as conn:
        conn.execute("BEGIN IMMEDIATE")
        replacement = conn.execute("SELECT id,image_path FROM beauty_center_images WHERE center_id=? ORDER BY sort_order,id LIMIT 1", (int(center["id"]),)).fetchone()
        next_path = str(replacement["image_path"] or "") if replacement else ""
        conn.execute("UPDATE beauty_centers SET image_path=?,updated_at=datetime('now','localtime') WHERE id=? AND owner_user_id=?", (next_path, int(center["id"]), _user_id()))
        if replacement:
            conn.execute("DELETE FROM beauty_center_images WHERE id=?", (int(replacement["id"]),))
        conn.commit()
    _remove_saved_image(old_path)
    flash("تصویر حذف شد؛ تصویر بعدی به ابتدای اسلایدر منتقل شد." if replacement else "تصویر حذف شد.", "success")
    return redirect(url_for("beauty_centers.owner_dashboard", tab="edit"))


@beauty_centers_bp.route("/dashboard/beauty-center/gallery/<int:image_id>/delete", methods=["POST"])
@login_required
def owner_gallery_delete(image_id):
    center = get_owner_center(_user_id())
    if not center:
        abort(404)
    with get_giso_db_conn() as conn:
        row = conn.execute("SELECT * FROM beauty_center_images WHERE id=? AND center_id=?", (int(image_id), int(center["id"]))).fetchone()
        if not row:
            abort(404)
        conn.execute("DELETE FROM beauty_center_images WHERE id=?", (int(image_id),)); conn.commit()
    _remove_saved_image(row["image_path"])
    flash("تصویر حذف شد.", "success")
    return redirect(url_for("beauty_centers.owner_dashboard", tab="edit"))


@beauty_centers_bp.route("/beauty-centers/gallery/<int:image_id>")
def gallery_media(image_id):
    with get_giso_db_conn() as conn:
        row = conn.execute("SELECT i.*,b.owner_user_id,b.status,b.is_active FROM beauty_center_images i JOIN beauty_centers b ON b.id=i.center_id WHERE i.id=?", (int(image_id),)).fetchone()
    if not row:
        abort(404)
    owner = _user_id() and int(row["owner_user_id"] or 0) == _user_id()
    if (row["status"] != "published" or not row["is_active"]) and not (owner or _is_staff()):
        abort(404)
    static_root = (Path(Config.GISO_DIR) / "static").resolve()
    raw = str(row["image_path"] or "").replace("\\", "/").lstrip("/")
    for prefix in ("giso/static/", "static/"):
        if raw.startswith(prefix): raw = raw[len(prefix):]
    candidate = (static_root / raw).resolve()
    if static_root not in candidate.parents or not candidate.is_file(): abort(404)
    response = send_file(candidate, conditional=True, max_age=3600)
    response.headers["X-Content-Type-Options"] = "nosniff"
    return response


@beauty_centers_bp.route("/beauty-centers/chat/<int:conversation_id>/feedback", methods=["POST"])
@login_required
def center_chat_feedback(conversation_id):
    ok,message=submit_center_feedback(conversation_id,_user_id(),request.form)
    flash(message,"success" if ok else "warning")
    conv,center=conversation_for_party(conversation_id,_user_id())
    return redirect(url_for("beauty_centers.center_chat",slug=center['slug'],conversation_id=conversation_id) if center else url_for('panel_user.center_chats'))


@beauty_centers_bp.route("/beauty-centers/media/<int:center_id>")
def center_media(center_id):
    center = get_center(center_id)
    if not center:
        abort(404)
    owner = _user_id() and int(center.get("owner_user_id") or 0) == _user_id()
    if center.get("status") != "published" and not (owner or _is_staff()):
        abort(404)
    static_root = (Path(Config.GISO_DIR) / "static").resolve()
    raw = str(center.get("image_path") or "").replace("\\", "/").lstrip("/")
    for prefix in ("giso/static/", "static/"):
        if raw.startswith(prefix):
            raw = raw[len(prefix):]
    candidate = (static_root / raw).resolve()
    if static_root not in candidate.parents or not candidate.is_file():
        abort(404)
    response = send_file(candidate, conditional=True, max_age=3600)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Content-Security-Policy"] = "default-src 'none'; sandbox"
    return response
