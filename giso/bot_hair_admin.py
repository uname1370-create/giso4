# -*- coding: utf-8 -*
"""giso/bot_hair_admin.py — منوی هوشمند مدیریت فروش مو در ربات (فاز ۵ نهایی + فاز 5.1 ربات)

تجربه ادمین در ربات را با پنل جدید سایت هم‌راستا می‌کند:

  - منوی ادمین معمولی جدا از سوپرادمین با نقش عملیاتی ثابت
  - «📋 درخواست‌های فروش مو» → صفحه‌بندی تک‌به‌تک (هر بار یک درخواست + عکس + اکشن‌ها + قبلی/بعدی)
  - «📱 ویرایش با شماره کاربر» → سفارش‌های کاربر به‌صورت صفحه‌بندی‌شده
  - «👥 لیست کاربران فروش مو» → فقط کاربران با درخواست فعال + تعداد + صفحه‌بندی + ورود به سفارش‌ها
  - «📊 گزارش‌ها» → «نمایش در حال بررسی» / «نمایش رد شده» با شماره‌های ۵تایی صفحه‌بندی‌شده
  - «💬 گفتگوها» → گفتگوهای در جریان (جدیدترین بالا) — جایگزین «اعتراض‌ها»

ادمین‌های تأییدشده یک نقش عملیاتی ثابت دارند و همه گزینه‌های روزمره را می‌بینند.
status-guard اکشن‌های نامعتبر را مخفی می‌کند؛ درخواست ردشده فقط قابل بازگشایی/قیمت‌گذاری است.

هیچ وابستگی به telegram در زمان import ندارد (importها lazy هستند).
"""
import json
import logging
import os
import time

from giso.base import get_giso_db_conn, normalize_phone, _fa_num, get_persian_status, to_shamsi

logger = logging.getLogger("giso_bot_hair_admin")

HAIR_SUBOPTIONS = ("approve", "reject", "price", "note", "message", "reports",
                   "objections", "review")

CALLBACK_SUBOPTION = {
    "hair_rej": "reject",
    "hair_reject": "reject",
    "hair_approve": "approve",
    "hair_complete": "approve",
    "hair_price": "price",
    "hair_note": "note",
    "hair_msg": "message",
    "hair_review": "review",
    "hair_app": "review",
}

ACTIVE_STATUSES = ("pending", "reviewing", "priced")
# صف اصلی «درخواست‌های فروش مو» فقط درخواست‌های جدید (pending) را نشان می‌دهد؛
# درخواست‌هایی که «در حال بررسی» یا «قیمت ثبت‌شده» شدند به گزارش‌ها منتقل می‌شوند.
PENDING_QUEUE_STATUSES = ("pending",)
# وضعیت‌هایی که هنوز می‌توان قیمت نهایی ثبت کرد
PRICEABLE_STATUSES = ("pending", "reviewing", "priced")
# وضعیت‌هایی که هنوز می‌توان «در حال بررسی» زد
REVIEWABLE_STATUSES = ("pending", "reviewing", "priced")
# وضعیت‌هایی که هنوز می‌توان رد کرد
REJECTABLE_STATUSES = ("pending", "reviewing", "priced")
REPORT_PAGE_SIZE = 5

EMPTY_REQUESTS_MSG = (
    "📭 درخواست‌ها تمام شد\n"
    "━━━━━━━━━━━━━━━━\n"
    "درخواست فعال جدیدی برای فروش مو وجود ندارد.\n"
    "به محض ثبت اولین درخواست در سایت، اینجا نمایش داده می‌شود 🌸"
)
EMPTY_USERS_MSG = (
    "👥 کاربران تمام شد\n"
    "━━━━━━━━━━━━━━━━\n"
    "کاربر فعالی با درخواست فروش مو یافت نشد.\n"
    "به محض ثبت اولین درخواست، کاربر اینجا ظاهر می‌شود 🌸"
)


def get_admin_sub_options(bale_id, section: str = "hair_sale") -> dict:
    """Compatibility payload: all operational Hair actions are always enabled."""
    keys = list(HAIR_SUBOPTIONS) if section == "hair_sale" else []
    out = {key: True for key in keys}
    out.update({f"bot_{key}_visible": True for key in keys})
    return out


def is_suboption_visible(bale_id, section: str, subkey: str, channel: str = "bot") -> bool:
    """Per-admin Hair visibility was removed; approved admins use one fixed role."""
    return True


def admin_sub_allowed(bale_id, section: str, subkey: str, default: bool = True) -> bool:
    """Compatibility bypass for old callers."""
    return True


def build_admin_hair_menu(uid=None):
    """Build the fixed operational Hair menu for approved admins."""
    from telegram import KeyboardButton, ReplyKeyboardMarkup
    from giso.base import _is_super_admin

    rows = [
        [KeyboardButton("📋 درخواست‌های فروش مو")],
        [KeyboardButton("📱 ویرایش با شماره کاربر"), KeyboardButton("👥 لیست کاربران فروش مو")],
        [KeyboardButton("📊 گزارش‌ها"), KeyboardButton("💬 گفتگوها")],
        [KeyboardButton("🔙 بازگشت")],
    ]
    return ReplyKeyboardMarkup(rows, resize_keyboard=True)


def admin_hair_menu_text() -> str:
    return (
        "💇 به منوی هوشمند مدیریت فروش مو خوش آمدید:\n"
        "━━━━━━━━━━━━━━━━\n"
        "📋 درخواست‌ها با اکشن‌های سریع (رد / قیمت / بررسی / گفتگو)\n"
        "📱 ویرایش با شماره کاربر\n"
        "👥 لیست کاربران فعال فروش مو\n"
        "📊 گزارش‌ها و 💬 گفتگوها\n"
        "━━━━━━━━━━━━━━━━\n"
        "گزینه مورد نظر را انتخاب کنید:"
    )


# ═══════════════════ فهرست‌ها ═══════════════════

def _list_request_ids(limit: int = 300):
    """فقط درخواست‌های جدید (pending)؛ پس از «در حال بررسی» یا «ثبت قیمت» از صف خارج می‌شوند."""
    try:
        marks = ",".join("?" * len(PENDING_QUEUE_STATUSES))
        with get_giso_db_conn() as conn:
            rows = conn.execute(
                f"SELECT id FROM hair_orders WHERE status IN ({marks}) "
                "ORDER BY id DESC LIMIT ?",
                (*PENDING_QUEUE_STATUSES, int(limit))).fetchall()
        return [int(r["id"]) for r in rows]
    except Exception as e:
        logger.error(f"bot_hair _list_request_ids: {e}")
        return []


def _list_active_users(limit: int = 100):
    try:
        marks = ",".join("?" * len(ACTIVE_STATUSES))
        with get_giso_db_conn() as conn:
            rows = conn.execute(
                f"SELECT phone, COUNT(*) AS cnt, MAX(id) AS last_id "
                f"FROM hair_orders WHERE status IN ({marks}) AND phone != '' "
                f"GROUP BY phone ORDER BY last_id DESC LIMIT ?",
                (*ACTIVE_STATUSES, int(limit))).fetchall()
        return [{"phone": str(r["phone"]), "cnt": int(r["cnt"] or 0)} for r in rows]
    except Exception as e:
        logger.error(f"bot_hair _list_active_users: {e}")
        return []


def _list_user_order_ids(phone: str, limit: int = 200):
    """درخواست‌های همان کاربر را فقط از وضعیت‌های فعال برمی‌گرداند."""
    np = normalize_phone(phone or "")
    if not np:
        return []
    try:
        marks = ",".join("?" * len(ACTIVE_STATUSES))
        with get_giso_db_conn() as conn:
            rows = conn.execute(
                f"SELECT id FROM hair_orders WHERE phone=? AND status IN ({marks}) "
                "ORDER BY id DESC LIMIT ?",
                (np, *ACTIVE_STATUSES, int(limit))).fetchall()
        return [int(r["id"]) for r in rows]
    except Exception as e:
        logger.error(f"bot_hair _list_user_order_ids: {e}")
        return []


def _get_order(order_id):
    try:
        with get_giso_db_conn() as conn:
            row = conn.execute("SELECT * FROM hair_orders WHERE id=?", (int(order_id),)).fetchone()
        return dict(row) if row else None
    except Exception as e:
        logger.error(f"bot_hair _get_order: {e}")
        return None


def _resolve_photo_path(photo_rel):
    if not photo_rel:
        return ""
    try:
        from giso.config import Config
        cands = [
            os.path.join(Config.BASE_DIR, "giso", "static", photo_rel),
            photo_rel,
            os.path.join(Config.UPLOAD_FOLDER, os.path.basename(photo_rel)),
        ]
        for c in cands:
            if os.path.exists(c):
                return c
    except Exception as e:
        logger.debug(f"bot_hair resolve photo: {e}")
    return ""


def _clamp(idx, total):
    try:
        idx = int(idx)
    except (TypeError, ValueError):
        idx = 0
    if total <= 0:
        return 0
    return max(0, min(total - 1, idx))


def order_card_text(order: dict, idx=None, total=None) -> str:
    oid = order.get("id")
    lines = [
        f"💇 درخواست فروش مو #{_fa_num(oid)}",
        "━━━━━━━━━━━━━━━━",
    ]
    if idx is not None and total:
        lines.append(f"📄 {_fa_num(idx + 1)} از {_fa_num(total)}")
        lines.append("━━━━━━━━━━━━━━━━")
    lines += [
        f"👤 نام: {order.get('customer_name') or '—'}",
        f"📱 شماره: {order.get('phone') or '—'}",
        f"📍 منطقه: {order.get('region') or '—'}",
        f"⏰ زمان تماس: {order.get('contact_time') or '—'}",
        "━━━━━━━━━━━━━━━━",
        f"🎨 نوع/رنگ: {order.get('hair_color') or order.get('hair_type') or '—'}",
        f"📏 طول: {_fa_num(order.get('length_cm', 0))} سانتی‌متر",
        f"🛡 سلامت: {order.get('hair_health') or '—'}",
        f"⚖️ حجم: {order.get('hair_weight') or '—'}",
    ]
    if order.get("description"):
        lines.append(f"📝 توضیح: {order.get('description')[:120]}")
    # رنج پیشنهادی سیستم برای راهنمای ادمین هنگام ثبت قیمت
    est = order.get("estimated_price") or "—"
    lines += [
        "━━━━━━━━━━━━━━━━",
        f"💰 رنج پیشنهادی سیستم: {est}",
        f"💎 قیمت نهایی: {order.get('final_price') or 'در انتظار'}",
        f"📌 وضعیت: {get_persian_status(order.get('status', 'pending'))}",
        f"📅 ثبت: {to_shamsi(order.get('created_at'))}",
    ]
    return "\n".join(lines)


def order_action_kb(order_id, _legacy_visibility: dict, idx=None, total=None, pager: str = "req",
                    extra_cb: str = "", status: str = "pending"):
    """Fixed operational action keyboard, limited only by order status.

    status-guard:
      - بررسی/قیمت/رد: روی pending/reviewing/priced
      - بازگشایی/قیمت: روی rejected برای ادامهٔ کار روزانه
      - completed/approved: بدون دکمهٔ تغییر وضعیت
    """
    from telegram import InlineKeyboardButton, InlineKeyboardMarkup

    st = (status or "pending").lower().strip()
    rows = []
    r1 = []
    if st in REVIEWABLE_STATUSES:
        r1.append(InlineKeyboardButton("🔍 در حال بررسی", callback_data=f"hair_review|{order_id}"))
    if st in REJECTABLE_STATUSES:
        r1.append(InlineKeyboardButton("❌ رد سفارش", callback_data=f"hair_rej|{order_id}"))
    if st in PRICEABLE_STATUSES:
        r1.append(InlineKeyboardButton("💰 ثبت قیمت نهایی", callback_data=f"hair_price|{order_id}"))
    # درخواست ردشده می‌تواند دوباره برای کار روزانه باز شود.
    if st == "rejected":
        r1.append(InlineKeyboardButton("✏️ بازگشایی (در حال بررسی)", callback_data=f"hair_review|{order_id}"))
        r1.append(InlineKeyboardButton("💰 ثبت قیمت نهایی", callback_data=f"hair_price|{order_id}"))
    if r1:
        rows.append(r1)
    # پیام به مشتری برای مدیریت (روی همه وضعیت‌ها به‌جز تکمیل‌شده)
    if st != "completed":
        rows.append([InlineKeyboardButton("💬 پیام به مشتری", callback_data=f"hair_msg|{order_id}")])
    if idx is not None and total:
        nav = []
        if idx > 0:
            nav.append(InlineKeyboardButton("◀️ قبلی", callback_data=f"hair_pg|{pager}|{idx - 1}"))
        if idx < total - 1:
            nav.append(InlineKeyboardButton("بعدی ▶️", callback_data=f"hair_pg|{pager}|{idx + 1}"))
        if nav:
            rows.append(nav)
    back_row = []
    if extra_cb:
        back_row.append(InlineKeyboardButton("🔙 بازگشت به گزارش", callback_data=extra_cb))
    back_row.append(InlineKeyboardButton("🔙 منوی فروش مو", callback_data="hair_pg|menu"))
    rows.append(back_row)
    return InlineKeyboardMarkup(rows)


async def _send_caption_with_photo(message, caption: str, kb, photo_rel: str):
    kb_dict = []
    try:
        kb_dict = json.loads(kb.to_json())
    except Exception:
        try:
            kb_dict = [[{"text": b.text, "callback_data": b.callback_data} for b in row]
                       for row in kb.inline_keyboard]
        except Exception:
            kb_dict = []

    photo_abs = _resolve_photo_path(photo_rel)
    token = ""
    try:
        from giso.base import _token_from_env, _token_from_db
        token = _token_from_env() or _token_from_db() or ""
    except Exception:
        token = ""

    if photo_abs and os.path.exists(photo_abs) and token:
        try:
            import asyncio
            import requests
            url = f"https://tapi.bale.ai/bot{token}/sendPhoto"
            data = {"chat_id": message.chat_id, "caption": caption, "parse_mode": "HTML",
                    "reply_markup": json.dumps({"inline_keyboard": kb_dict})}
            loop = asyncio.get_running_loop()

            def _send():
                with open(photo_abs, "rb") as f:
                    return requests.post(url, data=data, files={"photo": f}, timeout=10)

            # فراخوانی blocking خارج از event loop
            res = await loop.run_in_executor(None, _send)
            if int(getattr(res, "status_code", 500) or 500) == 200:
                return True
        except Exception as e:
            logger.debug(f"bot_hair sendPhoto fallback: {e}")
    try:
        await message.reply_text(caption, reply_markup=kb)
        return True
    except Exception as e:
        logger.debug(f"bot_hair reply_text: {e}")
    return False


async def show_requests_paged(message, uid, idx=0):
    ids = _list_request_ids()
    if not ids:
        await message.reply_text(EMPTY_REQUESTS_MSG)
        return 0
    idx = _clamp(idx, len(ids))
    order = _get_order(ids[idx])
    if not order:
        await message.reply_text(EMPTY_REQUESTS_MSG)
        return 0
    caption = order_card_text(order, idx=idx, total=len(ids))
    kb = order_action_kb(order["id"], {}, idx=idx, total=len(ids), pager="req",
                         status=order.get("status", "pending"))
    await _send_caption_with_photo(message, caption, kb, order.get("photo_path") or "")
    return len(ids)


async def show_users_paged(message, uid, idx=0):
    from telegram import InlineKeyboardButton, InlineKeyboardMarkup
    users = _list_active_users()
    if not users:
        await message.reply_text(EMPTY_USERS_MSG)
        return 0
    idx = _clamp(idx, len(users))
    u = users[idx]
    rows = [[InlineKeyboardButton(
        f"📋 مشاهده درخواست‌ها ({_fa_num(u['cnt'])} مورد)",
        callback_data=f"hair_pg|uo|{u['phone']}|0")]]
    nav = []
    if idx > 0:
        nav.append(InlineKeyboardButton("◀️ قبلی", callback_data=f"hair_pg|usr|{idx - 1}"))
    if idx < len(users) - 1:
        nav.append(InlineKeyboardButton("بعدی ▶️", callback_data=f"hair_pg|usr|{idx + 1}"))
    if nav:
        rows.append(nav)
    rows.append([InlineKeyboardButton("🔙 منوی فروش مو", callback_data="hair_pg|menu")])
    kb = InlineKeyboardMarkup(rows)
    caption = (
        "👥 کاربران فروش مو\n"
        "━━━━━━━━━━━━━━━━\n"
        f"📄 {_fa_num(idx + 1)} از {_fa_num(len(users))}\n"
        "━━━━━━━━━━━━━━━━\n"
        f"👤 {u['phone']}\n"
        f"🧾 {_fa_num(u['cnt'])} درخواست فعال\n"
        "━━━━━━━━━━━━━━━━\n"
        "برای دیدن درخواست‌ها روی دکمه زیر بزنید:")
    await message.reply_text(caption, reply_markup=kb)
    return len(users)


async def show_user_orders_paged(message, uid, phone, idx=0):
    ids = _list_user_order_ids(phone)
    if not ids:
        await message.reply_text(
            f"📭 درخواست‌های «{phone}» تمام شد — هیچ درخواست فعالی ندارد 🌸")
        return 0
    idx = _clamp(idx, len(ids))
    order = _get_order(ids[idx])
    if not order:
        await message.reply_text("📭 درخواست پیدا نشد.")
        return 0
    caption = order_card_text(order, idx=idx, total=len(ids))
    kb = order_action_kb(order["id"], {}, idx=idx, total=len(ids), pager=f"uo|{phone}",
                         status=order.get("status", "pending"))
    await _send_caption_with_photo(message, caption, kb, order.get("photo_path") or "")
    return len(ids)


_REPORT_SCOPE_STATUS = {"reviewing": "reviewing", "rejected": "rejected", "priced": "priced"}


def _report_phones(scope: str) -> list:
    status = _REPORT_SCOPE_STATUS.get(scope, "reviewing")
    try:
        with get_giso_db_conn() as conn:
            rows = conn.execute(
                "SELECT phone FROM hair_orders WHERE status=? AND phone != '' "
                "GROUP BY phone ORDER BY MAX(id) DESC", (status,)).fetchall()
        return [str(r["phone"]) for r in rows]
    except Exception as e:
        logger.error(f"bot_hair _report_phones({scope}): {e}")
        return []


def report_scope_label(scope: str) -> str:
    return {"reviewing": "🔍 نمایش در حال بررسی", "rejected": "❌ نمایش رد شده",
            "priced": "💰 نمایش قیمت ثبت‌شده"}.get(scope, "🔍 نمایش در حال بررسی")


async def show_report_phones(message, uid, scope: str, page=0):
    from telegram import InlineKeyboardButton, InlineKeyboardMarkup
    phones = _report_phones(scope)
    label = report_scope_label(scope)
    if not phones:
        await message.reply_text(
            f"{label}\n━━━━━━━━━━━━━━━━\n🧾 شمار کلی: ۰\nهیچ موردی یافت نشد 🌸", reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🔙 بازگشت به گزارش‌ها", callback_data="hair_rep|menu")
            ]]))
        return 0
    page = _clamp(page, (len(phones) + REPORT_PAGE_SIZE - 1) // REPORT_PAGE_SIZE or 1)
    total_pages = max(1, (len(phones) + REPORT_PAGE_SIZE - 1) // REPORT_PAGE_SIZE)
    chunk = phones[page * REPORT_PAGE_SIZE:(page + 1) * REPORT_PAGE_SIZE]
    caption = (
        f"{label}\n━━━━━━━━━━━━━━━━\n"
        f"🧾 شمار کلی: {_fa_num(len(phones))}\n"
        f"📄 صفحه {_fa_num(page + 1)} از {_fa_num(total_pages)}\n━━━━━━━━━━━━━━━━\n"
        "برای دیدن درخواست کاربر، روی شماره بزنید:")
    rows = [[InlineKeyboardButton(f"📱 {p}", callback_data=f"hair_rep_view|{scope}|{p}")] for p in chunk]
    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton("◀️ قبلی", callback_data=f"hair_rep|{scope}|{page - 1}"))
    if page < total_pages - 1:
        nav.append(InlineKeyboardButton("بعدی ▶️", callback_data=f"hair_rep|{scope}|{page + 1}"))
    if nav:
        rows.append(nav)
    rows.append([InlineKeyboardButton("🔙 بازگشت به گزارش‌ها", callback_data="hair_rep|menu")])
    await message.reply_text(caption, reply_markup=InlineKeyboardMarkup(rows))
    return len(phones)


async def show_report_user_view(message, uid, scope: str, phone: str):
    """نمایش فقط درخواست‌های منطبق با scope گزارش انتخاب‌شده."""
    status = _REPORT_SCOPE_STATUS.get(scope, "reviewing")
    ids = []
    try:
        np = normalize_phone(phone or "")
        with get_giso_db_conn() as conn:
            rows = conn.execute(
                "SELECT id FROM hair_orders WHERE phone=? AND status=? ORDER BY id DESC",
                (np, status)).fetchall()
        ids = [int(r["id"]) for r in rows]
    except Exception as e:
        logger.error(f"bot_hair show_report_user_view: {e}")
    if not ids:
        await message.reply_text(f"📭 درخواستی برای «{phone}» یافت نشد 🌸")
        return 0
    order = _get_order(ids[0])
    if not order:
        return 0
    caption = order_card_text(order, idx=0, total=len(ids))
    kb = order_action_kb(order["id"], {}, idx=0, total=len(ids),
                         pager=f"report|{scope}|{phone}", extra_cb=f"hair_rep|{scope}|0",
                         status=order.get("status", "pending"))
    await _send_caption_with_photo(message, caption, kb, order.get("photo_path") or "")
    return len(ids)


async def show_conversations(message, uid, limit: int = 10) -> int:
    from telegram import InlineKeyboardButton, InlineKeyboardMarkup
    try:
        with get_giso_db_conn() as conn:
            rows = conn.execute(
                "SELECT h.id, h.customer_name, h.phone, h.status, "
                "MAX(m.id) AS last_msg_id, COUNT(m.id) AS msg_cnt, "
                "(SELECT message FROM hair_messages mm WHERE mm.order_id=h.id ORDER BY mm.id DESC LIMIT 1) AS last_msg "
                "FROM hair_orders h JOIN hair_messages m ON m.order_id=h.id "
                "WHERE h.status IN ('pending','reviewing','priced') "
                "GROUP BY h.id ORDER BY last_msg_id DESC LIMIT ?", (int(limit),)).fetchall()
    except Exception as e:
        logger.error(f"bot_hair show_conversations: {e}")
        return 0
    if not rows:
        await message.reply_text(
            "💬 گفتگوها تمام شد\n━━━━━━━━━━━━━━━━\n"
            "هنوز گفتگویی با کاربران فعال وجود ندارد.\n"
            "با ارسال پیام به یک درخواست، گفتگو شروع می‌شود 🌸")
        return 0
    await message.reply_text(f"💬 گفتگوهای در جریان ({_fa_num(len(rows))}) — جدیدترین بالا:")
    for r in rows:
        last = (r["last_msg"] or "")[:120]
        txt = (
            f"💬 گفتگو #{_fa_num(r['id'])} — {r['customer_name'] or '—'}\n"
            f"📱 {r['phone'] or '—'} | 🧾 {_fa_num(r['msg_cnt'])} پیام\n"
            f"📌 وضعیت: {get_persian_status(r['status'])}\n"
            f"📝 آخرین پیام: {last or '—'}")
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton(f"💬 ادامه گفتگو | #{_fa_num(r['id'])}", callback_data=f"hair_msg|{r['id']}")],
            [InlineKeyboardButton(f"✅ پایان گفتگو | #{_fa_num(r['id'])}", callback_data=f"hair_complete|{r['id']}")],
            [InlineKeyboardButton("🔙 بازگشت", callback_data="hair_pg|menu")],
        ])
        await message.reply_text(txt, reply_markup=kb)
    return len(rows)


async def render_request_list(msg, uid, limit: int = 10) -> int:
    return await show_requests_paged(msg, uid, 0)


async def render_user_list(msg, uid, limit: int = 15) -> int:
    return await show_users_paged(msg, uid, 0)


async def render_user_orders(msg, uid, phone: str, limit: int = 10) -> int:
    return await show_user_orders_paged(msg, uid, phone, 0)


__all__ = [
    "HAIR_SUBOPTIONS", "CALLBACK_SUBOPTION", "ACTIVE_STATUSES",
    "PRICEABLE_STATUSES", "REVIEWABLE_STATUSES", "REJECTABLE_STATUSES",
    "get_admin_sub_options", "admin_sub_allowed",
    "build_admin_hair_menu", "admin_hair_menu_text",
    "order_card_text", "order_action_kb",
    "show_requests_paged", "show_users_paged", "show_user_orders_paged",
    "show_report_phones", "show_report_user_view", "show_conversations",
    "render_request_list", "render_user_list", "render_user_orders",
]
