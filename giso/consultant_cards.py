# -*- coding: utf-8 -*-
"""giso/consultant_cards.py — کارت محصول برای چت/گزارش مشاور AI (قابلیت C).

ماژولِ مستقل و بدون منطق تجاری طرف کاربر. فقط «تبدیلِ خروجیِ موتورِ توصیه
(یا لیست محصولات)» به یک لیستِ نرمال‌شده از کارت‌های محصول (حداکثر ۳ کارت)
را انجام می‌دهد تا صفحه/چتِ مشاور بتواند بدون تکرارِ منطق، کارت با عکس +
قیمت + دکمه خرید نشان دهد.

هرجا خواستی در گزارش یا چت مشاور محصول پیشنهاد بدهی:
    from giso.consultant_cards import build_product_cards
    cards = build_product_cards(recommendation_data)   # → list[ProductCard]

⚠️ قوانین سناریو: کد جدید به bot.py و analysis.py اضافه نمی‌شود؛ این ماژول
مستقل است و فقط (در صورت نیاز) ۱-۲ خط فراخوانی در محل استفاده اضافه می‌شود.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict, field
from typing import Any, Dict, List, Optional

MAX_CARDS = 3
# دسته‌هایی که «غذایی/ویژه» محسوب می‌شوند و به‌جای خرید معمولی «سفارش خاص» می‌گیرند.
_SPECIAL_ORDER_HINTS = ("food", "edible", "special", "خوراک", "غذا", "ویژه")


@dataclass
class ProductCard:
    """نمای یک کارت محصول در مشاور."""

    product_id: int
    name: str
    price: int
    image_url: str = ""
    category: str = ""
    reason: str = ""
    is_special_order: bool = False
    sell_url: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def _image_url(path: Optional[str]) -> str:
    """تبدیل مسیر ذخیره‌شده به آدرس public برای قالب (پیشوند /static/)."""
    if not path:
        return ""
    p = str(path).strip().lstrip("/")
    if p.startswith("static/"):
        return "/" + p
    return "/static/" + p


def _category_name(raw: Optional[str]) -> str:
    """نام فارسیِ خوانا برای دسته؛ در نبود آن، خود مقدار (یا خالی)."""
    mapping = {"hair": "مراقبت مو", "face": "مراقبت پوست", "beauty": "زیبایی"}
    if not raw:
        return ""
    return mapping.get(str(raw).strip().lower(), str(raw).strip())


def _is_special_order(category: Optional[str], name: Optional[str] = "") -> bool:
    blob = f"{category or ''} {name or ''}".lower()
    return any(k in blob for k in _SPECIAL_ORDER_HINTS)


def _normalize_one(item: Dict[str, Any]) -> Optional[ProductCard]:
    """یک رکوردِ محصول/توصیه را به ProductCard تبدیل می‌کند (نرمال‌سازی امن)."""
    if not isinstance(item, dict):
        return None
    try:
        product_id = int(item.get("product_id") or item.get("id") or 0) or 0
    except (TypeError, ValueError):
        product_id = 0
    if not product_id:
        return None
    try:
        price = int(item.get("price") or 0)
    except (TypeError, ValueError):
        price = 0
    name = str(item.get("name") or item.get("title") or "محصول").strip()
    category = item.get("category") or ""
    reason = str(
        item.get("reason") or item.get("personalized_reason")
        or item.get("description") or ""
    ).strip()[:160]
    image_url = _image_url(item.get("image_path") or item.get("image_url"))
    sell_url = str(item.get("sell_url") or "").strip()
    if not sell_url:
        sell_url = f"/shop/product/{product_id}"
    return ProductCard(
        product_id=product_id,
        name=name,
        price=max(0, price),
        image_url=image_url,
        category=_category_name(category),
        reason=reason,
        is_special_order=_is_special_order(category, name),
        sell_url=sell_url,
    )


def build_product_cards(
    consultant_response: Optional[Any], *, max_cards: int = MAX_CARDS
) -> List[ProductCard]:
    """تبدیل خروجیِ توصیه به لیست کارت محصول (حداکثر ۳ کارت).

    Args:
        consultant_response:
            - یک dict حاوی کلید `recommendations` (خروجیِ get_recommendation_for_user)،
            - یا یک dict حاوی کلید `items`،
            - یا خودِ لیستِ رکوردهای محصول.
    Returns:
        لیستِ حداکثر `max_cards` کارتِ نرمال‌شده. اگر ورودی نامعتبر بود، لیست خالی.
    """
    if not isinstance(max_cards, int) or max_cards < 1:
        max_cards = MAX_CARDS

    items: List[Any] = []
    if isinstance(consultant_response, dict):
        for key in ("recommendations", "items", "products"):
            if isinstance(consultant_response.get(key), list):
                items = consultant_response[key]
                break
    elif isinstance(consultant_response, list):
        items = consultant_response

    cards: List[ProductCard] = []
    for it in items:
        if len(cards) >= max_cards:
            break
        card = _normalize_one(it if isinstance(it, dict) else {})
        if card is not None:
            cards.append(card)
    return cards


def build_cards_for_user(user_phone: str = "", *, max_cards: int = MAX_CARDS) -> List[ProductCard]:
    """راحتی: توصیه را از موتور موجود می‌گیرد و به کارت محصول تبدیل می‌کند.

    کاملاً امن است؛ هر خطای داخلی (موتور توصیه یا دیتابیس) به لیست خالی تبدیل
    می‌شود تا صفحهٔ مشاور هیچ‌وقت از این بابت خطا ندهد.
    """
    try:
        from giso.recommendation_service import get_recommendation_for_user
        data = get_recommendation_for_user(user_phone or "", max_items=max_cards * 2)
        return build_product_cards(data, max_cards=max_cards)
    except Exception:
        return []


__all__ = ["ProductCard", "build_product_cards", "build_cards_for_user", "MAX_CARDS"]
