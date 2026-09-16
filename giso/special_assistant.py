# -*- coding: utf-8 -*-
"""giso/special_assistant.py — دستیار هوشمند اختصاصی «آقا رضا» برای ادمین اختصاصی.

- فقط برای شماره ادمین اختصاصی فعال است (giso.config.is_special_admin).
- از همان موتور ai_runtime (failover پروایدرها) استفاده می‌کند؛ هیچ سیستم پرداخت/اعتبار جدیدی ندارد.
- تاریخچه در جدول giso_special_assistant_chats ذخیره می‌شود و با actor_key مبتنی بر
  شماره، بین سایت و ربات بله **مشترک** است.
- دستیار فقط در حوزه مدیریت سایت/ربات جواب می‌دهد، آمار واقعی از دیتابیس می‌دهد و
  هیچ‌وقت عملیات حذف/تغییر انجام نمی‌دهد (فقط خواندن + پیشنهاد).
"""
from __future__ import annotations

import json
import logging
import re
from datetime import datetime

logger = logging.getLogger("giso_special_assistant")

ASSISTANT_NAME = "آقا رضا"
HISTORY_LIMIT = 50
MAX_TOKENS = 600

SYSTEM_PROMPT = """تو «آقا رضا» هستی؛ دستیار هوشمند شخصی خانم مهندس صادقی در پنل مدیریت گیسو.

مخاطب: خانم مهندس صادقی (همسر آقای مهندس صادقی، مدیر گروه گیسو) که تازه به تیم اضافه شده و نقش ادمین اختصاصی دارد.

لحن و شخصیت:
- صمیمی، محترمانه و دلگرم‌کننده؛ مثل یک همکار مشاور دلسوز.
- جملات کوتاه و دقیق (حداکثر ۳ تا ۴ خط).
- می‌توانی گاهی با گل 🌸 یا تشویق کوتاه همراه باشی، ولی زیاده‌روی نکن.

نمونه لحن:
- «سلام خانم مهندس! 🌸 خوش اومدید. من آقا رضا هستم.»
- «حتماً کمکتون می‌کنم؛ قدم‌به‌قدم می‌ریم جلو.»
- «آفرین! درست انجام دادید. 👏»
- «نگران نباشید، من کنارتونم.»

حوزه کاری (فقط همین):
- آموزش قدم‌به‌قدم بخش‌های پنل مدیریت گیسو (خرید مو، سفارش‌های فروشگاه، بازارچه مو، مراکز زیبایی، نظرات، گفتگوها/تیکت‌ها، کاربران، مرکز مالی).
- گزارش وضعیت واقعی از سامانه (آمار در ادامه‌ی همین پیام به‌صورت داده به تو داده می‌شود؛ فقط همان‌ها را بگو).
- کمک به پاسخ مشتری: پیام مشتری را تحلیل کن و یک «پیشنهاد پاسخ» مؤدبانه بده.
- راهنمایی مسیر کاری.

قوانین سخت:
۱. خارج از حوزه مدیریت سایت/ربات گیسو جواب نده. اگر موضوع غیرمرتبط بود، دقیقاً بگو:
   «خانم مهندس، این موضوع خارج از کار ماست. بیایید روی سایت تمرکز کنیم! 🌸»
۲. هیچ عدد/آماری از خودت ن‌ساز؛ فقط از بخش «آمار زنده سامانه» استفاده کن. اگر داده‌ای نبود بگو فعلاً آماری در دسترس نیست.
۳. تو هیچ عملیاتی (حذف/تغییر/تأیید/پرداخت) انجام نمی‌دهی؛ فقط راهنمایی و پیشنهاد می‌دهی. برای انجام کار، کاربر را به همان بخش پنل هدایت کن.
۴. کوتاه، فارسی و روان بنویس.
"""

OFF_TOPIC_HINT = "خانم مهندس، این موضوع خارج از کار ماست. بیایید روی سایت تمرکز کنیم! 🌸"


def _now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _conn():
    from giso.base import get_giso_db_conn
    return get_giso_db_conn()


def init_special_assistant_tables() -> bool:
    """جدول سبک تاریخچه مشترک سایت/ربات (افزودنی و idempotent)."""
    try:
        with _conn() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS giso_special_assistant_chats (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    actor_key TEXT NOT NULL,
                    channel TEXT DEFAULT 'site',
                    page_path TEXT DEFAULT '',
                    role TEXT DEFAULT 'assistant',
                    content TEXT NOT NULL DEFAULT '',
                    created_at TEXT DEFAULT ''
                )
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_special_assistant_actor "
                "ON giso_special_assistant_chats(actor_key, id)"
            )
            conn.commit()
        return True
    except Exception as exc:
        logger.warning("special assistant init: %s", exc)
        return False


def actor_key_for(phone_norm: str) -> str:
    """actor روی شماره سوار است تا تاریخچه‌ی سایت و ربات یکی باشد.

    شماره را نرمال می‌کند تا فرمت‌های «09...» / «989...» / «+989...» همگی به یک
    کلید برسند (سایت normalize_phone می‌فرستد؛ این تابع هم خودش تضمین می‌کند).
    """
    raw = str(phone_norm or "").strip()
    norm = raw
    try:
        from giso.base import normalize_phone as _np
        norm = _np(raw) or raw
    except Exception:
        pass
    # به ۱۰ رقم استاندارد برمی‌گردیم (9xxxxxxxxx) تا فرمت‌های 09/98/+98 یکی شوند.
    digits = re.sub(r"\D", "", norm or raw)
    if digits.startswith("98") and len(digits) == 12:
        digits = digits[2:]
    elif digits.startswith("0") and len(digits) == 11:
        digits = digits[1:]
    key_phone = digits if len(digits) == 10 else (norm or raw)
    return f"special_assistant:{key_phone}"


def get_history(actor_key: str, limit: int = HISTORY_LIMIT) -> list[dict]:
    try:
        init_special_assistant_tables()
        with _conn() as conn:
            rows = conn.execute(
                "SELECT role, content, channel, created_at FROM giso_special_assistant_chats "
                "WHERE actor_key=? ORDER BY id DESC LIMIT ?",
                (actor_key, int(limit)),
            ).fetchall()
        out = [
            {"role": ("assistant" if r["role"] == "assistant" else "user"),
             "content": r["content"], "channel": r["channel"], "created_at": r["created_at"]}
            for r in reversed(rows)
        ]
        return out
    except Exception as exc:
        logger.warning("special assistant history: %s", exc)
        return []


def _log(actor_key: str, role: str, content: str, channel: str, page_path: str = "") -> None:
    try:
        with _conn() as conn:
            conn.execute(
                "INSERT INTO giso_special_assistant_chats(actor_key, channel, page_path, role, content, created_at) "
                "VALUES (?,?,?,?,?,?)",
                (actor_key, channel, (page_path or "")[:300], role, (content or "")[:4000], _now()),
            )
            conn.commit()
        # هرس: فقط آخرین پیام‌ها نگه داشته شود (جدول سبک بماند).
        try:
            with _conn() as conn:
                conn.execute(
                    "DELETE FROM giso_special_assistant_chats WHERE actor_key=? AND id NOT IN "
                    "(SELECT id FROM giso_special_assistant_chats WHERE actor_key=? ORDER BY id DESC LIMIT ?)",
                    (actor_key, actor_key, HISTORY_LIMIT * 2),
                )
                conn.commit()
        except Exception:
            pass
    except Exception as exc:
        logger.warning("special assistant log: %s", exc)


def live_stats() -> dict:
    """آمار زنده و واقعی سامانه (فقط خواندنی). همه در try؛ هیچ‌وقت جریان چت را نمی‌شکند."""
    stats: dict = {}
    try:
        with _conn() as conn:
            def q1(sql, *a):
                try:
                    return int((conn.execute(sql, a).fetchone() or [0])[0] or 0)
                except Exception:
                    return 0
            today = datetime.now().strftime("%Y-%m-%d")
            stats["hair_orders_pending"] = q1(
                "SELECT COUNT(*) FROM hair_orders WHERE status IN ('pending','reviewing')")
            stats["hair_orders_total"] = q1("SELECT COUNT(*) FROM hair_orders")
            stats["shop_orders_total"] = q1("SELECT COUNT(*) FROM product_orders")
            stats["shop_orders_new"] = q1(
                "SELECT COUNT(*) FROM product_orders WHERE status IN ('new','pending')")
            stats["marketplace_pending_listings"] = q1(
                "SELECT COUNT(*) FROM hair_listings WHERE status='pending_review' AND COALESCE(deleted_at,'')=''")
            stats["marketplace_open_listings"] = q1(
                "SELECT COUNT(*) FROM hair_listings WHERE status IN ('published','negotiating') AND COALESCE(deleted_at,'')=''")
            stats["open_tickets"] = q1(
                "SELECT COUNT(*) FROM giso_support_tickets WHERE status NOT IN ('closed','done','resolved')")
            stats["users_total"] = q1("SELECT COUNT(*) FROM giso_web_auth")
            stats["users_new_today"] = q1(
                "SELECT COUNT(*) FROM giso_web_auth WHERE created_at >= ?", today)
            stats["centers_pending"] = q1(
                "SELECT COUNT(*) FROM beauty_centers WHERE status IN ('pending_review','reviewing')")
    except Exception as exc:
        logger.warning("special assistant stats: %s", exc)
    return stats


def _stats_block(stats: dict) -> str:
    fa = lambda n: str(int(n or 0)).translate(str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹"))
    lines = [
        "آمار زنده سامانه (فقط برای اطلاع خودت؛ در صورت پرسش همین‌ها را خلاصه و فارسی بگو):",
        f"- درخواست‌های فروش مو: {fa(stats.get('hair_orders_pending'))} در انتظار بررسی (در کل {fa(stats.get('hair_orders_total'))}).",
        f"- سفارش فروشگاه: {fa(stats.get('shop_orders_new'))} جدید (در کل {fa(stats.get('shop_orders_total'))}).",
        f"- بازارچه مو: {fa(stats.get('marketplace_pending_listings'))} آگهی در انتظار تأیید / {fa(stats.get('marketplace_open_listings'))} آگهی فعال.",
        f"- مراکز زیبایی: {fa(stats.get('centers_pending'))} مرکز در انتظار بررسی.",
        f"- تیکت/گفتگوی باز: {fa(stats.get('open_tickets'))}.",
        f"- کاربران: {fa(stats.get('users_total'))} نفر (امروز {fa(stats.get('users_new_today'))} ثبت‌نام جدید).",
    ]
    return "\n".join(lines)


# راهنمای کوتاه هر بخش پنل برای پیام خودکارِ تشخیص صفحه.
PAGE_HINTS = {
    "hair_sale": "این بخش «مدیریت خرید مو» است: درخواست‌های فروش مو را می‌بینید و قیمت‌گذاری/بررسی می‌کنید.",
    "marketplace": "این بخش «بازارچه مو» است: آگهی‌های فروش مو را تأیید یا رد می‌کنید و وضعیت معاملات را می‌بینید.",
    "beauty_centers": "این بخش «مراکز زیبایی» است: مرکز‌های ثبت‌شده را بررسی و تأیید می‌کنید.",
    "shop_orders": "این بخش «سفارش‌های فروشگاه» است: سفارش‌ها و وضعیت ارسال را مدیریت می‌کنید.",
    "reviews": "این بخش «نظرات عمومی» است: نظرات کاربران را مرور می‌کنید.",
    "consults": "این بخش «گفتگوها» است: تیکت‌های پشتیبانی و پاسخ به مشتری‌ها اینجاست.",
    "users": "این بخش «مدیریت کاربران» است: فهرست کاربران سایت را می‌بینید.",
    "wallet": "این بخش «مرکز مالی» است: تراکنش‌ها و درخواست‌های شارژ/تسویه را مشاهده و بررسی می‌کنید.",
    "dashboard": "این «پیشخوان» است: خلاصه وضعیت و آمار امروز را یک‌جا دارید.",
    "account": "این «حساب کاربری» شماست.",
}


def welcome_for_page(page: str = "") -> str:
    page = (page or "").strip()
    hint = PAGE_HINTS.get(page)
    if hint:
        return f"خانم مهندس عزیز، {hint} 🌸 اگر خواستید، قدم‌به‌قدم با هم بررسی‌شان کنیم."
    return "سلام خانم مهندس! 🌸 من آقا رضا هستم؛ برای توضیح هر بخش یا گزارش وضعیت، بپرسید."


def page_intro(page: str = "", stats: dict | None = None) -> str:
    """پیام خودکارِ بازشدن یک بخش، با آمار همان بخش (مختصر و واقعی)."""
    fa = lambda n: str(int(n or 0)).translate(str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹"))
    s = stats if isinstance(stats, dict) else {}
    page = (page or "").strip()
    if page == "hair_sale":
        return (f"خانم مهندس، الان در «مدیریت خرید مو» هستید. {fa(s.get('hair_orders_pending'))} درخواست "
                "در انتظار بررسی/قیمت‌گذاری است. اگر خواستید، روی هر درخواست می‌رویم و قیمت پیشنهاد می‌دهیم. 🌸")
    if page == "marketplace":
        return (f"اینجا «بازارچه مو» است. {fa(s.get('marketplace_pending_listings'))} آگهی در انتظار تأیید و "
                f"{fa(s.get('marketplace_open_listings'))} آگهی فعال داریم. آمار بازارچه همیشه برای من به‌روز است.")
    if page == "beauty_centers":
        return f"«مراکز زیبایی»: {fa(s.get('centers_pending'))} مرکز در انتظار بررسی است. اگر مرکزی نیاز به تأیید داشت، با هم مرور می‌کنیم."
    if page == "shop_orders":
        return f"«سفارش‌های فروشگاه»: {fa(s.get('shop_orders_new'))} سفارش جدید در جریان است. وضعیت ارسال را همین‌جا می‌بینید."
    if page == "consults":
        return f"«گفتگوها»: {fa(s.get('open_tickets'))} تیکت/گفتگوی باز داریم. اگر متن مشتری را برایم بفرستید، یک «پیشنهاد پاسخ» می‌نویسم."
    if page == "reviews":
        return "«نظرات عمومی» اینجاست. اگر نظری نیاز به پاسخ داشت، بفرمایید تا یک پاسخ مؤدبانه پیشنهاد بدهم."
    if page == "users":
        return (f"«مدیریت کاربران»: در مجموع {fa(s.get('users_total'))} کاربر داریم و امروز {fa(s.get('users_new_today'))} ثبت‌نام جدید. "
                "تغییرات حساس کاربر فقط با تأیید شما انجام می‌شود؛ من فقط راهنمایی می‌کنم.")
    if page == "wallet":
        return "«مرکز مالی»: تراکنش‌ها و درخواست‌های شارژ/تسویه را اینجا می‌بینید. هر موردی که مطمئن نبودید، از من بپرسید."
    if page == "dashboard":
        return (f"به پیشخوان خوش آمدید 🌸 امروز {fa(s.get('users_new_today'))} کاربر جدید، "
                f"{fa(s.get('hair_orders_pending'))} درخواست مو در انتظار و {fa(s.get('marketplace_pending_listings'))} "
                "آگهی بازارچه در انتظار تأیید داریم. هر کدام را بخواهید، شروع می‌کنیم.")
    return welcome_for_page(page)


async def _ask_ai(messages: list[dict]) -> dict:
    """فراخوانی مستقیم موتور failover؛ رایگان برای این دستیار (از اعتبار سیستم)."""
    from giso.ai_runtime import chat_with_failover
    return await chat_with_failover(messages, temperature=0.6, max_tokens=MAX_TOKENS, role="admin")


async def answer(phone_norm: str, user_message: str, channel: str = "site",
                 page_path: str = "") -> dict:
    """نقطه ورود اصلی: پیام کاربر → پاسخ آقا رضا. تاریخچه خودکار ذخیره می‌شود."""
    try:
        init_special_assistant_tables()
        ak = actor_key_for(phone_norm)
        user_message = (user_message or "").strip()
        if not user_message:
            return {"ok": False, "text": "پیامی ارسال نشد."}
        _log(ak, "user", user_message, channel, page_path)
        history = get_history(ak)
        convo = [{"role": ("user" if h["role"] == "user" else "assistant"),
                  "content": h["content"]} for h in history][-12:]
        stats = live_stats()
        messages = [{"role": "system", "content": SYSTEM_PROMPT + "\n\n" + _stats_block(stats)}]
        messages.extend(convo)
        res = await _ask_ai(messages)
        if res.get("ok") and res.get("text"):
            text = str(res["text"]).strip()
            _log(ak, "assistant", text, channel, page_path)
            return {"ok": True, "text": text, "provider": res.get("provider", ""), "stats": stats}
        return {"ok": False,
                "text": "خانم مهندس، الان دستیار هوشمند در دسترس نیست؛ کمی بعد دوباره بپرسید. 🌸",
                "stats": stats}
    except Exception as exc:
        logger.warning("special assistant answer: %s", exc)
        return {"ok": False, "text": "خطایی در دستیار رخ داد؛ کمی بعد دوباره تلاش کنید."}


def answer_sync(phone_norm: str, user_message: str, channel: str = "site", page_path: str = "") -> dict:
    from giso.async_compat import run_async_safe
    return run_async_safe(answer(phone_norm, user_message, channel=channel, page_path=page_path))


__all__ = [
    "ASSISTANT_NAME", "SYSTEM_PROMPT", "init_special_assistant_tables",
    "actor_key_for", "get_history", "live_stats", "welcome_for_page",
    "answer", "answer_sync",
]
