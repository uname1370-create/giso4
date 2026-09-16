# -*- coding: utf-8 -*-
"""
تست مکانیزم flag ریستارت گیسو (واگذاری ریستارت به main.py watcher).

پوشش:
۱) ساخت flag (timestamp)
۲) _check_giso_restart_flag: بدون flag → False؛ با flag → True + پاک‌شدن flag
۳) set کردن چندباره flag بدون مشکل
۴) _restart_giso_process فقط flag می‌سازد (نه os.execv) — بررسی منبع
"""
import os
import sys
import time
import tempfile
from pathlib import Path

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)


def _clean_flag(flag: Path):
    try:
        if flag.exists():
            flag.unlink()
    except Exception:
        pass


def test_flag_creation():
    """flag درست ساخته می‌شود (محتوا timestamp است)."""
    tmp = Path(tempfile.gettempdir()) / "test_giso_restart.flag"
    _clean_flag(tmp)
    tmp.parent.mkdir(parents=True, exist_ok=True)
    tmp.write_text(str(int(time.time())))
    try:
        assert tmp.exists(), "flag ساخته نشد"
        content = tmp.read_text()
        assert content.isdigit(), f"محتوای flag باید timestamp باشد: {content}"
        print("PASS  flag creation")
    finally:
        _clean_flag(tmp)


def test_flag_reader():
    """_check_giso_restart_flag درست کار می‌کند."""
    import main as main_module
    flag = Path(BASE_DIR) / "giso" / "data" / "giso-restart.flag"
    _clean_flag(flag)
    try:
        # حالت ۱: بدون flag → False
        assert main_module._check_giso_restart_flag() is False
        # حالت ۲: با flag → True و flag پاک می‌شود
        flag.parent.mkdir(parents=True, exist_ok=True)
        flag.write_text(str(int(time.time())))
        assert main_module._check_giso_restart_flag() is True
        assert not flag.exists(), "flag باید بعد از خواندن پاک شود"
        print("PASS  flag reader")
    finally:
        _clean_flag(flag)


def test_no_duplicate_flag():
    """چند بار set کردن flag، مشکل ایجاد نمی‌کند."""
    flag = Path(tempfile.gettempdir()) / "test_multi_flag.flag"
    _clean_flag(flag)
    for i in range(3):
        flag.parent.mkdir(parents=True, exist_ok=True)
        flag.write_text(str(int(time.time()) + i))
    assert flag.exists()
    _clean_flag(flag)
    print("PASS  multi-set flag")


def test_restart_uses_flag_not_execv():
    """_restart_giso_process دیگر از os.execv استفاده نمی‌کند و flag می‌سازد."""
    src = open(os.path.join(BASE_DIR, "giso", "bot.py"), encoding="utf-8").read()
    # کد فعالِ os.execv قدیمی (با آرگومان‌های اجرای ربات) نباید وجود داشته باشد
    assert "os.execv(sys.executable" not in src, "کد os.execv قدیمی هنوز در فایل است"
    # واگذاری به watcher
    assert "os._exit(0)" in src, "باید با os._exit(0) خاموش شود"
    assert "_GISO_RESTART_FLAG" in src
    assert "giso-restart.flag" in src
    print("PASS  restart uses flag (no os.execv)")


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
