بخش اول سنار یو میخا روی گیسو کار کنیم

گزارش نهایی بهینه‌سازی سناریو

1. سناریوی ساده و نهایی

تحلیل هوشمند گیسو → آینه زیبایی گیسو

مسیر پیشنهادی:

آینه زیبایی گیسو

↓

انتخاب خدمت

مثلاً: ابرو

↓

معرفی خدمت + نمونه مدل‌ها + توضیح کوتاه

↓

انتخاب مدل/سلیقه

↓

آپلود عکس

↓

بررسی کیفیت و مناسب‌بودن عکس

↓

اگر مناسب نبود → اصلاح/آپلود مجدد

اگر مناسب بود → ادامه

↓

تحلیل هوشمند مخصوص همان خدمت و مدل

مثلاً برای ابرو:

فرم مناسب ابرو

تناسب با فرم صورت

ضخامت

قوس

فاصله و تقارن

حالت طبیعی یا پررنگ

نقاطی که بهتر است تغییر کنند
↓
گزارش شخصی‌سازی‌شده + پیشنهاد مدل
↓
نمایش پیش‌نمایش قبل / بعد
↓
مشاور آنلاین مخصوص همان تحلیل
↓
خدمات و مراکز ارائه‌دهنده همان خدمت
↓
انتخاب مرکز → رزرو نوبت
↓
ثبت درخواست نهایی برای مرکز

این مسیر از سناریوی اولیه بهتر است چون تحلیل، Preview و رزرو را یک زنجیره واحد می‌کند، ولی هسته فعلی Analysis را با سیستم جدید قاطی نمی‌کند.

2. وضعیت فعلی Giso

بخش

الان وجود دارد؟

نیاز به تغییر

Analysis مو

✅

کم

Analysis پوست

✅

کم

AI Vision

✅

قابل استفاده

گزارش ساختاریافته AI

✅

قابل استفاده

بررسی عکس

✅

قابل استفاده، باید برای هر خدمت توسعه مفهومی پیدا کند

آینه جادویی در صفحه Analysis

✅

فقط اتصال به Flow جدید

Beauty Preview ایده‌ای

✅ مستقل

اتصال به Giso

خدمات مراکز زیبایی

✅

باید به Analysis متصل شود

لیست مراکز

✅

باید فیلتر بر اساس خدمت/تحلیل اضافه شود

رزرو مرکز

✅

قابل اتصال

گفتگوی کاربر و مرکز

✅

قابل استفاده

پنل مرکز زیبایی

✅

عمدتاً حفظ شود

تحلیل‌های کاربر

✅

قابل توسعه

کیف پول

✅

زیرساخت مناسب دارد

هزینه هر Analysis

✅

موجود

هزینه Preview اختصاصی

❌

نیاز به تعریف

هزینه بر اساس هر خدمت

❌

نیاز به توسعه

لینک Instagram مرکز

❌ در ساختار مرکز

نیاز به فیلد/مدیریت

لینک اختصاصی Preview برای مرکز

❌

نیاز به توسعه

آمار «چند تحلیل دنبال این خدمت هستند»

❌

نیاز به داده/گزارش جدید

ارسال Lead تحلیل به مرکز

❌ به شکل کامل

نیاز به توسعه

اتصال مستقیم Analysis → Center

⚠️ پایه دارد

نیاز به تکمیل

3. خدماتی که الان در Giso تعریف شده

ساختار فعلی مراکز زیبایی این خدمات را دارد:

دسته

خدمات موجود

مو

کوتاهی، رنگ، دکلره، احیا و ترمیم، کراتین، صافی، اکستنشن، بافت، مراقبت کف سر

پوست و صورت

فیشال، پاک‌سازی، آبرسانی، مراقبت صورت، ابرو، مژه

زیبایی

میکاپ، شینیون، ابرو، مژه، ناخن، خدمات عروس

پس برای شروع لازم نیست سیستم جدیدی برای تعریف خدمات بسازیم.

بهتر است همین SERVICES تبدیل شود به منبع اصلی انتخاب خدمت در آینه زیبایی.

4. چیزی که برای «ابرو» لازم است

برای ابرو نباید فقط بنویسیم «انتخاب مدل».

ساختار درست:

خدمت: ابرو

→ توضیح خدمت

→ نمونه مدل‌ها

→ انتخاب سلیقه:

طبیعی

نچرال و مرتب

قوس‌دار

صاف

پهن

ظریف

پررنگ‌تر

بعد AI بر اساس:

عکس کاربر + خدمت + مدل انتخابی

تحلیل مخصوص ابرو تولید کند.

خروجی:

مدل انتخابی شما با فرم کلی صورت بررسی شد.

نقاط مناسب برای شروع، قوس و انتهای ابرو مشخص شد.

برای چهره شما این ویژگی‌ها مناسب‌تر هستند...

سپس مدل پیشنهادی و Preview نمایش داده شود.

این بخش باید Service-specific باشد، نه یک Prompt عمومی برای همه خدمات. اینجا هوش مصنوعی بالاخره باید بفهمد «ابرو» با «رنگ مو» یکی نیست، اتفاقاً بشر برای همین چیزها کامپیوتر ساخته.

5. ساختار معماری پیشنهادی



Giso Analysis
│
├── تحلیل مو / پوست فعلی
│
└── آینه زیبایی گیسو
    │
    ├── Service Registry
    │   ├── ابرو
    │   ├── مژه
    │   ├── مو
    │   ├── رنگ
    │   ├── میکاپ
    │   └── ...
    │
    ├── Service Guide
    ├── Style / Model Selection
    ├── Image Validation
    ├── AI Service Analysis
    ├── Preview Engine
    ├── Result / Before-After
    ├── Online Consultant
    │
    └── Service Marketplace
        │
        ├── مراکز ارائه‌دهنده خدمت
        ├── تعداد درخواست‌های تحلیل
        ├── معرفی مرکز
        ├── Instagram
        ├── رزرو
        └── ارسال Lead به مرکز

6. چه چیزهایی را از ساختار فعلی استفاده کنیم؟

بخش موجود

استفاده

analysis.py

هسته ورود و Analysis فعلی

ai_brain.py

AI Vision

analysis_report.py

ساخت گزارش

analysis_labels.py

نرمال‌سازی

beauty_centers/services.py

لیست خدمات و ارتباط مرکز/خدمت

beauty_centers/routes.py

لیست و صفحه مراکز

beauty_centers/reservations/

رزرو

beauty_center_conversations

گفتگوی کاربر/مرکز

recommendation_service.py

منطق پیشنهاد

Wallet

اعتبار و هزینه

7. چه چیزهایی نیاز به تغییر ساختاری دارد؟

مورد

وضعیت

اضافه‌شدن «آینه زیبایی گیسو» به Analysis

🟡 تغییر UI + Route

Service Registry مخصوص AI

🟡 نیاز

تعریف مدل‌ها/استایل‌های هر خدمت

🟡 نیاز

Prompt تخصصی هر خدمت

🟡 نیاز

اتصال Preview به Giso

🟡 نیاز

ذخیره نتیجه Preview

🟡 نیاز

اتصال نتیجه به مرکز

🟡 نیاز

شمارش تقاضای هر خدمت

🟡 نیاز

Lead تحلیل → مرکز

🟡 نیاز

لینک Instagram مرکز

🔴 فیلد جدید لازم

لینک Preview اختصاصی مرکز

🔴 نیاز

قیمت/اعتبار جداگانه برای هر خدمت

🔴 نیاز

حفظ پنل فعلی مرکز

🟢 بدون بازطراحی

حفظ رزرو فعلی

🟢 قابل استفاده

حفظ گفتگوی فعلی

🟢 قابل استفاده

حفظ Analysis مو/پوست

🟢 باید دست‌نخورده بماند

8. بخش مراکز زیبایی

ساختار فعلی همین حالا پایه خوبی دارد:

مرکز → خدمات → صفحه مرکز → گفتگو → رزرو

بنابراین فقط باید یک لایه جدید اضافه شود:



مرکز زیبایی
│
├── خدمات فعلی
├── قیمت/اطلاعات خدمت
├── رزرو
├── گفتگو
├── معرفی مرکز
├── Instagram
│
└── آینه زیبایی گیسو
    ├── Preview خدمت
    ├── تعداد تحلیل‌های مرتبط
    ├── درخواست‌های رزرو مرتبط
    └── دریافت Lead

در صفحه مرکز هم برای هر خدمت، یک گزینه:

«پیش‌نمایش این خدمت با آینه زیبایی گیسو»

قرار بگیرد.

9. پنل مدیر مرکز

طبق چیزی که گفتی، ساختار اصلی پنل نباید به‌هم بخورد.

فقط یک بخش به مرکز اضافه شود:

«تحلیل‌های آینه زیبایی گیسو»

مدیر مرکز ببیند
:
بخش کدم بررسی ایجنت قسما برای قبل شروع سرنایغ؟
پرامپی دادم براب ررسی 
```
# مأموریت: بررسی کامل ساختار «آنالیز هوشمند» Giso بر اساس Graphify و کد واقعی

## وضعیت پروژه

Repository:
https://github.com/uname1370-create/giso4

Branch:
`arena/01a0e0b8-giso4`

نقشه Graphify:
`graphify-out/`

مسیر اصلی مورد بررسی:
`giso/`

---

# هدف

فعلاً **هیچ کدی ننویس و هیچ تغییری در پروژه نده.**

فقط یک بررسی عمیق و فنی انجام بده تا مشخص شود قابلیت «آنالیز هوشمند» در Giso الان دقیقاً:

1. کجا تعریف شده
2. از چه فایل‌ها و ماژول‌هایی تشکیل شده
3. در پنل کاربر چگونه تعریف و نمایش داده شده
4. در پنل سوپرادمین چگونه تعریف و نمایش داده شده
5. چه مسیرها، routeها، serviceها، modelها و APIهایی دارد
6. چه فایل‌هایی ورودی آن هستند
7. چه خروجی‌ای تولید می‌کند
8. چه مدل‌ها و Providerهای هوش مصنوعی در آن دخیل هستند
9. چه Promptهایی استفاده می‌کند
10. چه DB / جدول / رکوردهایی با آن ارتباط دارند
11. وضعیت فعلی واقعی آن چیست
12. چه قسمت‌هایی کامل، ناقص، متصل، بلااستفاده یا مشکوک هستند.

---

# مرحله ۱: ابتدا Graphify را بخوان

قبل از بررسی کد، ابتدا این مسیر را کامل بررسی کن:

`graphify-out/`

به‌خصوص:

* `GRAPH_REPORT.md`
* `graph.json`
* `manifest.json`
* `.graphify_analysis.json`
* `.graphify_labels.json`

اگر فایل دیگری در `graphify-out/` وجود دارد که برای فهم ارتباطات لازم است، آن را هم بررسی کن.

هدف این مرحله این است که ابتدا از روی Graph بفهمی ساختار پروژه و ارتباطات آن چگونه دیده شده است.

**Graphify را فقط به عنوان نقشه راه استفاده کن.**

بعد از آن، برای تأیید نهایی حتماً به کد واقعی مراجعه کن.

---

# مرحله ۲: محدوده بررسی

بررسی اصلی باید فقط داخل:

`giso/`

انجام شود.

اما اگر یک بخش از آنالیز هوشمند به فایل خارج از `giso/` وابسته است، فقط همان dependency واقعی را دنبال کن و در گزارش ذکر کن.

به صورت خاص بررسی کن:

* `giso/analysis.py`
* `giso/analysis_report.py`
* `giso/analysis_labels.py`
* `giso/analysis_final_override.py`
* `giso/ai_brain.py`
* `giso/ai_runtime.py`
* `giso/ai_runtime_policy.py`
* `giso/ai_discovery.py`
* `giso/ai_models_registry.py`
* `giso/ai_health.py`
* `giso/recommendation_service.py`
* `giso/ai_widget_chat*`
* `giso/widget_service.py`
* `giso/consultant_*`
* `giso/prompts/`
* `giso/panel/`
* `giso/panel_user/`
* `giso/models.py`
* `giso/db_core.py`
* `giso/db_engine.py`
* `giso/app.py`
* `giso/base.py`
* `giso/bot.py`

و هر فایل دیگری که Graphify نشان می‌دهد مستقیماً یا غیرمستقیم به سیستم آنالیز هوشمند متصل است.

**فقط به این لیست محدود نشو.**
اگر Graphify یا import/call واقعی فایل دیگری را به سیستم Analysis متصل نشان داد، آن را نیز بررسی کن.

---

# مرحله ۳: سناریوی «آنالیز هوشمند» را از ابتدا تا انتها پیدا کن

مسیر واقعی اجرای آنالیز را استخراج کن.

مشخص کن:

### ورودی

کاربر از کجا وارد آنالیز می‌شود؟

مثلاً:

* route
* menu
* button
* پنل کاربر
* ربات
* API
* upload عکس
* انتخاب نوع تحلیل
* فرم

دقیقاً فایل و تابع را بنویس.

---

### پردازش

بعد از ورود کاربر چه اتفاقی می‌افتد؟

زنجیره واقعی را مشخص کن:

`Route → Handler → Service → Analysis → AI → Result`

اگر ساختار متفاوت است، همان ساختار واقعی را گزارش کن.

برای هر مرحله بنویس:

* فایل
* تابع
* ارتباط با فایل بعدی
* نوع ارتباط
* EXTRACTED یا INFERRED بودن رابطه در Graphify، اگر مشخص است.

---

### AI

دقیقاً مشخص کن:

* چه تابعی AI را صدا می‌زند
* `ai_brain.py` چه نقشی دارد
* `ai_runtime.py` چه نقشی دارد
* providerها چگونه انتخاب می‌شوند
* fallback چگونه کار می‌کند
* health check چگونه کار می‌کند
* مدل پیش‌فرض چیست
* مدل جایگزین چیست
* آیا انتخاب مدل توسط کاربر انجام می‌شود یا سیستم
* timeout / failover / policy چگونه تعریف شده
* Prompt از کجا خوانده می‌شود
* آیا Prompt واقعاً در runtime استفاده می‌شود یا فقط فایل موجود است.

---

# مرحله ۴: Promptهای آنالیز هوشمند

پوشه:

`giso/prompts/`

را کامل بررسی کن.

برای هر Prompt مرتبط با آنالیز هوشمند مشخص کن:

* نام فایل
* کاربرد
* چه تابعی آن را می‌خواند
* چه زمانی استفاده می‌شود
* ورودی‌هایی که به Prompt می‌دهد
* خروجی مورد انتظار
* آیا واقعاً در مسیر runtime استفاده می‌شود یا orphan است.

اگر Promptی وجود دارد ولی هیچ مسیر واقعی به آن نمی‌رسد، واضح بنویس:

`وجود دارد ولی در runtime اثبات نشد`

---

# مرحله ۵: پنل کاربر

این بخش بسیار مهم است.

داخل:

`giso/panel_user/`

بررسی کن که «آنالیز هوشمند» دقیقاً چگونه تعریف شده است.

مشخص کن:

### منوی پنل کاربر

* گزینه آنالیز هوشمند کجاست؟
* در کدام فایل تعریف شده؟
* عنوان واقعی گزینه چیست؟
* route آن چیست؟
* permission آن چیست؟
* module آن چیست؟
* template آن چیست؟
* JavaScript مرتبط چیست؟
* API مرتبط چیست؟

### مسیر کاربر

از لحظه‌ای که کاربر روی گزینه آنالیز هوشمند کلیک می‌کند تا دریافت نتیجه، مسیر کامل را استخراج کن.

مثلاً:

`Menu → Route → Module → Service → AI → Report`

اگر مسیر متفاوت است، همان را گزارش کن.

---

# مرحله ۶: پنل سوپرادمین

داخل:

`giso/panel/`

به صورت جداگانه بررسی کن.

مشخص کن:

### گزینه‌های مربوط به AI / Analysis

* گزینه آنالیز هوشمند وجود دارد؟
* کجا تعریف شده؟
* آیا سوپرادمین می‌تواند تنظیمات AI را مدیریت کند؟
* آیا Providerها قابل مدیریت هستند؟
* آیا Model قابل مدیریت است؟
* آیا Prompt قابل مدیریت است؟
* آیا Health / status قابل مشاهده است؟
* آیا فعال/غیرفعال کردن AI وجود دارد؟
* آیا تنظیمات مربوط به Analysis وجود دارد؟

برای هر گزینه دقیقاً بنویس:

`فایل → تابع → route → permission → template`

---

# مرحله ۷: ارتباط پنل کاربر و سوپرادمین

بررسی کن آیا این دو واقعاً به یک سیستم واحد متصل هستند یا خیر.

مشخص کن:

* آیا پنل کاربر از همان Analysis engine استفاده می‌کند؟
* آیا پنل سوپرادمین همان Provider registry را مدیریت می‌کند؟
* آیا تنظیمات سوپرادمین روی اجرای آنالیز کاربر اثر دارد؟
* آیا DB مشترک است؟
* آیا configuration مشترک است؟
* آیا AI runtime مشترک است؟
* آیا مسیرهای جدا ولی backend مشترک هستند؟

---

# مرحله ۸: DB و ذخیره‌سازی

هر چیزی که به Analysis مربوط است پیدا کن:

* جدول‌ها
* مدل‌ها
* migration
* config
* history
* report
* result
* user analysis
* provider config
* AI settings

مشخص کن:

`فایل → تابع → جدول`

و اگر امکانش هست مشخص کن داده دقیقاً چه زمانی نوشته و چه زمانی خوانده می‌شود.

---

# مرحله ۹: Graphify در برابر کد واقعی

برای بخش آنالیز هوشمند یک تطبیق دقیق انجام بده.

یک جدول بساز:

| بخش         | Graphify نشان می‌دهد | کد واقعی | نتیجه        |
| ----------- | -------------------- | -------- | ------------ |
| Analysis    | ...                  | ...      | تطابق/اختلاف |
| AI Brain    | ...                  | ...      | ...          |
| AI Runtime  | ...                  | ...      | ...          |
| Prompt      | ...                  | ...      | ...          |
| Panel User  | ...                  | ...      | ...          |
| Super Admin | ...                  | ...      | ...          |
| Provider    | ...                  | ...      | ...          |
| DB          | ...                  | ...      | ...          |
| Template    | ...                  | ...      | ...          |
| JS/API      | ...                  | ...      | ...          |

اگر Graphify چیزی را نشان نمی‌دهد ولی در کد وجود دارد، علت را مشخص کن.

مثلاً:

`Graphify code-only است و template/prompt را node نکرده`

اگر Graphify رابطه‌ای را `INFERRED` نشان می‌دهد، آن را به عنوان واقعیت قطعی قبول نکن و از روی کد تأیید کن.

---

# مرحله ۱۰: وضعیت فعلی واقعی

در پایان فقط بر اساس کد واقعی اعلام کن:

## وضعیت فعلی آنالیز هوشمند

### موجود و فعال

مواردی که واقعاً مسیر اجرایی دارند.

### موجود ولی ناقص

مواردی که بخشی از مسیر وجود دارد ولی کامل نیست.

### تعریف شده ولی استفاده نمی‌شود

کد / Prompt / route / serviceهایی که وجود دارند ولی runtime usage آنها اثبات نشد.

### مشکوک

رابطه‌هایی که فقط Graphify به صورت INFERRED نشان داده و کد تأیید قطعی نمی‌دهد.

### قطع شده / بلااستفاده

اگر dependency یا مسیر مرده پیدا شد.

### تکراری

اگر چند implementation برای یک کار وجود دارد.

---

# مرحله ۱۱: هیچ تغییری نده

این مأموریت فقط Audit است.

ممنوع:

* تغییر کد
* حذف فایل
* جابه‌جایی فایل
* rename
* refactor
* تغییر route
* تغییر template
* تغییر Prompt
* تغییر DB
* تغییر Graph
* rebuild Graph
* commit
* push
* branch جدید

هیچ چیزی را اصلاح نکن.

حتی اگر باگ واضح پیدا کردی فقط گزارش کن.

---

# مرحله ۱۲: گزارش نهایی

گزارش نهایی باید شامل این بخش‌ها باشد:

## 1. خلاصه اجرایی

در چند پاراگراف بگو سیستم آنالیز هوشمند الان واقعاً چگونه کار می‌کند.

## 2. مسیر کامل اجرای آنالیز

از ورودی کاربر تا نتیجه نهایی.

## 3. فایل‌ها و کدهای اصلی

جدول:

`File | Function | Role | Relation`

## 4. پنل کاربر

گزینه، route، permission، module، template، JS و مسیر اجرا.

## 5. پنل سوپرادمین

گزینه‌های AI/Analysis، route، permission، module، template و قابلیت مدیریت.

## 6. AI Engine

`analysis → ai_brain → ai_runtime → provider → model → result`

با فایل و تابع واقعی.

## 7. Promptها

Promptهای واقعی و محل استفاده آنها.

## 8. DB

جدول‌ها و محل خواندن/نوشتن.

## 9. Graphify vs Code

اختلاف‌ها و تطابق‌ها.

## 10. وضعیت فعلی

* فعال
* ناقص
* بدون استفاده
* مشکوک
* تکراری
* قطع‌شده

## 11. مشکلات واقعی

فقط مشکلاتی که از کد قابل اثبات هستند.

## 12. نتیجه نهایی

یک جمع‌بندی روشن از اینکه:

**«الان آنالیز هوشمند Giso دقیقاً در چه وضعیتی قرار دارد و چه اجزایی واقعاً به هم متصل هستند.»**

---

## قانون مهم گزارش

حدس نزن.

اگر چیزی را از Graphify گرفتی ولی کد تأیید نکرد:

`Graph evidence only`

اگر کد تأیید کرد:

`Code verified`

اگر فقط از روی نام فایل یا import حدس زده شد:

`Unverified`

هیچ رابطه‌ای را صرفاً به خاطر وجود در Graphify به عنوان رابطه واقعی اعلام نکن.

هدف این مرحله فقط شناخت دقیق وضعیت موجود است، نه اصلاح پروژه.
```
گزرشا ایجنتشروع می‌کنم با بررسی فقط‌خواندنی وضعیت repo، سپس Graphify و بعد کد واقعی. هیچ فایل را تغییر نمی‌دهم و Graph را rebuild نمی‌کنم.

وضعیت فعلی repository نشان می‌دهد قبل از این audit، فقط فایل‌های `graphify-out/` از مرحله قبل modified هستند. از اینجا به بعد فقط read-only بررسی می‌کنم. حالا داده‌های Graph مرتبط با Analysis/AI را استخراج می‌کنم.

Graphify مسیرهای اصلی Analysis/AI را نشان داد، اما چون Graph فعلی code-only است، prompt/template nodeها در Graph نیستند. حالا از روی کد واقعی مسیر runtime را تأیید می‌کنم.

اکنون نقش AI providerها، runtime/failover، health و registry را از روی کد بررسی می‌کنم.

خروجی قبلی به‌خاطر طول فایل‌ها خلاصه شد؛ بخش‌های دقیق تنظیمات runtime و ترتیب fallback را جداگانه می‌خوانم.

حالا مسیر پنل کاربر و پنل سوپرادمین/ادمین مربوط به Analysis و AI را از کد می‌خوانم.

برای پنل AI خروجی بلند بود؛ بخش context و handlerهای کلیدی را جدا می‌خوانم.

قالب‌های پنل مسیر متفاوتی دارند؛ مکان‌شان را پیدا می‌کنم و سپس همان‌ها را می‌خوانم.

برای پایگاه داده و مدل‌ها، ستون‌های واقعی `Analysis` و جدول‌های AI/مشاوره را بررسی می‌کنم.

اکنون فایل‌های کمکی گزارش/برچسب/override و توصیه‌ها را بررسی می‌کنم تا مشخص شود واقعاً در مسیر اجرا هستند یا فقط پشتیبان/کمکی‌اند.

یک نکته مهم دیدم: override فقط تابع global را patch می‌کند؛ باید ببینم routeهای final واقعاً در زمان اجرا به همین global اشاره می‌کنند یا reference قبلی بسته شده است.

بعد promptها را کامل فهرست می‌کنم و هر فایل را با ارجاع کد تطبیق می‌دهم.

برای prompt ربات (`consultant_bot.txt`) مصرف واقعی را هم جداگانه از فایل ربات/ادمین بررسی می‌کنم.

اکنون مسیر «مشاور هوشمند» داخل آنالیز و درخواست محصول/مشاوره را از `analysis.py` دقیق می‌خوانم.

حالا مسیرهای فرعی مهم: فراخوانی متن AI، اعتبارسنجی تصویر، ذخیره آپلود و rate-limit را دقیق می‌خوانم.

برای تکمیل تصویر، ثابت‌های اولویت provider و importهای بالای `analysis.py` را هم جدا چک می‌کنم.

برای اشتراک backend بین پنل کاربر/ویجت/ربات و نقش‌ها، helperهای نقش و لاگ ویجت در `app.py` را هم بررسی می‌کنم.

در این repo فایل مستقل `ai_widget.py` نیست؛ فایل‌های مرتبط با ویجت را با find مشخص می‌کنم.

فایل‌های registry/discovery/health را هم برای وضعیت «کشف مدل‌ها» و سلامت مشترک تکمیل می‌کنم.

خروجی health از وسط شروع شد؛ DDL جدول سلامت را جدا می‌خوانم.

برای DB AI، جدول providerها و seed/defaultها را از `ai_brain.py` دقیق‌تر استخراج می‌کنم.

حالا recommendation/card modules که به آنالیز و پنل کاربر وصل‌اند را بررسی می‌کنم.

برای ورودی‌های UI/فرم‌ها/JS، قالب‌های آنالیز و فایل‌های JS مرتبط را اسکن می‌کنم.

قالب‌ها نشان دادند routeهای درخواست محصول/مشاوره ممکن است دکمه/فرم فعلی نداشته باشند؛ برای اطمینان search دقیق‌تر انجام می‌دهم.

برای سوپرادمین، علاوه بر پنل ماژولار، مسیرهای legacy داخل `app.py` هم وجود دارد؛ بررسی می‌کنم آیا هنوز فعال‌اند یا صرفاً پشتیبان.

برای «دستیار هوشمند مدیریتی» سوپرادمین نیز مسیر runtime/action/pending را بررسی می‌کنم.

نکته‌های آخر: برای مقایسه Graphify با code، روابط graph را برای فایل‌های کلیدی و پوشش prompt/template استخراج می‌کنم.

گزارش متنی Graphify را هم برای خلاصهٔ محدودیت‌ها/آمار مرور می‌کنم.

در پایان فقط وضعیت Git را می‌گیرم تا مطمئن شوم در این audit تغییری ایجاد نکرده‌ام.

یک نکته کوچک درباره دیده‌شدن لینک دستیار هوشمند در سایدبار پنل کاربر را هم از layout چک می‌کنم.

برای دقت، ساخت منوی پنل کاربر را هم چک می‌کنم چون `ai_assistant` در گروه‌ها هست اما در `USER_MODULES` نیست.

یک ریزه‌کاری promptهای final را هم بررسی می‌کنم: آیا placeholderها واقعاً replace می‌شوند یا فقط context به انتها اضافه می‌شود.

برای کامل‌کردن مسیر کاربر مهمان → ثبت‌نام → ادامه final، تابع `analysis_register` را هم می‌خوانم.

گزارش audit فقط‌خواندنی انجام شد. در این audit هیچ فایل/کدی را تغییر ندادم؛ `git status` هنوز فقط همان سه فایل Graphify قبلی را modified نشان می‌دهد: `graphify-out/.graphify_analysis.json`, `GRAPH_REPORT.md`, `graph.json`.

# 1) خلاصه اجرایی

**Code verified:** «آنالیز هوشمند» در گیسو یک سیستم واحد ساده نیست؛ چند لایه‌ی متصل دارد:

1. **هسته آنالیز تصویر و گزارش مو/پوست:** عمدتاً در `giso/analysis.py`
2. **override فعالِ final analysis:** در `giso/analysis_final_override.py` که در `giso/app.py` و `giso/wsgi.py` نصب می‌شود و در runtime تابع `_final_analysis` را patch می‌کند.
3. **AI provider/runtime:**
   - `giso/ai_brain.py` برای provider table، API call، vision/text fast
   - `giso/ai_runtime.py` برای چت مدیریت‌شده، ویجت، ربات، سوپرادمین، role policy، usage/pending/actions
   - `giso/ai_health.py`, `ai_models_registry.py`, `ai_discovery.py`, `ai_runtime_policy.py`, `ai_config.py`
4. **نمای پنل کاربر:** `giso/panel_user/` مخصوص تاریخچه آنالیز، آرشیو، پیشنهاد محصولات، مشاور در تب آنالیز، و صفحه دستیار.
5. **نمای سوپرادمین:** `giso/panel/` مخصوص مدیریت آنالیزها، AI providers، failover، widget، role policies، credits، pending actions، super assistant.
6. **ربات:** `giso/bot.py` و `giso/bot_admin_utils.py` بیشتر پیگیری/نمایش/چت مشاور را به سایت و runtime وصل می‌کنند؛ شروع تحلیل جدید عمدتاً سایت است.
7. **DB:** جدول اصلی `analyses` است، ولی سیستم به `giso_ai_*`, `analysis_rate_limits`, `consultant_requests`, `consultant_messages`, `product_requests`, `products`, `giso_widget_chats`, `giso_widget_feedback`, wallet/credits و تنظیمات `giso_config` هم وصل است.

**نتیجه وضعیت کلی:** سیستم از نظر مسیر اصلی «آپلود → تحلیل اولیه → سوالات → گزارش نهایی → گزارش/برنامه/راهکار/مشاور» وصل است، اما چند مشکل واقعی و مهم دارد:

- **مشکل جدی Code verified:** `analysis_final_override.py` نسخه‌ی active runtime است و نسبت به `analysis.py` عقب‌تر/متفاوت است؛ در override کسر هزینه‌ی گزارش کامل و mission completion که در `analysis.py` وجود دارد، اجرا نمی‌شود.
- **مشکل Code verified:** چند تصویر upload می‌شود و در DB ذخیره می‌شود، ولی `call_vision_with_fallback` فقط `image_paths[0]` را به AI می‌فرستد.
- **مشکل Code verified:** `/analysis/validate-image` وجود دارد و JS آن را صدا می‌زند، اما `_run_initial()` سمت سرور خودش اعتبارسنجی تصویر را enforce نمی‌کند.
- **مشکل Code verified:** تنظیم «AI فعال / failover» در پنل AI عمدتاً برای `ai_runtime` چت/ویجت/ربات است؛ مسیر core vision analysis و `ask_ai_fast` الزاماً از همان active provider/failover استفاده نمی‌کند. این از نظر UI می‌تواند گمراه‌کننده باشد.
- **Code verified:** routeهای `request_product` و `request_consultant` در `analysis.py` ثبت شده‌اند، ولی در template/static فعلی ارجاع فعال پیدا نشد؛ در عمل بخش محصول/مشاوره‌ی admin ممکن است ورودی UI فعلی نداشته باشد، جز مسیرهای قدیمی/مستقیم.

---

# 2) مسیر اجرای کامل کاربر: User entry → Result

## 2.1 شروع از سایت

**Code verified**

- صفحه انتخاب:
  - `GET /analysis` → `analysis()` در `giso/analysis.py`
  - template: `analysis_home.html`
- شروع مو:
  - `GET /analysis/hair` → `analysis_hair()`
  - template: `analysis_hair.html`
- شروع پوست:
  - `GET /analysis/skin` → `analysis_skin()`
  - template: `analysis_skin.html`

در `giso/templates/base.html` و `index.html` لینک‌های عمومی به `url_for('analysis')` وجود دارد. صفحه خانه هم چند CTA به آنالیز دارد.

## 2.2 Upload و تحلیل اولیه

**Code verified**

فرم‌های اصلی:

- `analysis_hair.html`
  - `POST {{ url_for('initial_analysis_hair') }}`
  - input file با `name="images"`
- `analysis_skin.html`
  - `POST {{ url_for('initial_analysis_skin') }}`
  - input file با `name="images"`

routeها:

- `POST /analysis/hair/initial` → `initial_analysis_hair()` → `_run_initial("hair")`
- `POST /analysis/skin/initial` → `initial_analysis_skin()` → `_run_initial("skin")`

داخل `_run_initial`:

1. `_save_uploaded_images(analysis_type)`
   - مسیر temp: `Config.GISO_DIR/data/uploads/analysis/temp`
   - فرمت مجاز: jpg/jpeg/png/webp
   - resize با Pillow تا 1024px، quality 85
2. prompt:
   - مو: `hair_initial_analysis.txt`
   - پوست: `skin_initial_analysis.txt`
3. AI:
   - `call_vision_with_fallback(saved, prompt)`
4. ساخت سوالات:
   - `_build_questions(analysis_type, data.get("detected_issues") or {})`
5. ساخت رکورد DB:
   - مدل: `Analysis`
   - جدول: `analyses`
   - ستون‌های پرشونده در این مرحله:
     - `user_id` اگر login باشد
     - `phone` اگر login باشد
     - `type`
     - `photo_path="analysis/"`
     - `image_paths=json.dumps(saved)`
     - `ai_report_json=json.dumps(data)`
6. `session["current_analysis_id"] = ana.id`
7. render همان template با `stage=3`, `initial`, `questions`

## 2.3 اعتبارسنجی تصویر

**Code verified**

route:

- `POST /analysis/validate-image` → `validate_image_route()`

promptها:

- `validate_hair.txt`
- `validate_skin.txt`

JS در `analysis_hair.html` و `analysis_skin.html`:

- `fetch('/analysis/validate-image', ...)`

اما:

**مشکل Code verified:** در `_run_initial()` هیچ call به `validate_uploaded_image()` وجود ندارد. یعنی اعتبارسنجی AI در عمل به مسیر JS/UX وابسته است و اگر کاربر/کلاینت آن را دور بزند، backend اولیه مستقیماً تحلیل را اجرا می‌کند.

## 2.4 سوالات تکمیلی و گزارش نهایی

**Code verified**

فرم سوالات:

- `analysis_hair.html`: `POST {{ url_for('final_analysis_hair') }}`
- `analysis_skin.html`: `POST {{ url_for('final_analysis_skin') }}`
- هر دو hidden input دارند:
  - `analysis_id = session.get('current_analysis_id')`

routeها:

- `POST /analysis/hair/final` → `final_analysis_hair()` → `_final_analysis("hair")`
- `POST /analysis/skin/final` → `final_analysis_skin()` → `_final_analysis("skin")`
- generic:
  - `/analysis/final` → `_final_analysis_router()`

اما در runtime:

**Code verified:** `giso/app.py` و `giso/wsgi.py` هر دو `analysis_final_override.install()` را صدا می‌زنند. این تابع:

```python
m._final_analysis = _final_analysis_fixed
```

پس مسیر active نهایی در runtime عملاً `giso/analysis_final_override.py::_final_analysis_fixed` است، نه بدنه‌ی اصلی `_final_analysis` داخل `analysis.py`.

مسیر override:

1. اگر POST باشد:
   - `session["pending_analysis_answers"] = request.form.to_dict()`
   - اگر `analysis_id` معتبر باشد:
     - `session["current_analysis_id"] = int(form_aid)`
2. اگر کاربر login نیست:
   - redirect به `analysis_register`
3. بعد از register/login:
   - redirect به `analysis_final`
   - `_final_analysis_router()` نوع تحلیل را از `Analysis` پیدا می‌کند.
4. پیدا کردن رکورد `Analysis` از session یا آخرین رکورد همان نوع.
5. اگر گزارش نهایی قبلاً ساخته شده باشد:
   - markers: `immediate_actions`, `condition`, `main_problems`
   - redirect به report
6. prompt:
   - مو: `hair_final_analysis.txt`
   - پوست: `skin_final_analysis.txt`
7. context شامل:
   - `initial_analysis`
   - `user_answers`
   - `user_name`
   - `user_city`
8. AI:
   - `call_vision_with_fallback(images, full_prompt, max_tokens=2000)`
9. validate structure:
   - `_validate_structured_output`
   - fallback: `_ensure_structured_fallback`
10. update DB:
   - `questions_answers`
   - `phone`
   - `user_id`
   - `photo_path`
   - `ai_report_json`
11. `_record_rate_limit`
12. cleanup temp images
13. redirect:
   - `/analysis/hair/report`
   - `/analysis/skin/report`

## 2.5 نمایش گزارش

**Code verified**

- `GET /analysis/hair/report?id=...` → `analysis_report_hair()` → `_analysis_report("hair")`
- `GET /analysis/skin/report?id=...` → `analysis_report_skin()` → `_analysis_report("skin")`

در `_analysis_report`:

- مالکیت با `_get_current_analysis_for_user(id)` یا owner conditions بررسی می‌شود.
- JSON از `ai_report_json` خوانده می‌شود.
- `_normalize_report_data` از `analysis_report.py`
- build helperها از `analysis_report.py`:
  - `_build_metric_cards`
  - `_build_strength_items`
  - `_build_concern_items`
  - `_build_routine_cards`
  - `_build_radar_points`
- template:
  - `analysis_report_hair.html`
  - `analysis_report_skin.html`

## 2.6 برنامه اختصاصی

**Code verified**

route:

- `GET /analysis/plan?id=...` → `analysis_plan()`

منبع:

- آخرین `Analysis` متعلق به کاربر، یا id مشخص.
- اگر `plan_json` در DB باشد همان را استفاده می‌کند.
- اگر نباشد:
  - prompt: `plan_generator.txt`
  - محصولات از `Product.query.all()`
  - AI متنی: `_call_text_ai(full_prompt, max_tokens=2500)`
  - fallback deterministic اگر AI fail شود
  - ذخیره:
    - `analysis.plan_json`
    - `analysis.duration_weeks`

همچنین:

- `report_type_viewed` را با `full`/`both` به‌روز می‌کند.
- `consultant_cards = build_cards_for_user(phone)` را برای template می‌گیرد.
- template: `analysis_plan.html`
- checklist APIs:
  - `POST /analysis/checklist/save/<analysis_id>`
  - `GET /analysis/checklist/progress/<analysis_id>`

## 2.7 راهکار سریع

**Code verified**

route:

- `GET /analysis/quick-solution?id=...` → `analysis_quick_solution()`

منبع:

- `analysis.ai_report_json`
- prompt: `quick_solution.txt`
- AI متنی: `_call_text_ai(prompt, max_tokens=1500)`
- fallback deterministic: `_default_quick_solution`
- ذخیره:
  - `analysis.quick_solution_json`
  - `analysis.updated_at`
- session cache:
  - `quick_solution_<analysis.id>`
- template:
  - `analysis_quick_solution.html`

## 2.8 مشاور صادقی داخل مسیر آنالیز

**Code verified**

UI:

- `consultant_component.html`
- `static/js/consultant.js`

APIها:

- `POST /api/consultant-chat/message`
- `GET /api/consultant-chat/history/<analysis_id>`
- `POST /api/consultant-chat/rate`

در `consultant_chat_message()`:

1. مالکیت analysis با `_get_current_analysis_for_user`
2. خواندن:
   - `analysis.ai_report_json`
   - `analysis.plan_json`
   - `analysis.consultant_chat_history`
   - `analysis.consultant_key_notes`
3. role policy:
   - `get_context_scope("user", section="consultant_chat")` از `ai_runtime`
4. اگر کاربر intent محصول داشته باشد:
   - محصولات in-stock از `Product`
5. beauty centers:
   - `recommended_centers(...)`
   - prompt extension از `giso.beauty_centers.ai_prompt.build_beauty_centers_prompt`
6. prompt:
   - `consultant_sadeghi.txt`
7. AI:
   - `chat_with_managed_ai(... role="user", section="consultant_chat")`
8. ذخیره:
   - `analysis.consultant_chat_history`
   - هر 5 پیام: خلاصه با `consultant_summarizer.txt` در `consultant_key_notes`
9. خروجی JSON:
   - `response`
   - `message_count`
   - `product_cards`
   - `nutrition_items`

---

# 3) جدول فایل‌های اصلی

| فایل | نقش واقعی | وضعیت |
|---|---|---|
| `giso/analysis.py` | هسته routeها، upload، vision fallback، initial/final/report/plan/quick/consultant APIs | **Code verified** |
| `giso/analysis_final_override.py` | patch فعال برای `_final_analysis` بعد از route registration | **Code verified؛ بسیار مهم** |
| `giso/analysis_report.py` | helperهای pure برای normalize و ساخت کارت/رادار/روتین گزارش | **Code verified** |
| `giso/analysis_labels.py` | label فارسی metricها، مصرف در پنل کاربر | **Code verified** |
| `giso/ai_brain.py` | جدول providerها، sync env، seed registry، `ask_ai`, `ask_ai_vision`, `ask_ai_fast`, refresh models | **Code verified** |
| `giso/ai_runtime.py` | runtime چت/ویجت/ربات/سوپرادمین، settings، policies، usage، pending actions | **Code verified** |
| `giso/ai_runtime_policy.py` | constants و policyهای role/default provider order/messages | **Code verified** |
| `giso/ai_config.py` | timeout/budget/cooldown/feature flag برای Vision/Chat/Fast | **Code verified** |
| `giso/ai_health.py` | health/cooldown مشترک provider/model | **Code verified** |
| `giso/ai_models_registry.py` | registry providerها و مدل‌های text/vision | **Code verified** |
| `giso/ai_discovery.py` | کشف `/models` و smart filter مدل‌ها | **Code verified** |
| `giso/recommendation_service.py` | پیشنهاد محصول و nutrition از DB | **Code verified** |
| `giso/consultant_cards.py` | تبدیل recommendation به کارت محصول | **Code verified** |
| `giso/consultant_chat_service.py` | مدیریت thread پیام مشاوره‌ی human/admin، archive view کاربر | **Code verified** |
| `giso/consultant_context.py` | context گزارش‌محور برای مشاور ربات | **Code verified** |
| `giso/widget_service.py` | نقش ویجت، history، brief کاربر، گزارش staff | **Code verified** |
| `giso/app.py` | ثبت routeها، API ویجت، legacy admin routes، نصب override | **Code verified** |
| `giso/models.py` | مدل `Analysis` و migration جدول‌های مرتبط | **Code verified** |
| `giso/base.py` | DB init، rate-limit config، init AI tables/seed providers | **Code verified** |
| `giso/db_core.py` | اتصال مرکزی SQLite/Postgres adapter | **Code verified** |
| `giso/db_engine.py` | مرز اختیاری Postgres با env | **Code verified** |
| `giso/panel/routes.py` | routeهای پنل admin/superadmin | **Code verified** |
| `giso/panel/modules/ai.py` | context و handlerهای مدیریت AI | **Code verified** |
| `giso/panel/modules/analyses.py` | context/handlerهای مدیریت آنالیز/مشاوره/product/rate-limit | **Code verified** |
| `giso/panel/modules/super_assistant.py` | دستیار مدیریتی سوپرادمین با pending/OTP/undo | **Code verified** |
| `giso/panel_user/routes.py` | routeهای داشبورد کاربر | **Code verified** |
| `giso/panel_user/modules/analyses.py` | context تاریخچه آنالیز کاربر و recommendation | **Code verified** |
| `giso/bot.py` | منوی ربات برای پیگیری آنالیز، admin analysis، لینک به سایت | **Code verified** |
| `giso/bot_admin_utils.py` | prompt `consultant_bot.txt` و chat managed AI برای ربات | **Code verified** |

---

# 4) پنل کاربر

## 4.1 نمایش و منو

**Code verified**

- Blueprint: `giso/panel_user`
- route اصلی تحلیل‌ها:
  - `/dashboard/analyses` → `panel_user.routes.analyses()`
- module:
  - `giso/panel_user/modules/analyses.py`
- template:
  - `giso/panel_user/templates/user_modules/analyses.html`

در `permissions.py`:

- `USER_MODULES` شامل:
  - `("analyses", "آنالیزها و برنامه من", "🔬")`
- `USER_MODULE_GROUPS` در گروه خدمات:
  - `analyses`
- `ai_assistant` هم در گروه پشتیبانی هست.
- `ai_assistant` در `USER_MODULES` نیست، اما `_menu_for_current_user()` از `USER_MODULE_GROUPS` می‌سازد؛ بنابراین طبق code، در منوی گروه‌بندی‌شده می‌تواند دیده شود.

## 4.2 داده‌های پنل کاربر

`panel_user/modules/analyses.py::context()`:

- owner filter:
  - `Analysis.user_id == current_user.id`
  - یا `Analysis.phone == normalize_phone(current_user.phone)`
- جدا می‌کند:
  - `hair_analyses`
  - `skin_analyses`
  - `archived_analyses`
  - `latest_hair`
  - `latest_skin`
- summary:
  - `main_problems`
  - `metrics`
  - `plan_json`
  - `quick_solution_json`
- recommendation:
  - `get_recommendation_for_user(current_user.phone, max_items=6)`

## 4.3 عملیات کاربر

**Code verified**

- بایگانی:
  - `POST /dashboard/analyses/<analysis_id>/archive`
  - `archived_at = now`
- بازیابی:
  - `POST /dashboard/analyses/<analysis_id>/restore`
  - `archived_at = ""`
- مشاهده report:
  - `/analysis/{{ type }}/report?id={{ id }}`
- مشاهده plan:
  - `/analysis/plan?id={{ id }}`
- مشاهده quick:
  - `/analysis/quick-solution?id={{ id }}`
- تب consultant:
  - include `consultant_component.html`
  - load `static/js/consultant.js`
  - `initConsultant(analysis.id)`

## 4.4 دستیار هوشمند پنل کاربر

**Code verified**

- route:
  - `/dashboard/assistant`
- template:
  - `user_modules/ai_assistant.html`
- JS:
  - `panel_user/static/js/ai_assistant.js`
- backend مشترک:
  - `GET /api/ai-widget/init`
  - `POST /api/ai-widget/chat`

این صفحه خودش backend جدا ندارد؛ همان widget backend را استفاده می‌کند.

---

# 5) سوپرادمین / پنل مدیریت

## 5.1 مدیریت آنالیزها

**Code verified**

route جدید:

- `/panel/analyses` با `@require_super`
- module:
  - `panel/modules/analyses.py`
- template:
  - `panel/templates/modules/analyses.html`

تب‌ها:

- آنالیزها
- درخواست مشاوره
- محصولات درخواستی
- خلاصه گفتگوهای مشاور
- محدودیت زمانی

داده‌ها:

- `analyses`
- `consultant_requests`
- `consultant_messages`
- `product_requests`
- `reviews`
- `analysis_rate_limits` و config از `giso_config`

handlerها:

- reply/status مشاوره:
  - `/panel/analyses/consultant/<id>/reply`
  - `/panel/analyses/consultant/<id>/status`
- status product request:
  - `/panel/analyses/product/<id>/status`

## 5.2 مدیریت AI

**Code verified**

route:

- `/panel/ai` با `@require_super`

module:

- `panel/modules/ai.py`

امکانات:

- provider add/update/delete/toggle/proxy/test
- refresh models برای یک provider
- refresh all models با `ai_discovery.refresh_all_models_async`
- bulk import models JSON
- chat test
- active provider
- failover chain
- role policy
- capabilities text
- widget settings
- AI credits
- pending actions
- action logs
- rollback logs
- provider status report

routeهای POST:

- `/panel/ai/config`
- `/panel/ai/provider/add`
- `/panel/ai/provider/<name>/toggle`
- `/panel/ai/provider/<name>/proxy`
- `/panel/ai/provider/<name>/update`
- `/panel/ai/provider/<name>/delete`
- `/panel/ai/provider/<name>/test`
- `/panel/ai/test-all`
- `/panel/ai/chat-test`
- `/panel/ai/provider/<name>/refresh-models`
- `/panel/ai/refresh-all-models`
- `/panel/ai/bulk-import-json`
- `/panel/ai/pending/<id>/execute`
- `/panel/ai/pending/<id>/cancel`
- `/panel/ai/log/<id>/rollback`

## 5.3 دستیار مدیریتی سوپرادمین

**Code verified**

routeها:

- `/panel/super-assistant`
- `/panel/super-assistant/chat`
- `/panel/super-assistant/code-send`
- `/panel/super-assistant/confirm`
- `/panel/super-assistant/cancel`
- `/panel/super-assistant/undo`
- `/panel/super-assistant/clear`
- `/panel/super-assistant/health`
- `/panel/super-assistant/insight-status`

module:

- `panel/modules/super_assistant.py`

ویژگی‌ها:

- فقط role `super`
- نیازمند step-up verified session
- history در `giso_panel_ai_chats`
- گزارش‌های deterministic از `ai_runtime.process_superadmin_request`
- اگر اقدام اجرایی باشد:
  - pending action ساخته می‌شود.
  - کد ۶ رقمی به ربات بله ارسال می‌شود.
  - بعد از confirm، `execute_pending_action`
  - undo با `rollback_action_log`

اقدامات پشتیبانی‌شده در `ai_runtime.SUPPORTED_SUPER_ACTIONS`:

- reportها:
  - dashboard, orders, users, tickets, consultants, hair orders, analyses, user summary, AI status, SEO, inspector reports
- actionها:
  - update order status
  - update ticket status
  - update consultant status
  - update hair order status
  - update product price
  - update product stock
  - delete product
  - delete user data
  - set chat enabled
  - set display name
  - set active provider

## 5.4 legacy admin routes

**Code verified**

در `app.py` هنوز routeهای legacy وجود دارند:

- `/admin/analyses` با `@require_super`
- `/admin/analyses/<id>` با `@require_super`
- `/admin/product-requests` با `@require_super`
- `/admin/consultants` بدون `@require_super` ولی با `_check_giso_admin_access`
- `/admin/consultants/<id>` بدون `@require_super` ولی با `_check_giso_admin_access`
- `/admin` خودش redirect می‌کند به پنل جدید.

**نکته وضعیت:** پنل جدید analysis super-only است، اما legacy consultants routeها super decorator ندارند و فقط admin access check دارند. این یک تفاوت دسترسی واقعی است.

---

# 6) موتور AI و providerها

## 6.1 provider registry

**Code verified**

`ai_models_registry.py` هشت provider دارد:

1. `groq`
2. `openrouter`
3. `mistral`
4. `sambanova`
5. `cloudflare`
6. `gemini`
7. `gapgpt`
8. `avalai`

ویژگی‌ها:

- `sambanova`: text only
- بقیه عمدتاً vision/text دارند، طبق registry.
- `gapgpt` و `avalai` ایرانی/پولی محسوب شده‌اند.
- seed خودکار در `ai_brain.seed_registry_providers()` فقط:
  - `groq`, `openrouter`, `mistral`, `sambanova`, `cloudflare`
- retired:
  - `huggingface`, `cerebras`, `llm7` → enabled=0

## 6.2 جدول providerها

**Code verified**

در `ai_brain.py`:

- `giso_ai_providers`
  - `name`
  - `kind`
  - `enabled`
  - `api_key`
  - `base_url`
  - `api_root`
  - `timeout`
  - `headers_json`
  - `fallback_json`
  - `models_json`
  - `selected_model`
  - `is_iranian`
  - `use_proxy`
  - `last_status`
  - `last_error`
  - `last_checked_at`
  - افزوده‌ها:
    - `proxy_url`
    - `proxy_type`
    - `vision_models_json`
    - `text_models_json`
    - `models_last_updated`
    - `models_source`
    - `discovery_report`

## 6.3 مسیر Vision analysis

**Code verified**

در `analysis.py`:

- اولویت vision:
  - `["groq", "openrouter", "cloudflare", "mistral", "gemini", "avalai", "gapgpt"]`
- انتخاب مدل:
  - `selected_model`
  - `vision_models_json`
  - `fallback_json`
  - `models_json`
  - registry `get_vision_models`
- فیلتر:
  - `enabled`
  - `last_status` اگر پر باشد باید `ok/success` باشد.
- health cooldown:
  - `ai_health.is_in_cooldown(provider, model)`
- budget:
  - `VISION_TOTAL_TIMEOUT_SECONDS = 45`
  - `VISION_PER_MODEL_TIMEOUT_SECONDS = 8`
- call:
  - `ask_ai_vision(provider, image_paths[0], prompt, model=..., max_tokens=...)`

**مشکل Code verified:** فقط اولین تصویر (`image_paths[0]`) برای AI ارسال می‌شود.

## 6.4 مسیر Text fast برای plan/quick

**Code verified**

`_call_text_ai()` و `_call_text_ai_raw()` در `analysis.py`:

- از `ask_ai_fast()` در `ai_brain.py` استفاده می‌کنند.
- `ask_ai_fast()`:
  - همه providerهای enabled
  - foreign اول، بعد Iranian
  - نه active provider از `ai_runtime`
  - نه failover_chain از `ai_runtime`
  - health cooldown مشترک را لحاظ می‌کند.
- budget:
  - `FAST_TOTAL_TIMEOUT_SECONDS = 15`
  - `FAST_PER_MODEL_TIMEOUT_SECONDS = 4`

## 6.5 مسیر Chat managed برای widget/consultant/bot/super

**Code verified**

`chat_with_managed_ai()` در `ai_runtime.py`:

- `chat_enabled`
- role policy
- daily limit
- capabilities prompt
- super live stats
- `chat_with_failover`
- usage logging در `giso_ai_usage_stats`

`chat_with_failover()`:

- active provider
- failover_chain
- health cooldown
- budget:
  - `CHAT_TOTAL_TIMEOUT_SECONDS = 30`
  - `CHAT_PER_MODEL_TIMEOUT_SECONDS = 6`

## 6.6 تفاوت مهم runtimeها

**Code verified**

- Core image analysis از `analysis.py` + `ai_brain.ask_ai_vision` استفاده می‌کند.
- Quick/plan از `ai_brain.ask_ai_fast` استفاده می‌کنند.
- Consultant chat/site widget/bot/super assistant از `ai_runtime.chat_with_managed_ai` استفاده می‌کنند.

بنابراین:

| تنظیم پنل AI | اثر روی core analysis | اثر روی widget/chat/bot |
|---|---:|---:|
| provider enabled/API key/model | بله | بله |
| active provider | نه مستقیم | بله |
| failover_chain | نه مستقیم | بله |
| role policy/capabilities | نه | بله |
| widget settings | نه | بله |
| health cooldown | بله | بله |

---

# 7) promptها

همه‌ی فایل‌های `giso/prompts/` بررسی شدند.

| prompt | مصرف واقعی | وضعیت |
|---|---|---|
| `hair_initial_analysis.txt` | `_run_initial("hair")` | **Code verified** |
| `skin_initial_analysis.txt` | `_run_initial("skin")` | **Code verified** |
| `hair_final_analysis.txt` | final hair در `analysis.py` و override | **Code verified** |
| `skin_final_analysis.txt` | final skin در `analysis.py` و override | **Code verified** |
| `validate_hair.txt` | `/analysis/validate-image` | **Code verified** |
| `validate_skin.txt` | `/analysis/validate-image` | **Code verified** |
| `plan_generator.txt` | `analysis_plan()` | **Code verified** |
| `quick_solution.txt` | `_generate_quick_solution()` | **Code verified** |
| `consultant_sadeghi.txt` | site consultant chat | **Code verified** |
| `consultant_summarizer.txt` | خلاصه history مشاور هر 5 پیام | **Code verified** |
| `consultant_bot.txt` | `bot_admin_utils._ask_consultant_bot()` | **Code verified** |

**نکته مهم Code verified:** `hair_final_analysis.txt` دارای placeholderهای `{user_answers}`, `{initial_analysis}`, `{user_name}` است، اما code نهایی آن‌ها را replace نمی‌کند؛ فقط JSON context را به انتهای prompt append می‌کند. یعنی مدل هم placeholderهای خام را می‌بیند و هم context واقعی را. این الزاماً شکستن کامل نیست، ولی prompt/code mismatch است.

---

# 8) DB / جدول‌ها / نقاط read-write

## 8.1 جدول اصلی analysis

**Code verified**

`models.py::Analysis`:

- `id`
- `user_id`
- `phone`
- `type`
- `photo_path`
- `ai_report_json`
- `plan_json`
- `quick_solution_json`
- `checklist_progress`
- `review_submitted`
- `review_rating`
- `review_text`
- `review_issue`
- `duration_weeks`
- `image_paths`
- `questions_answers`
- `admin_note`
- `consultant_chat_history`
- `consultant_key_notes`
- `report_type_viewed`
- `chat_rating`
- `created_at`
- `updated_at`
- `archived_at`

## 8.2 جدول‌های analysis مرتبط

**Code verified**

- `analysis_rate_limits`
  - rate limiting نهایی
- `product_requests`
  - درخواست محصول
- `consultant_requests`
  - درخواست مشاوره human/admin
- `consultant_messages`
  - پیام‌های درخواست مشاوره
- `giso_bot_consultant_chat`
  - history ربات
- `reviews`
  - rating/review
- `products`
  - recommendations و plan product context
- `giso_web_auth`
  - user identity
- wallet/credits tables از ماژول wallet/ai_credits

## 8.3 جدول‌های AI

**Code verified**

از `ai_brain.py`, `ai_runtime.py`, `models.py`:

- `giso_ai_providers`
- `giso_ai_checks_log`
- `giso_ai_health`
- `giso_ai_settings`
- `giso_ai_permissions`
- `giso_ai_usage_stats`
- `giso_user_activity`
- `giso_ai_pending_actions`
- `giso_ai_action_logs`
- `giso_widget_chats`
- `giso_widget_feedback`
- `giso_panel_ai_chats`

## 8.4 config

**Code verified**

Rate limit در `bot.db` / `giso_config`:

- `rate_limit_enabled`
- `rate_limit_minutes`
- `rate_limit_type`

خواندن:

- `base.read_rate_limit_config()`

نوشتن:

- legacy route: `/admin/config/analysis-ratelimit`
- form داخل پنل جدید `panel/templates/modules/analyses.html` هنوز action را به `admin_config_ratelimit` می‌زند.

## 8.5 DB engine

**Code verified**

- default: SQLite
- `giso/db_core.py`:
  - `get_giso_db_conn()`
  - `get_bot_db_conn()`
- optional Postgres:
  - `GISO_DB_ENGINE=postgres`
  - DSN envها در `db_engine.py`

---

# 9) Graphify vs Code

## 9.1 وضعیت Graphify

**Graph evidence only**

از `GRAPH_REPORT.md` و `graph.json`:

- 7755 nodes
- 24200 edges
- 241 communities
- 89% extracted
- 11% inferred
- built commit: `36856ba2`
- `html_nodes = 0`
- `txt_nodes = 0`

بنابراین Graphify فعلی **code-only** است؛ templateها، promptها، CSS، HTML، متن promptها را پوشش نداده است.

## 9.2 جدول مقایسه

| رابطه/ادعا | Graph evidence | Code verification | نتیجه |
|---|---:|---|---|
| `app.py` routeهای analysis را register می‌کند | `app.py -> analysis.py` extracted | `register_analysis_routes(app)` در `app.py` | **Code verified** |
| `analysis.py` از `ai_brain.py` استفاده می‌کند | extracted | `ask_ai_vision`, `ask_ai_fast`, `list_ai_providers`, `get_conn` | **Code verified** |
| `analysis.py` از `ai_runtime.py` استفاده می‌کند | extracted | `chat_with_managed_ai`, `get_context_scope` برای consultant chat | **Code verified** |
| `analysis.py` از `analysis_report.py` استفاده می‌کند | extracted | import مستقیم helperها | **Code verified** |
| `analysis_final_override.py` به analysis patch می‌زند | extracted | `install()` و نصب در `app.py/wsgi.py` | **Code verified** |
| `panel/routes.py` به `panel/modules/ai.py` وصل است | extracted | route `/panel/ai` و handlerهای AI | **Code verified** |
| `panel/routes.py` به `panel/modules/analyses.py` وصل است | extracted | route `/panel/analyses` و handlerها | **Code verified** |
| `panel/routes.py` به `panel/modules/super_assistant.py` وصل است | extracted | routeهای `/panel/super-assistant/*` | **Code verified** |
| `panel_user/routes.py` به `panel_user/modules/analyses.py` وصل است | extracted | `/dashboard/analyses` → `_an.context()` | **Code verified** |
| promptهای `giso/prompts/*.txt` | در Graph نیست | grep/code مستقیم | **Code verified خارج از Graph** |
| template route/form/JS relations | در Graph نیست | template/JS مستقیم | **Code verified خارج از Graph** |
| بعضی edgeهای `INFERRED` مثل endpoint/url_for | Graph inferred | فقط برخی با code/template تایید شدند | **Unverified مگر جدا تایید شده باشد** |

---

# 10) دسته‌بندی وضعیت فعلی

## 10.1 کامل و وصل

**Code verified**

- مسیر اصلی مو/پوست از `/analysis` تا گزارش نهایی وصل است.
- DB `analyses` کامل و دارای migration است.
- گزارش نهایی template و helperهای normalize متصل‌اند.
- plan و quick solution متصل‌اند.
- consultant chat API و UI متصل‌اند.
- پنل کاربر history/archive/report/plan/quick/consultant متصل است.
- پنل سوپرادمین برای AI و analysis فعال است.
- provider management و model discovery متصل‌اند.
- bot حداقل برای پیگیری آنالیز، مشاهده لینک گزارش/برنامه و consultant bot متصل است.

## 10.2 ناقص / مشکوک / misleading

1. **Override فعال با divergence**
   - `analysis.py` نهایی شامل billing full analysis و mission completion است.
   - `analysis_final_override.py` active است و این بخش‌ها را ندارد.
   - نتیجه: full report ممکن است بدون charge/mission اجرا شود.

2. **چندعکس ولی فقط عکس اول به AI**
   - upload چند فایل است.
   - `call_vision_with_fallback` فقط `image_paths[0]` را می‌فرستد.

3. **اعتبارسنجی تصویر server-enforced نیست**
   - endpoint validate وجود دارد.
   - `_run_initial` مستقیم تحلیل می‌کند.

4. **active provider/failover پنل برای core analysis نیست**
   - core vision از `VISION_PRIORITY_PROVIDERS`
   - text fast از foreign/iranian order
   - پنل AI ممکن است این را روشن نکند.

5. **routeهای `request_product` و `request_consultant`**
   - ثبت شده‌اند.
   - در template/static فعلی ارجاع فعال پیدا نشد.
   - پنل admin برای product/consultant requests وجود دارد، اما ورودی UI فعلی برای ایجادشان نامشخص/احتمالاً orphan است.

6. **Prompt mismatch در hair final**
   - placeholderها replace نمی‌شوند.

7. **legacy/new admin inconsistency**
   - پنل جدید `/panel/analyses` super-only است.
   - legacy `/admin/consultants` super decorator ندارد و فقط admin access check دارد.

---

# 11) مشکلات واقعی

## مشکل 1 — `analysis_final_override.py` فعال و عقب‌مانده است

**Code verified**

در `analysis.py` داخل `_final_analysis` اصلی:

- `_charge_service_or_block("analysis", ana.id, ...)`
- `complete_mission(..., "analysis_complete", ...)`

وجود دارد.

در `analysis_final_override.py::_final_analysis_fixed`:

- این‌ها وجود ندارند.

از آنجا که `install()` در `app.py` و `wsgi.py` اجرا می‌شود، runtime نهایی همان override است.

**اثر:** billing و mission برای full analysis ممکن است bypass شود.

## مشکل 2 — فقط اولین تصویر تحلیل می‌شود

**Code verified**

`call_vision_with_fallback`:

```python
ask_ai_vision(pname, image_paths[0], ...)
```

**اثر:** اگر کاربر چند عکس بفرستد، UI/DB وانمود می‌کند چندعکسی است، اما AI فقط اولین تصویر را می‌بیند.

## مشکل 3 — validate-image در backend اصلی enforce نشده

**Code verified**

`validate_image_route` وجود دارد، اما `_run_initial()` آن را صدا نمی‌زند.

**اثر:** اگر JS اجرا نشود یا دور زده شود، عکس بدون validation وارد AI analysis می‌شود.

## مشکل 4 — تنظیمات AI پنل برای همه‌ی مسیرها یکسان نیست

**Code verified**

- `set_active_provider` و `failover_chain` در `ai_runtime` برای chat مسیر دارند.
- core analysis vision از `pick_active_vision_model()` و priority خودش استفاده می‌کند.
- quick/plan از `ask_ai_fast()` استفاده می‌کنند.

**اثر:** superadmin ممکن است فکر کند «AI فعال» کل سیستم آنالیز را کنترل می‌کند، در حالی که فقط بخشی از چت/runtime را کنترل می‌کند.

## مشکل 5 — مسیرهای request product/consultant احتمالاً orphan UI هستند

**Code verified + Unverified UI**

- routeها در `analysis.py` هست.
- جستجو در templates/static فعلی لینک/form فعال برایشان پیدا نکرد.
- امکان دارد فقط legacy/external/direct استفاده شوند؛ در code فعلی UI اصلی دیده نشد.

## مشکل 6 — duplicate JSON key در widget chat response

**Code verified**

در `app.py::ai_widget_chat()` خروجی JSON دو بار کلید `ai_credit` دارد:

```python
"ai_credit": credit_line,
"ai_credit": credit_state,
```

در Python dict، مقدار دوم اولی را overwrite می‌کند.

**اثر:** `credit_line` عملاً از response حذف می‌شود.

---

# 12) نتیجه نهایی

**جمع‌بندی:** سیستم «آنالیز هوشمند» در گیسو از نظر route، DB، AI provider، گزارش، پنل کاربر، پنل سوپرادمین، bot و widget واقعاً گسترده و عمدتاً متصل است. هسته اصلی در `giso/analysis.py` است، ولی runtime واقعی final analysis به دلیل `analysis_final_override.py` باید با همان override تحلیل شود.

**وضعیت واقعی:**

- هسته analysis فعال است.
- AI providerها و runtime فعال‌اند.
- پنل کاربر و پنل سوپرادمین به همان DB و تا حدی همان providerها وصل‌اند.
- Graphify برای code navigation مفید است، اما برای prompt/template/UI کامل نیست.
- مهم‌ترین ریسک فنی فعلی divergence بین `analysis.py` و `analysis_final_override.py` است؛ این باعث mismatch واقعی در billing/mission/behavior شده است.
- دومین ریسک، برداشت غلط از تنظیمات AI پنل است: همه‌ی مسیرهای analysis از active provider/failover مشترک پیروی نمی‌کنند.
- چند route/قابلیت مثل `request_product`/`request_consultant` در backend هست ولی UI فعلی برایشان پیدا نشد و باید به‌عنوان orphan/legacy تلقی شوند مگر ورودی خارجی وجود داشته باشد.
----------
بخش سوم مدیریتداد هر سری نخا سنرای زااول باز گو کنم
بله، مستقیم ریپو را بررسی کردم. این بار از روی خود GitHub، نه حدس و گزارش‌های قبلی. بشر هنوز فایل‌ها را با دست جابه‌جا می‌کند، پس بهتر است Agent حداقل حافظه داشته باشد.

### وضعیت واقعی الان

روی branch هدف:

`arena/01a0e0b8-giso4`

آخرین commit:

`36856ba26afe4b413086c212b6b2b49f4c31454f`

پیام:
`Generate Graphify graph for Giso4`

یعنی **آخرین تغییر واقعی پروژه در این branch، کدنویسی قابلیت جدید نیست** و بیشتر مربوط به Graphify است.

قبل از آن هم:

1. حذف `graphify-out`
2. اصلاح `GISO_GUIDE.md`
3. اضافه‌کردن Graphify

پس در چند commit آخر، **هسته Giso دست‌کاری نشده** و تمرکز روی شناخت و مستندسازی پروژه بوده.

### یک نکته مهم که پیدا کردم

در tree فعلی branch هدف:

* `AGENTS.md` وجود ندارد.
* سیستم Memory برای Agent وجود ندارد.
* چیزی با نام `memory` یا `agent-memory` داخل پروژه نیست.
* فقط Agentهای موجود، مربوط به `bot_edu/ai_mentor/agents` هستند و Agent توسعه‌دهنده Giso نیستند.


---

## چیزی که برای Agent جدید لازم داریم

من دقیقاً چیزی که گفتی را به این شکل می‌بینم:

```text
Agent جدید
   │
   ├── اول وضعیت آخر Git را بخوان
   ├── آخرین تغییرات branch را بخوان
   ├── PROJECT_GUIDE.md
   ├── GISO_GUIDE.md
   ├── Graphify
   │
   ├── فقط محدوده Giso
   │
   ├── وضعیت فعلی کار را درک کند
   │
   ├── هر تصمیم/یافته جدید را ذخیره کند
   │
   └── جلسه بعد از صفر شروع نکند
```

برای بخش آخر، **بله، ابزار آماده برای این کار وجود دارد.**

### گزینه‌ای که دقیقاً به درد این پروژه می‌خورد

[mcp-memory در GitHub](https://github.com/corporatepiyush/mcp-memory?utm_source=chatgpt.com)

این پروژه یک MCP برای Agent است که همزمان دارد:

* حافظه دائمی
* Knowledge Graph
* رابطه بین اطلاعات
* Semantic Search
* Code Intelligence
* Codebase indexing
* ذخیره در **یک فایل SQLite**
* بدون نیاز به دیتابیس خارجی

یعنی برای Giso خیلی جالب است، چون Agent می‌تواند مثلاً این دانش را ذخیره کند:

```text
Giso
 ├── Analysis
 │    ├── hair
 │    ├── skin
 │    └── Beauty Mirror
 │
 ├── Beauty Mirror
 │    ├── service
 │    ├── style
 │    ├── image validation
 │    ├── AI analysis
 │    ├── preview
 │    └── reservation
 │
 ├── Architecture Rules
 │    ├── bot_edu locked
 │    ├── web locked
  │
 └── Decisions
      ├── current hair/skin Analysis untouched
      ├── Beauty Mirror new layer
      └── Graphify is code graph, not source of truth
```

و جلسه بعد بتواند همین روابط را دوباره بازیابی کند. ([GitHub][1])

---

### یک گزینه حتی نزدیک‌تر به چیزی که گفتی

[MemoryGraph در GitHub](https://github.com/memory-graph/memory-graph?utm_source=chatgpt.com)

این یکی مشخصاً برای **Coding Agent** ساخته شده و حافظه را به صورت Graph نگه می‌دارد:

```text
problem
   ↓
solution
   ↓
fix
   ↓
decision
   ↓
component
```

و خودش پیشنهاد می‌کند Agent قبل از شروع کار Memory را `recall` کند و در پایان تصمیم‌ها و یافته‌ها را ذخیره کند. حتی امکان جداکردن حافظه برای هر پروژه را دارد. ([GitHub][2])

### گزینه سوم

[Mnemograph در GitHub](https://github.com/tm42/mnemograph?utm_source=chatgpt.com)

این یکی برای Agentهای کدنویسی حافظه Graph دائمی می‌سازد و نکته جالبش این است که Memory را **project-local و قابل version-control با Git** طراحی کرده است. ([GitHub][3])

---

## برای Giso من معماری را این‌طور می‌چینم

**Graphify را حذف نکنیم.**

چون Graphify یک کار دارد:

```text
Graphify
= نقشه ساختار کد
```

ولی Memory باید کار دیگری داشته باشد:

```text
Agent Memory
= چیزهایی که Agent درباره پروژه یاد گرفته
```

پس:

```text
                 GISO
                  │
        ┌─────────┴─────────┐
        │                   │
     Graphify          Agent Memory
        │                   │
   کدها و روابط        تصمیمات
   imports             خطاهای قبلی
   calls               راه‌حل‌ها
   modules             معماری
   dependencies        نکات پروژه
        │                   │
        └─────────┬─────────┘
                  │
             Agent جدید
                  │
          فقط Giso را بررسی کند
```

این خیلی بهتر از این است که هر Agent جدید دوباره ۲۰۰ هزار خط پروژه را بخواند و بعد با اعتمادبه‌نفس انسانی اعلام کند «معماری را فهمیدم». ([GitHub][2])

### نتیجه بررسی من

**الان پروژه یک Code Graph دارد، ولی Agent Memory ندارد.**

و دقیقاً همین جای خالی است که برای Agent جدید باید پر شود.

برای سناریوی فعلی Giso، من فعلاً **کد پروژه را تغییر نمی‌دهم**. قدم منطقی بعدی این است که همین سه ابزار Memory را از نظر نصب، حجم، SQLite/دیتابیس، MCP، سازگاری با Agent فعلی و امکان محدودکردن حافظه فقط به `giso4` مقایسه کنیم و یکی را انتخاب کنیم.

[1]: https://github.com/corporatepiyush/mcp-memory?utm_source=chatgpt.com "GitHub - corporatepiyush/mcp-memory: MCP Knowledge Graph Persistent Memory server written in Rust · GitHub"
[2]: https://github.com/memory-graph/memory-graph?utm_source=chatgpt.com "GitHub - memory-graph/memory-graph: A graph DB-based MCP memory server for coding agents with intelligent relationship tracking · GitHub"
[3]: https://github.com/tm42/mnemograph?utm_source=chatgpt.com "GitHub - tm42/mnemograph: graph-based persistent, yet lightweight memory MCP for CC · GitHub"

