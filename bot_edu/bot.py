"""
bot.py — نقطه ورود ربات

راه‌اندازی Application بله (همیشه فعال) و در صورت فعال بودن، اپ تلگرام.
تلگرام کاملاً ایزوله است: هر خطایی در آن فقط تلگرام را غیرفعال می‌کند
و هرگز باعث توقف ربات بله نمی‌شود.
"""
import asyncio
import atexit
import logging
import os

# بارگذاری خودکار از فایل .env اگر وجود داشت
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # اگر python-dotenv نصب نبود، از env سیستم استفاده می‌شود

from telegram import Update
from telegram.ext import (
    ApplicationBuilder, CommandHandler, CallbackQueryHandler,
    MessageHandler, filters,
)

from db import init_db
from config import (
    TOKEN, DB_PATH, SETTINGS, set_app_bot, setup_data, register_platform_bot,
    TELEGRAM_CONNECT_RETRIES, telegram_proxy_candidates,
)
from handlers import (
    start, button_handler, handle_text, handle_media, handle_new_member,
    handle_contact,
)
import platform_runtime

logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    level=logging.INFO,
)
# PTB/httpx در سطح INFO آدرس کامل API بله را همراه توکن چاپ می‌کند.
# این namespaceها را مستقل از logger اصلی محدود می‌کنیم تا هیچ Secret در log نیاید.
for _noisy_logger in ("httpx", "httpcore", "telegram.request"):
    logging.getLogger(_noisy_logger).setLevel(logging.WARNING)

logger = logging.getLogger(__name__)


def _on_edubot_shutdown():
    """هنگام بسته شدن ربات اصلی، checkpoint بزن (WAL → DB)."""
    try:
        from db import checkpoint_db, DB_PATH
    except Exception:
        checkpoint_db, DB_PATH = None, None
    try:
        logger.info("ربات اصلی در حال بسته شدن... checkpoint...")
        if checkpoint_db:
            checkpoint_db(DB_PATH)
            giso_db = os.path.join(
                os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                "giso", "data", "giso.db",
            )
            if os.path.exists(giso_db):
                checkpoint_db(giso_db)
        logger.info("checkpoint انجام شد. ربات بسته شد.")
    except Exception as e:
        logger.debug(f"_on_edubot_shutdown: {e}")


atexit.register(_on_edubot_shutdown)


async def _periodic_checkpoint_edubot(context):
    """checkpoint خودکار هر ۵ دقیقه برای bot.db و giso.db."""
    # checkpoint bot.db
    try:
        from db import checkpoint_bot_db
        checkpoint_bot_db()
    except Exception as e:
        logger.error(f"edubot periodic checkpoint (bot.db) error: {e}")

    # checkpoint giso.db (اگر وجود داشته باشد)
    try:
        import sqlite3
        giso_db = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "giso", "data", "giso.db",
        )
        if os.path.exists(giso_db):
            conn = sqlite3.connect(giso_db)
            try:
                conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
            finally:
                conn.close()
    except Exception as e:
        logger.error(f"edubot periodic checkpoint (giso.db) error: {e}")


def _init_periodic_checkpoint_edubot(app):
    """ثبت job checkpoint خودکار هر ۵ دقیقه برای bot.db و giso.db."""
    try:
        if app is not None and hasattr(app, "job_queue") and app.job_queue is not None:
            app.job_queue.run_repeating(
                _periodic_checkpoint_edubot,
                interval=300,   # هر ۵ دقیقه
                first=60,       # اولین اجرا بعد از ۱ دقیقه
                name='edubot_periodic_checkpoint',
            )
            logger.info("periodic checkpoint (bot.db + giso.db) هر ۵ دقیقه فعال شد")
    except Exception as e:
        logger.error(f"_init_periodic_checkpoint_edubot: {e}")


def _register_handlers(app):
    """ثبت تمام handler‌ها روی یک Application (مشترک بین همه پلتفرم‌ها)."""
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler(
        "myid",
        lambda u, c: u.message.reply_text(f"🆔 شناسه شما:\n{u.effective_user.id}"),
    ))
    app.add_handler(CallbackQueryHandler(button_handler), group=1)
    app.add_handler(MessageHandler(filters.CONTACT, handle_contact), group=2)
    app.add_handler(MessageHandler(
        filters.PHOTO | filters.VIDEO | filters.Document.ALL,
        handle_media,
    ), group=2)
    app.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND,
        handle_text,
    ), group=3)
    app.add_handler(MessageHandler(
        filters.StatusUpdate.NEW_CHAT_MEMBERS,
        handle_new_member,
    ), group=4)


def _build_bale_app():
    app = (
        ApplicationBuilder()
        .token(TOKEN)
        .base_url("https://tapi.bale.ai/bot")
        .base_file_url("https://tapi.bale.ai/file/bot")
        .build()
    )
    _register_handlers(app)
    return app


def _mask_proxy(proxy) -> str:
    """نمایش امن پروکسی در لاگ (رمز عبور پنهان می‌شود)."""
    if not proxy:
        return "بدون پروکسی (اتصال مستقیم)"
    try:
        if "@" in proxy:
            scheme, rest = proxy.split("://", 1)
            _creds, host = rest.rsplit("@", 1)
            return f"{scheme}://***:***@{host}"
    except Exception:
        pass
    return proxy


def _build_telegram_app_with_proxy(token: str, proxy):
    """ساخت Application تلگرام با پروکسی مشخص (یا بدون پروکسی اگر None باشد)."""
    builder = ApplicationBuilder().token(token)
    if proxy:
        # هم درخواست‌های عادی و هم get_updates باید از پروکسی عبور کنند
        builder = builder.proxy(proxy).get_updates_proxy(proxy)
    builder = (
        builder
        .connect_timeout(20.0)
        .read_timeout(20.0)
        .write_timeout(20.0)
        .get_updates_connect_timeout(20.0)
        .get_updates_read_timeout(20.0)
    )
    app = builder.build()
    _register_handlers(app)
    return app


async def _verify_telegram(app) -> str:
    """
    تست واقعی اتصال با فراخوانی get_me.
    خروجی: نام کاربری ربات. در صورت خطا استثنا پرتاب می‌کند.
    """
    await app.initialize()
    me = await app.bot.get_me()
    return me.username or str(me.id)


async def _shutdown_quietly(app):
    """خاموش‌کردن بی‌سروصدای یک Application نیمه‌راه‌اندازی‌شده."""
    try:
        await app.shutdown()
    except Exception:
        pass


def _collect_proxy_candidates() -> list:
    """
    [افزوده] ترکیب گزینه‌های پروکسی از proxy_manager (حالت اتصال) و .env.

    اگر حالت «مستقیم» باشد، فقط اتصال مستقیم برگردانده می‌شود.
    در غیر این صورت پروکسی‌های .env هم به‌عنوان پشتیبان اضافه می‌شوند.
    """
    try:
        import proxy_manager as pm
        base = pm.candidates_for_mode()
        mode = pm.get_mode()
    except Exception as e:
        logger.warning("proxy_manager در دسترس نیست (%s) — بازگشت به .env", e)
        return telegram_proxy_candidates()

    if mode == pm.MODE_DIRECT:
        return [None]

    out = [p for p in base if p is not None]
    for p in telegram_proxy_candidates():   # پروکسی‌های .env به‌عنوان پشتیبان
        if p is not None and p not in out:
            out.append(p)
    out.append(None)                        # آخرین تلاش: مستقیم
    return out


async def _try_build_telegram_app():
    """
    [کار ۱] ساخت اپ تلگرام با تلاش روی چند پروکسی و چند بار retry.

    ترتیب تلاش بر اساس «حالت اتصال» انتخاب‌شده در پنل (proxy_manager):
      • 🟢 خودکار → پروکسی‌های دستی، سپس لیست سالم، سپس .env، سپس مستقیم
      • 🟡 دستی   → فقط پروکسی‌های دستی، سپس مستقیم
      • 🔴 مستقیم → فقط اتصال مستقیم

    برای هر گزینه حداکثر TELEGRAM_CONNECT_RETRIES بار تلاش می‌شود.

    خروجی: (app, proxy) در صورت موفقیت — یا (None, None) در صورت شکست کامل.
    هرگز استثنا پرتاب نمی‌کند؛ شکست تلگرام نباید کل ربات را متوقف کند.
    """
    token = (SETTINGS.get("telegram_token") or "").strip()
    enabled = str(SETTINGS.get("telegram_enabled", 0)) in ("1", "True", "true")

    if not token:
        logger.info("📴 تلگرام: توکن ثبت نشده — غیرفعال می‌ماند.")
        return None, None
    if not enabled:
        logger.info("📴 تلگرام: در پنل مدیریت غیرفعال است — راه‌اندازی نمی‌شود.")
        return None, None

    candidates = _collect_proxy_candidates()
    mode_txt = ""
    try:
        import proxy_manager as pm
        mode_txt = f" — حالت: {pm.mode_label()}"
    except Exception:
        pass
    logger.info("🔌 تلاش برای اتصال به تلگرام (%d گزینه)%s", len(candidates), mode_txt)

    for proxy in candidates:
        label = _mask_proxy(proxy)
        for attempt in range(1, TELEGRAM_CONNECT_RETRIES + 1):
            app = None
            try:
                app = _build_telegram_app_with_proxy(token, proxy)
                uname = await _verify_telegram(app)
                if proxy:
                    logger.info("✅ تلگرام با پروکسی متصل شد → @%s (%s)", uname, label)
                else:
                    logger.info("✅ تلگرام بدون پروکسی متصل شد → @%s", uname)
                return app, proxy
            except Exception as e:
                if app is not None:
                    await _shutdown_quietly(app)
                logger.warning(
                    "   ↻ تلاش %d/%d با «%s» ناموفق: %s",
                    attempt, TELEGRAM_CONNECT_RETRIES, label,
                    type(e).__name__ + ": " + str(e)[:120],
                )
                if attempt < TELEGRAM_CONNECT_RETRIES:
                    await asyncio.sleep(2)

    logger.error(
        "⚠️ اتصال به تلگرام ممکن نشد — تلگرام غیرفعال شد (ربات بله سالم ادامه می‌دهد).\n"
        "   راه‌حل‌ها:\n"
        "     • یک پروکسی در .env تنظیم کنید:  TELEGRAM_PROXY=http://host:port\n"
        "     • یا چند پروکسی:                 TELEGRAM_PROXY_LIST=http://a:1,http://b:2\n"
        "     • یا VPN را روشن کنید\n"
        "     • یا از پنل مدیریت، تلگرام را غیرفعال کنید تا این پیام دیگر نیاید."
    )
    return None, None


async def _start_polling(app, name: str, already_initialized: bool = False) -> bool:
    """
    راه‌اندازی polling یک Application با محافظت کامل.
    خروجی: True اگر موفق بود، False اگر شکست خورد (بدون پرتاب استثنا).
    """
    try:
        if not already_initialized:
            await app.initialize()
        await app.start()
        await app.updater.start_polling(
            allowed_updates=Update.ALL_TYPES, drop_pending_updates=True
        )
        return True
    except Exception as e:
        logger.error("❌ راه‌اندازی polling %s ناموفق بود: %s", name, e)
        await _shutdown_quietly(app)
        return False


async def _stop_app(app, name: str):
    """خاموش‌کردن امن یک Application (هر مرحله جدا محافظت شده)."""
    for step, fn in (
        ("updater.stop", lambda: app.updater.stop()),
        ("stop", lambda: app.stop()),
        ("shutdown", lambda: app.shutdown()),
    ):
        try:
            if step == "updater.stop" and not app.updater.running:
                continue
            await fn()
        except Exception as e:
            logger.debug("خطای جزئی هنگام %s برای %s: %s", step, name, e)


async def _run_all():
    """
    [کار ۱] اجرای همزمان بله (همیشه) و تلگرام (در صورت امکان).

    قانون طلایی: بله همیشه مستقل و پایدار است. هر خطایی در تلگرام
    فقط تلگرام را غیرفعال می‌کند و هرگز کل ربات را متوقف نمی‌کند.
    """
    # کنترل زنده: به ماژول runtime یاد بده چطور اپ تلگرام بسازد (کار ۲)
    platform_runtime.set_app_builder(_try_build_telegram_app)

    # ── بله: پلتفرم پایه و همیشه فعال ──
    bale_app = _build_bale_app()
    set_app_bot(bale_app.bot)
    register_platform_bot("bale", bale_app.bot)

    if not await _start_polling(bale_app, "بله"):
        logger.critical(
            "❌ راه‌اندازی ربات بله ناموفق بود.\n"
            "   موارد زیر را بررسی کنید:\n"
            "     • مقدار BOT_TOKEN در فایل .env درست و معتبر است؟\n"
            "     • اتصال اینترنت برقرار است؟ (tapi.bale.ai در دسترس باشد)\n"
            "     • توکن از @BotFather بله گرفته شده (نه تلگرام)؟"
        )
        return
    logger.info("✅ ربات بله روشن شد!")

    # ═══ شروع backup خودکار edu bot (اگر تنظیم شده) ═══
    try:
        from handlers import _init_edubot_auto_backup
        _init_edubot_auto_backup(bale_app)
    except Exception as _ib:
        logger.warning(f"init edubot auto backup: {_ib}")

    # ═══ checkpoint خودکار هر ۵ دقیقه (bot.db + giso.db) ═══
    try:
        _init_periodic_checkpoint_edubot(bale_app)
    except Exception as _pc:
        logger.warning(f"init periodic checkpoint edubot: {_pc}")

    running = [(bale_app, "بله")]

    # ── تلگرام: اختیاری، با پروکسی و retry، کاملاً ایزوله ──
    try:
        tg_app, tg_proxy = await _try_build_telegram_app()
    except Exception as e:  # حتی خطای غیرمنتظره هم نباید بله را متوقف کند
        logger.error("⚠️ خطای غیرمنتظره هنگام آماده‌سازی تلگرام: %s", e)
        tg_app, tg_proxy = None, None

    if tg_app is not None:
        # اپ در _try_build_telegram_app قبلاً initialize شده است
        if await _start_polling(tg_app, "تلگرام", already_initialized=True):
            register_platform_bot("telegram", tg_app.bot)
            running.append((tg_app, "تلگرام"))
            platform_runtime.set_telegram_app(tg_app, tg_proxy)
            logger.info("📲 تلگرام فعال شد.")
        else:
            logger.warning("⚠️ تلگرام راه‌اندازی نشد — ربات فقط با بله ادامه می‌دهد.")

    logger.info("🚀 ربات آماده است — پلتفرم‌های فعال: %s",
                "، ".join(n for _, n in running))

    try:
        await asyncio.Event().wait()
    except (KeyboardInterrupt, asyncio.CancelledError):
        logger.info("⏹ درخواست توقف دریافت شد…")
    finally:
        live_tg = platform_runtime.get_telegram_app()
        if live_tg is not None and all(live_tg is not a for a, _ in running):
            await _stop_app(live_tg, "تلگرام")
        for app, name in running:
            await _stop_app(app, name)
        logger.info("👋 ربات خاموش شد.")


def main():
    # ۰. بررسی وجود توکن — بدون آن ادامه بی‌معنی است
    if not TOKEN:
        logger.error(
            "❌ توکن ربات پیدا نشد.\n"
            "   یک فایل .env کنار bot.py بسازید و در آن بنویسید:\n"
            "       BOT_TOKEN=توکن_کامل_شما\n"
            "   می‌توانید از روی فایل نمونه بسازید:  cp .env.example .env"
        )
        raise SystemExit(1)

    # ═══ بازیابی خودکار دیتابیس (قبل از هر چیز) ═══
    try:
        from db import auto_restore_bot_db, auto_restore_giso_db
        restored_bot = auto_restore_bot_db()
        restored_giso = auto_restore_giso_db()
        if restored_bot:
            logger.info("🔄 bot.db از backup بازیابی شد")
        if restored_giso:
            logger.info("🔄 giso.db از backup بازیابی شد")
    except Exception as _ar:
        logger.warning(f"بازیابی خودکار دیتابیس ناموفق: {_ar}")

    # ۱. راه‌اندازی دیتابیس SQLite (ساخت جدول‌ها + PRAGMA)
    init_db(DB_PATH)

    # ۲. بارگذاری همه داده‌ها از SQLite به حافظه
    setup_data()

    # ۳. اجرای همزمان بله (همیشه) و تلگرام (در صورت فعال بودن و امکان اتصال)
    try:
        asyncio.run(_run_all())
    except KeyboardInterrupt:
        logger.info("👋 خروج با Ctrl+C.")


if __name__ == "__main__":
    main()
# Phase 10 Bale Bot overall
# Phase 10.5 Bale End-to-End Test needed
