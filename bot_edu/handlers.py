"""
handlers.py — همه handler‌های تلگرام
وابستگی مجاز: config، core، ui و telegram
"""
import time
import logging
import os
import sys
import html
import sqlite3
import asyncio
import shutil

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from config import (
    ADMIN_IDS, SUPPORT_GROUP, BOT_USERNAME, DB_PATH,
    COURSES, PROGRESS, USERS, TICKETS, SETTINGS, SHOP, SURVEYS, BOT_COMMANDS, MISSIONS,
    CASH_SALES, FEATURE_ACCESS, CASH_SALE_SETTINGS,
    save,
)
from core import (
    is_admin, ltype, next_cid, next_sid, next_mid, match_cmd,
    register_user, valid_refs, user_rank, normal_users_sorted,
    completed_lessons, total_lessons,
    full_access_check,
    apply_lesson, set_src, get_src, src_back,
    award_xp_and_credits, purchase_shop_item,
    has_completed_mission, complete_mission, MISSION_XP_LIMITS,
    _migrate_user,
    set_user_xp, add_user_xp, set_user_credits, add_user_credits,
    set_user_ban, set_user_mute, is_user_banned, is_user_muted,
    set_feature_rule, check_feature_access,
    FEATURE_KEYS, FEATURE_LABELS,
    set_user_feature_restriction, remove_user_feature_restriction, check_user_specific_access,
    get_cash_sale_setting, set_cash_sale_setting,
    has_phone, set_user_phone, normalize_phone,
    SECONDARY_PLATFORMS, platform_name, platform_enabled,
    get_current_platform, set_current_platform, detect_platform,
    user_has_platform, user_can_connect_platform, get_platform_link_mission,
    create_link_code,
    create_admin_link_code, register_platform_admin,
    canonical_user_id, is_banned_globally, build_deep_link,
    effective_user, touch_platform_activity,
    resolve_platform_identity_by_phone,
    members_count, fa_num, support_link,
    platform_invite_link, platform_bot_link,
    record_bot_group,
    get_platform_admins,
)
from config import get_platform_bot, active_platform_bots, sync_deleted_users_from_db
from ui import (
    btn, mkb, back_btn, home_btn, safe_answer,
    reply_kb, main_kb, src_kb, done_kb, lesson_menu_kb, phone_kb,
    show_access_denied, show_courses, show_course_user, send_lesson,
    show_profile, show_referral, show_shop, show_career_path,
    show_leaderboard, show_support, admin_panel, a_shop_panel,
    save_forwarded, show_latest_events, show_missions, show_mission_detail,
    a_missions_panel,
    show_users_manage, show_users_list, show_user_delete_menu, show_user_delete_list,
    show_user_detail, show_user_xp_panel, show_user_credit_panel,
    show_user_feature_restrictions,
    show_feature_access_panel, show_feature_detail,
    show_cash_sales_admin, show_cash_sale_review, show_cash_sale_request,
    show_cash_lesson_sale_request,
    show_phone_registration,
    format_card_number, format_card_admin,
    show_platform_management, show_platform_detail, show_platform_admins_list,
    show_platform_report, show_platform_link_prompt,
    show_proxy_menu, show_proxy_mode_menu, show_proxy_list,
    show_messaging_stats, show_phone_list,
    web_manage_kb, web_main_manage_kb, web_giso_manage_kb,
    bcast_type_kb,
)
from handlers_admin import (
    build_cash_admin_caption,
    bot_route_targets,
    send_cash_status_strict,
    send_ticket_reply_strict,
)
import proxy_manager as pm
from handlers_ai import (
    AI_STATES,
    handle_ai_callback,
    handle_ai_state,
)

# 🤖 ماژول «یار هوشمند شغلی» — پکیج جدا، بدون دست‌زدن به منطق موجود
from ai_mentor.ai_handlers import (
    AIM_MEDIA_STATES,
    AIM_STATES,
    handle_aim_callback,
    handle_aim_media,
    handle_aim_state,
    try_verification_code,
)
from ai_mentor.ai_admin import (
    AIMA_STATES,
    handle_aim_admin_callback,
    handle_aim_admin_state,
)
from platform_runtime import (
    apply_telegram_enabled,
    reload_telegram,
    stop_telegram,
    status_text as telegram_status_text,
)
from services.admin_service import (
    list_all_users as admin_list_all_users,
    delete_user_everywhere as admin_delete_user_everywhere,
    delete_all_users as admin_delete_all_users,
    resolve_user_id_by_phone as admin_resolve_user_id_by_phone,
    get_maintenance_flag as admin_get_maintenance_flag,
    set_maintenance_flag as admin_set_maintenance_flag,
    set_setting_value as admin_set_setting_value,
    get_site_health_report as admin_get_site_health_report,
    cleanup_server_sessions as admin_cleanup_server_sessions,
    cleanup_safe_caches as admin_cleanup_safe_caches,
    cleanup_incomplete_requests as admin_cleanup_incomplete_requests,
)
from handlers_messaging import (
    BC_DELAY_MAX as _BC_DELAY_MAX,
    BC_DELAY_MIN as _BC_DELAY_MIN,
    do_send as messaging_do_send,
    set_send_delay as messaging_set_delay,
    show_delay_menu,
    get_destination_count as messaging_get_destination_count,
    reset_bc as messaging_reset_bc,
    resolve_direct_target_strict,
    show_delivery_report_detail,
    show_delivery_reports,
    platform_user_entries as messaging_user_entries,
    show_bc_user_list,
    show_destination_menu as show_bc_destination_menu,
    show_messaging_center_v2,
    show_preview as messaging_show_preview,
    show_user_mode_menu,
)

logger = logging.getLogger(__name__)


def clear_user_state(ctx) -> str:
    """
    [باگ ۲ — رفع تلهٔ state] پاک‌کردن state متنیِ نیمه‌تمام.

    وقتی کاربر وسط یک فلوی متنی (مثلاً «ارسال تیکت») روی دکمه‌ای کلیک می‌کند،
    یعنی از آن فلو منصرف شده است. اگر state پاک نشود، پیام متنی بعدی او
    به‌اشتباه به‌عنوان ورودی همان فلو ثبت می‌شود.

    خروجی: state پاک‌شده (یا "" اگر چیزی نبود) — برای لاگ/تست.
    """
    old = ctx.user_data.pop("state", None)
    if not old:
        return ""
    # داده‌های موقتِ همان فلو هم پاک می‌شوند تا نشتی به فلوی بعدی نداشته باشیم
    for k in (
        "target_uid", "block_fkey", "feature_key", "feature_field",
        "proxy_platform", "platform_target",
        "cst_target_type", "cst_target_id", "cst_cid", "cst_idx",
        "cst_card_number", "cst_card_holder",
        "cash_target_type", "cash_target_id",
        "ticket_idx",
        # 🤖 یار هوشمند شغلی — پیش‌نویس مصاحبه و گام در حال پاسخ
        "aim_draft", "aim_step_id", "aima_key",
    ):
        ctx.user_data.pop(k, None)
    return old


# callbackهایی که ادامهٔ یک فلوی چندمرحله‌ای هستند و state باید حفظ شود
_STATE_KEEPING_PREFIXES = (
    "ai_kind|",           # انتخاب نوع پروایدر AI  (ادامهٔ فلوی افزودن)
    "src|",               # انتخاب نوع منبع سرفصل  (choose_type)
    "a_cmd_type|",        # انتخاب نوع دستور        (wait_cmd_type)
    "a_cmd_scope|",
    "a_cmd_match|",
    "a_cmd_adminonly|",
    "a_cmd_action|",
    "a_item_kind|",       # انتخاب نوع آیتم گنجینه  (wait_item_kind)
    "a_mission_type|",    # انتخاب نوع ماموریت      (wait_mission_type_select)
    "a_mission_plat|",
)


def _confirm_kb(yes_cb: str, cancel_cb: str):
    """[باگ ۳] کیبورد دومرحله‌ای تایید حذف."""
    return mkb([
        [btn("✅ بله، حذف کن", yes_cb)],
        [btn("❌ انصراف", cancel_cb)],
    ])


def _confirm_text(what: str, extra: str = "") -> str:
    """[باگ ۳] متن استاندارد تایید حذف."""
    body = (
        "⚠️ تایید حذف\n"
        "━━━━━━━━━━━━━━━━\n\n"
        f"{what}\n\n"
    )
    if extra:
        body += extra + "\n\n"
    return body + "❗️ این عملیات قابل بازگشت نیست.\nآیا مطمئن هستید؟"


def messaging_delay_min() -> float:
    return _BC_DELAY_MIN


def messaging_delay_max() -> float:
    return _BC_DELAY_MAX


# ========================= مرکز پیام‌رسانی (نوع پیام) =========================
# منطق کامل ارسال/پیش‌نمایش/گزارش در handlers_messaging.py پیاده شده است.
# فقط این نگاشت اینجا مانده چون شاخهٔ callback «bc_type|» از آن استفاده می‌کند.

_TYPE_FA = {"text": "متنی", "photo": "تصویری", "video": "ویدیو"}


# ========================= استارت =========================

async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    raw_user = update.effective_user
    # تشخیص پلتفرم فعلی از روی bot (بله/تلگرام/...)
    platform = detect_platform(ctx.bot)
    set_current_platform(platform)

    if update.effective_chat and update.effective_chat.type in ["group", "supergroup", "channel"]:
        # ثبت گروه/کانال برای ارسال گروهی مرکز پیام‌رسانی
        try:
            ch = update.effective_chat
            record_bot_group(platform, ch.id, ch.title or "", ch.type or "group")
        except Exception as e:
            logger.error(f"record_bot_group (start) error: {e}")
        u_eff = effective_user(raw_user, platform)
        txt = "👑 خوش آمدید، شما ادمین هستید." if is_admin(u_eff) else "❌ شما دسترسی ندارید."
        try:
            await update.message.reply_text(txt)
        except Exception as e1:
            logger.error(f"group start reply_text failed ({platform}): {e1}; retry send_message")
            try:
                await ctx.bot.send_message(update.effective_chat.id, txt)
            except Exception as e2:
                logger.error(f"group start send_message failed ({platform}): {e2}")
        return

    # بن سراسری — اگر در هر پلتفرمی بن باشد، پردازش نشود
    if is_banned_globally(platform, raw_user.id):
        await update.message.reply_text("⛔️ حساب شما مسدود شده است و امکان استفاده از ربات را ندارید.")
        return

    arg = ctx.args[0] if ctx.args else ""

    # ===== پلتفرم ثانویه (تلگرام): فلوی اشتراک شماره/اتصال =====
    if platform != "bale":
        await _handle_secondary_start(update, ctx, platform, raw_user, arg)
        return

    # ===== بله (پلتفرم پایه) =====
    ref = None
    if arg:
        try:
            ref = int(arg)
            if ref == raw_user.id or ref in ADMIN_IDS:
                ref = None
        except Exception:
            ref = None
    register_user(raw_user, ref)

    # مرحله اول — ثبت اجباری شماره تلفن برای همه کاربران (حتی ادمین)
    if not has_phone(raw_user.id):
        ctx.user_data["state"] = "wait_phone"
        await show_phone_registration(update.message, raw_user)
        return

    await send_main_welcome(update.message, raw_user)


async def _handle_secondary_start(update, ctx, platform, raw_user, arg):
    """استارت در پلتفرم ثانویه (تلگرام/...).
    اگر کاربر از قبل متصل باشد → ورود عادی با هویت اصلی.
    در غیر این صورت → درخواست اشتراک شمارهٔ تلفن (مثل بله) برای ادغام/ساخت حساب."""
    raw_id = raw_user.id

    # استخراج زمینهٔ ورود از arg: لینک ادمین / کد ماموریت اتصال / معرف
    pending = {"admin_code": "", "link_code": "", "referrer": None}
    if arg.startswith("a"):
        pending["admin_code"] = arg
    elif arg.startswith("u"):
        pending["link_code"] = arg
    elif arg:
        try:
            r = int(arg)
            if r != raw_id and r not in ADMIN_IDS:
                pending["referrer"] = r
        except Exception:
            pass

    # از قبل متصل → ورود عادی با هویت اصلی (canonical)
    if canonical_user_id(platform, raw_id) is not None:
        user = effective_user(raw_user, platform)
        register_user(user)
        touch_platform_activity(platform, raw_id)
        if pending["admin_code"]:
            register_platform_admin(platform, raw_id, pending["admin_code"])
        await send_main_welcome(update.message, user)
        return

    # لینک ادمینِ صرف (شخصی که در بله ادمین نیست) → همین حالا ادمینِ این پلتفرم شود،
    # ولی برای فعال‌سازی حساب باز هم باید شماره بدهد.
    if pending["admin_code"]:
        register_platform_admin(platform, raw_id, pending["admin_code"])

    # هنوز متصل نیست → باید شمارهٔ خودش را اشتراک بگذارد (فقط دکمهٔ اشتراک مخاطب)
    ctx.user_data["state"] = "wait_phone_secondary"
    ctx.user_data["sec_platform"] = platform
    ctx.user_data["sec_pending"] = pending
    await show_phone_registration(update.message, raw_user, platform=platform)


async def send_main_welcome(message, user):
    platform_line = f"🌐 شما از طریق پلتفرم «{platform_name(get_current_platform())}» متصل شده‌اید.\n"
    members_line = f"👥 تا الان {fa_num(members_count())} نفر عضو شده‌اند.\n\n"
    sup_disp, _ = support_link()
    if is_admin(user):
        text = (
            "👑 خیلی خوش آمدید جناب مهندس صادقی 💎\n\n"
            f"{platform_line}{members_line}"
            "ربات با موفقیت فعال شد و در خدمت شماست.\n"
            "از پنل مدیریت برای کنترل ربات استفاده کنید."
        )
        await message.reply_text(text, reply_markup=reply_kb(user))
    else:
        name = user.first_name or "دوست"
        u = USERS.get(str(user.id), {})
        _migrate_user(u)
        xp = u.get("xp", u.get("points", 0))
        credits = u.get("credits", 0)
        rnk = user_rank(user.id)
        tot = len(normal_users_sorted())

        # پیام اول — خوشامدگویی انرژی‌زا
        text1 = (
            f"🔥 سلام {name} عزیز! خوش اومدی!\n\n"
            f"{platform_line}{members_line}"
            f"🎓 به ربات آموزشی درآمدساز صادقی خوش آمدید!\n\n"
            f"✨ اینجا یاد می‌گیری, امتیاز می‌گیری و رشد می‌کنی!\n"
            f"دوره‌های آموزشی رایگان، سیستم رقابتی هوشمند و\n"
            f"جوایز ارزشمند منتظرته! 🏆\n\n"
            f"📈 امتیاز رشد (XP) فعلی: {xp}\n"
            f"💰 اعتبار فعلی: {credits}\n"
            f"🥇 رتبه شما: {rnk} از {tot} نفر\n\n"
            f"💡 امتیاز بگیر → رتبه بگیر → جوایز باز کن!\n\n"
            f"💬 گروه گفت‌وگوی تخصصی: {sup_disp}\n\n"
            f"👇 برای شروع روی «لیست دوره‌ها» بزن!"
        )
        await message.reply_text(text1, reply_markup=reply_kb(user))

        # پیام دوم — راهنمای کامل و شفاف
        text2 = (
            "📋 راهنمای کامل پنل کاربری\n\n"
            "━━━━━━━━━━━━━━━━\n"
            "📚 بخش‌های اصلی:\n"
            "  🎓 لیست دوره‌ها — مشاهده و شروع دوره‌های آموزشی\n"
            "  🏆 پروفایل من — آمار، سطح، رتبه و پیشرفت شما\n"
            "  🎯 ماموریت‌ها — انجام وظایف امتیازی و کسب XP\n"
            "  💎 گنجینه — خرید جوایز ویژه با اعتبار انباشته‌شده\n"
            "  📰 آخرین اتفاقات — جدیدترین دوره‌ها و رویدادها\n"
            "  👥 دعوت دوستان — لینک اختصاصی و کسب XP از دعوت\n"
            "  📞 پشتیبانی — ارسال پیام مستقیم به تیم ما\n"
            "  🧠 مسیر شغلی — راهنمای پیشرفت حرفه‌ای شما\n\n"
            "━━━━━━━━━━━━━━━━\n"
            "📈 تفاوت XP و اعتبار:\n\n"
            "  🏅 امتیاز رشد (XP):\n"
            "    — برای تعیین رتبه، سطح و رقابت استفاده می‌شود\n"
            "    — هرگز خرج نمی‌شود و همیشه افزایشی است\n"
            "    — سطح شما را از تازه‌کار به نخبه ارتقا می‌دهد\n\n"
            "  💰 اعتبار:\n"
            "    — ارز داخلی ربات برای خرید از گنجینه\n"
            "    — با خرید آیتم‌های گنجینه خرج می‌شود\n"
            "    — ممکن است برخی دوره‌ها نیاز به اعتبار داشته باشند\n\n"
            "━━━━━━━━━━━━━━━━\n"
            "🎁 روش‌های کسب XP و اعتبار:\n"
            "  📖 مشاهده سرفصل = +۵ XP | +۲ اعتبار\n"
            "  👥 دعوت دوست معتبر = +۱۰ XP | +۵ اعتبار\n"
            "  📊 نظرسنجی دوره = +۴۰ XP | +۱۰ اعتبار\n"
            "  🎯 ماموریت‌های امتیازی = تا +۱۰۰ XP\n\n"
            "━━━━━━━━━━━━━━━━\n"
            "🔒 چرا برخی بخش‌ها قفل هستند؟\n"
            "  برخی دوره‌ها یا امکانات نیاز به شرایط خاصی دارند:\n"
            "  • حداقل XP یا اعتبار\n"
            "  • عضویت در کانال یا گروه خاص\n"
            "  • دعوت تعداد مشخصی دوست\n"
            "  با یادگیری بیشتر همه درها باز می‌شوند! 🚀\n\n"
            "━━━━━━━━━━━━━━━━\n"
            "🏅 مسیر سطوح:\n"
            "  🌱 تازه‌کار (۰ XP) ← شروع\n"
            "  📗 یادگیرنده (۵۰ XP)\n"
            "  📘 کوشا (۱۵۰ XP)\n"
            "  📕 حرفه‌ای (۳۵۰ XP)\n"
            "  🎓 متخصص (۶۰۰ XP)\n"
            "  🏅 استاد (۱۰۰۰ XP)\n"
            "  💎 نخبه (۱۵۰۰ XP) ← هدف نهایی!\n\n"
            "همین الان اولین دوره را شروع کن! 💪"
        )
        await message.reply_text(text2)


# ========================= ثبت شماره تلفن =========================

async def _register_phone(msg, user, ctx, raw_phone: str):
    """اعتبارسنجی و ثبت شماره؛ در صورت موفقیت پیام خوش‌آمد و ادامه فلوی اصلی."""
    ok, result = set_user_phone(user.id, raw_phone)
    if not ok:
        if result == "duplicate":
            await msg.reply_text(
                "❌ این شماره قبلاً توسط کاربر دیگری ثبت شده است.\n"
                "لطفاً شماره موبایل متعلق به خودتان را وارد کنید.",
                reply_markup=phone_kb(),
            )
        else:
            await msg.reply_text(
                "❌ شماره وارد شده معتبر نیست.\n\n"
                "لطفاً یک شماره موبایل صحیح ایران وارد کنید؛ نمونه:\n"
                "  • 09123456789\n"
                "  • +989123456789",
                reply_markup=phone_kb(),
            )
        return

    ctx.user_data.pop("state", None)
    await msg.reply_text(
        "✅ شماره تلفن شما با موفقیت ثبت شد!\n"
        f"📱 شماره ثبت‌شده: {result}\n\n"
        "🎉 خوش آمدید! حالا می‌توانید از تمام امکانات ربات استفاده کنید.",
        reply_markup=reply_kb(user),
    )
    await send_main_welcome(msg, user)


async def _register_phone_secondary(msg, raw_user, ctx, raw_phone: str, platform: str):
    """ثبت شماره روی پلتفرم ثانویه (تلگرام/...) و ادغام بر اساس شماره.
    شماره = ملاک هویت: اگر شماره متعلق به حساب موجود باشد → همان حساب اصلی متصل می‌شود
    (XP/اعتبار/خریدها مشترک)، وگرنه حساب اصلیِ جدید ساخته می‌شود."""
    pname = platform_name(platform)
    norm = normalize_phone(raw_phone)
    if not norm:
        await msg.reply_text(
            "❌ شماره دریافت‌شده معتبر نیست. لطفاً دوباره با دکمهٔ «اشتراک‌گذاری شماره» اقدام کنید.",
            reply_markup=phone_kb(),
        )
        return

    pending = ctx.user_data.get("sec_pending", {}) or {}
    referrer = pending.get("referrer")

    canonical, is_new, status = resolve_platform_identity_by_phone(
        platform, raw_user, norm, referrer_id=referrer
    )

    # تکمیل ماموریت اتصال پلتفرم (یک‌بار، روی حساب اصلی)
    mission = get_platform_link_mission(platform)
    reward_line = ""
    if mission and not has_completed_mission(canonical, mission.get("id", "")):
        ok_m, xp_m, cr_m = complete_mission(canonical, mission.get("id", ""))
        if ok_m and (xp_m or cr_m):
            reward_line = f"\n🎁 پاداش اتصال: +{xp_m} XP | +{cr_m} اعتبار"

    ctx.user_data.pop("state", None)
    ctx.user_data.pop("sec_pending", None)
    ctx.user_data.pop("sec_platform", None)

    user = effective_user(raw_user, platform)
    touch_platform_activity(platform, raw_user.id)

    name = raw_user.first_name or "دوست"
    if status == "merged":
        await msg.reply_text(
            f"✅ خوش آمدید {name} عزیز!\n"
            f"📱 شمارهٔ شما شناسایی شد و حساب شما به {pname} متصل شد.\n"
            f"ℹ️ امتیاز، اعتبار و سوابق حساب شما به‌صورت یکپارچه در دسترس است."
            f"{reward_line}",
            reply_markup=reply_kb(user),
        )
    else:
        await msg.reply_text(
            f"✅ شماره ثبت شد و حساب شما در {pname} فعال شد!\n"
            f"📱 شمارهٔ ثبت‌شده: {norm}"
            f"{reward_line}",
            reply_markup=reply_kb(user),
        )
    await send_main_welcome(msg, user)


async def handle_contact(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    raw_user = update.effective_user
    if not msg or not raw_user or not msg.contact:
        return
    if update.effective_chat and update.effective_chat.type != "private":
        return

    platform = detect_platform(ctx.bot)
    set_current_platform(platform)

    contact = msg.contact
    # شماره باید متعلق به خود فرستنده باشد (نه مخاطب دیگری) — امنیت ادغام
    if contact.user_id and contact.user_id != raw_user.id:
        await msg.reply_text(
            "❌ لطفاً فقط شماره تماس «خودتان» را اشتراک بگذارید، نه شماره شخص دیگری.\n"
            "این شماره ملاک فعال‌سازی حساب شماست.",
            reply_markup=phone_kb(),
        )
        return

    # پلتفرم ثانویه → ادغام/ساخت حساب بر اساس شماره
    if platform != "bale":
        await _register_phone_secondary(msg, raw_user, ctx, contact.phone_number or "", platform)
        return

    # بله — مسیر استاندارد
    register_user(raw_user)
    await _register_phone(msg, raw_user, ctx, contact.phone_number or "")


def _admin_delete_summary(result: dict) -> str:
    if not result.get("ok"):
        if result.get("protected"):
            return "🛡 این کاربر ادمین اصلی است و قابل حذف نیست."
        return f"❌ حذف انجام نشد: {result.get('error', 'خطای نامشخص')}"
    counts = result.get("affected_counts") or {}
    total = result.get("total_affected") or sum(int(v or 0) for v in counts.values())
    if "deleted_count" in result:
        return (
            f"✅ همه کاربران غیرمحافظت‌شده حذف شدند.\n"
            f"تعداد کاربران حذف‌شده: {fa_num(result.get('deleted_count', 0))}\n"
            f"ادمین‌های اصلی محافظت‌شده: {fa_num(result.get('skipped_protected_count', 0))}\n"
            f"ردیف‌های تحت تاثیر: {fa_num(total)}"
        )
    u = result.get("user") or {}
    return f"✅ کاربر حذف شد.\nشناسه: {u.get('user_id', '—')}\nشماره: {u.get('phone') or '—'}\nردیف‌های تحت تاثیر: {fa_num(total)}"


def _site_maint_text() -> str:
    web_on = admin_get_maintenance_flag('site')
    giso_on = admin_get_maintenance_flag('giso')
    return (
        "🔒 غیرفعالی سایت\n\n"
        f"وضعیت سایت: {'غیرفعال' if web_on else 'فعال'}\n"
        f"وضعیت گیسو: {'غیرفعال' if giso_on else 'فعال'}\n\n"
        "تغییرات بلافاصله و بدون restart اعمال می‌شوند."
    )


def _site_maint_kb():
    return mkb([
        [btn("🌐 غیرفعال کردن سایت", "site_maint_off_web"), btn("🌐 فعال کردن سایت", "site_maint_on_web")],
        [btn("💇 غیرفعال کردن گیسو", "site_maint_off_giso"), btn("💇 فعال کردن گیسو", "site_maint_on_giso")],
        [btn("🔙 بازگشت", "a_web_manage")],
    ])


def _maint_base_url(scope: str) -> str:
    """منبع آدرس پایهٔ لینک موقت: اول تنظیم «🌐 آدرس سایت» در giso.db (منبع اصلی
    مشترک با ربات/پنل گیسو)، بعد نسخهٔ قدیمی bot.db، بعد env، بعد پیش‌فرض."""
    key = "site_base_url" if scope == "giso" else "main_site_base_url"
    base = ""
    try:
        from giso_admin import get_giso_site_config, get_giso_config
        base = str(get_giso_site_config(key, "") or "").strip()
        if not base:
            base = str(get_giso_config(key, "") or "").strip()
    except Exception:
        base = ""
    if not base and scope == "main":
        base = str(os.getenv("MAIN_SITE_URL") or "").strip()
    if not base:
        base = "https://giso.sadeghiai.ir" if scope == "giso" else "https://sadeghiai.ir"
    return base.rstrip("/")


def _site_main_maint_kb():
    rows=[[btn("🚧 فعال‌کردن به‌روزرسانی","site_maint_off_web"),btn("✅ پایان به‌روزرسانی","site_maint_on_web")],[btn("🖼 بارگذاری تصویر به‌روزرسانی","site_main_image_upload"),btn("♻️ تصویر پیش‌فرض","site_main_image_reset")]]
    if admin_get_maintenance_flag('site'): rows.append([btn("🔐 ساخت لینک ۱۰ دقیقه‌ای","site_temp_link_main"),btn("🗑 ابطال لینک","site_temp_revoke_main")])
    rows.append([btn("🌐 آدرس سایت","site_base_url_main")])
    rows.append([btn("🔙 بازگشت","a_web_main_manage")]);return mkb(rows)


def _site_giso_maint_kb():
    rows=[[btn("🚧 فعال‌کردن به‌روزرسانی","site_maint_off_giso"),btn("✅ پایان به‌روزرسانی","site_maint_on_giso")],[btn("🖼 بارگذاری تصویر به‌روزرسانی","site_giso_image_upload"),btn("♻️ تصویر پیش‌فرض","site_giso_image_reset")]]
    if admin_get_maintenance_flag('giso'): rows.append([btn("🔐 ساخت لینک ۱۰ دقیقه‌ای","site_temp_link_giso"),btn("🗑 ابطال لینک","site_temp_revoke_giso")])
    rows.append([btn("🌐 آدرس سایت","site_base_url_giso")])
    rows.append([btn("🔙 بازگشت","a_web_giso_manage")]);return mkb(rows)

def _site_main_backup_kb():
    return mkb([
        [btn("💾 تهیه پشتیبان bot.db", "site_backup_bot")],
        [btn("📥 بازگردانی bot.db", "site_restore_bot")],
        [btn("⏱ پشتیبان خودکار هر دو سامانه", "site_backup_schedule")],
        [btn("📋 فهرست پشتیبان‌ها", "site_backup_list_bot")],
        [btn("🔙 بازگشت", "a_web_main_manage")],
    ])


def _site_giso_backup_kb():
    return mkb([
        [btn("💾 تهیه پشتیبان giso.db", "site_backup_giso")],
        [btn("📥 بازگردانی giso.db", "site_restore_giso")],
        [btn("📋 فهرست پشتیبان‌ها", "site_backup_list_giso")],
        [btn("🔙 بازگشت", "a_web_giso_manage")],
    ])


def _project_root():
    from pathlib import Path
    return Path(__file__).resolve().parent.parent


def _maintenance_image_path(scope: str):
    root = _project_root()
    return (root / ("web" if scope == "main" else "giso") / "static" / "images" / "maintenance_custom.webp").resolve()


def _reset_maintenance_image(scope: str):
    path = _maintenance_image_path(scope)
    try:
        if path.is_file() and not path.is_symlink():
            path.unlink()
        admin_set_setting_value(f"{'site' if scope=='main' else 'giso'}_maintenance_image_version",str(int(time.time())))
        return True
    except Exception:
        return False


def _giso_ai_report_text():
    root = _project_root(); db_path = root / "giso" / "data" / "giso.db"
    if not db_path.exists():
        return "🧠 گزارش هوش مصنوعی گیسو\n\n🔴 دیتابیس گیسو در دسترس نیست."
    try:
        with sqlite3.connect(str(db_path)) as c:
            c.row_factory = sqlite3.Row
            providers = c.execute("SELECT name,enabled,last_status,selected_model,last_checked_at FROM giso_ai_providers ORDER BY id").fetchall()
            settings = {r[0]: r[1] for r in c.execute("SELECT key,value FROM giso_ai_settings").fetchall()} if c.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='giso_ai_settings'").fetchone() else {}
            usage = c.execute("SELECT COUNT(*) FROM giso_ai_usage_stats WHERE created_at>=date('now','localtime')").fetchone()[0] if c.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='giso_ai_usage_stats'").fetchone() else 0
        active=[p for p in providers if p['enabled']]; healthy=[p for p in active if str(p['last_status'] or '').lower().startswith('ok')]
        primary=settings.get('active_provider') or (active[0]['name'] if active else 'تنظیم نشده')
        model=next((p['selected_model'] for p in active if p['name']==primary), '') or 'تنظیم نشده'
        return ("🧠 <b>گزارش هوش مصنوعی گیسو</b>\n━━━━━━━━━━━━━━━━\n"
                f"وضعیت کلی: {'🟢 سالم' if healthy else '🔴 نیازمند بررسی'}\n"
                f"ارائه‌دهنده اصلی: {html.escape(str(primary))}\nمدل فعال: {html.escape(str(model))}\n"
                f"ارائه‌دهندگان فعال: {fa_num(len(active))}\nارائه‌دهندگان سالم: {fa_num(len(healthy))}\n"
                f"مصرف امروز: {fa_num(usage)} درخواست\n\nاین گزارش فقط خواندنی است.")
    except Exception as e:
        logger.warning("giso ai report: %s", e)
        return "🧠 گزارش هوش مصنوعی گیسو\n\n🔴 دریافت گزارش ممکن نشد."


def _giso_health_text():
    from pathlib import Path
    root=_project_root(); db_path=root/"giso"/"data"/"giso.db"; pid_path=root/"giso"/"data"/"giso-bot.pid"
    site_code='نامشخص';site_ms=0
    try:
        from giso_admin import get_giso_config, get_giso_site_config
        from urllib.request import Request,urlopen
        site_url=(get_giso_site_config('site_base_url','') or get_giso_config('site_base_url','')
                  or 'https://gisosadeghi.ir')
        started=time.monotonic()
        try:
            response=urlopen(Request(site_url,headers={'User-Agent':'GisoHealth/1.0'}),timeout=5);site_code=str(response.status);response.close()
        except Exception as e:
            site_code=str(getattr(e,'code','خطا'))
        site_ms=int((time.monotonic()-started)*1000)
    except Exception: pass
    db_ok=False; db_size=0; quick='اجرا نشد'; counts={}
    try:
        db_size=db_path.stat().st_size
        with sqlite3.connect(str(db_path),timeout=5) as c:
            quick=str(c.execute("PRAGMA quick_check").fetchone()[0]);db_ok=quick.lower()=='ok'
            for key,sql in {"hair":"SELECT COUNT(*) FROM hair_orders WHERE status IN ('pending','reviewing')","market":"SELECT COUNT(*) FROM hair_listings WHERE status='pending_review'","shop":"SELECT COUNT(*) FROM product_orders WHERE status='pending'","centers":"SELECT COUNT(*) FROM beauty_centers WHERE status IN ('pending_review','reviewing')"}.items():
                try: counts[key]=c.execute(sql).fetchone()[0]
                except Exception: counts[key]=0
    except Exception: pass
    pid='—'; running=False
    try:
        pid=int(pid_path.read_text().strip())
        if os.name=='nt': running=str(pid) in os.popen(f'tasklist /FI "PID eq {pid}"').read()
        else: os.kill(pid,0);running=True
    except Exception: running=False
    backups=[]
    for folder in (root/"giso"/"data"/"backup",root/"bot_edu"/"data"/"backup"):
        if folder.exists(): backups += list(folder.glob("giso_*.db"))
    latest=max(backups,key=lambda p:p.stat().st_mtime).name if backups else 'ثبت نشده'
    disk=shutil.disk_usage(str(root)).free//(1024*1024)
    return ("📊 <b>گزارش کلی سلامت گیسو</b>\n━━━━━━━━━━━━━━━━\n"
            f"🌐 سایت: پاسخ {site_code} در {fa_num(site_ms)} میلی‌ثانیه\n"
            f"حالت به‌روزرسانی: {'روشن' if admin_get_maintenance_flag('giso') else 'خاموش'}\n"
            f"🤖 ربات: {'🟢 فعال' if running else '🔴 متوقف'} | PID: {pid}\n"
            f"🗄 دیتابیس: {'🟢 سالم' if db_ok else '🔴 نیازمند بررسی'} | {fa_num(db_size//1024)} کیلوبایت\n"
            f"بررسی سریع: {'سالم' if str(quick).lower()=='ok' else html.escape(quick)}\n💾 آخرین پشتیبان: {html.escape(latest)}\n"
            f"💽 فضای آزاد: {fa_num(disk)} مگابایت\n\n"
            f"💇 خرید مو: {fa_num(counts.get('hair',0))} | 🏪 بازارچه: {fa_num(counts.get('market',0))}\n"
            f"🛍 سفارش: {fa_num(counts.get('shop',0))} | 🏥 مراکز: {fa_num(counts.get('centers',0))}")


def _safe_giso_cleanup_candidates():
    from pathlib import Path
    root=_project_root().resolve(); now=time.time(); files=[]
    allowed=[root/"giso"/"static"/"uploads"/"temp",root/"giso"/"data"/"temp"]
    for folder in allowed:
        if not folder.exists(): continue
        safe_root=folder.resolve()
        for p in folder.rglob('*'):
            try:
                rp=p.resolve()
                if p.is_symlink() or not p.is_file() or safe_root not in rp.parents: continue
                if now-p.stat().st_mtime>=86400: files.append(p)
            except Exception: continue
    # پشتیبان‌های اضافهٔ گیسو؛ پنج نسخه آخر هر prefix حفظ می‌شوند.
    for folder in (root/"giso"/"data"/"backup",root/"bot_edu"/"data"/"backup"):
        if not folder.exists(): continue
        groups={}
        for p in folder.glob('giso_*.db'):
            prefix='_'.join(p.name.split('_')[:2]);groups.setdefault(prefix,[]).append(p)
        for group in groups.values():
            group.sort(key=lambda p:p.stat().st_mtime,reverse=True);files.extend(group[5:])
    unique=[];seen=set()
    for p in files:
        try:
            rp=str(p.resolve())
            if rp not in seen:seen.add(rp);unique.append(p)
        except Exception: pass
    return unique


async def _handle_maintenance_image_upload(msg, ctx, scope: str):
    if not msg.photo and not (msg.document and (msg.document.mime_type or '').lower().startswith('image/')):
        await msg.reply_text("❌ یک تصویر JPG، PNG یا WebP ارسال کنید.")
        return False
    file_size = int((msg.document.file_size if msg.document else msg.photo[-1].file_size) or 0)
    if file_size > 5*1024*1024:
        await msg.reply_text("❌ حجم تصویر بیشتر از ۵ مگابایت است.")
        return False
    from pathlib import Path
    import tempfile
    file_id = msg.document.file_id if msg.document else msg.photo[-1].file_id
    tmp=Path(tempfile.gettempdir())/f"maintenance_{scope}_{int(time.time())}.img"
    try:
        tg=await ctx.bot.get_file(file_id);await tg.download_to_drive(custom_path=str(tmp))
        from PIL import Image
        with Image.open(tmp) as im:
            im.verify()
        with Image.open(tmp) as im:
            if im.width*im.height>20_000_000: raise ValueError("ابعاد تصویر بیش از حد مجاز است")
            im=im.convert('RGB');im.thumbnail((1600,1000),Image.Resampling.LANCZOS)
            dest=_maintenance_image_path(scope);dest.parent.mkdir(parents=True,exist_ok=True)
            staged=dest.with_suffix('.tmp.webp');im.save(staged,'WEBP',quality=88,method=6);os.replace(staged,dest)
        admin_set_setting_value(f"{'site' if scope=='main' else 'giso'}_maintenance_image_version",str(int(time.time())))
        ctx.user_data.pop('state',None)
        await msg.reply_text("✅ تصویر صفحه به‌روزرسانی ذخیره شد.",reply_markup=web_main_manage_kb() if scope=='main' else web_giso_manage_kb())
        return True
    except Exception as e:
        logger.warning("maintenance image upload failed: %s",e);await msg.reply_text("❌ تصویر معتبر نیست یا ذخیره نشد.");return False
    finally:
        try: tmp.unlink(missing_ok=True)
        except Exception: pass


def _site_backup_kb():
    """
    کیبورد کامل پشتیبان‌گیری و بازگردانی (دو دیتابیس) — نگهداری‌شده برای سازگاری.
    در UI زنده، این منو به زیرمنوی «💾 پشتیبان‌گیری» منتقل شده است.
    """
    return mkb([
        [btn("📦 دیتابیس سایت اصلی (bot.db)", "noop_header")],
        [
            btn("💾 backup", "site_backup_bot"),
            btn("📥 بازگردانی", "site_restore_bot"),
        ],
        [btn("📦 دیتابیس گیسو (giso.db)", "noop_header")],
        [
            btn("💾 backup", "site_backup_giso"),
            btn("📥 بازگردانی", "site_restore_giso"),
        ],
        [btn("💾 پشتیبان از هر دو", "site_backup_all")],
        [btn("⏱ تنظیم backup خودکار", "site_backup_schedule")],
        [btn("📋 لیست بکاپ‌های موجود", "site_backup_list")],
        [btn("🔙 بازگشت", "a_web_manage")],
    ])


def _edubot_backup_main_kb():
    """منوی اصلی «پشتیبان‌گیری» — ساده و تمیز (بخش A-1)."""
    return mkb([
        [btn("💾 پشتیبان‌گیری", "site_backup_sub")],
        [btn("📥 بازگردانی", "site_restore_menu")],
        [btn("⏱ تنظیم پشتیبان‌گیری خودکار", "site_backup_schedule")],
        [btn("🔙 بازگشت", "a_web_manage")],
    ])


def _edubot_backup_sub_kb():
    """زیرمنوی «💾 پشتیبان‌گیری» — bot / giso / هر دو / لیست (بخش A-2)."""
    return mkb([
        [btn("💾 پشتیبان‌گیری از bot.db", "site_backup_bot")],
        [btn("💾 پشتیبان‌گیری از giso.db", "site_backup_giso")],
        [btn("💾 پشتیبان‌گیری از هر دو", "site_backup_all")],
        [btn("📋 لیست بکاپ‌های موجود", "site_backup_list")],
        [btn("🔙 بازگشت", "site_backup_menu")],
    ])


def _edubot_restart_prompt_kb():
    """پیشنهاد ریستارت بعد از restore موفق (بخش B-3)."""
    return mkb([
        [btn("✅ بله، ریستارت کن", "edubot_restart_yes")],
        [btn("❌ نه، بعداً", "edubot_restart_later")],
    ])


def _site_restore_method_kb(kind: str):
    """منوی روش بازگردانی (دستی / انتخاب از لیست) برای یک دیتابیس."""
    return mkb([
        [btn("📤 ارسال فایل دستی", f"site_restore_{kind}_manual")],
        [btn("📋 انتخاب از لیست بکاپ‌ها", f"site_restore_{kind}_list")],
        [btn("🔙 بازگشت", "site_main_backup_menu" if kind == "bot" else "site_giso_backup_menu")],
    ])


def _backup_db_paths(kind: str):
    from pathlib import Path
    root = Path(__file__).resolve().parent.parent
    if kind == 'bot':
        return Path(DB_PATH).resolve(), 'bot_db_backup'
    if kind == 'giso':
        return (root / 'giso' / 'data' / 'giso.db').resolve(), 'giso_db_backup'
    raise ValueError('unknown backup kind')


def _make_db_backup(src_path, prefix: str):
    from pathlib import Path
    import tempfile
    from datetime import datetime
    import shutil
    ts = datetime.now().strftime('%Y%m%d_%H%M%S')
    src = Path(src_path)
    if not src.exists():
        raise FileNotFoundError(str(src))
    dst = Path(tempfile.gettempdir()) / f"{prefix}_{ts}.db"
    try:
        src_conn = sqlite3.connect(f"file:{src}?mode=ro", uri=True)
        dst_conn = sqlite3.connect(str(dst))
        try:
            src_conn.backup(dst_conn)
        finally:
            dst_conn.close()
            src_conn.close()
    except Exception:
        shutil.copy2(str(src), str(dst))
    return dst


async def _send_db_backup(q, kind: str, total: int = None, index: int = None):
    """بکاپ دستی که در همان پوشه data/backup ذخیره می‌شود (یکسان با بکاپ خودکار).

    پیام‌های زنده و مرحله‌ای (بدون نمایش مسیر فایل) + ارسال document با
    timeout بزرگ (رفع باگ Timed out برای فایل‌های چند مگابایتی).
    خروجی: (success: bool, message: str)
    """
    from datetime import datetime
    src, _prefix = _backup_db_paths(kind)
    backup_dir = _edubot_backup_dir()
    os.makedirs(backup_dir, exist_ok=True)
    label = "bot.db" if kind == 'bot' else "giso.db"
    step = f"[{index}/{total}] " if (index and total) else ""
    try:
        logger.info("database backup requested: %s", kind)

        async def _edit(t):
            try:
                await q.edit_message_text(t)
            except Exception:
                pass

        # مرحله ۱: آماده‌سازی
        await _edit(f"⏳ {step}در حال آماده‌سازی پشتیبان {label}...")
        # ═══ checkpoint قبل از backup (انتقال WAL به DB) ═══
        try:
            from db import checkpoint_db
            checkpoint_db(src)
        except Exception as _ce:
            logger.warning(f"checkpoint قبل از backup ({kind}) ناموفق: {_ce}")
        await _edit(f"⏳ {step}در حال ذخیره اطلاعات موقت...")

        manual_prefix = 'bot' if kind == 'bot' else 'giso'
        ts = datetime.now().strftime('%Y%m%d_%H%M%S')
        fname = f"{manual_prefix}_manual_{ts}.db"
        dst = os.path.join(backup_dir, fname)

        # مرحله ۲: ساخت فایل پشتیبان
        await _edit(f"⏳ {step}در حال ساخت فایل پشتیبان...")
        if kind == 'bot':
            # بکاپ bot.db با SQLite Backup API (سازگار با WAL و چند connection)
            from db import backup_bot_db_safe
            ok, _msg = backup_bot_db_safe(dst)
            if not ok:
                return False, f"❌ خطا در تهیه پشتیبان: {_msg}"
        else:
            # گیسو: copy فایل (گیسو تک‌connection است و checkpoint کافی است)
            shutil.copy2(str(src), dst)

        # حذف بکاپ‌های قدیمی (نگهداری ۵ آخر برای این نوع)
        _edubot_cleanup_old_backups(manual_prefix, 5)

        # مرحله ۳: ارسال document (با timeout بزرگ)
        await _edit(f"⏳ {step}در حال ارسال فایل...")
        size_kb = max(1, os.path.getsize(dst) // 1024)
        with open(dst, 'rb') as fh:
            await q.message.reply_document(
                document=fh,
                filename=fname,
                caption=f"💾 پشتیبان دیتابیس آماده شد: {fname}",
                read_timeout=120,
                write_timeout=120,
                connect_timeout=60,
            )
        admin_set_setting_value('last_backup_at', time.strftime('%Y-%m-%d %H:%M:%S'))
        # پایان: پیام موفقیت (بدون مسیر)
        await _edit(
            f"✅ {step}پشتیبان {label} با موفقیت آماده شد\n"
            f"📊 حجم: {size_kb} KB\n"
            f"🕐 زمان: {time.strftime('%H:%M:%S')}"
        )
        return True, f"✅ پشتیبان {label} آماده شد"
    except FileNotFoundError:
        return False, f"❌ فایل دیتابیس پیدا نشد: {label}"
    except Exception as e:
        return False, f"❌ خطا در تهیه پشتیبان: {e}"


# ═══════════════════════════════════════════════════════════
# ریستارت ربات آموزشی (os.execv — همان PID، main.py بدون تغییر)
# ═══════════════════════════════════════════════════════════
def _restart_edubot_process():
    """ریستارت کامل ربات آموزشی با os.execv.

    مسیر اجرا باید به bot.py باشد (نه handlers.py)، چون __file__ به
    handlers.py اشاره می‌کند و اجرای مستقیم آن صحیح نیست.
    """
    import sys as _sys
    import os as _os
    try:
        from db import checkpoint_db, DB_PATH as _EDU_DB_PATH
        checkpoint_db(_EDU_DB_PATH)
    except Exception:
        pass
    try:
        bot_py_path = _os.path.abspath(
            _os.path.join(_os.path.dirname(__file__), "bot.py")
        )
        _os.execv(_sys.executable, [_sys.executable, "-u", bot_py_path])
    except Exception as e:
        logger.error(f"_restart_edubot_process error: {e}")


def _edubot_restart_kb():
    return mkb([
        [
            InlineKeyboardButton("⏱ ۵ ثانیه", callback_data="edubot_restart_confirm_5"),
            InlineKeyboardButton("⏱ ۱۰ ثانیه", callback_data="edubot_restart_confirm_10"),
        ],
        [
            InlineKeyboardButton("⏱ ۳۰ ثانیه", callback_data="edubot_restart_confirm_30"),
            InlineKeyboardButton("⏱ ۶۰ ثانیه", callback_data="edubot_restart_confirm_60"),
        ],
        [InlineKeyboardButton("❌ لغو", callback_data="edubot_restart_cancel")],
    ])


async def _notify_edubot_active_users(context, seconds):
    """پیام به کاربران فعال (۱ ساعت اخیر) درباره ریستارت."""
    try:
        from db import get_conn
        from datetime import datetime, timedelta
        since = int(time.time()) - 3600
        conn = get_conn()
        rows = conn.execute(
            "SELECT DISTINCT user_id FROM users WHERE last_active >= ? AND user_id != ''",
            (since,)
        ).fetchall()
        msg = f"⚠️ ربات تا {seconds} ثانیه دیگر ریستارت خواهد شد.\nلطفاً چند لحظه صبر کنید..."
        for r in rows:
            uid = str(r["user_id"] or "")
            if not uid.isdigit():
                continue
            try:
                await context.bot.send_message(chat_id=int(uid), text=msg)
            except Exception:
                continue
    except Exception as e:
        logger.debug(f"_notify_edubot_active_users: {e}")


async def _edubot_restart_flow(query, ctx, seconds):
    """شمارش معکوس و ریستارت ربات آموزشی."""
    try:
        await _notify_edubot_active_users(ctx, seconds)
    except Exception:
        pass
    try:
        await query.edit_message_text(
            f"⚠️ ریستارت ربات آموزشی تا {seconds} ثانیه دیگر...",
            reply_markup=mkb([[InlineKeyboardButton("❌ لغو", callback_data="edubot_restart_cancel")]]),
        )
    except Exception:
        pass
    remaining = seconds
    while remaining > 0:
        await asyncio.sleep(min(2, remaining))
        remaining = max(0, remaining - 2)
        try:
            await query.edit_message_text(
                f"⚠️ ریستارت ربات آموزشی تا {remaining} ثانیه دیگر...",
                reply_markup=mkb([[InlineKeyboardButton("❌ لغو", callback_data="edubot_restart_cancel")]]),
            )
        except Exception:
            break
    try:
        await query.edit_message_text("✅ ربات آموزشی در حال ریستارت است...")
    except Exception:
        pass
    _restart_edubot_process()


# ═══════════════════════════════════════════════════════════
# backup خودکار زمان‌بندی شده (edu bot)
# ═══════════════════════════════════════════════════════════
_edubot_backup_job = None


def _edubot_backup_dir():
    return os.path.join(os.path.dirname(__file__), "data", "backup")


def _edubot_list_backup_files(db_type='bot'):
    """
    لیست فایل‌های بکاپ بر اساس نوع دیتابیس.
    db_type: 'bot' یا 'giso'
    خروجی: لیست dict شامل {name, path, size, mtime} مرتب‌شده از جدیدترین به قدیمی‌ترین.
    """
    backup_dir = _edubot_backup_dir()
    prefix = 'bot' if db_type == 'bot' else 'giso'
    out = []
    try:
        os.makedirs(backup_dir, exist_ok=True)
        for f in os.listdir(backup_dir):
            if f.startswith(prefix) and f.endswith('.db'):
                p = os.path.join(backup_dir, f)
                try:
                    size = os.path.getsize(p)
                    mtime = os.path.getmtime(p)
                except Exception:
                    size, mtime = 0, 0
                out.append({'name': f, 'path': p, 'size': size, 'mtime': mtime})
        out.sort(key=lambda x: x['mtime'], reverse=True)
    except Exception:
        pass
    return out


def _edubot_cleanup_old_backups(db_type='bot', max_files=5):
    """حذف بکاپ‌های قدیمی (نگهداری فقط max_files فایل آخر برای هر نوع)."""
    prefix = 'bot' if db_type == 'bot' else 'giso'
    backup_dir = _edubot_backup_dir()
    try:
        files = sorted(
            [f for f in os.listdir(backup_dir)
             if f.startswith(prefix) and f.endswith('.db')]
        )
        while len(files) > max_files:
            os.remove(os.path.join(backup_dir, files.pop(0)))
    except Exception:
        pass


def _edubot_restore_from_path(source_path, target_db='bot'):
    """
    بازگردانی از مسیر مشخص با safety + integrity + rollback.
    برای bot.db از SQLite Backup API (restore_bot_db_safe) استفاده می‌کند.
    خروجی: (success: bool, message: str)
    """
    try:
        if target_db == 'bot':
            from db import restore_bot_db_safe
            ok, msg = restore_bot_db_safe(source_path)
            return ok, msg
        safety_name = _safe_restore_db(target_db, source_path)
        return True, f"فایل جایگزین شد. نسخه امن قبلی: {safety_name}"
    except Exception as e:
        return False, f"بازگردانی ناموفق بود و rollback انجام شد: {e}"


def _edubot_giso_db_path():
    from pathlib import Path
    root = Path(__file__).resolve().parent.parent
    return (root / "giso" / "data" / "giso.db").resolve()


async def _auto_edubot_backup(context):
    """اجرای خودکار backup هر دو DB (checkpoint + Backup API + prune)."""
    import shutil
    from datetime import datetime
    try:
        from db import checkpoint_db, backup_bot_db_safe
    except Exception:
        checkpoint_db, backup_bot_db_safe = None, None

    logger.info("شروع backup خودکار edu bot...")
    try:
        backup_dir = _edubot_backup_dir()
        os.makedirs(backup_dir, exist_ok=True)
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')

        # ═══ bot.db با SQLite Backup API (سازگار با WAL و چند connection) ═══
        bot_backup = os.path.join(backup_dir, f"bot_auto_{timestamp}.db")
        if backup_bot_db_safe:
            ok, _bmsg = backup_bot_db_safe(bot_backup)
            if not ok:
                logger.error(f"backup خودکار bot.db ناموفق: {_bmsg}")
        else:
            # fallback به روش قدیمی
            if checkpoint_db:
                checkpoint_db(DB_PATH)
            shutil.copy2(str(DB_PATH), bot_backup)

        # ═══ giso.db ═══
        giso_db = _edubot_giso_db_path()
        if os.path.exists(giso_db):
            if checkpoint_db:
                checkpoint_db(giso_db)
            giso_backup = os.path.join(backup_dir, f"giso_auto_{timestamp}.db")
            shutil.copy2(str(giso_db), giso_backup)

        # ═══ حذف قدیمی (نگه داشتن ۵ آخر برای هر prefix) ═══
        for prefix in ("bot_auto_", "giso_auto_"):
            files = sorted(
                [f for f in os.listdir(backup_dir)
                 if f.startswith(prefix) and f.endswith(".db")]
            )
            while len(files) > 5:
                old = files.pop(0)
                os.remove(os.path.join(backup_dir, old))

        # ═══ ذخیره زمان ═══
        try:
            admin_set_setting_value("last_backup_at", timestamp)
        except Exception:
            pass

        logger.info(f"backup خودکار موفق: {timestamp}")
    except Exception as e:
        logger.error(f"backup خودکار edu bot خطا: {e}")


def _start_edubot_backup_timer(context, hours):
    """شروع timer backup خودکار."""
    global _edubot_backup_job
    _stop_edubot_backup_timer(context)
    if hours <= 0:
        return
    try:
        if context is None or not hasattr(context, "job_queue") or context.job_queue is None:
            logger.debug("job_queue در دسترس نیست؛ backup زمان‌بندی نشد")
            return
        _edubot_backup_job = context.job_queue.run_repeating(
            _auto_edubot_backup,
            interval=hours * 3600,
            first=hours * 3600,
            name='edubot_auto_backup',
        )
        logger.info(f"backup خودکار edu bot تنظیم شد: هر {hours} ساعت")
    except Exception as e:
        logger.error(f"_start_edubot_backup_timer: {e}")


def _stop_edubot_backup_timer(context):
    """توقف timer backup خودکار."""
    global _edubot_backup_job
    if _edubot_backup_job is not None:
        try:
            _edubot_backup_job.schedule_removal()
        except Exception:
            pass
        _edubot_backup_job = None
    try:
        if context is not None and hasattr(context, "job_queue") and context.job_queue is not None:
            for job in context.job_queue.get_jobs_by_name('edubot_auto_backup'):
                try:
                    job.schedule_removal()
                except Exception:
                    pass
    except Exception as e:
        logger.debug(f"_stop_edubot_backup_timer: {e}")


def _init_edubot_auto_backup(app):
    """شروع backup خودکار هنگام startup."""
    try:
        try:
            interval = int(SETTINGS.get("backup_interval_hours", "0") or "0")
        except (TypeError, ValueError):
            interval = 0
        if interval > 0 and app is not None and hasattr(app, "job_queue") and app.job_queue is not None:
            app.job_queue.run_repeating(
                _auto_edubot_backup,
                interval=interval * 3600,
                first=interval * 3600,
                name='edubot_auto_backup',
            )
            logger.info(f"backup خودکار edu bot شروع شد: هر {interval} ساعت")
    except Exception as e:
        logger.warning(f"_init_edubot_auto_backup: {e}")


def _fmt_ts(ts) -> str:
    try:
        return time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(int(ts)))
    except Exception:
        return str(ts or '—')


def _site_health_text() -> str:
    r = admin_get_site_health_report()
    if not r.get('ok'):
        return f"📊 <b>گزارش سلامت سایت</b>\n\n❌ خطا: <code>{html.escape(str(r.get('error')))}</code>"
    maint_site = 'غیرفعال' if r.get('site_maintenance') else 'فعال'
    maint_giso = 'غیرفعال' if r.get('giso_maintenance') else 'فعال'
    ts = _fmt_ts(r.get('generated_at'))
    return (
        "📊 <b>گزارش سلامت سایت</b>\n\n"
        "👥 <b>کاربران</b>\n"
        f"- کل کاربران: <b>{fa_num(r.get('users_total', 0))}</b>\n"
        f"- ثبت‌نام امروز: <b>{fa_num(r.get('users_today', 0))}</b>\n\n"
        "💬 <b>درخواست‌های مشاور</b>\n"
        f"- کل: <b>{fa_num(r.get('consultant_total', 0))}</b>\n"
        f"- در انتظار: <b>{fa_num(r.get('consultant_pending', 0))}</b>\n"
        f"- فعال: <b>{fa_num(r.get('consultant_active', 0))}</b>\n\n"
        "🔒 <b>Maintenance</b>\n"
        f"- سایت: <b>{maint_site}</b>\n"
        f"- گیسو: <b>{maint_giso}</b>\n\n"
        "💾 <b>آخرین بک‌آپ</b>\n"
        f"- {html.escape(str(r.get('last_backup_at') or 'ثبت نشده'))}\n\n"
        f"⏱ به‌روزرسانی: <code>{html.escape(ts)}</code>"
    )


def _main_site_health_text() -> str:
    r=admin_get_site_health_report()
    if not r.get('ok'): return "📊 گزارش سلامت سایت اصلی\n\n🔴 دریافت گزارش ممکن نشد."
    return ("📊 <b>گزارش سلامت سایت اصلی</b>\n━━━━━━━━━━━━━━━━\n"
            f"وضعیت سایت: {'🚧 در حال به‌روزرسانی' if r.get('site_maintenance') else '🟢 فعال'}\n"
            f"کاربران: {fa_num(r.get('users_total',0))}\nثبت‌نام امروز: {fa_num(r.get('users_today',0))}\n"
            f"درخواست مشاور: {fa_num(r.get('consultant_pending',0))} در انتظار\n"
            f"آخرین پشتیبان: {html.escape(str(r.get('last_backup_at') or 'ثبت نشده'))}\n"
            f"زمان گزارش: {_fmt_ts(r.get('generated_at'))}")


def _site_restore_kb():
    """زیرمنوی «📥 بازگردانی» — bot / giso / بازگشت (بخش A-3)."""
    return mkb([
        [btn("📥 بازگردانی bot.db", "site_restore_bot")],
        [btn("📥 بازگردانی giso.db", "site_restore_giso")],
        [btn("🔙 بازگشت", "site_backup_menu")],
    ])


def _site_cleanup_kb():
    return mkb([
        [btn("🧹 پاک کردن sessionهای قدیمی", "site_clean_sessions")],
        [btn("🧹 پاک کردن کش", "site_clean_cache")],
        [btn("🧹 پاک کردن درخواست‌های ناتمام", "site_clean_incomplete")],
        [btn("🔙 بازگشت", "a_web_manage")],
    ])


def _restore_target(kind: str):
    src, _prefix = _backup_db_paths(kind)
    prefix = 'bot_db_prerestore' if kind == 'bot' else 'giso_db_prerestore'
    return src, prefix


def _safe_restore_db(kind: str, uploaded_path):
    from pathlib import Path
    import shutil
    from datetime import datetime
    src_target, prefix = _restore_target(kind)
    if not str(uploaded_path).lower().endswith('.db'):
        raise ValueError('فقط فایل .db قابل قبول است.')
    if Path(uploaded_path).stat().st_size > 250 * 1024 * 1024:
        raise ValueError('حجم فایل بیشتر از حد مجاز است.')
    try:
        test_conn = sqlite3.connect(str(uploaded_path))
        try:
            row = test_conn.execute('PRAGMA integrity_check').fetchone()
            if not row or str(row[0]).lower() != 'ok':
                raise ValueError('فایل دیتابیس معتبر نیست.')
        finally:
            test_conn.close()
    except Exception as e:
        raise ValueError(f'فایل دیتابیس قابل خواندن نیست: {e}')
    src_target.parent.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime('%Y%m%d_%H%M%S')
    safety = src_target.with_name(f"{prefix}_{ts}.db")
    if src_target.exists():
        shutil.copy2(str(src_target), str(safety))
    try:
        logger.info("database restore requested: %s -> %s", kind, src_target)
        shutil.copy2(str(uploaded_path), str(src_target))
        if kind == 'bot':
            try:
                import config as _cfg
                if hasattr(_cfg, 'reload_all_from_db'):
                    _cfg.reload_all_from_db()
                else:
                    # fallback قدیمی
                    for obj_name in ('COURSES', 'PROGRESS', 'USERS', 'SETTINGS', 'SHOP', 'SURVEYS', 'FEATURE_ACCESS', 'CASH_SALE_SETTINGS', 'USER_FEATURE_RESTRICTIONS', 'PLATFORM_LINKS', 'LINK_CODES', 'ADMIN_LINK_CODES', 'PLATFORM_ADMINS', 'BOT_GROUPS'):
                        obj = getattr(_cfg, obj_name, None)
                        if hasattr(obj, 'clear'):
                            obj.clear()
                    for obj_name in ('TICKETS', 'BOT_COMMANDS', 'MISSIONS', 'CASH_SALES', 'DELIVERY_REPORTS'):
                        obj = getattr(_cfg, obj_name, None)
                        if hasattr(obj, 'clear'):
                            obj.clear()
                    if hasattr(_cfg, 'invalidate_user_cache'):
                        _cfg.invalidate_user_cache(None)
                    if hasattr(_cfg, 'setup_data'):
                        _cfg.setup_data()
            except Exception as e:
                logger.warning('post-restore memory reload failed: %s', e)
        return safety.name if safety.exists() else 'قبلاً فایل اصلی وجود نداشت'
    except Exception:
        if safety.exists():
            shutil.copy2(str(safety), str(src_target))
        raise


async def _handle_restore_upload(msg, ctx, kind: str):
    from pathlib import Path
    import tempfile
    doc = msg.document
    if not doc:
        await msg.reply_text("❌ فایل ارسال نشد. لطفاً فایل بکاپ (.db) را به صورت document ارسال کنید.", reply_markup=_site_restore_kb())
        return
    fname = Path(doc.file_name or '').name
    if not fname.lower().endswith('.db'):
        await msg.reply_text("❌ فقط فایل با پسوند .db پذیرفته می‌شود.", reply_markup=_site_restore_kb())
        return
    if int(doc.file_size or 0) > 250 * 1024 * 1024:
        await msg.reply_text("❌ حجم فایل بیشتر از حد مجاز است.", reply_markup=_site_restore_kb())
        return
    tmp_path = Path(tempfile.gettempdir()) / f"restore_upload_{int(time.time())}_{fname}"
    try:
        # دانلود فایل با timeout بزرگ و retry (رفع باگ Timed out)
        last_err = None
        for attempt in range(1, 4):
            try:
                try:
                    tg_file = await doc.get_file(
                        read_timeout=120, write_timeout=120, connect_timeout=60)
                except Exception:
                    tg_file = await ctx.bot.get_file(
                        doc.file_id, read_timeout=120, write_timeout=120, connect_timeout=60)
                await tg_file.download_to_drive(
                    custom_path=str(tmp_path), read_timeout=120, write_timeout=120)
                last_err = None
                break
            except Exception as e:
                last_err = e
                logger.error(f"download attempt {attempt}/3 failed: {e}")
                if attempt < 3:
                    await asyncio.sleep(1)
        if last_err:
            raise last_err

        # ── پیام‌های مرحله‌ای restore (بخش B-2) ──
        label = 'bot.db' if kind == 'bot' else 'giso.db'
        await msg.reply_text(f"⏳ در حال بازگردانی {label}...")
        await msg.reply_text("⏳ در حال ساخت پشتیبان امن قبلی...")

        if kind == 'bot':
            # restore کامل bot.db با SQLite Backup API + حذف WAL/SHM + reload memory
            from db import restore_bot_db_safe
            ok, restore_msg = restore_bot_db_safe(tmp_path)
        else:
            safety_name = _safe_restore_db(kind, tmp_path)
            ok, restore_msg = True, f"فایل جایگزین شد. نسخه امن قبلی: {safety_name}"

        await msg.reply_text("⏳ در حال بررسی سلامت اطلاعات...")

        ctx.user_data.pop('state', None)
        if ok:
            # پیشنهاد ریستارت بعد از restore موفق (بخش B-3)
            await msg.reply_text(
                f"✅ بازگردانی {label} با موفقیت انجام شد\n\n"
                f"{restore_msg}\n\n"
                "⚠️ برای اعمال کامل تغییرات، لازم است ربات ریستارت شود.\n"
                "آیا موافق هستید؟",
                reply_markup=_edubot_restart_prompt_kb()
            )
        else:
            await msg.reply_text(f"❌ {restore_msg}", reply_markup=_site_restore_kb())
    except Exception as e:
        await msg.reply_text(f"❌ restore ناموفق بود و rollback انجام شد:\n{e}", reply_markup=_site_restore_kb())
    finally:
        try:
            tmp_path.unlink(missing_ok=True)
        except Exception:
            pass


async def _show_admin_delete_list(target, page: int = 0):
    PAGE_SIZE = 10
    users = [u for u in admin_list_all_users() if not u.get("is_protected_admin")]
    total = len(users)
    start = max(0, int(page or 0)) * PAGE_SIZE
    end = min(start + PAGE_SIZE, total)
    chunk = users[start:end]
    text = f"📋 حذف از لیست کاربران\n\nادمین‌های اصلی در این لیست نمایش داده نمی‌شوند.\nکل قابل حذف: {fa_num(total)}"
    rows = []
    for u in chunk:
        name = (u.get("first_name") or "کاربر")[:18]
        phone = u.get("phone") or str(u.get("id"))
        rows.append([btn(f"🗑 {name} — {phone}", f"adm_del_user|{u.get('id')}")])
    nav = []
    page = int(page or 0)
    if page > 0:
        nav.append(btn("⬅️ قبلی", f"adm_del_from_list|{page - 1}"))
    if end < total:
        nav.append(btn("بعدی ➡️", f"adm_del_from_list|{page + 1}"))
    if nav:
        rows.append(nav)
    rows.append(back_btn("adm_del_menu"))
    await target.edit_message_text(text, reply_markup=mkb(rows))


# ========================= هندلر دکمه‌ها =========================

async def button_handler(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    d = q.data
    raw_user = q.from_user
    platform = detect_platform(ctx.bot)
    set_current_platform(platform)
    sync_deleted_users_from_db()

    # روی پلتفرم ثانویه، با هویت اصلی (canonical) کار می‌کنیم
    user = effective_user(raw_user, platform)

    # کاربرِ پلتفرم ثانویه که هنوز شماره نداده/متصل نشده → ابتدا فعال‌سازی
    if platform != "bale" and canonical_user_id(platform, raw_user.id) is None:
        await safe_answer(q, "📱 ابتدا با /start و اشتراک شمارهٔ تماس، حساب خود را فعال کنید.", True)
        return

    register_user(user)
    touch_platform_activity(platform, raw_user.id)
    from ui import web_manage_kb, web_main_manage_kb, web_giso_manage_kb, web_ai_manage_kb

    # [مشکل 1] بررسی بن و میوت برای غیرادمین‌ها — قبل از هر چیز دیگری
    if not is_admin(user) and is_user_banned(user.id):
        await safe_answer(q, "🚫 دسترسی شما به ربات مسدود شده است.", True)
        return
    if not is_admin(user) and is_user_muted(user.id):
        u_data = USERS.get(str(user.id), {})
        mute_until = u_data.get("mute_until", 0)
        remaining = max(0, int(mute_until) - int(time.time()))
        if remaining > 0:
            hrs = remaining // 3600
            mins = (remaining % 3600) // 60
            if hrs > 0:
                timer_txt = f"{hrs} ساعت و {mins} دقیقه"
            else:
                timer_txt = f"{mins} دقیقه"
            await safe_answer(q, f"🔇 شما میوت هستید. {timer_txt} دیگر آزاد می‌شوید.", True)
        else:
            await safe_answer(q, "🔇 شما در حال حاضر میوت هستید و نمی‌توانید از ربات استفاده کنید.", True)
        return

    # مرحله اول — تا شماره تلفن ثبت نشده، اجازه استفاده از دکمه‌ها نده
    if not has_phone(user.id):
        await safe_answer(q, "📱 ابتدا باید شماره تلفن خود را ثبت کنید. لطفاً /start را بزنید.", True)
        return

    # [باگ ۲ — رفع تلهٔ state] کلیک روی دکمه یعنی انصراف از فلوی متنی نیمه‌تمام.
    # استثنا: دکمه‌هایی که خودشان ادامهٔ همان فلو هستند (انتخاب نوع منبع/دستور/آیتم/ماموریت).
    if not d.startswith(_STATE_KEEPING_PREFIXES):
        _cleared = clear_user_state(ctx)
        if _cleared:
            logger.debug("state «%s» با کلیک روی «%s» پاک شد.", _cleared, d)

    skip_answer = d.startswith(("checkjoin|", "checkref|", "checkaccess|", "copylink|"))
    if not skip_answer:
        await safe_answer(q)

    # ===== هندلرهای مدیریت ربات گیسو =====
    try:
        from giso_handlers import giso_button_handler, giso_inline_followup
        if await giso_button_handler(update, ctx, user=user, is_admin_flag=is_admin(user)):
            return
        if await giso_inline_followup(update, ctx, is_admin_flag=is_admin(user)):
            return
    except Exception as e:
        logger.warning(f"giso button handler error: {e}")

    # ===== منوی اصلی =====
    if d == "main":
        await q.edit_message_text(
            "🎓 منوی اصلی\n\nیکی از گزینه‌ها رو انتخاب کنید:",
            reply_markup=main_kb(user),
        )

    elif d == "courses":
        # [مشکل 4] بررسی دسترسی عمومی + اختصاصی
        if not is_admin(user):
            ok, reason = check_feature_access(user.id, "courses")
            if not ok:
                await q.edit_message_text(f"🔒 دسترسی محدود\n\n{reason}", reply_markup=mkb([home_btn()]))
                return
            ok2, reason2 = check_user_specific_access(user.id, "courses")
            if not ok2:
                await q.edit_message_text(f"🔐 دسترسی اختصاصی محدود\n\n{reason2}", reply_markup=mkb([home_btn()]))
                return
        uid_for_courses = None if is_admin(user) else user.id
        await show_courses(q, uid=uid_for_courses)

    elif d == "all_courses_feedback":
        if not SURVEYS:
            await q.edit_message_text(
                "📊 نظر کاربران درباره دوره‌ها\n\nهنوز هیچ نظری ثبت نشده.",
                reply_markup=mkb([back_btn("courses")]),
            )
            return
        fb_lines = []
        total_all = 0
        for fb_cid, fb_votes in SURVEYS.items():
            if not fb_votes:
                continue
            fb_c = COURSES.get(fb_cid, {})
            fb_exc = sum(1 for v in fb_votes.values() if v.get("vote") == "excellent")
            fb_total = len(fb_votes)
            total_all += fb_total
            fb_pct = int(fb_exc * 100 / fb_total) if fb_total else 0
            fb_bar = "⭐" * min(5, round(fb_pct / 20))
            fb_lines.append(
                f"📖 {fb_c.get('title', fb_cid)}\n   {fb_bar} {fb_pct}٪ رضایت • {fb_total} نظر"
            )
        await q.edit_message_text(
            f"📊 نظر کاربران درباره دوره‌های آنلاین\n"
            f"مجموع {total_all} نظر ثبت‌شده\n\n" + "\n\n".join(fb_lines),
            reply_markup=mkb([back_btn("courses")]),
        )

    elif d == "support":
        if not is_admin(user):
            ok, reason = check_feature_access(user.id, "support")
            if not ok:
                await q.edit_message_text(f"🔒 دسترسی محدود\n\n{reason}", reply_markup=mkb([home_btn()]))
                return
            ok2, reason2 = check_user_specific_access(user.id, "support")
            if not ok2:
                await q.edit_message_text(f"🔐 دسترسی اختصاصی محدود\n\n{reason2}", reply_markup=mkb([home_btn()]))
                return
        await show_support(q, True, user)

    elif d == "profile":
        if not is_admin(user):
            ok, reason = check_feature_access(user.id, "profile")
            if not ok:
                await q.edit_message_text(f"🔒 دسترسی محدود\n\n{reason}", reply_markup=mkb([home_btn()]))
                return
            ok2, reason2 = check_user_specific_access(user.id, "profile")
            if not ok2:
                await q.edit_message_text(f"🔐 دسترسی اختصاصی محدود\n\n{reason2}", reply_markup=mkb([home_btn()]))
                return
        await show_profile(q, user, True)

    elif d == "referral":
        if not is_admin(user):
            ok, reason = check_feature_access(user.id, "referral")
            if not ok:
                await q.edit_message_text(f"🔒 دسترسی محدود\n\n{reason}", reply_markup=mkb([home_btn()]))
                return
            ok2, reason2 = check_user_specific_access(user.id, "referral")
            if not ok2:
                await q.edit_message_text(f"🔐 دسترسی اختصاصی محدود\n\n{reason2}", reply_markup=mkb([home_btn()]))
                return
        await show_referral(q, user, True)

    elif d == "leaderboard":
        if not is_admin(user):
            ok, reason = check_feature_access(user.id, "leaderboard")
            if not ok:
                await q.edit_message_text(f"🔒 دسترسی محدود\n\n{reason}", reply_markup=mkb([home_btn()]))
                return
            ok2, reason2 = check_user_specific_access(user.id, "leaderboard")
            if not ok2:
                await q.edit_message_text(f"🔐 دسترسی اختصاصی محدود\n\n{reason2}", reply_markup=mkb([home_btn()]))
                return
        await show_leaderboard(q)

    elif d == "career_path":
        if not is_admin(user):
            ok, reason = check_feature_access(user.id, "career_path")
            if not ok:
                await q.edit_message_text(f"🔒 دسترسی محدود\n\n{reason}", reply_markup=mkb([home_btn()]))
                return
            ok2, reason2 = check_user_specific_access(user.id, "career_path")
            if not ok2:
                await q.edit_message_text(f"🔐 دسترسی اختصاصی محدود\n\n{reason2}", reply_markup=mkb([home_btn()]))
                return
        # 🤖 «مسیر شغلی هوشمند» حالا مستقیم به ماژول یار هوشمند وصل است.
        # اگر ماژول خاموش باشد، صفحهٔ ایستای قبلی نمایش داده می‌شود (fail-safe).
        if not await handle_aim_callback("aim_menu", q, ctx, user):
            await show_career_path(q, user, True)

    elif d == "latest_events":
        if not is_admin(user):
            ok, reason = check_feature_access(user.id, "latest_events")
            if not ok:
                await q.edit_message_text(f"🔒 دسترسی محدود\n\n{reason}", reply_markup=mkb([home_btn()]))
                return
            ok2, reason2 = check_user_specific_access(user.id, "latest_events")
            if not ok2:
                await q.edit_message_text(f"🔐 دسترسی اختصاصی محدود\n\n{reason2}", reply_markup=mkb([home_btn()]))
                return
        await show_latest_events(q, is_q=True)

    # ===== گنجینه =====
    elif d == "shop":
        if not is_admin(user):
            ok, reason = check_feature_access(user.id, "shop")
            if not ok:
                await q.edit_message_text(f"🔒 دسترسی محدود\n\n{reason}", reply_markup=mkb([home_btn()]))
                return
            ok2, reason2 = check_user_specific_access(user.id, "shop")
            if not ok2:
                await q.edit_message_text(f"🔐 دسترسی اختصاصی محدود\n\n{reason2}", reply_markup=mkb([home_btn()]))
                return
        await show_shop(q, user, True)

    elif d == "noop":
        await safe_answer(q, "برای عضویت در این کانال، آیدی آن را از ادمین بخواهید.", True)

    # ===== ماموریت‌ها =====
    elif d == "missions":
        if not is_admin(user):
            ok, reason = check_feature_access(user.id, "missions")
            if not ok:
                await q.edit_message_text(f"🔒 دسترسی محدود\n\n{reason}", reply_markup=mkb([home_btn()]))
                return
            ok2, reason2 = check_user_specific_access(user.id, "missions")
            if not ok2:
                await q.edit_message_text(f"🔐 دسترسی اختصاصی محدود\n\n{reason2}", reply_markup=mkb([home_btn()]))
                return
        await show_missions(q, user, is_q=True)

    elif d.startswith("mission_view|"):
        mid = d.split("|", 1)[1]
        await show_mission_detail(q, user, mid)

    elif d.startswith("mission_done|"):
        mid = d.split("|", 1)[1]
        if has_completed_mission(user.id, mid):
            await safe_answer(q, "✅ این ماموریت را قبلاً انجام داده‌اید.", True)
            return
        ok, xp_r, cr_r = complete_mission(user.id, mid)
        if ok:
            await safe_answer(q, f"🎉 آفرین! +{xp_r} XP و +{cr_r} اعتبار دریافت کردید!", True)
            # اگر دکمه روی رسانه (عکس/ویدیو) است، edit_message_text کار نمی‌کند
            # پس پیام رسانه را حذف و منوی ماموریت را جدید ارسال می‌کنیم
            try:
                await show_missions(q, user, is_q=True)
            except Exception:
                try:
                    await q.message.delete()
                except Exception:
                    pass
                await show_missions(q.message, user, is_q=False)
        else:
            await safe_answer(q, "❌ ماموریت یافت نشد یا قبلاً انجام شده.", True)

    # ===== نظرسنجی دوره =====
    elif d.startswith("rate_course|"):
        parts = d.split("|")
        if len(parts) < 3:
            return
        cid_sv, vote_sv = parts[1], parts[2]
        uid_sv = str(user.id)
        if not SURVEYS.get(cid_sv, {}).get(uid_sv):
            SURVEYS.setdefault(cid_sv, {})[uid_sv] = {
                "vote": vote_sv, "time": int(time.time())
            }
            save("surveys")
            award_xp_and_credits(user.id, xp_amount=40, credits_amount=10)
            vote_txt = "⭐ عالی" if vote_sv == "excellent" else "🔧 نیاز به به‌روزرسانی"
            await q.edit_message_text(
                f"📊 نظر شما ثبت شد: {vote_txt}\n\n"
                f"🎁 پاداش: +۴۰ امتیاز رشد | +۱۰ اعتبار\n"
                f"ممنون از بازخورد ارزشمند شما! 💙",
                reply_markup=mkb([home_btn()]),
            )
        else:
            await safe_answer(q, "✅ نظر شما قبلاً ثبت شده.", True)

    # ===== گنجینه =====
    elif d.startswith("shop_item|"):
        sid = d.split("|", 1)[1]
        item = SHOP.get(sid)
        if not item or not item.get("active", False):
            await safe_answer(q, "❌ آیتم موجود نیست.", True)
            return
        if purchase_shop_item(user.id, item, chat_id=q.message.chat.id):
            await safe_answer(q, "✅ خرید انجام شد.", True)
            kind = item.get("kind")
            try:
                if kind in ("text", "access_note"):
                    await ctx.bot.send_message(
                        chat_id=q.message.chat.id, text=item.get("content", "")
                    )
                elif kind == "link":
                    await ctx.bot.send_message(
                        chat_id=q.message.chat.id,
                        text=item.get("description", ""),
                        reply_markup=mkb([[btn("🔗 باز کردن لینک", url=item.get("content", ""))]]),
                    )
                elif kind == "file":
                    try:
                        await ctx.bot.send_document(
                            chat_id=q.message.chat.id, document=item.get("content", "")
                        )
                    except Exception:
                        await ctx.bot.send_message(
                            chat_id=q.message.chat.id,
                            text="فایل آماده نیست. برای دریافت فایل با ادمین تماس بگیرید.",
                        )
            except Exception as e:
                logger.error(f"Deliver item error: {e}")
        else:
            u_buy = USERS.get(str(user.id), {})
            _migrate_user(u_buy)
            cr = u_buy.get("credits", 0)
            price = item.get("price", 0)
            await safe_answer(q, f"❌ اعتبار کافی نیست. (شما: {cr} | قیمت: {price})", True)
        await show_shop(q, user, True)
        return

    # ===== کپی لینک =====
    elif d.startswith("copylink|"):
        parts = d.split("|")
        uid = parts[1] if len(parts) > 1 else None
        cid = parts[2] if len(parts) > 2 else None
        required, current = None, None
        try:
            required = int(parts[3])
        except Exception:
            pass
        try:
            current = int(parts[4])
        except Exception:
            pass
        if uid:
            cur_plat = get_current_platform()
            link = platform_invite_link(cur_plat, uid)
            if not link:
                if cur_plat == "bale":
                    link = f"https://ble.ir/{BOT_USERNAME}?start={uid}"
                else:
                    link = ""
            if link:
                text = f"📋 لینک دعوت شما:\n\n{link}\n\n"
            else:
                text = (
                    f"⚠️ لینک دعوت برای «{platform_name(cur_plat)}» قابل ساخت نیست.\n\n"
                    f"علت: نام کاربری ربات این پلتفرم ثبت نشده است.\n"
                    f"مسیر: پنل مدیریت → تنظیمات عمومی → مدیریت پلتفرم‌ها → "
                    f"{platform_name(cur_plat)} → ثبت/ویرایش نام کاربری ربات\n\n"
                )
            if required is not None and current is not None:
                remaining = required - current
                text += (
                    f"✅ دعوت‌های فعلی: {current} نفر\n"
                    f"🎯 تعداد لازم: {required} نفر\n"
                    f"❌ باقی‌مانده: {remaining} نفر\n\n"
                )
            if link:
                text += "👆 لینک بالا رو کپی کنید و برای دوستاتون بفرستید!"
            try:
                await q.answer()
            except Exception:
                pass
            await ctx.bot.send_message(
                chat_id=q.message.chat.id,
                text=text,
                reply_markup=mkb([[btn("🔙 بازگشت", f"checkref|{cid}" if cid else "main")]]),
            )
        return

    elif d == "send_ticket":
        if is_admin(user):
            return
        ctx.user_data["state"] = "wait_ticket"
        await q.edit_message_text(
            "✉️ پیام خود را بنویسید و ارسال کنید.\n\n"
            "تیم پشتیبانی در اسرع وقت پاسخ خواهد داد. 💙",
            reply_markup=mkb([home_btn()]),
        )

    elif d.startswith("course|"):
        await show_course_user(q, d.split("|")[1], user.id, ctx)

    # ===== چک دسترسی =====
    elif d.startswith("checkaccess|"):
        parts = d.split("|")
        cid = parts[1] if len(parts) > 1 else "global"
        lesson_idx = None
        if len(parts) > 2:
            try:
                lesson_idx = int(parts[2])
            except (ValueError, IndexError):
                pass
        cid = None if cid == "global" else cid
        ok, prob, det = await full_access_check(ctx.bot, user.id, cid, lesson_idx=lesson_idx)
        if ok:
            await safe_answer(q, "✅ دسترسی تایید شد!", True)
            if lesson_idx is not None and cid:
                await send_lesson(q, ctx, cid, lesson_idx)
            elif cid:
                await show_course_user(q, cid, user.id, ctx)
            else:
                await q.edit_message_text("🎓 منو:", reply_markup=main_kb(user))
        else:
            await show_access_denied(q, user.id, prob, det, cid, lesson_idx)

    elif d.startswith("checkjoin|"):
        parts = d.split("|")
        cid = parts[1] if len(parts) > 1 else "global"
        lesson_idx = None
        if len(parts) > 2:
            try:
                lesson_idx = int(parts[2])
            except (ValueError, IndexError):
                pass
        cid = None if cid == "global" else cid
        ok, prob, det = await full_access_check(ctx.bot, user.id, cid, lesson_idx=lesson_idx)
        if ok:
            await safe_answer(q, "✅ عضویت تایید شد!", True)
            if lesson_idx is not None and cid:
                await send_lesson(q, ctx, cid, lesson_idx)
            elif cid:
                await show_course_user(q, cid, user.id, ctx)
            else:
                await q.edit_message_text("🎓 منو:", reply_markup=main_kb(user))
        else:
            if prob == "join":
                await safe_answer(q, "❌ هنوز عضو نشدید.", True)
            elif prob == "referral":
                await safe_answer(q, "✅ عضویت تایید شد، اما شرط دعوت کامل نشده.", True)
            await show_access_denied(q, user.id, prob, det, cid, lesson_idx)

    elif d.startswith("checkref|"):
        parts = d.split("|")
        cid = parts[1] if len(parts) > 1 else "global"
        lesson_idx = None
        if len(parts) > 2:
            try:
                lesson_idx = int(parts[2])
            except (ValueError, IndexError):
                pass
        cid = None if cid == "global" else cid
        ok, prob, det = await full_access_check(ctx.bot, user.id, cid, lesson_idx=lesson_idx)
        if ok:
            await safe_answer(q, "✅ دعوت‌های شما تایید شد!", True)
            if lesson_idx is not None and cid:
                await send_lesson(q, ctx, cid, lesson_idx)
            elif cid:
                await show_course_user(q, cid, user.id, ctx)
            else:
                await q.edit_message_text("🎓 منو:", reply_markup=main_kb(user))
        else:
            if prob == "referral":
                await safe_answer(q, "❌ تعداد دعوت کافی نیست.", True)
            elif prob == "join":
                await safe_answer(q, "❌ ابتدا عضویت اجباری را کامل کنید.", True)
            await show_access_denied(q, user.id, prob, det, cid, lesson_idx)

    elif d.startswith("lesson|"):
        _, cid, idx = d.split("|")
        await send_lesson(q, ctx, cid, int(idx))

    elif d.startswith("lock|"):
        await safe_answer(q, "🔒 ابتدا سرفصل‌های قبلی را تکمیل کنید.", True)

    # ===== پنل ادمین =====
    elif d == "a_panel":
        if not is_admin(user): return
        await admin_panel(q)

    elif d == "a_shop":
        if not is_admin(user): return
        await a_shop_panel(q)

    elif d == "a_courses_menu":
        if not is_admin(user): return
        await q.edit_message_text(
            "📚 مدیریت دوره‌ها\n\nدوره جدید بسازید یا دوره‌های موجود رو ویرایش کنید.",
            reply_markup=mkb([
                [btn("➕ ساخت دوره جدید", "a_addcourse")],
                [btn("🗂 ویرایش دوره‌ها", "a_manage")],
                [btn("❌ حذف دوره", "a_dellist")],
                back_btn("a_panel"),
            ]),
        )

    elif d == "a_reports":
        if not is_admin(user): return
        await q.edit_message_text(
            "📊 گزارش‌ها\n\nآمار، کاربران و پیام‌های پشتیبانی.",
            reply_markup=mkb([
                [btn("📊 آمار کلی", "a_stats")],
                [btn("👥 لیست کاربران", "a_userlist")],
                [btn("📬 پیام‌های پشتیبانی", "a_tickets")],
                [btn("📊 گزارش نظرسنجی", "a_manage_surveys")],
                [btn("🌐 گزارش پلتفرم‌ها", "a_platform_report")],
                back_btn("a_panel"),
            ]),
        )

    elif d == "a_global_settings":
        if not is_admin(user): return
        gj = SETTINGS.get("global_required_joins", [])
        gr = SETTINGS.get("global_required_referrals", 0)
        gc = SETTINGS.get("global_required_credits", 0)
        await q.edit_message_text(
            f"⚙️ تنظیمات عمومی\n\n"
            f"🔒 عضویت اجباری کلی:\n{'  '.join(gj) if gj else '  تنظیم نشده'}\n\n"
            f"👥 دعوت اجباری کلی: {gr} نفر\n\n"
            f"💰 اعتبار اجباری کلی: {gc}\n\n"
            f"📌 این تنظیمات روی همه دوره‌ها اعمال می‌شود.",
            reply_markup=mkb([
                [btn("🔒 تنظیم عضویت اجباری", "a_global_join")],
                [btn("👥 تنظیم دعوت اجباری", "a_global_ref")],
                [btn("💰 تنظیم اعتبار اجباری", "a_global_credit")],
                [btn("🤖 مدیریت دستورات ربات", "a_cmd_menu")],
                [btn("📊 مدیریت نظرسنجی پایان دوره", "a_manage_surveys")],
                [btn("🌐 مدیریت پلتفرم‌ها", "a_platforms")],
                [btn("🤖 مدیریت AI", "a_ai_panel")],
                back_btn("a_panel"),
            ]),
        )

    elif d == "a_global_join":
        if not is_admin(user): return
        ctx.user_data["state"] = "wait_global_join"
        gj = SETTINGS.get("global_required_joins", [])
        await q.edit_message_text(
            f"🔒 عضویت اجباری کلی\n\nفعلی: {', '.join(gj) if gj else 'ندارد'}\n\n"
            f"آیدی کانال‌ها رو هر خط یکی بفرستید:\n\n"
            f"برای حذف همه بنویسید: حذف\n\n⚠️ ربات باید ادمین کانال‌ها باشد.",
            reply_markup=mkb([back_btn("a_global_settings")]),
        )

    elif d == "a_global_ref":
        if not is_admin(user): return
        ctx.user_data["state"] = "wait_global_ref"
        gr = SETTINGS.get("global_required_referrals", 0)
        await q.edit_message_text(
            f"👥 دعوت اجباری کلی\n\nفعلی: {gr} نفر\n\n"
            f"تعداد دعوت اجباری رو بفرستید (عدد):\n(0 = غیرفعال)",
            reply_markup=mkb([back_btn("a_global_settings")]),
        )

    elif d == "a_global_credit":
        if not is_admin(user): return
        ctx.user_data["state"] = "wait_global_credit"
        gc = SETTINGS.get("global_required_credits", 0)
        await q.edit_message_text(
            f"💰 اعتبار اجباری کلی\n\nفعلی: {gc}\n\n"
            f"حداقل اعتبار لازم برای دسترسی به ربات:\n(عدد بفرستید، 0 = غیرفعال)",
            reply_markup=mkb([back_btn("a_global_settings")]),
        )

    elif d == "a_web_manage":
        if not is_admin(user):
            await safe_answer(q, "❌ دسترسی ندارید.", True)
            return
        await q.edit_message_text(
            "🌐 مدیریت سایت\n\nاز اینجا می‌توانید بخش‌های مختلف سایت را مدیریت کنید.",
            parse_mode="HTML",
            reply_markup=web_manage_kb()
        )
        return

    elif d == "a_web_main_manage":
        if not is_admin(user): await safe_answer(q,"❌ دسترسی ندارید.",True);return
        await q.edit_message_text("🌐 مدیریت سایت اصلی\n\nبخش موردنظر را انتخاب کنید.",reply_markup=web_main_manage_kb());return

    elif d == "a_web_giso_manage":
        if not is_admin(user): await safe_answer(q,"❌ دسترسی ندارید.",True);return
        try:
            from giso_admin import get_giso_config, get_giso_site_config
            site_url=(get_giso_site_config('site_base_url','') or get_giso_config('site_base_url','')
                      or 'https://gisosadeghi.ir')
        except Exception: site_url='https://gisosadeghi.ir'
        await q.edit_message_text("💎 مدیریت سایت گیسو\n\nگزارش‌ها خواندنی و عملیات حساس دومرحله‌ای هستند.",reply_markup=web_giso_manage_kb(site_url));return

    elif d == "site_main_maint_menu":
        if not is_admin(user): await safe_answer(q,"❌ دسترسی ندارید.",True);return
        state='در حال به‌روزرسانی' if admin_get_maintenance_flag('site') else 'فعال'
        await q.edit_message_text(f"🚧 وضعیت و به‌روزرسانی سایت اصلی\n\nوضعیت: {state}",reply_markup=_site_main_maint_kb());return

    elif d == "site_giso_maint_menu":
        if not is_admin(user): await safe_answer(q,"❌ دسترسی ندارید.",True);return
        state='در حال به‌روزرسانی' if admin_get_maintenance_flag('giso') else 'فعال'
        await q.edit_message_text(f"🚧 وضعیت و به‌روزرسانی گیسو\n\nوضعیت: {state}",reply_markup=_site_giso_maint_kb());return

    elif d == "site_main_backup_menu":
        if not is_admin(user): await safe_answer(q,"❌ دسترسی ندارید.",True);return
        await q.edit_message_text("💾 پشتیبان و بازگردانی سایت اصلی",reply_markup=_site_main_backup_kb());return

    elif d == "site_giso_backup_menu":
        if not is_admin(user): await safe_answer(q,"❌ دسترسی ندارید.",True);return
        await q.edit_message_text("💾 پشتیبان و بازگردانی گیسو",reply_markup=_site_giso_backup_kb());return

    elif d == "site_giso_ai_report":
        if not is_admin(user): await safe_answer(q,"❌ دسترسی ندارید.",True);return
        await q.edit_message_text(_giso_ai_report_text(),parse_mode='HTML',reply_markup=mkb([[btn("🔄 به‌روزرسانی","site_giso_ai_report")],[btn("🔙 بازگشت","a_web_giso_manage")]]));return

    elif d == "site_giso_health":
        if not is_admin(user): await safe_answer(q,"❌ دسترسی ندارید.",True);return
        health_text=await asyncio.to_thread(_giso_health_text)
        await q.edit_message_text(health_text,parse_mode='HTML',reply_markup=mkb([[btn("🔄 به‌روزرسانی","site_giso_health")],[btn("🔙 بازگشت","a_web_giso_manage")]]));return

    elif d == "site_main_health":
        if not is_admin(user): await safe_answer(q,"❌ دسترسی ندارید.",True);return
        await q.edit_message_text(_main_site_health_text(),parse_mode='HTML',reply_markup=mkb([[btn("🔄 به‌روزرسانی","site_main_health")],[btn("🔙 بازگشت","a_web_main_manage")]]));return

    elif d in ("site_temp_link_main","site_temp_link_giso","site_temp_revoke_main","site_temp_revoke_giso"):
        if int(user.id) not in ADMIN_IDS: await safe_answer(q,"⛔ فقط ادمین اصلی مجاز است.",True);return
        scope='main' if d.endswith('_main') else 'giso'
        from maintenance_access import create,revoke
        if 'revoke' in d:
            revoke(scope);await q.answer("لینک فعال باطل شد.",show_alert=True)
        else:
            token=create(scope,user.id)
            base=_maint_base_url(scope)
            url=f"{base}/maintenance-access/{token}"
            await q.edit_message_text("🔐 لینک یک‌بارمصرف ۱۰ دقیقه‌ای ساخته شد. پس از کلیک باید با حساب ادمین وارد شوید.",reply_markup=mkb([[btn("ورود امن",url=url)],[btn("🔙 بازگشت","site_main_maint_menu" if scope=='main' else "site_giso_maint_menu")]]));return
        await q.edit_message_text("🚧 مدیریت به‌روزرسانی",reply_markup=_site_main_maint_kb() if scope=='main' else _site_giso_maint_kb());return

    elif d in ("site_base_url_main","site_base_url_giso"):
        if int(user.id) not in ADMIN_IDS: await safe_answer(q,"⛔ فقط ادمین اصلی مجاز است.",True);return
        scope='main' if d.endswith('_main') else 'giso'
        ctx.user_data['state']=f'wait_site_base_url_{scope}'
        cur=_maint_base_url(scope)
        lbl='سایت اصلی' if scope=='main' else 'گیسو'
        await q.edit_message_text(f"🌐 آدرس فعلی {lbl}:\n{cur}\n\nآدرس جدید را بفرست (با https:// شروع شود).\n/cancel برای لغو.",reply_markup=mkb([[btn("❌ لغو","site_main_maint_menu" if scope=='main' else "site_giso_maint_menu")]]));return

    elif d in ("site_main_image_upload","site_giso_image_upload"):
        if int(user.id) not in ADMIN_IDS: await safe_answer(q,"⛔ فقط ادمین اصلی مجاز است.",True);return
        scope='main' if d.startswith('site_main') else 'giso';ctx.user_data['state']=f'wait_maintenance_image_{scope}'
        await q.edit_message_text("🖼 تصویر را ارسال کنید.\nJPG/PNG/WebP، حداکثر ۵ مگابایت و ۲۰ مگاپیکسل.",reply_markup=mkb([[btn("❌ لغو","a_web_main_manage" if scope=='main' else "a_web_giso_manage")]]));return

    elif d in ("site_main_image_reset","site_giso_image_reset"):
        if int(user.id) not in ADMIN_IDS: await safe_answer(q,"⛔ فقط ادمین اصلی مجاز است.",True);return
        scope='main' if d.startswith('site_main') else 'giso';ok=_reset_maintenance_image(scope)
        await q.answer("✅ تصویر پیش‌فرض فعال شد." if ok else "❌ بازنشانی ناموفق بود.",show_alert=True)
        await q.edit_message_text("🚧 تنظیم تصویر به‌روزرسانی",reply_markup=_site_main_maint_kb() if scope=='main' else _site_giso_maint_kb());return

    elif d == "site_giso_cleanup":
        if int(user.id) not in ADMIN_IDS: await safe_answer(q,"⛔ فقط ادمین اصلی مجاز است.",True);return
        files=_safe_giso_cleanup_candidates();size=sum(p.stat().st_size for p in files if p.exists());ctx.user_data['giso_cleanup_preview_at']=time.time()
        text=f"🧹 پیش‌نمایش پاک‌سازی امن گیسو\n\nفایل قابل حذف: {fa_num(len(files))}\nحجم قابل آزادسازی: {fa_num(size//1024)} کیلوبایت\n\nدیتابیس، فایل کاربران، رسیدها و فایل‌های اصلی حذف نمی‌شوند."
        await q.edit_message_text(text,reply_markup=mkb([[btn("✅ تأیید پاک‌سازی","site_giso_cleanup_confirm"),btn("❌ لغو","a_web_giso_manage")]]));return

    elif d == "site_giso_cleanup_confirm":
        if int(user.id) not in ADMIN_IDS: await safe_answer(q,"⛔ فقط ادمین اصلی مجاز است.",True);return
        preview=float(ctx.user_data.pop('giso_cleanup_preview_at',0) or 0)
        if time.time()-preview>300: await q.answer("پیش‌نمایش منقضی شده؛ دوباره بررسی کنید.",show_alert=True);return
        deleted=0;freed=0
        for path in _safe_giso_cleanup_candidates():
            try:
                if path.is_file() and not path.is_symlink(): freed+=path.stat().st_size;path.unlink();deleted+=1
            except Exception as e: logger.warning("safe cleanup skip %s: %s",path,e)
        await q.edit_message_text(f"✅ پاک‌سازی امن تمام شد.\nفایل حذف‌شده: {fa_num(deleted)}\nحجم آزادشده: {fa_num(freed//1024)} کیلوبایت",reply_markup=mkb([[btn("🔙 بازگشت","a_web_giso_manage")]]));return

    elif d == "site_maint_menu":
        if not is_admin(user):
            await safe_answer(q, "❌ دسترسی ندارید.", True)
            return
        await q.edit_message_text(_site_maint_text(), reply_markup=_site_maint_kb())
        return

    elif d in ("site_maint_on_web", "site_maint_off_web", "site_maint_on_giso", "site_maint_off_giso"):
        if not is_admin(user):
            await safe_answer(q, "❌ دسترسی ندارید.", True)
            return
        name = 'giso' if d.endswith('_giso') else 'site'
        value = '_off_' in d  # off callback یعنی غیرفعال کردن سایت/گیسو => maintenance=on
        ok = admin_set_maintenance_flag(name, value)
        if not ok:
            await safe_answer(q, "❌ ذخیره وضعیت ناموفق بود.", True)
        state_text = "در حال به‌روزرسانی" if value else "فعال"
        await q.edit_message_text(
            f"🚧 وضعیت {'گیسو' if name=='giso' else 'سایت اصلی'}\n\nوضعیت: {state_text}",
            reply_markup=_site_giso_maint_kb() if name=='giso' else _site_main_maint_kb(),
        )
        return

    elif d == "site_health_report":
        if not is_admin(user):
            await safe_answer(q, "❌ دسترسی ندارید.", True)
            return
        await q.edit_message_text(_site_health_text(), parse_mode="HTML", reply_markup=mkb([back_btn("a_web_manage")]))
        return

    elif d == "noop_header":
        await safe_answer(q)
        return

    elif d == "site_backup_menu":
        if not is_admin(user):
            await safe_answer(q, "❌ دسترسی ندارید.", True)
            return
        # خواندن تنظیمات فعلی
        try:
            interval = int(SETTINGS.get("backup_interval_hours", "0") or "0")
        except (TypeError, ValueError):
            interval = 0
        backup_dir = _edubot_backup_dir()
        try:
            os.makedirs(backup_dir, exist_ok=True)
        except Exception:
            pass
        try:
            backup_files = sorted(
                [f for f in os.listdir(backup_dir) if f.endswith('.db')],
                reverse=True,
            )
        except Exception:
            backup_files = []
        last_backup = SETTINGS.get("last_backup_at", "ثبت نشده")

        text = (
            "💾 <b>پشتیبان‌گیری و بازگردانی</b>\n\n"
            f"📁 تعداد backup: {len(backup_files)}\n"
            f"📅 آخرین backup: {html.escape(str(last_backup))}\n"
        )
        if interval > 0:
            text += f"\n⏱ backup خودکار: هر {interval} ساعت ✅\n"
        else:
            text += "\n⏱ backup خودکار: غیرفعال ❌\n"
        text += (
            "\n━━━━━━━━━━━━━━━━━━━━━━\n"
            "عملیات مورد نظر را انتخاب کنید.\n"
            "✅ قبل از هر backup، اطلاعات WAL به DB منتقل می‌شود."
        )
        await q.edit_message_text(text, reply_markup=_edubot_backup_main_kb(), parse_mode="HTML")
        return

    elif d == "site_backup_sub":
        # زیرمنوی «💾 پشتیبان‌گیری» (بخش A-2)
        if not is_admin(user):
            await safe_answer(q, "❌ دسترسی ندارید.", True)
            return
        await q.edit_message_text(
            "💾 <b>پشتیبان‌گیری</b>\n\n"
            "کدام دیتابیس را پشتیبان بگیرم؟",
            reply_markup=_edubot_backup_sub_kb(),
            parse_mode="HTML",
        )
        return

    elif d in ("site_backup_bot", "site_backup_giso", "site_backup_all"):
        if not is_admin(user):
            await safe_answer(q, "❌ دسترسی ندارید.", True)
            return
        kinds = ['bot', 'giso'] if d == 'site_backup_all' else (['bot'] if d == 'site_backup_bot' else ['giso'])
        if d == 'site_backup_all':
            await q.edit_message_text("⏳ شروع پشتیبان‌گیری از هر دو دیتابیس...")
            results = []
            for i, kind in enumerate(kinds, start=1):
                _ok, _m = await _send_db_backup(q, kind, total=len(kinds), index=i)
                results.append(_ok)
            if all(results):
                await q.edit_message_text("✅ هر دو پشتیبان با موفقیت ارسال شدند.")
            else:
                await q.edit_message_text("❌ یکی از پشتیبان‌ها ناموفق بود.")
        else:
            await q.edit_message_text("⏳ شروع پشتیبان‌گیری...")
            await _send_db_backup(q, kinds[0])
        return

    elif d == "site_backup_schedule":
        if not is_admin(user):
            await safe_answer(q, "❌ دسترسی ندارید.", True)
            return
        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("هر ۱ ساعت", callback_data="backup_sched_1"),
                InlineKeyboardButton("هر ۳ ساعت", callback_data="backup_sched_3"),
            ],
            [
                InlineKeyboardButton("هر ۶ ساعت", callback_data="backup_sched_6"),
                InlineKeyboardButton("هر ۱۲ ساعت", callback_data="backup_sched_12"),
            ],
            [
                InlineKeyboardButton("هر ۲۴ ساعت", callback_data="backup_sched_24"),
                InlineKeyboardButton("❌ غیرفعال", callback_data="backup_sched_0"),
            ],
            [InlineKeyboardButton("🔙 بازگشت", callback_data="site_backup_menu")],
        ])
        await q.edit_message_text(
            "⏱ <b>تنظیم backup خودکار</b>\n\n"
            "هر چند ساعت از هر دو دیتابیس backup بگیرم?\n\n"
            "💡 هر backup شامل:\n"
            "• checkpoint (انتقال WAL به DB)\n"
            "• کپی bot.db و giso.db\n"
            "• حذف backup قدیمی (نگهداری ۵ آخر)",
            reply_markup=keyboard,
            parse_mode="HTML",
        )
        return

    elif d.startswith("backup_sched_"):
        if not is_admin(user):
            await safe_answer(q, "❌ دسترسی ندارید.", True)
            return
        try:
            hours = int(d.replace("backup_sched_", ""))
        except (TypeError, ValueError):
            await safe_answer(q, "⚠️ مقدار نامعتبر.", True)
            return
        if not admin_set_setting_value("backup_interval_hours", str(hours)):
            await safe_answer(q, "❌ خطا در ذخیره تنظیم.", True)
            return
        if hours == 0:
            _stop_edubot_backup_timer(ctx)
            text = "❌ backup خودکار <b>غیرفعال</b> شد."
        else:
            _start_edubot_backup_timer(ctx, hours)
            text = f"✅ backup خودکار تنظیم شد: <b>هر {hours} ساعت</b>"
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 بازگشت به منوی backup", callback_data="site_backup_menu")]
        ])
        await q.edit_message_text(text, reply_markup=keyboard, parse_mode="HTML")
        return

    elif d == "site_restore_menu":
        if not is_admin(user):
            await safe_answer(q, "❌ دسترسی ندارید.", True)
            return
        await q.edit_message_text("📥 بارگذاری فایل پشتیبان\n\nنوع دیتابیس را انتخاب کنید:", reply_markup=_site_restore_kb())
        return

    elif d in ("site_restore_bot", "site_restore_giso"):
        if not is_admin(user):
            await safe_answer(q, "❌ دسترسی ندارید.", True)
            return
        kind = 'bot' if d == 'site_restore_bot' else 'giso'
        await q.edit_message_text(
            f"📥 بازگردانی {kind}.db\n\nروش بازگردانی را انتخاب کنید:",
            reply_markup=_site_restore_method_kb(kind)
        )
        return

    elif d in ("site_restore_bot_manual", "site_restore_giso_manual"):
        if not is_admin(user):
            await safe_answer(q, "❌ دسترسی ندارید.", True)
            return
        kind = 'bot' if d == 'site_restore_bot_manual' else 'giso'
        ctx.user_data['state'] = f'waiting_restore_{kind}'
        await q.edit_message_text(
            "📤 لطفاً فایل بکاپ (.db) را به صورت document ارسال کنید.\n\n"
            "برای لغو: /cancel",
            reply_markup=_site_restore_method_kb(kind)
        )
        return

    elif d in ("site_restore_bot_list", "site_restore_giso_list"):
        if not is_admin(user):
            await safe_answer(q, "❌ دسترسی ندارید.", True)
            return
        kind = 'bot' if d == 'site_restore_bot_list' else 'giso'
        files = _edubot_list_backup_files(kind)
        if not files:
            await q.edit_message_text(
                "📋 بکاپی برای این دیتابیس یافت نشد.",
                reply_markup=mkb([back_btn("site_restore_menu")])
            )
            return
        rows = []
        for i, f in enumerate(files[:10]):
            size_kb = f['size'] // 1024
            rows.append([InlineKeyboardButton(
                f"📄 {f['name']} ({size_kb}KB)",
                callback_data=f"edubot_restore_pick_{kind}_{i}"
            )])
        rows.append([InlineKeyboardButton("🔙 بازگشت", callback_data="site_restore_menu")])
        await q.edit_message_text(
            f"📋 بکاپ‌های {kind}.db:\n\nروی فایل مورد نظر کلیک کنید:",
            reply_markup=InlineKeyboardMarkup(rows)
        )
        return

    elif d.startswith("edubot_restore_pick_"):
        if not is_admin(user):
            await safe_answer(q, "❌ دسترسی ندارید.", True)
            return
        parts = d.split("_")  # edubot_restore_pick_<kind>_<idx>
        kind = parts[3]
        try:
            idx = int(parts[4])
        except (ValueError, IndexError):
            await safe_answer(q, "⚠️ مقدار نامعتبر.", True)
            return
        files = _edubot_list_backup_files(kind)
        if idx >= len(files):
            await safe_answer(q, "بکاپ پیدا نشد.", True)
            return
        f = files[idx]
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("✅ بله، بازگردانی کن", callback_data=f"edubot_restore_confirm_{kind}_{idx}")],
            [InlineKeyboardButton("❌ لغو", callback_data="site_restore_menu")],
        ])
        await q.edit_message_text(
            f"⚠️ آیا مطمئنی می‌خواهی از این فایل بازگردانی کنی؟\n\n📄 {f['name']}",
            reply_markup=kb
        )
        return

    elif d.startswith("edubot_restore_confirm_"):
        if not is_admin(user):
            await safe_answer(q, "❌ دسترسی ندارید.", True)
            return
        parts = d.split("_")  # edubot_restore_confirm_<kind>_<idx>
        kind = parts[3]
        try:
            idx = int(parts[4])
        except (ValueError, IndexError):
            await safe_answer(q, "⚠️ مقدار نامعتبر.", True)
            return
        files = _edubot_list_backup_files(kind)
        if idx >= len(files):
            await safe_answer(q, "بکاپ پیدا نشد.", True)
            return
        f = files[idx]
        label = 'bot.db' if kind == 'bot' else 'giso.db'
        # ── پیام‌های مرحله‌ای restore (بخش B-2) ──
        await q.edit_message_text(f"⏳ در حال بازگردانی {label}...")
        await q.edit_message_text("⏳ در حال ساخت پشتیبان امن قبلی...")
        ok, msg = _edubot_restore_from_path(f['path'], kind)
        await q.edit_message_text("⏳ در حال بررسی سلامت اطلاعات...")
        if ok:
            # پیشنهاد ریستارت بعد از restore موفق (بخش B-3)
            await q.edit_message_text(
                f"✅ بازگردانی {label} با موفقیت انجام شد\n\n"
                f"{msg}\n\n"
                "⚠️ برای اعمال کامل تغییرات، لازم است ربات ریستارت شود.\n"
                "آیا موافق هستید؟",
                reply_markup=_edubot_restart_prompt_kb()
            )
        else:
            await q.edit_message_text(f"❌ {msg}", reply_markup=_site_restore_kb())
        return

    elif d in ("site_backup_list_bot","site_backup_list_giso"):
        if not is_admin(user): await safe_answer(q,"❌ دسترسی ندارید.",True);return
        kind='bot' if d.endswith('_bot') else 'giso';files=_edubot_list_backup_files(kind)
        lines=[f"📋 <b>پشتیبان‌های {'سایت اصلی' if kind=='bot' else 'گیسو'}:</b>\n"]
        for f in files[:20]: lines.append(f"📄 {html.escape(f['name'])} ({fa_num(f['size']//1024)} کیلوبایت)")
        if not files: lines.append("هنوز پشتیبانی ثبت نشده است.")
        await q.edit_message_text("\n".join(lines),parse_mode='HTML',reply_markup=mkb([[btn("🔙 بازگشت","site_main_backup_menu" if kind=='bot' else "site_giso_backup_menu")]]));return

    elif d == "site_backup_list":
        if not is_admin(user):
            await safe_answer(q, "❌ دسترسی ندارید.", True)
            return
        files = _edubot_list_backup_files('bot') + _edubot_list_backup_files('giso')
        if not files:
            await q.edit_message_text(
                "📋 هنوز بکاپی گرفته نشده.",
                reply_markup=_site_backup_kb()
            )
            return
        lines = ["📋 <b>لیست بکاپ‌های موجود:</b>\n"]
        for f in files[:20]:
            size_kb = f['size'] // 1024
            lines.append(f"📄 {html.escape(f['name'])} ({size_kb}KB)")
        text = "\n".join(lines)
        # دانلود: برای سادگی فایل اول را می‌فرستیم (کاربر می‌تواند از مسیر پوشه backup استفاده کند)
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 بازگشت", callback_data="site_backup_menu")]
        ])
        await q.edit_message_text(text, reply_markup=kb, parse_mode="HTML")
        return

    elif d == "site_cleanup_menu":
        if not is_admin(user):
            await safe_answer(q, "❌ دسترسی ندارید.", True)
            return
        await q.edit_message_text("🔄 پاکسازی سریع\n\nیکی از گزینه‌های امن را انتخاب کنید:", reply_markup=_site_cleanup_kb())
        return

    elif d == "edubot_restart_menu":
        if not is_admin(user):
            await safe_answer(q, "❌ دسترسی ندارید.", True)
            return
        await q.edit_message_text(
            "🔄 ریستارت ربات آموزشی\n\nپس از چه مدت ریستارت شود؟",
            reply_markup=_edubot_restart_kb()
        )
        return

    elif d == "edubot_restart_yes":
        # کاربر بعد از restore با ریستارت موافقت کرد → منوی تایمر (بخش B-3)
        if not is_admin(user):
            await safe_answer(q, "❌ دسترسی ندارید.", True)
            return
        await q.edit_message_text(
            "⏱ چند ثانیه تایمر برای ریستارت انتخاب می‌کنید؟",
            reply_markup=_edubot_restart_kb()
        )
        return

    elif d == "edubot_restart_later":
        # کاربر ریستارت را رد کرد → بازگشت به منوی بازگردانی
        if not is_admin(user):
            await safe_answer(q, "❌ دسترسی ندارید.", True)
            return
        await safe_answer(q, "بسیار خوب، ریستارت لغو شد.", True)
        await q.edit_message_text(
            "📥 بازگردانی\n\nنوع دیتابیس را انتخاب کنید:",
            reply_markup=_site_restore_kb()
        )
        return

    elif d == "edubot_restart_cancel":
        if not is_admin(user):
            return
        await safe_answer(q, "لغو شد.", True)
        try:
            await q.edit_message_text("❌ ریستارت لغو شد.")
        except Exception:
            pass
        return

    elif d.startswith("edubot_restart_confirm_"):
        if not is_admin(user):
            await safe_answer(q, "❌ دسترسی ندارید.", True)
            return
        try:
            seconds = int(d.replace("edubot_restart_confirm_", ""))
        except (TypeError, ValueError):
            await safe_answer(q, "⚠️ مقدار نامعتبر.", True)
            return
        await _edubot_restart_flow(q, ctx, seconds)
        return

    elif d in ("site_clean_sessions", "site_clean_cache", "site_clean_incomplete"):
        if not is_admin(user):
            await safe_answer(q, "❌ دسترسی ندارید.", True)
            return
        if d == "site_clean_sessions":
            res = admin_cleanup_server_sessions()
            text = res.get('message') if res.get('ok') else f"❌ خطا: {res.get('error')}"
        elif d == "site_clean_cache":
            res = admin_cleanup_safe_caches()
            text = f"✅ کش پاک شد. تعداد آیتم‌ها: {fa_num(res.get('total', 0))}" if res.get('ok') else f"❌ خطا: {res.get('error')}"
        else:
            res = admin_cleanup_incomplete_requests()
            counts = res.get('counts') or {}
            text = (
                "✅ پاکسازی درخواست‌های ناتمام انجام شد.\n"
                f"مشاور pending قدیمی: {fa_num(counts.get('consultant_pending_old', 0))}\n"
                f"پیام مشاور orphan: {fa_num(counts.get('consultant_orphan_messages', 0))}\n"
                f"خرید نقدی pending قدیمی: {fa_num(counts.get('cash_pending_old', 0))}\n"
                f"تحلیل مهمان orphan: {fa_num(counts.get('guest_orphan_analysis', 0))}"
            ) if res.get('ok') else f"❌ خطا: {res.get('error')}"
        await q.edit_message_text(text, reply_markup=_site_cleanup_kb())
        return

    elif d == "a_web_ai_manage":
        if not is_admin(user):
            await safe_answer(q, "❌ دسترسی ندارید.", True)
            return
        await q.edit_message_text(
            "🤖 مدیریت هوش مصنوعی سایت\n\nیکی از گزینه‌های زیر را انتخاب کنید:",
            parse_mode="HTML",
            reply_markup=web_ai_manage_kb()
        )
        return

    elif d == "a_web_ai_status":
        if not is_admin(user):
            await safe_answer(q, "❌ دسترسی ندارید.", True)
            return
        try:
            import sys
            from pathlib import Path
            _web_path = Path(__file__).resolve().parent.parent / "web"
            if str(_web_path) not in sys.path:
                sys.path.insert(0, str(_web_path))
            from web_ai import get_status_report, format_status_for_telegram
            report = get_status_report()
            text = format_status_for_telegram(report)
            await q.edit_message_text(
                text,
                parse_mode="HTML",
                reply_markup=web_ai_manage_kb()
            )
        except Exception as e:
            await q.edit_message_text(
                f"❌ خطا در دریافت وضعیت:\n<code>{e}</code>",
                parse_mode="HTML",
                reply_markup=web_ai_manage_kb()
            )
        return

    elif d == "a_web_ai_check":
        if not is_admin(user):
            await safe_answer(q, "❌ دسترسی ندارید.", True)
            return
        await q.edit_message_text("⏳ در حال بررسی زنده هوش مصنوعی سایت...\nلطفاً چند ثانیه صبر کنید.")
        try:
            import sys
            from pathlib import Path
            _web_path = Path(__file__).resolve().parent.parent / "web"
            if str(_web_path) not in sys.path:
                sys.path.insert(0, str(_web_path))
            from web_ai import run_live_check, format_live_check_for_telegram
            report = run_live_check()
            text = format_live_check_for_telegram(report)
            await q.edit_message_text(
                text,
                parse_mode="HTML",
                reply_markup=web_ai_manage_kb()
            )
        except Exception as e:
            await q.edit_message_text(
                f"❌ خطا در بررسی زنده:\n<code>{e}</code>",
                parse_mode="HTML",
                reply_markup=web_ai_manage_kb()
            )
        return
    # ===== مدیریت پلتفرم‌ها (ادمین) =====

    elif d == "a_platforms":
        if not is_admin(user): return
        await show_platform_management(q, is_q=True)

    elif d == "a_platform_report":
        if not is_admin(user): return
        await show_platform_report(q, is_q=True)

    # ===== مرکز پیام‌رسانی =====

    elif d == "a_messaging":
        if not is_admin(user): return
        messaging_reset_bc(ctx)
        await show_messaging_center_v2(q, is_q=True)

    elif d == "bc_stats":
        if not is_admin(user): return
        await show_messaging_stats(q, is_q=True)

    elif d.startswith("bc_phones|"):
        if not is_admin(user): return
        try:
            page = int(d.split("|", 1)[1])
        except (ValueError, IndexError):
            page = 0
        await show_phone_list(q, page=page, is_q=True)

    elif d == "bc_reports":
        if not is_admin(user): return
        await show_delivery_reports(q, is_q=True)

    elif d == "bc_delay":
        # [ویژگی گم‌شده ۱] منوی تنظیم تأخیر ارسال
        if not is_admin(user): return
        await show_delay_menu(q, is_q=True)

    elif d.startswith("bc_delay_set|"):
        if not is_admin(user): return
        try:
            val = float(d.split("|", 1)[1])
        except (ValueError, IndexError):
            await safe_answer(q, "❌ مقدار نامعتبر.", True)
            return
        applied = messaging_set_delay(val)
        await safe_answer(q, f"✅ تأخیر ارسال: {applied:g} ثانیه", True)
        await show_delay_menu(q, is_q=True)

    elif d == "bc_delay_custom":
        if not is_admin(user): return
        ctx.user_data["state"] = "wait_bc_delay"
        await q.edit_message_text(
            "✏️ مقدار دلخواه تأخیر\n"
            "━━━━━━━━━━━━━━━━\n\n"
            f"یک عدد بین {messaging_delay_min():g} تا {messaging_delay_max():g} بفرستید.\n"
            "مثال: 1.5",
            reply_markup=mkb([back_btn("bc_delay")]),
        )

    elif d.startswith("bc_rep|"):
        # [باگ ۲ — رفع‌شده] پارامتر حالا id یکتای گزارش است، نه ایندکس لیست
        if not is_admin(user): return
        try:
            rep_id = int(d.split("|", 1)[1])
        except Exception:
            rep_id = -1
        await show_delivery_report_detail(q, rep_id, is_q=True)

    elif d.startswith("bc_route|"):
        if not is_admin(user): return
        route = d.split("|", 1)[1]
        messaging_reset_bc(ctx)
        ctx.user_data["bc"] = {"route": route}
        if route == "users":
            await show_user_mode_menu(q, is_q=True)
        else:
            await show_bc_destination_menu(q, route=route, is_q=True)

    elif d.startswith("bc_usermode|"):
        if not is_admin(user): return
        user_mode = d.split("|", 1)[1]
        bc = ctx.user_data.setdefault("bc", {"route": "users"})
        bc["route"] = "users"
        bc["user_mode"] = user_mode
        await show_bc_destination_menu(q, route="users", user_mode=user_mode, is_q=True)

    elif d.startswith("bc_dest|"):
        if not is_admin(user): return
        dest = d.split("|", 1)[1]
        bc = ctx.user_data.setdefault("bc", {"route": "users"})
        bc["dest"] = dest
        route = bc.get("route", "users")
        user_mode = bc.get("user_mode", "all")
        n, unit = messaging_get_destination_count(route, user_mode, dest)
        dest_label = "همه پلتفرم‌ها" if dest == "all" else platform_name(dest)
        bc["dest_label"] = dest_label
        bc["count"] = n
        bc["unit"] = unit
        if route == "users" and user_mode == "single":
            # [کار ۴-۱] بعد از انتخاب پلتفرم، فهرست کاربرانِ همان پلتفرم نمایش داده می‌شود
            ctx.user_data["state"] = "wait_bc_direct_target"
            await show_bc_user_list(q, dest, page=0, is_q=True)
        else:
            await q.edit_message_text(
                f"📤 مقصد: {dest_label} ({fa_num(n)} {unit})\n\nنوع پیام را انتخاب کنید:",
                reply_markup=bcast_type_kb(),
            )

    elif d.startswith("bc_ulist|"):
        # [کار ۴-۱] صفحه‌بندی فهرست کاربران
        if not is_admin(user): return
        parts = d.split("|")
        dest = parts[1] if len(parts) > 1 else "all"
        try:
            page = int(parts[2]) if len(parts) > 2 else 0
        except ValueError:
            page = 0
        ctx.user_data["state"] = "wait_bc_direct_target"
        await show_bc_user_list(q, dest, page=page, is_q=True)

    elif d.startswith("bc_upick|"):
        # [کار ۴-۱] انتخاب کاربر از فهرست (بدون نیاز به تایپ آی‌دی)
        if not is_admin(user): return
        parts = d.split("|")
        dest = parts[1] if len(parts) > 1 else "all"
        try:
            gi = int(parts[2])
        except (ValueError, IndexError):
            await safe_answer(q, "❌ انتخاب نامعتبر.", True)
            return
        entries = messaging_user_entries(dest)
        if gi < 0 or gi >= len(entries):
            await safe_answer(q, "❌ کاربر پیدا نشد. دوباره تلاش کنید.", True)
            return
        plat, cid, disp = entries[gi]
        ctx.user_data.pop("state", None)
        bc = ctx.user_data.setdefault("bc", {"route": "users", "user_mode": "single"})
        bc["route"] = "users"
        bc["user_mode"] = "single"
        bc["dest"] = dest
        bc["target_platform"] = plat
        bc["target_chat_id"] = cid
        bc["target_display"] = disp
        await q.edit_message_text(
            f"🎯 گیرنده: {disp}\n"
            f"🌐 پلتفرم: {platform_name(plat)}\n"
            f"💬 Chat ID: {cid}\n\n"
            "نوع پیام را انتخاب کنید:",
            reply_markup=bcast_type_kb(),
        )

    elif d.startswith("bc_pick|"):
        if not is_admin(user): return
        try:
            i = int(d.split("|", 1)[1])
        except Exception:
            i = -1
        cands = ctx.user_data.get("bc_candidates") or []
        if i < 0 or i >= len(cands):
            await safe_answer(q, "❌ گزینه نامعتبر است.", True)
            return
        plat, cid, disp = cands[i]
        ctx.user_data.pop("bc_candidates", None)
        bc = ctx.user_data.setdefault("bc", {"route": "users", "user_mode": "single"})
        bc["target_platform"] = plat
        bc["target_chat_id"] = cid
        bc["target_display"] = disp
        await q.edit_message_text(
            f"🎯 گیرنده: {disp} ({platform_name(plat)})\n\nنوع پیام را انتخاب کنید:",
            reply_markup=bcast_type_kb(),
        )

    elif d.startswith("bc_type|"):
        if not is_admin(user): return
        mtype = d.split("|", 1)[1]
        bc = ctx.user_data.setdefault("bc", {})
        bc["type"] = mtype
        bc["title"] = ""
        bc["desc"] = ""
        bc["file_id"] = None
        bc.pop("origin_platform", None)
        ctx.user_data["state"] = "wait_bc_title"
        await q.edit_message_text(
            f"📦 نوع پیام: {_TYPE_FA.get(mtype, mtype)}\n\n"
            "✏️ عنوان پیام را بفرستید:\n"
            "(برای رد کردن عنوان، یک «-» بفرستید)",
            reply_markup=mkb([back_btn("a_messaging")]),
        )

    elif d == "bc_send":
        if not is_admin(user): return
        ok, err = await messaging_do_send(q, ctx)
        if not ok and err:
            await ctx.bot.send_message(
                q.message.chat_id,
                err,
                reply_markup=mkb([back_btn("a_messaging")]),
            )

    elif d.startswith("a_plat|"):
        if not is_admin(user): return
        p = d.split("|", 1)[1]
        await show_platform_detail(q, p, is_q=True)

    elif d.startswith("a_plat_token|"):
        if not is_admin(user): return
        p = d.split("|", 1)[1]
        ctx.user_data["state"] = "wait_platform_token"
        ctx.user_data["platform_target"] = p
        await q.edit_message_text(
            f"🔑 توکن ربات {platform_name(p)} را بفرستید:\n\n"
            f"برای حذف بنویسید: حذف\n\n"
            f"ℹ️ پس از ذخیره، اتصال به‌صورت خودکار با توکن جدید برقرار می‌شود.",
            reply_markup=mkb([back_btn(f"a_plat|{p}")]),
        )

    elif d.startswith("a_plat_uname|"):
        if not is_admin(user): return
        p = d.split("|", 1)[1]
        ctx.user_data["state"] = "wait_platform_uname"
        ctx.user_data["platform_target"] = p
        await q.edit_message_text(
            f"🏷 نام کاربری ربات {platform_name(p)} را بدون @ بفرستید:\n"
            f"(برای ساخت لینک اتصال لازم است)\n\nبرای حذف بنویسید: حذف",
            reply_markup=mkb([back_btn(f"a_plat|{p}")]),
        )

    elif d.startswith("a_plat_support|"):
        if not is_admin(user): return
        p = d.split("|", 1)[1]
        ctx.user_data["state"] = "wait_platform_support"
        ctx.user_data["platform_target"] = p
        cur_sup = str(SETTINGS.get(f"{p}_support", "") or "").strip()
        await q.edit_message_text(
            f"📞 پشتیبانی مخصوص {platform_name(p)}\n"
            "━━━━━━━━━━━━━━━━\n\n"
            f"مقدار فعلی: {cur_sup or f'پیش‌فرض ({SUPPORT_GROUP} — گروه بله)'}\n\n"
            f"آیدی/لینک پشتیبانی {platform_name(p)} را بفرستید:\n"
            f"نمونه‌ها:\n  • @my_support\n  • https://t.me/my_support\n\n"
            "ℹ️ این لینک در این موارد به کاربرِ همین پلتفرم نشان داده می‌شود:\n"
            "  • پیام تأیید ارسال تیکت\n"
            "  • پاسخ تیم پشتیبانی\n"
            "  • صفحهٔ پشتیبانی و خرید نقدی\n\n"
            "اگر چیزی ثبت نشود، پشتیبانی پیش‌فرض (گروه بله) نمایش داده می‌شود.\n"
            "برای حذف/بازگشت به پیش‌فرض بنویسید: حذف",
            reply_markup=mkb([back_btn(f"a_plat|{p}")]),
        )

    elif d.startswith("a_plat_toggle|"):
        # [کار ۲] فعال/غیرفعال کردن پلتفرم — با اعمال واقعی روی اتصال
        if not is_admin(user): return
        p = d.split("|", 1)[1]
        cur = platform_enabled(p)
        new_state = not cur

        if p == "telegram":
            # ذخیره در دیتابیس + قطع/وصل واقعی اتصال
            ok, msg_txt = await apply_telegram_enabled(new_state)
            await safe_answer(q, msg_txt[:190], alert=not ok)
        else:
            SETTINGS[f"{p}_enabled"] = 1 if new_state else 0
            save("settings")

        await show_platform_detail(q, p, is_q=True)

    elif d.startswith("a_plat_status|"):
        # [کار ۲ — بند ۶] بررسی وضعیت واقعی اتصال
        if not is_admin(user): return
        p = d.split("|", 1)[1]
        if p == "telegram":
            body = telegram_status_text()
        else:
            body = "وضعیت: " + ("🟢 فعال" if platform_enabled(p) else "🔴 غیرفعال")
        await q.edit_message_text(
            f"📊 وضعیت واقعی {platform_name(p)}\n"
            "━━━━━━━━━━━━━━━━\n\n"
            f"{body}",
            reply_markup=mkb([
                [btn("🔄 بررسی دوباره", f"a_plat_status|{p}")],
                back_btn(f"a_plat|{p}"),
            ]),
        )

    elif d.startswith("a_plat_adminlink|"):
        if not is_admin(user): return
        p = d.split("|", 1)[1]
        code = create_admin_link_code(p, user.id)
        link = build_deep_link(p, code)
        link_line = link if link else "(ابتدا نام کاربری ربات این پلتفرم را ثبت کنید)"
        await q.edit_message_text(
            f"➕ لینک ادمین {platform_name(p)} ساخته شد:\n\n"
            f"{link_line}\n\n"
            f"🔑 کد: <code>{code}</code>\n"
            f"⏳ یک‌بارمصرف و دارای انقضا. شخص با باز کردن این لینک و زدن Start، "
            f"به‌عنوان ادمین {platform_name(p)} ثبت می‌شود.",
            reply_markup=mkb([back_btn(f"a_plat|{p}")]),
            parse_mode="HTML",
        )

    elif d.startswith("a_plat_admins|"):
        if not is_admin(user): return
        p = d.split("|", 1)[1]
        await show_platform_admins_list(q, p, is_q=True)

    # ===== [افزوده] زیرمنوی تنظیمات پروکسی تلگرام =====

    elif d.startswith("a_plat_proxy|"):
        if not is_admin(user): return
        p = d.split("|", 1)[1]
        await show_proxy_menu(q, p, is_q=True)

    elif d.startswith("a_plat_proxy_fetch|"):
        # 📥 دریافت خودکار از منبع + تست همزمان + ذخیره
        if not is_admin(user): return
        p = d.split("|", 1)[1]
        chat_id = q.message.chat_id

        if pm.cache_is_fresh() and pm.working_count() > 0:
            await q.edit_message_text(
                f"♻️ لیست فعلی تازه است ({pm.age_text()}) و {fa_num(pm.working_count())} "
                "پروکسی سالم دارد.\n\nبرای تست دوباره از «🔄 آپدیت و تست مجدد» استفاده کنید.",
                reply_markup=mkb([
                    [btn("🔄 تست مجدد همین حالا", f"a_plat_proxy_revalidate|{p}")],
                    back_btn(f"a_plat_proxy|{p}"),
                ]),
            )
            return

        await q.edit_message_text("📥 در حال دریافت لیست از منبع…")
        prog = await ctx.bot.send_message(chat_id, "⏳ آماده‌سازی…")

        async def _on_prog(done, total, alive):
            try:
                await ctx.bot.edit_message_text(
                    f"🔬 تست پروکسی‌ها… {fa_num(done)}/{fa_num(total)}  |  سالم: {fa_num(alive)}",
                    chat_id=chat_id, message_id=prog.message_id,
                )
            except Exception:
                pass

        rep, err = await pm.refresh_from_source(on_progress=_on_prog)
        if err:
            await ctx.bot.send_message(
                chat_id, f"❌ {err}",
                reply_markup=mkb([back_btn(f"a_plat_proxy|{p}")]),
            )
            return
        # [کار ۱] گزارش کامل: دریافتی / سالم / مرده / سریع‌ترین / زمان
        await ctx.bot.send_message(
            chat_id,
            pm.format_test_report(rep, "دریافت‌شده از منبع"),
            reply_markup=mkb([
                [btn("📄 نمایش لیست", f"a_plat_proxy_list|{p}|0")],
                [btn("✏️ ورود دستی پروکسی", f"a_plat_proxy_manual|{p}")],
                back_btn(f"a_plat_proxy|{p}"),
            ]),
        )

    elif d.startswith("a_plat_proxy_revalidate|"):
        # 🔄 تست مجدد پروکسی‌های ذخیره‌شده و حذف مرده‌ها
        if not is_admin(user): return
        p = d.split("|", 1)[1]
        chat_id = q.message.chat_id
        if pm.working_count() == 0:
            await safe_answer(q, "لیستی برای تست وجود ندارد. ابتدا دریافت کنید.", True)
            return

        await q.edit_message_text("🔄 در حال تست مجدد پروکسی‌های ذخیره‌شده…")
        prog = await ctx.bot.send_message(chat_id, "⏳ آماده‌سازی…")

        async def _on_prog2(done, total, alive):
            try:
                await ctx.bot.edit_message_text(
                    f"🔬 تست… {fa_num(done)}/{fa_num(total)}  |  سالم: {fa_num(alive)}",
                    chat_id=chat_id, message_id=prog.message_id,
                )
            except Exception:
                pass

        rep, err = await pm.revalidate(on_progress=_on_prog2)
        if err:
            await ctx.bot.send_message(
                chat_id, f"❌ {err}",
                reply_markup=mkb([back_btn(f"a_plat_proxy|{p}")]),
            )
            return
        await ctx.bot.send_message(
            chat_id,
            pm.format_test_report(rep, "تست‌شده از لیست ذخیره‌شده"),
            reply_markup=mkb([
                [btn("📄 نمایش لیست", f"a_plat_proxy_list|{p}|0")],
                back_btn(f"a_plat_proxy|{p}"),
            ]),
        )

    elif d.startswith("a_plat_proxy_testmanual|"):
        # [کار ۱ — بند ۲] «🧪 تست همین پروکسی‌ها» — فقط پروکسی‌های دستی
        if not is_admin(user): return
        p = d.split("|", 1)[1]
        chat_id = q.message.chat_id
        n_manual = len(pm.get_manual_proxies())
        if n_manual == 0:
            await safe_answer(q, "ابتدا پروکسی دستی وارد کنید.", True)
            return

        await q.edit_message_text(f"🧪 در حال تست {fa_num(n_manual)} پروکسی دستی…")
        prog = await ctx.bot.send_message(chat_id, "⏳ آماده‌سازی…")

        async def _on_prog3(done, total, alive):
            try:
                await ctx.bot.edit_message_text(
                    f"🔬 تست… {fa_num(done)}/{fa_num(total)}  |  سالم: {fa_num(alive)}",
                    chat_id=chat_id, message_id=prog.message_id,
                )
            except Exception:
                pass

        rep, err = await pm.test_manual_proxies(on_progress=_on_prog3)
        if err:
            await ctx.bot.send_message(
                chat_id, f"❌ {err}",
                reply_markup=mkb([back_btn(f"a_plat_proxy|{p}")]),
            )
            return
        await ctx.bot.send_message(
            chat_id,
            pm.format_test_report(rep, "وارد‌شده دستی"),
            reply_markup=mkb([
                [btn("📄 نمایش لیست", f"a_plat_proxy_list|{p}|0")],
                [btn("✏️ ویرایش پروکسی‌های دستی", f"a_plat_proxy_manual|{p}")],
                back_btn(f"a_plat_proxy|{p}"),
            ]),
        )

    elif d.startswith("a_plat_proxy_manual|"):
        # ✏️ ورود دستی پروکسی
        if not is_admin(user): return
        p = d.split("|", 1)[1]
        ctx.user_data["state"] = "wait_proxy_manual"
        ctx.user_data["proxy_platform"] = p
        cur = pm.get_manual_proxies()
        cur_txt = "\n".join(f"• {x}" for x in cur) if cur else "(خالی)"
        await q.edit_message_text(
            "✏️ وارد کردن دستی پروکسی\n"
            "━━━━━━━━━━━━━━━━\n\n"
            f"پروکسی‌های فعلی:\n{cur_txt}\n\n"
            f"حداکثر {fa_num(pm.MAX_MANUAL)} پروکسی — هر خط یکی:\n\n"
            "📝 فرمت‌های مجاز:\n"
            "  • 1.2.3.4:1080\n"
            "  • socks5://1.2.3.4:1080\n"
            "  • http://user:pass@1.2.3.4:3128\n\n"
            "برای پاک کردن همه بنویسید: حذف",
            reply_markup=mkb([back_btn(f"a_plat_proxy|{p}")]),
        )

    elif d.startswith("a_plat_proxy_src|"):
        # 🔧 تغییر URL منبع
        if not is_admin(user): return
        p = d.split("|", 1)[1]
        ctx.user_data["state"] = "wait_proxy_source"
        ctx.user_data["proxy_platform"] = p
        await q.edit_message_text(
            "🔧 تغییر URL منبع پروکسی\n"
            "━━━━━━━━━━━━━━━━\n\n"
            f"منبع فعلی:\n{pm.get_source_url()}\n\n"
            "URL جدید را بفرستید.\n"
            "خروجی باید متن ساده با هر خط یک پروکسی باشد.\n\n"
            "برای بازگشت به پیش‌فرض بنویسید: پیشفرض",
            reply_markup=mkb([back_btn(f"a_plat_proxy|{p}")]),
        )

    elif d.startswith("a_plat_proxy_list|"):
        # 📄 نمایش پروکسی‌های سالم
        if not is_admin(user): return
        parts = d.split("|")
        p = parts[1] if len(parts) > 1 else "telegram"
        try:
            page = int(parts[2]) if len(parts) > 2 else 0
        except ValueError:
            page = 0
        await show_proxy_list(q, p, page=page, is_q=True)

    elif d.startswith("a_plat_proxy_mode|"):
        # ⚙️ منوی انتخاب حالت اتصال
        if not is_admin(user): return
        p = d.split("|", 1)[1]
        await show_proxy_mode_menu(q, p, is_q=True)

    elif d.startswith("a_plat_proxy_setmode|"):
        # ⚙️ اعمال حالت اتصال
        if not is_admin(user): return
        parts = d.split("|")
        p = parts[1] if len(parts) > 1 else "telegram"
        mode = parts[2] if len(parts) > 2 else pm.MODE_AUTO
        pm.set_mode(mode)
        await safe_answer(q, f"✅ حالت اتصال: {pm.mode_label(mode)}", True)
        await show_proxy_mode_menu(q, p, is_q=True)

    elif d.startswith("a_plat_proxy_clear|"):
        # 🗑️ حذف لیست پروکسی
        if not is_admin(user): return
        p = d.split("|", 1)[1]
        n = pm.working_count()
        pm.clear_working()
        await safe_answer(q, f"🗑️ {n} پروکسی حذف شد.", True)
        await show_proxy_menu(q, p, is_q=True)

    # ===== 🗣 مشاور انسانی سایت =====
    elif d.startswith("cons_"):
        if not await _handle_consultant_callback(d, q, ctx, user):
            await safe_answer(q, "❌ این گزینه شناخته نشد.", True)

    # ===== 🤖 یار هوشمند شغلی (ai_mentor) =====
    # ⚠️ این شاخه باید قبل از شاخهٔ "ai_" بیاید.
    # پیشوند aim_ با ai_ شروع نمی‌شود، ولی برای خوانایی و جلوگیری از
    # اشتباه در ویرایش‌های بعدی، عمداً بالاتر قرار گرفته است.
    elif d.startswith("aim_a_"):
        # بخش ادمین ماژول
        if not is_admin(user): return
        if not await handle_aim_admin_callback(d, q, ctx, user):
            await safe_answer(q, "❌ این گزینه شناخته نشد.", True)

    elif d.startswith("aim_"):
        # بخش کاربر عادی — بدون گارد ادمین
        if not await handle_aim_callback(d, q, ctx, user):
            await safe_answer(q, "❌ این گزینه شناخته نشد.", True)

    # ===== 🤖 مدیریت هوش مصنوعی — فقط ادمین =====
    elif d == "a_ai_panel" or d.startswith(("ai_", "a_ai_")):
        if not is_admin(user): return
        handled_ai = await handle_ai_callback(d, q, ctx)
        if not handled_ai:
            await safe_answer(q, "❌ این گزینه شناخته نشد.", True)

    # ===== اتصال کاربر به پلتفرم دیگر =====

    elif d.startswith("u_link|"):
        p = d.split("|", 1)[1]
        if not user_can_connect_platform(user.id, p):
            await safe_answer(q, "این پلتفرم در دسترس نیست.", alert=True)
            return
        if user_has_platform(user.id, p):
            await safe_answer(q, "شما قبلاً به این پلتفرم متصل شده‌اید.", alert=True)
            return
        mission = get_platform_link_mission(p)
        mid = mission.get("id", "") if mission else ""
        code = create_link_code(user.id, p, mid)
        link = build_deep_link(p, code)
        await show_platform_link_prompt(q, user, p, code, link, is_q=True)

    # ===== مدیریت کاربران (ادمین) =====

    elif d == "a_users_manage":
        if not is_admin(user): return
        await show_users_manage(q)

    # [مشکل 2] لیست کاربران با صفحه‌بندی
    elif d.startswith("a_users_list|"):
        if not is_admin(user): return
        try:
            page = int(d.split("|", 1)[1])
        except (ValueError, IndexError):
            page = 0
        await show_users_list(q, page)

    elif d == "a_user_search":
        if not is_admin(user): return
        ctx.user_data["state"] = "wait_user_search_id"
        await q.edit_message_text(
            "🔍 جستجوی کاربر\n\nآی‌دی عددی کاربر را بفرستید:",
            reply_markup=mkb([back_btn("a_users_manage")]),
        )

    elif d == "adm_del_menu":
        if not is_admin(user): return
        await show_user_delete_menu(q)

    elif d == "adm_del_all":
        if not is_admin(user): return
        result = admin_delete_all_users(deleted_by={"user_id": user.id}, include_admins=True)
        await q.edit_message_text(_admin_delete_summary(result), reply_markup=mkb([back_btn("a_users_manage")]))

    elif d == "adm_del_by_phone":
        if not is_admin(user): return
        ctx.user_data["state"] = "wait_adm_del_phone"
        await q.edit_message_text(
            "📱 حذف با شماره همراه\n\nشماره کاربر را بفرستید. حذف بلافاصله انجام می‌شود.",
            reply_markup=mkb([back_btn("adm_del_menu")]),
        )

    elif d.startswith("adm_del_from_list"):
        if not is_admin(user): return
        try:
            page = int(d.split("|", 1)[1]) if "|" in d else 0
        except Exception:
            page = 0
        await _show_admin_delete_list(q, page)

    elif d.startswith("adm_del_user|"):
        if not is_admin(user): return
        uid_str = d.split("|", 1)[1]
        u_t = USERS.get(uid_str, {})
        result = admin_delete_user_everywhere(int(uid_str), u_t.get("phone", ""), {"user_id": user.id}, mode="single_user_id")
        await q.edit_message_text(_admin_delete_summary(result), reply_markup=mkb([back_btn("adm_del_from_list")]))

    elif d.startswith("a_user_detail|"):
        if not is_admin(user): return
        uid_str = d.split("|", 1)[1]
        await show_user_detail(q, uid_str)

    elif d.startswith("a_user_xp|"):
        if not is_admin(user): return
        uid_str = d.split("|", 1)[1]
        await show_user_xp_panel(q, uid_str)

    elif d.startswith("a_user_xp_add|"):
        if not is_admin(user): return
        uid_str = d.split("|", 1)[1]
        ctx.user_data["state"] = "wait_user_xp_delta"
        ctx.user_data["target_uid"] = uid_str
        u_t = USERS.get(uid_str, {})
        await q.edit_message_text(
            f"📈 افزودن/کاستن XP\n\nکاربر: {u_t.get('first_name', uid_str)}\nXP فعلی: {u_t.get('xp', 0)}\n\n"
            "مقدار تغییر را بفرستید (مثلاً: 50 برای اضافه یا -20 برای کاستن):",
            reply_markup=mkb([back_btn(f"a_user_xp|{uid_str}")]),
        )

    elif d.startswith("a_user_xp_set|"):
        if not is_admin(user): return
        uid_str = d.split("|", 1)[1]
        ctx.user_data["state"] = "wait_user_xp_value"
        ctx.user_data["target_uid"] = uid_str
        u_t = USERS.get(uid_str, {})
        await q.edit_message_text(
            f"🎯 تنظیم مقدار XP\n\nکاربر: {u_t.get('first_name', uid_str)}\nXP فعلی: {u_t.get('xp', 0)}\n\n"
            "مقدار جدید XP را بفرستید (عدد):",
            reply_markup=mkb([back_btn(f"a_user_xp|{uid_str}")]),
        )

    elif d.startswith("a_user_credit|"):
        if not is_admin(user): return
        uid_str = d.split("|", 1)[1]
        await show_user_credit_panel(q, uid_str)

    elif d.startswith("a_user_credit_add|"):
        if not is_admin(user): return
        uid_str = d.split("|", 1)[1]
        ctx.user_data["state"] = "wait_user_credit_delta"
        ctx.user_data["target_uid"] = uid_str
        u_t = USERS.get(uid_str, {})
        _migrate_user(u_t)
        await q.edit_message_text(
            f"💰 افزودن/کاستن اعتبار\n\nکاربر: {u_t.get('first_name', uid_str)}\nاعتبار فعلی: {u_t.get('credits', 0)}\n\n"
            "مقدار تغییر را بفرستید (مثلاً: 100 یا -50):",
            reply_markup=mkb([back_btn(f"a_user_credit|{uid_str}")]),
        )

    elif d.startswith("a_user_credit_set|"):
        if not is_admin(user): return
        uid_str = d.split("|", 1)[1]
        ctx.user_data["state"] = "wait_user_credit_value"
        ctx.user_data["target_uid"] = uid_str
        u_t = USERS.get(uid_str, {})
        _migrate_user(u_t)
        await q.edit_message_text(
            f"🎯 تنظیم مقدار اعتبار\n\nکاربر: {u_t.get('first_name', uid_str)}\nاعتبار فعلی: {u_t.get('credits', 0)}\n\n"
            "مقدار جدید اعتبار را بفرستید (عدد):",
            reply_markup=mkb([back_btn(f"a_user_credit|{uid_str}")]),
        )

    elif d.startswith("a_user_ban|"):
        if not is_admin(user): return
        uid_str = d.split("|", 1)[1]
        u_t = USERS.get(uid_str, {})
        await q.edit_message_text(
            f"🚫 بن کردن کاربر: {u_t.get('first_name', uid_str)}\n\n"
            "مدت بن را انتخاب کنید:",
            reply_markup=mkb([
                [btn("۲۴ ساعت", f"a_user_ban_dur|{uid_str}|24"),
                 btn("۴۸ ساعت", f"a_user_ban_dur|{uid_str}|48")],
                [btn("۱ هفته",  f"a_user_ban_dur|{uid_str}|168"),
                 btn("دائم",    f"a_user_ban_dur|{uid_str}|0")],
                back_btn(f"a_user_detail|{uid_str}"),
            ]),
        )

    elif d.startswith("a_user_ban_dur|"):
        if not is_admin(user): return
        parts = d.split("|")
        uid_str = parts[1]
        hrs = int(parts[2]) if len(parts) > 2 and parts[2].isdigit() else 0
        until_ts = int(time.time()) + hrs * 3600 if hrs > 0 else 0
        ok = set_user_ban(int(uid_str) if uid_str.isdigit() else 0, True, until_ts)
        dur_txt = f"{hrs} ساعت" if hrs > 0 else "دائم"
        if ok:
            await safe_answer(q, f"🚫 کاربر برای {dur_txt} بن شد.", True)
        await show_user_detail(q, uid_str)

    elif d.startswith("a_user_unban|"):
        if not is_admin(user): return
        uid_str = d.split("|", 1)[1]
        ok = set_user_ban(int(uid_str) if uid_str.isdigit() else 0, False)
        if ok:
            await safe_answer(q, "✅ کاربر آنبن شد.", True)
        await show_user_detail(q, uid_str)

    # [مشکل 3] محدودیت اختصاصی پنل کاربر
    elif d.startswith("a_user_panel_restrict|"):
        if not is_admin(user): return
        uid_str = d.split("|", 1)[1]
        await show_user_feature_restrictions(q, uid_str)

    elif d.startswith("a_user_feat_block|"):
        if not is_admin(user): return
        parts = d.split("|")
        if len(parts) < 3:
            return
        uid_str, fkey = parts[1], parts[2]
        # ذخیره state و بپرس چند ساعت یا دائم
        ctx.user_data["state"] = "wait_feat_block_duration"
        ctx.user_data["target_uid"] = uid_str
        ctx.user_data["block_fkey"] = fkey
        u_t = USERS.get(uid_str, {})
        fkey_label = dict(FEATURE_KEYS).get(fkey, fkey)
        await q.edit_message_text(
            f"🔒 محدود کردن بخش: {fkey_label}\n"
            f"👤 کاربر: {u_t.get('first_name', uid_str)}\n\n"
            "مدت محدودیت را انتخاب کنید (یا عدد ساعت بفرستید):",
            reply_markup=mkb([
                [btn("۲۴ ساعت", f"a_user_feat_block_dur|{uid_str}|{fkey}|24"),
                 btn("۴۸ ساعت", f"a_user_feat_block_dur|{uid_str}|{fkey}|48")],
                [btn("۱ هفته", f"a_user_feat_block_dur|{uid_str}|{fkey}|168"),
                 btn("دائم", f"a_user_feat_block_dur|{uid_str}|{fkey}|0")],
                back_btn(f"a_user_panel_restrict|{uid_str}"),
            ]),
        )

    elif d.startswith("a_user_feat_block_dur|"):
        if not is_admin(user): return
        parts = d.split("|")
        if len(parts) < 4:
            return
        uid_str, fkey, hrs_str = parts[1], parts[2], parts[3]
        try:
            hrs = int(hrs_str)
        except ValueError:
            hrs = 0
        until_ts = int(time.time()) + hrs * 3600 if hrs > 0 else 0
        set_user_feature_restriction(int(uid_str) if uid_str.isdigit() else 0, fkey, True, until_ts)
        fkey_label = dict(FEATURE_KEYS).get(fkey, fkey)
        dur_txt = f"{hrs} ساعت" if hrs > 0 else "دائم"
        await safe_answer(q, f"🔒 بخش «{fkey_label}» برای {dur_txt} محدود شد.", True)
        await show_user_feature_restrictions(q, uid_str)

    elif d.startswith("a_user_feat_unblock|"):
        if not is_admin(user): return
        parts = d.split("|")
        if len(parts) < 3:
            return
        uid_str, fkey = parts[1], parts[2]
        remove_user_feature_restriction(int(uid_str) if uid_str.isdigit() else 0, fkey)
        fkey_label = dict(FEATURE_KEYS).get(fkey, fkey)
        await safe_answer(q, f"✅ محدودیت بخش «{fkey_label}» برداشته شد.", True)
        await show_user_feature_restrictions(q, uid_str)

    elif d.startswith("a_user_mute|"):
        if not is_admin(user): return
        uid_str = d.split("|", 1)[1]
        ctx.user_data["state"] = "wait_user_mute_duration"
        ctx.user_data["target_uid"] = uid_str
        u_t = USERS.get(uid_str, {})
        await q.edit_message_text(
            f"🔇 میوت کردن کاربر: {u_t.get('first_name', uid_str)}\n\n"
            "مدت میوت را انتخاب کنید یا عدد دقیقه بفرستید:",
            reply_markup=mkb([
                [btn("۱ ساعت",  f"a_user_mute_dur|{uid_str}|60"),
                 btn("۶ ساعت",  f"a_user_mute_dur|{uid_str}|360")],
                [btn("۲۴ ساعت", f"a_user_mute_dur|{uid_str}|1440"),
                 btn("۴۸ ساعت", f"a_user_mute_dur|{uid_str}|2880")],
                [btn("۱ هفته",  f"a_user_mute_dur|{uid_str}|10080")],
                back_btn(f"a_user_detail|{uid_str}"),
            ]),
        )

    elif d.startswith("a_user_mute_dur|"):
        if not is_admin(user): return
        parts = d.split("|")
        uid_str = parts[1]
        mins = int(parts[2]) if len(parts) > 2 and parts[2].isdigit() else 60
        until = int(time.time()) + mins * 60
        ok = set_user_mute(int(uid_str) if uid_str.isdigit() else 0, until)
        hrs = mins // 60
        dur_txt = f"{hrs} ساعت" if hrs > 0 else f"{mins} دقیقه"
        if ok:
            await safe_answer(q, f"🔇 کاربر برای {dur_txt} میوت شد.", True)
        await show_user_detail(q, uid_str)

    elif d.startswith("a_user_unmute|"):
        if not is_admin(user): return
        uid_str = d.split("|", 1)[1]
        ok = set_user_mute(int(uid_str) if uid_str.isdigit() else 0, 0)
        if ok:
            await safe_answer(q, "✅ کاربر آنمیوت شد.", True)
        await show_user_detail(q, uid_str)

    # ===== دسترسی بخش‌ها (ادمین) =====

    elif d == "a_feature_access":
        if not is_admin(user): return
        await show_feature_access_panel(q)

    elif d.startswith("a_feature_set|"):
        if not is_admin(user): return
        fkey = d.split("|", 1)[1]
        if fkey not in dict(FEATURE_KEYS):
            await safe_answer(q, "❌ بخش نامعتبر.", True)
            return
        await show_feature_detail(q, fkey)

    elif d.startswith("a_feature_field|"):
        if not is_admin(user): return
        parts = d.split("|")
        if len(parts) < 3:
            return
        fkey = parts[1]
        field = parts[2]
        valid_fields = {"min_xp", "min_credits", "min_level", "min_edu_rank"}
        if fkey not in dict(FEATURE_KEYS) or field not in valid_fields:
            await safe_answer(q, "❌ پارامتر نامعتبر.", True)
            return
        ctx.user_data["state"] = "wait_feature_value"
        ctx.user_data["feature_key"] = fkey
        ctx.user_data["feature_field"] = field
        field_labels = {
            "min_xp": "حداقل XP (0 = بدون محدودیت)",
            "min_credits": "حداقل اعتبار (0 = بدون محدودیت)",
            "min_level": "حداقل سطح (0-6، 0 = بدون محدودیت)",
            "min_edu_rank": "حداقل رتبه علمی (0-6، 0 = بدون محدودیت)",
        }
        await q.edit_message_text(
            f"🔑 تنظیم دسترسی: {FEATURE_LABELS.get(fkey, fkey)}\n\n"
            f"مقدار جدید {field_labels.get(field, field)} را بفرستید (عدد):",
            reply_markup=mkb([back_btn(f"a_feature_set|{fkey}")]),
        )

    elif d.startswith("a_feature_reset|"):
        if not is_admin(user): return
        fkey = d.split("|", 1)[1]
        set_feature_rule(fkey, {"min_xp": 0, "min_credits": 0, "min_level": 0, "min_edu_rank": 0})
        await safe_answer(q, "✅ همه محدودیت‌های این بخش حذف شد.", True)
        await show_feature_detail(q, fkey)

    # ===== فروش نقدی (ادمین) =====

    elif d == "a_cash_sales":
        if not is_admin(user): return
        await show_cash_sales_admin(q)

    elif d.startswith("a_cash_review|"):
        if not is_admin(user): return
        try:
            req_id = int(d.split("|", 1)[1])
        except (ValueError, IndexError):
            return
        req = next((r for r in CASH_SALES if r.get("_db_id") == req_id), None)
        if req:
            # ارسال عکس فیش اگر وجود داشته باشد
            fiche = req.get("fiche_file_id", "")
            await show_cash_sale_review(q, req_id)
            if fiche:
                try:
                    await ctx.bot.send_photo(
                        chat_id=q.message.chat.id,
                        photo=fiche,
                        caption=f"📎 فیش درخواست #{req_id}\n👤 {req.get('user_name', '---')}",
                    )
                except Exception as e:
                    logger.error(f"Send fiche photo error: {e}")
        else:
            await safe_answer(q, "❌ درخواست پیدا نشد.", True)

    elif d.startswith("a_cash_approve|"):
        if not is_admin(user): return
        try:
            req_id = int(d.split("|", 1)[1])
        except (ValueError, IndexError):
            return
        req = next((r for r in CASH_SALES if r.get("_db_id") == req_id), None)
        if not req:
            await safe_answer(q, "❌ درخواست پیدا نشد.", True)
            return
        if req.get("status") != "pending":
            await safe_answer(q, "⚠️ این درخواست قبلاً بررسی شده.", True)
            return
        ok, err = await send_cash_status_strict(req, approved=True)
        if not ok:
            await safe_answer(q, f"❌ تأیید انجام نشد.\n{err}", True)
            return
        req["status"] = "approved"
        req["reviewed_at"] = int(time.time())
        # [مشکل 5] باز کردن دسترسی دوره یا سرفصل برای کاربر
        cid = req.get("course_id", "")
        uid_req = req.get("user_id")
        target_type = req.get("target_type", "course")
        lesson_id = req.get("lesson_id", "")
        if uid_req and cid and cid in COURSES:
            u_req = USERS.get(str(uid_req))
            if u_req:
                _migrate_user(u_req)
                if target_type == "lesson" and lesson_id:
                    u_req["credits_paid"][f"lesson_{lesson_id}"] = True
                else:
                    u_req["credits_paid"][f"course_{cid}"] = True
                # [مورد 6] اعطای XP و اعتبار بر اساس تنظیمات فروش نقدی
                _sale_key = f"lesson|{lesson_id}" if (target_type == "lesson" and lesson_id) else f"course|{cid}"
                _sale_cfg = CASH_SALE_SETTINGS.get(_sale_key, {})
                _xp_rw = _sale_cfg.get("xp_reward", 0)
                _cr_rw = _sale_cfg.get("credits_reward", 0)
                if _xp_rw:
                    u_req["xp"] = u_req.get("xp", 0) + _xp_rw
                if _cr_rw:
                    u_req["credits"] = u_req.get("credits", 0) + _cr_rw
                save("users")
        save("cash_sales")
        await safe_answer(q, "✅ درخواست تأیید شد و به کاربر اطلاع داده شد.", True)
        await show_cash_sales_admin(q)

    # [مشکل 5] نمایش عکس فیش برای ادمین
    elif d.startswith("a_cash_show_fiche|"):
        if not is_admin(user): return
        try:
            req_id = int(d.split("|", 1)[1])
        except (ValueError, IndexError):
            return
        req = next((r for r in CASH_SALES if r.get("_db_id") == req_id), None)
        if not req:
            await safe_answer(q, "❌ درخواست پیدا نشد.", True)
            return
        fiche_file_id = req.get("fiche_file_id", "")
        if not fiche_file_id:
            await safe_answer(q, "❌ فیشی برای این درخواست ثبت نشده.", True)
            return
        try:
            await ctx.bot.send_photo(
                user.id, fiche_file_id,
                caption=f"🖼 فیش درخواست #{req_id}\n👤 {req.get('user_name', '---')} ({req.get('user_id', '---')})",
            )
        except Exception:
            try:
                await ctx.bot.send_document(
                    user.id, fiche_file_id,
                    caption=f"📎 فیش درخواست #{req_id}",
                )
            except Exception as e:
                logger.error(f"Send fiche to admin error: {e}")
                await safe_answer(q, "❌ ارسال فیش ناموفق بود.", True)

    elif d.startswith("a_cash_reject|"):
        if not is_admin(user): return
        try:
            req_id = int(d.split("|", 1)[1])
        except (ValueError, IndexError):
            return
        req = next((r for r in CASH_SALES if r.get("_db_id") == req_id), None)
        if not req:
            await safe_answer(q, "❌ درخواست پیدا نشد.", True)
            return
        if req.get("status") != "pending":
            await safe_answer(q, "⚠️ این درخواست قبلاً بررسی شده.", True)
            return
        ok, err = await send_cash_status_strict(req, approved=False)
        if not ok:
            await safe_answer(q, f"❌ رد درخواست انجام نشد.\n{err}", True)
            return
        req["status"] = "rejected"
        req["reviewed_at"] = int(time.time())
        save("cash_sales")
        await safe_answer(q, "❌ درخواست رد شد.", True)
        await show_cash_sales_admin(q)

    # ===== فروش نقدی (کاربر) =====

    elif d.startswith("cash_locked_course|"):
        await safe_answer(q)
        cid = d.split("|", 1)[1]
        ctitle = COURSES.get(cid, {}).get("title", "")
        msg = (
            "🔒 این دوره فروش نقدی است\n"
            f"📖 {ctitle}\n\n"
            "برای تهیه این دوره به گنجینه مراجعه کنید و خرید را انجام دهید.\n"
            "پس از تایید خرید توسط ادمین، تمام سرفصل‌ها برای شما باز می‌شود."
        )
        await q.edit_message_text(msg, reply_markup=mkb([
            [btn("💵 خرید این دوره از گنجینه", f"cash_buy|{cid}")],
            [btn("⬅️ بازگشت به دوره", f"course|{cid}")],
            home_btn(),
        ]))

    elif d.startswith("cash_locked_lesson|"):
        await safe_answer(q)
        parts = d.split("|")
        cid = parts[1] if len(parts) > 1 else ""
        idx = int(parts[2]) if len(parts) > 2 and parts[2].isdigit() else 0
        lessons = COURSES.get(cid, {}).get("lessons", [])
        ltitle = lessons[idx].get("title", "") if idx < len(lessons) else ""
        msg = (
            "🔒 این سرفصل فروش نقدی است\n"
            f"📝 {ltitle}\n\n"
            "برای تهیه این سرفصل به گنجینه مراجعه کنید و خرید را انجام دهید.\n"
            "پس از تایید خرید توسط ادمین، این سرفصل برای شما باز می‌شود."
        )
        await q.edit_message_text(msg, reply_markup=mkb([
            [btn("💵 خرید این سرفصل از گنجینه", f"cash_lesson_buy|{cid}|{idx}")],
            [btn("⬅️ بازگشت به دوره", f"course|{cid}")],
            home_btn(),
        ]))

    elif d.startswith("cash_buy|"):
        if is_admin(user): return
        cid = d.split("|", 1)[1]
        if cid not in COURSES:
            await safe_answer(q, "❌ دوره پیدا نشد.", True)
            return
        # [مورد 1] بررسی اگر قبلاً خریده
        _u = USERS.get(str(user.id), {})
        _migrate_user(_u)
        if _u.get("credits_paid", {}).get(f"course_{cid}"):
            await safe_answer(q, "✅ این دوره قبلاً برای شما فعال شده است.", True)
            return
        # بررسی اگر قبلاً درخواست در انتظار دارد
        has_pending = any(
            r.get("user_id") == user.id and r.get("course_id") == cid and r.get("status") == "pending"
            for r in CASH_SALES
        )
        if has_pending:
            await safe_answer(q, "⏳ یک درخواست در حال بررسی دارید. صبر کنید.", True)
            return
        await show_cash_sale_request(q, user, cid, is_q=True)

    elif d.startswith("cash_lesson_buy|"):
        if is_admin(user): return
        parts = d.split("|")
        cid = parts[1] if len(parts) > 1 else ""
        idx = int(parts[2]) if len(parts) > 2 and parts[2].isdigit() else 0
        if cid not in COURSES:
            await safe_answer(q, "❌ دوره پیدا نشد.", True)
            return
        lessons = COURSES[cid].get("lessons", [])
        if idx >= len(lessons):
            await safe_answer(q, "❌ سرفصل پیدا نشد.", True)
            return
        lid = lessons[idx].get("lid", str(idx))
        # [مورد 1] بررسی اگر قبلاً خریده
        _u = USERS.get(str(user.id), {})
        _migrate_user(_u)
        if _u.get("credits_paid", {}).get(f"lesson_{lid}"):
            await safe_answer(q, "✅ این سرفصل قبلاً برای شما فعال شده است.", True)
            return
        # بررسی اگر قبلاً درخواست در انتظار دارد
        has_pending = any(
            r.get("user_id") == user.id and r.get("lesson_id") == lid and r.get("status") == "pending"
            for r in CASH_SALES
        )
        if has_pending:
            await safe_answer(q, "⏳ یک درخواست در حال بررسی دارید. صبر کنید.", True)
            return
        await show_cash_lesson_sale_request(q, user, cid, idx, is_q=True)

    # [مشکل 5] callback دکمه «ارسال فیش پرداخت»
    elif d.startswith("cash_send_fiche|"):
        if is_admin(user): return
        parts = d.split("|")
        # cash_send_fiche|course|cid   OR  cash_send_fiche|lesson|lid|cid|lesson_idx
        target_type = parts[1] if len(parts) > 1 else "course"
        if target_type == "course":
            cid = parts[2] if len(parts) > 2 else ""
            has_pending = any(
                r.get("user_id") == user.id and r.get("course_id") == cid and r.get("status") == "pending"
                for r in CASH_SALES
            )
            if has_pending:
                await safe_answer(q, "⏳ یک درخواست در حال بررسی دارید. صبر کنید.", True)
                return
            ctx.user_data["state"] = "wait_cash_fiche"
            ctx.user_data["cash_fiche_target_type"] = "course"
            ctx.user_data["cash_fiche_target_id"] = cid
            ctx.user_data["cash_fiche_course_id"] = cid
        else:  # lesson
            lid = parts[2] if len(parts) > 2 else ""
            cid = parts[3] if len(parts) > 3 else ""
            lesson_idx = parts[4] if len(parts) > 4 else "0"
            has_pending = any(
                r.get("user_id") == user.id and r.get("lesson_id") == lid and r.get("status") == "pending"
                for r in CASH_SALES
            )
            if has_pending:
                await safe_answer(q, "⏳ یک درخواست در حال بررسی دارید. صبر کنید.", True)
                return
            ctx.user_data["state"] = "wait_cash_fiche"
            ctx.user_data["cash_fiche_target_type"] = "lesson"
            ctx.user_data["cash_fiche_target_id"] = lid
            ctx.user_data["cash_fiche_course_id"] = cid
            ctx.user_data["cash_fiche_lesson_idx"] = lesson_idx
        await q.edit_message_text(
            "📤 ارسال فیش پرداخت\n\n"
            "یکی از گزینه‌های زیر را ارسال کنید:\n"
            "📸 عکس فیش یا اسکرین‌شات پرداخت\n"
            "📝 متن رسید (حداقل ۵ کلمه)\n\n"
            "⚠️ فایل، صوت، ویدیو و استیکر قابل قبول نیست.",
            reply_markup=mkb([back_btn("courses")]),
        )

    # ===== آمار و گزارش =====
    elif d == "a_stats":
        if not is_admin(user): return
        tot = len(USERS)
        tn = len(normal_users_sorted())
        now = int(time.time())
        ad = sum(
            1 for u in USERS.values()
            if u.get("last_active", 0) >= now - 86400 and u["id"] not in ADMIN_IDS
        )
        aw = sum(
            1 for u in USERS.values()
            if u.get("last_active", 0) >= now - 604800 and u["id"] not in ADMIN_IDS
        )
        ur = sum(1 for t in TICKETS if not t.get("replied"))
        tp_xp = sum(u.get("xp", u.get("points", 0)) for u in USERS.values() if u["id"] not in ADMIN_IDS)
        tp_cr = sum(u.get("credits", 0) for u in USERS.values() if u["id"] not in ADMIN_IDS)
        missions_done = sum(len(u.get("completed_missions", [])) for u in USERS.values())
        await q.edit_message_text(
            f"📊 آمار کلی ربات\n\n👥 کل کاربران: {tot}\n👤 کاربران عادی: {tn}\n"
            f"🟢 فعال امروز: {ad}\n🔵 فعال هفته: {aw}\n"
            f"📬 پیام‌های بی‌پاسخ: {ur}\n"
            f"📈 مجموع XP: {tp_xp}\n💰 مجموع اعتبارها: {tp_cr}\n"
            f"🎯 ماموریت‌های انجام شده: {missions_done}",
            reply_markup=mkb([back_btn("a_reports")]),
        )

    elif d == "a_userlist":
        if not is_admin(user): return
        users = sorted(
            [u for u in USERS.values() if u["id"] not in ADMIN_IDS],
            key=lambda x: x.get("last_active", 0), reverse=True,
        )[:15]
        if not users:
            await q.edit_message_text("هنوز کاربری نیست.", reply_markup=mkb([back_btn("a_reports")]))
            return
        rows = [
            [btn(f"👤 {u.get('first_name', '?')} ({u.get('xp', u.get('points',0))} XP)", f"a_udet|{u['id']}")]
            for u in users
        ]
        rows.append(back_btn("a_reports"))
        await q.edit_message_text("👥 کاربران عادی (۱۵ نفر اخیر):", reply_markup=mkb(rows))

    elif d.startswith("a_udet|"):
        if not is_admin(user): return
        uid = int(d.split("|")[1])
        u = USERS.get(str(uid))
        if not u:
            await q.edit_message_text("کاربر پیدا نشد.", reply_markup=mkb([back_btn("a_userlist")]))
            return
        _migrate_user(u)
        comp, tot, refs = completed_lessons(uid), total_lessons(), valid_refs(uid)
        ago = int(time.time()) - u.get("last_active", 0)
        if ago < 60:
            online = "🟢 آنلاین"
        elif ago < 3600:
            online = f"🟡 {ago // 60} دقیقه پیش"
        elif ago < 86400:
            online = f"🔵 {ago // 3600} ساعت پیش"
        else:
            online = f"⚪ {ago // 86400} روز پیش"
        cd = ""
        for ck, cv in COURSES.items():
            p = PROGRESS.get(str(uid), {}).get(ck, 0)
            cd += f"  📖 {cv['title']}: {p}/{len(cv.get('lessons', []))}\n"
        missions_done = len(u.get("completed_missions", []))
        await q.edit_message_text(
            f"👤 جزئیات کاربر\n\n📛 نام: {u.get('first_name', '?')}\n🆔 شناسه: {uid}\n"
            f"👤 یوزرنیم: @{u.get('username', 'ندارد')}\n{online}\n\n"
            f"📈 XP: {u.get('xp', u.get('points', 0))}\n"
            f"💰 اعتبار: {u.get('credits', 0)}\n"
            f"📚 سرفصل‌ها: {comp}/{tot}\n"
            f"👥 دعوت‌ها: {refs}\n"
            f"🎯 ماموریت‌ها: {missions_done}\n\n"
            f"📊 پیشرفت دوره‌ها:\n{cd if cd else '  شروع نکرده'}",
            reply_markup=mkb([back_btn("a_userlist")]),
        )

    # ===== تیکت‌ها =====
    elif d == "a_tickets":
        if not is_admin(user): return
        # [کار ۱ بند ۳] میان‌بر تنظیم لینک پشتیبانی — مستقیم از پنل پشتیبانی
        sup_rows = [[btn("📞 تنظیم لینک پشتیبانی هر پلتفرم", "a_support_links")]]
        if not TICKETS:
            await q.edit_message_text(
                "📬 پیامی از کاربران دریافت نشده.",
                reply_markup=mkb(sup_rows + [back_btn("a_reports")]),
            )
            return
        rows = []
        for i, t in enumerate(reversed(TICKETS[-10:])):
            idx = len(TICKETS) - 1 - i
            st = "✅" if t.get("replied") else "🔴"
            rows.append([btn(
                f"{st} {t.get('user_name', '?')}: {t.get('text', '')[:20]}...",
                f"a_ticket|{idx}",
            )])
        rows += sup_rows
        rows.append(back_btn("a_reports"))
        await q.edit_message_text("📬 پیام‌های کاربران:", reply_markup=mkb(rows))

    elif d == "a_support_links":
        # [کار ۱ بند ۳] نمای یکجای لینک پشتیبانی همهٔ پلتفرم‌ها
        if not is_admin(user): return
        lines = [
            "📞 لینک پشتیبانی هر پلتفرم",
            "━━━━━━━━━━━━━━━━",
            "",
            "این لینک به کاربرِ همان پلتفرم نشان داده می‌شود:",
            "  • پیام تأیید ارسال تیکت",
            "  • پاسخ تیم پشتیبانی",
            "  • صفحهٔ پشتیبانی و خرید نقدی",
            "",
        ]
        rows = []
        # بله (پلتفرم پایه) — از SUPPORT_GROUP در .env
        lines.append(f"🔵 بله: {SUPPORT_GROUP}  (از فایل .env)")
        for p in SECONDARY_PLATFORMS:
            raw = str(SETTINGS.get(f"{p}_support", "") or "").strip()
            shown = raw if raw else f"پیش‌فرض ← {SUPPORT_GROUP}"
            mark = "✅" if raw else "⚠️"
            lines.append(f"{mark} {platform_name(p)}: {shown}")
            rows.append([btn(f"✏️ ویرایش پشتیبانی {platform_name(p)}", f"a_plat_support|{p}")])
        lines += [
            "",
            "ℹ️ اگر برای پلتفرمی چیزی ثبت نشود، همان لینک بله استفاده می‌شود.",
        ]
        rows.append(back_btn("a_tickets"))
        await q.edit_message_text("\n".join(lines), reply_markup=mkb(rows))

    elif d.startswith("a_ticket|"):
        if not is_admin(user): return
        idx = int(d.split("|")[1])
        if idx < 0 or idx >= len(TICKETS):
            return
        t = TICKETS[idx]
        text = (
            f"📬 پیام #{idx+1}\n\n👤 فرستنده: {t.get('user_name', '?')}\n"
            f"🆔 شناسه Canonical: {t.get('canonical_user_id') or t.get('user_id')}\n"
            f"💬 Chat ID: {t.get('chat_id') or '---'}\n"
            f"🌐 پلتفرم: {platform_name(t.get('platform') or 'bale')}\n\n"
            f"📝 متن پیام:\n{t.get('text', '')}\n\n"
            f"وضعیت: {'✅ پاسخ داده شده' if t.get('replied') else '🔴 بدون پاسخ'}"
        )
        if t.get("reply_text"):
            text += f"\n\n💬 پاسخ شما:\n{t['reply_text']}"
        await q.edit_message_text(
            text,
            reply_markup=mkb([[btn("💬 ارسال پاسخ", f"a_reply|{idx}")], back_btn("a_tickets")]),
        )

    elif d.startswith("a_reply|"):
        if not is_admin(user): return
        ctx.user_data["state"] = "wait_ticket_reply"
        ctx.user_data["reply_idx"] = int(d.split("|")[1])
        await q.edit_message_text(
            "💬 پاسخ خود را بنویسید و ارسال کنید:",
            reply_markup=mkb([back_btn("a_tickets")]),
        )

    # ===== مدیریت ماموریت‌ها =====
    elif d == "a_missions":
        if not is_admin(user): return
        await a_missions_panel(q)

    elif d == "a_mission_add":
        if not is_admin(user): return
        ctx.user_data["state"] = "wait_mission_title"
        ctx.user_data.pop("mission_building", None)
        await q.edit_message_text(
            "🎯 ثبت ماموریت جدید\n\n"
            "محدودیت امتیاز رشد:\n"
            "  📝 متنی: ۱ تا ۲۰ XP\n"
            "  🖼 تصویری: ۲۰ تا ۵۰ XP\n"
            "  🎬 ویدیویی: ۵۰ تا ۱۰۰ XP\n\n"
            "ابتدا عنوان ماموریت را بنویسید:",
            reply_markup=mkb([back_btn("a_missions")]),
        )

    elif d.startswith("a_mission_view|"):
        if not is_admin(user): return
        mid = d.split("|", 1)[1]
        mission = next((m for m in MISSIONS if m.get("id") == mid), None)
        if not mission:
            await safe_answer(q, "❌ ماموریت پیدا نشد.", True)
            return
        mtype = mission.get("type", "text")
        type_icon = {"text": "📝", "photo": "🖼", "video": "🎬"}.get(mtype, "📌")
        st = "✅ فعال" if mission.get("active", True) else "❌ غیرفعال"
        # تعداد انجام‌دهندگان
        done_count = sum(
            1 for u in USERS.values()
            if mid in u.get("completed_missions", [])
        )
        await q.edit_message_text(
            f"🎯 جزئیات ماموریت\n\n"
            f"{type_icon} {mission.get('title', '')}\n"
            f"📝 توضیحات: {mission.get('description', '')[:50]}\n"
            f"🎁 XP: +{mission.get('xp_reward', 0)} | اعتبار: +{mission.get('credits_reward', 0)}\n"
            f"📊 وضعیت: {st}\n"
            f"👥 تعداد انجام‌دهندگان: {done_count} نفر",
            reply_markup=mkb([
                [btn("🔄 فعال/غیرفعال", f"a_mission_toggle|{mid}"),
                 btn("🗑 حذف", f"a_mission_del|{mid}")],
                back_btn("a_missions"),
            ]),
        )

    elif d.startswith("a_mission_toggle|"):
        if not is_admin(user): return
        mid = d.split("|", 1)[1]
        mission = next((m for m in MISSIONS if m.get("id") == mid), None)
        if mission:
            mission["active"] = not mission.get("active", True)
            save("missions")
            await safe_answer(q, "✅ وضعیت تغییر کرد.")
        await a_missions_panel(q)

    elif d.startswith("a_mission_del_yes|"):
        # [باگ ۳] حذف واقعی ماموریت — فقط بعد از تایید
        if not is_admin(user): return
        mid = d.split("|", 1)[1]
        title = next((m.get("title", mid) for m in MISSIONS if m.get("id") == mid), mid)
        original_len = len(MISSIONS)
        MISSIONS[:] = [m for m in MISSIONS if m.get("id") != mid]
        if len(MISSIONS) < original_len:
            save("missions")
            logger.info("🗑 ادمین %s ماموریت «%s» (%s) را حذف کرد.", user.id, title, mid)
            await safe_answer(q, "✅ ماموریت حذف شد.")
        await a_missions_panel(q)

    elif d.startswith("a_mission_del|"):
        # [باگ ۳] مرحلهٔ تایید حذف ماموریت
        if not is_admin(user): return
        mid = d.split("|", 1)[1]
        m = next((x for x in MISSIONS if x.get("id") == mid), None)
        if not m:
            await safe_answer(q, "❌ ماموریت پیدا نشد.", True)
            return
        await q.edit_message_text(
            _confirm_text(
                f"🎯 ماموریت: «{m.get('title', mid)}»",
                f"🎁 پاداش: {fa_num(m.get('xp_reward', 0))} XP | "
                f"{fa_num(m.get('credits_reward', 0))} اعتبار",
            ),
            reply_markup=_confirm_kb(f"a_mission_del_yes|{mid}", f"a_mission_view|{mid}"),
        )

    elif d.startswith("a_mission_type|"):
        if not is_admin(user): return
        mtype = d.split("|", 1)[1]
        ctx.user_data.setdefault("mission_building", {})["type"] = mtype
        if mtype == "platform_link":
            # ابتدا پلتفرم مقصد انتخاب شود
            await q.edit_message_text(
                "🔗 ماموریت اتصال پلتفرم\n\nپلتفرم مقصد را انتخاب کنید:",
                reply_markup=mkb(
                    [[btn(platform_name(p), f"a_mission_plat|{p}")] for p in SECONDARY_PLATFORMS]
                    + [back_btn("a_missions")]
                ),
            )
            return
        mn, mx = MISSION_XP_LIMITS.get(mtype, (1, 100))
        type_icon = {"text": "📝", "photo": "🖼", "video": "🎬"}.get(mtype, "📌")
        ctx.user_data["state"] = "wait_mission_xp"
        await q.edit_message_text(
            f"✅ نوع: {type_icon} {'متنی' if mtype=='text' else 'تصویری' if mtype=='photo' else 'ویدیویی'}\n\n"
            f"حالا مقدار XP پاداش را بفرستید (بین {mn} تا {mx}):",
            reply_markup=mkb([back_btn("a_missions")]),
        )

    elif d.startswith("a_mission_plat|"):
        if not is_admin(user): return
        p = d.split("|", 1)[1]
        mb = ctx.user_data.setdefault("mission_building", {})
        mb["type"] = "platform_link"
        mb["target_platform"] = p
        mn, mx = MISSION_XP_LIMITS.get("platform_link", (1, 100))
        ctx.user_data["state"] = "wait_mission_xp"
        await q.edit_message_text(
            f"✅ نوع: 🔗 اتصال به {platform_name(p)}\n\n"
            f"حالا مقدار XP پاداش را بفرستید (بین {mn} تا {mx}):",
            reply_markup=mkb([back_btn("a_missions")]),
        )

    # ===== مدیریت دوره‌ها =====
    elif d == "a_manage":
        if not is_admin(user): return
        if not COURSES:
            await q.edit_message_text(
                "هنوز دوره‌ای ساخته نشده.",
                reply_markup=mkb([back_btn("a_courses_menu")]),
            )
            return
        rows = [[btn(f"✏️ {v['title']}", f"a_open|{k}")] for k, v in COURSES.items()]
        rows.append(back_btn("a_courses_menu"))
        await q.edit_message_text("🗂 کدام دوره را ویرایش می‌کنید؟", reply_markup=mkb(rows))

    elif d == "a_dellist":
        if not is_admin(user): return
        if not COURSES:
            await q.edit_message_text("دوره‌ای نیست.", reply_markup=mkb([back_btn("a_courses_menu")]))
            return
        rows = [[btn(f"❌ {v['title']}", f"a_del|{k}")] for k, v in COURSES.items()]
        rows.append(back_btn("a_courses_menu"))
        await q.edit_message_text("❌ کدام دوره حذف شود؟", reply_markup=mkb(rows))

    elif d == "a_addcourse":
        if not is_admin(user): return
        ctx.user_data["state"] = "wait_course_title"
        await q.edit_message_text(
            "➕ ساخت دوره جدید\n\nعنوان دوره را بنویسید و ارسال کنید:",
            reply_markup=mkb([back_btn("a_courses_menu")]),
        )

    elif d.startswith("a_del_yes|"):
        # [باگ ۳] حذف واقعی دوره — فقط بعد از تایید
        if not is_admin(user): return
        cid = d.split("|", 1)[1]
        title = COURSES.pop(cid, {}).get("title", cid)
        save("courses")
        logger.info("🗑 ادمین %s دوره «%s» (%s) را حذف کرد.", user.id, title, cid)
        await q.edit_message_text(
            f"✅ دوره «{title}» با موفقیت حذف شد.",
            reply_markup=mkb([back_btn("a_courses_menu")]),
        )

    elif d.startswith("a_del|"):
        # [باگ ۳] مرحلهٔ تایید — حذف واقعی در a_del_yes انجام می‌شود
        if not is_admin(user): return
        cid = d.split("|")[1]
        c = COURSES.get(cid)
        if not c:
            await safe_answer(q, "❌ دوره پیدا نشد.", True)
            return
        n_les = len(c.get("lessons", []))
        await q.edit_message_text(
            _confirm_text(
                f"📖 دوره: «{c.get('title', cid)}»",
                f"📚 شامل {fa_num(n_les)} سرفصل — همه حذف خواهند شد.",
            ),
            reply_markup=_confirm_kb(f"a_del_yes|{cid}", f"a_open|{cid}"),
        )

    elif d.startswith("a_open|"):
        if not is_admin(user): return
        cid = d.split("|")[1]
        c = COURSES.get(cid)
        if not c:
            return
        ls, rj, rr = c.get("lessons", []), c.get("required_joins", []), c.get("referral_required", 0)
        rc = c.get("required_credits", 0)
        text = (
            f"📘 مدیریت دوره: {c['title']}\n\n"
            f"📝 توضیحات: {c.get('description') or 'تنظیم نشده'}\n"
            f"📚 تعداد سرفصل‌ها: {len(ls)}\n"
            f"🔒 عضویت اجباری: {', '.join(rj) if rj else 'ندارد'}\n"
            f"👥 دعوت اجباری: {rr} نفر\n"
            f"💰 اعتبار اجباری: {rc}\n\n"
        )
        if ls:
            text += "📋 سرفصل‌ها:\n"
            for i, l in enumerate(ls):
                text += f"  {i+1}. {l['title']} ({ltype(l.get('type'))})\n"
        await q.edit_message_text(text, reply_markup=mkb([
            [btn("✏️ ویرایش عنوان", f"a_ctitle|{cid}"),
             btn("📝 ویرایش توضیحات", f"a_cdesc|{cid}")],
            [btn("🔒 عضویت اجباری", f"a_cjoin|{cid}"),
             btn("👥 دعوت اجباری", f"a_cref|{cid}")],
            [btn("💰 اعتبار اجباری", f"a_ccredit|{cid}")],
            [btn("💵 تنظیم فروش نقدی", f"a_cash_sale_setting|course|{cid}")],
            [btn("📚 مدیریت سرفصل‌ها", f"a_lessons|{cid}"),
             btn("➕ سرفصل جدید", f"a_addl|{cid}")],
            [btn("📊 نظرسنجی", f"a_toggle_survey|{cid}")],
            back_btn("a_courses_menu"),
        ]))

    elif d.startswith("a_ctitle|"):
        if not is_admin(user): return
        cid = d.split("|")[1]
        ctx.user_data["state"] = "wait_ctitle"
        ctx.user_data["ecid"] = cid
        await q.edit_message_text(
            f"✏️ ویرایش عنوان دوره\n\nعنوان فعلی: {COURSES.get(cid, {}).get('title', '')}\n\nعنوان جدید:",
            reply_markup=mkb([back_btn(f"a_open|{cid}")]),
        )

    elif d.startswith("a_cdesc|"):
        if not is_admin(user): return
        cid = d.split("|")[1]
        ctx.user_data["state"] = "wait_cdesc"
        ctx.user_data["ecid"] = cid
        await q.edit_message_text(
            f"📝 ویرایش توضیحات دوره\n\nتوضیحات جدید:",
            reply_markup=mkb([back_btn(f"a_open|{cid}")]),
        )

    elif d.startswith("a_cjoin|"):
        if not is_admin(user): return
        cid = d.split("|")[1]
        ctx.user_data["state"] = "wait_cjoin"
        ctx.user_data["ecid"] = cid
        rj = COURSES.get(cid, {}).get("required_joins", [])
        await q.edit_message_text(
            f"🔒 عضویت اجباری دوره\n\nفعلی: {', '.join(rj) if rj else 'ندارد'}\n\n"
            f"آیدی کانال‌ها (هر خط یکی):\nبرای حذف: حذف",
            reply_markup=mkb([back_btn(f"a_open|{cid}")]),
        )

    elif d.startswith("a_cref|"):
        if not is_admin(user): return
        cid = d.split("|")[1]
        ctx.user_data["state"] = "wait_cref"
        ctx.user_data["ecid"] = cid
        rr = COURSES.get(cid, {}).get("referral_required", 0)
        await q.edit_message_text(
            f"👥 دعوت اجباری دوره\n\nفعلی: {rr} نفر\n\nعدد جدید (0 = غیرفعال):",
            reply_markup=mkb([back_btn(f"a_open|{cid}")]),
        )

    elif d.startswith("a_ccredit|"):
        if not is_admin(user): return
        cid = d.split("|")[1]
        ctx.user_data["state"] = "wait_ccredit"
        ctx.user_data["ecid"] = cid
        rc = COURSES.get(cid, {}).get("required_credits", 0)
        await q.edit_message_text(
            f"💰 اعتبار اجباری دوره\n\nفعلی: {rc}\n\n"
            f"حداقل اعتبار لازم برای دسترسی (0 = غیرفعال):",
            reply_markup=mkb([back_btn(f"a_open|{cid}")]),
        )

    # ===== تنظیم فروش نقدی (ادمین) =====

    elif d.startswith("a_cash_sale_setting|"):
        if not is_admin(user): return
        parts = d.split("|")
        # a_cash_sale_setting|course|{cid}  یا  a_cash_sale_setting|lesson|{cid}|{idx}
        target_type = parts[1] if len(parts) > 1 else "course"
        idx = 0
        if target_type == "course":
            cid = parts[2] if len(parts) > 2 else ""
            c = COURSES.get(cid)
            if not c:
                await safe_answer(q, "❌ دوره پیدا نشد.", True)
                return
            target_id = cid
            title_txt = c.get("title", "")
            back_cb = f"a_open|{cid}"
        else:
            cid = parts[2] if len(parts) > 2 else ""
            idx = int(parts[3]) if len(parts) > 3 else 0
            ls = COURSES.get(cid, {}).get("lessons", [])
            if idx >= len(ls):
                await safe_answer(q, "❌ سرفصل پیدا نشد.", True)
                return
            lesson = ls[idx]
            target_id = lesson.get("lid", str(idx))
            title_txt = lesson.get("title", "")
            back_cb = f"a_lmenu|{cid}|{idx}"
        setting = CASH_SALE_SETTINGS.get(f"{target_type}|{target_id}", {})
        enabled = setting.get("enabled", False)
        amount = setting.get("amount", 0)
        card_number = setting.get("card_number", "")
        card_holder = setting.get("card_holder", "")
        bank_name = setting.get("bank_name", "")
        display_note = setting.get("display_note", "")
        status_txt = "✅ فعال" if enabled else "❌ غیرفعال"
        card_txt = format_card_admin(card_number, card_holder, bank_name)
        xp_reward = setting.get("xp_reward", 0)
        credits_reward = setting.get("credits_reward", 0)
        idx_suffix = f"|{idx}" if target_type == "lesson" else ""
        text = (
            f"💵 تنظیم فروش نقدی\n\n"
            f"{'📚 دوره' if target_type == 'course' else '📖 سرفصل'}: {title_txt}\n\n"
            f"📊 وضعیت: {status_txt}\n"
            f"💰 مبلغ: {amount:,} تومان\n"
            f"💳 اطلاعات کارت: {card_txt}\n"
            f"📝 توضیحات: {display_note or 'ندارد'}\n"
            f"🎁 جایزه XP: {xp_reward} XP\n"
            f"💎 جایزه اعتبار: {credits_reward} اعتبار\n\n"
            f"ℹ️ آیتم نقدی همیشه هم در دوره/سرفصل و هم در گنجینه نمایش داده می‌شود."
        )
        await q.edit_message_text(text, reply_markup=mkb([
            [btn(f"🔄 {'غیرفعال' if enabled else 'فعال'} کردن",
                 f"a_cst_toggle|{target_type}|{target_id}|{cid}{idx_suffix}")],
            [btn("💰 تنظیم مبلغ",
                 f"a_cst_price|{target_type}|{target_id}|{cid}{idx_suffix}")],
            [btn("💳 اطلاعات کارت",
                 f"a_cst_method|{target_type}|{target_id}|{cid}{idx_suffix}")],
            [btn("📝 توضیحات نمایشی",
                 f"a_cst_note|{target_type}|{target_id}|{cid}{idx_suffix}")],
            [btn(f"🎁 جایزه XP ({xp_reward})",
                 f"a_cst_xpreward|{target_type}|{target_id}|{cid}{idx_suffix}"),
             btn(f"💎 جایزه اعتبار ({credits_reward})",
                 f"a_cst_creditreward|{target_type}|{target_id}|{cid}{idx_suffix}")],
            back_btn(back_cb),
        ]))

    elif d.startswith("a_lcash|"):
        if not is_admin(user): return
        parts = d.split("|")
        cid, idx = parts[1], int(parts[2])
        ls = COURSES.get(cid, {}).get("lessons", [])
        if idx >= len(ls):
            await safe_answer(q, "❌ سرفصل پیدا نشد.", True)
            return
        lesson = ls[idx]
        target_id = lesson.get("lid", str(idx))
        setting = CASH_SALE_SETTINGS.get(f"lesson|{target_id}", {})
        enabled = setting.get("enabled", False)
        amount = setting.get("amount", 0)
        card_number = setting.get("card_number", "")
        card_holder = setting.get("card_holder", "")
        bank_name = setting.get("bank_name", "")
        display_note = setting.get("display_note", "")
        xp_reward = setting.get("xp_reward", 0)
        credits_reward = setting.get("credits_reward", 0)
        status_txt = "✅ فعال" if enabled else "❌ غیرفعال"
        card_txt = format_card_admin(card_number, card_holder, bank_name)
        text = (
            f"💵 تنظیم فروش نقدی سرفصل\n\n"
            f"📖 سرفصل: {lesson.get('title', '')}\n\n"
            f"📊 وضعیت: {status_txt}\n"
            f"💰 مبلغ: {amount:,} تومان\n"
            f"💳 اطلاعات کارت: {card_txt}\n"
            f"📝 توضیحات: {display_note or 'ندارد'}\n"
            f"🎁 جایزه XP: {xp_reward} XP\n"
            f"💎 جایزه اعتبار: {credits_reward} اعتبار\n\n"
            f"ℹ️ آیتم نقدی همیشه هم در دوره/سرفصل و هم در گنجینه نمایش داده می‌شود."
        )
        await q.edit_message_text(text, reply_markup=mkb([
            [btn(f"🔄 {'غیرفعال' if enabled else 'فعال'} کردن",
                 f"a_cst_toggle|lesson|{target_id}|{cid}|{idx}")],
            [btn("💰 تنظیم مبلغ", f"a_cst_price|lesson|{target_id}|{cid}|{idx}")],
            [btn("💳 اطلاعات کارت", f"a_cst_method|lesson|{target_id}|{cid}|{idx}")],
            [btn("📝 توضیحات نمایشی", f"a_cst_note|lesson|{target_id}|{cid}|{idx}")],
            [btn(f"🎁 جایزه XP ({xp_reward})", f"a_cst_xpreward|lesson|{target_id}|{cid}|{idx}"),
             btn(f"💎 جایزه اعتبار ({credits_reward})", f"a_cst_creditreward|lesson|{target_id}|{cid}|{idx}")],
            back_btn(f"a_lmenu|{cid}|{idx}"),
        ]))

    elif d.startswith("a_cst_toggle|"):
        if not is_admin(user): return
        parts = d.split("|")
        target_type = parts[1]
        target_id = parts[2]
        cid = parts[3] if len(parts) > 3 else ""
        idx = int(parts[4]) if len(parts) > 4 else 0
        key = f"{target_type}|{target_id}"
        current = CASH_SALE_SETTINGS.get(key, {})
        new_enabled = not current.get("enabled", False)
        set_cash_sale_setting(
            target_type, target_id, new_enabled,
            current.get("amount", 0),
            current.get("payment_method", ""),
            current.get("display_note", ""),
            current.get("display_place", "course"),
            current.get("xp_reward", 0),
            current.get("credits_reward", 0),
        )
        await safe_answer(q, f"✅ فروش نقدی {'فعال' if new_enabled else 'غیرفعال'} شد.")
        if target_type == "course":
            back_cb = f"a_cash_sale_setting|course|{cid}"
        else:
            back_cb = f"a_cash_sale_setting|lesson|{cid}|{idx}"
        await q.edit_message_text(
            f"💵 فروش نقدی: {'✅ فعال' if new_enabled else '❌ غیرفعال'}\n\nبازگشت برای تنظیمات بیشتر:",
            reply_markup=mkb([back_btn(back_cb)]),
        )

    elif d.startswith("a_cst_price|"):
        if not is_admin(user): return
        parts = d.split("|")
        target_type = parts[1]
        target_id = parts[2]
        cid = parts[3] if len(parts) > 3 else ""
        idx = int(parts[4]) if len(parts) > 4 else 0
        ctx.user_data["state"] = "wait_cash_sale_price"
        ctx.user_data["cst_target_type"] = target_type
        ctx.user_data["cst_target_id"] = target_id
        ctx.user_data["cst_cid"] = cid
        ctx.user_data["cst_idx"] = idx
        cur = CASH_SALE_SETTINGS.get(f"{target_type}|{target_id}", {}).get("amount", 0)
        back_cb = f"a_cash_sale_setting|{target_type}|{cid}" + (f"|{idx}" if target_type == "lesson" else "")
        await q.edit_message_text(
            f"💰 تنظیم مبلغ فروش نقدی\n\nمبلغ فعلی: {cur:,} تومان\n\nمبلغ جدید را بفرستید (عدد — تومان):\n(0 = تماس با پشتیبانی)",
            reply_markup=mkb([back_btn(back_cb)]),
        )

    elif d.startswith("a_cst_method|"):
        if not is_admin(user): return
        parts = d.split("|")
        target_type = parts[1]
        target_id = parts[2]
        cid = parts[3] if len(parts) > 3 else ""
        idx = int(parts[4]) if len(parts) > 4 else 0
        ctx.user_data["state"] = "wait_cash_card_number"
        ctx.user_data["cst_target_type"] = target_type
        ctx.user_data["cst_target_id"] = target_id
        ctx.user_data["cst_cid"] = cid
        ctx.user_data["cst_idx"] = idx
        cur = CASH_SALE_SETTINGS.get(f"{target_type}|{target_id}", {}).get("card_number", "")
        back_cb = f"a_cash_sale_setting|{target_type}|{cid}" + (f"|{idx}" if target_type == "lesson" else "")
        cur_txt = format_card_number(cur) if cur else "تنظیم نشده"
        await q.edit_message_text(
            f"💳 ثبت اطلاعات کارت (مرحله ۱ از ۳)\n\n"
            f"شماره کارت فعلی: {cur_txt}\n\n"
            "شماره کارت ۱۶ رقمی را بفرستید:\n(می‌توانید با فاصله یا خط تیره بنویسید)",
            reply_markup=mkb([back_btn(back_cb)]),
        )

    elif d.startswith("a_cst_note|"):
        if not is_admin(user): return
        parts = d.split("|")
        target_type = parts[1]
        target_id = parts[2]
        cid = parts[3] if len(parts) > 3 else ""
        idx = int(parts[4]) if len(parts) > 4 else 0
        ctx.user_data["state"] = "wait_cash_sale_note"
        ctx.user_data["cst_target_type"] = target_type
        ctx.user_data["cst_target_id"] = target_id
        ctx.user_data["cst_cid"] = cid
        ctx.user_data["cst_idx"] = idx
        cur = CASH_SALE_SETTINGS.get(f"{target_type}|{target_id}", {}).get("display_note", "")
        back_cb = f"a_cash_sale_setting|{target_type}|{cid}" + (f"|{idx}" if target_type == "lesson" else "")
        await q.edit_message_text(
            f"📝 توضیحات نمایشی\n\nفعلی: {cur or 'ندارد'}\n\nتوضیحات جدید را بفرستید:\n(برای حذف: حذف)",
            reply_markup=mkb([back_btn(back_cb)]),
        )

    elif d.startswith("a_cst_xpreward|"):
        if not is_admin(user): return
        parts = d.split("|")
        target_type = parts[1]
        target_id = parts[2]
        cid = parts[3] if len(parts) > 3 else ""
        idx = int(parts[4]) if len(parts) > 4 else 0
        ctx.user_data["state"] = "wait_cash_sale_xpreward"
        ctx.user_data["cst_target_type"] = target_type
        ctx.user_data["cst_target_id"] = target_id
        ctx.user_data["cst_cid"] = cid
        ctx.user_data["cst_idx"] = idx
        cur_xp = CASH_SALE_SETTINGS.get(f"{target_type}|{target_id}", {}).get("xp_reward", 0)
        back_cb = f"a_cash_sale_setting|{target_type}|{cid}" + (f"|{idx}" if target_type == "lesson" else "")
        await q.edit_message_text(
            f"🎁 تنظیم جایزه XP\n\nفعلی: {cur_xp} XP\n\nمقدار جدید را بفرستید (عدد — XP):\n(0 = بدون جایزه)",
            reply_markup=mkb([back_btn(back_cb)]),
        )

    elif d.startswith("a_cst_creditreward|"):
        if not is_admin(user): return
        parts = d.split("|")
        target_type = parts[1]
        target_id = parts[2]
        cid = parts[3] if len(parts) > 3 else ""
        idx = int(parts[4]) if len(parts) > 4 else 0
        ctx.user_data["state"] = "wait_cash_sale_creditreward"
        ctx.user_data["cst_target_type"] = target_type
        ctx.user_data["cst_target_id"] = target_id
        ctx.user_data["cst_cid"] = cid
        ctx.user_data["cst_idx"] = idx
        cur_cr = CASH_SALE_SETTINGS.get(f"{target_type}|{target_id}", {}).get("credits_reward", 0)
        back_cb = f"a_cash_sale_setting|{target_type}|{cid}" + (f"|{idx}" if target_type == "lesson" else "")
        await q.edit_message_text(
            f"💎 تنظیم جایزه اعتبار\n\nفعلی: {cur_cr} اعتبار\n\nمقدار جدید را بفرستید (عدد — اعتبار):\n(0 = بدون جایزه)",
            reply_markup=mkb([back_btn(back_cb)]),
        )

    elif d.startswith("a_addl|"):
        if not is_admin(user): return
        cid = d.split("|")[1]
        ctx.user_data["state"] = "wait_ltitle"
        ctx.user_data["ecid"] = cid
        await q.edit_message_text(
            f"➕ سرفصل جدید برای دوره «{COURSES.get(cid, {}).get('title', '')}»\n\nعنوان سرفصل:",
            reply_markup=mkb([back_btn(f"a_open|{cid}")]),
        )

    elif d.startswith("a_lessons|"):
        if not is_admin(user): return
        cid = d.split("|")[1]
        c = COURSES.get(cid, {})
        ls = c.get("lessons", [])
        if not ls:
            await q.edit_message_text(
                f"📚 دوره «{c.get('title', '')}» سرفصلی ندارد.",
                reply_markup=mkb([[btn("➕ سرفصل جدید", f"a_addl|{cid}")], back_btn(f"a_open|{cid}")]),
            )
            return
        rows = [
            [btn(f"{i+1}. {l['title']} ({ltype(l.get('type'))})", f"a_lmenu|{cid}|{i}")]
            for i, l in enumerate(ls)
        ]
        rows.append([btn("➕ سرفصل جدید", f"a_addl|{cid}")])
        rows.append([btn("🗑 حذف همه سرفصل‌ها", f"a_clearl|{cid}")])
        rows.append(back_btn(f"a_open|{cid}"))
        await q.edit_message_text(
            f"📚 سرفصل‌های دوره «{c.get('title', '')}»:", reply_markup=mkb(rows)
        )

    elif d.startswith("a_lmenu|"):
        if not is_admin(user): return
        parts = d.split("|")
        cid, idx = parts[1], int(parts[2])
        c = COURSES.get(cid, {})
        ls = c.get("lessons", [])
        if idx >= len(ls):
            return
        l = ls[idx]
        lc = l.get("required_credits", 0)
        await q.edit_message_text(
            f"📌 سرفصل {idx+1}: {l['title']}\n"
            f"نوع: {ltype(l.get('type'))}\n"
            f"💰 اعتبار اجباری: {lc}",
            reply_markup=lesson_menu_kb(cid, idx),
        )

    elif d.startswith("a_lt|"):
        if not is_admin(user): return
        parts = d.split("|")
        cid, idx = parts[1], int(parts[2])
        ctx.user_data["state"] = "wait_lt_edit"
        ctx.user_data["ecid"] = cid
        ctx.user_data["eidx"] = idx
        await q.edit_message_text(
            "✏️ عنوان جدید سرفصل:",
            reply_markup=mkb([back_btn(f"a_lmenu|{cid}|{idx}")]),
        )

    elif d.startswith("a_ls|"):
        if not is_admin(user): return
        parts = d.split("|")
        cid, idx = parts[1], int(parts[2])
        c = COURSES.get(cid, {})
        ls = c.get("lessons", [])
        if idx >= len(ls):
            return
        l = ls[idx]
        set_src(ctx, "edit", cid, l["title"], idx)
        ctx.user_data["state"] = "choose_type"
        await q.edit_message_text(
            f"🔁 تغییر منبع سرفصل: {l['title']}\n\nنوع جدید را انتخاب کنید:",
            reply_markup=src_kb(f"a_lmenu|{cid}|{idx}"),
        )

    elif d.startswith("a_ljoin|"):
        if not is_admin(user): return
        parts = d.split("|")
        cid, idx = parts[1], int(parts[2])
        ctx.user_data["state"] = "wait_ljoin"
        ctx.user_data["ecid"] = cid
        ctx.user_data["eidx"] = idx
        lj = COURSES.get(cid, {}).get("lessons", [])[idx].get("required_joins", [])
        await q.edit_message_text(
            f"🔒 عضویت اجباری سرفصل\n\nفعلی: {', '.join(lj) if lj else 'ندارد'}\n\n"
            f"آیدی کانال‌ها (هر خط یکی):\nبرای حذف: حذف",
            reply_markup=mkb([back_btn(f"a_lmenu|{cid}|{idx}")]),
        )

    elif d.startswith("a_lref|"):
        if not is_admin(user): return
        parts = d.split("|")
        cid, idx = parts[1], int(parts[2])
        ctx.user_data["state"] = "wait_lref"
        ctx.user_data["ecid"] = cid
        ctx.user_data["eidx"] = idx
        lr = COURSES.get(cid, {}).get("lessons", [])[idx].get("referral_required", 0)
        await q.edit_message_text(
            f"👥 دعوت اجباری سرفصل\n\nفعلی: {lr} نفر\n\nعدد جدید (0 = غیرفعال):",
            reply_markup=mkb([back_btn(f"a_lmenu|{cid}|{idx}")]),
        )

    elif d.startswith("a_lcredit|"):
        if not is_admin(user): return
        parts = d.split("|")
        cid, idx = parts[1], int(parts[2])
        ctx.user_data["state"] = "wait_lcredit"
        ctx.user_data["ecid"] = cid
        ctx.user_data["eidx"] = idx
        lc = COURSES.get(cid, {}).get("lessons", [])[idx].get("required_credits", 0)
        await q.edit_message_text(
            f"💰 اعتبار اجباری سرفصل\n\nفعلی: {lc}\n\n"
            f"حداقل اعتبار لازم (0 = غیرفعال):",
            reply_markup=mkb([back_btn(f"a_lmenu|{cid}|{idx}")]),
        )

    elif d.startswith("a_ldel_yes|"):
        # [باگ ۳] حذف واقعی سرفصل — فقط بعد از تایید
        if not is_admin(user): return
        parts = d.split("|")
        cid, idx = parts[1], int(parts[2])
        lessons = COURSES.get(cid, {}).get("lessons", [])
        if 0 <= idx < len(lessons):
            removed = lessons.pop(idx)
            save("courses")
            logger.info("🗑 ادمین %s سرفصل «%s» از دوره %s را حذف کرد.",
                        user.id, removed.get("title", idx), cid)
            await safe_answer(q, f"✅ سرفصل «{removed['title']}» حذف شد.")
        await q.edit_message_text(
            f"📚 سرفصل‌های دوره «{COURSES.get(cid, {}).get('title', '')}»:",
            reply_markup=mkb(
                [[btn(f"{i+1}. {l['title']}", f"a_lmenu|{cid}|{i}")] for i, l in enumerate(COURSES.get(cid, {}).get("lessons", []))]
                + [[btn("➕ سرفصل جدید", f"a_addl|{cid}")], back_btn(f"a_open|{cid}")]
            ),
        )

    elif d.startswith("a_ldel|"):
        # [باگ ۳] مرحلهٔ تایید حذف سرفصل
        if not is_admin(user): return
        parts = d.split("|")
        cid, idx = parts[1], int(parts[2])
        lessons = COURSES.get(cid, {}).get("lessons", [])
        if not (0 <= idx < len(lessons)):
            await safe_answer(q, "❌ سرفصل پیدا نشد.", True)
            return
        await q.edit_message_text(
            _confirm_text(f"📝 سرفصل: «{lessons[idx].get('title', idx)}»"),
            reply_markup=_confirm_kb(f"a_ldel_yes|{cid}|{idx}", f"a_lmenu|{cid}|{idx}"),
        )

    elif d.startswith("a_lup|"):
        if not is_admin(user): return
        parts = d.split("|")
        cid, idx = parts[1], int(parts[2])
        ls = COURSES.get(cid, {}).get("lessons", [])
        if idx > 0:
            ls[idx], ls[idx-1] = ls[idx-1], ls[idx]
            save("courses")
            await safe_answer(q, "⬆️ جابجا شد.")
        await q.edit_message_text(
            f"📌 سرفصل {idx}: {ls[idx-1]['title'] if idx > 0 else ''}",
            reply_markup=lesson_menu_kb(cid, max(0, idx-1)),
        )

    elif d.startswith("a_ldn|"):
        if not is_admin(user): return
        parts = d.split("|")
        cid, idx = parts[1], int(parts[2])
        ls = COURSES.get(cid, {}).get("lessons", [])
        if idx < len(ls) - 1:
            ls[idx], ls[idx+1] = ls[idx+1], ls[idx]
            save("courses")
            await safe_answer(q, "⬇️ جابجا شد.")
        await q.edit_message_text(
            f"📌 سرفصل {idx+2}: {ls[min(idx+1, len(ls)-1)]['title']}",
            reply_markup=lesson_menu_kb(cid, min(idx+1, len(ls)-1)),
        )

    elif d.startswith("a_clearl_yes|"):
        # [باگ ۳] حذف واقعی همهٔ سرفصل‌ها — فقط بعد از تایید
        if not is_admin(user): return
        cid = d.split("|", 1)[1]
        n = len(COURSES.get(cid, {}).get("lessons", []))
        COURSES.get(cid, {})["lessons"] = []
        save("courses")
        logger.info("🗑 ادمین %s همهٔ %d سرفصل دوره %s را حذف کرد.", user.id, n, cid)
        await q.edit_message_text(
            f"✅ همه سرفصل‌ها حذف شدند. ({fa_num(n)} مورد)",
            reply_markup=mkb([back_btn(f"a_open|{cid}")]),
        )

    elif d.startswith("a_clearl|"):
        # [باگ ۳] مرحلهٔ تایید — خطرناک‌ترین حذف
        if not is_admin(user): return
        cid = d.split("|")[1]
        c = COURSES.get(cid, {})
        n = len(c.get("lessons", []))
        if n == 0:
            await safe_answer(q, "این دوره سرفصلی ندارد.", True)
            return
        await q.edit_message_text(
            _confirm_text(
                f"🗑 حذف «همهٔ» سرفصل‌های دوره «{c.get('title', cid)}»",
                f"📚 تعداد: {fa_num(n)} سرفصل",
            ),
            reply_markup=_confirm_kb(f"a_clearl_yes|{cid}", f"a_open|{cid}"),
        )

    # ===== منبع سرفصل =====
    elif d.startswith("src|"):
        if not is_admin(user): return
        src_type = d.split("|")[1]
        s = get_src(ctx)
        if not s:
            return
        back_cb = src_back(ctx)
        if src_type == "text":
            ctx.user_data["state"] = "wait_src_text"
            await q.edit_message_text("📝 متن سرفصل را بفرستید:", reply_markup=mkb([back_btn(back_cb)]))
        elif src_type == "link":
            ctx.user_data["state"] = "wait_src_link"
            await q.edit_message_text("🔗 لینک سرفصل را بفرستید:", reply_markup=mkb([back_btn(back_cb)]))
        elif src_type == "file":
            ctx.user_data["state"] = "wait_src_file"
            await q.edit_message_text("📎 فایل/عکس/ویدیو را ارسال کنید:", reply_markup=mkb([back_btn(back_cb)]))
        elif src_type == "forward":
            ctx.user_data["state"] = "wait_src_forward"
            await q.edit_message_text(
                "📨 پست کانال را فوروارد کنید:\n(ربات باید ادمین کانال باشد)",
                reply_markup=mkb([back_btn(back_cb)])
            )

    # ===== مدیریت نظرسنجی =====
    elif d == "a_manage_surveys":
        if not is_admin(user): return
        if not COURSES:
            await q.edit_message_text("دوره‌ای نیست.", reply_markup=mkb([back_btn("a_global_settings")]))
            return
        rows = []
        for cid, c in COURSES.items():
            sv_on = c.get("survey_enabled", True)
            st = "✅" if sv_on else "❌"
            rows.append([btn(f"{st} {c['title']}", f"a_toggle_survey|{cid}")])
        rows.append(back_btn("a_global_settings"))
        await q.edit_message_text(
            "📊 مدیریت نظرسنجی پایان دوره\n\nروی هر دوره بزنید تا فعال/غیرفعال شود:",
            reply_markup=mkb(rows),
        )

    elif d.startswith("a_toggle_survey|"):
        if not is_admin(user): return
        cid = d.split("|")[1]
        if cid in COURSES:
            COURSES[cid]["survey_enabled"] = not COURSES[cid].get("survey_enabled", True)
            save("courses")
            await safe_answer(q, "✅ وضعیت نظرسنجی تغییر کرد.")
        await q.edit_message_text(
            f"📊 نظرسنجی دوره «{COURSES.get(cid, {}).get('title', '')}»: "
            f"{'✅ فعال' if COURSES.get(cid, {}).get('survey_enabled', True) else '❌ غیرفعال'}",
            reply_markup=mkb([[btn("⬅️ بازگشت به مدیریت نظرسنجی", "a_manage_surveys")]]),
        )

    # ===== مدیریت دستورات =====
    elif d == "a_cmd_menu":
        if not is_admin(user): return
        cmd_rows = [
            [btn(f"{'✅' if cm.get('active', True) else '❌'} {i+1}. {cm['trigger'][:15]}",
                 f"a_cmd_edit|{i}")]
            for i, cm in enumerate(BOT_COMMANDS)
        ]
        cmd_rows.append([btn("➕ افزودن دستور جدید", "a_cmd_add")])
        cmd_rows.append(back_btn("a_global_settings"))
        await q.edit_message_text("🤖 مدیریت دستورات ربات", reply_markup=mkb(cmd_rows))

    elif d == "a_cmd_add":
        if not is_admin(user): return
        ctx.user_data["state"] = "wait_cmd_trigger"
        ctx.user_data.pop("cmd_building", None)
        await q.edit_message_text(
            "🤖 دستور جدید\n\nتریگر (کلمه یا عبارتی که ربات به آن پاسخ می‌دهد) را بفرستید:",
            reply_markup=mkb([back_btn("a_cmd_menu")]),
        )

    elif d.startswith("a_cmd_type|"):
        if not is_admin(user): return
        cmd_type = d.split("|")[1]
        ctx.user_data.setdefault("cmd_building", {})["command_type"] = cmd_type
        if cmd_type == "text_reply":
            ctx.user_data["state"] = "wait_cmd_text_response"
            await q.edit_message_text(
                "💬 متن پاسخ را بفرستید:",
                reply_markup=mkb([back_btn("a_cmd_menu")]),
            )
        else:
            await q.edit_message_text(
                "⚡ نام عملیات را انتخاب کنید:",
                reply_markup=mkb([
                    [btn("📊 نمایش آمار", "a_cmd_action|show_activity")],
                    [btn("📚 لیست دوره‌ها", "a_cmd_action|show_courses_list")],
                    [btn("⏰ نمایش زمان", "a_cmd_action|show_datetime")],
                    [btn("📈 گزارش کاربران", "a_cmd_action|show_users_report")],
                    back_btn("a_cmd_menu"),
                ]),
            )

    elif d.startswith("a_cmd_action|"):
        if not is_admin(user): return
        action = d.split("|")[1]
        ctx.user_data.setdefault("cmd_building", {})["action_name"] = action
        await q.edit_message_text(
            f"✅ عملیات: {action}\n\nمحدوده اجرا:",
            reply_markup=mkb([
                [btn("📱 خصوصی", "a_cmd_scope|private"),
                 btn("👥 گروه", "a_cmd_scope|group"),
                 btn("🌐 هر دو", "a_cmd_scope|both")],
                back_btn("a_cmd_menu"),
            ]),
        )

    elif d.startswith("a_cmd_scope|"):
        if not is_admin(user): return
        scope_val = d.split("|")[1]
        ctx.user_data.setdefault("cmd_building", {})["scope"] = scope_val
        await q.edit_message_text(
            f"✅ محدوده: {scope_val}\n\nنوع تطبیق متن:",
            reply_markup=mkb([
                [btn("🎯 دقیق", "a_cmd_match|exact"),
                 btn("⬆️ شروع با", "a_cmd_match|startswith"),
                 btn("🔍 شامل", "a_cmd_match|contains")],
                back_btn("a_cmd_menu"),
            ]),
        )

    elif d.startswith("a_cmd_match|"):
        if not is_admin(user): return
        match_val = d.split("|")[1]
        ctx.user_data.setdefault("cmd_building", {})["match_type"] = match_val
        await q.edit_message_text(
            f"✔️ تطبیق: {match_val}\n\nآیا فقط ادمین بتواند اجرا کند؟",
            reply_markup=mkb([
                [btn("🔑 فقط ادمین", "a_cmd_adminonly|yes"),
                 btn("🌍 همه کاربران", "a_cmd_adminonly|no")],
                back_btn("a_cmd_menu"),
            ]),
        )

    elif d.startswith("a_cmd_adminonly|"):
        if not is_admin(user): return
        ao_val = d.split("|")[1] == "yes"
        b_cmd = ctx.user_data.get("cmd_building", {})
        b_cmd["admin_only"] = ao_val
        b_cmd["active"] = True
        trigger_c = b_cmd.get("trigger", "")
        cmd_type_c = b_cmd.get("command_type", "text_reply")
        if not trigger_c:
            await safe_answer(q, "❌ Trigger ندارید. دوباره امتحان کنید.", True)
            return
        new_cmd = {
            "trigger": trigger_c,
            "active": True,
            "admin_only": ao_val,
            "scope": b_cmd.get("scope", "both"),
            "match_type": b_cmd.get("match_type", "exact"),
            "command_type": cmd_type_c,
            "response_text": b_cmd.get("response_text", "") if cmd_type_c == "text_reply" else "",
            "action_name": b_cmd.get("action_name", "") if cmd_type_c == "action" else "",
        }
        BOT_COMMANDS.append(new_cmd)
        save("bot_commands")
        ctx.user_data.pop("state", None)
        ctx.user_data.pop("cmd_building", None)
        ao_txt = "🔑 فقط ادمین" if ao_val else "🌍 همه کاربران"
        detail = new_cmd.get("response_text", "") if cmd_type_c == "text_reply" else new_cmd.get("action_name", "")
        await q.edit_message_text(
            f"✅ دستور ذخیره شد!\n\n"
            f"🔢 Trigger: «{trigger_c}»\n"
            f"🔧 نوع: {cmd_type_c}\n"
            f"📝 جزئیات: {detail[:30]}\n"
            f"🌐 محدوده: {new_cmd['scope']}\n"
            f"🔑 دسترسی: {ao_txt}",
            reply_markup=mkb([back_btn("a_cmd_menu")]),
        )

    elif d.startswith("a_cmd_edit|"):
        if not is_admin(user): return
        ed_idx = int(d.split("|")[1])
        if ed_idx >= len(BOT_COMMANDS): return
        ec = BOT_COMMANDS[ed_idx]
        ec_ao = "🔑 فقط ادمین" if ec.get("admin_only") else "🌍 همه"
        detail_e = (
            ec.get("response_text", "") if ec.get("command_type") == "text_reply"
            else ec.get("action_name", "")
        )
        await q.edit_message_text(
            f"✏️ دستور {ed_idx+1}\n\n"
            f"🔢 Trigger: «{ec['trigger']}»\n"
            f"🔧 نوع: {ec.get('command_type', 'text_reply')}\n"
            f"📝 جزئیات: {detail_e[:40]}\n"
            f"🌐 محدوده: {ec.get('scope', 'both')}\n"
            f"✔️ تطبیق: {ec.get('match_type', 'exact')}\n"
            f"🔑 دسترسی: {ec_ao}\n"
            f"📊 وضعیت: {'✅ فعال' if ec.get('active', True) else '❌ غیرفعال'}",
            reply_markup=mkb([
                [btn("🔄 فعال/غیرفعال", f"a_cmd_toggle|{ed_idx}"),
                 btn("🗑 حذف", f"a_cmd_del|{ed_idx}")],
                back_btn("a_cmd_menu"),
            ]),
        )

    elif d.startswith("a_cmd_toggle|"):
        if not is_admin(user): return
        tog_idx = int(d.split("|")[1])
        if tog_idx < len(BOT_COMMANDS):
            BOT_COMMANDS[tog_idx]["active"] = not BOT_COMMANDS[tog_idx].get("active", True)
            save("bot_commands")
        await safe_answer(q, "✅ وضعیت تغییر کرد.")
        cmd_rows2 = [
            [btn(f"{'✅' if cm.get('active', True) else '❌'} {i+1}. {cm['trigger'][:15]}",
                 f"a_cmd_edit|{i}")]
            for i, cm in enumerate(BOT_COMMANDS)
        ]
        cmd_rows2.append([btn("➕ افزودن دستور جدید", "a_cmd_add")])
        cmd_rows2.append(back_btn("a_global_settings"))
        await q.edit_message_text("🤖 مدیریت دستورات ربات", reply_markup=mkb(cmd_rows2))

    elif d.startswith("a_cmd_del_yes|"):
        # [باگ ۳] حذف واقعی دستور — فقط بعد از تایید
        if not is_admin(user): return
        del_idx = int(d.split("|", 1)[1])
        if del_idx < len(BOT_COMMANDS):
            removed = BOT_COMMANDS.pop(del_idx)
            save("bot_commands")
            logger.info("🗑 ادمین %s دستور «%s» را حذف کرد.", user.id, removed.get("trigger", del_idx))
            await safe_answer(q, f"✅ دستور «{removed['trigger']}» حذف شد.")
        cmd_rows3 = [
            [btn(f"{'✅' if cm.get('active', True) else '❌'} {i+1}. {cm['trigger'][:15]}",
                 f"a_cmd_edit|{i}")]
            for i, cm in enumerate(BOT_COMMANDS)
        ]
        cmd_rows3.append([btn("➕ افزودن دستور جدید", "a_cmd_add")])
        cmd_rows3.append(back_btn("a_global_settings"))
        await q.edit_message_text("🤖 مدیریت دستورات ربات — حذف شد.", reply_markup=mkb(cmd_rows3))

    elif d.startswith("a_cmd_del|"):
        # [باگ ۳] مرحلهٔ تایید حذف دستور
        if not is_admin(user): return
        del_idx = int(d.split("|")[1])
        if del_idx >= len(BOT_COMMANDS):
            await safe_answer(q, "❌ دستور پیدا نشد.", True)
            return
        cm = BOT_COMMANDS[del_idx]
        await q.edit_message_text(
            _confirm_text(f"🤖 دستور: «{cm.get('trigger', del_idx)}»"),
            reply_markup=_confirm_kb(f"a_cmd_del_yes|{del_idx}", f"a_cmd_edit|{del_idx}"),
        )

    # ===== گنجینه ادمین =====
    elif d == "a_add_item":
        if not is_admin(user): return
        ctx.user_data["state"] = "wait_item_name"
        ctx.user_data.pop("item_building", None)
        await q.edit_message_text(
            "➕ آیتم جدید\n\nنام آیتم را بفرستید:",
            reply_markup=mkb([back_btn("a_shop")]),
        )

    elif d.startswith("a_item_view|"):
        if not is_admin(user): return
        sid = d.split("|")[1]
        item = SHOP.get(sid)
        if not item:
            return
        st = "✅ فعال" if item.get("active") else "❌ غیرفعال"
        stock = item.get("stock") if item.get("stock") is not None else "نامحدود"
        buyers = len(item.get("purchased_by", []))
        await q.edit_message_text(
            f"💎 آیتم: {item.get('title', '')}\n"
            f"📝 توضیح: {item.get('description', '')}\n"
            f"💰 قیمت: {item.get('price', 0)} اعتبار\n"
            f"📦 موجودی: {stock}\n"
            f"👥 خریداران: {buyers} نفر\n"
            f"📊 وضعیت: {st}",
            reply_markup=mkb([
                [btn("🔄 فعال/غیرفعال", f"a_item_toggle|{sid}"),
                 btn("🗑 حذف", f"a_item_del|{sid}")],
                back_btn("a_shop"),
            ]),
        )

    elif d.startswith("a_item_toggle|"):
        if not is_admin(user): return
        sid = d.split("|")[1]
        if sid in SHOP:
            SHOP[sid]["active"] = not SHOP[sid].get("active", True)
            save("shop")
            await safe_answer(q, "✅ وضعیت تغییر کرد.")
        await a_shop_panel(q)

    elif d.startswith("a_item_del_yes|"):
        # [باگ ۳] حذف واقعی آیتم گنجینه — فقط بعد از تایید
        if not is_admin(user): return
        sid = d.split("|", 1)[1]
        if sid in SHOP:
            title = SHOP.pop(sid).get("title", sid)
            save("shop")
            logger.info("🗑 ادمین %s آیتم گنجینه «%s» (%s) را حذف کرد.", user.id, title, sid)
            await safe_answer(q, "✅ آیتم حذف شد.")
        await a_shop_panel(q)

    elif d.startswith("a_item_del|"):
        # [باگ ۳] مرحلهٔ تایید حذف آیتم گنجینه
        if not is_admin(user): return
        sid = d.split("|")[1]
        item = SHOP.get(sid)
        if not item:
            await safe_answer(q, "❌ آیتم پیدا نشد.", True)
            return
        buyers = len(item.get("purchased_by", []))
        extra = f"👥 خریداران: {fa_num(buyers)} نفر" if buyers else ""
        await q.edit_message_text(
            _confirm_text(f"💎 آیتم گنجینه: «{item.get('title', sid)}»", extra),
            reply_markup=_confirm_kb(f"a_item_del_yes|{sid}", f"a_item_view|{sid}"),
        )

    elif d.startswith("a_item_kind|"):
        if not is_admin(user): return
        kind = d.split("|")[1]
        ctx.user_data.setdefault("item_building", {})["kind"] = kind
        ctx.user_data["state"] = "wait_item_description"
        await q.edit_message_text(
            f"✅ نوع: {kind}\n\nتوضیحات آیتم:",
            reply_markup=mkb([back_btn("a_shop")]),
        )


# ========================= اجرای دستور عملیاتی =========================

async def _exec_action(action_name: str, msg, user, ctx, args: str = ""):
    import datetime
    bot = ctx.bot
    chat_id = msg.chat.id
    chat_type = msg.chat.type
    reply_to = msg.reply_to_message
    try:
        if action_name == "show_datetime":
            def _to_jalali(gy, gm, gd):
                g_y = gy - 1600
                g_m = gm - 1
                g_d_no = 365 * g_y + (g_y + 3) // 4 - (g_y + 99) // 100 + (g_y + 399) // 400
                months = [31, 29 if g_y % 4 == 0 and (g_y % 100 != 0 or (g_y + 1600) % 400 == 0) else 28,
                          31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
                for i in range(g_m):
                    g_d_no += months[i]
                g_d_no += gd - 1
                j_d_no = g_d_no - 79
                j_np = j_d_no // 12053
                j_d_no %= 12053
                j_y = 979 + 33 * j_np + 4 * (j_d_no // 1461)
                j_d_no %= 1461
                if j_d_no >= 366:
                    j_y += (j_d_no - 1) // 365
                    j_d_no = (j_d_no - 1) % 365
                for i, j_dm in enumerate([31, 31, 31, 31, 31, 31, 30, 30, 30, 30, 30, 29]):
                    if j_d_no >= j_dm:
                        j_d_no -= j_dm
                    else:
                        return j_y, i + 1, j_d_no + 1
                return j_y, 12, j_d_no + 1

            def _to_hijri(gy, gm, gd):
                a = (14 - gm) // 12
                y = gy + 4800 - a
                m = gm + 12 * a - 3
                jdn = gd + (153 * m + 2) // 5 + 365 * y + y // 4 - y // 100 + y // 400 - 32045
                l = jdn - 1948440 + 10632
                n = (l - 1) // 10631
                l = l - 10631 * n + 354
                j = ((10985 - l) // 5316) * ((50 * l) // 17719) + (l // 5670) * ((43 * l) // 15238)
                l = l - ((30 - j) // 15) * ((17719 * j) // 50) - (j // 16) * ((15238 * j) // 43) + 29
                hy_m = (24 * l) // 709
                hy_d = l - (709 * hy_m) // 24
                hy_y = 30 * n + j - 30
                return hy_y, hy_m, hy_d

            WEEKDAYS_FA   = ["دوشنبه", "سه‌شنبه", "چهارشنبه", "پنج‌شنبه", "جمعه", "شنبه", "یک‌شنبه"]

            try:
                import pytz
                tz = pytz.timezone("Asia/Tehran")
                now = datetime.datetime.now(tz)
            except Exception:
                now = datetime.datetime.utcnow()

            gy, gm, gd = now.year, now.month, now.day
            time_str = now.strftime("%H:%M:%S")
            weekday_fa = WEEKDAYS_FA[now.weekday()]

            jy, jm, jd = _to_jalali(gy, gm, gd)
            hy, hm, hd = _to_hijri(gy, gm, gd)

            # --- ساخت بخش آخرین اتفاقات ---
            ev_lines = []
            if COURSES:
                ev_lines.append("📚 دوره‌های آموزشی:")
                for _cid, _c in list(COURSES.items())[-3:]:
                    ev_lines.append(f"  📖 {_c['title']} — {len(_c.get('lessons', []))} سرفصل")
                ev_lines.append("")
            _active_m = [m for m in MISSIONS if m.get("active", True)]
            if _active_m:
                ev_lines.append("🎯 ماموریت‌های فعال:")
                for _m in _active_m[-3:]:
                    _mi = {"text": "📝", "photo": "🖼", "video": "🎬"}.get(_m.get("type", "text"), "📌")
                    ev_lines.append(f"  {_mi} {_m.get('title', '---')} — +{_m.get('xp_reward', 0)} XP")
                ev_lines.append("")
            _active_sh = [it for it in SHOP.values() if it.get("active", False)]
            if _active_sh:
                ev_lines.append("💎 آیتم‌های گنجینه:")
                for _it in _active_sh[-3:]:
                    ev_lines.append(f"  🛍 {_it.get('title', '---')} — {_it.get('price', 0)}💰")
                ev_lines.append("")
            _top = normal_users_sorted()[:3]
            if _top:
                _medals = ["🥇", "🥈", "🥉"]
                ev_lines.append("🏆 برترین‌های این هفته:")
                for _i, _u in enumerate(_top):
                    _migrate_user(_u)
                    ev_lines.append(f"  {_medals[_i]} {_u.get('first_name','ناشناس')} — {_u.get('xp', _u.get('points',0))} XP")
            events_text = ("\n\n📰 آخرین اتفاقات:\n" + "\n".join(ev_lines)) if ev_lines else ""

            await msg.reply_text(
                f"⏰ ساعت: {time_str}\n"
                f"📅 شمسی: {jy}/{jm:02d}/{jd:02d} ({weekday_fa})\n"
                f"🌙 قمری: {hy}/{hm:02d}/{hd:02d}\n"
                f"📆 میلادی: {gy}/{gm:02d}/{gd:02d}"
                f"{events_text}"
            )

        elif action_name == "show_courses_list":
            if not COURSES:
                await msg.reply_text("📚 هنوز دوره‌ای اضافه نشده.")
                return
            lines = [f"📖 {v['title']} ({len(v.get('lessons', []))} سرفصل)" for v in COURSES.values()]
            await msg.reply_text("📚 دوره‌های موجود:\n\n" + "\n".join(lines))

        elif action_name == "show_activity":
            now_t = int(time.time())
            d1 = sum(
                1 for u in USERS.values()
                if u.get("last_active", 0) >= now_t - 86400 and u["id"] not in ADMIN_IDS
            )
            d7 = sum(
                1 for u in USERS.values()
                if u.get("last_active", 0) >= now_t - 604800 and u["id"] not in ADMIN_IDS
            )
            await msg.reply_text(
                f"📊 فعالیت کاربران:\n\n🟢 فعال امروز: {d1} نفر\n"
                f"🔵 فعال هفته: {d7} نفر\n👥 کل کاربران: {len(USERS)} نفر"
            )

        elif action_name == "show_users_report":
            top = normal_users_sorted()[:10]
            if not top:
                await msg.reply_text("هنوز کاربری نیست.")
                return
            lines2 = [
                f"{i+1}. {u.get('first_name', '?')} | 📈{u.get('xp', u.get('points',0))} XP | دعوت: {valid_refs(u['id'])}"
                for i, u in enumerate(top)
            ]
            await msg.reply_text("📊 گزارش کاربران (ده نفر برتر):\n\n" + "\n".join(lines2))

        elif action_name == "show_course_survey_report":
            if not SURVEYS:
                await msg.reply_text("📊 هنوز نظری ثبت نشده.")
                return
            rpt = []
            for scid, svotes in SURVEYS.items():
                sc = COURSES.get(scid, {})
                exc = sum(1 for v in svotes.values() if v.get("vote") == "excellent")
                nu = len(svotes) - exc
                rpt.append(f"📖 {sc.get('title', scid)}: {len(svotes)} نظر (⭐{exc} / 🔧{nu})")
            await msg.reply_text("📊 نظرسنجی دوره‌ها:\n\n" + "\n".join(rpt))

        elif action_name in ("close_group", "open_group"):
            await msg.reply_text("❌ این عملیات پشتیبانی نمی‌شود.")

        elif action_name == "mute_reply_user":
            if chat_type not in ("group", "supergroup") or not reply_to:
                await msg.reply_text("❌ روی پیام کاربر ریپلای کنید.")
                return
            try:
                hours = int(args) if args.strip().isdigit() else 1
            except Exception:
                hours = 1
            try:
                from telegram import ChatPermissions
                until = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=hours)
                await bot.restrict_chat_member(
                    chat_id, reply_to.from_user.id,
                    ChatPermissions(can_send_messages=False), until_date=until,
                )
                await msg.reply_text(f"🔇 {reply_to.from_user.first_name} برای {hours} ساعت ساکت شد.")
            except Exception as mute_err:
                await msg.reply_text(f"❌ خطا: {mute_err}")

        elif action_name == "warn_reply_user":
            if chat_type not in ("group", "supergroup") or not reply_to:
                await msg.reply_text("❌ روی پیام کاربر ریپلای کنید.")
                return
            await msg.reply_text(
                f"⚠️ اخطار به {reply_to.from_user.first_name}: "
                "رفتار شما خلاف قوانین گروه است."
            )

        elif action_name == "ban_reply_user":
            if chat_type not in ("group", "supergroup") or not reply_to:
                await msg.reply_text("❌ روی پیام کاربر ریپلای کنید.")
                return
            try:
                await bot.ban_chat_member(chat_id, reply_to.from_user.id)
                await msg.reply_text(f"🚫 {reply_to.from_user.first_name} بن شد.")
            except Exception as ban_err:
                await msg.reply_text(f"❌ خطا: {ban_err}")

        elif action_name == "unban_user":
            try:
                uid_unban = reply_to.from_user.id if reply_to else int(args.strip())
                await bot.unban_chat_member(chat_id, uid_unban)
                await msg.reply_text("✅ کاربر از بن خارج شد.")
            except Exception as unban_err:
                await msg.reply_text(f"❌ خطا: {unban_err}")

    except Exception as e:
        logger.error(f"action {action_name} error: {e}")
        try:
            await msg.reply_text(f"❌ خطای اجرا: {e}")
        except Exception:
            pass



# ========================= مشاور انسانی سایت =========================

def _cons_conn():
    c = sqlite3.connect(DB_PATH)
    c.row_factory = sqlite3.Row
    return c


def _cons_now():
    return time.strftime('%Y-%m-%d %H:%M:%S')


def _cons_ensure_schema():
    try:
        with _cons_conn() as c:
            c.execute("""CREATE TABLE IF NOT EXISTS consultant_requests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                name TEXT DEFAULT '', phone TEXT DEFAULT '', city TEXT DEFAULT '',
                main_problem TEXT DEFAULT '', selected_route_title TEXT DEFAULT '',
                intro_message TEXT DEFAULT '', status TEXT DEFAULT 'pending',
                last_turn TEXT DEFAULT '', free_user_messages_used INTEGER DEFAULT 0,
                paused_at TEXT DEFAULT '', resumed_at TEXT DEFAULT '', admin_chat_id TEXT DEFAULT '',
                created_at TEXT DEFAULT '', approved_at TEXT DEFAULT '', closed_at TEXT DEFAULT ''
            )""")
            c.execute("""CREATE TABLE IF NOT EXISTS consultant_messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                request_id INTEGER NOT NULL,
                sender TEXT DEFAULT 'user', text TEXT DEFAULT '', created_at TEXT DEFAULT ''
            )""")
            cols = {r[1] for r in c.execute('PRAGMA table_info(consultant_requests)').fetchall()}
            additions = {
                'last_turn': "ALTER TABLE consultant_requests ADD COLUMN last_turn TEXT DEFAULT ''",
                'free_user_messages_used': 'ALTER TABLE consultant_requests ADD COLUMN free_user_messages_used INTEGER DEFAULT 0',
                'paused_at': "ALTER TABLE consultant_requests ADD COLUMN paused_at TEXT DEFAULT ''",
                'resumed_at': "ALTER TABLE consultant_requests ADD COLUMN resumed_at TEXT DEFAULT ''",
                'admin_chat_id': "ALTER TABLE consultant_requests ADD COLUMN admin_chat_id TEXT DEFAULT ''",
            }
            for col, sql in additions.items():
                if col not in cols:
                    c.execute(sql)
    except Exception as e:
        logger.warning('consultant schema ensure failed: %s', e)


def _cons_get(req_id: int):
    _cons_ensure_schema()
    with _cons_conn() as c:
        row = c.execute('SELECT * FROM consultant_requests WHERE id=?', (int(req_id),)).fetchone()
        return dict(row) if row else None


def _cons_messages(req_id: int):
    _cons_ensure_schema()
    with _cons_conn() as c:
        return [dict(r) for r in c.execute(
            'SELECT * FROM consultant_messages WHERE request_id=? ORDER BY id ASC',
            (int(req_id),)
        ).fetchall()]


def _cons_update(req_id: int, **fields):
    if not fields:
        return
    _cons_ensure_schema()
    keys = list(fields.keys())
    sql = ', '.join([f'{k}=?' for k in keys])
    vals = [fields[k] for k in keys] + [int(req_id)]
    with _cons_conn() as c:
        c.execute(f'UPDATE consultant_requests SET {sql} WHERE id=?', vals)


def _cons_add_message(req_id: int, sender: str, text: str):
    _cons_ensure_schema()
    with _cons_conn() as c:
        c.execute(
            'INSERT INTO consultant_messages (request_id, sender, text, created_at) VALUES (?, ?, ?, ?)',
            (int(req_id), sender, (text or '')[:2000], _cons_now())
        )


def _cons_site_url(req_id: int) -> str:
    base = (os.getenv('SITE_BASE_URL') or os.getenv('WEB_BASE_URL') or '').strip().rstrip('/')
    return f'{base}/admin/consultant/{int(req_id)}' if base else ''


def _cons_status_icon(status: str) -> str:
    return {
        'pending': '🟡',
        'active': '🟢',
        'paused': '⏸',
        'closed': '⚫️',
        'rejected': '🔴',
    }.get(status or '', '•')


def _cons_status_fa(status: str) -> str:
    return {
        'pending': 'در انتظار تأیید',
        'active': 'فعال',
        'paused': 'متوقف موقت',
        'closed': 'بسته شده',
        'rejected': 'رد شده',
    }.get(status or '', status or '—')


def _cons_turn_fa(turn: str) -> str:
    return {'user': 'نوبت مشاور', 'admin': 'نوبت کاربر'}.get(turn or '', '—')


def _cons_stats() -> dict:
    _cons_ensure_schema()
    with _cons_conn() as c:
        rows = c.execute('SELECT status, COUNT(*) AS c FROM consultant_requests GROUP BY status').fetchall()
    out = {'pending': 0, 'active': 0, 'paused': 0, 'closed': 0, 'rejected': 0, 'total': 0}
    for r in rows:
        st = r['status'] or 'pending'
        out[st] = int(r['c'] or 0)
        out['total'] += int(r['c'] or 0)
    return out


def _cons_admin_menu_text() -> str:
    st = _cons_stats()
    return (
        '📋 مدیریت مشاور\n━━━━━━━━━━━━━━━━\n\n'
        f"📦 کل درخواست‌ها: {fa_num(st['total'])}\n"
        f"🟡 در انتظار: {fa_num(st['pending'])}\n"
        f"🟢 فعال: {fa_num(st['active'])}\n"
        f"⏸ متوقف: {fa_num(st['paused'])}\n"
        f"⚫️ بسته‌شده: {fa_num(st['closed'])}\n"
        f"🔴 رد شده: {fa_num(st['rejected'])}\n\n"
        'یک فیلتر را انتخاب کنید:'
    )


def _cons_admin_menu_kb():
    return mkb([
        [btn('همه', 'cons_list|all'), btn('در انتظار تأیید', 'cons_list|pending')],
        [btn('فعال', 'cons_list|active'), btn('متوقف موقت', 'cons_list|paused')],
        [btn('بسته شده', 'cons_list|closed'), btn('رد شده', 'cons_list|rejected')],
        [btn('🔙 بازگشت به مدیریت سایت', 'a_web_manage')],
    ])


def _cons_list(status_filter: str = 'all', limit: int = 10) -> list:
    _cons_ensure_schema()
    with _cons_conn() as c:
        if status_filter and status_filter != 'all':
            rows = c.execute(
                'SELECT * FROM consultant_requests WHERE status=? ORDER BY id DESC LIMIT ?',
                (status_filter, int(limit)),
            ).fetchall()
        else:
            rows = c.execute(
                'SELECT * FROM consultant_requests ORDER BY id DESC LIMIT ?',
                (int(limit),),
            ).fetchall()
    return [dict(r) for r in rows]


def _cons_list_text(status_filter: str) -> str:
    label = 'همه' if status_filter == 'all' else _cons_status_fa(status_filter)
    rows = _cons_list(status_filter)
    lines = [f'📋 درخواست‌های مشاور — {label}', '━━━━━━━━━━━━━━━━', '']
    if not rows:
        lines.append('درخواستی برای این فیلتر وجود ندارد.')
    else:
        lines.append('برای مشاهده جزئیات روی درخواست بزنید:')
    return '\n'.join(lines)


def _cons_list_kb(status_filter: str):
    rows = []
    for req in _cons_list(status_filter):
        title = f"{_cons_status_icon(req.get('status'))} {req.get('name') or 'کاربر'} — {req.get('city') or '—'}"
        rows.append([btn(title[:60], f"cons_view|{req['id']}")])
    rows.append([btn('🔄 به‌روزرسانی', f'cons_list|{status_filter}')])
    rows.append([btn('🔙 فیلترها', 'cons_admin_menu')])
    return mkb(rows)


def _cons_detail_text(req: dict) -> str:
    msgs = _cons_messages(req['id'])[-10:]
    remaining = max(0, 5 - int(req.get('free_user_messages_used') or 0))
    lines = [
        f"📋 درخواست مشاور #{fa_num(req.get('id'))}",
        '━━━━━━━━━━━━━━━━',
        '',
        f"👤 نام: {req.get('name') or '—'}",
        f"🏙 شهر: {req.get('city') or '—'}",
        f"📱 شماره: {req.get('phone') or '—'}",
        f"📌 وضعیت: {_cons_status_icon(req.get('status'))} {_cons_status_fa(req.get('status'))}",
        f"🎯 مشکل: {req.get('main_problem') or '—'}",
        f"🧭 مسیر: {req.get('selected_route_title') or '—'}",
        f"💬 پیام اولیه: {req.get('intro_message') or '—'}",
        f"🎁 پیام رایگان باقی‌مانده: {fa_num(remaining)} از ۵",
        f"🔁 نوبت فعلی: {_cons_turn_fa(req.get('last_turn'))}",
        '',
        '🗨 آخرین پیام‌ها:',
    ]
    if not msgs:
        lines.append('  هنوز پیام چت ثبت نشده است.')
    for m in msgs:
        who = 'کاربر' if m.get('sender') == 'user' else 'مشاور'
        lines.append(f"  {who}: {(m.get('text') or '')[:160]}")
    return '\n'.join(lines)


def _cons_detail_kb(req: dict):
    req_id = int(req['id'])
    status = req.get('status') or ''
    rows = []
    if status == 'pending':
        rows.append([btn('✅ تأیید و شروع چت', f'cons_approve|{req_id}'), btn('❌ رد درخواست', f'cons_reject|{req_id}')])
    elif status == 'active':
        rows.append([btn('⏸ توقف موقت', f'cons_pause|{req_id}'), btn('🛑 پایان چت', f'cons_close|{req_id}')])
    elif status == 'paused':
        rows.append([btn('▶️ ادامه گفتگو', f'cons_resume|{req_id}'), btn('🛑 پایان چت', f'cons_close|{req_id}')])
    rows.append([btn('🔄 به‌روزرسانی', f'cons_view|{req_id}')])
    rows.append([btn('🔙 لیست درخواست‌ها', 'cons_admin_menu')])
    return mkb(rows)


def _cons_control_kb(req_id: int):
    rows = [
        [btn('⏸ توقف موقت', f'cons_pause|{req_id}'), btn('▶️ ادامه گفتگو', f'cons_resume|{req_id}')],
        [btn('🛑 پایان چت', f'cons_close|{req_id}')],
        [btn('👁 مشاهده پرونده در ربات', f'cons_view|{req_id}')],
        [btn('🔙 بازگشت', 'cons_admin_menu')],
    ]
    return mkb(rows)


def _cons_notification_kb(req_id: int):
    return mkb([
        [btn('✅ تأیید و شروع چت', f'cons_approve|{req_id}'), btn('❌ رد درخواست', f'cons_reject|{req_id}')],
        [btn('👁 مشاهده در پنل مشاور ربات', f'cons_view|{req_id}')],
    ])


def _cons_summary_text(req: dict) -> str:
    return (
        f"📩 درخواست مشاور #{req.get('id')}\n━━━━━━━━━━━━━━━━\n\n"
        f"👤 {req.get('name') or 'کاربر'}\n"
        f"📱 {req.get('phone') or '—'}\n"
        f"🏙 {req.get('city') or '—'}\n\n"
        f"🎯 مشکل: {req.get('main_problem') or '—'}\n\n"
        f"🧭 مسیر: {req.get('selected_route_title') or '—'}\n\n"
        f"💬 پیام اولیه: {req.get('intro_message') or '—'}"
    )


async def _handle_consultant_callback(d: str, q, ctx, user) -> bool:
    if not d.startswith('cons_'):
        return False
    if not is_admin(user):
        await safe_answer(q, '❌ دسترسی ندارید.', True)
        return True

    if d == 'cons_admin_menu':
        await q.edit_message_text(_cons_admin_menu_text(), reply_markup=_cons_admin_menu_kb())
        return True

    if d.startswith('cons_list|'):
        status_filter = d.split('|', 1)[1] or 'all'
        await q.edit_message_text(_cons_list_text(status_filter), reply_markup=_cons_list_kb(status_filter))
        return True

    if d.startswith('cons_view|'):
        try:
            req_id = int(d.split('|', 1)[1])
        except Exception:
            await safe_answer(q, '❌ درخواست نامعتبر است.', True)
            return True
        req = _cons_get(req_id)
        if not req:
            await safe_answer(q, '❌ درخواست پیدا نشد.', True)
            return True
        await q.edit_message_text(_cons_detail_text(req), reply_markup=_cons_detail_kb(req))
        return True

    try:
        action, raw_id = d.split('|', 1)
        req_id = int(raw_id)
    except Exception:
        await safe_answer(q, '❌ درخواست نامعتبر است.', True)
        return True
    req = _cons_get(req_id)
    if not req:
        await safe_answer(q, '❌ درخواست پیدا نشد.', True)
        return True

    if action == 'cons_approve':
        _cons_update(req_id, status='active', last_turn='admin',
                     approved_at=_cons_now(), admin_chat_id=str(q.from_user.id))
        ctx.user_data['state'] = 'consultant_chat_active'
        ctx.user_data['consultant_request_id'] = req_id
        await q.edit_message_text(
            f"✅ چت فعال شد. شما در حال گفتگو با {req.get('name') or 'کاربر'} هستید.\n"
            "هر پیام بعدی شما به سایت او ارسال می‌شود.",
            reply_markup=_cons_control_kb(req_id)
        )
        return True
    if action == 'cons_reject':
        _cons_update(req_id, status='rejected', closed_at=_cons_now())
        await q.edit_message_text('❌ درخواست مشاوره رد شد.', reply_markup=_cons_notification_kb(req_id))
        return True
    if action == 'cons_pause':
        _cons_update(req_id, status='paused', paused_at=_cons_now())
        await q.edit_message_text('⏸ گفتگو موقتاً متوقف شد.', reply_markup=_cons_control_kb(req_id))
        return True
    if action == 'cons_resume':
        _cons_update(req_id, status='active', resumed_at=_cons_now(), admin_chat_id=str(q.from_user.id))
        ctx.user_data['state'] = 'consultant_chat_active'
        ctx.user_data['consultant_request_id'] = req_id
        await q.edit_message_text('▶️ گفتگو دوباره فعال شد.', reply_markup=_cons_control_kb(req_id))
        return True
    if action == 'cons_close':
        _cons_update(req_id, status='closed', closed_at=_cons_now())
        if ctx.user_data.get('consultant_request_id') == req_id:
            ctx.user_data.pop('state', None)
            ctx.user_data.pop('consultant_request_id', None)
        await q.edit_message_text('🛑 گفتگو پایان یافت و پرونده بسته شد.', reply_markup=_cons_control_kb(req_id))
        return True
    return False


async def _handle_consultant_state(text: str, msg, ctx, user) -> bool:
    if not (is_admin(user) and ctx.user_data.get('state') == 'consultant_chat_active'):
        return False
    req_id = int(ctx.user_data.get('consultant_request_id') or 0)
    req = _cons_get(req_id)
    if not req:
        ctx.user_data.pop('state', None)
        ctx.user_data.pop('consultant_request_id', None)
        await msg.reply_text('❌ پرونده مشاوره پیدا نشد.')
        return True

    if text == '⏸ توقف موقت':
        _cons_update(req_id, status='paused', paused_at=_cons_now())
        await msg.reply_text('⏸ گفتگو موقتاً متوقف شد.', reply_markup=_cons_control_kb(req_id))
        return True
    if text == '▶️ ادامه گفتگو':
        _cons_update(req_id, status='active', resumed_at=_cons_now(), admin_chat_id=str(user.id))
        await msg.reply_text('▶️ گفتگو دوباره فعال شد.', reply_markup=_cons_control_kb(req_id))
        return True
    if text == '🛑 پایان چت':
        _cons_update(req_id, status='closed', closed_at=_cons_now())
        ctx.user_data.pop('state', None)
        ctx.user_data.pop('consultant_request_id', None)
        await msg.reply_text('🛑 گفتگو پایان یافت.', reply_markup=reply_kb(user))
        return True

    if req.get('status') != 'active':
        await msg.reply_text('این گفتگو فعال نیست. ابتدا از دکمه ادامه گفتگو استفاده کنید.', reply_markup=_cons_control_kb(req_id))
        return True
    if (req.get('last_turn') or '') == 'admin':
        await msg.reply_text('منتظر پاسخ کاربر باشید. تا پیام او نرسیده، پیام جدید ارسال نکنید.', reply_markup=_cons_control_kb(req_id))
        return True
    _cons_add_message(req_id, 'admin', text)
    _cons_update(req_id, last_turn='admin', admin_chat_id=str(user.id))
    await msg.reply_text('✅ پاسخ شما در سایت برای کاربر ثبت شد.', reply_markup=_cons_control_kb(req_id))
    return True


# ========================= میان‌بر یار هوشمند =========================

class _MsgShim:
    """شبیه‌ساز callback_query روی یک پیام معمولی.

    دکمهٔ «🧠 مسیر شغلی هوشمند» از نوع ReplyKeyboard است، پس callback_query
    وجود ندارد و نمی‌توان پیام را ویرایش کرد. این شیء همان رابطی را می‌دهد
    که handle_aim_callback انتظار دارد، ولی به‌جای ویرایش، پیام تازه می‌فرستد.
    """
    def __init__(self, m):
        self._m = m
        self.message = m

    async def edit_message_text(self, text, reply_markup=None, **kw):
        await self._m.reply_text(text, reply_markup=reply_markup)

    async def answer(self, text=None, show_alert=False, **kw):
        if text:
            await self._m.reply_text(text)


async def _open_ai_mentor(msg, user, ctx):
    """باز کردن منوی «یار هوشمند شغلی» از دکمهٔ متنیِ منوی کاربر.

    ctx به‌صورت صریح پاس داده می‌شود (نه از متغیر سراسری) تا در حالت
    چند کاربر همزمان، user_data افراد با هم قاطی نشود.
    اگر ماژول در دسترس نباشد، صفحهٔ ایستای قبلی نمایش داده می‌شود (fail-safe).
    """
    try:
        if await handle_aim_callback("aim_menu", _MsgShim(msg), ctx, user):
            return
    except Exception as e:
        logger.error(f"_open_ai_mentor خطا: {e}", exc_info=True)
    await show_career_path(msg, user)


# ========================= هندلر متن =========================

async def handle_text(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not update.effective_chat:
        return
    chat_type = update.effective_chat.type
    if chat_type == "channel":
        return
    raw_user = update.effective_user
    msg = update.message
    if not msg:
        return
    text = (msg.text or "").strip()

    platform = detect_platform(ctx.bot)
    set_current_platform(platform)
    sync_deleted_users_from_db()

    # روی پلتفرم ثانویه: تا حساب با شماره فعال نشده، فقط دکمهٔ اشتراک شماره پذیرفته می‌شود
    if chat_type == "private" and platform != "bale" and canonical_user_id(platform, raw_user.id) is None:
        await msg.reply_text(
            "📱 برای فعال‌سازی حساب، لطفاً فقط با دکمهٔ «اشتراک‌گذاری شماره» شمارهٔ خودتان را بفرستید.\n"
            "⚠️ شماره حتماً باید شماره‌ی خودتان باشد تا حسابتان اینجا فعال شود.",
            reply_markup=phone_kb(),
        )
        return

    # هویت اصلی (canonical) روی پلتفرم ثانویه
    user = effective_user(raw_user, platform)
    if platform != "bale":
        touch_platform_activity(platform, raw_user.id)

    # [مشکل 1] بررسی بن در هندلر پیام‌ها (فقط چت خصوصی)
    if chat_type == "private" and not is_admin(user) and is_user_banned(user.id):
        await msg.reply_text("🚫 دسترسی شما به ربات مسدود شده است.")
        return

    # [مشکل 8] بررسی میوت در هندلر پیام‌ها — کاربر میوت‌شده از دکمه‌های متنی هم نباید استفاده کند
    if chat_type == "private" and not is_admin(user) and is_user_muted(user.id):
        u_data = USERS.get(str(user.id), {})
        mute_until = u_data.get("mute_until", 0)
        remaining = max(0, int(mute_until) - int(time.time()))
        if remaining > 0:
            hrs = remaining // 3600
            mins = (remaining % 3600) // 60
            timer_txt = f"{hrs} ساعت و {mins} دقیقه" if hrs > 0 else f"{mins} دقیقه"
            await msg.reply_text(f"🔇 شما میوت هستید. {timer_txt} دیگر آزاد می‌شوید.")
        else:
            await msg.reply_text("🔇 شما در حال حاضر میوت هستید و نمی‌توانید از ربات استفاده کنید.")
        return

    # آپلود امن تصویر Maintenance فقط در خصوصی و فقط توسط ادمین اصلی.
    maintenance_state=str(ctx.user_data.get('state') or '')
    if maintenance_state.startswith('wait_site_base_url_'):
        if chat_type!='private' or int(user.id) not in ADMIN_IDS:
            ctx.user_data.pop('state',None);await msg.reply_text("⛔ دسترسی مجاز نیست.");return
        scope=maintenance_state.rsplit('_',1)[-1]
        if (text or '').strip()=='/cancel':
            ctx.user_data.pop('state',None);await msg.reply_text("❌ تنظیم آدرس لغو شد.",reply_markup=_site_main_maint_kb() if scope=='main' else _site_giso_maint_kb());return
        url=(text or '').strip()
        from urllib.parse import urlparse as _up
        ok=bool(url) and ' ' not in url and _up(url).scheme in ('http','https') and bool(_up(url).hostname)
        if not ok:
            await msg.reply_text("❌ آدرس معتبر نیست؛ باید با http:// یا https:// شروع شود.");return
        try:
            from giso_admin import set_giso_config, set_giso_site_config
            _key = 'main_site_base_url' if scope=='main' else 'site_base_url'
            _url = url.rstrip('/')
            # ① منبع اصلی giso.db (مشترک با ربات/پنل گیسو) — بدون این، مقدار از
            #    دید پنل گیسو «ذخیره‌نشده» می‌ماند؛ ② نسخهٔ قدیمی bot.db برای سازگاری.
            set_giso_site_config(_key, _url)
            set_giso_config(_key, _url)
            ctx.user_data.pop('state',None)
            await msg.reply_text(f"✅ آدرس {('سایت اصلی' if scope=='main' else 'گیسو')} ذخیره شد:\n{_url}\nلینک‌های موقت از این به بعد از این آدرس ساخته می‌شوند.",reply_markup=_site_main_maint_kb() if scope=='main' else _site_giso_maint_kb())
        except Exception as e:
            await msg.reply_text(f"❌ ذخیره نشد: {e}")
        return
    if maintenance_state.startswith('wait_maintenance_image_'):
        if chat_type!='private' or int(user.id) not in ADMIN_IDS:
            ctx.user_data.pop('state',None);await msg.reply_text("⛔ دسترسی مجاز نیست.");return
        scope=maintenance_state.rsplit('_',1)[-1]
        if text=='/cancel':
            ctx.user_data.pop('state',None);await msg.reply_text("❌ بارگذاری لغو شد.",reply_markup=web_main_manage_kb() if scope=='main' else web_giso_manage_kb());return
        await _handle_maintenance_image_upload(msg,ctx,scope)
        return

    # ===== گروه / سوپرگروه =====
    if chat_type in ("group", "supergroup"):
        # [کار ۳] ثبت خودکار گروه با هر پیام — قبلاً فقط با /start یا عضو جدید
        # ثبت می‌شد، پس گروه‌های قدیمی هرگز در «ارسال به گروه‌ها» دیده نمی‌شدند.
        try:
            ch = update.effective_chat
            record_bot_group(platform, ch.id, ch.title or "", ch.type or "group")
        except Exception as e:
            logger.debug(f"record_bot_group (text) error: {e}")

        for cmd in BOT_COMMANDS:
            if not cmd.get("active", True):
                continue
            sc = cmd.get("scope", "both")
            if sc == "private":
                continue
            if cmd.get("admin_only", False) and not is_admin(user):
                continue
            if match_cmd(cmd, text):
                if cmd.get("command_type") == "action":
                    args = text[len(cmd["trigger"]):].strip()
                    await _exec_action(cmd.get("action_name", ""), msg, user, ctx, args)
                else:
                    await msg.reply_text(cmd.get("response_text", ""))
                return
        if not is_admin(user):
            return
        state = ctx.user_data.get("state")
        if state == "wait_cmd_trigger":
            ctx.user_data.setdefault("cmd_building", {})["trigger"] = text
            ctx.user_data["state"] = "wait_cmd_type"
            await msg.reply_text(
                f"✅ Trigger: «{text}»\n\nنوع دستور را انتخاب کنید:",
                reply_markup=mkb([
                    [btn("💬 پاسخ متنی", "a_cmd_type|text_reply"),
                     btn("⚡ عملیاتی", "a_cmd_type|action")],
                    back_btn("a_cmd_menu"),
                ]),
            )
        return

    # ===== چت خصوصی =====
    register_user(user)
    state = ctx.user_data.get("state")

    # مرحله اول — تا شماره تلفن ثبت نشده، هر متنی به عنوان ورودی شماره پردازش شود
    if not has_phone(user.id):
        await _register_phone(msg, user, ctx, text)
        return

    # 🗣 state مشاور انسانی سایت — فقط ادمین
    if await _handle_consultant_state(text, msg, ctx, user):
        return

    # 🤖 stateهای پنل مدیریت AI — فقط ادمین
    if is_admin(user) and state in AI_STATES:
        if await handle_ai_state(state, text, msg, ctx):
            return

    # 🤖 stateهای «یار هوشمند شغلی» — ادمین (تنظیمات ماژول)
    if is_admin(user) and state in AIMA_STATES:
        if await handle_aim_admin_state(state, text, msg, ctx, user):
            return

    # 🤖 stateهای «یار هوشمند شغلی» — کاربر عادی (مصاحبه، چالش، چت)
    if state in AIM_STATES:
        if await handle_aim_state(state, text, msg, ctx, user):
            return

    # 🎀 stateهای مدیریت ربات گیسو — فقط ادمین
    if is_admin(user):
        try:
            from giso_handlers import giso_text_handler
            if await giso_text_handler(update, ctx):
                return
        except Exception as e:
            logger.warning(f"giso text handler error: {e}")

    if is_admin(user) and state == "wait_src_forward":
        await save_forwarded(msg, ctx)
        return

    if state == "wait_ticket" and not is_admin(user):
        TICKETS.append({
            "user_id": user.id, "user_name": user.first_name or "ناشناس",
            "username": user.username or "", "text": text,
            "time": int(time.time()), "replied": False, "reply_text": "",
            # پلتفرم و chat_id واقعیِ مبدا — برای پاسخ درست از همان پلتفرم
            "platform": platform, "chat_id": raw_user.id,
            "canonical_user_id": user.id,
        })
        save("tickets")
        ctx.user_data.pop("state", None)
        await msg.reply_text(
            f"✅ پیام شما ارسال شد!\n\nتیم پشتیبانی در اسرع وقت پاسخ می‌دهد. 💙\n"
            f"📞 {support_link(platform)[0]}",
            reply_markup=reply_kb(user),
        )
        # [کار ۲] اعلان به ادمین‌های همهٔ پلتفرم‌های فعال — هر پلتفرم با bot خودش.
        # bot_route_targets حالا ادمین‌هایی که با شماره متصل شده‌اند را هم برمی‌گرداند،
        # پس ادمین در تلگرام هم اعلان تیکتِ تلگرام را دریافت می‌کند.
        uname_line = f"👤 یوزرنیم: @{user.username}\n" if user.username else ""
        ticket_no = len(TICKETS)
        notify_text = (
            "📬 پیام پشتیبانی جدید\n"
            "━━━━━━━━━━━━━━━━\n"
            f"🌐 پلتفرم: {platform_name(platform)}\n"
            f"👤 نام: {user.first_name}\n"
            f"{uname_line}"
            f"🆔 شناسه: {user.id}\n"
            f"💬 Chat ID: {raw_user.id}\n"
            f"🎫 شماره تیکت: {fa_num(ticket_no)}\n\n"
            f"📝 متن پیام:\n{text}"
        )
        # دکمهٔ پاسخ مستقیم به همین تیکت + فهرست کامل
        kb = mkb([
            [btn("✍️ پاسخ به این پیام", f"a_reply|{ticket_no - 1}")],
            [btn("📬 مشاهده همهٔ پیام‌ها", "a_tickets")],
        ])
        sent_to, failed_to = [], []
        for p2 in active_platform_bots().keys():
            bot2 = get_platform_bot(p2)
            if not bot2:
                continue
            for aid in bot_route_targets(p2, get_platform_admins):
                try:
                    await bot2.send_message(aid, notify_text, reply_markup=kb)
                    sent_to.append(f"{p2}:{aid}")
                except Exception as e:
                    failed_to.append(f"{p2}:{aid}")
                    logger.error(f"Notify admin error ({p2}:{aid}): {e}")
        logger.info(
            "📬 تیکت #%d از %s — اعلان به %d ادمین ارسال شد%s",
            ticket_no, platform, len(sent_to),
            f" ({len(failed_to)} ناموفق)" if failed_to else "",
        )
        return

    if is_admin(user) and state == "wait_ticket_reply":
        idx = ctx.user_data.get("reply_idx")
        if idx is not None and 0 <= idx < len(TICKETS):
            tk = TICKETS[idx]
            ctx.user_data.pop("state", None)
            ctx.user_data.pop("reply_idx", None)
            ok, err = await send_ticket_reply_strict(tk, text)
            if ok:
                tk["replied"] = True
                tk["reply_text"] = text
                save("tickets")
                await msg.reply_text("✅ پاسخ شما ارسال شد.", reply_markup=mkb([back_btn("a_tickets")]))
            else:
                await msg.reply_text(
                    f"❌ ارسال پاسخ ناموفق بود.\n{err}",
                    reply_markup=mkb([back_btn("a_tickets")]),
                )
        return

    # 🌐 کد استعلام پروفایل عمومی (B2B) — هر کسی می‌تواند بفرستد.
    # فقط اگر متن دقیقاً یک کد ۶ حرفیِ معتبر و متعلق به پروفایلِ عمومی باشد
    # پاسخ داده می‌شود؛ در غیر این صورت بی‌صدا رد می‌شود تا مسیرهای بعدی
    # (دکمه‌های متنی و دستورات) دست‌نخورده بمانند.
    try:
        if await try_verification_code(text, msg, ctx):
            return
    except Exception as _e:
        logger.debug("verification code check failed: %s", _e)

    # دکمه‌های ثابت — با چک دسترسی برای کاربران غیرادمین
    _FEATURE_MAP = {
        "📚 لیست دوره‌ها":         ("courses",        lambda: show_courses(msg, False, uid=user.id)),
        "📞 پشتیبانی":             ("support",         lambda: show_support(msg, user=user)),
        "🏆 پروفایل من":           ("profile",         lambda: show_profile(msg, user)),
        "👥 دعوت دوستان":          ("referral",        lambda: show_referral(msg, user)),
        "🧠 مسیر شغلی هوشمند":    ("career_path",     lambda: _open_ai_mentor(msg, user, ctx)),
        "🎯 ماموریت‌ها":           ("missions",        lambda: show_missions(msg, user, is_q=False)),
        "📰 آخرین اتفاقات":        ("latest_events",   lambda: show_latest_events(msg, is_q=False)),
        "💎 گنجینه":               ("shop",            lambda: show_shop(msg, user, is_q=False)),
    }
    if text in _FEATURE_MAP:
        fkey, fn = _FEATURE_MAP[text]
        if not is_admin(user):
            ok, reason = check_feature_access(user.id, fkey)
            if not ok:
                await msg.reply_text(f"🔒 دسترسی محدود\n\n{reason}", reply_markup=reply_kb(user))
                return
            ok2, reason2 = check_user_specific_access(user.id, fkey)
            if not ok2:
                await msg.reply_text(f"🔐 دسترسی اختصاصی محدود\n\n{reason2}", reply_markup=reply_kb(user))
                return
        await fn()
        return

    if text == "👑 پنل مدیریت":
        if not is_admin(user):
            await msg.reply_text("❌ شما دسترسی ندارید.", reply_markup=reply_kb(user))
            return
        await admin_panel(msg, False)
        return

    if text == "🌐 مدیریت سایت":
        if not is_admin(user):
            await msg.reply_text("❌ شما دسترسی ندارید.", reply_markup=reply_kb(user))
            return
        await msg.reply_text(
            "🌐 مدیریت سایت\n\nاز اینجا می‌توانید بخش‌های مختلف سایت را مدیریت کنید.",
            reply_markup=web_manage_kb()
        )
        return

    if text == "⚙️ تنظیمات عمومی":
        if not is_admin(user):
            await msg.reply_text("❌ شما دسترسی ندارید.", reply_markup=reply_kb(user))
            return
        await msg.reply_text(
            "⚙️ تنظیمات عمومی",
            reply_markup=mkb([[btn("⚙️ باز کردن تنظیمات", "a_global_settings")]]),
        )
        return

    if text == "📣 مرکز پیام‌رسانی":
        if not is_admin(user):
            await msg.reply_text("❌ شما دسترسی ندارید.", reply_markup=reply_kb(user))
            return
        messaging_reset_bc(ctx)
        await show_messaging_center_v2(msg, is_q=False)
        return

    # دستورات سفارشی
    for cmd in BOT_COMMANDS:
        if not cmd.get("active", True):
            continue
        sc = cmd.get("scope", "both")
        if sc == "group":
            continue
        if cmd.get("admin_only", False) and not is_admin(user):
            continue
        if match_cmd(cmd, text):
            if cmd.get("command_type") == "action":
                args = text[len(cmd["trigger"]):].strip()
                await _exec_action(cmd.get("action_name", ""), msg, user, ctx, args)
            else:
                await msg.reply_text(cmd.get("response_text", ""))
            return

    if not is_admin(user):
        await msg.reply_text("برای شروع دکمه /start را بزنید. 👇", reply_markup=reply_kb(user))
        return

    # ===== state‌های ادمین =====
    FIELD_STATES = {
        "wait_ctitle": ("title", "عنوان"),
        "wait_cdesc":  ("description", "توضیحات"),
    }
    if state in FIELD_STATES:
        field, label = FIELD_STATES[state]
        cid = ctx.user_data.get("ecid")
        if cid in COURSES:
            COURSES[cid][field] = text
            save("courses")
        ctx.user_data.pop("state", None)
        await msg.reply_text(f"✅ {label} ذخیره شد.", reply_markup=mkb([back_btn(f"a_open|{cid}")]))
        return

    if state == "wait_course_title":
        cid = next_cid()
        COURSES[cid] = {"title": text, "description": "", "lessons": [],
                        "required_joins": [], "referral_required": 0, "required_credits": 0}
        save("courses")
        ctx.user_data.pop("state", None)
        await msg.reply_text(
            f"✅ دوره «{text}» ساخته شد!",
            reply_markup=mkb([[btn("✏️ مدیریت دوره", f"a_open|{cid}")], back_btn("a_courses_menu")]),
        )

    elif state == "wait_cjoin":
        cid = ctx.user_data.get("ecid")
        COURSES[cid]["required_joins"] = (
            [] if text == "حذف"
            else [l.strip() for l in text.split("\n") if l.strip()]
        )
        save("courses")
        ctx.user_data.pop("state", None)
        rj = COURSES[cid]["required_joins"]
        await msg.reply_text(
            f"✅ ذخیره شد.\n🔒 عضویت اجباری: {', '.join(rj) if rj else 'ندارد'}",
            reply_markup=mkb([back_btn(f"a_open|{cid}")]),
        )

    elif state == "wait_cref":
        cid = ctx.user_data.get("ecid")
        try:
            val = int(text)
        except Exception:
            val = 0
        COURSES[cid]["referral_required"] = val
        if val > 0:
            COURSES[cid]["referral_required_set_at"] = int(time.time())
        else:
            COURSES[cid].pop("referral_required_set_at", None)
        save("courses")
        ctx.user_data.pop("state", None)
        await msg.reply_text(
            f"✅ ذخیره شد.\n👥 دعوت اجباری: {val} نفر",
            reply_markup=mkb([back_btn(f"a_open|{cid}")]),
        )

    elif state == "wait_ccredit":
        cid = ctx.user_data.get("ecid")
        try:
            val = max(0, int(text))
        except Exception:
            val = 0
        COURSES[cid]["required_credits"] = val
        save("courses")
        ctx.user_data.pop("state", None)
        await msg.reply_text(
            f"✅ ذخیره شد.\n💰 اعتبار اجباری دوره: {val}",
            reply_markup=mkb([back_btn(f"a_open|{cid}")]),
        )

    # ===== state‌های فروش نقدی (ادمین) =====

    elif is_admin(user) and state == "wait_cash_sale_price":
        target_type = ctx.user_data.pop("cst_target_type", "course")
        target_id = ctx.user_data.pop("cst_target_id", "")
        cid = ctx.user_data.pop("cst_cid", "")
        idx = ctx.user_data.pop("cst_idx", 0)
        ctx.user_data.pop("state", None)
        try:
            amount = max(0, int(text.strip().replace(",", "").replace("،", "")))
        except Exception:
            await msg.reply_text("❌ مبلغ باید عدد باشد. دوباره بفرستید:")
            ctx.user_data["state"] = "wait_cash_sale_price"
            ctx.user_data["cst_target_type"] = target_type
            ctx.user_data["cst_target_id"] = target_id
            ctx.user_data["cst_cid"] = cid
            ctx.user_data["cst_idx"] = idx
            return
        cur = CASH_SALE_SETTINGS.get(f"{target_type}|{target_id}", {})
        set_cash_sale_setting(
            target_type, target_id,
            cur.get("enabled", False),
            amount,
            cur.get("payment_method", ""),
            cur.get("display_note", ""),
            cur.get("display_place", "course"),
            cur.get("xp_reward", 0),
            cur.get("credits_reward", 0),
        )
        back_cb = f"a_cash_sale_setting|{target_type}|{cid}" + (f"|{idx}" if target_type == "lesson" else "")
        await msg.reply_text(
            f"✅ مبلغ فروش نقدی ذخیره شد.\n💰 مبلغ: {amount:,} تومان",
            reply_markup=mkb([back_btn(back_cb)]),
        )

    elif is_admin(user) and state == "wait_cash_card_number":
        # [مشکل 5] مرحله ۱: شماره کارت ۱۶ رقمی با اعتبارسنجی
        target_type = ctx.user_data.get("cst_target_type", "course")
        cid = ctx.user_data.get("cst_cid", "")
        idx = ctx.user_data.get("cst_idx", 0)
        back_cb = f"a_cash_sale_setting|{target_type}|{cid}" + (f"|{idx}" if target_type == "lesson" else "")
        digits = "".join(ch for ch in text if ch.isdigit())
        if len(digits) != 16:
            await msg.reply_text(
                "❌ شماره کارت باید دقیقاً ۱۶ رقم باشد.\n"
                "لطفاً دوباره شماره کارت را بفرستید:",
                reply_markup=mkb([back_btn(back_cb)]),
            )
            return
        ctx.user_data["cst_card_number"] = digits
        ctx.user_data["state"] = "wait_cash_card_holder"
        await msg.reply_text(
            "✅ شماره کارت ثبت شد.\n\n"
            "💳 ثبت اطلاعات کارت (مرحله ۲ از ۳)\n\n"
            "نام صاحب کارت را بفرستید:",
            reply_markup=mkb([back_btn(back_cb)]),
        )

    elif is_admin(user) and state == "wait_cash_card_holder":
        # [مشکل 5] مرحله ۲: نام صاحب کارت
        target_type = ctx.user_data.get("cst_target_type", "course")
        cid = ctx.user_data.get("cst_cid", "")
        idx = ctx.user_data.get("cst_idx", 0)
        back_cb = f"a_cash_sale_setting|{target_type}|{cid}" + (f"|{idx}" if target_type == "lesson" else "")
        ctx.user_data["cst_card_holder"] = text.strip()
        ctx.user_data["state"] = "wait_cash_bank_name"
        await msg.reply_text(
            "✅ نام صاحب کارت ثبت شد.\n\n"
            "💳 ثبت اطلاعات کارت (مرحله ۳ از ۳)\n\n"
            "نام بانک را بفرستید:",
            reply_markup=mkb([back_btn(back_cb)]),
        )

    elif is_admin(user) and state == "wait_cash_bank_name":
        # [مشکل 5] مرحله ۳: نام بانک + ذخیره نهایی اطلاعات کارت
        target_type = ctx.user_data.pop("cst_target_type", "course")
        target_id = ctx.user_data.pop("cst_target_id", "")
        cid = ctx.user_data.pop("cst_cid", "")
        idx = ctx.user_data.pop("cst_idx", 0)
        card_number = ctx.user_data.pop("cst_card_number", "")
        card_holder = ctx.user_data.pop("cst_card_holder", "")
        bank_name = text.strip()
        ctx.user_data.pop("state", None)
        cur = CASH_SALE_SETTINGS.get(f"{target_type}|{target_id}", {})
        set_cash_sale_setting(
            target_type, target_id,
            cur.get("enabled", False),
            cur.get("amount", 0),
            cur.get("payment_method", ""),
            cur.get("display_note", ""),
            cur.get("display_place", "course"),
            cur.get("xp_reward", 0),
            cur.get("credits_reward", 0),
            card_number=card_number,
            card_holder=card_holder,
            bank_name=bank_name,
        )
        back_cb = f"a_cash_sale_setting|{target_type}|{cid}" + (f"|{idx}" if target_type == "lesson" else "")
        await msg.reply_text(
            "✅ اطلاعات کارت ذخیره شد.\n\n"
            f"💳 {format_card_number(card_number)}\n"
            f"👤 به نام: {card_holder}\n"
            f"🏦 بانک: {bank_name}",
            reply_markup=mkb([back_btn(back_cb)]),
        )

    elif is_admin(user) and state == "wait_cash_sale_method":
        target_type = ctx.user_data.pop("cst_target_type", "course")
        target_id = ctx.user_data.pop("cst_target_id", "")
        cid = ctx.user_data.pop("cst_cid", "")
        idx = ctx.user_data.pop("cst_idx", 0)
        ctx.user_data.pop("state", None)
        cur = CASH_SALE_SETTINGS.get(f"{target_type}|{target_id}", {})
        set_cash_sale_setting(
            target_type, target_id,
            cur.get("enabled", False),
            cur.get("amount", 0),
            text.strip(),
            cur.get("display_note", ""),
            cur.get("display_place", "course"),
            cur.get("xp_reward", 0),
            cur.get("credits_reward", 0),
        )
        back_cb = f"a_cash_sale_setting|{target_type}|{cid}" + (f"|{idx}" if target_type == "lesson" else "")
        await msg.reply_text(
            f"✅ روش پرداخت ذخیره شد.",
            reply_markup=mkb([back_btn(back_cb)]),
        )

    elif is_admin(user) and state == "wait_cash_sale_note":
        target_type = ctx.user_data.pop("cst_target_type", "course")
        target_id = ctx.user_data.pop("cst_target_id", "")
        cid = ctx.user_data.pop("cst_cid", "")
        idx = ctx.user_data.pop("cst_idx", 0)
        ctx.user_data.pop("state", None)
        cur = CASH_SALE_SETTINGS.get(f"{target_type}|{target_id}", {})
        note = "" if text.strip() == "حذف" else text.strip()
        set_cash_sale_setting(
            target_type, target_id,
            cur.get("enabled", False),
            cur.get("amount", 0),
            cur.get("payment_method", ""),
            note,
            cur.get("display_place", "course"),
            cur.get("xp_reward", 0),
            cur.get("credits_reward", 0),
        )
        back_cb = f"a_cash_sale_setting|{target_type}|{cid}" + (f"|{idx}" if target_type == "lesson" else "")
        await msg.reply_text(
            f"✅ توضیحات ذخیره شد." if note else "✅ توضیحات حذف شد.",
            reply_markup=mkb([back_btn(back_cb)]),
        )

    elif is_admin(user) and state == "wait_cash_sale_xpreward":
        target_type = ctx.user_data.pop("cst_target_type", "course")
        target_id = ctx.user_data.pop("cst_target_id", "")
        cid = ctx.user_data.pop("cst_cid", "")
        idx = ctx.user_data.pop("cst_idx", 0)
        ctx.user_data.pop("state", None)
        try:
            xp_rw = max(0, int(text.strip().replace(",", "").replace("،", "")))
        except Exception:
            await msg.reply_text("❌ مقدار باید عدد باشد.")
            ctx.user_data["state"] = "wait_cash_sale_xpreward"
            ctx.user_data["cst_target_type"] = target_type
            ctx.user_data["cst_target_id"] = target_id
            ctx.user_data["cst_cid"] = cid
            ctx.user_data["cst_idx"] = idx
            return
        cur = CASH_SALE_SETTINGS.get(f"{target_type}|{target_id}", {})
        set_cash_sale_setting(
            target_type, target_id,
            cur.get("enabled", False),
            cur.get("amount", 0),
            cur.get("payment_method", ""),
            cur.get("display_note", ""),
            cur.get("display_place", "course"),
            xp_rw,
            cur.get("credits_reward", 0),
        )
        back_cb = f"a_cash_sale_setting|{target_type}|{cid}" + (f"|{idx}" if target_type == "lesson" else "")
        await msg.reply_text(
            f"✅ جایزه XP ذخیره شد.\n🎁 مقدار: {xp_rw} XP",
            reply_markup=mkb([back_btn(back_cb)]),
        )

    elif is_admin(user) and state == "wait_cash_sale_creditreward":
        target_type = ctx.user_data.pop("cst_target_type", "course")
        target_id = ctx.user_data.pop("cst_target_id", "")
        cid = ctx.user_data.pop("cst_cid", "")
        idx = ctx.user_data.pop("cst_idx", 0)
        ctx.user_data.pop("state", None)
        try:
            cr_rw = max(0, int(text.strip().replace(",", "").replace("،", "")))
        except Exception:
            await msg.reply_text("❌ مقدار باید عدد باشد.")
            ctx.user_data["state"] = "wait_cash_sale_creditreward"
            ctx.user_data["cst_target_type"] = target_type
            ctx.user_data["cst_target_id"] = target_id
            ctx.user_data["cst_cid"] = cid
            ctx.user_data["cst_idx"] = idx
            return
        cur = CASH_SALE_SETTINGS.get(f"{target_type}|{target_id}", {})
        set_cash_sale_setting(
            target_type, target_id,
            cur.get("enabled", False),
            cur.get("amount", 0),
            cur.get("payment_method", ""),
            cur.get("display_note", ""),
            cur.get("display_place", "course"),
            cur.get("xp_reward", 0),
            cr_rw,
        )
        back_cb = f"a_cash_sale_setting|{target_type}|{cid}" + (f"|{idx}" if target_type == "lesson" else "")
        await msg.reply_text(
            f"✅ جایزه اعتبار ذخیره شد.\n💎 مقدار: {cr_rw} اعتبار",
            reply_markup=mkb([back_btn(back_cb)]),
        )

    elif state == "wait_global_join":
        SETTINGS["global_required_joins"] = (
            [] if text == "حذف"
            else [l.strip() for l in text.split("\n") if l.strip()]
        )
        save("settings")
        ctx.user_data.pop("state", None)
        gj = SETTINGS["global_required_joins"]
        await msg.reply_text(
            f"✅ ذخیره شد.\n🔒 عضویت اجباری کلی: {', '.join(gj) if gj else 'ندارد'}",
            reply_markup=mkb([back_btn("a_global_settings")]),
        )

    elif state == "wait_global_ref":
        try:
            val = int(text)
        except Exception:
            val = 0
        SETTINGS["global_required_referrals"] = val
        save("settings")
        ctx.user_data.pop("state", None)
        await msg.reply_text(
            f"✅ ذخیره شد.\n👥 دعوت اجباری کلی: {val} نفر",
            reply_markup=mkb([back_btn("a_global_settings")]),
        )

    elif state == "wait_global_credit":
        try:
            val = max(0, int(text))
        except Exception:
            val = 0
        SETTINGS["global_required_credits"] = val
        save("settings")
        ctx.user_data.pop("state", None)
        await msg.reply_text(
            f"✅ ذخیره شد.\n💰 اعتبار اجباری کلی: {val}",
            reply_markup=mkb([back_btn("a_global_settings")]),
        )

    elif state == "wait_platform_token":
        # [کار ۲ — بند ۳] ذخیرهٔ توکن + اعمال فوری روی اتصال زنده
        p = ctx.user_data.get("platform_target", "")
        ctx.user_data.pop("state", None)
        ctx.user_data.pop("platform_target", None)
        val = "" if text.strip() == "حذف" else text.strip()
        SETTINGS[f"{p}_token"] = val
        save("settings")

        extra = ""
        if p == "telegram":
            if val:
                ok, rmsg = await reload_telegram()
                extra = f"\n\n{rmsg}"
            else:
                await stop_telegram()
                extra = "\n\n📴 توکن حذف شد و اتصال تلگرام قطع گردید."

        await msg.reply_text(
            f"✅ توکن {platform_name(p)} ذخیره شد.{extra}",
            reply_markup=mkb([
                [btn("📊 بررسی وضعیت", f"a_plat_status|{p}")],
                back_btn(f"a_plat|{p}"),
            ]),
        )

    elif state == "wait_proxy_manual":
        # [افزوده] ثبت پروکسی‌های دستی
        p = ctx.user_data.pop("proxy_platform", "telegram")
        ctx.user_data.pop("state", None)
        raw = text.strip()
        if raw in ("حذف", "پاک"):
            pm.clear_manual_proxies()
            await msg.reply_text(
                "🗑️ همهٔ پروکسی‌های دستی حذف شدند.",
                reply_markup=mkb([back_btn(f"a_plat_proxy|{p}")]),
            )
            return
        lines = [ln for ln in raw.replace(",", "\n").splitlines() if ln.strip()]
        valid, invalid = [], []
        for ln in lines:
            n = pm.normalize_proxy(ln)
            (valid if n else invalid).append(n or ln.strip())
        if not valid:
            ctx.user_data["state"] = "wait_proxy_manual"
            ctx.user_data["proxy_platform"] = p
            await msg.reply_text(
                "❌ هیچ پروکسی معتبری پیدا نشد.\n\n"
                "نمونهٔ درست:\n  1.2.3.4:1080\n  socks5://1.2.3.4:1080",
                reply_markup=mkb([back_btn(f"a_plat_proxy|{p}")]),
            )
            return
        saved = pm.set_manual_proxies(valid)
        body = "\n".join(f"• {x}" for x in saved)
        extra = ""
        if invalid:
            extra = "\n\n⚠️ نامعتبر (نادیده گرفته شد):\n" + "\n".join(f"• {x}" for x in invalid[:5])
        if len(valid) > pm.MAX_MANUAL:
            extra += f"\n\nℹ️ فقط {fa_num(pm.MAX_MANUAL)} مورد اول ذخیره شد."
        await msg.reply_text(
            f"✅ {fa_num(len(saved))} پروکسی دستی ذخیره شد:\n\n{body}{extra}\n\n"
            "برای بررسی سلامت آن‌ها روی «🧪 تست همین پروکسی‌ها» بزنید.",
            reply_markup=mkb([
                [btn("🧪 تست همین پروکسی‌ها", f"a_plat_proxy_testmanual|{p}")],
                [btn("⚙️ حالت اتصال", f"a_plat_proxy_mode|{p}")],
                back_btn(f"a_plat_proxy|{p}"),
            ]),
        )

    elif state == "wait_proxy_source":
        # [افزوده] تغییر URL منبع پروکسی
        p = ctx.user_data.pop("proxy_platform", "telegram")
        ctx.user_data.pop("state", None)
        raw = text.strip()
        if raw in ("پیشفرض", "پیش‌فرض", "حذف"):
            pm.reset_source_url()
            await msg.reply_text(
                f"✅ منبع به حالت پیش‌فرض برگشت:\n{pm.DEFAULT_PROXY_SOURCE}",
                reply_markup=mkb([back_btn(f"a_plat_proxy|{p}")]),
            )
            return
        if not raw.lower().startswith(("http://", "https://")):
            ctx.user_data["state"] = "wait_proxy_source"
            ctx.user_data["proxy_platform"] = p
            await msg.reply_text(
                "❌ URL باید با http:// یا https:// شروع شود.",
                reply_markup=mkb([back_btn(f"a_plat_proxy|{p}")]),
            )
            return
        pm.set_source_url(raw)
        await msg.reply_text(
            f"✅ منبع پروکسی ذخیره شد:\n{raw}",
            reply_markup=mkb([
                [btn("📥 دریافت همین حالا", f"a_plat_proxy_fetch|{p}")],
                back_btn(f"a_plat_proxy|{p}"),
            ]),
        )

    elif state == "wait_platform_uname":
        p = ctx.user_data.get("platform_target", "")
        ctx.user_data.pop("state", None)
        ctx.user_data.pop("platform_target", None)
        val = "" if text.strip() == "حذف" else text.strip().lstrip("@")
        SETTINGS[f"{p}_username"] = val
        save("settings")
        await msg.reply_text(
            f"✅ نام کاربری ربات {platform_name(p)} ذخیره شد.",
            reply_markup=mkb([back_btn(f"a_plat|{p}")]),
        )

    elif state == "wait_platform_support":
        p = ctx.user_data.get("platform_target", "")
        ctx.user_data.pop("state", None)
        ctx.user_data.pop("platform_target", None)
        val = "" if text.strip() == "حذف" else text.strip()
        SETTINGS[f"{p}_support"] = val
        save("settings")
        done = f"«{val}»" if val else "پیش‌فرض (گروه بله)"
        await msg.reply_text(
            f"✅ پشتیبانی {platform_name(p)} ذخیره شد: {done}\n\n"
            f"ℹ️ کاربران {platform_name(p)} از این پس این لینک را می‌بینند.",
            reply_markup=mkb([
                [btn("📞 لینک پشتیبانی همه پلتفرم‌ها", "a_support_links")],
                back_btn(f"a_plat|{p}"),
            ]),
        )

    # ===== مرکز پیام‌رسانی: state‌های متنی =====
    elif state == "wait_bc_direct_target":
        ctx.user_data.pop("state", None)
        bc = ctx.user_data.setdefault("bc", {"route": "users", "user_mode": "single"})
        res, status = resolve_direct_target_strict(text, bc.get("dest", "all"))
        if status == "ambiguous" and isinstance(res, list):
            # چند کاندید وجود دارد → انتخاب پلتفرم
            ctx.user_data["bc_candidates"] = res
            rows = []
            for i, (p, _cid, disp) in enumerate(res):
                rows.append([btn(f"{platform_name(p)} — {disp}", f"bc_pick|{i}")])
            rows.append(back_btn("a_messaging"))
            await msg.reply_text(
                "این کاربر در چند پلتفرم پیدا شد. یکی را انتخاب کنید:",
                reply_markup=mkb(rows),
            )
            return
        if not res:
            if status == "platform_inactive":
                err = "❌ ربات پلتفرم مقصد فعال نیست."
            else:
                err = "❌ کاربری با این آی‌دی/یوزرنیم یافت نشد یا هنوز ربات را استارت نکرده است."
            await msg.reply_text(
                f"{err}\nدوباره تلاش کنید:",
                reply_markup=mkb([back_btn("a_messaging")]),
            )
            ctx.user_data["state"] = "wait_bc_direct_target"
            return
        plat, cid, disp = res
        bc["target_platform"] = plat
        bc["target_chat_id"] = cid
        bc["target_display"] = disp
        await msg.reply_text(
            f"🎯 گیرنده: {disp} ({platform_name(plat)})\n\nنوع پیام را انتخاب کنید:",
            reply_markup=bcast_type_kb(),
        )

    elif state == "wait_bc_delay":
        # [ویژگی گم‌شده ۱] مقدار دلخواه تأخیر ارسال
        ctx.user_data.pop("state", None)
        try:
            val = float(text.strip().replace("،", ".").replace("٫", "."))
        except ValueError:
            ctx.user_data["state"] = "wait_bc_delay"
            await msg.reply_text(
                f"❌ لطفاً یک عدد بفرستید (بین {messaging_delay_min():g} تا {messaging_delay_max():g}).",
                reply_markup=mkb([back_btn("bc_delay")]),
            )
            return
        applied = messaging_set_delay(val)
        note = ""
        if abs(applied - val) > 0.001:
            note = f"\n\nℹ️ مقدار به محدودهٔ مجاز تنظیم شد ({messaging_delay_min():g} تا {messaging_delay_max():g})."
        await msg.reply_text(
            f"✅ تأخیر ارسال روی {applied:g} ثانیه تنظیم شد.{note}",
            reply_markup=mkb([
                [btn("⏱ بازگشت به تنظیم تأخیر", "bc_delay")],
                back_btn("a_messaging"),
            ]),
        )

    elif state == "wait_bc_title":
        bc = ctx.user_data.setdefault("bc", {})
        bc["title"] = "" if text.strip() == "-" else text.strip()
        ctx.user_data["state"] = "wait_bc_desc"
        await msg.reply_text(
            "📝 توضیحات (متن اصلی پیام) را بفرستید:\n"
            "(برای رد کردن توضیحات، یک «-» بفرستید)",
            reply_markup=mkb([back_btn("a_messaging")]),
        )

    elif state == "wait_bc_desc":
        bc = ctx.user_data.setdefault("bc", {})
        bc["desc"] = "" if text.strip() == "-" else text.strip()
        mtype = bc.get("type", "text")
        if mtype == "text":
            await messaging_show_preview(msg, ctx, is_q=False)
        else:
            ctx.user_data["state"] = "wait_bc_content"
            kind = "تصویر" if mtype == "photo" else "ویدیو"
            await msg.reply_text(
                f"{'🖼' if mtype=='photo' else '🎬'} حالا {kind} را بفرستید "
                "(عنوان و توضیحات قبلاً گرفته شد، نیازی به کپشن نیست):",
                reply_markup=mkb([back_btn("a_messaging")]),
            )

    elif state == "wait_bc_content":
        bc = ctx.user_data.setdefault("bc", {})
        mtype = bc.get("type", "text")
        if mtype != "text":
            await msg.reply_text(
                f"لطفاً {'تصویر' if mtype=='photo' else 'ویدیو'} را ارسال کنید (نه متن).",
                reply_markup=mkb([back_btn("a_messaging")]),
            )
            return
        bc["desc"] = text
        await messaging_show_preview(msg, ctx, is_q=False)

    elif state == "wait_ltitle":
        cid = ctx.user_data.get("ecid")
        set_src(ctx, "add", cid, text, None)
        ctx.user_data["state"] = "choose_type"
        await msg.reply_text(
            f"✅ عنوان: {text}\n\nنوع محتوا:",
            reply_markup=src_kb(f"a_open|{cid}"),
        )

    elif state == "wait_ljoin":
        cid = ctx.user_data.get("ecid")
        idx = ctx.user_data.get("eidx")
        if cid in COURSES and idx is not None:
            ls = COURSES[cid].get("lessons", [])
            if 0 <= idx < len(ls):
                ls[idx]["required_joins"] = (
                    [] if text == "حذف"
                    else [l.strip() for l in text.split("\n") if l.strip()]
                )
                save("courses")
        ctx.user_data.pop("state", None)
        await msg.reply_text("✅ ذخیره شد.", reply_markup=mkb([back_btn(f"a_lmenu|{cid}|{idx}")]))

    elif state == "wait_lref":
        cid = ctx.user_data.get("ecid")
        idx = ctx.user_data.get("eidx")
        if cid in COURSES and idx is not None:
            ls = COURSES[cid].get("lessons", [])
            if 0 <= idx < len(ls):
                try:
                    val = int(text)
                except Exception:
                    val = 0
                ls[idx]["referral_required"] = val
                if val > 0:
                    ls[idx]["referral_required_set_at"] = int(time.time())
                save("courses")
        ctx.user_data.pop("state", None)
        await msg.reply_text("✅ ذخیره شد.", reply_markup=mkb([back_btn(f"a_lmenu|{cid}|{idx}")]))

    elif state == "wait_lcredit":
        cid = ctx.user_data.get("ecid")
        idx = ctx.user_data.get("eidx")
        val = 0
        if cid in COURSES and idx is not None:
            ls = COURSES[cid].get("lessons", [])
            if 0 <= idx < len(ls):
                try:
                    val = max(0, int(text))
                except Exception:
                    val = 0
                ls[idx]["required_credits"] = val
                save("courses")
        ctx.user_data.pop("state", None)
        await msg.reply_text(
            f"✅ اعتبار اجباری سرفصل: {val}",
            reply_markup=mkb([back_btn(f"a_lmenu|{cid}|{idx}")])
        )

    elif state == "wait_lt_edit":
        cid = ctx.user_data.get("ecid")
        idx = ctx.user_data.get("eidx")
        if cid in COURSES and idx is not None:
            ls = COURSES[cid].get("lessons", [])
            if 0 <= idx < len(ls):
                ls[idx]["title"] = text
                save("courses")
        ctx.user_data.pop("state", None)
        await msg.reply_text("✅ عنوان ذخیره شد.", reply_markup=mkb([back_btn(f"a_lmenu|{cid}|{idx}")]))

    elif state == "wait_src_text":
        s = get_src(ctx)
        if s:
            ok, cid, idx, r = apply_lesson(ctx, {"type": "text", "content": text})
            if ok:
                await msg.reply_text(f"✅ سرفصل متنی ذخیره شد.", reply_markup=done_kb(cid, idx))
            else:
                await msg.reply_text(f"❌ {r}")

    elif state == "wait_src_link":
        s = get_src(ctx)
        if s:
            ok, cid, idx, r = apply_lesson(ctx, {"type": "link", "content": text})
            if ok:
                await msg.reply_text(f"✅ سرفصل لینکی ذخیره شد.", reply_markup=done_kb(cid, idx))
            else:
                await msg.reply_text(f"❌ {r}")

    # ===== ماموریت‌ها state =====
    elif state == "wait_mission_title":
        ctx.user_data.setdefault("mission_building", {})["title"] = text
        ctx.user_data["state"] = "wait_mission_desc"
        await msg.reply_text(
            f"✅ عنوان: {text}\n\nتوضیحات ماموریت را بفرستید:",
            reply_markup=mkb([back_btn("a_missions")]),
        )

    elif state == "wait_mission_desc":
        ctx.user_data.setdefault("mission_building", {})["description"] = text
        ctx.user_data["state"] = "wait_mission_type_select"
        await msg.reply_text(
            "✅ توضیحات ذخیره شد.\n\nنوع ماموریت را انتخاب کنید:\n\n"
            "📝 متنی: XP پاداش ۱-۲۰\n"
            "🖼 تصویری: XP پاداش ۲۰-۵۰\n"
            "🎬 ویدیویی: XP پاداش ۵۰-۱۰۰",
            reply_markup=mkb([
                [btn("📝 متنی", "a_mission_type|text")],
                [btn("🖼 تصویری", "a_mission_type|photo")],
                [btn("🎬 ویدیویی", "a_mission_type|video")],
                [btn("🔗 اتصال پلتفرم", "a_mission_type|platform_link")],
                back_btn("a_missions"),
            ]),
        )

    elif state == "wait_mission_xp":
        mb = ctx.user_data.get("mission_building", {})
        mtype = mb.get("type", "text")
        mn, mx = MISSION_XP_LIMITS.get(mtype, (1, 100))
        try:
            xp_val = int(text)
        except Exception:
            xp_val = -1
        if not (mn <= xp_val <= mx):
            await msg.reply_text(
                f"❌ مقدار نامعتبر!\nبرای نوع {mtype}، XP باید بین {mn} و {mx} باشد.\n\nدوباره بفرستید:",
            )
            return
        mb["xp_reward"] = xp_val
        ctx.user_data["state"] = "wait_mission_credits"
        await msg.reply_text(
            f"✅ XP: +{xp_val}\n\nحالا مقدار اعتبار پاداش را بفرستید (عدد):",
            reply_markup=mkb([back_btn("a_missions")]),
        )

    elif state == "wait_mission_credits":
        mb = ctx.user_data.get("mission_building", {})
        try:
            cr_val = max(0, int(text))
        except Exception:
            cr_val = 0
        mb["credits_reward"] = cr_val
        mtype = mb.get("type", "text")
        if mtype == "platform_link":
            p = mb.get("target_platform", "")
            mid = next_mid()
            MISSIONS.append({
                "id": mid,
                "title": mb.get("title", ""),
                "description": mb.get("description", ""),
                "type": "platform_link",
                "target_platform": p,
                "content": "",
                "file_id": "",
                "caption": "",
                "xp_reward": mb.get("xp_reward", 0),
                "credits_reward": mb.get("credits_reward", 0),
                "active": True,
            })
            save("missions")
            ctx.user_data.pop("state", None)
            ctx.user_data.pop("mission_building", None)
            await msg.reply_text(
                f"✅ ماموریت اتصال «{mb.get('title', '')}» ({platform_name(p)}) ثبت شد!\n"
                f"🎁 +{mb.get('xp_reward', 0)} XP | +{cr_val} اعتبار",
                reply_markup=mkb([[btn("🎯 مشاهده ماموریت‌ها", "a_missions")], back_btn("a_panel")]),
            )
            return
        ctx.user_data["state"] = "wait_mission_content"
        if mtype == "text":
            await msg.reply_text(
                f"✅ اعتبار: +{cr_val}\n\nحالا متن محتوای ماموریت را بفرستید:",
                reply_markup=mkb([back_btn("a_missions")]),
            )
        else:
            await msg.reply_text(
                f"✅ اعتبار: +{cr_val}\n\nحالا فایل {'عکس' if mtype=='photo' else 'ویدیو'} را ارسال کنید:",
                reply_markup=mkb([back_btn("a_missions")]),
            )

    elif state == "wait_mission_content":
        mb = ctx.user_data.get("mission_building", {})
        mtype = mb.get("type", "text")
        if mtype == "text":
            mb["content"] = text
            mb["file_id"] = ""
            # ذخیره ماموریت
            mid = next_mid()
            MISSIONS.append({
                "id": mid,
                "title": mb.get("title", ""),
                "description": mb.get("description", ""),
                "type": mtype,
                "content": mb.get("content", ""),
                "file_id": "",
                "caption": "",
                "xp_reward": mb.get("xp_reward", 0),
                "credits_reward": mb.get("credits_reward", 0),
                "active": True,
            })
            save("missions")
            ctx.user_data.pop("state", None)
            ctx.user_data.pop("mission_building", None)
            await msg.reply_text(
                f"✅ ماموریت «{mb.get('title', '')}» ثبت شد!\n"
                f"🎁 +{mb.get('xp_reward', 0)} XP | +{mb.get('credits_reward', 0)} اعتبار",
                reply_markup=mkb([[btn("🎯 مشاهده ماموریت‌ها", "a_missions")], back_btn("a_panel")]),
            )
        else:
            await msg.reply_text("❌ لطفاً فایل رسانه ارسال کنید (نه متن).")

    # ===== گنجینه state =====
    elif state == "wait_item_name":
        ctx.user_data.setdefault("item_building", {})["title"] = text
        ctx.user_data["state"] = "wait_item_price"
        await msg.reply_text(
            f"✅ نام: {text}\n\nقیمت آیتم (اعتبار):",
            reply_markup=mkb([back_btn("a_shop")]),
        )

    elif state == "wait_item_price":
        try:
            price = max(0, int(text))
        except Exception:
            price = 0
        ctx.user_data.setdefault("item_building", {})["price"] = price
        ctx.user_data["state"] = "wait_item_kind"
        await msg.reply_text(
            f"✅ قیمت: {price} اعتبار\n\nنوع محتوا:",
            reply_markup=mkb([
                [btn("📝 متنی", "a_item_kind|text"), btn("🔗 لینک", "a_item_kind|link")],
                [btn("📎 فایل", "a_item_kind|file"), btn("📋 توضیح دسترسی", "a_item_kind|access_note")],
                back_btn("a_shop"),
            ]),
        )

    elif state == "wait_item_description":
        ctx.user_data.setdefault("item_building", {})["description"] = text
        ctx.user_data["state"] = "wait_item_content"
        await msg.reply_text(
            f"✅ توضیحات ذخیره شد.\n\nمحتوای آیتم (لینک، متن، یا file_id):",
            reply_markup=mkb([back_btn("a_shop")]),
        )

    elif state == "wait_item_content":
        ib = ctx.user_data.get("item_building", {})
        ib["content"] = text
        ctx.user_data["state"] = "wait_item_stock"
        await msg.reply_text(
            "✅ محتوا ذخیره شد.\n\nموجودی آیتم:\n(عدد = محدود | 0 = نامحدود):",
            reply_markup=mkb([back_btn("a_shop")]),
        )

    elif state == "wait_item_stock":
        ib = ctx.user_data.get("item_building", {})
        try:
            stock = int(text)
        except Exception:
            stock = 0
        sid = next_sid()
        SHOP[sid] = {
            "id": sid,
            "title": ib.get("title", "آیتم جدید"),
            "description": ib.get("description", ""),
            "price": ib.get("price", 0),
            "kind": ib.get("kind", "text"),
            "content": ib.get("content", ""),
            "active": True,
            "stock": None if stock == 0 else stock,
            "purchased_by": [],
            "repeatable": False,
        }
        save("shop")
        ctx.user_data.pop("state", None)
        ctx.user_data.pop("item_building", None)
        await msg.reply_text(
            f"✅ آیتم «{SHOP[sid]['title']}» ثبت شد!\n"
            f"💰 قیمت: {SHOP[sid]['price']} اعتبار",
            reply_markup=mkb([[btn("💎 مشاهده گنجینه", "a_shop")], back_btn("a_panel")]),
        )

    elif state == "wait_cmd_trigger":
        ctx.user_data.setdefault("cmd_building", {})["trigger"] = text
        ctx.user_data["state"] = "wait_cmd_type"
        await msg.reply_text(
            f"✅ Trigger: «{text}»\n\nنوع دستور:",
            reply_markup=mkb([
                [btn("💬 پاسخ متنی", "a_cmd_type|text_reply"),
                 btn("⚡ عملیاتی", "a_cmd_type|action")],
                back_btn("a_cmd_menu"),
            ]),
        )

    elif state == "wait_cmd_text_response":
        ctx.user_data.setdefault("cmd_building", {})["response_text"] = text
        await msg.reply_text(
            f"✅ پاسخ: «{text[:30]}»\n\nمحدوده اجرا:",
            reply_markup=mkb([
                [btn("📱 خصوصی", "a_cmd_scope|private"),
                 btn("👥 گروه", "a_cmd_scope|group"),
                 btn("🌐 هر دو", "a_cmd_scope|both")],
                back_btn("a_cmd_menu"),
            ]),
        )

    # ===== state‌های مدیریت کاربران =====

    elif is_admin(user) and state in ("waiting_restore_bot", "waiting_restore_giso"):
        kind = 'bot' if state == 'waiting_restore_bot' else 'giso'
        await msg.reply_text(
            f"❌ فایل ارسال نشد. لطفاً فایل بکاپ {kind}.db را به صورت document ارسال کنید.",
            reply_markup=_site_restore_method_kb(kind)
        )

    elif is_admin(user) and state == "wait_adm_del_phone":
        ctx.user_data.pop("state", None)
        phone = normalize_phone(text)
        if not phone:
            await msg.reply_text("❌ شماره معتبر نیست.", reply_markup=mkb([back_btn("adm_del_menu")]))
            return
        uid = admin_resolve_user_id_by_phone(phone)
        if not uid:
            await msg.reply_text("❌ کاربری با این شماره پیدا نشد.", reply_markup=mkb([back_btn("adm_del_menu")]))
            return
        result = admin_delete_user_everywhere(uid, phone, {"user_id": user.id}, mode="single_phone")
        await msg.reply_text(_admin_delete_summary(result), reply_markup=mkb([back_btn("adm_del_menu")]))

    elif is_admin(user) and state == "wait_user_search_id":
        ctx.user_data.pop("state", None)
        try:
            uid_num = int(text.strip())
        except ValueError:
            await msg.reply_text("❌ آی‌دی باید عدد باشد.", reply_markup=mkb([back_btn("a_users_manage")]))
            return
        uid_str = str(uid_num)
        u_found = USERS.get(uid_str)
        if not u_found:
            await msg.reply_text("❌ کاربری با این آی‌دی پیدا نشد.", reply_markup=mkb([back_btn("a_users_manage")]))
            return
        await msg.reply_text(
            f"✅ کاربر پیدا شد: {u_found.get('first_name', '---')}",
            reply_markup=mkb([[btn(f"👤 مشاهده کاربر", f"a_user_detail|{uid_str}")], back_btn("a_users_manage")]),
        )

    elif is_admin(user) and state == "wait_user_xp_delta":
        uid_str = ctx.user_data.pop("target_uid", None)
        ctx.user_data.pop("state", None)
        if not uid_str:
            return
        try:
            delta = int(text.strip())
        except ValueError:
            await msg.reply_text("❌ مقدار باید عدد باشد.", reply_markup=mkb([back_btn(f"a_user_xp|{uid_str}")]))
            return
        ok = add_user_xp(int(uid_str) if uid_str.isdigit() else 0, delta)
        u_t = USERS.get(uid_str, {})
        _migrate_user(u_t)
        sign = "+" if delta >= 0 else ""
        await msg.reply_text(
            f"{'✅' if ok else '❌'} {'XP تغییر کرد' if ok else 'کاربر پیدا نشد'}.\n"
            f"{'XP جدید: ' + str(u_t.get('xp', 0)) if ok else ''}\n"
            f"تغییر: {sign}{delta}",
            reply_markup=mkb([[btn("👤 بازگشت به کاربر", f"a_user_detail|{uid_str}")], back_btn("a_users_manage")]),
        )

    elif is_admin(user) and state == "wait_user_xp_value":
        uid_str = ctx.user_data.pop("target_uid", None)
        ctx.user_data.pop("state", None)
        if not uid_str:
            return
        try:
            val = int(text.strip())
        except ValueError:
            await msg.reply_text("❌ مقدار باید عدد باشد.", reply_markup=mkb([back_btn(f"a_user_xp|{uid_str}")]))
            return
        ok = set_user_xp(int(uid_str) if uid_str.isdigit() else 0, val)
        await msg.reply_text(
            f"{'✅ XP تنظیم شد' if ok else '❌ کاربر پیدا نشد'}.\n{'XP جدید: ' + str(val) if ok else ''}",
            reply_markup=mkb([[btn("👤 بازگشت به کاربر", f"a_user_detail|{uid_str}")], back_btn("a_users_manage")]),
        )

    elif is_admin(user) and state == "wait_user_credit_delta":
        uid_str = ctx.user_data.pop("target_uid", None)
        ctx.user_data.pop("state", None)
        if not uid_str:
            return
        try:
            delta = int(text.strip())
        except ValueError:
            await msg.reply_text("❌ مقدار باید عدد باشد.", reply_markup=mkb([back_btn(f"a_user_credit|{uid_str}")]))
            return
        ok = add_user_credits(int(uid_str) if uid_str.isdigit() else 0, delta)
        u_t = USERS.get(uid_str, {})
        _migrate_user(u_t)
        sign = "+" if delta >= 0 else ""
        await msg.reply_text(
            f"{'✅' if ok else '❌'} {'اعتبار تغییر کرد' if ok else 'کاربر پیدا نشد'}.\n"
            f"{'اعتبار جدید: ' + str(u_t.get('credits', 0)) if ok else ''}\n"
            f"تغییر: {sign}{delta}",
            reply_markup=mkb([[btn("👤 بازگشت به کاربر", f"a_user_detail|{uid_str}")], back_btn("a_users_manage")]),
        )

    elif is_admin(user) and state == "wait_user_credit_value":
        uid_str = ctx.user_data.pop("target_uid", None)
        ctx.user_data.pop("state", None)
        if not uid_str:
            return
        try:
            val = int(text.strip())
        except ValueError:
            await msg.reply_text("❌ مقدار باید عدد باشد.", reply_markup=mkb([back_btn(f"a_user_credit|{uid_str}")]))
            return
        ok = set_user_credits(int(uid_str) if uid_str.isdigit() else 0, val)
        await msg.reply_text(
            f"{'✅ اعتبار تنظیم شد' if ok else '❌ کاربر پیدا نشد'}.\n{'اعتبار جدید: ' + str(val) if ok else ''}",
            reply_markup=mkb([[btn("👤 بازگشت به کاربر", f"a_user_detail|{uid_str}")], back_btn("a_users_manage")]),
        )

    elif is_admin(user) and state == "wait_user_mute_duration":
        uid_str = ctx.user_data.pop("target_uid", None)
        ctx.user_data.pop("state", None)
        if not uid_str:
            return
        try:
            minutes = max(1, int(text.strip()))
        except ValueError:
            await msg.reply_text("❌ مدت زمان باید عدد (دقیقه) باشد.", reply_markup=mkb([back_btn(f"a_user_detail|{uid_str}")]))
            return
        until = int(time.time()) + minutes * 60
        ok = set_user_mute(int(uid_str) if uid_str.isdigit() else 0, until)
        await msg.reply_text(
            f"{'🔇 کاربر میوت شد' if ok else '❌ کاربر پیدا نشد'} برای {minutes} دقیقه.",
            reply_markup=mkb([[btn("👤 بازگشت به کاربر", f"a_user_detail|{uid_str}")], back_btn("a_users_manage")]),
        )

    # ===== state‌های دسترسی بخش‌ها =====

    elif is_admin(user) and state == "wait_feat_block_duration":
        # محدود کردن یک بخش برای کاربر خاص با ورود دستی مدت (ساعت)
        uid_str = ctx.user_data.pop("target_uid", None)
        fkey = ctx.user_data.pop("block_fkey", None)
        ctx.user_data.pop("state", None)
        if not uid_str or not fkey:
            return
        raw = text.strip()
        # «دائم» / «0» → محدودیت دائمی
        if raw in ("دائم", "دایم", "همیشه", "0", "۰"):
            hrs = 0
        else:
            try:
                hrs = max(0, int(raw))
            except ValueError:
                # ورودی نامعتبر → state را برگردان تا دوباره تلاش کند
                ctx.user_data["state"] = "wait_feat_block_duration"
                ctx.user_data["target_uid"] = uid_str
                ctx.user_data["block_fkey"] = fkey
                await msg.reply_text(
                    "❌ مدت باید عدد (ساعت) باشد.\nبرای محدودیت دائم بنویسید: دائم",
                    reply_markup=mkb([back_btn(f"a_user_panel_restrict|{uid_str}")]),
                )
                return
        until_ts = int(time.time()) + hrs * 3600 if hrs > 0 else 0
        set_user_feature_restriction(
            int(uid_str) if uid_str.isdigit() else 0, fkey, True, until_ts
        )
        fkey_label = dict(FEATURE_KEYS).get(fkey, fkey)
        dur_txt = f"{hrs} ساعت" if hrs > 0 else "دائم"
        await msg.reply_text(
            f"🔒 بخش «{fkey_label}» برای این کاربر محدود شد.\n⏰ مدت: {dur_txt}",
            reply_markup=mkb([
                [btn("🔐 بازگشت به محدودیت‌ها", f"a_user_panel_restrict|{uid_str}")],
                back_btn(f"a_user_detail|{uid_str}"),
            ]),
        )

    elif is_admin(user) and state == "wait_feature_value":
        fkey = ctx.user_data.pop("feature_key", None)
        field = ctx.user_data.pop("feature_field", None)
        ctx.user_data.pop("state", None)
        if not fkey or not field:
            return
        try:
            val = max(0, int(text.strip()))
        except ValueError:
            await msg.reply_text("❌ مقدار باید عدد باشد.", reply_markup=mkb([back_btn(f"a_feature_set|{fkey}")]))
            return
        rule = FEATURE_ACCESS.get(fkey, {"min_xp": 0, "min_credits": 0, "min_level": 0, "min_edu_rank": 0})
        rule[field] = val
        set_feature_rule(fkey, rule)
        await msg.reply_text(
            f"✅ محدودیت ذخیره شد.\n🔑 بخش: {FEATURE_LABELS.get(fkey, fkey)}\n📊 مقدار: {val}",
            reply_markup=mkb([[btn("🔑 بازگشت به بخش", f"a_feature_set|{fkey}")], back_btn("a_feature_access")]),
        )


# ========================= هندلر رسانه =========================

async def handle_media(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    raw_user = update.effective_user
    if not msg or not raw_user:
        return

    platform = detect_platform(ctx.bot)
    set_current_platform(platform)

    # روی پلتفرم ثانویه: تا حساب با شماره فعال نشده، فقط دکمهٔ اشتراک شماره
    if (not update.effective_chat or update.effective_chat.type == "private") \
            and platform != "bale" and canonical_user_id(platform, raw_user.id) is None:
        await msg.reply_text(
            "📱 برای فعال‌سازی حساب، لطفاً با دکمهٔ «اشتراک‌گذاری شماره» شمارهٔ خودتان را بفرستید.",
            reply_markup=phone_kb(),
        )
        return

    user = effective_user(raw_user, platform)

    # مرحله اول — تا شماره تلفن ثبت نشده، اجازه ارسال رسانه نده
    if (not update.effective_chat or update.effective_chat.type == "private") and not has_phone(user.id):
        register_user(user)
        await show_phone_registration(msg, user)
        return

    state = ctx.user_data.get("state")

    if str(state or '').startswith('wait_maintenance_image_'):
        if int(user.id) not in ADMIN_IDS:
            ctx.user_data.pop('state',None);await msg.reply_text("⛔ فقط ادمین اصلی مجاز است.");return
        scope=str(state).rsplit('_',1)[-1]
        await _handle_maintenance_image_upload(msg,ctx,scope)
        return

    if is_admin(user) and state in ("waiting_restore_bot", "waiting_restore_giso"):
        kind = 'bot' if state == 'waiting_restore_bot' else 'giso'
        await _handle_restore_upload(msg, ctx, kind)
        return

    # 🤖 یار هوشمند — دریافت عکس فیش پرداخت
    if state in AIM_MEDIA_STATES:
        if await handle_aim_media(state, msg, ctx, user):
            return

    # مرکز پیام‌رسانی — دریافت عکس/ویدیوی پیام
    if is_admin(user) and state == "wait_bc_content":
        bc = ctx.user_data.setdefault("bc", {})
        mtype = bc.get("type", "text")
        caption = msg.caption or ""
        file_id = None
        if mtype == "photo" and msg.photo:
            file_id = msg.photo[-1].file_id
        elif mtype == "video" and msg.video:
            file_id = msg.video.file_id
        if not file_id:
            await msg.reply_text(
                f"❌ لطفاً {'تصویر' if mtype=='photo' else 'ویدیو'} ارسال کنید.",
                reply_markup=mkb([back_btn("a_messaging")]),
            )
            return
        bc["file_id"] = file_id
        # file_id فقط روی همین پلتفرم معتبر است؛ برای ارسال به سایر پلتفرم‌ها باید re-upload شود
        bc["origin_platform"] = detect_platform(ctx.bot)
        # عنوان/توضیحات قبلاً گرفته شده؛ اگر توضیحات خالی بود و کپشن داشت، از کپشن استفاده شود
        if not (bc.get("desc") or "").strip() and caption.strip():
            bc["desc"] = caption.strip()
        await messaging_show_preview(msg, ctx, is_q=False)
        return

    # ذخیره فایل برای سرفصل
    if is_admin(user) and state in ("wait_src_file", "wait_src_forward"):
        await save_forwarded(msg, ctx)
        return

    # ذخیره فایل برای ماموریت
    if is_admin(user) and state == "wait_mission_content":
        mb = ctx.user_data.get("mission_building", {})
        mtype = mb.get("type", "text")
        file_id = None
        caption = msg.caption or ""

        if mtype == "photo" and msg.photo:
            file_id = msg.photo[-1].file_id
        elif mtype == "video" and msg.video:
            file_id = msg.video.file_id
        else:
            await msg.reply_text(f"❌ لطفاً {'عکس' if mtype=='photo' else 'ویدیو'} ارسال کنید.")
            return

        mid = next_mid()
        MISSIONS.append({
            "id": mid,
            "title": mb.get("title", ""),
            "description": mb.get("description", ""),
            "type": mtype,
            "content": "",
            "file_id": file_id,
            "caption": caption,
            "xp_reward": mb.get("xp_reward", 0),
            "credits_reward": mb.get("credits_reward", 0),
            "active": True,
        })
        save("missions")
        ctx.user_data.pop("state", None)
        ctx.user_data.pop("mission_building", None)
        await msg.reply_text(
            f"✅ ماموریت «{mb.get('title', '')}» با فایل رسانه ثبت شد!\n"
            f"🎁 +{mb.get('xp_reward', 0)} XP | +{mb.get('credits_reward', 0)} اعتبار",
            reply_markup=mkb([[btn("🎯 مشاهده ماموریت‌ها", "a_missions")], back_btn("a_panel")]),
        )
        return

    # [مشکل 5] دریافت فیش پرداخت نقدی (دوره یا سرفصل)
    if not is_admin(user) and state in ("wait_pay_fiche", "wait_cash_fiche"):
        target_type = ctx.user_data.get("cash_fiche_target_type", "course")
        target_id = ctx.user_data.get("cash_fiche_target_id", "")
        cid = ctx.user_data.get("cash_fiche_course_id") or ctx.user_data.get("pay_course_id", "")
        if not cid or cid not in COURSES:
            await msg.reply_text("❌ اطلاعات دوره پیدا نشد. دوباره از منو شروع کنید.")
            ctx.user_data.pop("state", None)
            return
        # استخراج file_id عکس یا متن فیش — [مورد 2+3]
        fiche_file_id = ""
        is_photo = False
        is_doc_image = bool(
            msg.document
            and (msg.document.mime_type or "").lower().startswith("image/")
        )
        if msg.photo:
            fiche_file_id = msg.photo[-1].file_id
            is_photo = True
        elif is_doc_image:
            # [مشکل 4] فایل تصویری (document عکس) هم به‌عنوان فیش قبول می‌شود
            fiche_file_id = msg.document.file_id
            is_photo = True
        elif msg.document or msg.audio or msg.video or msg.voice or msg.sticker:
            await msg.reply_text(
                "❌ فقط عکس فیش یا رسید متنی قابل قبول است.\n"
                "لطفاً عکس فیش را ارسال کنید یا رسید را به صورت متن (حداقل ۵ کلمه) بنویسید."
            )
            return
        elif msg.text:
            # بررسی دکمه بازگشت — [مورد 3]
            if msg.text.strip() in ("بازگشت", "🏠 خانه", "خانه", "منو"):
                ctx.user_data.pop("state", None)
                ctx.user_data.pop("cash_fiche_target_type", None)
                ctx.user_data.pop("cash_fiche_target_id", None)
                ctx.user_data.pop("cash_fiche_course_id", None)
                ctx.user_data.pop("cash_fiche_lesson_idx", None)
                await msg.reply_text(
                    "🏠 عملیات لغو شد. برای ادامه از منوی اصلی استفاده کنید.",
                    reply_markup=reply_kb(user),
                )
                return
            # بررسی حداقل ۵ کلمه — [مورد 3]
            if len(msg.text.strip().split()) < 5:
                await msg.reply_text(
                    "❌ متن رسید خیلی کوتاه است.\n"
                    "لطفاً عکس فیش ارسال کنید یا رسید متنی با حداقل ۵ کلمه بنویسید."
                )
                return
        else:
            await msg.reply_text("❌ لطفاً عکس فیش یا متن رسید ارسال کنید.")
            return
        # دریافت تنظیمات فروش نقدی
        setting = get_cash_sale_setting(target_type, target_id)
        course = COURSES.get(cid, {})
        # شناسه و عنوان درس
        lesson_id, lesson_title = "", ""
        if target_type == "lesson":
            lesson_idx_str = ctx.user_data.get("cash_fiche_lesson_idx", "0")
            try:
                lesson_idx = int(lesson_idx_str)
            except ValueError:
                lesson_idx = 0
            lessons = course.get("lessons", [])
            if lesson_idx < len(lessons):
                lesson_id = lessons[lesson_idx].get("lid", str(lesson_idx))
                lesson_title = lessons[lesson_idx].get("title", "")
        # ثبت درخواست
        req = {
            "user_id":      user.id,
            "user_name":    user.first_name or "",
            "username":     user.username or "",
            "canonical_user_id": user.id,
            "platform":     platform,
            "chat_id":      raw_user.id,
            "course_id":    cid,
            "course_title": course.get("title", ""),
            "target_type":  target_type,
            "lesson_id":    lesson_id,
            "lesson_title": lesson_title,
            "amount":       setting.get("amount", 0) if setting else 0,
            "payment_method": setting.get("payment_method", "") if setting else "",
            "fiche_file_id": fiche_file_id,
            "status":       "pending",
            "requested_at": int(time.time()),
            "reviewed_at":  0,
            "admin_note":   "",
        }
        CASH_SALES.append(req)
        save("cash_sales")
        ctx.user_data.pop("state", None)
        ctx.user_data.pop("pay_course_id", None)
        ctx.user_data.pop("cash_fiche_target_type", None)
        ctx.user_data.pop("cash_fiche_target_id", None)
        ctx.user_data.pop("cash_fiche_course_id", None)
        ctx.user_data.pop("cash_fiche_lesson_idx", None)
        subject_text = f"سرفصل: {lesson_title}" if lesson_title else f"دوره: {course.get('title', '---')}"
        await msg.reply_text(
            f"✅ فیش شما ثبت شد!\n\n"
            f"📚 {subject_text}\n"
            f"⏳ درخواست شما در صف بررسی ادمین است.\n"
            f"پس از تأیید، دسترسی فعال می‌شود. 💙",
            reply_markup=mkb([home_btn()]),
        )
        # اطلاع به ادمین‌ها — یک پیام واحد با دکمه تایید/رد
        req_id = req.get("_db_id", 0)
        import datetime as _dt
        _ts = _dt.datetime.fromtimestamp(req["requested_at"]).strftime("%Y-%m-%d %H:%M")
        admin_caption = f"{build_cash_admin_caption(req)}\n⏰ زمان: {_ts}"
        admin_kb = mkb([
            [btn("✅ تایید خرید", f"a_cash_approve|{req_id}"),
             btn("❌ رد خرید",   f"a_cash_reject|{req_id}")]
        ])
        for aid in ADMIN_IDS:
            try:
                if is_photo:
                    await ctx.bot.send_photo(
                        aid, fiche_file_id,
                        caption=admin_caption,
                        reply_markup=admin_kb,
                    )
                elif fiche_file_id:
                    doc_text = admin_caption + f"\n\n📄 متن فیش:\n{msg.text or '---'}"
                    await ctx.bot.send_message(aid, doc_text, reply_markup=admin_kb)
                else:
                    text_fiche = admin_caption + f"\n\n📄 متن فیش:\n{msg.text or '---'}"
                    await ctx.bot.send_message(aid, text_fiche, reply_markup=admin_kb)
            except Exception as e:
                logger.error(f"Notify admin cash sale error: {e}")
        return


# ========================= عضو جدید =========================

async def handle_new_member(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if not msg:
        return
    platform = detect_platform(ctx.bot)
    set_current_platform(platform)
    group_name = msg.chat.title or "این گروه"
    bot_link = platform_bot_link(platform)
    if not bot_link:
        bot_link = f"https://ble.ir/{BOT_USERNAME}" if platform == "bale" else f"(نام کاربری ربات {platform_name(platform)} ثبت نشده)"

    # ثبت این گروه/کانال برای ارسال گروهی مرکز پیام‌رسانی
    try:
        chat = msg.chat
        ctype = getattr(chat, "type", "group") or "group"
        if ctype in ("group", "supergroup", "channel"):
            record_bot_group(platform, chat.id, group_name, ctype)
    except Exception as e:
        logger.error(f"record_bot_group (new_member) error: {e}")

    # خلاصه آخرین دوره‌ها
    course_lines = []
    for cid, c in list(COURSES.items())[-3:]:
        ls_count = len(c.get("lessons", []))
        course_lines.append(f"  📖 {c.get('title', '---')} ({ls_count} سرفصل)")
    courses_text = ("\n\n📚 آخرین دوره‌های آموزشی:\n" + "\n".join(course_lines)) if course_lines else ""

    # خلاصه نظرسنجی‌ها
    survey_lines = []
    for cid, votes in list(SURVEYS.items())[-2:]:
        c = COURSES.get(cid, {})
        if votes:
            total = len(votes)
            exc = sum(1 for v in votes.values() if v.get("vote") == "excellent")
            pct = int(exc * 100 / total) if total else 0
            survey_lines.append(f"  ⭐ {c.get('title', cid)[:20]} — {pct}٪ رضایت ({total} نظر)")
    surveys_text = ("\n\n⭐ نظر کاربران:\n" + "\n".join(survey_lines)) if survey_lines else ""

    for member in msg.new_chat_members:
        if member.is_bot:
            continue
        register_user(member)
        try:
            welcome_text = (
                f"🎉 سلام {member.first_name} عزیز! خوش آمدی به «{group_name}» 👋\n\n"
                f"━━━━━━━━━━━━━━━━\n"
                f"🎓 این گروه برای یادگیری مهارت‌های درآمدساز و رشد حرفه‌ای تخصصی است.\n\n"
                f"🤖 ربات آموزشی ما امکانات ویژه‌ای دارد:\n"
                f"  📚 دوره‌های آموزشی رایگان و ساختاریافته\n"
                f"  🏆 سیستم رتبه‌بندی و XP برای رقابت\n"
                f"  🎯 ماموریت‌های امتیازی روزانه\n"
                f"  💎 گنجینه جوایز ویژه\n"
                f"  👥 سیستم دعوت و پاداش\n"
                f"{courses_text}"
                f"{surveys_text}\n\n"
                f"━━━━━━━━━━━━━━━━\n"
                f"👇 همین الان ربات را استارت کن و شروع کن:\n"
                f"🔗 {bot_link}"
            )
            try:
                await msg.reply_text(welcome_text)
            except Exception as e1:
                # برخی پلتفرم‌ها (بله) ممکن است reply به پیام سیستمی را رد کنند
                logger.error(f"Welcome reply_text failed ({platform}): {e1}; retry send_message")
                await ctx.bot.send_message(msg.chat_id, welcome_text)
        except Exception as e:
            logger.error(f"Welcome new member error ({platform}) chat={msg.chat_id}: {e}", exc_info=True)
# Phase 10.1 User Bot
