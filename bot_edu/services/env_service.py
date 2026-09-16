# -*- coding: utf-8 -*-
"""
env_service — دسترسی یکپارچه به env و نقش‌های سیستمی (با تکیه بر env_loader ریشه).
"""
from __future__ import annotations
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from env_loader import (  # noqa: E402  (re-export)
    load_project_env, env_str, env_bool, env_int, env_int_list, env_phone_list,
    project_root,
)

load_project_env()


def admin_ids() -> list:
    """آیدی‌های ادمین ربات (ADMIN_IDS)."""
    return env_int_list("ADMIN_IDS", "1191639507")


def site_admin_phones() -> list:
    """شماره‌های کاننیکال ادمین سایت (SITE_ADMIN_PHONES) — از قبل نرمال‌شده."""
    return env_phone_list("SITE_ADMIN_PHONES")


def bot_token() -> str:
    return env_str("BOT_TOKEN")


def secret_key() -> str:
    return env_str("SECRET_KEY", "sadeghiai-default-secret")
