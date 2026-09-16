"""
ai_admin.py — هندلرهای ادمینِ «یار هوشمند شغلی».

پیشوند callback: aim_a_    |    پیشوند state: wait_aima_
دسترسی ادمین در handlers.py قبل از فراخوانی بررسی می‌شود، اما اینجا هم
یک لایهٔ دفاعی دوم گذاشته شده است.

وابستگی: core (is_admin)، ui، ai_* — هرگز از handlers.py import نمی‌کند.
"""
import logging

from config import AI_MENTOR_ENABLED
from core import is_admin
from ui import btn, mkb, back_btn, safe_answer

from . import ai_db, ai_market
from .ai_ui import (
    ai_admin_back_kb, ai_admin_core_kb, ai_admin_kb, ai_admin_packs_kb,
    ai_admin_payment_kb, ai_admin_pending_kb, ai_admin_pricing_kb,
    ai_admin_missions_kb, ai_admin_purchase_kb, ai_admin_trends_kb,
    fa_digits, model_routing_admin_kb, model_routing_edit_kb, price_label,
)

logger = logging.getLogger(__name__)

AIMA_STATES = (
    "wait_aima_value",      # مقدار جدید یک تنظیم
    "wait_aima_trend",      # افزودن مهارت ترند
    "wait_aima_pack",       # افزودن بستهٔ اعتبار
    "wait_aima_pay",        # اطلاعات پرداخت (کارت/نام/بانک/توضیح)
    "wait_aima_reject",     # دلیل رد کردن فیش
    "wait_aima_route",      # ویرایش مسیریابی مدل
    "wait_aima_mission",    # تعریف مأموریت واقعی
)

# فیلدهای اطلاعات پرداخت
_PAY_LABELS = {
    "card_number": "💳 شمارهٔ کارت",
    "card_holder": "👤 نام صاحب کارت",
    "bank_name":   "🏦 نام بانک",
    "note":        "📝 توضیح اضافه",
}

_LABELS = {
    "price_roadmap":   "تعرفهٔ نقشه راه",
    "price_chat":      "تعرفهٔ چت منتور",
    "price_challenge": "تعرفهٔ تصحیح چالش",
    "price_report":    "تعرفهٔ گزارش شغلی",
    "price_trends":    "تعرفهٔ مشاهدهٔ ترندها",
    "price_help":      "تعرفهٔ کمک حین آموزش",
    "price_interview_sim": "تعرفهٔ شبیه‌ساز مصاحبه",
    "price_twin":      "تعرفهٔ همزاد شغلی",
    "free_quota":      "سهمیهٔ رایگان اولیه",
    "model":           "مدل/پروایدر",
    "system_prompt":   "پرامپت سفارشی",
    "trends_source":   "آدرس منبع ترندها",
}

_NUMERIC = {"price_roadmap", "price_chat", "price_challenge",
            "price_report", "price_trends", "price_help",
            "price_interview_sim", "price_twin", "free_quota"}


async def _edit(q, text, kb):
    try:
        await q.edit_message_text(text, reply_markup=kb)
    except Exception as e:
        if "not modified" not in str(e).lower():
            logger.debug(f"edit failed: {e}")


# ========================= callback =========================

async def handle_aim_admin_callback(d: str, q, ctx, user) -> bool:
    """پردازش callbackهای aim_a_. خروجی True یعنی پردازش شد."""
    if not d.startswith("aim_a_"):
        return False
    if not is_admin(user):
        await safe_answer(q, "⛔ فقط ادمین.", True)
        return True

    # ---- منوی اصلی ----
    if d == "aim_a_menu":
        ctx.user_data.pop("state", None)
        st = ai_db.module_stats()
        await _edit(q, (
            f"🤖 مدیریت یار هوشمند شغلی\n━━━━━━━━━━━━━━━━\n\n"
            f"👥 کاربران دارای مسیر: {st['users']}\n"
            f"▶️ مسیرهای فعال: {st['paths_active']}\n"
            f"📋 کل مسیرها: {st['paths_total']}\n"
            f"✅ گام‌های تکمیل‌شده: {st['steps_done']}\n"
            f"🔥 مهارت‌های ثبت‌شده: {st['trends']}"
        ), ai_admin_kb())
        return True

    # ---- تنظیمات هسته ----
    if d == "aim_a_core":
        s = ai_db.all_ai_settings()
        model = s.get("model") or "(خودکار — ask_ai_fast)"
        sp = s.get("system_prompt") or "(ندارد)"
        await _edit(q, (
            f"⚙️ تنظیمات هستهٔ AI\n━━━━━━━━━━━━━━━━\n\n"
            f"🧠 مدل: {model}\n"
            f"🎁 سهمیهٔ رایگان: {s.get('free_quota')}\n"
            f"📝 پرامپت سفارشی: {sp[:70]}\n\n"
            f"ℹ️ قالب مدل: «نام‌پروایدر:نام‌مدل» یا خالی برای انتخاب خودکار."
        ), ai_admin_core_kb())
        return True

    if d == "aim_a_toggle":
        if not AI_MENTOR_ENABLED:
            await safe_answer(
                q, "⚠️ ماژول از config.py خاموش است. ابتدا AI_MENTOR_ENABLED را True کنید.",
                True)
            return True
        cur = str(ai_db.get_ai_setting("enabled", "1")).strip()
        new = "0" if cur != "0" else "1"
        ai_db.save_ai_setting("enabled", new)
        await safe_answer(
            q, f"✅ ماژول {'روشن' if new == '1' else 'خاموش'} شد.", True)
        s = ai_db.all_ai_settings()
        await _edit(q, (
            f"⚙️ تنظیمات هستهٔ AI\n━━━━━━━━━━━━━━━━\n\n"
            f"🧠 مدل: {s.get('model') or '(خودکار)'}\n"
            f"🎁 سهمیهٔ رایگان: {s.get('free_quota')}"
        ), ai_admin_core_kb())
        return True

    # ---- تعرفه ----
    if d == "aim_a_pricing":
        await _edit(q, (
            "💰 تعرفهٔ هر اکشن\n━━━━━━━━━━━━━━━━\n\n"
            "برای تغییر، روی هر مورد بزنید. عدد ۰ یعنی رایگان."
        ), ai_admin_pricing_kb())
        return True

    # ---- ویرایش یک تنظیم ----
    if d.startswith("aim_a_set|"):
        key = d.split("|", 1)[1]
        if key not in _LABELS:
            await safe_answer(q, "❌ کلید نامعتبر.", True)
            return True
        ctx.user_data["state"] = "wait_aima_value"
        ctx.user_data["aima_key"] = key
        cur = ai_db.get_ai_setting(key, "")
        hint = "\n\nعدد بفرستید (۰ = رایگان)." if key in _NUMERIC else ""
        if key == "model":
            hint = "\n\nمثال: Groq:llama-3.1-8b-instant\nبرای حالت خودکار «-» بفرستید."
        elif key == "system_prompt":
            hint = "\n\nبرای حذف پرامپت سفارشی «-» بفرستید."
        await _edit(q, (
            f"✏️ {_LABELS[key]}\n━━━━━━━━━━━━━━━━\n\n"
            f"مقدار فعلی: {cur or '(خالی)'}{hint}"
        ), ai_admin_back_kb("aim_a_pricing" if key in _NUMERIC else "aim_a_core"))
        return True

    # ---- ترندها ----
    if d == "aim_a_trends":
        ctx.user_data.pop("state", None)
        trends = ai_db.get_trending_skills(20)
        src = ai_db.get_ai_setting("trends_source", "") or "(تنظیم نشده — فهرست پایه)"
        await _edit(q, (
            f"📈 مدیریت ترندهای بازار\n━━━━━━━━━━━━━━━━\n\n"
            f"تعداد ثبت‌شده: {len(trends)}\n"
            f"🌐 منبع اسکن: {src}\n\n"
            f"برای حذف روی هر مهارت بزنید."
        ), ai_admin_trends_kb(trends))
        return True

    if d == "aim_a_trend_add":
        ctx.user_data["state"] = "wait_aima_trend"
        await _edit(q, (
            "➕ افزودن مهارت\n━━━━━━━━━━━━━━━━\n\n"
            "قالب: نام مهارت | تعداد آگهی\n\nمثال: Rust | 120"
        ), ai_admin_back_kb("aim_a_trends"))
        return True

    if d.startswith("aim_a_trend_del|"):
        name = d.split("|", 1)[1]
        ai_db.delete_market_trend(name)
        await safe_answer(q, f"🗑 {name} حذف شد.", True)
        await _edit(q, "📈 مدیریت ترندهای بازار",
                    ai_admin_trends_kb(ai_db.get_trending_skills(20)))
        return True

    if d == "aim_a_trend_ai":
        await _edit(q, "⏳ در حال تولید فهرست با هوش مصنوعی…", None)
        res = await ai_market.update_market_trends_db(use_ai=True)
        via = {"ai": "با تحلیل AI", "raw": "بدون AI (فهرست پایه)"}.get(res.get("via"), "")
        msg = (f"✅ {res.get('count', 0)} مهارت ثبت شد {via}."
               if res.get("ok") else f"❌ {res.get('error', 'ناموفق')}")
        await _edit(q, msg, ai_admin_trends_kb(ai_db.get_trending_skills(20)))
        return True

    # ---- محتوای یادگیری ----
    if d == "aim_a_content":
        s = ai_db.all_ai_settings()
        await _edit(q, (
            f"📚 محتوای یادگیری با AI\n━━━━━━━━━━━━━━━━\n\n"
            f"محتوای گام‌ها به‌صورت خودکار توسط AI و بر پایهٔ دوره‌های ثبت‌شده در "
            f"ربات تولید می‌شود.\n\n"
            f"🧠 مدل فعلی: {s.get('model') or '(خودکار)'}\n"
            f"📝 پرامپت سفارشی: {(s.get('system_prompt') or '(ندارد)')[:60]}\n\n"
            f"ℹ️ هر دورهٔ جدیدی که در «مدیریت دوره‌ها» بسازید، به‌صورت خودکار "
            f"در نقشه‌های راه بعدی در نظر گرفته می‌شود."
        ), mkb([
            [btn("📝 ویرایش پرامپت سفارشی", "aim_a_set|system_prompt")],
            [btn("🌐 آدرس منبع ترندها", "aim_a_set|trends_source")],
            back_btn("aim_a_menu"),
        ]))
        return True

    # ---- بسته‌های اعتبار ----
    if d == "aim_a_packs":
        ctx.user_data.pop("state", None)
        packs = ai_db.list_credit_packages()
        active = sum(1 for p in packs if p["is_active"])
        await _edit(q, (
            f"💰 مدیریت بسته‌های اعتبار\n━━━━━━━━━━━━━━━━\n\n"
            f"📦 کل بسته‌ها: {len(packs)} | 🟢 فعال: {active}\n\n"
            f"• روی هر بسته بزنید تا فعال/غیرفعال شود.\n"
            f"• دکمهٔ 🗑 بسته را حذف می‌کند.\n\n"
            f"ℹ️ فقط بسته‌های فعال به کاربر نمایش داده می‌شوند."
        ), ai_admin_packs_kb(packs))
        return True

    if d == "aim_a_pack_add":
        ctx.user_data["state"] = "wait_aima_pack"
        await _edit(q, (
            "➕ افزودن بستهٔ اعتبار\n━━━━━━━━━━━━━━━━\n\n"
            "قالب: مقدار اعتبار | قیمت به تومان\n\n"
            "مثال: 5000 | 200000\n"
            "(یعنی ۵۰۰۰ اعتبار به قیمت ۲۰۰ هزار تومان)"
        ), ai_admin_back_kb("aim_a_packs"))
        return True

    if d.startswith("aim_a_pack_tog|"):
        ai_db.toggle_credit_package(d.split("|", 1)[1])
        await safe_answer(q, "✅ وضعیت بسته تغییر کرد.", True)
        await _edit(q, "💰 مدیریت بسته‌های اعتبار",
                    ai_admin_packs_kb(ai_db.list_credit_packages()))
        return True

    if d.startswith("aim_a_pack_del|"):
        ai_db.delete_credit_package(d.split("|", 1)[1])
        await safe_answer(q, "🗑 بسته حذف شد.", True)
        await _edit(q, "💰 مدیریت بسته‌های اعتبار",
                    ai_admin_packs_kb(ai_db.list_credit_packages()))
        return True

    # ---- فاز ۲: مسیریابی مدل‌ها ----
    if d == "aim_a_model_routing":
        ctx.user_data.pop("state", None)
        routes = ai_db.list_model_routing()
        total = sum(float(r.get("cost_per_request") or 0) for r in routes)
        await _edit(q, (
            f"🤖 مدیریت مدل‌های AI\n━━━━━━━━━━━━━━━━\n\n"
            f"برای هر نوع درخواست می‌توانید مدل ارزان‌تر یا قوی‌تر انتخاب کنید.\n"
            f"اگر مدل اصلی جواب ندهد، به‌ترتیب مدل‌های جایگزین امتحان می‌شوند.\n\n"
            f"💵 مجموع هزینهٔ تقریبی یک دور کامل: ${total:.4f}\n\n"
            f"قالب مدل: «نام‌پروایدر:نام‌مدل»"
        ), model_routing_admin_kb(routes))
        return True

    if d.startswith("aim_a_route_view|"):
        act = d.split("|", 1)[1]
        r = ai_db.get_model_routing(act)
        if not r:
            await safe_answer(q, "❌ این اکشن ثبت نشده است.", True)
            return True
        fbs = r.get("fallback_models") or []
        fb_txt = "\n".join(f"  {i}. {m}" for i, m in enumerate(fbs, 1)) or "  (ندارد)"
        await _edit(q, (
            f"{ai_db.ACTION_FA.get(act, act)}\n━━━━━━━━━━━━━━━━\n\n"
            f"وضعیت: {'🟢 فعال' if r.get('is_active') else '🔴 غیرفعال'}\n\n"
            f"🎯 مدل اصلی:\n  {r.get('primary_model') or '(ندارد)'}\n\n"
            f"🔁 مدل‌های جایگزین:\n{fb_txt}\n\n"
            f"💵 هزینهٔ تقریبی: ${float(r.get('cost_per_request') or 0):.4f}"
        ), model_routing_edit_kb(act))
        return True

    if d.startswith("aim_a_route_set|"):
        parts = d.split("|")
        if len(parts) < 3:
            await safe_answer(q, "❌ درخواست نامعتبر.", True)
            return True
        act, field = parts[1], parts[2]
        r = ai_db.get_model_routing(act)
        if not r or field not in ("primary", "fallback", "cost"):
            await safe_answer(q, "❌ نامعتبر.", True)
            return True
        ctx.user_data["state"] = "wait_aima_route"
        ctx.user_data["aima_route_act"] = act
        ctx.user_data["aima_route_field"] = field
        if field == "primary":
            cur, hint = r.get("primary_model", ""), \
                "قالب: «نام‌پروایدر:نام‌مدل»\nمثال: Groq:llama-3.1-8b-instant"
        elif field == "fallback":
            cur = " , ".join(r.get("fallback_models") or [])
            hint = ("مدل‌ها را با کاما جدا کنید.\n"
                    "مثال: LLM7:codestral-latest , Groq:llama-3.3-70b-versatile\n"
                    "برای خالی کردن «-» بفرستید.")
        else:
            cur, hint = str(r.get("cost_per_request", 0)), \
                "عدد اعشاری به دلار.\nمثال: 0.0008"
        await _edit(q, (
            f"✏️ ویرایش {ai_db.ACTION_FA.get(act, act)}\n━━━━━━━━━━━━━━━━\n\n"
            f"مقدار فعلی:\n{cur or '(خالی)'}\n\n{hint}"
        ), ai_admin_back_kb(f"aim_a_route_view|{act}"))
        return True

    if d.startswith("aim_a_route_tog|"):
        act = d.split("|", 1)[1]
        ai_db.toggle_model_routing(act)
        await safe_answer(q, "✅ وضعیت تغییر کرد.", True)
        r = ai_db.get_model_routing(act)
        await _edit(q, (
            f"{ai_db.ACTION_FA.get(act, act)}\n\n"
            f"وضعیت: {'🟢 فعال' if r and r.get('is_active') else '🔴 غیرفعال'}\n\n"
            f"ℹ️ در حالت غیرفعال، این اکشن از انتخاب خودکار پروایدر استفاده می‌کند."
        ), model_routing_edit_kb(act))
        return True

    # ---- فاز ۴: اطلاعات پرداخت ----
    if d == "aim_a_payment_info":
        ctx.user_data.pop("state", None)
        p = ai_db.get_admin_payment_info()
        ready = "🟢 کامل" if ai_db.payment_info_ready() else "🔴 ناقص (شمارهٔ کارت لازم است)"
        await _edit(q, (
            f"💳 اطلاعات پرداخت\n━━━━━━━━━━━━━━━━\n\n"
            f"وضعیت: {ready}\n\n"
            f"💳 شمارهٔ کارت: {p.get('card_number') or '(ثبت نشده)'}\n"
            f"👤 نام صاحب: {p.get('card_holder') or '(ثبت نشده)'}\n"
            f"🏦 بانک: {p.get('bank_name') or '(ثبت نشده)'}\n"
            f"📝 توضیح: {p.get('note') or '(ندارد)'}\n\n"
            f"ℹ️ این اطلاعات هنگام خرید اعتبار به کاربر نمایش داده می‌شود."
        ), ai_admin_payment_kb())
        return True

    if d.startswith("aim_a_pay_set|"):
        key = d.split("|", 1)[1]
        if key not in _PAY_LABELS:
            await safe_answer(q, "❌ فیلد نامعتبر.", True)
            return True
        ctx.user_data["state"] = "wait_aima_pay"
        ctx.user_data["aima_pay_key"] = key
        cur = ai_db.get_admin_payment_info().get(key, "")
        await _edit(q, (
            f"✏️ {_PAY_LABELS[key]}\n━━━━━━━━━━━━━━━━\n\n"
            f"مقدار فعلی: {cur or '(خالی)'}\n\n"
            f"مقدار جدید را بفرستید.\nبرای خالی کردن «-» بفرستید."
        ), ai_admin_back_kb("aim_a_payment_info"))
        return True

    # ---- فاز ۴: فیش‌های در انتظار ----
    if d == "aim_a_pending_purchases":
        ctx.user_data.pop("state", None)
        pend = ai_db.get_pending_purchases(20)
        st = ai_db.purchase_stats()
        await _edit(q, (
            f"📬 فیش‌های در انتظار تأیید\n━━━━━━━━━━━━━━━━\n\n"
            f"⏳ در انتظار: {st['pending']} | ✅ تأییدشده: {st['approved']} | "
            f"❌ ردشده: {st['rejected']}\n"
            f"💎 مجموع اعتبار شارژشده: {fa_digits(st['total_credits'])}\n\n"
            f"برای بررسی روی هر فیش بزنید:"
        ), ai_admin_pending_kb(pend))
        return True

    if d.startswith("aim_a_pur_view|"):
        pur = ai_db.get_purchase(d.split("|", 1)[1])
        if not pur:
            await safe_answer(q, "❌ فیش پیدا نشد.", True)
            return True
        txt = (
            f"🧾 فیش #{pur['id']}\n━━━━━━━━━━━━━━━━\n\n"
            f"👤 کاربر: {pur.get('user_name') or ''} ({pur['user_id']})\n"
            f"💎 اعتبار: {fa_digits(pur['amount'])}\n"
            f"💵 مبلغ: {price_label(pur['price'])}\n"
            f"📅 تاریخ: {pur.get('created_at', '')}\n"
            f"📱 پلتفرم: {pur.get('platform', 'bale')}\n"
            f"وضعیت: {pur.get('status')}\n"
        )
        if pur.get("fiche_text"):
            txt += f"\n📝 رسید متنی:\n{pur['fiche_text']}"

        # اگر عکس فیش هست، جداگانه فرستاده می‌شود
        if pur.get("fiche_file_id"):
            try:
                await q.message.reply_photo(pur["fiche_file_id"], caption=txt,
                                            reply_markup=ai_admin_purchase_kb(pur["id"]))
                await safe_answer(q)
                return True
            except Exception as e:
                logger.debug(f"ارسال عکس فیش ناموفق: {e}")
                txt += "\n\n⚠️ نمایش عکس فیش ممکن نشد."
        await _edit(q, txt, ai_admin_purchase_kb(pur["id"]))
        return True

    if d.startswith("aim_a_pur_ok|"):
        pid = d.split("|", 1)[1]
        pur = ai_db.get_purchase(pid)
        if not pur:
            await safe_answer(q, "❌ فیش پیدا نشد.", True)
            return True
        if pur.get("status") != "pending":
            await safe_answer(q, f"⚠️ این فیش قبلاً بررسی شده ({pur.get('status')}).", True)
            return True

        # ترتیب مهم است: اول قفل‌کردن وضعیت، بعد شارژ.
        # اگر برعکس بود، دو کلیک سریع می‌توانست دو بار شارژ کند.
        if not ai_db.approve_purchase(pid, f"admin:{user.id}"):
            await safe_answer(q, "⚠️ این فیش همین حالا توسط ادمین دیگری بررسی شد.", True)
            return True

        from core import change_credits
        change_credits(int(pur["user_id"]), int(pur["amount"]))
        ai_db.log_ai_usage(int(pur["user_id"]), "credit_purchase", 0, "")

        ok_msg = await _notify_user_purchase(pur, approved=True)
        await safe_answer(q, "✅ تأیید شد و اعتبار شارژ گردید.", True)
        await _edit(q, (
            f"✅ فیش #{pur['id']} تأیید شد.\n\n"
            f"💎 {fa_digits(pur['amount'])} اعتبار به کاربر {pur['user_id']} اضافه شد.\n"
            f"{'📨 به کاربر اطلاع داده شد.' if ok_msg else '⚠️ ارسال پیام به کاربر ناموفق بود.'}"
        ), ai_admin_pending_kb(ai_db.get_pending_purchases(20)))
        return True

    if d.startswith("aim_a_pur_no|"):
        pid = d.split("|", 1)[1]
        pur = ai_db.get_purchase(pid)
        if not pur or pur.get("status") != "pending":
            await safe_answer(q, "⚠️ این فیش قابل رد کردن نیست.", True)
            return True
        ctx.user_data["state"] = "wait_aima_reject"
        ctx.user_data["aima_pur_id"] = pid
        await _edit(q, (
            f"❌ رد فیش #{pid}\n━━━━━━━━━━━━━━━━\n\n"
            "دلیل رد را بنویسید (برای کاربر ارسال می‌شود).\n"
            "برای رد بدون توضیح «-» بفرستید."
        ), ai_admin_back_kb("aim_a_pending_purchases"))
        return True

    # ---- فاز ۴: مدیریت مأموریت‌های واقعی ----
    if d == "aim_a_missions":
        ctx.user_data.pop("state", None)
        ms = ai_db.list_real_missions()
        act = sum(1 for m in ms if m["status"] == "active")
        await _edit(q, (
            f"📝 مدیریت مأموریت‌های واقعی\n━━━━━━━━━━━━━━━━\n\n"
            f"📋 کل: {len(ms)} | 🟢 فعال: {act}\n\n"
            f"• روی هر مأموریت بزنید تا فعال/غیرفعال شود.\n"
            f"• دکمهٔ 🗑 آن را حذف می‌کند.\n\n"
            f"ℹ️ کار ارسالی کاربران خودکار توسط AI داوری می‌شود."
        ), ai_admin_missions_kb(ms))
        return True

    if d == "aim_a_mission_add":
        ctx.user_data["state"] = "wait_aima_mission"
        await _edit(q, (
            "➕ تعریف مأموریت جدید\n━━━━━━━━━━━━━━━━\n\n"
            "اطلاعات را در ۴ خط جداگانه بفرستید:\n\n"
            "خط ۱: عنوان\n"
            "خط ۲: توضیحات کامل\n"
            "خط ۳: پاداش اعتباری (عدد)\n"
            "خط ۴: مهارت‌های لازم (با کاما)\n\n"
            "مثال:\n"
            "ساخت صفحهٔ لاگین\n"
            "یک صفحهٔ لاگین با اعتبارسنجی بساز و لینک بده\n"
            "500\n"
            "HTML, CSS, JavaScript"
        ), ai_admin_back_kb("aim_a_missions"))
        return True

    if d.startswith("aim_a_mission_tog|"):
        ai_db.toggle_real_mission(d.split("|", 1)[1])
        await safe_answer(q, "✅ وضعیت تغییر کرد.", True)
        await _edit(q, "📝 مدیریت مأموریت‌های واقعی",
                    ai_admin_missions_kb(ai_db.list_real_missions()))
        return True

    if d.startswith("aim_a_mission_del|"):
        ai_db.delete_real_mission(d.split("|", 1)[1])
        await safe_answer(q, "🗑 حذف شد.", True)
        await _edit(q, "📝 مدیریت مأموریت‌های واقعی",
                    ai_admin_missions_kb(ai_db.list_real_missions()))
        return True

    if d == "aim_noop":
        await safe_answer(q)
        return True

    # ---- مانیتورینگ ----
    if d == "aim_a_monitor":
        u = ai_db.usage_summary(10)
        st = ai_db.module_stats()
        lines = ["👥 مانیتورینگ کاربران", "━━━━━━━━━━━━━━━━", "",
                 f"📞 کل فراخوانی‌ها: {u['total_calls']}",
                 f"💰 کل اعتبار مصرفی: {u['total_credits']}",
                 f"▶️ مسیرهای فعال: {st['paths_active']}", ""]
        if u["top_users"]:
            lines.append("🏆 پرمصرف‌ترین کاربران:")
            for x in u["top_users"][:7]:
                lines.append(f"  • {x['user_id']} — {x['calls']} بار / {x['credits']} اعتبار")
        else:
            lines.append("هنوز مصرفی ثبت نشده است.")
        await _edit(q, "\n".join(lines), ai_admin_back_kb())
        return True

    # ---- گزارش هزینه ----
    if d == "aim_a_reports":
        u = ai_db.usage_summary(10)
        lines = ["📊 گزارش هزینهٔ API", "━━━━━━━━━━━━━━━━", "",
                 f"📞 کل فراخوانی‌ها: {u['total_calls']}",
                 f"💰 کل اعتبار دریافتی: {u['total_credits']}", ""]
        if u["by_action"]:
            lines.append("📋 تفکیک بر اساس نوع:")
            for x in u["by_action"]:
                lines.append(f"  • {x['action'] or '—'}: {x['calls']} بار / {x['credits']} اعتبار")
        else:
            lines.append("داده‌ای ثبت نشده است.")
        lines += ["", "ℹ️ فقط ۵۰۰ رکورد آخر نگهداری می‌شود."]
        await _edit(q, "\n".join(lines), ai_admin_back_kb())
        return True

    return False


# ========================= اعلان به کاربر =========================

async def _notify_user_purchase(pur: dict, approved: bool, note: str = "") -> bool:
    """اطلاع نتیجهٔ فیش به کاربر — از ربات همان پلتفرمی که فیش را فرستاده.

    خروجی: True اگر پیام رفت. خطا هرگز باعث توقف عملیات ادمین نمی‌شود.
    """
    try:
        from config import get_platform_bot
        plat = (pur.get("platform") or "bale").strip() or "bale"
        chat = pur.get("chat_id") or pur.get("user_id")
        bot = get_platform_bot(plat)
        if not bot or not chat:
            return False
        if approved:
            text = (
                "✅ فیش شما تأیید شد!\n━━━━━━━━━━━━━━━━\n\n"
                f"💎 {fa_digits(pur['amount'])} اعتبار به حساب شما اضافه شد.\n\n"
                "می‌توانید از «🤖 یار هوشمند شغلی» استفاده کنید."
            )
        else:
            text = (
                "❌ فیش شما تأیید نشد.\n━━━━━━━━━━━━━━━━\n\n"
                f"💎 بسته: {fa_digits(pur['amount'])} اعتبار\n"
            )
            if note and note != "-":
                text += f"\n📝 دلیل: {note}\n"
            text += "\nدر صورت نیاز با پشتیبانی تماس بگیرید."
        await bot.send_message(chat, text)
        return True
    except Exception as e:
        logger.warning(f"اعلان نتیجهٔ فیش ناموفق: {e}")
        return False


# ========================= stateهای ادمین =========================

async def handle_aim_admin_state(state: str, text: str, msg, ctx, user) -> bool:
    if state not in AIMA_STATES:
        return False
    if not is_admin(user):
        return False

    text = (text or "").strip()

    if state == "wait_aima_value":
        key = ctx.user_data.pop("aima_key", "")
        ctx.user_data.pop("state", None)
        if not key:
            await msg.reply_text("❌ کلید تنظیم مشخص نیست.")
            return True

        if key in _NUMERIC:
            digits = "".join(ch for ch in text.translate(
                str.maketrans("۰۱۲۳۴۵۶۷۸۹", "0123456789")) if ch.isdigit())
            if not digits:
                await msg.reply_text("❌ لطفاً فقط عدد بفرستید.")
                return True
            value = str(int(digits))
        else:
            value = "" if text == "-" else text

        ai_db.save_ai_setting(key, value)
        await msg.reply_text(
            f"✅ {_LABELS.get(key, key)} به‌روزرسانی شد.\n\nمقدار جدید: {value or '(خالی)'}",
            reply_markup=mkb([back_btn("aim_a_menu")]),
        )
        return True

    if state == "wait_aima_trend":
        ctx.user_data.pop("state", None)
        parts = [p.strip() for p in text.split("|")]
        name = parts[0] if parts else ""
        if not name:
            await msg.reply_text("❌ نام مهارت خالی است.")
            return True
        cnt = 0
        if len(parts) > 1:
            digits = "".join(ch for ch in parts[1].translate(
                str.maketrans("۰۱۲۳۴۵۶۷۸۹", "0123456789")) if ch.isdigit())
            cnt = int(digits) if digits else 0
        ai_db.save_market_trend(name, cnt, "admin", "")
        await msg.reply_text(
            f"✅ «{name}» با {cnt} آگهی ثبت شد.",
            reply_markup=mkb([back_btn("aim_a_trends")]),
        )
        return True

    if state == "wait_aima_pack":
        ctx.user_data.pop("state", None)
        parts = [p.strip() for p in text.split("|")]
        if len(parts) < 2:
            await msg.reply_text(
                "❌ قالب نادرست است.\n\nنمونهٔ درست:\n5000 | 200000",
                reply_markup=mkb([back_btn("aim_a_packs")]),
            )
            return True

        def _num(s):
            digits = "".join(ch for ch in s.translate(
                str.maketrans("۰۱۲۳۴۵۶۷۸۹", "0123456789")) if ch.isdigit())
            return int(digits) if digits else 0

        amount, price = _num(parts[0]), _num(parts[1])
        if amount <= 0:
            await msg.reply_text("❌ مقدار اعتبار باید بزرگ‌تر از صفر باشد.",
                                 reply_markup=mkb([back_btn("aim_a_packs")]))
            return True

        pid = ai_db.add_credit_package(amount, price)
        if not pid:
            await msg.reply_text("❌ ثبت بسته ناموفق بود.",
                                 reply_markup=mkb([back_btn("aim_a_packs")]))
            return True

        await msg.reply_text(
            f"✅ بستهٔ جدید ثبت شد.\n\n"
            f"💎 {fa_digits(amount)} اعتبار\n"
            f"💵 {price_label(price)}",
            reply_markup=mkb([back_btn("aim_a_packs")]),
        )
        return True

    # ---- فاز ۲: ویرایش مسیریابی مدل ----
    if state == "wait_aima_route":
        act = ctx.user_data.pop("aima_route_act", "")
        field = ctx.user_data.pop("aima_route_field", "")
        ctx.user_data.pop("state", None)
        if not act or not field:
            await msg.reply_text("❌ اطلاعات ویرایش مشخص نیست.")
            return True

        back = mkb([back_btn(f"aim_a_route_view|{act}")])
        if field == "primary":
            if ":" not in text:
                await msg.reply_text(
                    "❌ قالب نادرست.\nباید «نام‌پروایدر:نام‌مدل» باشد.\n"
                    "مثال: Groq:llama-3.1-8b-instant", reply_markup=back)
                return True
            ai_db.update_model_routing(act, primary_model=text[:150])
            out = f"✅ مدل اصلی ثبت شد:\n{text[:150]}"
        elif field == "fallback":
            fbs = [] if text == "-" else [
                x.strip()[:150] for x in text.split(",") if x.strip()
            ]
            bad = [x for x in fbs if ":" not in x]
            if bad:
                await msg.reply_text(
                    f"❌ این موارد قالب «پروایدر:مدل» ندارند:\n{', '.join(bad)}",
                    reply_markup=back)
                return True
            ai_db.update_model_routing(act, fallback_models=fbs)
            out = f"✅ {len(fbs)} مدل جایگزین ثبت شد."
        else:  # cost
            try:
                cost = float(text.translate(
                    str.maketrans("۰۱۲۳۴۵۶۷۸۹", "0123456789")).strip())
                if cost < 0:
                    raise ValueError
            except Exception:
                await msg.reply_text("❌ عدد معتبر بفرستید. مثال: 0.0008",
                                     reply_markup=back)
                return True
            ai_db.update_model_routing(act, cost_per_request=cost)
            out = f"✅ هزینهٔ تقریبی ثبت شد: ${cost:.4f}"

        await msg.reply_text(out, reply_markup=back)
        return True

    # ---- فاز ۴: تعریف مأموریت واقعی ----
    if state == "wait_aima_mission":
        ctx.user_data.pop("state", None)
        parts = [x.strip() for x in text.split("\n") if x.strip()]
        back = mkb([back_btn("aim_a_missions")])
        if len(parts) < 3:
            await msg.reply_text(
                "❌ حداقل ۳ خط لازم است: عنوان، توضیحات، پاداش.",
                reply_markup=back)
            return True
        title, desc = parts[0], parts[1]
        digits = "".join(ch for ch in parts[2].translate(
            str.maketrans("۰۱۲۳۴۵۶۷۸۹", "0123456789")) if ch.isdigit())
        if not digits:
            await msg.reply_text("❌ پاداش باید عدد باشد (خط سوم).",
                                 reply_markup=back)
            return True
        reward = int(digits)
        skills = ([s.strip() for s in parts[3].split(",") if s.strip()]
                  if len(parts) > 3 else [])
        mid = ai_db.add_real_mission(title, desc, reward, skills, user.id)
        if not mid:
            await msg.reply_text("❌ ثبت مأموریت ناموفق بود.", reply_markup=back)
            return True
        await msg.reply_text(
            f"✅ مأموریت ثبت شد.\n\n"
            f"💼 {title}\n"
            f"🎁 پاداش: {fa_digits(reward)} اعتبار\n"
            f"🧩 مهارت‌ها: {', '.join(skills) or '—'}",
            reply_markup=back)
        return True

    # ---- فاز ۴: ثبت اطلاعات پرداخت ----
    if state == "wait_aima_pay":
        key = ctx.user_data.pop("aima_pay_key", "")
        ctx.user_data.pop("state", None)
        if key not in _PAY_LABELS:
            await msg.reply_text("❌ فیلد مشخص نیست.")
            return True
        value = "" if text == "-" else text[:120]
        if key == "card_number" and value:
            # فقط رقم نگه داشته می‌شود (فاصله و خط تیره حذف)
            value = "".join(ch for ch in value.translate(
                str.maketrans("۰۱۲۳۴۵۶۷۸۹", "0123456789")) if ch.isdigit())
            if len(value) < 16:
                await msg.reply_text(
                    "❌ شمارهٔ کارت باید ۱۶ رقم باشد.",
                    reply_markup=mkb([back_btn("aim_a_payment_info")]),
                )
                return True
        ai_db.save_admin_payment_info(**{key: value})
        await msg.reply_text(
            f"✅ {_PAY_LABELS[key]} ثبت شد.\n\nمقدار: {value or '(خالی)'}",
            reply_markup=mkb([back_btn("aim_a_payment_info")]),
        )
        return True

    # ---- فاز ۴: رد کردن فیش ----
    if state == "wait_aima_reject":
        pid = ctx.user_data.pop("aima_pur_id", "")
        ctx.user_data.pop("state", None)
        pur = ai_db.get_purchase(pid) if pid else None
        if not pur:
            await msg.reply_text("❌ فیش پیدا نشد.")
            return True
        note = "" if text == "-" else text[:200]
        if not ai_db.reject_purchase(pid, note):
            await msg.reply_text("⚠️ این فیش قبلاً بررسی شده است.",
                                 reply_markup=mkb([back_btn("aim_a_pending_purchases")]))
            return True
        sent = await _notify_user_purchase(pur, approved=False, note=note)
        await msg.reply_text(
            f"❌ فیش #{pid} رد شد.\n"
            f"{'📨 به کاربر اطلاع داده شد.' if sent else '⚠️ ارسال پیام به کاربر ناموفق بود.'}",
            reply_markup=mkb([back_btn("aim_a_pending_purchases")]),
        )
        return True

    return False
