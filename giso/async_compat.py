# -*- coding: utf-8 -*-
"""
اجرای امن coroutineها از کد sync (روت‌های Flask، کد PTB sync، اسکریپت‌ها).

چرا این فایل هست؟
- فلشک کد را در threadهای worker (بدون event loop) اجرا می‌کند؛
  پس asyncio.run() در حالت عادی کار می‌کند، ولی اگر همان thread قبلاً
  یک loop در حال اجرا داشته باشد (تست، ترد آلوده، برخی ابزارها) خطای
  «asyncio.run() cannot be called from a running event loop» می‌دهد.
- این helper سه حالت را پوشش می‌دهد:
    ۱) loop در حال اجرا در همین thread → اجرا در یک thread جدا (daemon)
    ۲) loop بسته/جدید آمادهٔ اجرا → run_until_complete
    ۳) بدون loop → asyncio.run معمولی

کاملاً سازگار با امضای قبلی: نتیجهٔ coroutine برگردانده می‌شود و
استثناها همان استثناهای قبلی‌اند (همان رفتار، فقط بدون کرش RuntimeError).
"""
from __future__ import annotations

import asyncio
import threading


def run_async_safe(coro):
    """یک coroutine را به‌صورت sync اجرا و نتیجه‌اش را برمی‌گرداند."""
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    # حالت ۱: همین thread یک loop در حال اجرا دارد → در thread مجزا
    if loop is not None and loop.is_running():
        box: dict = {}

        def _worker():
            try:
                box["result"] = asyncio.run(coro)
            except BaseException as exc:  # noqa: BLE001 - باید به thread اصلی برسد
                box["error"] = exc

        t = threading.Thread(target=_worker, daemon=True, name="giso-run-async")
        t.start()
        t.join()
        if "error" in box:
            raise box["error"]
        return box.get("result")

    # حالت ۲ و ۳: loop در حال اجرا نداریم
    try:
        return asyncio.run(coro)
    except RuntimeError:
        # گاهی یک loop بسته در thread ثبت شده؛ یک loop تازه می‌سازیم
        fresh = asyncio.new_event_loop()
        try:
            asyncio.set_event_loop(fresh)
            return fresh.run_until_complete(coro)
        finally:
            try:
                fresh.close()
            except Exception:
                pass


__all__ = ["run_async_safe"]
