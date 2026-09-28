# -*- coding: utf-8 -*-
"""ذخیره و آماده‌سازی عکس‌های آینه ابرو داخل محدوده Buti AI."""
import logging
import os
import uuid
from datetime import datetime

from giso.config import Config

logger = logging.getLogger("giso_buti_ai_eyebrow_upload")

ALLOWED_IMAGE_EXTENSIONS = {"jpg", "jpeg", "png", "webp"}
EYEBROW_UPLOAD_DIR = os.path.join(Config.GISO_DIR, "data", "uploads", "buti_ai", "eyebrow")


def missing_photo_status():
    return {"ok": False, "reason": "empty", "message": "عکسی انتخاب نشده است."}


def save_eyebrow_photo(file_storage, upload_dir=EYEBROW_UPLOAD_DIR):
    """ذخیره امن عکس MVP داخل محدوده runtime Buti AI؛ خروجی برای UI ساده است."""
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

    try:
        os.makedirs(upload_dir, exist_ok=True)
        safe_name = f"eyebrow_{datetime.utcnow().strftime('%Y%m%d%H%M%S')}_{uuid.uuid4().hex[:12]}.{ext}"
        path = os.path.join(upload_dir, safe_name)
        file_storage.save(path)

        # فشرده‌سازی سبک، مشابه مسیر آنالیز، ولی مستقل داخل Buti AI.
        try:
            from PIL import Image

            img = Image.open(path)
            img.thumbnail((1200, 1200))
            if ext in ("jpg", "jpeg"):
                if img.mode not in ("RGB", "L"):
                    img = img.convert("RGB")
                img.save(path, "JPEG", quality=86)
            elif ext == "png":
                img.save(path, "PNG")
            elif ext == "webp":
                img.save(path, "WEBP", quality=86)
        except Exception as exc:
            logger.debug("buti_ai eyebrow image resize skipped: %s", exc)

        return {"ok": True, "path": path, "filename": safe_name, "message": "عکس دریافت شد."}
    except Exception as exc:
        logger.error("Buti AI eyebrow photo save failed: %s", exc)
        return {"ok": False, "reason": "save_failed", "message": "ذخیره عکس انجام نشد. لطفاً دوباره تلاش کنید."}
