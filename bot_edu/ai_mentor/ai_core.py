"""
ai_core.py — منطق «یار هوشمند شغلی».

قواعد رعایت‌شده:
  • پرداخت فقط با سیستم credits موجود (core.change_credits) — سیستم جدید ساخته نشد.
  • فراخوانی AI فقط از core.ask_ai / core.ask_ai_fast.
  • هیچ استثنایی به بیرون درز نمی‌کند؛ همهٔ توابع خروجی قابل‌اتکا می‌دهند.

وابستگی: config، core، ai_db، ai_prompts و stdlib.
"""
import json
import logging
import os
import re
import secrets

from config import ADMIN_IDS, USERS
from core import ask_ai, ask_ai_fast, change_credits, award_xp_and_credits

from . import ai_db
from .ai_prompts import (
    AI_CAREER_REPORT_PROMPT,
    AI_CAREER_TWIN_PROMPT,
    AI_CHAT_MENTOR_PROMPT,
    AI_CHAT_MENTOR_WITH_CONTEXT,
    AI_INTERVIEW_GRADER_PROMPT,
    AI_INTERVIEW_SIMULATOR_PROMPT,
    AI_MENTOR_PROMPT,
    AI_MISSION_GRADER_PROMPT,
    AI_PUBLIC_PROFILE_SUMMARY,
    AI_TEAM_FEEDBACK_PROMPT,
    AI_TREND_ANALYST_PROMPT,
)

logger = logging.getLogger(__name__)

# نگاشت نوع اکشن → کلید تعرفه در ai_settings
ACTION_PRICE_KEY = {
    "roadmap":   "price_roadmap",
    "chat":      "price_chat",
    "challenge": "price_challenge",
    "report":    "price_report",
    "trends":    "price_trends",
    "help":      "price_help",
    "interview_sim": "price_interview_sim",
    "twin":      "price_twin",
}

ACTION_LABEL = {
    "roadmap":   "تولید نقشه راه",
    "chat":      "چت با منتور",
    "challenge": "تصحیح چالش",
    "report":    "گزارش آمادگی شغلی",
    "trends":    "مشاهدهٔ ترندها",
    "help":      "کمک حین آموزش",
    "interview_sim": "شبیه‌ساز مصاحبه",
    "twin":      "شبیه‌سازی همزاد شغلی",
}


# ========================= اعتبار =========================

def get_action_price(action_type: str) -> int:
    return ai_db.get_ai_setting_int(ACTION_PRICE_KEY.get(action_type, ""), 0)


def get_user_ai_balance(user_id: int) -> int:
    """موجودی اعتبار کاربر از سیستم credits موجود."""
    u = USERS.get(str(user_id))
    if not u:
        return 0
    try:
        return int(u.get("credits", 0) or 0)
    except Exception:
        return 0


def free_quota_left(user_id: int) -> int:
    """تعامل‌های رایگان باقی‌مانده (onboarding)."""
    quota = ai_db.get_ai_setting_int("free_quota", 3)
    used = ai_db.user_usage_count(user_id)
    return max(0, quota - used)


def can_afford(user_id: int, action_type: str) -> tuple:
    """بررسی موجودی **بدون** کسر — برای فلوهای چندمرحله‌ای.

    اجازه می‌دهد پیش از شروع یک فلوی طولانی مطمئن شویم کاربر توان
    پرداخت دارد، ولی کسر واقعی تا لحظهٔ ارائهٔ خدمت به تعویق بیفتد.
    خروجی: (ok, price, message)
    """
    try:
        uid = int(user_id)
    except Exception:
        return False, 0, "شناسهٔ کاربر نامعتبر است."
    if uid in ADMIN_IDS:
        return True, 0, ""
    cost = get_action_price(action_type)
    if cost <= 0 or free_quota_left(uid) > 0:
        return True, cost, ""
    balance = get_user_ai_balance(uid)
    if balance < cost:
        return False, cost, (
            f"❌ اعتبار کافی ندارید.\n\n"
            f"💰 موجودی شما: {balance}\n"
            f"💳 هزینهٔ «{ACTION_LABEL.get(action_type, action_type)}»: {cost}\n\n"
            f"برای ادامه، اعتبار خود را شارژ کنید."
        )
    return True, cost, ""


def refund(user_id: int, amount: int, reason: str = "") -> bool:
    """بازگرداندن اعتبار کسرشده — وقتی خدمت ارائه نشد.

    در سه حالت استفاده می‌شود: خطای AI، انصراف کاربر وسط فلو، یا
    ناتمام‌ماندن عملیات. اگر amount صفر باشد (رایگان یا ادمین) کاری
    نمی‌کند، پس فراخوانی بی‌مورد ضرری ندارد.
    """
    try:
        amount = int(amount or 0)
    except Exception:
        return False
    if amount <= 0:
        return False
    try:
        change_credits(int(user_id), amount)
        ai_db.log_ai_usage(int(user_id), f"refund:{reason or '-'}", -amount, "")
        logger.info(f"refund {amount} به کاربر {user_id} ({reason})")
        return True
    except Exception as e:
        logger.error(f"refund ناموفق ({user_id}, {amount}): {e}")
        return False


def check_and_deduct_credits(user_id: int, action_type: str) -> tuple:
    """
    بررسی و کسر اعتبار.
    خروجی: (ok: bool, cost: int, message: str)

    ترتیب بررسی:
      ۱. ادمین → همیشه رایگان
      ۲. تعرفهٔ صفر → رایگان
      ۳. سهمیهٔ رایگان اولیه → رایگان
      ۴. موجودی کافی → کسر و ادامه
      ۵. در غیر این صورت → رد با پیام شارژ
    """
    try:
        uid = int(user_id)
    except Exception:
        return False, 0, "شناسهٔ کاربر نامعتبر است."

    if uid in ADMIN_IDS:
        return True, 0, ""

    cost = get_action_price(action_type)
    if cost <= 0:
        return True, 0, ""

    if free_quota_left(uid) > 0:
        left = free_quota_left(uid) - 1
        return True, 0, f"🎁 این مورد رایگان بود ({left} تعامل رایگان باقی مانده)."

    balance = get_user_ai_balance(uid)
    if balance < cost:
        return False, cost, (
            f"❌ اعتبار کافی ندارید.\n\n"
            f"💰 موجودی شما: {balance}\n"
            f"💳 هزینهٔ «{ACTION_LABEL.get(action_type, action_type)}»: {cost}\n\n"
            f"برای ادامه، اعتبار خود را شارژ کنید."
        )

    # کسر از سیستم credits موجود
    change_credits(uid, -cost)
    return True, cost, ""


# ========================= کمکی JSON =========================

def _extract_json(text: str):
    """
    استخراج JSON از پاسخ مدل.
    مدل‌ها اغلب JSON را داخل ```json ... ``` یا همراه متن اضافه می‌فرستند.
    """
    if not text:
        return None
    t = text.strip()

    # حذف بلوک کد
    if "```" in t:
        m = re.search(r"```(?:json)?\s*(.+?)```", t, re.S)
        if m:
            t = m.group(1).strip()

    try:
        return json.loads(t)
    except Exception:
        pass

    # اولین شیء/آرایهٔ متوازن
    for opener, closer in (("{", "}"), ("[", "]")):
        start = t.find(opener)
        if start == -1:
            continue
        depth = 0
        for i in range(start, len(t)):
            if t[i] == opener:
                depth += 1
            elif t[i] == closer:
                depth -= 1
                if depth == 0:
                    try:
                        return json.loads(t[start:i + 1])
                    except Exception:
                        break
    return None


def _split_spec(spec: str):
    """«پروایدر:مدل» → (provider, model).

    اگر جداکننده نبود، نام پروایدر از روی متن حدس زده می‌شود
    (مثلاً «groq-llama-3.1-8b» → Groq) تا مقادیر دستیِ ادمین هم کار کنند.
    """
    spec = (spec or "").strip()
    if not spec:
        return "", ""
    if ":" in spec:
        p, m = spec.split(":", 1)
        return p.strip(), m.strip()
    low = spec.lower()
    for prov in ("Groq", "OpenRouter", "LLM7", "Cloudflare", "GapGPT", "AvalAI"):
        if prov.lower() in low:
            return prov, spec[len(prov):].lstrip("-_: ").strip()
    return "", spec


async def route_ai_request(action_type: str, messages: list,
                           max_tokens: int = 1400, user_id: int = 0,
                           **kwargs) -> dict:
    """مسیریابی هوشمند: مدل ارزان برای کار ساده، مدل قوی برای کار سنگین.

    ترتیب تلاش:
      ۱. مدل انتخابیِ ادمین در «تنظیمات هسته» (اگر ست شده باشد) — بالاترین اولویت
      ۲. primary_model همان اکشن از جدول ai_model_routing
      ۳. fallback_models به ترتیب
      ۴. ask_ai_fast (انتخاب خودکار بین همهٔ پروایدرهای فعال)

    هزینهٔ تقریبی در ai_usage_logs ثبت می‌شود.
    """
    tried = []

    # ۱) اگر ادمین صراحتاً مدل تعیین کرده، همان اولویت دارد
    override = (ai_db.get_ai_setting("model", "") or "").strip()
    if override:
        tried.append(override)

    route = ai_db.get_model_routing(action_type)
    if route and route.get("is_active"):
        if route.get("primary_model"):
            tried.append(route["primary_model"])
        for fb in route.get("fallback_models") or []:
            if fb:
                tried.append(fb)

    last_error = ""
    for spec in tried:
        provider, model = _split_spec(spec)
        if not provider:
            continue
        try:
            res = await ask_ai(provider, messages, model=model or None,
                               max_tokens=max_tokens)
        except Exception as e:
            last_error = str(e)
            logger.warning(f"route[{action_type}] {spec} استثنا: {e}")
            continue
        if res.get("ok"):
            _log_route_cost(user_id, action_type, route, res.get("model", ""))
            return res
        last_error = res.get("error", "")
        logger.info(f"route[{action_type}] {spec} ناموفق: {last_error}")

    # ۴) آخرین تلاش — انتخاب خودکار
    res = await ask_ai_fast(messages, max_tokens=max_tokens)
    if res.get("ok"):
        _log_route_cost(user_id, action_type, route, res.get("model", ""))
        return res
    if last_error and not res.get("error"):
        res["error"] = last_error
    return res


def _log_route_cost(user_id: int, action_type: str, route, model: str) -> None:
    """ثبت هزینهٔ تقریبی (بر حسب ۰٫۰۰۰۱ دلار) در ai_usage_logs."""
    try:
        cost = float((route or {}).get("cost_per_request") or 0)
        ai_db.log_ai_usage(int(user_id or 0), f"ai_{action_type}",
                           int(round(cost * 10000)), model or "")
    except Exception as e:
        logger.debug(f"_log_route_cost: {e}")


async def _ask(system_prompt: str, user_content: str, max_tokens: int = 1400,
               action_type: str = "", user_id: int = 0) -> dict:
    """فراخوانی AI — حالا از مسیریاب هوشمند عبور می‌کند."""
    custom = (ai_db.get_ai_setting("system_prompt", "") or "").strip()
    if custom:
        system_prompt = f"{system_prompt}\n\n{custom}"

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_content},
    ]

    if action_type:
        return await route_ai_request(action_type, messages,
                                      max_tokens=max_tokens, user_id=user_id)

    # سازگاری عقب‌رو — رفتار قبلی برای فراخوانی‌های بدون action_type
    model = (ai_db.get_ai_setting("model", "") or "").strip()
    if model and ":" in model:
        provider, mdl = model.split(":", 1)
        res = await ask_ai(provider.strip(), messages, model=mdl.strip() or None,
                           max_tokens=max_tokens)
        if res.get("ok"):
            return res
        logger.warning("پروایدر انتخابی ادمین ناموفق بود، بازگشت به حالت خودکار.")
    return await ask_ai_fast(messages, model=model or None, max_tokens=max_tokens)


# ========================= تولید محتوا با AI =========================
# ⚠️ فلوی «شروع مسیر جدید» به معماری چندعاملی منتقل شده است:
#     ایجنت ۱ → ai_mentor/agents/career_interview.py  (مصاحبه و انتخاب مسیر)
#     ایجنت ۲ → ai_mentor/agents/roadmap_builder.py   (اسکلت نقشه راه)
#     ایجنت ۳ → ai_mentor/agents/learning_mentor.py   (محتوای گام + داوری)
# پرامپت هر ایجنت در ai_mentor/prompts/*.txt است، نه در کد.
# توابع قدیمیِ این بخش (generate_ai_interview، build_persona،
# generate_roadmap، generate_lesson_content، update_learning_profile و
# _legacy_generate_roadmap) حذف شدند.


def _now_str() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


async def evaluate_challenge(challenge_text: str, user_answer: str,
                             user_age: int = 0) -> dict:
    """تصحیح پاسخ کاربر به یک چالش (سن برای تنظیم لحن اختیاری است)."""
    payload = f"صورت چالش:\n{challenge_text}\n\nپاسخ کاربر:\n{user_answer}"
    if user_age:
        payload += f"\n\nسن کاربر: {user_age} سال"
    res = await _ask(AI_MENTOR_PROMPT, payload, 900, "challenge")
    if not res.get("ok"):
        return {"ok": False, "error": res.get("error", "خطای نامشخص")}

    data = _extract_json(res.get("text", "")) or {}
    status = (data.get("status") or "").strip().lower()
    if status not in ("pass", "fail"):
        status = "fail"
    try:
        xp = int(data.get("xp_reward") or 0)
    except Exception:
        xp = 0
    return {
        "ok": True,
        "status": status,
        "feedback": (data.get("feedback") or "").strip() or "پاسخ شما بررسی شد.",
        "hint": (data.get("hint") or "").strip(),
        "xp_reward": max(0, min(xp, 50)) if status == "pass" else 0,
        "model": res.get("model", ""),
    }


async def generate_career_report(user_id: int) -> dict:
    """گزارش آمادگی شغلی بر اساس پیشرفت واقعی کاربر."""
    path = ai_db.get_active_path(user_id)
    if not path:
        return {"ok": False, "error": "هیچ مسیر فعالی ندارید."}

    steps = ai_db.get_path_steps(path["id"])
    done, total = ai_db.path_progress(path["id"])
    lines = []
    for s in steps:
        fb = s.get("ai_feedback") or {}
        mark = "✅" if s["status"] == "completed" else "⬜"
        note = (fb.get("feedback") or "")[:120]
        lines.append(f"{mark} گام {s['step_number']}: {s['title']} — {note}")

    payload = (
        f"شغل هدف: {path.get('target_job', '')}\n"
        f"پیشرفت: {done} از {total} گام\n\n"
        f"جزئیات گام‌ها:\n" + "\n".join(lines)
    )
    res = await _ask(AI_CAREER_REPORT_PROMPT, payload, 1400, "report")
    if not res.get("ok"):
        return {"ok": False, "error": res.get("error", "خطای نامشخص")}

    data = _extract_json(res.get("text", "")) or {}
    try:
        pct = int(data.get("readiness_percent") or 0)
    except Exception:
        pct = 0
    return {
        "ok": True,
        "readiness_percent": max(0, min(pct, 100)),
        "strengths": data.get("strengths") or [],
        "weaknesses": data.get("weaknesses") or [],
        "recommendations": data.get("recommendations") or [],
        "summary": (data.get("summary") or "").strip(),
        "model": res.get("model", ""),
    }


async def chat_with_mentor(user_text: str) -> dict:
    """پاسخ آزاد منتور (خروجی متن ساده، نه JSON)."""
    res = await _ask(AI_CHAT_MENTOR_PROMPT, user_text, 700, "chat")
    if not res.get("ok"):
        return {"ok": False, "error": res.get("error", "خطای نامشخص")}
    return {"ok": True, "text": (res.get("text") or "").strip(), "model": res.get("model", "")}


async def chat_with_mentor_context(user_id: int, step_id: int,
                                   user_text: str) -> dict:
    """چت آگاه‌از‌زمینه (فاز ۲): تاریخچهٔ همان گام به مدل داده می‌شود."""
    step = ai_db.get_step(step_id) if step_id else None
    path = ai_db.get_active_path(user_id)
    hist = ai_db.get_chat_history(user_id, path["id"] if path else 0, step_id, 10)

    hist_txt = "\n".join(
        f"{'کاربر' if h['role'] == 'user' else 'منتور'}: {h['content'][:250]}"
        for h in hist
    ) or "(این اولین پیام است)"

    content = (step or {}).get("content") or {}
    prompt = (AI_CHAT_MENTOR_WITH_CONTEXT
              .replace("{step_number}", str((step or {}).get("step_number", "—")))
              .replace("{step_title}", str((step or {}).get("title", "—")))
              .replace("{target_job}", str((path or {}).get("target_job", "—")))
              .replace("{step_desc}",
                       (content.get("description") or content.get("challenge") or "—")[:400])
              .replace("{chat_history}", hist_txt))

    res = await _ask(prompt, user_text, 700, "chat", user_id)
    if not res.get("ok"):
        return {"ok": False, "error": res.get("error", "خطای نامشخص")}

    answer = (res.get("text") or "").strip()
    pid = path["id"] if path else 0
    ai_db.save_chat_message(user_id, pid, step_id, "user", user_text)
    ai_db.save_chat_message(user_id, pid, step_id, "assistant", answer)
    return {"ok": True, "text": answer, "model": res.get("model", "")}


def add_trend_to_path(user_id: int, skill_name: str) -> dict:
    """افزودن یک مهارت ترند به مسیر کاربر (فاز ۲).

    اگر مسیر فعال دارد → گام جدید در انتهای مسیر.
    اگر ندارد → مسیر تازه‌ای بر پایهٔ همان مهارت ساخته می‌شود.
    خروجی: {ok, created, step_number, error}
    """
    skill = (skill_name or "").strip()
    if not skill:
        return {"ok": False, "error": "نام مهارت خالی است."}

    trend = None
    for t in ai_db.get_trending_skills(50):
        if t["skill_name"] == skill:
            trend = t
            break
    reason = (trend or {}).get("reason") or ""

    path = ai_db.get_active_path(user_id)
    created = False
    if not path:
        pid = ai_db.save_career_path(
            user_id, f"تسلط بر {skill}",
            {"target_job": f"تسلط بر {skill}", "source": "trend"},
        )
        if not pid:
            return {"ok": False, "error": "ساخت مسیر ناموفق بود."}
        created = True
        path = ai_db.get_active_path(user_id)
    pid = path["id"]

    steps = ai_db.get_path_steps(pid)
    # جلوگیری از افزودن تکراری
    if any((s.get("title") or "").strip() == f"یادگیری {skill}" for s in steps):
        return {"ok": False, "error": "این مهارت قبلاً به مسیر شما اضافه شده است."}

    num = (max((s["step_number"] for s in steps), default=0)) + 1
    # اگر مسیر تازه ساخته شده، گام اول باید فعال باشد
    status = "active" if (created or not steps) else "locked"
    sid = ai_db.save_path_step(
        pid, num, "ai_challenge", f"یادگیری {skill}",
        {
            "description": (f"این مهارت جزو پرتقاضاترین‌های بازار است. {reason}").strip(),
            "challenge": (
                f"یک تمرین عملی کوچک با «{skill}» انجام بده و خلاصهٔ کارت را "
                f"همین‌جا بنویس (چه ساختی، چه چالشی داشتی)."
            ),
            "course_id": "",
            "estimated_days": 7,
            "from_trend": skill,
        },
        status=status,
    )
    if not sid:
        return {"ok": False, "error": "افزودن گام ناموفق بود."}
    return {"ok": True, "created": created, "step_number": num, "step_id": sid}


# ========================= فاز ۳: گزارش آمادگی برای یک مسیر =========================

async def generate_career_readiness_report(user_id: int, path_id: int) -> dict:
    """گزارش آمادگی شغلی برای یک مسیر مشخص (نه فقط مسیر فعال)."""
    path = ai_db.get_path(path_id)
    if not path or int(path.get("user_id", 0)) != int(user_id):
        return {"ok": False, "error": "این مسیر پیدا نشد."}

    steps = ai_db.get_path_steps(path_id)
    done, total = ai_db.path_progress(path_id)

    lines = []
    for s in steps:
        fb = s.get("ai_feedback") or {}
        mark = "✅" if s["status"] == "completed" else "⬜"
        note = (fb.get("feedback") or "")[:140]
        xp = fb.get("xp_reward")
        lines.append(
            f"{mark} گام {s['step_number']}: {s['title']}"
            + (f" | نمره: {xp}" if xp else "")
            + (f" | بازخورد: {note}" if note else "")
        )
        # تاریخچهٔ کمک‌خواهی نشانهٔ نقاط ضعف است
        hist = ai_db.get_chat_history(user_id, path_id, s["id"], 4)
        for h in hist:
            if h["role"] == "user":
                lines.append(f"    ❓ سؤال کاربر: {h['content'][:110]}")

    prof = ai_db.get_user_profile(user_id) or {}
    payload = (
        f"شغل هدف: {path.get('target_job', '')}\n"
        f"پیشرفت: {done} از {total} گام\n"
        + (f"سن: {prof['age']}\n" if prof.get("age") else "")
        + (f"شهر: {prof['city']}\n" if prof.get("city") else "")
        + "\nجزئیات گام‌ها:\n" + "\n".join(lines)
    )

    res = await _ask(AI_CAREER_REPORT_PROMPT, payload, 1400, "report", user_id)
    if not res.get("ok"):
        return {"ok": False, "error": res.get("error", "خطای نامشخص")}

    data = _extract_json(res.get("text", "")) or {}
    try:
        pct = int(data.get("readiness_percent") or 0)
    except Exception:
        pct = 0
    pct = max(0, min(pct, 100))

    out = {
        "ok": True,
        "readiness_percent": pct,
        "strengths": data.get("strengths") or [],
        "weaknesses": data.get("weaknesses") or [],
        "recommendations": data.get("recommendations") or [],
        "summary": (data.get("summary") or "").strip(),
        "target_job": path.get("target_job", ""),
        "model": res.get("model", ""),
    }
    out["report_id"] = ai_db.save_career_report(
        user_id, path_id, path.get("target_job", ""), pct, out)
    return out


# ========================= فاز ۳: گواهینامهٔ PDF =========================

_FONT_CANDIDATES = (
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/truetype/freefont/FreeSans.ttf",
    "/Library/Fonts/Arial Unicode.ttf",
)


def _find_font():
    for p in _FONT_CANDIDATES:
        if os.path.exists(p):
            return p
    return None


def new_certificate_id() -> str:
    return f"CERT-{secrets.token_hex(4).upper()}"


def certificates_dir() -> str:
    d = os.path.join("data", "certificates")
    os.makedirs(d, exist_ok=True)
    return d


def generate_certificate_pdf(user_id: int, path_id: int,
                             certificate_id: str, readiness: int = 0) -> dict:
    """ساخت PDF گواهینامه با QR Code.

    خروجی: {ok, file_path, error}
    اگر fpdf2/qrcode نصب نباشند یا فونت یونیکد پیدا نشود، ok=False برمی‌گردد
    و بقیهٔ ربات بدون مشکل ادامه می‌دهد.
    """
    try:
        from fpdf import FPDF
    except ImportError:
        return {"ok": False, "error": "کتابخانهٔ fpdf2 نصب نیست."}

    path = ai_db.get_path(path_id)
    if not path:
        return {"ok": False, "error": "مسیر پیدا نشد."}

    font_path = _find_font()
    if not font_path:
        return {"ok": False, "error": "فونت یونیکد روی سرور پیدا نشد."}

    prof = ai_db.get_user_profile(user_id) or {}
    full_name = " ".join(
        x for x in (prof.get("first_name", ""), prof.get("last_name", "")) if x
    ).strip() or str(user_id)

    done, total = ai_db.path_progress(path_id)
    out_path = os.path.join(certificates_dir(), f"{certificate_id}.pdf")
    qr_path = ""

    try:
        pdf = FPDF(orientation="L", unit="mm", format="A4")
        pdf.add_font("U", "", font_path)
        pdf.add_page()
        pdf.set_auto_page_break(False)

        # قاب تزیینی
        pdf.set_draw_color(40, 90, 160)
        pdf.set_line_width(1.6)
        pdf.rect(10, 10, 277, 190)
        pdf.set_line_width(0.4)
        pdf.rect(14, 14, 269, 182)

        pdf.set_font("U", size=30)
        pdf.set_text_color(20, 60, 120)
        pdf.set_xy(0, 32)
        pdf.cell(297, 14, _rtl("گواهینامهٔ تکمیل مسیر یادگیری"), align="C")

        pdf.set_font("U", size=13)
        pdf.set_text_color(70, 70, 70)
        pdf.set_xy(0, 52)
        pdf.cell(297, 8, _rtl("این گواهی صادر می‌شود برای"), align="C")

        pdf.set_font("U", size=24)
        pdf.set_text_color(0, 0, 0)
        pdf.set_xy(0, 66)
        pdf.cell(297, 12, _rtl(full_name), align="C")

        pdf.set_font("U", size=13)
        pdf.set_text_color(70, 70, 70)
        pdf.set_xy(0, 86)
        pdf.cell(297, 8, _rtl("بابت تکمیل موفقیت‌آمیز مسیر"), align="C")

        pdf.set_font("U", size=18)
        pdf.set_text_color(20, 60, 120)
        pdf.set_xy(0, 98)
        pdf.cell(297, 10, _rtl(path.get("target_job", "")), align="C")

        pdf.set_font("U", size=12)
        pdf.set_text_color(50, 50, 50)
        pdf.set_xy(0, 118)
        pdf.cell(297, 8, _rtl(
            f"گام‌های تکمیل‌شده: {done} از {total}"
            + (f"   |   آمادگی شغلی: {readiness}٪" if readiness else "")
        ), align="C")

        pdf.set_xy(0, 130)
        pdf.cell(297, 8, _rtl(f"تاریخ صدور: {ai_db._now()[:10]}"), align="C")

        # QR Code — شامل شناسهٔ یکتا برای استعلام
        try:
            import qrcode
            qr_path = os.path.join(certificates_dir(), f"{certificate_id}.png")
            qrcode.make(f"{certificate_id}|user:{user_id}|path:{path_id}").save(qr_path)
            pdf.image(qr_path, x=246, y=143, w=32)
        except Exception as e:
            logger.info(f"QR ساخته نشد (گواهینامه بدون QR): {e}")

        pdf.set_font("U", size=11)
        pdf.set_text_color(90, 90, 90)
        pdf.set_xy(18, 172)
        pdf.cell(120, 7, f"{certificate_id}", align="L")
        pdf.set_xy(18, 180)
        pdf.cell(120, 7, _rtl("ربات آموزشی صادقی"), align="L")

        pdf.output(out_path)
    except Exception as e:
        logger.error(f"generate_certificate_pdf: {e}", exc_info=True)
        return {"ok": False, "error": f"ساخت PDF ناموفق بود: {e}"}
    finally:
        if qr_path and os.path.exists(qr_path):
            try:
                os.remove(qr_path)
            except Exception:
                pass

    return {"ok": True, "file_path": out_path}


def _rtl(text: str) -> str:
    """آماده‌سازی متن فارسی برای PDF.

    fpdf2 شکل‌دهی (shaping) و ترتیب راست‌به‌چپ را خودکار انجام نمی‌دهد.
    اگر arabic_reshaper و python-bidi نصب باشند استفاده می‌شوند؛ در غیر
    این صورت متن خام برگردانده می‌شود (خوانا ولی بدون اتصال حروف).
    """
    try:
        import arabic_reshaper
        from bidi.algorithm import get_display
        return get_display(arabic_reshaper.reshape(text))
    except Exception:
        return text


def issue_certificate(user_id: int, path_id: int, readiness: int = 0) -> dict:
    """صدور گواهینامه — اگر قبلاً صادر شده باشد همان برگردانده می‌شود."""
    existing = ai_db.get_certificate_for_path(user_id, path_id)
    if existing and existing.get("file_path") and os.path.exists(existing["file_path"]):
        return {"ok": True, "file_path": existing["file_path"],
                "certificate_id": existing["certificate_id"], "existing": True}

    cid = (existing or {}).get("certificate_id") or new_certificate_id()
    res = generate_certificate_pdf(user_id, path_id, cid, readiness)
    if not res.get("ok"):
        return res

    path = ai_db.get_path(path_id) or {}
    if not existing:
        ai_db.save_certificate(user_id, path_id, cid,
                               path.get("target_job", ""), readiness,
                               res["file_path"])
    return {"ok": True, "file_path": res["file_path"],
            "certificate_id": cid, "existing": False}


# ========================= فاز ۳: شبیه‌ساز مصاحبه =========================

async def start_interview_simulation(user_id: int, target_job: str) -> dict:
    """تولید ۱۰ سؤال مصاحبه و ساخت یک جلسهٔ جدید."""
    res = await _ask(
        AI_INTERVIEW_SIMULATOR_PROMPT.replace("{target_job}", target_job),
        f"موقعیت شغلی: {target_job}", 1600, "interview", user_id)
    if not res.get("ok"):
        return {"ok": False, "error": res.get("error", "خطای نامشخص")}

    data = _extract_json(res.get("text", "")) or {}
    raw = data.get("questions") or []
    qs = []
    for i, q in enumerate(raw[:10], 1):
        if isinstance(q, dict) and (q.get("text") or "").strip():
            qs.append({"n": i,
                       "kind": q.get("kind") if q.get("kind") in
                               ("technical", "behavioral") else "technical",
                       "text": q["text"].strip()[:400]})
        elif isinstance(q, str) and q.strip():
            qs.append({"n": i, "kind": "technical", "text": q.strip()[:400]})
    if len(qs) < 3:
        return {"ok": False, "error": "تولید سؤالات مصاحبه ناموفق بود."}

    sim_id = ai_db.create_simulation(user_id, target_job, qs)
    if not sim_id:
        return {"ok": False, "error": "ساخت جلسهٔ مصاحبه ناموفق بود."}
    return {"ok": True, "sim_id": sim_id, "questions": qs,
            "total": len(qs), "model": res.get("model", "")}


async def grade_interview_simulation(sim_id: int) -> dict:
    """نمره‌دهی همهٔ پاسخ‌ها در یک فراخوانی (به‌جای ۱۰ فراخوانی = صرفه‌جویی)."""
    sim = ai_db.get_simulation(sim_id)
    if not sim:
        return {"ok": False, "error": "جلسهٔ مصاحبه پیدا نشد."}

    pairs = sim["scores_json"]
    if not pairs:
        return {"ok": False, "error": "هیچ پاسخی ثبت نشده است."}

    body = "\n\n".join(
        f"سؤال {i}: {p.get('q', '')}\nپاسخ: {p.get('a', '') or '(بدون پاسخ)'}"
        for i, p in enumerate(pairs, 1)
    )
    res = await _ask(
        AI_INTERVIEW_GRADER_PROMPT.replace("{target_job}", sim.get("target_job", "")),
        body, 1800, "report", sim["user_id"])
    if not res.get("ok"):
        return {"ok": False, "error": res.get("error", "خطای نامشخص")}

    data = _extract_json(res.get("text", "")) or {}
    try:
        total = int(data.get("total_score") or 0)
    except Exception:
        total = 0
    total = max(0, min(total, 100))

    report = {
        "total_score": total,
        "scores": data.get("scores") or [],
        "strengths": data.get("strengths") or [],
        "weaknesses": data.get("weaknesses") or [],
        "tips": data.get("tips") or [],
    }
    ai_db.finish_simulation(sim_id, total, report)
    return {"ok": True, **report, "model": res.get("model", "")}


# ========================= فاز ۳: همزاد شغلی =========================

async def simulate_career_twin(user_id: int, path_id: int = 0) -> dict:
    """شبیه‌سازی نتیجهٔ ارسال رزومه در ۵ موقعیت شغلی فرضی."""
    path = ai_db.get_path(path_id) if path_id else ai_db.get_active_path(user_id)
    if not path:
        return {"ok": False, "error": "برای شبیه‌سازی، اول یک مسیر بسازید."}

    steps = ai_db.get_path_steps(path["id"])
    done_titles = [s["title"] for s in steps if s["status"] == "completed"]
    pending = [s["title"] for s in steps if s["status"] != "completed"]
    dn, tt = ai_db.path_progress(path["id"])

    prof = ai_db.get_user_profile(user_id) or {}
    skills = (
        f"شغل هدف: {path.get('target_job', '')}\n"
        f"پیشرفت مسیر: {dn} از {tt} گام\n"
        + (f"سن: {prof['age']} | شهر: {prof['city']}\n"
           if prof.get("age") or prof.get("city") else "")
        + "مهارت‌های کسب‌شده: "
        + (", ".join(done_titles) if done_titles else "(هنوز گامی تکمیل نشده)")
        + "\nدر حال یادگیری: "
        + (", ".join(pending[:5]) if pending else "—")
    )
    trends = ai_db.get_trending_skills(8)
    market = "\n".join(
        f"- {t['skill_name']}: {t['demand_count']} آگهی" for t in trends
    ) or "(داده‌ای ثبت نشده)"

    res = await _ask(
        AI_CAREER_TWIN_PROMPT.replace("{user_skills}", skills)
                             .replace("{market_trends}", market),
        "شبیه‌سازی را انجام بده.", 1800, "report", user_id)
    if not res.get("ok"):
        return {"ok": False, "error": res.get("error", "خطای نامشخص")}

    data = _extract_json(res.get("text", "")) or {}
    jobs = []
    for j in (data.get("jobs") or [])[:5]:
        if not isinstance(j, dict):
            continue
        try:
            mp = int(j.get("match_percent") or 0)
        except Exception:
            mp = 0
        jobs.append({
            "title": (j.get("title") or "").strip()[:100],
            "company": (j.get("company") or "").strip()[:100],
            "result": "accepted" if (j.get("result") or "").strip().lower() == "accepted"
                      else "rejected",
            "match_percent": max(0, min(mp, 100)),
            "reason": (j.get("reason") or "").strip()[:400],
            "salary_range": (j.get("salary_range") or "").strip()[:80],
        })
    if not jobs:
        return {"ok": False, "error": "شبیه‌سازی نتیجه‌ای تولید نکرد."}

    out = {
        "ok": True, "jobs": jobs,
        "summary": (data.get("summary") or "").strip(),
        "next_skill": (data.get("next_skill") or "").strip(),
        "target_job": path.get("target_job", ""),
        "model": res.get("model", ""),
    }
    ai_db.save_career_twin(user_id, path["id"], out)
    return out


# ========================= فاز ۴: مأموریت‌های واقعی =========================

async def grade_real_mission(user_id: int, mission_id: int,
                             submission: str) -> dict:
    """تصحیح کار ارسالی با AI و در صورت قبولی، اعطای پاداش اعتباری.

    خروجی: {ok, status, grade, feedback, improvements, reward, error}
    """
    mission = ai_db.get_real_mission(mission_id)
    if not mission:
        return {"ok": False, "error": "مأموریت پیدا نشد."}
    if mission.get("status") != "active":
        return {"ok": False, "error": "این مأموریت دیگر فعال نیست."}

    prompt = (AI_MISSION_GRADER_PROMPT
              .replace("{mission_title}", mission.get("title", ""))
              .replace("{mission_desc}", (mission.get("description") or "")[:1200])
              .replace("{required_skills}",
                       ", ".join(mission.get("required_skills") or []) or "—")
              .replace("{submission}", (submission or "")[:3000]))

    res = await _ask(prompt, "این کار را داوری کن.", 1200, "challenge", user_id)
    if not res.get("ok"):
        return {"ok": False, "error": res.get("error", "خطای نامشخص")}

    data = _extract_json(res.get("text", "")) or {}
    try:
        grade = int(data.get("grade") or 0)
    except Exception:
        grade = 0
    grade = max(0, min(grade, 100))
    status = (data.get("status") or "").strip().lower()
    if status not in ("approved", "rejected"):
        status = "approved" if grade >= 60 else "rejected"
    # نمره و وضعیت باید سازگار بمانند
    if status == "approved" and grade < 60:
        status = "rejected"

    feedback = (data.get("feedback") or "").strip() or "کار شما بررسی شد."
    ai_db.submit_user_mission(user_id, mission_id, submission, status,
                              grade, feedback)

    reward = 0
    if status == "approved":
        reward = int(mission.get("reward_credits") or 0)
        if reward:
            try:
                change_credits(int(user_id), reward)
            except Exception as e:
                logger.error(f"پاداش مأموریت اعطا نشد: {e}")
                reward = 0
        ai_db.log_ai_usage(user_id, "real_mission", 0, res.get("model", ""))

    return {"ok": True, "status": status, "grade": grade, "feedback": feedback,
            "improvements": data.get("improvements") or [], "reward": reward,
            "model": res.get("model", "")}


# ========================= فاز ۴: یادگیری تیمی =========================

def suggest_or_create_team(user_id: int) -> dict:
    """پیوستن به تیمِ در حال تشکیلِ متناسب، یا ساخت تیم جدید.

    تطبیق بر پایهٔ شغل هدف (از career_paths) و شهر (از user_profiles).
    خروجی: {ok, team, created, error}
    """
    existing = ai_db.get_user_team(user_id)
    if existing:
        return {"ok": True, "team": existing, "created": False,
                "already": True}

    path = ai_db.get_active_path(user_id)
    prof = ai_db.get_user_profile(user_id) or {}
    target_job = (path or {}).get("target_job", "") or "مسیر عمومی"
    city = prof.get("city", "") or ""

    team = ai_db.find_forming_team(target_job, city)
    created = False
    if team is None:
        name = f"تیم {target_job}"[:100]
        desc = (f"پروژهٔ گروهی برای «{target_job}»"
                + (f" — {city}" if city else ""))
        tid = ai_db.create_team(name, desc, target_job, city, 4)
        if not tid:
            return {"ok": False, "error": "ساخت تیم ناموفق بود."}
        team = ai_db.get_team(tid)
        created = True

    role = "leader" if created else "member"
    if not ai_db.add_team_member(team["id"], user_id, role):
        return {"ok": False, "error": "ظرفیت این تیم پر شده است. دوباره تلاش کنید."}

    return {"ok": True, "team": ai_db.get_team(team["id"]),
            "created": created, "already": False}


async def team_progress_feedback(team_id: int) -> dict:
    """بازخورد AI دربارهٔ پیشرفت تیم."""
    team = ai_db.get_team(team_id)
    if not team:
        return {"ok": False, "error": "تیم پیدا نشد."}

    members = ai_db.get_team_members(team_id)
    lines = []
    for m in members:
        uid = m["user_id"]
        prof = ai_db.get_user_profile(uid) or {}
        nm = (prof.get("first_name") or str(uid))
        p = ai_db.get_active_path(uid)
        if p:
            dn, tt = ai_db.path_progress(p["id"])
            lines.append(f"- {nm} ({m['role']}): {p.get('target_job', '')} — "
                         f"{dn} از {tt} گام")
        else:
            lines.append(f"- {nm} ({m['role']}): هنوز مسیری نساخته")

    prompt = (AI_TEAM_FEEDBACK_PROMPT
              .replace("{team_name}", team.get("team_name", ""))
              .replace("{project}", team.get("project_description", ""))
              .replace("{members}", "\n".join(lines) or "—"))

    res = await _ask(prompt, "بازخورد تیم را بنویس.", 900, "chat", 0)
    if not res.get("ok"):
        return {"ok": False, "error": res.get("error", "خطای نامشخص")}

    data = _extract_json(res.get("text", "")) or {}
    try:
        score = int(data.get("team_score") or 0)
    except Exception:
        score = 0
    return {"ok": True,
            "feedback": (data.get("feedback") or "").strip(),
            "next_steps": data.get("next_steps") or [],
            "team_score": max(0, min(score, 100)),
            "model": res.get("model", "")}


# ========================= فاز ۴: پروفایل عمومی =========================

def _collect_public_data(user_id: int) -> dict:
    """جمع‌آوری دادهٔ عمومیِ کاربر — مبنای خلاصهٔ کارفرمایی."""
    prof = ai_db.get_user_profile(user_id) or {}
    paths = ai_db.list_user_paths(user_id, 5)
    reports = ai_db.list_career_reports(user_id, None, 1)
    certs = ai_db.list_certificates(user_id, 5)
    missions = ai_db.approved_mission_titles(user_id)

    skills = []
    for p in paths:
        for s in ai_db.get_path_steps(p["id"]):
            if s["status"] == "completed":
                skills.append(s["title"])

    sims = [s for s in ai_db.list_simulations(user_id, 5)
            if s.get("status") == "finished"]
    best_sim = max((s.get("final_score", 0) for s in sims), default=0)

    return {
        "name": " ".join(x for x in (prof.get("first_name", ""),
                                     prof.get("last_name", "")) if x).strip(),
        "age": prof.get("age", 0),
        "city": prof.get("city", ""),
        "target_job": (paths[0]["target_job"] if paths else ""),
        "readiness": (reports[0]["readiness_percent"] if reports else 0),
        "skills": skills[:12],
        "missions": missions[:8],
        "certificates": [c["target_job"] for c in certs],
        "best_interview_score": best_sim,
    }


async def generate_public_summary(user_id: int) -> dict:
    """خلاصهٔ حرفه‌ای برای نمایش به کارفرما."""
    d = _collect_public_data(user_id)
    payload = (
        f"نام: {d['name'] or '—'}\n"
        + (f"سن: {d['age']}\n" if d["age"] else "")
        + (f"شهر: {d['city']}\n" if d["city"] else "")
        + f"مسیر شغلی: {d['target_job'] or '—'}\n"
        f"درصد آمادگی شغلی: {d['readiness']}٪\n"
        f"مهارت‌های کسب‌شده: {', '.join(d['skills']) or '—'}\n"
        f"پروژه‌های واقعی انجام‌شده: {', '.join(d['missions']) or '—'}\n"
        f"گواهینامه‌ها: {', '.join(d['certificates']) or '—'}\n"
        f"بهترین نمرهٔ شبیه‌ساز مصاحبه: {d['best_interview_score']}/۱۰۰"
    )
    res = await _ask(AI_PUBLIC_PROFILE_SUMMARY.replace("{user_data}", payload),
                     "خلاصه را بنویس.", 900, "report", user_id)
    if not res.get("ok"):
        return {"ok": False, "error": res.get("error", "خطای نامشخص"), "data": d}

    data = _extract_json(res.get("text", "")) or {}
    return {"ok": True, "data": d,
            "summary": (data.get("summary") or "").strip(),
            "key_skills": data.get("key_skills") or [],
            "highlight": (data.get("highlight") or "").strip(),
            "model": res.get("model", "")}


async def analyze_trends_with_ai(skills_payload: str) -> dict:
    """تحلیل ترندهای بازار با AI."""
    res = await _ask(AI_TREND_ANALYST_PROMPT, skills_payload, 1200, "trend")
    if not res.get("ok"):
        return {"ok": False, "error": res.get("error", "خطای نامشخص")}
    data = _extract_json(res.get("text", "")) or {}
    return {"ok": True, "trends": data.get("trends") or [], "model": res.get("model", "")}


# ========================= پاداش =========================

def grant_challenge_reward(user_id: int, xp: int) -> None:
    """اعطای XP پس از قبولی در چالش — از سیستم XP موجود."""
    if xp <= 0:
        return
    try:
        award_xp_and_credits(int(user_id), xp_amount=int(xp), credits_amount=0)
    except Exception as e:
        logger.error(f"grant_challenge_reward: {e}")
