# -*- coding: utf-8 -*-
"""
giso/ai_runtime_policy.py — سیاست‌های نقش، ثابت‌ها و هلیپرهای خالص runtime AI (Phase 2, Unit U4)
استخراج‌شده از giso/ai_runtime.py بدون تغییر رفتار؛ همه نام‌ها در giso.ai_runtime re-export می‌شوند.
هیچ import داخلی ندارد → بدون ریسک حلقهٔ import.
"""
import json
import re
import threading
import time
from datetime import datetime, timedelta
from typing import Any

_PROVIDER_COOLDOWN_LOCK = threading.Lock()
_PROVIDER_FAIL_COOLDOWNS: dict[str, float] = {}
PROVIDER_FAIL_COOLDOWN_SECONDS = 120
PENDING_ACTION_TTL_MINUTES = 30

OFF_MESSAGE = "🚫 مشاور هوشمند در حال حاضر در دسترس نیست"
NO_ACCESS_MESSAGE = "⛔ متأسفم، امکان چت با مشاور برای شما فراهم نیست"
LIMIT_MESSAGE = "⏱ سهمیه چت روزانه شما تمام شده. لطفاً فردا دوباره امتحان کنید"
PROVIDER_ERROR_MESSAGE = "⚠️ مشاور موقتاً در دسترس نیست، لطفاً بعداً امتحان کنید"
SOON_MESSAGE = "⚠️ این قابلیت به زودی اضافه می‌شود"
OUT_OF_SCOPE_MESSAGE = "این موضوع خارج از محدوده خدمات سایت و ربات گیسو است و من برای آن تعریف نشده‌ام."
NOT_DEFINED_MESSAGE = "این درخواست در ساختار فعلی برای من تعریف نشده و اجازه انجامش را ندارم."
POLICY_DENIED_MESSAGE = "این درخواست خلاف قوانین عملیاتی و سطح دسترسی تعریف‌شده برای من است و اجازه انجامش را ندارم."
NEED_MORE_DETAIL_MESSAGE = "برای انجام این کار به جزئیات دقیق‌تری مثل شناسه، شماره یا مقدار جدید نیاز دارم."

DEFAULT_DISPLAY_NAME = "دستیار هوشمند گیسو"
# فاز ۲ بازنویسی سیستم AI (تصمیم تأییدشده): سرویس‌های رایگان خارجی اول،
# ایرانی‌های پولی وسط، پشتیبان‌ها آخر.
# ۱۴۰۵-۰۶-۱۸: اولویت با رایگان‌های پاسخگو — گوک (۱۴٬۴۰۰ درخواست/روز) اول،
# بعد اوپن‌روتر/سامبانوا/میسترال؛ هوش مصنوعی‌های پولی ایرانی فقط پشتیبان آخر.
# (HuggingFace و Cerebras حذف شدند؛ دستور کارفرما — در پروژه جواب نمی‌دادند.)
DEFAULT_ACTIVE_PROVIDER_ORDER = [
    "groq", "openrouter", "sambanova", "mistral",
    "cloudflare", "gemini", "gapgpt", "avalai",
]

DEFAULT_USER_CAPABILITIES = (
    "برای کاربر عادی مثل یک مشاور دلسوز، صمیمی و همراه رفتار کن. "
    "به تمام اطلاعاتِ خودِ کاربر دسترسی داری (تحلیل، برنامه، محصولات، سفارش‌ها، فروش مو، "
    "کیف پول، بازارچه، مرکز زیبایی، تیکت‌ها و اعلان‌ها) و می‌توانی درباره‌شان گزارش و پیشنهاد و تحلیل بدهی. "
    "فقط گزارش، پیشنهاد و تحلیل بده؛ هرگز هیچ تغییری روی داده‌ها انجام نده. "
    "اگر کاربر دربارهٔ بخشی پرسید که هنوز فعال نکرده، او را قدم‌به‌قدم راهنمایی کن که برای شروع چه کند. "
    "اگر از لحن کاربر نگرانی، استرس، خستگی یا سردرگمی حس کردی، با همدلی جواب بده و قدم‌به‌قدم راهنمایی کن."
)
DEFAULT_ADMIN_CAPABILITIES = (
    "برای ادمین محدود مثل یک دستیار حرفه‌ای، همراه و خوش‌بیان رفتار کن؛ نه مثل ربات خشک. "
    "به او برای گزارش‌گیری، اولویت‌بندی تیکت‌ها، درخواست‌های مشاوره و پیگیری وضعیت‌ها کمک کن. "
    "هیچ اقدام خطرناک یا حذف داده انجام نده."
)
DEFAULT_SUPER_CAPABILITIES = (
    "برای سوپرادمین مثل یک دستیار ارشد مدیریتی، دقیق، محترمانه و فعال رفتار کن. "
    "خودت باید بدانی او سوپرادمین با سطح ۳ است؛ هرگز نپرس سطح دسترسی‌اش چیست و هرگز با او مثل کاربر عادی حرف نزن. "
    "به گزارش زندهٔ همهٔ بخش‌های سایت (سفارش‌ها، تیکت‌ها، فروش مو، کاربران، آنالیزها، کیف پول، وضعیت AI و سلامت عملیات) دسترسی داری. "
    "تحلیل‌هایت قدرتمند، عددی، ساختاریافته و با بخش‌بندی و اولویت‌بندی باشد؛ هرگز جواب ساختگی یا حدسی نده — "
    "اگر دادهٔ زنده بخشی را نداری، صریح بگو «برای این بخش دادهٔ زنده ندارم» و حدس نزن. "
    "در خطایابی دقیق، اول خطا/لاگ واقعی را بررسی کن، علت را بگو و راه‌حل بده. "
    "هر اقدام اجرایی که سوپرادمین بخواهد (تغییر تنظیم، وضعیت، اولویت‌بندی و…) مجاز است، "
    "اما فقط با پیش‌نمایش + تأیید دومرحله‌ای و امکان بازگردانی اجرا شود."
)
LEGACY_SUPER_CAPABILITIES = (
    "برای سوپرادمین مثل یک دستیار ارشد مدیریتی، دقیق، محترمانه و فعال رفتار کن. "
    "خودت باید بدانی او سوپرادمین با سطح ۳ است؛ هرگز نپرس سطح دسترسی‌اش چیست و هرگز با او مثل کاربر عادی حرف نزن. "
    "می‌توانی درباره آمار، گزارش‌ها، وضعیت فروش، تیکت‌ها، درخواست‌ها، سلامت عملیات و پیشنهاد اقدام بعدی کمک کنی، "
    "اما هیچ اقدام اجرایی واقعی بدون تأیید نهایی انجام نده."
)

DEFAULT_SETTINGS = {
    "chat_enabled": "1",
    "chat_display_name": DEFAULT_DISPLAY_NAME,
    "chat_active_provider": "",
    "failover_chain": json.dumps(DEFAULT_ACTIVE_PROVIDER_ORDER, ensure_ascii=False),
    "chat_capabilities_user": DEFAULT_USER_CAPABILITIES,
    "chat_capabilities_admin": DEFAULT_ADMIN_CAPABILITIES,
    "chat_capabilities_super": DEFAULT_SUPER_CAPABILITIES,
    "welcome_inactive_hours": "6",
    "widget_enabled": "1",
    "widget_position": "right-bottom",
    "widget_welcome_message": "سلام ✨ من مشاور هوشمند گیسو هستم و می‌تونم برای شناخت خدمات و مسیر مناسب کمکت کنم.",
    "widget_primary_color": "#e89090",
}

DEFAULT_ROLE_POLICIES = {
    "user": {
        "access_level": 2,
        "sections": ["consultant_chat", "analysis", "plan", "products", "orders"],
        "daily_limit": 10,
    },
    "admin": {
        "access_level": 2,
        "sections": [
            "consultant_chat",
            "admin_test",
            "reports",
            "tickets",
            "consultants",
            "products_edit",
            "users_edit",
        ],
        "daily_limit": 0,
    },
    "super": {
        "access_level": 3,
        "sections": ["*"],
        "daily_limit": 0,
    },
}

ROLE_LABELS = {
    "user": "کاربر عادی",
    "admin": "ادمین محدود",
    "super": "سوپرادمین",
}

SECTION_LABELS = {
    "consultant_chat": "چت مشاور",
    "analysis": "تحلیل‌های خودش",
    "plan": "برنامه و چک‌لیست",
    "products": "محصولات فروشگاه",
    "orders": "سفارش‌های خودش",
    "actions": "اقدامات آینده",
    "reports": "گزارش‌های آمار",
    "tickets": "تیکت‌های پشتیبانی",
    "consultants": "درخواست‌های مشاوره",
    "products_edit": "ویرایش محصولات",
    "users_edit": "ویرایش کاربران",
    "data_delete": "حذف داده‌ها",
    "admin_test": "تست ادمین",
}



def resolve_actor_role(user_id: int | str | None = None, phone: str = "", is_admin: bool = False) -> str:
    """تشخیص نقش اجرایی برای runtime چت: user / admin / super."""
    try:
        from giso.config import is_super_admin as _isa
        if _isa(uid=user_id, phone=phone):
            return "super"
    except Exception:
        pass
    if is_admin:
        return "admin"
    return "user"



def _now_str() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _today_prefix() -> str:
    return datetime.now().strftime("%Y-%m-%d")


def _pending_expires_at_str(minutes: int = PENDING_ACTION_TTL_MINUTES) -> str:
    try:
        ttl = max(1, int(minutes or PENDING_ACTION_TTL_MINUTES))
    except (TypeError, ValueError):
        ttl = PENDING_ACTION_TTL_MINUTES
    return (datetime.now() + timedelta(minutes=ttl)).strftime("%Y-%m-%d %H:%M:%S")



def _provider_in_cooldown(provider_name: str) -> bool:
    name = str(provider_name or "").strip()
    if not name:
        return False
    now_ts = time.time()
    with _PROVIDER_COOLDOWN_LOCK:
        until = float(_PROVIDER_FAIL_COOLDOWNS.get(name) or 0)
        if until <= now_ts:
            _PROVIDER_FAIL_COOLDOWNS.pop(name, None)
            return False
        return True


def _mark_provider_cooldown(provider_name: str, seconds: int = PROVIDER_FAIL_COOLDOWN_SECONDS) -> None:
    name = str(provider_name or "").strip()
    if not name:
        return
    try:
        cooldown = max(10, int(seconds or PROVIDER_FAIL_COOLDOWN_SECONDS))
    except (TypeError, ValueError):
        cooldown = PROVIDER_FAIL_COOLDOWN_SECONDS
    with _PROVIDER_COOLDOWN_LOCK:
        _PROVIDER_FAIL_COOLDOWNS[name] = time.time() + cooldown


def _clear_provider_cooldown(provider_name: str) -> None:
    name = str(provider_name or "").strip()
    if not name:
        return
    with _PROVIDER_COOLDOWN_LOCK:
        _PROVIDER_FAIL_COOLDOWNS.pop(name, None)


def _apply_provider_cooldown(chain: list[str]) -> list[str]:
    ready = []
    cooled = []
    seen = set()
    for provider_name in chain or []:
        name = str(provider_name or "").strip()
        if not name or name in seen:
            continue
        seen.add(name)
        if _provider_in_cooldown(name):
            cooled.append(name)
        else:
            ready.append(name)
    return ready or cooled



def _jloads(text: str | None, default: Any):
    try:
        return json.loads(text) if text else default
    except Exception:
        return default



def _safe_dict(row) -> dict[str, Any]:
    if row is None:
        return {}
    try:
        return dict(row)
    except Exception:
        return {}


def _clean_text(text: str) -> str:
    return str(text or "").strip().replace("ي", "ی").replace("ك", "ک")


def _text_lc(text: str) -> str:
    return _clean_text(text).lower()


def _extract_id_from_text(text: str) -> int | None:
    nums = re.findall(r"\d+", str(text or ""))
    if not nums:
        return None
    try:
        return int(nums[0])
    except Exception:
        return None


def _extract_phone_from_text(text: str) -> str:
    raw = re.sub(r"[^\d+]+", "", str(text or ""))
    if not raw:
        return ""
    try:
        from giso.base import normalize_phone
        return normalize_phone(raw) or ""
    except Exception:
        return raw


def _extract_amount_from_text(text: str) -> int | None:
    nums = re.findall(r"\d+", str(text or ""))
    if not nums:
        return None
    try:
        return int(nums[-1])
    except Exception:
        return None



def _is_smalltalk_request(text: str) -> bool:
    t = _text_lc(text)
    if not t:
        return True
    smalltalks = [
        "سلام", "درود", "خوبی", "حالت چطوره", "چطوری", "مرسی", "ممنون", "خسته نباشی",
        "صبح بخیر", "شب بخیر", "عالی", "اوکی", "باشه", "کمکم کن", "همراهی کن",
        "من سوپر ادمین هستم", "من سوپرادمین هستم", "من مدیرم", "من ادمینم",
    ]
    if t in smalltalks:
        return True
    if len(t) <= 20 and any(s in t for s in smalltalks):
        return True
    return False


def _looks_like_general_management_chat(text: str) -> bool:
    t = _text_lc(text)
    general_needles = [
        "کمکم کن", "راهنمایی", "چطور", "چجوری", "به نظرت", "پیشنهاد", "اولویت", "استراتژی",
        "برنامه", "بهبود", "چی کار کنم", "از کجا شروع", "در مورد", "میخوام بدونم", "می‌خوام بدونم",
    ]
    return any(n in t for n in general_needles)





# ── بازرس هوشمند: گزارش‌های قطعی سوپرادمین (ثابت‌ها + هلیپرهای خالص) ──
INSPECTOR_REPORT_ACTIONS = {
    "report_incidents": {"kind": "report", "table": "multiple", "description": "گزارش خطایابی و باگ‌ها"},
    "report_insights": {"kind": "report", "table": "multiple", "description": "گزارش پیشنهادهای بهبود"},
    "report_health": {"kind": "report", "table": "multiple", "description": "گزارش سلامت سرویس‌ها"},
}
INSPECTOR_REPORT_SCOPES = {name: "reports" for name in INSPECTOR_REPORT_ACTIONS}

_INSPECTOR_KEYWORDS = (
    "خطایاب", "عیب‌یاب", "عیب یاب", "باگ", "خطاها", "چه خطایی", "مشکل سیستم", "ارور", "گزارش خطا",
)
_INSPECTOR_IMPROVE_KEYWORDS = ("پیشنهاد بهبود", "بهبود سایت", "بهبود ربات", "توصیه بهبود", "بازرس هوشمند")
_INSPECTOR_HEALTH_KEYWORDS = (
    "سلامت سرویس", "سلامت سیستم", "وضعیت سرویس", "سلامت سرور",
    "سالم بودن", "همه چیز عادی", "وضعیت کلی سیستم",
)


_FORCE_REFRESH_PHRASES = (
    "همین الان", "دوباره بگیر", "کش رو نادیده", "کش را نادیده", "از نو",
    "تازه کن", "تازه بگیر", "بدون کش",
)


def detect_force_refresh(text: str) -> bool:
    """عبارات تازه/کش‌نشکن → گزارش باید از دیتابیس زنده بیاید."""
    t = _text_lc(text)
    if not t:
        return False
    if any(p in t for p in _FORCE_REFRESH_PHRASES):
        return True
    if "تازه" in t and any(x in t for x in ("گزارش", "لیست", "آمار", "وضعیت")):
        return True
    if t.startswith("الان ") and any(x in t for x in ("گزارش", "لیست", "آمار", "بگیر")):
        return True
    return False


def detect_inspector_report(text_l: str) -> str:
    if any(x in text_l for x in _INSPECTOR_KEYWORDS):
        return "report_incidents"
    if any(x in text_l for x in _INSPECTOR_IMPROVE_KEYWORDS):
        return "report_insights"
    if any(x in text_l for x in _INSPECTOR_HEALTH_KEYWORDS):
        return "report_health"
    return ""


def inspector_report(action_name: str) -> str:
    """گزارش قطعی بازرس هوشمند (بدون تماس AI؛ لود lazy تا حلقهٔ import نشود)."""
    try:
        from giso.monitoring_insights import incidents_report, improvements_report, health_report
        if action_name == "report_incidents":
            return incidents_report(limit=8)
        if action_name == "report_insights":
            return improvements_report(limit=8)
        if action_name == "report_health":
            return health_report()
    except Exception as e:
        labels = {
            "report_incidents": "خطایابی",
            "report_insights": "بهبود",
            "report_health": "سلامت",
        }
        return f"⚠️ خطا در گزارش {labels.get(action_name, action_name)}: {e}"
    return "⚠️ گزارش ناشناخته."


def _extract_name_candidate(text: str) -> str:
    s = _clean_text(text)
    patterns = [
        r'(?:اسم|نام)\s+(?:مشاور|هوش مصنوعی|AI)?\s*(?:را|رو)?\s*(?:بذار|بگذار|کن|کنش|تغییر بده)?\s*(?:روی|به)?\s*([^\n]+)',
    ]
    for pat in patterns:
        m = re.search(pat, s, flags=re.IGNORECASE)
        if m:
            cand = _clean_text(m.group(1))
            cand = re.sub(r"^(روی|به)\s+", "", cand).strip()
            cand = re.sub(r"\s+(بذار|بگذار|کن|کنش|تغییر بده)$", "", cand).strip()
            if cand:
                return cand[:40]
    return ""


def _extract_provider_candidate(text: str) -> str:
    t = _text_lc(text)
    for name in DEFAULT_ACTIVE_PROVIDER_ORDER:
        if name in t:
            return name
    return ""
