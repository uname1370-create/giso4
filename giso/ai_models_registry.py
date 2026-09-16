# -*- coding: utf-8 -*-
"""
رجیستری مدل‌های هوش مصنوعی گیسو
منبع اصلی مدل‌های پیش‌فرض هر پروایدر

فاز ۱ بازنویسی سیستم AI (ارجاع: 1.md و giso/ai2.md):
- این فایل فقط «داده» است و هیچ رفتار اجرایی را تغییر نمی‌دهد.
- لایه سازگاری `legacy_registry()` خروجی هم‌شکل PROVIDERS_REGISTRY قدیمی می‌دهد.
"""

# ثابت‌های نوع مدل
MODALITY_VISION = "vision"
MODALITY_TEXT = "text"
MODALITY_BOTH = "both"

# ثابت‌های منبع مدل
SOURCE_HARDCODED = "hardcoded"
SOURCE_DISCOVERED = "discovered"
SOURCE_MANUAL_JSON = "manual_json"

PROVIDERS = {
    # ═══ لیست تمیز ۱۴۰۵-۰۶-۱۸ (سپتامبر ۲۰۲۶) — فقط سرویس‌های واقعاً رایگان ═══
    # اولویت: رایگانِ پاسخگو اول؛ هر پروایدر با «نام + API Key» از ربات/پنل اضافه
    # می‌شود و آدرس بیس/مدل‌ها خودکار از همین رجیستری پر می‌شود.
    # حذف‌شده‌ها: HuggingFace و Cerebras (در پروژه جواب نمی‌دادند؛ دستور کارفرما).
    "groq": {
        "name": "groq",
        "display_name": "Groq",
        "kind": "openai",
        "base_url": "https://api.groq.com/openai/v1",
        "api_root": "https://api.groq.com/openai/v1",
        "timeout": 20,
        "is_iranian": False,
        "supports_vision": True,
        "supports_text": True,
        "supports_proxy": True,
        # رایگان بدون کارت: ۳۰ درخواست/دقیقه و تا ۱۴٬۴۰۰ درخواست/روز (سریع‌ترین)
        "vision_models": [
            {"id": "meta-llama/llama-4-scout-17b-16e-instruct", "is_free": True, "context": 128000, "source": "hardcoded"},
        ],
        "text_models": [
            {"id": "llama-3.3-70b-versatile", "is_free": True, "context": 128000, "source": "hardcoded"},
            {"id": "llama-3.1-8b-instant", "is_free": True, "context": 128000, "source": "hardcoded"},
            {"id": "qwen3-32b", "is_free": True, "context": 128000, "source": "hardcoded"},
            {"id": "openai/gpt-oss-120b", "is_free": True, "context": 128000, "source": "hardcoded"},
            {"id": "deepseek-r1-distill-llama-70b", "is_free": True, "context": 128000, "source": "hardcoded"},
        ],
    },
    "openrouter": {
        "name": "openrouter",
        "display_name": "OpenRouter",
        "kind": "openai",
        "base_url": "https://openrouter.ai/api/v1",
        "api_root": "https://openrouter.ai/api/v1",
        "timeout": 25,
        "is_iranian": False,
        "supports_vision": True,
        "supports_text": True,
        "supports_proxy": True,
        # رایگان بدون کارت: ۲۰ درخواست/دقیقه؛ ۵۰ روزانه (اکانت نو) تا ۱۰۰۰ (با ۱۰$ کردیت)
        # مدل‌های :free مرتب جابه‌جا می‌شوند — لیست زیر وضعیت ۱۸ سپتامبر ۲۰۲۶ است.
        "vision_models": [
            {"id": "google/gemma-4-31b-it:free", "is_free": True, "context": 262000, "source": "hardcoded"},
            {"id": "nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free", "is_free": True, "context": 256000, "source": "hardcoded"},
            {"id": "google/gemma-4-26b-a4b-it:free", "is_free": True, "context": 262000, "source": "hardcoded"},
            {"id": "thinkingmachines/inkling:free", "is_free": True, "context": 1000000, "source": "hardcoded"},
            {"id": "thinkingmachines/inkling-small:free", "is_free": True, "context": 1000000, "source": "hardcoded"},
        ],
        "text_models": [
            {"id": "nvidia/nemotron-3-ultra-550b-a55b:free", "is_free": True, "context": 1000000, "source": "hardcoded"},
            {"id": "minimax/minimax-m3:free", "is_free": True, "context": 1000000, "source": "hardcoded"},
            {"id": "nvidia/nemotron-3.5-lightning:free", "is_free": True, "context": 1000000, "source": "hardcoded"},
        ],
    },
    "mistral": {
        "name": "mistral",
        "display_name": "Mistral AI",
        "kind": "openai",
        "base_url": "https://api.mistral.ai/v1",
        "api_root": "https://api.mistral.ai/v1",
        "timeout": 60,
        "is_iranian": False,
        "supports_vision": True,
        "supports_text": True,
        "supports_proxy": True,
        # پلن رایگان «Experiment»: بدون کارت (تأیید شماره لازم)، ~۱ درخواست/ثانیه
        "vision_models": [
            {"id": "mistral-small-latest", "is_free": True, "context": 256000, "source": "hardcoded"},
            {"id": "pixtral-large-latest", "is_free": True, "context": 128000, "source": "hardcoded"},
        ],
        "text_models": [
            {"id": "mistral-medium-latest", "is_free": True, "context": 256000, "source": "hardcoded"},
            {"id": "mistral-large-latest", "is_free": True, "context": 256000, "source": "hardcoded"},
            {"id": "mistral-nemo", "is_free": True, "context": 128000, "source": "hardcoded"},
            {"id": "codestral-latest", "is_free": True, "context": 256000, "source": "hardcoded"},
        ],
    },
    "sambanova": {
        "name": "sambanova",
        "display_name": "SambaNova",
        "kind": "openai",
        "base_url": "https://api.sambanova.ai/v1",
        "api_root": "https://api.sambanova.ai/v1",
        "timeout": 25,
        "is_iranian": False,
        "supports_vision": False,
        "supports_text": True,
        "supports_proxy": True,
        # رایگان بدون کارت: ۶۰۰ درخواست/دقیقه — فقط متنی (بینایی ندارد)
        "vision_models": [],
        "text_models": [
            {"id": "Meta-Llama-3.3-70B-Instruct", "is_free": True, "context": 128000, "source": "hardcoded"},
            {"id": "Meta-Llama-3.1-8B-Instruct", "is_free": True, "context": 128000, "source": "hardcoded"},
            {"id": "DeepSeek-R1-Distill-Llama-70B", "is_free": True, "context": 128000, "source": "hardcoded"},
            {"id": "DeepSeek-R1", "is_free": True, "context": 128000, "source": "hardcoded"},
        ],
    },
    "cloudflare": {
        "name": "cloudflare",
        "display_name": "Cloudflare Workers AI",
        "kind": "cloudflare",
        "base_url": "https://api.cloudflare.com/client/v4/accounts/{account_id}/ai",
        "api_root": "https://api.cloudflare.com/client/v4/accounts/{account_id}/ai",
        "timeout": 25,
        "is_iranian": False,
        "supports_vision": True,
        "supports_text": True,
        "supports_proxy": True,
        # رایگان بدون کارت: ۱۰٬۰۰۰ نورون در روز؛ نیازمند جایگزینی {account_id} در آدرس
        "vision_models": [
            {"id": "@cf/meta/llama-3.2-11b-vision-instruct", "is_free": True, "context": 128000, "source": "hardcoded"},
            {"id": "@cf/qwen/qwen3.8-27b", "is_free": True, "context": 128000, "source": "hardcoded"},
        ],
        "text_models": [
            {"id": "@cf/meta/llama-3.3-70b-instruct-fp8-fast", "is_free": True, "context": 128000, "source": "hardcoded"},
            {"id": "@cf/mistral/mistral-7b-instruct", "is_free": True, "context": 32000, "source": "hardcoded"},
            {"id": "@cf/qwen/qwen-3-8b", "is_free": True, "context": 32000, "source": "hardcoded"},
        ],
    },
    "gemini": {
        "name": "gemini",
        "display_name": "Google Gemini",
        "kind": "openai",
        "base_url": "https://generativelanguage.googleapis.com/v1beta",
        "api_root": "https://generativelanguage.googleapis.com/v1beta",
        "timeout": 25,
        "is_iranian": False,
        "supports_vision": True,
        "supports_text": True,
        "supports_proxy": True,
        # گوگل آی‌پی ایران را مستقیم بلاک می‌کند؛ گیسو از ورکر کلودفلر کارفرما استفاده می‌کند.
        "vision_models": [
            {"id": "gemini-2.0-flash", "is_free": True, "context": 1000000, "source": "hardcoded"},
            {"id": "gemini-1.5-flash", "is_free": True, "context": 1000000, "source": "hardcoded"},
        ],
        "text_models": [
            {"id": "gemini-2.0-flash", "is_free": True, "context": 1000000, "source": "hardcoded"},
            {"id": "gemini-1.5-flash", "is_free": True, "context": 1000000, "source": "hardcoded"},
        ],
    },
    "gapgpt": {
        "name": "gapgpt",
        "display_name": "GapGPT",
        "kind": "openai",
        "base_url": "https://api.gapgpt.com/v1",
        "api_root": "https://api.gapgpt.com/v1",
        "timeout": 20,
        "is_iranian": True,
        "supports_vision": True,
        "supports_text": True,
        "supports_proxy": False,
        "vision_models": [
            {"id": "gpt-4o-mini", "is_free": False, "context": 128000, "source": "hardcoded"},
            {"id": "gemini-2.5-flash-lite", "is_free": False, "context": 32000, "source": "hardcoded"},
        ],
        "text_models": [
            {"id": "gpt-4o-mini", "is_free": False, "context": 128000, "source": "hardcoded"},
            {"id": "gemini-2.5-flash", "is_free": False, "context": 32000, "source": "hardcoded"},
        ],
    },
    "avalai": {
        "name": "avalai",
        "display_name": "AvalAI",
        "kind": "openai",
        "base_url": "https://api.avalai.ir/v1",
        "api_root": "https://api.avalai.ir/v1",
        "timeout": 20,
        "is_iranian": True,
        "supports_vision": True,
        "supports_text": True,
        "supports_proxy": False,
        "vision_models": [
            {"id": "gpt-4o-mini", "is_free": False, "context": 128000, "source": "hardcoded"},
        ],
        "text_models": [
            {"id": "gpt-4o-mini", "is_free": False, "context": 128000, "source": "hardcoded"},
            {"id": "gemini-2.5-flash", "is_free": False, "context": 32000, "source": "hardcoded"},
        ],
    },
}


# توابع کمکی

def get_provider(name: str):
    """اطلاعات کامل یک پروایدر از رجیستری (با نرمال‌سازی نام‌های نمایشی)."""
    return PROVIDERS.get(normalize_provider_name(name))


def normalize_provider_name(name: str) -> str:
    """نرمال‌سازی نام پروایدر به کلید رجیستری.

    نام‌های نمایشی مثل «hugging face» یا «cloudflare workers ai» (با فاصله)
    به کلید استاندارد (`huggingface`، `cloudflare`) نگاشت می‌شوند تا مدل‌های
    رجیستری برای آن‌ها پیدا شود. اگر معادلی نبود، همان نام تمیز برمی‌گردد.
    """
    cleaned = " ".join(str(name or "").strip().lower().split())
    if cleaned in PROVIDERS:
        return cleaned
    compact = cleaned.replace(" ", "")
    if compact in PROVIDERS:
        return compact
    for key, data in PROVIDERS.items():
        if cleaned == str(data.get("display_name", "")).strip().lower():
            return key
        if compact == str(data.get("display_name", "")).strip().lower().replace(" ", ""):
            return key
    return cleaned


def get_vision_models(name: str, free_only: bool = False) -> list:
    """لیست مدل‌های Vision یک پروایدر"""
    provider = get_provider(name)
    if not provider:
        return []
    models = provider.get("vision_models", [])
    if free_only:
        return [m for m in models if m.get("is_free")]
    return models


def get_text_models(name: str, free_only: bool = False) -> list:
    """لیست مدل‌های Text یک پروایدر"""
    provider = get_provider(name)
    if not provider:
        return []
    models = provider.get("text_models", [])
    if free_only:
        return [m for m in models if m.get("is_free")]
    return models


def get_all_providers() -> list:
    """لیست تمام پروایدرهای رجیستری"""
    return list(PROVIDERS.keys())


def get_free_providers() -> list:
    """فقط پروایدرهایی که حداقل یک مدل رایگان دارند"""
    result = []
    for name, data in PROVIDERS.items():
        has_free = any(m.get("is_free") for m in data.get("vision_models", []) + data.get("text_models", []))
        if has_free:
            result.append(name)
    return result


def get_best_vision_model(name: str):
    """بهترین مدل Vision یک پروایدر (اول رایگان)"""
    free = get_vision_models(name, free_only=True)
    if free:
        return free[0]["id"]
    all_vision = get_vision_models(name, free_only=False)
    return all_vision[0]["id"] if all_vision else None


def get_best_text_model(name: str):
    """بهترین مدل Text یک پروایدر (اول رایگان)"""
    free = get_text_models(name, free_only=True)
    if free:
        return free[0]["id"]
    all_text = get_text_models(name, free_only=False)
    return all_text[0]["id"] if all_text else None


def legacy_registry() -> dict:
    """
    تبدیل رجیستری جدید به فرمت PROVIDERS_REGISTRY قدیمی
    برای سازگاری با کد فعلی در ai_brain.py
    """
    result = {}
    for name, data in PROVIDERS.items():
        result[name] = {
            "kind": data["kind"],
            "base_url": data["base_url"],
            "api_root": data["api_root"],
            "timeout": data["timeout"],
            "is_iranian": data["is_iranian"],
            "use_proxy": False,  # پیش‌فرض
            "vision_preferred": [m["id"] for m in data.get("vision_models", [])],
            "text_preferred": [m["id"] for m in data.get("text_models", [])],
        }
    return result


__all__ = [
    "MODALITY_VISION", "MODALITY_TEXT", "MODALITY_BOTH",
    "SOURCE_HARDCODED", "SOURCE_DISCOVERED", "SOURCE_MANUAL_JSON",
    "PROVIDERS", "get_provider", "get_vision_models", "get_text_models",
    "get_all_providers", "get_free_providers", "get_best_vision_model",
    "get_best_text_model", "legacy_registry",
]
