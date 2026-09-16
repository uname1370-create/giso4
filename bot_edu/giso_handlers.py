# -*- coding: utf-8 -*-
"""
giso_handlers.py — هندلرهای پنل مدیریت ربات گیسو در ربات اصلی بله

⚠️ تصمیم نهایی محصول:
  • افزودن دستی ادمین گیسو از پنل بات اصلی حذف شد.
  • ادمین گیسو فقط از طریق درخواست خودکار کاربر (با عبارت درون ربات گیسو) و
    تأیید/رد توسط ادمین اصلی از همین پنل تعیین می‌شود.
  • بنابراین در این پنل امکانات زیر هستند:
      - 🔑 تنظیم توکن
      - 👤 تنظیم نام کاربری
      - 💬 تنظیم عبارت درخواست ادمین
      - 📨 درخواست‌های ادمینی (تأیید/رد)
      - 📊 آمار ربات گیسو
      - ⬅️ بازگشت
"""
import logging
from telegram import Update
from telegram.ext import ContextTypes

from ui import btn, back_btn, safe_answer
from telegram import InlineKeyboardMarkup
from giso_admin import (
    get_giso_config, set_giso_config,
    list_giso_admins,
    get_giso_stats,
    get_admin_request_phrase, set_admin_request_phrase,
    list_admin_requests, review_admin_request,
)

logger = logging.getLogger(__name__)
GISO_STATE_KEY = "giso_state"


def _rows(*rows):
    out: list = []
    for r in rows:
        if r is None:
            continue
        if hasattr(r, 'callback_data') or hasattr(r, 'url'):
            out.append([r]); continue
        row = []
        if isinstance(r, (list, tuple)):
            for b in r:
                if b is not None: row.append(b)
        if row:
            out.append(list(row))
    return InlineKeyboardMarkup(out)


def giso_menu_markup():
    return _rows(
        [btn("🔑 تنظیم توکن ربات گیسو", "a_giso_token")],
        [btn("👤 تنظیم نام کاربری ربات گیسو", "a_giso_username")],
        [btn("💬 عبارت درخواست ادمین", "a_giso_phrase")],
        [btn("📨 درخواست‌های ادمینی", "a_giso_requests")],
        [btn("📊 آمار ربات گیسو", "a_giso_stats")],
        back_btn("a_panel"),
    )


def giso_cancel_markup():
    return _rows([btn("🎀 بازگشت به مدیریت گیسو", "a_giso_management")])


def giso_requests_markup(reqs):
    rows = []
    for r in reqs[:20]:
        disp = ("0" + r["phone"][3:]) if r.get("phone", "").startswith("+98") else (r.get("phone") or "—")
        rows.append([btn(f"👤 {disp} | {r.get('bale_id','—')}", f"a_giso_req_view|{r['id']}")])
    if not rows:
        rows.append([btn("— درخواست بازی در انتظار نیست —", "a_giso_noop")])
    rows.append(back_btn("a_giso_management"))
    return _rows(*rows)


def giso_request_view_markup(req_id):
    return _rows(
        [btn("✅ تأیید و افزودن به ادمین‌ها", f"a_giso_req_approve|{req_id}"),
         btn("❌ رد درخواست", f"a_giso_req_reject|{req_id}")],
        [btn("🔙 بازگشت به فهرست درخواست‌ها", "a_giso_requests")],
        back_btn("a_giso_management"),
    )


async def show_giso_management(target, is_q=True):
    token = get_giso_config('bot_token', '')
    username = get_giso_config('bot_username', '')
    phrase = get_admin_request_phrase()
    pending = list_admin_requests('pending')
    token_status = "✅ ثبت شده" if token else "❌ ثبت نشده"
    text = (
        "🎀 مدیریت ربات گیسو\n"
        "➖➖➖➖➖\n\n"
        f"🔑 توکن ربات: {token_status}\n"
        f"👤 نام کاربری: @{username if username else '—'}\n"
        f"💬 عبارت درخواست ادمین: «{phrase}»\n"
        f"📨 درخواست‌های در انتظار: {len(pending)} مورد\n"
        "ℹ️ ادمین گیسو از طریق ارسال عبارت در ربات گیسو درخواست می‌دهد و شما تأیید/رد می‌کنید.\n\n"
        "یکی از گزینه‌ها را انتخاب کنید:"
    )
    if is_q:
        await target.edit_message_text(text, reply_markup=giso_menu_markup())
    else:
        await target.reply_text(text, reply_markup=giso_menu_markup())


async def show_giso_stats(target, is_q=True):
    stats = get_giso_stats()
    token_status = "✅ ثبت شده" if stats.get('token_set') else "❌ ثبت نشده"
    running_status = stats.get('status_label', '❌ غیرفعال')
    token_masked = stats.get('token_masked', '—')
    pid = stats.get('pid')
    pid_line = f"🆔 PID: {pid}\n" if pid else ""
    text = (
        "📊 وضعیت ربات گیسو\n"
        "➖➖➖➖➖\n\n"
        f"🚀 وضعیت اجرا: {running_status}\n{pid_line}"
        f"🔑 توکن: {token_status}\n🔑 مقدار توکن: {token_masked}\n"
        f"👤 نام کاربری: @{stats.get('bot_username','—')}\n"
        f"💬 عبارت درخواست ادمین: «{stats.get('admin_request_phrase','')}»\n"
        f"📨 درخواست‌های باز: {stats.get('pending_requests',0)}\n\n"
        "اگر توکن ثبت شده ولی اجرا نمی‌شود چند ثانیه صبر کنید یا main.py را بررسی کنید."
    )
    if is_q:
        await target.edit_message_text(text, reply_markup=_rows(
            [btn("🔄 به‌روزرسانی", "a_giso_stats")], back_btn("a_giso_management")))
    else:
        await target.reply_text(text, reply_markup=_rows(
            [btn("🔄 به‌روزرسانی", "a_giso_stats")], back_btn("a_giso_management")))


async def show_giso_requests(target, is_q=True):
    reqs = list_admin_requests("pending")
    text = "📨 درخواست‌های ادمینی در انتظار تأیید\n➖➖➖➖➖\n\n"
    if not reqs:
        text += "هیچ درخواست بازی در انتظار نیست."
    else:
        text += f"تعداد {len(reqs)} درخواست باز:\n"
        for r in reqs[:20]:
            disp = ("0" + r["phone"][3:]) if r.get("phone","").startswith("+98") else r.get("phone")
            text += f"  • 📱 {disp} | 🆔 {r.get('bale_id','—')} | {r.get('requested_at','')}\n"
    markup = giso_requests_markup(reqs)
    if is_q: await target.edit_message_text(text, reply_markup=markup)
    else: await target.reply_text(text, reply_markup=markup)


async def show_giso_request_view(target, req_id, is_q=True):
    reqs = list_admin_requests("all")
    req = next((r for r in reqs if r["id"] == int(req_id)), None)
    if not req:
        await safe_answer(target.callback_query if is_q else None, "درخواست پیدا نشد.", True); return
    disp = ("0" + req["phone"][3:]) if req.get("phone","").startswith("+98") else req.get("phone")
    sl = {"pending":"⏳ در انتظار","approved":"✅ تأیید شده","rejected":"❌ رد شده"}
    text = (f"📨 درخواست ادمینی #{req['id']}\n➖➖➖➖➖\n\n"
            f"📱 شماره: {disp}\n🆔 شناسه بله: {req.get('bale_id','—')}\n"
            f"📅 ثبت: {req.get('requested_at','—')}\n"
            f"📌 وضعیت: {sl.get(req.get('status'),req.get('status'))}\n")
    if req.get("reviewed_at"): text += f"⏰ بررسی: {req['reviewed_at']}\n"
    markup = (giso_request_view_markup(req["id"]) if req.get("status")=="pending"
              else _rows([btn("🔙 بازگشت", "a_giso_requests")], back_btn("a_giso_management")))
    if is_q: await target.edit_message_text(text, reply_markup=markup)
    else: await target.reply_text(text, reply_markup=markup)


async def giso_button_handler(update: Update, ctx: ContextTypes.DEFAULT_TYPE,
                             user=None, is_admin_flag=False):
    q = update.callback_query; d = q.data or ""
    if not d.startswith("a_giso"): return False
    if not is_admin_flag:
        await safe_answer(q, "❌ دسترسی ادمین لازم است.", True); return True

    if d == "a_giso_noop": await q.answer(); return True
    if d == "a_giso_management": await show_giso_management(q); return True
    if d == "a_giso_stats": await show_giso_stats(q); return True
    if d == "a_giso_requests": await show_giso_requests(q); return True

    if d.startswith("a_giso_req_view|"):
        try: await show_giso_request_view(q, int(d.split("|")[1]))
        except Exception as e:
            logger.warning(f"req_view: {e}"); await q.answer("نامعتبر", show_alert=True)
        return True

    if d.startswith("a_giso_req_approve|") or d.startswith("a_giso_req_reject|"):
        try:
            rid = int(d.split("|")[1])
            approve = d.startswith("a_giso_req_approve")
            rid_user = update.effective_user.id if update.effective_user else 0
            review_admin_request(rid, approve=approve, reviewer_id=rid_user)
            await q.answer("✅ تأیید شد." if approve else "❌ رد شد.", show_alert=True)
        except Exception as e:
            await q.answer(f"خطا: {e}", show_alert=True)
        await show_giso_requests(q); return True

    if d == "a_giso_token":
        ctx.user_data[GISO_STATE_KEY] = "wait_giso_token"
        cur = get_giso_config('bot_token','')
        mask = cur[:8]+'...'+cur[-4:] if len(cur)>12 else '(ثبت نشده)'
        await q.edit_message_text(
            f"🔑 تنظیم توکن ربات گیسو\n\nتوکن فعلی: {mask}\n\n"
            "لطفاً توکن را از @BotFather بفرستید.\n(برای انصراف /cancel)",
            reply_markup=giso_cancel_markup()); return True

    if d == "a_giso_username":
        ctx.user_data[GISO_STATE_KEY] = "wait_giso_username"
        cur = get_giso_config('bot_username','')
        await q.edit_message_text(
            f"👤 نام کاربری ربات گیسو\n\nنام فعلی: @{cur if cur else '(ثبت نشده)'}\n\n"
            "نام کاربری را بدون @ بفرستید (مثلاً giso_bot).\n(برای انصراف /cancel)",
            reply_markup=giso_cancel_markup()); return True

    if d == "a_giso_phrase":
        ctx.user_data[GISO_STATE_KEY] = "wait_giso_phrase"
        cur = get_admin_request_phrase()
        await q.edit_message_text(
            f"💬 عبارت درخواست ادمین\n\nعبارت فعلی: «{cur}»\n\n"
            "کاربر پس از به اشتراک‌گذاشتن تماس در ربات گیسو با ارسال همین عبارت درخواست ادمینی می‌فرستد. "
            "عبارت جدید را بفرستید:\n(برای انصراف /cancel)",
            reply_markup=giso_cancel_markup()); return True
    return False


async def giso_text_handler(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    state = ctx.user_data.get(GISO_STATE_KEY)
    if not state: return False
    msg = update.effective_message
    text = (msg.text or '').strip()
    if text == '/cancel':
        ctx.user_data.pop(GISO_STATE_KEY, None)
        await msg.reply_text("❌ عملیات لغو شد.", reply_markup=giso_cancel_markup()); return True

    if state == "wait_giso_token":
        if len(text) < 30 or ':' not in text:
            await msg.reply_text("❌ توکن نامعتبر است."); return True
        set_giso_config('bot_token', text); ctx.user_data.pop(GISO_STATE_KEY, None)
        await msg.reply_text("✅ توکن با موفقیت ثبت شد. ربات گیسو ظرف چند ثانیه راه‌اندازی می‌شود.",
                             reply_markup=giso_cancel_markup()); return True

    if state == "wait_giso_username":
        un = text.lstrip('@').strip()
        if not un or ' ' in un or len(un) < 3:
            await msg.reply_text("❌ نام کاربری نامعتبر."); return True
        set_giso_config('bot_username', un); ctx.user_data.pop(GISO_STATE_KEY, None)
        await msg.reply_text(f"✅ نام کاربری @{un} ثبت شد.", reply_markup=giso_cancel_markup()); return True

    if state == "wait_giso_phrase":
        if len(text) < 3:
            await msg.reply_text("❌ عبارت بسیار کوتاه است."); return True
        set_admin_request_phrase(text); ctx.user_data.pop(GISO_STATE_KEY, None)
        await msg.reply_text(f"✅ عبارت درخواست ادمین به «{text}» تغییر یافت.",
                             reply_markup=giso_cancel_markup()); return True
    return False


async def giso_inline_followup(update, ctx, is_admin_flag=False):
    # No manual-add FSM remains, so no-op
    return False
