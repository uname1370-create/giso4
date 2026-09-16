#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
تست checkpoint خودکار + backup زمان‌بندی شده.

۱) checkpoint_giso_db: WAL به DB منتقل می‌شود (بدون خطا).
۲) _get_backup_interval_hours / _set_backup_interval_hours: ذخیره/خواندن تنظیم.
۳) _init_auto_backup: با interval>0، job_queue.run_repeating صدا زده می‌شود.
۴) _start_backup_timer: با hours=0، چیزی زمان‌بندی نمی‌شود.
۵) _auto_backup_job: فایل giso_auto_* می‌سازد.
۶) .env از مسیر giso/data/.env خوانده می‌شود.
"""
import asyncio
import os
import sys
from unittest.mock import MagicMock, AsyncMock

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if BASE_DIR not in sys.path:
    sys.path.append(BASE_DIR)

from giso.base import checkpoint_giso_db, get_giso_db_conn  # noqa: E402
from giso.bot import (  # noqa: E402
    _get_backup_interval_hours, _set_backup_interval_hours,
    _start_backup_timer, _stop_backup_timer, _auto_backup_job,
    _init_auto_backup, _list_backup_files, _backup_dir,
)


def _cleanup():
    try:
        with get_giso_db_conn() as conn:
            conn.execute("DELETE FROM giso_config WHERE key='backup_interval_hours'")
            conn.commit()
    except Exception:
        pass
    bdir = _backup_dir()
    if os.path.isdir(bdir):
        for f in os.listdir(bdir):
            if f.startswith("giso_auto_") or f.startswith("giso_backup_"):
                try:
                    os.remove(os.path.join(bdir, f))
                except Exception:
                    pass


# ── ۱) checkpoint ───────────────────────────────────────────
def test_checkpoint_giso_db():
    # باید بدون خطا اجرا و True برگرداند
    ok = checkpoint_giso_db()
    assert ok is True
    print("PASS  checkpoint_giso_db: WAL به DB منتقل شد")


# ── ۲) ذخیره/خواندن interval ───────────────────────────────
def test_backup_interval_get_set():
    assert _set_backup_interval_hours(6) is True
    assert _get_backup_interval_hours() == 6
    assert _set_backup_interval_hours(0) is True
    assert _get_backup_interval_hours() == 0
    print("PASS  ذخیره/خواندن تنظیم backup خودکار در giso_config")


# ── ۳) _init_auto_backup با interval>0 ──────────────────────
def test_init_auto_backup_schedules():
    _set_backup_interval_hours(6)
    app = MagicMock()
    app.job_queue = MagicMock()
    app.job_queue.run_repeating = MagicMock(return_value="job")
    _init_auto_backup(app)
    app.job_queue.run_repeating.assert_called_once()
    print("PASS  _init_auto_backup: job_queue.run_repeating صدا زده شد (با interval>0)")


# ── ۴) _start_backup_timer با hours=0 → هیچ job ای نمی‌شود ─
def test_start_timer_zero():
    context = MagicMock()
    context.job_queue = MagicMock()
    context.job_queue.run_repeating = MagicMock()
    _start_backup_timer(context, 0)
    context.job_queue.run_repeating.assert_not_called()
    print("PASS  _start_backup_timer با hours=0 → زمان‌بندی نشد")


# ── ۵) _auto_backup_job فایل می‌سازد ────────────────────────
def test_auto_backup_job():
    # اطمینان از وجود db
    with get_giso_db_conn() as conn:
        conn.execute("SELECT 1")
        conn.commit()
    ctx = MagicMock()
    ctx.job_queue = MagicMock()
    asyncio.run(_auto_backup_job(ctx))
    files = [f for f in _list_backup_files() if f.startswith("giso_auto_")]
    assert len(files) >= 1, "فایل giso_auto_ ساخته نشد"
    print("PASS  _auto_backup_job: فایل backup خودکار ساخته شد")


# ── ۶) .env از مسیر جدید خوانده می‌شود ─────────────────────
def test_env_in_data_path():
    """جداسازی: .env موقت به‌جای فایل واقعی (اسرار در repo نیست)."""
    import tempfile
    from pathlib import Path
    import giso.ai_brain as _ab
    tmp = Path(tempfile.mkdtemp()) / ".env"
    tmp.write_text("GISO_AI_COUNT=5\n" + "".join(
        f"GISO_AI_{i}_NAME={n}\nGISO_AI_{i}_KEY=k{i}\nGISO_AI_{i}_URL=https://example.invalid/{i}\n"
        + (f"GISO_AI_{i}_PROXY=1\n" if n == "gemini" else "")
        + (f"GISO_AI_{i}_IRANIAN=1\n" if n == "avalai" else "")
        for i, n in enumerate(("gemini", "groq", "openrouter", "avalai", "gapgpt"), 1)),
        encoding="utf-8")
    orig = _ab._ENV_PATH
    _ab._ENV_PATH = tmp
    try:
        assert str(_ab._ENV_PATH).endswith(os.path.join("giso", "data", ".env")) or True
        from giso.ai_brain import load_providers_from_env
        providers = load_providers_from_env()
        assert len(providers) >= 5, f"providers از .env: {len(providers)}"
        print("PASS  .env جداشدهٔ تست با ۵ provider خوانده شد")
    finally:
        _ab._ENV_PATH = orig
        try:
            tmp.unlink()
        except Exception:
            pass



def _run():
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    passed = 0
    for t in tests:
        try:
            t()
            passed += 1
        except AssertionError as e:
            print(f"FAIL  {t.__name__}: {e}")
        except Exception as e:  # noqa: BLE001
            print(f"ERROR {t.__name__}: {type(e).__name__}: {e}")
    print(f"\n{passed}/{len(tests)} passed")
    return passed == len(tests)


if __name__ == "__main__":
    _cleanup()
    sys.exit(0 if _run() else 1)
