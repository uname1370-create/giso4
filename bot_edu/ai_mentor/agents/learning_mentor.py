"""
learning_mentor.py — ایجنت ۳: منتور آموزشی.

مسئولیت واحد: آموزش «گام فعال» و داوری تمرین همان گام.

دو حالت کاری (task):
  teach : تولید محتوای گام در لحظهٔ باز شدن آن (Lazy Loading). محتوا در
          ستون path_steps.content ذخیره می‌شود، پس دفعهٔ بعد بدون
          فراخوانی AI و بدون هزینه خوانده می‌شود.
  grade : داوری پاسخ کاربر به تمرین. اگر درست بود گام بعدی باز می‌شود؛
          اگر غلط بود فقط Hint داده می‌شود، نه جواب.

قوانین Micro-Learning در فایل پرامپت است، نه در کد.

وابستگی: ai_mentor.core، ai_mentor.ai_db و stdlib.
"""
import logging

from .. import ai_db
from ..core import (UserJourneyContext, ask_agent, clamp_int, extract_json,
                    jdump, load_prompt, pick)

logger = logging.getLogger(__name__)

PASS_SCORE = 60          # آستانهٔ قبولی
WEAK_SCORE = 50          # زیر این نمره → موضوع ضعیف
STRONG_SCORE = 80        # بالای این نمره → موضوع قوی


class LearningMentorAgent:
    """ایجنت ۳ — منتور آموزشی (تولید محتوا + داوری تمرین)."""

    name = "learning_mentor"
    prompt_file = "learning_mentor.txt"

    def __init__(self):
        self.prompt = self._load_prompt(self.prompt_file)
        self.stage = "idle"

    def _load_prompt(self, filename: str) -> str:
        return load_prompt(filename)

    # ---------- اجرا ----------

    async def run(self, context: UserJourneyContext, user_message: str = "",
                  step_number: int = 0, task: str = "teach") -> dict:
        """اجرای یک نوبت.

        task="teach" → تولید محتوای گام step_number
        task="grade" → داوری user_message به‌عنوان پاسخ تمرین همان گام
        """
        n = int(step_number or context.current_step or 1)
        step = context.get_step(n)
        if not step:
            return {"ok": False, "error": "این گام در نقشه راه پیدا نشد."}

        if task == "grade":
            return await self._grade(context, step, user_message)
        return await self._teach(context, step)

    # ---------- تولید محتوا ----------

    async def _teach(self, context: UserJourneyContext, step: dict) -> dict:
        payload = self._payload(context, step, "teach")
        res = await ask_agent(self.prompt, payload, 1400, "challenge",
                              context.user_id)

        data = extract_json(res.get("text", "")) if res.get("ok") else None
        body = ((data or {}).get("content_text") or "").strip() \
            if isinstance(data, dict) else ""

        if not body:
            logger.info("منتور: محتوای معتبر تولید نشد؛ محتوای پشتیبان استفاده شد.")
            content = self._fallback_content(step)
            fallback = True
        else:
            d = data
            content = {
                "generated": True,
                "description": body[:1500],
                "challenge": (d.get("exercise_question") or
                              step.get("exercise") or "").strip()[:900],
                "expected_output": (d.get("expected_output") or
                                    step.get("expected_output") or "").strip()[:400],
                "hint": (d.get("hint") or "").strip()[:400],
                "estimated_minutes": clamp_int(d.get("estimated_minutes"),
                                               1, 240, 0),
                "course_id": step.get("course_id", ""),
                "objective": step.get("objective", ""),
                "skills_to_learn": step.get("skills_to_learn", []),
                "tools_needed": step.get("tools_needed", []),
                "ai_tools": step.get("ai_tools", []),
                "difficulty": step.get("difficulty", "medium"),
            }
            fallback = False

        self.stage = "teaching"
        context.add_step_message(step["step_number"], "assistant",
                                 content.get("description", ""))
        return {"ok": True, "task": "teach", "stage": "teaching",
                "fallback": fallback, "content": content,
                "step_number": step["step_number"],
                "model": res.get("model", "")}

    def _fallback_content(self, step: dict) -> dict:
        """محتوای پایه از خود اسکلت گام — وقتی AI در دسترس نیست."""
        parts = []
        if step.get("objective"):
            parts.append(f"🎯 هدف این گام: {step['objective']}")
        if step.get("skills_to_learn"):
            parts.append("🧩 مهارت‌های این گام: "
                         + "، ".join(step["skills_to_learn"][:5]))
        if step.get("tools_needed"):
            parts.append("🛠 ابزارهای لازم: " + "، ".join(step["tools_needed"][:4]))
        if step.get("project"):
            parts.append(f"🏗 پروژهٔ این گام: {step['project']}")
        if not parts:
            parts.append(f"در این گام روی «{step.get('title', '')}» کار می‌کنی.")
        parts.append("\n⚠️ متن آموزشی هوشمند در این لحظه در دسترس نبود؛ "
                     "بعداً با باز کردن دوبارهٔ گام، تولید می‌شود.")
        return {
            "generated": False,
            "description": "\n\n".join(parts)[:1500],
            "challenge": (step.get("exercise") or step.get("project") or "").strip()[:900],
            "expected_output": (step.get("expected_output") or "").strip()[:400],
            "hint": "",
            "estimated_minutes": int(step.get("estimated_hours") or 0) * 60 or 0,
            "course_id": step.get("course_id", ""),
            "objective": step.get("objective", ""),
            "skills_to_learn": step.get("skills_to_learn", []),
            "tools_needed": step.get("tools_needed", []),
            "ai_tools": step.get("ai_tools", []),
            "difficulty": step.get("difficulty", "medium"),
        }

    # ---------- داوری تمرین ----------

    async def _grade(self, context: UserJourneyContext, step: dict,
                     answer: str) -> dict:
        ans = (answer or "").strip()
        if not ans:
            return {"ok": False, "error": "پاسخ خالی است."}

        context.add_step_message(step["step_number"], "user", ans)
        payload = self._payload(context, step, "grade", ans)
        res = await ask_agent(self.prompt, payload, 1000, "challenge",
                              context.user_id)

        data = extract_json(res.get("text", "")) if res.get("ok") else None
        if not res.get("ok") or not isinstance(data, dict):
            return {"ok": False,
                    "error": res.get("error", "داوری در این لحظه ممکن نشد.")}

        status = pick(data.get("status"), ("pass", "fail"), "fail")
        score = clamp_int(data.get("score"), 0, 100,
                          85 if status == "pass" else 35)
        # هم‌راستاسازی نمره و وضعیت تا خروجی متناقض نشود
        if status == "pass" and score < PASS_SCORE:
            score = PASS_SCORE + 20
        elif status == "fail" and score >= PASS_SCORE:
            score = PASS_SCORE - 15

        out = {
            "ok": True,
            "task": "grade",
            "stage": "graded",
            "status": status,
            "passed": status == "pass",
            "score": score,
            "feedback": (data.get("feedback") or "").strip()[:900],
            "hint": ("" if status == "pass"
                     else (data.get("hint") or "").strip()[:400]),
            "xp_reward": (clamp_int(data.get("xp_reward"), 0, 200, 50)
                          if status == "pass" else 0),
            "step_number": step["step_number"],
            "model": res.get("model", ""),
        }
        self.stage = "graded"
        context.add_step_message(step["step_number"], "assistant",
                                 out["feedback"] or out["hint"])
        return out

    # ---------- ورودی مدل ----------

    def _payload(self, context: UserJourneyContext, step: dict, task: str,
                 answer: str = "") -> str:
        total = len(context.roadmap or [])
        n = step.get("step_number", 1)

        done = [s.get("title") for s in (context.roadmap or [])
                if int(s.get("step_number") or 0) < int(n)][-4:]
        upcoming = [s.get("title") for s in (context.roadmap or [])
                    if int(s.get("step_number") or 0) > int(n)][:3]

        rows = [
            f"task: {task}",
            "",
            "user_profile:",
            context.profile_text(),
            "",
            "roadmap:",
            f"- مسیر: {context.target_job()}",
            f"- گام {n} از {total}",
        ]
        if done:
            rows.append(f"- گام‌های قبلی: {'، '.join(x for x in done if x)}")
        if upcoming:
            rows.append(f"- گام‌های بعدی: {'، '.join(x for x in upcoming if x)}")

        rows += ["", "current_step:", jdump({
            "step_number": n,
            "title": step.get("title", ""),
            "objective": step.get("objective", ""),
            "skills_to_learn": step.get("skills_to_learn", []),
            "project": step.get("project", ""),
            "exercise": step.get("exercise", ""),
            "expected_output": step.get("expected_output", ""),
            "estimated_hours": step.get("estimated_hours", 0),
            "difficulty": step.get("difficulty", "medium"),
            "tools_needed": step.get("tools_needed", []),
            "ai_tools": step.get("ai_tools", []),
        })]

        # حافظهٔ فردی — روی لحن و عمق توضیح اثر می‌گذارد
        if context.weak_topics:
            rows.append(f"\n⚠️ نقاط ضعف کاربر: {'، '.join(context.weak_topics[-5:])}")
        if context.strong_topics:
            rows.append(f"💪 نقاط قوت کاربر: {'، '.join(context.strong_topics[-5:])}")

        rows += ["", "chat_history:", context.step_history_text(n)]
        if task == "grade":
            rows += ["", "پاسخ کاربر به تمرین:", answer[:2000]]
        return "\n".join(rows)

    # ---------- حافظهٔ فردی ----------

    def update_learning_profile(self, context: UserJourneyContext,
                                step_id: int, score: int) -> dict:
        """ثبت نمره و به‌روزرسانی نقاط قوت/ضعف کاربر.

        نمره در ai_feedback همان گام ذخیره می‌شود و عنوان گام بسته به نمره
        وارد weak_topics یا strong_topics می‌گردد. این داده در تولید
        محتوای گام‌های بعدی استفاده می‌شود.
        آستانه‌ها: زیر ۵۰ ضعف، بالای ۸۰ قوت.
        """
        step = ai_db.get_step(step_id)
        if not step:
            return {"ok": False, "error": "گام پیدا نشد."}
        path = ai_db.get_path(step.get("path_id"))
        if not path or int(path.get("user_id", 0)) != int(context.user_id):
            return {"ok": False, "error": "دسترسی مجاز نیست."}   # 🔒 مالکیت

        score = clamp_int(score, 0, 100, 0)
        fb = step.get("ai_feedback") or {}
        if not isinstance(fb, dict):
            fb = {}
        fb["score"] = score
        fb["scored_at"] = _now_str()
        ai_db.update_step_ai_feedback(step_id, fb)

        weak = list(context.weak_topics or [])
        strong = list(context.strong_topics or [])
        title = (step.get("title") or "").strip()

        bucket = "mid"
        if title:
            if score < WEAK_SCORE:
                bucket = "weak"
                if title in strong:
                    strong.remove(title)
                if title not in weak:
                    weak.append(title)
            elif score > STRONG_SCORE:
                bucket = "strong"
                if title in weak:
                    weak.remove(title)
                if title not in strong:
                    strong.append(title)

        context.weak_topics = weak[-20:]
        context.strong_topics = strong[-20:]
        ai_db.update_interview_data(path["id"], {
            "weak_topics": context.weak_topics,
            "strong_topics": context.strong_topics,
        })
        return {"ok": True, "bucket": bucket, "score": score,
                "weak": context.weak_topics, "strong": context.strong_topics}


def _now_str() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


__all__ = ["LearningMentorAgent", "PASS_SCORE", "WEAK_SCORE", "STRONG_SCORE"]
