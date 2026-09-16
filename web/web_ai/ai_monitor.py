# -*- coding: utf-8 -*-
"""
web/web_ai/ai_monitor.py
گزارش‌گیر وضعیت هوش مصنوعی سایت برای پنل مدیریت ربات
این فایل توسط ربات فراخوانی می‌شود تا وضعیت AI سایت را گزارش دهد.
"""
import time
import logging
from typing import Dict, Any, List
from .ai_gateway import list_active_ais, status as _status
from .ai_engine import call_ai as _call

logger = logging.getLogger("web.web_ai.monitor")


# ═══════════════════════════════════════════════════════════
# ۱) گزارش وضعیت (سریع - بدون تست زنده)
# ═══════════════════════════════════════════════════════════
def get_status_report() -> Dict[str, Any]:
    """
    گزارش سریع وضعیت AI بدون فراخوانی زنده.
    فقط از دیتابیس می‌خواند.
    """
    try:
        overall = _status()
        active_list = list_active_ais()

        return {
            "ok": True,
            "connected": overall.get("connected", False),
            "total_active": len(active_list),
            "providers": active_list,
            "summary": overall.get("active_provider", "نامشخص")
        }
    except Exception as e:
        logger.error(f"get_status_report error: {e}")
        return {
            "ok": False,
            "connected": False,
            "total_active": 0,
            "providers": [],
            "summary": "خطا در بررسی وضعیت",
            "error": str(e)
        }


# ═══════════════════════════════════════════════════════════
# ۲) بررسی زنده (تست واقعی هر AI)
# ═══════════════════════════════════════════════════════════
def run_live_check() -> Dict[str, Any]:
    """
    تست زنده همه AIهای فعال با یک پیام کوتاه.
    زمان پاسخ هر کدام را می‌سنجد.
    """
    try:
        active_list = list_active_ais()
        if not active_list:
            return {
                "ok": False,
                "message": "هیچ AI فعالی برای تست یافت نشد",
                "results": []
            }

        results = []
        test_prompt = "سلام. فقط با یک کلمه پاسخ بده: OK"

        for ai in active_list:
            name = ai.get("name", "؟")
            model = ai.get("model", "؟")

            start = time.time()
            try:
                # تست ساده با نام provider مشخص
                msgs = [
                    {"role": "system", "content": f"[preferred_provider={name}]"},
                    {"role": "user", "content": test_prompt}
                ]
                reply = _call(msgs, max_tokens=20)
                elapsed = round(time.time() - start, 2)

                if reply and len(reply.strip()) > 0:
                    status_txt = "healthy"
                    icon = "✅"
                else:
                    status_txt = "empty_reply"
                    icon = "⚠️"

                results.append({
                    "name": name,
                    "model": model,
                    "status": status_txt,
                    "icon": icon,
                    "response_time": elapsed,
                    "reply_preview": (reply or "")[:50]
                })
            except Exception as e:
                elapsed = round(time.time() - start, 2)
                results.append({
                    "name": name,
                    "model": model,
                    "status": "failed",
                    "icon": "❌",
                    "response_time": elapsed,
                    "error": str(e)[:80]
                })

        healthy_count = sum(1 for r in results if r["status"] == "healthy")

        return {
            "ok": True,
            "total_tested": len(results),
            "healthy": healthy_count,
            "failed": len(results) - healthy_count,
            "results": results
        }
    except Exception as e:
        logger.error(f"run_live_check error: {e}")
        return {
            "ok": False,
            "message": f"خطا در بررسی زنده: {e}",
            "results": []
        }


# ═══════════════════════════════════════════════════════════
# ۳) قالب‌بندی برای نمایش در ربات (پیام تلگرام/بله)
# ═══════════════════════════════════════════════════════════
def format_status_for_telegram(report: Dict[str, Any]) -> str:
    """
    گزارش سریع را به متن آماده برای ربات تبدیل می‌کند.
    """
    if not report.get("ok"):
        return f"❌ خطا در دریافت وضعیت AI سایت:\n{report.get('error', 'نامشخص')}"

    connected = "✅ متصل و فعال" if report.get("connected") else "❌ قطع"
    total = report.get("total_active", 0)
    providers = report.get("providers", [])

    lines = [
        "📊 <b>وضعیت هوش مصنوعی سایت</b>",
        "",
        f"وضعیت کلی: {connected}",
        f"تعداد AI فعال: <b>{total}</b>",
        "━━━━━━━━━━━━━━━",
    ]

    if not providers:
        lines.append("⚠️ هیچ AI فعالی ثبت نشده است.")
    else:
        for p in providers:
            name = p.get("name", "؟")
            model = p.get("model", "پیش‌فرض")
            last_ok = p.get("last_ok") or "هرگز"
            iranian = "🇮🇷 " if p.get("is_iranian") else "🌐 "

            lines.append(f"")
            lines.append(f"{iranian}<b>{name}</b>")
            lines.append(f"   📌 مدل: {model}")
            lines.append(f"   ⏱ آخرین تست موفق: {last_ok}")

    lines.append("")
    lines.append("━━━━━━━━━━━━━━━")
    lines.append("💡 برای تست زنده، دکمه «بررسی هوش مصنوعی» را بزنید.")

    return "\n".join(lines)


def format_live_check_for_telegram(report: Dict[str, Any]) -> str:
    """
    نتیجه بررسی زنده را به متن آماده برای ربات تبدیل می‌کند.
    """
    if not report.get("ok"):
        return f"❌ {report.get('message', 'خطای نامشخص')}"

    total = report.get("total_tested", 0)
    healthy = report.get("healthy", 0)
    failed = report.get("failed", 0)
    results = report.get("results", [])

    lines = [
        "🔍 <b>نتیجه بررسی زنده هوش مصنوعی سایت</b>",
        "",
        f"📊 مجموع تست شده: <b>{total}</b>",
        f"✅ سالم: <b>{healthy}</b>",
        f"❌ خراب: <b>{failed}</b>",
        "━━━━━━━━━━━━━━━",
    ]

    for r in results:
        icon = r.get("icon", "•")
        name = r.get("name", "؟")
        model = r.get("model", "؟")
        rt = r.get("response_time", 0)
        status_txt = r.get("status", "")

        lines.append("")
        lines.append(f"{icon} <b>{name}</b>")
        lines.append(f"   📌 مدل: {model}")
        lines.append(f"   ⏱ زمان پاسخ: {rt} ثانیه")

        if status_txt == "healthy":
            preview = r.get("reply_preview", "")
            lines.append(f"   💬 پاسخ: {preview}")
        elif status_txt == "failed":
            err = r.get("error", "")
            lines.append(f"   ⚠️ خطا: {err}")
        elif status_txt == "empty_reply":
            lines.append(f"   ⚠️ پاسخ خالی برگشت")

    lines.append("")
    lines.append("━━━━━━━━━━━━━━━")

    if healthy == total:
        lines.append("🎉 همه AIهای سایت سالم هستند!")
    elif healthy == 0:
        lines.append("🚨 هیچ AI فعالی پاسخ نداد!")
    else:
        lines.append(f"⚠️ {failed} AI نیاز به بررسی دارد.")

    return "\n".join(lines)