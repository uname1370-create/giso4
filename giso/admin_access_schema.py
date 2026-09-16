# -*- coding: utf-8 -*-
"""Deprecated compatibility shim for the removed admin-access editor.

The approved normal-admin role is now fixed in :mod:`giso.panel.permissions`.
The empty schema keeps imports from an older worker safe without exposing or
persisting per-admin ``sub_options``.
"""

ADMIN_ACCESS_SCHEMA = {}


def section_options(section, channel):
    return []


__all__ = ["ADMIN_ACCESS_SCHEMA", "section_options"]
