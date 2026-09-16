# -*- coding: utf-8 -*-
"""
bot_helpers — توابع کمکی خالص ربات گیسو: فرمت متن/گزارش AI، نرمال‌سازی عبارت ادمینی، دسترسی بخش‌ها، پارس/تاریخ
Phase 2 / U6 extraction from giso/bot.py — NO behavior change; re-exported from giso.bot.
"""
import json
import logging

from giso.base import _admin_request_phrase, _fa_num, _is_super_admin, to_shamsi
from giso.ai_runtime import (
    ROLE_LABELS, SECTION_LABELS, check_role_access,
    get_active_provider, get_role_policy, get_runtime_overview,
    list_provider_options,
)

logger = logging.getLogger("giso_bot")

_VISIBLE_ROLE_SECTIONS = {
    "user": ["analysis", "plan", "products", "orders", "actions"],
    "admin": ["reports", "tickets", "consultants", "products_edit", "users_edit", "data_delete"],
}


_LEGACY_AI_CALLBACK_PREFIXES = (
    "ai_edit_select|",
    "ai_edit_fld|",
    "ai_edit_proxy|",
    "ai_edit_ref|",
    "ai_toggle|",
    "prx_mode|",
)


_LEGACY_AI_CALLBACKS = {"ai_edit_back", "prx_clearok", "prx_cancel"}


_BOT_OPERATIONAL_SECTIONS = frozenset({
    "dashboard", "orders", "hair_sale", "analysis_management", "reviews", "products",
})



def _managed_ai_provider_picker_text():
    grouped = list_provider_options()
    active = get_active_provider() or "—"
    lines = [
        "🎯 انتخاب هوش مصنوعی فعال",
        "━━━━━━━━━━━━━━━━━━━━━━━",
        f"فعلی: {active} ✅",
        "",
        "🇮🇷 پروایدرهای ایرانی:",
    ]
    iranian = grouped.get("iranian") or []
    foreign = grouped.get("foreign") or []
    if iranian:
        for item in iranian:
            lines.append(f"• {item['name']} — {item.get('selected_model') or '—'}")
    else:
        lines.append("• موردی ثبت نشده")
    lines += ["", "🌐 پروایدرهای خارجی:"]
    if foreign:
        for item in foreign:
            lines.append(f"• {item['name']} — {item.get('selected_model') or '—'}")
    else:
        lines.append("• موردی ثبت نشده")
    lines += ["", "روی هر گزینه بزن تا به عنوان AI فعال گفتگو ذخیره شود."]
    return "\n".join(lines)



def _managed_ai_permission_detail_text(role):
    policy = get_role_policy(role)
    if role == "super":
        return (
            "👑 دسترسی هوش مصنوعی برای سوپرادمین\n"
            "━━━━━━━━━━━━━━━━━━━━━━━\n"
            "سطح ۳: دسترسی کامل\n"
            "وضعیت: همیشه بدون محدودیت\n"
            "⚠️ این بخش فقط نمایشی است و قابل تغییر نیست."
        )
    sections = set(policy.get("sections") or [])
    role_title = ROLE_LABELS.get(role, role)
    daily_limit = int(policy.get("daily_limit", 0) or 0)
    lines = [
        f"🔐 تنظیم دسترسی {role_title}",
        "━━━━━━━━━━━━━━━━━━━━━━━",
        f"سطح فعلی: {policy.get('access_level', 0)}",
        f"محدودیت روزانه: {'نامحدود' if daily_limit == 0 else str(daily_limit)}",
        "",
        "بخش‌های فعال:",
    ]
    visible = _VISIBLE_ROLE_SECTIONS.get(role, [])
    for sec in visible:
        lines.append(f"{'☑' if sec in sections else '☐'} {SECTION_LABELS.get(sec, sec)}")
    return "\n".join(lines)



def _managed_ai_dashboard_text():
    info = get_runtime_overview()
    status = "فعال ✅" if info["enabled"] else "غیرفعال ❌"
    return (
        "🧠 مدیریت رفتار هوش مصنوعی گیسو\n"
        "━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"🔛 وضعیت: {status}\n"
        f"🤖 مدل انتخاب شده: {info['active_provider'] or '—'} ({info['selected_model']})\n"
        f"🎯 اسم نمایشی: {info['display_name']}\n\n"
        "📈 آمار امروز:\n"
        f"👥 کاربران استفاده‌کننده: {_fa_num(info['today_users'])}\n"
        f"💬 کل گفتگوها: {_fa_num(info['today_chats'])}\n"
        f"🪙 توکن مصرفی: {_fa_num(info['today_tokens'])}"
    )



def _ratelimit_status_text():
    try:
        from giso.base import read_rate_limit_config
        cfg = read_rate_limit_config()
        enabled = cfg["enabled"]
        minutes = cfg["minutes"]
        rtype = cfg["limit_type"]
        type_fa = {"ip": "فقط IP", "phone": "فقط شماره موبایل", "both": "هر دو"}.get(rtype, rtype)
        if not cfg.get("ok", True):
            type_fa = "هر دو (پیش‌فرض امن)"
    except Exception:
        enabled = True
        minutes = 5
        type_fa = "هر دو"
    status_fa = "فعال ✅" if enabled else "غیرفعال ⚪️"
    return (
        "⏱ تنظیمات محدودیت زمان تحلیل\n"
        "━━━━━━━━━━━━━━━━\n\n"
        f"وضعیت فعلی: {status_fa}\n"
        f"مدت زمان: {minutes} دقیقه\n"
        f"نوع محدودیت: {type_fa}"
    )



def _has_provider_ai_management_access(uid, phone="", existing_admin=None) -> bool:
    """Provider/proxy administration remains superadmin-only."""
    return bool(_is_super_admin(uid, phone))



def _is_legacy_ai_callback(data: str) -> bool:
    data = str(data or "")
    return data in _LEGACY_AI_CALLBACKS or data.startswith(_LEGACY_AI_CALLBACK_PREFIXES)



def _role_has_consultant_ai(role: str) -> bool:
    role = (role or "user").strip().lower()
    access = check_role_access(role, section="consultant_chat")
    return bool(access.get("allowed"))



def _normalize_admin_phrase(value) -> str:
    """نرمال‌سازی محدود عبارت ادمینی بدون تغییر متن ذخیره‌شده در bot.db."""
    import unicodedata
    text = unicodedata.normalize("NFKC", str(value or ""))
    text = text.translate(str.maketrans({"ي": "ی", "ى": "ی", "ك": "ک"}))
    text = text.replace("\u200c", " ").replace("\u200e", " ").replace("\u200f", " ")
    return " ".join(text.split()).strip()



def _admin_request_phrase_terms() -> list:
    """لیست عبارت‌های فعال درخواست ادمین (نرمال‌شده).

    سوپرادمین می‌تواند در «🔑 تنظیم کلمه ادمینی» چند عبارت را با جداکنندهٔ
    «|» یا «،» یا خط جدید تعریف کند؛ اگر کاربر عیناً یکی از آن‌ها را بفرستد
    (پس از نرمال‌سازی) درخواست ادمینی ثبت می‌شود — نه اینکه پیام به مشاور AI برود.
    پیش‌فرض وقتی چیزی تنظیم نشده: مقدار default تابع base._admin_request_phrase.
    """
    import re
    raw = str(_admin_request_phrase() or "")
    parts = re.split(r"[|،\n]+", raw)
    terms = []
    seen = set()
    for part in parts:
        term = _normalize_admin_phrase(part)
        if term and term not in seen:
            seen.add(term)
            terms.append(term)
    return terms


def _strip_admin_phrase_noise(value) -> str:
    """نرمال‌سازی + حذف نویز لبه‌ها (فاصله، نقطه‌گذاری، ایموجی‌های رایج انتهای پیام)."""
    text = _normalize_admin_phrase(value)
    return text.strip(" !؟?.،,ـ😊🌹👋")


# واژه‌های کوتاه درخواست ادمین — علاوه بر عبارت تنظیم‌شدهٔ سوپر.
# تطبیق «شامل بودن» فقط برای پیام کوتاه است تا چت معمولی AI
# («ادمین گفت قیمت چنده») یا دکمه‌های منو دزدیده نشوند.
_ADMIN_INTENT_PHRASES = (
    "ارتباط با ادمین",
    "سوپر ادمین",
    "سوپرادمین",
    "ادمین",
    "پشتیبانی",
)
_ADMIN_INTENT_EXCLUDED = frozenset({
    "🎧 پشتیبانی",
    "💬 پشتیبانی",
})


def _is_admin_request_phrase(value) -> bool:
    normalized = _strip_admin_phrase_noise(value)
    if not normalized:
        return False
    if any(normalized == term for term in _admin_request_phrase_terms()):
        return True
    if normalized in _ADMIN_INTENT_EXCLUDED:
        return False
    if normalized in _ADMIN_INTENT_PHRASES:
        return True
    # پیام کوتاهِ حاوی واژهٔ قصد — نه جملهٔ بلند گفتگوی مشاور
    words = normalized.split()
    if len(normalized) > 40 or len(words) > 6:
        return False
    return any(phrase in normalized for phrase in _ADMIN_INTENT_PHRASES)



def _admin_section_allowed(admin_bale_id, section) -> bool:
    return bool(_is_super_admin(admin_bale_id) or section in _BOT_OPERATIONAL_SECTIONS)



def _admin_section_visible_for_bot(admin_bale_id, section) -> bool:
    """Fixed role visibility; legacy sub-option values are intentionally inert."""
    return _admin_section_allowed(admin_bale_id, section)



def _is_super_admin_by_rec(a) -> bool:
    a_phone = a.get("phone", "")
    a_bid = str(a.get("bale_id", "") or a.get("telegram_id", "") or "")
    return (a_bid == "1191639507" or a_phone == "09156012931"
            or a_phone == "+989156012931" or a_phone.endswith("9156012931"))



def _extract_analysis_topic(ai_report_json, analysis_type):
    """استخراج موضوع اصلی تحلیل."""
    default = 'تحلیل مو' if analysis_type == 'hair' else 'تحلیل صورت'
    if not ai_report_json:
        return default
    try:
        data = json.loads(ai_report_json)
        if not isinstance(data, dict):
            return default
        for key in ('main_problems', 'problems'):
            problems = data.get(key)
            if problems:
                if isinstance(problems, list) and problems:
                    first = problems[0]
                    if isinstance(first, dict):
                        label = first.get('name') or first.get('title') or ''
                        if label:
                            return f"{default} - {str(label)[:30]}"
                    elif isinstance(first, str) and first:
                        return f"{default} - {first[:30]}"
        for key in ('overall_status', 'condition'):
            if data.get(key):
                return f"{default} - {str(data[key])[:30]}"
        return default
    except Exception:
        return default



def _extract_analysis_score(ai_report_json):
    """استخراج امتیاز کلی تحلیل."""
    if not ai_report_json:
        return None
    try:
        data = json.loads(ai_report_json)
        if not isinstance(data, dict):
            return None
        for key in ('overall_score', 'score', 'health_score', 'general_score'):
            if key in data:
                val = data[key]
                if isinstance(val, bool):
                    continue
                if isinstance(val, (int, float)):
                    return int(val)
                if isinstance(val, str) and val.strip().isdigit():
                    return int(val.strip())
        return None
    except Exception:
        return None



def _format_persian_date(date_str):
    """تبدیل تاریخ به فارسی خوانا."""
    from datetime import datetime

    if not date_str:
        return 'نامشخص'
    try:
        if 'T' in date_str:
            date_part, time_part = date_str.split('T')
            time_part = time_part[:5]
        elif ' ' in date_str:
            parts = date_str.split(' ')
            date_part = parts[0]
            time_part = parts[1][:5] if len(parts) > 1 else '00:00'
        else:
            date_part = date_str
            time_part = ''
        try:
            dt = datetime.strptime(date_part, '%Y-%m-%d')
            now = datetime.now()
            diff = (now - dt).days
            if diff == 0:
                return f"امروز - {time_part}"
            elif diff == 1:
                return f"دیروز - {time_part}"
            elif diff < 7:
                return f"{diff} روز پیش - {time_part}"
            else:
                return to_shamsi(date_str)
        except Exception:
            return to_shamsi(date_str)
    except Exception:
        return date_str



def _user_delete_info_text(info: dict) -> str:
    return (
        "👤 اطلاعات کاربر پیدا شد\n\n"
        f"نام: {info['name']}\n"
        f"شماره: {info['phone'] or '—'}\n"
        f"شناسه: {info['bale_id'] or '—'}\n"
        f"تاریخ عضویت: {to_shamsi(info['created_at'])}\n"
        f"تعداد درخواست فروش مو: {_fa_num(info['hair'])}\n"
        f"تعداد آنالیز: {_fa_num(info['analysis'])}\n"
        f"تعداد سفارش: {_fa_num(info['shop'])}\n\n"
        "⚠️ آیا از حذف این کاربر مطمئن هستید؟\n"
        "تمام اطلاعات کاربر حذف می‌شود و قابل بازگشت نیست."
    )



def make_state_pruner(user_states, ai_temp_data, ttl_seconds=2 * 3600, max_users=2000):
    """هرس stateهای رهاشدهی ربات (فیکس نشت حافظه).

    فقط هرس میکند؛ هیچ هندلری تغییر نمیدهد. خروجی (touch, maybe_cleanup) است:
      - touch(uid): ثبت زمان آخرین تعامل (در ورودی هر هندلر صدا زده میشود)
      - maybe_cleanup(): هر ۱۰۰ آپدیت یکبار هرس (کهنهها + سقف سخت حافظه)
    """
    import time as _time

    _state_touch = {}              # uid -> زمان آخرین تعامل
    _state_cleanup_tick = [0]      # شمارندهی سبک برای هرس هر ۱۰۰ آپدیت

    def _touch(uid):
        try:
            if not uid:
                return
            _state_touch[uid] = _time.time()
        except Exception:
            pass

    def _cleanup():
        try:
            now = _time.time()
            # ۱) حذف کاربران بیش از TTL بیتعامل
            for u in [u for u, t in list(_state_touch.items()) if now - t > ttl_seconds]:
                user_states.pop(u, None)
                ai_temp_data.pop(u, None)
                _state_touch.pop(u, None)
            # ۲) سقف سخت: فعالترین کاربران نگه داشته میشوند
            if len(user_states) > max_users or len(_state_touch) > max_users:
                keep = set(sorted(_state_touch, key=_state_touch.get, reverse=True)[:max_users])
                for u in list(user_states):
                    if u not in keep:
                        user_states.pop(u, None)
                        ai_temp_data.pop(u, None)
                for u in list(_state_touch):
                    if u not in keep:
                        _state_touch.pop(u, None)
        except Exception:
            pass

    def _maybe_cleanup():
        try:
            _state_cleanup_tick[0] += 1
            if _state_cleanup_tick[0] >= 100:
                _state_cleanup_tick[0] = 0
                _cleanup()
        except Exception:
            pass

    return _touch, _maybe_cleanup


def _split_text_chunks(text: str, limit: int):
    """شکست متن به تکه‌های ≤ limit با اولویت \\n\\n سپس \\n سپس برش سخت."""
    chunks, cur = [], ""
    for para in (text or "").split("\n\n"):
        candidate = (cur + "\n\n" + para) if cur else para
        if len(candidate) <= limit:
            cur = candidate
            continue
        if cur:
            chunks.append(cur)
            cur = ""
        for line in para.split("\n"):
            cand = (cur + "\n" + line) if cur else line
            if len(cand) <= limit:
                cur = cand
            else:
                if cur:
                    chunks.append(cur)
                    cur = ""
                while len(line) > limit:
                    chunks.append(line[:limit])
                    line = line[limit:]
                cur = line
    if cur:
        chunks.append(cur)
    return chunks


async def send_long_message(bot, chat_id, text, *, message=None, chunk_limit=4000, delay=0.5, **kwargs):
    """مرحلهٔ ۴ se.md / BUG-004 — ارسال امن پیام‌های بلند بله (سقف ۴۰۹۶).

    متن ≤ chunk_limit → دقیقاً یک ارسال با همان kwargs.
    متن بلند‌تر → شکست روی پاراگراف/خط؛ reply_markup و بقیهٔ kwargs فقط
    برای تکهٔ آخر؛ تأخیر delay بین تکه‌ها.
    اگر `message` داده شود، تکهٔ اول/تنها با message.reply_text می‌رود تا
    پیوند پاسخ (reply) حفظ شود و بقیهٔ تکه‌ها با bot.send_message.
    """
    import asyncio
    text = text or ""
    if bot is None and message is not None:
        bot = message.get_bot()
    if len(text) <= chunk_limit:
        if message is not None:
            return await message.reply_text(text, **kwargs)
        return await bot.send_message(chat_id=chat_id, text=text, **kwargs)
    pieces = _split_text_chunks(text, chunk_limit)
    sent = None
    for i, piece in enumerate(pieces):
        is_last = i == len(pieces) - 1
        extra = dict(kwargs) if is_last else {
            k: v for k, v in kwargs.items() if k in ("disable_notification",)
        }
        if message is not None and i == 0:
            sent = await message.reply_text(piece, **extra)
        else:
            sent = await bot.send_message(chat_id=chat_id, text=piece, **extra)
        if not is_last:
            await asyncio.sleep(delay)
    return sent
