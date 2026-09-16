# -*- coding: utf-8 -*-
"""
bot_backup — عملیات فایل پشتیبان‌گیری giso.db: لیست/جزئیات/بازیابی اتمیک/تنظیم بازه (بدون تایمر — تایمرها در bot.py می‌مانند)
Phase 2 / U6 extraction from giso/bot.py — NO behavior change; re-exported from giso.bot.
"""
import os
import logging

logger = logging.getLogger("giso_bot")




def _backup_dir():
    return os.path.join(os.path.dirname(__file__), "data", "backup")



def _list_backup_files():
    backup_dir = _backup_dir()
    try:
        os.makedirs(backup_dir, exist_ok=True)
        return sorted(
            [f for f in os.listdir(backup_dir) if f.endswith(".db")],
            reverse=True,
        )
    except Exception:
        return []



def _backup_max_files():
    try:
        from giso.ai_brain import _read_env_file
        env_vars = _read_env_file()
        return int(env_vars.get("GISO_BACKUP_MAX_FILES", "5") or "5")
    except Exception:
        return 5



def _list_backup_files_detail(db_type='giso'):
    """
    لیست فایل‌های بکاپ با جزئیات (name/path/size/mtime) مرتب از جدیدترین به قدیمی‌ترین.
    db_type: 'giso' (فقط نوع گیسو پشتیبانی می‌شود).
    """
    backup_dir = _backup_dir()
    prefix = 'giso'
    out = []
    try:
        os.makedirs(backup_dir, exist_ok=True)
        for f in os.listdir(backup_dir):
            if f.startswith(prefix) and f.endswith('.db'):
                p = os.path.join(backup_dir, f)
                try:
                    size = os.path.getsize(p)
                    mtime = os.path.getmtime(p)
                except Exception:
                    size, mtime = 0, 0
                out.append({'name': f, 'path': p, 'size': size, 'mtime': mtime})
        out.sort(key=lambda x: x['mtime'], reverse=True)
    except Exception:
        pass
    return out



def _giso_restore_from_path(source_path):
    """
    بازگردانی giso.db از مسیر مشخص با checkpoint + safety + integrity + rollback.
    جایگزینی اتمیک (کپی به temp + os.replace) + پاک‌سازی WAL/SHM قدیمی
    + checkpoint بعد از restore (رفع باگ غیراتومیک بودن کپی مستقیم، 2026-08-22).
    خروجی: (success: bool, message: str)
    """
    import shutil
    from datetime import datetime
    db_path = os.path.join(os.path.dirname(__file__), "data", "giso.db")
    if not source_path or not os.path.exists(source_path):
        return False, "فایل بکاپ پیدا نشد."
    if not str(source_path).lower().endswith('.db'):
        return False, "فقط فایل .db قابل قبول است."
    # checkpoint فعلی
    try:
        from giso.base import checkpoint_giso_db
        checkpoint_giso_db()
    except Exception:
        pass
    # integrity check
    try:
        import sqlite3
        c = sqlite3.connect(str(source_path))
        row = c.execute('PRAGMA integrity_check').fetchone()
        c.close()
        if not row or str(row[0]).lower() != 'ok':
            return False, "فایل دیتابیس معتبر نیست."
    except Exception as e:
        return False, f"فایل قابل خواندن نیست: {e}"
    backup_dir = _backup_dir()
    os.makedirs(backup_dir, exist_ok=True)
    ts = datetime.now().strftime('%Y%m%d_%H%M%S')
    pre = os.path.join(backup_dir, f"giso_pre_restore_{ts}.db")
    # فایل موقت در همان دایرکتوری DB (لازم برای atomic بودن os.replace روی filesystem یکسان)
    tmp = f"{db_path}.restore-{os.getpid()}.tmp"
    replaced = False
    try:
        if os.path.exists(db_path):
            shutil.copy2(db_path, pre)
        shutil.copy2(str(source_path), tmp)
        os.replace(tmp, db_path)  # اتمیک: یا کامل جایگزین می‌شود یا اصلاً
        replaced = True
    except Exception as e:
        if not replaced and os.path.exists(pre):
            try:
                shutil.copy2(pre, db_path)
            except Exception:
                pass
        return False, f"بازگردانی ناموفق و rollback انجام شد: {e}"
    finally:
        try:
            if os.path.exists(tmp):
                os.remove(tmp)
        except Exception:
            pass
    # پاک‌سازی WAL/SHM قدیمی که به فایل قبلی تعلق دارند (best-effort)
    for suffix in ("-wal", "-shm"):
        try:
            os.remove(f"{db_path}{suffix}")
        except OSError:
            pass
    # checkpoint بعد از restore: انتقال هر WAL تازه به فایل اصلی
    try:
        from giso.base import checkpoint_giso_db
        checkpoint_giso_db()
    except Exception:
        pass
    return True, f"بازگردانی انجام شد. نسخه امن قبلی: {os.path.basename(pre)}"



def _get_backup_interval_hours():
    """خواندن تنظیم backup خودکار از giso_config (۰ = غیرفعال)."""
    try:
        from giso.base import get_giso_db_conn
        conn = get_giso_db_conn()
        try:
            row = conn.execute(
                "SELECT value FROM giso_config WHERE key='backup_interval_hours'"
            ).fetchone()
        finally:
            conn.close()
        if row and row[0]:
            return int(row[0])
    except Exception:
        pass
    return 0



def _set_backup_interval_hours(hours):
    """ذخیره تنظیم backup خودکار در giso_config."""
    from giso.base import get_giso_db_conn
    from datetime import datetime
    try:
        conn = get_giso_db_conn()
        try:
            conn.execute(
                "CREATE TABLE IF NOT EXISTS giso_config ("
                "id INTEGER PRIMARY KEY AUTOINCREMENT, "
                "key TEXT UNIQUE NOT NULL, value TEXT DEFAULT '', "
                "updated_at TEXT DEFAULT '')"
            )
            now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            conn.execute(
                "INSERT INTO giso_config (key, value, updated_at) "
                "VALUES ('backup_interval_hours', ?, ?) "
                "ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_at=excluded.updated_at",
                (str(int(hours)), now)
            )
            conn.commit()
        finally:
            conn.close()
        return True
    except Exception as e:
        logger.error(f"_set_backup_interval_hours: {e}")
        return False

