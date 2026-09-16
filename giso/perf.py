"""کمک‌های عملکرد HTTP — مورد ۱۹ img/help.md (تحویل ۱۴۰۵-۰۶-۱۰).

فشرده‌سازی gzip برای پاسخ‌های متنی same-origin (HTML/CSS/JS/JSON/SVG).
در لایهٔ استقرار (nginx) هم می‌توان gzip را فعال کرد؛ این لایه فقط وقتی
پاسخ هنوز Content-Encoding ندارد اعمال می‌شود تا تداخلی پیش نیاید.

قانون: این ماژول فقط میان‌افزار است؛ هیچ منطق دامنه‌ای اینجا اضافه نشود.
"""
from __future__ import annotations

import gzip
import io
import logging

logger = logging.getLogger("giso_perf")

# آستانهٔ فشرده‌سازی — پاسخ‌های کوچک‌تر ارزش overhead هدر gzip را ندارند.
_MIN_BYTES = 1024
# سطح فشرده‌سازی متعادل (سرعت/نسبت) برای پاسخ‌های زنده.
_LEVEL = 6
_MIMES = frozenset({
    "text/html", "text/css", "text/javascript", "application/javascript",
    "application/json", "text/plain", "application/xml", "image/svg+xml",
})


def _compress(resp, request) -> None:
    """در صورت صلاحیت، بدنهٔ پاسخ را gzip می‌کند (بی‌صدا خطا را نادیده می‌گیرد)."""
    if resp.status_code != 200 or resp.direct_passthrough:
        return
    if resp.headers.get("Content-Encoding"):
        return  # لایهٔ دیگری (مثلاً nginx) قبلاً فشرده کرده است
    if "gzip" not in (request.headers.get("Accept-Encoding") or "").lower():
        return
    mime = (resp.mimetype or "").split(";")[0].strip().lower()
    if mime not in _MIMES:
        return
    data = resp.get_data()
    if len(data) < _MIN_BYTES:
        return
    buf = io.BytesIO()
    with gzip.GzipFile(fileobj=buf, mode="wb", compresslevel=_LEVEL) as f:
        f.write(data)
    packed = buf.getvalue()
    if len(packed) >= len(data):
        return  # فشرده‌سازی سودی نداشت
    resp.set_data(packed)
    resp.headers["Content-Encoding"] = "gzip"
    resp.headers.add("Vary", "Accept-Encoding")
    resp.headers["Content-Length"] = str(len(packed))


def register(app):
    """میان‌افزار gzip را روی اپلیکیشن فلاسک ثبت می‌کند."""

    @app.after_request
    def _giso_gzip_text(resp):
        try:
            from flask import request
            _compress(resp, request)
        except Exception:  # هر خطا نباید پاسخ را از کار بیندازد
            logger.debug("gzip middleware skipped", exc_info=True)
        return resp

    return app
