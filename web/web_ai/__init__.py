# -*- coding: utf-8 -*-
"""
web/web_ai/__init__.py — پکیج هوش مصنوعی وب‌سایت

⚠️ برای استفاده از هوش مصنوعی در هر جای سایت:
   from web_ai import ask, chat, status, list_active_ais

⚠️ برای گزارش‌گیری از ربات:
   from web_ai import get_status_report, run_live_check
"""
from .ai_gateway import ask, chat, status, list_active_ais
from .ai_engine import check_ai_status, call_ai
from .guest_interviewer import interviewer_chat
from .guest_analyzer import analyze_guest_paths
from .ai_monitor import (
    get_status_report,
    run_live_check,
    format_status_for_telegram,
    format_live_check_for_telegram,
)

__all__ = [
    # لایه جدید (توصیه‌شده)
    "ask", "chat", "status", "list_active_ais",
    # سازگاری قدیم
    "check_ai_status", "call_ai",
    "interviewer_chat", "analyze_guest_paths",
    # مانیتور برای ربات
    "get_status_report", "run_live_check",
    "format_status_for_telegram", "format_live_check_for_telegram",
]