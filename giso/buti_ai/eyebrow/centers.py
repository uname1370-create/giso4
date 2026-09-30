# -*- coding: utf-8 -*-
"""اتصال نازک آینه ابرو به مراکز زیبایی گیسو.

مالک سناریو همچنان Buti AI است؛ برای فهرست مرکز فقط از API عمومی
`giso.beauty_centers.services.list_public_centers` استفاده می‌کنیم.
"""
from __future__ import annotations

import logging

logger = logging.getLogger("giso_buti_ai_eyebrow_centers")

BUTI_EYEBROW_SERVICE = "eyebrow"
BEAUTY_CENTER_BROW_SERVICE = "brow"
DEFAULT_CITY = "مشهد"


def active_eyebrow_centers(city: str = "", limit: int = 3) -> list[dict]:
    """مراکز فعال منتشرشده که خدمت ابرو را ارائه می‌کنند."""
    try:
        from giso.beauty_centers.services import list_public_centers

        return list_public_centers(
            city=str(city or "").strip(),
            service=BEAUTY_CENTER_BROW_SERVICE,
            limit=max(1, min(12, int(limit or 3))),
        )
    except Exception as exc:
        logger.warning("Buti AI eyebrow centers lookup failed: %s", str(exc)[:160])
        return []


def has_active_eyebrow_centers(city: str = "") -> bool:
    return bool(active_eyebrow_centers(city=city, limit=1))



def enrich_eyebrow_center_suggestions(centers: list[dict], candidate: dict | None = None, city: str = "") -> list[dict]:
    """افزودن متن و اولویت مخصوص آینه ابرو به کارت‌های مرکز، بدون تغییر API عمومی مراکز."""
    candidate = candidate or {}
    final_label = str(candidate.get("final_label") or "مدل انتخابی ابرو").strip()
    target_city = str(city or "").strip()
    enriched: list[dict] = []
    for index, center in enumerate(centers or [], start=1):
        item = dict(center or {})
        services = item.get("services") if isinstance(item.get("services"), list) else []
        service_labels = item.get("service_labels") if isinstance(item.get("service_labels"), list) else []
        has_brow = BEAUTY_CENTER_BROW_SERVICE in services or any("ابرو" in str(label) for label in service_labels)
        city_match = bool(target_city and str(item.get("city") or "").strip() == target_city)
        score = 0
        score += 45 if has_brow else 0
        score += 20 if city_match else 0
        score += 15 if item.get("is_featured") else 0
        try:
            score += min(20, int((item.get("feedback") or {}).get("score100") or 0) // 5)
        except Exception:
            pass
        item["mirror_rank"] = index
        item["mirror_score"] = max(0, min(100, score))
        item["mirror_match_reason"] = (
            f"برای اجرای {final_label}، این مرکز به‌عنوان ارائه‌دهنده خدمات ابرو پیشنهاد شده است."
            if has_brow else
            f"قبل از رزرو، از مرکز درباره اجرای {final_label} سؤال کن."
        )
        tags = ["خدمات ابرو"] if has_brow else []
        if city_match:
            tags.append("همان شهر")
        if item.get("feedback") and item.get("feedback", {}).get("label"):
            tags.append(str(item["feedback"]["label"]))
        item["mirror_tags"] = tags[:4]
        enriched.append(item)
    enriched.sort(key=lambda c: (-int(c.get("mirror_score") or 0), int(c.get("mirror_rank") or 0)))
    return enriched

def user_default_city(current_user) -> str:
    """شهر پیش‌فرض برای فرم انتظار؛ بدون وابستگی سخت به مدل کاربر."""
    try:
        city = str(getattr(current_user, "city", "") or "").strip()
        return city or DEFAULT_CITY
    except Exception:
        return DEFAULT_CITY


def user_default_phone(current_user) -> str:
    try:
        return str(getattr(current_user, "phone", "") or "").strip()
    except Exception:
        return ""


__all__ = [
    "BEAUTY_CENTER_BROW_SERVICE",
    "BUTI_EYEBROW_SERVICE",
    "DEFAULT_CITY",
    "active_eyebrow_centers",
    "enrich_eyebrow_center_suggestions",
    "has_active_eyebrow_centers",
    "user_default_city",
    "user_default_phone",
]
