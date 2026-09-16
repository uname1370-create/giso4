# -*- coding: utf-8 -*-
"""
config.py — تنظیمات وب‌سایت آموزشی sadeghiai

قواعد معماری:
  - وب‌سایت و ربات bot_edu یک سیستم آموزشی یکپارچه هستند.
  - دیتابیس مشترک: bot_edu/data/bot.db
  - جدول‌های web_identity_* در همین دیتابیس ساخته می‌شوند.
  - گیسو کاملاً جداست و هیچ منطق نقشی از آن در وب‌سایت آموزشی استفاده نمی‌شود.
  - تنها منبع env: فایل .env در ریشه پروژه (توسط env_loader لود می‌شود).
"""
import os
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
_BOT = _ROOT / "bot_edu"
_WEB = _ROOT / "web"

# اطمینان از لود شدن env از ریشه پروژه
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))
from env_loader import load_project_env, env_str, env_bool, env_phone_list  # noqa: E402
load_project_env()

# افزودن bot_edu به sys.path تا phoneutil/mentor_service قابل import باشند
if str(_BOT) not in sys.path:
    sys.path.append(str(_BOT))

_DB_BOT = _BOT / "data" / "bot.db"


class Config:
    BASE_DIR = str(_ROOT)
    BOT_EDU_DIR = str(_BOT)
    WEB_DIR = str(_WEB)

    # امنیت: هیچ پیش‌فرض شناخته‌شده‌ای نداریم — کلید حتماً از env (یا .env ریشه) می‌آید.
    # برای توسعهٔ محلی SECRET_KEY را در .env ریشه بگذار؛ در غیر این صورت fail-fast (مثل giso/config.py).
    SECRET_KEY = env_str("SECRET_KEY")
    if not SECRET_KEY:
        raise RuntimeError(
            "SECRET_KEY must be set (env vars or root .env). Generate one with: "
            "python -c \"import secrets; print(secrets.token_urlsafe(48))\""
        )

    # دیتابیس اصلی مشترک با ربات
    SQLALCHEMY_DATABASE_URI = f"sqlite:///{_DB_BOT}"
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    PERMANENT_SESSION_LIFETIME = 7 * 24 * 3600
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"

    FLASK_ENV = env_str("FLASK_ENV", "development")
    DEBUG = env_bool("FLASK_DEBUG", True)

    UPLOAD_FOLDER = str(_WEB / "static" / "images")
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024
    ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "gif"}

    BALE_TOKEN = env_str("BOT_TOKEN") or env_str("BALE_TOKEN")

    # ادمین وب‌سایت آموزشی — فقط بر اساس شماره موبایل نرمال
    # این لیست از env SITE_ADMIN_PHONES (کاما جدا) به canonical +989... تبدیل می‌شود.
    SITE_ADMIN_PHONES = env_phone_list("SITE_ADMIN_PHONES")


# ۴ سوال امنیتی ثابت
SECURITY_QUESTIONS = [
    ("pet",      "نام اولین حیوان خانگی شما چه بود؟"),
    ("teacher",  "نام معلم موردعلاقه شما در دوران مدرسه چه بود؟"),
    ("city",     "در کدام شهر متولد شدید؟"),
    ("friend",   "نام بهترین دوست دوران کودکی شما چه بود؟"),
]
SECURITY_QUESTIONS_MAP = dict(SECURITY_QUESTIONS)
