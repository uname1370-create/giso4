# -*- coding: utf-8 -*-
"""قالب‌بندی یکسان مبلغ‌های گیسو با رقم فارسی و واحد تومان."""
from decimal import Decimal, InvalidOperation

_FA_DIGITS = str.maketrans("0123456789٠١٢٣٤٥٦٧٨٩", "۰۱۲۳۴۵۶۷۸۹۰۱۲۳۴۵۶۷۸۹")
_ARABIC_TO_EN = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")


def _as_int(value) -> int:
    """تبدیل محافظه‌کارانه مقدار عددی/رشته‌ای به عدد صحیح تومان."""
    if value is None or value == "":
        return 0
    if isinstance(value, bool):
        return int(value)
    try:
        cleaned = (str(value).translate(_ARABIC_TO_EN)
                   .replace(",", "").replace("٬", "").replace("،", "").strip())
        return int(Decimal(cleaned))
    except (InvalidOperation, TypeError, ValueError):
        return 0


_THOUSANDS_FA = str.maketrans(",", "٬")  # جداکنندهٔ هزارگان فارسی — هرگز شبیه نقطهٔ اعشار نیست


def format_number_fa(value, *, show_plus: bool = False) -> str:
    """عدد با جداکنندهٔ هزارگان فارسی «٬» و رقم فارسی (جداکننده باشد ولی با اعشار اشتباه نشود)."""
    number = _as_int(value)
    rendered = f"+{number:,}" if (show_plus and number > 0) else f"{number:,}"
    return rendered.translate(_FA_DIGITS).translate(_THOUSANDS_FA)


def to_persian_digits(value) -> str:
    """فقط تبدیل رقم برای تاریخ، تلفن و شناسه؛ بدون افزودن جداکننده."""
    return str(value if value is not None else "").translate(_FA_DIGITS)


def format_toman(value, *, show_plus: bool = False) -> str:
    """قالب رسمی مبلغ در UI و اعلان‌ها: «۱۲۳,۴۵۶ تومان»."""
    return f"{format_number_fa(value, show_plus=show_plus)} تومان"


def sale_price_from_cost(cost, *, markup: float = 1.5, round_to: int = 10000) -> int:
    """قیمت فروش از روی قیمت فاکتور: پیش‌فرض ×۱.۵ (۵۰٪ سود)، رند رو به بالا به `round_to`.

    برای کاتالوگ تأمین/فروشگاه استفاده می‌شود. اگر قیمت فاکتور نامعتبر باشد ۰ برمی‌گردد
    (یعنی قیمت باید دستی تکمیل شود).
    """
    try:
        cost = int(Decimal(str(cost).translate(_ARABIC_TO_EN).replace(",", "").replace("٬", "")))
    except (InvalidOperation, TypeError, ValueError):
        return 0
    if cost <= 0:
        return 0
    raw = int(Decimal(str(cost)) * Decimal(str(markup)))
    if round_to and round_to > 0:
        # رند رو به بالا به نزدیک‌ترین مضرب round_to
        raw = -(-raw // round_to) * round_to
    return int(raw)


__all__ = ["format_number_fa", "format_toman", "to_persian_digits"]
