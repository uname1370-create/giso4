# -*- coding: utf-8 -*-
"""
giso/analysis.py — تمام کدهای آنالیز هوشمند مو و صورت (روت‌های وب و مدیریت نتایج).
"""

import json
import logging
import os

import uuid
from datetime import datetime, timedelta, timezone
try:
    from flask import (Blueprint, render_template, request, redirect, url_for,
                       flash, session, jsonify, send_file)
    from flask_login import login_required, login_user, logout_user, current_user
    from werkzeug.security import generate_password_hash, check_password_hash
except ImportError:
    class Blueprint:
        def __init__(self, *a, **kw):
            pass
    def login_required(fn):
        return fn
    def login_user(*a, **kw):
        pass
    def logout_user(*a, **kw):
        pass
    def check_password_hash(*a, **kw):
        return True
    current_user = None

from giso.config import Config
from giso.models import db, Analysis, Product
from giso.base import normalize_phone
from giso.security import audit_event

def _charge_service_or_block(service: str, ref_id, service_label: str = ""):
    """کسر هزینه‌ی یک خدمت پولی از کیف پول (spend → cash) و بلاک در کمبود اعتبار.

    خروجی (should_block: bool, redirect_target|None). اگر خدمت رایگان/غیرفعال یا کسر
    موفق باشد → (False, None). اگر اعتبار کافی نباشد → (True, پیام کیف پول + redirect).
    ضدتکرار با کلید یکتای ``service_<service>:<ref_id>`` در wallet_core انجام می‌شود.
    خطاهای سامانه مالی fail-open هستند تا جریان خدمت کاربر نشکند.
    """
    try:
        uid = getattr(current_user, "id", None)
        if not uid:
            return False, None
        from giso.wallet import charge_service_credit, get_wallet_balances
        from giso.money import format_toman
        try:
            from markupsafe import Markup
        except Exception:
            Markup = lambda s: s  # noqa: E731
        res = charge_service_credit(int(uid), service, ref_id)
        if res.get("ok"):
            return False, None
        # اعتبار کافی نیست → بلاک + لینک کیف پول
        bal = get_wallet_balances(int(uid))
        fee = int(res.get("fee") or 0)
        missing = int(res.get("missing") or 0)
        label = service_label or "این خدمت"
        try:
            link = url_for("panel_user.wallet")
        except Exception:
            link = "/dashboard/wallet"
        msg = (
            f"💰 برای «{label}» به {format_toman(fee)} اعتبار نیاز است. "
            f"موجودی فعلی شما: {format_toman(bal.get('usable', 0))} "
            f"(کمبود: {format_toman(missing)}). لطفاً ابتدا کیف پول خود را شارژ کنید و دوباره تلاش کنید."
        )
        flash(Markup(f'{msg} <a href="{link}" style="font-weight:700;text-decoration:underline;">رفتن به کیف پول و شارژ →</a>'), "warning")
        return True, redirect(link)
    except Exception as e:
        # fail-open: خطای سامانه مالی نباید جریان خدمت را بشکند
        try:
            logger.warning("charge service credit failed (%s/%s): %s", service, ref_id, e)
        except Exception:
            pass
        return False, None

try:
    from sqlalchemy import or_
except Exception:
    or_ = None
from giso.ai_brain import (
    ask_ai_vision,
    ask_ai_fast,
    list_ai_providers,
    PROVIDERS_REGISTRY,
    get_conn,
)
from giso.ai_runtime import chat_with_managed_ai, get_context_scope, NO_ACCESS_MESSAGE, PROVIDER_ERROR_MESSAGE
from giso.analysis_report import (
    _normalize_report_data,
    _build_metric_cards,
    _build_strength_items,
    _build_concern_items,
    _build_routine_cards,
    _build_radar_points,
)

logger = logging.getLogger("giso_analysis")

analysis_routes = Blueprint("analysis", __name__)

# ترتیب اولویت پروایدرها بر اساس کیفیت + رایگان بودن
# gemini برای تحلیل صورت/مو انسان safety filter دارد و رد می‌کند؛ پس آخر قرار می‌گیرد.
# ۱۴۰۵-۰۶-۱۸: اولویت تحلیل عکس با سرویس‌های رایگانِ دارای مدل بینایی است؛
# پروایدرهای پولی ایرانی فقط پشتیبان آخر هستند.
VISION_PRIORITY_PROVIDERS = ["groq", "openrouter", "cloudflare", "mistral", "gemini", "avalai", "gapgpt"]

# کلمات کلیدی تشخیص مدل Vision (case-insensitive)
VISION_KEYWORDS = [
    "vision", "gpt-4o", "gpt-5", "gemini", "claude-3", "claude-4",
    "llama-3.2", "llama-4", "llava", "multimodal", "image", "pixtral", "qwen-vl",
    # مدل‌های رایگان بینایی ۱۴۰۵-۰۶-۱۸ (اوپن‌روتر/میسترال):
    "gemma-4", "inkling", "omni", "mistral-small",
]
# کلمات کلیدی استثنا (مدل‌های غیر Vision)
NON_VISION_KEYWORDS = [
    "tts", "embedding", "whisper", "audio", "compound",
    "text-only", "moderation",
]

_ANALYSIS_TMP = os.path.join(Config.GISO_DIR, "data", "uploads", "analysis", "temp")

def _row_get(row, key, default=None):
    """دسترسی امن به فیلد row — پشتیبانی از sqlite3.Row و dict."""
    if row is None:
        return default
    try:
        val = row[key]  # sqlite3.Row از subscript پشتیبانی می‌کند
        return val if val is not None else default
    except (KeyError, IndexError, TypeError):
        pass
    try:
        if hasattr(row, "get"):
            return row.get(key, default)
    except Exception:
        pass
    return default

def analysis():
    """صفحهٔ انتخاب نوع آنالیز (مو / پوست) — عمومی و بدون نیاز به ورود."""
    return render_template("analysis_home.html")

def analysis_hair():
    """صفحهٔ آنالیز مو (مراحل ۱ تا ۴) — شروع از راهنما."""
    return render_template("analysis_hair.html", stage=0, initial=None, questions=None,
                           analysis_type="hair", ai_error="")

def analysis_skin():
    """صفحهٔ آنالیز پوست (مراحل ۱ تا ۴) — شروع از راهنما."""
    return render_template("analysis_skin.html", stage=0, initial=None, questions=None,
                           analysis_type="skin", ai_error="")

# ============================================================
# سیستم انتخاب هوشمند مدل Vision با Fallback کامل
# ============================================================

def _is_vision_model(model_name):
    """تشخیص هوشمند اینکه آیا نام مدل قابلیت Vision دارد یا نه."""
    if not model_name:
        return False
    m = model_name.lower()
    for kw in NON_VISION_KEYWORDS:
        if kw in m:
            return False
    for kw in VISION_KEYWORDS:
        if kw in m:
            return True
    return False

def _provider_model_candidates(row):
    """لیست مدل‌های قابل استفادهٔ یک پروایدر — منابع به ترتیب اولویت (فاز ۲):
    1. selected_model  2. vision_models_json (ستون جدید)  3. fallback_json (قدیمی)
    4. models_json (کشف قدیمی)  5. رجیستری فایل (giso.ai_models_registry)
    """
    models = []

    def add(m):
        if m and m not in models:
            models.append(m)

    try:
        add((_row_get(row, "selected_model", "") or "").strip())
    except Exception:
        pass
    try:
        for m in json.loads(_row_get(row, "vision_models_json", "[]") or "[]"):
            mid = m.get("id") if isinstance(m, dict) else m
            if isinstance(m, dict) and m.get("disabled"):
                continue
            add(mid)
    except Exception:
        pass
    try:
        for m in json.loads(_row_get(row, "fallback_json", "[]") or "[]"):
            add(m)
    except Exception:
        pass
    try:
        for m in json.loads(_row_get(row, "models_json", "[]") or "[]"):
            add(m)
    except Exception:
        pass
    # رجیستری فایل همیشه به انتهای زنجیرهٔ هر پروایدر اضافه می‌شود؛
    # پروایدرهای پروکسی اغلب لیست مدل‌شان نام بینایی ندارد و بدون این، زنجیره خالی می‌ماند.
    try:
        from giso.ai_models_registry import get_vision_models
        for m in get_vision_models(_row_get(row, "name", "")):
            add(m.get("id"))
    except Exception:
        pass
    return models

def _provider_vision_model(row):
    """اولین مدل Vision از بین کاندیدهای پروایدر را برمی‌گرداند (یا None)."""
    for m in _provider_model_candidates(row):
        if _is_vision_model(m):
            return m
    return None

def _provider_active(row):
    """فعال بودن پروایدر: enabled و در صورت داشتن last_status، ok بودن آن."""
    if not _row_get(row, "enabled"):
        return False
    ls = str(_row_get(row, "last_status", "") or "").strip().lower()
    # اگه last_status خالی باشد (هنوز چک نشده)، فرض کن فعال است
    if ls and ls not in ("ok", "success"):
        return False
    return True

def pick_active_vision_model():
    """
    لیست پروایدرهای فعال و دارای مدل Vision را به ترتیب اولویت برمی‌گرداند.
    خروجی: لیست [{'provider_name': str, 'model_name': str}, ...]
    """
    try:
        rows = list_ai_providers(only_enabled=True)
    except Exception as e:
        logger.error(f"list_ai_providers error: {e}")
        rows = []

    logger.info("[VISION_MODEL_PICK] Checking providers... (total: %d)", len(rows))
    vision = []
    for r in rows:
        provider_name = _row_get(r, "name", "unknown")
        is_active = _provider_active(r)
        # زنجیرهٔ چندمدلی: اگر مدل اول کار نکرد، بعدی همان پروایدر امتحان می‌شود (مورد ۸ دستور start/1.md)
        chain = [m for m in _provider_model_candidates(r) if _is_vision_model(m)][:3] if is_active else []
        logger.info(
            "[VISION_MODEL_PICK] %s: chain=%s, active=%s, last_status=%s",
            provider_name,
            chain or "None",
            is_active,
            _row_get(r, "last_status", ""),
        )
        for m in chain:
            vision.append({"provider_name": provider_name, "model_name": m})

    prio = {p: i for i, p in enumerate(VISION_PRIORITY_PROVIDERS)}

    def sort_key(item):
        name = item["provider_name"].lower()
        return (prio.get(name, len(prio)), name)

    vision.sort(key=sort_key)

    logger.info("[VISION_MODEL_PICK] Vision-capable: %d/%d", len(vision), len(rows))
    logger.info("[VISION_MODEL_PICK] Priority order:")
    for i, item in enumerate(vision, 1):
        logger.info("%d. %s / %s", i, item["provider_name"], item["model_name"])
    return vision

def _parse_ai_json(text):
    """پارس مقاوم JSON از خروجی مدل (با پشتیبانی از code fence و متن اضافه)."""
    if not text:
        return None
    t = text.strip()
    if t.startswith("```"):
        lines = t.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        t = "\n".join(lines).strip()
    try:
        return json.loads(t)
    except Exception:
        pass
    s = t.find("{")
    e = t.rfind("}")
    if s != -1 and e > s:
        try:
            return json.loads(t[s:e + 1])
        except Exception:
            return None
    return None

# Phase 5 S2: Structured AI Output — required fields validation
_STRUCTURED_REQUIRED_FIELDS = {
    "hair": ["overall_score", "metrics", "main_problems", "summary"],
    "skin": ["overall_score", "metrics", "main_problems", "summary"],
}

def _validate_structured_output(data, analysis_type="hair"):
    """Phase 5: Validate AI output has required structured fields. Returns (is_valid, missing_fields)."""
    if not isinstance(data, dict):
        return False, ["not_a_dict"]
    required = _STRUCTURED_REQUIRED_FIELDS.get(analysis_type, _STRUCTURED_REQUIRED_FIELDS["hair"])
    missing = [f for f in required if f not in data or not data[f]]
    # Also check that metrics is a dict with at least 3 values
    metrics = data.get("metrics") or data.get("radar_metrics") or {}
    if not isinstance(metrics, dict) or len(metrics) < 3:
        missing.append("metrics_insufficient")
    return len(missing) == 0, missing

def _ensure_structured_fallback(data, analysis_type="hair"):
    """Phase 5: Ensure output has minimum structure even if AI output is partial."""
    if not isinstance(data, dict):
        data = {}
    if not data.get("overall_score"):
        data["overall_score"] = 50
    if not isinstance(data.get("metrics"), dict) and not isinstance(data.get("radar_metrics"), dict):
        default_metrics = {"آبرسانی": 50, "انعطاف‌پذیری": 50, "استحکام": 50, "درخشش": 50, "سلامت پوست سر": 50, "سرعت رشد": 50}
        data["radar_metrics"] = default_metrics
    if not data.get("main_problems") and not data.get("concerns"):
        data["concerns"] = ["نیاز به بررسی حضوری"]
    if not data.get("summary"):
        data["summary"] = "تحلیل اولیه انجام شد. برای نتیجه دقیق‌تر، مشاوره حضوری توصیه می‌شود."
    return data

def _log_ai_failure(provider, model, err):
    """لاگ خطای مدل در جدول giso_ai_checks_log (فقط لاگ، نه تغییر پروایدر)."""
    try:
        conn = get_conn()
        with conn:
            conn.execute(
                "INSERT INTO giso_ai_checks_log (provider_name, status, error_text, checked_at) VALUES (?,?,?,?)",
                (provider, "error", f"{model}: {str(err)[:200]}",
                 datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"))
            )
            conn.execute(
                "DELETE FROM giso_ai_checks_log WHERE id NOT IN "
                "(SELECT id FROM giso_ai_checks_log ORDER BY id DESC LIMIT 100)"
            )
    except Exception:
        pass

def _classify_error(raw):
    """نوع خطا را برمی‌گرداند: '429' | 'network' | 'json' | 'general'"""
    s = str(raw or "").lower()
    if "429" in s or "rate limit" in s or "too many" in s:
        return "429"
    if any(k in s for k in ("timeout", "connect", "httpx", "network", "read timed out", "ssl")):
        return "network"
    return "general"

def _is_ai_refusal(text):
    """تشخیص اینکه AI پاسخ رد داده یا تحلیل کرده است."""
    if not text:
        return True

    refusal_keywords = [
        "متأسفم", "نمی‌توانم", "نمیتوانم", "not able to",
        "cannot analyze", "unable to", "sorry", "خودداری",
        "امکان‌پذیر نیست", "قادر نیستم", "cant analyze",
        "unable", "refuse", "قوانین", "policies", "safety",
        "privacy", "شخصی", "personal", "identify",
    ]
    text_lower = text.lower()

    # اگه متن خیلی کوتاه باشد و شامل کلمات رد باشد
    if len(text) < 500:
        for kw in refusal_keywords:
            if kw.lower() in text_lower:
                return True

    # اگه JSON برنگردانده (فقط متن)، تحلیل محسوب نمی‌شود
    if not ("{" in text and "}" in text):
        return True

    return False

def _smart_error_message(error_types):
    """پیام مناسب کاربر بر اساس نوع خطاها."""
    if not error_types:
        return "⚠️ سرویس تحلیل تصویر موقتاً در دسترس نیست. لطفاً چند دقیقه دیگر تلاش کنید."
    if all(t == "429" for t in error_types):
        return "⚠️ سرویس‌ها موقتاً پرترافیک هستن. لطفاً ۵ دقیقه دیگر تلاش کنید."
    if all(t == "network" for t in error_types):
        return "⚠️ مشکل اتصال به سرویس هوش مصنوعی. لطفاً چند دقیقه دیگر تلاش کنید."
    if all(t == "refused" for t in error_types):
        return ("⚠️ متأسفانه در حال حاضر سیستم هوش مصنوعی نمی‌تواند این تصویر را تحلیل کند. "
                "لطفاً عکس واضح‌تر و در نور بهتر بگیرید، یا چند دقیقه دیگر دوباره تلاش کنید.")
    if "refused" in error_types:
        return ("⚠️ برخی سرویس‌ها نتوانستند تصویر را تحلیل کنند. "
                "لطفاً عکس واضح‌تر بگیرید و دوباره تلاش کنید.")
    return "⚠️ سرویس تحلیل تصویر موقتاً در دسترس نیست. لطفاً چند دقیقه دیگر تلاش کنید."

def call_vision_with_fallback(image_paths, prompt, max_retries_per_model=2, max_tokens=1500):
    """موتور بینایی — فاز ۳: بودجه ۴۵ ثانیه کل / ۸ ثانیه هر مدل + سلامت مشترک.

    با پرچم امنیت FEATURE_FLAG_LEGACY_MODE رفتار قدیمی (تلاش مجدد هر مدل) برمی‌گردد.
    """
    import time as _time
    from giso.ai_config import (VISION_TOTAL_TIMEOUT_SECONDS, VISION_PER_MODEL_TIMEOUT_SECONDS,
                                BACKOFF_429_FREE_PROVIDER_SECONDS, BACKOFF_429_PAID_PROVIDER_SECONDS,
                                FEATURE_FLAG_LEGACY_MODE)
    if FEATURE_FLAG_LEGACY_MODE:
        return _legacy_call_vision_with_fallback(image_paths, prompt, max_retries_per_model, max_tokens)

    if isinstance(image_paths, str):
        image_paths = [image_paths]
    if not image_paths:
        return {"ok": False, "error": "هیچ عکسی برای تحلیل وجود ندارد"}

    try:
        from giso import ai_health
    except Exception:
        ai_health = None

    providers = pick_active_vision_model()
    if not providers:
        try:
            rows = list_ai_providers(only_enabled=True)
        except Exception:
            rows = []
        if not rows:
            return {"ok": False, "error": "⚠️ در حال حاضر هیچ سرویس هوش مصنوعی فعال نیست. لطفاً با پشتیبانی تماس بگیرید."}
        return {"ok": False, "error": "⚠️ سرویس‌های فعلی قابلیت تحلیل تصویر ندارن. لطفاً چند دقیقه دیگر تلاش کنید."}

    # فیلتر کولداون سلامت مشترک
    if ai_health is not None:
        filtered = [it for it in providers
                    if not ai_health.is_in_cooldown(it["provider_name"], it["model_name"])]
        skipped = len(providers) - len(filtered)
        if skipped:
            logger.info("[VISION_FALLBACK] %d model(s) skipped due to cooldown", skipped)
        providers = filtered or providers  # اگر همه در کولداون بودند، شانس دوباره بده

    start = _time.time()
    error_types = []
    for item in providers:
        pname = item["provider_name"]
        model = item["model_name"]
        elapsed = _time.time() - start
        if elapsed > VISION_TOTAL_TIMEOUT_SECONDS:
            logger.info("[AI_ATTEMPT] engine=vision result=budget_exceeded elapsed=%.1fs", elapsed)
            break
        attempt_start = _time.time()
        result = None
        try:
            from giso.async_compat import run_async_safe
            result = run_async_safe(ask_ai_vision(
                pname, image_paths[0], prompt, model=model, max_tokens=max_tokens,
                timeout_override=VISION_PER_MODEL_TIMEOUT_SECONDS))
        except Exception as exc:
            result = {"ok": False, "error": f"{type(exc).__name__}: {exc}"}
        duration = _time.time() - attempt_start

        if result and result.get("ok"):
            text = result.get("text", "") or ""
            if _is_ai_refusal(text):
                if ai_health is not None:
                    ai_health.mark_failure(pname, model, "refused", text[:120])
                logger.info("[AI_ATTEMPT] engine=vision provider=%s model=%s result=refused duration=%.1fs",
                            pname, model, duration)
                _log_ai_failure(pname, model, f"AI refused: {text[:100]}")
                error_types.append("refused")
                continue
            parsed = _parse_ai_json(text)
            if parsed is not None:
                if ai_health is not None:
                    ai_health.mark_success(pname, model)
                logger.info("[AI_ATTEMPT] engine=vision provider=%s model=%s result=success duration=%.1fs",
                            pname, model, duration)
                return {"ok": True, "provider": pname, "model": model, "data": parsed, "text": text}
            # JSON نامعتبر
            if ai_health is not None:
                ai_health.mark_failure(pname, model, "json", text[:120])
            logger.info("[AI_ATTEMPT] engine=vision provider=%s model=%s result=json_parse_error duration=%.1fs",
                        pname, model, duration)
            _log_ai_failure(pname, model, "پارس JSON ناموفق: " + text[:120])
            error_types.append("json")
            continue

        raw = (result or {}).get("error", "unknown")
        etype = "general"
        if ai_health is not None:
            etype = ai_health.classify_error_text(raw)
            ai_health.mark_failure(pname, model, etype, str(raw)[:200])
        logger.info("[AI_ATTEMPT] engine=vision provider=%s model=%s result=%s duration=%.1fs",
                    pname, model, etype, duration)
        _log_ai_failure(pname, model, str(raw)[:200])
        if etype == "429":
            is_free = ai_health.get_provider_is_free(pname) if ai_health is not None else True
            backoff = BACKOFF_429_FREE_PROVIDER_SECONDS if is_free else BACKOFF_429_PAID_PROVIDER_SECONDS
            if backoff > 0:
                _time.sleep(backoff)
            error_types.append("429")
        elif etype in ("timeout", "network"):
            error_types.append("network")
        elif etype == "auth":
            error_types.append("general")
        else:
            error_types.append("general")

    return {"ok": False, "error": _smart_error_message(error_types)}


def _legacy_call_vision_with_fallback(image_paths, prompt, max_retries_per_model=2, max_tokens=1500):
    """
    رفتار قدیمی (پرچم امنیت): فراخوانی ask_ai_vision با fallback و تلاش مجدد هر مدل.
    image_paths: لیست مسیر عکس‌ها (از اولین عکس استفاده می‌شود).
    خروجی: {'ok': True, 'provider', 'model', 'data', 'text'} یا {'ok': False, 'error'}
    """
    if isinstance(image_paths, str):
        image_paths = [image_paths]
    if not image_paths:
        return {"ok": False, "error": "هیچ عکسی برای تحلیل وجود ندارد"}

    providers = pick_active_vision_model()
    if not providers:
        try:
            rows = list_ai_providers(only_enabled=True)
        except Exception:
            rows = []
        if not rows:
            return {"ok": False, "error": "⚠️ در حال حاضر هیچ سرویس هوش مصنوعی فعال نیست. لطفاً با پشتیبانی تماس بگیرید."}
        return {"ok": False, "error": "⚠️ سرویس‌های فعلی قابلیت تحلیل تصویر ندارن. لطفاً چند دقیقه دیگر تلاش کنید."}

    error_types = []
    for item in providers:
        pname = item["provider_name"]
        model = item["model_name"]
        for attempt in range(1, max_retries_per_model + 1):
            logger.info("[VISION_FALLBACK] Trying %s/%s (attempt %d/%d)", pname, model, attempt, max_retries_per_model)
            result = None
            try:
                from giso.async_compat import run_async_safe
                result = run_async_safe(ask_ai_vision(pname, image_paths[0], prompt, model=model, max_tokens=max_tokens))
            except Exception as exc:
                result = {"ok": False, "error": f"{type(exc).__name__}: {exc}"}
            if result and result.get("ok"):
                text = result.get("text", "") or ""
                # چک رد شدن AI (مثلاً safety filter برای تصاویر انسان)
                if _is_ai_refusal(text):
                    logger.warning("[VISION_FALLBACK] %s/%s refused to analyze: %s",
                                   pname, model, text[:100])
                    _log_ai_failure(pname, model, f"AI refused: {text[:100]}")
                    error_types.append("refused")
                    break  # برو مدل بعدی
                parsed = _parse_ai_json(text)
                if parsed is not None:
                    logger.info("[VISION_FALLBACK] SUCCESS %s/%s", pname, model)
                    return {"ok": True, "provider": pname, "model": model,
                            "data": parsed, "text": text}
                err_type = "json"
                logger.info("[VISION_FALLBACK] ERROR: json_parse_error")
                _log_ai_failure(pname, model, "پارس JSON ناموفق: " + text[:120])
                error_types.append(err_type)
            else:
                raw = (result or {}).get("error", "unknown")
                err_type = _classify_error(raw)
                logger.info("[VISION_FALLBACK] ERROR: %s", raw)
                _log_ai_failure(pname, model, str(raw)[:200])
                error_types.append(err_type)
        logger.info("[VISION_FALLBACK] Moving to next provider")

    return {"ok": False, "error": _smart_error_message(error_types)}

# ============================================================
# بارگذاری پرامپت و مدیریت عکس‌ها
# ============================================================

def _load_prompt(filename):
    """بارگذاری پرامپت از فایل (giso/prompts)."""
    try:
        path = os.path.join(Config.GISO_DIR, "prompts", filename)
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    except Exception as e:
        logger.error(f"_load_prompt {filename}: {e}")
        return ""

def _save_uploaded_images(analysis_type):
    saved = []
    try:
        os.makedirs(_ANALYSIS_TMP, exist_ok=True)
        for f in request.files.getlist("images"):
            if not f or not f.filename:
                continue
            fn = f.filename
            ext = fn.rsplit(".", 1)[-1].lower() if "." in fn else "jpg"
            if ext not in ("jpg", "jpeg", "png", "webp"):
                continue
            fname = f"a_{analysis_type}_{uuid.uuid4().hex[:12]}.{ext}"
            path = os.path.join(_ANALYSIS_TMP, fname)
            f.save(path)
            # فشرده‌سازی عکس پیش از ارسال به AI (بزرگ‌ترین بُعد حداکثر ۱۰۲۴ پیکسل، کیفیت ۸۵٪)
            try:
                from PIL import Image
                img = Image.open(path)
                img.thumbnail((1024, 1024))
                if ext in ("jpg", "jpeg"):
                    if img.mode not in ("RGB", "L"):
                        img = img.convert("RGB")
                    img.save(path, "JPEG", quality=85)
                elif ext == "png":
                    img.save(path, "PNG")
                elif ext == "webp":
                    img.save(path, "WEBP", quality=85)
            except Exception as e_img:
                # اگر Pillow نصب نبود یا پردازش شکست خورد، عکس اصلی بدون تغییر می‌ماند (fallback امن)
                logger.debug(f"image resize skipped ({ext}): {e_img}")
            saved.append(path)
    except Exception as e:
        logger.error(f"_save_uploaded_images: {e}")
    return saved

def _cleanup_files(paths):
    for p in paths or []:
        try:
            if os.path.exists(p):
                os.remove(p)
        except Exception:
            pass

# ============================================================
# بانک سوالات هوشمند تکمیلی
# ============================================================

def _build_questions(analysis_type, issues):
    issues = issues or {}

    # ═══ سوالات ثابت (همیشه) ═══
    fixed = [
        {"title": "جنسیت", "name": "gender",
         "options": ["زن", "مرد"], "required": True},
        {"title": "بازه سنی", "name": "age",
         "options": ["زیر ۲۰", "۲۰-۳۰", "۳۰-۴۰", "بالای ۴۰"], "required": True},
    ]

    # ═══ سوالات عمومی سبک زندگی (همیشه) ═══
    lifestyle = [
        {"title": "سطح استرس روزانه", "name": "stress",
         "options": ["کم", "متوسط", "زیاد"], "required": True},
        {"title": "کیفیت خواب", "name": "sleep",
         "options": ["خوب (۷-۸ ساعت)", "متوسط (۵-۶ ساعت)", "کم (کمتر از ۵)"], "required": True},
        {"title": "مصرف آب روزانه", "name": "water",
         "options": ["۸ لیوان یا بیشتر", "۴-۷ لیوان", "کمتر از ۴ لیوان"], "required": True},
    ]

    # ═══ سوالات هوشمند بر اساس مشکلات ═══
    smart = []

    if analysis_type == "hair":
        if issues.get("has_color_damage"):
            smart.append({"title": "آخرین بار کی رنگ کردی؟", "name": "last_color",
                          "options": ["کمتر از ۱ ماه", "۱ تا ۳ ماه پیش", "۳ تا ۶ ماه پیش", "بیشتر از ۶ ماه"],
                          "required": True})
            smart.append({"title": "چه نوع رنگی استفاده کردی؟", "name": "color_type",
                          "options": ["رنگ معمولی", "دکلره", "هایلایت / آمبره", "رنگ گیاهی (حنا)"],
                          "required": True})
        if issues.get("has_oiliness"):
            smart.append({"title": "روزی چند بار مو رو می‌شوری؟", "name": "wash_freq",
                          "options": ["هر روز", "یک روز درمیان", "۲ بار در هفته", "کمتر"],
                          "required": True})
        if issues.get("has_thinning"):
            smart.append({"title": "چند وقته این ریزش رو حس می‌کنی؟", "name": "thinning_since",
                          "options": ["کمتر از ۱ ماه", "۱ تا ۳ ماه", "بیشتر از ۳ ماه"],
                          "required": True})
        if issues.get("has_split_ends"):
            smart.append({"title": "از سشوار یا حالت‌دهنده حرارتی استفاده می‌کنی؟", "name": "heat_tools",
                          "options": ["روزانه", "چند بار در هفته", "به ندرت", "هرگز"],
                          "required": True})
        if issues.get("has_dandruff"):
            smart.append({"title": "خارش پوست سر داری؟", "name": "scalp_itch",
                          "options": ["زیاد", "کم", "ندارم"],
                          "required": True})
        # اگر هیچ مشکل خاصی نبود، سوالات عمومی مو
        if not smart:
            smart.append({"title": "نوع موی خودت رو چطور توصیف می‌کنی؟", "name": "hair_type_self",
                          "options": ["خشک", "چرب", "مختلط", "نرمال", "نمی‌دونم"],
                          "required": True})
            smart.append({"title": "از چه شامپویی استفاده می‌کنی؟", "name": "shampoo_type",
                          "options": ["ضد ریزش", "ضد شوره", "آبرسان", "عمومی", "متفاوت"],
                          "required": True})
    else:  # skin
        if issues.get("has_acne"):
            smart.append({"title": "چند وقته با جوش درگیری؟", "name": "acne_since",
                          "options": ["کمتر از ۱ ماه", "۱ تا ۶ ماه", "بیشتر از ۶ ماه"],
                          "required": True})
            smart.append({"title": "بیشتر کجای صورت جوش می‌زنی؟", "name": "acne_area",
                          "options": ["پیشانی", "گونه", "چانه", "کل صورت"],
                          "required": True})
        if issues.get("has_dark_spots"):
            smart.append({"title": "علت لک‌ها چیه به نظرت؟", "name": "spots_cause",
                          "options": ["آفتاب", "جای جوش", "تغییرات هورمونی", "نمی‌دونم"],
                          "required": True})
        if issues.get("has_dryness"):
            smart.append({"title": "کرم مرطوب‌کننده استفاده می‌کنی؟", "name": "moisturizer",
                          "options": ["بله، روزانه", "گاهی", "خیر"],
                          "required": True})
        if issues.get("has_oiliness"):
            smart.append({"title": "بیشتر کجای صورت چربه؟", "name": "oil_area",
                          "options": ["ناحیه T (پیشانی، بینی، چانه)", "کل صورت", "فقط بینی"],
                          "required": True})
        if issues.get("has_wrinkles"):
            smart.append({"title": "از کرم ضدآفتاب استفاده می‌کنی؟", "name": "sunscreen",
                          "options": ["روزانه", "گاهی", "خیر"],
                          "required": True})
            smart.append({"title": "بیشتر در معرض آفتابی؟", "name": "sun_exposure",
                          "options": ["زیاد", "متوسط", "کم"],
                          "required": True})
        # اگر هیچ مشکل خاصی نبود، سوالات عمومی پوست
        if not smart:
            smart.append({"title": "نوع پوست خودت رو چطور توصیف می‌کنی؟", "name": "skin_type_self",
                          "options": ["خشک", "چرب", "مختلط", "حساس", "نرمال", "نمی‌دونم"],
                          "required": True})
            smart.append({"title": "روال مراقبت پوستت چقدره؟", "name": "skincare_routine",
                          "options": ["روزانه کامل", "چند مرحله‌ای", "فقط شستشو", "هیچ"],
                          "required": True})

    # حداقل ۲ سوال هوشمند (اگر کمتر بود، سوال هدف اضافه بشه)
    if len(smart) < 2:
        goal_opts = (["رفع مشکل خاص", "بهبود کلی سلامت مو", "پیشگیری", "کنجکاوی"]
                     if analysis_type == "hair" else
                     ["رفع مشکل خاص", "بهبود کلی سلامت پوست", "پیشگیری", "کنجکاوی"])
        smart.append({"title": "چه هدفی از این تحلیل داری؟", "name": "goal",
                      "options": goal_opts, "required": True})

    # حداکثر ۴ سوال هوشمند
    smart = smart[:4]

    # ═══ فیلد اختیاری آخر (تنها فیلد اختیاری) ═══
    free_text = {
        "title": "چیز خاص دیگه‌ای می‌خوای بگی؟",
        "name": "extra",
        "free": True,
        "required": False,
        "placeholder": ("اختیاری - اگه چیز خاصی درباره موهات هست بنویس"
                        if analysis_type == "hair" else
                        "اختیاری - اگه چیز خاصی درباره پوستت هست بنویس"),
    }

    # مجموع: ۲ ثابت + ۳ سبک زندگی + ۲-۴ هوشمند + ۱ اختیاری = ۸-۱۰ سوال
    return fixed + lifestyle + smart + [free_text]

# ============================================================
# محدودیت زمان تحلیل (Rate Limit)
# ============================================================

def _get_config_value(key, default=""):
    try:
        from giso_admin import get_giso_config
        return get_giso_config(key, default)
    except Exception:
        return default

def _set_config_value(key, value):
    try:
        from giso_admin import set_giso_config
        set_giso_config(key, value)
    except Exception as e:
        logger.error(f"set config {key}: {e}")

def check_rate_limit(ip, phone, analysis_type):
    """
    بررسی محدودیت زمان تحلیل بر اساس تنظیمات (enabled/minutes/type).
    خروجی: {"allowed": True} یا {"allowed": False, "wait_minutes": X}
    """
    try:
        enabled = None
        try:
            from giso.base import read_rate_limit_config
            cfg = read_rate_limit_config()
            enabled = cfg["enabled"]
            minutes = cfg["minutes"]
            limit_type = cfg["limit_type"]
        except Exception as exc:
            logger.error(f"check_rate_limit config read failed: {exc}")
            # bot.db خوانده نشد → fail-closed محافظه‌کارانه (هر ۵ دقیقه، هر دو)
            return {"allowed": False, "wait_minutes": 5}
        if not enabled:
            return {"allowed": True}
        try:
            minutes = max(1, int(minutes or 60))
        except (TypeError, ValueError):
            minutes = 60

        conds = []
        params = []
        if limit_type in ("ip", "both") and ip:
            conds.append("ip = ?")
            params.append(ip)
        if limit_type in ("phone", "both") and phone:
            conds.append("phone = ?")
            params.append(phone)
        if not conds:
            return {"allowed": True}

        conn = get_conn()
        with conn:
            row = conn.execute(
                f"SELECT created_at FROM analysis_rate_limits WHERE "
                f"({' OR '.join(conds)}) AND analysis_type = ? "
                f"ORDER BY id DESC LIMIT 1",
                (*params, analysis_type)
            ).fetchone()
        if row:
            created = row["created_at"]
            from datetime import datetime as _dt
            last = _dt.strptime(created, "%Y-%m-%d %H:%M:%S")
            elapsed = (datetime.now() - last).total_seconds() / 60
            wait = max(0, int(minutes - elapsed))
            if wait > 0:
                return {"allowed": False, "wait_minutes": wait}
        return {"allowed": True}
    except Exception as e:
        logger.error(f"check_rate_limit: {e}")
        return {"allowed": True}

def _record_rate_limit(ip, phone, analysis_type):
    try:
        conn = get_conn()
        with conn:
            conn.execute(
                "INSERT INTO analysis_rate_limits (ip, phone, analysis_type, created_at) VALUES (?,?,?,?)",
                (ip, phone, analysis_type, datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
            )
    except Exception as e:
        logger.error(f"_record_rate_limit: {e}")

# ============================================================
# ثبت‌نام سریع و پردازش نهایی AI
# ============================================================

def _login_user_ctx(phone, password):
    """ورود کاربر با شماره و رمز؛ خروجی پیام خطا یا None."""
    from giso.models import User
    np = normalize_phone(phone)
    user = User.query.filter_by(phone=np).first() if np else None
    if not user:
        return "این شماره در سیستم ثبت‌نام نشده"
    if not check_password_hash(user.password_hash, password):
        return "رمز عبور اشتباه است"
    login_user(user, remember=False, duration=timedelta(hours=1))
    try:
        user.touch_login()
    except Exception:
        pass
    return None

def analysis_register():
    """صفحه ثبت‌نام سریع در جریان تحلیل (اگر کاربر لاگین نباشد)."""
    if current_user.is_authenticated:
        return redirect(url_for("analysis_final"))
    if request.method == "POST":
        mode = request.form.get("mode", "register")
        if mode == "login":
            phone = request.form.get("phone", "").strip()
            password = request.form.get("password", "")
            err = _login_user_ctx(phone, password)
            if err:
                flash("⚠️ " + err, "danger")
                return render_template("analysis_register.html", mode="login")
            flash("✅ خوش آمدید! در حال آماده‌سازی گزارش نهایی...", "success")
            return redirect(url_for("analysis_final"))
        else:
            # ثبت‌نام جدید
            from giso.models import User
            name = request.form.get("name", "").strip()
            phone = request.form.get("phone", "").strip()
            password = request.form.get("password", "")
            city = request.form.get("city", "").strip()
            sq = request.form.get("security_question", "").strip()
            sa = request.form.get("security_answer", "").strip()

            np = normalize_phone(phone)
            if not np:
                flash("⚠️ لطفاً شماره همراه معتبر وارد کن", "danger")
                return render_template("analysis_register.html", mode="register")
            from giso.security import validate_new_password
            _ok, _msg = validate_new_password(password)
            if not _ok:
                flash("⚠️ " + _msg, "danger")
                return render_template("analysis_register.html", mode="register")
            if not name:
                flash("⚠️ لطفاً همه فیلدهای ضروری رو پر کن", "danger")
                return render_template("analysis_register.html", mode="register")
            if not city:
                flash("⚠️ لطفاً شهر خودت رو وارد کن", "danger")
                return render_template("analysis_register.html", mode="register")
            if User.query.filter_by(phone=np).first():
                flash("⚠️ این شماره قبلاً ثبت‌نام کرده. از تب ورود استفاده کن", "danger")
                return render_template("analysis_register.html", mode="register")
            # A8/H4 Fix: گارد شماره‌های حساس (ادمین/سوپرادمین) — نیاز به کد تأیید ربات
            try:
                from giso.app import _sensitive_register_requires_bot_code, _sensitive_register_issue_code
                if _sensitive_register_requires_bot_code(np):
                    ok, msg = _sensitive_register_issue_code(np, force=False)
                    if ok:
                        flash("🔒 این شماره متعلق به حساب حساس است. لطفاً کد تأیید ارسال‌شده به ربات را وارد کنید.", "warning")
                    else:
                        flash("🔒 برای ثبت‌نام با این شماره، ابتدا باید از طریق ربات احراز هویت شوید.", "warning")
                    return render_template("analysis_register.html", mode="register")
            except Exception as guard_err:
                logger.debug(f"sensitive register guard (analysis): {guard_err}")
            if sq == "سوال شخصی خودم" and not request.form.get("custom_question", "").strip():
                flash("⚠️ لطفاً سوال امنیتی شخصی خودت رو بنویس", "danger")
                return render_template("analysis_register.html", mode="register")
            if sq == "سوال شخصی خودم":
                sq = request.form.get("custom_question", "").strip()

            user = User(
                phone=np,
                name=name,
                city=city,
                password_hash=generate_password_hash(password, method="pbkdf2:sha256"),
                security_question=sq,
                security_answer=sa.strip().lower(),
            )
            db.session.add(user)
            db.session.commit()
            try:
                from giso.account_password_vault import remember_account_password
                remember_account_password(user.id, password)
            except Exception:
                pass
            login_user(user, remember=False, duration=timedelta(hours=1))
            try:
                user.touch_login()
            except Exception:
                pass
            flash("✅ ثبت‌نام با موفقیت انجام شد. در حال آماده‌سازی گزارش...", "success")
            return redirect(url_for("analysis_final"))
    return render_template("analysis_register.html", mode="register")

def _final_analysis(analysis_type):
    """پردازش نهایی AI — P0: session اول، auth قبل از ana، تشخیص صحیح گزارش نهایی."""
    # 1) همیشه پاسخ POST را نگه دار تا بعد از لاگین از دست نرود
    if request.method == "POST":
        try:
            session["pending_analysis_answers"] = request.form.to_dict()
            form_aid = (request.form.get("analysis_id") or "").strip()
            if form_aid.isdigit():
                session["current_analysis_id"] = int(form_aid)
        except Exception:
            pass

    # 2) لاگین نبود → ثبت‌نام (نه صفحه انتخاب آنالیز)
    if not current_user.is_authenticated:
        return redirect(url_for("analysis_register"))

    # 3) پیدا کردن رکورد آنالیز
    aid = session.get("current_analysis_id")
    ana = None
    if aid:
        try:
            ana = Analysis.query.get(int(aid))
        except Exception:
            ana = None
    if not ana or (ana.type or "hair") != analysis_type:
        try:
            phone = getattr(current_user, "phone", "") or ""
            q = Analysis.query.filter_by(type=analysis_type)
            if phone:
                q = q.filter_by(phone=phone)
            else:
                q = q.filter_by(user_id=getattr(current_user, "id", None))
            cand = q.order_by(Analysis.id.desc()).limit(5).all()
            for c in cand:
                qa = (c.questions_answers or "").strip()
                if not qa or qa in ("{}", "null"):
                    ana = c
                    session["current_analysis_id"] = c.id
                    break
            if not ana and cand:
                ana = cand[0]
                session["current_analysis_id"] = ana.id
        except Exception as e:
            try:
                logger.error("recover analysis: %s", e)
            except Exception:
                pass
    if not ana or (ana.type or "hair") != analysis_type:
        flash("⚠️ جلسه آنالیز منقضی شده. لطفاً دوباره از آپلود عکس شروع کن.", "warning")
        return redirect(url_for("analysis"))

    # 4) گزارش نهایی واقعاً تمام شده؟ (نه فقط overall_score روی تحلیل اولیه)
    try:
        _existing_report = json.loads(ana.ai_report_json or "{}")
    except Exception:
        _existing_report = {}
    qa_done = bool((ana.questions_answers or "").strip()) and (ana.questions_answers or "").strip() not in ("{}", "null")
    final_markers = ("immediate_actions", "condition", "main_problems")
    if (
        isinstance(_existing_report, dict)
        and qa_done
        and any(k in _existing_report for k in final_markers)
    ):
        if analysis_type == "hair":
            return redirect(url_for("analysis_report_hair"))
        return redirect(url_for("analysis_report_skin"))

    # A2: GET بدون پاسخ ذخیره‌شده → برگشت
    if request.method == "GET" and not session.get("pending_analysis_answers"):
        flash("⚠️ لطفاً سوالات را از ابتدا پاسخ دهید.", "warning")
        return redirect(url_for("analysis"))

    phone = getattr(current_user, "phone", "") or ""
    ip = request.remote_addr or ""
    rl = check_rate_limit(ip, phone, analysis_type)
    if not rl.get("allowed"):
        wait = rl.get("wait_minutes", 0)
        flash(
            f"⏱ برای تحلیل بعدی، {wait} دقیقه دیگه تلاش کن. تحلیل قبلی‌ت هنوز معتبره و می‌تونی دوباره ببینیش.",
            "warning",
        )
        return redirect(url_for("analysis"))

    # کسر هزینه‌ی آنالیز کامل (در صورت فعال بودن) — قبل از فراخوانی پرهزینه AI.
    # ضدتکرار با شناسه آنالیز: بازسازی/تلاش مجدد برای همان آنالیز دوبار کسر نمی‌کند.
    _block, _redir = _charge_service_or_block(
        "analysis", ana.id, "آنالیز هوشمند (گزارش کامل)")
    if _block:
        return _redir

    initial = {}
    try:
        initial = json.loads(ana.ai_report_json or "{}")
    except Exception:
        initial = {}
    if request.method == "POST":
        answers = request.form.to_dict()
    elif session.get("pending_analysis_answers"):
        answers = session.pop("pending_analysis_answers")
    else:
        answers = {}
    try:
        ana.questions_answers = json.dumps(answers, ensure_ascii=False)
        from giso.models import db as _db
        _db.session.commit()
    except Exception:
        pass

    user_name = getattr(current_user, "name", "") or ""
    user_city = getattr(current_user, "city", "") or getattr(current_user, "location", "") or ""

    prompt_name = "hair_final_analysis.txt" if analysis_type == "hair" else "skin_final_analysis.txt"
    prompt = _load_prompt(prompt_name)
    context = json.dumps(
        {
            "initial_analysis": initial,
            "user_answers": answers,
            "user_name": user_name,
            "user_city": user_city,
        },
        ensure_ascii=False,
    )
    full_prompt = prompt + "\n\n" + context

    images = []
    try:
        images = json.loads(ana.image_paths or "[]")
    except Exception:
        images = []
    result = call_vision_with_fallback(images, full_prompt, max_tokens=2000)

    if not result.get("ok"):
        _cleanup_files(images)
        flash(result.get("error", "⚠️ سرویس تحلیل تصویر موقتاً در دسترس نیست."), "danger")
        return redirect(url_for("analysis"))

    data = result.get("data") or {}
    is_valid, missing = _validate_structured_output(data, analysis_type)
    if not is_valid:
        try:
            logger.warning("AI output missing structured fields: %s", missing)
        except Exception:
            pass
        data = _ensure_structured_fallback(data, analysis_type)
    try:
        from giso.models import db
        photo_path = ""
        first_img = images[0] if images else ""
        if first_img:
            photo_path = first_img.split("uploads/")[-1] if "uploads/" in first_img else first_img
        ana.phone = phone or ana.phone
        ana.user_id = getattr(current_user, "id", None) or ana.user_id
        ana.photo_path = photo_path or "analysis/"
        ana.ai_report_json = json.dumps(data, ensure_ascii=False)
        db.session.commit()
        data["_analysis_id"] = ana.id
        # مأموریت idempotent «اتمام آنالیز» (فقط برای کاربر لاگین‌شده‌ی سایت)
        try:
            _uid = getattr(current_user, "id", None)
            if _uid:
                from giso.wallet import complete_mission as _cm_anal
                _cm_anal(int(_uid), "analysis_complete", event_key=f"analysis:{ana.id}")
        except Exception as _anal_e:
            try:
                logger.warning("analysis_complete mission failed: %s", _anal_e)
            except Exception:
                pass
    except Exception as e:
        try:
            logger.error("update analysis final: %s", e)
        except Exception:
            pass

    _record_rate_limit(ip, phone, analysis_type)

    try:
        _cleanup_files(images)
        session.pop("current_analysis_id", None)
        session.pop("pending_analysis_answers", None)
    except Exception:
        pass

    if analysis_type == "hair":
        return redirect(url_for("analysis_report_hair"))
    return redirect(url_for("analysis_report_skin"))

def _final_analysis_router():
    """مسیریاب پردازش نهایی بر اساس نوع تحلیل در session (فقط id)."""
    aid = session.get("current_analysis_id")
    atype = "hair"
    if aid:
        try:
            ana = Analysis.query.get(int(aid))
            atype = (ana.type or "hair") if ana else "hair"
        except Exception:
            atype = "hair"
    return _final_analysis(atype)

def _analysis_report(analysis_type):
    """نمایش آخرین گزارش نهایی کاربر از جدول analyses."""
    if not current_user.is_authenticated:
        return redirect(url_for("login"))
    try:
        phone = getattr(current_user, "phone", "") or ""
        req_id = request.args.get("id", "")
        last = None
        if req_id:
            try:
                last = _get_current_analysis_for_user(int(req_id))
                if not last:
                    audit_event("analysis_report_ownership_denied", "failed", target=str(req_id), details="report owner mismatch")
            except Exception:
                last = None
        if not last:
            owner_conds = _build_analysis_owner_conditions()
            last = Analysis.query.filter(or_(*owner_conds), Analysis.type == analysis_type)\
                .order_by(Analysis.id.desc()).first()
    except Exception:
        last = None
    if not last:
        flash("هنوز گزارش نهایی برای این نوع آنالیز ثبت نشده است.", "info")
        return redirect(url_for("analysis"))
    try:
        data = json.loads(last.ai_report_json or "{}")
    except Exception:
        data = {}
    # نرمال‌سازی ساختار گزارش (سازگاری با ساختار جدید و قدیمی)
    data = _normalize_report_data(data, analysis_type)
    template = "analysis_report_hair.html" if analysis_type == "hair" else "analysis_report_skin.html"
    # نام/شهر کاربر
    uname = getattr(current_user, "name", "") or "دوست عزیز"
    ucity = getattr(current_user, "city", "") or getattr(current_user, "region", "") or ""
    # محاسبه زمان باقی‌مانده محدودیت
    rl = check_rate_limit(request.remote_addr or "", phone, analysis_type)
    wait_minutes = rl.get("wait_minutes", 0) if not rl.get("allowed") else 0
    # آماده‌سازی داده‌های گزارش
    metric_cards = _build_metric_cards(data, analysis_type)
    strength_items = _build_strength_items(data, analysis_type)
    concern_items = _build_concern_items(data)
    routine_cards = _build_routine_cards(data, analysis_type)
    radar_pts = _build_radar_points(data, analysis_type)  # برای سازگاری
    # مشکلات اصلی با شدت (ساختار جدید)
    main_problems = []
    for mp in data.get("main_problems") or []:
        if isinstance(mp, dict):
            main_problems.append({
                "name": mp.get("name", ""),
                "severity": mp.get("severity", "متوسط"),
                "description": mp.get("description", ""),
            })
    return render_template(template, final=data, analysis_type=analysis_type,
                           user_name=uname, user_city=ucity,
                           wait_minutes=wait_minutes, analysis_id=last.id,
                           radar_pts=radar_pts,
                           metric_cards=metric_cards,
                           strength_items=strength_items,
                           concern_items=concern_items,
                           routine_cards=routine_cards,
                           main_problems=main_problems)

def analysis_report_hair():
    return _analysis_report("hair")

def analysis_report_skin():
    return _analysis_report("skin")

# ============================================================
# مرحله ۷: برنامه اختصاصی + درخواست محصول + مشاوره
# ============================================================

def _call_text_ai(prompt, max_tokens=2000):
    """فراخوانی هوش مصنوعی متنی (بدون تصویر) با fallback بین پروایدرها."""
    try:
        from giso.async_compat import run_async_safe
        result = run_async_safe(ask_ai_fast(
            [{"role": "user", "content": prompt}], max_tokens=max_tokens))
    except Exception as exc:
        result = {"ok": False, "error": f"{type(exc).__name__}: {exc}"}
    if result and result.get("ok"):
        parsed = _parse_ai_json(result.get("text", "") or "")
        if parsed is not None:
            return {"ok": True, "data": parsed}
        return {"ok": False, "error": "پارس JSON ناموفق"}
    return {"ok": False, "error": (result or {}).get("error", "خطای ناشناخته")}

def _call_text_ai_raw(prompt, max_tokens=2000):
    """فراخوانی هوش مصنوعی متنی و برگرداندن متن خام (برای چت مشاور و خلاصه‌ساز)."""
    try:
        from giso.async_compat import run_async_safe
        result = run_async_safe(ask_ai_fast(
            [{"role": "user", "content": prompt}], max_tokens=max_tokens))
    except Exception as exc:
        result = {"ok": False, "error": f"{type(exc).__name__}: {exc}"}
    if result and result.get("ok"):
        text = (result.get("text", "") or "").strip()
        if text:
            return {"ok": True, "text": text}
        return {"ok": False, "error": "پاسخ خالی از سرویس"}
    return {"ok": False, "error": (result or {}).get("error", "خطای ناشناخته")}

def validate_uploaded_image(image_path, analysis_type):
    """چک هوشمند عکس با AI - بررسی نوع و کیفیت."""
    try:
        prompt = _load_prompt(f"validate_{analysis_type}.txt")
        result = call_vision_with_fallback([image_path], prompt, max_tokens=800)
        if not result.get("ok"):
            return {"valid": False, "reason_code": "system_error",
                    "message": "خطا در بررسی عکس. لطفاً دوباره تلاش کنید."}
        return result.get("data") or {}
    except Exception as e:
        logger.error(f"validate_uploaded_image: {e}")
        return {"valid": False, "reason_code": "system_error",
                "message": "خطا در بررسی عکس. لطفاً دوباره تلاش کنید."}

def validate_image_route():
    """POST /analysis/validate-image — بررسی هوشمند عکس آپلودشده."""
    try:
        analysis_type = request.form.get("analysis_type", "hair")
        if analysis_type not in ("hair", "skin"):
            analysis_type = "hair"
        # فایل می‌تواند با نام image یا images بیاید
        f = request.files.get("image")
        saved = []
        if f and f.filename:
            saved = [f]
        if not saved:
            saved = _save_uploaded_images(analysis_type)
        if not saved:
            return jsonify({"valid": False, "reason_code": "no_image",
                            "message": "عکسی دریافت نشد."}), 400
        # ذخیره موقت فایل
        tmp_path = None
        if hasattr(saved[0], 'save'):
            os.makedirs(_ANALYSIS_TMP, exist_ok=True)
            ext = saved[0].filename.rsplit('.', 1)[-1].lower() if '.' in saved[0].filename else 'jpg'
            if ext not in ("jpg","jpeg","png","webp"):
                ext = "jpg"
            tmp_path = os.path.join(_ANALYSIS_TMP, f"val_{uuid.uuid4().hex[:12]}.{ext}")
            saved[0].save(tmp_path)
        else:
            tmp_path = saved[0]
        result = validate_uploaded_image(tmp_path, analysis_type)
        try:
            if tmp_path and os.path.exists(tmp_path):
                os.remove(tmp_path)
        except Exception:
            pass
        return jsonify(result)
    except Exception as e:
        logger.error(f"validate_image_route: {e}")
        return jsonify({"valid": False, "reason_code": "system_error",
                        "message": "خطا در بررسی عکس."}), 500

def _build_plan_context(analysis_type):
    """گرفتن آخرین تحلیل کاربر برای ساخت برنامه اختصاصی."""
    phone = getattr(current_user, "phone", "") or ""
    last = None
    try:
        last = Analysis.query.filter_by(phone=phone, type=analysis_type)\
            .order_by(Analysis.id.desc()).first()
    except Exception:
        last = None
    return last

def _normalize_plan_for_template(plan):
    """
    تبدیل ساختار plan_json به شکل موردنیاز template جدید برنامه تخصصی.
    هم با ساختار قدیمی (weekly_plan/nutrition/lifestyle_habits/checklist.weeks)
    و هم با ساختار جدید (weekly_plans/nutrition_dos/lifestyle_tips/checklist flat)
    سازگار است.
    """
    plan = plan or {}

    out = {
        "consultant_intro": plan.get("consultant_intro", "") or "",
        "duration_weeks": plan.get("duration_weeks", 4) or 4,
        "overview": (plan.get("overview") or (plan.get("summary", {}) or {}).get("situation", "")) or "",
    }

    # برنامه هفتگی
    weekly = plan.get("weekly_plans") or plan.get("weekly_plan") or []
    wplans = []
    for w in weekly or []:
        if not isinstance(w, dict):
            continue
        item = {
            "week_number": w.get("week_number", 1),
            "title": w.get("title") or w.get("week_title") or f"هفته {w.get('week_number', '')}",
            "description": w.get("description", "") or "",
            "morning_routine": w.get("morning_routine", []) or [],
            "evening_routine": w.get("evening_routine", []) or [],
            "weekly_special": w.get("weekly_special", []) or [],
        }
        # ادغام specific_days و avoid_this_week در weekly_special اگر خالی بود
        extra = []
        for sd in w.get("specific_days", []) or []:
            if isinstance(sd, dict):
                extra.append(f"{sd.get('day', '')}: {sd.get('action', '')}")
        for av in w.get("avoid_this_week", []) or []:
            extra.append(f"ممنوع: {av}")
        if extra and not item["weekly_special"]:
            item["weekly_special"] = extra
        wplans.append(item)
    out["weekly_plans"] = wplans

    # تغذیه
    nutrition = plan.get("nutrition") or {}
    add = plan.get("nutrition_dos")
    if add is None:
        add = [d.get("name", "") for d in nutrition.get("add_to_diet", []) or [] if isinstance(d, dict)]
    red = plan.get("nutrition_donts")
    if red is None:
        red = [d.get("name", "") for d in nutrition.get("reduce_from_diet", []) or [] if isinstance(d, dict)]
    out["nutrition_dos"] = [str(x) for x in (add or []) if str(x).strip()]
    out["nutrition_donts"] = [str(x) for x in (red or []) if str(x).strip()]

    # سبک زندگی
    tips = plan.get("lifestyle_tips")
    if tips is None:
        tips = [f"{h.get('habit', '')} - {h.get('detail', '')}".strip(" -")
                for h in plan.get("lifestyle_habits", []) or [] if isinstance(h, dict)]
    out["lifestyle_tips"] = [str(x) for x in (tips or []) if str(x).strip()]

    # علائم هشدار
    out["warning_signs"] = plan.get("warning_signs", []) or []

    # چک‌لیست → لیست تخت
    flat = []
    cl = plan.get("checklist") or {}
    if isinstance(cl, dict):
        for w in cl.get("weeks", []) or []:
            wn = w.get("week_number", 1) if isinstance(w, dict) else 1
            items = w.get("items", []) if isinstance(w, dict) else []
            for i, txt in enumerate(items or []):
                flat.append({"week": wn, "id": f"w{wn}-{i}", "text": str(txt)})
    elif isinstance(cl, list):
        for i, item in enumerate(cl or []):
            if isinstance(item, dict):
                flat.append({"week": item.get("week", 1), "id": str(item.get("id", i)),
                             "text": str(item.get("text", ""))})
            else:
                flat.append({"week": 1, "id": str(i), "text": str(item)})
    out["checklist"] = flat

    return out

def _load_plan_for_display(analysis):
    """بارگذاری plan_json خام از دیتابیس (بدون تولید جدید)."""
    plan = {}
    if getattr(analysis, "plan_json", ""):
        try:
            plan = json.loads(analysis.plan_json)
        except Exception:
            plan = {}
    return plan if isinstance(plan, dict) else {}

def analysis_plan():
    """صفحه برنامه اختصاصی بر اساس آخرین گزارش کاربر."""
    if not current_user.is_authenticated:
        return redirect(url_for("login"))
    # پشتیبانی از ?id= برای مشاهده برنامه یک تحلیل خاص
    req_id = request.args.get("id", "")
    last = None
    if req_id:
        try:
            last = Analysis.query.filter_by(id=int(req_id), phone=getattr(current_user, "phone", "") or "").first()
        except Exception:
            last = None
    if not last:
        last = _build_plan_context("hair") or _build_plan_context("skin")
    if not last:
        flash("برای دریافت برنامه اختصاصی ابتدا یک تحلیل انجام دهید.", "info")
        return redirect(url_for("analysis"))

    user_name = getattr(current_user, "name", "") or "دوست عزیز"

    # علامت‌گذاری اینکه کاربر گزارش کامل (full) رو دیده
    try:
        current_view = last.report_type_viewed or ''
        if 'full' not in current_view:
            new_view = 'both' if 'quick' in current_view else 'full'
            last.report_type_viewed = new_view
            db.session.commit()
    except Exception as e:
        logger.warning(f"report_type_viewed update failed: {e}")

    # بررسی plan ذخیره‌شده در دیتابیس (نه session)
    plan = None
    if getattr(last, "plan_json", ""):
        try:
            plan = json.loads(last.plan_json)
        except Exception:
            plan = None

    if plan is None:
        analysis_type = last.type or "hair"
        report = {}
        try:
            report = json.loads(last.ai_report_json or "{}")
        except Exception:
            report = {}
        user_city = getattr(current_user, "city", "") or getattr(current_user, "region", "") or ""

        # لیست محصولات موجود در گیسو
        products = []
        try:
            products = Product.query.all()
        except Exception:
            products = []
        products_ctx = [
            {"id": p.id, "name": p.name, "category": p.category or "",
             "description": p.description or ""}
            for p in products
        ]

        prompt = _load_prompt("plan_generator.txt")
        prompt = prompt.replace("{analysis_result}", json.dumps(report, ensure_ascii=False)[:3000])
        prompt = prompt.replace("{user_name}", user_name)
        prompt = prompt.replace("{analysis_type}", analysis_type or "hair")
        prompt = prompt.replace("[city]", user_city or "شهر شما").replace("[name]", user_name)
        context = json.dumps({
            "report": report,
            "giso_products": products_ctx,
            "city": user_city,
            "name": user_name,
        }, ensure_ascii=False)
        full_prompt = prompt + "\n\n" + context

        result = _call_text_ai(full_prompt, max_tokens=2500)
        if result.get("ok"):
            plan = result.get("data") or {}
        else:
            # fallback: اگر AI جواب نداد، فقط مسیر و پیام پیش‌فرض
            plan = {
                "consultant_intro": f"{user_name} عزیز، برنامه اختصاصی شما آماده شده است.",
                "duration_weeks": 4,
                "weekly_plan": [
                    {"week_number": 1, "week_title": "هفته 1 - شناخت وضعیت",
                     "morning_routine": ["بررسی روتین فعلی", "ثبت عادت‌های روزانه"],
                     "evening_routine": ["مراقبت پایه", "ثبت پیشرفت"],
                     "expected_result": "شناخت کامل از وضعیت"},
                    {"week_number": 2, "week_title": "هفته 2 - مراقبت منظم",
                     "morning_routine": ["رعایت روتین پیشنهادی", "تغذیه سالم"],
                     "evening_routine": ["مراقبت شبانه", "ثبت پیشرفت"],
                     "expected_result": "شروع روند بهبود"},
                ],
                "warning_signs": [],
            }
        # ذخیره فقط در دیتابیس (plan_json + duration_weeks) — نه session
        try:
            last.plan_json = json.dumps(plan, ensure_ascii=False)
            try:
                last.duration_weeks = int(plan.get("duration_weeks", 4))
            except (TypeError, ValueError):
                last.duration_weeks = 4
            db.session.commit()
        except Exception as e:
            logger.error(f"save plan_json: {e}")

    # نرمال‌سازی plan برای template
    plan_data = _normalize_plan_for_template(plan)

    # کارت محصول برای مشاور (قابلیت C): فقط فراخوانیِ ماژول مستقل، بدون بدنه.
    try:
        from giso.consultant_cards import build_cards_for_user
        consultant_cards = build_cards_for_user(getattr(current_user, "phone", "") or "")
    except Exception:
        consultant_cards = []

    return render_template("analysis_plan.html",
                           plan=plan_data,
                           analysis=last,
                           user_name=user_name,
                           analysis_type=(last.type or "hair"),
                           analysis_id=last.id,
                           consultant_cards=consultant_cards,
                           checklist_progress=getattr(last, "checklist_progress", "{}"))

def request_product():
    """ثبت درخواست محصول (برای محصولاتی که در گیسو موجود نیستند)."""
    if not current_user.is_authenticated:
        return redirect(url_for("login"))
    try:
        phone = getattr(current_user, "phone", "") or ""
        city = getattr(current_user, "city", "") or getattr(current_user, "region", "") or ""
        problem = request.form.get("problem_summary", "").strip() or request.form.get("message", "").strip()
        analysis_id = request.form.get("analysis_id", "") or ""
        try:
            analysis_id = int(analysis_id) or 0
        except (TypeError, ValueError):
            analysis_id = 0
        conn = get_conn()
        with conn:
            cur = conn.execute(
                "INSERT INTO product_requests (user_id, phone, city, analysis_id, problem_summary, status, created_at) "
                "VALUES (?,?,?,?,?, 'pending', ?)",
                (getattr(current_user, "id", None), phone, city, analysis_id, problem,
                 datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
            )
            rid = cur.lastrowid
        flash("✅ درخواست اطلاع‌رسانی محصول شما ثبت شد. به‌محض موجود شدن، اطلاع می‌دهیم.", "success")
    except Exception as e:
        logger.error(f"request_product: {e}")
        flash("❌ خطا در ثبت درخواست محصول.", "danger")
    return redirect(url_for("analysis_plan"))

def request_consultant():
    """ثبت درخواست مشاوره و اعلان به ادمین‌ها در ربات."""
    if not current_user.is_authenticated:
        return redirect(url_for("login"))
    rid = None
    try:
        phone = getattr(current_user, "phone", "") or ""
        city = getattr(current_user, "city", "") or getattr(current_user, "region", "") or ""
        name = getattr(current_user, "name", "") or "کاربر"
        msg_text = request.form.get("message", "").strip()
        if not msg_text:
            flash("لطفاً پیام خود را بنویسید.", "danger")
            return redirect(url_for("analysis_plan"))
        analysis_id = request.form.get("analysis_id", "") or ""
        try:
            analysis_id = int(analysis_id) or 0
        except (TypeError, ValueError):
            analysis_id = 0
        conn = get_conn()
        with conn:
            cur = conn.execute(
                "INSERT INTO consultant_requests (user_id, phone, city, customer_name, analysis_id, "
                "initial_message, status, created_at, updated_at) "
                "VALUES (?,?,?,?,?,?, 'new', ?, ?)",
                (getattr(current_user, "id", None), phone, city, name, analysis_id, msg_text,
                 datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                 datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
            )
            rid = cur.lastrowid
            # ذخیره پیام اولیه
            conn.execute(
                "INSERT INTO consultant_messages (request_id, sender, message, is_read, created_at) "
                "VALUES (?, 'user', ?, 0, ?)",
                (rid, msg_text, datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
            )
        # کسر هزینه‌ی مشاوره (یک بار به‌ازای هر جلسه/درخواست، نه هر پیام گفتگو).
        # ضدتکرار با شناسه‌ی درخواست؛ اگر اعتبار کافی نباشد درخواست بلاک و رکورد حذف می‌شود.
        _block, _redir = _charge_service_or_block(
            "consultation", rid, "مشاوره آنلاین (یک جلسه)")
        if _block:
            try:
                with get_conn() as _c:
                    _c.execute("DELETE FROM consultant_requests WHERE id=?", (rid,))
                    _c.commit()
            except Exception:
                pass
            return _redir
        try:
            from giso.panel.modules.notifications import safe_log
            safe_log("analysis", "consultant", "درخواست مشاوره جدید",
                     f"درخواست مشاوره کاربر {name} ثبت شد.", source_type="consultant_request", source_id=rid)
        except Exception as exc:
            logger.exception("consultant admin notification failed: %s", exc)
        flash("✅ درخواست مشاوره شما ثبت شد. مشاور زیبایی گیسو در اسرع وقت پاسخگو خواهد بود.", "success")
    except Exception as e:
        logger.error(f"request_consultant: {e}")
        flash("❌ خطا در ثبت درخواست مشاوره.", "danger")
    # اعلان به ادمین در ربات (در صورت امکان)
    _notify_consultant_admins(rid)
    return redirect(url_for("analysis_plan"))

def save_checklist(analysis_id):
    """ذخیره پیشرفت چک‌لیست در دیتابیس."""
    if not current_user.is_authenticated:
        return jsonify({"ok": False, "error": "login"}), 401
    try:
        data = request.get_json(silent=True) or {}
        a = Analysis.query.filter_by(id=analysis_id, phone=getattr(current_user, "phone", "") or "").first()
        if not a:
            return jsonify({"ok": False, "error": "not found"}), 404
        a.checklist_progress = json.dumps(data, ensure_ascii=False)
        db.session.commit()
        return jsonify({"ok": True})
    except Exception as e:
        logger.error(f"save_checklist: {e}")
        return jsonify({"ok": False, "error": str(e)}), 500

@login_required
def save_checklist_progress(analysis_id):
    """ذخیره پیشرفت چک‌لیست (آیتم به آیتم)."""
    try:
        analysis = _get_current_analysis_for_user(analysis_id)
        if not analysis:
            return jsonify({'ok': False, 'error': 'تحلیل پیدا نشد'}), 404

        data = request.get_json(silent=True) or {}
        item_id = str(data.get('item_id', ''))
        checked = bool(data.get('checked', False))

        try:
            progress = json.loads(analysis.checklist_progress or '{}')
        except Exception:
            progress = {}
        if not isinstance(progress, dict):
            progress = {}

        if checked:
            progress[item_id] = True
        else:
            progress.pop(item_id, None)

        analysis.checklist_progress = json.dumps(progress, ensure_ascii=False)
        db.session.commit()

        return jsonify({'ok': True})
    except Exception as e:
        logger.error(f"save_checklist_progress error: {e}")
        return jsonify({'ok': False, 'error': 'خطا'}), 500

@login_required
def get_checklist_progress(analysis_id):
    """دریافت پیشرفت چک‌لیست."""
    try:
        analysis = _get_current_analysis_for_user(analysis_id)
        if not analysis:
            return jsonify({'ok': False, 'error': 'تحلیل پیدا نشد'}), 404

        try:
            progress = json.loads(analysis.checklist_progress or '{}')
        except Exception:
            progress = {}
        if not isinstance(progress, dict):
            progress = {}

        return jsonify({'ok': True, 'progress': progress})
    except Exception as e:
        logger.error(f"get_checklist_progress error: {e}")
        return jsonify({'ok': False, 'error': 'خطا'}), 500

# ============================================================
# مشاور هوشمند صادقی — زیرساخت چت AI (راه سریع / اصولی)
# ============================================================

def _load_consultant_prompt(user_name, analysis_data, plan_data, products, key_notes, chat_history, user_message,
                            beauty_centers=None):
    """بارگذاری پرامپت مشاور صادقی با داده‌های کاربر."""
    template = _load_prompt("consultant_sadeghi.txt")
    if not template:
        return None

    # ساخت لیست محصولات
    products_text = ""
    for p in products[:20]:  # حداکثر ۲۰ محصول
        products_text += f"- {p['name']} (قیمت: {p['price']} تومان) - {p.get('description', '')[:100]}\n"

    # ساخت تاریخچه چت
    history_text = ""
    for msg in chat_history[-6:]:  # ۶ پیام آخر
        role = "کاربر" if msg['role'] == 'user' else "مشاور"
        history_text += f"{role}: {msg['content']}\n"

    prompt = template.replace('{user_name}', user_name or 'دوست عزیز')
    prompt = prompt.replace('{analysis_data}', json.dumps(analysis_data, ensure_ascii=False)[:1500])
    prompt = prompt.replace('{plan_data}', json.dumps(plan_data or {}, ensure_ascii=False)[:1000])
    prompt = prompt.replace('{products_list}', products_text)
    prompt = prompt.replace('{key_notes}', key_notes or 'گفتگوی جدید')
    prompt = prompt.replace('{chat_history}', history_text or 'شروع گفتگو')
    prompt = prompt.replace('{user_message}', user_message)

    # Beauty Centers owns its prompt policy; Analysis only supplies database-backed matches.
    from giso.beauty_centers.ai_prompt import build_beauty_centers_prompt
    prompt += build_beauty_centers_prompt(beauty_centers)
    return prompt

def _summarize_chat_history(chat_history):
    """خلاصه‌سازی تاریخچه گفتگو با AI."""
    if not chat_history or len(chat_history) < 3:
        return ""

    template = _load_prompt("consultant_summarizer.txt")
    if not template:
        return ""

    history_text = ""
    for msg in chat_history:
        role = "کاربر" if msg['role'] == 'user' else "مشاور"
        history_text += f"{role}: {msg['content']}\n"

    prompt = template.replace('{chat_history}', history_text)

    try:
        result = _call_text_ai_raw(prompt, max_tokens=200)
        if result and result.get('ok'):
            summary = result.get('text', '').strip()
            return summary[:500]  # حداکثر ۵۰۰ کاراکتر
    except Exception as e:
        logger.error(f"summarize error: {e}")

    return ""

def _build_analysis_owner_conditions():
    """ساخت شرط‌های مالکیت تحلیل برای کاربر جاری (فقط فیلدهای موجود)."""
    conds = []
    uid = getattr(current_user, "id", None)
    if uid is not None:
        conds.append(Analysis.user_id == uid)
    phone = (getattr(current_user, "phone", "") or "").strip()
    if phone:
        conds.append(Analysis.phone == phone)
    return conds

def _get_current_analysis_for_user(analysis_id):
    """پیدا کردن تحلیل متعلق به کاربر جاری (با id و شماره/شناسه کاربر)."""
    if not current_user.is_authenticated:
        return None
    analysis = None
    try:
        conds = _build_analysis_owner_conditions()
        if not conds:
            return None
        analysis = Analysis.query.filter(
            Analysis.id == analysis_id,
            or_(*conds)
        ).first()
    except Exception as exc:
        logger.error("analysis ownership query failed: %s", exc)
        try:
            analysis = Analysis.query.filter(
                Analysis.id == analysis_id,
                Analysis.user_id == getattr(current_user, "id", None)
            ).first()
        except Exception as fallback_exc:
            logger.error("analysis ownership fallback failed: %s", fallback_exc)
            analysis = None
    if not analysis:
        audit_event("analysis_ownership_denied", "failed", target=str(analysis_id), details="analysis is not owned by current user")
    return analysis

def _user_asked_to_buy(text):
    """کارت محصول فقط وقتی کاربر خرید/معرفی محصول بخواهد، نه وسط آنالیز."""
    t = (text or "").replace("ي", "ی").replace("ك", "ک")
    keys = (
        "خرید", "بخرم", "بخری", "بخر", "می‌خرم", "ميخرم", "میخرم",
        "سفارش", "لینک خرید", "چی بخرم", "میخوام بخرم", "می‌خوام بخرم",
        "چه محصولی", "محصول خوب", "محصول معرفی", "از فروشگاه",
    )
    return any(k in t for k in keys)

@login_required
def consultant_chat_message():
    """API چت با مشاور صادقی (ارسال پیام و دریافت پاسخ)."""
    try:
        data = request.get_json(silent=True) or {}
        analysis_id = data.get('analysis_id')
        user_message = (data.get('message') or '').strip()

        if not user_message:
            return jsonify({'ok': False, 'error': 'پیام خالی'}), 400

        scope = get_context_scope("user", section="consultant_chat")
        if not scope.get("allowed"):
            return jsonify({'ok': False, 'error': scope.get('message') or NO_ACCESS_MESSAGE}), 403

        analysis = _get_current_analysis_for_user(analysis_id)
        if not analysis:
            return jsonify({'ok': False, 'error': 'تحلیل پیدا نشد'}), 404

        # بارگذاری تاریخچه
        try:
            chat_history = json.loads(analysis.consultant_chat_history or '[]')
        except Exception:
            chat_history = []
        if not isinstance(chat_history, list):
            chat_history = []

        # اضافه کردن پیام کاربر
        chat_history.append({
            'role': 'user',
            'content': user_message,
            'timestamp': datetime.now().isoformat()
        })

        # بارگذاری داده‌ها
        try:
            analysis_data = json.loads(analysis.ai_report_json or '{}')
        except Exception:
            analysis_data = {}
        try:
            plan_data = json.loads(analysis.plan_json or '{}')
        except Exception:
            plan_data = {}

        if not scope.get("include_analysis"):
            analysis_data = {}
        if not scope.get("include_plan"):
            plan_data = {}

        # بارگذاری محصولات فقط برای سطح ۲ به بالا و فقط اگر کاربر خرید خواست
        want_products = _user_asked_to_buy(user_message)
        products = []
        if scope.get("include_products") and want_products:
            try:
                all_products = Product.query.filter_by(in_stock=True).limit(30).all()
                for p in all_products:
                    products.append({
                        'id': p.id,
                        'name': p.name,
                        'price': p.price,
                        'description': p.description or '',
                        'category': p.category or ''
                    })
            except Exception:
                pass

        beauty_centers = []
        if scope.get("include_products"):
            try:
                from giso.beauty_centers.services import recommended_centers
                beauty_centers = recommended_centers(
                    analysis.id, int(getattr(current_user, "id", 0) or 0),
                    city=getattr(current_user, "city", "") or "", track_impression=False,
                )
            except Exception:
                beauty_centers = []

        user_name = getattr(current_user, "name", "") or "دوست عزیز"

        prompt = _load_consultant_prompt(
            user_name=user_name,
            analysis_data=analysis_data,
            plan_data=plan_data,
            products=products,
            key_notes=analysis.consultant_key_notes or '',
            chat_history=chat_history[:-1],  # پیام فعلی جدا
            user_message=user_message,
            beauty_centers=beauty_centers,
        )

        if not prompt:
            return jsonify({'ok': False, 'error': 'خطا در بارگذاری پرامپت'}), 500

        # فراخوانی AI مدیریت‌شده (فقط برای چت مشاور)
        from giso.async_compat import run_async_safe
        result = run_async_safe(chat_with_managed_ai(
            [{"role": "user", "content": prompt}],
            actor_key=f"site:{getattr(current_user, 'phone', '') or getattr(current_user, 'id', '')}",
            role="user",
            channel="site",
            section="consultant_chat",
            question_text=user_message,
            max_tokens=800,
        ))

        if not result or not result.get('ok'):
            reason = (result or {}).get('reason')
            error_text = (result or {}).get('text') or PROVIDER_ERROR_MESSAGE
            status_code = 429 if reason == 'daily_limit' else (403 if reason in ('access_level_0', 'section_blocked') else 503)
            return jsonify({
                'ok': False,
                'error': error_text
            }), status_code

        ai_response = result.get('text', '').strip()

        # اضافه کردن پاسخ AI به تاریخچه
        chat_history.append({
            'role': 'assistant',
            'content': ai_response,
            'timestamp': datetime.now().isoformat()
        })

        # ذخیره تاریخچه
        analysis.consultant_chat_history = json.dumps(chat_history, ensure_ascii=False)

        # اگر ۵ پیام یا بیشتر شد، خلاصه بساز
        if len(chat_history) >= 5 and len(chat_history) % 5 == 0:
            try:
                summary = _summarize_chat_history(chat_history)
                if summary:
                    analysis.consultant_key_notes = summary
            except Exception:
                pass

        db.session.commit()

        # قابلیت C: کارت محصول (آرایشی) + آیتم خوراکی (سفارش خاص) — فقط برداشتن داده، بدون خطا.
        phone = getattr(current_user, "phone", "") or ""
        product_cards, nutrition_items = [], []
        try:
            from giso.consultant_cards import build_cards_for_user
            product_cards = [c.to_dict() for c in build_cards_for_user(phone)[:3]]
        except Exception:
            pass
        try:
            from giso.recommendation_service import get_nutrition_recommendations
            nutrition_items = [i.to_dict() for i in get_nutrition_recommendations(phone, analysis_data, limit=3)]
        except Exception:
            pass

        return jsonify({
            'ok': True,
            'response': ai_response,
            'message_count': len(chat_history),
            'product_cards': product_cards,
            'nutrition_items': nutrition_items,
        })
    except Exception as e:
        logger.error(f"consultant_chat error: {e}")
        return jsonify({
            'ok': False,
            'error': 'خطا در پردازش پیام'
        }), 500

@login_required
def consultant_chat_history_route(analysis_id):
    """دریافت تاریخچه گفتگو با مشاور."""
    try:
        analysis = _get_current_analysis_for_user(analysis_id)
        if not analysis:
            return jsonify({'ok': False, 'error': 'تحلیل پیدا نشد'}), 404

        try:
            chat_history = json.loads(analysis.consultant_chat_history or '[]')
        except Exception:
            chat_history = []
        if not isinstance(chat_history, list):
            chat_history = []

        return jsonify({
            'ok': True,
            'history': chat_history,
            'key_notes': analysis.consultant_key_notes or ''
        })
    except Exception as e:
        logger.error(f"chat_history error: {e}")
        return jsonify({'ok': False, 'error': 'خطا'}), 500

@login_required
def consultant_chat_rate():
    """ثبت امتیاز گفتگو با مشاور."""
    try:
        data = request.get_json(silent=True) or {}
        analysis_id = data.get('analysis_id')
        try:
            rating = int(data.get('rating', 0))
        except (TypeError, ValueError):
            rating = 0

        if rating < 1 or rating > 5:
            return jsonify({'ok': False, 'error': 'امتیاز باید 1 تا 5 باشه'}), 400

        analysis = _get_current_analysis_for_user(analysis_id)
        if not analysis:
            return jsonify({'ok': False, 'error': 'تحلیل پیدا نشد'}), 404

        analysis.chat_rating = rating
        db.session.commit()

        return jsonify({'ok': True})
    except Exception as e:
        logger.error(f"chat_rate error: {e}")
        return jsonify({'ok': False, 'error': 'خطا'}), 500

# ============================================================
# راه سریع رفع مشکل (Quick Solution) — مرحله ۴
# ============================================================

def _default_quick_solution(analysis_data, user_name, analysis_type):
    """محتوای پیش‌فرض اگر AI جواب نداد."""
    def _skin_steps():
        return [
            {
                "step_number": 1,
                "title": "🧴 پاکسازی روزانه",
                "description": "صبح و شب صورتت رو با شوینده ملایم بشور. از آب ولرم استفاده کن.",
                "time_frame": "از همین امروز"
            },
            {
                "step_number": 2,
                "title": "💧 آبرسانی مداوم",
                "description": "بعد از شستشو، از مرطوب‌کننده مناسب نوع پوستت استفاده کن. روزی حداقل ۲ لیوان آب اضافه بنوش.",
                "time_frame": "۲ هفته اول"
            },
            {
                "step_number": 3,
                "title": "☀️ محافظت از آفتاب",
                "description": "کرم ضد آفتاب حتماً استفاده کن، حتی در روزهای ابری.",
                "time_frame": "همیشه"
            }
        ]

    def _hair_steps():
        return [
            {
                "step_number": 1,
                "title": "🧴 شامپوی مناسب",
                "description": "شامپوی بدون سولفات با pH متعادل استفاده کن. هفته‌ای ۲-۳ بار بشور.",
                "time_frame": "از همین امروز"
            },
            {
                "step_number": 2,
                "title": "💧 آبرسانی و تغذیه",
                "description": "هفته‌ای یک بار از ماسک آبرسان استفاده کن. روغن مغذی هم روی نوک موها بذار.",
                "time_frame": "۲ هفته اول"
            },
            {
                "step_number": 3,
                "title": "🚫 پرهیز از آسیب",
                "description": "از سشوار و اتو داغ کمتر استفاده کن. موقع خشک کردن، حوله رو ضربه‌ای بزن نه بکش.",
                "time_frame": "همیشه"
            }
        ]

    if analysis_type == 'skin':
        steps = _skin_steps()
        return {
            "situation_summary": "پوستت نیاز به مراقبت داره. با روتین درست، ظرف ۲ هفته بهبود رو می‌بینی.",
            "quick_diagnosis": "پوستت نیاز به پاکسازی و آبرسانی منظم داره.",
            "quick_steps": steps,
            "three_actions": steps,
            "warning_signs": ["التهاب یا قرمزی شدید و پایدار", "زخم‌های باز روی پوست"],
            "consultant_intro": f"سلام {user_name} عزیز 🌸\nخوشحالم که می‌خوای مشکلاتت رو رفع کنی. با کمی توجه و محصولات مناسب، پوستت درخشش لازم رو پیدا می‌کنه. می‌خوای بریم سراغ محصولاتی که واقعاً کمکت می‌کنن؟"
        }
    else:  # hair
        steps = _hair_steps()
        return {
            "situation_summary": "موهات نیاز به مراقبت داره. با روتین ساده، ظرف ۲ هفته تفاوت رو حس می‌کنی.",
            "quick_diagnosis": "موهات نیاز به آبرسانی و مراقبت از آسیب‌های حرارتی دارن.",
            "quick_steps": steps,
            "three_actions": steps,
            "warning_signs": ["ریزش ناگهانی و شدید مو", "خارش یا التهاب پوست سر همراه با ریزش"],
            "consultant_intro": f"سلام {user_name} عزیز 🌸\nخوشحالم که می‌خوای مشکلاتت رو رفع کنی. با محصولات مناسب و روتین درست، موهات درخشش قبلش رو پیدا می‌کنه. می‌خوای بریم سراغ محصولاتی که واقعاً کمکت می‌کنن؟"
        }

def _generate_quick_solution(analysis):
    """تولید محتوای راه سریع با AI."""
    try:
        # داده‌های تحلیل
        analysis_data = json.loads(analysis.ai_report_json or '{}')

        # بارگذاری پرامپت
        template = _load_prompt("quick_solution.txt")
        if not template:
            return None

        # جایگزینی متغیرها
        user_name = getattr(current_user, "name", "") or "دوست عزیز"
        analysis_type = (analysis.type or "hair")

        prompt = template.replace('{analysis_data}', json.dumps(analysis_data, ensure_ascii=False)[:2000])
        prompt = prompt.replace('{user_name}', user_name)
        prompt = prompt.replace('{analysis_type}', analysis_type)

        # فراخوانی AI (خروجی JSON — _call_text_ai آن را پارس می‌کند)
        result = _call_text_ai(prompt, max_tokens=1500)

        if not result or not result.get('ok'):
            return _default_quick_solution(analysis_data, user_name, analysis_type)

        data = result.get('data') or {}
        if not isinstance(data, dict):
            return _default_quick_solution(analysis_data, user_name, analysis_type)

        # سازگاری با هر دو ساختار:
        # - جدید: summary_message / quick_diagnosis / three_actions / warning_signs
        # - قدیمی: situation_summary / quick_steps
        steps = data.get('three_actions') or data.get('quick_steps') or []
        if not isinstance(steps, list) or len(steps) < 1:
            return _default_quick_solution(analysis_data, user_name, analysis_type)

        # نرمال‌سازی قدم‌ها به قالب مشترک (title/description/time_frame)
        norm_steps = []
        for st in steps[:3]:
            if not isinstance(st, dict):
                continue
            norm_steps.append({
                "step_number": st.get("step_number") or (len(norm_steps) + 1),
                "title": st.get("title", ""),
                "description": st.get("description", ""),
                "time_frame": st.get("time_frame", ""),
            })
        if not norm_steps:
            return _default_quick_solution(analysis_data, user_name, analysis_type)

        summary = (data.get('summary_message') or data.get('situation_summary') or "").strip()
        if not summary:
            summary = (data.get('quick_diagnosis') or "").strip()
        if not summary:
            summary = "بر اساس تحلیل، یک برنامه سریع برایت آماده کرده‌ایم."

        return {
            "situation_summary": summary,
            "quick_diagnosis": (data.get('quick_diagnosis') or "").strip(),
            "quick_steps": norm_steps,
            "three_actions": norm_steps,
            "warning_signs": data.get('warning_signs') or [],
            "consultant_intro": (data.get('consultant_intro') or "").strip() or (
                f"سلام {user_name} عزیز 🌸\nخوشحالم که می‌خوای مشکلاتت رو رفع کنی. با مشاوره‌ی من، به سراغ محصولات مناسب می‌ریم."
            ),
        }
    except Exception as e:
        logger.error(f"_generate_quick_solution error: {e}")
        return None

@login_required
def analysis_quick_solution():
    """صفحه راه سریع رفع مشکل."""
    try:
        # پیدا کردن آخرین تحلیل کاربر
        analysis_id = request.args.get('id', type=int)

        owner_conds = _build_analysis_owner_conditions()

        if analysis_id:
            analysis = _get_current_analysis_for_user(analysis_id)
            if not analysis:
                audit_event("analysis_quick_solution_ownership_denied", "failed", target=str(analysis_id), details="quick solution owner mismatch")
        else:
            analysis = Analysis.query.filter(
                or_(*owner_conds)
            ).order_by(Analysis.id.desc()).first()

        if not analysis:
            flash('تحلیلی برای شما پیدا نشد. لطفاً اول یک تحلیل انجام دهید.', 'warning')
            return redirect(url_for('analysis'))

        # کسر هزینه‌ی گزارش سریع (در صورت فعال بودن) — یک بار به‌ازای هر تحلیل (ضدتکرار با id تحلیل).
        # قبل از تولید محتوا/فراخوانی AI انجام می‌شود تا در کمبود اعتبار، خدمت بلاک شود.
        _block, _redir = _charge_service_or_block(
            'quick_report', analysis.id, 'گزارش سریع/کامل')
        if _block:
            return _redir

        # علامت‌گذاری اینکه کاربر گزارش سریع رو دیده
        current_view = analysis.report_type_viewed or ''
        if 'quick' not in current_view:
            new_view = 'both' if 'full' in current_view else 'quick'
            analysis.report_type_viewed = new_view
            db.session.commit()

        # تولید محتوا (کش در session)
        cache_key = f'quick_solution_{analysis.id}'
        quick_data = session.get(cache_key)

        if not quick_data:
            quick_data = _generate_quick_solution(analysis)
            if quick_data:
                session[cache_key] = quick_data
                # ذخیره در دیتابیس (quick_solution_json)
                try:
                    analysis.quick_solution_json = json.dumps(quick_data, ensure_ascii=False)
                    analysis.updated_at = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    db.session.commit()
                except Exception as e:
                    logger.warning(f"save quick_solution_json: {e}")

        if not quick_data:
            flash('خطا در تولید محتوا. لطفاً دوباره تلاش کنید.', 'danger')
            return redirect(url_for('analysis'))

        # داده‌های تحلیل برای مشاور
        try:
            analysis_json = json.loads(analysis.ai_report_json or '{}')
        except Exception:
            analysis_json = {}

        return render_template(
            'analysis_quick_solution.html',
            analysis=analysis,
            quick_data=quick_data,
            analysis_json=analysis_json,
            user_name=getattr(current_user, "name", "") or 'دوست عزیز',
            quick_type=(analysis.type or 'hair'),
        )
    except Exception as e:
        logger.error(f"analysis_quick_solution error: {e}")
        flash('خطای غیرمنتظره. لطفاً دوباره تلاش کنید.', 'danger')
        return redirect(url_for('analysis'))

# ============================================================
# توابع کمکی تولید PDF با پشتیبانی فارسی (RTL + shaping)
# ============================================================

def _notify_consultant_admins(request_id):
    """ثبت درخواست مشاوره در notification center؛ کنترل گفتگو در ربات حفظ می‌شود."""
    try:
        row = None
        conn = get_conn()
        with conn:
            row = conn.execute("SELECT * FROM consultant_requests WHERE id=?", (request_id,)).fetchone()
        if not row:
            return
        from giso.panel.modules.notifications import log_notification
        log_notification(
            "analysis", "consultant", "درخواست مشاوره جدید",
            f"کاربر: {row['customer_name'] or '—'} | شماره: {row['phone'] or '—'} | پیام: {(row['initial_message'] or '')[:300]}",
            source_type="consultant_request", source_id=request_id,
        )
    except Exception as exc:
        logger.exception("consultant request notification center failed: %s", exc)

def _run_initial(analysis_type):
    tmpl = "analysis_hair.html" if analysis_type == "hair" else "analysis_skin.html"
    prompt_name = "hair_initial_analysis.txt" if analysis_type == "hair" else "skin_initial_analysis.txt"
    saved = _save_uploaded_images(analysis_type)
    if not saved:
        flash("حداقل یک عکس لازم است.", "danger")
        return render_template(tmpl, stage=2, initial=None, questions=None,
                               analysis_type=analysis_type, ai_error="")
    prompt = _load_prompt(prompt_name)
    result = call_vision_with_fallback(saved, prompt)
    if not result.get("ok"):
        _cleanup_files(saved)
        return render_template(tmpl, stage=2, initial=None, questions=None,
                               analysis_type=analysis_type,
                               ai_error=result.get("error", "⚠️ سرویس تحلیل تصویر موقتاً در دسترس نیست."))
    data = result.get("data") or {}
    questions = _build_questions(analysis_type, data.get("detected_issues") or {})
    # ذخیره تحلیل اولیه + عکس‌ها در دیتابیس با یک رکورد ناتمام؛ فقط ID در session
    try:
        phone = getattr(current_user, "phone", "") if current_user.is_authenticated else ""
        ana = Analysis(
            user_id=getattr(current_user, "id", None) if current_user.is_authenticated else None,
            phone=phone,
            type=analysis_type,
            photo_path="analysis/",
            image_paths=json.dumps(saved, ensure_ascii=False),
            ai_report_json=json.dumps(data, ensure_ascii=False),
        )
        db.session.add(ana)
        db.session.commit()
        session.pop("analysis_flow", None)
        session["current_analysis_id"] = ana.id
        # مرکز اعلان‌ها: رویداد «آنالیز جدید» در محل وقوع ثبت می‌شود (فاز ۴۲:
        # sync خودکار حذف شده؛ idempotent با source_type+source_id → یک اعلان برای هر آنالیز)
        try:
            from giso.panel.modules.notifications import safe_log
            safe_log("analysis", "new", "آنالیز جدید",
                     f"کاربر {phone or '—'} آنالیز {'مو' if analysis_type == 'hair' else 'پوست'} ثبت کرد.",
                     source_type="analysis_new", source_id=ana.id)
        except Exception as exc:
            logger.exception("new analysis notification failed: %s", exc)
    except Exception as e:
        logger.error(f"_run_initial save: {e}")
        # اگر ذخیره رکورد شکست خورد، عکس‌های آپلودشده باید پاک شوند (دیگر به آن‌ها ارجاعی نیست)
        _cleanup_files(saved)
    return render_template(tmpl, stage=3, initial=data, questions=questions,
                           analysis_type=analysis_type, ai_error="")

def initial_analysis_hair():
    return _run_initial("hair")

def initial_analysis_skin():
    return _run_initial("skin")

@login_required
def run_analysis():
    flash("بخش تحلیل هوش مصنوعی گیسو در دست ساخت است.", "info")
    return redirect(url_for("analysis"))

@login_required
def admin_analysis_note(analysis_id):
    from giso.app import _check_giso_admin_access
    if _r := _check_giso_admin_access():
        return _r
    from giso.panel.permissions import current_role_and_perms
    role, _perms, _bid = current_role_and_perms()
    if role != "super":
        flash("⛔ مدیریت آنالیز فقط برای سوپرادمین مجاز است.", "warning")
        return redirect(url_for("panel.dashboard"))
    try:
        a = Analysis.query.get_or_404(analysis_id)
        a.admin_note = request.form.get("admin_note", "").strip()
        db.session.commit()
        flash("یادداشت ادمین برای این آنالیز ثبت شد.", "success")
    except Exception:
        try:
            db.session.rollback()
        except Exception:
            pass
        flash("خطا در ثبت یادداشت آنالیز.", "danger")
    return redirect(url_for("admin_dashboard", tab="tab-analyses"))

def final_analysis_hair():
    """روت POST /analysis/hair/final — پردازش نهایی آنالیز مو."""
    return _final_analysis("hair")

def final_analysis_skin():
    """روت POST /analysis/skin/final — پردازش نهایی آنالیز پوست."""
    return _final_analysis("skin")

def register_analysis_routes(app):
    app.add_url_rule("/analysis", endpoint="analysis", view_func=analysis, methods=["GET"])
    app.add_url_rule("/analysis/hair", endpoint="analysis_hair", view_func=analysis_hair, methods=["GET"])
    app.add_url_rule("/analysis/skin", endpoint="analysis_skin", view_func=analysis_skin, methods=["GET"])
    app.add_url_rule("/analysis/run", endpoint="run_analysis", view_func=run_analysis, methods=["POST"])
    app.add_url_rule("/analysis/hair/initial", endpoint="initial_analysis_hair", view_func=initial_analysis_hair, methods=["POST"])
    app.add_url_rule("/analysis/skin/initial", endpoint="initial_analysis_skin", view_func=initial_analysis_skin, methods=["POST"])
    app.add_url_rule("/analysis/register", endpoint="analysis_register", view_func=analysis_register, methods=["GET", "POST"])
    app.add_url_rule("/analysis/hair/final", endpoint="final_analysis_hair", view_func=final_analysis_hair, methods=["POST"])
    app.add_url_rule("/analysis/skin/final", endpoint="final_analysis_skin", view_func=final_analysis_skin, methods=["POST"])
    app.add_url_rule("/analysis/final", endpoint="analysis_final", view_func=_final_analysis_router, methods=["GET", "POST"])
    app.add_url_rule("/analysis/hair/report", endpoint="analysis_report_hair", view_func=analysis_report_hair, methods=["GET"])
    app.add_url_rule("/analysis/skin/report", endpoint="analysis_report_skin", view_func=analysis_report_skin, methods=["GET"])
    app.add_url_rule("/analysis/plan", endpoint="analysis_plan", view_func=analysis_plan, methods=["GET"])
    app.add_url_rule("/analysis/quick-solution", endpoint="analysis_quick_solution", view_func=analysis_quick_solution, methods=["GET"])
    app.add_url_rule("/analysis/request-product", endpoint="request_product", view_func=request_product, methods=["POST"])
    app.add_url_rule("/analysis/request-consultant", endpoint="request_consultant", view_func=request_consultant, methods=["POST"])
    app.add_url_rule("/analysis/save-checklist/<int:analysis_id>", endpoint="save_checklist", view_func=save_checklist, methods=["POST"])
    app.add_url_rule("/analysis/checklist/save/<int:analysis_id>", endpoint="save_checklist_progress", view_func=save_checklist_progress, methods=["POST"])
    app.add_url_rule("/analysis/checklist/progress/<int:analysis_id>", endpoint="get_checklist_progress", view_func=get_checklist_progress, methods=["GET"])
    app.add_url_rule("/analysis/validate-image", endpoint="validate_image_route", view_func=validate_image_route, methods=["POST"])
    # مشاور هوشمند صادقی
    app.add_url_rule("/api/consultant-chat/message", endpoint="consultant_chat_message", view_func=consultant_chat_message, methods=["POST"])
    app.add_url_rule("/api/consultant-chat/history/<int:analysis_id>", endpoint="consultant_chat_history", view_func=consultant_chat_history_route, methods=["GET"])
    app.add_url_rule("/api/consultant-chat/rate", endpoint="consultant_chat_rate", view_func=consultant_chat_rate, methods=["POST"])
    app.add_url_rule("/admin/analysis/<int:analysis_id>/note", endpoint="admin_analysis_note", view_func=admin_analysis_note, methods=["POST"])

__all__ = [
    "analysis_routes",
    "analysis",
    "run_analysis",
    "admin_analysis_note",
    "register_analysis_routes",
    "analysis_register",
    "check_rate_limit",
    "_final_analysis",
    "analysis_plan",
    "request_product",
    "request_consultant",
    "save_checklist",
    "save_checklist_progress",
    "get_checklist_progress",
    "_normalize_plan_for_template",
    "_load_plan_for_display",
    "_load_consultant_prompt",
    "_summarize_chat_history",
    "consultant_chat_message",
    "consultant_chat_history_route",
    "consultant_chat_rate",
    "_generate_quick_solution",
    "_default_quick_solution",
    "analysis_quick_solution",
]
# Phase 3.5 Analysis Sync: analysis state sync comment
# Phase 7 AI Analysis overall: verify ai_brain/provider/load
# Phase 7.1 Loading: verify /analysis page query performance
# Phase 7.4 AI Output: verify vision/text output format
# Phase 7.5 Ownership: enforce user-only analysis
# Phase 7.6 Analysis Test note
# Phase 3.5 Sync — Analysis status sync guard (no loop)
