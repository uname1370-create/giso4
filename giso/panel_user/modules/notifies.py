# -*- coding: utf-8 -*-
"""panel_user/modules/notifies.py — اعلان موجودی محصولات."""
from giso.panel_user.modules._base import get_stock_notifies


def context():
    return {"stock_notifies": get_stock_notifies()}
