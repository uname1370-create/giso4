# -*- coding: utf-8 -*-
"""پنل کاربر: پنج نمای ساده بازارچه مو."""
from flask_login import current_user

from giso.marketplace.services import user_marketplace_context


def context():
    return user_marketplace_context(current_user)
