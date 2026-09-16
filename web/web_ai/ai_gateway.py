# -*- coding: utf-8 -*-
"""
web/web_ai/ai_gateway.py
لایه استفاده از هوش مصنوعی برای بقیه سایت
تنها فایلی که ایجنت باید بشناسد.
"""
import logging
from typing import Dict, Any, List
from .ai_engine import call_ai as _engine_call, check_ai_status

logger = logging.getLogger("web.web_ai.gateway")


def ask(prompt: str, provider: str | None = None, max_tokens: int = 800) -> str:
    """سؤال ساده از هوش مصنوعی"""
    try:
        if provider:
            msgs = [
                {"role": "system", "content": f"[preferred_provider={provider}]"},
                {"role": "user", "content": prompt}
            ]
        else:
            msgs = [{"role": "user", "content": prompt}]
        return _engine_call(msgs, max_tokens=max_tokens)
    except Exception as e:
        logger.error(f"ai_gateway.ask error: {e}")
        return ""


def chat(messages: List[Dict[str, str]], provider: str | None = None, max_tokens: int = 800) -> str:
    """گفتگوی چند نوبتی با تاریخچه"""
    try:
        return _engine_call(messages, max_tokens=max_tokens)
    except Exception as e:
        logger.error(f"ai_gateway.chat error: {e}")
        return ""


def status() -> Dict[str, Any]:
    """وضعیت فعلی هوش مصنوعی سایت"""
    return check_ai_status()


def list_active_ais() -> List[Dict[str, Any]]:
    """لیست هوش مصنوعی‌های فعال با مدل‌هایشان"""
    try:
        import ai_brain as _ab
        provs = _ab.list_ai_providers(only_enabled=True)
        result = []
        for row in provs:
            p = dict(row)
            api_key = str(p.get("api_key") or "").strip()
            if p.get("enabled") and api_key:
                result.append({
                    "name": p.get("name", ""),
                    "model": p.get("selected_model") or p.get("last_model") or "پیش‌فرض",
                    "is_iranian": bool(p.get("is_iranian")),
                    "last_ok": p.get("last_ok", "")
                })
        return result
    except Exception as e:
        logger.error(f"ai_gateway.list_active_ais error: {e}")
        return []