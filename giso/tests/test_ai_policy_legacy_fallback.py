# -*- coding: utf-8 -*-
"""سیاست مرکزی در مسیرهای legacy و امنیت اعتبارسنجی TLS.

- اگر مدیر برای یک کاربرد (متن یا بینایی) اسلات ذخیره کرده، مسیر legacy نباید مدل‌های
  خاموش/ناسازگار یا مدل‌های خارج از تنظیم مدیر را اجرا کند.
- اگر هیچ ردیفی برای کاربرد نیست (نصب اولیه/قدیمی)، رفتار قبلی حفظ می‌شود.
- همه دیتابیس‌ها موقت‌اند و همه پاسخ‌های AI فیک‌اند؛ هیچ تماس زنده‌ای وجود ندارد.
"""
import asyncio
import os
import shutil
import socket
import sqlite3
import ssl
import struct
import subprocess
import sys
import threading
import types
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

os.environ.setdefault("SECRET_KEY", "arena-test-secret-for-buti-ai-tests-32chars")
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if BASE_DIR not in sys.path:
    sys.path.append(BASE_DIR)

import httpx  # noqa: E402
import pytest  # noqa: E402

import giso.base as giso_base  # noqa: E402
from giso import ai_brain  # noqa: E402
from giso import ai_discovery as disc  # noqa: E402
from giso import ai_health  # noqa: E402
from giso import ai_runtime  # noqa: E402
from giso import analysis as an  # noqa: E402
from giso.buti_ai import ai_models as bam  # noqa: E402


@pytest.fixture
def temp_db(tmp_path, monkeypatch):
    """همهٔ مسیرهای DB به یک فایل موقت هدایت می‌شوند؛ دیتابیس واقعی لمس نمی‌شود."""
    path = str(tmp_path / "policy.db")

    def _connect():
        conn = sqlite3.connect(path)
        conn.row_factory = sqlite3.Row
        return conn

    class _Ctx:
        def __enter__(self):
            self.conn = _connect()
            return self.conn

        def __exit__(self, *exc):
            self.conn.commit()
            self.conn.close()
            return False

    monkeypatch.setattr(ai_brain, "get_conn", lambda: _connect())
    monkeypatch.setattr(bam, "get_giso_db_conn", lambda: _Ctx())
    monkeypatch.setattr(giso_base, "get_giso_db_conn", lambda: _Ctx())
    monkeypatch.setattr(ai_runtime, "_RUNTIME_READY", False)
    monkeypatch.setattr(ai_health, "is_in_cooldown", lambda *a, **k: False)
    monkeypatch.setattr(ai_health, "mark_success", lambda *a, **k: None)
    monkeypatch.setattr(ai_health, "mark_failure", lambda *a, **k: None)
    monkeypatch.setattr(ai_health, "classify_error_text", lambda *a, **k: "other")
    ai_brain.init_ai_tables()
    ai_runtime.init_ai_runtime_tables()
    bam.init_buti_ai_model_assignments(_connect())
    return path


def _provider(name, model):
    ok = ai_brain.add_ai_provider(
        name=name, kind="openai", api_key=f"key-{name}", base_url="https://example.invalid/v1",
        api_root="https://example.invalid/v1", enabled=True, selected_model=model, replace=False,
    )
    assert ok is True


def _slot(task, priority, provider, model, enabled=True):
    ok, msg = bam.save_model_assignment(task, priority, provider, model, enabled=enabled)
    assert ok is True, msg


def _vision_pairs():
    return [(p["provider_name"], p["model_name"]) for p in an.pick_active_vision_model()]


def _record_ask_ai(monkeypatch):
    calls = []

    async def fake_ask(pname, messages, model=None, **kwargs):
        calls.append((pname, model))
        return {"ok": True, "text": "ok", "model": model or "selected", "error": ""}

    monkeypatch.setattr(ai_brain, "ask_ai", fake_ask)
    return calls


# ------------------------------------------------------------------ بینایی (C4)

def test_disabled_admin_slot_is_not_run_by_legacy_scan(temp_db):
    _provider("p1", "vision-bad")
    _slot(bam.TASK_EYEBROW_ANALYSIS, 1, "p1", "vision-bad", enabled=False)
    assert ("p1", "vision-bad") not in _vision_pairs()


def test_all_vision_slots_disabled_blocks_other_providers(temp_db):
    """مدیر بینایی را تنظیم کرده ولی همه اسلات‌ها خاموش‌اند: پروایدر دیگری که در زنجیره نیست اجرا نشود."""
    _provider("p1", "vision-bad")
    _provider("p2", "vision-other")
    _slot(bam.TASK_EYEBROW_ANALYSIS, 1, "p1", "vision-bad", enabled=False)
    assert _vision_pairs() == []


def test_incompatible_configured_slot_blocks_legacy_scan(temp_db):
    _provider("p1", "vision-bad")
    _provider("p2", "vision-other")
    _slot(bam.TASK_EYEBROW_ANALYSIS, 1, "p1", "vision-bad", enabled=True)
    disc._save_check("p1", "vision-bad", disc.CAP_VISION, disc.CHECK_INCOMPATIBLE,
                     "vision", "rejected image input")
    assert _vision_pairs() == []


def test_model_marked_incompatible_is_skipped_without_any_rows(temp_db):
    """بدون ردیف (نصب قدیمی): شاهد ناسازگاری واقعی همچنان مانع می‌شود؛ مدل سازگار حفظ می‌شود."""
    _provider("p1", "vision-bad")
    _provider("p3", "vision-ok")
    disc._save_check("p1", "vision-bad", disc.CAP_VISION, disc.CHECK_INCOMPATIBLE,
                     "vision", "rejected image input")
    assert _vision_pairs() == [("p3", "vision-ok")]


def test_legacy_default_still_used_when_nothing_is_configured(temp_db):
    _provider("p1", "vision-ok")
    assert ("p1", "vision-ok") in _vision_pairs()


def test_explicit_admin_chain_wins_over_legacy(temp_db):
    _provider("p1", "vision-other")
    _provider("p2", "vision-ok")
    _slot(bam.TASK_EYEBROW_ANALYSIS, 1, "p2", "vision-ok")
    assert _vision_pairs() == [("p2", "vision-ok")]


def test_disabled_provider_is_never_run(temp_db):
    _provider("p1", "vision-ok")
    with sqlite3.connect(temp_db) as conn:
        conn.execute("UPDATE giso_ai_providers SET enabled=0 WHERE name='p1'")
    assert ("p1", "vision-ok") not in _vision_pairs()


# ------------------------------------------------------------------ متن (C5)

def test_text_all_slots_disabled_blocks_fast_path(temp_db, monkeypatch):
    """ask_ai_fast: اسلات متن مدیر خاموش است؛ نباید مدل selected_model اجرا شود."""
    from giso.ai_brain import ask_ai_fast

    _provider("p1", "text-off")
    _slot(bam.TASK_TEXT_CHAT, 1, "p1", "text-off", enabled=False)
    calls = _record_ask_ai(monkeypatch)
    res = asyncio.run(ask_ai_fast([{"role": "user", "content": "hi"}]))
    assert calls == []
    assert res["ok"] is False and res.get("reason") == "no_allowed_model"
    assert res.get("error")


def test_text_all_slots_disabled_blocks_chat_failover(temp_db, monkeypatch):
    """chat_with_failover: همان قاعده، و خطای شفاف برگردد."""
    _provider("p1", "text-off")
    _slot(bam.TASK_TEXT_CHAT, 1, "p1", "text-off", enabled=False)
    calls = _record_ask_ai(monkeypatch)
    res = asyncio.run(ai_runtime.chat_with_failover([{"role": "user", "content": "hi"}]))
    assert calls == []
    assert res["ok"] is False and res.get("reason") == "no_allowed_model"


def test_text_legacy_still_used_without_any_text_rows(temp_db, monkeypatch):
    from giso.ai_brain import ask_ai_fast

    _provider("p1", "text-ok")
    calls = _record_ask_ai(monkeypatch)
    res = asyncio.run(ask_ai_fast([{"role": "user", "content": "hi"}]))
    assert calls == [("p1", None)]
    assert res["ok"] is True


def test_text_admin_chain_runs_only_its_slots(temp_db, monkeypatch):
    from giso.ai_brain import ask_ai_fast

    _provider("p1", "text-off")
    _provider("p2", "text-ok")
    _slot(bam.TASK_TEXT_CHAT, 1, "p2", "text-ok", enabled=True)
    calls = _record_ask_ai(monkeypatch)
    res = asyncio.run(ask_ai_fast([{"role": "user", "content": "hi"}]))
    assert calls == [("p2", "text-ok")]
    assert res["ok"] is True


# ------------------------------------------------------------------ TLS و سازگاری کلاینت

def test_make_client_reuses_verified_ssl_context(monkeypatch):
    """context یکسان و با اعتبارسنجی کامل گواهی؛ timeout و proxy همچنان منتقل می‌شوند."""
    seen = []

    class _FakeClient:
        def __init__(self, **kwargs):
            seen.append(kwargs)

    fake = types.SimpleNamespace(AsyncClient=_FakeClient, create_ssl_context=httpx.create_ssl_context)
    monkeypatch.setattr(ai_brain, "_httpx", fake)
    monkeypatch.setattr(ai_brain, "_SHARED_SSL_CONTEXT", None)

    ai_brain._make_client(7)
    ai_brain._make_client(7, "socks5://127.0.0.1:1")

    ctx = seen[0]["verify"]
    assert isinstance(ctx, ssl.SSLContext)
    assert ctx.verify_mode == ssl.CERT_REQUIRED and ctx.check_hostname is True
    assert seen[1]["verify"] is ctx
    assert seen[0]["timeout"] == 7 and seen[1]["timeout"] == 7
    assert seen[1]["proxy"] == "socks5://127.0.0.1:1"


class _OkHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        body = b"tls-ok"
        self.send_response(200)
        self.send_header("Content-Type", "text/plain")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass


@pytest.fixture
def self_signed_https(tmp_path):
    """سرور HTTPS محلی با گواهی خودامضا (فقط 127.0.0.1)."""
    if shutil.which("openssl") is None:
        pytest.skip("openssl در دسترس نیست")
    cert, key = tmp_path / "cert.pem", tmp_path / "key.pem"
    subprocess.run(
        ["openssl", "req", "-x509", "-newkey", "rsa:2048", "-nodes", "-days", "1",
         "-subj", "/CN=127.0.0.1", "-addext", "subjectAltName=IP:127.0.0.1",
         "-keyout", str(key), "-out", str(cert)],
        check=True, capture_output=True, timeout=60,
    )
    server = ThreadingHTTPServer(("127.0.0.1", 0), _OkHandler)
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    ctx.load_cert_chain(str(cert), str(key))
    server.socket = ctx.wrap_socket(server.socket, server_side=True)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        yield f"https://127.0.0.1:{server.server_address[1]}/"
    finally:
        server.shutdown()
        server.server_close()


def test_self_signed_certificate_is_rejected_by_make_client(self_signed_https, monkeypatch):
    """اعتبارسنجی گواهی با context کش‌شده خاموش نشده است (گواهی خودامضا باید رد شود)."""
    monkeypatch.setattr(ai_brain, "_SHARED_SSL_CONTEXT", None)

    async def _go():
        async with ai_brain._make_client(5) as client:
            await client.get(self_signed_https)

    with pytest.raises(httpx.ConnectError) as info:
        asyncio.run(_go())
    assert "certificate" in str(info.value).lower()


def test_positive_control_same_server_accepts_trusted_client(self_signed_https):
    """کنترل مثبت: همان سرور با اعتبارسنجی خاموش (فقط برای اثبات سرور) پاسخ می‌دهد."""

    async def _go():
        async with httpx.AsyncClient(verify=False, timeout=5) as client:
            return (await client.get(self_signed_https)).text

    assert asyncio.run(_go()) == "tls-ok"


def _recv_exact(sock, n):
    buf = b""
    while len(buf) < n:
        chunk = sock.recv(n - len(buf))
        if not chunk:
            raise OSError("socket closed")
        buf += chunk
    return buf


@pytest.fixture
def socks5_relay():
    """رله SOCKS5 محلی (CONNECT بدون احراز هویت) — ترافیک واقعی را به مقصد 127.0.0.1 می‌فرستد."""
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind(("127.0.0.1", 0))
    srv.listen(8)
    srv.settimeout(0.5)
    stop = threading.Event()

    def pipe(src, dst):
        try:
            while True:
                data = src.recv(65536)
                if not data:
                    break
                dst.sendall(data)
        except OSError:
            pass
        finally:
            for s in (src, dst):
                try:
                    s.shutdown(socket.SHUT_RDWR)
                except OSError:
                    pass

    def handle(conn):
        try:
            _recv_exact(conn, 2)
            nmethods = _recv_exact(conn, 1)[0]
            _recv_exact(conn, nmethods)
            conn.sendall(b"\x05\x00")
            ver, cmd, _rsv, atyp = _recv_exact(conn, 4)
            if ver != 5 or cmd != 1:
                conn.close()
                return
            if atyp == 1:
                host = socket.inet_ntoa(_recv_exact(conn, 4))
            elif atyp == 3:
                host = _recv_exact(conn, _recv_exact(conn, 1)[0]).decode()
            else:
                conn.close()
                return
            port = struct.unpack("!H", _recv_exact(conn, 2))[0]
            target = socket.create_connection((host, port), timeout=5)
            conn.sendall(b"\x05\x00\x00\x01" + bytes(4) + b"\x00\x00")
            threading.Thread(target=pipe, args=(conn, target), daemon=True).start()
            threading.Thread(target=pipe, args=(target, conn), daemon=True).start()
        except OSError:
            conn.close()

    def loop():
        while not stop.is_set():
            try:
                conn, _addr = srv.accept()
            except socket.timeout:
                continue
            except OSError:
                break
            threading.Thread(target=handle, args=(conn,), daemon=True).start()

    threading.Thread(target=loop, daemon=True).start()
    try:
        yield f"socks5://127.0.0.1:{srv.getsockname()[1]}"
    finally:
        stop.set()
        srv.close()


def test_self_signed_rejected_through_socks_proxy(self_signed_https, socks5_relay, monkeypatch):
    """مسیر SOCKS با کلاینت ما: گواهی خودامضا همچنان رد می‌شود."""
    monkeypatch.setattr(ai_brain, "_SHARED_SSL_CONTEXT", None)

    async def _go():
        async with ai_brain._make_client(5, socks5_relay) as client:
            await client.get(self_signed_https)

    with pytest.raises(httpx.ConnectError) as info:
        asyncio.run(_go())
    assert "certificate" in str(info.value).lower()


def test_positive_control_through_socks_proxy(self_signed_https, socks5_relay):
    """کنترل مثبت: رله SOCKS واقعاً ترافیک را به سرور TLS می‌رساند (با اعتبارسنجی خاموش، فقط برای اثبات مسیر)."""

    async def _go():
        async with httpx.AsyncClient(proxies=socks5_relay, verify=False, timeout=5) as client:
            return (await client.get(self_signed_https)).text

    assert asyncio.run(_go()) == "tls-ok"
