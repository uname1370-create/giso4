# -*- coding: utf-8 -*-
"""Empty product description filler for SEO meta (validator + skip rules)."""
from __future__ import annotations

import html
import logging
import re
from datetime import datetime

logger = logging.getLogger("giso_seo_meta")

DESC_MIN = 150
DESC_MAX = 160
NIGHTLY_CAP = 20
BANNED_PHRASES = (
    "بهترین",
    "100%",
    "100 ٪",
    "۱۰۰٪",
    "۱۰۰ درصد",
    "درمان قطعی",
    "معالجه",
    "شفا",
    "تشخیص پزشکی",
    "داروی",
    "تجویز",
)
CLAIM_RE = re.compile(
    r"(درمان|معالجه|شفا|تشخیص\s*پزشک|بهترین|۱۰۰\s*%|100\s*%|۱۰۰\s*٪)",
    re.IGNORECASE,
)
TAG_RE = re.compile(r"<[^>]+>")
MD_RE = re.compile(r"[*_`#\[\]>]{1,}")


def _price_missing_note() -> str:
    try:
        from giso.channel_importer import PRICE_MISSING_NOTE
        return str(PRICE_MISSING_NOTE or "")
    except Exception:
        return "قیمت به‌صورت خودکار تشخیص داده نشد"


def sanitize_description(text: str) -> str:
    raw = html.unescape(str(text or ""))
    raw = TAG_RE.sub(" ", raw)
    raw = MD_RE.sub(" ", raw)
    raw = raw.replace("\n", " ").replace("\r", " ").replace("\t", " ")
    raw = re.sub(r"\s+", " ", raw).strip()
    return raw


def validate_description(text: str) -> tuple[bool, str]:
    cleaned = sanitize_description(text)
    if not cleaned:
        return False, "empty"
    if len(cleaned) < DESC_MIN or len(cleaned) > DESC_MAX:
        return False, "length"
    low = cleaned.lower()
    for needle in BANNED_PHRASES:
        if needle.lower() in low or needle in cleaned:
            return False, "banned"
    if CLAIM_RE.search(cleaned):
        return False, "claim"
    return True, cleaned


def _today_prefix(now: datetime | None = None) -> str:
    return (now or datetime.now()).strftime("%Y-%m-%d")


def should_skip_product(row: dict, now: datetime | None = None) -> str:
    """Return skip reason or empty string if the row may be filled."""
    description = str(row.get("description") or "").strip()
    if description:
        return "not_empty"
    status = str(row.get("publish_status") or "published").strip() or "published"
    if status != "published":
        return "not_published"
    source = str(row.get("source") or "site").strip() or "site"
    if source == "channel":
        return "channel"
    note = _price_missing_note()
    blob = str(row.get("description") or "") + str(row.get("short_description") or "")
    if note and note in blob:
        return "price_note"
    updated = str(row.get("updated_at") or "").strip()
    today = _today_prefix(now)
    if updated.startswith(today):
        return "admin_today"
    return ""


def list_fill_candidates(conn, limit: int = NIGHTLY_CAP, now: datetime | None = None) -> list[dict]:
    limit = max(1, min(int(limit or NIGHTLY_CAP), NIGHTLY_CAP))
    try:
        rows = conn.execute(
            "SELECT id, name, category, description, short_description, source, "
            "publish_status, updated_at FROM products "
            "WHERE TRIM(COALESCE(description, '')) = '' "
            "ORDER BY id ASC LIMIT ?",
            (limit * 4,),
        ).fetchall()
    except Exception as exc:
        logger.debug("list_fill_candidates: %s", exc)
        return []
    out = []
    for raw in rows:
        row = dict(raw)
        if should_skip_product(row, now=now):
            continue
        out.append(row)
        if len(out) >= limit:
            break
    return out


def write_description_if_empty(conn, product_id: int, text: str) -> bool:
    ok, cleaned = validate_description(text)
    if not ok:
        return False
    try:
        cur = conn.execute(
            "UPDATE products SET description=? WHERE id=? AND TRIM(COALESCE(description,''))=''",
            (cleaned, int(product_id)),
        )
        return int(cur.rowcount or 0) == 1
    except Exception as exc:
        logger.debug("write_description_if_empty: %s", exc)
        return False


def build_meta_prompt(name: str, category: str = "") -> str:
    cat = (category or "").strip() or "مراقبت مو و پوست"
    return (
        f"یک توضیح محصول فارسی برای فروشگاه گیسو بنویس. نام محصول: {name}. دسته: {cat}. "
        f"فقط متن ساده، {DESC_MIN} تا {DESC_MAX} حرف، بدون تگ HTML، بدون markdown، "
        "بدون ادعای درمانی، بدون واژه بهترین یا ۱۰۰٪. پرداخت در محل مشهد را می‌توانی ذکر کنی."
    )
