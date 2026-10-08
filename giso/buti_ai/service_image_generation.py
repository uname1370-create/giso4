# -*- coding: utf-8 -*-
"""Provider-backed final image generation for non-eyebrow آینه گیسو services.

The eyebrow service already has a mature image-generation chain. This module
keeps Nail/Lip/Hair on the same AI Management provider source while adding
service-specific ROI/mask/prompt/validation gates. If any real-AI gate fails,
the caller falls back to each service module's truthful Pillow guided output.
"""
from __future__ import annotations

import os
import time
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from giso.buti_ai.eyebrow import image_generation as shared_image


class ServiceImageGenerationError(RuntimeError):
    """Controlled provider/mask/validation failure for service final design."""


SERVICE_CONSTRAINTS: Dict[str, Dict[str, Any]] = {
    "lip_shading": {
        "safe_name": "lip",
        "status": "ai_lip_shading_ready",
        "message": "طراحی عکس نهایی لب با AI و ماسک اختصاصی لب آماده شد.",
        "fallback_message": "خروجی AI لب برای این عکس قابل تأیید نبود؛ نسخه راهنمای غیر AI فقط داخل محدوده لب نمایش داده می‌شود.",
        "min_in_ratio": 0.008,
        "max_out_ratio": 0.04,
        "max_mask_coverage": 0.075,
        "accept_fallback_mask": False,
        "mask_error": "mask واقعی لب برای ادعای AI آماده نیست.",
    },
    "nail": {
        "safe_name": "nail",
        "status": "ai_nail_design_ready",
        "message": "طراحی عکس نهایی ناخن با AI و ماسک صفحه ناخن آماده شد.",
        "fallback_message": "خروجی AI ناخن برای این عکس قابل تأیید نبود؛ نسخه راهنمای غیر AI فقط روی ناخن‌ها نمایش داده می‌شود.",
        "min_in_ratio": 0.006,
        "max_out_ratio": 0.045,
        "max_mask_coverage": 0.09,
        # Geometric nail masks are fallback only; real AI requires the
        # color-validated nail-plate mask from the service detector.
        "accept_fallback_mask": False,
        "mask_error": "mask واقعی صفحه ناخن برای ادعای AI آماده نیست.",
    },
    "hair_color": {
        "safe_name": "hair_color",
        "status": "ai_hair_color_ready",
        "message": "طراحی عکس نهایی رنگ و لایت مو با AI و ماسک اختصاصی مو آماده شد.",
        "fallback_message": "خروجی AI رنگ مو برای این عکس قابل تأیید نبود؛ نسخه راهنمای غیر AI فقط روی محدوده مو نمایش داده می‌شود.",
        "min_in_ratio": 0.006,
        "max_out_ratio": 0.05,
        "max_mask_coverage": 0.48,
        # Proportional hair masks are fallback only; real AI requires the
        # conservative color-segmentation mask that removes face/skin regions.
        "accept_fallback_mask": False,
        "mask_error": "mask واقعی مو برای ادعای AI آماده نیست.",
    },
}


def _source_path(module: Any, candidate: Dict[str, Any]) -> str:
    helper = getattr(module, "_source_path", None)
    if callable(helper):
        return str(helper(candidate) or "")
    filename = os.path.basename(str((candidate or {}).get("photo_filename") or ""))
    root = os.path.abspath(getattr(module, "UPLOAD_DIR"))
    path = os.path.abspath(os.path.join(root, filename))
    return path if path.startswith(root + os.sep) and os.path.exists(path) else ""


def _mask_path_and_info(detection: Dict[str, Any]) -> Tuple[str, Dict[str, Any]]:
    mask = detection.get("mask") if isinstance(detection.get("mask"), dict) else {}
    mask_path = str(mask.get("path") or detection.get("mask_path") or "").strip()
    return mask_path, mask


def _safe_mask_for_real_ai(service_key: str, detection: Dict[str, Any], mask_path: str) -> None:
    constraints = SERVICE_CONSTRAINTS[service_key]
    mask = detection.get("mask") if isinstance(detection.get("mask"), dict) else {}
    if not mask.get("ok") or not mask_path or not os.path.exists(mask_path):
        raise ServiceImageGenerationError(str(constraints["mask_error"]))
    if (mask.get("is_fallback") or detection.get("is_fallback") or mask.get("real_mask") is False) and not constraints.get("accept_fallback_mask"):
        raise ServiceImageGenerationError(str(constraints["mask_error"]))
    try:
        coverage = float(mask.get("coverage_ratio") or 0)
    except Exception:
        coverage = 0.0
    if coverage <= 0 or coverage > float(constraints.get("max_mask_coverage") or 1):
        raise ServiceImageGenerationError("mask خدمت برای AI واقعی ایمن/معتبر نیست.")


def _fit_to_size(image, size):
    return shared_image._fit_provider_image_to_source(image, size)


def _validation_ok(service_key: str, validation: Dict[str, Any]) -> bool:
    constraints = SERVICE_CONSTRAINTS[service_key]
    return bool(
        validation.get("ok")
        and validation.get("visible_in_mask_change")
        and validation.get("outside_preserved")
        and float(validation.get("in_mask_diff_ratio") if validation.get("in_mask_diff_ratio") is not None else 0)
        >= float(constraints["min_in_ratio"])
        and float(validation.get("outside_mask_diff_ratio") if validation.get("outside_mask_diff_ratio") is not None else 1)
        <= float(constraints["max_out_ratio"])
    )


def _save_constrained_provider_output(
    image_value: str,
    timeout: int,
    source_path: str,
    mask_path: str,
    module: Any,
    service_key: str,
    provider_endpoint: str = "",
    provider_extra: Optional[Dict[str, Any]] = None,
) -> Tuple[str, Dict[str, Any]]:
    from io import BytesIO
    from PIL import Image
    from giso.buti_ai.image_validation import (
        outside_mask_pixels_equal,
        save_lossless_webp,
        validate_masked_output,
    )

    raw, _mime = shared_image._decode_image_value(
        image_value, timeout, provider_endpoint, provider_extra
    )
    if not raw:
        raise ServiceImageGenerationError("تصویر خروجی AI خالی بود.")
    base = Image.open(source_path).convert("RGB")
    base.thumbnail((shared_image.MAX_SAVE_SIDE, shared_image.MAX_SAVE_SIDE))
    provider_image = Image.open(BytesIO(raw)).convert("RGB")
    provider_image = _fit_to_size(provider_image, base.size).convert("RGB")
    mask = Image.open(mask_path).convert("L")
    resample = Image.Resampling.LANCZOS if hasattr(Image, "Resampling") else Image.LANCZOS
    if mask.size != base.size:
        mask = mask.resize(base.size, resample)
    # Binary composite is deliberate: feathering can alter samples just outside the real mask.
    mask = mask.point(lambda px: 255 if int(px) >= 18 else 0)
    final_image = Image.composite(provider_image, base, mask).convert("RGB")
    if not outside_mask_pixels_equal(base, final_image, mask):
        raise ServiceImageGenerationError("composite خدمت پیکسل‌های بیرون mask را دقیق حفظ نکرد.")

    final_dir = getattr(module, "FINAL_DIR")
    upload_dir = getattr(module, "UPLOAD_DIR")
    os.makedirs(final_dir, exist_ok=True)
    safe_name = str(SERVICE_CONSTRAINTS[service_key]["safe_name"])
    filename = f"final/ai_{safe_name}_{datetime.utcnow().strftime('%Y%m%d%H%M%S')}_{shared_image.uuid.uuid4().hex[:10]}.webp"
    out_path = os.path.join(upload_dir, filename)
    tmp_path = f"{out_path}.tmp-{shared_image.uuid.uuid4().hex[:8]}.webp"
    try:
        save_lossless_webp(final_image, tmp_path)
        with Image.open(tmp_path) as probe:
            if probe.format != "WEBP":
                raise ServiceImageGenerationError("فایل نهایی خدمت WebP نیست.")
            probe.verify()
        with Image.open(tmp_path) as saved:
            if not outside_mask_pixels_equal(base, saved.convert("RGB"), mask):
                raise ServiceImageGenerationError("فایل WebP نهایی پیکسل‌های بیرون mask را تغییر داده است.")
        validation = validate_masked_output(source_path, tmp_path, mask_path, service_key=service_key)
        if not _validation_ok(service_key, validation):
            raise ServiceImageGenerationError("خروجی AI در محدوده خدمت یا حفظ بیرون mask تأیید نشد.")
        os.replace(tmp_path, out_path)
        meta = {
            "saved": True,
            "readable": True,
            "final_filename": filename,
            "final_format": "WEBP",
            "final_size_bytes": int(os.path.getsize(out_path)),
            "final_width": int(final_image.width or 0),
            "final_height": int(final_image.height or 0),
            "mask_used": True,
            "mask_filename": shared_image._upload_relative_path(mask_path, upload_dir=upload_dir),
            "provider_output_constrained_to_service_mask": True,
            "validation": validation,
            "visible_in_mask_change": True,
            "outside_preserved": True,
            "in_mask_diff_ratio": validation.get("in_mask_diff_ratio"),
            "outside_mask_diff_ratio": validation.get("outside_mask_diff_ratio"),
            "mask_coverage_ratio": validation.get("mask_coverage_ratio"),
        }
        return filename, meta
    finally:
        if os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except Exception:
                pass


def _prepare_png_image_and_mask(source_path: str, mask_path: str, max_side: int) -> Tuple[bytes, bytes, int, int, int, float]:
    """Return same-size PNG image/mask bytes for providers that accept masks."""
    from io import BytesIO
    from PIL import Image

    image = Image.open(source_path).convert("RGB")
    mask = Image.open(mask_path).convert("L")
    if mask.size != image.size:
        mask = mask.resize(image.size, Image.Resampling.NEAREST if hasattr(Image, "Resampling") else Image.NEAREST)
    w, h = image.size
    if w <= 0 or h <= 0:
        raise ServiceImageGenerationError("ابعاد عکس برای ارسال به AI نامعتبر است.")
    scale = min(1.0, float(max_side) / float(max(w, h)))
    if min(w, h) * scale < 256 and max_side >= 256:
        scale = max(scale, 256.0 / float(max(1, min(w, h))))
    new_w = shared_image._dimension_for_model(w * scale)
    new_h = shared_image._dimension_for_model(h * scale)
    if (new_w, new_h) != (w, h):
        resample = Image.Resampling.LANCZOS if hasattr(Image, "Resampling") else Image.LANCZOS
        image = image.resize((new_w, new_h), resample)
        mask = mask.resize((new_w, new_h), Image.Resampling.NEAREST if hasattr(Image, "Resampling") else Image.NEAREST)
    mask = mask.point(lambda px: 255 if int(px) >= 18 else 0)
    mask_pixels = sum(1 for px in mask.getdata() if px > 0)
    coverage = float(mask_pixels) / float(max(1, new_w * new_h))
    if mask_pixels <= 0:
        raise ServiceImageGenerationError("mask خدمت برای ارسال به AI خالی است.")
    image_out = BytesIO()
    mask_out = BytesIO()
    image.save(image_out, "PNG", optimize=True)
    mask.save(mask_out, "PNG", optimize=True)
    return image_out.getvalue(), mask_out.getvalue(), int(new_w), int(new_h), int(mask_pixels), round(coverage, 6)


def _data_uri(data: bytes, mime: str = "image/png") -> str:
    return "data:%s;base64,%s" % (mime, shared_image.base64.b64encode(data).decode("ascii"))


def _call_cloudflare_flux(provider: shared_image.ImageProviderConfig, service_key: str, source_path: str,
                          prompt: str, timeout: int) -> str:
    if str(provider.model or "").strip() != shared_image.DEFAULT_CLOUDFLARE_MODEL:
        raise ServiceImageGenerationError("این مدل Cloudflare برای طراحی عکس نهایی آینه گیسو با عکس ورودی پشتیبانی‌شده نیست.")
    width, height = shared_image._output_size_for_cloudflare(source_path)
    photo_bytes, photo_mime, photo_ext = shared_image._image_bytes_for_provider(source_path, shared_image.MAX_PROVIDER_INPUT_SIDE, square=False)
    guidance = str(provider.extra.get("guidance") or shared_image._env_value(None, "CLOUDFLARE_GUIDANCE") or "5")
    provider.extra["_last_request_meta"] = {
        "reference_image_sent": False,
        "cloudflare_request_format": f"multipart_{service_key}_prompt_input_image_0",
        "cloudflare_output_width": width,
        "cloudflare_output_height": height,
    }
    response = shared_image._post_request(
        provider.endpoint,
        disable_env_proxy=True,
        headers=shared_image._authorization_headers(provider),
        data={
            "prompt": f"{prompt} ROLE: IMAGE 0 is the original customer photo authority; do not use any other face/body source.",
            "guidance": guidance,
            "width": str(width),
            "height": str(height),
        },
        files={"input_image_0": (f"customer-{service_key}.{photo_ext}", photo_bytes, photo_mime)},
        timeout=timeout,
    )
    return shared_image._parse_response_image(response)


def _call_cloudflare_inpainting(provider: shared_image.ImageProviderConfig, service_key: str, source_path: str,
                                mask_path: str, candidate: Dict[str, Any], prompt: str, timeout: int) -> str:
    image_bytes, mask_bytes, width, height, mask_pixels, coverage = _prepare_png_image_and_mask(
        source_path,
        mask_path,
        shared_image.MAX_INPAINTING_INPUT_SIDE,
    )
    if coverage > float(SERVICE_CONSTRAINTS[service_key].get("max_mask_coverage") or 1):
        raise ServiceImageGenerationError("mask خدمت برای inpainting بیش از حد وسیع است.")
    guidance = float(provider.extra.get("guidance") or shared_image._env_value(None, "CLOUDFLARE_INPAINTING_GUIDANCE") or 7.5)
    strength = float(provider.extra.get("strength") or shared_image._env_value(None, "CLOUDFLARE_INPAINTING_STRENGTH") or 0.72)
    try:
        num_steps = int(provider.extra.get("num_steps") or shared_image._env_value(None, "CLOUDFLARE_INPAINTING_STEPS") or 20)
    except Exception:
        num_steps = 20
    payload = {
        "prompt": (
            f"{prompt} Apply the selected service result only inside the uploaded inpainting mask. "
            "Mask polarity: white pixels are editable, black pixels must remain unchanged."
        ),
        "negative_prompt": (
            "changed identity, changed face shape, changed skin outside mask, changed teeth, changed eyes, "
            "changed clothes, changed background, distorted anatomy, cartoon, illustration, beauty filter outside mask"
        ),
        "image": list(image_bytes),
        "mask": list(mask_bytes),
        "width": width,
        "height": height,
        "num_steps": max(1, min(20, num_steps)),
        "strength": max(0.05, min(1.0, strength)),
        "guidance": guidance,
    }
    detection = candidate.get("detection") if isinstance(candidate.get("detection"), dict) else {}
    provider.extra["_last_request_meta"] = {
        "ai_inpainting": True,
        "mask_used": True,
        "mask_width": width,
        "mask_height": height,
        "mask_pixels": mask_pixels,
        "mask_coverage_ratio": coverage,
        "mask_polarity": "white_edit_black_keep",
        "mask_source_method": detection.get("method") if isinstance(detection, dict) else "",
        "mask_filename": shared_image._upload_relative_path(mask_path),
        "cloudflare_request_format": "json_image_and_service_mask_byte_arrays",
    }
    response = shared_image._post_request(
        provider.endpoint,
        disable_env_proxy=True,
        headers={**shared_image._authorization_headers(provider), "Content-Type": "application/json"},
        json=payload,
        timeout=timeout,
    )
    return shared_image._parse_response_image(response)


def _call_openai_image_edit(provider: shared_image.ImageProviderConfig, source_path: str, mask_path: str, prompt: str, timeout: int) -> str:
    image_bytes, mask_bytes, _w, _h, _pixels, _coverage = _prepare_png_image_and_mask(source_path, mask_path, 1024)
    data = {"prompt": prompt, "n": "1"}
    if provider.model:
        data["model"] = provider.model
    size = str(provider.extra.get("size") or "").strip()
    if size:
        data["size"] = size
    response_format = str(provider.extra.get("response_format") or "b64_json").strip()
    if response_format:
        data["response_format"] = response_format
    response = shared_image.requests.post(
        provider.endpoint,
        headers=shared_image._authorization_headers(provider),
        data=data,
        files={
            "image": ("customer-photo.png", image_bytes, "image/png"),
            "mask": ("service-mask.png", mask_bytes, "image/png"),
        },
        timeout=timeout,
    )
    return shared_image._parse_response_image(response)


def _call_generic_multipart(provider: shared_image.ImageProviderConfig, service_key: str, source_path: str,
                            mask_path: str, candidate: Dict[str, Any], prompt: str, timeout: int) -> str:
    image_bytes, mask_bytes, _w, _h, _pixels, _coverage = _prepare_png_image_and_mask(source_path, mask_path, 1024)
    data = {
        "prompt": prompt,
        "service": service_key,
        "style": str(candidate.get("final_label") or candidate.get("final_style") or ""),
        "style_key": str(candidate.get("final_style") or ""),
        "mask_polarity": "white_edit_black_keep",
    }
    if provider.model:
        data["model"] = provider.model
    response = shared_image.requests.post(
        provider.endpoint,
        headers=shared_image._authorization_headers(provider),
        data=data,
        files={
            "image": ("customer-photo.png", image_bytes, "image/png"),
            "mask": ("service-mask.png", mask_bytes, "image/png"),
        },
        timeout=timeout,
    )
    return shared_image._parse_response_image(response)


def _call_json_image(provider: shared_image.ImageProviderConfig, service_key: str, source_path: str,
                     mask_path: str, candidate: Dict[str, Any], prompt: str, timeout: int) -> str:
    image_bytes, mask_bytes, _w, _h, _pixels, coverage = _prepare_png_image_and_mask(source_path, mask_path, 1024)
    detection = candidate.get("detection") if isinstance(candidate.get("detection"), dict) else {}
    payload: Dict[str, Any] = {
        "prompt": prompt,
        "service": service_key,
        "styleKey": str(candidate.get("final_style") or ""),
        "style": str(candidate.get("final_label") or ""),
        "regions": detection.get("regions") if isinstance(detection.get("regions"), list) else [],
        "maskPolarity": "white_edit_black_keep",
        "maskCoverage": coverage,
        "imageBase64": _data_uri(image_bytes, "image/png"),
        "maskBase64": _data_uri(mask_bytes, "image/png"),
    }
    if provider.model:
        payload["model"] = provider.model
    response = shared_image.requests.post(
        provider.endpoint,
        headers={**shared_image._authorization_headers(provider), "Content-Type": "application/json"},
        json=payload,
        timeout=timeout,
    )
    return shared_image._parse_response_image(response)


def _call_provider(provider: shared_image.ImageProviderConfig, source_path: str, mask_path: str,
                   candidate: Dict[str, Any], prompt: str, timeout: int) -> str:
    """Call provider using service-specific prompt and mask where supported."""
    service_key = str(candidate.get("service_key") or "").strip().lower()
    kind = shared_image._cloudflare_kind_for_model(provider.model, provider.kind) if (provider.kind or "").strip().lower().startswith("cloudflare") else (provider.kind or "").strip().lower()
    provider.kind = kind
    provider.extra.pop("_last_request_meta", None)
    if kind == "cloudflare":
        return _call_cloudflare_flux(provider, service_key, source_path, prompt, timeout)
    if kind in shared_image.CLOUDFLARE_INPAINTING_KINDS:
        return _call_cloudflare_inpainting(provider, service_key, source_path, mask_path, candidate, prompt, timeout)
    if kind in {"openai_image_edit", "openai_edit", "images_edit"}:
        return _call_openai_image_edit(provider, source_path, mask_path, prompt, timeout)
    if kind in {"multipart", "form", "form_data"}:
        return _call_generic_multipart(provider, service_key, source_path, mask_path, candidate, prompt, timeout)
    if kind in {"json", "json_image", "data_uri"}:
        return _call_json_image(provider, service_key, source_path, mask_path, candidate, prompt, timeout)
    raise ServiceImageGenerationError(f"نوع provider پشتیبانی نمی‌شود: {kind or 'unknown'}")


def generate_final_design(service_key: str, module: Any, candidate: Dict[str, Any],
                          env: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
    service_key = str(service_key or "").strip().lower()
    if service_key not in SERVICE_CONSTRAINTS:
        return module.generate_guided_design(candidate or {})
    candidate = dict(candidate or {})
    source_path = _source_path(module, candidate)
    if not source_path:
        return {"ok": False, "status": "missing_photo", "message": "برای طراحی عکس نهایی، عکس واقعی لازم است."}

    # Final is the security boundary: do not reuse an upload-time detection.
    # A stale/fallback mask must never reach a real-AI provider.
    try:
        detection = module.detect_regions(source_path, allow_fallback=False)
    except Exception as exc:
        detection = {}
        attempts_for_mask = [{"ok": False, "stage": "mask", "error": str(exc)[:220]}]
    else:
        attempts_for_mask = []
    if hasattr(module, "refine_detection_for_style"):
        try:
            detection = module.refine_detection_for_style(source_path, detection, candidate.get("final_style") or candidate.get("selected_style") or "")
        except Exception:
            pass
    candidate["detection"] = detection
    mask_path, mask_info = _mask_path_and_info(detection)
    try:
        providers = shared_image.configured_image_providers(env, service_key=service_key)
    except TypeError:
        providers = shared_image.configured_image_providers(env)
    prompt = module.build_design_prompt(candidate) if hasattr(module, "build_design_prompt") else "Photorealistic beauty service image edit. Preserve all pixels outside the provided mask."
    attempts: List[Dict[str, Any]] = list(attempts_for_mask)
    timeout = shared_image._timeout_seconds(env)

    mask_ready_for_real_ai = bool(providers)
    mask_error = ""
    if providers:
        try:
            _safe_mask_for_real_ai(service_key, detection, mask_path)
        except Exception as exc:
            mask_ready_for_real_ai = False
            mask_error = str(exc)[:220]
            attempts.append({"ok": False, "stage": "mask", "error": mask_error})

    for provider in (providers if mask_ready_for_real_ai else []):
        started = time.monotonic()
        try:
            image_value = _call_provider(provider, source_path, mask_path, candidate, prompt, timeout)
            filename, meta = _save_constrained_provider_output(
                image_value, timeout, source_path, mask_path, module, service_key,
                provider_endpoint=provider.endpoint, provider_extra=provider.extra,
            )
            ms = int((time.monotonic() - started) * 1000)
            attempt = shared_image._attempt(provider, True, ms, timeout_seconds=timeout)
            attempt.update({k: v for k, v in meta.items() if k != "validation"})
            attempts.append(attempt)
            result = {
                "ok": True,
                "filename": filename,
                "provider": provider.id,
                "provider_label": provider.label,
                "kind": provider.kind,
                "model": provider.model,
                "status": SERVICE_CONSTRAINTS[service_key]["status"],
                "prompt": prompt,
                "service_key": service_key,
                "detection": detection,
                "attempts": attempts,
                "fallback_used": False,
                "configured_provider_count": len(providers),
                "ai_inpainting": provider.kind in shared_image.CLOUDFLARE_INPAINTING_KINDS,
                "is_ai_generated": True,
                "message": SERVICE_CONSTRAINTS[service_key]["message"],
            }
            result.update(meta)
            return result
        except Exception as exc:
            ms = int((time.monotonic() - started) * 1000)
            attempts.append(shared_image._attempt(provider, False, ms, shared_image._friendly_provider_error(exc), timeout_seconds=timeout))

    fallback = module.generate_guided_design(candidate)
    fallback["attempts"] = attempts
    fallback["configured_provider_count"] = len(providers)
    if mask_error:
        fallback["real_ai_blocked_reason"] = mask_error
    fallback["fallback_used"] = bool(attempts)
    fallback["prompt"] = prompt
    fallback["ai_inpainting"] = False
    fallback["is_ai_generated"] = False
    fallback["fallback_type"] = "non_ai_guided_fallback"
    if fallback.get("ok"):
        fallback["status"] = "non_ai_guided_fallback_ready" if attempts else "non_ai_guided_preview_ready"
        if attempts:
            fallback["message"] = SERVICE_CONSTRAINTS[service_key]["fallback_message"]
    return fallback


__all__ = ["generate_final_design"]
