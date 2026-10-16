# -*- coding: utf-8 -*-
"""panel/modules/ai.py — مدیریت کامل AI (فاز 5).

فهرست پروایدرها، افزودن/ویرایش/حذف، فعال/غیرفعال، پروکسی، تست، تست گفتگو،
AI فعال و failover، دسترسی نقش‌ها، رفتار و هویت، Widget، عملیات و تاریخچه.

داده و عملیات: همان توابع موجود (ai_runtime + ai_brain) که ربات استفاده می‌کند —
هیچ سیستم موازی ساخته نمی‌شود.
"""
import logging

from flask import request, redirect, url_for, flash

from giso.panel.permissions import current_role_and_perms

logger = logging.getLogger("giso_panel_ai")


def _require_super():
    role, perms, bale_id = current_role_and_perms()
    if role != "super":
        flash("فقط سوپرادمین می‌تواند AI را مدیریت کند.", "warning")
        return redirect(url_for("panel.ai"))
    return None


def _run_async(coro):
    """اجرای coroutine با helper واحد (هم در thread بدون loop، هم loop در حال اجرا)."""
    from giso.async_compat import run_async_safe
    try:
        return run_async_safe(coro)
    except Exception:
        return None


def _relative_time_fa(stamp):
    """فرمت فارسی «X دقیقه/ساعت/روز پیش» از مهر زمانی «2026-09-08 12:00 UTC»."""
    from datetime import datetime, timezone
    s = str(stamp or "").strip()
    if not s:
        return "—"
    try:
        dt = datetime.strptime(s[:16], "%Y-%m-%d %H:%M").replace(tzinfo=timezone.utc)
        diff = max(0, int((datetime.now(timezone.utc) - dt).total_seconds()))
        if diff < 60:
            return "همین الان"
        if diff < 3600:
            return f"{diff // 60} دقیقه پیش"
        if diff < 86400:
            return f"{diff // 3600} ساعت پیش"
        return f"{diff // 86400} روز پیش"
    except Exception:
        return s[:16]


# ───────────────────── handler ها (POST — فقط سوپرادمین) ─────────────────────

def handle_config():
    """همان اکشن‌های پنل قدیمی (admin_config_ai) — redirect به پنل ماژولار."""
    g = _require_super()
    if g:
        return g
    action = (request.form.get("ai_action") or "").strip().lower()
    ok = False
    message = "درخواست نامعتبر است."
    try:
        from giso.ai_runtime import (
            set_chat_enabled, set_display_name, set_active_provider,
            set_failover_chain, get_failover_chain, list_provider_options,
            set_role_policy, set_role_capabilities,
            set_widget_enabled, set_widget_position,
            set_widget_welcome_message, set_widget_primary_color,
        )
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
            try:
                access_level = int(request.form.get("access_level", 0) or 0)
            except (TypeError, ValueError):
                access_level = 0
            try:
                daily_limit = int(request.form.get("daily_limit", 0) or 0)
            except (TypeError, ValueError):
                daily_limit = 0
            sections = request.form.getlist("sections")
            ok, message = set_role_policy(role_name, access_level=access_level,
                                          sections=sections, daily_limit=daily_limit)
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
        elif action == "save_credit_settings":
            from giso_admin import set_giso_config
            set_giso_config("ai_user_credit_enabled", "1" if request.form.get("enabled") == "1" else "0")
            # مورد ۱۱ help.md: اعتبار اولیهٔ عددی حذف شد؛ فقط هزینهٔ کسر از اعتبار مصرفی.
            cost=max(1,min(10000,int(request.form.get("cost",1) or 1)))
            set_giso_config("ai_user_request_cost",str(cost))
            scope=str(request.form.get("scope","spend") or "spend").strip().lower()
            set_giso_config("ai_user_credit_scope", scope if scope in ("spend","cash") else "spend")
            ok=True;message="تنظیمات اعتبار هوش مصنوعی ذخیره شد."
        elif action == "save_beauty_mirror_model":
            from giso.buti_ai.ai_models import save_model_assignment
            ok, message = save_model_assignment(
                request.form.get("task_key", ""),
                request.form.get("priority", "1"),
                request.form.get("provider_name", ""),
                request.form.get("model_name", ""),
                enabled=request.form.get("enabled") == "1",
                image_kind=request.form.get("image_kind", ""),
                endpoint_override=request.form.get("endpoint_override", ""),
            )
        elif action == "seed_beauty_mirror_models":
            from giso.buti_ai.ai_models import auto_configure_defaults
            res = auto_configure_defaults(overwrite=False)
            ok = bool(res.get("ok"))
            added = int(res.get("added") or 0)
            message = f"{added} اسلات خالی آینه گیسو به‌صورت خودکار تنظیم شد." if ok else "تنظیم خودکار مدل‌های آینه گیسو انجام نشد."
        elif action == "repair_beauty_mirror_image_models":
            from giso.buti_ai.ai_models import repair_legacy_cloudflare_eyebrow_image_slots
            res = repair_legacy_cloudflare_eyebrow_image_slots()
            ok = bool(res.get("ok"))
            changed = int(res.get("changed") or 0)
            message = f"{changed} اسلات زنجیرهٔ مشترک طراحی تصویر آینه بررسی/اصلاح شد." if ok else "اصلاح زنجیرهٔ طراحی تصویر آینه انجام نشد."
    except Exception as e:
        ok = False
        message = f"خطا در اجرای تغییر: {e}"
    flash(message, "success" if ok else "danger")
    return redirect(url_for("panel.ai"))


def handle_credit_adjust():
    g = _require_super()
    if g: return g
    try:
        from giso.ai_credits import admin_adjust_credit
        ok,message=admin_adjust_credit(int(request.form.get("user_id") or 0),int(request.form.get("delta") or 0),actor="super")
    except (TypeError,ValueError):
        ok,message=False,"مقدار اعتبار نامعتبر است."
    flash(message,"success" if ok else "danger")
    return redirect(url_for("panel.ai")+"#pane-credits")


def handle_credit_scope():
    """مورد ۱۱ help2: انتخاب حوزهٔ کسر اعتبار کاربر (نقدی/مصرفی) توسط سوپرادمین."""
    g = _require_super()
    if g: return g
    try:
        from giso.ai_credits import set_deduct_scope
        ok = set_deduct_scope(int(request.form.get("user_id") or 0), request.form.get("scope") or "spend")
        message = "حوزهٔ کسر اعتبار ذخیره شد." if ok else "حوزهٔ نامعتبر است."
    except (TypeError, ValueError):
        ok, message = False, "کاربر نامعتبر است."
    flash(message, "success" if ok else "danger")
    return redirect(url_for("panel.ai") + "#pane-credits")


def _valid_base_url(url: str) -> bool:
    """اعتبارسنجی Base URL سفارشی (مثلاً Worker کلودفلر) — فقط http/https با هوست معتبر."""
    try:
        from urllib.parse import urlparse
        u = urlparse((url or "").strip())
        return u.scheme in ("http", "https") and bool(u.hostname) and " " not in (url or "")
    except Exception:
        return False


def _proxy_type_of(proxy_url):
    u = str(proxy_url or "").strip()
    if u.startswith("socks5"):
        return "socks5"
    if u.startswith("http"):
        return "http"
    return ""


def _provider_activation_error(provider):
    """اعتبارسنجی حداقلی برای جلوگیری از فعال‌کردن ردیف‌های seed خالی/ناقص."""
    if not provider:
        return "پروایدر پیدا نشد."
    if not str(provider["api_key"] or "").strip():
        return "برای فعال‌سازی، ابتدا API Key یا Token را ثبت کنید."
    kind = str(provider["kind"] or "").strip().lower()
    if kind == "cloudflare":
        root = str(provider["api_root"] or provider["base_url"] or "").strip()
        if not root or "{account_id}" in root:
            return "برای Cloudflare، یک Account ID معتبر لازم است."
    elif not str(provider["base_url"] or "").strip():
        return "برای فعال‌سازی، ابتدا Base URL را ثبت کنید."
    return ""


_LEGACY_CF_SLOT_NAMES = {"cf", "cf1", "cf2", "cf3"}
_DISPLAY_NAME_MAX = 60


def _create_provider_from_form(choice):
    """منطق مشترک فرم واحد «افزودن سرویس».

    choice: «cloudflare» | کلید یکی از سرویس‌های رجیستری | «custom».
    هر ثبت، یک نمونهٔ مستقل با شناسهٔ داخلی یکتا می‌سازد و فقط با تأیید واقعی
    اتصال (check_ai_provider) فعال می‌شود؛ هرگز موفقیت را حدس نمی‌زند.
    """
    from urllib.parse import urlparse
    from giso.ai_brain import (
        create_provider_instance, finalize_provider_instance, check_ai_provider,
        refresh_models, normalize_cloudflare_account_id, normalize_cloudflare_api_root,
        cloudflare_account_id_from_url, list_ai_providers, save_provider_to_env,
        _validate_base_url, _normalize_gemini_base_url,
    )
    from giso.ai_models_registry import get_provider as _reg_provider

    display_name = (request.form.get("display_name") or request.form.get("provider_name") or "").strip()
    api_key = (request.form.get("api_key") or "").strip()
    if not display_name or not api_key:
        flash("نام سرویس و کلید API (یا Token) الزامی هستند.", "warning")
        return redirect(url_for("panel.ai"))
    if len(display_name) > _DISPLAY_NAME_MAX:
        flash(f"نام سرویس حداکثر {_DISPLAY_NAME_MAX} نویسه باشد.", "warning")
        return redirect(url_for("panel.ai"))
    if choice in _LEGACY_CF_SLOT_NAMES:
        flash("نام‌های cf / cf1 / cf2 / cf3 دیگر در فرم استفاده نمی‌شوند؛ گزینهٔ Cloudflare را انتخاب کنید.", "warning")
        return redirect(url_for("panel.ai"))

    if choice == "cloudflare":
        account_id = normalize_cloudflare_account_id(request.form.get("account_id") or "")
        if not account_id:
            flash("برای Cloudflare، Account ID الزامی است.", "warning")
            return redirect(url_for("panel.ai"))
        try:
            base_url = normalize_cloudflare_api_root("", account_id, require_account=True)
        except ValueError as cf_error:
            flash(str(cf_error), "warning")
            return redirect(url_for("panel.ai"))
        for row in list_ai_providers():
            same_kind = str(row["kind"] or "").strip().lower() == "cloudflare"
            if same_kind and cloudflare_account_id_from_url(row["api_root"] or row["base_url"] or "") == account_id:
                flash("این Account ID قبلاً به یک حساب Cloudflare وصل شده است.", "warning")
                return redirect(url_for("panel.ai"))
        reg = _reg_provider("cloudflare") or {}
        family, kind, models_source = "cloudflare", "cloudflare", "registry"
        timeout, is_iranian = int(reg.get("timeout", 25) or 25), False
        vision, text = reg.get("vision_models", []), reg.get("text_models", [])
    elif choice == "custom":
        base_url = (request.form.get("base_url") or "").strip()
        if not base_url:
            flash("برای سرویس دلخواه، Base URL الزامی است.", "warning")
            return redirect(url_for("panel.ai"))
        if not _valid_base_url(base_url):
            flash("Base URL نامعتبر است (باید با https:// شروع شود).", "warning")
            return redirect(url_for("panel.ai"))
        try:
            _validate_base_url(base_url)
        except ValueError as url_error:
            flash(str(url_error), "warning")
            return redirect(url_for("panel.ai"))
        if (urlparse(base_url).hostname or "").lower() == "api.cloudflare.com":
            flash("برای Cloudflare از گزینهٔ Cloudflare استفاده کنید.", "warning")
            return redirect(url_for("panel.ai"))
        family, kind, models_source = "custom", "openai", "discovered"
        timeout, is_iranian = 20, False
        vision, text = [], []
    else:
        reg = _reg_provider(choice)
        if not reg or reg.get("name") != choice:
            flash("سرویس انتخاب‌شده در رجیستری وجود ندارد.", "warning")
            return redirect(url_for("panel.ai"))
        family, models_source = choice, "registry"
        base_url = reg.get("base_url", "")
        if family == "gemini":
            base_url = _normalize_gemini_base_url(base_url)
        kind = reg.get("kind", "openai")
        timeout = int(reg.get("timeout", 20) or 20)
        is_iranian = bool(reg.get("is_iranian", False))
        vision, text = reg.get("vision_models", []), reg.get("text_models", [])

    try:
        name = create_provider_instance(
            family, display_name, api_key, base_url, kind=kind, timeout=timeout,
            is_iranian=is_iranian, vision_models=vision, text_models=text,
            models_source=models_source,
        )
    except Exception as exc:
        logger.error(f"provider instance create: {type(exc).__name__}")
        flash("ذخیرهٔ سرویس انجام نشد.", "danger")
        return redirect(url_for("panel.ai"))

    # تأیید واقعی اتصال: فقط نتیجهٔ ok موفقیت است.
    try:
        res = _run_async(check_ai_provider(name)) or {}
    except Exception as exc:
        logger.error(f"provider instance check: {type(exc).__name__}")
        res = {"status": "error", "error": "خطای غیرمنتظره در تست اتصال", "selected": ""}
    verified = str(res.get("status") or "").startswith("ok")
    finalize_provider_instance(name, verified, res.get("selected") or "")

    if verified:
        if kind == "openai":
            try:
                refresh_models(name)  # فهرست Vision/Text از /models همان سرویس
            except Exception as refresh_exc:
                logger.debug(f"provider refresh after verify: {type(refresh_exc).__name__}")
        try:
            from giso.buti_ai.ai_models import auto_configure_for_provider
            auto_configure_for_provider(name, overwrite=False)  # فقط اسلات‌های خالی
        except Exception as auto_exc:
            logger.debug(f"beauty mirror auto config after provider add: {type(auto_exc).__name__}")
        try:
            save_provider_to_env(name=name, api_key=api_key, base_url=base_url,
                                 model=res.get("selected") or "", enabled=True, proxy=False,
                                 iranian=is_iranian, timeout=timeout)
        except Exception as env_exc:
            logger.warning(f"provider env backup: {type(env_exc).__name__}")
        flash(f"✅ «{display_name}» متصل و تأیید شد. مدل تأییدشده: {res.get('selected') or '—'}", "success")
    else:
        err = str(res.get("error") or "").strip()[:120] or "پاسخی دریافت نشد"
        flash(f"⚠️ «{display_name}» ذخیره شد، اما اتصال تأیید نشد و سرویس غیرفعال است. "
              f"دلیل: {err}. بعد از رفع مشکل با «🔁 تست سلامت» دوباره بررسی کنید.", "warning")
    return redirect(url_for("panel.ai"))


def handle_provider_add():
    """فرم واحد «افزودن سرویس» (Cloudflare، سرویس‌های رجیستری یا سرویس دلخواه)."""
    g = _require_super()
    if g:
        return g
    choice = (request.form.get("provider") or request.form.get("name") or "").strip().lower()
    if not choice:
        flash("یک سرویس را از فهرست انتخاب کنید.", "warning")
        return redirect(url_for("panel.ai"))
    return _create_provider_from_form(choice)


def handle_provider_toggle(name):
    g = _require_super()
    if g:
        return g
    try:
        from giso.ai_brain import get_ai_provider, toggle_ai_provider, save_provider_to_env
        provider = get_ai_provider(name)
        if not provider:
            flash("پروایدر پیدا نشد.", "danger")
            return redirect(url_for("panel.ai"))
        if not bool(provider["enabled"]):
            activation_error = _provider_activation_error(provider)
            if activation_error:
                flash(activation_error, "warning")
                return redirect(url_for("panel.ai"))
        new_val = toggle_ai_provider(name)
        if new_val is None:
            flash("خطا در تغییر وضعیت پروایدر.", "danger")
        else:
            try:
                provider = get_ai_provider(name)
                if provider:
                    save_provider_to_env(
                        name=name, api_key=provider["api_key"] or "",
                        base_url=provider["base_url"] or "",
                        model=provider["selected_model"] or "",
                        enabled=bool(provider["enabled"]),
                        proxy=bool(provider["use_proxy"]),
                        iranian=bool(provider["is_iranian"]),
                        timeout=provider["timeout"] or 20,
                        proxy_url=provider["proxy_url"] or "",
                        proxy_type=provider["proxy_type"] or "",
                    )
            except Exception as env_exc:
                logger.warning("panel ai provider toggle backup failed: %s", type(env_exc).__name__)
            flash(f"پروایدر «{name}» {'فعال' if new_val else 'غیرفعال'} شد.", "success")
    except Exception as e:
        logger.error(f"panel ai provider toggle: {e}")
        flash("خطا در تغییر وضعیت.", "danger")
    return redirect(url_for("panel.ai"))


def handle_provider_proxy(name):
    g = _require_super()
    if g:
        return g
    try:
        from giso.ai_brain import toggle_use_proxy, get_ai_provider, save_provider_to_env
        new_val = toggle_use_proxy(name)
        if new_val is None:
            flash("پروایدر پیدا نشد.", "danger")
        else:
            try:
                provider = get_ai_provider(name)
                if provider:
                    save_provider_to_env(
                        name=name, api_key=provider["api_key"] or "",
                        base_url=provider["base_url"] or "",
                        model=provider["selected_model"] or "",
                        enabled=bool(provider["enabled"]), proxy=bool(new_val),
                        iranian=bool(provider["is_iranian"]),
                        timeout=provider["timeout"] or 20,
                        proxy_url=provider["proxy_url"] or "",
                        proxy_type=provider["proxy_type"] or "",
                    )
            except Exception as env_exc:
                logger.warning("panel ai provider proxy backup failed: %s", type(env_exc).__name__)
            flash(f"پروکسی عمومی برای «{name}» {'فعال' if new_val else 'غیرفعال'} شد.", "success")
    except Exception as e:
        logger.error(f"panel ai provider proxy: {e}")
        flash("خطا در تغییر پروکسی.", "danger")
    return redirect(url_for("panel.ai"))


def handle_provider_update(name):
    g = _require_super()
    if g:
        return g
    field = (request.form.get("field") or "").strip()
    value = (request.form.get("value") or "").strip()
    editable = ("api_key", "base_url", "api_root", "timeout", "headers", "fallback",
                "selected_model", "proxy_url")
    if field not in editable:
        flash("فیلد نامعتبر است.", "warning")
        return redirect(url_for("panel.ai"))
    if field in ("timeout",):
        try:
            value = str(max(5, min(120, int(value))))
        except (TypeError, ValueError):
            flash("timeout باید عدد باشد (۵ تا ۱۲۰).", "warning")
            return redirect(url_for("panel.ai"))
    if field == "proxy_url" and value and not _proxy_type_of(value):
        flash("آدرس پروکسی باید با socks5:// یا http:// شروع شود (خالی = بدون پروکسی).", "warning")
        return redirect(url_for("panel.ai"))
    if field in ("base_url", "api_root") and str(name).lower() == "gemini":
        from giso.ai_brain import _normalize_gemini_base_url
        value = _normalize_gemini_base_url(value)
    if field in ("base_url", "api_root") and value and not _valid_base_url(value):
        flash("Base URL نامعتبر است (باید با http:// یا https:// شروع شود).", "warning")
        return redirect(url_for("panel.ai"))
    try:
        from giso.ai_brain import (
            update_ai_provider_field, get_ai_provider, save_provider_to_env,
            get_conn, _lock, toggle_ai_provider, normalize_cloudflare_api_root,
        )
        # فاز ۲ (۲.۸): اگر api_key از خالی به پر تغییر کرد → فقط در صورت کامل‌بودن تنظیمات فعال شود.
        old_row = get_ai_provider(name)
        old_api_key = str(old_row["api_key"] or "").strip() if old_row else ""
        is_cloudflare = bool(old_row and str(old_row["kind"] or "").strip().lower() == "cloudflare")

        if is_cloudflare and field in ("base_url", "api_root"):
            try:
                value = normalize_cloudflare_api_root(value, require_account=True)
            except ValueError as cf_error:
                flash(str(cf_error), "warning")
                return redirect(url_for("panel.ai"))

        if field == "proxy_url":
            conn = get_conn()
            try:
                with _lock, conn:
                    cur = conn.execute(
                        "UPDATE giso_ai_providers SET proxy_url=?, proxy_type=? WHERE name=?",
                        (value, _proxy_type_of(value), name),
                    )
                ok = cur.rowcount > 0
            finally:
                conn.close()
        elif is_cloudflare and field in ("base_url", "api_root"):
            # موتور Cloudflare از api_root استفاده می‌کند؛ هر دو ستون را هماهنگ نگه دار.
            conn = get_conn()
            try:
                with _lock, conn:
                    cur = conn.execute(
                        "UPDATE giso_ai_providers SET base_url=?, api_root=? WHERE name=?",
                        (value, value, name),
                    )
                ok = cur.rowcount > 0
            finally:
                conn.close()
        else:
            ok = update_ai_provider_field(name, field, value)

        if ok:
            auto_enabled = False
            auto_disabled = False
            activation_block_reason = ""
            if field == "api_key" and value and not old_api_key and old_row and not old_row["enabled"]:
                updated_row = get_ai_provider(name)
                activation_block_reason = _provider_activation_error(updated_row)
                if not activation_block_reason:
                    auto_enabled = bool(toggle_ai_provider(name))
            elif field == "api_key" and not value and old_row and old_row["enabled"]:
                auto_disabled = toggle_ai_provider(name) is False
            backup_saved = False
            try:
                prov = get_ai_provider(name)
                if prov:
                    save_provider_to_env(
                        name=name,
                        api_key=prov["api_key"] or "",
                        base_url=prov["base_url"] or "",
                        model=prov["selected_model"] or "",
                        enabled=bool(prov["enabled"]),
                        proxy=bool(prov["use_proxy"]),
                        iranian=bool(prov["is_iranian"]),
                        timeout=prov["timeout"] or 20,
                        proxy_url=prov["proxy_url"] or "",
                        proxy_type=prov["proxy_type"] or "",
                    )
                    backup_saved = True
            except Exception as env_exc:
                logger.warning("panel ai provider update backup failed: %s", type(env_exc).__name__)
            extra = " و پروایدر فعال شد" if auto_enabled else (" و به‌دلیل حذف کلید غیرفعال شد" if auto_disabled else "")
            storage_label = "دیتابیس + .env" if backup_saved else "دیتابیس (نسخهٔ پشتیبان .env به‌روز نشد)"
            flash(f"فیلد «{field}» پروایدر «{name}» ذخیره شد{extra} ({storage_label}).", "success")
            if activation_block_reason:
                flash(f"کلید ذخیره شد؛ برای فعال‌سازی، تنظیمات ناقص را کامل کنید: {activation_block_reason}", "warning")
            # فاز ۲ (۲.۸): با تغییر کلید یا آدرس، مدل‌ها خودکار تازه شوند.
            if field in ("api_key", "base_url"):
                try:
                    from giso.ai_brain import refresh_models
                    res = refresh_models(name)
                    if res.get("ok"):
                        flash(f"🔄 مدل‌ها به‌روزرسانی شد: {res['vision_count']} Vision + {res['text_count']} Text", "success")
                except Exception as re_:
                    logger.error(f"panel ai refresh after update: {re_}")
        else:
            flash("پروایدر پیدا نشد یا ذخیره فیلد انجام نشد.", "danger")
    except Exception as e:
        logger.error(f"panel ai provider update: {e}")
        flash(f"خطا: {str(e)[:100]}", "danger")
    return redirect(url_for("panel.ai"))


def handle_refresh_models(name):
    """فاز ۲: دکمه «🔄 بروزرسانی مدل‌ها» — فقط /models، بدون پینگ تست."""
    g = _require_super()
    if g:
        return g
    try:
        from giso.ai_brain import refresh_models
        res = refresh_models(name) or {}
        if res.get("ok"):
            new_count = len(res.get("new") or [])
            removed = res.get("removed") or []
            msg = (f"🔄 مدل‌های «{name}» به‌روزرسانی شد: "
                   f"{res['vision_count']} Vision + {res['text_count']} Text")
            if new_count:
                msg += f" | جدید: {new_count}"
            if removed:
                msg += f" | حذف‌شده از سرویس: {'، '.join(removed[:5])}"
            flash(msg, "success")
        else:
            flash(f"خطا در بروزرسانی مدل‌های «{name}»: {str(res.get('error') or '')[:120]}", "danger")
    except Exception as e:
        logger.error(f"panel ai refresh models: {e}")
        flash(f"خطا: {str(e)[:100]}", "danger")
    return redirect(url_for("panel.ai"))


def handle_bulk_import():
    """فاز ۲: ورود دسته‌ای مدل‌ها با JSON — فقط افزودنی، بدون پاک‌کردن."""
    g = _require_super()
    if g:
        return g
    json_data = request.form.get("json_data") or ""
    try:
        from giso.ai_brain import bulk_import_models
        res = bulk_import_models(json_data) or {}
        if res.get("ok"):
            flash(f"✅ {res['added']} مدل به «{res['provider']}» اضافه شد "
                  f"(Vision: {res['vision_count']} | Text: {res['text_count']}).", "success")
        else:
            flash(f"خطا در ورود دسته‌ای: {str(res.get('error') or '')[:150]}", "danger")
    except Exception as e:
        logger.error(f"panel ai bulk import: {e}")
        flash(f"خطا: {str(e)[:100]}", "danger")
    return redirect(url_for("panel.ai"))


def handle_provider_delete(name):
    g = _require_super()
    if g:
        return g
    step = (request.form.get("step") or "").strip()
    try:
        from giso.ai_brain import delete_ai_provider
        if step == "confirm":
            ok = delete_ai_provider(name)
            if ok:
                flash(f"پروایدر «{name}» حذف شد.", "success")
            else:
                flash("پروایدر پیدا نشد.", "danger")
        else:
            flash(f"⚠️ برای حذف نهایی پروایدر «{name}»، دوباره دکمه حذف را بزنید.", "warning")
    except Exception as e:
        logger.error(f"panel ai provider delete: {e}")
        flash("خطا در حذف.", "danger")
    return redirect(url_for("panel.ai"))


def handle_provider_test(name):
    g = _require_super()
    if g:
        return g
    try:
        from giso.ai_brain import check_ai_provider
        res = _run_async(check_ai_provider(name)) or {}
        status = str(res.get("status") or "error")
        ok = status.startswith("ok")
        models = "، ".join(res.get("models") or [])[:120] or "—"
        msg = (f"پروایدر «{name}»: {'✅ سالم' if ok else '❌ خطا'} — مدل: {res.get('selected') or '—'} | مدل‌ها: {models}")
        if res.get("error"):
            msg += f" | پیام: {str(res['error'])[:100]}"
        flash(msg, "success" if ok else "danger")
    except Exception as e:
        logger.error(f"panel ai provider test: {e}")
        flash(f"خطا در تست: {str(e)[:100]}", "danger")
    return redirect(url_for("panel.ai"))


def handle_refresh_all_models():
    """دکمهٔ «بروزرسانی همهٔ هوش مصنوعی‌ها» (مأموریت 11):
    لیست مدل هر پروایدر را از /models خودش هوشمندانه به‌روز می‌کند و
    گزارش هر سرویس را در پنل مدیریت هوش مصنوعی نشان می‌دهد."""
    from giso.ai_discovery import refresh_all_models_async
    try:
        res = _run_async(refresh_all_models_async())
    except Exception as e:
        flash(f"خطا در بروزرسانی هوشمند: {e}", "error")
        return redirect(url_for("panel.ai"))
    flash("بروزرسانی هوشمند همهٔ سرویس‌ها: " + str(res.get("summary") or ""), "info")
    # گزارش هر سرویس به‌صورت جدا — در کارت‌های همین صفحه نمایش داده می‌شود
    for r in (res.get("reports") or []):
        nm = r.get("name") or "?"
        if r.get("ok"):
            flash(f"{nm}: به‌روزرسانی شد — {r.get('vision_count', 0)} بینایی + "
                  f"{r.get('text_count', 0)} متنی (جدید: {r.get('new', 0)}) — "
                  f"برتر: {r.get('top') or '-'}", "success")
        elif r.get("skipped"):
            flash(f"{nm}: رد شد — {r.get('error') or ''}", "info")
        else:
            flash(f"{nm}: خطا — {r.get('error') or ''} (لیست قبلی حفظ شد)", "error")
    return redirect(url_for("panel.ai"))


def handle_test_all():
    g = _require_super()
    if g:
        return g
    try:
        from giso.ai_brain import check_all_ai_providers
        results = _run_async(check_all_ai_providers()) or []
        if not results:
            flash("هیچ پروایدری ثبت نشده است.", "warning")
            return redirect(url_for("panel.ai"))
        ok_count = sum(1 for r in results if str(r.get("status") or "").startswith("ok"))
        lines = [f"تست {len(results)} پروایدر: {ok_count} سالم ✅"]
        for r in results[:10]:
            s = str(r.get("status") or "error")
            lines.append(f"• {r.get('name')}: {'✅' if s.startswith('ok') else '❌'} {str(r.get('error') or '')[:80]}")
        flash(" | ".join(lines), "success" if ok_count == len(results) else "warning")
    except Exception as e:
        logger.error(f"panel ai test all: {e}")
        flash(f"خطا در تست: {str(e)[:100]}", "danger")
    return redirect(url_for("panel.ai"))


def handle_chat_test():
    g = _require_super()
    if g:
        return g
    prompt = (request.form.get("prompt") or "").strip()
    if not prompt:
        flash("متن تست خالی است.", "warning")
        return redirect(url_for("panel.ai"))
    try:
        from giso.ai_brain import ask_ai_fast
        res = _run_async(ask_ai_fast([{"role": "user", "content": prompt}])) or {}
        if res.get("ok"):
            answer = (res.get("text") or "").strip() or "(پاسخ خالی)"
            flash(f"✅ پاسخ از «{res.get('provider') or '—'}»: {answer[:300]}", "success")
        else:
            flash(f"❌ تست گفتگو ناموفق: {str(res.get('error') or 'خطا')[:200]}", "danger")
    except Exception as e:
        logger.error(f"panel ai chat test: {e}")
        flash(f"خطا: {str(e)[:120]}", "danger")
    return redirect(url_for("panel.ai"))


def handle_pending_execute(pending_id):
    g = _require_super()
    if g:
        return g
    try:
        from giso.ai_runtime import execute_pending_action
        from flask_login import current_user
        result = execute_pending_action(int(pending_id), str(getattr(current_user, "id", "") or "panel"))
        flash(str(result.get("text") or "—"), "success" if not result.get("error") else "danger")
    except Exception as e:
        logger.error(f"panel ai pending execute: {e}")
        flash(f"خطا: {str(e)[:100]}", "danger")
    return redirect(url_for("panel.ai"))


def handle_pending_cancel(pending_id):
    g = _require_super()
    if g:
        return g
    try:
        from giso.ai_runtime import cancel_pending_action
        from flask_login import current_user
        result = cancel_pending_action(int(pending_id), str(getattr(current_user, "id", "") or "panel"))
        flash(str(result.get("text") or "—"), "success" if not result.get("error") else "danger")
    except Exception as e:
        logger.error(f"panel ai pending cancel: {e}")
        flash(f"خطا: {str(e)[:100]}", "danger")
    return redirect(url_for("panel.ai"))


def handle_rollback(log_id):
    g = _require_super()
    if g:
        return g
    try:
        from giso.ai_runtime import rollback_action_log
        from flask_login import current_user
        result = rollback_action_log(int(log_id), str(getattr(current_user, "id", "") or "panel"))
        flash(str(result.get("text") or "—"), "success" if not result.get("error") else "danger")
    except Exception as e:
        logger.error(f"panel ai rollback: {e}")
        flash(f"خطا: {str(e)[:100]}", "danger")
    return redirect(url_for("panel.ai"))


# ───────────────────── context ─────────────────────

def context():
    data = {}
    try:
        from giso.ai_runtime import (
            get_runtime_overview, list_provider_options, get_failover_chain,
            get_role_policy, get_role_capabilities, get_widget_config,
            get_widget_usage_stats, get_recent_pending_actions,
            get_recent_action_logs, get_recent_rollback_logs,
            build_provider_status_report,
        )
        data["runtime"] = get_runtime_overview() or {}
        grouped = list_provider_options() or {}
        chain = list(get_failover_chain() or [])
        rows = []
        for bucket, items in grouped.items():
            for item in items or []:
                row = dict(item)
                pname = str(row.get("name") or "")
                row["bucket"] = bucket
                row["failover_index"] = (chain.index(pname) + 1) if pname in chain else 0
                try:
                    from giso.ai_brain import get_ai_provider, _effective_base_url, _col, provider_family_of
                    row["family"] = provider_family_of(pname)
                    prov = get_ai_provider(pname)
                    if prov:
                        row["display_name"] = str(_col(prov, "display_name", "") or "")
                        row["verify_status"] = str(_col(prov, "last_status", "") or "")
                        row["verify_error"] = str(_col(prov, "last_error", "") or "")
                        row["is_cloudflare"] = str(prov["kind"] or "").strip().lower() == "cloudflare"
                        row["base_url"] = str(prov["base_url"] or "")
                        row["api_root"] = str(prov["api_root"] or "")
                        row["use_proxy"] = bool(prov["use_proxy"])
                        row["has_api_key"] = bool(str(prov["api_key"] or "").strip())
                        # فاز ۲: ستون‌های جدید جدول پروایدرها
                        import json as _json
                        try:
                            vm = _json.loads(_col(prov, "vision_models_json", "") or "[]")
                            row["vision_count"] = len([m for m in vm if not (isinstance(m, dict) and m.get("disabled"))])
                        except Exception:
                            row["vision_count"] = 0
                        try:
                            tm = _json.loads(_col(prov, "text_models_json", "") or "[]")
                            row["text_count"] = len([m for m in tm if not (isinstance(m, dict) and m.get("disabled"))])
                        except Exception:
                            row["text_count"] = 0
                        row["proxy_url"] = str(_col(prov, "proxy_url", "") or "")
                        row["models_last_updated"] = str(_col(prov, "models_last_updated", "") or "")
                        row["models_last_updated_fa"] = _relative_time_fa(row["models_last_updated"])
                        row["models_source"] = str(_col(prov, "models_source", "") or "")
                        row["discovery_report"] = str(_col(prov, "discovery_report", "") or "")
                        # اسم مدل‌های کشف‌شده (Vision + Text) برای انتخاب در کارت پروایدر
                        try:
                            _ids = []
                            _raw_models = (
                                list(_json.loads(_col(prov, "vision_models_json", "") or "[]"))
                                + list(_json.loads(_col(prov, "text_models_json", "") or "[]"))
                            )
                            for _m in _raw_models:
                                _mid = str((_m.get("id") if isinstance(_m, dict) else _m) or "").strip()
                                if _mid and not (isinstance(_m, dict) and _m.get("disabled")) and _mid not in _ids:
                                    _ids.append(_mid)
                            row["discovered_models"] = _ids[:80]
                        except Exception:
                            row["discovered_models"] = []
                        if row.get("family") == "gemini":
                            row["effective_base_url"] = _effective_base_url("gemini", row["base_url"])
                            row["connects_via_worker"] = "workers.dev" in (row["effective_base_url"] or "").lower()
                        if row.get("is_cloudflare"):
                            try:
                                from giso.ai_brain import cloudflare_account_id_from_url
                                from giso.ai_models_registry import get_image_models
                                row["cloudflare_account_id"] = cloudflare_account_id_from_url(row.get("api_root") or row.get("base_url") or "")
                                _image_models = get_image_models("cloudflare") or []
                                row["cloudflare_image_model_default"] = str(
                                    _image_models[0].get("id") if _image_models and isinstance(_image_models[0], dict) else (_image_models[0] if _image_models else "")
                                )
                            except Exception:
                                row["cloudflare_account_id"] = ""
                                row["cloudflare_image_model_default"] = ""
                except Exception:
                    pass
                rows.append(row)
        # حساب‌های هر خانواده (مثلاً چند Cloudflare) کنار هم نمایش داده شوند؛ ترتیب داخل گروه حفظ می‌شود.
        rows.sort(key=lambda r: str(r.get("family") or r.get("name") or ""))
        data["providers"] = rows
        data["failover_chain"] = chain
        # فاز ۲: گزینه‌های فرم افزودن از رجیستری مرکزی
        try:
            from giso.ai_models_registry import PROVIDERS as _REG_PROVIDERS
            data["registry_options"] = [
                {
                    "name": n,
                    "display": (d.get("display_name", n) + (" / cf" if n == "cloudflare" else "")),
                }
                for n, d in _REG_PROVIDERS.items()
            ]
        except Exception:
            data["registry_options"] = []
        try:
            from giso.buti_ai.ai_models import panel_slots_context
            from giso.panel.modules.ai_categories import build_category_view
            data["beauty_mirror"] = build_category_view(panel_slots_context())
        except Exception as mirror_exc:
            logger.error(f"panel ai beauty mirror context: {mirror_exc}")
            data["beauty_mirror"] = {"slots": [], "providers": [], "model_options": []}
        data["policies"] = {
            "user": get_role_policy("user"),
            "admin": get_role_policy("admin"),
            "super": get_role_policy("super"),
        }
        data["capabilities"] = {
            "user": get_role_capabilities("user"),
            "admin": get_role_capabilities("admin"),
            "super": get_role_capabilities("super"),
        }
        data["widget"] = get_widget_config() or {}
        data["widget_usage"] = get_widget_usage_stats() or {}
        try:
            from giso.ai_credits import credit_settings, admin_credit_users
            data["credit_settings"] = credit_settings()
            data["credit_users"] = admin_credit_users(limit=200)
        except Exception as credit_exc:
            # اعتبار یک بخش جانبی پنل است؛ خرابی/مهاجرت ناقص آن نباید کارت‌های Provider را مخفی کند.
            logger.error("panel ai credit context: %s", credit_exc)
            data["credit_settings"] = {"enabled": False, "cost": 1, "scope": "spend"}
            data["credit_users"] = []
        data["pending"] = get_recent_pending_actions(limit=10)
        data["logs"] = get_recent_action_logs(limit=10)
        data["rollbacks"] = get_recent_rollback_logs(limit=10)
        try:
            data["status_report"] = build_provider_status_report()
        except Exception:
            data["status_report"] = ""
    except Exception as e:
        logger.error(f"panel ai: {e}")
        data = {}
    return {"ai": data}


def _first_discovered_model(provider_name):
    """اولین مدل کشف‌شده (Vision اول) از منطق مشترک ai_brain."""
    from giso.ai_brain import first_discovered_model
    return first_discovered_model(provider_name)


def handle_custom_model_add():
    """مسیر قدیمی فرم «مدل دلخواه»؛ اکنون همان منطق فرم واحد با گزینهٔ custom."""
    g = _require_super()
    if g:
        return g
    return _create_provider_from_form("custom")
