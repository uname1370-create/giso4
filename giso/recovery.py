# -*- coding: utf-8 -*-
"""Independent GISO recovery packages.

A package contains a consistent giso.db snapshot, durable user uploads and a
non-secret export of the few GISO settings stored in bot_edu/data/bot.db.  It
never contains or overwrites bot.db.
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import shutil
import sqlite3
import tempfile
import zipfile
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath

logger = logging.getLogger(__name__)

GISO_DIR = Path(__file__).resolve().parent
DB_PATH = GISO_DIR / "data" / "giso.db"
BOT_DB_PATH = GISO_DIR.parent / "bot_edu" / "data" / "bot.db"
RECOVERY_DIR = GISO_DIR / "data" / "recovery"
UPLOADS_DIR = GISO_DIR / "static" / "uploads"
RECEIPTS_DIR = GISO_DIR / "data" / "wallet_receipts"
FORMAT_VERSION = 1
# Only non-secret cross-project values. In particular bot_token/API keys/OTP
# secrets are deliberately not exported.
CONFIG_KEYS = {
    "admin_request_phrase", "site_theme", "giso_maintenance",
    "giso_rate_limit", "giso_notification_enabled",
}


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _valid_db(path: Path) -> bool:
    conn = None
    try:
        conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
        integrity = conn.execute("PRAGMA integrity_check").fetchone()
        tables = conn.execute(
            "SELECT count(*) FROM sqlite_master WHERE type='table'"
        ).fetchone()
        return bool(integrity and integrity[0] == "ok" and tables and tables[0] > 0)
    except (sqlite3.Error, OSError):
        return False
    finally:
        # روی ویندوز handle باز مانع پاک‌سازی فایل موقت می‌شود (WinError 32)؛
        # `with sqlite3.connect(...)` کانکشن را نمی‌بندد — بستن صریح لازم است.
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass


def _snapshot_db(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    src = sqlite3.connect(str(source))
    dst = None
    try:
        dst = sqlite3.connect(str(destination))
        src.backup(dst)
    finally:
        for c in (dst, src):
            if c is not None:
                try:
                    c.close()
                except Exception:
                    pass
    if not _valid_db(destination):
        raise RuntimeError("Database snapshot failed integrity validation")


def _export_giso_config() -> dict:
    result = {"settings": {}, "admins": [], "admin_requests": []}
    if not BOT_DB_PATH.exists():
        return result
    conn = None
    try:
        conn = sqlite3.connect(f"file:{BOT_DB_PATH}?mode=ro", uri=True)
        conn.row_factory = sqlite3.Row
        tables = {r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'")}
        for table in ("giso_config", "settings"):
            if table in tables:
                marks = ",".join("?" for _ in CONFIG_KEYS)
                for row in conn.execute(
                    f'SELECT key,value FROM "{table}" WHERE key IN ({marks})',
                    tuple(sorted(CONFIG_KEYS))):
                    result["settings"][row["key"]] = row["value"]
        for table in ("giso_admins", "giso_admin_requests"):
            if table in tables:
                # Explicitly omit any columns introduced later that may be secret.
                allowed = ({"phone", "telegram_id", "bale_id", "added_by", "added_at"}
                           if table == "giso_admins" else
                           {"phone", "bale_id", "status", "requested_at", "reviewed_by", "reviewed_at"})
                columns = [r[1] for r in conn.execute(f'PRAGMA table_info("{table}")')
                           if r[1] in allowed]
                if columns:
                    query = ",".join(f'"{c}"' for c in columns)
                    result[table.replace("giso_", "")] = [dict(r) for r in conn.execute(
                        f'SELECT {query} FROM "{table}"')]
    except sqlite3.Error:
        # Config is supplementary; giso.db remains the recovery source of truth.
        pass
    finally:
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass
    return result


def _durable_files():
    for root, archive_root in ((RECEIPTS_DIR, "wallet_receipts"),
                               (UPLOADS_DIR, "uploads")):
        if not root.exists():
            continue
        for path in sorted(root.rglob("*")):
            if not path.is_file() or path.is_symlink():
                continue
            rel = path.relative_to(root)
            if "temp" in rel.parts or path.name.startswith("."):
                continue
            yield path, f"files/{archive_root}/{rel.as_posix()}"


def create_recovery_package(destination: Path | None = None) -> dict:
    if not DB_PATH.exists():
        return {"ok": False, "error": "فایل دیتابیس گیسو پیدا نشد."}
    RECOVERY_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    destination = Path(destination or RECOVERY_DIR / f"giso_recovery_{stamp}.zip")
    destination.parent.mkdir(parents=True, exist_ok=True)
    tmp_zip = destination.with_name(destination.name + f".{os.getpid()}.tmp")
    try:
        with tempfile.TemporaryDirectory(prefix="giso-recovery-") as td:
            stage = Path(td)
            db = stage / "giso.db"
            _snapshot_db(DB_PATH, db)
            config = stage / "giso-config.json"
            config.write_text(json.dumps(_export_giso_config(), ensure_ascii=False, indent=2), "utf-8")
            entries = [(db, "giso.db"), (config, "giso-config.json"), *_durable_files()]
            files = [{"path": arc, "size": src.stat().st_size, "sha256": _sha256(src)}
                     for src, arc in entries]
            manifest = {
                "format": "giso-recovery", "version": FORMAT_VERSION,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "files": files,
            }
            manifest_path = stage / "manifest.json"
            manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), "utf-8")
            with zipfile.ZipFile(tmp_zip, "w", zipfile.ZIP_DEFLATED, allowZip64=True) as zf:
                for src, arc in entries:
                    zf.write(src, arc)
                zf.write(manifest_path, "manifest.json")
        os.replace(tmp_zip, destination)
        return {"ok": True, "name": destination.name, "path": str(destination),
                "size": destination.stat().st_size, "files": len(files)}
    except Exception as exc:
        tmp_zip.unlink(missing_ok=True)
        return {"ok": False, "error": str(exc)}


def _safe_member(name: str) -> bool:
    p = PurePosixPath(name)
    return bool(name and not p.is_absolute() and ".." not in p.parts and "\\" not in name)


def validate_recovery_package(package: Path, extract_to: Path | None = None) -> dict:
    package = Path(package)
    if not package.is_file() or package.suffix.lower() != ".zip":
        return {"ok": False, "error": "فایل Recovery معتبر نیست."}
    owned_tmp = None
    try:
        if extract_to is None:
            owned_tmp = tempfile.TemporaryDirectory(prefix="giso-validate-")
            extract_to = Path(owned_tmp.name)
        extract_to.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(package) as zf:
            infos = zf.infolist()
            if any(not _safe_member(i.filename) for i in infos):
                raise ValueError("مسیر ناامن داخل بسته شناسایی شد.")
            names = {i.filename for i in infos}
            if any(((i.external_attr >> 16) & 0o170000) == 0o120000 for i in infos):
                raise ValueError("Symlink داخل بسته مجاز نیست.")
            if sum(i.file_size for i in infos) > 5 * 1024 * 1024 * 1024:
                raise ValueError("حجم بازشده بسته بیش از حد مجاز است.")
            if not {"manifest.json", "giso.db", "giso-config.json"}.issubset(names):
                raise ValueError("اجزای اجباری بسته کامل نیست.")
            zf.extractall(extract_to)
        manifest = json.loads((extract_to / "manifest.json").read_text("utf-8"))
        if manifest.get("format") != "giso-recovery" or manifest.get("version") != FORMAT_VERSION:
            raise ValueError("نسخه بسته Recovery پشتیبانی نمی‌شود.")
        listed = manifest.get("files")
        if not isinstance(listed, list):
            raise ValueError("Manifest معتبر نیست.")
        listed_names = {item.get("path", "") for item in listed if isinstance(item, dict)}
        if names - {"manifest.json"} != listed_names:
            raise ValueError("فایل ثبت‌نشده یا مفقود در بسته وجود دارد.")
        for item in listed:
            rel = item.get("path", "")
            if not _safe_member(rel):
                raise ValueError("مسیر Manifest ناامن است.")
            file_path = extract_to / rel
            if not file_path.is_file() or file_path.stat().st_size != item.get("size") or _sha256(file_path) != item.get("sha256"):
                raise ValueError(f"Checksum نامعتبر: {rel}")
        if not _valid_db(extract_to / "giso.db"):
            raise ValueError("دیتابیس داخل بسته سالم نیست.")
        return {"ok": True, "manifest": manifest, "extract_to": str(extract_to)}
    except (OSError, ValueError, KeyError, json.JSONDecodeError, zipfile.BadZipFile) as exc:
        return {"ok": False, "error": str(exc)}
    finally:
        if owned_tmp:
            owned_tmp.cleanup()


def restore_recovery_package(package: Path) -> tuple[bool, str]:
    """Validate, replace GISO DB/files, and roll all changes back on failure."""
    RECOVERY_DIR.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="giso-restore-") as td:
        stage = Path(td) / "stage"
        checked = validate_recovery_package(Path(package), stage)
        if not checked["ok"]:
            return False, checked["error"]
        rollback = Path(td) / "rollback"
        rollback_db = rollback / "giso.db"
        had_db = DB_PATH.exists()
        # اگر DB فعلی خراب باشد، snapshot ممکن نیست؛ Recovery باید همچنان ادامه
        # یابد (دقیقاً همان سناریویی که برای آن ساخته شده) و فایل خراب جایگزین شود.
        rollback_ok = False
        if had_db:
            try:
                # _snapshot_db خودش صحت فایل را با backup + integrity_check می‌سنجد؛
                # اگر DB فعلی خراب باشد خطا می‌دهد و ما بدون snapshot ادامه می‌دهیم.
                _snapshot_db(DB_PATH, rollback_db)
                rollback_ok = True
            except (sqlite3.Error, OSError, RuntimeError) as exc:
                logger.warning(
                    "گرفتن snapshot از giso.db فعلی ممکن نشد (احتمالاً خراب است)؛ "
                    "بدون snapshot ادامه می‌دهیم: %s",
                    exc,
                )
        touched = []
        db_tmp = DB_PATH.with_name(f"{DB_PATH.name}.recovery-{os.getpid()}.tmp")
        try:
            # Preserve each overwritten upload; newly created files are recorded too.
            files_root = stage / "files"
            for source_root, target_root in ((files_root / "wallet_receipts", RECEIPTS_DIR),
                                             (files_root / "uploads", UPLOADS_DIR)):
                if not source_root.exists():
                    continue
                for src in source_root.rglob("*"):
                    if not src.is_file():
                        continue
                    rel = src.relative_to(source_root)
                    dest = target_root / rel
                    old = rollback / "files" / target_root.name / rel
                    existed = dest.exists()
                    if existed:
                        old.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copy2(dest, old)
                    touched.append((dest, old if existed else None))
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(src, dest)
            DB_PATH.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(stage / "giso.db", db_tmp)
            os.replace(db_tmp, DB_PATH)
            for suffix in ("-wal", "-shm"):
                DB_PATH.with_name(DB_PATH.name + suffix).unlink(missing_ok=True)
            if not _valid_db(DB_PATH):
                raise RuntimeError("Smoke check دیتابیس پس از Restore ناموفق بود.")
            # Deliberately do not import giso-config.json into bot.db.
            emergency = RECOVERY_DIR / f"giso_pre_restore_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"
            if rollback_ok:
                shutil.copy2(rollback_db, emergency)
            note = "نسخه اضطراری: " + emergency.name if rollback_ok else \
                "DB قبلی خراب بود؛ نسخه اضطراری ساخته نشد."
            return True, f"Recovery کامل گیسو انجام شد. {note}"
        except Exception as exc:
            if rollback_ok and rollback_db.exists():
                shutil.copy2(rollback_db, db_tmp)
                os.replace(db_tmp, DB_PATH)
            elif not had_db:
                DB_PATH.unlink(missing_ok=True)
            # حالت had_db=True ولی rollback_ok=False (DB قبلی خراب): رول‌بک ممکن نیست؛
            # اگر replace انجام شده، DB فعلی (بستهٔ معتبر) سالم می‌ماند و اگر نشده،
            # همان فایل خراب باقی می‌ماند — در هر دو مورد کرش نخواهیم کرد.
            for dest, old in reversed(touched):
                if old and old.exists():
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(old, dest)
                else:
                    dest.unlink(missing_ok=True)
            if rollback_ok:
                return False, f"Restore ناموفق بود و Rollback انجام شد: {exc}"
            return False, f"Restore ناموفق بود؛ رول‌بک ممکن نبود (DB قبلی خراب): {exc}"
        finally:
            db_tmp.unlink(missing_ok=True)
