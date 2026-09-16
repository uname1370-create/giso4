# -*- coding: utf-8 -*-
"""Bale admin menus and callbacks for Beauty Centers."""
import html
import time

_STATUS_CACHE = {"at": 0.0, "values": None}

from giso.base import _fa_num
from giso.beauty_centers.services import STATUS_FA, admin_set_status, get_center, list_admin_centers


def beauty_admin_menu_kb(is_super: bool = False):
    from telegram import KeyboardButton, ReplyKeyboardMarkup
    rows = [
        [KeyboardButton("📥 درخواست‌های جدید مرکز"), KeyboardButton("🏢 مراکز منتشرشده")],
        [KeyboardButton("⏳ منقضی و متوقف")],
    ]
    if is_super:
        rows.append([KeyboardButton("📊 وضعیت مراکز"), KeyboardButton("⭐ اعتبار آگهی مراکز")])
        rows.append([KeyboardButton("⚙️ تنظیمات مراکز")])
    rows.append([KeyboardButton("🔙 بازگشت")])
    return ReplyKeyboardMarkup(rows, resize_keyboard=True)


def beauty_admin_menu_text(is_super: bool = False) -> str:
    suffix = "\n⭐ معرفی ویژه و تنظیمات فقط برای سوپرادمین است." if is_super else ""
    return "🏥 مدیریت مراکز زیبایی\n━━━━━━━━━━━━━━━━\nدرخواست‌ها، مراکز منتشرشده و گزارش‌ها را مدیریت کنید." + suffix


async def handle_beauty_owner_callback(query, owner_user_id: int, site_url: str) -> bool:
    """Show an owner's real center status; editing and messages stay on the website."""
    center = {}
    try:
        from giso.beauty_centers.services import get_owner_center
        center = get_owner_center(int(owner_user_id or 0))
    except Exception:
        center = {}
    if not center:
        try:
            await query.answer("مرکزی برای این حساب ثبت نشده است.", show_alert=True)
        except Exception:
            pass
        return False
    try:
        await query.answer()
    except Exception:
        pass
    from telegram import InlineKeyboardButton, InlineKeyboardMarkup
    site = str(site_url or "https://gisosadeghi.ir").rstrip("/")
    rows = [[
        InlineKeyboardButton("🏥 پنل مرکز", url=f"{site}/dashboard/beauty-center"),
        InlineKeyboardButton("💬 پیام‌ها", url=f"{site}/dashboard/beauty-center?tab=messages"),
    ]]
    if center.get("status") == "published" and center.get("slug"):
        rows.append([InlineKeyboardButton("🌐 صفحه عمومی مرکز", url=f"{site}/beauty-centers/{center['slug']}")])
    safe = lambda value: str(value or "—").replace("<", "‹").replace(">", "›").replace("&", "و")
    text = (
        "🏥 مرکز زیبایی من\n━━━━━━━━━━━━━━━━\n"
        f"نام: {safe(center.get('name'))}\n"
        f"وضعیت: {safe(center.get('status_label'))}\n"
        f"📍 {safe(center.get('city'))}، {safe(center.get('region'))}\n"
        f"👁 بازدید: {_fa_num(center.get('views_count') or 0)}\n"
        f"💬 استعلام قیمت: {_fa_num(center.get('price_inquiry_clicks') or 0)}\n"
        f"✨ نمایش در آنالیز: {_fa_num(center.get('analysis_impressions') or 0)}\n\n"
        "ویرایش اطلاعات و پاسخ به پیام‌ها فقط در پنل امن سایت انجام می‌شود."
    )
    await query.message.reply_text(text, reply_markup=InlineKeyboardMarkup(rows))
    return True


def _center_card(center: dict, index: int, total: int) -> str:
    safe = lambda value: str(value or "—").replace("<", "‹").replace(">", "›").replace("&", "و")
    return (
        f"🏥 مرکز زیبایی #{_fa_num(center.get('id'))}\n━━━━━━━━━━━━━━━━\n"
        f"📄 {_fa_num(index + 1)} از {_fa_num(total)}\n"
        f"نام: {safe(center.get('name'))}\nدسته: {safe(center.get('category_label'))}\nنوع: {safe(center.get('type_label'))}\n"
        f"📍 {safe(center.get('city'))}، {safe(center.get('region'))}\n"
        f"📱 {safe(center.get('business_phone'))}\n"
        f"خدمات: {safe('، '.join(center.get('service_labels') or []))}\n"
        f"💰 سطح هزینه: {safe(center.get('price_level_label'))}"
        + (f" — شروع از {_fa_num(center.get('starting_price'))} تومان\n" if center.get('starting_price') else "\n")
        + f"وضعیت: {center.get('status_label')}\n"
        f"👁 بازدید: {_fa_num(center.get('views_count') or 0)}"
    )


def _center_kb(center_id: int, index: int, total: int, scope: str):
    from telegram import InlineKeyboardButton, InlineKeyboardMarkup
    rows = []
    if scope == "pending_review":
        rows.append([
            InlineKeyboardButton("🔍 بررسی", callback_data=f"bc_act|{center_id}|review|{index}"),
            InlineKeyboardButton("✅ انتشار", callback_data=f"bc_act|{center_id}|publish|{index}"),
            InlineKeyboardButton("❌ رد", callback_data=f"bc_act|{center_id}|reject|{index}"),
        ])
    elif scope == "published":
        rows.append([InlineKeyboardButton("⏸ توقف نمایش", callback_data=f"bc_act|{center_id}|pause|{index}")])
    elif scope == "paused":
        rows.append([InlineKeyboardButton("✅ انتشار دوباره", callback_data=f"bc_act|{center_id}|publish|{index}")])
    nav = []
    if index > 0:
        nav.append(InlineKeyboardButton("◀️ قبلی", callback_data=f"bc_pg|{scope}|{index-1}"))
    if index < total - 1:
        nav.append(InlineKeyboardButton("بعدی ▶️", callback_data=f"bc_pg|{scope}|{index+1}"))
    if nav:
        rows.append(nav)
    rows.append([InlineKeyboardButton("🔙 منوی مراکز", callback_data="bc_back")])
    return InlineKeyboardMarkup(rows)


async def show_centers_paged(message, status: str = "pending_review", index: int = 0):
    centers = list_admin_centers(status)
    if not centers:
        await message.reply_text("موردی در این بخش وجود ندارد.")
        return
    index = max(0, min(int(index), len(centers) - 1))
    center = centers[index]
    await message.reply_text(_center_card(center, index, len(centers)),
                             reply_markup=_center_kb(center["id"], index, len(centers), status))


async def handle_beauty_admin_text(message, text: str, is_super: bool = False,
                                   is_admin: bool = False) -> bool:
    """Handle the isolated admin menu and fail closed for non-staff callers."""
    beauty_texts = {
        "🏥 مراکز زیبایی", "📥 درخواست‌های جدید مرکز", "🏢 مراکز منتشرشده",
        "⏳ منقضی و متوقف", "📊 وضعیت مراکز", "⭐ اعتبار آگهی مراکز",
        "⚙️ تنظیمات مراکز",
    }
    if text not in beauty_texts:
        return False
    if not (is_admin or is_super):
        await message.reply_text("⛔ این بخش فقط برای مدیران گیسو در دسترس است.")
        return True
    mapping = {
        "📥 درخواست‌های جدید مرکز": "pending_review",
        "🏢 مراکز منتشرشده": "published",
        "⏳ منقضی و متوقف": "paused",
    }
    if text == "🏥 مراکز زیبایی":
        await message.reply_text(beauty_admin_menu_text(is_super),
                                 reply_markup=beauty_admin_menu_kb(is_super))
        return True
    if text in mapping:
        await show_centers_paged(message, mapping[text], 0)
        return True
    if text == "📊 وضعیت مراکز":
        if not is_super:
            await message.reply_text("⛔ فقط سوپرادمین")
            return True
        from giso.base import get_giso_db_conn
        now=time.monotonic();values=_STATUS_CACHE.get("values") if now-float(_STATUS_CACHE.get("at") or 0)<15 else None
        if values is None:
            with get_giso_db_conn() as conn:
                active=conn.execute("SELECT COUNT(*) FROM beauty_centers WHERE status='published' AND is_active=1").fetchone()[0]
                pending=conn.execute("SELECT COUNT(*) FROM beauty_centers WHERE status IN ('pending_review','reviewing')").fetchone()[0]
                expired=conn.execute("SELECT COUNT(*) FROM beauty_centers WHERE listing_expires_at<>'' AND listing_expires_at<=datetime('now','localtime')").fetchone()[0]
            values=(active,pending,expired);_STATUS_CACHE.update(at=now,values=values)
        else: active,pending,expired=values
        await message.reply_text(f"📊 مراکز فعال: {_fa_num(active)}\nدر انتظار: {_fa_num(pending)}\nمنقضی: {_fa_num(expired)}")
        return True
    if text in ("⭐ اعتبار آگهی مراکز", "⚙️ تنظیمات مراکز"):
        if not is_super:
            await message.reply_text("⛔ این گزینه فقط برای سوپرادمین در دسترس است.")
            return True
        await message.reply_text("تعرفه و مدیریت کامل اعتبار آگهی مراکز در پنل امن سایت انجام می‌شود.")
        return True
    return False


async def handle_beauty_admin_callback(query, data: str, is_super: bool = False,
                                       is_admin: bool = False):
    """Apply center callbacks only after an explicit staff authorization signal."""
    if not (is_admin or is_super):
        try:
            await query.answer("⛔ فقط مدیران گیسو", show_alert=True)
        except Exception:
            pass
        return
    if data == "bc_back":
        await query.message.reply_text(beauty_admin_menu_text(is_super),
                                       reply_markup=beauty_admin_menu_kb(is_super))
        return
    if data.startswith("bc_pg|"):
        parts = data.split("|")
        await show_centers_paged(query.message, parts[1], int(parts[2]))
        return
    if not data.startswith("bc_act|"):
        return
    parts = data.split("|")
    if len(parts) != 4 or not parts[1].isdigit() or not parts[3].isdigit():
        try:
            await query.answer("درخواست نامعتبر است.", show_alert=True)
        except Exception:
            pass
        return
    center_id, action, index = int(parts[1]), parts[2], int(parts[3])
    target = {"review": "reviewing", "publish": "published", "reject": "rejected", "pause": "paused"}.get(action)
    if not target:
        return
    note = "اطلاعات مرکز نیازمند اصلاح است." if target == "rejected" else ""
    ok, message, center = admin_set_status(center_id, target, note)
    if ok: _STATUS_CACHE.update(at=0.0, values=None)
    try:
        await query.answer(message, show_alert=not ok)
    except Exception:
        pass
    await query.message.reply_text(("✅ " if ok else "❌ ") + message)
    await show_centers_paged(query.message, center.get("status") if center else "pending_review", index)


__all__ = ["beauty_admin_menu_kb", "beauty_admin_menu_text", "handle_beauty_admin_text",
           "handle_beauty_admin_callback", "handle_beauty_owner_callback", "show_centers_paged"]
