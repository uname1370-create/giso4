# 💎 استودیو تخصصی PMU عسل رجبی — پیش‌نمایش هوشمند زیبایی

پلتفرم **چندخدمتی ویزاردی Next.js 14 + TypeScript + Tailwind** (RTL، فارسی، فونت وزیرمتن) برای
استودیو آرایش دائم عسل رجبی در مشهد. کاربر خدمت (ابرو / لب / خط چشم / ریمو) را انتخاب می‌کند،
تکنیک و سلیقهٔ خود را مشخص می‌کند، عکس چهره‌اش را آپلود می‌کند، پیش‌نمایش هوشمند را می‌بیند و
نوبت رزرو می‌کند. یک دستیار هوشمند چت (Feature-gated) و یک پنل مدیریت کامل هم دارد.

> اسناد تکمیلی: `start.md` (فازها و نیازمندی‌های محصول) و `graphify-out/GRAPH_REPORT.md`
> (نقشهٔ ساختار کد — ۵۴۱ گره، ۱۰۰۴ یال، ۲۶ جامعه).

```
beauty-preview/
├── app/
│   ├── layout.tsx                    ← RTL + فونت وزیرمتن (لوکال) + متادیتا
│   ├── page.tsx                      ← تنها صفحه: ویزارد ۶ مرحله‌ای (۰ تا ۵) + AiChatWidget
│   ├── globals.css                   ← تم تیره/لوکس، کلاس‌های مشترک (card، btn-gold، btn-whatsapp…)
│   ├── fonts/                        ← Vazirmatn (self-hosted) + مجوز OFL
│   ├── admin/                        ← پنل مدیریت: page.tsx (ورود) + dashboard/page.tsx (داشبورد)
│   └── api/
│       ├── generate/route.ts         ← روت اصلی: اعتبارسنجی + زنجیرهٔ پروایدر + فشرده‌سازی
│       ├── consult/route.ts          ← تحلیل چهره و نسخهٔ مشاوره (پشتیبان هوشمند)
│       ├── appointments/route.ts     ← ثبت لید/نوبت + ذخیرهٔ تصاویر قبل/بعد
│       ├── chat/route.ts             ← دستیار هوشمند غزل (OpenAI SDK)
│       ├── plan/route.ts             ← اطلاعات سالن و پلن (bronze/silver/gold)
│       ├── track/route.ts            ← ثبت بازدیدِ صفحهٔ اصلی (برای آمار پنل)
│       ├── providers/route.ts        ← بررسی سلامت پروایدرها/کلیدها (?check=1)
│       ├── site-image/[...path]/route.ts  ← سرو امن تصاویر آپلودی (جایگزین مستقیم public/)
│       └── admin/                    ← login, stats, leads, leads/[id], chat-logs,
│                                       tenant, upload-brow, upload-hero, upload-reference
├── src/
│   ├── options.ts                    ← ۴ سبک ابرو، ۶ رنگ، واتساپ/اینستاگرام، پرامپت انگلیسی
│   ├── brow-shapes.ts                ← مولد تصاویر SVG ابرو/لب/خط چشم (دمو، پس‌زمینهٔ شفاف)
│   ├── techniques.ts                 ← تکنیک‌های هر خدمت (۴ ابرو، ۴ لب، ۳ خط چشم)
│   ├── services-content.ts           ← محتوای ۴ خدمت: مدت زمان، ماندگاری، افراد مناسب، مراقبت
│   ├── style-dna.ts                  ← تزریق پاسخ‌های سلیقه‌ای در پرامپت (Style DNA)
│   ├── plan-config.ts                ← ماتریس امکانات پلن‌ها (برنزی/نقره‌ای/طلایی)
│   ├── db.ts                         ← دیتابیس SQLite (better-sqlite3): leads, chat_logs, tenant_settings
│   ├── storage.ts                    ← ذخیرهٔ عکس کاربر و نتیجه در public/uploads/leads/[id]/
│   ├── stats.ts                      ← خواندن/نوشتن آمار در data/stats.json
│   ├── image-compress.ts             ← فشرده‌سازی خروجی (PNG → JPEG q90، fail-open)
│   ├── admin-auth.ts                 ← توکن امزاشدهٔ پنل (ADMIN_PASSWORD + sha256)
│   ├── admin-client.ts               ← ابزار سمت مرورگر پنل (توکن، fetch، تاریخ فارسی)
│   ├── site-images.ts                ← ذخیره/حذف تصاویر آپلودی (نام‌های ثابت) + سرو امن
│   ├── providers/
│   │   ├── index.ts                  ← زنجیرهٔ پروایدرها: فقط Cloudflare؛ سهمیه تمام‌شده → demo
│   │   ├── cloudflare.ts             ← FLUX.2 Klein 4B، تا ۳ حساب مستقل
│   │   ├── openrouter.ts / pollinations.ts  ← پروایدرهای جایگزین
│   │   ├── http.ts                   ← ابزار مشترک: تجزیهٔ data URI، timeout، خواندن امن نتیجه
│   │   └── types.ts                  ← قرارداد Provider / ProviderInput / AttemptLog
│   └── lib/vision/                   ← بینایی ماشین سمت کلاینت (MediaPipe + Canvas)
│       ├── face-landmarker.ts        ← بارگذاری FaceLandmarker
│       ├── landmarks-extractor.ts    ← استخراج لندمارک‌های صورت
│       └── canvas-composite.ts       ← Hard Composite سمت کلاینت (دو مرحلهٔ فدر)
├── src/components/
│   ├── StepIndicator.tsx             ← شمارهٔ مراحل ویزارد (قابل کلیک)
│   ├── AiChatWidget.tsx              ← دستیار شناور غزل (Feature gate با پلن)
│   └── wizard/
│       ├── HeroStep.tsx              ← مرحلهٔ ۰: هیرو + شعار + CTA
│       ├── ServiceSelectStep.tsx     ← مرحلهٔ ۱: انتخاب خدمت (۴ کارت)
│       ├── PreferencesStep.tsx       ← مرحلهٔ ۲: تکنیک + ۳ سؤال سلیقه‌ای
│       ├── UploadStep.tsx            ← مرحلهٔ ۳: آپلود عکس + بازخورد نور/وضوح
│       ├── PreviewStep.tsx           ← مرحلهٔ ۴: تولید پیش‌نمایش + اسلایدر قبل/بعد
│       ├── BookingStep.tsx           ← مرحلهٔ ۵: فرم رزرو + چک‌باکس‌های ایمنی
│       ├── SafetyCheckStep.tsx       ← ۳ سؤال ایمنی پزشکی (در BookingStep)
│       └── ConsultStep.tsx           ← نمایش نتیجهٔ تحلیل چهره (از /api/consult)
├── scripts/
│   ├── mock-providers.mjs            ← سرور mock پروایدرها
│   ├── test-chain.mjs                ← تست زنجیرهٔ پروایدرها
│   ├── test-admin.mjs                ← تست پنل مدیریت
│   └── reminder.mjs                  ← اسکریپت CRON یادآوری لیدها
├── data/                             ← stats.json (آمار) + app.sqlite (CRM) + leads.json
├── public/
│   ├── eyebrows/ lips/ eyeliner/     ← تصاویر نمونهٔ تکنیک‌ها
│   ├── hero/                         ← تصویر هیرو
│   ├── services/                     ← تصاویر ۴ خدمت اصلی
│   └── uploads/leads/[id]/           ← عکس قبل/بعد هر مراجع (original.png + result.jpg)
├── schema.prisma                     ← طرح‌نمای Prisma (مدل Lead — مرجع؛ دیتابیس فعلی better-sqlite3)
├── requirements.txt                  ← نیازمندی‌های پایتونِ موتور بینایی (FastAPI/OpenCV/MediaPipe)
├── next.config.mjs                   ← distDir (NEXT_DIST_DIR) + remotePatterns
├── tailwind.config.ts · postcss.config.mjs · tsconfig.json
└── package.json                      ← next 14.2.35, react 18, openai, sharp, better-sqlite3,
                                       @mediapipe/tasks-vision, react-compare-slider
```

> ⚠️ نام پوشهٔ `src` عمداً `src` است (نه `lib`): الگوی `lib/` در `.gitignore` ریشهٔ ریپو هر
> پوشهٔ `lib/` را نادیده می‌گیرد. ماژول‌های بینایی کلاینت در `src/lib/vision/` هستند و با
> دو خط `!src/lib/` و `!src/lib/**` در `.gitignore` از این نادیده‌گرفتن مستثنا شده‌اند.

---

## ۱) راه‌اندازی

```bash
cd beauty-preview
npm install
npm run dev                    # http://localhost:3000
```

> نکته: فایل `.env.example` در پروژه وجود ندارد. کلیدها را مستقیماً در `.env.local` (یا `.env`)
> قرار دهید. این فایل‌ها داخل `.gitignore` هستند و در ریپو کامیت نمی‌شوند.

اسکریپت‌های موجود (`package.json`):

```bash
npm run dev             # next dev -H 0.0.0.0 -p 3000
npm run build           # ساخت نسخهٔ production
npm start               # اجرای نسخهٔ ساخته‌شده روی پورت ۳۰۰۰
npm run type-check      # بررسی تایپ‌ها (tsc --noEmit)
npm run mock:providers  # بالا آوردن سرور mock پروایدرها
npm run test:chain      # تست زنجیرهٔ پروایدرها با سرور mock (بدون مصرف اعتبار)
npm run test:admin      # تست پنل مدیریت (آمار و تصاویر واقعی را دست‌نخورده می‌گذارد)
```

### ⚠️ مهم — کلیدها را کامیت نکنید

- فایل‌های `.env` و `.env.local` در `.gitignore` هستند؛ **هرگز** آن‌ها را `git add` نکنید.
- اگر کلیدی اشتباهاً کامیت و پوش شد، فرض کنید **سوخته** است: همان لحظه کلید را در پنل
  پروایدر باطل/چرخش (rotate) کنید. پاک‌کردن فایل، کلیدِ رفته در تاریخچهٔ گیت را بی‌اثر نمی‌کند.
- ترتیب اولویت در Next.js:

  ```
  .env.development.local  →  .env.local  →  .env.development  →  .env
  ```

  ⚠️ اگر متغیری را در فایل بالاتر **خالی** بگذارید (مثلاً `CLOUDFLARE_API_TOKEN_1=` در `.env.local`)،
  همان مقدار خالی بر `.env` غلبه می‌کند و آن پروایدر غیرفعال می‌شود. پس کلیدها را فقط در **یک**
  فایل مقدار بدهید.

### تست سلامت کلیدها (درخواست واقعی)

با یک درخواست GET، هر کلید به‌صورت جداگانه و واقعی آزمایش می‌شود:

```bash
curl "http://localhost:3000/api/providers?check=1"      # تست واقعی همهٔ پروایدرها
curl "http://localhost:3000/api/providers"              # فقط وضعیت (بدون مصرف اعتبار)
curl "http://localhost:3000/api/providers?check=1&timeout=30000"   # مهلت هر بررسی
```

خروجی نمونه:

```json
{
  "ok": true,
  "demo": false,
  "summary": "1 از 1 پروایدر سالم است",
  "providers": [
    { "id": "cloudflare", "label": "Cloudflare", "envKey": "CLOUDFLARE_API_TOKEN_1", "configured": true, "ok": true, "ms": 4210 }
  ]
}
```

> حالت `check=1` یک تصویر ۸×۸ واقعی تولید می‌کند و ممکن است مقدار ناچیزی از اعتبار حساب
> مصرف شود؛ برای همین به‌صورت پیش‌فرض خاموش است.

---

## ۲) کلیدهای API و زنجیرهٔ پروایدرها

همهٔ فراخوانی‌ها **فقط سمت سرور** در `app/api/generate/route.ts` انجام می‌شود و هیچ کلیدی به
مرورگر نمی‌رود. زنجیرهٔ فعلی **تک‌پروایدر** است (`src/providers/index.ts`):

| # | پروایدر | متغیر محیطی | نحوهٔ فراخوانی |
|---|---------|--------------|-----------------|
| ۱ | [Cloudflare Workers AI](https://developers.cloudflare.com/workers-ai/) | `CLOUDFLARE_API_TOKEN_1` + `CLOUDFLARE_ACCOUNT_ID_1` (و حساب‌های ۲ و ۳) | `POST /accounts/{id}/ai/run/@cf/black-forest-labs/flux-2-klein-4b` — تا ۳ حساب مستقل، پشت‌سرهم |

رفتار زنجیره:

- اگر کلید یک حساب تنظیم نشده باشد، آن حساب **رد (skip)** می‌شود.
- اگر خطا بدهد، حساب بعدی امتحان می‌شود.
- اگر همهٔ حساب‌ها شکست بخورند، به‌جای خطای ۵۰۲ پاسخ `demo: true` برگردانده
  می‌شود تا مسیر کاربر قطع نشود.
- ترتیب پروایدرها با `PROVIDER_ORDER` (لیست شناسه‌ها با کاما) قابل تنظیم است؛ شناسه‌های
  ناشناخته نادیده گرفته می‌شوند.

خواندن نتیجه در همهٔ پروایدرها امن است (هم `url` و هم `b64_json` پشتیبانی می‌شود):

```ts
const img = response.data?.[0];
const url = img?.url ?? (img?.b64_json ? `data:image/png;base64,${img.b64_json}` : null);
if (!url) throw new Error('هیچ تصویری دریافت نشد');
```

پس از دریافت آدرس تصویر، سرور آن را به **data URI** تبدیل می‌کند تا دکمهٔ «دانلود تصویر» در
مرورگر بدون مشکل CORS کار کند. سپس `src/image-compress.ts` آن PNG بزرگ را به **JPEG باکیفیت**
(پیش‌فرض q90، mozjpeg) تبدیل می‌کند:

- `IMAGE_COMPRESS=off` → بدون فشرده‌سازی.
- `IMAGE_JPEG_QUALITY=1..100` (پیش‌فرض ۹۰).
- fail-open: اگر `sharp` نصب نباشد یا خطایی بدهد، همان تصویر اصلی برمی‌گردد.

### متغیرهای محیطی

| متغیر | توضیح |
| --- | --- |
| `CLOUDFLARE_API_TOKEN_1..3` + `CLOUDFLARE_ACCOUNT_ID_1..3` | تا ۳ حساب مستقل Cloudflare |
| `CLOUDFLARE_MODEL` | مدل تصویرسازی (پیش‌فرض `@cf/black-forest-labs/flux-2-klein-4b`) |
| `CLOUDFLARE_VISION_MODEL` | مدل بینایی سرور |
| `OPENAI_API_KEY` | دستیار هوشمند غزل (`app/api/chat/route.ts`) |
| `POLLINATIONS_API_KEY` | پروایدر جایگزین Pollinations |
| `ADMIN_PASSWORD` | رمز پنل مدیریت (پیش‌فرض `1234`) |
| `DEMO_MODE` | `auto` (پیش‌فرض) / `on` / `off` |
| `PROVIDER_TIMEOUT_MS` | مهلت سراسری هر پروایدر (پیش‌فرض ۹۰ ثانیه) |

### حالت نمایشی (بدون کلید API)

`DEMO_MODE` سه مقدار دارد:

- `auto` (پیش‌فرض): اگر هیچ کلید API‌ای تنظیم نشده باشد، صفحه در **حالت نمایشی** کار می‌کند؛
  ابرو/لب/خط چشم با مدل و رنگ انتخابی، به‌صورت محلی (SVG) روی عکس کشیده می‌شود تا کل مسیر
  صفحه قابل تست باشد.
- `on` / `off`: فعال یا غیرفعال کردن همیشگی.

برچسب «حالت نمایشی» و توضیح شفاف در نتیجه نمایش داده می‌شود تا با خروجی واقعی هوش مصنوعی
اشتباه گرفته نشود.

---

## ۳) جریان کار صفحه (app/page.tsx)

ویزارد **۶ مرحله‌ای** است (`WIZARD_STEPS`)؛ هر مرحله یک کامپوننت جداگانه در `src/components/wizard/`
است که از طریق props کنترل می‌شود:

| مرحله | کامپوننت | توضیح |
|-------|-----------|-------|
| ۰ — خانه | `HeroStep` | تصویر هیرو، شعار «تو زیبایی؛ من فقط کشفش می‌کنم ✨»، دکمهٔ CTA |
| ۱ — انتخاب خدمت | `ServiceSelectStep` | ۴ کارت: میکروبلیدینگ ابرو، شیدینگ لب، خط چشم و بن‌مژه، ریمو تخصصی |
| ۲ — سلیقه و انتخاب مدل | `PreferencesStep` | کارت‌های تکنیک (متناسب با خدمت) + ۳ سؤال (آرایش روزانه، فرم ابرو، تراکم) |
| ۳ — آپلود تصویر | `UploadStep` | فقط JPG/PNG/WEBP و حداکثر ۵ مگابایت، با بازخورد کیفیت عکس |
| ۴ — پیش‌نمایش هوشمند | `PreviewStep` | دکمهٔ تولید → `POST /api/generate` → اسلایدر قبل/بعد + دکمهٔ دانلود و واتساپ |
| ۵ — رزرو نوبت | `BookingStep` | فرم نام/شماره/اینستاگرام + `SafetyCheckStep` (۳ سؤال ایمنی پزشکی) |

مرحلهٔ ۲ نتایج تحلیل چهره را هم از `GET /api/consult` می‌گیرد (فرم صورت، تقارن، زیرتن پوست،
فیتزپاتریک) که در `ConsultStep` نمایش داده می‌شود. در خدمت **ریمو** تولید تصویر انجام نمی‌شود
و کاربر مستقیم به مشاوره و رزرو هدایت می‌شود.

> اگر کاربر انتخابش را بعد از تولید پیش‌نمایش عوض کند، نتیجهٔ قبلی به‌عنوان «کهنه» (stale)
> شناخته و دور ریخته می‌شود.

### پیام واتساپ

```
سلام خانم رجبی، برای [نام خدمت] با مدل [نام مدل] می‌خواهم مشاوره و نوبت بگیرم.
```

به لینک `https://wa.me/989058674412` با پارامتر `text` (URL-encoded) وصل می‌شود
(`WHATSAPP_NUMBER` در `src/options.ts`).

### پرامپت ارسالی به هوش مصنوعی

پرامپت از `buildEnglishPrompt` در `src/options.ts` ساخته می‌شود؛ برای هر خدمت یک بلوک
SCOPE اختصاصی دارد (مثلاً برای لب: «فقط ناحیهٔ lip vermilion، بدون overlining») که از
`styleDesignSpec` (قرارداد فنی هر تکنیک) و `STYLE_DNA` (پاسخ‌های سلیقه‌ای از `src/style-dna.ts`)
تغذیه می‌شود. نمونهٔ بخش ابرو:

```
Apply professional microblading eyebrows in the style of <مدل> (<English Name>)
with color <HEX> (<نام فارسی رنگ>) to this face photo.
Keep everything else exactly the same.
Realistic, natural, high quality beauty result.
```

نام انگلیسی هر مدل از `labelEn` می‌آید تا مدل‌های تصویری (که فارسی را ضعیف می‌فهمند) دقیق‌تر
عمل کنند.

### امنیت تصویر (Hard Composite)

پیکسل‌های خارج از ناحیهٔ ویرایش از عکس اصلی بازیابی می‌شوند تا چهرهٔ کاربر هرگز تغییر نکند.
این منطق **دو نسخه** دارد:

- **سمت کلاینت** — `src/lib/vision/` (MediaPipe FaceLandmarker + Canvas): ماسک دو مرحله‌ای
  فدر، رسم چندضلعی و ترکیب نهایی. خروجی نهایی برای ثبت نوبت به صفحه رزرو داده می‌شود.
- **سمت سرور** — در `src/providers/`، محدود کردن ویرایش به ناحیهٔ مجاز از طریق پرامپت و
  پردازش تصویر (sharp).

---

## ۴) تصاویر نمونهٔ تکنیک‌ها

تصاویر نمونه‌کار هر تکنیک از `src/techniques.ts` خوانده می‌شوند:

| خدمت | تکنیک‌ها | پوشهٔ تصاویر |
| --- | --- | --- |
| ابرو | هایر استروک طبیعی، فدر براو، آمبره پودری، کامبینیشن | `public/eyebrows/` |
| لب | لیپ بلاش آبرنگی، نود پینک، فول کالر، خنثی‌سازی تیرگی | `public/lips/` |
| خط چشم | بن‌مژه مخفی، خط چشم کلاسیک، شیدینگ اسموکی | `public/eyeliner/` |

مدیر می‌تواند هر تصویر را از پنل (`POST /api/admin/upload-reference`) جایگزین کند؛ فایل با
نام `<styleKey>.png` در پوشهٔ `public/<service>/` ذخیره می‌شود.

برای ابروها، اگر تصویر واقعی وجود نداشته باشد، `src/brow-shapes.ts` به‌صورت قطعی (deterministic)
تصویر SVG می‌سازد: مسیر بستهٔ ابرو + تارهای موی کوتاه که از لبهٔ پایین به سمت بالا کشیده شده‌اند
و با `clipPath` داخل شکل ابرو بریده می‌شوند. هیچ چهره یا پوستی در تصویر نیست و پس‌زمینه شفاف است.

---

## ۵) پنل مدیریت — `/admin`

آدرس: `http://localhost:3000/admin` — رمز از `ADMIN_PASSWORD` خوانده می‌شود و اگر تنظیم نشده
باشد، رمز پیش‌فرض **`1234`** است. هیچ کتابخانهٔ احراز هویتی نصب نشده است: رمز با یک درخواست
ساده به `/api/admin/login` فرستاده می‌شود، در پاسخ یک **توکن امزاشدهٔ ۱۲ ساعته** می‌آید و در
`sessionStorage` مرورگر (کلید `beauty_admin_token`) نگه داشته می‌شود. توکن با یک هش SHA-256 از
`ADMIN_PASSWORD` ساخته می‌شود؛ بنابراین تغییر رمز همهٔ توکن‌های قبلی را باطل می‌کند.

برای ابزارهای ساده (curl، اسکریپت) روش سادهٔ جایگزین هم کار می‌کند: هدر
`x-admin-password: <ADMIN_PASSWORD>` روی هر روت `/api/admin/*`.

| بخش | توضیح |
| --- | --- |
| 📊 **آمار بازدید** | کارت‌های بازدید امروز/کل و پیش‌نمایش‌های ساخته‌شده + آخرین رویدادها با تاریخ/ساعت فارسی |
| 👥 **مدیریت مراجعین (CRM)** | جدول لیدها (نام، شماره، خدمت، تاریخ، وضعیت)، مودال جزئیات با عکس قبل/بعد، تغییر وضعیت، یادداشت، تماس مستقیم واتساپ، حذف امن |
| 🖼️ **تصاویر ابرو** | آپلود عکس واقعی برای هر یک از ۴ سبک (فقط JPG، حداکثر ۵ مگابایت) |
| 🌟 **تصویر هیرو** | آپلود بنر بالای صفحهٔ اصلی (JPG/PNG/WEBP، حداکثر ۱۰ مگابایت) |
| 📚 **تصاویر مرجع** | آپلود/جایگزینی تصویر نمونهٔ هر تکنیک |
| 💬 **دستیار هوشمند** | فعال/غیرفعال کردن چت‌بات، ویرایش نام دستیار و پیام خوشامد، مشاهدهٔ تاریخچهٔ مکالمات |
| 🏪 **تنظیمات سالن** | نام سالن، پلن (bronze/silver/gold)، سهمیهٔ ماهانهٔ تولید |

### روت‌های API پنل

| روت | متدها | توضیح |
| --- | --- | --- |
| `/api/admin/login` | POST | ورود و دریافت توکن |
| `/api/admin/stats` | GET | خلاصهٔ آمار |
| `/api/admin/leads` | GET | فهرست همهٔ لیدها |
| `/api/admin/leads/[id]` | GET · PATCH · DELETE | جزئیات، تغییر وضعیت/یادداشت، حذف امن |
| `/api/admin/chat-logs` | GET | تاریخچهٔ مکالمات چت |
| `/api/admin/tenant` | GET · PATCH | تنظیمات سالن و پلن |
| `/api/admin/upload-brow` | POST | آپلود تصویر سبک ابرو |
| `/api/admin/upload-hero` | POST | آپلود تصویر هیرو |
| `/api/admin/upload-reference` | POST | آپلود تصویر مرجع تکنیک |

### نام فایل‌های ثابت

| مدل ابرو | فایل |
| --- | --- |
| هایر استروک طبیعی | `public/eyebrows/natural-hairstroke.jpg` |
| فدر براو | `public/eyebrows/feather.jpg` |
| آمبره پودری | `public/eyebrows/ombre-powder.jpg` |
| کامبینیشن | `public/eyebrows/combination.jpg` |

تصویر هیرو با نام `hero.<ext>` (jpg/png/webp — فقط یکی هم‌زمان) در `public/hero/` ذخیره می‌شود.

`src/options.ts` برای هر سبک دو آدرس دارد: `imagePath` (مسیر فایل داخل public، همان نام‌های
بالا) و `imageUrl` (آدرسی که مرورگر می‌خواند). صفحهٔ اصلی اول `imageUrl` را امتحان می‌کند و اگر
فایل وجود نداشت (۴۰۴) خودکار به تصویر SVG تولیدی برمی‌گردد.

> 💡 تصاویر از روت `GET /api/site-image/...` سرو می‌شوند، نه مستقیم از `public/`؛ چون سرور
> production نکست فهرست `public/` را فقط یک بار در زمان بالا آمدن می‌خواند و فایل آپلودشده تا
> ری‌استارت سرور ۴۰۴ می‌داد. این روت در هر درخواست فایل را از دیسک می‌خواند، پس آپلود هم در
> `npm run dev` و هم در `npm run build && npm start` بلافاصله دیده می‌شود.
> نمایش تصویرها روی صفحهٔ اصلی به‌صورت client-side انجام می‌شود؛ همین باعث می‌شود کش مرورگر
> تصویر قدیمی را نشان ندهد (هدر `no-store` + پارامتر نسخه).

### آمار و دیتابیس

پروژه از دو لایهٔ ذخیره‌سازی استفاده می‌کند:

- **آمار بازدید** — فایل `data/stats.json` با ساختار `{visits, previews, history[]}`. هر بازدید
  صفحهٔ اصلی یک بار در هر نشست مرورگر و حداکثر یک بار در هر ۶ ساعت از هر IP ثبت می‌شود
  (`POST /api/track`) و هر پیش‌نمایش موفق در `app/api/generate/route.ts` یک رویداد `preview`
  می‌سازد. نوشتن‌ها با یک قفل سریال می‌شوند تا فایل خراب نشود.
- **CRM لیدها و چت** — دیتابیس SQLite `data/app.sqlite` (better-sqlite3 در `src/db.ts`) با
  سه جدول `leads`، `chat_logs` و `tenant_settings`. تصاویر هر لید در
  `public/uploads/leads/<leadId>/` (دقیقاً `original.png` و `result.jpg`) و مسیرشان در دیتابیس
  ذخیره می‌شود. فایل `data/leads.json` هم به‌عنوان لایهٔ پل باید باقی مانده است.

> ⚠️ نکات: ۱) رمز پیش‌فرض را روی سرور واقعی عوض کنید: `ADMIN_PASSWORD=...` در `.env.local`.
> ۲) آدرس پیج اینستاگرام در `src/options.ts` → `INSTAGRAM_URL` است؛ آن را با پیج واقعی خودتان
> عوض کنید. ۳) برای چند ادمین یا نقش‌های مختلف باید به سامانهٔ auth واقعی ارتقا داده شود.

---

## ۶) دستیار هوشمند غزل (AiChatWidget)

دستیار شناور چت در گوشهٔ صفحه، در `app/page.tsx` (نه در `layout.tsx`) رندر می‌شود تا دقیقاً
یک نمونه فعال باشد. نام و قابلیت دستیار از `GET /api/plan` خوانده می‌شود و متناسب با پلن سالن
(ماتریس `PLAN_CONFIGS` در `src/plan-config.ts`) فعال می‌شود — مثلاً پلن برنزی چت‌بات ندارد.

پیام‌ها به `POST /api/chat` می‌روند که با OpenAI SDK و System Prompt تخصصی (لتن صمیمی و
حرفه‌ای، بدون قیمت قطعی، بدون تشخیص پزشکی) کار می‌کند. تاریخچهٔ مکالمه‌ها در جدول `chat_logs`
ذخیره و از پنل قابل مشاهده است.

---

## ۷) نکات فنی

- **دو لایهٔ ذخیره‌سازی** — `data/stats.json` برای آمار و `data/app.sqlite` (SQLite) برای CRM.
  `schema.prisma` طرح‌نمای Prisma برای مدل `Lead` را نگه می‌دارد ولی دیتابیس فعلی پروژه با
  `better-sqlite3` در `src/db.ts` اجرا می‌شود.
- رنگ‌بندی: پس‌زمینه `#0A0A0A`، اکسنت طلایی (`gold` در متغیرهای Tailwind)، اکسنت ثانویه
  سبزرنگ (emerald) برای واتساپ و ویژگی‌ها.
- چیدمان دسکتاپ-اول و وسط‌چین (`max-w-6xl` سربرگ، `max-w-4xl` محتوای ویزارد)؛ در موبایل
  تک‌ستونه می‌شود.
- فونت وزیرمتن **لوکال** است (`app/fonts/Vazirmatn-Variable.woff2`) تا ساخت پروژه به دسترسی به
  Google Fonts وابسته نباشد.
- `PROVIDER_TIMEOUT_MS` مهلت سراسری پروایدرها را تعیین می‌کند (پیش‌فرض ۹۰ ثانیه). مهلت اختصاصی
  Cloudflare با `CLOUDFLARE_TIMEOUT_MS` و `CLOUDFLARE_GUIDANCE` (پیش‌فرض ۵) قابل تنظیم است.
- ورودی مدل klein باید کوچک‌تر از ۵۱۲×۵۱۲ باشد (توسط sharp کوچک می‌شود) و خروجی بین ۲۵۶ و
  ۱۵۳۶ پیکسل است.
- مسیر فایل آمار با `STATS_PATH` قابل تغییر است (پیش‌فرض `data/stats.json`)؛ اسکریپت‌های تست از
  همین راه آمار واقعی را دست‌نخورده می‌گذارند و در `.next-*` جداگانه build می‌گیرند تا اگر
  `npm run dev` در حال اجرا باشد خراب نشود (`NEXT_DIST_DIR` در `next.config.mjs`).
- پکیج `sharp` برای پردازش تصویر (کوچک‌کردن ورودی + فشرده‌سازی خروجی) استفاده می‌شود؛ بارگذاریِ
  آن اختیاری (fail-open) است تا نبودش پروژه را از کار نیندازد.
- **هیچ بستهٔ PWA نصب نشده است.**
- موتور بینایی پایتون (FastAPI/OpenCV/MediaPipe) در `requirements.txt` تعریف شده ولی پوشهٔ
  `vision-engine/` در پروژه وجود ندارد؛ منطق بینایی فعلاً کلاً سمت کلاینت
  (`src/lib/vision/` با `@mediapipe/tasks-vision`) و سمت سرور (`src/providers/`) پیاده‌سازی شده است.
