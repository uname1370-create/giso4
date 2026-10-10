"""Telegram proxy path: a proxy must serve getUpdates, and outages must self-heal.

Live part: real python-telegram-bot 20.7 talking to a local fake Bot API that can
answer getMe but drop every getUpdates connection (the user-visible
'Server disconnected without sending a response' failure).
"""
from __future__ import annotations

import asyncio
import json
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest
from telegram.ext import ApplicationBuilder

import bot
import platform_runtime
from config import SETTINGS
from giso.telegram_http import build_bot_request


class FakeBotApi:
    """mode: 'ok' | 'drop' (getUpdates always dropped) | 'flaky' (every 2nd dropped)."""

    def __init__(self):
        self.mode = "ok"
        self.get_updates_calls = 0

    def outcome(self):
        self.get_updates_calls += 1
        if self.mode == "drop":
            return "drop"
        if self.mode == "flaky":
            return "drop" if self.get_updates_calls % 2 else "ok"
        return "ok"


@pytest.fixture
def fake_api():
    api = FakeBotApi()

    class Handler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def log_message(self, *args):
            pass

        def do_POST(self):
            length = int(self.headers.get("Content-Length") or 0)
            self.rfile.read(length)
            if self.path.endswith("/getUpdates"):
                if api.outcome() == "drop":
                    self.close_connection = True
                    self.connection.shutdown(2)
                    self.connection.close()
                    return
                time.sleep(0.05)
                body = {"ok": True, "result": []}
            elif self.path.endswith("/getMe"):
                body = {"ok": True, "result": {"id": 1, "is_bot": True, "first_name": "t", "username": "t_bot"}}
            else:
                body = {"ok": True, "result": True}
            data = json.dumps(body).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

    srv = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    api.base = f"http://127.0.0.1:{srv.server_address[1]}/bot"
    try:
        yield api
    finally:
        srv.shutdown()


def _build_app(base, health=None):
    """Same wiring as bot._build_telegram_app_with_proxy, but against the fake API."""
    health = health or platform_runtime.PollHealth()
    app = (
        ApplicationBuilder()
        .token("123:TEST")
        .base_url(base)
        .request(build_bot_request(connect_timeout=5, read_timeout=5))
        .get_updates_request(build_bot_request(connect_timeout=5, read_timeout=5, on_result=health.record))
        .build()
    )
    health.app = app
    return app


# ── unit: health counting and stop rule ──

class _FakeApp:
    class updater:
        running = True


def test_success_resets_failure_streak(monkeypatch):
    monkeypatch.setattr(platform_runtime, "POLL_ERROR_LIMIT", 3)
    app = _FakeApp()
    monkeypatch.setitem(platform_runtime._STATE, "app", app)
    stops = []

    async def fake_recover(a, count, exc):
        stops.append(count)

    monkeypatch.setattr(platform_runtime, "_recover_after_poll_failures", fake_recover)
    health = platform_runtime.PollHealth()
    health.app = app

    async def run():
        for _ in range(4):
            health.record(False, RuntimeError("drop"))
            health.record(False, RuntimeError("drop"))
            health.record(True)  # any success breaks the streak
        await asyncio.sleep(0)

    asyncio.run(run())
    assert stops == []


def test_consecutive_failures_recover_only_the_live_app(monkeypatch):
    monkeypatch.setattr(platform_runtime, "POLL_ERROR_LIMIT", 3)
    live = _FakeApp()
    monkeypatch.setitem(platform_runtime._STATE, "app", live)
    stops = []

    async def fake_recover(a, count, exc):
        stops.append(a)

    monkeypatch.setattr(platform_runtime, "_recover_after_poll_failures", fake_recover)

    stale = platform_runtime.PollHealth()
    stale.app = _FakeApp()
    for _ in range(5):
        stale.record(False, RuntimeError("drop"))

    health = platform_runtime.PollHealth()
    health.app = live

    async def run():
        for _ in range(3):
            health.record(False, RuntimeError("drop"))
        await asyncio.sleep(0)

    asyncio.run(run())
    assert stops == [live]


# ── live: real PTB against the fake Bot API ──

def test_probe_rejects_proxy_that_answers_getme_but_drops_getupdates(fake_api, monkeypatch):
    monkeypatch.setitem(SETTINGS, "telegram_enabled", "1")
    fake_api.mode = "drop"
    app = _build_app(fake_api.base)

    with pytest.raises(Exception):
        asyncio.run(bot._verify_telegram(app))


def test_verify_accepts_proxy_that_serves_polling_path(fake_api, monkeypatch):
    monkeypatch.setitem(SETTINGS, "telegram_enabled", "1")
    fake_api.mode = "ok"
    app = _build_app(fake_api.base)

    assert asyncio.run(bot._verify_telegram(app)) == "t_bot"


def test_flaky_proxy_with_successes_in_between_is_not_stopped(fake_api, monkeypatch):
    monkeypatch.setattr(platform_runtime, "POLL_ERROR_LIMIT", 3)
    monkeypatch.setitem(SETTINGS, "telegram_enabled", "1")
    monkeypatch.setitem(SETTINGS, "telegram_token", "123:TEST")
    fake_api.mode = "ok"

    async def run():
        app = _build_app(fake_api.base)
        await app.initialize()
        await app.start()
        monkeypatch.setitem(platform_runtime._STATE, "app", app)
        fake_api.mode = "flaky"
        await app.updater.start_polling(drop_pending_updates=True)
        await asyncio.sleep(6)
        alive = app.updater.running and platform_runtime._STATE.get("app") is app
        calls = fake_api.get_updates_calls
        await platform_runtime.stop_telegram()
        return alive, calls

    alive, calls = asyncio.run(run())
    assert calls >= 6, "polling must actually have run through the flaky proxy"
    assert alive is True


def test_outage_stops_app_then_reconnects_when_proxy_recovers(fake_api, monkeypatch):
    monkeypatch.setattr(platform_runtime, "POLL_ERROR_LIMIT", 3)
    monkeypatch.setattr(platform_runtime, "RECONNECT_DELAYS", (0.2,))
    monkeypatch.setitem(SETTINGS, "telegram_enabled", "1")
    monkeypatch.setitem(SETTINGS, "telegram_token", "123:TEST")
    monkeypatch.setitem(platform_runtime._STATE, "app", None)
    monkeypatch.setitem(platform_runtime._STATE, "reconnect", None)
    builds = []

    async def builder():
        builds.append(1)
        app = _build_app(fake_api.base)
        await bot._verify_telegram(app)  # same probe the real builder uses
        return app, None

    monkeypatch.setitem(platform_runtime._STATE, "builder", builder)
    monkeypatch.setattr(platform_runtime, "register_platform_bot", lambda *a, **k: None)

    async def run():
        fake_api.mode = "ok"
        ok, _ = await platform_runtime.start_telegram()
        assert ok is True and platform_runtime.is_telegram_running()

        fake_api.mode = "drop"
        for _ in range(200):
            await asyncio.sleep(0.1)
            if not platform_runtime.is_telegram_running():
                break
        assert not platform_runtime.is_telegram_running(), "persistent outage must stop the app"
        down_status = platform_runtime.telegram_status()

        fake_api.mode = "ok"
        for _ in range(300):
            await asyncio.sleep(0.1)
            if platform_runtime.is_telegram_running():
                break
        up = platform_runtime.is_telegram_running()
        await platform_runtime.stop_telegram()
        task = platform_runtime._STATE.get("reconnect")
        if task is not None:
            task.cancel()
        return down_status, up

    down_status, up = asyncio.run(run())
    assert down_status["synced"] is False  # panel must not claim 'connected'
    assert up is True
    assert len(builds) >= 2  # reconnect attempts happened while the proxy was down


def test_admin_disable_cancels_pending_reconnect(monkeypatch):
    monkeypatch.setitem(SETTINGS, "telegram_enabled", "1")

    async def run():
        task = asyncio.get_running_loop().create_task(asyncio.sleep(999))
        monkeypatch.setitem(platform_runtime._STATE, "reconnect", task)
        monkeypatch.setitem(platform_runtime._STATE, "app", None)
        monkeypatch.setattr(platform_runtime, "save", lambda *a, **k: None)
        await platform_runtime.apply_telegram_enabled(False)
        await asyncio.sleep(0)
        return task.cancelled()

    assert asyncio.run(run()) is True
