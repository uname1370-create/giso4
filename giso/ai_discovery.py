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

# نقشهٔ راه الگوریتم: دقیقاً هر سرویس کجا و چطور بررسی شود و دنبال چه بگردد.
# آدرس = {base}/models (base از تنظیمات همان پروایدر می‌آید) + کلید + پروکسی خودش.
PROVIDER_PLAYBOOK = {
    "openrouter": "GET /models با قیمت رسمی در پاسخ؛ فقط مدل‌های قیمت‌صفر یا ':free' — بینایی از فیلد image در input_modalities",
    "groq": "GET /models؛ همه رایگان‌اند (قیمت در پاسخ نیست) — بینایی با کلید (llama-4/llava)، متنی قوی 70b به بالا",
    "mistral": "GET /models؛ تیر رایگان همه مدل‌ها را دارد — بینایی: pixtral و mistral-small",
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


def _price_info(item, provider_name: str) -> dict:
    """وضعیت قیمت با شاهد (طبقه‌بند مشترک ai_models_registry)."""
    from giso.ai_models_registry import classify_model_price
    return classify_model_price(item, provider_name)


def _item_is_free(item, provider_name: str) -> bool:
    """رایگان فقط با شاهد صریح (پسوند :free، قیمت صفر، یا ادعای رجیستری)."""
    from giso.ai_models_registry import PRICE_FREE
    return _price_info(item, provider_name)["status"] == PRICE_FREE


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
        from giso.ai_models_registry import PRICE_FREE
        info = _price_info(item, pname)
        is_free = info["status"] == PRICE_FREE
        ctx = _context_of(item)
        model = {"id": mid, "is_free": bool(is_free), "context": ctx,
                 "source": "discovered", "price_status": info["status"],
                 "price_source": info["source"]}
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


def unfiltered_chat_models(provider_name: str, items: list) -> tuple:
    """مدل‌های چت‌پذیری که فیلتر هوشمند کنار گذاشته است، با برچسب قیمت.

    فقط برای نمایش است و هرگز جای مدل رایگان انتخاب‌شده را نمی‌گیرد.
    """
    from giso.ai_models_registry import PRICE_FREE
    vision, text, seen = [], [], set()
    pname = str(provider_name or "").lower()
    for item in items:
        if not isinstance(item, dict):
            continue
        mid = _item_id(item)
        if not mid or mid.lower() in seen:
            continue
        low = mid.lower()
        if any(k in low for k in _NON_CHAT_KEYWORDS):
            continue
        seen.add(low)
        info = _price_info(item, pname)
        model = {"id": mid, "is_free": info["status"] == PRICE_FREE, "context": _context_of(item),
                 "source": "discovered", "price_status": info["status"], "price_source": info["source"]}
        (vision if _item_has_vision(item, mid) else text).append(model)
    return vision, text


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
              "top": "", "error": "", "selected_missing": False}
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
        hint = {"gemini": " (اتصال باید از ورکر کلودفلر باشد)"}.get(str(name).lower(), "")
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
    # مدل‌های چت‌پذیر کنار گذاشته‌شده، با برچسب قیمت، به‌عنوان متن اضافه می‌شوند (نه رایگان)
    shown_ids = {m["id"] for m in vision + text}
    extra_v, extra_t = unfiltered_chat_models(name, items)
    text = text + [m for m in extra_v + extra_t if m["id"] not in shown_ids]

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
    # شاهد قابلیت رسمی API (فقط فیلدهای صریح) کنار هر مدل؛ حدس از نام انجام نمی‌شود
    from giso.ai_models_registry import official_capability_hints
    caps_map = {}
    for it in items:
        if isinstance(it, dict) and it.get("id"):
            hints = official_capability_hints(it)
            if hints:
                caps_map[it["id"]] = hints
    for m in merged_v + merged_t:
        if m.get("id") in caps_map:
            m["caps"] = caps_map[m["id"]]
        else:
            m.pop("caps", None)

    all_ids = [m["id"] for m in merged_v + merged_t if not m.get("disabled")]
    selected = str(row["selected_model"] or "")
    # انتخاب ادمین هرگز توسط کشف عوض یا پر نمی‌شود؛ خالی بودن و ناموجود بودن فقط گزارش می‌شود
    selected_missing = bool(selected) and selected not in all_ids
    selected_empty = not selected

    # گزارش کوتاه هر سرویس
    top_models = [m["id"] for m in (vision + text)[:2]]
    report.update({
        "ok": True,
        "vision_count": len([m for m in merged_v if not m.get("disabled")]),
        "text_count": len([m for m in merged_t if not m.get("disabled")]),
        "new": len(new_v) + len(new_t),
        "top": "، ".join(top_models),
        "selected_missing": selected_missing,
        "selected_empty": selected_empty,
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
                 json.dumps(ai_brain._merge_fallback_order(row["fallback_json"], all_ids), ensure_ascii=False),
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


# ---------------------------------------------------------------------------
# بخش «مدیریت و انتخاب مدل‌ها»: وضعیت قابلیت هر مدل و تست واقعی آن.
#
# سطح‌های شاهد (از قوی به ضعیف):
#   ۱. تست واقعی موفق روی همان قابلیت            → تأییدشده
#   ۲. فیلد صریح قابلیت در خود API               → تأییدشده (یا ناسازگار اگر False)
#   ۳. ثبت در فهرست همان قابلیت (نام/رجیستری)     → احتمالی؛ نیازمند تست
#   ۴. هیچ شاهدی                                   → نامشخص (هرگز «آماده» نیست)
# رایگان بودن جداگانه و فقط با شاهد معتبر از ai_models_registry می‌آید.
# ---------------------------------------------------------------------------
CAP_TEXT = "text"
CAP_VISION = "vision"
CAP_IMAGE_GEN = "image_gen"
CAPABILITIES = (CAP_TEXT, CAP_VISION, CAP_IMAGE_GEN)

STATUS_CONFIRMED = "confirmed"
STATUS_PROBABLE = "probable"
STATUS_INCOMPATIBLE = "incompatible"
STATUS_UNKNOWN = "unknown"
COMPATIBLE_STATUSES = (STATUS_CONFIRMED, STATUS_PROBABLE)
STATUS_LABELS_FA = {
    STATUS_CONFIRMED: "تأییدشده",
    STATUS_PROBABLE: "احتمالی — نیازمند تست",
    STATUS_INCOMPATIBLE: "ناسازگار",
    STATUS_UNKNOWN: "نامشخص",
}

CHECK_OK = "ok"
CHECK_FAILED = "failed"
CHECK_INCOMPATIBLE = "incompatible"
CHECK_NOT_TESTED = "not_tested"
CHECK_INCONCLUSIVE = "inconclusive"

STAGE_AUTH = "auth"
STAGE_TIMEOUT = "timeout"
STAGE_NETWORK = "network"
STAGE_TRANSIENT = "transient"
STAGE_MODEL_MISSING = "model_missing"
STAGE_MODEL_RUN = "model_run"
STAGE_INCOMPATIBLE = "incompatible"
STAGE_INCONCLUSIVE = "inconclusive"
# مراحلی که اتصال/احراز پروایدر را شکست‌خورده نشان می‌دهند؛ provider_connection = «اتصال برقرار بود»
PROVIDER_CONNECTION_STAGES = (STAGE_AUTH, STAGE_TIMEOUT, STAGE_NETWORK)
_NETWORK_TOKENS = ("connecterror", "connection", "tls", "ssl", "eof occurred", "name or service",
                   "resolve", "unreachable", "reset by peer", "remoteprotocol", "remotedisconnected",
                   "network")
_MODALITY_REJECT_RE = re.compile(
    r"(does not|doesn't|do not|not|no)\s+(support|accept|allow)\w*[^.]{0,40}(image|vision|multimodal)"
    r"|(image|vision|multimodal)[^.]{0,30}(not supported|unsupported|not allowed)", re.IGNORECASE)

_PROBE_PROMPT = "Reply with the single word OK."
_SECRET_PATTERNS = (
    re.compile(r"(?i)bearer\s+[A-Za-z0-9._\-]+"),
    re.compile(r"sk-[A-Za-z0-9_\-]{8,}"),
)


def ensure_checks_table(conn) -> None:
    """جدول نتیجهٔ تست واقعی هر (پروایدر، مدل، قابلیت) — افزایشی و بی‌خطر."""
    conn.execute(
        """CREATE TABLE IF NOT EXISTS giso_ai_model_checks (
            provider_name TEXT NOT NULL,
            model_id TEXT NOT NULL,
            capability TEXT NOT NULL,
            result TEXT NOT NULL DEFAULT '',
            stage TEXT NOT NULL DEFAULT '',
            detail TEXT NOT NULL DEFAULT '',
            checked_at TEXT NOT NULL DEFAULT '',
            PRIMARY KEY (provider_name, model_id, capability)
        )"""
    )


def _load_checks(provider_name: str) -> dict:
    from giso import ai_brain
    out: dict = {}
    try:
        with ai_brain.get_conn() as conn:
            ensure_checks_table(conn)
            rows = conn.execute(
                "SELECT model_id, capability, result, stage, detail, checked_at "
                "FROM giso_ai_model_checks WHERE provider_name=?",
                (provider_name,),
            ).fetchall()
        for r in rows:
            out[(r[0], r[1])] = {"result": r[2], "stage": r[3], "detail": r[4], "checked_at": r[5]}
    except Exception as exc:
        logger.error("load model checks (%s): %s", provider_name, exc)
    return out


def _save_check(provider_name: str, model_id: str, capability: str, result: str,
                stage: str, detail: str) -> None:
    from giso import ai_brain
    try:
        with ai_brain.get_conn() as conn:
            ensure_checks_table(conn)
            conn.execute(
                """INSERT INTO giso_ai_model_checks
                   (provider_name, model_id, capability, result, stage, detail, checked_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?)
                   ON CONFLICT(provider_name, model_id, capability) DO UPDATE SET
                     result=excluded.result, stage=excluded.stage,
                     detail=excluded.detail, checked_at=excluded.checked_at""",
                (provider_name, model_id, capability, result, stage, detail[:300],
                 _now_fa()),
            )
    except Exception as exc:
        logger.error("save model check (%s/%s): %s", provider_name, model_id, exc)


def _entries_by_id(raw) -> dict:
    out: dict = {}
    if isinstance(raw, str):
        try:
            raw = json.loads(raw or "[]")
        except Exception:
            raw = []
    for item in raw if isinstance(raw, list) else []:
        if isinstance(item, dict) and item.get("id") and not item.get("disabled"):
            out[str(item["id"]).strip()] = item
        elif isinstance(item, str) and item.strip():
            out[item.strip()] = {"id": item.strip()}
    return out


def _provider_catalog(provider_name: str) -> dict:
    """فهرست مدل‌های ذخیره‌شدهٔ یک پروایدر از دیتابیس (بدون هیچ درخواست بیرونی)."""
    from giso import ai_brain
    row = ai_brain.get_ai_provider(provider_name)
    if row is None:
        return {}
    return {
        "row": row,
        "vision": _entries_by_id(ai_brain._col(row, "vision_models_json", "")),
        "text": _entries_by_id(ai_brain._col(row, "text_models_json", "")),
    }


def resolve_model_capability(model_id: str, capability: str, *, catalog: dict, checks: dict) -> dict:
    """وضعیت یک قابلیت برای یک مدل بر اساس شاهدهای بالا؛ هرگز از نام به‌تنهایی «تأیید» نمی‌کند."""
    from giso import ai_brain
    entry_v = catalog.get("vision", {}).get(model_id)
    entry_t = catalog.get("text", {}).get(model_id)
    in_vision = entry_v is not None
    in_text = entry_t is not None
    caps: dict = {}
    for entry in (entry_v, entry_t):
        if entry and isinstance(entry.get("caps"), dict):
            for key, value in entry["caps"].items():
                caps.setdefault(key, value)
    check = checks.get((model_id, capability)) or {}
    # نتیجهٔ ناموفق یا نامشخص فقط یادداشت می‌شود؛ هرگز مدل را ناسازگار نمی‌کند
    last_result = check.get("result")
    last_note = ""
    if last_result in (CHECK_FAILED, CHECK_INCONCLUSIVE):
        label = "ناموفق" if last_result == CHECK_FAILED else "بدون نتیجهٔ قطعی"
        last_note = f"آخرین تست {label} ({check.get('checked_at')}): {check.get('detail') or ''}"

    if check.get("result") == CHECK_OK:
        status, source = STATUS_CONFIRMED, f"تست واقعی موفق ({check.get('checked_at')})"
    elif check.get("result") == CHECK_INCOMPATIBLE:
        status, source = STATUS_INCOMPATIBLE, f"تست واقعی: این قابلیت پشتیبانی نمی‌شود ({check.get('checked_at')})"
    elif isinstance(caps.get(capability), bool) and caps[capability]:
        status, source = STATUS_CONFIRMED, "فراداده رسمی API"
    elif isinstance(caps.get(capability), bool):
        status, source = STATUS_INCOMPATIBLE, "فراداده رسمی API این قابلیت را ندارد"
    elif capability == CAP_VISION and in_vision:
        status, source = STATUS_PROBABLE, "در فهرست بینایی پروایدر (نیازمند تست)"
    elif capability == CAP_TEXT and in_text:
        status, source = STATUS_PROBABLE, "در فهرست متنی پروایدر (نیازمند تست)"
    elif capability == CAP_IMAGE_GEN and (in_vision or in_text) and ai_brain._ai_is_image_generation_model(model_id):
        status, source = STATUS_PROBABLE, "نام مدل تصویری است (نیازمند تست)"
    else:
        status, source = STATUS_UNKNOWN, "شاهدی برای این قابلیت ثبت نشده"

    entry = entry_v or entry_t or {}
    return {
        "capability": capability,
        "status": status,
        "status_label": STATUS_LABELS_FA[status],
        "source": source,
        "last_result": check.get("result", ""),
        "last_stage": check.get("stage", ""),
        "last_checked": check.get("checked_at", ""),
        "last_note": last_note,
        "price_status": str(entry.get("price_status") or ""),
    }


def model_capability_for_provider(provider_name: str, model_id: str, capability: str) -> dict:
    catalog = _provider_catalog(provider_name)
    return resolve_model_capability(
        model_id, capability, catalog=catalog, checks=_load_checks(provider_name)
    )


def compatible_model_options(capability: str) -> list:
    """مدل‌های سازگار (تأییدشده یا احتمالی) از پروایدرهای فعال، برای منوی هر دسته."""
    from giso import ai_brain
    out: list = []
    try:
        rows = ai_brain.list_ai_providers() or []
    except Exception:
        rows = []
    for row in rows:
        name = str(ai_brain._col(row, "name", "") or "").strip().lower()
        if not name or not ai_brain._col(row, "enabled", 0):
            continue
        catalog = _provider_catalog(name)
        if not catalog:
            continue
        checks = _load_checks(name)
        ids = list(catalog["vision"].keys()) + [m for m in catalog["text"].keys() if m not in catalog["vision"]]
        for model_id in ids:
            info = resolve_model_capability(model_id, capability, catalog=catalog, checks=checks)
            if info["status"] in COMPATIBLE_STATUSES:
                out.append({"provider": name, "model": model_id, **info})
    out.sort(key=lambda o: (o["provider"], o["status"] != STATUS_CONFIRMED, o["model"]))
    return out


def redact_secrets(text, secrets=()) -> str:
    """کلید و توکن‌ها را از متن خطا پاک می‌کند تا هرگز در پیام یا لاگ عمومی نرسند."""
    out = str(text or "")
    for secret in secrets:
        if secret and len(str(secret)) >= 6:
            out = out.replace(str(secret), "[پنهان]")
    for pattern in _SECRET_PATTERNS:
        out = pattern.sub("[پنهان]", out)
    return out[:300]


def _probe_png_path() -> str:
    """یک PNG کوچک ۳۲×۳۲ برای تست قابلیت بینایی (بدون وابستگی به کتابخانهٔ تصویر)."""
    import os
    import struct
    import tempfile
    import zlib

    width = height = 32
    raw = b"".join(b"\x00" + b"\xff\x80\x00" * width for _ in range(height))

    def chunk(kind: bytes, data: bytes) -> bytes:
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)

    png = (b"\x89PNG\r\n\x1a\n"
           + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
           + chunk(b"IDAT", zlib.compress(raw))
           + chunk(b"IEND", b""))
    fd, path = tempfile.mkstemp(suffix=".png", prefix="giso_probe_")
    with os.fdopen(fd, "wb") as handle:
        handle.write(png)
    return path


def _classify_check_error(error: str, capability: str) -> tuple:
    """(نتیجه، مرحله، توضیح فارسی) برای خطای یک تست واقعی.

    مرحله‌ها:
      auth          کلید/دسترسی (401/403) — مشکل اتصال/حساب، نه مدل
      timeout       زمان پاسخ تمام شد — موقت، مدل ناسازگار نیست
      network       اتصال شبکه/TLS — موقت، مدل ناسازگار نیست
      transient     429 یا 5xx — موقت، مدل ناسازگار نیست
      model_missing 404 — مدل روی این پروایدر نیست (ناموفق، نه ناسازگار قطعی)
      incompatible  فقط پذیرش صریح نشدن ورودی تصویر توسط مدل
      model_run     سایر خطاهای درخواست (ناموفق)
      inconclusive  خطای ناشناخته — نتیجه نامشخص، نه ناسازگاری
    فقط «incompatible» نتیجهٔ ناسازگاری است؛ بقیه هرگز مدل را ناسازگار نشان نمی‌دهند.
    """
    text = str(error or "")
    low = text.lower()
    code_match = re.search(r"HTTP (\d{3})", text)
    code = int(code_match.group(1)) if code_match else 0
    if code in (401, 403) or "api key" in low or "کلید" in text:
        return CHECK_FAILED, STAGE_AUTH, "احراز هویت ناموفق: کلید یا دسترسی معتبر نیست."
    if "timeout" in low or "timed out" in low:
        return CHECK_FAILED, STAGE_TIMEOUT, "زمان پاسخ‌گویی تمام شد (timeout). خطای موقت است."
    if any(token in low for token in _NETWORK_TOKENS):
        return CHECK_FAILED, STAGE_NETWORK, "اتصال شبکه‌ای یا TLS به پروایدر برقرار نشد. خطای موقت است."
    if code == 404:
        return CHECK_FAILED, STAGE_MODEL_MISSING, "این مدل روی این پروایدر پیدا نشد."
    if code == 429:
        return CHECK_FAILED, STAGE_TRANSIENT, "محدودیت نرخ درخواست (429). خطای موقت؛ ناسازگاری تشخیص داده نشد."
    if code >= 500:
        return CHECK_FAILED, STAGE_TRANSIENT, "سرویس پروایدر موقتاً خطا داد (5xx). خطای موقت؛ ناسازگاری تشخیص داده نشد."
    if capability == CAP_VISION and code in (400, 422) and _MODALITY_REJECT_RE.search(text):
        return CHECK_INCOMPATIBLE, STAGE_INCOMPATIBLE, "این مدل ورودی تصویر را صریحاً نمی‌پذیرد."
    if code:
        return CHECK_FAILED, STAGE_MODEL_RUN, f"اجرای مدل ناموفق بود (HTTP {code})."
    return CHECK_INCONCLUSIVE, STAGE_INCONCLUSIVE, "نتیجه نامشخص: خطای ناشناخته؛ ناسازگاری تشخیص داده نشد."


async def run_model_check(provider_name: str, model_id: str, capability: str) -> dict:
    """تست واقعی یک مدل با همان مسیر فراخوانی مصرف‌کننده‌ها.

    موفق فقط وقتی است که پاسخ معتبر از همان مدل درخواستی برسد.
    پاسخ از مدل دیگر یا پاسخ خالی «نامشخص» است (نه ناسازگار).
    تولید تصویر هزینه‌بر است و اجرا نمی‌شود؛ نتیجه‌اش «تست نشده» ثبت می‌شود.
    """
    from giso import ai_brain
    provider_name = str(provider_name or "").strip().lower()
    model_id = str(model_id or "").strip()
    result = {"provider": provider_name, "model": model_id, "capability": capability,
              "ok": False, "stage": "config", "result": CHECK_FAILED, "message": "",
              "provider_connection": False}
    if capability not in CAPABILITIES:
        result["message"] = "نوع قابلیت نامعتبر است."
        return result
    row = ai_brain.get_ai_provider(provider_name)
    if row is None:
        result["message"] = "پروایدر پیدا نشد."
        return result
    if not ai_brain._col(row, "enabled", 0):
        result["message"] = "پروایدر غیرفعال است؛ ابتدا آن را فعال کنید."
        return result
    api_key = str(ai_brain._col(row, "api_key", "") or "").strip()
    if not api_key:
        result["message"] = "کلید API برای این پروایدر ثبت نشده است."
        return result

    if capability == CAP_IMAGE_GEN:
        detail = "تست تولید تصویر انجام نشد: تولید تصویر هزینه‌بر است و در این بخش اجرا نمی‌شود."
        _save_check(provider_name, model_id, capability, CHECK_NOT_TESTED, "not_tested", detail)
        result.update({"stage": "not_tested", "result": CHECK_NOT_TESTED, "message": detail})
        return result

    probe_path = None
    try:
        if capability == CAP_TEXT:
            reply = await ai_brain.ask_ai(
                provider_name, [{"role": "user", "content": _PROBE_PROMPT}],
                model=model_id, temperature=0.0, max_tokens=8,
            )
        else:
            probe_path = _probe_png_path()
            reply = await ai_brain.ask_ai_vision(
                provider_name, probe_path, _PROBE_PROMPT, model=model_id, max_tokens=8,
            )
    except Exception as exc:  # خطای غیرمنتظره: بدون پیام خام
        reply = {"ok": False, "error": f"{type(exc).__name__}"}
    finally:
        if probe_path:
            try:
                import os
                os.remove(probe_path)
            except OSError:
                pass

    reply = reply or {}
    answered_model = str(reply.get("model") or "")
    text_ok = bool(str(reply.get("text") or "").strip())
    if reply.get("ok") and text_ok and answered_model == model_id:
        detail = "پاسخ معتبر از همین مدل دریافت شد."
        _save_check(provider_name, model_id, capability, CHECK_OK, "ok", detail)
        result.update({"ok": True, "stage": "ok", "result": CHECK_OK, "message": detail,
                       "provider_connection": True})
        return result

    if reply.get("ok") and answered_model and answered_model != model_id:
        result_kind, stage = CHECK_INCONCLUSIVE, STAGE_INCONCLUSIVE
        explanation = f"پاسخ از مدل دیگری ({answered_model}) آمد؛ این مدل تست نشد."
    elif reply.get("ok"):
        result_kind, stage = CHECK_INCONCLUSIVE, STAGE_INCONCLUSIVE
        explanation = "پاسخ خالی برگشت؛ نتیجه نامشخص است."
    else:
        raw_error = redact_secrets(reply.get("error") or "", secrets=(api_key,))
        result_kind, stage, explanation = _classify_check_error(raw_error, capability)
        explanation = f"{explanation} ({raw_error})" if raw_error else explanation
    _save_check(provider_name, model_id, capability, result_kind, stage, explanation)
    result.update({"stage": stage, "result": result_kind, "message": explanation,
                   "provider_connection": stage not in PROVIDER_CONNECTION_STAGES})
    return result
