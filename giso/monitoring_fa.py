# -*- coding: utf-8 -*-
"""نگاشت نام صفحات و خطاها به فارسیِ کوتاه و قابل‌فهم برای پنل پایش هوشمند.

این ماژول فقط داده‌ی نمایشی را تبدیل می‌کند؛ هیچ تغییری در ساختار/ثبت ایجاد نمی‌کند.
- نام صفحات رفتار کاربران (page_path) به برچسب فارسی.
- خلاصه‌ی خطا به جمله‌ی کوتاه فارسی بر اساس نوع خطا (بدون افشای ترِیس‌بک/مسیر فنی).
"""
import re

# نگاشت مسیرهای پربازدید سایت/پنل به نام فارسی صفحه.
PAGE_LABELS = {
    "/": "صفحه اصلی",
    "/login": "ورود",
    "/register": "ثبت‌نام",
    "/forgot-password": "بازیابی رمز",
    "/admin": "پیشخوان مدیریت",
    "/admin/dashboard": "پیشخوان مدیریت",
    "/admin/wallet": "مرکز مالی",
    "/admin/consults": "گفتگوها و تیکت‌ها",
    "/admin/hair-orders": "درخواست‌های خرید مو",
    "/admin/marketplace": "مدیریت بازارچه",
    "/admin/analyses": "آنالیز هوشمند",
    "/admin/reviews": "نظرات",
    "/admin/users": "مدیریت کاربران",
    "/admin/settings": "تنظیمات سایت",
    "/admin/monitoring": "پایش هوشمند",
    "/admin/notifications": "مدیریت اعلان‌ها",
    "/admin/shop": "مدیریت فروشگاه",
    "/admin/shop-orders": "سفارش‌های فروشگاه",
    "/shop": "فروشگاه",
    "/shop/cart": "سبد خرید فروشگاه",
    "/shop/checkout": "تسویه‌حساب فروشگاه",
    "/marketplace": "بازارچه مو",
    "/analysis": "آنالیز هوشمند مو",
    "/hair": "ثبت درخواست خرید مو",
    "/dashboard": "داشبورد کاربری",
    "/dashboard/wallet": "کیف پول کاربر",
    "/consultant": "مشاور هوشمند",
}

# پیشوندهای مسیر → بخش (برای مسیرهای پارامتردار)
PAGE_PREFIXES = [
    ("/admin/wallet", "مرکز مالی"),
    ("/admin/consults", "گفتگوها و تیکت‌ها"),
    ("/admin/marketplace", "مدیریت بازارچه"),
    ("/admin/shop", "فروشگاه (مدیریت)"),
    ("/shop/cart", "سبد خرید فروشگاه"),
    ("/shop/order", "جزئیات سفارش فروشگاه"),
    ("/shop", "فروشگاه"),
    ("/marketplace/listing", "جزئیات آگهی بازارچه"),
    ("/marketplace", "بازارچه مو"),
    ("/hair", "خرید مو"),
    ("/analysis", "آنالیز هوشمند مو"),
    ("/dashboard", "داشبورد کاربری"),
    ("/admin", "پنل مدیریت"),
    ("/static", "فایل استاتیک"),
    ("/api/", "رابط برنامه‌نویسی (API)"),
]


def page_label(path: str) -> str:
    """نام فارسیِ کوتاهِ یک مسیر صفحه؛ اگر ناشناخته بود خود مسیر تمیز برمی‌گردد."""
    try:
        p = str(path or "/").split("?")[0].strip()
        if not p:
            return "صفحه اصلی"
        if p in PAGE_LABELS:
            return PAGE_LABELS[p]
        # نرمال‌سازی انتهای اسلش و شناسه‌های عددی
        base = re.sub(r"/\d+", "", p.rstrip("/")) or "/"
        if base in PAGE_LABELS:
            return PAGE_LABELS[base]
        for prefix, label in PAGE_PREFIXES:
            if p.startswith(prefix):
                return label
        # مسیر ناشناخته: کوتاه و امن (فقط مسیر، بدون کوئری)
        return p[:40]
    except Exception:
        return "صفحه نامشخص"


# نگاشت نوع/کلیدواژه‌ی خطا به جمله‌ی کوتاه فارسی (به‌ترتیب اولویت).
_ERROR_RULES = [
    (("operationalerror", "database is locked", "no such table", "readonly"),
     "خطای موقت در دسترسی به پایگاه داده؛ در صورت تکرار به پشتیبانی گزارش شود."),
    (("timeout", "timed out", "deadline"),
     "پاسخ سرویس بیرونی بیش از حد طول کشید (وقفه‌ی زمانی)."),
    (("connection", "resolve", "unreachable", "name or service", "max retries"),
     "اتصال به سرویس بیرونی برقرار نشد."),
    (("integrityerror", "unique constraint", "foreign key"),
     "تداخل یا تکرار غیرمجاز در ثبت داده (رکورد تکراری)."),
    (("filenotfound", "no such file", "not found"),
     "فایل یا مسیر موردنظر پیدا نشد."),
    (("permissiondenied", "unauthorized", "forbidden", "403"),
     "دسترسی به این عملیات مجاز نیست."),
    (("429", "too many requests", "rate"),
     "تعداد درخواست‌ها بیش از حد مجاز بود."),
    (("valueerror", "keyerror", "typeerror", "indexerror", "attributeerror"),
     "خطا در پردازش ورودی/داده؛ فرمت داده با انتظار هم‌خوانی نداشت."),
    (("token", "401", "authentication"),
     "توکن یا احراز هویت سرویس معتبر نیست."),
    (("json", "decode", "parse"),
     "قالب پاسخ دریافتی معتبر نبود."),
]


def error_label(error_text: str, service: str = "", section: str = "") -> str:
    """خلاصه‌ی کوتاه و امنِ فارسی برای یک خطا (به‌جای متن خام exception)."""
    try:
        text = str(error_text or "").lower()
        for keys, message in _ERROR_RULES:
            if any(k in text for k in keys):
                return message
        # بدون تطابق: جمله‌ی عمومی و امن (بدون افشای جزئیات فنی)
        scope = page_label(section) if section else "سیستم"
        return f"خطای پردازشی در «{scope}»؛ جزئیات در گزارش فنی ثبت شد."
    except Exception:
        return "خطای نامشخص سیستم؛ جزئیات در گزارش فنی ثبت شد."


SEVERITY_FA = {
    "error": "خطا",
    "warning": "هشدار",
    "critical": "بحرانی",
    "info": "اطلاع",
}


def severity_label(level: str) -> str:
    return SEVERITY_FA.get(str(level or "error").lower().strip(), "خطا")
