"""
core.py — منطق کسب‌وکار
وابستگی مجاز: فقط config و کتابخانه‌های استاندارد + telegram.Bot
هرگز از ui یا handlers import نکنید.
"""
import asyncio
import time
import logging
import re
import secrets
import contextvars

from config import (
    ADMIN_IDS, BOT_USERNAME, SUPPORT_GROUP,
    COURSES, PROGRESS, USERS, SETTINGS, SHOP, MISSIONS,
    FEATURE_ACCESS,
    USER_FEATURE_RESTRICTIONS, CASH_SALE_SETTINGS,
    PLATFORM_LINKS, LINK_CODES, ADMIN_LINK_CODES, PLATFORM_ADMINS,
    BOT_GROUPS,
    save,
)
import config as _config  # برای دسترسی live به _config._app_bot در notify_level_up

logger = logging.getLogger(__name__)


# ========================= چندپلتفرمی — تعاریف پایه =========================

PLATFORMS = {
    "bale":     {"name": "بله",    "deep_link": "https://ble.ir/{bot}?start={payload}"},
    "telegram": {"name": "تلگرام", "deep_link": "https://t.me/{bot}?start={payload}"},
}
# پلتفرم‌های ثانویه (غیر از بله). روبیکا و ایتا در دور هفتم کاملاً حذف شدند.
SECONDARY_PLATFORMS = ["telegram"]

LINK_CODE_TTL  = 24 * 3600   # انقضای کد اتصال کاربر (ثانیه)
ADMIN_LINK_TTL = 24 * 3600   # انقضای لینک ادمینی (ثانیه)

# پلتفرم فعلیِ هر update — task-local (هر update در task جدا پردازش می‌شود)
_current_platform = contextvars.ContextVar("current_platform", default="bale")


def set_current_platform(platform: str):
    _current_platform.set(platform or "bale")


def get_current_platform() -> str:
    return _current_platform.get()


def detect_platform(bot=None) -> str:
    """تشخیص پلتفرم از روی نمونه bot (base_url یا attr صریح)."""
    if bot is None:
        return "bale"
    p = getattr(bot, "_platform", None)
    if p:
        return p
    base = (getattr(bot, "base_url", "") or "").lower()
    if "bale.ai" in base:
        return "bale"
    if "telegram.org" in base:
        return "telegram"
    return "bale"


def platform_name(platform: str) -> str:
    return PLATFORMS.get(platform, {}).get("name", platform)


def platform_enabled(platform: str) -> bool:
    if platform == "bale":
        return True
    return str(SETTINGS.get(f"{platform}_enabled", 0)) in ("1", "True", "true")


def platform_token(platform: str) -> str:
    if platform == "telegram":
        return str(SETTINGS.get("telegram_token", "") or "")
    return ""


def platform_configured(platform: str) -> bool:
    if platform == "bale":
        return True
    return bool(platform_token(platform))


def platform_username(platform: str) -> str:
    if platform == "bale":
        return BOT_USERNAME
    return str(SETTINGS.get(f"{platform}_username", "") or "")


def build_deep_link(platform: str, payload: str) -> str:
    user = platform_username(platform)
    tmpl = PLATFORMS.get(platform, {}).get("deep_link", "")
    if not user or not tmpl:
        return ""
    return tmpl.format(bot=user, payload=payload)


# پایه‌ی آدرس وب هر پلتفرم — برای ساخت لینک پشتیبانی/دعوت
_PLATFORM_WEB_BASE = {
    "bale":     "https://ble.ir/",
    "telegram": "https://t.me/",
}


def platform_invite_link(platform: str, payload) -> str:
    """لینک دعوت/اتصال مخصوص هر پلتفرم با پیلودِ مشترک (شناسه کاربر اصلی)."""
    link = build_deep_link(platform, str(payload))
    if link:
        return link
    # اگر نام کاربری ربات آن پلتفرم ثبت نشده، برای بله از BOT_USERNAME استفاده کن
    if platform == "bale":
        return f"https://ble.ir/{BOT_USERNAME}?start={payload}"
    return ""


def platform_bot_link(platform: str = None) -> str:
    """لینک خانهٔ ربات در پلتفرم (بدون پیلود) — برای خوشامد گروه و معرفی."""
    p = platform or get_current_platform()
    user = platform_username(p)
    base = _PLATFORM_WEB_BASE.get(p, "https://ble.ir/")
    if not user:
        if p == "bale":
            user = BOT_USERNAME
            base = "https://ble.ir/"
        else:
            return ""
    return base + user


def support_link(platform: str = None):
    """لینک پشتیبانی بسته به پلتفرم فعلی.
    خروجی: (display, url)
    - اگر ادمینِ آن پلتفرم آیدی/لینک پشتیبانی اختصاصی ثبت کرده باشد، همان استفاده می‌شود.
    - در غیر این صورت، پیش‌فرض = گروه پشتیبانی بله.
    """
    p = platform or get_current_platform()
    raw = ""
    if p and p != "bale":
        raw = str(SETTINGS.get(f"{p}_support", "") or "").strip()
    if raw:
        if raw.startswith("http"):
            return raw, raw
        uname = raw.lstrip("@")
        base = _PLATFORM_WEB_BASE.get(p, "https://t.me/")
        disp = raw if raw.startswith("@") else f"@{uname}"
        return disp, base + uname
    grp = SUPPORT_GROUP
    return grp, f"https://ble.ir/{grp.lstrip('@')}"


# ========================= نمایش اعداد فارسی =========================

_FA_DIGITS = str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹")


def fa_num(n) -> str:
    """تبدیل عدد به رشتهٔ فارسی با جداکنندهٔ هزارگان (مثلاً ۱٬۲۳۴)."""
    try:
        s = f"{int(n):,}".replace(",", "٬")
    except Exception:
        s = str(n)
    return s.translate(_FA_DIGITS)


def members_count() -> int:
    """تعداد کل اعضای واقعیِ ثبت‌شده (دارای شماره) — هویت یکتا بر اساس کاربر اصلی.
    کاربری که با یک شماره هم در بله و هم در تلگرام است، یک نفر شمرده می‌شود
    (چون به یک رکورد کاربر اصلی متصل است). ادمین‌ها شمرده نمی‌شوند."""
    cnt = 0
    for uid_str, u in USERS.items():
        if not u.get("phone"):
            continue
        try:
            if int(u.get("id", uid_str)) in ADMIN_IDS:
                continue
        except Exception:
            pass
        cnt += 1
    return cnt


# ========================= چندپلتفرمی — هویت =========================

def canonical_user_id(platform: str, platform_user_id):
    """نگاشت شناسه پلتفرم به کاربر اصلی (canonical). برای بله = همان id."""
    if platform == "bale":
        try:
            return int(platform_user_id)
        except Exception:
            return None
    link = PLATFORM_LINKS.get(f"{platform}:{platform_user_id}")
    return int(link["user_id"]) if link else None


def is_platform_admin(platform: str, platform_user_id) -> bool:
    return f"{platform}:{platform_user_id}" in PLATFORM_ADMINS


class _IdentityUser:
    """نمایندهٔ کاربرِ اصلی (canonical) با حفظ نام/نام‌کاربریِ پلتفرمِ مبدا.
    وقتی کاربری در تلگرام (یا پلتفرم ثانویه) با شماره به یک حساب بله وصل می‌شود،
    در همهٔ منطق داخلی با شناسهٔ اصلی (بله) کار می‌کنیم اما نام نمایشی از تلگرام می‌آید."""
    __slots__ = ("id", "first_name", "last_name", "username", "is_bot", "_raw")

    def __init__(self, canonical_id, raw):
        self.id = int(canonical_id)
        self.first_name = getattr(raw, "first_name", "") or ""
        self.last_name = getattr(raw, "last_name", "") or ""
        self.username = getattr(raw, "username", "") or ""
        self.is_bot = getattr(raw, "is_bot", False)
        self._raw = raw

    @property
    def full_name(self):
        return (f"{self.first_name} {self.last_name}").strip() or self.first_name


def platform_raw_id(user):
    """شناسهٔ واقعی پلتفرم (قبل از نگاشت به کاربر اصلی)."""
    raw = getattr(user, "_raw", None)
    return raw.id if raw is not None else user.id


def effective_user(raw_user, platform: str = None):
    """کاربر مؤثر برای منطق داخلی: روی بله = همان کاربر؛ روی پلتفرم ثانویهٔ متصل =
    نمایندهٔ کاربر اصلی با شناسهٔ canonical (تا XP/اعتبار/ادمین مشترک باشد)."""
    if raw_user is None:
        return raw_user
    p = platform or get_current_platform()
    if p == "bale":
        return raw_user
    cuid = canonical_user_id(p, raw_user.id)
    if cuid is None or int(cuid) == int(raw_user.id):
        return raw_user
    return _IdentityUser(cuid, raw_user)


# ========================= ابزار عمومی =========================

def is_admin(user, platform: str = None) -> bool:
    """تشخیص ادمین — افزایشی و چندپلتفرمی.
    کار با کاربرِ خام پلتفرم یا کاربرِ مؤثر (canonical) هر دو سازگار است.
    - وراثت ادمینی بر اساس شماره: اگر کاربر اصلی در ADMIN_IDS باشد، در همهٔ پلتفرم‌ها ادمین است.
    - یا ادمینِ مستقیماً ثبت‌شدهٔ همان پلتفرم (لینک ادمینی)."""
    if user is None:
        return False
    p = platform or get_current_platform()
    # کاربر اصلیِ مؤثر اگر ادمین بله باشد (وراثت ادمینی)
    if user.id in ADMIN_IDS:
        return True
    raw_id = platform_raw_id(user)
    if raw_id in ADMIN_IDS:
        return True
    # ادمینِ ثبت‌شدهٔ همان پلتفرم با شناسهٔ واقعی پلتفرم
    if is_platform_admin(p, raw_id):
        return True
    # نگاشت شناسهٔ واقعیِ پلتفرم به کاربر اصلی، سپس بررسی ادمین بودنِ آن
    cuid = canonical_user_id(p, raw_id)
    if cuid is not None and cuid in ADMIN_IDS:
        return True
    return False


def ltype(t: str) -> str:
    return {
        "text":         "📝 متن",
        "link":         "🔗 لینک",
        "photo":        "🖼 عکس",
        "video":        "🎬 ویدیو",
        "document":     "📎 فایل",
        "channel_post": "📨 پست کانال",
    }.get(t, t or "نامشخص")


def next_cid() -> str:
    nums = [int(k[1:]) for k in COURSES if k.startswith("c") and k[1:].isdigit()]
    return f"c{max(nums, default=0) + 1}"


def next_sid() -> str:
    nums = [int(k[1:]) for k in SHOP if k.startswith("s") and k[1:].isdigit()]
    return f"s{max(nums, default=0) + 1}"


def next_lid() -> str:
    return f"l{int(time.time() * 1000) % 100000000}"


def next_mid() -> str:
    ids = [
        int(m["id"][1:]) for m in MISSIONS
        if str(m.get("id", "")).startswith("m") and str(m.get("id", ""))[1:].isdigit()
    ]
    return f"m{max(ids, default=0) + 1}"


# ========================= مایگریشن کاربر =========================

def _migrate_user(u: dict) -> dict:
    """اطمینان از وجود فیلدهای جدید در کاربران قدیمی"""
    if "xp" not in u:
        u["xp"] = u.get("points", 0)
    if "credits" not in u:
        u["credits"] = 0
    u.setdefault("completed_missions", [])
    u.setdefault("credits_paid", {})
    u.setdefault("level_announced", 0)
    u.setdefault("pending_level_up", None)
    u.setdefault("phone", "")
    return u


# ========================= سیستم کاربران =========================

USER_LEVELS = [
    {"icon": "🌱", "title": "تازه‌کار",   "threshold": 0},
    {"icon": "📗", "title": "یادگیرنده", "threshold": 50},
    {"icon": "📘", "title": "کوشا",       "threshold": 150},
    {"icon": "📕", "title": "حرفه‌ای",    "threshold": 350},
    {"icon": "🎓", "title": "متخصص",     "threshold": 600},
    {"icon": "🏅", "title": "استاد",      "threshold": 1000},
    {"icon": "💎", "title": "نخبه",       "threshold": 1500},
]

EDUCATIONAL_RANKS = [
    {"title": "مبتدی",      "threshold": 0,    "icon": "🔰"},
    {"title": "پایه",       "threshold": 30,   "icon": "📌"},
    {"title": "متوسط",      "threshold": 100,  "icon": "📐"},
    {"title": "پیشرفته",    "threshold": 250,  "icon": "📡"},
    {"title": "ماهر",       "threshold": 500,  "icon": "🔬"},
    {"title": "خبره",       "threshold": 900,  "icon": "🏆"},
    {"title": "قهرمان",     "threshold": 1400, "icon": "🌟"},
]

# حد فاصل ثبت last_active (ثانیه) — برای کاهش save‌های غیرضروری
_LAST_ACTIVE_THROTTLE = 60


def register_user(user, referrer_id=None):
    """
    ثبت یا به‌روزرسانی کاربر.
    برای کاربران موجود، فقط زمانی save می‌زند که داده‌ای واقعاً تغییر کرده باشد.
    last_active حداکثر هر 60 ثانیه یکبار ذخیره می‌شود.
    """
    uid = str(user.id)
    now = int(time.time())

    if uid not in USERS:
        # کاربر جدید — همه فیلدها را بساز و یکبار save کن
        USERS[uid] = {
            "id": user.id,
            "first_name": user.first_name or "",
            "username": user.username or "",
            "joined": now,
            "last_active": now,
            "points": 0,
            "xp": 0,
            "credits": 0,
            "referrer": referrer_id,
            "referrals": [],
            "level_announced": 0,
            "pending_level_up": None,
            "completed_missions": [],
            "credits_paid": {},
        }
        if referrer_id and str(referrer_id) != uid and referrer_id not in ADMIN_IDS:
            ref = USERS.get(str(referrer_id))
            if ref:
                _migrate_user(ref)
                refs_list = ref.setdefault("referrals", [])
                exists = any(
                    (isinstance(r, dict) and r.get("id") == user.id) or
                    (isinstance(r, int) and r == user.id)
                    for r in refs_list
                )
                if not exists:
                    refs_list.append({"id": user.id, "time": now})
                    # XP برای referrer — save داخل award_xp_and_credits انجام می‌شود
                    award_xp_and_credits(int(str(referrer_id)), xp_amount=10, credits_amount=5)
                    return  # award_xp_and_credits قبلاً save کرده
        save("users")
    else:
        u = USERS[uid]
        changed = False

        # به‌روزرسانی last_active — حداکثر هر 60 ثانیه
        if u.get("last_active", 0) < now - _LAST_ACTIVE_THROTTLE:
            u["last_active"] = now
            changed = True

        # به‌روزرسانی اطلاعات پروفایل — فقط اگر تغییر کرده
        new_fn = user.first_name or ""
        new_un = user.username or ""
        if u.get("first_name") != new_fn:
            u["first_name"] = new_fn
            changed = True
        if u.get("username") != new_un:
            u["username"] = new_un
            changed = True

        _migrate_user(u)

        if changed:
            save("users")


def get_user_xp(uid) -> int:
    u = USERS.get(str(uid))
    if not u:
        return 0
    _migrate_user(u)
    return u.get("xp", u.get("points", 0))


def get_user_credits(uid) -> int:
    u = USERS.get(str(uid))
    if not u:
        return 0
    _migrate_user(u)
    return u.get("credits", 0)


def get_level_info(xp: int):
    level = USER_LEVELS[0]
    for lvl in USER_LEVELS:
        if xp >= lvl["threshold"]:
            level = lvl
        else:
            break
    current_index = USER_LEVELS.index(level)
    next_level = USER_LEVELS[current_index + 1] if current_index + 1 < len(USER_LEVELS) else None
    return level, next_level, current_index


def get_level_progress(xp: int):
    current, next_level, current_index = get_level_info(xp)
    if not next_level:
        return current, None, 100
    progress = xp - current["threshold"]
    total = next_level["threshold"] - current["threshold"]
    percent = int(progress * 100 / total) if total else 100
    return current, next_level, percent


def get_educational_rank(xp: int) -> dict:
    rank = EDUCATIONAL_RANKS[0]
    for r in EDUCATIONAL_RANKS:
        if xp >= r["threshold"]:
            rank = r
        else:
            break
    return rank


async def notify_level_up(uid, level, ctx=None, chat_id=None):
    """
    ارسال پیام تبریک ارتقاء سطح.
    اولویت: ctx.bot → _app_bot (ذخیره‌شده در config) → لاگ خطا
    """
    u = USERS.get(str(uid))
    if not u:
        return
    _migrate_user(u)
    text = (
        "🎉 تبریک!\n"
        "شما به سطح جدید ارتقاء پیدا کردید.\n"
        f"{level['icon']} سطح جدید: {level['title']}\n"
        f"📈 امتیاز رشد (XP): {u.get('xp', 0)}\n"
        f"💰 اعتبار: {u.get('credits', 0)}"
    )

    # تعیین chat_id
    if chat_id is None and ctx is not None:
        chat = getattr(ctx, "effective_chat", None) or getattr(ctx, "_effective_chat", None)
        chat_id = getattr(chat, "id", None)
    if chat_id is None:
        chat_id = uid

    # انتخاب bot instance
    bot = None
    if ctx is not None and hasattr(ctx, "bot"):
        bot = ctx.bot
    elif _config._app_bot is not None:
        bot = _config._app_bot

    if bot is None:
        logger.warning(f"notify_level_up: نمونه bot موجود نیست، ارسال پیام سطح به {uid} ممکن نشد.")
        return

    try:
        await bot.send_message(chat_id=chat_id, text=text)
    except Exception as e:
        logger.error(f"Level-up notify error for uid={uid}: {e}")


def award_xp_and_credits(uid, xp_amount: int = 0, credits_amount: int = 0, ctx=None, chat_id=None):
    """
    اعطای امتیاز رشد و اعتبار به کاربر.
    تنها یک بار save می‌زند (همه تغییرات یکجا).
    """
    if uid in ADMIN_IDS or (xp_amount <= 0 and credits_amount <= 0):
        return
    u = USERS.get(str(uid))
    if not u:
        return
    _migrate_user(u)

    old_xp = u.get("xp", 0)
    _, _, old_index = get_level_info(old_xp)

    if xp_amount > 0:
        u["xp"] = old_xp + xp_amount
        u["points"] = u["xp"]  # backward compat

    if credits_amount > 0:
        u["credits"] = u.get("credits", 0) + credits_amount

    # بررسی ارتقاء سطح — قبل از save، همه تغییرات را یکجا اعمال کن
    level_up_data = None
    if xp_amount > 0:
        _, _, new_index = get_level_info(u["xp"])
        if new_index > old_index:
            announced = u.get("level_announced", old_index)
            if new_index > announced:
                u["level_announced"] = new_index
                level_up_data = USER_LEVELS[new_index]

    # یک save برای همه تغییرات
    save("users")

    # ارسال پیام ارتقاء سطح (async، خارج از save)
    if level_up_data is not None:
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(
                notify_level_up(uid, level_up_data, ctx=ctx, chat_id=chat_id)
            )
        except RuntimeError:
            pass


def award_points(uid, amount: int, ctx=None, chat_id=None, reason=None):
    """backward compat — فقط XP می‌دهد"""
    award_xp_and_credits(uid, xp_amount=amount, credits_amount=0, ctx=ctx, chat_id=chat_id)


def add_points(uid, amount: int):
    award_xp_and_credits(uid, xp_amount=amount, credits_amount=0)


def change_credits(uid, amount: int):
    """تغییر اعتبار (منفی برای خرج، مثبت برای اضافه)"""
    if uid in ADMIN_IDS or amount == 0:
        return
    u = USERS.get(str(uid))
    if not u:
        return
    _migrate_user(u)
    u["credits"] = max(0, u.get("credits", 0) + amount)
    save("users")


# ========================= مدیریت کاربران توسط ادمین =========================

def set_user_xp(uid, value: int):
    """تنظیم مستقیم XP کاربر (ادمین)"""
    u = USERS.get(str(uid))
    if not u:
        return False
    _migrate_user(u)
    u["xp"] = max(0, int(value))
    u["points"] = u["xp"]
    save("users")
    return True


def add_user_xp(uid, delta: int):
    """افزودن/کاستن XP کاربر (ادمین)"""
    u = USERS.get(str(uid))
    if not u:
        return False
    _migrate_user(u)
    u["xp"] = max(0, u.get("xp", 0) + int(delta))
    u["points"] = u["xp"]
    save("users")
    return True


def set_user_credits(uid, value: int):
    """تنظیم مستقیم اعتبار کاربر (ادمین)"""
    u = USERS.get(str(uid))
    if not u:
        return False
    _migrate_user(u)
    u["credits"] = max(0, int(value))
    save("users")
    return True


def add_user_credits(uid, delta: int):
    """افزودن/کاستن اعتبار کاربر (ادمین)"""
    u = USERS.get(str(uid))
    if not u:
        return False
    _migrate_user(u)
    u["credits"] = max(0, u.get("credits", 0) + int(delta))
    save("users")
    return True


def set_user_ban(uid, banned: bool, until_ts: int = 0):
    """بن/آنبن کردن کاربر — until_ts=0 یعنی دائم، >0 یعنی تایمردار"""
    u = USERS.get(str(uid))
    if not u:
        return False
    u["is_banned"] = banned
    u["ban_until"] = until_ts if (banned and until_ts > 0) else 0
    save("users")
    return True


def set_user_mute(uid, until: int):
    """میوت کردن کاربر تا زمان مشخص (0 = آنمیوت)"""
    u = USERS.get(str(uid))
    if not u:
        return False
    u["is_muted"] = until > int(time.time())
    u["mute_until"] = until
    save("users")
    return True


def is_user_banned(uid) -> bool:
    u = USERS.get(str(uid))
    if not u or not u.get("is_banned", False):
        return False
    ban_until = u.get("ban_until", 0)
    if ban_until > 0 and int(time.time()) >= ban_until:
        u["is_banned"] = False
        u["ban_until"] = 0
        save("users")
        return False
    return True


def is_user_muted(uid) -> bool:
    u = USERS.get(str(uid))
    if not u:
        return False
    if u.get("is_muted", False):
        if u.get("mute_until", 0) > int(time.time()):
            return True
        else:
            u["is_muted"] = False
    return False


# ========================= سیستم ثبت شماره تلفن =========================


def normalize_phone(raw: str):
    """
    اعتبارسنجی و نرمال‌سازی شماره موبایل ایران.
    ورودی‌های مجاز: 09xxxxxxxxx ، +989xxxxxxxx ، 00989xxxxxxxx ، 9xxxxxxxxx
    خروجی: فرمت استاندارد «+989xxxxxxxx» یا None اگر نامعتبر بود.

    پیاده‌سازی از phoneutil به‌صورت اشتراکی استفاده می‌کند تا فرمت همه‌جا یکسان باشد.
    """
    try:
        from phoneutil import normalize_phone as _np
        norm = _np(raw)
        return norm or None
    except Exception:
        # Fallback امن در صورت نبود phoneutil
        if not raw:
            return None
        _DIGIT_MAP = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")
        s = str(raw).strip().translate(_DIGIT_MAP)
        s = re.sub(r"[\s\-()]", "", s)
        if s.startswith("0098"):
            s = "+98" + s[4:]
        if s.startswith("+98"):
            rest = s[3:]
        elif s.startswith("98") and len(s) == 12:
            rest = s[2:]
        elif s.startswith("0"):
            rest = s[1:]
        else:
            rest = s
        if len(rest) == 10 and rest.isdigit() and rest.startswith("9"):
            return "+98" + rest
        return None


def get_user_phone(uid) -> str:
    u = USERS.get(str(uid))
    if not u:
        return ""
    return u.get("phone", "") or ""


def has_phone(uid) -> bool:
    return bool(get_user_phone(uid))


def phone_owner(phone: str):
    """اگر این شماره قبلاً برای کاربر دیگری ثبت شده باشد، شناسه آن کاربر را برمی‌گرداند."""
    norm = normalize_phone(phone)
    if not norm:
        return None
    for uid_str, u in USERS.items():
        if (u.get("phone", "") or "") == norm:
            return int(uid_str)
    return None


def set_user_phone(uid, phone: str):
    """
    ثبت شماره برای کاربر پس از اعتبارسنجی و بررسی تکراری‌نبودن.
    خروجی: (ok: bool, result: str)
      - ok=True  → result = شماره استاندارد ثبت‌شده
      - ok=False → result = پیام خطا
    """
    norm = normalize_phone(phone)
    if not norm:
        return False, "invalid"
    owner = phone_owner(norm)
    if owner is not None and owner != int(uid):
        return False, "duplicate"
    u = USERS.get(str(uid))
    if not u:
        return False, "no_user"
    _migrate_user(u)
    u["phone"] = norm
    save("users")
    return True, norm


# ========================= چندپلتفرمی — کد اتصال کاربر =========================

def _gen_code(prefix: str) -> str:
    return f"{prefix}{secrets.token_hex(5)}"


def user_has_platform(user_id, platform: str) -> bool:
    """آیا این کاربر اصلی قبلاً به این پلتفرم متصل شده است؟"""
    for v in PLATFORM_LINKS.values():
        if v.get("platform") == platform and int(v.get("user_id", 0)) == int(user_id):
            return True
    return False


def create_link_code(user_id: int, platform: str, mission_id: str = "", ttl: int = LINK_CODE_TTL) -> str:
    code = _gen_code("u")
    now = int(time.time())
    LINK_CODES[code] = {
        "code": code, "user_id": int(user_id), "platform": platform,
        "mission_id": mission_id or "", "created_at": now,
        "expires_at": now + ttl, "used": 0, "used_at": 0, "used_by": "",
    }
    save("link_codes")
    return code


def validate_link_code(code: str, platform: str = None):
    """خروجی: (info|None, status)"""
    info = LINK_CODES.get(code)
    if not info:
        return None, "not_found"
    if info.get("used"):
        return None, "used"
    if info.get("expires_at", 0) and int(time.time()) > info["expires_at"]:
        return None, "expired"
    if platform and info.get("platform") != platform:
        return None, "wrong_platform"
    return info, "ok"


def connect_user_to_platform(platform: str, platform_user_id, code: str):
    """مصرف کد در پلتفرم مقصد و ثبت نگاشت.
    خروجی: (ok, user_id, mission_id, status)"""
    key = f"{platform}:{platform_user_id}"
    # idempotent — اگر این کاربرِ پلتفرم از قبل متصل است، خطا نده و دوباره جایزه نده
    if key in PLATFORM_LINKS:
        existing = PLATFORM_LINKS[key]
        info0 = LINK_CODES.get(code) or {}
        return True, int(existing.get("user_id", 0)), info0.get("mission_id", ""), "already"
    info, status = validate_link_code(code, platform)
    if not info:
        return False, None, "", status
    user_id = int(info["user_id"])
    PLATFORM_LINKS[key] = {
        "platform": platform, "platform_user_id": str(platform_user_id),
        "user_id": user_id, "connected_at": int(time.time()), "via": "link",
    }
    save("platform_links")
    info["used"] = 1
    info["used_at"] = int(time.time())
    info["used_by"] = str(platform_user_id)
    save("link_codes")
    return True, user_id, info.get("mission_id", ""), "ok"


def link_user_by_phone(platform: str, platform_user_id, owner_user_id: int) -> bool:
    """ادغام بر اساس شماره تلفن — نگاشت کاربر پلتفرم به کاربر اصلیِ صاحب شماره."""
    key = f"{platform}:{platform_user_id}"
    if key in PLATFORM_LINKS:
        return False
    now = int(time.time())
    PLATFORM_LINKS[key] = {
        "platform": platform, "platform_user_id": str(platform_user_id),
        "user_id": int(owner_user_id), "connected_at": now, "via": "phone",
        "last_active": now, "interactions": 0,
    }
    save("platform_links")
    return True


def touch_platform_activity(platform: str, platform_user_id):
    """به‌روزرسانی سبکِ فعالیت یک اتصال پلتفرم (last_active + شمارندهٔ تعامل).
    برای گزارش «فعال‌ترین پلتفرم» استفاده می‌شود. throttle مثل register_user."""
    if not platform or platform == "bale":
        return
    link = PLATFORM_LINKS.get(f"{platform}:{platform_user_id}")
    if not link:
        return
    now = int(time.time())
    if link.get("last_active", 0) < now - _LAST_ACTIVE_THROTTLE:
        link["last_active"] = now
        link["interactions"] = int(link.get("interactions", 0)) + 1
        save("platform_links")


def credit_referral(new_user_id, referrer_id) -> bool:
    """ثبت دعوت برای معرف و اعطای پاداش — با محافظت در برابر تکرار/خودمعرفی.
    معرف باید با شناسهٔ کاربر اصلی (canonical) داده شود."""
    if not referrer_id:
        return False
    try:
        referrer_id = int(referrer_id)
        new_user_id = int(new_user_id)
    except Exception:
        return False
    if referrer_id == new_user_id or referrer_id in ADMIN_IDS:
        return False
    ref = USERS.get(str(referrer_id))
    if not ref:
        return False
    _migrate_user(ref)
    refs_list = ref.setdefault("referrals", [])
    exists = any(
        (isinstance(r, dict) and r.get("id") == new_user_id) or
        (isinstance(r, int) and r == new_user_id)
        for r in refs_list
    )
    if exists:
        return False
    refs_list.append({"id": new_user_id, "time": int(time.time())})
    nu = USERS.get(str(new_user_id))
    if nu and not nu.get("referrer"):
        nu["referrer"] = referrer_id
    award_xp_and_credits(referrer_id, xp_amount=10, credits_amount=5)
    return True


def resolve_platform_identity_by_phone(platform: str, raw_user, norm_phone: str, referrer_id=None):
    """ادغام/ساختِ هویت بر اساس شمارهٔ تلفن برای پلتفرم ثانویه.
    شماره = ملاکِ نهاییِ هویت. خروجی: (canonical_uid, is_new_user, status)
      status: "merged"  → شماره متعلق به یک حساب موجود بود؛ همان حساب اصلی متصل شد.
              "created" → شماره جدید بود؛ کاربر اصلیِ جدید با شناسهٔ این پلتفرم ساخته شد.
    """
    raw_id = raw_user.id
    raw_key = f"{platform}:{raw_id}"
    now = int(time.time())
    owner = phone_owner(norm_phone)

    if owner is not None:
        canonical = int(owner)
        # حذف رکورد موقتِ بی‌شماره که ممکن است با شناسهٔ پلتفرم ساخته شده باشد
        stray = USERS.get(str(raw_id))
        if str(raw_id) != str(canonical) and stray is not None and not stray.get("phone"):
            USERS.pop(str(raw_id), None)
            # ابطال اثر انگشتِ کاربرِ حذف‌شده تا در ذخیره‌های بعدی باقی نماند
            _config.invalidate_user_cache(raw_id)
            save("users")
        if raw_key not in PLATFORM_LINKS:
            PLATFORM_LINKS[raw_key] = {
                "platform": platform, "platform_user_id": str(raw_id),
                "user_id": canonical, "connected_at": now, "via": "phone",
                "last_active": now, "interactions": 0,
            }
            save("platform_links")
        return canonical, False, "merged"

    # شمارهٔ جدید — کاربر اصلی = همان شناسهٔ پلتفرم
    canonical = int(raw_id)
    was_member = bool(USERS.get(str(raw_id), {}).get("phone"))
    register_user(raw_user)
    set_user_phone(raw_id, norm_phone)
    if raw_key not in PLATFORM_LINKS:
        PLATFORM_LINKS[raw_key] = {
            "platform": platform, "platform_user_id": str(raw_id),
            "user_id": canonical, "connected_at": now, "via": "phone",
            "last_active": now, "interactions": 0,
        }
        save("platform_links")
    is_new = not was_member
    if is_new and referrer_id:
        credit_referral(canonical, referrer_id)
    return canonical, is_new, "created"


# ========================= چندپلتفرمی — لینک ادمینی =========================

def create_admin_link_code(platform: str, created_by: int, ttl: int = ADMIN_LINK_TTL) -> str:
    code = _gen_code("a")
    now = int(time.time())
    ADMIN_LINK_CODES[code] = {
        "code": code, "platform": platform, "created_by": int(created_by),
        "created_at": now, "expires_at": now + ttl, "used": 0, "used_at": 0, "used_by": "",
    }
    save("admin_link_codes")
    return code


def validate_admin_link_code(code: str, platform: str = None):
    info = ADMIN_LINK_CODES.get(code)
    if not info:
        return None, "not_found"
    if info.get("used"):
        return None, "used"
    if info.get("expires_at", 0) and int(time.time()) > info["expires_at"]:
        return None, "expired"
    if platform and info.get("platform") != platform:
        return None, "wrong_platform"
    return info, "ok"


def register_platform_admin(platform: str, platform_user_id, code: str):
    """مصرف لینک ادمینی در پلتفرم مقصد و ثبت ادمین. خروجی: (ok, status)"""
    # idempotent — اگر از قبل ادمین این پلتفرم است، خطا نده
    if f"{platform}:{platform_user_id}" in PLATFORM_ADMINS:
        return True, "already"
    info, status = validate_admin_link_code(code, platform)
    if not info:
        return False, status
    PLATFORM_ADMINS[f"{platform}:{platform_user_id}"] = {
        "platform": platform, "platform_user_id": str(platform_user_id),
        "user_id": int(info.get("created_by", 0)), "added_at": int(time.time()),
    }
    save("platform_admins")
    info["used"] = 1
    info["used_at"] = int(time.time())
    info["used_by"] = str(platform_user_id)
    save("admin_link_codes")
    return True, "ok"


def get_platform_admins(platform: str) -> list:
    return [v for v in PLATFORM_ADMINS.values() if v.get("platform") == platform]


# ========================= چندپلتفرمی — بن سراسری =========================

def is_banned_globally(platform: str, platform_user_id) -> bool:
    """بن سراسری: اگر شناسه پلتفرم یا کاربر اصلیِ متصل بن باشد."""
    if is_user_banned(platform_user_id):
        return True
    cuid = canonical_user_id(platform, platform_user_id)
    if cuid is not None and int(cuid) != int(platform_user_id) and is_user_banned(cuid):
        return True
    return False


# ========================= چندپلتفرمی — گزارش =========================

ACTIVE_WINDOW = 7 * 24 * 3600  # بازهٔ «فعال اخیر» = ۷ روز


def _bale_active_recent(now: int) -> int:
    """کاربران اصلی (بله) که در ۷ روز اخیر فعال بوده‌اند (بدون ادمین)."""
    cnt = 0
    for u in USERS.values():
        if u.get("id") in ADMIN_IDS:
            continue
        if int(u.get("last_active", 0)) >= now - ACTIVE_WINDOW:
            cnt += 1
    return cnt


def platform_activity_stats() -> dict:
    """آمار فعالیت هر پلتفرم برای گزارش/تشخیص فعال‌ترین پلتفرم.
    خروجی: {platform: {"linked", "active", "interactions", "admins"}}"""
    now = int(time.time())
    stats = {}
    total_unique = members_count()
    stats["bale"] = {
        "linked": total_unique,
        "active": _bale_active_recent(now),
        "interactions": 0,
        "admins": len(ADMIN_IDS),
    }
    for p in SECONDARY_PLATFORMS:
        linked = active = inter = 0
        for v in PLATFORM_LINKS.values():
            if v.get("platform") != p:
                continue
            linked += 1
            inter += int(v.get("interactions", 0))
            if int(v.get("last_active", v.get("connected_at", 0))) >= now - ACTIVE_WINDOW:
                active += 1
        stats[p] = {
            "linked": linked, "active": active,
            "interactions": inter, "admins": len(get_platform_admins(p)),
        }
    return stats


def most_active_platform() -> str:
    """نامِ فعال‌ترین پلتفرم بر اساس تعداد فعالِ اخیر و سپس تعاملات."""
    stats = platform_activity_stats()
    best = max(stats.items(), key=lambda kv: (kv[1]["active"], kv[1]["interactions"], kv[1]["linked"]))
    return platform_name(best[0])


def platform_report() -> str:
    total_users = members_count()
    stats = platform_activity_stats()
    b = stats["bale"]
    lines = [
        "📊 گزارش پلتفرم‌ها",
        "━━━━━━━━━━━━━━━━",
        f"👥 کل اعضای یکتا (همه پلتفرم‌ها): {fa_num(total_users)} نفر",
        f"🔥 فعال‌ترین پلتفرم: {most_active_platform()}",
        f"🟢 مجموع فعال‌های اخیر (جمعِ همه پلتفرم‌ها): {fa_num(sum(s['active'] for s in stats.values()))} نفر",
        "",
        f"🟦 بله (پایه): فعال ✅\n"
        f"  👥 کاربران: {fa_num(b['linked'])} | 🟢 فعال اخیر: {fa_num(b['active'])} | 👤 ادمین: {fa_num(b['admins'])}",
        "",
    ]
    for p in SECONDARY_PLATFORMS:
        s = stats[p]
        st = "فعال ✅" if platform_enabled(p) else "غیرفعال ❌"
        cfg = "ثبت‌شده" if platform_configured(p) else "ثبت‌نشده"
        lines.append(
            f"{platform_name(p)}: {st} | اتصال: {cfg}\n"
            f"  🔗 متصل: {fa_num(s['linked'])} | 🟢 فعال اخیر: {fa_num(s['active'])}"
            f" | 💬 تعامل: {fa_num(s['interactions'])} | 👤 ادمین: {fa_num(s['admins'])}"
        )
        lines.append("")
    via_link = sum(1 for v in PLATFORM_LINKS.values() if v.get("via") == "link")
    via_phone = sum(1 for v in PLATFORM_LINKS.values() if v.get("via") == "phone")
    lines.append(f"🔗 اتصال با لینک: {fa_num(via_link)} | 📱 اتصال با شماره: {fa_num(via_phone)}")
    pl_missions = sum(1 for m in MISSIONS if m.get("type") == "platform_link")
    lines.append(f"🎯 ماموریت‌های اتصال پلتفرم: {fa_num(pl_missions)}")
    return "\n".join(lines)


# ========================= مرکز پیام‌رسانی =========================

def _secondary_origin_ids() -> set:
    """شناسه‌هایی که منشأشان یک پلتفرم ثانویه است (canonical == platform_user_id)
    و روی بله چتی ندارند — برای جلوگیری از ارسال اشتباه روی بله."""
    ids = set()
    for link in PLATFORM_LINKS.values():
        if link.get("platform") and link.get("platform") != "bale":
            if str(link.get("user_id")) == str(link.get("platform_user_id")):
                ids.add(str(link.get("platform_user_id")))
    return ids


def platform_recipients(platform: str) -> list:
    """لیست chat_idهای قابل‌ارسال روی یک پلتفرم (فقط اعضای دارای شماره، بدون ادمین‌ها).
    - بله: کلید رکورد کاربر = chat_id بله.
    - ثانویه: platform_user_id رکورد اتصال = chat_id همان پلتفرم."""
    out = []
    if platform == "bale":
        secondary_only = _secondary_origin_ids()
        for uid_str, u in USERS.items():
            if not u.get("phone"):
                continue
            if uid_str in secondary_only:
                continue
            try:
                cid = int(u.get("id", uid_str))
            except Exception:
                continue
            if cid in ADMIN_IDS:
                continue
            out.append(cid)
        return out
    for link in PLATFORM_LINKS.values():
        if link.get("platform") != platform:
            continue
        try:
            pid = int(link.get("platform_user_id"))
        except Exception:
            continue
        cuid = link.get("user_id")
        try:
            if cuid is not None and int(cuid) in ADMIN_IDS:
                continue
        except Exception:
            pass
        out.append(pid)
    return out


def platform_phone_count(platform: str) -> int:
    """تعداد اعضای دارای شمارهٔ تماس روی یک پلتفرم (بدون ادمین)."""
    if platform == "bale":
        return len(platform_recipients("bale"))
    cnt = 0
    for link in PLATFORM_LINKS.values():
        if link.get("platform") != platform:
            continue
        cuid = link.get("user_id")
        owner = USERS.get(str(cuid)) or USERS.get(str(link.get("platform_user_id")))
        if owner and owner.get("phone"):
            try:
                if int(owner.get("id", cuid)) in ADMIN_IDS:
                    continue
            except Exception:
                pass
            cnt += 1
    return cnt


def messaging_stats() -> dict:
    """آمار مرکز پیام‌رسانی: برای هر پلتفرمِ دارای bot فعال → اعضا/شماره/فعال اخیر."""
    bots = _config.active_platform_bots()
    act = platform_activity_stats()
    out = {}
    for p in (["bale"] + list(SECONDARY_PLATFORMS)):
        if p not in bots:
            continue
        out[p] = {
            "members": len(platform_recipients(p)),
            "phones": platform_phone_count(p),
            "active": act.get(p, {}).get("active", 0),
            "has_bot": True,
        }
    return out


def resolve_direct_target(query: str):
    """یافتن یک گیرندهٔ دایرکت بر اساس آیدی عددی یا یوزرنیم.
    خروجی: (platform, chat_id, display) یا None."""
    q = (query or "").strip().lstrip("@").lower()
    if not q:
        return None
    bots = _config.active_platform_bots()
    # آیدی عددی
    if q.isdigit():
        qid = int(q)
        if "bale" in bots and str(qid) in USERS and USERS[str(qid)].get("phone"):
            u = USERS[str(qid)]
            return ("bale", qid, u.get("first_name") or str(qid))
        for link in PLATFORM_LINKS.values():
            if str(link.get("platform_user_id")) == str(qid) and link.get("platform") in bots:
                return (link.get("platform"), qid, str(qid))
        # شاید آیدیِ کاربر اصلی باشد که روی بله چت دارد
        if "bale" in bots and str(qid) in USERS:
            return ("bale", qid, USERS[str(qid)].get("first_name") or str(qid))
        return None
    # یوزرنیم — در رکورد کاربران بله جست‌وجو می‌شود
    for uid_str, u in USERS.items():
        if (u.get("username") or "").lower() == q and u.get("phone"):
            cid = int(u.get("id", uid_str))
            # ترجیح پلتفرمی که چت دارد
            if "bale" in bots and str(cid) in USERS:
                return ("bale", cid, u.get("first_name") or q)
            for link in PLATFORM_LINKS.values():
                if str(link.get("user_id")) == str(cid) and link.get("platform") in bots:
                    return (link.get("platform"), int(link.get("platform_user_id")), u.get("first_name") or q)
    return None


def phone_list(platform: str = None, limit: int = 0) -> list:
    """لیست (نام، شماره، پلتفرم) برای نمایش به ادمین. بدون ادمین‌ها."""
    out = []
    seen = set()
    for uid_str, u in USERS.items():
        ph = u.get("phone")
        if not ph:
            continue
        try:
            if int(u.get("id", uid_str)) in ADMIN_IDS:
                continue
        except Exception:
            pass
        if ph in seen:
            continue
        seen.add(ph)
        out.append((u.get("first_name") or "—", ph))
    if limit and limit > 0:
        return out[:limit]
    return out


# ---- گروه‌ها/کانال‌هایی که ربات در آن‌ها حضور دارد ----

def record_bot_group(platform: str, chat_id, title: str = "", chat_type: str = "group") -> None:
    """ثبت/به‌روزرسانی گروه یا کانالی که ربات در آن حضور دارد (برای ارسال گروهی)."""
    if not platform or chat_id is None:
        return
    key = f"{platform}:{chat_id}"
    now = int(time.time())
    rec = BOT_GROUPS.get(key)
    if rec:
        if title:
            rec["title"] = title
        if chat_type:
            rec["chat_type"] = chat_type
        rec["last_seen"] = now
    else:
        BOT_GROUPS[key] = {
            "platform": platform, "chat_id": str(chat_id),
            "title": title or "", "chat_type": chat_type or "group",
            "added_at": now, "last_seen": now,
        }
    save("bot_groups")


def group_targets(platform: str = None) -> list:
    """لیست chat_idهای گروه/کانالِ ثبت‌شده برای ارسال گروهی.
    خروجی: لیست تاپل (platform, chat_id, title)."""
    out = []
    for g in BOT_GROUPS.values():
        if platform and platform != "all" and g.get("platform") != platform:
            continue
        out.append((g.get("platform"), g.get("chat_id"), g.get("title") or g.get("chat_id")))
    return out


def group_count(platform: str = None) -> int:
    """تعداد گروه/کانالِ ثبت‌شده روی یک پلتفرم (یا همه)."""
    return len(group_targets(platform))


# ========================= سیستم دسترسی بخش‌ها =========================

FEATURE_KEYS = [
    ("courses",       "📚 لیست دوره‌ها"),
    ("missions",      "🎯 ماموریت‌ها"),
    ("profile",       "🏆 پروفایل"),
    ("referral",      "👥 دعوت دوستان"),
    ("support",       "📞 پشتیبانی"),
    ("leaderboard",   "🏅 جدول رتبه"),
    ("career_path",   "🧠 مسیر شغلی"),
    ("latest_events", "📰 آخرین اتفاقات"),
    ("shop",          "💎 گنجینه"),
]

FEATURE_LABELS = {k: v for k, v in FEATURE_KEYS}


def get_feature_rule(feature_key: str) -> dict:
    """دریافت قانون دسترسی یک بخش. اگر تعریف نشده، همه مجاز هستند."""
    return FEATURE_ACCESS.get(feature_key, {
        "min_xp": 0, "min_credits": 0, "min_level": 0, "min_edu_rank": 0
    })


def set_feature_rule(feature_key: str, rules: dict):
    """تنظیم قانون دسترسی یک بخش"""
    FEATURE_ACCESS[feature_key] = {
        "min_xp":       max(0, int(rules.get("min_xp", 0))),
        "min_credits":  max(0, int(rules.get("min_credits", 0))),
        "min_level":    max(0, int(rules.get("min_level", 0))),
        "min_edu_rank": max(0, int(rules.get("min_edu_rank", 0))),
    }
    save("feature_access")


def check_feature_access(user_id: int, feature_key: str) -> tuple:
    """
    بررسی دسترسی کاربر به یک بخش.
    برگرداندن: (ok: bool, reason: str|None)
    """
    if user_id in ADMIN_IDS:
        return True, None
    rule = get_feature_rule(feature_key)
    if not any(rule.values()):
        return True, None
    u = USERS.get(str(user_id))
    if not u:
        return False, "کاربر ثبت نشده"
    _migrate_user(u)
    xp = u.get("xp", 0)
    credits_ = u.get("credits", 0)
    _, _, level_idx = get_level_info(xp)
    edu_rank = EDUCATIONAL_RANKS.index(get_educational_rank(xp))
    min_xp = rule.get("min_xp", 0)
    min_credits = rule.get("min_credits", 0)
    min_level = rule.get("min_level", 0)
    min_edu_rank = rule.get("min_edu_rank", 0)
    if min_xp > 0 and xp < min_xp:
        return False, f"حداقل {min_xp} XP نیاز است (شما: {xp} XP)"
    if min_credits > 0 and credits_ < min_credits:
        return False, f"حداقل {min_credits} اعتبار نیاز است (شما: {credits_})"
    if min_level > 0 and level_idx < min_level:
        lvl = USER_LEVELS[min_level] if min_level < len(USER_LEVELS) else USER_LEVELS[-1]
        return False, f"باید به سطح «{lvl['title']}» برسید"
    if min_edu_rank > 0 and edu_rank < min_edu_rank:
        rank = EDUCATIONAL_RANKS[min_edu_rank] if min_edu_rank < len(EDUCATIONAL_RANKS) else EDUCATIONAL_RANKS[-1]
        return False, f"باید به رتبه «{rank['title']}» برسید"
    return True, None


# ========================= [مشکل 3] محدودیت اختصاصی بخش‌ها برای کاربر =========================

def get_user_feature_restriction(user_id: int, feature_key: str) -> dict | None:
    """دریافت محدودیت اختصاصی یک کاربر برای یک بخش."""
    uid_str = str(user_id)
    restrictions = USER_FEATURE_RESTRICTIONS.get(uid_str, {})
    r = restrictions.get(feature_key)
    if r is None:
        return None
    # اگر محدودیت موقت منقضی شده، حذفش کن
    if r.get("until_ts", 0) > 0 and r["until_ts"] <= int(time.time()):
        restrictions.pop(feature_key, None)
        save("user_feature_restrictions")
        return None
    return r


def set_user_feature_restriction(user_id: int, feature_key: str, is_blocked: bool,
                                  until_ts: int = 0, note: str = "") -> bool:
    """تنظیم محدودیت اختصاصی یک بخش برای یک کاربر."""
    uid_str = str(user_id)
    if uid_str not in USERS:
        return False
    USER_FEATURE_RESTRICTIONS.setdefault(uid_str, {})[feature_key] = {
        "is_blocked": is_blocked,
        "until_ts": until_ts,
        "note": note,
    }
    save("user_feature_restrictions")
    return True


def remove_user_feature_restriction(user_id: int, feature_key: str) -> bool:
    """حذف محدودیت اختصاصی یک بخش برای یک کاربر."""
    uid_str = str(user_id)
    restrictions = USER_FEATURE_RESTRICTIONS.get(uid_str, {})
    if feature_key in restrictions:
        restrictions.pop(feature_key)
        if not restrictions:
            USER_FEATURE_RESTRICTIONS.pop(uid_str, None)
        save("user_feature_restrictions")
    return True


def check_user_specific_access(user_id: int, feature_key: str) -> tuple:
    """
    بررسی محدودیت اختصاصی کاربر برای یک بخش.
    برگرداندن: (ok: bool, reason: str|None)
    """
    if user_id in ADMIN_IDS:
        return True, None
    r = get_user_feature_restriction(user_id, feature_key)
    if r is None:
        return True, None
    if not r.get("is_blocked", False):
        return True, None
    until_ts = r.get("until_ts", 0)
    note = r.get("note", "")
    if until_ts > 0:
        remaining = until_ts - int(time.time())
        if remaining <= 0:
            remove_user_feature_restriction(user_id, feature_key)
            return True, None
        hrs = remaining // 3600
        mins = (remaining % 3600) // 60
        reason = f"دسترسی شما به این بخش تا {hrs} ساعت و {mins} دقیقه دیگر محدود است."
    else:
        reason = "دسترسی شما به این بخش توسط ادمین محدود شده است."
    if note:
        reason += f"\n📝 {note}"
    return False, reason


# ========================= [مشکل 5] تنظیمات فروش نقدی =========================

def get_cash_sale_setting(target_type: str, target_id: str) -> dict | None:
    """دریافت تنظیم فروش نقدی برای یک دوره یا سرفصل."""
    key = f"{target_type}|{target_id}"
    s = CASH_SALE_SETTINGS.get(key)
    if s and s.get("enabled"):
        return s
    return None


def set_cash_sale_setting(target_type: str, target_id: str, enabled: bool,
                           amount: int = 0, payment_method: str = "",
                           display_note: str = "",
                           display_place: str = "course",
                           xp_reward: int = 0,
                           credits_reward: int = 0,
                           card_number=None, card_holder=None, bank_name=None) -> None:
    """تنظیم فروش نقدی برای یک دوره یا سرفصل.
    فیلدهای کارت (card_number/card_holder/bank_name) اگر None باشند، مقدار قبلی حفظ می‌شود."""
    key = f"{target_type}|{target_id}"
    old = CASH_SALE_SETTINGS.get(key, {})
    CASH_SALE_SETTINGS[key] = {
        "enabled": enabled,
        "amount": max(0, int(amount)),
        "payment_method": payment_method,
        "display_note": display_note,
        "display_place": display_place if display_place in ("course", "shop") else old.get("display_place", "course"),
        "xp_reward": max(0, int(xp_reward)),
        "credits_reward": max(0, int(credits_reward)),
        "card_number": old.get("card_number", "") if card_number is None else card_number,
        "card_holder": old.get("card_holder", "") if card_holder is None else card_holder,
        "bank_name":   old.get("bank_name", "")   if bank_name   is None else bank_name,
    }
    save("cash_sale_settings")


def normal_users_sorted():
    users = []
    for u in USERS.values():
        if u["id"] not in ADMIN_IDS:
            _migrate_user(u)
            users.append(u)
    return sorted(users, key=lambda x: x.get("xp", x.get("points", 0)), reverse=True)


def user_rank(uid: int) -> int:
    """رتبه کاربر در جدول — از نتیجه‌ای که یکبار sort شده استفاده می‌کند"""
    sorted_users = normal_users_sorted()
    for index, u in enumerate(sorted_users, start=1):
        if u["id"] == uid:
            return index
    return len(sorted_users) + 1


def valid_refs(uid: int, since=None) -> int:
    u = USERS.get(str(uid))
    if not u:
        return 0
    unique = set()
    for r in u.get("referrals", []):
        if isinstance(r, dict):
            rid = r.get("id")
            tm = r.get("time")
            if rid is None:
                continue
            if since is not None and (tm is None or tm < since):
                continue
        else:
            rid = int(r)
            if since is not None:
                continue
        if rid == int(str(uid)) or rid in ADMIN_IDS:
            continue
        unique.add(rid)
    return len(unique)


# ========================= پیشرفت دوره =========================

def get_completed_lids(uid, cid: str) -> set:
    val = PROGRESS.get(str(uid), {}).get(cid, [])
    return set(val) if isinstance(val, list) else set()


def has_done_lesson(uid, cid: str, lid: str) -> bool:
    return lid in get_completed_lids(uid, cid)


def mark_lesson_done(uid, cid: str, lid: str):
    prog = PROGRESS.setdefault(str(uid), {})
    val = prog.get(cid, [])
    if isinstance(val, int):
        # مایگریشن inline: int → list (startup migration باید قبلاً انجام شده باشد)
        lessons = COURSES.get(cid, {}).get("lessons", [])
        val = [ls["lid"] for ls in lessons[:val] if ls.get("lid")]
    if lid not in val:
        val.append(lid)
    prog[cid] = val
    save("progress")


def get_prog(uid, cid: str) -> int:
    val = PROGRESS.get(str(uid), {}).get(cid, 0)
    if isinstance(val, list):
        lids_in_course = {
            ls.get("lid")
            for ls in COURSES.get(cid, {}).get("lessons", [])
            if ls.get("lid")
        }
        return sum(1 for lid in val if lid in lids_in_course)
    return val


def get_seq_prog(uid, cid: str) -> int:
    val = PROGRESS.get(str(uid), {}).get(cid, 0)
    if isinstance(val, int):
        return val
    done = set(val)
    count = 0
    for ls in COURSES.get(cid, {}).get("lessons", []):
        lid = ls.get("lid")
        if lid and lid in done:
            count += 1
        elif not lid:
            count += 1
        else:
            break
    return count


def completed_lessons(uid) -> int:
    total = 0
    for cid, val in PROGRESS.get(str(uid), {}).items():
        if isinstance(val, list):
            lids_in_course = {
                ls.get("lid")
                for ls in COURSES.get(cid, {}).get("lessons", [])
                if ls.get("lid")
            }
            total += sum(1 for lid in val if lid in lids_in_course)
        elif isinstance(val, int):
            total += val
    return total


def total_lessons() -> int:
    return sum(len(c.get("lessons", [])) for c in COURSES.values())


# ========================= بررسی دسترسی =========================

async def check_membership(bot, user_id: int, channels: list):
    if not channels:
        return True, []
    not_joined = []
    for ch in channels:
        ch = ch.strip()
        if not ch:
            continue
        # نرمال‌سازی: اگر عددی نیست و @ ندارد، @ اضافه کن
        ch_norm = ch
        if not ch_norm.startswith("@") and not ch_norm.lstrip("-").isdigit():
            ch_norm = f"@{ch_norm}"
        try:
            member = await bot.get_chat_member(chat_id=ch_norm, user_id=user_id)
            if getattr(member, "status", "left") in ["left", "kicked"]:
                not_joined.append(ch_norm)
        except Exception as e:
            ename = type(e).__name__.lower()
            emsg = str(e).lower()
            if "chatmemberrestricted" in ename or "can_edit_tag" in emsg:
                continue
            not_joined.append(ch_norm)
    return len(not_joined) == 0, not_joined


def _get_lesson_paid_key(course_id: str, lesson_idx: int) -> str:
    """
    ساخت کلید credits_paid برای یک سرفصل.
    از lid استفاده می‌کند (migration-safe). اگر lid وجود نداشت، از idx استفاده می‌کند.
    """
    lessons = COURSES.get(course_id, {}).get("lessons", [])
    if 0 <= lesson_idx < len(lessons):
        lid = lessons[lesson_idx].get("lid")
        if lid:
            return f"lesson_{course_id}_{lid}"
    return f"lesson_{course_id}_{lesson_idx}"


async def full_access_check(bot, user_id: int, course_id: str = None, lesson_idx: int = None):
    """
    بررسی کامل دسترسی کاربر.
    برگرداندن: (ok, problem_type, details_dict)
    """
    if user_id in ADMIN_IDS:
        return True, None, None

    u = USERS.get(str(user_id))
    if u:
        _migrate_user(u)

    # ===== بررسی عضویت‌ها =====
    gj = SETTINGS.get("global_required_joins", [])
    if gj:
        ok, nj = await check_membership(bot, user_id, gj)
        if not ok:
            return False, "join", {"channels": nj, "source": "global"}

    if course_id and course_id in COURSES:
        cj = COURSES[course_id].get("required_joins", [])
        if cj:
            ok, nj = await check_membership(bot, user_id, cj)
            if not ok:
                return False, "join", {"channels": nj, "source": "course"}

    if course_id and lesson_idx is not None and course_id in COURSES:
        lessons = COURSES[course_id].get("lessons", [])
        if 0 <= lesson_idx < len(lessons):
            lj = lessons[lesson_idx].get("required_joins", [])
            if lj:
                ok, nj = await check_membership(bot, user_id, lj)
                if not ok:
                    return False, "join", {"channels": nj, "source": "lesson"}

    # ===== بررسی دعوت‌ها =====
    gr = SETTINGS.get("global_required_referrals", 0)
    if gr > 0:
        cur = valid_refs(user_id)
        if cur < gr:
            return False, "referral", {"required": gr, "current": cur, "source": "global"}

    if course_id and course_id in COURSES:
        cr = COURSES[course_id].get("referral_required", 0)
        if cr > 0:
            since = COURSES[course_id].get("referral_required_set_at")
            if since is None:
                since = int(time.time())
                COURSES[course_id]["referral_required_set_at"] = since
                save("courses")
            cur = valid_refs(user_id, since=since)
            if cur < cr:
                return False, "referral", {"required": cr, "current": cur, "source": "course"}

    if course_id and lesson_idx is not None and course_id in COURSES:
        lessons = COURSES[course_id].get("lessons", [])
        if 0 <= lesson_idx < len(lessons):
            lr = lessons[lesson_idx].get("referral_required", 0)
            if lr > 0:
                since = lessons[lesson_idx].get("referral_required_set_at")
                if since is None:
                    since = int(time.time())
                    lessons[lesson_idx]["referral_required_set_at"] = since
                    save("courses")
                cur = valid_refs(user_id, since=since)
                if cur < lr:
                    return False, "referral", {"required": lr, "current": cur, "source": "lesson"}

    # ===== بررسی اعتبار اجباری =====
    credits_paid = u.get("credits_paid", {}) if u else {}
    user_changed = False  # برای batch save

    # اعتبار عمومی
    gc = SETTINGS.get("global_required_credits", 0)
    if gc > 0 and "global" not in credits_paid:
        cur_credits = u.get("credits", 0) if u else 0
        if cur_credits < gc:
            return False, "credits", {"required": gc, "current": cur_credits, "source": "global"}
        if u:
            u["credits"] = max(0, cur_credits - gc)
            u["credits_paid"]["global"] = True
            user_changed = True

    # اعتبار دوره
    if course_id and course_id in COURSES:
        cc = COURSES[course_id].get("required_credits", 0)
        paid_key = f"course_{course_id}"
        if cc > 0 and paid_key not in credits_paid:
            cur_credits = u.get("credits", 0) if u else 0
            if cur_credits < cc:
                if user_changed:
                    save("users")  # ذخیره تغییرات قبلی قبل از خروج
                return False, "credits", {
                    "required": cc, "current": cur_credits,
                    "source": "course", "course_title": COURSES[course_id].get("title", "")
                }
            if u:
                u["credits"] = max(0, cur_credits - cc)
                u["credits_paid"][paid_key] = True
                user_changed = True

    # اعتبار سرفصل
    if course_id and lesson_idx is not None and course_id in COURSES:
        lessons = COURSES[course_id].get("lessons", [])
        if 0 <= lesson_idx < len(lessons):
            lc = lessons[lesson_idx].get("required_credits", 0)
            paid_key = _get_lesson_paid_key(course_id, lesson_idx)
            if lc > 0 and paid_key not in credits_paid:
                cur_credits = u.get("credits", 0) if u else 0
                if cur_credits < lc:
                    if user_changed:
                        save("users")
                    return False, "credits", {
                        "required": lc, "current": cur_credits,
                        "source": "lesson"
                    }
                if u:
                    u["credits"] = max(0, cur_credits - lc)
                    u["credits_paid"][paid_key] = True
                    user_changed = True

    # یک save برای همه کسرهای اعتبار
    if user_changed:
        save("users")

    return True, None, None


# ========================= گنجینه امتیازی =========================

def get_active_shop_items() -> list:
    return [item for item in SHOP.values() if item.get("active", False)]


def can_purchase_item(uid, item: dict) -> bool:
    uid = int(uid)
    purchased = item.get("purchased_by", [])
    if uid in purchased and not item.get("repeatable", False):
        return False
    stock = item.get("stock")
    if stock is not None and stock <= 0:
        return False
    return True


def purchase_shop_item(uid, item: dict, chat_id=None) -> bool:
    if not can_purchase_item(uid, item):
        return False
    price = int(item.get("price", 0))
    u = USERS.get(str(uid))
    if not u:
        return False
    _migrate_user(u)
    if u.get("credits", 0) < price:
        return False
    change_credits(uid, -price)
    item.setdefault("purchased_by", []).append(int(uid))
    if item.get("stock") is not None:
        item["stock"] = max(0, int(item["stock"]) - 1)
    save("shop")
    return True


# ========================= سیستم ماموریت‌ها =========================

def get_active_missions() -> list:
    return [m for m in MISSIONS if m.get("active", True)]


def has_completed_mission(uid, mission_id: str) -> bool:
    u = USERS.get(str(uid))
    if not u:
        return False
    _migrate_user(u)
    return mission_id in u.get("completed_missions", [])


def complete_mission(uid, mission_id: str) -> tuple:
    """انجام ماموریت و اعطای پاداش — از double-complete محافظت می‌کند"""
    if has_completed_mission(uid, mission_id):
        return False, 0, 0
    mission = next((m for m in MISSIONS if m.get("id") == mission_id), None)
    if not mission or not mission.get("active", True):
        return False, 0, 0
    u = USERS.get(str(uid))
    if not u:
        return False, 0, 0
    _migrate_user(u)
    xp_reward = mission.get("xp_reward", 0)
    credits_reward = mission.get("credits_reward", 0)
    u["completed_missions"].append(mission_id)
    save("users")
    # award_xp_and_credits هم save می‌زند — جداسازی completed_missions از XP/credits
    # برای جلوگیری از race condition، اینجا جداگانه save کردیم
    award_xp_and_credits(uid, xp_amount=xp_reward, credits_amount=credits_reward)
    return True, xp_reward, credits_reward


def get_platform_link_mission(platform: str):
    """ماموریت فعالِ اتصال برای یک پلتفرم خاص (یا None)."""
    for m in MISSIONS:
        if (m.get("type") == "platform_link" and m.get("active", True)
                and m.get("target_platform") == platform):
            return m
    return None


def user_can_connect_platform(user_id, platform: str) -> bool:
    """دکمه اتصال فقط وقتی: پلتفرم فعال + اطلاعات ثبت‌شده + ماموریت اتصال فعال موجود."""
    return (platform_enabled(platform)
            and platform_configured(platform)
            and get_platform_link_mission(platform) is not None)


MISSION_XP_LIMITS = {
    "text":  (1, 20),
    "photo": (20, 50),
    "video": (50, 100),
}


# ========================= منبع سرفصل =========================

def set_src(ctx, mode: str, cid: str, title: str, idx=None):
    ctx.user_data["src"] = {"mode": mode, "cid": cid, "title": title, "idx": idx}


def get_src(ctx):
    return ctx.user_data.get("src")


def src_back(ctx) -> str:
    s = get_src(ctx)
    if not s:
        return "a_panel"
    return f"a_lmenu|{s['cid']}|{s['idx']}" if s["mode"] == "edit" else f"a_open|{s['cid']}"


def apply_lesson(ctx, data: dict):
    s = get_src(ctx)
    if not s:
        return False, None, None, "اطلاعات ذخیره نشده."
    cid, title, mode, idx = s["cid"], s["title"], s["mode"], s["idx"]
    if cid not in COURSES:
        return False, None, None, "دوره پیدا نشد."
    data["title"] = title
    lessons = COURSES[cid].setdefault("lessons", [])
    if mode == "add":
        data.setdefault("lid", next_lid())
        lessons.append(data)
        new_idx = len(lessons) - 1
    else:
        if idx is None or idx >= len(lessons):
            return False, None, None, "سرفصل پیدا نشد."
        lessons[idx] = data
        new_idx = idx
    save("courses")
    ctx.user_data.pop("src", None)
    ctx.user_data.pop("state", None)
    return True, cid, new_idx, "ok"


# ========================= تطبیق دستورات =========================

def match_cmd(cmd: dict, text: str) -> bool:
    t = cmd.get("trigger", "")
    mt = cmd.get("match_type", "exact")
    if mt == "exact":
        return text == t
    if mt == "startswith":
        return text.startswith(t)
    if mt == "contains":
        return t in text
    return False


# ========================= هوش مصنوعی (AI) =========================
# ⚠️ بازآرایی: منطق فراخوانی پروایدرها به ai_brain.py منتقل شد تا «مغز
# هوش مصنوعی» در یک فایل متمرکز باشد. نام‌ها عیناً از اینجا دوباره export
# می‌شوند، پس کدهای موجود مثل `from core import ask_ai, ask_ai_fast`
# (در ai_mentor و handlers_ai) بدون هیچ تغییری کار می‌کنند.
# قالب «X as X» شکل استاندارد اعلام re-export است.
from ai_brain import (           # noqa: E402
    _ai_check_cloudflare as _ai_check_cloudflare,
    _ai_check_openai as _ai_check_openai,
    _ai_err as _ai_err,
    _ai_jloads as _ai_jloads,
    _ai_text_cloudflare as _ai_text_cloudflare,
    _ai_text_openai as _ai_text_openai,
    ai_pick_preferred_model as ai_pick_preferred_model,
    ask_ai as ask_ai,
    ask_ai_fast as ask_ai_fast,
    check_ai_provider as check_ai_provider,
    check_all_ai_providers as check_all_ai_providers,
)

# فهرست re-exportهای AI — هم مستندسازی، هم اعلام «استفاده‌شده» به pyflakes.
__all_ai__ = (
    ask_ai, ask_ai_fast, check_ai_provider, check_all_ai_providers,
    ai_pick_preferred_model, _ai_jloads, _ai_text_openai,
    _ai_text_cloudflare, _ai_err, _ai_check_openai, _ai_check_cloudflare,
)
