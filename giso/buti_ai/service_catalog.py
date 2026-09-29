# -*- coding: utf-8 -*-
"""Service catalog for آینه زیبایی گیسو / Buti AI.

This module is intentionally small and declarative. Service-specific flow logic
stays in each service folder (eyebrow/, nail/, hair_color/, lip/).
"""
from __future__ import annotations

from typing import Dict, Iterable, List

SERVICE_EYEBROW = "eyebrow"
SERVICE_NAIL = "nail"
SERVICE_HAIR_COLOR = "hair_color"
SERVICE_LIP = "lip_shading"

SERVICE_SLUGS = {
    SERVICE_NAIL: "nail",
    SERVICE_HAIR_COLOR: "hair-color",
    SERVICE_LIP: "lip-shading",
}

SLUG_TO_SERVICE = {slug: key for key, slug in SERVICE_SLUGS.items()}

SERVICE_CATALOG: Dict[str, Dict[str, object]] = {
    SERVICE_EYEBROW: {
        "key": SERVICE_EYEBROW,
        "slug": "eyebrow",
        "title": "آینه ابرو گیسو",
        "short_title": "ابرو",
        "icon": "🪞",
        "badge": "فعال",
        "tag": "PMU",
        "description": "مدل ابروی دلخواهت را روی عکس خودت ببین؛ فقط محدوده ابرو تغییر می‌کند.",
        "meta": ["ماسک ابرو", "قبل/بعد", "اتصال به مراکز ابرو"],
        "image": "brows/eyebrow_ai_mirror.jpg",
        "sample_dir": "brows",
        "upload_sample": "brows/upload_face_only.jpg",
        "image_blueprint": "buti_ai",
        "service_type": "eyebrow",
        "beauty_center_service": "brow",
        "status": "active",
    },
    SERVICE_NAIL: {
        "key": SERVICE_NAIL,
        "slug": SERVICE_SLUGS[SERVICE_NAIL],
        "title": "آینه ناخن گیسو",
        "short_title": "ناخن",
        "icon": "💅",
        "badge": "جدید",
        "tag": "Nail",
        "description": "فرم و رنگ ناخن را روی عکس دست خودت ببین؛ مناسب انتخاب طرح قبل از رزرو.",
        "meta": ["نود، فرنچ، بیبی‌بومر", "خروجی کم‌ریسک", "مناسب سالن‌دارها"],
        "image": "services/nail/nude_minimal.jpg",
        "sample_dir": "services/nail",
        "upload_sample": "services/nail/upload_sample.jpg",
        "image_blueprint": "buti_ai",
        "service_type": "nail",
        "beauty_center_service": "nail",
        "status": "active",
    },
    SERVICE_HAIR_COLOR: {
        "key": SERVICE_HAIR_COLOR,
        "slug": SERVICE_SLUGS[SERVICE_HAIR_COLOR],
        "title": "آینه رنگ و لایت مو گیسو",
        "short_title": "رنگ مو",
        "icon": "🎨",
        "badge": "جدید",
        "tag": "Hair Color",
        "description": "رنگ، لایت و فیس‌فریم را قبل از هزینه روی موی خودت مقایسه کن.",
        "meta": ["رنگ و لایت", "بالیاژ و فیس‌فریم", "بازار قوی سالن‌ها"],
        "image": "services/coming_soon.jpg",
        "sample_dir": "services/hair_color",
        "upload_sample": "services/hair_color/upload_sample.jpg",
        "image_blueprint": "buti_ai",
        "service_type": "hair_color",
        "beauty_center_service": "hair_color",
        "status": "planned",
    },
    SERVICE_LIP: {
        "key": SERVICE_LIP,
        "slug": SERVICE_SLUGS[SERVICE_LIP],
        "title": "آینه لب و شیدینگ گیسو",
        "short_title": "لب",
        "icon": "💋",
        "badge": "جدید",
        "tag": "Lip PMU",
        "description": "شیدینگ، تینت و کانتور لب را با حفظ چهره روی عکس خودت ببین.",
        "meta": ["شیدینگ و کانتور", "فقط ماسک لب", "مناسب PMU"],
        "image": "services/lip_shading/natural_shading.jpg",
        "sample_dir": "services/lip_shading",
        "upload_sample": "services/lip_shading/upload_sample.jpg",
        "image_blueprint": "buti_ai",
        "service_type": "lip_shading",
        "beauty_center_service": "lip_shading",
        "status": "active",
    },
}


def supported_service_keys() -> List[str]:
    return [SERVICE_NAIL, SERVICE_HAIR_COLOR, SERVICE_LIP]


def service_for_slug(slug: str) -> str:
    return SLUG_TO_SERVICE.get(str(slug or "").strip().lower(), "")


def slug_for_service(service_key: str) -> str:
    service_key = str(service_key or "").strip().lower()
    return str(SERVICE_CATALOG.get(service_key, {}).get("slug") or SERVICE_SLUGS.get(service_key) or service_key)


def get_service_meta(service_key: str) -> Dict[str, object]:
    service_key = str(service_key or "").strip().lower()
    return dict(SERVICE_CATALOG.get(service_key) or {})


def mirror_services(eyebrow_href: str, service_hrefs: Dict[str, str] | None = None) -> List[Dict[str, object]]:
    service_hrefs = service_hrefs or {}
    items: List[Dict[str, object]] = []
    for key in (SERVICE_EYEBROW, SERVICE_NAIL, SERVICE_HAIR_COLOR, SERVICE_LIP):
        item = dict(SERVICE_CATALOG[key])
        item["href"] = eyebrow_href if key == SERVICE_EYEBROW else service_hrefs.get(key, "#")
        items.append(item)
    return items


__all__ = [
    "SERVICE_CATALOG",
    "SERVICE_EYEBROW",
    "SERVICE_NAIL",
    "SERVICE_HAIR_COLOR",
    "SERVICE_LIP",
    "get_service_meta",
    "mirror_services",
    "service_for_slug",
    "slug_for_service",
    "supported_service_keys",
]
