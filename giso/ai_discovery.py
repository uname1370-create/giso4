# -*- coding: utf-8 -*-
"""
giso/ai_discovery.py — کشف هوشمند مدل‌ها («بروزرسانی همهٔ هوش مصنوعی‌ها»)

کار این ماژول (مأموریت 11):
۱. فهرست پروایدرهای ثبت‌شده را می‌گیرد؛
۲. برای هرکدام لیست مدل‌ها را از آدرس /models خود سرویس می‌گیرد؛
۳. هوشمندانه مدل‌های رایگانِ قوی و کم‌هزینه را که به کار پروژه می‌آیند
   (بینایی برای تحلیل عکس + متنی برای چت) انتخاب می‌کند؛
۴. لیست همان پروایدر را خودکار به‌روز می‌کند (بدون دخالت دستی)؛
۵. گزارش هر سرویس را برمی‌گرداند تا در پنل مدیریت نمایش داده شود.

این فایل هیچ رابط کاربری‌ای ندارد؛ دکمه‌ها در پنل و ربات این توابع را صدا می‌زنند.
"""
from __future__ import annotations

import asyncio
import json
import logging
import re
import time

logger = logging.getLogger(__name__)

# پروایدرهایی که اندپوینت /models استاندارد ندارند؛ مدل‌هایشان از رجیستری
# پایه مدیریت می‌شود و کشف برایشان معنا ندارد.
DISCOVERY_SKIP_PROVIDERS = ("cloudflare",)

# پروایدرهایی که کلاً رایگان/محدودشده هستند؛ وقتی /models قیمت ندهد،
# مدل‌هایشان «رایگان» فرض می‌شود.
KNOWN_FREE_PROVIDERS = ("openrouter", "groq", "mistral", "sambanova", "cloudflare")

# نقشهٔ راه الگوریتم: دقیقاً هر سرویس کجا و چطور بررسی شود و دنبال چه بگردد.
# آدرس = {base}/models (base از تنظیمات همان پروایدر می‌آید) + کلید + پروکسی خودش.
PROVIDER_PLAYBOOK = {
    "openrouter": "GET /models با قیمت رسمی در پاسخ؛ فقط مدل‌های قیمت‌صفر یا ':free' — بینایی از فیلد image در input_modalities",
    "groq": "GET /models؛ همه رایگان‌اند (قیمت در پاسخ نیست) — بینایی با کلید (llama-4/llava)، متنی قوی 70b به بالا",
    "mistral": "GET /models؛ تیر رایگان همه مدل‌ها را دارد — بینایی: pixtral و mistral-small",
    "sambanova": "GET /models؛ معمولاً ۴۰۲ یعنی کردیت تمام شده — اگر جواب داد، همه رایگان‌اند",
    "gemini": "از ورکر Cloudflare کاربر: {worker}/v1/models — مدل‌های جمینای همگی بینایی دارند",
    "cloudflare": "اندپوینت /models ندارد؛ مدل‌ها از رجیستری پایه مدیریت می‌شوند (کشف نمی‌شود)",
}

# سقف تعداد مدل نگهداری‌شده برای هر پروایدر (لیست تمیز و کوتاه می‌ماند)
MAX_VISION_MODELS = 6
MAX_TEXT_MODELS = 8

# کلمات کلیدی مدل‌هایی که به درد چت/تحلیل نمی‌خورند (حذف قطعی)
_NON_CHAT_KEYWORDS = (
    "embed", "tts", "whisper", "speech", "audio", "music", "lyria",
    "flux", "dall", "imagen", "stable-diffusion", "sdxl", "image-gen",
    "moderation", "guard", "rerank", "tokenizer", "clip", "bge", "e5-",
    "cogvideo", "veo", "videocraft", "safety", "nomic", "jina",
    "csam", "scam", "lora",
)

# امتیاز خانوادگی مدل‌ها — فقط برای انتخاب «قوی‌ترین رایگان‌ها» استفاده
# می‌شود؛ جایی نمایش داده نمی‌شود. (بالاتر = قوی‌تر برای کار گیسو)
_FAMILY_STRONG = (
    "gemma-4", "inkling", "nemotron", "gpt-oss-120b", "kimi-k2",
    "mistral-large", "pixtral", "llama-4", "minimax-m", "qwen3.6",
    "gemini-2.5-flash", "gemini-3", "glm-5", "deepseek-v", "gpt-5",
    "claude", "gpt-4o", "grok",
)
_FAMILY_MID = (
    "llama-3.3-70b", "llama-3.1-70b", "qwen3-32b", "qwen-3-32b",
    "mistral-small", "mistral-medium", "mistral-nemo", "gpt-oss-20b",
    "deepseek-r1", "mixtral", "gemma-3-27b", "gemma-2-27b", "gpt-4o-mini",
    "gemini-2.0", "qwq", "magistral",
)


def _now_fa() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")


def _item_id(item) -> str:
    """شناسهٔ مدل از آیتم‌های با فرمت‌های مختلف (OpenRouter/OpenAI/میسترال)."""
    try:
        return str(item.get("id") or item.get("model") or "").strip()
    except Exception:
        return ""


def _item_is_free(item, provider_name: str) -> bool:
    """رایگان؟ ۱) پسوند :free  ۲) قیمت صفر در پاسخ  ۳) پروایدر کلاً رایگان."""
    mid = _item_id(item)
    if mid.endswith(":free"):
        return True
    try:
        pricing = item.get("pricing") or {}
        p_in = pricing.get("prompt")
        p_out = pricing.get("completion")
        if p_in is not None and p_out is not None:
            # قیمت رسماً در پاسخ هست → همین عدد تعیین‌کننده است (مورد اوپن‌روتر)
            return float(p_in) == 0 and float(p_out) == 0
    except Exception:
        pass
    # پاسخ اصلاً قیمت ندارد (گوک/میسترال/سامبانوا/کلودفلر) → تیر سرویس ملاک است
    return str(provider_name or "").lower() in KNOWN_FREE_PROVIDERS


def _item_has_vision(item, mid: str) -> bool:
    """بینایی؟ اول فیلدهای رسمی سرویس، بعد کلمات کلیدی."""
    try:
        arch = item.get("architecture") or {}
        mods = str(arch.get("input_modalities") or "").lower()
        if "image" in mods:
            return True
        modality = str(item.get("modality") or "").lower()
        if "image" in modality and "null" not in modality:
            return True
        caps = item.get("capabilities") or {}
        if isinstance(caps, dict) and caps.get("vision") is True:
            return True
    except Exception:
        pass
    try:
        from giso.ai_brain import _is_vision_model_id
        return bool(_is_vision_model_id(mid))
    except Exception:
        return False


def _strength_score(mid: str, is_free: bool, context: int) -> float:
    """امتیاز داخلی برای انتخاب قوی‌ترین‌ها (نمایش داده نمی‌شود)."""
    m = mid.lower()
    score = 0.0
    if any(f in m for f in _FAMILY_STRONG):
        score += 30.0
    elif any(f in m for f in _FAMILY_MID):
        score += 18.0
    else:
        # مدل‌های خیلی کوچک (≤8b) برای تحلیل گیسو ضعیف‌اند
        if re.search(r"\b[1-8]b\b", m) or m.endswith("-3b") or "-7b" in m:
            score += 4.0
        else:
            score += 10.0
    if is_free:
        score += 25.0
    if context and context > 0:
        # زمینهٔ بزرگ‌تر امتیاز بیشتری دارد (با سقف)
        score += min(15.0, (context / 131072.0) * 15.0)
    if m.endswith(":free") or m.endswith("-latest"):
        score += 3.0  # شناسه‌های رسمیِ پایدار
    return score


def _context_of(item) -> int:
    try:
        return int(item.get("context_length") or item.get("context") or 0)
    except Exception:
        return 0


def _drop_dated_duplicates(models: list) -> list:
    """اگر هم‌خانوادهٔ «…-latest» هست، نسخهٔ تاریخ‌دار (مثل -2506) حذف شود."""
    latest_bases = set()
    for m in models:
        mid = m.get("id", "")
        if str(mid).endswith("-latest"):
            latest_bases.add(str(mid)[: -len("-latest")])
    if not latest_bases:
        return models
    out = []
    for m in models:
        mid = str(m.get("id", ""))
        if re.search(r"-\d{4}$", mid) and mid[:5] and any(
                mid.startswith(b) for b in latest_bases):
            continue
        out.append(m)
    return out


def smart_filter_models(provider_name: str, items: list) -> tuple:
    """هستهٔ انتخاب هوشمند: آیتم‌های خام /models ← (بینایی، متنی).

    خروجی: دو لیست مدل [{id, is_free, context, source}] به ترتیب امتیاز.
    """
    vision, text, seen = [], [], set()
    pname = str(provider_name or "").lower()
    for item in items:
        if not isinstance(item, dict):
            continue
        mid = _item_id(item)
        if not mid or mid.lower() in seen:
            continue
        low = mid.lower()
        # حذف مدل‌های غیرمرتبط با چت/تحلیل (امبدینگ، صوتی، تولید عکس و…)
        if any(k in low for k in _NON_CHAT_KEYWORDS):
            continue
        seen.add(low)
        is_free = _item_is_free(item, pname)
        ctx = _context_of(item)
        model = {"id": mid, "is_free": bool(is_free), "context": ctx,
                 "source": "discovered"}
        if _item_has_vision(item, mid):
            vision.append(model)
        else:
            text.append(model)

    # اگر اصلاً مدل رایگانی هست، پولی‌ها دیگر انتخاب نمی‌شوند؛
    # ولی اگر سرویس کلاً پولی است (مثل سرویس‌های ایرانی) لیست خالی نماند.
    if any(m["is_free"] for m in vision + text):
        vision = [m for m in vision if m["is_free"]]
        text = [m for m in text if m["is_free"]]

    vision = _drop_dated_duplicates(vision)
    text = _drop_dated_duplicates(text)

    vision.sort(key=lambda m: -_strength_score(m["id"], m["is_free"], m["context"]))
    text.sort(key=lambda m: -_strength_score(m["id"], m["is_free"], m["context"]))
    return vision[:MAX_VISION_MODELS], text[:MAX_TEXT_MODELS]


def _fa_fetch_error(err: str) -> str:
    """ترجمهٔ خوانای خطاهای دریافت لیست برای گزارش."""
    e = str(err or "")
    if "403" in e:
        return "مسدود از سمت سرویس (۴۰۳) — احتمالاً نیاز به پروکسی"
    if "402" in e:
        return "سهمیهٔ رایگان/کردیت تمام شده (۴۰۲)"
    if "401" in e:
        return "کلید نامعتبر است (۴۰۱)"
    if "404" in e:
        return "آدرس /models در این سرویس موجود نیست (۴۰۴)"
    if "Timeout" in e or "timed out" in e:
        return "تایم‌اوت در دریافت لیست"
    return e[:120]


async def discover_provider(name: str) -> dict:
    """کشف هوشمند مدل‌های یک پروایدر + به‌روزرسانی خودکار لیستش."""
    from giso import ai_brain
    report = {"name": name, "ok": False, "skipped": False,
              "vision_count": 0, "text_count": 0, "new": 0,
              "top": "", "error": ""}
    row = ai_brain.get_ai_provider(name)
    if row is None:
        report["error"] = "پروایدر پیدا نشد"
        return report
    if not row["enabled"]:
        report["skipped"] = True
        report["error"] = "غیرفعال است — رد شد"
        return report
    if str(name or "").lower() in DISCOVERY_SKIP_PROVIDERS or row["kind"] == "cloudflare":
        report["skipped"] = True
        report["error"] = "مدل‌هایش از رجیستری پایه مدیریت می‌شود"
        return report
    if not str(row["api_key"] or "").strip():
        report["skipped"] = True
        report["error"] = "کلید ندارد — لیست فعلی حفظ شد"
        return report

    fetched = await ai_brain._fetch_remote_models(row)
    if not fetched or not fetched.get("ok"):
        err = _fa_fetch_error((fetched or {}).get("error", "خطا"))
        hint = {"sambanova": " (این سرویس اخیراً عملاً اعتباری شده است)",
                "gemini": " (اتصال باید از ورکر کلودفلر باشد)"}.get(str(name).lower(), "")
        report["error"] = err + hint
        return report

    items = fetched.get("items") or []
    if not items:
        report["error"] = "لیست مدل خالی برگشت"
        return report

    vision, text = smart_filter_models(name, items)
    if not vision and not text:
        report["error"] = "مدل مناسبی پیدا نشد — لیست فعلی حفظ شد"
        return report

    # ادغام با لیست قبلی: مدل‌های دستی/رجیستری معتبر حفظ می‌شوند
    old_vision = ai_brain._ai_jloads(ai_brain._col(row, "vision_models_json", ""), [])
    old_text = ai_brain._ai_jloads(ai_brain._col(row, "text_models_json", ""), [])
    merged_v, new_v = ai_brain._merge_discovered(old_vision if isinstance(old_vision, list) else [],
                                                 [m["id"] for m in vision])
    merged_t, new_t = ai_brain._merge_discovered(old_text if isinstance(old_text, list) else [],
                                                 [m["id"] for m in text])
    # مدل‌های کشف‌شدهٔ جدید با امتیازشان جایگزین نسخهٔ سادهٔ ادغام شوند
    score_map = {m["id"]: m for m in vision + text}
    for m in merged_v + merged_t:
        if m.get("id") in score_map and not m.get("disabled"):
            m.update({k: v for k, v in score_map[m["id"]].items() if k != "id"})

    all_ids = [m["id"] for m in merged_v + merged_t if not m.get("disabled")]
    selected = str(row["selected_model"] or "")
    if selected not in all_ids and all_ids:
        # مدل انتخابی قبلی دیگر وجود ندارد → اولین مدل زنده جایگزینش شود
        selected = all_ids[0]

    # گزارش کوتاه هر سرویس
    top_models = [m["id"] for m in (vision + text)[:2]]
    report.update({
        "ok": True,
        "vision_count": len([m for m in merged_v if not m.get("disabled")]),
        "text_count": len([m for m in merged_t if not m.get("disabled")]),
        "new": len(new_v) + len(new_t),
        "top": "، ".join(top_models),
    })

    try:
        with ai_brain._lock, ai_brain.get_conn() as conn:
            try:
                conn.execute("ALTER TABLE giso_ai_providers ADD COLUMN discovery_report TEXT")
            except Exception:
                pass  # ستون از قبل وجود دارد
            conn.execute(
                """UPDATE giso_ai_providers SET
                     vision_models_json=?, text_models_json=?, models_json=?,
                     fallback_json=?, selected_model=?, models_source='discovered',
                     models_last_updated=?, discovery_report=?
                   WHERE name=?""",
                (json.dumps(merged_v, ensure_ascii=False),
                 json.dumps(merged_t, ensure_ascii=False),
                 json.dumps(all_ids, ensure_ascii=False),
                 json.dumps(all_ids, ensure_ascii=False),
                 selected, _now_fa(),
                 f"🕘 {_now_fa()} — {report['vision_count']} بینایی + "
                 f"{report['text_count']} متنی ({report['new']} جدید)",
                 name))
    except Exception as e:
        logger.error(f"discover_provider save ({name}): {e}")
        report["ok"] = False
        report["error"] = "خطا در ذخیره"
    return report


async def refresh_all_models_async() -> dict:
    """دکمهٔ «بروزرسانی همهٔ هوش مصنوعی‌ها» — همهٔ پروایدرها به‌صورت موازی."""
    from giso import ai_brain
    rows = ai_brain.list_ai_providers() or []
    if not rows:
        return {"ok": False, "reports": [], "summary": "هیچ پروایدری ثبت نشده است"}
    tasks = [discover_provider(str(r["name"])) for r in rows]
    reports = await asyncio.gather(*tasks, return_exceptions=True)
    cleaned = []
    for r in reports:
        if isinstance(r, Exception):
            cleaned.append({"name": "?", "ok": False, "error": str(r)[:120]})
        else:
            cleaned.append(r)
    ok_n = sum(1 for r in cleaned if r.get("ok"))
    skip_n = sum(1 for r in cleaned if r.get("skipped"))
    err_n = len(cleaned) - ok_n - skip_n
    summary = (f"{ok_n} سرویس به‌روزرسانی شد ✅ | {skip_n} رد شد | {err_n} خطا")
    return {"ok": True, "reports": cleaned, "summary": summary}


def refresh_all_models() -> dict:
    """نسخهٔ همگام برای پنل سایت (ربات از نسخهٔ async استفاده می‌کند)."""
    from giso.ai_brain import run_async_sync
    return run_async_sync(refresh_all_models_async()) or {
        "ok": False, "reports": [], "summary": "خطا در اجرای بروزرسانی"}


__all__ = [
    "smart_filter_models", "discover_provider",
    "refresh_all_models", "refresh_all_models_async",
    "MAX_VISION_MODELS", "MAX_TEXT_MODELS",
]
