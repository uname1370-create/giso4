# -*- coding: utf-8 -*-
"""تولید و کش ویدئوی واقعی Image-to-Video برای Hero صفحه اصلی گیسو.

مدل فعلی: Cloudflare AI / RunwayML Gen-4.5.
ویدئو فقط با درخواست صریح ادمین تولید می‌شود تا هر بار ورود کاربر هزینه AI ایجاد نکند.
خروجی در giso/static/uploads/home-hero/ ذخیره و در دفعات بعد از همان فایل پخش می‌شود.
"""
from __future__ import annotations

import base64
import json
import logging
import os
import re
import tempfile
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

import requests

from giso.config import Config
from giso.ai_brain import list_ai_providers

logger = logging.getLogger("giso_home_hero_video")

MODEL = "runwayml/gen-4.5"
DURATION = 5
RATIO = "960:960"
PROMPT = (
    "Animate the exact supplied hero photograph naturally and conservatively. "
    "Two children gently and realistically play with and handle the long hair bundles "
    "they are already holding, with subtle hand, wrist, shoulder and head movement. "
    "The hair strands and loose hair bundles move softly and naturally. "
    "Keep both children's faces, identity, age, clothing, skin, hands, hair color, "
    "the mirror, gold frame, studio background and every object in the composition "
    "unchanged. No new people, no new objects, no face changes, no body deformation, "
    "no extra fingers, no text, no camera shake. Very subtle cinematic slow motion, "
    "luxury beauty advertisement, warm soft lighting, almost locked camera with only "
    "a tiny natural push-in. Preserve the original composition."
)

OUTPUT_DIR = Path(Config.UPLOAD_FOLDER) / "home-hero"
OUTPUT_PATH = OUTPUT_DIR / "giso-main-hero-ai.mp4"


def _provider_credentials() -> list[Tuple[str, str, str]]:
    """از همان Providerهای Cloudflare پنل AI استفاده می‌کند؛ کلید جدیدی در کد ندارد."""
    found: list[Tuple[str, str, str]] = []
    for row in list_ai_providers(only_enabled=True):
        name = str(row["name"] or "").strip().lower()
        if name not in {"cf", "cloudflare", "cf1", "cf2", "cf3"}:
            continue
        token = str(row["api_key"] or "").strip()
        api_root = str(row["api_root"] or "").strip().rstrip("/")
        if not token or not api_root:
            continue
        if "/client/v4/accounts/" not in api_root or not api_root.endswith("/ai/run"):
            continue
        found.append((name, token, api_root))
    # fallback به env برای نصب‌هایی که هنوز Provider در DB ندارند.
    for index in range(1, 4):
        token = (
            os.environ.get(f"CLOUDFLARE_API_TOKEN_{index}", "").strip()
            or os.environ.get(f"BUTI_AI_CLOUDFLARE_API_TOKEN_{index}", "").strip()
        )
        account = (
            os.environ.get(f"CLOUDFLARE_ACCOUNT_ID_{index}", "").strip()
            or os.environ.get(f"BUTI_AI_CLOUDFLARE_ACCOUNT_ID_{index}", "").strip()
        )
        if token and account:
            found.append(
                (f"env_cf{index}", token,
                 f"https://api.cloudflare.com/client/v4/accounts/{account}/ai/run")
            )
    return found


def _image_data_uri() -> str:
    path = Path(Config.BASE_DIR) / "giso" / "static" / "images" / "giso-main-hero.png"
    if not path.is_file():
        raise FileNotFoundError(f"Hero image not found: {path}")
    encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:image/png;base64,{encoded}"


def _extract_video(payload: Any) -> str:
    if not isinstance(payload, dict):
        return ""
    result = payload.get("result")
    if isinstance(result, dict):
        return str(result.get("video") or "").strip()
    return str(payload.get("video") or "").strip()


def _download_video(url: str) -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix=".hero-", suffix=".mp4", dir=str(OUTPUT_DIR))
    os.close(fd)
    temp_path = Path(temp_name)
    try:
        with requests.get(url, stream=True, timeout=(15, 180)) as response:
            response.raise_for_status()
            content_type = (response.headers.get("content-type") or "").lower()
            if "video" not in content_type and not url.lower().split("?")[0].endswith(".mp4"):
                raise RuntimeError("Cloudflare returned a non-video response.")
            total = 0
            with temp_path.open("wb") as out:
                for chunk in response.iter_content(chunk_size=1024 * 256):
                    if not chunk:
                        continue
                    total += len(chunk)
                    if total > 80 * 1024 * 1024:
                        raise RuntimeError("Generated hero video is larger than 80MB.")
                    out.write(chunk)
        if total < 4096:
            raise RuntimeError("Generated hero video is unexpectedly small.")
        temp_path.replace(OUTPUT_PATH)
    finally:
        try:
            if temp_path.exists():
                temp_path.unlink()
        except Exception:
            pass


def hero_video_status() -> Dict[str, Any]:
    exists = OUTPUT_PATH.is_file() and OUTPUT_PATH.stat().st_size > 4096
    return {
        "ready": bool(exists),
        "url": "/static/uploads/home-hero/giso-main-hero-ai.mp4" if exists else "",
        "model": MODEL,
        "duration": DURATION,
    }


def generate_hero_video() -> Dict[str, Any]:
    """یک بار ویدئوی واقعی را تولید و در سایت cache می‌کند."""
    current = hero_video_status()
    if current["ready"]:
        return {"ok": True, "cached": True, **current}

    image = _image_data_uri()
    providers = _provider_credentials()
    if not providers:
        return {
            "ok": False,
            "error": "Cloudflare Provider فعال و دارای API Key/API Root در پنل AI پیدا نشد."
        }

    headers = {"Authorization": "Bearer {token}", "Content-Type": "application/json"}
    last_error = ""
    for provider_name, token, api_root in providers:
        try:
            request_headers = {k: v.format(token=token) for k, v in headers.items()}
            payload = {
                "model": MODEL,
                "input": {
                    "prompt": PROMPT,
                    "image_input": image,
                    "duration": DURATION,
                    "ratio": RATIO,
                },
            }
            response = requests.post(
                api_root,
                headers=request_headers,
                json=payload,
                timeout=(20, 240),
            )
            if response.status_code != 200:
                last_error = f"{provider_name}: HTTP {response.status_code}: {response.text[:240]}"
                continue
            data = response.json()
            if data.get("success") is False:
                last_error = f"{provider_name}: {str(data.get('errors') or data)[:240]}"
                continue
            video_url = _extract_video(data)
            if not video_url:
                last_error = f"{provider_name}: Cloudflare response has no video URL."
                continue
            _download_video(video_url)
            logger.info("Home hero I2V generated successfully via %s", provider_name)
            return {"ok": True, "cached": False, **hero_video_status()}
        except Exception as exc:
            last_error = f"{provider_name}: {type(exc).__name__}: {exc}"
            logger.warning("Home hero I2V provider failed: %s", last_error)

    return {"ok": False, "error": last_error or "تولید ویدئوی Hero ناموفق بود."}
