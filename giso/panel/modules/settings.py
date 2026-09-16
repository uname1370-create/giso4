# -*- coding: utf-8 -*-
"""panel/modules/settings.py — تنظیمات سایت و ربات (فقط سوپرادمین) — فاز 4.3 + فاز 5.

فاز 5:
  - تایمر خروج پنل با نقش‌های جدا (ادمین/کاربر) + فعال/غیرفعال + دقیقه + انتخاب نقش
  - تم سایت (مسیر هوشمند/ساده طلایی/کلاسیک/ارزش مو/سلامت هوشمند)
  - آدرس سایت گیسو (تنظیم + تست) — همان کلید giso_config.site_base_url ربات
  - همه مقادیر در giso_config (همان کلیدهای ربات) ذخیره می‌شوند
"""
import logging
import os
import re

from flask import request, redirect, url_for, flash

from giso.panel.permissions import current_role_and_perms

logger = logging.getLogger("giso_panel_settings")

KEYS = {
    "idle_minutes": "panel_idle_minutes",
    "idle_enabled": "panel_idle_enabled",
    "idle_role": "panel_idle_role",
    "idle_minutes_admin": "panel_idle_minutes_admin",
    "idle_minutes_user": "panel_idle_minutes_user",
    "registration_enabled": "site_registration_enabled",
    "extra_sections": "panel_extra_sections",
    "site_theme": "site_theme",
    "site_base_url": "site_base_url",
    "brand_name": "site_brand_name",
    "brand_tagline": "site_brand_tagline",
    "logo_path": "site_logo_path",
    "hero_image_path": "site_hero_image_path",
    "counter_offset_users": "counter_offset_users",
    "counter_offset_analyses": "counter_offset_analyses",
    "counter_offset_hair": "counter_offset_hair",
    "counter_offset_commissions": "counter_offset_commissions",
    "support_bale_id": "site_support_bale_id",
    "support_bale_user": "site_support_bale_user",
    "support_telegram": "site_support_telegram",
    "instagram": "site_instagram",
    "whatsapp": "site_whatsapp",
    "eitaa": "site_eitaa",
    "rubika": "site_rubika",
    "footer_copyright": "site_footer_copyright",
    "designer_name": "site_designer_name",
    "designer_url": "site_designer_url",
    "google_site_verification": "google_site_verification",
    "google_analytics_id": "google_analytics_id",
    "login_logo": "login_logo_path",
}
DEFAULTS = {
    "idle_minutes": "10",
    "idle_enabled": "1",
    "idle_role": "both",
    "idle_minutes_admin": "0",
    "idle_minutes_user": "0",
    "registration_enabled": "1",
    "extra_sections": "1",
    "site_theme": "original",
    "brand_name": "گیسو صادقی",
    "brand_tagline": "هوشمند ببین، دقیق انتخاب کن",
    "logo_path": "",
    "hero_image_path": "",
    "support_bale_id": "1191639507",
    "support_bale_user": "",
    "support_telegram": "",
    "instagram": "",
    "whatsapp": "",
    "eitaa": "",
    "rubika": "",
    "footer_copyright": "",
    "designer_name": "",
    "designer_url": "",
    "google_site_verification": "",
    "google_analytics_id": "",
    "login_logo": "",
}
# مرحله اول بازنشستگی تم‌ها: فقط دو تم در UI قابل انتخاب‌اند. مقادیر قدیمی
# در app.py به smart_assistant نگاشت می‌شوند تا دیتابیس‌های قدیمی نشکنند.
SITE_THEMES = [
    ("original", "🎯 مسیر هوشمند گیسو"),
    ("smart_assistant", "✦ دستیار هوشمند"),
]


MAINTENANCE_DURATIONS = (0, 5, 15, 30, 60, 120, 240)


def _get_bot_setting(key, default=""):
    try:
        from giso.base import get_bot_db_conn
        conn = get_bot_db_conn()
        try:
            row = conn.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
            return str((row[0] if row else default) or default)
        finally:
            conn.close()
    except Exception:
        return default


def _set_bot_setting(key, value):
    try:
        from giso.base import get_bot_db_conn
        conn = get_bot_db_conn()
        try:
            conn.execute("INSERT INTO settings (key, value) VALUES (?, ?) "
                         "ON CONFLICT(key) DO UPDATE SET value=excluded.value", (key, str(value)))
            conn.commit()
        finally:
            conn.close()
    except Exception as e:
        logger.warning(f"bot setting {key} write failed: {e}")


def get_maintenance_context() -> dict:
    """وضعیت به‌روزرسانی برای پنل سوپرادمین (کار ۱ دستورالعمل)."""
    try:
        dur_raw = _get_bot_setting("giso_maintenance_duration", "0")
        dur = int(str(dur_raw).translate(str.maketrans("۰۱۲۳۴۵۶۷۸۹", "0123456789")) or 0)
    except (TypeError, ValueError):
        dur = 0
    if dur not in MAINTENANCE_DURATIONS:
        dur = 0
    from flask import current_app
    img_exists = False
    try:
        img_exists = os.path.isfile(os.path.join(current_app.static_folder or "", "images", "maintenance_custom.webp"))
    except Exception:
        pass
    return {
        "maintenance_on": _get_bot_setting("giso_maintenance", "") == "on",
        "maintenance_duration": dur,
        "maintenance_durations": MAINTENANCE_DURATIONS,
        "maintenance_image_exists": img_exists,
    }


def _save_maintenance_image(file_storage) -> bool:
    """تصویر سفارشی صفحهٔ به‌روزرسانی: ≤5MB/20MP، تبدیل امن به WebP، جایگزینی اتمیک."""
    try:
        data = file_storage.read()
        if len(data) > 5 * 1024 * 1024:
            flash("⚠️ تصویر به‌روزرسانی باید حداکثر ۵ مگابایت باشد.", "warning")
            return False
        import io
        from PIL import Image
        img = Image.open(io.BytesIO(data))
        img.verify()
        img = Image.open(io.BytesIO(data))
        w, h = img.size
        if w * h > 20_000_000:
            flash("⚠️ ابعاد تصویر به‌روزرسانی بسیار بزرگ است (سقف ۲۰ مگاپیکسل).", "warning")
            return False
        img = img.convert("RGB")
        img.thumbnail((1600, 1600))
        from flask import current_app
        target = os.path.join(current_app.static_folder or "", "images", "maintenance_custom.webp")
        os.makedirs(os.path.dirname(target), exist_ok=True)
        tmp = target + f".tmp-{os.getpid()}"
        img.save(tmp, "WEBP", quality=85, method=6)
        os.replace(tmp, target)  # جایگزینی اتمیک
        _set_bot_setting("giso_maintenance_image_version", str(int(__import__("time").time())))
        return True
    except Exception as e:
        logger.warning(f"maintenance image save failed: {e}")
        flash("⚠️ فایل تصویر معتبر نیست (فقط jpg/png/webp سالم پذیرفته می‌شود).", "warning")
        return False


def _save_login_logo(file_storage) -> bool:
    """لوگوی صفحهٔ ورود: فقط PNG/WebP، ≤2MB، ذخیره با نام ثابت و مسیر در giso_config."""
    ext = os.path.splitext(file_storage.filename or "")[1].lower()
    if ext not in (".png", ".webp"):
        flash("⚠️ لوگوی صفحهٔ ورود فقط می‌تواند PNG یا WebP باشد.", "warning")
        return False
    try:
        data = file_storage.read()
        if len(data) > 2 * 1024 * 1024:
            flash("⚠️ لوگوی صفحهٔ ورود باید حداکثر ۲ مگابایت باشد.", "warning")
            return False
        import io
        from PIL import Image
        img = Image.open(io.BytesIO(data))
        img.verify()
        img = Image.open(io.BytesIO(data))
        w, h = img.size
        if w * h > 20_000_000:
            flash("⚠️ ابعاد لوگو بسیار بزرگ است.", "warning")
            return False
        img.thumbnail((512, 512))
        from flask import current_app
        folder = os.path.join(current_app.static_folder or "", "uploads", "logos")
        os.makedirs(folder, exist_ok=True)
        fmt = "WEBP" if ext == ".webp" else "PNG"
        if fmt == "PNG":
            img = img.convert("RGBA")
        else:
            img = img.convert("RGB")
        target = os.path.join(folder, f"login_logo{ext}")
        tmp = target + f".tmp-{os.getpid()}"
        img.save(tmp, fmt)
        os.replace(tmp, target)
        _set_config(KEYS["login_logo"], f"uploads/logos/login_logo{ext}")
        return True
    except Exception as e:
        logger.warning(f"login logo save failed: {e}")
        flash("⚠️ فایل لوگو معتبر نیست.", "warning")
        return False


def _get_config(key, default=""):
    try:
        from giso_admin import get_giso_config
        return get_giso_config(key, default) or default
    except Exception:
        return default


def _set_config(key, value):
    try:
        from giso_admin import set_giso_config
        set_giso_config(key, str(value))
    except Exception as e:
        logger.warning(f"settings set {key}: {e}")
    try:
        from giso.base import invalidate_giso_config_cache
        invalidate_giso_config_cache()
    except Exception:
        pass


def get_idle_config() -> dict:
    def _num(key, default):
        try:
            return max(0, min(1440, int(_get_config(key, default) or default)))
        except (TypeError, ValueError):
            return int(default)
    enabled = str(_get_config(KEYS["idle_enabled"], DEFAULTS["idle_enabled"])) == "1"
    role = str(_get_config(KEYS["idle_role"], DEFAULTS["idle_role"])).strip().lower()
    if role not in ("both", "admin", "user"):
        role = "both"
    shared = _num(KEYS["idle_minutes"], DEFAULTS["idle_minutes"])
    if shared < 1:
        shared = 10
    m_admin = _num(KEYS["idle_minutes_admin"], "0")
    m_user = _num(KEYS["idle_minutes_user"], "0")
    return {"enabled": enabled, "minutes": shared, "role": role,
            "minutes_admin": m_admin or shared, "minutes_user": m_user or shared}


def idle_minutes_for_role(role: str) -> int:
    try:
        cfg = get_idle_config()
        if not cfg["enabled"]:
            return 0
        apply_to = cfg["role"]
        if apply_to == "admin" and role != "admin":
            return 0
        if apply_to == "user" and role != "user":
            return 0
        return cfg.get(f"minutes_{role}") or cfg.get("minutes") or 10
    except Exception:
        return 10


def get_idle_minutes() -> int:
    return get_idle_config()["minutes"]


def _clean_digits(val, maxlen=20):
    return "".join(ch for ch in str(val or "") if ch.isdigit())[:maxlen]


def _clean_handle(val, maxlen=40):
    s = str(val or "").strip().lstrip("@")
    s = re.sub(r"^https?://", "", s, flags=re.I)
    for prefix in ("www.instagram.com/", "instagram.com/", "ble.ir/", "bale.ai/"):
        if s.lower().startswith(prefix):
            s = s[len(prefix):]
    s = s.strip("/").split("?")[0].split("/")[0]
    return "".join(ch for ch in s if ch.isalnum() or ch in "._")[:maxlen]


def _clean_url(val, maxlen=200):
    """URL عمومی امن (فقط http/https، بدون لوکال/داخلی) — برای لینک طراح سایت."""
    s = str(val or "").strip()
    if not s:
        return ""
    if not re.match(r"^https?://", s, flags=re.I):
        s = "https://" + s
    try:
        from urllib.parse import urlparse
        host = (urlparse(s).hostname or "").lower()
        if not host or any(x in host for x in ("127.", "localhost", "0.0.0.0", "::1", "10.", "192.168.")):
            return ""
    except Exception:
        return ""
    return s[:maxlen]


def _clean_google_verify(val):
    s = str(val or "").strip()
    return s if re.fullmatch(r"[A-Za-z0-9_-]{8,100}", s) else ""


def _clean_ga_id(val):
    s = str(val or "").strip()
    if re.fullmatch(r"G-[A-Z0-9]+", s, re.I):
        return "G-" + s.split("-", 1)[1]
    if re.fullmatch(r"GTM-[A-Z0-9]+", s, re.I):
        return "GTM-" + s.split("-", 1)[1]
    if re.fullmatch(r"UA-\d+-\d+", s, re.I):
        return s.upper()
    return ""


def get_site_appearance() -> dict:
    """فوتر، شبکه‌های اجتماعی و تگ‌های گوگل — از تنظیمات سوپر، با مقدار امن برای قالب."""
    # فیلدهای تلفن/ایمیل دیگر فرم پنل ندارند؛ فقط برای سازگاری با خوانش‌های قدیمی خوانده می‌شوند.
    phone = _clean_digits(_get_config("site_support_phone", ""), 15)
    bale_id = _clean_digits(_get_config(KEYS["support_bale_id"], DEFAULTS["support_bale_id"]), 20)
    bale_user = _clean_handle(_get_config(KEYS["support_bale_user"], DEFAULTS["support_bale_user"]))
    instagram = _clean_handle(_get_config(KEYS["instagram"], DEFAULTS["instagram"]))
    telegram = _clean_handle(_get_config(KEYS["support_telegram"], DEFAULTS["support_telegram"]))
    eitaa = _clean_handle(_get_config(KEYS["eitaa"], DEFAULTS["eitaa"]))
    rubika = _clean_handle(_get_config(KEYS["rubika"], DEFAULTS["rubika"]))
    whatsapp = _clean_digits(_get_config(KEYS["whatsapp"], DEFAULTS["whatsapp"]), 15)
    bale_url = ""
    if bale_user:
        bale_url = "https://ble.ir/" + bale_user
    elif bale_id:
        bale_url = "https://ble.ir/" + bale_id
    return {
        "phone": phone,
        "bale_id": bale_id,
        "bale_user": bale_user,
        "bale_url": bale_url,
        "telegram": telegram,
        "telegram_url": ("https://t.me/" + telegram) if telegram else "",
        "instagram": instagram,
        "instagram_url": ("https://instagram.com/" + instagram) if instagram else "",
        "whatsapp": whatsapp,
        "whatsapp_url": ("https://wa.me/" + whatsapp) if whatsapp else "",
        "eitaa": eitaa,
        "eitaa_url": ("https://eitaa.com/" + eitaa) if eitaa else "",
        "rubika": rubika,
        "rubika_url": ("https://rubika.ir/" + rubika) if rubika else "",
        "email": str(_get_config("site_support_email", "")).strip()[:80],
        "footer_copyright": str(_get_config(KEYS["footer_copyright"], DEFAULTS["footer_copyright"])).strip()[:200],
        "designer_name": str(_get_config(KEYS["designer_name"], DEFAULTS["designer_name"])).strip()[:80],
        "designer_url": _clean_url(_get_config(KEYS["designer_url"], DEFAULTS["designer_url"])),
        "google_site_verification": _clean_google_verify(
            _get_config(KEYS["google_site_verification"], DEFAULTS["google_site_verification"])
        ),
        "google_analytics_id": _clean_ga_id(
            _get_config(KEYS["google_analytics_id"], DEFAULTS["google_analytics_id"])
        ),
    }


def is_registration_enabled() -> bool:
    try:
        return _get_config(KEYS["registration_enabled"], DEFAULTS["registration_enabled"]) == "1"
    except Exception:
        return True


def get_site_base_url() -> str:
    """آدرس پایه‌ی سایت؛ اگر هنوز در تنظیمات ذخیره نشده باشد، آدرس رسمی گیسو
    (DEFAULT_SITE_BASE_URL) به‌عنوان پیش‌فرض برمی‌گردد تا فیلد تنظیمات و لاگ‌ها
    خالی نباشند و ربات/لینک‌ها آدرس درست را نشان دهند."""
    try:
        from giso.base import get_giso_db_conn, DEFAULT_SITE_BASE_URL
        with get_giso_db_conn() as conn:
            row = conn.execute("SELECT value FROM giso_config WHERE key='site_base_url'").fetchone()
        val = str((row[0] if row else "") or "").strip().rstrip("/")
        return val or DEFAULT_SITE_BASE_URL
    except Exception:
        try:
            from giso.base import DEFAULT_SITE_BASE_URL
            return DEFAULT_SITE_BASE_URL
        except Exception:
            return "https://gisosadeghi.ir"


def set_site_base_url(url: str):
    from datetime import datetime
    url = (url or "").strip().rstrip("/")
    if not url:
        return False, "آدرس نمی‌تواند خالی باشد"
    if not (url.startswith("http://") or url.startswith("https://")):
        return False, "آدرس باید با http:// یا https:// شروع شود"
    try:
        from urllib.parse import urlparse
        host = (urlparse(url).hostname or "").lower()
        if any(x in host for x in ("127.", "localhost", "0.0.0.0", "::1", "10.", "192.168.")):
            return False, "آدرس لوکال/داخلی قابل ذخیره نیست؛ آدرس عمومی دامنه را وارد کنید (اعلان‌ها روی گوشی با آدرس لوکال باز نمی‌شوند)."
    except Exception:
        pass
    try:
        from giso.base import get_giso_db_conn
        with get_giso_db_conn() as conn:
            conn.execute("CREATE TABLE IF NOT EXISTS giso_config (id INTEGER PRIMARY KEY AUTOINCREMENT, key TEXT UNIQUE NOT NULL, value TEXT DEFAULT '', updated_at TEXT DEFAULT '')")
            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            conn.execute("INSERT INTO giso_config (key, value, updated_at) VALUES ('site_base_url', ?, ?) ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_at=excluded.updated_at", (url, now))
            conn.commit()
        # 🔄 همگام‌سازی با bot.db: پنل ربات edu همین کلید را از bot.db می‌خواند.
        try:
            from giso.db_core import sync_site_config_to_bot_db
            sync_site_config_to_bot_db("site_base_url", url)
        except Exception as e:
            logger.warning(f"site_base_url sync to bot.db skipped: {e}")
        return True, "آدرس سایت ذخیره شد."
    except Exception as e:
        return False, f"خطا: {str(e)[:100]}"


def test_site_base_url(url: str) -> tuple:
    import urllib.request
    url = (url or "").strip().rstrip("/")
    if not (url.startswith("http://") or url.startswith("https://")):
        return False, "آدرس باید با http:// یا https:// شروع شود"
    try:
        req = urllib.request.Request(url, method="GET", headers={"User-Agent": "Giso-Panel/1.0"})
        with urllib.request.urlopen(req, timeout=8) as resp:
            return True, f"آدرس در دسترس است (HTTP {resp.status})."
    except urllib.error.HTTPError as e:
        return False, f"سرور پاسخ داد ولی با خطا (HTTP {e.code})."
    except Exception as e:
        return False, f"اتصال برقرار نشد: {str(e)[:120]}"


def _handle_post(role):
    if role != "super":
        flash("فقط سوپرادمین می‌تواند تنظیمات را تغییر دهد.", "warning")
        return redirect(url_for("panel.settings"))
    try:
        if "idle_minutes" in request.form or "idle_enabled" in request.form:
            idle = request.form.get("idle_minutes", "10").strip()
            try: idle = max(1, min(1440, int(idle)))
            except (TypeError, ValueError): idle = 10
            enabled = request.form.get("idle_enabled") == "1"
            role_opt = (request.form.get("idle_role") or "both").strip().lower()
            if role_opt not in ("both", "admin", "user"): role_opt = "both"
            m_admin = request.form.get("idle_minutes_admin", "0").strip()
            m_user = request.form.get("idle_minutes_user", "0").strip()
            try: m_admin = max(0, min(1440, int(m_admin)))
            except (TypeError, ValueError): m_admin = 0
            try: m_user = max(0, min(1440, int(m_user)))
            except (TypeError, ValueError): m_user = 0
            _set_config(KEYS["idle_minutes"], idle)
            _set_config(KEYS["idle_enabled"], "1" if enabled else "0")
            _set_config(KEYS["idle_role"], role_opt)
            _set_config(KEYS["idle_minutes_admin"], m_admin)
            _set_config(KEYS["idle_minutes_user"], m_user)
            flash("تایمر خروج پنل ذخیره و همان لحظه اعمال شد.", "success")

        if request.form.get("save_maintenance") == "1":
            # مدت به‌روزرسانی (کار ۱): گزینه‌های ثابت؛ مقدار نامعتبر → بدون تایمر
            dur_raw = (request.form.get("maintenance_duration") or "0").strip()
            try:
                dur = int(str(dur_raw).translate(str.maketrans("۰۱۲۳۴۵۶۷۸۹", "0123456789")) or 0)
            except (TypeError, ValueError):
                dur = 0
            if dur not in MAINTENANCE_DURATIONS:
                dur = 0
            _set_bot_setting("giso_maintenance_duration", dur)
            if request.form.get("remove_maintenance_image") == "1":
                try:
                    from flask import current_app
                    target = os.path.join(current_app.static_folder or "", "images", "maintenance_custom.webp")
                    if os.path.isfile(target):
                        os.remove(target)
                        _set_bot_setting("giso_maintenance_image_version", "0")
                except Exception as e:
                    logger.warning(f"maintenance image remove failed: {e}")
            file = request.files.get("maintenance_image")
            if file and file.filename:
                if _save_maintenance_image(file):
                    flash("✅ تصویر صفحهٔ به‌روزرسانی ذخیره شد.", "success")
            flash("تنظیمات صفحهٔ به‌روزرسانی ذخیره شد.", "success")

        if request.form.get("save_login_logo") == "1":
            if request.form.get("remove_login_logo") == "1":
                _set_config(KEYS["login_logo"], "")
                flash("لوگوی صفحهٔ ورود حذف شد؛ لوگوی برند سایت نمایش داده می‌شود.", "success")
            else:
                file = request.files.get("login_logo")
                if file and file.filename and _save_login_logo(file):
                    flash("✅ لوگوی صفحهٔ ورود ذخیره شد و در /login اعمال شد.", "success")

        if request.form.get("save_registration") == "1":
            reg = request.form.get("registration_enabled") == "1"
            _set_config(KEYS["registration_enabled"], "1" if reg else "0")
            if "extra_sections" in request.form:
                extra = request.form.get("extra_sections") == "1"
                _set_config(KEYS["extra_sections"], "1" if extra else "0")
            flash("وضعیت ثبت‌نام ذخیره شد.", "success")

        if "site_theme" in request.form:
            theme = (request.form.get("site_theme") or "original").strip().lower()
            if theme not in [t for t, _ in SITE_THEMES]: theme = "original"
            _set_config(KEYS["site_theme"], theme)
            flash("تم سایت ذخیره شد و در کل سایت گیسو اعمال شد.", "success")

        if request.form.get("save_brand") == "1":
            _set_config(KEYS["brand_name"], (request.form.get("brand_name") or "").strip()[:80])
            _set_config(KEYS["brand_tagline"], (request.form.get("brand_tagline") or "").strip()[:120])
            if request.form.get("remove_logo") == "1": _set_config(KEYS["logo_path"], "")
            if request.form.get("remove_hero_image") == "1": _set_config(KEYS["hero_image_path"], "")
            # دو لوگو/تصویر جدا: ① لوگوی هدر ② تصویر بزرگ صفحه اول (هیرو)
            for _field, _cfg_key, _label in (
                ("brand_logo", "logo_path", "لوگو"),
                ("hero_image", "hero_image_path", "تصویر صفحه اول"),
            ):
                file = request.files.get(_field)
                if file and file.filename:
                    ext = os.path.splitext(file.filename or "")[1].lower()
                    if ext in (".jpg", ".jpeg", ".png", ".webp", ".svg"):
                        try:
                            from giso.shop.logic.inventory import _save_product_image
                            saved = _save_product_image(file)
                            if saved: _set_config(KEYS[_cfg_key], saved)
                        except Exception as _le:
                            logger.warning(f"settings {_field} save: {_le}")
                            flash(f"⚠️ ذخیره {_label} ناموفق بود، ولی متن‌ها ذخیره شدند.", "warning")
                    else: flash(f"⚠️ فرمت {_label} باید jpg/png/webp باشد.", "warning")
            flash("لوگو و هدر سایت ذخیره شد و در کل سایت اعمال شد.", "success")

        if request.form.get("save_appearance") == "1":
            _set_config(KEYS["support_bale_user"], _clean_handle(request.form.get("support_bale_user")))
            _set_config(KEYS["support_telegram"], _clean_handle(request.form.get("support_telegram")))
            _set_config(KEYS["instagram"], _clean_handle(request.form.get("instagram")))
            _set_config(KEYS["whatsapp"], _clean_digits(request.form.get("whatsapp"), 15))
            _set_config(KEYS["eitaa"], _clean_handle(request.form.get("eitaa")))
            _set_config(KEYS["rubika"], _clean_handle(request.form.get("rubika")))
            _set_config(KEYS["google_site_verification"], _clean_google_verify(request.form.get("google_site_verification")))
            _set_config(KEYS["google_analytics_id"], _clean_ga_id(request.form.get("google_analytics_id")))
            flash("ظاهر سایت، شبکه‌های اجتماعی و گوگل ذخیره شد و روی سایت اعمال شد.", "success")

        if request.form.get("save_footer_credit") == "1":
            _set_config(KEYS["footer_copyright"], str(request.form.get("footer_copyright") or "").strip()[:200])
            _set_config(KEYS["designer_name"], str(request.form.get("designer_name") or "").strip()[:80])
            _set_config(KEYS["designer_url"], _clean_url(request.form.get("designer_url")))
            flash("نوار فوتر و اعتبار طراح ذخیره شد و روی سایت اعمال شد.", "success")

        if request.form.get("save_counters") == "1":
            for _k in ("counter_offset_users", "counter_offset_analyses", "counter_offset_hair", "counter_offset_commissions"):
                try:
                    _v = int(str(request.form.get(_k, "0") or "0").translate(str.maketrans("۰۱۲۳۴۵۶۷۸۹", "0123456789")) or 0)
                except (TypeError, ValueError): _v = 0
                _set_config(KEYS[_k], str(max(0, min(99999999, _v))))
            flash("عددهای نمایشی شمارنده‌ها ذخیره شد (مبنا: آمار واقعی دیتابیس).", "success")

        if "site_base_url" in request.form:
            url = (request.form.get("site_base_url") or "").strip()
            action = (request.form.get("site_url_action") or "save").strip()
            if action == "test":
                ok, msg = test_site_base_url(url)
                flash(("✅ " if ok else "❌ ") + msg, "success" if ok else "danger")
            else:
                ok, msg = set_site_base_url(url)
                flash(("✅ " if ok else "❌ ") + msg, "success" if ok else "danger")
    except Exception as e:
        logger.error(f"settings post: {e}")
        flash("خطا در ذخیره تنظیمات.", "danger")
    return redirect(url_for("panel.settings"))


def context():
    cfg = get_idle_config()
    pending_restore = ""
    try:
        from flask import session
        pending_restore = str(session.get("panel_restore_file") or "").strip()
    except Exception: pass
    return {
        "idle_enabled": cfg["enabled"], "idle_shared_minutes": cfg["minutes"],
        "idle_role": cfg["role"], "idle_minutes_admin": cfg["minutes_admin"], "idle_minutes_user": cfg["minutes_user"],
        "registration_enabled": _get_config(KEYS["registration_enabled"], DEFAULTS["registration_enabled"]) == "1",
        "extra_sections": _get_config(KEYS["extra_sections"], DEFAULTS["extra_sections"]) == "1",
        "site_theme": _get_config(KEYS["site_theme"], DEFAULTS["site_theme"]) or "original",
        "site_themes": SITE_THEMES,
        "brand_name": _get_config(KEYS["brand_name"], DEFAULTS["brand_name"]),
        "brand_tagline": _get_config(KEYS["brand_tagline"], DEFAULTS["brand_tagline"]),
        "logo_path": _get_config(KEYS["logo_path"], DEFAULTS["logo_path"]),
        "hero_image_path": _get_config(KEYS["hero_image_path"], DEFAULTS["hero_image_path"]),
        "counter_offset_users": _get_config(KEYS["counter_offset_users"], "0"),
        "counter_offset_analyses": _get_config(KEYS["counter_offset_analyses"], "0"),
        "counter_offset_hair": _get_config(KEYS["counter_offset_hair"], "0"),
        "counter_offset_commissions": _get_config(KEYS["counter_offset_commissions"], "0"),
        "site_base_url": get_site_base_url(),
        "login_logo_path": _get_config(KEYS["login_logo"], DEFAULTS["login_logo"]),
        **get_maintenance_context(),
        "pending_restore": pending_restore,
        "backup": _backup_context(),
        **get_site_appearance(),
    }


def _backup_context():
    try:
        from giso.panel.modules import backup as _bk
        return _bk.context()
    except Exception as e:
        logger.warning(f"backup context: {e}")
        return {"files": [], "interval_hours": 0, "backup_dir_exists": False}


def handle_post():
    """پردازش POST — فقط سوپرادمین (در route فراخوانی می‌شود)."""
    role, perms, bale_id = current_role_and_perms()
    return _handle_post(role)
