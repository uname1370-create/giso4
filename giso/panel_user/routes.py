# -*- coding: utf-8 -*-
"""
giso/panel_user/routes.py — routeهای ماژولار پنل کاربر عادی (فاز 4.2)

آدرس canonical: /dashboard
ماژول‌ها: /dashboard/<module>
فرم‌ها به route های POST قدیمی submit می‌شوند (action های قبلی حفظ شده).
"""
import logging

from flask import render_template, redirect, url_for, flash, current_app, request, abort
from flask_login import login_required, current_user

from giso.panel_user import panel_user_bp
from giso.panel_user.permissions import USER_MODULES, USER_MODULE_GROUPS, MODULES_META, current_user_role
from giso.panel_user.modules import (
    overview as _ov, profile as _pf, orders as _od, hair_sale as _hs,
    analyses as _an, chats as _ch, wallet as _wl, notifies as _nt, reviews as _rv,
    marketplace as _mp,
)
from giso.shop.panel import user as _shop_user
from giso.shop.routes import ensure_shop_template_paths
from giso.models import db, Wishlist
from giso.panel.modules.notifications import (
    list_user_notifications, user_unread_count, mark_user_notifications_read,
)

logger = logging.getLogger("giso_panel_user_routes")

MODULE_VIEWS = {
    "overview": _ov,
    "profile": _pf,
    "orders": _od,
    "hair_sale": _hs,
    "marketplace": _mp,
    "analyses": _an,
    "chats": _ch,
    "wallet": _wl,
    "notifies": _nt,
    "reviews": _rv,
    "shop": _shop_user,
}


def _guard():
    """گارد: فقط کاربر عادی لاگین‌شده؛ ادمین/سوپر → پنل مدیریت."""
    if not current_user.is_authenticated:
        return_to = request.full_path.rstrip("?")
        return redirect(url_for("login", next=return_to))
    role = current_user_role()
    if role in ("admin", "super"):
        return redirect(url_for("panel.dashboard"))
    return None


@panel_user_bp.before_request
def _guard_before_context_build():
    """گارد Blueprint باید پیش از محاسبه context هر route اجرا شود."""
    return _guard()


def _menu_for_current_user():
    """منوی گروه‌بندی‌شدهٔ کاربر (اصلی/خدمات/پشتیبانی/حساب) — §۷ سناریو."""
    from giso.panel_user.permissions import MODULES_META, USER_MODULE_GROUPS
    has_center = False
    try:
        from giso.beauty_centers.services import get_owner_center
        has_center = bool(get_owner_center(int(getattr(current_user, "id", 0) or 0)))
    except Exception:
        has_center = False
    menu = []
    for group, mods in USER_MODULE_GROUPS.items():
        menu.append(("__group", group, ""))
        for m in mods:
            if m == "beauty_center" and not has_center:
                continue
            label, icon = MODULES_META.get(m, (m, "•"))
            menu.append((m, label, icon))
    return menu


def _render(module, template_module=None, **ctx):
    g = _guard()
    if g:
        return g
    label, icon = MODULES_META.get(module, (module, "📄"))
    phone = getattr(current_user, "phone", "") or ""
    wallet_usable = 0
    try:
        from giso.wallet import get_wallet_balances
        _hdr_uid = int(getattr(current_user, "id", 0) or 0)
        _hdr_bal = {}
        wallet_usable = (get_wallet_balances(_hdr_uid) or {}).get("usable", 0)
        try:
            from giso.wallet_core import grant_initial_spend_credit as _gisc
            if _hdr_uid and _gisc(_hdr_uid):
                wallet_usable = (get_wallet_balances(_hdr_uid) or {}).get("usable", wallet_usable)
            _hdr_bal = get_wallet_balances(_hdr_uid) or {}
        except Exception:
            _hdr_bal = {}
    except Exception:
        wallet_usable = 0
    menu_badges = {}
    try:
        from giso.beauty_centers.services import user_center_unread_count
        center_unread = user_center_unread_count(int(getattr(current_user, "id", 0) or 0))
        if center_unread:
            menu_badges["center_chats"] = center_unread
    except Exception:
        pass
    try:
        unread = int(user_unread_count(phone) or 0)
        if unread:
            menu_badges["overview"] = unread
    except Exception:
        pass
    ctx.update({
        "user": current_user,
        "menu": _menu_for_current_user(), "menu_badges": menu_badges,
        "user_module_groups": USER_MODULE_GROUPS,
        "current_module": module,
        "current_module_label": label,
        "current_module_icon": icon,
        "user_notifications": list_user_notifications(phone, limit=5),
        "user_notification_unread": user_unread_count(phone),
        "header_wallet_usable": wallet_usable,
        "header_wallet_cash": (_hdr_bal or {}).get("cash", 0),
        "header_wallet_spend": (_hdr_bal or {}).get("spend", 0),
        "user_missions_pending": _pending_missions(int(getattr(current_user, "id", 0) or 0)),
    })
    return render_template(f"user_modules/{template_module or module}.html", **ctx)


def _pending_missions(user_id: int, limit: int = 5) -> list:
    """مورد ۳ help.md: ماموریت‌های در انتظار برای ویجت نوار بالای پنل کاربر."""
    try:
        from giso.wallet_missions import list_missions_for_user
        return [m for m in list_missions_for_user(user_id) if not m.get("completed")][:limit]
    except Exception:
        return []

@panel_user_bp.route("/")
@panel_user_bp.route("/overview")
def overview():
    return _render("overview", **(_ov.context() or {}))


@panel_user_bp.route("/profile")
def profile():
    return _render("profile", **(_pf.context() or {}))


@panel_user_bp.route("/orders")
def orders():
    return _render("orders", **(_od.context() or {}))


@panel_user_bp.route("/orders/<int:checkout_id>/edit", methods=["POST"])
def order_edit(checkout_id):
    if g := _guard(): return g
    from giso.wallet import edit_shop_checkout_atomic
    quantities={key.split('_',1)[1]:value for key,value in request.form.items() if key.startswith('qty_')}
    ok,message=edit_shop_checkout_atomic(current_user.id,checkout_id,quantities,request.form.get('address'),request.form.get('courier_note'),request.form.get('delivery_time'))
    flash(message,"success" if ok else "warning")
    return redirect(url_for('panel_user.orders'))


@panel_user_bp.route("/hair-sale")
def hair_sale():
    return _render("hair_sale", **(_hs.context() or {}))


@panel_user_bp.route("/hair-sale/<int:order_id>/edit", methods=["POST"])
def hair_sale_edit(order_id):
    if g := _guard(): return g
    from giso.base import get_giso_db_conn, normalize_phone
    phone = normalize_phone(getattr(current_user, "phone", "") or "")
    allowed = ("pending", "reviewing")
    try:
        length = max(10, min(200, int(request.form.get("length_cm") or 0)))
    except (TypeError, ValueError):
        flash("طول مو معتبر نیست.", "warning"); return redirect(url_for("panel_user.hair_sale"))
    with get_giso_db_conn() as conn:
        row = conn.execute("SELECT * FROM hair_orders WHERE id=? AND (user_id=? OR phone=?)", (int(order_id), int(current_user.id), phone)).fetchone()
        if not row: abort(404)
        if row["status"] not in allowed:
            flash("این درخواست دیگر قابل ویرایش نیست.", "warning"); return redirect(url_for("panel_user.hair_sale"))
        if int(row["user_edit_count"] or 0) >= 2:
            flash("سقف دو بار ویرایش این درخواست استفاده شده است.", "warning"); return redirect(url_for("panel_user.hair_sale"))
        # مأموریت 35: فیلد «قیمت مورد نظر» — خط قیمت قدیمی از توضیحات حذف و
        # قیمت جدید به‌صورت خط استاندارد جایگزینش می‌شود (بدون نیاز به ویرایش دستی متن).
        new_price = (request.form.get("seller_expected_price") or "").replace("<", "").replace(">", "").strip()[:80]
        desc_lines = [ln for ln in (request.form.get("description") or "").split("\n") if "قیمت مورد نظر فروشنده" not in ln]
        if new_price:
            insert_at = 1 if (desc_lines and desc_lines[0].startswith("🧭")) else 0
            desc_lines.insert(insert_at, f"💰 قیمت مورد نظر فروشنده: {new_price}")
        description = "\n".join(desc_lines)[:1000]
        conn.execute("UPDATE hair_orders SET length_cm=?,hair_color=?,hair_weight=?,hair_health=?,region=?,contact_time=?,description=?,user_edit_count=COALESCE(user_edit_count,0)+1,updated_at=datetime('now','localtime') WHERE id=?", (length,(request.form.get("hair_color") or "")[:100],(request.form.get("hair_weight") or "")[:100],(request.form.get("hair_health") or "")[:100],(request.form.get("region") or "")[:100],(request.form.get("contact_time") or "")[:100],description,int(order_id)))
        conn.commit()
    try:
        from giso.security import audit_event
        audit_event("hair_order_user_edit", "success", target=str(order_id), details="user_edit_count_incremented")
    except Exception: pass
    flash("اطلاعات درخواست ویرایش شد.", "success")
    return redirect(url_for("panel_user.hair_sale"))


@panel_user_bp.route("/hair-sale/<int:order_id>/withdraw", methods=["POST"])
def hair_sale_withdraw(order_id):
    if g := _guard(): return g
    from giso.base import get_giso_db_conn, normalize_phone
    phone=normalize_phone(getattr(current_user,"phone","") or "")
    with get_giso_db_conn() as conn:
        row=conn.execute("SELECT status FROM hair_orders WHERE id=? AND (user_id=? OR phone=?)",(int(order_id),int(current_user.id),phone)).fetchone()
        if not row:abort(404)
        if row["status"] not in ("pending","reviewing"):
            flash("این درخواست دیگر قابل انصراف نیست.","warning");return redirect(url_for("panel_user.hair_sale"))
        conn.execute("UPDATE hair_orders SET status='withdrawn',updated_at=datetime('now','localtime') WHERE id=?",(int(order_id),));conn.commit()
    try:
        from giso.security import audit_event
        audit_event("hair_order_user_withdraw", "success", target=str(order_id))
    except Exception: pass
    flash("درخواست با حفظ سابقه لغو شد.","success")
    return redirect(url_for("panel_user.hair_sale"))


@panel_user_bp.route("/marketplace")
def marketplace():
    # لینک‌های قدیمی تب درخواست خرید را بدون تغییر contract به صفحه مستقل هدایت کن.
    if request.args.get("tab") == "buyer-request":
        return redirect(url_for("panel_user.buyer_request"))
    return _render("marketplace", **(_mp.context() or {}))


@panel_user_bp.route("/hair/buyer-request")
def buyer_request():
    """نمای مستقل BuyerProfile؛ ثبت فرم همچنان به route POST فعلی انجام می‌شود."""
    return _render(
        "buyer_request", template_module="marketplace", buyer_request_page=True,
        **(_mp.context() or {}),
    )


@panel_user_bp.route("/analyses")
def analyses():
    return _render("analyses", **(_an.context() or {}))


@panel_user_bp.route("/analyses/<int:analysis_id>/restore", methods=["POST"])
def analysis_restore(analysis_id):
    if g := _guard(): return g
    from giso.models import Analysis, db
    from giso.base import normalize_phone
    row=Analysis.query.filter_by(id=analysis_id).first_or_404()
    if row.user_id!=current_user.id and normalize_phone(row.phone)!=normalize_phone(current_user.phone): abort(403)
    row.archived_at="";db.session.commit();flash("آنالیز به فهرست اصلی برگشت.","success")
    return redirect(url_for("panel_user.analyses",tab="archive"))


@panel_user_bp.route("/analyses/<int:analysis_id>/archive", methods=["POST"])
def analysis_archive(analysis_id):
    if g := _guard(): return g
    from datetime import datetime
    from giso.models import Analysis, db
    from giso.base import normalize_phone
    row=Analysis.query.filter_by(id=analysis_id).first_or_404()
    if row.user_id!=current_user.id and normalize_phone(row.phone)!=normalize_phone(current_user.phone): abort(403)
    row.archived_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S");db.session.commit()
    flash("آنالیز با حفظ گزارش و سوابق بایگانی شد.","success")
    return redirect(url_for("panel_user.analyses",tab=row.type))


@panel_user_bp.route("/analysis-history")
def analysis_history():
    # مقصد canonical متفاوت برای لینک legacy /dashboard/analyses
    return _render("analyses", **(_an.context() or {}))


@panel_user_bp.route("/chats")
def chats():
    return _render("chats", **(_ch.context() or {}))


@panel_user_bp.route("/assistant")
def ai_assistant():
    """دستیار هوشمند گیسو — چت هوشمند در پنل کاربری (گزارش‌محور، فقط‌خواندنی)."""
    return _render("ai_assistant")


@panel_user_bp.route("/conversations")
def conversations():
    # مقصد canonical متفاوت برای لینک legacy /dashboard/chats
    return _render("chats", **(_ch.context() or {}))


@panel_user_bp.route("/center-conversations")
def center_chats():
    """پرسش‌وپاسخ مستقل کاربر با مراکز زیبایی."""
    from giso.beauty_centers.services import user_center_conversations
    rows = user_center_conversations(int(getattr(current_user, "id", 0) or 0))
    return _render(
        "center_chats", template_module="center_chats",
        center_conversations=rows,
        center_unread=sum(int(row.get("unread") or 0) for row in rows),
    )


@panel_user_bp.route("/chats/support", methods=["POST"])
def support_ticket_create():
    if g := _guard():
        return g
    ok, message = _ch.create_support_ticket(request.form.get("message", ""))
    flash(message, "success" if ok else "danger")
    return redirect(url_for("panel_user.chats"))


@panel_user_bp.route("/chats/bug-report", methods=["POST"])
def bug_report_create():
    ok, message, _report_id = _ch.create_bug_report(
        request.form.get("title", ""), request.form.get("details", ""),
        request.form.get("page_path", ""))
    flash(message, "success" if ok else "warning")
    return redirect(url_for("panel_user.chats") + "#bug-report")


@panel_user_bp.route("/wallet")
def wallet():
    return _render("wallet", **(_wl.context() or {}))


@panel_user_bp.route("/wallet/topup", methods=["POST"])
def wallet_topup():
    if g := _guard():
        return g
    from giso.wallet import create_topup_request
    from giso.wallet_receipts import (
        ReceiptValidationError, remove_topup_receipt, save_topup_receipt,
    )
    receipt_path = ""
    try:
        receipt_path = save_topup_receipt(request.files.get("receipt_image"), current_user.id)
    except ReceiptValidationError as exc:
        flash(str(exc), "danger")
        return redirect(url_for("panel_user.wallet", tab="topup"))
    ok, message, _request_id = create_topup_request(
        current_user.id,
        request.form.get("amount", ""),
        request.form.get("payment_reference", ""),
        request.form.get("user_note", ""),
        receipt_path=receipt_path,
    )
    if not ok:
        remove_topup_receipt(receipt_path)
    flash(message, "success" if ok else "danger")
    return redirect(url_for("panel_user.wallet", tab="topup"))


@panel_user_bp.route("/wallet/balepay", methods=["POST"])
def wallet_balepay():
    """§18 پرداخت آنی با بله: ساخت فاکتور و هدایت به ربات بله."""
    if g := _guard():
        return g
    from giso.wallet_balepay import create_invoice
    ok, message, link = create_invoice(
        current_user.id, getattr(current_user, "phone", "") or "", request.form.get("amount", ""))
    if ok and link:
        return redirect(link)
    flash(message, "danger")
    return redirect(url_for("panel_user.wallet", tab="topup"))


@panel_user_bp.route("/wallet/balepay/follow", methods=["POST"])
def wallet_balepay_follow():
    """§18 پیگیری فاکتورهای بلاتکلیف پرداخت بله با inquireTransaction."""
    if g := _guard():
        return g
    from giso.wallet_balepay import follow_pending
    flash(follow_pending(current_user.id), "info")
    return redirect(url_for("panel_user.wallet", tab="topup"))


@panel_user_bp.route("/wallet/withdraw", methods=["POST"])
def wallet_withdraw():
    if g := _guard():
        return g
    from giso.wallet import create_withdrawal_request
    ok, message, _request_id = create_withdrawal_request(
        current_user.id,
        request.form.get("amount", ""),
        request.form.get("card_holder_name", ""),
        request.form.get("sheba", ""),
        request.form.get("card_number", ""),
    )
    flash(message, "success" if ok else "danger")
    return redirect(url_for("panel_user.wallet", tab="settlement"))


@panel_user_bp.route("/notifies")
def notifies():
    return _render("notifies", **(_nt.context() or {}))


@panel_user_bp.route("/profile/clear-logins", methods=["POST"])
def clear_login_history():
    """مورد ۵ help.md: پاک‌کردن لیست ورودها از پروفایل کاربر."""
    g = _guard()
    if g:
        return g
    from giso import login_history
    ok = login_history.clear(int(getattr(current_user, "id", 0) or 0))
    flash("تاریخچهٔ ورودهای شما پاک شد." if ok else "پاک‌کردن تاریخچه ممکن نشد.", "success" if ok else "danger")
    return redirect(url_for("panel_user.profile"))


@panel_user_bp.route("/notifications", methods=["GET", "POST"])
def notifications():
    g = _guard()
    if g:
        return g
    phone = getattr(current_user, "phone", "") or ""
    if request.method == "POST":
        if request.form.get("action") == "clear_read":
            from giso.panel.modules.notifications import delete_read_user_notifications
            n = delete_read_user_notifications(phone)
            flash(f"{n} اعلان خوانده‌شده پاک شد." if n else "اعلان خوانده‌شده‌ای نبود.", "success")
            return redirect(url_for("panel_user.notifications"))
        mark_user_notifications_read(phone, request.form.get("notification_id"))
        if request.form.get("return_to") == "profile":
            return redirect(url_for("panel_user.profile") + "#profile-notifications")
        return redirect(url_for("panel_user.notifications"))
    return _render("notifications", user_notifications=list_user_notifications(phone, limit=100),
                   user_notification_unread=user_unread_count(phone))


@panel_user_bp.route("/wishlist", methods=["GET", "POST"])
def wishlist():
    g = _guard()
    if g:
        return g
    if request.method == "POST":
        try:
            product_id = int(request.form.get("product_id", 0) or 0)
            row = Wishlist.query.filter_by(user_id=current_user.id, product_id=product_id).first()
            if row:
                db.session.delete(row)
            elif product_id:
                db.session.add(Wishlist(user_id=current_user.id, product_id=product_id))
            db.session.commit()
        except Exception:
            db.session.rollback()
        return redirect(url_for("panel_user.wishlist"))
    rows = Wishlist.query.filter_by(user_id=current_user.id).order_by(Wishlist.id.desc()).all()
    return render_template("user_modules/wishlist.html", user=current_user, menu=_menu_for_current_user(), user_module_groups=USER_MODULE_GROUPS,
                           current_module="wishlist", current_module_label="علاقه‌مندی‌ها",
                           current_module_icon="❤️", wishlist=rows)


@panel_user_bp.route("/reviews")
def reviews():

    return _render("reviews", **(_rv.context() or {}))


@panel_user_bp.route("/shop")
def shop():
    g = _guard()
    if g:
        return g
    ensure_shop_template_paths(current_app)
    label, icon = MODULES_META.get("shop", ("فروشگاه من", "🛒"))
    ctx = _shop_user.context() or {}
    phone = getattr(current_user, "phone", "") or ""
    wallet_usable = 0
    try:
        from giso.wallet import get_wallet_balances
        _hdr_uid = int(getattr(current_user, "id", 0) or 0)
        _hdr_bal = {}
        wallet_usable = (get_wallet_balances(_hdr_uid) or {}).get("usable", 0)
        try:
            from giso.wallet_core import grant_initial_spend_credit as _gisc
            if _hdr_uid and _gisc(_hdr_uid):
                wallet_usable = (get_wallet_balances(_hdr_uid) or {}).get("usable", wallet_usable)
            _hdr_bal = get_wallet_balances(_hdr_uid) or {}
        except Exception:
            _hdr_bal = {}
    except Exception:
        wallet_usable = 0
    ctx.update({
        "user": current_user,
        "menu": _menu_for_current_user(),
        "user_module_groups": USER_MODULE_GROUPS,
        "current_module": "shop",
        "current_module_label": label,
        "current_module_icon": icon,
        "user_notifications": list_user_notifications(phone, limit=5),
        "user_notification_unread": user_unread_count(phone),
        "header_wallet_usable": wallet_usable,
        "header_wallet_cash": (_hdr_bal or {}).get("cash", 0),
        "header_wallet_spend": (_hdr_bal or {}).get("spend", 0),
    })
    return render_template("user/shop.html", **ctx)
