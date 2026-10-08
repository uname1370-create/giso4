"""HTTPX requests for bot endpoints with explicit, predictable proxy handling.

python-telegram-bot's default HTTPX client inherits HTTP_PROXY/HTTPS_PROXY from
Windows and Unix environments. Bale polling must not silently inherit a proxy
configured for unrelated traffic; callers may still pass a proxy explicitly.
"""
from __future__ import annotations

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
