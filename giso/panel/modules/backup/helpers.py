# -*- coding: utf-8 -*-
"""panel/modules/backup.py — پشتیبان‌گیری / بازگردانی / ریستارت ربات (فاز 5).

همان روش و مسیر ربات:
  - نسخه‌ها در giso/data/backup (giso_backup_* دستی / giso_auto_* خودکار)
  - تنظیم بازه خودکار در giso_config.backup_interval_hours (giso.db — همان کلید ربات)
  - ریستارت با flag گیسو (giso/data/giso-restart.flag) + SIGTERM به PID ربات
    → main.py watcher (هر ۱۰ ثانیه) instance جدید spawn می‌کند.

هیچ وابستگی به giso/bot.py ندارد (تا بدون telegram هم کار کند).
"""
import logging
import os
import shutil
import sqlite3
import threading
import time
from datetime import datetime
from pathlib import Path

from flask import request, redirect, url_for, flash

from giso.base import get_giso_db_conn, checkpoint_giso_db
from giso.panel.permissions import current_role_and_perms

logger = logging.getLogger("giso_panel_backup")

_GISO_DIR = Path(__file__).resolve().parent.parent.parent.parent          # giso/
DB_PATH = _GISO_DIR / "data" / "giso.db"
BACKUP_DIR = _GISO_DIR / "data" / "backup"
RESTART_FLAG = _GISO_DIR / "data" / "giso-restart.flag"
PID_FILE = _GISO_DIR / "data" / "giso-bot.pid"
_ENV_PATH = _GISO_DIR / "data" / ".env"

RESTART_OPTIONS = [5, 10, 30, 60]

# ───────────────────── دانلود بکاپ (خروج نسخه از روی سرور) + بکاپ خودکار کامل ─────────────────────
# بازه‌ی پیش‌فرض ساخت خودکار بسته‌ی کامل Recovery (ساعت). ۰ = غیرفعال.
AUTO_RECOVERY_INTERVAL_HOURS = 3
# حداکثر تعداد بسته‌های Recovery خودکار که روی دیسک نگه داشته می‌شوند.
AUTO_RECOVERY_MAX_FILES = 8



def _safe_backup_dir_file(name: str, directory: Path) -> Path | None:
    """Resolve a bare filename strictly inside `directory` (path-traversal safe)."""
    try:
        name = (name or "").strip()
        if not name or "/" in name or "\\" in name or name in (".", "..") or name.startswith("."):
            return None
        base = directory.resolve()
        candidate = (base / name).resolve()
        if base != candidate and base not in candidate.parents:
            return None
        return candidate if candidate.is_file() else None
    except Exception:
        return None

def _recovery_directory():
    from giso.recovery import RECOVERY_DIR
    return RECOVERY_DIR

def _recovery_auto_enabled() -> bool:
    """Automatic full-recovery ZIP on/off, stored in giso_config (default: on)."""
    try:
        with get_giso_db_conn() as conn:
            row = conn.execute(
                "SELECT value FROM giso_config WHERE key='recovery_auto_enabled'"
            ).fetchone()
            return not (row and str(row[0]).strip() in ("0", "off", "false"))
    except Exception:
        return True

def _set_recovery_auto_enabled(enabled: bool) -> bool:
    try:
        with get_giso_db_conn() as conn:
            conn.execute(
                "CREATE TABLE IF NOT EXISTS giso_config ("
                "id INTEGER PRIMARY KEY AUTOINCREMENT, "
                "key TEXT UNIQUE NOT NULL, value TEXT DEFAULT '', "
                "updated_at TEXT DEFAULT '')"
            )
            conn.execute(
                "INSERT INTO giso_config (key, value, updated_at) "
                "VALUES ('recovery_auto_enabled', ?, ?) "
                "ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_at=excluded.updated_at",
                ("1" if enabled else "0", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
            )
            conn.commit()
        return True
    except Exception as exc:
        logger.warning("recovery auto toggle: %s", exc)
        return False

def build_recovery_package(kind: str = "manual") -> dict:
    """Create a full recovery ZIP (db + uploads + receipts). Safe to call repeatedly."""
    try:
        from giso.recovery import create_recovery_package
        result = create_recovery_package()
        if result.get("ok") and kind == "auto":
            _prune_auto_recovery()
        return result
    except Exception as exc:
        logger.warning("build_recovery_package: %s", exc)
        return {"ok": False, "error": str(exc)}

def _prune_auto_recovery():
    """Keep only the newest AUTO_RECOVERY_MAX_FILES recovery ZIPs on disk."""
    try:
        rdir = _recovery_directory()
        if not rdir.exists():
            return
        zips = sorted(rdir.glob("giso_recovery_*.zip"),
                      key=lambda p: p.stat().st_mtime, reverse=True)
        for old in zips[AUTO_RECOVERY_MAX_FILES:]:
            try:
                old.unlink()
            except Exception:
                pass
    except Exception as exc:
        logger.warning("recovery prune: %s", exc)

def maybe_auto_recovery(force: bool = False):
    """Create an automatic full-recovery ZIP if the latest one is older than the interval.

    Runs the (potentially heavy) ZIP build in a background thread so a web request is
    never blocked; guarded against overlapping runs. Failures are logged, never raised.
    """
    def _due() -> bool:
        try:
            if not _recovery_auto_enabled():
                return False
            rdir = _recovery_directory()
            newest = 0.0
            if rdir.exists():
                zips = list(rdir.glob("giso_recovery_*.zip"))
                if zips:
                    newest = max(p.stat().st_mtime for p in zips)
            age_hours = (time.time() - newest) / 3600.0 if newest else 1e9
            return force or age_hours >= AUTO_RECOVERY_INTERVAL_HOURS
        except Exception:
            return False

    if not _due():
        return
    if not _auto_recovery_lock.acquire(blocking=False):
        return
    try:
        if _auto_recovery_running["v"]:
            return
        _auto_recovery_running["v"] = True

        def _worker():
            try:
                build_recovery_package(kind="auto")
            except Exception as exc:
                logger.warning("auto recovery worker: %s", exc)
            finally:
                _auto_recovery_running["v"] = False
                try:
                    _auto_recovery_lock.release()
                except RuntimeError:
                    pass

        threading.Thread(target=_worker, name="giso-auto-recovery", daemon=True).start()
    except Exception:
        try:
            _auto_recovery_lock.release()
        except RuntimeError:
            pass

def _max_files() -> int:
    """حداکثر تعداد فایل‌های نگهداری‌شده (از giso/data/.env مثل ربات)."""
    try:
        if _ENV_PATH.exists():
            for line in _ENV_PATH.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if line.startswith("GISO_BACKUP_MAX_FILES="):
                    val = line.split("=", 1)[1].strip() or "5"
                    return max(1, int(val))
    except Exception:
        pass
    return 5

def _generate_manifest(backup_path: Path, db_path: Path, uploads_dir: Path):
    import json, sqlite3
    try:
        conn = sqlite3.connect(str(db_path))
        cur = conn.execute("SELECT count(*) FROM sqlite_master WHERE type='table'")
        table_count = cur.fetchone()[0]
        conn.close()
    except Exception:
        table_count = 0
    manifest = {
        "backup_time": datetime.now().isoformat(),
        "version": "1.0",
        "db_path": str(db_path),
        "uploads_dir": str(uploads_dir),
        "files_backed_up": [str(db_path.name), "uploads/"],
        "db_tables": table_count,
    }
    manifest_path = backup_path.parent / "manifest_latest.json"
    try:
        manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        pass

def _pre_restore_check(source_path: Path, current_db: Path) -> bool:
    """Pre-restore safety: verify source DB exists and basic integrity; never drop current DB."""
    if not source_path.exists():
        return False
    try:
        conn = sqlite3.connect(str(source_path))
        cur = conn.execute("SELECT count(*) FROM sqlite_master WHERE type='table'")
        result = cur.fetchone()[0] > 0
        conn.close()
        return result
    except Exception:
        return False

def _safe_restore(source_path: Path, current_db: Path):
    """Safe restore: copy current DB to .pre-restore before replacing; only replace if pre-check passed."""
    if not _pre_restore_check(source_path, current_db):
        raise RuntimeError("Pre-restore check failed: source DB invalid or missing.")
    pre_path = current_db.with_suffix(current_db.suffix + ".pre-restore")
    try:
        shutil.copy2(str(current_db), str(pre_path))
    except Exception:
        pass
    shutil.copy2(str(source_path), str(current_db))

def _write_restart_flag():
    """ساخت flag ریستارت — main.py watcher آن را می‌خواند و instance جدید spawn می‌کند.

    فقط از POST/thread ریستارت صدا زده می‌شود؛ هرگز از رندر.
    """
    RESTART_FLAG.parent.mkdir(parents=True, exist_ok=True)
    RESTART_FLAG.write_text(str(int(time.time())))

def _process_is_giso_bot(pid: int) -> bool:
    """آیا PID داده‌شده متعلق به فرایند «گیسوبات» است؟ (جلوگیری از کشتن فرایند اشتباه)

    فقط وقتی ربات را SIGTERM می‌کنیم که cmdline فرایند شامل giso/bot.py باشد؛
    در غیر این صورت flag تنها می‌ماند و watcher در اولین spawn بعدی آن را مصرف می‌کند.
    """
    try:
        if os.name == "nt":
            out = os.popen(f'tasklist /FI "PID eq {int(pid)}"').read() or ""
            return "python" in out.lower() and "bot" in out.lower()
        # لینوکس/مک: /proc یا ps
        proc_cmdline = Path(f"/proc/{int(pid)}/cmdline")
        if proc_cmdline.exists():
            args = proc_cmdline.read_text(errors="ignore").replace("\x00", " ")
            return ("giso" in args and "bot.py" in args) or args.strip().endswith("bot.py")
        out = os.popen(f"ps -p {int(pid)} -o args=").read() or ""
        return ("giso" in out and "bot.py" in out) or out.strip().endswith("bot.py")
    except Exception as e:
        logger.debug(f"_process_is_giso_bot({pid}): {e}")
        return False

def _kill_giso_bot_if_running():
    """اگر PID ربات موجود، زنده و متعلق به گیسوبات بود SIGTERM می‌فرستد تا watcher دوباره spawn کند.

    فقط از POST/thread ریستارت صدا زده می‌شود؛ هرگز از رندر.
    """
    try:
        if PID_FILE.exists():
            pid = int((PID_FILE.read_text(encoding="utf-8").strip() or "0"))
            if pid <= 0:
                return False
            if not _process_is_giso_bot(pid):
                logger.warning(
                    f"ریستارت: PID {pid} متعلق به گیسوبات نیست؛ فقط flag گذاشته شد "
                    f"(watcher در spawn بعدی اجرا می‌کند).")
                return False
            try:
                os.kill(pid, 15)  # SIGTERM
                return True
            except ProcessLookupError:
                return False
            except PermissionError:
                return False
    except (ValueError, TypeError):
        pass
    except Exception as e:
        logger.warning(f"panel kill pid: {e}")
    return False

def _read_pending_deadline() -> int | None:
    """فقط خواندن مهلت pending — بدون هیچ عارضه (بدون حذف فایل، بدون flag، بدون سیگنال)."""
    try:
        if not RESTART_PENDING_FILE.exists():
            return None
        raw = RESTART_PENDING_FILE.read_text(encoding="utf-8").strip()
        deadline = int(raw or "0")
        return deadline if deadline > 0 else None
    except (ValueError, TypeError, OSError):
        return None
    except Exception as e:
        logger.debug(f"_read_pending_deadline: {e}")
        return None

def _write_pending(seconds: int) -> int | None:
    """ایجاد اتمیک فایل pending (فقط از POST). اگر فایل موجود باشد → None (race جلوگیری می‌شود)."""
    deadline = int(time.time()) + int(seconds)
    try:
        RESTART_PENDING_FILE.parent.mkdir(parents=True, exist_ok=True)
        fd = os.open(RESTART_PENDING_FILE, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(str(deadline))
        return deadline
    except FileExistsError:
        return None
    except Exception as e:
        logger.warning(f"_write_pending: {e}")
        return None

def _cleanup_expired_pending():
    """پاک‌کردن pending منقضی‌شده/مرده — **فقط از POST** صدا زده می‌شود."""
    try:
        deadline = _read_pending_deadline()
        if deadline and int(time.time()) >= deadline:
            RESTART_PENDING_FILE.unlink()
    except Exception as e:
        logger.debug(f"_cleanup_expired_pending: {e}")

def is_giso_bot_running() -> bool:
    """بررسی زنده بودن ربات — **بدون ارسال هیچ سیگنالی** (فقط وجود فرایند از /proc یا ps).

    مجاز در رندر صفحه: هیچ SIGTERM/kill/exit در این مسیر نیست.
    """
    try:
        if not PID_FILE.exists():
            return False
        pid = int(PID_FILE.read_text(encoding="utf-8").strip() or "0")
        if pid <= 0:
            return False
        if os.name == "nt":
            out = os.popen(f'tasklist /FI "PID eq {pid}"').read() or ""
            return str(pid) in out
        if Path(f"/proc/{pid}").exists():
            return True
        out = os.popen(f"ps -p {pid} -o pid=").read() or ""
        return str(pid) in out.split()
    except Exception:
        return False

_auto_recovery_lock = threading.Lock()
_auto_recovery_running = {"v": False}

RESTART_PENDING_FILE = _GISO_DIR / "data" / "giso-restart.pending"
