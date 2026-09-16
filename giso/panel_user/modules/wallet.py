# -*- coding: utf-8 -*-
"""پنل کاربر: کیف پول واحد، مأموریت، افزایش موجودی و تسویه cash."""
from flask import request

from giso.panel_user.modules._base import get_wallet

VALID_TABS = {"summary", "missions", "topup", "settlement"}


def context():
    tab = (request.args.get("tab") or "summary").strip().lower()
    if tab not in VALID_TABS:
        tab = "summary"
    return {"wallet": get_wallet() or {}, "wallet_tab": tab}
