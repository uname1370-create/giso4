# -*- coding: utf-8 -*-
"""
giso/panel — پنل ادمین ماژولار گیسو (فاز 4)

- Blueprint: panel با url_prefix=/admin
- قالب‌ها: giso/panel/templates
- استاتیک: giso/panel/static
- هر ماژول در giso/panel/modules/<module>.py
"""
from flask import Blueprint

panel_bp = Blueprint(
    "panel",
    __name__,
    url_prefix="/admin",
    template_folder="templates",
    static_folder="static",
)

from giso.panel import routes  # noqa: E402,F401
