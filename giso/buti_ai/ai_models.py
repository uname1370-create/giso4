# -*- coding: utf-8 -*-
"""تنظیمات مدل‌های اختصاصی آینه زیبایی گیسو.

این ماژول عمداً داخل `giso/buti_ai/` است تا سناریوی آینه زیبایی/ابرو
مالک تنظیمات خودش باشد، اما پنل مرکزی «مدیریت هوش مصنوعی» بتواند همان
تنظیمات را نمایش و ذخیره کند.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Any, Dict, Iterable, List, Optional

from giso.base import get_giso_db_conn

logger = logging.getLogger("giso_buti_ai_models")

TASK_EYEBROW_ANALYSIS = "eyebrow_analysis"
TASK_EYEBROW_IMAGE_DESIGN = "eyebrow_image_design"

TASK_DEFS: Dict[str, Dict[str, Any]] = {
    TASK_EYEBROW_ANALYSIS: {
        "label": "آینه ابرو — تحلیل عکس",
        "short_label": "تحلیل عکس",
        "kind": "vision",
        "slots": 1,
        "help": "مدل بینایی که عکس کاربر را تحلیل می‌کند.",
    },
    TASK_EYEBROW_IMAGE_DESIGN: {
        "label": "آینه ابرو — طراحی نهایی تصویر",
        "short_label": "طراحی تصویر",
        "kind": "image",
        "slots": 3,
        "help": "مدل‌های تصویرسازی به‌ترتیب اولویت؛ اگر مدل اول جواب نداد، بعدی امتحان می‌شود.",
    },
}

AI_MODEL_ASSIGNMENTS_SQL = """
CREATE TABLE IF NOT EXISTS buti_ai_model_assignments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_key TEXT NOT NULL,
    priority INTEGER NOT NULL DEFAULT 1,
    provider_name TEXT NOT NULL DEFAULT '',
    model_name TEXT NOT NULL DEFAULT '',
    enabled INTEGER NOT NULL DEFAULT 1,
    image_kind TEXT NOT NULL DEFAULT '',
    endpoint_override TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(task_key, priority)
);
CREATE INDEX IF NOT EXISTS idx_buti_ai_model_assignments_task
ON buti_ai_model_assignments(task_key, enabled, priority);
"""


def _now() -> str:
    return datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")


def _row_get(row: Any, key: str, default: Any = "") -> Any:
    if row is None:
        return default
    try:
        value = row[key]
        return default if value is None else value
    except Exception:
        pass
    try:
        if hasattr(row, "get"):
            value = row.get(key, default)
            return default if value is None else value
    except Exception:
        pass
    return default


def init_buti_ai_model_assignments(conn=None) -> None:
    """ایجاد جدول تنظیم مدل‌های آینه زیبایی، افزودنی و امن."""
    own_conn = conn is None
    c = conn or get_giso_db_conn()
    try:
        c.executescript(AI_MODEL_ASSIGNMENTS_SQL)
        # مهاجرت افزودنی برای دیتابیس‌های قدیمی‌تر.
        columns = {row[1] for row in c.execute("PRAGMA table_info(buti_ai_model_assignments)").fetchall()}
        for column, ddl in (
            ("image_kind", "image_kind TEXT NOT NULL DEFAULT ''"),
            ("endpoint_override", "endpoint_override TEXT NOT NULL DEFAULT ''"),
            ("updated_at", "updated_at TEXT NOT NULL DEFAULT ''"),
        ):
            if column not in columns:
                c.execute(f"ALTER TABLE buti_ai_model_assignments ADD COLUMN {ddl}")
        c.commit()
    except Exception as exc:
        logger.error("init_buti_ai_model_assignments failed: %s", exc)
    finally:
        if own_conn:
            try:
                c.close()
            except Exception:
                pass


def normalize_task_key(task_key: str) -> str:
    key = str(task_key or "").strip().lower()
    return key if key in TASK_DEFS else ""


def _normal_priority(priority: Any, task_key: str) -> int:
    try:
        value = int(priority or 1)
    except (TypeError, ValueError):
        value = 1
    slots = int(TASK_DEFS.get(task_key, {}).get("slots") or 1)
    return max(1, min(max(1, slots), value))


def save_model_assignment(task_key: str, priority: Any, provider_name: str, model_name: str,
                          enabled: bool = True, image_kind: str = "",
                          endpoint_override: str = "") -> tuple[bool, str]:
    """ذخیره یک اسلات مدل برای آینه زیبایی.

    ذخیره بر اساس `(task_key, priority)` است؛ یعنی اسلات ۱ مدل اصلی و
    اسلات‌های بعدی fallback هستند.
    """
    task_key = normalize_task_key(task_key)
    if not task_key:
        return False, "نوع کاربرد مدل نامعتبر است."
    priority = _normal_priority(priority, task_key)
    provider_name = str(provider_name or "").strip().lower()
    model_name = str(model_name or "").strip()
    image_kind = str(image_kind or "").strip().lower()
    endpoint_override = str(endpoint_override or "").strip()

    if not provider_name or not model_name:
        return False, "نام پروایدر و نام مدل الزامی است."

    now = _now()
    init_buti_ai_model_assignments()
    try:
        with get_giso_db_conn() as conn:
            conn.execute(
                """
                INSERT INTO buti_ai_model_assignments (
                    task_key, priority, provider_name, model_name, enabled,
                    image_kind, endpoint_override, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(task_key, priority) DO UPDATE SET
                    provider_name=excluded.provider_name,
                    model_name=excluded.model_name,
                    enabled=excluded.enabled,
                    image_kind=excluded.image_kind,
                    endpoint_override=excluded.endpoint_override,
                    updated_at=excluded.updated_at
                """,
                (
                    task_key, priority, provider_name, model_name, int(bool(enabled)),
                    image_kind, endpoint_override, now, now,
                ),
            )
            conn.commit()
        return True, "تنظیم مدل آینه زیبایی ذخیره شد."
    except Exception as exc:
        logger.error("save_model_assignment failed: %s", exc)
        return False, "ذخیره تنظیم مدل انجام نشد."


def list_model_assignments(task_key: str = "", only_enabled: bool = False) -> List[Dict[str, Any]]:
    init_buti_ai_model_assignments()
    task_key = normalize_task_key(task_key) if task_key else ""
    where: List[str] = []
    params: List[Any] = []
    if task_key:
        where.append("task_key=?")
        params.append(task_key)
    if only_enabled:
        where.append("enabled=1")
    sql = "SELECT * FROM buti_ai_model_assignments"
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY task_key, priority, id"
    try:
        with get_giso_db_conn() as conn:
            rows = conn.execute(sql, params).fetchall()
        return [dict(row) for row in rows]
    except Exception as exc:
        logger.error("list_model_assignments failed: %s", exc)
        return []


def assignment_map() -> Dict[str, Dict[int, Dict[str, Any]]]:
    result: Dict[str, Dict[int, Dict[str, Any]]] = {key: {} for key in TASK_DEFS}
    for row in list_model_assignments():
        key = normalize_task_key(row.get("task_key"))
        if key:
            result.setdefault(key, {})[int(row.get("priority") or 1)] = row
    return result


def _json_list(value: Any) -> List[Any]:
    try:
        data = json.loads(str(value or "[]"))
        return data if isinstance(data, list) else []
    except Exception:
        return []


def _add_unique(target: List[str], item: Any) -> None:
    mid = item.get("id") if isinstance(item, dict) else item
    mid = str(mid or "").strip()
    if mid and mid not in target:
        target.append(mid)


def _models_for_provider_row(row: Any) -> List[str]:
    models: List[str] = []
    _add_unique(models, _row_get(row, "selected_model", ""))
    for column in ("vision_models_json", "text_models_json", "fallback_json", "models_json"):
        for item in _json_list(_row_get(row, column, "[]")):
            if isinstance(item, dict) and item.get("disabled"):
                continue
            _add_unique(models, item)
    try:
        from giso.ai_models_registry import get_image_models, get_text_models, get_vision_models

        name = _row_get(row, "name", "")
        for group in (get_image_models(name), get_vision_models(name), get_text_models(name)):
            for item in group:
                _add_unique(models, item)
    except Exception:
        pass
    return models


def provider_model_options() -> Dict[str, Any]:
    """گزینه‌های قابل نمایش در پنل مدیریت برای انتخاب مدل آینه زیبایی."""
    try:
        from giso.ai_brain import _col, _effective_base_url, get_ai_provider, list_ai_providers
        from giso.ai_brain import cloudflare_account_id_from_url
    except Exception:
        _col = None
        _effective_base_url = None
        get_ai_provider = None
        list_ai_providers = None
        cloudflare_account_id_from_url = None

    providers: List[Dict[str, Any]] = []
    all_models: List[str] = []
    if list_ai_providers is None:
        return {"providers": providers, "models": all_models}

    try:
        rows = list_ai_providers() or []
    except Exception:
        rows = []

    for row in rows:
        name = str(_row_get(row, "name", "") or "").strip()
        if not name:
            continue
        models = _models_for_provider_row(row)
        for model in models:
            if model not in all_models:
                all_models.append(model)
        base_url = str(_row_get(row, "api_root", "") or _row_get(row, "base_url", "") or "")
        providers.append({
            "name": name,
            "enabled": bool(_row_get(row, "enabled", 0)),
            "kind": str(_row_get(row, "kind", "") or ""),
            "has_api_key": bool(str(_row_get(row, "api_key", "") or "").strip()),
            "selected_model": str(_row_get(row, "selected_model", "") or ""),
            "models": models,
            "cloudflare_account_id": cloudflare_account_id_from_url(base_url) if cloudflare_account_id_from_url else "",
        })
    return {"providers": providers, "models": all_models}


def panel_slots_context() -> Dict[str, Any]:
    """ساخت داده ساده برای تب «مدل‌های آینه زیبایی» در پنل."""
    assignments = assignment_map()
    options = provider_model_options()
    slots: List[Dict[str, Any]] = []
    for task_key, meta in TASK_DEFS.items():
        for priority in range(1, int(meta.get("slots") or 1) + 1):
            current = assignments.get(task_key, {}).get(priority, {})
            slots.append({
                "task_key": task_key,
                "task_label": meta["label"],
                "task_kind": meta["kind"],
                "task_help": meta["help"],
                "priority": priority,
                "slot_label": "مدل اصلی" if priority == 1 else f"Fallback {priority}",
                "provider_name": current.get("provider_name", ""),
                "model_name": current.get("model_name", ""),
                "enabled": bool(current.get("enabled", 1)) if current else True,
                "image_kind": current.get("image_kind", ""),
                "endpoint_override": current.get("endpoint_override", ""),
                "has_value": bool(current),
            })
    return {
        "tasks": TASK_DEFS,
        "slots": slots,
        "providers": options.get("providers", []),
        "model_options": options.get("models", []),
    }


def configured_vision_chain() -> List[Dict[str, str]]:
    """زنجیره اختصاصی تحلیل عکس ابرو از مدیریت AI."""
    chain: List[Dict[str, str]] = []
    try:
        from giso.ai_brain import get_ai_provider
    except Exception:
        return chain
    for row in list_model_assignments(TASK_EYEBROW_ANALYSIS, only_enabled=True):
        provider_name = str(row.get("provider_name") or "").strip().lower()
        model_name = str(row.get("model_name") or "").strip()
        if not provider_name or not model_name:
            continue
        provider = get_ai_provider(provider_name)
        if not provider or not _row_get(provider, "enabled", 0):
            continue
        chain.append({"provider_name": provider_name, "model_name": model_name})
    return chain


def _cloudflare_run_root(row: Any) -> str:
    try:
        from giso.ai_brain import normalize_cloudflare_api_root
    except Exception:
        normalize_cloudflare_api_root = None
    raw = str(_row_get(row, "api_root", "") or _row_get(row, "base_url", "") or "").strip()
    if normalize_cloudflare_api_root:
        try:
            raw = normalize_cloudflare_api_root(raw, "", require_account=False)
        except Exception:
            pass
    root = raw.rstrip("/")
    if "{account_id}" in root:
        return ""
    return root


def _openai_image_endpoint(row: Any, override: str = "") -> str:
    override = str(override or "").strip()
    if override:
        return override
    base = str(_row_get(row, "api_root", "") or _row_get(row, "base_url", "") or "").strip().rstrip("/")
    if not base:
        return ""
    if base.endswith("/images/edits") or base.endswith("/images/generations"):
        return base
    return base + "/images/edits"


def configured_image_provider_dicts(limit: int = 3) -> List[Dict[str, Any]]:
    """providerهای تصویرسازی آینه ابرو از مدیریت AI، بدون لاگ‌کردن کلیدها."""
    try:
        from giso.ai_brain import get_ai_provider
    except Exception:
        return []

    providers: List[Dict[str, Any]] = []
    for row in list_model_assignments(TASK_EYEBROW_IMAGE_DESIGN, only_enabled=True):
        if len(providers) >= max(1, int(limit or 3)):
            break
        provider_name = str(row.get("provider_name") or "").strip().lower()
        model_name = str(row.get("model_name") or "").strip()
        if not provider_name or not model_name:
            continue
        provider = get_ai_provider(provider_name)
        if not provider or not _row_get(provider, "enabled", 0):
            continue
        api_key = str(_row_get(provider, "api_key", "") or "").strip()
        if not api_key:
            continue
        provider_kind = str(_row_get(provider, "kind", "") or "").strip().lower()
        image_kind = str(row.get("image_kind") or "").strip().lower()
        endpoint = ""
        if provider_kind == "cloudflare" or provider_name == "cloudflare":
            root = _cloudflare_run_root(provider)
            if not root:
                continue
            endpoint = root.rstrip("/") + "/" + model_name
            image_kind = "cloudflare"
        else:
            endpoint = _openai_image_endpoint(provider, row.get("endpoint_override", ""))
            image_kind = image_kind or "openai_image_edit"
        if not endpoint:
            continue
        priority = int(row.get("priority") or 1)
        providers.append({
            "id": f"ai_mirror_{provider_name}_{priority}",
            "label": f"مدیریت AI: {provider_name} #{priority}",
            "kind": image_kind,
            "endpoint": endpoint,
            "model": model_name,
            "api_key": api_key,
            "headers": {},
            "extra": {"priority": priority, "source": "ai_management"},
        })
    return providers


__all__ = [
    "TASK_EYEBROW_ANALYSIS",
    "TASK_EYEBROW_IMAGE_DESIGN",
    "TASK_DEFS",
    "init_buti_ai_model_assignments",
    "save_model_assignment",
    "list_model_assignments",
    "panel_slots_context",
    "configured_vision_chain",
    "configured_image_provider_dicts",
]
