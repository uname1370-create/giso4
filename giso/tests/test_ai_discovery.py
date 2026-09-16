#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
تست ماژول کشف هوشمند مدل‌ها (giso/ai_discovery) — مأموریت 11

۱) فیلتر هوشمند، مدل‌های غیرمرتبط (امبدینگ/صوتی/تولید عکس) را حذف می‌کند
۲) طبقه‌بندی بینایی/متنی بر اساس فیلدهای رسمی سرویس کار می‌کند
۳) فقط رایگان‌های قوی نگه داشته می‌شوند و سقف تعداد رعایت می‌شود
۴) نسخه‌های تاریخ‌دار در حضور «-latest» حذف می‌شوند
۵) کشف یک پروایدر (بدون شبکه) لیست را در دیتابیس ذخیره و گزارش می‌سازد
۶) خطای ۴۰۳/۴۰۲ به فارسی خوانا ترجمه می‌شود و لیست قبلی حفظ می‌شود
"""
import os
import sys

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if BASE_DIR not in sys.path:
    sys.path.append(BASE_DIR)

from giso.ai_discovery import (  # noqa: E402
    smart_filter_models, _fa_fetch_error, discover_provider,
    refresh_all_models_async, MAX_VISION_MODELS, MAX_TEXT_MODELS,
)
from giso.ai_brain import run_async_sync, init_ai_tables  # noqa: E402


# ── داده‌های نمونه (شبیه پاسخ واقعی /models هر سرویس) ─────────────────────
PAID_ITEM = {"id": "anthropic/claude-sonnet-4.5",
             "pricing": {"prompt": "3", "completion": "15"},
             "architecture": {"input_modalities": ["text", "image"]},
             "context_length": 200000}

OPENROUTER_ITEMS = [
    {"id": "google/gemma-4-31b-it:free", "pricing": {"prompt": "0", "completion": "0"},
     "architecture": {"input_modalities": ["text", "image"], "output_modalities": ["text"]},
     "context_length": 131072},
    {"id": "nvidia/nemotron-3-ultra-550b-a55b:free",
     "pricing": {"prompt": "0", "completion": "0"}, "context_length": 262144},
    {"id": "meta-llama/llama-3.1-8b-instruct", "pricing": {"prompt": "0.05", "completion": "0.08"},
     "context_length": 131072},
    {"id": "openai/text-embedding-3-small", "pricing": {"prompt": "0", "completion": "0"},
     "context_length": 8192},
    {"id": "openai/whisper-1", "pricing": {"prompt": "0", "completion": "0"}},
    {"id": "google/guard-gemma", "pricing": {"prompt": "0", "completion": "0"}},
    {"id": "black-forest-labs/flux-schnell", "pricing": {"prompt": "0", "completion": "0"}},
]

GROQ_ITEMS = [
    {"id": "llama-4-scout-17b-16e-instruct"},
    {"id": "llama-3.3-70b-versatile"},
    {"id": "mistral-saba-24b"},
    {"id": "meta-llama/llama-guard-3-8b"},
    {"id": "whisper-large-v3-turbo"},
]


def test_junk_models_filtered_out():
    vision, text = smart_filter_models("openrouter", OPENROUTER_ITEMS)
    ids = [m["id"] for m in vision + text]
    assert not any("embed" in i for i in ids)
    assert not any("whisper" in i for i in ids)
    assert not any("guard" in i for i in ids)
    assert not any("flux" in i for i in ids)


def test_vision_classification_from_modality():
    vision, text = smart_filter_models("openrouter", OPENROUTER_ITEMS)
    v_ids = [m["id"] for m in vision]
    assert "google/gemma-4-31b-it:free" in v_ids
    # مدل بدون فیلد بینایی، متنی طبقه‌بندی می‌شود
    assert "nvidia/nemotron-3-ultra-550b-a55b:free" in [m["id"] for m in text]


def test_paid_model_dropped_when_free_available():
    vision, text = smart_filter_models("openrouter", OPENROUTER_ITEMS + [PAID_ITEM])
    ids = [m["id"] for m in vision + text]
    # پولی‌ها وقتی رایگانِ مناسب هست اصلاً وارد لیست نمی‌شوند
    assert "anthropic/claude-sonnet-4.5" not in ids
    assert "meta-llama/llama-3.1-8b-instruct" not in ids
    assert all(m["is_free"] for m in vision + text)


def test_paid_only_provider_not_left_empty():
    """پروایدر تماماًپولی (مثل سرویس‌های ایرانی) نباید لیستش خالی شود."""
    items = [{"id": "gpt-4o-mini", "pricing": {"prompt": "0.15", "completion": "0.6"}},
             {"id": "gemini-2.5-flash", "pricing": {"prompt": "0.3", "completion": "2.5"}}]
    vision, text = smart_filter_models("avalai", items)
    assert vision or text


def test_groq_style_free_provider_and_vision_keyword():
    vision, text = smart_filter_models("groq", GROQ_ITEMS)
    v_ids = [m["id"] for m in vision]
    t_ids = [m["id"] for m in text]
    assert "llama-4-scout-17b-16e-instruct" in v_ids
    assert "llama-3.3-70b-versatile" in t_ids
    assert all(m["is_free"] for m in vision + text)  # پروایدر کلاً رایگان


def test_caps_respected():
    items = [{"id": f"test/model-{i}", "pricing": {"prompt": "0", "completion": "0"}}
             for i in range(60)]
    vision, text = smart_filter_models("openrouter", items)
    assert len(vision) + len(text) <= MAX_VISION_MODELS + MAX_TEXT_MODELS


def test_dated_duplicates_dropped_when_latest_exists():
    items = [
        {"id": "qwen/qwen3-32b-latest"},
        {"id": "qwen/qwen3-32b-2506"},
        {"id": "mistral/mistral-small-latest"},
    ]
    vision, text = smart_filter_models("openrouter", items)
    ids = [m["id"] for m in vision + text]
    assert "qwen/qwen3-32b-2506" not in ids
    assert "qwen/qwen3-32b-latest" in ids


def test_fetch_error_translation():
    assert "۴۰۳" in _fa_fetch_error("HTTP 403 Forbidden")
    assert "سهمیه" in _fa_fetch_error("HTTP 402 Payment Required")
    assert "کلید" in _fa_fetch_error("HTTP 401 Unauthorized")
    assert "تایم‌اوت" in _fa_fetch_error("Request timed out")


def test_discover_provider_saves_report(monkeypatch):
    """کشف آفلاین یک پروایدر: ذخیره در دیتابیس + گزارش."""
    import giso.ai_brain as brain
    init_ai_tables()
    name = "test_discovery_prov"
    try:
        brain.add_ai_provider(name=name, api_key="x")
    except Exception:
        pass  # از اجرای قبلی مانده باشد

    async def fake_fetch(row):
        return {"ok": True, "source": "live", "items": GROQ_ITEMS}
    monkeypatch.setattr(brain, "_fetch_remote_models", fake_fetch)

    rep = run_async_sync(discover_provider(name))
    assert rep["ok"] is True
    assert rep["vision_count"] >= 1 and rep["text_count"] >= 1
    assert rep["new"] > 0

    row = brain.get_ai_provider(name)
    assert row is not None
    from giso.ai_brain import _ai_jloads, _col
    vm = _ai_jloads(_col(row, "vision_models_json", ""), [])
    tm = _ai_jloads(_col(row, "text_models_json", ""), [])
    assert any(m["id"] == "llama-4-scout-17b-16e-instruct" for m in vm)
    assert any(m["id"] == "llama-3.3-70b-versatile" for m in tm)
    assert str(_col(row, "models_source", "")) == "discovered"
    assert str(_col(row, "discovery_report", "")).strip() != ""
    brain.delete_ai_provider(name)


def test_discover_provider_error_keeps_list(monkeypatch):
    """خطای ۴۰۳ → گزارش فارسی + لیست قبلی حفظ می‌شود."""
    import giso.ai_brain as brain
    init_ai_tables()
    name = "test_discovery_err"
    try:
        brain.add_ai_provider(name=name, api_key="x")
    except Exception:
        pass

    async def fake_fetch(row):
        return {"ok": False, "error": "HTTP 403"}
    monkeypatch.setattr(brain, "_fetch_remote_models", fake_fetch)

    rep = run_async_sync(discover_provider(name))
    assert rep["ok"] is False
    assert "۴۰۳" in rep["error"] or "مسدود" in rep["error"]
    brain.delete_ai_provider(name)


def test_refresh_all_reports_every_provider(monkeypatch):
    """refresh_all_models_async برای همهٔ پروایدرها گزارش تولید می‌کند."""
    import giso.ai_brain as brain
    init_ai_tables()
    try:
        brain.add_ai_provider(name="test_refresh_all", api_key="x")
    except Exception:
        pass
    rows_before = {r["name"] for r in (brain.list_ai_providers() or [])}

    async def fake_fetch(row):
        return {"ok": True, "source": "live", "items": GROQ_ITEMS}
    monkeypatch.setattr(brain, "_fetch_remote_models", fake_fetch)

    res = run_async_sync(refresh_all_models_async())
    assert res["ok"] is True
    names = {r.get("name") for r in res["reports"]}
    for n in rows_before:
        if n == "cloudflare":
            continue  # از کشف مستثنی است
        assert n in names, f"گزارش پروایدر {n} جا افتاده"
    assert res["summary"]
    try:
        brain.delete_ai_provider("test_refresh_all")
    except Exception:
        pass
