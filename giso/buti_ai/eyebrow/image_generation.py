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
import http.client
import ipaddress
import json
import logging
import mimetypes
import os
import re
import socket
import ssl
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from io import BytesIO
from typing import Any, Dict, Iterable, List, Optional, Tuple
from urllib.parse import urlsplit, urlunsplit

import requests

from giso.buti_ai.eyebrow import final_design
from giso.buti_ai.eyebrow.landmarks import MASK_POLARITY, ensure_eyebrow_mask
from giso.buti_ai.eyebrow.options import normalize_style_key

logger = logging.getLogger("giso_buti_ai_image_generation")

# Shared default for Buti AI final image generation. The active model is still
# read from «مدیریت هوش مصنوعی»; this value is only the safe fallback when
# no management assignment is available.
CLOUDFLARE_INPAINTING_MODEL = "@cf/runwayml/stable-diffusion-v1-5-inpainting"
DEFAULT_CLOUDFLARE_MODEL = CLOUDFLARE_INPAINTING_MODEL
DEFAULT_CLOUDFLARE_IMAGE_MODEL = CLOUDFLARE_INPAINTING_MODEL
CLOUDFLARE_INPAINTING_KINDS = {"cloudflare_inpainting", "cloudflare_inpaint", "inpainting", "mask_inpainting"}
# حداکثر زمان انتظار هر مدل به‌صورت مستقل؛ اگر یک مدل خراب/گیرکرده باشد
# کل زنجیره منتظر آن نمی‌ماند. از پنل/ENV قابل تنظیم است.
DEFAULT_TIMEOUT_SECONDS = 45
MAX_DOWNLOAD_BYTES = 12 * 1024 * 1024
MAX_SAVE_SIDE = 1600
MAX_PROVIDER_INPUT_SIDE = 512
MAX_INPAINTING_INPUT_SIDE = 512
MAX_DIFF_SAMPLE_PIXELS = 260_000
# سخت‌گیرانه‌تر برای جلوگیری از artifact روی چشم/صورت و ماسک سفید (تصویر کاربر با حجاب)
# مقادیر سخت‌گیرانه‌تر بعد از مشاهده هاله سفید در عکس نهایی
MIN_VISIBLE_EYEBROW_MEAN_DELTA = 4.5
MAX_VISIBLE_EYEBROW_MEAN_DELTA = 32.0
MIN_VISIBLE_EYEBROW_CHANGED_RATIO = 0.018
VISIBLE_EYEBROW_PIXEL_DELTA = 8.0
MAX_OUTSIDE_MASK_MEAN_DELTA = 0.65
MAX_OUTSIDE_MASK_P99_DELTA = 3.5
MAX_OUTSIDE_CHANGED_RATIO = 0.012
MAX_INSIDE_WHITE_RATIO = 0.12


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
    # زمان هر attempt مستقل است؛ مدل خراب نباید کل fallback chain را معطل کند.
    for key in ("BUTI_AI_IMAGE_MODEL_TIMEOUT_SECONDS", "BUTI_AI_IMAGE_TIMEOUT_SECONDS", "CLOUDFLARE_TIMEOUT_MS", "PROVIDER_TIMEOUT_MS"):
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
    raw = _env_value(env, "BUTI_AI_IMAGE_PROVIDER_ORDER") or _env_value(env, "PROVIDER_ORDER")
    if not raw:
        return providers
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
    return ordered


def _cloudflare_providers(env: Optional[Dict[str, str]]) -> List[ImageProviderConfig]:
    providers: List[ImageProviderConfig] = []
    global_model = (
        _env_value(env, "BUTI_AI_CLOUDFLARE_MODEL")
        or _env_value(env, "CLOUDFLARE_MODEL")
        or DEFAULT_CLOUDFLARE_IMAGE_MODEL
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
        configured_items = configured_image_provider_dicts(service_key=service_key or "eyebrow")
    except TypeError:
        # Backward-compatible for tests/older monkeypatches that only accepted limit.
        configured_items = configured_image_provider_dicts()
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
    if content_type.startswith("image/"):
        data = response.content or b""
        if not data:
            raise ImageProviderError("پاسخ تصویر خالی بود")
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
        raise ImageProviderError(_extract_api_error(payload, raw_text) or f"HTTP {response.status_code}")

    if payload is not None:
        found = _extract_image_value(payload)
        if found:
            return found
    if raw_text.startswith("data:image/") or raw_text.startswith("http") or _looks_like_base64(raw_text):
        return raw_text.strip()
    raise ImageProviderError("پاسخ موفق بود اما تصویر خروجی پیدا نشد")


def _call_cloudflare(provider: ImageProviderConfig, source_path: str, reference_path: str, prompt: str, timeout: int) -> str:
    model_name = str(provider.model or "").strip()
    if model_name == CLOUDFLARE_INPAINTING_MODEL:
        raise ImageProviderError(
            "این مدل باید با kind=cloudflare_inpainting استفاده شود؛ "
            "در مدیریت AI نوع را inpainting بگذار یا از flux-2-klein-4b استفاده کن."
        )
    if model_name != DEFAULT_CLOUDFLARE_MODEL:
        raise ImageProviderError(
            "این مدل Cloudflare برای ویرایش عکس ورودی پشتیبانی نمی‌شود؛ "
            "برای ویرایش با عکس ورودی از flux-2-klein-4b یا مسیر inpainting سازگار استفاده کن."
        )
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
    mask = mask.point(lambda px: 255 if int(px) >= 128 else 0)
    mask_pixels = sum(1 for px in mask.getdata() if px > 0)
    total_pixels = max(1, new_w * new_h)
    coverage = float(mask_pixels) / float(total_pixels)
    if mask_pixels <= 0:
        raise ImageProviderError("mask واقعی ابرو خالی است؛ inpainting متوقف شد")
    if coverage > 0.12:
        raise ImageProviderError("mask ابرو بیش از حد وسیع است؛ برای حفظ صورت inpainting متوقف شد")

    image_out = BytesIO()
    mask_out = BytesIO()
    image.save(image_out, "PNG", optimize=True)
    mask.save(mask_out, "PNG", optimize=True)
    return image_out.getvalue(), mask_out.getvalue(), int(new_w), int(new_h), int(mask_pixels), round(coverage, 6)


def _real_eyebrow_mask_for_candidate(source_path: str, candidate: Dict[str, Any]) -> Tuple[Dict[str, Any], str]:
    detection = candidate.get("eyebrow_detection") if isinstance(candidate.get("eyebrow_detection"), dict) else {}
    if not detection or not detection.get("regions"):
        detection = final_design.ensure_eyebrow_detection(candidate)
    if detection and detection.get("regions"):
        detection = ensure_eyebrow_mask(source_path, detection)
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
    strength = float(provider.extra.get("strength") or _env_value(None, "CLOUDFLARE_INPAINTING_STRENGTH") or 0.72)
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
    if kind == "cloudflare":
        return _call_cloudflare(provider, source_path, reference_path, prompt, timeout)
    if kind in CLOUDFLARE_INPAINTING_KINDS:
        return _call_cloudflare_inpainting(provider, source_path, candidate, prompt, timeout)
    if kind in {"openai_image_edit", "openai_edit", "images_edit"}:
        return _call_openai_image_edit(provider, source_path, prompt, timeout)
    if kind in {"multipart", "form", "form_data"}:
        return _call_generic_multipart(provider, source_path, reference_path, prompt, timeout)
    if kind in {"json", "json_image", "data_uri"}:
        return _call_json_image(provider, source_path, reference_path, candidate, prompt, timeout)
    raise ImageProviderError(f"نوع provider پشتیبانی نمی‌شود: {kind or 'unknown'}")


_ALLOWED_PROVIDER_IMAGE_MIME_TYPES = frozenset({"image/jpeg", "image/png", "image/webp"})


def _normalize_provider_image_hostname(value: Any) -> str:
    """Normalize one exact DNS name; IP literals and wildcard patterns are never allowlisted."""
    raw = str(value or "").strip().rstrip(".")
    if not raw or any(char in raw for char in "/\\:*@[]"):
        return ""
    try:
        hostname = raw.encode("idna").decode("ascii").lower()
    except UnicodeError:
        return ""
    try:
        ipaddress.ip_address(hostname)
    except ValueError:
        pass
    else:
        return ""
    if len(hostname) > 253 or not hostname:
        return ""
    labels = hostname.split(".")
    if any(
        not label or len(label) > 63
        or not re.fullmatch(r"[a-z0-9](?:[a-z0-9-]*[a-z0-9])?", label)
        for label in labels
    ):
        return ""
    return hostname


def _provider_image_host_allowlist(provider_endpoint: str, provider_extra: Optional[Dict[str, Any]] = None) -> set:
    """Use the exact provider endpoint host plus explicitly configured exact CDN hosts."""
    allowed = set()
    try:
        endpoint = urlsplit(str(provider_endpoint or ""))
        if endpoint.scheme.lower() == "https" and endpoint.hostname and endpoint.port in (None, 443):
            host = _normalize_provider_image_hostname(endpoint.hostname)
            if host:
                allowed.add(host)
    except ValueError:
        pass

    extra = provider_extra if isinstance(provider_extra, dict) else {}
    nested_extra = extra.get("extra") if isinstance(extra.get("extra"), dict) else {}
    configured = extra.get("image_output_hosts")
    if configured is None:
        configured = nested_extra.get("image_output_hosts")
    if isinstance(configured, str):
        configured_hosts = configured.split(",")
    elif isinstance(configured, (list, tuple, set)):
        configured_hosts = configured
    else:
        configured_hosts = ()
    for item in configured_hosts:
        host = _normalize_provider_image_hostname(item)
        if host:
            allowed.add(host)
    return allowed


def _is_public_provider_image_ip(value: str) -> bool:
    try:
        address = ipaddress.ip_address(value.split("%", 1)[0])
    except ValueError:
        return False
    if isinstance(address, ipaddress.IPv6Address) and address.ipv4_mapped is not None:
        address = address.ipv4_mapped
    return bool(
        address.is_global
        and not address.is_private
        and not address.is_loopback
        and not address.is_link_local
        and not address.is_reserved
        and not address.is_multicast
        and not address.is_unspecified
    )


def _resolve_public_provider_image_addresses(hostname: str, port: int = 443) -> List[Tuple[int, str]]:
    """Resolve once, reject any non-public answer, and return IPs to pin the TLS connection to."""
    try:
        records = socket.getaddrinfo(hostname, port, type=socket.SOCK_STREAM)
    except (OSError, socket.gaierror) as exc:
        raise ImageProviderError("مقصد خروجی تصویر provider قابل resolve نیست") from exc
    addresses: List[Tuple[int, str]] = []
    seen = set()
    for family, _socktype, _protocol, _canonname, sockaddr in records:
        if family not in (socket.AF_INET, socket.AF_INET6) or not sockaddr:
            raise ImageProviderError("پاسخ DNS مقصد خروجی تصویر provider نامعتبر است")
        ip = str(sockaddr[0]).split("%", 1)[0]
        if not _is_public_provider_image_ip(ip):
            raise ImageProviderError("مقصد خروجی تصویر provider به IP غیرعمومی resolve شد")
        key = (family, ip)
        if key not in seen:
            addresses.append(key)
            seen.add(key)
    if not addresses:
        raise ImageProviderError("مقصد خروجی تصویر provider هیچ IP عمومی ندارد")
    return addresses


class _PinnedProviderImageHTTPSConnection(http.client.HTTPSConnection):
    """HTTPS connection pinned to an already-validated public IP (no proxy or second DNS lookup)."""

    def __init__(self, hostname: str, address: str, family: int, timeout: float):
        super().__init__(hostname, 443, timeout=timeout, context=ssl.create_default_context())
        self._pinned_address = address
        self._pinned_family = family

    def connect(self) -> None:
        raw_socket = socket.socket(self._pinned_family, socket.SOCK_STREAM)
        try:
            raw_socket.settimeout(self.timeout)
            if self._pinned_family == socket.AF_INET6:
                raw_socket.connect((self._pinned_address, self.port, 0, 0))
            else:
                raw_socket.connect((self._pinned_address, self.port))
            self.sock = self._context.wrap_socket(raw_socket, server_hostname=self.host)
        except Exception:
            raw_socket.close()
            raise


def _download_provider_image_url(
    value: str,
    timeout: int,
    provider_endpoint: str = "",
    provider_extra: Optional[Dict[str, Any]] = None,
) -> Tuple[bytes, str]:
    if len(value) > 4096 or any(ord(char) < 32 or ord(char) == 127 for char in value) or "\\" in value:
        raise ImageProviderError("URL خروجی تصویر provider نامعتبر است")
    try:
        parsed = urlsplit(value)
        port = parsed.port
    except ValueError as exc:
        raise ImageProviderError("URL خروجی تصویر provider نامعتبر است") from exc
    if (
        parsed.scheme.lower() != "https"
        or not parsed.hostname
        or parsed.username is not None
        or parsed.password is not None
        or port not in (None, 443)
    ):
        raise ImageProviderError("فقط URL امن HTTPS روی پورت 443 برای خروجی تصویر مجاز است")
    hostname = _normalize_provider_image_hostname(parsed.hostname)
    if not hostname or hostname not in _provider_image_host_allowlist(provider_endpoint, provider_extra):
        raise ImageProviderError("میزبان URL خروجی تصویر در allowlist دقیق provider نیست")

    addresses = _resolve_public_provider_image_addresses(hostname)
    path = urlunsplit(("", "", parsed.path or "/", parsed.query, ""))
    request_timeout = max(1, min(int(timeout or DEFAULT_TIMEOUT_SECONDS), 30))
    last_error: Optional[Exception] = None
    for family, address in addresses:
        connection = _PinnedProviderImageHTTPSConnection(hostname, address, family, request_timeout)
        response = None
        try:
            connection.request(
                "GET",
                path,
                headers={"Accept": "image/jpeg,image/png,image/webp", "Accept-Encoding": "identity", "Connection": "close"},
            )
            response = connection.getresponse()
            status = int(getattr(response, "status", 0) or 0)
            if status in (301, 302, 303, 307, 308):
                raise ImageProviderError("redirect خروجی تصویر provider مجاز نیست")
            if status != 200:
                raise ImageProviderError(f"دانلود خروجی provider ناموفق بود: HTTP {status}")
            content_encoding = (response.getheader("Content-Encoding") or "identity").strip().lower()
            if content_encoding not in ("", "identity"):
                raise ImageProviderError("فشرده‌سازی خروجی تصویر provider مجاز نیست")
            mime = (response.getheader("Content-Type") or "").split(";", 1)[0].strip().lower()
            if mime not in _ALLOWED_PROVIDER_IMAGE_MIME_TYPES:
                raise ImageProviderError("Content-Type خروجی provider تصویر مجاز نیست")
            raw_length = response.getheader("Content-Length")
            if raw_length is not None:
                if not re.fullmatch(r"[0-9]+", str(raw_length).strip()):
                    raise ImageProviderError("Content-Length خروجی تصویر provider نامعتبر است")
                if int(raw_length) > MAX_DOWNLOAD_BYTES:
                    raise ImageProviderError("حجم خروجی provider بیش از حد مجاز است")
            chunks: List[bytes] = []
            total = 0
            while True:
                chunk = response.read(min(65536, MAX_DOWNLOAD_BYTES + 1 - total))
                if not chunk:
                    break
                total += len(chunk)
                if total > MAX_DOWNLOAD_BYTES:
                    raise ImageProviderError("حجم خروجی provider بیش از حد مجاز است")
                chunks.append(chunk)
            if not total:
                raise ImageProviderError("پاسخ تصویر خالی بود")
            return b"".join(chunks), mime
        except ImageProviderError:
            raise
        except (OSError, http.client.HTTPException, ssl.SSLError) as exc:
            last_error = exc
        finally:
            if response is not None:
                try:
                    response.close()
                except Exception:
                    pass
            connection.close()
    raise ImageProviderError("دانلود امن خروجی تصویر provider ناموفق بود") from last_error


def _decode_image_value(
    image_value: str,
    timeout: int,
    provider_endpoint: str = "",
    provider_extra: Optional[Dict[str, Any]] = None,
) -> Tuple[bytes, str]:
    value = (image_value or "").strip()
    if value.startswith("data:image/"):
        match = re.match(r"^data:([^;]+);base64,(.+)$", value, flags=re.S)
        if not match:
            raise ImageProviderError("data URI تصویر نامعتبر است")
        return base64.b64decode(match.group(2), validate=False), match.group(1)
    if value.startswith("http://") or value.startswith("https://"):
        return _download_provider_image_url(value, timeout, provider_endpoint, provider_extra)
    if _looks_like_base64(value):
        return base64.b64decode(value, validate=False), "image/png"
    raise ImageProviderError("فرمت خروجی provider قابل خواندن نیست")


def _provider_eyebrow_mask_for_save(source_path: str, candidate: Dict[str, Any], size: Tuple[int, int]):
    """Return a resized eyebrow-only real mask so provider output cannot alter eyes/lashes."""
    try:
        from PIL import Image, ImageFilter
    except Exception as exc:
        raise ImageProviderError("برای محدودکردن خروجی AI به ابرو، Pillow لازم است") from exc

    detection = candidate.get("eyebrow_detection") if isinstance(candidate.get("eyebrow_detection"), dict) else {}
    if not detection or not detection.get("regions"):
        detection = final_design.ensure_eyebrow_detection(candidate)
    if not detection or not detection.get("regions"):
        raise ImageProviderError("خروجی AI پذیرفته نشد؛ محدوده واقعی دو ابرو روی عکس تشخیص داده نشد")
    if detection and detection.get("regions"):
        detection = ensure_eyebrow_mask(source_path, detection)
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
    # پوشش ابرو: برای حجاب کمی بازتر می‌کنیم تا تشخیص از دست نرود، ولی هاله سفید را جدا کنترل می‌کنیم
    if coverage <= 0 or coverage > 0.045:
        raise ImageProviderError("mask ابرو برای ذخیره خروجی AI ایمن نیست؛ محدوده ویرایش بیش از حد وسیع/نامعتبر است")
    # بررسی اینکه mask به لبه تصویر نچسبیده باشد (حجاب/پس‌زمینه) - برای حجاب کمی بازتر
    try:
        regions = detection.get("regions") if isinstance(detection, dict) else []
        for r in (regions or [])[:2]:
            x = float(r.get("x") or 0)
            y = float(r.get("y") or 0)
            w = float(r.get("width") or 0)
            h = float(r.get("height") or 0)
            # اگر ابرو خیلی بزرگ باشد، احتمال تشخیص اشتباه حجاب است - کمی بازتر برای حجاب
            if w > size[0] * 0.42 or h > size[1] * 0.16:
                raise ImageProviderError("mask ابرو بیش از حد بزرگ است؛ احتمال تشخیص اشتباه حجاب")
            if x < size[0] * 0.01 or (x + w) > size[0] * 0.99:
                raise ImageProviderError("mask ابرو به لبه تصویر چسبیده؛ نامعتبر")
            # برای حجاب، ابرو ممکن است کمی بالاتر یا پایین‌تر باشد - بازه بازتر
            if y < size[1] * 0.08 or y > size[1] * 0.60:
                raise ImageProviderError("mask ابرو خارج از محدوده معقول صورت است")
    except ImageProviderError:
        raise
    except Exception:
        pass
    try:
        mask = Image.open(mask_path).convert("L").resize(size, Image.Resampling.LANCZOS if hasattr(Image, "Resampling") else Image.LANCZOS)
        # Binary core + erosion کم برای جلوگیری از هاله سفید ولی نه خیلی زیاد که خط باریک شود
        mask = mask.point(lambda px: 255 if int(px) >= 128 else 0)
        # قبلاً 7 بود که mask دقیق 28px را به 22px می‌کرد و خط سفید می‌شد، الان 3
        try:
            mask = mask.filter(ImageFilter.MinFilter(size=3))
        except Exception:
            pass
        _beauty_log(
            "[EYEBROW_MASK]",
            "provider_mask_ready",
            method=detection.get("method") if isinstance(detection, dict) else "",
            mask_path=_upload_relative_path(mask_path),
            mask_size=f"{mask.size[0]}x{mask.size[1]}",
            coverage_ratio=coverage,
            real_mask=not bool(mask_info.get("is_fallback")),
            polarity=mask_info.get("polarity") or MASK_POLARITY,
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
    # بررسی ماسک سفید: اگر داخل ماسک خیلی سفید باشد، خروجی نامعتبر است (مشکل تصویر کاربر)
    white_inside = 0
    try:
        final_px_for_white = final_image.load()
        mask_px_for_white = mask.load()
        for y in range(0, height, stride):
            for x in range(0, width, stride):
                if int(mask_px_for_white[x, y]) >= 128:
                    r, g, b = final_px_for_white[x, y]
                    if r > 235 and g > 235 and b > 235:
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
                          provider_kind: str = "", provider_endpoint: str = "",
                          provider_extra: Optional[Dict[str, Any]] = None) -> Tuple[str, Dict[str, Any]]:
    if not source_path or candidate is None:
        raise ImageProviderError("عکس مبنا برای composite ایمن ابرو موجود نیست")
    raw, _mime = _decode_image_value(image_value, timeout, provider_endpoint, provider_extra)
    if not raw:
        raise ImageProviderError("تصویر خروجی خالی است")
    tmp_path = ""
    out_path = ""
    try:
        from PIL import Image
        from giso.buti_ai.image_validation import outside_mask_pixels_equal, save_lossless_webp

        provider_image = Image.open(BytesIO(raw)).convert("RGB")
        meta: Dict[str, Any] = {
            "provider_output_constrained_to_eyebrow_mask": False,
            "provider_raw_width": int(provider_image.width or 0),
            "provider_raw_height": int(provider_image.height or 0),
        }
        final_image = provider_image
        base_for_validation = None
        mask_for_validation = None
        # Provider output is never trusted outside the detected eyebrow mask, including Flux.
        base = Image.open(source_path).convert("RGB")
        base.thumbnail((MAX_SAVE_SIDE, MAX_SAVE_SIDE))
        fitted_provider = _fit_provider_image_to_source(provider_image, base.size).convert("RGB")
        mask, detection = _provider_eyebrow_mask_for_save(source_path, candidate, base.size)

        # The provider may change the whole frame; only its pixels under this binary mask survive.
        # Reject the known all-white failure mode before compositing, then verify the saved file.
        try:
            # بررسی پس‌زمینه سفید کلی در خروجی provider
            _w, _h = fitted_provider.size
            _total = max(1, _w * _h)
            _white_count = 0
            _stride_white = max(1, int((_total / 50000) ** 0.5))
            _fpx = fitted_provider.load()
            for _yy in range(0, _h, _stride_white):
                for _xx in range(0, _w, _stride_white):
                    _r, _g, _b = _fpx[_xx, _yy]
                    if _r > 242 and _g > 242 and _b > 242:
                        _white_count += 1
            _white_ratio_total = float(_white_count) / float(max(1, (_w // _stride_white) * (_h // _stride_white)))
            if _white_ratio_total > 0.55:
                raise ImageProviderError("خروجی AI پس‌زمینه سفید زیاد دارد و رد شد (مدل چهره جدید ساخت)")
            # تغییر بیرون از mask در raw provider قابل انتظار است؛ composite آن را دور می‌اندازد.
            try:
                _outside_metrics_before = _visible_eyebrow_diff_metrics(base, fitted_provider, mask)
                _beauty_log(
                    "[COMPOSITE]",
                    "pre_composite_outside_metrics",
                    outside_mean_delta=_outside_metrics_before.get("outside_mean_delta"),
                    outside_changed_ratio=_outside_metrics_before.get("outside_changed_ratio"),
                    inside_mean_delta=_outside_metrics_before.get("inside_mean_delta"),
                    white_ratio_total=round(_white_ratio_total, 4),
                    note="raw provider pixels outside the mask are discarded by deterministic composite",
                )
            except Exception:
                pass
        except ImageProviderError:
            raise
        except Exception:
            pass

        final_image = Image.composite(fitted_provider, base, mask)
        if not outside_mask_pixels_equal(base, final_image, mask):
            raise ImageProviderError("composite نهایی پیکسل‌های بیرون mask ابرو را دقیق حفظ نکرد")
        diff_meta = _validate_provider_visible_change(base, final_image, mask)
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
        if final_image.width <= 0 or final_image.height <= 0:
            raise ImageProviderError("ابعاد خروجی provider نامعتبر بود")
        os.makedirs(final_design.FINAL_DESIGN_DIR, exist_ok=True)
        # Lossless WebP keeps exact composite pixels while giving the browser a compact final asset.
        filename = f"final/ai_eyebrow_{datetime.utcnow().strftime('%Y%m%d%H%M%S')}_{uuid.uuid4().hex[:10]}.webp"
        out_path = os.path.join(final_design.EYEBROW_UPLOAD_DIR, filename)
        tmp_path = f"{out_path}.tmp-{uuid.uuid4().hex[:8]}.webp"
        save_lossless_webp(final_image, tmp_path)
        try:
            with Image.open(tmp_path) as saved_probe:
                saved_probe.verify()
            with Image.open(tmp_path) as saved_image:
                if saved_image.format != "WEBP":
                    raise ImageProviderError("فرمت فایل نهایی ابرو WebP نیست")
                saved_w, saved_h = saved_image.size
                if base_for_validation is not None and mask_for_validation is not None:
                    saved_rgb = saved_image.convert("RGB")
                    if not outside_mask_pixels_equal(base_for_validation, saved_rgb, mask_for_validation):
                        raise ImageProviderError("فایل WebP ذخیره‌شده پیکسل‌های بیرون mask ابرو را تغییر داده است")
                    saved_diff_meta = _validate_provider_visible_change(
                        base_for_validation,
                        saved_rgb,
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
            "final_format": "WEBP",
            "final_size_bytes": int(os.path.getsize(out_path)),
        })
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


def _attempt(provider: ImageProviderConfig, ok: bool, ms: int, error: str = "", timeout_seconds: Optional[int] = None) -> Dict[str, Any]:
    item = {
        "provider": provider.id,
        "label": provider.label,
        "kind": provider.kind,
        "model": provider.model,
        "ok": bool(ok),
        "ms": int(ms),
        "timeout_seconds": int(timeout_seconds) if timeout_seconds else None,
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
            "final_width", "final_height", "final_filename", "final_format", "final_size_bytes",
            "saved_file_diff_validated",
            "saved_eyebrow_roi_changed", "saved_outside_mask_preserved",
        ):
            if key in meta:
                item[key] = meta[key]
    if error:
        item["error"] = str(error)[:280]
    return item


def generate_final_design(candidate: Dict[str, Any], env: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
    """تولید طراحی عکس نهایی با providerهای تصویر و fallback پایتونی امن.

    اگر provider تصویر تنظیم نشده باشد یا همه providerها شکست بخورند، خروجی
    `generate_python_guided_design` ساخته می‌شود تا تجربه کاربر قطع نشود.
    """
    candidate = dict(candidate or {})
    source_path = final_design.source_image_path(candidate)
    if not source_path:
        _beauty_log("[FINAL]", "missing_source_photo", is_ai_generated=False, status="missing_photo")
        return {"ok": False, "message": "برای طراحی عکس نهایی، عکس واقعی لازم است.", "status": "missing_photo"}

    source_w, source_h = _image_size_for_log(source_path)
    _beauty_log(
        "[EYEBROW_PREVIEW]",
        "final_source_ready",
        original_path=_upload_relative_path(source_path) or os.path.basename(source_path),
        original_size=f"{source_w}x{source_h}",
        selected_style=candidate.get("final_style"),
        change_level=candidate.get("change_key"),
    )
    eyebrow_detection = final_design.ensure_eyebrow_detection(candidate)
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
    prompt = final_design.build_design_prompt(candidate)
    try:
        providers = configured_image_providers(env, service_key="eyebrow")
    except TypeError:
        # Backward-compatible for tests/older monkeypatches that only accepted env.
        providers = configured_image_providers(env)
    reference_path = _reference_image_path(candidate)
    timeout = _timeout_seconds(env)
    attempts: List[Dict[str, Any]] = []

    for provider in providers:
        started = time.monotonic()
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
            filename, save_meta = _save_provider_output(
                image_value, timeout, source_path, candidate,
                provider_kind=provider.kind, provider_endpoint=provider.endpoint,
                provider_extra=provider.extra,
            )
            if save_meta:
                last_meta = provider.extra.setdefault("_last_request_meta", {})
                for meta_key, meta_value in save_meta.items():
                    if meta_key in last_meta and (meta_key == "mask_used" or meta_key.startswith("mask_")):
                        continue
                    last_meta[meta_key] = meta_value
            ms = int((time.monotonic() - started) * 1000)
            attempt = _attempt(provider, True, ms, timeout_seconds=timeout)
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
                "final_width", "final_height", "final_filename", "final_format", "final_size_bytes",
                "saved_file_diff_validated",
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
            return result
        except Exception as exc:
            ms = int((time.monotonic() - started) * 1000)
            safe_error = _friendly_provider_error(exc)
            attempts.append(_attempt(provider, False, ms, safe_error, timeout_seconds=timeout))
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
            return fallback
    except Exception as exc:
        _beauty_log("[FINAL]", "python_fallback_failed", error=str(exc)[:120])

    # اگر حتی پایتونی هم شکست خورد -> AI FAILED
    _beauty_log(
        "[FINAL]",
        "ai_failed_all_providers",
        is_ai_generated=False,
        status="ai_failed",
        configured_provider_count=len(providers),
        attempts_count=len(attempts),
    )
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
    "DEFAULT_CLOUDFLARE_IMAGE_MODEL",
    "ImageProviderConfig",
    "configured_image_providers",
    "generate_final_design",
]
