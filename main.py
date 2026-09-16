# -*- coding: utf-8 -*-
"""
main.py — Central launcher for sadeghiai.

Runs four services as independent subprocesses:
  1) bot_edu/bot.py   — always (Bale + Telegram)
  2) web/app.py       — always (port 5000)
  3) giso/app.py      — always (port 5001)
  4) giso/bot.py      — only when GISO_BOT_TOKEN is set OR when
                        bot_token appears in giso_config (bot.db).
                        The watcher checks every 10s and starts/stops
                        the giso bot as needed.

All services run in their own working directory to avoid import-name
conflicts (e.g. bot.py existing in both bot_edu/ and giso/).
"""
import os
import sys
import time
import sqlite3
import signal
import logging
import subprocess
import threading
from pathlib import Path

# وقتی stdout/stderr به فایل یا سرویس هدایت می‌شود (نه کنسول)، ویندوز روی
# cp1252 می‌افتد و پرینت‌های یونیکد («═»، ایموجی‌ها) با UnicodeEncodeError
# کل لانچر را می‌کُشند. خروجی را به UTF-8 با جایگزینی امن کاراکتر تنظیم می‌کنیم.
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")  # Python 3.7+
    except Exception:
        pass


# ---------------------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent
# لود اولیه env از ریشه پروژه تا همه ساب‌پرسس‌ها از مقادیر درست بهره ببرند
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))
try:
    from env_loader import load_project_env
    load_project_env()
except ImportError:
    pass
PID_FILE = BASE_DIR / "giso" / "data" / "giso-bot.pid"
RESTART_FLAG = BASE_DIR / "giso" / "data" / "giso-restart.flag"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("sadeghiai")

processes = {}
_lock = threading.Lock()
# رویداد توقف سراسری: نگهبان‌ها با این رویداد از حلقه خارج می‌شوند
# (تا هنگام خاموش‌شدن لانچر، سرویس مرده دوباره spawn نشود).
_shutdown = threading.Event()


# ---------------------------------------------------------------------------
# helpers

def _mask(token: str) -> str:
    if not token:
        return ""
    t = str(token).strip()
    return t if len(t) <= 14 else f"{t[:10]}...{t[-6:]}"


def _env():
    """Environment for all subprocesses — includes PYTHONPATH to project root."""
    env = os.environ.copy()
    pp = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = str(BASE_DIR) + (os.pathsep + pp if pp else "")
    # ساب‌پروس‌ها هم خروجی یونیکد دارند؛ با هدایت خروجی به فایل روی cp1252 کرش نمی‌کنند
    env.setdefault("PYTHONIOENCODING", "utf-8")
    return env


def _spawn(label: str, script: Path, cwd: Path, env=None) -> subprocess.Popen:
    """Spawn a subprocess with stdout/stderr forwarded to current console."""
    logger.info("Starting %s ...", label)
    proc = subprocess.Popen(
        [sys.executable, "-u", str(script)],
        cwd=str(cwd),
        env=env or _env(),
        stdout=sys.stdout,
        stderr=sys.stderr,
    )
    with _lock:
        processes[label] = proc
    logger.info("✅ %s started (PID %d)", label, proc.pid)
    return proc


def _terminate(proc: subprocess.Popen, timeout: float = 5.0):
    """Terminate a subprocess gracefully, then force-kill after timeout."""
    if proc is None or proc.poll() is not None:
        return
    try:
        proc.terminate()
    except Exception:
        pass
    try:
        proc.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        try:
            proc.kill()
        except Exception:
            pass
    except Exception:
        pass


def _read_giso_token_from_db() -> str:
    """Read giso bot token directly from bot.db (no imports of bot_edu code)."""
    db_path = BASE_DIR / "bot_edu" / "data" / "bot.db"
    if not db_path.exists():
        return ""
    try:
        conn = sqlite3.connect(str(db_path))
        try:
            # busy_timeout: جلوگیری از «database is locked» هنگام هم‌زمانی با ربات edu
            # (بدون import از giso.base تا وابستگی SECRET_KEY به لانچر اضافه نشود)
            conn.execute("PRAGMA busy_timeout = 5000")
            cur = conn.execute("SELECT value FROM giso_config WHERE key='bot_token'")
            row = cur.fetchone()
        finally:
            conn.close()
        return (row[0] if row else "").strip()
    except Exception as e:
        logger.warning("Could not read giso token from db: %s", e)
        return ""


def _write_pid(pid: int):
    try:
        PID_FILE.parent.mkdir(parents=True, exist_ok=True)
        PID_FILE.write_text(str(pid), encoding="utf-8")
    except Exception as e:
        logger.warning("Could not write PID file: %s", e)


def _clear_pid():
    try:
        if PID_FILE.exists():
            PID_FILE.unlink()
    except Exception:
        pass


def _check_giso_restart_flag():
    """
    چک می‌کند آیا ربات گیسو flag ریستارت گذاشته یا نه.
    اگر بله، flag را پاک می‌کند و True برمی‌گرداند.
    """
    if RESTART_FLAG.exists():
        try:
            RESTART_FLAG.unlink()
            logger.info("🔄 flag ریستارت گیسو پیدا شد — instance جدید spawn می‌شود")
            return True
        except Exception as e:
            logger.warning(f"پاک‌کردن flag ریستارت ناموفق: {e}")
            return True
    return False


# ---------------------------------------------------------------------------
# thread targets

def _watch_and_restart(label: str, script: Path, cwd: Path,
                       check_interval: float = 10.0, env=None, backoff_limit: float = 30.0):
    """
    نگهبان عمومی یک سرویس:
      • سرویس را spawn می‌کند؛
      • هر check_interval ثانیه poll() می‌زند؛
      • اگر سرویس مرده بود، آن را دوباره بالا می‌آورد.
    اگر سرویس پشت‌سرهم کرش کند (کمتر از backoff_limit دوام آورد)، فاصلهٔ
    ری‌استارت به‌تدریج تا ۳۰ ثانیه زیاد می‌شود تا جلوی حلقهٔ کرش-ری‌استارت
    بی‌نهایت گرفته شود. هنگام shutdown سراسری، ری‌استارت نمی‌کند.
    """
    wait = check_interval
    while not _shutdown.is_set():
        proc = None
        started = time.time()
        try:
            proc = _spawn(label, script, cwd, env=env)
        except Exception as e:
            logger.error("%s spawn failed: %s", label, e, exc_info=True)
        if proc is not None:
            # تا زمان خروج سرویس یا دستور توقف، منتظر می‌مانیم
            while not _shutdown.is_set():
                rc = proc.poll()
                if rc is not None:
                    break
                time.sleep(min(2.0, check_interval))
            if _shutdown.is_set():
                break
            uptime = time.time() - started
            logger.warning("سرویس %s خارج شد (code=%s) — عمر: %.0f ثانیه", label, proc.returncode, uptime)
            # کرش زودهنگام (<30s) → فاصلهٔ ری‌استارت را زیاد کن؛ وگرنه به ۱۰ ثانیه برگرد
            wait = min(wait * 2, backoff_limit) if uptime < backoff_limit else check_interval
        else:
            wait = backoff_limit
        # انتظار پیش از ری‌استارت (قابل قطع با shutdown)
        if _shutdown.wait(wait):
            break
        logger.info("♻️  ری‌استارت سرویس %s ...", label)


def _run_bot_edu():
    """نگهبان ربات آموزش — کرش کند، در حداکثر ۱۰–۳۰ ثانیه برمی‌گردد."""
    _watch_and_restart(
        "bot-edu",
        BASE_DIR / "bot_edu" / "bot.py",
        BASE_DIR / "bot_edu",
    )


def _run_web():
    """نگهبان سایت اصلی (پورت 5000) — ری‌استارت خودکار."""
    _watch_and_restart(
        "web-main",
        BASE_DIR / "web" / "app.py",
        BASE_DIR / "web",
    )


def _run_giso_web():
    """نگهبان سایت گیسو (پورت 5001) — ری‌استارت خودکار."""
    _watch_and_restart(
        "giso-web",
        BASE_DIR / "giso" / "app.py",
        BASE_DIR / "giso",
    )


def _giso_bot_watcher():
    """
    Every 10 seconds:
      • read token from bot.db (or env GISO_BOT_TOKEN)
      • if token present and process not running → start it
      • if running process died → restart
      • if token removed → stop the process
    """
    proc = None
    current_token = ""
    while True:
        try:
            # Token priority: env override → db
            token = (os.environ.get("GISO_BOT_TOKEN") or _read_giso_token_from_db() or "").strip()

            # --- case 1: no token → stop if running ---
            if not token:
                if proc is not None and proc.poll() is None:
                    logger.info("Giso token removed — stopping giso-bot.")
                    _terminate(proc)
                    proc = None
                    _clear_pid()
                current_token = ""
            else:
                # --- case 2: token changed → restart ---
                if token != current_token and proc is not None and proc.poll() is None:
                    logger.info("Giso token changed — restarting giso-bot.")
                    _terminate(proc)
                    proc = None
                    _clear_pid()
                # --- case 3: need to (re)start ---
                if proc is None or proc.poll() is not None:
                    # چک flag ریستارت (برای لاگ بهتر؛ همیشه spawn انجام می‌شود)
                    was_restart = _check_giso_restart_flag()
                    if was_restart:
                        logger.info("Spawn giso-bot به دلیل ریستارت درخواست‌شده...")
                    else:
                        logger.info("Spawn giso-bot ...")
                    env = _env()
                    env["GISO_BOT_TOKEN"] = token
                    proc = _spawn(
                        "giso-bot",
                        BASE_DIR / "giso" / "bot.py",
                        BASE_DIR / "giso",
                        env=env,
                    )
                    _write_pid(proc.pid)
                    current_token = token
        except Exception as e:
            logger.error("giso-bot watcher error: %s", e, exc_info=True)

        # انتظار ۱۰ ثانیه‌ایِ قابل‌قطع: هنگام shutdown، watcher فوراً خارج می‌شود
        if _shutdown.wait(10):
            break


# ---------------------------------------------------------------------------
def _stop_all():
    logger.info("Stopping all services...")
    _shutdown.set()  # به همهٔ نگهبان‌ها بگو ری‌استارت نکنند و خارج شوند
    with _lock:
        procs = list(processes.values())
    for p in procs:
        _terminate(p)
    _clear_pid()
    logger.info("✅ All services stopped.")


def _install_signal_handlers():
    def _sig(sig, frame):
        _stop_all()
        sys.exit(0)
    signal.signal(signal.SIGINT, _sig)
    signal.signal(signal.SIGTERM, _sig)


def main():
    print()
    print("═" * 60)
    print("  🚀 sadeghiai system launcher")
    print("═" * 60)

    _install_signal_handlers()
    _clear_pid()
    # پاک‌سازی flag ریستارت قدیمی (اگر از یک ریستارت ناتمام باقی مانده باشد)
    try:
        if RESTART_FLAG.exists():
            RESTART_FLAG.unlink()
            logger.info("flag ریستارت قدیمی پاک شد")
    except Exception:
        pass

    threads = [
        threading.Thread(target=_run_bot_edu,  name="bot-edu",   daemon=True),
        threading.Thread(target=_run_web,       name="web-main", daemon=True),
        threading.Thread(target=_run_giso_web,  name="giso-web", daemon=True),
        threading.Thread(target=_giso_bot_watcher, name="giso-bot-watcher", daemon=True),
    ]
    for t in threads:
        t.start()
        time.sleep(1.5)

    print("═" * 60)
    print("  🌐 Main website:   http://127.0.0.1:5000")
    print("  🎀 Giso website:   http://127.0.0.1:5001")
    print("  🤖 Bot-edu:        Bale bot (always)")
    print("  💇‍♀️ Giso bot:       Activate via admin panel → auto-starts")
    print("═" * 60)
    print("  Press Ctrl+C to stop everything")
    print()

    try:
        while True:
            time.sleep(2)
    except KeyboardInterrupt:
        pass
    finally:
        _stop_all()


if __name__ == "__main__":
    main()
