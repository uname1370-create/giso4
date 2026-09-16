# -*- coding: utf-8 -*-
"""Worker پس‌زمینه مرکز پیام: کشیدن صف خارج از چرخه HTTP (Queue/Batch)."""
import threading

from giso.broadcasts_center import core

_thread = None
_lock = threading.Lock()


def _loop(stop_evt):
    while not stop_evt.is_set():
        try:
            n = core.process_batch(5)
        except Exception:
            n = 0
        stop_evt.wait(0.2 if n else 1.5)


def start():
    """شروع idempotent؛ در gunicorn هر worker یک thread دارد."""
    global _thread
    with _lock:
        if _thread is not None and _thread.is_alive():
            return _thread
        stop_evt = threading.Event()
        t = threading.Thread(target=_loop, args=(stop_evt,), daemon=True,
                             name="giso-bc-worker")
        t._bc_stop = stop_evt  # type: ignore[attr-defined]
        t.start()
        _thread = t
        return t


def alive():
    return bool(_thread is not None and _thread.is_alive())


def queue_size():
    return core.queue_size()
