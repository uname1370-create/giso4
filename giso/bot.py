# -*- coding: utf-8 -*-
"""
giso/bot.py — نقطه ورود اصلی ربات بله گیسو (Main Runner، کیبوردها و مسیریاب رویدادها).
"""
import asyncio
import atexit
import json
import logging
import os
import re

import sys
import time
from pathlib import Path

logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger("giso_bot")
_READ_REPORT_CACHE = {}

# جلوگیری از لو رفتن توکن ربات در لاگ‌های httpx (سطح INFO → WARNING)
logging.getLogger("httpx").setLevel(logging.WARNING)

def _to_thread(fn, *args, **kwargs):
    """اجرای فراخوانی blocking خارج از event loop (در صورت اجرا داخل loop)."""
    import functools
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        return fn(*args, **kwargs)
    return loop.run_in_executor(None, functools.partial(fn, *args, **kwargs))

BALE_BASE_URL = "https://tapi.bale.ai/bot"
BALE_FILE_URL = "https://tapi.bale.ai/file/bot"
RETRY_DELAY_SECS = 5
TIMEOUT = 20.0

BASE_DIR = Path(__file__).resolve().parent
PID_FILE = BASE_DIR / "data" / "giso-bot.pid"
BOT_DB = BASE_DIR.parent / "bot_edu" / "data" / "bot.db"

def _on_shutdown_checkpoint():
    """هنگام بسته شدن ربات، checkpoint بزن (انتقال WAL به DB)."""
    try:
        from giso.base import checkpoint_giso_db
        logger.info("ربات در حال بسته شدن... checkpoint...")
        checkpoint_giso_db()
        logger.info("checkpoint انجام شد. ربات بسته شد.")
    except Exception as e:
        logger.debug(f"_on_shutdown_checkpoint: {e}")

# ثبت shutdown handler هنگام خروج از process
atexit.register(_on_shutdown_checkpoint)

# مسیر flag file برای اطلاع به main.py که ریستارت درخواست شده است
_GISO_RESTART_FLAG = Path(__file__).parent / "data" / "giso-restart.flag"

def _restart_giso_process():
    """
    ریستارت ربات گیسو با واگذاری به main.py watcher.

    برخلاف روش قبلی (os.execv که در ویندوز دو instance می‌ساخت):
      ۱) checkpoint نهایی
      ۲) flag ریستارت را set می‌کند
      ۳) خودش را کاملاً می‌کشد
      ۴) main.py watcher می‌بیند process مرده، flag را چک می‌کند،
         و یک instance جدید (به‌عنوان فرزند خودش) spawn می‌کند
      ۵) نتیجه: همیشه یک instance زنده
    """
    import time

    # ۱) checkpoint نهایی
    try:
        from giso.base import checkpoint_giso_db
        checkpoint_giso_db()
    except Exception as e:
        logger.warning(f"checkpoint قبل از ریستارت ناموفق: {e}")

    # ۲) set کردن flag ریستارت
    try:
        _GISO_RESTART_FLAG.parent.mkdir(parents=True, exist_ok=True)
        _GISO_RESTART_FLAG.write_text(str(int(time.time())))
        logger.info("✅ flag ریستارت set شد — main.py دوباره spawn می‌کند")
    except Exception as e:
        logger.error(f"set کردن flag ریستارت ناموفق: {e}")

    # ۳) خروج قطعی (بدون ساخت process جدید / بدون orphan)
    logger.info("⏻ ربات گیسو در حال خاموش شدن برای ریستارت...")
    os._exit(0)

sys.path.append(str(BASE_DIR.parent / "bot_edu"))

from giso.base import (
    get_giso_db_conn,
    normalize_phone,
    display_phone,
    to_shamsi,
    _fa_num,
    _token_from_env,
    _token_from_db,
    _is_super_admin,
    _giso_lookup,
    _giso_init_db,
    _get_giso_user,
    _upsert_giso_user,
    _demote_giso_user_admin,
    notify_user_bot_by_order,
)
from giso.money import format_toman
from giso.hair_sale import (
    handle_hair_sale_commands,
    handle_hair_sale_state,
)
from giso.ai_brain import (
    get_ai_provider,
    list_ai_providers,
    add_ai_provider,
    delete_ai_provider,
    toggle_ai_provider,
    toggle_use_proxy,
    update_ai_provider_field,
    check_ai_provider,
    check_all_ai_providers,
    PROVIDERS_REGISTRY,
)
from giso.ai_runtime import (
    ROLE_LABELS,
    SECTION_LABELS,
    OFF_MESSAGE,
    NO_ACCESS_MESSAGE,
    init_ai_runtime_tables,
    get_display_name,
    set_display_name,
    is_chat_enabled,
    set_chat_enabled,
    is_widget_enabled,
    set_widget_enabled,
    set_widget_position,
    set_widget_welcome_message,
    set_widget_primary_color,
    get_widget_usage_stats,
    get_widget_config,
    get_failover_chain,
    set_failover_chain,
    build_provider_status_report,
    get_recent_pending_actions,
    get_recent_action_logs,
    get_recent_rollback_logs,
    touch_user_activity,
    mark_welcome_shown,
    should_show_welcome,
    get_smart_welcome_context,
    get_active_provider,
    set_active_provider,
    list_provider_options,
    get_role_capabilities,
    set_role_capabilities,
    get_role_policy,
    set_role_policy,
    check_role_access,
    resolve_actor_role,
    get_runtime_overview,
    build_status_report,
    admin_test_prompt,
    process_superadmin_request,
    execute_pending_action,
    cancel_pending_action,
    rollback_action_log,
    get_superadmin_action_capabilities_text,
)
CONSULTANT_AI_LABEL = "💬 مشاور هوشمند گیسو"
PROVIDERS_AI_LABEL = "🧩 مدیریت Providerها و پروکسی"
BEHAVIOR_AI_LABEL = "🧠 مدیریت رفتار هوش مصنوعی"

from giso.gemini_proxy_manager import (
    set_mode,
    mode_label,
    set_source_url,
    reset_source_url,
    set_manual_proxies,
    clear_manual_proxies,
    refresh_from_source,
    revalidate,
    format_test_report,
    status_summary,
)
# فاز B فروشگاه: منوی ربات فروشگاه (سبک — فقط دو هوک)
from giso.shop.bot.handlers import handle_shop_bot_text, handle_shop_bot_callback, handle_shop_bot_photo

# منوی عملیاتی ثابت فروش مو برای ادمین‌های تأییدشده
from giso.bot_hair_admin import (
    build_admin_hair_menu,
    admin_hair_menu_text,
    render_request_list,
    render_user_orders,
    show_requests_paged,
    show_users_paged,
    show_user_orders_paged,
    show_report_phones,
    show_report_user_view,
    show_conversations,
)
from giso.bot_market_admin import (
    market_menu_kb,
    market_menu_text,
    show_market_paged,
    handle_market_callback,
    show_pending_buyers,
    show_market_status,
    show_credit_tariffs,
)
from giso.bot_chats_admin import (
    chats_menu_kb,
    chats_menu_text,
    show_kind_paged,
    handle_gchat_callback,
    save_reply as gchat_save_reply,
    _kind_from_text as gchat_kind_from_text,
)
# ⚡ عملیات سریع کاربر در ربات (۲۴ نمای درون‌باتی، فقط‌خواندنی/آینه‌ای — ماژول مستقل)
from giso import bot_user_actions as _uact
from giso.beauty_centers.reservations.bot_handlers import handle_reservation_bot

def _build_app(token):
    from telegram.ext import ApplicationBuilder
    return (
        ApplicationBuilder()
        .token(token)
        .base_url(BALE_BASE_URL)
        .base_file_url(BALE_FILE_URL)
        .connect_timeout(TIMEOUT)
        .read_timeout(TIMEOUT)
        .write_timeout(TIMEOUT)
        .get_updates_connect_timeout(TIMEOUT)
        .get_updates_read_timeout(TIMEOUT)
        .build()
    )

def _write_pid(pid: int):
    try:
        PID_FILE.parent.mkdir(parents=True, exist_ok=True)
        PID_FILE.write_text(str(pid), encoding="utf-8")
    except Exception as e:
        logger.debug("PID file write failed: %s", e)

def _clear_pid():
    try:
        if PID_FILE.exists():
            PID_FILE.unlink()
    except Exception:
        pass

try:
    from telegram import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardButton, InlineKeyboardMarkup
except ImportError:
    class ReplyKeyboardMarkup:
        def __init__(self, kb, **kw):
            self.keyboard = kb
    class InlineKeyboardMarkup:
        def __init__(self, kb, **kw):
            self.inline_keyboard = kb
    class InlineKeyboardButton:
        def __init__(self, text, callback_data=None, **kw):
            self.text = text
            self.callback_data = callback_data
    class KeyboardButton:
        def __init__(self, text, **kw):
            self.text = text

def _admin_kb(user_id=None):
    """Admin keyboard with a fixed operational role and no per-admin switches."""
    from telegram import KeyboardButton, ReplyKeyboardMarkup

    if not user_id or _is_super_admin(user_id):
        keyboard = [
            [KeyboardButton("📊 پیشخوان"), KeyboardButton("🛍 فروشگاه")],
            [KeyboardButton("💇 خرید مو"), KeyboardButton("🔬 آنالیز")],
            [KeyboardButton("🏪 بازارچه"), KeyboardButton("🏥 مراکز زیبایی")],
            [KeyboardButton("💬 مدیریت گفتگوها")],
            [KeyboardButton("🛠 مدیریت")],
            [KeyboardButton("⚙️ تنظیمات سایت")],
        ]
        return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

    keyboard = [
        [KeyboardButton("💇 خرید مو"), KeyboardButton("🛍 فروشگاه")],
        [KeyboardButton("🏪 بازارچه")],
        [KeyboardButton("💬 مدیریت گفتگوها")],
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

# ═══ زیرمنوهای گروهی سوپرادمین (فاز P0 بازطراحی منوی ربات) ═══
def _admin_analysis_group_kb():
    """🔬 آنالیز → درخواست‌ها / مدیریت / محصولات درخواستی."""
    return ReplyKeyboardMarkup(
        [
            ["📬 درخواست‌های آنالیز", "🔬 مدیریت آنالیز"],
            ["🛒 محصولات درخواستی"],
            ["🔙 بازگشت"],
        ],
        resize_keyboard=True,
    )

def _admin_watch_kb():
    """👁 نظارت → آمار زنده سه بخش (فقط خواندنی)."""
    return ReplyKeyboardMarkup(
        [
            ["💇 نظارت خرید مو"],
            ["🔬 نظارت آنالیز"],
            ["🛍 نظارت فروشگاه"],
            ["🔙 بازگشت"],
        ],
        resize_keyboard=True,
    )

def _admin_management_group_kb():
    """🛠 مدیریت → همه مدیریت‌های واقعی سیستم (همه با هندلر موجود)."""
    return ReplyKeyboardMarkup(
        [
            ["👥 مدیریت کاربران سایت", "👑 مدیریت ادمین‌ها"],
            ["⭐ نظرات", "📢 مدیریت کانال"],
            ["🌐 مدیریت سایت", "💬 مدیریت ویجت"],
            ["🚨 وضعیت فوری"],
            [PROVIDERS_AI_LABEL],
            [BEHAVIOR_AI_LABEL],
            ["🔙 بازگشت"],
        ],
        resize_keyboard=True,
    )

def _admin_site_ops_kb():
    """🌐 مدیریت سایت → عملیات سرویس (بکاپ/ریستارت)."""
    return ReplyKeyboardMarkup(
        [
            ["💾 پشتیبان‌گیری", "🔄 ریستارت ربات"],
            ["🔙 بازگشت"],
        ],
        resize_keyboard=True,
    )

def _admin_site_settings_kb():
    """⚙️ تنظیمات سایت → تنظیمات سطح سایت/ربات (محدودیت زمان، تم، آدرس)."""
    return ReplyKeyboardMarkup(
        [
            ["⏱ محدودیت زمان تحلیل"],
            ["🎨 انتخاب تم سایت", "🌐 تنظیم آدرس سایت گیسو"],
            ["🔙 بازگشت"],
        ],
        resize_keyboard=True,
    )

def _admin_ai_kb():
    return ReplyKeyboardMarkup(
        [
            ["📋 فهرست پروایدرها"],
            ["➕ افزودن پروایدر", "✏️ ویرایش پروایدر"],
            ["⏸ فعال/غیرفعال", "🗑 حذف پروایدر"],
            ["🔁 بررسی یک پروایدر", "🔄 بررسی همه"],
            ["🔄 بروزرسانی هوشمند مدل‌ها"],
            ["📊 گزارش وضعیت", "💬 تست گفتگو"],
            ["🌐 مدیریت پروکسی Gemini"],
            ["🔙 بازگشت"],
        ],
        resize_keyboard=True,
    )

def _admin_proxy_kb():
    return ReplyKeyboardMarkup(
        [
            ["📊 وضعیت پروکسی"],
            ["🔄 تغییر حالت اتصال"],
            ["📥 دریافت پروکسی از منبع"],
            ["🧪 تست پروکسی‌های سالم"],
            ["➕ افزودن پروکسی دستی", "🗑 پاک کردن دستی‌ها"],
            ["🔗 تنظیم URL منبع"],
            ["🔙 بازگشت"],
        ],
        resize_keyboard=True,
    )

def _admin_mgmt_kb():
    return ReplyKeyboardMarkup(
        [
            ["🔑 تنظیم کلمه ادمینی", "📥 بررسی درخواست‌ها"],
            ["📋 لیست ادمین‌ها"],
            ["🗑 حذف ادمین", "🗑 حذف همه درخواست‌ها"],
            ["🔙 بازگشت"],
        ],
        resize_keyboard=True,
    )

def _admin_users_kb():
    return ReplyKeyboardMarkup(
        [
            ["📊 گزارش کلی کاربران"],
            ["🗑 حذف کاربران"],
            ["🔙 بازگشت"],
        ],
        resize_keyboard=True,
    )

def _admin_users_del_kb():
    return ReplyKeyboardMarkup(
        [
            ["🔎 جستجوی کاربر"],
            ["🗑 حذف همه (بجز ادمین‌ها)"],
            ["📋 حذف از لیست"],
            ["📱 حذف با شماره"],
            ["🔙 بازگشت"],
        ],
        resize_keyboard=True,
    )

def _admin_settings_kb():
    return ReplyKeyboardMarkup(
        [
            ["🎨 انتخاب تم سایت", "⏱ محدودیت زمان تحلیل"],
            ["🌐 تنظیم آدرس سایت گیسو", BEHAVIOR_AI_LABEL],
            ["💾 پشتیبان‌گیری", "🔄 ریستارت ربات"],
            ["🔙 بازگشت"],
        ],
        resize_keyboard=True,
    )

def _managed_ai_main_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📊 وضعیت و سلامت", callback_data="mair_menu_status")],
        [InlineKeyboardButton("🎯 انتخاب و پایداری AI", callback_data="mair_menu_selection")],
        [InlineKeyboardButton("🔐 دسترسی و محدودیت", callback_data="mair_menu_permissions")],
        [InlineKeyboardButton("🎭 رفتار و هویت", callback_data="mair_menu_behavior")],
        [InlineKeyboardButton("⚙️ عملیات و تاریخچه", callback_data="mair_menu_ops")],
        [InlineKeyboardButton("🌐 تنظیمات Widget سایت", callback_data="mair_menu_widget")],
        [InlineKeyboardButton("🔙 بازگشت", callback_data="mair_back_settings")],
    ])

def _managed_ai_status_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📊 گزارش کامل وضعیت", callback_data="mair_menu_report")],
        [InlineKeyboardButton("🧪 تست AI فعال", callback_data="mair_active_test")],
        [InlineKeyboardButton("🧩 وضعیت Providerها", callback_data="mair_provider_status")],
        [InlineKeyboardButton("🔙 بازگشت", callback_data="mair_main")],
    ])

def _managed_ai_selection_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🎯 انتخاب AI فعال", callback_data="mair_menu_providers")],
        [InlineKeyboardButton("🔁 Failover و ترتیب پشتیبان", callback_data="mair_menu_failover")],
        [InlineKeyboardButton("🔙 بازگشت", callback_data="mair_main")],
    ])

def _managed_ai_behavior_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("✏️ اسم نمایشی", callback_data="mair_menu_display")],
        [InlineKeyboardButton("📋 قابلیت‌های نقش‌ها", callback_data="mair_menu_capabilities")],
        [InlineKeyboardButton("👁 پیش‌نمایش رفتار", callback_data="mair_behavior_preview")],
        [InlineKeyboardButton("🔙 بازگشت", callback_data="mair_main")],
    ])

def _managed_ai_ops_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("⏳ اقدامات در انتظار", callback_data="mair_pending_list")],
        [InlineKeyboardButton("🧾 لاگ اقدامات", callback_data="mair_logs_list")],
        [InlineKeyboardButton("↩️ بازگردانی‌های اخیر", callback_data="mair_rollbacks_list")],
        [InlineKeyboardButton("🔙 بازگشت", callback_data="mair_main")],
    ])

def _managed_ai_widget_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔛 فعال/غیرفعال Widget", callback_data="mair_widget_toggle")],
        [InlineKeyboardButton("🎨 موقعیت نمایش", callback_data="mair_widget_position")],
        [InlineKeyboardButton("💬 متن خوش‌آمد", callback_data="mair_widget_welcome")],
        [InlineKeyboardButton("🎨 رنگ اصلی Widget", callback_data="mair_widget_color")],
        [InlineKeyboardButton("📊 آمار استفاده Widget", callback_data="mair_widget_stats")],
        [InlineKeyboardButton("🔙 بازگشت", callback_data="mair_main")],
    ])

def _managed_ai_widget_position_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("راست پایین", callback_data="mair_widget_pos|right-bottom"), InlineKeyboardButton("چپ پایین", callback_data="mair_widget_pos|left-bottom")],
        [InlineKeyboardButton("راست بالا", callback_data="mair_widget_pos|right-top"), InlineKeyboardButton("چپ بالا", callback_data="mair_widget_pos|left-top")],
        [InlineKeyboardButton("🔙 بازگشت", callback_data="mair_menu_widget")],
    ])

def _managed_ai_permission_roles_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("👥 کاربران عادی", callback_data="mair_perm_role|user")],
        [InlineKeyboardButton("👮 ادمین‌های محدود", callback_data="mair_perm_role|admin")],
        [InlineKeyboardButton("👑 سوپرادمین", callback_data="mair_perm_role|super")],
        [InlineKeyboardButton("🔙 بازگشت", callback_data="mair_main")],
    ])

def _managed_ai_capabilities_roles_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("✏️ قابلیت‌های کاربر عادی", callback_data="mair_caps_role|user")],
        [InlineKeyboardButton("✏️ قابلیت‌های ادمین محدود", callback_data="mair_caps_role|admin")],
        [InlineKeyboardButton("✏️ قابلیت‌های سوپرادمین", callback_data="mair_caps_role|super")],
        [InlineKeyboardButton("🔙 بازگشت", callback_data="mair_menu_behavior")],
    ])

def _managed_ai_provider_list_kb():
    rows = []
    grouped = list_provider_options()
    for key in ("iranian", "foreign"):
        items = grouped.get(key) or []
        for item in items:
            status_icon = "✅" if item.get("enabled") else "❌"
            active_icon = "🟢" if item.get("is_active") else "⚪️"
            model = item.get("selected_model") or "—"
            label = f"{active_icon} {status_icon} {item['name']} ({model[:22]})"
            rows.append([InlineKeyboardButton(label, callback_data=f"mair_pick_provider|{item['name']}")])
    rows.append([InlineKeyboardButton("🔙 بازگشت", callback_data="mair_main")])
    return InlineKeyboardMarkup(rows)

def _managed_ai_permission_detail_kb(role):
    policy = get_role_policy(role)
    if role == "super":
        return InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 بازگشت", callback_data="mair_menu_permissions")],
        ])
    access_level = int(policy.get("access_level", 0) or 0)
    sections = set(policy.get("sections") or [])
    daily_limit = int(policy.get("daily_limit", 0) or 0)
    rows = [
        [
            InlineKeyboardButton(("✅ " if access_level == 0 else "⚪️ ") + "سطح ۰", callback_data=f"mair_perm_level|{role}|0"),
            InlineKeyboardButton(("✅ " if access_level == 1 else "⚪️ ") + "سطح ۱", callback_data=f"mair_perm_level|{role}|1"),
        ],
        [
            InlineKeyboardButton(("✅ " if access_level == 2 else "⚪️ ") + "سطح ۲", callback_data=f"mair_perm_level|{role}|2"),
            InlineKeyboardButton(("✅ " if access_level == 3 else "⚪️ ") + "سطح ۳", callback_data=f"mair_perm_level|{role}|3"),
        ],
    ]
    for sec in _VISIBLE_ROLE_SECTIONS.get(role, []):
        checked = "☑" if sec in sections else "☐"
        rows.append([InlineKeyboardButton(f"{checked} {SECTION_LABELS.get(sec, sec)}", callback_data=f"mair_perm_sec|{role}|{sec}")])
    rows.append([
        InlineKeyboardButton(("✅ " if daily_limit == 5 else "⚪️ ") + "۵", callback_data=f"mair_perm_limit|{role}|5"),
        InlineKeyboardButton(("✅ " if daily_limit == 10 else "⚪️ ") + "۱۰", callback_data=f"mair_perm_limit|{role}|10"),
        InlineKeyboardButton(("✅ " if daily_limit == 25 else "⚪️ ") + "۲۵", callback_data=f"mair_perm_limit|{role}|25"),
    ])
    rows.append([
        InlineKeyboardButton(("✅ " if daily_limit == 50 else "⚪️ ") + "۵۰", callback_data=f"mair_perm_limit|{role}|50"),
        InlineKeyboardButton(("✅ " if daily_limit == 0 else "⚪️ ") + "نامحدود", callback_data=f"mair_perm_limit|{role}|0"),
    ])
    rows.append([
        InlineKeyboardButton("💾 ذخیره تنظیمات", callback_data=f"mair_perm_save|{role}"),
        InlineKeyboardButton("🔙 بازگشت", callback_data="mair_menu_permissions"),
    ])
    return InlineKeyboardMarkup(rows)

def _managed_ai_display_name_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("✏️ تغییر اسم", callback_data="mair_change_display")],
        [InlineKeyboardButton("🔙 بازگشت", callback_data="mair_main")],
    ])

def _managed_ai_toggle_kb():
    enabled = is_chat_enabled()
    rows = []
    if enabled:
        rows.append([InlineKeyboardButton("🔴 غیرفعال کن", callback_data="mair_toggle_confirm_off")])
    else:
        rows.append([InlineKeyboardButton("🟢 فعال کن", callback_data="mair_toggle_apply|1")])
    rows.append([InlineKeyboardButton("🔙 بازگشت", callback_data="mair_main")])
    return InlineKeyboardMarkup(rows)

def _ratelimit_inline_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔛 فعال/غیرفعال کردن", callback_data="rl_toggle")],
        [InlineKeyboardButton("⏰ تغییر مدت زمان", callback_data="rl_minutes")],
        [InlineKeyboardButton("🎯 تغییر نوع محدودیت", callback_data="rl_type")],
        [InlineKeyboardButton("🔙 بازگشت", callback_data="rl_back")],
    ])

def _admin_theme_kb():
    """فقط دو تم پشتیبانی‌شده؛ دکمه‌های قدیمی در handler سازگاری می‌مانند."""
    return ReplyKeyboardMarkup(
        [
            ["✦ تم دستیار هوشمند", "🎯 تم مسیر هوشمند گیسو"],
            ["🔙 بازگشت"],
        ],
        resize_keyboard=True,
    )

_LEGACY_AI_MENU_TEXTS = {
    PROVIDERS_AI_LABEL,
    "🤖 مدیریت AI",
    "🤖 تنظیم AI",
    "📋 فهرست پروایدرها",
    "➕ افزودن پروایدر",
    "✏️ ویرایش پروایدر",
    "⏸ فعال/غیرفعال",
    "🗑 حذف پروایدر",
    "🔁 بررسی یک پروایدر",
    "🔄 بررسی همه",
    "🔄 بروزرسانی هوشمند مدل‌ها",
    "📊 گزارش وضعیت",
    "💬 تست گفتگو",
    "🌐 مدیریت پروکسی Gemini",
    "📊 وضعیت پروکسی",
    "🔄 تغییر حالت اتصال",
    "📥 دریافت پروکسی از منبع",
    "🧪 تست پروکسی‌های سالم",
    "➕ افزودن پروکسی دستی",
    "🗑 پاک کردن دستی‌ها",
    "🔗 تنظیم URL منبع",
}

_LEGACY_AI_STATES = {
    "wait_ai_add_name",
    "wait_ai_add_key",
    "wait_ai_add_base_url",
    "wait_ai_edit_val",
    "wait_ai_del_select",
    "wait_ai_del_confirm",
    "wait_ai_check_select",
    "wait_ai_try_prompt",
    "wait_proxy_manual_add",
    "wait_proxy_source_url",
}

_SUPER_ONLY_AI_STATES = {
    "wait_ai_display_name",
    "wait_ai_capabilities_user",
    "wait_ai_capabilities_admin",
    "wait_ai_capabilities_super",
    "wait_widget_welcome",
    "wait_widget_color",
}

def _consultant_ai_inline_kb(role: str):
    if not _role_has_consultant_ai(role):
        return None
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(CONSULTANT_AI_LABEL, callback_data="consultant_ai_start")]
    ])

def _consultant_ai_end_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("❌ پایان گفتگو", callback_data="consultant_ai_end")]
    ])

def _super_action_confirm_kb(pending_id: int):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ تأیید و اجرا", callback_data=f"ai_act_confirm|{pending_id}")],
        [InlineKeyboardButton("❌ لغو اقدام", callback_data=f"ai_act_cancel|{pending_id}")],
        [InlineKeyboardButton("🔚 بستن", callback_data="consultant_ai_end")],
    ])

def _super_action_result_kb(log_id: int | None, reversible: bool = False):
    rows = []
    if reversible and log_id:
        rows.append([InlineKeyboardButton("↩️ بازگردانی آخرین تغییر", callback_data=f"ai_act_undo|{log_id}")])
    rows.append([InlineKeyboardButton("🔚 بستن", callback_data="consultant_ai_end")])
    return InlineKeyboardMarkup(rows)

def _set_consultant_ai_active(context, active: bool = True):
    ud = getattr(context, "user_data", None)
    if not isinstance(ud, dict):
        return
    if active:
        ud["consultant_ai_active"] = True
        ud["consultant_active"] = True  # سازگاری با مسیر قدیمی
    else:
        ud.pop("consultant_ai_active", None)
        ud.pop("consultant_active", None)

def _is_consultant_ai_active(context) -> bool:
    ud = getattr(context, "user_data", None)
    if not isinstance(ud, dict):
        return False
    return bool(ud.get("consultant_ai_active") or ud.get("consultant_active"))

# ═══════════════ 🆕 فروشگاه در ربات: لینک، سفارش‌ها، نظردهی ═══════════════
_SHOP_STATUS_FA = {"pending": "⏳ در انتظار", "completed": "✅ تکمیل‌شده", "cancelled": "⛔ لغو"}

# فیلدهای ویرایشی پروفایل (هماهنگ با سایت): ربات فقط سه فیلد هویتی را مستقیم ویرایش می‌کند.
_BOT_EDITABLE_FIELDS = frozenset({"first_name", "last_name", "city"})
_PROFILE_EDIT_CALLBACKS = (
    "upro|edit|first_name", "upro|edit|last_name", "upro|edit|city",
    "upro|edit|region", "upro|edit|contact_time",
)

def _profile_inline_kb(site_url: str = "", has_beauty_center: bool = False, edit_locked: bool = False):
    """ویرایش کوتاه پروفایل + کارت مرکز زیبایی؛ قفل ویرایش در صورت ویرایشِ سایت.

    اگر edit_locked=True (کاربر اطلاعات را در «سایت» ویرایش کرده) دکمه‌های ویرایش
    نشان داده نمی‌شوند تا سایت منبع اصلی بماند.
    """
    from telegram import InlineKeyboardButton, InlineKeyboardMarkup
    rows = []
    if not edit_locked:
        _shown = [cb for cb in _PROFILE_EDIT_CALLBACKS
                  if cb.rsplit("|", 1)[-1] in _BOT_EDITABLE_FIELDS]
        rows.append([
            InlineKeyboardButton(("✏️ نام" if cb.endswith("first_name") else "✏️ نام خانوادگی"),
                                 callback_data=cb)
            for cb in _shown[:2]
        ])
        rows.append([InlineKeyboardButton("📍 شهر", callback_data=_shown[2])])
    if has_beauty_center:
        rows.append([
            InlineKeyboardButton("🏥 وضعیت مرکز من", callback_data="bcowner|show"),
            InlineKeyboardButton("🌐 پنل مرکز", url=f"{site_url}/dashboard/beauty-center"),
        ])
    else:
        rows.append([InlineKeyboardButton("🏥 ثبت رایگان مرکز", url=f"{site_url}/beauty-centers/register")])
    rows.append([InlineKeyboardButton("🔙 بازگشت به منوی اصلی", callback_data="upro|home")])
    return InlineKeyboardMarkup(rows)

async def _show_user_profile(message, phone: str):
    from giso.user_profile_service import get_user_activity_summary, get_user_profile
    profile = get_user_profile(phone)
    if not profile:
        await message.reply_text(
            "👤 برای تکمیل پروفایل، ابتدا حساب سایت را با همین شماره ایجاد کنید.\n"
            f"🌐 {_get_giso_site_url()}/register"
        )
        return
    activity = get_user_activity_summary(phone)
    try:
        from giso.ai_credits import get_ai_credit
        ai_credit = get_ai_credit(phone, create=True)
    except Exception:
        ai_credit = {"balance": 0, "total_used": 0}
    # بعضی نسخه‌های بله قالب‌بندی HTML را به‌صورت خام نشان می‌دهند؛
    # پروفایل عمداً Plain Text ارسال می‌شود تا نشانه‌های قالب‌بندی دیده نشوند.
    safe = lambda value: str(value or "—").replace("<", "‹").replace(">", "›").replace("&", "و")
    lines = [
        "👤 پروفایل من", "━━━━━━━━━━━━━━━━",
        f"نام: {safe(profile.get('first_name'))}",
        f"نام خانوادگی: {safe(profile.get('last_name'))}",
        f"📱 موبایل: {safe(display_phone(profile.get('phone') or phone))}",
        f"📍 شهر: {safe(profile.get('city'))}",
        f"🗺 منطقه: {safe(profile.get('region'))}",
        f"🤖 اتصال بله: {'متصل ✅' if activity.get('bot_connected') else 'متصل نشده'}",
        "━━━━━━━━━━━━━━━━", "📊 فعالیت‌های من",
        f"🔬 آنالیز: {_fa_num(activity.get('analyses', 0))}",
        f"🛍 خرید: {_fa_num(activity.get('shop_checkouts', 0))}",
        f"💇 فروش مو: {_fa_num(activity.get('hair_orders', 0))}",
        f"🏪 آگهی بازارچه: {_fa_num(activity.get('market_listings', 0))}",
        f"📈 پیشنهاد خرید: {_fa_num(activity.get('market_offers', 0))}",
        f"💬 گفتگوی بازارچه: {_fa_num(activity.get('market_conversations', 0))}",
        f"🔔 اعلان جدید: {_fa_num(activity.get('unread_notifications', 0))}",
        f"✨ اعتبار همراه هوشمند: {_fa_num(ai_credit.get('balance', 0))}",
        f"📉 مصرف هوش مصنوعی: {_fa_num(ai_credit.get('total_used', 0))}",
    ]
    try:
        from giso.beauty_centers.services import get_owner_center
        has_beauty_center = bool(get_owner_center(int(profile.get("id") or 0)))
    except Exception:
        has_beauty_center = False
    try:
        from giso.user_profile_service import is_bot_profile_edit_locked
        edit_locked = is_bot_profile_edit_locked(profile.get("phone") or phone)
    except Exception:
        edit_locked = False
    if edit_locked:
        lines.append("━━━━━━━━━━━━━━━━")
        lines.append("🌐 اطلاعات نام و شهر در سایت به‌روز شده است؛ برای ویرایش از بخش پروفایل سایت استفاده کنید.")
    await message.reply_text(
        "\n".join(lines),
        reply_markup=_profile_inline_kb(_get_giso_site_url() or "https://gisosadeghi.ir",
                                        has_beauty_center, edit_locked=edit_locked),
    )

async def _show_user_notifications(message, phone: str):
    from telegram import InlineKeyboardButton, InlineKeyboardMarkup
    from giso.panel.modules.notifications import list_user_notifications, user_unread_count
    items = list_user_notifications(phone, limit=8)
    unread = user_unread_count(phone)
    lines = [f"🔔 اعلان‌های من — {_fa_num(unread)} خوانده‌نشده", "━━━━━━━━━━━━━━━━"]
    rows = []
    if not items:
        lines.append("اعلان تازه‌ای ندارید.")
    for item in items:
        icon = {"shop": "🛍", "hair_sale": "💇", "marketplace": "🏪", "wallet": "💰", "analysis": "🔬"}.get(item.get("category"), "🔔")
        marker = "🔴" if item.get("status") == "unread" else "⚪️"
        title = str(item.get("title") or "اعلان گیسو").replace("<", "‹").replace(">", "›").replace("&", "و")
        plain_message = re.sub(r"<[^>]+>", "", str(item.get("message") or ""))
        plain_message = plain_message[:220].replace("<", "‹").replace(">", "›").replace("&", "و")
        created_at = str(item.get("created_at") or "").replace("<", "‹").replace(">", "›").replace("&", "و")
        lines.append(f"{marker} {icon} {title}\n{plain_message}\n🕒 {created_at}")
        if item.get("status") == "unread":
            rows.append([InlineKeyboardButton(
                f"✅ خواندم #{item.get('id')}", callback_data=f"unotif|read|{item.get('id')}"
            )])
    if unread:
        rows.append([InlineKeyboardButton("✅ خواندن همه", callback_data="unotif|all")])
    rows.append([
        InlineKeyboardButton("🔄 نمایش اعلان‌ها", callback_data="unotif|show"),
        InlineKeyboardButton("🌐 اعلان‌ها در سایت", url=f"{_get_giso_site_url()}/dashboard/notifications"),
    ])
    await message.reply_text("\n\n".join(lines), reply_markup=InlineKeyboardMarkup(rows))

def _user_kb(pending: bool = False):
    # پنل کاربر نهایی — ۶ دکمه‌ی اصلی (خلوت). دکمه‌های قدیمی (آنالیز/فروش مو/بازارچه/فروشگاه)
    # از کیبورد حذف شدند، اما handlerهای متنی آن‌ها برای سازگاری با کیبوردِ بازِ کاربران
    # حفظ شده‌اند؛ دسترسی کامل از «⚡️ عملیات سریع من» و سایت ممکن است.
    return ReplyKeyboardMarkup(
        [
            ["💰 کیف پول", "🎯 مأموریت"],
            ["💬 مشاور"],
            ["👤 پروفایل", "🎧 پشتیبانی"],
            ["📖 راهنما"],
        ],
        resize_keyboard=True,
    )

def _user_hair_sale_kb():
    return ReplyKeyboardMarkup(
        [
            ["📋 درخواست‌های قبلی من"],
            ["🌐 ثبت درخواست جدید (سایت)"],
            ["⭐ ثبت نظر"],
            ["🔙 بازگشت"],
        ],
        resize_keyboard=True,
    )

def _admin_hair_sale_kb():
    """منوی هوشمند فروش مو ادمین (فاز ۵ نهایی) — جایگزین منوی ۵ گزینه قدیمی.

    بدون uid → همه گزینه‌ها (برای پاسخ‌های داخلی hair_sale.py)؛
    ورود از منوی ادمین از build_admin_hair_menu(uid=uid) استفاده می‌کند (زیرگزینه‌ها).
    """
    return build_admin_hair_menu(uid=None)

def _admin_hair_reports_kb():
    """زیرمنوی گزارش‌های فروش مو (فاز 3.2 + فاز 5.1 ربات)."""
    # طبق مشخصات: «⏳ در انتظار» (کاربردی نداشت) و «💬 گفتگوها» (تکراری با منوی اصلی) حذف شدند
    return ReplyKeyboardMarkup(
        [
            ["📊 گزارش کلی", "🔍 نمایش در حال بررسی"],
            ["❌ نمایش رد شده", "💰 قیمت ثبت‌شده"],
            ["💰 فروش کلی"],
            ["🔙 بازگشت"],
        ],
        resize_keyboard=True,
    )

def _admin_hair_status_kb():
    return ReplyKeyboardMarkup(
        [
            ["📥 در انتظار بررسی", "✅ تایید شده"],
            ["❌ رد شده", "📝 اعتراض ثبت شده"],
            ["📦 تکمیل شده"],
            ["🔙 بازگشت"],
        ],
        resize_keyboard=True,
    )

_SUPER_ONLY_ADMIN_TEXTS = frozenset({
    "👥 مدیریت کاربران سایت", "👥 مدیریت کاربران", "👑 مدیریت ادمین‌ها",
    "📢 مدیریت کانال", "⚙️ مدیریت سایت و ربات", "⚙️ تنظیمات سایت",
    "🌐 تنظیم آدرس سایت گیسو", "💾 پشتیبان‌گیری", "🔄 ریستارت ربات",
    "⏱ محدودیت زمان تحلیل", "🎨 انتخاب تم سایت", "✨ تم ساده طلایی",
    "👑 تم کلاسیک", "💇 تم ارزش مو و بازارچه", "🔬 تم سلامت و آنالیز",
    "✦ تم دستیار هوشمند", "🎯 تم مسیر هوشمند گیسو",
    "🚨 وضعیت فوری", "🔑 تنظیم کلمه ادمینی", "📥 بررسی درخواست‌ها", "📋 لیست ادمین‌ها",
    "🗑 حذف ادمین", "🗑 حذف همه درخواست‌ها",
})

async def _show_admin_settings(msg):
    try:
        await msg.reply_text(
            "⚙️ به منوی مدیریت سایت و ربات خوش آمدید.",
            reply_markup=_admin_settings_kb(),
        )
    except Exception:
        pass

async def _show_admin_phrase_menu(msg):
    """نمایش منوی تنظیم کلمه ادمینی با دکمه‌های ویرایش/حذف/ثبت."""
    try:
        from giso_admin import get_giso_config
        cur = get_giso_config("admin_request_phrase", "") or ""
    except Exception:
        cur = ""
    if cur.strip():
        txt = f"🔑 کلمه ادمینی فعلی: {cur}"
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("✏️ ویرایش کلمه", callback_data="adm_phrase_edit"),
             InlineKeyboardButton("🗑 حذف کلمه", callback_data="adm_phrase_delete")],
            [InlineKeyboardButton("🔙 بازگشت", callback_data="adm_mgmt_back")],
        ])
    else:
        txt = "🔑 هنوز کلمه‌ای ثبت نشده"
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("➕ ثبت کلمه ادمینی", callback_data="adm_phrase_add")],
            [InlineKeyboardButton("🔙 بازگشت", callback_data="adm_mgmt_back")],
        ])
    await msg.reply_text(txt, reply_markup=kb)

def _user_del_confirm_kb(bale_id: str, phone: str = ""):
    if bale_id:
        cb = f"user_del_confirm|{bale_id}"
    else:
        cb = f"user_del_confirm_phone|{phone}"
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ بله، حذف شود", callback_data=cb),
         InlineKeyboardButton("❌ خیر، لغو", callback_data="user_del_cancel")]
    ])

# ═══ پشتیبان‌گیری دیتابیس (توابع کمکی سطح ماژول) ═══

_backup_job = None  # global برای نگه داشتن job فعلی

def _stop_backup_timer(context):
    """توقف timer backup خودکار."""
    global _backup_job
    if _backup_job is not None:
        try:
            _backup_job.schedule_removal()
        except Exception:
            pass
        _backup_job = None
        logger.info("backup خودکار متوقف شد")
    try:
        if context is not None and hasattr(context, "job_queue") and context.job_queue is not None:
            current = context.job_queue.get_jobs_by_name('giso_auto_backup')
            for job in current:
                try:
                    job.schedule_removal()
                except Exception:
                    pass
    except Exception as e:
        logger.debug(f"_stop_backup_timer: {e}")

def _start_backup_timer(context, hours):
    """شروع timer برای backup خودکار."""
    global _backup_job
    _stop_backup_timer(context)
    if hours <= 0:
        return
    try:
        if context is None or not hasattr(context, "job_queue") or context.job_queue is None:
            logger.debug("job_queue در دسترس نیست؛ backup خودکار زمان‌بندی نشد")
            return
        _backup_job = context.job_queue.run_repeating(
            _auto_backup_job,
            interval=hours * 3600,
            first=hours * 3600,
            name='giso_auto_backup',
        )
        logger.info(f"backup خودکار تنظیم شد: هر {hours} ساعت")
    except Exception as e:
        logger.error(f"_start_backup_timer: {e}")

async def _auto_backup_job(context):
    """اجرای خودکار backup (صدا زده شده توسط job_queue)."""
    import shutil
    from datetime import datetime
    try:
        from giso.base import checkpoint_giso_db
    except Exception:
        checkpoint_giso_db = None

    logger.info("شروع backup خودکار...")
    try:
        if checkpoint_giso_db:
            checkpoint_giso_db()

        db_path = os.path.join(os.path.dirname(__file__), "data", "giso.db")
        backup_dir = _backup_dir()
        os.makedirs(backup_dir, exist_ok=True)
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_path = os.path.join(backup_dir, f"giso_auto_{timestamp}.db")
        shutil.copy2(db_path, backup_path)

        all_backups = sorted(
            [f for f in os.listdir(backup_dir)
             if f.startswith("giso_auto_") and f.endswith(".db")]
        )
        max_files = _backup_max_files()
        while len(all_backups) > max_files:
            old = all_backups.pop(0)
            os.remove(os.path.join(backup_dir, old))
            logger.info(f"backup قدیمی حذف شد: {old}")

        logger.info(f"backup خودکار موفق: {backup_path}")
    except Exception as e:
        logger.error(f"backup خودکار خطا: {e}")

async def _periodic_checkpoint(context):
    """checkpoint خودکار giso.db هر ۵ دقیقه (انتقال WAL به دیتابیس اصلی)."""
    try:
        from giso.base import checkpoint_giso_db
        checkpoint_giso_db()
    except Exception as e:
        logger.error(f"periodic checkpoint (giso.db) error: {e}")

async def _broadcast_queue_job(context):
    try:
        from giso.broadcasts import process_bot_batch
        await process_bot_batch(context.bot,limit=10)
    except Exception as exc:
        logger.warning("broadcast queue job: %s",exc)

async def _monitoring_ai_job(context):
    try:
        from giso.monitoring_ai import generate
        await generate(force=False)
    except Exception as exc:logger.warning("monitoring AI job: %s",exc)

async def _insights_job(context):
    """بازرس هوشمند آفلاین: عیب‌یابی خطاهای باز + استخراج پیشنهاد بهبود.

    کاملاً مستقل و در try؛ اگر AI/دیتابیس در دسترس نبود، ربات بی‌تأثیر می‌ماند.
    تحلیل فقط در زمان شغل انجام می‌شود (نه در لحظهٔ درخواست کاربر) تا سرور
    و سایت فشاری حس نکنند.
    """
    try:
        # اگر کاربر گزارش‌های هوشمند پایش را خاموش کرده، بازرس هم AI صدا نزند
        try:
            from giso.monitoring_settings import enabled as _mon_enabled
            if not _mon_enabled("ai_reports"):
                return
        except Exception:
            pass
        from giso.monitoring_insights import triage_open_errors, collect_improvement_insights
        await triage_open_errors(max_errors=5)
        await collect_improvement_insights(max_items=5)
    except Exception as exc:
        logger.warning("insights job: %s", exc)

def _init_monitoring_ai(app):
    try:
        if app is not None and app.job_queue is not None:
            app.job_queue.run_repeating(_monitoring_ai_job,interval=1800,first=300,name='giso_monitoring_ai')
            # بازرس هوشمند: هر ۱۵ دقیقه (۹۰۰ ثانیه)، اولین اجرا بعد از ۷ دقیقه
            app.job_queue.run_repeating(_insights_job,interval=900,first=420,name='giso_insights')
    except Exception as exc:logger.warning("monitoring AI init: %s",exc)

def _init_broadcast_queue(app):
    try:
        if app is not None and app.job_queue is not None:
            app.job_queue.run_repeating(_broadcast_queue_job,interval=60,first=8,name='giso_broadcast_queue')
    except Exception as exc:logger.warning("broadcast queue init: %s",exc)

def _init_periodic_checkpoint(app):
    """ثبت job checkpoint خودکار هر ۵ دقیقه برای giso.db."""
    try:
        if app is not None and hasattr(app, "job_queue") and app.job_queue is not None:
            app.job_queue.run_repeating(
                _periodic_checkpoint,
                interval=300,   # هر ۵ دقیقه
                first=300,      # اولین اجرا بعد از ۵ دقیقه
                name='giso_periodic_checkpoint',
            )
            logger.info("periodic checkpoint (giso.db) هر ۵ دقیقه فعال شد")
    except Exception as e:
        logger.error(f"_init_periodic_checkpoint: {e}")

def _init_auto_backup(app):
    """بررسی و شروع backup خودکار هنگام startup."""
    try:
        hours = _get_backup_interval_hours()
        if hours > 0 and app is not None and hasattr(app, "job_queue") and app.job_queue is not None:
            app.job_queue.run_repeating(
                _auto_backup_job,
                interval=hours * 3600,
                first=hours * 3600,
                name='giso_auto_backup',
            )
            logger.info(f"backup خودکار شروع شد: هر {hours} ساعت")
    except Exception as e:
        logger.warning(f"_init_auto_backup: {e}")

# ═══ پنل کاربر آنالیز: آدرس سایت و توابع کمکی اتصال به سایت ═══

# آدرس پیش‌فرض سایت (برای سازگاری؛ بهتر است از _get_giso_site_url() استفاده شود)

# ═══ پنل ادمین: مدیریت آنالیز (پیگیری سریع) ═══

# ═══════════════════════════════════════════════════════════
# مشاور صادقی در ربات (گفتگوی هوشمند با آگاهی از فعالیت‌های کاربر)
# ═══════════════════════════════════════════════════════════

# ═══════════════════════════════════════════════════════════
# سیستم پشتیبانی (تیکت‌های کاربر + پاسخ ادمین)
# ═══════════════════════════════════════════════════════════

# ═══════════════════════════════════════════════════════════
# پیام ورود هوشمند کاربر (بر اساس فعالیت‌ها)
# ═══════════════════════════════════════════════════════════

# ═══════════════════════════════════════════════════════════
# پیام ورود هوشمند ادمین (آمار کلی + اولویت‌ها)
# ═══════════════════════════════════════════════════════════

# ═══════════════════════════════════════════════════════════
# خلاصه گفتگوهای مشاور برای ادمین
# ═══════════════════════════════════════════════════════════

async def _run_async(token=None, test_mode=False):
    from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardButton, InlineKeyboardMarkup
    from telegram.ext import (
        CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler, PreCheckoutQueryHandler,
    )

    _giso_init_db()
    # ربات ممکن است مستقل از وب اجرا شود؛ مهاجرت‌های افزایشی قبل از منوهای
    # کیف پول، پروفایل، بازارچه و مراکز باید آماده باشند.
    try:
        from giso.models import migrate_giso_tables
        from giso.marketplace.schema import migrate_marketplace_tables
        from giso.beauty_centers.schema import migrate_beauty_center_tables
        migrate_giso_tables()
        migrate_marketplace_tables()
        migrate_beauty_center_tables()
    except Exception as migration_exc:
        logger.error("bot startup migrations failed: %s", migration_exc)
    try:
        init_ai_runtime_tables()
    except Exception as e:
        logger.debug(f"init_ai_runtime_tables in bot: {e}")
    _user_states = {}
    _ai_temp_data = {}
    # مرحله ۶: گفتگوی دستیار «آقا رضا» در ربات برای ادمین اختصاصی (uid های فعال)
    _special_chat_active = set()
    # ── فیکس موضعی نشت حافظهٔ state ──────────────────────────────────────
    # stateهای گفتگوی رهاشده (کاربر فرم را نیمه‌کاره رها کرده) تا ری‌استارت
    # ربات در حافظه می‌ماندند. این بخش فقط هرس می‌کند؛ هیچ هندلری تغییر نمی‌کند.
    _touch_state_activity, _maybe_cleanup_stale_states = make_state_pruner(
        _user_states, _ai_temp_data,
    )  # TTL ۲ ساعته + سقف ۲۰۰۰ کاربر (پیش‌فرض‌های هرس)
    # ─────────────────────────────────────────────────────────────────────
    try:
        from giso.special_assistant import init_special_assistant_tables as _init_sa_tables
        _init_sa_tables()
    except Exception as _e_sa_init:
        logger.debug(f"init_special_assistant_tables in bot: {_e_sa_init}")
    # فیکس موضعی فروشگاه: ثبت مرجع state برای callbackهای stateدار shop (بدون refactor)
    try:
        from giso.shop.bot.handlers import register_user_states as _shop_reg_states
        _shop_reg_states(_user_states)
    except Exception as _e_shop_states:
        logger.debug(f"shop register_user_states: {_e_shop_states}")

    async def _show_ai_panel(target, is_q=False):
        providers = list_ai_providers()
        total = len(providers)
        active = sum(1 for p in providers if p["enabled"])
        healthy = sum(1 for p in providers if str(p["last_status"]).lower().startswith("ok"))
        nokey = sum(1 for p in providers if not str(p["api_key"]).strip())

        lines = [
            "🧩 مدیریت Providerها و پروکسی",
            "──────────────",
            f"📦 کل پروایدرها: {_fa_num(total)}",
            f"✅ فعال: {_fa_num(active)}   🟢 سالم: {_fa_num(healthy)}",
        ]
        if nokey:
            lines.append(f"⚙️ بدون API Key: {_fa_num(nokey)}")
        lines += [
            "",
            "ℹ️ کلیدها را می‌توانید از همین منو وارد کنید.",
        ]
        text = "\n".join(lines)
        if is_q:
            try:
                await target.edit_message_text(text, reply_markup=_admin_ai_kb())
            except Exception:
                await target.message.reply_text(text, reply_markup=_admin_ai_kb())
        else:
            await target.reply_text(text, reply_markup=_admin_ai_kb())

    async def _show_managed_ai_panel(target, is_q=False):
        text = _managed_ai_dashboard_text()
        if is_q:
            try:
                await target.edit_message_text(text, reply_markup=_managed_ai_main_kb())
            except Exception:
                await target.message.reply_text(text, reply_markup=_managed_ai_main_kb())
        else:
            await target.reply_text(text, reply_markup=_managed_ai_main_kb())

    async def _show_managed_ai_status_menu(target, is_q=False):
        text = "📊 وضعیت و سلامت هوش مصنوعی\n━━━━━━━━━━━━━━━━━━━━━━━\nاز این بخش می‌تونی گزارش وضعیت، سلامت AI فعال و providerها را ببینی."
        if is_q:
            await target.edit_message_text(text, reply_markup=_managed_ai_status_kb())
        else:
            await target.reply_text(text, reply_markup=_managed_ai_status_kb())

    async def _show_managed_ai_selection_menu(target, is_q=False):
        chain = get_failover_chain()
        text = (
            "🎯 انتخاب و پایداری AI\n━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"AI فعال فعلی: {get_active_provider() or '—'}\n"
            f"زنجیره Failover: {' ← '.join(chain[:5]) if chain else 'ندارد'}"
        )
        if is_q:
            await target.edit_message_text(text, reply_markup=_managed_ai_selection_kb())
        else:
            await target.reply_text(text, reply_markup=_managed_ai_selection_kb())

    async def _show_managed_ai_permissions(target, is_q=False):
        text = (
            "🔐 تنظیم دسترسی‌های هوش مصنوعی\n"
            "━━━━━━━━━━━━━━━━━━━━━━━\n"
            "برای کدام گروه می‌خواهی سطح، بخش‌ها و محدودیت روزانه را تنظیم کنی؟"
        )
        if is_q:
            await target.edit_message_text(text, reply_markup=_managed_ai_permission_roles_kb())
        else:
            await target.reply_text(text, reply_markup=_managed_ai_permission_roles_kb())

    async def _show_managed_ai_permission_role(query, role):
        await query.edit_message_text(
            _managed_ai_permission_detail_text(role),
            reply_markup=_managed_ai_permission_detail_kb(role),
        )

    async def _show_managed_ai_display_name(target, is_q=False):
        text = (
            "✏️ تنظیم اسم نمایشی هوش مصنوعی\n"
            "━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"اسم فعلی: {get_display_name()}\n\n"
            "این اسم در پاسخ‌های چت مشاور نمایش داده می‌شود."
        )
        if is_q:
            await target.edit_message_text(text, reply_markup=_managed_ai_display_name_kb())
        else:
            await target.reply_text(text, reply_markup=_managed_ai_display_name_kb())

    async def _show_managed_ai_capabilities(target, is_q=False):
        text = (
            "📋 قابلیت‌های هوش مصنوعی\n"
            "━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"👥 کاربر عادی:\n{get_role_capabilities('user')[:300]}\n\n"
            f"👮 ادمین محدود:\n{get_role_capabilities('admin')[:300]}\n\n"
            f"👑 سوپرادمین:\n{get_role_capabilities('super')[:300]}"
        )
        if is_q:
            await target.edit_message_text(text, reply_markup=_managed_ai_capabilities_roles_kb())
        else:
            await target.reply_text(text, reply_markup=_managed_ai_capabilities_roles_kb())

    async def _show_managed_ai_providers(target, is_q=False):
        text = _managed_ai_provider_picker_text()
        kb = _managed_ai_provider_list_kb()
        if is_q:
            await target.edit_message_text(text, reply_markup=kb)
        else:
            await target.reply_text(text, reply_markup=kb)

    async def _show_managed_ai_role_capabilities(query, role):
        text = (
            f"📋 قابلیت‌های نقش {ROLE_LABELS.get(role, role)}\n"
            "━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"{get_role_capabilities(role)}"
        )
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("✏️ ویرایش", callback_data=f"mair_caps_edit|{role}")],
            [InlineKeyboardButton("🔙 بازگشت", callback_data="mair_menu_capabilities")],
        ])
        await query.edit_message_text(text, reply_markup=kb)

    async def _show_managed_ai_toggle(target, is_q=False):
        status = "✅ فعال" if is_chat_enabled() else "❌ غیرفعال"
        info = get_runtime_overview()
        text = (
            "🔛 وضعیت هوش مصنوعی\n"
            "━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"وضعیت فعلی: {status}\n\n"
            f"📊 آمار امروز: {_fa_num(info['today_users'])} کاربر | {_fa_num(info['today_chats'])} گفتگو"
        )
        if is_q:
            await target.edit_message_text(text, reply_markup=_managed_ai_toggle_kb())
        else:
            await target.reply_text(text, reply_markup=_managed_ai_toggle_kb())

    async def _show_managed_ai_report(target, is_q=False):
        text = build_status_report()
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 بازگشت", callback_data="mair_menu_status")],
        ])
        if is_q:
            await target.edit_message_text(text, reply_markup=kb)
        else:
            await target.reply_text(text, reply_markup=kb)

    async def _show_managed_ai_failover(query):
        chain = get_failover_chain()
        rows = []
        for name in list_provider_options().get('iranian', []) + list_provider_options().get('foreign', []):
            pname = name['name']
            idx = chain.index(pname) + 1 if pname in chain else 0
            label = f"{idx}. {pname}" if idx else f"— {pname}"
            rows.append([InlineKeyboardButton(label, callback_data=f"mair_fail_promote|{pname}")])
        rows.extend([
            [InlineKeyboardButton("🧪 تست زنجیره", callback_data="mair_fail_test")],
            [InlineKeyboardButton("♻️ بازنشانی به پیش‌فرض", callback_data="mair_fail_reset")],
            [InlineKeyboardButton("🔙 بازگشت", callback_data="mair_menu_selection")],
        ])
        text = (
            "🔁 Failover و ترتیب پشتیبان\n━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"ترتیب فعلی: {' ← '.join(chain) if chain else 'ندارد'}\n\n"
            "برای بالا آوردن اولویت هر provider، روی آن بزن تا اول زنجیره قرار بگیرد."
        )
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(rows))

    async def _show_managed_ai_ops(target, is_q=False):
        text = (
            "⚙️ عملیات و تاریخچه\n━━━━━━━━━━━━━━━━━━━━━━━\n"
            "اقدامات در انتظار، لاگ‌ها و بازگردانی‌های اخیر را از اینجا ببین."
        )
        if is_q:
            await target.edit_message_text(text, reply_markup=_managed_ai_ops_kb())
        else:
            await target.reply_text(text, reply_markup=_managed_ai_ops_kb())

    async def _show_pending_actions(query):
        rows = get_recent_pending_actions(limit=10)
        btns = []
        text_lines = ["⏳ اقدامات در انتظار تأیید", "━━━━━━━━━━━━━━━━━━━━━━━"]
        if not rows:
            text_lines.append("فعلاً اقدامی در انتظار تأیید نیست.")
        else:
            for idx, item in enumerate(rows, start=1):
                title = str(item.get('preview_text') or item.get('action_name') or 'اقدام')
                title_short = title.splitlines()[0][:60]
                text_lines.append(f"{idx}. #{item.get('id')} — {title_short}")
                btns.append([
                    InlineKeyboardButton(f"👁 جزئیات #{item.get('id')}", callback_data=f"mair_pending_view|{item.get('id')}")
                ])
        btns.append([InlineKeyboardButton("🔙 بازگشت", callback_data="mair_menu_ops")])
        await query.edit_message_text("\n".join(text_lines), reply_markup=InlineKeyboardMarkup(btns))

    async def _show_action_logs(query):
        rows = get_recent_action_logs(limit=10)
        btns = []
        text_lines = ["🧾 لاگ اقدامات AI", "━━━━━━━━━━━━━━━━━━━━━━━"]
        if not rows:
            text_lines.append("لاگی ثبت نشده است.")
        else:
            for idx, item in enumerate(rows, start=1):
                text_lines.append(f"{idx}. [{item.get('status')}] {item.get('action_name')} روی {item.get('target_table') or '—'} #{item.get('target_id') or 0}")
                btns.append([InlineKeyboardButton(f"👁 جزئیات لاگ #{item.get('id')}", callback_data=f"mair_log_view|{item.get('id')}")])
        btns.append([InlineKeyboardButton("🔙 بازگشت", callback_data="mair_menu_ops")])
        await query.edit_message_text("\n".join(text_lines), reply_markup=InlineKeyboardMarkup(btns))

    async def _show_rollbacks(query):
        rows = get_recent_rollback_logs(limit=10)
        btns = []
        text_lines = ["↩️ بازگردانی‌های اخیر", "━━━━━━━━━━━━━━━━━━━━━━━"]
        if not rows:
            text_lines.append("هنوز rollback ثبت نشده است.")
        else:
            for idx, item in enumerate(rows, start=1):
                text_lines.append(f"{idx}. {item.get('action_name')} — {to_shamsi(item.get('created_at'))}")
        btns.append([InlineKeyboardButton("🔙 بازگشت", callback_data="mair_menu_ops")])
        await query.edit_message_text("\n".join(text_lines), reply_markup=InlineKeyboardMarkup(btns))

    async def _show_managed_ai_widget_menu(target, is_q=False):
        cfg = get_widget_config()
        status = "فعال ✅" if cfg['enabled'] else "غیرفعال ❌"
        text = (
            "🌐 تنظیمات Widget سایت\n━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"وضعیت: {status}\n"
            f"موقعیت: {cfg['position']}\n"
            f"رنگ اصلی: {cfg['primary_color']}\n"
            f"متن خوش‌آمد: {cfg['welcome_message'][:80]}"
        )
        if is_q:
            await target.edit_message_text(text, reply_markup=_managed_ai_widget_kb())
        else:
            await target.reply_text(text, reply_markup=_managed_ai_widget_kb())

    async def _show_widget_stats(query):
        st = get_widget_usage_stats()
        lines = [
            "📊 آمار استفاده Widget",
            "━━━━━━━━━━━━━━━━━━━━━━━",
            f"👥 کاربران امروز: {_fa_num(st['today_users'])}",
            f"💬 پیام‌های امروز: {_fa_num(st['today_messages'])}",
            "",
            "📄 پرمصرف‌ترین صفحات:",
        ]
        if st['pages']:
            for idx, item in enumerate(st['pages'], start=1):
                lines.append(f"{idx}. {item['page']} ({_fa_num(item['count'])})")
        else:
            lines.append("هنوز داده‌ای ثبت نشده است.")
        await query.edit_message_text("\n".join(lines), reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 بازگشت", callback_data="mair_menu_widget")]]))

    async def _show_proxy_panel(target, is_q=False):
        summary = status_summary()
        lines = [
            "📊 وضعیت پروکسی Gemini در گیسو",
            "━━━━━━━━━━━━━━━━",
            f"🔹 حالت اتصال: {summary['mode_label']}",
            f"🔹 آدرس ورکر: {summary['worker_url']}" if summary.get("is_worker") else "",
            f"🔹 تعداد پروکسی‌های سالم: {_fa_num(summary['working_count'])}",
            f"🔹 تعداد پروکسی‌های دستی: {_fa_num(summary['manual_count'])}",
            f"🔹 پروکسی فعال فعلی: {summary['active_proxy'] or 'ندارد'}",
            f"🔹 آخرین بررسی: {summary['last_checked']}",
            f"🔹 آدرس منبع: {summary['source_url']}",
        ]
        text = "\n".join([_l for _l in lines if _l])
        if is_q:
            try:
                await target.edit_message_text(text, reply_markup=_admin_proxy_kb())
            except Exception:
                await target.message.reply_text(text, reply_markup=_admin_proxy_kb())
        else:
            await target.reply_text(text, reply_markup=_admin_proxy_kb())

    async def _ai_cmd_list_providers(msg):
        providers = list_ai_providers()
        if not providers:
            await msg.reply_text("📋 هیچ پروایدری ثبت نشده است.", reply_markup=_admin_ai_kb())
        else:
            lines = ["📋 فهرست پروایدرها", "━━━━━━━━━━━━━━━━"]
            for r in providers:
                icon = "✅" if r["enabled"] else "❌"
                flag = " 🇮🇷" if r["is_iranian"] else ""
                prx = " 🌐" if r["use_proxy"] else ""
                key_icon = "✅" if (r["api_key"] or "").strip() else "❌"
                lines.append(
                    f"{icon} {r['name']} ({r['kind']}){flag}{prx}\n"
                    f"    API Key: {key_icon} | مدل: {r['selected_model'] or '—'}\n"
                    f"    وضعیت: {r['last_status'] or '—'}"
                )
                if r["last_error"]:
                    lines.append(f"    ⚠️ خطا: {str(r['last_error'])[:100]}")
            text = "\n".join(lines)
            if len(text) > 3800:
                text = text[:3800] + "\n…"
            await msg.reply_text(text, reply_markup=_admin_ai_kb())

    async def _ai_cmd_smart_refresh(msg):
        """🔄 بروزرسانی هوشمند مدل‌ها — لیست هر سرویس را از /models خودش
        هوشمندانه به‌روز می‌کند (رایگان + قوی + کم‌هزینه) و گزارش می‌دهد.
        کل بدنه محافظت‌شده است تا هیچ خطایی به هندلر عمومی نشت نکند."""
        try:
            from giso.ai_discovery import refresh_all_models_async
            await msg.reply_text("⏳ در حال بروزرسانی هوشمند همهٔ هوش مصنوعی‌ها...",
                                 reply_markup=ReplyKeyboardRemove())
            try:
                res = await refresh_all_models_async()
            except Exception as e:
                logger.exception("smart refresh engine error")
                await msg.reply_text(f"❌ خطا در بروزرسانی: {type(e).__name__}: {e}")
                await _show_ai_panel(msg)
                return
            lines = ["🧠 گزارش بروزرسانی هوشمند:", "", res.get("summary", "")]
            for r in (res.get("reports") or []):
                nm = r.get("name") or "?"
                if r.get("ok"):
                    lines.append(f"✅ {nm}: {r.get('vision_count', 0)} بینایی + "
                                 f"{r.get('text_count', 0)} متنی (جدید: {r.get('new', 0)})")
                    if r.get("top"):
                        lines.append(f"   ⭐ {r.get('top')}")
                elif r.get("skipped"):
                    lines.append(f"⏭ {nm}: {r.get('error') or 'رد شد'}")
                else:
                    lines.append(f"❌ {nm}: {r.get('error') or 'خطا'}")
            # گزارش بلند احتمالی تکه‌تکه فرستاده شود (سقف تلگرام ۴۰۹۶)
            await send_long_message(msg.get_bot(), msg.chat_id, "\n".join(lines), message=msg)
            await _show_ai_panel(msg)
        except Exception as e:
            logger.exception("_ai_cmd_smart_refresh unhandled")
            try:
                await msg.reply_text(f"❌ خطا در بروزرسانی هوشمند: {type(e).__name__}: {e}")
            except Exception:
                pass
            try:
                await _show_ai_panel(msg)
            except Exception:
                pass

    async def _ai_cmd_status_report(msg):
        providers = list_ai_providers()
        if not providers:
            await msg.reply_text("📊 هیچ پروایدری ثبت نشده است.", reply_markup=_admin_ai_kb())
        else:
            lines = ["📊 گزارش وضعیت پروایدرها", "━━━━━━━━━━━━━━━━", ""]
            for r in providers:
                models = []
                try:
                    models = json.loads(r["models_json"] or "[]")
                except Exception:
                    pass
                models_str = "، ".join(models[:3]) if models else "—"
                s = (r["last_status"] or "").lower()
                icon = "✅" if s.startswith("ok") else ("⚙️" if "not configured" in s else ("⚪️" if not s else "❌"))
                flag = " 🇮🇷" if r["is_iranian"] else ""
                prx = " (پروکسی 🌐)" if r["use_proxy"] else ""
                key_icon = "✅" if (r["api_key"] or "").strip() else "❌"
                lines.append(
                    f"{icon} {r['name']}{flag}{prx}\n"
                    f"  وضعیت: {r['last_status'] or '—'} | API Key: {key_icon}\n"
                    f"  مدل انتخابی: {r['selected_model'] or '—'}\n"
                    f"  مدل‌ها: {models_str}\n"
                    f"  آخرین بررسی: {to_shamsi(r['last_checked_at'])}"
                )
                if r["last_error"]:
                    lines.append(f"  ⚠️ {str(r['last_error'])[:110]}")
                lines.append("")
            text = "\n".join(lines)
            if len(text) > 3800:
                text = text[:3800] + "\n…"
            await msg.reply_text(text, reply_markup=_admin_ai_kb())

    async def _ai_cmd_check_all(msg):
        providers = list_ai_providers()
        if not providers:
            await msg.reply_text("📋 هیچ پروایدری ثبت نشده است.", reply_markup=_admin_ai_kb())
        else:
            await msg.reply_text(f"⏳ در حال بررسی {_fa_num(len(providers))} پروایدر…")
            results = await check_all_ai_providers()
            lines = ["🔄 نتیجهٔ بررسی همه پروایدرها", "━━━━━━━━━━━━━━━━"]
            ok_n = 0
            for r in results:
                good = str(r.get("status", "")).startswith("ok")
                ok_n += 1 if good else 0
                icon = "✅" if good else "❌"
                detail = r.get("selected") or r.get("error") or "—"
                pname = r.get("name", "")
                lines.append(f"{icon} {pname} — {str(detail)[:60]}")
            lines += ["", f"📊 سالم: {_fa_num(ok_n)} از {_fa_num(len(results))}"]
            await msg.reply_text("\n".join(lines), reply_markup=_admin_ai_kb())

    async def _ai_show_provider_edit(query, name: str):
        row = get_ai_provider(name)
        if not row:
            try:
                await query.answer("❌ پروایدر پیدا نشد.", show_alert=True)
            except Exception:
                pass
            return
        kind = row["kind"]
        base_url = row["base_url"] or "—"
        api_root = row["api_root"] or "—"
        timeout = row["timeout"] or 20
        key_status = "✅ ثبت‌شده" if (row["api_key"] or "").strip() else "❌ ثبت‌نشده"
        proxy_status = "فعال 🌐" if row["use_proxy"] else "غیرفعال"

        text = (
            f"📝 ویرایش پروایدر «{name}»\n\n"
            f"نوع: {kind}\n"
            f"Base URL: {base_url}\n"
            f"API Root: {api_root}\n"
            f"Timeout: {timeout} ثانیه\n"
            f"API Key: {key_status}\n"
            f"پروکسی Gemini: {proxy_status}"
        )
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔑 API Key", callback_data=f"ai_edit_fld|{name}|api_key"),
             InlineKeyboardButton("🌐 Base URL", callback_data=f"ai_edit_fld|{name}|base_url")],
            [InlineKeyboardButton("📁 API Root", callback_data=f"ai_edit_fld|{name}|api_root"),
             InlineKeyboardButton("⏱ Timeout", callback_data=f"ai_edit_fld|{name}|timeout")],
            [InlineKeyboardButton("📋 Headers (JSON)", callback_data=f"ai_edit_fld|{name}|headers"),
             InlineKeyboardButton("🔄 مدل‌های پشتیبان (JSON)", callback_data=f"ai_edit_fld|{name}|fallback")],
            [InlineKeyboardButton(f"🌐 پروکسی: {proxy_status}", callback_data=f"ai_edit_proxy|{name}")],
            [InlineKeyboardButton("🔍 تست و دریافت مجدد مدل‌ها", callback_data=f"ai_edit_ref|{name}")],
            [InlineKeyboardButton("🔙 بازگشت", callback_data="ai_edit_back")]
        ])
        try:
            await query.edit_message_text(text, reply_markup=kb)
        except Exception:
            try:
                await query.message.reply_text(text, reply_markup=kb)
            except Exception:
                pass

    async def _handle_ai_state(msg, text, uid, existing_admin) -> bool:
        if not existing_admin or not existing_admin.get("is_admin"):
            return False

        state_str = _user_states.get(uid, "")
        if not (state_str.startswith("wait_ai_") or state_str.startswith("wait_proxy_")):
            return False

        admin_phone = existing_admin.get("phone", "") if isinstance(existing_admin, dict) else ""
        if state_str in _SUPER_ONLY_AI_STATES and not _is_super_admin(uid, admin_phone):
            _user_states.pop(uid, None)
            _ai_temp_data.pop(uid, None)
            await msg.reply_text("⛔ فقط سوپرادمین", reply_markup=_admin_kb(uid))
            return True
        if state_str in _LEGACY_AI_STATES and not _has_provider_ai_management_access(uid, admin_phone, existing_admin):
            _user_states.pop(uid, None)
            _ai_temp_data.pop(uid, None)
            await msg.reply_text("⛔ شما به مدیریت Providerها و پروکسی دسترسی ندارید.", reply_markup=_admin_kb(uid))
            return True

        if text in ("🔙 بازگشت", "/cancel"):
            _user_states.pop(uid, None)
            _ai_temp_data.pop(uid, None)
            if state_str.startswith("wait_proxy_"):
                await _show_proxy_panel(msg)
            elif state_str in ("wait_ai_display_name", "wait_ai_capabilities_user", "wait_ai_capabilities_admin", "wait_ai_capabilities_super", "wait_widget_welcome", "wait_widget_color"):
                await msg.reply_text("❌ عملیات لغو شد.", reply_markup=_admin_settings_kb())
                await msg.reply_text(_managed_ai_dashboard_text(), reply_markup=_managed_ai_main_kb())
            else:
                await _show_ai_panel(msg)
            return True

        if state_str == "wait_ai_add_name":
            name = text.strip().lower()
            if not name:
                await msg.reply_text("❌ نام نمی‌تواند خالی باشد.")
                return True
            known = name in PROVIDERS_REGISTRY
            _ai_temp_data[uid] = {"name": name, "unknown": not known}
            _user_states[uid] = "wait_ai_add_key"
            step_txt = "۲/۲ — پروایدر شناخته‌شده" if known else "۲/۳ — پروایدر ناشناخته"
            await msg.reply_text(
                f"{step_txt}: لطفاً API Key برای پروایدر «{name}» را ارسال کنید (یا `-` برای خالی):",
                reply_markup=ReplyKeyboardMarkup([["🔙 بازگشت"]], resize_keyboard=True),
            )
            return True

        if state_str == "wait_ai_add_key":
            name = _ai_temp_data.get(uid, {}).get("name", "openai")
            unknown = _ai_temp_data.get(uid, {}).get("unknown", False)
            api_key = "" if text.strip() == "-" else text.strip()

            if unknown:
                _ai_temp_data[uid]["api_key"] = api_key
                _user_states[uid] = "wait_ai_add_base_url"
                await msg.reply_text(
                    f"۳/۳ — لطفاً آدرس Base URL (یا API Root) برای پروایدر «{name}» را ارسال کنید (مثلاً https://api.example.com/v1):",
                    reply_markup=ReplyKeyboardMarkup([["🔙 بازگشت"]], resize_keyboard=True),
                )
                return True

            _user_states.pop(uid, None)
            _ai_temp_data.pop(uid, None)
            reg = PROVIDERS_REGISTRY.get(name, {})
            kind = reg.get("kind", "openai")
            base_url = reg.get("base_url", "")
            api_root = reg.get("api_root", "")
            timeout = reg.get("timeout", 20)
            is_iranian = reg.get("is_iranian", False)
            use_proxy = reg.get("use_proxy", False)

            ok = add_ai_provider(
                name=name, kind=kind, api_key=api_key, base_url=base_url,
                api_root=api_root, timeout=timeout, is_iranian=is_iranian,
                use_proxy=use_proxy, enabled=True, replace=True
            )
            if not ok:
                await msg.reply_text(f"❌ ذخیرهٔ پروایدر «{name}» ناموفق بود.", reply_markup=_admin_ai_kb())
                return True

            # ذخیره همزمان در .env (بدون چاپ API Key)
            try:
                from giso.ai_brain import save_provider_to_env
                save_provider_to_env(
                    name=name, api_key=api_key, base_url=base_url,
                    model="", enabled=True, proxy=use_proxy,
                    iranian=is_iranian, timeout=timeout,
                )
            except Exception as e:
                logger.debug(f"save_provider_to_env (add known): {e}")

            await msg.reply_text(f"⏳ در حال تست سلامت پروایدر «{name}»…")
            res = await check_ai_provider(name)
            st_fa = "سالم ✅" if str(res.get("status", "")).startswith("ok") else str(res.get("status", "خطا ❌"))
            msg_res = (
                "✅ پروایدر با موفقیت اضافه شد\n\n"
                f"🤖 نام: {name}\n"
                f"📌 نوع: {kind}\n"
                f"🌐 پروکسی Gemini: {'فعال' if use_proxy else 'غیرفعال'}\n"
                f"🎯 مدل انتخابی: {res.get('selected') or '—'}\n"
                f"📊 وضعیت اتصال: {st_fa}"
            )
            if res.get("error") and not str(res.get("status", "")).startswith("ok"):
                msg_res += f"\n⚠️ خطا: {res.get('error')}"
            await msg.reply_text(msg_res, reply_markup=_admin_ai_kb())
            return True

        if state_str == "wait_ai_add_base_url":
            name = _ai_temp_data.get(uid, {}).get("name", "custom")
            api_key = _ai_temp_data.get(uid, {}).get("api_key", "")
            base_url = "" if text.strip() == "-" else text.strip()
            _user_states.pop(uid, None)
            _ai_temp_data.pop(uid, None)

            ok = add_ai_provider(
                name=name, kind="openai", api_key=api_key, base_url=base_url,
                api_root=base_url, timeout=20, is_iranian=False,
                use_proxy=False, enabled=True, replace=True
            )
            if not ok:
                await msg.reply_text(f"❌ ذخیرهٔ پروایدر «{name}» ناموفق بود.", reply_markup=_admin_ai_kb())
                return True

            # ذخیره همزمان در .env (بدون چاپ API Key)
            try:
                from giso.ai_brain import save_provider_to_env
                save_provider_to_env(
                    name=name, api_key=api_key, base_url=base_url,
                    model="", enabled=True, proxy=False,
                    iranian=False, timeout=20,
                )
            except Exception as e:
                logger.debug(f"save_provider_to_env (add custom): {e}")

            await msg.reply_text(f"⏳ در حال تست سلامت پروایدر «{name}»…")
            res = await check_ai_provider(name)
            st_fa = "سالم ✅" if str(res.get("status", "")).startswith("ok") else str(res.get("status", "خطا ❌"))
            msg_res = (
                "✅ پروایدر ناشناخته با موفقیت اضافه شد\n\n"
                f"🤖 نام: {name}\n"
                f"📌 نوع: openai\n"
                f"🔗 Base URL: {base_url}\n"
                f"🎯 مدل انتخابی: {res.get('selected') or '—'}\n"
                f"📊 وضعیت اتصال: {st_fa}"
            )
            if res.get("error") and not str(res.get("status", "")).startswith("ok"):
                msg_res += f"\n⚠️ خطا: {res.get('error')}"
            await msg.reply_text(msg_res, reply_markup=_admin_ai_kb())
            return True

        if state_str == "wait_ai_edit_val":
            name = _ai_temp_data.get(uid, {}).get("provider", "")
            field = _ai_temp_data.get(uid, {}).get("field", "")
            val = text.strip()
            _user_states.pop(uid, None)
            _ai_temp_data.pop(uid, None)

            if field in ("headers", "fallback"):
                try:
                    json.loads(val)
                except Exception:
                    await msg.reply_text("❌ فرمت JSON نامعتبر است. ویرایش لغو شد.", reply_markup=_admin_ai_kb())
                    return True
            elif field == "timeout":
                try:
                    val = str(max(5, min(120, int(val))))
                except ValueError:
                    await msg.reply_text("❌ Timeout باید عدد باشد (۵ تا ۱۲۰).", reply_markup=_admin_ai_kb())
                    return True

            ok = update_ai_provider_field(name, field, val)
            # ذخیره همزمان تغییر در .env (بدون چاپ API Key)
            if ok:
                try:
                    from giso.ai_brain import save_provider_to_env
                    prov = get_ai_provider(name)
                    if prov:
                        save_provider_to_env(
                            name=name,
                            api_key=prov.get("api_key") or "",
                            base_url=prov.get("base_url") or "",
                            model=prov.get("selected_model") or "",
                            enabled=bool(prov.get("enabled")),
                            proxy=bool(prov.get("use_proxy")),
                            iranian=bool(prov.get("is_iranian")),
                            timeout=prov.get("timeout") or 20,
                        )
                except Exception as e:
                    logger.debug(f"save_provider_to_env (update field): {e}")
            await msg.reply_text(
                f"{'✅ فیلد «' + field + '» با موفقیت ذخیره شد.' if ok else '❌ خطا در ذخیره فیلد.'}",
                reply_markup=_admin_ai_kb()
            )
            return True

        if state_str == "wait_ai_del_select":
            name = text.strip()
            row = get_ai_provider(name)
            if not row:
                _user_states.pop(uid, None)
                await msg.reply_text("❌ پروایدر پیدا نشد.", reply_markup=_admin_ai_kb())
                return True
            _ai_temp_data[uid] = {"delete_provider": name}
            _user_states[uid] = "wait_ai_del_confirm"
            await msg.reply_text(
                f"⚠️ تایید حذف پروایدر «{name}»\n"
                "آیا مطمئن هستید؟",
                reply_markup=ReplyKeyboardMarkup([["✅ بله، حذف کن", "❌ انصراف"]], resize_keyboard=True)
            )
            return True

        if state_str == "wait_ai_del_confirm":
            name = _ai_temp_data.get(uid, {}).get("delete_provider", "")
            _user_states.pop(uid, None)
            _ai_temp_data.pop(uid, None)
            if text == "✅ بله، حذف کن":
                ok = delete_ai_provider(name)
                await msg.reply_text(f"{'✅ پروایدر حذف شد' if ok else '❌ خطا در حذف'}: {name}")
            else:
                await msg.reply_text("❌ عملیات حذف لغو شد.")
            await _show_ai_panel(msg)
            return True

        if state_str == "wait_ai_check_select":
            name = text.strip()
            _user_states.pop(uid, None)
            row = get_ai_provider(name)
            if not row:
                await msg.reply_text("❌ پروایدر پیدا نشد.", reply_markup=_admin_ai_kb())
                return True
            await msg.reply_text(f"⏳ در حال بررسی «{name}»…")
            res = await check_ai_provider(name)
            st_fa = "سالم ✅" if str(res.get("status", "")).startswith("ok") else str(res.get("status", "خطا ❌"))
            models_str = "، ".join(res.get("models", [])[:5]) if res.get("models") else "—"
            msg_res = (
                f"📊 نتیجهٔ بررسی پروایدر «{name}»\n"
                "━━━━━━━━━━━━━━━━\n"
                f"🔹 وضعیت: {st_fa}\n"
                f"🎯 مدل انتخابی: {res.get('selected') or '—'}\n"
                f"📚 مدل‌ها: {models_str}"
            )
            if res.get("error") and not str(res.get("status", "")).startswith("ok"):
                msg_res += f"\n⚠️ خطا: {res.get('error')}"
            await msg.reply_text(msg_res, reply_markup=_admin_ai_kb())
            return True

        if state_str == "wait_ai_try_prompt":
            _user_states.pop(uid, None)
            prompt = text.strip()
            if not prompt:
                await msg.reply_text("❌ متن پرامپت خالی است.", reply_markup=_admin_ai_kb())
                return True
            await msg.reply_text("⏳ در حال پرسش از هوش مصنوعی…")
            role = "super" if _is_super_admin(uid) else "admin"
            res = await admin_test_prompt(prompt, actor_key=f"admin:{uid}", role=role)
            if res.get("ok"):
                answer = (res.get("text") or "").strip() or "(پاسخ خالی بود)"
                if len(answer) > 3000:
                    answer = answer[:3000] + "\n…"
                body = (
                    f"✅ پاسخ از «{res.get('provider') or '—'}»\n"
                    f"🎯 مدل: {res.get('model') or '—'}\n"
                    "━━━━━━━━━━━━━━━━\n\n"
                    f"{answer}"
                )
            else:
                body = (
                    "❌ تست هوش مصنوعی ناموفق بود\n"
                    "━━━━━━━━━━━━━━━━\n\n"
                    f"⚠️ {res.get('text') or res.get('error') or '—'}"
                )
            await msg.reply_text(body, reply_markup=_admin_ai_kb())
            return True

        if state_str == "wait_ai_display_name":
            _user_states.pop(uid, None)
            ok, message = set_display_name(text.strip())
            await msg.reply_text(
                ("✅ " if ok else "❌ ") + message,
                reply_markup=_admin_settings_kb(),
            )
            await msg.reply_text(_managed_ai_dashboard_text(), reply_markup=_managed_ai_main_kb())
            return True

        if state_str.startswith("wait_ai_capabilities_"):
            role = state_str.replace("wait_ai_capabilities_", "")
            _user_states.pop(uid, None)
            ok, message = set_role_capabilities(role, text.strip())
            await msg.reply_text(
                ("✅ " if ok else "❌ ") + message,
                reply_markup=_admin_settings_kb(),
            )
            await msg.reply_text(_managed_ai_dashboard_text(), reply_markup=_managed_ai_main_kb())
            return True

        if state_str == "wait_widget_welcome":
            _user_states.pop(uid, None)
            ok, message = set_widget_welcome_message(text.strip())
            await msg.reply_text(("✅ " if ok else "❌ ") + message, reply_markup=_admin_settings_kb())
            await msg.reply_text("🌐 تنظیمات Widget به‌روزرسانی شد.", reply_markup=_managed_ai_widget_kb())
            return True

        if state_str == "wait_widget_color":
            _user_states.pop(uid, None)
            ok, message = set_widget_primary_color(text.strip())
            await msg.reply_text(("✅ " if ok else "❌ ") + message, reply_markup=_admin_settings_kb())
            await msg.reply_text("🌐 تنظیمات Widget به‌روزرسانی شد.", reply_markup=_managed_ai_widget_kb())
            return True

        if state_str == "wait_proxy_manual_add":
            _user_states.pop(uid, None)
            lines = [l.strip() for l in text.splitlines() if l.strip()]
            cnt = set_manual_proxies(lines)
            await msg.reply_text(f"✅ تعداد {cnt} پروکسی دستی ذخیره شد.", reply_markup=_admin_proxy_kb())
            return True

        if state_str == "wait_proxy_source_url":
            _user_states.pop(uid, None)
            if text in ("پیش‌فرض", "default"):
                reset_source_url()
            else:
                set_source_url(text)
            await msg.reply_text("✅ آدرس منبع پروکسی ذخیره شد.", reply_markup=_admin_proxy_kb())
            return True

        return False

    async def _handle_ai_menu(msg, text, uid, existing_admin) -> bool:
        if not existing_admin or not existing_admin.get("is_admin"):
            return False

        admin_phone = existing_admin.get("phone", "") if isinstance(existing_admin, dict) else ""
        if text in _LEGACY_AI_MENU_TEXTS and not _has_provider_ai_management_access(uid, admin_phone, existing_admin):
            await msg.reply_text("⛔ شما به مدیریت Providerها و پروکسی دسترسی ندارید.", reply_markup=_admin_kb(uid))
            return True

        if text in (PROVIDERS_AI_LABEL, "🤖 مدیریت AI", "🤖 تنظیم AI"):
            await _show_ai_panel(msg)
            return True

        if text == "📋 فهرست پروایدرها":
            await _ai_cmd_list_providers(msg)
            return True

        if text == "➕ افزودن پروایدر":
            from telegram import ReplyKeyboardMarkup
            _user_states[uid] = "wait_ai_add_name"
            _ai_temp_data[uid] = {}
            await msg.reply_text(
                "➕ افزودن پروایدر جدید\n"
                "━━━━━━━━━━━━━━━━\n\n"
                "۱/۲ — لطفاً نام پروایدر را وارد کنید (gemini، groq، openrouter، avalai):",
                reply_markup=ReplyKeyboardMarkup([["🔙 بازگشت"]], resize_keyboard=True),
            )
            return True

        if text == "✏️ ویرایش پروایدر":
            from telegram import InlineKeyboardButton, InlineKeyboardMarkup
            providers = list_ai_providers()
            if not providers:
                await msg.reply_text("📋 هیچ پروایدری ثبت نشده است.", reply_markup=_admin_ai_kb())
            else:
                btns = []
                for p in providers:
                    icon = "✅" if p["enabled"] else "❌"
                    btns.append([InlineKeyboardButton(f"{icon} {p['name']} ({p['kind']})", callback_data=f"ai_edit_select|{p['name']}")])
                await msg.reply_text("✏️ برای ویرایش، پروایدر مورد نظر را انتخاب کنید:", reply_markup=InlineKeyboardMarkup(btns))
            return True

        if text == "⏸ فعال/غیرفعال":
            from telegram import InlineKeyboardButton, InlineKeyboardMarkup
            providers = list_ai_providers()
            if not providers:
                await msg.reply_text("📋 هیچ پروایدری ثبت نشده است.", reply_markup=_admin_ai_kb())
            else:
                btns = []
                for p in providers:
                    icon = "✅ فعال" if p["enabled"] else "❌ غیرفعال"
                    btns.append([InlineKeyboardButton(f"{p['name']} ({icon})", callback_data=f"ai_toggle|{p['name']}")])
                await msg.reply_text("⏸ برای تغییر وضعیت فعال/غیرفعال، پروایدر را انتخاب کنید:", reply_markup=InlineKeyboardMarkup(btns))
            return True

        if text == "🗑 حذف پروایدر":
            from telegram import ReplyKeyboardMarkup
            providers = list_ai_providers()
            if not providers:
                await msg.reply_text("📋 هیچ پروایدری ثبت نشده است.", reply_markup=_admin_ai_kb())
            else:
                _user_states[uid] = "wait_ai_del_select"
                kb_rows = [[p["name"]] for p in providers] + [["🔙 بازگشت"]]
                await msg.reply_text("🗑 کدام پروایدر حذف شود؟", reply_markup=ReplyKeyboardMarkup(kb_rows, resize_keyboard=True))
            return True

        if text == "🔁 بررسی یک پروایدر":
            from telegram import ReplyKeyboardMarkup
            providers = list_ai_providers()
            if not providers:
                await msg.reply_text("📋 هیچ پروایدری ثبت نشده است.", reply_markup=_admin_ai_kb())
            else:
                _user_states[uid] = "wait_ai_check_select"
                kb_rows = [[p["name"]] for p in providers] + [["🔙 بازگشت"]]
                await msg.reply_text("🔁 کدام پروایدر بررسی شود؟", reply_markup=ReplyKeyboardMarkup(kb_rows, resize_keyboard=True))
            return True

        if text == "🔄 بررسی همه":
            await _ai_cmd_check_all(msg)
            return True

        if text == "🔄 بروزرسانی هوشمند مدل‌ها":
            await _ai_cmd_smart_refresh(msg)
            return True

        if text == "📊 گزارش وضعیت":
            await _ai_cmd_status_report(msg)
            return True

        if text == "💬 تست گفتگو":
            from telegram import ReplyKeyboardMarkup
            _user_states[uid] = "wait_ai_try_prompt"
            await msg.reply_text(
                "💬 متن پرامپت خود را برای تست هوش مصنوعی ارسال کنید:",
                reply_markup=ReplyKeyboardMarkup([["🔙 بازگشت"]], resize_keyboard=True),
            )
            return True

        if text == "🌐 مدیریت پروکسی Gemini":
            _user_states[uid] = "in_proxy_menu"
            await _show_proxy_panel(msg)
            return True

        if text == "📊 وضعیت پروکسی":
            await _show_proxy_panel(msg)
            return True

        if text == "🔄 تغییر حالت اتصال":
            from telegram import InlineKeyboardButton, InlineKeyboardMarkup
            kb = InlineKeyboardMarkup([
                [InlineKeyboardButton("⚡ فوری — ورکر کلودفلر (بدون پروکسی)", callback_data="prx_mode|worker")],
                [InlineKeyboardButton("🟢 خودکار (auto)", callback_data="prx_mode|auto")],
                [InlineKeyboardButton("🟡 دستی (manual)", callback_data="prx_mode|manual")],
                [InlineKeyboardButton("⚪️ مستقیم (direct)", callback_data="prx_mode|direct")],
            ])
            await msg.reply_text("🔄 حالت اتصال پروکسی را انتخاب کنید:", reply_markup=kb)
            return True

        if text == "📥 دریافت پروکسی از منبع":
            await msg.reply_text("⏳ در حال دریافت و تست پروکسی‌ها از منبع…")
            working, rep = await refresh_from_source()
            await msg.reply_text(format_test_report(rep, "دریافت‌شده"), reply_markup=_admin_proxy_kb())
            return True

        if text == "🧪 تست پروکسی‌های سالم":
            await msg.reply_text("⏳ در حال تست مجدد پروکسی‌های سالم…")
            working, rep = await revalidate()
            await msg.reply_text(format_test_report(rep, "بررسی‌شده"), reply_markup=_admin_proxy_kb())
            return True

        if text == "➕ افزودن پروکسی دستی":
            from telegram import ReplyKeyboardMarkup
            _user_states[uid] = "wait_proxy_manual_add"
            await msg.reply_text(
                "➕ لیست پروکسی‌های دستی خود را (هر کدام در یک خط، مثلاً `socks5://ip:port` یا `http://ip:port`) ارسال کنید:",
                reply_markup=ReplyKeyboardMarkup([["🔙 بازگشت"]], resize_keyboard=True),
            )
            return True

        if text == "🗑 پاک کردن دستی‌ها":
            from telegram import InlineKeyboardButton, InlineKeyboardMarkup
            kb = InlineKeyboardMarkup([
                [InlineKeyboardButton("✅ بله، پاک کن", callback_data="prx_clearok"),
                 InlineKeyboardButton("❌ انصراف", callback_data="prx_cancel")]
            ])
            await msg.reply_text("⚠️ آیا از پاک کردن تمام پروکسی‌های دستی اطمینان دارید؟", reply_markup=kb)
            return True

        if text == "🔗 تنظیم URL منبع":
            from telegram import ReplyKeyboardMarkup
            _user_states[uid] = "wait_proxy_source_url"
            await msg.reply_text(
                "🔗 آدرس اینترنتی (URL) جدید منبع پروکسی را ارسال کنید\n(یا کلمه `پیش‌فرض` را بفرستید):",
                reply_markup=ReplyKeyboardMarkup([["🔙 بازگشت"]], resize_keyboard=True),
            )
            return True

        return False

    async def _send_user_status_message(context, order_id, text_msg, kb=None):
        """ارسال پیام وضعیت با دکمه‌های اینلاین به کاربر صاحب درخواست."""
        try:
            with get_giso_db_conn() as conn:
                order_row = conn.execute("SELECT phone FROM hair_orders WHERE id=?", (order_id,)).fetchone()
                if not order_row or not order_row["phone"]:
                    return
                np = normalize_phone(order_row["phone"])
            # ─── اعلان پنل کاربر در سایت (مستقل از بله؛ idempotent بر اساس متن+ترتیب روزانه) ───
            try:
                import hashlib as _h_sm
                from giso.panel.modules.notifications import log_user_notification as _logu
                _msg_key = int(_h_sm.sha1(f"{order_id}|{text_msg}".encode("utf-8")).hexdigest()[:12], 16)
                _logu(np, "hair_status", "به‌روزرسانی درخواست فروش مو",
                      text_msg, source_type=f"hair_notify:{order_id}:{_msg_key}",
                      source_id=int(order_id or 0), category="hair_sale")
            except Exception as _e_sm:
                logger.debug("user panel hair status mirror failed: %s", _e_sm)
            with get_giso_db_conn() as conn:
                user_row = conn.execute("SELECT bale_id FROM giso_users WHERE phone=?", (np,)).fetchone()
                if not (user_row and user_row["bale_id"] and str(user_row["bale_id"]).isdigit()):
                    return
                cid = int(user_row["bale_id"])
        except Exception as e:
            logger.debug("status msg lookup err: %s", e)
            return
        try:
            if context and hasattr(context, "bot"):
                if kb is not None:
                    asyncio.create_task(context.bot.send_message(chat_id=cid, text=text_msg, reply_markup=kb))
                else:
                    asyncio.create_task(context.bot.send_message(chat_id=cid, text=text_msg))
        except Exception as e:
            logger.debug("status msg send err: %s", e)

    # ═══ پنل کاربر: آنالیز هوشمند (پیگیری، نه تحلیل جدید) ═══
    async def _analysis_menu_payload(phone):
        info = _check_site_user_info(phone)
        if not info['has_account']:
            return None, (
                "📱 هنوز در سایت گیسو حساب کاربری نداری.\n\n"
                f"🌐 برای شروع تحلیل، وارد این آدرس شو:\n"
                f"{_get_giso_site_url()}/analysis\n\n"
                "بعد از تحلیل، برگرد اینجا تا نتیجه رو دنبال کنی. 🌸"
            )
        if info['analyses_count'] == 0:
            return None, (
                f"🌸 {info['name']} عزیز!\n\n"
                "هنوز تحلیلی انجام ندادی.\n\n"
                f"🌐 برای شروع، وارد سایت شو:\n{_get_giso_site_url()}/analysis"
            )

        keyboard = [
            [InlineKeyboardButton("📋 آنالیزهای من", callback_data="analysis_list")],
        ]
        if info['has_active_checklist']:
            keyboard.append([
                InlineKeyboardButton("✅ چک‌لیست پیشرفت من", callback_data="analysis_checklist")
            ])
        keyboard.extend([
            [InlineKeyboardButton("📚 برنامه آنالیز من", url=f"{_get_giso_site_url()}/dashboard/analyses")],
            [InlineKeyboardButton("💬 گفتگوهای مشاوره", url=f"{_get_giso_site_url()}/dashboard/chats")],
            [InlineKeyboardButton("✨ همراه هوشمند", callback_data="consultant_ai_start")],
            [InlineKeyboardButton("🌐 آنالیز جدید در سایت", url=f"{_get_giso_site_url()}/analysis")],
        ])

        text = (
            f"🔬 *آنالیز هوشمند گیسو*\n\n"
            f"سلام {info['name']} عزیز! 🌸\n\n"
            f"📊 تعداد تحلیل‌های شما: {_fa_num(info['analyses_count'])}\n"
        )
        if info['has_active_checklist']:
            text += "✅ چک‌لیست فعال داری\n"
        text += "\n📱 گزینه مورد نظر رو انتخاب کن:"

        return InlineKeyboardMarkup(keyboard), text

    async def handle_analysis_menu(update, context):
        """منوی آنالیز هوشمند (از پیام متنی)."""
        user_id = str(update.effective_user.id)
        phone = _get_user_phone(user_id)
        if not phone:
            await update.message.reply_text(
                "⚠️ برای دسترسی به آنالیز، ابتدا شماره تماس خود را اشتراک بگذارید."
            )
            return
        kb, text = await _analysis_menu_payload(phone)
        if kb is None:
            await update.message.reply_text(text)
            return
        await update.message.reply_text(text, reply_markup=kb, parse_mode='Markdown')

    async def _analysis_menu_callback(query, phone):
        kb, text = await _analysis_menu_payload(phone)
        if kb is None:
            await query.edit_message_text(text)
            return
        await query.edit_message_text(text, reply_markup=kb, parse_mode='Markdown')

    async def _analysis_list(query, phone):
        """لیست تحلیل‌های کاربر."""
        analyses = _get_user_analyses(phone, limit=10)
        if not analyses:
            await query.edit_message_text(
                "📋 هیچ تحلیلی برای شما ثبت نشده.\n\n"
                f"🌐 برای تحلیل جدید:\n{_get_giso_site_url()}/analysis"
            )
            return

        text = "📋 *آنالیزهای شما:*\n\n"
        keyboard = []
        for a in analyses:
            icon = "💇" if a['type'] == 'hair' else "✨"
            type_fa = "مو" if a['type'] == 'hair' else "پوست"
            date_str = to_shamsi(a.get('created_at'),with_time=False)
            keyboard.append([
                InlineKeyboardButton(
                    f"{icon} تحلیل {type_fa} - {date_str}",
                    callback_data=f"analysis_view_{a['id']}"
                )
            ])
        keyboard.append([
            InlineKeyboardButton("🔙 بازگشت", callback_data="analysis_menu")
        ])
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

    async def _analysis_view(query, phone, analysis_id):
        """نمایش جزئیات یک تحلیل."""
        analysis = _get_analysis_by_id(analysis_id, phone)
        if not analysis:
            await query.edit_message_text("⚠️ تحلیل پیدا نشد.")
            return

        try:
            report = json.loads(analysis.get('ai_report_json') or '{}')
        except Exception:
            report = {}
        if not isinstance(report, dict):
            report = {}

        type_fa = "مو" if analysis['type'] == 'hair' else "پوست"
        icon = "💇" if analysis['type'] == 'hair' else "✨"

        text = (
            f"{icon} *تحلیل {type_fa}*\n\n"
            f"📅 تاریخ: {to_shamsi(analysis.get('created_at'),with_time=False)}\n"
            f"🆔 شماره: #{analysis['id']}\n"
        )
        if report.get('overall_status'):
            text += f"📊 وضعیت کلی: {report['overall_status']}\n"
        if report.get('summary'):
            text += f"\n📝 خلاصه:\n{str(report['summary'])[:200]}\n"

        keyboard = [
            [InlineKeyboardButton(
                "🌐 مشاهده در سایت",
                url=f"{_get_giso_site_url()}/analysis/{analysis['type']}/report?id={analysis['id']}"
            )],
        ]
        if analysis.get('plan_json'):
            keyboard.append([
                InlineKeyboardButton(
                    "📚 مشاهده برنامه کامل",
                    url=f"{_get_giso_site_url()}/analysis/plan?id={analysis['id']}"
                )
            ])
        keyboard.append([
            InlineKeyboardButton("🔙 بازگشت به لیست", callback_data="analysis_list")
        ])
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

    async def _analysis_checklist(query, phone):
        """نمایش چک‌لیست پیشرفت آخرین تحلیل."""
        analysis = _get_latest_analysis_with_plan(phone)
        if not analysis:
            await query.edit_message_text(
                "⚠️ چک‌لیست فعالی برای شما موجود نیست.\n\n"
                f"برای ساخت چک‌لیست، به سایت بروید:\n🌐 {_get_giso_site_url()}/analysis"
            )
            return

        try:
            plan = json.loads(analysis.get('plan_json') or '{}')
        except Exception:
            plan = {}
        if not isinstance(plan, dict):
            plan = {}
        try:
            progress = json.loads(analysis.get('checklist_progress') or '{}')
        except Exception:
            progress = {}
        if not isinstance(progress, dict):
            progress = {}

        # نرمال‌سازی چک‌لیست به لیست تخت
        checklist = []
        cl = plan.get('checklist') or {}
        if isinstance(cl, dict):
            for w in cl.get('weeks', []) or []:
                wn = w.get('week_number', 1) if isinstance(w, dict) else 1
                items = w.get('items', []) if isinstance(w, dict) else []
                for i, txt in enumerate(items or []):
                    checklist.append({'week': wn, 'id': f"w{wn}-{i}", 'text': str(txt)})
        elif isinstance(cl, list):
            for i, item in enumerate(cl or []):
                if isinstance(item, dict):
                    checklist.append({'week': item.get('week', 1), 'id': str(item.get('id', i)),
                                      'text': str(item.get('text', ''))})
                else:
                    checklist.append({'week': 1, 'id': str(i), 'text': str(item)})

        if not checklist:
            await query.edit_message_text("⚠️ چک‌لیستی برای این تحلیل تعریف نشده.")
            return

        total = len(checklist)
        completed = sum(1 for item in checklist if progress.get(str(item['id']), False))
        percentage = int((completed / total * 100)) if total > 0 else 0

        text = (
            f"✅ *چک‌لیست پیشرفت شما*\n\n"
            f"📊 پیشرفت: {_fa_num(completed)} از {_fa_num(total)} ({_fa_num(percentage)}%)\n\n"
            "*آیتم‌ها:*\n"
        )
        for item in checklist[:15]:
            is_done = progress.get(str(item['id']), False)
            icon = "✅" if is_done else "⬜"
            text += f"{icon} {item['text'][:60]}\n"
        if len(checklist) > 15:
            text += f"\n... و {_fa_num(len(checklist) - 15)} آیتم دیگر"

        text += "\n\n💡 برای تیک زدن آیتم‌ها به سایت بروید."

        keyboard = [
            [InlineKeyboardButton("🌐 مدیریت در سایت", url=f"{_get_giso_site_url()}/analysis/plan?id={analysis['id']}")],
            [InlineKeyboardButton("🔙 بازگشت", callback_data="analysis_menu")],
        ]
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

    async def _analysis_consultant(query, phone):
        """شروع گفتگوی واقعی با مشاور صادقی در ربات."""
        analysis = _get_latest_analysis(phone)
        if not analysis:
            await query.edit_message_text("⚠️ برای گفتگو با مشاور، ابتدا باید تحلیل انجام دهید.")
            return

        text = (
            "💬 *گفتگو با مشاور صادقی*\n\n"
            "من گزارش تحلیل‌های شما رو دیدم و آماده کمکم.\n\n"
            "پیام خودت رو بنویس.\n"
            "برای پایان: /end"
        )
        keyboard = [
            [InlineKeyboardButton("❌ پایان گفتگو", callback_data="cons_bot_end")],
            [InlineKeyboardButton("🔙 بازگشت", callback_data="analysis_menu")],
        ]
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

    async def _analysis_products(query, phone):
        """محصولات پیشنهادی بر اساس آخرین تحلیل."""
        analysis = _get_latest_analysis_with_plan(phone)
        if not analysis:
            await query.edit_message_text("⚠️ برای دیدن محصولات پیشنهادی، ابتدا باید تحلیل انجام دهید.")
            return

        text = (
            "🛒 *محصولات پیشنهادی برای شما*\n\n"
            "بر اساس تحلیل شما، مشاور صادقی می‌تونه محصولات مناسب رو معرفی کنه:\n\n"
            "💡 گزینه‌های شما:\n"
        )
        keyboard = [
            [InlineKeyboardButton("💬 مشاور محصول (چت)", url=f"{_get_giso_site_url()}/analysis/plan?id={analysis['id']}")],
            [InlineKeyboardButton("🛒 مشاهده فروشگاه", url=f"{_get_giso_site_url()}/shop")],
            [InlineKeyboardButton("🔙 بازگشت", callback_data="analysis_menu")],
        ]
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

    # ═══ پنل ادمین: مدیریت آنالیز (فقط ادمین) ═══
    async def _admin_ana_menu_payload(uid):
        stats = _get_admin_analysis_stats()

        text = (
            f"🔬 *مدیریت آنالیز - پنل ادمین*\n\n"
            f"📊 *آمار سریع:*\n"
            f"• کل تحلیل‌ها: {_fa_num(stats['total'])}\n"
            f"• امروز: {_fa_num(stats['today'])}\n"
            f"• 💇 مو: {_fa_num(stats['hair_count'])} | ✨ پوست: {_fa_num(stats['skin_count'])}\n"
        )
        if stats['pending_consultants'] > 0:
            text += f"\n🔴 *{_fa_num(stats['pending_consultants'])} درخواست مشاوره جدید!*\n"
        if stats['pending_products'] > 0:
            text += f"🔴 {_fa_num(stats['pending_products'])} محصول درخواستی جدید\n"
        text += "\n📱 گزینه مورد نظر رو انتخاب کن:"

        keyboard = [
            [InlineKeyboardButton("📊 آمار کامل", callback_data="adm_ana_stats")],
            [InlineKeyboardButton("📋 لیست ۱۰ تحلیل آخر", callback_data="adm_ana_list")],
        ]

        cons_btn_text = "💬 درخواست‌های مشاوره"
        if stats['pending_consultants'] > 0:
            cons_btn_text += f" ({_fa_num(stats['pending_consultants'])})"
        keyboard.append([InlineKeyboardButton(cons_btn_text, callback_data="adm_ana_consultants")])

        prod_btn_text = "🛒 محصولات درخواستی"
        if stats['pending_products'] > 0:
            prod_btn_text += f" ({_fa_num(stats['pending_products'])})"
        keyboard.append([InlineKeyboardButton(prod_btn_text, callback_data="adm_ana_products")])

        keyboard.append([
            InlineKeyboardButton("💬 خلاصه گفتگوهای مشاور", callback_data="adm_ana_chats")
        ])

        if _is_super_admin(uid):
            keyboard.append([
                InlineKeyboardButton("⏱ تنظیمات محدودیت زمانی", callback_data="adm_ana_ratelimit")
            ])
        keyboard.append([
            InlineKeyboardButton("🌐 پنل کامل در سایت", url=f"{_get_giso_site_url()}/admin/analyses")
        ])

        return InlineKeyboardMarkup(keyboard), text

    def _admin_has_analysis_access(uid):
        """Admin analysis panel matches the site: superadmin only."""
        return bool(_is_super_admin(uid))

    async def handle_admin_analysis_menu(update, context):
        """منوی مدیریت آنالیز - فقط ادمین (از پیام متنی)."""
        uid = str(update.effective_user.id)
        if not _is_giso_admin(uid) or not _admin_has_analysis_access(uid):
            await update.message.reply_text("⛔ دسترسی ندارید.")
            return
        kb, text = await _admin_ana_menu_payload(uid)
        await update.message.reply_text(text, reply_markup=kb, parse_mode='Markdown')

    async def _admin_ana_menu_callback(query, uid):
        kb, text = await _admin_ana_menu_payload(uid)
        await query.edit_message_text(text, reply_markup=kb, parse_mode='Markdown')

    async def _admin_ana_stats(query, uid):
        stats = _get_admin_analysis_stats()
        text = (
            f"📊 *آمار کامل آنالیز گیسو*\n\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"*تعداد کلی:*\n"
            f"• کل تحلیل‌ها: {_fa_num(stats['total'])}\n"
            f"• 💇 آنالیز مو: {_fa_num(stats['hair_count'])}\n"
            f"• ✨ آنالیز پوست: {_fa_num(stats['skin_count'])}\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"*بازه زمانی:*\n"
            f"• 📅 امروز: {_fa_num(stats['today'])}\n"
            f"• 📆 این هفته: {_fa_num(stats['this_week'])}\n"
            f"• 🗓 این ماه: {_fa_num(stats['this_month'])}\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"*مشاوره و محصول:*\n"
            f"• 💬 درخواست مشاوره: {_fa_num(stats['total_consultants'])} (جدید: {_fa_num(stats['pending_consultants'])})\n"
            f"• 🛒 محصولات درخواستی: {_fa_num(stats['total_products'])} (جدید: {_fa_num(stats['pending_products'])})\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"*نظرات کاربران:*\n"
            f"• ⭐ میانگین امتیاز: {_fa_num(stats['avg_rating'])}\n"
            f"• تعداد نظرات: {_fa_num(stats['total_reviews'])}\n"
        )
        keyboard = [
            [InlineKeyboardButton("🔙 بازگشت", callback_data="adm_ana_menu")]
        ]
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

    async def _admin_ana_list(query, uid):
        analyses = _get_recent_analyses(limit=10)
        if not analyses:
            text = "📋 هنوز تحلیلی ثبت نشده."
        else:
            text = "📋 *۱۰ تحلیل آخر:*\n\n"
            for a in analyses:
                icon = "💇" if a['type'] == 'hair' else "✨"
                date_display = _format_persian_date(a.get('created_at'))
                text += f"{icon} #{a['id']} - *{a['user_name']}*\n"
                text += f"   🔬 {a['topic']}\n"
                if a.get('score'):
                    text += f"   📊 امتیاز: {a['score']}/100\n"
                text += f"   📅 {date_display}\n"
                text += f"   📱 {a['phone']}\n"
                if a.get('review_rating'):
                    stars = '⭐' * int(a['review_rating'])
                    text += f"   {stars}\n"
                text += "\n"
        keyboard = [
            [InlineKeyboardButton("🌐 مشاهده کامل در سایت", url=f"{_get_giso_site_url()}/admin/analyses")],
            [InlineKeyboardButton("🔙 بازگشت", callback_data="adm_ana_menu")]
        ]
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

    async def _admin_ana_consultants(query, uid):
        requests_data = _get_recent_consultant_requests(limit=10)
        if not requests_data:
            text = "💬 هیچ درخواست مشاوره‌ای موجود نیست."
            keyboard = [[InlineKeyboardButton("🔙 بازگشت", callback_data="adm_ana_menu")]]
        else:
            text = "💬 *درخواست‌های مشاوره:*\n\n"
            pending_count = 0
            for r in requests_data:
                status_icon = {
                    'new': '🔴', 'reviewing': '🟡', 'chatting': '💬', 'closed': '✅'
                }.get(r['status'], '⚪')
                if r['status'] in ('new', 'reviewing'):
                    pending_count += 1
            if pending_count > 0:
                text += f"🔔 *{_fa_num(pending_count)} درخواست منتظر پاسخ!*\n\n"
            text += "روی هر درخواست بزن تا جزئیات و پاسخ رو ببینی:"
            keyboard = []
            for r in requests_data:
                status_icon = {
                    'new': '🔴', 'reviewing': '🟡', 'chatting': '💬', 'closed': '✅'
                }.get(r['status'], '⚪')
                keyboard.append([
                    InlineKeyboardButton(
                        f"{status_icon} #{r['id']} - {r['customer_name'][:20]}",
                        callback_data=f"cons_view_{r['id']}"
                    )
                ])
            keyboard.append([InlineKeyboardButton("🔙 بازگشت", callback_data="adm_ana_menu")])
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

    async def _admin_ana_products(query, uid):
        requests_data = _get_recent_product_requests(limit=10)
        if not requests_data:
            text = "🛒 هیچ محصول درخواستی موجود نیست."
            keyboard = [[InlineKeyboardButton("🔙 بازگشت", callback_data="adm_ana_menu")]]
        else:
            text = "🛒 *محصولات درخواستی کاربران:*\n\n"
            text += "روی هر درخواست بزن تا وضعیتش رو تغییر بدی:"
            keyboard = []
            for r in requests_data:
                status_icon = {
                    'pending': '🕐', 'added': '✅', 'rejected': '❌'
                }.get(r.get('status', ''), '🕐')
                keyboard.append([
                    InlineKeyboardButton(
                        f"{status_icon} #{r['id']} - {r['phone']}",
                        callback_data=f"prod_view_{r['id']}"
                    )
                ])
            keyboard.append([InlineKeyboardButton("🔙 بازگشت", callback_data="adm_ana_menu")])
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

    async def _admin_ana_ratelimit(query, uid):
        text = (
            f"⏱ *تنظیمات محدودیت زمانی*\n\n"
            f"از این قابلیت می‌تونی محدودیت زمانی بین تحلیل‌های کاربران رو تنظیم کنی.\n\n"
            f"🌐 مدیریت در سایت:\n"
            f"{_get_giso_site_url()}/admin/config/analysis-ratelimit"
        )
        keyboard = [
            [InlineKeyboardButton("🌐 برو به تنظیمات", url=f"{_get_giso_site_url()}/admin/config/analysis-ratelimit")],
            [InlineKeyboardButton("🔙 بازگشت", callback_data="adm_ana_menu")]
        ]
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

    # ═══ خلاصه گفتگوهای مشاور (ادمین) ═══
    async def _admin_ana_chats(query, uid, filter_type='all'):
        summaries = _get_chat_summaries(filter_type=filter_type, limit=10)
        keyboard = []
        if not summaries:
            text = "💬 خلاصه گفتگویی موجود نیست."
        else:
            filter_label = {
                'today': 'امروز', 'week': 'این هفته', 'month': 'این ماه', 'all': 'همه'
            }.get(filter_type, 'همه')
            text = f"💬 *خلاصه گفتگوهای مشاور:*\n\n"
            text += f"📅 فیلتر: {filter_label}\n"
            text += "━━━━━━━━━━━━━━━━━━━━━━\n\n"
            for s in summaries:
                text += f"👤 *{s['user_name']}*\n"
                text += f"📅 {s['date']}\n"
                text += f"💬 {_fa_num(s['message_count'])} پیام رد و بدل شد\n"
                if s['summary']:
                    text += f"📝 خلاصه:\n{s['summary'][:100]}\n"
                else:
                    text += "📝 خلاصه: هنوز خلاصه‌ای ثبت نشده\n"
                if s['rating']:
                    stars = '⭐' * int(s['rating'])
                    text += f"{stars}\n"
                text += "\n"
                keyboard.append([
                    InlineKeyboardButton(f"👁 مشاهده چت کامل #{s['id']}",
                                         callback_data=f"adm_chat_view_{s['id']}")
                ])

        keyboard.append([
            InlineKeyboardButton("📅 امروز", callback_data="adm_ana_chats_today"),
            InlineKeyboardButton("📆 هفته", callback_data="adm_ana_chats_week"),
        ])
        keyboard.append([
            InlineKeyboardButton("🗓 ماه", callback_data="adm_ana_chats_month"),
            InlineKeyboardButton("📚 همه", callback_data="adm_ana_chats_all"),
        ])
        keyboard.append([InlineKeyboardButton("🔙 بازگشت", callback_data="adm_ana_menu")])
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

    async def _admin_chat_view(query, uid):
        """نمایش گفتگوی کامل مشاور با یک کاربر."""
        try:
            analysis_id = int(query.data.replace("adm_chat_view_", ""))
        except (ValueError, TypeError):
            await query.edit_message_text("⚠️ تحلیل پیدا نشد.")
            return
        import json as _json
        try:
            conn = get_giso_db_conn()
            row = conn.execute(
                "SELECT a.consultant_chat_history, "
                "COALESCE(u.name, w.name, 'کاربر ناشناس') as user_name, "
                "COALESCE(u.phone, w.phone, '') as phone, a.type "
                "FROM analyses a "
                "LEFT JOIN giso_web_auth u ON a.user_id = u.id "
                "LEFT JOIN giso_web_auth w ON a.phone = w.phone "
                "WHERE a.id=?",
                (analysis_id,)
            ).fetchone()
            conn.close()
        except Exception as e:
            logger.error(f"_admin_chat_view: {e}")
            await query.edit_message_text("❌ خطا در دریافت گفتگو")
            return

        if not row or not row[0]:
            text = "💬 گفتگویی برای این تحلیل ثبت نشده."
        else:
            try:
                history = _json.loads(row[0])
            except Exception:
                history = []
            if not isinstance(history, list):
                history = []
            user_name = row[1] or 'کاربر ناشناس'
            phone = row[2] or 'نامشخص'
            analysis_type = 'مو' if row[3] == 'hair' else 'پوست'

            text = f"💬 *گفتگوی کامل با {user_name}*\n"
            text += f"📱 {phone}\n"
            text += f"🔬 تحلیل {analysis_type} #{analysis_id}\n"
            text += "━━━━━━━━━━━━━━━━━━━━\n\n"
            for msg in history[:30]:
                if not isinstance(msg, dict):
                    continue
                role = msg.get('role', 'unknown')
                content = str(msg.get('content', ''))[:200]
                if not content.strip():
                    continue
                if role == 'user':
                    text += f"👤 *کاربر:*\n{content}\n\n"
                else:
                    text += f"👩 *مشاور:*\n{content}\n\n"
            if len(history) > 30:
                text += f"\n⚠️ {len(history) - 30} پیام دیگه (خیلی طولانی)"

        keyboard = [
            [InlineKeyboardButton("🔙 بازگشت", callback_data="adm_ana_chats_all")]
        ]
        # برش امن روی مرز خط + فالبک بدون مارک‌داون (رفع باگ 🟡 آئودیت 1.md)
        if len(text) > 4000:
            cut = text.rfind("\n", 3000, 4000)
            text = text[:cut if cut > 0 else 4000]
        try:
            await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
        except Exception:
            await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))

    # ═══ سیستم پشتیبانی (کاربر ↔ ادمین) ═══
    def _support_menu_payload():
        text = (
            "💬 *پشتیبانی گیسو*\n\n"
            "اگه سوال یا مشکلی داری، پیامت رو بنویس.\n"
            "ادمین در اسرع وقت جواب میده.\n\n"
            "💡 نکته: برای مشاوره درباره محصولات، از "
            "«💬 گفتگو با مشاور» در بخش آنالیز استفاده کن."
        )
        keyboard = [
            [InlineKeyboardButton("✏️ ارسال پیام جدید", callback_data="support_new")],
            [InlineKeyboardButton("📋 تیکت‌های من", callback_data="support_my_tickets")],
        ]
        return text, InlineKeyboardMarkup(keyboard)

    async def handle_support_menu_text(msg):
        text, kb = _support_menu_payload()
        await msg.reply_text(text, reply_markup=kb, parse_mode='Markdown')

    async def handle_support_menu(query):
        text, kb = _support_menu_payload()
        await query.edit_message_text(text, reply_markup=kb, parse_mode='Markdown')

    async def handle_support_new(query, context):
        context.user_data['awaiting_support_message'] = True
        await query.edit_message_text(
            "✏️ پیام خودت رو بنویس...\n\n"
            "برای لغو: /cancel"
        )

    async def handle_support_my_tickets(query):
        user_id = str(query.from_user.id)
        _ensure_support_tickets_table()
        tickets = []
        try:
            conn = get_giso_db_conn()
            rows = conn.execute(
                "SELECT id, message, status, admin_reply, created_at "
                "FROM giso_support_tickets WHERE user_bale_id=? "
                "ORDER BY id DESC LIMIT 10",
                (user_id,)
            ).fetchall()
            conn.close()
            for row in rows:
                tickets.append({
                    'id': row[0], 'message': (row[1] or '')[:80],
                    'status': row[2], 'has_reply': bool(row[3]),
                    'created_at': row[4] or '',
                })
        except Exception as e:
            logger.error(f"handle_support_my_tickets: {e}")

        if not tickets:
            text = "📋 هنوز تیکتی ثبت نکردی."
        else:
            text = "📋 *تیکت‌های شما:*\n\n"
            for t in tickets:
                status_icon = {'new': '🔴', 'reviewing': '🟡',
                               'replied': '✅', 'closed': '⚫'}.get(t['status'], '⚪')
                text += f"{status_icon} #{t['id']}\n"
                text += f"   💬 {t['message']}\n"
                if t['has_reply']:
                    text += f"   ✅ ادمین جواب داده\n"
                text += "\n"

        keyboard = [[InlineKeyboardButton("🔙 بازگشت", callback_data="support_menu")]]
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

    async def handle_support_reply(query, context):
        """شروع پاسخ به تیکت (فقط ادمین)."""
        user_id = str(query.from_user.id)
        if not _is_giso_admin(user_id):
            await query.answer("⛔ فقط ادمین", show_alert=True)
            return
        try:
            ticket_id = int(query.data.replace("sup_reply_", ""))
        except (ValueError, TypeError):
            await query.edit_message_text("⚠️ تیکت پیدا نشد.")
            return
        context.user_data['replying_ticket'] = ticket_id
        await query.message.reply_text(
            f"💬 *پاسخ به تیکت #{ticket_id}*\n\n"
            f"پاسخ خودت رو بنویس.\n"
            f"برای لغو: /cancel",
            parse_mode='Markdown'
        )

    async def handle_support_close(query):
        """بستن تیکت (فقط ادمین)."""
        user_id = str(query.from_user.id)
        if not _is_giso_admin(user_id):
            await query.answer("⛔ فقط ادمین", show_alert=True)
            return
        try:
            ticket_id = int(query.data.replace("sup_close_", ""))
        except (ValueError, TypeError):
            await query.edit_message_text("⚠️ تیکت پیدا نشد.")
            return
        try:
            conn = get_giso_db_conn()
            conn.execute("UPDATE giso_support_tickets SET status='closed' WHERE id=?", (ticket_id,))
            conn.commit()
            conn.close()
            await query.answer("✅ تیکت بسته شد", show_alert=True)
            await query.edit_message_text(query.message.text + "\n\n✅ *بسته شد*", parse_mode='Markdown')
        except Exception as e:
            logger.error(f"handle_support_close: {e}")

    async def _notify_admins_new_ticket(context, ticket_id, user_name, phone, message):
        """اطلاع به ادمین‌ها از تیکت جدید."""
        admin_ids = []
        try:
            conn = get_giso_db_conn()
            rows = conn.execute("SELECT DISTINCT bale_id FROM giso_users WHERE is_admin=1").fetchall()
            conn.close()
            admin_ids = [str(r[0]) for r in rows if r[0]]
        except Exception as e:
            logger.error(f"_notify_admins_new_ticket: {e}")

        text = (
            f"🔔 *تیکت جدید پشتیبانی*\n\n"
            f"🎫 شماره: #{ticket_id}\n"
            f"👤 نام: {user_name}\n"
            f"📱 شماره: {phone or 'ثبت نشده'}\n\n"
            f"💬 پیام:\n{message[:500]}"
        )
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("💬 پاسخ دادن", callback_data=f"sup_reply_{ticket_id}")],
            [InlineKeyboardButton("✅ حل شد", callback_data=f"sup_close_{ticket_id}")],
        ])
        for admin_id in admin_ids:
            if not str(admin_id).isdigit():
                continue
            try:
                await context.bot.send_message(
                    chat_id=int(admin_id), text=text,
                    reply_markup=keyboard, parse_mode='Markdown'
                )
            except Exception as e:
                logger.warning(f"Failed to notify admin {admin_id}: {e}")

    # ═══ درخواست‌های مشاوره تعاملی (ادمین) ═══
    async def handle_consultant_view(query, uid):
        try:
            req_id = int(query.data.replace("cons_view_", ""))
        except (ValueError, TypeError):
            await query.edit_message_text("⚠️ درخواست پیدا نشد.")
            return
        row = None
        try:
            conn = get_giso_db_conn()
            row = conn.execute(
                "SELECT id, customer_name, phone, initial_message, status, created_at, analysis_id "
                "FROM consultant_requests WHERE id=?",
                (req_id,)
            ).fetchone()
            conn.close()
        except Exception as e:
            logger.error(f"handle_consultant_view: {e}")
        if not row:
            await query.edit_message_text("⚠️ درخواست پیدا نشد.")
            return
        text = (
            f"💬 *درخواست مشاوره #{row[0]}*\n\n"
            f"👤 نام: {row[1] or 'نامشخص'}\n"
            f"📱 شماره: {row[2] or 'نامشخص'}\n"
            f"📅 تاریخ: {(row[5] or '').split('T')[0]}\n"
            f"📊 وضعیت: {row[4]}\n\n"
            f"💬 پیام:\n{row[3] or ''}"
        )
        keyboard = [
            [InlineKeyboardButton("💬 پاسخ دادن", callback_data=f"cons_reply_{row[0]}")],
            [InlineKeyboardButton("🟡 در حال بررسی", callback_data=f"cons_review_{row[0]}")],
            [InlineKeyboardButton("✅ بستن", callback_data=f"cons_close_{row[0]}")],
            [InlineKeyboardButton("🔙 بازگشت", callback_data="adm_ana_consultants")],
        ]
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

    async def handle_consultant_reply(query, uid, context):
        try:
            req_id = int(query.data.replace("cons_reply_", ""))
        except (ValueError, TypeError):
            await query.edit_message_text("⚠️ درخواست پیدا نشد.")
            return
        context.user_data['replying_consultant'] = req_id
        await query.message.reply_text(
            f"💬 *پاسخ به درخواست مشاوره #{req_id}*\n\n"
            f"پاسخ خودت رو بنویس.\n"
            f"برای لغو: /cancel",
            parse_mode='Markdown'
        )

    async def handle_consultant_end(query):
        """پایان چت مشاور در ربات (کاربر)."""
        await query.edit_message_text(
            "گفتگو پایان یافت 👋\n\n"
            "هر وقت خواستی برگرد و دوباره از «💬 مشاور هوشمند گیسو» شروع کن."
        )

    # ═══ محصولات درخواستی تعاملی (ادمین) ═══
    async def handle_product_request_view(query, uid):
        try:
            req_id = int(query.data.replace("prod_view_", ""))
        except (ValueError, TypeError):
            await query.edit_message_text("⚠️ درخواست پیدا نشد.")
            return
        row = None
        try:
            conn = get_giso_db_conn()
            row = conn.execute(
                "SELECT id, phone, city, problem_summary, status, created_at "
                "FROM product_requests WHERE id=?",
                (req_id,)
            ).fetchone()
            conn.close()
        except Exception as e:
            logger.error(f"handle_product_request_view: {e}")
        if not row:
            await query.edit_message_text("⚠️ درخواست پیدا نشد.")
            return
        text = (
            f"🛒 *درخواست محصول #{row[0]}*\n\n"
            f"📱 شماره: {row[1] or 'نامشخص'}\n"
            f"📍 شهر: {row[2] or 'نامشخص'}\n"
            f"📊 وضعیت: {row[4]}\n"
            f"📅 تاریخ: {(row[5] or '').split('T')[0]}\n\n"
            f"📝 مشکل:\n{row[3] or ''}"
        )
        keyboard = [
            [InlineKeyboardButton("✅ اضافه شد", callback_data=f"prod_add_{row[0]}"),
             InlineKeyboardButton("❌ نیست", callback_data=f"prod_reject_{row[0]}")],
            [InlineKeyboardButton("🔙 بازگشت", callback_data="adm_ana_products")],
        ]
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

    async def handle_product_request_action(query, uid):
        try:
            parts = query.data.split('_')
            action = parts[1]
            req_id = int(parts[2])
        except (ValueError, IndexError, TypeError):
            await query.answer("⚠️ داده نامعتبر", show_alert=True)
            return
        if action not in ('add', 'reject'):
            return
        new_status = 'added' if action == 'add' else 'rejected'
        try:
            conn = get_giso_db_conn()
            conn.execute("UPDATE product_requests SET status=? WHERE id=?", (new_status, req_id))
            conn.commit()
            conn.close()
        except Exception as e:
            logger.error(f"product action: {e}")
            await query.answer("❌ خطا در ذخیره", show_alert=True)
            return
        status_text = '✅ اضافه شد' if action == 'add' else '❌ در دسترس نیست'
        await query.answer(status_text, show_alert=True)
        try:
            await query.edit_message_text(query.message.text + f"\n\n{status_text}", parse_mode='Markdown')
        except Exception:
            pass

    # ═══ تنظیم آدرس سایت گیسو (فقط سوپرادمین) ═══
    def _giso_url_menu_text():
        current_url = _get_giso_site_url()
        return (
            f"🌐 *تنظیم آدرس سایت گیسو*\n\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"📍 آدرس فعلی: `{current_url}`\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"از این آدرس برای همه لینک‌های سایت در ربات استفاده می‌شود.\n\n"
            f"💡 نکته:\n"
            f"• برای localhost: http://192.168.1.101:5001\n"
            f"• برای دامنه: https://giso.sadeghiai.ir"
        )

    def _giso_url_menu_kb():
        return InlineKeyboardMarkup([
            [InlineKeyboardButton("✏️ تغییر آدرس", callback_data="giso_url_change")],
            [InlineKeyboardButton("🔄 تست آدرس", callback_data="giso_url_test")],
            [InlineKeyboardButton("↩️ بازگشت به پیش‌فرض", callback_data="giso_url_reset")],
        ])

    async def handle_giso_site_url_menu(update, context):
        """منوی تنظیم آدرس سایت گیسو - فقط سوپرادمین."""
        uid = str(update.effective_user.id)
        if not _is_super_admin(uid):
            await update.message.reply_text("⛔ فقط سوپرادمین")
            return
        await update.message.reply_text(
            _giso_url_menu_text(),
            reply_markup=_giso_url_menu_kb(),
            parse_mode='Markdown',
        )

    async def _giso_url_menu_callback(query, uid):
        await query.edit_message_text(
            _giso_url_menu_text(),
            reply_markup=_giso_url_menu_kb(),
            parse_mode='Markdown',
        )

    async def _giso_url_change(query, uid):
        context_user = None
        # برای دریافت آدرس در handle_text باید از context.user_data استفاده شود؛
        # در اینجا فقط پیام درخواست را نشان می‌دهیم و state در handle_text چک می‌شود.
        await query.edit_message_text(
            "✏️ *تغییر آدرس سایت گیسو*\n\n"
            "لطفاً آدرس جدید رو وارد کن.\n\n"
            "مثال‌ها:\n"
            "• https://giso.sadeghiai.ir\n"
            "• http://192.168.1.101:5001\n"
            "• https://giso.mydomain.com\n\n"
            "⚠️ باید با http:// یا https:// شروع بشه\n"
            "⚠️ اگه می‌خوای لغو کنی، /cancel بزن",
            parse_mode='Markdown',
        )

    async def _giso_url_test(query, uid):
        current_url = _get_giso_site_url()
        await query.edit_message_text(f"🔄 در حال تست... `{current_url}`", parse_mode='Markdown')
        result = await _to_thread(_test_giso_site_url, current_url)
        if result['success']:
            text = (
                f"✅ *سایت در دسترس است*\n\n"
                f"📍 آدرس: {current_url}\n"
                f"📊 کد پاسخ: {result['status_code']}\n"
                f"⏱ زمان پاسخ: {result['time_ms']}ms\n\n"
                f"همه چیز درسته! 🌸"
            )
        else:
            text = (
                f"❌ *سایت در دسترس نیست*\n\n"
                f"📍 آدرس: {current_url}\n"
                f"⚠️ {result['message']}\n\n"
                f"لطفاً آدرس رو بررسی کن یا تغییر بده."
            )
        await query.edit_message_text(
            text,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 بازگشت", callback_data="giso_url_menu")]
            ]),
            parse_mode='Markdown',
        )

    async def _giso_url_reset(query, uid):
        success, message = _set_giso_site_url(DEFAULT_SITE_BASE_URL)
        if success:
            text = (
                f"✅ *آدرس به پیش‌فرض بازگشت*\n\n"
                f"📍 آدرس جدید: `{DEFAULT_SITE_BASE_URL}`\n\n"
                f"همه لینک‌های ربات از این آدرس استفاده می‌کنن."
            )
        else:
            text = f"❌ خطا: {message}"
        await query.edit_message_text(
            text,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 بازگشت", callback_data="giso_url_menu")]
            ]),
            parse_mode='Markdown',
        )

    # ═══ سیستم پشتیبان‌گیری دیتابیس (فقط سوپرادمین) ═══
    def _restart_menu_kb():
        return InlineKeyboardMarkup([
            [InlineKeyboardButton("⏱ ۵ ثانیه", callback_data="restart_confirm_5"),
             InlineKeyboardButton("⏱ ۱۰ ثانیه", callback_data="restart_confirm_10")],
            [InlineKeyboardButton("⏱ ۳۰ ثانیه", callback_data="restart_confirm_30"),
             InlineKeyboardButton("⏱ ۶۰ ثانیه", callback_data="restart_confirm_60")],
            [InlineKeyboardButton("❌ لغو", callback_data="restart_cancel")],
        ])

    async def handle_restart_menu(query, context):
        """نمایش منوی انتخاب تایمر ریستارت (فقط سوپرادمین)."""
        uid = str(query.from_user.id)
        if not _is_super_admin(uid):
            return
        try:
            await query.answer()
        except Exception:
            pass
        try:
            await query.edit_message_text(
                "🔄 *ریستارت ربات گیسو*\n\n"
                "پس از چه مدت ربات ریستارت شود؟\n\n"
                "⚠️ به کاربران فعال پیام داده می‌شود.",
                reply_markup=_restart_menu_kb(),
                parse_mode='Markdown',
            )
        except Exception:
            pass

    async def _notify_giso_active_users(context, seconds):
        """پیام به کاربران فعال (۱ ساعت اخیر) درباره ریستارت."""
        try:
            from giso.base import get_giso_db_conn
            from datetime import datetime, timedelta
            since = (datetime.now() - timedelta(hours=1)).strftime('%Y-%m-%d %H:%M:%S')
            conn = get_giso_db_conn()
            rows = conn.execute(
                "SELECT bale_id FROM giso_users WHERE last_active >= ? AND contact_shared=1",
                (since,)
            ).fetchall()
            conn.close()
            msg = f"⚠️ ربات تا {seconds} ثانیه دیگر ریستارت خواهد شد.\nلطفاً چند لحظه صبر کنید..."
            for r in rows:
                bid = str(r["bale_id"] or "")
                if not bid.isdigit():
                    continue
                try:
                    await context.bot.send_message(chat_id=int(bid), text=msg)
                except Exception:
                    continue
        except Exception as e:
            logger.debug(f"_notify_giso_active_users: {e}")

    async def handle_restart_confirm(query, context):
        """شروع شمارش معکوس و ریستارت (فقط سوپرادمین)."""
        uid = str(query.from_user.id)
        if not _is_super_admin(uid):
            return
        try:
            seconds = int(query.data.replace("restart_confirm_", ""))
        except (ValueError, TypeError):
            await query.edit_message_text("⚠️ مقدار نامعتبر.")
            return
        try:
            await query.answer()
        except Exception:
            pass
        # ارسال پیام به کاربران فعال + ویرایش شمارش معکوس
        try:
            await _notify_giso_active_users(context, seconds)
        except Exception:
            pass
        await query.edit_message_text(
            f"⚠️ ریستارت ربات گیسو تا {seconds} ثانیه دیگر...",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("❌ لغو", callback_data="restart_cancel")]
            ]),
        )
        # شمارش معکوس (هر ۲ ثانیه یک ویرایش برای جلوگیری از rate limit)
        remaining = seconds
        while remaining > 0:
            await asyncio.sleep(min(2, remaining))
            remaining = max(0, remaining - 2)
            try:
                await query.edit_message_text(
                    f"⚠️ ریستارت ربات گیسو تا {remaining} ثانیه دیگر...",
                    reply_markup=InlineKeyboardMarkup([
                        [InlineKeyboardButton("❌ لغو", callback_data="restart_cancel")]
                    ]),
                )
            except Exception:
                break
        try:
            await query.edit_message_text("✅ ربات در حال ریستارت است...")
        except Exception:
            pass
        # checkpoint نهایی + ریستارت
        _restart_giso_process()

    async def handle_restart_cancel(query, context):
        try:
            await query.answer("لغو شد.", show_alert=True)
        except Exception:
            pass
        try:
            await query.edit_message_text("❌ ریستارت لغو شد.")
        except Exception:
            pass

    async def handle_backup_menu(update, context):
        """منوی پشتیبان‌گیری (فقط سوپرادمین)."""
        uid = str(update.effective_user.id)
        if not _is_super_admin(uid):
            await update.message.reply_text("⛔ فقط سوپرادمین")
            return
        text = await _backup_menu_text()
        keyboard = await _backup_menu_kb()
        await update.message.reply_text(
            text,
            reply_markup=keyboard,
            parse_mode='Markdown',
        )

    async def _backup_menu_text():
        backup_files = _list_backup_files()
        interval = _get_backup_interval_hours()
        text = "💾 *پشتیبان‌گیری دیتابیس*\n\n"
        text += f"📁 تعداد backup: {_fa_num(len(backup_files))}\n"
        if backup_files:
            text += f"📅 آخرین: {backup_files[0]}\n"
        if interval > 0:
            text += f"\n⏱ backup خودکار: هر {_fa_num(interval)} ساعت ✅\n"
        else:
            text += "\n⏱ backup خودکار: غیرفعال ❌\n"
        return text

    async def _backup_menu_kb():
        return InlineKeyboardMarkup([
            [InlineKeyboardButton("💾 گرفتن backup الان", callback_data="backup_now")],
            [InlineKeyboardButton("⏱ تنظیم زمان backup خودکار", callback_data="backup_set_interval")],
            [InlineKeyboardButton("📥 بارگذاری backup", callback_data="backup_upload")],
            [InlineKeyboardButton("📋 لیست backup ها", callback_data="backup_list")],
            [InlineKeyboardButton("🔙 بازگشت", callback_data="back_settings")],
        ])

    async def handle_backup_now(query, context):
        """گرفتن backup فوری و ارسال document به سوپرادمین."""
        uid = str(query.from_user.id)
        if not _is_super_admin(uid):
            return
        try:
            await query.answer("در حال تهیه backup...")
        except Exception:
            pass
        import shutil
        from datetime import datetime
        from giso.base import checkpoint_giso_db

        # ═══ قبل از کپی، checkpoint بزن (انتقال WAL به DB) ═══
        checkpoint_giso_db()

        db_path = os.path.join(os.path.dirname(__file__), "data", "giso.db")
        backup_dir = _backup_dir()
        os.makedirs(backup_dir, exist_ok=True)
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_path = os.path.join(backup_dir, f"giso_backup_{timestamp}.db")

        try:
            shutil.copy2(db_path, backup_path)
            size_kb = os.path.getsize(backup_path) // 1024
            # ارسال document به سوپرادمین
            sent = False
            try:
                if context and hasattr(context, "bot"):
                    with open(backup_path, "rb") as f:
                        await context.bot.send_document(
                            chat_id=int(uid),
                            document=f,
                            filename=f"giso_backup_{timestamp}.db",
                            caption=f"✅ backup گرفته شد\n📅 {timestamp}\n📦 اندازه: {_fa_num(size_kb)} KB",
                        )
                    sent = True
            except Exception as e:
                logger.error(f"backup send_document error: {e}")
            if not sent:
                try:
                    await query.message.reply_text(
                        f"✅ backup گرفته شد (ارسال فایل ممکن نشد)\n📅 {timestamp}"
                    )
                except Exception:
                    pass
            # حذف backup های قدیمی (نگه داشتن N آخر)
            all_backups = sorted(
                [x for x in os.listdir(backup_dir)
                 if x.startswith("giso_backup_") and x.endswith(".db")]
            )
            max_files = _backup_max_files()
            while len(all_backups) > max_files:
                os.remove(os.path.join(backup_dir, all_backups.pop(0)))
        except Exception as e:
            logger.error(f"backup_now error: {e}")
            try:
                await query.message.reply_text(f"❌ خطا: {str(e)[:100]}")
            except Exception:
                pass

    async def handle_backup_upload(query, context):
        """منوی بازگردانی: انتخاب روش (دستی / لیست بکاپ‌ها) — فقط سوپرادمین."""
        uid = str(query.from_user.id)
        if not _is_super_admin(uid):
            return
        try:
            await query.answer()
        except Exception:
            pass
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("📤 ارسال فایل دستی", callback_data="backup_restore_manual")],
            [InlineKeyboardButton("📋 انتخاب از لیست بکاپ‌ها", callback_data="backup_restore_list")],
            [InlineKeyboardButton("🔙 بازگشت", callback_data="backup_menu")],
        ])
        try:
            await query.edit_message_text(
                "📥 *بازگردانی دیتابیس گیسو*\n\n"
                "روش بازگردانی را انتخاب کن:",
                reply_markup=keyboard,
                parse_mode='Markdown',
            )
        except Exception:
            pass

    async def handle_restore_manual(query, context):
        """شروع بازگردانی دستی (انتظار فایل document)."""
        uid = str(query.from_user.id)
        if not _is_super_admin(uid):
            return
        try:
            await query.answer()
        except Exception:
            pass
        _ud = getattr(context, "user_data", None)
        if isinstance(_ud, dict):
            _ud["awaiting_backup_file"] = True
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 بازگشت", callback_data="backup_menu")],
        ])
        try:
            await query.edit_message_text(
                "📤 *ارسال فایل بکاپ*\n\n"
                "فایل بکاپ (.db) را به عنوان document ارسال کن.\n\n"
                "⚠️ **هشدار:** همه اطلاعات فعلی جایگزین می‌شوند!\n\n"
                "برای لغو: /cancel",
                reply_markup=keyboard,
                parse_mode='Markdown'
            )
        except Exception:
            pass

    async def handle_restore_list(query, context):
        """لیست بکاپ‌های ذخیره‌شده گیسو برای انتخاب بازگردانی."""
        uid = str(query.from_user.id)
        if not _is_super_admin(uid):
            return
        try:
            await query.answer()
        except Exception:
            pass
        files = _list_backup_files_detail('giso')
        # حذف فایل‌های pre_restore از لیست قابل بازگردانی
        files = [f for f in files if 'pre_restore' not in f['name']]
        if not files:
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 بازگشت", callback_data="backup_menu")],
            ])
            try:
                await query.edit_message_text("📋 بکاپی برای بازگردانی یافت نشد.", reply_markup=keyboard)
            except Exception:
                pass
            return
        rows = []
        for i, f in enumerate(files[:10]):
            size_kb = f['size'] // 1024
            rows.append([InlineKeyboardButton(
                f"📄 {f['name']} ({_fa_num(size_kb)}KB)",
                callback_data=f"giso_restore_pick_{i}"
            )])
        rows.append([InlineKeyboardButton("🔙 بازگشت", callback_data="backup_menu")])
        try:
            await query.edit_message_text(
                "📋 *بکاپ‌های ذخیره‌شده:*\n\nروی فایل مورد نظر کلیک کن:",
                reply_markup=InlineKeyboardMarkup(rows),
                parse_mode='Markdown',
            )
        except Exception:
            pass

    async def handle_restore_pick(query, context):
        """نمایش تأیید نهایی قبل از بازگردانی از لیست."""
        uid = str(query.from_user.id)
        if not _is_super_admin(uid):
            return
        try:
            await query.answer()
        except Exception:
            pass
        try:
            idx = int(query.data.replace("giso_restore_pick_", ""))
        except (ValueError, TypeError):
            await query.edit_message_text("⚠️ مقدار نامعتبر.")
            return
        files = [f for f in _list_backup_files_detail('giso') if 'pre_restore' not in f['name']]
        if idx >= len(files):
            await query.edit_message_text("⚠️ بکاپ پیدا نشد.")
            return
        f = files[idx]
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("✅ بله، بازگردانی کن", callback_data=f"giso_restore_confirm_{idx}")],
            [InlineKeyboardButton("❌ لغو", callback_data="backup_menu")],
        ])
        await query.edit_message_text(
            f"⚠️ *آیا مطمئنی می‌خواهی از این فایل بازگردانی کنی؟*\n\n📄 `{f['name']}`",
            reply_markup=keyboard,
            parse_mode='Markdown',
        )

    async def handle_restore_confirm(query, context):
        """انجام بازگردانی از فایل انتخابی لیست."""
        uid = str(query.from_user.id)
        if not _is_super_admin(uid):
            return
        try:
            await query.answer()
        except Exception:
            pass
        try:
            idx = int(query.data.replace("giso_restore_confirm_", ""))
        except (ValueError, TypeError):
            await query.edit_message_text("⚠️ مقدار نامعتبر.")
            return
        files = [f for f in _list_backup_files_detail('giso') if 'pre_restore' not in f['name']]
        if idx >= len(files):
            await query.edit_message_text("⚠️ بکاپ پیدا نشد.")
            return
        f = files[idx]
        ok, msg = _giso_restore_from_path(f['path'])
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 بازگشت به منوی backup", callback_data="backup_menu")],
        ])
        await query.edit_message_text(
            ("✅ " if ok else "❌ ") + msg,
            reply_markup=keyboard,
        )

    async def handle_backup_list(query, context):
        """لیست backup ها (فقط سوپرادمین)."""
        uid = str(query.from_user.id)
        if not _is_super_admin(uid):
            return
        try:
            await query.answer()
        except Exception:
            pass
        backup_files = _list_backup_files()
        if not backup_files:
            text = "📋 هنوز backup ای گرفته نشده."
        else:
            lines = ["📋 *لیست backup ها:*\n"]
            for f in backup_files[:10]:
                try:
                    size = os.path.getsize(os.path.join(_backup_dir(), f)) // 1024
                except Exception:
                    size = 0
                lines.append(f"📦 {f}\n   اندازه: {_fa_num(size)} KB")
            text = "\n".join(lines)
        keyboard = [
            [InlineKeyboardButton("🔙 بازگشت", callback_data="back_settings")]
        ]
        try:
            await query.edit_message_text(
                text,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode='Markdown',
            )
        except Exception:
            pass

    async def handle_backup_back(query):
        try:
            await query.edit_message_text(
                await _backup_menu_text(),
                reply_markup=await _backup_menu_kb(),
                parse_mode='Markdown',
            )
        except Exception:
            pass

    async def handle_backup_set_interval(query, context):
        """نمایش گزینه‌های تنظیم زمان backup خودکار (فقط سوپرادمین)."""
        uid = str(query.from_user.id)
        if not _is_super_admin(uid):
            return
        try:
            await query.answer()
        except Exception:
            pass
        keyboard = [
            [
                InlineKeyboardButton("هر ۱ ساعت", callback_data="backup_interval_1"),
                InlineKeyboardButton("هر ۳ ساعت", callback_data="backup_interval_3"),
            ],
            [
                InlineKeyboardButton("هر ۶ ساعت", callback_data="backup_interval_6"),
                InlineKeyboardButton("هر ۱۲ ساعت", callback_data="backup_interval_12"),
            ],
            [
                InlineKeyboardButton("هر ۲۴ ساعت", callback_data="backup_interval_24"),
                InlineKeyboardButton("❌ غیرفعال", callback_data="backup_interval_0"),
            ],
            [InlineKeyboardButton("🔙 بازگشت", callback_data="backup_menu")],
        ]
        try:
            await query.edit_message_text(
                "⏱ *تنظیم backup خودکار*\n\n"
                "هر چند ساعت backup بگیرم?\n\n"
                "💡 هر backup شامل:\n"
                "• checkpoint (انتقال WAL به DB)\n"
                "• کپی کامل دیتابیس\n"
                "• حذف backup های قدیمی (نگهداری ۵ آخر)",
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode='Markdown',
            )
        except Exception:
            pass

    async def handle_backup_interval_set(query, context):
        """ذخیره تنظیم زمان backup خودکار (فقط سوپرادمین)."""
        uid = str(query.from_user.id)
        if not _is_super_admin(uid):
            return
        try:
            await query.answer()
        except Exception:
            pass
        try:
            hours = int(query.data.replace("backup_interval_", ""))
        except (ValueError, TypeError):
            await query.edit_message_text("⚠️ مقدار نامعتبر.")
            return

        if not _set_backup_interval_hours(hours):
            await query.edit_message_text("❌ خطا در ذخیره تنظیم.")
            return

        if hours == 0:
            _stop_backup_timer(context)
            text = "❌ backup خودکار **غیرفعال** شد."
        else:
            _start_backup_timer(context, hours)
            text = f"✅ backup خودکار تنظیم شد: **هر {_fa_num(hours)} ساعت**"

        keyboard = [
            [InlineKeyboardButton("🔙 بازگشت به منوی backup", callback_data="backup_menu")]
        ]
        try:
            await query.edit_message_text(
                text,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode='Markdown',
            )
        except Exception:
            pass

    async def handle_private_photo(update, context):
        """عکس ارسالی در چت خصوصی — مخصوص «تعویض عکس» محصول منتظر تأیید (ادمین‌های فروشگاه)."""
        msg = update.message
        if not msg:
            return
        uid = update.effective_user.id if update.effective_user else None
        if not uid:
            return
        try:
            if await handle_shop_bot_photo(msg, uid, context):
                return
        except Exception as e:
            logger.warning(f"private photo handling failed: {e}", exc_info=True)

    async def handle_document(update, context):
        """دریافت فایل backup (فقط سوپرادمین در حالت awaiting_backup_file)."""
        _ud = getattr(context, "user_data", None)
        if not (isinstance(_ud, dict) and _ud.get("awaiting_backup_file")):
            return
        uid = str(update.effective_user.id)
        if not _is_super_admin(uid):
            try:
                _ud.pop("awaiting_backup_file", None)
            except Exception:
                pass
            return
        document = update.message.document
        if not document or not document.file_name:
            await update.message.reply_text("⚠️ فایل ارسال نشد.")
            return
        if not document.file_name.endswith(".db"):
            await update.message.reply_text("⚠️ فقط فایل .db قبول می‌شود.")
            return
        try:
            _ud.pop("awaiting_backup_file", None)
        except Exception:
            pass
        import tempfile
        from datetime import datetime

        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        tmp_path = os.path.join(tempfile.gettempdir(), f"giso_restore_upload_{timestamp}.db")

        try:
            # دانلود به فایل موقت با timeout بزرگ + retry (رفع باگ Timed out)
            last_err = None
            for attempt in range(1, 4):
                try:
                    file = await document.get_file(
                        read_timeout=120, write_timeout=120, connect_timeout=60)
                    await file.download_to_drive(
                        custom_path=tmp_path, read_timeout=120, write_timeout=120)
                    last_err = None
                    break
                except Exception as e:
                    last_err = e
                    logger.error(f"restore download attempt {attempt}/3 failed: {e}")
                    if attempt < 3:
                        await asyncio.sleep(1)
            if last_err:
                raise last_err

            # بازگردانی از فایل موقت (checkpoint + safety + integrity + rollback)
            ok, msg = _giso_restore_from_path(tmp_path)
            await update.message.reply_text(
                ("✅ " if ok else "❌ ") + msg,
            )
        except Exception as e:
            logger.error(f"restore backup error: {e}")
            await update.message.reply_text(
                f"❌ خطا: {str(e)[:100]}\nدیتابیس قبلی بازگردانی شد."
            )
        finally:
            try:
                if os.path.exists(tmp_path):
                    os.remove(tmp_path)
            except Exception:
                pass

    async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        if not query:
            return
        user = update.effective_user
        uid = user.id if user else 0
        # فیکس نشت حافظه: ثبت تعامل + هرس دوره‌ای state (هیچ هندلری تغییر نمی‌کند)
        _touch_state_activity(uid)
        _maybe_cleanup_stale_states()
        user_rec = _get_giso_user(uid)
        phone = user_rec.get("phone", "") if user_rec else ""
        data = query.data or ""
        # 🆕 تأیید/رد محصول‌های واردشده از کانال فروشگاه (channel_importer)
        # ═══ فاز B: callback های فروشگاه (نام‌فضای shop_) ═══
        if await handle_shop_bot_callback(query, uid, phone, context):
            return

        # ⚡ عملیات سریع کاربر (نام‌فضای اختصاصی «ua|») — ماژول مستقل bot_user_actions.
        # بعد از همه‌ی هندلرهای موجود و فقط برای پیشوند خودش فعال می‌شود تا چیزی نشکند.
        if await _uact.handle_ua_callback(query, phone, data):
            return

        if data.startswith("upro|"):
            try:
                await query.answer()
            except Exception:
                pass
            parts = data.split("|")
            action = parts[1] if len(parts) > 1 else "show"
            field = parts[2] if len(parts) > 2 else ""
            from giso.user_profile_service import PROFILE_FIELDS, get_user_profile, update_user_profile
            bot_editable_fields = _BOT_EDITABLE_FIELDS
            if action == "home":
                _user_states.pop(uid, None)
                context.user_data.pop("profile_pending", None)
                await query.message.reply_text("به منوی اصلی برگشتی.", reply_markup=_user_kb())
                return
            if action == "edit" and field in bot_editable_fields:
                # اگر اطلاعات در سایت ویرایش شده، ویرایش در ربات قفل است.
                try:
                    from giso.user_profile_service import is_bot_profile_edit_locked
                    _locked = is_bot_profile_edit_locked(phone)
                except Exception:
                    _locked = False
                if _locked:
                    await query.message.reply_text(
                        "🔒 ویرایش پروفایل تا ۱۵ روز دیگر قفل است؛ برای تغییر اطلاعات با پشتیبانی گیسو هماهنگ کن.",
                        reply_markup=_user_kb(),
                    )
                    return
                profile = get_user_profile(phone)
                label = PROFILE_FIELDS[field][0]
                current_value = profile.get(field) or "ثبت نشده"
                _user_states[uid] = f"user_profile_edit|{field}"
                context.user_data.pop("profile_pending", None)
                await query.message.reply_text(
                    f"✏️ ویرایش {label}\nمقدار فعلی: {str(current_value).replace(chr(60), chr(8249)).replace(chr(62), chr(8250))}\n\nمقدار جدید را ارسال کنید یا /cancel بزنید.",
                )
                return
            if action == "save" and field in bot_editable_fields:
                pending = context.user_data.get("profile_pending") or {}
                if pending.get("field") != field:
                    await query.message.reply_text("⚠️ درخواست ویرایش منقضی شده است؛ دوباره از پروفایل انتخاب کنید.")
                    return
                ok, message, _profile = update_user_profile(phone, {field: pending.get("value", "")}, actor="bot")
                context.user_data.pop("profile_pending", None)
                _user_states.pop(uid, None)
                await query.message.reply_text(("✅ " if ok else "❌ ") + message)
                await _show_user_profile(query.message, phone)
                return
            if action == "cancel":
                context.user_data.pop("profile_pending", None)
                _user_states.pop(uid, None)
                await query.message.reply_text("ویرایش لغو شد.")
                await _show_user_profile(query.message, phone)
                return
            await _show_user_profile(query.message, phone)
            return

        if data.startswith("unotif|"):
            try:
                await query.answer()
            except Exception:
                pass
            from giso.panel.modules.notifications import mark_user_notifications_read
            parts = data.split("|")
            action = parts[1] if len(parts) > 1 else "show"
            if action == "read" and len(parts) > 2 and parts[2].isdigit():
                mark_user_notifications_read(phone, int(parts[2]))
            elif action == "all":
                mark_user_notifications_read(phone)
            await _show_user_notifications(query.message, phone)
            return

        if data == "bcowner|show":
            from giso.user_profile_service import get_user_profile
            profile = get_user_profile(phone)
            if not profile:
                await query.answer("ابتدا حساب سایت را با همین شماره متصل کنید.", show_alert=True)
                return
            from giso.beauty_centers.bot_handlers import handle_beauty_owner_callback
            await handle_beauty_owner_callback(
                query, int(profile.get("id") or 0),
                _get_giso_site_url() or "https://gisosadeghi.ir",
            )
            return

        elif data.startswith("rsv|"):
            return await handle_reservation_bot(update, context)

        if data.startswith("bc_"):
            if not (_is_giso_admin(uid) or _is_super_admin(uid, phone)):
                await query.answer("⛔ فقط ادمین", show_alert=True)
                return
            from giso.beauty_centers.bot_handlers import handle_beauty_admin_callback
            await handle_beauty_admin_callback(
                query, data, _is_super_admin(uid, phone),
                is_admin=_is_giso_admin(uid),
            )
            return

        if data.startswith(("mkt_", "gchat_")):
            if not (_is_giso_admin(uid) or _is_super_admin(uid, phone)):
                await query.answer("⛔ فقط ادمین", show_alert=True)
                return
            try:
                await query.answer()
            except Exception:
                pass
            if data.startswith("mkt_"):
                await handle_market_callback(query, data)
                return
            await handle_gchat_callback(query, data, _user_states)
            return

        if data.startswith(("work_market|", "work_buyer|", "work_report|", "work_review|")):
            if not _is_giso_admin(uid):
                await query.answer("⛔ فقط ادمین", show_alert=True)
                return
            parts = data.split("|")
            if len(parts) != 3:
                await query.answer("⚠️ داده نامعتبر.", show_alert=True)
                return
            scope, action = parts[0], parts[1]
            try:
                item_id = int(parts[2])
            except (TypeError, ValueError):
                await query.answer("⚠️ شناسه نامعتبر.", show_alert=True)
                return
            now = time.strftime("%Y-%m-%d %H:%M:%S")
            updated = False
            user_notice = None
            try:
                with get_giso_db_conn() as conn:
                    if scope == "work_market" and action in ("approve", "reject"):
                        status = "published" if action == "approve" else "rejected"
                        row = conn.execute(
                            "SELECT l.id, u.phone FROM hair_listings l LEFT JOIN giso_web_auth u ON u.id=l.seller_user_id "
                            "WHERE l.id=? AND l.status='pending_review' AND COALESCE(l.deleted_at,'')=''", (item_id,)
                        ).fetchone()
                        if row:
                            if action == "approve":
                                conn.execute(
                                    "UPDATE hair_listings SET status='published', published_at=CASE WHEN COALESCE(published_at,'')='' THEN ? ELSE published_at END, reject_reason='', updated_at=? WHERE id=?",
                                    (now, now, item_id),
                                )
                            else:
                                conn.execute(
                                    "UPDATE hair_listings SET status='rejected', reject_reason='آگهی با قوانین بازارچه مطابقت ندارد.', updated_at=? WHERE id=?",
                                    (now, item_id),
                                )
                            updated = True
                            user_notice = (row["phone"] or "", "listing_status", "وضعیت آگهی بازارچه",
                                           f"وضعیت آگهی #{item_id}: {'تأیید و منتشر شد' if action == 'approve' else 'رد شد'}",
                                           f"marketplace_listing_{status}")
                    elif scope == "work_buyer" and action in ("verify", "reject"):
                        status = "verified" if action == "verify" else "rejected"
                        row = conn.execute(
                            "SELECT b.id, COALESCE(NULLIF(b.request_phone,''),u.phone,b.phone_snapshot) AS phone "
                            "FROM buyer_profiles b LEFT JOIN giso_web_auth u ON u.id=b.user_id "
                            "WHERE b.id=? AND b.verification_status='pending'", (item_id,)
                        ).fetchone()
                        if row:
                            conn.execute(
                                "UPDATE buyer_profiles SET verification_status=?, verified_at=?, updated_at=? WHERE id=?",
                                (status, now if status == "verified" else "", now, item_id),
                            )
                            updated = True
                            user_notice = (row["phone"] or "", "buyer_request_status", "وضعیت درخواست خرید مو",
                                           f"درخواست خرید شما {'تأیید شد' if action == 'verify' else 'رد شد'}.",
                                           f"marketplace_buyer_request_{status}")
                    elif scope == "work_report" and action in ("resolve", "dismiss"):
                        status = "resolved" if action == "resolve" else "dismissed"
                        cur = conn.execute(
                            "UPDATE listing_reports SET status=?, updated_at=? WHERE id=? AND status='open'",
                            (status, now, item_id),
                        )
                        updated = bool(cur.rowcount)
                    elif scope == "work_review" and action in ("approve", "reject"):
                        status = "visible" if action == "approve" else "hidden"
                        cur = conn.execute(
                            "UPDATE reviews SET status=? WHERE id=? AND status!='deleted'", (status, item_id)
                        )
                        updated = bool(cur.rowcount)
                    if updated:
                        conn.commit()
                if user_notice and user_notice[0]:
                    from giso.panel.modules.notifications import log_user_notification
                    log_user_notification(
                        user_notice[0], user_notice[1], user_notice[2], user_notice[3],
                        source_type=user_notice[4], source_id=item_id, category="marketplace",
                    )
            except Exception as exc:
                logger.warning("normal admin inline work action: %s", exc)
            if updated:
                await query.answer("✅ انجام شد")
                try:
                    await query.edit_message_text((query.message.text or "") + "\n\n✅ انجام شد")
                except Exception:
                    pass
            else:
                await query.answer("این مورد قبلاً تعیین تکلیف شده یا در دسترس نیست.", show_alert=True)
            return

        if data.startswith("chimp|"):
            # Old channel cards exposed edit/delete callbacks to every admin.
            # Keep those established controls for superadmin, but fail closed
            # for normal admins (their current cards use restricted shop_pen).
            if _is_giso_admin(uid) and not _is_super_admin(uid, phone):
                await query.answer("⛔ این کارت قدیمی است؛ از اقدام سریع استفاده کنید.", show_alert=True)
                return
            try:
                from giso import channel_importer as _ci
                await _ci.on_channel_callback(query, context, uid)
            except Exception as _e_ch:
                logger.warning(f"chimp callback error: {_e_ch}")
            return

        # Fail closed for permission buttons left in previously sent messages.
        if data.startswith("badm|") or data.startswith("adm_perm_"):
            try:
                await query.answer("این تنظیمات ساده‌سازی شده است", show_alert=True)
            except Exception:
                pass
            return
        try:
            await query.answer()
        except Exception:
            pass

        if _is_super_admin(uid, phone):
            if not user_rec or not user_rec.get("is_admin"):
                _upsert_giso_user(
                    bale_id=uid,
                    phone=(phone or "09156012931"),
                    first_name=(user.first_name or "") if user else "",
                    username=(user.username or "") if user else "",
                    is_admin=True,
                    contact_shared=True,
                    pending_request=False
                )
                user_rec = _get_giso_user(uid)

        if data.startswith("adm_") and not data.startswith("adm_ana") \
                and not data.startswith("adm_chat_view") and not _is_super_admin(uid, phone):
            try:
                await query.edit_message_text("⛔ شما دسترسی به مدیریت ادمین‌ها ندارید.")
            except Exception:
                pass
            return

        # فقط callbackهای مدیریت ادمین منحصر به ادمین هستند؛ بقیه (ثبت نظر، اعتراض، پاسخ) برای کاربران آزاد است
        _admin_only_hair = (
            "hair_admin_list", "hair_admin_u|", "hair_app|", "hair_review|",
            "hair_price|", "hair_price_conf|", "hair_price_cancel|",
            "hair_approve|", "hair_reject|", "hair_rej|",
            "hair_complete|", "hair_note|", "hair_msg|",
        )
        if data.startswith(_admin_only_hair) and not (_is_super_admin(uid, phone) or (user_rec and user_rec.get("is_admin"))):
            try:
                await query.edit_message_text("⛔ شما به مدیریت سفارش‌های مو دسترسی ندارید.")
            except Exception:
                pass
            return

        if _is_legacy_ai_callback(data) and not _has_provider_ai_management_access(uid, phone, user_rec):
            try:
                await query.edit_message_text("⛔ شما به مدیریت Providerها و پروکسی دسترسی ندارید.")
            except Exception:
                pass
            return

        # ═══ پنل کاربر: آنالیز هوشمند (callbacks) ═══
        if data == "analysis_menu":
            await _analysis_menu_callback(query, phone)
            return
        elif data == "analysis_list":
            await _analysis_list(query, phone)
            return
        elif data.startswith("analysis_view_"):
            try:
                aid = int(data.replace("analysis_view_", ""))
            except (ValueError, TypeError):
                await query.edit_message_text("⚠️ تحلیل پیدا نشد.")
                return
            await _analysis_view(query, phone, aid)
            return
        elif data == "analysis_checklist":
            await _analysis_checklist(query, phone)
            return
        elif data == "analysis_consultant":
            await _start_consultant_ai_chat(query, context, uid, _runtime_role_for_user(uid, phone, user_rec), is_query=True)
            return
        elif data == "consultant_ai_start":
            await _start_consultant_ai_chat(query, context, uid, _runtime_role_for_user(uid, phone, user_rec), is_query=True)
            return
        elif data == "analysis_products":
            await _analysis_products(query, phone)
            return
        elif data in ("cons_bot_end", "consultant_ai_end"):
            _set_consultant_ai_active(context, False)
            touch_user_activity(uid)
            await handle_consultant_end(query)
            return
        elif data.startswith("ai_act_confirm|"):
            if not _is_super_admin(uid, phone):
                await query.edit_message_text("⛔ فقط سوپرادمین")
                return
            try:
                pending_id = int(data.split("|", 1)[1])
            except Exception:
                await query.edit_message_text("⚠️ شناسه اقدام نامعتبر است.")
                return
            result = execute_pending_action(pending_id, uid)
            await query.edit_message_text(
                result.get("text") or "—",
                reply_markup=_super_action_result_kb(result.get("log_id"), reversible=bool(result.get("reversible"))),
            )
            return
        elif data.startswith("ai_act_cancel|"):
            if not _is_super_admin(uid, phone):
                await query.edit_message_text("⛔ فقط سوپرادمین")
                return
            try:
                pending_id = int(data.split("|", 1)[1])
            except Exception:
                await query.edit_message_text("⚠️ شناسه اقدام نامعتبر است.")
                return
            result = cancel_pending_action(pending_id, uid)
            await query.edit_message_text(result.get("text") or "—", reply_markup=_consultant_ai_end_kb())
            return
        elif data.startswith("ai_act_undo|"):
            if not _is_super_admin(uid, phone):
                await query.edit_message_text("⛔ فقط سوپرادمین")
                return
            try:
                log_id = int(data.split("|", 1)[1])
            except Exception:
                await query.edit_message_text("⚠️ شناسه بازگردانی نامعتبر است.")
                return
            result = rollback_action_log(log_id, uid)
            await query.edit_message_text(result.get("text") or "—", reply_markup=_consultant_ai_end_kb())
            return
        elif data == "support_menu":
            await handle_support_menu(query)
            return
        elif data == "support_new":
            await handle_support_new(query, context)
            return
        elif data == "support_my_tickets":
            await handle_support_my_tickets(query)
            return
        elif data.startswith("sup_reply_"):
            await handle_support_reply(query, context)
            return
        elif data.startswith("sup_close_"):
            await handle_support_close(query)
            return
        elif data.startswith("cons_view_"):
            if not _is_giso_admin(uid):
                await query.edit_message_text("⛔ دسترسی ندارید.")
                return
            await handle_consultant_view(query, uid)
            return
        elif data.startswith("cons_reply_"):
            if not _is_giso_admin(uid):
                await query.edit_message_text("⛔ دسترسی ندارید.")
                return
            await handle_consultant_reply(query, uid, context)
            return
        elif data.startswith("prod_view_"):
            if not _is_giso_admin(uid):
                await query.edit_message_text("⛔ دسترسی ندارید.")
                return
            await handle_product_request_view(query, uid)
            return
        elif data.startswith("prod_add_") or data.startswith("prod_reject_"):
            if not _is_giso_admin(uid):
                await query.edit_message_text("⛔ دسترسی ندارید.")
                return
            await handle_product_request_action(query, uid)
            return

        # ═══ پنل ادمین: مدیریت آنالیز (فقط ادمین) ═══
        if data.startswith("adm_ana"):
            if not _is_giso_admin(uid) or not _admin_has_analysis_access(uid):
                await query.edit_message_text("⛔ دسترسی ندارید.")
                return
            if data == "adm_ana_menu":
                await _admin_ana_menu_callback(query, uid)
            elif data == "adm_ana_stats":
                await _admin_ana_stats(query, uid)
            elif data == "adm_ana_list":
                await _admin_ana_list(query, uid)
            elif data == "adm_ana_consultants":
                await _admin_ana_consultants(query, uid)
            elif data == "adm_ana_products":
                await _admin_ana_products(query, uid)
            elif data == "adm_ana_ratelimit":
                if not _is_super_admin(uid, phone):
                    await query.edit_message_text("⛔ این تنظیم فقط برای سوپرادمین است.")
                    return
                await _admin_ana_ratelimit(query, uid)
            elif data == "adm_ana_chats" or data == "adm_ana_chats_all":
                await _admin_ana_chats(query, uid, 'all')
            elif data == "adm_ana_chats_today":
                await _admin_ana_chats(query, uid, 'today')
            elif data == "adm_ana_chats_week":
                await _admin_ana_chats(query, uid, 'week')
            elif data == "adm_ana_chats_month":
                await _admin_ana_chats(query, uid, 'month')
            return

        # ═══ مشاهده گفتگوی کامل مشاور (فقط ادمین با دسترسی آنالیز) ═══
        if data.startswith("adm_chat_view_"):
            if not _is_giso_admin(uid) or not _admin_has_analysis_access(uid):
                await query.edit_message_text("⛔ دسترسی ندارید.")
                return
            await _admin_chat_view(query, uid)
            return

        # ═══ تنظیم آدرس اصلی سایت (فقط سوپرادمین) ═══
        if data.startswith("giso_url"):
            if not _is_super_admin(uid, phone):
                await query.edit_message_text("⛔ فقط سوپرادمین")
                return
            if data == "giso_url_menu":
                await _giso_url_menu_callback(query, uid)
            elif data == "giso_url_change":
                context.user_data['awaiting_giso_url'] = True
                await _giso_url_change(query, uid)
            elif data == "giso_url_test":
                await _giso_url_test(query, uid)
            elif data == "giso_url_reset":
                await _giso_url_reset(query, uid)
            return

        # ═══ مدیریت رفتار هوش مصنوعی (فقط سوپرادمین) ═══
        if data.startswith("mair_"):
            if not _is_super_admin(uid, phone):
                await query.edit_message_text("⛔ فقط سوپرادمین")
                return
            if data == "mair_main":
                await _show_managed_ai_panel(query, is_q=True)
                return
            if data == "mair_back_settings":
                try:
                    await query.edit_message_text("⚙️ به منوی مدیریت سایت و ربات برگشتی.")
                except Exception:
                    pass
                await query.message.reply_text(
                    "⚙️ منوی مدیریت سایت و ربات:",
                    reply_markup=_admin_settings_kb(),
                )
                return
            if data == "mair_menu_status":
                await _show_managed_ai_status_menu(query, is_q=True)
                return
            if data == "mair_active_test":
                active = get_active_provider() or ""
                if not active:
                    await query.edit_message_text("هیچ AI فعالی برای تست ثبت نشده است.", reply_markup=_managed_ai_status_kb())
                    return
                res = await check_ai_provider(active)
                text = (
                    f"🧪 تست AI فعال\n━━━━━━━━━━━━━━━━━━━━━━━\n"
                    f"AI: {active}\nوضعیت: {res.get('status') or '—'}\nمدل: {res.get('selected') or res.get('selected_model') or res.get('selected') or '—'}"
                )
                if res.get('error'):
                    text += f"\nخطا: {str(res.get('error'))[:200]}"
                await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 بازگشت", callback_data="mair_menu_status")]]))
                return
            if data == "mair_provider_status":
                await query.edit_message_text(build_provider_status_report(), reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 بازگشت", callback_data="mair_menu_status")]]))
                return
            if data == "mair_menu_selection":
                await _show_managed_ai_selection_menu(query, is_q=True)
                return
            if data == "mair_menu_providers":
                await _show_managed_ai_providers(query, is_q=True)
                return
            if data.startswith("mair_pick_provider|"):
                new_name = data.split("|", 1)[1]
                old_name = get_active_provider() or "—"
                ok, msg = set_active_provider(new_name)
                text = (
                    ("✅ AI فعال تغییر کرد\n\n" if ok else "❌ تغییر AI ناموفق بود\n\n") +
                    f"🤖 قبلی: {old_name}\n"
                    f"🤖 جدید: {new_name}\n\n"
                    f"{msg}"
                )
                kb = InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔙 بازگشت به انتخاب AI", callback_data="mair_menu_providers")],
                    [InlineKeyboardButton("🏠 منوی AI", callback_data="mair_main")],
                ])
                await query.edit_message_text(text, reply_markup=kb)
                return
            if data == "mair_menu_failover":
                await _show_managed_ai_failover(query)
                return
            if data.startswith("mair_fail_promote|"):
                pname = data.split("|", 1)[1]
                chain = [p for p in get_failover_chain() if p != pname]
                chain.insert(0, pname)
                set_failover_chain(chain)
                await _show_managed_ai_failover(query)
                return
            if data == "mair_fail_reset":
                all_names = [x['name'] for x in (list_provider_options().get('iranian', []) + list_provider_options().get('foreign', []))]
                set_failover_chain(all_names)
                await _show_managed_ai_failover(query)
                return
            if data == "mair_fail_test":
                chain = get_failover_chain()
                lines = ["🧪 تست زنجیره Failover", "━━━━━━━━━━━━━━━━━━━━━━━"]
                for idx, pname in enumerate(chain[:5], start=1):
                    res = await check_ai_provider(pname)
                    lines.append(f"{idx}. {pname} — {res.get('status') or '—'}")
                await query.edit_message_text("\n".join(lines), reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 بازگشت", callback_data="mair_menu_failover")]]))
                return
            if data == "mair_menu_permissions":
                await _show_managed_ai_permissions(query, is_q=True)
                return
            if data.startswith("mair_perm_role|"):
                role = data.split("|", 1)[1]
                await _show_managed_ai_permission_role(query, role)
                return
            if data.startswith("mair_perm_level|"):
                _, role, level = data.split("|", 2)
                current = get_role_policy(role)
                set_role_policy(role, access_level=int(level), sections=current.get("sections"), daily_limit=current.get("daily_limit"))
                await _show_managed_ai_permission_role(query, role)
                return
            if data.startswith("mair_perm_sec|"):
                _, role, sec = data.split("|", 2)
                current = get_role_policy(role)
                sections = list(current.get("sections") or [])
                if sec in sections:
                    sections = [s for s in sections if s != sec]
                else:
                    sections.append(sec)
                set_role_policy(role, access_level=current.get("access_level"), sections=sections, daily_limit=current.get("daily_limit"))
                await _show_managed_ai_permission_role(query, role)
                return
            if data.startswith("mair_perm_limit|"):
                _, role, limit = data.split("|", 2)
                current = get_role_policy(role)
                set_role_policy(role, access_level=current.get("access_level"), sections=current.get("sections"), daily_limit=int(limit))
                await _show_managed_ai_permission_role(query, role)
                return
            if data.startswith("mair_perm_save|"):
                role = data.split("|", 1)[1]
                await query.message.reply_text("✅ تنظیمات دسترسی ذخیره شد.")
                await _show_managed_ai_permission_role(query, role)
                return
            if data == "mair_menu_behavior":
                text = "🎭 رفتار و هویت\n━━━━━━━━━━━━━━━━━━━━━━━\nاسم نمایشی، قابلیت‌های هر نقش و پیش‌نمایش رفتاری را از اینجا مدیریت کن."
                await query.edit_message_text(text, reply_markup=_managed_ai_behavior_kb())
                return
            if data == "mair_menu_display":
                await _show_managed_ai_display_name(query, is_q=True)
                return
            if data == "mair_change_display":
                _user_states[uid] = "wait_ai_display_name"
                await context.bot.send_message(
                    chat_id=uid,
                    text="اسم جدید را وارد کن (حداکثر ۲۰ کاراکتر)\n/cancel برای لغو",
                )
                return
            if data == "mair_menu_capabilities":
                await _show_managed_ai_capabilities(query, is_q=True)
                return
            if data.startswith("mair_caps_role|"):
                role = data.split("|", 1)[1]
                await _show_managed_ai_role_capabilities(query, role)
                return
            if data.startswith("mair_caps_edit|"):
                role = data.split("|", 1)[1]
                _user_states[uid] = f"wait_ai_capabilities_{role}"
                await context.bot.send_message(
                    chat_id=uid,
                    text=f"متن قابلیت‌های {ROLE_LABELS.get(role, role)} را ارسال کن.\n/cancel برای لغو",
                )
                return
            if data == "mair_behavior_preview":
                lines = ["👁 پیش‌نمایش رفتار", "━━━━━━━━━━━━━━━━━━━━━━━"]
                for role in ("user", "admin", "super"):
                    pol = get_role_policy(role)
                    lines.append(f"\n{ROLE_LABELS.get(role, role)}: level={pol.get('access_level')} | limit={pol.get('daily_limit')}")
                    lines.append(f"sections: {', '.join(pol.get('sections') or [])}")
                await query.edit_message_text("\n".join(lines), reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 بازگشت", callback_data="mair_menu_behavior")]]))
                return
            if data == "mair_menu_toggle":
                await _show_managed_ai_toggle(query, is_q=True)
                return
            if data == "mair_toggle_confirm_off":
                kb = InlineKeyboardMarkup([
                    [InlineKeyboardButton("✅ بله، خاموش کن", callback_data="mair_toggle_apply|0")],
                    [InlineKeyboardButton("❌ لغو", callback_data="mair_menu_toggle")],
                ])
                await query.edit_message_text(
                    "⚠️ اگر خاموش کنی، چت مشاور سایت و ربات متوقف می‌شود.\n\nمطمئنی؟",
                    reply_markup=kb,
                )
                return
            if data.startswith("mair_toggle_apply|"):
                flag = data.split("|", 1)[1] == "1"
                set_chat_enabled(flag)
                await _show_managed_ai_toggle(query, is_q=True)
                return
            if data == "mair_menu_report":
                await _show_managed_ai_report(query, is_q=True)
                return
            if data == "mair_menu_ops":
                await _show_managed_ai_ops(query, is_q=True)
                return
            if data == "mair_pending_list":
                await _show_pending_actions(query)
                return
            if data.startswith("mair_pending_view|"):
                pid = int(data.split("|", 1)[1])
                item = next((x for x in get_recent_pending_actions(limit=50) if int(x.get('id') or 0) == pid), None)
                if not item:
                    await query.edit_message_text("اقدام موردنظر پیدا نشد.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 بازگشت", callback_data="mair_pending_list")]]))
                    return
                text = str(item.get('preview_text') or '') or f"اقدام #{pid}"
                kb = InlineKeyboardMarkup([
                    [InlineKeyboardButton("✅ تأیید", callback_data=f"ai_act_confirm|{pid}"), InlineKeyboardButton("❌ لغو", callback_data=f"ai_act_cancel|{pid}")],
                    [InlineKeyboardButton("🔙 بازگشت", callback_data="mair_pending_list")],
                ])
                await query.edit_message_text(text, reply_markup=kb)
                return
            if data == "mair_logs_list":
                await _show_action_logs(query)
                return
            if data.startswith("mair_log_view|"):
                lid = int(data.split("|", 1)[1])
                item = next((x for x in get_recent_action_logs(limit=100) if int(x.get('id') or 0) == lid), None)
                if not item:
                    await query.edit_message_text("لاگ پیدا نشد.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 بازگشت", callback_data="mair_logs_list")]]))
                    return
                text = (
                    f"🧾 لاگ #{lid}\n━━━━━━━━━━━━━━━━━━━━━━━\n"
                    f"action: {item.get('action_name')}\nstatus: {item.get('status')}\n"
                    f"target: {item.get('target_table')} #{item.get('target_id')}\n"
                    f"time: {to_shamsi(item.get('created_at'))}"
                )
                await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 بازگشت", callback_data="mair_logs_list")]]))
                return
            if data == "mair_rollbacks_list":
                await _show_rollbacks(query)
                return
            if data == "mair_menu_widget":
                await _show_managed_ai_widget_menu(query, is_q=True)
                return
            if data == "mair_widget_toggle":
                set_widget_enabled(not is_widget_enabled())
                await _show_managed_ai_widget_menu(query, is_q=True)
                return
            if data == "mair_widget_position":
                await query.edit_message_text("🎨 موقعیت نمایش Widget را انتخاب کن:", reply_markup=_managed_ai_widget_position_kb())
                return
            if data.startswith("mair_widget_pos|"):
                pos = data.split("|", 1)[1]
                set_widget_position(pos)
                await _show_managed_ai_widget_menu(query, is_q=True)
                return
            if data == "mair_widget_welcome":
                _user_states[uid] = "wait_widget_welcome"
                await context.bot.send_message(chat_id=uid, text="متن خوش‌آمد Widget را بفرست.\n/cancel برای لغو")
                return
            if data == "mair_widget_color":
                _user_states[uid] = "wait_widget_color"
                await context.bot.send_message(chat_id=uid, text="رنگ اصلی Widget را به صورت #RRGGBB بفرست.\nمثال: #8b5cf6")
                return
            if data == "mair_widget_stats":
                await _show_widget_stats(query)
                return

        # ═══ پشتیبان‌گیری (فقط سوپرادمین) ═══
        if data.startswith(("backup_", "giso_restore_pick_", "giso_restore_confirm_")) \
                or data == "back_settings":
            if not _is_super_admin(uid, phone):
                await query.edit_message_text("⛔ فقط سوپرادمین")
                return
            if data == "backup_now":
                await handle_backup_now(query, context)
            elif data == "backup_upload":
                await handle_backup_upload(query, context)
            elif data == "backup_list":
                await handle_backup_list(query, context)
            elif data == "backup_set_interval":
                await handle_backup_set_interval(query, context)
            elif data.startswith("backup_interval_"):
                await handle_backup_interval_set(query, context)
            elif data == "backup_restore_manual":
                await handle_restore_manual(query, context)
            elif data == "backup_restore_list":
                await handle_restore_list(query, context)
            elif data.startswith("giso_restore_pick_"):
                await handle_restore_pick(query, context)
            elif data.startswith("giso_restore_confirm_"):
                await handle_restore_confirm(query, context)
            elif data == "backup_menu":
                await handle_backup_back(query)
            elif data == "back_settings":
                await handle_backup_back(query)
            return

        # ═══ ریستارت ربات (فقط سوپرادمین) ═══
        if data.startswith("restart_"):
            if not _is_super_admin(uid, phone):
                await query.edit_message_text("⛔ فقط سوپرادمین")
                return
            if data == "restart_menu":
                await handle_restart_menu(query, context)
            elif data.startswith("restart_confirm_"):
                await handle_restart_confirm(query, context)
            elif data == "restart_cancel":
                await handle_restart_cancel(query, context)
            return

        try:
            from giso_admin import review_admin_request, delete_giso_admin, list_giso_admins

            # ═══ فاز ۵ نهایی: منوی هوشمند فروش مو ادمین (لیست درخواست‌ها / کاربران) ═══
            if data == "hair_admin_list":
                await render_request_list(query.message, uid)
                return
            if data.startswith("hair_admin_u|"):
                _u_phone = data.split("|", 1)[1]
                await render_user_orders(query.message, uid, _u_phone)
                return

            # ═══ فاز 5.1 ربات: صفحه‌بندی قبلی/بعدی (درخواست‌ها / کاربران / سفارش‌های کاربر) ═══
            if data.startswith("hair_pg|") or data.startswith("hair_rep|") or data.startswith("hair_rep_view|"):
                if not _is_giso_admin(uid):
                    return
                try:
                    parts = data.split("|")
                    if data == "hair_pg|menu":
                        await query.message.reply_text(admin_hair_menu_text(),
                                                       reply_markup=build_admin_hair_menu(uid=uid))
                        return
                    if parts[0] == "hair_pg" and parts[1] == "req":
                        await show_requests_paged(query.message, uid, int(parts[2]))
                        return
                    if parts[0] == "hair_pg" and parts[1] == "usr":
                        await show_users_paged(query.message, uid, int(parts[2]))
                        return
                    if parts[0] == "hair_pg" and parts[1] == "uo":
                        # hair_pg|uo|<phone>|<idx> — شماره می‌تواند «+» داشته باشد ولی «|» ندارد
                        await show_user_orders_paged(query.message, uid, parts[2], int(parts[3]))
                        return
                    if parts[0] == "hair_rep" and parts[1] in ("reviewing", "rejected", "priced"):
                        await show_report_phones(query.message, uid, parts[1], int(parts[2]))
                        return
                    if parts[0] == "hair_rep" and parts[1] == "menu":
                        await query.message.reply_text(
                            "📊 گزارش‌های خرید مو — یکی را انتخاب کنید:", reply_markup=_admin_hair_reports_kb())
                        return
                    if parts[0] == "hair_rep_view" and parts[1] in ("reviewing", "rejected", "priced"):
                        await show_report_user_view(query.message, uid, parts[1], parts[2])
                        return
                except (IndexError, ValueError) as _pg_e:
                    logger.debug(f"hair pager callback err: {_pg_e}")
                except Exception as _pg_e:
                    logger.warning(f"hair pager callback: {_pg_e}")
                return

            if data.startswith("hair_app|") or data.startswith("hair_review|"):
                order_id = int(data.split("|")[1])
                with get_giso_db_conn() as conn:
                    conn.execute("UPDATE hair_orders SET status='reviewing', updated_at=? WHERE id=?",
                                 (time.strftime("%Y-%m-%d %H:%M:%S"), order_id))
                    conn.commit()
                await query.edit_message_text(f"✅ وضعیت درخواست خرید مو #{order_id} به «در حال بررسی 🔍» تغییر کرد.")
                notify_user_bot_by_order(context, order_id, "✅ کارشناسان گیسو در حال بررسی تصویر و مشخصات موی شما هستند.")
                # UX: بلافاصله درخواست بعدی لیست را بیاور تا ادمین در جریان کار بماند
                try:
                    from giso.bot_hair_admin import show_requests_paged as _srp
                    await _srp(query.message, uid, 0)
                except Exception as _e_nxt:
                    logger.debug(f"hair next-card after review: {_e_nxt}")

            elif data.startswith("hair_rej|") or data.startswith("hair_reject|"):
                order_id = int(data.split("|")[1])
                with get_giso_db_conn() as conn:
                    conn.execute("UPDATE hair_orders SET status='rejected', updated_at=? WHERE id=?",
                                 (time.strftime("%Y-%m-%d %H:%M:%S"), order_id))
                    conn.commit()
                await query.edit_message_text(f"❌ درخواست خرید مو #{order_id} رد شد و به «گزارش‌ها ← نمایش رد شده» منتقل شد.")
                kb_objection = InlineKeyboardMarkup([
                    [InlineKeyboardButton("📝 ثبت اعتراض یا نظر", callback_data=f"hair_objection|{order_id}")]
                ])
                await _send_user_status_message(
                    context, order_id,
                    "❌ متاسفانه درخواست شما رد شد",
                    kb=kb_objection
                )
                # UX: بلافاصله درخواست بعدی لیست را بیاور
                try:
                    from giso.bot_hair_admin import show_requests_paged as _srp
                    await _srp(query.message, uid, 0)
                except Exception as _e_nxt:
                    logger.debug(f"hair next-card after reject: {_e_nxt}")

            elif data.startswith("hair_approve|"):
                order_id = int(data.split("|")[1])
                # فاز 3.2: اگر قیمت نهایی ثبت نشده، اول از ادمین قیمت بپرس سپس تأیید کن
                with get_giso_db_conn() as conn:
                    _ap_row = conn.execute("SELECT final_price FROM hair_orders WHERE id=?", (order_id,)).fetchone()
                    _has_price = bool(_ap_row and (_ap_row["final_price"] or "").strip())
                if not _has_price:
                    _user_states[uid] = f"waiting_hair_approve_price_{order_id}"
                    try:
                        # رنج پیشنهادی سیستم برای راهنمای ادمین (مطابق مشخصات پنل خرید مو)
                        _est_txt = ""
                        try:
                            with get_giso_db_conn() as conn:
                                _est_row = conn.execute("SELECT estimated_price FROM hair_orders WHERE id=?", (order_id,)).fetchone()
                            if _est_row and (_est_row["estimated_price"] or "").strip():
                                _est_txt = f"\n💰 رنج پیشنهادی سیستم: {_est_row['estimated_price']}"
                        except Exception:
                            _est_txt = ""
                        await context.bot.send_message(
                            chat_id=uid,
                            text=f"✅ برای تأیید درخواست #{_fa_num(order_id)}، ابتدا قیمت نهایی را وارد کنید (به تومان — مثلاً 25 میلیون تومان):{_est_txt}"
                        )
                    except Exception as _e_ap:
                        logger.warning(f"hair_approve price prompt failed: {_e_ap}")
                    return
                with get_giso_db_conn() as conn:
                    conn.execute("UPDATE hair_orders SET status='approved', updated_at=? WHERE id=?",
                                 (time.strftime("%Y-%m-%d %H:%M:%S"), order_id))
                    conn.commit()
                try:
                    from giso.marketplace.services import close_listing_for_direct_sale
                    close_listing_for_direct_sale(order_id)
                except Exception as _cls_e:
                    logger.debug(f"close listing direct sale: {_cls_e}")
                await query.edit_message_text(f"✅ درخواست خرید مو #{order_id} تایید شد.")
                await _send_user_status_message(
                    context, order_id,
                    "✅ درخواست فروش موی شما تایید شد\nکارشناس به‌زودی با شما تماس می‌گیرد"
                )

            elif data.startswith("hair_complete|"):
                order_id = int(data.split("|")[1])
                with get_giso_db_conn() as conn:
                    conn.execute("UPDATE hair_orders SET status='completed', updated_at=? WHERE id=?",
                                 (time.strftime("%Y-%m-%d %H:%M:%S"), order_id))
                    conn.commit()
                # مأموریت «تکمیل خرید مو» (best-effort؛ اگر مأموریت فعال نباشد هیچ اتفاقی نمی‌افتد)
                _complete_hair_order_mission(order_id)
                # خرید مستقیم گیسو: آگهی متصل بازارچه بسته و «فروخته‌شده» می‌شود
                try:
                    from giso.marketplace.services import close_listing_for_direct_sale
                    close_listing_for_direct_sale(order_id)
                except Exception as _cls_e:
                    logger.debug(f"close listing direct sale: {_cls_e}")
                await query.edit_message_text(f"📦 درخواست خرید مو #{order_id} تکمیل شد.")
                kb_rate = InlineKeyboardMarkup([
                    [InlineKeyboardButton("⭐ ثبت نظر و امتیاز", callback_data=f"hair_rev_sel|{order_id}")]
                ])
                await _send_user_status_message(
                    context, order_id,
                    "🎉 خرید موی شما با موفقیت تکمیل شد\nاز اعتماد شما سپاسگزاریم",
                    kb=kb_rate
                )

            elif data.startswith("hair_price_conf|") or data.startswith("hair_price_cancel|"):
                order_id = int(data.split("|")[1])
                from giso.hair_sale import confirm_hair_price, cancel_hair_price
                if data.startswith("hair_price_conf|"):
                    await confirm_hair_price(query, uid, order_id, _user_states)
                else:
                    await cancel_hair_price(query, uid, order_id, _user_states)

            elif data.startswith("hair_price|"):
                order_id = int(data.split("|")[1])
                _user_states[uid] = f"waiting_hair_price_{order_id}"
                # رنج پیشنهادی سیستم برای راهنمای ادمین (مطابق مشخصات پنل خرید مو)
                _est_txt = ""
                try:
                    with get_giso_db_conn() as conn:
                        _est_row = conn.execute("SELECT estimated_price FROM hair_orders WHERE id=?", (order_id,)).fetchone()
                    if _est_row and (_est_row["estimated_price"] or "").strip():
                        _est_txt = f"\n💰 رنج پیشنهادی سیستم: {_est_row['estimated_price']}"
                except Exception:
                    _est_txt = ""
                # فیکس: query.answer قبلاً در ابتدای handler یک‌بار صدا زده شده و اینجا
                # HTTP 400 می‌داد؛ چون در همان try بود، پیام «قیمت را وارد کنید» هم
                # هرگز ارسال نمی‌شد و ادمین چیزی نمی‌دید. try ها جدا شدند.
                try:
                    await context.bot.send_message(
                        chat_id=uid,
                        text=f"💰 لطفاً قیمت نهایی برای درخواست خرید مو #{order_id} را ارسال کنید (به تومان — مثلاً 28 میلیون تومان):{_est_txt}"
                    )
                except Exception as _e_pr:
                    logger.warning(f"hair_price prompt send failed: {_e_pr}")

            elif data.startswith("hair_note|"):
                order_id = int(data.split("|")[1])
                _user_states[uid] = f"waiting_hair_note_{order_id}"
                try:
                    await context.bot.send_message(
                        chat_id=uid,
                        text=f"📝 لطفاً یادداشت کارشناس برای درخواست خرید مو #{order_id} را ارسال کنید:"
                    )
                except Exception as _e_nt:
                    logger.warning(f"hair_note prompt failed: {_e_nt}")

            elif data.startswith("hair_rev_sel|"):
                order_id = int(data.split("|")[1])
                kb_rates = InlineKeyboardMarkup([
                    [
                        InlineKeyboardButton("⭐ 5 عالی", callback_data=f"hair_rev_rate|{order_id}|5"),
                        InlineKeyboardButton("⭐ 4 خوب", callback_data=f"hair_rev_rate|{order_id}|4"),
                    ],
                    [
                        InlineKeyboardButton("⭐ 3 متوسط", callback_data=f"hair_rev_rate|{order_id}|3"),
                        InlineKeyboardButton("⭐ 2 ضعیف", callback_data=f"hair_rev_rate|{order_id}|2"),
                        InlineKeyboardButton("⭐ 1 خیلی ضعیف", callback_data=f"hair_rev_rate|{order_id}|1"),
                    ]
                ])
                await query.edit_message_text(
                    f"⭐ ثبت نظر برای سفارش فروش مو #{_fa_num(order_id)}:\nلطفاً امتیاز خود از ۱ تا ۵ را انتخاب کنید:",
                    reply_markup=kb_rates
                )

            elif data.startswith("hair_rev_rate|"):
                parts = data.split("|")
                order_id = int(parts[1])
                rating = int(parts[2])
                _user_states[uid] = f"waiting_hair_rev_txt_{order_id}_{rating}"
                try:
                    await context.bot.send_message(
                        chat_id=uid,
                        text=f"✍️ امتیاز شما ({_fa_num(rating)} از ۵) ثبت شد. لطفاً متن نظر و تجربه خود از خرید مو #{_fa_num(order_id)} را ارسال کنید:"
                    )
                except Exception:
                    pass

            # 🆕 نظردهی سفارش‌های فروشگاه (مشابه فلو فروش مو)
            elif data.startswith("srev|sel|"):
                order_id = int(data.split("|")[2])
                if not any(r["id"] == order_id for r in _shop_order_rows(phone or "", limit=50)):
                    await query.answer("⛔ این سفارش متعلق به شما نیست.", show_alert=True)
                    return
                kb_rates = InlineKeyboardMarkup([
                    [
                        InlineKeyboardButton("⭐ 5 عالی", callback_data=f"srev|rate|{order_id}|5"),
                        InlineKeyboardButton("⭐ 4 خوب", callback_data=f"srev|rate|{order_id}|4"),
                    ],
                    [
                        InlineKeyboardButton("⭐ 3 متوسط", callback_data=f"srev|rate|{order_id}|3"),
                        InlineKeyboardButton("⭐ 2 ضعیف", callback_data=f"srev|rate|{order_id}|2"),
                        InlineKeyboardButton("⭐ 1 خیلی ضعیف", callback_data=f"srev|rate|{order_id}|1"),
                    ]
                ])
                await query.edit_message_text(
                    f"⭐ ثبت نظر برای سفارش فروشگاه #{_fa_num(order_id)}:\nلطفاً امتیاز خود از ۱ تا ۵ را انتخاب کنید:",
                    reply_markup=kb_rates
                )

            elif data.startswith("srev|rate|"):
                parts = data.split("|")
                order_id = int(parts[2])
                rating = int(parts[3])
                _user_states[uid] = f"waiting_shop_rev_txt_{order_id}_{rating}"
                try:
                    await context.bot.send_message(
                        chat_id=uid,
                        text=f"✍️ امتیاز شما ({_fa_num(rating)} از ۵) ثبت شد. لطفاً متن نظر و تجربه خود از سفارش فروشگاه #{_fa_num(order_id)} را ارسال کنید:"
                    )
                except Exception:
                    pass

            elif data.startswith("hair_msg|"):
                order_id = int(data.split("|")[1])
                _user_states[uid] = f"waiting_admin_msg_{order_id}"
                # نمایش آخرین پیام‌های گفتگو (استایل‌دار) تا ادمین بداند به چه پاسخ می‌دهد
                _hist_txt = ""
                try:
                    with get_giso_db_conn() as conn:
                        _h_rows = conn.execute(
                            "SELECT sender, message FROM hair_messages WHERE order_id=? ORDER BY id DESC LIMIT 4",
                            (order_id,)).fetchall()
                    if _h_rows:
                        _parts = []
                        for _hr in reversed(_h_rows):
                            _icon = "👤 مشتری" if _hr["sender"] == "user" else "🧑‍💼 کارشناس"
                            _parts.append(f"{_icon}: {(_hr['message'] or '')[:150]}")
                        _hist_txt = "\n━━━━━━━━━━━━━━━━\n💬 آخرین پیام‌های گفتگو:\n" + "\n".join(_parts) + "\n━━━━━━━━━━━━━━━━"
                except Exception:
                    _hist_txt = ""
                try:
                    await context.bot.send_message(
                        chat_id=uid,
                        text=f"💬 گفتگوی درخواست #{_fa_num(order_id)}{_hist_txt}\n✍️ پیام خود برای مشتری را ارسال کنید:"
                    )
                except Exception as _e_ms:
                    logger.warning(f"hair_msg prompt failed: {_e_ms}")

            elif data.startswith("hair_view_msgs|"):
                order_id = int(data.split("|")[1])
                with get_giso_db_conn() as conn:
                    msgs = conn.execute(
                        "SELECT * FROM hair_messages WHERE order_id=? ORDER BY id ASC",
                        (order_id,)
                    ).fetchall()
                    conn.execute(
                        "UPDATE hair_messages SET is_read=1 WHERE order_id=? AND sender='admin'",
                        (order_id,)
                    )
                    conn.commit()
                if not msgs:
                    await query.answer("💬 پیامی برای این درخواست ثبت نشده است.", show_alert=True)
                    return
                lines = [f"💬 گفتگوی درخواست #{_fa_num(order_id)}", "━━━━━━━━━━━━━━━━"]
                for m in msgs:
                    who = "👨‍💼 کارشناس گیسو" if m["sender"] == "admin" else "👤 شما"
                    lines.append(f"\n{who} ({to_shamsi(m['created_at'])}):\n{m['message']}")
                kb = InlineKeyboardMarkup([
                    [InlineKeyboardButton(f"💬 پاسخ به کارشناس | #{_fa_num(order_id)}", callback_data=f"hair_user_reply|{order_id}")]
                ])
                try:
                    await query.message.reply_text("\n".join(lines), reply_markup=kb)
                except Exception:
                    pass

            elif data.startswith("hair_user_reply|"):
                order_id = int(data.split("|")[1])
                _user_states[uid] = f"waiting_user_msg_reply_{order_id}"
                try:
                    await context.bot.send_message(
                        chat_id=uid,
                        text=f"💬 لطفاً متن پاسخ خود به کارشناس برای درخواست #{_fa_num(order_id)} را ارسال کنید:"
                    )
                except Exception:
                    pass

            elif data.startswith("hair_objection|"):
                order_id = int(data.split("|")[1])
                _user_states[uid] = f"waiting_hair_objection_{order_id}"
                try:
                    await context.bot.send_message(
                        chat_id=uid,
                        text=f"📝 لطفاً متن اعتراض یا نظر خود درباره درخواست #{_fa_num(order_id)} را ارسال کنید:"
                    )
                except Exception:
                    pass

            elif data.startswith("ai_edit_select|"):
                name = data.split("|", 1)[1]
                await _ai_show_provider_edit(query, name)
                return

            elif data.startswith("ai_edit_fld|"):
                parts = data.split("|", 2)
                name = parts[1]
                field = parts[2]
                _ai_temp_data[uid] = {"provider": name, "field": field}
                _user_states[uid] = "wait_ai_edit_val"
                await query.message.reply_text(
                    f"✏️ ویرایش فیلد «{field}» برای پروایدر «{name}»\nلطفاً مقدار جدید را ارسال کنید (یا `-` برای خالی):",
                    reply_markup=ReplyKeyboardMarkup([["🔙 بازگشت"]], resize_keyboard=True)
                )
                return

            elif data.startswith("ai_edit_proxy|"):
                name = data.split("|", 1)[1]
                toggle_use_proxy(name)
                await _ai_show_provider_edit(query, name)
                return

            elif data.startswith("ai_edit_ref|"):
                name = data.split("|", 1)[1]
                # query.answer() فقط یک بار (در ابتدای handle_callback) پاسخ داده شده است.
                # صدا زدن مجدد query.answer() باعث خطای duplicate می‌شود؛ نتیجه را با reply_text نشان می‌دهیم.
                try:
                    logger.info("[AI_CHECK] Starting check for provider: %s", name)
                    res = await check_ai_provider(name)
                    logger.info("[AI_CHECK] Result: status=%s, error=%s, models=%d",
                                res.get("status"), res.get("error"), len(res.get("models", [])))
                    st_fa = "سالم ✅" if str(res.get("status", "")).startswith("ok") else str(res.get("status", "خطا ❌"))
                    models_str = "، ".join(res.get("models", [])[:5]) if res.get("models") else "—"
                    msg_text = (
                        f"📊 نتیجه تست پروایدر «{name}»\n"
                        "━━━━━━━━━━━━━━━━\n"
                        f"🔹 وضعیت: {st_fa}\n"
                        f"🎯 مدل انتخابی: {res.get('selected') or '—'}\n"
                        f"📚 تعداد مدل‌ها: {len(res.get('models', []))}\n"
                        f"🧪 مدل‌ها: {models_str}"
                    )
                    if res.get("error") and not str(res.get("status", "")).startswith("ok"):
                        msg_text += f"\n⚠️ خطا: {res.get('error')}"
                    await query.message.reply_text(msg_text)
                except Exception as e:
                    logger.error(f"AI check callback error: {e}", exc_info=True)
                    try:
                        await query.message.reply_text(f"❌ خطا در تست پروایدر {name}:\n{str(e)[:200]}")
                    except Exception:
                        pass
                await _ai_show_provider_edit(query, name)
                return

            elif data == "ai_edit_back":
                await _show_ai_panel(query.message)
                return

            elif data.startswith("ai_toggle|"):
                name = data.split("|", 1)[1]
                new_st = toggle_ai_provider(name)
                st_txt = "فعال ✅" if new_st else "غیرفعال ❌"
                # query.answer() قبلاً در ابتدای handle_callback یک بار صدا زده شده؛
                # صدا زدن مجدد باعث duplicate می‌شود.
                await query.edit_message_text(f"✅ وضعیت پروایدر «{name}» به {st_txt} تغییر یافت.")
                return

            elif data.startswith("prx_mode|"):
                mode = data.split("|", 1)[1]
                set_mode(mode)
                await query.edit_message_text(f"✅ حالت اتصال پروکسی به {mode_label(mode)} تغییر یافت.")
                return

            elif data == "prx_clearok":
                clear_manual_proxies()
                await query.edit_message_text("✅ لیست پروکسی‌های دستی پاک شد.")
                return

            elif data == "prx_cancel":
                await query.edit_message_text("❌ عملیات لغو شد.")
                return

            elif data.startswith("cons_start|"):
                if not (_is_super_admin(uid, phone) or (user_rec and user_rec.get("is_admin"))):
                    await query.edit_message_text("⛔ شما دسترسی ادمین ندارید.")
                    return
                rid = int(data.split("|")[1])
                _user_states[uid] = f"consultant_chat_{rid}"
                with get_giso_db_conn() as conn:
                    conn.execute("UPDATE consultant_requests SET status='chatting', admin_id=?, updated_at=? WHERE id=?",
                                 (uid, time.strftime("%Y-%m-%d %H:%M:%S"), rid))
                    conn.commit()
                await query.edit_message_text(f"✅ گفتگوی مشاوره #{rid} شروع شد. پیام خود را ارسال کنید (یا /cancel برای پایان).")
                return

            elif data.startswith("cons_review|"):
                if not (_is_super_admin(uid, phone) or (user_rec and user_rec.get("is_admin"))):
                    await query.edit_message_text("⛔ شما دسترسی ادمین ندارید.")
                    return
                rid = int(data.split("|")[1])
                with get_giso_db_conn() as conn:
                    conn.execute("UPDATE consultant_requests SET status='reviewing', admin_id=?, updated_at=? WHERE id=?",
                                 (uid, time.strftime("%Y-%m-%d %H:%M:%S"), rid))
                    conn.commit()
                await query.edit_message_text(f"🔍 درخواست مشاوره #{rid} در حال بررسی است.")
                return

            elif data.startswith("cons_close|"):
                if not (_is_super_admin(uid, phone) or (user_rec and user_rec.get("is_admin"))):
                    await query.edit_message_text("⛔ شما دسترسی ادمین ندارید.")
                    return
                rid = int(data.split("|")[1])
                _user_states.pop(uid, None)
                with get_giso_db_conn() as conn:
                    conn.execute("UPDATE consultant_requests SET status='closed', updated_at=? WHERE id=?",
                                 (time.strftime("%Y-%m-%d %H:%M:%S"), rid))
                    conn.commit()
                await query.edit_message_text(f"✅ گفتگوی مشاوره #{rid} پایان یافت.")
                return

            elif data == "rl_toggle":
                if not _is_super_admin(uid, phone):
                    await query.edit_message_text("⛔ شما دسترسی به این تنظیم ندارید.")
                    return
                from giso_admin import set_giso_config
                from giso.base import read_rate_limit_config
                cur = read_rate_limit_config().get("enabled", True)
                new = "0" if cur else "1"
                set_giso_config("rate_limit_enabled", new)
                st_fa = "فعال" if not cur else "غیرفعال"
                await query.edit_message_text(
                    _ratelimit_status_text(),
                    reply_markup=_ratelimit_inline_kb(),
                )
                try:
                    await context.bot.send_message(chat_id=uid, text=f"✅ محدودیت زمانی {st_fa} شد")
                except Exception:
                    pass
                return

            elif data == "rl_minutes":
                if not _is_super_admin(uid, phone):
                    await query.edit_message_text("⛔ شما دسترسی به این تنظیم ندارید.")
                    return
                _user_states[uid] = "waiting_rate_limit_minutes"
                # query.answer() در ابتدای handle_callback فقط یک بار صدا زده شده؛
                # صدا زدن مجدد باعث خطای duplicate answerCallbackQuery (400) می‌شود.
                try:
                    await context.bot.send_message(
                        chat_id=uid,
                        text="⏰ مدت زمان جدید رو به دقیقه بفرست (مثال: 60):"
                    )
                except Exception:
                    pass
                return

            elif data == "rl_type":
                if not _is_super_admin(uid, phone):
                    await query.edit_message_text("⛔ شما دسترسی به این تنظیم ندارید.")
                    return
                kb = InlineKeyboardMarkup([
                    [InlineKeyboardButton("📱 فقط IP", callback_data="rl_type_set|ip")],
                    [InlineKeyboardButton("☎️ فقط شماره موبایل", callback_data="rl_type_set|phone")],
                    [InlineKeyboardButton("🔗 هر دو", callback_data="rl_type_set|both")],
                ])
                await query.edit_message_text("🎯 نوع محدودیت را انتخاب کنید:", reply_markup=kb)
                return

            elif data.startswith("rl_type_set|"):
                if not _is_super_admin(uid, phone):
                    await query.edit_message_text("⛔ شما دسترسی به این تنظیم ندارید.")
                    return
                new_type = data.split("|")[1]
                if new_type not in ("ip", "phone", "both"):
                    new_type = "both"
                from giso_admin import set_giso_config
                set_giso_config("rate_limit_type", new_type)
                type_fa = {"ip": "فقط IP", "phone": "فقط شماره موبایل", "both": "هر دو"}[new_type]
                await query.edit_message_text(
                    f"✅ نوع محدودیت به «{type_fa}» تغییر کرد\n\n" + _ratelimit_status_text(),
                    reply_markup=_ratelimit_inline_kb(),
                )
                return

            elif data == "rl_back":
                if not _is_super_admin(uid, phone):
                    await query.edit_message_text("⛔ این تنظیم فقط برای سوپرادمین است.")
                    return
                await _show_admin_settings(msg=query.message)
                return

            elif data.startswith("rev_tgl|"):
                # ⭐ پنهان/نمایان کردن نظر (از منوی «🛠 مدیریت → ⭐ نظرات»)
                try:
                    _rv_id = int(data.split("|", 1)[1])
                except (ValueError, IndexError):
                    await query.answer("⚠️ داده نامعتبر.", show_alert=True)
                    return
                if not (_is_super_admin(uid, phone) or _admin_section_visible_for_bot(uid, "reviews")):
                    await query.answer("⛔ دسترسی ندارید.", show_alert=True)
                    return
                try:
                    with get_giso_db_conn() as conn:
                        _row = conn.execute("SELECT status FROM reviews WHERE id=?", (_rv_id,)).fetchone()
                        if not _row:
                            await query.answer("⚠️ نظر پیدا نشد.", show_alert=True)
                            return
                        _new = "hidden" if _row["status"] == "visible" else "visible"
                        conn.execute(
                            "UPDATE reviews SET status=? WHERE id=?",
                            (_new, _rv_id))
                        conn.commit()
                    _fa = "🚫 پنهان شد" if _new == "hidden" else "👁 نمایان شد"
                    try:
                        await query.edit_message_text(
                            (query.message.text or "") + f"\n\n✅ وضعیت نظر #{_fa_num(_rv_id)}: {_fa}")
                    except Exception:
                        pass
                    await query.answer(f"✅ {_fa}")
                except Exception as _e:
                    logger.warning(f"rev_tgl err: {_e}")
                    try:
                        await query.answer("❌ خطا در تغییر وضعیت.", show_alert=True)
                    except Exception:
                        pass
                return

            elif data.startswith("adm_app|"):
                if not _is_super_admin(uid, phone):
                    await query.answer("⛔ فقط سوپرادمین می‌تواند درخواست ادمینی را تأیید کند.", show_alert=True)
                    return
                try:
                    req_id = int(data.split("|", 1)[1])
                except (ValueError, IndexError):
                    await query.edit_message_text("❌ شناسه درخواست نامعتبر است.")
                    return
                try:
                    result = review_admin_request(req_id, approve=True, reviewer_id=uid)
                    if not result or not result.get("ok"):
                        raise RuntimeError("approval_failed")
                    applicant_phone = result.get("phone") or ""
                    applicant_bale = result.get("bale_id") or ""
                    if not str(applicant_bale).isdigit():
                        raise RuntimeError("invalid_applicant_bale_id")
                    from giso.base import clear_admin_demoted
                    clear_admin_demoted(bale_id=str(applicant_bale), phone=str(applicant_phone))
                    _upsert_giso_user(
                        bale_id=applicant_bale, phone=applicant_phone,
                        is_admin=True, pending_request=False,
                    )
                    await query.edit_message_text(
                        f"✅ درخواست #{_fa_num(req_id)} تأیید شد و دسترسی ادمین فعال شد."
                    )
                    try:
                        await context.bot.send_message(
                            chat_id=int(applicant_bale),
                            text="✅ درخواست ادمینی شما تأیید شد. اکنون به پنل ادمین گیسو دسترسی دارید.",
                        )
                    except Exception as notify_exc:
                        logger.warning("admin approval notification failed: %s", notify_exc)
                except ValueError as exc:
                    reason = str(exc)
                    if "already_reviewed" in reason:
                        text_msg = f"⚠️ درخواست #{_fa_num(req_id)} قبلاً بررسی شده است."
                    elif "request_not_found" in reason:
                        text_msg = f"❌ درخواست #{_fa_num(req_id)} پیدا نشد."
                    else:
                        text_msg = "❌ درخواست ادمینی معتبر نیست."
                    await query.edit_message_text(text_msg)
                except Exception as exc:
                    logger.exception("admin request approval failed: %s", exc)
                    await query.edit_message_text("❌ تأیید ادمین کامل نشد؛ هیچ پیام موفقیت کاذبی ثبت نشد.")
                return

            elif data.startswith("adm_rej|"):
                if not _is_super_admin(uid, phone):
                    await query.answer("⛔ فقط سوپرادمین می‌تواند درخواست را رد کند.", show_alert=True)
                    return
                try:
                    req_id=int(data.split("|",1)[1])
                    result=review_admin_request(req_id,approve=False,reviewer_id=uid)
                    applicant_bale=str(result.get("bale_id") or "");applicant_phone=result.get("phone") or ""
                    _upsert_giso_user(bale_id=applicant_bale,phone=applicant_phone,is_admin=False,pending_request=False)
                    await query.edit_message_text(f"❌ درخواست #{_fa_num(req_id)} رد شد.")
                    if applicant_bale.isdigit():
                        try: await context.bot.send_message(chat_id=int(applicant_bale),text="❌ درخواست ادمینی شما توسط سوپرادمین رد شد.")
                        except Exception as notify_exc: logger.warning("admin rejection notification failed: %s",notify_exc)
                except ValueError as exc:
                    reason=str(exc);await query.edit_message_text("⚠️ درخواست قبلاً بررسی شده است." if "already_reviewed" in reason else "❌ درخواست پیدا نشد.")
                except Exception as exc:
                    logger.exception("admin request rejection failed: %s",exc);await query.edit_message_text("❌ رد درخواست کامل نشد.")
                return

            elif data.startswith("adm_del|"):
                admin_id = int(data.split("|")[1])
                admins = list_giso_admins()
                target_admin = next((a for a in admins if int(a.get("id", 0)) == admin_id), None)
                if not target_admin:
                    await query.edit_message_text("❌ ادمین مورد نظر پیدا نشد.")
                    return
                t_phone = normalize_phone(target_admin.get("phone", ""))
                t_bid = str(target_admin.get("bale_id", "") or target_admin.get("telegram_id", ""))
                if t_bid == "1191639507" or t_phone == "+989156012931" or t_phone.endswith("9156012931"):
                    await query.edit_message_text("⛔ حذف سوپرادمین اصلی مجاز نیست.")
                    return
                # حذف کامل و مقاوم (همه فرمت‌های شماره + bale_id + commit صریح)
                try:
                    from giso.panel.modules.admins import remove_giso_admin_completely
                    ok = remove_giso_admin_completely(admin_id)
                except Exception as _e:
                    logger.debug(f"remove_giso_admin_completely fallback: {_e}")
                    delete_giso_admin(admin_id)
                    # ردیف giso_users باید پاک شود تا sync ربات (P10.4) دوباره ادمین نسازد
                    try:
                        with get_giso_db_conn() as _gconn:
                            _gconn.execute("DELETE FROM giso_users WHERE bale_id=?", (t_bid,))
                            _gconn.commit()
                    except Exception as _ge:
                        logger.debug(f"fallback giso_users delete: {_ge}")
                    ok = True
                if not ok:
                    await query.edit_message_text("❌ حذف ادمین انجام نشد.")
                    return
                await query.edit_message_text(f"✅ ادمین #{admin_id} با موفقیت حذف شد.")
                if t_bid and t_bid.isdigit():
                    try:
                        await context.bot.send_message(
                            chat_id=int(t_bid),
                            text="⚠️ دسترسی ادمینی شما لغو شد."
                        )
                    except Exception as e:
                        logger.debug(f"notify removed admin error: {e}")

            elif data in ("adm_phrase_add", "adm_phrase_edit"):
                _user_states[uid] = "waiting_admin_phrase"
                try:
                    await query.message.reply_text("کلمه جدید درخواست ادمینی را ارسال کنید:")
                except Exception:
                    pass
                return

            elif data == "adm_phrase_delete":
                try:
                    from giso_admin import set_giso_config
                    set_giso_config("admin_request_phrase", "")
                    from giso.base import invalidate_giso_config_cache
                    invalidate_giso_config_cache("admin_request_phrase")
                except Exception:
                    pass
                try:
                    await query.edit_message_text("🗑 کلمه ادمینی حذف شد.")
                except Exception:
                    pass
                await _show_admin_phrase_menu(query.message)
                return

            elif data == "adm_mgmt_back":
                try:
                    await query.message.reply_text(
                        "👑 به زیرمنوی مدیریت ادمین‌ها بازگشتید.",
                        reply_markup=_admin_mgmt_kb(),
                    )
                except Exception:
                    pass
                return

            elif data == "user_delete_all_confirm":
                if not _is_super_admin(uid, phone):
                    await query.edit_message_text("⛔ شما دسترسی به حذف کاربران ندارید.")
                    return
                from giso_admin import list_giso_admins
                admin_rows = list_giso_admins()
                adm_phones = {"09156012931", "+989156012931"}
                adm_bids = {"1191639507"}
                for ar in admin_rows:
                    if ar.get("phone"):
                        adm_phones.add(normalize_phone(ar["phone"]))
                    if ar.get("bale_id"):
                        adm_bids.add(str(ar["bale_id"]))
                # حذف کامل و اتمیک هر کاربر (داده‌های وابسته + ردیف‌های هویتی) —
                # روش قدیمی فقط دو ردیف هویتی را حذف می‌کرد و برای کاربرانی که
                # رکورد وابسته داشتند با خطای FK کل عملیات می‌شکست.
                from giso.base import erase_user_data
                targets = {}
                with get_giso_db_conn() as conn:
                    u_rows = conn.execute("SELECT bale_id, phone FROM giso_users WHERE is_admin=0").fetchall()
                    web_rows = conn.execute("SELECT phone FROM giso_web_auth").fetchall()
                for u in u_rows:
                    u_bid = str(u["bale_id"] or "")
                    u_phone_norm = normalize_phone(u["phone"])
                    if u_bid not in adm_bids and u_phone_norm not in adm_phones:
                        targets[(u_bid, u_phone_norm)] = (u_bid, u["phone"] or "")
                for w in web_rows:
                    w_phone_norm = normalize_phone(w["phone"])
                    if w_phone_norm not in adm_phones:
                        # اگر همین شماره در targets هست (هم ربات هم سایت) ادغام می‌شود
                        merged = False
                        for key, (bid, ph) in targets.items():
                            if (not ph and not key[1]) or key[1] == w_phone_norm:
                                targets[key] = (bid, w["phone"] or ph)
                                merged = True
                                break
                        if not merged:
                            targets[("site", w_phone_norm)] = ("", w["phone"] or "")
                del_count = 0
                for _key, (bid, ph) in targets.items():
                    er = erase_user_data(ph, bid)
                    if er.get("ok"):
                        del_count += 1
                await query.edit_message_text(f"✅ {del_count} کاربر حذف شد.")

            elif data == "user_del_cancel":
                await query.edit_message_text("❌ عملیات حذف کاربر لغو شد.")

            elif data.startswith("user_del_req|"):
                if not _is_super_admin(uid, phone):
                    await query.edit_message_text("⛔ شما دسترسی به حذف کاربران ندارید.")
                    return
                target_bid = data.split("|")[1].strip()
                if target_bid == "1191639507":
                    await query.edit_message_text("⛔ امکان حذف ادمین یا سوپرادمین از این بخش وجود ندارد.")
                    return
                info = _lookup_user_delete_info(target_bid)
                if not info:
                    await query.edit_message_text("❌ کاربر مورد نظر پیدا نشد.")
                    return
                if info["is_admin"]:
                    await query.edit_message_text("⛔ امکان حذف ادمین یا سوپرادمین از این بخش وجود ندارد.")
                    return
                await query.edit_message_text(
                    _user_delete_info_text(info),
                    reply_markup=_user_del_confirm_kb(info["bale_id"], info["phone"]),
                )
                return

            elif data.startswith("user_del_confirm|"):
                if not _is_super_admin(uid, phone):
                    await query.edit_message_text("⛔ شما دسترسی به حذف کاربران ندارید.")
                    return
                target_bid = data.split("|")[1].strip()
                if target_bid == "1191639507":
                    await query.edit_message_text("⛔ امکان حذف ادمین یا سوپرادمین از این بخش وجود ندارد.")
                    return
                with get_giso_db_conn() as conn:
                    row = conn.execute("SELECT phone, is_admin FROM giso_users WHERE bale_id=?", (target_bid,)).fetchone()
                    if row and row["is_admin"]:
                        await query.edit_message_text("⛔ امکان حذف ادمین یا سوپرادمین از این بخش وجود ندارد.")
                        return
                    t_phone = row["phone"] if row else ""
                # حذف کامل (سایت + ربات + داده‌های وابسته) — حذف مستقیم دو ردیف
                # هویتی برای کاربرانی که رکورد وابسته داشتند با IntegrityError
                # (foreign_keys) خطا می‌داد و دکمه «کار نمی‌کرد».
                from giso.base import erase_user_data
                er = erase_user_data(t_phone, target_bid)
                if not er.get("ok"):
                    reason = er.get("reason") or ""
                    if reason == "super_admin":
                        await query.edit_message_text("⛔ امکان حذف ادمین یا سوپرادمین از این بخش وجود ندارد.")
                    else:
                        await query.edit_message_text(f"❌ خطا در حذف کاربر: {reason[:120]}")
                    return
                await query.edit_message_text("✅ کاربر با موفقیت حذف شد.")
                return

            elif data.startswith("user_del_confirm_phone|"):
                if not _is_super_admin(uid, phone):
                    await query.edit_message_text("⛔ شما دسترسی به حذف کاربران ندارید.")
                    return
                t_phone = data.split("|")[1].strip()
                np_phone = normalize_phone(t_phone)
                if np_phone == "09156012931" or np_phone == "+989156012931" or np_phone.endswith("9156012931"):
                    await query.edit_message_text("⛔ امکان حذف ادمین یا سوپرادمین از این بخش وجود ندارد.")
                    return
                # حذف کامل (سایت + ربات + داده‌های وابسته) — به‌جای دو DELETE مستقیم
                # که برای کاربران دارای رکورد وابسته با خطای FK شکست می‌خورد.
                from giso.base import erase_user_data
                er = erase_user_data(t_phone)
                if not er.get("ok"):
                    await query.edit_message_text(f"❌ خطا در حذف کاربر: {(er.get('reason') or '')[:120]}")
                    return
                await query.edit_message_text("✅ کاربر با موفقیت حذف شد.")
                return
        except Exception as e:
            logger.error(f"handle_callback error: {e}")
            try:
                await query.edit_message_text("❌ خطا در اجرای عملیات.")
            except Exception:
                pass

    async def _role_after_contact(uid, phone) -> str:
        info = _giso_lookup(uid, phone)
        if info["is_admin"]:
            return "admin"
        if info["is_pending"]:
            return "pending"
        return "user"

    def _runtime_role_for_user(uid, phone, existing=None):
        return resolve_actor_role(
            user_id=uid,
            phone=phone,
            is_admin=bool(existing and existing.get("is_admin")),
        )

    def _get_admin_ai_context(uid, phone, role: str):
        stats = _get_admin_dashboard_stats()
        role = (role or "admin").strip().lower()
        first_name = "مدیر"
        try:
            user_rec = _get_giso_user(uid) or {}
            first_name = (user_rec.get("first_name") or "").strip() or first_name
        except Exception:
            pass
        context = {
            "admin_name": first_name,
            "admin_phone": phone or "",
            "admin_role": "سوپرادمین" if role == "super" else "ادمین",
            "today_analyses": stats.get('today_analyses', 0),
            "today_hair_sales": stats.get('today_hair_sales', 0),
            "today_shop_orders": stats.get('today_shop_orders', 0),
            "today_new_users": stats.get('today_new_users', 0),
            "pending_hair_reviews": stats.get('pending_hair_reviews', 0),
            "pending_shop_orders": stats.get('pending_shop_orders', 0),
            "pending_tickets": stats.get('pending_tickets', 0),
            "pending_consultations": stats.get('pending_consultations', 0),
            "pending_product_requests": stats.get('pending_product_requests', 0),
            "new_reviews": stats.get('new_reviews', 0),
            "priorities": stats.get('priorities', []) or [],
        }
        context["stats_summary"] = (
            f"کاربر جدید امروز: {context['today_new_users']} | "
            f"آنالیز امروز: {context['today_analyses']} | "
            f"سفارش فروشگاه امروز: {context['today_shop_orders']} | "
            f"درخواست فروش مو امروز: {context['today_hair_sales']} | "
            f"تیکت‌های در انتظار: {context['pending_tickets']} | "
            f"درخواست‌های مشاوره در انتظار: {context['pending_consultations']}"
        )
        context["priority_text"] = "\n".join(context["priorities"]) if context["priorities"] else "مورد بحرانی ثبت نشده است."
        return context

    def _build_admin_consultant_prompt(role: str, context: dict, history_text: str, user_message: str) -> str:
        role_title = "سوپرادمین" if role == "super" else "ادمین"
        guidance = (
            "می‌توانی درباره آمار، گزارش‌های امروز، کاربران جدید، سفارش‌ها، تیکت‌های باز، "
            "درخواست‌های مشاوره، فروش مو، سلامت عملیاتی و اولویت‌های رسیدگی پاسخ بده. "
            "اگر سوال کلی بود، جمع‌بندی مدیریتی بده و در پایان یک پیشنهاد اقدام بعدی هم مطرح کن."
        )
        return (
            f"تو {get_display_name()} هستی و الان با {role_title} گیسو صحبت می‌کنی.\n"
            f"نام مدیر: {context.get('admin_name', 'مدیر')}\n"
            f"شماره: {context.get('admin_phone', '')}\n"
            f"سمت: {context.get('admin_role', role_title)}\n\n"
            f"خلاصه وضعیت امروز:\n{context.get('stats_summary', '')}\n\n"
            f"اولویت‌های مهم:\n{context.get('priority_text', '')}\n\n"
            f"تعداد تیکت‌های در انتظار: {context.get('pending_tickets', 0)}\n"
            f"تعداد درخواست‌های مشاوره در انتظار: {context.get('pending_consultations', 0)}\n"
            f"تعداد سفارش‌های در انتظار: {context.get('pending_shop_orders', 0)}\n"
            f"تعداد فروش مو در انتظار بررسی: {context.get('pending_hair_reviews', 0)}\n"
            f"محصولات درخواستی معطل: {context.get('pending_product_requests', 0)}\n\n"
            f"قابلیت‌های مورد انتظار:\n{guidance}\n\n"
            f"تاریخچه این جلسه:\n{history_text or 'شروع گفتگو'}\n\n"
            f"پیام جدید {role_title}:\n{user_message}\n\n"
            "با لحن انسانی، همراه، خوش‌بیان و مدیریتی پاسخ بده. "
            "اگر لازم بود پاسخ را در قالب: جمع‌بندی، نکات مهم، و پیشنهاد اقدام بعدی بنویس."
        )

    async def _send_smart_welcome_message(msg, uid, role: str, force: bool = False):
        if uid is None:
            return False
        try:
            if not force and not should_show_welcome(uid):
                return False
            payload = get_smart_welcome_context(uid, role)
            kb = _consultant_ai_inline_kb(role) if payload.get("show_button") else None
            await msg.reply_text(payload.get("text") or "سلام!", reply_markup=kb)
            mark_welcome_shown(uid)
            touch_user_activity(uid)
            return True
        except Exception as e:
            logger.error(f"_send_smart_welcome_message: {e}")
            return False

    async def _send_consultant_ai_guidance(msg, role: str):
        if not is_chat_enabled():
            await msg.reply_text(OFF_MESSAGE)
            return
        if not _role_has_consultant_ai(role):
            await msg.reply_text(NO_ACCESS_MESSAGE)
            return
        await msg.reply_text(
            "سلام! 🌸\n\n"
            "برای صحبت با مشاور هوشمند گیسو،\n"
            "لطفاً از دکمه زیر استفاده کن 👇\n\n"
            f"[{CONSULTANT_AI_LABEL}]\n\n"
            "یا از منوی اصلی همین گزینه رو انتخاب کن.",
            reply_markup=_consultant_ai_inline_kb(role),
        )

    async def _start_consultant_ai_chat(entry_target, context, uid, role: str, is_query: bool = False):
        if not is_chat_enabled():
            text = OFF_MESSAGE
            kb = None
        else:
            access = check_role_access(role, section="consultant_chat")
            if not access.get("allowed"):
                text = access.get("message") or NO_ACCESS_MESSAGE
                kb = None
            else:
                _set_consultant_ai_active(context, True)
                touch_user_activity(uid)
                if role == "super":
                    admin_ctx = _get_admin_ai_context(uid, _get_user_phone(uid) or "", role)
                    admin_name = admin_ctx.get("admin_name") or "دوست من"
                    text = (
                        f"👑 {admin_name} جان خوش اومدی! من {get_display_name()} هستم و از اینجا به بعد مثل یک همکار همراه کنارت می‌مونم.\n\n"
                        f"{get_superadmin_action_capabilities_text()}\n\n"
                        "هر جا فقط گزارش یا جمع‌بندی بخوای مستقیم میارم؛ هر جا تغییر واقعی بخوای، اول پیش‌نمایش می‌دم و بعد از تأییدت اجرا می‌کنم.\n\n"
                        "برای پایان گفتگو /end بزن"
                    )
                elif role == "admin":
                    text = (
                        f"🎉 عالیه! من {get_display_name()} هستم؛ همراه هوشمندت برای کارهای عملیاتی گیسو.\n\n"
                        "می‌تونی درباره تیکت‌ها، درخواست‌های امروز، اولویت‌های رسیدگی و گزارش‌های سریع سؤال بپرسی.\n\n"
                        "برای پایان گفتگو /end بزن"
                    )
                else:
                    report = _uact.consultant_status_report(uid, "")
                    text = (
                        f"🎉 عالیه! من {get_display_name()} هستم؛ دستیار هوشمند گیسو.\n\n"
                        + (report + "\n\n" if report else "")
                        + "می‌تونم دربارهٔ همهٔ کارهایت بهت گزارش و پیشنهاد بدم:\n"
                        "🔬 تحلیل مو و پوست و برنامه‌ات | 💇 فروش مو | 🏪 بازارچه | 🛍 سفارش‌ها\n"
                        "💰 کیف پول و مأموریت‌ها | 🏥 مرکز زیبایی | 🎫 تیکت‌ها | 🔔 اعلان‌ها\n\n"
                        "هر سؤالی دربارهٔ وضعیتت یا خدمات داری همین‌جا بپرس؛ قدم‌به‌قدم همراهت هستم 💫\n\n"
                        "برای پایان گفتگو /end بزن"
                    )
                kb = _consultant_ai_end_kb()
        try:
            if is_query:
                await entry_target.edit_message_text(text, reply_markup=kb)
            else:
                await entry_target.reply_text(text, reply_markup=kb)
        except Exception:
            try:
                await entry_target.message.reply_text(text, reply_markup=kb)
            except Exception:
                pass

    async def _show_panel(msg, fname: str, role: str, extra: str = "", uid=None):
        if role == "admin":
            await msg.reply_text(
                f"💈 سلام {fname}! به پنل ادمین گیسو خوش آمدید.\n\n"
                "از این پنل می‌توانید سفارش‌ها، محصولات و درخواست‌های آنالیز را مدیریت کنید.\n"
                "در حال حاضر پنل کامل ادمین از طریق سایت گیسو در دسترس است.\n"
                f"{extra}",
                reply_markup=_admin_kb(uid),
            )
        elif role == "pending":
            await msg.reply_text(
                f"💇‍♀️ سلام {fname}! درخواست ادمینی شما در انتظار بررسی است.\n\n"
                "پس از تأیید ادمین اصلی، پنل ادمین برای شما فعال می‌شود.\n"
                "با ارسال «وضعیت درخواست ادمین» می‌توانید آخرین وضعیت را ببینید.",
                reply_markup=_user_kb(pending=True),
            )
        else:
            await msg.reply_text(
                f"💇‍♀️ سلام {fname}! به ربات گیسو خوش آمدید.\n\n"
                "از این ربات می‌توانید برای فروش مو، آنالیز هوشمند مو/صورت و خرید محصولات "
                "زیبایی استفاده کنید. سایت گیسو همیشه در دسترس است.\n"
                f"{extra}",
                reply_markup=_user_kb(pending=False),
            )

    async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
        # پرداخت آنی بله: deep-link «/start pay_<token>» → فاکتور (ماژول bot_balepay)
        if context.args and str(context.args[0]).startswith("pay_"):
            from giso.bot_balepay import handle_pay_start
            if await handle_pay_start(update, context):
                return
        user = update.effective_user
        uid = user.id if user else None
        fname = (user.first_name if user else "") or "کاربر"
        existing = _get_giso_user(uid) if uid else None
        # مرحله ۶: ادمین اختصاصی (special) — فقط وقتی شماره را به اشتراک گذاشته باشد فعال می‌شود.
        # اگر هنوز شماره نداده، مثل هر کاربر دیگری دکمه‌ی اشتراک‌گذاری شماره نشان داده می‌شود.
        if existing and existing.get("contact_shared") and \
                _is_special_admin_bot(uid, existing.get("phone", "")) and \
                not _is_super_admin(uid, existing.get("phone", "")):
            _upsert_giso_user(
                bale_id=uid,
                phone=existing.get("phone", ""),
                first_name=fname,
                username=(user.username or "") if user else "",
                is_admin=True,
                contact_shared=True,
                pending_request=False,
            )
            _set_consultant_ai_active(context, False)
            await update.message.reply_text(await _special_welcome_text(), reply_markup=_special_menu_kb())
            return
        if _is_super_admin(uid, (existing.get("phone", "") if existing else "")):
            _upsert_giso_user(
                bale_id=uid,
                phone=(existing.get("phone", "09156012931") if existing else "09156012931"),
                first_name=fname,
                username=(user.username or "") if user else "",
                is_admin=True,
                contact_shared=True,
                pending_request=False
            )
            _set_consultant_ai_active(context, False)
            await _send_smart_welcome_message(update.message, uid, "super", force=True)
            await update.message.reply_text("از منوی زیر ادامه بده 👇", reply_markup=_admin_kb(uid))
            return

        if existing and existing.get("contact_shared"):
            fresh = await _role_after_contact(uid, existing.get("phone", ""))
            _upsert_giso_user(uid, is_admin=(fresh == "admin"),
                              pending_request=(fresh == "pending"))
            _set_consultant_ai_active(context, False)
            runtime_role = "admin" if fresh == "admin" else "user"
            if await _send_smart_welcome_message(update.message, uid, runtime_role, force=True):
                if fresh == "admin":
                    await update.message.reply_text("از منوی ادمین ادامه بده 👇", reply_markup=_admin_kb(uid))
                else:
                    await update.message.reply_text("از منوی زیر ادامه بده 👇", reply_markup=_user_kb(pending=(fresh == "pending")))
                return
            if fresh == "pending":
                await _show_panel(update.message, fname, "pending", uid=uid)
            elif fresh == "admin":
                await _show_panel(update.message, fname, "admin", uid=uid)
            else:
                await _show_panel(update.message, fname, "user", uid=uid)
            # راهنمای بار اول: خوش‌آمد کامل + معرفی کوتاه بخش‌ها (فقط کاربر عادی)
            if not _is_super_admin(uid, existing.get("phone", "") or "") and runtime_role == "user":
                try:
                    await _uact.send_first_contact_welcome(
                        update.message, existing.get("phone", "") or "",
                        fname, pending=False,
                    )
                except Exception as _e_wel:
                    logger.debug(f"first-contact welcome: {_e_wel}")
            return

        kb = ReplyKeyboardMarkup(
            [[KeyboardButton("📱 ارسال شماره تماس", request_contact=True)]],
            resize_keyboard=True,
            one_time_keyboard=True,
        )
        await update.message.reply_text(
            f"💇‍♀️ سلام {fname}! به ربات گیسو خوش آمدید.\n\n"
            "برای استفاده از ربات، لطفاً شماره تماس خود را با زدن دکمه زیر به اشتراک بگذارید:\n"
            "⚠️ شماره باید متعلق به همین حساب بله باشد.",
            reply_markup=kb,
        )

    async def handle_contact(update: Update, context: ContextTypes.DEFAULT_TYPE):
        msg = update.effective_message
        if not msg or not msg.contact:
            return
        user = update.effective_user
        uid = user.id if user else None
        contact = msg.contact
        if uid is None:
            await msg.reply_text("❌ خطا در شناسایی کاربر.")
            return
        if contact.user_id is not None and int(contact.user_id) != int(uid):
            await msg.reply_text(
                "❌ لطفاً شماره تماس خودتان را از دکمه زیر ارسال کنید "
                "(شمارهٔ دیگران پذیرفته نمی‌شود)."
            )
            return
        phone = normalize_phone(contact.phone_number)
        if not phone:
            await msg.reply_text(
                "❌ شمارهٔ دریافت‌شده نامعتبر است. لطفاً شماره موبایل ایرانی معتبر ارسال کنید."
            )
            return

        info = _giso_lookup(uid, phone)
        role = "admin" if info["is_admin"] else ("pending" if info["is_pending"] else "user")
        _upsert_giso_user(
            bale_id=uid,
            phone=phone,
            first_name=(user.first_name or "") if user else "",
            username=(user.username or "") if user else "",
            is_admin=(role == "admin"),
            contact_shared=True,
            pending_request=(role == "pending"),
        )
        _set_consultant_ai_active(context, False)
        # مرحله ۶: ادمین اختصاصی (special) — پس از اشتراک‌گذاریِ شماره‌ی خودش فعال می‌شود.
        if _is_special_admin_bot(uid, phone) and not _is_super_admin(uid, phone):
            _upsert_giso_user(
                bale_id=uid, phone=phone,
                first_name=(user.first_name or "") if user else "",
                username=(user.username or "") if user else "",
                is_admin=True, contact_shared=True, pending_request=False,
            )
            _set_consultant_ai_active(context, False)
            _special_chat_active.discard(uid)
            await msg.reply_text(await _special_welcome_text(), reply_markup=_special_menu_kb())
            return
        runtime_role = "super" if _is_super_admin(uid, phone) else ("admin" if role == "admin" else "user")
        sent = await _send_smart_welcome_message(msg, uid, runtime_role, force=True)
        if sent:
            if role == "admin":
                await msg.reply_text("از منوی ادمین ادامه بده 👇", reply_markup=_admin_kb(uid))
            else:
                await msg.reply_text("از منوی زیر ادامه بده 👇", reply_markup=_user_kb(pending=(role == "pending")))
        elif role == "admin":
            await _show_panel(msg, user.first_name or "کاربر", role, uid=uid)
        else:
            await _show_panel(msg, user.first_name or "کاربر", "user", uid=uid)

    async def _refresh_pending(uid, phone, user_rec):
        try:
            # شرط: سوپرادمین نباید درخواست ادمین ثبت کنه
            if _is_super_admin(uid, phone):
                return "admin", {"already_admin": True}
            # لیست سیاه: ادمینِ حذف‌شده نباید با ارسال کلمه دوباره ادمین شود
            try:
                from giso.base import is_admin_demoted
                if is_admin_demoted(bale_id=str(uid), phone=phone):
                    return "demoted", {"already_admin": False}
            except Exception:
                pass
            # شرط: ادمین‌های فعال نتوانند درخواست جدید بدهند
            # اصلاح 2026-08-23: قبلاً «existing» بود که نه پارامتر این تابع بود و نه
            # در محدودهٔ _run_async تعریف شده بود → NameError → برای هر کاربر عادی
            # «❌ خطا در ثبت درخواست» برمی‌گشت و درخواست اصلاً ثبت نمی‌شد.
            if user_rec and user_rec.get("is_admin"):
                return "admin", {"already_admin": True}
            # شرط: کاربرانی که قبلاً درخواست دادند، دوباره ثبت نشود
            from giso_admin import has_pending_admin_request
            if has_pending_admin_request(phone=phone or "", bale_id=str(uid)):
                return "already_pending", {"already_pending": True}
            from giso_admin import create_admin_request
            r = create_admin_request(phone=phone, bale_id=str(uid))
            if r.get("already_admin"):
                return "admin", r
            if r.get("already_pending"):
                return "already_pending", r
            return ("ok" if r.get("ok") else "error"), r
        except Exception as e:
            logger.debug("create_admin_request: %s", e)
            return "error", {}

    async def _process_admin_keyword(uid, phone, fname, user_rec, msg, context):
        """پردازش کلمه‌ی درخواست ادمین: ثبت درخواست + اعلان سوپرادمین.

        اصلاح 2026-08-23: این بلاک قبلاً فقط در انتهای handle_text اجرا می‌شد؛
        یعنی اگر کاربر در گفتگوی مشاور AI (consultant_ai_active) بود، کلمهٔ
        ادمین به AI برده می‌شد و هیچ‌وقت ثبت نمی‌شد. اکنون همین منطق از هر دو
        نقطه (پیش از گفتگوی AI و انتهای handle_text) قابل فراخوانی است.
        """
        status, r = await _refresh_pending(uid, phone, user_rec)
        if status == "admin":
            _upsert_giso_user(uid, is_admin=True, pending_request=False)
            await _show_panel(msg, fname, "admin",
                             extra="\n✅ شما هم‌اکنون ادمین گیسو هستید.", uid=uid)
            return
        if status == "demoted":
            # کاربری که قبلاً ادمین بوده و حذف شده — فقط پنل کاربر عادی
            await _show_panel(msg, fname, "user", uid=uid)
            return
        if status in ("ok", "already_pending"):
            _upsert_giso_user(uid, pending_request=True)
            msg_txt = "✅ درخواست ادمینی شما ثبت شد و پس از بررسی اعلام می‌شود." if status == "ok" else "⏳ درخواست ادمینی شما قبلاً ثبت شده و در انتظار بررسی است."
            await msg.reply_text(msg_txt, reply_markup=_user_kb(pending=True))
            try:
                from telegram import InlineKeyboardButton, InlineKeyboardMarkup
                req_id = r.get("id", 0)
                kb = InlineKeyboardMarkup([
                    [InlineKeyboardButton("✅ تایید", callback_data=f"adm_app|{req_id}"),
                     InlineKeyboardButton("❌ رد", callback_data=f"adm_rej|{req_id}")]
                ])
                notif_txt = (f"🔔 درخواست ادمینی جدید:\n\n"
                             f"👤 نام: {fname}\n"
                             f"📱 شماره تماس: {phone}\n"
                             f"🆔 شناسه بله/تلگرام: {uid}\n"
                             f"⏰ زمان: {to_shamsi(r.get('requested_at', time.strftime('%Y-%m-%d %H:%M:%S')))}\n"
                             f"🔢 شماره درخواست: #{req_id}")
                await context.bot.send_message(chat_id=1191639507, text=notif_txt, reply_markup=kb)
            except Exception as ex:
                logger.warning(f"Could not notify superadmin: {ex}")
            return

        await msg.reply_text("❌ خطا در ثبت درخواست. لطفاً بعداً دوباره تلاش کنید.")

    async def handle_channel_post(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """🆕 پست‌های جدید کانال بله فروشگاه → ایمپورت هوشمند محصول (با تأیید ادمین)."""
        try:
            from giso import channel_importer as _ci
            await _ci.on_channel_post(update, context)
        except Exception as _e_cp:
            logger.warning(f"handle_channel_post error: {_e_cp}")

    async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
        user = update.effective_user
        uid = user.id if user else None
        # فیکس نشت حافظه: ثبت تعامل + هرس دوره‌ای state (هیچ هندلری تغییر نمی‌کند)
        _touch_state_activity(uid)
        _maybe_cleanup_stale_states()
        existing = _get_giso_user(uid) if uid else None
        msg = update.effective_message
        text = (msg.text or "").strip()
        # فقط انتخاب‌های منوی اصلی ثبت می‌شوند؛ متن گفتگو یا پیام کاربر هرگز ذخیره نمی‌شود.
        _tracked_bot_actions={"📖 راهنما","🔍 آنالیز هوشمند","💇 فروش مو","🏪 بازارچه مو","🛍 فروشگاه","🏥 مرکز زیبایی من",CONSULTANT_AI_LABEL,"💬 مشاور","💬 پشتیبانی","🎧 پشتیبانی","💰 کیف پول من","💰 کیف پول","🎯 مأموریت","👤 پروفایل من","👤 پروفایل","🔔 اعلان‌های من"}
        if text in _tracked_bot_actions:
            try:
                from giso.monitoring_events import record_batch
                record_batch([{"type":"action_click","page":"/bot","key":text,"device":"بله"}],"bot",str(uid or ""))
            except Exception:pass
        # ایمپورت محلی برای استفاده در منوهای inline (چون import های دیگری در پایین تابع
        # نام‌های InlineKeyboardButton/Markup را برای کل تابع لوکال می‌کنند)
        from telegram import InlineKeyboardButton as _ikb, InlineKeyboardMarkup as _ikm
        # عبارت درخواست ادمین بالاترین اولویت متنی را دارد و نباید توسط هیچ state،
        # پیام خوش‌آمد یا مشاور هوشمند مصرف شود. کاربر باید قبلاً شماره را به اشتراک گذاشته باشد.
        if existing and existing.get("contact_shared") and _is_admin_request_phrase(text):
            _set_consultant_ai_active(context, False)
            await _process_admin_keyword(
                uid, existing.get("phone") or "", user.first_name or "کاربر",
                existing, msg, context,
            )
            return
        # گارد مکمل (۱۴۰۵-۰۶-۱۴): کلمهٔ درخواست ادمین در هیچ حالتی به مشاور AI یا
        # stateهای دیگر نمی‌رسد. کاربری که هنوز شماره‌اش را ثبت نکرده، به جای جواب AI
        # به اشتراک شماره هدایت می‌شود تا درخواستش برای سوپرادمین قابل ثبت باشد.
        if _is_admin_request_phrase(text):
            _set_consultant_ai_active(context, False)
            await msg.reply_text(
                "🔐 برای ثبت درخواست ادمینی، ابتدا شمارهٔ تماس‌ات را با دکمهٔ زیر "
                "به اشتراک بگذار؛ بعد دوباره همان کلمه را بفرست.",
                reply_markup=ReplyKeyboardMarkup(
                    [[KeyboardButton("📱 ارسال شماره تماس", request_contact=True)]],
                    resize_keyboard=True,
                ),
            )
            return
        # 🆕 دریافت متن نظر سفارش فروشگاه (state ماشین ربات) — قبل از هر بخش
        if str(_user_states.get(uid, "")).startswith("waiting_shop_rev_txt_"):
            if await _handle_shop_review_state(
                msg, text, uid, (existing.get("phone", "") if existing else ""), _user_states
            ):
                return
        if _is_super_admin(uid, (existing.get("phone", "") if existing else "")):
            if not existing or not existing.get("is_admin"):
                _upsert_giso_user(
                    bale_id=uid,
                    phone=(existing.get("phone", "09156012931") if existing else "09156012931"),
                    first_name=(user.first_name or "") if user else "",
                    username=(user.username or "") if user else "",
                    is_admin=True,
                    contact_shared=True,
                    pending_request=False
                )
                existing = _get_giso_user(uid)
        if not existing or not existing.get("contact_shared"):
            kb = ReplyKeyboardMarkup(
                [[KeyboardButton("📱 ارسال شماره تماس", request_contact=True)]],
                resize_keyboard=True, one_time_keyboard=True,
            )
            await msg.reply_text(
                "برای استفاده از ربات گیسو ابتدا شماره تماس خود را با دکمه زیر به اشتراک بگذارید:",
                reply_markup=kb,
            )
            return

        # ═══ مرحله ۶: دستیار هوشمند «آقا رضا» — فقط برای ادمین اختصاصی (special) ═══
        # دکمه‌ی اختصاصی یا ادامه‌ی گفتگوی فعال؛ هیچ‌کدام از جریان‌های عادی ادمین/کاربر را لمس نمی‌کند.
        _sp_phone = (existing.get("phone", "") or "") if existing else ""
        if await handle_special_assistant_bot_text(msg, context, update, uid, _sp_phone, _special_chat_active):
            return

        # ═══ لغو بارگذاری backup ═══
        _ud_cancel = getattr(context, "user_data", None)
        if isinstance(_ud_cancel, dict) and _ud_cancel.get("awaiting_backup_file") and text == "/cancel":
            _ud_cancel.pop("awaiting_backup_file", None)
            await msg.reply_text("❌ بارگذاری backup لغو شد.")
            return

        # ═══ دریافت آدرس جدید سایت ═══
        _ud = getattr(context, "user_data", None)
        _awaiting_url = bool(_ud and isinstance(_ud, dict) and _ud.get('awaiting_giso_url'))
        if _awaiting_url:
            if text == '/cancel':
                context.user_data.pop('awaiting_giso_url', None)
                await msg.reply_text("❌ لغو شد.")
                return
            if not _is_super_admin(uid, existing.get("phone") or ""):
                context.user_data.pop('awaiting_giso_url', None)
                await msg.reply_text("⛔ فقط سوپرادمین")
                return
            success, message = _set_giso_site_url(text)
            context.user_data.pop('awaiting_giso_url', None)
            if success:
                new_url = text.strip().rstrip('/')
                test_result = await _to_thread(_test_giso_site_url, new_url)
                response = (
                    f"✅ *آدرس ذخیره شد*\n\n"
                    f"📍 آدرس جدید: `{new_url}`\n\n"
                )
                if test_result['success']:
                    response += f"✅ تست: در دسترس ({test_result['status_code']})\n"
                    response += f"⏱ زمان: {test_result['time_ms']}ms\n\n"
                    response += "همه لینک‌ها از این آدرس استفاده می‌کنن."
                else:
                    response += f"⚠️ *هشدار:* سایت الان در دسترس نیست\n"
                    response += f"({test_result['message']})\n\n"
                    response += "ولی آدرس ذخیره شد. اگه بعداً در دسترس شد، کار می‌کنه."
                await msg.reply_text(response, parse_mode='Markdown')
            else:
                await msg.reply_text(
                    f"❌ {message}\n\n"
                    "لطفاً دوباره تلاش کن یا /cancel بزن."
                )
            return

        _ud_state = getattr(context, "user_data", None)
        _ud_state = _ud_state if isinstance(_ud_state, dict) else {}

        # ═══ ویرایش موضعی پروفایل کاربر — پیش از AI و سایر stateها ═══
        profile_state = str(_user_states.get(uid, "") or "")
        if profile_state.startswith("user_profile_edit|"):
            field = profile_state.split("|", 1)[1]
            if text in ("/cancel", "لغو", "❌ لغو"):
                _user_states.pop(uid, None)
                _ud_state.pop("profile_pending", None)
                await msg.reply_text("ویرایش پروفایل لغو شد.", reply_markup=_user_kb())
                return
            from giso.user_profile_service import PROFILE_FIELDS
            if field not in {"first_name", "last_name", "city"}:
                _user_states.pop(uid, None)
                await msg.reply_text("فیلد پروفایل معتبر نیست.", reply_markup=_user_kb())
                return
            label, limit = PROFILE_FIELDS[field]
            clear_requested = text.strip() in ("-", "حذف", "پاک شود", "خالی")
            value = "" if clear_requested else " ".join(text.split()).strip()[:limit]
            if not value and not clear_requested:
                await msg.reply_text(f"مقدار {label} خالی است؛ مقدار جدید را بفرستید، برای پاک‌کردن «حذف» یا برای لغو /cancel بزنید.")
                return
            _ud_state["profile_pending"] = {"field": field, "value": value}
            _user_states[uid] = f"user_profile_confirm|{field}"
            confirm_kb = _ikm([[
                _ikb("✅ تأیید", callback_data=f"upro|save|{field}"),
                _ikb("❌ لغو", callback_data="upro|cancel"),
            ]])
            shown_value = value or "خالی"
            await msg.reply_text(
                f"{label} به «{shown_value}» تغییر کند؟", reply_markup=confirm_kb,
            )
            return
        if profile_state.startswith("user_profile_confirm|"):
            await msg.reply_text("لطفاً از دکمه‌های تأیید یا لغو استفاده کنید.")
            return

        # ═══ ثبت عبارت ادمینی جدید (سوپر) — پیش از چت مشاور AI ═══
        # (اصلاح ۱۴۰۵-۰۶-۱۴: این state قبلاً «بعد» از بلوک چت AI بود و اگر سوپرادمین
        # در گفتگوی مشاور بود، عبارت جدید به AI می‌رفت و هرگز ذخیره نمی‌شد.)
        if _user_states.get(uid) == "waiting_admin_phrase":
            if _is_super_admin(uid, phone):
                try:
                    from giso_admin import set_giso_config
                    set_giso_config("admin_request_phrase", text)
                    from giso.base import invalidate_giso_config_cache
                    invalidate_giso_config_cache("admin_request_phrase")
                    _user_states.pop(uid, None)
                    await msg.reply_text(f"✅ کلمه ادمینی ذخیره شد: {text}")
                    await _show_admin_phrase_menu(msg)
                except Exception as e:
                    logger.error(f"set phrase error: {e}")
                    _user_states.pop(uid, None)
                    await msg.reply_text("❌ خطا در ذخیره عبارت.", reply_markup=_admin_mgmt_kb())
                return
            _user_states.pop(uid, None)
            await msg.reply_text("⛔ فقط سوپرادمین می‌تواند کلمه ادمینی را تنظیم کند.")
            return

        # ═══ چت مشاور هوشمند فعال ═══
        # ═══ کلمه‌ی درخواست ادمین — حتی در میانه‌ی گفتگوی AI هم باید کار کند ═══
        # (اصلاح 2026-08-23: قبلاً اگر کاربر در گفتگوی مشاور AI بود، همهٔ پیام‌ها —
        # حتی کلمهٔ درخواست ادمین — به AI برده می‌شد و درخواست ثبت نمی‌شد.)
        if _is_consultant_ai_active(context) and _is_admin_request_phrase(text):
            _set_consultant_ai_active(context, False)
            await _process_admin_keyword(
                uid, existing.get("phone") or "", user.first_name or "کاربر",
                existing, msg, context)
            return

        if _is_consultant_ai_active(context):
            if text == '/end':
                _set_consultant_ai_active(context, False)
                await msg.reply_text("گفتگو پایان یافت 👋 هر وقت خواستی برگرد")
                return

            phone_now = _get_user_phone(uid)
            if not phone_now:
                await msg.reply_text("⚠️ خطا در دسترسی به اطلاعات.")
                return

            try:
                await context.bot.send_chat_action(
                    chat_id=update.effective_chat.id, action="typing"
                )
            except Exception:
                pass

            active_role = _runtime_role_for_user(uid, phone_now, existing)
            _save_bot_chat_message(uid, 'user', text)

            if active_role == "super":
                action_result = process_superadmin_request(uid, phone_now, text)
                if action_result.get("handled"):
                    response = action_result.get("text") or "—"
                    _save_bot_chat_message(uid, 'assistant', response)
                    if action_result.get("mode") == "pending":
                        await msg.reply_text(
                            f"👩 *{get_display_name()}:*\n\n{response}",
                            reply_markup=_super_action_confirm_kb(int(action_result.get("pending_id") or 0)),
                            parse_mode='Markdown'
                        )
                    else:
                        await send_long_message(
                            context.bot, msg.chat_id,
                            f"👩 *{get_display_name()}:*\n\n{response}",
                            message=msg,
                            reply_markup=_consultant_ai_end_kb(),
                            parse_mode='Markdown'
                        )
                    return

            response = await _ask_consultant_bot(uid, phone_now, text, role=active_role, bot=context.bot, chat_id=update.effective_chat.id)
            _save_bot_chat_message(uid, 'assistant', response)

            await send_long_message(
                context.bot, msg.chat_id,
                f"👩 *{get_display_name()}:*\n\n{response}",
                message=msg,
                reply_markup=_consultant_ai_end_kb(),
                parse_mode='Markdown'
            )
            return

        # ═══ ثبت پیام پشتیبانی (کاربر) ═══
        if _ud_state.get('awaiting_support_message'):
            if text == '/cancel':
                _ud_state.pop('awaiting_support_message', None)
                await msg.reply_text("❌ لغو شد.")
                return
            if len(text) < 5:
                await msg.reply_text("⚠️ پیام خیلی کوتاهه. لطفاً کامل‌تر بنویس.")
                return
            phone_now = _get_user_phone(uid)
            user_name = 'کاربر'
            try:
                _fn = getattr(user, 'first_name', None)
                if isinstance(_fn, str) and _fn.strip():
                    user_name = _fn
            except Exception:
                pass
            ticket_id = _create_support_ticket(uid, user_name, phone_now or '', text)
            if ticket_id:
                _ud_state.pop('awaiting_support_message', None)
                await msg.reply_text(
                    f"✅ *پیامت ثبت شد*\n\n"
                    f"🎫 شماره تیکت: #{ticket_id}\n"
                    f"📅 ادمین در اسرع وقت جواب میده.\n\n"
                    f"برای مشاهده وضعیت، از منوی پشتیبانی «تیکت‌های من» رو ببین.",
                    parse_mode='Markdown'
                )
                await _notify_admins_new_ticket(context, ticket_id, user_name, phone_now or '', text)
            else:
                await msg.reply_text("❌ خطا در ثبت. لطفاً بعداً تلاش کن.")
            return

        phone = existing.get("phone") or ""
        fname = user.first_name or "کاربر"
        runtime_role = _runtime_role_for_user(uid, phone, existing)
        should_show_rewelcome = should_show_welcome(uid)
        touch_user_activity(uid)

        # ═══ پاسخ ادمین به تیکت پشتیبانی ═══
        if _is_giso_admin(uid) and _ud_state.get('replying_ticket'):
            if text == '/cancel':
                _ud_state.pop('replying_ticket', None)
                await msg.reply_text("❌ لغو شد.")
                return
            ticket_id = _ud_state.pop('replying_ticket')
            from datetime import datetime
            try:
                conn = get_giso_db_conn()
                row = conn.execute(
                    "SELECT user_bale_id, message FROM giso_support_tickets WHERE id=?",
                    (ticket_id,)
                ).fetchone()
                if row:
                    user_bale_id = row[0]
                    original_message = row[1] or ''
                    conn.execute(
                        "UPDATE giso_support_tickets SET admin_reply=?, admin_bale_id=?, "
                        "status='replied', replied_at=? WHERE id=?",
                        (text, str(uid), datetime.now().strftime('%Y-%m-%d %H:%M:%S'), ticket_id)
                    )
                    conn.commit()
                    try:
                        await context.bot.send_message(
                            chat_id=int(user_bale_id),
                            text=(
                                f"💬 *پاسخ ادمین به تیکت #{ticket_id}*\n\n"
                                f"❓ پیام شما:\n{original_message[:200]}\n\n"
                                f"✅ پاسخ:\n{text}"
                            ),
                            parse_mode='Markdown'
                        )
                        await msg.reply_text(
                            f"✅ پاسخ برای کاربر ارسال شد.\n"
                            f"تیکت #{ticket_id} به وضعیت «پاسخ داده شده» تغییر کرد."
                        )
                    except Exception as e:
                        await msg.reply_text(
                            f"⚠️ پاسخ ذخیره شد ولی ارسال به کاربر ناموفق: {str(e)[:100]}"
                        )
                conn.close()
            except Exception as e:
                logger.error(f"admin reply ticket error: {e}")
                await msg.reply_text("❌ خطا در ذخیره پاسخ.")
            return

        # ═══ پاسخ ادمین به درخواست مشاوره ═══
        if _is_giso_admin(uid) and _ud_state.get('replying_consultant'):
            if text == '/cancel':
                _ud_state.pop('replying_consultant', None)
                await msg.reply_text("❌ لغو شد.")
                return
            req_id = _ud_state.pop('replying_consultant')
            from datetime import datetime
            try:
                conn = get_giso_db_conn()
                conn.execute(
                    "INSERT INTO consultant_messages (request_id, sender, message, is_read, created_at) "
                    "VALUES (?, 'admin', ?, 0, ?)",
                    (req_id, text, datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
                )
                conn.execute("UPDATE consultant_requests SET status='chatting' WHERE id=?", (req_id,))
                phone_row = conn.execute(
                    "SELECT phone FROM consultant_requests WHERE id=?", (req_id,)
                ).fetchone()
                conn.commit()
                conn.close()

                if phone_row and phone_row[0]:
                    user_bale = _get_bale_id_by_phone(phone_row[0])
                    if user_bale:
                        try:
                            await send_long_message(
                                context.bot, int(user_bale),
                                (
                                    f"💬 *پاسخ مشاور به درخواست #{req_id}*\n\n"
                                    f"{text}\n\n"
                                    f"می‌تونی در سایت ادامه گفتگو رو دنبال کنی."
                                ),
                                parse_mode='Markdown'
                            )
                        except Exception:
                            pass
                await msg.reply_text(
                    f"✅ پاسخ ثبت شد.\n"
                    f"در سایت هم قابل مشاهده‌ست."
                )
            except Exception as e:
                logger.error(f"consultant reply error: {e}")
                await msg.reply_text("❌ خطا در ذخیره.")
            return

        # همگام‌سازی آنلاین وضعیت ادمین با bot.db
        info = _giso_lookup(uid, phone)
        if info["is_admin"] and not existing.get("is_admin"):
            _upsert_giso_user(uid, is_admin=True, pending_request=False)
            existing = _get_giso_user(uid)
        elif not info["is_admin"] and existing.get("is_admin") and not _is_super_admin(uid, phone):
            _upsert_giso_user(uid, is_admin=False, pending_request=False)
            existing = _get_giso_user(uid)
        runtime_role = _runtime_role_for_user(uid, phone, existing)

        # پاسخ ادمین به یک گفتگو (مدیریت گفتگوها) — قبل از فروشگاه/FSMهای دیگر
        _gchat_st = str(_user_states.get(uid, "") or "")
        if _gchat_st.startswith("gchat_reply|"):
            if text in ("لغو", "/cancel", "🔙 بازگشت"):
                _user_states.pop(uid, None)
                await msg.reply_text("لغو شد.", reply_markup=chats_menu_kb())
                return
            _gp = _gchat_st.split("|")
            try:
                _gk, _gcid, _gidx = _gp[1], _gp[2], int(_gp[3])
            except (IndexError, ValueError):
                _user_states.pop(uid, None)
                await msg.reply_text("❌ داده نامعتبر.", reply_markup=_admin_kb(uid))
                return
            _ok = gchat_save_reply(_gk, _gcid, text)
            _user_states.pop(uid, None)
            await msg.reply_text("✅ پاسخ ثبت شد." if _ok else "❌ خطا در ذخیره.")
            await show_kind_paged(msg, _gk, _gidx)
            return

        # ═══ فاز B: منوی فروشگاه ربات (سبک — فقط «🛍 فروشگاه» و state های آن) ═══
        # خروج از زیرمنوی فروشگاه → بازگشت به منوی اصلیِ نقش (ادمین/کاربر)
        if text == "🔙 بازگشت" and _user_states.get(uid, "") in (
                "shop_user_menu", "shop_admin_menu", "shop_super_menu",
                "market_menu", "gchat_menu", "beauty_menu"):
            _user_states.pop(uid, None)
            try:  # پاک‌سازی state ویرایش معلق محصول (اگر وسط ویرایش خارج شده)
                from giso.shop.bot.handlers import _PENDING_EDIT
                _PENDING_EDIT.pop(uid, None)
                _PENDING_EDIT.pop(str(uid), None)
            except Exception:
                pass
            if existing.get("is_admin"):
                await msg.reply_text("به منوی اصلی ادمین بازگشتید.", reply_markup=_admin_kb(uid))
            else:
                await msg.reply_text("به منوی اصلی بازگشتید.",
                                     reply_markup=_user_kb(pending=bool(existing.get("pending_request"))))
            return
        if existing.get("is_admin") and (text == "🏥 مراکز زیبایی" or _user_states.get(uid) == "beauty_menu"):
            try:
                from giso.beauty_centers.bot_handlers import handle_beauty_admin_text
                if await handle_beauty_admin_text(
                        msg, text, _is_super_admin(uid, phone),
                        is_admin=bool(existing.get("is_admin"))):
                    _user_states[uid] = "beauty_menu"
                    return
            except Exception as exc:
                logger.error("beauty center bot menu failed: %s", exc)
                await msg.reply_text("❌ خطا در دریافت مراکز زیبایی.", reply_markup=_admin_kb(uid))
                return

        if await handle_shop_bot_text(msg, text, uid, phone, existing, _user_states, context):
            return

        # ── راهنما (دکمه 📖 یا /help) برای همه‌ی کاربران، پیش از شاخه‌های نقش ──
        if text == "📖 راهنما" or text.strip().lower() in ("/help", "/start_help"):
            await _uact.send_user_help(msg, phone, (user.first_name or "") if user else "")
            return
        # ── دستورات سریع کاربر (فقط کاربر عادی؛ ادمین‌ها منوی خودشان را دارند) ──
        if not existing.get("is_admin"):
            _cmd_alias = {
                "/wallet": "💰 کیف پول من",
                "/shop": "🛍 فروشگاه",
                "/support": "💬 پشتیبانی",
            }
            _mapped = _cmd_alias.get(text.strip().lower())
            if _mapped:
                text = _mapped

        # (state «waiting_admin_phrase» بالاتر، «پیش از چت مشاور AI» پردازش می‌شود.)

        if _user_states.get(uid) == "waiting_rate_limit_minutes":
            if not _is_super_admin(uid, phone):
                _user_states.pop(uid, None)
                await msg.reply_text("⛔ شما دسترسی به این تنظیم ندارید.", reply_markup=_admin_kb(uid))
                return
            try:
                minutes = int(text.strip())
                minutes = max(1, min(1440, minutes))
                from giso_admin import set_giso_config
                set_giso_config("rate_limit_minutes", str(minutes))
                _user_states.pop(uid, None)
                await msg.reply_text(f"✅ مدت زمان به {minutes} دقیقه تغییر کرد.", reply_markup=_admin_settings_kb())
            except (ValueError, TypeError):
                await msg.reply_text("❌ لطفاً یک عدد معتبر به دقیقه بفرست (مثلاً 60):")
                return
            return

        # جستجوی کاربر با شماره، نام یا شناسه ربات → نمایش خلاصه
        if _user_states.get(uid) == "waiting_user_search":
            _user_states.pop(uid, None)
            if not _is_super_admin(uid, phone):
                await msg.reply_text("⛔ فقط سوپرادمین می‌تواند جستجو کند.", reply_markup=_admin_kb(uid))
                return
            query = (text or "").strip()
            info = _lookup_user_info(query)
            if not info:
                await msg.reply_text("🔎 کاربری با این مشخصات پیدا نشد (شماره / نام / شناسه ربات).", reply_markup=_admin_users_del_kb())
                return
            lines = [
                "👤 خلاصه کاربر",
                "━━━━━━━━━━━━━━━━",
                f"نام: {info.get('name') or '—'}",
                f"📱 شماره: {info.get('phone') or '—'}",
                f"🆔 شناسه ربات: {info.get('bale_id') or '—'}",
                f"📅 عضویت: {to_shamsi(info.get('created_at'))}",
                f"💇 فروش مو: {_fa_num(info.get('hair', 0))}",
                f"🔍 آنالیز: {_fa_num(info.get('analysis', 0))}",
                f"🛍 سفارش: {_fa_num(info.get('shop', 0))}",
                f"👑 ادمین: {'بله' if info.get('is_admin') else 'خیر'}",
            ]
            await msg.reply_text("\n".join(lines), reply_markup=_admin_users_del_kb())
            return

        if _user_states.get(uid) == "waiting_user_del_phone":
            if not _is_super_admin(uid, phone):
                _user_states.pop(uid, None)
                await msg.reply_text("⛔ شما دسترسی به حذف کاربران ندارید.", reply_markup=_admin_kb(uid))
                return
            del_ph = normalize_phone(text)
            if not del_ph or len(del_ph) < 10:
                await msg.reply_text("❌ شماره وارد شده نامعتبر است. لطفاً شماره معتبر ارسال کنید (یا دکمه بازگشت را بزنید):")
                return
            if del_ph == "09156012931" or del_ph == "+989156012931" or del_ph.endswith("9156012931"):
                _user_states.pop(uid, None)
                await msg.reply_text("⛔ امکان حذف ادمین یا سوپرادمین از این بخش وجود ندارد.", reply_markup=_admin_users_del_kb())
                return
            from giso_admin import find_giso_admin
            if find_giso_admin(del_ph):
                _user_states.pop(uid, None)
                await msg.reply_text("⛔ امکان حذف ادمین یا سوپرادمین از این بخش وجود ندارد.", reply_markup=_admin_users_del_kb())
                return
            info = _lookup_user_delete_info(del_ph)
            _user_states.pop(uid, None)
            if not info:
                await msg.reply_text(f"❌ کاربری با شماره {del_ph} یافت نشد.", reply_markup=_admin_users_del_kb())
                return
            if info["is_admin"]:
                await msg.reply_text("⛔ امکان حذف ادمین یا سوپرادمین از این بخش وجود ندارد.", reply_markup=_admin_users_del_kb())
                return
            await msg.reply_text(
                _user_delete_info_text(info),
                reply_markup=_user_del_confirm_kb(info["bale_id"], info["phone"]),
            )
            return

        # چت مشاوره: وقتی ادمین در state گفتگو است، پیامش را ذخیره و به کاربر ارسال کن
        st = _user_states.get(uid, "")
        if st.startswith("consultant_chat_"):
            if text == "/cancel":
                _user_states.pop(uid, None)
                await msg.reply_text("گفتگو پایان یافت.", reply_markup=_admin_kb(uid))
                return
            # اصلاح 2026-08-23: «user_rec» در محدوده‌ی handle_text تعریف نشده بود
            # (نام صحیح «existing» است) و باعث NameError/خاموش‌شدن پاسخ مشاور می‌شد.
            if not (_is_super_admin(uid, phone) or (existing and existing.get("is_admin"))):
                _user_states.pop(uid, None)
                await msg.reply_text("⛔ دسترسی ادمین ندارید.", reply_markup=_user_kb())
                return
            try:
                rid = int(st.split("_")[-1])
            except (ValueError, IndexError):
                _user_states.pop(uid, None)
                return
            with get_giso_db_conn() as conn:
                conn.execute("INSERT INTO consultant_messages (request_id, sender, message, is_read, created_at) "
                             "VALUES (?, 'admin', ?, 0, ?)",
                             (rid, text, time.strftime("%Y-%m-%d %H:%M:%S")))
                conn.commit()
            # ارسال به کاربر در ربات (اگر ثبت‌نام کرده)
            try:
                with get_giso_db_conn() as conn:
                    row = conn.execute("SELECT phone, customer_name FROM consultant_requests WHERE id=?", (rid,)).fetchone()
                if row:
                    user_cid = None
                    with get_giso_db_conn() as c2:
                        user_row = c2.execute("SELECT bale_id FROM giso_users WHERE phone=?", (row["phone"],)).fetchone()
                        if user_row and str(user_row["bale_id"]).isdigit():
                            user_cid = int(user_row["bale_id"])
                    if user_cid:
                        asyncio.create_task(context.bot.send_message(
                            chat_id=user_cid,
                            text=f"💬 مشاور گیسو پاسخ داد:\n{text}"))
            except Exception as e:
                logger.debug(f"send consultant msg to user err: {e}")
            await msg.reply_text("✅ پیام شما ارسال شد.")
            return

        if await handle_hair_sale_state(msg, text, uid, phone, existing, _user_states, _admin_hair_sale_kb, _user_hair_sale_kb, context):
            return

        if await _handle_ai_state(msg, text, uid, existing):
            return

        if existing.get("is_admin"):
            if text == "/start":
                await _show_panel(msg, fname, "admin", uid=uid)
                return

            if text in {
                "🛡 دسترسی ادمین‌ها", "⚙️ تنظیمات دسترسی ادمین‌ها",
                "👁 دسترسی ادمین‌های معمولی",
            }:
                await msg.reply_text(
                    "این تنظیمات ساده‌سازی شده است", reply_markup=_admin_kb(uid)
                )
                return

            if text in ("📬 صندوق اعلان کار من", "✅ اقدام سریع", "💬 پاسخ به کاربر"):
                await msg.reply_text("این گزینه حذف شده است.", reply_markup=_admin_kb(uid))
                return

            if text == "🏪 بازارچه":
                _user_states[uid] = "market_menu"
                await msg.reply_text(market_menu_text(), reply_markup=market_menu_kb(_is_super_admin(uid, phone)))
                return
            if text == "📋 درخواست‌های بازارچه":
                _user_states[uid] = "market_menu"
                await show_market_paged(msg, 0)
                return
            if text == "🧑‍💼 خریداران منتظر":
                await show_pending_buyers(msg)
                return
            if text == "📊 وضعیت بازارچه":
                if not _is_super_admin(uid, phone):
                    await msg.reply_text("⛔ فقط سوپرادمین")
                else:
                    await show_market_status(msg, True)
                return
            if text == "💳 تعرفه اعتباری":
                if not _is_super_admin(uid, phone):
                    await msg.reply_text("⛔ فقط سوپرادمین")
                else:
                    await show_credit_tariffs(msg)
                return
            if text == "📢 مدیریت کانال" and _is_super_admin(uid, phone):
                site = _get_giso_site_url()
                await msg.reply_text(
                    "📢 مدیریت کانال گیسو\n\nتنظیم شناسه کانال، حالت انتشار و بررسی محصولات کانال از پنل امن سایت انجام می‌شود.",
                    reply_markup=InlineKeyboardMarkup([[
                        InlineKeyboardButton("🌐 ورود به مدیریت کانال", url=f"{site}/admin/channel")
                    ]]),
                )
                return
            if text == "💬 مدیریت گفتگوها":
                _user_states[uid] = "gchat_menu"
                await msg.reply_text(chats_menu_text(), reply_markup=chats_menu_kb())
                return
            _gkind = gchat_kind_from_text(text)
            if _gkind:
                _user_states[uid] = "gchat_menu"
                await show_kind_paged(msg, _gkind, 0)
                return

            # Sensitive configuration/identity commands stay superadmin-only,
            # including when an old keyboard or a manually typed label is used.
            if text in _SUPER_ONLY_ADMIN_TEXTS and not _is_super_admin(uid, phone):
                await msg.reply_text("⛔ فقط سوپرادمین", reply_markup=_admin_kb(uid))
                return

            # صندوق اعلان / اقدام سریع / پاسخ به کاربر از کیبورد فعلی حذف شده‌اند.
            # stub بالاتر پیام «حذف شده» می‌دهد؛ هندلر مرده نباید بعد از return بماند.

            if runtime_role == "admin" and text in {
                "📊 پیشخوان", "🛒 سفارش‌ها", "💇 فروش مو",
                "🔬 آنالیز", "🔬 مدیریت آنالیز", "📬 درخواست‌های آنالیز", "⭐ نظرات",
                "📦 محصولات", "📊 گزارش فروش", "📢 مدیریت کانال",
                "👥 مدیریت کاربران سایت", "👑 مدیریت ادمین‌ها",
                "⚙️ مدیریت سایت و ربات", "⚙️ تنظیمات سایت",
                CONSULTANT_AI_LABEL, PROVIDERS_AI_LABEL,
            }:
                await msg.reply_text(
                    "این منوی قدیمی غیرفعال است؛ از خرید مو، فروشگاه، بازارچه یا مدیریت گفتگوها استفاده کنید.",
                    reply_markup=_admin_kb(uid),
                )
                return

            # Fixed operational section policy for normal admins.
            _section_of = {
                "💇 فروش مو": "hair_sale",
                "💇 خرید مو": "hair_sale",
                "📬 درخواست‌های آنالیز": "analysis_management",
                "🔬 مدیریت آنالیز": "analysis_management",
                "📦 محصولات": "products",
                "⭐ نظرات": "reviews",
                "🛍 سفارش‌ها": "orders",
                "🛒 سفارش‌ها": "orders",
                "📊 پیشخوان": "dashboard",
                "📢 مدیریت کانال": "channel_management",
                "👥 مدیریت کاربران سایت": "users",
                "👑 مدیریت ادمین‌ها": "admins",
                "⚙️ مدیریت سایت و ربات": "site_bot_settings",
                "⚙️ تنظیمات سایت": "site_bot_settings",
                PROVIDERS_AI_LABEL: "ai_management",
            }
            if text in _section_of:
                if not _admin_section_visible_for_bot(uid, _section_of[text]):
                    await msg.reply_text(
                        "⛔ شما به این بخش دسترسی ندارید. در صورت نیاز با سوپرادمین هماهنگ کنید.",
                        reply_markup=_admin_kb(uid),
                    )
                    return

            # ═══ فاز P0: گروه‌های منوی جدید سوپرادمین ═══
            if text in ("💇 خرید مو", "🔬 آنالیز", "👁 نظارت", "🛠 مدیریت", "⚙️ تنظیمات سایت"):
                if text == "💇 خرید مو":
                    _user_states.pop(uid, None)
                    await msg.reply_text(admin_hair_menu_text(), reply_markup=build_admin_hair_menu(uid=uid))
                    return
                if text == "👁 نظارت":
                    await msg.reply_text("این گزینه حذف شده است.", reply_markup=_admin_kb(uid))
                    return
                if not _is_super_admin(uid, phone):
                    await msg.reply_text("⛔ این بخش مخصوص سوپرادمین است.", reply_markup=_admin_kb(uid))
                    return
                if text == "🔬 آنالیز":
                    await msg.reply_text(
                        "🔬 بخش آنالیز — یکی از گزینه‌ها را انتخاب کنید:",
                        reply_markup=_admin_analysis_group_kb())
                    return
                if text == "🛠 مدیریت":
                    await msg.reply_text(
                        "🛠 بخش مدیریت — یکی از مدیریت‌ها را انتخاب کنید:",
                        reply_markup=_admin_management_group_kb())
                    return
                if text == "⚙️ تنظیمات سایت":
                    await msg.reply_text(
                        "⚙️ تنظیمات سایت و ربات — یکی از گزینه‌ها را انتخاب کنید:",
                        reply_markup=_admin_site_settings_kb())
                    return

            if text == "🚨 وضعیت فوری":
                if not _is_super_admin(uid, phone):
                    await msg.reply_text("⛔ فقط سوپرادمین.", reply_markup=_admin_kb(uid))
                    return
                try:
                    _cached = _READ_REPORT_CACHE.get("urgent")
                    if _cached and time.monotonic() - _cached[0] < 15:
                        _txt = _cached[1]
                    else:
                        from pathlib import Path as _Path
                        with get_giso_db_conn() as _c:
                            _hair = _c.execute("SELECT COUNT(*) FROM hair_orders WHERE status IN ('pending','reviewing')").fetchone()[0]
                            _market = _c.execute("SELECT COUNT(*) FROM hair_listings WHERE status='pending_review' AND COALESCE(deleted_at,'')='' ").fetchone()[0]
                            _centers = _c.execute("SELECT COUNT(*) FROM beauty_centers WHERE status IN ('pending_review','reviewing')").fetchone()[0]
                            _orders = _c.execute("SELECT COUNT(*) FROM product_orders WHERE status IN ('pending','new')").fetchone()[0]
                            _ai = _c.execute("SELECT COUNT(*) FROM giso_ai_providers WHERE COALESCE(enabled,0)=1").fetchone()[0]
                        _backup_dir = _Path(__file__).resolve().parent / "data" / "backup"
                        _backups = sorted(_backup_dir.glob("*.db"), key=lambda p: p.stat().st_mtime, reverse=True) if _backup_dir.exists() else []
                        _last_backup = _backups[0].name if _backups else "ندارد"
                        _bot_ok = bool(_token_from_env() or _token_from_db())
                        _txt = ("🚨 وضعیت فوری گیسو\n━━━━━━━━━━━━━━━━\n"
                                f"🤖 ربات: {'🟢 فعال' if _bot_ok else '🔴 بدون توکن'}\n"
                                f"🧠 هوش مصنوعی فعال: {_fa_num(_ai)} ارائه‌دهنده\n"
                                f"💾 آخرین پشتیبان: {_last_backup}\n\n"
                                f"💇 خرید موی معطل: {_fa_num(_hair)}\n"
                                f"🏪 آگهی منتظر: {_fa_num(_market)}\n"
                                f"🏥 مرکز منتظر: {_fa_num(_centers)}\n"
                                f"🛍 سفارش جدید: {_fa_num(_orders)}")
                        _READ_REPORT_CACHE["urgent"] = (time.monotonic(), _txt)
                    await msg.reply_text(_txt, reply_markup=_admin_management_group_kb())
                except Exception:
                    await msg.reply_text("❌ دریافت وضعیت فوری ممکن نشد.", reply_markup=_admin_management_group_kb())
                return

            # 👁 نظارت — حذف شده
            if text in ("💇 نظارت خرید مو", "🔬 نظارت آنالیز", "🛍 نظارت فروشگاه"):
                await msg.reply_text("این گزینه حذف شده است.", reply_markup=_admin_kb(uid))
                return
                if not _is_super_admin(uid, phone):
                    await msg.reply_text("⛔ فقط سوپرادمین.", reply_markup=_admin_kb(uid))
                    return
                from giso.bot_watch import watch_hair_text, watch_analysis_text, watch_shop_text
                _wt = {"💇 نظارت خرید مو": watch_hair_text,
                       "🔬 نظارت آنالیز": watch_analysis_text,
                       "🛍 نظارت فروشگاه": watch_shop_text}[text]
                await send_long_message(context.bot, msg.chat_id, _wt(), message=msg, reply_markup=_admin_watch_kb())
                return

            # 🛒 محصولات درخواستی (زیرمنوی 🔬 آنالیز) — همان لیست منوی آنالیز اما از دکمه متنی
            if text == "🛒 محصولات درخواستی":
                if not (_is_super_admin(uid, phone) or _admin_section_visible_for_bot(uid, "analysis_management")):
                    await msg.reply_text("⛔ دسترسی ندارید.", reply_markup=_admin_kb(uid))
                    return
                from telegram import InlineKeyboardButton, InlineKeyboardMarkup
                _reqs = _get_recent_product_requests(limit=10)
                if not _reqs:
                    await msg.reply_text("🛒 هیچ محصول درخواستی موجود نیست.",
                                         reply_markup=_admin_analysis_group_kb() if _is_super_admin(uid, phone) else _admin_kb(uid))
                else:
                    _pkb = []
                    for r in _reqs:
                        _ic = {"pending": "🕐", "added": "✅", "rejected": "❌"}.get(r.get("status", ""), "🕐")
                        _pkb.append([InlineKeyboardButton(
                            f"{_ic} #{r['id']} - {r['phone']}",
                            callback_data=f"prod_view_{r['id']}")])
                    await msg.reply_text(
                        "🛒 محصولات درخواستی کاربران — برای تغییر وضعیت روی هر مورد بزنید:",
                        reply_markup=InlineKeyboardMarkup(_pkb))
                    if _is_super_admin(uid, phone):
                        await msg.reply_text("گزینه بعدی:", reply_markup=_admin_analysis_group_kb())
                return

            # 🌐 مدیریت سایت (عملیات سرویس)
            if text == "🌐 مدیریت سایت":
                if not _is_super_admin(uid, phone):
                    await msg.reply_text("⛔ فقط سوپرادمین.", reply_markup=_admin_kb(uid))
                    return
                await msg.reply_text(
                    "🌐 مدیریت سایت — عملیات سرویس را انتخاب کنید:",
                    reply_markup=_admin_site_ops_kb())
                return

            # 💬 مدیریت ویجت سایت
            if text == "💬 مدیریت ویجت":
                if not _is_super_admin(uid, phone):
                    await msg.reply_text("⛔ فقط سوپرادمین.", reply_markup=_admin_kb(uid))
                    return
                await _show_managed_ai_widget_menu(msg)
                return

            # ⭐ نظرات — نمایش اخیر + پنهان/نمایان
            if text == "⭐ نظرات":
                from telegram import InlineKeyboardButton, InlineKeyboardMarkup
                with get_giso_db_conn() as conn:
                    _rv_counts = conn.execute(
                        "SELECT status, COUNT(*) FROM reviews GROUP BY status"
                    ).fetchall()
                    _rv_rows = conn.execute(
                        "SELECT id, phone, review_type, rating, comment, status, created_at "
                        "FROM reviews ORDER BY id DESC LIMIT 8").fetchall()
                _cmap = {r[0]: r[1] for r in _rv_counts}
                _total_rv = sum(_cmap.values())
                _head = (
                    "⭐ مدیریت نظرات\n━━━━━━━━━━━━━━━━\n"
                    f"📊 کل: {_fa_num(_total_rv)} | 👁 نمایان: {_fa_num(_cmap.get('visible', 0))}"
                    f" | 🚫 پنهان: {_fa_num(_cmap.get('hidden', 0))} | 🗑 حذف‌شده: {_fa_num(_cmap.get('deleted', 0))}\n"
                    "━━━━━━━━━━━━━━━━"
                )
                await msg.reply_text(_head, reply_markup=_admin_management_group_kb() if _is_super_admin(uid, phone) else _admin_kb(uid))
                if not _rv_rows:
                    await msg.reply_text("⭐ هنوز نظری ثبت نشده است.")
                for _rv in _rv_rows:
                    _cmt = (_rv["comment"] or "").strip()
                    if len(_cmt) > 120:
                        _cmt = _cmt[:120] + "…"
                    _st = {"visible": "👁 نمایان", "hidden": "🚫 پنهان", "deleted": "🗑 حذف‌شده"}.get(_rv["status"], _rv["status"] or "—")
                    _type_fa = {"shop_order": "🛍 سفارش فروشگاه", "hair": "💇 فروش مو", "analysis": "🔬 آنالیز"}.get(_rv["review_type"], _rv["review_type"] or "—")
                    _txt = (
                        f"⭐ نظر #{_fa_num(_rv['id'])} | {_type_fa}\n"
                        f"📱 {_rv['phone'] or '—'} | امتیاز: {_fa_num(_rv['rating'] or 0)}/۵ | {_st}\n"
                        f"📝 {_cmt or '—'}"
                    )
                    if _rv["status"] != "deleted":
                        _next_lbl = "🚫 پنهان کن" if _rv["status"] == "visible" else "👁 نمایان کن"
                        _rv_kb = InlineKeyboardMarkup([[
                            InlineKeyboardButton(_next_lbl, callback_data=f"rev_tgl|{_rv['id']}")
                        ]])
                        await msg.reply_text(_txt, reply_markup=_rv_kb)
                    else:
                        await msg.reply_text(_txt)
                return

            # ═══ منوی عملیاتی فروش مو: درخواست‌ها، گزارش‌ها و گفتگوها ═══
            _st_hair = _user_states.get(uid, "")

            # بازگشت از زیرمنوی جدید فروش مو
            if text == "🔙 بازگشت" and _st_hair == "hair_reports_menu":
                _user_states.pop(uid, None)
                await msg.reply_text("💇 به منوی مدیریت درخواست‌های فروش مو خوش آمدید:", reply_markup=_admin_hair_sale_kb())
                return

            # state تأیید سفارش + قیمت نهایی
            if _st_hair.startswith("waiting_hair_approve_price_"):
                order_id = int(_st_hair.split("_")[-1])
                _user_states.pop(uid, None)
                price_text = (text or "").strip()
                if not price_text:
                    await msg.reply_text("❌ متن قیمت خالی است. دوباره تلاش کنید یا از منو خارج شوید.", reply_markup=_admin_hair_sale_kb())
                    return
                with get_giso_db_conn() as conn:
                    conn.execute("UPDATE hair_orders SET final_price=?, status='approved', updated_at=? WHERE id=?",
                                 (price_text, time.strftime("%Y-%m-%d %H:%M:%S"), order_id))
                    conn.commit()
                await msg.reply_text(f"✅ قیمت نهایی «{price_text}» ثبت و درخواست #{_fa_num(order_id)} تایید شد.", reply_markup=_admin_hair_sale_kb())
                # اعلان به کاربر با ۳ دکمه: اعتراض / گفتگو / نظر
                try:
                    from telegram import InlineKeyboardButton, InlineKeyboardMarkup
                    user_kb = InlineKeyboardMarkup([
                        [InlineKeyboardButton("📝 ثبت اعتراض", callback_data=f"hair_objection|{order_id}")],
                        [InlineKeyboardButton("💬 مشاهده گفتگو", callback_data=f"hair_view_msgs|{order_id}")],
                        [InlineKeyboardButton("⭐ ثبت نظر", callback_data=f"hair_rev_sel|{order_id}")],
                    ])
                    user_msg = (
                        f"💰 قیمت نهایی موی شما مشخص شد\n"
                        "━━━━━━━━━━━━━━━━\n"
                        f"💇 درخواست: #{_fa_num(order_id)}\n"
                        f"💎 قیمت نهایی: {price_text}\n"
                        "━━━━━━━━━━━━━━━━\n"
                        "اگر سوالی دارید یا می‌خواهید اعتراض کنید، از دکمه‌های زیر استفاده کنید:"
                    )
                    notify_user_bot_by_order(context, order_id, user_msg, reply_markup=user_kb)
                except Exception:
                    notify_user_bot_by_order(context, order_id, f"✅ قیمت نهایی موی شما: {price_text}")
                return

            # گزینه‌های منوی قدیمی (فاز 3.2) → هدایت به منوی هوشمند جدید (فاز ۵ نهایی)
            if text in ("✅ تأیید سفارش", "❌ رد سفارش", "💰 ثبت قیمت نهایی"):
                _user_states.pop(uid, None)
                await msg.reply_text(
                    "✨ این گزینه در منوی جدید «📋 درخواست‌های فروش مو» قرار گرفت — از آنجا با اکشن‌های سریع کار کنید:",
                    reply_markup=build_admin_hair_menu(uid=uid),
                )
                return

            # 📊 گزارش‌ها
            if text == "📊 گزارش‌ها":
                _user_states[uid] = "hair_reports_menu"
                await msg.reply_text("📊 گزارش‌های خرید مو — یکی را انتخاب کنید:", reply_markup=_admin_hair_reports_kb())
                return

            # گزارش‌های زیرمنو (وقتی در منوی گزارش هستیم)
            if _st_hair == "hair_reports_menu":
                # «نمایش در حال بررسی» / «نمایش رد شده» → لیست شماره‌ها صفحه‌بندی‌شده (فاز 5.1 ربات)
                if text == "🔍 نمایش در حال بررسی":
                    await show_report_phones(msg, uid, "reviewing", 0)
                    return
                if text == "❌ نمایش رد شده":
                    await show_report_phones(msg, uid, "rejected", 0)
                    return
                if text == "💰 قیمت ثبت‌شده":
                    await show_report_phones(msg, uid, "priced", 0)
                    return
                if text == "💬 گفتگوها":
                    cnt = await show_conversations(msg, uid)
                    await msg.reply_text(
                        ("💬 گفتگویی در جریان نیست." if cnt == 0 else f"💬 {_fa_num(cnt)} گفتگو — برای پاسخ روی دکمه بزنید."),
                        reply_markup=_admin_hair_reports_kb())
                    return
                _scope_map = {
                    "📊 گزارش کلی": "overall",
                    "💰 فروش کلی": "sales",
                }
                if text in _scope_map:
                    from giso.bot_reports import hair_sale_reports_text
                    await msg.reply_text(hair_sale_reports_text(_scope_map[text]), reply_markup=_admin_hair_reports_kb())
                    return

            # 💬 گفتگوها (منوی اصلی فروش مو — جایگزین «اعتراض‌ها») — گفتگوهای در جریان
            if text == "💬 گفتگوها":
                cnt = await show_conversations(msg, uid)
                tail = "💬 گفتگویی در جریان نیست." if cnt == 0 else f"💬 {_fa_num(cnt)} گفتگو نمایش داده شد — برای پاسخ روی دکمه بزنید."
                await msg.reply_text(tail, reply_markup=build_admin_hair_menu(uid=uid))
                return

            # ═══ فاز ۵ نهایی: منوی هوشمند فروش مو ادمین ═══
            # ورود به فروش مو → منوی عملیاتی ثابت
            if text == "💇 فروش مو":
                _user_states.pop(uid, None)
                await msg.reply_text(admin_hair_menu_text(), reply_markup=build_admin_hair_menu(uid=uid))
                return

            # حالت: منتظر شماره کاربر (ویرایش با شماره)
            if _st_hair == "hair_admin_phone":
                if text == "🔙 بازگشت":
                    _user_states.pop(uid, None)
                    await msg.reply_text(admin_hair_menu_text(), reply_markup=build_admin_hair_menu(uid=uid))
                    return
                _user_states.pop(uid, None)
                await render_user_orders(msg, uid, text.strip())
                await msg.reply_text(admin_hair_menu_text(), reply_markup=build_admin_hair_menu(uid=uid))
                return

            # 📋 لیست درخواست‌های فروش مو (صفحه‌بندی تک‌به‌تک + عکس + اکشن‌ها)
            if text == "📋 درخواست‌های فروش مو":
                cnt = await show_requests_paged(msg, uid, 0)
                tail = "📋 درخواستی برای فروش مو ثبت نشده است." if cnt == 0 else f"📋 {_fa_num(cnt)} درخواست — با دکمه‌های قبلی/بعدی مرور کنید."
                await msg.reply_text(tail, reply_markup=build_admin_hair_menu(uid=uid))
                return

            # 📱 ویرایش با شماره کاربر
            if text == "📱 ویرایش با شماره کاربر":
                _user_states[uid] = "hair_admin_phone"
                await msg.reply_text(
                    "📱 شماره موبایل کاربر را وارد کنید تا درخواست‌های فروش موی او نمایش داده شود:\n"
                    "(مثلاً 09123456789)\nبرای لغو: 🔙 بازگشت",
                    reply_markup=ReplyKeyboardMarkup([["🔙 بازگشت"]], resize_keyboard=True),
                )
                return

            # 👥 لیست کاربران فروش مو (فقط کاربران با درخواست فعال + تعداد)
            if text == "👥 لیست کاربران فروش مو":
                cnt = await show_users_paged(msg, uid, 0)
                tail = "👥 کاربر فعالی در فروش مو یافت نشد." if cnt == 0 else f"👥 {_fa_num(cnt)} کاربر — با دکمه‌های قبلی/بعدی مرور کنید."
                await msg.reply_text(tail, reply_markup=build_admin_hair_menu(uid=uid))
                return

            # پنل مدیریت فروش مو (زیرمنوی ادمین) و منوهای مرتبط
            if await handle_hair_sale_commands(msg, text, uid, phone, True, _user_states,
                                               _admin_kb, _user_kb, _admin_hair_sale_kb, _user_hair_sale_kb,
                                               _admin_hair_status_kb):
                return

            if await _handle_ai_menu(msg, text, uid, existing):
                return

            if text == CONSULTANT_AI_LABEL:
                await _start_consultant_ai_chat(msg, context, uid, _runtime_role_for_user(uid, phone, existing), is_query=False)
                return

            if text == "🔬 مدیریت آنالیز":
                await handle_admin_analysis_menu(update, context)
                return

            if text == "🌐 تنظیم آدرس سایت گیسو":
                await handle_giso_site_url_menu(update, context)
                return

            if text == "⚙️ مدیریت سایت و ربات":
                await msg.reply_text(
                    "⚙️ به منوی مدیریت سایت و ربات خوش آمدید.",
                    reply_markup=_admin_settings_kb(),
                )
                return

            if text in (BEHAVIOR_AI_LABEL, "🤖 مدیریت هوش مصنوعی"):
                if not _is_super_admin(uid, phone):
                    await msg.reply_text("⛔ فقط سوپرادمین", reply_markup=_admin_kb(uid))
                    return
                await msg.reply_text(_managed_ai_dashboard_text(), reply_markup=_managed_ai_main_kb())
                return

            if text == "💾 پشتیبان‌گیری":
                await handle_backup_menu(update, context)
                return

            if text == "🔄 ریستارت ربات":
                if not _is_super_admin(uid, phone):
                    await msg.reply_text("⛔ فقط سوپرادمین", reply_markup=_admin_kb(uid))
                    return
                await msg.reply_text(
                    "🔄 ریستارت ربات گیسو\n\nزمان ریستارت را انتخاب کنید:",
                    reply_markup=_restart_menu_kb(),
                )
                return

            if text == "⏱ محدودیت زمان تحلیل":
                if _is_super_admin(uid, phone):
                    await msg.reply_text(
                        _ratelimit_status_text(),
                        reply_markup=_ratelimit_inline_kb(),
                    )
                else:
                    await msg.reply_text(
                        "⛔ شما دسترسی به این تنظیم ندارید.",
                        reply_markup=_admin_kb(uid),
                    )
                return

            if text == "🎨 انتخاب تم سایت":
                try:
                    from giso_admin import get_giso_config
                    cur_theme = get_giso_config("site_theme", "original") or "original"
                except Exception:
                    cur_theme = "original"
                await msg.reply_text(
                    f"🎨 تم فعلی سایت: {cur_theme}\n\n"
                    "لطفاً تم مورد نظر را برای کل سایت گیسو انتخاب کنید:",
                    reply_markup=_admin_theme_kb(),
                )
                return

            if text in {"✨ تم ساده طلایی", "👑 تم کلاسیک", "💇 تم ارزش مو و بازارچه", "🔬 تم سلامت و آنالیز"}:
                # دکمه‌های مانده در کیبورد قدیمی کاربران نباید مقدار بازنشسته ذخیره کنند.
                try:
                    from giso_admin import set_giso_config
                    set_giso_config("site_theme", "smart_assistant")
                    await msg.reply_text(
                        "این تم بازنشسته شده است؛ سایت روی «دستیار هوشمند» قرار گرفت.",
                        reply_markup=_admin_theme_kb(),
                    )
                except Exception:
                    await msg.reply_text("❌ خطا در ذخیره تم سایت.", reply_markup=_admin_theme_kb())
                return

            if text == "✦ تم دستیار هوشمند":
                try:
                    from giso_admin import set_giso_config
                    set_giso_config("site_theme", "smart_assistant")
                    await msg.reply_text(
                        "✅ تم سایت روی «دستیار هوشمند» تنظیم شد.",
                        reply_markup=_admin_theme_kb(),
                    )
                except Exception:
                    await msg.reply_text("❌ خطا در ذخیره تم سایت.", reply_markup=_admin_theme_kb())
                return

            if text == "🎯 تم مسیر هوشمند گیسو":
                try:
                    from giso_admin import set_giso_config
                    set_giso_config("site_theme", "original")
                    await msg.reply_text(
                        "✅ تم سایت روی «مسیر هوشمند گیسو» تنظیم شد.",
                        reply_markup=_admin_theme_kb(),
                    )
                except Exception:
                    await msg.reply_text("❌ خطا در ذخیره تم سایت.", reply_markup=_admin_theme_kb())
                return

            if text == "👑 مدیریت ادمین‌ها":
                if _admin_section_visible_for_bot(uid, "admins"):
                    await msg.reply_text(
                        "👑 به زیرمنوی مدیریت ادمین‌ها خوش آمدید.",
                        reply_markup=_admin_mgmt_kb(),
                    )
                else:
                    await msg.reply_text(
                        "⛔ شما دسترسی به مدیریت ادمین‌ها ندارید.",
                        reply_markup=_admin_kb(uid),
                    )
                return

            if text == "🔑 تنظیم کلمه ادمینی":
                if _is_super_admin(uid, phone):
                    await _show_admin_phrase_menu(msg)
                else:
                    await msg.reply_text(
                        "⛔ شما دسترسی به مدیریت ادمین‌ها ندارید.",
                        reply_markup=_admin_kb(uid),
                    )
                return

            if text == "📥 بررسی درخواست‌ها":
                if _is_super_admin(uid, phone):
                    try:
                        from giso_admin import list_admin_requests
                        from telegram import InlineKeyboardButton, InlineKeyboardMarkup
                        reqs = list_admin_requests(status="pending")
                        if not reqs:
                            await msg.reply_text(
                                "📥 هیچ درخواست ادمینی در انتظار بررسی وجود ندارد.",
                                reply_markup=_admin_mgmt_kb(),
                            )
                        else:
                            await msg.reply_text(
                                f"📥 تعداد {len(reqs)} درخواست در انتظار بررسی:",
                                reply_markup=_admin_mgmt_kb(),
                            )
                            for req in reqs:
                                req_id = req.get("id", 0)
                                r_phone = req.get("phone", "—")
                                r_bid = req.get("bale_id", "—")
                                r_time = req.get("requested_at", "—")
                                kb = InlineKeyboardMarkup([
                                    [InlineKeyboardButton("✅ تایید", callback_data=f"adm_app|{req_id}"),
                                     InlineKeyboardButton("❌ رد", callback_data=f"adm_rej|{req_id}")]
                                ])
                                txt = (f"🔔 درخواست ادمینی #{req_id}\n\n"
                                       f"📱 شماره تماس: {r_phone}\n"
                                       f"🆔 شناسه بله/تلگرام: {r_bid}\n"
                                       f"⏰ زمان: {to_shamsi(r_time)}")
                                await msg.reply_text(txt, reply_markup=kb)
                    except Exception as e:
                        logger.error(f"error list requests: {e}")
                        await msg.reply_text("❌ خطا در بارگذاری درخواست‌ها.", reply_markup=_admin_mgmt_kb())
                else:
                    await msg.reply_text(
                        "⛔ شما دسترسی به مدیریت ادمین‌ها ندارید.",
                        reply_markup=_admin_kb(uid),
                    )
                return

            if text == "📋 لیست ادمین‌ها":
                if _is_super_admin(uid, phone):
                    try:
                        from giso.panel.modules.admins import list_active_giso_admins
                        admins = list_active_giso_admins()
                        if admins:
                            lines = ["📋 لیست ادمین‌های گیسو:\n"]
                            for idx, a in enumerate(admins, 1):
                                p = a.get("phone", "—")
                                bid = str(a.get("bale_id", "") or a.get("telegram_id", "") or "—")
                                dt = a.get("added_at", "—")
                                is_sup = (bid == "1191639507" or p == "09156012931" or p == "+989156012931" or p.endswith("9156012931"))
                                access_label = "super admin 👑" if is_sup else "full admin"
                                lines.append(f"{idx}. شماره تماس: {p} | شناسه: {bid}\n"
                                             f"   نوع دسترسی: {access_label} | تاریخ عضویت: {dt}")
                            reply_text = "\n\n".join(lines)
                        else:
                            reply_text = "📋 لیست ادمین‌ها خالی است."
                    except Exception:
                        reply_text = "📋 لیست ادمین‌ها به‌زودی نمایش داده می‌شود."
                    await msg.reply_text(reply_text, reply_markup=_admin_mgmt_kb())
                else:
                    await msg.reply_text(
                        "⛔ شما دسترسی به مدیریت ادمین‌ها ندارید.",
                        reply_markup=_admin_kb(uid),
                    )
                return

            if text == "🗑 حذف ادمین":
                if _is_super_admin(uid, phone):
                    try:
                        from giso.panel.modules.admins import list_active_giso_admins
                        from telegram import InlineKeyboardButton, InlineKeyboardMarkup
                        admins = list_active_giso_admins()
                        await msg.reply_text(
                            "🗑 برای حذف هر ادمین از دکمه زیر مورد استفاده کنید:\n"
                            "⚠️ توجه: سوپرادمین اصلی قابل حذف نیست.",
                            reply_markup=_admin_mgmt_kb(),
                        )
                        for a in admins:
                            a_id = a.get("id", 0)
                            a_phone = a.get("phone", "—")
                            a_bid = str(a.get("bale_id", "") or a.get("telegram_id", "") or "—")
                            is_sup = (a_bid == "1191639507" or a_phone == "09156012931" or a_phone == "+989156012931" or a_phone.endswith("9156012931"))
                            txt = (f"👤 ادمین #{a_id}\n"
                                   f"📱 شماره: {a_phone} | 🆔 شناسه: {a_bid}\n"
                                   f"🛡 نوع: {'super admin 👑' if is_sup else 'full admin'}")
                            kb = InlineKeyboardMarkup([
                                [InlineKeyboardButton("🗑 حذف این ادمین", callback_data=f"adm_del|{a_id}")]
                            ])
                            await msg.reply_text(txt, reply_markup=None if is_sup else kb)
                    except Exception as e:
                        logger.error(f"error delete admin list: {e}")
                        await msg.reply_text("❌ خطا در نمایش ادمین‌ها برای حذف.", reply_markup=_admin_mgmt_kb())
                else:
                    await msg.reply_text(
                        "⛔ شما دسترسی به مدیریت ادمین‌ها ندارید.",
                        reply_markup=_admin_kb(uid),
                    )
                return

            if text == "🗑 حذف همه درخواست‌ها":
                if _is_super_admin(uid, phone):
                    try:
                        from giso_admin import _connect, list_giso_admins
                        conn = _connect()
                        # حذف همه درخواست‌ها
                        req_before = conn.execute("SELECT COUNT(*) FROM giso_admin_requests").fetchone()[0]
                        conn.execute("DELETE FROM giso_admin_requests")
                        conn.commit()
                        conn.close()
                        # حذف همه ادمین‌های فعال (بجز سوپرادمین و تنزل‌یافته‌ها)
                        from giso.panel.modules.admins import list_active_giso_admins
                        admins = list_active_giso_admins()
                        removed = 0
                        for a in admins:
                            a_bid = str(a.get("bale_id", "") or a.get("telegram_id", "") or "")
                            a_phone = str(a.get("phone", "") or "")
                            # سوپرادمین اصلی حذف نشود
                            if a_bid == "1191639507" or a_phone in ("09156012931", "+989156012931"):
                                continue
                            try:
                                from giso.panel.modules.admins import remove_giso_admin_completely
                                if remove_giso_admin_completely(a.get("id", 0)):
                                    removed += 1
                            except Exception:
                                try:
                                    from giso_admin import delete_giso_admin
                                    delete_giso_admin(a.get("id", 0))
                                    _demote_giso_user_admin(bale_id=a_bid, phone=a_phone)
                                    removed += 1
                                except Exception:
                                    pass
                        await msg.reply_text(
                            f"✅ عملیات انجام شد:\n"
                            f"📥 {req_before} درخواست ادمینی حذف شد\n"
                            f"👤 {removed} ادمین فعال حذف شد\n"
                            f"👑 سوپرادمین اصلی حفظ شد",
                            reply_markup=_admin_mgmt_kb()
                        )
                    except Exception as e:
                        logger.error(f"delete all requests: {e}")
                        await msg.reply_text("❌ خطا در حذف.", reply_markup=_admin_mgmt_kb())
                else:
                    await msg.reply_text("⛔ فقط سوپرادمین.", reply_markup=_admin_kb(uid))
                return

            if text in ("👥 مدیریت کاربران سایت", "👥 مدیریت کاربران"):
                if _admin_section_visible_for_bot(uid, "users"):
                    await msg.reply_text(
                        "👥 به بخش مدیریت کاربران خوش آمدید. گزینه مورد نظر را انتخاب کنید:",
                        reply_markup=_admin_users_kb(),
                    )
                else:
                    await msg.reply_text(
                        "⛔ شما دسترسی به مدیریت کاربران ندارید.",
                        reply_markup=_admin_kb(uid),
                    )
                return

            if text == "📊 گزارش کلی کاربران":
                if _admin_section_visible_for_bot(uid, "users"):
                    try:
                        from giso_admin import list_giso_admins
                        admins = list_giso_admins()
                        adm_cnt = len(admins)
                        today_str = time.strftime("%Y-%m-%d")
                        with get_giso_db_conn() as conn:
                            cnt_site = conn.execute("SELECT COUNT(*) FROM giso_web_auth").fetchone()[0]
                            cnt_bot = conn.execute("SELECT COUNT(*) FROM giso_users").fetchone()[0]
                            cnt_today = conn.execute("SELECT COUNT(*) FROM giso_users WHERE last_active LIKE ?", (f"{today_str}%",)).fetchone()[0]
                            act_hair = conn.execute("SELECT COUNT(DISTINCT phone) FROM hair_orders WHERE phone != ''").fetchone()[0]
                            act_analysis = conn.execute("SELECT COUNT(DISTINCT phone) FROM analyses WHERE phone != ''").fetchone()[0]
                            act_shop = conn.execute("SELECT COUNT(DISTINCT phone) FROM product_orders WHERE phone != ''").fetchone()[0]
                            act_reviews = conn.execute("SELECT COUNT(DISTINCT phone) FROM reviews WHERE phone != ''").fetchone()[0]
                        rep_text = (
                            "👥 گزارش کلی کاربران گیسو\n\n"
                            "📊 آمار کلی:\n"
                            f"- کل کاربران سایت: {_fa_num(cnt_site)}\n"
                            f"- کل کاربران ربات: {_fa_num(cnt_bot)}\n"
                            f"- کاربران فعال امروز: {_fa_num(cnt_today)}\n"
                            f"- کل ادمین‌ها: {_fa_num(adm_cnt)}\n\n"
                            "📊 فعالیت:\n"
                            f"- درخواست فروش مو: {_fa_num(act_hair)} کاربر\n"
                            f"- آنالیز هوشمند: {_fa_num(act_analysis)} کاربر\n"
                            f"- سفارش فروشگاه: {_fa_num(act_shop)} کاربر\n"
                            f"- نظرات: {_fa_num(act_reviews)} کاربر"
                        )
                        await msg.reply_text(rep_text, reply_markup=_admin_users_kb())
                    except Exception as e_rep:
                        logger.error(f"report users err: {e_rep}")
                        await msg.reply_text("❌ خطا در ایجاد گزارش کلی کاربران.", reply_markup=_admin_users_kb())
                else:
                    await msg.reply_text(
                        "⛔ شما دسترسی به مدیریت کاربران ندارید.",
                        reply_markup=_admin_kb(uid),
                    )
                return

            if text == "🗑 حذف کاربران":
                if _admin_section_visible_for_bot(uid, "users"):
                    await msg.reply_text(
                        "🗑 به منوی حذف کاربران خوش آمدید. یکی از گزینه‌های زیر را انتخاب کنید:",
                        reply_markup=_admin_users_del_kb(),
                    )
                else:
                    await msg.reply_text(
                        "⛔ شما دسترسی به مدیریت کاربران ندارید.",
                        reply_markup=_admin_kb(uid),
                    )
                return

            if text == "🗑 حذف همه (بجز ادمین‌ها)":
                if _admin_section_visible_for_bot(uid, "users"):
                    from telegram import InlineKeyboardButton, InlineKeyboardMarkup
                    from giso_admin import list_giso_admins
                    admin_rows = list_giso_admins()
                    adm_phones = {"09156012931", "+989156012931"}
                    adm_bids = {"1191639507"}
                    for ar in admin_rows:
                        if ar.get("phone"):
                            adm_phones.add(normalize_phone(ar["phone"]))
                        if ar.get("bale_id"):
                            adm_bids.add(str(ar["bale_id"]))
                    count = 0
                    with get_giso_db_conn() as conn:
                        for u in conn.execute("SELECT bale_id, phone FROM giso_users WHERE is_admin=0").fetchall():
                            if str(u["bale_id"]) not in adm_bids and normalize_phone(u["phone"]) not in adm_phones:
                                count += 1
                        for w in conn.execute("SELECT phone FROM giso_web_auth").fetchall():
                            if normalize_phone(w["phone"]) not in adm_phones:
                                count += 1
                    kb = InlineKeyboardMarkup([
                        [InlineKeyboardButton("✅ بله، همه را حذف کن", callback_data="user_delete_all_confirm"),
                         InlineKeyboardButton("❌ خیر، لغو", callback_data="user_del_cancel")]
                    ])
                    await msg.reply_text(
                        "⚠️ هشدار جدی\n\n"
                        "شما در حال حذف تمام کاربران عادی هستید.\n"
                        f"تعداد کاربرانی که حذف می‌شوند: {_fa_num(count)}\n\n"
                        "این عمل قابل بازگشت نیست.\n\n"
                        "آیا کاملاً مطمئن هستید؟",
                        reply_markup=kb,
                    )
                else:
                    await msg.reply_text(
                        "⛔ شما دسترسی به مدیریت کاربران ندارید.",
                        reply_markup=_admin_kb(uid),
                    )
                return

            if text == "📋 حذف از لیست":
                if _admin_section_visible_for_bot(uid, "users"):
                    try:
                        from telegram import InlineKeyboardButton, InlineKeyboardMarkup
                        from giso_admin import list_giso_admins
                        admins = list_giso_admins()
                        adm_bids = {"1191639507"}
                        for a in admins:
                            if a.get("bale_id"):
                                adm_bids.add(str(a["bale_id"]))
                        with get_giso_db_conn() as conn:
                            rows = conn.execute("SELECT bale_id, phone, first_name FROM giso_users WHERE is_admin=0 ORDER BY last_active DESC LIMIT 10").fetchall()
                        non_admins = [r for r in rows if str(r["bale_id"]) not in adm_bids]
                        if not non_admins:
                            await msg.reply_text("📋 در حال حاضر هیچ کاربر غیرادمین در سیستم ثبت نشده است.", reply_markup=_admin_users_del_kb())
                        else:
                            await msg.reply_text("📋 لیست کاربران اخیر (برای حذف روی دکمه کاربر مورد نظر کلیک کنید):", reply_markup=_admin_users_del_kb())
                            for u in non_admins:
                                b_id = str(u["bale_id"])
                                fname = u["first_name"] or "کاربر"
                                ph = u["phone"] or "—"
                                kb_del = InlineKeyboardMarkup([
                                    [InlineKeyboardButton(f"🗑 حذف {fname} ({ph})", callback_data=f"user_del_req|{b_id}")]
                                ])
                                await msg.reply_text(f"👤 نام: {fname} | 📱 شماره: {ph} | 🆔 شناسه: {b_id}", reply_markup=kb_del)
                    except Exception as e_ulist:
                        logger.error(f"user del list err: {e_ulist}")
                        await msg.reply_text("❌ خطا در نمایش لیست کاربران.", reply_markup=_admin_users_del_kb())
                else:
                    await msg.reply_text(
                        "⛔ شما دسترسی به مدیریت کاربران ندارید.",
                        reply_markup=_admin_kb(uid),
                    )
                return

            if text == "🔎 جستجوی کاربر":
                if _admin_section_visible_for_bot(uid, "users"):
                    _user_states[uid] = "waiting_user_search"
                    await msg.reply_text(
                        "🔎 شماره موبایل، نام یا شناسه ربات کاربر را ارسال کنید تا خلاصه‌اش نمایش داده شود:",
                        reply_markup=_admin_users_del_kb(),
                    )
                else:
                    await msg.reply_text(
                        "⛔ شما دسترسی به مدیریت کاربران ندارید.",
                        reply_markup=_admin_kb(uid),
                    )
                return

            if text == "📱 حذف با شماره":
                if _admin_section_visible_for_bot(uid, "users"):
                    _user_states[uid] = "waiting_user_del_phone"
                    await msg.reply_text(
                        "📱 لطفاً شماره همراه کاربر مورد نظر را برای حذف ارسال کنید:",
                        reply_markup=_admin_users_del_kb(),
                    )
                else:
                    await msg.reply_text(
                        "⛔ شما دسترسی به مدیریت کاربران ندارید.",
                        reply_markup=_admin_kb(uid),
                    )
                return

            if text == "🔙 بازگشت":
                await msg.reply_text(
                    "به منوی اصلی ادمین بازگشتید.",
                    reply_markup=_admin_kb(uid),
                )
                return

            if text == "📊 پیشخوان":
                _today = time.strftime("%Y-%m-%d")
                with get_giso_db_conn() as conn:
                    pend_hair = conn.execute("SELECT COUNT(*) as c FROM hair_orders WHERE status='pending'").fetchone()["c"]
                    review_hair = conn.execute("SELECT COUNT(*) as c FROM hair_orders WHERE status='reviewing'").fetchone()["c"]
                    an_cnt = conn.execute("SELECT COUNT(*) as c FROM analyses").fetchone()["c"]
                    an_today = conn.execute("SELECT COUNT(*) FROM analyses WHERE created_at >= ?", (_today,)).fetchone()[0]
                    pend_shop = conn.execute("SELECT COUNT(*) as c FROM product_orders WHERE status='pending'").fetchone()["c"]
                    orders_today = conn.execute("SELECT COUNT(*) FROM product_orders WHERE created_at >= ?", (_today,)).fetchone()[0]
                    try:
                        rev_today = conn.execute(
                            "SELECT COALESCE(SUM(p.price * o.quantity),0) FROM product_orders o "
                            "JOIN products p ON p.id=o.product_id "
                            "WHERE o.status='completed' AND o.created_at >= ?", (_today,)).fetchone()[0] or 0
                    except Exception:
                        rev_today = 0
                    prod_cnt = conn.execute("SELECT COUNT(*) as c FROM products").fetchone()["c"]
                    prod_pend = conn.execute("SELECT COUNT(*) FROM products WHERE publish_status='pending'").fetchone()[0]
                    web_cnt = conn.execute("SELECT COUNT(*) as c FROM giso_web_auth").fetchone()["c"]
                    web_today = conn.execute("SELECT COUNT(*) FROM giso_web_auth WHERE created_at >= ?", (_today,)).fetchone()[0]
                    bot_cnt = conn.execute("SELECT COUNT(*) as c FROM giso_users").fetchone()["c"]
                    hair_today = conn.execute("SELECT COUNT(*) FROM hair_orders WHERE created_at >= ?", (_today,)).fetchone()[0]
                    # اخبار جدید امروز (مرکز اعلان‌ها — اگر جدول موجود باشد)
                    news_today = []
                    try:
                        news_today = conn.execute(
                            "SELECT category, title FROM giso_notifications "
                            "WHERE created_at >= ? ORDER BY id DESC LIMIT 5", (_today + " 00:00:00",)).fetchall()
                    except Exception:
                        news_today = []
                _cat_emoji = {"shop": "🛍", "hair_sale": "💇", "analysis": "🔬", "users": "👥",
                              "wallet": "💳", "channel": "📢", "bot": "🤖", "security": "🛡", "system": "⚙️"}
                dash_parts = [
                    "📊 پیشخوان مدیریت گیسو",
                    "━━━━━━━━━━━━━━━━",
                    f"📅 امروز ({_today}):",
                    f"   👥 عضو جدید: {_fa_num(web_today)} | 🔬 آنالیز: {_fa_num(an_today)}",
                    f"   💇 درخواست مو: {_fa_num(hair_today)} | 🛍 سفارش: {_fa_num(orders_today)}",
                    f"   💰 فروش امروز: {format_toman(int(rev_today))}",
                    "",
                    "📰 اخبار جدید امروز:",
                ]
                if news_today:
                    for _ne in news_today:
                        dash_parts.append(f"   {_cat_emoji.get(_ne['category'], '🔔')} {_ne['title'] or _ne['category']}")
                else:
                    dash_parts.append("   — رویداد جدیدی ثبت نشده است.")
                dash_parts += [
                    "",
                    "⏳ در انتظار اقدام:",
                    f"   💇 فروش مو: {_fa_num(pend_hair)} جدید / {_fa_num(review_hair)} در حال بررسی",
                    f"   🛍 سفارش‌های فروشگاه: {_fa_num(pend_shop)}",
                    f"   📦 محصول منتظر تأیید: {_fa_num(prod_pend)}",
                    "",
                    "📈 موجودی کلی:",
                    f"   🔬 آنالیز‌ها: {_fa_num(an_cnt)} | 📦 محصولات: {_fa_num(prod_cnt)}",
                    f"   👤 کاربران سایت: {_fa_num(web_cnt)} | 🤖 کاربران ربات: {_fa_num(bot_cnt)}",
                ]
                await msg.reply_text("\n".join(dash_parts), reply_markup=_admin_kb(uid))
                # فاز P2: تریگر lazy گزارش بازاریابی روزانه (حداکثر یک‌بار در روز)
                try:
                    from giso.marketing import maybe_send_daily_digest
                    maybe_send_daily_digest()
                except Exception:
                    pass
                # مرحله ۵: تریگر واریز شبانه‌ی اعتبار رتبه (idempotent، یک‌بار در روز)
                try:
                    from giso.rank_daily import maybe_deposit_rank_credits
                    maybe_deposit_rank_credits()
                except Exception:
                    pass
                return

            # رفع باگ قدیمی: کیبورد «🛒 سفارش‌ها» می‌فرستاد ولی هندلر «🛍 سفارش‌ها» را چک می‌کرد
            if text in ("🛍 سفارش‌ها", "🛒 سفارش‌ها", "🧾 سفارش‌های جدید"):
                with get_giso_db_conn() as conn:
                    rows = conn.execute(
                        "SELECT po.id, po.customer_name, po.phone, po.status, po.created_at, p.name as pname "
                        "FROM product_orders po LEFT JOIN products p ON po.product_id=p.id "
                        "ORDER BY po.id DESC LIMIT 10"
                    ).fetchall()
                if not rows:
                    await msg.reply_text("🛍 هیچ سفارش محصولی ثبت نشده است.", reply_markup=_admin_kb(uid))
                else:
                    lines = ["🛍 سفارش‌های فروشگاه (۱۰ مورد اخیر):", "━━━━━━━━━━━━━━━━"]
                    for r in rows:
                        lines.append(
                            f"\n🔹 سفارش #{_fa_num(r['id'])} | {r['pname'] or '—'}\n"
                            f"   👤 {r['customer_name'] or '—'} | 📱 {r['phone'] or '—'}\n"
                            f"   📌 وضعیت: {r['status']} | 📅 {to_shamsi(r['created_at'])}"
                        )
                    await msg.reply_text("\n".join(lines), reply_markup=_admin_kb(uid))
                return

            if text == "📬 درخواست‌های آنالیز":
                with get_giso_db_conn() as conn:
                    rows = conn.execute("SELECT * FROM analyses ORDER BY id DESC LIMIT 10").fetchall()
                if not rows:
                    await msg.reply_text("📬 هیچ درخواست آنالیز هوشمندی ثبت نشده است.", reply_markup=_admin_kb(uid))
                else:
                    lines = ["📬 درخواست‌های آنالیز هوشمند (۱۰ مورد اخیر):", "━━━━━━━━━━━━━━━━"]
                    for r in rows:
                        rep = r["ai_report_json"] or "{}"
                        has_rep = "دارد" if rep.strip("{}").strip() else "در انتظار"
                        lines.append(
                            f"\n🔹 آنالیز #{_fa_num(r['id'])} | نوع: {r['type'] or '—'}\n"
                            f"   📱 {r['phone'] or '—'} | 📌 گزارش: {has_rep} | 📅 {to_shamsi(r['created_at'])}"
                        )
                    await msg.reply_text("\n".join(lines), reply_markup=_admin_kb(uid))
                return

            if text == "📦 محصولات":
                with get_giso_db_conn() as conn:
                    rows = conn.execute("SELECT * FROM products ORDER BY id DESC LIMIT 15").fetchall()
                if not rows:
                    await msg.reply_text("📦 در حال حاضر هیچ محصولی در فروشگاه ثبت نشده است.", reply_markup=_admin_kb(uid))
                else:
                    lines = ["📦 محصولات فروشگاه گیسو:", "━━━━━━━━━━━━━━━━"]
                    for p in rows:
                        st_icon = "✅ موجود" if p["in_stock"] else "❌ ناموجود"
                        cat = p["category"] or "—"
                        lines.append(f"\n🔹 {p['name']} ({cat})\n   💰 {format_toman(p['price'])} | {st_icon}")
                    await msg.reply_text("\n".join(lines), reply_markup=_admin_kb(uid))
                return

            if text == "📢 مدیریت کانال":
                await msg.reply_text(
                    "📢 مدیریت کانال اطلاع‌رسانی گیسو از پنل ادمین وب‌سایت گیسو انجام می‌شود. "
                    "از این بخش در ربات، پیام‌های خودکار و اعلان‌ها برای مشتریان ارسال می‌شود.",
                    reply_markup=_admin_kb(uid),
                )
                return

            await msg.reply_text(
                "🚧 این بخش در حال تکمیل است.",
                reply_markup=_admin_kb(uid),
            )
            return

        if _is_admin_request_phrase(text):
            await _process_admin_keyword(uid, phone, fname, existing, msg, context)
            return

        if text == "🏪 بازارچه مو":
            # مسیر واحد: همان ویوی «آگهی‌های من + آمار» در ماژول ua| (قبلاً لینک خام تکراری بود).
            await _uact.send_ua_view(msg, phone, "ua|mkt|my")
            return

        if text == "🛍 فروشگاه":
            # مسیر واحد: سفارش‌ها + وضعیت + فاکتور/پیگیری/سفارش مجدد در ماژول ua| (حذف لینک خام تکراری).
            await _uact.send_ua_view(msg, phone, "ua|shop|orders")
            return

        if text == "📦 سفارش‌های من":
            await _msg_user_orders(msg, phone)
            return

        if text == "⭐ ثبت نظر":
            await _msg_user_review_picker(msg, phone)
            return

        if text == "🔍 آنالیز هوشمند":
            await handle_analysis_menu(update, context)
            return

        if text == "🏥 مرکز زیبایی من":
            try:
                from giso.user_profile_service import get_user_profile
                profile = get_user_profile(phone)
                site_url = _get_giso_site_url() or "https://gisosadeghi.ir"
                if not profile:
                    await msg.reply_text(
                        "برای مدیریت مرکز، ابتدا حساب سایت را با همین شماره فعال کن.",
                        reply_markup=_ikm([[_ikb("ثبت‌نام در سایت", url=f"{site_url}/register")]]),
                    )
                else:
                    from giso.beauty_centers.services import get_owner_center
                    center = get_owner_center(int(profile.get("id") or 0))
                    if not center:
                        await msg.reply_text(
                            "هنوز مرکزی برای این حساب ثبت نشده است.",
                            reply_markup=_ikm([[_ikb("ثبت مرکز زیبایی", url=f"{site_url}/beauty-centers/register")]]),
                        )
                        return
                    from giso.beauty_centers.bot_handlers import handle_beauty_owner_callback
                    class _MessageQuery:
                        message = msg
                        async def answer(self, *args, **kwargs): return None
                    await handle_beauty_owner_callback(_MessageQuery(), int(profile.get("id") or 0), site_url)
            except Exception as exc:
                logger.error("user beauty center menu failed: %s", exc)
                await msg.reply_text("دریافت وضعیت مرکز ممکن نشد؛ از پنل سایت ادامه بده.", reply_markup=_user_kb())
            return

        if text == CONSULTANT_AI_LABEL:
            await _start_consultant_ai_chat(msg, context, uid, runtime_role, is_query=False)
            return
        # مشاور هوشمند: برچسب کامل قدیمی مستقیم وارد چت می‌شود؛ برچسب کوتاه «🤖 مشاور»
        # ابتدا کارت گزارش وضعیت را نشان می‌دهد (سوال بپرس → همان فلوی چت موجود).
        if text in (CONSULTANT_AI_LABEL, "💬 مشاور", "🤖 مشاور", "🤖 مشاور هوشمند", "🤖 مشاور هوشمند شخصی گیسو"):
            await _start_consultant_ai_chat(msg, context, uid, runtime_role, is_query=False)
            return

        if text in ("💰 کیف پول من", "💰 کیف پول"):
            # ویوی کوتاه جدید (مانده دوگانه + رتبه)؛ جزئیات بیشتر با لینک سایت
            await _uact.send_ua_view(msg, phone, "ua|wallet|main")
            return

        if text in ("🎯 مأموریت", "🎯 مأموریت‌ها"):
            # ویوی درون‌رباتی مأموریت‌ها (لیست + وضعیت + امتیاز/رتبه)
            await _uact.send_ua_view(msg, phone, "ua|mission|main")
            return

        if text in ("💬 پشتیبانی", "🎧 پشتیبانی"):
            await handle_support_menu_text(msg)
            return

        if text in ("👤 حساب من", "👤 پروفایل من", "👤 پروفایل"):
            # ویوی کوتاه جدید؛ نسخه‌ی کامل/ویرایش از طریق دکمه‌های درون ویو (upro|) در دسترس است
            await _uact.send_ua_view(msg, phone, "ua|profile|main")
            return

        if text == "🔔 اعلان‌های من":
            try:
                await _show_user_notifications(msg, phone)
            except Exception as e:
                logger.error(f"bot user notifications error: {e}")
                await msg.reply_text("❌ خطا در دریافت اعلان‌ها.", reply_markup=_user_kb())
            return

        if await handle_hair_sale_commands(msg, text, uid, phone, existing.get("is_admin"), _user_states,
                                           _admin_kb, _user_kb, _admin_hair_sale_kb, _user_hair_sale_kb,
                                           _admin_hair_status_kb):
            return

        if text == "/start":
            _set_consultant_ai_active(context, False)
            info = _giso_lookup(uid, phone)
            role = "admin" if info["is_admin"] else ("pending" if info["is_pending"] else "user")
            _upsert_giso_user(uid, is_admin=(role == "admin"),
                              pending_request=(role == "pending"))
            runtime_role2 = "super" if _is_super_admin(uid, phone) else ("admin" if role == "admin" else "user")
            if await _send_smart_welcome_message(msg, uid, runtime_role2, force=True):
                if role == "admin":
                    await msg.reply_text("از منوی ادمین ادامه بده 👇", reply_markup=_admin_kb(uid))
                else:
                    await msg.reply_text("از منوی زیر ادامه بده 👇", reply_markup=_user_kb(pending=(role == "pending")))
            else:
                await _show_panel(msg, fname, role, uid=uid)
            return

        if should_show_rewelcome and not text.startswith("/"):
            sent = await _send_smart_welcome_message(msg, uid, runtime_role, force=False)
            if sent:
                if runtime_role == "admin":
                    await msg.reply_text("از منوی ادمین ادامه بده 👇", reply_markup=_admin_kb(uid))
                else:
                    await msg.reply_text("از منوی زیر ادامه بده 👇", reply_markup=_user_kb(pending=bool(existing.get("pending_request"))))
                return

        await _send_consultant_ai_guidance(msg, runtime_role)

    async def handle_error(update, context):
        """ثبت خطای کنترل‌نشده و پاسخ کوتاه؛ مانع پیام «No error handlers» می‌شود."""
        logger.exception("خطای کنترل‌نشده ربات گیسو", exc_info=context.error)
        try:
            from giso.monitoring_errors import record
            record('giso-bot',getattr(getattr(update,'effective_message',None),'text','handler'),context.error)
        except Exception:pass
        try:
            target = update.effective_message if update else None
            if target:
                await target.reply_text("❌ در اجرای این بخش خطایی رخ داد. لطفاً دوباره تلاش کنید.")
        except Exception:
            pass

    if test_mode:
        return {
            "start": start,
            "handle_text": handle_text,
            "handle_callback": handle_callback,
            "handle_contact": handle_contact,
            "user_states": _user_states,
        }

    loop = asyncio.get_running_loop()
    while True:
        app = None
        current_token = (_token_from_env() or _token_from_db() or "").strip()
        if not current_token:
            logger.error(
                "⚠️ توکن ربات گیسو ثبت نشده است. "
                "از پنل ادمین ربات اصلی «🎀 مدیریت ربات گیسو» → «🔑 تنظیم توکن» را بزنید."
            )
            return False

        try:
            logger.info(
                "Building Giso bot (Bale)... token=%s...%s pid=%d",
                current_token[:8], current_token[-4:], os.getpid(),
            )
            app = _build_app(current_token)
            # 🆕 پست‌های کانال فروشگاه — اولِ اول ثبت می‌شود تا به هیچ هندلر دیگر (حتی /start) نرسد
            app.add_handler(MessageHandler(filters.ChatType.CHANNEL, handle_channel_post))
            app.add_handler(CommandHandler("start", start))
            # پرداخت آنی کیف پول بله (docs.bale.ai → پرداخت)
            from giso.bot_balepay import handle_pre_checkout as _balepay_pre, handle_successful_payment as _balepay_paid
            app.add_handler(PreCheckoutQueryHandler(_balepay_pre))
            app.add_handler(MessageHandler(filters.SUCCESSFUL_PAYMENT, _balepay_paid))
            app.add_handler(MessageHandler(filters.CONTACT, handle_contact))
            app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
            app.add_handler(MessageHandler(filters.COMMAND, handle_text))
            app.add_handler(MessageHandler(filters.Document.ALL, handle_document))  # بارگذاری backup
            app.add_handler(MessageHandler(filters.PHOTO & ~filters.ChatType.CHANNEL, handle_private_photo))  # تعویض عکس محصول منتظر تأیید
            app.add_handler(CallbackQueryHandler(handle_callback))  # مهم: ثبت هندلر دکمه‌های اینلاین
            app.add_error_handler(handle_error)
            _write_pid(os.getpid())
            logger.info("✅ Giso bot running on Bale.")

            # ═══ شروع backup خودکار (اگر تنظیم شده) ═══
            _init_auto_backup(app)

            # ═══ checkpoint خودکار giso.db هر ۵ دقیقه ═══
            _init_periodic_checkpoint(app)
            _init_broadcast_queue(app)
            _init_monitoring_ai(app)

            await app.initialize()
            await app.start()
            await app.updater.start_polling(drop_pending_updates=True)
            await asyncio.Event().wait()
        except asyncio.CancelledError:
            raise
        except KeyboardInterrupt:
            raise
        except Exception as e:
            logger.error(
                "❌ Giso bot error: %s — retrying in %ds...",
                e, RETRY_DELAY_SECS,
            )
            new_token = (_token_from_env() or _token_from_db() or "").strip()
            if not new_token:
                logger.warning("Token removed — Giso bot stopped.")
                return False
            await asyncio.sleep(RETRY_DELAY_SECS)
        finally:
            if app is not None:
                try:
                    await app.updater.stop()
                except Exception:
                    pass
                try:
                    await app.stop()
                except Exception:
                    pass
                try:
                    await app.shutdown()
                except Exception:
                    pass

async def get_test_handlers(token="123456789:AA_dummy_token"):
    return await _run_async(token, test_mode=True)

def run_bot(token=None):
    if token:
        os.environ["GISO_BOT_TOKEN"] = str(token)
    try:
        import telegram  # noqa: F401
    except ImportError:
        logger.error(
            "python-telegram-bot is not installed. Run: pip install python-telegram-bot==20.7"
        )
        return False
    _giso_init_db()
    _clear_pid()
    try:
        from giso.async_compat import run_async_safe
        run_async_safe(_run_async(token))
        return True
    except KeyboardInterrupt:
        logger.info("Giso bot interrupted.")
        return True
    finally:
        _clear_pid()


# re-export — نام‌های مصرف‌شده توسط تست‌ها (بازگردانی مرحلهٔ ۳ پاک‌سازی 1.md)
from giso.bot_admin_utils import _get_bot_chat_history, _get_user_dashboard_info, _get_user_full_context  # re-export
from giso.bot_helpers import _extract_analysis_score  # re-export

# Phase 2 / U6 — re-export (cut & paste safe module)
from giso.bot_helpers import (
    send_long_message,
    _VISIBLE_ROLE_SECTIONS,
    _BOT_OPERATIONAL_SECTIONS,
    _managed_ai_provider_picker_text,
    _managed_ai_permission_detail_text,
    _managed_ai_dashboard_text,
    _ratelimit_status_text,
    _has_provider_ai_management_access,
    _is_legacy_ai_callback,
    _role_has_consultant_ai,
    _normalize_admin_phrase,
    _is_admin_request_phrase,
    _admin_section_visible_for_bot,
    _extract_analysis_topic,
    _format_persian_date,
    _user_delete_info_text,
    make_state_pruner,
)  # _BOT_OPERATIONAL_SECTIONS, _normalize_admin_phrase, _extract_analysis_topic: re-export

# Phase 2 / U6 — re-export (cut & paste safe module)
from giso.bot_backup import (
    _backup_dir,
    _list_backup_files,
    _backup_max_files,
    _list_backup_files_detail,
    _giso_restore_from_path,
    _get_backup_interval_hours,
    _set_backup_interval_hours,
)

# Phase 5 — re-export (user in-bot views moved to bot_user_actions)
from giso.bot_user_actions import (
    _msg_user_orders,
    _msg_user_review_picker,
    _handle_shop_review_state,
)

# Phase 2 / U6 — re-export (cut & paste safe module)
from giso.bot_admin_utils import (
    DEFAULT_SITE_BASE_URL,
    SITE_BASE_URL,
    _shop_order_rows,
    _lookup_user_delete_info,
    _lookup_user_info,
    _get_giso_site_url,
    _set_giso_site_url,
    _test_giso_site_url,
    _check_site_user_info,
    _build_welcome_from_site,
    _default_welcome_message,
    _is_special_admin_bot,
    _special_menu_kb,
    _special_welcome_text,
    handle_special_assistant_bot_text,
    _complete_hair_order_mission,
    _get_user_phone,
    _get_user_analyses,
    _get_analysis_by_id,
    _get_latest_analysis,
    _get_latest_analysis_with_plan,
    _is_giso_admin,
    _get_admin_analysis_stats,
    _get_recent_analyses,
    _get_recent_consultant_requests,
    _get_recent_product_requests,
    _save_bot_chat_message,
    _ask_consultant_bot,
    _ensure_support_tickets_table,
    _create_support_ticket,
    _get_bale_id_by_phone,
    _build_smart_welcome_user,
    _get_admin_dashboard_stats,
    _build_smart_welcome_admin,
    _get_chat_summaries,
)  # SITE_BASE_URL, _build_welcome_from_site, _default_welcome_message, _build_smart_welcome_user, _build_smart_welcome_admin: re-export

if __name__ == "__main__":
    run_bot()# P0-Recovery: ensure uploads backed up and restore preserves User/Order/Analysis/HairSale/Bale relations
