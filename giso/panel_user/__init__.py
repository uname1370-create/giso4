# -*- coding: utf-8 -*-
"""
giso/panel_user — پنل کاربر عادی ماژولار گیسو (فاز 4.2)

- Blueprint: panel_user با url_prefix=/dashboard
- قالب‌ها: giso/panel_user/templates
- استاتیک: giso/panel_user/static
- هر ماژول در giso/panel_user/modules/<module>.py
"""
from flask import Blueprint

panel_user_bp = Blueprint(
    "panel_user",
    __name__,
    url_prefix="/dashboard",
    template_folder="templates",
    static_folder="static",
)

from giso.panel_user import routes  # noqa: E402,F401
