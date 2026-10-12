# AGENT START HERE — Giso4 / Buti AI

اگر برای ادامهٔ کار روی Giso4 وارد شدی، قبل از هر تغییر کد فقط این پوشه را بخوان؛ کاربر نباید دوباره سناریو را توضیح دهد.

## آخرین handoff — 2026-10-12، حدود 20:19 Asia/Tehran

- شاخه `arena/7f567e47-giso4` شامل Stage 1–3 در `525e80e` و Stage 4–5 در commit pushشدهٔ `e5512dc` است. Stage 6 در commit `ca522c0` به همان branch push شده؛ remote و local اکنون روی همین commit هستند.
- Stage 5: چهار آمار اصلی صفحه مراکز حفظ شدند؛ بخش تقاضای عمومی از خدمت‌های فعال موجود در inventory ساخته می‌شود و نام/گروه خدمت hardcode نیست. شروع فرم رزرو به‌صورت aggregate، با dedupe نشست/روز، ثبت می‌شود؛ شمارنده افراد یکتا یا رزرو قطعی نیست.
- آمار عمومی ۳۰روزه زیر آستانهٔ پیش‌فرض ۵ نمایش دقیق نمی‌دهد؛ آستانه با `BEAUTY_SERVICE_DEMAND_MIN_SAMPLE` قابل تنظیم است. تب «آمار هوشمند» مالک فقط داده‌های مرکز resolveشدهٔ خودش را در بازه‌های ۷/۳۰/۹۰ روز نشان می‌دهد. مدیریت، تفکیک شهر/خدمت دارد.
- حریم خصوصی: eventهای جدید `user_id=0` دارند و هیچ عکس، `final_design_id`، شماره تماس یا visitor ID ثبت نمی‌کنند.
- اعتبارسنجی Stage 5 روی کد جاری: **70 passed، 132 warnings**؛ smoke عمومی HTTP 200 و حضور چهار KPI قدیمی همراه با بخش تقاضا/حالت خالی تأیید شد. Sweep گستردهٔ مراکز: **80 passed، 10 failed** در expectationهای قدیمی stage 7/10/12/13/14؛ فیکسچر مدیا و تست فرم GET/CSRF اصلاح شده‌اند. کل suite پس از Stage 5 اجرا نشده.
- Stage 6: مقایسهٔ قیمت با همان شهر/service key، حذف مرکز خود صفحه، حداقل نمونهٔ قابل‌تنظیم و نمایش میانه/بازه/تعداد/زمان پیاده‌سازی شده. تست pricing/benchmark: **11 passed**؛ sweep مراکز: **88 passed، 10 failed** در expectationهای قدیمی Stage 7/10/12/13/14 و admin-bot. Full suite سبز اعلام نشده.
- قبل از شروع Stage 7 منتظر تأیید کاربر بمان.

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

## Latest handoff — 2026-10-12, 18:17 Asia/Tehran

- Stages 1–3 of the Beauty Centers roadmap are implemented and pushed to `arena/7f567e47-giso4` at commit `525e80e`.
- Stage 4 (Instagram profile link and outbound click tracking) is implemented locally but remains uncommitted/unpushed. Dedicated tests pass (**7 passed**); final combined center/Buti AI regressions pass (**58 passed, 132 warnings**). `py_compile`, route-map check, Jinja compilation and `git diff --check` pass.
- Full repository suite after Stage 3 and before Stage 4 was not green: **727 passed, 69 failed, 4 skipped, 364 warnings**. Failures span wider project areas; see `PROJECT_MEMORY.md` and the implementation scenario for details. `test_phase4_beauty_owner_ui` still expects the legacy label `افزایش دیده‌شدن آگهی`. Stage 4 has targeted/combined regressions, not a new full-suite run.
- Stage 5 has not started. After reviewing Stage 4, ask the user before committing/pushing it or continuing to Stage 5.
- The historical snapshot below may contain superseded status; prefer this latest handoff plus `PROJECT_MEMORY.md`.

## وضعیت به‌روز Buti AI — آپلود، تحلیل و پیشنهاد مدل — 2026-10-12

### واقعاً اعمال‌شده و تأییدشده

این موارد در کد موجود و تست‌شده هستند:

- مسیرهای ابرو و لب/خدمات عمومی داخل `giso/buti_ai/` فعال هستند.
- انتخاب مدل و شدت تغییر در session نگهداری می‌شود.
- preview عکس در صفحه upload نمایش داده می‌شود.
- محدودیت نوع فایل و حجم عکس در سمت کاربر و server وجود دارد.
- endpointهای validate عکس برای ابرو و خدمات عمومی وجود دارند.
- تحلیل‌های اختصاصی موجودند: `analyze_eyebrow_photo` و `analyze_lip_photo`.
- زنجیره Vision از مدیریت مدل‌های AI خوانده می‌شود و token در کد/مستندات ذخیره نشده است.
- مسیر تولید نهایی ابرو و لب و قرارداد mask/polarity قبلی حفظ شده‌اند.
- خروجی before/after و گزارش دانلودی تصویر/PDF پیاده‌سازی شده است.
- کنترل مالکیت session/candidate و جلوگیری از path traversal در دانلود پیاده‌سازی شده است.
- مجموعه قبلی تست‌های Buti AI شامل ابرو، لب، خدمات عمومی و دانلود در یک اجرای سالم `65 passed` داشته است.

### تغییر جدیدی که اکنون در working tree در حال تکمیل است

برای اینکه ایجنت بعدی دوباره‌کاری نکند، سناریوی دقیق این کار در فایل زیر ثبت شده است:

`BUTI_AI_UPLOAD_ANALYSIS_RECOMMENDATION_IMPLEMENTATION_SCENARIO.md`

هدف این تغییر جدید این است که بعد از انتخاب عکس:

```text
preview → validate/quality → Vision analysis → دو گزینهٔ پیشنهاد/انتخاب دستی → تأیید کاربر → تولید نهایی
```

در working tree فعلی، اتصال اولیه این بخش‌ها اضافه شده است:

- routeهای upload ابرو و generic دیگر در POST اول مستقیماً به final redirect نمی‌کنند و candidate تحلیل‌شده را برای نمایش پیشنهاد نگه می‌دارند.
- پاسخ validate ابرو و لب/خدمات عمومی دارای `recommendation` است.
- JavaScript آپلود از endpoint validate استفاده می‌کند و کارت پیشنهاد را در صفحه می‌سازد.
- قالب‌های `eyebrow_wizard.html` و `generic_service_wizard.html` کارت «پیشنهاد گیسو» و «انتخاب خودم» دارند.
- انتخاب تأییدشده با `analysis_confirmed=1` و `final_style` وارد مرحله تولید می‌شود.
- candidate عمومی، `recommended_style` و `ai_analysis` را نگه می‌دارد.
- استایل کارت تحلیل و دو انتخاب به CSS اضافه شده است.

### وضعیت تأیید این تغییر جدید

این اتصال جدید هنوز **کامل و قابل انتشار اعلام نشده است**. آخرین تست نشان داد که تست قدیمی انتظار redirect مستقیم `302` دارد، درحالی‌که قرارداد جدید باید در POST اول صفحه پیشنهاد را با `200` نمایش دهد:

```text
test_buti_ai_eyebrow_real_photo_step_flow_with_csrf
expected 302, received 200
```

بنابراین ایجنت بعدی باید تست‌های direct-redirect را طبق سناریوی جدید اصلاح کند؛ نباید رفتار جدید را به redirect مستقیم برگرداند.

تا قبل از سبز شدن تست‌های جدید، smoke test مرورگر و live provider:

- commit جدید انجام نشود؛
- push انجام نشود؛
- پیشنهاد AI واقعی ادعا نشود.

### ترتیب اجباری ادامه کار

1. خواندن کامل `BUTI_AI_UPLOAD_ANALYSIS_RECOMMENDATION_IMPLEMENTATION_SCENARIO.md`.
2. اجرای `git status --short --branch` و حفظ همه تغییرات موجود.
3. تکمیل تست POST اول upload، نمایش recommendation و POST دوم confirmation.
4. تست جداگانه ابرو و لب با mock provider و provider unavailable.
5. اجرای `node --check giso/buti_ai/static/buti_ai.js` و `python3 -m py_compile`.
6. اجرای suite کامل Buti AI.
7. اجرای سایت و بررسی واقعی upload/recommendation/final با مرورگر.
8. فقط پس از موفقیت همه موارد، commit محدود و push امن به شاخه `arena/7f567e47-giso4`.
