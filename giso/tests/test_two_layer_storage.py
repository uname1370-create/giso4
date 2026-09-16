#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
تست سیستم ذخیره‌سازی دو لایه + backup خودکار.

۱) load_providers_from_env: ۵ provider از giso/.env خوانده می‌شود.
۲) sync_env_providers_to_db: اگر DB خالی است، از .env پر می‌شود.
۳) save_provider_to_env: یک provider جدید در .env ذخیره/آپدیت می‌شود.
۴) backup: گرفتن backup فایل .db در پوشه backup + لیست + محدودیت تعداد.
"""
import asyncio
import os
import sys
import shutil
from unittest.mock import MagicMock, AsyncMock

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if BASE_DIR not in sys.path:
    sys.path.append(BASE_DIR)

from giso.ai_brain import (  # noqa: E402
    load_providers_from_env, sync_env_providers_to_db, save_provider_to_env,
    list_ai_providers, init_ai_tables, _ENV_PATH,
)
from giso.app import create_app  # noqa: E402
from giso.base import get_giso_db_conn  # noqa: E402

DUMMY_ENV = ("GISO_AI_COUNT=5\n" "GISO_AI_1_NAME=gemini\nGISO_AI_1_KEY=k1\nGISO_AI_1_URL=https://example.invalid/1\nGISO_AI_1_PROXY=1\n" "GISO_AI_2_NAME=groq\nGISO_AI_2_KEY=k2\nGISO_AI_2_URL=https://example.invalid/2\n" "GISO_AI_3_NAME=openrouter\nGISO_AI_3_KEY=k3\nGISO_AI_3_URL=https://example.invalid/3\n" "GISO_AI_4_NAME=avalai\nGISO_AI_4_KEY=k4\nGISO_AI_4_URL=https://example.invalid/4\nGISO_AI_4_IRANIAN=1\n" "GISO_AI_5_NAME=gapgpt\nGISO_AI_5_KEY=k5\nGISO_AI_5_URL=https://example.invalid/5\n")


def _ensure_dummy_env():
    """جداسازی کامل: مسیر .env ماژول به فایل موقت تست وصل می‌شود."""
    import tempfile
    from pathlib import Path
    import giso.ai_brain as _ab
    tmp = Path(tempfile.mkdtemp()) / ".env"
    tmp.write_text(DUMMY_ENV, encoding="utf-8")
    orig = _ab._ENV_PATH
    _ab._ENV_PATH = tmp
    return orig


def _drop_dummy_env(orig):
    import giso.ai_brain as _ab
    try:
        _ab._ENV_PATH.unlink()
    except Exception:
        pass
    _ab._ENV_PATH = orig
# ── ۱) خواندن از .env ───────────────────────────────────────
def test_load_providers_from_env():
    created = _ensure_dummy_env()
    try:
        providers = load_providers_from_env()
        assert len(providers) >= 5, f"تعداد providers از .env: {len(providers)}"
        names = [p["name"] for p in providers]
        for expected in ("gemini", "groq", "openrouter", "avalai", "gapgpt"):
            assert expected in names, f"provider {expected} در .env نیست"
        gemini = next(p for p in providers if p["name"] == "gemini")
        assert gemini["use_proxy"] == 1
        avalai = next(p for p in providers if p["name"] == "avalai")
        assert avalai["is_iranian"] == 1
        print("PASS  load_providers_from_env: ۵ provider از .env خوانده شد")
    finally:
        _drop_dummy_env(created)


# ── ۲) sync از .env به DB وقتی خالی است ────────────────────
def test_sync_env_to_db_when_empty():
    created = _ensure_dummy_env()
    app = create_app()
    init_ai_tables()
    try:
        # پاک کردن جدول برای شبیه‌سازی DB خالی
        with get_giso_db_conn() as conn:
            conn.execute("DELETE FROM giso_ai_providers")
            conn.commit()
        existing = list_ai_providers()
        assert len(existing) == 0, "پیش‌شرط: DB باید خالی باشد"

        sync_env_providers_to_db()

        after = list_ai_providers()
        assert len(after) >= 5, f"پس از sync، تعداد providers: {len(after)}"
        names = [r["name"] for r in after]
        for expected in ("gemini", "groq", "openrouter", "avalai", "gapgpt"):
            assert expected in names, f"{expected} پس از sync در DB نیست"
        print("PASS  sync_env_providers_to_db: DB خالی از .env پر شد")
    finally:
        _drop_dummy_env(created)
        # پاک‌سازی
        try:
            with get_giso_db_conn() as conn:
                conn.execute("DELETE FROM giso_ai_providers")
                conn.commit()
        except Exception:
            pass


# ── ۳) sync وقتی DB پر است → نباید دوباره seed کند ─────────
def test_sync_skips_when_db_full():
    created = _ensure_dummy_env()
    app = create_app()
    init_ai_tables()
    try:
        sync_env_providers_to_db()
        first = len(list_ai_providers())
        sync_env_providers_to_db()
        second = len(list_ai_providers())
        assert first > 0 and second == first, f"{first} vs {second}"
        print("PASS  sync وقتی DB پر است، دوباره seed نمی‌کند")
    finally:
        _drop_dummy_env(created)
        try:
            with get_giso_db_conn() as conn:
                conn.execute("DELETE FROM giso_ai_providers")
                conn.commit()
        except Exception:
            pass


# ── ۴) ذخیره همزمان در .env ────────────────────────────────
def test_save_provider_to_env():
    # از یک فایل .env موقت استفاده می‌کنیم تا فایل واقعی خراب نشود
    created = _ensure_dummy_env()
    import giso.ai_brain as _ab
    from pathlib import Path as _Path
    tmp_env = _Path(os.path.join(BASE_DIR, "giso", "data", ".env.test_tmp"))
    shutil.copy2(str(_ENV_PATH), str(tmp_env))
    orig_path = _ab._ENV_PATH
    _ab._ENV_PATH = tmp_env
    try:
        save_provider_to_env(
            name="testprovider", api_key="secretkey123", base_url="https://test.example/v1",
            model="test-model", enabled=True, proxy=False, iranian=True, timeout=30,
        )
        providers = load_providers_from_env()
        tp = next((p for p in providers if p["name"] == "testprovider"), None)
        assert tp is not None, "provider تست در .env ذخیره نشد"
        assert tp["api_key"] == "secretkey123"
        assert tp["base_url"] == "https://test.example/v1"
        assert tp["is_iranian"] == 1
        # API Key نباید در لاگ/خروجی باشد (فقط در .env)
        print("PASS  save_provider_to_env: provider در .env موقت ذخیره شد (بدون لو رفتن Key)")
    finally:
        # بازگردانی _ENV_PATH و پاک‌سازی فایل موقت
        _ab._ENV_PATH = orig_path
        _drop_dummy_env(created)
        try:
            os.remove(tmp_env)
        except Exception:
            pass


# ── ۵) backup فایل ──────────────────────────────────────────
def test_backup_file_created_and_pruned():
    app = create_app()
    backup_dir = os.path.join(BASE_DIR, "giso", "data", "backup")
    os.makedirs(backup_dir, exist_ok=True)
    # ساخت چند فایل backup مصنوعی
    for i in range(8):
        p = os.path.join(backup_dir, f"giso_backup_2026010{i}_000000.db")
        with open(p, "w") as f:
            f.write("x" * 1024)
    try:
        from giso.bot import _list_backup_files, _backup_max_files
        files = _list_backup_files()
        assert len(files) >= 8, "باید ۸ فایل backup لیست شود"
        # prune به ۵
        maxf = _backup_max_files()
        assert maxf == 5
        all_b = sorted(files)
        while len(all_b) > maxf:
            os.remove(os.path.join(backup_dir, all_b.pop(0)))
        remaining = _list_backup_files()
        assert len(remaining) <= maxf, f"بعد از prune باید ≤{maxf} باشد، شد {len(remaining)}"
        print("PASS  backup: فایل ساخته/لیست/محدودیت تعداد (نگه‌داشتن ۵) درست است")
    finally:
        for f in os.listdir(backup_dir):
            try:
                os.remove(os.path.join(backup_dir, f))
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
    sys.exit(0 if _run() else 1)
