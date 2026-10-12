# AGENT START HERE — Giso4 / Buti AI

اگر برای ادامهٔ کار روی Giso4 وارد شدی، قبل از هر تغییر کد فقط این پوشه را بخوان؛ کاربر نباید دوباره سناریو را توضیح دهد.

## ترتیب مطالعهٔ اجباری

1. `BOOTSTRAP_PROMPT.md`
2. `PROJECT_MEMORY.md`
3. `PROJECT_MEMORY.json`
4. `CODE_BOUNDARY_RULES_BUTI_AI.md`
5. `FINAL_IMPLEMENTATION_SCENARIO_BUTI_AI_2026-10-12.md`
6. `TECHNICAL_DESIGN_BUTI_AI_MVP.md`
7. `SCENARIO_BEAUTY_MIRROR_EYEBROW.md`
8. `SCENARIO_BEAUTY_MIRROR_SERVICE_EXPANSION.md`
9. `UPDATE_TEMPLATE.md`
10. `../tools/letta/README.md` یا `tools/letta/README.md` در ریشهٔ مخزن

## وضعیت تصمیم محصول

چهار خدمت هدف این مرحله:

- ابرو
- لب
- رژگونه
- خط چشم

ابرو و لب در مسیر اصلی AI/inpainting هستند. رژگونه و خط چشم در MVP باید ابتدا با local preview کنترل‌شده و سپس در صورت موفقیت با provider تصویری اجرا شوند.

زنجیرهٔ پیشنهادی provider:

```text
Cloudflare inpainting → AvalAI image edit → local preview
```

هوشا تا وقتی API رسمی server-to-server برای image edit و mask، احراز هویت، قیمت و SLA آن تأیید نشده، provider production محسوب نمی‌شود.

در قطع اینترنت، local preview مجاز است؛ اما هرگز نباید با عنوان «نتیجهٔ واقعی AI» نمایش داده شود.

## قانون شروع کار

- واقعیت کد را بررسی کن؛ فقط به این اسناد اکتفا نکن.
- ابتدا branch و `git status` را ثبت کن.
- قبل از کدنویسی سناریوی بازتولید و تست بنویس.
- منطق Buti AI را داخل `giso/buti_ai/` نگه دار.
- `giso/bot.py`، `bot_edu/`، `web/` و `main.py` را بدون اجازهٔ صریح تغییر نده.
- provider واقعی، fallback محلی، cost ledger، quota، consent و idempotency را از هم تفکیک کن.
- fallback محلی را AI واقعی معرفی نکن.
- کلید API، token، عکس خصوصی، log یا credential را در این پوشه ذخیره نکن.
- قبل از فعال‌سازی عمومی، تست provider واقعی، تست قطع اینترنت، تست امنیت فایل و load test انجام بده.

## فایل مرجع اصلی

شرح کامل معماری، پنل AI، providerها، حالت offline، صفحهٔ سالن، پنل کاربر، ربات بله، هزینه، مقیاس‌پذیری و ترتیب فازها در این فایل است:

`FINAL_IMPLEMENTATION_SCENARIO_BUTI_AI_2026-10-12.md`

## گزارش پایان هر کار

در پایان کار باید این موارد گزارش و در Project Memory به‌روزرسانی شوند:

- علت ریشه‌ای
- فایل‌های تغییرکرده
- اصلاحات
- تست‌های واقعاً اجراشده
- عملکرد واقعی تأییدشده
- محدودیت‌های باقی‌مانده
- گام بعدی
