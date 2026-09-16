# -*- coding: utf-8 -*-
"""giso/site_jobs.py — hook‌های پس‌زمینه‌ی best-effort وب‌اپ گیسو.

سه hook اینجا جمع شده‌اند تا giso/app.py زیر سقف ۲٬۱۴۲ خط بماند؛ رفتار،
throttle و نام thread دقیقاً همان است که قبلاً داخل create_app بود:
  - giso_daily_marketing_digest   : گزارش بازاریابی روزانه (حداکثر یک‌بار در روز)
  - giso_rank_credit_deposit      : تریگر واریز شبانه‌ی اعتبار رتبه (۲۳:۵۹)
  - giso_broadcast_site_drain     : تخلیه‌ی صف پیام سراسری سمت سایت
هیچ‌کدام مسیر پاسخ کاربر را بلاک نمی‌کنند؛ همه‌ی خطاها بی‌صدا خورده می‌شوند.
"""
import threading
import time

from flask import request


# ── فاز P2: گزارش بازاریابی روزانه به بله سوپرادمین ──
_DIGEST_CHECK = {"last": 0.0}


# ── مرحله ۵: تریگر واریز شبانه‌ی اعتبار رتبه ──
_RANK_CREDIT_CHECK = {"last": 0.0}


# ── مرحله ۵/منو: تخلیه‌ی سبک صف پیام سراسری سمت سایت ──
_BROADCAST_SITE_CHECK = {"last": 0.0}


def install_site_background_hooks(app):
    """ثبت hook های پس‌زمینه روی app (قبلاً به‌صورت inline در create_app بود)."""

    @app.before_request
    def giso_daily_marketing_digest():
        try:
            now = time.time()
            if now - _DIGEST_CHECK["last"] < 3600:
                return None
            _DIGEST_CHECK["last"] = now
            if (request.path or "").startswith("/static/"):
                return None
            from giso.marketing import maybe_send_daily_digest
            maybe_send_daily_digest()
        except Exception:
            pass
        return None

    @app.before_request
    def giso_rank_credit_deposit():
        try:
            now_ts = time.time()
            if now_ts - _RANK_CREDIT_CHECK["last"] < 240:
                return None
            _RANK_CREDIT_CHECK["last"] = now_ts
            if (request.path or "").startswith("/static/"):
                return None
            from giso.rank_daily import maybe_deposit_rank_credits
            maybe_deposit_rank_credits()
        except Exception:
            pass
        return None

    @app.after_request
    def giso_broadcast_site_drain(response):
        try:
            now_ts = time.time()
            if now_ts - _BROADCAST_SITE_CHECK["last"] < 20:
                return response
            _BROADCAST_SITE_CHECK["last"] = now_ts

            def _drain():
                try:
                    from giso.broadcasts import process_site_bot_batch
                    for _ in range(3):  # حداکثر چند دسته در هر تریگر
                        if process_site_bot_batch(limit=5) <= 0:
                            break
                except Exception:
                    pass
            threading.Thread(target=_drain, name="broadcast-site-drain", daemon=True).start()
        except Exception:
            pass
        return response

    return app


__all__ = ["install_site_background_hooks"]
