# -*- coding: utf-8 -*-
"""صف تک‌به‌تک درخواست‌های بازارچه مو در ربات (ادمین معمولی + سوپر)."""
import logging
import time

from giso.base import get_giso_db_conn, _fa_num, display_phone, to_shamsi

logger = logging.getLogger("giso_bot_market_admin")
_STATUS_CACHE = {"at": 0.0, "values": None}

STATUS_FA = {
    "pending_review": "🔍 در حال بررسی",
    "published": "✅ انتشار داده شد",
    "rejected": "❌ رد شد",
    "negotiating": "💬 در حال مذاکره",
    "paused": "⏸ متوقف",
    "sold": "💰 فروخته‌شده",
}


def market_menu_kb(is_super: bool = False):
    from telegram import KeyboardButton, ReplyKeyboardMarkup
    rows = [[KeyboardButton("📋 درخواست‌های بازارچه"), KeyboardButton("🧑‍💼 خریداران منتظر")]]
    if is_super:
        rows += [[KeyboardButton("📊 وضعیت بازارچه"), KeyboardButton("💳 تعرفه اعتباری")]]
    rows.append([KeyboardButton("🔙 بازگشت")])
    return ReplyKeyboardMarkup(rows,
        resize_keyboard=True,
    )


def market_menu_text() -> str:
    return (
        "🏪 بازارچه مو — درخواست‌ها\n"
        "━━━━━━━━━━━━━━━━\n"
        "آگهی‌هایی که فروشنده برای بازارچه ثبت کرده، اینجا تک‌به‌تک می‌آید.\n"
        "درخواست فروش مستقیم به گیسو در «💇 خرید مو» جداست."
    )


def _list_ids(limit=200):
    try:
        with get_giso_db_conn() as conn:
            rows = conn.execute(
                "SELECT id FROM hair_listings WHERE status='pending_review' "
                "AND COALESCE(deleted_at,'')='' ORDER BY id DESC LIMIT ?",
                (int(limit),),
            ).fetchall()
        return [int(r["id"]) for r in rows]
    except Exception as exc:
        logger.error("market list ids: %s", exc)
        return []


def _get(listing_id):
    try:
        with get_giso_db_conn() as conn:
            row = conn.execute(
                "SELECT l.*, u.name AS seller_name, u.phone AS seller_phone "
                "FROM hair_listings l LEFT JOIN giso_web_auth u ON u.id=l.seller_user_id "
                "WHERE l.id=?",
                (int(listing_id),),
            ).fetchone()
        return dict(row) if row else None
    except Exception as exc:
        logger.error("market get: %s", exc)
        return None


def _set_status(listing_id, status):
    now = time.strftime("%Y-%m-%d %H:%M:%S")
    try:
        with get_giso_db_conn() as conn:
            if status == "published":
                conn.execute(
                    "UPDATE hair_listings SET status='published', published_at=COALESCE(NULLIF(published_at,''), ?), "
                    "updated_at=?, reject_reason='' WHERE id=? AND COALESCE(deleted_at,'')=''",
                    (now, now, int(listing_id)),
                )
            elif status == "rejected":
                conn.execute(
                    "UPDATE hair_listings SET status='rejected', updated_at=?, "
                    "reject_reason='آگهی با قوانین بازارچه مطابقت ندارد.' "
                    "WHERE id=? AND COALESCE(deleted_at,'')=''",
                    (now, int(listing_id)),
                )
            else:
                conn.execute(
                    "UPDATE hair_listings SET status='pending_review', updated_at=? "
                    "WHERE id=? AND COALESCE(deleted_at,'')=''",
                    (now, int(listing_id)),
                )
            conn.commit()
        try:
            from giso.marketplace.services import notify_listing_status
            from types import SimpleNamespace
            row = _get(listing_id)
            if row:
                notify_listing_status(SimpleNamespace(**row))
        except Exception:
            pass
        _STATUS_CACHE.update(at=0.0, values=None)
        return True
    except Exception as exc:
        logger.error("market set status: %s", exc)
        return False


def _card(row, idx, total):
    return (
        f"🏪 آگهی بازارچه #{_fa_num(row.get('id'))}\n"
        "━━━━━━━━━━━━━━━━\n"
        f"📄 {_fa_num(idx + 1)} از {_fa_num(total)}\n"
        "━━━━━━━━━━━━━━━━\n"
        f"👤 فروشنده: {row.get('seller_name') or '—'}\n"
        f"📱 شماره: {display_phone(row.get('seller_phone') or '')}\n"
        f"📍 شهر: {row.get('city') or row.get('region') or '—'}\n"
        f"📏 طول: {_fa_num(row.get('length_cm') or 0)} سانتی‌متر\n"
        f"🛡 سلامت: {row.get('hair_health') or '—'}\n"
        f"💰 قیمت فروشنده: {_fa_num(row.get('seller_asking_price') or 0)} تومان\n"
        f"📌 وضعیت: {STATUS_FA.get(row.get('status'), row.get('status'))}\n"
        f"📅 ثبت: {to_shamsi(row.get('created_at'))}"
    )


def _kb(listing_id, idx, total):
    from telegram import InlineKeyboardButton, InlineKeyboardMarkup
    rows = [[
        InlineKeyboardButton("🔍 در حال بررسی", callback_data=f"mkt_act|{listing_id}|review|{idx}"),
        InlineKeyboardButton("✅ انتشار", callback_data=f"mkt_act|{listing_id}|publish|{idx}"),
        InlineKeyboardButton("❌ رد شد", callback_data=f"mkt_act|{listing_id}|reject|{idx}"),
    ]]
    nav = []
    if idx > 0:
        nav.append(InlineKeyboardButton("◀️ قبلی", callback_data=f"mkt_pg|{idx - 1}"))
    if idx < total - 1:
        nav.append(InlineKeyboardButton("بعدی ▶️", callback_data=f"mkt_pg|{idx + 1}"))
    if nav:
        rows.append(nav)
    rows.append([InlineKeyboardButton("🔙 بازگشت", callback_data="mkt_back")])
    return InlineKeyboardMarkup(rows)


async def show_market_paged(message, idx=0):
    ids = _list_ids()
    if not ids:
        await message.reply_text(
            "📭 درخواست بازارچه‌ای در صف بررسی نیست.",
            reply_markup=market_menu_kb(),
        )
        return 0
    idx = max(0, min(int(idx or 0), len(ids) - 1))
    row = _get(ids[idx])
    if not row:
        await message.reply_text("آگهی پیدا نشد.", reply_markup=market_menu_kb())
        return 0
    await message.reply_text(
        _card(row, idx, len(ids)),
        reply_markup=_kb(row["id"], idx, len(ids)),
    )
    return len(ids)


async def handle_market_callback(query, data):
    from telegram import InlineKeyboardMarkup
    msg = query.message
    if data == "mkt_back":
        await msg.reply_text(market_menu_text(), reply_markup=market_menu_kb())
        return
    if data.startswith("mkt_pg|"):
        try:
            idx = int(data.split("|")[1])
        except (ValueError, IndexError):
            idx = 0
        await show_market_paged(msg, idx)
        return
    if data.startswith("mkt_act|"):
        parts = data.split("|")
        try:
            lid, action, idx = int(parts[1]), parts[2], int(parts[3])
        except (ValueError, IndexError):
            return
        status = {"review": "pending_review", "publish": "published", "reject": "rejected"}.get(action)
        if not status:
            return
        ok = _set_status(lid, status)
        label = STATUS_FA.get(status, status)
        try:
            await query.answer(f"{label}" if ok else "خطا")
        except Exception:
            pass
        if action == "publish" and ok:
            await msg.reply_text(f"✅ آگهی #{_fa_num(lid)} در بازارچه مو منتشر شد.")
        elif action == "reject" and ok:
            await msg.reply_text(f"❌ آگهی #{_fa_num(lid)} رد شد.")
        else:
            await msg.reply_text(f"🔍 آگهی #{_fa_num(lid)} در صف «در حال بررسی» ماند.")
        await show_market_paged(msg, idx)

async def show_pending_buyers(message):
    with get_giso_db_conn() as conn:
        rows=conn.execute("SELECT p.id,p.request_name,p.request_city,p.buyer_type,u.phone FROM buyer_profiles p LEFT JOIN giso_web_auth u ON u.id=p.user_id WHERE p.verification_status='pending' ORDER BY p.id DESC LIMIT 10").fetchall()
    if not rows:
        await message.reply_text("📭 خریدار منتظر بررسی وجود ندارد.",reply_markup=market_menu_kb())
        return
    from telegram import InlineKeyboardButton,InlineKeyboardMarkup
    for r in rows:
        await message.reply_text(f"🧑‍💼 درخواست خریدار #{_fa_num(r['id'])}\nنام: {r['request_name'] or '—'}\nشهر: {r['request_city'] or '—'}\nشماره: {display_phone(r['phone'] or '')}",reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("✅ تأیید",callback_data=f"work_buyer|verify|{r['id']}"),InlineKeyboardButton("❌ رد",callback_data=f"work_buyer|reject|{r['id']}")]]))

async def show_market_status(message,is_super=False):
    now = time.monotonic()
    vals = _STATUS_CACHE.get("values") if now - float(_STATUS_CACHE.get("at") or 0) < 15 else None
    if vals is None:
        with get_giso_db_conn() as conn:
            vals={"pending":conn.execute("SELECT COUNT(*) FROM hair_listings WHERE status='pending_review'").fetchone()[0],"active":conn.execute("SELECT COUNT(*) FROM hair_listings WHERE status IN ('published','negotiating')").fetchone()[0],"buyers":conn.execute("SELECT COUNT(*) FROM buyer_profiles WHERE verification_status='pending'").fetchone()[0],"offers":conn.execute("SELECT COUNT(*) FROM buyer_offers WHERE created_at>=date('now','localtime')").fetchone()[0],"chats":conn.execute("SELECT COUNT(*) FROM marketplace_messages WHERE created_at>=date('now','localtime')").fetchone()[0],"sold":conn.execute("SELECT COUNT(*) FROM buyer_offers WHERE status='sold' AND sold_at>=date('now','localtime')").fetchone()[0]}
        _STATUS_CACHE.update(at=now, values=vals)
    await message.reply_text("📊 وضعیت بازارچه\n━━━━━━━━━━━━━━━━\n"+"\n".join([f"آگهی منتظر: {_fa_num(vals['pending'])}",f"آگهی فعال: {_fa_num(vals['active'])}",f"خریدار منتظر: {_fa_num(vals['buyers'])}",f"پیشنهاد امروز: {_fa_num(vals['offers'])}",f"پیام امروز: {_fa_num(vals['chats'])}",f"فروش موفق امروز: {_fa_num(vals['sold'])}"]),reply_markup=market_menu_kb(is_super))

async def show_credit_tariffs(message):
    from giso.marketplace.settings import marketplace_settings
    s=marketplace_settings()
    text=("💳 تعرفه امکانات اعتباری\n━━━━━━━━━━━━━━━━\n"
          f"نردبان: {_fa_num(s['promo_bump_price'])} تومان\nفروش فوری: {_fa_num(s['promo_urgent_price'])} تومان\nویژه: {_fa_num(s['promo_featured_price'])} تومان\n"
          f"اعلان ۷ روزه: {_fa_num(s['buyer_alert_7_price'])} تومان\nاعلان ۳۰ روزه: {_fa_num(s['buyer_alert_30_price'])} تومان\n۵ پیشنهاد اضافه: {_fa_num(s['buyer_bonus_price'])} تومان\n\nویرایش امن تعرفه‌ها از پنل سایت انجام می‌شود.")
    await message.reply_text(text,reply_markup=market_menu_kb(True))
