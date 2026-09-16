# -*- coding: utf-8 -*-
"""
giso/panel/routes.py — ثبت routeهای ماژولار پنل ادمین (فاز 4)

هر ماژول یک تابع view دارد که:
  - گارد دسترسی (verification + permission) را اجرا می‌کند
  - داده را از توابع موجود (hair_sale/referrals/...) جمع می‌کند
  - قالب panel/templates/modules/<module>.html را رندر می‌کند

فرم‌ها به route های POST قدیمی submit می‌شوند (action های قبلی حفظ شده).
"""
import logging
from functools import wraps

from flask import render_template, redirect, url_for, request, flash, current_app, abort, send_file

from giso.panel import panel_bp
from giso.panel.permissions import (
    current_role_and_perms, module_allowed, visible_modules, MODULES_META,
    REGULAR_ADMIN_NAV, SPECIAL_ADMIN_NAV, SPECIAL_ADMIN_MODULES,
)

logger = logging.getLogger("giso_panel_routes")


@panel_bp.context_processor
def _inject_role_flags():
    """role flags همیشه در layout پنل در دسترس باشند (برای تم شرطی ادمین اختصاصی)."""
    try:
        role, _perms, _bid = current_role_and_perms()
        return {"is_super": role == "super", "is_special": role == "special", "role": role}
    except Exception:
        return {"is_super": False, "is_special": False, "role": "admin"}


@panel_bp.before_request
def _panel_csrf_guard():
    """CSRF سراسری برای همهٔ POSTهای پنل ادمین (مرحلهٔ ۱ se.md / BUG-001).

    توکن از فرم (csrf_token) یا هدر X-GISO-CSRF/X-CSRF-Token پذیرفته می‌شود
    (giso/security.validate_csrf). قالب‌های پنل توکن را embed می‌کنند.
    """
    if request.method != "POST":
        return None
    from giso.security import validate_csrf
    if not validate_csrf():
        abort(403)
    return None


def _guard():
    """گارد دسترسی پنل: ورود + verification + بازگشت در صورت عدم دسترسی."""
    try:
        from giso.app import _check_giso_admin_access
        r = _check_giso_admin_access()
        if r:
            return r
    except Exception as e:
        logger.exception("panel guard failed: %s", e)
        try:
            from giso.security import audit_event
            audit_event("panel_guard_exception", "failed", target=request.path, details=repr(e))
        except Exception as audit_exc:
            logger.exception("panel guard audit failed: %s", audit_exc)
        flash("در بررسی دسترسی پنل خطای داخلی رخ داد. لطفاً دوباره تلاش کنید.", "danger")
        return redirect(url_for("login"))
    return None


def _audit_denied(action: str, target, role: str = ""):
    """ثبت تلاش دسترسی رد‌شده در audit log (بدون شکستن جریان کاربر)."""
    try:
        from giso.security import audit_event
        audit_event(action, "denied", target=str(target),
                    details=f"role={role} path={request.path}")
    except Exception as exc:
        logger.debug("audit denied failed: %s", exc)


def require_super(view):
    """گارد سطح-route برای مسیرهای حساس (رفع R5 — defense in depth).

    این دکوراتور جایگزین `_require_super()` داخل handlerها نیست؛ لایه دوم است.
    دلیل وجودش: `module_allowed()` فقط داخل `_render()` اجرا می‌شود و
    `_render()` در مسیرهای POST صدا زده نمی‌شود، بنابراین بدون این لایه،
    امنیت POSTها صرفاً به یک «قرارداد نانوشته» وابسته می‌ماند.
    """
    @wraps(view)
    def _wrapped(*args, **kwargs):
        if r := _guard():
            return r
        role, _perms, _bid = current_role_and_perms()
        if role != "super":
            _audit_denied(f"route:{view.__name__}", request.path, role)
            flash("⛔ این عملیات فقط برای سوپرادمین مجاز است.", "warning")
            return redirect(url_for("panel.dashboard"))
        return view(*args, **kwargs)
    return _wrapped


def require_manage(view):
    """گارد سطح‌route برای ماژول‌های کاربران/مالی همه.

    فقط سوپرادمین. ادمین اختصاصی و ادمین عادی هر دو رد می‌شوند
    (مالی کیف همه / مدیریت کاربران خارج از نقش special است).
    """
    @wraps(view)
    def _wrapped(*args, **kwargs):
        if r := _guard():
            return r
        role, _perms, _bid = current_role_and_perms()
        if role != "super":
            _audit_denied(f"route:{view.__name__}", request.path, role)
            flash("⛔ این بخش فقط برای مدیر ارشد مجاز است.", "warning")
            return redirect(url_for("panel.dashboard"))
        return view(*args, **kwargs)
    return _wrapped


def require_special(view):
    """گارد مسیرهای اختصاصی (آقا رضا / راهنما / گزارش شخصی). سوپر و ادمین عادی رد."""
    @wraps(view)
    def _wrapped(*args, **kwargs):
        deny, _role = _guard_special()
        if deny is not None:
            return deny
        return view(*args, **kwargs)
    return _wrapped


def _render(module, template, **ctx):
    """رندر قالب ماژول با context مشترک (role/perms/menu)."""
    role, perms, bale_id = current_role_and_perms()
    if not module_allowed(module, role, perms):
        flash("⛔ شما به این بخش دسترسی ندارید.", "warning")
        return redirect(url_for("panel.dashboard"))
    from flask_login import current_user
    label = dict((m, l) for m, l, _ in MODULES_META).get(module, module)
    if role == "special":
        label = dict((m, l) for m, l, _ in SPECIAL_ADMIN_NAV).get(module, label)
    elif role != "super":
        label = dict((m, l) for m, l, _ in REGULAR_ADMIN_NAV).get(module, label)
    ctx.update({
        "role": role,
        "perms": perms,
        "menu": visible_modules(role, perms, bale_id),
        "current_module": module,
        "current_module_label": label,
        "is_super": role == "super",
        "is_special": role == "special",
        "user": current_user,
    })
    # فاز جامع اعلان‌ها: شمارنده خوانده‌نشده برای badge سایدبار (سبک — COUNT ایندکس‌شده)
    try:
        from giso.panel.modules.notifications import unread_count
        ctx["notif_unread"] = unread_count(role)
    except Exception:
        ctx["notif_unread"] = 0
    tpl = template if "/" in template else f"modules/{template}"
    return render_template(tpl, **ctx)


# ─────────────────── ماژول‌ها ───────────────────
from giso.panel.modules import dashboard as _dash
from giso.panel.modules import users as _users
from giso.panel.modules import admins as _admins
from giso.panel.modules import products as _products
from giso.panel.modules import shop_orders as _shop
from giso.panel.modules import hair_sale as _hair
from giso.panel.modules import marketplace as _marketplace
from giso.beauty_centers import panel_admin as _beauty_centers
from giso.panel.modules import analyses as _analyses
from giso.panel.modules import reviews as _reviews
from giso.panel.modules import channel as _channel
from giso.panel.modules import ai as _ai
from giso.panel.modules import super_assistant as _sassist
from giso.panel.modules import ratelimit as _ratelimit
from giso.panel.modules import wallet as _wallet
from giso.panel.modules import settings as _settings
from giso.panel.modules import backup as _backup
from giso.panel.modules import reports as _reports
from giso.shop.panel import admin as _shop_admin
from giso.shop.panel import super as _shop_super
from giso.shop.routes import ensure_shop_template_paths


@panel_bp.route("/")
@panel_bp.route("/dashboard")
def dashboard():
    if r := _guard():
        return r
    role, _perms, _bid = current_role_and_perms()
    context = _dash.context() if role == "super" else _dash.work_context()
    if role == "special":
        queues = [
            item for item in (context.get("work_queues") or [])
            if item.get("module") in SPECIAL_ADMIN_MODULES
        ]
        context["work_queues"] = queues
        context["work_open_total"] = sum(int(item.get("count") or 0) for item in queues)
    return _render("dashboard", "dashboard.html", **context)


@panel_bp.route("/users")
@require_manage
def users():
    if r := _guard():
        return r
    return _render("users", "users.html", **_users.context())


@panel_bp.route("/users/special-security", methods=["POST"])
@require_super
def users_special_security():
    if r := _guard():
        return r
    return _users.handle_special_security()


@panel_bp.route("/users/<int:user_id>/ban", methods=["POST"])
@require_super
def user_ban(user_id):
    if r := _guard():
        return r
    return _users.handle_ban(user_id)


@panel_bp.route("/users/<int:user_id>/unban", methods=["POST"])
@require_super
def user_unban(user_id):
    if r := _guard():
        return r
    return _users.handle_unban(user_id)


@panel_bp.route("/users/<int:user_id>/show-password", methods=["POST"])
@require_super
def user_show_password(user_id):
    return _users.handle_show_password(user_id)


@panel_bp.route("/users/<int:user_id>/reset-password", methods=["POST"])
@require_super
def user_reset_password(user_id):
    return _users.handle_reset_password(user_id)


@panel_bp.route("/users/<int:user_id>/update", methods=["POST"])
@require_super
def user_update(user_id):
    if r := _guard():
        return r
    return _users.handle_update(user_id)


@panel_bp.route("/users/<int:user_id>/wallet", methods=["POST"])
@require_super
def user_wallet(user_id):
    return _users.handle_wallet(user_id)


@panel_bp.route("/users/<int:user_id>/delete", methods=["POST"])
@require_super
def user_delete(user_id):
    if r := _guard():
        return r
    return _users.handle_delete(user_id)


@panel_bp.route("/admins", methods=["GET", "POST"])
@require_super
def admins():
    # مسیر قدیمی /admin/admins با canonical متفاوت نگه داشته می‌شود.
    if request.method == "GET" and request.args.get("canonical") != "1":
        return redirect(url_for("panel.admins_canonical", bale_id=request.args.get("bale_id")))
    if r := _guard():
        return r
    if request.method == "POST":
        return _admins.handle_post()
    return _render("admins", "admins.html", **_admins.context())


@panel_bp.route("/admin-management")
@require_super
def admins_canonical():
    if r := _guard():
        return r
    return _render("admins", "admins.html", **_admins.context())


@panel_bp.route("/products")
def products():
    if r := _guard():
        return r
    role, _perms, _bid = current_role_and_perms()
    if role == "super":
        return _render("products", "products.html", **_products.context())
    return _render("products", "channel_products.html", **_products.channel_context())


@panel_bp.route("/account")
def account():
    if r := _guard():
        return r
    return _render("account", "account.html")


@panel_bp.route("/account/profile", methods=["POST"])
def account_profile():
    if r := _guard():
        return r
    role, perms, _bid = current_role_and_perms()
    if not module_allowed("account", role, perms):
        return redirect(url_for("panel.dashboard"))
    from flask_login import current_user
    from giso.models import db, User
    first_name = (request.form.get("first_name") or "").strip()[:60]
    last_name = (request.form.get("last_name") or "").strip()[:60]
    user = User.query.filter_by(phone=getattr(current_user, "phone", "")).first()
    if not user:
        flash("حساب پیدا نشد.", "danger")
        return redirect(url_for("panel.account"))
    user.first_name = first_name
    user.last_name = last_name
    user.name = (first_name + " " + last_name).strip() or user.name
    db.session.commit()
    flash("نام و نام خانوادگی ذخیره شد.", "success")
    return redirect(url_for("panel.account"))


@panel_bp.route("/account/password", methods=["POST"])
def account_password():
    if r := _guard():
        return r
    role, perms, _bid = current_role_and_perms()
    if not module_allowed("account", role, perms):
        return redirect(url_for("panel.dashboard"))
    from flask_login import current_user
    from werkzeug.security import check_password_hash, generate_password_hash
    from giso.models import db, User
    current_password = request.form.get("current_password", "") or ""
    new_password = request.form.get("new_password", "") or ""
    repeat_password = request.form.get("new_password2", "") or ""
    user = User.query.filter_by(phone=getattr(current_user, "phone", "")).first()
    from giso.security import validate_new_password as _vnp
    _ok, _msg = _vnp(new_password)
    if not user or not check_password_hash(user.password_hash, current_password):
        flash("رمز فعلی صحیح نیست.", "danger")
    elif not _ok:
        flash(_msg, "danger")
    elif new_password != repeat_password:
        flash("تکرار رمز جدید مطابقت ندارد.", "danger")
    else:
        user.password_hash = generate_password_hash(new_password, method="pbkdf2:sha256")
        db.session.commit()
        try:
            from giso.account_password_vault import remember_account_password
            remember_account_password(user.id, new_password)
        except Exception:
            pass
        flash("رمز عبور با موفقیت تغییر کرد.", "success")
    return redirect(url_for("panel.account"))


@panel_bp.route("/consults")
def consults():
    if r := _guard():
        return r
    from giso.panel.modules import consults as _consults
    return _render("consults", "consults.html", **_consults.context())


@panel_bp.route("/consults/reply/<int:req_id>", methods=["POST"])
def consult_reply(req_id):
    if r := _guard():
        return r
    from giso.panel.modules import consults as _consults
    return _consults.handle_reply(req_id)


@panel_bp.route("/consults/status/<int:req_id>", methods=["POST"])
def consult_status(req_id):
    if r := _guard():
        return r
    from giso.panel.modules import consults as _consults
    return _consults.handle_status(req_id)


@panel_bp.route("/consults/tickets/<int:ticket_id>/reply", methods=["POST"])
def support_ticket_reply(ticket_id):
    if r := _guard():
        return r
    from giso.panel.modules import consults as _consults
    return _consults.handle_support_reply(ticket_id)


@panel_bp.route("/consults/tickets/<int:ticket_id>/status", methods=["POST"])
def support_ticket_status(ticket_id):
    if r := _guard():
        return r
    from giso.panel.modules import consults as _consults
    return _consults.handle_support_status(ticket_id)


@panel_bp.route("/consults/delete/<int:req_id>", methods=["POST"])
@require_super
def consult_delete(req_id):
    if r := _guard():
        return r
    from giso.panel.modules import consults as _consults
    return _consults.handle_delete(req_id)


@panel_bp.route("/consults/thread/reply", methods=["POST"])
def consult_thread_reply():
    if r := _guard():
        return r
    from giso.panel.modules import consults as _consults
    return _consults.handle_thread_reply()


@panel_bp.route("/consults/thread/status", methods=["POST"])
def consult_thread_status():
    if r := _guard():
        return r
    from giso.panel.modules import consults as _consults
    return _consults.handle_thread_status()


@panel_bp.route("/shop-orders")
def shop_orders():
    if r := _guard():
        return r
    return _render("shop_orders", "shop_orders.html", **_shop.context())


@panel_bp.route("/shop-orders/<int:order_id>/delete", methods=["POST"])
@require_super
def shop_order_delete(order_id):
    if r := _guard():
        return r
    return _shop.handle_delete(order_id)


@panel_bp.route("/shop-orders/delete-status", methods=["POST"])
@require_super
def shop_orders_delete_status():
    if r := _guard():
        return r
    return _shop.handle_delete_by_status()


@panel_bp.route("/hair-orders")
def hair_sale():
    if r := _guard():
        return r
    return _render("hair_sale", "hair_sale.html", **_hair.context())


@panel_bp.route("/marketplace")
def marketplace():
    if r := _guard():
        return r
    return _render("marketplace", "marketplace.html", **_marketplace.context())


@panel_bp.route("/marketplace/listings/<int:listing_id>/action", methods=["POST"])
def marketplace_listing_action(listing_id):
    if r := _guard():
        return r
    if not module_allowed("marketplace", *current_role_and_perms()[:2]):
        return redirect(url_for("panel.dashboard"))
    return _marketplace.handle_listing_action(listing_id)


@panel_bp.route("/marketplace/reports/<int:report_id>/action", methods=["POST"])
def marketplace_report_action(report_id):
    if r := _guard():
        return r
    if not module_allowed("marketplace", *current_role_and_perms()[:2]):
        return redirect(url_for("panel.dashboard"))
    return _marketplace.handle_report_action(report_id)


@panel_bp.route("/marketplace/buyers/<int:profile_id>/action", methods=["POST"])
def marketplace_buyer_action(profile_id):
    if r := _guard():
        return r
    if not module_allowed("marketplace", *current_role_and_perms()[:2]):
        return redirect(url_for("panel.dashboard"))
    return _marketplace.handle_buyer_action(profile_id)


@panel_bp.route("/marketplace/settings", methods=["POST"])
@require_super
def marketplace_settings():
    if r := _guard():
        return r
    return _marketplace.handle_settings()


@panel_bp.route("/beauty-centers")
def beauty_centers():
    if r := _guard():
        return r
    role, perms, _bid = current_role_and_perms()
    if not module_allowed("beauty_centers", role, perms):
        return redirect(url_for("panel.dashboard"))
    tab = (request.args.get("tab") or "requests").strip()
    super_tabs = {"dashboard", "promotions", "feedback", "settings"}
    if tab in super_tabs and role != "super":
        tab = "requests"
    if tab not in ("dashboard", "requests", "published", "paused", "reports", "promotions", "feedback", "settings"):
        tab = "requests"
    return _render("beauty_centers", "beauty_centers/admin.html", **_beauty_centers.context(tab))


@panel_bp.route("/beauty-centers/settings", methods=["POST"])
@require_super
def beauty_center_settings():
    if r := _guard():
        return r
    return _beauty_centers.handle_settings()


@panel_bp.route("/beauty-centers/<int:center_id>/status", methods=["POST"])
def beauty_center_status(center_id):
    if r := _guard():
        return r
    role, perms, _bid = current_role_and_perms()
    if not module_allowed("beauty_centers", role, perms):
        return redirect(url_for("panel.dashboard"))
    from flask_login import current_user
    return _beauty_centers.handle_status(center_id, int(getattr(current_user, "id", 0) or 0))


@panel_bp.route("/beauty-centers/feature-selected", methods=["POST"])
@require_super
def beauty_center_feature_selected():
    if r := _guard(): return r
    return _beauty_centers.handle_feature_selected()


@panel_bp.route("/beauty-centers/<int:center_id>/feature", methods=["POST"])
@require_super
def beauty_center_feature(center_id):
    return _beauty_centers.handle_feature(center_id, request.form.get("featured") == "1")


@panel_bp.route("/beauty-centers/discount/<int:discount_id>/status", methods=["POST"])
@require_super
def beauty_center_discount_status(discount_id):
    if r := _guard(): return r
    return _beauty_centers.handle_discount(discount_id)


@panel_bp.route("/beauty-centers/feedback/<int:feedback_id>/status", methods=["POST"])
@require_super
def beauty_center_feedback_status(feedback_id):
    if r := _guard(): return r
    return _beauty_centers.handle_feedback(feedback_id)


@panel_bp.route("/analyses")
@require_super
def analyses():
    if r := _guard():
        return r
    return _render("analyses", "analyses.html", **_analyses.context())


@panel_bp.route("/reviews")
def reviews():
    if r := _guard():
        return r
    return _render("reviews", "reviews.html", **_reviews.context())


@panel_bp.route("/reviews/<int:review_id>/toggle", methods=["POST"])
def review_toggle(review_id):
    if r := _guard():
        return r
    return _reviews.handle_toggle(review_id)


@panel_bp.route("/reviews/<int:review_id>/delete", methods=["POST"])
@require_super
def review_delete(review_id):
    if r := _guard():
        return r
    return _reviews.handle_delete(review_id)


@panel_bp.route("/channel", methods=["GET", "POST"])
@require_super
def channel():
    if r := _guard():
        return r
    return _render("channel", "channel.html", **_channel.context())


@panel_bp.route("/ai")
@require_super
def ai():
    if r := _guard():
        return r
    return _render("ai", "ai.html", **_ai.context())


# ═══════════ دستیار هوشمند مدیریتی سوپرادمین (سایت) ═══════════

@panel_bp.route("/super-assistant")
@require_super
def super_assistant():
    if r := _guard():
        return r
    return _render("super_assistant", "super_assistant.html", **_sassist.context())


@panel_bp.route("/super-assistant/chat", methods=["POST"])
@require_super
def super_assistant_chat():
    if r := _guard():
        return r
    return _sassist.handle_chat_post()


@panel_bp.route("/super-assistant/code-send", methods=["POST"])
@require_super
def super_assistant_code_send():
    if r := _guard():
        return r
    return _sassist.handle_code_send_post()


@panel_bp.route("/super-assistant/confirm", methods=["POST"])
@require_super
def super_assistant_confirm():
    if r := _guard():
        return r
    return _sassist.handle_action_confirm_post()


@panel_bp.route("/super-assistant/cancel", methods=["POST"])
@require_super
def super_assistant_cancel():
    if r := _guard():
        return r
    return _sassist.handle_action_cancel_post()


@panel_bp.route("/super-assistant/undo", methods=["POST"])
@require_super
def super_assistant_undo():
    if r := _guard():
        return r
    return _sassist.handle_undo_post()


@panel_bp.route("/super-assistant/clear", methods=["POST"])
@require_super
def super_assistant_clear():
    if r := _guard():
        return r
    return _sassist.handle_clear_post()


@panel_bp.route("/super-assistant/health")
@require_super
def super_assistant_health():
    if r := _guard():
        return r
    from flask import jsonify as _jsonify
    return _jsonify(ok=True, items=_sassist.get_system_health())


@panel_bp.route("/super-assistant/insight-status", methods=["POST"])
@require_super
def super_assistant_insight_status():
    if r := _guard():
        return r
    return _sassist.handle_insight_status_post()


@panel_bp.route("/ratelimit")
def ratelimit():
    # فاز جامع UX: صفحه مستقل حدف، در تب «⏱ محدودیت زمانی» آنالیزها ادغام شد
    return redirect(url_for("panel.analyses", tab="ratelimit"))


@panel_bp.route("/referrals")
def referrals():
    flash("برنامه معرفی متوقف شده است؛ مرکز مالی جایگزین این بخش است.", "info")
    return redirect(url_for("panel.wallet"))


@panel_bp.route("/referral-center")
def referrals_canonical():
    flash("برنامه معرفی متوقف شده است؛ مرکز مالی جایگزین این بخش است.", "info")
    return redirect(url_for("panel.wallet"))


@panel_bp.route("/wallet")
@require_manage
def wallet():
    return _render("wallet", "wallet.html", **_wallet.context())


@panel_bp.route("/wallet/missions", methods=["POST"])
@require_super
def wallet_mission_create():
    from giso.wallet import create_mission
    ok, message = create_mission({
        "code": request.form.get("code", ""),
        "title": request.form.get("title", ""),
        "description": request.form.get("description", ""),
        "reward_amount": request.form.get("reward_amount", ""),
        "reward_scope": request.form.get("reward_scope", "spend"),
        "reward_points": request.form.get("reward_points", ""),
        "mission_type": request.form.get("mission_type", "once"),
        "is_active": request.form.get("is_active") == "1",
    })
    flash(message, "success" if ok else "danger")
    return redirect(url_for("panel.wallet", tab="missions"))


@panel_bp.route("/wallet/missions/<int:mission_id>", methods=["POST"])
@require_super
def wallet_mission_update(mission_id):
    from giso.wallet import update_mission
    ok, message = update_mission(mission_id, {
        "title": request.form.get("title", ""),
        "description": request.form.get("description", ""),
        "reward_amount": request.form.get("reward_amount", ""),
        "reward_scope": request.form.get("reward_scope", "spend"),
        "reward_points": request.form.get("reward_points", ""),
        "mission_type": request.form.get("mission_type", "once"),
        "is_active": request.form.get("is_active") == "1",
    })
    flash(message, "success" if ok else "danger")
    return redirect(url_for("panel.wallet", tab="missions"))


@panel_bp.route("/wallet/missions/awards/<int:completion_id>", methods=["POST"])
@require_super
def wallet_mission_award(completion_id):
    from giso.wallet import review_mission_award
    ok, message = review_mission_award(completion_id, request.form.get("action", ""))
    flash(message, "success" if ok else "danger")
    return redirect(url_for("panel.wallet", tab="missions"))


@panel_bp.route("/wallet/missions/<int:mission_id>/delete", methods=["POST"])
@require_super
def wallet_mission_delete(mission_id):
    from giso.wallet import delete_mission
    ok, message = delete_mission(mission_id)
    flash(message, "success" if ok else "danger")
    return redirect(url_for("panel.wallet", tab="missions"))


@panel_bp.route("/wallet/topups/<int:request_id>/receipt", methods=["GET"])
@require_manage
def wallet_topup_receipt(request_id):
    from giso.base import get_giso_db_conn
    from giso.wallet_receipts import receipt_file_path
    try:
        with get_giso_db_conn() as conn:
            row = conn.execute(
                "SELECT receipt_path FROM wallet_topup_requests WHERE id=?", (int(request_id),)
            ).fetchone()
        if not row or not row["receipt_path"]:
            return abort(404)
        path = receipt_file_path(row["receipt_path"])
        response = send_file(path, mimetype="image/png" if path.suffix == ".png" else "image/jpeg",
                             as_attachment=False, download_name=f"topup-{request_id}{path.suffix}")
        response.headers["Cache-Control"] = "private, no-store, max-age=0"
        response.headers["X-Content-Type-Options"] = "nosniff"
        return response
    except FileNotFoundError:
        return abort(404)


@panel_bp.route("/wallet/topups/<int:request_id>/status", methods=["POST"])
@require_super
def wallet_topup_status(request_id):
    from giso.wallet import review_topup
    ok, message = review_topup(
        request_id, request.form.get("status", ""), request.form.get("admin_note", "")
    )
    flash(message, "success" if ok else "danger")
    return redirect(url_for("panel.wallet", tab="topups"))


@panel_bp.route("/wallet/settlements/<int:withdrawal_id>/status", methods=["POST"])
@require_super
def wallet_settlement_status(withdrawal_id):
    from giso.wallet import review_withdrawal
    ok, message = review_withdrawal(
        withdrawal_id, request.form.get("status", ""), request.form.get("admin_note", "")
    )
    flash(message, "success" if ok else "danger")
    return redirect(url_for("panel.wallet", tab="settlements"))


@panel_bp.route("/wallet/service-fees", methods=["POST"])
@require_super
def wallet_service_fees():
    from giso.wallet import save_service_fees
    ok, message = save_service_fees({
        "fee_analysis": request.form.get("fee_analysis", ""),
        "fee_hair": request.form.get("fee_hair", ""),
        "fee_shop": request.form.get("fee_shop", ""),
        "fee_marketplace": request.form.get("fee_marketplace", ""),
    })
    flash(message, "success" if ok else "danger")
    return redirect(url_for("panel.wallet", tab="settings"))


@panel_bp.route("/wallet/rank-settings", methods=["POST"])
@require_super
def wallet_rank_settings():
    from giso.wallet import save_rank_settings
    values = {
        "daily_credit_enabled": request.form.get("daily_credit_enabled") == "1",
    }
    for level in (1, 2, 3, 4):
        values[f"threshold_{level}"] = request.form.get(f"threshold_{level}", "")
        values[f"daily_credit_{level}"] = request.form.get(f"daily_credit_{level}", "")
    ok, message = save_rank_settings(values)
    flash(message, "success" if ok else "danger")
    return redirect(url_for("panel.wallet", tab="ranks"))


@panel_bp.route("/wallet/rank-deposit", methods=["POST"])
@require_super
def wallet_rank_deposit():
    from giso.rank_daily import deposit_rank_credits_for_date
    today = (request.form.get("date") or "").strip()[:10] or None
    res = deposit_rank_credits_for_date(today if today else None, push=True)
    if not res.get("ok"):
        flash("واریز روزانهٔ رتبه فعال نیست یا انجام نشد.", "warning")
    else:
        flash(f"واریز انجام شد: {res.get('deposited', 0)} نفر — "
              f"{res.get('skipped', 0)} قبلاً پردازش‌شده.", "success")
    return redirect(url_for("panel.wallet", tab="ranks"))


@panel_bp.route("/wallet/service-credits", methods=["POST"])
@require_super
def wallet_service_credits():
    from giso.wallet import save_service_credit_settings, SERVICE_CREDIT_DEFS
    values = {}
    for key, _label, _en, _fee, _d in SERVICE_CREDIT_DEFS:
        values[f"fee_{key}"] = request.form.get(f"fee_{key}", "")
        values[f"enabled_{key}"] = request.form.get(f"enabled_{key}") == "1"
    ok, message = save_service_credit_settings(values)
    flash(message, "success" if ok else "danger")
    return redirect(url_for("panel.wallet", tab="service_credits"))


@panel_bp.route("/wallet/settings", methods=["POST"])
@require_super
def wallet_settings():
    from giso.wallet import save_financial_settings
    ok, message = save_financial_settings({
        "topup_enabled": request.form.get("topup_enabled") == "1",
        "withdrawal_enabled": request.form.get("withdrawal_enabled") == "1",
        "min_topup": request.form.get("min_topup", ""),
        "min_withdrawal": request.form.get("min_withdrawal", ""),
        "topup_method": request.form.get("topup_method", ""),
        "card_holder": request.form.get("card_holder", ""),
        "card_number": request.form.get("card_number", ""),
        "sheba": request.form.get("sheba", ""),
        "invoice_seller_name": request.form.get("invoice_seller_name", ""),
        "invoice_seller_phone": request.form.get("invoice_seller_phone", ""),
        "invoice_seller_address": request.form.get("invoice_seller_address", ""),
    })
    flash(message, "success" if ok else "danger")
    return redirect(url_for("panel.wallet", tab="settings"))


# ═══════════ فاز B: فروشگاه (🛍) — پنل ادمین / سوپرادمین ═══════════

@panel_bp.route("/shop")
def shop():
    if r := _guard():
        return r
    ensure_shop_template_paths(current_app)
    return _render("shop", "admin/shop.html", **_shop_admin.context())


@panel_bp.route("/shop-super")
@require_super
def shop_super():
    """فاز جامع UX: «تنظیمات فروشگاه» حذف و داخل «🛍 مدیریت فروشگاه» (تب تنظیمات) تجمیع شد."""
    if r := _guard():
        return r
    return redirect(url_for("panel.shop") + "#pane-config")


@panel_bp.route("/monitoring/settings",methods=["POST"])
@require_super
def monitoring_settings_save():
    if r := _guard(): return r
    from giso.monitoring_settings import save,KEYS
    save({k:request.form.get(k)=="1" for k in KEYS},
         ai_hour=request.form.get('ai_hour'),
         interval_hours=request.form.get('interval_hours'),
         report_refresh_hours=request.form.get('report_refresh_hours'))
    flash("تنظیمات پایش ذخیره شد.","success")
    return redirect(url_for("panel.monitoring",tab="settings"))


@panel_bp.route("/monitoring/broadcast/prepare",methods=["POST"])
@require_super
def monitoring_broadcast_prepare():
    if r := _guard(): return r
    from flask import session
    title=" ".join((request.form.get('title') or '').split())[:160];message=(request.form.get('message') or '').strip()[:3000]
    channel=(request.form.get('channel') or 'site').strip();target=(request.form.get('target') or 'all').strip();link=(request.form.get('link_url') or '').strip()[:500]
    if not title or not message or channel not in ('site','bot','both') or target not in ('all','centers','buyers','sellers'):
        flash("اطلاعات پیام کامل یا معتبر نیست.","warning")
    elif link and not link.startswith(('https://','http://')):
        flash("لینک باید با https:// یا http:// شروع شود.","warning")
    else:
        session['broadcast_preview']={'title':title,'message':message,'channel':channel,'target':target,'link_url':link};session.modified=True
    return redirect(url_for('panel.monitoring',tab='broadcasts'))

@panel_bp.route("/monitoring/broadcast/send",methods=["POST"])
@require_super
def monitoring_broadcast_send():
    if r := _guard(): return r
    from flask import session
    data=session.pop('broadcast_preview',None) or {}
    if not data:flash("پیش‌نمایش منقضی شده است.","warning")
    else:
        from giso.broadcasts import create_campaign
        from flask_login import current_user
        ok,msg,_=create_campaign(data.get('title'),data.get('message'),data.get('link_url'),data.get('channel'),data.get('target'),getattr(current_user,'id',0));flash(msg,'success' if ok else 'danger')
    return redirect(url_for('panel.monitoring',tab='broadcasts'))

@panel_bp.route("/monitoring/reset/<scope>",methods=["POST"])
@require_super
def monitoring_reset(scope):
    if r := _guard(): return r
    if request.form.get('confirm')!='RESET':
        flash("تأیید بازنشانی معتبر نیست.","warning")
        return redirect(url_for('panel.monitoring',tab=scope))
    from giso.monitoring_reset import reset
    ok,msg,count=reset(scope)
    try:
        from giso.security import audit_event
        audit_event('monitoring_reset','success' if ok else 'failed',target=scope,details=f'count={count}')
    except Exception:pass
    flash(f"{msg} تعداد: {count}",'success' if ok else 'danger')
    return redirect(url_for('panel.monitoring',tab=scope))

@panel_bp.route("/monitoring/ai-report/run",methods=["POST"])
@require_super
def monitoring_ai_report_run():
    if r := _guard(): return r
    from giso.async_compat import run_async_safe
    from giso.monitoring_ai import generate
    ok,msg=run_async_safe(generate(force=True));flash(msg,'success' if ok else 'warning')
    return redirect(url_for('panel.monitoring',tab='ai_reports'))

@panel_bp.route("/monitoring/bug-reports/<int:report_id>/review", methods=["POST"])
@require_super
def monitoring_bug_review(report_id):
    if r := _guard():
        return r
    from giso.bug_reports import review
    from flask_login import current_user
    decision = (request.form.get("decision") or "").strip()
    note = request.form.get("admin_note") or ""
    actor = str(getattr(current_user, "phone", "") or "super")
    ok, message = review(report_id, decision, actor, note)
    try:
        from giso.security import audit_event
        audit_event("bug_report_review", "success" if ok else "failed",
                    target=str(report_id), details=f"decision={decision}")
    except Exception:
        pass
    from flask import flash
    flash(message, "success" if ok else "warning")
    return redirect(url_for("panel.monitoring", tab="errors") + "#bug-reports")


@panel_bp.route("/monitoring/errors-report.txt")
@require_super
def monitoring_errors_report_download():
    """دانلود گزارش متنی کامل خطاها و وضعیت سیستم (کش‌شده با بازهٔ تنظیم‌شده)."""
    if r := _guard():
        return r
    from giso.monitoring_errors import get_or_refresh_text_report
    try:
        hours = max(1, min(168, int(request.args.get("hours", 24) or 24)))
    except (TypeError, ValueError):
        hours = 24
    force = request.args.get("refresh") == "1"
    text, _gen, _ref = get_or_refresh_text_report(force=force, hours=hours)
    import io
    from flask import send_file
    return send_file(
        io.BytesIO(text.encode("utf-8")),
        mimetype="text/plain; charset=utf-8",
        as_attachment=True,
        download_name="giso-error-report.txt",
    )


@panel_bp.route("/monitoring/manual-error", methods=["POST"])
@require_super
def monitoring_manual_error_create():
    """ثبت گزارش دستی خطا: مخاطب/مشکل/منبع خطا/علت/چرایی."""
    if r := _guard():
        return r
    from giso.monitoring_errors import record_manual
    from flask_login import current_user
    reporter = str(getattr(current_user, "phone", "") or "super")[:40]
    ok, msg = record_manual(
        reporter=reporter,
        audience=request.form.get("audience", ""),
        problem=request.form.get("problem", ""),
        error_source=request.form.get("error_source", ""),
        cause=request.form.get("cause", ""),
        why=request.form.get("why", ""),
        severity=request.form.get("severity", "error"),
    )
    try:
        from giso.security import audit_event
        audit_event("monitoring_manual_error", "success" if ok else "failed",
                    target="manual", details=(request.form.get("problem", "") or "")[:200])
    except Exception:
        pass
    flash(msg, "success" if ok else "danger")
    return redirect(url_for("panel.monitoring", tab="errors") + "#manual-error")


@panel_bp.route("/monitoring")
@require_super
def monitoring():
    if r := _guard(): return r
    from giso.panel.modules import monitoring as _monitoring
    return _render("monitoring", "monitoring.html", **_monitoring.context())


@panel_bp.route("/reports")
@require_super
def reports():
    if r := _guard():
        return r
    return _render("reports", "reports.html", **_reports.context())


# ═══════════ دستیار اختصاصی ادمین (آقا رضا) — فقط نقش special ═══════════

def _guard_special():
    """گارد اختصاصی: فقط ادمین اختصاصی (special). سوپر/ادمین عادی رد می‌شوند.

    خروجی: ``(deny_return, role)`` که در صورت مجاز بودن ``deny_return`` برابر
    ``None`` است؛ در غیر این‌صورت یک مقدار قابل‌برگشت برای Flask است (یا یک
    ``redirect`` برای مرورگر، یا تاپل ``(jsonify(...), 403)`` برای درخواست AJAX).
    """
    if r := _guard():
        return r, ""
    role, _perms, _bid = current_role_and_perms()
    if role != "special":
        if request.headers.get("X-Requested-With") == "XMLHttpRequest":
            from flask import jsonify
            return (jsonify({"ok": False, "text": "این دستیار فقط برای ادمین اختصاصی فعال است."}), 403), ""
        flash("⛔ این بخش فقط برای ادمین اختصاصی مجاز است.", "warning")
        return redirect(url_for("panel.dashboard")), ""
    return None, role


@panel_bp.route("/assistant/chat", methods=["POST"])
def assistant_chat():
    from flask import jsonify
    g, _r = _guard_special()
    if g:
        return g
    from flask_login import current_user
    from giso.base import normalize_phone
    from giso.special_assistant import answer_sync, init_special_assistant_tables
    phone_norm = normalize_phone(getattr(current_user, "phone", "") or "")
    if not phone_norm:
        return jsonify({"ok": False, "text": "شماره کاربر شناسایی نشد."}), 400
    message = (request.form.get("message") or request.json.get("message", "") if request.is_json else request.form.get("message") or "")
    page = (request.form.get("page") or (request.json.get("page", "") if request.is_json else "") or "")
    message = (message or "").strip()[:1500]
    init_special_assistant_tables()
    if not message:
        return jsonify({"ok": False, "text": "پیامی ارسال نشد."}), 400
    res = answer_sync(phone_norm, message, channel="site", page_path=str(page)[:200])
    return jsonify({"ok": bool(res.get("ok")), "text": res.get("text", "")})


@panel_bp.route("/assistant/history")
def assistant_history():
    from flask import jsonify
    g, _r = _guard_special()
    if g:
        return g
    from flask_login import current_user
    from giso.base import normalize_phone
    from giso.special_assistant import (
        actor_key_for, get_history, welcome_for_page, page_intro, live_stats,
    )
    phone_norm = normalize_phone(getattr(current_user, "phone", "") or "")
    page = (request.args.get("page") or "").strip()
    history = get_history(actor_key_for(phone_norm))
    stats = live_stats()
    return jsonify({
        "ok": True,
        "name": "آقا رضا",
        "welcome": welcome_for_page(page),
        "page_intro": page_intro(page, stats),
        "history": history,
        "stats": stats,
    })


@panel_bp.route("/aga-reza")
@require_special
def aga_reza():
    """صفحهٔ سایدبار آقا رضا؛ منطق چت همان special_assistant موجود است."""
    from giso.special_assistant import live_stats, welcome_for_page, ASSISTANT_NAME
    return _render(
        "aga_reza", "aga_reza.html",
        stats=live_stats() or {},
        welcome=welcome_for_page("dashboard"),
        assistant_name=ASSISTANT_NAME,
    )


@panel_bp.route("/special-reports")
@require_special
def special_reports():
    """گزارش شخصی فقط‌خواندنی از آمار زندهٔ آقا رضا — بدون ماژول مالی سوپر."""
    from giso.special_assistant import live_stats
    return _render("special_reports", "special_reports.html", stats=live_stats() or {})


@panel_bp.route("/special-guide")
def special_guide():
    """مرحله ۷: راهنمای کامل فارسی HTML، فقط برای ادمین اختصاصی (با دانلود/چاپ در خود صفحه)."""
    from flask import jsonify, send_from_directory
    role_r, role = _guard_special()
    if role_r is not None:
        # برای غیرِ special: در مرورگر به داشبورد برمی‌گردیم (به‌جای پاسخ JSON نامناسب)
        if not request.headers.get("X-Requested-With"):
            flash("⛔ این راهنما فقط برای ادمین اختصاصی است.", "warning")
            return redirect(url_for("panel.dashboard"))
        return jsonify({"ok": False, "text": "این راهنما فقط برای ادمین اختصاصی فعال است."}), 403
    from pathlib import Path
    guide_dir = Path(__file__).resolve().parent / "static"
    return send_from_directory(guide_dir, "special-admin-guide.html")


@panel_bp.route("/settings", methods=["GET", "POST"])
@require_super
def settings():
    if r := _guard():
        return r
    if request.method == "POST":
        return _settings.handle_post()
    return _render("settings", "settings.html", **_settings.context())


# ═══════════ فاز 5: پشتیبان‌گیری / بازگردانی / ریستارت (فقط سوپرادمین) ═══════════

@panel_bp.route("/settings/backup-now", methods=["POST"])
@require_super
def backup_now():
    if r := _guard():
        return r
    return _backup.handle_backup_now()


@panel_bp.route("/settings/backup-interval", methods=["POST"])
@require_super
def backup_interval():
    if r := _guard():
        return r
    return _backup.handle_set_interval()


@panel_bp.route("/settings/backup-upload", methods=["POST"])
@require_super
def backup_upload():
    if r := _guard():
        return r
    return _backup.handle_upload()


@panel_bp.route("/settings/backup-restore", methods=["POST"])
@require_super
def backup_restore():
    if r := _guard():
        return r
    return _backup.handle_restore()


@panel_bp.route("/settings/backup-delete", methods=["POST"])
@require_super
def backup_delete():
    if r := _guard():
        return r
    return _backup.handle_delete_file()


@panel_bp.route("/settings/recovery-create", methods=["POST"])
@require_super
def recovery_create():
    if r := _guard():
        return r
    return _backup.handle_recovery_create()


@panel_bp.route("/settings/recovery-upload", methods=["POST"])
@require_super
def recovery_upload():
    if r := _guard():
        return r
    return _backup.handle_recovery_upload()


@panel_bp.route("/settings/recovery-restore", methods=["POST"])
@require_super
def recovery_restore():
    if r := _guard():
        return r
    return _backup.handle_recovery_restore()


@panel_bp.route("/settings/recovery-download")
@require_super
def recovery_download():
    if r := _guard():
        return r
    return _backup.handle_recovery_download()


@panel_bp.route("/settings/recovery-download-latest")
@require_super
def recovery_download_latest():
    if r := _guard():
        return r
    return _backup.handle_recovery_download_latest()


@panel_bp.route("/settings/backup-download")
@require_super
def backup_download():
    if r := _guard():
        return r
    return _backup.handle_backup_download()


@panel_bp.route("/settings/recovery-auto", methods=["POST"])
@require_super
def recovery_auto_toggle():
    if r := _guard():
        return r
    return _backup.handle_recovery_auto_toggle()


@panel_bp.route("/settings/restart", methods=["POST"])
@require_super
def restart_bot():
    if r := _guard():
        return r
    return _backup.handle_restart()


@panel_bp.route("/settings/restart-cancel", methods=["POST"])
@require_super
def restart_bot_cancel():
    if r := _guard():
        return r
    return _backup.handle_restart_cancel()


# ═══════════ فاز جامع: 🔔 مدیریت اعلان‌ها (سوپرادمین همه‌چیز؛ ادمین فقط «اعلان‌های من») ═══════════
from giso.panel.modules import notifications as _notif  # noqa: E402


@panel_bp.route("/notifications")
@require_super
def notifications():
    if r := _guard():
        return r
    role, _perms, _bid = current_role_and_perms()
    category = (request.args.get("category") or "").strip()
    status = (request.args.get("status") or "").strip()
    return _render("notifications", "notifications.html",
                   **_notif.context(role, category=category, status=status))


@panel_bp.route("/notifications/data")
def notifications_data():
    """داده سبک برای Bell: آخرین اعلان‌های نقش جاری + شمارنده خوانده‌نشده (JSON)."""
    if r := _guard():
        return r
    from flask import jsonify
    try:
        role, _perms, _bid = current_role_and_perms()
        items = _notif.list_notifications(role, limit=5)
        unread = _notif.unread_count(role)
        return jsonify({
            "ok": True,
            "unread": unread,
            "items": [{"id": n["id"], "title": n["title"], "message": n["message"],
                       "category": n["category"], "status": n["status"],
                       "created_at": n["created_at"], "cat_fa": n.get("cat_fa", ""),
                       "url": n.get("url", ""),
                       "icon": n.get("icon", "🔔")} for n in items],
        })
    except Exception as e:
        logger.warning(f"notifications_data: {e}")
        return jsonify({"ok": False, "unread": 0, "items": []})


@panel_bp.route("/notifications/<int:nid>/read", methods=["POST"])
@require_super
def notification_read(nid):
    if r := _guard():
        return r
    # رفع R1: نقش کاربر جاری به لایه mutation پاس داده می‌شود تا
    # ادمین معمولی نتواند اعلان سوپرادمین را (که نمی‌بیند) تغییر دهد.
    role, _perms, _bid = current_role_and_perms()
    if _notif.set_status(nid, "read", role):
        flash("اعلان به‌عنوان «خوانده شد» ثبت شد.", "success")
    else:
        _audit_denied("notification_read", nid, role)
        flash("⛔ این اعلان در دسترس شما نیست.", "warning")
    return redirect(url_for("panel.notifications"))


@panel_bp.route("/notifications/<int:nid>/archive", methods=["POST"])
@require_super
def notification_archive(nid):
    if r := _guard():
        return r
    role, _perms, _bid = current_role_and_perms()
    if _notif.set_status(nid, "archived", role):
        flash("اعلان آرشیو شد.", "success")
    else:
        _audit_denied("notification_archive", nid, role)
        flash("⛔ این اعلان در دسترس شما نیست.", "warning")
    return redirect(url_for("panel.notifications"))




def _back_to_active_tab(endpoint: str = "panel.notifications") -> str:
    """فاز جامع UX: برگشت به تب فعلی صفحه (_back_tab که JS فرم تزریق می‌کند)."""
    tab = (request.form.get("_back_tab") or "").strip() or "list"
    return url_for(endpoint) + "#pane-" + tab


@panel_bp.route("/notifications/read-all", methods=["POST"])
@require_super
def notification_read_all():
    if r := _guard():
        return r
    role, _perms, _bid = current_role_and_perms()
    n = _notif.mark_all_read(role)
    flash(f"{n} اعلان به‌عنوان خوانده‌شده علامت خورد.", "success")
    return redirect(_back_to_active_tab())


@panel_bp.route("/notifications/archive-all", methods=["POST"])
@require_super
def notification_archive_all():
    if r := _guard():
        return r
    # رفع R2: به‌جای SQL درون-route با فیلتر متفاوت، از همان سیاست نقشِ
    # list/unread استفاده می‌شود تا «دیدن» و «آرشیو» دقیقاً یکسان باشند.
    role, _perms, _bid = current_role_and_perms()
    n = _notif.archive_all(role)
    flash(f"{n} اعلان آرشیو شد.", "success")
    return redirect(_back_to_active_tab())


@panel_bp.route("/notifications/delete-all", methods=["POST"])
@require_super
def notification_delete_all():
    if r := _guard():
        return r
    role, _perms, _bid = current_role_and_perms()
    n = _notif.delete_all(role)
    flash(f"{n} اعلان برای همیشه حذف شد.", "success")
    return redirect(_back_to_active_tab())


@panel_bp.route("/notifications/settings", methods=["POST"])
@require_super
def notification_settings():
    if r := _guard():
        return r
    role, _perms, _bid = current_role_and_perms()
    if role != "super":
        flash("⛔ فقط سوپرادمین می‌تواند تنظیمات اعلان‌ها را تغییر دهد.", "warning")
        return redirect(url_for("panel.notifications"))
    updates = {}
    for cat, _st in _notif.DEFAULT_CATEGORY_SETTINGS.items():
        target = (request.form.get(f"target_{cat}") or "").strip()
        dest = (request.form.get(f"dest_{cat}") or "").strip()
        enabled = (request.form.get(f"enabled_{cat}") or "0").strip()
        if target or dest or enabled in ("1", "0"):
            updates[cat] = {
                "target_role": target or None,
                "destination": dest or None,
                "enabled": int(enabled) if enabled in ("1", "0") else None,
            }
    ok, msg = _notif.save_category_settings(updates)
    flash(msg, "success" if ok else "danger")
    return redirect(_back_to_active_tab())


@panel_bp.route("/notifications/archive-days", methods=["POST"])
@require_super
def notification_archive_days():
    if r := _guard():
        return r
    role, _perms, _bid = current_role_and_perms()
    if role != "super":
        flash("⛔ فقط سوپرادمین می‌تواند این تنظیم را تغییر دهد.", "warning")
        return redirect(url_for("panel.notifications"))
    try:
        days = int(request.form.get("days", "7") or "7")
    except (TypeError, ValueError):
        days = 7
    if _notif.set_archive_days(days):
        flash(f"آرشیو خودکار بعد از {days} روز فعال شد.", "success")
    else:
        flash("خطا در ذخیره تنظیم آرشیو.", "danger")
    return redirect(_back_to_active_tab())


@panel_bp.route("/notifications/sound", methods=["POST"])
@require_super
def notification_sound():
    if r := _guard():
        return r
    role, _perms, _bid = current_role_and_perms()
    if role != "super":
        flash("⛔ فقط سوپرادمین می‌تواند این تنظیم را تغییر دهد.", "warning")
        return redirect(url_for("panel.notifications"))
    on = (request.form.get("on") or "1") == "1"
    _notif.set_sound_on(on)
    flash("تنظیم صدا ذخیره شد (فقط UI).", "success")
    return redirect(_back_to_active_tab())


@panel_bp.route("/notifications/test", methods=["POST"])
@require_super
def notification_test():
    if r := _guard():
        return r
    role, _perms, _bid = current_role_and_perms()
    if role != "super":
        flash("⛔ تست ارسال فقط برای سوپرادمین است.", "warning")
        return redirect(url_for("panel.notifications"))
    ok, msg = _notif.test_send()
    flash(msg, "success" if ok else "danger")
    return redirect(_back_to_active_tab())


# ═══════════ فاز 5: اکشن‌های آنالیز (مشاوره / محصول درخواستی) ═══════════

@panel_bp.route("/analyses/consultant/<int:req_id>/reply", methods=["POST"])
@require_super
def analyses_consultant_reply(req_id):
    if r := _guard():
        return r
    return _analyses.handle_consultant_reply(req_id)


@panel_bp.route("/analyses/consultant/<int:req_id>/status", methods=["POST"])
@require_super
def analyses_consultant_status(req_id):
    if r := _guard():
        return r
    return _analyses.handle_consultant_status(req_id)


@panel_bp.route("/analyses/product/<int:req_id>/status", methods=["POST"])
@require_super
def analyses_product_status(req_id):
    if r := _guard():
        return r
    return _analyses.handle_product_status(req_id)


# ═══════════ فاز 5: پورسانت فروش مو (همان کلیدهای ربات) ═══════════

@panel_bp.route("/hair-commission", methods=["POST"])
@require_super
def hair_commission():
    if r := _guard():
        return r
    return _hair.handle_commission()


# ═══════════ فاز 5: مدیریت کامل AI ═══════════

@panel_bp.route("/ai/config", methods=["POST"])
@require_super
def ai_config():
    if r := _guard():
        return r
    return _ai.handle_config()


@panel_bp.route("/ai/credits/adjust", methods=["POST"])
@require_super
def ai_credit_adjust():
    if r := _guard(): return r
    return _ai.handle_credit_adjust()


# مورد ۱۱ help2: انتخاب حوزهٔ کسر اعتبار کاربر (نقدی/مصرفی)
@panel_bp.route("/ai/credits/scope", methods=["POST"])
@require_super
def ai_credit_scope():
    if r := _guard(): return r
    return _ai.handle_credit_scope()


@panel_bp.route("/ai/provider/add", methods=["POST"])
@require_super
def ai_provider_add():
    if r := _guard():
        return r
    return _ai.handle_provider_add()


@panel_bp.route("/ai/provider/<path:name>/toggle", methods=["POST"])
@require_super
def ai_provider_toggle(name):
    if r := _guard():
        return r
    return _ai.handle_provider_toggle(name)


@panel_bp.route("/ai/provider/<path:name>/proxy", methods=["POST"])
@require_super
def ai_provider_proxy(name):
    if r := _guard():
        return r
    return _ai.handle_provider_proxy(name)


@panel_bp.route("/ai/provider/<path:name>/update", methods=["POST"])
@require_super
def ai_provider_update(name):
    if r := _guard():
        return r
    return _ai.handle_provider_update(name)


@panel_bp.route("/ai/provider/<path:name>/delete", methods=["POST"])
@require_super
def ai_provider_delete(name):
    if r := _guard():
        return r
    return _ai.handle_provider_delete(name)


@panel_bp.route("/ai/provider/<path:name>/test", methods=["POST"])
@require_super
def ai_provider_test(name):
    if r := _guard():
        return r
    return _ai.handle_provider_test(name)


@panel_bp.route("/ai/test-all", methods=["POST"])
@require_super
def ai_test_all():
    if r := _guard():
        return r
    return _ai.handle_test_all()


@panel_bp.route("/ai/chat-test", methods=["POST"])
@require_super
def ai_chat_test():
    if r := _guard():
        return r
    return _ai.handle_chat_test()


@panel_bp.route("/ai/provider/<path:name>/refresh-models", methods=["POST"])
@require_super
def ai_provider_refresh_models(name):
    if r := _guard():
        return r
    return _ai.handle_refresh_models(name)


@panel_bp.route("/ai/refresh-all-models", methods=["POST"])
@require_super
def ai_provider_refresh_all_models():
    """مأموریت 11: دکمهٔ «بروزرسانی همهٔ هوش مصنوعی‌ها» — کشف هوشمند."""
    if r := _guard():
        return r
    return _ai.handle_refresh_all_models()


@panel_bp.route("/ai/bulk-import-json", methods=["POST"])
@require_super
def ai_bulk_import_json():
    if r := _guard():
        return r
    return _ai.handle_bulk_import()


@panel_bp.route("/ai/pending/<int:pending_id>/execute", methods=["POST"])
@require_super
def ai_pending_execute(pending_id):
    if r := _guard():
        return r
    return _ai.handle_pending_execute(pending_id)


@panel_bp.route("/ai/pending/<int:pending_id>/cancel", methods=["POST"])
@require_super
def ai_pending_cancel(pending_id):
    if r := _guard():
        return r
    return _ai.handle_pending_cancel(pending_id)


@panel_bp.route("/ai/log/<int:log_id>/rollback", methods=["POST"])
@require_super
def ai_log_rollback(log_id):
    if r := _guard():
        return r
    return _ai.handle_rollback(log_id)
