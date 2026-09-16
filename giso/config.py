# -*- coding: utf-8 -*-
"""
تنظیمات پروژه گیسو — از .env ریشه پروژه لود می‌شود (env_loader)
"""
import os
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
_BOT = _ROOT / 'bot_edu'
_GISO = _ROOT / 'giso'

# لود env از ریشه پروژه
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))
from env_loader import load_project_env  # noqa: E402
load_project_env()

_DB_BOT = _BOT / 'data' / 'bot.db'
_DB_GISO = _GISO / 'data' / 'giso.db'


def _sa_uri(kind: str, sqlite_path) -> str:
    """URI دوانجینهٔ SQLAlchemy: پیش‌فرض sqlite؛ با GISO_DB_ENGINE=postgres روی PG.

    توجه: DSN باید URL باشد (postgresql://user:pass@host:5432/db). اگر فرمت
    keyword باشد (host=...) با خطای صریح متوقف می‌شویم — بازگشت بی‌صدا به
    sqlite یعنی نوشتن روی دیتابیس اشتباه در پروداکشن!
    """
    try:
        from giso import db_engine
        if db_engine.is_pg(kind):
            dsn = db_engine.dsn_for(kind)
            if not dsn.startswith("postgresql://"):
                raise ValueError(
                    "DSN باید با postgresql:// شروع شود (URL کامل)، مقدار فعلی "
                    "برای SQLAlchemy قابل تجزیه نیست.")
            return dsn.replace("postgresql://", "postgresql+psycopg2://", 1)
    except ImportError:
        pass
    return f'sqlite:///{sqlite_path}'


class Config:
    BASE_DIR = str(_ROOT)
    BOT_EDU_DIR = str(_BOT)
    GISO_DIR = str(_GISO)

    DEBUG = False
    # آدرس پایهٔ سفارشی Gemini (مثلاً Cloudflare Worker) — از env یا /etc/giso/web.env
    # نمونه: GEMINI_BASE_URL=https://sadeghiai.uname1370.workers.dev
    # اگر خالی باشد، آدرس پیش‌فرض generativelanguage.googleapis.com استفاده می‌شود.
    GEMINI_BASE_URL = (os.environ.get("GEMINI_BASE_URL", "") or "").strip().rstrip("/")
    # توکن پرداخت کیف‌پولی بازوی بله (از @botfather) — هرگز لاگ نشود.
    # مقدار پیش‌فرض، توکن آزمایشی رسمی بله است (پرداخت واقعی انجام نمی‌دهد).
    BALE_PROVIDER_TOKEN = (os.environ.get("BALE_PROVIDER_TOKEN", "") or "").strip() or "WALLET-TEST-1111111111111111"
    SECRET_KEY = os.environ.get("SECRET_KEY")
    if not SECRET_KEY and not DEBUG:
        raise RuntimeError("SECRET_KEY must be set in production")
        # Phase 12 Security — Session cookie hardening
        SESSION_COOKIE_SECURE = True
        SESSION_COOKIE_HTTPONLY = True
        SESSION_COOKIE_SAMESITE = "Lax"
        PERMANENT_SESSION_LIFETIME = 1800

    SQLALCHEMY_DATABASE_URI = _sa_uri("giso", _DB_GISO)
    SQLALCHEMY_BINDS = {'bot': _sa_uri("bot", _DB_BOT)}
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    PERMANENT_SESSION_LIFETIME = 3600
    SESSION_COOKIE_HTTPONLY = True
    # فاز 6: SameSite=Lax — کاهش ریسک CSRF بین‌سایتی (همراه با session-based auth)
    SESSION_COOKIE_SAMESITE = 'Lax'
    # در production فقط با HTTPS فعال شود؛ در توسعه localhost بدون Secure باقی می‌ماند.
    SESSION_COOKIE_SECURE = (
        os.environ.get('SESSION_COOKIE_SECURE', '').lower() == 'true'
        or os.environ.get('FLASK_ENV', '').lower() == 'production'
    )

    FLASK_ENV = os.environ.get('FLASK_ENV', 'development')

    UPLOAD_FOLDER = str(_GISO / 'static' / 'uploads')
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg'}

    AI_API_KEY = os.environ.get('AI_API_KEY', '')
    AI_PROVIDER = os.environ.get('AI_PROVIDER', 'groq')
    ANALYSIS_COOLDOWN_MINUTES = 60

import re

SUPERADMIN_PHONE_DIGITS = "9156012931"
SUPERADMIN_BALE_ID = 1191639507


def is_super_admin(uid=None, phone: str = "") -> bool:
    """
    بررسی متمرکز و انعطاف‌پذیر سوپرادمین اصلی گیسو
    - شناسه بله/تلگرام: 1191639507 (int یا str)
    - شماره همراه: 09156012931 / +989156012931 / 989156012931 / هر فرمتی که به 9156012931 ختم شود
    """
    if uid is not None and uid != "":
        try:
            if int(uid) == SUPERADMIN_BALE_ID:
                return True
        except (ValueError, TypeError):
            if str(uid).strip() == str(SUPERADMIN_BALE_ID):
                return True

    if phone:
        digits = re.sub(r'[^\d]', '', str(phone))
        if digits.endswith(SUPERADMIN_PHONE_DIGITS) and len(digits) in (10, 11, 12, 13, 14):
            return True
        try:
            from phoneutil import normalize_phone
            norm = normalize_phone(phone)
            if norm and norm.endswith(SUPERADMIN_PHONE_DIGITS):
                return True
        except Exception:
            pass

    return False


# ── ادمین اختصاصی (خانم مهندس صادقی) ──────────────────────────────────────────
# نقش سومِ سبک: نه super (به تنظیمات/بکاپ/مدیریت ادمین/AI دسترسی ندارد) و نه ادمین
# عادیِ محض (چند دسترسی عملیاتی اضافه می‌گیرد). تشخیص کاملاً در کدِ گیسو است تا هیچ
# رکوردی در bot.db (پوشه‌ی قفل‌شده‌ی bot_edu) نوشته نشود؛ مستقل از is_super_admin.
SPECIAL_ADMIN_PHONE_DIGITS = "9353258836"
SPECIAL_ADMIN_PROFILE = {
    "phone": "09353258836",
    "first_name": "خانم",
    "last_name": "مهندس صادقی",
    "full_name": "خانم مهندس صادقی",
    "city": "مشهد",
    "role": "special_admin",
}


def is_special_admin(uid=None, phone: str = "") -> bool:
    """
    تشخیص ادمین اختصاصی گیسو (۰۹۳۵۳۲۵۸۸۳۶) — نقش «special_admin».
    عمداً جدا از is_super_admin نگه داشته شده تا با سوپرادمین تداخل نکند.
    """
    if phone:
        digits = re.sub(r'[^\d]', '', str(phone))
        if digits.endswith(SPECIAL_ADMIN_PHONE_DIGITS) and len(digits) in (10, 11, 12, 13, 14):
            return True
        try:
            from phoneutil import normalize_phone
            norm = normalize_phone(phone)
            if norm and norm.endswith(SPECIAL_ADMIN_PHONE_DIGITS):
                return True
        except Exception:
            pass
    return False
