"""
ai_db.py — جدول‌ها و توابع دیتابیس «یار هوشمند شغلی».

قواعد رعایت‌شده:
  • دیتابیس یکپارچه: همه‌چیز در همان data/bot.db، هیچ فایل جانبی ساخته نمی‌شود.
  • اتصال و قفل نوشتن از db.py گرفته می‌شود (get_conn و _lock) تا با
    بقیهٔ پروژه thread-safe بماند.
  • init_ai_tables(conn) از داخل db.init_db() صدا زده می‌شود.

وابستگی: فقط db و stdlib.
"""
import json
import logging
from datetime import datetime, timezone

import db as _db

logger = logging.getLogger(__name__)


# ========================= کمکی =========================

def _now() -> str:
    """زمان UTC به شکل رشتهٔ استاندارد."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


def _conn():
    return _db.get_conn()


def jloads(raw, default=None):
    """JSON امن — هرگز استثنا پرتاب نمی‌کند."""
    if not raw:
        return default if default is not None else {}
    if isinstance(raw, (dict, list)):
        return raw
    try:
        return json.loads(raw)
    except Exception:
        return default if default is not None else {}


def jdumps(obj) -> str:
    try:
        return json.dumps(obj, ensure_ascii=False)
    except Exception:
        return "{}"


# ========================= ساخت جدول‌ها =========================

_SCHEMA = """
CREATE TABLE IF NOT EXISTS career_paths (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id             INTEGER NOT NULL,
    target_job          TEXT    DEFAULT '',
    interview_data      TEXT    DEFAULT '{}',
    status              TEXT    DEFAULT 'active',
    created_at          TEXT    DEFAULT '',
    completed_at        TEXT    DEFAULT '',
    -- معماری چندعاملی: خروجی خام هر ایجنت جدا نگه داشته می‌شود
    interview_data_json TEXT    DEFAULT '{}',   -- خروجی نهایی ایجنت ۱
    roadmap_json        TEXT    DEFAULT '{}'    -- خروجی ایجنت ۲
);
CREATE INDEX IF NOT EXISTS idx_career_paths_user   ON career_paths(user_id);
CREATE INDEX IF NOT EXISTS idx_career_paths_status ON career_paths(status);

CREATE TABLE IF NOT EXISTS path_steps (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    path_id      INTEGER NOT NULL,
    step_number  INTEGER DEFAULT 0,
    step_type    TEXT    DEFAULT 'resource',
    title        TEXT    DEFAULT '',
    content      TEXT    DEFAULT '{}',
    status       TEXT    DEFAULT 'locked',
    ai_feedback  TEXT    DEFAULT '{}',
    completed_at TEXT    DEFAULT '',
    -- معماری چندعاملی: محتوای Lazy Loaded ایجنت ۳
    content_json TEXT    DEFAULT '{}',
    FOREIGN KEY (path_id) REFERENCES career_paths(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_path_steps_path ON path_steps(path_id);

CREATE TABLE IF NOT EXISTS market_trends (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    skill_name   TEXT    NOT NULL UNIQUE,
    demand_count INTEGER DEFAULT 0,
    source       TEXT    DEFAULT '',
    reason       TEXT    DEFAULT '',
    updated_at   TEXT    DEFAULT ''
);

CREATE TABLE IF NOT EXISTS ai_settings (
    setting_key   TEXT PRIMARY KEY,
    setting_value TEXT DEFAULT '',
    updated_at    TEXT DEFAULT ''
);

CREATE TABLE IF NOT EXISTS ai_usage_logs (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id       INTEGER NOT NULL,
    action_type   TEXT    DEFAULT '',
    cost_credits  INTEGER DEFAULT 0,
    ai_model_used TEXT    DEFAULT '',
    created_at    TEXT    DEFAULT ''
);
CREATE INDEX IF NOT EXISTS idx_ai_usage_user ON ai_usage_logs(user_id);

-- بسته‌های خرید اعتبار — کاملاً قابل مدیریت از پنل ادمین (بدون هاردکد)
CREATE TABLE IF NOT EXISTS ai_credit_packages (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    amount     INTEGER NOT NULL,
    price      INTEGER NOT NULL,
    is_active  INTEGER DEFAULT 1,
    created_at TEXT    DEFAULT ''
);
"""

# بسته‌های اولیه — فقط یک‌بار و تنها اگر جدول خالی باشد درج می‌شوند.
# ادمین می‌تواند آزادانه حذف/اضافه/غیرفعال کند.
# ───────── فاز ۱: پروفایل کاربر ─────────
_PROFILE_SCHEMA = """
CREATE TABLE IF NOT EXISTS user_profiles (
    user_id    INTEGER PRIMARY KEY,
    first_name TEXT    DEFAULT '',
    last_name  TEXT    DEFAULT '',
    age        INTEGER DEFAULT 0,
    city       TEXT    DEFAULT '',
    updated_at TEXT    DEFAULT ''
);
"""

# ───────── فاز ۱: پرداخت و فیش واریزی ─────────
_PAYMENT_SCHEMA = """
CREATE TABLE IF NOT EXISTS admin_payment_info (
    id          INTEGER PRIMARY KEY CHECK (id = 1),   -- تک‌ردیفی
    card_number TEXT DEFAULT '',
    card_holder TEXT DEFAULT '',
    bank_name   TEXT DEFAULT '',
    note        TEXT DEFAULT '',
    updated_at  TEXT DEFAULT ''
);

CREATE TABLE IF NOT EXISTS ai_credit_purchases (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id     INTEGER NOT NULL,
    user_name   TEXT    DEFAULT '',
    package_id  INTEGER DEFAULT 0,
    amount      INTEGER DEFAULT 0,     -- اعتباری که باید شارژ شود
    price       INTEGER DEFAULT 0,     -- مبلغ به تومان
    fiche_file_id TEXT  DEFAULT '',    -- شناسهٔ عکس فیش
    fiche_text  TEXT    DEFAULT '',    -- یا متن رسید
    platform    TEXT    DEFAULT 'bale',
    chat_id     TEXT    DEFAULT '',
    status      TEXT    DEFAULT 'pending',   -- pending | approved | rejected
    admin_note  TEXT    DEFAULT '',
    created_at  TEXT    DEFAULT '',
    reviewed_at TEXT    DEFAULT ''
);
CREATE INDEX IF NOT EXISTS idx_aicp_user   ON ai_credit_purchases(user_id);
CREATE INDEX IF NOT EXISTS idx_aicp_status ON ai_credit_purchases(status);
"""

# ───────── فاز ۲: مسیریابی هوشمند مدل‌ها ─────────
_ROUTING_SCHEMA = """
CREATE TABLE IF NOT EXISTS ai_model_routing (
    action_type      TEXT PRIMARY KEY,
    primary_model    TEXT    DEFAULT '',
    fallback_models  TEXT    DEFAULT '[]',
    cost_per_request REAL    DEFAULT 0,
    is_active        INTEGER DEFAULT 1,
    updated_at       TEXT    DEFAULT ''
);
"""

# مقادیر پیش‌فرض — قالب «پروایدر:مدل» با نام‌های واقعیِ ثبت‌شده در ai_providers.
# نام‌های موجود: Groq / OpenRouter / LLM7 / Cloudflare / GapGPT / AvalAI
DEFAULT_ROUTING = [
    ("interview", "Groq:llama-3.1-8b-instant",
     ["Cloudflare:@cf/meta/llama-3.2-3b-instruct"], 0.0001),
    ("roadmap", "OpenRouter:gpt-4o-mini",
     ["LLM7:codestral-latest", "Groq:llama-3.3-70b-versatile"], 0.0020),
    ("challenge", "Groq:llama-3.3-70b-versatile",
     ["LLM7:devstral-small-2:24b"], 0.0008),
    ("chat", "Groq:mixtral-8x7b-32768",
     ["Cloudflare:@cf/meta/llama-3.1-8b-instruct"], 0.0003),
    ("report", "OpenRouter:anthropic/claude-3-haiku",
     ["AvalAI:gemini-1.5-flash"], 0.0015),
    ("trend", "Cloudflare:@cf/meta/llama-3.2-3b-instruct",
     ["Groq:llama-3.1-8b-instant"], 0.0001),
]

ACTION_FA = {
    "interview": "🎤 مصاحبه",
    "roadmap":   "🗺 نقشه راه",
    "challenge": "🧩 چالش",
    "chat":      "💬 چت منتور",
    "report":    "📄 گزارش",
    "trend":     "🔥 ترندها",
}

# ───────── فاز ۲: تاریخچهٔ چت آموزشی ─────────
_CHAT_SCHEMA = """
CREATE TABLE IF NOT EXISTS ai_chat_history (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id    INTEGER NOT NULL,
    path_id    INTEGER DEFAULT 0,
    step_id    INTEGER DEFAULT 0,
    role       TEXT    DEFAULT 'user',
    content    TEXT    DEFAULT '',
    created_at TEXT    DEFAULT ''
);
CREATE INDEX IF NOT EXISTS idx_chat_hist ON ai_chat_history(user_id, step_id);
"""

# ───────── فاز ۲: تاریخچهٔ ترند برای محاسبهٔ رشد ─────────
_TREND_HISTORY_SCHEMA = """
CREATE TABLE IF NOT EXISTS market_trend_history (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    skill_name   TEXT    NOT NULL,
    demand_count INTEGER DEFAULT 0,
    recorded_at  TEXT    DEFAULT ''
);
CREATE INDEX IF NOT EXISTS idx_trend_hist ON market_trend_history(skill_name);
"""

# ───────── فاز ۳: گزارش، گواهینامه، شبیه‌ساز، همزاد شغلی ─────────
_PHASE3_SCHEMA = """
CREATE TABLE IF NOT EXISTS ai_career_reports (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id           INTEGER NOT NULL,
    path_id           INTEGER DEFAULT 0,
    target_job        TEXT    DEFAULT '',
    readiness_percent INTEGER DEFAULT 0,
    report_json       TEXT    DEFAULT '{}',
    created_at        TEXT    DEFAULT ''
);
CREATE INDEX IF NOT EXISTS idx_reports_user ON ai_career_reports(user_id, path_id);

CREATE TABLE IF NOT EXISTS ai_certificates (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id        INTEGER NOT NULL,
    path_id        INTEGER DEFAULT 0,
    certificate_id TEXT    UNIQUE NOT NULL,
    target_job     TEXT    DEFAULT '',
    readiness      INTEGER DEFAULT 0,
    file_path      TEXT    DEFAULT '',
    created_at     TEXT    DEFAULT ''
);
CREATE INDEX IF NOT EXISTS idx_cert_user ON ai_certificates(user_id);

CREATE TABLE IF NOT EXISTS interview_simulations (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id        INTEGER NOT NULL,
    target_job     TEXT    DEFAULT '',
    questions_json TEXT    DEFAULT '[]',
    scores_json    TEXT    DEFAULT '[]',
    final_score    INTEGER DEFAULT 0,
    report_json    TEXT    DEFAULT '{}',
    status         TEXT    DEFAULT 'active',   -- active | finished
    created_at     TEXT    DEFAULT ''
);
CREATE INDEX IF NOT EXISTS idx_sim_user ON interview_simulations(user_id);

CREATE TABLE IF NOT EXISTS ai_career_twin (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id    INTEGER NOT NULL,
    path_id    INTEGER DEFAULT 0,
    result_json TEXT   DEFAULT '{}',
    created_at TEXT    DEFAULT ''
);
CREATE INDEX IF NOT EXISTS idx_twin_user ON ai_career_twin(user_id);
"""

# ───────── فاز ۴: مأموریت واقعی، تیم، پروفایل عمومی ─────────
_PHASE4_SCHEMA = """
CREATE TABLE IF NOT EXISTS real_missions (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    title           TEXT    DEFAULT '',
    description     TEXT    DEFAULT '',
    reward_credits  INTEGER DEFAULT 0,
    required_skills TEXT    DEFAULT '[]',
    status          TEXT    DEFAULT 'active',   -- active | completed
    created_by      INTEGER DEFAULT 0,
    created_at      TEXT    DEFAULT ''
);
CREATE INDEX IF NOT EXISTS idx_rm_status ON real_missions(status);

CREATE TABLE IF NOT EXISTS user_missions (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id         INTEGER NOT NULL,
    mission_id      INTEGER NOT NULL,
    submission_text TEXT    DEFAULT '',
    status          TEXT    DEFAULT 'pending',  -- pending | approved | rejected
    ai_grade        INTEGER DEFAULT 0,
    ai_feedback     TEXT    DEFAULT '',
    created_at      TEXT    DEFAULT ''
);
CREATE INDEX IF NOT EXISTS idx_um_user ON user_missions(user_id, mission_id);

CREATE TABLE IF NOT EXISTS learning_teams (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    team_name           TEXT    DEFAULT '',
    project_description TEXT    DEFAULT '',
    target_job          TEXT    DEFAULT '',
    city                TEXT    DEFAULT '',
    max_members         INTEGER DEFAULT 4,
    status              TEXT    DEFAULT 'forming',  -- forming | active | completed
    created_at          TEXT    DEFAULT ''
);
CREATE INDEX IF NOT EXISTS idx_lt_status ON learning_teams(status);

CREATE TABLE IF NOT EXISTS team_members (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    team_id   INTEGER NOT NULL,
    user_id   INTEGER NOT NULL,
    role      TEXT    DEFAULT 'member',   -- leader | member
    joined_at TEXT    DEFAULT '',
    UNIQUE (team_id, user_id)
);
CREATE INDEX IF NOT EXISTS idx_tm_user ON team_members(user_id);

CREATE TABLE IF NOT EXISTS public_profiles (
    user_id           INTEGER PRIMARY KEY,
    is_public         INTEGER DEFAULT 0,
    custom_bio        TEXT    DEFAULT '',
    verification_code TEXT    UNIQUE,
    views             INTEGER DEFAULT 0,
    updated_at        TEXT    DEFAULT ''
);
CREATE INDEX IF NOT EXISTS idx_pp_code ON public_profiles(verification_code);
"""

DEFAULT_PACKAGES = [
    (1000, 50000),
    (3000, 120000),
    (10000, 350000),
]

# تعرفهٔ پیش‌فرض هر اکشن (قابل تغییر از پنل ادمین)
DEFAULT_SETTINGS = {
    "price_roadmap":    "100",   # مصاحبه + تولید نقشه راه
    "price_chat":       "0",     # هر پیام چت با منتور
    "price_challenge":  "50",    # تصحیح یک چالش
    "price_report":     "200",   # گزارش آمادگی شغلی
    "price_trends":     "0",     # مشاهدهٔ ترندها — رایگان
    "price_help":       "10",    # کمک حین آموزش (چت آگاه‌از‌زمینه)
    "price_interview_sim": "100",  # شبیه‌ساز مصاحبه (۱۰ سؤال)
    "price_twin":       "300",   # شبیه‌سازی همزاد شغلی
    "free_quota":       "3",     # ۳ تعامل اول هر کاربر رایگان
    "enabled":          "1",     # کلید روشن/خاموش کل ماژول
    "model":            "",      # خالی = انتخاب خودکار (ask_ai_fast)
    "system_prompt":    "",      # پرامپت سفارشی ادمین (اختیاری)
}


def _migrate_agent_columns(c) -> None:
    """افزودن ستون‌های معماری چندعاملی به جدول‌های قدیمی (migration ایمن).

    روی دیتابیس تازه کاری نمی‌کند (ستون‌ها در _SCHEMA هستند) و روی
    دیتابیس قدیمی هر ستون را فقط اگر نبود اضافه می‌کند.
    """
    migrations = (
        ("career_paths", "interview_data_json", "TEXT DEFAULT '{}'"),
        ("career_paths", "roadmap_json",        "TEXT DEFAULT '{}'"),
        ("path_steps",   "content_json",        "TEXT DEFAULT '{}'"),
    )
    for table, column, decl in migrations:
        try:
            cols = {r[1] for r in c.execute(f"PRAGMA table_info({table})").fetchall()}
            if column not in cols:
                c.execute(f"ALTER TABLE {table} ADD COLUMN {column} {decl}")
                logger.info(f"🧩 ستون {table}.{column} اضافه شد.")
        except Exception as e:
            logger.warning(f"مهاجرت {table}.{column} ناموفق: {e}")


def init_ai_tables(conn=None) -> None:
    """ساخت جدول‌های ماژول + درج تنظیمات پیش‌فرض.

    از داخل db.init_db() صدا زده می‌شود. اگر conn داده نشود، از اتصال
    فعال db استفاده می‌کند.
    """
    c = conn if conn is not None else _conn()
    try:
        c.executescript(_SCHEMA)
        for k, v in DEFAULT_SETTINGS.items():
            c.execute(
                "INSERT INTO ai_settings (setting_key, setting_value, updated_at) "
                "VALUES (?, ?, ?) ON CONFLICT DO NOTHING",
                (k, v, _now()),
            )

        # ── مهاجرت یک‌باره ─────────────────────────────────────────────
        # در نسخهٔ اول، مقدار enabled می‌توانست روی "0" بماند و چون در
        # دیتابیس ذخیره می‌شد، با ری‌استارت هم برنمی‌گشت؛ نتیجه پیام
        # «این بخش موقتاً غیرفعال است» برای کاربر بود.
        # این مهاجرت فقط یک‌بار اجرا می‌شود و ماژول را روشن می‌کند.
        # پس از آن، دکمهٔ پنل ادمین آزادانه کار می‌کند و دوباره بازنویسی نمی‌شود.
        done = c.execute(
            "SELECT setting_value FROM ai_settings WHERE setting_key = 'enabled_reset_v2'"
        ).fetchone()
        if done is None:
            c.execute(
                "UPDATE ai_settings SET setting_value = '1', updated_at = ? "
                "WHERE setting_key = 'enabled'",
                (_now(),),
            )
            c.execute(
                "INSERT INTO ai_settings (setting_key, setting_value, updated_at) "
                "VALUES ('enabled_reset_v2', '1', ?) "
                "ON CONFLICT(setting_key) DO UPDATE SET setting_value=excluded.setting_value, updated_at=excluded.updated_at",
                (_now(),),
            )
            logger.info("🤖 ماژول یار هوشمند به‌صورت پیش‌فرض فعال شد (مهاجرت یک‌باره).")

        # ── مهاجرت ستون‌های معماری چندعاملی ───────────────────────────
        # دیتابیس‌های قدیمی این سه ستون را ندارند. ALTER TABLE در SQLite
        # اگر ستون موجود باشد خطا می‌دهد، پس اول فهرست ستون‌ها را می‌خوانیم.
        _migrate_agent_columns(c)

        # بسته‌های پیش‌فرض فقط وقتی جدول کاملاً خالی است درج می‌شوند؛
        # پس اگر ادمین همه را حذف کرد، دوباره برنمی‌گردند.
        empty = c.execute("SELECT COUNT(*) FROM ai_credit_packages").fetchone()[0]
        if not empty:
            for amount, price in DEFAULT_PACKAGES:
                c.execute(
                    "INSERT INTO ai_credit_packages (amount, price, is_active, created_at) "
                    "VALUES (?, ?, 1, ?)",
                    (amount, price, _now()),
                )
        c.commit()
        logger.info("✅ جدول‌های «یار هوشمند شغلی» آماده است.")
    except Exception as e:
        logger.error(f"init_ai_tables خطا: {e}", exc_info=True)


# ========================= مسیریابی مدل‌ها (فاز ۲) =========================

def init_model_routing_table(conn=None) -> None:
    """ساخت جدول ai_model_routing + درج پیش‌فرض‌ها (فقط اگر نبودند)."""
    c = conn if conn is not None else _conn()
    try:
        c.executescript(_ROUTING_SCHEMA)
        for action, primary, fbs, cost in DEFAULT_ROUTING:
            c.execute(
                "INSERT INTO ai_model_routing "
                "(action_type, primary_model, fallback_models, cost_per_request, "
                " is_active, updated_at) VALUES (?, ?, ?, ?, 1, ?) ON CONFLICT DO NOTHING",
                (action, primary, jdumps(fbs), float(cost), _now()),
            )
        c.commit()
    except Exception as e:
        logger.error(f"init_model_routing_table خطا: {e}", exc_info=True)


def get_model_routing(action_type: str):
    """تنظیم مسیریابی یک اکشن یا None."""
    try:
        row = _conn().execute(
            "SELECT * FROM ai_model_routing WHERE action_type = ?", (action_type,)
        ).fetchone()
        if row is None:
            return None
        d = dict(row)
        d["fallback_models"] = jloads(d.get("fallback_models"), [])
        return d
    except Exception as e:
        logger.error(f"get_model_routing: {e}")
        return None


def list_model_routing() -> list:
    try:
        rows = _conn().execute(
            "SELECT * FROM ai_model_routing ORDER BY action_type ASC"
        ).fetchall()
        out = []
        for r in rows:
            d = dict(r)
            d["fallback_models"] = jloads(d.get("fallback_models"), [])
            out.append(d)
        return out
    except Exception as e:
        logger.error(f"list_model_routing: {e}")
        return []


def update_model_routing(action_type: str, primary_model: str = None,
                         fallback_models=None, cost_per_request=None,
                         is_active=None) -> bool:
    """به‌روزرسانی جزئی — فیلدهای None دست‌نخورده می‌مانند."""
    cur = get_model_routing(action_type)
    if cur is None:
        return False
    try:
        with _db._lock:
            with _conn() as c:
                c.execute(
                    "UPDATE ai_model_routing SET primary_model = ?, "
                    "fallback_models = ?, cost_per_request = ?, is_active = ?, "
                    "updated_at = ? WHERE action_type = ?",
                    (primary_model if primary_model is not None else cur["primary_model"],
                     jdumps(fallback_models if fallback_models is not None
                            else cur["fallback_models"]),
                     float(cost_per_request if cost_per_request is not None
                           else cur["cost_per_request"]),
                     int(is_active if is_active is not None else cur["is_active"]),
                     _now(), action_type),
                )
        return True
    except Exception as e:
        logger.error(f"update_model_routing: {e}")
        return False


def toggle_model_routing(action_type: str) -> bool:
    cur = get_model_routing(action_type)
    if cur is None:
        return False
    return update_model_routing(action_type, is_active=0 if cur["is_active"] else 1)


# ========================= تاریخچهٔ چت آموزشی (فاز ۲) =========================

def init_chat_history_table(conn=None) -> None:
    c = conn if conn is not None else _conn()
    try:
        c.executescript(_CHAT_SCHEMA)
        c.commit()
    except Exception as e:
        logger.error(f"init_chat_history_table خطا: {e}", exc_info=True)


def save_chat_message(user_id: int, path_id: int, step_id: int,
                      role: str, content: str) -> int:
    """ثبت یک پیام + هرس روی ۳۰ پیام آخر هر گام (جلوگیری از رشد بی‌نهایت)."""
    try:
        with _db._lock:
            with _conn() as c:
                cur = c.execute(
                    "INSERT INTO ai_chat_history "
                    "(user_id, path_id, step_id, role, content, created_at) "
                    "VALUES (?, ?, ?, ?, ?, ?)",
                    (int(user_id), int(path_id or 0), int(step_id or 0),
                     role if role in ("user", "assistant") else "user",
                     (content or "")[:2000], _now()),
                )
                c.execute(
                    "DELETE FROM ai_chat_history WHERE user_id = ? AND step_id = ? "
                    "AND id NOT IN (SELECT id FROM ai_chat_history "
                    "WHERE user_id = ? AND step_id = ? ORDER BY id DESC LIMIT 30)",
                    (int(user_id), int(step_id or 0), int(user_id), int(step_id or 0)),
                )
                return int(cur.lastrowid or 0)
    except Exception as e:
        logger.error(f"save_chat_message: {e}")
        return 0


def get_chat_history(user_id: int, path_id: int = 0, step_id: int = 0,
                     limit: int = 10) -> list:
    """آخرین پیام‌ها به ترتیب قدیمی → جدید (مناسب برای دادن به مدل)."""
    try:
        rows = _conn().execute(
            "SELECT role, content, created_at FROM ai_chat_history "
            "WHERE user_id = ? AND step_id = ? ORDER BY id DESC LIMIT ?",
            (int(user_id), int(step_id or 0), int(limit)),
        ).fetchall()
        return [dict(r) for r in reversed(rows)]
    except Exception as e:
        logger.error(f"get_chat_history: {e}")
        return []


def clear_chat_history(user_id: int, step_id: int = 0) -> bool:
    try:
        with _db._lock:
            with _conn() as c:
                c.execute(
                    "DELETE FROM ai_chat_history WHERE user_id = ? AND step_id = ?",
                    (int(user_id), int(step_id or 0)),
                )
        return True
    except Exception as e:
        logger.error(f"clear_chat_history: {e}")
        return False


# ========================= رشد ترندها (فاز ۲) =========================

def init_trend_history_table(conn=None) -> None:
    c = conn if conn is not None else _conn()
    try:
        c.executescript(_TREND_HISTORY_SCHEMA)
        c.commit()
    except Exception as e:
        logger.error(f"init_trend_history_table خطا: {e}", exc_info=True)


def record_trend_snapshot(skill_name: str, demand_count: int) -> None:
    """ثبت یک نقطه در تاریخچه — مبنای محاسبهٔ رشد."""
    try:
        with _db._lock:
            with _conn() as c:
                c.execute(
                    "INSERT INTO market_trend_history "
                    "(skill_name, demand_count, recorded_at) VALUES (?, ?, ?)",
                    (skill_name.strip(), int(demand_count or 0), _now()),
                )
                c.execute(
                    "DELETE FROM market_trend_history WHERE skill_name = ? "
                    "AND id NOT IN (SELECT id FROM market_trend_history "
                    "WHERE skill_name = ? ORDER BY id DESC LIMIT 24)",
                    (skill_name.strip(), skill_name.strip()),
                )
    except Exception as e:
        logger.error(f"record_trend_snapshot: {e}")


def get_trend_growth(skill_name: str, months: int = 6) -> dict:
    """درصد رشد یک مهارت بین قدیمی‌ترین و جدیدترین نقطهٔ ثبت‌شده.

    خروجی: {ok, first, last, change, percent, points}
    اگر تاریخچهٔ کافی نباشد ok=False برمی‌گردد (نمودار نمایش داده نمی‌شود).
    """
    out = {"ok": False, "first": 0, "last": 0, "change": 0, "percent": 0.0, "points": []}
    try:
        rows = _conn().execute(
            "SELECT demand_count FROM market_trend_history WHERE skill_name = ? "
            "ORDER BY id DESC LIMIT ?", (skill_name, int(max(2, months))),
        ).fetchall()
        pts = [int(r[0] or 0) for r in reversed(rows)]
        if len(pts) < 2:
            return out
        first, last = pts[0], pts[-1]
        out.update({
            "ok": True, "first": first, "last": last,
            "change": last - first,
            "percent": round(((last - first) / first * 100) if first else 0.0, 1),
            "points": pts,
        })
    except Exception as e:
        logger.error(f"get_trend_growth: {e}")
    return out


# ========================= فاز ۳: گزارش / گواهینامه / مصاحبه / همزاد ==========

def init_phase3_tables(conn=None) -> None:
    """ساخت جدول‌های فاز ۳. از db.init_db() صدا زده می‌شود."""
    c = conn if conn is not None else _conn()
    try:
        c.executescript(_PHASE3_SCHEMA)
        c.commit()
    except Exception as e:
        logger.error(f"init_phase3_tables خطا: {e}", exc_info=True)


# ---- گزارش آمادگی شغلی ----

def save_career_report(user_id: int, path_id: int, target_job: str,
                       readiness: int, report: dict) -> int:
    try:
        with _db._lock:
            with _conn() as c:
                cur = c.execute(
                    "INSERT INTO ai_career_reports "
                    "(user_id, path_id, target_job, readiness_percent, report_json, created_at) "
                    "VALUES (?, ?, ?, ?, ?, ?)",
                    (int(user_id), int(path_id or 0), (target_job or "")[:120],
                     int(readiness or 0), jdumps(report or {}), _now()),
                )
                return int(cur.lastrowid or 0)
    except Exception as e:
        logger.error(f"save_career_report: {e}")
        return 0


def list_career_reports(user_id: int, path_id: int = None, limit: int = 10) -> list:
    try:
        if path_id is None:
            rows = _conn().execute(
                "SELECT * FROM ai_career_reports WHERE user_id = ? "
                "ORDER BY id DESC LIMIT ?", (int(user_id), int(limit))).fetchall()
        else:
            rows = _conn().execute(
                "SELECT * FROM ai_career_reports WHERE user_id = ? AND path_id = ? "
                "ORDER BY id DESC LIMIT ?",
                (int(user_id), int(path_id), int(limit))).fetchall()
        out = []
        for r in rows:
            d = dict(r)
            d["report_json"] = jloads(d.get("report_json"), {})
            out.append(d)
        return out
    except Exception as e:
        logger.error(f"list_career_reports: {e}")
        return []


def get_career_report(report_id: int):
    try:
        row = _conn().execute(
            "SELECT * FROM ai_career_reports WHERE id = ?", (int(report_id),)).fetchone()
        if row is None:
            return None
        d = dict(row)
        d["report_json"] = jloads(d.get("report_json"), {})
        return d
    except Exception as e:
        logger.error(f"get_career_report: {e}")
        return None


# ---- گواهینامه ----

def save_certificate(user_id: int, path_id: int, certificate_id: str,
                     target_job: str, readiness: int, file_path: str) -> int:
    try:
        with _db._lock:
            with _conn() as c:
                cur = c.execute(
                    "INSERT INTO ai_certificates "
                    "(user_id, path_id, certificate_id, target_job, readiness, "
                    " file_path, created_at) VALUES (?, ?, ?, ?, ?, ?, ?) ON CONFLICT DO NOTHING",
                    (int(user_id), int(path_id or 0), certificate_id,
                     (target_job or "")[:120], int(readiness or 0),
                     file_path or "", _now()),
                )
                return int(cur.lastrowid or 0)
    except Exception as e:
        logger.error(f"save_certificate: {e}")
        return 0


def get_certificate_for_path(user_id: int, path_id: int):
    """گواهینامهٔ موجود یک مسیر — برای جلوگیری از صدور تکراری."""
    try:
        row = _conn().execute(
            "SELECT * FROM ai_certificates WHERE user_id = ? AND path_id = ? "
            "ORDER BY id DESC LIMIT 1", (int(user_id), int(path_id))).fetchone()
        return dict(row) if row is not None else None
    except Exception as e:
        logger.error(f"get_certificate_for_path: {e}")
        return None


def list_certificates(user_id: int, limit: int = 20) -> list:
    try:
        rows = _conn().execute(
            "SELECT * FROM ai_certificates WHERE user_id = ? ORDER BY id DESC LIMIT ?",
            (int(user_id), int(limit))).fetchall()
        return [dict(r) for r in rows]
    except Exception as e:
        logger.error(f"list_certificates: {e}")
        return []


def get_certificate(cert_row_id: int):
    try:
        row = _conn().execute(
            "SELECT * FROM ai_certificates WHERE id = ?", (int(cert_row_id),)).fetchone()
        return dict(row) if row is not None else None
    except Exception as e:
        logger.error(f"get_certificate: {e}")
        return None


# ---- شبیه‌ساز مصاحبه ----

def create_simulation(user_id: int, target_job: str, questions: list) -> int:
    try:
        with _db._lock:
            with _conn() as c:
                c.execute(
                    "UPDATE interview_simulations SET status = 'finished' "
                    "WHERE user_id = ? AND status = 'active'", (int(user_id),))
                cur = c.execute(
                    "INSERT INTO interview_simulations "
                    "(user_id, target_job, questions_json, scores_json, final_score, "
                    " report_json, status, created_at) "
                    "VALUES (?, ?, ?, '[]', 0, '{}', 'active', ?)",
                    (int(user_id), (target_job or "")[:120],
                     jdumps(questions or []), _now()),
                )
                return int(cur.lastrowid or 0)
    except Exception as e:
        logger.error(f"create_simulation: {e}")
        return 0


def get_simulation(sim_id: int):
    try:
        row = _conn().execute(
            "SELECT * FROM interview_simulations WHERE id = ?", (int(sim_id),)).fetchone()
        if row is None:
            return None
        d = dict(row)
        d["questions_json"] = jloads(d.get("questions_json"), [])
        d["scores_json"] = jloads(d.get("scores_json"), [])
        d["report_json"] = jloads(d.get("report_json"), {})
        return d
    except Exception as e:
        logger.error(f"get_simulation: {e}")
        return None


def append_simulation_answer(sim_id: int, question: str, answer: str) -> bool:
    """ثبت یک پاسخ. نمره‌دهی در پایان انجام می‌شود (یک فراخوانی AI به‌جای ۱۰)."""
    sim = get_simulation(sim_id)
    if not sim:
        return False
    scores = sim["scores_json"]
    scores.append({"q": (question or "")[:400], "a": (answer or "")[:1500]})
    try:
        with _db._lock:
            with _conn() as c:
                c.execute(
                    "UPDATE interview_simulations SET scores_json = ? WHERE id = ?",
                    (jdumps(scores), int(sim_id)))
        return True
    except Exception as e:
        logger.error(f"append_simulation_answer: {e}")
        return False


def finish_simulation(sim_id: int, final_score: int, report: dict) -> bool:
    try:
        with _db._lock:
            with _conn() as c:
                c.execute(
                    "UPDATE interview_simulations SET status = 'finished', "
                    "final_score = ?, report_json = ? WHERE id = ?",
                    (int(final_score or 0), jdumps(report or {}), int(sim_id)))
        return True
    except Exception as e:
        logger.error(f"finish_simulation: {e}")
        return False


def list_simulations(user_id: int, limit: int = 10) -> list:
    try:
        rows = _conn().execute(
            "SELECT * FROM interview_simulations WHERE user_id = ? "
            "ORDER BY id DESC LIMIT ?", (int(user_id), int(limit))).fetchall()
        out = []
        for r in rows:
            d = dict(r)
            d["report_json"] = jloads(d.get("report_json"), {})
            out.append(d)
        return out
    except Exception as e:
        logger.error(f"list_simulations: {e}")
        return []


# ---- همزاد شغلی ----

def save_career_twin(user_id: int, path_id: int, result: dict) -> int:
    try:
        with _db._lock:
            with _conn() as c:
                cur = c.execute(
                    "INSERT INTO ai_career_twin (user_id, path_id, result_json, created_at) "
                    "VALUES (?, ?, ?, ?)",
                    (int(user_id), int(path_id or 0), jdumps(result or {}), _now()))
                return int(cur.lastrowid or 0)
    except Exception as e:
        logger.error(f"save_career_twin: {e}")
        return 0


def latest_career_twin(user_id: int):
    try:
        row = _conn().execute(
            "SELECT * FROM ai_career_twin WHERE user_id = ? ORDER BY id DESC LIMIT 1",
            (int(user_id),)).fetchone()
        if row is None:
            return None
        d = dict(row)
        d["result_json"] = jloads(d.get("result_json"), {})
        return d
    except Exception as e:
        logger.error(f"latest_career_twin: {e}")
        return None


# ========================= فاز ۴: مأموریت / تیم / پروفایل عمومی =========

def init_phase4_tables(conn=None) -> None:
    """ساخت جدول‌های فاز ۴. از db.init_db() صدا زده می‌شود."""
    c = conn if conn is not None else _conn()
    try:
        c.executescript(_PHASE4_SCHEMA)
        c.commit()
    except Exception as e:
        logger.error(f"init_phase4_tables خطا: {e}", exc_info=True)


# ---- مأموریت‌های واقعی ----

def add_real_mission(title: str, description: str, reward_credits: int,
                     required_skills=None, created_by: int = 0) -> int:
    try:
        with _db._lock:
            with _conn() as c:
                cur = c.execute(
                    "INSERT INTO real_missions (title, description, reward_credits, "
                    "required_skills, status, created_by, created_at) "
                    "VALUES (?, ?, ?, ?, 'active', ?, ?)",
                    ((title or "")[:150], (description or "")[:2000],
                     max(0, int(reward_credits or 0)),
                     jdumps(required_skills or []), int(created_by or 0), _now()),
                )
                return int(cur.lastrowid or 0)
    except Exception as e:
        logger.error(f"add_real_mission: {e}")
        return 0


def list_real_missions(only_active: bool = False, limit: int = 30) -> list:
    try:
        sql = "SELECT * FROM real_missions"
        if only_active:
            sql += " WHERE status = 'active'"
        sql += " ORDER BY id DESC LIMIT ?"
        rows = _conn().execute(sql, (int(limit),)).fetchall()
        out = []
        for r in rows:
            d = dict(r)
            d["required_skills"] = jloads(d.get("required_skills"), [])
            out.append(d)
        return out
    except Exception as e:
        logger.error(f"list_real_missions: {e}")
        return []


def get_real_mission(mission_id: int):
    try:
        row = _conn().execute(
            "SELECT * FROM real_missions WHERE id = ?", (int(mission_id),)).fetchone()
        if row is None:
            return None
        d = dict(row)
        d["required_skills"] = jloads(d.get("required_skills"), [])
        return d
    except Exception as e:
        logger.error(f"get_real_mission: {e}")
        return None


def toggle_real_mission(mission_id: int) -> bool:
    try:
        with _db._lock:
            with _conn() as c:
                c.execute(
                    "UPDATE real_missions SET status = "
                    "CASE status WHEN 'active' THEN 'completed' ELSE 'active' END "
                    "WHERE id = ?", (int(mission_id),))
        return True
    except Exception as e:
        logger.error(f"toggle_real_mission: {e}")
        return False


def delete_real_mission(mission_id: int) -> bool:
    try:
        with _db._lock:
            with _conn() as c:
                c.execute("DELETE FROM real_missions WHERE id = ?", (int(mission_id),))
        return True
    except Exception as e:
        logger.error(f"delete_real_mission: {e}")
        return False


def submit_user_mission(user_id: int, mission_id: int, submission_text: str,
                        status: str = "pending", ai_grade: int = 0,
                        ai_feedback: str = "") -> int:
    try:
        with _db._lock:
            with _conn() as c:
                cur = c.execute(
                    "INSERT INTO user_missions (user_id, mission_id, submission_text, "
                    "status, ai_grade, ai_feedback, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (int(user_id), int(mission_id), (submission_text or "")[:4000],
                     status, int(ai_grade or 0), (ai_feedback or "")[:1000], _now()),
                )
                return int(cur.lastrowid or 0)
    except Exception as e:
        logger.error(f"submit_user_mission: {e}")
        return 0


def get_user_mission(user_id: int, mission_id: int):
    """آخرین ارسال کاربر برای یک مأموریت."""
    try:
        row = _conn().execute(
            "SELECT * FROM user_missions WHERE user_id = ? AND mission_id = ? "
            "ORDER BY id DESC LIMIT 1", (int(user_id), int(mission_id))).fetchone()
        return dict(row) if row is not None else None
    except Exception as e:
        logger.error(f"get_user_mission: {e}")
        return None


def list_user_missions(user_id: int, limit: int = 20) -> list:
    try:
        rows = _conn().execute(
            "SELECT um.*, rm.title FROM user_missions um "
            "LEFT JOIN real_missions rm ON rm.id = um.mission_id "
            "WHERE um.user_id = ? ORDER BY um.id DESC LIMIT ?",
            (int(user_id), int(limit))).fetchall()
        return [dict(r) for r in rows]
    except Exception as e:
        logger.error(f"list_user_missions: {e}")
        return []


def approved_mission_titles(user_id: int) -> list:
    """عنوان مأموریت‌های تأییدشده — برای پروفایل عمومی."""
    try:
        rows = _conn().execute(
            "SELECT rm.title FROM user_missions um "
            "JOIN real_missions rm ON rm.id = um.mission_id "
            "WHERE um.user_id = ? AND um.status = 'approved'",
            (int(user_id),)).fetchall()
        return [r[0] for r in rows if r[0]]
    except Exception as e:
        logger.error(f"approved_mission_titles: {e}")
        return []


# ---- تیم یادگیری ----

def create_team(team_name: str, project_description: str = "",
                target_job: str = "", city: str = "", max_members: int = 4) -> int:
    try:
        with _db._lock:
            with _conn() as c:
                cur = c.execute(
                    "INSERT INTO learning_teams (team_name, project_description, "
                    "target_job, city, max_members, status, created_at) "
                    "VALUES (?, ?, ?, ?, ?, 'forming', ?)",
                    ((team_name or "")[:100], (project_description or "")[:1000],
                     (target_job or "")[:120], (city or "")[:60],
                     max(2, int(max_members or 4)), _now()),
                )
                return int(cur.lastrowid or 0)
    except Exception as e:
        logger.error(f"create_team: {e}")
        return 0


def get_team(team_id: int):
    try:
        row = _conn().execute(
            "SELECT * FROM learning_teams WHERE id = ?", (int(team_id),)).fetchone()
        return dict(row) if row is not None else None
    except Exception as e:
        logger.error(f"get_team: {e}")
        return None


def team_member_count(team_id: int) -> int:
    try:
        row = _conn().execute(
            "SELECT COUNT(*) FROM team_members WHERE team_id = ?",
            (int(team_id),)).fetchone()
        return int(row[0] or 0)
    except Exception as e:
        logger.error(f"team_member_count: {e}")
        return 0


def get_team_members(team_id: int) -> list:
    try:
        rows = _conn().execute(
            "SELECT * FROM team_members WHERE team_id = ? ORDER BY id ASC",
            (int(team_id),)).fetchall()
        return [dict(r) for r in rows]
    except Exception as e:
        logger.error(f"get_team_members: {e}")
        return []


def get_user_team(user_id: int):
    """تیم فعلی کاربر (اگر عضو تیمی باشد)."""
    try:
        row = _conn().execute(
            "SELECT t.*, m.role FROM team_members m "
            "JOIN learning_teams t ON t.id = m.team_id "
            "WHERE m.user_id = ? ORDER BY m.id DESC LIMIT 1",
            (int(user_id),)).fetchone()
        return dict(row) if row is not None else None
    except Exception as e:
        logger.error(f"get_user_team: {e}")
        return None


def add_team_member(team_id: int, user_id: int, role: str = "member") -> bool:
    """افزودن عضو — ظرفیت تیم رعایت می‌شود و عضویت تکراری رد می‌گردد."""
    try:
        with _db._lock:
            with _conn() as c:
                t = c.execute("SELECT max_members FROM learning_teams WHERE id = ?",
                              (int(team_id),)).fetchone()
                if t is None:
                    return False
                n = c.execute("SELECT COUNT(*) FROM team_members WHERE team_id = ?",
                              (int(team_id),)).fetchone()[0]
                if int(n or 0) >= int(t[0] or 4):
                    return False
                c.execute(
                    "INSERT INTO team_members (team_id, user_id, role, joined_at) "
                    "VALUES (?, ?, ?, ?) ON CONFLICT DO NOTHING",
                    (int(team_id), int(user_id),
                     role if role in ("leader", "member") else "member", _now()))
                # پر شدن ظرفیت → تیم فعال می‌شود
                n2 = c.execute("SELECT COUNT(*) FROM team_members WHERE team_id = ?",
                               (int(team_id),)).fetchone()[0]
                if int(n2 or 0) >= int(t[0] or 4):
                    c.execute("UPDATE learning_teams SET status = 'active' WHERE id = ?",
                              (int(team_id),))
        return True
    except Exception as e:
        logger.error(f"add_team_member: {e}")
        return False


def leave_team(user_id: int, team_id: int) -> bool:
    try:
        with _db._lock:
            with _conn() as c:
                c.execute("DELETE FROM team_members WHERE user_id = ? AND team_id = ?",
                          (int(user_id), int(team_id)))
                n = c.execute("SELECT COUNT(*) FROM team_members WHERE team_id = ?",
                              (int(team_id),)).fetchone()[0]
                if int(n or 0) == 0:
                    c.execute("DELETE FROM learning_teams WHERE id = ?", (int(team_id),))
                else:
                    c.execute("UPDATE learning_teams SET status = 'forming' WHERE id = ?",
                              (int(team_id),))
        return True
    except Exception as e:
        logger.error(f"leave_team: {e}")
        return False


def find_forming_team(target_job: str = "", city: str = ""):
    """تیمی در حال تشکیل با شغل هدف مشابه (ترجیحاً همان شهر)."""
    try:
        rows = _conn().execute(
            "SELECT t.* FROM learning_teams t WHERE t.status = 'forming' "
            "AND (SELECT COUNT(*) FROM team_members m WHERE m.team_id = t.id) < t.max_members "
            "ORDER BY t.id ASC LIMIT 30").fetchall()
        cands = [dict(r) for r in rows]
        if not cands:
            return None
        tj = (target_job or "").strip().lower()
        ct = (city or "").strip().lower()
        # اولویت: شغل + شهر → شغل → هر تیم باز
        for c in cands:
            if tj and (c.get("target_job") or "").lower() == tj \
                    and ct and (c.get("city") or "").lower() == ct:
                return c
        for c in cands:
            if tj and (c.get("target_job") or "").lower() == tj:
                return c
        return cands[0]
    except Exception as e:
        logger.error(f"find_forming_team: {e}")
        return None


# ---- پروفایل عمومی ----

def get_public_profile(user_id: int):
    try:
        row = _conn().execute(
            "SELECT * FROM public_profiles WHERE user_id = ?", (int(user_id),)).fetchone()
        return dict(row) if row is not None else None
    except Exception as e:
        logger.error(f"get_public_profile: {e}")
        return None


def generate_verification_code(user_id: int) -> str:
    """کد یکتای ۶ کاراکتری برای استعلام کارفرما.

    حروف مبهم (O/0/I/1) حذف شده‌اند تا خواندن و تایپ آسان باشد.
    """
    import secrets as _s
    alpha = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
    for _ in range(12):
        code = "".join(_s.choice(alpha) for _ in range(6))
        try:
            with _db._lock:
                with _conn() as c:
                    exists = c.execute(
                        "SELECT 1 FROM public_profiles WHERE verification_code = ?",
                        (code,)).fetchone()
                    if exists:
                        continue
                    c.execute(
                        "INSERT INTO public_profiles (user_id, is_public, custom_bio, "
                        "verification_code, views, updated_at) VALUES (?, 0, '', ?, 0, ?) "
                        "ON CONFLICT(user_id) DO UPDATE SET "
                        "verification_code = excluded.verification_code, "
                        "updated_at = excluded.updated_at",
                        (int(user_id), code, _now()))
            return code
        except Exception:
            continue
    logger.error("generate_verification_code: تولید کد یکتا ناموفق بود")
    return ""


def ensure_public_profile(user_id: int) -> dict:
    p = get_public_profile(user_id)
    if p is None:
        generate_verification_code(user_id)
        p = get_public_profile(user_id) or {}
    elif not (p.get("verification_code") or "").strip():
        generate_verification_code(user_id)
        p = get_public_profile(user_id) or {}
    return p


def set_public_profile(user_id: int, is_public: bool = None,
                       custom_bio: str = None) -> bool:
    cur = ensure_public_profile(user_id)
    try:
        with _db._lock:
            with _conn() as c:
                c.execute(
                    "UPDATE public_profiles SET is_public = ?, custom_bio = ?, "
                    "updated_at = ? WHERE user_id = ?",
                    (int(cur.get("is_public", 0) if is_public is None else bool(is_public)),
                     (cur.get("custom_bio", "") if custom_bio is None
                      else (custom_bio or "")[:600]),
                     _now(), int(user_id)))
        return True
    except Exception as e:
        logger.error(f"set_public_profile: {e}")
        return False


def find_by_verification_code(code: str):
    """یافتن پروفایل عمومی با کد — فقط اگر کاربر آن را عمومی کرده باشد."""
    code = (code or "").strip().upper()
    if len(code) != 6:
        return None
    try:
        row = _conn().execute(
            "SELECT * FROM public_profiles WHERE verification_code = ? AND is_public = 1",
            (code,)).fetchone()
        if row is None:
            return None
        with _db._lock:
            with _conn() as c:
                c.execute(
                    "UPDATE public_profiles SET views = views + 1 WHERE verification_code = ?",
                    (code,))
        return dict(row)
    except Exception as e:
        logger.error(f"find_by_verification_code: {e}")
        return None


# ========================= پروفایل کاربر (فاز ۱) =========================

def init_user_profiles_table(conn=None) -> None:
    """ساخت جدول user_profiles. از db.init_db() صدا زده می‌شود."""
    c = conn if conn is not None else _conn()
    try:
        c.executescript(_PROFILE_SCHEMA)
        c.commit()
    except Exception as e:
        logger.error(f"init_user_profiles_table خطا: {e}", exc_info=True)


def get_user_profile(user_id: int):
    """پروفایل کاربر یا None اگر هنوز ثبت نشده باشد."""
    try:
        row = _conn().execute(
            "SELECT * FROM user_profiles WHERE user_id = ?", (int(user_id),)
        ).fetchone()
        return dict(row) if row is not None else None
    except Exception as e:
        logger.error(f"get_user_profile: {e}")
        return None


def save_user_profile(user_id: int, first_name: str = "", last_name: str = "",
                      age: int = 0, city: str = "") -> bool:
    """درج یا به‌روزرسانی پروفایل (UPSERT)."""
    try:
        with _db._lock:
            with _conn() as c:
                c.execute(
                    "INSERT INTO user_profiles "
                    "(user_id, first_name, last_name, age, city, updated_at) "
                    "VALUES (?, ?, ?, ?, ?, ?) "
                    "ON CONFLICT(user_id) DO UPDATE SET "
                    "first_name = excluded.first_name, last_name = excluded.last_name, "
                    "age = excluded.age, city = excluded.city, "
                    "updated_at = excluded.updated_at",
                    (int(user_id), (first_name or "").strip()[:60],
                     (last_name or "").strip()[:60], int(age or 0),
                     (city or "").strip()[:60], _now()),
                )
        return True
    except Exception as e:
        logger.error(f"save_user_profile: {e}")
        return False


def has_user_profile(user_id: int) -> bool:
    return get_user_profile(user_id) is not None


# ========================= پرداخت و فیش (فاز ۱) =========================

def init_payment_tables(conn=None) -> None:
    """ساخت جدول‌های admin_payment_info و ai_credit_purchases."""
    c = conn if conn is not None else _conn()
    try:
        c.executescript(_PAYMENT_SCHEMA)
        c.execute(
            "INSERT INTO admin_payment_info "
            "(id, card_number, card_holder, bank_name, note, updated_at) "
            "VALUES (1, '', '', '', '', ?) ON CONFLICT DO NOTHING",
            (_now(),),
        )
        c.commit()
    except Exception as e:
        logger.error(f"init_payment_tables خطا: {e}", exc_info=True)


def get_admin_payment_info() -> dict:
    """اطلاعات کارت ادمین (همیشه یک دیکشنری برمی‌گرداند)."""
    empty = {"card_number": "", "card_holder": "", "bank_name": "", "note": ""}
    try:
        row = _conn().execute(
            "SELECT * FROM admin_payment_info WHERE id = 1"
        ).fetchone()
        return dict(row) if row is not None else empty
    except Exception as e:
        logger.error(f"get_admin_payment_info: {e}")
        return empty


def save_admin_payment_info(card_number: str = None, card_holder: str = None,
                            bank_name: str = None, note: str = None) -> bool:
    """به‌روزرسانی جزئیِ اطلاعات کارت — فیلدهای None دست‌نخورده می‌مانند."""
    cur = get_admin_payment_info()
    try:
        with _db._lock:
            with _conn() as c:
                c.execute(
                    "INSERT INTO admin_payment_info "
                    "(id, card_number, card_holder, bank_name, note, updated_at) "
                    "VALUES (1, ?, ?, ?, ?, ?) "
                    "ON CONFLICT(id) DO UPDATE SET "
                    "card_number = excluded.card_number, card_holder = excluded.card_holder, "
                    "bank_name = excluded.bank_name, note = excluded.note, "
                    "updated_at = excluded.updated_at",
                    (card_number if card_number is not None else cur.get("card_number", ""),
                     card_holder if card_holder is not None else cur.get("card_holder", ""),
                     bank_name if bank_name is not None else cur.get("bank_name", ""),
                     note if note is not None else cur.get("note", ""),
                     _now()),
                )
        return True
    except Exception as e:
        logger.error(f"save_admin_payment_info: {e}")
        return False


def payment_info_ready() -> bool:
    """آیا ادمین شماره کارت را ثبت کرده است؟"""
    return bool((get_admin_payment_info().get("card_number") or "").strip())


def save_credit_purchase(user_id: int, user_name: str, package_id: int,
                         amount: int, price: int, fiche_file_id: str = "",
                         fiche_text: str = "", platform: str = "bale",
                         chat_id: str = "") -> int:
    """ثبت فیش جدید با وضعیت pending. خروجی: id یا 0."""
    try:
        with _db._lock:
            with _conn() as c:
                cur = c.execute(
                    "INSERT INTO ai_credit_purchases "
                    "(user_id, user_name, package_id, amount, price, fiche_file_id, "
                    " fiche_text, platform, chat_id, status, admin_note, created_at, reviewed_at) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'pending', '', ?, '')",
                    (int(user_id), (user_name or "")[:80], int(package_id or 0),
                     int(amount or 0), int(price or 0), fiche_file_id or "",
                     (fiche_text or "")[:500], platform or "bale",
                     str(chat_id or ""), _now()),
                )
                return int(cur.lastrowid or 0)
    except Exception as e:
        logger.error(f"save_credit_purchase: {e}", exc_info=True)
        return 0


def get_purchase(purchase_id: int):
    try:
        row = _conn().execute(
            "SELECT * FROM ai_credit_purchases WHERE id = ?", (int(purchase_id),)
        ).fetchone()
        return dict(row) if row is not None else None
    except Exception as e:
        logger.error(f"get_purchase: {e}")
        return None


def get_pending_purchases(limit: int = 20) -> list:
    try:
        rows = _conn().execute(
            "SELECT * FROM ai_credit_purchases WHERE status = 'pending' "
            "ORDER BY id ASC LIMIT ?", (int(limit),)
        ).fetchall()
        return [dict(r) for r in rows]
    except Exception as e:
        logger.error(f"get_pending_purchases: {e}")
        return []


def user_pending_purchases(user_id: int) -> int:
    """تعداد فیش‌های در انتظار تأیید یک کاربر."""
    try:
        row = _conn().execute(
            "SELECT COUNT(*) FROM ai_credit_purchases "
            "WHERE user_id = ? AND status = 'pending'", (int(user_id),)
        ).fetchone()
        return int(row[0] or 0)
    except Exception as e:
        logger.error(f"user_pending_purchases: {e}")
        return 0


def _set_purchase_status(purchase_id: int, status: str, note: str = "") -> bool:
    """تغییر وضعیت فیش — فقط اگر هنوز pending باشد (ضد تأیید دوباره)."""
    try:
        with _db._lock:
            with _conn() as c:
                cur = c.execute(
                    "UPDATE ai_credit_purchases SET status = ?, admin_note = ?, "
                    "reviewed_at = ? WHERE id = ? AND status = 'pending'",
                    (status, (note or "")[:200], _now(), int(purchase_id)),
                )
                return cur.rowcount > 0
    except Exception as e:
        logger.error(f"_set_purchase_status: {e}")
        return False


def approve_purchase(purchase_id: int, note: str = "") -> bool:
    """علامت‌زدن فیش به‌عنوان تأییدشده.

    ⚠️ فقط وضعیت را عوض می‌کند؛ افزودن اعتبار در ai_admin انجام می‌شود
    (تا این فایل به core وابسته نشود). خروجی False یعنی قبلاً بررسی شده.
    """
    return _set_purchase_status(purchase_id, "approved", note)


def reject_purchase(purchase_id: int, note: str = "") -> bool:
    return _set_purchase_status(purchase_id, "rejected", note)


def purchase_stats() -> dict:
    out = {"pending": 0, "approved": 0, "rejected": 0, "total_credits": 0}
    try:
        for r in _conn().execute(
            "SELECT status, COUNT(*) FROM ai_credit_purchases GROUP BY status"
        ):
            if r[0] in out:
                out[r[0]] = int(r[1] or 0)
        row = _conn().execute(
            "SELECT COALESCE(SUM(amount),0) FROM ai_credit_purchases WHERE status='approved'"
        ).fetchone()
        out["total_credits"] = int(row[0] or 0)
    except Exception as e:
        logger.error(f"purchase_stats: {e}")
    return out


# ========================= تنظیمات =========================

def get_ai_setting(key: str, default: str = "") -> str:
    try:
        row = _conn().execute(
            "SELECT setting_value FROM ai_settings WHERE setting_key = ?", (key,)
        ).fetchone()
        if row is None:
            return DEFAULT_SETTINGS.get(key, default)
        return row[0]
    except Exception as e:
        logger.error(f"get_ai_setting({key}): {e}")
        return DEFAULT_SETTINGS.get(key, default)


def get_ai_setting_int(key: str, default: int = 0) -> int:
    try:
        return int(float(get_ai_setting(key, str(default))))
    except Exception:
        return default


def save_ai_setting(key: str, value) -> bool:
    try:
        with _db._lock:
            with _conn() as c:
                c.execute(
                    "INSERT INTO ai_settings (setting_key, setting_value, updated_at) "
                    "VALUES (?, ?, ?) "
                    "ON CONFLICT(setting_key) DO UPDATE SET "
                    "setting_value = excluded.setting_value, updated_at = excluded.updated_at",
                    (key, str(value), _now()),
                )
        return True
    except Exception as e:
        logger.error(f"save_ai_setting({key}): {e}")
        return False


def all_ai_settings() -> dict:
    out = dict(DEFAULT_SETTINGS)
    try:
        for row in _conn().execute("SELECT setting_key, setting_value FROM ai_settings"):
            out[row[0]] = row[1]
    except Exception as e:
        logger.error(f"all_ai_settings: {e}")
    return out


# ========================= مسیر شغلی =========================

def save_career_path(user_id: int, target_job: str, interview_data: dict) -> int:
    """ساخت مسیر جدید. مسیرهای فعال قبلی بایگانی می‌شوند. خروجی: path_id"""
    try:
        with _db._lock:
            with _conn() as c:
                c.execute(
                    "UPDATE career_paths SET status = 'archived' "
                    "WHERE user_id = ? AND status = 'active'",
                    (int(user_id),),
                )
                cur = c.execute(
                    "INSERT INTO career_paths "
                    "(user_id, target_job, interview_data, status, created_at, completed_at) "
                    "VALUES (?, ?, ?, 'active', ?, '')",
                    (int(user_id), target_job or "", jdumps(interview_data or {}), _now()),
                )
                return int(cur.lastrowid or 0)
    except Exception as e:
        logger.error(f"save_career_path: {e}", exc_info=True)
        return 0


def _path_row(row):
    """ردیف career_paths → دیکشنری با فیلدهای JSON پارس‌شده."""
    d = dict(row)
    d["interview_data"] = jloads(d.get("interview_data"), {})
    # ستون‌های معماری چندعاملی (روی دیتابیس قدیمی ممکن است نباشند)
    d["interview_data_json"] = jloads(d.get("interview_data_json"), {})
    d["roadmap_json"] = jloads(d.get("roadmap_json"), {})
    return d


def get_active_path(user_id: int):
    """مسیر فعال کاربر یا None."""
    try:
        row = _conn().execute(
            "SELECT * FROM career_paths WHERE user_id = ? AND status = 'active' "
            "ORDER BY id DESC LIMIT 1",
            (int(user_id),),
        ).fetchone()
        return _path_row(row) if row is not None else None
    except Exception as e:
        logger.error(f"get_active_path: {e}")
        return None


def get_path(path_id: int):
    try:
        row = _conn().execute(
            "SELECT * FROM career_paths WHERE id = ?", (int(path_id),)
        ).fetchone()
        return _path_row(row) if row is not None else None
    except Exception as e:
        logger.error(f"get_path: {e}")
        return None


def save_interview_json(path_id: int, data: dict) -> bool:
    """ذخیرهٔ خروجی نهایی ایجنت ۱ در career_paths.interview_data_json."""
    try:
        with _db._lock:
            with _conn() as c:
                c.execute(
                    "UPDATE career_paths SET interview_data_json = ? WHERE id = ?",
                    (jdumps(data or {}), int(path_id)),
                )
        return True
    except Exception as e:
        logger.error(f"save_interview_json: {e}")
        return False


def save_roadmap_json(path_id: int, data: dict) -> bool:
    """ذخیرهٔ خروجی ایجنت ۲ در career_paths.roadmap_json."""
    try:
        with _db._lock:
            with _conn() as c:
                c.execute(
                    "UPDATE career_paths SET roadmap_json = ? WHERE id = ?",
                    (jdumps(data or {}), int(path_id)),
                )
        return True
    except Exception as e:
        logger.error(f"save_roadmap_json: {e}")
        return False


def list_user_paths(user_id: int, limit: int = 10) -> list:
    try:
        rows = _conn().execute(
            "SELECT * FROM career_paths WHERE user_id = ? ORDER BY id DESC LIMIT ?",
            (int(user_id), int(limit)),
        ).fetchall()
        return [dict(r) for r in rows]
    except Exception as e:
        logger.error(f"list_user_paths: {e}")
        return []


def complete_path(path_id: int) -> bool:
    try:
        with _db._lock:
            with _conn() as c:
                c.execute(
                    "UPDATE career_paths SET status = 'completed', completed_at = ? WHERE id = ?",
                    (_now(), int(path_id)),
                )
        return True
    except Exception as e:
        logger.error(f"complete_path: {e}")
        return False


def set_path_status(path_id: int, user_id: int, status: str) -> bool:
    """تغییر وضعیت مسیر — فقط توسط صاحب آن (🔒 ضد IDOR).

    اگر مسیری active شود، بقیهٔ مسیرهای فعالِ همان کاربر بایگانی می‌شوند
    تا همیشه فقط یک مسیر فعال بماند (سازگار با get_active_path).
    """
    if status not in ("active", "archived", "completed"):
        return False
    p = get_path(path_id)
    if not p or int(p.get("user_id", 0)) != int(user_id):
        return False
    try:
        with _db._lock:
            with _conn() as c:
                if status == "active":
                    c.execute(
                        "UPDATE career_paths SET status = 'archived' "
                        "WHERE user_id = ? AND status = 'active' AND id != ?",
                        (int(user_id), int(path_id)),
                    )
                c.execute("UPDATE career_paths SET status = ? WHERE id = ?",
                          (status, int(path_id)))
        return True
    except Exception as e:
        logger.error(f"set_path_status: {e}")
        return False


def delete_path(path_id: int, user_id: int) -> bool:
    """حذف کامل مسیر و گام‌هایش — فقط توسط صاحب آن (🔒 ضد IDOR)."""
    p = get_path(path_id)
    if not p or int(p.get("user_id", 0)) != int(user_id):
        return False
    try:
        with _db._lock:
            with _conn() as c:
                c.execute("DELETE FROM path_steps WHERE path_id = ?", (int(path_id),))
                c.execute("DELETE FROM career_paths WHERE id = ?", (int(path_id),))
        return True
    except Exception as e:
        logger.error(f"delete_path: {e}")
        return False


# ========================= گام‌های مسیر =========================

def save_path_step(path_id: int, step_number: int, step_type: str,
                   title: str, content: dict, status: str = "locked") -> int:
    payload = jdumps(content or {})
    try:
        with _db._lock:
            with _conn() as c:
                cur = c.execute(
                    "INSERT INTO path_steps "
                    "(path_id, step_number, step_type, title, content, status, "
                    " ai_feedback, completed_at, content_json) "
                    "VALUES (?, ?, ?, ?, ?, ?, '{}', '', ?)",
                    (int(path_id), int(step_number), step_type or "resource",
                     title or "", payload, status, payload),
                )
                return int(cur.lastrowid or 0)
    except Exception as e:
        logger.error(f"save_path_step: {e}", exc_info=True)
        return 0


def _step_row(row):
    """ردیف path_steps → دیکشنری با فیلدهای JSON پارس‌شده.

    content و content_json هم‌معنا هستند: content_json ستون رسمی معماری
    چندعاملی است و content برای سازگاری با کد موجود نگه داشته می‌شود.
    اگر یکی خالی و دیگری پر بود، پرشده ملاک است.
    """
    d = dict(row)
    d["ai_feedback"] = jloads(d.get("ai_feedback"), {})
    content = jloads(d.get("content"), {})
    cjson = jloads(d.get("content_json"), {})
    merged = cjson or content or {}
    d["content"] = merged
    d["content_json"] = merged
    return d


def get_path_steps(path_id: int) -> list:
    try:
        rows = _conn().execute(
            "SELECT * FROM path_steps WHERE path_id = ? ORDER BY step_number ASC",
            (int(path_id),),
        ).fetchall()
        return [_step_row(r) for r in rows]
    except Exception as e:
        logger.error(f"get_path_steps: {e}")
        return []


def get_step(step_id: int):
    try:
        row = _conn().execute(
            "SELECT * FROM path_steps WHERE id = ?", (int(step_id),)
        ).fetchone()
        return _step_row(row) if row is not None else None
    except Exception as e:
        logger.error(f"get_step: {e}")
        return None


def update_step_content(step_id: int, content: dict) -> bool:
    """ذخیرهٔ محتوای تولیدشدهٔ یک گام (Lazy Loading).

    هر دو ستون content و content_json با هم نوشته می‌شوند تا کد قدیمی و
    معماری جدید یک دادهٔ واحد ببینند. پس از این، دفعهٔ بعد محتوا از
    دیتابیس خوانده می‌شود و AI دوباره صدا زده نمی‌شود.
    """
    payload = jdumps(content or {})
    try:
        with _db._lock:
            with _conn() as c:
                c.execute(
                    "UPDATE path_steps SET content = ?, content_json = ? "
                    "WHERE id = ?",
                    (payload, payload, int(step_id)),
                )
        return True
    except Exception as e:
        logger.error(f"update_step_content: {e}")
        return False


def update_step_ai_feedback(step_id: int, feedback: dict) -> bool:
    """ذخیرهٔ بازخورد/نمرهٔ یک گام بدون تغییر وضعیت آن."""
    try:
        with _db._lock:
            with _conn() as c:
                c.execute("UPDATE path_steps SET ai_feedback = ? WHERE id = ?",
                          (jdumps(feedback or {}), int(step_id)))
        return True
    except Exception as e:
        logger.error(f"update_step_ai_feedback: {e}")
        return False


def update_interview_data(path_id: int, patch: dict) -> bool:
    """به‌روزرسانی جزئیِ interview_data (شامل persona و حافظهٔ فردی).

    کلیدهای موجود حفظ می‌شوند و فقط کلیدهای داده‌شده بازنویسی می‌گردند.
    """
    p = get_path(path_id)
    if not p:
        return False
    data = p.get("interview_data") or {}
    if not isinstance(data, dict):
        data = {}
    data.update(patch or {})
    try:
        with _db._lock:
            with _conn() as c:
                c.execute("UPDATE career_paths SET interview_data = ? WHERE id = ?",
                          (jdumps(data), int(path_id)))
        return True
    except Exception as e:
        logger.error(f"update_interview_data: {e}")
        return False


def get_owned_step(step_id: int, user_id: int):
    """گام — فقط اگر متعلق به همین کاربر باشد (ضد IDOR).

    شناسهٔ گام عددیِ قابل‌حدس است؛ بدون این بررسی، کاربر می‌توانست گام
    خصوصی دیگران را ببیند یا با پاسخ‌دادن، آن را تکمیل کند و XP بگیرد.
    خروجی None یعنی «پیدا نشد یا مال شما نیست».
    """
    step = get_step(step_id)
    if not step:
        return None
    path = get_path(step.get("path_id"))
    if not path or int(path.get("user_id", 0)) != int(user_id):
        return None
    return step


def user_in_team(team_id: int, user_id: int) -> bool:
    """آیا کاربر عضو این تیم است؟ (ضد نشت اطلاعات تیم‌های دیگر)"""
    try:
        row = _conn().execute(
            "SELECT 1 FROM team_members WHERE team_id = ? AND user_id = ?",
            (int(team_id), int(user_id)),
        ).fetchone()
        return row is not None
    except Exception as e:
        logger.error(f"user_in_team: {e}")
        return False


def update_step_status(step_id: int, status: str, ai_feedback: dict = None) -> bool:
    """به‌روزرسانی وضعیت گام و در صورت تکمیل، فعال‌کردن گام بعدی."""
    try:
        with _db._lock:
            with _conn() as c:
                done = _now() if status == "completed" else ""
                if ai_feedback is None:
                    c.execute(
                        "UPDATE path_steps SET status = ?, completed_at = ? WHERE id = ?",
                        (status, done, int(step_id)),
                    )
                else:
                    c.execute(
                        "UPDATE path_steps SET status = ?, ai_feedback = ?, completed_at = ? "
                        "WHERE id = ?",
                        (status, jdumps(ai_feedback), done, int(step_id)),
                    )

                if status == "completed":
                    row = c.execute(
                        "SELECT path_id, step_number FROM path_steps WHERE id = ?",
                        (int(step_id),),
                    ).fetchone()
                    if row is not None:
                        c.execute(
                            "UPDATE path_steps SET status = 'active' "
                            "WHERE path_id = ? AND step_number = ? AND status = 'locked'",
                            (row[0], int(row[1]) + 1),
                        )
        return True
    except Exception as e:
        logger.error(f"update_step_status: {e}", exc_info=True)
        return False


def path_progress(path_id: int) -> tuple:
    """(تکمیل‌شده، کل) برای نمایش درصد پیشرفت."""
    try:
        row = _conn().execute(
            "SELECT COUNT(*), SUM(CASE WHEN status='completed' THEN 1 ELSE 0 END) "
            "FROM path_steps WHERE path_id = ?",
            (int(path_id),),
        ).fetchone()
        total = int(row[0] or 0)
        done = int(row[1] or 0)
        return done, total
    except Exception as e:
        logger.error(f"path_progress: {e}")
        return 0, 0


# ========================= ترندهای بازار =========================

def save_market_trend(skill_name: str, demand_count: int,
                      source: str = "", reason: str = "") -> bool:
    try:
        with _db._lock:
            with _conn() as c:
                c.execute(
                    "INSERT INTO market_trends (skill_name, demand_count, source, reason, updated_at) "
                    "VALUES (?, ?, ?, ?, ?) "
                    "ON CONFLICT(skill_name) DO UPDATE SET "
                    "demand_count = excluded.demand_count, source = excluded.source, "
                    "reason = excluded.reason, updated_at = excluded.updated_at",
                    (skill_name.strip(), int(demand_count or 0), source or "", reason or "", _now()),
                )
        # فاز ۲ — ثبت نقطه در تاریخچه برای محاسبهٔ رشد
        record_trend_snapshot(skill_name, demand_count)
        return True
    except Exception as e:
        logger.error(f"save_market_trend: {e}")
        return False


def get_trending_skills(limit: int = 5) -> list:
    try:
        rows = _conn().execute(
            "SELECT * FROM market_trends ORDER BY demand_count DESC, skill_name ASC LIMIT ?",
            (int(limit),),
        ).fetchall()
        return [dict(r) for r in rows]
    except Exception as e:
        logger.error(f"get_trending_skills: {e}")
        return []


def delete_market_trend(skill_name: str) -> bool:
    try:
        with _db._lock:
            with _conn() as c:
                c.execute("DELETE FROM market_trends WHERE skill_name = ?", (skill_name,))
        return True
    except Exception as e:
        logger.error(f"delete_market_trend: {e}")
        return False


def clear_market_trends() -> bool:
    try:
        with _db._lock:
            with _conn() as c:
                c.execute("DELETE FROM market_trends")
        return True
    except Exception as e:
        logger.error(f"clear_market_trends: {e}")
        return False


# ========================= بسته‌های اعتبار =========================

def list_credit_packages(only_active: bool = False) -> list:
    """فهرست بسته‌ها — مرتب بر اساس مقدار اعتبار."""
    try:
        sql = "SELECT * FROM ai_credit_packages"
        if only_active:
            sql += " WHERE is_active = 1"
        sql += " ORDER BY amount ASC"
        return [dict(r) for r in _conn().execute(sql).fetchall()]
    except Exception as e:
        logger.error(f"list_credit_packages: {e}")
        return []


def get_credit_package(pkg_id: int):
    try:
        row = _conn().execute(
            "SELECT * FROM ai_credit_packages WHERE id = ?", (int(pkg_id),)
        ).fetchone()
        return dict(row) if row is not None else None
    except Exception as e:
        logger.error(f"get_credit_package: {e}")
        return None


def add_credit_package(amount: int, price: int) -> int:
    """افزودن بستهٔ جدید. خروجی: id یا 0 در صورت خطا."""
    try:
        amount, price = int(amount), int(price)
        if amount <= 0 or price < 0:
            return 0
        with _db._lock:
            with _conn() as c:
                cur = c.execute(
                    "INSERT INTO ai_credit_packages (amount, price, is_active, created_at) "
                    "VALUES (?, ?, 1, ?)",
                    (amount, price, _now()),
                )
                return int(cur.lastrowid or 0)
    except Exception as e:
        logger.error(f"add_credit_package: {e}")
        return 0


def toggle_credit_package(pkg_id: int) -> bool:
    """فعال/غیرفعال کردن یک بسته."""
    try:
        with _db._lock:
            with _conn() as c:
                c.execute(
                    "UPDATE ai_credit_packages "
                    "SET is_active = CASE is_active WHEN 1 THEN 0 ELSE 1 END WHERE id = ?",
                    (int(pkg_id),),
                )
        return True
    except Exception as e:
        logger.error(f"toggle_credit_package: {e}")
        return False


def delete_credit_package(pkg_id: int) -> bool:
    try:
        with _db._lock:
            with _conn() as c:
                c.execute("DELETE FROM ai_credit_packages WHERE id = ?", (int(pkg_id),))
        return True
    except Exception as e:
        logger.error(f"delete_credit_package: {e}")
        return False


# ========================= لاگ مصرف =========================

def log_ai_usage(user_id: int, action: str, cost: int = 0, model: str = "") -> None:
    """ثبت مصرف + هرس خودکار روی ۵۰۰ رکورد آخر (جلوگیری از رشد بی‌نهایت)."""
    try:
        with _db._lock:
            with _conn() as c:
                c.execute(
                    "INSERT INTO ai_usage_logs "
                    "(user_id, action_type, cost_credits, ai_model_used, created_at) "
                    "VALUES (?, ?, ?, ?, ?)",
                    (int(user_id), action or "", int(cost or 0), model or "", _now()),
                )
                c.execute(
                    "DELETE FROM ai_usage_logs WHERE id NOT IN "
                    "(SELECT id FROM ai_usage_logs ORDER BY id DESC LIMIT 500)"
                )
    except Exception as e:
        logger.error(f"log_ai_usage: {e}")


def user_usage_count(user_id: int) -> int:
    """تعداد تعامل‌های کاربر — مبنای سهمیهٔ رایگان."""
    try:
        row = _conn().execute(
            "SELECT COUNT(*) FROM ai_usage_logs WHERE user_id = ?", (int(user_id),)
        ).fetchone()
        return int(row[0] or 0)
    except Exception as e:
        logger.error(f"user_usage_count: {e}")
        return 0


def usage_summary(limit: int = 10) -> dict:
    """خلاصهٔ مصرف برای پنل ادمین."""
    out = {"total_calls": 0, "total_credits": 0, "top_users": [], "by_action": []}
    try:
        c = _conn()
        row = c.execute(
            "SELECT COUNT(*), COALESCE(SUM(cost_credits), 0) FROM ai_usage_logs"
        ).fetchone()
        out["total_calls"] = int(row[0] or 0)
        out["total_credits"] = int(row[1] or 0)
        out["top_users"] = [
            {"user_id": r[0], "calls": r[1], "credits": r[2]}
            for r in c.execute(
                "SELECT user_id, COUNT(*), COALESCE(SUM(cost_credits),0) FROM ai_usage_logs "
                "GROUP BY user_id ORDER BY COUNT(*) DESC LIMIT ?",
                (int(limit),),
            ).fetchall()
        ]
        out["by_action"] = [
            {"action": r[0], "calls": r[1], "credits": r[2]}
            for r in c.execute(
                "SELECT action_type, COUNT(*), COALESCE(SUM(cost_credits),0) FROM ai_usage_logs "
                "GROUP BY action_type ORDER BY COUNT(*) DESC"
            ).fetchall()
        ]
    except Exception as e:
        logger.error(f"usage_summary: {e}")
    return out


def module_stats() -> dict:
    """آمار کلی ماژول برای پنل ادمین."""
    out = {"paths_active": 0, "paths_total": 0, "steps_done": 0, "users": 0, "trends": 0}
    try:
        c = _conn()
        out["paths_total"] = int(c.execute("SELECT COUNT(*) FROM career_paths").fetchone()[0] or 0)
        out["paths_active"] = int(c.execute(
            "SELECT COUNT(*) FROM career_paths WHERE status='active'").fetchone()[0] or 0)
        out["steps_done"] = int(c.execute(
            "SELECT COUNT(*) FROM path_steps WHERE status='completed'").fetchone()[0] or 0)
        out["users"] = int(c.execute(
            "SELECT COUNT(DISTINCT user_id) FROM career_paths").fetchone()[0] or 0)
        out["trends"] = int(c.execute("SELECT COUNT(*) FROM market_trends").fetchone()[0] or 0)
    except Exception as e:
        logger.error(f"module_stats: {e}")
    return out
