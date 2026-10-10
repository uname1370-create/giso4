"""HTTPX requests for bot endpoints with explicit, predictable proxy handling.

python-telegram-bot's default HTTPX client inherits HTTP_PROXY/HTTPS_PROXY from
Windows and Unix environments. Bale polling must not silently inherit a proxy
configured for unrelated traffic; callers may still pass a proxy explicitly.
"""
from __future__ import annotations

from telegram.request import HTTPXRequest


class ExplicitProxyHTTPXRequest(HTTPXRequest):
    """Use the configured proxy only; ignore ambient proxy environment variables.

    `on_result(ok: bool, exc: Exception | None)` is called after every HTTP
    round-trip when provided. Polling uses it to tell a working proxy from a
    dropped one (PTB itself only reports failures, never successes).
    """

    def __init__(self, *args, on_result=None, **kwargs):
        super().__init__(*args, **kwargs)
        self._on_result = on_result

    def _build_client(self):
        import httpx

        client_kwargs = dict(self._client_kwargs)
        client_kwargs["trust_env"] = False
        return httpx.AsyncClient(**client_kwargs)

    async def do_request(self, *args, **kwargs):
        if self._on_result is None:
            return await super().do_request(*args, **kwargs)
        try:
            result = await super().do_request(*args, **kwargs)
        except Exception as exc:
            self._on_result(False, exc)
            raise
        self._on_result(True, None)
        return result


def build_bot_request(
    *,
    proxy: str | None = None,
    connection_pool_size: int = 1,
    connect_timeout: float = 5.0,
    read_timeout: float = 5.0,
    write_timeout: float = 5.0,
    pool_timeout: float = 1.0,
    on_result=None,
) -> ExplicitProxyHTTPXRequest:
    """Create a PTB request object that never inherits an unrelated system proxy."""
    return ExplicitProxyHTTPXRequest(
        connection_pool_size=connection_pool_size,
        proxy=(str(proxy).strip() or None) if proxy else None,
        connect_timeout=connect_timeout,
        read_timeout=read_timeout,
        write_timeout=write_timeout,
        pool_timeout=pool_timeout,
        on_result=on_result,
    )
