# -*- coding: utf-8 -*-
"""Beauty Centers: a modular, introduction-only directory for Giso."""
from flask import Blueprint

beauty_centers_bp = Blueprint(
    "beauty_centers",
    __name__,
    template_folder="templates",
    static_folder="static",
    static_url_path="/beauty-centers-static",
)

from giso.beauty_centers import routes  # noqa: E402,F401
from giso.beauty_centers.pricing import routes as pricing_routes  # noqa: E402,F401

__all__ = ["beauty_centers_bp"]
