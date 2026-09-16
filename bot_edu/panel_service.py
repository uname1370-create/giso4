# -*- coding: utf-8 -*-
"""
panel_service — façade سازگار با import قدیمی.
منطق واقعی در services/panel_service.py قرار دارد.
"""
from services.panel_service import (  # noqa: F401
    PanelItem,
    PUBLIC_ITEMS, USER_PANEL_ITEMS, MENTOR_ITEMS, SITE_ADMIN_ITEMS,
    public_items, user_panel_items, mentor_items, site_admin_items, find_item,
)
