"""HTTPX requests for bot endpoints with explicit, predictable proxy handling.

python-telegram-bot's default HTTPX client inherits HTTP_PROXY/HTTPS_PROXY from
Windows and Unix environments. Bale polling must not silently inherit a proxy
configured for unrelated traffic; callers may still pass a proxy explicitly.
"""
from __future__ import annotations

import logging
import threading
import time

from telegram.request import HTTPXRequest


class ExplicitProxyHTTPXRequest(HTTPXRequest):
    """Use the configured proxy only; ignore ambient proxy environment variables."""

    def _build_client(self):
        import httpx

        client_kwargs = dict(self._client_kwargs)
        client_kwargs["trust_env"] = False
        return httpx.AsyncClient(**client_kwargs)


def build_bot_request(
    *,
    proxy: str | None = None,
    connection_pool_size: int = 1,
    connect_timeout: float = 5.0,
    read_timeout: float = 5.0,
    write_timeout: float = 5.0,
    pool_timeout: float = 1.0,
) -> ExplicitProxyHTTPXRequest:
    """Create a PTB request object that never inherits an unrelated system proxy."""
    return ExplicitProxyHTTPXRequest(
        connection_pool_size=connection_pool_size,
        proxy=(str(proxy).strip() or None) if proxy else None,
        connect_timeout=connect_timeout,
        read_timeout=read_timeout,
        write_timeout=write_timeout,
        pool_timeout=pool_timeout,
    )


# ---------------------------------------------------------------------------
# Polling network errors (Bale / Telegram long polling)
#
# PTB 20.7 runs getUpdates in a background task (Updater._network_loop_retry).
# When the remote side (Bale/Telegram server, a proxy, VPN or ISP middlebox)
# closes the TCP/TLS connection before sending any HTTP response, httpcore
# raises RemoteProtocolError("Server disconnected without sending a response."),
# PTB wraps it in telegram.error.NetworkError, logs it, sleeps 1s→1.5x→…→30s and
# retries by itself. The bot keeps working, but without an error_callback PTB's
# default callback prints a full multi-part traceback to stderr every time —
# which is what shows up in the VS Code terminal.
#
# The helpers below keep real failures visible, but turn transient network
# drops into one short, rate-limited warning that names the platform.
# ---------------------------------------------------------------------------
_POLLING_LOGGER_NAME = "telegram.ext.Updater"
_PTB_LOOP_ERROR_MSG = "Error while %s: %s"
_PTB_DEFAULT_CALLBACK_MSG = "Exception happened while polling for updates."
_PTB_SHUTDOWN_CLEANUP_PREFIX = "Error while calling `get_updates` one more time"
_log = logging.getLogger("bot.polling")


def is_transient_polling_error(exc) -> bool:
    """True for transport-level failures that PTB retries on its own.

    BadRequest subclasses NetworkError in PTB but is an API error (not
    transient), so it is excluded explicitly.
    """
    try:
        from telegram.error import BadRequest, NetworkError
    except Exception:  # pragma: no cover - telegram not installed
        return False
    return isinstance(exc, NetworkError) and not isinstance(exc, BadRequest)


def make_polling_error_callback(platform: str, *, report_interval: float = 60.0, logger=None):
    """Build an ``error_callback`` for ``Updater.start_polling``.

    • transient network errors → at most one WARNING line per ``report_interval``
      seconds (with a count of the suppressed repeats), no traceback;
    • anything else → logged with full traceback, as before.
    """
    log = logger or _log
    lock = threading.Lock()
    state = {"last": None, "suppressed": 0}

    def _callback(exc) -> None:
        if not is_transient_polling_error(exc):
            log.error("❌ خطای polling %s: %s", platform, exc, exc_info=exc)
            return
        now = time.monotonic()
        with lock:
            if state["last"] is not None and now - state["last"] < report_interval:
                state["suppressed"] += 1
                return
            suppressed, state["suppressed"], state["last"] = state["suppressed"], 0, now
        extra = f" — {suppressed} مورد مشابه دیگر در {int(report_interval)} ثانیهٔ اخیر" if suppressed else ""
        log.warning(
            "⚠️ قطع موقت شبکه در polling %s (%s). کتابخانه خودکار دوباره تلاش می‌کند؛ ربات متوقف نشده است%s.",
            platform, exc, extra,
        )

    return _callback


# Final exception line of a rendered traceback for errors PTB retries itself.
# (BadRequest/Forbidden/Conflict/InvalidToken have their own class names and
# are therefore never matched.)
_TRANSIENT_TRACEBACK_TAILS = ("telegram.error.NetworkError:", "telegram.error.TimedOut:")
# str(NetworkError) produced by PTB's HTTPXRequest for transport failures.
_TRANSIENT_TEXT_MARKERS = ("httpx.", "httpx ", "Server disconnected without sending a response", "Bad Gateway")


def _last_exception_line(text: str) -> str:
    for line in reversed(text.strip().splitlines()):
        line = line.strip()
        if line:
            return line
    return ""


class PollingNetworkNoiseFilter(logging.Filter):
    """Filter for the ``telegram.ext.Updater`` logger.

    • drops PTB's own "Error while getting Updates: <network error>" line — the
      platform-aware error_callback above already reports it (rate-limited);
    • safety net: if some code path starts polling without our callback, PTB's
      default callback traceback for a transient error is reduced to one WARNING
      line instead of a multi-screen traceback;
    • the one-shot "get_updates one more time" call made during shutdown keeps its
      message but loses the traceback when the cause is a network drop.
    Non-network errors (Conflict, InvalidToken, Forbidden, BadRequest …) pass unchanged.

    Works with both record shapes: the normal one (msg + args + exc_info) and the
    pre-rendered one produced by giso.marketplace's redacting LogRecordFactory
    (msg already formatted, args=(), traceback appended to msg, exc_info=None).
    """

    @staticmethod
    def _to_warning(record: logging.LogRecord, msg: str) -> None:
        record.msg = msg
        record.args = ()
        record.exc_info = None
        record.exc_text = None
        record.levelno = logging.WARNING
        record.levelname = logging.getLevelName(logging.WARNING)

    def filter(self, record: logging.LogRecord) -> bool:
        try:
            raw = record.msg if isinstance(record.msg, str) else ""
            args = record.args if isinstance(record.args, tuple) else ()
            exc = record.exc_info[1] if record.exc_info else None

            # 1) "Error while getting Updates: <exc>" (logged by _network_loop_retry)
            if raw == _PTB_LOOP_ERROR_MSG and len(args) == 2:
                if args[0] == "getting Updates" and is_transient_polling_error(args[1]):
                    return False
                return True
            if raw.startswith("Error while getting Updates: ") and "\n" not in raw:
                detail = raw[len("Error while getting Updates: "):]
                return not any(m in detail for m in _TRANSIENT_TEXT_MARKERS)

            # 2) default error callback / 3) shutdown cleanup call
            is_default_cb = raw.startswith(_PTB_DEFAULT_CALLBACK_MSG)
            is_cleanup = raw.startswith(_PTB_SHUTDOWN_CLEANUP_PREFIX)
            if not (is_default_cb or is_cleanup):
                return True
            head, sep, tb_text = raw.partition("\nTraceback")
            if exc is not None:
                transient = is_transient_polling_error(exc)
                cause = str(exc)
            elif sep:
                tail = _last_exception_line(tb_text)
                transient = tail.startswith(_TRANSIENT_TRACEBACK_TAILS)
                cause = tail.split(":", 1)[1].strip() if ":" in tail else tail
            else:
                return True
            if not transient:
                return True
            if is_default_cb:
                self._to_warning(record, f"⚠️ قطع موقت شبکه در polling ({cause}) — تلاش مجدد خودکار.")
            else:
                # فقط traceback حذف می‌شود. PTB 20.7 در این پیام «%s» می‌گذارد ولی
                # آرگومانش را پاس نمی‌دهد؛ علت واقعی را جایش می‌نشانیم.
                text = record.getMessage() if exc is not None else head
                self._to_warning(record, text.replace("%s", cause, 1))
        except Exception:
            return True
        return True


def install_polling_noise_filter() -> PollingNetworkNoiseFilter:
    """Attach the filter to PTB's Updater logger once per process (idempotent)."""
    target = logging.getLogger(_POLLING_LOGGER_NAME)
    for existing in target.filters:
        if isinstance(existing, PollingNetworkNoiseFilter):
            return existing
    flt = PollingNetworkNoiseFilter()
    target.addFilter(flt)
    return flt
