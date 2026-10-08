"""Regression tests for provider-returned image URLs; all networking is mocked."""
from __future__ import annotations

import ipaddress
import socket

import pytest

from giso.buti_ai.eyebrow import image_generation as image_generation


class _FakeResponse:
    def __init__(self, body=b"image-bytes", status=200, headers=None):
        self.status = status
        self._body = body
        self._offset = 0
        self._headers = {str(key).lower(): str(value) for key, value in (headers or {}).items()}
        self.closed = False
        self.read_calls = 0

    def getheader(self, name):
        return self._headers.get(str(name).lower())

    def read(self, size=-1):
        self.read_calls += 1
        if size < 0:
            size = len(self._body) - self._offset
        chunk = self._body[self._offset:self._offset + size]
        self._offset += len(chunk)
        return chunk

    def close(self):
        self.closed = True


class _FakeConnection:
    def __init__(self, hostname, address, family, timeout, response, calls):
        self.hostname = hostname
        self.address = address
        self.family = family
        self.timeout = timeout
        self.response = response
        self.calls = calls
        self.closed = False

    def request(self, method, target, headers=None):
        self.calls.append({
            "hostname": self.hostname,
            "address": self.address,
            "family": self.family,
            "timeout": self.timeout,
            "method": method,
            "target": target,
            "headers": headers or {},
        })

    def getresponse(self):
        return self.response

    def close(self):
        self.closed = True


def _dns_record(ip, port=443):
    address = ipaddress.ip_address(ip)
    if address.version == 4:
        return (socket.AF_INET, socket.SOCK_STREAM, socket.IPPROTO_TCP, "", (str(address), port))
    return (socket.AF_INET6, socket.SOCK_STREAM, socket.IPPROTO_TCP, "", (str(address), port, 0, 0))


def _mock_fetch(monkeypatch, response, records):
    calls = []
    resolutions = []

    def fake_getaddrinfo(host, port, *, type):
        resolutions.append((host, port, type))
        return list(records)

    def fake_connection(hostname, address, family, timeout):
        return _FakeConnection(hostname, address, family, timeout, response, calls)

    monkeypatch.setattr(image_generation.socket, "getaddrinfo", fake_getaddrinfo)
    monkeypatch.setattr(image_generation, "_PinnedProviderImageHTTPSConnection", fake_connection)
    return calls, resolutions


def test_allowlisted_public_cdn_url_is_fetched_with_size_type_and_timeout_limits(monkeypatch):
    body = b"a small mocked image payload"
    response = _FakeResponse(body, headers={"Content-Type": "image/webp; charset=binary", "Content-Length": len(body)})
    calls, resolutions = _mock_fetch(monkeypatch, response, [_dns_record("93.184.216.34")])

    raw, mime = image_generation._decode_image_value(
        "https://images.example.test/result.webp?v=1",
        12,
        "https://api.example.test/v1/image",
        {"image_output_hosts": ["images.example.test"]},
    )

    assert raw == body
    assert mime == "image/webp"
    assert resolutions == [("images.example.test", 443, socket.SOCK_STREAM)]
    assert len(calls) == 1
    assert calls[0]["method"] == "GET"
    assert calls[0]["target"] == "/result.webp?v=1"
    assert calls[0]["address"] == "93.184.216.34"
    assert calls[0]["timeout"] == 12
    assert calls[0]["headers"]["Accept-Encoding"] == "identity"
    assert response.closed is True


def test_exact_provider_endpoint_host_is_allowed_without_extra_hosts(monkeypatch):
    body = b"image"
    response = _FakeResponse(body, headers={"Content-Type": "image/png"})
    calls, _ = _mock_fetch(monkeypatch, response, [_dns_record("93.184.216.34")])

    raw, mime = image_generation._decode_image_value(
        "https://api.example.test/generated.png", 4, "https://api.example.test/v1/generate"
    )

    assert (raw, mime) == (body, "image/png")
    assert calls[0]["hostname"] == "api.example.test"


@pytest.mark.parametrize("ip", [
    "127.0.0.1",          # IPv4 loopback
    "10.4.5.6",           # RFC1918
    "172.20.1.4",         # RFC1918
    "192.168.2.9",        # RFC1918
    "169.254.169.254",    # link-local / cloud metadata
    "100.64.0.1",         # shared address space
    "240.0.0.1",          # reserved IPv4
    "::1",                # IPv6 loopback
    "fc00::1",            # IPv6 unique-local
    "fe80::1",            # IPv6 link-local
    "2001:db8::1",        # documentation/reserved IPv6
    "::ffff:127.0.0.1",   # IPv4-mapped loopback
])
def test_dns_answer_to_non_public_ip_is_rejected_before_connect(monkeypatch, ip):
    response = _FakeResponse(headers={"Content-Type": "image/png"})
    calls, _ = _mock_fetch(monkeypatch, response, [_dns_record(ip)])

    with pytest.raises(image_generation.ImageProviderError, match="IP غیرعمومی"):
        image_generation._decode_image_value(
            "https://images.example.test/out.png", 5,
            "https://api.example.test/v1", {"image_output_hosts": ["images.example.test"]},
        )

    assert calls == []


def test_mixed_public_and_private_dns_answers_fail_closed(monkeypatch):
    response = _FakeResponse(headers={"Content-Type": "image/png"})
    calls, _ = _mock_fetch(
        monkeypatch, response, [_dns_record("93.184.216.34"), _dns_record("10.0.0.7")]
    )

    with pytest.raises(image_generation.ImageProviderError):
        image_generation._decode_image_value(
            "https://images.example.test/out.png", 5,
            "https://api.example.test/v1", {"image_output_hosts": ["images.example.test"]},
        )

    assert calls == []


@pytest.mark.parametrize("url", [
    "http://api.example.test/image.png",
    "https://127.0.0.1/image.png",
    "https://[::1]/image.png",
    "https://10.0.0.7/image.png",
    "https://169.254.169.254/latest/meta-data",
    "https://user:pass@api.example.test/image.png",
    "https://api.example.test:8443/image.png",
])
def test_unsafe_scheme_ip_literal_credentials_or_port_are_rejected_without_dns(monkeypatch, url):
    dns_calls = []
    monkeypatch.setattr(
        image_generation.socket,
        "getaddrinfo",
        lambda *args, **kwargs: dns_calls.append(args) or [_dns_record("93.184.216.34")],
    )

    with pytest.raises(image_generation.ImageProviderError):
        image_generation._decode_image_value(url, 5, "https://api.example.test/v1")

    assert dns_calls == []


def test_unlisted_host_is_rejected_before_dns(monkeypatch):
    dns_calls = []
    monkeypatch.setattr(
        image_generation.socket, "getaddrinfo", lambda *args, **kwargs: dns_calls.append(args) or []
    )

    with pytest.raises(image_generation.ImageProviderError, match="allowlist"):
        image_generation._decode_image_value(
            "https://attacker.example.test/image.png", 5, "https://api.example.test/v1"
        )

    assert dns_calls == []


def test_public_redirect_to_private_metadata_url_is_never_followed(monkeypatch):
    response = _FakeResponse(
        b"",
        status=302,
        headers={"Location": "https://169.254.169.254/latest/meta-data"},
    )
    calls, resolutions = _mock_fetch(monkeypatch, response, [_dns_record("93.184.216.34")])

    with pytest.raises(image_generation.ImageProviderError, match="redirect"):
        image_generation._decode_image_value(
            "https://api.example.test/image.png", 5, "https://api.example.test/v1"
        )

    assert len(calls) == 1
    assert len(resolutions) == 1
    assert calls[0]["target"] == "/image.png"


def test_non_image_content_type_is_rejected(monkeypatch):
    response = _FakeResponse(b"html", headers={"Content-Type": "text/html", "Content-Length": "4"})
    _mock_fetch(monkeypatch, response, [_dns_record("93.184.216.34")])

    with pytest.raises(image_generation.ImageProviderError, match="Content-Type"):
        image_generation._decode_image_value(
            "https://api.example.test/image", 5, "https://api.example.test/v1"
        )


def test_declared_or_streamed_oversize_response_is_rejected(monkeypatch):
    monkeypatch.setattr(image_generation, "MAX_DOWNLOAD_BYTES", 4)
    declared = _FakeResponse(b"12345", headers={"Content-Type": "image/png", "Content-Length": "5"})
    _mock_fetch(monkeypatch, declared, [_dns_record("93.184.216.34")])
    with pytest.raises(image_generation.ImageProviderError, match="حجم"):
        image_generation._decode_image_value(
            "https://api.example.test/image", 5, "https://api.example.test/v1"
        )
    assert declared.read_calls == 0

    streamed = _FakeResponse(b"12345", headers={"Content-Type": "image/png"})
    _mock_fetch(monkeypatch, streamed, [_dns_record("93.184.216.34")])
    with pytest.raises(image_generation.ImageProviderError, match="حجم"):
        image_generation._decode_image_value(
            "https://api.example.test/image", 5, "https://api.example.test/v1"
        )


def test_https_socket_connects_to_validated_ip_and_keeps_hostname_for_tls(monkeypatch):
    calls = {}

    class _RawSocket:
        def settimeout(self, timeout):
            calls["timeout"] = timeout

        def connect(self, address):
            calls["address"] = address

        def close(self):
            calls["raw_closed"] = True

    class _TLSContext:
        verify_mode = image_generation.ssl.CERT_REQUIRED
        check_hostname = True

        def set_alpn_protocols(self, protocols):
            calls["alpn"] = tuple(protocols)

        def wrap_socket(self, raw_socket, *, server_hostname):
            calls["server_hostname"] = server_hostname
            return raw_socket

    raw = _RawSocket()
    monkeypatch.setattr(image_generation.socket, "socket", lambda family, socktype: raw)
    monkeypatch.setattr(image_generation.ssl, "create_default_context", lambda: _TLSContext())
    monkeypatch.setattr(
        image_generation.socket,
        "getaddrinfo",
        lambda *args, **kwargs: pytest.fail("pinned socket must not resolve the hostname again"),
    )

    connection = image_generation._PinnedProviderImageHTTPSConnection(
        "images.example.test", "93.184.216.34", socket.AF_INET, 3
    )
    connection.connect()

    assert calls["address"] == ("93.184.216.34", 443)
    assert calls["server_hostname"] == "images.example.test"
    assert calls["timeout"] == 3
