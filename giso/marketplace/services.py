# -*- coding: utf-8 -*-
"""Focused domain helpers for the lightweight Giso hair marketplace."""
import hashlib
import logging
import os
import re
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta

logger = logging.getLogger("giso_marketplace_services")
_MARKETPLACE_NOTIFY_POOL = ThreadPoolExecutor(max_workers=3, thread_name_prefix="giso_market_user")

from sqlalchemy import func

from giso.config import Config
from giso.base import get_giso_db_conn, get_site_url
from giso.marketplace.settings import marketplace_settings
from giso.models import (
    db, User, HairListing, BuyerProfile, BuyerOffer,
    MarketplaceMessage, MarketplaceReview, MarketplaceUserRating,
)

LISTING_PUBLIC_STATUSES = ("published", "negotiating")
OFFER_ACTIVE_STATUSES = ("pending", "countered", "accepted")
# مهلت نمایش عمومی هر آگهی فروش مو (هم‌الگوی آگهی مرکز زیبایی). پس از این مدت،
# آگهی فقط از فهرست/جزئیات عمومی پنهان می‌شود (نه حذف، نه تغییر وضعیت معامله) و
# فروشنده با بسته «تمدید» می‌تواند دوباره آن را به همین تعداد روز فعال نگه دارد.
LISTING_DURATION_DAYS = 30
LISTING_STATUSES = (
    "pending_review", "published", "negotiating", "rejected",
    "paused", "closed", "withdrawn", "sold",
)
OFFER_STATUSES = ("pending", "countered", "accepted", "rejected", "withdrawn", "expired", "sold")

LISTING_STATUS_FA = {
    "pending_review": "در انتظار بررسی", "published": "منتشرشده",
    "negotiating": "در حال مذاکره", "rejected": "ردشده",
    "paused": "متوقف‌شده", "closed": "بسته‌شده", "withdrawn": "انصراف فروشنده",
    "sold": "فروخته‌شده",
}
OFFER_STATUS_FA = {
    "pending": "در انتظار پاسخ", "countered": "قیمت متقابل فروشنده",
    "accepted": "پذیرفته‌شده", "rejected": "ردشده",
    "withdrawn": "پس‌گرفته‌شده", "expired": "منقضی‌شده", "sold": "معامله موفق",
}


def now_str() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def parse_amount(value) -> int:
    text = str(value or "").translate(str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789"))
    digits = re.sub(r"[^0-9]", "", text)
    try:
        return int(digits) if digits else 0
    except (TypeError, ValueError):
        return 0


def _fa_number(value) -> str:
    return str(value or 0).translate(str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹"))


def format_amount(value) -> str:
    """Return a privacy-safe display amount with Persian digits and 3-digit groups."""
    amount = parse_amount(value)
    return _fa_number(f"{amount:,}")


def public_listing_note(value) -> str:
    """Keep listing detail useful while masking contact data entered in free text."""
    text = str(value or "").strip()
    text = re.sub(
        r"(?<![0-9۰-۹])(?:(?:\+|۰۰|00)?(?:۹۸|98)|[۰0])?[۹9][0-9۰-۹\s\-]{9,15}(?![0-9۰-۹])",
        "[اطلاعات تماس حذف شد]", text,
    )
    text = re.sub(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}", "[اطلاعات تماس حذف شد]", text)
    return text


def listing_public_title(listing) -> str:
    hair_label = {
        "raw": "موی طبیعی", "colored": "موی رنگ‌شده", "blonde": "موی روشن",
    }.get(str(getattr(listing, "hair_type", "") or ""), "موی طبیعی")
    city = str(getattr(listing, "city", "") or getattr(listing, "region", "") or "ایران").strip()
    length = _fa_number(getattr(listing, "length_cm", 0))
    return f"{hair_label} {city} {length} سانتی‌متر"


def make_listing_slug(listing) -> str:
    """Build a readable Persian slug while preserving Persian characters."""
    text = listing_public_title(listing).replace(" سانتی‌متر", "سانتی متر")
    text = re.sub(r"[^A-Za-z0-9\u0600-\u06FF]+", "-", text)
    return re.sub(r"-{2,}", "-", text).strip("-")[:200] or f"آگهی-مو-{getattr(listing, 'id', 0)}"


def ensure_listing_slug(listing) -> str:
    """Assign an idempotent canonical slug; collisions receive a stable id suffix."""
    if not listing:
        return ""
    current = str(getattr(listing, "slug", "") or "").strip()
    if current:
        return current
    base = make_listing_slug(listing)
    candidate = base
    existing = HairListing.query.filter(
        HairListing.slug == candidate,
        HairListing.id != int(getattr(listing, "id", 0) or 0),
    ).first()
    if existing:
        candidate = f"{base}-{_fa_number(getattr(listing, 'id', 0))}"
    listing.slug = candidate[:220]
    return listing.slug


def ensure_listing_slugs(listings, commit: bool = True) -> bool:
    changed = False
    for listing in listings or []:
        if not str(getattr(listing, "slug", "") or "").strip():
            ensure_listing_slug(listing)
            changed = True
    if changed and commit:
        db.session.commit()
    return changed


def seller_public_code(user_id: int) -> str:
    digest = hashlib.sha256(f"giso-market-seller:{int(user_id)}".encode("utf-8")).hexdigest()
    return digest[:8].upper()


def seller_public_stats(user_id: int) -> dict:
    """Privacy-safe seller aggregates used by cards and the public seller profile."""
    listings = HairListing.query.filter(
        HairListing.seller_user_id == int(user_id), HairListing.deleted_at == "",
    )
    reviews = MarketplaceReview.query.join(
        HairListing, HairListing.id == MarketplaceReview.listing_id,
    ).filter(
        MarketplaceReview.reviewee_user_id == int(user_id),
        MarketplaceReview.reviewer_role == "buyer",
        MarketplaceReview.status == "visible",
        HairListing.deleted_at == "",
    ).all()
    ratings = [int(row.rating or 0) for row in reviews if 1 <= int(row.rating or 0) <= 5]
    average = round(sum(ratings) / len(ratings), 1) if ratings else 0
    successful = listings.filter(HairListing.status == "sold").count()
    return {
        "code": seller_public_code(user_id),
        "average": average,
        "rating_count": len(ratings),
        "successful_transactions": successful,
        "listing_count": listings.count(),
        "is_verified_seller": bool(successful >= 3 and average >= 4),
    }


def marketplace_stats() -> dict:
    """Four lifetime counters used by the compact public marketplace hero."""
    visible = HairListing.query.filter(HairListing.deleted_at == "")
    views = visible.with_entities(func.coalesce(func.sum(HairListing.views_count), 0)).scalar() or 0
    return {
        "successful_transactions": visible.filter_by(status="sold").count(),
        "buyer_count": BuyerProfile.query.filter_by(verification_status="verified").count(),
        "total_views": int(views),
        "total_listings": visible.count(),
        "active_listings": visible.filter(HairListing.status.in_(LISTING_PUBLIC_STATUSES)).count(),
    }


def marketplace_reputation(user_id: int) -> dict:
    """Anonymous star-only reputation; textual comments are intentionally ignored."""
    reviews = MarketplaceReview.query.join(
        HairListing, HairListing.id == MarketplaceReview.listing_id,
    ).filter(
        MarketplaceReview.reviewee_user_id == int(user_id),
        MarketplaceReview.status == "visible",
        HairListing.deleted_at == "",
    ).all()
    ratings = [int(row.rating or 0) for row in reviews if 1 <= int(row.rating or 0) <= 5]
    return {
        "count": len(ratings),
        "average": round(sum(ratings) / len(ratings), 1) if ratings else 0,
    }


def refresh_user_rating(user_id: int):
    reviews = MarketplaceReview.query.join(
        HairListing, HairListing.id == MarketplaceReview.listing_id,
    ).filter(
        MarketplaceReview.reviewee_user_id == int(user_id),
        MarketplaceReview.status == "visible",
        HairListing.deleted_at == "",
    ).all()
    ratings = [int(row.rating or 0) for row in reviews if 1 <= int(row.rating or 0) <= 5]
    cache = MarketplaceUserRating.query.filter_by(user_id=int(user_id)).first()
    if not cache:
        cache = MarketplaceUserRating(user_id=int(user_id))
        db.session.add(cache)
    cache.rating_avg = round(sum(ratings) / len(ratings), 2) if ratings else 0.0
    cache.rating_count = len(ratings)
    cache.updated_at = now_str()
    db.session.commit()
    return cache


def _move_marketplace_photo(photo_path: str) -> str:
    photo_path = str(photo_path or "")
    if not photo_path.startswith("uploads/temp/"):
        return photo_path
    source = os.path.join(Config.BASE_DIR, "giso", "static", photo_path)
    if not os.path.exists(source):
        return photo_path
    destination_dir = os.path.join(Config.UPLOAD_FOLDER, "marketplace")
    os.makedirs(destination_dir, exist_ok=True)
    extension = os.path.splitext(source)[1].lower()
    if extension not in (".jpg", ".jpeg", ".png"):
        extension = ".jpg"
    # WebP conversion (max 1000x1000, q82) with fallback to the raw os.replace below.
    webp_destination = os.path.join(destination_dir, f"listing_{uuid.uuid4().hex}.webp")
    try:
        from PIL import Image
        img = Image.open(source)
        img = img.convert("RGB")
        img.thumbnail((1000, 1000))
        img.save(webp_destination, "WEBP", quality=82)
        os.remove(source)
        return "uploads/marketplace/" + os.path.basename(webp_destination)
    except Exception as ex_w:
        logger.warning(f"marketplace photo WebP conversion failed ({ex_w}); falling back to raw move")
        try:
            if os.path.exists(webp_destination):
                os.remove(webp_destination)
        except Exception:
            pass
        filename = f"listing_{uuid.uuid4().hex}{extension}"
        destination = os.path.join(destination_dir, filename)
        os.replace(source, destination)
        return "uploads/marketplace/" + filename


def build_listing_from_temp(temp: dict, user, region: str = "", defer_photo_move: bool = False):
    if not user or not getattr(user, "id", None):
        raise ValueError("seller_user_required")
    if not temp.get("marketplace_terms_accepted"):
        raise ValueError("marketplace_terms_required")
    asking_price = parse_amount(temp.get("seller_expected_price"))
    if asking_price <= 0:
        raise ValueError("seller_asking_price_required")
    photo_path = str(temp.get("photo_path") or "")
    if not photo_path:
        raise ValueError("listing_photo_required")
    if not defer_photo_move:
        photo_path = _move_marketplace_photo(photo_path)
    listing = HairListing(
        seller_user_id=user.id,
        photo_path=photo_path,
        hair_type=str(temp.get("hair_type") or "raw")[:100],
        length_cm=int(temp.get("length_cm") or 50),
        hair_health=str(temp.get("hair_health") or "")[:100],
        hair_weight=str(temp.get("hair_weight") or "")[:100],
        city=str(getattr(user, "city", "") or region or getattr(user, "region", "") or "")[:100],
        region=str(region or getattr(user, "region", "") or "")[:150],
        seller_asking_price=asking_price,
        seller_note=str(temp.get("seller_price_note") or "")[:500],
        estimated_price_snapshot=str(temp.get("estimated_price") or "")[:100],
        status="pending_review",
        terms_version="marketplace-v1",
        terms_accepted_at=str(temp.get("marketplace_terms_accepted_at") or now_str()),
        created_at=now_str(), updated_at=now_str(),
    )
    db.session.add(listing)
    db.session.flush()
    ensure_listing_slug(listing)
    return listing


def create_marketplace_listing(temp: dict, user, region: str = ""):
    listing = build_listing_from_temp(temp, user, region, defer_photo_move=False)
    db.session.commit()
    notify_listing_created(listing)
    return listing


def refresh_listing_offer_stats(listing_id: int):
    """Preserve the existing highest-offer rules and state machine."""
    listing = HairListing.query.get(listing_id)
    if not listing:
        return
    offers = BuyerOffer.query.filter_by(listing_id=listing_id).all()
    listing.offers_count = len([row for row in offers if row.status != "withdrawn"])
    amounts = [int(row.offer_amount) for row in offers if row.status in OFFER_ACTIVE_STATUSES and row.offer_amount]
    listing.highest_offer_amount = max(amounts) if amounts else 0
    listing.updated_at = now_str()
    db.session.commit()


def _send_marketplace_bale_user(phone: str, title: str, message: str):
    """ارسال غیرمسدودکننده اعلان بازارچه به حساب بله متصل کاربر."""
    try:
        from giso.base import normalize_phone, get_giso_db_conn, _token_from_env, _token_from_db, _http_post
        from giso.security import record_delivery
        normalized = normalize_phone(phone or "")
        if not normalized:
            return
        with get_giso_db_conn() as conn:
            row = conn.execute(
                "SELECT bale_id FROM giso_users WHERE phone=? AND contact_shared=1 LIMIT 1",
                (normalized,),
            ).fetchone()
        if not row or not str(row["bale_id"] or "").isdigit():
            return
        recipient = int(row["bale_id"])
        token = (_token_from_env() or _token_from_db() or "").strip()
        if not token:
            record_delivery(0, recipient, "failed", error_code="missing_token",
                            error_message="Bale token is not configured")
            return
        site = get_site_url()
        body = f"🏪 {title}\n━━━━━━━━━━━━━━━━\n{message}\n\n🔗 {site}/dashboard/marketplace"
        response = _http_post(
            f"https://tapi.bale.ai/bot{token}/sendMessage",
            json_payload={"chat_id": recipient, "text": body[:4000], "parse_mode": "HTML"},
        )
        code = int(getattr(response, "status_code", 0) or 0)
        record_delivery(0, recipient, "sent" if code in (200, 201, 202, 204) else "failed",
                        http_status=code, error_code="" if code in (200, 201, 202, 204) else "http_error")
    except Exception as exc:
        logger.debug("marketplace user Bale notification failed: %s", exc)


def notify_marketplace_user(phone: str, subcategory: str, title: str, message: str,
                            source_type: str, source_id: int):
    """اعلان واحد بازارچه: Bell/Toast سایت + پیام بله در صورت اتصال حساب."""
    try:
        from giso.panel.modules.notifications import log_user_notification
        log_user_notification(
            phone, subcategory, title, message,
            source_type=source_type, source_id=source_id, category="marketplace",
        )
    except Exception as exc:
        logger.debug("marketplace site notification failed: %s", exc)
    try:
        _MARKETPLACE_NOTIFY_POOL.submit(_send_marketplace_bale_user, phone, title, message)
    except Exception as exc:
        logger.debug("marketplace Bale notification queue failed: %s", exc)


def notify_marketplace_admin(event_type: str, title: str, message: str,
                             source_type: str, source_id: int):
    try:
        from giso.panel.modules.notifications import log_notification
        return log_notification(
            "marketplace", event_type, title, message,
            target_role="admin", source_type=source_type, source_id=int(source_id or 0),
        )
    except Exception:
        return None


def notify_listing_created(listing):
    try:
        from giso.panel.modules.notifications import log_notification
        log_notification(
            "marketplace", "listing_new", "آگهی جدید بازارچه مو",
            f"آگهی #{listing.id} برای بررسی ثبت شد.",
            source_type="marketplace_listing", source_id=listing.id,
        )
        seller = User.query.get(listing.seller_user_id)
        if seller:
            notify_marketplace_user(
                seller.phone, "listing_created", "آگهی بازارچه ثبت شد",
                f"آگهی #{listing.id} در صف بررسی قرار گرفت.",
                "marketplace_listing_created", listing.id,
            )
    except Exception:
        pass


def notify_listing_status(listing):
    """Only approval/rejection notifications remain in the simplified flow."""
    if listing.status not in ("published", "rejected"):
        return
    try:
        label = LISTING_STATUS_FA.get(listing.status, listing.status)
        seller = User.query.get(listing.seller_user_id)
        if seller:
            notify_marketplace_user(
                seller.phone, "listing_status", "وضعیت آگهی بازارچه",
                f"وضعیت آگهی #{listing.id}: {label}",
                f"marketplace_listing_{listing.status}", listing.id,
            )
        notify_marketplace_admin(
            "listing_status", "تغییر وضعیت آگهی بازارچه",
            f"وضعیت آگهی #{listing.id} به {label} تغییر کرد.",
            f"marketplace_admin_listing_{listing.status}", listing.id,
        )
    except Exception:
        pass


def notify_offer_created(offer, listing):
    try:
        seller = User.query.get(listing.seller_user_id)
        if seller:
            notify_marketplace_user(
                seller.phone, "offer_new", "پیشنهاد جدید بازارچه",
                f"برای آگهی #{listing.id} پیشنهاد {format_amount(offer.offer_amount)} تومان ثبت شد.",
                "marketplace_offer_new", offer.id,
            )
        notify_marketplace_admin(
            "offer_new", "پیشنهاد جدید بازارچه",
            f"پیشنهاد #{offer.id} برای آگهی #{listing.id} ثبت شد.",
            "marketplace_admin_offer_new", offer.id,
        )
    except Exception:
        pass


def notify_offer_status(offer, title="وضعیت پیشنهاد بازارچه"):
    try:
        buyer = User.query.get(offer.buyer_user_id)
        if buyer:
            amount = offer.seller_counter_amount if offer.status == "countered" else offer.offer_amount
            notify_marketplace_user(
                buyer.phone, "offer_status", title,
                f"پیشنهاد شما برای آگهی #{offer.listing_id}: {OFFER_STATUS_FA.get(offer.status, offer.status)} — {format_amount(amount)} تومان",
                f"marketplace_offer_{offer.status}", offer.id,
            )
        notify_marketplace_admin(
            "offer_status", title,
            f"پیشنهاد #{offer.id} برای آگهی #{offer.listing_id}: {OFFER_STATUS_FA.get(offer.status, offer.status)}",
            f"marketplace_admin_offer_{offer.status}", offer.id,
        )
    except Exception:
        pass


def notify_seller_offer_status(offer, title="به‌روزرسانی پیشنهاد خریدار"):
    try:
        listing = HairListing.query.get(offer.listing_id)
        seller = User.query.get(listing.seller_user_id) if listing else None
        if seller:
            notify_marketplace_user(
                seller.phone, "offer_buyer_status", title,
                f"وضعیت پیشنهاد #{offer.id}: {OFFER_STATUS_FA.get(offer.status, offer.status)}",
                f"marketplace_offer_buyer_{offer.status}", offer.id,
            )
        notify_marketplace_admin(
            "offer_buyer_status", title,
            f"پیشنهاد #{offer.id}: {OFFER_STATUS_FA.get(offer.status, offer.status)}",
            f"marketplace_admin_offer_buyer_{offer.status}", offer.id,
        )
    except Exception:
        pass


def notify_buyer_request_created(profile):
    try:
        from giso.panel.modules.notifications import log_notification
        log_notification(
            "marketplace", "buyer_request", "درخواست خرید مو",
            f"درخواست خرید #{profile.id} برای بررسی ثبت شد.",
            target_role="admin", source_type="marketplace_buyer_request", source_id=profile.id,
        )
    except Exception:
        pass


def notify_buyer_profile_status(profile):
    try:
        user = User.query.get(profile.user_id)
        phone = (user.phone if user else "") or profile.phone_snapshot
        if phone:
            status_label = {
                "pending": "در انتظار بررسی", "verified": "تأییدشده",
                "rejected": "ردشده", "suspended": "موقتاً محدودشده",
            }.get(profile.verification_status, profile.verification_status)
            notify_marketplace_user(
                phone, "buyer_request_status", "وضعیت درخواست خرید مو",
                f"وضعیت درخواست خرید شما: {status_label}",
                f"marketplace_buyer_request_{profile.verification_status}", profile.id,
            )
    except Exception:
        pass


def daily_offer_count(user_id: int) -> int:
    since = (datetime.now() - timedelta(hours=24)).strftime("%Y-%m-%d %H:%M:%S")
    return BuyerOffer.query.filter(BuyerOffer.buyer_user_id == user_id, BuyerOffer.created_at >= since).count()


def is_offer_party(offer, user_id: int) -> bool:
    listing = HairListing.query.get(offer.listing_id) if offer else None
    return bool(offer and listing and user_id in (offer.buyer_user_id, listing.seller_user_id))


def close_listing_for_direct_sale(hair_order_id: int) -> bool:
    """وقتی گیسو مو را مستقیم خرید (hair_order به completed/approved رفت)،
    آگهی متصل بازارچه (source_hair_order_id) بسته و «فروخته‌شده» می‌شود و
    پیشنهادهای باز آن منقضی می‌شوند تا در پنل خریدار/فروشنده باز نمانند.
    """
    if not hair_order_id:
        return False
    try:
        listing = HairListing.query.filter_by(
            source_hair_order_id=int(hair_order_id), deleted_at="",
        ).first()
        if not listing or listing.status == "sold":
            return False
        stamp = now_str()
        listing.status = "sold"
        listing.sold_at = stamp
        listing.updated_at = stamp
        open_offers = BuyerOffer.query.filter(
            BuyerOffer.listing_id == listing.id,
            BuyerOffer.status.in_(("pending", "countered", "accepted")),
        ).all()
        for offer in open_offers:
            offer.status = "expired"
            offer.updated_at = stamp
            offer.chat_closed = 1
            offer.chat_closed_at = stamp
        db.session.commit()
        for offer in open_offers:
            try:
                notify_offer_status(offer, title="پایان دریافت پیشنهاد برای آگهی")
            except Exception:
                pass
        return True
    except Exception as exc:
        logger.warning("close_listing_for_direct_sale failed: %s", exc)
        try:
            db.session.rollback()
        except Exception:
            pass
        return False


def user_marketplace_context(user):
    """Everything needed by the single user marketplace workspace.

    The returned collections only reorganise existing listings/offers/messages; they do
    not introduce a second conversation or offer state machine.
    """
    listings = HairListing.query.filter(
        HairListing.seller_user_id == user.id,
        HairListing.deleted_at == "",
    ).order_by(HairListing.id.desc()).all()
    listing_ids = [row.id for row in listings]
    seller_offers = (
        BuyerOffer.query.filter(BuyerOffer.listing_id.in_(listing_ids))
        .order_by(BuyerOffer.id.desc()).all()
        if listing_ids else []
    )
    offers_by_listing = {listing_id: [] for listing_id in listing_ids}
    for offer in seller_offers:
        offers_by_listing.setdefault(offer.listing_id, []).append(offer)

    my_offers = BuyerOffer.query.join(
        HairListing, HairListing.id == BuyerOffer.listing_id,
    ).filter(
        BuyerOffer.buyer_user_id == user.id,
        HairListing.deleted_at == "",
    ).order_by(BuyerOffer.id.desc()).all()

    all_party_offers = []
    seen_party_offer_ids = set()
    for offer in seller_offers + my_offers:
        if offer.id not in seen_party_offer_ids:
            seen_party_offer_ids.add(offer.id)
            all_party_offers.append(offer)

    offer_listings = {}
    for offer in all_party_offers:
        if offer.listing_id not in offer_listings:
            offer_listings[offer.listing_id] = HairListing.query.filter_by(
                id=offer.listing_id, deleted_at="",
            ).first()

    canonical_listings = list(listings) + [row for row in offer_listings.values() if row]
    ensure_listing_slugs(canonical_listings)

    conversations = [
        offer for offer in all_party_offers
        if offer.status in ("accepted", "sold") or bool(offer.chat_closed)
    ]
    conversations.sort(key=lambda row: (row.updated_at or row.created_at or "", row.id), reverse=True)
    conversation_ids = [row.id for row in conversations]
    latest_messages = {}
    if conversation_ids:
        messages = MarketplaceMessage.query.filter(
            MarketplaceMessage.offer_id.in_(conversation_ids),
        ).order_by(MarketplaceMessage.offer_id.asc(), MarketplaceMessage.id.desc()).all()
        for message in messages:
            latest_messages.setdefault(message.offer_id, message)

    reviewed_ids = {
        row.offer_id for row in MarketplaceReview.query.filter_by(reviewer_user_id=user.id).all()
    }
    successful = [offer for offer in all_party_offers if offer.status == "sold"]
    successful.sort(key=lambda row: (row.sold_at or row.updated_at or "", row.id), reverse=True)
    buyer_profile = BuyerProfile.query.filter_by(user_id=user.id).first()

    import uuid
    purchase_nonces={"alert":uuid.uuid4().hex,"bonus":uuid.uuid4().hex,
                     "bump":uuid.uuid4().hex,"urgent":uuid.uuid4().hex,"featured":uuid.uuid4().hex,
                     "renew":uuid.uuid4().hex}
    try:
        from giso.user_profile_service import safe_form_defaults
        profile_defaults = safe_form_defaults(user)
    except Exception:
        profile_defaults = {"city": ""}
    # وضعیت مهلت ۳۰روزه‌ی نمایش عمومی برای کارت‌های فروشنده (روزهای باقی‌مانده/انقضا).
    listing_expiry_by_id = {
        row.id: {
            "expired": not listing_expiry_is_active(row),
            "days_left": max(0, listing_days_left(row)),
        }
        for row in listings
    }
    return {
        "listing_expiry_by_id": listing_expiry_by_id,
        "listing_duration_days": LISTING_DURATION_DAYS,
        **buyer_feature_context(user.id),
        "profile_defaults": profile_defaults,
        "market_purchase_nonces": purchase_nonces,
        "market_listings": listings,
        "market_active_listings": [
            row for row in listings
            if row.status in ("pending_review", "published", "negotiating", "paused")
        ],
        "market_archived_listings": [
            row for row in listings if row.status in ("closed", "withdrawn", "rejected")
        ],
        "market_successful_offers": successful,
        "market_conversations": conversations,
        "market_conversation_latest": latest_messages,
        "seller_offers_by_listing": offers_by_listing,
        "my_market_offers": my_offers,
        "my_active_market_offers": [row for row in my_offers if row.status in OFFER_ACTIVE_STATUSES],
        "market_archived_offers": [
            row for row in my_offers if row.status in ("rejected", "withdrawn", "expired")
        ],
        "offer_listings": offer_listings,
        "market_reviewed_offer_ids": reviewed_ids,
        "market_reputation": marketplace_reputation(user.id),
        "buyer_request": buyer_profile,
        "buyer_request_active": bool(buyer_profile),
        "buyer_status_fa": {
            "pending": "در انتظار بررسی", "verified": "تأییدشده",
            "rejected": "ردشده", "suspended": "موقتاً محدودشده",
        },
        "buyer_type_fa": {
            "personal": "خرید شخصی", "salon": "خرید برای سالن", "commercial": "خرید تجاری",
        },
        "listing_status_fa": LISTING_STATUS_FA,
        "offer_status_fa": OFFER_STATUS_FA,
        "fmt_market_amount": format_amount,
    }


def buyer_feature_context(user_id: int) -> dict:
    settings = marketplace_settings()
    used = daily_offer_count(int(user_id))
    now = now_str()
    with get_giso_db_conn() as conn:
        bonus = conn.execute("SELECT COALESCE(SUM(extra_offers),0) FROM marketplace_offer_bonus_purchases WHERE user_id=? AND expires_at>?", (int(user_id), now)).fetchone()[0]
        alerts = [dict(row) for row in conn.execute("SELECT * FROM marketplace_buyer_alerts WHERE user_id=? AND is_active=1 AND expires_at>? ORDER BY id DESC", (int(user_id), now)).fetchall()]
    limit = 5 + int(bonus or 0)
    return {"buyer_feature_alerts": alerts, "buyer_offer_used": used, "buyer_offer_limit": limit,
            "buyer_offer_remaining": max(0, limit-used), "buyer_feature_settings": settings}


def _debit_buyer_feature(user_id: int, amount: int, key: str, description: str, conn) -> tuple[bool,str]:
    from giso.wallet import get_wallet_balances
    balances = get_wallet_balances(int(user_id), conn=conn)
    amount = max(0, int(amount or 0))
    if amount <= 0: return True, ""
    if int(balances.get("usable") or 0) < amount: return False, "اعتبار کیف پول برای خرید این امکان کافی نیست."
    spend = min(int(balances.get("spend") or 0), amount); cash = amount-spend
    stamp = now_str()
    if spend:
        conn.execute("INSERT INTO wallet_transactions(user_id,kind,amount,status,source_type,source_id,balance_scope,idempotency_key,description,created_at) VALUES (?,'marketplace_feature',?,'used','marketplace_buyer',0,'spend',?,?,?)", (int(user_id),-spend,key+':spend',description,stamp))
    if cash:
        conn.execute("INSERT INTO wallet_transactions(user_id,kind,amount,status,source_type,source_id,balance_scope,idempotency_key,description,created_at) VALUES (?,'marketplace_feature',?,'used','marketplace_buyer',0,'cash',?,?,?)", (int(user_id),-cash,key+':cash',description,stamp))
    return True, ""


def _market_purchase_key(prefix: str, user_id: int, nonce: str) -> str:
    import re
    clean=str(nonce or '').strip().lower()
    if not re.fullmatch(r'[a-f0-9]{32}',clean):return ''
    return f'{prefix}:{int(user_id)}:{clean}'


def purchase_buyer_alert(user_id: int, values: dict) -> tuple[bool,str]:
    raw_days = str(values.get("duration") or "7")
    days = 30 if raw_days == "30" else (3 if raw_days == "3" else 7)
    settings = marketplace_settings()
    if not settings["buyer_features_enabled"]: return False, "امکانات اعتباری خریدار موقتاً غیرفعال است."
    price = settings[{3:"buyer_alert_3_price",7:"buyer_alert_7_price",30:"buyer_alert_30_price"}[days]]
    key = _market_purchase_key('buyer_alert',user_id,values.get('purchase_nonce'))
    if not key:return False,"درخواست منقضی شده است؛ صفحه را تازه‌سازی کنید."
    with get_giso_db_conn() as conn:
        try:
            conn.execute("BEGIN IMMEDIATE")
            if conn.execute("SELECT id FROM marketplace_buyer_alerts WHERE purchase_transaction_key=?",(key,)).fetchone():conn.rollback();return True,"این اعلان قبلاً فعال شده است."
            ok,msg=_debit_buyer_feature(user_id,price,key,f"اعلان هوشمند آگهی {days} روزه",conn)
            if not ok: conn.rollback(); return False,msg
            conn.execute("INSERT INTO marketplace_buyer_alerts(user_id,min_length,max_length,hair_type,city,min_price,max_price,duration_days,expires_at,is_active,purchase_transaction_key,created_at) VALUES (?,?,?,?,?,?,?,?,datetime('now','localtime',?),1,?,datetime('now','localtime'))", (int(user_id),int(values.get('min_length') or 0),int(values.get('max_length') or 0),str(values.get('hair_type') or '')[:100],str(values.get('city') or '')[:100],parse_amount(values.get('min_price')),parse_amount(values.get('max_price')),days,f'+{days} days',key))
            conn.commit(); return True,f"اعلان هوشمند برای {days} روز فعال شد."
        except Exception: conn.rollback(); return False,"فعال‌سازی اعلان ناموفق بود."


def notify_matching_buyer_alerts(listing) -> int:
    """اعلان سایت و بله برای جست‌وجوهای فعال منطبق با آگهی تازه‌منتشرشده."""
    now=now_str(); sent=0
    with get_giso_db_conn() as conn:
        rows=conn.execute("SELECT a.*,u.phone FROM marketplace_buyer_alerts a JOIN giso_web_auth u ON u.id=a.user_id WHERE a.is_active=1 AND a.expires_at>? AND (?=0 OR a.min_length=0 OR ? >= a.min_length) AND (?=0 OR a.max_length=0 OR ? <= a.max_length) AND (a.city='' OR a.city=?) AND (a.hair_type='' OR ? LIKE '%'||a.hair_type||'%') AND (a.min_price=0 OR ?>=a.min_price) AND (a.max_price=0 OR ?<=a.max_price)",(now,int(listing.length_cm or 0),int(listing.length_cm or 0),int(listing.length_cm or 0),int(listing.length_cm or 0),str(listing.city or ''),str(listing.hair_type or ''),int(listing.seller_asking_price or 0),int(listing.seller_asking_price or 0))).fetchall()
    for row in rows:
        try:
            notify_marketplace_user(row['phone'],"smart_alert",title="آگهی مناسب جست‌وجوی شما",message=f"موی {listing.length_cm} سانتی‌متری در {listing.city or 'بازارچه'} منتشر شد.",source_type="buyer_smart_alert",source_id=listing.id)
            sent+=1
        except Exception: pass
    return sent


def listing_expiry_is_active(listing, at: str = "") -> bool:
    """True if the listing still has public-display time left.

    An empty ``listing_expires_at`` means 'no deadline' so every pre-existing
    row keeps showing until the seller/owner renews it explicitly.
    """
    raw = getattr(listing, "listing_expires_at", "") or ""
    if not str(raw).strip():
        return True
    try:
        return str(raw) > (at or now_str())
    except Exception:
        return True


def listing_days_left(listing, at: str = "") -> int:
    """Whole days of public display remaining (<=0 means expired)."""
    raw = getattr(listing, "listing_expires_at", "") or ""
    if not str(raw).strip():
        return LISTING_DURATION_DAYS
    try:
        ref = datetime.strptime(at or now_str(), "%Y-%m-%d %H:%M:%S")
        exp = datetime.strptime(str(raw), "%Y-%m-%d %H:%M:%S")
        return int((exp - ref).days)
    except Exception:
        return LISTING_DURATION_DAYS


def renew_listing_promotion(user_id: int, listing_id: int, nonce: str = '') -> tuple[bool, str]:
    """Extend a seller's own listing's public-display window by LISTING_DURATION_DAYS days.

    Mirrors the beauty-center renewal: charge via the existing wallet debit, record the
    purchase idempotently, and never delete or change the listing's transaction status.
    """
    settings = marketplace_settings()
    if not settings["seller_features_enabled"]:
        return False, "تمدید آگهی موقتاً غیرفعال است."
    price = settings["renew_price"]
    key = _market_purchase_key(f'listing_renew_{int(listing_id)}', user_id, nonce)
    if not key:
        return False, "درخواست منقضی شده است؛ صفحه را تازه‌سازی کنید."
    with get_giso_db_conn() as conn:
        listing = conn.execute(
            "SELECT * FROM hair_listings WHERE id=? AND seller_user_id=? "
            "AND status IN ('published','negotiating') AND COALESCE(deleted_at,'')=''",
            (int(listing_id), int(user_id)),
        ).fetchone()
        if not listing:
            return False, "فقط آگهی فعال خودتان قابل تمدید است."
        try:
            conn.execute("BEGIN IMMEDIATE")
            dup = conn.execute(
                "SELECT id FROM marketplace_promotion_purchases WHERE transaction_key=?", (key,)
            ).fetchone()
            if dup:
                conn.rollback()
                return True, "این تمدید قبلاً اعمال شده است."
            ok, msg = _debit_buyer_feature(user_id, price, key, f"تمدید {LISTING_DURATION_DAYS} روزه آگهی #{int(listing_id)}", conn)
            if not ok:
                conn.rollback()
                return False, msg
            # اگر هنوز مهلت باقی مانده، به همان زمان اضافه می‌شود؛ در غیر این صورت از همین لحظه.
            new_expiry = conn.execute(
                "SELECT datetime(MAX(COALESCE(NULLIF(listing_expires_at,''),''), datetime('now','localtime')), '+{0} days') "
                "FROM hair_listings WHERE id=?".format(LISTING_DURATION_DAYS),
                (int(listing_id),),
            ).fetchone()[0]
            conn.execute(
                "UPDATE hair_listings SET listing_expires_at=?, updated_at=datetime('now','localtime') WHERE id=?",
                (new_expiry, int(listing_id)),
            )
            conn.execute(
                "INSERT INTO marketplace_promotion_purchases(listing_id,user_id,package_key,amount,starts_at,expires_at,transaction_key,status,created_at) "
                "VALUES (?,?,?,? ,datetime('now','localtime'),?,?, 'active', datetime('now','localtime'))",
                (int(listing_id), int(user_id), "renew", int(price), new_expiry, key),
            )
            conn.commit()
            return True, f"آگهی با موفقیت {LISTING_DURATION_DAYS} روز تمدید شد."
        except Exception:
            conn.rollback()
            return False, "تمدید آگهی ناموفق بود."


def purchase_listing_promotion(user_id: int, listing_id: int, package_key: str, nonce: str = '') -> tuple[bool,str]:
    packages={"bump":("نردبان",0,"promo_bump_price"),"urgent":("فروش فوری",1,"promo_urgent_price"),"featured":("آگهی ویژه",7,"promo_featured_price")}
    if package_key not in packages:return False,"بسته ارتقا نامعتبر است."
    label,days,price_key=packages[package_key]; settings=marketplace_settings()
    if not settings["seller_features_enabled"]: return False,"ارتقای آگهی موقتاً غیرفعال است."
    price=settings[price_key]
    key=_market_purchase_key(f'listing_promo_{listing_id}_{package_key}',user_id,nonce)
    if not key:return False,"درخواست منقضی شده است؛ صفحه را تازه‌سازی کنید."
    with get_giso_db_conn() as conn:
        listing=conn.execute("SELECT * FROM hair_listings WHERE id=? AND seller_user_id=? AND status IN ('published','negotiating') AND COALESCE(deleted_at,'')=''",(int(listing_id),int(user_id))).fetchone()
        if not listing:return False,"فقط آگهی فعال خودتان قابل ارتقا است."
        try:
            conn.execute("BEGIN IMMEDIATE")
            if conn.execute("SELECT id FROM marketplace_promotion_purchases WHERE transaction_key=?",(key,)).fetchone():conn.rollback();return True,"این ارتقا قبلاً ثبت شده است."
            ok,msg=_debit_buyer_feature(user_id,price,key,f"ارتقای {label} آگهی #{listing_id}",conn)
            if not ok:conn.rollback();return False,msg
            expires="" if days==0 else conn.execute("SELECT datetime('now','localtime',?)",(f'+{days} days',)).fetchone()[0]
            promo="" if package_key=='bump' else package_key
            conn.execute("UPDATE hair_listings SET promotion_type=?,promotion_expires_at=?,promotion_bumped_at=datetime('now','localtime'),updated_at=datetime('now','localtime') WHERE id=?",(promo,expires,int(listing_id)))
            conn.execute("INSERT INTO marketplace_promotion_purchases(listing_id,user_id,package_key,amount,starts_at,expires_at,transaction_key,status,created_at) VALUES (?,?,?,?,datetime('now','localtime'),?,?,'active',datetime('now','localtime'))",(int(listing_id),int(user_id),package_key,int(price),expires,key));conn.commit();return True,f"بسته {label} برای آگهی فعال شد."
        except Exception:conn.rollback();return False,"فعال‌سازی ارتقا ناموفق بود."


def purchase_offer_bonus(user_id: int, nonce: str = '') -> tuple[bool,str]:
    if not marketplace_settings()["buyer_features_enabled"]: return False,"امکانات اعتباری خریدار موقتاً غیرفعال است."
    with get_giso_db_conn() as conn:
        verified=conn.execute("SELECT id FROM buyer_profiles WHERE user_id=? AND verification_status='verified'",(int(user_id),)).fetchone()
        if not verified:return False,"این بسته فقط برای خریدار تأییدشده فعال است."
        key=_market_purchase_key('offer_bonus',user_id,nonce); price=marketplace_settings()['buyer_bonus_price']
        if not key:return False,"درخواست منقضی شده است؛ صفحه را تازه‌سازی کنید."
        try:
            conn.execute("BEGIN IMMEDIATE")
            if conn.execute("SELECT id FROM marketplace_offer_bonus_purchases WHERE transaction_key=?",(key,)).fetchone():conn.rollback();return True,"این بسته قبلاً فعال شده است."
            ok,msg=_debit_buyer_feature(user_id,price,key,"پنج پیشنهاد اضافه برای ۲۴ ساعت",conn)
            if not ok:conn.rollback();return False,msg
            conn.execute("INSERT INTO marketplace_offer_bonus_purchases(user_id,extra_offers,expires_at,transaction_key,created_at) VALUES (?,5,datetime('now','localtime','+1 day'),?,datetime('now','localtime'))",(int(user_id),key));conn.commit();return True,"پنج پیشنهاد اضافه برای ۲۴ ساعت فعال شد."
        except Exception:conn.rollback();return False,"خرید بسته پیشنهاد ناموفق بود."


__all__ = [
    "LISTING_PUBLIC_STATUSES", "OFFER_ACTIVE_STATUSES", "LISTING_STATUSES", "OFFER_STATUSES",
    "LISTING_STATUS_FA", "OFFER_STATUS_FA", "now_str", "parse_amount", "format_amount",
    "public_listing_note", "listing_public_title", "make_listing_slug", "ensure_listing_slug", "ensure_listing_slugs",
    "seller_public_code", "seller_public_stats",
    "marketplace_stats", "marketplace_reputation", "refresh_user_rating",
    "build_listing_from_temp", "create_marketplace_listing", "refresh_listing_offer_stats",
    "daily_offer_count", "is_offer_party", "close_listing_for_direct_sale", "user_marketplace_context",
    "notify_listing_created", "notify_listing_status", "notify_offer_created", "notify_offer_status",
    "notify_seller_offer_status", "notify_buyer_request_created", "notify_buyer_profile_status",
    "notify_marketplace_admin", "buyer_feature_context", "purchase_buyer_alert", "purchase_offer_bonus", "purchase_listing_promotion", "notify_matching_buyer_alerts",
    "LISTING_DURATION_DAYS", "listing_expiry_is_active", "listing_days_left", "renew_listing_promotion",
]
