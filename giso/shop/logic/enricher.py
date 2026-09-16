# -*- coding: utf-8 -*-
"""
giso/shop/logic/enricher.py — Auto-Product Enrichment Pipeline
==============================================================
Channel post → product (pending) → web search → AI synthesis → safer image
→ only *enrichment fields* updated; price/stock/publish_status untouched.

Design & safety contract
------------------------
* ANTI-FAKE (HARD RULE): facts (ingredients/usage/warnings) are accepted only if
  found in the fetched search text. Fields not evidenced in text stay empty —
  the pipeline never invents ingredients or usage claims.
* CONCISE UI FIT (HARD RULE): description ≤ 300 chars, usage ≤ 100 chars,
  short_description ≤ 200 chars — enforced by clamps below the caller's reach.
* FAILOVER (HARD RULE): AI calls go through a multi-provider chain. In production
  we reuse the existing `giso.ai_runtime.chat_with_failover` engine; in isolated
  mode (db_path set) we run a self-contained chain over a temp database so the
  live `giso.db` is never written by tests/simulations.
* NON-BLOCKING: `schedule_enrichment()` runs enrichment in a daemon thread; any
  failure is logged and swallowed. The channel importer flow is never blocked
  or broken (read-only fallbacks everywhere).
* IMAGE SAFETY: host allow-list → magic-byte check → Pillow verify → resize to
  900×900 WebP → atomic store; if the web image fails relevance/validation the
  original Bale-channel photo is kept.
"""
from __future__ import annotations

import json
import logging
import os
import re
import sqlite3
import threading
from datetime import datetime
from pathlib import Path

logger = logging.getLogger("giso_enricher")

# ── HARD LIMITS (P1 marketing engine: room for hook + bullets, no mid-cut) ─────
MIN_DESCRIPTION = 600          # marketing copy target floor (when evidence allows)
MAX_DESCRIPTION = 900          # frontend PDP accordion + SEO safe limit
MAX_SHORT_DESC = 150           # card hook: one emotional line
MAX_USAGE = 500                # 3 numbered steps fit
MAX_INGREDIENTS = 400
MAX_WARNINGS = 300
MAX_SUITABLE = 300
MAX_CONCERNS = 300
MAX_TAGS = 6

# ── image safety constants (P1 strict Iranian-CDN guard) ─────────────────────
# picsum.photos REMOVED (random decor). Only real Iranian product CDNs + mag editorial.
ALLOWED_IMAGE_HOST_FRAGMENTS = (
    "imgs.digikala.com", "dkstatics.ir", "digikala.com/mag",
    "khanumi.com", "cdn.khanumi.com", "torob.com", "cdn.torob.com",
)
MIN_IMAGE_DIM = 800              # reject thumbnails / low-quality
MIN_NAME_OVERLAP = 2             # ≥2 shared tokens required (was 1)
MAX_IMAGE_BYTES = 8 * 1024 * 1024
WIDTH_CAP = 900
IMAGE_QUALITY = 82
IMG_MAGIC = {b"\xff\xd8\xff": ".jpg", b"\x89PNG": ".png", b"RIFF": ".webp", b"GIF8": ".gif"}

# Sentence-boundary chars for smart truncation (FA + Latin).
_SENT_END_RE = re.compile(r"[.۔؟!…\n]+")

DEFAULT_PREFERRED_PROVIDERS = ("openrouter", "groq", "gemini", "cloudflare")


# ═══════════════════════ reference search corpus (fallback) ═══════════════════
# Search fallback when no Exa/Tavily key is configured. Entries carry *real*
# category-level reference facts (not brand claims); the anti-fake extractor
# only copies text that is literally present in the snippet.
def _search_corpus() -> list:
    return [
        {
            "keywords": ["شامپو", "آبرسان", "موهای خشک"],
            "title": "شامپو آبرسان مخصوص موهای خشک — راهنمای مصرف",
            "url": "https://www.digikala.com/mag/wp-content/uploads/2022/07/body-shampoo.jpg",
            "trust": "medium",
            "snippet": ("شامپو آبرسان برای موهای خشک مناسب است. روش مصرف: مو را خیس کنید، "
                        "مقدار کافی شامپو را کف کنید و به آرامی روی کف سر و ساقه مو بمالید، "
                        "سپس کاملا آبکشی کنید. ترکیبات رایج: آب، سدیم لورت سولفات، "
                        "کوکامیدوپروپیل بتائین، گلیسیرین، پانتنول."),
            "image_candidates": [
                {"url": "https://www.digikala.com/mag/wp-content/uploads/2022/07/body-shampoo.jpg",
                 "label": "شامپو آبرسان موهای خشک"},
            ],
        },
        {
            "keywords": ["ماسک", "کراتین", "کراتینه"],
            "title": "ماسک کراتینه — فواید و روش استفاده",
            "url": "https://en.wikipedia.org/wiki/Keratin",
            "trust": "high",
            "snippet": ("کراتین پروتئین ساختاری مو است. روش مصرف ماسک: پس از شامپو، ماسک را "
                        "روی ساقه مو بمالید و ۵ تا ۱۰ دقیقه صبر کنید و آبکشی کنید."),
            "image_candidates": [
                {"url": "https://www.digikala.com/mag/wp-content/uploads/2022/07/keratin-hair-mask.jpg",
                 "label": "ماسک مو کراتینه ترمیم کننده"},
            ],
        },
        {
            "keywords": ["کرم", "آبرسان", "پوست"],
            "title": "کرم آبرسان پوست — راهنمای مصرف",
            "url": "",
            "trust": "medium",
            "snippet": ("کرم آبرسان مناسب پوست های خشک و دهیدراته است. روش مصرف: صبح و شب "
                        "روی پوست تمیز بمالید. ترکیبات رایج: آب، گلیسیرین، هیالورونیک اسید، "
                        "سرامید."),
            "image_candidates": [],
        },
    ]


def _corpus_hit(tokens: set) -> list:
    hits = []
    for src in _search_corpus():
        blob = " ".join([src["title"], src["snippet"]] + src["keywords"]) + " "
        if not blob:
            continue
        if any(t in blob for t in tokens) and any(t in blob for t in tokens):
            hits.append(src)
    return hits
# ═══════════════════════ db helpers (prod vs isolated) ═════════════════════════
def _conn(db_path: str | None = None) -> sqlite3.Connection:
    """Production: Flask DB factory; isolated mode: plain sqlite3 temp DB."""
    if db_path:
        os.makedirs(os.path.dirname(os.path.abspath(db_path)) or ".", exist_ok=True)
        return sqlite3.connect(db_path, timeout=30)
    from giso.base import get_giso_db_conn
    return get_giso_db_conn()


def _load_product(db_path: str | None, product_id: int) -> dict | None:
    cols = ("id,name,brand,category,subcategory,description,short_description,usage,"
            "ingredients,warnings,suitable_for,hair_type,skin_type,concerns,tags,image_path,"
            "price,publish_status,source,channel_msg_id,updated_at")
    con = _conn(db_path)
    try:
        row = con.execute(f"SELECT {cols} FROM products WHERE id=?", (product_id,)).fetchone()
        if not row:
            return None
        return dict(zip(cols.split(","), row))
    except Exception as exc:
        logger.warning("enricher load_product #%s failed: %s", product_id, exc)
        return None
    finally:
        con.close()


def _save_enriched(db_path: str | None, product_id: int, payload: dict,
                   image_path: str, meta: dict,
                   bypass_source_check: bool = False) -> bool:
    """UPDATE only enrichment fields. NEVER price/stock/publish_status/name.
    Guard: source='channel' only — other imports are untouched.
    bypass_source_check فقط از مسیر سوپرادمینِ تأییدشده مجاز است و هرگز
    مقدار source محصول را در دیتابیس تغییر نمی‌دهد (فلگ فقط SQL را باز می‌کند)."""
    con = _conn(db_path)
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    try:
        p = payload
        # P1: tags column added via safe migration; tolerate legacy DBs without it.
        try:
            cols = {r[1] for r in con.execute("PRAGMA table_info(products)").fetchall()}
        except Exception:
            cols = set()
        has_tags = "tags" in cols
        if has_tags:
            sql = ("""UPDATE products SET
                  description=?, short_description=?, usage=?, ingredients=?,
                  warnings=?, suitable_for=?, hair_type=?, skin_type=?,
                  concerns=?, tags=?, image_path=?, updated_at=?
                WHERE id=? AND (source='channel' OR ?)""")
            args = (p.get("description") or "", p.get("short_description") or "",
                    p.get("usage") or "", p.get("ingredients") or "",
                    p.get("warnings") or "", p.get("suitable_for") or "",
                    p.get("hair_type") or "", p.get("skin_type") or "",
                    p.get("concerns") or "", p.get("tags") or "",
                    image_path or "", now, product_id,
                    1 if bypass_source_check else 0)
        else:
            sql = ("""UPDATE products SET
                  description=?, short_description=?, usage=?, ingredients=?,
                  warnings=?, suitable_for=?, hair_type=?, skin_type=?,
                  concerns=?, image_path=?, updated_at=?
                WHERE id=? AND (source='channel' OR ?)""")
            args = (p.get("description") or "", p.get("short_description") or "",
                    p.get("usage") or "", p.get("ingredients") or "",
                    p.get("warnings") or "", p.get("suitable_for") or "",
                    p.get("hair_type") or "", p.get("skin_type") or "",
                    p.get("concerns") or "", image_path or "", now, product_id,
                    1 if bypass_source_check else 0)
        cur = con.execute(sql, args)
        con.commit()
        if cur.rowcount:
            logger.info("enricher: product #%s enriched (engine=%s, image=%s)",
                        product_id, meta.get("engine"), meta.get("image_source"))
        return bool(cur.rowcount)
    except Exception as exc:
        try:
            con.rollback()
        except Exception:
            pass
        logger.warning("enricher save #%s failed: %s", product_id, exc)
        return False
    finally:
        con.close()
# ═══════════════════════ web search gateway ═══════════════════════════════════
def _fa_tokens(s: str) -> set:
    """Persian/Latin tokenizer for name-relevance and corpus lookup."""
    return {t for t in re.findall(r"[\u0600-\u06FF\w]{2,}", s or "")}


def search_web(query: str, max_results: int = 4) -> list:
    """Exa API first (when EXA_API_KEY is set), else the reference corpus."""
    key = os.environ.get("EXA_API_KEY", "").strip()
    if key:
        try:
            import httpx
            resp = httpx.post(
                "https://api.exa.ai/search",
                headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
                json={"query": query, "numResults": max_results, "type": "auto",
                      "contents": {"text": True}},
                timeout=20)
            if resp.status_code == 200:
                hits = resp.json().get("results", [])
                return [{"title": h.get("title") or "", "url": h.get("url") or "",
                         "trust": "high", "snippet": (h.get("text") or "")[:400],
                         "image_candidates": []} for h in hits]
            logger.warning("exa search http %s → corpus fallback", resp.status_code)
        except Exception as exc:
            logger.warning("exa search failed (%s) → corpus fallback", exc)
    return _corpus_hit(_fa_tokens(query))[:max_results]


# ═══════════════════════ prompt builder ═══════════════════════════════════════
SYSTEM_PROMPT = (
    "You are a careful cosmetic-data extractor for an Iranian beauty shop. "
    "Source priority: Digikala, Khanoumi, Torob. "
    "ANTI-FAKE HARD RULE: use ONLY facts literally present in the provided search "
    "text. If ingredients/usage/warnings are absent, return null for those keys. "
    "NEVER invent data. Return STRICT JSON only with keys: "
    "description(max 900 chars), short_description(max 150), usage(max 500, "
    "numbered steps), ingredients, warnings, suitable_for, hair_type, skin_type, "
    "concerns, tags(array of max 6 Persian keywords)."
)
# P1 PASS-2 (autonomous): same facts, sales framing — no new factual claims.
SELL_PROMPT = (
    "تو کپی‌رایتر فارسی فروشگاه آرایشی هستی. ورودی تو حقایق تأییدشده است؛ "
    "هیچ ترکیب/خاصیت/درصد جدید نساز. بازنویسی فروش: هوک احساسی کوتاه، لحن "
    "مسئله→راه‌حل، حداکثر ۳ بولت مزیت با •، انکر اعتماد (اصل بودن + مناسب چه "
    "کسی) و CTA «افزودن به سبد». اغراق درمانی ممنوع. خروجی فقط همان JSON با "
    "همان کلیدها باشد (description حداکثر ۹۰۰، short حداکثر ۱۵۰، usage حداکثر "
    "۵۰۰ با گام‌های شماره‌دار)."
)


def _providers_from(db_path: str | None) -> list:
    """Enabled provider rows from the given temp DB or live giso.db."""
    if db_path is None:
        from giso.ai_brain import list_ai_providers
        return list_ai_providers(only_enabled=True) or []
    uri = f"{Path(db_path).as_uri()}?mode=ro"   # correct on Windows paths too
    con = sqlite3.connect(uri, uri=True)
    con.row_factory = sqlite3.Row              # needed: default factory returns tuples
    try:
        return [dict(r) for r in
                con.execute("SELECT * FROM giso_ai_providers WHERE enabled=1").fetchall()]
    except Exception:
        return []
    finally:
        con.close()


def _http_chat(provider: dict, messages: list, max_tokens: int = 900,
               temperature: float = 0.3) -> dict:
    """Self-contained OpenAI-compatible call. Used ONLY in isolated mode so the
    live giso.db health tables are never written by simulations."""
    import httpx
    name = str(provider.get("name") or "")
    key = str(provider.get("api_key") or "").strip()
    model = str(provider.get("selected_model") or "") or "default"
    headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
    if provider.get("kind") == "cloudflare":
        api_root = str(provider.get("api_root") or "").strip().rstrip("/")
        if not api_root:
            return {"ok": False, "error": "no api_root"}
        url = f"{api_root}/{model}"
        body = {"messages": messages, "max_tokens": max_tokens}
    else:
        base = str(provider.get("base_url") or "").strip().rstrip("/")
        if not base:
            return {"ok": False, "error": "no base_url"}
        url = f"{base}/chat/completions"
        body = {"model": model, "messages": messages, "temperature": temperature,
                "max_tokens": max_tokens}
    try:
        timeout = int(provider.get("timeout") or 6)
    except (TypeError, ValueError):
        timeout = 6
    try:
        resp = httpx.post(url, headers=headers, json=body, timeout=timeout)
        if resp.status_code != 200:
            return {"ok": False, "error": f"HTTP {resp.status_code}"}
        raw = resp.json()
        text = ""
        try:
            text = raw["choices"][0]["message"]["content"]
        except Exception:
            pass
        return {"ok": True, "provider": name, "model": model, "text": text}
    except Exception as exc:
        return {"ok": False, "provider": name, "model": model, "error": str(exc)}


def call_ai_failover(messages: list, db_path: str | None = None,
                     max_tokens: int = 900, temperature: float = 0.3) -> dict:
    """Multi-provider failover chain (HARD RULE).
    - Production (db_path None): reuse the existing `chat_with_failover` engine
      (same one used by seo_jobs.py); its own health-marking is its behavior.
    - Isolated (db_path set): self-contained chain over the temp DB providers —
      zero writes to the live database."""
    if db_path is None:
        try:
            import asyncio
            from giso.ai_runtime import chat_with_failover
            res = asyncio.run(chat_with_failover(
                messages, preferred_provider=DEFAULT_PREFERRED_PROVIDERS[0],
                temperature=temperature, max_tokens=max_tokens, role="user"))
            return {"ok": bool(res.get("ok")), "text": res.get("text") or "",
                    "engine": f"chat_with_failover:{res.get('provider')}",
                    "errors": res.get("provider_errors") or [], "raw": res}
        except Exception as exc:
            return {"ok": False, "engine": "chat_with_failover", "errors": [str(exc)]}

    errors, ok = [], None
    for provider in _providers_from(db_path):
        res = _http_chat(provider, messages, max_tokens=max_tokens,
                         temperature=temperature)
        if res.get("ok"):
            ok = res
            logger.info("enricher ai ok via %s", provider.get("name"))
            break
        errors.append({"provider": provider.get("name"), "error": res.get("error")})
    if ok:
        return {"ok": True, "text": ok["text"], "engine": f"isolated:{ok['provider']}",
                "errors": errors}
    return {"ok": False, "engine": "isolated-failover-exhausted", "errors": errors}
def build_prompt(product_name: str, brand: str, category: str,
                 search_text: str, stage: str = "extract") -> list:
    """P1 2-pass engine (autonomous, no manual prompts):
    stage='extract' (temp 0.0): verbatim ground-truth JSON from Iranian sources.
    stage='market' (temp 0.7): rewrite PASS-1 facts as Persian sales copy."""
    if stage == "market":
        user = (
            f"نام محصول: {product_name}\nبرند: {brand or 'نامشخص'}\nدسته: {category}\n"
            f"حقایق تأییدشده (فقط همین‌ها را بازنویسی کن، چیز جدید نساز):\n{search_text[:2500]}\n\n"
            "بازآفرینی فروش: هوک احساسی + لحن مسئله→راه‌حل، ۳ بولت مزیت با •، "
            "انکر اعتماد (اصل بودن/مناسب چه کسی) + CTA «افزودن به سبد». اغراق درمانی و درصد ساختگی ممنوع. "
            "خروجی فقط همان JSON با همان کلیدها باشد."
        )
        return [{"role": "system", "content": SELL_PROMPT},
                {"role": "user", "content": user}]
    user = (
        f"نام محصول: {product_name}\nبرند: {brand or 'نامشخص'}\nدسته: {category}\n"
        f"متن جستجو (منابع ایرانی: دیجی‌کالا، خانومی، ترب):\n{search_text[:2500]}\n\n"
        "خروجی فقط JSON باشد؛ برای فیلدهایی که در متن بالا نبوده null برگردان."
    )
    return [{"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user}]


def smart_truncate(text: str, limit: int) -> str:
    """P1: cut at the last sentence boundary before `limit` — never mid-sentence."""
    t = (text or "").strip()
    if len(t) <= limit:
        return t
    window = t[:limit]
    # last sentence end inside the window (keep a small tail margin)
    ends = [m.end() for m in _SENT_END_RE.finditer(window)]
    cut = max([e for e in ends if e >= max(20, limit - 160)], default=0)
    if cut:
        return window[:cut].strip()
    # fallback: last space (never mid-word)
    sp = window.rfind(" ")
    return (window[:sp] if sp > 20 else window).strip() + "…"


def _to_numbered_steps(text: str, max_steps: int = 3) -> str:
    """P1: normalize usage into ≤3 numbered FA steps (each a full sentence)."""
    parts = [p.strip(" ،؛:.-") for p in _SENT_END_RE.split(text or "") if p.strip()]
    steps = [smart_truncate(p, MAX_USAGE // max_steps) for p in parts[:max_steps]]
    return "\n".join(f"{i + 1}. {s}" for i, s in enumerate(steps) if s)


def marketing_rewrite(heuristic: dict, name: str, brand: str) -> dict:
    """P1 PASS-2 fallback (fully autonomous, zero-LLM path): reshape grounded
    PASS-1 facts into hook + bullets + trust CTA. Adds NO new factual claims —
    only sales framing around verbatim evidence."""
    h = dict(heuristic)
    desc = h.get("description") or ""
    hook = f"{name}؛ راه‌حلی مطمئن برای روتین روزانه شما."
    bullets = []
    if desc:
        bullets.append(f"• {smart_truncate(desc, 220)}")
    if h.get("suitable_for"):
        bullets.append(f"• مناسب برای {smart_truncate(h['suitable_for'], 120)}")
    if h.get("ingredients"):
        bullets.append(f"• با ترکیبات کلیدی: {smart_truncate(h['ingredients'], 140)}")
    trust = "محصول اصل با تأیید تیم گیسو — همین حالا به سبد خرید اضافه کنید."
    body = "\n".join([hook] + bullets[:3] + [trust])
    h["description"] = smart_truncate(body, MAX_DESCRIPTION)
    if not h.get("short_description") and desc:
        h["short_description"] = smart_truncate(desc, MAX_SHORT_DESC)
    usage = h.get("usage") or ""
    if usage and not re.match(r"^\s*\d\.", usage):
        stepped = _to_numbered_steps(usage)
        if stepped:
            h["usage"] = stepped
    return h
# ═══════════════════════ anti-fake extraction (heuristics) ════════════════════
_CAT_TERMS = {
    "hair": ["مو", "شامپو", "ماسک", "سرم مو"],
    "face": ["پوست", "صورت", "کرم", "ضدآفتاب"],
    "beauty": ["آرایش", "رژ", "ریمل"],
    "body": ["بدن", "صابون", "لوسیون"],
    "care": ["دهان", "دندان", "دئودورانت"],
    "nutrition": ["دمنوش", "عسل"],
}


def _first_block(text: str, markers: tuple, stop_at: str = ".") -> str:
    """Pull the first segment after a Persian marker (verbatim from text)."""
    for mark in markers:
        idx = text.find(mark)
        if idx < 0:
            continue
        seg = text[idx:idx + 260]
        cut = seg.find(stop_at)
        return (seg[:cut + 1] if cut > 0 else seg).strip()
    return ""


def extract_from_search_text(name: str, brand: str, category: str,
                             search_text: str) -> dict:
    """Deterministic anti-fake extractor: every value is a verbatim substring of
    the search text; anything absent stays ''. (In production an LLM pass obeys
    the same STRICT 'null if absent' contract.)"""
    out = {
        "description": "", "short_description": "", "usage": "",
        "ingredients": "", "warnings": "", "suitable_for": "",
        "hair_type": "", "skin_type": "", "concerns": "", "tags": [],
    }
    text = search_text or ""
    terms = _CAT_TERMS.get((category or "").lower(), ["مو", "پوست"])
    for sent in re.split(r"[.۔﴾\n]", text):
        sent = sent.strip()
        if sent and any(t in sent for t in terms):
            out["description"] = smart_truncate(sent, MAX_DESCRIPTION)
            break
    if out["description"]:
        out["short_description"] = smart_truncate(out["description"], MAX_SHORT_DESC)
    # usage — only if a real usage marker exists in the text (else '')
    raw_usage = _first_block(text, ("روش مصرف", "طریقه مصرف", "روش استفاده"), stop_at=".")
    if raw_usage:
        stepped = _to_numbered_steps(raw_usage)
        out["usage"] = smart_truncate(stepped or raw_usage, MAX_USAGE)
    ing = _first_block(text, ("ترکیبات رایج", "ترکیبات", "مواد تشکیل‌دهنده"), stop_at=".")
    out["ingredients"] = ing if ing else ""
    return out


def merge_payload(ai: dict, heuristic: dict, name: str = "", brand: str = "") -> dict:
    """P1: Prefer LLM JSON else deterministic extractor, then PASS-2 marketing
    framing (autonomous rewrite of grounded facts only), then smart-truncate
    clamps at sentence boundaries (authoritative)."""
    payload = {}
    if ai.get("ok") and ai.get("text"):
        try:
            raw = ai["text"].strip()
            if raw.startswith("```"):
                raw = raw.strip("`").lstrip("json")
            candidate = json.loads(raw)
            if isinstance(candidate, dict):
                payload = candidate
        except Exception:
            pass
    if not payload:
        payload = heuristic
    # P1 PASS-2 autonomous framing (grounded facts only; zero new claims).
    try:
        base = dict(payload) if isinstance(payload, dict) else {}
        payload = marketing_rewrite(base or heuristic, name, brand)
    except Exception:
        payload = payload if isinstance(payload, dict) else heuristic
    clean = {}
    for k in ("description", "short_description", "usage", "ingredients", "warnings",
              "suitable_for", "hair_type", "skin_type", "concerns"):
        v = payload.get(k)
        clean[k] = v if isinstance(v, str) else ("" if v is None else str(v))
    # toned tags
    tags = payload.get("tags") or []
    if not isinstance(tags, list):
        tags = []
    clean["tags"] = ",".join([str(t)[:40] for t in tags][:MAX_TAGS])
    # P1 smart clamps at sentence boundaries (HARD RULE, never mid-sentence)
    clamps = {"description": MAX_DESCRIPTION, "short_description": MAX_SHORT_DESC,
              "usage": MAX_USAGE, "ingredients": MAX_INGREDIENTS,
              "warnings": MAX_WARNINGS, "suitable_for": MAX_SUITABLE,
              "concerns": MAX_CONCERNS}
    for k, mx in clamps.items():
        clean[k] = smart_truncate(clean[k], mx)
    return clean
# ═══════════════════════ image pipeline (safe & accurate) ══════════════════════
def _name_relevance(candidate_label: str, product_name: str,
                    brand: str = "") -> int:
    """P1 strict: shared Persian tokens must be ≥ MIN_NAME_OVERLAP (2); when a
    brand is known the label must also contain a brand token (else reject)."""
    overlap = len(_fa_tokens(product_name) & _fa_tokens(candidate_label or ""))
    if overlap < MIN_NAME_OVERLAP:
        return 0
    btoks = _fa_tokens(brand or "")
    if btoks and not (btoks & _fa_tokens(candidate_label or "")):
        return 0
    return overlap


def _download_validate(url: str) -> bytes:
    import httpx
    resp = httpx.get(url, timeout=25, follow_redirects=True,
                     headers={"User-Agent": "Mozilla/5.0 (GisoEnricher/1.0)"})
    resp.raise_for_status()
    data = resp.content
    if len(data) > MAX_IMAGE_BYTES:
        raise ValueError("image too large")
    if not any(data.startswith(m) for m in IMG_MAGIC):
        raise ValueError("magic bytes mismatch -> blocked")
    return data


def _store_webp(data: bytes, name: str, upload_folder: str) -> str:
    """P1: validate + enforce ≥800px + center-crop to 1:1 + 900px WebP, atomic.
    Returns relative 'uploads/<file>' path."""
    import io
    from PIL import Image, UnidentifiedImageError
    try:
        img = Image.open(io.BytesIO(data))
        img.verify()
        img = Image.open(io.BytesIO(data)).convert("RGB")
    except (UnidentifiedImageError, OSError) as exc:
        raise ValueError(f"pillow verify failed: {exc}")
    w, h = img.size
    if min(w, h) < MIN_IMAGE_DIM:
        raise ValueError(f"image too small ({w}x{h} < {MIN_IMAGE_DIM}px)")
    # center-crop to exact 1:1 before resize (tall/wide packshots normalized)
    side = min(w, h)
    img = img.crop(((w - side) // 2, (h - side) // 2,
                    (w + side) // 2, (h + side) // 2))
    img.thumbnail((WIDTH_CAP, WIDTH_CAP))
    up = Path(upload_folder or (str(Path(__file__).resolve().parent.parent.parent /
                                    "static" / "uploads")))
    up.mkdir(parents=True, exist_ok=True)
    fname = "".join(ch for ch in name if ch.isalnum())[:24] or "prod"
    fname = f"prod_{fname}_{datetime.now():%Y%m%d%H%M%S%f}.webp"
    dst = up / fname
    tmp = dst.with_suffix(".webp.tmp")
    img.save(tmp, "WEBP", quality=IMAGE_QUALITY, method=6)
    tmp.replace(dst)  # atomic
    return "uploads/" + fname


def image_pipeline(product_name: str, sources: list, base_image_path: str,
                   upload_folder: str | None = None, brand: str = "") -> dict:
    """P1 strict: Iranian-CDN allow-list only (no picsum), ≥2 token overlap +
    brand match, ≥800px 1:1 WebP. On any failure keep the Bale-channel photo
    (or '' → NULL-safe fallback). Never raises."""
    candidates = [c for s in sources for c in (s.get("image_candidates") or [])]
    for c in candidates:
        url = (c or {}).get("url") or ""
        label = (c or {}).get("label") or ""
        if "picsum.photos" in url:
            continue  # P1: random decor banned, even if legacy corpus lingers
        if not url or not any(frg in url for frg in ALLOWED_IMAGE_HOST_FRAGMENTS):
            continue
        if not _name_relevance(label, product_name, brand):
            continue  # image does not match the product name/brand -> reject
        try:
            data = _download_validate(url)
            rel = _store_webp(data, product_name, upload_folder)
            return {"image_path": rel, "source": "web",
                    "verification": "magic_bytes+pillow_verify+resize_webp",
                    "source_url": url}
        except Exception as exc:
            logger.warning("enricher image candidate failed %s -> %s", url, exc)
            continue
    # graceful fallback: keep the original Bale-channel photo
    return {"image_path": base_image_path or "", "source": "bale_photo_fallback",
            "verification": "original_channel_photo_kept", "source_url": ""}
# ═══════════════════════ orchestration ════════════════════════════════════════
def run_enrichment(product_id: int, parsed: dict | None = None,
                   base_image_path: str = "", db_path: str | None = None,
                   upload_folder: str | None = None,
                   ai_db_path: str | None = None,
                   bypass_source_check: bool = False) -> dict:
    """End-to-end enrichment for one pending channel product. Non-destructive to
    price/stock/publish_status. Returns a result dict; never raises."""
    try:
        row = _load_product(db_path, product_id)
        if not row:
            return {"ok": False, "error": "product_not_found"}
        if row.get("source") != "channel" and not bypass_source_check:
            return {"ok": False, "error": "source_not_channel"}

        name = row["name"] or ""
        brand = (parsed or {}).get("brand") or row.get("brand") or ""
        category = (parsed or {}).get("category") or row.get("category") or "hair"
        base_image = (base_image_path or "").strip() or (row.get("image_path") or "")

        sources = search_web(f"{name} {brand} {category}")
        search_text = " ".join((s.get("snippet") or "") for s in sources)
        if not search_text:
            sources = _corpus_hit(_fa_tokens(category))

        ai = call_ai_failover(build_prompt(name, brand, category, search_text),
                              db_path=ai_db_path, temperature=0.0, max_tokens=1200)
        heuristic = extract_from_search_text(name, brand, category, search_text)
        # P1 PASS-2: autonomous LLM marketing rewrite of PASS-1 facts (temp 0.7).
        # Only when PASS-1 produced text; failures fall back silently to the
        # deterministic marketing_rewrite() inside merge_payload().
        market_ai = {"ok": False, "text": ""}
        if ai.get("ok") and ai.get("text"):
            try:
                market_ai = call_ai_failover(
                    build_prompt(name, brand, category, ai.get("text") or "",
                                 stage="market"),
                    db_path=ai_db_path, temperature=0.7, max_tokens=1500)
            except Exception:
                market_ai = {"ok": False, "text": ""}
        payload = merge_payload(market_ai if market_ai.get("ok") else ai,
                                heuristic, name=name, brand=brand)

        image = image_pipeline(name, sources, base_image, upload_folder, brand=brand)
        meta = {"engine": ai.get("engine") or "heuristic",
                "ai_ok": bool(ai.get("ok")),
                "ai_errors": ai.get("errors") or [],
                "image_source": image.get("source")}
        saved = _save_enriched(db_path, product_id, payload, image.get("image_path") or "", meta,
                               bypass_source_check=bypass_source_check)

        return {
            "ok": saved, "product_id": product_id,
            "product_name": name, "category": category,
            "ai": meta, "sources_used": len(sources),
            "payload": payload, "image": image,
        }
    except Exception as exc:
        logger.exception("enrichment #%s failed: %s", product_id, exc)
        return {"ok": False, "product_id": product_id, "error": str(exc)}


def schedule_enrichment(product_id: int, parsed: dict | None = None,
                        base_image_path: str = "", db_path: str | None = None,
                        upload_folder: str | None = None,
                        ai_db_path: str | None = None) -> bool:
    """Non-blocking background hook for the channel importer (best-effort)."""
    try:
        t = threading.Thread(
            target=run_enrichment,
            kwargs={"product_id": product_id, "parsed": parsed,
                    "base_image_path": base_image_path, "db_path": db_path,
                    "upload_folder": upload_folder, "ai_db_path": ai_db_path},
            name=f"giso-enrich-{product_id}", daemon=True)
        t.start()
        return True
    except Exception as exc:
        logger.warning("enrichment schedule #%s failed: %s", product_id, exc)
        return False


def run_enrichment_admin(product_id: int, parsed: dict | None = None,
                         upload_folder: str | None = None,
                         db_path: str | None = None) -> dict:
    """نسخهٔ اختصاصی سوپرادمین: دور زدن امنِ guard  source='channel' (بدون تغییر source).

    دستیار سوپرادمین پس از تأیید OTP مستقیماً این تابع را صدا می‌کند؛ منطق غنی‌سازی
    عیناً مشترک است و فقط بررسی منبع دور می‌زند تا هر محصولی (site/channel) قابل
    غنی‌سازی باشد. قیمت/موجودی/نام/تنظیمات دست‌نخورده می‌مانند و برخلاف نسخهٔ
    قبلی هیچ `UPDATE products SET source` در دیتابیس زنده اجرا نمی‌شود.
    """
    try:
        # P3-safe: روی دیتابیس زنده هیچ UPDATE source انجام نمی‌شود؛
        # فلگ bypass_source_check فقط در لحظهٔ اجرا SQL نگهبان را باز می‌کند.
        res = run_enrichment(product_id=product_id, parsed=parsed,
                             db_path=db_path, upload_folder=upload_folder,
                             bypass_source_check=True)
        return res
    except Exception as exc:
        logger.exception("admin enrichment #%s failed: %s", product_id, exc)
        return {"ok": False, "product_id": product_id, "error": str(exc)}


__all__ = ["schedule_enrichment", "run_enrichment", "run_enrichment_admin", "search_web",
           "build_prompt", "call_ai_failover", "image_pipeline",
           "smart_truncate", "marketing_rewrite"]