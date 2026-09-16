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


def handle_provider_add():
    """فاز ۲: فقط «نام سرویس + کلید API» الزامی است؛ بقیه خودکار از رجیستری."""
    g = _require_super()
    if g:
        return g
    name = (request.form.get("name") or "").strip().lower()
    if not name:  # گزینه «نام دلخواه» از منو → فیلد متنی
        name = (request.form.get("custom_name") or "").strip().lower()
    api_key = (request.form.get("api_key") or "").strip()
    if not name or not api_key:
        flash("نام سرویس و کلید API الزامی هستند.", "warning")
        return redirect(url_for("panel.ai"))

    from giso.ai_models_registry import get_provider as _reg_provider
    import json as _json
    registry_data = _reg_provider(name)

    if registry_data:
        base_url = (request.form.get("base_url") or "").strip() or registry_data["base_url"]
        kind = (request.form.get("kind") or "").strip().lower() or registry_data["kind"]
        try:
            timeout = max(5, min(120, int(request.form.get("timeout") or registry_data["timeout"])))
        except (TypeError, ValueError):
            timeout = registry_data["timeout"]
        is_iranian = registry_data["is_iranian"]
        vision_models = registry_data.get("vision_models", [])
        text_models = registry_data.get("text_models", [])
        from giso.ai_models_registry import get_best_vision_model, get_best_text_model
        model = (request.form.get("selected_model") or "").strip() \
            or get_best_vision_model(name) or get_best_text_model(name) or ""
        models_source = "registry"
    else:
        base_url = (request.form.get("base_url") or "").strip()
        if not base_url:
            flash("برای سرویس ناشناخته، آدرس پایه (Base URL) الزامی است.", "warning")
            return redirect(url_for("panel.ai"))
        kind = (request.form.get("kind") or "").strip().lower() or "openai"
        if kind not in ("openai", "cloudflare"):
            kind = "openai"
        try:
            timeout = max(5, min(120, int(request.form.get("timeout") or 20)))
        except (TypeError, ValueError):
            timeout = 20
        is_iranian = request.form.get("is_iranian") == "1"
        vision_models = []
        text_models = []
        model = (request.form.get("selected_model") or "").strip()
        models_source = "manual"

    if name == "gemini":
        from giso.ai_brain import _normalize_gemini_base_url
        base_url = _normalize_gemini_base_url(base_url)
    if base_url and not _valid_base_url(base_url):
        flash("Base URL نامعتبر است (باید با http:// یا https:// شروع شود).", "warning")
        return redirect(url_for("panel.ai"))

    use_proxy = request.form.get("use_proxy") == "1"
    if name == "gemini":
        use_proxy = False
    proxy_url = (request.form.get("proxy_url") or "").strip()
    proxy_type = _proxy_type_of(proxy_url)
    if proxy_url and not proxy_type:
        flash("آدرس پروکسی باید با socks5:// یا http:// شروع شود.", "warning")
        return redirect(url_for("panel.ai"))

    try:
        from giso.ai_brain import add_ai_provider, save_provider_to_env
        ok = add_ai_provider(
            name=name, kind=kind, api_key=api_key, base_url=base_url,
            api_root=base_url, timeout=timeout, is_iranian=is_iranian,
            selected_model=model, enabled=True, use_proxy=use_proxy, replace=True,
            vision_models_json=_json.dumps(vision_models, ensure_ascii=False),
            text_models_json=_json.dumps(text_models, ensure_ascii=False),
            models_source=models_source,
            proxy_url=proxy_url, proxy_type=proxy_type,
        )
        if ok:
            try:
                save_provider_to_env(name=name, api_key=api_key, base_url=base_url,
                                     model=model, enabled=True, proxy=use_proxy,
                                     iranian=is_iranian, timeout=timeout)
            except Exception:
                pass
            # شناسایی خودکار مدل‌های زنده از /models (بدون شکست در صورت خطا)
            try:
                from giso.ai_brain import refresh_models
                res = refresh_models(name)
                if res.get("ok"):
                    flash(f"✅ سرویس «{name}» اضافه شد — {res['vision_count']} مدل Vision + "
                          f"{res['text_count']} مدل Text شناسایی شد.", "success")
                else:
                    flash(f"✅ سرویس «{name}» اضافه شد. برای شناسایی مدل‌ها روی دکمه 🔄 کلیک کنید. "
                          f"({str(res.get('error') or '')[:80]})", "success")
            except Exception as re_:
                logger.error(f"panel ai refresh after add: {re_}")
                flash(f"✅ سرویس «{name}» اضافه شد. برای شناسایی مدل‌ها روی دکمه 🔄 کلیک کنید.", "success")
        else:
            flash("خطا در افزودن پروایدر.", "danger")
    except Exception as e:
        logger.error(f"panel ai provider add: {e}")
        flash(f"خطا: {str(e)[:100]}", "danger")
    return redirect(url_for("panel.ai"))


def handle_provider_toggle(name):
    g = _require_super()
    if g:
        return g
    try:
        from giso.ai_brain import toggle_ai_provider
        new_val = toggle_ai_provider(name)
        if new_val is None:
            flash("پروایدر پیدا نشد.", "danger")
        else:
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
        from giso.ai_brain import toggle_use_proxy
        new_val = toggle_use_proxy(name)
        if new_val is None:
            flash("پروایدر پیدا نشد.", "danger")
        else:
            flash(f"پروکسی Gemini برای «{name}» {'فعال' if new_val else 'غیرفعال'} شد.", "success")
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
        from giso.ai_brain import update_ai_provider_field, get_ai_provider, save_provider_to_env
        # فاز ۲ (۲.۸): اگر api_key از خالی به پر تغییر کرد → فعال‌سازی خودکار
        old_row = get_ai_provider(name)
        old_api_key = str(old_row["api_key"] or "").strip() if old_row else ""
        if field == "proxy_url":
            update_ai_provider_field(name, "proxy_url", value)
            from giso.ai_brain import get_conn, _lock
            conn = get_conn()
            with _lock, conn:
                conn.execute("UPDATE giso_ai_providers SET proxy_type=? WHERE name=?",
                             (_proxy_type_of(value), name))
            ok = True
        else:
            ok = update_ai_provider_field(name, field, value)
        if ok:
            auto_enabled = False
            if field == "api_key" and not old_api_key and value and old_row and not old_row["enabled"]:
                from giso.ai_brain import toggle_ai_provider
                toggle_ai_provider(name)
                auto_enabled = True
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
                    )
            except Exception:
                pass
            extra = " و پروایدر فعال شد" if auto_enabled else ""
            flash(f"فیلد «{field}» پروایدر «{name}» ذخیره شد{extra} (دیتابیس + .env).", "success")
            # فاز ۲ (۲.۸): با تغییر کلید یا آدرس، مدل‌ها خودکار تازه شوند
            if field in ("api_key", "base_url"):
                try:
                    from giso.ai_brain import refresh_models
                    res = refresh_models(name)
                    if res.get("ok"):
                        flash(f"🔄 مدل‌ها به‌روزرسانی شد: {res['vision_count']} Vision + {res['text_count']} Text", "success")
                except Exception as re_:
                    logger.error(f"panel ai refresh after update: {re_}")
        else:
            flash("خطا در ذخیره فیلد.", "danger")
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
                    from giso.ai_brain import get_ai_provider, _effective_base_url, _col
                    prov = get_ai_provider(pname)
                    if prov:
                        row["base_url"] = str(prov["base_url"] or "")
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
                        if pname.lower() == "gemini":
                            row["effective_base_url"] = _effective_base_url("gemini", row["base_url"])
                            row["connects_via_worker"] = "workers.dev" in (row["effective_base_url"] or "").lower()
                except Exception:
                    pass
                rows.append(row)
        data["providers"] = rows
        data["failover_chain"] = chain
        # فاز ۲: گزینه‌های فرم افزودن از رجیستری مرکزی
        try:
            from giso.ai_models_registry import PROVIDERS as _REG_PROVIDERS
            data["registry_options"] = [
                {"name": n, "display": d.get("display_name", n)}
                for n, d in _REG_PROVIDERS.items()
            ]
        except Exception:
            data["registry_options"] = []
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
        from giso.ai_credits import credit_settings, admin_credit_users
        data["credit_settings"] = credit_settings()
        data["credit_users"] = admin_credit_users(limit=200)
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
