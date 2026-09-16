"""
ai_market.py — اسکن و تحلیل ترندهای بازار کار.

توجه دربارهٔ منابع بیرونی:
سرور ربات ممکن است به سایت‌های کاریابی دسترسی نداشته باشد (فیلترینگ یا
نبود اینترنت). بنابراین این ماژول:
  ۱. اول تلاش می‌کند از منبع پیکربندی‌شده داده بگیرد (اختیاری، با httpx).
  ۲. اگر نشد، از فهرست پایهٔ داخلی استفاده می‌کند و آن را با AI رتبه‌بندی می‌کند.
  ۳. اگر AI هم در دسترس نبود، فهرست پایه بدون تحلیل ذخیره می‌شود.
هیچ‌وقت خطا پرتاب نمی‌شود و ربات هرگز به‌خاطر این ماژول متوقف نمی‌گردد.

وابستگی: ai_db، ai_core و stdlib.
"""
import logging

from . import ai_db
from .ai_core import analyze_trends_with_ai

logger = logging.getLogger(__name__)

try:
    import httpx as _httpx
except Exception:
    _httpx = None

# فهرست پایه — مهارت‌های پرتقاضای بازار ایران
BASE_SKILLS = [
    ("Python", 1200), ("JavaScript", 1100), ("React", 950),
    ("SQL", 900), ("Django", 700), ("Docker", 650),
    ("Git", 620), ("Node.js", 600), ("TypeScript", 560),
    ("Linux", 540), ("REST API", 500), ("PostgreSQL", 480),
    ("هوش مصنوعی", 460), ("Next.js", 420), ("Flutter", 400),
]


async def fetch_trends_from_sources(url: str = None, timeout: int = 12) -> tuple:
    """
    تلاش برای دریافت ترندها از منبع بیرونی.
    خروجی: (skills: list[tuple[str, int]], source: str)
    در صورت شکست، فهرست پایه برگردانده می‌شود.
    """
    src_url = (url or ai_db.get_ai_setting("trends_source", "") or "").strip()
    if not src_url or _httpx is None:
        return list(BASE_SKILLS), "base"

    try:
        async with _httpx.AsyncClient(timeout=timeout) as client:
            r = await client.get(src_url)
            r.raise_for_status()
            data = r.json()

        skills = []
        if isinstance(data, dict):
            data = data.get("skills") or data.get("data") or []
        if isinstance(data, list):
            for item in data:
                if isinstance(item, dict):
                    name = (item.get("skill") or item.get("name") or "").strip()
                    cnt = item.get("demand_count") or item.get("count") or 0
                    if name:
                        skills.append((name, int(cnt or 0)))
                elif isinstance(item, str) and item.strip():
                    skills.append((item.strip(), 0))
        if skills:
            return skills[:30], src_url
        logger.warning("منبع ترند پاسخ داد ولی داده‌ای نداشت؛ فهرست پایه استفاده شد.")
    except Exception as e:
        logger.warning(f"دریافت ترند از منبع ناموفق بود ({e}); فهرست پایه استفاده شد.")

    return list(BASE_SKILLS), "base"


async def analyze_job_demand(skills_list) -> dict:
    """تحلیل تقاضا با AI. اگر AI در دسترس نباشد، ok=False برمی‌گردد."""
    if not skills_list:
        return {"ok": False, "error": "فهرست مهارت خالی است."}
    payload = "فهرست مهارت‌ها و تعداد آگهی شغلی:\n" + "\n".join(
        f"- {name}: {cnt} آگهی" for name, cnt in skills_list[:25]
    )
    return await analyze_trends_with_ai(payload)


async def update_market_trends_db(use_ai: bool = True) -> dict:
    """
    به‌روزرسانی جدول market_trends.
    خروجی: {ok, count, via, error}
    """
    skills, source = await fetch_trends_from_sources()

    if use_ai:
        res = await analyze_job_demand(skills)
        if res.get("ok") and res.get("trends"):
            saved = 0
            for t in res["trends"][:15]:
                if not isinstance(t, dict):
                    continue
                name = (t.get("skill") or "").strip()
                if not name:
                    continue
                try:
                    cnt = int(t.get("demand_count") or 0)
                except Exception:
                    cnt = 0
                if ai_db.save_market_trend(name, cnt, source, (t.get("reason") or "").strip()):
                    saved += 1
            if saved:
                return {"ok": True, "count": saved, "via": "ai"}
        logger.info("تحلیل AI در دسترس نبود؛ ذخیرهٔ فهرست خام.")

    # ذخیرهٔ خام بدون AI
    saved = 0
    for name, cnt in skills[:15]:
        if ai_db.save_market_trend(name, cnt, source, ""):
            saved += 1
    if saved:
        return {"ok": True, "count": saved, "via": "raw"}
    return {"ok": False, "count": 0, "error": "ذخیره‌سازی ناموفق بود."}


def ensure_seeded() -> None:
    """اگر جدول ترندها خالی بود، فهرست پایه را بدون نیاز به شبکه درج می‌کند."""
    try:
        if ai_db.get_trending_skills(1):
            return
        for name, cnt in BASE_SKILLS[:10]:
            ai_db.save_market_trend(name, cnt, "base", "")
    except Exception as e:
        logger.error(f"ensure_seeded: {e}")
