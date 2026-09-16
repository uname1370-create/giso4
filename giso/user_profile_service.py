# -*- coding: utf-8 -*-
"""Single source of truth for the editable Giso user profile (site + Bale bot)."""
from __future__ import annotations

import logging
import re
from datetime import datetime, timedelta
from typing import Mapping

from giso.base import get_giso_db_conn, normalize_phone

logger = logging.getLogger("giso_user_profile")

PROFILE_FIELDS = {
    "first_name": ("نام", 60),
    "last_name": ("نام خانوادگی", 60),
    "city": ("شهر", 100),
    "region": ("منطقه یا محله", 200),
    "contact_time": ("زمان مناسب تماس", 100),
}
_CONTROL_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


def _clean(value, limit: int) -> str:
    text = _CONTROL_RE.sub("", str(value or ""))
    text = " ".join(text.replace("\u200e", " ").replace("\u200f", " ").split())
    return text[:limit].strip()


def get_user_profile(phone: str) -> dict:
    normalized = normalize_phone(phone or "")
    if not normalized:
        return {}
    # SQL خام مرکزی تا سرویس هم در Flask و هم در پردازش مستقل ربات کار کند.
    with get_giso_db_conn() as conn:
        row = conn.execute(
            "SELECT id,phone,name,first_name,last_name,city,region,contact_time,created_at,last_login,last_profile_edit_at "
            "FROM giso_web_auth WHERE phone=? LIMIT 1", (normalized,),
        ).fetchone()
    if not row:
        return {}
    return dict(row)


def update_user_profile(phone: str, values: Mapping, actor: str = "site") -> tuple[bool, str, dict]:
    """به‌روزرسانی whitelist با SQL مشترک؛ قابل استفاده در سایت و ربات."""
    normalized = normalize_phone(phone or "")
    if not normalized:
        return False, "شماره حساب معتبر نیست.", {}
    current = get_user_profile(normalized)
    if not current:
        return False, "حساب کاربری پیدا نشد.", {}
    last_edit=str(current.get("last_profile_edit_at") or "").strip()
    if last_edit:
        try:
            allowed_at=datetime.fromisoformat(last_edit)+timedelta(days=15)
            if datetime.now()<allowed_at:
                return False, f"ویرایش اطلاعات هر ۱۵ روز یک‌بار ممکن است. زمان بعدی: {allowed_at.strftime('%Y-%m-%d %H:%M')}", current
        except (TypeError,ValueError): pass
    updates = {field: _clean(values.get(field), limit) for field, (_label, limit) in PROFILE_FIELDS.items() if field in values}
    if not updates:
        return False, "اطلاعاتی برای ویرایش ارسال نشده است.", current
    first = updates.get("first_name", current.get("first_name") or "")
    last = updates.get("last_name", current.get("last_name") or "")
    full_name = f"{first} {last}".strip()[:150] or (current.get("name") or "")
    try:
        fields = list(updates)
        assignments = ",".join(f"{field}=?" for field in fields)
        params = [updates[field] for field in fields]
        with get_giso_db_conn() as conn:
            conn.execute(f"UPDATE giso_web_auth SET {assignments},name=?,last_profile_edit_at=datetime('now','localtime') WHERE phone=?", (*params, full_name, normalized))
            if "first_name" in updates:
                conn.execute("UPDATE giso_users SET first_name=? WHERE phone=?", (first, normalized))
            conn.commit()
        try:
            from giso.security import audit_event
            audit_event("user_profile_update", "success", target=str(current["id"]), details=f"actor={actor};fields={','.join(sorted(updates))}")
        except Exception:
            pass
        return True, "اطلاعات پروفایل با موفقیت ذخیره شد.", get_user_profile(normalized)
    except Exception as exc:
        logger.exception("profile update failed: %s", exc)
        return False, "ذخیره اطلاعات پروفایل ناموفق بود.", get_user_profile(normalized)


def safe_form_defaults(user=None, phone: str = "") -> dict:
    """Minimal profile defaults for authenticated order/advertisement forms.

    Never returns password/security fields, identifiers, login metadata or an exact
    address. Empty values remain empty and submitted form values must take priority.
    """
    authenticated = bool(user is not None and getattr(user, "is_authenticated", False))
    account_phone = normalize_phone(phone or (getattr(user, "phone", "") if authenticated else ""))
    if not account_phone:
        return {"full_name": "", "phone": "", "city": "", "region": "", "contact_time": ""}
    profile = get_user_profile(account_phone)
    if not profile:
        return {"full_name": "", "phone": account_phone, "city": "", "region": "", "contact_time": ""}
    first = _clean(profile.get("first_name"), 60)
    last = _clean(profile.get("last_name"), 60)
    full_name = _clean(f"{first} {last}".strip() or profile.get("name"), 150)
    return {
        "full_name": full_name,
        "phone": normalize_phone(profile.get("phone") or account_phone),
        "city": _clean(profile.get("city"), 100),
        "region": _clean(profile.get("region"), 200),
        "contact_time": _clean(profile.get("contact_time"), 100),
    }


def get_user_activity_summary(phone: str) -> dict:
    """Real counts shared by site profile and bot profile card."""
    profile = get_user_profile(phone)
    if not profile:
        return {}
    user_id = int(profile["id"])
    normalized = profile["phone"]
    summary = {
        "analyses": 0, "shop_checkouts": 0, "hair_orders": 0,
        "market_listings": 0, "market_offers": 0, "market_conversations": 0,
        "reviews": 0, "unread_notifications": 0, "bot_connected": False,
    }
    try:
        with get_giso_db_conn() as conn:
            summary["analyses"] = conn.execute(
                "SELECT COUNT(*) FROM analyses WHERE user_id=? OR phone=?", (user_id, normalized)
            ).fetchone()[0]
            summary["shop_checkouts"] = conn.execute(
                "SELECT COUNT(DISTINCT CASE WHEN checkout_id IS NOT NULL THEN 'c-' || checkout_id ELSE 'o-' || id END) "
                "FROM product_orders WHERE user_id=? OR phone=?", (user_id, normalized)
            ).fetchone()[0]
            summary["hair_orders"] = conn.execute(
                "SELECT COUNT(*) FROM hair_orders WHERE user_id=? OR phone=?", (user_id, normalized)
            ).fetchone()[0]
            summary["market_listings"] = conn.execute(
                "SELECT COUNT(*) FROM hair_listings WHERE seller_user_id=? AND COALESCE(deleted_at,'')=''", (user_id,)
            ).fetchone()[0]
            summary["market_offers"] = conn.execute(
                "SELECT COUNT(*) FROM buyer_offers WHERE buyer_user_id=?", (user_id,)
            ).fetchone()[0]
            summary["market_conversations"] = conn.execute(
                "SELECT COUNT(*) FROM buyer_offers o JOIN hair_listings l ON l.id=o.listing_id "
                "WHERE (o.buyer_user_id=? OR l.seller_user_id=?) AND (o.status IN ('accepted','sold') OR o.chat_closed=1)",
                (user_id, user_id),
            ).fetchone()[0]
            summary["reviews"] = conn.execute(
                "SELECT COUNT(*) FROM reviews WHERE user_id=? OR phone=?", (user_id, normalized)
            ).fetchone()[0]
            bot_row = conn.execute(
                "SELECT 1 FROM giso_users WHERE phone=? AND contact_shared=1 AND COALESCE(bale_id,'')!='' LIMIT 1",
                (normalized,),
            ).fetchone()
            summary["bot_connected"] = bool(bot_row)
            summary["unread_notifications"] = conn.execute(
                "SELECT COUNT(*) FROM giso_notifications WHERE target_role='user' AND recipient_id=? AND status='unread'",
                (normalized,),
            ).fetchone()[0]
    except Exception as exc:
        logger.warning("profile activity summary failed: %s", exc)
    return summary


__all__ = ["PROFILE_FIELDS", "get_user_profile", "update_user_profile", "safe_form_defaults", "get_user_activity_summary"]


def is_bot_profile_edit_locked(phone: str) -> bool:
    """True اگر ویرایش پروفایل در «ربات» طبق سیاست ۱۵ روزه قفل باشد.

    سیاست فعلی (update_user_profile): هر ویرایش validated، last_profile_edit_at را
    به‌روز می‌کند و تا ۱۵ روز اجازه‌ی ویرایش بعدی نمی‌دهد. این تابع همان گارد را
    برای نمایش پیامِ قفل قبل از ورود به فرمِ ویرایش در ربات منعکس می‌کند.
    """
    normalized = normalize_phone(phone or "")
    if not normalized:
        return False
    try:
        profile = get_user_profile(normalized)
        last_edit = str((profile or {}).get("last_profile_edit_at") or "").strip()
        if not last_edit:
            return False
        allowed_at = datetime.fromisoformat(last_edit) + timedelta(days=15)
        return datetime.now() < allowed_at
    except (TypeError, ValueError):
        return False
    except Exception:
        return False


def build_user_status_report(phone: str) -> str:
    """گزارش وضعیت کوتاه کاربر برای شروع گفتگوی مشاور هوشمند شخصی (اعداد واقعی)."""
    try:
        s = get_user_activity_summary(phone)
        if not s:
            return ""

        def _n(v):
            try:
                return str(int(v or 0)).translate(str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹"))
            except Exception:
                return str(v or 0)

        lines = [
            "📊 نگاهی به فعالیت شما در گیسو:",
            f"🔬 آنالیز ثبت‌شده: {_n(s.get('analyses'))}",
            f"🛍 سفارش خرید: {_n(s.get('shop_checkouts'))}",
            f"💇 درخواست فروش مو: {_n(s.get('hair_orders'))}",
            f"🏪 آگهی بازارچه: {_n(s.get('market_listings'))}  ·  💬 گفتگوی بازارچه: {_n(s.get('market_conversations'))}",
            f"🔔 اعلان خوانده‌نشده: {_n(s.get('unread_notifications'))}",
        ]
        return "\n".join(lines)
    except Exception:
        return ""


__all__ = [
    "PROFILE_FIELDS", "get_user_profile", "update_user_profile",
    "safe_form_defaults", "get_user_activity_summary",
    "is_bot_profile_edit_locked", "build_user_status_report",
]
