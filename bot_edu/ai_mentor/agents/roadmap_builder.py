"""
roadmap_builder.py — ایجنت ۲: معمار نقشه راه.

مسئولیت واحد: تبدیل JSON نهاییِ ایجنت ۱ به **اسکلت** نقشه راه.

⚠️ این ایجنت هیچ محتوای آموزشی تولید نمی‌کند. هر گام فقط عنوان، هدف،
مهارت‌ها، پروژه و تمرین دارد؛ متن درس بعداً و در لحظهٔ باز شدن گام توسط
ایجنت ۳ ساخته می‌شود (Lazy Loading). به همین دلیل این مرحله سریع است و
کاربر پشت یک درخواست سنگین منتظر نمی‌ماند.

وابستگی: ai_mentor.core، config (فهرست دوره‌ها) و stdlib.
"""
import logging

from config import COURSES

from ..core import (UserJourneyContext, ask_agent, clamp_int, extract_json,
                    jdump, load_prompt, pick)

logger = logging.getLogger(__name__)

MIN_STEPS = 10
MAX_STEPS = 15
_DIFFICULTIES = ("easy", "medium", "hard")

# حافظهٔ جمعی (شبیه‌سازی‌شده) — تجربهٔ کاربران مشابه.
# با انباشته‌شدن دادهٔ واقعی، همین ساختار قابل جایگزینی است.
MOCK_COLLECTIVE_MEMORY = {
    "programmer": {
        "avg_completion_rate": 0.78,
        "hard_steps": ["OOP", "Django", "Async", "الگوریتم"],
        "tip": "مفاهیم شیءگرایی معمولاً گلوگاه است؛ با مثال عملی شروع کن.",
    },
    "designer": {
        "avg_completion_rate": 0.85,
        "hard_steps": ["Typography", "تئوری رنگ", "Design System"],
        "tip": "تایپوگرافی سخت‌ترین بخش است؛ با تمرین بصری جلو برو.",
    },
    "marketer": {
        "avg_completion_rate": 0.81,
        "hard_steps": ["Google Analytics", "قیف فروش", "A/B Testing"],
        "tip": "تحلیل داده معمولاً دلهره‌آور است؛ با گزارش‌های ساده آغاز کن.",
    },
    "data": {
        "avg_completion_rate": 0.72,
        "hard_steps": ["آمار", "Pandas", "یادگیری ماشین", "SQL پیشرفته"],
        "tip": "آمار پایه بیشترین ریزش را دارد؛ آن را به گام‌های خرد بشکن.",
    },
    "other": {
        "avg_completion_rate": 0.80,
        "hard_steps": [],
        "tip": "",
    },
}


def collective_hint(category: str) -> str:
    """متن آماده از حافظهٔ جمعی برای تزریق به پرامپت معمار."""
    mem = MOCK_COLLECTIVE_MEMORY.get(
        (category or "other").strip().lower(), MOCK_COLLECTIVE_MEMORY["other"])
    if not mem.get("hard_steps"):
        return ""
    pct = int(mem.get("avg_completion_rate", 0) * 100)
    out = [
        "تجربهٔ کاربران مشابه (حافظهٔ جمعی):",
        f"- نرخ تکمیل میانگین این دسته: {pct}٪",
        f"- گام‌های دشوار: {', '.join(mem['hard_steps'])}",
        "- این گام‌های دشوار را به چند گام کوچک‌تر بشکن.",
    ]
    if mem.get("tip"):
        out.append(f"- نکته: {mem['tip']}")
    return "\n".join(out)


def courses_brief(limit: int = 40) -> str:
    """فهرست فشردهٔ دوره‌های ربات — تا معمار course_id جعلی نسازد."""
    lines = []
    for cid, c in list(COURSES.items())[:limit]:
        title = (c.get("title") or "").strip()
        if not title:
            continue
        desc = (c.get("description") or "").strip().replace("\n", " ")[:70]
        lines.append(f"- course_id={cid} | عنوان: {title} | توضیح: {desc}")
    return "\n".join(lines) if lines else "(هیچ دوره‌ای ثبت نشده است)"


class RoadmapBuilderAgent:
    """ایجنت ۲ — معمار نقشه راه (فقط اسکلت، بدون محتوا)."""

    name = "roadmap_builder"
    prompt_file = "roadmap_builder.txt"

    def __init__(self):
        self.prompt = self._load_prompt(self.prompt_file)
        self.stage = "idle"

    def _load_prompt(self, filename: str) -> str:
        return load_prompt(filename)

    # ---------- اجرا ----------

    async def run(self, context: UserJourneyContext,
                  user_message: str = "") -> dict:
        """ساخت اسکلت نقشه راه از JSON ایجنت ۱.

        خروجی: {ok, stage, roadmap, total_steps, total_estimated_days,
                 final_project, model}
        نتیجه روی context.roadmap نوشته می‌شود.
        """
        payload = self._build_payload(context)
        res = await ask_agent(self.prompt, payload, 2200, "roadmap",
                              context.user_id)

        data = extract_json(res.get("text", "")) if res.get("ok") else None
        steps = self._clean_roadmap((data or {}).get("roadmap")
                                    if isinstance(data, dict) else None)

        if not steps:
            logger.info("معمار نقشه راه: خروجی معتبر نبود؛ اسکلت پشتیبان ساخته شد.")
            steps = self._fallback_roadmap(context)
            fallback = True
            d = {}
        else:
            fallback = False
            d = data if isinstance(data, dict) else {}

        context.roadmap = steps
        context.current_step = 1
        self.stage = "done"

        days = clamp_int(d.get("total_estimated_days"), 1, 720, 0)
        if not days:
            hours = sum(int(s.get("estimated_hours") or 0) for s in steps)
            daily = max(1, int((context.user_profile or {}).get(
                "daily_minutes", 60)) // 60 or 1)
            days = max(len(steps), min(360, round(hours / daily) or len(steps)))

        return {
            "ok": True,
            "stage": "done",
            "fallback": fallback,
            "roadmap": steps,
            "total_steps": len(steps),
            "total_estimated_days": days,
            "final_project": (d.get("final_project") or
                              (steps[-1].get("project") if steps else "")
                              or "").strip()[:400],
            "model": res.get("model", ""),
        }

    def _build_payload(self, context: UserJourneyContext) -> str:
        """ورودی ایجنت ۲ — دقیقاً همان JSON خروجی ایجنت ۱ + زمینهٔ ربات."""
        agent1_json = {
            "user_profile": context.user_profile or {},
            "selected_path": context.selected_path or {},
            "market_analysis": context.market_analysis or {},
            "recommended_tools": list(context.recommended_tools or []),
        }
        rows = ["ورودی از Career Interview Agent:", jdump(agent1_json)]

        hint = collective_hint((context.user_profile or {}).get("category", "other"))
        if hint:
            rows += ["", hint]
        rows += ["", "دوره‌های موجود در ربات:", courses_brief()]
        return "\n".join(rows)

    # ---------- اعتبارسنجی ----------

    def _clean_roadmap(self, raw) -> list:
        """پاک‌سازی خروجی مدل. محتوای آموزشی عمداً نگه داشته نمی‌شود."""
        if not isinstance(raw, list) or not raw:
            return []

        out = []
        for i, s in enumerate(raw[:MAX_STEPS], 1):
            if isinstance(s, str) and s.strip():
                s = {"title": s.strip()}
            if not isinstance(s, dict):
                continue
            title = (s.get("title") or "").strip()[:120]
            if not title:
                continue

            # course_id فقط اگر واقعاً در فهرست دوره‌های ربات باشد
            cid = str(s.get("course_id") or "").strip()
            if cid not in COURSES:
                cid = ""

            out.append({
                "step_number": len(out) + 1,
                "title": title,
                "objective": (s.get("objective") or "").strip()[:400],
                "skills_to_learn": [str(x).strip()[:60] for x in
                                    (s.get("skills_to_learn") or [])[:8] if x],
                "project": (s.get("project") or "").strip()[:600],
                "exercise": (s.get("exercise") or "").strip()[:600],
                "expected_output": (s.get("expected_output") or "").strip()[:400],
                "estimated_hours": clamp_int(s.get("estimated_hours"), 1, 200, 4),
                "difficulty": pick(s.get("difficulty"), _DIFFICULTIES, "medium"),
                "tools_needed": [str(x).strip()[:60] for x in
                                 (s.get("tools_needed") or [])[:8] if x],
                "ai_tools": [str(x).strip()[:60] for x in
                             (s.get("ai_tools") or [])[:6] if x],
                "course_id": cid,
                "step_type": "course" if cid else "lesson",
            })
        return out

    def _fallback_roadmap(self, context: UserJourneyContext) -> list:
        """اسکلت پایه وقتی AI در دسترس نیست — مسیر هرگز نیمه‌کاره نمی‌ماند."""
        job = context.target_job()
        skills = list((context.selected_path or {}).get("key_skills") or [])
        tools = list(context.recommended_tools or [])
        if not skills:
            skills = ["مبانی حوزه", "ابزارهای پایه", "پروژهٔ کوچک",
                      "کار تیمی", "نمونه‌کار"]

        titles = [
            (f"آشنایی با مسیر {job}", "easy"),
            ("راه‌اندازی ابزارهای کار", "easy"),
        ]
        for sk in skills[:7]:
            titles.append((f"یادگیری عملی {sk}", "medium"))
        titles += [
            ("ساخت پروژهٔ تمرینی میانی", "medium"),
            ("رفع اشکال و بهبود پروژه", "medium"),
            ("ساخت نمونه‌کار قابل ارائه", "hard"),
            ("آماده‌سازی رزومه و پروفایل", "easy"),
            (f"پروژهٔ نهایی {job}", "hard"),
        ]
        titles = titles[:MAX_STEPS]
        while len(titles) < MIN_STEPS:
            titles.insert(-1, (f"تمرین تکمیلی {len(titles)}", "medium"))

        out = []
        for i, (title, diff) in enumerate(titles, 1):
            out.append({
                "step_number": i,
                "title": title[:120],
                "objective": f"تسلط عملی بر «{title}» با یک خروجی قابل ارائه.",
                "skills_to_learn": skills[:3],
                "project": f"یک تمرین کوچک دربارهٔ «{title}» انجام بده.",
                "exercise": ("خروجی کارت را همین‌جا بفرست و بنویس چه چالشی "
                             "داشتی."),
                "expected_output": "یک فایل، کد، لینک یا توضیح کوتاه از کار انجام‌شده.",
                "estimated_hours": 4,
                "difficulty": diff,
                "tools_needed": tools[:3],
                "ai_tools": [],
                "course_id": "",
                "step_type": "lesson",
            })
        return out


__all__ = ["RoadmapBuilderAgent", "MOCK_COLLECTIVE_MEMORY",
           "collective_hint", "courses_brief", "MIN_STEPS", "MAX_STEPS"]
