# -*- coding: utf-8 -*-
"""
giso/ai_brain.py — مغز مستقل AI گیسو با پشتیبانی از پروکسی + تحلیل تصویر.
"""
import asyncio
import base64
import json
import json as _json
import logging
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger(__name__)

try:
    import httpx as _httpx
except ImportError:
    _httpx = None


_GISO_DB_PATH = Path(__file__).resolve().parent / "data" / "giso.db"
_lock = threading.Lock()


def get_conn() -> sqlite3.Connection:
    from giso.base import get_giso_db_conn
    return get_giso_db_conn()


AI_SCHEMA = """
CREATE TABLE IF NOT EXISTS giso_ai_providers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT UNIQUE NOT NULL,
    kind TEXT NOT NULL DEFAULT 'openai',
    enabled INTEGER NOT NULL DEFAULT 1,
    api_key TEXT NOT NULL DEFAULT '',
    base_url TEXT NOT NULL DEFAULT '',
    api_root TEXT NOT NULL DEFAULT '',
    timeout INTEGER NOT NULL DEFAULT 20,
    headers_json TEXT NOT NULL DEFAULT '{}',
    fallback_json TEXT NOT NULL DEFAULT '[]',
    models_json TEXT NOT NULL DEFAULT '[]',
    selected_model TEXT NOT NULL DEFAULT '',
    is_iranian INTEGER NOT NULL DEFAULT 0,
    use_proxy INTEGER NOT NULL DEFAULT 0,
    last_status TEXT NOT NULL DEFAULT '',
    last_error TEXT NOT NULL DEFAULT '',
    last_checked_at TEXT NOT NULL DEFAULT ''
);
CREATE INDEX IF NOT EXISTS idx_giso_ai_providers_name ON giso_ai_providers(name);

CREATE TABLE IF NOT EXISTS giso_ai_checks_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    provider_name TEXT NOT NULL,
    status TEXT NOT NULL,
    error_text TEXT NOT NULL DEFAULT '',
    checked_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_giso_ai_checks_log_provider ON giso_ai_checks_log(provider_name);
"""


def init_ai_tables(conn=None):
    c = conn if conn is not None else get_conn()
    try:
        c.executescript(AI_SCHEMA)
        try:
            c.execute("ALTER TABLE giso_ai_providers ADD COLUMN use_proxy INTEGER DEFAULT 0")
        except Exception:
            pass
        # ستون‌های جدید فاز ۱ بازنویسی سیستم AI (هر ستون جدا با تحمل خطا)
        for col_name, col_type in (
            ("proxy_url", "TEXT"),
            ("proxy_type", "TEXT"),
            ("vision_models_json", "TEXT"),
            ("text_models_json", "TEXT"),
            ("models_last_updated", "TEXT"),
            ("models_source", "TEXT"),
            # گزارش آخرین کشف هوشمند مدل‌ها (دکمهٔ بروزرسانی همه) — مأموریت 11
            ("discovery_report", "TEXT"),
        ):
            try:
                c.execute(f"ALTER TABLE giso_ai_providers ADD COLUMN {col_name} {col_type}")
            except Exception:
                pass  # ستون از قبل وجود دارد
        # فاز ۳: جدول سلامت مشترک پروایدرها (هر سه موتور از آن می‌خوانند)
        try:
            c.execute("""
                CREATE TABLE IF NOT EXISTS giso_ai_health (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    provider TEXT NOT NULL,
                    model TEXT DEFAULT '',
                    last_result TEXT,
                    last_error TEXT,
                    fail_count INTEGER DEFAULT 0,
                    cooldown_until TEXT,
                    updated_at TEXT,
                    UNIQUE(provider, model)
                )
            """)
            c.execute("""
                CREATE INDEX IF NOT EXISTS idx_ai_health_cooldown
                ON giso_ai_health(cooldown_until)
            """)
        except Exception:
            pass
        c.commit()
    except Exception as e:
        logger.error(f"giso init_ai_tables: {e}")


# پیش‌فرض اتصال مستقیم Gemini (OpenAI-compat) از ایران — ورکر کلودفلر گیسو
GEMINI_DEFAULT_BASE_URL = "https://sadeghiai.uname1370.workers.dev/v1beta/openai"


def _col(row, name, default=""):
    """دسترسی امن به ستون ردیف (تحمل نبود ستون در دیتابیس‌های قدیمی)."""
    try:
        val = row[name]
        return val if val is not None else default
    except Exception:
        return default


def _get_proxy_for_provider(row, sensitive=False):
    try:
        # فاز ۲: اولویت اول = پروکسی اختصاصی خود پروایدر (ستون جدید)
        custom = str(_col(row, "proxy_url", "") or "").strip()
        if custom and (custom.startswith("socks5") or custom.startswith("http")):
            return custom
        name = str(row["name"] or "").strip().lower()
        # Gemini با Base URL (ورکر/سفارشی) مثل AvalAI/Groq مستقیم می‌رود؛ SOCKS بایپاس می‌شود.
        if name == "gemini" and _effective_base_url(name, row["base_url"]):
            return None
        if not row["use_proxy"]:
            return None
        from giso.gemini_proxy_manager import get_active_proxy
        return get_active_proxy(sensitive=sensitive)
    except Exception as e:
        logger.warning(f"giso _get_proxy_for_provider: {e}")
        return None


def _make_client(timeout, proxy=None):
    if proxy:
        try:
            return _httpx.AsyncClient(proxy=proxy, timeout=timeout)
        except TypeError:
            return _httpx.AsyncClient(proxies=proxy, timeout=timeout)
    return _httpx.AsyncClient(timeout=timeout)


def _record_gemini_proxy_result(provider_name, proxy, ok, status=0):
    if str(provider_name).lower() != "gemini" or not proxy:
        return
    try:
        from giso.gemini_proxy_manager import record_runtime_result
        record_runtime_result(proxy, ok, status)
    except Exception:
        pass


def _ai_now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")


def get_ai_provider(name):
    conn = get_conn()
    try:
        return conn.execute("SELECT * FROM giso_ai_providers WHERE name=?", (name,)).fetchone()
    except Exception:
        return None
    finally:
        conn.close()


def list_ai_providers(only_enabled=False):
    conn = get_conn()
    sql = "SELECT * FROM giso_ai_providers"
    if only_enabled:
        sql += " WHERE enabled=1"
    sql += " ORDER BY id"
    try:
        return conn.execute(sql).fetchall()
    except Exception:
        return []
    finally:
        conn.close()


def default_models_for_provider(name):
    """مدل‌های رایگان پیش‌فرض (متن+بینایی) بر اساس رجیستری؛ برای پرکردن خودکار پروایدر جدید."""
    from giso.ai_models_registry import normalize_provider_name as _normalize_pname
    reg = PROVIDERS_REGISTRY.get(_normalize_pname(name), {}) or {}
    vision = reg.get("vision_preferred", [])
    text = reg.get("text_preferred", [])
    models = []
    for m in list(vision) + list(text):
        if m not in models:
            models.append(m)
    return models, (vision[0] if vision else (text[0] if text else ""))


def add_ai_provider(name, kind="openai", api_key="", base_url="", api_root="",
                    timeout=20, headers_json="{}", fallback_json="[]",
                    models_json="[]", selected_model="",
                    is_iranian=False, enabled=True, use_proxy=False, replace=False,
                    vision_models_json="", text_models_json="", models_source="",
                    proxy_url="", proxy_type=""):
    # نرمال‌سازی نام: «hugging face» ← «huggingface»، «cloudflare workers ai» ← «cloudflare»
    from giso.ai_models_registry import normalize_provider_name as _normalize_pname
    name = _normalize_pname(name)
    if str(name or "").lower() == "gemini":
        use_proxy = False
        base_url = _normalize_gemini_base_url(base_url)
        if not api_root or _is_google_gemini_host(api_root):
            api_root = base_url
    conn = get_conn()
    # پیش‌فرض رایگان: اگر ادمین مدلی نداد، رجیستری پر می‌کند (مورد ۸ دستور start/1.md)
    reg_models, reg_selected = default_models_for_provider(name)
    if not str(selected_model or "").strip():
        selected_model = reg_selected
    try:
        if not json.loads(models_json or "[]"):
            models_json = json.dumps(reg_models, ensure_ascii=False)
    except Exception:
        pass
    try:
        if not json.loads(fallback_json or "[]"):
            fallback_json = json.dumps(reg_models, ensure_ascii=False)
    except Exception:
        pass
    _cols_vals = """INSERT INTO giso_ai_providers
                (name, kind, enabled, api_key, base_url, api_root,
                 timeout, headers_json, fallback_json, models_json, selected_model,
                 is_iranian, use_proxy,
                 proxy_url, proxy_type, vision_models_json, text_models_json, models_source)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)"""
    # ستون‌های جدید فاز ۲: با COALESCE مقدار خالی، دادهٔ کشف‌شدهٔ قبلی در جایگزینی پاک نمی‌شود.
    _upsert = """ ON CONFLICT(name) DO UPDATE SET kind=excluded.kind, enabled=excluded.enabled,
                api_key=excluded.api_key, base_url=excluded.base_url, api_root=excluded.api_root,
                timeout=excluded.timeout, headers_json=excluded.headers_json,
                fallback_json=excluded.fallback_json, models_json=excluded.models_json,
                selected_model=excluded.selected_model, is_iranian=excluded.is_iranian,
                use_proxy=excluded.use_proxy,
                proxy_url=COALESCE(NULLIF(excluded.proxy_url, ''), giso_ai_providers.proxy_url),
                proxy_type=COALESCE(NULLIF(excluded.proxy_type, ''), giso_ai_providers.proxy_type),
                vision_models_json=COALESCE(NULLIF(excluded.vision_models_json, ''), giso_ai_providers.vision_models_json),
                text_models_json=COALESCE(NULLIF(excluded.text_models_json, ''), giso_ai_providers.text_models_json),
                models_source=COALESCE(NULLIF(excluded.models_source, ''), giso_ai_providers.models_source)"""
    sql = _cols_vals + (_upsert if replace else " ON CONFLICT DO NOTHING")
    try:
        with _lock, conn:
            cur = conn.execute(sql,
                (name, kind, 1 if enabled else 0, api_key, base_url, api_root,
                 int(timeout), headers_json, fallback_json, models_json, selected_model,
                 1 if is_iranian else 0, 1 if use_proxy else 0,
                 proxy_url or "", proxy_type or "",
                 vision_models_json or "", text_models_json or "", models_source or "")
            )
        return cur.rowcount > 0
    except Exception as e:
        logger.error(f"add_ai_provider: {e}")
        return False


def delete_ai_provider(name):
    conn = get_conn()
    try:
        with _lock, conn:
            cur = conn.execute("DELETE FROM giso_ai_providers WHERE name=?", (name,))
        return cur.rowcount > 0
    except Exception:
        return False


def toggle_ai_provider(name):
    conn = get_conn()
    try:
        row = conn.execute("SELECT enabled FROM giso_ai_providers WHERE name=?", (name,)).fetchone()
        if row is None:
            return None
        new_val = 0 if row["enabled"] else 1
        with _lock, conn:
            conn.execute("UPDATE giso_ai_providers SET enabled=? WHERE name=?", (new_val, name))
        return bool(new_val)
    except Exception:
        return None


def toggle_use_proxy(name):
    conn = get_conn()
    try:
        row = conn.execute("SELECT use_proxy FROM giso_ai_providers WHERE name=?", (name,)).fetchone()
        if row is None:
            return None
        # Gemini از ورکر کلودفلر می‌رود؛ SOCKS روی googleapis از ایران کار نمی‌کند.
        if str(name or "").lower() == "gemini":
            with _lock, conn:
                conn.execute("UPDATE giso_ai_providers SET use_proxy=0 WHERE name=?", (name,))
            return False
        new_val = 0 if row["use_proxy"] else 1
        with _lock, conn:
            conn.execute("UPDATE giso_ai_providers SET use_proxy=? WHERE name=?", (new_val, name))
        return bool(new_val)
    except Exception:
        return None


def _gemini_env_root() -> str:
    """ریشهٔ آدرس Gemini: اول env (GEMINI_BASE_URL)، بعد حالت «پروکسی فوری» (ورکر کلودفلر)."""
    try:
        from giso.config import Config as _Cfg
        root = (getattr(_Cfg, "GEMINI_BASE_URL", "") or "").strip().rstrip("/")
        if root:
            return root
    except Exception:
        pass
    try:
        from giso.gemini_proxy_manager import MODE_WORKER, get_mode, get_worker_base_url
        if get_mode() == MODE_WORKER:
            return (get_worker_base_url() or "").strip().rstrip("/")
    except Exception:
        pass
    return ""


def _is_google_gemini_host(url: str) -> bool:
    """آدرس مستقیم گوگل از ایران بدون ورکر وصل نمی‌شود."""
    return "generativelanguage.googleapis.com" in (url or "").lower()


def _normalize_gemini_base_url(url: str) -> str:
    """خالی یا googleapis → ورکر پیش‌فرض گیسو؛ ورکر/آدرس سفارشی حفظ می‌شود."""
    u = (url or "").strip().rstrip("/")
    if not u or _is_google_gemini_host(u):
        return GEMINI_DEFAULT_BASE_URL
    return u


def _gemini_openai_base() -> str:
    """Base سازگار با OpenAI برای Gemini: مقدار env (مثلاً Worker) اولویت دارد."""
    root = _gemini_env_root()
    if not root or _is_google_gemini_host(root):
        return GEMINI_DEFAULT_BASE_URL
    if root.endswith("/openai"):
        return root
    if root.endswith("/v1beta"):
        return root + "/openai"
    return root + "/v1beta/openai"


def _effective_base_url(provider_name, row_base) -> str:
    """Base URL مؤثر: Gemini هرگز به googleapis مستقیم نمی‌رود (ورکر پیش‌فرض)."""
    base = (row_base or "").strip().rstrip("/")
    if str(provider_name or "").lower() != "gemini":
        return base
    env_root = _gemini_env_root()
    if env_root and not _is_google_gemini_host(env_root):
        return _gemini_openai_base()
    return _normalize_gemini_base_url(base)


# ═══ رجیستری فاز ۱ بازنویسی سیستم AI ═══
# منبع داده به giso/ai_models_registry.py منتقل شد (فایل مستقل، بدون رفتار اجرایی).
# لایه سازگاری: خروجی دقیقاً هم‌شکل PROVIDERS_REGISTRY قدیمی است تا کد فعلی
# (ai_brain.default_models_for_provider، analysis._provider_model_candidates،
#  bot.py افزودن پروایدر) بدون تغییر کار کند.
from giso.ai_models_registry import legacy_registry as _legacy_registry

PROVIDERS_REGISTRY = _legacy_registry()

_AI_EDITABLE = {
    "api_key": "api_key", "base_url": "base_url", "api_root": "api_root",
    "timeout": "timeout", "headers": "headers_json", "fallback": "fallback_json",
    "selected_model": "selected_model",
    # فاز ۲: پروکسی اختصاصی — بدون این، ویرایش «پروکسی اختصاصی» از پنل بی‌صدا شکست می‌خورد
    "proxy_url": "proxy_url",
}


def update_ai_provider_field(name, field, value):
    col = _AI_EDITABLE.get(field)
    if not col:
        return False
    if str(name or "").lower() == "gemini" and field in ("base_url", "api_root"):
        value = _normalize_gemini_base_url(value)
    conn = get_conn()
    try:
        with _lock, conn:
            cur = conn.execute(f"UPDATE giso_ai_providers SET {col}=? WHERE name=?", (value, name))
        return cur.rowcount > 0
    except Exception:
        return False


def save_ai_check_result(name, status, error, models, selected):
    now = _ai_now()
    conn = get_conn()
    try:
        with _lock, conn:
            conn.execute(
                """UPDATE giso_ai_providers
                   SET last_status=?, last_error=?, last_checked_at=?,
                       models_json=?, selected_model=?
                   WHERE name=?""",
                (status, error, now, json.dumps(models, ensure_ascii=False), selected, name)
            )
            conn.execute(
                """INSERT INTO giso_ai_checks_log (provider_name, status, error_text, checked_at)
                   VALUES (?,?,?,?)""",
                (name, status, error, now)
            )
            conn.execute(
                """DELETE FROM giso_ai_checks_log WHERE id NOT IN
                   (SELECT id FROM giso_ai_checks_log ORDER BY id DESC LIMIT 100)"""
            )
    except Exception as e:
        logger.error(f"save_ai_check_result: {e}")


def ai_provider_count():
    conn = get_conn()
    try:
        return conn.execute("SELECT COUNT(*) FROM giso_ai_providers").fetchone()[0]
    except Exception:
        return 0
    finally:
        conn.close()


def _ai_jloads(text, default):
    try:
        return _json.loads(text) if text else default
    except Exception:
        return default


def ai_pick_preferred_model(models, fallbacks):
    """
    اولویت انتخاب مدل (برای تحلیل عکس):
    1) fallbacks تعیین شده توسط ادمین
    2) مدل‌های vision رایگان (Gemini، Groq)
    3) مدل‌های vision پولی (GPT-4o، Claude)
    4) هر مدلی که کلیدواژه vision داشته باشد
    5) مدل‌های سبک متنی
    """
    if not models:
        return fallbacks[0] if fallbacks else ""
    model_set = set(models)

    for m in fallbacks:
        if m in model_set:
            return m

    free_vision = [
        "gemini-2.5-flash", "gemini-2.0-flash", "gemini-1.5-flash",
        "llama-3.2-11b-vision", "llama-4-scout", "pixtral-12b",
    ]
    for kw in free_vision:
        for m in models:
            if kw in str(m).lower():
                return str(m)

    paid_vision = [
        "gpt-4o-mini", "gpt-4o", "claude-3.5-sonnet", "claude-3-opus",
        "gemini-2.5-pro", "gemini-1.5-pro",
    ]
    for kw in paid_vision:
        for m in models:
            if kw in str(m).lower():
                return str(m)

    vision_kw = ["vision", "vl", "multimodal", "image"]
    for kw in vision_kw:
        for m in models:
            if kw in str(m).lower():
                return str(m)

    light = ["mini", "flash", "haiku", "8b", "small", "nano", ":free", "free"]
    for kw in light:
        for m in models:
            if kw in str(m).lower():
                return str(m)

    return str(models[0])


def _ai_text_openai(raw):
    choices = raw.get("choices")
    if isinstance(choices, list) and choices:
        content = (choices[0].get("message") or {}).get("content", "")
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            return "\n".join(it.get("text", "") for it in content
                             if isinstance(it, dict) and it.get("type") == "text").strip()
    return ""


def _ai_text_cloudflare(raw):
    result = raw.get("result", {})
    if isinstance(result, dict):
        for k in ("response", "text"):
            if isinstance(result.get(k), str):
                return result[k]
    if isinstance(raw.get("response"), str):
        return raw["response"]
    return ""


def _ai_err(provider, model, error):
    return {"ok": False, "provider": provider, "model": model,
            "text": "", "raw": {}, "error": error}


async def _ai_check_openai(row):
    api_key = (row["api_key"] or "").strip()
    base_url = _effective_base_url(row["name"], row["base_url"])
    timeout = int(row["timeout"] or 20)
    extra_headers = _ai_jloads(row["headers_json"], {})
    fallback = _ai_jloads(row["fallback_json"], [])
    proxy = _get_proxy_for_provider(row)

    if not api_key:
        return {"status": "not configured", "error": "API Key ثبت نشده", "models": [], "selected": ""}
    if not base_url:
        return {"status": "not configured", "error": "Base URL ثبت نشده", "models": [], "selected": ""}

    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    headers.update(extra_headers)
    models, selected, status, error = [], "", "error", ""

    async with _make_client(timeout, proxy) as client:
        try:
            resp = await client.get(f"{base_url}/models", headers=headers)
            if resp.status_code == 200:
                data = resp.json()
                models = [m["id"] for m in data.get("data", [])
                          if isinstance(m, dict) and m.get("id")]
        except Exception as exc:
            error = str(exc)

        candidates = []
        if models:
            pref = ai_pick_preferred_model(models, fallback)
            if pref:
                candidates.append(pref)
        for m in fallback + models:
            if m not in candidates:
                candidates.append(m)

        for model in candidates[:6]:
            try:
                resp = await client.post(
                    f"{base_url}/chat/completions", headers=headers,
                    json={"model": model,
                          "messages": [{"role": "user", "content": "Hi"}],
                          "max_tokens": 8, "temperature": 0.2}
                )
                if resp.status_code == 200:
                    selected, status, error = model, "ok", ""
                    if model not in models:
                        models.insert(0, model)
                    break
                error = f"HTTP {resp.status_code}: {resp.text[:200]}"
            except Exception as exc:
                error = str(exc)

    if status != "ok" and not error:
        error = "هیچ مدل سالمی پیدا نشد"
    return {"status": status, "error": error, "models": models, "selected": selected}


async def _ai_check_cloudflare(row):
    api_key = (row["api_key"] or "").strip()
    api_root = (row["api_root"] or "").strip().rstrip("/")
    timeout = int(row["timeout"] or 20)
    fallback = _ai_jloads(row["fallback_json"], [])
    proxy = _get_proxy_for_provider(row)

    if not api_key:
        return {"status": "not configured", "error": "API Key ثبت نشده", "models": [], "selected": ""}
    if not api_root:
        return {"status": "not configured", "error": "API Root ثبت نشده", "models": [], "selected": ""}
    if "{account_id}" in api_root:
        return {"status": "not configured",
                "error": "شناسهٔ حساب کلودفلر در API Root جایگزین {account_id} نشده است",
                "models": [], "selected": ""}

    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    models, selected, status, error = [], "", "error", ""

    async with _make_client(timeout, proxy) as client:
        for model in fallback:
            try:
                resp = await client.post(
                    f"{api_root}/{model}", headers=headers,
                    json={"messages": [{"role": "user", "content": "Hi"}], "max_tokens": 8}
                )
                if resp.status_code == 200:
                    raw = resp.json()
                    if raw.get("success", True) is False:
                        continue
                    selected, models, status, error = model, [model], "ok", ""
                    break
                error = f"HTTP {resp.status_code}"
            except Exception as exc:
                error = str(exc)

    if status != "ok" and not error:
        error = "هیچ مدل سالم Cloudflare پیدا نشد"
    return {"status": status, "error": error, "models": models, "selected": selected}


async def check_ai_provider(name):
    if _httpx is None:
        return {"status": "error", "error": "httpx نصب نیست", "models": [], "selected": ""}
    row = get_ai_provider(name)
    if row is None:
        return {"status": "not found", "error": "پروایدر پیدا نشد", "models": [], "selected": ""}
    if row["kind"] == "cloudflare":
        result = await _ai_check_cloudflare(row)
    else:
        result = await _ai_check_openai(row)
    save_ai_check_result(name, result["status"], result["error"],
                         result["models"], result["selected"])
    return result


async def check_all_ai_providers():
    rows = list_ai_providers()
    results = await asyncio.gather(
        *(check_ai_provider(r["name"]) for r in rows), return_exceptions=True
    )
    summary = []
    for row, res in zip(rows, results):
        if isinstance(res, Exception):
            summary.append({"name": row["name"], "status": "exception",
                            "error": str(res), "selected": "", "models": []})
        else:
            summary.append({"name": row["name"], **res})
    return summary


# ═══════════════════════════════════════════════════════════
# فاز ۲: کشف پویای مدل‌ها + ورود دسته‌ای + کاشت پروایدرهای جدید
# ═══════════════════════════════════════════════════════════

# کلیدواژه‌های تشخیص مدل بینایی در کشف پویا (هماهنگ با analysis.VISION_KEYWORDS)
_DYNAMIC_VISION_KEYWORDS = [
    "vision", "vl", "multimodal", "image", "gpt-4o", "gpt-5",
    "gemini", "claude-3", "claude-4", "llama-3.2", "llama-4",
    "llava", "pixtral", "qwen-vl", "qwen2.5-vl", "smolvlm",
    # مدل‌های رایگان بینایی ۱۴۰۵-۰۶-۱۹ (برای کشف هوشمند و آنالیز):
    "gemma-4", "inkling", "omni", "mistral-small",
]
_DYNAMIC_NON_VISION_KEYWORDS = [
    "tts", "embedding", "whisper", "audio", "compound",
    "text-only", "moderation", "rerank", "search",
]


def _is_vision_model_id(model_id):
    m = str(model_id or "").lower()
    if not m:
        return False
    for kw in _DYNAMIC_NON_VISION_KEYWORDS:
        if kw in m:
            return False
    for kw in _DYNAMIC_VISION_KEYWORDS:
        if kw in m:
            return True
    return False


def _model_is_free(entry):
    """تشخیص رایگان بودن: پسوند :free یا قیمت صفر (سبک OpenRouter)."""
    try:
        if str(entry.get("id", "")).endswith(":free"):
            return True
        pricing = entry.get("pricing") or {}
        prompt_price = pricing.get("prompt")
        if prompt_price is not None and float(prompt_price) == 0:
            return True
    except Exception:
        pass
    return False


async def _fetch_remote_models(row):
    """فقط گرفتن لیست مدل‌ها از /models — بدون درخواست تست (Hi)."""
    api_key = (row["api_key"] or "").strip()
    base_url = _effective_base_url(row["name"], row["base_url"])
    if not api_key:
        return {"ok": False, "error": "API Key ثبت نشده"}
    if not base_url:
        return {"ok": False, "error": "Base URL ثبت نشده"}
    timeout = max(5, min(30, int(row["timeout"] or 20)))
    headers = {"Authorization": f"Bearer {api_key}"}
    headers.update(_ai_jloads(row["headers_json"], {}))
    proxy = _get_proxy_for_provider(row)
    try:
        async with _make_client(timeout, proxy) as client:
            resp = await client.get(f"{base_url}/models", headers=headers)
        if resp.status_code != 200:
            return {"ok": False, "error": f"HTTP {resp.status_code}"}
        data = resp.json()
        items = data.get("data", []) if isinstance(data, dict) else []
        return {"ok": True, "items": [m for m in items if isinstance(m, dict) and m.get("id")]}
    except Exception as exc:
        return {"ok": False, "error": f"{type(exc).__name__}: {str(exc)[:160]}"}


def _merge_discovered(existing, discovered_ids):
    """مدل جدید ← افزودن با source=discovered؛ حذف‌شده ← پرچم disabled (بدون حذف فیزیکی)."""
    merged, seen = [], set()
    for m in existing:
        if not isinstance(m, dict) or not m.get("id"):
            continue
        m = dict(m)
        if m["id"] in discovered_ids:
            m.pop("disabled", None)
        else:
            m["disabled"] = True
        seen.add(m["id"])
        merged.append(m)
    new_ids = []
    for mid in discovered_ids:
        if mid in seen:
            continue
        merged.append({"id": mid, "is_free": str(mid).endswith(":free"),
                       "source": "discovered"})
        new_ids.append(mid)
    return merged, new_ids


def refresh_models(provider_name):
    """
    فاز ۲: به‌روزرسانی لیست مدل‌ها از /models سرویس (بدون پینگ تست).
    نتیجه در ستون‌های vision_models_json و text_models_json ذخیره می‌شود.
    """
    row = get_ai_provider(provider_name)
    if row is None:
        return {"ok": False, "error": "پروایدر پیدا نشد"}
    if row["kind"] == "cloudflare":
        return {"ok": False, "error": "Cloudflare endpoint مدل‌های جدا ندارد؛ مدل‌ها از رجیستری/ورودی دستی مدیریت می‌شوند"}
    fetched = run_async_sync(_fetch_remote_models(row))
    if not fetched or not fetched.get("ok"):
        return {"ok": False, "error": (fetched or {}).get("error", "خطا در دریافت مدل‌ها")}

    vision_ids, text_ids = [], []
    free_map = {}
    for item in fetched["items"]:
        mid = item["id"]
        free_map[mid] = _model_is_free(item)
        if _is_vision_model_id(mid):
            vision_ids.append(mid)
        else:
            text_ids.append(mid)

    old_vision = _ai_jloads(_col(row, "vision_models_json", ""), [])
    old_text = _ai_jloads(_col(row, "text_models_json", ""), [])
    if not isinstance(old_vision, list):
        old_vision = []
    if not isinstance(old_text, list):
        old_text = []

    merged_vision, new_vision = _merge_discovered(old_vision, vision_ids)
    merged_text, new_text = _merge_discovered(old_text, text_ids)
    for m in merged_vision + merged_text:
        if m.get("id") in free_map:
            m["is_free"] = free_map[m["id"]]

    now = _ai_now()
    try:
        conn = get_conn()
        with _lock, conn:
            conn.execute(
                """UPDATE giso_ai_providers
                   SET vision_models_json=?, text_models_json=?,
                       models_last_updated=?, models_source='discovered'
                   WHERE name=?""",
                (json.dumps(merged_vision, ensure_ascii=False),
                 json.dumps(merged_text, ensure_ascii=False),
                 now, provider_name)
            )
    except Exception as e:
        logger.error(f"refresh_models save: {e}")
        return {"ok": False, "error": "خطا در ذخیره مدل‌ها"}

    return {
        "ok": True,
        "vision_count": len([m for m in merged_vision if not m.get("disabled")]),
        "text_count": len([m for m in merged_text if not m.get("disabled")]),
        "new": new_vision + new_text,
        "removed": [m["id"] for m in merged_vision + merged_text if m.get("disabled")],
        "updated_at": now,
    }


def bulk_import_models(json_text):
    """ورود دسته‌ای مدل‌ها با JSON — فقط افزودنی، بدون پاک‌کردن مدل‌های فعلی."""
    try:
        data = json.loads(json_text or "")
    except Exception:
        return {"ok": False, "error": "JSON نامعتبر است"}
    provider = str(data.get("provider") or "").strip().lower()
    add_models = data.get("add_models") or []
    if not provider or get_ai_provider(provider) is None:
        return {"ok": False, "error": "پروایدر مشخص نشده یا پیدا نشد"}
    if not isinstance(add_models, list) or not add_models:
        return {"ok": False, "error": "لیست add_models خالی یا نامعتبر است"}

    row = get_ai_provider(provider)
    vision = _ai_jloads(_col(row, "vision_models_json", ""), [])
    text = _ai_jloads(_col(row, "text_models_json", ""), [])
    if not isinstance(vision, list):
        vision = []
    if not isinstance(text, list):
        text = []
    seen = {m.get("id") for m in vision + text if isinstance(m, dict)}

    added = 0
    for item in add_models:
        if not isinstance(item, dict) or not item.get("id"):
            continue
        mid = str(item["id"]).strip()
        if mid in seen:
            continue
        entry = {
            "id": mid,
            "is_free": bool(item.get("is_free")),
            "context": item.get("context", 0),
            "source": "manual_json",
        }
        mtype = str(item.get("type") or "").lower()
        if mtype == "vision":
            vision.append(entry)
        elif mtype == "both":
            # مدل دوگانه: هم در زنجیره بینایی و هم در زنجیره متن
            vision.append(dict(entry))
            text.append(entry)
        else:
            text.append(entry)
        seen.add(mid)
        added += 1

    if added:
        try:
            conn = get_conn()
            with _lock, conn:
                conn.execute(
                    """UPDATE giso_ai_providers
                       SET vision_models_json=?, text_models_json=?,
                           models_last_updated=?, models_source='manual_json'
                       WHERE name=?""",
                    (json.dumps(vision, ensure_ascii=False),
                     json.dumps(text, ensure_ascii=False),
                     _ai_now(), provider)
                )
        except Exception as e:
            logger.error(f"bulk_import_models save: {e}")
            return {"ok": False, "error": "خطا در ذخیره مدل‌ها"}

    return {"ok": True, "added": added, "provider": provider,
            "vision_count": len(vision), "text_count": len(text)}


def _normalize_existing_provider_names():
    """مهاجرت نام‌های نمایشی ذخیره‌شده در دیتابیس به کلید استاندارد رجیستری.

    مثلاً ردیف «hugging face» (با فاصله، بدون مدل) به «huggingface» تبدیل و
    مدل‌های رجیستری برایش فعال می‌شود. اگر ردیف استاندارد از قبل وجود داشته
    باشد، کلید/پروکسی ردیف قدیمی به آن منتقل و ردیف تکراری حذف می‌شود.
    """
    from giso.ai_models_registry import normalize_provider_name as _normalize_pname
    try:
        with _lock, get_conn() as conn:
            rows = conn.execute(
                "SELECT name, api_key, proxy_url, enabled FROM giso_ai_providers").fetchall()
        for r in rows:
            old = str(r["name"] or "")
            canon = _normalize_pname(old)
            if canon == old:
                continue
            # اتصال تازه برای هر تغییر: _ManagedConnection در پایان with بسته می‌شود
            with _lock, get_conn() as conn:
                dup = conn.execute(
                    "SELECT name FROM giso_ai_providers WHERE name=?", (canon,)).fetchone()
                if dup:
                    # ادغام: کلید/پروکسی ردیف قدیمی به ردیف استاندارد منتقل می‌شود
                    conn.execute(
                        """UPDATE giso_ai_providers SET
                             api_key=CASE WHEN api_key='' THEN ? ELSE api_key END,
                             proxy_url=CASE WHEN proxy_url='' THEN ? ELSE proxy_url END
                           WHERE name=?""",
                        (str(r["api_key"] or ""), str(r["proxy_url"] or ""), canon))
                    conn.execute("DELETE FROM giso_ai_providers WHERE name=?", (old,))
                    logger.info(f"normalize providers: «{old}» در «{canon}» ادغام شد")
                else:
                    conn.execute(
                        "UPDATE giso_ai_providers SET name=? WHERE name=?", (canon, old))
                    logger.info(f"normalize providers: «{old}» ← «{canon}»")
    except Exception as e:
        logger.error(f"_normalize_existing_provider_names: {e}")


def _backfill_registry_models(name):
    """پُرکردن مدل‌های خالی یک ردیف از رجیستری (بدون دست‌زدن به دادهٔ موجود).

    ردیف‌های قدیمی که با نام نمایشی (مثل «hugging face») ساخته شده بودند
    لیست مدل خالی دارند؛ بعد از تغییر نام به کلید استاندارد، مدل‌ها هم از
    رجیستری تزریق می‌شود تا زنجیرهٔ فراخوانی خالی نماند.
    """
    from giso.ai_models_registry import get_provider as _reg_provider

    def _load_list(raw):
        try:
            val = _json.loads(raw or "[]")
            return val if isinstance(val, list) else []
        except Exception:
            return []

    reg = _reg_provider(name) or {}
    if not reg:
        return
    try:
        with _lock, get_conn() as conn:
            row = conn.execute(
                "SELECT models_json, selected_model, fallback_json, "
                "vision_models_json, text_models_json "
                "FROM giso_ai_providers WHERE name=?", (name,)).fetchone()
            if row is None:
                return
            vision = reg.get("vision_models", [])
            text = reg.get("text_models", [])
            all_ids = [m.get("id") for m in vision + text if m.get("id")]
            updates = []
            params = []
            if not _load_list(row["models_json"]):
                updates.append("models_json=?")
                params.append(_json.dumps(all_ids, ensure_ascii=False))
            if not _load_list(row["fallback_json"]):
                updates.append("fallback_json=?")
                params.append(_json.dumps(all_ids, ensure_ascii=False))
            if not str(row["selected_model"] or "").strip() and all_ids:
                updates.append("selected_model=?")
                params.append(all_ids[0])
            if not _load_list(row["vision_models_json"]) and vision:
                updates.append("vision_models_json=?")
                params.append(_json.dumps(vision, ensure_ascii=False))
            if not _load_list(row["text_models_json"]) and text:
                updates.append("text_models_json=?")
                params.append(_json.dumps(text, ensure_ascii=False))
            if updates:
                params.append(name)
                conn.execute(
                    f"UPDATE giso_ai_providers SET {', '.join(updates)} WHERE name=?", params)
                logger.info(f"backfill_registry_models: مدل‌های «{name}» از رجیستری کامل شد")
    except Exception as e:
        logger.error(f"_backfill_registry_models({name}): {e}")


# پروایدرهایی که اگر ردیف نداشته باشند، ردیف خالی (بدون کلید، غیرفعال) می‌گیرند؛
# به‌محض واردشدن «نام + API Key» در ربات/پنل، آدرس بیس و مدل‌ها خودکار پر می‌شود.
REGISTRY_SEED_PROVIDERS = ("groq", "openrouter", "mistral", "sambanova", "cloudflare")

# پروایدرهای بازنشستهٔ پروژه (دستور کارفرما ۱۴۰۵-۰۶-۱۸: در پروژه جواب نمی‌دادند).
# ردیف‌شان حذف نمی‌شود تا داده‌ای از بین نرود؛ فقط غیرفعال می‌مانند (الگوی LLM7).
RETIRED_PROVIDERS = ("huggingface", "cerebras", "llm7")


def _refresh_registry_sourced_models():
    """به‌روزرسانی مدل‌های پروایدرهایی که لیست مدلشان از رجیستری آمده است.

    فقط ردیف‌هایی که منبع مدلشان «رجیستری» یا خالی است (یعنی کاربر دستی مدل
    وارد نکرده) با لیست تمیز رجیستری تازه‌سازی می‌شوند تا مدل‌های مردهٔ قدیمی
    (مثل gemma-3-27b اوپن‌روتر) از زنجیره بیرون بیفتند. ردیف‌های با منبع
    «دستی» یا «کشف از API» هرگز لمس نمی‌شوند. مدل انتخابی کاربر فقط وقتی
    تغییر می‌کند که مدل فعلی دیگر در لیست جدید وجود نداشته باشد (مرده باشد).
    فقط پروایدرهای لیست تمیز تازه‌سازی می‌شوند؛ پروایدرهای ایرانی و جمینای
    کارفرما (gapgpt، avalai، gemini) با تنظیمات شخصی دست‌نخورده می‌مانند.
    """
    from giso.ai_models_registry import get_provider as _reg_provider
    # فقط پروایدرهای رایگانِ لیست تمیز تازه‌سازی می‌شوند؛ بقیه دست‌نخورده.
    refresh_names = ("groq", "openrouter", "mistral", "sambanova", "cloudflare")
    try:
        for name in refresh_names:
            reg = _reg_provider(name) or {}
            if not reg:
                continue
            try:
                with _lock, get_conn() as conn:
                    row = conn.execute(
                        "SELECT models_source, selected_model FROM giso_ai_providers "
                        "WHERE name=?", (name,)).fetchone()
                    if row is None:
                        continue
                    src = str(row["models_source"] or "").strip()
                    if src not in ("", "registry"):
                        continue  # مدل دستی/کشف‌شده: دست نزن
                    vision = reg.get("vision_models", [])
                    text = reg.get("text_models", [])
                    all_ids = [m.get("id") for m in vision + text if m.get("id")]
                    if not all_ids:
                        continue
                    selected = str(row["selected_model"] or "")
                    new_selected = selected if selected in all_ids else all_ids[0]
                    conn.execute(
                        """UPDATE giso_ai_providers SET
                             models_json=?, fallback_json=?, selected_model=?,
                             vision_models_json=?, text_models_json=?,
                             models_source='registry'
                           WHERE name=?""",
                        (_json.dumps(all_ids, ensure_ascii=False),
                         _json.dumps(all_ids, ensure_ascii=False),
                         new_selected,
                         _json.dumps(vision, ensure_ascii=False),
                         _json.dumps(text, ensure_ascii=False),
                         name))
                if selected != new_selected:
                    logger.info(f"refresh models: «{name}» مدل انتخابی {selected or '—'} ← {new_selected}")
            except Exception as e:
                logger.error(f"_refresh_registry_sourced_models({name}): {e}")
    except Exception as e:
        logger.error(f"_refresh_registry_sourced_models: {e}")


def seed_registry_providers():
    """کاشت ردیف‌های خالی هوش مصنوعی جدید از رجیستری (بدون کلید، غیرفعال)."""
    from giso.ai_models_registry import get_provider as _reg_provider
    _normalize_existing_provider_names()
    _refresh_registry_sourced_models()
    seeded = []
    for name in REGISTRY_SEED_PROVIDERS:
        if get_ai_provider(name) is not None:
            # ردیف از قبل هست (مثلاً با نام نمایشی قدیمی که تغییرنام یافته):
            # اگر مدل‌هایش خالی است، از رجیستری کامل شود.
            _backfill_registry_models(name)
            continue
        reg = _reg_provider(name) or {}
        ok = add_ai_provider(
            name=name, kind=reg.get("kind", "openai"), api_key="",
            base_url=reg.get("base_url", ""), api_root=reg.get("api_root", ""),
            timeout=reg.get("timeout", 20), is_iranian=bool(reg.get("is_iranian")),
            enabled=False, use_proxy=False, replace=False,
            vision_models_json=json.dumps(reg.get("vision_models", []), ensure_ascii=False),
            text_models_json=json.dumps(reg.get("text_models", []), ensure_ascii=False),
            models_source="registry",
        )
        if ok:
            seeded.append(name)
    # غیرفعال‌سازی پروایدرهای بازنشسته (ماندن در دیتابیس با enabled=0)
    try:
        with _lock, get_conn() as conn:
            for _ret in RETIRED_PROVIDERS:
                conn.execute("UPDATE giso_ai_providers SET enabled=0 WHERE name=?", (_ret,))
    except Exception as e:
        logger.error(f"seed_registry_providers disable retired: {e}")
    if seeded:
        logger.info(f"seed_registry_providers: {', '.join(seeded)} اضافه شد")
    return seeded


def run_async_sync(coro):
    """اجرای یک coroutine به‌صورت همگام (برای فراخوانی از کد غیر-async)."""
    try:
        from giso.async_compat import run_async_safe
        return run_async_safe(coro)
    except Exception as e:
        logger.error(f"run_async_sync: {e}")
        return None


async def ask_ai(provider_name, messages, model=None, temperature=0.7, max_tokens=1200,
                 sensitive_proxy=False, timeout_override=None):
    if _httpx is None:
        return _ai_err(provider_name, "", "httpx نصب نیست")

    row = get_ai_provider(provider_name)
    if row is None:
        return _ai_err(provider_name, "", "پروایدر پیدا نشد")
    if not row["enabled"]:
        return _ai_err(provider_name, "", "پروایدر غیرفعال است")

    fallback = _ai_jloads(row["fallback_json"], [])
    use_model = model or row["selected_model"] or (fallback[0] if fallback else "")
    if not use_model:
        # فالبک نهایی: مدل پیش‌فرض رجیستری — پروایدرهایی که با نام نمایشی (مثل
        # «hugging face») اضافه شده‌اند و مدل ذخیره‌شده ندارند هم بی‌مدل نمی‌مانند.
        use_model = default_models_for_provider(provider_name)[1]
    if not use_model:
        return _ai_err(provider_name, "", "مدلی انتخاب نشده")

    api_key = (row["api_key"] or "").strip()
    if not api_key:
        return _ai_err(provider_name, use_model, "API Key تنظیم نشده")

    # فاز ۳: سقف زمانی هر موتور می‌تواند تایم‌اوت پروایدر را محدود کند
    try:
        timeout = int(timeout_override) if timeout_override else int(row["timeout"] or 20)
    except (TypeError, ValueError):
        timeout = int(row["timeout"] or 20)
    proxy = _get_proxy_for_provider(row, sensitive=sensitive_proxy)
    # Gemini با Base URL: httpx مستقیم به {base}/chat/completions — بدون SOCKS
    if str(provider_name or "").strip().lower() == "gemini":
        proxy = None

    try:
        if row["kind"] == "cloudflare":
            api_root = (row["api_root"] or "").strip().rstrip("/")
            if not api_root:
                return _ai_err(provider_name, use_model, "API Root تنظیم نشده")
            if "{account_id}" in api_root:
                # آدرس کلودفلر باید شناسهٔ حساب واقعی داشته باشد؛ وگرنه همهٔ
                # فراخوانی‌ها بی‌دلیل شکست می‌خورند. پیام راهنمای واضح بده.
                return _ai_err(provider_name, use_model,
                               "شناسهٔ حساب کلودفلر در API Root جایگزین {account_id} نشده است")
            headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
            async with _make_client(timeout, proxy) as client:
                resp = await client.post(
                    f"{api_root}/{use_model}", headers=headers,
                    json={"messages": messages, "max_tokens": max_tokens}
                )
            if resp.status_code != 200:
                return _ai_err(provider_name, use_model, f"HTTP {resp.status_code}")
            raw = resp.json()
            return {"ok": True, "provider": provider_name, "model": use_model,
                    "text": _ai_text_cloudflare(raw), "raw": raw, "error": ""}

        base_url = _effective_base_url(provider_name, row["base_url"])
        if not base_url:
            return _ai_err(provider_name, use_model, "Base URL تنظیم نشده")
        headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
        headers.update(_ai_jloads(row["headers_json"], {}))
        async with _make_client(timeout, proxy) as client:
            resp = await client.post(
                f"{base_url}/chat/completions", headers=headers,
                json={"model": use_model, "messages": messages,
                      "temperature": temperature, "max_tokens": max_tokens}
            )
        _record_gemini_proxy_result(provider_name, proxy, resp.status_code == 200, resp.status_code)
        if resp.status_code != 200:
            return _ai_err(provider_name, use_model, f"HTTP {resp.status_code}: {resp.text[:200]}")
        raw = resp.json()
        return {"ok": True, "provider": provider_name, "model": use_model,
                "text": _ai_text_openai(raw), "raw": raw, "error": ""}
    except Exception as exc:
        _record_gemini_proxy_result(provider_name, proxy, False, 0)
        return _ai_err(provider_name, use_model, f"{type(exc).__name__}: {str(exc)[:200]}")


async def ask_ai_vision(provider_name, image_path, prompt, model=None, max_tokens=1200,
                        timeout_override=None):
    """
    ارسال عکس به AI برای تحلیل مو / صورت.
    فرمت استاندارد OpenAI vision (image_url در قالب base64).
    """
    if _httpx is None:
        return _ai_err(provider_name, "", "httpx نصب نیست")
    try:
        with open(image_path, "rb") as f:
            img_data = base64.b64encode(f.read()).decode()
        ext = image_path.split(".")[-1].lower()
        if ext == "jpg":
            ext = "jpeg"
        image_url = f"data:image/{ext};base64,{img_data}"
    except Exception as e:
        return _ai_err(provider_name, "", f"خطا در خواندن عکس: {e}")

    messages = [{
        "role": "user",
        "content": [
            {"type": "text", "text": prompt},
            {"type": "image_url", "image_url": {"url": image_url}}
        ]
    }]
    return await ask_ai(provider_name, messages, model=model, max_tokens=max_tokens,
                        sensitive_proxy=True, timeout_override=timeout_override)


async def ask_ai_fast(messages, model=None, temperature=0.7, max_tokens=1200, category=""):
    """راه سریع متنی — فاز ۳: سقف ۱۵ ثانیه کل / ۴ ثانیه هر مدل + سلامت مشترک."""
    import time as _time
    from giso.ai_config import (FAST_TOTAL_TIMEOUT_SECONDS, FAST_PER_MODEL_TIMEOUT_SECONDS,
                                FEATURE_FLAG_LEGACY_MODE)
    legacy = FEATURE_FLAG_LEGACY_MODE
    health = None
    if not legacy:
        try:
            from giso import ai_health as health
        except Exception:
            health = None

    rows = list_ai_providers(only_enabled=True)
    if not rows:
        return _ai_err("", "", "هیچ پروایدر فعالی وجود ندارد")
    foreign = [r for r in rows if not r["is_iranian"]]
    iranian = [r for r in rows if r["is_iranian"]]
    last_error = "همه پروایدرها خطا دادند"
    start = _time.time()
    for row in foreign + iranian:
        pname = row["name"]
        use_model = model or row["selected_model"] or ""
        if not legacy:
            if _time.time() - start > FAST_TOTAL_TIMEOUT_SECONDS:
                logger.info("[AI_ATTEMPT] engine=fast result=budget_exceeded elapsed=%.1fs",
                            _time.time() - start)
                break
            if health is not None and health.is_in_cooldown(pname):
                logger.info("[AI_ATTEMPT] engine=fast provider=%s result=cooldown_skipped", pname)
                continue
        attempt_start = _time.time()
        result = await ask_ai(pname, messages, model=model,
                              temperature=temperature, max_tokens=max_tokens,
                              timeout_override=None if legacy else FAST_PER_MODEL_TIMEOUT_SECONDS)
        duration = _time.time() - attempt_start
        if result["ok"]:
            if not legacy and health is not None:
                health.mark_success(pname, result.get("model") or use_model)
            logger.info("[AI_ATTEMPT] engine=fast provider=%s model=%s result=success duration=%.1fs",
                        pname, result.get("model") or use_model, duration)
            return result
        last_error = result["error"]
        if not legacy and health is not None:
            etype = health.classify_error_text(last_error)
            health.mark_failure(pname, result.get("model") or use_model, etype, last_error)
            logger.info("[AI_ATTEMPT] engine=fast provider=%s model=%s result=%s duration=%.1fs",
                        pname, result.get("model") or use_model, etype, duration)
    return _ai_err("", "", last_error)


# ═══════════════════════════════════════════════════════════
# ذخیره‌سازی دو لایه: دیتابیس + فایل .env (fallback/backup)
# ═══════════════════════════════════════════════════════════
_ENV_PATH = Path(__file__).resolve().parent / "data" / ".env"


def _read_env_file():
    """خواندن فایل .env به صورت dict (بدون رندر متغیر)."""
    import os
    env_vars = {}
    try:
        if not _ENV_PATH.exists():
            return env_vars
        with open(_ENV_PATH, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, value = line.split("=", 1)
                env_vars[key.strip()] = value.strip()
    except Exception as e:
        logger.error(f"_read_env_file: {e}")
    return env_vars


def load_providers_from_env():
    """
    خواندن اطلاعات AI providers از فایل .env
    فقط وقتی استفاده می‌شود که دیتابیس خالی باشد (fallback)
    """
    import os
    env_vars = _read_env_file()
    if not env_vars:
        logger.warning("فایل .env گیسو پیدا نشد یا خالی است")
        return []

    try:
        count = int(env_vars.get("GISO_AI_COUNT", "0") or "0")
    except (TypeError, ValueError):
        count = 0

    providers = []
    for i in range(1, count + 1):
        prefix = f"GISO_AI_{i}_"
        name = env_vars.get(f"{prefix}NAME", "")
        if not name:
            continue
        try:
            enabled = int(env_vars.get(f"{prefix}ENABLED", "1") or "1")
        except (TypeError, ValueError):
            enabled = 1
        try:
            proxy = int(env_vars.get(f"{prefix}PROXY", "0") or "0")
        except (TypeError, ValueError):
            proxy = 0
        try:
            iranian = int(env_vars.get(f"{prefix}IRANIAN", "0") or "0")
        except (TypeError, ValueError):
            iranian = 0
        try:
            timeout = int(env_vars.get(f"{prefix}TIMEOUT", "20") or "20")
        except (TypeError, ValueError):
            timeout = 20
        providers.append({
            "name": name,
            "api_key": env_vars.get(f"{prefix}KEY", ""),
            "base_url": env_vars.get(f"{prefix}URL", ""),
            "selected_model": env_vars.get(f"{prefix}MODEL", ""),
            "enabled": enabled,
            "use_proxy": proxy,
            "is_iranian": iranian,
            "timeout": timeout,
        })
    logger.info(f"از .env خوانده شد: {len(providers)} provider")
    return providers


def sync_env_providers_to_db():
    """
    اگر دیتابیس خالی است، از .env بخوان و پر کن.
    سرعت خواندن عادی را تحت تأثیر قرار نمی‌دهد (فقط وقتی DB خالی است اجرا می‌شود).
    """
    try:
        existing = list_ai_providers()
        if existing and len(existing) > 0:
            return  # دیتابیس پر است، نیازی نیست
        providers = load_providers_from_env()
        if not providers:
            return
        for p in providers:
            add_ai_provider(
                name=p["name"], kind="openai", api_key=p["api_key"],
                base_url=p["base_url"], api_root=p["base_url"],
                timeout=p["timeout"], is_iranian=bool(p["is_iranian"]),
                enabled=bool(p["enabled"]), use_proxy=bool(p["use_proxy"]),
                replace=True,
            )
            if p.get("selected_model"):
                update_ai_provider_field(p["name"], "selected_model", p["selected_model"])
        logger.info(f"از .env به دیتابیس sync شد: {len(providers)} provider")
    except Exception as e:
        logger.error(f"sync_env_providers_to_db: {e}")


def _validate_base_url(base_url: str) -> None:
    """مرحلهٔ ۲ se.md / BUG-002 — جلوگیری از SSRF در base_url پراوایدر AI.

    فقط https؛ مسدودسازی loopback/private/link-local/reserved و localhost.
    base_url خالی مجاز است (پراوایدرهای پیش‌فرض/بدون override دست‌نخورده).
    """
    url = (base_url or "").strip()
    if not url:
        return
    from urllib.parse import urlparse
    import ipaddress
    u = urlparse(url)
    if u.scheme != "https":
        raise ValueError("نشانی پراوایدر باید فقط https باشد.")
    host = (u.hostname or "").lower()
    if not host:
        raise ValueError("نشانی پراوایدر نامعتبر است.")
    if host == "localhost" or host.endswith(".localhost") or host.endswith(".local"):
        raise ValueError("نشانی داخلی/لوکال برای پراوایدر مجاز نیست.")
    try:
        ip = ipaddress.ip_address(host.strip("[]"))
    except ValueError:
        ip = None
    if ip is not None and (ip.is_loopback or ip.is_private or ip.is_link_local
                           or ip.is_reserved or ip.is_unspecified):
        raise ValueError("آدرس IP داخلی برای پراوایدر مجاز نیست.")


def save_provider_to_env(name, api_key="", base_url="", model="", enabled=True,
                         proxy=False, iranian=False, timeout=20):
    """
    ذخیره یا آپدیت یک provider در فایل .env.
    API Key در هیچ لاگی چاپ نمی‌شود.
    """
    import os
    _validate_base_url(base_url)
    lines = []
    if _ENV_PATH.exists():
        try:
            with open(_ENV_PATH, "r", encoding="utf-8") as f:
                lines = f.readlines()
        except Exception:
            pass

    env_vars = _read_env_file()
    try:
        count = int(env_vars.get("GISO_AI_COUNT", "0") or "0")
    except (TypeError, ValueError):
        count = 0

    # پیدا کردن شماره این provider یا افزودن شماره جدید
    found_idx = None
    for i in range(1, count + 1):
        if env_vars.get(f"GISO_AI_{i}_NAME", "") == name:
            found_idx = i
            break
    if not found_idx:
        count += 1
        found_idx = count

    prefix = f"GISO_AI_{found_idx}_"
    new_vars = {
        f"{prefix}NAME": name,
        f"{prefix}KEY": api_key or "",
        f"{prefix}URL": base_url or "",
        f"{prefix}MODEL": model or "",
        f"{prefix}ENABLED": str(int(bool(enabled))),
        f"{prefix}PROXY": str(int(bool(proxy))),
        f"{prefix}IRANIAN": str(int(bool(iranian))),
        f"{prefix}TIMEOUT": str(int(timeout or 20)),
        "GISO_AI_COUNT": str(count),
    }

    updated_keys = set()
    new_lines = []
    for line in lines:
        line_stripped = line.strip()
        if line_stripped and not line_stripped.startswith("#") and "=" in line_stripped:
            k = line_stripped.split("=", 1)[0].strip()
            if k in new_vars:
                new_lines.append(f"{k}={new_vars[k]}\n")
                updated_keys.add(k)
                continue
        new_lines.append(line)

    for k, v in new_vars.items():
        if k not in updated_keys:
            new_lines.append(f"{k}={v}\n")

    try:
        with open(_ENV_PATH, "w", encoding="utf-8") as f:
            f.writelines(new_lines)
        logger.info(f"provider '{name}' در .env ذخیره شد")
    except Exception as e:
        logger.error(f"save_provider_to_env: {e}")


__all__ = [
    "init_ai_tables", "AI_SCHEMA", "get_ai_provider", "list_ai_providers",
    "add_ai_provider", "delete_ai_provider", "toggle_ai_provider",
    "toggle_use_proxy", "update_ai_provider_field", "save_ai_check_result",
    "ai_provider_count", "ai_pick_preferred_model",
    "check_ai_provider", "check_all_ai_providers",
    "ask_ai", "ask_ai_vision", "ask_ai_fast", "PROVIDERS_REGISTRY",
    "GEMINI_DEFAULT_BASE_URL", "_effective_base_url", "_normalize_gemini_base_url",
    "load_providers_from_env", "sync_env_providers_to_db", "save_provider_to_env",
    "refresh_models", "bulk_import_models", "seed_registry_providers", "_col",
]
# Phase 7.2 Provider: verify ai_brain provider selection
# Phase 7.3 Prompt: standardize AI prompt consistency
