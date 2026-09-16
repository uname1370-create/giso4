import sqlite3
import sys
from types import ModuleType

from giso import login_history
from giso import security_alerts


class Request:
    def __init__(self, ua, ip="192.0.2.4"):
        self.headers = {"User-Agent": ua}
        self.remote_addr = ip


def connection_factory(path):
    def connect():
        conn = sqlite3.connect(path)
        conn.row_factory = sqlite3.Row
        return conn
    return connect


def test_baseline_new_device_and_fifth_failure(monkeypatch, tmp_path):
    connect = connection_factory(tmp_path / "login.db")
    monkeypatch.setattr(login_history, "get_giso_db_conn", connect)
    import giso.monitoring_settings as settings
    monkeypatch.setattr(settings, "enabled", lambda key: True)
    captured = []
    monkeypatch.setattr(security_alerts, "notify_suspicious_login", lambda e: captured.append(e) or True)

    first = login_history.record("+989120000000", 7, True, Request("Browser A"))
    assert first["suspicious"] == 0 and not captured
    second = login_history.record("+989120000000", 7, True, Request("Mobile Browser B"))
    assert second["suspicious"] == 1 and captured[-1]["id"] == second["id"]

    captured.clear()
    for i in range(5):
        event = login_history.record("+989120000000", 7, False, Request("Attacker"), "bad password")
    assert event["suspicious"] == 1
    assert len(captured) == 1
    later = login_history.record("+989120000000", 7, False, Request("Attacker"), "bad password")
    assert later["suspicious"] == 0 and len(captured) == 1


def test_alert_is_idempotent_private_and_plain_text(monkeypatch, tmp_path):
    connect = connection_factory(tmp_path / "alerts.db")
    monkeypatch.setattr(security_alerts, "get_giso_db_conn", connect)
    site, admin, bale = [], [], []
    notifications = ModuleType("giso.panel.modules.notifications")
    notifications.log_user_notification = lambda *a, **k: site.append((a, k))
    notifications.safe_log = lambda *a, **k: admin.append((a, k))
    monkeypatch.setitem(sys.modules, "giso.panel.modules.notifications", notifications)
    monkeypatch.setattr(security_alerts._POOL, "submit", lambda fn, phone, text: bale.append((phone, text)))
    event = {"id": 22, "phone": "+989121234567", "success": 1, "suspicious": 1,
             "device_label": "موبایل", "created_at": "2026-08-28 10:00:00",
             "device_hash": "device-secret", "ip_hash": "ip-secret"}

    assert security_alerts.notify_suspicious_login(event) is True
    assert security_alerts.notify_suspicious_login(event) is False
    assert len(site) == len(admin) == len(bale) == 1
    rendered = str(site + admin + bale)
    assert "device-secret" not in rendered and "ip-secret" not in rendered
    assert "<b>" not in rendered and "parse_mode" not in rendered
    assert "+989121234567" not in str(admin)
