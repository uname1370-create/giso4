#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""منبع آدرس لینک موقت: تنظیم «🌐 آدرس سایت» اولویت دارد (هر دو سایت)."""
import os, sys
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if BASE_DIR not in sys.path:
    sys.path.append(BASE_DIR)
BOT_EDU = os.path.join(BASE_DIR, 'bot_edu')
if BOT_EDU not in sys.path:
    sys.path.append(BOT_EDU)


def test_maint_base_url_prefers_admin_setting():
    from bot_edu.handlers import _maint_base_url
    from giso_admin import (get_giso_config, set_giso_config,
                            get_giso_site_config, set_giso_site_config)
    # بکاپ مقدارهای واقعی هر دو دیتابیس — تا محیط توسعه خراب نشود
    orig_bot_site = get_giso_config("site_base_url", "")
    orig_bot_main = get_giso_config("main_site_base_url", "")
    orig_giso_site = get_giso_site_config("site_base_url", "")
    orig_giso_main = get_giso_site_config("main_site_base_url", "")
    try:
        # ذخیره از مسیر پنل edu-bot: هر دو دیتابیس باید یکسان شوند
        set_giso_site_config("site_base_url", "https://my-giso.example.com/")
        set_giso_config("site_base_url", "https://my-giso.example.com/")
        assert _maint_base_url("giso") == "https://my-giso.example.com"

        set_giso_config("main_site_base_url", "https://my-main.example.com")
        set_giso_site_config("main_site_base_url", "https://my-main.example.com")
        assert _maint_base_url("main") == "https://my-main.example.com"

        # ذخیره از مسیر پنل/ربات گیسو (فقط giso.db + sync) هم باید در edu دیده شود
        set_giso_site_config("site_base_url", "https://from-giso.example.com")
        assert _maint_base_url("giso") == "https://from-giso.example.com"
    finally:
        # بازگردانی دقیق مقادیر قبلی هر دو دیتابیس
        set_giso_config("site_base_url", orig_bot_site)
        set_giso_config("main_site_base_url", orig_bot_main)
        set_giso_site_config("site_base_url", orig_giso_site)
        set_giso_site_config("main_site_base_url", orig_giso_main)
    assert _maint_base_url("giso").startswith("https://"), "fallback باید https باشد"
    print("PASS  آدرس لینک موقت از تنظیم «🌐 آدرس سایت» می‌آید (هر دو سایت)")


def test_giso_side_write_stays_consistent_with_bot_db():
    """نوشتن سمت گیسو با sync_site_config_to_bot_db باید در bot.db هم دیده شود."""
    from giso_admin import (get_giso_config, set_giso_config,
                            get_giso_site_config, set_giso_site_config)
    from giso.db_core import sync_site_config_to_bot_db
    orig_bot = get_giso_config("site_base_url", "")
    orig_giso = get_giso_site_config("site_base_url", "")
    try:
        set_giso_site_config("site_base_url", "https://sync-test.example.com")
        assert sync_site_config_to_bot_db("site_base_url", "https://sync-test.example.com") is True
        assert get_giso_config("site_base_url", "") == "https://sync-test.example.com"
    finally:
        set_giso_site_config("site_base_url", orig_giso)
        set_giso_config("site_base_url", orig_bot)
    print("PASS  نوشتن سمت گیسو با bot.db همگام می‌شود")
