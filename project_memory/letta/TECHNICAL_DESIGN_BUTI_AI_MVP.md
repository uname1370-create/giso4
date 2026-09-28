# طراحی فنی MVP: Buti AI / آینه ابرو گیسو

وضعیت: طراحی فنی مستند؛ هنوز هیچ کد اجرایی Giso برای این MVP تغییر نکرده است.

هدف این سند: مشخص کردن اینکه نسخه اول «آینه ابرو گیسو» چطور باید داخل ماژول مستقل `giso/buti_ai/` ساخته شود، بدون پخش شدن منطق در بخش‌های دیگر پروژه.

---

## 1. اصل مالکیت ماژول

مالک قابلیت:

```text
giso/buti_ai/
```

نام فنی/توسعه‌ای:

```text
Buti AI / buti_ai
```

نام محصول در UI:

```text
آینه زیبایی گیسو
آینه ابرو گیسو
```

قانون اصلی:

- هر چیزی که مخصوص آینه زیبایی است، اول باید در `giso/buti_ai/` طراحی شود.
- فایل‌های عمومی Giso فقط نقش اتصال، provider مشترک، یا reuse زیرساخت را دارند.
- اگر مجبور به تغییر فایل عمومی شدیم، تغییر باید بسیار نازک و قابل توضیح باشد.

---


## 2. قانون سخت مرز کد و عدم آسیب به Giso

قبل از هر تغییر اجرایی، Agent باید `project_memory/letta/CODE_BOUNDARY_RULES_BUTI_AI.md` را بخواند و رعایت کند.

خلاصه الزام‌ها:

- کد اختصاصی Buti AI داخل `giso/buti_ai/` بماند.
- تغییرات خارج از این پوشه فقط اتصال نازک و ضروری باشند.
- هیچ flow موجود Giso، مخصوصاً تحلیل‌های فعلی، نباید خراب شود.
- اگر نیاز به تغییر فایل عمومی بود، دلیل آن باید در توضیح commit/PR روشن باشد.
- اگر جای درست کد مشخص نبود، کدنویسی متوقف شود و از کاربر پرسیده شود.

---

## 3. محدوده MVP مرحله اول

MVP اول نباید از همان ابتدا پیچیده شود.

نسخه اول باید این مسیر را بدهد:

```text
ورود به آینه زیبایی
→ انتخاب آینه ابرو
→ انتخاب سلیقه/مدل
→ آپلود عکس
→ بررسی کیفیت اولیه عکس
→ تحلیل ابرو با AI یا fallback کنترل‌شده
→ نمایش نتیجه متنی شیک
→ CTA برای مشاهده مراکز/رزرو
```

در MVP اول، preview تصویری واقعی می‌تواند هنوز فعال نباشد. اگر provider تصویر آماده نبود، باید fallback شفاف نمایش داده شود:

> پیش‌نمایش تصویری در حال آماده‌سازی است؛ فعلاً پیشنهاد تخصصی متنی برای شما نمایش داده می‌شود.

---

## 4. ساختار پیشنهادی آینده داخل `giso/buti_ai/`

این‌ها طراحی هستند و فعلاً فایل اجرایی ساخته نشده است.

```text
giso/buti_ai/
  __init__.py
  routes.py                 # blueprint/routeهای آینه زیبایی
  services.py               # اگر ساختار فعلی ساده است، serviceهای MVP می‌تواند اینجا شروع شود
  models.py                 # فقط اگر ذخیره‌سازی/DB اختصاصی لازم شد
  prompts.py                # promptهای اختصاصی Buti AI اگر معماری اجازه دهد
  eyebrow/
    flow.py                 # orchestration سناریوی ابرو
    prompts.py              # promptهای ابرو در صورت نیاز به تفکیک
    photo_quality.py        # بررسی کیفیت عکس
    analysis.py             # تبدیل خروجی vision به نتیجه قابل نمایش
    preview.py              # placeholder/fallback/اتصال آینده به image generation
  templates/
    buti_ai/
      index.html
      eyebrow_wizard.html
      eyebrow_result.html
  static/
    buti_ai/
      buti-ai.css
      buti-ai.js
```

اگر ساختار فعلی `giso/buti_ai/` ساده‌تر باشد، مرحله اول می‌تواند با تعداد فایل کمتر انجام شود؛ اما اصل تفکیک باید حفظ شود.

---

## 5. Routeهای پیشنهادی MVP

نام routeها باید با UI فارسی سازگار باشد ولی در کد واضح و انگلیسی بماند.

پیشنهاد:

```text
GET  /buti-ai/
GET  /buti-ai/eyebrow
POST /buti-ai/eyebrow/session
POST /buti-ai/eyebrow/upload
POST /buti-ai/eyebrow/analyze
GET  /buti-ai/eyebrow/result/<session_id>
GET  /buti-ai/eyebrow/centers/<session_id>
```

اگر مسیر فعلی `giso/buti_ai/` route دیگری دارد، باید با آن سازگار شود و routeهای نهایی بعد از خواندن کد واقعی انتخاب شوند.

---

## 6. مرز اتصال با بخش‌های دیگر Giso

### 6.1 `giso/analysis.py`

نقش مجاز:

- reuse الگوهای upload/validation،
- فهمیدن مسیر فعلی تحلیل تصویر،
- استفاده از helperهای مشترک اگر وجود دارند.

نقش غیرمجاز:

- انتقال منطق آینه ابرو به `giso/analysis.py`.

### 6.2 `giso/ai_brain.py`

نقش مجاز:

- استفاده از provider/vision call فعلی مثل `ask_ai_vision` در صورت مناسب بودن.

نقش غیرمجاز:

- قرار دادن prompt کامل ابرو و flow محصول داخل `ai_brain.py`.

### 6.3 `giso/beauty_centers/`

نقش مجاز:

- نمایش مراکز مرتبط،
- لینک رزرو،
- ثبت lead یا درخواست بعد از نتیجه.

نقش غیرمجاز:

- مالک شدن منطق آینه زیبایی یا wizard.

### 6.4 `giso/prompts/`

اگر معماری فعلی Giso promptها را در `giso/prompts/` نگه می‌دارد، promptهای Buti AI باید با نام واضح ساخته شوند، مثل:

```text
giso/prompts/buti_ai_eyebrow_quality.md
giso/prompts/buti_ai_eyebrow_analysis.md
```

اما wrapper و orchestration همچنان باید در `giso/buti_ai/` بماند.

---

## 7. داده‌های مورد نیاز session

حداقل داده‌های یک session آینه ابرو:

```json
{
  "session_id": "",
  "user_id": null,
  "service": "eyebrow",
  "selected_style": "natural | microblading | powder | combination | giso_suggested",
  "change_level": "very_natural | medium | clear",
  "photo_path": "",
  "photo_quality": {},
  "analysis_result": {},
  "preview_status": "not_requested | fallback | generated | failed",
  "created_at": "",
  "updated_at": ""
}
```

در MVP اول، اگر schema فعلی `giso/buti_ai/` session دارد، باید از همان استفاده یا آن را در همان ماژول توسعه داد. نباید برای این کار جدول/منطق پراکنده در بخش‌های دیگر ساخته شود.

---

## 8. Promptهای MVP

MVP به سه prompt اصلی نیاز دارد:

1. بررسی کیفیت عکس
2. تحلیل فرم ابرو و پیشنهاد مدل
3. تبدیل خروجی تحلیل به متن فارسی کاربرپسند

Prompt پیش‌نمایش تصویری در مرحله بعد فعال می‌شود، مگر اینکه provider تصویر از قبل آماده و امن باشد.

قانون مهم preview:

- فقط ابرو تغییر کند.
- هویت چهره حفظ شود.
- پوست، چشم، بینی، لب، مو، پس‌زمینه و نور عوض نشود.

---

## 9. UI/UX MVP

UI باید با سبک سایت فعلی گیسو هماهنگ باشد:

- فارسی و RTL،
- مراحل کوتاه،
- دکمه‌های واضح،
- متن‌های دوستانه،
- کارت‌های ساده برای مدل ابرو،
- پیام خطای محترمانه برای عکس نامناسب،
- CTA روشن برای مراکز زیبایی.

صفحات MVP:

```text
index: معرفی آینه زیبایی
wizard: انتخاب مدل + آپلود
loading/result: تحلیل و نمایش نتیجه
centers: مراکز مرتبط و رزرو
```

---

## 10. Acceptance Criteria مرحله ۳، وقتی کدنویسی مجاز شد

وقتی کاربر مجوز کدنویسی داد، فاز پیاده‌سازی پایه زمانی قبول است که:

- همه کدهای اختصاصی آینه ابرو داخل `giso/buti_ai/` باشد.
- route پایه آینه ابرو باز شود.
- کاربر بتواند مدل/سلیقه انتخاب کند.
- کاربر بتواند عکس آپلود کند یا در حالت demo/fallback مسیر را ببیند.
- نتیجه متنی فارسی نمایش داده شود.
- اگر AI آماده نبود، خطای خام نشان داده نشود و fallback شفاف باشد.
- لینک/CTA به مراکز زیبایی وجود داشته باشد.
- `web/`, `bot_edu/`, `main.py` تغییر نکند مگر با مجوز صریح.
- مسیرهای تحلیل فعلی مو/پوست خراب نشود.

---

## 11. ترتیب اجرای بعدی

ترتیب قطعی:

1. Project Memory و سناریو ثبت و push شود. **انجام شد.**
2. طراحی فنی MVP ثبت شود. **این سند.**
3. فقط بعد از تأیید کدنویسی، فاز 1 داخل `giso/buti_ai/` پیاده‌سازی شود.
4. بعد از MVP پایه، AI analysis اضافه شود.
5. بعد preview/fallback تصویری اضافه شود.
6. بعد اتصال عمیق به مراکز/رزرو/پنل/آمار انجام شود.

---

## 12. کارهایی که فعلاً نباید انجام شود

- ساخت پروژه جدا بیرون از Giso.
- پخش کردن routeها و serviceهای آینه زیبایی در فایل‌های نامرتبط.
- تغییر سنگین `giso/analysis.py` یا `giso/ai_brain.py`.
- refactor کردن `giso/bot.py`.
- تغییر `web/`, `bot_edu/`, `main.py`.
- ذخیره API key یا secret در Project Memory یا repo.
- اجرای preview تصویر بدون safety/fallback.

---

## 13. اجرای فعلی فاز ۱

مرحله اجرا شروع شده و این طراحی به شکل MVP پایه اعمال شده است:

- Landing page آینه زیبایی: `/analysis/mirror`
- Wizard آینه ابرو: `/analysis/mirror/eyebrow`
- اتصال مراکز زیبایی: `/analysis/mirror/eyebrow/centers`
- کارت آینه در صفحه آنالیز از template داخل Buti AI خوانده می‌شود.

نکته مهم:

- هنوز AI vision و image generation اضافه نشده است.
- خروجی فعلی، fallback/راهنمای متنی MVP است.
- این وضعیت برای شروع تجربه کاربری و تثبیت معماری ماژول کافی است.

---

## 14. فاز ۱.۵ — ساختار واقعی اجراشده

ساختار پیشنهادی مرحله طراحی برای سناریوی ابرو اکنون به شکل سبک‌تر اجرا شده است:

```text
giso/buti_ai/eyebrow/
  __init__.py
  options.py
  upload.py
  result.py
  flow.py
```

این تقسیم‌بندی جایگزین قرار گرفتن منطق محصول در `routes.py` شد. مسیرها همچنان همان مسیرهای فاز ۱ هستند:

```text
/analysis/mirror
/analysis/mirror/eyebrow
/analysis/mirror/eyebrow/centers
```

مرحله بعدی پیشنهادی پس از تأیید کاربر:

1. UI/UX polish روی همین ساختار، یا
2. اضافه کردن quality check عکس با AI داخل همین پکیج، بدون دست زدن به تحلیل‌های مو/پوست.
