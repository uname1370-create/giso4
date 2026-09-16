# -*- coding: utf-8 -*-
"""مرکز اعلان سفارش فروشگاه.

- ابزارهای فرم تماس/تحویل سفارش (روزهای هفته + بازه‌های ساعتی)
- اعلان مرکزی سفارش (log_notification → پنل + بله کوتاه برای همه ادمین‌ها)
- اعلان «شیک» سوپرادمین با عکس محصول (sendPhoto؛ در نبود عکس، متن کامل)
"""
import hashlib
import json
import logging
import os
import re

logger = logging.getLogger("giso_shop_logic_checkout")

CONTACT_DAYS = ["شنبه", "یکشنبه", "دوشنبه", "سه‌شنبه", "چهارشنبه", "پنجشنبه", "جمعه"]
CONTACT_TIME_SLOTS = ["۹ تا ۱۲ ظهر", "۱۲ تا ۱۵ عصر", "۱۵ تا ۱۸ عصر", "۱۸ تا ۲۱ شب"]


def _shop_order_action_markup(order_ids):
    rows = []
    for raw_id in list(order_ids or [])[:10]:
        try:
            order_id = int(raw_id)
        except (TypeError, ValueError):
            continue
        rows.append([
            {"text": f"🚚 ارسال #{order_id}", "callback_data": f"shop_ord_st|{order_id}|shipped"},
            {"text": f"📦 تحویل #{order_id}", "callback_data": f"shop_ord_st|{order_id}|delivered"},
            {"text": f"❌ رد #{order_id}", "callback_data": f"shop_ord_st|{order_id}|rejected"},
        ])
    return {"inline_keyboard": rows} if rows else None


def _notify_admins_shop_order(text: str, order_ids=None):
    """ثبت اعلان سفارش در مرکز اعلان (پنل)؛ پیام بلهٔ سوپر توسط _send_super_order_photo می‌رود
    (اعلان شیک با عکس) تا دامنهٔ مقصد تنظیمات کاربر دست‌نخورده بماند و پیام تکراری نیاید.
    ادمین‌های معمولی (که پیام عکس سوپر را دریافت نمی‌کنند) پیام متنی دریافت می‌کنند."""
    try:
        from giso.panel.modules.notifications import log_notification
        match = re.search(r"#(\d+)", text or "")
        source_id = int(match.group(1)) if match else int(hashlib.sha1((text or "").encode("utf-8")).hexdigest()[:8], 16)
        subcategory = "checkout" if "سبد" in (text or "") else "order"
        log_notification(
            "shop", subcategory, "سفارش جدید فروشگاه", text or "",
            source_type="shop_order_center", source_id=source_id,
            destination="site",
        )
    except Exception as exc:
        logger.exception("shop order notification center failed: %s", exc)
    # اعلان بله برای ادمین‌های معمولی (سوپر از _send_super_order_photo پیام دارد)
    try:
        from giso.base import _token_from_env, _token_from_db, _http_post
        from giso.panel.modules import notifications as _notif
        token = (_token_from_env() or _token_from_db() or "").strip()
        if token:
            url = f"https://tapi.bale.ai/bot{token}/sendMessage"
            markup = _shop_order_action_markup(order_ids)
            for cid in sorted(_notif._regular_admin_ids()):
                try:
                    payload = {"chat_id": int(cid), "text": f"🛍 {text}"[:4000], "parse_mode": "HTML"}
                    if markup:
                        payload["reply_markup"] = markup
                    _http_post(url, json_payload=payload)
                except Exception as e_cid:
                    logger.debug(f"shop order bale notify to {cid} failed: {e_cid}")
    except Exception as exc:
        logger.debug(f"shop order admin bale notify failed: {exc}")


def _send_super_order_photo(product, caption: str, order_ids=None):
    """ارسال اعلان شیک سفارش به سوپرادمین‌های بله با عکس محصول.

    عکس از مسیر لوکال فایل محصول (multipart) ارسال می‌شود؛ در نبود عکس/توکن،
    فقط متن کامل ارسال می‌شود. خطاها هرگز جریان خرید را نمی‌شکنند.
    """
    try:
        from giso.panel.modules import notifications as _notif
        from giso.base import _token_from_env, _token_from_db, _http_post
        from giso.config import Config

        token = (_token_from_env() or _token_from_db() or "").strip()
        if not token:
            return
        targets = set()
        try:
            targets = {int(x) for x in _notif._super_admin_ids()}
        except Exception:
            targets = set()
        if not targets:
            return

        photo_abs = ""
        rel = (getattr(product, "image_path", "") or "").strip()
        if rel:
            for cand in (
                os.path.join(Config.GISO_DIR, "static", rel),
                os.path.join(Config.BASE_DIR, "giso", "static", rel),
                os.path.join(Config.BASE_DIR, "giso", "static", "uploads", os.path.basename(rel)),
            ):
                if os.path.exists(cand):
                    photo_abs = cand
                    break

        base = f"https://tapi.bale.ai/bot{token}"
        markup = _shop_order_action_markup(order_ids)
        for cid in targets:
            try:
                if photo_abs:
                    try:
                        import requests
                        with open(photo_abs, "rb") as fh:
                            data = {"chat_id": int(cid), "caption": caption[:1024], "parse_mode": "HTML"}
                            if markup:
                                data["reply_markup"] = json.dumps(markup, ensure_ascii=False)
                            requests.post(
                                f"{base}/sendPhoto", data=data, files={"photo": fh}, timeout=12,
                            )
                        continue
                    except Exception as e_ph:
                        logger.warning(f"super order sendPhoto to {cid} failed: {e_ph}")
                payload = {"chat_id": int(cid), "text": caption[:4000], "parse_mode": "HTML"}
                if markup:
                    payload["reply_markup"] = markup
                _http_post(f"{base}/sendMessage", json_payload=payload)
            except Exception as e_cid:
                logger.warning(f"super order notification to {cid} failed: {e_cid}")
    except Exception as exc:
        logger.exception("super order photo notification failed: %s", exc)


__all__ = ["_notify_admins_shop_order", "_send_super_order_photo", "CONTACT_DAYS", "CONTACT_TIME_SLOTS"]
