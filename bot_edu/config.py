"""
config.py — تنظیمات، اتصال دیتابیس و ذخیره‌سازی SQLite
وابستگی: فقط db.py و stdlib

قاعده جدید:
  فایل .env در ریشهٔ پروژه تنها منبع env است. برای لود کردن آن از env_loader
  واقع در ریشهٔ پروژه استفاده می‌شود (هم bot_edu هم web هم giso هم main.py).
"""
import json
import os
import sys
import time
import logging
import threading
from pathlib import Path

# اطمینان از دسترسی به env_loader در ریشه پروژه
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))
try:
    from env_loader import load_project_env
    load_project_env()
except ImportError:
    # fallback در صورتی که env_loader در دسترس نباشد (سناریوهای قدیمی)
    try:
        from dotenv import load_dotenv
        load_dotenv(_PROJECT_ROOT / ".env")
        for sub in ("bot_edu", "web", "giso"):
            load_dotenv(_PROJECT_ROOT / sub / ".env", override=False)
    except ImportError:
        pass

from db import get_conn

logger = logging.getLogger(__name__)


def _env_int_list(name: str, default: str = "") -> list:
    """خواندن لیست آیدی عددی از متغیر محیطی (جداشده با کاما)."""
    raw = (os.getenv(name) or default).strip()
    out = []
    for part in raw.replace("،", ",").split(","):
        part = part.strip()
        if not part:
            continue
        try:
            out.append(int(part))
        except ValueError:
            logger.warning(f"{name}: مقدار نامعتبر نادیده گرفته شد → {part!r}")
    return out


def _env_str_list(name: str, default: str = "") -> list:
    """خواندن لیست رشته از متغیر محیطی (جداشده با کاما) — برای لیست پروکسی."""
    raw = (os.getenv(name) or default).strip()
    return [p.strip() for p in raw.replace("،", ",").split(",") if p.strip()]


def _env_str(name: str, default: str = "") -> str:
    return (os.getenv(name) or default).strip()


# ========================= تنظیمات =========================
from pathlib import Path
_BOT_EDU_DIR = Path(__file__).resolve().parent
_raw_db_path = _env_str("DB_PATH", "data/bot.db")
if not os.path.isabs(_raw_db_path):
    DB_PATH = str((_BOT_EDU_DIR / _raw_db_path).resolve())
else:
    DB_PATH = _raw_db_path

TOKEN         = _env_str("BOT_TOKEN")
ADMIN_IDS     = _env_int_list("ADMIN_IDS", "1191639507")
SUPPORT_GROUP = _env_str("SUPPORT_GROUP", "@edu_work")
BOT_USERNAME  = _env_str("BOT_USERNAME", "sadeghy_edubot")

# 🤖 کلید اصلی ماژول «یار هوشمند شغلی» (ai_mentor)
AI_MENTOR_ENABLED = _env_str("AI_MENTOR_ENABLED", "true").strip().lower() not in ("0", "false", "no", "off")

if not TOKEN:
    logger.error(
        "❌ توکن ربات تنظیم نشده است!\n"
        "   فایل .env را در ریشه پروژه بسازید و این خط را در آن بنویسید:\n"
        "   BOT_TOKEN=توکن_کامل_شما\n"
        "   (نمونه در .env.example ریشه موجود است)"
    )

# ========================= پروکسی تلگرام =========================
# در ایران api.telegram.org مسدود است. برای اتصال بدون VPN می‌توان از
# پروکسی HTTP/SOCKS5 استفاده کرد.
#
#   • TELEGRAM_PROXY      → یک پروکسی مشخص (اولویت اول)
#   • TELEGRAM_PROXY_LIST → چند پروکسی جداشده با کاما (به ترتیب امتحان می‌شوند)
#
# فرمت‌های مجاز:
#   http://host:port
#   http://user:pass@host:port
#   socks5://host:port          (نیازمند: pip install "httpx[socks]")
#
# اگر هیچ‌کدام تنظیم نشده باشند، اتصال مستقیم امتحان می‌شود (نیازمند VPN).
TELEGRAM_PROXY = (os.getenv("TELEGRAM_PROXY") or "").strip()

# لیست پروکسی‌های پشتیبان — اگر اولی جواب نداد، بعدی امتحان می‌شود.
TELEGRAM_PROXY_LIST = _env_str_list("TELEGRAM_PROXY_LIST")

# تعداد دفعات تلاش برای هر پروکسی (کار ۱ — مکانیزم retry)
TELEGRAM_CONNECT_RETRIES = 3

# ========================= هوش مصنوعی (AI Providers) =========================
# ⚠️ هیچ API Key ای داخل کد نوشته نمی‌شود — همه از .env خوانده می‌شوند.
# اگر کلیدی در .env نباشد، آن پروایدر با api_key خالی ساخته می‌شود و
# ادمین می‌تواند بعداً از پنل «🤖 مدیریت AI» آن را وارد کند.

# نام پروایدرهای ایرانی — در ask_ai_fast آخر امتحان می‌شوند
# (چون معمولاً کندتر/گران‌ترند ولی از داخل ایران در دسترس‌اند)
AI_IRANIAN_PROVIDERS = {"GapGPT", "AvalAI"}

# تعریف پروایدرهای پیش‌فرض — کلیدها از متغیرهای محیطی خوانده می‌شوند
AI_DEFAULT_PROVIDERS = [
    {
        "name": "Groq", "kind": "openai",
        "env_key": "AI_GROQ_API_KEY",
        "base_url": "https://api.groq.com/openai/v1",
        "api_root": "", "timeout": 18, "headers": {},
        "fallback": ["llama-3.1-8b-instant", "llama-3.3-70b-versatile", "mixtral-8x7b-32768"],
    },
    {
        "name": "OpenRouter", "kind": "openai",
        "env_key": "AI_OPENROUTER_API_KEY",
        "base_url": "https://openrouter.ai/api/v1",
        "api_root": "", "timeout": 22,
        "headers": {"HTTP-Referer": "https://ble.ir", "X-Title": "sadeghy-edubot"},
        "fallback": ["meta-llama/llama-3.1-8b-instruct", "anthropic/claude-3-haiku"],
    },
    {
        "name": "LLM7", "kind": "openai",
        "env_key": "AI_LLM7_API_KEY",
        "base_url": "https://api.llm7.io/v1",
        "api_root": "", "timeout": 25, "headers": {},
        "fallback": ["codestral-latest", "devstral-small-2:24b"],
    },
    {
        "name": "Cloudflare", "kind": "cloudflare",
        "env_key": "AI_CLOUDFLARE_API_KEY",
        "base_url": "",
        # آدرس کامل از .env خوانده می‌شود چون شامل ACCOUNT_ID است
        "api_root_env": "AI_CLOUDFLARE_API_ROOT",
        "api_root": "", "timeout": 20, "headers": {},
        "fallback": ["@cf/meta/llama-3.2-3b-instruct", "@cf/meta/llama-3.1-8b-instruct"],
    },
    {
        "name": "GapGPT", "kind": "openai",
        "env_key": "AI_GAPGPT_API_KEY",
        "base_url": "https://api.gapgpt.app/v1",
        "api_root": "", "timeout": 40, "headers": {},
        "fallback": ["gpt-4.1-mini", "gemini-2.0-flash", "gpt-4.1-nano"],
    },
    {
        "name": "AvalAI", "kind": "openai",
        "env_key": "AI_AVALAI_API_KEY",
        "base_url": "https://api.avalai.ir/v1",
        "api_root": "", "timeout": 30, "headers": {},
        "fallback": ["gemini-1.5-flash", "gpt-4o-mini", "claude-3-5-haiku-latest"],
    },
]


def seed_ai_providers() -> int:
    """
    ثبت پروایدرهای پیش‌فرض در دیتابیس (فقط اگر از قبل نباشند).
    API Keyها از .env خوانده می‌شوند؛ اگر نباشند مقدار خالی ذخیره می‌شود.
    خروجی: تعداد پروایدرهای تازه‌افزوده‌شده.
    """
    from db import add_ai_provider  # import محلی برای پرهیز از وابستگی چرخشی

    added = 0
    for p in AI_DEFAULT_PROVIDERS:
        api_key = (os.getenv(p.get("env_key", "")) or "").strip()
        api_root = p.get("api_root", "")
        if p.get("api_root_env"):
            api_root = (os.getenv(p["api_root_env"]) or "").strip() or api_root
        ok = add_ai_provider(
            name=p["name"],
            kind=p["kind"],
            api_key=api_key,
            base_url=p.get("base_url", ""),
            api_root=api_root,
            timeout=p.get("timeout", 20),
            headers_json=json.dumps(p.get("headers", {}), ensure_ascii=False),
            fallback_json=json.dumps(p.get("fallback", []), ensure_ascii=False),
            is_iranian=p["name"] in AI_IRANIAN_PROVIDERS,
            enabled=True,
        )
        if ok:
            added += 1
    if added:
        logger.info("🤖 %d پروایدر هوش مصنوعی پیش‌فرض ثبت شد.", added)
    return added


def sync_ai_keys_from_env() -> int:
    """
    اگر ادمین کلیدی را در .env اضافه/عوض کرد ولی رکورد از قبل با کلید خالی
    ساخته شده بود، کلید را به‌روز می‌کند. کلیدهایی که از پنل وارد شده‌اند
    بازنویسی نمی‌شوند (فقط رکوردهای با api_key خالی پر می‌شوند).
    """
    from db import get_ai_provider, update_ai_provider_field

    updated = 0
    for p in AI_DEFAULT_PROVIDERS:
        env_val = (os.getenv(p.get("env_key", "")) or "").strip()
        if not env_val:
            continue
        row = get_ai_provider(p["name"])
        if row is not None and not (row["api_key"] or "").strip():
            if update_ai_provider_field(p["name"], "api_key", env_val):
                updated += 1
    if updated:
        logger.info("🤖 %d کلید هوش مصنوعی از .env همگام شد.", updated)
    return updated


def telegram_proxy_candidates() -> list:
    """
    فهرست مرتب پروکسی‌هایی که باید امتحان شوند.
    ترتیب: TELEGRAM_PROXY → TELEGRAM_PROXY_LIST → اتصال مستقیم (None).
    مقدار None یعنی «بدون پروکسی» و همیشه به‌عنوان آخرین گزینه امتحان می‌شود.
    """
    out = []
    if TELEGRAM_PROXY:
        out.append(TELEGRAM_PROXY)
    for p in TELEGRAM_PROXY_LIST:
        if p not in out:
            out.append(p)
    out.append(None)  # آخرین تلاش: اتصال مستقیم (اگر VPN روشن باشد کار می‌کند)
    return out

# نمونه bot برای استفاده در notify_level_up بدون ctx
# توسط bot.py بعد از راه‌اندازی پر می‌شود
_app_bot = None

# قفل نوشتن برای thread safety
_lock = threading.Lock()


def set_app_bot(bot):
    """ذخیره نمونه bot برای استفاده خارج از handler‌ها (مثل notify_level_up)"""
    global _app_bot
    _app_bot = bot


# نمونهٔ bot هر پلتفرم — برای ارسال همگانی/دایرکت بین پلتفرم‌ها
# توسط bot.py بعد از ساخت هر Application پر می‌شود.
_PLATFORM_BOTS = {}


def register_platform_bot(platform, bot):
    """ثبت نمونهٔ bot یک پلتفرم برای ارسال پیام مرکز پیام‌رسانی."""
    if platform and bot is not None:
        _PLATFORM_BOTS[platform] = bot


def unregister_platform_bot(platform):
    """حذف نمونهٔ bot یک پلتفرم (وقتی آن پلتفرم غیرفعال می‌شود)."""
    _PLATFORM_BOTS.pop(platform, None)


def get_platform_bot(platform):
    """نمونهٔ bot یک پلتفرم (یا None اگر آن پلتفرم فعال/ثبت‌نشده باشد)."""
    return _PLATFORM_BOTS.get(platform)


def active_platform_bots():
    """دیکشنری {platform: bot} از پلتفرم‌هایی که bot فعال دارند."""
    return dict(_PLATFORM_BOTS)


# ========================= داده‌های جهانی (در حافظه) =========================
# این ساختارها توسط setup_data() از دیتابیس پر می‌شوند.
# handlers.py و ui.py و core.py بدون تغییر از همین نام‌ها استفاده می‌کنند.

COURSES        = {}
PROGRESS       = {}
USERS          = {}
TICKETS        = []
SETTINGS       = {}
SHOP           = {}
SURVEYS        = {}
BOT_COMMANDS   = []
MISSIONS       = []
FEATURE_ACCESS = {}   # {feature_key: {min_xp, min_credits, min_level, min_edu_rank}}
CASH_SALES     = []   # [{_db_id, user_id, user_name, username, course_id, course_title, ...}]
# [مشکل 3] محدودیت اختصاصی بخش‌ها برای هر کاربر
USER_FEATURE_RESTRICTIONS = {}  # {uid_str: {feature_key: {is_blocked, until_ts, note}}}
# [مشکل 5] تنظیمات فروش نقدی برای دوره/سرفصل
CASH_SALE_SETTINGS = {}  # {"course|c1": {enabled, amount, payment_method, display_note}}

# ========================= چندپلتفرمی (Final Stage) =========================
PLATFORM_LINKS   = {}  # {"telegram:123": {platform, platform_user_id, user_id, connected_at, via}}
LINK_CODES       = {}  # {code: {code, user_id, platform, mission_id, created_at, expires_at, used, used_at, used_by}}
ADMIN_LINK_CODES = {}  # {code: {code, platform, created_by, created_at, expires_at, used, used_at, used_by}}
PLATFORM_ADMINS  = {}  # {"telegram:123": {platform, platform_user_id, user_id, added_at}}
BOT_GROUPS       = {}  # {"bale:-100..": {platform, chat_id, title, chat_type, added_at, last_seen}}

# [افزوده] گزارش تحویل مرکز پیام‌رسانی — ماندگار در دیتابیس
DELIVERY_REPORTS      = []   # [{id, ts, route, sent, failed, total, ...}]
MAX_DELIVERY_REPORTS  = 20   # فقط N گزارش آخر نگه داشته می‌شود


# ========================= توابع بارگذاری =========================

def _load_courses() -> dict:
    conn = get_conn()
    result = {}
    for row in conn.execute("SELECT * FROM courses").fetchall():
        cid = row["course_id"]
        result[cid] = {
            "title":                   row["title"] or "",
            "description":             row["description"] or "",
            "required_joins":          json.loads(row["required_joins"] or "[]"),
            "referral_required":       row["referral_required"] or 0,
            "referral_required_set_at": row["referral_required_set_at"],
            "required_credits":        row["required_credits"] or 0,
            "survey_enabled":          bool(row["survey_enabled"]),
            "lessons":                 [],
        }
    for row in conn.execute(
        "SELECT * FROM lessons ORDER BY course_id, position"
    ).fetchall():
        cid = row["course_id"]
        if cid in result:
            result[cid]["lessons"].append({
                "lid":                    row["lid"],
                "title":                  row["title"] or "",
                "type":                   row["type"] or "",
                "content":               row["content"] or "",
                "file_id":               row["file_id"] or "",
                "caption":               row["caption"] or "",
                "source_chat_id":        row["source_chat_id"],
                "source_message_id":     row["source_message_id"],
                "required_joins":        json.loads(row["required_joins"] or "[]"),
                "referral_required":     row["referral_required"] or 0,
                "referral_required_set_at": row["referral_required_set_at"],
                "required_credits":      row["required_credits"] or 0,
            })
    return result


def _load_users() -> dict:
    conn = get_conn()
    result = {}

    for row in conn.execute("SELECT * FROM users").fetchall():
        uid = str(row["user_id"])
        result[uid] = {
            "id":             row["user_id"],
            "first_name":     row["first_name"] or "",
            "username":       row["username"] or "",
            "joined":         row["joined"] or 0,
            "last_active":    row["last_active"] or 0,
            "points":         row["points"] or 0,
            "xp":             row["xp"] or 0,
            "credits":        row["credits"] or 0,
            "referrer":       row["referrer"],
            "level_announced": row["level_announced"] or 0,
            "pending_level_up": row["pending_level_up"],
            "is_banned":      bool(row["is_banned"]) if "is_banned" in row.keys() else False,
            "is_muted":       bool(row["is_muted"]) if "is_muted" in row.keys() else False,
            "mute_until":     row["mute_until"] if "mute_until" in row.keys() else 0,
            "phone":          (row["phone"] if "phone" in row.keys() else "") or "",
            "referrals":          [],
            "completed_missions": [],
            "credits_paid":       {},
        }

    for row in conn.execute(
        "SELECT referrer_id, referred_id, time FROM referrals"
    ).fetchall():
        uid = str(row["referrer_id"])
        if uid in result:
            result[uid]["referrals"].append({"id": row["referred_id"], "time": row["time"] or 0})

    for row in conn.execute(
        "SELECT user_id, mission_id FROM completed_missions"
    ).fetchall():
        uid = str(row["user_id"])
        if uid in result:
            result[uid]["completed_missions"].append(row["mission_id"])

    for row in conn.execute(
        "SELECT user_id, scope_key FROM credits_paid"
    ).fetchall():
        uid = str(row["user_id"])
        if uid in result:
            result[uid]["credits_paid"][row["scope_key"]] = True

    return result


def _load_progress() -> dict:
    """
    PROGRESS = {uid_str: {cid: [lid1, lid2, ...]}}
    برای پیدا کردن cid هر lid، جدول lessons را join می‌کند.
    """
    conn = get_conn()
    result = {}
    for row in conn.execute("""
        SELECT p.user_id, l.course_id, p.lid
        FROM progress p
        LEFT JOIN lessons l ON p.lid = l.lid
        ORDER BY p.user_id, l.course_id, p.completed_at
    """).fetchall():
        cid = row["course_id"]
        if cid is None:
            continue  # سرفصل orphan — نادیده بگیر
        uid = str(row["user_id"])
        lid = row["lid"]
        result.setdefault(uid, {}).setdefault(cid, [])
        if lid not in result[uid][cid]:
            result[uid][cid].append(lid)
    return result


def _load_settings() -> dict:
    conn = get_conn()
    result = {}
    for row in conn.execute("SELECT key, value FROM settings").fetchall():
        key = row["key"]
        val = row["value"] or ""
        if key == "global_required_joins":
            result[key] = json.loads(val or "[]")
        else:
            try:
                result[key] = int(val)
            except (ValueError, TypeError):
                result[key] = val
    return result


def _load_shop() -> dict:
    conn = get_conn()
    result = {}
    for row in conn.execute("SELECT * FROM shop_items").fetchall():
        sid = row["item_id"]
        result[sid] = {
            "id":          sid,
            "title":       row["title"] or "",
            "description": row["description"] or "",
            "price":       row["price"] or 0,
            "kind":        row["kind"] or "",
            "content":     row["content"] or "",
            "active":      bool(row["active"]),
            "stock":       row["stock"],
            "repeatable":  bool(row["repeatable"]),
            "purchased_by": [],
        }
    for row in conn.execute("SELECT user_id, item_id FROM purchases").fetchall():
        sid = row["item_id"]
        if sid in result:
            result[sid]["purchased_by"].append(row["user_id"])
    return result


def _load_surveys() -> dict:
    """SURVEYS = {cid: {uid_str: {"vote": "...", "time": ...}}}"""
    conn = get_conn()
    result = {}
    for row in conn.execute("SELECT * FROM survey_votes").fetchall():
        cid = row["course_id"]
        uid = str(row["user_id"])
        result.setdefault(cid, {})[uid] = {
            "vote": row["vote"] or "",
            "time": row["time"] or 0,
        }
    return result


def _load_tickets() -> list:
    conn = get_conn()
    result = []
    for row in conn.execute("SELECT * FROM tickets ORDER BY id").fetchall():
        cols = row.keys()
        result.append({
            "_db_id":    row["id"],
            "user_id":   row["user_id"],
            "user_name": row["user_name"] or "",
            "username":  row["username"] or "",
            "text":      row["text"] or "",
            "time":      row["time"] or 0,
            "replied":   bool(row["replied"]),
            "reply_text": row["reply_text"] or "",
            "platform":  (row["platform"] if "platform" in cols else "bale") or "bale",
            "chat_id":   (row["chat_id"] if "chat_id" in cols else "") or "",
            "canonical_user_id": (row["canonical_user_id"] if "canonical_user_id" in cols else row["user_id"]) or row["user_id"],
        })
    return result


def _load_bot_commands() -> list:
    conn = get_conn()
    result = []
    for row in conn.execute("SELECT * FROM bot_commands ORDER BY id").fetchall():
        result.append({
            "_db_id":       row["id"],
            "trigger":      row["trigger"] or "",
            "active":       bool(row["active"]),
            "admin_only":   bool(row["admin_only"]),
            "scope":        row["scope"] or "both",
            "match_type":   row["match_type"] or "exact",
            "command_type": row["command_type"] or "text_reply",
            "response_text": row["response_text"] or "",
            "action_name":  row["action_name"] or "",
        })
    return result


def _load_missions() -> list:
    conn = get_conn()
    result = []
    for row in conn.execute("SELECT * FROM missions").fetchall():
        result.append({
            "id":             row["mission_id"],
            "title":          row["title"] or "",
            "description":    row["description"] or "",
            "type":           row["type"] or "",
            "content":        row["content"] or "",
            "file_id":        row["file_id"] or "",
            "caption":        row["caption"] or "",
            "xp_reward":      row["xp_reward"] or 0,
            "credits_reward": row["credits_reward"] or 0,
            "active":         bool(row["active"]),
        })
    return result


def _load_feature_access() -> dict:
    conn = get_conn()
    result = {}
    for row in conn.execute("SELECT * FROM feature_access").fetchall():
        result[row["feature_key"]] = {
            "min_xp":       row["min_xp"] or 0,
            "min_credits":  row["min_credits"] or 0,
            "min_level":    row["min_level"] or 0,
            "min_edu_rank": row["min_edu_rank"] or 0,
        }
    return result


def _load_cash_sales() -> list:
    conn = get_conn()
    result = []
    cols = None
    for row in conn.execute("SELECT * FROM cash_sale_requests ORDER BY id").fetchall():
        if cols is None:
            cols = row.keys()
        result.append({
            "_db_id":         row["id"],
            "user_id":        row["user_id"],
            "user_name":      row["user_name"] or "",
            "username":       row["username"] or "",
            "course_id":      row["course_id"] or "",
            "course_title":   row["course_title"] or "",
            "lesson_id":      row["lesson_id"] if "lesson_id" in cols else "",
            "lesson_title":   row["lesson_title"] if "lesson_title" in cols else "",
            "target_type":    row["target_type"] if "target_type" in cols else "course",
            "amount":         row["amount"] if "amount" in cols else 0,
            "payment_method": row["payment_method"] if "payment_method" in cols else "",
            "fiche_file_id":  row["fiche_file_id"] or "",
            "status":         row["status"] or "pending",
            "requested_at":   row["requested_at"] or 0,
            "reviewed_at":    row["reviewed_at"] or 0,
            "admin_note":     row["admin_note"] or "",
            "platform":       (row["platform"] if "platform" in cols else "bale") or "bale",
            "chat_id":        (row["chat_id"] if "chat_id" in cols else "") or "",
            "canonical_user_id": (row["canonical_user_id"] if "canonical_user_id" in cols else row["user_id"]) or row["user_id"],
        })
    return result


def _load_user_feature_restrictions() -> dict:
    """بارگذاری محدودیت‌های اختصاصی کاربران از دیتابیس"""
    conn = get_conn()
    result = {}
    try:
        for row in conn.execute("SELECT * FROM user_feature_restrictions").fetchall():
            uid = str(row["user_id"])
            fkey = row["feature_key"]
            result.setdefault(uid, {})[fkey] = {
                "is_blocked": bool(row["is_blocked"]),
                "until_ts":   row["until_ts"] or 0,
                "note":       row["note"] or "",
            }
    except Exception:
        pass
    return result


def _load_cash_sale_settings() -> dict:
    """بارگذاری تنظیمات فروش نقدی از دیتابیس"""
    conn = get_conn()
    result = {}
    try:
        for row in conn.execute("SELECT * FROM cash_sale_settings").fetchall():
            key = f"{row['target_type']}|{row['target_id']}"
            cols = row.keys()
            result[key] = {
                "enabled":        bool(row["enabled"]),
                "amount":         row["amount"] or 0,
                "payment_method": row["payment_method"] or "",
                "display_note":   row["display_note"] or "",
                "display_place":  row["display_place"] if "display_place" in cols else "course",
                "card_number":    (row["card_number"] or "") if "card_number" in cols else "",
                "card_holder":    (row["card_holder"] or "") if "card_holder" in cols else "",
                "bank_name":      (row["bank_name"] or "") if "bank_name" in cols else "",
            }
    except Exception:
        pass
    return result


def _load_platform_links() -> dict:
    conn = get_conn()
    result = {}
    try:
        for row in conn.execute("SELECT * FROM platform_links").fetchall():
            key = f"{row['platform']}:{row['platform_user_id']}"
            keys = row.keys()
            result[key] = {
                "platform":         row["platform"],
                "platform_user_id": str(row["platform_user_id"]),
                "user_id":          int(row["user_id"]),
                "connected_at":     row["connected_at"] or 0,
                "via":              row["via"] or "link",
                "last_active":      (row["last_active"] if "last_active" in keys else 0) or 0,
                "interactions":     (row["interactions"] if "interactions" in keys else 0) or 0,
            }
    except Exception:
        pass
    return result


def _load_link_codes() -> dict:
    conn = get_conn()
    result = {}
    try:
        for row in conn.execute("SELECT * FROM link_codes").fetchall():
            result[row["code"]] = {
                "code":       row["code"],
                "user_id":    int(row["user_id"]),
                "platform":   row["platform"],
                "mission_id": row["mission_id"] or "",
                "created_at": row["created_at"] or 0,
                "expires_at": row["expires_at"] or 0,
                "used":       int(row["used"] or 0),
                "used_at":    row["used_at"] or 0,
                "used_by":    row["used_by"] or "",
            }
    except Exception:
        pass
    return result


def _load_admin_link_codes() -> dict:
    conn = get_conn()
    result = {}
    try:
        for row in conn.execute("SELECT * FROM admin_link_codes").fetchall():
            result[row["code"]] = {
                "code":       row["code"],
                "platform":   row["platform"],
                "created_by": int(row["created_by"] or 0),
                "created_at": row["created_at"] or 0,
                "expires_at": row["expires_at"] or 0,
                "used":       int(row["used"] or 0),
                "used_at":    row["used_at"] or 0,
                "used_by":    row["used_by"] or "",
            }
    except Exception:
        pass
    return result


def _load_platform_admins() -> dict:
    conn = get_conn()
    result = {}
    try:
        for row in conn.execute("SELECT * FROM platform_admins").fetchall():
            key = f"{row['platform']}:{row['platform_user_id']}"
            result[key] = {
                "platform":         row["platform"],
                "platform_user_id": str(row["platform_user_id"]),
                "user_id":          int(row["user_id"] or 0),
                "added_at":         row["added_at"] or 0,
            }
    except Exception:
        pass
    return result


def _load_bot_groups() -> dict:
    conn = get_conn()
    result = {}
    try:
        for row in conn.execute("SELECT * FROM bot_groups").fetchall():
            key = f"{row['platform']}:{row['chat_id']}"
            result[key] = {
                "platform":  row["platform"],
                "chat_id":   str(row["chat_id"]),
                "title":     row["title"] or "",
                "chat_type": row["chat_type"] or "group",
                "added_at":  row["added_at"] or 0,
                "last_seen": row["last_seen"] or 0,
            }
    except Exception:
        pass
    return result


def _load_delivery_reports() -> list:
    """[افزوده] گزارش‌های تحویل مرکز پیام‌رسانی — جدیدترین آخر."""
    conn = get_conn()
    out = []
    try:
        rows = conn.execute(
            "SELECT * FROM delivery_reports ORDER BY id DESC LIMIT ?",
            (MAX_DELIVERY_REPORTS,),
        ).fetchall()
        for row in reversed(rows):   # قدیمی → جدید
            try:
                per = json.loads(row["per_platform"] or "{}")
            except Exception:
                per = {}
            try:
                errs = json.loads(row["errors"] or "[]")
            except Exception:
                errs = []
            out.append({
                "id":           row["id"],
                "ts":           row["ts"] or 0,
                "route":        row["route"] or "",
                "route_label":  row["route_label"] or "",
                "dest":         row["dest"] or "",
                "dest_label":   row["dest_label"] or "",
                "mtype":        row["mtype"] or "",
                "mtype_fa":     row["mtype_fa"] or "",
                "sent":         row["sent"] or 0,
                "failed":       row["failed"] or 0,
                "total":        row["total"] or 0,
                "per_platform": per,
                "errors":       errs,
            })
    except Exception as e:
        logger.warning(f"بارگذاری گزارش‌های تحویل ناموفق: {e}")
    return out


def add_delivery_report(rep: dict) -> int:
    """
    [افزوده] ذخیرهٔ یک گزارش تحویل در دیتابیس + هرس قدیمی‌ها.
    خروجی: id یکتای ردیف (برای استفاده به‌جای ایندکس لیست).
    """
    conn = get_conn()
    new_id = 0
    try:
        with _lock:
            with conn:
                cur = conn.execute(
                    """INSERT INTO delivery_reports
                       (ts, route, route_label, dest, dest_label, mtype, mtype_fa,
                        sent, failed, total, per_platform, errors)
                       VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (
                        int(rep.get("ts", 0)),
                        rep.get("route", ""), rep.get("route_label", ""),
                        rep.get("dest", ""), rep.get("dest_label", ""),
                        rep.get("mtype", ""), rep.get("mtype_fa", ""),
                        int(rep.get("sent", 0)), int(rep.get("failed", 0)),
                        int(rep.get("total", 0)),
                        json.dumps(rep.get("per_platform", {}), ensure_ascii=False),
                        json.dumps(rep.get("errors", []), ensure_ascii=False),
                    ),
                )
                new_id = cur.lastrowid
                # فقط N گزارش آخر نگه داشته می‌شود
                conn.execute(
                    """DELETE FROM delivery_reports WHERE id NOT IN
                       (SELECT id FROM delivery_reports ORDER BY id DESC LIMIT ?)""",
                    (MAX_DELIVERY_REPORTS,),
                )
    except Exception as e:
        logger.error(f"ذخیرهٔ گزارش تحویل ناموفق: {e}")
    return new_id


def clear_delivery_reports():
    """[افزوده] پاک کردن همهٔ گزارش‌های تحویل."""
    conn = get_conn()
    try:
        with _lock:
            with conn:
                conn.execute("DELETE FROM delivery_reports")
    except Exception as e:
        logger.error(f"پاک‌کردن گزارش‌های تحویل ناموفق: {e}")


# ========================= بهینه‌سازی: ذخیرهٔ هدفمند =========================
# مسئله: _save_users() قبلاً در هر فراخوانی همهٔ کاربران را بازنویسی می‌کرد
# (۴ دستور SQL × تعداد کل کاربران). با ۲۰۰۰ کاربر ≈ ۷۵۰ms و چون نوشتن‌ها
# همگام‌اند، کل event loop قفل می‌شد.
#
# راهکار: «اثر انگشت» هر کاربر پس از هر ذخیره نگه داشته می‌شود. در ذخیرهٔ بعدی
# فقط کاربرانی که واقعاً تغییر کرده‌اند در دیتابیس نوشته می‌شوند.
#
# چرا امن است:
#   • هیچ نقطهٔ فراخوانی تغییر نمی‌کند — save("users") دقیقاً مثل قبل کار می‌کند.
#   • اثر انگشت از همان فیلدهایی ساخته می‌شود که _save_users می‌نویسد؛
#     پس هر تغییر واقعی حتماً دیده می‌شود (کلید جدید = تغییر).
#   • اگر اثر انگشت موجود نباشد (اولین ذخیره پس از راه‌اندازی) همهٔ کاربران
#     نوشته می‌شوند — یعنی رفتار قبلی حفظ می‌شود.
#   • _save_users هرگز ردیفی را حذف نمی‌کرد؛ این رفتار عیناً حفظ شده است.

_USER_FP: dict = {}    # {uid_str: fingerprint} — آخرین وضعیت ذخیره‌شدهٔ هر کاربر
_PLINK_FP: dict = {}   # {(platform, platform_user_id): fingerprint} — اتصال‌های پلتفرم


def _user_fingerprint(u: dict) -> tuple:
    """اثر انگشت دقیقاً از فیلدهایی که _save_users در دیتابیس می‌نویسد.
    هر تغییر در این فیلدها ⇒ اثر انگشت متفاوت ⇒ کاربر دوباره نوشته می‌شود."""
    return (
        u.get("first_name", ""),
        u.get("username", ""),
        u.get("joined"),
        u.get("last_active"),
        u.get("points", 0),
        u.get("xp", 0),
        u.get("credits", 0),
        u.get("referrer"),
        u.get("level_announced", 0),
        u.get("pending_level_up"),
        bool(u.get("is_banned")),
        bool(u.get("is_muted")),
        u.get("mute_until", 0),
        u.get("phone", "") or "",
        tuple(
            (r.get("id"), r.get("time", 0)) if isinstance(r, dict) else (int(r), 0)
            for r in u.get("referrals", [])
        ),
        tuple(u.get("completed_missions", [])),
        tuple(sorted(k for k, v in u.get("credits_paid", {}).items() if v)),
    )


def invalidate_user_cache(uid=None):
    """ابطال اثر انگشت — کاربر در ذخیرهٔ بعدی حتماً بازنویسی می‌شود.
    uid=None یعنی ابطال کامل (همهٔ کاربران دوباره نوشته می‌شوند)."""
    if uid is None:
        _USER_FP.clear()
        _PLINK_FP.clear()
    else:
        _USER_FP.pop(str(uid), None)


def remove_user_from_memory(user_id) -> bool:
    """حذف زندهٔ ردپای کاربر از حافظهٔ ربات، بدون نیاز به restart."""
    try:
        uid = int(user_id or 0)
        uid_str = str(uid)
        with _lock:
            USERS.pop(uid_str, None)
            PROGRESS.pop(uid_str, None)
            USER_FEATURE_RESTRICTIONS.pop(uid_str, None)
            _USER_FP.pop(uid_str, None)

            # روابط داخل userهای باقی‌مانده
            for u in list(USERS.values()):
                if isinstance(u, dict):
                    if int(u.get("referrer") or 0) == uid:
                        u["referrer"] = None
                    refs = []
                    for r in u.get("referrals", []) or []:
                        try:
                            rid = int(r.get("id") if isinstance(r, dict) else r)
                        except Exception:
                            rid = 0
                        if rid != uid:
                            refs.append(r)
                    u["referrals"] = refs

            # لیست‌ها/دیکشنری‌های user-scoped
            TICKETS[:] = [t for t in TICKETS if int((t or {}).get("user_id") or 0) != uid and int((t or {}).get("canonical_user_id") or 0) != uid]
            CASH_SALES[:] = [r for r in CASH_SALES if int((r or {}).get("user_id") or 0) != uid and int((r or {}).get("canonical_user_id") or 0) != uid]
            for votes in SURVEYS.values():
                if isinstance(votes, dict):
                    votes.pop(uid_str, None)

            for key, v in list(PLATFORM_LINKS.items()):
                if int((v or {}).get("user_id") or 0) == uid or str((v or {}).get("platform_user_id") or "") == uid_str:
                    PLATFORM_LINKS.pop(key, None)
                    try:
                        _PLINK_FP.pop(((v or {}).get("platform"), str((v or {}).get("platform_user_id") or "")), None)
                    except Exception:
                        pass
            for code, v in list(LINK_CODES.items()):
                if int((v or {}).get("user_id") or 0) == uid or str((v or {}).get("used_by") or "") == uid_str:
                    LINK_CODES.pop(code, None)
            for code, v in list(ADMIN_LINK_CODES.items()):
                if int((v or {}).get("created_by") or 0) == uid:
                    v["created_by"] = 0
                if str((v or {}).get("used_by") or "") == uid_str:
                    v["used_by"] = "0"
            for key, v in list(PLATFORM_ADMINS.items()):
                if int((v or {}).get("user_id") or 0) == uid or str((v or {}).get("platform_user_id") or "") == uid_str:
                    PLATFORM_ADMINS.pop(key, None)
        return True
    except Exception as e:
        logger.warning(f"remove_user_from_memory failed: {e}")
        return False


def remove_all_users_from_memory() -> bool:
    """پاک‌سازی زندهٔ همه داده‌های user-scoped از حافظهٔ ربات."""
    try:
        with _lock:
            USERS.clear()
            PROGRESS.clear()
            TICKETS.clear()
            SURVEYS.clear()
            CASH_SALES.clear()
            USER_FEATURE_RESTRICTIONS.clear()
            PLATFORM_LINKS.clear()
            LINK_CODES.clear()
            PLATFORM_ADMINS.clear()
            _USER_FP.clear()
            _PLINK_FP.clear()
            for v in ADMIN_LINK_CODES.values():
                if isinstance(v, dict):
                    v["created_by"] = 0
                    v["used_by"] = "0"
        return True
    except Exception as e:
        logger.warning(f"remove_all_users_from_memory failed: {e}")
        return False


def reload_all_from_db() -> bool:
    """
    بازخوانی کامل همه دیتابیس‌ها به حافظه بعد از restore.
    چون setup_data() از update/extend استفاده می‌کند (ادغام)، ابتدا حافظه را پاک
    می‌کنیم تا هیچ داده کهنه‌ای از قبل نماند، سپس دوباره بارگذاری کامل انجام می‌شود.
    """
    try:
        remove_all_users_from_memory()
        # reset سایر cache های سراسری
        try:
            COURSES.clear()
            SHOP.clear()
            SETTINGS.clear()
            BOT_COMMANDS[:] = []
            MISSIONS[:] = []
            FEATURE_ACCESS.clear()
            CASH_SALE_SETTINGS.clear()
            BOT_GROUPS.clear()
            DELIVERY_REPORTS[:] = []
        except Exception:
            pass
        setup_data()
        logger.info(f"✅ حافظه از DB reload شد — {len(USERS)} کاربر")
        return True
    except Exception as e:
        logger.warning(f"reload_all_from_db failed: {e}")
        return False


def sync_deleted_users_from_db() -> bool:
    """Best-effort hook: اگر وب کاربری را از DB حذف کرده باشد، حافظهٔ ربات هم سبک sync شود."""
    try:
        conn = get_conn()
        existing = {str(row["user_id"]) for row in conn.execute("SELECT user_id FROM users").fetchall()}
        for uid_str in list(USERS.keys()):
            if uid_str not in existing:
                remove_user_from_memory(uid_str)
        return True
    except Exception as e:
        logger.debug(f"sync_deleted_users_from_db failed: {e}")
        return False


# ========================= توابع ذخیره‌سازی =========================

def _save_courses():
    conn = get_conn()
    with _lock:
        with conn:
            existing = {row[0] for row in conn.execute("SELECT course_id FROM courses")}
            new_keys = set(COURSES.keys())

            for cid in existing - new_keys:
                conn.execute("DELETE FROM lessons WHERE course_id = ?", (cid,))
                conn.execute("DELETE FROM courses WHERE course_id = ?", (cid,))

            for cid, c in COURSES.items():
                conn.execute("""
                    INSERT INTO courses
                    (course_id, title, description, required_joins, referral_required,
                     referral_required_set_at, required_credits, survey_enabled)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(course_id) DO UPDATE SET
                        title=excluded.title, description=excluded.description,
                        required_joins=excluded.required_joins, referral_required=excluded.referral_required,
                        referral_required_set_at=excluded.referral_required_set_at,
                        required_credits=excluded.required_credits, survey_enabled=excluded.survey_enabled
                """, (
                    cid,
                    c.get("title", ""),
                    c.get("description", ""),
                    json.dumps(c.get("required_joins", []), ensure_ascii=False),
                    c.get("referral_required", 0),
                    c.get("referral_required_set_at"),
                    c.get("required_credits", 0),
                    int(c.get("survey_enabled", True)),
                ))

                conn.execute("DELETE FROM lessons WHERE course_id = ?", (cid,))
                for idx, ls in enumerate(c.get("lessons", [])):
                    conn.execute("""
                        INSERT INTO lessons
                        (lid, course_id, position, title, type, content, file_id, caption,
                         source_chat_id, source_message_id, required_joins, referral_required,
                         referral_required_set_at, required_credits)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        ls.get("lid"),
                        cid,
                        idx,
                        ls.get("title", ""),
                        ls.get("type", ""),
                        ls.get("content", ""),
                        ls.get("file_id", ""),
                        ls.get("caption", ""),
                        ls.get("source_chat_id"),
                        ls.get("source_message_id"),
                        json.dumps(ls.get("required_joins", []), ensure_ascii=False),
                        ls.get("referral_required", 0),
                        ls.get("referral_required_set_at"),
                        ls.get("required_credits", 0),
                    ))


def _save_users():
    """ذخیرهٔ کاربران — فقط کاربرانی که واقعاً تغییر کرده‌اند نوشته می‌شوند.
    خروجی در دیتابیس با نسخهٔ قبلی (بازنویسی کامل) یکسان است."""
    conn = get_conn()
    now = int(time.time())
    written = {}   # اثر انگشت‌های این دور — فقط پس از commit موفق اعمال می‌شوند
    with _lock:
        with conn:
            for uid_str, u in USERS.items():
                # اگر این کاربر از آخرین ذخیره تغییری نکرده، از آن عبور کن
                fp = _user_fingerprint(u)
                if _USER_FP.get(uid_str) == fp:
                    continue

                uid = int(uid_str)
                conn.execute("""
                    INSERT INTO users
                    (user_id, first_name, username, joined, last_active, points, xp,
                     credits, referrer, level_announced, pending_level_up,
                     is_banned, is_muted, mute_until, phone)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(user_id) DO UPDATE SET
                        first_name=excluded.first_name, username=excluded.username,
                        joined=excluded.joined, last_active=excluded.last_active,
                        points=excluded.points, xp=excluded.xp, credits=excluded.credits,
                        referrer=excluded.referrer, level_announced=excluded.level_announced,
                        pending_level_up=excluded.pending_level_up, is_banned=excluded.is_banned,
                        is_muted=excluded.is_muted, mute_until=excluded.mute_until,
                        phone=excluded.phone
                """, (
                    uid,
                    u.get("first_name", ""),
                    u.get("username", ""),
                    u.get("joined", now),
                    u.get("last_active", now),
                    u.get("points", 0),
                    u.get("xp", 0),
                    u.get("credits", 0),
                    u.get("referrer"),
                    u.get("level_announced", 0),
                    u.get("pending_level_up"),
                    1 if u.get("is_banned") else 0,
                    1 if u.get("is_muted") else 0,
                    u.get("mute_until", 0),
                    u.get("phone", "") or "",
                ))

                conn.execute("DELETE FROM referrals WHERE referrer_id = ?", (uid,))
                for r in u.get("referrals", []):
                    if isinstance(r, dict):
                        conn.execute(
                            "INSERT INTO referrals (referrer_id, referred_id, time) VALUES (?, ?, ?)",
                            (uid, r.get("id"), r.get("time", 0)),
                        )
                    else:
                        conn.execute(
                            "INSERT INTO referrals (referrer_id, referred_id, time) VALUES (?, ?, ?)",
                            (uid, int(r), 0),
                        )

                conn.execute("DELETE FROM completed_missions WHERE user_id = ?", (uid,))
                for mid in u.get("completed_missions", []):
                    conn.execute(
                        "INSERT INTO completed_missions (user_id, mission_id) VALUES (?, ?)",
                        (uid, mid),
                    )

                conn.execute("DELETE FROM credits_paid WHERE user_id = ?", (uid,))
                for scope_key, val in u.get("credits_paid", {}).items():
                    if val:
                        conn.execute(
                            "INSERT INTO credits_paid (user_id, scope_key) VALUES (?, ?)",
                            (uid, scope_key),
                        )

                written[uid_str] = fp

    # فقط اگر تراکنش با موفقیت commit شد اثر انگشت‌ها به‌روز می‌شوند.
    # اگر خطایی رخ دهد، with conn تراکنش را rollback می‌کند و این خط اجرا
    # نمی‌شود — پس کاربران در ذخیرهٔ بعدی دوباره نوشته خواهند شد.
    _USER_FP.update(written)


def _save_progress():
    conn = get_conn()
    now = int(time.time())
    with _lock:
        with conn:
            existing = {
                (row[0], row[1])
                for row in conn.execute("SELECT user_id, lid FROM progress")
            }
            new_pairs = set()
            for uid_str, user_prog in PROGRESS.items():
                uid = int(uid_str)
                for cid, lids in user_prog.items():
                    if isinstance(lids, list):
                        for lid in lids:
                            new_pairs.add((uid, lid))

            for uid, lid in new_pairs - existing:
                conn.execute(
                    "INSERT INTO progress (user_id, lid, completed_at) VALUES (?, ?, ?) ON CONFLICT DO NOTHING",
                    (uid, lid, now),
                )
            for uid, lid in existing - new_pairs:
                conn.execute(
                    "DELETE FROM progress WHERE user_id = ? AND lid = ?",
                    (uid, lid),
                )


def _save_settings():
    conn = get_conn()
    with _lock:
        with conn:
            for key, val in SETTINGS.items():
                if isinstance(val, (list, dict)):
                    v = json.dumps(val, ensure_ascii=False)
                else:
                    v = str(val)
                conn.execute(
                    "INSERT INTO settings (key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                    (key, v),
                )


def _save_shop():
    conn = get_conn()
    now = int(time.time())
    with _lock:
        with conn:
            existing = {row[0] for row in conn.execute("SELECT item_id FROM shop_items")}
            new_keys = set(SHOP.keys())

            for sid in existing - new_keys:
                conn.execute("DELETE FROM shop_items WHERE item_id = ?", (sid,))
                conn.execute("DELETE FROM purchases WHERE item_id = ?", (sid,))

            for sid, item in SHOP.items():
                conn.execute("""
                    INSERT INTO shop_items
                    (item_id, title, description, price, kind, content, active, stock, repeatable)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(item_id) DO UPDATE SET
                        title=excluded.title, description=excluded.description,
                        price=excluded.price, kind=excluded.kind, content=excluded.content,
                        active=excluded.active, stock=excluded.stock, repeatable=excluded.repeatable
                """, (
                    sid,
                    item.get("title", ""),
                    item.get("description", ""),
                    item.get("price", 0),
                    item.get("kind", ""),
                    item.get("content", ""),
                    int(item.get("active", True)),
                    item.get("stock"),
                    int(item.get("repeatable", False)),
                ))

                existing_buyers = {
                    row[0]
                    for row in conn.execute(
                        "SELECT user_id FROM purchases WHERE item_id = ?", (sid,)
                    )
                }
                for uid in item.get("purchased_by", []):
                    if uid not in existing_buyers:
                        conn.execute(
                            "INSERT INTO purchases (user_id, item_id, purchased_at) VALUES (?, ?, ?)",
                            (uid, sid, now),
                        )


def _save_surveys():
    conn = get_conn()
    with _lock:
        with conn:
            conn.execute("DELETE FROM survey_votes")
            for cid, votes in SURVEYS.items():
                for uid_str, vote_data in votes.items():
                    if isinstance(vote_data, dict):
                        conn.execute(
                            "INSERT INTO survey_votes (user_id, course_id, vote, time) VALUES (?, ?, ?, ?)",
                            (int(uid_str), cid, vote_data.get("vote", ""), vote_data.get("time", 0)),
                        )


def _save_tickets():
    conn = get_conn()
    now = int(time.time())
    with _lock:
        with conn:
            for t in TICKETS:
                if "_db_id" in t:
                    conn.execute(
                        "UPDATE tickets SET replied=?, reply_text=?, platform=?, chat_id=?, canonical_user_id=? WHERE id=?",
                        (
                            int(t.get("replied", False)),
                            t.get("reply_text", ""),
                            t.get("platform", "bale"),
                            str(t.get("chat_id", "") or ""),
                            int(t.get("canonical_user_id") or t.get("user_id") or 0),
                            t["_db_id"],
                        ),
                    )
                else:
                    cursor = conn.execute("""
                        INSERT INTO tickets
                        (user_id, user_name, username, text, time, replied, reply_text, platform, chat_id, canonical_user_id)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        t.get("user_id"),
                        t.get("user_name", ""),
                        t.get("username", ""),
                        t.get("text", ""),
                        t.get("time", now),
                        int(t.get("replied", False)),
                        t.get("reply_text", ""),
                        t.get("platform", "bale"),
                        str(t.get("chat_id", "") or ""),
                        int(t.get("canonical_user_id") or t.get("user_id") or 0),
                    ))
                    t["_db_id"] = cursor.lastrowid


def _save_bot_commands():
    conn = get_conn()
    with _lock:
        with conn:
            existing_ids = {row[0] for row in conn.execute("SELECT id FROM bot_commands")}
            current_ids = {c.get("_db_id") for c in BOT_COMMANDS if c.get("_db_id")}

            for did in existing_ids - current_ids:
                conn.execute("DELETE FROM bot_commands WHERE id = ?", (did,))

            for cmd in BOT_COMMANDS:
                if "_db_id" in cmd and cmd["_db_id"] in existing_ids:
                    conn.execute("""
                        UPDATE bot_commands
                        SET trigger=?, active=?, admin_only=?, scope=?,
                            match_type=?, command_type=?, response_text=?, action_name=?
                        WHERE id=?
                    """, (
                        cmd.get("trigger", ""),
                        int(cmd.get("active", True)),
                        int(cmd.get("admin_only", False)),
                        cmd.get("scope", "both"),
                        cmd.get("match_type", "exact"),
                        cmd.get("command_type", "text_reply"),
                        cmd.get("response_text", ""),
                        cmd.get("action_name", ""),
                        cmd["_db_id"],
                    ))
                else:
                    cursor = conn.execute("""
                        INSERT INTO bot_commands
                        (trigger, active, admin_only, scope, match_type, command_type, response_text, action_name)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        cmd.get("trigger", ""),
                        int(cmd.get("active", True)),
                        int(cmd.get("admin_only", False)),
                        cmd.get("scope", "both"),
                        cmd.get("match_type", "exact"),
                        cmd.get("command_type", "text_reply"),
                        cmd.get("response_text", ""),
                        cmd.get("action_name", ""),
                    ))
                    cmd["_db_id"] = cursor.lastrowid


def _save_missions():
    conn = get_conn()
    with _lock:
        with conn:
            existing = {row[0] for row in conn.execute("SELECT mission_id FROM missions")}
            new_ids = {m.get("id") for m in MISSIONS if m.get("id")}

            for mid in existing - new_ids:
                conn.execute("DELETE FROM missions WHERE mission_id = ?", (mid,))

            for m in MISSIONS:
                mid = m.get("id")
                if not mid:
                    continue
                conn.execute("""
                    INSERT INTO missions
                    (mission_id, title, description, type, content, file_id, caption,
                     xp_reward, credits_reward, active)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(mission_id) DO UPDATE SET
                        title=excluded.title, description=excluded.description,
                        type=excluded.type, content=excluded.content, file_id=excluded.file_id,
                        caption=excluded.caption, xp_reward=excluded.xp_reward,
                        credits_reward=excluded.credits_reward, active=excluded.active
                """, (
                    mid,
                    m.get("title", ""),
                    m.get("description", ""),
                    m.get("type", ""),
                    m.get("content", ""),
                    m.get("file_id", ""),
                    m.get("caption", ""),
                    m.get("xp_reward", 0),
                    m.get("credits_reward", 0),
                    int(m.get("active", True)),
                ))


def _save_feature_access():
    conn = get_conn()
    with _lock:
        with conn:
            conn.execute("DELETE FROM feature_access")
            for fkey, rule in FEATURE_ACCESS.items():
                conn.execute("""
                    INSERT INTO feature_access (feature_key, min_xp, min_credits, min_level, min_edu_rank)
                    VALUES (?, ?, ?, ?, ?)
                """, (
                    fkey,
                    rule.get("min_xp", 0),
                    rule.get("min_credits", 0),
                    rule.get("min_level", 0),
                    rule.get("min_edu_rank", 0),
                ))


def _save_cash_sales():
    conn = get_conn()
    now = int(time.time())
    with _lock:
        with conn:
            for req in CASH_SALES:
                if "_db_id" in req:
                    conn.execute(
                        """
                        UPDATE cash_sale_requests
                        SET status=?, reviewed_at=?, admin_note=?, platform=?, chat_id=?, canonical_user_id=?
                        WHERE id=?
                        """,
                        (
                            req.get("status", "pending"),
                            req.get("reviewed_at", 0),
                            req.get("admin_note", ""),
                            req.get("platform", "bale"),
                            str(req.get("chat_id", "") or ""),
                            int(req.get("canonical_user_id") or req.get("user_id") or 0),
                            req["_db_id"],
                        ),
                    )
                else:
                    cursor = conn.execute("""
                        INSERT INTO cash_sale_requests
                        (user_id, user_name, username, course_id, course_title,
                         lesson_id, lesson_title, target_type, amount, payment_method,
                         fiche_file_id, status, requested_at, reviewed_at, admin_note,
                         platform, chat_id, canonical_user_id)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        req.get("user_id"),
                        req.get("user_name", ""),
                        req.get("username", ""),
                        req.get("course_id", ""),
                        req.get("course_title", ""),
                        req.get("lesson_id", ""),
                        req.get("lesson_title", ""),
                        req.get("target_type", "course"),
                        req.get("amount", 0),
                        req.get("payment_method", ""),
                        req.get("fiche_file_id", ""),
                        req.get("status", "pending"),
                        req.get("requested_at", now),
                        req.get("reviewed_at", 0),
                        req.get("admin_note", ""),
                        req.get("platform", "bale"),
                        str(req.get("chat_id", "") or ""),
                        int(req.get("canonical_user_id") or req.get("user_id") or 0),
                    ))
                    req["_db_id"] = cursor.lastrowid


def _save_user_feature_restrictions():
    conn = get_conn()
    with _lock:
        with conn:
            try:
                conn.execute("DELETE FROM user_feature_restrictions")
                for uid_str, restrictions in USER_FEATURE_RESTRICTIONS.items():
                    uid = int(uid_str)
                    for fkey, r in restrictions.items():
                        conn.execute("""
                            INSERT INTO user_feature_restrictions
                            (user_id, feature_key, is_blocked, until_ts, note)
                            VALUES (?, ?, ?, ?, ?)
                        """, (uid, fkey, 1 if r.get("is_blocked") else 0,
                              r.get("until_ts", 0), r.get("note", "")))
            except Exception as e:
                logger.error(f"_save_user_feature_restrictions error: {e}")


def _save_cash_sale_settings():
    conn = get_conn()
    with _lock:
        with conn:
            try:
                conn.execute("DELETE FROM cash_sale_settings")
                for key, s in CASH_SALE_SETTINGS.items():
                    parts = key.split("|", 1)
                    if len(parts) != 2:
                        continue
                    ttype, tid = parts
                    conn.execute("""
                        INSERT INTO cash_sale_settings
                        (target_type, target_id, enabled, amount, payment_method, display_note, display_place,
                         card_number, card_holder, bank_name)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (ttype, tid, 1 if s.get("enabled") else 0,
                          s.get("amount", 0), s.get("payment_method", ""),
                          s.get("display_note", ""), s.get("display_place", "course"),
                          s.get("card_number", ""), s.get("card_holder", ""),
                          s.get("bank_name", "")))
            except Exception as e:
                logger.error(f"_save_cash_sale_settings error: {e}")


def _save_platform_links():
    """ذخیرهٔ اتصال‌های پلتفرم — فقط رکوردهای تغییرکرده نوشته می‌شوند.

    این تابع در مسیر داغ است: touch_platform_activity() با هر پیام تلگرام آن را
    صدا می‌زند. نسخهٔ قبلی کل جدول را DELETE و بازنویسی می‌کرد.
    منطق حذف (رکوردهایی که از دیکشنری برداشته شده‌اند) با تفاضل مجموعه‌ها
    عیناً حفظ شده است.
    """
    conn = get_conn()
    written = {}
    try:
        with _lock:
            with conn:
                existing = {
                    (row[0], row[1])
                    for row in conn.execute(
                        "SELECT platform, platform_user_id FROM platform_links"
                    )
                }
                current = set()
                for v in PLATFORM_LINKS.values():
                    pk = (v.get("platform", ""), str(v.get("platform_user_id", "")))
                    current.add(pk)

                    fp = (int(v.get("user_id", 0)), v.get("connected_at", 0),
                          v.get("via", "link"), int(v.get("last_active", 0) or 0),
                          int(v.get("interactions", 0) or 0))
                    if _PLINK_FP.get(pk) == fp and pk in existing:
                        continue

                    conn.execute(
                        "INSERT INTO platform_links "
                        "(platform, platform_user_id, user_id, connected_at, via, last_active, interactions) "
                        "VALUES (?, ?, ?, ?, ?, ?, ?) "
                        "ON CONFLICT(platform, platform_user_id) DO UPDATE SET "
                        "user_id=excluded.user_id, connected_at=excluded.connected_at, via=excluded.via, "
                        "last_active=excluded.last_active, interactions=excluded.interactions",
                        (pk[0], pk[1], fp[0], fp[1], fp[2], fp[3], fp[4]),
                    )
                    written[pk] = fp

                # رکوردهایی که دیگر در حافظه نیستند حذف می‌شوند (مثل رفتار قبلی)
                for pk in existing - current:
                    conn.execute(
                        "DELETE FROM platform_links WHERE platform = ? AND platform_user_id = ?",
                        pk,
                    )
                    _PLINK_FP.pop(pk, None)
    except Exception as e:
        logger.error(f"_save_platform_links error: {e}")
        return
    _PLINK_FP.update(written)


def _save_link_codes():
    conn = get_conn()
    with _lock:
        with conn:
            try:
                conn.execute("DELETE FROM link_codes")
                for v in LINK_CODES.values():
                    conn.execute(
                        "INSERT INTO link_codes "
                        "(code, user_id, platform, mission_id, created_at, expires_at, used, used_at, used_by) "
                        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?) "
                        "ON CONFLICT(code) DO UPDATE SET "
                        "user_id=excluded.user_id, platform=excluded.platform, mission_id=excluded.mission_id, "
                        "created_at=excluded.created_at, expires_at=excluded.expires_at, used=excluded.used, "
                        "used_at=excluded.used_at, used_by=excluded.used_by",
                        (v.get("code", ""), int(v.get("user_id", 0)), v.get("platform", ""),
                         v.get("mission_id", ""), v.get("created_at", 0), v.get("expires_at", 0),
                         int(v.get("used", 0)), v.get("used_at", 0), str(v.get("used_by", ""))),
                    )
            except Exception as e:
                logger.error(f"_save_link_codes error: {e}")


def _save_admin_link_codes():
    conn = get_conn()
    with _lock:
        with conn:
            try:
                conn.execute("DELETE FROM admin_link_codes")
                for v in ADMIN_LINK_CODES.values():
                    conn.execute(
                        "INSERT INTO admin_link_codes "
                        "(code, platform, created_by, created_at, expires_at, used, used_at, used_by) "
                        "VALUES (?, ?, ?, ?, ?, ?, ?, ?) "
                        "ON CONFLICT(code) DO UPDATE SET "
                        "platform=excluded.platform, created_by=excluded.created_by, created_at=excluded.created_at, "
                        "expires_at=excluded.expires_at, used=excluded.used, used_at=excluded.used_at, used_by=excluded.used_by",
                        (v.get("code", ""), v.get("platform", ""), int(v.get("created_by", 0)),
                         v.get("created_at", 0), v.get("expires_at", 0),
                         int(v.get("used", 0)), v.get("used_at", 0), str(v.get("used_by", ""))),
                    )
            except Exception as e:
                logger.error(f"_save_admin_link_codes error: {e}")


def _save_platform_admins():
    conn = get_conn()
    with _lock:
        with conn:
            try:
                conn.execute("DELETE FROM platform_admins")
                for v in PLATFORM_ADMINS.values():
                    conn.execute(
                        "INSERT INTO platform_admins "
                        "(platform, platform_user_id, user_id, added_at) "
                        "VALUES (?, ?, ?, ?) "
                        "ON CONFLICT(platform, platform_user_id) DO UPDATE SET "
                        "user_id=excluded.user_id, added_at=excluded.added_at",
                        (v.get("platform", ""), str(v.get("platform_user_id", "")),
                         int(v.get("user_id", 0)), v.get("added_at", 0)),
                    )
            except Exception as e:
                logger.error(f"_save_platform_admins error: {e}")


def _save_bot_groups():
    conn = get_conn()
    with _lock:
        with conn:
            try:
                conn.execute("DELETE FROM bot_groups")
                for v in BOT_GROUPS.values():
                    conn.execute(
                        "INSERT INTO bot_groups "
                        "(platform, chat_id, title, chat_type, added_at, last_seen) "
                        "VALUES (?, ?, ?, ?, ?, ?) "
                        "ON CONFLICT(platform, chat_id) DO UPDATE SET "
                        "title=excluded.title, chat_type=excluded.chat_type, "
                        "added_at=excluded.added_at, last_seen=excluded.last_seen",
                        (v.get("platform", ""), str(v.get("chat_id", "")),
                         v.get("title", ""), v.get("chat_type", "group"),
                         int(v.get("added_at", 0) or 0), int(v.get("last_seen", 0) or 0)),
                    )
            except Exception as e:
                logger.error(f"_save_bot_groups error: {e}")


# ========================= نقشه ذخیره‌سازی =========================

_SAVE_MAP = {
    "courses":                    _save_courses,
    "progress":                   _save_progress,
    "users":                      _save_users,
    "tickets":                    _save_tickets,
    "settings":                   _save_settings,
    "shop":                       _save_shop,
    "surveys":                    _save_surveys,
    "bot_commands":               _save_bot_commands,
    "missions":                   _save_missions,
    "feature_access":             _save_feature_access,
    "cash_sales":                 _save_cash_sales,
    "user_feature_restrictions":  _save_user_feature_restrictions,
    "cash_sale_settings":         _save_cash_sale_settings,
    "platform_links":             _save_platform_links,
    "link_codes":                 _save_link_codes,
    "admin_link_codes":           _save_admin_link_codes,
    "platform_admins":            _save_platform_admins,
    "bot_groups":                 _save_bot_groups,
}


def save(key: str):
    """ذخیره یک دیکشنری/لیست جهانی در دیتابیس SQLite."""
    fn = _SAVE_MAP.get(key)
    if fn is None:
        logger.warning(f"save: کلید ناشناخته '{key}'")
        return
    try:
        fn()
    except Exception as e:
        logger.error(f"save({key}) خطا: {e}", exc_info=True)


# ========================= راه‌اندازی داده =========================

def setup_data():
    """
    بارگذاری همه داده‌ها از SQLite به دیکشنری‌های جهانی در حافظه.
    باید بعد از init_db() و قبل از شروع polling صدا زده شود.
    چون سایر ماژول‌ها با from config import COURSES... به همین object‌ها
    اشاره دارند، از update/extend استفاده می‌کنیم تا reference‌ها درست بمانند.
    """
    COURSES.update(_load_courses())
    USERS.update(_load_users())
    PROGRESS.update(_load_progress())
    SETTINGS.update(_load_settings())
    SHOP.update(_load_shop())
    SURVEYS.update(_load_surveys())
    TICKETS.extend(_load_tickets())
    BOT_COMMANDS.extend(_load_bot_commands())
    MISSIONS.extend(_load_missions())
    FEATURE_ACCESS.update(_load_feature_access())
    CASH_SALES.extend(_load_cash_sales())
    USER_FEATURE_RESTRICTIONS.update(_load_user_feature_restrictions())
    CASH_SALE_SETTINGS.update(_load_cash_sale_settings())
    PLATFORM_LINKS.update(_load_platform_links())
    LINK_CODES.update(_load_link_codes())
    ADMIN_LINK_CODES.update(_load_admin_link_codes())
    PLATFORM_ADMINS.update(_load_platform_admins())
    BOT_GROUPS.update(_load_bot_groups())
    DELIVERY_REPORTS.extend(_load_delivery_reports())

    # پروایدرهای هوش مصنوعی: ثبت پیش‌فرض‌ها + همگام‌سازی کلیدها با .env
    try:
        seed_ai_providers()
        sync_ai_keys_from_env()
    except Exception as e:
        logger.error(f"راه‌اندازی پروایدرهای AI ناموفق: {e}")

    logger.info(
        f"داده‌ها بارگذاری شدند — "
        f"دوره‌ها: {len(COURSES)} | کاربران: {len(USERS)} | "
        f"تیکت‌ها: {len(TICKETS)} | دستورات: {len(BOT_COMMANDS)} | "
        f"ماموریت‌ها: {len(MISSIONS)} | دسترسی‌ها: {len(FEATURE_ACCESS)} | "
        f"درخواست‌های نقدی: {len(CASH_SALES)} | "
        f"محدودیت‌های کاربر: {sum(len(v) for v in USER_FEATURE_RESTRICTIONS.values())} | "
        f"تنظیمات نقدی: {len(CASH_SALE_SETTINGS)}"
    )
