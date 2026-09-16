# -*- coding: utf-8 -*-
"""
phoneutil.py — ابزار مشترک نرمال‌سازی شماره موبایل ایران.

همه بخش‌های پروژه (بات، giso، سایت) از همین تابع استفاده می‌کنند تا فرمت
یکپارچه و بدون تکرار منطق داشته باشند.

ورودی‌های پذیرفته‌شده:
    09xxxxxxxxx
    9xxxxxxxxx
    989xxxxxxxxx
    +989xxxxxxxxx
    00989xxxxxxxxx
    ارقام فارسی/عربی و کاراکترهای فاصله/خط‌تیره هم نرمال می‌شوند.

خروجی: فرمت استاندارد «+989xxxxxxxxx» یا رشته خالی در صورت نامعتبر.
"""
import re

# نگاشت ارقام فارسی/عربی به انگلیسی
_DIGIT_MAP = str.maketrans(
    "۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩",
    "01234567890123456789",
)


def normalize_phone(raw) -> str:
    """نرمال‌سازی و اعتبارسنجی شماره موبایل ایران.

    خروجی در فرمت استاندارد «+989xxxxxxxxx»؛ در صورت نامعتبر، رشتهٔ خالی «» برمی‌گرداند.
    """
    if raw is None:
        return ""
    s = str(raw).strip().translate(_DIGIT_MAP)
    # حذف فاصله، خط‌تیره، پرانتز
    s = re.sub(r"[\s\-()]", "", s)
    if not s:
        return ""
    if s.startswith("0098"):
        s = "+98" + s[4:]
    if s.startswith("+98"):
        rest = s[3:]
    elif s.startswith("98") and len(s) == 12:
        rest = s[2:]
    elif s.startswith("0"):
        rest = s[1:]
    else:
        rest = s
    # rest باید دقیقاً ۱۰ رقم و با ۹ شروع شود
    if len(rest) == 10 and rest.isdigit() and rest.startswith("9"):
        return "+98" + rest
    return ""


def phone_equal(a: str, b: str) -> bool:
    """مقایسهٔ دو شماره مستقل از فرمت ورودی."""
    na = normalize_phone(a)
    nb = normalize_phone(b)
    return bool(na) and na == nb


def phone_display(normalized: str) -> str:
    """تبدیل فرمت استاندارد (+989...) به فرمت نمایشی 09..."""
    s = normalize_phone(normalized)
    if not s:
        return ""
    return "0" + s[3:]  # +989xx → 09xx
