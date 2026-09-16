"""
handlers_admin.py — کمکی‌های ادمین برای پاسخ پشتیبانی و خرید نقدی
وابستگی مجاز: config، core، ui و stdlib
"""
import logging

from config import ADMIN_IDS, get_platform_bot
from core import platform_name, support_link
from ui import btn, mkb

logger = logging.getLogger(__name__)


def build_support_reply_text(text: str, platform: str = None) -> str:
    """
    [کار ۱] متن پاسخ پشتیبانی — لینک پشتیبانی مطابق پلتفرمِ مقصد.
    اگر ادمین برای آن پلتفرم لینک اختصاصی ثبت کرده باشد همان،
    وگرنه fallback به گروه پشتیبانی بله.
    """
    body = (text or "").strip()
    sup_disp, _url = support_link(platform)
    return (
        "☎️ پاسخ تیم پشتیبانی\n"
        "➖➖➖➖➖\n"
        f"{body}\n\n"
        "💙 همیشه کنار شما هستیم\n"
        f"📞 {sup_disp}"
    )


async def send_ticket_reply_strict(ticket: dict, text: str):
    """ارسال پاسخ تیکت فقط از bot همان پلتفرم و به chat_id همان پلتفرم."""
    tk_plat = (ticket.get("platform") or "bale").strip() or "bale"
    tk_chat = ticket.get("chat_id")
    if tk_chat in (None, ""):
        return False, "شناسه چت مقصد برای این تیکت ثبت نشده است."

    reply_bot = get_platform_bot(tk_plat)
    if not reply_bot:
        return False, f"ربات پلتفرم «{platform_name(tk_plat)}» فعال نیست."

    try:
        # [کار ۱] لینک پشتیبانی همان پلتفرمِ کاربر نمایش داده می‌شود
        await reply_bot.send_message(tk_chat, build_support_reply_text(text, tk_plat))
        return True, ""
    except Exception as e:
        logger.error(f"ticket reply error ({tk_plat}:{tk_chat}): {e}")
        return False, (
            f"ارسال پاسخ روی پلتفرم «{platform_name(tk_plat)}» ناموفق بود.\n"
            "احتمالاً کاربر ربات را بلاک کرده یا چت مقصد دیگر در دسترس نیست."
        )


def build_cash_subject(req: dict) -> str:
    if req.get("target_type") == "lesson" and req.get("lesson_title"):
        return f"سرفصل: {req.get('lesson_title')}"
    return f"دوره: {req.get('course_title', '---')}"


def build_cash_admin_caption(req: dict) -> str:
    subject_text = build_cash_subject(req)
    amount = int(req.get("amount", 0) or 0)
    amount_line = f"💰 مبلغ: {amount:,} تومان\n" if amount else ""
    platform = req.get("platform") or "bale"
    return (
        "📬 درخواست خرید نقدی\n\n"
        f"👤 نام: {req.get('user_name', '---')}\n"
        f"🆔 شناسه Canonical: {req.get('canonical_user_id') or req.get('user_id')}\n"
        f"💬 Chat ID: {req.get('chat_id', '---')}\n"
        f"👤 یوزرنیم: @{req.get('username') or '---'}\n"
        f"🌐 پلتفرم: {platform_name(platform)}\n\n"
        f"📦 نوع: {'دوره' if req.get('target_type') == 'course' else 'سرفصل'}\n"
        f"📖 عنوان: {subject_text}\n"
        f"{amount_line}"
    ).rstrip()


def _cash_result_text(req: dict, approved: bool) -> str:
    subject = req.get("lesson_title") if req.get("target_type") == "lesson" else req.get("course_title", "---")
    if approved:
        if req.get("target_type") == "lesson":
            return (
                "✅ خرید شما تایید شد\n"
                f"📝 سرفصل {subject} برای شما فعال شد"
            )
        return (
            "✅ خرید شما تایید شد\n"
            f"📖 دوره {subject} برای شما فعال شد"
        )
    return (
        "❌ درخواست خرید شما رد شد\n"
        "برای اطلاعات بیشتر با پشتیبانی تماس بگیرید"
    )


def _cash_result_markup(approved: bool):
    if approved:
        return mkb([[btn("🏪 مشاهده گنجینه", "shop")]])
    return mkb([[btn("✉️ ارسال پیام به پشتیبانی", "send_ticket")]])


async def send_cash_status_strict(req: dict, approved: bool):
    """ارسال نتیجه خرید نقدی فقط از bot همان پلتفرم و بدون fallback ناخواسته."""
    req_plat = (req.get("platform") or "bale").strip() or "bale"
    req_chat = req.get("chat_id")
    if req_chat in (None, ""):
        return False, "شناسه چت مقصد برای این درخواست ثبت نشده است."

    bot = get_platform_bot(req_plat)
    if not bot:
        return False, f"ربات پلتفرم «{platform_name(req_plat)}» فعال نیست."

    try:
        await bot.send_message(
            req_chat,
            _cash_result_text(req, approved),
            reply_markup=_cash_result_markup(approved),
        )
        return True, ""
    except Exception as e:
        logger.error(f"cash notify error ({req_plat}:{req_chat}): {e}")
        return False, (
            f"ارسال نتیجه خرید روی پلتفرم «{platform_name(req_plat)}» ناموفق بود.\n"
            "احتمالاً کاربر ربات را بلاک کرده یا چت مقصد دیگر در دسترس نیست."
        )


def bot_route_targets(platform: str, get_platform_admins_fn):
    """
    مقصدهای ادمینیِ یک پلتفرم (برای اعلان تیکت و مسیر «ربات‌های فعال»).

    [کار ۲ — رفع باگ] قبلاً برای پلتفرم ثانویه فقط `platform_admins` خوانده می‌شد،
    یعنی ادمین اصلی که با «شماره» به تلگرام وصل شده بود (نه با لینک ادمین)
    هیچ اعلانی دریافت نمی‌کرد. حالا هر دو منبع در نظر گرفته می‌شوند:
      ۱) ادمین‌های ثبت‌شدهٔ همان پلتفرم (لینک ادمینی)
      ۲) ادمین‌های ADMIN_IDS که حساب‌شان به آن پلتفرم متصل است (وراثت ادمینی)
    """
    seen = set()
    out = []

    def _add(v):
        key = str(v)
        if key in seen:
            return
        seen.add(key)
        try:
            out.append(int(v))
        except (TypeError, ValueError):
            out.append(v)

    if platform == "bale":
        for aid in ADMIN_IDS:
            _add(aid)
        return out

    # ۱) ادمین‌های ثبت‌شدهٔ همان پلتفرم
    for admin in get_platform_admins_fn(platform):
        raw_id = admin.get("platform_user_id")
        if raw_id not in (None, ""):
            _add(raw_id)

    # ۲) ادمین‌های اصلی (ADMIN_IDS) که با شماره به این پلتفرم متصل شده‌اند
    try:
        from config import PLATFORM_LINKS
        for link in PLATFORM_LINKS.values():
            if link.get("platform") != platform:
                continue
            try:
                owner = int(link.get("user_id") or 0)
            except (TypeError, ValueError):
                continue
            if owner in ADMIN_IDS:
                pid = link.get("platform_user_id")
                if pid not in (None, ""):
                    _add(pid)
    except Exception as e:
        logger.warning(f"bot_route_targets: خواندن PLATFORM_LINKS ناموفق: {e}")

    return out
# Phase 10.2 Admin Bot
