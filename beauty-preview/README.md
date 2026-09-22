# 💎 پیش‌نمایش هوشمند ابرو — شبیه‌ساز میکروبلیدینگ

وب‌اپ تک‌صفحه‌ای **Next.js 14 + TypeScript + Tailwind** (RTL، فارسی، فونت وزیرمتن) که به کاربر
اجازه می‌دهد مدل و رنگ ابرو را انتخاب کند، عکس چهره‌اش را آپلود کند و پیش‌نمایش میکروبلیدینگ را
با هوش مصنوعی ببیند.

```
beauty-preview/
├── app/
│   ├── layout.tsx              ← RTL + فونت وزیرمتن (لوکال) + متادیتا
│   ├── page.tsx                ← تنها صفحه: ۵ مرحله (مدل، رنگ، عکس، ساخت، نتیجه)
│   ├── globals.css             ← تم تیره/لوکس، کلاس‌های مشترک (btn-gold، tooltip…)
│   ├── fonts/                  ← Vazirmatn (self-hosted) + مجوز OFL
│   ├── api/generate/route.ts   ← روت اصلی: اعتبارسنجی + زنجیرهٔ پروایدرها
│   └── api/providers/route.ts  ← بررسی سلامت پروایدرها/کلیدها (?check=1)
└── src/                        ← ⚠️ نام پوشه عمداً src است (نه lib): الگوی lib/
    │                              در .gitignore ریشهٔ ریپو هر پوشهٔ lib/ را نادیده می‌گیرد
    ├── options.ts              ← ۴ مدل ابرو، ۶ رنگ، پیام/لینک واتساپ، پرامپت انگلیسی
    ├── brow-shapes.ts          ← مولد تصاویر SVG ابرو (بدون چهره، پس‌زمینهٔ شفاف)
    └── providers/
        ├── index.ts            ← زنجیرهٔ جایگزین: Runware → SiliconFlow → AIMLAPI → Pollinations
        ├── http.ts             ← ابزار مشترک: تجزیهٔ data URI، timeout، خواندن امن نتیجه
        ├── runware.ts          ← آرایهٔ JSON، دو مرحله: imageUpload سپس imageInference
        ├── siliconflow.ts      ← OpenAI SDK: images.edit با Qwen/Qwen-Image-Edit
        ├── aimlapi.ts          ← image_url: flux/kontext-pro/image-to-image
        └── pollinations.ts     ← OpenAI SDK: images.edits با مدل kontext
```

---

## ۱) راه‌اندازی

```bash
cd beauty-preview
npm install
cp .env.example .env.local     # کلیدهای API را داخلش بگذارید (یا در .env)
npm run dev                    # http://localhost:3000
```

اسکریپت‌های دیگر:

```bash
npm run build       # ساخت نسخهٔ production
npm start           # اجرای نسخهٔ ساخته‌شده روی پورت ۳۰۰۰
npm run type-check  # بررسی تایپ‌ها (tsc --noEmit)
npm run test:chain  # تست زنجیرهٔ جایگزین با سرور mock (بدون مصرف اعتبار)
```

### ⚠️ مهم — کلیدها را کامیت نکنید

- فایل‌های `.env` و `.env.local` در `.gitignore` هستند؛ **هرگز** آن‌ها را `git add` نکنید.
- اگر کلیدی اشتباهاً کامیت و پوش شد، فرض کنید **سوخته** است: همان لحظه کلید را در پنل
  پروایدر باطل/چرخش (rotate) کنید. پاک‌کردن فایل، کلیدِ رفته در تاریخچهٔ گیت را بی‌اثر نمی‌کند.
- ترتیب اولویت در Next.js:

  ```
  .env.development.local  →  .env.local  →  .env.development  →  .env
  ```

  ⚠️ اگر متغیری را در فایل بالاتر **خالی** بگذارید (مثلاً `RUNWARE_API_KEY=` در `.env.local`)،
  همان مقدار خالی بر `.env` غلبه می‌کند و پروایدر غیرفعال می‌شود. پس کلیدها را فقط در **یک**
  فایل مقدار بدهید.

### تست سلامت کلیدها (درخواست واقعی)

با یک درخواست GET، هر کلید به‌صورت جداگانه و واقعی آزمایش می‌شود:

```bash
curl "http://localhost:3000/api/providers?check=1"      # تست واقعی همهٔ پروایدرها
curl "http://localhost:3000/api/providers"              # فقط وضعیت (بدون مصرف اعتبار)
```

خروجی نمونه:

```json
{
  "ok": true,
  "demo": false,
  "summary": "2 از 4 پروایدر سالم است",
  "providers": [
    { "id": "runware", "label": "Runware", "envKey": "RUNWARE_API_KEY", "configured": true, "ok": true, "ms": 4210 },
    { "id": "siliconflow", "label": "SiliconFlow", "envKey": "SILICONFLOW_API_KEY", "configured": true, "ok": false, "ms": 30012, "error": "..." }
  ]
}
```

> حالت `check=1` یک تصویر ۸×۸ واقعی تولید می‌کند و ممکن است مقدار ناچیزی از اعتبار حساب
> مصرف شود؛ برای همین به‌صورت پیش‌فرض خاموش است.

---

## ۲) کلیدهای API و زنجیرهٔ جایگزین

همهٔ فراخوانی‌ها **فقط سمت سرور** در `app/api/generate/route.ts` انجام می‌شود و هیچ کلیدی به
مرورگر نمی‌رود. پروایدرها به این ترتیب امتحان می‌شوند؛ اگر کلیدی خالی باشد آن پروایدر رد می‌شود
(skip) و اگر خطا بدهد، پروایدر بعدی امتحان می‌شود:

| # | پروایدر | متغیر محیطی | نحوهٔ فراخوانی |
|---|---------|--------------|-----------------|
| ۱ | [Runware](https://runware.ai/docs) | `RUNWARE_API_KEY` | `POST https://api.runware.ai/v1` — آرایهٔ JSON (غیر OpenAI): ابتدا `imageUpload` سپس `imageInference` با `seedImage` و مدل `bfl:flux-1-kontext-pro@1` |
| ۲ | [SiliconFlow](http://docs.siliconflow.com/) | `SILICONFLOW_API_KEY` | OpenAI SDK → `images.edit` با `Qwen/Qwen-Image-Edit`؛ در صورت خطا مسیر جایگزین `images/generations` با فیلد `image` |
| ۳ | [AIMLAPI](https://docs.aimlapi.com/) | `AIMLAPI_API_KEY` | `POST /v1/images/generations` با `model: flux/kontext-pro/image-to-image` و فیلد `image_url` |
| ۴ | [Pollinations](https://gen.pollinations.ai/docs) | `POLLINATIONS_API_KEY` | OpenAI SDK → `images.edit` با مدل `kontext` (کلید `sk_...`) |

خواندن نتیجه در همهٔ پروایدرها امن است (هم `url` و هم `b64_json` پشتیبانی می‌شود):

```ts
const img = response.data?.[0];
const url = img?.url ?? (img?.b64_json ? `data:image/png;base64,${img.b64_json}` : null);
if (!url) throw new Error('هیچ تصویری دریافت نشد');
```

پس از دریافت آدرس تصویر، سرور آن را به **data URI** تبدیل می‌کند تا دکمهٔ «دانلود تصویر» در
مرورگر بدون مشکل CORS کار کند.

### حالت نمایشی (بدون کلید API)

`DEMO_MODE` سه مقدار دارد:

- `auto` (پیش‌فرض): اگر هیچ کلید API‌ای تنظیم نشده باشد، صفحه در **حالت نمایشی** کار می‌کند؛
  شکل ابرو با مدل و رنگ انتخابی، به‌صورت محلی روی عکس کشیده می‌شود تا کل مسیر صفحه قابل تست باشد.
- `on` / `off`: فعال یا غیرفعال کردن همیشگی.

برچسب «حالت نمایشی» و توضیح شفاف در نتیجه نمایش داده می‌شود تا با خروجی واقعی هوش مصنوعی
اشتباه گرفته نشود.

---

## ۳) جریان کار صفحه (app/page.tsx)

| مرحله | توضیح |
|-------|-------|
| ۱ — مدل ابرو | ۴ کارت (۲×۲) با تصویر SVG تولیدی و نام فارسی: هایر استروک طبیعی، فدر براو، اومبره پودری، کامبینیشن. انتخاب‌شده = حاشیهٔ طلایی + تیک |
| ۲ — رنگ | ۶ دایرهٔ رنگ با tooltip نام فارسی (قهوه‌ای طبیعی `#8B6914`، قهوه‌ای تیره `#5C3D11`، بلوند `#C4A265`، خاکستری تیره `#4A4A4A`، مشکی نرم `#2C2C2C`، قهوه‌ای قرمز `#7B3F00`). انتخاب‌شده = حلقهٔ سفید |
| ۳ — آپلود عکس | کادر drag & drop با برچسب «عکس چهره خود را آپلود کنید»، فقط JPG/PNG/WEBP و حداکثر ۵ مگابایت، به‌همراه thumbnail و دکمهٔ حذف |
| ۴ — دکمهٔ ساخت | دکمهٔ طلایی «ایجاد پیش‌نمایش هوشمند» — فقط با انتخاب مدل + رنگ + عکس فعال می‌شود |
| ۵ — نتیجه | اسلایدر مقایسه (`react-compare-slider`) با برچسب «قبل» (چپ) و «بعد» (راست)، دکمهٔ «دانلود تصویر» و دکمهٔ واتساپ با پیام آماده |

مراحل ۲ و ۳ تا تکمیل مرحلهٔ قبل کم‌رنگ و غیرفعال هستند (بدون پنهان کردن ساختار صفحه).

### پیام واتساپ

```
سلام خانم رجبی، مدل [نام مدل] با رنگ [نام رنگ] برای میکروبلیدینگ انتخاب کردم و می‌خواهم نوبت بگیرم.
```

به لینک `https://wa.me/989058674412` با پارامتر `text` (URL-encoded) وصل می‌شود.

### پرامپت ارسالی به هوش مصنوعی

```
Apply professional microblading eyebrows in the style of <مدل> (<English Name>)
with color <HEX> (<نام فارسی رنگ>) to this face photo.
Keep everything else exactly the same.
Realistic, natural, high quality beauty result.
```

نام انگلیسی هر مدل از `labelEn` در `src/options.ts` می‌آید تا مدل‌های تصویری (که فارسی را
ضعیف می‌فهمند) دقیق‌تر عمل کنند.

---

## ۴) تصاویر SVG ابروها

`src/brow-shapes.ts` به‌صورت برنامه‌نویسی‌شده و قطعی (deterministic) تصویر SVG می‌سازد:
مسیر بستهٔ ابرو + تارهای موی کوتاه که از لبهٔ پایین به سمت بالا و دم ابرو کشیده شده‌اند و با
`clipPath` داخل شکل ابرو بریده می‌شوند. هیچ چهره یا پوستی در تصویر نیست و پس‌زمینه کاملاً شفاف است.

اگر خواستید عکس واقعی بگذارید، فایل را در `public/eyebrows/` قرار دهید و در `src/options.ts`
مقدار `sampleImage` همان مدل را به مسیر فایل تغییر دهید؛ در غیر این صورت همان SVG تولیدی
نمایش داده می‌شود.

---

## ۵) نکات فنی

- **بدون دیتابیس، بدون auth، بدون پنل ادمین** — فقط همین یک صفحه و یک روت API.
- رنگ‌بندی: پس‌زمینه `#0A0A0A`، اکسنت `#D4AF37`، کارت‌ها `#1A1A1A`.
- چیدمان دسکتاپ-اول و وسط‌چین (`max-w-5xl`)؛ در موبایل تک‌ستونه می‌شود.
- فونت وزیرمتن **لوکال** است (`app/fonts/Vazirmatn-Variable.woff2`) تا ساخت پروژه به دسترسی به
  Google Fonts وابسته نباشد.
- `PROVIDER_TIMEOUT_MS` مهلت هر پروایدر را تعیین می‌کند (پیش‌فرض ۹۰ ثانیه).
- هیچ بستهٔ PWA نصب نشده است.
