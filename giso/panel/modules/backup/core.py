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


from giso.panel.modules import backup as _bpkg
from .helpers import *  # noqa: F401,F403
from .helpers import RESTART_PENDING_FILE  # noqa: F401 (شیء مشترک)
from .helpers import _cleanup_expired_pending, _generate_manifest, _kill_giso_bot_if_running, _max_files, _pre_restore_check, _read_pending_deadline, _recovery_auto_enabled, _recovery_directory, _safe_backup_dir_file, _set_recovery_auto_enabled, _write_pending  # noqa: F401


def _require_super():
    role, perms, bale_id = current_role_and_perms()
    if role != "super":
        flash("فقط سوپرادمین می‌تواند این عملیات را انجام دهد.", "warning")
        return redirect(url_for("panel.settings"))
    return None

def list_backup_files():
    """لیست نسخه‌های پشتیبان از جدیدترین به قدیمی‌ترین (نام/مسیر/حجم/زمان)."""
    out = []
    try:
        BACKUP_DIR.mkdir(parents=True, exist_ok=True)
        for f in os.listdir(BACKUP_DIR):
            if f.startswith("giso") and f.endswith(".db"):
                p = BACKUP_DIR / f
                try:
                    out.append({
                        "name": f,
                        "path": str(p),
                        "size": os.path.getsize(p),
                        "mtime": os.path.getmtime(p),
                        "mtime_fa": datetime.fromtimestamp(os.path.getmtime(p)).strftime("%Y-%m-%d %H:%M"),
                    })
                except Exception:
                    continue
        out.sort(key=lambda x: x["mtime"], reverse=True)
    except Exception as e:
        logger.error(f"panel backup list: {e}")
    return out

def take_backup(kind: str = "manual") -> dict:
    """ساخت نسخه پشتیبان (checkpoint + کپی + هرس) — مثل ربات."""
    ok_check = checkpoint_giso_db()
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    prefix = "giso_backup_" if kind == "manual" else "giso_auto_"
    path = BACKUP_DIR / f"{prefix}{ts}.db"
    if not DB_PATH.exists():
        return {"ok": False, "name": "", "error": "فایل دیتابیس پیدا نشد."}
    shutil.copy2(DB_PATH, path)
    try:
        _generate_manifest(path, DB_PATH, _GISO_DIR / "data" / "uploads")
    except Exception:
        pass  # manifest non-critical
    # هرس نسخه‌های قدیمی (نگه داشتن N آخر) — مثل ربات
    try:
        files = sorted(f for f in os.listdir(BACKUP_DIR)
                       if f.startswith(prefix) and f.endswith(".db"))
        maxf = _max_files()
        while len(files) > maxf:
            old = BACKUP_DIR / files.pop(0)
            try:
                old.unlink()
            except Exception:
                pass
    except Exception as e:
        logger.warning(f"backup prune: {e}")
    return {
        "ok": True,
        "name": path.name,
        "path": str(path),
        "size": os.path.getsize(path),
        "checkpoint": bool(ok_check),
    }

def get_backup_interval_hours() -> int:
    """بازه backup خودکار (ساعت؛ ۰ = غیرفعال) — همان کلید ربات در giso.db."""
    try:
        with get_giso_db_conn() as conn:
            row = conn.execute(
                "SELECT value FROM giso_config WHERE key='backup_interval_hours'"
            ).fetchone()
            if row and row[0]:
                return int(row[0])
    except Exception:
        pass
    return 0

def set_backup_interval_hours(hours: int) -> bool:
    """ذخیره بازه backup خودکار (giso.db — همان کلید ربات)."""
    try:
        with get_giso_db_conn() as conn:
            conn.execute(
                "CREATE TABLE IF NOT EXISTS giso_config ("
                "id INTEGER PRIMARY KEY AUTOINCREMENT, "
                "key TEXT UNIQUE NOT NULL, value TEXT DEFAULT '', "
                "updated_at TEXT DEFAULT '')"
            )
            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            conn.execute(
                "INSERT INTO giso_config (key, value, updated_at) "
                "VALUES ('backup_interval_hours', ?, ?) "
                "ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_at=excluded.updated_at",
                (str(int(hours)), now)
            )
            conn.commit()
        return True
    except Exception as e:
        logger.error(f"panel set backup interval: {e}")
        return False

def restore_backup(source_path) -> tuple:
    """بازگردانی giso.db از نسخه (همان منطق امن ربات: checkpoint + integrity + safety)."""
    source_path = str(source_path or "")
    if not source_path or not os.path.exists(source_path):
        return False, "فایل بکاپ پیدا نشد."
    if not source_path.lower().endswith(".db"):
        return False, "فقط فایل .db قابل قبول است."
    if not _pre_restore_check(Path(source_path), DB_PATH):
        return False, "Pre-restore check failed: backup file invalid or missing."
    checkpoint_giso_db()
    # بررسی سلامت فایل
    try:
        c = sqlite3.connect(source_path)
        row = c.execute("PRAGMA integrity_check").fetchone()
        c.close()
        if not row or str(row[0]).lower() != "ok":
            return False, "فایل دیتابیس معتبر نیست (integrity check ناموفق)."
    except Exception as e:
        return False, f"فایل قابل خواندن نیست: {e}"
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    pre = BACKUP_DIR / f"giso_pre_restore_{ts}.db"
    # فایل موقت در همان دایرکتوری DB — جایگزینی اتمیک با os.replace (رفع باگ
    # غیراتومیک بودن copy2 مستقیم روی فایل زنده، 2026-08-22)
    tmp = DB_PATH.with_name(f"{DB_PATH.name}.restore-{os.getpid()}.tmp")
    replaced = False
    try:
        if DB_PATH.exists():
            shutil.copy2(DB_PATH, pre)
        shutil.copy2(source_path, tmp)
        os.replace(tmp, DB_PATH)  # اتمیک: یا کامل جایگزین می‌شود یا اصلاً
        replaced = True
    except Exception as e:
        if not replaced and pre.exists():
            try:
                shutil.copy2(pre, DB_PATH)
            except Exception:
                pass
        return False, f"بازگردانی ناموفق و rollback انجام شد: {e}"
    finally:
        try:
            if tmp.exists():
                tmp.unlink()
        except Exception:
            pass
    # پاک‌سازی WAL/SHM قدیمی که به فایل قبلی تعلق دارند (best-effort)
    for suffix in ("-wal", "-shm"):
        try:
            (DB_PATH.parent / f"{DB_PATH.name}{suffix}").unlink(missing_ok=True)
        except Exception:
            pass
    # checkpoint بعد از restore: انتقال هر WAL تازه به فایل اصلی
    try:
        checkpoint_giso_db()
    except Exception:
        pass
    return True, f"بازگردانی انجام شد. نسخه امن قبلی: {pre.name}"

def pending_restart_info() -> dict | None:
    """وضعیت ریستارت در انتظار — **فقط خواندن**؛ هیچ اجرای واقعی انجام نمی‌دهد.

    مجاز در رندر صفحه: صرفاً نمایش «چند ثانیه مانده». هیچ flag/سیگنال/حذفی در GET نیست.
    """
    deadline = _read_pending_deadline()
    if not deadline:
        return None
    remaining = deadline - int(time.time())
    if remaining <= 0:
        # منقضی‌شده: نمایش داده نمی‌شود (تمیزکاری فایل فقط در POST انجام می‌شود)
        return None
    return {"remaining": remaining}

def execute_pending_restart(expected_deadline: int | None = None) -> bool:
    """اجرای ریستارتِ در انتظار اگر مهلتش رسیده باشد — فقط از thread ناشی از POST.

    - بدون expected_deadline: فقط بررسی «مهلت رسیده» (سازگاری با فراخوانی‌های قدیمی/تست).
    - با expected_deadline: اگر فایل pending متعلق به arm دیگری باشد اجرا نمی‌شود (anti-race).
    """
    try:
        deadline = _read_pending_deadline()
        if not deadline:
            return False
        if expected_deadline is not None and int(expected_deadline) != deadline:
            return False  # pending متعلق به arm جدیدتری است — اجرا نکن
        if int(time.time()) < deadline:
            return False
        _bpkg._write_restart_flag()
        _kill_giso_bot_if_running()
        try:
            RESTART_PENDING_FILE.unlink()
        except Exception:
            pass
        return True
    except (ValueError, TypeError):
        return False
    except Exception as e:
        logger.warning(f"execute_pending_restart: {e}")
        return False

def cancel_bot_restart() -> bool:
    """لغو ریستارت در انتظار (فقط از POST؛ فایل pending حذف می‌شود و thread بی‌اثر می‌شود)."""
    try:
        if RESTART_PENDING_FILE.exists():
            RESTART_PENDING_FILE.unlink()
            return True
    except Exception as e:
        logger.warning(f"cancel_bot_restart: {e}")
    return False

def request_bot_restart(seconds: int = 5) -> bool:
    """درخواست ریستارت ربات با شمارش معکوس قابل لغو — فقط از POST هدفمند.

    - اگر ریستارتی فعال در انتظار باشد، درخواست جدید ثبت نمی‌شود (False).
    - pending منقضی/مرده ابتدا پاک می‌شود، سپس فایل جدید به‌صورت اتمیک ساخته می‌شود.
    - یک thread آن را پس از N ثانیه اجرا می‌کند (تنها executor ریستارت).
    - رندر/GET هیچ‌کدام از این مسیر را صدا نمی‌زنند.
    """
    try:
        seconds = int(seconds)
    except (TypeError, ValueError):
        seconds = 5
    if seconds not in RESTART_OPTIONS:
        seconds = 5
    # pending فعال (مهلت آینده) → درخواست جدید رد می‌شود
    if pending_restart_info() is not None:
        return False
    # پاک‌سازی pending منقضی/مرده (فقط در POST)
    _cleanup_expired_pending()

    deadline = _write_pending(seconds)
    if deadline is None:
        # race: درخواست هم‌زمان دیگری برنده شده
        return False

    def _do():
        try:
            time.sleep(max(0, deadline - int(time.time())))
        except Exception:
            time.sleep(seconds)
        # فقط اگر هنوز لغو نشده، مهلت رسیده و متعلق به همین arm باشد اجرا می‌شود
        execute_pending_restart(expected_deadline=deadline)

    t = threading.Thread(target=_do, daemon=True, name="giso_restart_trigger")
    t.start()
    return True

def handle_backup_now():
    g = _require_super()
    if g:
        return g
    try:
        res = take_backup("manual")
        if res.get("ok"):
            size_kb = int(res.get("size", 0)) // 1024
            try:
                from giso.panel.modules.notifications import safe_log as _nlog
                _nlog("system", "backup", "بکاپ دستی",
                      f"نسخه پشتیبان {res.get('name', '')} ({size_kb} KB)",
                      source_type="system_backup", source_id=None)
            except Exception:
                pass
            flash(f"✅ نسخه پشتیبان گرفته شد: {res['name']} ({size_kb} KB)", "success")
        else:
            flash(f"❌ {res.get('error') or 'خطا در تهیه نسخه'}", "danger")
    except Exception as e:
        logger.error(f"panel backup_now: {e}")
        flash("❌ خطا در تهیه نسخه پشتیبان.", "danger")
    return redirect(url_for("panel.settings"))

def handle_set_interval():
    g = _require_super()
    if g:
        return g
    try:
        hours = int(request.form.get("hours", "0") or "0")
        hours = max(0, min(168, hours))
        ok = set_backup_interval_hours(hours)
        if ok:
            msg = f"⏱ backup خودکار: هر {hours} ساعت" if hours > 0 else "⏱ backup خودکار غیرفعال شد"
            # timer ربات در استارت مقدار می‌گیرد؛ برای اعمال فوری ریستارت لازم است
            flash(f"✅ {msg}. برای اعمال فوری، ربات را از بخش «🔄 ریستارت ربات» ریستارت کنید (در غیر این صورت از استارت بعدی ربات اعمال می‌شود).", "success")
        else:
            flash("❌ خطا در ذخیره بازه backup.", "danger")
    except (TypeError, ValueError):
        flash("⚠️ مقدار بازه معتبر نیست.", "warning")
    except Exception as e:
        logger.error(f"panel set interval: {e}")
        flash("❌ خطا در ذخیره بازه.", "danger")
    return redirect(url_for("panel.settings"))

def handle_upload():
    """آپلود نسخه دستی (.db) به پوشه backup — مثل handle_backup_upload ربات."""
    g = _require_super()
    if g:
        return g
    f = request.files.get("backup_file")
    if not f or not f.filename:
        flash("⚠️ فایلی انتخاب نشده است.", "warning")
        return redirect(url_for("panel.settings"))
    if not f.filename.lower().endswith(".db"):
        flash("❌ فقط فایل .db قابل آپلود است.", "danger")
        return redirect(url_for("panel.settings"))
    try:
        BACKUP_DIR.mkdir(parents=True, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_name = "".join(ch for ch in os.path.basename(f.filename) if ch.isalnum() or ch in "._-")
        name = f"giso_upload_{ts}_{safe_name or 'backup.db'}"
        dest = BACKUP_DIR / name
        f.save(dest)
        flash(f"✅ نسخه «{name}» در پوشه backup قرار گرفت.", "success")
    except Exception as e:
        logger.error(f"panel backup upload: {e}")
        flash("❌ خطا در ذخیره فایل.", "danger")
    return redirect(url_for("panel.settings"))

def handle_delete_file():
    """حذف هر فایل دیتابیس بکاپ داخل پوشه backup (فقط سوپر)."""
    g = _require_super()
    if g:
        return g
    name = (request.form.get("file") or "").strip()
    if not name or "/" in name or "\\" in name or not name.endswith(".db"):
        flash("نام فایل نامعتبر است.", "danger")
        return redirect(url_for("panel.settings"))
    src = BACKUP_DIR / name
    try:
        if not src.exists() or not src.is_file():
            flash("فایل بکاپ پیدا نشد.", "danger")
            return redirect(url_for("panel.settings"))
        src.unlink()
        flash(f"فایل «{name}» حذف شد.", "success")
    except Exception as e:
        logger.error(f"panel backup delete: {e}")
        flash("خطا در حذف فایل بکاپ.", "danger")
    return redirect(url_for("panel.settings"))

def handle_restore():
    """بازگردانی دومرحله‌ای (بدون تایپ) — مثل حذف دومرحله‌ای سایر بخش‌ها."""
    g = _require_super()
    if g:
        return g
    from flask import session
    step = (request.form.get("step") or "").strip()
    if step == "confirm":
        name = (request.form.get("file") or "").strip()
        # امنیت: فقط فایل‌های داخل پوشه backup
        if not name or "/" in name or "\\" in name or not name.startswith("giso"):
            flash("⚠️ نام فایل نامعتبر است.", "danger")
            return redirect(url_for("panel.settings"))
        src = BACKUP_DIR / name
        if not src.exists():
            flash("❌ نسخه پیدا نشد.", "danger")
            return redirect(url_for("panel.settings"))
        ok, msg = restore_backup(str(src))
        flash(("✅ " if ok else "❌ ") + msg, "success" if ok else "danger")
        session.pop("panel_restore_file", None)
        return redirect(url_for("panel.settings"))
    # مرحله اول: ثبت درخواست در session
    name = (request.form.get("file") or "").strip()
    if not name or "/" in name or "\\" in name or not name.startswith("giso"):
        flash("⚠️ نام فایل نامعتبر است.", "danger")
        return redirect(url_for("panel.settings"))
    if not (BACKUP_DIR / name).exists():
        flash("❌ نسخه پیدا نشد.", "danger")
        return redirect(url_for("panel.settings"))
    session["panel_restore_file"] = name
    session.modified = True
    flash(f"⚠️ آیا از بازگردانی «{name}» مطمئن هستید؟ دکمه بازگردانی را دوباره بزنید.", "warning")
    return redirect(url_for("panel.settings"))

def _recovery_files():
    from giso.recovery import RECOVERY_DIR
    RECOVERY_DIR.mkdir(parents=True, exist_ok=True)
    out = []
    for path in RECOVERY_DIR.glob("giso_recovery_*.zip"):
        if path.is_file():
            out.append({"name": path.name, "size": path.stat().st_size,
                        "mtime": path.stat().st_mtime,
                        "mtime_fa": datetime.fromtimestamp(path.stat().st_mtime).strftime("%Y-%m-%d %H:%M")})
    return sorted(out, key=lambda row: row["mtime"], reverse=True)

def _giso_maintenance_enabled() -> bool:
    """Fail closed: full recovery is allowed only while GISO maintenance is on."""
    from giso.recovery import BOT_DB_PATH
    try:
        with sqlite3.connect(f"file:{BOT_DB_PATH}?mode=ro", uri=True) as conn:
            tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            for table in ("settings", "giso_config"):
                if table in tables:
                    row = conn.execute(f'SELECT value FROM "{table}" WHERE key=?', ("giso_maintenance",)).fetchone()
                    if row and str(row[0]).strip().lower() in {"1", "true", "on", "yes"}:
                        return True
    except Exception as exc:
        logger.warning("recovery maintenance check failed: %s", exc)
    return False

def handle_recovery_create():
    g = _require_super()
    if g:
        return g
    from giso.recovery import create_recovery_package
    result = create_recovery_package()
    if result.get("ok"):
        flash(f"✅ بسته Recovery مستقل گیسو ساخته شد: {result['name']}", "success")
    else:
        flash(f"❌ ساخت Recovery ناموفق بود: {result.get('error', '')}", "danger")
    return redirect(url_for("panel.settings"))

def _download_headers_response(path: Path, download_name: str):
    """send_file with attachment disposition so the file leaves the server."""
    from flask import send_file
    try:
        return send_file(str(path), as_attachment=True, download_name=download_name)
    except TypeError:
        # Older Flask: use mimetype + attachment_headers fallback.
        resp = send_file(str(path))
        resp.headers["Content-Disposition"] = f'attachment; filename="{download_name}"'
        return resp

def handle_recovery_download():
    """Download a recovery ZIP from the server (off-site backup enabler). GET + super."""
    g = _require_super()
    if g:
        return g
    from flask import abort
    name = (request.args.get("file") or "").strip()
    path = _safe_backup_dir_file(name, _recovery_directory())
    if not path or path.suffix.lower() != ".zip" or not path.name.startswith("giso_recovery_"):
        abort(404)
    return _download_headers_response(path, path.name)

def handle_backup_download():
    """Download a raw .db backup from the server. GET + super."""
    g = _require_super()
    if g:
        return g
    from flask import abort
    name = (request.args.get("file") or "").strip()
    path = _safe_backup_dir_file(name, BACKUP_DIR)
    if not path or path.suffix.lower() != ".db" or not path.name.startswith("giso"):
        abort(404)
    return _download_headers_response(path, path.name)

def handle_recovery_download_latest():
    """Build a fresh ZIP (if none newer than the interval) and stream it immediately."""
    g = _require_super()
    if g:
        return g
    from flask import abort
    try:
        rdir = _recovery_directory()
        rdir.mkdir(parents=True, exist_ok=True)
        newest = None
        zips = sorted(rdir.glob("giso_recovery_*.zip"),
                      key=lambda p: p.stat().st_mtime, reverse=True)
        if zips and (time.time() - zips[0].stat().st_mtime) / 3600.0 < 1:
            newest = zips[0]
        if newest is None:
            result = build_recovery_package(kind="manual")
            if not result.get("ok"):
                flash(f"❌ ساخت بسته Recovery ناموفق بود: {result.get('error', '')}", "danger")
                return redirect(url_for("panel.settings"))
            newest = Path(result["path"])
        if not newest or not newest.is_file():
            abort(404)
        return _download_headers_response(newest, newest.name)
    except Exception as exc:
        logger.warning("recovery download latest: %s", exc)
        flash("دانلود بسته Recovery ممکن نشد.", "danger")
        return redirect(url_for("panel.settings"))

def handle_recovery_auto_toggle():
    g = _require_super()
    if g:
        return g
    enabled = (request.form.get("recovery_auto") or "1") == "1"
    if _set_recovery_auto_enabled(enabled):
        flash(f"بکاپ خودکار کامل (هر {AUTO_RECOVERY_INTERVAL_HOURS} ساعت) {'فعال شد' if enabled else 'غیرفعال شد'}.", "success")
        if enabled:
            # درخواست فوری نسخه‌ی اول در پس‌زمینه
            try:
                maybe_auto_recovery(force=True)
            except Exception:
                pass
    else:
        flash("ذخیره تنظیم بکاپ خودکار ناموفق بود.", "danger")
    return redirect(url_for("panel.settings"))

def handle_recovery_upload():
    g = _require_super()
    if g:
        return g
    from giso.recovery import RECOVERY_DIR, validate_recovery_package
    uploaded = request.files.get("recovery_file")
    if not uploaded or not uploaded.filename or not uploaded.filename.lower().endswith(".zip"):
        flash("❌ فقط بسته ZIP معتبر Recovery قابل قبول است.", "danger")
        return redirect(url_for("panel.settings"))
    RECOVERY_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    dest = RECOVERY_DIR / f"giso_recovery_upload_{stamp}.zip"
    uploaded.save(dest)
    checked = validate_recovery_package(dest)
    if not checked.get("ok"):
        dest.unlink(missing_ok=True)
        flash(f"❌ بسته رد شد: {checked.get('error', '')}", "danger")
    else:
        flash(f"✅ بسته Recovery بررسی و ذخیره شد: {dest.name}", "success")
    return redirect(url_for("panel.settings"))

def handle_recovery_restore():
    g = _require_super()
    if g:
        return g
    from giso.recovery import RECOVERY_DIR, restore_recovery_package
    name = (request.form.get("file") or "").strip()
    confirmation = (request.form.get("confirmation") or "").strip()
    if not name.startswith("giso_recovery_") or not name.endswith(".zip") or "/" in name or "\\" in name:
        flash("❌ نام بسته Recovery نامعتبر است.", "danger")
    elif confirmation != "RECOVER":
        flash("❌ برای بازگردانی باید عبارت RECOVER را دقیق وارد کنید.", "danger")
    elif not _giso_maintenance_enabled():
        flash("❌ ابتدا حالت به‌روزرسانی گیسو را از مدیریت سایت فعال کنید.", "danger")
    else:
        source = RECOVERY_DIR / name
        ok, message = restore_recovery_package(source)
        flash(("✅ " if ok else "❌ ") + message, "success" if ok else "danger")
    return redirect(url_for("panel.settings"))

def handle_restart():
    """ریستارت ربات با تایمر ۵/۱۰/۳۰/۶۰ ثانیه (فقط سوپرادمین) — فقط با دکمه مخصوص خودش.

    امنیت (فاز 5.2):
      - فقط POST با فیلد seconds از فرم مخصوص ریستارت پذیرفته می‌شود.
      - مقدار seconds باید دقیقاً یکی از گزینه‌های مجاز باشد؛ مقدار نامعتبر → رد بدون ریستارت.
      - اگر قبلاً ریستارتی در انتظار باشد، درخواست جدید ثبت نمی‌شود و دکمه «لغو» آن را کنسل می‌کند.
    """
    g = _require_super()
    if g:
        return g
    if "seconds" not in request.form:
        flash("درخواست ریستارت نامعتبر است (فقط از دکمه ریستارت می‌توانید اقدام کنید).", "warning")
        return redirect(url_for("panel.settings"))
    try:
        seconds = int(request.form.get("seconds"))
    except (TypeError, ValueError):
        seconds = None
    if seconds not in RESTART_OPTIONS:
        flash("⚠️ زمان ریستارت نامعتبر است؛ ریستارتی اجرا نشد.", "warning")
        return redirect(url_for("panel.settings"))
    if pending_restart_info() is not None:
        flash("⚠️ ریستارتی در انتظار است؛ ابتدا آن را لغو کنید یا صبر کنید.", "warning")
        return redirect(url_for("panel.settings"))
    ok = request_bot_restart(seconds)
    if ok:
        try:
            from giso.panel.modules.notifications import safe_log as _nlog
            _nlog("system", "restart", "ریستارت ربات",
                  f"ریستارت تا {seconds} ثانیه دیگر",
                  source_type="system_restart", source_id=None)
        except Exception:
            pass
        flash(f"🔄 ریستارت ربات تا {seconds} ثانیه دیگر انجام می‌شود — برای انصراف دکمه «لغو» را بزنید.", "success")
    else:
        flash("⚠️ ریستارتی در انتظار است؛ ابتدا آن را لغو کنید.", "warning")
    return redirect(url_for("panel.settings"))

def handle_restart_cancel():
    """لغو ریستارت در انتظار (فقط سوپرادمین)."""
    g = _require_super()
    if g:
        return g
    if cancel_bot_restart():
        flash("❌ ریستارت در انتظار لغو شد.", "success")
    else:
        flash("ریستارتی در انتظار نیست.", "info")
    return redirect(url_for("panel.settings"))

def context():
    files = list_backup_files()
    pending = pending_restart_info()
    # ساخت خودکار بسته‌ی کامل Recovery در صورت رسیدن موعد (در thread پس‌زمینه؛
    # رندر پنل را نمی‌بندد). این تابع هر ۳ ساعت یک‌بار واقعاً بسته می‌سازد و بقیه دفعات no-op است.
    try:
        maybe_auto_recovery()
    except Exception as exc:
        logger.warning("maybe_auto_recovery on settings view: %s", exc)
    return {
        "files": files,
        "interval_hours": get_backup_interval_hours(),
        "restart_options": RESTART_OPTIONS,
        "bot_running": is_giso_bot_running(),
        "pending_restart": pending,
        "backup_dir_exists": BACKUP_DIR.exists(),
        "recovery_files": _recovery_files(),
        "recovery_maintenance": _giso_maintenance_enabled(),
        "recovery_auto_enabled": _recovery_auto_enabled(),
        "recovery_auto_interval_hours": AUTO_RECOVERY_INTERVAL_HOURS,
    }
