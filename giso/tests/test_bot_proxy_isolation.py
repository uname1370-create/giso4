import asyncio

from giso.telegram_http import build_bot_request


def test_bot_request_ignores_ambient_http_proxy(monkeypatch):
    monkeypatch.setenv("HTTP_PROXY", "http://127.0.0.1:1")
    monkeypatch.setenv("HTTPS_PROXY", "http://127.0.0.1:2")

    request = build_bot_request()
    try:
        assert request._client._trust_env is False
        assert request._client_kwargs["proxies"] is None
    finally:
        asyncio.run(request.shutdown())


def test_bot_request_uses_only_explicit_proxy(monkeypatch):
    monkeypatch.setenv("HTTPS_PROXY", "http://127.0.0.1:1")
    explicit_proxy = "http://127.0.0.1:8888"

    request = build_bot_request(proxy=explicit_proxy)
    try:
        assert request._client._trust_env is False
        assert request._client_kwargs["proxies"] == explicit_proxy
    finally:
        asyncio.run(request.shutdown())
