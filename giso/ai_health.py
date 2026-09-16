# -*- coding: utf-8 -*-
"""
مدیریت سلامت مشترک پروایدرها (فاز ۳ بازنویسی سیستم AI)
هر ۳ موتور (Vision, Chat, Fast) از این ماژول استفاده می‌کنند.

جدول `giso_ai_health` در init_ai_tables ساخته می‌شود:
    (provider, model) یکتا — خطاها، شمارش شکست و پایان کولداؤن را نگه می‌دارد.
"""
import logging
from datetime import datetime, timedelta, timezone

from giso.ai_config import HEALTH_COOLDOWN_MINUTES

logger = logging.getLogger(__name__)

# نوع خطاها برای ثبت در ستون last_result
ERROR_TYPES = ("timeout", "429", "auth", "refused", "http_error", "network", "unknown", "json")


def _conn():
    from giso.base import get_giso_db_conn
    return get_giso_db_conn()


def _now():
    return datetime.now(timezone.utc)


def _iso(dt):
    return dt.strftime("%Y-%m-%d %H:%M:%S")


def _parse_iso(text):
    try:
        return datetime.strptime(str(text or "")[:19], "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
    except Exception:
        return None


def _row(provider, model=None):
    m = model or ""
    try:
        with _conn() as conn:
            return conn.execute(
                "SELECT * FROM giso_ai_health WHERE provider=? AND model=?",
                (str(provider or "").lower(), m),
            ).fetchone()
    except Exception:
        return None


def mark_success(provider: str, model: str = None):
    """موفقیت را ثبت کن و کولداؤن را پاک کن."""
    try:
        with _conn() as conn:
            conn.execute(
                """INSERT INTO giso_ai_health (provider, model, last_result, last_error,
                                               fail_count, cooldown_until, updated_at)
                   VALUES (?,?,?,?,0,'',?)
                   ON CONFLICT(provider, model) DO UPDATE SET
                       last_result='success', last_error='', fail_count=0,
                       cooldown_until='', updated_at=excluded.updated_at""",
                (str(provider or "").lower(), model or "", "success", "", _iso(_now())),
            )
    except Exception as e:
        logger.warning(f"ai_health.mark_success: {e}")


def mark_failure(provider: str, model: str, error_type: str, error_msg: str = "",
                 cooldown_minutes: int = None):
    """
    خطا را ثبت کن و کولداؤن بگذار.
    error_type: 'timeout', '429', 'auth', 'refused', 'http_error', 'network', 'json', 'unknown'
    """
    if error_type not in ERROR_TYPES:
        error_type = "unknown"
    minutes = HEALTH_COOLDOWN_MINUTES if cooldown_minutes is None else max(0, int(cooldown_minutes))
    cooldown_until = _iso(_now() + timedelta(minutes=minutes)) if minutes > 0 else ""
    try:
        with _conn() as conn:
            conn.execute(
                """INSERT INTO giso_ai_health (provider, model, last_result, last_error,
                                               fail_count, cooldown_until, updated_at)
                   VALUES (?,?,?,?,1,?,?)
                   ON CONFLICT(provider, model) DO UPDATE SET
                       last_result=excluded.last_result,
                       last_error=excluded.last_error,
                       fail_count=giso_ai_health.fail_count + 1,
                       cooldown_until=excluded.cooldown_until,
                       updated_at=excluded.updated_at""",
                (str(provider or "").lower(), model or "", error_type,
                 str(error_msg or "")[:200], cooldown_until, _iso(_now())),
            )
    except Exception as e:
        logger.warning(f"ai_health.mark_failure: {e}")


def is_in_cooldown(provider: str, model: str = None) -> bool:
    """آیا این پروایدر/مدل الان در کولداون است؟"""
    return get_cooldown_remaining_seconds(provider, model) > 0


def get_cooldown_remaining_seconds(provider: str, model: str = None) -> int:
    """چند ثانیه دیگر کولداون تمام می‌شود؟

    کولداون سطح پروایدر (سطر با مدل خالی) روی همهٔ مدل‌های آن پروایدر هم اثر می‌گذارد.
    """
    pname = str(provider or "").lower()
    best = 0
    rows = []
    if model:
        # بررسی سطر مدل مشخص + سطر سطح پروایدر
        for m in (model, ""):
            r = _row(pname, m)
            if r is not None:
                rows.append(r)
    else:
        # بدون مدل: هر کولداونی روی این پروایدر (سطح پروایدر یا هر مدل) مؤثر است
        try:
            with _conn() as conn:
                rows = conn.execute(
                    "SELECT * FROM giso_ai_health WHERE provider=?", (pname,)
                ).fetchall()
        except Exception:
            rows = []
    for row in rows:
        until = _parse_iso(row["cooldown_until"])
        if until is None:
            continue
        remaining = (until - _now()).total_seconds()
        if remaining > best:
            best = remaining
    return max(0, int(best))


def filter_available(chain: list) -> list:
    """از یک زنجیره [(provider, model), ...] فقط آنهایی که کولداون ندارند را برگرداند."""
    out = []
    for item in chain or []:
        try:
            p, m = item
        except Exception:
            continue
        if not is_in_cooldown(p, m):
            out.append(item)
    return out


def get_provider_is_free(provider_name: str) -> bool:
    """آیا پروایدر رایگان است؟ (برای تصمیم بک‌آف 429)"""
    try:
        from giso.ai_models_registry import get_provider
        reg = get_provider(provider_name)
        if not reg:
            return True  # ناشناخته را رایگان فرض کن
        # اگر ایرانی است، معمولاً پولی است
        return not reg.get("is_iranian", False)
    except Exception:
        return True


def get_fail_count(provider: str, model: str = None) -> int:
    row = _row(provider, model)
    return int(row["fail_count"] or 0) if row else 0


def classify_error_text(error_text: str) -> str:
    """طبقه‌بندی متن خطا به یکی از انواع استاندارد (مشترک هر سه موتور)."""
    s = str(error_text or "").lower()
    if not s:
        return "unknown"
    if "429" in s or "rate limit" in s or "too many" in s or "quota" in s:
        return "429"
    if "401" in s or "403" in s or "unauthorized" in s or "forbidden" in s \
            or "api key" in s or "authentication" in s or "کلید" in s \
            or "username or password" in s or "invalid username" in s \
            or "proxy auth" in s or "authentication failed" in s:
        # پیام «Invalid username or password» مربوط به هندشیک احراز هویت
        # پروکسی‌های رایگان است و باید به‌عنوان خطای دسترسی طبقه‌بندی شود.
        return "auth"
    if "timeout" in s or "timed out" in s or "read timed" in s:
        return "timeout"
    if any(k in s for k in ("connect", "httpx", "network", "ssl", "dns", "unreachable")):
        return "network"
    if "http 4" in s or "http 5" in s or "http 3" in s:
        return "http_error"
    return "unknown"


__all__ = [
    "ERROR_TYPES", "mark_success", "mark_failure", "is_in_cooldown",
    "get_cooldown_remaining_seconds", "filter_available", "get_provider_is_free",
    "get_fail_count", "classify_error_text",
]
