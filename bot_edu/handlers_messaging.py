"""
handlers_messaging.py — کمکی‌های مرکز پیام‌رسانی
وابستگی مجاز: config، core، ui و stdlib
"""
import asyncio
import html as _html
import io
import logging
import time

from config import (
    ADMIN_IDS, PLATFORM_LINKS, SETTINGS, USERS,
    DELIVERY_REPORTS, MAX_DELIVERY_REPORTS,
    active_platform_bots, add_delivery_report, get_platform_bot, save,
)
from core import (
    fa_num,
    get_platform_admins,
    group_count,
    group_targets,
    messaging_stats,
    platform_name,
    platform_recipients,
)
from handlers_admin import bot_route_targets
from ui import btn, mkb, back_btn, bcast_confirm_kb

logger = logging.getLogger(__name__)

_BC_DELAY = 0.05          # پیش‌فرض (ثانیه)
BC_DELAY_MIN = 0.1        # حداقل مجاز
BC_DELAY_MAX = 5.0        # حداکثر مجاز


def get_send_delay() -> float:
    """[ویژگی گم‌شده ۱] تأخیر بین ارسال‌ها — قابل تنظیم از پنل."""
    try:
        v = float(SETTINGS.get("bc_send_delay", 0) or 0)
    except (TypeError, ValueError):
        return _BC_DELAY
    if v <= 0:
        return _BC_DELAY
    return max(BC_DELAY_MIN, min(BC_DELAY_MAX, v))


def set_send_delay(value: float) -> float:
    """ذخیرهٔ تأخیر ارسال (بین BC_DELAY_MIN و BC_DELAY_MAX)."""
    v = max(BC_DELAY_MIN, min(BC_DELAY_MAX, float(value)))
    SETTINGS["bc_send_delay"] = v
    save("settings")
    return v


def delay_text() -> str:
    return f"{get_send_delay():g} ثانیه"
_TYPE_FA = {"text": "متنی", "photo": "تصویری", "video": "ویدیو"}
_BC_SIG_CENTER = "📣 ارسال از مرکز پیام‌رسانی\n💙 با احترام، مدیریت"

# گزارش تحویل — همان لیست جهانی config که از دیتابیس پر می‌شود (ماندگار)
_DELIVERY_REPORTS = DELIVERY_REPORTS
_MAX_REPORTS = MAX_DELIVERY_REPORTS


def reset_bc(ctx):
    ctx.user_data.pop("bc", None)
    st = ctx.user_data.get("state", "")
    if isinstance(st, str) and st.startswith("wait_bc_"):
        ctx.user_data.pop("state", None)


def get_route(route: str, user_mode: str = "all") -> str:
    if route == "groups":
        return "groups"
    if route == "bots":
        return "bots"
    if user_mode == "single":
        return "direct"
    return "users"


def _route_label(route: str, user_mode: str = "all") -> str:
    real = get_route(route, user_mode)
    return {
        "groups": "👥 گروه‌ها/کانال‌ها",
        "users": "📩 همه کاربران",
        "direct": "✉️ کاربر مشخص",
        "bots": "🤖 ربات‌های فعال",
    }.get(real, "مرکز پیام‌رسانی")


def _resolve_platforms(dest: str):
    bots = active_platform_bots()
    if dest == "all":
        return list(bots.keys())
    return [dest] if dest in bots else []


def _platform_admin_targets(platform: str) -> list:
    return bot_route_targets(platform, get_platform_admins)


def get_destination_count(route: str, user_mode: str, dest: str):
    plats = _resolve_platforms(dest)
    if not plats:
        return 0, "مقصد"

    real = get_route(route, user_mode)
    if real == "groups":
        return sum(group_count(p) for p in plats), "گروه/کانال"
    if real == "bots":
        total = sum(len(_platform_admin_targets(p)) for p in plats)
        return total, "مقصد"
    if real == "users":
        total = sum(len(platform_recipients(p)) for p in plats)
        return total, "نفر"
    if real == "direct":
        # [باگ ۱ — رفع‌شده] قبلاً این شاخه نبود و همیشه ۰ برمی‌گرداند.
        # برای «کاربر مشخص» تعداد افراد قابل انتخاب در آن پلتفرم گزارش می‌شود.
        total = sum(len(platform_recipients(p)) for p in plats)
        return total, "نفر (قابل انتخاب)"
    return 0, "مخاطب"


def _messaging_summary_text() -> str:
    stats = messaging_stats()
    lines = ["📣 مرکز پیام‌رسانی", "━━━━━━━━━━━━━━━━"]
    for p, s in stats.items():
        lines.append(
            f"🔹 {platform_name(p)}\n"
            f"   👥 اعضا: {fa_num(s['members'])} | 📞 شماره: {fa_num(s['phones'])} | "
            f"🟢 فعال اخیر: {fa_num(s['active'])} | 👥 گروه/کانال: {fa_num(group_count(p))}"
        )
    return "\n".join(lines)


async def show_messaging_center_v2(target, is_q=True):
    text = _messaging_summary_text() + "\n\nمسیر رسمی ارسال را انتخاب کنید:"
    rows = [
        [btn("📊 آمار اعضا", "bc_stats")],
        [btn("📞 لیست شماره‌ها", "bc_phones|0")],
        [btn("📦 گزارش تحویل (۲۰ مورد آخر)", "bc_reports")],
        [btn(f"⏱ تأخیر ارسال ({delay_text()})", "bc_delay")],
        [btn("👥 ارسال به گروه‌ها/کانال‌ها", "bc_route|groups")],
        [btn("📩 ارسال به کاربران", "bc_route|users")],
        [btn("🤖 ارسال به ربات‌های فعال", "bc_route|bots")],
        back_btn("a_panel"),
    ]
    markup = mkb(rows)
    if is_q:
        await target.edit_message_text(text, reply_markup=markup)
    else:
        await target.reply_text(text, reply_markup=markup)


async def show_user_mode_menu(target, is_q=True):
    text = (
        "📩 ارسال به کاربران\n\n"
        "نوع گیرنده را انتخاب کنید:\n"
        "• همه اعضا\n"
        "• یک کاربر مشخص"
    )
    markup = mkb([
        [btn("📩 همه اعضا", "bc_usermode|all")],
        [btn("✉️ کاربر مشخص", "bc_usermode|single")],
        [btn("⬅️ بازگشت", "a_messaging")],
    ])
    if is_q:
        await target.edit_message_text(text, reply_markup=markup)
    else:
        await target.reply_text(text, reply_markup=markup)


async def show_destination_menu(target, route: str, user_mode: str = "all", is_q=True):
    stats = messaging_stats()
    real = get_route(route, user_mode)
    rows = []

    if real == "groups":
        total = group_count("all")
        rows.append([btn(f"🌐 همه پلتفرم‌ها ({fa_num(total)} گروه/کانال)", "bc_dest|all")])
        for p in stats:
            rows.append([btn(f"{platform_name(p)} ({fa_num(group_count(p))} گروه/کانال)", f"bc_dest|{p}")])
        head = "👥 ارسال به گروه‌ها/کانال‌ها\n\nپلتفرم مقصد را انتخاب کنید:"
    elif real == "bots":
        total = sum(len(_platform_admin_targets(p)) for p in stats)
        rows.append([btn(f"🌐 همه پلتفرم‌ها ({fa_num(total)} مقصد)", "bc_dest|all")])
        for p in stats:
            rows.append([btn(f"{platform_name(p)} ({fa_num(len(_platform_admin_targets(p)))} مقصد)", f"bc_dest|{p}")])
        head = (
            "🤖 ارسال به ربات‌های فعال\n\n"
            "این مسیر پیام را به «ادمین‌های ثبت‌شده همان پلتفرم» می‌فرستد.\n"
            "اگر برای یک پلتفرم ادمین ثبت نشده باشد، مقصدی ندارد.\n\n"
            "پلتفرم مقصد را انتخاب کنید:"
        )
    elif real == "direct":
        rows.append([btn("🌐 همه پلتفرم‌ها", "bc_dest|all")])
        for p, s in stats.items():
            rows.append([btn(f"{platform_name(p)} ({fa_num(s['members'])} نفر)", f"bc_dest|{p}")])
        head = "✉️ ارسال به کاربر مشخص\n\nپلتفرم مقصد را انتخاب کنید:"
    else:
        total = sum(s["members"] for s in stats.values())
        rows.append([btn(f"🌐 همه پلتفرم‌ها ({fa_num(total)} نفر)", "bc_dest|all")])
        for p, s in stats.items():
            rows.append([btn(f"{platform_name(p)} ({fa_num(s['members'])} نفر)", f"bc_dest|{p}")])
        head = "📩 ارسال به همه کاربران\n\nپلتفرم مقصد را انتخاب کنید:"

    rows.append([btn("⬅️ بازگشت", "a_messaging")])
    markup = mkb(rows)
    if is_q:
        await target.edit_message_text(head, reply_markup=markup)
    else:
        await target.reply_text(head, reply_markup=markup)


def _caption(bc: dict) -> str:
    title = (bc.get("title") or "").strip()
    desc = (bc.get("desc") or "").strip()
    parts = []
    if title:
        parts.append(f"<b>{_html.escape(title)}</b>")
    if desc:
        parts.append(_html.escape(desc))
    body = "\n\n".join(parts)
    if body:
        return f"{body}\n\n➖➖➖➖➖\n{_BC_SIG_CENTER}"
    return _BC_SIG_CENTER


def _dest_head(bc: dict) -> str:
    route = get_route(bc.get("route", "users"), bc.get("user_mode", "all"))
    if route == "direct":
        return f"✉️ گیرنده: {bc.get('target_display', '')} ({platform_name(bc.get('target_platform', ''))})"
    count = bc.get("count", 0)
    unit = bc.get("unit", "مقصد")
    return f"{_route_label(bc.get('route', 'users'), bc.get('user_mode', 'all'))} → {bc.get('dest_label', '')} ({fa_num(count)} {unit})"


async def show_preview(target, ctx, is_q=True):
    bc = ctx.user_data.get("bc", {})
    ctx.user_data.pop("state", None)
    mtype = bc.get("type", "text")
    head = _dest_head(bc)
    head += f"\n📦 نوع: {_TYPE_FA.get(mtype, mtype)}\n\n— پیش‌نمایش —"
    markup = bcast_confirm_kb()
    chat_id = target.message.chat_id if hasattr(target, "message") and target.message else target.chat_id
    await ctx.bot.send_message(chat_id, head)
    cap = _caption(bc)
    try:
        if mtype == "photo":
            await ctx.bot.send_photo(chat_id, bc.get("file_id"), caption=cap or None, reply_markup=markup, parse_mode="HTML")
        elif mtype == "video":
            await ctx.bot.send_video(chat_id, bc.get("file_id"), caption=cap or None, reply_markup=markup, parse_mode="HTML")
        else:
            await ctx.bot.send_message(chat_id, cap or "(بدون متن)", reply_markup=markup, parse_mode="HTML")
    except Exception as e:
        logger.error(f"bc preview error: {e}")
        await ctx.bot.send_message(chat_id, "⚠️ خطا در پیش‌نمایش. دوباره تلاش کنید.", reply_markup=markup)


def _explain_send_error(e) -> str:
    """
    [کار ۳] ترجمهٔ خطای خام API به علت قابل‌فهم + راه‌حل.
    ادمین به‌جای «Forbidden: ...» می‌فهمد دقیقاً چه کاری باید بکند.
    """
    msg = str(e).lower()
    if "not a member" in msg or "bot was kicked" in msg or "chat not found" in msg:
        return "ربات عضو این گروه/کانال نیست یا حذف شده — دوباره اضافه‌اش کنید"
    if "not enough rights" in msg or "have no rights" in msg or "can't send" in msg:
        return "ربات اجازهٔ ارسال پیام ندارد — ربات را ادمین کنید"
    if "forbidden" in msg or "blocked" in msg:
        return "دسترسی مسدود است — ربات باید ادمین گروه/کانال باشد"
    if "deactivated" in msg:
        return "این حساب/گروه غیرفعال شده است"
    if "user is deactivated" in msg or "user not found" in msg:
        return "کاربر یافت نشد یا حسابش غیرفعال است"
    if "not started" in msg or "can't initiate" in msg:
        return "کاربر هنوز ربات را استارت نکرده است"
    if "flood" in msg or "too many requests" in msg:
        return "محدودیت فلاد — تأخیر ارسال را بیشتر کنید"
    if "timeout" in msg or "timed out" in msg:
        return "اتصال قطع/کند است"
    if "wrong file identifier" in msg or "file_id" in msg:
        return "شناسهٔ فایل روی این پلتفرم معتبر نیست"
    return str(e)[:90]


async def _send_one(bot, chat_id, mtype, content, file_id):
    if mtype == "photo":
        if isinstance(file_id, (bytes, bytearray)):
            bio = io.BytesIO(file_id)
            bio.name = "image.jpg"
            await bot.send_photo(chat_id, bio, caption=content or None, parse_mode="HTML")
        else:
            await bot.send_photo(chat_id, file_id, caption=content or None, parse_mode="HTML")
    elif mtype == "video":
        if isinstance(file_id, (bytes, bytearray)):
            bio = io.BytesIO(file_id)
            bio.name = "video.mp4"
            await bot.send_video(chat_id, bio, caption=content or None, parse_mode="HTML")
        else:
            await bot.send_video(chat_id, file_id, caption=content or None, parse_mode="HTML")
    else:
        await bot.send_message(chat_id, content or "", parse_mode="HTML")


async def _download_media_bytes(bot, file_id: str):
    """دانلود فایل از یک پلتفرم به bytes برای re-upload به پلتفرم دیگر."""
    if not bot or not file_id:
        return None
    try:
        f = await bot.get_file(file_id)
    except Exception:
        try:
            f = bot.get_file(file_id)
        except Exception:
            return None
    try:
        data = await f.download_as_bytearray()
        return bytes(data)
    except Exception:
        try:
            data = f.download_as_bytearray()
            return bytes(data)
        except Exception:
            try:
                buf = io.BytesIO()
                await f.download_to_memory(out=buf)
                return buf.getvalue()
            except Exception:
                return None


def _push_report(rep: dict):
    """
    [ویژگی گم‌شده ۲ — رفع‌شده] ذخیرهٔ گزارش در دیتابیس (ماندگار بعد از ری‌استارت)
    به‌علاوهٔ نگه‌داری در حافظه برای دسترسی سریع.
    [باگ ۲ — رفع‌شده] هر گزارش یک id یکتا از دیتابیس می‌گیرد.
    """
    new_id = add_delivery_report(rep)
    rep["id"] = new_id or (int(time.time() * 1000) % 10 ** 9)
    _DELIVERY_REPORTS.append(rep)
    if len(_DELIVERY_REPORTS) > _MAX_REPORTS:
        del _DELIVERY_REPORTS[:-_MAX_REPORTS]


def _find_report(rep_id: int):
    """[باگ ۲] یافتن گزارش با id یکتا — نه ایندکس لیست."""
    for r in _DELIVERY_REPORTS:
        if int(r.get("id", -1)) == int(rep_id):
            return r
    return None


async def show_delivery_reports(target, is_q=True):
    if not _DELIVERY_REPORTS:
        txt = "📦 گزارش تحویل\n\nهنوز گزارشی ثبت نشده است."
        markup = mkb([back_btn("a_messaging")])
        if is_q:
            await target.edit_message_text(txt, reply_markup=markup)
        else:
            await target.reply_text(txt, reply_markup=markup)
        return
    lines = [f"📦 گزارش تحویل ({fa_num(_MAX_REPORTS)} مورد آخر)", "━━━━━━━━━━━━━━━━"]
    rows = []
    # [باگ ۲ — رفع‌شده] شماره‌گذاری نمایشی از بالا، ولی callback با id یکتا
    total_n = len(_DELIVERY_REPORTS)
    for i, rep in enumerate(reversed(_DELIVERY_REPORTS)):
        num = total_n - i                      # فقط برای نمایش
        rid = int(rep.get("id", 0))            # شناسهٔ پایدار
        tstr = time.strftime("%Y-%m-%d %H:%M", time.localtime(rep.get("ts", 0)))
        ok, bad = fa_num(rep.get("sent", 0)), fa_num(rep.get("failed", 0))
        lines.append(f"#{fa_num(num)} — {tstr} — {rep.get('route_label','')} (✅{ok} ⚠️{bad})")
        rows.append([btn(f"📄 گزارش #{fa_num(num)}", f"bc_rep|{rid}")])
    rows.append(back_btn("a_messaging"))
    txt = "\n".join(lines)
    markup = mkb(rows)
    if is_q:
        await target.edit_message_text(txt, reply_markup=markup)
    else:
        await target.reply_text(txt, reply_markup=markup)


async def show_delivery_report_detail(target, rep_id: int, is_q=True):
    """[باگ ۲ — رفع‌شده] جستجو با id یکتا به‌جای ایندکس لیست."""
    rep = _find_report(rep_id)
    if rep is None:
        txt = "❌ گزارش پیدا نشد یا حذف شده است."
        markup = mkb([back_btn("bc_reports")])
        if is_q:
            await target.edit_message_text(txt, reply_markup=markup)
        else:
            await target.reply_text(txt, reply_markup=markup)
        return
    try:
        num = len(_DELIVERY_REPORTS) - _DELIVERY_REPORTS.index(rep)
    except ValueError:
        num = 1
    tstr = time.strftime("%Y-%m-%d %H:%M", time.localtime(rep.get("ts", 0)))
    lines = [
        f"📦 گزارش #{fa_num(num)}",
        "━━━━━━━━━━━━━━━━",
        f"⏰ زمان: {tstr}",
        f"🧭 مسیر: {rep.get('route_label','')}",
        f"🌐 مقصد: {rep.get('dest_label','')}",
        f"📦 نوع: {rep.get('mtype_fa','')}",
        "",
        f"✅ موفق: {fa_num(rep.get('sent',0))}",
        f"⚠️ ناموفق: {fa_num(rep.get('failed',0))}",
        f"📊 کل: {fa_num(rep.get('total',0))}",
        "",
        "📌 تفکیک پلتفرم‌ها:",
    ]
    for p, s in (rep.get("per_platform") or {}).items():
        lines.append(f"• {platform_name(p)}: ✅ {fa_num(s.get('sent',0))} | ⚠️ {fa_num(s.get('failed',0))} | کل {fa_num(s.get('total',0))}")
    if rep.get("errors"):
        lines.append("")
        lines.append("نمونه خطاها:")
        for e in rep["errors"][:3]:
            lines.append(f"• {e}")
    txt = "\n".join(lines)
    # [باگ ۴ — رفع‌شده] دو دکمه با متن یکسان → متن‌های متمایز
    markup = mkb([
        [btn("⬅️ فهرست گزارش‌ها", "bc_reports")],
        [btn("🏠 مرکز پیام‌رسانی", "a_messaging")],
    ])
    if is_q:
        await target.edit_message_text(txt, reply_markup=markup)
    else:
        await target.reply_text(txt, reply_markup=markup)


def _bulk_targets(route: str, user_mode: str, dest: str):
    plats = _resolve_platforms(dest)
    real = get_route(route, user_mode)
    targets = {}
    if real == "groups":
        for p in plats:
            targets[p] = [cid for (_pl, cid, _title) in group_targets(p)]
        return targets, "گروه/کانال"
    if real == "bots":
        for p in plats:
            targets[p] = _platform_admin_targets(p)
        return targets, "مقصد"
    for p in plats:
        targets[p] = platform_recipients(p)
    return targets, "نفر"


async def do_send(q, ctx):
    bc = ctx.user_data.get("bc")
    if not bc:
        return False, "اطلاعات ارسال یافت نشد."

    mtype = bc.get("type", "text")
    content = _caption(bc)
    file_id = bc.get("file_id")
    chat_id = q.message.chat_id
    route = get_route(bc.get("route", "users"), bc.get("user_mode", "all"))
    origin_platform = (bc.get("origin_platform") or "").strip()
    media_bytes = None

    if route == "direct":
        target_platform = bc.get("target_platform")
        bot = get_platform_bot(target_platform)
        if not bot:
            reset_bc(ctx)
            return False, "⚠️ ربات پلتفرم مقصد فعال نیست."
        try:
            if mtype in ("photo", "video") and file_id and origin_platform and target_platform != origin_platform:
                src_bot = get_platform_bot(origin_platform) or ctx.bot
                media_bytes = await _download_media_bytes(src_bot, file_id)
            await _send_one(bot, bc.get("target_chat_id"), mtype, content, media_bytes or file_id)
            await ctx.bot.send_message(
                chat_id,
                f"✅ پیام به {bc.get('target_display', '')} در {platform_name(target_platform)} ارسال شد.",
                reply_markup=mkb([back_btn("a_messaging")]),
            )
            _push_report({
                "ts": int(time.time()),
                "route": route,
                "route_label": _route_label(bc.get("route", "users"), bc.get("user_mode", "all")),
                "dest": bc.get("dest", ""),
                "dest_label": bc.get("dest_label", ""),
                "mtype": mtype,
                "mtype_fa": _TYPE_FA.get(mtype, mtype),
                "sent": 1,
                "failed": 0,
                "total": 1,
                "per_platform": {target_platform: {"sent": 1, "failed": 0, "total": 1}},
                "errors": [],
            })
            reset_bc(ctx)
            return True, ""
        except Exception as e:
            logger.error(f"bc direct send error: {e}")
            _push_report({
                "ts": int(time.time()),
                "route": route,
                "route_label": _route_label(bc.get("route", "users"), bc.get("user_mode", "all")),
                "dest": bc.get("dest", ""),
                "dest_label": bc.get("dest_label", ""),
                "mtype": mtype,
                "mtype_fa": _TYPE_FA.get(mtype, mtype),
                "sent": 0,
                "failed": 1,
                "total": 1,
                "per_platform": {target_platform: {"sent": 0, "failed": 1, "total": 1}},
                "errors": [str(e)],
            })
            reset_bc(ctx)
            return False, "❌ ارسال ناموفق بود. احتمالاً کاربر ربات را استارت نکرده یا آن را بلاک کرده است."

    targets, unit = _bulk_targets(bc.get("route", "users"), bc.get("user_mode", "all"), bc.get("dest", "all"))
    total = sum(len(v) for v in targets.values())
    if total == 0:
        reset_bc(ctx)
        if route == "groups":
            return False, (
                "⚠️ هیچ گروه/کانالی ثبت نشده است.\n\n"
                "📋 برای ثبت یک گروه/کانال:\n"
                "۱️⃣ ربات را به گروه/کانال اضافه کنید\n"
                "۲️⃣ ربات را **ادمین** کنید (با دسترسی ارسال پیام)\n"
                "۳️⃣ در گروه یک پیام بفرستید یا /start بزنید\n\n"
                "پس از این، گروه در فهرست مقاصد ظاهر می‌شود."
            )
        if route == "bots":
            return False, "⚠️ هیچ مقصد فعالی برای مسیر ربات‌های هر پلتفرم ثبت نشده است (ادمین آن پلتفرم ثبت نشده)."
        return False, "⚠️ هیچ مخاطبی برای ارسال وجود ندارد."

    # برای ارسال عکس/ویدیو به چند پلتفرم: file_id بین پلتفرم‌ها مشترک نیست → دانلود و re-upload
    if mtype in ("photo", "video") and file_id and origin_platform:
        needs_reupload = any((p != origin_platform) and ids for p, ids in targets.items())
        if needs_reupload:
            src_bot = get_platform_bot(origin_platform) or ctx.bot
            media_bytes = await _download_media_bytes(src_bot, file_id)

    _delay = get_send_delay()
    progress = await ctx.bot.send_message(chat_id, f"⏳ شروع ارسال… (۰ از {fa_num(total)})")
    sent = 0
    failed = 0
    done = 0
    per_platform = {p: {"sent": 0, "failed": 0, "total": len(ids)} for p, ids in targets.items()}
    errors = []

    for p, ids in targets.items():
        bot = get_platform_bot(p)
        if not bot:
            failed += len(ids)
            done += len(ids)
            per_platform[p]["failed"] += len(ids)
            continue
        for cid in ids:
            try:
                media = file_id
                if mtype in ("photo", "video") and file_id and origin_platform and p != origin_platform:
                    if media_bytes:
                        media = media_bytes
                    else:
                        raise RuntimeError("media_reupload_failed")
                await _send_one(bot, cid, mtype, content, media)
                sent += 1
                per_platform[p]["sent"] += 1
            except Exception as e:
                failed += 1
                per_platform[p]["failed"] += 1
                logger.warning("bc skip %s:%s -> %s", p, cid, e)
                if len(errors) < 3:
                    errors.append(f"{platform_name(p)}:{cid} → {_explain_send_error(e)}")
            done += 1
            if done % 20 == 0:
                try:
                    await ctx.bot.edit_message_text(
                        f"⏳ در حال ارسال… ({fa_num(sent)} از {fa_num(total)})",
                        chat_id=chat_id,
                        message_id=progress.message_id,
                    )
                except Exception:
                    pass
            await asyncio.sleep(_delay)

    await ctx.bot.send_message(
        chat_id,
        f"✅ ارسال تمام شد.\n\n📤 موفق: {fa_num(sent)}\n⚠️ ناموفق/رد: {fa_num(failed)}\n📊 کل: {fa_num(total)} {unit}",
        reply_markup=mkb([back_btn("a_messaging")]),
    )
    _push_report({
        "ts": int(time.time()),
        "route": route,
        "route_label": _route_label(bc.get("route", "users"), bc.get("user_mode", "all")),
        "dest": bc.get("dest", ""),
        "dest_label": bc.get("dest_label", ""),
        "mtype": mtype,
        "mtype_fa": _TYPE_FA.get(mtype, mtype),
        "sent": sent,
        "failed": failed,
        "total": total,
        "per_platform": per_platform,
        "errors": errors,
    })
    reset_bc(ctx)
    return True, ""


def resolve_direct_target_strict(query: str, dest: str = "all"):
    q = (query or "").strip().lstrip("@").lower()
    if not q:
        return None, "empty"

    plats = _resolve_platforms(dest)
    if not plats:
        return None, "platform_inactive"

    candidates = []
    seen = set()

    def _add(platform, chat_id, display):
        key = (platform, str(chat_id))
        if key in seen:
            return
        seen.add(key)
        candidates.append((platform, chat_id, display))

    if q.isdigit():
        qid = int(q)
        if "bale" in plats and str(qid) in USERS:
            u = USERS[str(qid)]
            if qid not in ADMIN_IDS:
                _add("bale", qid, u.get("first_name") or str(qid))

        for link in PLATFORM_LINKS.values():
            lp = link.get("platform")
            if lp not in plats:
                continue
            owner = USERS.get(str(link.get("user_id"))) or {}
            if str(link.get("platform_user_id")) == str(qid):
                _add(lp, int(link.get("platform_user_id")), owner.get("first_name") or str(qid))
            elif str(link.get("user_id")) == str(qid):
                try:
                    _add(lp, int(link.get("platform_user_id")), owner.get("first_name") or str(qid))
                except Exception:
                    pass
    else:
        for uid_str, u in USERS.items():
            if int(u.get("id", uid_str)) in ADMIN_IDS:
                continue
            if (u.get("username") or "").strip().lower() != q:
                continue
            canonical_id = int(u.get("id", uid_str))
            if "bale" in plats:
                _add("bale", canonical_id, u.get("first_name") or q)
            for link in PLATFORM_LINKS.values():
                if str(link.get("user_id")) != str(canonical_id):
                    continue
                lp = link.get("platform")
                if lp not in plats:
                    continue
                try:
                    _add(lp, int(link.get("platform_user_id")), u.get("first_name") or q)
                except Exception:
                    pass

    if not candidates:
        return None, "not_found"
    if len(candidates) > 1:
        return candidates, "ambiguous"
    return candidates[0], "ok"


async def show_delay_menu(target, is_q=True):
    """[ویژگی گم‌شده ۱] منوی تنظیم تأخیر ارسال."""
    cur = get_send_delay()
    text = (
        "⏱ تأخیر بین ارسال‌ها\n"
        "━━━━━━━━━━━━━━━━\n\n"
        f"مقدار فعلی: {cur:g} ثانیه\n\n"
        "این تأخیر بین ارسال هر پیام رعایت می‌شود تا ربات\n"
        "به‌خاطر فلاد محدود یا بلاک نشود.\n\n"
        "• کمتر → سریع‌تر ولی ریسک بیشتر\n"
        "• بیشتر → کندتر ولی امن‌تر\n\n"
        f"محدودهٔ مجاز: {BC_DELAY_MIN:g} تا {BC_DELAY_MAX:g} ثانیه"
    )
    presets = [0.1, 0.5, 1.0, 2.0, 3.0, 5.0]
    rows, row = [], []
    for v in presets:
        mark = " ✅" if abs(v - cur) < 0.001 else ""
        row.append(btn(f"{v:g}s{mark}", f"bc_delay_set|{v}"))
        if len(row) == 3:
            rows.append(row); row = []
    if row:
        rows.append(row)
    rows.append([btn("✏️ مقدار دلخواه", "bc_delay_custom")])
    rows.append(back_btn("a_messaging"))
    markup = mkb(rows)
    if is_q:
        await target.edit_message_text(text, reply_markup=markup)
    else:
        await target.reply_text(text, reply_markup=markup)


def platform_user_entries(dest: str, limit: int = 0) -> list:
    """
    [کار ۴-۱] فهرست کاربرانِ قابل‌ارسال در یک پلتفرم.
    خروجی: [(platform, chat_id, display)] — بدون ادمین‌ها.
    """
    plats = _resolve_platforms(dest)
    out, seen = [], set()

    def _add(p, cid, name):
        key = (p, str(cid))
        if key in seen:
            return
        seen.add(key)
        out.append((p, cid, name or str(cid)))

    for p in plats:
        if p == "bale":
            for uid in platform_recipients("bale"):
                u = USERS.get(str(uid)) or {}
                _add("bale", uid, u.get("first_name"))
        else:
            for link in PLATFORM_LINKS.values():
                if link.get("platform") != p:
                    continue
                try:
                    owner = int(link.get("user_id") or 0)
                except (TypeError, ValueError):
                    continue
                if owner in ADMIN_IDS:
                    continue
                u = USERS.get(str(owner)) or {}
                if not (u.get("phone") or "").strip():
                    continue
                pid = link.get("platform_user_id")
                if pid in (None, ""):
                    continue
                _add(p, pid, u.get("first_name"))

    out.sort(key=lambda x: str(x[2]))
    return out[:limit] if limit else out


async def show_bc_user_list(target, dest: str, page: int = 0, is_q=True):
    """
    [کار ۴-۱] نمایش صفحه‌بندی‌شدهٔ کاربرانِ پلتفرم انتخاب‌شده.
    ادمین می‌تواند مستقیم روی نام کاربر بزند یا آی‌دی/یوزرنیم تایپ کند.
    """
    entries = platform_user_entries(dest)
    dest_label = "همه پلتفرم‌ها" if dest == "all" else platform_name(dest)
    per = 10
    total_pages = max(1, (len(entries) + per - 1) // per)
    page = max(0, min(page, total_pages - 1))
    chunk = entries[page * per:(page + 1) * per]

    if not entries:
        text = (
            f"✉️ ارسال به کاربر مشخص — {dest_label}\n"
            "━━━━━━━━━━━━━━━━\n\n"
            "هیچ کاربری در این پلتفرم پیدا نشد.\n"
            "(کاربر باید ربات را استارت کرده و شماره ثبت کرده باشد)\n\n"
            "می‌توانید آی‌دی عددی یا یوزرنیم را دستی بفرستید:"
        )
        markup = mkb([back_btn("a_messaging")])
    else:
        text = (
            f"✉️ ارسال به کاربر مشخص — {dest_label}\n"
            "━━━━━━━━━━━━━━━━\n"
            f"👥 {fa_num(len(entries))} کاربر | صفحهٔ {fa_num(page + 1)} از {fa_num(total_pages)}\n\n"
            "روی نام کاربر بزنید، یا آی‌دی عددی/یوزرنیم را بفرستید:"
        )
        rows = []
        # اندیس سراسری تا انتخاب بین صفحات درست بماند
        for i, (p, cid, disp) in enumerate(chunk):
            gi = page * per + i
            tag = "" if dest != "all" else f" ({platform_name(p)})"
            rows.append([btn(f"👤 {disp}{tag}", f"bc_upick|{dest}|{gi}")])
        nav = []
        if page > 0:
            nav.append(btn("⬅️ قبلی", f"bc_ulist|{dest}|{page - 1}"))
        if page < total_pages - 1:
            nav.append(btn("بعدی ➡️", f"bc_ulist|{dest}|{page + 1}"))
        if nav:
            rows.append(nav)
        rows.append(back_btn("a_messaging"))
        markup = mkb(rows)

    if is_q:
        await target.edit_message_text(text, reply_markup=markup)
    else:
        await target.reply_text(text, reply_markup=markup)
