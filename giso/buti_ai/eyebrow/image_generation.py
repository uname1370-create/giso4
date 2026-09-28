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
from giso.buti_ai.eyebrow.options import normalize_style_key

logger = logging.getLogger("giso_buti_ai_image_generation")

DEFAULT_CLOUDFLARE_MODEL = "@cf/black-forest-labs/flux-2-klein-4b"
DEFAULT_TIMEOUT_SECONDS = 90
MAX_DOWNLOAD_BYTES = 12 * 1024 * 1024
MAX_SAVE_SIDE = 1600
MAX_PROVIDER_INPUT_SIDE = 512


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


def _env_value(env: Optional[Dict[str, str]], key: str, default: str = "") -> str:
    source = env if env is not None else os.environ
    return str(source.get(key, default) or "").strip()


def _truthy(value: Any) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "on", "y"}


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
                kind="cloudflare",
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


def _ai_management_providers() -> List[ImageProviderConfig]:
    """خواندن مدل‌های تصویرسازی آینه ابرو از مدیریت AI سوپرادمین."""
    try:
        from giso.buti_ai.ai_models import configured_image_provider_dicts
    except Exception as exc:
        logger.debug("Buti AI management image providers unavailable: %s", exc)
        return []
    providers: List[ImageProviderConfig] = []
    for item in configured_image_provider_dicts(limit=3):
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


def configured_image_providers(env: Optional[Dict[str, str]] = None) -> List[ImageProviderConfig]:
    """برگرداندن providerهای تصویرسازی فعال؛ بدون لو دادن کلیدها.

    در اجرای واقعی (`env is None`) اول تنظیمات پنل «مدیریت AI» خوانده می‌شود.
    در تست‌ها/فراخوانی‌های env-محور، رفتار قدیمی ثابت می‌ماند.
    """
    providers: List[ImageProviderConfig] = []
    if env is None:
        providers.extend(_ai_management_providers())
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
    scale = min(1.0, 1536.0 / max(w, h))
    out_w = int(round((w * scale) / 8) * 8)
    out_h = int(round((h * scale) / 8) * 8)
    return max(256, min(1536, out_w)), max(256, min(1536, out_h))


def _reference_image_path(candidate: Dict[str, Any]) -> str:
    style = normalize_style_key((candidate or {}).get("final_style"))
    base = os.path.abspath(os.path.join(os.path.dirname(os.path.dirname(__file__)), "static", "brows"))
    path = os.path.abspath(os.path.join(base, f"{style}.jpg"))
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
    width, height = _output_size_for_cloudflare(source_path)
    photo_bytes, photo_mime, photo_ext = _image_bytes_for_provider(source_path, MAX_PROVIDER_INPUT_SIDE, square=False)
    files = {
        "input_image_0": (f"customer-face.{photo_ext}", photo_bytes, photo_mime),
    }
    if reference_path:
        ref_bytes, ref_mime, ref_ext = _image_bytes_for_provider(reference_path, MAX_PROVIDER_INPUT_SIDE, square=True)
        files["input_image_1"] = (f"technique-macro.{ref_ext}", ref_bytes, ref_mime)

    guidance = str(provider.extra.get("guidance") or _env_value(None, "CLOUDFLARE_GUIDANCE") or "5")
    data = {
        "prompt": (
            f"{prompt} ROLE: IMAGE 0 is the customer-face authority; "
            "IMAGE 1 if present is only a technique swatch, never a face source."
        ),
        "guidance": guidance,
        "width": str(width),
        "height": str(height),
    }
    response = requests.post(
        provider.endpoint,
        headers=_authorization_headers(provider),
        data=data,
        files=files,
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
    kind = (provider.kind or "").strip().lower()
    if kind == "cloudflare":
        return _call_cloudflare(provider, source_path, reference_path, prompt, timeout)
    if kind in {"openai_image_edit", "openai_edit", "images_edit"}:
        return _call_openai_image_edit(provider, source_path, prompt, timeout)
    if kind in {"multipart", "form", "form_data"}:
        return _call_generic_multipart(provider, source_path, reference_path, prompt, timeout)
    if kind in {"json", "json_image", "data_uri"}:
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


def _save_provider_output(image_value: str, timeout: int) -> str:
    raw, _mime = _decode_image_value(image_value, timeout)
    if not raw:
        raise ImageProviderError("تصویر خروجی خالی است")
    try:
        from PIL import Image

        image = Image.open(BytesIO(raw)).convert("RGB")
        image.thumbnail((MAX_SAVE_SIDE, MAX_SAVE_SIDE))
        os.makedirs(final_design.FINAL_DESIGN_DIR, exist_ok=True)
        filename = f"final/ai_eyebrow_{datetime.utcnow().strftime('%Y%m%d%H%M%S')}_{uuid.uuid4().hex[:10]}.jpg"
        out_path = os.path.join(final_design.EYEBROW_UPLOAD_DIR, filename)
        image.save(out_path, "JPEG", quality=90, optimize=True)
        return filename
    except ImageProviderError:
        raise
    except Exception as exc:
        raise ImageProviderError(f"خروجی provider تصویر معتبر نبود: {str(exc)[:120]}") from exc


def _attempt(provider: ImageProviderConfig, ok: bool, ms: int, error: str = "") -> Dict[str, Any]:
    item = {
        "provider": provider.id,
        "label": provider.label,
        "kind": provider.kind,
        "model": provider.model,
        "ok": bool(ok),
        "ms": int(ms),
    }
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
        return {"ok": False, "message": "برای طراحی عکس نهایی، عکس واقعی لازم است.", "status": "missing_photo"}

    eyebrow_detection = final_design.ensure_eyebrow_detection(candidate)
    prompt = final_design.build_design_prompt(candidate)
    providers = configured_image_providers(env)
    reference_path = _reference_image_path(candidate)
    timeout = _timeout_seconds(env)
    attempts: List[Dict[str, Any]] = []

    for provider in providers:
        started = time.monotonic()
        try:
            image_value = _call_provider(provider, source_path, reference_path, candidate, prompt, timeout)
            filename = _save_provider_output(image_value, timeout)
            ms = int((time.monotonic() - started) * 1000)
            attempts.append(_attempt(provider, True, ms))
            return {
                "ok": True,
                "filename": filename,
                "provider": provider.id,
                "provider_label": provider.label,
                "model": provider.model,
                "status": "ai_final_ready",
                "prompt": prompt,
                "eyebrow_detection_method": eyebrow_detection.get("method") if isinstance(eyebrow_detection, dict) else "",
                "eyebrow_detection": eyebrow_detection,
                "attempts": attempts,
                "fallback_used": False,
                "configured_provider_count": len(providers),
                "message": "طراحی عکس نهایی با مدل تصویرسازی آماده شد.",
            }
        except Exception as exc:
            ms = int((time.monotonic() - started) * 1000)
            safe_error = str(exc)[:280] or "provider failed"
            attempts.append(_attempt(provider, False, ms, safe_error))
            logger.info(
                "Buti AI image provider failed provider=%s model=%s ms=%s error=%s",
                provider.id,
                provider.model,
                ms,
                safe_error[:160],
            )

    fallback = final_design.generate_python_guided_design(candidate)
    fallback["attempts"] = attempts
    fallback["configured_provider_count"] = len(providers)
    fallback["fallback_used"] = bool(providers)
    fallback["prompt"] = prompt
    if fallback.get("ok"):
        if providers:
            fallback["status"] = "guided_fallback_ready"
            fallback["message"] = "مدل‌های تصویرسازی فعلاً جواب ندادند؛ عکس و انتخاب شما حفظ شد و نسخه راهنمای امن نمایش داده می‌شود. کمی بعد می‌توانید دوباره تلاش کنید."
        else:
            fallback["status"] = "guided_final_ready"
            fallback["message"] = "مدل تصویرسازی هنوز در مدیریت AI تنظیم نشده؛ عکس و انتخاب شما حفظ شد و نسخه راهنمای امن آماده شد."
    elif providers:
        fallback["message"] = "فعلاً طراحی عکس نهایی آماده نشد؛ عکس و انتخاب شما حفظ شد. لطفاً چند دقیقه بعد دوباره تلاش کنید."
    return fallback


__all__ = [
    "ImageProviderConfig",
    "configured_image_providers",
    "generate_final_design",
]
