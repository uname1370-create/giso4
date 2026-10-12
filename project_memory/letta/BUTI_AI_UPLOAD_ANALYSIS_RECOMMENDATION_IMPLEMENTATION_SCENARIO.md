# سناریوی اجرایی Buti AI
## اتصال آپلود عکس، تحلیل هوشمند، پیشنهاد مدل و تولید نهایی

**تاریخ:** 2026-10-12
**شاخه هدف:** `arena/7f567e47-giso4`
**مخزن:** `uname1370-create/giso4`
**محدوده:** فقط flow خدمات ابرو و لب در Buti AI؛ بدون تغییر در بخش‌های نامرتبط پروژه.

---

## 1. هدف محصول

کاربر باید بتواند:

1. وارد خدمت ابرو یا لب شود.
2. مدل مورد علاقه خود را انتخاب کند یا از ابتدا گزینه «پیشنهاد گیسو» را انتخاب کند.
3. عکس واقعی خود را آپلود کند.
4. بلافاصله در همان مرحله، preview عکس را ببیند.
5. عکس از نظر فنی و محتوایی بررسی شود.
6. تحلیل هوشمند بر اساس عکس، مدل انتخاب‌شده و شدت تغییر انجام شود.
7. دو انتخاب واضح ببیند:
   - **پیشنهاد گیسو بر اساس تحلیل عکس**
   - **همان مدل انتخابی کاربر**
8. فقط پس از تأیید یکی از دو گزینه، تولید تصویر نهایی شروع شود.
9. نتیجه قبل/بعد، وضعیت واقعی AI، مدل انتخاب‌شده و دانلود تصویر/PDF نمایش داده شود.

> هیچ fallback یا composite محلی نباید به‌عنوان نتیجه واقعی هوش مصنوعی معرفی شود.

---

## 2. وضعیت فعلی کد در شروع کار

### بخش‌های موجود و قابل استفاده

- `giso/buti_ai/eyebrow/ai.py`
  - `check_photo_quality`
  - `analyze_eyebrow_photo`
  - اتصال به زنجیره Vision مدیریت‌شده در پنل AI
- `giso/buti_ai/eyebrow/result.py`
  - پاک‌سازی تحلیل
  - `recommended_style`
  - `style_scores`
  - `alternative_styles`
  - `face_analysis`
- `giso/buti_ai/lip/final_design.py`
  - `check_photo_quality`
  - `analyze_lip_photo`
  - تشخیص ناحیه لب
- `giso/buti_ai/generic_service.py`
  - flow عمومی خدمات جدید و اتصال تحلیل سرویس
- routeهای validate عکس در `giso/buti_ai/routes.py`
- preview سمت کاربر در `giso/buti_ai/static/buti_ai.js`
- قالب‌های upload:
  - `giso/buti_ai/templates/buti_ai/eyebrow_wizard.html`
  - `giso/buti_ai/templates/buti_ai/generic_service_wizard.html`
- قالب‌های نتیجه:
  - `eyebrow_final_design.html`
  - `generic_final_design.html`

### مشکل اصلی موجود

صفحه آپلود فقط preview را نشان می‌دهد. در نسخه قدیمی JavaScript، تابع تحلیل عملاً غیرفعال بود:

```javascript
async function validateEyebrowPhoto(file, validateUrl) {
    return;
}
```

همچنین route آپلود پس از دریافت عکس مستقیماً به صفحه تولید نهایی redirect می‌شد و کاربر مرحله تأیید پیشنهاد را نمی‌دید.

---

## 3. مرز تغییرات

### مجاز

- routeهای داخل `giso/buti_ai/routes.py`
- flowهای داخل `giso/buti_ai/eyebrow/`
- `giso/buti_ai/generic_service.py`
- سرویس مخصوص لب
- قالب‌های wizard و final در `giso/buti_ai/templates/buti_ai/`
- `giso/buti_ai/static/buti_ai.js`
- `giso/buti_ai/static/buti_ai.css`
- تست‌های اختصاصی Buti AI
- مستندات داخل `project_memory/letta/`

### ممنوع

- تغییر `web/`
- تغییر `bot_edu/`
- بازنویسی `main.py`
- تغییر `giso/bot.py`
- ساخت سیستم تحلیل موازی خارج از Buti AI
- تغییر معماری provider یا مدیریت مدل‌ها بدون نیاز
- حذف fallback موجود
- معرفی preview محلی به‌عنوان AI واقعی
- ذخیره token، API key یا اطلاعات حساس در session، HTML یا گزارش دانلود

---

## 4. قرارداد UX مرحله‌ها

### مرحله اول: انتخاب خدمت

مسیرها:

```text
/analysis/mirror/
/analysis/mirror/eyebrow
/analysis/mirror/lip-shading
```

صفحه باید خدمت و نمونه‌ها را نشان دهد.

### مرحله دوم: انتخاب مدل

برای ابرو مدل‌ها:

- `natural`
- `microblading`
- `powder`
- `combination`
- `giso_suggested`

برای لب مدل‌ها از `STYLES` داخل `giso/buti_ai/lip/final_design.py` استفاده شود و key جدید اختراع نشود.

شدت تغییر:

- `very_natural`
- `medium`
- `clear`

انتخاب کاربر در session نگهداری شود:

```python
{
    "style": "natural",
    "change_level": "medium"
}
```

### مرحله سوم: آپلود و تحلیل

در صفحه upload باید موارد زیر وجود داشته باشد:

- انتخاب JPG، PNG یا WebP
- محدودیت حجم مطابق قرارداد فعلی
- preview واقعی عکس انتخاب‌شده
- دکمه تغییر عکس
- نمونه عکس مناسب
- راهنمای نور، زاویه و وضوح
- وضعیت «در حال بررسی عکس»
- نمایش checkهای تحلیل
- کارت دو گزینه‌ای پیشنهاد مدل

در زمان انتخاب فایل، JavaScript باید endpoint validate را با `FormData` صدا بزند. توکن CSRF نیز باید همراه درخواست ارسال شود.

### مرحله چهارم: تأیید پیشنهاد

پس از پاسخ تحلیل، کاربر باید دو گزینه ببیند:

#### گزینه A: پیشنهاد گیسو

```text
پیشنهاد گیسو: [نام مدل]
دلیل: [دلیل کوتاه تحلیل]
بر اساس چهره/لب، مدل انتخابی و شدت تغییر
```

#### گزینه B: انتخاب خودم

```text
همان مدل انتخابی من: [نام مدل اولیه]
بدون تغییر نسبت به انتخاب اولیه
```

یکی باید انتخاب شده باشد؛ ترجیحاً پیشنهاد گیسو در صورت وجود تحلیل موفق، و در غیر این صورت انتخاب کاربر.

### مرحله پنجم: تولید نهایی

فقط با submit تأیید نهایی:

```text
analysis_confirmed=1
final_style=<validated-style-key>
```

تولید نهایی آغاز شود.

مدل نهایی باید دقیقاً از `final_style` معتبر و normalize‌شده استفاده کند.

---

## 5. قرارداد endpoint validate

### ابرو

```text
POST /analysis/mirror/eyebrow/validate-photo
```

ورودی:

- `photo`
- `csrf_token`

مراحل server-side:

1. ذخیره موقت امن عکس.
2. بررسی فرمت، حجم و decode واقعی تصویر.
3. اجرای `check_photo_quality`.
4. اجرای `analyze_eyebrow_photo` با selection فعلی.
5. حذف فایل موقت در `finally`.
6. عدم ذخیره دائمی عکس در validate.

پاسخ موفق نمونه:

```json
{
  "valid": true,
  "status": "ai_checked",
  "message": "عکس برای طراحی مناسب است.",
  "checks": {
    "face_visible": true,
    "eyebrows_visible": true,
    "lighting": "good",
    "angle": "frontal",
    "sharpness": "good"
  },
  "recommendation": {
    "status": "ai_analyzed",
    "style": "natural",
    "label": "طبیعی و نچرال",
    "reason": "دلیل کوتاه و غیرقطعی تحلیل",
    "alternatives": []
  }
}
```

### لب

```text
POST /analysis/mirror/lip-shading/validate-photo
```

مراحل:

1. ذخیره موقت امن.
2. `module.check_photo_quality`.
3. `module.analyze_lip_photo`.
4. استخراج `recommended_style` از data.
5. normalize کردن key با `generic_service.normalize_model_key`.
6. بازگرداندن recommendation.
7. پاک‌سازی فایل موقت.

در نبود provider:

```json
{
  "valid": true,
  "status": "ai_unavailable",
  "recommendation": {
    "status": "ai_unavailable",
    "style": "<selected_style>",
    "label": "مدل انتخابی",
    "reason": "تحلیل هوشمند فعلاً در دسترس نیست؛ می‌توانی مدل انتخابی خودت را ادامه بدهی."
  }
}
```

این وضعیت نباید به‌عنوان تحلیل موفق AI نمایش داده شود.

---

## 6. قرارداد route upload و finalize

### رفتار POST اول upload

POST اول عکس واقعی دارد و `analysis_confirmed` ندارد:

1. عکس دائمی در upload directory سرویس ذخیره شود.
2. quality و analysis سمت server اجرا شود.
3. candidate در session ذخیره شود.
4. کاربر به‌جای redirect مستقیم به final، همان صفحه upload را با کارت پیشنهاد ببیند.
5. candidate شامل این داده‌ها باشد:

```python
{
    "photo_filename": "...",
    "selected_style": "...",
    "selected_label": "...",
    "recommended_style": "...",
    "recommended_label": "...",
    "ai_analysis": {...},
    "change_key": "...",
    "detection": {...},
    "_owner_user_id": ...
}
```

### رفتار POST دوم تأیید

POST دوم بدون فایل جدید و با `analysis_confirmed=1` انجام شود.

مراحل:

1. candidate از session خوانده شود.
2. مالکیت candidate بررسی شود.
3. `final_style` با options همان سرویس normalize و validate شود.
4. فقط `selected_style` و `final_style` تغییر کند.
5. عکس قبلی حفظ شود.
6. redirect به final design انجام شود.

اگر candidate وجود نداشت یا مالکیت رد شد:

- تولید انجام نشود.
- پیام امن نمایش داده شود.
- کاربر به wizard برگردد.

---

## 7. رفتار تولید تصویر

### ابرو

- مسیر واقعی provider و mask ابرو حفظ شود.
- `final_style` تأییدشده مبنای prompt و render باشد.
- مدل انتخاب‌شده کاربر نباید بی‌دلیل با پیشنهاد AI جایگزین شود.
- اگر کاربر پیشنهاد گیسو را انتخاب کرد، همان پیشنهاد وارد تولید شود.
- اگر کاربر انتخاب دستی را انتخاب کرد، پیشنهاد AI فقط راهنما بماند.

### لب

- مسیر `service_image_generation.py` حفظ شود.
- mask لب و polarity فعلی تغییر نکند مگر با تست واقعی.
- `final_style` انتخاب‌شده باید به renderer و provider برسد.
- خارج از mask نباید تغییر قابل مشاهده داشته باشد.

### fallback

اگر provider شکست خورد:

```text
is_ai_generated = false
fallback_used = true
```

و UI باید شفاف بنویسد:

```text
این نسخه AI واقعی نیست؛ راهنمای غیر AI است.
```

---

## 8. تغییرات JavaScript

در `giso/buti_ai/static/buti_ai.js`:

1. تابع validate دیگر نباید خالی باشد.
2. هنگام انتخاب فایل:
   - preview نمایش داده شود.
   - دکمه تا پایان validate غیرفعال باشد.
   - وضعیت loading نمایش داده شود.
   - پاسخ endpoint خوانده شود.
   - checkها در `btiUploadChecks` نمایش داده شوند.
   - کارت recommendation ساخته شود.
3. تغییر radio پیشنهاد باید hidden input `final_style` را به‌روزرسانی کند.
4. در خطای endpoint:
   - اگر عکس از نظر فنی قابل قبول است، انتخاب دستی قابل ادامه باشد.
   - پیام «تحلیل هوشمند در دسترس نبود» نمایش داده شود.
   - خطا نباید بی‌دلیل کاربر را متوقف کند.
5. هر HTML پویا باید با escape امن تولید شود.
6. endpoint فقط same-origin و همراه credential/CSRF فراخوانی شود.

---

## 9. قالب‌ها

### `eyebrow_wizard.html`

باید داشته باشد:

- `data-bti-upload-form`
- `data-bti-validate-url`
- `btiUploadPreview`
- `btiUploadChecks`
- `btiFinalStyle`
- کارت پیشنهاد گیسو
- کارت انتخاب دستی
- دکمه «تأیید انتخاب و ساخت عکس نهایی»

### `generic_service_wizard.html`

همین قرارداد برای لب اعمال شود و از `service_meta` و `styles` همان سرویس استفاده کند.

### قالب final

باید نشان دهد:

- مدل نهایی انتخاب‌شده
- آیا تحلیل واقعی AI انجام شده یا خیر
- before/after
- دکمه دانلود تصویر
- دکمه دانلود PDF
- متن هشدار غیر AI در fallback

---

## 10. تست‌های اجباری

### تست backend

1. validate ابرو با عکس معتبر و mock تحلیل موفق.
2. validate لب با عکس معتبر و mock تحلیل موفق.
3. validate با عکس خراب.
4. validate با provider unavailable.
5. پیشنهاد AI به‌درستی از پاسخ parser استخراج شود.
6. مدل نامعتبر normalize شود.
7. POST اول upload به صفحه تحلیل برگردد، نه final.
8. POST دوم با `analysis_confirmed=1` به final redirect شود.
9. POST دوم بدون candidate reject شود.
10. candidate کاربر دیگر reject شود.
11. انتخاب پیشنهاد AI در final_style ذخیره شود.
12. انتخاب دستی در final_style ذخیره شود.
13. عکس در POST دوم دوباره لازم نباشد.
14. provider نهایی همان final_style تأییدشده را دریافت کند.

### تست frontend

با Playwright یا browser واقعی:

1. باز کردن صفحه ابرو.
2. رفتن به upload.
3. انتخاب عکس معتبر.
4. مشاهده preview.
5. مشاهده loading تحلیل.
6. مشاهده کارت «پیشنهاد گیسو» و «انتخاب خودم».
7. تغییر انتخاب.
8. کلیک تأیید.
9. مشاهده final.
10. تکرار همین flow برای لب.

### تست provider واقعی

فقط با credential موجود محیط:

- حداقل یک عکس واقعی روبه‌رو برای ابرو.
- حداقل یک عکس واقعی لب.
- ثبت provider/model بدون افشای token.
- بررسی بصری before/after.
- بررسی اینکه fallback با AI واقعی اشتباه نشود.

---

## 11. معیار پذیرش نهایی

کار فقط زمانی کامل است که همه موارد زیر برقرار باشند:

- در صفحه upload بعد از انتخاب عکس، تحلیل واقعاً اجرا می‌شود.
- اگر provider در دسترس باشد، suggestion واقعی از پاسخ مدل نمایش داده می‌شود.
- اگر provider در دسترس نباشد، UI صادقانه fallback را اعلام می‌کند.
- دو گزینه پیشنهاد گیسو و انتخاب دستی قابل انتخاب هستند.
- انتخاب نهایی واقعاً روی تولید تصویر اثر می‌گذارد.
- عکس بدون تأیید کاربر وارد تولید نهایی نمی‌شود.
- قبل/بعد و دانلود فقط برای candidate مجاز نمایش داده می‌شود.
- تست‌های مرتبط سبز هستند.
- هیچ مسیر نامرتبط پروژه تغییر نکرده است.
- `git diff --check` سبز است.
- سایت با وب‌سرور اجرا و از URL عمومی Sandbox بررسی شده است.
- سپس commit و push فقط به `arena/7f567e47-giso4` انجام می‌شود.

---

## 12. وضعیت اجرای فعلی این سند

در شروع تدوین این سند، بخشی از اتصال جدید در working tree به‌صورت آزمایشی اعمال شده است، اما هنوز کامل نیست.

آخرین مشکل شناخته‌شده:

```text
test_buti_ai_eyebrow_real_photo_step_flow_with_csrf
expected 302, received 200
```

این شکست به‌دلیل تغییر عمدی قرارداد جدید است: POST اول باید صفحه تحلیل و تأیید را نمایش دهد، نه اینکه مستقیماً به final redirect شود. تست باید به قرارداد جدید منتقل شود و سپس کل suite دوباره اجرا شود.

تا زمانی که تست‌ها، اجرای واقعی browser و flow provider تأیید نشده‌اند:

- commit نهایی انجام نشود.
- push انجام نشود.
- خروجی AI واقعی ادعا نشود.

---

## 13. دستورالعمل handoff برای ایجنت بعدی

ایجنت بعدی باید به‌ترتیب زیر کار کند:

1. همین فایل را کامل بخواند.
2. `AGENT_START_HERE.md` و `CODE_BOUNDARY_RULES_BUTI_AI.md` را بخواند.
3. `git status` و diff فعلی را بررسی کند و تغییرات موجود را حذف نکند.
4. ابتدا syntax و route tests را اجرا کند.
5. تست‌های قدیمی direct-redirect را طبق قرارداد جدید اصلاح کند، نه اینکه رفتار جدید را به عقب برگرداند.
6. برای POST اول upload تست کند که صفحه recommendation برمی‌گردد.
7. برای POST دوم تست کند که final redirect انجام می‌شود.
8. flow ابرو و لب را جداگانه و سپس مشترک تست کند.
9. با browser واقعی صفحات upload را باز کند.
10. در صورت فعال بودن provider، live test بگیرد.
11. diff را review کند:

```bash
git diff --check
git status --short
```

12. فقط فایل‌های مرتبط را commit کند.
13. قبل از push، آخرین commit remote را fetch و مقایسه کند.
14. سپس با `git push --force-with-lease origin arena/7f567e47-giso4` فقط همان شاخه را به‌روزرسانی کند.
15. hash commit و نتیجه تست را گزارش کند.
