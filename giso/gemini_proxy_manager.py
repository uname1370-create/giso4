# -*- coding: utf-8 -*-
"""
giso/gemini_proxy_manager.py — مدیریت پروکسی Gemini برای گیسو (ذخیره در giso.db).
"""
import asyncio
import json
import logging
import time
from pathlib import Path

try:
    import httpx as _httpx
except ImportError:
    _httpx = None

logger = logging.getLogger(__name__)

_GISO_DB_PATH = Path(__file__).resolve().parent / "data" / "giso.db"

# منبع پیش‌فرض: v4 با فیلتر کشورهای غیرتحریمی (ایتالیا/فرانسه/کانادا/آمریکا)
# — مطابق آدرس تأییدشدهٔ کارفرما (۱۴۰۵-۰۶-۱۸). در پنل قابل تغییر است.
DEFAULT_PROXY_SOURCE = (
    "https://api.proxyscrape.com/v4/free-proxy-list/get?request=display_proxies"
    "&proxy_format=protocolipport&format=text&protocol=socks5&country=it%2Cfr%2Cca%2Cus"
)

# The check targets Gemini itself and authenticates through a header so the API key
# never appears in URLs/logs. 401/403/429 are failures, not "healthy connectivity".
def _gemini_native_base() -> str:
    """ریشهٔ بومی Gemini: env → حالت «پروکسی فوری» (ورکر) → گوگل."""
    try:
        from giso.config import Config as _Cfg
        root = (getattr(_Cfg, "GEMINI_BASE_URL", "") or "").strip().rstrip("/")
    except Exception:
        root = ""
    if not root and get_mode() == MODE_WORKER:
        root = get_worker_base_url()
    if not root:
        return "https://generativelanguage.googleapis.com"
    for suf in ("/v1beta/openai", "/openai", "/v1beta"):
        if root.endswith(suf):
            return root[: -len(suf)]
    return root


def _test_url() -> str:
    return _gemini_native_base() + "/v1beta/models"
# بودجهٔ زمانی تست (۱۴۰۵-۰۶-۱۹): پروکسی‌های رایگان ۲ تا ۸ ثانیه تأخیر دارند.
# تفکیک اتصال/خواندن: پروکسی مرده در ~۲.۵ ثانیه رد می‌شود نه ۸ ثانیه.
_TEST_TIMEOUT = 6.0       # بودجهٔ خواندن پاسخ برای پروکسی زنده
_TEST_CONNECT_TIMEOUT = 2.5  # مهلت برقراری اتصال — مرده‌ها اینجا سریع می‌افتند
_QUICK_PROBE_TIMEOUT = 2.5   # پروب TCP فاز اول (قبل از هر تست سنگین)

MODE_AUTO = "auto"
MODE_MANUAL = "manual"
MODE_DIRECT = "direct"
# حالت «پروکسی فوری»: بدون پروکسی، مستقیم از ورکر کلودفلر (مورد درخواستی ۱۴۰۵-۰۶-۱۱)
MODE_WORKER = "worker"
DEFAULT_WORKER_URL = "https://sadeghiai.uname1370.workers.dev"
MAX_FETCH = 30  # ۱۴۰۵-۰۶-۱۹: با پروب سریع، کاندید بیشتر تقریباً هزینهٔ زمانی ندارد؛ شانس بالاتر

# ── بهینه‌سازی ۳: فیلتر جغرافیایی ─────────────────────────────────────────────
# گوگل بر اساس IP موقعیت را می‌سنجد؛ کشورهای تحت تحریم مستقیم رد می‌شوند حتی با
# پروکسی خروجیِ آن کشورها. این پروکسی‌ها اصلاً وارد فهرست «سالم» نمی‌شوند.
# تشخیص کشور best-effort است: اگر GeoIP در دسترس نبود، پروکسی رد نمی‌شود (fail-open)
# تا فقط به‌خاطر در دسترس‌نبودن سرویس موقعیت، همه‌چیز مختل نشود.
DENIED_COUNTRIES = {"IR", "RU", "CN", "KP", "SY", "VE", "CU", "BY"}
# مسیرهای سبک تشخیص کشورِ خروجی پروکسی (هر کدام فقط کد کشور برمی‌گردانند).
_GEO_API_URLS = (
    "https://www.cloudflare.com/cdn-cgi/trace",   # خطوط متنی: loc=DE
    "https://ipapi.co/json/",                       # {"country_code":"DE"}
)
_GEO_TIMEOUT = 5.0

# ── بهینه‌سازی ۲: امتیازدهی هوشمند (پایداری ۵۰٪ + سرعت ۳۰٪ + Vision ۲۰٪) ────────
SCORE_W_STABILITY = 0.50
SCORE_W_SPEED = 0.30
SCORE_W_VISION = 0.20
# تأخیر مرجع برای نرمال‌سازی سرعت (میلی‌ثانیه)؛ سریع‌تر = امتیاز بالاتر.
SPEED_REF_MS = 1500
# ۱۴۰۵-۰۶-۱۸: اگر پروکسی در استفادهٔ واقعی این‌قدر شکست پیاپی بخورد،
# برای همیشه از استخر «سالم‌ها» حذف می‌شود (تا رفرش بعدی از منبع).
RUNTIME_EVICT_AFTER = 5


def _fa_num(val):
    s = str(val)
    en = "0123456789"
    fa = "۰۱۲۳۴۵۶۷۸۹"
    return s.translate(str.maketrans(en, fa))


def _get_db():
    from giso.base import get_giso_db_conn
    conn = get_giso_db_conn()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS giso_proxy_settings (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL DEFAULT ''
        )
    """)
    conn.commit()
    return conn


def _get_setting(key: str, default: str = "") -> str:
    try:
        with _get_db() as conn:
            row = conn.execute("SELECT value FROM giso_proxy_settings WHERE key=?", (key,)).fetchone()
            return row["value"] if row else default
    except Exception:
        return default


def _set_setting(key: str, value: str) -> bool:
    try:
        with _get_db() as conn:
            conn.execute(
                "INSERT INTO giso_proxy_settings (key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                (key, str(value))
            )
        return True
    except Exception as e:
        logger.warning(f"giso _set_setting error: {e}")
        return False


def get_mode() -> str:
    m = _get_setting("proxy_mode", MODE_AUTO).strip().lower()
    return m if m in (MODE_AUTO, MODE_MANUAL, MODE_DIRECT, MODE_WORKER) else MODE_AUTO


def set_mode(mode: str) -> bool:
    m = mode.strip().lower()
    if m not in (MODE_AUTO, MODE_MANUAL, MODE_DIRECT, MODE_WORKER):
        m = MODE_AUTO
    return _set_setting("proxy_mode", m)


def mode_label(mode: str = None) -> str:
    m = mode if mode else get_mode()
    if m == MODE_AUTO:
        return "🟢 خودکار (auto)"
    if m == MODE_MANUAL:
        return "🟡 دستی (manual)"
    if m == MODE_WORKER:
        return "⚡ فوری — ورکر کلودفلر (بدون پروکسی)"
    return "⚪️ مستقیم (direct)"


def get_worker_base_url() -> str:
    """آدرس ورکر کلودفلر برای حالت «پروکسی فوری» (پیش‌فرض: ورکر گیسو)."""
    url = _get_setting("worker_base_url", DEFAULT_WORKER_URL).strip().rstrip("/")
    return url or DEFAULT_WORKER_URL


def set_worker_base_url(url: str) -> bool:
    """ذخیرهٔ آدرس ورکر — فقط http/https معتبر پذیرفته می‌شود."""
    try:
        from urllib.parse import urlparse
        u = urlparse((url or "").strip())
        if u.scheme not in ("http", "https") or not u.hostname:
            return False
    except Exception:
        return False
    return bool(_set_setting("worker_base_url", url.strip().rstrip("/")))


# منبع پیش‌فرض قدیمی (v2) — فقط برای مهاجرت خودکار سرورهایی که هرگز
# منبع را شخصی‌سازی نکرده‌اند؛ آدرس سفارشی کارفرما دست‌نخورده می‌ماند.
_LEGACY_DEFAULT_SOURCE = (
    "https://api.proxyscrape.com/v2/?request=displayproxies"
    "&protocol=socks5&timeout=10000&country=all"
)


def get_source_url() -> str:
    url = _get_setting("source_url", DEFAULT_PROXY_SOURCE).strip()
    if not url:
        return DEFAULT_PROXY_SOURCE
    if url == _LEGACY_DEFAULT_SOURCE:
        # مهاجرت یک‌باره: پیش‌فرض قدیمی ذخیره‌شده ← منبع جدید
        _set_setting("source_url", DEFAULT_PROXY_SOURCE)
        return DEFAULT_PROXY_SOURCE
    return url


def set_source_url(url: str) -> bool:
    return _set_setting("source_url", url.strip())


def reset_source_url() -> str:
    set_source_url(DEFAULT_PROXY_SOURCE)
    return DEFAULT_PROXY_SOURCE


def get_manual_proxies() -> list:
    raw = _get_setting("manual_proxies", "[]")
    try:
        data = json.loads(raw)
        return data if isinstance(data, list) else []
    except Exception:
        return []


def set_manual_proxies(items: list) -> int:
    cleaned = []
    for x in items:
        s = str(x).strip()
        if s and s not in cleaned:
            cleaned.append(s)
    _set_setting("manual_proxies", json.dumps(cleaned, ensure_ascii=False))
    return len(cleaned)


def clear_manual_proxies() -> bool:
    return _set_setting("manual_proxies", "[]")


def load_working() -> list:
    raw = _get_setting("working_proxies", "[]")
    try:
        data = json.loads(raw)
        return data if isinstance(data, list) else []
    except Exception:
        return []


def _load_health() -> dict:
    try:
        data = json.loads(_get_setting("proxy_health", "{}"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _mask_proxy(proxy: str | None) -> str:
    """Hide credentials and most of the host in admin/report surfaces."""
    if not proxy:
        return "—"
    try:
        from urllib.parse import urlsplit
        value = proxy if "://" in proxy else "socks5://" + proxy
        parsed = urlsplit(value)
        host = parsed.hostname or ""
        masked_host = (host[:3] + "***" + host[-2:]) if len(host) > 6 else "***"
        return f"{parsed.scheme}://{masked_host}:{parsed.port}" if parsed.port else f"{parsed.scheme}://{masked_host}"
    except Exception:
        return "***"


def _record_health(proxy: str, ok: bool, latency_ms: int, status: int = 0,
                   country: str | None = None, vision_ok: bool | None = None) -> None:
    health = _load_health()
    item = health.get(proxy, {}) if isinstance(health.get(proxy), dict) else {}
    successes = int(item.get("successes", 0)) + (1 if ok else 0)
    failures = int(item.get("failures", 0)) + (0 if ok else 1)
    consecutive = 0 if ok else int(item.get("consecutive_failures", 0)) + 1
    vision_attempts = int(item.get("vision_attempts", 0)) + (1 if vision_ok is not None else 0)
    vision_ok_count = int(item.get("vision_ok", 0)) + (1 if vision_ok is True else 0)
    entry = {"successes": successes, "failures": failures,
             "consecutive_failures": consecutive,
             "latency_ms": latency_ms if ok else int(item.get("latency_ms", 99999)),
             "last_status": int(status), "checked_at": int(time.time()),
             "vision_attempts": vision_attempts, "vision_ok": vision_ok_count}
    if country is not None:
        entry["country"] = str(country).upper()
    elif item.get("country"):
        entry["country"] = item.get("country")
    health[proxy] = entry
    _set_setting("proxy_health", json.dumps(health, ensure_ascii=False))


def _country_denied(code: str) -> bool:
    try:
        return str(code or "").upper() in DENIED_COUNTRIES
    except Exception:
        return False


async def _detect_country(proxy: str) -> str:
    """Best-effort exit-IP country code through the proxy. '' = unknown (fail-open)."""
    cached = _load_health().get(proxy, {}).get("country", "")
    if cached:
        return str(cached).upper()
    if not _httpx or not proxy:
        return ""
    try:
        client_factory = getattr(_httpx, "AsyncClient")
        try:
            _geo_to = _httpx.Timeout(_GEO_TIMEOUT, connect=_TEST_CONNECT_TIMEOUT)
        except Exception:
            _geo_to = _GEO_TIMEOUT
        try:
            client = client_factory(proxy=proxy, timeout=_geo_to)
        except TypeError:
            client = client_factory(proxies=proxy, timeout=_geo_to)
        async with client:
            for url in _GEO_API_URLS:
                try:
                    res = await client.get(url)
                    if res.status_code != 200:
                        continue
                    text = res.text or ""
                    # cloudflare trace: "loc=DE"
                    if "loc=" in text:
                        for line in text.splitlines():
                            if line.startswith("loc="):
                                code = line.split("=", 1)[1].strip().upper()
                                if len(code) == 2:
                                    return code
                    # ipapi.co JSON: {"country_code":"DE"}
                    try:
                        data = res.json()
                        code = str(data.get("country_code") or data.get("country") or "").upper()
                        if len(code) == 2:
                            return code
                    except Exception:
                        pass
                except Exception:
                    continue
    except Exception:
        return ""
    return ""


async def _test_vision_proxy(proxy: str, key: str = "", timeout: float = 5.0) -> bool:
    """Optimization 4: verify the proxy can carry a real Gemini multimodal call.

    Sends a tiny image request to Gemini's generateContent; 200 (or a content-safety
    rejection, which still proves the route reaches Gemini) counts as vision-capable.
    Only ever used for manual proxies (public scraped proxies never carry sensitive
    payloads). Returns False on auth/region/transport failure.
    """
    if not _httpx or not proxy or not key:
        return False
    model = "gemini-1.5-flash"
    url = f"{_gemini_native_base()}/v1beta/models/{model}:generateContent"
    body = {
        "contents": [{"parts": [
            {"text": "What color? One word."},
            {"inline_data": {"mime_type": "image/png",
                             # 1x1 قرمز PNG کوچک (فقط برای اثبات عبور درخواست multimodal)
                             "data": "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="}},
        ]}],
        "generationConfig": {"maxOutputTokens": 8},
    }
    try:
        try:
            client = _httpx.AsyncClient(proxy=proxy, timeout=timeout)
        except TypeError:
            client = _httpx.AsyncClient(proxies=proxy, timeout=timeout)
        async with client:
            res = await client.post(url, headers={"x-goog-api-key": key, "Content-Type": "application/json"}, json=body)
        # 200 = موفق. 400 مربوط به محتوا/ایمنی هم یعنی مسیر به Gemini رسیده (vision مسیر باز است).
        if res.status_code == 200:
            return True
        if res.status_code in (400, 429) and "location" not in (res.text or "").lower():
            return res.status_code == 400 and "BLOCK" in (res.text or "").upper()
        return False
    except Exception:
        return False



def record_runtime_result(proxy: str | None, ok: bool, status: int = 0) -> None:
    """Feed real Gemini text/vision outcomes to ranking and circuit breaker."""
    if proxy:
        current = _load_health().get(proxy, {})
        _record_health(proxy, ok, int(current.get("latency_ms", 99999)), status)
        if ok:
            # A recovered proxy can immediately re-enter the stable sorted list.
            save_working(load_working())
        else:
            # حذف خودکار پروکسی مرده از استخر: اگر در استفادهٔ واقعی پشت‌سرهم
            # شکست خورد، دیگر در لیست «سالم‌ها» نمی‌ماند (با رفرش بعدی از منبع،
            # فقط پروکسی‌های زندهٔ جدید جایگزینش می‌شوند).
            item = _load_health().get(proxy, {})
            if int(item.get("consecutive_failures", 0)) >= RUNTIME_EVICT_AFTER:
                works = load_working()
                alive = [p for p in works if p != proxy]
                if len(alive) != len(works):
                    save_working(alive)
                    logger.info(
                        "giso proxy eviction: پروکسی %s بعد از %d شکست پیاپی از استخر حذف شد",
                        _mask_proxy(proxy), int(item.get("consecutive_failures", 0)))


def _stability(item: dict) -> float:
    total = int(item.get("successes", 0)) + int(item.get("failures", 0))
    if total <= 0:
        return 0.0
    return max(0.0, min(1.0, int(item.get("successes", 0)) / total))


def _speed_score(item: dict) -> float:
    ms = int(item.get("latency_ms", 99999) or 99999)
    if ms >= 99999 or ms <= 0:
        return 0.0
    # سریع‌تر → نزدیک‌تر به ۱؛ در تابع برعکس مرتب می‌شود.
    return max(0.0, min(1.0, 1.0 - (ms / SPEED_REF_MS)))


def _vision_score(item: dict) -> float:
    attempts = int(item.get("vision_attempts", 0))
    ok = int(item.get("vision_ok", 0))
    if attempts <= 0:
        return 0.0  # هنوز تست Vision نشده؛ بهش امتیاز نمی‌دهیم ولی ردش هم نمی‌کنیم
    return max(0.0, min(1.0, ok / attempts))


def proxy_smart_score(proxy: str) -> float:
    """Optimization 2: composite 0..1 — stability 50%, speed 30%, vision 20%.

    Vision only contributes once tested; the other two weights are renormalized so a
    never-vision-tested (but fast & stable) proxy is not unfairly pushed to the bottom.
    """
    item = _load_health().get(proxy, {})
    stab = _stability(item)
    speed = _speed_score(item)
    vis = _vision_score(item)
    if int(item.get("vision_attempts", 0)) > 0:
        return SCORE_W_STABILITY * stab + SCORE_W_SPEED * speed + SCORE_W_VISION * vis
    # بدون داده‌ی Vision: وزن‌ها روی پایداری/سرعت نرمال می‌شوند.
    w_sum = SCORE_W_STABILITY + SCORE_W_SPEED
    return (SCORE_W_STABILITY * stab + SCORE_W_SPEED * speed) / w_sum


def _proxy_score(proxy: str):
    # مرتب‌سازی صعودی: امتیاز بالاتر جلو بیفتد، پس قرینه می‌کنیم و tie-breaker روی تأخیر.
    item = _load_health().get(proxy, {})
    return (-proxy_smart_score(proxy), int(item.get("latency_ms", 99999)))


def save_working(proxies: list):
    cleaned = []
    for x in proxies:
        s = str(x).strip()
        if s and s not in cleaned:
            cleaned.append(s)
    cleaned.sort(key=_proxy_score)
    _set_setting("working_proxies", json.dumps(cleaned, ensure_ascii=False))
    _set_setting("last_checked", time.strftime("%Y-%m-%d %H:%M:%S"))


def get_active_proxy(sensitive: bool = False) -> str | None:
    """Return active proxy; sensitive payloads never use scraped public proxies."""
    mode = get_mode()
    if mode in (MODE_DIRECT, MODE_WORKER):
        return None  # فوری/مستقیم: بدون پروکسی
    health = _load_health()
    now = int(time.time())
    def circuit_open(p):
        item = health.get(p, {})
        return (int(item.get("consecutive_failures", 0)) >= 3 and
                now - int(item.get("checked_at", 0)) < 900)
    def rank(p):
        # ترتیب هوشمند: امتیاز ترکیبی (پایداری/سرعت/vision) و سپس تأخیر.
        return _proxy_score(p)
    manual_healthy = lambda: [p for p in get_manual_proxies() if not circuit_open(p)]
    if sensitive:
        # محتوای حساس/عکس فقط از پروکسی دستی رد می‌شود؛ پروکسی‌ای که تست چندرسانه‌ای آن
        # موفق بوده (vision_ok>0) در اولویت است (بهینه‌سازی ۴).
        mans = manual_healthy()
        vision_ok = [p for p in mans if int(health.get(p, {}).get("vision_ok", 0)) > 0]
        candidates = sorted(vision_ok or mans, key=rank)
        return candidates[0] if candidates else None
    if mode == MODE_MANUAL:
        mans = sorted(manual_healthy(), key=rank)
        return mans[0] if mans else None
    # auto
    w = load_working()
    # Circuit breaker: after three consecutive failures skip the proxy for 15 min.
    available = [p for p in w if not (
        int(health.get(p, {}).get("consecutive_failures", 0)) >= 3 and
        now - int(health.get(p, {}).get("checked_at", 0)) < 900
    )]
    if available:
        return sorted(available, key=rank)[0]
    mans = get_manual_proxies()
    mans = sorted((p for p in mans if not circuit_open(p)), key=rank)
    return mans[0] if mans else None


def _get_all_settings() -> dict:
    out = {}
    try:
        with _get_db() as conn:
            for row in conn.execute("SELECT key, value FROM giso_proxy_settings").fetchall():
                out[row["key"]] = row["value"]
    except Exception:
        pass
    return out


def _gemini_api_key() -> str:
    """Read only Gemini's key; never log or persist a copy in proxy settings."""
    try:
        from giso.ai_brain import get_ai_provider
        row = get_ai_provider("gemini")
        return str(row["api_key"] or "").strip() if row else ""
    except Exception:
        return ""


def _proxy_host_port(proxy: str):
    """استخراج (host, port) از آدرس پروکسی؛ برای پروکسی‌های نامعتبر/IPv6 مبهم → None."""
    try:
        s = str(proxy or "").strip()
        if "://" in s:
            s = s.split("://", 1)[1]
        # حذف کاربر:رمز (user:pass@host:port)
        if "@" in s:
            s = s.rsplit("@", 1)[1]
        s = s.rstrip("/")
        if not s or s.count(":") != 1:
            return None  # IPv6 یا فرمت ناشناخته → پروب نمی‌کنیم، به تست کامل واگذار می‌شود
        host, port = s.split(":", 1)
        return host, int(port)
    except Exception:
        return None


async def _quick_probe(proxy: str, timeout: float = _QUICK_PROBE_TIMEOUT) -> bool:
    """پروب سریع «پینگِ اتصالی»: فقط بازکردن سوکت TCP به خود پروکسی.

    پروکسی مرده اینجا در ~۲ ثانیه رد می‌شود، بدون ساخت کلاینت سنگین و بدون
    درخواست واقعی به جمینای. زنده‌ها به تست کامل (تأیید واقعی) می‌روند.
    """
    hp = _proxy_host_port(proxy)
    if hp is None:
        return True  # قابل پروب نیست؛ اجازه بده تست کامل تصمیم بگیرد
    host, port = hp
    try:
        _reader, writer = await asyncio.wait_for(
            asyncio.open_connection(host, port), timeout=timeout)
        try:
            writer.close()
        except Exception:
            pass
        return True
    except Exception:
        return False


async def _test_single_proxy_detail(proxy: str, timeout: float = _TEST_TIMEOUT) -> tuple:
    """Return (healthy, latency_ms, HTTP status) using authenticated Gemini API."""
    key = _gemini_api_key()
    if not _httpx or not proxy or not key:
        return False, 99999, 0
    t0 = time.time()
    try:
        # تفکیک مهلت اتصال/خواندن: پروکسی مرده در ~۲.۵ ثانیه می‌افتد، نه ۸ ثانیه.
        try:
            _to = _httpx.Timeout(timeout, connect=_TEST_CONNECT_TIMEOUT)
        except Exception:
            _to = timeout
        try:
            client = _httpx.AsyncClient(proxy=proxy, timeout=_to)
        except TypeError:
            client = _httpx.AsyncClient(proxies=proxy, timeout=_to)
        async with client:
            res = await client.get(_test_url(), headers={"x-goog-api-key": key})
            ms = int((time.time() - t0) * 1000)
            # Only a successful authenticated response proves this route is usable.
            return res.status_code == 200, ms, int(res.status_code)
    except Exception:
        return False, 99999, 0


async def _test_single_proxy_ms(proxy: str, timeout: float = _TEST_TIMEOUT) -> tuple:
    ok, ms, status = await _test_single_proxy_detail(proxy, timeout)
    _record_health(proxy, ok, ms, status)
    return ok, ms


async def _vet_proxy(proxy: str, is_manual: bool, run_vision: bool = False) -> tuple:
    """Full vetting for a candidate proxy.

    Returns (usable, latency_ms, is_manual):
      - connectivity test against the authenticated Gemini endpoint (reject 401/403/429);
      - Optimization 3: drop exit nodes in DENIED_COUNTRIES (best-effort, fail-open);
      - Optimization 4: for MANUAL proxies, run a tiny multimodal call and record vision_ok.
    """
    # فاز ۱ — پروب سریع: پروکسی‌ای که اصلاً سوکتش باز نمی‌شود، اینجا در ~۲ ثانیه
    # رد می‌شود و هرگز وارد تست سنگین جمینای نمی‌شود (سرعت کل چک را چند برابر می‌کند).
    if not await _quick_probe(proxy):
        _record_health(proxy, False, 99999, 0)
        return False, 99999, is_manual
    # فاز ۲ — تست کامل: اتصال واقعی به جمینای + تشخیص کشور (هم‌زمان).
    _conn_task = asyncio.ensure_future(_test_single_proxy_detail(proxy, _TEST_TIMEOUT))
    _geo_task = asyncio.ensure_future(_detect_country(proxy))
    ok, ms, status = await _conn_task
    if not ok:
        # اتصال شکست خورد؛ منتظر تشخیص کشور نمان و تسک آن را لغو کن.
        _geo_task.cancel()
        _record_health(proxy, False, ms, status)
        return False, ms, is_manual
    try:
        country = await _geo_task
    except Exception:
        country = ""
    vision_ok = None
    if is_manual and run_vision:
        try:
            vision_ok = await _test_vision_proxy(proxy, _gemini_api_key())
        except Exception:
            vision_ok = None
    # کشور مردود → پروکسی قابل استفاده نیست (ولی اگر تشخیص ناموفق بود رد نمی‌کنیم).
    if country and _country_denied(country):
        _record_health(proxy, False, ms, status, country=country, vision_ok=vision_ok)
        return False, ms, is_manual
    _record_health(proxy, True, ms, status, country=country or None, vision_ok=vision_ok)
    return True, ms, is_manual


async def refresh_from_source(url: str = None, on_progress=None, limit: int = MAX_FETCH) -> tuple:
    if not _httpx:
        return [], {"total": 0, "healthy": 0, "failed": 0, "manual_healthy": 0, "manual_total": 0,
                    "online_healthy": 0, "online_total": 0, "fastest": "—", "duration": 0.0,
                    "error": "httpx نصب نیست"}
    src = url or get_source_url()
    t0 = time.time()
    raw_list = []
    try:
        async with _httpx.AsyncClient(timeout=12.0) as client:
            resp = await client.get(src)
            if resp.status_code == 200:
                for line in resp.text.splitlines():
                    p = line.strip()
                    if not p or ":" not in p or p in raw_list:
                        continue
                    # خطوط نامعتبر (مثل پیام خطا یا متن تبلیغاتی) را کنار بگذار
                    if not any(ch.isdigit() for ch in p):
                        continue
                    if not p.startswith("http") and not p.startswith("socks"):
                        p = "socks5://" + p
                    raw_list.append(p)
    except Exception as e:
        logger.warning(f"giso refresh_from_source fetch error: {e}")

    mans = get_manual_proxies()
    # ترتیب تصادفی: در لیست‌های رایگان همیشه اول همان پروکسی‌های مرده نمی‌آیند
    import random as _random
    _random.shuffle(raw_list)
    online_cands = raw_list[:limit]

    all_cands = []
    is_man_map = {}
    for p in mans:
        all_cands.append(p)
        is_man_map[p] = True
    for p in online_cands:
        if p not in is_man_map:
            all_cands.append(p)
            is_man_map[p] = False

    total = len(all_cands)
    working = []
    man_h, on_h = 0, 0
    fastest_str = "—"
    min_ms = 99999

    sem = asyncio.Semaphore(20)

    async def _check_item(idx, proxy):
        async with sem:
            # تست یکپارچه: اتصال واقعی + فیلتر کشور + (برای پروکسی دستی) تست Vision.
            ok, ms, is_man = await _vet_proxy(proxy, is_man_map[proxy], run_vision=True)
            if on_progress:
                try:
                    await on_progress(idx, total)
                except Exception:
                    pass
            return proxy, ok, ms, is_man

    if all_cands:
        tasks = [_check_item(i, p) for i, p in enumerate(all_cands, 1)]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        for res in results:
            if isinstance(res, tuple) and len(res) == 4:
                p, ok, ms, is_man = res
                if ok:
                    working.append((ms, p))
                    if is_man:
                        man_h += 1
                    else:
                        on_h += 1
                    if ms < min_ms:
                        min_ms = ms
                        fastest_str = f"{_mask_proxy(p)} ({ms}ms)"

    # سریع‌ترین اول → همان به‌عنوان پروکسی فعال انتخاب می‌شود.
    working.sort(key=lambda x: x[0])
    working = [p for _ms, p in working]
    save_working(working)
    dur = round(time.time() - t0, 1)
    report = {
        "total": total,
        "healthy": len(working),
        "failed": total - len(working),
        "manual_total": len(mans),
        "manual_healthy": man_h,
        "online_total": len([p for p in all_cands if not is_man_map[p]]),
        "online_healthy": on_h,
        "fastest": fastest_str,
        "duration": dur,
        "error": ("API Key پروایدر Gemini ثبت نشده" if not _gemini_api_key()
                  else ("" if raw_list else "پروکسی از منبع دریافت نشد"))
    }
    return working, report


async def revalidate(on_progress=None) -> tuple:
    mans = get_manual_proxies()
    works = load_working()
    t0 = time.time()
    all_cands = []
    is_man_map = {}
    for p in mans:
        all_cands.append(p)
        is_man_map[p] = True
    for p in works:
        if p not in is_man_map:
            all_cands.append(p)
            is_man_map[p] = False

    total = len(all_cands)
    working = []
    man_h, on_h = 0, 0
    fastest_str = "—"
    min_ms = 99999
    sem = asyncio.Semaphore(20)  # ۱۴۰۵-۰۶-۱۹: بازبینی هم موازی کامل انجام شود

    async def _check_item(idx, proxy):
        async with sem:
            # تست یکپارچه: اتصال واقعی + فیلتر کشور + (برای پروکسی دستی) تست Vision.
            ok, ms, is_man = await _vet_proxy(proxy, is_man_map[proxy], run_vision=True)
            if on_progress:
                try:
                    await on_progress(idx, total)
                except Exception:
                    pass
            return proxy, ok, ms, is_man

    if all_cands:
        tasks = [_check_item(i, p) for i, p in enumerate(all_cands, 1)]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        for res in results:
            if isinstance(res, tuple) and len(res) == 4:
                p, ok, ms, is_man = res
                if ok:
                    working.append((ms, p))
                    if is_man:
                        man_h += 1
                    else:
                        on_h += 1
                    if ms < min_ms:
                        min_ms = ms
                        fastest_str = f"{_mask_proxy(p)} ({ms}ms)"

    # سریع‌ترین اول → همان به‌عنوان پروکسی فعال انتخاب می‌شود.
    working.sort(key=lambda x: x[0])
    working = [p for _ms, p in working]
    save_working(working)
    dur = round(time.time() - t0, 1)
    report = {
        "total": total,
        "healthy": len(working),
        "failed": total - len(working),
        "manual_total": len(mans),
        "manual_healthy": man_h,
        "online_total": len([p for p in all_cands if not is_man_map[p]]),
        "online_healthy": on_h,
        "fastest": fastest_str,
        "duration": dur,
        "error": "" if _gemini_api_key() else "API Key پروایدر Gemini ثبت نشده"
    }
    return working, report


def format_test_report(rep: dict, source_label: str = "دریافت‌شده") -> str:
    err = rep.get("error", "")
    err_line = f"\n⚠️ خطا: {err}" if err else ""
    fastest = rep.get("fastest", "—")
    man_h = rep.get("manual_healthy", 0)
    man_t = rep.get("manual_total", 0)
    on_h = rep.get("online_healthy", 0)
    on_t = rep.get("online_total", 0)
    dur = rep.get("duration", 0)
    return (
        "✅ نتیجه تست\n\n"
        f"📊 دستی: {_fa_num(man_h)} از {_fa_num(man_t)} سالم\n"
        f"📊 آنلاین: {_fa_num(on_h)} از {_fa_num(on_t)} سالم\n"
        f"⚡️ سریع‌ترین: {fastest}\n"
        f"🕒 مدت زمان: {_fa_num(dur)} ثانیه{err_line}"
    )


def status_summary() -> dict:
    s = _get_all_settings()
    mode = s.get("proxy_mode", MODE_AUTO).strip().lower()
    if mode not in (MODE_AUTO, MODE_MANUAL, MODE_DIRECT, MODE_WORKER):
        mode = MODE_AUTO
    mans = []
    works = []
    try:
        mans = json.loads(s.get("manual_proxies", "[]"))
    except Exception:
        pass
    try:
        works = json.loads(s.get("working_proxies", "[]"))
    except Exception:
        pass
    active = get_active_proxy()
    last_chk = s.get("last_checked", "—")
    src = s.get("source_url", DEFAULT_PROXY_SOURCE) or DEFAULT_PROXY_SOURCE
    try:
        from urllib.parse import urlsplit, urlunsplit
        parsed = urlsplit(src)
        # Never expose source credentials or query tokens in bot status.
        safe_source = urlunsplit((parsed.scheme, parsed.hostname or "", parsed.path, "", ""))
    except Exception:
        safe_source = "—"
    return {
        "mode": mode,
        "mode_label": mode_label(mode),
        "is_worker": mode == MODE_WORKER,
        "worker_url": get_worker_base_url() if mode == MODE_WORKER else "",
        "source_url": safe_source,
        "working_count": len(works),
        "manual_count": len(mans),
        "active_proxy": _mask_proxy(active),
        "last_checked": last_chk
    }


__all__ = [
    "get_mode", "set_mode", "mode_label", "get_worker_base_url", "set_worker_base_url", "MODE_WORKER",
    "get_source_url", "set_source_url", "reset_source_url",
    "get_manual_proxies", "set_manual_proxies", "clear_manual_proxies",
    "load_working", "save_working", "get_active_proxy",
    "refresh_from_source", "revalidate",
    "format_test_report", "status_summary", "record_runtime_result",
    "proxy_smart_score", "DENIED_COUNTRIES",
    "_detect_country", "_test_vision_proxy", "_vet_proxy",
]
