# -*- coding: utf-8 -*-
"""Routes for the simplified Giso hair marketplace."""
import hashlib
import html
import logging
from pathlib import Path

from flask import Response, abort, flash, redirect, render_template, request, send_file, url_for
from flask_login import current_user, login_required
from sqlalchemy import or_, and_, case
from sqlalchemy.exc import IntegrityError

from giso.config import Config
from giso.marketplace import marketplace_bp
from giso.marketplace.settings import MARKETPLACE_TERMS_LINES, marketplace_settings
from giso.marketplace.services import (
    LISTING_PUBLIC_STATUSES, OFFER_ACTIVE_STATUSES, LISTING_STATUS_FA, OFFER_STATUS_FA,
    daily_offer_count, ensure_listing_slug, ensure_listing_slugs, format_amount, is_offer_party,
    listing_public_title, listing_expiry_is_active, listing_days_left, LISTING_DURATION_DAYS,
    marketplace_reputation, marketplace_stats, public_listing_note,
    notify_offer_created, notify_offer_status, notify_seller_offer_status,
    notify_listing_status, now_str, parse_amount, refresh_listing_offer_stats,
    refresh_user_rating, seller_public_stats,
)
from giso.models import (
    db, User, HairListing, BuyerProfile, BuyerOffer,
    MarketplaceEventStat, MarketplaceMessage, MarketplaceReview,
)

logger = logging.getLogger("giso_marketplace_routes")
_CHAT_READ_ONLY_STATUSES = ("closed", "paused", "rejected", "withdrawn", "sold")


@marketplace_bp.app_context_processor
def inject_marketplace_policy():
    return {
        "marketplace_policy": marketplace_settings(),
        "marketplace_terms_lines": MARKETPLACE_TERMS_LINES,
    }


@marketplace_bp.before_app_request
def marketplace_global_guards():
    """Enforce marketplace-only consent and extend the existing sitemap."""
    if request.endpoint == "hair_sale" and request.method == "POST":
        sale_path = (request.form.get("sale_path") or "").strip()
        if request.form.get("step") == "2" and sale_path in ("marketplace", "both"):
            if request.form.get("marketplace_terms_accepted") != "1":
                flash("مطالعه و پذیرش قوانین بازارچه برای ثبت آگهی الزامی است.", "warning")
                return redirect(url_for("hair_sale"))
    if request.endpoint == "sitemap_xml":
        return _marketplace_sitemap_response()
    return None


def _marketplace_sitemap_response():
    """Append live marketplace URLs to the existing product sitemap on every request."""
    try:
        from giso.seo_sitemap import read_sitemap_cache
        cached = read_sitemap_cache()
        if cached:
            return Response(cached, mimetype="application/xml; charset=utf-8")
    except Exception:
        pass
    try:
        from giso.shop.routes import sitemap_xml as base_sitemap
        response = base_sitemap()
        if not isinstance(response, Response):
            response = Response(response, mimetype="application/xml; charset=utf-8")
        xml = response.get_data(as_text=True)
    except Exception:
        xml = (
            '<?xml version="1.0" encoding="UTF-8"?>\n'
            '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n</urlset>\n'
        )
        response = Response(xml, mimetype="application/xml; charset=utf-8")

    rows = _public_query().order_by(HairListing.id.asc()).all()
    ensure_listing_slugs(rows)
    public_base = request.host_url.rstrip("/")
    additions = [
        (public_base + "/", "daily", "1.0", ""),
        (public_base + "/hair-sale", "weekly", "0.8", ""),
        (public_base + "/hair-marketplace", "daily", "0.9", ""),
        (url_for("marketplace.mashhad_landing", _external=True), "weekly", "0.85", ""),
    ]
    for listing in rows:
        additions.append((
            url_for("marketplace.listing_slug", slug=listing.slug, _external=True),
            "weekly", "0.75", (listing.updated_at or listing.published_at or "")[:10],
        ))
    blocks = []
    for loc, changefreq, priority, lastmod in additions:
        escaped_loc = html.escape(loc)
        if f"<loc>{escaped_loc}</loc>" in xml:
            continue
        block = f"  <url><loc>{escaped_loc}</loc>"
        if lastmod:
            block += f"<lastmod>{html.escape(lastmod)}</lastmod>"
        block += f"<changefreq>{changefreq}</changefreq><priority>{priority}</priority></url>"
        blocks.append(block)
    marker = "</urlset>"
    payload = "\n".join(blocks) + "\n"
    xml = xml.replace(marker, payload + marker) if marker in xml else xml + payload
    try:
        from giso.seo_sitemap import write_sitemap_cache
        write_sitemap_cache(xml)
    except Exception:
        pass
    response.set_data(xml)
    response.mimetype = "application/xml"
    return response


def _public_query():
    # مهلت ۳۰روزه‌ی نمایش عمومی (هم‌الگوی مرکز زیبایی): ردیف‌هایی که مهلتشان گذشته
    # از فهرست عمومی کنار گذاشته می‌شوند، اما ستون خالی ('' ) یعنی بدون مهلت و همیشه نمایش،
    # تا هیچ آگهی قدیمیِ بدون مهلت به‌ناگهان ناپدید نشود.
    return HairListing.query.filter(
        HairListing.status.in_(LISTING_PUBLIC_STATUSES),
        HairListing.deleted_at == "",
        or_(HairListing.listing_expires_at == "", HairListing.listing_expires_at > now_str()),
    )


def _parse_page():
    try:
        return max(1, int(request.args.get("page", 1) or 1))
    except (TypeError, ValueError):
        return 1


def _listing_detail_url(listing) -> str:
    if not str(getattr(listing, "slug", "") or "").strip():
        ensure_listing_slug(listing)
        db.session.commit()
    return url_for("marketplace.listing_slug", slug=listing.slug)


def _offer_action_redirect(offer, tab="conversations"):
    """Keep new panel forms in the panel while preserving every legacy redirect."""
    if request.form.get("return_to") == "panel":
        return redirect(url_for("panel_user.marketplace", tab=tab))
    return redirect(url_for("marketplace.offer_chat", offer_id=offer.id))


@marketplace_bp.route("/marketplace")
@marketplace_bp.route("/hair-marketplace")
def listings():
    settings = marketplace_settings()
    query = _public_query()
    keyword = (request.args.get("q") or "").strip()[:100]
    if keyword:
        pattern = f"%{keyword}%"
        query = query.filter(or_(
            HairListing.city.ilike(pattern),
            HairListing.region.ilike(pattern),
            HairListing.hair_health.ilike(pattern),
            HairListing.seller_note.ilike(pattern),
        ))
    current = now_str()
    promo_rank = case(
        (and_(HairListing.promotion_type == "featured", HairListing.promotion_expires_at > current), 3),
        (and_(HairListing.promotion_type == "urgent", HairListing.promotion_expires_at > current), 2),
        else_=0,
    )
    query = query.order_by(promo_rank.desc(), HairListing.promotion_bumped_at.desc(), HairListing.published_at.desc(), HairListing.id.desc())
    page = _parse_page()
    per_page = 18
    total = query.count() if settings["enabled"] else 0
    rows = query.offset((page - 1) * per_page).limit(per_page).all() if settings["enabled"] else []
    total_pages = max(1, (total + per_page - 1) // per_page)
    recent_sales = HairListing.query.filter_by(status="sold", deleted_at="").filter(
        HairListing.sold_at != "",
    ).order_by(HairListing.sold_at.desc(), HairListing.id.desc()).limit(6).all() if settings["enabled"] else []
    ensure_listing_slugs(list(rows) + list(recent_sales))
    seller_stats_by_id = {
        seller_id: seller_public_stats(seller_id)
        for seller_id in {row.seller_user_id for row in rows}
    }
    return render_template(
        "marketplace_list.html",
        listings=rows, recent_sales=recent_sales,
        market_stats=marketplace_stats(), settings=settings,
        seller_stats_by_id=seller_stats_by_id,
        listing_status_fa=LISTING_STATUS_FA,
        listing_public_title=listing_public_title,
        fmt_market_amount=format_amount,
        keyword=keyword, page=page, total_pages=total_pages, total=total, now_market=now_str(),
        # SEO: جست‌وجو (keyword) و صفحه‌بندی عمیق (page>1) ایندکس نشوند؛ فقط لیست پایه indexable است.
        noindex=bool(keyword) or page > 1,
    )


@marketplace_bp.route("/hair-marketplace-mashhad")
def mashhad_landing():
    return render_template("hair_marketplace_mashhad.html")


@marketplace_bp.route("/marketplace/seller/<int:seller_id>")
def public_seller_profile(seller_id):
    if not db.session.get(User, seller_id):
        abort(404)
    stats = seller_public_stats(seller_id)
    if not stats["listing_count"]:
        abort(404)
    return render_template("marketplace_seller.html", seller_stats=stats)


@marketplace_bp.route("/marketplace/profile/<int:user_id>")
def public_reputation_profile(user_id):
    if not db.session.get(User, user_id):
        abort(404)
    reputation = marketplace_reputation(user_id)
    if not BuyerProfile.query.filter_by(user_id=user_id).first() and not HairListing.query.filter_by(seller_user_id=user_id).first():
        abort(404)
    seller_reviews = MarketplaceReview.query.filter_by(
        reviewee_user_id=user_id, reviewer_role="buyer", status="visible",
    ).count()
    buyer_reviews = MarketplaceReview.query.filter_by(
        reviewee_user_id=user_id, reviewer_role="seller", status="visible",
    ).count()
    roles = []
    if seller_reviews:
        roles.append("فروشنده")
    if buyer_reviews:
        roles.append("خریدار")
    profile_code = hashlib.sha256(f"giso-market-profile:{user_id}".encode("utf-8")).hexdigest()[:8].upper()
    return render_template(
        "marketplace_detail.html", public_profile=True, listing=None,
        profile_code=profile_code, profile_role_label=" و ".join(roles) or "عضو بازارچه",
        profile_reputation=reputation, settings=marketplace_settings(),
    )


@marketplace_bp.route("/marketplace/media/<int:listing_id>")
def listing_photo(listing_id):
    """سرو امن عکس آگهی با سازگاری مسیرهای قدیمی/منتقل‌شده."""
    listing = HairListing.query.filter_by(id=listing_id, deleted_at="").first_or_404()
    authenticated = bool(getattr(current_user, "is_authenticated", False))
    current_id = getattr(current_user, "id", None) if authenticated else None
    is_owner = bool(authenticated and current_id == listing.seller_user_id)
    is_buyer_party = bool(authenticated and BuyerOffer.query.filter_by(
        listing_id=listing.id, buyer_user_id=current_id,
    ).first())
    if listing.status not in LISTING_PUBLIC_STATUSES and not (is_owner or is_buyer_party):
        abort(404)

    static_root = (Path(Config.GISO_DIR) / "static").resolve()
    raw = str(listing.photo_path or "").strip().replace("\\", "/").lstrip("/")
    for prefix in ("giso/static/", "static/"):
        if raw.startswith(prefix):
            raw = raw[len(prefix):]
    basename = Path(raw).name
    relative_candidates = [raw]
    if basename:
        relative_candidates.extend((
            f"uploads/marketplace/{basename}", f"uploads/{basename}", f"uploads/temp/{basename}",
        ))
    seen = set()
    for relative in relative_candidates:
        if not relative or relative in seen:
            continue
        seen.add(relative)
        candidate = (static_root / relative).resolve()
        if static_root != candidate and static_root not in candidate.parents:
            continue
        if candidate.is_file():
            return send_file(candidate, conditional=True, max_age=3600)
    abort(404)


@marketplace_bp.route("/marketplace/<int:listing_id>")
def listing_detail(listing_id):
    """Legacy numeric URL: preserve compatibility and permanently redirect to canonical slug."""
    listing = HairListing.query.filter_by(id=listing_id, deleted_at="").first_or_404()
    authenticated = bool(getattr(current_user, "is_authenticated", False))
    is_owner = bool(authenticated and current_user.id == listing.seller_user_id)
    if (listing.status not in LISTING_PUBLIC_STATUSES or not listing_expiry_is_active(listing)) and not is_owner:
        abort(404)
    ensure_listing_slug(listing)
    db.session.commit()
    return redirect(url_for("marketplace.listing_slug", slug=listing.slug), code=301)


@marketplace_bp.route("/marketplace/<path:slug>")
def listing_slug(slug):
    listing = HairListing.query.filter_by(slug=slug, deleted_at="").first_or_404()
    return _render_listing_detail(listing)


def _render_listing_detail(listing):
    authenticated = bool(getattr(current_user, "is_authenticated", False))
    is_owner = bool(authenticated and current_user.id == listing.seller_user_id)
    if (listing.status not in LISTING_PUBLIC_STATUSES or not listing_expiry_is_active(listing)) and not is_owner:
        abort(404)
    settings = marketplace_settings()
    if not settings["enabled"] and not is_owner:
        abort(404)
    # برای مالک، آگهی منقضی همچنان باز است اما شمارش بازدید عمومی انجام نمی‌شود.
    listing_expired = not listing_expiry_is_active(listing)
    if not is_owner and listing.status in LISTING_PUBLIC_STATUSES and not listing_expired:
        listing.views_count = int(listing.views_count or 0) + 1
        today = now_str()[:10]
        daily = MarketplaceEventStat.query.filter_by(date=today).first()
        if not daily:
            daily = MarketplaceEventStat(date=today, updated_at=now_str())
            db.session.add(daily)
        daily.views_count = int(daily.views_count or 0) + 1
        daily.updated_at = now_str()
        db.session.commit()
    profile = BuyerProfile.query.filter_by(user_id=current_user.id).first() if authenticated else None
    active_offer = None
    owner_offers = []
    if authenticated:
        active_offer = BuyerOffer.query.filter(
            BuyerOffer.listing_id == listing.id,
            BuyerOffer.buyer_user_id == current_user.id,
            BuyerOffer.status.in_(OFFER_ACTIVE_STATUSES),
        ).first()
        if is_owner:
            owner_offers = BuyerOffer.query.filter_by(listing_id=listing.id).order_by(BuyerOffer.id.desc()).all()
    seller_stats = seller_public_stats(listing.seller_user_id)
    from giso.marketplace.services import buyer_feature_context
    buyer_features = buyer_feature_context(current_user.id) if authenticated and not is_owner else {}
    return render_template(
        "marketplace_detail.html", listing=listing, settings=settings,
        buyer_profile=profile, active_offer=active_offer, owner_offers=owner_offers,
        is_owner=is_owner, seller_stats=seller_stats,
        seller_reputation={"average": seller_stats["average"], "count": seller_stats["rating_count"]},
        listing_status_fa=LISTING_STATUS_FA, offer_status_fa=OFFER_STATUS_FA,
        listing_public_title=listing_public_title,
        public_seller_note=public_listing_note(listing.seller_note), buyer_features=buyer_features,
        listing_expired=listing_expired,
        listing_days_left=max(0, listing_days_left(listing)),
        listing_duration_days=LISTING_DURATION_DAYS,
        listing_renew_nonce=(__import__("uuid").uuid4().hex if is_owner else ""),
        fmt_market_amount=format_amount,
    )


@marketplace_bp.route("/marketplace/seller/promote", methods=["POST"])
@login_required
def seller_promote_selected():
    try: listing_id=int(request.form.get("listing_id") or 0)
    except (TypeError,ValueError): listing_id=0
    if not listing_id:
        flash("آگهی را انتخاب کنید.","warning");return redirect(url_for("panel_user.marketplace",tab="promotion"))
    from giso.marketplace.services import purchase_listing_promotion
    ok,message=purchase_listing_promotion(current_user.id,listing_id,(request.form.get('package_key') or '').strip(),request.form.get('purchase_nonce') or '')
    flash(message,"success" if ok else "warning")
    return redirect(url_for("panel_user.marketplace",tab="promotion"))


@marketplace_bp.route("/marketplace/seller/listings/<int:listing_id>/promote", methods=["POST"])
@login_required
def seller_promote_listing(listing_id):
    from giso.marketplace.services import purchase_listing_promotion
    ok,message=purchase_listing_promotion(current_user.id,listing_id,(request.form.get('package_key') or '').strip(),request.form.get('purchase_nonce') or '')
    flash(message,"success" if ok else "warning")
    return redirect(url_for("panel_user.marketplace",tab="listings"))


@marketplace_bp.route("/marketplace/seller/renew", methods=["POST"])
@login_required
def seller_renew_selected():
    try: listing_id=int(request.form.get("listing_id") or 0)
    except (TypeError,ValueError): listing_id=0
    if not listing_id:
        flash("آگهی را انتخاب کنید.","warning");return redirect(url_for("panel_user.marketplace",tab="promotion"))
    from giso.marketplace.services import renew_listing_promotion
    ok,message=renew_listing_promotion(current_user.id,listing_id,request.form.get('purchase_nonce') or '')
    flash(message,"success" if ok else "warning")
    return redirect(url_for("panel_user.marketplace",tab="promotion"))


@marketplace_bp.route("/marketplace/seller/listings/<int:listing_id>/renew", methods=["POST"])
@login_required
def seller_renew_listing(listing_id):
    from giso.marketplace.services import renew_listing_promotion
    ok,message=renew_listing_promotion(current_user.id,listing_id,request.form.get('purchase_nonce') or '')
    flash(message,"success" if ok else "warning")
    return redirect(url_for("panel_user.marketplace",tab="listings"))


@marketplace_bp.route("/dashboard/hair/buyer-features/alert", methods=["POST"])
@login_required
def buyer_feature_alert():
    from giso.marketplace.services import purchase_buyer_alert
    ok, message = purchase_buyer_alert(current_user.id, request.form)
    flash(message, "success" if ok else "warning")
    return redirect(url_for("panel_user.buyer_request", tab="features"))


@marketplace_bp.route("/dashboard/hair/buyer-features/alert/<int:alert_id>/disable", methods=["POST"])
@login_required
def buyer_feature_alert_disable(alert_id):
    from giso.base import get_giso_db_conn
    with get_giso_db_conn() as conn:
        cur=conn.execute("UPDATE marketplace_buyer_alerts SET is_active=0 WHERE id=? AND user_id=?",(int(alert_id),int(current_user.id)));conn.commit()
    flash("اعلان هوشمند غیرفعال شد." if cur.rowcount else "اعلان پیدا نشد.","success" if cur.rowcount else "warning")
    return redirect(url_for("panel_user.buyer_request",tab="features"))


@marketplace_bp.route("/dashboard/hair/buyer-features/bonus", methods=["POST"])
@login_required
def buyer_feature_bonus():
    from giso.marketplace.services import purchase_offer_bonus
    ok, message = purchase_offer_bonus(current_user.id,request.form.get('purchase_nonce') or '')
    flash(message, "success" if ok else "warning")
    return redirect(url_for("panel_user.buyer_request", tab="features"))


@marketplace_bp.route("/marketplace/<int:listing_id>/offer", methods=["POST"])
@login_required
def create_offer(listing_id):
    settings = marketplace_settings()
    if not settings["enabled"]:
        flash("بازارچه موقتاً غیرفعال است.", "warning")
        return redirect(url_for("marketplace.listings"))
    listing = HairListing.query.filter_by(id=listing_id, deleted_at="").first_or_404()
    if listing.status not in LISTING_PUBLIC_STATUSES or not listing_expiry_is_active(listing):
        flash("این آگهی در حال حاضر پیشنهاد جدید نمی‌پذیرد.", "warning")
        return redirect(_listing_detail_url(listing))
    if listing.seller_user_id == current_user.id:
        flash("برای آگهی خودتان نمی‌توانید پیشنهاد ثبت کنید.", "warning")
        return redirect(_listing_detail_url(listing))

    amount = parse_amount(request.form.get("offer_amount"))
    note = (request.form.get("offer_note") or "").strip()[:500]
    if amount <= 0:
        flash("مبلغ پیشنهاد معتبر نیست.", "danger")
        return redirect(_listing_detail_url(listing))

    profile = BuyerProfile.query.filter_by(user_id=current_user.id).first()
    if not profile or profile.verification_status != "verified":
        flash("برای ثبت پیشنهاد، ابتدا درخواست خرید مو را از بخش بازارچه پنل ثبت و تأیید کنید.", "warning")
        return redirect(url_for("panel_user.marketplace", tab="buyer-request"))

    active = BuyerOffer.query.filter(
        BuyerOffer.listing_id == listing.id,
        BuyerOffer.buyer_user_id == current_user.id,
        BuyerOffer.status.in_(OFFER_ACTIVE_STATUSES),
    ).first()
    if active:
        flash("شما برای این آگهی یک پیشنهاد فعال دارید.", "warning")
        return redirect(_listing_detail_url(listing))
    from giso.marketplace.services import buyer_feature_context
    feature_state = buyer_feature_context(current_user.id)
    if daily_offer_count(current_user.id) >= feature_state["buyer_offer_limit"]:
        flash("سقف پیشنهادهای ۲۴ ساعت اخیر شما تکمیل شده است؛ از تب امکانات خریدار می‌توانید بسته ۵ پیشنهاد اضافه فعال کنید.", "warning")
        return redirect(_listing_detail_url(listing))

    try:
        offer = BuyerOffer(
            listing_id=listing.id,
            buyer_user_id=current_user.id,
            buyer_profile_id=profile.id,
            device_id=None,
            offer_amount=amount,
            offer_note=note,
            status="pending",
            risk_snapshot="",  # legacy column retained; active risk snapshots are disabled
            created_at=now_str(), updated_at=now_str(),
        )
        db.session.add(offer)
        db.session.commit()
        refresh_listing_offer_stats(listing.id)
        notify_offer_created(offer, listing)
        flash("پیشنهاد شما مستقیماً برای فروشنده ثبت شد.", "success")
    except IntegrityError:
        db.session.rollback()
        flash("پیشنهاد ثبت نشد؛ ممکن است پیشنهاد فعال دیگری داشته باشید.", "danger")
    except Exception as exc:
        db.session.rollback()
        logger.warning("create marketplace offer failed: %s", exc.__class__.__name__)
        flash("پیشنهاد ثبت نشد؛ لطفاً دوباره تلاش کنید.", "danger")
    return redirect(_listing_detail_url(listing))


@marketplace_bp.route("/marketplace/seller/offers/<int:offer_id>/respond", methods=["POST"])
@login_required
def seller_respond_offer(offer_id):
    offer = BuyerOffer.query.get_or_404(offer_id)
    listing = HairListing.query.filter_by(id=offer.listing_id, deleted_at="").first_or_404()
    if listing.seller_user_id != current_user.id:
        abort(403)
    if listing.status in ("rejected", "closed", "withdrawn", "sold"):
        flash("این آگهی بسته است و پاسخ جدیدی ثبت نمی‌شود.", "warning")
        return redirect(url_for("panel_user.marketplace", tab="listings"))
    if offer.status != "pending":
        flash("این پیشنهاد دیگر قابل تغییر نیست.", "warning")
        return redirect(url_for("panel_user.marketplace", tab="listings"))
    action = (request.form.get("action") or "").strip()
    note = (request.form.get("seller_response_note") or "").strip()[:500]
    stamp = now_str()
    if action == "accept":
        offer.status = "accepted"
        offer.accepted_at = stamp
        offer.seller_response_note = note
        if listing.status in LISTING_PUBLIC_STATUSES:
            listing.status = "negotiating"
    elif action == "reject":
        offer.status = "rejected"
        offer.rejected_at = stamp
        offer.seller_response_note = note
    elif action == "counter":
        counter = parse_amount(request.form.get("seller_counter_amount"))
        if counter <= 0:
            flash("مبلغ قیمت متقابل معتبر نیست.", "danger")
            return redirect(url_for("panel_user.marketplace", tab="listings"))
        offer.status = "countered"
        offer.seller_counter_amount = counter
        offer.seller_response_note = note
    else:
        abort(400)
    offer.updated_at = stamp
    listing.updated_at = stamp
    db.session.commit()
    refresh_listing_offer_stats(listing.id)
    notify_offer_status(offer)
    flash("پاسخ شما ثبت شد.", "success")
    return redirect(url_for("panel_user.marketplace", tab="listings"))


@marketplace_bp.route("/marketplace/offers/<int:offer_id>/buyer-response", methods=["POST"])
@login_required
def buyer_respond_counter(offer_id):
    offer = BuyerOffer.query.get_or_404(offer_id)
    if offer.buyer_user_id != current_user.id:
        abort(403)
    if offer.status != "countered":
        flash("این پیشنهاد قیمت متقابل فعالی ندارد.", "warning")
        return redirect(url_for("panel_user.marketplace", tab="offers"))
    action = (request.form.get("action") or "").strip()
    listing = HairListing.query.filter_by(id=offer.listing_id, deleted_at="").first_or_404()
    if listing.status in ("rejected", "closed", "withdrawn", "sold"):
        flash("این آگهی بسته است و پاسخ جدیدی ثبت نمی‌شود.", "warning")
        return redirect(url_for("panel_user.marketplace", tab="offers"))
    if action == "accept":
        offer.status = "accepted"
        offer.accepted_at = now_str()
        if listing.status in LISTING_PUBLIC_STATUSES:
            listing.status = "negotiating"
    elif action == "reject":
        offer.status = "rejected"
        offer.rejected_at = now_str()
    else:
        abort(400)
    offer.updated_at = now_str()
    listing.updated_at = now_str()
    db.session.commit()
    refresh_listing_offer_stats(listing.id)
    notify_seller_offer_status(offer, title="پاسخ خریدار به قیمت متقابل")
    flash("پاسخ شما ثبت شد.", "success")
    return redirect(url_for("panel_user.marketplace", tab="offers"))


@marketplace_bp.route("/marketplace/offers/<int:offer_id>/withdraw", methods=["POST"])
@login_required
def withdraw_offer(offer_id):
    offer = BuyerOffer.query.get_or_404(offer_id)
    HairListing.query.filter_by(id=offer.listing_id, deleted_at="").first_or_404()
    if offer.buyer_user_id != current_user.id:
        abort(403)
    if offer.status not in ("pending", "countered"):
        flash("این پیشنهاد قابل پس‌گرفتن نیست.", "warning")
    else:
        offer.status = "withdrawn"
        offer.updated_at = now_str()
        db.session.commit()
        refresh_listing_offer_stats(offer.listing_id)
        notify_seller_offer_status(offer, title="پس‌گرفتن پیشنهاد توسط خریدار")
        flash("پیشنهاد پس گرفته شد.", "success")
    return redirect(url_for("panel_user.marketplace", tab="offers"))


@marketplace_bp.route("/marketplace/seller/listings/<int:listing_id>/status", methods=["POST"])
@login_required
def seller_listing_status(listing_id):
    listing = HairListing.query.filter_by(id=listing_id, deleted_at="").first_or_404()
    if listing.seller_user_id != current_user.id:
        abort(403)
    action = (request.form.get("action") or "").strip()
    success_message = "وضعیت آگهی به‌روزرسانی شد."
    if action == "pause" and listing.status in LISTING_PUBLIC_STATUSES:
        listing.status = "paused"
    elif action == "resume" and listing.status == "paused":
        listing.status = "published"
    elif action == "close" and listing.status not in ("closed", "withdrawn", "sold"):
        listing.status = "closed"
    elif action == "withdraw" and listing.status == "pending_review":
        listing.status = "withdrawn"
    elif action == "edit" and listing.status != "sold":
        if int(listing.edit_count or 0) >= 2:
            flash("سقف دو بار ویرایش اطلاعات این آگهی استفاده شده است.", "warning")
            return redirect(url_for("panel_user.marketplace", tab="listings"))
        has_active_offer = BuyerOffer.query.filter(BuyerOffer.listing_id==listing.id, BuyerOffer.status.in_(OFFER_ACTIVE_STATUSES)).first()
        if has_active_offer:
            flash("تا زمانی که پیشنهاد فعال وجود دارد، اطلاعات آگهی قابل ویرایش نیست.", "warning")
            return redirect(url_for("panel_user.marketplace", tab="listings"))
        asking_price = parse_amount(request.form.get("seller_asking_price"))
        if asking_price <= 0:
            flash("قیمت مدنظر فروشنده معتبر نیست.", "warning")
            return redirect(url_for("panel_user.marketplace", tab="listings"))
        listing.seller_asking_price = asking_price
        listing.seller_note = (request.form.get("seller_note") or "").strip()[:500]
        listing.city = (request.form.get("city") or listing.city or "").strip()[:100]
        listing.edit_count = int(listing.edit_count or 0) + 1
        if listing.status in ("rejected", "published", "negotiating"):
            listing.status = "pending_review"
            listing.reject_reason = ""
            success_message = "اصلاحات ذخیره و آگهی دوباره برای بررسی ارسال شد."
        else:
            success_message = "اطلاعات قابل‌ویرایش آگهی ذخیره شد."
        try:
            from giso.security import audit_event
            audit_event("marketplace_listing_user_edit", "success", target=str(listing.id), details=f"edit_count={listing.edit_count}")
        except Exception: pass
    elif action == "delete" and listing.status in ("pending_review", "published", "negotiating", "paused", "closed", "withdrawn", "rejected"):
        has_active_offer = BuyerOffer.query.filter(
            BuyerOffer.listing_id == listing.id,
            BuyerOffer.status.in_(OFFER_ACTIVE_STATUSES),
        ).first()
        if has_active_offer:
            flash("تا زمانی که پیشنهاد فعال وجود دارد، حذف آگهی مجاز نیست.", "warning")
            return redirect(url_for("panel_user.marketplace", tab="listings"))
        listing.deleted_at = now_str()
        success_message = "آگهی از پنل شما حذف شد."
    else:
        flash("این تغییر وضعیت مجاز نیست.", "warning")
        return redirect(url_for("panel_user.marketplace", tab="listings"))
    listing.updated_at = now_str()
    db.session.commit()
    flash(success_message, "success")
    return redirect(url_for("panel_user.marketplace", tab="listings"))


@marketplace_bp.route("/marketplace/offers/<int:offer_id>/sold", methods=["POST"])
@login_required
def complete_offer(offer_id):
    """A single seller click records a successful sale; no buyer confirmation exists."""
    offer = BuyerOffer.query.get_or_404(offer_id)
    listing = HairListing.query.filter_by(id=offer.listing_id, deleted_at="").first_or_404()
    if listing.seller_user_id != current_user.id:
        abort(403)
    if offer.status == "sold" and listing.status == "sold":
        return _offer_action_redirect(offer, tab="successful")
    if offer.status != "accepted" or listing.status in ("rejected", "withdrawn", "sold"):
        flash("فقط پیشنهاد پذیرفته‌شده را می‌توان فروش موفق ثبت کرد.", "warning")
        return _offer_action_redirect(offer)

    stamp = now_str()
    offer.status = "sold"
    offer.sold_at = stamp
    offer.updated_at = stamp
    offer.chat_closed = 1
    offer.chat_closed_at = stamp
    offer.chat_closed_by_user_id = current_user.id
    listing.status = "sold"
    listing.sold_at = stamp
    listing.sold_offer_id = offer.id
    listing.updated_at = stamp
    other_offers = BuyerOffer.query.filter(
        BuyerOffer.listing_id == listing.id,
        BuyerOffer.id != offer.id,
        BuyerOffer.status.in_(("pending", "countered", "accepted")),
    ).all()
    for other in other_offers:
        other.status = "expired"
        other.updated_at = stamp
        other.chat_closed = 1
        other.chat_closed_at = stamp
        other.chat_closed_by_user_id = current_user.id
    db.session.commit()
    for other in other_offers:
        notify_offer_status(other, title="پایان دریافت پیشنهاد برای آگهی")
    notify_offer_status(offer, title="فروش موفق بازارچه")
    notify_seller_offer_status(offer, title="فروش موفق بازارچه")
    flash("فروش موفق ثبت شد و امتیازدهی ستاره‌ای برای دو طرف فعال است.", "success")
    return _offer_action_redirect(offer, tab="successful")


@marketplace_bp.route("/marketplace/offers/<int:offer_id>/review", methods=["POST"])
@login_required
def submit_review(offer_id):
    offer = BuyerOffer.query.get_or_404(offer_id)
    listing = HairListing.query.filter_by(id=offer.listing_id, deleted_at="").first_or_404()
    if not is_offer_party(offer, current_user.id):
        abort(403)
    if not (offer.status == "sold" or offer.chat_closed):
        flash("امتیازدهی پس از فروش موفق یا بستن گفتگو فعال می‌شود.", "warning")
        return redirect(url_for("marketplace.offer_chat", offer_id=offer.id))
    try:
        rating = int(request.form.get("rating") or 0)
    except (TypeError, ValueError):
        rating = 0
    if rating not in (1, 2, 3, 4, 5):
        flash("امتیاز باید بین ۱ تا ۵ ستاره باشد.", "warning")
        return redirect(url_for("marketplace.offer_chat", offer_id=offer.id))
    if MarketplaceReview.query.filter_by(offer_id=offer.id, reviewer_user_id=current_user.id).first():
        flash("امتیاز شما قبلاً ثبت شده است.", "info")
        return redirect(url_for("marketplace.offer_chat", offer_id=offer.id))
    reviewer_is_seller = current_user.id == listing.seller_user_id
    review = MarketplaceReview(
        listing_id=listing.id, offer_id=offer.id,
        reviewer_user_id=current_user.id,
        reviewee_user_id=offer.buyer_user_id if reviewer_is_seller else listing.seller_user_id,
        reviewer_role="seller" if reviewer_is_seller else "buyer",
        rating=rating, comment="", status="visible", created_at=now_str(),
    )
    db.session.add(review)
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        flash("امتیاز شما قبلاً ثبت شده است.", "info")
        return redirect(url_for("marketplace.offer_chat", offer_id=offer.id))
    refresh_user_rating(review.reviewee_user_id)
    try:
        from giso.wallet import complete_mission
        complete_mission(current_user.id, "review_submit", event_key=f"market-review:{review.id}")
    except Exception:
        pass
    flash("امتیاز ستاره‌ای شما به‌صورت ناشناس ثبت شد.", "success")
    return redirect(url_for("marketplace.offer_chat", offer_id=offer.id))


@marketplace_bp.route("/marketplace/offers/<int:offer_id>/chat/close", methods=["POST"])
@login_required
def close_offer_chat(offer_id):
    offer = BuyerOffer.query.get_or_404(offer_id)
    HairListing.query.filter_by(id=offer.listing_id, deleted_at="").first_or_404()
    if not is_offer_party(offer, current_user.id):
        abort(403)
    if offer.status not in ("accepted", "sold"):
        flash("این گفتگو قابل بستن نیست.", "warning")
        return _offer_action_redirect(offer)
    if not offer.chat_closed:
        offer.chat_closed = 1
        offer.chat_closed_at = now_str()
        offer.chat_closed_by_user_id = current_user.id
        offer.updated_at = now_str()
        db.session.commit()
        flash("گفتگو بسته شد و امتیازدهی ستاره‌ای برای دو طرف فعال است.", "success")
    else:
        flash("این گفتگو قبلاً بسته شده است.", "info")
    return _offer_action_redirect(offer)


@marketplace_bp.route("/marketplace/offers/<int:offer_id>/chat", methods=["GET", "POST"])
@login_required
def offer_chat(offer_id):
    offer = BuyerOffer.query.get_or_404(offer_id)
    listing = HairListing.query.filter_by(id=offer.listing_id, deleted_at="").first_or_404()
    if not is_offer_party(offer, current_user.id):
        abort(403)
    if offer.status not in ("pending", "countered", "accepted", "sold") and not offer.chat_closed:
        flash("این پیشنهاد امکان گفتگو ندارد.", "warning")
        return redirect(url_for("panel_user.marketplace"))
    settings = marketplace_settings()
    chat_read_only = bool(offer.chat_closed) or offer.status == "sold" or listing.status in _CHAT_READ_ONLY_STATUSES
    if offer.status == "sold" or listing.status == "sold":
        read_only_reason = "فروش موفق ثبت شده و گفتگو برای حفظ تاریخچه فقط‌خواندنی است."
    elif offer.chat_closed:
        read_only_reason = "این گفتگو توسط یکی از طرفین بسته شده است."
    else:
        read_only_reason = f"وضعیت آگهی «{LISTING_STATUS_FA.get(listing.status, listing.status)}» است."

    if request.method == "POST":
        if chat_read_only:
            flash("گفتگو بسته است و فقط تاریخچه آن قابل مشاهده است.", "warning")
            return redirect(url_for("marketplace.offer_chat", offer_id=offer.id))
        if not settings["chat_enabled"]:
            flash("ارسال پیام بازارچه موقتاً غیرفعال است.", "warning")
            return redirect(url_for("marketplace.offer_chat", offer_id=offer.id))
        text = (request.form.get("message_text") or "").strip()[:1000]
        if not text:
            flash("متن پیام خالی است.", "warning")
        else:
            role = "seller" if current_user.id == listing.seller_user_id else "buyer"
            db.session.add(MarketplaceMessage(
                offer_id=offer.id, sender_user_id=current_user.id,
                sender_role=role, message_text=text, created_at=now_str(),
            ))
            db.session.commit()
        return redirect(url_for("marketplace.offer_chat", offer_id=offer.id))

    reviewed = MarketplaceReview.query.filter_by(
        offer_id=offer.id, reviewer_user_id=current_user.id,
    ).first()
    rating_pending = bool((offer.status == "sold" or offer.chat_closed) and not reviewed)
    messages = MarketplaceMessage.query.filter_by(offer_id=offer.id).order_by(MarketplaceMessage.id.asc()).all()
    return render_template(
        "marketplace_chat.html", listing=listing, offer=offer, messages=messages,
        settings=settings, chat_read_only=chat_read_only,
        chat_read_only_reason=read_only_reason,
        is_seller=current_user.id == listing.seller_user_id,
        rating_pending=rating_pending, reviewed=bool(reviewed),
        listing_status_fa=LISTING_STATUS_FA, fmt_market_amount=format_amount,
    )
