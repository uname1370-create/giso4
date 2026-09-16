# -*- coding: utf-8 -*-
"""
mentor_service.py — (سازگاری با گذشته) re-export از services/

تمام فراخوان‌های قدیمی در bot_edu و web باید از طریق این فایل کار کنند.
منطق واقعی در services/mentor_service.py است.
"""
from __future__ import annotations
import sys
from pathlib import Path

_BOT_DIR = Path(__file__).resolve().parent
if str(_BOT_DIR) not in sys.path:
    sys.path.insert(0, str(_BOT_DIR))

from services.mentor_service import (  # noqa: F401,E402
    _ai_ready, _ai_mentor_enabled, _call_ai, _ensure_tables, _real_fallback,
    get_mentor_state, save_mentor_step, mentor_chat, mentor_feature_flags,
    mentor_profile, MENTOR_ONBOARDING_QUESTIONS, _append_chat, _bootstrap_into_ai_mentor,
)
from services.user_service import (  # noqa: F401,E402
    get_user, touch_user, get_user_rank,
    list_courses, list_shop_items, list_missions, user_progress_summary,
    create_user, get_user_by_phone, is_site_admin,
)
from services.admin_service import (  # noqa: F401,E402
    list_all_users, list_pending_cash_requests, count_open_tickets, admin_stats,
    get_user_delete_footprint, delete_user_everywhere, delete_all_users, resolve_user_id_by_phone,
)
from services.panel_service import (  # noqa: F401,E402
    public_items, user_panel_items, mentor_items, site_admin_items,
    PanelItem,
)
from services.env_service import site_admin_phones  # noqa: F401,E402


def get_or_create_user_by_phone(norm_phone: str, first_name: str = "کاربر سایت") -> dict:
    """برگرفته از user_service — برای سازگاری."""
    from services.user_service import get_user_by_phone as _by_phone, create_user as _create
    u = _by_phone(norm_phone)
    if u:
        return u
    return _create(norm_phone, first_name=first_name)
