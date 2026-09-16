# -*- coding: utf-8 -*-
"""Small stable marketplace settings surface using the existing config store."""

MARKETPLACE_TERMS_LINES = (
    "۱. گیسو فقط بستر معرفی خریدار و فروشنده است و طرف معامله نیست.",
    "۲. توافق نهایی، قیمت‌گذاری و انجام معامله بر عهده خریدار و فروشنده است.",
    "۳. گیسو هیچ ضمانتی درباره پرداخت، کیفیت مو یا رفتار طرفین ارائه نمی‌کند.",
    "۴. اطلاعات شخصی مانند شماره تماس، آدرس و نام کامل به‌صورت عمومی نمایش داده نمی‌شود.",
    "۵. عکس مو فقط با تأیید ادمین در بازارچه منتشر می‌شود و باید فقط از مو باشد.",
    "۶. ثبت اطلاعات غیرواقعی، آگهی جعلی یا رفتار مزاحم موجب حذف حساب می‌شود.",
    "۷. توصیه می‌شود معامله در محیط امن و به‌صورت حضوری انجام شود.",
    "۸. کاربر می‌پذیرد مسئولیت انتخاب طرف معامله بر عهده خود اوست.",
    "۹. با ادامه ثبت، کاربر تأیید می‌کند این قوانین را مطالعه کرده و می‌پذیرد.",
)
DEFAULT_TERMS = "\n".join(MARKETPLACE_TERMS_LINES)
DEFAULT_DISCLAIMER = (
    "گیسو فقط بستر معرفی و ارتباط است؛ مسئولیت توافق و معامله نهایی با خریدار و فروشنده است."
)

DEFAULTS = {
    "marketplace_enabled": "1",
    "marketplace_terms": DEFAULT_TERMS,
    "marketplace_disclaimer": DEFAULT_DISCLAIMER,
    "marketplace_offer_limit": "5",
    "marketplace_buyer_alert_3_price": "25000",
    "marketplace_buyer_alert_7_price": "50000",
    "marketplace_buyer_alert_30_price": "150000",
    "marketplace_buyer_bonus_price": "30000",
    "marketplace_promo_bump_price": "25000",
    "marketplace_promo_urgent_price": "75000",
    "marketplace_promo_featured_price": "200000",
    "marketplace_renew_price": "50000",
    "marketplace_seller_features_enabled": "1",
    "marketplace_buyer_features_enabled": "1",
    "marketplace_show_highest_offer": "1",
    "marketplace_chat_enabled": "1",
}


def _get(key):
    try:
        from giso_admin import get_giso_config
        return get_giso_config(key, DEFAULTS.get(key, ""))
    except Exception:
        return DEFAULTS.get(key, "")


def marketplace_settings() -> dict:
    try:
        offer_limit = 5  # قانون ثابت بازارچه: پنج پیشنهاد پایه در هر ۲۴ ساعت
    except (TypeError, ValueError):
        offer_limit = 5
    def _price(key, default):
        try: return max(0, int(_get(key) or default))
        except (TypeError, ValueError): return default
    return {
        "enabled": str(_get("marketplace_enabled") or "1") == "1",
        "terms": str(_get("marketplace_terms") or DEFAULT_TERMS),
        "disclaimer": str(_get("marketplace_disclaimer") or DEFAULT_DISCLAIMER),
        "offer_limit": offer_limit,
        "buyer_alert_3_price": _price("marketplace_buyer_alert_3_price", 25000),
        "buyer_alert_7_price": _price("marketplace_buyer_alert_7_price", 50000),
        "buyer_alert_30_price": _price("marketplace_buyer_alert_30_price", 150000),
        "buyer_bonus_price": _price("marketplace_buyer_bonus_price", 30000),
        "promo_bump_price": _price("marketplace_promo_bump_price", 25000),
        "promo_urgent_price": _price("marketplace_promo_urgent_price", 75000),
        "promo_featured_price": _price("marketplace_promo_featured_price", 200000),
        "renew_price": _price("marketplace_renew_price", 50000),
        "seller_features_enabled": str(_get("marketplace_seller_features_enabled") or "1") == "1",
        "buyer_features_enabled": str(_get("marketplace_buyer_features_enabled") or "1") == "1",
        "show_highest_offer": str(_get("marketplace_show_highest_offer") or "1") == "1",
        "chat_enabled": str(_get("marketplace_chat_enabled") or "1") == "1",
    }


def save_marketplace_settings(values: dict) -> tuple:
    try:
        from giso_admin import set_giso_config
        current = marketplace_settings()
        set_giso_config("marketplace_enabled", "1" if values.get("enabled", current["enabled"]) else "0")
        set_giso_config("marketplace_terms", str(values.get("terms", current["terms"]) or DEFAULT_TERMS)[:5000])
        set_giso_config("marketplace_disclaimer", str(values.get("disclaimer", current["disclaimer"]) or DEFAULT_DISCLAIMER)[:5000])
        try:
            limit = max(1, min(100, int(values.get("offer_limit", current["offer_limit"]) or 10)))
        except (TypeError, ValueError):
            limit = 10
        set_giso_config("marketplace_offer_limit", "5")
        for key, fallback in (("buyer_alert_3_price",25000),("buyer_alert_7_price",50000),("buyer_alert_30_price",150000),("buyer_bonus_price",30000),("promo_bump_price",25000),("promo_urgent_price",75000),("promo_featured_price",200000),("renew_price",50000)):
            try: price = max(0, int(values.get(key, current.get(key, fallback)) or fallback))
            except (TypeError, ValueError): price = fallback
            set_giso_config("marketplace_" + key, str(price))
        set_giso_config("marketplace_seller_features_enabled", "1" if values.get("seller_features_enabled", current["seller_features_enabled"]) else "0")
        set_giso_config("marketplace_buyer_features_enabled", "1" if values.get("buyer_features_enabled", current["buyer_features_enabled"]) else "0")
        set_giso_config("marketplace_show_highest_offer", "1" if values.get("show_highest_offer", current["show_highest_offer"]) else "0")
        set_giso_config("marketplace_chat_enabled", "1" if values.get("chat_enabled", current["chat_enabled"]) else "0")
        return True, "تنظیمات بازارچه ذخیره شد."
    except Exception:
        return False, "ذخیره تنظیمات بازارچه ناموفق بود."


__all__ = [
    "marketplace_settings", "save_marketplace_settings", "MARKETPLACE_TERMS_LINES",
    "DEFAULT_TERMS", "DEFAULT_DISCLAIMER",
]
