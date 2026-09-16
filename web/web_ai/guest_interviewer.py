# -*- coding: utf-8 -*-
"""
web/web_ai/guest_interviewer.py
فانل عارضه‌یابی مهمان — پروفایل یک‌پیامی + سؤال‌های تطبیقی AI

هدف:
  1) گرفتن نام، سن و شهر در یک پیام
  2) پرسیدن فقط فیلدهای جاافتاده
  3) پرسیدن ۳ تا ۵ سؤال تشخیصی تطبیقی
  4) یک سؤال شفاف‌سازی در صورت تناقض
"""
import json
import logging
import re
from pathlib import Path
from typing import List, Dict, Any, Tuple
from .ai_engine import check_ai_status
from .ai_gateway import ask as ai_ask

logger = logging.getLogger("web.web_ai.guest_interviewer")

_PROMPTS_DIR = Path(__file__).resolve().parent / "prompts"
_PROMPT_CACHE: str = ""

MIN_DIAGNOSTIC_QUESTIONS = 3
MAX_DIAGNOSTIC_QUESTIONS = 5
PROFILE_FIELDS = ("name", "age", "city")

CORE_QUESTIONS = [
    {
        "question": "الان دقیقاً کجای مسیرتی و بزرگ‌ترین گیر یا مشکل فعلیت چیه؟",
        "chips": ["🎓 دانشجو و سردرگمم", "💼 شاغلم ولی راضی نیستم", "🆕 تازه‌کارم", "💸 دنبال درآمد سریع‌ترم"],
        "typing_hint": "مثل: دانشجو هستم، ۲ سال طراحی گرافیک کار کردم ولی درآمد ثابت ندارم.",
        "example": "مثل: دانشجو هستم، ۲ سال طراحی گرافیک کار کردم ولی درآمد ثابت ندارم.",
        "expected_topic": "وضعیت فعلی مسیر شغلی و مشکل اصلی کاربر",
        "part": "status",
        "layer": "تشخیص مسئله",
    },
    {
        "question": "اگر قرار باشه ۱۰ روز دیگه یک خروجی واقعی داشته باشی، دوست داری اون خروجی چی باشه؟",
        "chips": [],
        "typing_hint": "مثل: می‌خوام اولین مشتری واقعی برای طراحی پست اینستاگرام پیدا کنم.",
        "example": "مثل: می‌خوام اولین مشتری واقعی برای طراحی پست اینستاگرام پیدا کنم.",
        "expected_topic": "خروجی واقعی و قابل انجامی که کاربر می‌خواهد تا ۱۰ روز آینده بسازد",
        "part": "output",
        "layer": "علاقه و خروجی مطلوب",
    },
    {
        "question": "روزی چقدر زمان واقعی داری؟",
        "chips": ["روزی ۳۰ دقیقه", "روزی ۱ ساعت", "روزی ۲ ساعت", "روزی ۳ ساعت به بالا"],
        "typing_hint": "مثل: روزی ۱ ساعت",
        "example": "مثل: روزی ۱ ساعت",
        "expected_topic": "زمان روزانه واقعی که کاربر می‌تواند برای مسیرش بگذارد",
        "part": "time",
        "layer": "زمان در دسترس",
    },
    {
        "question": "با چه ابزار یا مهارتی راحت‌تری؟",
        "chips": ["📱 موبایل", "💻 لپ‌تاپ", "📱💻 هر دو", "🧰 هنوز ابزار خاصی ندارم"],
        "typing_hint": "مثل: موبایل + کمی تجربه طراحی",
        "example": "مثل: موبایل + کمی تجربه طراحی",
        "expected_topic": "ابزار یا مهارت فعلی کاربر برای شروع",
        "part": "tools",
        "layer": "ابزار و مهارت فعلی",
    },
]

OPTIONAL_QUESTIONS = [
    {
        "question": "برای شروع، کدوم امکانات رو داری؟ می‌تونی چندتا رو با هم انتخاب کنی یا خودت بنویسی.",
        "chips": ["📱 موبایل — برای طراحی پست، محتوا، مکالمه", "💻 لپ‌تاپ — برای کارهای حرفه‌ای، تدوین، کدنویسی", "🌐 اینترنت پایدار — برای کار آنلاین با مشتری", "🎨 نمونه‌کار قبلی — کاری که قبلاً انجام دادی"],
        "typing_hint": "مثل: فقط موبایل دارم.",
        "example": "مثل: فقط موبایل دارم.",
        "expected_topic": "امکانات شروع شامل موبایل، لپ‌تاپ، اینترنت پایدار یا نمونه‌کار قبلی",
        "input_type": "multi_select",
        "layer": "امکانات شروع",
    },
    {
        "question": "ترجیح می‌دی اولین خروجی‌ات برای استخدام، فریلنسری، فروش خدمت، یا فقط تست علاقه باشه؟",
        "chips": ["🏢 استخدام", "🧑‍💻 فریلنسری", "🛍 فروش خدمت", "🧪 تست علاقه"],
        "typing_hint": "اگر هدفت چیز دیگری است آزاد بنویس",
        "layer": "هدف خروجی اول",
    },
]


def _load_prompt() -> str:
    global _PROMPT_CACHE
    if _PROMPT_CACHE:
        return _PROMPT_CACHE
    p_file = _PROMPTS_DIR / "interviewer.txt"
    try:
        if p_file.exists():
            _PROMPT_CACHE = p_file.read_text(encoding="utf-8").strip()
            return _PROMPT_CACHE
    except Exception as e:
        logger.warning("guest_interviewer load prompt error: %s", e)
    return "تو مشاور شغلی هوشمند sadeghiai هستی. فقط سؤال‌های کوتاه، دقیق و فارسی بپرس."


def _load_prompt_file(name: str) -> str:
    try:
        p_file = _PROMPTS_DIR / name
        if p_file.exists():
            return p_file.read_text(encoding="utf-8").strip()
    except Exception as e:
        logger.warning("guest_interviewer load %s error: %s", name, e)
    return ""


def _user_texts(messages: List[Dict[str, str]]) -> List[str]:
    return [
        (m.get("text") or m.get("content") or "").strip()
        for m in messages if m.get("role") == "user"
    ]


def _parse_json(raw: str) -> Dict[str, Any] | None:
    if not raw:
        return None
    try:
        s = raw.strip()
        if "```json" in s:
            s = s.split("```json", 1)[1].split("```", 1)[0].strip()
        elif "```" in s:
            s = s.split("```", 1)[1].split("```", 1)[0].strip()
        start = s.find("{")
        end = s.rfind("}")
        if start != -1 and end != -1:
            s = s[start:end + 1]
        return json.loads(s)
    except Exception as e:
        logger.info("guest_interviewer json parse failed: %s", e)
        return None


def _fallback_profile_extract(text: str) -> Dict[str, str]:
    clean = (text or "").strip()
    profile = {"name": "", "age": "", "city": ""}

    age_match = re.search(r"(\d{1,2}|[۰-۹]{1,2})\s*(?:ساله|سال)?", clean)
    if age_match:
        profile["age"] = age_match.group(1)

    known_cities = ["تهران", "مشهد", "اصفهان", "شیراز", "تبریز", "کرج", "قم", "اهواز", "رشت", "کرمان", "یزد", "ارومیه"]
    for city in known_cities:
        if city in clean:
            profile["city"] = city
            break

    # حذف سن/شهر/کلمات رایج برای حدس اسم
    name_candidate = clean
    if profile["age"]:
        name_candidate = re.sub(rf"{re.escape(profile['age'])}\s*(?:ساله|سال)?", " ", name_candidate)
    if profile["city"]:
        name_candidate = name_candidate.replace(profile["city"], " ")
    for word in ("من", "هستم", "اسمم", "نامم", "از", "ساکن", "توی", "در", "و", "،", ","):
        name_candidate = name_candidate.replace(word, " ")
    parts = [p for p in name_candidate.split() if len(p) > 1]
    if parts:
        profile["name"] = parts[0]
    return profile


def _extract_profile_ai(text: str, base_prompt: str, has_ai: bool) -> Dict[str, str]:
    fallback = _fallback_profile_extract(text)
    if not has_ai:
        return fallback
    prompt = f"""{base_prompt}

از متن زیر فقط نام، سن و شهر کاربر را استخراج کن.
اگر موردی نبود مقدارش رشته خالی باشد.
خروجی فقط JSON معتبر باشد:
{{"name":"...","age":"...","city":"..."}}

متن کاربر:
{text}
"""
    raw = ai_ask(prompt, max_tokens=180)
    parsed = _parse_json(raw)
    if not isinstance(parsed, dict):
        return fallback
    return {
        "name": str(parsed.get("name") or fallback.get("name") or "").strip(),
        "age": str(parsed.get("age") or fallback.get("age") or "").strip(),
        "city": str(parsed.get("city") or fallback.get("city") or "").strip(),
    }


def _profile_from_texts(texts: List[str], base_prompt: str, has_ai: bool) -> Tuple[Dict[str, str], int]:
    """تا وقتی پروفایل کامل شود، پیام‌های اول کاربر را برای تکمیل name/age/city مصرف می‌کند."""
    profile = {"name": "", "age": "", "city": ""}
    consumed = 0
    buffer: List[str] = []
    for idx, text in enumerate(texts):
        buffer.append(text)
        extracted = _extract_profile_ai("\n".join(buffer), base_prompt, has_ai)
        for key in PROFILE_FIELDS:
            if extracted.get(key):
                profile[key] = extracted[key]
        consumed = idx + 1
        if all(profile.values()):
            return profile, consumed
    return profile, consumed


def _missing_profile_question(missing: List[str]) -> str:
    labels = {"name": "اسمت", "age": "سنت", "city": "شهرت"}
    first = missing[0] if missing else "name"
    return f"فقط {labels[first]} رو هم بگو تا بریم جلو 🌟"


def _detect_contradiction(adaptive_answers: List[str], base_prompt: str, has_ai: bool) -> Dict[str, Any]:
    joined = "\n".join(adaptive_answers)
    fallback = {"has_contradiction": False, "summary": "", "question": ""}
    low_time = any(x in joined for x in ("۳۰", "30", "نیم", "کم", "هفته‌ای"))
    fast = any(x in joined for x in ("سریع", "فوری", "۳ روز", "3 روز", "درآمد", "زود"))
    no_skill = any(x in joined for x in ("هیچی", "بلد نیستم", "تازه", "صفر"))
    if low_time and fast:
        fallback = {
            "has_contradiction": True,
            "summary": "زمان کم با انتظار نتیجه خیلی سریع هم‌زمان گفته شده است.",
            "question": "برای خروجی ۱۰ روزه، ترجیح می‌دی خروجی خیلی کوچک بسازیم یا روزی کمی زمان بیشتری بذاری؟",
        }
    elif no_skill and fast:
        fallback = {
            "has_contradiction": True,
            "summary": "تازه‌کار بودن با انتظار نتیجه سریع نیاز به کوچک‌سازی هدف دارد.",
            "question": "برای شروع سریع، حاضری اول یک خروجی خیلی ساده بسازی و بعد بزرگش کنیم؟",
        }
    if not has_ai:
        return fallback

    prompt = f"""{base_prompt}

پاسخ‌های تشخیصی کاربر را بررسی کن. اگر تناقض عملی مهم وجود دارد، فقط یک سؤال کوتاه و کمک‌کننده برای شفاف‌سازی بده.
خروجی فقط JSON:
{{"has_contradiction": true/false, "summary":"...", "question":"..."}}

پاسخ‌ها:
{joined}
"""
    raw = ai_ask(prompt, max_tokens=260)
    parsed = _parse_json(raw)
    if not isinstance(parsed, dict):
        return fallback
    return {
        "has_contradiction": bool(parsed.get("has_contradiction")),
        "summary": str(parsed.get("summary") or fallback.get("summary") or "").strip(),
        "question": str(parsed.get("question") or fallback.get("question") or "").strip(),
    }


def validate_answer_with_ai(question, answer, expected_topic) -> Dict[str, str]:
    """Soft AI validation. Failure never blocks the flow."""
    fallback = {"status": "ok", "reason": "", "guidance": ""}
    try:
        prompt = _load_prompt_file("validator.txt")
        if not prompt:
            return fallback
        prompt = (prompt
                  .replace("{{expected_topic}}", str(expected_topic or ""))
                  .replace("{{question}}", str(question or ""))
                  .replace("{{answer}}", str(answer or "")))
        raw = ai_ask(prompt, max_tokens=220)
        parsed = _parse_json(raw)
        if not isinstance(parsed, dict):
            return fallback
        status = str(parsed.get("status") or "ok").strip()
        answer_clean = str(answer or "").strip()
        if status not in ("ok", "incomplete", "unrelated"):
            status = "ok"
        # خیلی نرم: فقط پاسخ خالی/تک‌حرفی را واقعاً incomplete حساب کن.
        if status == "incomplete" and len(answer_clean) > 1:
            status = "ok"
        # اگر متن کمی اطلاعات دارد، حتی اگر AI سخت‌گیر بود، جلو می‌رویم.
        if status == "unrelated" and len(answer_clean) > 3:
            status = "ok"
        return {
            "status": status,
            "reason": str(parsed.get("reason") or "").strip(),
            "guidance": str(parsed.get("guidance") or "").strip(),
        }
    except Exception as e:
        logger.info("answer validation skipped: %s", e)
        return fallback


def _has_time_part(answer: str) -> bool:
    text = answer or ""
    return bool(re.search(r"(\d+|[۰-۹]+)\s*(ساعت|دقیقه|روز|هفته)", text)) or any(x in text for x in ("نیم ساعت", "کمتر از", "هر روز", "روزی", "وقت دارم"))


def _has_tool_part(answer: str) -> bool:
    text = answer or ""
    return any(x in text for x in ("موبایل", "لپ", "لپ‌تاپ", "کامپیوتر", "اینترنت", "فتوشاپ", "طراحی", "کدنویسی", "اکسل", "کانوا", "مهارت", "ابزار", "هر دو"))


def _had_soft_retry(messages: List[Dict[str, str]]) -> bool:
    for m in reversed(messages):
        if m.get("role") == "bot":
            return "همین یه جمله کوچیک" in (m.get("text") or "")
    return False


def _question_response(q: Dict[str, Any], profile: Dict[str, str], step: int, phase: str = "diagnosis") -> Dict[str, Any]:
    return {
        "reply": q["question"],
        "step": step,
        "total_steps": 5,
        "phase": phase,
        "profile": profile,
        "can_analyze": False,
        "chips": q.get("chips", []),
        "allow_typing": True,
        "typing_hint": q.get("typing_hint", ""),
        "example": q.get("example", q.get("typing_hint", "")),
        "input_type": q.get("input_type", "chips"),
        "layer": q.get("layer", ""),
    }


def _optional_question(adaptive_answers: List[str]) -> Dict[str, Any] | None:
    joined = " ".join(adaptive_answers)
    if len(adaptive_answers) >= MAX_DIAGNOSTIC_QUESTIONS:
        return None
    if len(" ".join(adaptive_answers).strip()) < 80:
        return OPTIONAL_QUESTIONS[0]
    if not any(x in joined for x in ("استخدام", "فریلنس", "فروش", "نمونه", "پروژه", "خدمت")):
        return OPTIONAL_QUESTIONS[1]
    return None


def _final_message(profile: Dict[str, str], adaptive_count: int) -> str:
    return (
        f"{profile.get('name') or 'دوست عزیز'}، اطلاعات اصلی رو گرفتم. "
        f"با {adaptive_count} پاسخ تشخیصی، الان می‌تونم گره اصلی، مسیرهای سریع‌تر و ابزارهای AI مناسب تو رو بسازم."
    )


def interviewer_chat(messages: List[Dict[str, str]]) -> Dict[str, Any]:
    """مدیریت فانل تشخیصی تطبیقی مهمان."""
    texts = _user_texts(messages)
    base_prompt = _load_prompt()
    status = check_ai_status()
    has_ai = bool(status.get("has_key"))

    if not texts:
        return {
            "reply": "سلام! خوشحالم که اومدی 🌟\n\nبرای شروع، لطفاً توی یک پیام اسمت، سنت و شهرت رو بنویس.\nمثال: علی، ۲۳ ساله، تهران",
            "step": 1,
            "total_steps": 5,
            "phase": "profile",
            "can_analyze": False,
            "chips": [],
            "allow_typing": True,
            "typing_hint": "مثلاً: سارا، ۲۴ ساله، اصفهان",
            "example": "مثلاً: سارا، ۲۴ ساله، اصفهان",
            "layer": "پروفایل اولیه",
        }

    profile, consumed = _profile_from_texts(texts, base_prompt, has_ai)
    missing = [key for key in PROFILE_FIELDS if not profile.get(key)]
    if missing:
        return {
            "reply": _missing_profile_question(missing),
            "step": 1,
            "total_steps": 5,
            "phase": "profile",
            "profile": profile,
            "can_analyze": False,
            "chips": [],
            "allow_typing": True,
            "typing_hint": "فقط مورد جاافتاده را بنویس",
            "example": "مثلاً: علی، ۲۳ ساله، تهران",
            "layer": "تکمیل پروفایل",
        }

    adaptive_answers = texts[consumed:]
    adaptive_count = len(adaptive_answers)
    retried_once = _had_soft_retry(messages)

    # اگر کاربر در پاسخ زمان، ابزار را هم گفته باشد، سؤال ابزار را تکرار نمی‌کنیم.
    answered_time = any(_has_time_part(a) for a in adaptive_answers)
    answered_tools = any(_has_tool_part(a) for a in adaptive_answers)
    effective_count = adaptive_count
    if adaptive_count >= 3 and answered_time and answered_tools:
        effective_count = max(effective_count, 4)

    if adaptive_count > 0 and not retried_once:
        prev_idx = min(adaptive_count - 1, len(CORE_QUESTIONS) - 1)
        if prev_idx < len(CORE_QUESTIONS):
            prev_q = CORE_QUESTIONS[prev_idx]
            # بسیار نرم: فقط پاسخ‌های خالی/تک‌حرفی واقعاً نگه داشته می‌شوند.
            validation = validate_answer_with_ai(prev_q.get("question"), adaptive_answers[-1], prev_q.get("expected_topic")) if has_ai else {"status": "ok"}
            if validation.get("status") in ("incomplete", "unrelated"):
                guidance = validation.get("guidance") or "همین یه جمله کوچیک کمکم می‌کنه بهتر راهنمایی‌ات کنم 🌟"
                if "همین یه جمله کوچیک" not in guidance:
                    guidance = guidance.rstrip(".؟! ") + "؛ همین یه جمله کوچیک کمکم می‌کنه بهتر راهنمایی‌ات کنم 🌟"
                return {
                    "reply": guidance,
                    "step": min(1 + adaptive_count, 5),
                    "total_steps": 5,
                    "phase": "soft_retry",
                    "profile": profile,
                    "can_analyze": False,
                    "chips": prev_q.get("chips", []),
                    "allow_typing": True,
                    "typing_hint": prev_q.get("typing_hint", ""),
                    "example": "",
                    "input_type": prev_q.get("input_type", "chips"),
                    "layer": prev_q.get("layer", ""),
                    "soft_retry": True,
                }

    if effective_count < len(CORE_QUESTIONS):
        q = CORE_QUESTIONS[effective_count]
        return _question_response(q, profile, min(2 + effective_count, 5))

    contradiction = _detect_contradiction(adaptive_answers, base_prompt, has_ai)
    if contradiction.get("has_contradiction") and effective_count == len(CORE_QUESTIONS):
        return {
            "reply": contradiction.get("question") or "یک نکته رو شفاف کنیم: ترجیح می‌دی خروجی کوچک‌تر ولی سریع‌تر بسازیم؟",
            "step": 5,
            "total_steps": 5,
            "phase": "clarification",
            "profile": profile,
            "contradiction": contradiction,
            "can_analyze": False,
            "chips": ["خروجی کوچک‌تر ولی سریع‌تر", "زمان بیشتر می‌ذارم", "مسیر مطمئن‌تر مهم‌تره"],
            "allow_typing": True,
            "typing_hint": "ترجیح واقعی‌ات را کوتاه بنویس",
            "layer": "شفاف‌سازی تناقض",
        }

    optional = _optional_question(adaptive_answers)
    if optional and effective_count < MAX_DIAGNOSTIC_QUESTIONS:
        return _question_response(optional, profile, min(2 + effective_count, 5))

    return {
        "reply": _final_message(profile, effective_count),
        "step": 6,
        "total_steps": 5,
        "phase": "analysis_ready",
        "profile": profile,
        "can_analyze": True,
        "chips": [],
        "allow_typing": False,
        "typing_hint": "",
        "layer": "آماده تحلیل",
    }
