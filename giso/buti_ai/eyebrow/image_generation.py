# -*- coding: utf-8 -*-
"""زنجیره تولید تصویر نهایی ابرو برای Buti AI.

این فایل عمداً داخل `giso/buti_ai/eyebrow/` است تا منطق اختصاصی آینه ابرو
در ماژول خودش بماند. خروجی واقعی image-generation فقط وقتی فعال می‌شود که
provider/model/key در پنل «مدیریت AI» یا محیط تنظیم شده باشد. در غیر این صورت،
خروجی امن `python_guided_composite` از `final_design.py` fallback می‌شود.

پیکربندی‌های پشتیبانی‌شده بدون ذخیره کلید در کد:

1) Cloudflare سازگار با نسخه قدیمی buti-test:
   CLOUDFLARE_API_TOKEN_1..3
   CLOUDFLARE_ACCOUNT_ID_1..3
   CLOUDFLARE_MODEL یا CLOUDFLARE_MODEL_1..3

2) سه مدل عمومی HTTP/OpenAI-compatible:
   BUTI_AI_IMAGE_MODEL_1_URL
   BUTI_AI_IMAGE_MODEL_1_KEY یا BUTI_AI_IMAGE_MODEL_1_KEY_ENV
   BUTI_AI_IMAGE_MODEL_1_MODEL
   BUTI_AI_IMAGE_MODEL_1_KIND=openai_image_edit|multipart|json_image
   ... تا 3

3) JSON پیشرفته:
   BUTI_AI_IMAGE_PROVIDERS='[{"id":"model_a","kind":"openai_image_edit",...}]'

هیچ کلید API، تصویر base64 یا داده حساس لاگ/ذخیره مستقیم نمی‌شود.
"""
from __future__ import annotations

import base64
import json
import logging
import mimetypes
import os
import re
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from io import BytesIO
from typing import Any, Dict, Iterable, List, Optional, Tuple

import requests

from giso.buti_ai.eyebrow import final_design
from giso.buti_ai.eyebrow.landmarks import MASK_POLARITY, ensure_eyebrow_mask
from giso.buti_ai.eyebrow.options import normalize_style_key

logger = logging.getLogger("giso_buti_ai_image_generation")

DEFAULT_CLOUDFLARE_MODEL = "@cf/black-forest-labs/flux-2-klein-4b"
CLOUDFLARE_INPAINTING_MODEL = "@cf/runwayml/stable-diffusion-v1-5-inpainting"
CLOUDFLARE_INPAINTING_KINDS = {"cloudflare_inpainting", "cloudflare_inpaint", "inpainting", "mask_inpainting"}
DEFAULT_TIMEOUT_SECONDS = 90
MAX_DOWNLOAD_BYTES = 12 * 1024 * 1024
MAX_SAVE_SIDE = 1600
# Increased from 512 to 768 to preserve eyebrow hair detail – critical for microblading strokes
# 768 is supported by Cloudflare and balances quality vs latency
MAX_PROVIDER_INPUT_SIDE = 768
MAX_INPAINTING_INPUT_SIDE = 768
MAX_DIFF_SAMPLE_PIXELS = 260_000
# Updated thresholds for Design Region (larger than old tight mask)
# Old tight mask coverage 0.01-0.045, new design region 0.02-0.09
# MAX increased to allow real redesign while still preventing eye/face intrusion
MIN_VISIBLE_EYEBROW_MEAN_DELTA = 3.0
MAX_VISIBLE_EYEBROW_MEAN_DELTA = 220.0
MIN_VISIBLE_EYEBROW_CHANGED_RATIO = 0.018
VISIBLE_EYEBROW_PIXEL_DELTA = 7.0
# Stricter outside preservation for true inpainting guarantee – but allow composite guarantee
MAX_OUTSIDE_MASK_MEAN_DELTA = 0.6
MAX_OUTSIDE_MASK_P99_DELTA = 3.5
MAX_OUTSIDE_CHANGED_RATIO = 0.01
MAX_INSIDE_WHITE_RATIO = 0.06
WHITE_THRESHOLD = 190
LIGHT_WHITE_THRESHOLD = 180
# Design Region coverage limits
MAX_DESIGN_COVERAGE_RATIO = 0.095
MAX_INPAINTING_COVERAGE_RATIO = 0.18


class ImageProviderError(RuntimeError):
    """خطای کنترل‌شده provider بدون داده حساس."""


@dataclass
class ImageProviderConfig:
    id: str
    label: str
    kind: str
    endpoint: str
    model: str = ""
    api_key: str = ""
    headers: Dict[str, str] = field(default_factory=dict)
    extra: Dict[str, Any] = field(default_factory=dict)

    def public(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "label": self.label,
            "kind": self.kind,
            "model": self.model,
            "endpoint_host": _safe_host(self.endpoint),
        }


def _safe_host(url: str) -> str:
    try:
        from urllib.parse import urlparse

        parsed = urlparse(url or "")
        return parsed.netloc or ""
    except Exception:
        return ""


def _safe_log_value(value: Any, limit: int = 180) -> str:
    if value is None:
        return ""
    if isinstance(value, float):
        return f"{value:.6f}"
    text = str(value)
    text = text.replace("\n", " ").replace("\r", " ").strip()
    return text[:limit]


def _beauty_log(tag: str, message: str = "", **fields: Any) -> None:
    """Beauty-AI-only structured log helper; never include keys/tokens/secrets."""
    safe_parts = []
    for key, value in fields.items():
        key_text = str(key or "").strip()
        if not key_text:
            continue
        if any(secret in key_text.lower() for secret in ("token", "secret", "api_key", "authorization", "account_id")):
            continue
        safe_parts.append(f"{key_text}={_safe_log_value(value)}")
    suffix = " ".join(safe_parts)
    logger.info("%s %s%s%s", tag, message or "", " " if suffix else "", suffix)


def _trace_log(step: str, message: str = "", **fields: Any) -> None:
    """Diagnostic trace logger for eyebrow final design flow - READ ONLY instrumentation.
    Never logs secrets, base64, or image content.
    """
    safe_parts = []
    for key, value in fields.items():
        key_text = str(key or "").strip()
        if not key_text:
            continue
        low = key_text.lower()
        if any(secret in low for secret in ("token", "secret", "api_key", "authorization", "account_id", "key", "password")):
            # allow non-secret keys like model, provider, etc.
            if low not in {"api_key", "token", "secret", "authorization", "account_id"} and "key" not in low:
                pass
            else:
                if low in {"provider", "model", "endpoint", "host", "kind", "label", "id"}:
                    pass
                else:
                    # skip truly secret fields
                    if low in {"api_key", "token", "secret", "authorization"}:
                        continue
        # skip base64/data uri
        if isinstance(value, str) and len(value) > 500 and ("base64" in value or "data:image" in value):
            value = f"[base64 len={len(value)}]"
        safe_parts.append(f"{key_text}={_safe_log_value(value)}")
    suffix = " ".join(safe_parts)
    logger.info("[EYEBROW_TRACE][%s] %s%s%s", step, message or "", " " if suffix else "", suffix)


def _image_size_for_log(path: str) -> Tuple[int, int]:
    try:
        from PIL import Image

        with Image.open(path) as image:
            return int(image.width or 0), int(image.height or 0)
    except Exception:
        return 0, 0


def _env_value(env: Optional[Dict[str, str]], key: str, default: str = "") -> str:
    source = env if env is not None else os.environ
    return str(source.get(key, default) or "").strip()


def _truthy(value: Any) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "on", "y"}


def _cloudflare_kind_for_model(model: str, configured_kind: str = "cloudflare") -> str:
    """Capability routing for documented Cloudflare image models, without changing selected model."""
    kind = str(configured_kind or "").strip().lower() or "cloudflare"
    if kind in CLOUDFLARE_INPAINTING_KINDS:
        return "cloudflare_inpainting"
    if str(model or "").strip() == CLOUDFLARE_INPAINTING_MODEL:
        return "cloudflare_inpainting"
    return kind


def _timeout_seconds(env: Optional[Dict[str, str]]) -> int:
    for key in ("BUTI_AI_IMAGE_TIMEOUT_SECONDS", "CLOUDFLARE_TIMEOUT_MS", "PROVIDER_TIMEOUT_MS"):
        raw = _env_value(env, key)
        if not raw:
            continue
        try:
            value = int(float(raw))
        except Exception:
            continue
        if key.endswith("_MS"):
            value = max(1, int(value / 1000))
        if value >= 2:
            return min(value, 180)
    return DEFAULT_TIMEOUT_SECONDS


def _provider_order(providers: List[ImageProviderConfig], env: Optional[Dict[str, str]]) -> List[ImageProviderConfig]:
    # Prioritize true inpainting providers for eyebrow redesign – they guarantee outside preservation
    # If no explicit order env, sort inpainting kinds first
    raw = _env_value(env, "BUTI_AI_IMAGE_PROVIDER_ORDER") or _env_value(env, "PROVIDER_ORDER")
    if not raw:
        # No explicit order: inpainting first, then flux/other
        inpaint = [p for p in providers if str(p.kind or "").lower() in CLOUDFLARE_INPAINTING_KINDS or str(p.model or "").strip() == CLOUDFLARE_INPAINTING_MODEL]
        others = [p for p in providers if p not in inpaint]
        return inpaint + others
    by_id = {p.id.lower(): p for p in providers}
    ordered: List[ImageProviderConfig] = []
    for item in raw.split(","):
        key = item.strip().lower()
        provider = by_id.get(key)
        if provider and provider not in ordered:
            ordered.append(provider)
    for provider in providers:
        if provider not in ordered:
            ordered.append(provider)
    # After explicit order, still bubble inpainting to front if not already ordered strictly
    # Keep explicit order but ensure inpainting providers are tried before flux if they appear
    # (If user explicitly wants flux first via env, respect it)
    if not raw:
        inpaint = [p for p in ordered if str(p.kind or "").lower() in CLOUDFLARE_INPAINTING_KINDS]
        others = [p for p in ordered if p not in inpaint]
        return inpaint + others
    return ordered


def _cloudflare_providers(env: Optional[Dict[str, str]]) -> List[ImageProviderConfig]:
    providers: List[ImageProviderConfig] = []
    global_model = (
        _env_value(env, "BUTI_AI_CLOUDFLARE_MODEL")
        or _env_value(env, "CLOUDFLARE_MODEL")
        or DEFAULT_CLOUDFLARE_MODEL
    )
    for index in range(1, 4):
        token = _env_value(env, f"BUTI_AI_CLOUDFLARE_API_TOKEN_{index}") or _env_value(env, f"CLOUDFLARE_API_TOKEN_{index}")
        account_id = _env_value(env, f"BUTI_AI_CLOUDFLARE_ACCOUNT_ID_{index}") or _env_value(env, f"CLOUDFLARE_ACCOUNT_ID_{index}")
        if not token or not account_id:
            continue
        model = (
            _env_value(env, f"BUTI_AI_CLOUDFLARE_MODEL_{index}")
            or _env_value(env, f"CLOUDFLARE_MODEL_{index}")
            or global_model
        )
        endpoint = f"https://api.cloudflare.com/client/v4/accounts/{account_id}/ai/run/{model}"
        providers.append(
            ImageProviderConfig(
                id=f"cloudflare_{index}",
                label=f"Cloudflare {index}",
                kind=_cloudflare_kind_for_model(model, "cloudflare"),
                endpoint=endpoint,
                model=model,
                api_key=token,
                extra={
                    "account_index": index,
                    "guidance": _env_value(env, "BUTI_AI_CLOUDFLARE_GUIDANCE") or _env_value(env, "CLOUDFLARE_GUIDANCE") or "5",
                },
            )
        )
    return providers


def _resolve_api_key(raw: Dict[str, Any], env: Optional[Dict[str, str]], prefix: str = "") -> str:
    key_env = str(raw.get("api_key_env") or raw.get("key_env") or "").strip()
    if key_env:
        return _env_value(env, key_env)
    if prefix:
        pref_env = _env_value(env, f"{prefix}_KEY_ENV")
        if pref_env:
            return _env_value(env, pref_env)
        return _env_value(env, f"{prefix}_KEY")
    return str(raw.get("api_key") or raw.get("key") or "").strip()


def _normal_headers(value: Any) -> Dict[str, str]:
    if not isinstance(value, dict):
        return {}
    headers: Dict[str, str] = {}
    for key, val in value.items():
        k = str(key or "").strip()
        v = str(val or "").strip()
        if k and v:
            headers[k] = v
    return headers


def _json_configured_providers(env: Optional[Dict[str, str]]) -> List[ImageProviderConfig]:
    raw = _env_value(env, "BUTI_AI_IMAGE_PROVIDERS")
    if not raw:
        return []
    try:
        data = json.loads(raw)
    except Exception as exc:
        logger.warning("Invalid BUTI_AI_IMAGE_PROVIDERS JSON: %s", str(exc)[:120])
        return []
    if not isinstance(data, list):
        return []

    providers: List[ImageProviderConfig] = []
    for idx, item in enumerate(data, start=1):
        if not isinstance(item, dict) or item.get("enabled") is False:
            continue
        endpoint = str(item.get("endpoint") or item.get("url") or "").strip()
        if not endpoint:
            continue
        kind = str(item.get("kind") or item.get("format") or "openai_image_edit").strip().lower()
        provider_id = str(item.get("id") or item.get("name") or f"json_model_{idx}").strip().lower()
        provider_id = re.sub(r"[^a-z0-9_\-]+", "_", provider_id)[:64] or f"json_model_{idx}"
        api_key = _resolve_api_key(item, env)
        if not api_key and not _truthy(item.get("allow_no_auth")):
            continue
        providers.append(
            ImageProviderConfig(
                id=provider_id,
                label=str(item.get("label") or item.get("name") or provider_id).strip()[:80] or provider_id,
                kind=kind,
                endpoint=endpoint,
                model=str(item.get("model") or "").strip(),
                api_key=api_key,
                headers=_normal_headers(item.get("headers")),
                extra={k: v for k, v in item.items() if k not in {"api_key", "key", "headers"}},
            )
        )
    return providers


def _numbered_model_providers(env: Optional[Dict[str, str]]) -> List[ImageProviderConfig]:
    providers: List[ImageProviderConfig] = []
    for index in range(1, 4):
        prefix = f"BUTI_AI_IMAGE_MODEL_{index}"
        endpoint = _env_value(env, f"{prefix}_URL") or _env_value(env, f"{prefix}_ENDPOINT")
        if not endpoint:
            continue
        api_key = _resolve_api_key({}, env, prefix=prefix)
        allow_no_auth = _truthy(_env_value(env, f"{prefix}_ALLOW_NO_AUTH"))
        if not api_key and not allow_no_auth:
            continue
        kind = (_env_value(env, f"{prefix}_KIND") or "openai_image_edit").lower()
        model = _env_value(env, f"{prefix}_MODEL")
        provider_id = (_env_value(env, f"{prefix}_ID") or f"image_model_{index}").lower()
        provider_id = re.sub(r"[^a-z0-9_\-]+", "_", provider_id)[:64] or f"image_model_{index}"
        providers.append(
            ImageProviderConfig(
                id=provider_id,
                label=_env_value(env, f"{prefix}_LABEL") or f"Image Model {index}",
                kind=kind,
                endpoint=endpoint,
                model=model,
                api_key=api_key,
                extra={
                    "size": _env_value(env, f"{prefix}_SIZE"),
                    "response_format": _env_value(env, f"{prefix}_RESPONSE_FORMAT"),
                },
            )
        )
    return providers


def _ai_management_providers(service_key: str = "eyebrow") -> List[ImageProviderConfig]:
    """خواندن مدل‌های تصویرسازی آینه گیسو از مدیریت AI سوپرادمین."""
    try:
        from giso.buti_ai.ai_models import configured_image_provider_dicts
    except Exception as exc:
        logger.debug("Buti AI management image providers unavailable: %s", exc)
        return []
    providers: List[ImageProviderConfig] = []
    try:
        configured_items = configured_image_provider_dicts(limit=3, service_key=service_key or "eyebrow")
    except TypeError:
        # Backward-compatible for tests/older monkeypatches that only accepted limit.
        configured_items = configured_image_provider_dicts(limit=3)
    for item in configured_items:
        try:
            providers.append(
                ImageProviderConfig(
                    id=str(item.get("id") or "ai_mirror_image"),
                    label=str(item.get("label") or item.get("id") or "AI Management"),
                    kind=str(item.get("kind") or "openai_image_edit"),
                    endpoint=str(item.get("endpoint") or ""),
                    model=str(item.get("model") or ""),
                    api_key=str(item.get("api_key") or ""),
                    headers=_normal_headers(item.get("headers")),
                    extra=item.get("extra") if isinstance(item.get("extra"), dict) else {},
                )
            )
        except Exception:
            continue
    return [p for p in providers if p.endpoint and (p.api_key or _truthy(p.extra.get("allow_no_auth")))]


def configured_image_providers(env: Optional[Dict[str, str]] = None, service_key: str = "eyebrow") -> List[ImageProviderConfig]:
    """برگرداندن providerهای تصویرسازی فعال؛ بدون لو دادن کلیدها.

    در اجرای واقعی (`env is None`) اول تنظیمات پنل «مدیریت AI» خوانده می‌شود.
    در تست‌ها/فراخوانی‌های env-محور، رفتار قدیمی ثابت می‌ماند.
    """
    providers: List[ImageProviderConfig] = []
    if env is None:
        providers.extend(_ai_management_providers(service_key=service_key or "eyebrow"))
    providers.extend(_cloudflare_providers(env))
    providers.extend(_numbered_model_providers(env))
    providers.extend(_json_configured_providers(env))
    return _provider_order(providers, env)


def _mime_for_path(path: str) -> str:
    mime, _ = mimetypes.guess_type(path)
    return mime or "image/jpeg"


def _image_bytes_for_provider(path: str, max_side: int = MAX_PROVIDER_INPUT_SIDE, square: bool = False) -> Tuple[bytes, str, str]:
    """کوچک‌سازی امن ورودی برای providerها. در خطا، بایت اصلی برمی‌گردد."""
    original_mime = _mime_for_path(path)
    try:
        from PIL import Image

        image = Image.open(path).convert("RGB")
        if square:
            w, h = image.size
            side = min(w, h)
            left = max(0, int((w - side) / 2))
            top = max(0, int((h - side) / 2))
            image = image.crop((left, top, left + side, top + side))
        image.thumbnail((max_side, max_side))
        out = BytesIO()
        image.save(out, "JPEG", quality=92, optimize=True)
        return out.getvalue(), "image/jpeg", "jpg"
    except Exception:
        with open(path, "rb") as handle:
            data = handle.read()
        extension = os.path.splitext(path)[1].lstrip(".").lower() or "jpg"
        if extension == "jpeg":
            extension = "jpg"
        return data, original_mime, extension


def _output_size_for_cloudflare(path: str) -> Tuple[int, int]:
    try:
        from PIL import Image

        with Image.open(path) as image:
            w, h = image.size
    except Exception:
        w, h = 1024, 1024
    if w <= 0 or h <= 0:
        w, h = 1024, 1024
    try:
        max_side = int(float(_env_value(None, "CLOUDFLARE_IMAGE_OUTPUT_MAX_SIDE") or 1024))
    except Exception:
        max_side = 1024
    max_side = max(512, min(1536, max_side))
    scale = min(1.0, float(max_side) / max(w, h))
    out_w = int(round((w * scale) / 8) * 8)
    out_h = int(round((h * scale) / 8) * 8)
    return max(256, min(max_side, out_w)), max(256, min(max_side, out_h))


def _upload_relative_path(path: str, upload_dir: str = "") -> str:
    try:
        base = os.path.abspath(upload_dir or final_design.EYEBROW_UPLOAD_DIR)
        absolute = os.path.abspath(str(path or ""))
        if absolute.startswith(base + os.sep):
            return os.path.relpath(absolute, base).replace(os.sep, "/")
    except Exception:
        pass
    return ""


def _reference_image_path(candidate: Dict[str, Any]) -> str:
    style = normalize_style_key((candidate or {}).get("final_style"))
    base = os.path.abspath(os.path.join(os.path.dirname(os.path.dirname(__file__)), "static", "brows"))
    # اول PNG شفاف (بدون پس‌زمینه) برای تشخیص بهتر هوش مصنوعی، بعد JPG
    for ext in (".png", ".jpg", ".webp"):
        path = os.path.abspath(os.path.join(base, f"{style}{ext}"))
        if path.startswith(base + os.sep) and os.path.exists(path):
            return path
    return ""


def _authorization_headers(provider: ImageProviderConfig) -> Dict[str, str]:
    headers = dict(provider.headers or {})
    if provider.api_key and not any(k.lower() == "authorization" for k in headers):
        headers["Authorization"] = f"Bearer {provider.api_key}"
    return headers


def _extract_api_error(payload: Any, raw: str = "") -> str:
    try:
        if isinstance(payload, dict):
            errors = payload.get("errors")
            if isinstance(errors, list) and errors:
                first = errors[0]
                if isinstance(first, dict):
                    return str(first.get("message") or first.get("code") or first)[:300]
                return str(first)[:300]
            error = payload.get("error")
            if isinstance(error, str):
                return error[:300]
            if isinstance(error, dict):
                return str(error.get("message") or error.get("detail") or error)[:300]
            for key in ("message", "detail"):
                if isinstance(payload.get(key), str):
                    return str(payload[key])[:300]
    except Exception:
        pass
    return (raw or "").strip()[:300]


def _looks_like_base64(text: str) -> bool:
    compact = text.strip()
    if len(compact) < 80:
        return False
    return re.fullmatch(r"[A-Za-z0-9+/=\s]+", compact) is not None


def _post_request(url: str, disable_env_proxy: bool = False, **kwargs) -> requests.Response:
    """POST helper; Cloudflare image calls should not inherit broken system proxies."""
    if disable_env_proxy and getattr(requests.post, "__module__", "").startswith("requests"):
        session = requests.Session()
        session.trust_env = False
        try:
            return session.post(url, **kwargs)
        finally:
            session.close()
    return requests.post(url, **kwargs)


def _extract_image_value(value: Any, depth: int = 0) -> Optional[str]:
    """استخراج تصویر از پاسخ‌های رایج: data URI، url، b64_json، result.image."""
    if depth > 5 or value is None:
        return None
    if isinstance(value, str):
        text = value.strip()
        if text.startswith("data:image/") or text.startswith("http://") or text.startswith("https://"):
            return text
        if _looks_like_base64(text):
            return text
        return None
    if isinstance(value, list):
        for item in value:
            found = _extract_image_value(item, depth + 1)
            if found:
                return found
        return None
    if isinstance(value, dict):
        priority_keys = (
            "image",
            "resultUrl",
            "result_url",
            "url",
            "b64_json",
            "base64",
            "data_uri",
            "dataUri",
            "output",
            "result",
            "data",
            "images",
        )
        for key in priority_keys:
            if key in value:
                found = _extract_image_value(value.get(key), depth + 1)
                if found:
                    return found
        for item in value.values():
            found = _extract_image_value(item, depth + 1)
            if found:
                return found
    return None


def _parse_response_image(response: requests.Response) -> str:
    content_type = (response.headers.get("content-type") or "").split(";")[0].strip().lower()
    raw_text = ""
    payload: Any = None
    # [09] پاسخ Provider - اولیه
    try:
        _status = response.status_code
        _ctype = content_type
        _size = len(response.content or b"")
        _trace_log("09", "provider_response", http_status=_status, content_type=_ctype,
                   response_size=_size, endpoint_host=_safe_host(response.url))
    except Exception:
        pass

    if content_type.startswith("image/"):
        data = response.content or b""
        if not data:
            _trace_log("09", "provider_error", error_type="empty_image", http_status=response.status_code)
            raise ImageProviderError("پاسخ تصویر خالی بود")
        _trace_log("09", "provider_image_direct", content_type=content_type, size=len(data), output_type="image/*")
        return "data:%s;base64,%s" % (content_type, base64.b64encode(data).decode("ascii"))

    try:
        raw_text = response.text or ""
    except Exception:
        raw_text = ""
    try:
        payload = response.json()
    except Exception:
        payload = None

    if not response.ok:
        _err = _extract_api_error(payload, raw_text) or f"HTTP {response.status_code}"
        _trace_log("09", "provider_error", error_type="http_error", http_status=response.status_code,
                   error_message=_err[:200])
        raise ImageProviderError(_err)

    if payload is not None:
        found = _extract_image_value(payload)
        if found:
            _out_type = "data_uri" if str(found).startswith("data:") else ("url" if str(found).startswith("http") else "base64")
            _trace_log("09", "provider_response_parsed", output_type=_out_type,
                       found_length=len(str(found)), content_type=content_type)
            return found
    if raw_text.startswith("data:image/") or raw_text.startswith("http") or _looks_like_base64(raw_text):
        _trace_log("09", "provider_response_raw", output_type="raw_text", length=len(raw_text))
        return raw_text.strip()
    _trace_log("09", "provider_error", error_type="no_image_found", http_status=response.status_code)
    raise ImageProviderError("پاسخ موفق بود اما تصویر خروجی پیدا نشد")


def _call_cloudflare(provider: ImageProviderConfig, source_path: str, reference_path: str, prompt: str, timeout: int) -> str:
    model_name = str(provider.model or "").strip()
    if model_name == CLOUDFLARE_INPAINTING_MODEL:
        raise ImageProviderError(
            "این مدل باید با kind=cloudflare_inpainting استفاده شود؛ "
            "در مدیریت AI نوع را inpainting بگذار یا از flux-2-klein-4b استفاده کن."
        )
    if model_name != DEFAULT_CLOUDFLARE_MODEL:
        _beauty_log("[AI]", "cloudflare_model_not_default", model=model_name, expected=DEFAULT_CLOUDFLARE_MODEL)
    width, height = _output_size_for_cloudflare(source_path)
    photo_bytes, photo_mime, photo_ext = _image_bytes_for_provider(source_path, MAX_PROVIDER_INPUT_SIDE, square=False)
    files = {
        "input_image_0": (f"customer-face.{photo_ext}", photo_bytes, photo_mime),
    }
    # Reference Image: PNG های مرجع پس‌زمینه سفید دارند (254,254,255) و باعث ابرو سفید می‌شدند
    # برای flux-2-klein-4b که text-to-image است، فرستادن reference سفید = تولید ابرو سفید/هاله سفید
    # پس پیش‌فرض را False می‌کنیم تا فقط چهره مشتری فرستاده شود و ابرو از prompt ساخته شود
    # اگر کاربر واقعاً بخواهد reference بفرستد، باید CLOUDFLARE_SEND_REFERENCE_IMAGE=1 بگذارد
    send_reference = False
    if _env_value(None, "CLOUDFLARE_SEND_REFERENCE_IMAGE") == "1":
        send_reference = True
    if provider.extra.get("send_reference_image") is True:
        send_reference = True
    # فقط JPG بفرست که پس‌زمینه پوست دارد، نه PNG سفید
    if reference_path and send_reference:
        # اگر PNG سفید است، نفرست
        if str(reference_path).lower().endswith(".png"):
            # PNG های فعلی پس‌زمینه سفید دارند، برای جلوگیری از ابرو سفید نفرست
            send_reference = False
        else:
            try:
                ref_bytes, ref_mime, ref_ext = _image_bytes_for_provider(reference_path, MAX_PROVIDER_INPUT_SIDE, square=True)
                files["input_image_1"] = (f"technique-macro.{ref_ext}", ref_bytes, ref_mime)
            except Exception:
                send_reference = False

    guidance = str(provider.extra.get("guidance") or _env_value(None, "CLOUDFLARE_GUIDANCE") or "5")
    data = {
        "prompt": (
            f"{prompt} ROLE: IMAGE 0 is the customer-face authority and must be kept 100% identical except eyebrows; "
            "IMAGE 1 if present is ONLY a technique swatch showing eyebrow style, never a face source, never use its background, face, or skin. "
            "Do NOT create white background, white halo, or new face."
        ),
        "negative_prompt": (
            "new face, changed identity, changed eyes, changed eyelids, changed eyelashes, red streak, white overlay, white halo, white background, "
            "transparent background, cutout face, face cutout, eye artifact, forehead artifact, skin retouching, hair change, hijab change, background change, "
            "makeup change outside eyebrows, distorted face, cartoon, illustration, blurry, low quality, white border around face"
        ),
        "guidance": guidance,
        "width": str(width),
        "height": str(height),
    }
    provider.extra["_last_request_meta"] = {
        "reference_image_sent": bool(reference_path and send_reference),
        "cloudflare_request_format": "multipart_prompt_input_image_0",
        "cloudflare_output_width": width,
        "cloudflare_output_height": height,
    }
    # [07] قبل از ارسال به مدل
    _trace_log("07", "before_request_flux", provider_id=provider.id, model=provider.model,
               route="_call_cloudflare", input_image_size=f"{len(photo_bytes)} bytes",
               input_image_mime=photo_mime, mask_size="no mask (flux)", mask_coverage="N/A",
               guidance=guidance, prompt_length=len(prompt or ""), negative_prompt_length=len(data.get("negative_prompt") or ""),
               mask_in_request=False, request_format="multipart", reference_image_used=bool(reference_path and send_reference))
    # [08] ارسال Request
    _trace_log("08", "sending_request", provider_id=provider.id, model=provider.model,
               endpoint_host=_safe_host(provider.endpoint), http_method="POST",
               request_format="multipart", image_field="input_image_0", mask_field="none",
               image_sent=True, mask_sent=False, start_time=str(time.time()))

    response = _post_request(
        provider.endpoint,
        disable_env_proxy=True,
        headers=_authorization_headers(provider),
        data=data,
        files=files,
        timeout=timeout,
    )
    return _parse_response_image(response)


def _dimension_for_model(value: int) -> int:
    value = int(round(float(value or 0) / 8.0) * 8)
    return max(256, min(2048, value or 512))


def _prepare_cloudflare_inpainting_assets(source_path: str, mask_path: str) -> Tuple[bytes, bytes, int, int, int, float]:
    """ساخت image/mask هم‌اندازه برای Cloudflare inpainting.

    طبق نمونه رسمی Workers AI برای مدل inpainting، `image` و `mask` آرایه‌ای از
    byteهای فایل هستند؛ بنابراین هر دو را به PNG هم‌اندازه تبدیل می‌کنیم و بعد
    byte array می‌فرستیم، نه multipart و نه فیلد حدسی mask_image/input_mask.
    """
    try:
        from PIL import Image
    except Exception as exc:
        raise ImageProviderError("کتابخانه پردازش تصویر برای ساخت mask در دسترس نیست") from exc

    try:
        image = Image.open(source_path).convert("RGB")
        mask = Image.open(mask_path).convert("L")
    except Exception as exc:
        raise ImageProviderError("عکس یا mask ابرو برای inpainting قابل خواندن نیست") from exc

    if mask.size != image.size:
        mask = mask.resize(image.size, Image.Resampling.NEAREST if hasattr(Image, "Resampling") else Image.NEAREST)

    width, height = image.size
    if width <= 0 or height <= 0:
        raise ImageProviderError("ابعاد عکس برای inpainting نامعتبر است")

    scale = min(1.0, float(MAX_INPAINTING_INPUT_SIDE) / float(max(width, height)))
    if min(width, height) * scale < 256:
        scale = max(scale, 256.0 / float(max(1, min(width, height))))
    new_w = _dimension_for_model(width * scale)
    new_h = _dimension_for_model(height * scale)
    if (new_w, new_h) != (width, height):
        image = image.resize((new_w, new_h), Image.Resampling.LANCZOS if hasattr(Image, "Resampling") else Image.LANCZOS)
        mask = mask.resize((new_w, new_h), Image.Resampling.NEAREST if hasattr(Image, "Resampling") else Image.NEAREST)
    # Ensure binary mask – no blur/feather for inpainting guarantee (step 6)
    mask = mask.point(lambda px: 255 if int(px) >= 128 else 0)
    mask_pixels = sum(1 for px in mask.getdata() if px > 0)
    total_pixels = max(1, new_w * new_h)
    coverage = float(mask_pixels) / float(total_pixels)
    if mask_pixels <= 0:
        raise ImageProviderError("mask واقعی ابرو خالی است؛ inpainting متوقف شد")
    # Increased from 0.12 to 0.18 for Design Region (larger than old tight mask)
    if coverage > MAX_INPAINTING_COVERAGE_RATIO:
        raise ImageProviderError(f"mask ابرو بیش از حد وسیع است ({coverage:.3f} > {MAX_INPAINTING_COVERAGE_RATIO})؛ برای حفظ صورت inpainting متوقف شد")

    image_out = BytesIO()
    mask_out = BytesIO()
    image.save(image_out, "PNG", optimize=True)
    mask.save(mask_out, "PNG", optimize=True)
    return image_out.getvalue(), mask_out.getvalue(), int(new_w), int(new_h), int(mask_pixels), round(coverage, 6)


def _real_eyebrow_mask_for_candidate(source_path: str, candidate: Dict[str, Any]) -> Tuple[Dict[str, Any], str]:
    detection = candidate.get("eyebrow_detection") if isinstance(candidate.get("eyebrow_detection"), dict) else {}
    # Resolve style for design region
    try:
        from giso.buti_ai.eyebrow.options import normalize_style_key
        style_key = normalize_style_key(candidate.get("final_style") or candidate.get("selected_style") or "giso_suggested")
    except Exception:
        style_key = str(candidate.get("final_style") or "giso_suggested").strip().lower() or "giso_suggested"

    if not detection or not detection.get("regions"):
        detection = final_design.ensure_eyebrow_detection(candidate, style_key=style_key)
    if detection and detection.get("regions"):
        detection = ensure_eyebrow_mask(source_path, detection, style_key=style_key, design_mode=True)
        candidate["eyebrow_detection"] = detection
    mask = detection.get("mask") if isinstance(detection, dict) and isinstance(detection.get("mask"), dict) else {}
    mask_path = str(mask.get("path") or detection.get("mask_path") or "").strip() if isinstance(detection, dict) else ""
    if not mask.get("ok") or not mask_path or not os.path.exists(mask_path):
        raise ImageProviderError("برای Cloudflare Inpainting، mask واقعی ابرو در دسترس نیست")
    if mask.get("is_fallback") or mask.get("real_mask") is False or str(detection.get("method") or "") == "proportional_fallback":
        raise ImageProviderError("mask نسبتی/fallback برای AI Inpainting واقعی استفاده نمی‌شود")
    if detection.get("plausible") is False:
        raise ImageProviderError("mask ابرو از نظر هندسی نامعتبر است")
    return detection, mask_path


def _call_cloudflare_inpainting(provider: ImageProviderConfig, source_path: str, candidate: Dict[str, Any], prompt: str, timeout: int) -> str:
    detection, mask_path = _real_eyebrow_mask_for_candidate(source_path, candidate)
    image_bytes, mask_bytes, width, height, mask_pixels, coverage = _prepare_cloudflare_inpainting_assets(source_path, mask_path)
    guidance = float(provider.extra.get("guidance") or _env_value(None, "CLOUDFLARE_INPAINTING_GUIDANCE") or 7.5)
    # شدت تغییر را به change_key وصل کن – increased for real redesign
    try:
        from giso.buti_ai.eyebrow.options import normalize_change_level
        change_key = normalize_change_level((candidate or {}).get("change_key"))
        if change_key == "very_natural":
            default_strength = 0.62
        elif change_key == "medium":
            default_strength = 0.75
        elif change_key == "clear":
            default_strength = 0.88
        else:
            default_strength = 0.75
    except Exception:
        default_strength = 0.75
    strength = float(provider.extra.get("strength") or _env_value(None, "CLOUDFLARE_INPAINTING_STRENGTH") or default_strength)
    try:
        num_steps = int(provider.extra.get("num_steps") or _env_value(None, "CLOUDFLARE_INPAINTING_STEPS") or 20)
    except Exception:
        num_steps = 20
    num_steps = max(1, min(20, num_steps))
    payload = {
        "prompt": (
            f"{prompt} Apply the selected eyebrow design only inside the uploaded inpainting mask. "
            f"Mask polarity: {MASK_POLARITY}; white pixels are editable eyebrow pixels, black pixels must remain unchanged."
        ),
        "negative_prompt": (
            "new face, changed identity, changed eyes, changed eyelids, changed eyelashes, skin retouching, "
            "hair change, background change, makeup change outside eyebrows, distorted face, cartoon, illustration"
        ),
        "image": list(image_bytes),
        "mask": list(mask_bytes),
        "width": width,
        "height": height,
        "num_steps": num_steps,
        "strength": max(0.05, min(1.0, strength)),
        "guidance": guidance,
    }
    provider.extra["_last_request_meta"] = {
        "ai_inpainting": True,
        "mask_used": True,
        "mask_width": width,
        "mask_height": height,
        "mask_pixels": mask_pixels,
        "mask_coverage_ratio": coverage,
        "mask_polarity": MASK_POLARITY,
        "mask_source_method": detection.get("method"),
        "mask_filename": _upload_relative_path(mask_path),
        "reference_image_sent": False,
        "cloudflare_request_format": "json_image_and_mask_byte_arrays",
    }
    # [07] قبل از ارسال - inpainting واقعی
    _trace_log("07", "before_request_inpainting", provider_id=provider.id, model=provider.model,
               route="_call_cloudflare_inpainting", input_image_size=f"{len(image_bytes)} bytes",
               mask_size=f"{width}x{height}", mask_pixels=mask_pixels, mask_coverage=coverage,
               mask_polarity=MASK_POLARITY, strength=strength, guidance=guidance, steps=num_steps,
               prompt_length=len(prompt or ""), negative_prompt_length=len(payload.get("negative_prompt") or ""),
               mask_in_request=True, request_format="json_image_and_mask_byte_arrays",
               image_format="PNG byte array", mask_format="PNG L 255 white edit 0 black keep")
    # [08] ارسال Request inpainting
    _trace_log("08", "sending_request", provider_id=provider.id, model=provider.model,
               endpoint_host=_safe_host(provider.endpoint), http_method="POST",
               request_format="json", image_field="image", mask_field="mask",
               image_sent=True, mask_sent=True, start_time=str(time.time()),
               width=width, height=height)

    response = _post_request(
        provider.endpoint,
        disable_env_proxy=True,
        headers={**_authorization_headers(provider), "Content-Type": "application/json"},
        json=payload,
        timeout=timeout,
    )
    return _parse_response_image(response)


def _call_openai_image_edit(provider: ImageProviderConfig, source_path: str, prompt: str, timeout: int) -> str:
    photo_bytes, photo_mime, photo_ext = _image_bytes_for_provider(source_path, 1024, square=False)
    data = {
        "prompt": prompt,
        "n": "1",
    }
    if provider.model:
        data["model"] = provider.model
    size = str(provider.extra.get("size") or "").strip()
    if size:
        data["size"] = size
    response_format = str(provider.extra.get("response_format") or "b64_json").strip()
    if response_format:
        data["response_format"] = response_format

    response = requests.post(
        provider.endpoint,
        headers=_authorization_headers(provider),
        data=data,
        files={"image": (f"customer-face.{photo_ext}", photo_bytes, photo_mime)},
        timeout=timeout,
    )
    return _parse_response_image(response)


def _call_generic_multipart(provider: ImageProviderConfig, source_path: str, reference_path: str, prompt: str, timeout: int) -> str:
    photo_bytes, photo_mime, photo_ext = _image_bytes_for_provider(source_path, 1024, square=False)
    files = {"image": (f"customer-face.{photo_ext}", photo_bytes, photo_mime)}
    if reference_path:
        ref_bytes, ref_mime, ref_ext = _image_bytes_for_provider(reference_path, MAX_PROVIDER_INPUT_SIDE, square=True)
        files["reference_image"] = (f"reference.{ref_ext}", ref_bytes, ref_mime)
    data = {"prompt": prompt, "service": "eyebrow"}
    if provider.model:
        data["model"] = provider.model
    response = requests.post(
        provider.endpoint,
        headers=_authorization_headers(provider),
        data=data,
        files=files,
        timeout=timeout,
    )
    return _parse_response_image(response)


def _data_uri_for_path(path: str, max_side: int = 1024) -> str:
    data, mime, _ = _image_bytes_for_provider(path, max_side, square=False)
    return "data:%s;base64,%s" % (mime, base64.b64encode(data).decode("ascii"))


def _call_json_image(provider: ImageProviderConfig, source_path: str, reference_path: str, candidate: Dict[str, Any], prompt: str, timeout: int) -> str:
    payload: Dict[str, Any] = {
        "prompt": prompt,
        "service": "eyebrows",
        "styleKey": normalize_style_key(candidate.get("final_style")),
        "style": candidate.get("final_label") or "",
        "eyebrowRegions": (candidate.get("eyebrow_detection") or {}).get("regions") if isinstance(candidate.get("eyebrow_detection"), dict) else [],
        "imageBase64": _data_uri_for_path(source_path, max_side=1024),
    }
    if reference_path:
        payload["referenceImageBase64"] = _data_uri_for_path(reference_path, max_side=512)
    if provider.model:
        payload["model"] = provider.model
    response = requests.post(
        provider.endpoint,
        headers={**_authorization_headers(provider), "Content-Type": "application/json"},
        json=payload,
        timeout=timeout,
    )
    return _parse_response_image(response)


def _call_provider(provider: ImageProviderConfig, source_path: str, reference_path: str, candidate: Dict[str, Any], prompt: str, timeout: int) -> str:
    kind = _cloudflare_kind_for_model(provider.model, provider.kind) if (provider.kind or "").strip().lower().startswith("cloudflare") else (provider.kind or "").strip().lower()
    provider.kind = kind
    provider.extra.pop("_last_request_meta", None)
    # [06] انتخاب Route
    _is_inpaint = kind in CLOUDFLARE_INPAINTING_KINDS
    _trace_log("06", "route_selection", provider_id=provider.id, model=provider.model,
               configured_kind=provider.kind, resolved_kind=kind,
               route=("inpainting" if _is_inpaint else kind),
               mask_required=_is_inpaint, mask_used=_is_inpaint or bool(candidate.get("eyebrow_detection")),
               reference_image_used=bool(reference_path), image_edit=(kind in {"openai_image_edit"}), inpainting=_is_inpaint)

    if kind == "cloudflare":
        _trace_log("06", "ROUTE= _call_cloudflare", provider_id=provider.id, model=provider.model)
        return _call_cloudflare(provider, source_path, reference_path, prompt, timeout)
    if kind in CLOUDFLARE_INPAINTING_KINDS:
        _trace_log("06", "ROUTE= _call_cloudflare_inpainting", provider_id=provider.id, model=provider.model)
        return _call_cloudflare_inpainting(provider, source_path, candidate, prompt, timeout)
    if kind in {"openai_image_edit", "openai_edit", "images_edit"}:
        _trace_log("06", "ROUTE= _call_openai_image_edit", provider_id=provider.id, model=provider.model)
        return _call_openai_image_edit(provider, source_path, prompt, timeout)
    if kind in {"multipart", "form", "form_data"}:
        _trace_log("06", "ROUTE= _call_generic_multipart", provider_id=provider.id, model=provider.model)
        return _call_generic_multipart(provider, source_path, reference_path, prompt, timeout)
    if kind in {"json", "json_image", "data_uri"}:
        _trace_log("06", "ROUTE= _call_json_image", provider_id=provider.id, model=provider.model)
        return _call_json_image(provider, source_path, reference_path, candidate, prompt, timeout)
    raise ImageProviderError(f"نوع provider پشتیبانی نمی‌شود: {kind or 'unknown'}")


def _decode_image_value(image_value: str, timeout: int) -> Tuple[bytes, str]:
    value = (image_value or "").strip()
    if value.startswith("data:image/"):
        match = re.match(r"^data:([^;]+);base64,(.+)$", value, flags=re.S)
        if not match:
            raise ImageProviderError("data URI تصویر نامعتبر است")
        return base64.b64decode(match.group(2), validate=False), match.group(1)
    if value.startswith("http://") or value.startswith("https://"):
        response = requests.get(value, timeout=min(timeout, 30), stream=True)
        if not response.ok:
            raise ImageProviderError(f"دانلود خروجی provider ناموفق بود: HTTP {response.status_code}")
        chunks = []
        total = 0
        for chunk in response.iter_content(chunk_size=65536):
            if not chunk:
                continue
            total += len(chunk)
            if total > MAX_DOWNLOAD_BYTES:
                raise ImageProviderError("حجم خروجی provider بیش از حد مجاز است")
            chunks.append(chunk)
        mime = (response.headers.get("content-type") or "image/jpeg").split(";")[0].strip()
        return b"".join(chunks), mime
    if _looks_like_base64(value):
        return base64.b64decode(value, validate=False), "image/png"
    raise ImageProviderError("فرمت خروجی provider قابل خواندن نیست")


def _provider_eyebrow_mask_for_save(source_path: str, candidate: Dict[str, Any], size: Tuple[int, int], for_composite: bool = False):
    """Return a resized eyebrow-only real mask so provider output cannot alter eyes/lashes.

    for_composite=False: binary mask 0/255 with NEAREST resize – for inpainting guarantee (step 6)
    for_composite=True: slight feathered mask for final composite if needed, but still binary core
    """
    try:
        from PIL import Image, ImageFilter
    except Exception as exc:
        raise ImageProviderError("برای محدودکردن خروجی AI به ابرو، Pillow لازم است") from exc

    # Resolve style for design region
    try:
        from giso.buti_ai.eyebrow.options import normalize_style_key
        style_key = normalize_style_key(candidate.get("final_style") or candidate.get("selected_style") or "giso_suggested")
    except Exception:
        style_key = str(candidate.get("final_style") or "giso_suggested").strip().lower() or "giso_suggested"

    detection = candidate.get("eyebrow_detection") if isinstance(candidate.get("eyebrow_detection"), dict) else {}
    if not detection or not detection.get("regions"):
        detection = final_design.ensure_eyebrow_detection(candidate, style_key=style_key)
    if not detection or not detection.get("regions"):
        raise ImageProviderError("خروجی AI پذیرفته نشد؛ محدوده واقعی دو ابرو روی عکس تشخیص داده نشد")
    if detection and detection.get("regions"):
        # Rebuild with design region and current style
        detection = ensure_eyebrow_mask(source_path, detection, style_key=style_key, design_mode=True)
        candidate["eyebrow_detection"] = detection
    mask_info = detection.get("mask") if isinstance(detection, dict) and isinstance(detection.get("mask"), dict) else {}
    mask_path = str(mask_info.get("path") or detection.get("mask_path") or "").strip() if isinstance(detection, dict) else ""
    if not mask_info.get("ok") or not mask_path or not os.path.exists(mask_path):
        raise ImageProviderError("خروجی AI ذخیره نشد؛ mask ابرو برای حفظ چشم/مژه ساخته نشد")
    if mask_info.get("is_fallback") or mask_info.get("real_mask") is False or bool(detection.get("is_fallback")):
        raise ImageProviderError("خروجی AI پذیرفته نشد؛ mask fallback/نسبتی برای ادعای AI واقعی استفاده نمی‌شود")
    if detection.get("plausible") is False:
        raise ImageProviderError("خروجی AI پذیرفته نشد؛ محدوده ابرو از نظر هندسی نامعتبر است")
    try:
        coverage = float(mask_info.get("coverage_ratio") or 0)
    except Exception:
        coverage = 0.0
    # Updated coverage for Design Region: old tight 0.045, new design up to 0.095
    if coverage <= 0 or coverage > MAX_DESIGN_COVERAGE_RATIO:
        # Allow slightly larger for powder/combination
        if coverage > 0.12:
            raise ImageProviderError(f"mask ابرو برای ذخیره خروجی AI ایمن نیست؛ coverage {coverage:.4f} > {MAX_DESIGN_COVERAGE_RATIO} بیش از حد وسیع")
    # بررسی اینکه mask به لبه تصویر نچسبیده باشد – بازه بازتر برای design region
    try:
        regions = detection.get("regions") if isinstance(detection, dict) else []
        is_precise_mask = any(
            "precise" in str((r or {}).get("polygon_source") or "") or "tight" in str((r or {}).get("polygon_source") or "") or "design" in str((r or {}).get("polygon_source") or "")
            for r in (regions or [])
        )
        max_h_ratio = 0.40 if is_precise_mask else 0.32
        max_w_ratio = 0.52 if is_precise_mask else 0.48
        for r in (regions or [])[:2]:
            x = float(r.get("x") or 0)
            y = float(r.get("y") or 0)
            w = float(r.get("width") or 0)
            h = float(r.get("height") or 0)
            if w > size[0] * max_w_ratio or h > size[1] * max_h_ratio:
                raise ImageProviderError("mask ابرو بیش از حد بزرگ است؛ احتمال تشخیص اشتباه حجاب")
            if x < size[0] * 0.005 or (x + w) > size[0] * 0.995:
                raise ImageProviderError("mask ابرو به لبه تصویر چسبیده؛ نامعتبر")
            min_y_ratio = 0.04 if is_precise_mask else 0.06
            max_y_ratio_check = 0.65 if is_precise_mask else 0.62
            if y < size[1] * min_y_ratio or y > size[1] * max_y_ratio_check:
                raise ImageProviderError("mask ابرو خارج از محدوده معقول صورت است")
    except ImageProviderError:
        raise
    except Exception:
        pass
    try:
        # Step 6: Mask اصلی باید binary باشد، Blur نکن، Feather نکن، Resize با NEAREST
        if for_composite:
            # For composite we may want slight feather, but still keep binary core
            # Use NEAREST for resize to avoid gray edges, then optional tiny blur for natural edge
            mask = Image.open(mask_path).convert("L").resize(size, Image.Resampling.NEAREST if hasattr(Image, "Resampling") else Image.NEAREST)
            mask = mask.point(lambda px: 255 if int(px) >= 128 else 0)
            # No MaxFilter for binary guarantee, only optional 0.5 blur for natural transition if needed
            # But per step 9, final composite must be Original outside + AI inside with no outside leak
            # So we keep binary for safety, feather is separate if needed
        else:
            # Inpainting mask – strict binary, NEAREST resize, no blur, no MaxFilter
            mask = Image.open(mask_path).convert("L").resize(size, Image.Resampling.NEAREST if hasattr(Image, "Resampling") else Image.NEAREST)
            mask = mask.point(lambda px: 255 if int(px) >= 128 else 0)

        _beauty_log(
            "[EYEBROW_MASK]",
            "provider_mask_ready",
            method=detection.get("method") if isinstance(detection, dict) else "",
            mask_path=_upload_relative_path(mask_path),
            mask_size=f"{mask.size[0]}x{mask.size[1]}",
            coverage_ratio=coverage,
            real_mask=not bool(mask_info.get("is_fallback")),
            polarity=mask_info.get("polarity") or MASK_POLARITY,
            design_mode=mask_info.get("design_mode"),
            style_key=mask_info.get("style_key"),
            for_composite=for_composite,
        )
        return mask, detection
    except ImageProviderError:
        raise
    except Exception as exc:
        raise ImageProviderError("mask ابرو برای محدودکردن خروجی AI قابل خواندن نیست") from exc

def _fit_provider_image_to_source(image, size: Tuple[int, int]):
    try:
        from PIL import Image, ImageOps
    except Exception:
        return image.resize(size)
    if image.size == size:
        return image
    target_ratio = float(size[0]) / float(max(1, size[1]))
    source_ratio = float(image.size[0]) / float(max(1, image.size[1]))
    resample = Image.Resampling.LANCZOS if hasattr(Image, "Resampling") else Image.LANCZOS
    if abs(target_ratio - source_ratio) <= 0.08:
        return image.resize(size, resample)
    return ImageOps.fit(image, size, method=resample, centering=(0.5, 0.5))


def _pixel_delta_rgb(a: Tuple[int, int, int], b: Tuple[int, int, int]) -> float:
    return (abs(int(a[0]) - int(b[0])) + abs(int(a[1]) - int(b[1])) + abs(int(a[2]) - int(b[2]))) / 3.0


def _percentile(values: List[float], percentile: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = int(round((len(ordered) - 1) * max(0.0, min(1.0, percentile))))
    return float(ordered[index])


def _visible_eyebrow_diff_metrics(base, final_image, mask) -> Dict[str, Any]:
    """Compare original/final, requiring visible change inside the real eyebrow mask only."""
    if base.size != final_image.size:
        final_image = _fit_provider_image_to_source(final_image, base.size).convert("RGB")
    if mask.size != base.size:
        try:
            from PIL import Image
            mask = mask.resize(base.size, Image.Resampling.NEAREST if hasattr(Image, "Resampling") else Image.NEAREST)
        except Exception:
            mask = mask.resize(base.size)
    base = base.convert("RGB")
    final_image = final_image.convert("RGB")
    mask = mask.convert("L")
    width, height = base.size
    total = max(1, width * height)
    stride = max(1, int((float(total) / float(MAX_DIFF_SAMPLE_PIXELS)) ** 0.5))
    inside_deltas: List[float] = []
    outside_deltas: List[float] = []
    changed_inside = 0
    changed_outside = 0
    base_px = base.load()
    final_px = final_image.load()
    mask_px = mask.load()
    for y in range(0, height, stride):
        for x in range(0, width, stride):
            m = int(mask_px[x, y])
            delta = _pixel_delta_rgb(base_px[x, y], final_px[x, y])
            if m >= 128:
                inside_deltas.append(delta)
                if delta >= VISIBLE_EYEBROW_PIXEL_DELTA:
                    changed_inside += 1
            elif m <= 2:
                outside_deltas.append(delta)
                if delta >= VISIBLE_EYEBROW_PIXEL_DELTA:
                    changed_outside += 1
    inside_pixels = len(inside_deltas)
    outside_pixels = len(outside_deltas)
    inside_mean = sum(inside_deltas) / inside_pixels if inside_pixels else 0.0
    outside_mean = sum(outside_deltas) / outside_pixels if outside_pixels else 0.0
    inside_changed_ratio = float(changed_inside) / float(max(1, inside_pixels))
    outside_changed_ratio = float(changed_outside) / float(max(1, outside_pixels))
    # بررسی ماسک سفید: اگر داخل ماسک خیلی سفید باشد، خروجی نامعتبر است (مشکل image-1.png با باکس سفید)
    white_inside = 0
    try:
        final_px_for_white = final_image.load()
        mask_px_for_white = mask.load()
        for y in range(0, height, stride):
            for x in range(0, width, stride):
                if int(mask_px_for_white[x, y]) >= 128:
                    r, g, b = final_px_for_white[x, y]
                    # Detect white / light gray halo – lower threshold to catch 190+ translucent white
                    if r > WHITE_THRESHOLD and g > WHITE_THRESHOLD and b > WHITE_THRESHOLD:
                        if max(r, g, b) - min(r, g, b) < 28:
                            white_inside += 1
                        elif r > 225 and g > 225 and b > 225:
                            white_inside += 1
                    # Also catch very light beige that is not eyebrow (eyebrow should be dark brown/black, brightness < 120)
                    elif (r + g + b) / 3.0 > 185 and max(r, g, b) - min(r, g, b) < 35:
                        # light but not dark brow
                        white_inside += 1
    except Exception:
        white_inside = 0
    white_ratio = float(white_inside) / float(max(1, inside_pixels))
    metrics = {
        "diff_stride": int(stride),
        "inside_mask_sampled_pixels": int(inside_pixels),
        "outside_mask_sampled_pixels": int(outside_pixels),
        "inside_mean_delta": round(float(inside_mean), 4),
        "inside_p95_delta": round(_percentile(inside_deltas, 0.95), 4),
        "inside_changed_ratio": round(float(inside_changed_ratio), 6),
        "inside_white_ratio": round(float(white_ratio), 6),
        "outside_mean_delta": round(float(outside_mean), 4),
        "outside_p99_delta": round(_percentile(outside_deltas, 0.99), 4),
        "outside_changed_ratio": round(float(outside_changed_ratio), 6),
        "visible_change_threshold_delta": VISIBLE_EYEBROW_PIXEL_DELTA,
    }
    visible = (
        inside_pixels > 0
        and (
            inside_mean >= MIN_VISIBLE_EYEBROW_MEAN_DELTA
            or inside_changed_ratio >= MIN_VISIBLE_EYEBROW_CHANGED_RATIO
        )
        and metrics["inside_p95_delta"] >= VISIBLE_EYEBROW_PIXEL_DELTA
        and inside_mean <= MAX_VISIBLE_EYEBROW_MEAN_DELTA
        and white_ratio <= MAX_INSIDE_WHITE_RATIO
    )
    safe_outside = (
        outside_pixels > 0
        and outside_mean <= MAX_OUTSIDE_MASK_MEAN_DELTA
        and metrics["outside_p99_delta"] <= MAX_OUTSIDE_MASK_P99_DELTA
        and outside_changed_ratio <= MAX_OUTSIDE_CHANGED_RATIO
    )
    metrics["eyebrow_roi_changed"] = bool(visible)
    metrics["outside_mask_preserved"] = bool(safe_outside)
    return metrics


def _validate_provider_visible_change(base, final_image, mask) -> Dict[str, Any]:
    metrics = _visible_eyebrow_diff_metrics(base, final_image, mask)
    _beauty_log(
        "[COMPOSITE]",
        "diff_metrics",
        original_size=f"{base.size[0]}x{base.size[1]}",
        final_size=f"{final_image.size[0]}x{final_image.size[1]}",
        mask_size=f"{mask.size[0]}x{mask.size[1]}",
        inside_mean_delta=metrics.get("inside_mean_delta"),
        inside_changed_ratio=metrics.get("inside_changed_ratio"),
        inside_white_ratio=metrics.get("inside_white_ratio"),
        outside_mean_delta=metrics.get("outside_mean_delta"),
        outside_p99_delta=metrics.get("outside_p99_delta"),
        eyebrow_roi_changed=metrics.get("eyebrow_roi_changed"),
        outside_mask_preserved=metrics.get("outside_mask_preserved"),
    )
    if not metrics.get("eyebrow_roi_changed"):
        # اگر سفید زیاد باشد، پیام دقیق‌تر
        if float(metrics.get("inside_white_ratio") or 0) > MAX_INSIDE_WHITE_RATIO:
            raise ImageProviderError("خروجی AI داخل ابرو ماسک سفید تولید کرد و رد شد")
        if float(metrics.get("inside_mean_delta") or 0) > MAX_VISIBLE_EYEBROW_MEAN_DELTA:
            raise ImageProviderError("خروجی AI تغییر بیش از حد شدید داخل ابرو داشت و رد شد")
        raise ImageProviderError("خروجی AI در محدوده واقعی ابرو تغییر قابل مشاهده ایجاد نکرد")
    if not metrics.get("outside_mask_preserved"):
        raise ImageProviderError("خروجی AI بیرون از mask ابرو تغییر ناخواسته داشت و رد شد")
    return metrics


def _save_provider_output(image_value: str, timeout: int, source_path: str = "",
                          candidate: Optional[Dict[str, Any]] = None,
                          provider_kind: str = "") -> Tuple[str, Dict[str, Any]]:
    raw, _mime = _decode_image_value(image_value, timeout)
    if not raw:
        raise ImageProviderError("تصویر خروجی خالی است")
    tmp_path = ""
    out_path = ""
    try:
        from PIL import Image

        provider_image = Image.open(BytesIO(raw)).convert("RGB")
        # [10] دریافت تصویر AI
        _trace_log("10", "provider_output_received", width=provider_image.width, height=provider_image.height,
                   mode=provider_image.mode, format="RGB from bytes", file_size=len(raw),
                   output_type="full_image" if provider_image.width>200 else "cropped", provider_kind=provider_kind)

        meta: Dict[str, Any] = {
            "provider_output_constrained_to_eyebrow_mask": False,
            "provider_raw_width": int(provider_image.width or 0),
            "provider_raw_height": int(provider_image.height or 0),
        }
        final_image = provider_image
        base_for_validation = None
        mask_for_validation = None
        # برای نتیجه دقیق و متمرکز روی ابرو و جلوگیری از تغییر لب/پوست/مژه، برای همه providerها از ماسک استفاده می‌کنیم
        # با ماسک ضخیم‌تر (MaxFilter 7) و strength کنترل‌شده، فقط ابرو عوض می‌شه
        use_mask = bool(source_path and candidate is not None)
        _trace_log("11", "composite_check", use_mask=use_mask, source_path_exists=bool(source_path and os.path.exists(source_path)),
                   candidate_exists=candidate is not None, provider_kind=provider_kind,
                   condition_source_and_candidate=bool(source_path and candidate is not None))
        if use_mask:
            base = Image.open(source_path).convert("RGB")
            base.thumbnail((MAX_SAVE_SIDE, MAX_SAVE_SIDE))
            fitted_provider = _fit_provider_image_to_source(provider_image, base.size).convert("RGB")
            # Binary mask for guarantee: outside identical, per step 6 & 9
            # for_composite=False gives strict binary NEAREST mask
            mask, detection = _provider_eyebrow_mask_for_save(source_path, candidate, base.size, for_composite=False)
            # Also build feathered version for optional natural edge, but we will use binary for guarantee
            try:
                mask_feathered, _ = _provider_eyebrow_mask_for_save(source_path, candidate, base.size, for_composite=True)
            except Exception:
                mask_feathered = mask

            # --- پیش‌اعتبارسنجی: برای flux-2-klein-4b که مدل text-to-image است نه inpainting،
            # خروجی خام همیشه پس‌زمینه/هویت متفاوت دارد. چون در مرحله بعد با mask کامپوزیت
            # می‌کنیم و بیرون از ابرو دقیقاً برابر عکس اصلی می‌شود، نباید روی outside سخت‌گیری کنیم.
            try:
                _w, _h = fitted_provider.size
                _total = max(1, _w * _h)
                _white_count = 0
                _stride_white = max(1, int((_total / 50000) ** 0.5))
                _fpx = fitted_provider.load()
                for _yy in range(0, _h, _stride_white):
                    for _xx in range(0, _w, _stride_white):
                        _r, _g, _b = _fpx[_xx, _yy]
                        if _r > WHITE_THRESHOLD and _g > WHITE_THRESHOLD and _b > WHITE_THRESHOLD:
                            if max(_r, _g, _b) - min(_r, _g, _b) < 20:
                                _white_count += 1
                _white_ratio_total = float(_white_count) / float(max(1, (_w // _stride_white) * (_h // _stride_white)))
                if _white_ratio_total > 0.35:
                    raise ImageProviderError("خروجی AI پس‌زمینه سفید زیاد دارد و رد شد (مدل چهره جدید ساخت - هاله سفید)")
                try:
                    _outside_metrics_before = _visible_eyebrow_diff_metrics(base, fitted_provider, mask)
                    _beauty_log(
                        "[COMPOSITE]",
                        "pre_composite_outside_metrics",
                        outside_mean_delta=_outside_metrics_before.get("outside_mean_delta"),
                        outside_changed_ratio=_outside_metrics_before.get("outside_changed_ratio"),
                        inside_mean_delta=_outside_metrics_before.get("inside_mean_delta"),
                        white_ratio_total=round(_white_ratio_total, 4),
                        note="flux model - outside change expected, will be fixed by composite",
                    )
                except Exception:
                    pass
            except ImageProviderError:
                raise
            except Exception:
                pass

            # [11] Composite – قطعی: Final = Original خارج Mask + AI داخل Mask (step 9)
            # Use binary mask for 100% guarantee outside identical
            _trace_log("11", "composite_before", func="Image.composite",
                       source_image=f"{base.size[0]}x{base.size[1]}", provider_output=f"{fitted_provider.size[0]}x{fitted_provider.size[1]}",
                       mask_size=f"{mask.size[0]}x{mask.size[1]}", mask_coverage=detection.get("mask", {}).get("coverage_ratio") if isinstance(detection, dict) else "unknown",
                       mask_bbox=str(mask.getbbox()) if hasattr(mask, 'getbbox') else "",
                       design_mode=(detection.get("mask", {}).get("design_mode") if isinstance(detection, dict) else False),
                       style_key=(detection.get("mask", {}).get("style_key") if isinstance(detection, dict) else ""))

            # Binary composite guarantees outside preservation mathematically
            final_image = Image.composite(fitted_provider, base, mask)
            _trace_log("11", "composite_executed", executed=True, result_size=f"{final_image.size[0]}x{final_image.size[1]}",
                       outside_preserved_from_original=True, mask_applied=True, composite_bypassed=False,
                       binary_mask=True, mask_mode=mask.mode)

            # White halo cleaning for ALL models – inpainting can also produce light halo if prompt weak
            # More aggressive: replace light gray/white inside mask with base where base is darker
            try:
                _f_final = final_image.load()
                _f_base = base.load()
                _f_mask = mask.load()
                _w, _h = final_image.size
                _cleaned = 0
                for _yy in range(_h):
                    for _xx in range(_w):
                        mv = int(_f_mask[_xx, _yy])
                        if mv < 128:
                            continue
                        r, g, b = _f_final[_xx, _yy]
                        br, bg, bb = _f_base[_xx, _yy]
                        # If pixel is light (white/light gray/beige) and base is darker, it's halo, not brow
                        # Brow should be dark: brightness < 130, so >185 is suspicious
                        avg = (r + g + b) / 3.0
                        base_avg = (br + bg + bb) / 3.0
                        is_light = avg > 185
                        is_grayish = max(r, g, b) - min(r, g, b) < 35
                        is_white = r > WHITE_THRESHOLD and g > WHITE_THRESHOLD and b > WHITE_THRESHOLD
                        # If light and base darker by >20, clean
                        if (is_light and is_grayish) or is_white:
                            if base_avg < avg - 15:
                                # Replace halo with original skin
                                _f_final[_xx, _yy] = _f_base[_xx, _yy]
                                _cleaned += 1
                            # Also if very white (>230) regardless of base
                            elif r > 230 and g > 230 and b > 230:
                                _f_final[_xx, _yy] = _f_base[_xx, _yy]
                                _cleaned += 1
                if _cleaned > 0:
                    _beauty_log("[COMPOSITE]", "white_halo_cleaned", cleaned_pixels=_cleaned, model_type=provider_kind)
                    _trace_log("11", "white_halo_cleaned", cleaned_pixels=_cleaned, provider_kind=provider_kind)
            except Exception as _e:
                _beauty_log("[COMPOSITE]", "white_halo_clean_failed", error=str(_e)[:80])
                _trace_log("11", "white_halo_clean_failed", error=str(_e)[:80])

            # [12] Validation
            _trace_log("12", "validation_start", func="_validate_provider_visible_change",
                       base_size=f"{base.size[0]}x{base.size[1]}", final_size=f"{final_image.size[0]}x{final_image.size[1]}",
                       mask_size=f"{mask.size[0]}x{mask.size[1]}")
            diff_meta = _validate_provider_visible_change(base, final_image, mask)
            _trace_log("12", "validation_done", inside_mean_delta=diff_meta.get("inside_mean_delta"),
                       inside_changed_ratio=diff_meta.get("inside_changed_ratio"),
                       inside_white_ratio=diff_meta.get("inside_white_ratio"),
                       outside_mean_delta=diff_meta.get("outside_mean_delta"),
                       outside_p99_delta=diff_meta.get("outside_p99_delta"),
                       outside_changed_ratio=diff_meta.get("outside_changed_ratio"),
                       eyebrow_roi_changed=diff_meta.get("eyebrow_roi_changed"),
                       outside_mask_preserved=diff_meta.get("outside_mask_preserved"))
            base_for_validation = base.copy()
            mask_for_validation = mask.copy()
            mask_info = detection.get("mask") if isinstance(detection, dict) and isinstance(detection.get("mask"), dict) else {}
            meta.update({
                "provider_output_constrained_to_eyebrow_mask": True,
                "mask_used": True,
                "mask_width": int(mask_info.get("width") or 0),
                "mask_height": int(mask_info.get("height") or 0),
                "mask_pixels": int(mask_info.get("pixel_count") or 0),
                "mask_coverage_ratio": mask_info.get("coverage_ratio"),
                "mask_polarity": mask_info.get("polarity") or MASK_POLARITY,
                "mask_source_method": detection.get("method") if isinstance(detection, dict) else "",
                "mask_is_fallback": bool(mask_info.get("is_fallback") or (detection.get("is_fallback") if isinstance(detection, dict) else False)),
                "mask_filename": _upload_relative_path(str(mask_info.get("path") or detection.get("mask_path") or "")),
                "eyebrow_roi_changed": True,
                "outside_mask_preserved": True,
            })
            meta.update(diff_meta)
        else:
            # [11] composite bypass - no mask
            _trace_log("11", "composite_bypassed", reason="no source_path or no candidate", use_mask=False,
                       provider_kind=provider_kind, executed=False)
            # برای flux بدون ماسک (مثل buti-test) فقط سفید زیاد را چک کن
            try:
                _w, _h = final_image.size
                _total = max(1, _w * _h)
                _white_count = 0
                _stride_white = max(1, int((_total / 50000) ** 0.5))
                _fpx = final_image.load()
                for _yy in range(0, _h, _stride_white):
                    for _xx in range(0, _w, _stride_white):
                        _r, _g, _b = _fpx[_xx, _yy]
                        if _r > WHITE_THRESHOLD and _g > WHITE_THRESHOLD and _b > WHITE_THRESHOLD:
                            if max(_r, _g, _b) - min(_r, _g, _b) < 20:
                                _white_count += 1
                _white_ratio_total = float(_white_count) / float(max(1, (_w // _stride_white) * (_h // _stride_white)))
                if _white_ratio_total > 0.35:
                    _trace_log("12", "validation_failed_white_total", white_ratio_total=_white_ratio_total, threshold=0.35)
                    raise ImageProviderError("خروجی AI پس‌زمینه سفید زیاد دارد و رد شد")
                _beauty_log("[AI_OUTPUT]", "flux_no_mask_white_check", white_ratio_total=round(_white_ratio_total,4))
                _trace_log("12", "validation_flux_no_mask", white_ratio_total=round(_white_ratio_total,4))
            except ImageProviderError:
                raise
            except Exception:
                pass
            final_image.thumbnail((MAX_SAVE_SIDE, MAX_SAVE_SIDE))
        if final_image.width <= 0 or final_image.height <= 0:
            raise ImageProviderError("ابعاد خروجی provider نامعتبر بود")
        os.makedirs(final_design.FINAL_DESIGN_DIR, exist_ok=True)
        # PNG keeps every pixel outside the eyebrow mask identical after save; JPEG
        # recompression can touch face/skin/background outside the ROI.
        filename = f"final/ai_eyebrow_{datetime.utcnow().strftime('%Y%m%d%H%M%S')}_{uuid.uuid4().hex[:10]}.png"
        out_path = os.path.join(final_design.EYEBROW_UPLOAD_DIR, filename)
        tmp_path = f"{out_path}.tmp-{uuid.uuid4().hex[:8]}.png"
        final_image.save(tmp_path, "PNG", optimize=True)
        try:
            with Image.open(tmp_path) as saved_probe:
                saved_probe.verify()
            with Image.open(tmp_path) as saved_image:
                saved_w, saved_h = saved_image.size
                if base_for_validation is not None and mask_for_validation is not None:
                    saved_diff_meta = _validate_provider_visible_change(
                        base_for_validation,
                        saved_image.convert("RGB"),
                        mask_for_validation,
                    )
                    for diff_key, diff_value in saved_diff_meta.items():
                        meta[f"saved_{diff_key}"] = diff_value
                    meta["saved_file_diff_validated"] = True
        except ImageProviderError:
            raise
        except Exception as exc:
            raise ImageProviderError("فایل ذخیره‌شده خروجی AI قابل خواندن نبود") from exc
        if int(saved_w or 0) <= 0 or int(saved_h or 0) <= 0:
            raise ImageProviderError("ابعاد فایل ذخیره‌شده خروجی AI نامعتبر بود")
        os.replace(tmp_path, out_path)
        tmp_path = ""
        meta.update({
            "saved": True,
            "readable": True,
            "final_width": int(saved_w),
            "final_height": int(saved_h),
            "final_filename": filename,
        })
        # [13] ذخیره Final Image
        try:
            _final_fsize = os.path.getsize(out_path)
        except Exception:
            _final_fsize = 0
        _trace_log("13", "final_image_saved", final_path=_upload_relative_path(out_path) or filename,
                   filename=filename, width=saved_w, height=saved_h, format="PNG",
                   file_size=_final_fsize, final_validation=meta.get("saved_file_diff_validated"),
                   saved_eyebrow_roi_changed=meta.get("saved_eyebrow_roi_changed"),
                   saved_outside_preserved=meta.get("saved_outside_mask_preserved"))

        _beauty_log(
            "[AI_OUTPUT]",
            "saved_provider_output",
            output_path=filename,
            output_size=f"{saved_w}x{saved_h}",
            saved=True,
            valid=True,
            mask_used=meta.get("mask_used"),
            eyebrow_roi_changed=meta.get("eyebrow_roi_changed"),
        )
        return filename, meta
    except ImageProviderError:
        if tmp_path:
            try:
                os.remove(tmp_path)
            except Exception:
                pass
        if out_path and os.path.exists(out_path):
            try:
                os.remove(out_path)
            except Exception:
                pass
        raise
    except Exception as exc:
        if tmp_path:
            try:
                os.remove(tmp_path)
            except Exception:
                pass
        raise ImageProviderError(f"خروجی provider تصویر معتبر نبود: {str(exc)[:120]}") from exc

def _friendly_provider_error(exc: Exception) -> str:
    raw = str(exc or "").strip() or "provider failed"
    low = raw.lower()
    if "read timed out" in low or "timeout" in low or "timed out" in low:
        return "مدل دیر جواب داد و زمان درخواست تمام شد."
    if "request body is not valid json" in low:
        return "این مدل برای مسیر طراحی عکس نهایی فعلی مناسب نیست و باید از اسلات ابرو حذف شود."
    return raw[:280]


def _attempt(provider: ImageProviderConfig, ok: bool, ms: int, error: str = "") -> Dict[str, Any]:
    item = {
        "provider": provider.id,
        "label": provider.label,
        "kind": provider.kind,
        "model": provider.model,
        "ok": bool(ok),
        "ms": int(ms),
        "ai_inpainting": provider.kind in CLOUDFLARE_INPAINTING_KINDS,
    }
    meta = provider.extra.get("_last_request_meta") if isinstance(provider.extra, dict) else None
    if isinstance(meta, dict):
        for key in (
            "mask_used", "mask_width", "mask_height", "mask_pixels", "mask_coverage_ratio",
            "mask_polarity", "mask_source_method", "mask_is_fallback", "mask_filename",
            "reference_image_sent", "cloudflare_request_format", "cloudflare_output_width",
            "cloudflare_output_height", "provider_output_constrained_to_eyebrow_mask",
            "eyebrow_roi_changed", "outside_mask_preserved", "inside_mean_delta",
            "inside_p95_delta", "inside_changed_ratio", "inside_mask_sampled_pixels",
            "outside_mean_delta", "outside_p99_delta", "outside_changed_ratio",
            "provider_raw_width", "provider_raw_height", "saved", "readable",
            "final_width", "final_height", "final_filename", "saved_file_diff_validated",
            "saved_eyebrow_roi_changed", "saved_outside_mask_preserved",
        ):
            if key in meta:
                item[key] = meta[key]
    if error:
        item["error"] = str(error)[:280]
    return item


def _is_two_stage_enabled(candidate: Dict[str, Any], env: Optional[Dict[str, str]]) -> bool:
    """Check if two-stage (flux enhance + inpainting) is enabled."""
    # From env
    try:
        if _truthy(_env_value(env, "BUTI_AI_EYEBROW_TWO_STAGE") or _env_value(env, "EYEBROW_TWO_STAGE")):
            return True
    except Exception:
        pass
    # From candidate flag
    try:
        if isinstance(candidate, dict):
            if candidate.get("two_stage") or candidate.get("twoStage") or candidate.get("use_two_stage"):
                return True
            # If change_level is clear and we have both models, enable two-stage for best quality
            if str(candidate.get("change_key") or "").lower() == "clear":
                # Only if explicitly allowed via env TWO_STAGE_FOR_CLEAR
                if _truthy(_env_value(env, "BUTI_AI_EYEBROW_TWO_STAGE_FOR_CLEAR")):
                    return True
    except Exception:
        pass
    return False


def _find_flux_and_inpaint_providers(providers: List[ImageProviderConfig]) -> Tuple[Optional[ImageProviderConfig], Optional[ImageProviderConfig]]:
    """Find flux (whole face) and inpainting (eyebrow) providers from list."""
    flux = None
    inpaint = None
    for p in providers:
        kind = str(p.kind or "").lower()
        model = str(p.model or "").strip()
        if kind in CLOUDFLARE_INPAINTING_KINDS or model == CLOUDFLARE_INPAINTING_MODEL:
            if inpaint is None:
                inpaint = p
        elif model == DEFAULT_CLOUDFLARE_FINAL_IMAGE_MODEL or "flux" in model.lower():
            if flux is None:
                flux = p
    # If no explicit flux, take first non-inpainting as flux candidate
    if flux is None:
        for p in providers:
            kind = str(p.kind or "").lower()
            if kind not in CLOUDFLARE_INPAINTING_KINDS:
                flux = p
                break
    return flux, inpaint


def _generate_two_stage_design(candidate: Dict[str, Any], providers: List[ImageProviderConfig], prompt: str, timeout: int, source_path: str, eyebrow_detection: Dict[str, Any], env: Optional[Dict[str, str]]) -> Dict[str, Any]:
    """Two-stage: flux enhance whole face (low strength) + inpainting precise eyebrow.
    
    Stage 1: flux with low strength 0.35 – enhance skin/lighting, keep identity
    Stage 2: inpainting with mask – redesign eyebrow on enhanced face
    """
    flux_provider, inpaint_provider = _find_flux_and_inpaint_providers(providers)
    if not flux_provider or not inpaint_provider:
        _trace_log("05", "two_stage_missing_providers", has_flux=bool(flux_provider), has_inpaint=bool(inpaint_provider))
        return {}

    _trace_log("05", "two_stage_start", flux_id=flux_provider.id, flux_model=flux_provider.model,
               inpaint_id=inpaint_provider.id, inpaint_model=inpaint_provider.model)

    # Stage 1: Face enhancement with flux low strength
    face_enhance_prompt = (
        f"{prompt} | FACE ENHANCE STAGE: enhance this face photo naturally, even skin tone, soft natural lighting, "
        f"keep same person identity 100%, same eyes, same nose, same lips, same hijab, same background, "
        f"photorealistic, high quality, no makeup change except eyebrows will be done in next stage, "
        f"NO new face, NO white background, NO halo"
    )
    # Use low strength for flux to preserve identity
    original_flux_strength = flux_provider.extra.get("strength")
    flux_provider.extra["strength"] = 0.32
    flux_provider.extra["guidance"] = 4.5

    try:
        _trace_log("06", "two_stage_stage1_flux", provider_id=flux_provider.id, model=flux_provider.model, strength=0.32)
        image_value_stage1 = _call_provider(flux_provider, source_path, "", candidate, face_enhance_prompt, timeout)
        # Save intermediate to temp file for stage 2
        intermediate_bytes, _ = _decode_image_value(image_value_stage1, timeout)
        from PIL import Image
        import tempfile
        tmp_dir = tempfile.mkdtemp(prefix="eyebrow_two_stage_")
        intermediate_path = os.path.join(tmp_dir, "stage1_enhanced.jpg")
        try:
            img = Image.open(BytesIO(intermediate_bytes)).convert("RGB")
            img.thumbnail((MAX_PROVIDER_INPUT_SIDE, MAX_PROVIDER_INPUT_SIDE))
            img.save(intermediate_path, "JPEG", quality=92, optimize=True)
        except Exception as e:
            _trace_log("06", "two_stage_stage1_save_failed", error=str(e)[:120])
            # Fallback: use original source
            intermediate_path = source_path

        # Stage 2: Inpainting eyebrow on enhanced face
        _trace_log("06", "two_stage_stage2_inpaint", provider_id=inpaint_provider.id, model=inpaint_provider.model,
                   intermediate_path=_upload_relative_path(intermediate_path))
        # Restore flux strength
        if original_flux_strength is not None:
            flux_provider.extra["strength"] = original_flux_strength
        else:
            flux_provider.extra.pop("strength", None)

        # Call inpainting with intermediate as source
        image_value_stage2 = _call_cloudflare_inpainting(inpaint_provider, intermediate_path, candidate, prompt, timeout)
        # Save final with composite: intermediate outside + inpaint inside
        # _save_provider_output expects source_path to composite with – we want intermediate as base for outside
        filename, save_meta = _save_provider_output(image_value_stage2, timeout, intermediate_path, candidate, provider_kind=inpaint_provider.kind)

        # Cleanup temp
        try:
            if os.path.exists(intermediate_path) and tmp_dir in intermediate_path:
                os.remove(intermediate_path)
                os.rmdir(tmp_dir)
        except Exception:
            pass

        # Build result
        current_detection = candidate.get("eyebrow_detection") if isinstance(candidate.get("eyebrow_detection"), dict) else eyebrow_detection
        result = {
            "ok": True,
            "filename": filename,
            "provider": f"{flux_provider.id}+{inpaint_provider.id}",
            "provider_label": f"{flux_provider.label} + {inpaint_provider.label}",
            "kind": "two_stage_flux_inpaint",
            "model": f"{flux_provider.model} -> {inpaint_provider.model}",
            "status": "ai_two_stage_ready",
            "prompt": prompt,
            "face_enhance_prompt": face_enhance_prompt,
            "eyebrow_detection_method": current_detection.get("method") if isinstance(current_detection, dict) else "",
            "eyebrow_detection": current_detection,
            "attempts": [],
            "fallback_used": False,
            "ai_inpainting": True,
            "is_ai_generated": True,
            "two_stage": True,
            "stage1_provider": flux_provider.id,
            "stage2_provider": inpaint_provider.id,
            "configured_provider_count": len(providers),
            "message": "طراحی دو مرحله‌ای: صورت با Flux بهبود یافت و ابرو با Inpainting دقیق بازطراحی شد.",
        }
        for k, v in save_meta.items():
            result[k] = v
        _trace_log("14", "two_stage_success", final_path=filename, stage1=flux_provider.id, stage2=inpaint_provider.id)
        return result

    except Exception as exc:
        _trace_log("05", "two_stage_failed", error=str(exc)[:200])
        # Restore flux strength on failure
        try:
            if original_flux_strength is not None:
                flux_provider.extra["strength"] = original_flux_strength
            else:
                flux_provider.extra.pop("strength", None)
        except Exception:
            pass
        return {}
    finally:
        # Ensure cleanup
        try:
            if 'tmp_dir' in locals() and os.path.exists(tmp_dir):
                import shutil
                shutil.rmtree(tmp_dir, ignore_errors=True)
        except Exception:
            pass


def generate_final_design(candidate: Dict[str, Any], env: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
    """تولید طراحی عکس نهایی با providerهای تصویر و fallback پایتونی امن.

    اگر provider تصویر تنظیم نشده باشد یا همه providerها شکست بخورند، خروجی
    `generate_python_guided_design` ساخته می‌شود تا تجربه کاربر قطع نشود.
    """
    flow_start = time.monotonic()
    _gen_start = time.monotonic()
    candidate = dict(candidate or {})
    # [01] شروع درخواست
    _trace_log("01", "start_request", file="image_generation.py", func="generate_final_design",
               service_id="eyebrow", selected_style=candidate.get("final_style"), change_key=candidate.get("change_key"),
               photo_filename=candidate.get("photo_filename"), session_id=candidate.get("session_id"))

    source_path = final_design.source_image_path(candidate)
    if not source_path:
        _beauty_log("[FINAL]", "missing_source_photo", is_ai_generated=False, status="missing_photo")
        _trace_log("01", "missing_source_photo", status="missing_photo")
        return {"ok": False, "message": "برای طراحی عکس نهایی، عکس واقعی لازم است.", "status": "missing_photo"}

    # [02] عکس ورودی
    try:
        from PIL import Image as _PIL
        with _PIL.open(source_path) as _img:
            _iw, _ih = _img.size
            _imode = _img.mode
            _iformat = _img.format
    except Exception:
        _iw, _ih, _imode, _iformat = 0, 0, "", ""
    try:
        _fsize = os.path.getsize(source_path)
    except Exception:
        _fsize = 0
    _fname = os.path.basename(source_path)
    _ext = os.path.splitext(_fname)[1]
    _exists = os.path.exists(source_path)
    source_w, source_h = _image_size_for_log(source_path)
    _trace_log("02", "input_image", file_path=_upload_relative_path(source_path) or _fname,
               filename=_fname, extension=_ext, width=_iw or source_w, height=_ih or source_h,
               mode=_imode, format=_iformat, file_size=_fsize, exists=_exists)

    _beauty_log(
        "[EYEBROW_PREVIEW]",
        "final_source_ready",
        original_path=_upload_relative_path(source_path) or os.path.basename(source_path),
        original_size=f"{source_w}x{source_h}",
        selected_style=candidate.get("final_style"),
        change_level=candidate.get("change_key"),
    )
    # [03] تشخیص چهره/ابرو – با Design Region بر اساس style
    try:
        from giso.buti_ai.eyebrow.options import normalize_style_key
        _style_for_detection = normalize_style_key(candidate.get("final_style") or candidate.get("selected_style") or "giso_suggested")
    except Exception:
        _style_for_detection = str(candidate.get("final_style") or "giso_suggested").strip().lower() or "giso_suggested"
    _trace_log("03", "eyebrow_detection_start", func="final_design.ensure_eyebrow_detection", style_key=_style_for_detection)
    eyebrow_detection = final_design.ensure_eyebrow_detection(candidate, style_key=_style_for_detection)
    _det_method = eyebrow_detection.get("method") if isinstance(eyebrow_detection, dict) else ""
    _det_ok = eyebrow_detection.get("ok") if isinstance(eyebrow_detection, dict) else False
    _regions = eyebrow_detection.get("regions") if isinstance(eyebrow_detection, dict) else []
    _trace_log("03", "eyebrow_detection_done", method=_det_method, ok=_det_ok, regions_count=len(_regions or []),
               left_bbox=str((_regions[0].get("x"), _regions[0].get("y"), _regions[0].get("width"), _regions[0].get("height")) ) if len(_regions or [])>0 else "",
               right_bbox=str((_regions[1].get("x"), _regions[1].get("y"), _regions[1].get("width"), _regions[1].get("height")) ) if len(_regions or [])>1 else "",
               mask_path=_upload_relative_path(str((eyebrow_detection.get("mask") or {}).get("path") or eyebrow_detection.get("mask_path") or "")) if isinstance(eyebrow_detection, dict) else "")
    mask_info = eyebrow_detection.get("mask") if isinstance(eyebrow_detection, dict) and isinstance(eyebrow_detection.get("mask"), dict) else {}
    _beauty_log(
        "[EYEBROW_MASK]",
        "detection_ready",
        method=eyebrow_detection.get("method") if isinstance(eyebrow_detection, dict) else "",
        mask_path=_upload_relative_path(str(mask_info.get("path") or (eyebrow_detection or {}).get("mask_path") or "")) if isinstance(eyebrow_detection, dict) else "",
        mask_size=f"{mask_info.get('width') or source_w}x{mask_info.get('height') or source_h}",
        coverage_ratio=mask_info.get("coverage_ratio"),
        real_mask=mask_info.get("real_mask"),
        polarity=mask_info.get("polarity") or MASK_POLARITY,
    )
    # [04] ساخت MASK - دقیق
    try:
        _mask_path = str(mask_info.get("path") or eyebrow_detection.get("mask_path") or "")
        _mask_exists = os.path.exists(_mask_path) if _mask_path else False
        _mask_w = int(mask_info.get("width") or 0)
        _mask_h = int(mask_info.get("height") or 0)
        _mask_pixels = int(mask_info.get("pixel_count") or 0)
        _coverage = mask_info.get("coverage_ratio")
        _polarity = mask_info.get("polarity") or MASK_POLARITY
        _edit_val = mask_info.get("edit_value")
        _keep_val = mask_info.get("keep_value")
        _real = mask_info.get("real_mask")
        _is_fallback = mask_info.get("is_fallback")
        # محاسبه min/max و non-zero و bbox از فایل mask اگر وجود دارد
        _min_px, _max_px, _non_zero, _bbox = 0, 0, 0, ""
        if _mask_exists:
            try:
                from PIL import Image as _PILMask
                with _PILMask.open(_mask_path) as _m:
                    _mw, _mh = _m.size
                    _mmode = _m.mode
                    _mdata = list(_m.getdata())
                    if _mdata:
                        _min_px = min(_mdata)
                        _max_px = max(_mdata)
                        _non_zero = sum(1 for px in _mdata if px > 0)
                        # bbox
                        _bbox_img = _m.getbbox()
                        _bbox = str(_bbox_img)
                    else:
                        _mmode = _m.mode
            except Exception:
                pass
        _trace_log("04", "mask_built", file="landmarks.py", func="ensure_eyebrow_mask",
                   mask_path=_upload_relative_path(_mask_path) if _mask_path else "",
                   exists=_mask_exists, width=_mask_w, height=_mask_h, mode="L",
                   format="PNG", pixel_count=_mask_pixels, coverage_ratio=_coverage,
                   coverage_percent=round(float(_coverage or 0)*100, 3) if _coverage else 0,
                   polarity=_polarity, edit_value=_edit_val, keep_value=_keep_val,
                   white_is_edit=(_polarity=="white_edit_black_keep"), real_mask=_real, is_fallback=_is_fallback,
                   min_pixel=_min_px, max_pixel=_max_px, non_zero_count=_non_zero, bbox=_bbox,
                   both_eyebrows_covered=len(_regions or [])==2, includes_eye="unknown")
    except Exception as _e:
        _trace_log("04", "mask_built_failed", error=str(_e)[:120])

    prompt = final_design.build_design_prompt(candidate)
    # [05] انتخاب Provider + [01] prompt length
    _trace_log("01", "prompt_built", prompt_length=len(prompt or ""), style=candidate.get("final_style"))
    try:
        providers = configured_image_providers(env, service_key="eyebrow")
    except TypeError:
        providers = configured_image_providers(env)
    # [05] provider selection
    try:
        _order = [p.id for p in providers]
        _trace_log("05", "providers_configured", count=len(providers), order=str(_order),
                   endpoint_hosts=str([_safe_host(p.endpoint) for p in providers]))
        for _idx, _p in enumerate(providers):
            _trace_log("05", f"provider_{_idx+1}_detail", provider_id=_p.id, label=_p.label,
                       model=_p.model, configured_kind=_p.kind, resolved_kind=_cloudflare_kind_for_model(_p.model, _p.kind),
                       endpoint_host=_safe_host(_p.endpoint))
    except Exception as _e:
        _trace_log("05", "provider_log_failed", error=str(_e)[:120])

    reference_path = _reference_image_path(candidate)
    timeout = _timeout_seconds(env)
    attempts: List[Dict[str, Any]] = []

    # Two-stage: flux enhance + inpainting – if enabled and both providers available
    if _is_two_stage_enabled(candidate, env):
        _trace_log("05", "two_stage_enabled_check", enabled=True, candidate_flag=candidate.get("two_stage"))
        two_stage_result = _generate_two_stage_design(candidate, providers, prompt, timeout, source_path, eyebrow_detection, env)
        if two_stage_result and two_stage_result.get("ok"):
            _trace_log("14", "two_stage_final_return", final_path=two_stage_result.get("filename"))
            return two_stage_result
        else:
            _trace_log("05", "two_stage_fallback_to_single", reason="two_stage failed or incomplete")

    for provider in providers:
        started = time.monotonic()
        # [05] attempt provider
        _trace_log("05", "provider_attempt", provider_id=provider.id, label=provider.label,
                   model=provider.model, kind=provider.kind, endpoint_host=_safe_host(provider.endpoint),
                   attempt_index=len(attempts)+1, fallback_active=len(attempts)>0)
        _beauty_log(
            "[AI]",
            "provider_attempt_start",
            provider=provider.id,
            model=provider.model,
            image_kind=provider.kind,
            endpoint_host=_safe_host(provider.endpoint),
        )
        try:
            image_value = _call_provider(provider, source_path, reference_path, candidate, prompt, timeout)
            filename, save_meta = _save_provider_output(image_value, timeout, source_path, candidate, provider_kind=provider.kind)
            if save_meta:
                last_meta = provider.extra.setdefault("_last_request_meta", {})
                for meta_key, meta_value in save_meta.items():
                    if meta_key in last_meta and (meta_key == "mask_used" or meta_key.startswith("mask_")):
                        continue
                    last_meta[meta_key] = meta_value
            ms = int((time.monotonic() - started) * 1000)
            attempt = _attempt(provider, True, ms)
            attempts.append(attempt)
            _beauty_log(
                "[AI]",
                "provider_attempt_success",
                provider=provider.id,
                model=provider.model,
                image_kind=provider.kind,
                ms=ms,
                mask_used=attempt.get("mask_used"),
                eyebrow_roi_changed=attempt.get("eyebrow_roi_changed"),
            )
            ai_inpainting = provider.kind in CLOUDFLARE_INPAINTING_KINDS
            current_detection = candidate.get("eyebrow_detection") if isinstance(candidate.get("eyebrow_detection"), dict) else eyebrow_detection
            result = {
                "ok": True,
                "filename": filename,
                "provider": provider.id,
                "provider_label": provider.label,
                "kind": provider.kind,
                "model": provider.model,
                "status": "ai_inpainting_ready" if ai_inpainting else "ai_final_ready",
                "prompt": prompt,
                "eyebrow_detection_method": current_detection.get("method") if isinstance(current_detection, dict) else "",
                "eyebrow_detection": current_detection,
                "attempts": attempts,
                "fallback_used": False,
                "ai_inpainting": ai_inpainting,
                "is_ai_generated": True,
                "configured_provider_count": len(providers),
                "message": "طراحی عکس نهایی با AI Inpainting و ماسک واقعی ابرو آماده شد." if ai_inpainting else "طراحی عکس نهایی با AI آماده شد و فقط داخل محدوده ابرو روی عکس اصلی اعمال شد.",
            }
            for key in (
                "mask_used", "mask_width", "mask_height", "mask_pixels", "mask_coverage_ratio",
                "mask_polarity", "mask_source_method", "mask_is_fallback", "mask_filename",
                "reference_image_sent", "cloudflare_request_format", "cloudflare_output_width",
                "cloudflare_output_height", "provider_output_constrained_to_eyebrow_mask",
                "eyebrow_roi_changed", "outside_mask_preserved", "inside_mean_delta",
                "inside_p95_delta", "inside_changed_ratio", "inside_mask_sampled_pixels",
                "outside_mean_delta", "outside_p99_delta", "outside_changed_ratio",
                "provider_raw_width", "provider_raw_height", "saved", "readable",
                "final_width", "final_height", "final_filename", "saved_file_diff_validated",
                "saved_eyebrow_roi_changed", "saved_outside_mask_preserved",
            ):
                if key in attempt:
                    result[key] = attempt[key]
            if result.get("mask_is_fallback") and not ai_inpainting:
                result["message"] = "طراحی عکس نهایی با AI آماده شد و فقط داخل محدوده تقریبی ابرو روی عکس اصلی اعمال شد."
            _beauty_log(
                "[FINAL]",
                "ai_final_ready",
                final_path=filename,
                is_ai_generated=True,
                status=result.get("status"),
                provider=provider.id,
                model=provider.model,
                final_url_points_to_saved_file=bool(result.get("saved") and result.get("readable")),
            )
            # [14] FINAL summary
            try:
                _dur = int((time.monotonic() - _gen_start) * 1000) if '_gen_start' in locals() else ms
            except Exception:
                _dur = ms
            _trace_log("14", "FINAL_AI_SUCCESS", total_duration_ms=_dur, provider=provider.id,
                       model=provider.model, route=result.get("kind") or provider.kind,
                       mask_used=result.get("mask_used"), coverage_ratio=result.get("mask_coverage_ratio"),
                       composite_executed=True, validation_ok=True,
                       final_path=filename, final_width=result.get("final_width"), final_height=result.get("final_height"),
                       is_ai_generated=True, status=result.get("status"))
            return result
        except Exception as exc:
            ms = int((time.monotonic() - started) * 1000)
            safe_error = _friendly_provider_error(exc)
            attempts.append(_attempt(provider, False, ms, safe_error))
            _beauty_log(
                "[AI]",
                "provider_attempt_failed",
                provider=provider.id,
                model=provider.model,
                image_kind=provider.kind,
                ms=ms,
                error=safe_error[:160],
            )
            logger.info(
                "Buti AI image provider failed provider=%s model=%s ms=%s error=%s",
                provider.id,
                provider.model,
                ms,
                safe_error[:160],
            )

    # اصلاح: اگر همه CFها شکست خوردند، به جای AI FAILED یک پیش‌نمایش راهنمای پایتونی نشان بده
    # تا کاربر عکس الکی نبیند و فلو قطع نشود. این پیش‌نمایش غیر AI است ولی واقعی و قابل دیدن است
    # و به مشتری می‌گوید مدل انتخابی چطوری می‌شود، تا وقتی مدل inpainting درست تنظیم شود
    _beauty_log(
        "[FINAL]",
        "ai_failed_try_python_fallback",
        is_ai_generated=False,
        configured_provider_count=len(providers),
        attempts_count=len(attempts),
    )
    try:
        fallback = final_design.generate_python_guided_design(candidate)
        fallback["attempts"] = attempts
        fallback["configured_provider_count"] = len(providers)
        fallback["fallback_used"] = bool(providers)
        fallback["prompt"] = prompt
        fallback["ai_inpainting"] = False
        fallback["is_ai_generated"] = False
        fallback["fallback_type"] = "non_ai_guided_fallback"
        if fallback.get("ok"):
            if providers:
                # اگر مدل‌ها تلاش کردند و سفید رد شدند، پیام دقیق بده
                white_failed = any("سفید" in str(a.get("error") or "") for a in attempts)
                if white_failed:
                    fallback["status"] = "non_ai_guided_preview_ready"
                    fallback["message"] = "مدل فعلی CF با پس‌زمینه سفید خروجی داد و رد شد. این یک پیش‌نمایش راهنمای غیر AI با مدل انتخابی شماست تا وقتی مدل inpainting درست تنظیم شود. برای نتیجه واقعی AI، در مدیریت AI مدل @cf/runwayml/stable-diffusion-v1-5-inpainting را با نوع inpainting بگذار."
                else:
                    fallback["status"] = "non_ai_guided_fallback_ready"
                    fallback["message"] = "خروجی مدل‌های AI برای این عکس قابل تأیید نبود؛ عکس و انتخاب شما حفظ شد و فقط نسخه راهنمای غیر AI نمایش داده می‌شود."
            else:
                fallback["status"] = "non_ai_guided_preview_ready"
                fallback["message"] = "مدل تصویرسازی هنوز در مدیریت AI تنظیم نشده؛ عکس و انتخاب شما حفظ شد و فقط نسخه راهنمای غیر AI آماده شد."
            _beauty_log(
                "[FINAL]",
                "fallback_final_ready",
                final_path=fallback.get("filename"),
                is_ai_generated=False,
                status=fallback.get("status"),
                configured_provider_count=len(providers),
                fallback_used=fallback.get("fallback_used"),
            )
            _trace_log("14", "FINAL_FALLBACK", total_duration_ms=int((time.monotonic()-_gen_start)*1000),
                       provider="python_fallback", model="python_guided", route="python_guided_design",
                       final_path=fallback.get("filename"), is_ai_generated=False, status=fallback.get("status"),
                       attempts_count=len(attempts))
            return fallback
    except Exception as exc:
        _beauty_log("[FINAL]", "python_fallback_failed", error=str(exc)[:120])
        _trace_log("13", "python_fallback_failed", error=str(exc)[:160])

    # اگر حتی پایتونی هم شکست خورد -> AI FAILED
    _beauty_log(
        "[FINAL]",
        "ai_failed_all_providers",
        is_ai_generated=False,
        status="ai_failed",
        configured_provider_count=len(providers),
        attempts_count=len(attempts),
    )
    _trace_log("14", "FINAL_FAILED", total_duration_ms=int((time.monotonic()-_gen_start)*1000),
               provider="none", status="ai_failed", attempts_count=len(attempts),
               is_ai_generated=False, validation_ok=False)
    return {
        "ok": False,
        "status": "ai_failed",
        "message": "هر سه مدل CF1, CF2, CF3 برای این عکس ناموفق بودند و پیش‌نمایش راهنما هم ساخته نشد. لطفاً عکس واضح‌تری بفرست.",
        "attempts": attempts,
        "configured_provider_count": len(providers),
        "fallback_used": False,
        "ai_inpainting": False,
        "is_ai_generated": False,
        "prompt": prompt,
        "eyebrow_detection": eyebrow_detection,
        "eyebrow_detection_method": eyebrow_detection.get("method") if isinstance(eyebrow_detection, dict) else "",
    }


__all__ = [
    "CLOUDFLARE_INPAINTING_MODEL",
    "ImageProviderConfig",
    "configured_image_providers",
    "generate_final_design",
]
