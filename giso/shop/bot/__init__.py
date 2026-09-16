# -*- coding: utf-8 -*-
"""giso/shop/bot — منوها و هندلرهای ربات فروشگاه (فاز B).

این فایل یک لایه dispatch بسیار کوچک روی handlers.py است تا callbackهایی که
پیاده‌سازی‌شان پایین‌تر از return قدیمی handlers قرار دارند، واقعاً reachable
بمانند؛ بدون تغییر معماری bot.py یا شکستن handlers.py.
"""
from giso.shop.bot import handlers as _handlers

_legacy_handle_shop_bot_callback = _handlers.handle_shop_bot_callback
_legacy_handle_shop_bot_text = _handlers.handle_shop_bot_text


async def handle_shop_bot_text(msg, text, uid, phone, existing, user_states, context=None) -> bool:
    """Delegate to Shop; normal admins receive the complete operational menu."""
    return await _legacy_handle_shop_bot_text(
        msg, text, uid, phone, existing, user_states, context
    )


async def handle_shop_bot_callback(query, uid, phone, context=None) -> bool:
    """Dispatch امن callbackهای فروشگاه بدون refactor در bot.py."""
    data = query.data or ""
    if data == "shop_cfg_visibility" or data.startswith("shop_vis_toggle|"):
        try:
            await query.answer("این تنظیمات ساده‌سازی شده است", show_alert=True)
        except Exception:
            pass
        return True
    callback_family = (
        data.startswith((
            "shop_ord_pg|", "shop_ord_st|", "shop_edit|",
            "shop_stock|", "shop_del|"
        ))
        or data == "shop_back_menu"
    )
    if callback_family:
        try:
            if not (_handlers._is_super_admin(uid, phone) or _handlers._shop_admin_allowed(uid)):
                try:
                    await query.answer("⛔ دسترسی به این بخش مجاز نیست.", show_alert=True)
                except Exception:
                    pass
                return True

            # handlers.py در نسخه فعلی این map را در scope بالاتر دریافت می‌کند؛
            # اگر در محیطی وجود نداشت، fallback به dict خالی است.
            user_states = getattr(_handlers, "user_states", {})
            msg = getattr(query, "message", None)
            if data.startswith(("shop_ord_pg|", "shop_ord_st|")) or data == "shop_back_menu":
                handled = await _handlers._handle_shop_order_callbacks(
                    query, data, uid, phone, msg, user_states
                )
            else:
                handled = await _handlers._handle_product_callbacks(
                    query, data, uid, phone, msg, user_states
                )
            if handled:
                return True
        except Exception:
            # callback ناشناخته/خراب به handler قدیمی سپرده می‌شود.
            pass
    return await _legacy_handle_shop_bot_callback(query, uid, phone, context)


# bot.py مستقیماً submodule handlers را import می‌کند؛ چون package قبل از
# submodule load می‌شود، این patch entry-point را بدون دست‌زدن به bot.py اعمال می‌کند.
_handlers.handle_shop_bot_callback = handle_shop_bot_callback
_handlers.handle_shop_bot_text = handle_shop_bot_text

handle_shop_bot_photo = _handlers.handle_shop_bot_photo

__all__ = ["handle_shop_bot_text", "handle_shop_bot_callback", "handle_shop_bot_photo"]
