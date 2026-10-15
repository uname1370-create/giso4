# -*- coding: utf-8 -*-
"""دسته‌بندی چهارگانهٔ مدل‌های AI در پنل مدیریت.

دسته‌ها: متن، تحلیل عکس، طراحی تصویر، ارزیابی خروجی.
این ماژول فقط داده برای قالب می‌سازد و هیچ پروایدر، مدل، اسلات یا وضعیت فعالی را تغییر نمی‌دهد
(باز شدن پنل بی‌اثر است). برچسب قیمت از طبقه‌بند مشترک می‌آید؛ قیمت نامشخص هرگز «رایگان» نشان داده نمی‌شود.
"""
from __future__ import annotations

import json
from typing import Any, Dict, List

from giso.ai_models_registry import PRICE_FREE, PRICE_PAID, PRICE_UNKNOWN
from giso.buti_ai.ai_models import (
    TASK_EYEBROW_ANALYSIS,
    TASK_MIRROR_IMAGE_DESIGN,
    TASK_MIRROR_OUTPUT_VALIDATION,
)

PRICE_LABELS = {
    PRICE_FREE: "رایگان",
    PRICE_PAID: "پولی",
    PRICE_UNKNOWN: "قیمت نامشخص",
}
_PRICE_ORDER = {PRICE_FREE: 0, PRICE_UNKNOWN: 1, PRICE_PAID: 2}

CATEGORY_DEFS: List[Dict[str, str]] = [
    {
        "key": "text",
        "label": "متن",
        "task_key": "",
        "help": "مدل متنی مشاور و سایر بخش‌ها از زنجیره failover پروایدرها می‌آید. ترتیب و مدل هر پروایدر در کارت همان پروایدر تنظیم می‌شود.",
    },
    {
        "key": "image_analysis",
        "label": "تحلیل عکس",
        "task_key": TASK_EYEBROW_ANALYSIS,
        "help": "مدل‌های بینایی برای تحلیل عکس ورودی آینه گیسو (ابرو، ناخن، لب، رنگ مو) به ترتیب اولویت.",
    },
    {
        "key": "image_generation",
        "label": "طراحی تصویر",
        "task_key": TASK_MIRROR_IMAGE_DESIGN,
        "help": "مدل تولید/ویرایش تصویر. این زنجیره یک‌بار تنظیم می‌شود و برای ابرو، ناخن، لب و رنگ مو مشترک است.",
    },
    {
        "key": "output_evaluation",
        "label": "ارزیابی خروجی",
        "task_key": TASK_MIRROR_OUTPUT_VALIDATION,
        "help": "به داور خروجی ابرو و لب وصل است: بررسی می‌کند جز ناحیهٔ هدف چیزی تغییر نکرده باشد. اگر مدلی تنظیم نشود، بررسی AI انجام نمی‌شود و فقط بررسی پیکسلی اجرا می‌شود. ناخن و رنگ مو فقط پیکسلی بررسی می‌شوند.",
    },
]
_CATEGORY_BY_TASK = {d["task_key"]: d["key"] for d in CATEGORY_DEFS if d["task_key"]}


def price_label(status: str) -> str:
    return PRICE_LABELS.get(status, PRICE_LABELS[PRICE_UNKNOWN])


def _entries(row: Any, column: str) -> List[Dict[str, Any]]:
    from giso.ai_brain import _col

    try:
        raw = json.loads(_col(row, column, "") or "[]")
    except Exception:
        return []
    out: List[Dict[str, Any]] = []
    for item in raw if isinstance(raw, list) else []:
        if isinstance(item, dict):
            mid = str(item.get("id") or "").strip()
            if mid and not item.get("disabled"):
                out.append({"id": mid, "status": str(item.get("price_status") or PRICE_UNKNOWN)})
        elif str(item or "").strip():
            out.append({"id": str(item).strip(), "status": PRICE_UNKNOWN})
    return out


def _sorted_free_first(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return sorted(items, key=lambda i: _PRICE_ORDER.get(i["status"], 1))


def provider_model_index() -> Dict[str, Dict[str, List[Dict[str, Any]]]]:
    """برای هر پروایدر: مدل‌های بینایی و متنی با وضعیت قیمت، رایگان‌ها اول."""
    from giso.ai_brain import _col, list_ai_providers

    index: Dict[str, Dict[str, List[Dict[str, Any]]]] = {}
    try:
        rows = list_ai_providers() or []
    except Exception:
        rows = []
    for row in rows:
        name = str(_col(row, "name", "") or "").strip().lower()
        if not name:
            continue
        index[name] = {
            "vision": _sorted_free_first(_entries(row, "vision_models_json")),
            "text": _sorted_free_first(_entries(row, "text_models_json")),
            "enabled": bool(_col(row, "enabled", 0)),
        }
    return index


def _option(model_id: str, provider: str, status: str) -> Dict[str, str]:
    return {
        "value": model_id,
        "provider": provider,
        "price_status": status,
        "label": f"{provider} — {price_label(status)}",
    }


def build_category_view(bm: Dict[str, Any]) -> Dict[str, Any]:
    """bm = خروجی panel_slots_context؛ همان را با دسته‌ها و برچسب قیمت برمی‌گرداند."""
    from giso.ai_runtime import get_failover_chain

    bm = dict(bm or {})
    index = provider_model_index()
    providers = bm.get("providers") or []
    provider_names = {str(p.get("name") or "").strip().lower(): p for p in providers}

    all_options: List[Dict[str, str]] = []
    seen_all = set()
    for pname, groups in index.items():
        for kind in ("vision", "text"):
            for item in groups.get(kind, []):
                key = (pname, item["id"])
                if key in seen_all:
                    continue
                seen_all.add(key)
                all_options.append(_option(item["id"], pname, item["status"]))
    all_options.sort(key=lambda o: _PRICE_ORDER.get(o["price_status"], 1))

    chain_names: List[str] = []
    try:
        chain_names = [str(n).strip().lower() for n in (get_failover_chain() or [])]
    except Exception:
        chain_names = []

    slots = []
    for slot in bm.get("slots") or []:
        item = dict(slot)
        item["category_key"] = _CATEGORY_BY_TASK.get(item.get("task_key"), "")
        slots.append(item)

    categories: List[Dict[str, Any]] = []
    for definition in CATEGORY_DEFS:
        cat = dict(definition)
        cat["slots"] = [s for s in slots if s.get("category_key") == cat["key"]]
        if cat["key"] == "text":
            chain_rows = []
            for pos, pname in enumerate(chain_names, start=1):
                prov = provider_names.get(pname, {})
                chain_rows.append({
                    "position": pos,
                    "name": pname,
                    "model": str(prov.get("selected_model") or ""),
                    "enabled": bool(prov.get("enabled", False)),
                })
            text_opts = []
            for pname in chain_names:
                for item in index.get(pname, {}).get("text", []):
                    text_opts.append(_option(item["id"], pname, item["status"]))
            cat["chain"] = chain_rows
            cat["options"] = text_opts
        elif cat["key"] == "image_analysis":
            opts = []
            for pname, groups in index.items():
                for item in groups.get("vision", []):
                    opts.append(_option(item["id"], pname, item["status"]))
            cat["options"] = opts
        elif cat["key"] == "image_generation":
            opts = []
            for cand in bm.get("image_candidates") or []:
                pname = str(cand.get("provider") or "").strip().lower()
                status = PRICE_UNKNOWN
                for item in index.get(pname, {}).get("vision", []) + index.get(pname, {}).get("text", []):
                    if item["id"] == cand.get("model"):
                        status = item["status"]
                opts.append(_option(str(cand.get("model") or ""), pname, status))
            cat["options"] = opts
        else:
            opts = []
            for pname, groups in index.items():
                for item in groups.get("vision", []):
                    opts.append(_option(item["id"], pname, item["status"]))
            cat["options"] = opts
        categories.append(cat)

    bm["categories"] = categories
    bm["all_model_options"] = all_options
    bm["price_labels"] = PRICE_LABELS
    bm["slots"] = slots
    return bm
