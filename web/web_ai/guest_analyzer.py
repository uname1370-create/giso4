# -*- coding: utf-8 -*-
"""
web/web_ai/guest_analyzer.py
تحلیل‌گر AI برای فانل /mentor/try

خروجی ساختگی تولید نمی‌شود. اگر AI خروجی کامل ندهد، پیام retry/خطا برمی‌گردد.
"""
import json
import logging
import re
from pathlib import Path
from typing import List, Dict, Any, Tuple
from .ai_engine import check_ai_status, call_ai

logger = logging.getLogger("web.web_ai.guest_analyzer")

_PROMPTS_DIR = Path(__file__).resolve().parent / "prompts"
_PROMPT_CACHE: str = ""
PROFILE_FIELDS = ("name", "age", "city")


def _load_prompt() -> str:
    global _PROMPT_CACHE
    if _PROMPT_CACHE:
        return _PROMPT_CACHE
    p_file = _PROMPTS_DIR / "analyzer.txt"
    try:
        if p_file.exists():
            _PROMPT_CACHE = p_file.read_text(encoding="utf-8").strip()
            return _PROMPT_CACHE
    except Exception as e:
        logger.warning("guest_analyzer load prompt error: %s", e)
    return "تو مشاور شغلی هوشمند sadeghiai هستی. خروجی فقط JSON معتبر باشد."


def _user_texts(conversation: List[Dict[str, str]]) -> List[str]:
    return [
        (m.get("text") or m.get("content") or "").strip()
        for m in conversation if m.get("role") == "user"
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
        logger.info("guest_analyzer parse json failed: %s", e)
        return None


def _fallback_profile_extract(text: str) -> Dict[str, str]:
    clean = (text or "").strip()
    profile = {"name": "", "age": "", "city": ""}
    age_match = re.search(r"(\d{1,2}|[۰-۹]{1,2})\s*(?:ساله|سال)?", clean)
    if age_match:
        profile["age"] = age_match.group(1)
    for city in ["تهران", "مشهد", "اصفهان", "شیراز", "تبریز", "کرج", "قم", "اهواز", "رشت", "کرمان", "یزد", "ارومیه"]:
        if city in clean:
            profile["city"] = city
            break
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


def _extract_profile_ai(text: str, has_ai: bool) -> Dict[str, str]:
    fallback = _fallback_profile_extract(text)
    if not has_ai:
        return fallback
    prompt = f"""از متن زیر فقط name، age و city را استخراج کن.
اگر موردی نبود رشته خالی بگذار. خروجی فقط JSON باشد:
{{"name":"...","age":"...","city":"..."}}

{text}
"""
    parsed = _parse_json(call_ai(prompt, max_tokens=180))
    if not isinstance(parsed, dict):
        return fallback
    return {
        "name": str(parsed.get("name") or fallback.get("name") or "").strip(),
        "age": str(parsed.get("age") or fallback.get("age") or "").strip(),
        "city": str(parsed.get("city") or fallback.get("city") or "").strip(),
    }


def _profile_from_texts(texts: List[str], has_ai: bool) -> Tuple[Dict[str, str], int]:
    profile = {"name": "", "age": "", "city": ""}
    consumed = 0
    buffer: List[str] = []
    for idx, text in enumerate(texts):
        buffer.append(text)
        extracted = _extract_profile_ai("\n".join(buffer), has_ai)
        for key in PROFILE_FIELDS:
            if extracted.get(key):
                profile[key] = extracted[key]
        consumed = idx + 1
        if all(profile.values()):
            return profile, consumed
    return profile, consumed


def _extract_context(conversation: List[Dict[str, str]], has_ai: bool) -> Dict[str, Any]:
    texts = _user_texts(conversation)
    profile, consumed = _profile_from_texts(texts, has_ai)
    adaptive_answers = texts[consumed:]
    return {
        "profile": profile,
        "diagnostic_answers": adaptive_answers,
        "raw_user_messages": texts,
    }


def _build_analysis_prompt(base_prompt: str, context: Dict[str, Any]) -> str:
    profile = context.get("profile", {})
    answers = context.get("diagnostic_answers", [])
    answer_lines = "\n".join([f"{i+1}) {a}" for i, a in enumerate(answers)]) or "بدون پاسخ تشخیصی"
    return f"""{base_prompt}

════════════════════════════════════════════
پروفایل قطعی کاربر:
════════════════════════════════════════════
نام: {profile.get('name') or 'نامشخص'}
سن: {profile.get('age') or 'نامشخص'}
شهر: {profile.get('city') or 'نامشخص'}

════════════════════════════════════════════
پاسخ‌های تشخیصی تطبیقی کاربر:
════════════════════════════════════════════
{answer_lines}

════════════════════════════════════════════
دستور نهایی:
════════════════════════════════════════════
بر اساس پروفایل و پاسخ‌های تشخیصی، خروجی را با schema انعطاف‌پذیر خواسته‌شده بساز.
تمرکز اصلی: تشخیص bottleneck واقعی، سریع‌ترین خروجی عملی ۳ تا ۱۰ روزه، مسیرهای ۱ تا ۳ عدد، و ابزارهای AI مناسب.
خروجی فقط JSON معتبر باشد.
"""


def _analysis_unavailable_response(context: Dict[str, Any], reason: str) -> Dict[str, Any]:
    profile = context.get("profile", {})
    name = profile.get("name") or "دوست عزیز"
    return {
        "success": False,
        "error": "AI_ANALYSIS_UNAVAILABLE",
        "reason": reason,
        "message": (
            f"{name} عزیز، برای اینکه مسیر یا نمودار ساختگی نشون ندیم، "
            "تحلیل هوشمند کامل نشد. لطفاً دوباره تلاش کن."
        ),
        "user_profile": {
            "name": name,
            "age": profile.get("age") or "",
            "city": profile.get("city") or "",
            "current_status": "",
            "interest_direction": "",
            "time_available": "",
        },
        "routes": [],
        "metrics": [],
    }


def _number_in_3_to_10(value: Any) -> bool:
    nums = [int(x) for x in re.findall(r"\d+", str(value or ""))]
    return bool(nums) and min(nums) >= 3 and max(nums) <= 10


def _validate_result(result: Dict[str, Any]) -> bool:
    if not isinstance(result, dict):
        logger.info("guest_analyzer validate failed: result type=%s", type(result).__name__)
        return False
    if result.get("success") is not True:
        logger.info("guest_analyzer validate failed: success is not true")
        return False
    for key in ("user_profile", "diagnosis", "routes", "metrics", "cta"):
        if not result.get(key):
            logger.info("guest_analyzer validate failed: missing %s", key)
            return False

    routes = result.get("routes")
    if not isinstance(routes, list) or not (1 <= len(routes) <= 3):
        logger.info("guest_analyzer validate failed: routes len invalid")
        return False
    metrics = result.get("metrics")
    if not isinstance(metrics, list) or not (3 <= len(metrics) <= 6):
        logger.info("guest_analyzer validate failed: metrics len invalid")
        return False

    strengths = result.get("strengths", [])
    challenges = result.get("challenges", [])
    if strengths and (not isinstance(strengths, list) or len(strengths) > 4):
        return False
    if challenges and (not isinstance(challenges, list) or len(challenges) > 4):
        return False

    for idx, route in enumerate(routes, start=1):
        if not isinstance(route, dict):
            return False
        required = (
            "title", "fit_percent", "why_fit", "first_result_window_days",
            "first_result_type", "effort_level", "salary_note", "ai_tools",
            "sprint_plan", "cautions"
        )
        missing = [key for key in required if not route.get(key)]
        if missing:
            logger.info("guest_analyzer validate failed: route_%s missing=%s", idx, missing)
            return False
        if not _number_in_3_to_10(route.get("first_result_window_days")):
            logger.info("guest_analyzer validate failed: route_%s first window out of range", idx)
            return False
        if not isinstance(route.get("ai_tools"), list) or not route["ai_tools"]:
            return False
        for tool in route["ai_tools"]:
            if not isinstance(tool, dict) or not tool.get("name") or not tool.get("why") or not tool.get("how_helps"):
                return False
        if not isinstance(route.get("sprint_plan"), list) or not route["sprint_plan"]:
            return False
        for sprint in route["sprint_plan"]:
            if not isinstance(sprint, dict) or not sprint.get("day_range") or not sprint.get("task"):
                return False

    for metric in metrics:
        if not isinstance(metric, dict) or not metric.get("label") or metric.get("score") is None:
            return False
    return True


def _call_analysis_ai(prompt: str) -> Dict[str, Any] | None:
    raw = call_ai(prompt, max_tokens=3600)
    logger.info("guest_analyzer ai analysis raw_len=%s preview=%r", len(raw or ""), (raw or "")[:200])
    return _parse_json(raw)


def analyze_guest_paths(conversation: List[Dict[str, str]]) -> Dict[str, Any]:
    """تحلیل نهایی منعطف برای /mentor/try."""
    status = check_ai_status()
    has_ai = bool(status.get("has_key"))
    context = _extract_context(conversation, has_ai)
    profile = context.get("profile", {})

    if not has_ai or not all(profile.get(k) for k in PROFILE_FIELDS):
        logger.info("guest_analyzer unavailable: has_ai=%s profile=%s", has_ai, profile)
        return _analysis_unavailable_response(context, "ai_not_available_or_profile_incomplete")

    base_prompt = _load_prompt()
    prompt = _build_analysis_prompt(base_prompt, context)

    for attempt in (1, 2):
        parsed = _call_analysis_ai(prompt)
        if _validate_result(parsed):
            return parsed
        logger.info("guest_analyzer analysis attempt_%s invalid", attempt)
        prompt += "\n\nتلاش قبلی ناقص بود. این بار دقیقاً schema خواسته‌شده را کامل کن؛ routes بین ۱ تا ۳ و metrics بین ۳ تا ۶ باشد."

    return _analysis_unavailable_response(context, "invalid_ai_response_after_retry")
