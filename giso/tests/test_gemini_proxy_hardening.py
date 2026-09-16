import asyncio
import json

from giso import gemini_proxy_manager as pm


def settings_backend(monkeypatch, initial=None):
    data = dict(initial or {})
    monkeypatch.setattr(pm, "_get_setting", lambda key, default="": data.get(key, default))
    monkeypatch.setattr(pm, "_set_setting", lambda key, value: data.__setitem__(key, str(value)) is None)
    return data


class FakeResponse:
    def __init__(self, status):
        self.status_code = status


class FakeClient:
    status = 200
    headers = None
    def __init__(self, **kwargs):
        self.kwargs = kwargs
    async def __aenter__(self): return self
    async def __aexit__(self, *args): return None
    async def get(self, url, headers=None):
        type(self).headers = headers
        return FakeResponse(type(self).status)


class FakeHttpx:
    AsyncClient = FakeClient


def test_authenticated_check_rejects_auth_and_rate_limit(monkeypatch):
    settings_backend(monkeypatch)
    monkeypatch.setattr(pm, "_httpx", FakeHttpx)
    monkeypatch.setattr(pm, "_gemini_api_key", lambda: "secret")
    for status in (401, 403, 429, 500):
        FakeClient.status = status
        ok, _ = asyncio.run(pm._test_single_proxy_ms("socks5://one:1"))
        assert not ok
    FakeClient.status = 200
    ok, _ = asyncio.run(pm._test_single_proxy_ms("socks5://one:1"))
    assert ok
    assert FakeClient.headers == {"x-goog-api-key": "secret"}


def test_stable_fast_proxy_is_sorted_first(monkeypatch):
    data = settings_backend(monkeypatch)
    health = {
        "socks5://slow:1": {"successes": 2, "failures": 0, "latency_ms": 900},
        "socks5://fast:2": {"successes": 5, "failures": 0, "latency_ms": 80},
        "socks5://flaky:3": {"successes": 8, "failures": 2, "latency_ms": 20},
    }
    data["proxy_health"] = json.dumps(health)
    pm.save_working(list(health))
    # امتیاز هوشمند (پایداری ۵۰٪ + سرعت ۳۰٪ + vision ۲۰٪): flaky بسیار سریع‌تر
    # (۲۰ms) است و با وجود ۸۰٪ پایداری، از slowِ ۹۰۰ms جلو می‌افتد.
    assert pm.load_working() == ["socks5://fast:2", "socks5://flaky:3", "socks5://slow:1"]


def test_circuit_breaker_and_masked_status(monkeypatch):
    now = 2_000_000
    health = {
        "socks5://user:pass@broken.example:1080": {
            "consecutive_failures": 3, "checked_at": now, "successes": 0,
            "failures": 3, "latency_ms": 99999},
        "socks5://user:pass@good.example:1080": {
            "consecutive_failures": 0, "checked_at": now, "successes": 2,
            "failures": 0, "latency_ms": 100},
    }
    data = settings_backend(monkeypatch, {
        "proxy_mode": "auto", "working_proxies": json.dumps(list(health)),
        "proxy_health": json.dumps(health),
        "source_url": "https://user:pass@source.example/list?token=secret",
    })
    monkeypatch.setattr(pm.time, "time", lambda: now)
    assert "good.example" in pm.get_active_proxy()
    # Scraped working proxies are never selected for real user images.
    assert pm.get_active_proxy(sensitive=True) is None
    data["manual_proxies"] = json.dumps(["socks5://trusted.example:1080"])
    assert "trusted.example" in pm.get_active_proxy(sensitive=True)
    monkeypatch.setattr(pm, "_get_all_settings", lambda: data)
    summary = pm.status_summary()
    assert "user" not in summary["active_proxy"] and "pass" not in summary["active_proxy"]
    assert "token" not in summary["source_url"] and "pass" not in summary["source_url"]
