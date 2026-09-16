"""
handlers_ai.py — هندلرهای پنل «🤖 مدیریت AI»

وابستگی مجاز: db، config، core، ui و stdlib
هرگز از handlers.py import نکنید (زنجیرهٔ import را نشکنید).

این ماژول جایگزین بخش aiogram فایل ai.py مستقل شده است:
  • aiogram Router      → توابع ساده که از handlers.py صدا زده می‌شوند
  • aiogram FSM States  → همان ctx.user_data["state"] پروژه
  • دیتابیس جداگانه     → data/bot.db (توابع db.get_ai_provider و ...)
"""
import json
import logging

from db import (
    add_ai_provider,
    delete_ai_provider,
    get_ai_provider,
    list_ai_providers,
    toggle_ai_provider,
    update_ai_provider_field,
)
from core import check_ai_provider, check_all_ai_providers, ask_ai_fast
from ui import (
    btn, mkb, back_btn, safe_answer,
    ai_admin_kb, ai_providers_kb, ai_edit_fields_kb, ai_kind_kb,
    show_ai_panel, show_ai_list, show_ai_status,
)

logger = logging.getLogger(__name__)

# ========================= stateهای این ماژول =========================
# همگی با پیشوند wait_ai_ تا با stateهای موجود تداخل نداشته باشند.
AI_STATES = (
    "wait_ai_name",       # نام پروایدر جدید
    "wait_ai_base_url",   # Base URL
    "wait_ai_api_key",    # API Key
    "wait_ai_api_root",   # API Root (برای Cloudflare)
    "wait_ai_timeout",    # Timeout — پایان فلوی افزودن
    "wait_ai_field",      # مقدار جدید یک فیلد در ویرایش
    "wait_ai_prompt",     # متن تست گفتگو
)

# برچسب فارسی فیلدها
_FIELD_LABELS = {
    "api_key":  "🔑 API Key",
    "base_url": "🌐 Base URL",
    "api_root": "📁 API Root",
    "timeout":  "⏱ Timeout",
    "headers":  "📋 Headers (JSON)",
    "fallback": "🔄 مدل‌های پشتیبان (JSON)",
}


def _clean(ctx):
    """پاک‌سازی دادهٔ موقتِ فلوی AI."""
    for k in ("ai_new", "ai_edit_provider", "ai_edit_field"):
        ctx.user_data.pop(k, None)


def _fmt_check(name: str, result: dict) -> str:
    """متن نتیجهٔ بررسی یک پروایدر."""
    status = result.get("status", "")
    if str(status).startswith("ok"):
        models = result.get("models") or []
        return (
            f"✅ {name} — سالم است\n"
            f"━━━━━━━━━━━━━━━━\n"
            f"🎯 مدل انتخابی: {result.get('selected') or '—'}\n"
            f"📚 مدل‌های موجود: {'، '.join(models[:5]) if models else '—'}"
        )
    return (
        f"❌ {name} — {status}\n"
        f"━━━━━━━━━━━━━━━━\n"
        f"⚠️ {result.get('error') or '—'}"
    )


# ========================= هندلر callbackها =========================

async def handle_ai_callback(d: str, q, ctx) -> bool:
    """
    پردازش همهٔ callbackهای AI.
    خروجی: True اگر این callback پردازش شد، False اگر مربوط به AI نبود.
    دسترسی ادمین قبلاً در handlers.py بررسی شده است.
    """
    # ---- صفحهٔ اصلی ----
    if d == "a_ai_panel":
        _clean(ctx)
        await show_ai_panel(q, is_q=True)
        return True

    if d == "ai_list":
        await show_ai_list(q, is_q=True)
        return True

    if d == "ai_status":
        await show_ai_status(q, is_q=True)
        return True

    # ---- انتخاب پروایدر برای عملیات ----
    if d in ("ai_edit", "ai_delete", "ai_toggle", "ai_check_one"):
        titles = {
            "ai_edit":      "✏️ کدام پروایدر ویرایش شود؟",
            "ai_delete":    "🗑 کدام پروایدر حذف شود؟",
            "ai_toggle":    "⏯ وضعیت کدام پروایدر تغییر کند؟",
            "ai_check_one": "🔄 کدام پروایدر بررسی شود؟",
        }
        action = d.split("_", 1)[1]      # edit | delete | toggle | check_one
        await q.edit_message_text(titles[d], reply_markup=ai_providers_kb(action))
        return True

    # ---- اجرای عملیات روی پروایدر انتخاب‌شده ----
    if d.startswith("ai_do|"):
        parts = d.split("|", 2)
        if len(parts) < 3:
            await safe_answer(q, "❌ درخواست نامعتبر.", True)
            return True
        action, name = parts[1], parts[2]

        if action == "edit":
            ctx.user_data["ai_edit_provider"] = name
            row = get_ai_provider(name)
            if row is None:
                await safe_answer(q, "❌ پروایدر پیدا نشد.", True)
                return True
            await q.edit_message_text(
                f"✏️ ویرایش «{name}»\n"
                "━━━━━━━━━━━━━━━━\n"
                f"نوع: {row['kind']}\n"
                f"Base URL: {row['base_url'] or '—'}\n"
                f"API Root: {row['api_root'] or '—'}\n"
                f"Timeout: {row['timeout']} ثانیه\n"
                f"API Key: {'✅ ثبت‌شده' if (row['api_key'] or '').strip() else '❌ ثبت‌نشده'}\n\n"
                "کدام فیلد را می‌خواهید تغییر دهید؟",
                reply_markup=ai_edit_fields_kb(name),
            )
            return True

        if action == "toggle":
            new_state = toggle_ai_provider(name)
            if new_state is None:
                await safe_answer(q, "❌ پروایدر پیدا نشد.", True)
                return True
            txt = "فعال ✅" if new_state else "غیرفعال ❌"
            logger.info("🤖 ادمین وضعیت پروایدر «%s» را به %s تغییر داد.", name, txt)
            await safe_answer(q, f"وضعیت «{name}» → {txt}", True)
            await show_ai_panel(q, is_q=True)
            return True

        if action == "delete":
            # تایید دومرحله‌ای — هماهنگ با سایر حذف‌های ربات
            await q.edit_message_text(
                "⚠️ تایید حذف\n"
                "━━━━━━━━━━━━━━━━\n\n"
                f"🤖 پروایدر: «{name}»\n\n"
                "❗️ این عملیات قابل بازگشت نیست.\nآیا مطمئن هستید؟",
                reply_markup=mkb([
                    [btn("✅ بله، حذف کن", f"ai_delok|{name}")],
                    [btn("❌ انصراف", "a_ai_panel")],
                ]),
            )
            return True

        if action == "check_one":
            await q.edit_message_text(f"⏳ در حال بررسی «{name}»…")
            result = await check_ai_provider(name)
            await q.edit_message_text(_fmt_check(name, result), reply_markup=ai_admin_kb())
            return True

        await safe_answer(q, "❌ عملیات ناشناخته.", True)
        return True

    # ---- حذف نهایی ----
    if d.startswith("ai_delok|"):
        name = d.split("|", 1)[1]
        ok = delete_ai_provider(name)
        if ok:
            logger.info("🗑 ادمین پروایدر AI «%s» را حذف کرد.", name)
        await safe_answer(q, f"{'✅ حذف شد' if ok else '❌ پیدا نشد'}: {name}", True)
        await show_ai_panel(q, is_q=True)
        return True

    # ---- بررسی همه ----
    if d == "ai_check_all":
        rows = list_ai_providers()
        if not rows:
            await safe_answer(q, "هیچ پروایدری ثبت نشده است.", True)
            return True
        await q.edit_message_text(f"⏳ در حال بررسی {len(rows)} پروایدر…")
        results = await check_all_ai_providers()
        lines = ["🔁 نتیجهٔ بررسی همه", "━━━━━━━━━━━━━━━━"]
        ok_n = 0
        for r in results:
            good = str(r.get("status", "")).startswith("ok")
            ok_n += 1 if good else 0
            icon = "✅" if good else "❌"
            detail = r.get("selected") or r.get("error") or "—"
            lines.append(f"{icon} {r['name']} — {str(detail)[:60]}")
        lines += ["", f"📊 سالم: {ok_n} از {len(results)}"]
        await q.edit_message_text("\n".join(lines), reply_markup=ai_admin_kb())
        return True

    # ---- افزودن پروایدر ----
    if d == "ai_add":
        _clean(ctx)
        ctx.user_data["ai_new"] = {}
        ctx.user_data["state"] = "wait_ai_name"
        await q.edit_message_text(
            "➕ افزودن پروایدر جدید\n"
            "━━━━━━━━━━━━━━━━\n\n"
            "۱/۵ — نام پروایدر را بفرستید:\n"
            "(مثال: MyGPT)",
            reply_markup=mkb([back_btn("a_ai_panel")]),
        )
        return True

    if d.startswith("ai_kind|"):
        kind = d.split("|", 1)[1]
        ctx.user_data.setdefault("ai_new", {})["kind"] = kind
        ctx.user_data["state"] = "wait_ai_base_url"
        if kind == "cloudflare":
            hint = "برای Cloudflare معمولاً لازم نیست — «-» بفرستید."
        else:
            hint = "مثال: https://api.groq.com/openai/v1"
        await q.edit_message_text(
            f"✅ نوع: {kind}\n\n۳/۵ — Base URL را بفرستید:\n{hint}",
            reply_markup=mkb([back_btn("a_ai_panel")]),
        )
        return True

    # ---- ویرایش یک فیلد ----
    if d.startswith("ai_field|"):
        parts = d.split("|", 2)
        if len(parts) < 3:
            await safe_answer(q, "❌ درخواست نامعتبر.", True)
            return True
        name, field = parts[1], parts[2]
        row = get_ai_provider(name)
        if row is None:
            await safe_answer(q, "❌ پروایدر پیدا نشد.", True)
            return True
        ctx.user_data["ai_edit_provider"] = name
        ctx.user_data["ai_edit_field"] = field
        ctx.user_data["state"] = "wait_ai_field"

        col = {"headers": "headers_json", "fallback": "fallback_json"}.get(field, field)
        cur = row[col] if col in row.keys() else ""
        if field == "api_key" and cur:
            cur = str(cur)[:6] + "…"      # کلید کامل نمایش داده نمی‌شود
        hints = {
            "headers":  '\nنمونه: {"X-Title": "MyBot"}',
            "fallback": '\nنمونه: ["model-a", "model-b"]',
            "timeout":  "\nعدد به ثانیه (مثلاً 20)",
        }
        await q.edit_message_text(
            f"✏️ {_FIELD_LABELS.get(field, field)} — «{name}»\n"
            "━━━━━━━━━━━━━━━━\n"
            f"مقدار فعلی: {cur or '—'}\n\n"
            f"مقدار جدید را بفرستید:{hints.get(field, '')}",
            reply_markup=mkb([back_btn(f"ai_do|edit|{name}")]),
        )
        return True

    # ---- تست گفتگو ----
    if d == "ai_try":
        ctx.user_data["state"] = "wait_ai_prompt"
        await q.edit_message_text(
            "💬 تست گفتگو با هوش مصنوعی\n"
            "━━━━━━━━━━━━━━━━\n\n"
            "یک سؤال یا متن بفرستید.\n"
            "ربات به‌ترتیب پروایدرهای فعال را امتحان می‌کند و\n"
            "اولین پاسخ موفق را نشان می‌دهد.",
            reply_markup=mkb([back_btn("a_ai_panel")]),
        )
        return True

    return False      # مربوط به AI نبود


# ========================= هندلر پیام‌های متنی (stateها) =========================

async def handle_ai_state(state: str, text: str, msg, ctx) -> bool:
    """
    پردازش stateهای متنی AI.
    خروجی: True اگر پردازش شد.
    """
    # ---- فلوی افزودن ----
    if state == "wait_ai_name":
        name = text.strip()
        if not name:
            await msg.reply_text("❌ نام نمی‌تواند خالی باشد.")
            return True
        if get_ai_provider(name) is not None:
            ctx.user_data["state"] = "wait_ai_name"
            await msg.reply_text(
                f"❌ پروایدری با نام «{name}» از قبل وجود دارد.\nنام دیگری بفرستید:",
                reply_markup=mkb([back_btn("a_ai_panel")]),
            )
            return True
        ctx.user_data.setdefault("ai_new", {})["name"] = name
        ctx.user_data.pop("state", None)      # منتظر کلیک نوع
        await msg.reply_text(
            f"✅ نام: {name}\n\n۲/۵ — نوع پروایدر را انتخاب کنید:",
            reply_markup=ai_kind_kb(),
        )
        return True

    if state == "wait_ai_base_url":
        val = text.strip()
        ctx.user_data.setdefault("ai_new", {})["base_url"] = "" if val == "-" else val
        ctx.user_data["state"] = "wait_ai_api_key"
        await msg.reply_text(
            "۴/۵ — API Key را بفرستید:\n(اگر ندارید «-» بفرستید و بعداً وارد کنید)",
            reply_markup=mkb([back_btn("a_ai_panel")]),
        )
        return True

    if state == "wait_ai_api_key":
        val = text.strip()
        ctx.user_data.setdefault("ai_new", {})["api_key"] = "" if val == "-" else val
        kind = ctx.user_data.get("ai_new", {}).get("kind", "openai")
        if kind == "cloudflare":
            ctx.user_data["state"] = "wait_ai_api_root"
            await msg.reply_text(
                "۵/۵ — API Root را بفرستید:\n"
                "نمونه:\nhttps://api.cloudflare.com/client/v4/accounts/ACCOUNT_ID/ai/run",
                reply_markup=mkb([back_btn("a_ai_panel")]),
            )
        else:
            ctx.user_data.setdefault("ai_new", {})["api_root"] = ""
            ctx.user_data["state"] = "wait_ai_timeout"
            await msg.reply_text(
                "۵/۵ — Timeout به ثانیه (پیش‌فرض ۲۰):",
                reply_markup=mkb([back_btn("a_ai_panel")]),
            )
        return True

    if state == "wait_ai_api_root":
        val = text.strip()
        ctx.user_data.setdefault("ai_new", {})["api_root"] = "" if val == "-" else val
        ctx.user_data["state"] = "wait_ai_timeout"
        await msg.reply_text(
            "⏱ Timeout به ثانیه (پیش‌فرض ۲۰):",
            reply_markup=mkb([back_btn("a_ai_panel")]),
        )
        return True

    if state == "wait_ai_timeout":
        try:
            timeout = max(5, min(120, int(text.strip())))
        except ValueError:
            timeout = 20
        data = ctx.user_data.get("ai_new", {}) or {}
        ctx.user_data.pop("state", None)
        _clean(ctx)

        name = data.get("name", "").strip()
        if not name:
            await msg.reply_text("❌ اطلاعات ناقص بود. دوباره تلاش کنید.",
                                 reply_markup=ai_admin_kb())
            return True

        ok = add_ai_provider(
            name=name,
            kind=data.get("kind", "openai"),
            api_key=data.get("api_key", ""),
            base_url=data.get("base_url", ""),
            api_root=data.get("api_root", ""),
            timeout=timeout,
            enabled=True,
        )
        if not ok:
            await msg.reply_text(f"❌ ذخیرهٔ «{name}» ناموفق بود.",
                                 reply_markup=ai_admin_kb())
            return True

        logger.info("🤖 ادمین پروایدر AI «%s» را افزود.", name)
        await msg.reply_text(f"✅ پروایدر «{name}» ذخیره شد.\n⏳ در حال بررسی…")
        result = await check_ai_provider(name)
        await msg.reply_text(_fmt_check(name, result), reply_markup=ai_admin_kb())
        return True

    # ---- ویرایش فیلد ----
    if state == "wait_ai_field":
        name = ctx.user_data.pop("ai_edit_provider", "")
        field = ctx.user_data.pop("ai_edit_field", "")
        ctx.user_data.pop("state", None)
        if not name or not field:
            await msg.reply_text("❌ اطلاعات ویرایش ناقص بود.", reply_markup=ai_admin_kb())
            return True

        value = text.strip()

        # اعتبارسنجی مقدار بر اساس نوع فیلد
        if field in ("headers", "fallback"):
            try:
                json.loads(value)
            except json.JSONDecodeError:
                ctx.user_data["ai_edit_provider"] = name
                ctx.user_data["ai_edit_field"] = field
                ctx.user_data["state"] = "wait_ai_field"
                await msg.reply_text(
                    "❌ فرمت JSON نامعتبر است. دوباره بفرستید.\n"
                    'نمونه: {"X-Title": "MyBot"}  یا  ["model-a"]',
                    reply_markup=mkb([back_btn(f"ai_do|edit|{name}")]),
                )
                return True
        elif field == "timeout":
            try:
                value = str(max(5, min(120, int(value))))
            except ValueError:
                ctx.user_data["ai_edit_provider"] = name
                ctx.user_data["ai_edit_field"] = field
                ctx.user_data["state"] = "wait_ai_field"
                await msg.reply_text(
                    "❌ Timeout باید عدد باشد (۵ تا ۱۲۰).",
                    reply_markup=mkb([back_btn(f"ai_do|edit|{name}")]),
                )
                return True

        ok = update_ai_provider_field(name, field, value)
        label = _FIELD_LABELS.get(field, field)
        if ok:
            logger.info("🤖 ادمین فیلد %s پروایدر «%s» را تغییر داد.", field, name)
        await msg.reply_text(
            f"{'✅' if ok else '❌'} {label} برای «{name}» "
            f"{'ذخیره شد' if ok else 'ذخیره نشد'}.",
            reply_markup=mkb([
                [btn("🔄 بررسی این پروایدر", f"ai_do|check_one|{name}")],
                [btn("✏️ ویرایش فیلد دیگر", f"ai_do|edit|{name}")],
                back_btn("a_ai_panel"),
            ]),
        )
        return True

    # ---- تست گفتگو ----
    if state == "wait_ai_prompt":
        ctx.user_data.pop("state", None)
        prompt = text.strip()
        if not prompt:
            await msg.reply_text("❌ متن خالی است.", reply_markup=ai_admin_kb())
            return True
        await msg.reply_text("⏳ در حال پرسش از هوش مصنوعی…")
        result = await ask_ai_fast([{"role": "user", "content": prompt}], max_tokens=600)
        if result.get("ok"):
            answer = (result.get("text") or "").strip() or "(پاسخ خالی بود)"
            if len(answer) > 3000:
                answer = answer[:3000] + "\n…"
            body = (
                f"✅ پاسخ از «{result['provider']}»\n"
                f"🎯 مدل: {result.get('model') or '—'}\n"
                "━━━━━━━━━━━━━━━━\n\n"
                f"{answer}"
            )
        else:
            body = (
                "❌ هیچ پروایدری پاسخ نداد\n"
                "━━━━━━━━━━━━━━━━\n\n"
                f"⚠️ {result.get('error') or '—'}\n\n"
                "پیشنهاد: از «🔁 بررسی همه» وضعیت پروایدرها را ببینید."
            )
        await msg.reply_text(body, reply_markup=ai_admin_kb())
        return True

    return False
