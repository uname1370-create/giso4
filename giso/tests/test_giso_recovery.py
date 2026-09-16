import hashlib
import json
import sqlite3
import zipfile
from pathlib import Path

import giso.recovery as recovery


def make_db(path: Path, value="original"):
    path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(path) as conn:
        conn.execute("CREATE TABLE sample (value TEXT)")
        conn.execute("INSERT INTO sample VALUES (?)", (value,))


def configure(monkeypatch, tmp_path):
    giso = tmp_path / "giso"
    monkeypatch.setattr(recovery, "DB_PATH", giso / "data/giso.db")
    monkeypatch.setattr(recovery, "BOT_DB_PATH", tmp_path / "bot_edu/data/bot.db")
    monkeypatch.setattr(recovery, "RECOVERY_DIR", giso / "data/recovery")
    monkeypatch.setattr(recovery, "UPLOADS_DIR", giso / "static/uploads")
    monkeypatch.setattr(recovery, "RECEIPTS_DIR", giso / "data/wallet_receipts")
    make_db(recovery.DB_PATH)
    recovery.UPLOADS_DIR.mkdir(parents=True)
    recovery.RECEIPTS_DIR.mkdir(parents=True)


def db_value(path):
    with sqlite3.connect(path) as conn:
        return conn.execute("SELECT value FROM sample").fetchone()[0]


def test_package_contains_db_files_and_no_bot_secret(monkeypatch, tmp_path):
    configure(monkeypatch, tmp_path)
    recovery.BOT_DB_PATH.parent.mkdir(parents=True)
    with sqlite3.connect(recovery.BOT_DB_PATH) as conn:
        conn.execute("CREATE TABLE settings (key TEXT, value TEXT)")
        conn.executemany("INSERT INTO settings VALUES (?,?)", [
            ("giso_maintenance", "on"), ("bot_token", "TOP-SECRET")])
    (recovery.RECEIPTS_DIR / "receipt.webp").write_bytes(b"receipt")
    (recovery.UPLOADS_DIR / "active.jpg").write_bytes(b"image")
    (recovery.UPLOADS_DIR / "temp").mkdir()
    (recovery.UPLOADS_DIR / "temp/ignored.jpg").write_bytes(b"temp")

    result = recovery.create_recovery_package()
    assert result["ok"]
    with zipfile.ZipFile(result["path"]) as zf:
        names = set(zf.namelist())
        config = zf.read("giso-config.json").decode()
    assert {"giso.db", "manifest.json", "files/wallet_receipts/receipt.webp",
            "files/uploads/active.jpg"} <= names
    assert "ignored.jpg" not in " ".join(names)
    assert "TOP-SECRET" not in config and "bot_token" not in config
    assert Path(result["path"]).read_bytes().find(b"bot.db") == -1


def test_tamper_and_traversal_are_rejected(monkeypatch, tmp_path):
    configure(monkeypatch, tmp_path)
    package = Path(recovery.create_recovery_package()["path"])
    tampered = tmp_path / "tampered.zip"
    with zipfile.ZipFile(package) as src, zipfile.ZipFile(tampered, "w") as dst:
        for info in src.infolist():
            data = src.read(info.filename)
            dst.writestr(info, b"broken" if info.filename == "giso.db" else data)
    assert not recovery.validate_recovery_package(tampered)["ok"]

    traversal = tmp_path / "traversal.zip"
    with zipfile.ZipFile(package) as src, zipfile.ZipFile(traversal, "w") as dst:
        for info in src.infolist():
            dst.writestr(info, src.read(info.filename))
        dst.writestr("../escape", b"bad")
    assert not recovery.validate_recovery_package(traversal)["ok"]
    assert not (tmp_path / "escape").exists()


def test_restore_never_overwrites_bot_db(monkeypatch, tmp_path):
    configure(monkeypatch, tmp_path)
    recovery.BOT_DB_PATH.parent.mkdir(parents=True)
    recovery.BOT_DB_PATH.write_bytes(b"education-database")
    (recovery.UPLOADS_DIR / "photo.jpg").write_bytes(b"from-package")
    package = Path(recovery.create_recovery_package()["path"])
    bot_before = recovery.BOT_DB_PATH.read_bytes()
    with sqlite3.connect(recovery.DB_PATH) as conn:
        conn.execute("UPDATE sample SET value='changed'")
    (recovery.UPLOADS_DIR / "photo.jpg").write_bytes(b"changed")

    ok, _ = recovery.restore_recovery_package(package)
    assert ok and db_value(recovery.DB_PATH) == "original"
    assert (recovery.UPLOADS_DIR / "photo.jpg").read_bytes() == b"from-package"
    assert recovery.BOT_DB_PATH.read_bytes() == bot_before


def test_post_restore_failure_rolls_back_db_and_files(monkeypatch, tmp_path):
    configure(monkeypatch, tmp_path)
    (recovery.UPLOADS_DIR / "photo.jpg").write_bytes(b"package")
    package = Path(recovery.create_recovery_package()["path"])
    with sqlite3.connect(recovery.DB_PATH) as conn:
        conn.execute("UPDATE sample SET value='live'")
    (recovery.UPLOADS_DIR / "photo.jpg").write_bytes(b"live-file")
    real_valid = recovery._valid_db
    calls = {"n": 0}

    def fail_smoke(path):
        calls["n"] += 1
        # validation succeeds; final live DB smoke check fails
        return False if calls["n"] == 3 else real_valid(path)

    monkeypatch.setattr(recovery, "_valid_db", fail_smoke)
    ok, message = recovery.restore_recovery_package(package)
    assert not ok and "Rollback" in message
    assert db_value(recovery.DB_PATH) == "live"
    assert (recovery.UPLOADS_DIR / "photo.jpg").read_bytes() == b"live-file"


def test_restore_recovers_when_current_db_is_corrupt(monkeypatch, tmp_path):
    """بحرانی‌ترین سناریو: giso.db فعلی خراب است و باید از بسته Recovery برگردد."""
    configure(monkeypatch, tmp_path)
    package = Path(recovery.create_recovery_package()["path"])
    recovery.DB_PATH.write_bytes(b"corrupted-not-a-db")
    ok, message = recovery.restore_recovery_package(package)
    assert ok is True
    assert db_value(recovery.DB_PATH) == "original"
    assert "خراب" in message


def test_restore_corrupt_current_failure_does_not_crash(monkeypatch, tmp_path):
    """اگر DB قبلی خراب باشد و smoke بعد از replace هم شکست بخورد، نباید کرش کند."""
    configure(monkeypatch, tmp_path)
    (recovery.UPLOADS_DIR / "photo.jpg").write_bytes(b"package")
    package = Path(recovery.create_recovery_package()["path"])
    recovery.DB_PATH.write_bytes(b"corrupted-not-a-db")
    (recovery.UPLOADS_DIR / "photo.jpg").write_bytes(b"live-file")
    real_valid = recovery._valid_db
    calls = {"n": 0}

    def fail_smoke(path):
        calls["n"] += 1
        # فراخوانی اول: اعتبارسنجی بسته (روی فایل extract شده) → سالم؛
        # فراخوانی دوم (smoke بعد از replace روی DB فعلی) → شکست مصنوعی.
        return False if calls["n"] == 2 and Path(path) == recovery.DB_PATH else real_valid(path)

    monkeypatch.setattr(recovery, "_valid_db", fail_smoke)
    ok, message = recovery.restore_recovery_package(package)
    assert ok is False
    assert "رول‌بک ممکن نبود" in message
