"""Disabled Telegram must be a strict no-network mode for the edu bot."""
from __future__ import annotations

import asyncio
from types import SimpleNamespace

import bot
import platform_runtime
import proxy_manager
import ui
from config import SETTINGS


def _fail_if_called(*args, **kwargs):
    raise AssertionError("Telegram/proxy network path should not be called while disabled")


async def _fail_async_if_called(*args, **kwargs):
    _fail_if_called(*args, **kwargs)


def test_bootstrap_skips_all_telegram_proxy_and_api_work_when_disabled(monkeypatch):
    monkeypatch.setitem(SETTINGS, "telegram_enabled", "0")
    monkeypatch.setitem(SETTINGS, "telegram_token", "test-token")
    monkeypatch.setattr(bot, "_collect_proxy_candidates", _fail_if_called)
    monkeypatch.setattr(bot, "_build_telegram_app_with_proxy", _fail_if_called)

    app, proxy = asyncio.run(bot._try_build_telegram_app())

    assert app is None
    assert proxy is None


def test_telegram_verification_refuses_api_call_when_disabled(monkeypatch):
    monkeypatch.setitem(SETTINGS, "telegram_enabled", "0")

    class NoNetworkApp:
        async def initialize(self):
            _fail_if_called()

    try:
        asyncio.run(bot._verify_telegram(NoNetworkApp()))
    except RuntimeError as exc:
        assert "disabled" in str(exc).lower()
    else:
        raise AssertionError("disabled Telegram verification should not reach the API")


def test_runtime_start_is_silent_noop_when_telegram_is_disabled(monkeypatch):
    monkeypatch.setitem(SETTINGS, "telegram_enabled", "0")
    monkeypatch.setitem(SETTINGS, "telegram_token", "test-token")
    monkeypatch.setitem(platform_runtime._STATE, "app", None)
    monkeypatch.setitem(platform_runtime._STATE, "builder", _fail_async_if_called)

    ok, message = asyncio.run(platform_runtime.start_telegram())

    assert ok is True
    assert "غیرفعال" in message
    assert "پروکسی" not in message
    assert "فعال کنید" not in message


def test_disabled_proxy_menu_shows_no_proxy_setup_or_test_actions(monkeypatch):
    monkeypatch.setitem(SETTINGS, "telegram_enabled", "0")
    monkeypatch.setattr(proxy_manager, "status_summary", _fail_if_called)

    class Target:
        text = ""
        reply_markup = None

        async def edit_message_text(self, text, reply_markup=None):
            self.text = text
            self.reply_markup = reply_markup

    target = Target()
    asyncio.run(ui.show_proxy_menu(target))

    assert target.text == "📴 تلگرام غیرفعال است."
    callback_data = [
        button.callback_data
        for row in target.reply_markup.inline_keyboard
        for button in row
    ]
    assert callback_data == ["a_plat|telegram"]


def test_disabled_telegram_detail_hides_proxy_controls(monkeypatch):
    monkeypatch.setitem(SETTINGS, "telegram_enabled", "0")

    class Target:
        text = ""
        reply_markup = None

        async def edit_message_text(self, text, reply_markup=None):
            self.text = text
            self.reply_markup = reply_markup

    target = Target()
    asyncio.run(ui.show_platform_detail(target, "telegram", is_q=True))

    assert "تنظیمات پروکسی" not in target.text
    callback_data = [
        button.callback_data
        for row in target.reply_markup.inline_keyboard
        for button in row
    ]
    assert not any(value and value.startswith("a_plat_proxy") for value in callback_data)


def test_proxy_fetch_and_test_entrypoints_do_no_network_when_telegram_is_disabled(monkeypatch):
    monkeypatch.setitem(SETTINGS, "telegram_enabled", "0")
    monkeypatch.setattr(proxy_manager.httpx, "AsyncClient", _fail_if_called)
    original_fetch = proxy_manager.fetch_from_source
    monkeypatch.setattr(proxy_manager, "load_working", _fail_if_called)
    monkeypatch.setattr(proxy_manager, "get_manual_proxies", _fail_if_called)

    async def run_checks():
        assert await original_fetch() == (
            [], proxy_manager.TELEGRAM_DISABLED_ERROR,
        )
        assert await proxy_manager.test_proxy_timed("socks5://127.0.0.1:1080") == (
            False, 0, proxy_manager.TELEGRAM_DISABLED_ERROR,
        )
        report = await proxy_manager.test_many_report(["socks5://127.0.0.1:1080"])
        assert report["total"] == 0
        assert report["config_error"] == proxy_manager.TELEGRAM_DISABLED_ERROR
        assert await proxy_manager.refresh_from_source() == (
            None, proxy_manager.TELEGRAM_DISABLED_ERROR,
        )
        assert await proxy_manager.revalidate() == (
            None, proxy_manager.TELEGRAM_DISABLED_ERROR,
        )
        assert await proxy_manager.test_manual_proxies() == (
            None, proxy_manager.TELEGRAM_DISABLED_ERROR,
        )

    asyncio.run(run_checks())


def test_bale_bootstrap_remains_available_when_telegram_is_disabled(monkeypatch):
    monkeypatch.setitem(SETTINGS, "telegram_enabled", "0")
    monkeypatch.setitem(SETTINGS, "telegram_token", "test-token")
    bale_app = SimpleNamespace(bot=object())
    starts = []

    monkeypatch.setattr(bot, "_build_bale_app", lambda: bale_app)

    async def fake_start_polling(app, name, already_initialized=False):
        starts.append(name)
        return True

    monkeypatch.setattr(bot, "_start_polling", fake_start_polling)

    async def fake_stop_app(app, name):
        return None

    monkeypatch.setattr(bot, "_stop_app", fake_stop_app)
    monkeypatch.setattr(bot, "_init_periodic_checkpoint_edubot", lambda app: None)
    monkeypatch.setattr(bot, "_collect_proxy_candidates", _fail_if_called)

    import handlers

    monkeypatch.setattr(handlers, "_init_edubot_auto_backup", lambda app: None)

    class StopWait:
        async def wait(self):
            raise asyncio.CancelledError

    monkeypatch.setattr(bot.asyncio, "Event", StopWait)

    asyncio.run(bot._run_all())

    assert starts == ["بله"]
