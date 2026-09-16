# -*- coding: utf-8 -*-
"""
giso/phones.py — نرمال‌سازی شماره و تاریخ فارسی (Phase 2, Unit U2)
استخراج‌شده از giso/base.py بدون تغییر رفتار؛ نام‌ها در giso.base re-export می‌شوند.
"""
import re
from datetime import datetime

_DIGIT_MAP = str.maketrans(
    "۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩",
    "01234567890123456789",
)


def normalize_phone(raw) -> str:
    """Iranian mobile → +989xxxxxxxxx یا ''."""
    try:
        from phoneutil import normalize_phone as _np
        return _np(raw)
    except Exception:
        pass
    if not raw:
        return ""
    s = str(raw).strip().translate(_DIGIT_MAP)
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
    if len(rest) == 10 and rest.isdigit() and rest.startswith("9"):
        return "+98" + rest
    return ""


def _phone_variants(phone: str) -> list:
    if not phone:
        return []
    digits = re.sub(r"[^\d]", "", str(phone))
    if not digits:
        return [str(phone)]
    if digits.startswith("98") and len(digits) >= 12:
        local = "0" + digits[2:]
        intl = "+" + digits
    elif digits.startswith("0"):
        local = digits
        intl = "+98" + digits[1:]
    else:
        local = "0" + digits
        intl = "+98" + digits
    return list({str(phone), digits, local, intl})


def _fa_num(val) -> str:
    s = str(val)
    en = "0123456789"
    fa = "۰۱۲۳۴۵۶۷۸۹"
    return s.translate(str.maketrans(en, fa))


fa_num = _fa_num


def display_phone(raw) -> str:
    """نمایش موبایل ایران به‌صورت ۱۱ رقم: 09xxxxxxxxx."""
    if raw is None:
        return "—"
    n = normalize_phone(raw)
    if n.startswith("+98") and len(n) >= 13:
        return "0" + n[3:13]
    s = str(raw).strip().translate(_DIGIT_MAP)
    s = re.sub(r"[^\d]", "", s)
    if not s:
        return "—"
    if s.startswith("98") and len(s) >= 12:
        s = "0" + s[2:]
    elif s.startswith("9") and len(s) == 10:
        s = "0" + s
    if len(s) >= 11 and s.startswith("09"):
        return s[:11]
    return s if s else "—"


def gregorian_to_jalali(gy: int, gm: int, gd: int):
    """تبدیل میلادی به شمسی بدون وابستگی خارجی."""
    g_d_m = [0, 31, 59, 90, 120, 151, 181, 212, 243, 273, 304, 334]
    if gy > 1600:
        jy = 979
        gy -= 1600
    else:
        jy = 0
        gy -= 621
    gy2 = gy + 1 if gm > 2 else gy
    days = (365 * gy) + ((gy2 + 3) // 4) - ((gy2 + 99) // 100) + ((gy2 + 399) // 400) - 80 + gd + g_d_m[gm - 1]
    jy += 33 * (days // 12053)
    days %= 12053
    jy += 4 * (days // 1461)
    days %= 1461
    if days > 365:
        jy += (days - 1) // 365
        days = (days - 1) % 365
    if days < 186:
        jm = 1 + days // 31
        jd = 1 + (days % 31)
    else:
        jm = 7 + (days - 186) // 30
        jd = 1 + ((days - 186) % 30)
    return int(jy), int(jm), int(jd)


def to_shamsi(value, with_time: bool = True) -> str:
    """تاریخ میلادی (str/datetime) → شمسی با رقم فارسی. ورودی خالی → —."""
    if value is None:
        return "—"
    raw = str(value).strip()
    if not raw:
        return "—"
    date_part, time_part = raw, ""
    if "T" in raw:
        date_part, time_part = raw.split("T", 1)
    elif " " in raw:
        date_part, time_part = raw.split(" ", 1)
    date_part = date_part.replace("/", "-")[:10]
    bits = date_part.split("-")
    if len(bits) != 3:
        return _fa_num(raw)
    try:
        gy, gm, gd = int(bits[0]), int(bits[1]), int(bits[2])
        if gy < 1600:
            return _fa_num(raw[:16] if with_time else raw[:10])
        jy, jm, jd = gregorian_to_jalali(gy, gm, gd)
    except (TypeError, ValueError):
        return _fa_num(raw)
    out = f"{jy:04d}/{jm:02d}/{jd:02d}"
    if with_time:
        tm = re.sub(r"[^0-9:]", "", time_part)[:5]
        if tm:
            out = f"{out} {tm}"
    return _fa_num(out)



