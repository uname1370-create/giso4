# -*- coding: utf-8 -*-
"""مدیریت بازارچه و داشبورد آماری حریم‌خصوصی‌محور سوپرادمین."""
from datetime import datetime, timedelta

from flask import abort, flash, redirect, request, url_for
from sqlalchemy import or_

from giso.marketplace.settings import marketplace_settings, save_marketplace_settings
from giso.marketplace.services import (
    LISTING_PUBLIC_STATUSES, LISTING_STATUS_FA, OFFER_STATUS_FA,
    ensure_listing_slug, format_amount, marketplace_reputation, now_str,
    notify_buyer_profile_status, notify_listing_status, refresh_user_rating,
    seller_public_code,
)
from giso.models import (
    db, User, HairListing, BuyerProfile, BuyerOffer, MarketplaceMessage,
    MarketplaceReview, MarketplaceEventStat, ListingReport,
)
from giso.panel.permissions import current_role_and_perms


def _set_listing_expiry_on_publish(listing):
    """Start the 30-day public-display window when an ad first goes public.

    Preserves an existing/future deadline (renewals) and never overrides it on a
    simple status toggle. Safe no-op if the column is missing on a legacy DB.
    """
    try:
        if str(getattr(listing, "listing_expires_at", "") or "").strip():
            return
        from giso.marketplace.services import LISTING_DURATION_DAYS
        listing.listing_expires_at = (
            datetime.now() + timedelta(days=int(LISTING_DURATION_DAYS))
        ).strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        pass


def _seven_day_chart():
    today = datetime.now().date()
    labels = []
    listings = []
    offers = []
    deals = []
    for offset in range(6, -1, -1):
        day = today - timedelta(days=offset)
        prefix = day.isoformat()
        labels.append(prefix)
        listings.append(HairListing.query.filter(HairListing.created_at.startswith(prefix)).count())
        offers.append(BuyerOffer.query.filter(BuyerOffer.created_at.startswith(prefix)).count())
        deals.append(BuyerOffer.query.filter(
            BuyerOffer.status == "sold", BuyerOffer.sold_at.startswith(prefix),
        ).count())
    return {"labels": labels, "listings": listings, "offers": offers, "deals": deals}


def _buyer_admin_details(profiles):
    user_ids = [row.user_id for row in profiles]
    offers = (
        BuyerOffer.query.filter(BuyerOffer.buyer_user_id.in_(user_ids))
        .order_by(BuyerOffer.id.desc()).all()
        if user_ids else []
    )
    grouped = {user_id: [] for user_id in user_ids}
    for offer in offers:
        grouped.setdefault(offer.buyer_user_id, []).append(offer)
    details = {}
    for profile in profiles:
        rows = grouped.get(profile.user_id, [])
        counts = {status: 0 for status in OFFER_STATUS_FA}
        for offer in rows:
            counts[offer.status] = counts.get(offer.status, 0) + 1
        details[profile.id] = {
            "code": seller_public_code(profile.user_id),
            "offers": rows,
            "offer_count": len(rows),
            "offer_total": sum(int(row.offer_amount or 0) for row in rows),
            "status_counts": counts,
            "reputation": marketplace_reputation(profile.user_id),
        }
    return details


def _status_monitor_data():
    """پایش وضعیت آگهی‌ها: آگهی‌های منتشرشده/مذاکره/بسته/ردشده + پیشنهادها + خلاصه چت."""
    listings = HairListing.query.filter(
        HairListing.deleted_at == "",
        HairListing.status.in_(("published", "negotiating", "closed", "rejected")),
    ).order_by(HairListing.id.desc()).limit(200).all()
    if not listings:
        return []
    listing_ids = [row.id for row in listings]
    offers = BuyerOffer.query.filter(
        BuyerOffer.listing_id.in_(listing_ids),
    ).order_by(BuyerOffer.id.desc()).all()
    offers_by_listing = {lid: [] for lid in listing_ids}
    for offer in offers:
        offers_by_listing.setdefault(offer.listing_id, []).append(offer)
    offer_listing_map = {offer.id: offer.listing_id for offer in offers}
    buyer_ids = {offer.buyer_user_id for offer in offers}
    buyers = {u.id: u for u in User.query.filter(User.id.in_(buyer_ids)).all()} if buyer_ids else {}
    chat_by_listing = {lid: {"count": 0, "last": None} for lid in listing_ids}
    if offers:
        messages = MarketplaceMessage.query.filter(
            MarketplaceMessage.offer_id.in_([offer.id for offer in offers]),
        ).order_by(MarketplaceMessage.id.desc()).all()
        for m in messages:
            lid = offer_listing_map.get(m.offer_id)
            if lid is None:
                continue
            entry = chat_by_listing.setdefault(lid, {"count": 0, "last": None})
            entry["count"] += 1
            if entry["last"] is None:
                entry["last"] = m
    out = []
    for listing in listings:
        out.append({
            "listing": listing,
            "seller_code": seller_public_code(listing.seller_user_id),
            "offers": offers_by_listing.get(listing.id, []),
            "buyers": buyers,
            "chat_count": chat_by_listing.get(listing.id, {}).get("count", 0),
            "last_message": chat_by_listing.get(listing.id, {}).get("last"),
        })
    return out


def context():
    role, _perms, _bid = current_role_and_perms()
    is_super = role == "super"
    default_tab = "dashboard" if is_super else "listings"
    tab = (request.args.get("tab") or default_tab).strip()
    valid_tabs = {"dashboard", "listings", "status", "buyers", "reviews", "credits", "settings"} if is_super else {"listings", "status", "buyers", "reports"}
    if tab not in valid_tabs:
        tab = default_tab
    status_monitor = _status_monitor_data() if tab == "status" else []
    status = (request.args.get("status") or "all").strip()
    keyword = (request.args.get("q") or "").strip()[:100]
    query = HairListing.query.filter(HairListing.deleted_at == "")
    if status in LISTING_STATUS_FA:
        query = query.filter_by(status=status)
    else:
        status = "all"
    if keyword:
        pattern = f"%{keyword}%"
        query = query.filter(or_(
            HairListing.city.ilike(pattern),
            HairListing.region.ilike(pattern),
            HairListing.seller_note.ilike(pattern),
            HairListing.admin_note.ilike(pattern),
        ))
    listings = query.order_by(HairListing.id.desc()).limit(200).all()
    profiles = BuyerProfile.query.order_by(BuyerProfile.id.desc()).limit(200).all()
    reviews = MarketplaceReview.query.order_by(MarketplaceReview.id.desc()).limit(250).all() if is_super else []
    listing_reports = (ListingReport.query.order_by(ListingReport.id.desc()).limit(250).all()
                       if not is_super else [])

    dashboard = {}
    recent_conversations = []
    recent_deals = []
    dashboard_listing_map = {}
    if is_super:
        today = datetime.now().date().isoformat()
        all_listings = HairListing.query.filter(HairListing.deleted_at == "")
        recent_conversations = BuyerOffer.query.filter(or_(
            BuyerOffer.status.in_(("accepted", "sold")), BuyerOffer.chat_closed == 1,
        )).order_by(BuyerOffer.updated_at.desc(), BuyerOffer.id.desc()).limit(5).all()
        recent_deals = BuyerOffer.query.filter_by(status="sold").order_by(
            BuyerOffer.sold_at.desc(), BuyerOffer.id.desc(),
        ).limit(5).all()
        dashboard_listing_ids = {
            row.listing_id for row in recent_conversations + recent_deals
        }
        dashboard_listing_map = {
            row.id: row for row in HairListing.query.filter(HairListing.id.in_(dashboard_listing_ids)).all()
        } if dashboard_listing_ids else {}
        latest_message = {}
        conversation_ids = [row.id for row in recent_conversations]
        if conversation_ids:
            for message in MarketplaceMessage.query.filter(
                MarketplaceMessage.offer_id.in_(conversation_ids),
            ).order_by(MarketplaceMessage.id.desc()).all():
                latest_message.setdefault(message.offer_id, message)
        event_today = MarketplaceEventStat.query.filter_by(date=today).first()
        dashboard = {
            "total_listings": all_listings.count(),
            "pending_listings_count": all_listings.filter_by(status="pending_review").count(),
            "total_buyers": BuyerProfile.query.count(),
            "successful_deals": BuyerOffer.query.filter_by(status="sold").count(),
            "active_sellers": db.session.query(HairListing.seller_user_id).filter(
                HairListing.deleted_at == "", HairListing.status.in_(LISTING_PUBLIC_STATUSES),
            ).distinct().count(),
            "today_offers": BuyerOffer.query.filter(BuyerOffer.created_at.startswith(today)).count(),
            "open_chats": BuyerOffer.query.filter_by(status="accepted", chat_closed=0).count(),
            "today_views": int(event_today.views_count or 0) if event_today else 0,
            "chart": _seven_day_chart(),
            "pending_listings": all_listings.filter_by(status="pending_review").order_by(
                HairListing.id.desc(),
            ).limit(5).all(),
            "pending_buyers": BuyerProfile.query.filter_by(verification_status="pending").order_by(
                BuyerProfile.id.desc(),
            ).limit(5).all(),
            "recent_conversations": recent_conversations,
            "recent_conversation_messages": latest_message,
            "recent_deals": recent_deals,
        }

    user_ids = {row.seller_user_id for row in listings}
    user_ids.update(row.user_id for row in profiles)
    user_ids.update(row.seller_user_id for row in dashboard.get("pending_listings", []))
    users_by_id = {
        row.id: row for row in User.query.filter(User.id.in_(user_ids)).all()
    } if user_ids else {}
    buyer_details = _buyer_admin_details(profiles)
    buyer_offer_listing_ids = {
        offer.listing_id for detail in buyer_details.values() for offer in detail["offers"]
    }
    buyer_offer_listings = {
        row.id: row for row in HairListing.query.filter(HairListing.id.in_(buyer_offer_listing_ids)).all()
    } if buyer_offer_listing_ids else {}

    return {
        "market_tab": tab,
        "market_status": status,
        "market_keyword": keyword,
        "market_listings": listings,
        "status_monitor": status_monitor,
        "buyer_profiles": profiles,
        "buyer_admin_details": buyer_details,
        "buyer_offer_listings": buyer_offer_listings,
        "market_reviews": reviews,
        "market_reports": listing_reports,
        "market_users_by_id": users_by_id,
        "market_dashboard": dashboard,
        "dashboard_listing_map": dashboard_listing_map,
        "market_settings": marketplace_settings(),
        "listing_status_fa": LISTING_STATUS_FA,
        "offer_status_fa": OFFER_STATUS_FA,
        "fmt_market_amount": format_amount,
        "is_super": is_super,
    }


def handle_listing_action(listing_id):
    """عملیات مدیریت آگهی — برای سوپرادمین و ادمین عادی یکسان (فاز یکپارچه‌سازی)."""
    listing = HairListing.query.filter_by(id=listing_id, deleted_at="").first_or_404()
    was_published = listing.status in ("published", "negotiating")
    action = (request.form.get("action") or "").strip()
    note = (request.form.get("admin_note") or "").strip()[:1000]
    reason = (request.form.get("reject_reason") or "").strip()[:1000]
    target_tab = (request.form.get("back_tab") or request.form.get("back_status") or "listings").strip()

    if action == "approve" and listing.status in ("pending_review", "rejected", "paused"):
        listing.status = "published"
        listing.published_at = listing.published_at or now_str()
        listing.reject_reason = ""
        _set_listing_expiry_on_publish(listing)
        ensure_listing_slug(listing)
    elif action == "reject" and listing.status in ("pending_review", "published", "negotiating", "paused", "closed"):
        listing.status = "rejected"
        listing.reject_reason = reason or "آگهی با قوانین بازارچه مطابقت ندارد."
    elif action == "pause" and listing.status in ("published", "negotiating"):
        listing.status = "paused"
    elif action == "close" and listing.status not in ("sold", "closed", "withdrawn"):
        listing.status = "closed"
    elif action == "status_change":
        # تغییر وضعیت از طریق dropdown (منتشر شده / رد شده / بسته شده)
        new_status = (request.form.get("status") or "").strip()
        if new_status == "published" and listing.status not in ("sold", "withdrawn"):
            listing.status = "published"
            listing.published_at = listing.published_at or now_str()
            listing.reject_reason = ""
            _set_listing_expiry_on_publish(listing)
        elif new_status == "rejected" and listing.status not in ("sold", "withdrawn"):
            listing.status = "rejected"
            listing.reject_reason = reason or listing.reject_reason or "آگهی با قوانین بازارچه مطابقت ندارد."
        elif new_status == "closed" and listing.status not in ("sold", "closed", "withdrawn"):
            listing.status = "closed"
        else:
            flash("وضعیت انتخاب‌شده برای این آگهی مجاز نیست.", "warning")
            return redirect(url_for("panel.marketplace", tab="listings"))
    elif action in ("delete_ad", "delete"):
        has_active = BuyerOffer.query.filter(
            BuyerOffer.listing_id == listing.id,
            BuyerOffer.status.in_(("pending", "countered", "accepted")),
        ).first()
        if has_active:
            flash("تا زمانی که پیشنهاد فعال وجود دارد، حذف آگهی مجاز نیست.", "warning")
            return redirect(url_for("panel.marketplace", tab="listings"))
        listing.deleted_at = now_str()
        db.session.commit()
        flash("آگهی حذف شد.", "success")
        return redirect(url_for("panel.marketplace", tab=target_tab if target_tab in ("listings", "status") else "listings"))
    else:
        flash("این تغییر وضعیت برای آگهی مجاز نیست.", "warning")
        return redirect(url_for("panel.marketplace", tab="listings"))
    listing.admin_note = note or listing.admin_note
    listing.updated_at = now_str()
    db.session.commit()
    notify_listing_status(listing)
    if not was_published and listing.status == "published":
        try:
            from giso.marketplace.services import notify_matching_buyer_alerts
            notify_matching_buyer_alerts(listing)
        except Exception:
            pass
    flash("وضعیت آگهی به‌روزرسانی شد.", "success")
    return redirect(url_for("panel.marketplace", tab=target_tab if target_tab in ("listings", "status") else "listings",
                            status=request.form.get("back_status", "all")))


def handle_report_action(report_id):
    """Normal-admin report triage; keep the legacy superadmin response unchanged."""
    role, _perms, _bid = current_role_and_perms()
    if role == "super":
        abort(404)
    report = ListingReport.query.get_or_404(report_id)
    action = (request.form.get("action") or "").strip()
    if action not in ("resolve", "dismiss", "reopen"):
        flash("عملیات گزارش نامعتبر است.", "warning")
        return redirect(url_for("panel.marketplace", tab="reports"))
    report.status = {"resolve": "resolved", "dismiss": "dismissed", "reopen": "open"}[action]
    report.updated_at = now_str()
    db.session.commit()
    flash("وضعیت گزارش بازارچه به‌روزرسانی شد.", "success")
    return redirect(url_for("panel.marketplace", tab="reports"))


def handle_buyer_action(profile_id):
    profile = BuyerProfile.query.get_or_404(profile_id)
    action = (request.form.get("action") or "").strip()
    note = (request.form.get("admin_note") or "").strip()[:1000]
    if action == "verify":
        profile.verification_status = "verified"
        profile.verified_at = now_str()
    elif action == "reject":
        profile.verification_status = "rejected"
        profile.verified_at = ""
    elif action == "suspend":
        profile.verification_status = "suspended"
    elif action == "delete":
        active = BuyerOffer.query.filter(BuyerOffer.buyer_user_id==profile.user_id, BuyerOffer.status.in_(("pending","countered","accepted"))).first()
        if active:
            flash("این خریدار پیشنهاد فعال دارد و قابل حذف نیست؛ ابتدا او را تعلیق کنید.", "warning")
            return redirect(url_for("panel.marketplace", tab="buyers"))
        db.session.delete(profile); db.session.commit()
        flash("پروفایل خریدار با حفظ سوابق تاریخی حذف شد.", "success")
        return redirect(url_for("panel.marketplace", tab="buyers"))
    else:
        flash("عملیات درخواست خریدار نامعتبر است.", "warning")
        return redirect(url_for("panel.marketplace", tab="buyers"))
    profile.admin_note = note
    profile.updated_at = now_str()
    db.session.commit()
    notify_buyer_profile_status(profile)
    flash("وضعیت درخواست خرید به‌روزرسانی شد.", "success")
    return redirect(url_for("panel.marketplace", tab="buyers"))


def handle_settings():
    role, _perms, _bid = current_role_and_perms()
    if role != "super":
        abort(403)
    action = (request.form.get("marketplace_admin_action") or "settings").strip()
    if action == "review_moderation":
        try:
            review_id = int(request.form.get("review_id") or 0)
        except (TypeError, ValueError):
            review_id = 0
        review = MarketplaceReview.query.get_or_404(review_id)
        review_action = (request.form.get("review_action") or "").strip()
        if review_action not in ("hide", "restore"):
            flash("عملیات امتیاز معتبر نیست.", "warning")
            return redirect(url_for("panel.marketplace", tab="reviews"))
        review.status = "hidden" if review_action == "hide" else "visible"
        db.session.commit()
        refresh_user_rating(review.reviewee_user_id)
        flash("وضعیت نمایش امتیاز به‌روزرسانی شد.", "success")
        return redirect(url_for("panel.marketplace", tab="reviews"))

    if action == "credits":
        values = {
            "seller_features_enabled": request.form.get("seller_features_enabled") == "1",
            "buyer_features_enabled": request.form.get("buyer_features_enabled") == "1",
            "buyer_alert_3_price": request.form.get("buyer_alert_3_price"),
            "buyer_alert_7_price": request.form.get("buyer_alert_7_price"),
            "buyer_alert_30_price": request.form.get("buyer_alert_30_price"),
            "buyer_bonus_price": request.form.get("buyer_bonus_price"),
            "promo_bump_price": request.form.get("promo_bump_price"),
            "promo_urgent_price": request.form.get("promo_urgent_price"),
            "promo_featured_price": request.form.get("promo_featured_price"),
        }
    else:
        values = {
            "enabled": request.form.get("enabled") == "1",
            "terms": request.form.get("terms", ""),
            "disclaimer": request.form.get("disclaimer", ""),
            "offer_limit": request.form.get("offer_limit", "5"),
            "show_highest_offer": request.form.get("show_highest_offer") == "1",
            "chat_enabled": request.form.get("chat_enabled") == "1",
        }
    ok, message = save_marketplace_settings(values)
    flash(message, "success" if ok else "danger")
    return redirect(url_for("panel.marketplace", tab="credits" if action == "credits" else "settings"))
