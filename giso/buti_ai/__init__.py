# -*- coding: utf-8 -*-
"""
giso/buti_ai/__init__.py — ماژول بومی آینه جادویی گیسو (پیش‌نمایش چهره و زیبایی).
"""
from flask import Blueprint

buti_ai_bp = Blueprint(
    "buti_ai",
    __name__,
    url_prefix="/analysis/mirror",
    template_folder="templates",
    static_folder="static",
)

from giso.buti_ai import routes  # noqa: E402, F401
