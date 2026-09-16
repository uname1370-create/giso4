"""
ai_brain.py — «مغز هوش مصنوعی» ربات، متمرکز در یک فایل.

این فایل حاصل بازآراییِ (refactoring) کدهای پراکندهٔ AI است. هیچ قابلیتی
اضافه یا حذف نشده و هیچ نامی تغییر نکرده — فقط محل نگهداری کد عوض شده.

محتویات:
  • جدول‌های ai_providers و ai_checks_log  (منتقل‌شده از db.py)
  • توابع دیتابیس پروایدرها               (منتقل‌شده از db.py)
  • منطق فراخوانی AI: ask_ai / ask_ai_fast (منتقل‌شده از core.py)
  • تست سلامت پروایدرها                    (منتقل‌شده از core.py)

سازگاری عقب‌رو (بسیار مهم):
  db.py و core.py همین نام‌ها را دوباره export می‌کنند، پس کدهای موجود مثل
  `from db import get_ai_provider` و `from core import ask_ai` بدون هیچ
  تغییری کار می‌کنند. ماژول ai_mentor و handlers_ai هم دست‌نخورده‌اند.

وابستگی: فقط stdlib + httpx. هرگز از core.py یا handlers.py import نکنید
(زنجیرهٔ import پروژه نباید بشکند).
"""
import asyncio
import json
import json as _json
import logging
import sqlite3
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

try:
    import httpx as _httpx
except ImportError:      # httpx در requirements هست؛ این فقط محافظ است
    _httpx = None


# ========================= اتصال به دیتابیس =========================
# اتصال از db.py گرفته می‌شود تا دیتابیس یکپارچه بماند (همان data/bot.db).
# import داخل تابع است تا وابستگی چرخشی db ⇄ ai_brain ایجاد نشود.

def get_conn() -> sqlite3.Connection:
    import db as _db
    return _db.get_conn()


# قفل نوشتن مشترک با db.py — همان شیء، نه یک قفل جدید.
# اگر قفل جدیدی ساخته می‌شد، نوشتن همزمان AI و بقیهٔ جدول‌ها
# دیگر هماهنگ نبود.
class _SharedLock:
    """پراکسی به db._lock — تا زمان استفاده، db لازم نیست بارگذاری شده باشد."""
    def __enter__(self):
        import db as _db
        self._l = _db._lock
        self._l.acquire()
        return self._l

    def __exit__(self, *exc):
        self._l.release()
        return False


_lock = _SharedLock()


# ========================= جدول‌های AI =========================

AI_SCHEMA = """
-- ================= هوش مصنوعی (AI Providers) =================

CREATE TABLE IF NOT EXISTS ai_providers (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    name            TEXT    UNIQUE NOT NULL,
    kind            TEXT    NOT NULL DEFAULT 'openai',   -- openai | cloudflare
    enabled         INTEGER NOT NULL DEFAULT 1,
    api_key         TEXT    NOT NULL DEFAULT '',
    base_url        TEXT    NOT NULL DEFAULT '',
    api_root        TEXT    NOT NULL DEFAULT '',
    timeout         INTEGER NOT NULL DEFAULT 20,
    headers_json    TEXT    NOT NULL DEFAULT '{}',
    fallback_json   TEXT    NOT NULL DEFAULT '[]',
    models_json     TEXT    NOT NULL DEFAULT '[]',
    selected_model  TEXT    NOT NULL DEFAULT '',
    is_iranian      INTEGER NOT NULL DEFAULT 0,          -- برای اولویت‌بندی در ask_ai_fast
    last_status     TEXT    NOT NULL DEFAULT '',
    last_error      TEXT    NOT NULL DEFAULT '',
    last_checked_at TEXT    NOT NULL DEFAULT ''
);
CREATE INDEX IF NOT EXISTS idx_ai_providers_name ON ai_providers(name);

CREATE TABLE IF NOT EXISTS ai_checks_log (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    provider_name TEXT    NOT NULL,
    status        TEXT    NOT NULL,
    error_text    TEXT    NOT NULL DEFAULT '',
    checked_at    TEXT    NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_ai_checks_log_provider ON ai_checks_log(provider_name);
"""


def init_ai_tables(conn=None) -> None:
    """ساخت جدول‌های ai_providers و ai_checks_log.

    از داخل db.init_db() صدا زده می‌شود. اگر conn داده نشود، از اتصال
    فعال db استفاده می‌کند.
    """
    c = conn if conn is not None else get_conn()
    try:
        c.executescript(AI_SCHEMA)
        c.commit()
    except Exception as e:
        logger.error(f"init_ai_tables خطا: {e}", exc_info=True)


# ========================= توابع دیتابیس پروایدرها =========================

def _ai_now() -> str:
    """زمان فعلی به فرمت استاندارد UTC برای ثبت بررسی‌ها."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")


def get_ai_provider(name: str):
    """یک پروایدر بر اساس نام (یا None)."""
    conn = get_conn()
    try:
        return conn.execute(
            "SELECT * FROM ai_providers WHERE name = ?", (name,)
        ).fetchone()
    except Exception as e:
        logger.error(f"get_ai_provider({name}): {e}")
        return None


def list_ai_providers(only_enabled: bool = False) -> list:
    """فهرست همهٔ پروایدرها (یا فقط فعال‌ها)."""
    conn = get_conn()
    sql = "SELECT * FROM ai_providers"
    if only_enabled:
        sql += " WHERE enabled = 1"
    sql += " ORDER BY id"
    try:
        return conn.execute(sql).fetchall()
    except Exception as e:
        logger.error(f"list_ai_providers: {e}")
        return []


def add_ai_provider(name: str, kind: str = "openai", api_key: str = "",
                    base_url: str = "", api_root: str = "", timeout: int = 20,
                    headers_json: str = "{}", fallback_json: str = "[]",
                    is_iranian: bool = False, enabled: bool = True,
                    replace: bool = False) -> bool:
    """
    افزودن پروایدر جدید.
    replace=False → اگر نام تکراری بود کاری نمی‌کند (ON CONFLICT DO NOTHING).
    replace=True → رکورد هم‌نام به‌روزرسانی می‌شود (ON CONFLICT(name) DO UPDATE).
    """
    conn = get_conn()
    _cols_vals = """INSERT INTO ai_providers
                        (name, kind, enabled, api_key, base_url, api_root,
                         timeout, headers_json, fallback_json, is_iranian)
                        VALUES (?,?,?,?,?,?,?,?,?,?)"""
    _upsert = """ ON CONFLICT(name) DO UPDATE SET kind=excluded.kind, enabled=excluded.enabled,
                        api_key=excluded.api_key, base_url=excluded.base_url, api_root=excluded.api_root,
                        timeout=excluded.timeout, headers_json=excluded.headers_json,
                        fallback_json=excluded.fallback_json, is_iranian=excluded.is_iranian"""
    sql = _cols_vals + (_upsert if replace else " ON CONFLICT DO NOTHING")
    try:
        with _lock:
            with conn:
                cur = conn.execute(sql,
                    (name, kind, 1 if enabled else 0, api_key, base_url, api_root,
                     int(timeout), headers_json, fallback_json, 1 if is_iranian else 0),
                )
        return cur.rowcount > 0
    except Exception as e:
        logger.error(f"add_ai_provider({name}): {e}")
        return False


def delete_ai_provider(name: str) -> bool:
    conn = get_conn()
    try:
        with _lock:
            with conn:
                cur = conn.execute("DELETE FROM ai_providers WHERE name = ?", (name,))
        return cur.rowcount > 0
    except Exception as e:
        logger.error(f"delete_ai_provider({name}): {e}")
        return False


def toggle_ai_provider(name: str):
    """فعال/غیرفعال کردن — خروجی: وضعیت جدید (bool) یا None اگر پیدا نشد."""
    conn = get_conn()
    try:
        row = conn.execute(
            "SELECT enabled FROM ai_providers WHERE name = ?", (name,)
        ).fetchone()
        if row is None:
            return None
        new_val = 0 if row["enabled"] else 1
        with _lock:
            with conn:
                conn.execute(
                    "UPDATE ai_providers SET enabled = ? WHERE name = ?", (new_val, name)
                )
        return bool(new_val)
    except Exception as e:
        logger.error(f"toggle_ai_provider({name}): {e}")
        return None


# ستون‌هایی که ادمین اجازهٔ ویرایششان را دارد (جلوگیری از SQL injection)
_AI_EDITABLE = {
    "api_key":  "api_key",
    "base_url": "base_url",
    "api_root": "api_root",
    "timeout":  "timeout",
    "headers":  "headers_json",
    "fallback": "fallback_json",
}


def update_ai_provider_field(name: str, field: str, value) -> bool:
    """به‌روزرسانی یک فیلد مجاز از پروایدر."""
    col = _AI_EDITABLE.get(field)
    if not col:
        logger.warning(f"update_ai_provider_field: فیلد نامعتبر {field!r}")
        return False
    conn = get_conn()
    try:
        with _lock:
            with conn:
                cur = conn.execute(
                    f"UPDATE ai_providers SET {col} = ? WHERE name = ?", (value, name)
                )
        return cur.rowcount > 0
    except Exception as e:
        logger.error(f"update_ai_provider_field({name}.{field}): {e}")
        return False


def save_ai_check_result(name: str, status: str, error: str,
                         models: list, selected: str) -> None:
    """ذخیرهٔ نتیجهٔ بررسی پروایدر + ثبت در تاریخچه."""
    now = _ai_now()
    conn = get_conn()
    try:
        with _lock:
            with conn:
                conn.execute(
                    """UPDATE ai_providers
                       SET last_status=?, last_error=?, last_checked_at=?,
                           models_json=?, selected_model=?
                       WHERE name=?""",
                    (status, error, now,
                     json.dumps(models, ensure_ascii=False), selected, name),
                )
                conn.execute(
                    """INSERT INTO ai_checks_log
                       (provider_name, status, error_text, checked_at)
                       VALUES (?,?,?,?)""",
                    (name, status, error, now),
                )
                # فقط ۱۰۰ رکورد آخر نگه داشته می‌شود
                conn.execute(
                    """DELETE FROM ai_checks_log WHERE id NOT IN
                       (SELECT id FROM ai_checks_log ORDER BY id DESC LIMIT 100)"""
                )
    except Exception as e:
        logger.error(f"save_ai_check_result({name}): {e}")


def ai_provider_count() -> int:
    conn = get_conn()
    try:
        return conn.execute("SELECT COUNT(*) FROM ai_providers").fetchone()[0]
    except Exception:
        return 0


# ========================= منطق فراخوانی AI =========================
# منطق خالص فراخوانی پروایدرها — هیچ پیامی به کاربر ارسال نمی‌کند.

def _ai_jloads(text, default):
    try:
        return _json.loads(text) if text else default
    except Exception:
        return default


def ai_pick_preferred_model(models: list, fallbacks: list) -> str:
    """
    انتخاب مدل ترجیحی:
      ۱) اگر یکی از fallbackها در فهرست مدل‌ها بود → همان
      ۲) مدل سبک/رایگان (mini, flash, haiku, 8b, ...)
      ۳) در نهایت اولین مدل
    """
    if not models:
        return fallbacks[0] if fallbacks else ""
    model_set = set(models)
    for m in fallbacks:
        if m in model_set:
            return m
    keywords = [":free", "free", "mini", "flash", "haiku", "8b", "small", "nano"]
    scored = []
    for m in models:
        low = m.lower()
        score = sum((100 - i) for i, kw in enumerate(keywords) if kw in low)
        scored.append((score, m))
    scored.sort(reverse=True)
    if scored and scored[0][0] > 0:
        return scored[0][1]
    return models[0]


def _ai_text_openai(raw: dict) -> str:
    choices = raw.get("choices")
    if isinstance(choices, list) and choices:
        content = (choices[0].get("message") or {}).get("content", "")
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            parts = [
                it.get("text", "") for it in content
                if isinstance(it, dict) and it.get("type") == "text"
            ]
            return "\n".join(p for p in parts if p).strip()
    return ""


def _ai_text_cloudflare(raw: dict) -> str:
    result = raw.get("result", {})
    if isinstance(result, dict):
        for k in ("response", "text"):
            if isinstance(result.get(k), str):
                return result[k]
    if isinstance(raw.get("response"), str):
        return raw["response"]
    return ""


def _ai_err(provider, model, error) -> dict:
    return {"ok": False, "provider": provider, "model": model,
            "text": "", "raw": {}, "error": error}


# ---- بررسی سلامت پروایدر ----

async def _ai_check_openai(row) -> dict:
    api_key = (row["api_key"] or "").strip()
    base_url = (row["base_url"] or "").strip().rstrip("/")
    timeout = int(row["timeout"] or 20)
    extra_headers = _ai_jloads(row["headers_json"], {})
    fallback = _ai_jloads(row["fallback_json"], [])

    if not api_key:
        return {"status": "not configured", "error": "API Key ثبت نشده", "models": [], "selected": ""}
    if not base_url:
        return {"status": "not configured", "error": "Base URL ثبت نشده", "models": [], "selected": ""}

    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    headers.update(extra_headers)
    models, selected, status, error = [], "", "error", ""

    async with _httpx.AsyncClient(timeout=timeout) as client:
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

        for model in candidates[:6]:      # حداکثر ۶ مدل امتحان می‌شود
            try:
                resp = await client.post(
                    f"{base_url}/chat/completions", headers=headers,
                    json={"model": model,
                          "messages": [{"role": "user", "content": "Hi"}],
                          "max_tokens": 8, "temperature": 0.2},
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


async def _ai_check_cloudflare(row) -> dict:
    api_key = (row["api_key"] or "").strip()
    api_root = (row["api_root"] or "").strip().rstrip("/")
    timeout = int(row["timeout"] or 20)
    fallback = _ai_jloads(row["fallback_json"], [])

    if not api_key:
        return {"status": "not configured", "error": "API Key ثبت نشده", "models": [], "selected": ""}
    if not api_root:
        return {"status": "not configured", "error": "API Root ثبت نشده", "models": [], "selected": ""}

    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    models, selected, status, error = [], "", "error", ""

    async with _httpx.AsyncClient(timeout=timeout) as client:
        for model in fallback:
            try:
                resp = await client.post(
                    f"{api_root}/{model}", headers=headers,
                    json={"messages": [{"role": "user", "content": "Hi"}], "max_tokens": 8},
                )
                if resp.status_code == 200:
                    raw = resp.json()
                    if raw.get("success", True) is False:
                        errs = raw.get("errors") or []
                        error = str(errs[:1]) if errs else "Cloudflare: success=false"
                        continue
                    selected, models, status, error = model, [model], "ok", ""
                    break
                error = f"HTTP {resp.status_code}: {resp.text[:200]}"
            except Exception as exc:
                error = str(exc)

    if status != "ok" and not error:
        error = "هیچ مدل سالم Cloudflare پیدا نشد"
    return {"status": status, "error": error, "models": models, "selected": selected}


async def check_ai_provider(name: str) -> dict:
    """بررسی سلامت یک پروایدر + ذخیرهٔ نتیجه در دیتابیس."""
    if _httpx is None:
        return {"status": "error", "error": "کتابخانه httpx نصب نیست", "models": [], "selected": ""}
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


async def check_all_ai_providers() -> list:
    """بررسی همزمان همهٔ پروایدرها."""
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


# ---- فراخوانی مدل ----

async def ask_ai(provider_name: str, messages: list, model: str = None,
                 temperature: float = 0.7, max_tokens: int = 1200) -> dict:
    """
    پرسش از یک پروایدر مشخص.
    خروجی: {ok, provider, model, text, raw, error}
    """
    if _httpx is None:
        return _ai_err(provider_name, "", "کتابخانه httpx نصب نیست")

    row = get_ai_provider(provider_name)
    if row is None:
        return _ai_err(provider_name, "", "پروایدر پیدا نشد")
    if not row["enabled"]:
        return _ai_err(provider_name, "", "پروایدر غیرفعال است")

    fallback = _ai_jloads(row["fallback_json"], [])
    use_model = model or row["selected_model"] or (fallback[0] if fallback else "")
    if not use_model:
        return _ai_err(provider_name, "", "مدلی انتخاب نشده — ابتدا پروایدر را بررسی کنید")

    api_key = (row["api_key"] or "").strip()
    if not api_key:
        return _ai_err(provider_name, use_model, "API Key تنظیم نشده")

    timeout = int(row["timeout"] or 20)
    try:
        if row["kind"] == "cloudflare":
            api_root = (row["api_root"] or "").strip().rstrip("/")
            if not api_root:
                return _ai_err(provider_name, use_model, "API Root تنظیم نشده")
            headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
            async with _httpx.AsyncClient(timeout=timeout) as client:
                resp = await client.post(f"{api_root}/{use_model}", headers=headers,
                                         json={"messages": messages, "max_tokens": max_tokens})
            if resp.status_code != 200:
                return _ai_err(provider_name, use_model,
                               f"HTTP {resp.status_code}: {resp.text[:300]}")
            raw = resp.json()
            return {"ok": True, "provider": provider_name, "model": use_model,
                    "text": _ai_text_cloudflare(raw), "raw": raw, "error": ""}

        base_url = (row["base_url"] or "").strip().rstrip("/")
        if not base_url:
            return _ai_err(provider_name, use_model, "Base URL تنظیم نشده")
        headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
        headers.update(_ai_jloads(row["headers_json"], {}))
        async with _httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.post(
                f"{base_url}/chat/completions", headers=headers,
                json={"model": use_model, "messages": messages,
                      "temperature": temperature, "max_tokens": max_tokens},
            )
        if resp.status_code != 200:
            return _ai_err(provider_name, use_model,
                           f"HTTP {resp.status_code}: {resp.text[:300]}")
        raw = resp.json()
        return {"ok": True, "provider": provider_name, "model": use_model,
                "text": _ai_text_openai(raw), "raw": raw, "error": ""}

    except Exception as exc:
        name = type(exc).__name__
        if "Timeout" in name:
            return _ai_err(provider_name, use_model, "Timeout — پروایدر پاسخ نداد")
        return _ai_err(provider_name, use_model, f"{name}: {str(exc)[:200]}")


async def ask_ai_fast(messages: list, model: str = None,
                      temperature: float = 0.7, max_tokens: int = 1200,
                      category: str = "") -> dict:
    """
    پرسش با تلاش خودکار روی پروایدرهای فعال.
    ترتیب: خارجی‌ها اول (سریع‌تر) → ایرانی‌ها (در دسترس‌تر از داخل ایران).
    اولین پاسخ موفق برگردانده می‌شود.
    """
    rows = list_ai_providers(only_enabled=True)
    if not rows:
        return _ai_err("", "", "هیچ پروایدر فعالی وجود ندارد")

    foreign = [r for r in rows if not r["is_iranian"]]
    iranian = [r for r in rows if r["is_iranian"]]

    last_error = "همهٔ پروایدرها خطا دادند"
    for row in foreign + iranian:
        result = await ask_ai(row["name"], messages, model=model,
                              temperature=temperature, max_tokens=max_tokens)
        if result["ok"]:
            return result
        last_error = result["error"]
    return _ai_err("", "", last_error)


# ========================= فهرست export =========================
# نام‌ها عیناً حفظ شده‌اند تا importهای موجود نشکنند.
__all__ = [
    # جدول‌ها
    "init_ai_tables", "AI_SCHEMA",
    # دیتابیس
    "_ai_now", "get_ai_provider", "list_ai_providers", "add_ai_provider",
    "delete_ai_provider", "toggle_ai_provider", "update_ai_provider_field",
    "save_ai_check_result", "ai_provider_count", "_AI_EDITABLE",
    # منطق AI
    "ask_ai", "ask_ai_fast", "check_ai_provider", "check_all_ai_providers",
    "ai_pick_preferred_model",
    "_ai_jloads", "_ai_text_openai", "_ai_text_cloudflare", "_ai_err",
    "_ai_check_openai", "_ai_check_cloudflare",
]
