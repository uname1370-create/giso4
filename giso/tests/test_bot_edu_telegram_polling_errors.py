"""Telegram polling errors must not leave a 'connected' bot retrying forever.

PTB 20.7 keeps retrying getUpdates after every TelegramError and leaves
updater.running=True. platform_runtime stops the app after a streak of errors.
"""
from __future__ import annotations

import asyncio
from types import SimpleNamespace

import bot
import platform_runtime
from config import SETTINGS


class _FakeUpdater:
    def __init__(self):
        self.running = False
        self.poll_kwargs = None

    async def start_polling(self, **kwargs):
        self.poll_kwargs = kwargs
        self.running = True


def _fake_app():
    updater = _FakeUpdater()

    async def _noop(*a, **k):
        return None

    return SimpleNamespace(
        updater=updater,
        running=True,
        bot=object(),
        initialize=_noop,
        start=_noop,
        stop=_noop,
        shutdown=_noop,
    )


def _reset_state(monkeypatch, app):
    monkeypatch.setitem(platform_runtime._STATE, "app", app)
    monkeypatch.setitem(platform_runtime._STATE, "proxy", None)


def _record_stops(monkeypatch):
    calls = []

    async def fake_stop():
        calls.append(True)
        return True, "stopped"

    monkeypatch.setattr(platform_runtime, "stop_telegram", fake_stop)
    return calls


def _clock(monkeypatch, start=1000.0):
    now = {"t": start}
    monkeypatch.setattr(platform_runtime, "_now", lambda: now["t"])
    return now


def test_errors_below_limit_do_not_stop(monkeypatch):
    app = _fake_app()
    _reset_state(monkeypatch, app)
    stops = _record_stops(monkeypatch)
    _clock(monkeypatch)
    cb = platform_runtime.make_polling_error_callback(app)

    async def run():
        for _ in range(platform_runtime.POLL_ERROR_LIMIT - 1):
            cb(RuntimeError("Server disconnected"))
        await asyncio.sleep(0)

    asyncio.run(run())
    assert stops == []


def test_error_streak_at_limit_stops_the_live_app_once(monkeypatch):
    app = _fake_app()
    _reset_state(monkeypatch, app)
    stops = _record_stops(monkeypatch)
    _clock(monkeypatch)
    cb = platform_runtime.make_polling_error_callback(app)

    async def run():
        for _ in range(platform_runtime.POLL_ERROR_LIMIT + 5):
            cb(RuntimeError("Server disconnected"))
        await asyncio.sleep(0)
        await asyncio.sleep(0)

    asyncio.run(run())
    assert stops == [True]


def test_stale_app_is_not_stopped(monkeypatch):
    old_app = _fake_app()
    new_app = _fake_app()
    _reset_state(monkeypatch, new_app)
    stops = _record_stops(monkeypatch)
    _clock(monkeypatch)
    cb = platform_runtime.make_polling_error_callback(old_app)

    async def run():
        for _ in range(platform_runtime.POLL_ERROR_LIMIT):
            cb(RuntimeError("Server disconnected"))
        await asyncio.sleep(0)
        await asyncio.sleep(0)

    asyncio.run(run())
    assert stops == []


def test_spaced_errors_do_not_accumulate(monkeypatch):
    app = _fake_app()
    _reset_state(monkeypatch, app)
    stops = _record_stops(monkeypatch)
    clock = _clock(monkeypatch)
    cb = platform_runtime.make_polling_error_callback(app)

    async def run():
        for _ in range(platform_runtime.POLL_ERROR_LIMIT * 3):
            clock["t"] += platform_runtime.POLL_ERROR_WINDOW_SEC + 1
            cb(RuntimeError("Server disconnected"))
        await asyncio.sleep(0)
        await asyncio.sleep(0)

    asyncio.run(run())
    assert stops == []


def test_runtime_start_passes_error_callback_to_polling(monkeypatch):
    app = _fake_app()
    monkeypatch.setitem(SETTINGS, "telegram_enabled", "1")
    monkeypatch.setitem(SETTINGS, "telegram_token", "test-token")
    monkeypatch.setitem(platform_runtime._STATE, "app", None)
    monkeypatch.setitem(platform_runtime._STATE, "proxy", None)

    async def builder():
        return app, None

    monkeypatch.setitem(platform_runtime._STATE, "builder", builder)
    monkeypatch.setattr(platform_runtime, "register_platform_bot", lambda *a: None)

    ok, _ = asyncio.run(platform_runtime.start_telegram())

    assert ok is True
    assert callable(app.updater.poll_kwargs.get("error_callback"))
    assert app.updater.poll_kwargs.get("drop_pending_updates") is True


def test_bot_start_polling_passes_error_callback(monkeypatch):
    app = _fake_app()
    sentinel = object()

    ok = asyncio.run(
        bot._start_polling(app, "تلگرام", already_initialized=True, error_callback=sentinel)
    )

    assert ok is True
    assert app.updater.poll_kwargs["error_callback"] is sentinel
