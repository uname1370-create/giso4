"""Transient getUpdates network drops must not flood the console with tracebacks.

Reproduces the production log:
    httpx.RemoteProtocolError: Server disconnected without sending a response.
    -> telegram.error.NetworkError (raised inside PTB's Updater polling loop)
"""
from __future__ import annotations

import asyncio
import json
import logging
import sys
import traceback

import pytest

from telegram.error import BadRequest, Conflict, NetworkError, TimedOut
from telegram.ext import ApplicationBuilder

from giso.telegram_http import (
    PollingNetworkNoiseFilter,
    build_bot_request,
    install_polling_noise_filter,
    is_transient_polling_error,
    make_polling_error_callback,
)

DISCONNECT = NetworkError("httpx.RemoteProtocolError: Server disconnected without sending a response.")


@pytest.fixture(params=["plain", "prerendered"])
def record_shape(request):
    """Run each test with normal records and with records pre-rendered the way
    giso.marketplace's redacting LogRecordFactory does it in production
    (msg formatted, args=(), traceback appended to msg, exc_info=None)."""
    if request.param == "plain":
        yield request.param
        return
    previous = logging.getLogRecordFactory()

    def prerender(*a, **k):
        rec = previous(*a, **k)
        rec.msg = rec.getMessage()
        rec.args = ()
        if rec.exc_info:
            rec.msg += "\n" + "".join(traceback.format_exception(*rec.exc_info))
            rec.exc_info = None
            rec.exc_text = None
        return rec

    logging.setLogRecordFactory(prerender)
    try:
        yield request.param
    finally:
        logging.setLogRecordFactory(previous)


def _exc_info(exc):
    try:
        raise exc
    except type(exc):
        return sys.exc_info()


def _record(msg, args=(), exc=None, level=logging.ERROR):
    """Create a record through the active factory (like logger.error would)."""
    factory = logging.getLogRecordFactory()
    return factory("telegram.ext.Updater", level, __file__, 1, msg, args, _exc_info(exc) if exc else None)


def _has_traceback(rec) -> bool:
    return bool(rec.exc_info) or "Traceback (most recent call last)" in rec.getMessage()


def test_transient_classification():
    assert is_transient_polling_error(DISCONNECT)
    assert is_transient_polling_error(TimedOut())
    assert not is_transient_polling_error(BadRequest("Chat not found"))  # BadRequest subclasses NetworkError
    assert not is_transient_polling_error(Conflict("terminated by other getUpdates request"))
    assert not is_transient_polling_error(ValueError("x"))


def test_callback_rate_limits_network_errors_and_keeps_real_errors(caplog, record_shape):
    log = logging.getLogger("test.polling")
    cb = make_polling_error_callback("بله", report_interval=3600, logger=log)
    with caplog.at_level(logging.DEBUG, logger="test.polling"):
        for _ in range(5):
            cb(_exc_info(DISCONNECT)[1])
        cb(_exc_info(Conflict("terminated by other getUpdates request"))[1])  # PTB passes raised exceptions

    warnings = [r for r in caplog.records if r.levelno == logging.WARNING]
    errors = [r for r in caplog.records if r.levelno == logging.ERROR]
    assert len(warnings) == 1, "network drops must be reported once per interval"
    assert not _has_traceback(warnings[0]), "no traceback for transient drops"
    assert "بله" in warnings[0].getMessage()
    assert len(errors) == 1 and _has_traceback(errors[0]), "real errors keep their traceback"


def test_filter_drops_ptb_loop_line_only_for_network_errors(record_shape):
    flt = PollingNetworkNoiseFilter()
    assert flt.filter(_record("Error while %s: %s", ("getting Updates", DISCONNECT))) is False
    assert flt.filter(_record("Error while %s: %s", ("getting Updates", Conflict("x")))) is True
    assert flt.filter(_record("Error while %s: %s", ("getting Updates", BadRequest("Chat not found")))) is True


def test_filter_strips_traceback_of_default_callback(record_shape):
    flt = PollingNetworkNoiseFilter()
    rec = _record("Exception happened while polling for updates.", exc=DISCONNECT)
    assert flt.filter(rec) is True
    assert not _has_traceback(rec) and rec.levelno == logging.WARNING
    assert "Server disconnected" in rec.getMessage()

    real = _record("Exception happened while polling for updates.", exc=Conflict("x"))
    assert flt.filter(real) is True
    assert _has_traceback(real) and real.levelno == logging.ERROR


def test_install_is_idempotent():
    a = install_polling_noise_filter()
    b = install_polling_noise_filter()
    assert a is b
    flts = [f for f in logging.getLogger("telegram.ext.Updater").filters if isinstance(f, PollingNetworkNoiseFilter)]
    assert len(flts) == 1


def test_real_ptb_polling_against_server_that_drops_connection(caplog, record_shape):
    """End-to-end with PTB 20.7: the server closes getUpdates without a response."""
    install_polling_noise_filter()
    calls = {"getUpdates": 0}

    async def handle(reader, writer):
        try:
            while True:
                head = await reader.readuntil(b"\r\n\r\n")
                lines = head.decode().split("\r\n")
                method = lines[0].split()[1].rsplit("/", 1)[-1]
                clen = next((int(l.split(":")[1]) for l in lines[1:] if l.lower().startswith("content-length:")), 0)
                if clen:
                    await reader.readexactly(clen)
                if method == "getUpdates":
                    calls["getUpdates"] += 1
                    writer.close()  # "Server disconnected without sending a response."
                    return
                result = True if method == "deleteWebhook" else {"id": 1, "is_bot": True, "first_name": "t", "username": "t"}
                body = json.dumps({"ok": True, "result": result}).encode()
                writer.write(b"HTTP/1.1 200 OK\r\nContent-Type: application/json\r\nContent-Length: %d\r\n\r\n" % len(body) + body)
                await writer.drain()
        except (asyncio.IncompleteReadError, ConnectionError):
            writer.close()

    async def main():
        server = await asyncio.start_server(handle, "127.0.0.1", 0)
        port = server.sockets[0].getsockname()[1]
        app = (
            ApplicationBuilder()
            .token("1:TEST")
            .base_url(f"http://127.0.0.1:{port}/bot")
            .request(build_bot_request())
            .get_updates_request(build_bot_request())
            .build()
        )
        await app.initialize()
        await app.start()
        await app.updater.start_polling(error_callback=make_polling_error_callback("بله", report_interval=3600))
        await asyncio.sleep(2.8)  # PTB retries after 1s, then 1.5s
        still_running = app.updater.running
        await app.updater.stop()
        await app.stop()
        await app.shutdown()
        server.close()
        await server.wait_closed()
        return still_running

    with caplog.at_level(logging.DEBUG):
        still_running = asyncio.run(main())

    assert still_running, "polling must survive the disconnect (PTB retries by itself)"
    assert calls["getUpdates"] >= 2, "PTB should have retried getUpdates"
    polling = [r for r in caplog.records if r.name in ("telegram.ext.Updater", "bot.polling")]
    assert not any(_has_traceback(r) for r in polling), "no traceback should be printed for transient drops"
    assert not any(r.getMessage().startswith("Error while getting Updates") for r in polling)
    runtime_warnings = [r for r in polling if r.levelno == logging.WARNING and r.name == "bot.polling"]
    assert len(runtime_warnings) == 1, "exactly one concise, rate-limited warning while running"
    assert not any(r.levelno >= logging.ERROR for r in polling), "network drops are not ERRORs"


def test_filter_strips_traceback_of_shutdown_cleanup_only_for_network_errors(record_shape):
    flt = PollingNetworkNoiseFilter()
    msg = "Error while calling `get_updates` one more time to mark all fetched updates as read: %s."
    rec = _record(msg, (DISCONNECT,), exc=DISCONNECT)
    assert flt.filter(rec) is True
    assert not _has_traceback(rec) and rec.levelno == logging.WARNING
    assert "Server disconnected" in rec.getMessage()

    # PTB 20.7 logs this message with a literal "%s" and no args
    ptb_style = _record(msg, exc=DISCONNECT)
    assert flt.filter(ptb_style) is True
    assert "%s" not in ptb_style.getMessage() and "Server disconnected" in ptb_style.getMessage()

    real = _record(msg, (Conflict("x"),), exc=Conflict("x"))
    assert flt.filter(real) is True
    assert _has_traceback(real) and real.levelno == logging.ERROR
