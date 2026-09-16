"""
ai_handlers.py — هندلرهای کاربرِ «یار هوشمند شغلی».

معماری: این پروژه با python-telegram-bot کار می‌کند و یک dispatcher مرکزی
(handlers.button_handler) دارد؛ خبری از aiogram Router نیست. بنابراین این
ماژول دو تابع ساده در اختیار handlers.py می‌گذارد:
    handle_aim_callback(d, q, ctx, user) -> bool
    handle_aim_state(state, text, msg, ctx, user) -> bool
خروجی True یعنی «این رویداد را من پردازش کردم».

━━━ فلوی «شروع مسیر جدید» — معماری چندعاملی ━━━
    aim_start
      └─ ایجنت ۱ (CareerInterviewAgent) → state: wait_aim_interview
           ├─ questioning : ۶ تا ۸ سؤال مکالمه‌ای، یکی‌یکی
           ├─ suggestion  : معرفی ۳ مسیر بازار  → aim_pick_path|N
           ├─ report      : گزارش کامل مسیر     → aim_confirm_path
           └─ done        : خروجی JSON نهایی
      └─ ایجنت ۲ (RoadmapBuilderAgent) → اسکلت نقشه راه، بدون محتوا
      └─ ایجنت ۳ (LearningMentorAgent) → محتوای هر گام در لحظهٔ باز شدن
           (aim_step|) و داوری تمرین (state: wait_aim_exercise_answer)

پیشوند callback: aim_    |    پیشوند state: wait_aim_
وابستگی: config، core، ui، ai_* — هرگز از handlers.py import نمی‌کند.
"""
import asyncio
import logging
import os

from config import AI_MENTOR_ENABLED
from ui import btn, mkb, back_btn, home_btn, safe_answer

from . import ai_core, ai_db, ai_market
from .agents import (CareerInterviewAgent, LearningMentorAgent,
                     RoadmapBuilderAgent)
from .agents.career_interview import MAX_QUESTIONS
from .core import UserJourneyContext
from .ai_ui import (
    ai_buy_hint_kb, ai_certs_kb, ai_challenge_kb, ai_help_kb,
    ai_interview_start_kb, ai_learn_kb, ai_main_user_kb, ai_pack_confirm_kb,
    ai_path_progress_kb, ai_pricing_info_kb, ai_pricing_kb,
    ai_edit_profile_kb, ai_mission_detail_kb, ai_missions_kb,
    ai_path_manage_kb, ai_paths_kb, ai_profile_kb, ai_public_profile_kb,
    ai_report_path_kb, ai_reports_kb, ai_settings_kb, ai_sim_answer_kb,
    ai_team_kb, ai_trends_kb, ai_twin_kb, fa_digits, price_label,
    pricing_info_text, progress_text, spark,
)

logger = logging.getLogger(__name__)

# stateهای این ماژول — پیشوند wait_aim_ تا با wait_ai_ پنل ادمین قاطی نشود
AIM_STATES = (
    # فاز ۱ — اطلاعات اولیه (onboarding)
    "wait_aim_profile_name",      # نام و نام خانوادگی
    "wait_aim_profile_age",       # سن
    "wait_aim_profile_city",      # شهر
    # ── معماری چندعاملی ──
    "wait_aim_interview",         # گفتگو با ایجنت ۱ (مصاحبه‌گر)
    "wait_aim_exercise_answer",   # پاسخ تمرین → داوری ایجنت ۳
    # ── بقیهٔ قابلیت‌ها (دست‌نخورده) ──
    "wait_aim_chat",              # پیام چت با منتور
    "wait_aim_help",              # کمک آگاه‌از‌زمینه در یک گام
    "wait_aim_fiche",             # فیش پرداخت (عکس یا متن)
    "wait_aim_sim_job",           # شغل دلخواه برای شبیه‌ساز مصاحبه
    "wait_aim_sim_answer",        # پاسخ به سؤال شبیه‌ساز مصاحبه
    "wait_aim_mission_submission",  # ارسال کار مأموریت واقعی
    "wait_aim_pub_bio",           # معرفی کوتاه پروفایل عمومی
    "wait_aim_edit_profile",      # ویرایش نام/سن/شهر
)

# stateهایی که ورودی تصویری می‌پذیرند (برای مسیریابی در handle_media)
AIM_MEDIA_STATES = ("wait_aim_fiche",)

# ═════════ ایجنت‌های معماری چندعاملی ═════════
# بدون حالت داخلیِ وابسته به کاربر ساخته می‌شوند؛ همهٔ وضعیت در
# UserJourneyContext است، پس یک نمونه برای همهٔ کاربران کافی است.
_AGENT1 = CareerInterviewAgent()   # مصاحبه‌گر شغلی
_AGENT2 = RoadmapBuilderAgent()    # معمار نقشه راه
_AGENT3 = LearningMentorAgent()    # منتور آموزشی

# پیام‌های وضعیت هنگام ساخت اسکلت نقشه راه (ایجنت ۲)
_BUILD_STEPS = (
    "🧠 در حال جمع‌بندی گفتگو…",
    "🗺 معمار نقشه راه در حال طراحی گام‌هاست…",
    "✨ در حال نهایی‌سازی…",
)

_WAIT = "⏳ در حال پردازش با هوش مصنوعی… چند لحظه صبر کنید."


def _clear(ctx):
    for k in ("state", "aim_draft", "aim_step_id", "aim_journey"):
        ctx.user_data.pop(k, None)


# ═════════ زمینهٔ سفر کاربر (UserJourneyContext) ═════════

def _journey(ctx, user) -> UserJourneyContext:
    """زمینهٔ سفر کاربر از حافظهٔ نشست، یا ساخت تازه.

    در حافظه نگه داشته می‌شود تا مصاحبهٔ چندنوبتی بدون رفت‌وبرگشت
    اضافی به دیتابیس پیش برود؛ در پایان (مرحلهٔ done) در career_paths
    ذخیره می‌گردد.
    """
    data = ctx.user_data.get("aim_journey")
    if isinstance(data, dict):
        return UserJourneyContext.from_dict(user.id, data)
    return UserJourneyContext(user.id)


def _save_journey(ctx, journey: UserJourneyContext) -> None:
    """ذخیرهٔ زمینه در حافظهٔ نشست (بین نوبت‌های گفتگو)."""
    ctx.user_data["aim_journey"] = journey.to_dict()


def _journey_from_path(path: dict) -> UserJourneyContext:
    """بازسازی زمینه از مسیر ذخیره‌شده در دیتابیس."""
    return UserJourneyContext.from_path(path)


def _draft(ctx) -> dict:
    return ctx.user_data.setdefault("aim_draft", {})


def _fa_int(text: str) -> int:
    """استخراج عدد از متن فارسی یا انگلیسی (۲۵ → 25). اگر نبود صفر."""
    digits = "".join(
        ch for ch in (text or "").translate(
            str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")
        ) if ch.isdigit()
    )
    try:
        return int(digits) if digits else 0
    except Exception:
        return 0


# فاز ۳ — مراحل نمایش «در حال تحلیل» هنگام ساخت نقشه راه
_ANALYZE_STEPS = (
    "⏳ در حال تحلیل پاسخ‌های شما…",
    "🔍 در حال بررسی دوره‌های موجود…",
    "🗺 در حال ساخت نقشه راه…",
)


async def _animate(message, steps=_ANALYZE_STEPS, delay: float = 1.1):
    """نمایش متوالی پیام‌های وضعیت روی همان پیام.

    اگر ویرایش پیام ناموفق بود (مثلاً محدودیت پلتفرم)، بی‌صدا رد می‌شود
    تا فلوی اصلی متوقف نشود.
    """
    for s in steps[1:]:
        try:
            await asyncio.sleep(delay)
            await message.edit_text(s)
        except Exception:
            break


async def _edit(q, text, kb):
    """ویرایش امن پیام (اگر متن عوض نشده باشد خطا نمی‌دهد)."""
    try:
        await q.edit_message_text(text, reply_markup=kb)
    except Exception as e:
        if "not modified" not in str(e).lower():
            logger.debug(f"edit failed: {e}")


def module_enabled() -> bool:
    """آیا ماژول «یار هوشمند شغلی» در دسترس است؟

    دو لایه:
      ۱. config.AI_MENTOR_ENABLED — کلید اصلی (پیش‌فرض True).
         اگر False باشد، ماژول برای همه خاموش است.
      ۲. تنظیم «enabled» در دیتابیس — دکمهٔ پنل ادمین.
         پیش‌فرض روشن؛ فقط اگر ادمین صراحتاً «0» ذخیره کرده باشد خاموش می‌شود.
    """
    if not AI_MENTOR_ENABLED:
        return False
    return str(ai_db.get_ai_setting("enabled", "1")).strip() != "0"


# ========================= صفحه‌ها =========================

async def show_main(q, user):
    path = ai_db.get_active_path(user.id)
    bal = ai_core.get_user_ai_balance(user.id)
    free = ai_core.free_quota_left(user.id)

    lines = ["🤖 یار هوشمند شغلی", "━━━━━━━━━━━━━━━━", ""]
    if path:
        done, total = ai_db.path_progress(path["id"])
        lines.append(f"🎯 مسیر فعال: {path.get('target_job', '—')}")
        lines.append(f"📊 پیشرفت: {done} از {total} گام")
    else:
        lines.append("هنوز مسیری نساخته‌اید. با «شروع مسیر جدید» آغاز کنید.")
    lines += ["", f"💰 اعتبار شما: {bal}"]
    if free > 0:
        lines.append(f"🎁 تعامل رایگان باقی‌مانده: {free}")

    # فاز ۴ — یادآوری فیش در انتظار تأیید
    pend = ai_db.user_pending_purchases(user.id)
    if pend:
        lines += ["", f"⏳ شما {fa_digits(pend)} فیش در انتظار تأیید دارید."]

    await _edit(q, "\n".join(lines), ai_main_user_kb(bool(path)))


async def show_progress(q, user):
    path = ai_db.get_active_path(user.id)
    if not path:
        await _edit(q, "هنوز مسیر فعالی ندارید.\nبا «🚀 شروع مسیر جدید» شروع کنید.",
                    ai_main_user_kb(False))
        return
    steps = ai_db.get_path_steps(path["id"])
    done, total = ai_db.path_progress(path["id"])
    await _edit(q, progress_text(path, done, total), ai_path_progress_kb(steps))


def _has_content(c) -> bool:
    """آیا محتوای این گام قبلاً تولید شده است؟"""
    return bool(isinstance(c, dict)
                and ((c.get("description") or "").strip()
                     or (c.get("challenge") or "").strip()))


async def show_step(q, step_id, user=None):
    """نمایش یک گام — با Lazy Loading محتوا توسط ایجنت ۳.

    اگر content خالی باشد، LearningMentorAgent در همین لحظه محتوا را
    می‌سازد و در دیتابیس ذخیره می‌کند. دفعهٔ بعد محتوا از دیتابیس خوانده
    می‌شود و هیچ فراخوانی AI انجام نمی‌گیرد (بدون هزینه).
    """
    # 🔒 بررسی مالکیت — گام فقط برای صاحبش قابل مشاهده است
    step = (ai_db.get_owned_step(step_id, user.id) if user is not None
            else ai_db.get_step(step_id))
    if not step:
        await safe_answer(q, "❌ این گام پیدا نشد.", True)
        return

    c = step.get("content") or {}

    # ⚡ Lazy Loading — ایجنت ۳ فقط بار اول صدا زده می‌شود
    if not _has_content(c) and step["step_type"] in ("lesson", "ai_challenge",
                                                     "resource"):
        await _edit(q, "📝 منتور در حال آماده‌سازی این درس برای شماست…", None)
        res = await generate_step_content(step)
        if res.get("ok"):
            c = res["content"]
            step = ai_db.get_step(step_id) or step
        else:
            logger.info(f"تولید محتوای گام ناموفق: {res.get('error')}")
            c = c or {}
            c.setdefault("description",
                         "⚠️ تولید محتوا در این لحظه ممکن نشد. "
                         "کمی بعد دوباره تلاش کنید.")

    icon = {"course": "📚", "ai_challenge": "🧩",
            "lesson": "📝", "resource": "📖"}.get(step["step_type"], "•")
    txt = [f"{icon} گام {step['step_number']}: {step['title']}", ""]
    if c.get("objective"):
        txt += [f"🎯 هدف: {c['objective']}", ""]
    if c.get("description"):
        txt += [c["description"], ""]
    if c.get("challenge"):
        txt += ["✍️ تمرین شما:", c["challenge"], ""]
    if c.get("expected_output"):
        txt += [f"📤 خروجی موردانتظار: {c['expected_output']}", ""]
    if c.get("tools_needed"):
        txt.append("🛠 ابزارها: " + "، ".join(c["tools_needed"][:4]))
    if c.get("ai_tools"):
        txt.append("🤖 ابزارهای AI کمکی: " + "، ".join(c["ai_tools"][:3]))
    if c.get("estimated_minutes"):
        txt.append(f"⏱ زمان تخمینی: {fa_digits(c['estimated_minutes'])} دقیقه")
    elif c.get("estimated_days"):
        txt.append(f"⏱ زمان تخمینی: {c['estimated_days']} روز")

    fb = step.get("ai_feedback") or {}
    if fb.get("feedback"):
        txt += ["", f"💬 بازخورد قبلی: {fb['feedback']}"]

    await _edit(q, "\n".join(txt),
                ai_challenge_kb(step["id"], step["step_type"],
                                c.get("course_id", ""),
                                bool((c.get("challenge") or "").strip())))


async def generate_step_content(step: dict) -> dict:
    """فراخوانی ایجنت ۳ برای ساخت محتوای یک گام و ذخیرهٔ آن.

    زمینهٔ سفر از روی مسیر ذخیره‌شده بازسازی می‌شود تا منتور پروفایل
    کاربر، کل نقشه راه و نقاط قوت/ضعف او را بداند.
    """
    path = ai_db.get_path(step.get("path_id"))
    if not path:
        return {"ok": False, "error": "مسیر پیدا نشد."}

    journey = _journey_from_path(path)
    journey.current_step = int(step.get("step_number") or 1)

    # اگر نقشه راه در زمینه نبود (مسیرهای قدیمی)، از خود گام‌ها بساز
    if not journey.roadmap:
        journey.roadmap = [{
            "step_number": s["step_number"],
            "title": s["title"],
            "objective": (s.get("content") or {}).get("objective", ""),
            "exercise": (s.get("content") or {}).get("challenge", ""),
            "estimated_hours": 0,
            "difficulty": "medium",
        } for s in ai_db.get_path_steps(path["id"])]

    res = await _AGENT3.run(journey, step_number=step["step_number"],
                            task="teach")
    if not res.get("ok"):
        return res

    content = dict(res["content"])
    # course_id گام (اگر به دورهٔ ربات وصل است) حفظ می‌شود
    content.setdefault("course_id", (step.get("content") or {}).get("course_id", ""))
    ai_db.update_step_content(step["id"], content)
    return {"ok": True, "content": content}


async def show_trends(q, refresh=False, view="list"):
    """ترندهای تعاملی (فاز ۲) — سه نما + دکمهٔ افزودن به مسیر."""
    if refresh:
        await _edit(q, _WAIT, None)
        await ai_market.update_market_trends_db(use_ai=True)
    else:
        ai_market.ensure_seeded()

    trends = ai_db.get_trending_skills(8)
    if not trends:
        await _edit(q, "فعلاً داده‌ای ثبت نشده است.", ai_trends_kb([], view))
        return

    lines = ["🔥 مهارت‌های پرتقاضای بازار", "━━━━━━━━━━━━━━━━", ""]
    for i, t in enumerate(trends, 1):
        name, cnt = t["skill_name"], fa_digits(t["demand_count"])
        if view == "growth":
            g = ai_db.get_trend_growth(name)
            if g["ok"]:
                arrow = "📈" if g["change"] > 0 else ("📉" if g["change"] < 0 else "➖")
                lines.append(f"{i}. {name} — {cnt} آگهی")
                lines.append(f"   {arrow} {g['percent']}٪  {spark(g['points'])}")
            else:
                lines.append(f"{i}. {name} — {cnt} آگهی")
                lines.append("   ⏳ تاریخچهٔ کافی برای نمودار ثبت نشده")
        elif view == "full":
            lines.append(f"{i}. {name}")
            lines.append(f"   📊 تقاضا: {cnt} آگهی")
            if t.get("reason"):
                lines.append(f"   💡 {t['reason']}")
            if t.get("source"):
                lines.append(f"   🔗 منبع: {t['source']}")
            g = ai_db.get_trend_growth(name)
            if g["ok"]:
                lines.append(f"   📈 رشد: {g['percent']}٪")
            lines.append("")
        else:  # list
            lines.append(f"{i}. {name} — {cnt} آگهی")
            if t.get("reason"):
                lines.append(f"   ↳ {t['reason']}")

    await _edit(q, "\n".join(lines), ai_trends_kb(trends, view))


async def show_balance(q, user):
    s = ai_db.all_ai_settings()
    bal = ai_core.get_user_ai_balance(user.id)
    free = ai_core.free_quota_left(user.id)
    await _edit(q, (
        f"💰 موجودی و تعرفه\n━━━━━━━━━━━━━━━━\n\n"
        f"اعتبار شما: {bal}\n"
        f"تعامل رایگان باقی‌مانده: {free}\n\n"
        f"📋 تعرفه‌ها:\n"
        f"🗺 نقشه راه: {s.get('price_roadmap')}\n"
        f"✍️ تصحیح چالش: {s.get('price_challenge')}\n"
        f"📄 گزارش شغلی: {s.get('price_report')}\n"
        f"💬 چت منتور: {s.get('price_chat')}\n"
        f"🔥 ترندها: {s.get('price_trends')}"
    ), ai_settings_kb())


# ========================= callback اصلی =========================

async def handle_aim_callback(d: str, q, ctx, user) -> bool:
    """پردازش callbackهای aim_. خروجی True یعنی پردازش شد."""
    if not d.startswith("aim_"):
        return False

    # گارد خاموش بودن ماژول (ادمین همیشه دسترسی دارد)
    if not module_enabled() and not d.startswith("aim_a_"):
        from core import is_admin
        if not is_admin(user):
            await safe_answer(q, "این بخش موقتاً غیرفعال است.", True)
            return True

    # ---- منوی اصلی ----
    if d == "aim_menu":
        _clear(ctx)
        await show_main(q, user)
        return True

    if d == "aim_locked":
        await safe_answer(q, "🔒 ابتدا گام‌های قبلی را کامل کنید.", True)
        return True

    # ---- شروع مسیر جدید — ایجنت ۱ (مصاحبه‌گر شغلی) ----
    if d == "aim_start":
        # 💰 فقط «بررسی» موجودی؛ کسر واقعی در لحظهٔ ساخت نقشه راه انجام
        # می‌شود. اگر کاربر وسط مصاحبه منصرف شود، اعتبارش نمی‌سوزد.
        can, price, msg = ai_core.can_afford(user.id, "roadmap")
        if not can:
            await _edit(q, msg, ai_buy_hint_kb())
            return True
        ctx.user_data["aim_draft"] = {}
        ctx.user_data.pop("aim_journey", None)

        # فاز ۱ — اگر پروفایل ثبت نشده، اول اطلاعات اولیه گرفته می‌شود
        if not ai_db.has_user_profile(user.id):
            ctx.user_data["state"] = "wait_aim_profile_name"
            await _edit(q, (
                "👤 اطلاعات اولیه\n━━━━━━━━━━━━━━━━\n\n"
                "قبل از ساخت مسیر، چند سؤال کوتاه می‌پرسم تا برنامه را "
                "دقیقاً برای شما شخصی‌سازی کنم.\n\n"
                "۱ از ۳:\n📝 نام و نام خانوادگی‌تان را بنویسید:"
            ), mkb([back_btn("aim_menu")]))
            return True

        return await _begin_interview(q, ctx, user)

    # ---- انتخاب یکی از ۳ مسیر پیشنهادی ایجنت ۱ ----
    if d.startswith("aim_pick_path|"):
        return await _pick_path(q, ctx, user, d.split("|", 1)[1])

    # ---- بازگشت به فهرست مسیرهای پیشنهادی ----
    if d == "aim_paths_again":
        journey = _journey(ctx, user)
        if not journey.suggested_paths:
            await safe_answer(q, "❌ فهرست مسیرها در دسترس نیست.", True)
            return True
        journey.stage = "suggestion"
        _save_journey(ctx, journey)
        await _edit(q, _paths_text(journey.suggested_paths),
                    _paths_kb(journey.suggested_paths))
        return True

    # ---- تأیید مسیر → ایجنت ۲ (معمار نقشه راه) ----
    if d == "aim_confirm_path":
        return await _confirm_and_build(q, ctx, user)

    if d == "aim_continue":
        await show_progress(q, user)
        return True

    if d.startswith("aim_step|"):
        await show_step(q, d.split("|", 1)[1], user)
        return True

    # ---- تکمیل دستی یک گام ----
    if d.startswith("aim_done|"):
        sid = d.split("|", 1)[1]
        step = ai_db.get_owned_step(sid, user.id)   # 🔒 مالکیت
        if not step:
            await safe_answer(q, "❌ گام پیدا نشد.", True)
            return True
        if step["step_type"] == "ai_challenge":
            await safe_answer(q, "این گام چالش دارد؛ باید پاسخ بفرستید.", True)
            return True
        ai_db.update_step_status(sid, "completed")
        await safe_answer(q, "✅ گام تکمیل شد.", True)
        await show_progress(q, user)
        # فاز ۳ — اگر مسیر ۱۰۰٪ شد، گواهینامه صادر می‌شود
        await _maybe_issue_certificate(ctx, user, step["path_id"])
        return True

    # ---- ارسال پاسخ تمرین → داوری ایجنت ۳ ----
    if d.startswith("aim_answer|"):
        sid = d.split("|", 1)[1]
        step = ai_db.get_owned_step(sid, user.id)   # 🔒 مالکیت
        if not step:
            await safe_answer(q, "❌ گام پیدا نشد.", True)
            return True
        ctx.user_data["aim_step_id"] = sid
        ctx.user_data["state"] = "wait_aim_exercise_answer"
        c = step.get("content") or {}
        lines = ["✍️ پاسخ تمرین", "━━━━━━━━━━━━━━━━", ""]
        if c.get("challenge"):
            lines += [c["challenge"], ""]
        if c.get("expected_output"):
            lines += [f"📤 خروجی موردانتظار: {c['expected_output']}", ""]
        lines.append("پاسخ خود را در یک پیام بنویسید:")
        await _edit(q, "\n".join(lines), mkb([back_btn(f"aim_step|{sid}")]))
        return True

    # ---- ترندها (فاز ۲: تعاملی) ----
    if d == "aim_trends":
        await show_trends(q, refresh=False, view="list")
        return True
    if d.startswith("aim_trends|"):
        v = d.split("|", 1)[1]
        await show_trends(q, refresh=False,
                          view=v if v in ("list", "growth", "full") else "list")
        return True
    if d == "aim_trends_refresh":
        await show_trends(q, refresh=True)
        return True

    if d.startswith("aim_add_trend|"):
        skill = d.split("|", 1)[1]
        res = ai_core.add_trend_to_path(user.id, skill)
        if not res.get("ok"):
            await safe_answer(q, f"⚠️ {res.get('error')}", True)
            return True
        note = ("🆕 مسیر جدیدی برای شما ساخته شد."
                if res.get("created") else
                f"به‌عنوان گام {fa_digits(res['step_number'])} اضافه شد.")
        await safe_answer(q, "✅ به مسیر شما اضافه شد.", True)
        await _edit(q, (
            f"✅ «{skill}» به مسیر شما اضافه شد.\n━━━━━━━━━━━━━━━━\n\n{note}"
        ), mkb([[btn("🎯 مشاهدهٔ مسیر", "aim_continue")], back_btn("aim_trends")]))
        return True

    # ---- کمک حین آموزش (فاز ۲) ----
    if d.startswith("aim_chat_help|"):
        sid = d.split("|", 1)[1]
        step = ai_db.get_owned_step(sid, user.id)   # 🔒 مالکیت
        if not step:
            await safe_answer(q, "❌ گام پیدا نشد.", True)
            return True
        # 💰 فقط بررسی؛ کسر در لحظهٔ پاسخ‌دادن AI انجام می‌شود
        can, cost, cmsg = ai_core.can_afford(user.id, "help")
        if not can:
            await _edit(q, cmsg, ai_buy_hint_kb())
            return True
        ctx.user_data["state"] = "wait_aim_help"
        ctx.user_data["aim_help_step"] = sid
        hist = ai_db.get_chat_history(user.id, 0, int(sid), 6)
        lines = [f"💡 کمک در گام {fa_digits(step['step_number'])}",
                 "━━━━━━━━━━━━━━━━", "", f"📌 {step['title']}", ""]
        if hist:
            lines.append("🗨 گفتگوی قبلی:")
            for h in hist[-4:]:
                who = "شما" if h["role"] == "user" else "منتور"
                lines.append(f"  {who}: {h['content'][:110]}")
            lines.append("")
        lines.append("سؤالت را بنویس؛ منتور با توجه به همین گام جواب می‌دهد.")
        await _edit(q, "\n".join(lines), mkb([back_btn(f"aim_step|{sid}")]))
        return True

    if d.startswith("aim_help_clear|"):
        sid = d.split("|", 1)[1]
        if not ai_db.get_owned_step(sid, user.id):   # 🔒 مالکیت
            await safe_answer(q, "❌ گام پیدا نشد.", True)
            return True
        ai_db.clear_chat_history(user.id, int(sid))
        await safe_answer(q, "🧹 تاریخچه پاک شد.", True)
        await show_step(q, sid, user)
        return True

    # ---- یادگیری / چت ----
    if d == "aim_learn":
        await _edit(q, (
            "🤖 یادگیری با هوش مصنوعی\n━━━━━━━━━━━━━━━━\n\n"
            "می‌توانید سؤال‌های شغلی و آموزشی‌تان را از منتور بپرسید "
            "یا مهارت‌های پرتقاضای بازار را ببینید."
        ), ai_learn_kb())
        return True

    if d == "aim_chat":
        # 💰 فقط بررسی؛ کسر در لحظهٔ پاسخ‌دادن AI انجام می‌شود
        can, cost, msg = ai_core.can_afford(user.id, "chat")
        if not can:
            await _edit(q, msg, ai_buy_hint_kb())
            return True
        ctx.user_data["state"] = "wait_aim_chat"
        await _edit(q, "💬 سؤالت را بنویس:", mkb([back_btn("aim_learn")]))
        return True

    # ---- گزارش آمادگی ----
    if d == "aim_report":
        ok, cost, msg = ai_core.check_and_deduct_credits(user.id, "report")
        if not ok:
            await _edit(q, msg, ai_buy_hint_kb())
            return True
        await _edit(q, _WAIT, None)
        res = await ai_core.generate_career_report(user.id)
        if not res.get("ok"):
            back = ai_core.refund(user.id, cost, "report_failed")
            await _edit(q, f"❌ {res.get('error')}\n\n"
                        + ("اعتبار شما بازگردانده شد." if back else ""),
                        mkb([back_btn("aim_continue")]))
            return True
        ai_db.log_ai_usage(user.id, "report", cost, res.get("model", ""))
        lines = [
            "📄 گزارش آمادگی شغلی", "━━━━━━━━━━━━━━━━", "",
            f"📊 آمادگی: {res['readiness_percent']}٪", "",
        ]
        if res.get("strengths"):
            lines += ["💪 نقاط قوت:"] + [f"  • {x}" for x in res["strengths"][:5]] + [""]
        if res.get("weaknesses"):
            lines += ["⚠️ نقاط ضعف:"] + [f"  • {x}" for x in res["weaknesses"][:5]] + [""]
        if res.get("recommendations"):
            lines += ["🎯 پیشنهادها:"] + [f"  {i}. {x}" for i, x in
                                          enumerate(res["recommendations"][:3], 1)]
        if res.get("summary"):
            lines += ["", res["summary"]]
        await _edit(q, "\n".join(lines), mkb([back_btn("aim_continue")]))
        return True

    # ---- پروفایل ----
    if d == "aim_profile":
        await _edit(q, _profile_text(user), ai_profile_kb())
        return True

    # ---- راهنما و تعرفه ----
    if d == "aim_guide_pricing":
        from config import SUPPORT_GROUP
        sup = (SUPPORT_GROUP or "").strip()
        lines = [
            "📋 راهنما و تعرفه", "━━━━━━━━━━━━━━━━", "",
            f"💰 اعتبار فعلی شما: {fa_digits(ai_core.get_user_ai_balance(user.id))}",
        ]
        free = ai_core.free_quota_left(user.id)
        if free:
            lines.append(f"🎁 تعامل رایگان باقی‌مانده: {fa_digits(free)}")
        lines += ["", "🔹 امکانات و هزینهٔ هرکدام:", ""]
        for act, desc in (
            ("roadmap", "🚀 شروع مسیر جدید — مصاحبهٔ هوشمند و ساخت نقشه راه"),
            ("challenge", "🧩 تصحیح چالش — داوری پاسخ شما و دریافت XP"),
            ("help", "💡 کمک در گام — راهنمایی هوشمند وقتی گیر کردید"),
            ("chat", "💬 چت با منتور — پرسش آزاد آموزشی و شغلی"),
            ("report", "📄 گزارش آمادگی — تحلیل نقاط قوت و ضعف شما"),
            ("interview_sim", "🎤 شبیه‌ساز مصاحبه — ۱۰ سؤال واقعی + نمره"),
            ("twin", "👯‍♂️ همزاد شغلی — شبیه‌سازی نتیجهٔ ارسال رزومه"),
            ("trends", "🔥 ترندهای بازار — پرتقاضاترین مهارت‌ها"),
        ):
            price = ai_core.get_action_price(act)
            tag = "رایگان" if price <= 0 else f"{fa_digits(price)} اعتبار"
            lines.append(f"{desc}\n   └ {tag}")
        lines += [
            "", "━━━━━━━━━━━━━━━━",
            "💼 مأموریت‌های واقعی و یادگیری تیمی رایگان‌اند و حتی",
            "   می‌توانند برای شما اعتبار بیاورند.",
        ]
        rows = [[btn("💳 شارژ اعتبار", "aim_buy")]]
        if sup:
            rows.append([btn("📞 پشتیبانی", "support")])
        rows.append(back_btn("aim_menu"))
        await _edit(q, "\n".join(lines), mkb(rows))
        return True

    # ---- ویرایش اطلاعات پروفایل ----
    if d == "aim_edit_profile":
        prof = ai_db.get_user_profile(user.id) or {}
        await _edit(q, (
            "✏️ ویرایش اطلاعات\n━━━━━━━━━━━━━━━━\n\n"
            f"📝 نام: {' '.join(x for x in (prof.get('first_name',''), prof.get('last_name','')) if x) or '—'}\n"
            f"🎂 سن: {fa_digits(prof.get('age', 0)) if prof.get('age') else '—'}\n"
            f"🏙 شهر: {prof.get('city') or '—'}\n\n"
            "کدام مورد را می‌خواهید تغییر دهید؟"
        ), ai_edit_profile_kb())
        return True

    if d.startswith("aim_edit_field|"):
        f = d.split("|", 1)[1]
        if f not in ("name", "age", "city"):
            await safe_answer(q, "❌ نامعتبر.", True)
            return True
        ctx.user_data["state"] = "wait_aim_edit_profile"
        ctx.user_data["aim_edit_field"] = f
        hint = {"name": "نام و نام خانوادگی جدید را بنویسید:",
                "age": "سن خود را بنویسید (عدد بین ۵ تا ۱۰۰):",
                "city": "نام شهر خود را بنویسید:"}[f]
        await _edit(q, f"✏️ ویرایش\n━━━━━━━━━━━━━━━━\n\n{hint}",
                    mkb([back_btn("aim_edit_profile")]))
        return True

    # ---- مدیریت مسیرها ----
    if d == "aim_paths":
        paths = ai_db.list_user_paths(user.id, 10)
        lines = ["🗂 مدیریت مسیرها", "━━━━━━━━━━━━━━━━", ""]
        if paths:
            for p in paths:
                done, total = ai_db.path_progress(p["id"])
                icon = {"active": "▶️", "completed": "✅"}.get(p["status"], "📦")
                lines.append(f"{icon} {p['target_job']} — "
                             f"{fa_digits(done)}/{fa_digits(total)} گام")
        else:
            lines.append("هنوز مسیری نساخته‌اید.")
        await _edit(q, "\n".join(lines), ai_paths_kb(paths))
        return True

    if d.startswith("aim_path_view|"):
        pid = d.split("|", 1)[1]
        p = ai_db.get_path(pid)
        if not p or int(p.get("user_id", 0)) != int(user.id):   # 🔒 مالکیت
            await safe_answer(q, "❌ این مسیر پیدا نشد.", True)
            return True
        done, total = ai_db.path_progress(int(pid))
        st = {"active": "▶️ فعال", "completed": "✅ تکمیل‌شده",
              "archived": "📦 بایگانی"}.get(p["status"], p["status"])
        await _edit(q, (
            f"🎯 {p['target_job']}\n━━━━━━━━━━━━━━━━\n\n"
            f"📌 وضعیت: {st}\n"
            f"📊 پیشرفت: {fa_digits(done)} از {fa_digits(total)} گام\n"
            f"📅 ساخته‌شده: {(p.get('created_at') or '')[:10]}"
        ), ai_path_manage_kb(pid, p["status"]))
        return True

    if d.startswith("aim_path_archive|"):
        pid = d.split("|", 1)[1]
        if ai_db.set_path_status(pid, user.id, "archived"):   # 🔒 داخل تابع
            await safe_answer(q, "📦 مسیر بایگانی شد.", True)
        else:
            await safe_answer(q, "❌ انجام نشد.", True)
        return await handle_aim_callback("aim_paths", q, ctx, user)

    if d.startswith("aim_path_activate|"):
        pid = d.split("|", 1)[1]
        if ai_db.set_path_status(pid, user.id, "active"):
            await safe_answer(q, "♻️ مسیر دوباره فعال شد.", True)
        else:
            await safe_answer(q, "❌ انجام نشد.", True)
        return await handle_aim_callback("aim_paths", q, ctx, user)

    if d.startswith("aim_path_delete|"):
        pid = d.split("|", 1)[1]
        if ai_db.delete_path(pid, user.id):
            await safe_answer(q, "🗑 مسیر حذف شد.", True)
        else:
            await safe_answer(q, "❌ انجام نشد.", True)
        return await handle_aim_callback("aim_paths", q, ctx, user)

    # ---- فاز ۳: گزارش‌های آمادگی شغلی ----
    if d == "aim_reports":
        paths = ai_db.list_user_paths(user.id, 10)
        await _edit(q, (
            "📄 گزارش‌های آمادگی شغلی\n━━━━━━━━━━━━━━━━\n\n"
            f"هزینهٔ تولید هر گزارش: {fa_digits(ai_core.get_action_price('report'))} اعتبار\n\n"
            "مسیر مورد نظر را انتخاب کنید:"
        ), ai_reports_kb(paths))
        return True

    if d.startswith("aim_report_path|"):
        pid = d.split("|", 1)[1]
        path = ai_db.get_path(pid)
        if not path or int(path.get("user_id", 0)) != int(user.id):
            await safe_answer(q, "❌ این مسیر پیدا نشد.", True)
            return True
        prev = ai_db.list_career_reports(user.id, int(pid))
        done, total = ai_db.path_progress(int(pid))
        await _edit(q, (
            f"🎯 {path['target_job']}\n━━━━━━━━━━━━━━━━\n\n"
            f"📊 پیشرفت: {fa_digits(done)} از {fa_digits(total)} گام\n"
            f"📄 گزارش‌های قبلی: {fa_digits(len(prev))}\n\n"
            f"هزینهٔ گزارش جدید: {fa_digits(ai_core.get_action_price('report'))} اعتبار"
        ), ai_report_path_kb(pid, bool(prev)))
        return True

    if d.startswith("aim_report_new|"):
        pid = d.split("|", 1)[1]
        ok, cost, msg = ai_core.check_and_deduct_credits(user.id, "report")
        if not ok:
            await _edit(q, msg, ai_buy_hint_kb())
            return True
        await _edit(q, _WAIT, None)
        res = await ai_core.generate_career_readiness_report(user.id, int(pid))
        if not res.get("ok"):
            back = ai_core.refund(user.id, cost, "report_failed")
            await _edit(q, f"❌ {res.get('error')}\n\n"
                        + ("اعتبار شما بازگردانده شد." if back else ""),
                        mkb([back_btn("aim_reports")]))
            return True
        await _edit(q, _report_text(res), mkb([
            [btn("📚 گزارش‌های این مسیر", f"aim_report_list|{pid}")],
            back_btn("aim_reports"),
        ]))
        return True

    if d.startswith("aim_report_list|"):
        pid = d.split("|", 1)[1]
        reps = ai_db.list_career_reports(user.id, int(pid))
        if not reps:
            await safe_answer(q, "گزارشی ثبت نشده است.", True)
            return True
        rows = [[btn(f"📄 {r['created_at'][:10]} — {fa_digits(r['readiness_percent'])}٪",
                     f"aim_report_view|{r['id']}")] for r in reps[:10]]
        rows.append(back_btn(f"aim_report_path|{pid}"))
        await _edit(q, "📚 گزارش‌های این مسیر\n\nیکی را انتخاب کنید:", mkb(rows))
        return True

    if d.startswith("aim_report_view|"):
        rep = ai_db.get_career_report(d.split("|", 1)[1])
        if not rep or int(rep.get("user_id", 0)) != int(user.id):
            await safe_answer(q, "❌ گزارش پیدا نشد.", True)
            return True
        await _edit(q, _report_text(rep["report_json"], rep.get("created_at", "")),
                    mkb([back_btn(f"aim_report_list|{rep['path_id']}")]))
        return True

    # ---- فاز ۳: گواهینامه‌ها ----
    if d == "aim_certs":
        certs = ai_db.list_certificates(user.id)
        await _edit(q, (
            "🎓 گواهینامه‌های من\n━━━━━━━━━━━━━━━━\n\n"
            + (f"تعداد: {fa_digits(len(certs))}\n\nبرای دریافت فایل، روی هر مورد بزنید."
               if certs else
               "پس از تکمیل ۱۰۰٪ یک مسیر، گواهینامه به‌صورت خودکار صادر می‌شود.")
        ), ai_certs_kb(certs))
        return True

    if d.startswith("aim_cert_get|"):
        cert = ai_db.get_certificate(d.split("|", 1)[1])
        if not cert or int(cert.get("user_id", 0)) != int(user.id):
            await safe_answer(q, "❌ گواهینامه پیدا نشد.", True)
            return True
        await safe_answer(q, "📤 در حال ارسال…")
        sent = await _send_certificate(ctx, q.message.chat_id, cert)
        if not sent:
            # فایل حذف شده — دوباره ساخته می‌شود
            res = ai_core.issue_certificate(user.id, cert["path_id"],
                                            cert.get("readiness", 0))
            if res.get("ok"):
                cert["file_path"] = res["file_path"]
                sent = await _send_certificate(ctx, q.message.chat_id, cert)
        if not sent:
            await safe_answer(q, "❌ ارسال فایل ناموفق بود.", True)
        return True

    # ---- فاز ۳: همزاد شغلی ----
    if d in ("aim_career_twin", "aim_career_twin_run"):
        prev = ai_db.latest_career_twin(user.id)
        if d == "aim_career_twin" and prev:
            await _edit(q, _twin_text(prev["result_json"], prev.get("created_at", "")),
                        ai_twin_kb())
            return True
        ok, cost, msg = ai_core.check_and_deduct_credits(user.id, "twin")
        if not ok:
            await _edit(q, msg, ai_buy_hint_kb())
            return True
        await _edit(q, "🔮 در حال شبیه‌سازی بازار کار…", None)
        res = await ai_core.simulate_career_twin(user.id)
        if not res.get("ok"):
            back = ai_core.refund(user.id, cost, "twin_failed")
            await _edit(q, f"❌ {res.get('error')}\n\n"
                        + ("اعتبار شما بازگردانده شد." if back else ""),
                        mkb([back_btn("aim_profile")]))
            return True
        await _edit(q, _twin_text(res), ai_twin_kb())
        return True

    if d == "aim_history":
        paths = ai_db.list_user_paths(user.id, 10)
        lines = ["🗂 مسیرهای قبلی", "━━━━━━━━━━━━━━━━", ""]
        if paths:
            for p in paths:
                done, total = ai_db.path_progress(p["id"])
                lines.append(f"• {p['target_job']} ({p['status']}) — {done}/{total}")
        else:
            lines.append("موردی ثبت نشده است.")
        await _edit(q, "\n".join(lines), mkb([back_btn("aim_settings")]))
        return True

    # ---- فاز ۳: شبیه‌ساز مصاحبه ----
    if d == "aim_interview_sim":
        paths = ai_db.list_user_paths(user.id, 6)
        active = [s for s in ai_db.list_simulations(user.id, 3)
                  if s.get("status") == "active"]
        await _edit(q, (
            "🎤 شبیه‌ساز مصاحبه شغلی\n━━━━━━━━━━━━━━━━\n\n"
            "۱۰ سؤال واقعی (۷ تخصصی + ۳ رفتاری) از شما پرسیده می‌شود.\n"
            "در پایان، نمره و نقاط قوت و ضعف‌تان را می‌گیرید.\n\n"
            f"💵 هزینه: {fa_digits(ai_core.get_action_price('interview_sim'))} اعتبار\n\n"
            "شغل هدف را انتخاب کنید:"
        ), ai_interview_start_kb(paths, bool(active)))
        return True

    if d == "aim_sim_custom":
        ctx.user_data["state"] = "wait_aim_sim_job"
        await _edit(q, (
            "✍️ شغل هدف مصاحبه\n━━━━━━━━━━━━━━━━\n\n"
            "عنوان شغلی که می‌خواهید برایش تمرین کنید را بنویسید:\n\n"
            "مثال: توسعه‌دهندهٔ فرانت‌اند React"
        ), mkb([back_btn("aim_interview_sim")]))
        return True

    if d.startswith("aim_sim_go|"):
        path = ai_db.get_path(d.split("|", 1)[1])
        if not path or int(path.get("user_id", 0)) != int(user.id):
            await safe_answer(q, "❌ مسیر پیدا نشد.", True)
            return True
        return await _sim_begin(q, ctx, user, path.get("target_job", ""))

    if d == "aim_sim_resume":
        sims = [s for s in ai_db.list_simulations(user.id, 3)
                if s.get("status") == "active"]
        if not sims:
            await safe_answer(q, "مصاحبهٔ نیمه‌تمامی ندارید.", True)
            return True
        sim = ai_db.get_simulation(sims[0]["id"])
        ctx.user_data["aim_sim_id"] = sim["id"]
        ctx.user_data["state"] = "wait_aim_sim_answer"
        idx = len(sim["scores_json"])
        if idx >= len(sim["questions_json"]):
            return await _sim_finish(q.message, ctx, user, sim["id"])
        await _edit(q, _sim_q_text(sim, idx), ai_sim_answer_kb())
        return True

    if d == "aim_sim_skip":
        sid = ctx.user_data.get("aim_sim_id")
        if not sid:
            await safe_answer(q, "مصاحبهٔ فعالی ندارید.", True)
            return True
        return await _sim_answer(q.message, ctx, user, "(بدون پاسخ)", q=q)

    if d == "aim_sim_stop":
        sid = ctx.user_data.get("aim_sim_id")
        if not sid:
            await safe_answer(q, "مصاحبهٔ فعالی ندارید.", True)
            return True
        ctx.user_data.pop("state", None)
        await safe_answer(q, "🛑 مصاحبه پایان یافت.")
        return await _sim_finish(q.message, ctx, user, sid, edit_q=q)

    if d == "aim_sim_history":
        sims = [s for s in ai_db.list_simulations(user.id, 10)
                if s.get("status") == "finished"]
        if not sims:
            await safe_answer(q, "هنوز مصاحبه‌ای کامل نکرده‌اید.", True)
            return True
        lines = ["📊 نتایج مصاحبه‌های قبلی", "━━━━━━━━━━━━━━━━", ""]
        for s in sims:
            lines.append(f"🎤 {s['target_job'][:40]}")
            lines.append(f"   نمره: {fa_digits(s['final_score'])}/۱۰۰ "
                         f"— {s['created_at'][:10]}")
        await _edit(q, "\n".join(lines), mkb([back_btn("aim_interview_sim")]))
        return True

    # ---- فاز ۴: مأموریت‌های واقعی ----
    if d == "aim_real_missions":
        missions = ai_db.list_real_missions(only_active=True)
        done = {m["mission_id"] for m in ai_db.list_user_missions(user.id, 50)
                if m.get("status") == "approved"}
        await _edit(q, (
            "💼 مأموریت‌های واقعی\n━━━━━━━━━━━━━━━━\n\n"
            "پروژه‌های عملی انجام دهید و اعتبار کسب کنید.\n"
            "کار شما توسط هوش مصنوعی داوری می‌شود.\n\n"
            f"📋 مأموریت‌های فعال: {fa_digits(len(missions))}"
        ), ai_missions_kb(missions, done))
        return True

    if d.startswith("aim_mission_view|"):
        m = ai_db.get_real_mission(d.split("|", 1)[1])
        if not m:
            await safe_answer(q, "❌ مأموریت پیدا نشد.", True)
            return True
        prev = ai_db.get_user_mission(user.id, m["id"])
        lines = [f"💼 {m['title']}", "━━━━━━━━━━━━━━━━", "",
                 m.get("description", ""), "",
                 f"🎁 پاداش: {fa_digits(m['reward_credits'])} اعتبار"]
        if m.get("required_skills"):
            lines.append(f"🧩 مهارت‌های لازم: {', '.join(m['required_skills'])}")
        can = True
        if prev:
            st = {"approved": "✅ تأییدشده", "rejected": "❌ ردشده",
                  "pending": "⏳ در انتظار"}.get(prev["status"], prev["status"])
            lines += ["", f"📌 وضعیت ارسال قبلی شما: {st}"
                          f" (نمره: {fa_digits(prev.get('ai_grade', 0))})"]
            if prev.get("ai_feedback"):
                lines.append(f"💬 {prev['ai_feedback'][:250]}")
            if prev["status"] == "approved":
                can = False
                lines.append("\n🎉 شما این مأموریت را با موفقیت انجام داده‌اید.")
        await _edit(q, "\n".join(lines), ai_mission_detail_kb(m["id"], can))
        return True

    if d.startswith("aim_mission_do|"):
        mid = d.split("|", 1)[1]
        m = ai_db.get_real_mission(mid)
        if not m or m.get("status") != "active":
            await safe_answer(q, "❌ این مأموریت فعال نیست.", True)
            return True
        prev = ai_db.get_user_mission(user.id, m["id"])
        if prev and prev["status"] == "approved":
            await safe_answer(q, "✅ قبلاً این مأموریت را انجام داده‌اید.", True)
            return True
        ctx.user_data["state"] = "wait_aim_mission_submission"
        ctx.user_data["aim_mission_id"] = m["id"]
        await _edit(q, (
            f"✍️ ارسال کار — {m['title']}\n━━━━━━━━━━━━━━━━\n\n"
            "شرح کاری که انجام داده‌اید را بنویسید.\n"
            "می‌توانید لینک پروژه، کد یا توضیح کامل بفرستید.\n\n"
            "⚠️ حداقل ۱۵ کلمه بنویسید تا قابل داوری باشد."
        ), mkb([back_btn(f"aim_mission_view|{m['id']}")]))
        return True

    if d == "aim_my_missions":
        subs = ai_db.list_user_missions(user.id, 15)
        lines = ["📋 ارسال‌های من", "━━━━━━━━━━━━━━━━", ""]
        if subs:
            for s in subs:
                st = {"approved": "✅", "rejected": "❌",
                      "pending": "⏳"}.get(s["status"], "•")
                lines.append(f"{st} {s.get('title') or '—'} — "
                             f"نمره {fa_digits(s.get('ai_grade', 0))}")
        else:
            lines.append("هنوز کاری ارسال نکرده‌اید.")
        await _edit(q, "\n".join(lines), mkb([back_btn("aim_real_missions")]))
        return True

    # ---- فاز ۴: یادگیری تیمی ----
    if d == "aim_team_learning":
        team = ai_db.get_user_team(user.id)
        if not team:
            await _edit(q, (
                "👥 یادگیری تیمی\n━━━━━━━━━━━━━━━━\n\n"
                "با هم‌مسیرهای خودتان در یک تیم کوچک (حداکثر ۴ نفر) "
                "روی یک پروژهٔ مشترک کار کنید.\n\n"
                "تیم بر اساس شغل هدف و شهر شما انتخاب می‌شود."
            ), ai_team_kb(False))
            return True
        return await _show_team(q, user, team["id"])

    if d == "aim_team_join":
        res = ai_core.suggest_or_create_team(user.id)
        if not res.get("ok"):
            await safe_answer(q, f"⚠️ {res.get('error')}", True)
            return True
        team = res["team"]
        note = ("🆕 تیم جدیدی ساخته شد و شما سرگروه هستید."
                if res.get("created") else "✅ به یک تیم موجود اضافه شدید.")
        await safe_answer(q, "✅ انجام شد.", True)
        return await _show_team(q, user, team["id"], note)

    if d.startswith("aim_team_members|"):
        tid = d.split("|", 1)[1]
        team = ai_db.get_team(tid)
        # 🔒 فقط اعضای همان تیم
        if not team or not ai_db.user_in_team(int(tid), user.id):
            await safe_answer(q, "❌ تیم پیدا نشد.", True)
            return True
        members = ai_db.get_team_members(tid)
        lines = [f"👥 اعضای {team['team_name']}", "━━━━━━━━━━━━━━━━", ""]
        for m in members:
            prof = ai_db.get_user_profile(m["user_id"]) or {}
            nm = prof.get("first_name") or str(m["user_id"])
            crown = "👑 " if m["role"] == "leader" else "• "
            p = ai_db.get_active_path(m["user_id"])
            prog = ""
            if p:
                dn, tt = ai_db.path_progress(p["id"])
                prog = f" — {fa_digits(dn)}/{fa_digits(tt)} گام"
            me = " (شما)" if int(m["user_id"]) == int(user.id) else ""
            lines.append(f"{crown}{nm}{me}{prog}")
        await _edit(q, "\n".join(lines),
                    mkb([back_btn("aim_team_learning")]))
        return True

    if d.startswith("aim_team_feedback|"):
        tid = d.split("|", 1)[1]
        # 🔒 فقط اعضای همان تیم
        if not ai_db.user_in_team(int(tid), user.id):
            await safe_answer(q, "❌ تیم پیدا نشد.", True)
            return True
        await _edit(q, "🤖 در حال بررسی پیشرفت تیم…", None)
        res = await ai_core.team_progress_feedback(int(tid))
        if not res.get("ok"):
            await _edit(q, f"❌ {res.get('error')}",
                        mkb([back_btn("aim_team_learning")]))
            return True
        lines = ["🤖 بازخورد تیم", "━━━━━━━━━━━━━━━━", "",
                 res.get("feedback", ""), ""]
        if res.get("team_score"):
            lines.append(f"📊 امتیاز تیم: {fa_digits(res['team_score'])}/۱۰۰\n")
        if res.get("next_steps"):
            lines.append("🎯 گام‌های بعدی:")
            lines += [f"  {i}. {x}" for i, x in enumerate(res["next_steps"][:3], 1)]
        await _edit(q, "\n".join(lines), mkb([back_btn("aim_team_learning")]))
        return True

    if d.startswith("aim_team_leave|"):
        tid = d.split("|", 1)[1]
        if not ai_db.user_in_team(int(tid), user.id):   # 🔒 مالکیت
            await safe_answer(q, "❌ تیم پیدا نشد.", True)
            return True
        ai_db.leave_team(user.id, int(tid))
        await safe_answer(q, "🚪 از تیم خارج شدید.", True)
        await _edit(q, (
            "👥 یادگیری تیمی\n━━━━━━━━━━━━━━━━\n\n"
            "شما عضو هیچ تیمی نیستید."
        ), ai_team_kb(False))
        return True

    # ---- فاز ۴: پروفایل عمومی ----
    if d == "aim_public_profile":
        p = ai_db.ensure_public_profile(user.id)
        is_pub = bool(p.get("is_public"))
        await _edit(q, (
            "🌐 پروفایل عمومی\n━━━━━━━━━━━━━━━━\n\n"
            f"وضعیت: {'🟢 عمومی' if is_pub else '🔴 خصوصی'}\n"
            f"🔖 کد استعلام شما: {p.get('verification_code', '—')}\n"
            f"👁 بازدید کارفرما: {fa_digits(p.get('views', 0))}\n\n"
            + (f"📝 معرفی: {p.get('custom_bio')}\n\n" if p.get("custom_bio") else "")
            + ("کارفرما با ارسال این کد ۶ حرفی به ربات، خلاصهٔ مهارت‌ها و "
               "آمادگی شغلی شما را می‌بیند."
               if is_pub else
               "برای اینکه کارفرما بتواند پروفایل شما را ببیند، "
               "آن را «عمومی» کنید.")
        ), ai_public_profile_kb(is_pub))
        return True

    if d == "aim_pub_toggle":
        p = ai_db.ensure_public_profile(user.id)
        new = not bool(p.get("is_public"))
        ai_db.set_public_profile(user.id, is_public=new)
        await safe_answer(q, "🟢 عمومی شد." if new else "🔴 خصوصی شد.", True)
        return await handle_aim_callback("aim_public_profile", q, ctx, user)

    if d == "aim_pub_bio":
        ctx.user_data["state"] = "wait_aim_pub_bio"
        await _edit(q, (
            "📝 معرفی کوتاه\n━━━━━━━━━━━━━━━━\n\n"
            "یک معرفی کوتاه از خودتان بنویسید (حداکثر ۶۰۰ کاراکتر).\n"
            "این متن به کارفرما نمایش داده می‌شود.\n\n"
            "برای حذف «-» بفرستید."
        ), mkb([back_btn("aim_public_profile")]))
        return True

    if d == "aim_pub_preview":
        await _edit(q, "👁 در حال ساخت پیش‌نمایش…", None)
        txt = await _public_profile_text(user.id, preview=True)
        await _edit(q, txt, mkb([back_btn("aim_public_profile")]))
        return True

    # ---- تنظیمات / موجودی ----
    if d == "aim_settings":
        await _edit(q, "⚙️ تنظیمات یار هوشمند", ai_settings_kb())
        return True
    if d == "aim_balance":
        await show_balance(q, user)
        return True

    # ---- خرید اعتبار ----
    if d == "aim_buy":
        # فاز ۲ (بهبود ۴) — تعرفه‌ها بالای بسته‌ها نمایش داده می‌شود
        await _edit(q, (
            "💳 شارژ اعتبار هوشمند\n━━━━━━━━━━━━━━━━\n\n"
            f"💰 اعتبار فعلی شما: {fa_digits(ai_core.get_user_ai_balance(user.id))}\n\n"
            f"{pricing_info_text()}\n\n"
            "━━━━━━━━━━━━━━━━\n"
            "بستهٔ مورد نظر را انتخاب کنید. پس از انتخاب، راهنمای پرداخت "
            "و ارسال رسید نمایش داده می‌شود."
        ), ai_pricing_info_kb())
        return True

    if d.startswith("aim_pack|"):
        # شناسهٔ بسته از دیتابیس خوانده می‌شود — هیچ قیمتی در کد نیست
        pkg = ai_db.get_credit_package(d.split("|", 1)[1])
        if not pkg or not pkg.get("is_active"):
            await safe_answer(q, "❌ این بسته دیگر در دسترس نیست.", True)
            await _edit(q, "💳 شارژ اعتبار هوشمند", ai_pricing_kb())
            return True

        # فاز ۴ — اطلاعات کارت از دیتابیس خوانده می‌شود
        pay = ai_db.get_admin_payment_info()
        if not ai_db.payment_info_ready():
            await _edit(q, (
                "⚠️ اطلاعات پرداخت هنوز توسط مدیر ثبت نشده است.\n\n"
                "لطفاً از بخش «📞 پشتیبانی» اقدام کنید."
            ), mkb([[btn("📞 پشتیبانی", "support")], back_btn("aim_buy")]))
            return True

        lines = [
            f"💎 بستهٔ {fa_digits(pkg['amount'])} اعتبار",
            "━━━━━━━━━━━━━━━━", "",
            f"💰 مقدار اعتبار: {fa_digits(pkg['amount'])}",
            f"💵 مبلغ قابل پرداخت: {price_label(pkg['price'])}", "",
            "🏦 اطلاعات پرداخت:",
            f"💳 شمارهٔ کارت: {pay.get('card_number', '')}",
        ]
        if pay.get("card_holder"):
            lines.append(f"👤 به نام: {pay['card_holder']}")
        if pay.get("bank_name"):
            lines.append(f"🏛 بانک: {pay['bank_name']}")
        if pay.get("note"):
            lines += ["", f"📝 {pay['note']}"]
        lines += ["", "پس از واریز، روی دکمهٔ زیر بزنید و عکس فیش را بفرستید."]

        await _edit(q, "\n".join(lines), ai_pack_confirm_kb(pkg["id"]))
        return True

    if d.startswith("aim_fiche|"):
        pkg = ai_db.get_credit_package(d.split("|", 1)[1])
        if not pkg or not pkg.get("is_active"):
            await safe_answer(q, "❌ این بسته دیگر در دسترس نیست.", True)
            return True
        if ai_db.user_pending_purchases(user.id) > 0:
            await safe_answer(q, "⏳ یک فیش در حال بررسی دارید. صبر کنید.", True)
            return True
        ctx.user_data["state"] = "wait_aim_fiche"
        ctx.user_data["aim_pkg_id"] = pkg["id"]
        await _edit(q, (
            "📤 ارسال فیش پرداخت\n━━━━━━━━━━━━━━━━\n\n"
            f"بستهٔ {fa_digits(pkg['amount'])} اعتبار — {price_label(pkg['price'])}\n\n"
            "یکی از این دو را بفرستید:\n"
            "📸 عکس فیش یا اسکرین‌شات پرداخت\n"
            "📝 متن رسید (حداقل ۵ کلمه)\n\n"
            "⚠️ فایل، صوت، ویدیو و استیکر پذیرفته نمی‌شود."
        ), mkb([back_btn("aim_buy")]))
        return True

    if d == "aim_noop":
        await safe_answer(q)
        return True

    return False


# ========================= فاز ۳: کمکی‌ها =========================

def _report_text(r: dict, when: str = "") -> str:
    lines = ["📄 گزارش آمادگی شغلی", "━━━━━━━━━━━━━━━━", ""]
    if r.get("target_job"):
        lines.append(f"🎯 مسیر: {r['target_job']}")
    if when:
        lines.append(f"📅 تاریخ: {when[:10]}")
    pct = int(r.get("readiness_percent") or 0)
    filled = max(0, min(10, round(pct / 10)))
    lines += ["", f"📊 آمادگی: {fa_digits(pct)}٪",
              "▰" * filled + "▱" * (10 - filled), ""]
    if r.get("strengths"):
        lines += ["💪 نقاط قوت:"] + [f"  • {x}" for x in r["strengths"][:5]] + [""]
    if r.get("weaknesses"):
        lines += ["⚠️ نقاط ضعف:"] + [f"  • {x}" for x in r["weaknesses"][:5]] + [""]
    if r.get("recommendations"):
        lines += ["🎯 پیشنهادها:"] + [
            f"  {i}. {x}" for i, x in enumerate(r["recommendations"][:3], 1)]
    if r.get("summary"):
        lines += ["", r["summary"]]
    return "\n".join(lines)


def _twin_text(r: dict, when: str = "") -> str:
    lines = ["👯‍♂️ همزاد شغلی — شبیه‌سازی بازار", "━━━━━━━━━━━━━━━━", ""]
    if r.get("target_job"):
        lines.append(f"🎯 بر اساس مسیر: {r['target_job']}")
    if when:
        lines.append(f"📅 {when[:10]}")
    jobs = r.get("jobs") or []
    acc = sum(1 for j in jobs if j.get("result") == "accepted")
    lines += ["", f"📨 از {fa_digits(len(jobs))} موقعیت، "
                  f"{fa_digits(acc)} پذیرش گرفتید.", ""]
    for j in jobs:
        icon = "✅" if j.get("result") == "accepted" else "❌"
        lines.append(f"{icon} {j.get('title', '')} — {j.get('company', '')}")
        if j.get("match_percent"):
            lines.append(f"   🎯 تطابق: {fa_digits(j['match_percent'])}٪")
        if j.get("salary_range"):
            lines.append(f"   💰 {j['salary_range']}")
        if j.get("reason"):
            lines.append(f"   ↳ {j['reason']}")
        lines.append("")
    if r.get("summary"):
        lines.append(f"📝 {r['summary']}")
    if r.get("next_skill"):
        lines.append(f"\n🚀 مهارت بعدی پیشنهادی: {r['next_skill']}")
    return "\n".join(lines)


def _sim_q_text(sim: dict, idx: int) -> str:
    qs = sim["questions_json"]
    q = qs[idx]
    kind = "🔧 تخصصی" if q.get("kind") == "technical" else "🧠 رفتاری"
    return (
        f"🎤 مصاحبه — {sim.get('target_job', '')}\n━━━━━━━━━━━━━━━━\n\n"
        f"سؤال {fa_digits(idx + 1)} از {fa_digits(len(qs))}  ({kind})\n\n"
        f"❓ {q['text']}\n\n"
        "پاسخ خود را بنویسید:"
    )


async def _sim_begin(q, ctx, user, target_job: str) -> bool:
    """شروع یک جلسهٔ مصاحبه پس از کسر اعتبار."""
    ok, cost, msg = ai_core.check_and_deduct_credits(user.id, "interview_sim")
    if not ok:
        await _edit(q, msg, ai_buy_hint_kb())
        return True
    await _edit(q, "🎤 در حال آماده‌سازی سؤالات مصاحبه…", None)
    res = await ai_core.start_interview_simulation(user.id, target_job)
    if not res.get("ok"):
        back = ai_core.refund(user.id, cost, "interview_sim_failed")
        await _edit(q, f"❌ {res.get('error')}\n\n"
                    + ("اعتبار شما بازگردانده شد." if back else ""),
                    mkb([back_btn("aim_interview_sim")]))
        return True
    ctx.user_data["aim_sim_id"] = res["sim_id"]
    ctx.user_data["state"] = "wait_aim_sim_answer"
    sim = ai_db.get_simulation(res["sim_id"])
    await _edit(q, _sim_q_text(sim, 0), ai_sim_answer_kb())
    return True


async def _sim_answer(msg, ctx, user, text: str, q=None) -> bool:
    """ثبت یک پاسخ و رفتن به سؤال بعد (یا پایان)."""
    sid = ctx.user_data.get("aim_sim_id")
    sim = ai_db.get_simulation(sid) if sid else None
    if not sim or sim.get("status") != "active":
        ctx.user_data.pop("state", None)
        await msg.reply_text("❌ مصاحبهٔ فعالی پیدا نشد.",
                             reply_markup=mkb([back_btn("aim_menu")]))
        return True

    idx = len(sim["scores_json"])
    qs = sim["questions_json"]
    if idx >= len(qs):
        return await _sim_finish(msg, ctx, user, sid, edit_q=q)

    ai_db.append_simulation_answer(sid, qs[idx]["text"], text)
    sim = ai_db.get_simulation(sid)
    nxt = len(sim["scores_json"])

    if nxt >= len(qs):
        return await _sim_finish(msg, ctx, user, sid, edit_q=q)

    ctx.user_data["state"] = "wait_aim_sim_answer"
    body = _sim_q_text(sim, nxt)
    if q is not None:
        await _edit(q, body, ai_sim_answer_kb())
    else:
        await msg.reply_text(body, reply_markup=ai_sim_answer_kb())
    return True


async def _sim_finish(msg, ctx, user, sim_id, edit_q=None) -> bool:
    """نمره‌دهی نهایی — یک فراخوانی AI برای همهٔ پاسخ‌ها."""
    ctx.user_data.pop("state", None)
    ctx.user_data.pop("aim_sim_id", None)

    if edit_q is not None:
        await _edit(edit_q, "📝 در حال بررسی پاسخ‌های شما…", None)
        wait = None
    else:
        wait = await msg.reply_text("📝 در حال بررسی پاسخ‌های شما…")

    res = await ai_core.grade_interview_simulation(sim_id)
    if not res.get("ok"):
        out, kb = f"❌ {res.get('error')}", mkb([back_btn("aim_interview_sim")])
    else:
        sc = int(res.get("total_score") or 0)
        grade = ("عالی 🏆" if sc >= 80 else "خوب 👍" if sc >= 60
                 else "متوسط 📚" if sc >= 40 else "نیاز به تمرین 💪")
        lines = ["🎤 نتیجهٔ شبیه‌سازی مصاحبه", "━━━━━━━━━━━━━━━━", "",
                 f"📊 نمرهٔ کل: {fa_digits(sc)} از ۱۰۰  ({grade})",
                 "▰" * max(0, min(10, round(sc / 10)))
                 + "▱" * (10 - max(0, min(10, round(sc / 10)))), ""]
        if res.get("strengths"):
            lines += ["💪 نقاط قوت:"] + [f"  • {x}" for x in res["strengths"][:4]] + [""]
        if res.get("weaknesses"):
            lines += ["⚠️ نقاط ضعف:"] + [f"  • {x}" for x in res["weaknesses"][:4]] + [""]
        if res.get("tips"):
            lines += ["🎯 نکات کلیدی:"] + [
                f"  {i}. {x}" for i, x in enumerate(res["tips"][:3], 1)]
        out = "\n".join(lines)
        kb = mkb([[btn("🔁 مصاحبهٔ دوباره", "aim_interview_sim")],
                  back_btn("aim_menu")])

    if edit_q is not None:
        await _edit(edit_q, out, kb)
    elif wait is not None:
        try:
            await wait.edit_text(out, reply_markup=kb)
        except Exception:
            await msg.reply_text(out, reply_markup=kb)
    return True


async def _send_certificate(ctx, chat_id, cert: dict) -> bool:
    """ارسال فایل PDF گواهینامه."""
    fp = cert.get("file_path") or ""
    if not fp or not os.path.exists(fp):
        return False
    try:
        with open(fp, "rb") as f:
            await ctx.bot.send_document(
                chat_id, f, filename=os.path.basename(fp),
                caption=(f"🎓 گواهینامهٔ «{cert.get('target_job', '')}»\n"
                         f"🔖 کد استعلام: {cert.get('certificate_id', '')}"),
            )
        return True
    except Exception as e:
        logger.warning(f"ارسال گواهینامه ناموفق: {e}")
        return False


async def _maybe_issue_certificate(ctx, user, path_id) -> None:
    """اگر مسیر ۱۰۰٪ تکمیل شد، گواهینامه صادر و ارسال می‌شود.

    هر خطایی بی‌صدا رد می‌شود تا فلوی اصلی کاربر متوقف نشود.
    """
    try:
        done, total = ai_db.path_progress(path_id)
        if total <= 0 or done < total:
            return
        if ai_db.get_certificate_for_path(user.id, path_id):
            return

        ai_db.complete_path(path_id)
        reps = ai_db.list_career_reports(user.id, int(path_id), 1)
        readiness = reps[0]["readiness_percent"] if reps else 0

        res = ai_core.issue_certificate(user.id, int(path_id), readiness)
        if not res.get("ok"):
            logger.info(f"صدور گواهینامه ناموفق: {res.get('error')}")
            return
        cert = ai_db.get_certificate_for_path(user.id, path_id) or {
            "file_path": res["file_path"],
            "certificate_id": res["certificate_id"],
            "target_job": (ai_db.get_path(path_id) or {}).get("target_job", ""),
        }
        chat_id = None
        try:
            chat_id = ctx._chat_id
        except Exception:
            pass
        if chat_id is None:
            chat_id = user.id
        await _send_certificate(ctx, chat_id, cert)
    except Exception as e:
        logger.warning(f"_maybe_issue_certificate: {e}")


# ═════════════════ معماری چندعاملی — ارکستراسیون ═════════════════

async def _begin_interview(q, ctx, user) -> bool:
    """شروع گفتگو با ایجنت ۱ (مصاحبه‌گر شغلی)."""
    journey = UserJourneyContext(user.id)
    journey.stage = "introduction"
    ctx.user_data["state"] = "wait_aim_interview"

    await _edit(q, (
        "🚀 بیا با هم مسیرت رو پیدا کنیم\n━━━━━━━━━━━━━━━━\n\n"
        "من مصاحبه‌گر شغلی‌ات هستم. چند سؤال کوتاه می‌پرسم تا خوب "
        "بشناسمت، بعد چند مسیر واقعی بازار رو بهت معرفی می‌کنم.\n\n"
        "⏳ در حال آماده‌سازی اولین سؤال…"
    ), None)

    res = await _AGENT1.run(journey, "")
    _save_journey(ctx, journey)
    return await _render_interview(q, ctx, user, res, edit=True)


async def _render_interview(target, ctx, user, res: dict,
                            edit: bool = False) -> bool:
    """نمایش خروجی ایجنت ۱ بسته به مرحله‌ای که در آن است.

    target یا یک CallbackQuery است (edit=True) یا یک Message.
    """
    async def _out(text, kb=None):
        if edit:
            await _edit(target, text, kb)
        else:
            await target.reply_text(text, reply_markup=kb)

    stage = res.get("stage")

    # ── مرحلهٔ سؤال ──
    if stage == "questioning":
        asked = res.get("asked", 1)
        total = res.get("total", MAX_QUESTIONS)
        lines = [f"💬 پرسش {fa_digits(asked)} از حدود {fa_digits(total)}",
                 "━━━━━━━━━━━━━━━━", "", res.get("message", "")]
        if res.get("hint"):
            lines += ["", f"💡 {res['hint']}"]
        await _out("\n".join(lines), mkb([back_btn("aim_menu")]))
        return True

    # ── مرحلهٔ معرفی مسیرها ──
    if stage == "suggestion":
        paths = res.get("paths") or []
        ctx.user_data.pop("state", None)
        await _out(_paths_text(paths, res.get("message", "")), _paths_kb(paths))
        return True

    # ── مرحلهٔ گزارش ──
    if stage == "report":
        ctx.user_data.pop("state", None)
        journey = _journey(ctx, user)
        await _out(_report_path_text(journey.selected_path, res.get("report") or {}),
                   _confirm_kb())
        return True

    ctx.user_data.pop("state", None)
    await _out("⚠️ گفتگو ناتمام ماند. دوباره تلاش کنید.",
               mkb([[btn("🔄 شروع دوباره", "aim_start")], back_btn("aim_menu")]))
    return True


def _paths_text(paths, intro: str = "") -> str:
    """متن معرفی ۳ مسیر پیشنهادی بازار."""
    lines = ["🧭 مسیرهای پیشنهادی برای تو", "━━━━━━━━━━━━━━━━", ""]
    if intro:
        lines += [intro, ""]
    demand_fa = {"high": "🔥 تقاضای بالا", "medium": "📊 تقاضای متوسط",
                 "low": "📉 تقاضای کم"}
    diff_fa = {"easy": "🟢 ساده", "medium": "🟡 متوسط", "hard": "🔴 سخت"}
    for p in paths:
        lines.append(f"{fa_digits(p.get('id', 0))}. {p.get('title', '')}")
        if p.get("fit_percent"):
            lines.append(f"   🎯 تناسب با تو: {fa_digits(p['fit_percent'])}٪")
        meta = [demand_fa.get(p.get("demand"), ""), diff_fa.get(p.get("difficulty"), "")]
        meta = [m for m in meta if m]
        if meta:
            lines.append("   " + "  |  ".join(meta))
        if p.get("salary_range"):
            lines.append(f"   💰 {p['salary_range']}")
        if p.get("why"):
            lines.append(f"   ↳ {p['why']}")
        if p.get("key_skills"):
            lines.append(f"   🧩 {'، '.join(p['key_skills'][:4])}")
        lines.append("")
    lines.append("کدام مسیر را می‌خواهی؟ روی آن بزن تا گزارش کاملش را ببینی.")
    return "\n".join(lines)


def _paths_kb(paths):
    """دکمهٔ انتخاب برای هر مسیر پیشنهادی (حداکثر ۲ دکمه در ردیف)."""
    rows = [[btn(f"{fa_digits(p.get('id', i))}. {(p.get('title') or '')[:34]}",
                 f"aim_pick_path|{p.get('id', i)}")]
            for i, p in enumerate(paths, 1)]
    if not rows:
        rows.append([btn("— مسیری پیشنهاد نشد —", "aim_noop")])
    rows.append([btn("🔄 شروع دوباره", "aim_start")])
    rows.append(back_btn("aim_menu"))
    return mkb(rows)


def _confirm_kb():
    return mkb([
        [btn("✅ همین مسیر را می‌خواهم", "aim_confirm_path")],
        [btn("🔙 مسیرهای دیگر", "aim_paths_again")],
        back_btn("aim_menu"),
    ])


def _report_path_text(path: dict, report: dict) -> str:
    """گزارش کامل مسیر انتخابی — تا کاربر با چشم باز تصمیم بگیرد."""
    p, r = path or {}, report or {}
    lines = [f"📋 گزارش مسیر: {p.get('title', '')}", "━━━━━━━━━━━━━━━━", ""]
    if r.get("summary"):
        lines += [r["summary"], ""]
    if r.get("key_skills"):
        lines += ["🧩 مهارت‌های کلیدی:"] + [f"  • {x}" for x in r["key_skills"][:8]] + [""]
    if r.get("tools"):
        lines += ["🛠 ابزارهای موردنیاز:"] + [f"  • {x}" for x in r["tools"][:6]] + [""]
    if r.get("ai_tools"):
        lines += ["🤖 ابزارهای هوش مصنوعی کمکی:"] + [
            f"  • {x}" for x in r["ai_tools"][:5]] + [""]
    if r.get("duration"):
        lines += [f"⏳ مدت تخمینی: {r['duration']}", ""]
    if p.get("salary_range"):
        lines += [f"💰 بازهٔ درآمد: {p['salary_range']}", ""]
    if r.get("opportunities"):
        lines += ["🚀 فرصت‌های شغلی:"] + [f"  • {x}" for x in r["opportunities"][:5]] + [""]
    if r.get("challenges"):
        lines += ["⚠️ چالش‌های پیش رو:"] + [f"  • {x}" for x in r["challenges"][:5]] + [""]
    lines.append("اگر این مسیر را تأیید کنی، نقشه راه گام‌به‌گامت ساخته می‌شود.")
    return "\n".join(lines)


async def _pick_path(q, ctx, user, raw_id) -> bool:
    """کاربر یکی از ۳ مسیر را انتخاب کرد → ایجنت ۱ گزارش کامل می‌دهد."""
    journey = _journey(ctx, user)
    if not journey.suggested_paths:
        await safe_answer(q, "❌ فهرست مسیرها منقضی شده. دوباره شروع کنید.", True)
        return True

    try:
        pid = int(str(raw_id).strip())
    except Exception:
        await safe_answer(q, "❌ انتخاب نامعتبر است.", True)
        return True

    chosen = next((p for p in journey.suggested_paths
                   if int(p.get("id") or 0) == pid), None)
    if not chosen:
        await safe_answer(q, "❌ این مسیر پیدا نشد.", True)
        return True

    journey.selected_path = chosen
    journey.stage = "report"
    await _edit(q, f"📋 در حال آماده‌سازی گزارش «{chosen.get('title', '')}»…", None)

    res = await _AGENT1.run(journey, "")
    report = res.get("report") or {}
    if not report.get("summary"):
        report = _AGENT1.fallback_report(chosen)
        journey.report = report
    _save_journey(ctx, journey)

    await _edit(q, _report_path_text(chosen, report), _confirm_kb())
    return True


async def _confirm_and_build(q, ctx, user) -> bool:
    """تأیید کاربر → JSON نهایی ایجنت ۱ → ایجنت ۲ اسکلت نقشه راه را می‌سازد.

    کسر اعتبار دقیقاً همین‌جا انجام می‌شود — لحظهٔ ارائهٔ خدمت. اگر کاربر
    وسط مصاحبه منصرف شده بود، چیزی از او کسر نشده است.
    """
    journey = _journey(ctx, user)
    if not journey.selected_path:
        await safe_answer(q, "❌ اول یک مسیر انتخاب کنید.", True)
        return True

    ok_pay, cost, pay_msg = ai_core.check_and_deduct_credits(user.id, "roadmap")
    if not ok_pay:
        await _edit(q, pay_msg, ai_buy_hint_kb())
        return True

    # ── ایجنت ۱: خروجی JSON نهایی (بدون فراخوانی اضافهٔ AI) ──
    final_json = _AGENT1.build_final_json(journey)

    await _edit(q, _BUILD_STEPS[0], None)
    wait_msg = q.message

    # ── ایجنت ۲: اسکلت نقشه راه ──
    anim = asyncio.ensure_future(_animate(wait_msg, _BUILD_STEPS))
    try:
        res = await _AGENT2.run(journey)
    except Exception as e:
        logger.error(f"معمار نقشه راه استثنا داد: {e}", exc_info=True)
        res = {"ok": False, "error": str(e)}
    finally:
        anim.cancel()

    if not res.get("ok") or not res.get("roadmap"):
        back = ai_core.refund(user.id, cost, "roadmap_failed")
        await _edit(q, (
            f"❌ ساخت نقشه راه ناموفق بود.\n{res.get('error', '')}\n\n"
            f"{'اعتبار شما بازگردانده شد.' if back else ''}"
        ), mkb([[btn("🔄 تلاش دوباره", "aim_confirm_path")], back_btn("aim_menu")]))
        return True

    target = journey.target_job()
    path_id = ai_db.save_career_path(user.id, target, {
        "journey": journey.to_dict(),
        "weak_topics": [],
        "strong_topics": [],
    })
    if not path_id:
        ai_core.refund(user.id, cost, "path_save_failed")
        await _edit(q, "❌ ذخیرهٔ مسیر ناموفق بود. اعتبار بازگردانده شد.",
                    mkb([back_btn("aim_menu")]))
        return True

    journey.path_id = path_id
    # خروجی خام هر ایجنت جدا هم ذخیره می‌شود (قابل بازبینی و اشکال‌زدایی)
    ai_db.save_interview_json(path_id, final_json)
    ai_db.save_roadmap_json(path_id, {
        "roadmap": res["roadmap"],
        "total_steps": res.get("total_steps", len(res["roadmap"])),
        "total_estimated_days": res.get("total_estimated_days", 0),
        "final_project": res.get("final_project", ""),
    })

    # ⚠️ محتوا عمداً خالی می‌ماند — ایجنت ۳ در لحظهٔ باز کردن گام می‌سازد
    for st in res["roadmap"]:
        n = int(st.get("step_number") or 0)
        ai_db.save_path_step(
            path_id, n, st.get("step_type", "lesson"), st.get("title", ""),
            {
                "course_id": st.get("course_id", ""),
                "objective": st.get("objective", ""),
                "skills_to_learn": st.get("skills_to_learn", []),
                "tools_needed": st.get("tools_needed", []),
                "ai_tools": st.get("ai_tools", []),
                "difficulty": st.get("difficulty", "medium"),
                "estimated_hours": st.get("estimated_hours", 0),
                "expected_output": st.get("expected_output", ""),
            },
            status="active" if n == 1 else "locked",
        )

    ai_db.log_ai_usage(user.id, "roadmap", cost, res.get("model", ""))
    ctx.user_data.pop("aim_journey", None)
    ctx.user_data.pop("aim_draft", None)
    ctx.user_data.pop("state", None)

    await _edit(q, _roadmap_summary(target, res), mkb([
        [btn("🎯 شروع گام اول", "aim_continue")], home_btn()]))
    return True


def _roadmap_summary(target: str, res: dict) -> str:
    """خلاصهٔ اسکلت نقشه راه پس از ساخت."""
    steps = res.get("roadmap") or []
    lines = ["✅ نقشه راه شما آماده شد!", "━━━━━━━━━━━━━━━━", "",
             f"🎯 مسیر: {target}",
             f"📋 تعداد گام‌ها: {fa_digits(len(steps))}"]
    if res.get("total_estimated_days"):
        lines.append(f"⏳ مدت تخمینی: {fa_digits(res['total_estimated_days'])} روز")
    lines += ["", "🗺 نگاه کلی به گام‌ها:"]
    diff_icon = {"easy": "🟢", "medium": "🟡", "hard": "🔴"}
    for s in steps[:6]:
        icon = diff_icon.get(s.get("difficulty"), "•")
        lines.append(f"  {icon} {fa_digits(s.get('step_number', 0))}. {s.get('title', '')}")
    if len(steps) > 6:
        lines.append(f"  … و {fa_digits(len(steps) - 6)} گام دیگر")
    if res.get("final_project"):
        lines += ["", f"🏆 پروژهٔ نهایی: {res['final_project']}"]
    lines += ["", "محتوای هر گام دقیقاً وقتی بازش کنی ساخته می‌شود،",
              "پس همیشه متناسب با پیشرفت توست."]
    return "\n".join(lines)


def _profile_text(user) -> str:
    """متن پروفایل — نام، سن، شهر، اعتبار، XP و خلاصهٔ مسیرها."""
    from config import USERS
    prof = ai_db.get_user_profile(user.id) or {}
    u = USERS.get(str(user.id), {}) or {}
    bal = ai_core.get_user_ai_balance(user.id)
    paths = ai_db.list_user_paths(user.id, 5)

    nm = " ".join(x for x in (prof.get("first_name", ""),
                              prof.get("last_name", "")) if x).strip()
    lines = ["👤 پروفایل من", "━━━━━━━━━━━━━━━━", ""]
    lines.append(f"📝 نام: {nm or user.first_name or '—'}")
    lines.append(f"🎂 سن: {fa_digits(prof['age']) if prof.get('age') else '—'}")
    lines.append(f"🏙 شهر: {prof.get('city') or '—'}")
    lines += ["", f"💰 اعتبار: {fa_digits(bal)}",
              f"⭐ امتیاز (XP): {fa_digits(u.get('xp', 0) or 0)}"]
    free = ai_core.free_quota_left(user.id)
    if free:
        lines.append(f"🎁 تعامل رایگان: {fa_digits(free)}")

    lines += ["", "🗂 مسیرهای من:"]
    if paths:
        for p in paths:
            done, total = ai_db.path_progress(p["id"])
            icon = {"active": "▶️", "completed": "✅"}.get(p["status"], "📦")
            lines.append(f"  {icon} {p['target_job']} — "
                         f"{fa_digits(done)}/{fa_digits(total)}")
    else:
        lines.append("  هنوز مسیری نساخته‌اید.")

    nc = len(ai_db.list_certificates(user.id))
    nr = len(ai_db.list_career_reports(user.id))
    nm2 = len([x for x in ai_db.list_user_missions(user.id, 50)
               if x.get("status") == "approved"])
    if nc or nr or nm2:
        lines += ["", f"🎓 رزومه: {fa_digits(nc)}  |  "
                      f"📄 گزارش: {fa_digits(nr)}  |  "
                      f"💼 مأموریت: {fa_digits(nm2)}"]
    return "\n".join(lines)


# ========================= فاز ۴: تیم و پروفایل عمومی =========================

async def _show_team(q, user, team_id, note: str = "") -> bool:
    team = ai_db.get_team(team_id)
    if not team:
        await safe_answer(q, "❌ تیم پیدا نشد.", True)
        return True
    n = ai_db.team_member_count(team_id)
    st = {"forming": "🟡 در حال تشکیل", "active": "🟢 فعال",
          "completed": "✅ تکمیل‌شده"}.get(team["status"], team["status"])
    lines = [f"👥 {team['team_name']}", "━━━━━━━━━━━━━━━━", ""]
    if note:
        lines += [note, ""]
    lines += [
        f"📌 وضعیت: {st}",
        f"👤 اعضا: {fa_digits(n)} از {fa_digits(team['max_members'])}",
    ]
    if team.get("project_description"):
        lines += ["", f"📋 {team['project_description']}"]
    if team["status"] == "forming":
        lines += ["", "⏳ به‌محض پر شدن ظرفیت، تیم فعال می‌شود."]
    await _edit(q, "\n".join(lines), ai_team_kb(True, team_id))
    return True


async def _public_profile_text(user_id: int, preview: bool = False) -> str:
    """متن پروفایل عمومی — هم برای پیش‌نمایش کاربر، هم برای کارفرما."""
    res = await ai_core.generate_public_summary(user_id)
    d = res.get("data") or {}
    p = ai_db.get_public_profile(user_id) or {}

    lines = ["🌐 پروفایل حرفه‌ای" + (" (پیش‌نمایش)" if preview else ""),
             "━━━━━━━━━━━━━━━━", ""]
    if d.get("name"):
        lines.append(f"👤 {d['name']}")
    meta = []
    if d.get("age"):
        meta.append(f"{fa_digits(d['age'])} ساله")
    if d.get("city"):
        meta.append(d["city"])
    if meta:
        lines.append("   " + " | ".join(meta))
    if d.get("target_job"):
        lines += ["", f"🎯 مسیر شغلی: {d['target_job']}"]
    if d.get("readiness"):
        lines.append(f"📊 آمادگی شغلی: {fa_digits(d['readiness'])}٪")
    if d.get("best_interview_score"):
        lines.append(f"🎤 نمرهٔ مصاحبهٔ آزمایشی: "
                     f"{fa_digits(d['best_interview_score'])}/۱۰۰")

    if p.get("custom_bio"):
        lines += ["", f"📝 {p['custom_bio']}"]

    if res.get("ok") and res.get("summary"):
        lines += ["", "💼 خلاصهٔ حرفه‌ای:", res["summary"]]
    ks = res.get("key_skills") or d.get("skills") or []
    if ks:
        lines += ["", "🧩 مهارت‌های کلیدی:"] + [f"  • {x}" for x in ks[:6]]
    if d.get("missions"):
        lines += ["", "🏗 پروژه‌های واقعی انجام‌شده:"] + [
            f"  • {x}" for x in d["missions"][:5]]
    if d.get("certificates"):
        lines += ["", "🎓 گواهینامه‌ها:"] + [
            f"  • {x}" for x in d["certificates"][:4]]
    if res.get("highlight"):
        lines += ["", f"⭐ {res['highlight']}"]
    if not res.get("ok"):
        lines += ["", "ℹ️ خلاصهٔ هوشمند در دسترس نبود؛ داده‌های خام نمایش داده شد."]
    return "\n".join(lines)


async def try_verification_code(text: str, msg, ctx) -> bool:
    """اگر متن یک «کد استعلام» معتبر باشد، پروفایل عمومی را نشان می‌دهد.

    این تابع از handlers.handle_text صدا زده می‌شود و برای هر کاربری
    (حتی کسی که حساب ندارد یا کارفرماست) کار می‌کند.
    خروجی True یعنی متن مصرف شد.
    """
    code = (text or "").strip().upper()
    # فیلتر سریع: دقیقاً ۶ کاراکتر از الفبای کدها
    if len(code) != 6 or not all(
            ch in "ABCDEFGHJKLMNPQRSTUVWXYZ23456789" for ch in code):
        return False
    if not module_enabled():
        return False

    rec = ai_db.find_by_verification_code(code)
    if not rec:
        return False

    try:
        wait = await msg.reply_text("🔎 در حال دریافت پروفایل…")
        body = await _public_profile_text(int(rec["user_id"]))
        body += f"\n\n🔖 کد استعلام: {code}"
        try:
            await wait.edit_text(body)
        except Exception:
            await msg.reply_text(body)
    except Exception as e:
        logger.warning(f"try_verification_code: {e}")
        return False
    return True


# ========================= فاز ۴: ثبت فیش =========================

async def submit_fiche(msg, ctx, user, fiche_file_id: str = "",
                       fiche_text: str = "") -> bool:
    """ثبت فیش پرداخت (از عکس یا متن) و اطلاع به ادمین‌ها."""
    pkg_id = ctx.user_data.pop("aim_pkg_id", 0)
    ctx.user_data.pop("state", None)

    pkg = ai_db.get_credit_package(pkg_id) if pkg_id else None
    if not pkg:
        await msg.reply_text("❌ اطلاعات بسته پیدا نشد. دوباره از منو شروع کنید.",
                             reply_markup=mkb([back_btn("aim_buy")]))
        return True

    if ai_db.user_pending_purchases(user.id) > 0:
        await msg.reply_text("⏳ یک فیش در حال بررسی دارید.",
                             reply_markup=mkb([back_btn("aim_menu")]))
        return True

    platform, chat_id = _origin(ctx, msg)
    pid = ai_db.save_credit_purchase(
        user.id, user.first_name or str(user.id), pkg["id"],
        pkg["amount"], pkg["price"], fiche_file_id, fiche_text,
        platform, chat_id,
    )
    if not pid:
        await msg.reply_text("❌ ثبت فیش ناموفق بود. دوباره تلاش کنید.",
                             reply_markup=mkb([back_btn("aim_buy")]))
        return True

    await msg.reply_text(
        "✅ فیش شما ثبت شد.\n━━━━━━━━━━━━━━━━\n\n"
        f"💎 بسته: {fa_digits(pkg['amount'])} اعتبار\n"
        f"💵 مبلغ: {price_label(pkg['price'])}\n\n"
        "⏳ پس از تأیید مدیر، اعتبار به حساب شما اضافه و به شما اطلاع داده می‌شود.",
        reply_markup=mkb([back_btn("aim_menu")]),
    )
    await _notify_admins_new_fiche(ctx, user, pkg)
    return True


def _origin(ctx, msg):
    """پلتفرم و chat_id مبدأ — برای پاسخ از همان ربات."""
    platform = "bale"
    try:
        from core import get_current_platform
        platform = get_current_platform() or "bale"
    except Exception:
        pass
    chat_id = ""
    try:
        chat_id = str(msg.chat_id)
    except Exception:
        pass
    return platform, chat_id


async def _notify_admins_new_fiche(ctx, user, pkg):
    """اعلان فیش جدید به ادمین‌ها — خطا هرگز به کاربر نشت نمی‌کند."""
    try:
        from config import ADMIN_IDS
        text = (
            "📬 فیش پرداخت جدید\n━━━━━━━━━━━━━━━━\n\n"
            f"👤 کاربر: {user.first_name or ''} ({user.id})\n"
            f"💎 بسته: {fa_digits(pkg['amount'])} اعتبار\n"
            f"💵 مبلغ: {price_label(pkg['price'])}\n\n"
            "برای بررسی: پنل مدیریت ← مدیریت یار هوشمند ← فیش‌های در انتظار"
        )
        for aid in list(ADMIN_IDS)[:10]:
            try:
                await ctx.bot.send_message(aid, text)
            except Exception:
                continue
    except Exception as e:
        logger.debug(f"اعلان فیش به ادمین ناموفق: {e}")


async def handle_aim_media(state: str, msg, ctx, user) -> bool:
    """دریافت عکس فیش. از handlers.handle_media صدا زده می‌شود."""
    if state != "wait_aim_fiche":
        return False

    file_id = ""
    if getattr(msg, "photo", None):
        file_id = msg.photo[-1].file_id
    elif getattr(msg, "document", None) and \
            (msg.document.mime_type or "").lower().startswith("image/"):
        file_id = msg.document.file_id
    else:
        await msg.reply_text(
            "❌ فقط عکس فیش یا رسید متنی پذیرفته می‌شود.\n"
            "لطفاً عکس فیش را بفرستید یا رسید را به‌صورت متن بنویسید."
        )
        return True

    return await submit_fiche(msg, ctx, user, fiche_file_id=file_id)


# ========================= stateهای متنی =========================

async def handle_aim_state(state: str, text: str, msg, ctx, user) -> bool:
    """پردازش ورودی متنی. خروجی True یعنی پردازش شد."""
    if state not in AIM_STATES:
        return False

    text = (text or "").strip()
    if not text:
        await msg.reply_text("لطفاً یک متن معتبر بفرستید.")
        return True

    # ---- فاز ۱: اطلاعات اولیه (onboarding) ----
    if state == "wait_aim_profile_name":
        parts = text.split()
        _draft(ctx)["p_first"] = parts[0][:60]
        _draft(ctx)["p_last"] = " ".join(parts[1:])[:60] if len(parts) > 1 else ""
        ctx.user_data["state"] = "wait_aim_profile_age"
        await msg.reply_text("۲ از ۳:\n🎂 چند سالته؟\n\nمثال: ۲۵")
        return True

    if state == "wait_aim_profile_age":
        age = _fa_int(text)
        if not 5 <= age <= 100:
            await msg.reply_text("❌ لطفاً یک سن معتبر بین ۵ تا ۱۰۰ بنویسید.")
            return True
        _draft(ctx)["p_age"] = age
        ctx.user_data["state"] = "wait_aim_profile_city"
        await msg.reply_text("۳ از ۳:\n🏙 در چه شهری زندگی می‌کنی؟\n\nمثال: تهران")
        return True

    if state == "wait_aim_profile_city":
        dr = _draft(ctx)
        dr["p_city"] = text[:60]
        ai_db.save_user_profile(
            user.id, dr.get("p_first", ""), dr.get("p_last", ""),
            dr.get("p_age", 0), dr.get("p_city", ""),
        )
        # پروفایل ثبت شد → شروع گفتگو با ایجنت ۱ (مصاحبه‌گر)
        journey = UserJourneyContext(user.id)
        ctx.user_data["state"] = "wait_aim_interview"
        await msg.reply_text(
            f"✅ ممنون {dr.get('p_first', '')}!\n\n"
            "🚀 حالا با هم گفتگو می‌کنیم تا مسیر درست را پیدا کنیم.\n\n"
            "⏳ در حال آماده‌سازی اولین سؤال…"
        )
        res = await _AGENT1.run(journey, "")
        _save_journey(ctx, journey)
        return await _render_interview(msg, ctx, user, res, edit=False)

    # ═════ ایجنت ۱ — گفتگوی مکالمه‌ای مصاحبه‌گر شغلی ═════
    # هر پیام کاربر به ایجنت ۱ می‌رود و پاسخش نمایش داده می‌شود. ایجنت
    # خودش تصمیم می‌گیرد سؤال بعدی را بپرسد یا به مرحلهٔ معرفی مسیرها برود.
    if state == "wait_aim_interview":
        journey = _journey(ctx, user)
        wait_msg = await msg.reply_text("💭 …")
        try:
            res = await _AGENT1.run(journey, text)
        except Exception as e:
            logger.error(f"مصاحبه‌گر استثنا داد: {e}", exc_info=True)
            ctx.user_data.pop("state", None)
            await wait_msg.edit_text(
                "❌ گفتگو با خطا مواجه شد. دوباره تلاش کنید.",
                reply_markup=mkb([[btn("🔄 شروع دوباره", "aim_start")],
                                  back_btn("aim_menu")]))
            return True
        _save_journey(ctx, journey)
        try:
            await wait_msg.delete()
        except Exception:
            pass
        return await _render_interview(msg, ctx, user, res, edit=False)

    # ═════ ایجنت ۳ — داوری پاسخ تمرین ═════
    # اگر درست بود گام بعدی باز می‌شود؛ اگر غلط بود فقط Hint داده می‌شود.
    if state == "wait_aim_exercise_answer":
        sid = ctx.user_data.get("aim_step_id")
        ctx.user_data.pop("state", None)
        # 🔒 مالکیت — جلوگیری از تکمیل گام دیگران و گرفتن XP
        step = ai_db.get_owned_step(sid, user.id) if sid else None
        if not step:
            await msg.reply_text("❌ گام پیدا نشد.")
            return True

        ok, cost, cmsg = ai_core.check_and_deduct_credits(user.id, "challenge")
        if not ok:
            await msg.reply_text(cmsg, reply_markup=ai_buy_hint_kb())
            return True

        wait_msg = await msg.reply_text("🧐 منتور در حال بررسی پاسخ شماست…")
        path = ai_db.get_path(step["path_id"])
        journey = _journey_from_path(path) if path else UserJourneyContext(user.id)
        if not journey.roadmap:
            journey.roadmap = [{
                "step_number": s["step_number"], "title": s["title"],
                "objective": (s.get("content") or {}).get("objective", ""),
                "exercise": (s.get("content") or {}).get("challenge", ""),
            } for s in ai_db.get_path_steps(step["path_id"])]

        try:
            res = await _AGENT3.run(journey, text,
                                    step_number=step["step_number"],
                                    task="grade")
        except Exception as e:
            logger.error(f"منتور در داوری استثنا داد: {e}", exc_info=True)
            res = {"ok": False, "error": str(e)}

        if not res.get("ok"):
            back = ai_core.refund(user.id, cost, "challenge_failed")
            await wait_msg.edit_text(
                f"❌ بررسی ناموفق بود.\n{res.get('error', '')}\n"
                + ("اعتبار شما بازگردانده شد." if back else ""),
                reply_markup=mkb([[btn("🔄 تلاش دوباره", f"aim_answer|{sid}")],
                                  back_btn("aim_continue")]))
            return True

        ai_db.log_ai_usage(user.id, "challenge", cost, res.get("model", ""))
        passed = res["passed"]

        # 🧠 حافظهٔ فردی — نمره ثبت می‌شود و روی محتوای گام‌های بعدی اثر
        # می‌گذارد (نقاط قوت/ضعف).
        prof_res = _AGENT3.update_learning_profile(journey, int(sid),
                                                   res["score"])
        # نمره داخل همان payload می‌رود تا update_step_status بازخورد
        # ثبت‌شده را بازنویسی نکند.
        payload = {"feedback": res["feedback"], "hint": res.get("hint", ""),
                   "score": res["score"], "status": res["status"],
                   "xp_reward": res.get("xp_reward", 0)}

        if passed:
            ai_db.update_step_status(sid, "completed", payload)
            ai_core.grant_challenge_reward(user.id, res.get("xp_reward", 0))
            out = (f"✅ آفرین! قبول شدی.\n\n"
                   f"📊 نمره: {fa_digits(res['score'])}/۱۰۰\n\n"
                   f"💬 {res['feedback']}\n\n"
                   f"🎁 +{fa_digits(res.get('xp_reward', 0))} امتیاز")
            if prof_res.get("bucket") == "strong":
                out += "\n\n💪 این مهارت به نقاط قوت شما اضافه شد."
            out += "\n\n🔓 گام بعدی باز شد."
            kb = mkb([[btn("🎯 ادامهٔ مسیر", "aim_continue")], home_btn()])
        else:
            ai_db.update_step_status(sid, "active", payload)
            out = (f"📝 هنوز کامل نیست.\n\n"
                   f"📊 نمره: {fa_digits(res['score'])}/۱۰۰\n\n"
                   f"💬 {res['feedback']}")
            if res.get("hint"):
                out += f"\n\n💡 راهنمایی: {res['hint']}"
            if prof_res.get("bucket") == "weak":
                out += "\n\n📌 این موضوع را یادداشت کردم تا در گام‌های بعدی بیشتر رویش کار کنیم."
            kb = mkb([[btn("🔄 تلاش دوباره", f"aim_answer|{sid}")],
                      back_btn("aim_continue")])
        ctx.user_data.pop("aim_step_id", None)
        await wait_msg.edit_text(out, reply_markup=kb)
        if passed:
            # فاز ۳ — اگر با این تمرین مسیر ۱۰۰٪ شد، گواهینامه صادر می‌شود
            await _maybe_issue_certificate(ctx, user, step["path_id"])
        return True

    # ---- فاز ۴: دریافت فیش (متنی) ----
    if state == "wait_aim_fiche":
        if len(text.split()) < 5:
            await msg.reply_text(
                "❌ رسید متنی باید حداقل ۵ کلمه باشد.\n"
                "بهتر است عکس فیش را بفرستید."
            )
            return True
        return await submit_fiche(msg, ctx, user, fiche_text=text)

    # ---- فاز ۳: شبیه‌ساز مصاحبه ----
    if state == "wait_aim_sim_job":
        ctx.user_data.pop("state", None)
        job = text[:120]

        class _Shim:
            """اجازه می‌دهد _sim_begin که برای callback نوشته شده،
            از مسیر پیام متنی هم استفاده شود."""
            def __init__(self, m):
                self._m = m
                self.message = m

            async def edit_message_text(self, t, reply_markup=None, **k):
                await self._m.reply_text(t, reply_markup=reply_markup)

            async def answer(self, text=None, show_alert=False, **k):
                if text:
                    await self._m.reply_text(text)

        return await _sim_begin(_Shim(msg), ctx, user, job)

    if state == "wait_aim_sim_answer":
        return await _sim_answer(msg, ctx, user, text)

    # ---- فاز ۴: ارسال کار مأموریت واقعی ----
    if state == "wait_aim_mission_submission":
        mid = ctx.user_data.get("aim_mission_id")
        if not mid:
            ctx.user_data.pop("state", None)
            await msg.reply_text("❌ مأموریت مشخص نیست.")
            return True
        if len(text.split()) < 15:
            await msg.reply_text(
                "❌ توضیح شما خیلی کوتاه است.\n"
                "حداقل ۱۵ کلمه بنویسید تا داوری منصفانه باشد."
            )
            return True
        ctx.user_data.pop("state", None)
        ctx.user_data.pop("aim_mission_id", None)

        wait_msg = await msg.reply_text("🤖 در حال داوری کار شما…")
        res = await ai_core.grade_real_mission(user.id, int(mid), text)
        if not res.get("ok"):
            await wait_msg.edit_text(
                f"❌ داوری ناموفق بود.\n{res.get('error', '')}",
                reply_markup=mkb([back_btn("aim_real_missions")]))
            return True

        passed = res["status"] == "approved"
        out = [("🎉 آفرین! کار شما تأیید شد." if passed
                else "📝 کار شما هنوز تأیید نشد."), "━━━━━━━━━━━━━━━━", "",
               f"📊 نمره: {fa_digits(res['grade'])}/۱۰۰", "",
               f"💬 {res['feedback']}"]
        if passed and res.get("reward"):
            out += ["", f"🎁 {fa_digits(res['reward'])} اعتبار به حساب شما اضافه شد."]
        if not passed and res.get("improvements"):
            out += ["", "🔧 برای بهبود:"] + [
                f"  • {x}" for x in res["improvements"][:3]]
        kb = mkb([[btn("💼 مأموریت‌های دیگر", "aim_real_missions")], home_btn()]) \
            if passed else \
            mkb([[btn("🔄 ارسال دوباره", f"aim_mission_do|{mid}")],
                 back_btn("aim_real_missions")])
        await wait_msg.edit_text("\n".join(out), reply_markup=kb)
        return True

    # ---- ویرایش اطلاعات پروفایل ----
    if state == "wait_aim_edit_profile":
        f = ctx.user_data.pop("aim_edit_field", "")
        ctx.user_data.pop("state", None)
        prof = ai_db.get_user_profile(user.id) or {}
        back = mkb([back_btn("aim_edit_profile")])
        if f == "name":
            parts = text.split()
            ai_db.save_user_profile(
                user.id, parts[0][:60],
                " ".join(parts[1:])[:60] if len(parts) > 1 else "",
                prof.get("age", 0), prof.get("city", ""))
            out = f"✅ نام شما به «{text[:60]}» تغییر کرد."
        elif f == "age":
            age = _fa_int(text)
            if not 5 <= age <= 100:
                await msg.reply_text("❌ سن باید عددی بین ۵ تا ۱۰۰ باشد.",
                                     reply_markup=back)
                return True
            ai_db.save_user_profile(user.id, prof.get("first_name", ""),
                                    prof.get("last_name", ""), age,
                                    prof.get("city", ""))
            out = f"✅ سن شما به {fa_digits(age)} تغییر کرد."
        elif f == "city":
            ai_db.save_user_profile(user.id, prof.get("first_name", ""),
                                    prof.get("last_name", ""),
                                    prof.get("age", 0), text[:60])
            out = f"✅ شهر شما به «{text[:60]}» تغییر کرد."
        else:
            await msg.reply_text("❌ فیلد مشخص نیست.", reply_markup=back)
            return True
        await msg.reply_text(out, reply_markup=mkb([back_btn("aim_profile")]))
        return True

    # ---- فاز ۴: معرفی کوتاه پروفایل عمومی ----
    if state == "wait_aim_pub_bio":
        ctx.user_data.pop("state", None)
        bio = "" if text == "-" else text[:600]
        ai_db.set_public_profile(user.id, custom_bio=bio)
        await msg.reply_text(
            "✅ معرفی شما ذخیره شد." if bio else "🗑 معرفی حذف شد.",
            reply_markup=mkb([back_btn("aim_public_profile")]))
        return True

    # ---- فاز ۲: کمک آگاه‌از‌زمینه در یک گام ----
    if state == "wait_aim_help":
        sid = ctx.user_data.get("aim_help_step")
        ctx.user_data.pop("state", None)
        if not sid:
            await msg.reply_text("❌ گام مشخص نیست.")
            return True
        ok_pay, cost, pay_msg = ai_core.check_and_deduct_credits(user.id, "help")
        if not ok_pay:
            await msg.reply_text(pay_msg, reply_markup=ai_buy_hint_kb())
            return True
        wait_msg = await msg.reply_text(_WAIT)
        res = await ai_core.chat_with_mentor_context(user.id, int(sid), text)
        if not res.get("ok"):
            back = ai_core.refund(user.id, cost, "help_failed")
            await wait_msg.edit_text(
                f"❌ پاسخ‌گویی ناموفق بود.\n{res.get('error', '')}\n"
                + ("اعتبار شما بازگردانده شد." if back else ""))
            return True
        await wait_msg.edit_text(f"💡 {res['text']}", reply_markup=ai_help_kb(sid))
        return True

    # ---- چت با منتور ----
    if state == "wait_aim_chat":
        ctx.user_data.pop("state", None)
        ok_pay, cost, pay_msg = ai_core.check_and_deduct_credits(user.id, "chat")
        if not ok_pay:
            await msg.reply_text(pay_msg, reply_markup=ai_buy_hint_kb())
            return True
        wait_msg = await msg.reply_text(_WAIT)
        res = await ai_core.chat_with_mentor(text)
        if not res.get("ok"):
            back = ai_core.refund(user.id, cost, "chat_failed")
            await wait_msg.edit_text(
                f"❌ پاسخ‌گویی ناموفق بود.\n{res.get('error', '')}\n"
                + ("اعتبار شما بازگردانده شد." if back else ""))
            return True
        ai_db.log_ai_usage(user.id, "chat", cost, res.get("model", ""))
        await wait_msg.edit_text(
            f"🤖 {res['text']}",
            reply_markup=mkb([[btn("💬 سؤال بعدی", "aim_chat")], back_btn("aim_learn")]),
        )
        return True

    return False
