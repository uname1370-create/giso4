# -*- coding: utf-8 -*-
"""تنظیمات مدل‌های اختصاصی آینه گیسو.

این ماژول عمداً داخل `giso/buti_ai/` است تا سناریوی آینه گیسو
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

TASK_EYEBROW_ANALYSIS = "eyebrow_analysis"  # legacy key; now used as the shared آینه گیسو photo-analysis task
TASK_MIRROR_IMAGE_DESIGN = "mirror_image_design"
# Deprecated per-service keys remain readable and migrate into the shared task.
TASK_EYEBROW_IMAGE_DESIGN = "eyebrow_image_design"
TASK_NAIL_IMAGE_DESIGN = "nail_image_design"
TASK_LIP_IMAGE_DESIGN = "lip_shading_image_design"
TASK_HAIR_COLOR_IMAGE_DESIGN = "hair_color_image_design"
LEGACY_IMAGE_DESIGN_TASK_KEYS = (
    TASK_EYEBROW_IMAGE_DESIGN,
    TASK_NAIL_IMAGE_DESIGN,
    TASK_LIP_IMAGE_DESIGN,
    TASK_HAIR_COLOR_IMAGE_DESIGN,
)
TASK_MIRROR_OUTPUT_VALIDATION = "mirror_output_validation"
IMAGE_DESIGN_TASK_KEYS = (TASK_MIRROR_IMAGE_DESIGN,)
VISION_TASK_KEYS = (TASK_EYEBROW_ANALYSIS, TASK_MIRROR_OUTPUT_VALIDATION)
# فقط تحلیل عکس هنگام افزودن پروایدر خودکار پر می‌شود؛ داور خروجی دستی است تا هزینهٔ اضافهٔ ناخواسته نداشته باشد
AUTO_FILL_VISION_TASK_KEYS = (TASK_EYEBROW_ANALYSIS,)
CLOUDFLARE_INPAINTING_MODEL = "@cf/runwayml/stable-diffusion-v1-5-inpainting"
CLOUDFLARE_FLUX_MODEL = "@cf/black-forest-labs/flux-2-klein-4b"
DEFAULT_CLOUDFLARE_FINAL_IMAGE_MODEL = CLOUDFLARE_INPAINTING_MODEL
CLOUDFLARE_INPAINTING_KINDS = {"cloudflare_inpainting", "cloudflare_inpaint", "inpainting", "mask_inpainting"}
LEGACY_UNSUPPORTED_CLOUDFLARE_FINAL_MODELS = {
    "@cf/black-forest-labs/flux-1-schnell",
    "@cf/stabilityai/stable-diffusion-xl-base-1.0",
}

TASK_DEFS: Dict[str, Dict[str, Any]] = {
    TASK_EYEBROW_ANALYSIS: {
        "label": "آینه گیسو — تحلیل عکس ورودی",
        "short_label": "تحلیل عکس",
        "kind": "vision",
        "slots": 3,
        "help": "مدل‌های بینایی مخصوص بخش آینه گیسو، به‌ترتیب اولویت؛ اگر cf1 خطا داد، cf2/cf3 یا مدل بعدی امتحان می‌شود.",
    },
    TASK_MIRROR_IMAGE_DESIGN: {
        "label": "آینه گیسو — طراحی تصویر مشترک همه خدمات",
        "short_label": "طراحی تصویر",
        "kind": "image",
        "slots": 3,
        "help": "این زنجیره تصویرسازی/inpainting یک‌بار تنظیم می‌شود و برای ابرو، ناخن، لب و رنگ مو به‌ترتیب اولویت به کار می‌رود؛ prompt و mask هر خدمت جداگانه حفظ می‌شود.",
    },
    TASK_MIRROR_OUTPUT_VALIDATION: {
        "label": "آینه گیسو — اعتبارسنجی خروجی نهایی",
        "short_label": "اعتبارسنجی خروجی",
        "kind": "vision",
        "slots": 3,
        "help": "مدل بینایی برای بررسی خروجی نهایی؛ تغییر داخل mask، حفظ بیرون mask و نبود تغییر ناخواسته را کنترل می‌کند.",
    },
}

# کاربرد متنی (مشاور/چت). جدا از TASK_DEFS تا تب آینهٔ گیسو تغییر نکند؛
# فقط بخش «مدیریت و انتخاب مدل‌ها» و مسیر چت متنی از آن می‌خوانند.
TASK_TEXT_CHAT = "text_chat"
TEXT_TASK_DEFS: Dict[str, Dict[str, Any]] = {
    TASK_TEXT_CHAT: {
        "label": "متن — مشاور و چت",
        "short_label": "متن",
        "kind": "text",
        "slots": 3,
        "help": "مدل متنی برای مشاور و چت‌ها به ترتیب اولویت. اگر مدل اول خطای قابل بازیابی بدهد، مدل بعدی امتحان می‌شود.",
    },
}
# سه دستهٔ بخش «مدیریت و انتخاب مدل‌ها» → کاربرد ذخیره‌سازی و قابلیت لازم
MODEL_SECTION_CATEGORIES = {
    "text": {"task_key": TASK_TEXT_CHAT, "capability": "text", "label": "متن"},
    "image_analysis": {"task_key": TASK_EYEBROW_ANALYSIS, "capability": "vision", "label": "تحلیل عکس"},
    "image_generation": {"task_key": TASK_MIRROR_IMAGE_DESIGN, "capability": "image_gen", "label": "ساخت/ویرایش تصویر"},
}


def _task_meta(task_key: str) -> Dict[str, Any]:
    return TASK_DEFS.get(task_key) or TEXT_TASK_DEFS.get(task_key) or {}


SERVICE_IMAGE_TASK_MAP = {
    "eyebrow": TASK_MIRROR_IMAGE_DESIGN,
    "nail": TASK_MIRROR_IMAGE_DESIGN,
    "lip_shading": TASK_MIRROR_IMAGE_DESIGN,
    "hair_color": TASK_MIRROR_IMAGE_DESIGN,
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


_DIGIT_TRANSLATION = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")


def _normalize_provider_digits(provider_name: str) -> str:
    return str(provider_name or "").strip().lower().translate(_DIGIT_TRANSLATION)


def _is_cloudflare_provider_name(provider_name: str) -> bool:
    name = _normalize_provider_digits(provider_name)
    if name == "cloudflare" or re.fullmatch(r"cf[1-3]", name) is not None:
        return True
    # نمونه‌های جدید Cloudflare (مثل cloudflare-1a2b3c) از روی خانوادهٔ شناسه تشخیص داده می‌شوند.
    try:
        from giso.ai_brain import provider_family_of
        return provider_family_of(name) == "cloudflare"
    except Exception:
        return False


def _cloudflare_slot_priority(provider_name: str) -> int:
    match = re.fullmatch(r"cf([0-9]+)", _normalize_provider_digits(provider_name))
    if not match:
        return 0
    try:
        return max(1, min(int(TASK_DEFS[TASK_MIRROR_IMAGE_DESIGN]["slots"]), int(match.group(1))))
    except Exception:
        return 0


def _registry_family_for_provider(provider_name: str) -> str:
    if _is_cloudflare_provider_name(provider_name):
        return "cloudflare"
    try:
        from giso.ai_brain import provider_family_of
        return provider_family_of(provider_name)
    except Exception:
        return _normalize_provider_digits(provider_name)


def _cloudflare_image_kind_for_model(model_name: str, image_kind: str = "") -> str:
    """Preserve explicit capabilities and always route the documented inpainting model through masks."""
    model = str(model_name or "").strip()
    kind = str(image_kind or "").strip().lower()
    # This model requires an input image and mask; a generic saved "cloudflare" kind
    # must not accidentally route it through the Flux text-to-image handler.
    if model == CLOUDFLARE_INPAINTING_MODEL:
        return "cloudflare_inpainting"
    if kind:
        return "cloudflare_inpainting" if kind in CLOUDFLARE_INPAINTING_KINDS else kind
    return "cloudflare"


def _is_supported_cloudflare_final_model(model_name: str, image_kind: str = "") -> bool:
    """Only documented/safe Cloudflare models enter final service image generation."""
    model = str(model_name or "").strip()
    kind = _cloudflare_image_kind_for_model(model, image_kind)
    if kind in CLOUDFLARE_INPAINTING_KINDS:
        return model == CLOUDFLARE_INPAINTING_MODEL
    return model == CLOUDFLARE_FLUX_MODEL


def _migrate_legacy_image_design_assignments(conn) -> int:
    """Merge old per-service image chains into the shared mirror image chain once."""
    placeholders = ",".join("?" for _ in LEGACY_IMAGE_DESIGN_TASK_KEYS)
    rows = conn.execute(
        f"""
        SELECT id, task_key, priority, provider_name, model_name, enabled,
               image_kind, endpoint_override, created_at, updated_at
        FROM buti_ai_model_assignments
        WHERE task_key IN ({placeholders})
        """,
        LEGACY_IMAGE_DESIGN_TASK_KEYS,
    ).fetchall()
    if not rows:
        return 0

    slots = int(TASK_DEFS[TASK_MIRROR_IMAGE_DESIGN]["slots"])
    current_rows = conn.execute(
        """
        SELECT priority, provider_name, model_name, image_kind, endpoint_override
        FROM buti_ai_model_assignments
        WHERE task_key=?
        """,
        (TASK_MIRROR_IMAGE_DESIGN,),
    ).fetchall()
    occupied = {int(row[0] or 1) for row in current_rows}
    identities = {
        (
            str(row[1] or "").strip().lower(),
            str(row[2] or "").strip(),
            _cloudflare_image_kind_for_model(str(row[2] or ""), str(row[3] or "")),
            str(row[4] or "").strip(),
        )
        for row in current_rows
    }
    legacy_order = {key: index for index, key in enumerate(LEGACY_IMAGE_DESIGN_TASK_KEYS)}
    rows = sorted(
        rows,
        key=lambda row: (
            int(row[2] or 1),
            legacy_order.get(str(row[1] or ""), len(legacy_order)),
            int(row[0] or 0),
        ),
    )
    now = _now()
    migrated = 0
    for row in rows:
        provider_name = str(row[3] or "").strip().lower()
        model_name = str(row[4] or "").strip()
        if not provider_name or not model_name:
            continue
        image_kind = _cloudflare_image_kind_for_model(model_name, str(row[6] or ""))
        endpoint_override = str(row[7] or "").strip()
        identity = (provider_name, model_name, image_kind, endpoint_override)
        if identity in identities:
            continue

        try:
            preferred_priority = max(1, min(slots, int(row[2] or 1)))
        except (TypeError, ValueError):
            preferred_priority = 1
        if preferred_priority in occupied:
            preferred_priority = next((p for p in range(1, slots + 1) if p not in occupied), 0)
        if not preferred_priority:
            continue

        enabled_value = str(row[5] if row[5] is not None else "0").strip().lower()
        enabled = int(enabled_value not in {"", "0", "false", "off", "no"})
        created_at = str(row[8] or now)
        updated_at = str(row[9] or created_at)
        conn.execute(
            """
            INSERT OR IGNORE INTO buti_ai_model_assignments (
                task_key, priority, provider_name, model_name, enabled,
                image_kind, endpoint_override, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                TASK_MIRROR_IMAGE_DESIGN, preferred_priority, provider_name,
                model_name, enabled, image_kind, endpoint_override,
                created_at, updated_at,
            ),
        )
        occupied.add(preferred_priority)
        identities.add(identity)
        migrated += 1
    return migrated


def init_buti_ai_model_assignments(conn=None) -> None:
    """ایجاد جدول تنظیم مدل‌های آینه گیسو، افزودنی و امن."""
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
        _migrate_legacy_image_design_assignments(c)
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
    if key in LEGACY_IMAGE_DESIGN_TASK_KEYS:
        return TASK_MIRROR_IMAGE_DESIGN
    return key if (key in TASK_DEFS or key in TEXT_TASK_DEFS) else ""


def _normal_priority(priority: Any, task_key: str) -> int:
    try:
        value = int(priority or 1)
    except (TypeError, ValueError):
        value = 1
    slots = int(_task_meta(task_key).get("slots") or 1)
    return max(1, min(max(1, slots), value))


def save_model_assignment(task_key: str, priority: Any, provider_name: str, model_name: str,
                          enabled: bool = True, image_kind: str = "",
                          endpoint_override: str = "", validate: bool = False) -> tuple[bool, str]:
    """ذخیره یک اسلات مدل برای آینه گیسو.

    ذخیره بر اساس `(task_key, priority)` است؛ یعنی اسلات ۱ مدل اصلی و
    اسلات‌های بعدی fallback هستند. این تنظیمات فقط در Buti AI/آینه گیسو مصرف می‌شود.
    """
    task_key = normalize_task_key(task_key)
    if not task_key:
        return False, "نوع کاربرد مدل نامعتبر است."
    priority = _normal_priority(priority, task_key)
    provider_name = str(provider_name or "").strip().lower()
    model_name = str(model_name or "").strip()
    image_kind = str(image_kind or "").strip().lower()
    if task_key in IMAGE_DESIGN_TASK_KEYS and model_name == CLOUDFLARE_INPAINTING_MODEL:
        image_kind = "cloudflare_inpainting"
    endpoint_override = str(endpoint_override or "").strip()

    if not provider_name or not model_name:
        return False, "نام پروایدر و نام مدل الزامی است."
    if enabled and validate:
        # اعتبارسنجی سمت سرور برای ذخیرهٔ دستی از پنل (ذخیرهٔ خودکار/داخلی بدون این قاعده می‌ماند)
        problem = validate_slot_selection(task_key, provider_name, model_name, image_kind, endpoint_override)
        if problem:
            return False, problem

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
        return True, "تنظیم مدل آینه گیسو ذخیره شد."
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
        stored_key = str(row.get("task_key") or "").strip().lower()
        # Legacy rows remain in storage for recovery, but the panel only edits the
        # migrated shared chain and must not let a legacy row override it.
        if stored_key in LEGACY_IMAGE_DESIGN_TASK_KEYS:
            continue
        key = normalize_task_key(stored_key)
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
    """گزینه‌های قابل نمایش در پنل مدیریت برای انتخاب مدل آینه گیسو."""
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
    image_candidates: List[Dict[str, str]] = []
    if list_ai_providers is None:
        return {"providers": providers, "models": all_models, "image_candidates": image_candidates[:30]}

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
            model_l = str(model or "").lower()
            if any(token in model_l for token in ("flux", "image", "diffusion", "sdxl", "dall-e", "gpt-image", "imagen", "kandinsky", "stable")):
                image_candidates.append({"provider": name, "model": model, "hint": "احتمالاً مدل تصویر"})
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
    return {"providers": providers, "models": all_models, "image_candidates": image_candidates[:30]}


def panel_slots_context() -> Dict[str, Any]:
    """ساخت داده ساده برای تب «مدل‌های آینه گیسو» در پنل.

    مسیر خواندنی است: تعمیر اسلات‌های قدیمی اینجا اجرا نمی‌شود؛ فقط دکمهٔ صریح
    «اصلاح مدل‌های ناسازگار» در پنل آن را انجام می‌دهد.
    """
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
        "scope_label": "فقط آینه گیسو / Buti AI",
        "scope_note": "این اسلات‌ها روی مشاور عمومی، ربات، آنالیز مو/پوست و سایر بخش‌های گیسو اثر نمی‌گذارند؛ فقط مسیر آینه گیسو از آن‌ها می‌خواند. مدل‌های طراحی تصویر در اینجا یک‌بار تنظیم می‌شوند و برای ابرو، ناخن، لب و رنگ مو مشترک‌اند؛ تحلیل و اعتبارسنجی جدا هستند.",
        "slots": slots,
        "providers": options.get("providers", []),
        "model_options": options.get("models", []),
        "readiness": readiness_status(),
        "image_candidates": options.get("image_candidates", []),
        "recommended_image_model": DEFAULT_CLOUDFLARE_FINAL_IMAGE_MODEL,
    }


def configured_text_chain() -> List[Dict[str, str]]:
    """زنجیرهٔ مدل‌های متنی (فقط اسلات‌های فعال و پروایدرهای فعال، به ترتیب اولویت)."""
    return configured_vision_chain(TASK_TEXT_CHAT)


def clear_model_assignment(task_key: str, priority: Any) -> tuple[bool, str]:
    """خالی کردن یک اسلات؛ فقط همان (کاربرد، اولویت) حذف می‌شود."""
    task_key = normalize_task_key(task_key)
    if not task_key:
        return False, "نوع کاربرد مدل نامعتبر است."
    priority = _normal_priority(priority, task_key)
    init_buti_ai_model_assignments()
    try:
        with get_giso_db_conn() as conn:
            conn.execute("DELETE FROM buti_ai_model_assignments WHERE task_key=? AND priority=?",
                         (task_key, priority))
            conn.commit()
        return True, "اسلات خالی شد."
    except Exception as exc:
        logger.error("clear_model_assignment failed: %s", exc)
        return False, "خالی کردن اسلات انجام نشد."


def save_model_section(category: str, selections: List[Optional[tuple]]) -> tuple[bool, str]:
    """ذخیرهٔ سه اسلات یک دسته؛ اعتبارسنجی کامل قبل از هر نوشتن (همه یا هیچ).

    selections: فهرست حداکثر سه عضوی به ترتیب اولویت؛ هر عضو (provider, model) یا None.
    مدل فقط وقتی پذیرفته می‌شود که برای قابلیت همان دسته «تأییدشده» یا «احتمالی» باشد،
    پروایدرش فعال باشد و در یک دسته تکراری نباشد.
    """
    from giso.ai_brain import get_ai_provider
    from giso.ai_discovery import COMPATIBLE_STATUSES, STATUS_LABELS_FA, model_capability_for_provider

    spec = MODEL_SECTION_CATEGORIES.get(category)
    if not spec:
        return False, "دسته نامعتبر است."
    task_key, capability = spec["task_key"], spec["capability"]
    slots = int(_task_meta(task_key).get("slots") or 1)
    errors: List[str] = []
    seen: set = set()
    plan: List[tuple] = []
    previous = {row.get("priority"): row for row in list_model_assignments(task_key)}
    for idx in range(1, slots + 1):
        sel = selections[idx - 1] if idx - 1 < len(selections) else None
        if not sel:
            plan.append((idx, None))
            continue
        provider_name, model_name = str(sel[0] or "").strip().lower(), str(sel[1] or "").strip()
        if not provider_name or not model_name:
            errors.append(f"اسلات {idx}: پروایدر یا مدل خالی است.")
            continue
        if (provider_name, model_name) in seen:
            errors.append(f"اسلات {idx}: «{model_name}» قبلاً در همین دسته انتخاب شده است.")
            continue
        seen.add((provider_name, model_name))
        prev = previous.get(idx) or {}
        same = (prev.get("provider_name") == provider_name and prev.get("model_name") == model_name)
        problem = validate_slot_selection(
            task_key, provider_name, model_name,
            image_kind=(prev.get("image_kind") or "") if same else "",
            endpoint_override=(prev.get("endpoint_override") or "") if same else "",
        )
        if problem:
            errors.append(f"اسلات {idx}: {problem}")
            continue
        plan.append((idx, (provider_name, model_name)))
    if errors:
        return False, " | ".join(errors)

    previous = {row.get("priority"): row for row in list_model_assignments(task_key)}
    for idx, sel in plan:
        if sel is None:
            clear_model_assignment(task_key, idx)
            continue
        provider_name, model_name = sel
        prev = previous.get(idx) or {}
        same = (prev.get("provider_name") == provider_name and prev.get("model_name") == model_name)
        save_model_assignment(
            task_key, idx, provider_name, model_name, enabled=True,
            image_kind=(prev.get("image_kind") or "") if same else "",
            endpoint_override=(prev.get("endpoint_override") or "") if same else "",
        )
    return True, f"تنظیم دستهٔ «{spec['label']}» ذخیره شد."


# ───────── سیاست مرکزی انتخاب مدل ─────────
# همهٔ مسیرهای واقعی (متن، تحلیل عکس، تولید تصویر، داور) زنجیرهٔ ذخیره‌شدهٔ همین بخش را
# می‌خوانند. تنها تصمیم «خطای قابل بازیابی» و «اعتبار یک اسلات» در این فایل است.
TASK_CAPABILITY = {
    TASK_TEXT_CHAT: "text",
    TASK_EYEBROW_ANALYSIS: "vision",
    TASK_MIRROR_OUTPUT_VALIDATION: "vision",
    TASK_MIRROR_IMAGE_DESIGN: "image_gen",
}

_CHAIN_STOP_PATTERN = re.compile(r"HTTP (400|401|402|403|422)\b")
_CHAIN_STOP_TEXT = ("api key", "کلید", "پروایدر غیرفعال", "مدلی انتخاب نشده", "base url",
                    "api root", "{account_id}", "httpx نصب نیست")


def is_recoverable_chain_error(error_text: Any) -> bool:
    """فقط خطای قابل بازیابی به مدل بعدی زنجیره می‌رود.

    مجوز/کلید (401/403)، درخواست نامعتبر (400/422)، سهمیه/پرداخت (402) و پیکربندی ناقص
    زنجیره را متوقف می‌کنند تا تلاش بی‌هدف و حلقه‌ای رخ ندهد.
    timeout، 429، 5xx، 404 و خطاهای ناشناخته قابل بازیابی‌اند.
    """
    text = str(error_text or "")
    if _CHAIN_STOP_PATTERN.search(text):
        return False
    low = text.lower()
    if any(token in low for token in _CHAIN_STOP_TEXT):
        return False
    return True


def image_slot_problem(provider_name: str, provider_row: Any, model_name: str,
                       image_kind: str = "", endpoint_override: str = "") -> str:
    """دلیلی که یک اسلات تصویر قابل اجرا نیست، یا "" اگر قابل اجراست.

    همان قواعد `configured_image_provider_dicts` است تا ذخیره و اجرا یکسان قضاوت کنند.
    """
    if provider_row is None:
        return "پروایدر پیدا نشد"
    if not str(_row_get(provider_row, "api_key", "") or "").strip():
        return "کلید API ثبت نشده است"
    kind = str(image_kind or "").strip().lower()
    provider_kind = str(_row_get(provider_row, "kind", "") or "").strip().lower()
    if provider_kind == "cloudflare" or _is_cloudflare_provider_name(provider_name):
        if not _cloudflare_run_root(provider_row):
            return "آدرس Cloudflare کامل نیست (شناسهٔ حساب لازم است)"
        effective = _cloudflare_image_kind_for_model(model_name, kind)
        if not _is_supported_cloudflare_final_model(model_name, effective):
            return "این مدل Cloudflare برای ساخت/ویرایش عکس پشتیبانی نمی‌شود"
        return ""
    if not _openai_image_endpoint(provider_row, endpoint_override):
        return "endpoint تصویر ساخته نشد"
    return ""


def validate_slot_selection(task_key: str, provider_name: str, model_name: str,
                            image_kind: str = "", endpoint_override: str = "") -> str:
    """اعتبارسنجی یک انتخاب اسلات با همان قواعدی که مصرف‌کننده‌ها اجرا می‌کنند.

    خروجی: "" اگر پذیرفته است؛ وگرنه دلیل فارسی. کلید API در پیام نمی‌آید.
    """
    from giso.ai_brain import get_ai_provider
    from giso.ai_discovery import COMPATIBLE_STATUSES, STATUS_LABELS_FA, model_capability_for_provider

    task = normalize_task_key(task_key) or str(task_key or "")
    capability = TASK_CAPABILITY.get(task)
    if not capability:
        return "نوع کاربرد مدل نامعتبر است."
    provider_name = str(provider_name or "").strip().lower()
    model_name = str(model_name or "").strip()
    if not provider_name or not model_name:
        return "نام پروایدر و نام مدل الزامی است."
    row = get_ai_provider(provider_name)
    if row is None:
        return f"پروایدر «{provider_name}» پیدا نشد."
    if not _row_get(row, "enabled", 0):
        return f"پروایدر «{provider_name}» غیرفعال است."
    info = model_capability_for_provider(provider_name, model_name, capability)
    if info["status"] not in COMPATIBLE_STATUSES:
        label = STATUS_LABELS_FA.get(info["status"], info["status"])
        return f"«{model_name}» برای این دسته پذیرفته نشد (وضعیت: {label})."
    if capability == "image_gen":
        problem = image_slot_problem(provider_name, row, model_name, image_kind, endpoint_override)
        if problem:
            return f"«{model_name}»: {problem}."
    return ""


def configured_vision_chain(task_key: str = TASK_EYEBROW_ANALYSIS) -> List[Dict[str, str]]:
    """زنجیره مدل‌های بینایی یک دسته از مدیریت AI (پیش‌فرض: دستهٔ تحلیل عکس)."""
    chain: List[Dict[str, str]] = []
    try:
        from giso.ai_brain import get_ai_provider
    except Exception:
        return chain
    for row in list_model_assignments(task_key or TASK_EYEBROW_ANALYSIS, only_enabled=True):
        provider_name = str(row.get("provider_name") or "").strip().lower()
        model_name = str(row.get("model_name") or "").strip()
        if not provider_name or not model_name:
            continue
        provider = get_ai_provider(provider_name)
        if not provider or not _row_get(provider, "enabled", 0):
            continue
        if _slot_is_explicitly_incompatible(provider_name, model_name, task_key or TASK_EYEBROW_ANALYSIS):
            # مدل صراحتاً ناسازگار با این کاربرد اجرا نمی‌شود؛ unknown/probable دست‌نخورده می‌ماند
            logger.info("model slot skipped (incompatible): provider=%s model=%s task=%s",
                        provider_name, model_name, task_key)
            continue
        chain.append({"provider_name": provider_name, "model_name": model_name})
    return chain


def _slot_is_explicitly_incompatible(provider_name: str, model_name: str, task_key: str) -> bool:
    """True فقط وقتی وضعیت قابلیت مدل برای همین کاربرد «ناسازگار» باشد (خطا در بررسی = False)."""
    capability = TASK_CAPABILITY.get(normalize_task_key(task_key) or task_key)
    if not capability:
        return False
    try:
        from giso.ai_discovery import STATUS_INCOMPATIBLE, model_capability_for_provider
        info = model_capability_for_provider(provider_name, model_name, capability) or {}
    except Exception:
        return False
    return info.get("status") == STATUS_INCOMPATIBLE


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
    """Fix old auto-slots that used unsupported Cloudflare models for photo editing.

    Older configs could leave slot 2/3 as flux-1-schnell or SDXL. Those endpoints
    expect JSON and fail for the current photo-edit flow. If cf2/cf3 providers
    exist, map each slot to that account with the recommended SD 1.5 inpainting
    model; otherwise disable the unsupported extra slot so the user does not see
    repeated errors in final design.
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

        slot_provider_name = f"cf{priority}" if 1 <= priority <= int(TASK_DEFS[TASK_MIRROR_IMAGE_DESIGN]["slots"]) else ""
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
            image_kind=_cloudflare_image_kind_for_model(DEFAULT_CLOUDFLARE_FINAL_IMAGE_MODEL),
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


def image_task_for_service(service_key: str = "eyebrow") -> str:
    """برگرداندن task تصویرسازی مشترک آینه گیسو برای هر خدمت."""
    return SERVICE_IMAGE_TASK_MAP.get(str(service_key or "").strip().lower(), TASK_MIRROR_IMAGE_DESIGN)


def configured_image_provider_dicts(limit: int = 3, task_key: str = "", service_key: str = "eyebrow") -> List[Dict[str, Any]]:
    """providerهای تصویرسازی آینه گیسو از مدیریت AI، بدون لاگ‌کردن کلیدها.

    این تابع هیچ ردیفی را تغییر نمی‌دهد. تعمیر تنظیمات قدیمی فقط از عملیات صریح پنل
    (`repair_legacy_cloudflare_eyebrow_image_slots`) اجرا می‌شود. اسلاتی که قابل اجرا نیست
    با دلیل در لاگ ثبت و کنار گذاشته می‌شود.
    """
    try:
        from giso.ai_brain import get_ai_provider
    except Exception:
        return []

    providers: List[Dict[str, Any]] = []
    image_task_key = normalize_task_key(task_key) or image_task_for_service(service_key)
    for row in list_model_assignments(image_task_key, only_enabled=True):
        if len(providers) >= max(1, int(limit or 3)):
            break
        provider_name = str(row.get("provider_name") or "").strip().lower()
        model_name = str(row.get("model_name") or "").strip()
        try:
            priority = int(row.get("priority") or 1)
        except (TypeError, ValueError):
            priority = 1
        if not provider_name or not model_name:
            continue
        provider = get_ai_provider(provider_name)
        if not provider or not _row_get(provider, "enabled", 0):
            logger.info("image slot skipped: priority=%s provider=%s reason=provider_inactive", priority, provider_name)
            continue
        image_kind = str(row.get("image_kind") or "").strip().lower()
        endpoint_override = row.get("endpoint_override", "")
        problem = image_slot_problem(provider_name, provider, model_name, image_kind, endpoint_override)
        if problem:
            logger.info("image slot skipped: priority=%s provider=%s model=%s reason=%s",
                        priority, provider_name, model_name, problem)
            continue
        api_key = str(_row_get(provider, "api_key", "") or "").strip()
        provider_kind = str(_row_get(provider, "kind", "") or "").strip().lower()
        if provider_kind == "cloudflare" or _is_cloudflare_provider_name(provider_name):
            root = _cloudflare_run_root(provider)
            image_kind = _cloudflare_image_kind_for_model(model_name, image_kind)
            endpoint = root.rstrip("/") + "/" + model_name
        else:
            endpoint = _openai_image_endpoint(provider, endpoint_override)
            image_kind = image_kind or "openai_image_edit"
        if not endpoint:
            continue
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
    """وضعیت آماده‌بودن آینه گیسو برای استفاده واقعی از AI.

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

    # خواندنی: بدون تعمیر خودکار (تعمیر فقط از دکمهٔ صریح پنل)

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
                    return "این مدل Cloudflare برای طراحی عکس نهایی آینه گیسو پشتیبانی نمی‌شود؛ از Stable Diffusion 1.5 Inpainting (پیشنهادی) یا flux-2-klein-4b استفاده کن."
                if not _cloudflare_run_root(provider):
                    return "Cloudflare Account ID یا API Root درست تنظیم نشده است."
            elif not _openai_image_endpoint(provider, endpoint_override):
                return f"برای پروایدر تصویر «{provider_name}» endpoint تصویر مشخص نیست."
        return ""

    analysis_rows = list_model_assignments(TASK_EYEBROW_ANALYSIS, only_enabled=True)
    validation_rows = list_model_assignments(TASK_MIRROR_OUTPUT_VALIDATION, only_enabled=True)

    analysis_ready = False
    for row in analysis_rows:
        problem = provider_problem(str(row.get("provider_name") or ""), str(row.get("model_name") or ""), image_task=False)
        if not problem:
            analysis_ready = True
            break
    if not analysis_ready:
        issues.append("مدل تحلیل عکس آینه گیسو آماده نیست.")
        if analysis_rows:
            sample = analysis_rows[0]
            issues.append(provider_problem(str(sample.get("provider_name") or ""), str(sample.get("model_name") or ""), image_task=False))

    validation_ready = False
    for row in validation_rows:
        problem = provider_problem(str(row.get("provider_name") or ""), str(row.get("model_name") or ""), image_task=False)
        if not problem:
            validation_ready = True
            break
    if not validation_ready:
        warnings.append("مدل اعتبارسنجی خروجی نهایی تنظیم نشده؛ خروجی واقعی AI باید با کنترل mask و diff تأیید شود.")

    image_task = TASK_MIRROR_IMAGE_DESIGN
    image_rows = list_model_assignments(image_task, only_enabled=True)
    total_image_ready_count = 0
    image_providers: List[str] = []
    first_image_problem = ""
    for row in image_rows:
        provider_name = str(row.get("provider_name") or "")
        model_name = str(row.get("model_name") or "")
        problem = provider_problem(
            provider_name,
            model_name,
            image_task=True,
            endpoint_override=str(row.get("endpoint_override") or ""),
        )
        if not problem:
            total_image_ready_count += 1
            if provider_name not in image_providers:
                image_providers.append(provider_name)
        elif not first_image_problem:
            first_image_problem = problem

    image_ready = total_image_ready_count > 0
    if not image_ready:
        issues.append("مدل طراحی تصویر مشترک آینه گیسو آماده نیست.")
        if first_image_problem:
            issues.append(first_image_problem)
    elif total_image_ready_count < 2:
        warnings.append("برای fallback بهتر، حداقل دو مدل فعال در زنجیره مشترک طراحی تصویر پیشنهاد می‌شود.")

    # وضعیت هر خدمت نمایش داده می‌شود، اما همه از همین زنجیرهٔ مشترک می‌خوانند.
    service_image_status: Dict[str, Dict[str, Any]] = {
        service_key: {
            "ready": bool(image_ready),
            "ready_count": total_image_ready_count,
            "providers": list(image_providers),
            "task_key": image_task,
            "problem": first_image_problem,
        }
        for service_key in SERVICE_IMAGE_TASK_MAP
    }

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
        "validation_ready": bool(validation_ready),
        "image_ready": bool(image_ready),
        "image_ready_count": total_image_ready_count,
        "service_image_status": service_image_status,
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
    """پرکردن خودکار اسلات‌های خالی آینه گیسو بعد از افزودن پروایدر.

    این کار فقط اسلات‌های خالی را پر می‌کند تا انتخاب دستی سوپرادمین خراب نشود.
    زنجیرهٔ تصویرسازی مشترک است؛ همهٔ خدمات آینه از همان fallbackها استفاده می‌کنند.
    """
    try:
        from giso.ai_models_registry import (
            get_best_vision_model,
            get_image_models,
            normalize_provider_name,
        )
    except Exception as exc:
        return {"ok": False, "added": 0, "items": [], "error": str(exc)[:160]}

    provider_name = _normalize_provider_digits(provider_name)
    # «cf» نام قدیمی است و باید به کلید «cloudflare» نگاشت شود؛ نمونه‌های جدید نام خودشان را نگه می‌دارند.
    provider_name = provider_name if (_is_cloudflare_provider_name(provider_name) and provider_name != "cf") else normalize_provider_name(provider_name)
    registry_family = _registry_family_for_provider(provider_name)
    added: List[Dict[str, Any]] = []

    vision_model = get_best_vision_model(registry_family)
    account_slot = _cloudflare_slot_priority(provider_name)
    analysis_priority = account_slot or 1
    analysis_overwrite = bool(overwrite)
    for vision_task in AUTO_FILL_VISION_TASK_KEYS:
        priority = min(analysis_priority, int(TASK_DEFS.get(vision_task, {}).get("slots") or analysis_priority))
        if vision_model and (analysis_overwrite or _slot_is_empty(vision_task, priority)):
            ok, _message = save_model_assignment(
                vision_task,
                priority,
                provider_name,
                vision_model,
                enabled=True,
            )
            if ok:
                added.append({"task": vision_task, "priority": priority, "model": vision_model})

    image_items = _model_items(get_image_models(registry_family), limit=3, auto_assign_only=True)
    if registry_family == "cloudflare" and image_items:
        preferred = next(
            (item for item in image_items if item["id"] == DEFAULT_CLOUDFLARE_FINAL_IMAGE_MODEL),
            None,
        )
        if preferred:
            image_items = [preferred] + [item for item in image_items if item["id"] != preferred["id"]]
    if account_slot and image_items:
        image_items = [image_items[0]]
        priorities = [account_slot]
    else:
        priorities = list(range(1, len(image_items) + 1))
    for image_task in IMAGE_DESIGN_TASK_KEYS:
        for priority, item in zip(priorities, image_items):
            model = item["id"]
            image_kind = item.get("image_kind") or ("cloudflare" if registry_family == "cloudflare" else "")
            if registry_family == "cloudflare":
                image_kind = _cloudflare_image_kind_for_model(model, image_kind)
            if not (overwrite or _slot_is_empty(image_task, priority)):
                continue
            ok, _message = save_model_assignment(
                image_task,
                priority,
                provider_name,
                model,
                enabled=True,
                image_kind=image_kind,
            )
            if ok:
                added.append({"task": image_task, "priority": priority, "model": model, "image_kind": image_kind})

    return {"ok": True, "added": len(added), "items": added, "provider": provider_name}


def auto_configure_defaults(overwrite: bool = False) -> Dict[str, Any]:
    """پیشنهاد خودکار مدل‌های آینه گیسو از پروایدرهای فعال فعلی."""
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
    # Cloudflare برای تصویرسازی آینه گیسو اولویت دارد، چون رجیستری تصویرساز دارد.
    names = (["cloudflare"] if "cloudflare" in names else []) + [n for n in names if n != "cloudflare"]

    all_items: List[Dict[str, Any]] = []
    for name in names:
        result = auto_configure_for_provider(name, overwrite=overwrite)
        all_items.extend(result.get("items") or [])
    return {"ok": True, "added": len(all_items), "items": all_items, "providers": names}


__all__ = [
    "CLOUDFLARE_INPAINTING_MODEL",
    "CLOUDFLARE_FLUX_MODEL",
    "DEFAULT_CLOUDFLARE_FINAL_IMAGE_MODEL",
    "TASK_EYEBROW_ANALYSIS",
    "TASK_MIRROR_IMAGE_DESIGN",
    "TASK_EYEBROW_IMAGE_DESIGN",
    "TASK_NAIL_IMAGE_DESIGN",
    "TASK_LIP_IMAGE_DESIGN",
    "TASK_HAIR_COLOR_IMAGE_DESIGN",
    "LEGACY_IMAGE_DESIGN_TASK_KEYS",
    "TASK_MIRROR_OUTPUT_VALIDATION",
    "IMAGE_DESIGN_TASK_KEYS",
    "VISION_TASK_KEYS",
    "SERVICE_IMAGE_TASK_MAP",
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
    "configured_text_chain",
    "TASK_TEXT_CHAT",
    "TEXT_TASK_DEFS",
    "MODEL_SECTION_CATEGORIES",
    "clear_model_assignment",
    "save_model_section",
    "image_task_for_service",
    "configured_image_provider_dicts",
]
