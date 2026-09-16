# -*- coding: utf-8 -*-
"""
giso/app.py — فایل اصلی Flask پروژه گیسو (Main Runner، احراز هویت، داشبورد و پنل ادمین).
"""
import json
import logging
import os
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path
try:
    from flask import (Flask, render_template, request, redirect, url_for,
                       flash, session, jsonify)
    from flask_login import (LoginManager, login_user, logout_user,
                             login_required, current_user)
    from werkzeug.security import generate_password_hash, check_password_hash
except ImportError:
    class DummyFlask:
        def __init__(self, *a, **kw):
            class C:
                def from_object(self, *a): pass
            self.config = C()
            self.permanent_session_lifetime = None
        def route(self, *a, **kw):
            return lambda fn: fn
        def before_request(self, fn):
            return fn
        def context_processor(self, fn):
            return fn
        def add_url_rule(self, *a, **kw):
            pass
        class _AC:
            def __enter__(self): pass
            def __exit__(self, *a): pass
        def app_context(self):
            return self._AC()
    Flask = DummyFlask
    def render_template(*a, **kw): return ""
    def redirect(*a, **kw): return ""
    def url_for(*a, **kw): return ""
    def flash(*a, **kw): pass
    request = None
    session = {}
    def jsonify(*a, **kw): return {}
    class LoginManager:
        def __init__(self, *a, **kw): pass
        def user_loader(self, fn): return fn
    def login_user(*a, **kw): pass
    def logout_user(*a, **kw): pass
    def login_required(fn): return fn
    current_user = None

sys.path.append(str(Path(__file__).resolve().parent.parent / "bot_edu"))
from giso.config import Config, SUPERADMIN_BALE_ID, is_super_admin
from giso.models import (
    db,
    User,
    HairOrder,
    Analysis,
    ProductOrder,
    Review,
    migrate_giso_tables,
)
from giso.base import normalize_phone, get_giso_db_conn, get_bot_db_conn, to_shamsi, display_phone, _giso_init_db
from giso.security import install_security, ensure_security_tables, audit_event, validate_new_password
from giso.hair_sale import register_hair_sale_routes
from giso.analysis import register_analysis_routes
from giso.shop import register_shop_routes, seed_sample_products
from giso.ai_runtime import (
    get_display_name,
    set_display_name,
    get_widget_config,
    set_widget_enabled,
    set_widget_position,
    set_widget_welcome_message,
    set_widget_primary_color,
    list_provider_options,
    set_role_policy,
    set_role_capabilities,
    get_failover_chain,
    set_failover_chain,
    set_chat_enabled,
    set_active_provider,
    build_site_widget_context,
    build_site_widget_prompt,
    build_site_widget_fallback_reply,
    build_widget_welcome,
    chat_with_managed_ai,
)

logger = logging.getLogger("giso_app")
from giso.stepup import (
    _ADMIN_PANEL_SESSION_TTL_SECONDS,
    _admin_panel_clear_state,
    _admin_panel_target,
    _admin_panel_is_verified,
    _generate_admin_panel_code,
    _send_admin_panel_code_to_bot,
    _admin_panel_issue_code_via,
    _admin_panel_verify_code,
    _admin_panel_current_stepup_status,
    _sensitive_register_clear_state,
    _sensitive_register_requires_bot_code,
    _sensitive_register_issue_code_via,
    _sensitive_register_verify_code,
    _sensitive_register_status,
    render_register_view as _render_register_view,
)
def _admin_panel_issue_code(phone_norm: str, force: bool = False):
    """لایه‌ی re-export گیسو: منطق در stepup، اما مولد/ارسال‌کننده از همین ماژول
    خوانده می‌شوند تا patch های قبلی روی giso.app همچنان مؤثر بمانند."""
    return _admin_panel_issue_code_via(
        phone_norm, force, _generate_admin_panel_code, _send_admin_panel_code_to_bot,
    )
def _sensitive_register_issue_code(phone_norm: str, force: bool = False):
    """لایه‌ی re-export گیسو برای صدور کد ثبت‌نام حساس (قابل patch در giso.app)."""
    return _sensitive_register_issue_code_via(
        phone_norm, force, _generate_admin_panel_code, _send_admin_panel_code_to_bot,
    )
from giso.widget_service import (
    _resolve_site_ai_role,
    _widget_actor_key,
    _widget_history_get,
    _widget_history_set,
    _widget_log_chat,
    _widget_user_brief,
    _widget_staff_report,
    _widget_csrf_token,
    _notify_consultant_admin_new_msg,
    _notify_consultant_user_new_msg,
)

_BOT_FLAG_CACHE = {}
_HOME_CACHE = {}
def _compute_home_data(home_stats: dict, home_reviews: list):
    """محاسبه آمار و نظرات صفحه اصلی (یک‌بار در هر بازه کش)."""
    try:
        with get_giso_db_conn() as conn:
            home_stats["users"] = conn.execute("SELECT COUNT(*) FROM giso_web_auth").fetchone()[0] or 0
            home_stats["analyses"] = conn.execute("SELECT COUNT(*) FROM analyses").fetchone()[0] or 0
            home_stats["orders"] = conn.execute(
                "SELECT COUNT(*) FROM product_orders WHERE status='completed'").fetchone()[0] or 0
            # خریدهای مو (با قیمت قطعی؛ اگر هنوز قیمت‌دار نیست، کل درخواست‌ها)
            _hs = conn.execute(
                "SELECT COUNT(*) FROM hair_orders WHERE COALESCE(final_price,0) > 0").fetchone()[0] or 0
            home_stats["hair_sales"] = int(_hs) or conn.execute("SELECT COUNT(*) FROM hair_orders").fetchone()[0] or 0
            # تسویه‌های موفق کیف پول (کلید داخلی commissions برای سازگاری قالب قدیمی حفظ شده)
            try:
                home_stats["commissions"] = conn.execute(
                    "SELECT COUNT(*) FROM withdrawal_requests WHERE status='paid'").fetchone()[0] or 0
            except Exception:
                home_stats["commissions"] = 0
            rv = conn.execute(
                "SELECT COUNT(*), COALESCE(AVG(rating),0) FROM reviews WHERE status='visible'"
            ).fetchone()
            home_stats["reviews"] = int(rv[0] or 0)
            _avg = float(rv[1] or 0.0)
            home_stats["avg_rating"] = round(_avg, 1)
            # درصد رضایت ≈ سهم نظرات ۴ و ۵ ستاره
            home_stats["satisfaction"] = round((_avg / 5.0) * 100) if _avg > 0 else 0
            rows = conn.execute(
                "SELECT phone, review_type, order_id, rating, comment, created_at FROM reviews "
                "WHERE status='visible' AND comment != '' ORDER BY id DESC LIMIT 12"
            ).fetchall()

            def _mask(ph):
                ph = str(ph or "")
                if len(ph) >= 8:
                    return ph[:5] + "•••" + ph[-3:]
                return ph or "کاربر گیسو"

            def _order_product_price(rt, oid):
                """نام محصول + قیمت مرتبط با نظر (برای کارت کروسل)."""
                try:
                    if rt == "shop_order" and oid:
                        o = conn.execute(
                            "SELECT product_id FROM product_orders WHERE id=?", (oid,)).fetchone()
                        if o and o["product_id"]:
                            pr = conn.execute(
                                "SELECT name, price FROM products WHERE id=?", (o["product_id"],)).fetchone()
                            if pr:
                                return pr["name"], int(pr["price"] or 0)
                    if rt in ("hair", "hair_sale") and oid:
                        h = conn.execute(
                            "SELECT final_price FROM hair_orders WHERE id=?", (oid,)).fetchone()
                        if h and h["final_price"]:
                            return "فروش مو", int(h["final_price"])
                except Exception:
                    pass
                return "", 0

            _type_fa = {"shop_order": "فروشگاه", "hair": "فروش مو", "hair_sale": "فروش مو",
                        "analysis": "آنالیز"}
            for r in rows:
                _pn, _pp = _order_product_price(r["review_type"], r["order_id"])
                home_reviews.append({
                    "name": _mask(r["phone"]),
                    "label": _type_fa.get(r["review_type"], r["review_type"] or "گیسو"),
                    "rating": int(r["rating"] or 0),
                    "comment": (r["comment"] or "")[:180],
                    "date": str(r["created_at"] or "")[:10],
                    "product_name": _pn,
                    "price": _pp,
                })
    except Exception as _e:
        logger.debug(f"index home stats error: {_e}")
def _bot_setting_value(key: str, default: str = "") -> str:
    try:
        conn=get_bot_db_conn()
        try:
            row=conn.execute("SELECT value FROM settings WHERE key=?",(key,)).fetchone()
            return str((row[0] if row else default) or default)
        finally: conn.close()
    except Exception: return default
def _maintenance_flag(key: str) -> bool:
    """خواندن فلگ نگهداری از bot.db با کش کوتاه ده‌ثانیه‌ای."""
    try:
        now = time.time()
        hit = _BOT_FLAG_CACHE.get(key)
        if hit and (now - hit[1]) < 10:
            return hit[0]
        conn = get_bot_db_conn()
        try:
            row = conn.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
            val = str((row[0] if row else "") or "").strip().lower() == "on"
        finally:
            conn.close()
        # گذار روشن→خاموش: زمان شروع تایمر پاک می‌شود تا دور بعدیِ
        # به‌روزرسانی با تایمر تازه شروع شود (ایدمپوتنت).
        if key == "giso_maintenance" and hit and hit[0] and not val:
            _maint_started_at_write(None)
        _BOT_FLAG_CACHE[key] = (val, now)
        return val
    except Exception as exc:
        # رفتار fail-safe: اگر bot.db خوانده نشد، maintenance خاموش فرض می‌شود (بدون کرش).
        logger.warning("maintenance flag (%s) read failed → default False: %s", key, exc)
        return False

# ── تایمر به‌روزرسانی (کار ۱ — مطابق دستورالعمل) ──────────────────────────
# مدت (دقیقه) و زمان شروع در جدول settings همان bot.db ذخیره می‌شوند که خودِ
# فلگ نگهداری از آن خوانده می‌شود؛ نوشتن ایدمپوتنت و فقط هنگام فعال‌بودن حالت است.
_MAINT_DURATION_OPTIONS = (0, 5, 15, 30, 60, 120, 240)
def _maint_duration_minutes() -> int:
    """مدت به‌روزرسانی (دقیقه) — ۰ یعنی بدون تایمر."""
    try:
        raw = _bot_setting_value("giso_maintenance_duration", "0")
        val = int(str(raw).translate(str.maketrans("۰۱۲۳۴۵۶۷۸۹", "0123456789")) or 0)
    except (TypeError, ValueError):
        val = 0
    return val if val in _MAINT_DURATION_OPTIONS else 0
def _maint_started_at() -> int:
    try:
        return max(0, int(_bot_setting_value("giso_maintenance_started_at", "0") or 0))
    except (TypeError, ValueError):
        return 0
def _maint_started_at_write(value=None):
    """value=epoch → ذخیرهٔ ایدمپوتنت؛ value=None → پاک‌کردن (پایان دور به‌روزرسانی)."""
    try:
        conn = get_bot_db_conn()
        try:
            if value is None:
                conn.execute("DELETE FROM settings WHERE key='giso_maintenance_started_at'")
            else:
                conn.execute(
                    "INSERT INTO settings (key, value) VALUES ('giso_maintenance_started_at', ?) "
                    "ON CONFLICT(key) DO UPDATE SET value=excluded.value", (str(int(value)),))
            conn.commit()
        finally:
            conn.close()
    except Exception as exc:
        logger.warning("maintenance started_at write failed: %s", exc)
def _maint_resolve_until() -> int:
    """epoch پایان به‌روزرسانی؛ ۰ یعنی بدون تایمر (نمایش داده نمی‌شود)."""
    duration = _maint_duration_minutes()
    if duration <= 0:
        return 0
    try:
        started = _maint_started_at()
        if not started:
            started = int(time.time())
            _maint_started_at_write(started)
        return started + duration * 60
    except Exception:
        return 0

def _giso_maintenance_admin_bypass() -> bool:
    try:
        if not current_user.is_authenticated:
            return False
        phone_norm = normalize_phone(getattr(current_user, "phone", "") or "")
        if is_super_admin(phone=phone_norm):
            return True
        if phone_norm in _env_site_admin_phones():
            return True
        conn = get_bot_db_conn()
        try:
            row = conn.execute("SELECT 1 FROM giso_admins WHERE phone=? LIMIT 1", (phone_norm,)).fetchone()
            return bool(row)
        finally:
            conn.close()
    except Exception:
        pass
    return False

def cleanup_temp_uploads():
    try:
        import time
        temp_dir = os.path.join(Config.UPLOAD_FOLDER, "temp")
        if not os.path.exists(temp_dir):
            return
        now = time.time()
        for root, dirs, files in os.walk(temp_dir):
            for name in files:
                fpath = os.path.join(root, name)
                try:
                    if os.path.isfile(fpath) and (now - os.path.getmtime(fpath)) > 86400:
                        os.remove(fpath)
                except Exception:
                    pass
    except Exception as e:
        logger.warning(f"cleanup_temp_uploads error: {e}")

def _check_giso_admin_access():
    if not current_user.is_authenticated:
        flash("لطفاً ابتدا وارد حساب کاربری خود شوید.", "warning")
        return redirect(url_for("login"))
    phone_norm = normalize_phone(getattr(current_user, "phone", "") or "")
    try:
        target = _admin_panel_target(phone_norm)
    except Exception as exc:
        logger.error("admin panel target check failed: %s", exc, exc_info=True)
        target = None
    if not target:
        # سوپرادمین از هویت متمرکز config تشخیص داده می‌شود؛ به env وابسته نیست.
        if is_super_admin(phone=phone_norm):
            target = {"role": "super", "bale_id": str(SUPERADMIN_BALE_ID), "phone": phone_norm}
        else:
            flash("دسترسی به پنل مدیریت گیسو فقط برای ادمین‌های مجاز است.", "danger")
            return redirect(url_for("login"))
    try:
        if not _admin_panel_is_verified(phone_norm):
            session["admin_panel_next"] = request.full_path if request.query_string else (request.path or "/admin")
            return redirect(url_for("admin_verify"))
    except Exception as exc:
        logger.error("admin panel step-up check failed: %s", exc, exc_info=True)
        # خطای داخلی نباید به خطای مبهم دسترسی تبدیل شود؛ کاربر به step-up برمی‌گردد.
        session["admin_panel_next"] = request.full_path if request.query_string else (request.path or "/admin")
        return redirect(url_for("admin_verify"))
    return None

def _html_escape_q(s: str) -> str:
    return (str(s).replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;").replace('"', "&quot;"))

def _ensure_ai_logging():
    """فاز ۳: لاگ‌های مشاهده‌پذیری موتورهای AI (مثل [AI_ATTEMPT]) در وب هم دیده شوند.

    فقط وقتی هیچ هندلری تنظیم نشده باشد فعال می‌شود تا با پیکربندی لاگ
    موجود در استقرار کاربر تداخل نکند (بدون هندلر اضافه، خروجی دوتایی نداریم).
    """
    if logging.getLogger().handlers:
        return
    _fmt = logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
    for name in ("giso.ai_brain", "giso.ai_health", "giso_ai_runtime", "giso_analysis"):
        lg = logging.getLogger(name)
        if lg.handlers:
            continue
        handler = logging.StreamHandler()
        handler.setFormatter(_fmt)
        lg.addHandler(handler)
        lg.setLevel(logging.INFO)
        # بدون انتشار به روت: اگر بعداً هندلر روت اضافه شد، خطی دوتایی نشود
        lg.propagate = False

def create_app():
    _ensure_ai_logging()
    app = Flask(__name__)
    app.config.from_object(Config)
    from giso.security import security_startup_warnings
    security_startup_warnings(app, _ADMIN_PANEL_SESSION_TTL_SECONDS)

    os.makedirs(os.path.join(Config.BASE_DIR, "giso", "data"), exist_ok=True)
    os.makedirs(Config.UPLOAD_FOLDER, exist_ok=True)
    os.makedirs(os.path.join(Config.UPLOAD_FOLDER, "temp"), exist_ok=True)
    cleanup_temp_uploads()

    db.init_app(app)

    # فاز ۰ امنیت: CSRF، rate-limit و audit بدون تغییر route/sessionهای قبلی
    install_security(app)
    try:
        with app.app_context():
            ensure_security_tables()
    except Exception as exc:
        logger.warning("security tables init failed: %s", exc)

    @app.teardown_request
    def _record_unhandled_request_error(exc):
        if exc is not None:
            try:
                from giso.monitoring_errors import record
                record('giso-web',request.path,exc)
            except Exception:pass

    login_manager = LoginManager(app)
    login_manager.login_view = "login"
    login_manager.login_message = "لطفاً ابتدا وارد حساب خود شوید."
    login_manager.login_message_category = "info"

    @login_manager.user_loader
    def load_user(phone):
        return User.query.filter_by(phone=phone).first()

    @app.context_processor
    def inject_helpers():
        def _is_giso_admin_user():
            try:
                if not current_user.is_authenticated:
                    return False
                phone_norm = normalize_phone(getattr(current_user, "phone", "") or "")
                if is_super_admin(phone=phone_norm):
                    return True
                from giso_admin import find_giso_admin_by_phone
                return bool(find_giso_admin_by_phone(phone_norm))
            except Exception:
                return False

        def _get_site_theme():
            try:
                from giso.base import cached_giso_config
                theme = cached_giso_config("site_theme", "smart_assistant") or "smart_assistant"
                # بازنشستگی دومرحله‌ای: مقادیر تاریخی به تم جدید نگاشت می‌شوند؛
                # CSS قدیمی تا پایان تست رگرسیون حذف فیزیکی نمی‌شود.
                if theme not in {"original", "smart_assistant"}:
                    return "smart_assistant"
                return theme
            except Exception:
                return "smart_assistant"

        def _get_site_brand():
            """لوگو و هدر داینامیک سایت (قابل مدیریت از ⚙️ تنظیمات سوپرادمین)."""
            brand = {
                "name": "گیسو صادقی",
                "tagline": "هوشمند ببین، دقیق انتخاب کن",
                "logo": "images/logo-96.webp",
                "hero_image": "images/giso-main-hero.png",
            }
            try:
                from giso.base import cached_giso_config
                name = (cached_giso_config("site_brand_name", "") or "").strip()
                tagline = (cached_giso_config("site_brand_tagline", "") or "").strip()
                logo = (cached_giso_config("site_logo_path", "") or "").strip()
                hero_image = (cached_giso_config("site_hero_image_path", "") or "").strip()
                if name:
                    brand["name"] = name
                if tagline:
                    brand["tagline"] = tagline
                if logo:
                    brand["logo"] = logo
                if hero_image:
                    brand["hero_image"] = hero_image
            except Exception:
                pass
            return brand

        def _get_login_logo():
            """لوگوی اختصاصی صفحهٔ ورود؛ اگر تنظیم نشده باشد، لوگوی برند سایت."""
            try:
                from giso.base import cached_giso_config
                custom = (cached_giso_config("login_logo_path", "") or "").strip()
                return custom or _get_site_brand()["logo"]
            except Exception:
                return "images/logo-96.webp"

        # فاز 4.3+5: تایمر خروج خودکار (زنده از giso_config؛ نقش ادمین/کاربر جدا)
        def _current_panel_role():
            try:
                if not current_user.is_authenticated:
                    return "user"
                phone_norm = normalize_phone(getattr(current_user, "phone", "") or "")
                if _admin_panel_target(phone_norm):
                    return "admin"
                return "user"
            except Exception:
                return "user"

        def _idle_minutes():
            try:
                from giso.panel.modules.settings import idle_minutes_for_role
                return idle_minutes_for_role(_current_panel_role())
            except Exception:
                return 10

        def _get_site_appearance():
            try:
                from giso.panel.modules.settings import get_site_appearance
                return get_site_appearance()
            except Exception:
                return {"phone": "", "bale_id": "", "bale_user": "", "bale_url": "",
                        "instagram": "", "instagram_url": "",
                        "google_site_verification": "", "google_analytics_id": ""}
        from giso.money import format_number_fa, format_toman, to_persian_digits
        return {
            "is_giso_admin_user": _is_giso_admin_user,
            "site_theme": _get_site_theme(),
            "site_brand": _get_site_brand(),
            "login_logo": _get_login_logo(),
            "site_appearance": _get_site_appearance(),
            "idle_minutes": _idle_minutes,
            "fa_number": format_number_fa,
            "fa_digits": to_persian_digits,
            "toman": format_toman,
            "to_shamsi": to_shamsi,
            "display_phone": display_phone,
        }
    from giso.money import format_number_fa as _fn_fa, format_toman as _ft_fa, to_persian_digits as _tp_fa
    app.jinja_env.filters.setdefault("fa_digits", _tp_fa)
    app.jinja_env.filters.setdefault("fa_number", _fn_fa)
    app.jinja_env.filters.setdefault("toman", _ft_fa)

    @app.before_request
    def set_permanent():
        session.permanent = True
        app.permanent_session_lifetime = timedelta(hours=1)

    # فاز 6: کش استاتیک — هدرهای Cache-Control برای فایل‌های static
    # (نسخه‌بندی ?v= روی لینک‌های css/js در قالب‌ها؛ تغییر نسخه → کش شکسته می‌شود)
    @app.after_request
    def giso_static_cache_headers(resp):
        try:
            if (request.path or "").startswith("/static/"):
                resp.headers.setdefault("Cache-Control", "public, max-age=604800")
            else:
                # صفحات پنل‌ها هرگز کش نشوند تا تغییرات UI (از جمله <style> داخلی)
                # با یک رفرس ساده اعمال شوند — رفع مشکل «کش مرورگر» به‌صورت ریشه‌ای
                p = request.path or ""
                if resp.mimetype == "text/html" and (p.startswith("/admin") or p.startswith("/dashboard")):
                    resp.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
                    resp.headers["Pragma"] = "no-cache"
                    resp.headers["Expires"] = "0"
        except Exception:
            pass
        return resp

    # مورد ۱۹ img/help.md: فشرده‌سازی gzip پاسخ‌های متنی (ماژول دامنه‌ای giso/perf.py)
    from giso import perf
    perf.register(app)

    @app.route('/maintenance-access/<token>')
    def giso_maintenance_token_entry(token):
        try:
            from maintenance_access import consume
            consumed = consume('giso',token)
        except Exception as exc:
            # bot.db خراب/در دسترس نیست → لینک معتبر تلقی نشود و سرویس کرش نکند
            logger.warning("maintenance token consume failed: %s", exc)
            consumed = False
        if not _maintenance_flag('giso_maintenance') or not consumed:
            return ('لینک منقضی یا استفاده شده است.',410)
        session['giso_maintenance_entry_until']=int(time.time())+600;session.modified=True
        return redirect(url_for('login'))

    # مسیر خصوصی فقط دروازه ورود هنگام Maintenance است؛ احراز هویت و OTP حذف نمی‌شوند.
    _private_admin_path = (os.getenv("GISO_MAINTENANCE_ADMIN_PATH") or "").strip().strip("/")
    if _private_admin_path and "/" not in _private_admin_path:
        def _maintenance_admin_entry():
            session["giso_maintenance_entry_until"] = int(time.time()) + 600
            session.modified = True
            return redirect(url_for("login"))
        app.add_url_rule(f"/{_private_admin_path}", endpoint="giso_maintenance_admin_entry",
                         view_func=_maintenance_admin_entry, methods=["GET"])

    @app.before_request
    def giso_maintenance_gate():
        try:
            if (request.endpoint or "").startswith("static") or (request.path or "").startswith("/static/"):
                return None
            if not _maintenance_flag("giso_maintenance"):
                return None
            # اگر مسیر خصوصی تنظیم نشده، رفتار سازگار قبلی حفظ می‌شود تا مدیر قفل نشود.
            entry_valid = int(session.get("giso_maintenance_entry_until") or 0) >= int(time.time())
            if request.path.startswith('/maintenance-access/'):
                return None
            if request.path == "/logout":
                return None
            if request.path in ("/login", "/admin/verify") and (entry_valid or not _private_admin_path):
                return None
            if _giso_maintenance_admin_bypass():
                return None
            return render_template("maintenance.html",
                                   maintenance_image_version=_bot_setting_value("giso_maintenance_image_version","0"),
                                   maintenance_until=_maint_resolve_until()), 503
        except Exception:
            return None

    # hook های پس‌زمینه (دایجست/رتبه/broadcast) → giso/site_jobs.py (رفتار یکسان)
    from giso.site_jobs import install_site_background_hooks
    install_site_background_hooks(app)

    # ثبت روت‌های ماژولار (فروش مو، آنالیز، فروشگاه)
    register_hair_sale_routes(app)
    register_analysis_routes(app)
    register_shop_routes(app)
    # بازارچه مو روی همان app/auth/db؛ بدون پنل یا احراز هویت موازی
    from giso.marketplace import marketplace_bp
    app.register_blueprint(marketplace_bp)
    # مراکز زیبایی: ماژول مستقل، همان حساب کاربر و دیتابیس مشترک
    from giso.beauty_centers import beauty_centers_bp
    app.register_blueprint(beauty_centers_bp)
    # نوبتهای آنلاین مراکز زیبایی: ماژول مستقل (همان auth/db) — رزرو، پنل مالک و «نوبت‌های من»
    from giso.beauty_centers.reservations.routes import reservations_bp
    app.register_blueprint(reservations_bp)

    # ═══ فاز 4: پنل ادمین ماژولار ═══
    from giso.panel import panel_bp
    from giso.panel.routes import require_super
    # ═══ فاز 4.3: مرکز پیام و اعلان انبوه (ماژول مستقل؛ قبل از ثبت بلوپرینت) ═══
    from giso.broadcasts_center.routes import register as _bc_register
    _bc_register(panel_bp)
    app.register_blueprint(panel_bp)
    from giso.broadcasts_center import worker as _bc_worker
    _bc_worker.start()
    # ═══ فاز 4.2: پنل کاربر عادی ماژولار ═══
    from giso.panel_user import panel_user_bp
    app.register_blueprint(panel_user_bp)

    @app.route("/")
    def index():
        # فاز P2: آمار واقعی + نظرات تأییدشده (visible) برای صفحه اصلی
        # (آمار با کش ۵ دقیقه‌ای؛ آفست‌ها در هر رندر جدا اعمال می‌شوند)
        home_stats = {"users": 0, "analyses": 0, "orders": 0, "avg_rating": 0.0, "reviews": 0,
                      "hair_sales": 0, "commissions": 0, "satisfaction": 0}
        home_reviews = []
        _now = time.time()
        _cached = _HOME_CACHE.get("home")
        if _cached and (_now - _cached[0]) < 300:
            home_stats, home_reviews = _cached[1][0], _cached[1][1]
        else:
            _compute_home_data(home_stats, home_reviews)
            _HOME_CACHE["home"] = (_now, (home_stats, home_reviews))
        home_stats = dict(home_stats)
        # آفست عددهای نمایشی (قابل تنظیم از ⚙️ تنظیمات سوپرادمین — مبنا همیشه آمار واقعی DB است)
        try:
            from giso.base import cached_giso_config
            def _off(key):
                try:
                    return max(0, int(str(cached_giso_config(key, "0") or "0")))
                except (TypeError, ValueError):
                    return 0

            home_stats["users_display"] = home_stats["users"] + _off("counter_offset_users")
            home_stats["analyses_display"] = home_stats["analyses"] + _off("counter_offset_analyses")
            home_stats["hair_display"] = home_stats["hair_sales"] + _off("counter_offset_hair")
            home_stats["commissions_display"] = home_stats["commissions"] + _off("counter_offset_commissions")
        except Exception:
            home_stats["users_display"] = home_stats["users"]
            home_stats["analyses_display"] = home_stats["analyses"]
            home_stats["hair_display"] = home_stats["hair_sales"]
            home_stats["commissions_display"] = home_stats["commissions"]
        return render_template("index.html", home_stats=home_stats, home_reviews=home_reviews)

    @app.route("/api/ai-widget/init", methods=["GET"])
    def ai_widget_init():
        cfg = get_widget_config()
        role = _resolve_site_ai_role()
        page_path = request.args.get("page", request.path or "/")
        user_name = ""
        phone = ""
        if role != "guest":
            user_name = getattr(current_user, "name", "") or ""
            phone = normalize_phone(getattr(current_user, "phone", "") or "")
        context = build_site_widget_context(role=role, phone=phone, user_name=user_name, page_path=page_path)
        welcome = build_widget_welcome(role=role, user_name=context.get("user_name") or user_name, page_hint=page_path)
        history = _widget_history_get()
        brief = _widget_user_brief(role, phone, user_name)
        context["profile_line"] = brief.get("profile_line", "")
        context["personal_notices"] = brief.get("notices", [])
        # ─── پیام توضیحی ویجت برای صفحات کلیدی (در اولویت: اطلاع شخصی از صفحه مهم‌تر است) ───
        page_notice = ""
        if not brief.get("notice_text"):
            _pp = (page_path or "").split("?")[0]
            # راهنمای کوتاه و صفحه‌محور؛ حباب خودکار باز نمی‌شود و فقط پیام
            # متناسب با همان صفحه را کنار آیکن نشان می‌دهد.
            if _pp.startswith("/hair-sale"):
                page_notice = "برای ارزیابی مو، یک عکس واضح و مشخصات مو را آماده کن. اگر سؤال داری همین‌جا بپرس."
            elif _pp.startswith("/analysis"):
                page_notice = "با یک عکس واضح، آنالیز مو یا پوست را شروع کن. نتیجه جایگزین تشخیص پزشکی نیست."
            elif _pp.startswith("/marketplace"):
                page_notice = "اینجا می‌توانی آگهی‌ها را ببینی، پیشنهاد بدهی و گفت‌وگوها را امن پیگیری کنی."
            elif _pp.startswith("/shop"):
                page_notice = "برای انتخاب محصول یا پیگیری خرید، سؤال کوتاهت را از همراه هوشمند بپرس."
            elif _pp.startswith("/beauty-centers") or _pp.startswith("/dashboard/beauty-center"):
                page_notice = "مرکز را بر اساس خدمت و منطقه بررسی کن؛ قیمت و شرایط را پیش از مراجعه مستقیم بپرس."
            elif _pp.startswith("/dashboard/wallet"):
                page_notice = "موجودی نقدی و اعتبار مصرفی جدا هستند؛ برای توضیح هرکدام از من بپرس."
            elif _pp.startswith("/dashboard"):
                page_notice = "در پنل می‌توانی وضعیت درخواست‌ها، سفارش‌ها و پیام‌های جدیدت را یک‌جا ببینی."
            else:
                page_notice = "من همراه هوشمند گیسو هستم؛ سؤال کوتاهت را بپرس تا همین بخش را توضیح بدهم."
        role_hint = ""
        try:
            if role == "user" and current_user and current_user.is_authenticated:
                _phone_n = normalize_phone(getattr(current_user, "phone", "") or "")
                if _admin_panel_target(_phone_n):
                    role_hint = "admin_unverified"
        except Exception:
            role_hint = ""
        return jsonify({
            "ok": True,
            "enabled": bool(cfg["enabled"]),
            "position": cfg["position"],
            "primary_color": cfg["primary_color"],
            "display_name": get_display_name(),
            "role": role,
            "role_hint": role_hint,
            "welcome": welcome,
            "history": history,
            "notice_text": brief.get("notice_text", "") or page_notice,
            "notices": brief.get("notices", []),
            "brief_counts": brief.get("counts", {}),
            "staff_report": brief.get("staff_report", ""),
            "summary": context.get("summary", ""),
            # چیپ سؤال/پیشنهاد و امتیازدهی از UI حذف شده‌اند؛ فقط راهنمای صفحه می‌ماند.
            "actions": [],
            "state": context.get("state", ""),
            "state_label": context.get("state_label", ""),
            "focus": context.get("focus", ""),
            "focus_label": context.get("focus_label", ""),
            "page_title": context.get("page_title", ""),
            "input_placeholder": context.get("input_placeholder", ""),
            "csrf_token": _widget_csrf_token(),
        })

    @app.route("/api/ai-widget/feedback", methods=["POST"])
    def ai_widget_feedback():
        cfg = get_widget_config()
        if not cfg["enabled"]:
            return jsonify({"ok": False, "error": "ویجت غیرفعال است."}), 503
        data = request.get_json(silent=True) or {}
        sent_token = (request.headers.get("X-AI-Widget-CSRF") or data.get("csrf_token") or "").strip()
        if not sent_token or sent_token != _widget_csrf_token():
            return jsonify({"ok": False, "error": "درخواست نامعتبر است."}), 403
        try:
            rating = int(data.get("rating") or 0)
        except (TypeError, ValueError):
            rating = 0
        if rating not in (1, -1):
            return jsonify({"ok": False, "error": "امتیاز نامعتبر است."}), 400
        try:
            role = _resolve_site_ai_role()
            with get_giso_db_conn() as conn:
                conn.execute(
                    "INSERT INTO giso_widget_feedback (actor_key, rating, page_path, created_at) VALUES (?,?,?,datetime('now','localtime'))",
                    (_widget_actor_key(role), rating, str(data.get("page") or "/")[:200]),
                )
                conn.commit()
        except Exception:
            pass
        return jsonify({"ok": True})

    @app.route("/api/ai-widget/chat", methods=["POST"])
    def ai_widget_chat():
        cfg = get_widget_config()
        if not cfg["enabled"]:
            return jsonify({"ok": False, "error": "مشاور هوشمند سایت فعلاً غیرفعال است."}), 503
        data = request.get_json(silent=True) or {}
        sent_token = (request.headers.get("X-AI-Widget-CSRF") or data.get("csrf_token") or "").strip()
        if not sent_token or sent_token != _widget_csrf_token():
            return jsonify({"ok": False, "error": "درخواست نامعتبر است."}), 403
        user_message = (data.get("message") or "").strip()
        page_path = request.args.get("page") or data.get("page") or "/"
        if not user_message:
            return jsonify({"ok": False, "error": "پیام خالی است."}), 400
        role = _resolve_site_ai_role()
        phone = normalize_phone(getattr(current_user, "phone", "") or "") if role != "guest" else ""
        user_name = getattr(current_user, "name", "") or "" if role != "guest" else ""
        context = build_site_widget_context(role=role, phone=phone, user_name=user_name, page_path=page_path, user_message=user_message)
        credit_request_key = ""
        credit_state = {}
        if role in ("guest", "user"):
            import uuid
            from giso.ai_credits import reserve_ai_credit
            credit_request_key = uuid.uuid4().hex
            credit_ok, credit_message, credit_state = reserve_ai_credit(phone, credit_request_key, channel="site_widget")
            if not credit_ok:
                return jsonify({"ok": False, "error": credit_message, "ai_credit": credit_state}), 402
        history = _widget_history_get()
        brief = _widget_user_brief(role, phone, user_name)
        context["profile_line"] = brief.get("profile_line", "")
        context["personal_notices"] = brief.get("notices", [])
        # ادمین/سوپرادمین تأییدشده: دستورهای گزارش‌گیری مستقیم از دیتابیس جواب می‌گیرند (بدون AI)
        staff_direct = _widget_staff_report(user_message) if role in ("admin", "super") else None
        if staff_direct:
            result = {"ok": True, "text": staff_direct, "provider": "staff-direct", "model": "deterministic-report"}
        else:
            messages = build_site_widget_prompt(role=role, context=context, user_message=user_message, history=history)
            role_for_runtime = role if role in ("user", "admin", "super") else "user"
            from giso.async_compat import run_async_safe
            result = run_async_safe(chat_with_managed_ai(
                messages,
                actor_key=_widget_actor_key(role),
                role=role_for_runtime,
                channel=f"site_widget|{page_path}",
                section="consultant_chat",
                question_text=user_message,
                action="widget_chat",
                max_tokens=700,
            ))
        fallback_mode = False
        response_text = result.get("text") or ""
        provider_name = result.get("provider") or ""
        model_name = result.get("model") or ""
        if not result.get("ok"):
            reason = str(result.get("reason") or "")
            if reason in ("provider_error", "daily_limit", "empty_answer"):
                response_text = build_site_widget_fallback_reply(role=role, context=context, user_message=user_message, reason=reason)
                provider_name = "runtime-fallback"
                model_name = f"deterministic-{reason or 'fallback'}"
                fallback_mode = True
            else:
                if credit_request_key:
                    from giso.ai_credits import refund_ai_credit
                    refund_ai_credit(phone, credit_request_key, channel="site_widget")
                return jsonify({"ok": False, "error": result.get("text") or result.get("error") or "خطا در پاسخ"}), 429 if result.get("reason") == "daily_limit" else 503
        if fallback_mode and credit_request_key:
            from giso.ai_credits import refund_ai_credit, get_ai_credit
            refund_ai_credit(phone, credit_request_key, channel="site_widget")
            credit_state = get_ai_credit(phone, create=False) if phone else credit_state
        # مورد ۱۱ help2: خط کوچک نرخ/مصرف/مانده فقط وقتی کسر اعتبار فعال است
        credit_line = None
        if role in ("guest", "user") and phone:
            from giso.ai_credits import credit_settings as _cs_fn, get_ai_credit as _gc_fn
            _cs = _cs_fn()
            if _cs.get("enabled"):
                _st = _gc_fn(phone, create=False)
                credit_line = {"cost": _cs["cost"], "balance": _st["balance"], "used": _st["total_used"]}
        history.append({"role": "user", "content": user_message})
        history.append({"role": "assistant", "content": response_text})
        _widget_history_set(history)
        _widget_log_chat(role, phone, user_name, page_path, user_message, response_text)
        return jsonify({
            "ok": True,
            "response": response_text,
            "display_name": get_display_name(),
            "history": history[-12:],
            "provider": provider_name,
            "model": model_name,
            "fallback_used": bool(result.get("fallback_used")) or fallback_mode,
            "ai_credit": credit_line,
            "ai_credit": credit_state,
            "notice_text": brief.get("notice_text", ""),
            "summary": context.get("summary", ""),
            "actions": [],
            "state": context.get("state", ""),
            "state_label": context.get("state_label", ""),
            "focus": context.get("focus", ""),
            "focus_label": context.get("focus_label", ""),
            "page_title": context.get("page_title", ""),
            "input_placeholder": context.get("input_placeholder", ""),
        })

    @app.route("/api/ux-events", methods=["POST"])
    def ux_events_api():
        data=request.get_json(silent=True) or {}
        try:
            from giso.monitoring_events import record_batch
            actor_type='user' if current_user.is_authenticated else 'guest'
            actor_id=str(getattr(current_user,'id','') or session.get('ai_widget_guest_id') or '')
            count=record_batch(data.get('events'),actor_type,actor_id)
            return jsonify({'ok':True,'accepted':count})
        except Exception:
            return jsonify({'ok':False}),503

    @app.route("/api/notifications/poll", methods=["GET"])
    def notifications_poll():
        """endpoint سبک Bell/Toast سایت: ۵ اعلان آخر کاربر لاگین‌شده + تعداد خوانده‌نشده.

        - مهمان: payload خالی (بدون ۴۰ تا JS ساده بماند).
        - اعلان‌های اختصاصی کاربر تا ۷ روز نگهداری و سپس توسط
          list_user_notifications پاک می‌شوند.
        """
        if not getattr(current_user, "is_authenticated", False):
            return jsonify({"ok": True, "unread": 0, "items": []})
        phone = normalize_phone(getattr(current_user, "phone", "") or "")
        try:
            from giso.panel.modules.notifications import list_user_notifications, user_unread_count
            items = list_user_notifications(phone, limit=5)
            unread = user_unread_count(phone)
        except Exception:
            items, unread = [], 0
        _icons = {"shop": "🛍", "hair_sale": "💇", "marketplace": "🏪", "beauty_centers": "🏥",
                  "wallet": "💰", "analysis": "🔬", "bot": "🤖"}
        out = []
        for n in items:
            cat = n.get("category", "")
            try:
                if cat == "marketplace":
                    url = url_for("panel_user.marketplace")
                elif cat == "beauty_centers":
                    url = url_for("beauty_centers.owner_dashboard")
                else:
                    url = url_for("panel_user.notifications")
            except Exception:
                url = ""
            out.append({
                "id": n.get("id"),
                "title": n.get("title", ""),
                "message": (n.get("message") or "")[:200],
                "category": cat,
                "unread": n.get("status") == "unread",
                "created_at": n.get("created_at", ""),
                "url": url,
                "icon": _icons.get(cat, "🔔"),
            })
        return jsonify({"ok": True, "unread": unread, "items": out})

    @app.route("/admin/verify", methods=["GET", "POST"])
    @login_required
    def admin_verify():
        phone_norm = normalize_phone(getattr(current_user, "phone", "") or "")
        target = _admin_panel_target(phone_norm)
        if not target:
            flash("این حساب دسترسی به پنل مدیریت ندارد.", "danger")
            return redirect(url_for("index"))
        if _admin_panel_is_verified(phone_norm):
            return redirect(session.pop("admin_panel_next", None) or url_for("admin_dashboard"))

        status = _admin_panel_current_stepup_status(phone_norm)
        info_message = ""
        if request.method == "POST":
            action = (request.form.get("action") or "verify").strip().lower()
            if action == "resend":
                ok, msg = _admin_panel_issue_code(phone_norm, force=True)
                status = _admin_panel_current_stepup_status(phone_norm)
                if ok:
                    info_message = msg
                else:
                    flash(msg, "warning")
            else:
                code = (request.form.get("code") or "").strip()
                ok, msg = _admin_panel_verify_code(phone_norm, code)
                status = _admin_panel_current_stepup_status(phone_norm)
                if ok:
                    try:
                        from giso.panel.modules.notifications import safe_log as _nlog
                        _nlog("security", "step_up", "ورود دومرحله‌ای (step-up)",
                              f"{phone_norm}", source_type="admin_step_up",
                              source_id=0)
                    except Exception:
                        pass
                    flash(msg, "success")
                    return redirect(session.pop("admin_panel_next", None) or url_for("admin_dashboard"))
                flash(msg, "danger")
        elif not status.get("pending"):
            ok, msg = _admin_panel_issue_code(phone_norm)
            status = _admin_panel_current_stepup_status(phone_norm)
            if ok:
                info_message = msg
            else:
                flash(msg, "warning")

        return render_template(
            "admin_verify.html",
            target_role=("سوپرادمین" if target.get("role") == "super" else "ادمین"),
            phone=phone_norm,
            info_message=info_message,
            code_pending=bool(status.get("pending")),
            expires_in=int(status.get("expires_in") or 0),
            attempts_left=int(status.get("attempts_left") or 0),
            resend_in=int(status.get("resend_in") or 0),
        )

    @app.route("/login", methods=["GET", "POST"])
    def login():
        if current_user.is_authenticated:
            return redirect(url_for("index"))
        if request.method == "POST":
            phone = normalize_phone(request.form.get("phone", ""))
            password = request.form.get("password", "")
            if not phone:
                flash("شماره موبایل نامعتبر است.", "danger")
                return render_template("login.html")
            # محافظت سه‌مرحله‌ای از brute-force: ۳ شکست -> ۵ دقیقه | ۶ -> ۱۰ دقیقه | ۱۰ -> ۱ ساعت
            from giso.security import (login_lock_status, login_failed, login_succeeded,
                                       login_failed_message, login_lockout_message)
            lock = login_lock_status(phone)
            if lock["locked"]:
                flash(login_lockout_message(lock["remaining"]), "danger")
                return render_template("login.html")
            user = User.query.filter_by(phone=phone).first()
            if not user or not check_password_hash(user.password_hash, password):
                try:
                    from giso.login_history import record
                    record(phone,int(getattr(user,'id',0) or 0),False,request,'رمز یا حساب نامعتبر')
                except Exception:pass
                flash(login_failed_message(login_failed(phone)), "danger")
                return render_template("login.html")
            # فاز 4.5: کاربر بن‌شده نمی‌تواند لاگین کند
            if getattr(user, "is_banned", 0):
                flash("حساب شما موقتاً مسدود شده است. با پشتیبانی تماس بگیرید.", "danger")
                return render_template("login.html")
            _admin_panel_clear_state(clear_verified=True)
            _sensitive_register_clear_state()
            login_succeeded(phone)  # پاک‌کردن شمارنده‌ی تلاش‌های ناموفق
            login_user(user, remember=False, duration=timedelta(hours=1))
            try:
                from giso.login_history import record
                record(phone,user.id,True,request)
            except Exception:pass
            user.touch_login()
            flash("خوش آمدید به گیسو!", "success")
            # فاز طراحی: redirect نقش‌محور — ادمین/سوپر → پنل مدیریت؛ کاربر عادی → داشبورد
            try:
                _t = _admin_panel_target(normalize_phone(user.phone or ""))
                if _t:
                    if _t.get("role") == "super":
                        try:
                            from giso.panel.modules.notifications import safe_log as _nlog
                            _nlog("security", "super_login", "ورود سوپرادمین",
                                  f"{user.phone}", source_type="super_login",
                                  source_id=getattr(user, "id", 0) or 0)
                        except Exception:
                            pass
                    return redirect(url_for("panel.dashboard"))
                # فاز جامع خرید: بازگشت به همان محصول/سبد بعد از ورود (?next= مسیر نسبی داخلی)
                _next = (request.args.get("next") or "").strip()
                if _next.startswith("/") and not _next.startswith("//"):
                    return redirect(_next)
                return redirect(url_for("dashboard"))
            except Exception:
                return redirect(url_for("index"))
        return render_template("login.html")

    @app.route("/forgot-password", methods=["GET", "POST"])
    def forgot_password():
        if current_user.is_authenticated:
            return redirect(url_for("index"))
        if request.method == "POST":
            step = request.form.get("step", "phone")
            if step == "phone":
                phone = normalize_phone(request.form.get("phone", ""))
                if not phone:
                    flash("شماره موبایل نامعتبر است.", "danger")
                    return render_template("forgot_password.html", step="phone", phone="")
                user = User.query.filter_by(phone=phone).first()
                if not user:
                    flash("کاربری با این شماره در سیستم یافت نشد.", "danger")
                    return render_template("forgot_password.html", step="phone", phone="")
                session["fp_phone"] = phone
                session.pop("fp_answer_ok", None)
                session.pop("fp_bot_verified", None)
                return render_template("forgot_password.html", step="answer",
                                       security_question=user.security_question or "")
            if step == "answer":
                phone = session.get("fp_phone", "")
                user = User.query.filter_by(phone=phone).first() if phone else None
                if not user:
                    return redirect(url_for("forgot_password"))
                if not (user.security_answer or "").strip():
                    flash("برای این حساب سوال امنیتی ثبت نشده است.", "danger")
                    return render_template("forgot_password.html", step="answer",
                                           security_question=user.security_question or "")
                answer = request.form.get("security_answer", "").strip()
                if (user.security_answer or "").strip().lower() != answer.strip().lower():
                    flash("پاسخ سوال امنیتی اشتباه است.", "danger")
                    return render_template("forgot_password.html", step="answer",
                                           security_question=user.security_question or "")
                session["fp_answer_ok"] = True
                if _sensitive_register_requires_bot_code(phone):
                    ok, msg = _sensitive_register_issue_code(phone, force=True)
                    if not ok:
                        flash(msg, "warning")
                    return render_template("forgot_password.html", step="bot", info_message=msg if ok else "", **_sensitive_register_status(phone))
                session["fp_verified"] = True
                return render_template("forgot_password.html", step="password")
            if step == "bot":
                phone = session.get("fp_phone", "")
                if not session.get("fp_answer_ok") or not phone:
                    return redirect(url_for("forgot_password"))
                action = (request.form.get("action") or "verify").strip().lower()
                if action == "resend":
                    ok, msg = _sensitive_register_issue_code(phone, force=True)
                    if not ok:
                        flash(msg, "warning")
                    return render_template("forgot_password.html", step="bot", info_message=msg if ok else "", **_sensitive_register_status(phone))
                code = (request.form.get("bot_code") or "").strip()
                ok, msg = _sensitive_register_verify_code(phone, code)
                if not ok:
                    flash(msg, "danger")
                    return render_template("forgot_password.html", step="bot", info_message="", **_sensitive_register_status(phone))
                session["fp_bot_verified"] = True
                session["fp_verified"] = True
                return render_template("forgot_password.html", step="password")
            if step == "password":
                phone = session.get("fp_phone", "")
                if not session.get("fp_verified"):
                    return redirect(url_for("forgot_password"))
                if _sensitive_register_requires_bot_code(phone) and not session.get("fp_bot_verified"):
                    return redirect(url_for("forgot_password"))
                user = User.query.filter_by(phone=phone).first() if phone else None
                newp = request.form.get("password", "")
                newp2 = request.form.get("password2", "")
                _ok, _msg = validate_new_password(newp)
                if not _ok:
                    flash(_msg, "danger")
                    return render_template("forgot_password.html", step="password")
                if newp != newp2:
                    flash("رمزها مطابقت ندارند.", "danger")
                    return render_template("forgot_password.html", step="password")
                if not user:
                    session.pop("fp_phone", None)
                    session.pop("fp_verified", None)
                    session.pop("fp_answer_ok", None)
                    session.pop("fp_bot_verified", None)
                    return redirect(url_for("forgot_password"))
                try:
                    user.password_hash = generate_password_hash(newp, method="pbkdf2:sha256")
                    db.session.commit()
                    try:
                        from giso.account_password_vault import remember_account_password
                        remember_account_password(user.id, newp)
                    except Exception:
                        pass
                    session.pop("fp_phone", None)
                    session.pop("fp_verified", None)
                    session.pop("fp_answer_ok", None)
                    session.pop("fp_bot_verified", None)
                    flash("رمز عبور شما با موفقیت تغییر کرد. اکنون وارد شوید.", "success")
                    return redirect(url_for("login"))
                except Exception:
                    try:
                        db.session.rollback()
                    except Exception:
                        pass
                    flash("خطا در تغییر رمز عبور. لطفاً دوباره تلاش کنید.", "danger")
                    return render_template("forgot_password.html", step="password")
            return redirect(url_for("forgot_password"))
        return render_template("forgot_password.html", step="phone", phone="")

    @app.route("/register", methods=["GET", "POST"])
    def register():
        if current_user.is_authenticated:
            return redirect(url_for("index"))
        # فاز 4.3: اگر ثبت‌نام سایت غیرفعال شده باشد (سوپرادمین از پنل)، مسدود کن
        try:
            from giso.panel.modules.settings import is_registration_enabled
            if not is_registration_enabled():
                if request.method == "POST":
                    flash("ثبت‌نام جدید در حال حاضر غیرفعال است. لطفاً بعداً مراجعه کنید.", "warning")
                return render_template("register.html", phone="", security_question="",
                                       require_bot_code=False, info_message="",
                                       referral_code="", referral_hint="",
                                       code_pending=False, expires_in=0,
                                       attempts_left=5, resend_in=0)
        except Exception:
            pass
        if request.method == "POST":
            action = (request.form.get("action") or "register").strip().lower()
            phone = normalize_phone(request.form.get("phone", ""))
            password = request.form.get("password", "")
            password2 = request.form.get("password2", "")
            sq = request.form.get("security_question", "").strip()
            sa = request.form.get("security_answer", "").strip()
            bot_code = (request.form.get("bot_code") or "").strip()
            # برنامه معرفی متوقف شده است؛ فیلدهای تاریخی دیتابیس فقط برای ممیزی حفظ می‌شوند.
            referral_code = ""
            if not phone:
                flash("شماره موبایل نامعتبر است.", "danger")
                return _render_register_view(phone=phone, security_question=sq, referral_code=referral_code)

            # Smart register: اگر شماره قبلاً در giso_web_auth ثبت شده، به‌جای ادامه‌ی
            # فرم، مستقیم به صفحه‌ی ورود هدایت می‌شود (فقط برای ثبت‌نام عادی؛
            # جریان کد حساس سوپرادمین دست‌نخورده می‌ماند).
            if action == "register" and User.query.filter_by(phone=phone).first():
                flash("شما قبلاً ثبت‌نام کرده‌اید، لطفاً وارد شوید", "warning")
                return redirect(url_for("login"))

            if action == "resend_sensitive_code":
                ok, msg = _sensitive_register_issue_code(phone, force=True)
                if not ok:
                    flash(msg, "warning")
                    return _render_register_view(phone=phone, security_question=sq, require_bot_code=True, referral_code=referral_code)
                return _render_register_view(phone=phone, security_question=sq, require_bot_code=True, info_message=msg, referral_code=referral_code)

            if request.form.get("site_terms_accepted") != "1":
                flash("مطالعه و پذیرش قوانین عمومی سایت برای ثبت‌نام الزامی است.", "warning")
                return _render_register_view(
                    phone=phone, security_question=sq,
                    require_bot_code=(action == "verify_sensitive"),
                    referral_code=referral_code,
                )

            if not sq:
                flash("لطفاً سوال امنیتی را انتخاب کن.", "danger")
                return _render_register_view(phone=phone, security_question=sq, referral_code=referral_code)
            if not sa:
                flash("پاسخ سوال امنیتی را وارد کن.", "danger")
                return _render_register_view(phone=phone, security_question=sq, referral_code=referral_code)
            _ok, _msg = validate_new_password(password)
            if not _ok:
                flash(_msg, "danger")
                return _render_register_view(phone=phone, security_question=sq, require_bot_code=(action != "register"), referral_code=referral_code)
            if password != password2:
                flash("رمزها مطابقت ندارند.", "danger")
                return _render_register_view(phone=phone, security_question=sq, require_bot_code=(action != "register"), referral_code=referral_code)
            if User.query.filter_by(phone=phone).first():
                flash("این شماره قبلاً ثبت شده است.", "warning")
                return redirect(url_for("login"))

            sensitive_target = _admin_panel_target(phone)

            if sensitive_target:
                if action != "verify_sensitive":
                    ok, msg = _sensitive_register_issue_code(phone)
                    if not ok:
                        flash(msg, "warning")
                        return _render_register_view(phone=phone, security_question=sq, require_bot_code=True, referral_code=referral_code)
                    return _render_register_view(phone=phone, security_question=sq, require_bot_code=True, info_message=msg, referral_code=referral_code)
                ok, msg = _sensitive_register_verify_code(phone, bot_code)
                if not ok:
                    flash(msg, "danger")
                    return _render_register_view(phone=phone, security_question=sq, require_bot_code=True, referral_code=referral_code)

            user = User(phone=phone,
                        password_hash=generate_password_hash(password, method="pbkdf2:sha256"),
                        security_question=sq, security_answer=sa.strip().lower())
            db.session.add(user)
            db.session.commit()
            try:
                from giso.account_password_vault import remember_account_password
                remember_account_password(user.id, password)
            except Exception:
                pass
            try:
                from giso.wallet import complete_mission
                complete_mission(user.id, "registration", event_key=f"user:{user.id}")
            except Exception as mission_exc:
                logger.warning(f"registration mission failed: {mission_exc}")
            _admin_panel_clear_state(clear_verified=True)
            _sensitive_register_clear_state()
            login_user(user, remember=False, duration=timedelta(hours=1))
            flash("ثبت‌نام با موفقیت انجام شد.", "success")
            try:
                from giso.panel.modules.notifications import safe_log as _nlog
                _nlog("users", "register", "ثبت‌نام کاربر", f"{phone}",
                      source_type="user_register", source_id=user.id)
            except Exception:
                pass
            # فاز جامع خرید: بازگشت به همان محصول/سبد بعد از عضویت (?next= مسیر نسبی داخلی)
            _next = (request.args.get("next") or "").strip()
            if _next.startswith("/") and not _next.startswith("//"):
                return redirect(_next)
            return redirect(url_for("index"))

        pending_phone = normalize_phone(session.get("sreg_phone", "") or "")
        require_bot_code = bool(pending_phone)
        security_question = ""
        info_message = ""
        # پارامترهای قدیمی ?ref برای سازگاری لینک‌ها نادیده گرفته می‌شوند؛
        # رابطه یا کد معرفی جدید ساخته نمی‌شود.
        referral_code = ""
        referral_hint = ""
        if require_bot_code:
            info_message = "برای تکمیل ثبت‌نام این شماره، کد تأییدی که به ربات ارسال شده را وارد کن."
        return _render_register_view(phone=pending_phone, security_question=security_question,
                                     require_bot_code=require_bot_code, info_message=info_message,
                                     referral_code=referral_code, referral_hint=referral_hint)

    @app.route("/logout")
    @login_required
    def logout():
        _admin_panel_clear_state(clear_verified=True)
        _sensitive_register_clear_state()
        idle_reason = (request.args.get("reason") or "").strip()
        logout_user()
        if idle_reason == "idle":
            flash("به دلیل چند دقیقه عدم فعالیت، برای امنیت از حسابت خارج شدی. دوباره وارد شو 🌸", "warning")
        return redirect(url_for("index"))

    @app.route("/dashboard")
    @login_required
    def dashboard():
        # فاز طراحی: ادمین/سوپرادمین هرگز نباید /dashboard ببینند → پنل مدیریت
        try:
            phone_norm = normalize_phone(getattr(current_user, "phone", "") or "")
            if _admin_panel_target(phone_norm):
                return redirect(url_for("panel.dashboard"))
        except Exception:
            pass
        # فاز 4.2 + فاز 6: کاربر عادی همیشه به پنل کاربر ماژولار جدید هدایت می‌شود
        # (نمای قدیمی dashboard.html و fallback ?legacy=1 حذف شدند)
        return redirect(url_for("panel_user.overview"))

    @app.route("/dashboard/review", methods=["POST"])
    @login_required
    def submit_review():
        try:
            review_type = request.form.get("review_type", "shop_order").strip()
            if review_type not in ("shop_order", "hair_order"):
                review_type = "shop_order"
            try:
                order_id = int(request.form.get("order_id", 0) or 0)
            except ValueError:
                order_id = 0
            try:
                rating = int(request.form.get("rating", 5) or 5)
            except ValueError:
                rating = 5
            rating = max(1, min(5, rating))
            comment = request.form.get("comment", "").strip()

            if order_id <= 0:
                flash("لطفاً شماره سفارش معتبر انتخاب یا وارد کنید.", "danger")
                return redirect(url_for("dashboard"))

            # E2 fix: چک تملک سفارش پیش از INSERT (دو فضای شماره جدا؛ مطابق پنل کاربر).
            if review_type == "hair_order":
                hair = HairOrder.query.filter_by(id=order_id).first()
                owns_hair = hair is not None and (
                    int(hair.user_id or 0) == int(current_user.id)
                    or (hair.phone and hair.phone == current_user.phone)
                )
                if not owns_hair:
                    return "شما مجاز به ثبت نظر برای این درخواست نیستید.", 403
            else:
                order = ProductOrder.query.filter_by(id=order_id).first()
                if order is None or int(order.user_id or 0) != int(current_user.id):
                    return "شما مجاز به ثبت نظر برای این سفارش نیستید.", 403
            # E2 fix: یکتایی نظر (review_type, order_id) — جلوگیری از نظر تکراری قبل از INSERT.
            if Review.query.filter_by(review_type=review_type, order_id=order_id).first() is not None:
                return "نظر برای این سفارش قبلاً ثبت شده است.", 409

            rev = Review(
                user_id=current_user.id,
                phone=current_user.phone,
                review_type=review_type,
                order_id=order_id,
                rating=rating,
                comment=comment
            )
            db.session.add(rev)
            db.session.commit()
            flash("نظر و رضایت شما با موفقیت ثبت شد. از همراهی شما سپاسگزاریم 🌸", "success")
        except Exception:
            try:
                db.session.rollback()
            except Exception:
                pass
            flash("خطا در ثبت نظر. لطفاً دوباره تلاش کنید.", "danger")
        return redirect(url_for("dashboard"))

    @app.route("/my")
    @login_required
    def my_alias():
        """نام مستعار /my — فقط ریدایرکت به آدرس اصلی پنل کاربری (/dashboard)."""
        return redirect(url_for("dashboard"))

    @app.route("/dashboard/profile/update", methods=["POST"])
    @login_required
    def dashboard_profile_update():
        """ویرایش پروفایل مشترک سایت و ربات با whitelist مرکزی."""
        from giso.user_profile_service import PROFILE_FIELDS, update_user_profile
        # فرم پروفایل همه‌ی فیلدهای whitelist مرکزی را می‌فرستد؛ سرویس هم قفل
        # ۱۵ روزه و محدودیت طول هر فیلد را اعمال می‌کند.
        values = {
            field: request.form.get(field, "")
            for field in PROFILE_FIELDS
        }
        ok, message, profile = update_user_profile(current_user.phone, values, actor="site")
        if ok and profile.get("first_name") and profile.get("last_name"):
            try:
                from giso.wallet import complete_mission
                complete_mission(current_user.id, "profile_complete", event_key=f"profile:{current_user.id}")
            except Exception as mission_exc:
                logger.warning(f"profile mission failed: {mission_exc}")
        flash((message + " 🌸") if ok else message, "success" if ok else "danger")
        return redirect(url_for("panel_user.profile"))

    @app.route("/dashboard/password/change", methods=["POST"])
    @login_required
    def dashboard_password_change():
        """تغییر رمز عبور از داخل پنل کاربری (با تأیید رمز فعلی)."""
        cur = request.form.get("current_password", "") or ""
        from giso.security import rate_limit
        allowed,retry=rate_limit("dashboard_password_change",5,3600,identifier=getattr(current_user,"id",current_user.phone))
        if not allowed:
            flash(f"تعداد تلاش‌ها زیاد است؛ {retry} ثانیه دیگر دوباره تلاش کنید.","warning")
            return redirect(url_for("panel_user.profile"))
        newp = request.form.get("new_password", "") or ""
        newp2 = request.form.get("new_password2", "") or ""
        try:
            u = User.query.filter_by(phone=current_user.phone).first()
            if not u:
                flash("حساب کاربری یافت نشد. دوباره وارد شوید.", "danger")
                return redirect(url_for("login"))
            if not check_password_hash(u.password_hash, cur):
                flash("رمز فعلی اشتباه است.", "danger")
                return redirect(url_for("panel_user.profile"))
            _ok, _msg = validate_new_password(newp)
            if not _ok:
                flash(_msg, "danger")
                return redirect(url_for("panel_user.profile"))
            if newp != newp2:
                flash("تکرار رمز جدید با رمز مطابقت ندارد.", "danger")
                return redirect(url_for("panel_user.profile"))
            if check_password_hash(u.password_hash,newp):
                flash("رمز جدید باید با رمز فعلی متفاوت باشد.","warning")
                return redirect(url_for("panel_user.profile"))
            u.password_hash = generate_password_hash(newp, method="pbkdf2:sha256")
            db.session.commit()
            try:
                from giso.panel.modules.users import _clear_visible_pass
                _clear_visible_pass(u.id)
            except Exception:
                pass
            try:
                from giso.panel.modules.notifications import log_user_notification
                log_user_notification(u.phone,"security","تغییر رمز عبور","رمز حساب شما از پنل کاربری تغییر کرد.",source_type="password_change",source_id=int(time.time()),category="security")
            except Exception: pass
            audit_event("password_change","success",target=str(u.id))
            flash("رمز عبور با موفقیت تغییر کرد 🔒", "success")
        except Exception:
            try:
                db.session.rollback()
            except Exception:
                pass
            flash("خطا در تغییر رمز عبور. دوباره تلاش کنید.", "danger")
        return redirect(url_for("panel_user.profile"))

    @app.route("/dashboard/wallet/withdraw", methods=["POST"])
    @login_required
    def wallet_withdraw():
        """ثبت درخواست تسویه کیف پول توسط کاربر."""
        uid = getattr(current_user, "id", None)
        if not uid:
            flash("حساب کاربری معتبر نیست.", "danger")
            return redirect(url_for("dashboard"))
        amount = request.form.get("amount", "")
        holder = request.form.get("card_holder_name", "")
        sheba = request.form.get("sheba", "")
        card = request.form.get("card_number", "")
        try:
            from giso.referrals import create_withdrawal_request
            ok, msg, _wid = create_withdrawal_request(uid, amount, holder, sheba, card)
            flash(msg, "success" if ok else "danger")
        except Exception as e:
            logger.error(f"wallet_withdraw: {e}")
            flash("خطا در ثبت درخواست تسویه.", "danger")
        return redirect(url_for("panel_user.wallet", tab="settlement"))

    # ─────────────── مدیریت وب: معرفی‌ها و تسویه‌ها (فاز ۳) ───────────────
    @app.route("/admin/referrals")
    @login_required
    def admin_referrals():
        """مسیر legacy معرفی‌ها؛ canonical اکنون پنل ماژولار است."""
        return redirect(url_for("panel.referrals"))
        if _r := _check_giso_admin_access():
            return _r
        from giso.referrals import list_referrals, get_referral_stats, get_referral_settings
        referrals = []
        stats = {}
        settings = {}
        try:
            referrals = list_referrals(limit=200)
        except Exception:
            pass
        try:
            stats = get_referral_stats()
        except Exception:
            pass
        try:
            settings = get_referral_settings()
        except Exception:
            pass
        phone_norm = normalize_phone(getattr(current_user, "phone", "") or "")
        target = _admin_panel_target(phone_norm) or {}
        is_super = target.get("role") == "super"
        return render_template("admin_referrals.html",
                               referrals=referrals, stats=stats, settings=settings,
                               is_super=is_super)

    @app.route("/admin/referral/settings", methods=["POST"])
    @login_required
    @require_super
    def admin_referral_settings():
        """مسیر سازگاری: برنامه معرفی متوقف است و تنظیم جدید پذیرفته نمی‌شود."""
        guard = _admin_guard()
        if guard:
            return guard
        if _r := _check_giso_admin_access():
            return _r
        flash("برنامه معرفی و پورسانت متوقف شده است؛ سوابق تاریخی فقط برای ممیزی حفظ می‌شوند.", "info")
        return redirect(url_for("panel.wallet"))

    # ═══ فاز 3.4: مدیریت ادمین‌ها در سایت (فقط سوپرادمین) ═══
    @app.route("/admin/admins")
    @login_required
    def admin_admins():
        """مسیر legacy ادمین‌ها؛ canonical اکنون پنل ماژولار است."""
        return redirect(url_for("panel.admins"))

    @app.route("/admin/admins/<int:admin_row_id>/permission", methods=["POST"])
    @login_required
    def admin_admins_permission(admin_row_id):
        """Fail closed for forms cached before permission configuration removal."""
        if _r := _check_giso_admin_access():
            return _r
        phone_norm = normalize_phone(getattr(current_user, "phone", "") or "")
        target = _admin_panel_target(phone_norm) or {}
        if target.get("role") != "super":
            flash("فقط سوپرادمین می‌تواند ادمین‌ها را مدیریت کند.", "warning")
            return redirect(url_for("panel.dashboard"))
        flash("این تنظیمات ساده‌سازی شده است", "info")
        return redirect(url_for("panel.admins"))

    # ═══ فاز 3.5: مدیریت کامل کاربران در سایت (فقط سوپرادمین) ═══
    @app.route("/admin/users/manage")
    @login_required
    def admin_users_manage():
        """مسیر legacy کاربران؛ canonical اکنون پنل ماژولار است."""
        return redirect(url_for("panel.users"))
        if _r := _check_giso_admin_access():
            return _r
        phone_norm = normalize_phone(getattr(current_user, "phone", "") or "")
        target = _admin_panel_target(phone_norm) or {}
        if target.get("role") != "super":
            flash("فقط سوپرادمین می‌تواند کاربران را مدیریت کند.", "warning")
            return redirect(url_for("admin_dashboard"))
        q = (request.args.get("q") or "").strip()
        users = []
        if q:
            try:
                qn = normalize_phone(q)
                from sqlalchemy import or_
                query = User.query
                conds = []
                if qn:
                    conds.append(User.phone == qn)
                conds.append(User.name.like(f"%{q}%"))
                if q.upper().startswith("G") and len(q) <= 10:
                    conds.append(User.referral_code == q.upper())
                users = query.filter(or_(*conds)).order_by(User.id.desc()).limit(50).all()
            except Exception as e:
                logger.error(f"admin_users_manage search: {e}")
        else:
            try:
                users = User.query.order_by(User.id.desc()).limit(30).all()
            except Exception:
                users = []
        # داده‌های هر کاربر
        user_rows = []
        try:
            from giso.referrals import get_wallet_balance, get_user_transactions, get_user_referrals
            for u in users:
                uid = u.id
                user_rows.append({
                    "id": uid,
                    "phone": u.phone,
                    "name": (u.name or "").strip() or (u.first_name or ""),
                    "referral_code": u.referral_code or "",
                    "created_at": u.created_at or "",
                    "last_login": u.last_login or "",
                    "balance": get_wallet_balance(uid),
                    "transactions": get_user_transactions(uid, limit=15),
                    "referrals": get_user_referrals(uid, limit=10),
                })
        except Exception as e:
            logger.error(f"admin_users_manage enrich: {e}")
        return render_template("admin_users.html", users=user_rows, q=q)

    @app.route("/admin/users/<int:user_id>/update", methods=["POST"])
    @login_required
    def admin_user_update(user_id):
        """ویرایش نام کاربر (فقط سوپرادمین)."""
        if _r := _check_giso_admin_access():
            return _r
        phone_norm = normalize_phone(getattr(current_user, "phone", "") or "")
        target = _admin_panel_target(phone_norm) or {}
        if target.get("role") != "super":
            flash("فقط سوپرادمین می‌تواند کاربر را ویرایش کند.", "warning")
            return redirect(url_for("admin_dashboard"))
        try:
            u = User.query.get_or_404(user_id)
            new_name = (request.form.get("name") or "").strip()[:150]
            if new_name:
                u.name = new_name
                if not (u.first_name or ""):
                    u.first_name = new_name.split()[0] if new_name.split() else new_name
            db.session.commit()
            flash("نام کاربر به‌روزرسانی شد.", "success")
        except Exception as e:
            logger.error(f"admin_user_update: {e}")
            flash("خطا در به‌روزرسانی کاربر.", "danger")
        return redirect(url_for("admin_users_manage", q=request.form.get("phone", "")))

    @app.route("/admin/users/<int:user_id>/wallet", methods=["POST"])
    @login_required
    @require_super
    def admin_user_wallet(user_id):
        """مسیر legacy اصلاح مانده؛ عملیات مرکزی نیز سوپرادمین را صریحاً چک می‌کند."""
        if _r := _check_giso_admin_access():
            return _r
        phone_norm = normalize_phone(getattr(current_user, "phone", "") or "")
        target = _admin_panel_target(phone_norm) or {}
        if target.get("role") != "super":
            flash("فقط سوپرادمین می‌تواند مانده کیف پول را تغییر دهد.", "warning")
            return redirect(url_for("admin_dashboard"))
        try:
            u = User.query.get_or_404(user_id)
            from giso.wallet import manual_adjust
            ok, msg = manual_adjust(
                user_id, request.form.get("delta", ""),
                request.form.get("balance_scope", "cash"),
                request.form.get("reason", ""),
            )
            flash(msg, "success" if ok else "danger")
            phone = u.phone
        except Exception as exc:
            logger.error(f"admin_user_wallet: {exc}")
            flash("خطا در تغییر مانده کیف پول.", "danger")
            phone = ""
        return redirect(url_for("admin_users_manage", q=phone))

    @app.route("/admin/users/<int:user_id>/delete", methods=["POST"])
    @login_required
    def admin_user_delete(user_id):
        """حذف کاربر (فقط سوپرادمین) با confirm در فرم."""
        if _r := _check_giso_admin_access():
            return _r
        phone_norm = normalize_phone(getattr(current_user, "phone", "") or "")
        target = _admin_panel_target(phone_norm) or {}
        if target.get("role") != "super":
            flash("فقط سوپرادمین می‌تواند کاربر را حذف کند.", "warning")
            return redirect(url_for("admin_dashboard"))
        confirm = (request.form.get("confirm") or "").strip()
        if confirm != "DELETE":
            flash("برای حذف، عبارت DELETE را تایپ کنید.", "warning")
            return redirect(url_for("admin_users_manage"))
        try:
            u = User.query.get_or_404(user_id)
            phone = u.phone
            # محافظت از سوپرادمین/ادمین‌ها
            from giso.config import is_super_admin
            if is_super_admin(phone=phone):
                flash("نمی‌توان سوپرادمین را حذف کرد.", "danger")
                return redirect(url_for("admin_users_manage"))
            # ادمین‌ها/حساب‌های تاریخی هرگز حذف نمی‌شوند؛ شناسه کاربر برای ممیزی می‌ماند.
            db.session.delete(u)
            db.session.commit()
            flash(f"کاربر {phone} حذف شد.", "success")
        except Exception as e:
            logger.error(f"admin_user_delete: {e}")
            flash("خطا در حذف کاربر.", "danger")
        return redirect(url_for("admin_users_manage"))

    @app.route("/admin/withdrawals")
    @login_required
    def admin_withdrawals():
        """مسیر legacy تسویه‌ها؛ canonical اکنون پنل ماژولار است."""
        return redirect(url_for("panel.wallet"))
        if _r := _check_giso_admin_access():
            return _r
        from giso.referrals import list_withdrawals
        withdrawals = []
        try:
            withdrawals = list_withdrawals(limit=200)
        except Exception:
            pass
        return render_template("admin_withdrawals.html", withdrawals=withdrawals)

    @app.route("/admin/withdrawal/<int:withdrawal_id>/status", methods=["POST"])
    @login_required
    @require_super
    def admin_withdrawal_status(withdrawal_id):
        """مسیر legacy بررسی تسویه؛ فقط سوپرادمین."""
        if _r := _check_giso_admin_access():
            return _r
        phone_norm = normalize_phone(getattr(current_user, "phone", "") or "")
        target = _admin_panel_target(phone_norm) or {}
        if target.get("role") != "super":
            flash("فقط سوپرادمین می‌تواند عملیات تسویه را انجام دهد.", "warning")
            return redirect(url_for("panel.dashboard"))
        new_status = (request.form.get("status") or "").strip().lower()
        note = request.form.get("admin_note", "").strip()
        try:
            from giso.referrals import set_withdrawal_status
            ok, msg = set_withdrawal_status(withdrawal_id, new_status, note)
            flash(msg, "success" if ok else "danger")
        except Exception as e:
            logger.error(f"admin_withdrawal_status: {e}")
            flash("خطا در به‌روزرسانی تسویه.", "danger")
        return redirect(url_for("admin_withdrawals"))

    @app.route("/dashboard/analyses")
    @login_required
    def dashboard_analyses():
        """مسیر legacy تاریخچه آنالیز؛ canonical اکنون پنل ماژولار است."""
        return redirect(url_for("panel_user.analysis_history"))
        analyses = []
        try:
            rows = Analysis.query.filter_by(phone=current_user.phone).order_by(Analysis.id.desc()).all()
            for a in rows:
                report = {}
                try:
                    report = json.loads(a.ai_report_json or "{}")
                except Exception:
                    report = {}
                analyses.append({
                    "id": a.id,
                    "type": a.type or "hair",
                    "type_fa": "💇 آنالیز مو" if (a.type or "hair") == "hair" else "✨ آنالیز پوست",
                    "created_at": a.created_at or "",
                    "score": report.get("overall_score", 0),
                    "status": report.get("status_label", ""),
                    "report": report,
                    "review_submitted": a.review_submitted or 0,
                })
        except Exception as e:
            logger.error(f"dashboard_analyses: {e}")
        return render_template("dashboard_analyses.html", analyses=analyses)

    @app.route("/dashboard/chats")
    @login_required
    def dashboard_chats():
        """مسیر legacy گفتگوها؛ canonical اکنون پنل ماژولار است."""
        return redirect(url_for("panel_user.conversations"))
        phone = getattr(current_user, "phone", "") or ""
        cons = []
        hair_chats = []
        try:
            with get_giso_db_conn() as conn:
                cons = conn.execute(
                    "SELECT * FROM consultant_requests WHERE phone=? ORDER BY id DESC",
                    (phone,)
                ).fetchall()
                # آخرین پیام هر درخواست
                for c in cons:
                    last = conn.execute(
                        "SELECT * FROM consultant_messages WHERE request_id=? ORDER BY id DESC LIMIT 1",
                        (c["id"],)
                    ).fetchone()
                    c = dict(c)
                    c["last_message"] = last["message"] if last else c.get("initial_message", "")
                    c["last_time"] = last["created_at"] if last else c.get("created_at", "")
                    unread = conn.execute(
                        "SELECT COUNT(*) as c FROM consultant_messages WHERE request_id=? AND sender='admin' AND is_read=0",
                        (c["id"],)
                    ).fetchone()["c"]
                    c["unread"] = unread
                    cons[cons.index(list(cons).index(c) if False else c) if False else 0] = c
        except Exception as e:
            logger.error(f"dashboard_chats: {e}")
        # بازسازی لیست به صورت dict برای تمیزتر شدن
        cons_list = []
        try:
            with get_giso_db_conn() as conn:
                for c in conn.execute(
                    "SELECT * FROM consultant_requests WHERE phone=? ORDER BY id DESC", (phone,)
                ).fetchall():
                    last = conn.execute(
                        "SELECT * FROM consultant_messages WHERE request_id=? ORDER BY id DESC LIMIT 1",
                        (c["id"],)
                    ).fetchone()
                    unread = conn.execute(
                        "SELECT COUNT(*) as c FROM consultant_messages WHERE request_id=? AND sender='admin' AND is_read=0",
                        (c["id"],)
                    ).fetchone()["c"]
                    d = dict(c)
                    d["last_message"] = last["message"] if last else d.get("initial_message", "")
                    d["last_time"] = last["created_at"] if last else d.get("created_at", "")
                    d["unread"] = unread
                    cons_list.append(d)
        except Exception as e:
            logger.error(f"dashboard_chats build: {e}")
        return render_template("dashboard_chats.html", consultant_chats=cons_list)

    @app.route("/dashboard/chats/consultant/<int:request_id>", methods=["GET", "POST"])
    @login_required
    def dashboard_consultant_chat(request_id):
        """صفحه چت با مشاور برای یک درخواست مشاوره."""
        phone = getattr(current_user, "phone", "") or ""
        if request.method == "POST" and request.form.get("action") == "clear_thread":
            from giso.consultant_chat_service import is_owner, clear_user_thread
            if is_owner(request_id, phone):
                clear_user_thread(request_id)
                flash("گفتگو از نمای شما پاک شد؛ در تاریخچه حفظ می‌شود.", "success")
            return redirect(url_for("dashboard_consultant_chat", request_id=request_id))
        if request.method == "POST":
            from flask import abort
            from giso.consultant_chat_service import is_owner
            if not is_owner(request_id, phone): abort(403)  # E2: مالکیت پیش از نوشتن
            message = request.form.get("message", "").strip()
            if message:
                try:
                    with get_giso_db_conn() as conn:
                        conn.execute(
                            "INSERT INTO consultant_messages (request_id, sender, message, is_read, created_at) "
                            "VALUES (?, 'user', ?, 0, ?)",
                            (request_id, message, datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
                        )
                        conn.commit()
                    _notify_consultant_admin_new_msg(request_id, message)
                except Exception as e:
                    logger.error(f"dashboard consultant send: {e}")
            return redirect(url_for("dashboard_consultant_chat", request_id=request_id))
        req = None
        messages = []
        try:
            with get_giso_db_conn() as conn:
                r = conn.execute("SELECT * FROM consultant_requests WHERE id=? AND phone=?", (request_id, phone)).fetchone()
                if r:
                    req = dict(r)
                from giso.consultant_chat_service import thread_messages
                messages = thread_messages(request_id, include_cleared=request.args.get("history") == "1")
                # مارک پیام‌های ادمین به‌عنوان خوانده‌شده
                conn.execute("UPDATE consultant_messages SET is_read=1 WHERE request_id=? AND sender='admin' AND is_read=0", (request_id,))
                conn.commit()
        except Exception as e:
            logger.error(f"dashboard consultant chat: {e}")
        if not req:
            audit_event("consultant_chat_ownership_denied", "failed", target=str(request_id), details="consultant request owner mismatch")
            flash("درخواست مشاوره پیدا نشد.", "danger")
            return redirect(url_for("dashboard_chats"))
        return render_template("dashboard_consultant_chat.html", req=req, messages=messages)

    @app.route("/dashboard/hair-chat/<int:order_id>", methods=["GET", "POST"])
    @login_required
    def dashboard_hair_chat(order_id):
        """چت اختصاصی فروش مو در سایت — پیام‌ها در hair_messages (مشترک با ربات)."""
        phone = getattr(current_user, "phone", "") or ""
        # مالکیت: فقط صاحب سفارش
        order = None
        try:
            order = HairOrder.query.filter_by(id=order_id, phone=phone).first()
        except Exception:
            order = None
        if not order:
            audit_event("hair_chat_ownership_denied", "failed", target=str(order_id), details="hair order owner mismatch")
            flash("درخواست فروش مو پیدا نشد.", "danger")
            return redirect(url_for("dashboard"))

        if request.method == "POST":
            message = request.form.get("message", "").strip()
            if message:
                try:
                    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    msg_row_id = 0
                    with get_giso_db_conn() as conn:
                        cur = conn.execute(
                            "INSERT INTO hair_messages (order_id, sender, message, is_read, created_at) "
                            "VALUES (?, 'user', ?, 0, ?)",
                            (order_id, message, now)
                        )
                        msg_row_id = int(cur.lastrowid or 0)
                        conn.commit()
                    # اعلان سیستمی مرکزی؛ workflow چت خودِ جدول hair_messages حفظ می‌شود.
                    # source_id هر پیام یکتا است تا هر پیام کاربر یک اعلان مجزا برای ادمین بسازد.
                    try:
                        from giso.panel.modules.notifications import log_notification
                        log_notification(
                            "hair_sale", "message", "پیام جدید چت فروش مو",
                            f"سفارش #{order_id} — {message[:300]}",
                            source_type="hair_chat_user_message", source_id=msg_row_id or order_id,
                        )
                    except Exception as exc:
                        logger.exception("hair chat notification center failed: %s", exc)
                except Exception as e:
                    logger.error(f"dashboard_hair_chat send: {e}")
            return redirect(url_for("dashboard_hair_chat", order_id=order_id))

        messages = []
        try:
            with get_giso_db_conn() as conn:
                messages = [dict(m) for m in conn.execute(
                    "SELECT * FROM hair_messages WHERE order_id=? ORDER BY id ASC", (order_id,)
                ).fetchall()]
                # مارک پیام‌های ادمین به‌عنوان خوانده‌شده
                conn.execute("UPDATE hair_messages SET is_read=1 WHERE order_id=? AND sender='admin' AND is_read=0", (order_id,))
                conn.commit()
        except Exception as e:
            logger.error(f"dashboard_hair_chat load: {e}")
        return render_template("dashboard_hair_chat.html", order=order, messages=messages)

    @app.route("/admin/analyses")
    @login_required
    @require_super
    def admin_analyses():
        """پنل بازطراحی‌شده درخواست‌های آنالیز ادمین."""
        if _r := _check_giso_admin_access():
            return _r
        filter_type = request.args.get("filter", "all").strip()
        rows = []
        stats = {"total": 0, "today": 0, "hair_count": 0, "skin_count": 0, "avg_rating": 0}
        try:
            with get_giso_db_conn() as conn:
                query = "SELECT a.*, w.name as user_name, w.city as user_city FROM analyses a LEFT JOIN giso_web_auth w ON a.phone=w.phone"
                if filter_type in ("hair", "skin"):
                    query += f" WHERE a.type='{filter_type}'"
                query += " ORDER BY a.id DESC"
                all_rows = [dict(r) for r in conn.execute(query).fetchall()]
                # آمار
                stats["total"] = len(all_rows)
                today = datetime.now().strftime("%Y-%m-%d")
                today_rows = conn.execute("SELECT id FROM analyses WHERE created_at LIKE ?", (f"{today}%",)).fetchall()
                stats["today"] = len(today_rows)
                stats["hair_count"] = conn.execute("SELECT COUNT(*) as c FROM analyses WHERE type='hair'").fetchone()["c"]
                stats["skin_count"] = conn.execute("SELECT COUNT(*) as c FROM analyses WHERE type='skin'").fetchone()["c"]
                score_rows = conn.execute("SELECT ai_report_json FROM analyses WHERE ai_report_json != '{}'").fetchall()
                scores = []
                for s in score_rows:
                    try:
                        scores.append(json.loads(s["ai_report_json"]).get("overall_score", 0))
                    except Exception:
                        pass
                stats["avg_rating"] = round(sum(scores) / len(scores)) if scores else 0
                # پردازش هر ردیف
                for r in all_rows:
                    rep = {}
                    try:
                        rep = json.loads(r.get("ai_report_json") or "{}")
                    except Exception:
                        rep = {}
                    r["type_fa"] = "💇 آنالیز مو" if (r.get("type") or "hair") == "hair" else "✨ آنالیز پوست"
                    r["score"] = rep.get("overall_score", 0)
                    r["status"] = rep.get("status_label", "")
                    rows.append(r)
        except Exception as e:
            logger.error(f"admin_analyses: {e}")
        return render_template("admin_analyses.html", analyses=rows, stats=stats, filter=filter_type)

    @app.route("/admin/analyses/<int:analysis_id>")
    @login_required
    @require_super
    def admin_analysis_detail(analysis_id):
        """جزئیات کامل یک آنالیز برای ادمین."""
        if _r := _check_giso_admin_access():
            return _r
        a = None
        report = {}
        plan = {}
        try:
            a = Analysis.query.get_or_404(analysis_id)
            report = json.loads(a.ai_report_json or "{}")
            plan = json.loads(a.plan_json or "{}")
        except Exception:
            pass
        if not a:
            flash("آنالیز پیدا نشد.", "danger")
            return redirect(url_for("admin_analyses"))
        return render_template("admin_analysis_detail.html", analysis=a,
                               report=report, plan=plan)

    @app.route("/admin/consultants")
    @login_required
    def admin_consultants():
        if _r := _check_giso_admin_access():
            return _r
        status = request.args.get("status", "all").strip()
        rows = []
        try:
            with get_giso_db_conn() as conn:
                if status and status in ("new", "reviewing", "chatting", "closed"):
                    rows = [dict(r) for r in conn.execute(
                        "SELECT * FROM consultant_requests WHERE status=? ORDER BY id DESC", (status,)
                    ).fetchall()]
                else:
                    status = "all"
                    rows = [dict(r) for r in conn.execute(
                        "SELECT * FROM consultant_requests ORDER BY id DESC").fetchall()]
        except Exception as e:
            logger.error(f"admin_consultants: {e}")
        return render_template("admin_consultants.html", requests=rows, status=status)

    @app.route("/admin/consultants/<int:request_id>")
    @login_required
    def admin_consultant_detail(request_id):
        if _r := _check_giso_admin_access():
            return _r
        req = None
        messages = []
        try:
            with get_giso_db_conn() as conn:
                r = conn.execute("SELECT * FROM consultant_requests WHERE id=?", (request_id,)).fetchone()
                if r:
                    req = dict(r)
                messages = [dict(m) for m in conn.execute(
                    "SELECT * FROM consultant_messages WHERE request_id=? ORDER BY id ASC", (request_id,)
                ).fetchall()]
        except Exception as e:
            logger.error(f"admin_consultant_detail: {e}")
        if not req:
            flash("درخواست پیدا نشد.", "danger")
            return redirect(url_for("admin_consultants"))
        return render_template("admin_consultant_detail.html", req=req, messages=messages)

    @app.route("/admin/consultants/<int:request_id>/status", methods=["POST"])
    @login_required
    def admin_consultant_status(request_id):
        if _r := _check_giso_admin_access():
            return _r
        status = request.form.get("status", "").strip()
        if status in ("new", "reviewing", "chatting", "closed"):
            try:
                with get_giso_db_conn() as conn:
                    conn.execute("UPDATE consultant_requests SET status=?, updated_at=? WHERE id=?",
                                 (status, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), request_id))
                    conn.commit()
                flash("وضعیت درخواست مشاوره به‌روزرسانی شد.", "success")
            except Exception as e:
                logger.error(f"admin_consultant_status: {e}")
                flash("خطا در به‌روزرسانی وضعیت.", "danger")
        return redirect(url_for("admin_consultant_detail", request_id=request_id))

    @app.route("/admin/consultants/<int:request_id>/reply", methods=["POST"])
    @login_required
    def admin_consultant_reply(request_id):
        if _r := _check_giso_admin_access():
            return _r
        message = request.form.get("message", "").strip()
        if message:
            try:
                with get_giso_db_conn() as conn:
                    conn.execute(
                        "INSERT INTO consultant_messages (request_id, sender, message, is_read, created_at) "
                        "VALUES (?, 'admin', ?, 0, ?)",
                        (request_id, message, datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
                    )
                    conn.commit()
                _notify_consultant_user_new_msg(request_id, message)
                try:
                    with get_giso_db_conn() as conn:
                        req_row = conn.execute("SELECT phone FROM consultant_requests WHERE id=?", (request_id,)).fetchone()
                    if req_row:
                        from giso.panel.modules.notifications import log_user_notification
                        log_user_notification(req_row["phone"], "consultant_reply", "پاسخ مشاور گیسو", message,
                                               source_type="consultant_reply", source_id=request_id)
                except Exception as exc:
                    logger.exception("consultant user notification failed: %s", exc)
                flash("پاسخ شما ارسال شد.", "success")
            except Exception as e:
                logger.error(f"admin_consultant_reply: {e}")
                flash("خطا در ارسال پاسخ.", "danger")
        return redirect(url_for("admin_consultant_detail", request_id=request_id))

    @app.route("/admin/product-requests")
    @login_required
    @require_super
    def admin_product_requests():
        if _r := _check_giso_admin_access():
            return _r
        rows = []
        try:
            with get_giso_db_conn() as conn:
                rows = [dict(r) for r in conn.execute(
                    "SELECT * FROM product_requests ORDER BY id DESC").fetchall()]
        except Exception as e:
            logger.error(f"admin_product_requests: {e}")
        return render_template("admin_product_requests.html", requests=rows)

    def _admin_guard():
        # Phase 4.1 / 4.4 — Backend permission enforcement: only admin/super may proceed
        from giso.panel.permissions import current_role_and_perms
        role, _, _ = current_role_and_perms()
        if role not in ("admin", "super"):
            from flask import flash, redirect, url_for
            flash("دسترسی ممنوع: فقط ادمین یا سوپرادمین.", "danger")
            return redirect(url_for("panel.settings"))
        return None

    @app.route("/admin")
    @app.route("/admin/")
    @login_required
    def admin_dashboard():
        """پنل مدیریت — فاز 4/6: فقط redirect به پنل ماژولار جدید.

        - /admin بدون tab → panel.dashboard
        - لینک‌های قدیمی ?tab=... → ماژول متناظر پنل جدید (migration حفظ می‌شود)
        - هر tab ناشناخته → panel.dashboard (قالب قدیمی admin.html حذف شده است)
        """
        if _r := _check_giso_admin_access():
            return _r
        _tab_map = {
            "tab-dash": "dashboard",
            "tab-products": "products",
            "tab-shop-orders": "shop_orders",
            "tab-hair-orders": "hair_sale",
            "tab-reviews": "reviews",
            "tab-analyses": "analyses",
            "tab-channel": "channel",
            "tab-ai": "ai",
            "tab-users": "users",
            "tab-ratelimit": "ratelimit",
        }
        _tab_param = request.args.get("tab", "")
        if _tab_param in _tab_map:
            try:
                return redirect(url_for("panel." + _tab_map[_tab_param]))
            except Exception:
                pass
        return redirect(url_for("panel.dashboard"))

    @app.route("/admin/review/<int:review_id>/delete", methods=["POST"])
    @login_required
    @require_super
    def admin_review_delete(review_id):
        if _r := _check_giso_admin_access():
            return _r
        try:
            r = Review.query.get_or_404(review_id)
            db.session.delete(r)
            db.session.commit()
            flash("نظر با موفقیت حذف شد.", "success")
        except Exception:
            try:
                db.session.rollback()
            except Exception:
                pass
            flash("خطا در حذف نظر.", "danger")
        return redirect(url_for("admin_dashboard", tab="tab-reviews"))

    @app.route("/admin/config/ai", methods=["POST"])
    @login_required
    @require_super
    def admin_config_ai():
        if _r := _check_giso_admin_access():
            return _r
        phone_norm = normalize_phone(getattr(current_user, "phone", "") or "")
        target = _admin_panel_target(phone_norm) or {}
        if target.get("role") != "super":
            flash("در پنل وب، تغییرهای AI فقط برای سوپرادمین فعال است و ادمین‌های دیگر فقط نمای مدیریتی را می‌بینند.", "warning")
            return redirect(url_for("admin_dashboard", tab="tab-ai"))

        action = (request.form.get("ai_action") or "").strip().lower()
        ok = False
        message = "درخواست نامعتبر است."

        try:
            if action == "set_chat_enabled":
                ok = set_chat_enabled(request.form.get("enabled") == "1")
                message = "وضعیت مشاور هوشمند ذخیره شد." if ok else "خطا در ذخیره وضعیت مشاور هوشمند."
            elif action == "set_display_name":
                ok, message = set_display_name(request.form.get("display_name", ""))
            elif action == "set_active_provider":
                ok, message = set_active_provider(request.form.get("provider_name", ""))
            elif action == "promote_failover":
                provider_name = (request.form.get("provider_name") or "").strip()
                chain = [p for p in get_failover_chain() if p != provider_name]
                if provider_name:
                    chain.insert(0, provider_name)
                ok, message = set_failover_chain(chain)
            elif action == "reset_failover":
                grouped = list_provider_options() or {}
                all_names = [x.get('name') for x in (grouped.get('iranian') or []) + (grouped.get('foreign') or []) if x.get('name')]
                ok, message = set_failover_chain(all_names)
            elif action == "save_role_policy":
                role_name = (request.form.get("role_name") or "user").strip().lower()
                access_level = int(request.form.get("access_level", 0) or 0)
                daily_limit = int(request.form.get("daily_limit", 0) or 0)
                sections = request.form.getlist("sections")
                ok, message = set_role_policy(role_name, access_level=access_level, sections=sections, daily_limit=daily_limit)
            elif action == "save_role_capabilities":
                role_name = (request.form.get("role_name") or "user").strip().lower()
                ok, message = set_role_capabilities(role_name, request.form.get("capabilities_text", ""))
            elif action == "set_widget_enabled":
                ok = set_widget_enabled(request.form.get("enabled") == "1")
                message = "وضعیت Widget سایت ذخیره شد." if ok else "خطا در ذخیره وضعیت Widget."
            elif action == "set_widget_position":
                ok, message = set_widget_position(request.form.get("position", ""))
            elif action == "set_widget_welcome":
                ok, message = set_widget_welcome_message(request.form.get("welcome_message", ""))
            elif action == "set_widget_color":
                ok, message = set_widget_primary_color(request.form.get("primary_color", ""))
        except Exception as e:
            ok = False
            message = f"خطا در اجرای تغییر: {e}"

        flash(message, "success" if ok else "danger")
        return redirect(url_for("admin_dashboard", tab="tab-ai"))

    @app.route("/admin/config/analysis-ratelimit", methods=["GET", "POST"])
    @login_required
    @require_super
    def admin_config_ratelimit():
        if _r := _check_giso_admin_access():
            return _r
        phone_norm = normalize_phone(getattr(current_user, "phone", "") or "")
        target = _admin_panel_target(phone_norm) or {}
        if target.get("role") != "super":
            flash("فقط سوپرادمین می‌تواند محدودیت زمانی آنالیز را تغییر دهد.", "warning")
            return redirect(url_for("panel.analyses"))
        from giso_admin import set_giso_config
        if request.method == "POST":
            try:
                enabled = request.form.get("rate_limit_enabled") == "1"
                minutes = request.form.get("rate_limit_minutes", "60").strip()
                try:
                    minutes = max(1, min(1440, int(minutes)))
                except ValueError:
                    minutes = 60
                limit_type = request.form.get("rate_limit_type", "both")
                if limit_type not in ("ip", "phone", "both"):
                    limit_type = "both"
                set_giso_config("rate_limit_enabled", "1" if enabled else "0")
                set_giso_config("rate_limit_minutes", str(minutes))
                set_giso_config("rate_limit_type", limit_type)
                flash("✅ تنظیمات محدودیت زمان تحلیل با موفقیت ذخیره شد.", "success")
            except Exception:
                flash("❌ خطا در ذخیره تنظیمات.", "danger")
            # فاز جامع UX: برگشت به تب «⏱ محدودیت زمانی» آنالیزها (همین صفحه)
            return redirect(url_for("panel.analyses", tab="ratelimit"))
        try:
            from giso.base import read_rate_limit_config
            _cfg = read_rate_limit_config()
            rate_limit_enabled = _cfg["enabled"]
            rate_limit_minutes = _cfg["minutes"]
            rate_limit_type = _cfg["limit_type"]
        except Exception:
            rate_limit_enabled = True
            rate_limit_minutes = 5
            rate_limit_type = "both"
        return render_template("admin_analysis_ratelimit.html",
                               rate_limit_enabled=rate_limit_enabled,
                               rate_limit_minutes=rate_limit_minutes,
                               rate_limit_type=rate_limit_type)

    with app.app_context():
        # فیکس استقلال: فقط جدول‌های بومی giso.db اینجا؛ جدول‌های bot جدا با
        # try/except تا خرابی bot.db لاگ شود نه کرش.
        try:
            db.create_all(bind_key=None)
        except Exception as exc:
            logger.warning("giso.db schema init failed: %s", exc)
        try:
            _giso_init_db()
        except Exception as exc:
            logger.warning("shared giso tables init failed: %s", exc)
        try:
            from giso.panel.modules.notifications import ensure_notifications_table
            ensure_notifications_table()
        except Exception as exc:
            logger.warning("notification tables init failed: %s", exc)
        try:
            migrate_giso_tables()
        except Exception:
            pass
        try:
            from giso.marketplace.schema import migrate_marketplace_tables
            migrate_marketplace_tables()
        except Exception as exc:
            logger.warning("marketplace tables init failed: %s", exc)
        try:
            from giso.beauty_centers.schema import migrate_beauty_center_tables
            migrate_beauty_center_tables()
        except Exception as exc:
            logger.warning("beauty center tables init failed: %s", exc)
        try:
            db.create_all(bind="bot")
        except Exception:
            pass
        try:
            seed_sample_products()
        except Exception:
            pass

    # P0: پچ گزارش نهایی آنالیز روی همه entrypointها (نه فقط wsgi)
    try:
        from giso.analysis_final_override import install as _install_analysis_final
        _install_analysis_final()
    except Exception as _e:
        logger.warning("analysis final override not applied: %s", _e)

    # سئو شبانه: thread دیمون داخل همین پروسس giso-web (بدون systemd timer / بدون root).
    try:
        from giso.seo_jobs import start_seo_scheduler
        start_seo_scheduler()
    except Exception as _e:
        logger.warning("seo scheduler start skipped: %s", _e)

    # مرحلهٔ ۳ se.md / BUG-003 — صفحات خطای برند گیسو
    for _ec in (404, 405, 500):
        app.register_error_handler(
            _ec, lambda _e, _c=_ec: (render_template("errors/%d.html" % _c), _c))

    return app

app = None
if __name__ == "__main__":
    app = create_app()
    print("=" * 60)
    print("  پروژه گیسو در حال اجرا...")
    print("  آدرس: http://127.0.0.1:5001")
    print("  توقف: Ctrl+C")
    print("=" * 60)
    try:
        # سرویس production-ready: waitress (threaded) — پرهیز از گلوگاه تک‌نخی Flask dev
        from waitress import serve
        serve(app, host="0.0.0.0", port=5001, threads=8)
    except ImportError:
        # fallback امن: اگر waitress در محیط نصب نبود، رفتار قبلی حفظ می‌شود
        app.run(host="0.0.0.0", port=5001, debug=False, use_reloader=False)
else:
    app = create_app()
