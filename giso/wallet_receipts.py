# -*- coding: utf-8 -*-
"""ذخیره خصوصی و امن تصویر رسید افزایش موجودی کیف پول.

رسیدها عمداً زیر ``static`` ذخیره نمی‌شوند؛ فقط route سوپرادمین آن‌ها را
پس از احراز دسترسی با ``send_file`` تحویل می‌دهد.
"""
from io import BytesIO
import logging
import os
from pathlib import Path
import re
import secrets

logger = logging.getLogger("giso_wallet_receipts")
ALLOWED_RECEIPT_EXTENSIONS = {"jpg", "jpeg", "png"}
MAX_RECEIPT_BYTES = 5 * 1024 * 1024
MAX_RECEIPT_PIXELS = 20_000_000
_SAFE_STORED_NAME = re.compile(r"^[a-f0-9]{32}\.(?:jpg|png)$")


class ReceiptValidationError(ValueError):
    """خطای ورودی قابل نمایش برای فایل رسید نامعتبر."""


def receipt_directory() -> Path:
    path = Path(__file__).resolve().parent / "data" / "wallet_receipts"
    path.mkdir(parents=True, exist_ok=True, mode=0o700)
    try:
        path.chmod(0o700)
    except OSError:
        pass
    return path


def save_topup_receipt(file_storage, user_id: int) -> str:
    """اعتبارسنجی و بازکدگذاری JPG/PNG؛ خروجی فقط نام تصادفی فایل است."""
    if not file_storage or not getattr(file_storage, "filename", ""):
        raise ReceiptValidationError("تصویر رسید پرداخت الزامی است.")
    original_name = os.path.basename(str(file_storage.filename or ""))
    extension = original_name.rsplit(".", 1)[-1].lower() if "." in original_name else ""
    if extension not in ALLOWED_RECEIPT_EXTENSIONS:
        raise ReceiptValidationError("فرمت رسید فقط باید JPG، JPEG یا PNG باشد.")

    stream = getattr(file_storage, "stream", file_storage)
    try:
        stream.seek(0)
    except Exception:
        pass
    data = stream.read(MAX_RECEIPT_BYTES + 1)
    if not data:
        raise ReceiptValidationError("فایل رسید خالی است.")
    if len(data) > MAX_RECEIPT_BYTES:
        raise ReceiptValidationError("حجم تصویر رسید نباید بیشتر از ۵ مگابایت باشد.")

    try:
        from PIL import Image, UnidentifiedImageError
        probe = Image.open(BytesIO(data))
        width, height = probe.size
        if width < 32 or height < 32:
            raise ReceiptValidationError("ابعاد تصویر رسید معتبر نیست.")
        if width * height > MAX_RECEIPT_PIXELS:
            raise ReceiptValidationError("ابعاد تصویر رسید بیش از حد بزرگ است.")
        probe.verify()
        detected = str(probe.format or "").upper()
        expected = "PNG" if extension == "png" else "JPEG"
        if detected != expected:
            raise ReceiptValidationError("پسوند فایل رسید با محتوای تصویر مطابقت ندارد.")
        image = Image.open(BytesIO(data))
        image.load()
        stored_extension = "png" if detected == "PNG" else "jpg"
        stored_name = f"{secrets.token_hex(16)}.{stored_extension}"
        target = receipt_directory() / stored_name
        if stored_extension == "jpg":
            image.convert("RGB").save(target, format="JPEG", quality=90, optimize=True)
        else:
            image.save(target, format="PNG", optimize=True)
        try:
            target.chmod(0o600)
        except OSError:
            pass
        return stored_name
    except ReceiptValidationError:
        raise
    except (UnidentifiedImageError, OSError, ValueError):
        raise ReceiptValidationError("فایل انتخاب‌شده یک تصویر سالم JPG یا PNG نیست.")
    except Exception as exc:
        logger.exception("receipt image processing failed: %s", exc)
        raise ReceiptValidationError("پردازش تصویر رسید ناموفق بود؛ دوباره تلاش کنید.")


def receipt_file_path(stored_name: str) -> Path:
    """resolve امن نام ذخیره‌شده؛ path دلخواه دیتابیس پذیرفته نمی‌شود."""
    name = str(stored_name or "").strip().lower()
    if not _SAFE_STORED_NAME.fullmatch(name):
        raise FileNotFoundError("invalid receipt path")
    path = receipt_directory() / name
    if not path.is_file():
        raise FileNotFoundError(name)
    return path


def remove_topup_receipt(stored_name: str) -> None:
    """پاک‌سازی فایل orphan در صورت شکست ثبت دیتابیس."""
    try:
        path = receipt_file_path(stored_name)
        path.unlink(missing_ok=True)
    except FileNotFoundError:
        pass
    except Exception as exc:
        logger.warning("orphan receipt cleanup failed: %s", exc)


__all__ = [
    "ALLOWED_RECEIPT_EXTENSIONS", "MAX_RECEIPT_BYTES", "MAX_RECEIPT_PIXELS", "ReceiptValidationError",
    "save_topup_receipt", "receipt_file_path", "remove_topup_receipt",
]
