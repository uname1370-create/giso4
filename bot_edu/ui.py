"""
ui.py — کیبوردها و توابع نمایشی
وابستگی مجاز: config، core و telegram
هرگز از handlers import نکنید.
"""
import time
import html
import json
import logging

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton

from config import (
    BOT_USERNAME, SUPPORT_GROUP, ADMIN_IDS,
    COURSES, USERS, SHOP, SURVEYS, MISSIONS, SETTINGS, CASH_SALES,
    USER_FEATURE_RESTRICTIONS, CASH_SALE_SETTINGS,
    save,
)
from core import (
    is_admin, ltype, next_lid,
    full_access_check, valid_refs, completed_lessons, total_lessons,
    get_prog, get_seq_prog, get_completed_lids, has_done_lesson,
    mark_lesson_done, award_xp_and_credits,
    user_rank, normal_users_sorted, get_level_progress,
    get_educational_rank,
    apply_lesson,
    get_active_missions, has_completed_mission,
    _migrate_user,
    FEATURE_KEYS, FEATURE_LABELS, get_feature_rule,
    USER_LEVELS, EDUCATIONAL_RANKS,
    is_user_muted,
    get_user_feature_restriction, get_cash_sale_setting,
    SECONDARY_PLATFORMS, platform_name, platform_enabled, platform_configured,
    platform_token, platform_username, get_current_platform,
    user_has_platform, user_can_connect_platform, get_platform_link_mission,
    get_platform_admins, platform_report,
    members_count, fa_num, support_link, platform_invite_link,
    messaging_stats, phone_list, group_count,
)

logger = logging.getLogger(__name__)


# ========================= ابزار پایه =========================

def btn(text: str, cb: str = None, url: str = None) -> InlineKeyboardButton:
    return InlineKeyboardButton(text, url=url) if url else InlineKeyboardButton(text, callback_data=cb)


def mkb(rows) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(rows)


def back_btn(cb: str) -> list:
    return [btn("⬅️ بازگشت", cb)]


def home_btn() -> list:
    return [btn("🏠 منوی اصلی", "main")]


async def safe_answer(q, text: str = None, alert: bool = False):
    try:
        await q.answer(text=text, show_alert=alert) if text else await q.answer()
    except Exception as e:
        logger.debug(f"Answer error: {e}")


# ========================= کیبوردها =========================

def reply_kb(user):
    if is_admin(user):
        return ReplyKeyboardMarkup([
            [KeyboardButton("📚 لیست دوره‌ها"), KeyboardButton("👑 پنل مدیریت")],
            [KeyboardButton("⚙️ تنظیمات عمومی"), KeyboardButton("📣 مرکز پیام‌رسانی")],
            [KeyboardButton("🌐 مدیریت سایت")],
        ], resize_keyboard=True)

    all_btns = [
        "📚 لیست دوره‌ها",
        "🏆 پروفایل من",
        "🎯 ماموریت‌ها",
        "💎 گنجینه",
        "📰 آخرین اتفاقات",
        "👥 دعوت دوستان",
        "📞 پشتیبانی",
        "🧠 مسیر شغلی هوشمند",
    ]
    rows = []
    for i in range(0, len(all_btns), 2):
        rows.append([KeyboardButton(all_btns[i])] + ([KeyboardButton(all_btns[i+1])] if i+1 < len(all_btns) else []))
    return ReplyKeyboardMarkup(rows, resize_keyboard=True)


def phone_kb():
    """کیبورد اشتراک‌گذاری شماره تماس برای مرحله ثبت شماره."""
    return ReplyKeyboardMarkup(
        [[KeyboardButton("📱 اشتراک‌گذاری شماره تماس", request_contact=True)]],
        resize_keyboard=True,
        one_time_keyboard=False,
    )


async def show_phone_registration(target, user, platform: str = None):
    """
    نمایش صفحه ثبت شماره تلفن.
    target می‌تواند message باشد (reply) — کیبورد request_contact نیاز به reply دارد.
    روی پلتفرم ثانویه (تلگرام/...) فقط دکمهٔ اشتراک مخاطب پذیرفته می‌شود (نه تایپ دستی).
    """
    if platform and platform != "bale":
        pname = platform_name(platform)
        text = (
            f"📱 فعال‌سازی حساب در {pname}\n"
            "━━━━━━━━━━━━━━━━\n\n"
            "برای فعال‌سازی حساب خود، لطفاً روی دکمهٔ «📱 اشتراک‌گذاری شماره تماس» بزنید.\n\n"
            "⚠️ شماره حتماً باید شماره‌ی خودتان باشد تا حسابتان اینجا فعال شود.\n"
            "🔐 فقط از طریق همین دکمه شماره را بفرستید (تایپ دستی پذیرفته نمی‌شود).\n\n"
            "ℹ️ اگر این شماره قبلاً در ربات عضو بوده، امتیاز و اعتبار و سوابق شما به‌صورت یکپارچه می‌آید."
        )
        await target.reply_text(text, reply_markup=phone_kb())
        return
    text = (
        "📱 ثبت شماره تلفن\n"
        "━━━━━━━━━━━━━━━━\n\n"
        "برای استفاده از ربات، لطفاً ابتدا شماره موبایل خود را ثبت کنید.\n\n"
        "✅ دو روش برای ثبت دارید:\n"
        "  ۱) روی دکمه «📱 اشتراک‌گذاری شماره تماس» بزنید (سریع‌ترین راه)\n"
        "  ۲) شماره را به‌صورت دستی تایپ و ارسال کنید\n\n"
        "📝 نمونه فرمت‌های مجاز:\n"
        "  • 09123456789\n"
        "  • +989123456789\n\n"
        "⚠️ شماره باید معتبر و متعلق به خودتان باشد و قبلاً توسط کاربر دیگری ثبت نشده باشد."
    )
    await target.reply_text(text, reply_markup=phone_kb())


def _ai_mentor_enabled() -> bool:
    """آیا ماژول «یار هوشمند شغلی» فعال است؟

    import داخل تابع است تا اگر پکیج ai_mentor نبود یا دیتابیس هنوز آماده
    نشده بود، منوی اصلی ربات هرگز نشکند (fail-safe).
    """
    try:
        from ai_mentor.ai_handlers import module_enabled
        return module_enabled()
    except Exception:
        return False


def main_kb(user):
    if is_admin(user):
        return mkb([[btn("📚 لیست دوره‌ها", "courses")], [btn("👑 پنل مدیریت", "a_panel")]])
    rows = [
        [btn("📚 لیست دوره‌ها", "courses")],
        [btn("🏆 پروفایل من", "profile"), btn("🎯 ماموریت‌ها", "missions")],
        [btn("💎 گنجینه امتیازی", "shop"), btn("📰 آخرین اتفاقات", "latest_events")],
        [btn("👥 دعوت دوستان", "referral")],
    ]
    # 🤖 یار هوشمند شغلی — فقط اگر ماژول فعال باشد (دکمه‌های قبلی دست‌نخورده‌اند)
    if _ai_mentor_enabled():
        rows.append([btn("🤖 یار هوشمند شغلی", "aim_menu")])
    rows.append([btn("📞 پشتیبانی", "support")])
    return mkb(rows)


def src_kb(back_cb: str):
    return mkb([
        [btn("📝 متن", "src|text"), btn("🔗 لینک", "src|link")],
        [btn("📎 فایل مستقیم", "src|file")],
        [btn("📨 فوروارد از کانال", "src|forward")],
        back_btn(back_cb),
    ])


def done_kb(cid: str, idx: int = None):
    rows = []
    if idx is not None:
        rows.append([btn("✏️ مدیریت سرفصل", f"a_lmenu|{cid}|{idx}")])
    rows.append([btn("📚 لیست سرفصل‌ها", f"a_lessons|{cid}")])
    rows.append([btn("⬅️ بازگشت به دوره", f"a_open|{cid}")])
    return mkb(rows)


def lesson_menu_kb(cid: str, idx: int):
    return mkb([
        [btn("✏️ ویرایش عنوان", f"a_lt|{cid}|{idx}"),
         btn("🔁 تغییر منبع", f"a_ls|{cid}|{idx}")],
        [btn("🔒 عضویت اجباری سرفصل", f"a_ljoin|{cid}|{idx}"),
         btn("👥 دعوت اجباری سرفصل", f"a_lref|{cid}|{idx}")],
        [btn("💰 اعتبار اجباری سرفصل", f"a_lcredit|{cid}|{idx}")],
        [btn("💵 فروش نقدی سرفصل", f"a_lcash|{cid}|{idx}")],
        [btn("⬆️ بالا", f"a_lup|{cid}|{idx}"),
         btn("⬇️ پایین", f"a_ldn|{cid}|{idx}")],
        [btn("🗑 حذف سرفصل", f"a_ldel|{cid}|{idx}")],
        back_btn(f"a_lessons|{cid}"),
    ])


def join_kb(not_joined: list, course_id: str = None, lesson_idx: int = None, platform: str = None):
    rows = []
    p = platform or get_current_platform()
    base = {
        "bale": "https://ble.ir/",
        "telegram": "https://t.me/",
    }.get(p, "https://ble.ir/")
    for ch in not_joined:
        ch = ch.strip()
        is_numeric = ch.lstrip("-").isdigit()
        if is_numeric:
            # آیدی عددی: لینک مستقیم ندارد، فقط اطلاع می‌دهیم
            rows.append([btn(f"📢 عضویت در کانال (id: {ch})", "noop")])
        else:
            name = ch if ch.startswith("@") else f"@{ch}"
            clean = ch.lstrip("@")
            rows.append([btn(f"📢 عضویت در {name}", url=f"{base}{clean}")])
    cid = course_id or "global"
    suffix = f"|{lesson_idx}" if lesson_idx is not None else ""
    rows.append([btn("✅ بررسی مجدد عضویت", f"checkjoin|{cid}{suffix}")])
    rows.append(home_btn())
    return mkb(rows)


def referral_kb(user_id: int, required: int, current: int,
                course_id: str = None, lesson_idx: int = None):
    cid = course_id or "global"
    suffix = f"|{lesson_idx}" if lesson_idx is not None else ""
    return mkb([
        [btn("📋 کپی لینک دعوت", f"copylink|{user_id}|{cid}|{required}|{current}")],
        [btn(f"🔄 بررسی مجدد ({current}/{required})", f"checkref|{cid}{suffix}")],
        home_btn(),
    ])


def credits_kb(course_id: str = None, lesson_idx: int = None):
    cid = course_id or "global"
    suffix = f"|{lesson_idx}" if lesson_idx is not None else ""
    rows = [
        [btn("🎯 رفتن به ماموریت‌ها برای کسب اعتبار", "missions")],
        [btn(f"🔄 بررسی مجدد", f"checkaccess|{cid}{suffix}")],
    ]
    if course_id and course_id != "global":
        rows.append([btn("💵 خرید نقدی این دوره", f"cash_buy|{course_id}")])
    rows.append(home_btn())
    return mkb(rows)


# ========================= نمایش دسترسی =========================

async def show_access_denied(query, user_id: int, problem: str, details: dict,
                              course_id: str = None, lesson_idx: int = None):
    ct = f"📖 دوره: {COURSES[course_id]['title']}\n\n" if course_id and course_id in COURSES else ""

    if problem == "join":
        channels = details["channels"]
        src_key = details["source"]
        src = "عمومی" if src_key == "global" else ("این سرفصل" if src_key == "lesson" else "این دوره")
        ch_list = "".join(
            f"  ❌ {ch if ch.startswith('@') else f'@{ch}'}\n" for ch in channels
        )
        text = (
            f"{ct}🔒 عضویت اجباری ({src})\n\n"
            f"برای دسترسی باید در کانال‌های زیر عضو شوید:\n\n{ch_list}\n"
            f"📌 بعد از عضویت، دکمه «بررسی مجدد» را بزنید.\n\n"
            f"⚠️ اگر از کانال خارج شوید، دسترسی قطع خواهد شد."
        )
        await query.edit_message_text(text, reply_markup=join_kb(channels, course_id, lesson_idx))

    elif problem == "referral":
        req, cur = details["required"], details["current"]
        remaining = req - cur
        src_key = details["source"]
        src = "عمومی" if src_key == "global" else ("این سرفصل" if src_key == "lesson" else "این دوره")
        link = platform_invite_link(get_current_platform(), user_id) or f"https://ble.ir/{BOT_USERNAME}?start={user_id}"
        text = (
            f"{ct}👥 دعوت اجباری ({src})\n\n"
            f"برای دسترسی باید دوستان خود را دعوت کنید:\n\n"
            f"✅ دعوت‌های معتبر شما: {cur} نفر\n"
            f"🎯 تعداد لازم: {req} نفر\n"
            f"❌ باقی‌مانده: {remaining} نفر\n\n"
            f"📋 لینک دعوت شما:\n{link}\n\n"
            f"⚠️ شرایط دعوت معتبر:\n"
            f"  • کاربر باید جدید باشد\n"
            f"  • نباید تکراری باشد\n"
            f"  • نباید خود شما باشید\n\n"
            f"📌 بعد از دعوت، دکمه «بررسی مجدد» را بزنید."
        )
        await query.edit_message_text(
            text, reply_markup=referral_kb(user_id, req, cur, course_id, lesson_idx)
        )

    elif problem == "credits":
        req, cur = details["required"], details["current"]
        src_key = details["source"]
        src = "عمومی" if src_key == "global" else ("این سرفصل" if src_key == "lesson" else "این دوره")
        text = (
            f"{ct}💰 اعتبار ناکافی ({src})\n\n"
            f"برای دسترسی به این محتوا نیاز به اعتبار دارید:\n\n"
            f"💰 اعتبار فعلی شما: {cur}\n"
            f"🎯 اعتبار لازم: {req}\n"
            f"❌ کمبود: {req - cur}\n\n"
            f"💡 چطور اعتبار کسب کنیم؟\n"
            f"  • مشاهده سرفصل (اول بار): +۲ اعتبار\n"
            f"  • دعوت دوست معتبر: +۵ اعتبار\n"
            f"  • تکمیل نظرسنجی دوره: +۱۰ اعتبار\n"
            f"  • انجام ماموریت‌های امتیازی 🎯\n\n"
            f"📌 پس از کسب اعتبار، دکمه «بررسی مجدد» را بزنید."
        )
        await query.edit_message_text(
            text, reply_markup=credits_kb(course_id, lesson_idx)
        )


# ========================= نمایش دوره‌ها =========================

async def show_courses(target, is_query=True, uid: int = None):
    visible_courses = {}
    for cid, c in COURSES.items():
        visible_courses[cid] = c

    if not visible_courses:
        text = "📚 هنوز دوره‌ای اضافه نشده.\n\nبه زودی دوره‌های جدید اضافه خواهند شد! 🎓"
        r = mkb([home_btn()])
    else:
        rows = [
            [btn(f"📖 {c['title']} ({len(c.get('lessons', []))} سرفصل)", f"course|{cid}")]
            for cid, c in visible_courses.items()
        ]
        rows.append([btn("👁 نظر کاربران درباره دوره‌های آنلاین", "all_courses_feedback")])
        rows.append(home_btn())
        text = "📚 دوره‌های آموزشی موجود:\n\nروی هر دوره بزنید تا سرفصل‌ها رو ببینید 👇"
        r = mkb(rows)
    if is_query:
        await target.edit_message_text(text, reply_markup=r)
    else:
        await target.reply_text(text, reply_markup=r)


async def show_course_user(query, cid: str, uid: int, ctx):
    c = COURSES.get(cid)
    if not c:
        await query.edit_message_text(
            "❌ این دوره پیدا نشد یا حذف شده.",
            reply_markup=mkb([back_btn("courses")])
        )
        return

    has_access, problem, details = await full_access_check(ctx.bot, uid, cid)
    if not has_access:
        await show_access_denied(query, uid, problem, details, cid)
        return

    lessons = c.get("lessons", [])
    done_lids = get_completed_lids(uid, cid)
    seq_prog = get_seq_prog(uid, cid)
    prog = get_prog(uid, cid)

    if not lessons:
        text = (
            f"📖 {c['title']}\n\n{c.get('description', 'بدون توضیحات')}\n\n"
            f"⏳ هنوز سرفصلی به این دوره اضافه نشده."
        )
        await query.edit_message_text(text, reply_markup=mkb([back_btn("courses"), home_btn()]))
        return

    # چک فروش نقدی در سطح دوره
    u_data = USERS.get(str(uid), {})
    credits_paid = u_data.get("credits_paid", {})
    course_cash = CASH_SALE_SETTINGS.get(f"course|{cid}", {})
    course_cash_active = course_cash.get("enabled", False)
    course_cash_paid = credits_paid.get(f"course_{cid}", False)

    status = "🎉 تبریک! همه سرفصل‌ها رو دیدید!" if prog >= len(lessons) else "▶️ ادامه بدید..."
    text = (
        f"📖 {c['title']}\n\n📝 {c.get('description', 'بدون توضیحات')}\n\n"
        f"📊 پیشرفت شما: {prog}/{len(lessons)} سرفصل\n{status}"
    )

    # حالت: دوره کامل نقدی است و کاربر نخریده
    if course_cash_active and not course_cash_paid:
        text += "\n\n💵 این دوره فروش نقدی است\nبرای تهیه این دوره به گنجینه مراجعه کنید"
        rows = []
        for i, ls in enumerate(lessons):
            rows.append([btn(f"🔒 {i+1}. {ls['title']}", f"cash_locked_course|{cid}")])
        rows.append([btn("🏪 رفتن به گنجینه", "shop")])
        rows.append(back_btn("courses"))
        rows.append(home_btn())
        try:
            await query.edit_message_text(text, reply_markup=mkb(rows))
        except Exception:
            try:
                await query.message.delete()
            except Exception:
                pass
            await query.message.chat.send_message(text, reply_markup=mkb(rows))
        return

    rows = []
    visible_idx = 0
    for i, ls in enumerate(lessons):
        lid = ls.get("lid", str(i))
        lesson_setting = CASH_SALE_SETTINGS.get(f"lesson|{lid}", {})
        lesson_cash_paid = credits_paid.get(f"lesson_{lid}", False)
        # چک فروش نقدی سرفصل (هر display_place — دوره/گنجینه — باز هم در دوره نمایش داده می‌شود)
        lesson_cash_active = lesson_setting.get("enabled", False)
        if lesson_cash_active and not lesson_cash_paid:
            rows.append([btn(f"💵🔒 {i+1}. {ls['title']}", f"cash_locked_lesson|{cid}|{i}")])
            visible_idx += 1
            continue
        is_done = (lid and lid in done_lids) or (not lid and i < seq_prog)
        is_next = (not is_done) and i == seq_prog
        if is_done:
            rows.append([btn(f"✅ {i+1}. {ls['title']}", f"lesson|{cid}|{i}")])
        elif is_next:
            rows.append([btn(f"▶️ {i+1}. {ls['title']}", f"lesson|{cid}|{i}")])
        else:
            rows.append([btn(f"🔒 {i+1}. {ls['title']}", f"lock|{cid}|{i}")])
        visible_idx += 1
    rows.append(back_btn("courses"))
    rows.append(home_btn())

    try:
        await query.edit_message_text(text, reply_markup=mkb(rows))
    except Exception:
        try:
            await query.message.delete()
        except Exception:
            pass
        await query.message.chat.send_message(text, reply_markup=mkb(rows))

    # نظرسنجی پایان دوره — اگر همه سرفصل‌ها دیده شده و هنوز رای نداده، خودکار نمایش داده شود
    # (شامل دوره‌های نقدی که پس از خرید همه سرفصل‌ها مشاهده شده‌اند)
    if prog >= len(lessons) and c.get("survey_enabled", True):
        uid_s = str(uid)
        if not SURVEYS.get(cid, {}).get(uid_s):
            sv_title = c.get("title", "")
            sv_msg = f"📊 نظرسنجی پایان دوره: {sv_title}\n\nنظر شما درباره این دوره چیست؟"
            try:
                await query.message.chat.send_message(
                    sv_msg,
                    reply_markup=mkb([
                        [btn("⭐ عالی بود، پیشنهاد میکنم بقیه هم شرکت کنند",
                             f"rate_course|{cid}|excellent")],
                        [btn("🔧 نیاز به به‌روزرسانی دارد", f"rate_course|{cid}|needs_update")],
                    ]),
                )
            except Exception as e:
                logger.debug(f"Auto survey send error: {e}")


async def send_lesson(query, ctx, cid: str, idx: int):
    user = query.from_user
    chat = query.message.chat.id

    has_access, problem, details = await full_access_check(ctx.bot, user.id, cid, lesson_idx=idx)
    if not has_access:
        await show_access_denied(query, user.id, problem, details, cid, lesson_idx=idx)
        return

    c = COURSES.get(cid)
    if not c:
        return
    lessons = c.get("lessons", [])
    if idx < 0 or idx >= len(lessons):
        return

    # چک قفل فروش نقدی — جلوگیری از باز شدن سرفصل/دوره نقدی از هر مسیری
    # (دکمه «سرفصل بعدی»، دکمه بازگشت، یا کلیک مستقیم)
    u_cp = USERS.get(str(user.id), {}).get("credits_paid", {})
    _ls_lock = lessons[idx]
    _lid_lock = _ls_lock.get("lid", str(idx))
    course_cash_lock = CASH_SALE_SETTINGS.get(f"course|{cid}", {})
    if course_cash_lock.get("enabled", False) and not u_cp.get(f"course_{cid}", False):
        await safe_answer(query)
        await query.edit_message_text(
            "🔒 این دوره فروش نقدی است\n"
            f"📖 {c.get('title', '')}\n\n"
            "برای تهیه این دوره به گنجینه مراجعه کنید و خرید را انجام دهید.\n"
            "پس از تایید خرید توسط ادمین، تمام سرفصل‌ها برای شما باز می‌شود.",
            reply_markup=mkb([
                [btn("💵 خرید این دوره از گنجینه", f"cash_buy|{cid}")],
                [btn("⬅️ بازگشت به دوره", f"course|{cid}")],
                home_btn(),
            ]),
        )
        return
    lesson_cash_lock = CASH_SALE_SETTINGS.get(f"lesson|{_lid_lock}", {})
    if lesson_cash_lock.get("enabled", False) and not u_cp.get(f"lesson_{_lid_lock}", False):
        await safe_answer(query)
        await query.edit_message_text(
            "🔒 این سرفصل فروش نقدی است\n"
            f"📝 {_ls_lock.get('title', '')}\n\n"
            "برای تهیه این سرفصل به گنجینه مراجعه کنید و خرید را انجام دهید.\n"
            "پس از تایید خرید توسط ادمین، این سرفصل برای شما باز می‌شود.",
            reply_markup=mkb([
                [btn("💵 خرید این سرفصل از گنجینه", f"cash_lesson_buy|{cid}|{idx}")],
                [btn("⬅️ بازگشت به دوره", f"course|{cid}")],
                home_btn(),
            ]),
        )
        return

    seq = get_seq_prog(user.id, cid)
    if idx > seq:
        await safe_answer(query, "🔒 ابتدا سرفصل‌های قبلی را ببینید.", True)
        return

    ls = lessons[idx]
    lt = ls.get("type")

    if not ls.get("lid"):
        ls["lid"] = next_lid()
        save("courses")

    try:
        await query.message.delete()
    except Exception:
        pass

    try:
        if lt == "text":
            await ctx.bot.send_message(chat, f"📝 {ls['title']}\n\n{ls.get('content', '')}")
        elif lt == "link":
            await ctx.bot.send_message(
                chat,
                f"🔗 {ls['title']}\n\nبرای مشاهده محتوا روی دکمه زیر بزنید:",
                reply_markup=mkb([[btn("🔗 باز کردن لینک", url=ls.get("content", ""))]]),
            )
        elif lt == "photo":
            await ctx.bot.send_photo(
                chat, ls["file_id"], caption=f"🖼 {ls['title']}\n{ls.get('caption', '')}"
            )
        elif lt == "video":
            await ctx.bot.send_video(
                chat, ls["file_id"], caption=f"🎬 {ls['title']}\n{ls.get('caption', '')}"
            )
        elif lt == "document":
            await ctx.bot.send_document(
                chat, ls["file_id"], caption=f"📎 {ls['title']}\n{ls.get('caption', '')}"
            )
        elif lt == "channel_post":
            await ctx.bot.copy_message(chat, ls["source_chat_id"], ls["source_message_id"])
        else:
            await ctx.bot.send_message(chat, "❌ این نوع محتوا پشتیبانی نمی‌شود.")
            return
    except Exception as e:
        logger.error(f"Send lesson error: {e}")
        await ctx.bot.send_message(chat, f"❌ خطا در ارسال محتوا:\n{e}")
        return

    lid = ls.get("lid")
    first_time = not has_done_lesson(user.id, cid, lid)
    if first_time:
        mark_lesson_done(user.id, cid, lid)
        award_xp_and_credits(user.id, xp_amount=5, credits_amount=2)

    prog = get_prog(user.id, cid)
    seq2 = get_seq_prog(user.id, cid)
    rows = []
    if idx + 1 < len(lessons) and idx + 1 <= seq2:
        _nxt = lessons[idx + 1]
        _nxt_lid = _nxt.get("lid", str(idx + 1))
        _nxt_cash = CASH_SALE_SETTINGS.get(f"lesson|{_nxt_lid}", {})
        if _nxt_cash.get("enabled", False) and not u_cp.get(f"lesson_{_nxt_lid}", False):
            rows.append([btn(f"💵🔒 سرفصل بعدی: {_nxt['title']}", f"cash_locked_lesson|{cid}|{idx+1}")])
        else:
            rows.append([btn(f"▶️ سرفصل بعدی: {_nxt['title']}", f"lesson|{cid}|{idx+1}")])
    if prog >= len(lessons):
        rows.append([btn("🎉 تبریک! دوره تمام شد!", f"course|{cid}")])
    else:
        rows.append([btn("📚 بازگشت به دوره", f"course|{cid}")])
    rows.append(home_btn())

    message = f"✅ سرفصل {idx+1} از {len(lessons)} مشاهده شد"
    if first_time:
        message += "\n📈 +۵ امتیاز رشد | 💰 +۲ اعتبار"

    await ctx.bot.send_message(chat, message, reply_markup=mkb(rows))

    if first_time and prog >= len(lessons):
        sv_course = COURSES.get(cid, {})
        if sv_course.get("survey_enabled", True):
            uid_s = str(user.id)
            if not SURVEYS.get(cid, {}).get(uid_s):
                sv_title = sv_course.get("title", "")
                sv_msg = f"📊 نظرسنجی پایان دوره: {sv_title}\n\nنظر شما درباره این دوره چیست؟"
                await ctx.bot.send_message(
                    chat, sv_msg,
                    reply_markup=mkb([
                        [btn("⭐ عالی بود، پیشنهاد میکنم بقیه هم شرکت کنند",
                             f"rate_course|{cid}|excellent")],
                        [btn("🔧 نیاز به به‌روزرسانی دارد", f"rate_course|{cid}|needs_update")],
                    ]),
                )


# ========================= پروفایل =========================

async def show_profile(target, user, is_q=False):
    if is_admin(user):
        text = "👑 شما ادمین هستید.\nپروفایل و امتیاز فقط برای کاربران عادی است."
        r = mkb([home_btn()])
    else:
        u = USERS.get(str(user.id), {})
        _migrate_user(u)
        xp = u.get("xp", u.get("points", 0))
        credits = u.get("credits", 0)
        comp = completed_lessons(user.id)
        rnk = user_rank(user.id)
        tot = total_lessons()
        refs = valid_refs(user.id)
        tn = len(normal_users_sorted())
        current_level, next_level, progress = get_level_progress(xp)
        edu_rank = get_educational_rank(xp)
        missions_done = len(u.get("completed_missions", []))

        badges = []
        # نشان‌های سطح کاربر — متصل به رتبه فعلی (هر سطحی که رسیده باشد نشانش را می‌گیرد)
        for lvl in USER_LEVELS:
            if xp >= lvl["threshold"]:
                badges.append(f"{lvl['icon']} {lvl['title']}")
        if refs >= 3:  badges.append("👥 معرف فعال")
        if refs >= 10: badges.append("🌟 سفیر")

        level_text = f"{current_level['icon']} {current_level['title']}"
        next_text = (
            f"\n⏳ تا سطح بعدی {next_level['icon']} {next_level['title']}: "
            f"{next_level['threshold'] - xp} امتیاز رشد باقی‌مانده"
            if next_level else "\n🎉 شما در بالاترین سطح هستید!"
        )
        progress_text = f"\n📈 پیشرفت: {progress}%" if next_level else ""

        cur_platform = platform_name(get_current_platform())
        text = (
            f"🏆 پروفایل {user.first_name}\n\n"
            f"👥 تا الان {fa_num(members_count())} نفر عضو شده‌اند.\n"
            f"🌐 پلتفرم فعلی: {cur_platform}\n"
            f"📈 امتیاز رشد (XP): {xp}\n"
            f"💰 اعتبار: {credits}\n"
            f"{edu_rank['icon']} رتبه آموزشی: {edu_rank['title']}\n\n"
            f"{level_text}{next_text}{progress_text}\n"
            f"🥇 رتبه رقابتی: {rnk} از {tn} نفر\n"
            f"📚 سرفصل‌های تکمیل شده: {comp}/{tot}\n"
            f"👥 دعوت‌های معتبر: {refs} نفر\n"
            f"🎯 ماموریت‌های انجام شده: {missions_done}\n\n"
            f"🎖 نشان‌ها:\n{'  '.join(badges) if badges else '  هنوز نشانی ندارید!'}\n\n"
            f"💡 چطور امتیاز رشد بگیریم؟\n"
            f"  📖 هر سرفصل = +۵ XP\n"
            f"  👥 هر دعوت معتبر = +۱۰ XP\n"
            f"  📊 نظرسنجی دوره = +۴۰ XP\n"
            f"  🎯 ماموریت‌های امتیازی = تا +۱۰۰ XP"
        )
        rows = [
            [btn("👥 دعوت دوستان", "referral")],
            [btn("💎 گنجینه امتیازی", "shop")],
            [btn("🏅 جدول رتبه‌بندی", "leaderboard"), btn("🎯 ماموریت‌ها", "missions")],
        ]
        for p in SECONDARY_PLATFORMS:
            if user_can_connect_platform(user.id, p) and not user_has_platform(user.id, p):
                rows.append([btn(f"🔗 اتصال به {platform_name(p)}", f"u_link|{p}")])
        rows.append(home_btn())
        r = mkb(rows)
    if is_q:
        await target.edit_message_text(text, reply_markup=r)
    else:
        await target.reply_text(text, reply_markup=r)


# ========================= چندپلتفرمی — صفحات کاربر =========================

async def show_platform_link_prompt(target, user, platform: str, code: str, deep_link: str, is_q=False):
    pname = platform_name(platform)
    link_line = deep_link if deep_link else "(لینک بعد از تنظیم نام کاربری ربات مقصد فعال می‌شود)"
    text = (
        f"🔗 اتصال حساب شما به {pname}\n\n"
        f"۱) روی لینک زیر بزنید:\n{link_line}\n\n"
        f"۲) در ربات مقصد دکمه «Start» را بزنید\n"
        f"۳) اتصال به‌صورت خودکار انجام می‌شود ✅\n\n"
        f"🔑 کد یک‌بارمصرف شما: <code>{code}</code>\n"
        f"⏳ این کد محدودیت زمانی دارد و فقط یک‌بار قابل استفاده است."
    )
    r = mkb([[btn("⬅️ بازگشت به پروفایل", "profile")], home_btn()])
    if is_q:
        await target.edit_message_text(text, reply_markup=r, parse_mode="HTML")
    else:
        await target.reply_text(text, reply_markup=r, parse_mode="HTML")


# ========================= چندپلتفرمی — صفحات ادمین =========================

def _platform_status_line(p: str) -> str:
    en = "🟢 فعال" if platform_enabled(p) else "🔴 غیرفعال"
    cfg = "✅ ثبت‌شده" if platform_configured(p) else "❌ ثبت‌نشده"
    return f"{platform_name(p)}: {en} | اتصال: {cfg}"


async def show_platform_management(target, is_q=False):
    lines = ["🌐 مدیریت پلتفرم‌ها\n"]
    for p in SECONDARY_PLATFORMS:
        lines.append(_platform_status_line(p))
    text = "\n".join(lines) + "\n\nبرای تنظیم هر پلتفرم روی آن بزنید."
    rows = [[btn(f"⚙️ {platform_name(p)}", f"a_plat|{p}")] for p in SECONDARY_PLATFORMS]
    rows.append(back_btn("a_global_settings"))
    r = mkb(rows)
    if is_q:
        await target.edit_message_text(text, reply_markup=r)
    else:
        await target.reply_text(text, reply_markup=r)


async def show_platform_detail(target, platform: str, is_q=False):
    p = platform
    en = platform_enabled(p)
    tok = platform_token(p)
    uname = platform_username(p)
    mission = get_platform_link_mission(p)
    tok_disp = (tok[:6] + "…") if tok else "ثبت‌نشده"
    sup_raw = str(SETTINGS.get(f"{p}_support", "") or "").strip()
    sup_disp = sup_raw if sup_raw else f"پیش‌فرض ({SUPPORT_GROUP})"
    text = (
        f"⚙️ تنظیم {platform_name(p)}\n\n"
        f"وضعیت: {'🟢 فعال' if en else '🔴 غیرفعال'}\n"
        f"توکن: {tok_disp}\n"
        f"نام کاربری ربات: {uname or 'ثبت‌نشده'}\n"
        f"ماموریت اتصال فعال: {'✅ دارد' if mission else '❌ ندارد'}\n"
        f"پشتیبانی مختص این پلتفرم: {sup_disp}\n"
    )
    # [افزوده] بلوک اطلاعات اتصال/پروکسی — فقط برای تلگرام
    if p == "telegram":
        text += "\n" + _telegram_conn_block()
    rows = [
        [btn("🔑 ثبت/ویرایش توکن", f"a_plat_token|{p}")],
        [btn("🏷 ثبت/ویرایش نام کاربری ربات", f"a_plat_uname|{p}")],
        [btn("📞 ثبت/ویرایش پشتیبانی این پلتفرم", f"a_plat_support|{p}")],
        [btn("🔴 غیرفعال کن" if en else "🟢 فعال کن", f"a_plat_toggle|{p}")],
        [btn("📊 بررسی وضعیت واقعی اتصال", f"a_plat_status|{p}")],
        [btn("➕ ایجاد لینک ادمین", f"a_plat_adminlink|{p}")],
        [btn("👤 ادمین‌های متصل", f"a_plat_admins|{p}")],
        back_btn("a_platforms"),
    ]
    # [افزوده] زیرمنوی تنظیمات پروکسی — فقط برای تلگرام، بدون تغییر دکمه‌های بالا
    if p == "telegram":
        rows.insert(-1, [btn("🌐 تنظیمات پروکسی", f"a_plat_proxy|{p}")])
    r = mkb(rows)
    if is_q:
        await target.edit_message_text(text, reply_markup=r)
    else:
        await target.reply_text(text, reply_markup=r)


def _telegram_conn_block() -> str:
    """[افزوده] بلوک اطلاعات اتصال و پروکسی برای بالای پنل تلگرام."""
    try:
        import proxy_manager as pm
        from platform_runtime import is_telegram_running, current_proxy_label
    except Exception:
        return ""
    st = pm.status_summary()
    connected = is_telegram_running()
    cur = current_proxy_label()
    return (
        "━━━━━━━━━━━━━━━━\n"
        f"اتصال: {'✅ متصل' if connected else '❌ قطع'}\n"
        f"پروکسی فعلی: {cur}\n"
        f"پروکسی‌های سالم: {fa_num(st['working'])}"
        + (f" (+{fa_num(st['manual'])} دستی)" if st["manual"] else "")
        + "\n"
        f"آخرین آپدیت لیست: {st['age']}\n"
        f"حالت اتصال: {st['mode_label']}\n"
    )


async def show_proxy_menu(target, platform: str = "telegram", is_q=True):
    """[افزوده] زیرمنوی «🌐 تنظیمات پروکسی»."""
    import proxy_manager as pm
    st = pm.status_summary()
    src = st["source"]
    src_disp = (src[:52] + "…") if len(src) > 52 else src
    text = (
        "🌐 تنظیمات پروکسی تلگرام\n"
        "━━━━━━━━━━━━━━━━\n\n"
        f"📄 پروکسی‌های سالم: {fa_num(st['working'])}\n"
        f"✏️ پروکسی‌های دستی: {fa_num(st['manual'])}\n"
        f"🕒 آخرین آپدیت: {st['age']}"
        + ("  ✅ تازه" if st["fresh"] else "  ⚠️ قدیمی")
        + "\n"
        f"⚙️ حالت اتصال: {st['mode_label']}\n\n"
        f"🔧 منبع:\n{src_disp}\n\n"
        f"ℹ️ هر بار دریافت خودکار، حداکثر {fa_num(pm.MAX_FETCH)} پروکسی تست می‌شود.\n"
        "ℹ️ کش هوشمند: اگر لیست کمتر از ۶ ساعت قدیمی باشد، دوباره تست نمی‌شود."
    )
    rows = [
        [btn("📥 دریافت خودکار از منبع", f"a_plat_proxy_fetch|{platform}")],
        [btn("✏️ وارد کردن دستی پروکسی", f"a_plat_proxy_manual|{platform}")],
        [btn("🔧 تغییر URL منبع", f"a_plat_proxy_src|{platform}")],
        [btn("🔄 آپدیت و تست مجدد لیست", f"a_plat_proxy_revalidate|{platform}")],
        [btn("📄 نمایش پروکسی‌های سالم", f"a_plat_proxy_list|{platform}|0")],
        [btn("⚙️ حالت اتصال", f"a_plat_proxy_mode|{platform}")],
        [btn("🗑️ حذف لیست پروکسی", f"a_plat_proxy_clear|{platform}")],
        back_btn(f"a_plat|{platform}"),
    ]
    # [کار ۱] دکمهٔ تست پروکسی‌های دستی — فقط وقتی پروکسی دستی ثبت شده باشد
    if st["manual"]:
        rows.insert(2, [btn(f"🧪 تست {fa_num(st['manual'])} پروکسی دستی",
                            f"a_plat_proxy_testmanual|{platform}")])
    r = mkb(rows)
    if is_q:
        await target.edit_message_text(text, reply_markup=r)
    else:
        await target.reply_text(text, reply_markup=r)


async def show_proxy_mode_menu(target, platform: str = "telegram", is_q=True):
    """[افزوده] انتخاب یکی از سه حالت اتصال."""
    import proxy_manager as pm
    cur = pm.get_mode()
    text = (
        "⚙️ حالت اتصال تلگرام\n"
        "━━━━━━━━━━━━━━━━\n\n"
        f"حالت فعلی: {pm.mode_label(cur)}\n\n"
        "🟢 خودکار — ابتدا پروکسی‌های دستی، سپس لیست سالم، در آخر اتصال مستقیم\n"
        "🟡 دستی — فقط پروکسی‌هایی که خودتان وارد کرده‌اید\n"
        "🔴 مستقیم — بدون پروکسی (نیازمند VPN)"
    )
    rows = []
    for m in (pm.MODE_AUTO, pm.MODE_MANUAL, pm.MODE_DIRECT):
        mark = "  ✅" if m == cur else ""
        rows.append([btn(f"{pm.MODE_LABELS[m]}{mark}", f"a_plat_proxy_setmode|{platform}|{m}")])
    rows.append(back_btn(f"a_plat_proxy|{platform}"))
    r = mkb(rows)
    if is_q:
        await target.edit_message_text(text, reply_markup=r)
    else:
        await target.reply_text(text, reply_markup=r)


async def show_proxy_list(target, platform: str = "telegram", page: int = 0, is_q=True):
    """[افزوده] نمایش صفحه‌بندی‌شدهٔ پروکسی‌های سالم."""
    import proxy_manager as pm
    items = pm.load_working()
    manual = pm.get_manual_proxies()
    per = 20
    total_pages = max(1, (len(items) + per - 1) // per)
    page = max(0, min(page, total_pages - 1))
    chunk = items[page * per:(page + 1) * per]

    lines = [
        "📄 پروکسی‌های سالم",
        "━━━━━━━━━━━━━━━━",
        f"تعداد کل: {fa_num(len(items))}  |  آخرین آپدیت: {pm.age_text()}",
        "",
    ]
    if chunk:
        lines += [f"{fa_num(page * per + i + 1)}. {p}" for i, p in enumerate(chunk)]
    else:
        lines.append("هنوز پروکسی سالمی ذخیره نشده است.")
    if manual:
        lines += ["", f"✏️ پروکسی‌های دستی ({fa_num(len(manual))}):"]
        lines += [f"• {p}" for p in manual]

    nav = []
    if page > 0:
        nav.append(btn("⬅️ قبلی", f"a_plat_proxy_list|{platform}|{page-1}"))
    if page < total_pages - 1:
        nav.append(btn("بعدی ➡️", f"a_plat_proxy_list|{platform}|{page+1}"))
    rows = [nav] if nav else []
    rows.append(back_btn(f"a_plat_proxy|{platform}"))
    r = mkb(rows)
    txt = "\n".join(lines)
    if is_q:
        await target.edit_message_text(txt, reply_markup=r)
    else:
        await target.reply_text(txt, reply_markup=r)


async def show_platform_admins_list(target, platform: str, is_q=False):
    admins = get_platform_admins(platform)
    if admins:
        body = "\n".join(
            f"• {a.get('platform_user_id')} (اصلی: {a.get('user_id') or '-'})"
            for a in admins
        )
    else:
        body = "هنوز ادمینی متصل نشده."
    text = f"👤 ادمین‌های متصل {platform_name(platform)}\n\n{body}"
    r = mkb([back_btn(f"a_plat|{platform}")])
    if is_q:
        await target.edit_message_text(text, reply_markup=r)
    else:
        await target.reply_text(text, reply_markup=r)


async def show_platform_report(target, is_q=False):
    text = platform_report()
    r = mkb([back_btn("a_reports")])
    if is_q:
        await target.edit_message_text(text, reply_markup=r)
    else:
        await target.reply_text(text, reply_markup=r)


# ========================= مرکز پیام‌رسانی =========================

_TYPE_LABELS = {"text": "📝 متنی", "photo": "🖼 تصویری", "video": "🎬 ویدیو"}


def _messaging_summary_text() -> str:
    stats = messaging_stats()
    total = members_count()
    lines = [
        "📣 مرکز پیام‌رسانی",
        "━━━━━━━━━━━━━━━━",
        f"👥 کل اعضای یکتا: {fa_num(total)} نفر",
        "",
        "📊 به تفکیک پلتفرم:",
    ]
    if not stats:
        lines.append("  (هیچ پلتفرمی با ربات فعال نیست)")
    for p, s in stats.items():
        lines.append(
            f"  {platform_name(p)} — 👥 اعضا: {fa_num(s['members'])} | "
            f"📞 شماره: {fa_num(s['phones'])} | 🟢 فعال اخیر: {fa_num(s['active'])} | "
            f"👥 گروه/کانال: {fa_num(group_count(p))}"
        )
    return "\n".join(lines)


async def show_messaging_stats(target, is_q=True):
    stats = messaging_stats()
    lines = ["📊 آمار اعضا (مرکز پیام‌رسانی)", "━━━━━━━━━━━━━━━━",
             f"👥 کل اعضای یکتا: {fa_num(members_count())} نفر", ""]
    for p, s in stats.items():
        lines.append(
            f"🔹 {platform_name(p)}\n"
            f"   👥 اعضا: {fa_num(s['members'])} نفر\n"
            f"   📞 تعداد شماره‌ها: {fa_num(s['phones'])}\n"
            f"   🟢 فعال اخیر: {fa_num(s['active'])} نفر\n"
            f"   👥 گروه/کانال: {fa_num(group_count(p))}\n"
        )
    r = mkb([back_btn("a_messaging")])
    txt = "\n".join(lines)
    if is_q:
        await target.edit_message_text(txt, reply_markup=r)
    else:
        await target.reply_text(txt, reply_markup=r)


_PHONES_PER_PAGE = 30


async def show_phone_list(target, page=0, is_q=True):
    items = phone_list()
    total = len(items)
    start = page * _PHONES_PER_PAGE
    chunk = items[start:start + _PHONES_PER_PAGE]
    lines = [f"📞 لیست شماره‌ها ({fa_num(total)} نفر)", "━━━━━━━━━━━━━━━━"]
    if not chunk:
        lines.append("هیچ شماره‌ای ثبت نشده است.")
    for i, (name, ph) in enumerate(chunk, start=start + 1):
        lines.append(f"{fa_num(i)}. {name} — {ph}")
    nav = []
    if start > 0:
        nav.append(btn("◀️ قبلی", f"bc_phones|{page-1}"))
    if start + _PHONES_PER_PAGE < total:
        nav.append(btn("بعدی ▶️", f"bc_phones|{page+1}"))
    rows = []
    if nav:
        rows.append(nav)
    rows.append(back_btn("a_messaging"))
    r = mkb(rows)
    txt = "\n".join(lines)
    if is_q:
        await target.edit_message_text(txt, reply_markup=r)
    else:
        await target.reply_text(txt, reply_markup=r)


def bcast_type_kb():
    return mkb([
        [btn("📝 متنی", "bc_type|text")],
        [btn("🖼 تصویری", "bc_type|photo")],
        [btn("🎬 ویدیو", "bc_type|video")],
        back_btn("a_messaging"),
    ])


def bcast_confirm_kb():
    return mkb([
        [btn("✅ تأیید و ارسال", "bc_send")],
        [btn("❌ انصراف", "a_messaging")],
    ])


# ========================= دعوت =========================

async def show_referral(target, user, is_q=False):
    if is_admin(user):
        text = "👑 شما ادمین هستید.\nسیستم دعوت فقط برای کاربران عادی است."
        r = mkb([home_btn()])
    else:
        refs = valid_refs(user.id)
        cur = get_current_platform()
        link = platform_invite_link(cur, user.id)
        if not link:
            if cur == "bale":
                link = f"https://ble.ir/{BOT_USERNAME}?start={user.id}"
            else:
                link = "(نام کاربری ربات این پلتفرم ثبت نشده است؛ از پنل مدیریت → تنظیمات عمومی → مدیریت پلتفرم‌ها آن را ثبت کنید)"
        text = (
            f"👥 دعوت دوستان\n\nبا دعوت دوستانتان امتیاز رشد و اعتبار بگیرید! 🎁\n\n"
            f"📋 لینک اختصاصی شما (پلتفرم {platform_name(cur)}):\n{link}\n\n"
            f"✅ دعوت‌های معتبر شما: {refs} نفر\n"
            f"📈 هر دعوت = +۱۰ امتیاز رشد | +۵ اعتبار\n\n"
            f"📌 شرایط دعوت معتبر:\n"
            f"  • کاربر باید برای اولین بار ربات را استارت کند\n"
            f"  • نباید تکراری باشد\n  • نباید خودتان باشید\n\n"
            f"لینک بالا را برای دوستانتان ارسال کنید! 📤"
        )
        r = mkb([
            [btn("📋 کپی لینک دعوت", f"copylink|{user.id}|global||")],
            home_btn(),
        ])
    if is_q:
        await target.edit_message_text(text, reply_markup=r)
    else:
        await target.reply_text(text, reply_markup=r)


# ========================= گنجینه =========================

async def show_shop(target, user, is_q=False):
    from config import CASH_SALE_SETTINGS, COURSES
    if is_admin(user):
        text = "👑 شما ادمین هستید.\nگنجینه امتیازی فقط برای کاربران عادی است."
        r = mkb([home_btn()])
    else:
        u = USERS.get(str(user.id), {})
        _migrate_user(u)
        credits = u.get("credits", 0)
        lines = []
        rows = []

        for sid, item in SHOP.items():
            if not item.get("active", False):
                continue
            price = int(item.get("price", 0))
            stock = item.get("stock")
            status = "ناموجود" if stock == 0 else f"{price}💰"
            owned = int(user.id) in item.get("purchased_by", [])
            label = f"{item.get('title', 'آیتم')} — {status}"
            if stock != 0 and not owned:
                rows.append([btn(label, f"shop_item|{sid}")])
            lines.append(
                f"• {item.get('title', 'بدون نام')} — {status}"
                f"{' ✅ خریداری شده' if owned else ''}"
            )

        for key, setting in CASH_SALE_SETTINGS.items():
            # [مشکل 2/3] آیتم نقدی همیشه در گنجینه نمایش داده می‌شود (نمایش دوگانه پیش‌فرض)
            if not setting.get("enabled"):
                continue
            parts = key.split("|", 1)
            if len(parts) != 2:
                continue
            target_type, target_id = parts
            amount = setting.get("amount", 0)
            amount_txt = f"{amount:,} تومان" if amount > 0 else "تماس با پشتیبانی"
            paid = u.get("credits_paid", {})
            if target_type == "course":
                c = COURSES.get(target_id)
                if not c:
                    continue
                title = c.get("title", target_id)
                owned = bool(paid.get(f"course_{target_id}"))
                if owned:
                    lines.append(f"• 💵 {title} — ✅ خریداری شده")
                else:
                    label = f"💵 {title} — {amount_txt}"
                    rows.append([btn(label, f"cash_buy|{target_id}")])
                    lines.append(f"• 💵 {title} — {amount_txt} (فروش نقدی)")
            elif target_type == "lesson":
                owned = bool(paid.get(f"lesson_{target_id}"))
                for cid, c in COURSES.items():
                    for i, ls in enumerate(c.get("lessons", [])):
                        if ls.get("lid") == target_id:
                            title = f"{c.get('title', cid)} / {ls.get('title', target_id)}"
                            if owned:
                                lines.append(f"• 💵 {title} — ✅ خریداری شده")
                            else:
                                label = f"💵 {title} — {amount_txt}"
                                rows.append([btn(label, f"cash_lesson_buy|{cid}|{i}")])
                                lines.append(f"• 💵 {title} — {amount_txt} (فروش نقدی)")
                            break

        if not lines:
            text = "💎 آیتمی برای خرید وجود ندارد.\nبعدا دوباره چک کنید."
            r = mkb([home_btn()])
        else:
            text = (
                f"💎 گنجینه امتیازی\n\n💰 اعتبار شما: {credits}\n\n"
                f"{chr(10).join(lines)}\n\n"
                "برای خرید، روی دکمه‌ی آیتم مورد نظر بزنید.\n"
                "💡 اعتبار از مشاهده سرفصل، دعوت دوستان و ماموریت‌ها کسب می‌شود."
            )
            rows.append(home_btn())
            r = mkb(rows)
    if is_q:
        await target.edit_message_text(text, reply_markup=r)
    else:
        await target.reply_text(text, reply_markup=r)


async def a_shop_panel(target, is_q=True):
    text = "💎 مدیریت گنجینه\n\nآیتم‌های فعلی:"
    rows = []
    if not SHOP:
        text += "\n\nهیچ آیتمی ساخته نشده."
    else:
        for sid, it in SHOP.items():
            st = "✅ فعال" if it.get("active") else "❌ غیرفعال"
            stock = it.get("stock") if it.get("stock") is not None else "نامحدود"
            text += (
                f"\n• {sid}: {it.get('title', 'بدون نام')} — {st} — "
                f"{it.get('price', 0)}💰 — موجودی: {stock}"
            )
            rows.append([btn(f"🔧 {it.get('title', '...')}", f"a_item_view|{sid}")])
    rows.append([btn("➕ افزودن آیتم", "a_add_item")])
    rows.append(back_btn("a_panel"))
    r = mkb(rows)
    if is_q:
        await target.edit_message_text(text, reply_markup=r)
    else:
        await target.reply_text(text, reply_markup=r)


# ========================= آخرین اتفاقات =========================

async def show_latest_events(target, is_q=True):
    lines = []

    # دوره‌های جدید (آخرین ۳ دوره)
    if COURSES:
        lines.append("📚 دوره‌های آموزشی:")
        for cid, c in list(COURSES.items())[-3:]:
            lesson_count = len(c.get("lessons", []))
            lines.append(f"  📖 {c['title']} — {lesson_count} سرفصل")
        lines.append("")

    # ماموریت‌های فعال (آخرین ۳)
    active_missions = [m for m in MISSIONS if m.get("active", True)]
    if active_missions:
        lines.append("🎯 ماموریت‌های فعال:")
        for m in active_missions[-3:]:
            mtype_icon = {"text": "📝", "photo": "🖼", "video": "🎬"}.get(m.get("type", "text"), "📌")
            lines.append(f"  {mtype_icon} {m.get('title', '---')} — +{m.get('xp_reward', 0)} XP")
        lines.append("")

    # آیتم‌های فعال گنجینه (آخرین ۳)
    active_shop = [item for item in SHOP.values() if item.get("active", False)]
    if active_shop:
        lines.append("💎 آیتم‌های گنجینه:")
        for item in active_shop[-3:]:
            stock = item.get("stock")
            stock_txt = "نامحدود" if stock is None else str(stock)
            lines.append(f"  🛍 {item.get('title', '---')} — {item.get('price', 0)}💰 | موجودی: {stock_txt}")
        lines.append("")

    # ۳ نفر اول جدول رتبه‌بندی
    top = normal_users_sorted()[:3]
    if top:
        medals = ["🥇", "🥈", "🥉"]
        lines.append("🏆 برترین‌های این هفته:")
        for i, u in enumerate(top):
            _migrate_user(u)
            xp = u.get("xp", u.get("points", 0))
            lines.append(f"  {medals[i]} {u.get('first_name', 'ناشناس')} — {xp} XP")
        lines.append("")

    # آخرین نظرات دوره‌ها
    recent_surveys = []
    for cid, votes in SURVEYS.items():
        c = COURSES.get(cid, {})
        if votes:
            total = len(votes)
            excellent = sum(1 for v in votes.values() if v.get("vote") == "excellent")
            pct = int(excellent * 100 / total) if total else 0
            recent_surveys.append((c.get("title", cid), total, pct))
    if recent_surveys:
        lines.append("⭐ نظرات کاربران:")
        for title, total, pct in recent_surveys[-3:]:
            bar = "⭐" * min(5, round(pct / 20))
            lines.append(f"  {bar} {title} — {pct}٪ رضایت ({total} نظر)")
        lines.append("")

    # متن انگیزشی
    total_users = len([u for u in USERS.values() if u["id"] not in ADMIN_IDS])
    total_ls = total_lessons()
    lines.append(
        f"🚀 انگیزه روز:\n"
        f"  «یادگیری سرمایه‌ای است که هرگز از دست نمی‌رود.»\n\n"
        f"👥 {total_users} نفر در حال یادگیری | 📚 {total_ls} سرفصل آموزشی"
    )

    text = "📰 آخرین اتفاقات\n\n" + "\n".join(lines) if lines else "📰 هنوز اتفاق خاصی ثبت نشده."
    r = mkb([
        [btn("📚 لیست دوره‌ها", "courses"), btn("🏅 جدول رتبه", "leaderboard")],
        [btn("🎯 ماموریت‌ها", "missions"), btn("💎 گنجینه امتیازی", "shop")],
        home_btn(),
    ])
    if is_q:
        await target.edit_message_text(text, reply_markup=r)
    else:
        await target.reply_text(text, reply_markup=r)


# ========================= ماموریت‌های امتیازی =========================

async def show_missions(target, user, is_q=True):
    if is_admin(user):
        text = "👑 شما ادمین هستید.\nاز پنل مدیریت، ماموریت‌ها را مدیریت کنید."
        r = mkb([[btn("🎯 مدیریت ماموریت‌ها", "a_missions")], home_btn()])
        if is_q:
            await target.edit_message_text(text, reply_markup=r)
        else:
            await target.reply_text(text, reply_markup=r)
        return

    active = get_active_missions()
    uid = str(user.id)
    u = USERS.get(uid, {})
    _migrate_user(u)
    done_ids = u.get("completed_missions", [])

    if not active:
        text = "🎯 ماموریت‌های امتیازی\n\nبه زودی ماموریت‌های جدید اضافه می‌شوند! 🔥"
        r = mkb([home_btn()])
        if is_q:
            await target.edit_message_text(text, reply_markup=r)
        else:
            await target.reply_text(text, reply_markup=r)
        return

    rows = []
    pending = []
    done_list = []

    for m in active:
        mid = m.get("id", "")
        title = m.get("title", "بدون عنوان")
        mtype = m.get("type", "text")
        xp_r = m.get("xp_reward", 0)
        cr_r = m.get("credits_reward", 0)
        type_icon = {"text": "📝", "photo": "🖼", "video": "🎬"}.get(mtype, "📌")

        if mid in done_ids:
            done_list.append(f"✅ {type_icon} {title}")
        else:
            pending.append((mid, title, mtype, xp_r, cr_r, type_icon))

    text = "🎯 ماموریت‌های امتیازی\n\n"
    text += f"✅ انجام شده: {len(done_list)} ماموریت\n"
    text += f"⏳ باقی‌مانده: {len(pending)} ماموریت\n\n"

    if pending:
        text += "📋 ماموریت‌های فعال:\n"
        for mid, title, mtype, xp_r, cr_r, type_icon in pending:
            text += f"\n{type_icon} {title}\n  🎁 +{xp_r} XP | +{cr_r} اعتبار\n"
        rows = [
            [btn(f"{type_icon} {title[:25]}...", f"mission_view|{mid}")]
            if len(title) > 25 else
            [btn(f"{type_icon} {title}", f"mission_view|{mid}")]
            for mid, title, mtype, xp_r, cr_r, type_icon in pending
        ]

    if done_list:
        text += "\n✅ انجام شده‌ها:\n" + "\n".join(done_list[:5])
        if len(done_list) > 5:
            text += f"\n  و {len(done_list) - 5} ماموریت دیگر..."

    rows.append(home_btn())
    r = mkb(rows)
    if is_q:
        await target.edit_message_text(text, reply_markup=r)
    else:
        await target.reply_text(text, reply_markup=r)


async def show_mission_detail(query, user, mission_id: str):
    mission = next((m for m in MISSIONS if m.get("id") == mission_id), None)
    if not mission or not mission.get("active", True):
        await safe_answer(query, "❌ این ماموریت موجود نیست.", True)
        return

    already_done = has_completed_mission(user.id, mission_id)
    mtype = mission.get("type", "text")
    type_icon = {"text": "📝", "photo": "🖼", "video": "🎬", "platform_link": "🔗"}.get(mtype, "📌")
    xp_r = mission.get("xp_reward", 0)
    cr_r = mission.get("credits_reward", 0)
    content = mission.get("content", "")
    file_id = mission.get("file_id", "")
    caption = mission.get("caption", "") or ""

    header_text = (
        f"{type_icon} {mission.get('title', '')}\n\n"
        f"📝 توضیحات:\n{mission.get('description', '')}\n\n"
        f"🎁 پاداش: +{xp_r} XP | +{cr_r} اعتبار\n\n"
    )

    done_r = mkb([
        [btn("✅ انجام دادم، پاداش بده!", f"mission_done|{mission_id}")],
        back_btn("missions"),
    ])

    if already_done:
        await query.edit_message_text(
            header_text + "✅ این ماموریت را انجام داده‌اید!",
            reply_markup=mkb([back_btn("missions")])
        )
        return

    if mtype == "platform_link":
        p = mission.get("target_platform", "")
        pname = platform_name(p)
        if user_has_platform(user.id, p):
            await query.edit_message_text(
                header_text + f"✅ شما قبلاً به {pname} متصل شده‌اید.",
                reply_markup=mkb([back_btn("missions")]),
            )
            return
        if not (platform_enabled(p) and platform_configured(p)):
            await query.edit_message_text(
                header_text + f"⏳ اتصال به {pname} فعلاً در دسترس نیست.",
                reply_markup=mkb([back_btn("missions")]),
            )
            return
        await query.edit_message_text(
            header_text + f"برای دریافت پاداش، حساب خود را به {pname} متصل کنید.\n"
                          f"تکمیل این ماموریت بعد از اتصال موفق، خودکار انجام می‌شود.",
            reply_markup=mkb([
                [btn(f"🔗 اتصال به {pname}", f"u_link|{p}")],
                back_btn("missions"),
            ]),
        )
        return

    if mtype == "text":
        # محتوای متنی را در همین پیام + دکمه در پایین نمایش بده
        full_text = header_text + (f"📌 محتوا:\n{content}" if content else "📌 محتوای این ماموریت:")
        await query.edit_message_text(full_text, reply_markup=done_r)
    else:
        # عکس/ویدیو: اول پیام اطلاعاتی، سپس رسانه با دکمه «انجام دادم» در پایین آن
        await query.edit_message_text(
            header_text + "📌 محتوا را در پایین ببینید:",
            reply_markup=mkb([back_btn("missions")])
        )
        try:
            if mtype == "photo" and file_id:
                await query.message.chat.send_photo(
                    file_id, caption=caption or None, reply_markup=done_r
                )
            elif mtype == "video" and file_id:
                await query.message.chat.send_video(
                    file_id, caption=caption or None, reply_markup=done_r
                )
        except Exception as e:
            logger.error(f"Mission content send error: {e}")
            await query.message.chat.send_message("✅ برای دریافت پاداش:", reply_markup=done_r)


# ========================= مسیر شغلی =========================

async def show_career_path(target, user, is_q=False):
    text = (
        "🧠 مسیر شغلی هوشمند\n\n"
        "با گذراندن دوره‌ها، امتیاز جمع کنید و به سمت فرصت‌های شغلی بهتر پیش بروید.\n"
        "این بخش به زودی با راهنمایی شغلی و پیشنهاد مسیر مناسب برای شما کامل می‌شود.\n\n"
        "برای شروع، دوره‌ها را ببینید و پروفایل خود را تکمیل کنید."
    )
    r = mkb([home_btn()])
    if is_q:
        await target.edit_message_text(text, reply_markup=r)
    else:
        await target.reply_text(text, reply_markup=r)


# ========================= رتبه‌بندی =========================

async def show_leaderboard(q):
    top = normal_users_sorted()[:10]
    if not top:
        await q.edit_message_text("🏅 هنوز کاربری ثبت‌نام نکرده!", reply_markup=mkb([home_btn()]))
        return
    medals = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟"]
    text = "🏅 جدول رتبه‌بندی (۱۰ نفر برتر)\n\nرتبه‌بندی بر اساس امتیاز رشد (XP)\n\n"
    for i, u in enumerate(top):
        _migrate_user(u)
        xp = u.get("xp", u.get("points", 0))
        edu_rank = get_educational_rank(xp)
        text += (
            f"{medals[i]} {u.get('first_name', 'ناشناس')} "
            f"{edu_rank['icon']} — {xp} XP ({valid_refs(u['id'])} دعوت)\n"
        )
    text += (
        "\n━━━━━━━━━━━━━━━━\n"
        "💡 روش‌های کسب امتیاز رشد (XP):\n"
        "  📖 مشاهده سرفصل = +۵ XP\n"
        "  👥 دعوت دوست معتبر = +۱۰ XP\n"
        "  📊 نظرسنجی دوره = +۴۰ XP\n"
        "  🎯 ماموریت‌های امتیازی = تا +۱۰۰ XP"
    )
    await q.edit_message_text(text, reply_markup=mkb([[btn("🎯 ماموریت‌ها", "missions")], home_btn()]))


# ========================= پشتیبانی =========================

async def show_support(target, is_q=False, user=None):
    if user and is_admin(user):
        text = "👑 برای مشاهده پیام‌های کاربران از پنل مدیریت > گزارش‌ها استفاده کنید."
        r = mkb([[btn("📬 پیام‌های کاربران", "a_tickets")], home_btn()])
    else:
        sup_disp, sup_url = support_link()
        text = (
            f"📞 پشتیبانی\n\nسوال یا مشکلی دارید؟ ما اینجاییم! 💙\n\n"
            f"🔹 روش ۱: دکمه «ارسال پیام» را بزنید و پیامتان را بنویسید.\n"
            f"    تیم پشتیبانی در اسرع وقت پاسخ خواهد داد.\n\n"
            f"🔹 روش ۲: مستقیم به پشتیبانی مراجعه کنید:\n    {sup_disp}"
        )
        r = mkb([
            [btn("✉️ ارسال پیام به پشتیبانی", "send_ticket")],
            [btn(f"💬 پشتیبانی {sup_disp}", url=sup_url)],
            home_btn(),
        ])
    if is_q:
        await target.edit_message_text(text, reply_markup=r)
    else:
        await target.reply_text(text, reply_markup=r)


# ========================= پنل ادمین =========================

async def admin_panel(target, is_q=True):
    text = "👑 پنل مدیریت\n\nاز اینجا می‌تونید دوره‌ها، کاربران، ماموریت‌ها و تنظیمات ربات رو مدیریت کنید."
    r = mkb([
        [btn("📚 مدیریت دوره‌ها", "a_courses_menu")],
        [btn("🎯 مدیریت ماموریت‌ها", "a_missions")],
        [btn("💎 مدیریت گنجینه", "a_shop")],
        [btn("👥 مدیریت کاربران", "a_users_manage")],
        [btn("🔑 دسترسی بخش‌ها", "a_feature_access")],
        [btn("💵 درخواست‌های نقدی", "a_cash_sales")],
        [btn("📊 گزارش‌ها و آمار", "a_reports")],
        [btn("📣 مرکز پیام‌رسانی", "a_messaging")],
        [btn("🤖 مدیریت یار هوشمند", "aim_a_menu")],
        [btn("🎀 مدیریت ربات گیسو", "a_giso_management")],
        [btn("⚙️ تنظیمات عمومی", "a_global_settings")],
        home_btn(),
    ])
    if is_q:
        await target.edit_message_text(text, reply_markup=r)
    else:
        await target.reply_text(text, reply_markup=r)


# ========================= مدیریت کاربران (ادمین) =========================

async def show_users_manage(target, is_q=True):
    total = len([u for u in USERS.values() if u["id"] not in ADMIN_IDS])
    banned = sum(1 for u in USERS.values() if u.get("is_banned") and u["id"] not in ADMIN_IDS)
    text = (
        f"👥 مدیریت کاربران\n\n"
        f"📊 کل کاربران: {total}\n"
        f"🚫 بن‌شده: {banned}\n\n"
        "جستجوی کاربر با آی‌دی عددی یا مشاهده لیست همه کاربران:"
    )
    r = mkb([
        [btn("🔍 جستجوی کاربر با آی‌دی", "a_user_search")],
        [btn("📋 لیست کاربران", "a_users_list|0")],
        [btn("🗑 حذف کاربران", "adm_del_menu")],
        back_btn("a_panel"),
    ])
    if is_q:
        await target.edit_message_text(text, reply_markup=r)
    else:
        await target.reply_text(text, reply_markup=r)


async def show_user_delete_menu(target, is_q=True):
    text = (
        "🗑 حذف کاربران\n\n"
        "حذف‌ها فوری انجام می‌شوند؛ هیچ عبارت تأییدی لازم نیست.\n"
        "همه عملیات در user_deletion_logs ثبت می‌شود."
    )
    r = mkb([
        [btn("🗑 حذف همه کاربران", "adm_del_all")],
        [btn("📱 حذف با شماره همراه", "adm_del_by_phone")],
        [btn("📋 حذف از لیست", "adm_del_from_list")],
        back_btn("a_users_manage"),
    ])
    if is_q:
        await target.edit_message_text(text, reply_markup=r)
    else:
        await target.reply_text(text, reply_markup=r)


async def show_user_delete_list(target, page: int = 0, is_q=True):
    PAGE_SIZE = 10
    users = list(USERS.values())
    users.sort(key=lambda u: u.get("joined", 0), reverse=True)
    total = len(users)
    start = page * PAGE_SIZE
    end = min(start + PAGE_SIZE, total)
    chunk = users[start:end]
    text = f"📋 حذف از لیست کاربران (صفحه {page + 1})\n\nکل: {total} کاربر\nیک دکمه = حذف فوری.\n"
    rows = []
    for u in chunk:
        _migrate_user(u)
        uid_str = str(u.get("id"))
        name = (u.get("first_name") or "کاربر")[:18]
        phone = u.get("phone") or uid_str
        rows.append([btn(f"🗑 {name} — {phone}", f"adm_del_user|{uid_str}")])
    nav = []
    if page > 0:
        nav.append(btn("⬅️ قبلی", f"adm_del_from_list|{page - 1}"))
    if end < total:
        nav.append(btn("بعدی ➡️", f"adm_del_from_list|{page + 1}"))
    if nav:
        rows.append(nav)
    rows.append(back_btn("adm_del_menu"))
    r = mkb(rows)
    if is_q:
        await target.edit_message_text(text, reply_markup=r)
    else:
        await target.reply_text(text, reply_markup=r)


async def show_users_list(target, page: int = 0, is_q=True):
    """[مشکل 2] نمایش لیست کاربران با صفحه‌بندی"""
    PAGE_SIZE = 10
    normal = [u for u in USERS.values() if u["id"] not in ADMIN_IDS]
    normal.sort(key=lambda u: u.get("joined", 0), reverse=True)
    total = len(normal)
    start = page * PAGE_SIZE
    end = min(start + PAGE_SIZE, total)
    chunk = normal[start:end]

    text = f"📋 لیست کاربران (صفحه {page + 1})\n\nکل: {total} کاربر\n\n"
    rows = []
    for u in chunk:
        _migrate_user(u)
        uid_str = str(u["id"])
        uname = f"@{u['username']}" if u.get("username") else str(u["id"])
        ban_icon = "🚫" if u.get("is_banned") else "✅"
        text += f"{ban_icon} {u.get('first_name', 'ناشناس')} — {uname} | {u.get('xp', 0)} XP\n"
        rows.append([btn(f"👤 {u.get('first_name', 'ناشناس')[:20]}", f"a_user_detail|{uid_str}")])

    nav = []
    if page > 0:
        nav.append(btn("⬅️ قبلی", f"a_users_list|{page - 1}"))
    if end < total:
        nav.append(btn("بعدی ➡️", f"a_users_list|{page + 1}"))
    if nav:
        rows.append(nav)
    rows.append(back_btn("a_users_manage"))
    r = mkb(rows)
    if is_q:
        await target.edit_message_text(text, reply_markup=r)
    else:
        await target.reply_text(text, reply_markup=r)


async def show_user_detail(target, uid_str: str, is_q=True):
    u = USERS.get(uid_str)
    if not u:
        text = "❌ کاربر پیدا نشد."
        r = mkb([back_btn("a_users_manage")])
        if is_q:
            await target.edit_message_text(text, reply_markup=r)
        else:
            await target.reply_text(text, reply_markup=r)
        return
    _migrate_user(u)
    uid = u["id"]
    xp = u.get("xp", 0)
    credits_ = u.get("credits", 0)
    refs = valid_refs(uid)
    banned = "🚫 بله" if u.get("is_banned") else "✅ خیر"
    muted = "🔇 بله" if is_user_muted(uid) else "✅ خیر"
    uname = f"@{u['username']}" if u.get("username") else "ندارد"
    # [مشکل 3] شمارش محدودیت‌های اختصاصی
    user_restrictions = USER_FEATURE_RESTRICTIONS.get(uid_str, {})
    active_restrictions = sum(1 for r in user_restrictions.values() if r.get("is_blocked"))
    text = (
        f"👤 کاربر: {u.get('first_name', 'ناشناس')}\n"
        f"🆔 آی‌دی: {uid}\n"
        f"📛 یوزرنیم: {uname}\n"
        f"📈 XP: {xp}\n"
        f"💰 اعتبار: {credits_}\n"
        f"👥 دعوت‌ها: {refs}\n"
        f"🚫 بن: {banned}\n"
        f"🔇 میوت: {muted}\n"
        f"🔐 محدودیت بخش‌ها: {active_restrictions} بخش محدود\n"
    )
    ban_btn_text = "✅ آنبن کردن" if u.get("is_banned") else "🚫 بن کردن"
    ban_cb = f"a_user_unban|{uid_str}" if u.get("is_banned") else f"a_user_ban|{uid_str}"
    mute_cb = f"a_user_unmute|{uid_str}" if is_user_muted(uid) else f"a_user_mute|{uid_str}"
    mute_btn_text = "✅ آنمیوت" if is_user_muted(uid) else "🔇 میوت"
    r = mkb([
        [btn("📈 تنظیم XP", f"a_user_xp|{uid_str}"), btn("💰 تنظیم اعتبار", f"a_user_credit|{uid_str}")],
        [btn(ban_btn_text, ban_cb), btn(mute_btn_text, mute_cb)],
        [btn("🔐 محدودیت بخش‌های اختصاصی", f"a_user_panel_restrict|{uid_str}")],
        back_btn("a_users_manage"),
    ])
    if is_q:
        await target.edit_message_text(text, reply_markup=r)
    else:
        await target.reply_text(text, reply_markup=r)


async def show_user_feature_restrictions(target, uid_str: str, is_q=True):
    """[مشکل 3] نمایش و مدیریت محدودیت‌های اختصاصی بخش‌های پنل کاربر"""
    u = USERS.get(uid_str)
    if not u:
        t = "❌ کاربر پیدا نشد."
        r = mkb([back_btn(f"a_user_detail|{uid_str}")])
        if is_q:
            await target.edit_message_text(t, reply_markup=r)
        else:
            await target.reply_text(t, reply_markup=r)
        return
    _migrate_user(u)
    uid = u["id"]
    text = (
        f"🔐 محدودیت بخش‌های اختصاصی\n"
        f"👤 کاربر: {u.get('first_name', 'ناشناس')} (آی‌دی: {uid})\n\n"
        "برای محدود/آزاد کردن هر بخش روی آن بزنید:\n"
    )
    rows = []
    for fkey, flabel in FEATURE_KEYS:
        r_data = get_user_feature_restriction(uid, fkey)
        if r_data and r_data.get("is_blocked"):
            until_ts = r_data.get("until_ts", 0)
            if until_ts > 0:
                remaining = max(0, until_ts - int(time.time()))
                hrs = remaining // 3600
                status = f"🔒 محدود ({hrs}ساعت)"
            else:
                status = "🔒 محدود دائم"
            action_cb = f"a_user_feat_unblock|{uid_str}|{fkey}"
            action_label = f"✅ رفع محدودیت"
        else:
            status = "✅ آزاد"
            action_cb = f"a_user_feat_block|{uid_str}|{fkey}"
            action_label = f"🔒 محدود کردن"
        text += f"\n{status} {flabel}"
        rows.append([btn(f"{action_label} — {flabel}", action_cb)])
    rows.append(back_btn(f"a_user_detail|{uid_str}"))
    r = mkb(rows)
    if is_q:
        await target.edit_message_text(text, reply_markup=r)
    else:
        await target.reply_text(text, reply_markup=r)


async def show_user_xp_panel(target, uid_str: str, is_q=True):
    u = USERS.get(uid_str)
    if not u:
        t = "❌ کاربر پیدا نشد."
        r = mkb([back_btn("a_users_manage")])
    else:
        _migrate_user(u)
        xp = u.get("xp", 0)
        t = f"📈 مدیریت XP کاربر: {u.get('first_name', '---')}\n\nXP فعلی: {xp}\n\nعملیات:"
        r = mkb([
            [btn("➕ افزودن XP", f"a_user_xp_add|{uid_str}"), btn("🎯 تنظیم مقدار", f"a_user_xp_set|{uid_str}")],
            back_btn(f"a_user_detail|{uid_str}"),
        ])
    if is_q:
        await target.edit_message_text(t, reply_markup=r)
    else:
        await target.reply_text(t, reply_markup=r)


async def show_user_credit_panel(target, uid_str: str, is_q=True):
    u = USERS.get(uid_str)
    if not u:
        t = "❌ کاربر پیدا نشد."
        r = mkb([back_btn("a_users_manage")])
    else:
        _migrate_user(u)
        cr = u.get("credits", 0)
        t = f"💰 مدیریت اعتبار کاربر: {u.get('first_name', '---')}\n\nاعتبار فعلی: {cr}\n\nعملیات:"
        r = mkb([
            [btn("➕ افزودن اعتبار", f"a_user_credit_add|{uid_str}"),
             btn("🎯 تنظیم مقدار", f"a_user_credit_set|{uid_str}")],
            back_btn(f"a_user_detail|{uid_str}"),
        ])
    if is_q:
        await target.edit_message_text(t, reply_markup=r)
    else:
        await target.reply_text(t, reply_markup=r)


# ========================= دسترسی بخش‌ها (ادمین) =========================

async def show_feature_access_panel(target, is_q=True):
    text = "🔑 مدیریت دسترسی بخش‌ها\n\nبرای هر بخش می‌توانید حداقل XP، اعتبار، سطح و رتبه تنظیم کنید.\n\n"
    rows = []
    for fkey, flabel in FEATURE_KEYS:
        rule = get_feature_rule(fkey)
        has_rule = any(rule.values())
        status = "🔒 محدود" if has_rule else "🔓 آزاد"
        text += f"{status} {flabel}\n"
        rows.append([btn(f"🔧 {flabel}", f"a_feature_set|{fkey}")])
    rows.append(back_btn("a_panel"))
    r = mkb(rows)
    if is_q:
        await target.edit_message_text(text, reply_markup=r)
    else:
        await target.reply_text(text, reply_markup=r)


async def show_feature_detail(target, fkey: str, is_q=True):
    flabel = FEATURE_LABELS.get(fkey, fkey)
    rule = get_feature_rule(fkey)
    lvl_name = USER_LEVELS[rule["min_level"]]["title"] if rule["min_level"] < len(USER_LEVELS) else "نامعتبر"
    rank_name = EDUCATIONAL_RANKS[rule["min_edu_rank"]]["title"] if rule["min_edu_rank"] < len(EDUCATIONAL_RANKS) else "نامعتبر"
    text = (
        f"🔑 تنظیم دسترسی: {flabel}\n\n"
        f"📈 حداقل XP: {rule['min_xp']} (0 = بدون محدودیت)\n"
        f"💰 حداقل اعتبار: {rule['min_credits']} (0 = بدون محدودیت)\n"
        f"⭐ حداقل سطح: {rule['min_level']} ({lvl_name}) (0 = بدون محدودیت)\n"
        f"🎓 حداقل رتبه علمی: {rule['min_edu_rank']} ({rank_name}) (0 = بدون محدودیت)\n\n"
        "برای تنظیم هر مقدار روی دکمه آن بزنید:"
    )
    r = mkb([
        [btn(f"📈 حداقل XP ({rule['min_xp']})", f"a_feature_field|{fkey}|min_xp")],
        [btn(f"💰 حداقل اعتبار ({rule['min_credits']})", f"a_feature_field|{fkey}|min_credits")],
        [btn(f"⭐ حداقل سطح ({rule['min_level']})", f"a_feature_field|{fkey}|min_level")],
        [btn(f"🎓 حداقل رتبه ({rule['min_edu_rank']})", f"a_feature_field|{fkey}|min_edu_rank")],
        [btn("🔓 حذف همه محدودیت‌ها", f"a_feature_reset|{fkey}")],
        back_btn("a_feature_access"),
    ])
    if is_q:
        await target.edit_message_text(text, reply_markup=r)
    else:
        await target.reply_text(text, reply_markup=r)


# ========================= فروش نقدی (ادمین) =========================

async def show_cash_sales_admin(target, is_q=True):
    pending = [r for r in CASH_SALES if r.get("status") == "pending"]
    all_count = len(CASH_SALES)
    text = (
        f"💵 درخواست‌های فروش نقدی\n\n"
        f"📊 کل درخواست‌ها: {all_count}\n"
        f"⏳ در انتظار بررسی: {len(pending)}\n\n"
    )
    rows = []
    if pending:
        text += "📋 درخواست‌های در انتظار:\n"
        for req in pending[-10:]:
            req_id = req.get("_db_id", "?")
            text += (
                f"\n• #{req_id} | {req.get('user_name', '---')} "
                f"| دوره: {req.get('course_title', '---')[:15]}"
            )
            rows.append([btn(f"🔍 بررسی #{req_id}", f"a_cash_review|{req_id}")])
    else:
        text += "✅ هیچ درخواست در انتظاری وجود ندارد."
    rows.append(back_btn("a_panel"))
    r = mkb(rows)
    if is_q:
        await target.edit_message_text(text, reply_markup=r)
    else:
        await target.reply_text(text, reply_markup=r)


async def show_cash_sale_review(target, req_id: int, is_q=True):
    """[مشکل 5] نمایش جزئیات درخواست فروش نقدی برای ادمین"""
    import datetime
    req = next((r for r in CASH_SALES if r.get("_db_id") == req_id), None)
    if not req:
        t = "❌ درخواست پیدا نشد."
        r = mkb([back_btn("a_cash_sales")])
        if is_q:
            await target.edit_message_text(t, reply_markup=r)
        else:
            await target.reply_text(t, reply_markup=r)
        return
    dt = datetime.datetime.fromtimestamp(req.get("requested_at", 0)).strftime("%Y-%m-%d %H:%M")
    status_map = {"pending": "⏳ در انتظار", "approved": "✅ تأیید شده", "rejected": "❌ رد شده"}
    status_text = status_map.get(req.get("status"), req.get("status", ""))
    uname = f"@{req['username']}" if req.get("username") else "ندارد"
    target_type = req.get("target_type", "course")
    amount = req.get("amount", 0)
    payment_method = req.get("payment_method", "")
    lesson_title = req.get("lesson_title", "")
    text = (
        f"💵 درخواست فروش نقدی #{req_id}\n\n"
        f"👤 کاربر: {req.get('user_name', '---')}\n"
        f"📛 یوزرنیم: {uname}\n"
        f"🆔 آی‌دی: {req.get('user_id', '---')}\n"
        f"📚 دوره: {req.get('course_title', '---')}\n"
    )
    if target_type == "lesson" and lesson_title:
        text += f"📖 سرفصل: {lesson_title}\n"
    if amount > 0:
        text += f"💰 مبلغ: {amount:,} تومان\n"
    if payment_method:
        text += f"💳 روش پرداخت: {payment_method}\n"
    text += (
        f"📅 تاریخ درخواست: {dt}\n"
        f"📋 وضعیت: {status_text}\n"
    )
    fiche_file_id = req.get("fiche_file_id", "")
    rows = []
    if req.get("status") == "pending":
        rows.append([
            btn("✅ تأیید", f"a_cash_approve|{req_id}"),
            btn("❌ رد", f"a_cash_reject|{req_id}"),
        ])
    if fiche_file_id:
        rows.append([btn("🖼 مشاهده فیش پرداخت", f"a_cash_show_fiche|{req_id}")])
    rows.append(back_btn("a_cash_sales"))
    r = mkb(rows)
    if is_q:
        await target.edit_message_text(text, reply_markup=r)
    else:
        await target.reply_text(text, reply_markup=r)


# ========================= فروش نقدی (کاربر) =========================

def format_card_number(raw: str) -> str:
    """شماره کارت را به صورت گروه‌های ۴ رقمی برمی‌گرداند."""
    digits = "".join(ch for ch in str(raw) if ch.isdigit())
    if not digits:
        return str(raw)
    return " ".join(digits[i:i + 4] for i in range(0, len(digits), 4))


def format_card_admin(card_number: str, card_holder: str = "", bank_name: str = "") -> str:
    """نمایش خلاصه اطلاعات کارت برای پنل ادمین (بدون HTML)."""
    if not card_number:
        return "تنظیم نشده"
    parts = [format_card_number(card_number)]
    if card_holder:
        parts.append(f"به نام {card_holder}")
    if bank_name:
        parts.append(f"بانک {bank_name}")
    return " — ".join(parts)


def build_payment_info_html(setting: dict) -> str:
    """بلوک اطلاعات پرداخت (HTML) — شماره کارت قابل‌کپی، نام صاحب کارت و بانک."""
    card_number = setting.get("card_number", "")
    card_holder = setting.get("card_holder", "")
    bank_name = setting.get("bank_name", "")
    payment_method = setting.get("payment_method", "")
    lines = []
    if card_number:
        lines.append("💳 شماره کارت (برای کپی، روی شماره بزنید یا نگه دارید):")
        lines.append(f"<code>{html.escape(card_number)}</code>")
        if card_holder:
            lines.append(f"👤 به نام: {html.escape(card_holder)}")
        if bank_name:
            lines.append(f"🏦 بانک: {html.escape(bank_name)}")
    elif payment_method:
        lines.append(f"💳 روش پرداخت:\n{html.escape(payment_method)}")
    return "\n".join(lines)


async def _send_cash_page(target, text, r, is_q):
    if is_q:
        try:
            await target.edit_message_text(text, reply_markup=r, parse_mode="HTML")
        except Exception:
            await target.message.reply_text(text, reply_markup=r, parse_mode="HTML")
    else:
        await target.reply_text(text, reply_markup=r, parse_mode="HTML")


async def show_cash_sale_request(target, user, course_id: str, is_q=False):
    """[مشکل 4/5] صفحه خرید نقدی دوره — با اطلاعات کامل پرداخت"""
    course = COURSES.get(course_id)
    if not course:
        await target.reply_text("❌ دوره پیدا نشد.")
        return
    # دریافت تنظیمات فروش نقدی این دوره
    setting = get_cash_sale_setting("course", course_id)
    if not setting:
        await target.reply_text(
            "❌ فروش نقدی برای این دوره فعال نیست.\n"
            f"📞 برای اطلاعات بیشتر با پشتیبانی تماس بگیرید: {support_link()[0]}",
            reply_markup=mkb([back_btn(f"course|{course_id}")])
        )
        return
    title = html.escape(course.get("title", "---"))
    amount = setting.get("amount", 0)
    # [مشکل 4] قیمت تنظیم‌نشده → هدایت به پشتیبانی
    if amount <= 0:
        text = (
            f"💵 خرید نقدی دوره\n\n"
            f"📚 دوره: {title}\n\n"
            f"💬 برای تهیه این مورد با پشتیبانی تماس بگیرید."
        )
        r = mkb([
            [btn("✉️ ارسال پیام به پشتیبانی", "send_ticket")],
            back_btn(f"course|{course_id}"),
        ])
        await _send_cash_page(target, text, r, is_q)
        return
    display_note = setting.get("display_note", "")
    payment_html = build_payment_info_html(setting)
    text = (
        f"💵 خرید نقدی دوره\n\n"
        f"📚 دوره: {title}\n"
        f"💰 مبلغ: {amount:,} تومان\n"
    )
    if payment_html:
        text += f"\n{payment_html}\n"
    if display_note:
        text += f"\n📝 توضیحات: {html.escape(display_note)}\n"
    text += (
        "\n━━━━━━━━━━━━━━━━\n"
        "📋 مراحل خرید:\n"
        f"1️⃣ مبلغ را واریز کنید.\n"
        f"2️⃣ دکمه «ارسال فیش پرداخت» را بزنید.\n"
        f"3️⃣ عکس فیش/رسید را ارسال کنید.\n"
        f"4️⃣ پس از تأیید ادمین، دسترسی دوره فعال می‌شود.\n\n"
        f"📞 پشتیبانی: {html.escape(support_link()[0])}"
    )
    r = mkb([
        [btn("📤 ارسال فیش پرداخت", f"cash_send_fiche|course|{course_id}")],
        back_btn(f"course|{course_id}"),
    ])
    await _send_cash_page(target, text, r, is_q)


async def show_cash_lesson_sale_request(target, user, course_id: str, lesson_idx: int, is_q=False):
    """[مشکل 4/5] صفحه خرید نقدی سرفصل"""
    course = COURSES.get(course_id)
    if not course:
        await target.reply_text("❌ دوره پیدا نشد.")
        return
    lessons = course.get("lessons", [])
    if lesson_idx >= len(lessons):
        await target.reply_text("❌ سرفصل پیدا نشد.")
        return
    lesson = lessons[lesson_idx]
    lid = lesson.get("lid", str(lesson_idx))
    setting = get_cash_sale_setting("lesson", lid)
    if not setting:
        await target.reply_text(
            "❌ فروش نقدی برای این سرفصل فعال نیست.",
            reply_markup=mkb([back_btn(f"course|{course_id}")])
        )
        return
    c_title = html.escape(course.get("title", "---"))
    l_title = html.escape(lesson.get("title", "---"))
    amount = setting.get("amount", 0)
    # [مشکل 4] قیمت تنظیم‌نشده → هدایت به پشتیبانی
    if amount <= 0:
        text = (
            f"💵 خرید نقدی سرفصل\n\n"
            f"📚 دوره: {c_title}\n"
            f"📖 سرفصل: {l_title}\n\n"
            f"💬 برای تهیه این مورد با پشتیبانی تماس بگیرید."
        )
        r = mkb([
            [btn("✉️ ارسال پیام به پشتیبانی", "send_ticket")],
            back_btn(f"course|{course_id}"),
        ])
        await _send_cash_page(target, text, r, is_q)
        return
    display_note = setting.get("display_note", "")
    payment_html = build_payment_info_html(setting)
    text = (
        f"💵 خرید نقدی سرفصل\n\n"
        f"📚 دوره: {c_title}\n"
        f"📖 سرفصل: {l_title}\n"
        f"💰 مبلغ: {amount:,} تومان\n"
    )
    if payment_html:
        text += f"\n{payment_html}\n"
    if display_note:
        text += f"\n📝 توضیحات: {html.escape(display_note)}\n"
    text += (
        "\n📋 مراحل خرید:\n"
        f"1️⃣ مبلغ را واریز کنید.\n"
        f"2️⃣ دکمه «ارسال فیش پرداخت» را بزنید.\n"
        f"3️⃣ پس از تأیید ادمین، دسترسی سرفصل فعال می‌شود.\n\n"
        f"📞 پشتیبانی: {html.escape(support_link()[0])}"
    )
    r = mkb([
        [btn("📤 ارسال فیش پرداخت", f"cash_send_fiche|lesson|{lid}|{course_id}|{lesson_idx}")],
        back_btn(f"course|{course_id}"),
    ])
    await _send_cash_page(target, text, r, is_q)


async def a_missions_panel(target, is_q=True):
    text = "🎯 مدیریت ماموریت‌های امتیازی\n\n"
    rows = []
    if not MISSIONS:
        text += "هیچ ماموریتی ثبت نشده."
    else:
        for m in MISSIONS:
            mid = m.get("id", "")
            st = "✅ فعال" if m.get("active", True) else "❌ غیرفعال"
            mtype = m.get("type", "text")
            type_icon = {"text": "📝", "photo": "🖼", "video": "🎬"}.get(mtype, "📌")
            text += f"\n{type_icon} {m.get('title', 'بی‌نام')} — {st} — +{m.get('xp_reward', 0)} XP"
            rows.append([btn(f"🔧 {type_icon} {m.get('title', '...')[:20]}", f"a_mission_view|{mid}")])
    rows.append([btn("➕ ثبت ماموریت جدید", "a_mission_add")])
    rows.append(back_btn("a_panel"))
    r = mkb(rows)
    if is_q:
        await target.edit_message_text(text, reply_markup=r)
    else:
        await target.reply_text(text, reply_markup=r)


# ========================= فوروارد سرفصل =========================

async def save_forwarded(msg, ctx):
    fc = getattr(msg, "forward_from_chat", None)
    fm = getattr(msg, "forward_from_message_id", None)

    if fc and fm:
        lesson = {"type": "channel_post", "source_chat_id": fc.id, "source_message_id": fm}
    elif msg.photo:
        lesson = {"type": "photo", "file_id": msg.photo[-1].file_id, "caption": msg.caption or ""}
    elif msg.video:
        lesson = {"type": "video", "file_id": msg.video.file_id, "caption": msg.caption or ""}
    elif msg.document:
        lesson = {"type": "document", "file_id": msg.document.file_id, "caption": msg.caption or ""}
    elif msg.text:
        t = msg.text.strip()
        lesson = (
            {"type": "link", "content": t} if t.startswith("http")
            else {"type": "text", "content": t}
        )
    else:
        await msg.reply_text("❌ این نوع فایل پشتیبانی نمی‌شود.")
        return

    ok, cid, idx, r = apply_lesson(ctx, lesson)
    if ok:
        await msg.reply_text(
            f"✅ سرفصل با موفقیت ذخیره شد!\n📌 نوع: {ltype(lesson['type'])}",
            reply_markup=done_kb(cid, idx),
        )
    else:
        await msg.reply_text(f"❌ {r}")


# ========================= هوش مصنوعی (AI) =========================
# کیبوردها و صفحات پنل «🤖 مدیریت AI»
# استایل دکمه‌ها هماهنگ با سایر بخش‌های ربات (btn/mkb/back_btn)

def ai_admin_kb():
    """منوی اصلی مدیریت AI."""
    return mkb([
        [btn("📋 فهرست پروایدرها", "ai_list")],
        [btn("➕ افزودن پروایدر", "ai_add"),
         btn("✏️ ویرایش پروایدر", "ai_edit")],
        [btn("⏯ فعال/غیرفعال", "ai_toggle"),
         btn("🗑 حذف پروایدر", "ai_delete")],
        [btn("🔄 بررسی یک پروایدر", "ai_check_one"),
         btn("🔁 بررسی همه", "ai_check_all")],
        [btn("📊 گزارش وضعیت", "ai_status")],
        [btn("💬 تست گفتگو", "ai_try")],
        back_btn("a_global_settings"),
    ])


def ai_providers_kb(action: str, back_cb: str = "a_ai_panel"):
    """
    فهرست پروایدرها به‌صورت دکمه.
    action مشخص می‌کند کلیک روی هر پروایدر چه کاری انجام دهد.
    نمونه callback: ai_do|{action}|{name}
    """
    from db import list_ai_providers
    rows = []
    for r in list_ai_providers():
        icon = "✅" if r["enabled"] else "❌"
        flag = " 🇮🇷" if r["is_iranian"] else ""
        rows.append([btn(f"{icon} {r['name']} ({r['kind']}){flag}",
                         f"ai_do|{action}|{r['name']}")])
    if not rows:
        rows.append([btn("— پروایدری ثبت نشده —", "noop")])
    rows.append(back_btn(back_cb))
    return mkb(rows)


def ai_edit_fields_kb(provider_name: str):
    """فیلدهای قابل‌ویرایش یک پروایدر."""
    fields = [
        ("api_key",  "🔑 API Key"),
        ("base_url", "🌐 Base URL"),
        ("api_root", "📁 API Root"),
        ("timeout",  "⏱ Timeout"),
        ("headers",  "📋 Headers (JSON)"),
        ("fallback", "🔄 مدل‌های پشتیبان (JSON)"),
    ]
    rows = [[btn(label, f"ai_field|{provider_name}|{f}")] for f, label in fields]
    rows.append(back_btn("ai_edit"))
    return mkb(rows)


def ai_kind_kb():
    """انتخاب نوع پروایدر هنگام افزودن."""
    return mkb([
        [btn("🔵 openai (سازگار با OpenAI)", "ai_kind|openai")],
        [btn("🟠 cloudflare (Workers AI)", "ai_kind|cloudflare")],
        back_btn("a_ai_panel"),
    ])


def _ai_status_icon(status: str) -> str:
    s = (status or "").lower()
    if s.startswith("ok"):
        return "✅"
    if "not configured" in s:
        return "⚙️"
    if not s:
        return "⚪️"
    return "❌"


async def show_ai_panel(target, is_q=True):
    """صفحهٔ اصلی «🤖 مدیریت AI» با خلاصهٔ وضعیت."""
    from db import list_ai_providers
    rows = list_ai_providers()
    total = len(rows)
    active = sum(1 for r in rows if r["enabled"])
    healthy = sum(1 for r in rows if (r["last_status"] or "").startswith("ok"))
    nokey = sum(1 for r in rows if not (r["api_key"] or "").strip())

    lines = [
        "🤖 مدیریت هوش مصنوعی",
        "━━━━━━━━━━━━━━━━",
        f"📦 کل پروایدرها: {fa_num(total)}",
        f"✅ فعال: {fa_num(active)}   |   🟢 سالم: {fa_num(healthy)}",
    ]
    if nokey:
        lines.append(f"⚙️ بدون API Key: {fa_num(nokey)}")
    lines += [
        "",
        "ℹ️ کلیدها را می‌توانید در فایل .env یا از همین‌جا وارد کنید.",
    ]
    text = "\n".join(lines)
    if is_q:
        await target.edit_message_text(text, reply_markup=ai_admin_kb())
    else:
        await target.reply_text(text, reply_markup=ai_admin_kb())


async def show_ai_list(target, is_q=True):
    """فهرست ساده پروایدرها با مدل انتخابی."""
    from db import list_ai_providers
    rows = list_ai_providers()
    if not rows:
        text = "📋 هیچ پروایدری ثبت نشده است."
    else:
        lines = ["📋 فهرست پروایدرها", "━━━━━━━━━━━━━━━━"]
        for r in rows:
            icon = "✅" if r["enabled"] else "❌"
            flag = " 🇮🇷" if r["is_iranian"] else ""
            key = "🔑" if (r["api_key"] or "").strip() else "⚙️"
            lines.append(
                f"{icon}{key} {r['name']} ({r['kind']}){flag}\n"
                f"    مدل: {r['selected_model'] or '—'}"
            )
        text = "\n".join(lines)
    if is_q:
        await target.edit_message_text(text, reply_markup=ai_admin_kb())
    else:
        await target.reply_text(text, reply_markup=ai_admin_kb())


async def show_ai_status(target, is_q=True):
    """گزارش کامل وضعیت هر پروایدر."""
    from db import list_ai_providers
    rows = list_ai_providers()
    if not rows:
        text = "📊 هیچ پروایدری ثبت نشده است."
    else:
        lines = ["📊 گزارش وضعیت پروایدرها", "━━━━━━━━━━━━━━━━", ""]
        for r in rows:
            models = []
            try:
                models = json.loads(r["models_json"] or "[]")
            except Exception:
                pass
            models_str = "، ".join(models[:3]) if models else "—"
            lines.append(
                f"{_ai_status_icon(r['last_status'])} {r['name']}"
                f"{' 🇮🇷' if r['is_iranian'] else ''}\n"
                f"  وضعیت: {r['last_status'] or '—'}\n"
                f"  مدل انتخابی: {r['selected_model'] or '—'}\n"
                f"  مدل‌ها: {models_str}\n"
                f"  آخرین بررسی: {r['last_checked_at'] or '—'}"
            )
            if r["last_error"]:
                lines.append(f"  ⚠️ {r['last_error'][:110]}")
            lines.append("")
        text = "\n".join(lines)
    if len(text) > 3800:
        text = text[:3800] + "\n…"
    if is_q:
        await target.edit_message_text(text, reply_markup=ai_admin_kb())
    else:
        await target.reply_text(text, reply_markup=ai_admin_kb())


def web_manage_kb():
    """درگاه تفکیک‌شده مدیریت دو سامانه؛ Callback قدیمی حفظ شده است."""
    return mkb([
        [btn("🌐 مدیریت سایت اصلی", "a_web_main_manage")],
        [btn("💎 مدیریت سایت گیسو", "a_web_giso_manage")],
        [btn("🔙 بازگشت به پنل ادمین", "a_panel")],
    ])


def web_main_manage_kb():
    return mkb([
        [btn("🚧 وضعیت و به‌روزرسانی", "site_main_maint_menu")],
        [btn("💾 پشتیبان و بازگردانی", "site_main_backup_menu")],
        [btn("🤖 مدیریت هوش مصنوعی سایت", "a_web_ai_manage")],
        [btn("📋 مدیریت مشاور", "cons_admin_menu")],
        [btn("📊 گزارش سلامت سایت اصلی", "site_main_health")],
        [btn("🧹 پاک‌سازی و نگهداری", "site_cleanup_menu")],
        [btn("🔄 ریستارت ربات آموزشی", "edubot_restart_menu")],
        [btn("🔙 بازگشت به انتخاب سامانه", "a_web_manage")],
    ])


def web_giso_manage_kb(site_url=""):
    rows = [
        [btn("🎀 مدیریت ربات گیسو", "a_giso_management")],
        [btn("🚧 وضعیت و به‌روزرسانی", "site_giso_maint_menu")],
        [btn("💾 پشتیبان و بازگردانی", "site_giso_backup_menu")],
        [btn("🧠 گزارش هوش مصنوعی گیسو", "site_giso_ai_report")],
        [btn("📊 گزارش کلی سلامت گیسو", "site_giso_health")],
        [btn("🧹 پاک‌سازی امن گیسو", "site_giso_cleanup")],
    ]
    if site_url:
        rows.append([btn("🌐 مشاهده سایت گیسو", url=site_url)])
    rows.append([btn("🔙 بازگشت به انتخاب سامانه", "a_web_manage")])
    return mkb(rows)


def web_ai_manage_kb():
    """کیبورد مدیریت هوش مصنوعی سایت"""
    return mkb([
        [btn("📊 نمایش وضعیت هوش مصنوعی", "a_web_ai_status")],
        [btn("🔍 بررسی هوش مصنوعی سایت", "a_web_ai_check")],
        [btn("🔙 بازگشت", "a_web_manage")],
    ])
