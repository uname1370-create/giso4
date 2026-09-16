# -*- coding: utf-8 -*-
"""Disk cache for the final /sitemap.xml payload (shop + marketplace append)."""
from __future__ import annotations

import logging
import os
import time
from pathlib import Path

logger = logging.getLogger("giso_seo_sitemap")

TTL_SECONDS = 3 * 3600  # 3 hours, inside the 1–6 hour window


def _data_dir() -> Path:
    try:
        from giso.config import Config
        return Path(Config.GISO_DIR) / "data"
    except Exception:
        return Path(__file__).resolve().parent / "data"


def cache_path() -> Path:
    override = (os.environ.get("GISO_SITEMAP_CACHE_PATH") or "").strip()
    if override:
        return Path(override)
    return _data_dir() / "sitemap.xml.cache"


def cache_ttl_seconds() -> int:
    raw = (os.environ.get("GISO_SITEMAP_TTL") or "").strip()
    if raw:
        try:
            return max(0, int(raw))
        except (TypeError, ValueError):
            pass
    return TTL_SECONDS


def sitemap_cache_enabled() -> bool:
    """Production-only by default so local tests never serve a stale file."""
    flag = (os.environ.get("GISO_SITEMAP_CACHE") or "").strip().lower()
    if flag in ("0", "false", "off", "no"):
        return False
    if flag in ("1", "true", "on", "yes"):
        return True
    return (os.environ.get("FLASK_ENV") or "").strip().lower() == "production"


def read_sitemap_cache() -> str | None:
    if not sitemap_cache_enabled():
        return None
    path = cache_path()
    try:
        if not path.is_file():
            return None
        age = time.time() - path.stat().st_mtime
        if age > cache_ttl_seconds():
            return None
        text = path.read_text(encoding="utf-8")
        if "<urlset" not in text:
            return None
        return text
    except Exception as exc:
        logger.debug("read_sitemap_cache: %s", exc)
        return None


def write_sitemap_cache(xml: str) -> None:
    if not sitemap_cache_enabled():
        return
    text = str(xml or "")
    if "<urlset" not in text:
        return
    path = cache_path()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(path.suffix + ".tmp")
        tmp.write_text(text, encoding="utf-8")
        tmp.replace(path)
    except Exception as exc:
        logger.debug("write_sitemap_cache: %s", exc)


def invalidate_sitemap_cache() -> None:
    """Optional helper. Forgetting to call it does not break the site (TTL covers it)."""
    path = cache_path()
    try:
        if path.is_file():
            path.unlink()
    except Exception:
        pass


def sitemap_cache_status() -> dict:
    path = cache_path()
    try:
        if not path.is_file():
            return {"exists": False, "age_seconds": None, "path": str(path)}
        age = int(max(0, time.time() - path.stat().st_mtime))
        return {"exists": True, "age_seconds": age, "path": str(path), "bytes": path.stat().st_size}
    except Exception:
        return {"exists": False, "age_seconds": None, "path": str(path)}
