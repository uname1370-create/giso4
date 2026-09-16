"""
career_interview.py — ایجنت ۱: مصاحبه‌گر شغلی.

مسئولیت واحد: شناخت کاربر و رساندن او به یک «مسیر شغلی انتخاب‌شده».
این ایجنت هرگز محتوای آموزشی تولید نمی‌کند و هرگز نقشه راه نمی‌سازد.

ماشین حالت (stage):
    introduction → questioning → suggestion → report → done

  questioning : ۶ تا ۸ سؤال مکالمه‌ای، یکی‌یکی، با واکنش به پاسخ قبلی.
  suggestion  : تحلیل بازار و معرفی ۳ مسیر شغلی متناسب با پاسخ‌ها.
  report      : گزارش کامل مسیری که کاربر انتخاب کرده (تا با چشم باز
                تصمیم بگیرد).
  done        : خروجی JSON نهایی برای تحویل به ایجنت ۲.

وابستگی: ai_mentor.core، ai_mentor.ai_db و stdlib.
"""
import logging

from .. import ai_db
from ..core import (UserJourneyContext, ask_agent, clamp_int, extract_json,
                    load_prompt, pick)

logger = logging.getLogger(__name__)

# کمینه و بیشینهٔ سؤال‌های مصاحبه — طبق مشخصات: ۶ تا ۸ سؤال مکالمه‌ای
MIN_QUESTIONS = 6
MAX_QUESTIONS = 8

# محورهای پشتیبان — اگر AI در دسترس نبود، مصاحبه متوقف نمی‌شود
FALLBACK_QUESTIONS = [
    {"key": "motivation",
     "text": "🎯 چه چیزی باعث شد بخوای این مسیر رو شروع کنی؟",
     "hint": "مثال: می‌خوام از شغل فعلی‌ام جابه‌جا بشم"},
    {"key": "level",
     "text": "📈 الان چقدر با این حوزه آشنایی داری؟",
     "hint": "مثال: تازه شروع کردم / یک‌کم بلدم / تجربه دارم"},
    {"key": "time",
     "text": "⏰ روزی چقدر وقت آزاد داری؟",
     "hint": "مثال: نیم ساعت / ۲ ساعت"},
    {"key": "style",
     "text": "🧠 چطوری بهتر یاد می‌گیری؟",
     "hint": "مثال: با تمرین عملی / با ویدیو / با خوندن"},
    {"key": "interest",
     "text": "💡 کدوم حوزه بیشتر برات جذابه؟",
     "hint": "مثال: برنامه‌نویسی وب، طراحی، تحلیل داده"},
    {"key": "background",
     "text": "🎓 پیشینه‌ات چیه؟ (تحصیل یا کار قبلی)",
     "hint": "مثال: دانشجوی مهندسی / فروشنده بودم"},
    {"key": "constraints",
     "text": "⚙️ محدودیت خاصی داری؟ (لپ‌تاپ، زبان انگلیسی، بودجه)",
     "hint": "مثال: انگلیسی‌ام ضعیفه / فقط موبایل دارم"},
    {"key": "goal_type",
     "text": "💼 هدف نهایی‌ات استخدامه، فریلنسری، یا کسب‌وکار خودت؟",
     "hint": "مثال: می‌خوام استخدام شرکت بشم"},
]

# مسیرهای پشتیبان بر اساس دسته — وقتی AI نتواند پیشنهاد بدهد
_FALLBACK_PATHS = {
    "programmer": [
        {"title": "توسعه‌دهندهٔ بک‌اند پایتون", "demand": "high",
         "difficulty": "medium", "fit_percent": 80,
         "why": "تقاضای پایدار بازار و مسیر یادگیری روشن.",
         "salary_range": "۲۵ تا ۶۰ میلیون تومان",
         "key_skills": ["Python", "Django", "SQL", "Git"]},
        {"title": "توسعه‌دهندهٔ فرانت‌اند React", "demand": "high",
         "difficulty": "medium", "fit_percent": 75,
         "why": "نتیجهٔ کار سریع دیده می‌شود و انگیزه‌بخش است.",
         "salary_range": "۲۰ تا ۵۰ میلیون تومان",
         "key_skills": ["JavaScript", "React", "HTML/CSS", "Git"]},
        {"title": "توسعه‌دهندهٔ اپلیکیشن موبایل", "demand": "medium",
         "difficulty": "hard", "fit_percent": 65,
         "why": "بازار تخصصی‌تر با رقابت کمتر.",
         "salary_range": "۲۵ تا ۵۵ میلیون تومان",
         "key_skills": ["Flutter", "Dart", "REST API"]},
    ],
    "designer": [
        {"title": "طراح رابط و تجربهٔ کاربری (UI/UX)", "demand": "high",
         "difficulty": "medium", "fit_percent": 80,
         "why": "ترکیب خلاقیت و مهارت فنی، با نمونه‌کار قابل ارائه.",
         "salary_range": "۲۰ تا ۵۰ میلیون تومان",
         "key_skills": ["Figma", "Design System", "User Research"]},
        {"title": "طراح گرافیک دیجیتال", "demand": "medium",
         "difficulty": "easy", "fit_percent": 70,
         "why": "ورود سریع و امکان فریلنسری از همان ماه‌های اول.",
         "salary_range": "۱۵ تا ۳۵ میلیون تومان",
         "key_skills": ["Photoshop", "Illustrator", "تایپوگرافی"]},
        {"title": "طراح موشن گرافیک", "demand": "medium",
         "difficulty": "hard", "fit_percent": 60,
         "why": "رقابت کمتر و نرخ پروژه‌ای بالاتر.",
         "salary_range": "۲۰ تا ۴۵ میلیون تومان",
         "key_skills": ["After Effects", "اصول انیمیشن"]},
    ],
    "marketer": [
        {"title": "کارشناس دیجیتال مارکتینگ", "demand": "high",
         "difficulty": "easy", "fit_percent": 78,
         "why": "ورود آسان و کاربرد در تقریباً همهٔ کسب‌وکارها.",
         "salary_range": "۱۵ تا ۴۰ میلیون تومان",
         "key_skills": ["SEO", "Google Analytics", "تولید محتوا"]},
        {"title": "متخصص تبلیغات و رشد (Growth)", "demand": "medium",
         "difficulty": "medium", "fit_percent": 68,
         "why": "نتیجهٔ کار با عدد قابل اثبات است.",
         "salary_range": "۲۰ تا ۵۰ میلیون تومان",
         "key_skills": ["قیف فروش", "A/B Testing", "کمپین"]},
        {"title": "مدیر شبکه‌های اجتماعی", "demand": "medium",
         "difficulty": "easy", "fit_percent": 65,
         "why": "شروع سریع و امکان کار دورکاری.",
         "salary_range": "۱۲ تا ۳۰ میلیون تومان",
         "key_skills": ["استراتژی محتوا", "تقویم محتوایی"]},
    ],
    "data": [
        {"title": "تحلیلگر داده", "demand": "high",
         "difficulty": "medium", "fit_percent": 78,
         "why": "پل ورود کم‌ریسک به دنیای داده.",
         "salary_range": "۲۵ تا ۵۵ میلیون تومان",
         "key_skills": ["SQL", "Excel", "Pandas", "مصورسازی"]},
        {"title": "مهندس یادگیری ماشین", "demand": "medium",
         "difficulty": "hard", "fit_percent": 60,
         "why": "درآمد بالاتر ولی نیازمند پایهٔ ریاضی و آمار.",
         "salary_range": "۳۵ تا ۸۰ میلیون تومان",
         "key_skills": ["Python", "آمار", "scikit-learn"]},
        {"title": "مهندس داده", "demand": "medium",
         "difficulty": "hard", "fit_percent": 62,
         "why": "تقاضای رو به رشد و رقابت کمتر.",
         "salary_range": "۳۰ تا ۷۰ میلیون تومان",
         "key_skills": ["SQL پیشرفته", "ETL", "Airflow"]},
    ],
    "other": [
        {"title": "متخصص دیجیتال (مسیر عمومی)", "demand": "medium",
         "difficulty": "medium", "fit_percent": 70,
         "why": "مسیری منعطف که با علاقهٔ شما شکل می‌گیرد.",
         "salary_range": "۱۵ تا ۴۰ میلیون تومان",
         "key_skills": ["مهارت پایهٔ دیجیتال", "کار با ابزارهای AI"]},
        {"title": "تولیدکنندهٔ محتوای تخصصی", "demand": "medium",
         "difficulty": "easy", "fit_percent": 65,
         "why": "ورود سریع با کمترین پیش‌نیاز فنی.",
         "salary_range": "۱۲ تا ۳۰ میلیون تومان",
         "key_skills": ["نویسندگی", "سئو محتوا"]},
        {"title": "پشتیبان فنی محصولات نرم‌افزاری", "demand": "medium",
         "difficulty": "easy", "fit_percent": 60,
         "why": "نقطهٔ شروع خوب برای ورود به صنعت نرم‌افزار.",
         "salary_range": "۱۲ تا ۲۵ میلیون تومان",
         "key_skills": ["ارتباط مؤثر", "عیب‌یابی پایه"]},
    ],
}

_CATEGORIES = ("programmer", "designer", "marketer", "data", "other")
_LEVELS = ("beginner", "intermediate", "advanced")
_STYLES = ("visual", "practical", "reading", "mixed")
_DEMANDS = ("low", "medium", "high")
_DIFFICULTIES = ("easy", "medium", "hard")
_STAGES = ("introduction", "questioning", "suggestion", "report",
           "confirmation", "done")


class CareerInterviewAgent:
    """ایجنت ۱ — مصاحبه‌گر شغلی."""

    name = "career_interview"
    prompt_file = "career_interview.txt"

    def __init__(self):
        self.prompt = self._load_prompt(self.prompt_file)
        self.stage = "introduction"

    # ---------- پرامپت ----------

    def _load_prompt(self, filename: str) -> str:
        """خواندن پرامپت از ai_mentor/prompts/."""
        return load_prompt(filename)

    # ---------- ورودی مدل ----------

    def _market_brief(self, limit: int = 8) -> str:
        """مهارت‌های پرتقاضای فعلی از جدول market_trends."""
        try:
            rows = ai_db.get_trending_skills(limit)
        except Exception as e:
            logger.debug(f"market_brief: {e}")
            rows = []
        if not rows:
            return "(دادهٔ ترند در دسترس نیست)"
        return "، ".join(
            f"{r['skill_name']} ({r.get('demand_count', 0)} آگهی)" for r in rows)

    def _build_payload(self, context: UserJourneyContext, task: str,
                       extra: str = "") -> str:
        prof = {}
        try:
            prof = ai_db.get_user_profile(context.user_id) or {}
        except Exception:
            prof = {}

        rows = [
            f"task: {task}",
            f"stage فعلی: {context.stage}",
            f"تعداد سؤال‌های پرسیده‌شده تا الان: {len(context.answers)}",
            f"حداقل سؤال لازم: {MIN_QUESTIONS} | حداکثر: {MAX_QUESTIONS}",
            "",
            "profile:",
            f"- سن: {prof.get('age') or '—'}",
            f"- شهر: {prof.get('city') or '—'}",
            "",
            "answers:",
            context.answers_text(),
            "",
            "conversation:",
            context.conversation_text(),
            "",
            f"market: {self._market_brief()}",
        ]
        if extra:
            rows += ["", extra]
        return "\n".join(rows)

    # ---------- اجرا ----------

    async def run(self, context: UserJourneyContext,
                  user_message: str = "") -> dict:
        """یک نوبت گفتگو با کاربر.

        ورودی user_message پاسخ کاربر به سؤال قبلی است (در شروع خالی).
        خروجی: {ok, stage, message, hint, paths, report, final_json}
        وضعیت جدید هم روی خود context نوشته می‌شود.
        """
        msg = (user_message or "").strip()

        # ثبت پاسخ کاربر روی کلید سؤال قبلی
        if msg:
            context.add_message("user", msg)
            key = context.answers.pop("_pending_key", None) if isinstance(
                context.answers, dict) else None
            if key:
                context.answers[key] = msg[:400]
            else:
                context.answers[f"q{len(context.answers) + 1}"] = msg[:400]

        # اگر به حد سؤال‌ها رسیدیم، وقت پیشنهاد مسیر است
        answered = len([k for k in context.answers if not k.startswith("_")])
        task = "questioning"
        if context.stage in ("suggestion", "report", "done"):
            task = context.stage
        elif answered >= MAX_QUESTIONS:
            task = "suggestion"

        res = await ask_agent(self.prompt, self._build_payload(context, task),
                              1500, "interview", context.user_id)
        data = extract_json(res.get("text", "")) if res.get("ok") else None

        if not res.get("ok") or not isinstance(data, dict):
            logger.info(f"مصاحبه‌گر: AI در دسترس نبود ({res.get('error', '')})؛ "
                        "سؤال پشتیبان استفاده شد.")
            return self._fallback_turn(context, answered)

        return self._apply(context, data, answered)

    def _apply(self, context: UserJourneyContext, data: dict,
               answered: int) -> dict:
        """اعمال خروجی مدل روی context با اعتبارسنجی کامل."""
        stage = pick(data.get("stage"), _STAGES, "questioning")
        message = (data.get("message") or "").strip()

        # ضدلغزش: مدل نباید قبل از حداقل سؤال‌ها به پیشنهاد بپرد
        if stage in ("suggestion", "report", "done") and answered < MIN_QUESTIONS:
            stage = "questioning"

        if stage == "questioning":
            if not message:
                return self._fallback_turn(context, answered)
            key = (data.get("answer_key") or "").strip()[:40] or f"q{answered + 1}"
            context.answers["_pending_key"] = key
            context.stage = "questioning"
            context.add_message("assistant", message)
            return {
                "ok": True, "stage": "questioning", "message": message,
                "hint": (data.get("hint") or "").strip()[:160],
                "asked": answered + 1, "total": MAX_QUESTIONS,
            }

        if stage == "suggestion":
            paths = self._clean_paths(data.get("paths") or [])
            if not paths:
                paths = self._fallback_paths(context)
            context.suggested_paths = paths
            context.stage = "suggestion"
            if message:
                context.add_message("assistant", message)
            return {"ok": True, "stage": "suggestion",
                    "message": message or "این سه مسیر با پاسخ‌های شما جور است:",
                    "paths": paths}

        if stage == "report":
            report = self._clean_report(data.get("report") or {})
            context.report = report
            context.stage = "report"
            if message:
                context.add_message("assistant", message)
            return {"ok": True, "stage": "report", "message": message,
                    "report": report}

        # done — خروجی JSON نهایی برای ایجنت ۲
        final = self._clean_final(data.get("final_json") or {}, context)
        self._store_final(context, final)
        return {"ok": True, "stage": "done", "message": message,
                "final_json": final}

    # ---------- پشتیبان ----------

    def _fallback_turn(self, context: UserJourneyContext,
                       answered: int) -> dict:
        """وقتی AI در دسترس نیست: سؤال بعدی از فهرست ثابت."""
        if answered < len(FALLBACK_QUESTIONS) and answered < MAX_QUESTIONS:
            q = FALLBACK_QUESTIONS[answered]
            context.answers["_pending_key"] = q["key"]
            context.stage = "questioning"
            context.add_message("assistant", q["text"])
            return {"ok": True, "stage": "questioning", "message": q["text"],
                    "hint": q["hint"], "asked": answered + 1,
                    "total": MAX_QUESTIONS, "fallback": True}

        paths = self._fallback_paths(context)
        context.suggested_paths = paths
        context.stage = "suggestion"
        return {"ok": True, "stage": "suggestion", "fallback": True,
                "message": "بر اساس پاسخ‌هایت، این سه مسیر پیشنهاد من است:",
                "paths": paths}

    def _guess_category(self, context: UserJourneyContext) -> str:
        """حدس دستهٔ شغلی از روی متن پاسخ‌ها — فقط برای حالت fallback."""
        blob = " ".join(str(v) for k, v in (context.answers or {}).items()
                        if not k.startswith("_")).lower()
        table = (
            ("programmer", ("برنامه", "کد", "کدنویس", "پایتون", "python",
                            "جاوا", "java", "وب", "web", "بک‌اند", "backend",
                            "فرانت", "front", "توسعه‌دهنده", "developer")),
            ("designer", ("طراح", "گرافیک", "ui", "ux", "فیگما", "figma",
                          "فتوشاپ", "photoshop", "خلاق")),
            ("marketer", ("مارکتینگ", "بازاریاب", "تبلیغ", "سئو", "seo",
                          "شبکه اجتماعی", "اینستاگرام", "فروش", "محتوا")),
            ("data", ("داده", "دیتا", "data", "آمار", "تحلیل", "هوش مصنوعی",
                      "machine", "یادگیری ماشین", "sql")),
        )
        for cat, keys in table:
            if any(k in blob for k in keys):
                return cat
        return "other"

    def _fallback_paths(self, context: UserJourneyContext) -> list:
        cat = self._guess_category(context)
        return [dict(p, id=i) for i, p in
                enumerate(_FALLBACK_PATHS.get(cat, _FALLBACK_PATHS["other"]), 1)]

    # ---------- اعتبارسنجی ----------

    def _clean_paths(self, raw) -> list:
        out = []
        if not isinstance(raw, list):
            return out
        for i, p in enumerate(raw[:3], 1):
            if not isinstance(p, dict):
                continue
            title = (p.get("title") or "").strip()[:120]
            if not title:
                continue
            out.append({
                "id": i,
                "title": title,
                "why": (p.get("why") or "").strip()[:400],
                "demand": pick(p.get("demand"), _DEMANDS, "medium"),
                "salary_range": (p.get("salary_range") or "").strip()[:120],
                "difficulty": pick(p.get("difficulty"), _DIFFICULTIES, "medium"),
                "fit_percent": clamp_int(p.get("fit_percent"), 0, 100, 70),
                "key_skills": [str(x).strip()[:60]
                               for x in (p.get("key_skills") or [])[:8] if x],
            })
        return out

    def _clean_report(self, raw) -> dict:
        r = raw if isinstance(raw, dict) else {}

        def _list(key, n=8, ln=160):
            return [str(x).strip()[:ln] for x in (r.get(key) or [])[:n] if x]

        return {
            "summary": (r.get("summary") or "").strip()[:900],
            "key_skills": _list("key_skills", 10, 80),
            "tools": _list("tools", 10, 60),
            "ai_tools": _list("ai_tools", 8, 60),
            "duration": (r.get("duration") or "").strip()[:120],
            "opportunities": _list("opportunities"),
            "challenges": _list("challenges"),
        }

    def _clean_final(self, raw, context: UserJourneyContext) -> dict:
        """اعتبارسنجی JSON نهایی — قرارداد ورودی ایجنت ۲."""
        f = raw if isinstance(raw, dict) else {}
        up = f.get("user_profile") if isinstance(f.get("user_profile"), dict) else {}
        sp = f.get("selected_path") if isinstance(f.get("selected_path"), dict) else {}
        ma = f.get("market_analysis") if isinstance(f.get("market_analysis"), dict) else {}

        chosen = context.selected_path or {}
        title = ((sp.get("title") or chosen.get("title")
                  or up.get("target_job") or "مسیر من").strip()[:120])

        profile = {
            "target_job": (up.get("target_job") or title).strip()[:120],
            "category": pick(up.get("category"), _CATEGORIES,
                             self._guess_category(context)),
            "level": pick(up.get("level"), _LEVELS, "beginner"),
            "daily_minutes": clamp_int(up.get("daily_minutes"), 5, 720, 60),
            "learning_style": pick(up.get("learning_style"), _STYLES, "mixed"),
            "motivation": (up.get("motivation") or "").strip()[:300],
            "background": (up.get("background") or "").strip()[:300],
            "constraints": (up.get("constraints") or "").strip()[:300],
            "goal_type": (up.get("goal_type") or "").strip()[:120],
        }
        selected = {
            "title": title,
            "why": (sp.get("why") or chosen.get("why") or "").strip()[:400],
            "difficulty": pick(sp.get("difficulty") or chosen.get("difficulty"),
                               _DIFFICULTIES, "medium"),
            "key_skills": [str(x).strip()[:60] for x in
                           (sp.get("key_skills") or chosen.get("key_skills")
                            or [])[:10] if x],
        }
        market = {
            "demand": pick(ma.get("demand") or chosen.get("demand"),
                           _DEMANDS, "medium"),
            "salary_range": (ma.get("salary_range")
                             or chosen.get("salary_range") or "").strip()[:120],
            "trending_skills": [str(x).strip()[:60] for x in
                                (ma.get("trending_skills") or [])[:10] if x],
            "note": (ma.get("note") or "").strip()[:400],
        }
        tools = [str(x).strip()[:60] for x in
                 (f.get("recommended_tools") or [])[:12] if x]
        if not tools:
            tools = list((context.report or {}).get("tools") or [])[:12]

        return {
            "user_profile": profile,
            "selected_path": selected,
            "market_analysis": market,
            "recommended_tools": tools,
        }

    def _store_final(self, context: UserJourneyContext, final: dict) -> None:
        context.user_profile = final["user_profile"]
        context.selected_path = final["selected_path"]
        context.market_analysis = final["market_analysis"]
        context.recommended_tools = final["recommended_tools"]
        context.stage = "done"
        context.answers.pop("_pending_key", None)

    # ---------- تولید JSON نهایی بدون AI ----------

    def build_final_json(self, context: UserJourneyContext) -> dict:
        """ساخت JSON نهایی از داده‌های موجود، بدون فراخوانی AI.

        وقتی کاربر مسیر را انتخاب و تأیید کرده، همهٔ اطلاعات لازم در
        context هست؛ پس نیازی به یک درخواست اضافه به مدل نیست.
        """
        final = self._clean_final({
            "user_profile": self._profile_from_answers(context),
            "selected_path": context.selected_path or {},
            "market_analysis": {
                "demand": (context.selected_path or {}).get("demand", "medium"),
                "salary_range": (context.selected_path or {}).get("salary_range", ""),
                "trending_skills": (context.report or {}).get("key_skills", []),
                "note": (context.report or {}).get("summary", "")[:400],
            },
            "recommended_tools": ((context.report or {}).get("tools") or [])
            + ((context.report or {}).get("ai_tools") or []),
        }, context)
        self._store_final(context, final)
        return final

    def _profile_from_answers(self, context: UserJourneyContext) -> dict:
        """استخراج پروفایل از پاسخ‌های خام (بدون AI)."""
        a = {k: v for k, v in (context.answers or {}).items()
             if not k.startswith("_")}
        blob = " ".join(str(v) for v in a.values()).lower()

        level = "beginner"
        if any(w in blob for w in ("تجربه دارم", "حرفه", "پیشرفته", "چند سال")):
            level = "advanced"
        elif any(w in blob for w in ("یک‌کم", "یکم", "متوسط", "کمی بلد",
                                     "آشنایی دارم")):
            level = "intermediate"

        style = "mixed"
        if any(w in blob for w in ("عملی", "تمرین", "پروژه", "دست")):
            style = "practical"
        elif any(w in blob for w in ("ویدیو", "فیلم", "تصویر", "دیدن")):
            style = "visual"
        elif any(w in blob for w in ("خوندن", "خواندن", "متن", "کتاب")):
            style = "reading"

        minutes = 60
        for token, val in (("نیم ساعت", 30), ("۱ ساعت", 60), ("1 ساعت", 60),
                           ("۲ ساعت", 120), ("2 ساعت", 120),
                           ("۳ ساعت", 180), ("3 ساعت", 180),
                           ("۴ ساعت", 240), ("4 ساعت", 240)):
            if token in blob:
                minutes = val
                break

        return {
            "target_job": (context.selected_path or {}).get("title", ""),
            "category": self._guess_category(context),
            "level": level,
            "daily_minutes": minutes,
            "learning_style": style,
            "motivation": str(a.get("motivation") or a.get("q1") or "")[:300],
            "background": str(a.get("background") or "")[:300],
            "constraints": str(a.get("constraints") or "")[:300],
            "goal_type": str(a.get("goal_type") or "")[:120],
        }

    # ---------- گزارش پشتیبان ----------

    def fallback_report(self, path: dict) -> dict:
        """گزارش پایه از دادهٔ خود مسیر — وقتی AI در دسترس نیست."""
        p = path or {}
        diff = {"easy": "نسبتاً ساده", "medium": "متوسط",
                "hard": "چالش‌برانگیز"}.get(p.get("difficulty"), "متوسط")
        demand = {"high": "تقاضای بالا", "medium": "تقاضای متوسط",
                  "low": "تقاضای محدود"}.get(p.get("demand"), "تقاضای متوسط")
        return {
            "summary": (f"{p.get('title', 'این مسیر')} در بازار ایران "
                        f"{demand} دارد و سختی آن {diff} است. "
                        + (p.get("why") or "")),
            "key_skills": list(p.get("key_skills") or []),
            "tools": [],
            "ai_tools": [],
            "duration": "",
            "opportunities": [],
            "challenges": [],
        }


__all__ = ["CareerInterviewAgent", "FALLBACK_QUESTIONS",
           "MIN_QUESTIONS", "MAX_QUESTIONS"]
