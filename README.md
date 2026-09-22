# 💎 گیسو صادقی — پلتفرم هوشمند زیبایی و سلامت مو و پوست

[![Python](https://img.shields.io/badge/Python-3.10+-blue.svg)](https://python.org)
[![Flask](https://img.shields.io/badge/Flask-3.0-green.svg)](https://flask.palletsprojects.com)
[![SQLite](https://img.shields.io/badge/SQLite-WAL-lightgrey.svg)](https://sqlite.org)
[![License](https://img.shields.io/badge/Platform-Bale%20Bot-orange.svg)](https://tapi.bale.ai)

## 🌟 گیسو چیست؟

گیسو صادقی یک **پلتفرم هوشمند Beauty Commerce** است که از طریق وب‌سایت و ربات بله خدمات زیر را ارائه می‌دهد:

- 🔬 **آنالیز هوشمند مو و پوست** با AI چندپروایدر + گزارش PDF + برنامه اختصاصی
- 💇 **خرید موی طبیعی** با ارزیابی قیمت + گفتگوی زنده کارشناس
- 🛍 **فروشگاه تخصصی** محصولات آرایشی-بهداشتی + ایمپورت از کانال بله
- 🤖 **مشاور هوشمند صادقی** در سایت و ربات
- 🔔 **سیستم اعلان‌ها** + مدیریت ادمین‌ها + بکاپ/ریستور

## 📊 آمار پروژه

| شاخص | مقدار |
|-------|-------|
| جداول دیتابیس | 40 |
| فایل‌های پایتون | 115 |
| فایل‌های تست | 41 (400+ تست) |
| ماژول‌های پنل ادمین | 15 |
| ماژول‌های پنل کاربر | 10 |
| Routeهای وب | ~150 |
| Callbackهای ربات | ~128 |
| پروایدرهای AI | 7 |
| سناردوم ۱ (تثبیت) | ✅ 95% |
| سناردوم ۲ (توسعه) | ✅ 83% |

## 🏗 معماری

```
        گیسو صادقی
            │
  ┌─────────┼─────────┐
  │         │         │
 وب‌سایت   ربات بله    AI
 (Flask)   (Bale Bot) (7 Provider)
  │         │         │
  └────┬────┘         │
       │              │
    giso.db       ai_brain.py
   (40 جدول)    (Vision + Text)
       │
  ┌────┴────┐
  │         │
 سایت     ربات
 (UI)    (Chat)
```

**Single Source of Truth = giso/data/giso.db** (SQLite WAL)

## 🚀 نصب و اجرا

```bash
# 1. کلون
git clone https://github.com/uname1370-create/Giso1.git
cd Giso1

# 2. نصب وابستگی‌ها
pip install -r requirements.txt

# 3. تنظیمات
cp .env.example giso/data/.env
# ویرایش giso/data/.env با API key ها

# 4. اجرا
python main.py

# یا با Gunicorn
gunicorn wsgi:application --bind 0.0.0.0:5001 --workers 2
```

## 📁 ساختار پروژه

```
Giso1/
├── main.py                        ← نقطه ورود
├── env_loader.py                  ← لود تنظیمات
├── requirements.txt               ← وابستگی‌ها
├── giso/
│   ├── app.py                     ← Flask web
│   ├── bot.py                     ← ربات بله (8370 خط)
│   ├── base.py                    ← لایه پایه
│   ├── config.py                  ← تنظیمات
│   ├── models.py                  ← مدل‌ها (40 جدول)
│   ├── security.py                ← امنیت
│   ├── ai_brain.py                ← مغز AI
│   ├── ai_runtime.py              ← runtime AI
│   ├── analysis.py                ← آنالیز هوشمند
│   ├── hair_sale.py               ← فروش مو
│   ├── shop.py                    ← wrapper فروشگاه
│   ├── referrals.py               ← معرفی + کیف پول
│   ├── recommendation_service.py  ← موتور Recommendation
│   ├── prompt_management.py       ← نسخه‌بندی پرامپت
│   ├── content.py                 ← محتوای آموزشی
│   ├── channel_importer.py        ← ایمپورت کانال بله
│   ├── panel/                     ← پنل ادمین (15 ماژول)
│   ├── panel_user/                ← پنل کاربر (10 ماژول)
│   ├── shop/                      ← فروشگاه ماژولار
│   ├── templates/                 ← قالب‌ها
│   ├── static/                    ← CSS/JS/تصاویر
│   ├── prompts/                   ← پرامپت‌های AI
│   ├── tests/                     ← 41 فایل تست
│   └── data/                      ← دیتابیس + بکاپ
└── bot_edu/                       ← ربات اصلی edu
```

## 💎 وب‌اپ پیش‌نمایش هوشمند ابرو (`beauty-preview/`)

یک اپ **مستقل** از گیسو (Next.js 14 + TypeScript + Tailwind، فارسی و RTL) برای شبیه‌سازی
میکروبلیدینگ ابرو:

| مرحله | توضیح |
|-------|-------|
| ۱ | انتخاب مدل ابرو: هایر استروک طبیعی، فدر براو، اومبره پودری، کامبینیشن |
| ۲ | انتخاب رنگ: ۶ رنگ استاندارد پیگمنت با نام فارسی و tooltip |
| ۳ | آپلود عکس چهره (drag & drop، JPG/PNG/WEBP، حداکثر ۵ مگابایت) |
| ۴ | دکمهٔ «ایجاد پیش‌نمایش هوشمند» |
| ۵ | اسلایدر مقایسهٔ «قبل/بعد» + دانلود تصویر + رزرو نوبت در واتساپ |

**زنجیرهٔ جایگزین AI (فقط سمت سرور):** Runware → SiliconFlow → AIMLAPI → Pollinations
(هر پروایدری که کلیدش خالی باشد رد می‌شود و در صورت خطا، بعدی امتحان می‌شود).

```bash
cd beauty-preview
npm install
cp .env.example .env.local     # کلیدها را داخلش بگذارید
npm run dev                    # http://localhost:3000
npm run test:chain             # تست زنجیرهٔ ۴ پروایدری با سرور mock (بدون مصرف اعتبار)
```

> جزئیات کامل: [`beauty-preview/README.md`](beauty-preview/README.md)

## 🔐 امنیت

- احراز هویت دومرحله‌ای پنل مدیریت (کد ربات)
- گارد شماره‌های حساس (ادمین/سوپرادمین)
- Security headers (CSP, HSTS, X-Frame-Options)
- Ownership check روی تمام داده‌های حساس
- Audit log برای تمام رویدادهای حساس
- CSRF + SameSite=Lax + HttpOnly

## 🤖 هوش مصنوعی

- **7 پروایدر:** Gemini, OpenRouter, Groq, Avalai, GapGPT, Cloudflare, LLM7
- **Fallback خودکار** بین پروایدرها + retry هوشمند
- **ذخیره‌سازی دو لایه:** DB + .env
- **نسخه‌بندی پرامپت** با rollback
- **Structured output validation**

## 📱 ربات بله

- منوی کاربر: آنالیز/فروشگاه/فروش مو/سفارش/پشتیبانی/پروفایل
- منوی ادمین: پیشخوان/سفارش/فروش مو/آنالیز/محصولات/کانال/کاربران
- منوی سوپرادمین: همه + AI/پروکسی/بکاپ/ریستارت/دسترسی
- منوی هوشمند فروش مو: لیست تک‌به‌تک + عکس + اکشن + صفحه‌بندی

## 🧪 تست‌ها

```bash
# اجرای همه تست‌ها
python -m pytest giso/tests/ -v

# تست خاص
python giso/tests/test_panel_phase5.py
python giso/tests/test_shop_phase_a.py
```

## 📄 مستندات

- [`PROJECT_GUIDE.md`](PROJECT_GUIDE.md) — راهنمای کلی سه بخش ریپو (ربات آموزش، سایت آموزش، گیسو)
- [`GISO_GUIDE.md`](GISO_GUIDE.md) — راهنمای جامع فنی گیسو (معماری، ساختار کد و توابع، دیتابیس + آخرین تغییرات)
- [`beauty-preview/README.md`](beauty-preview/README.md) — راهنمای وب‌اپ پیش‌نمایش هوشمند ابرو (Next.js + زنجیرهٔ پروایدرها)

## 📜 مجوز

این پروژه مالکیت خصوصی دارد.

---

**گیسو صادقی — هوشمند ببین، دقیق انتخاب کن** 💎
