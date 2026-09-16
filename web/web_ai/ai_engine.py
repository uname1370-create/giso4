# -*- coding: utf-8 -*-
"""
web/web_ai/ai_engine.py
پل ارتباطی امن وب‌سایت با موتور هوش مصنوعی ربات
بدون دستکاری دیتابیس، فقط خواندن پرووایدر و ارسال پیام.
"""
import asyncio
import logging
from typing import List, Dict, Any

# فراخوانی مستقیم از موتور ربات (bot_edu/ai_brain.py)
import ai_brain as _ab

logger = logging.getLogger("web.web_ai.ai_engine")


def check_ai_status() -> Dict[str, Any]:
    """بررسی وضعیت کلیدهای AI ثبت‌شده توسط ربات"""
    try:
        provs = _ab.list_ai_providers(only_enabled=True)
        if not provs:
            return {
                "connected": False,
                "active_provider": "در انتظار کلید API",
                "provider_count": 0,
                "has_key": False
            }

        # اولین پرووایدر فعال با کلید
        for row in provs:
            p = dict(row)
            api_key = str(p.get("api_key") or "").strip()
            if p.get("enabled") and api_key:
                return {
                    "connected": True,
                    "active_provider": p.get("name", "فعال"),
                    "provider_count": len(provs),
                    "has_key": True
                }

        return {
            "connected": False,
            "active_provider": "در انتظار کلید API",
            "provider_count": len(provs),
            "has_key": False
        }
    except Exception as e:
        logger.error(f"ai_engine check_ai_status error: {e}")
        return {
            "connected": False,
            "active_provider": "خطای ارتباط",
            "provider_count": 0,
            "has_key": False
        }


def call_ai(messages: List[Dict[str, str]] | str, max_tokens: int = 800) -> str:
    """ارسال پیام به موتور AI ربات و دریافت پاسخ"""
    try:
        # ── ساخت آرایه پیام‌ها ──
        if isinstance(messages, str):
            msgs = [{"role": "user", "content": messages}]
        else:
            msgs = []
            for m in messages:
                role = m.get("role", "user")
                if role not in ("system", "user", "assistant"):
                    role = "user"
                content = m.get("content") or m.get("text") or ""
                if content.strip():
                    msgs.append({"role": role, "content": content})

        if not msgs:
            return ""

        # ── اجرای ایمن async در محیط sync ──
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = None

        if loop and loop.is_running():
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as pool:
                res = pool.submit(
                    asyncio.run,
                    _ab.ask_ai_fast(msgs, max_tokens=max_tokens)
                ).result()
        else:
            res = asyncio.run(_ab.ask_ai_fast(msgs, max_tokens=max_tokens))

        # ── استخراج پاسخ ──
        if isinstance(res, dict) and res.get("ok"):
            return (res.get("text") or "").strip()

        logger.warning(f"AI call_ai error: {res}")
        return ""
    except Exception as e:
        logger.error(f"ai_engine.call_ai failed: {e}")
        return ""