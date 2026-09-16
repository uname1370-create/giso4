"""
core.py — هستهٔ مشترک معماری چندعاملی (Multi-Agent) «یار هوشمند شغلی».

اینجا فقط دو چیز است:
  ۱. کلاس UserJourneyContext — حافظهٔ کل سفر کاربر (پروفایل، مسیر انتخابی،
     تحلیل بازار، نقشه راه، گام فعلی و تاریخچهٔ چت هر گام).
  ۲. توابع مشترک ایجنت‌ها — بارگذاری پرامپت از فایل txt، فراخوانی AI و
     استخراج امن JSON.

⚠️ نکتهٔ نام‌گذاری: این فایل ai_mentor/core.py است و با core.py سطح ریشهٔ
پروژه فرق دارد. چون این پکیج absolute import می‌کند (`from core import ...`)،
پایتون همچنان core.py ریشه را می‌بیند و تداخلی پیش نمی‌آید. برای دسترسی به
همین فایل از داخل پکیج باید relative import کرد: `from . import core`.

وابستگی: ai_core (برای _ask و _extract_json) و stdlib. هرگز به ai_brain
دست نمی‌زند و هرگز از handlers.py import نمی‌کند.
"""
import json
import logging
import os

logger = logging.getLogger(__name__)

# پوشهٔ پرامپت‌ها — همهٔ پرامپت‌های ایجنت‌ها فایل txt هستند، نه رشتهٔ داخل کد
PROMPTS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "prompts")

# کش پرامپت‌ها — فایل فقط یک بار از دیسک خوانده می‌شود
_PROMPT_CACHE = {}


def load_prompt(filename: str) -> str:
    """خواندن پرامپت یک ایجنت از ai_mentor/prompts/.

    اگر فایل نبود، رشتهٔ خالی برمی‌گردد و ایجنت به fallback داخلی خودش
    می‌افتد؛ پس نبود فایل هرگز ربات را متوقف نمی‌کند.
    """
    name = (filename or "").strip()
    if not name:
        return ""
    if name in _PROMPT_CACHE:
        return _PROMPT_CACHE[name]

    path = os.path.join(PROMPTS_DIR, name)
    try:
        with open(path, "r", encoding="utf-8") as f:
            text = f.read().strip()
        _PROMPT_CACHE[name] = text
        return text
    except FileNotFoundError:
        logger.error(f"پرامپت پیدا نشد: {path}")
    except Exception as e:
        logger.error(f"خواندن پرامپت {name} ناموفق: {e}")
    _PROMPT_CACHE[name] = ""
    return ""


def clear_prompt_cache() -> None:
    """پاک‌کردن کش — برای وقتی ادمین فایل پرامپت را دستی عوض می‌کند."""
    _PROMPT_CACHE.clear()


# ========================= زمینهٔ سفر کاربر =========================

class UserJourneyContext:
    """حافظهٔ کل سفر یک کاربر بین سه ایجنت.

    این شیء بین ایجنت ۱ (مصاحبه‌گر)، ایجنت ۲ (معمار) و ایجنت ۳ (منتور)
    دست‌به‌دست می‌شود. برای ماندگاری، در ستون career_paths.interview_data
    ذخیره می‌گردد (کلید journey) و با from_dict دوباره ساخته می‌شود.
    """

    def __init__(self, user_id):
        self.user_id = int(user_id or 0)
        self.user_profile = {}
        self.selected_path = {}
        self.market_analysis = {}
        self.recommended_tools = []
        self.roadmap = []
        self.current_step = 0
        self.chat_histories = {}      # {step_number: [messages]}

        # ── فیلدهای کمکیِ فلو (در دیتابیس هم ذخیره می‌شوند) ──
        self.stage = "introduction"   # مرحلهٔ ایجنت ۱
        self.answers = {}             # پاسخ‌های خام مصاحبه
        self.conversation = []        # [{"role": "...", "content": "..."}]
        self.suggested_paths = []     # ۳ مسیر پیشنهادی ایجنت ۱
        self.report = {}              # گزارش مسیر انتخابی
        self.weak_topics = []         # حافظهٔ فردی — نقاط ضعف
        self.strong_topics = []       # حافظهٔ فردی — نقاط قوت
        self.path_id = 0              # career_paths.id پس از ذخیره

    # ---------- تاریخچهٔ گفتگو ----------

    def add_message(self, role: str, content: str, limit: int = 40) -> None:
        """افزودن یک پیام به تاریخچهٔ مصاحبه (با سقف برای کنترل حجم)."""
        text = (content or "").strip()
        if not text:
            return
        self.conversation.append({
            "role": "user" if role == "user" else "assistant",
            "content": text[:1200],
        })
        if len(self.conversation) > limit:
            self.conversation = self.conversation[-limit:]

    def conversation_text(self, last: int = 16) -> str:
        """تاریخچهٔ گفتگو به شکل متن، برای تزریق به پرامپت."""
        rows = self.conversation[-last:] if last else self.conversation
        return "\n".join(
            f"{'کاربر' if m['role'] == 'user' else 'مصاحبه‌گر'}: {m['content']}"
            for m in rows
        ) or "(هنوز گفتگویی انجام نشده)"

    def add_step_message(self, step_number, role: str, content: str,
                         limit: int = 12) -> None:
        """افزودن پیام به تاریخچهٔ چتِ یک گام مشخص."""
        key = str(step_number)
        text = (content or "").strip()
        if not text:
            return
        hist = self.chat_histories.setdefault(key, [])
        hist.append({"role": "user" if role == "user" else "assistant",
                     "content": text[:800]})
        if len(hist) > limit:
            self.chat_histories[key] = hist[-limit:]

    def step_history_text(self, step_number, last: int = 6) -> str:
        hist = self.chat_histories.get(str(step_number)) or []
        rows = hist[-last:] if last else hist
        return "\n".join(
            f"{'کاربر' if m['role'] == 'user' else 'منتور'}: {m['content']}"
            for m in rows
        ) or "(این اولین تعامل در این گام است)"

    # ---------- دسترسی به گام‌ها ----------

    def get_step(self, step_number):
        """گام موردنظر از نقشه راه (بر اساس step_number) یا None."""
        try:
            n = int(step_number)
        except Exception:
            return None
        for s in self.roadmap:
            if int(s.get("step_number") or 0) == n:
                return s
        return None

    def answers_text(self) -> str:
        """پاسخ‌های جمع‌آوری‌شده به شکل متن، برای تزریق به پرامپت."""
        if not self.answers:
            return "(هنوز پاسخی ثبت نشده)"
        return "\n".join(f"- {k}: {v}" for k, v in self.answers.items())

    # ---------- تبدیل ----------

    def to_dict(self) -> dict:
        """تبدیل به دیکشنری برای ذخیره در دیتابیس."""
        return {
            "user_profile": self.user_profile or {},
            "selected_path": self.selected_path or {},
            "market_analysis": self.market_analysis or {},
            "recommended_tools": list(self.recommended_tools or []),
            "roadmap": list(self.roadmap or []),
            "current_step": int(self.current_step or 0),
            "chat_histories": self.chat_histories or {},
            "stage": self.stage or "introduction",
            "answers": self.answers or {},
            "conversation": list(self.conversation or [])[-40:],
            "suggested_paths": list(self.suggested_paths or []),
            "report": self.report or {},
            "weak_topics": list(self.weak_topics or [])[-20:],
            "strong_topics": list(self.strong_topics or [])[-20:],
            "path_id": int(self.path_id or 0),
        }

    @classmethod
    def from_dict(cls, user_id, data):
        """ساخت از دیکشنری دیتابیس. هر مقدار خراب بی‌صدا نادیده می‌رود."""
        ctx = cls(user_id)
        d = data if isinstance(data, dict) else {}

        # سازگاری عقب‌رو: مسیرهای قدیمی، persona داشتند نه user_profile
        profile = d.get("user_profile")
        if not isinstance(profile, dict) or not profile:
            profile = d.get("persona") if isinstance(d.get("persona"), dict) else {}

        ctx.user_profile = profile or {}
        ctx.selected_path = d.get("selected_path") if isinstance(d.get("selected_path"), dict) else {}
        ctx.market_analysis = d.get("market_analysis") if isinstance(d.get("market_analysis"), dict) else {}
        ctx.recommended_tools = list(d.get("recommended_tools") or [])
        ctx.roadmap = list(d.get("roadmap") or [])
        ctx.chat_histories = d.get("chat_histories") if isinstance(d.get("chat_histories"), dict) else {}
        ctx.stage = (d.get("stage") or "introduction")
        ctx.answers = d.get("answers") if isinstance(d.get("answers"), dict) else {}
        ctx.conversation = [m for m in (d.get("conversation") or [])
                            if isinstance(m, dict) and m.get("content")]
        ctx.suggested_paths = list(d.get("suggested_paths") or [])
        ctx.report = d.get("report") if isinstance(d.get("report"), dict) else {}
        ctx.weak_topics = list(d.get("weak_topics") or [])
        ctx.strong_topics = list(d.get("strong_topics") or [])

        for key, attr in (("current_step", "current_step"), ("path_id", "path_id")):
            try:
                setattr(ctx, attr, int(d.get(key) or 0))
            except Exception:
                setattr(ctx, attr, 0)
        return ctx

    @classmethod
    def from_path(cls, path: dict):
        """ساخت مستقیم از ردیف career_paths (کلید journey داخل interview_data)."""
        p = path or {}
        idata = p.get("interview_data") or {}
        if not isinstance(idata, dict):
            idata = {}
        journey = idata.get("journey")
        ctx = cls.from_dict(p.get("user_id", 0),
                            journey if isinstance(journey, dict) else idata)
        try:
            ctx.path_id = int(p.get("id") or 0)
        except Exception:
            ctx.path_id = 0
        # حافظهٔ فردی همیشه از سطح بالای interview_data خوانده می‌شود
        ctx.weak_topics = list(idata.get("weak_topics") or ctx.weak_topics)
        ctx.strong_topics = list(idata.get("strong_topics") or ctx.strong_topics)
        return ctx

    def target_job(self) -> str:
        """عنوان شغل هدف — از مسیر انتخابی یا پروفایل."""
        return ((self.selected_path or {}).get("title")
                or (self.user_profile or {}).get("target_job")
                or "مسیر من").strip()[:120]

    def profile_text(self) -> str:
        """پروفایل کاربر به شکل متن، برای تزریق به پرامپت ایجنت‌های ۲ و ۳."""
        p = self.user_profile or {}
        rows = [
            f"- شغل هدف: {p.get('target_job') or self.target_job()}",
            f"- دسته: {p.get('category', 'other')}",
            f"- سطح: {p.get('level', 'beginner')}",
            f"- زمان روزانه: {p.get('daily_minutes', 60)} دقیقه",
            f"- سبک یادگیری: {p.get('learning_style', 'mixed')}",
        ]
        for key, label in (("motivation", "انگیزه"), ("background", "پیشینه"),
                           ("constraints", "محدودیت‌ها"), ("goal_type", "هدف")):
            if p.get(key):
                rows.append(f"- {label}: {p[key]}")
        return "\n".join(rows)

    def __repr__(self) -> str:
        return (f"<UserJourneyContext user={self.user_id} stage={self.stage} "
                f"steps={len(self.roadmap)} current={self.current_step}>")


# ========================= توابع مشترک ایجنت‌ها =========================

def jdump(obj) -> str:
    """JSON فارسی‌خوان برای تزریق به پرامپت."""
    try:
        return json.dumps(obj, ensure_ascii=False, indent=2)
    except Exception:
        return "{}"


def extract_json(text: str):
    """استخراج امن JSON از پاسخ مدل (همان منطق آزمودهٔ ai_core)."""
    from . import ai_core
    return ai_core._extract_json(text)


async def ask_agent(system_prompt: str, user_content: str,
                    max_tokens: int = 1400, action_type: str = "",
                    user_id: int = 0) -> dict:
    """فراخوانی AI برای یک ایجنت.

    از ai_core._ask عبور می‌کند تا مسیریابی مدل، پرامپت سفارشی ادمین و
    ثبت هزینه دقیقاً مثل بقیهٔ ماژول کار کند. ai_core خودش فقط ask_ai و
    ask_ai_fast را از core.py می‌گیرد، پس قانون «AI فقط از core» رعایت است.
    """
    from . import ai_core
    if not (system_prompt or "").strip():
        return {"ok": False, "error": "پرامپت این ایجنت در دسترس نیست."}
    return await ai_core._ask(system_prompt, user_content, max_tokens,
                              action_type, user_id)


def clamp_int(value, low: int, high: int, default: int = 0) -> int:
    """تبدیل امن به عدد صحیح داخل بازه (اعداد فارسی هم پذیرفته می‌شوند)."""
    try:
        if isinstance(value, str):
            value = value.translate(str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩",
                                                  "01234567890123456789"))
            value = "".join(ch for ch in value if ch.isdigit() or ch == "-")
        n = int(value)
    except Exception:
        return default
    return max(low, min(n, high))


def pick(value, allowed, default: str) -> str:
    """اعتبارسنجی مقدار شمارشی (enum) از خروجی مدل."""
    v = (str(value or "")).strip().lower()
    return v if v in allowed else default


__all__ = [
    "PROMPTS_DIR", "UserJourneyContext", "load_prompt", "clear_prompt_cache",
    "ask_agent", "extract_json", "jdump", "clamp_int", "pick",
]
