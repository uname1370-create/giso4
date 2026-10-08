# -*- coding: utf-8 -*-
"""ذخیره و آماده‌سازی عکس‌های آینه ابرو داخل محدوده Buti AI."""
import io
import logging
import os
import uuid
import warnings
from datetime import datetime

from giso.config import Config

logger = logging.getLogger("giso_buti_ai_eyebrow_upload")

ALLOWED_IMAGE_EXTENSIONS = {"jpg", "jpeg", "png", "webp"}
ALLOWED_IMAGE_FORMATS = {"JPEG", "PNG", "WEBP"}
MAX_UPLOAD_BYTES = 8 * 1024 * 1024
MAX_IMAGE_SIDE = 6000
MAX_IMAGE_PIXELS = 24_000_000
EYEBROW_UPLOAD_DIR = os.path.join(Config.GISO_DIR, "data", "uploads", "buti_ai", "eyebrow")


def missing_photo_status():
    return {"ok": False, "reason": "empty", "message": "عکسی انتخاب نشده است."}


def _read_upload_bytes(file_storage):
    try:
        raw = file_storage.read(MAX_UPLOAD_BYTES + 1)
    finally:
        try:
            file_storage.seek(0)
        except Exception:
            pass
    return raw or b""


def save_eyebrow_photo(file_storage, upload_dir=EYEBROW_UPLOAD_DIR, prefix="eyebrow"):
    """ذخیره امن عکس واقعی داخل runtime Buti AI؛ فقط JPG/PNG/WebP معتبر پذیرفته می‌شود."""
    if not file_storage or not getattr(file_storage, "filename", ""):
        return missing_photo_status()

    filename = file_storage.filename or ""
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if ext not in ALLOWED_IMAGE_EXTENSIONS:
        return {
            "ok": False,
            "reason": "bad_extension",
            "message": "فرمت عکس باید jpg، png یا webp باشد.",
        }

    raw = _read_upload_bytes(file_storage)
    if not raw:
        return missing_photo_status()
    if len(raw) > MAX_UPLOAD_BYTES:
        return {
            "ok": False,
            "reason": "too_large",
            "message": "حجم عکس باید کمتر از ۸ مگابایت باشد.",
        }

    try:
        from PIL import Image, ImageOps

        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            probe = Image.open(io.BytesIO(raw))
            source_format = str(probe.format or "").upper()
            width, height = int(probe.width or 0), int(probe.height or 0)
            if source_format not in ALLOWED_IMAGE_FORMATS:
                return {
                    "ok": False,
                    "reason": "bad_content",
                    "message": "فایل تصویر معتبر نیست. فقط عکس واقعی JPG، PNG یا WebP بفرست.",
                }
            if width < 1 or height < 1 or max(width, height) > MAX_IMAGE_SIDE or width * height > MAX_IMAGE_PIXELS:
                return {
                    "ok": False,
                    "reason": "bad_dimensions",
                    "message": "ابعاد عکس بیش از حد مجاز است.",
                }
            if bool(getattr(probe, "is_animated", False)) or int(getattr(probe, "n_frames", 1) or 1) != 1:
                return {
                    "ok": False,
                    "reason": "animated",
                    "message": "تصویر متحرک برای تحلیل پذیرفته نمی‌شود.",
                }
            probe.verify()

        image = Image.open(io.BytesIO(raw))
        image = ImageOps.exif_transpose(image)
        image.load()
        image = image.convert("RGB")
        image.thumbnail((1200, 1200))

        os.makedirs(upload_dir, exist_ok=True)
        safe_prefix = "".join(ch for ch in str(prefix or "eyebrow").lower() if ch.isalnum() or ch in ("_", "-"))[:32] or "eyebrow"
        safe_name = f"{safe_prefix}_{datetime.utcnow().strftime('%Y%m%d%H%M%S')}_{uuid.uuid4().hex[:12]}.jpg"
        path = os.path.join(upload_dir, safe_name)
        image.save(path, "JPEG", quality=86, optimize=True, exif=b"")
        return {"ok": True, "path": path, "filename": safe_name, "message": "عکس دریافت شد."}
    except Exception as exc:
        logger.debug("Buti AI eyebrow image validation failed: %s", str(exc)[:160])
        return {
            "ok": False,
            "reason": "bad_content",
            "message": "فایل تصویر معتبر نیست. فقط عکس واقعی JPG، PNG یا WebP بفرست.",
        }
