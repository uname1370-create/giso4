# -*- coding: utf-8 -*-
"""Nightly empty-description fill + weekly Bale SEO report.

Scheduling lives in a daemon thread started from create_app (giso-web).
No systemd timer, no bot.py job_queue, no site_jobs before_request.

CLI ``python -u giso/seo_jobs.py`` remains a one-shot (flock-protected).
"""
from __future__ import annotations

import asyncio
import fcntl
import json
import logging
import os
import sys
import threading
import time
from datetime import datetime, timedelta
from pathlib import Path

logger = logging.getLogger("giso_seo_jobs")

NIGHTLY_CAP = 20
PREFERRED_PROVIDER = "gemini"
FAILOVER_PROVIDER = "groq"
NIGHTLY_HOUR = 3
_SCHEDULER_LOCK = threading.Lock()
_scheduler_started = False


def _data_dir() -> Path:
    try:
        from giso.config import Config
        return Path(Config.GISO_DIR) / "data"
    except Exception:
        return Path(__file__).resolve().parent / "data"


def lock_path() -> Path:
    return _data_dir() / "seo_jobs.lock"


def state_path() -> Path:
    return _data_dir() / "seo_job_state.json"


def load_state() -> dict:
    path = state_path()
    try:
        if path.is_file():
            data = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                return data
    except Exception:
        pass
    return {
        "filled_total": 0,
        "rejected_total": 0,
        "filled_week": 0,
        "rejected_week": 0,
        "last_meta_run": "",
        "last_weekly_report": "",
    }


def save_state(state: dict) -> None:
    path = state_path()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(path)
    except Exception as exc:
        logger.debug("save_state: %s", exc)


def weekly_report_due(state: dict, now: datetime | None = None) -> bool:
    now = now or datetime.now()
    last = str(state.get("last_weekly_report") or "").strip()
    if not last:
        return True
    try:
        last_dt = datetime.strptime(last[:10], "%Y-%m-%d")
    except (TypeError, ValueError):
        return True
    return (now.date() - last_dt.date()) >= timedelta(days=7)


async def _ask_meta_text(name: str, category: str) -> str:
    from giso.ai_runtime import chat_with_failover
    from giso.seo_meta import build_meta_prompt

    prompt = build_meta_prompt(name, category)
    messages = [
        {"role": "system", "content": "فقط همان توضیح محصول را برگردان. هیچ عنوان یا توضیح اضافه ننویس."},
        {"role": "user", "content": prompt},
    ]
    result = await chat_with_failover(
        messages,
        preferred_provider=PREFERRED_PROVIDER,
        temperature=0.3,
        max_tokens=120,
        role="user",
    )
    if result and result.get("ok"):
        return str(result.get("text") or "")
    # Explicit groq retry if the chain did not already try it.
    if FAILOVER_PROVIDER and (result or {}).get("provider") != FAILOVER_PROVIDER:
        result = await chat_with_failover(
            messages,
            preferred_provider=FAILOVER_PROVIDER,
            temperature=0.3,
            max_tokens=120,
            role="user",
        )
        if result and result.get("ok"):
            return str(result.get("text") or "")
    return ""


async def fill_empty_descriptions(limit: int = NIGHTLY_CAP) -> dict:
    from giso.base import get_giso_db_conn
    from giso.seo_meta import list_fill_candidates, write_description_if_empty, validate_description

    filled = 0
    rejected = 0
    try:
        with get_giso_db_conn() as conn:
            candidates = list_fill_candidates(conn, limit=limit)
            for row in candidates:
                try:
                    raw = await _ask_meta_text(str(row.get("name") or ""), str(row.get("category") or ""))
                    ok, _cleaned = validate_description(raw)
                    if not ok:
                        rejected += 1
                        continue
                    if write_description_if_empty(conn, int(row["id"]), raw):
                        filled += 1
                    else:
                        rejected += 1
                except Exception:
                    rejected += 1
            try:
                conn.commit()
            except Exception:
                pass
    except Exception as exc:
        logger.debug("fill_empty_descriptions: %s", exc)
    return {"filled": filled, "rejected": rejected}


def _send_bale_text(text: str) -> bool:
    try:
        from giso.base import _http_post, _token_from_env, _token_from_db
        from giso.panel.modules.notifications import _super_admin_ids
    except Exception:
        return False
    token = _token_from_env() or _token_from_db() or ""
    if not token:
        return False
    try:
        targets = sorted(_super_admin_ids() or set())
    except Exception:
        targets = []
    if not targets:
        return False
    ok_any = False
    for cid in targets:
        try:
            _http_post(
                f"https://tapi.bale.ai/bot{token}/sendMessage",
                json_payload={"chat_id": int(cid), "text": text},
            )
            ok_any = True
        except Exception:
            pass
    return ok_any


def build_weekly_report(state: dict) -> str:
    from giso.seo_sitemap import sitemap_cache_status
    status = sitemap_cache_status()
    if status.get("exists"):
        age = int(status.get("age_seconds") or 0)
        sitemap_line = f"کش sitemap موجود است (سن {age} ثانیه)."
    else:
        sitemap_line = "کش sitemap روی دیسک نیست (TTL یا هنوز ساخته نشده)."
    return (
        "📊 گزارش هفتگی سئو گیسو\n"
        "━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"✅ توضیح پرشده این هفته: {int(state.get('filled_week') or 0)}\n"
        f"⏭ ردشده این هفته: {int(state.get('rejected_week') or 0)}\n"
        f"Σ پرشده کل: {int(state.get('filled_total') or 0)}\n"
        f"🗺 {sitemap_line}\n"
        "بدون پینگ گوگل — فقط وضعیت داخلی."
    )


def send_weekly_report(state: dict) -> bool:
    text = build_weekly_report(state)
    return _send_bale_text(text)


def seconds_until_nightly(now: datetime | None = None, hour: int = NIGHTLY_HOUR) -> int:
    now = now or datetime.now()
    target = now.replace(hour=int(hour), minute=0, second=0, microsecond=0)
    if now >= target:
        target = target + timedelta(days=1)
    return max(1, int((target - now).total_seconds()))


def scheduler_enabled() -> bool:
    flag = (os.environ.get("GISO_SEO_SCHEDULER") or "").strip().lower()
    if flag in ("0", "false", "off", "no"):
        return False
    if flag in ("1", "true", "on", "yes"):
        return True
    return (os.environ.get("FLASK_ENV") or "").strip().lower() == "production"


def _scheduler_loop() -> None:
    logger.info("seo scheduler loop started; nightly window %02d:00", NIGHTLY_HOUR)
    while True:
        try:
            delay = seconds_until_nightly()
            logger.info("seo scheduler sleeping %ss until nightly window", delay)
            remaining = delay
            while remaining > 0:
                chunk = min(300, remaining)
                time.sleep(chunk)
                remaining -= chunk
            logger.info("seo scheduler firing nightly jobs")
            main()
        except Exception as exc:
            logger.warning("seo scheduler loop: %s", exc)
            time.sleep(60)


def start_seo_scheduler() -> bool:
    """Idempotent daemon thread. Safe to call on every create_app."""
    global _scheduler_started
    if not scheduler_enabled():
        logger.info("seo scheduler off (set GISO_SEO_SCHEDULER=1 or FLASK_ENV=production)")
        return False
    with _SCHEDULER_LOCK:
        if _scheduler_started:
            logger.info("seo scheduler already running")
            return True
        thread = threading.Thread(
            target=_scheduler_loop,
            name="giso-seo-scheduler",
            daemon=True,
        )
        thread.start()
        _scheduler_started = True
        logger.info("seo scheduler thread started")
        return True


def run_jobs(now: datetime | None = None) -> dict:
    now = now or datetime.now()
    state = load_state()
    result = {"filled": 0, "rejected": 0, "weekly_sent": False}
    try:
        meta = asyncio.run(fill_empty_descriptions(limit=NIGHTLY_CAP))
        result["filled"] = int(meta.get("filled") or 0)
        result["rejected"] = int(meta.get("rejected") or 0)
        state["filled_week"] = int(state.get("filled_week") or 0) + result["filled"]
        state["rejected_week"] = int(state.get("rejected_week") or 0) + result["rejected"]
        state["filled_total"] = int(state.get("filled_total") or 0) + result["filled"]
        state["rejected_total"] = int(state.get("rejected_total") or 0) + result["rejected"]
        state["last_meta_run"] = now.strftime("%Y-%m-%d %H:%M:%S")
    except Exception as exc:
        logger.debug("run_jobs meta: %s", exc)
    if weekly_report_due(state, now=now):
        try:
            if send_weekly_report(state):
                result["weekly_sent"] = True
                state["last_weekly_report"] = now.strftime("%Y-%m-%d")
                state["filled_week"] = 0
                state["rejected_week"] = 0
        except Exception as exc:
            logger.debug("run_jobs weekly: %s", exc)
    save_state(state)
    return result


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    path = lock_path()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        handle = open(path, "a+", encoding="utf-8")
    except Exception:
        return 0
    try:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        handle.close()
        return 0
    try:
        run_jobs()
    except Exception as exc:
        logger.debug("seo_jobs main: %s", exc)
    finally:
        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
        except Exception:
            pass
        handle.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
