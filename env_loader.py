# -*- coding: utf-8 -*-
"""
env_loader.py — لودر یکپارچهٔ متغیرهای محیطی برای کل پروژهٔ sadeghiai

تنها منبع متغیرهای محیطی:
  1) متغیرهای محیطی سیستم (os.environ)
  2) فایل .env در ریشهٔ پروژه (این فایل) — اولویت با مقادیر از قبل موجود است

همهٔ بخش‌های پروژه (main.py، bot_edu، web، giso) باید دقیقاً از همین تابع
load_project_env() استفاده کنند تا دیگر ابهامی دربارهٔ محل .env وجود نداشته باشد.

فایل‌های .env در زیرشاخه‌ها (web/.env، giso/.env، bot_edu/.env) به‌عنوان override
برای توسعه‌دهنده support می‌شوند ولی اولویت آخر را دارند؛ بنابراین برای نصب عادی
کافیست فقط یک فایل .env در ریشه ساخته شود.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent
_ENV_LOADED = False


def project_root() -> Path:
    return _PROJECT_ROOT


def load_project_env() -> Path:
    """لود فایل(های) .env به ترتیب اولویت. بارها صدا زده شود امن است (فقط بار اول اثر دارد)."""
    global _ENV_LOADED
    try:
        from dotenv import load_dotenv
    except ImportError:
        # اگر python-dotenv نصب نباشد، فقط متغیرهای سیستم استفاده می‌شوند
        _ENV_LOADED = True
        return _PROJECT_ROOT

    # 1) فایل اصلی ریشه (کمترین اولویت — override=False)
    root_env = _PROJECT_ROOT / ".env"
    if root_env.exists():
        load_dotenv(root_env, override=False)

    # 2) برای راحتی توسعهٔ لوکال، فایل‌های .env زیرشاخه‌ها را هم می‌خوانیم
    #    (ولی مقادیر ریشه را override نمی‌کنند)
    for sub in ("bot_edu", "web", "giso"):
        sub_env = _PROJECT_ROOT / sub / ".env"
        if sub_env.exists():
            load_dotenv(sub_env, override=False)

    _ENV_LOADED = True
    return root_env


def ensure_env_loaded():
    if not _ENV_LOADED:
        load_project_env()


def env_str(name: str, default: str = "") -> str:
    ensure_env_loaded()
    return (os.environ.get(name) or default).strip()


def env_int(name: str, default: int = 0) -> int:
    try:
        return int(env_str(name, str(default)))
    except (TypeError, ValueError):
        return default


def env_bool(name: str, default: bool = False) -> bool:
    v = env_str(name, "1" if default else "0").lower()
    return v in ("1", "true", "yes", "on", "y")


def env_int_list(name: str, default: str = "") -> list:
    raw = env_str(name, default)
    out = []
    for part in raw.replace("،", ",").split(","):
        part = part.strip()
        if not part:
            continue
        try:
            out.append(int(part))
        except ValueError:
            continue
    return out


def env_phone_list(name: str, default: str = "") -> list:
    """خواندن لیست شماره تلفن از env و نرمال‌سازی به canonical +989xxxxxxxxx."""
    ensure_env_loaded()
    raw = env_str(name, default)
    out = []
    try:
        sys.path.insert(0, str(_PROJECT_ROOT / "bot_edu"))
        from phoneutil import normalize_phone
    except Exception:
        def normalize_phone(x: str) -> str:
            if not x:
                return ""
            _digits = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")
            s = str(x).strip().translate(_digits)
            s = "".join(ch for ch in s if ch.isdigit() or ch == "+")
            if s.startswith("0098"):
                s = "+98" + s[4:]
            elif s.startswith("989"):
                s = "+98" + s[2:]
            elif s.startswith("09"):
                s = "+98" + s[1:]
            elif s.startswith("9"):
                s = "+98" + s
            return s if s.startswith("+989") and len(s) == 13 else ""
    for part in raw.replace("،", ",").split(","):
        p = part.strip()
        if not p:
            continue
        n = normalize_phone(p)
        if n and n not in out:
            out.append(n)
    return out


if __name__ == "__main__":
    load_project_env()
    print(f"Project root: {_PROJECT_ROOT}")
    print(f"BOT_TOKEN set: {bool(env_str('BOT_TOKEN'))}")
    print(f"ADMIN_IDS: {env_int_list('ADMIN_IDS')}")
    print(f"SITE_ADMIN_PHONES: {env_phone_list('SITE_ADMIN_PHONES')}")
