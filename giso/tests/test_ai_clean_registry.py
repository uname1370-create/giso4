# -*- coding: utf-8 -*-
"""تست‌های «لیست تمیز هوش مصنوعی» (مأموریت ۱۴۰۵-۰۶-۱۸) — فقط خواندنی، بدون تغییر دیتابیس.

لیست تمیز: سرویس‌های واقعاً رایگان و پاسخگو برای پروژه (گوک، اوپن‌روتر،
میسترال، سامبانوا، کلودفلر) + جمینای کارفرما از طریق ورکر. پروایدرهای
حذف‌شده: HuggingFace و Cerebras (به دستور کارفرما؛ در پروژه جواب نمی‌دادند).
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))


def test_retired_providers_removed_from_registry():
    from giso.ai_models_registry import PROVIDERS
    assert "huggingface" not in PROVIDERS
    assert "cerebras" not in PROVIDERS


def test_clean_registry_providers_exist():
    from giso.ai_models_registry import PROVIDERS, get_provider
    for name in ("groq", "openrouter", "mistral", "sambanova", "cloudflare",
                 "gemini", "gapgpt", "avalai"):
        assert name in PROVIDERS, f"پروایدر {name} از رجیستری پاک حذف شده"
    assert get_provider("mistral")["base_url"] == "https://api.mistral.ai/v1"
    assert get_provider("sambanova")["base_url"] == "https://api.sambanova.ai/v1"
    assert get_provider("groq")["base_url"] == "https://api.groq.com/openai/v1"


def test_openrouter_free_models_current():
    """مدل‌های رایگان اوپن‌روتر مطابق وضعیت سپتامبر ۲۰۲۶ (بدون مدل مرده)."""
    from giso.ai_models_registry import get_provider
    p = get_provider("openrouter")
    vision_ids = [m["id"] for m in p["vision_models"]]
    all_ids = vision_ids + [m["id"] for m in p["text_models"]]
    # مدل‌های مرده/حذف‌شده از :free اوپن‌روتر نباید باشند
    assert "google/gemma-3-27b-it:free" not in all_ids
    assert "meta-llama/llama-3.3-70b-instruct:free" not in all_ids
    # مدل‌های بینایی رایگان فعلی
    for mid in ("google/gemma-4-31b-it:free",
                "thinkingmachines/inkling:free",
                "google/gemma-4-26b-a4b-it:free"):
        assert mid in vision_ids, f"{mid} باید در بینایی اوپن‌روتر باشد"


def test_groq_free_models_current():
    from giso.ai_models_registry import get_provider
    p = get_provider("groq")
    ids = [m["id"] for m in p["vision_models"] + p["text_models"]]
    assert "meta-llama/llama-4-scout-17b-16e-instruct" in ids
    assert "llama-3.3-70b-versatile" in ids
    assert "qwen3-32b" in ids
    # مدل‌های از رده خارج
    assert "qwen-qwq-32b" not in ids
    assert "meta-llama/llama-4-maverick-17b-128e-instruct" not in ids


def test_display_name_normalization():
    from giso.ai_models_registry import normalize_provider_name
    assert normalize_provider_name("Groq") == "groq"
    assert normalize_provider_name("Mistral AI") == "mistral"
    assert normalize_provider_name("SambaNova") == "sambanova"
    assert normalize_provider_name("cloudflare workers ai") == "cloudflare"
    assert normalize_provider_name("OpenRouter") == "openrouter"


def test_vision_keyword_detection_for_clean_list():
    """مدل‌های بینایی لیست تمیز باید در آنالیز عکس تشخیص داده شوند."""
    from giso.analysis import _is_vision_model
    assert _is_vision_model("meta-llama/llama-4-scout-17b-16e-instruct")
    assert _is_vision_model("google/gemma-4-31b-it:free")
    assert _is_vision_model("thinkingmachines/inkling:free")
    assert _is_vision_model("nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free")
    assert _is_vision_model("mistral-small-latest")
    # مدل صرفاً متنی نباید بینایی فرض شود
    assert not _is_vision_model("llama-3.3-70b-versatile")
    assert not _is_vision_model("nvidia/nemotron-3-ultra-550b-a55b:free")


def test_chat_failover_chain_free_first():
    from giso.ai_runtime_policy import DEFAULT_ACTIVE_PROVIDER_ORDER
    assert "huggingface" not in DEFAULT_ACTIVE_PROVIDER_ORDER
    assert "cerebras" not in DEFAULT_ACTIVE_PROVIDER_ORDER
    assert DEFAULT_ACTIVE_PROVIDER_ORDER[0] == "groq"
    for name in ("openrouter", "sambanova", "mistral"):
        assert name in DEFAULT_ACTIVE_PROVIDER_ORDER


def test_vision_priority_free_first():
    from giso.analysis import VISION_PRIORITY_PROVIDERS
    assert VISION_PRIORITY_PROVIDERS[0] == "groq"
    assert "cerebras" not in VISION_PRIORITY_PROVIDERS
    assert "huggingface" not in VISION_PRIORITY_PROVIDERS


def test_retired_providers_disabled_at_seed():
    """پروایدرهای بازنشسته در شروع سرور غیرفعال می‌شوند (حذف نمی‌شوند)."""
    from giso.ai_brain import RETIRED_PROVIDERS, REGISTRY_SEED_PROVIDERS
    assert "huggingface" in RETIRED_PROVIDERS
    assert "cerebras" in RETIRED_PROVIDERS
    assert "llm7" in RETIRED_PROVIDERS
    assert "mistral" in REGISTRY_SEED_PROVIDERS
    assert "sambanova" in REGISTRY_SEED_PROVIDERS
