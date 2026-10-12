# Bootstrap prompt for a Giso4 Project Memory / Coding Agent

Repository: `https://github.com/uname1370-create/giso4`
Current branch: `arena/7f567e47-giso4`
Current verified HEAD: `03f3733`

## قبل از هر کاری بخوان

اگر برای ادامهٔ توسعه وارد پروژه شدی، ابتدا فایل `AGENT_START_HERE.md` را بخوان و سپس به‌ترتیب زیر پیش برو:

1. `PROJECT_MEMORY.md`
2. `PROJECT_MEMORY.json`
3. `CODE_BOUNDARY_RULES_BUTI_AI.md`
4. `FINAL_IMPLEMENTATION_SCENARIO_BUTI_AI_2026-10-12.md`
5. `TECHNICAL_DESIGN_BUTI_AI_MVP.md`
6. `SCENARIO_BEAUTY_MIRROR_EYEBROW.md`
7. `SCENARIO_BEAUTY_MIRROR_SERVICE_EXPANSION.md`
8. `UPDATE_TEMPLATE.md`
9. `tools/letta/README.md`

سپس حتماً branch، `git status`، ساختار واقعی کد و تست‌های مربوط را بررسی کن. این اسناد جایگزین بررسی کد نیستند.

## نقش و مرزها

- Project Memory وضعیت، تصمیم‌ها، قوانین و handoff را نگه می‌دارد.
- Git/GitHub منبع حقیقت کد و فایل‌های tracked است.
- Coding Agent مسئول تغییر کد، تست و گزارش است.
- چیزی را که در کد بررسی نکرده‌ای واقعیت قطعی اعلام نکن.
- secret، API key، token، عکس خصوصی، DB، log، credential یا فایل runtime را در این پوشه ذخیره نکن.

## تصمیم نهایی محصول Buti AI

چهار خدمت هدف این مرحله:

1. ابرو
2. لب
3. رژگونه
4. خط چشم

ابرو و لب در مسیر اصلی AI/inpainting هستند. رژگونه و خط چشم در MVP ابتدا با local preview کنترل‌شده شروع می‌شوند و فقط بعد از benchmark واقعی به provider مولد وصل می‌شوند.

زنجیرهٔ پیشنهادی:

```text
Cloudflare inpainting → AvalAI image edit → local preview
```

AvalAI فقط پس از تأیید endpoint، مدل، mask، قیمت و تست واقعی production محسوب می‌شود. هوشا تا زمان داشتن API رسمی server-to-server برای image edit/mask و قرارداد مشخص، provider production نیست.

در قطع اینترنت، local preview مجاز است؛ اما هرگز نباید با عنوان «نتیجهٔ واقعی AI» نمایش داده شود.

## قوانین کدنویسی

- منطق اختصاصی Buti AI در `giso/buti_ai/` بماند.
- از معماری موازی برای service catalog، reservation، mirror یا provider ساخته نشود.
- `giso/bot.py`، `bot_edu/`، `web/` و `main.py` بدون اجازهٔ صریح تغییر نکنند.
- از fallback به‌عنوان AI واقعی یاد نشود.
- migrationها additive و idempotent باشند.
- قبل از هر generation، consent، quota، idempotency، مالکیت فایل و trusted mask بررسی شود.
- پردازش سنگین تصویر داخل handler اصلی بله انجام نشود؛ از job/queue استفاده شود.
- قبل از فعال‌سازی عمومی، provider واقعی، قطع اینترنت، امنیت فایل، هزینه و load test بررسی شود.

## فایل مرجع اصلی

سناریوی کامل اجرایی در این فایل است:

`FINAL_IMPLEMENTATION_SCENARIO_BUTI_AI_2026-10-12.md`

این فایل شامل معماری providerها، offline preview، پنل AI، صفحه سالن، پنل کاربر، ربات بله، هزینه، مقیاس‌پذیری و ترتیب فازهاست.

## قانون به‌روزرسانی حافظه

بعد از هر کار معنادار، `PROJECT_MEMORY.md` و `PROJECT_MEMORY.json` را مطابق `UPDATE_TEMPLATE.md` به‌روزرسانی کن و گزارش پایان کار را با این موارد بده:

- علت ریشه‌ای
- فایل‌های تغییرکرده
- اصلاحات
- تست‌های واقعاً اجراشده و نتیجه
- عملکرد واقعی تأییدشده
- محدودیت‌های باقی‌مانده
- گام بعدی
