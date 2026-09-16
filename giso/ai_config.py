# -*- coding: utf-8 -*-
"""تنظیمات مرکزی سیستم AI - همه ثابت‌های قابل تنظیم اینجا (فاز ۳ بازنویسی)."""

# سقف‌های زمانی موتور Vision
VISION_TOTAL_TIMEOUT_SECONDS = 45
VISION_PER_MODEL_TIMEOUT_SECONDS = 8
VISION_MAX_MODELS_PER_PROVIDER = 3

# سقف‌های زمانی موتور Chat
CHAT_TOTAL_TIMEOUT_SECONDS = 30
CHAT_PER_MODEL_TIMEOUT_SECONDS = 6

# سقف‌های زمانی موتور Fast
FAST_TOTAL_TIMEOUT_SECONDS = 15
FAST_PER_MODEL_TIMEOUT_SECONDS = 4

# رفتار 429
BACKOFF_429_FREE_PROVIDER_SECONDS = 0    # پرش فوری
BACKOFF_429_PAID_PROVIDER_SECONDS = 2    # ۲ ثانیه صبر

# سلامت
HEALTH_COOLDOWN_MINUTES = 5

# پرچم امنیت: با True رفتار قدیمی هر سه موتور برمی‌گردد
FEATURE_FLAG_LEGACY_MODE = False
