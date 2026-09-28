# -*- coding: utf-8 -*-
"""تنظیمات مدل‌های اختصاصی آینه زیبایی گیسو.

این ماژول عمداً داخل `giso/buti_ai/` است تا سناریوی آینه زیبایی/ابرو
مالک تنظیمات خودش باشد، اما پنل مرکزی «مدیریت هوش مصنوعی» بتواند همان
تنظیمات را نمایش و ذخیره کند.
"""
from __future__ import annotations

import json
import logging
import re
from datetime import datetime
from typing import Any, Dict, Iterable, List, Optional

from giso.base import get_giso_db_conn

logger = logging.getLogger("giso_buti_ai_models")

TASK_EYEBROW_ANALYSIS = "eyebrow_analysis"
TASK_EYEBROW_IMAGE_DESIGN = "eyebrow_image_design"
DEFAULT_CLOUDFLARE_FINAL_IMAGE_MODEL = "@cf/black-forest-labs/flux-2-klein-4b"
CLOUDFLARE_INPAINTING_MODEL = "@cf/runwayml/stable-diffusion-v1-5-inpainting"
CLOUDFLARE_INPAINTING_KINDS = {"cloudflare_inpainting", "cloudflare_inpaint", "inpainting", "mask_inpainting"}
LEGACY_UNSUPPORTED_CLOUDFLARE_FINAL_MODELS = {
    "@cf/black-forest-labs/flux-1-schnell",
    "@cf/stabilityai/stable-diffusion-xl-base-1.0",
}

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


def _is_cloudflare_provider_name(provider_name: str) -> bool:
    name = str(provider_name or "").strip().lower()
    return name == "cloudflare" or re.fullmatch(r"cf[1-3]", name) is not None


def _cloudflare_slot_priority(provider_name: str) -> int:
    match = re.fullmatch(r"cf([0-9]+)", str(provider_name or "").strip().lower())
    if not match:
        return 0
    try:
        return max(1, min(int(TASK_DEFS[TASK_EYEBROW_IMAGE_DESIGN]["slots"]), int(match.group(1))))
    except Exception:
        return 0


def _registry_family_for_provider(provider_name: str) -> str:
    return "cloudflare" if _is_cloudflare_provider_name(provider_name) else str(provider_name or "").strip().lower()


def _cloudflare_image_kind_for_model(model_name: str, image_kind: str = "") -> str:
    """Preserve explicit AI Management capability; infer only documented inpainting model."""
    kind = str(image_kind or "").strip().lower()
    if kind:
        return "cloudflare_inpainting" if kind in CLOUDFLARE_INPAINTING_KINDS else kind
    if str(model_name or "").strip() == CLOUDFLARE_INPAINTING_MODEL:
        return "cloudflare_inpainting"
    return "cloudflare"


def _is_supported_cloudflare_final_model(model_name: str, image_kind: str = "") -> bool:
    """Only documented/safe Cloudflare models enter final eyebrow generation."""
    model = str(model_name or "").strip()
    kind = _cloudflare_image_kind_for_model(model, image_kind)
    if kind in CLOUDFLARE_INPAINTING_KINDS:
        return model == CLOUDFLARE_INPAINTING_MODEL
    return model == DEFAULT_CLOUDFLARE_FINAL_IMAGE_MODEL


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

        name = _registry_family_for_provider(_row_get(row, "name", ""))
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
    try:
        repair_legacy_cloudflare_eyebrow_image_slots()
    except Exception as exc:
        logger.debug("legacy Cloudflare eyebrow slot repair for panel skipped: %s", exc)
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
        "readiness": readiness_status(),
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


def repair_legacy_cloudflare_eyebrow_image_slots() -> Dict[str, Any]:
    """Fix old auto-slots that used Cloudflare text-to-image JSON models for photo editing.

    Older configs could leave slot 2/3 as flux-1-schnell or SDXL. Those endpoints
    expect JSON and fail for the current photo-edit flow. If cf2/cf3 providers
    exist, map each slot to that account with the safe FLUX 2 model; otherwise
    disable the unsupported extra slot so the user does not see repeated JSON
    errors in final design.
    """
    try:
        from giso.ai_brain import get_ai_provider
    except Exception as exc:
        return {"ok": False, "changed": 0, "error": str(exc)[:120]}

    changed: List[Dict[str, Any]] = []
    for row in list_model_assignments(TASK_EYEBROW_IMAGE_DESIGN):
        try:
            priority = int(row.get("priority") or 1)
        except Exception:
            priority = 1
        provider_name = str(row.get("provider_name") or "").strip().lower()
        model_name = str(row.get("model_name") or "").strip()
        image_kind = str(row.get("image_kind") or "").strip().lower()
        provider = get_ai_provider(provider_name)
        provider_kind = str(_row_get(provider, "kind", "") or "").strip().lower()
        is_cf = provider_kind == "cloudflare" or _is_cloudflare_provider_name(provider_name)
        if not is_cf:
            continue
        effective_kind = _cloudflare_image_kind_for_model(model_name, image_kind)
        if effective_kind in CLOUDFLARE_INPAINTING_KINDS:
            continue
        if _is_supported_cloudflare_final_model(model_name, image_kind):
            continue
        if model_name not in LEGACY_UNSUPPORTED_CLOUDFLARE_FINAL_MODELS and not model_name.startswith("@cf/"):
            continue

        slot_provider_name = f"cf{priority}" if 1 <= priority <= int(TASK_DEFS[TASK_EYEBROW_IMAGE_DESIGN]["slots"]) else ""
        slot_provider = get_ai_provider(slot_provider_name) if slot_provider_name else None
        target_provider = provider_name
        enabled = False
        if slot_provider and str(_row_get(slot_provider, "kind", "") or "").strip().lower() == "cloudflare" and str(_row_get(slot_provider, "api_key", "") or "").strip():
            target_provider = slot_provider_name
            enabled = True
        elif priority == 1 and provider and str(_row_get(provider, "api_key", "") or "").strip():
            enabled = True
        ok, _message = save_model_assignment(
            TASK_EYEBROW_IMAGE_DESIGN,
            priority,
            target_provider,
            DEFAULT_CLOUDFLARE_FINAL_IMAGE_MODEL,
            enabled=enabled,
            image_kind="cloudflare",
        )
        if ok:
            changed.append({
                "priority": priority,
                "from_provider": provider_name,
                "to_provider": target_provider,
                "from_model": model_name,
                "to_model": DEFAULT_CLOUDFLARE_FINAL_IMAGE_MODEL,
                "enabled": enabled,
            })
    return {"ok": True, "changed": len(changed), "items": changed}


def configured_image_provider_dicts(limit: int = 3) -> List[Dict[str, Any]]:
    """providerهای تصویرسازی آینه ابرو از مدیریت AI، بدون لاگ‌کردن کلیدها."""
    try:
        from giso.ai_brain import get_ai_provider
    except Exception:
        return []

    try:
        repair_legacy_cloudflare_eyebrow_image_slots()
    except Exception as exc:
        logger.debug("legacy Cloudflare eyebrow slot repair skipped: %s", exc)

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
        if provider_kind == "cloudflare" or _is_cloudflare_provider_name(provider_name):
            root = _cloudflare_run_root(provider)
            if not root:
                continue
            image_kind = _cloudflare_image_kind_for_model(model_name, image_kind)
            if not _is_supported_cloudflare_final_model(model_name, image_kind):
                continue
            endpoint = root.rstrip("/") + "/" + model_name
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
            "extra": {"priority": priority, "source": "ai_management", "image_kind": image_kind},
        })
    return providers


def readiness_status() -> Dict[str, Any]:
    """وضعیت آماده‌بودن آینه زیبایی برای استفاده واقعی از AI.

    این تابع کلیدها را نمایش نمی‌دهد؛ فقط می‌گوید تنظیمات لازم برای تحلیل عکس
    و طراحی تصویر موجود است یا نه.
    """
    try:
        from giso.ai_brain import get_ai_provider
    except Exception:
        return {
            "ready": False,
            "analysis_ready": False,
            "image_ready": False,
            "image_ready_count": 0,
            "image_providers": [],
            "issues": ["دسترسی به مدیریت AI ممکن نیست؛ تنظیمات پروایدرها را بررسی کن."],
            "warnings": [],
        }

    try:
        repair_legacy_cloudflare_eyebrow_image_slots()
    except Exception as exc:
        logger.debug("legacy Cloudflare eyebrow slot repair for readiness skipped: %s", exc)

    issues: List[str] = []
    warnings: List[str] = []

    def _enabled(value: Any) -> bool:
        return str(value if value is not None else "0").strip().lower() not in {"", "0", "false", "off", "no"}

    def provider_problem(provider_name: str, model_name: str, image_task: bool = False, endpoint_override: str = "") -> str:
        if not provider_name or not model_name:
            return "پروایدر یا مدل انتخاب نشده است."
        try:
            provider = get_ai_provider(provider_name)
        except Exception:
            return f"وضعیت پروایدر «{provider_name}» قابل خواندن نیست."
        if not provider:
            return f"پروایدر «{provider_name}» در مدیریت AI پیدا نشد."
        if not _enabled(_row_get(provider, "enabled", 0)):
            return f"پروایدر «{provider_name}» غیرفعال است."
        if not str(_row_get(provider, "api_key", "") or "").strip():
            return f"پروایدر «{provider_name}» API Key/Token ندارد."
        if image_task:
            kind = str(_row_get(provider, "kind", "") or "").strip().lower()
            if kind == "cloudflare" or _is_cloudflare_provider_name(provider_name):
                safe_kind = _cloudflare_image_kind_for_model(model_name, "")
                if not _is_supported_cloudflare_final_model(model_name, safe_kind):
                    return "این مدل Cloudflare برای طراحی عکس نهایی ابرو پشتیبانی نمی‌شود؛ از flux-2-klein-4b یا مدل inpainting واقعی استفاده کن."
                if not _cloudflare_run_root(provider):
                    return "Cloudflare Account ID یا API Root درست تنظیم نشده است."
            elif not _openai_image_endpoint(provider, endpoint_override):
                return f"برای پروایدر تصویر «{provider_name}» endpoint تصویر مشخص نیست."
        return ""

    analysis_rows = list_model_assignments(TASK_EYEBROW_ANALYSIS, only_enabled=True)
    image_rows = list_model_assignments(TASK_EYEBROW_IMAGE_DESIGN, only_enabled=True)

    analysis_ready = False
    for row in analysis_rows:
        problem = provider_problem(str(row.get("provider_name") or ""), str(row.get("model_name") or ""), image_task=False)
        if not problem:
            analysis_ready = True
            break
    if not analysis_ready:
        issues.append("مدل تحلیل عکس ابرو آماده نیست.")
        if analysis_rows:
            sample = analysis_rows[0]
            issues.append(provider_problem(str(sample.get("provider_name") or ""), str(sample.get("model_name") or ""), image_task=False))

    image_ready_count = 0
    image_providers: List[str] = []
    first_image_problem = ""
    for row in image_rows:
        provider_name = str(row.get("provider_name") or "")
        model_name = str(row.get("model_name") or "")
        problem = provider_problem(provider_name, model_name, image_task=True, endpoint_override=str(row.get("endpoint_override") or ""))
        if not problem:
            image_ready_count += 1
            if provider_name not in image_providers:
                image_providers.append(provider_name)
        elif not first_image_problem:
            first_image_problem = problem
    image_ready = image_ready_count > 0
    if not image_ready:
        issues.append("مدل طراحی تصویر آینه ابرو آماده نیست.")
        if first_image_problem:
            issues.append(first_image_problem)
    elif image_ready_count < 2:
        warnings.append("برای fallback بهتر، حداقل دو مدل طراحی تصویر فعال پیشنهاد می‌شود.")

    def _unique_messages(items: List[str]) -> List[str]:
        result: List[str] = []
        for item in items:
            item = str(item or "").strip()
            if item and item not in result:
                result.append(item)
        return result

    issues = _unique_messages(issues)
    warnings = _unique_messages(warnings)
    return {
        "ready": bool(analysis_ready and image_ready),
        "analysis_ready": bool(analysis_ready),
        "image_ready": bool(image_ready),
        "image_ready_count": image_ready_count,
        "image_providers": image_providers,
        "issues": issues,
        "warnings": warnings,
    }


def _slot_is_empty(task_key: str, priority: int) -> bool:
    """آیا اسلات کاربردی هنوز مدل واقعی ندارد؟"""
    task_key = normalize_task_key(task_key)
    priority = _normal_priority(priority, task_key)
    for row in list_model_assignments(task_key):
        try:
            if int(row.get("priority") or 0) != priority:
                continue
        except Exception:
            continue
        if str(row.get("provider_name") or "").strip() and str(row.get("model_name") or "").strip():
            return False
    return True


def _model_ids(items: Iterable[Any], limit: int = 3) -> List[str]:
    ids: List[str] = []
    for item in items or []:
        mid = item.get("id") if isinstance(item, dict) else item
        mid = str(mid or "").strip()
        if mid and mid not in ids:
            ids.append(mid)
        if len(ids) >= limit:
            break
    return ids


def _model_items(items: Iterable[Any], limit: int = 3, auto_assign_only: bool = False) -> List[Dict[str, str]]:
    result: List[Dict[str, str]] = []
    seen = set()
    for item in items or []:
        if isinstance(item, dict):
            if auto_assign_only and item.get("auto_assign") is False:
                continue
            mid = str(item.get("id") or "").strip()
            image_kind = str(item.get("image_kind") or item.get("kind") or "").strip().lower()
        else:
            mid = str(item or "").strip()
            image_kind = ""
        if not mid or mid in seen:
            continue
        seen.add(mid)
        result.append({"id": mid, "image_kind": image_kind})
        if len(result) >= limit:
            break
    return result


def auto_configure_for_provider(provider_name: str, overwrite: bool = False) -> Dict[str, Any]:
    """پرکردن خودکار اسلات‌های خالی آینه زیبایی بعد از افزودن پروایدر.

    این کار فقط اسلات‌های خالی را پر می‌کند تا انتخاب دستی سوپرادمین خراب نشود.
    برای Cloudflare علاوه بر تحلیل عکس، سه مدل تصویرسازی پیش‌فرض هم تنظیم می‌شود.
    """
    try:
        from giso.ai_models_registry import (
            get_best_vision_model,
            get_image_models,
            normalize_provider_name,
        )
    except Exception as exc:
        return {"ok": False, "added": 0, "items": [], "error": str(exc)[:160]}

    provider_name = str(provider_name or "").strip().lower()
    provider_name = provider_name if _is_cloudflare_provider_name(provider_name) else normalize_provider_name(provider_name)
    registry_family = _registry_family_for_provider(provider_name)
    added: List[Dict[str, Any]] = []

    vision_model = get_best_vision_model(registry_family)
    account_slot = _cloudflare_slot_priority(provider_name)
    analysis_overwrite = bool(overwrite and (not account_slot or account_slot == 1))
    if vision_model and (analysis_overwrite or _slot_is_empty(TASK_EYEBROW_ANALYSIS, 1)):
        ok, _message = save_model_assignment(
            TASK_EYEBROW_ANALYSIS,
            1,
            provider_name,
            vision_model,
            enabled=True,
        )
        if ok:
            added.append({"task": TASK_EYEBROW_ANALYSIS, "priority": 1, "model": vision_model})

    image_items = _model_items(get_image_models(registry_family), limit=3, auto_assign_only=True)
    if account_slot and image_items:
        image_items = [image_items[0]]
        priorities = [account_slot]
    else:
        priorities = list(range(1, len(image_items) + 1))
    for priority, item in zip(priorities, image_items):
        model = item["id"]
        image_kind = item.get("image_kind") or ("cloudflare" if registry_family == "cloudflare" else "")
        if registry_family == "cloudflare":
            image_kind = _cloudflare_image_kind_for_model(model, image_kind)
        if not (overwrite or _slot_is_empty(TASK_EYEBROW_IMAGE_DESIGN, priority)):
            continue
        ok, _message = save_model_assignment(
            TASK_EYEBROW_IMAGE_DESIGN,
            priority,
            provider_name,
            model,
            enabled=True,
            image_kind=image_kind,
        )
        if ok:
            added.append({"task": TASK_EYEBROW_IMAGE_DESIGN, "priority": priority, "model": model, "image_kind": image_kind})

    return {"ok": True, "added": len(added), "items": added, "provider": provider_name}


def auto_configure_defaults(overwrite: bool = False) -> Dict[str, Any]:
    """پیشنهاد خودکار مدل‌های آینه زیبایی از پروایدرهای فعال فعلی."""
    try:
        from giso.ai_brain import list_ai_providers
        from giso.ai_models_registry import normalize_provider_name
    except Exception as exc:
        return {"ok": False, "added": 0, "items": [], "error": str(exc)[:160]}

    try:
        rows = list_ai_providers(only_enabled=True) or []
    except Exception:
        rows = []

    names: List[str] = []
    for row in rows:
        name = normalize_provider_name(_row_get(row, "name", ""))
        if name and name not in names:
            names.append(name)
    # Cloudflare برای تصویرسازی ابرو اولویت دارد، چون رجیستری تصویرساز دارد.
    names = (["cloudflare"] if "cloudflare" in names else []) + [n for n in names if n != "cloudflare"]

    all_items: List[Dict[str, Any]] = []
    for name in names:
        result = auto_configure_for_provider(name, overwrite=overwrite)
        all_items.extend(result.get("items") or [])
    return {"ok": True, "added": len(all_items), "items": all_items, "providers": names}


__all__ = [
    "CLOUDFLARE_INPAINTING_MODEL",
    "DEFAULT_CLOUDFLARE_FINAL_IMAGE_MODEL",
    "TASK_EYEBROW_ANALYSIS",
    "TASK_EYEBROW_IMAGE_DESIGN",
    "TASK_DEFS",
    "init_buti_ai_model_assignments",
    "save_model_assignment",
    "list_model_assignments",
    "panel_slots_context",
    "readiness_status",
    "auto_configure_for_provider",
    "auto_configure_defaults",
    "repair_legacy_cloudflare_eyebrow_image_slots",
    "configured_vision_chain",
    "configured_image_provider_dicts",
]
