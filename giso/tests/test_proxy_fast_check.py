# -*- coding: utf-8 -*-
"""تست «چک سریع پراکسی» — پروب دو فاز (۱۴۰۵-۰۶-۱۹).

فاز ۱: پروب سریعِ اتصالِ سوکت به خود پروکسی (~۲.۵ ثانیه) — مرده‌ها اینجا رد
می‌شوند و وارد تست سنگین جمینای نمی‌شوند. فاز ۲: فقط زنده‌ها تست واقعی می‌شوند.
این تست‌ها فقط از لوپ‌بک محلی استفاده می‌کنند و به اینترنت نیاز ندارند.
"""

import asyncio
import os
import socket
import sys
import time

os.environ.setdefault("SECRET_KEY", "test-secret")
sys.path.insert(0, "/home/user/Giso2")


def test_proxy_host_port_parsing():
    from giso.gemini_proxy_manager import _proxy_host_port
    assert _proxy_host_port("socks5://1.2.3.4:1080") == ("1.2.3.4", 1080)
    assert _proxy_host_port("socks5://user:pass@5.6.7.8:9050") == ("5.6.7.8", 9050)
    assert _proxy_host_port("http://9.9.9.9:8080") == ("9.9.9.9", 8080)
    assert _proxy_host_port("1.2.3.4:1080") == ("1.2.3.4", 1080)
    # فرمت‌های مبهم → پروب رد می‌شود و به تست کامل واگذار (هرگز حذف اشتباه)
    assert _proxy_host_port("socks5://[::1]:1080") is None
    assert _proxy_host_port("not-a-proxy") is None
    assert _proxy_host_port("") is None


def test_quick_probe_dead_port_fast():
    """پورت بستهٔ محلی باید سریع (<۳ ثانیه) رد شود."""
    from giso.gemini_proxy_manager import _quick_probe
    t0 = time.time()
    ok = asyncio.run(_quick_probe("socks5://127.0.0.1:1", timeout=2.5))
    dur = time.time() - t0
    assert ok is False
    assert dur < 3.0, f"پروب مرده باید سریع باشد: {dur:.1f}s"


def test_quick_probe_alive_port():
    """سوکت باز محلی باید تأیید شود."""
    from giso.gemini_proxy_manager import _quick_probe
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind(("127.0.0.1", 0))
    srv.listen(1)
    port = srv.getsockname()[1]
    try:
        ok = asyncio.run(_quick_probe(f"socks5://127.0.0.1:{port}", timeout=2.5))
        assert ok is True
    finally:
        srv.close()


def test_vet_proxy_dead_fails_fast():
    """پروکسی مرده نباید ۸ ثانیه وقت بگیرد — باید زیر ۴ ثانیه رد شود."""
    from giso import gemini_proxy_manager as g
    t0 = time.time()
    ok, ms, is_man = asyncio.run(g._vet_proxy("socks5://127.0.0.1:1", False))
    dur = time.time() - t0
    assert ok is False
    assert dur < 4.0, f"وت پروکسی مرده باید سریع باشد: {dur:.1f}s"


def test_split_timeouts_constants():
    from giso import gemini_proxy_manager as g
    assert g._TEST_CONNECT_TIMEOUT < g._TEST_TIMEOUT
    assert g._QUICK_PROBE_TIMEOUT <= 3.0
    assert g.MAX_FETCH >= 30
