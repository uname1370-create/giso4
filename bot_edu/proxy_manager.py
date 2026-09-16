"""
proxy_manager.py — مدیریت لیست پروکسی برای اتصال تلگرام

وابستگی مجاز: config و stdlib + httpx
هرگز از core / ui / handlers import نکنید (زنجیره import را نشکنید).

قابلیت‌ها:
  • دریافت خودکار لیست پروکسی از ProxyScrape (یا هر URL دلخواه)
  • تست همزمان (concurrent) پروکسی‌ها روی api.telegram.org
  • ذخیره سالم‌ها در data/working_proxies.txt
  • کش هوشمند در data/proxy_cache.json (اعتبار ۶ ساعت)
  • پروکسی‌های دستی ادمین
  • سه حالت اتصال: خودکار / دستی / مستقیم
"""
import asyncio
import json
import logging
import os
import re
import time

import httpx

from config import SETTINGS, save, DB_PATH

logger = logging.getLogger(__name__)

# ========================= ثابت‌ها =========================

# URL پیش‌فرض منبع پروکسی (قابل تغییر از پنل ادمین)
DEFAULT_PROXY_SOURCE = (
    "https://api.proxyscrape.com/v2/?request=displayproxies"
    "&protocol=socks5&timeout=10000&country=all"
)

# آدرسی که برای تست سلامت پروکسی صدا زده می‌شود
_TEST_URL = "https://api.telegram.org"

# اعتبار کش (ثانیه) — ۶ ساعت
CACHE_TTL = 6 * 3600

# سقف تست همزمان (برای جلوگیری از فشار روی شبکه)
_MAX_CONCURRENCY = 20

# مهلت هر تست (ثانیه)
_TEST_TIMEOUT = 8.0

# [کار ۱] حداکثر پروکسی که از منبع دریافت و تست می‌شود.
# قبلاً ۳۰۰ بود که تست آن بسیار زمان‌بر می‌شد.
MAX_FETCH = 10

# حداقل پروکسی سالم برای اینکه نتیجه «قابل قبول» تلقی شود
MIN_HEALTHY = 3

# [کار ۱] حداکثر پروکسی دستی (از ۱۰ به ۲۰ افزایش یافت)
MAX_MANUAL = 20

# حالت‌های اتصال
MODE_AUTO = "auto"      # 🟢 خودکار — از لیست پروکسی
MODE_MANUAL = "manual"  # 🟡 دستی — فقط پروکسی‌های دستی
MODE_DIRECT = "direct"  # 🔴 مستقیم — بدون پروکسی

MODE_LABELS = {
    MODE_AUTO:   "🟢 خودکار",
    MODE_MANUAL: "🟡 دستی",
    MODE_DIRECT: "🔴 مستقیم",
}


# ========================= مسیر فایل‌ها =========================

def _data_dir() -> str:
    """پوشهٔ data کنار دیتابیس."""
    d = os.path.dirname(DB_PATH) or "data"
    os.makedirs(d, exist_ok=True)
    return d


def working_file() -> str:
    return os.path.join(_data_dir(), "working_proxies.txt")


def cache_file() -> str:
    return os.path.join(_data_dir(), "proxy_cache.json")


# ========================= تنظیمات (دیتابیس) =========================

def get_source_url() -> str:
    """URL منبع پروکسی (از دیتابیس یا پیش‌فرض)."""
    return str(SETTINGS.get("proxy_source_url", "") or "").strip() or DEFAULT_PROXY_SOURCE


def set_source_url(url: str):
    SETTINGS["proxy_source_url"] = (url or "").strip()
    save("settings")


def reset_source_url():
    SETTINGS["proxy_source_url"] = ""
    save("settings")


def get_mode() -> str:
    """حالت اتصال فعلی."""
    m = str(SETTINGS.get("telegram_conn_mode", "") or "").strip()
    return m if m in (MODE_AUTO, MODE_MANUAL, MODE_DIRECT) else MODE_AUTO


def set_mode(mode: str):
    if mode in (MODE_AUTO, MODE_MANUAL, MODE_DIRECT):
        SETTINGS["telegram_conn_mode"] = mode
        save("settings")


def mode_label(mode: str = None) -> str:
    return MODE_LABELS.get(mode or get_mode(), "🟢 خودکار")


def get_manual_proxies() -> list:
    """پروکسی‌های دستی ثبت‌شده توسط ادمین."""
    raw = str(SETTINGS.get("manual_proxies", "") or "")
    return [p.strip() for p in raw.split(",") if p.strip()]


def set_manual_proxies(items: list):
    clean = []
    for p in items[:MAX_MANUAL]:
        n = normalize_proxy(p)
        if n and n not in clean:
            clean.append(n)
    SETTINGS["manual_proxies"] = ",".join(clean)
    save("settings")
    return clean


def clear_manual_proxies():
    SETTINGS["manual_proxies"] = ""
    save("settings")


# ========================= نرمال‌سازی =========================

_PROXY_RE = re.compile(
    r"^(?:(?P<scheme>socks5|socks5h|http|https)://)?"
    r"(?:(?P<user>[^:@/]+):(?P<pw>[^@/]+)@)?"
    r"(?P<host>[A-Za-z0-9_.\-]+):(?P<port>\d{2,5})/?$"
)


def normalize_proxy(raw: str) -> str:
    """
    نرمال‌سازی رشتهٔ پروکسی به فرمت کامل.
    ورودی‌های مجاز: ip:port | socks5://ip:port | http://user:pass@ip:port
    خروجی: رشتهٔ کامل با scheme — یا "" اگر نامعتبر باشد.
    """
    s = (raw or "").strip()
    if not s:
        return ""
    m = _PROXY_RE.match(s)
    if not m:
        return ""
    scheme = m.group("scheme") or "socks5"   # پیش‌فرض ProxyScrape = socks5
    host = m.group("host")
    port = m.group("port")
    try:
        if not (0 < int(port) < 65536):
            return ""
    except ValueError:
        return ""
    user, pw = m.group("user"), m.group("pw")
    auth = f"{user}:{pw}@" if user and pw else ""
    return f"{scheme}://{auth}{host}:{port}"


# ========================= کش =========================

def _read_cache() -> dict:
    try:
        with open(cache_file(), encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _write_cache(data: dict):
    try:
        with open(cache_file(), "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.warning(f"نوشتن کش پروکسی ناموفق: {e}")


def cache_age() -> int:
    """سن کش به ثانیه (اگر کش نباشد عدد بسیار بزرگ برمی‌گرداند)."""
    ts = int(_read_cache().get("updated_at", 0) or 0)
    if ts <= 0:
        return 10 ** 9
    return max(0, int(time.time()) - ts)


def cache_is_fresh() -> bool:
    """[کش هوشمند] آیا لیست کمتر از ۶ ساعت قدیمی است؟"""
    return cache_age() < CACHE_TTL


def age_text() -> str:
    """سن کش به فارسی خوانا."""
    a = cache_age()
    if a >= 10 ** 8:
        return "هرگز"
    if a < 60:
        return "همین الان"
    if a < 3600:
        return f"{a // 60} دقیقه پیش"
    if a < 86400:
        return f"{a // 3600} ساعت پیش"
    return f"{a // 86400} روز پیش"


# ========================= فایل پروکسی‌های سالم =========================

def load_working() -> list:
    """خواندن پروکسی‌های سالم از فایل."""
    try:
        with open(working_file(), encoding="utf-8") as f:
            return [ln.strip() for ln in f if ln.strip() and not ln.startswith("#")]
    except FileNotFoundError:
        return []
    except Exception as e:
        logger.warning(f"خواندن working_proxies.txt ناموفق: {e}")
        return []


def save_working(proxies: list):
    """ذخیرهٔ پروکسی‌های سالم + به‌روزرسانی کش."""
    try:
        with open(working_file(), "w", encoding="utf-8") as f:
            f.write("# پروکسی‌های سالم — تولیدشده توسط proxy_manager\n")
            f.write(f"# آخرین به‌روزرسانی: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
            for p in proxies:
                f.write(p + "\n")
    except Exception as e:
        logger.error(f"نوشتن working_proxies.txt ناموفق: {e}")
        return
    _write_cache({
        "updated_at": int(time.time()),
        "count": len(proxies),
        "source": get_source_url(),
    })


def clear_working():
    """[🗑️ حذف لیست] پاک کردن همهٔ پروکسی‌های ذخیره‌شده."""
    for path in (working_file(), cache_file()):
        try:
            if os.path.exists(path):
                os.remove(path)
        except Exception as e:
            logger.warning(f"حذف {path} ناموفق: {e}")


def working_count() -> int:
    return len(load_working())


# ========================= دریافت از منبع =========================

async def fetch_from_source(url: str = None, limit: int = None) -> tuple:
    """
    [📥 دریافت خودکار] گرفتن لیست خام پروکسی از URL.
    [کار ۱] فقط `limit` مورد اول برداشته می‌شود (پیش‌فرض MAX_FETCH = ۱۰).
    خروجی: (list, error_message)
    """
    cap = MAX_FETCH if limit is None else max(1, int(limit))
    src = (url or get_source_url()).strip()
    if not src:
        return [], "URL منبع تنظیم نشده است."
    try:
        async with httpx.AsyncClient(timeout=25.0, follow_redirects=True) as cl:
            r = await cl.get(src)
            r.raise_for_status()
            text = r.text
    except Exception as e:
        logger.error(f"دریافت لیست پروکسی ناموفق: {e}")
        return [], f"دریافت از منبع ناموفق بود: {type(e).__name__}"

    out, seen = [], set()
    for line in text.splitlines():
        n = normalize_proxy(line)
        if n and n not in seen:
            seen.add(n)
            out.append(n)
        if len(out) >= cap:
            break
    if not out:
        return [], "منبع پاسخ داد ولی هیچ پروکسی معتبری در آن نبود."
    return out, ""


# ========================= تست پروکسی =========================

def _client_with_proxy(proxy: str, timeout: float):
    """
    ساخت AsyncClient با پروکسی — سازگار با هر دو نسخهٔ httpx.
    httpx < 0.26 پارامتر `proxies` دارد و ≥ 0.26 پارامتر `proxy`.
    """
    try:
        return httpx.AsyncClient(proxy=proxy, timeout=timeout)
    except TypeError:
        return httpx.AsyncClient(proxies=proxy, timeout=timeout)


class ProxyTestError(Exception):
    """خطای پیکربندی (مثل نبود socksio) — با خطای شبکه فرق دارد."""


async def test_proxy_timed(proxy: str, timeout: float = _TEST_TIMEOUT) -> tuple:
    """
    تست یک پروکسی روی api.telegram.org به‌همراه اندازه‌گیری زمان پاسخ.
    خروجی: (ok: bool, ms: int, error: str)
      • ms = زمان پاسخ به میلی‌ثانیه (اگر ناموفق: 0)
      • error = علت شکست ("" اگر موفق)
    """
    t0 = time.monotonic()
    try:
        async with _client_with_proxy(proxy, timeout) as cl:
            r = await cl.get(_TEST_URL)
            ms = int((time.monotonic() - t0) * 1000)
            if r.status_code < 500:
                return True, ms, ""
            return False, ms, f"HTTP {r.status_code}"
    except ImportError as e:
        # [باگ ۱] نبود socksio → خطای پیکربندی، نه شبکه
        raise ProxyTestError(str(e)) from e
    except Exception as e:
        return False, 0, type(e).__name__


async def test_proxy(proxy: str, timeout: float = _TEST_TIMEOUT) -> bool:
    """تست ساده (سازگاری با کد قبلی)."""
    try:
        ok, _ms, _err = await test_proxy_timed(proxy, timeout)
        return ok
    except ProxyTestError:
        return False


async def test_many(proxies: list, on_progress=None) -> list:
    """تست همزمان — خروجی: فقط لیست سالم‌ها (سازگاری با کد قبلی)."""
    rep = await test_many_report(proxies, on_progress=on_progress)
    return rep["alive"]


async def test_many_report(proxies: list, on_progress=None) -> dict:
    """
    [کار ۱] تست همزمان با گزارش کامل.

    خروجی dict:
      total    : تعداد تست‌شده
      alive    : لیست سالم‌ها (مرتب از سریع‌ترین)
      dead     : تعداد مرده‌ها
      timings  : {proxy: ms}
      fastest  : (proxy, ms) یا None
      config_error : متن خطای پیکربندی (مثل نبود socksio) یا ""
    """
    empty = {"total": 0, "alive": [], "dead": 0, "timings": {},
             "fastest": None, "config_error": ""}
    if not proxies:
        return empty

    sem = asyncio.Semaphore(_MAX_CONCURRENCY)
    timings, done = {}, 0
    total = len(proxies)
    lock = asyncio.Lock()
    config_error = ""

    async def one(p):
        nonlocal done, config_error
        ok, ms = False, 0
        try:
            async with sem:
                ok, ms, _err = await test_proxy_timed(p)
        except ProxyTestError as e:
            async with lock:
                if not config_error:
                    config_error = str(e)
        async with lock:
            done += 1
            if ok:
                timings[p] = ms
            if on_progress:
                try:
                    await on_progress(done, total, len(timings))
                except Exception:
                    pass

    await asyncio.gather(*(one(p) for p in proxies), return_exceptions=True)

    # سریع‌ترین اول
    ordered = sorted(timings.items(), key=lambda kv: kv[1])
    alive = [p for p, _ in ordered]
    return {
        "total": total,
        "alive": alive,
        "dead": total - len(alive),
        "timings": timings,
        "fastest": (ordered[0] if ordered else None),
        "config_error": config_error,
    }


async def refresh_from_source(url: str = None, on_progress=None, limit: int = None) -> tuple:
    """
    [📥 دریافت + تست + ذخیره] چرخهٔ کامل — حداکثر MAX_FETCH مورد.
    خروجی: (report_dict, error_message)
    """
    raw, err = await fetch_from_source(url, limit=limit)
    if err:
        return None, err
    rep = await test_many_report(raw, on_progress=on_progress)
    save_working(rep["alive"])
    logger.info("📥 لیست پروکسی به‌روز شد: %d سالم از %d دریافتی",
                len(rep["alive"]), rep["total"])
    return rep, ""


async def revalidate(on_progress=None) -> tuple:
    """
    [🔄 آپدیت همزمان] تست دوبارهٔ پروکسی‌های ذخیره‌شده و حذف مرده‌ها.
    خروجی: (report_dict, error_message)
    """
    current = load_working()
    if not current:
        return None, "هیچ پروکسی ذخیره‌شده‌ای وجود ندارد."
    rep = await test_many_report(current, on_progress=on_progress)
    save_working(rep["alive"])
    logger.info("🔄 بازبینی پروکسی: %d سالم، %d حذف شد", len(rep["alive"]), rep["dead"])
    return rep, ""


async def test_manual_proxies(on_progress=None) -> tuple:
    """
    [کار ۱ — «🧪 تست همین پروکسی‌ها»] تست فقط پروکسی‌های دستیِ ادمین.
    سالم‌ها به لیست ذخیره‌شده اضافه و مرده‌ها از فهرست دستی حذف می‌شوند.
    خروجی: (report_dict, error_message)
    """
    manual = get_manual_proxies()
    if not manual:
        return None, "هیچ پروکسی دستی‌ای ثبت نشده است."
    rep = await test_many_report(manual, on_progress=on_progress)

    # فقط سالم‌ها در فهرست دستی باقی می‌مانند
    set_manual_proxies(rep["alive"])

    # سالم‌ها به لیست کلی هم اضافه شوند (بدون تکرار)
    merged = list(rep["alive"])
    for p in load_working():
        if p not in merged:
            merged.append(p)
    save_working(merged)

    logger.info("🧪 تست پروکسی دستی: %d سالم از %d", len(rep["alive"]), rep["total"])
    return rep, ""


def format_test_report(rep: dict, source_label: str = "دریافت‌شده") -> str:
    """
    [کار ۱ — بند ۳] گزارش خلاصهٔ نتیجهٔ تست برای نمایش به ادمین.
    """
    if not rep:
        return "❌ گزارشی در دسترس نیست."

    total, alive, dead = rep["total"], rep["alive"], rep["dead"]
    lines = [
        "📊 گزارش تست پروکسی",
        "━━━━━━━━━━━━━━━━",
        f"📥 {source_label}: {total} پروکسی",
        f"✅ سالم: {len(alive)}",
        f"❌ مرده: {dead}",
    ]

    fastest = rep.get("fastest")
    if fastest:
        lines.append(f"⚡️ سریع‌ترین: {fastest[0]}  ({fastest[1]} میلی‌ثانیه)")

    lines.append(f"🕒 آخرین آپدیت: {age_text()}")

    if rep.get("config_error"):
        lines += [
            "",
            "🔴 خطای پیکربندی:",
            "بستهٔ socksio نصب نیست، پس پروکسی‌های socks5 قابل تست نیستند.",
            "راه‌حل:  pip install \"httpx[socks]\"",
        ]
    elif len(alive) < MIN_HEALTHY:
        lines += [
            "",
            "⚠️ پروکسی سالم کم است.",
            "پیشنهاد: پروکسی دستی وارد کنید یا منبع را تغییر دهید.",
        ]

    return "\n".join(lines)


# ========================= انتخاب پروکسی برای اتصال =========================

def candidates_for_mode() -> list:
    """
    فهرست پروکسی‌هایی که bot.py باید امتحان کند — بر اساس حالت اتصال.
    مقدار None یعنی «اتصال مستقیم».
    """
    mode = get_mode()

    if mode == MODE_DIRECT:
        return [None]

    if mode == MODE_MANUAL:
        out = list(get_manual_proxies())
        out.append(None)  # آخرین تلاش
        return out

    # حالت خودکار: دستی‌ها اول (اولویت ادمین)، بعد لیست سالم، بعد مستقیم
    out = list(get_manual_proxies())
    for p in load_working():
        if p not in out:
            out.append(p)
    out.append(None)
    return out


def status_summary() -> dict:
    """اطلاعات نمایشی برای بالای پنل تلگرام."""
    return {
        "mode": get_mode(),
        "mode_label": mode_label(),
        "working": working_count(),
        "manual": len(get_manual_proxies()),
        "age": age_text(),
        "fresh": cache_is_fresh(),
        "source": get_source_url(),
    }
