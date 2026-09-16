"""
platform_runtime.py — کنترل زندهٔ اتصال پلتفرم تلگرام (کار ۲)

وابستگی مجاز: config و stdlib + telegram
هرگز از core / ui / handlers import نکنید (زنجیره import را نشکنید).

این ماژول اجازه می‌دهد ادمین از پنل مدیریت، تلگرام را در همان لحظه
فعال یا غیرفعال کند — بدون نیاز به ری‌استارت ربات.
"""
import logging

from config import (
    SETTINGS, save, register_platform_bot, unregister_platform_bot,
)

logger = logging.getLogger(__name__)

# اپ زندهٔ تلگرام (اگر در حال اجرا باشد) — توسط bot.py و همین ماژول ست می‌شود
_STATE = {"app": None, "proxy": None, "builder": None}


def set_app_builder(fn):
    """
    ثبت تابع سازندهٔ اپ تلگرام (از bot.py).
    امضا: async fn() -> (app | None, proxy | None)
    این کار وابستگی معکوس به bot.py را حذف می‌کند.
    """
    _STATE["builder"] = fn


def set_telegram_app(app, proxy=None):
    """ثبت اپ زندهٔ تلگرام پس از راه‌اندازی موفق در bot.py."""
    _STATE["app"] = app
    _STATE["proxy"] = proxy


def get_telegram_app():
    return _STATE.get("app")


def mask_proxy(proxy) -> str:
    """نمایش امن پروکسی (رمز عبور پنهان)."""
    if not proxy:
        return "بدون پروکسی"
    try:
        if "@" in proxy:
            scheme, rest = proxy.split("://", 1)
            _creds, host = rest.rsplit("@", 1)
            return f"{scheme}://***:***@{host}"
    except Exception:
        pass
    return proxy


def current_proxy_label() -> str:
    """[افزوده] نمایش پروکسی فعالِ اتصال جاری (برای پنل ادمین)."""
    if not is_telegram_running():
        return "—"
    p = _STATE.get("proxy")
    return mask_proxy(p) if p else "بدون پروکسی (مستقیم)"


def is_telegram_running() -> bool:
    """آیا اپ تلگرام واقعاً در حال polling است؟ (وضعیت واقعی، نه تنظیمات)"""
    app = _STATE.get("app")
    if app is None:
        return False
    try:
        return bool(app.updater and app.updater.running)
    except Exception:
        return False


def telegram_status() -> dict:
    """
    [کار ۲ — بند ۶] بررسی وضعیت واقعی اتصال تلگرام.

    خروجی:
      enabled    : تنظیم ادمین (چیزی که در دیتابیس ذخیره شده)
      running    : وضعیت واقعی اجرا (آیا الان polling می‌کند؟)
      configured : آیا توکن ثبت شده؟
      proxy      : پروکسی فعال (masked)
      synced     : آیا تنظیم و واقعیت هم‌خوان‌اند؟
    """
    enabled = str(SETTINGS.get("telegram_enabled", 0)) in ("1", "True", "true")
    token = (SETTINGS.get("telegram_token") or "").strip()
    running = is_telegram_running()
    return {
        "enabled": enabled,
        "running": running,
        "configured": bool(token),
        "proxy": mask_proxy(_STATE.get("proxy")) if running else "-",
        "synced": (enabled and running) or (not enabled and not running),
    }


def status_text() -> str:
    """متن فارسی خوانا از وضعیت تلگرام — برای نمایش در پنل ادمین."""
    st = telegram_status()
    lines = [
        f"تنظیم ادمین: {'🟢 فعال' if st['enabled'] else '🔴 غیرفعال'}",
        f"وضعیت واقعی: {'🟢 متصل و در حال کار' if st['running'] else '⚫️ متصل نیست'}",
        f"توکن: {'✅ ثبت‌شده' if st['configured'] else '❌ ثبت‌نشده'}",
    ]
    if st["running"]:
        lines.append(f"پروکسی: {st['proxy']}")
    if not st["synced"]:
        if st["enabled"] and not st["running"]:
            lines.append("⚠️ فعال است ولی متصل نیست (اتصال ناموفق یا نیاز به ری‌استارت)")
        else:
            lines.append("⚠️ غیرفعال است ولی هنوز در حال اجراست")
    return "\n".join(lines)


async def stop_telegram() -> tuple:
    """
    [کار ۲ — بند ۴] توقف واقعی اتصال تلگرام.
    خروجی: (ok: bool, message: str)
    """
    app = _STATE.get("app")
    if app is None:
        return True, "تلگرام از قبل متصل نبود."

    try:
        try:
            if app.updater and app.updater.running:
                await app.updater.stop()
        except Exception as e:
            logger.debug(f"updater.stop: {e}")
        try:
            if app.running:
                await app.stop()
        except Exception as e:
            logger.debug(f"app.stop: {e}")
        try:
            await app.shutdown()
        except Exception as e:
            logger.debug(f"app.shutdown: {e}")

        _STATE["app"] = None
        _STATE["proxy"] = None
        unregister_platform_bot("telegram")
        logger.info("📴 تلگرام غیرفعال شد.")
        return True, "📴 تلگرام غیرفعال شد و اتصال قطع گردید."
    except Exception as e:
        logger.error(f"خطا هنگام توقف تلگرام: {e}")
        return False, f"خطا هنگام قطع اتصال تلگرام: {e}"


async def start_telegram() -> tuple:
    """
    [کار ۲ — بند ۵] برقراری واقعی اتصال تلگرام (با پروکسی و retry).
    خروجی: (ok: bool, message: str)
    """
    if is_telegram_running():
        return True, "✅ تلگرام از قبل فعال و متصل است."

    token = (SETTINGS.get("telegram_token") or "").strip()
    if not token:
        return False, "❌ ابتدا توکن تلگرام را ثبت کنید."

    builder = _STATE.get("builder")
    if builder is None:
        return False, (
            "⚠️ کنترل زنده در دسترس نیست. پس از ری‌استارت ربات، "
            "تلگرام طبق تنظیمات فعلی راه‌اندازی می‌شود."
        )

    # اگر اپ قدیمی نیمه‌فعال مانده، اول تمیزش کن
    if _STATE.get("app") is not None:
        await stop_telegram()

    try:
        app, proxy = await builder()
    except Exception as e:
        logger.error(f"خطای غیرمنتظره هنگام ساخت اپ تلگرام: {e}")
        return False, f"❌ خطا هنگام اتصال: {type(e).__name__}"

    if app is None:
        return False, (
            "⚠️ اتصال به تلگرام ممکن نشد.\n"
            "علت معمول: نبود دسترسی به api.telegram.org\n\n"
            "راه‌حل: در فایل .env یک پروکسی تنظیم کنید:\n"
            "TELEGRAM_PROXY=http://host:port\n"
            "یا VPN را روشن کنید."
        )

    try:
        await app.start()
        await app.updater.start_polling(drop_pending_updates=True)
    except Exception as e:
        logger.error(f"خطا هنگام شروع polling تلگرام: {e}")
        try:
            await app.shutdown()
        except Exception:
            pass
        return False, f"❌ اتصال برقرار شد ولی دریافت پیام شروع نشد: {e}"

    _STATE["app"] = app
    _STATE["proxy"] = proxy
    register_platform_bot("telegram", app.bot)
    logger.info("✅ تلگرام فعال شد. (%s)", mask_proxy(proxy))
    return True, f"✅ تلگرام فعال شد و متصل است.\n🔌 {mask_proxy(proxy)}"


async def apply_telegram_enabled(enabled: bool) -> tuple:
    """
    [کار ۲ — بند ۳] ذخیرهٔ وضعیت در دیتابیس + اعمال واقعی آن.
    وضعیت در جدول settings کلید telegram_enabled ذخیره می‌شود،
    پس بعد از ری‌استارت هم حفظ می‌ماند.
    """
    SETTINGS["telegram_enabled"] = 1 if enabled else 0
    save("settings")  # ← ماندگاری بعد از ری‌استارت

    if enabled:
        return await start_telegram()
    return await stop_telegram()


async def reload_telegram() -> tuple:
    """اعمال توکن جدید: قطع اتصال فعلی و اتصال دوباره با توکن تازه."""
    was_enabled = str(SETTINGS.get("telegram_enabled", 0)) in ("1", "True", "true")
    await stop_telegram()
    if not was_enabled:
        return True, "توکن ذخیره شد. (تلگرام غیرفعال است)"
    return await start_telegram()
