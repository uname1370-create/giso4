# SATRT1 — سناریوی تست کامل ۱۰ اصلاحیه Giso4

## هدف

این سناریو فقط برای **تست و راستی‌آزمایی** اصلاحات انجام‌شده روی همین برنچ است:

- Repository: `uname1370-create/giso4`
- Branch: `arena/09bed010-giso4`

مبنای تست، همان ۱۰ موردی است که قبلاً به‌عنوان مشکل قطعی شناسایی و برای اصلاح به ایجنت داده شده‌اند.

## قانون بسیار مهم

این مرحله **فقط TEST / AUDIT / VERIFICATION** است.

- هیچ کدی را تغییر نده.
- هیچ فایل کدی را اصلاح نکن.
- هیچ refactor انجام نده.
- هیچ feature جدید نساز.
- هیچ migration جدید نساز.
- هیچ ساختار جدیدی اضافه نکن.
- UI را تغییر نده.
- اگر تستی شکست خورد، فقط علت، محل کد و شواهد را گزارش کن.
- اگر برای اجرای تست نیاز به داده یا تنظیم موقت داری، فقط از Test DB / Test Environment استفاده کن و چیزی را در سورس تغییر نده.
- فایل‌های گزارش را فقط در پایان و برای ثبت نتیجه بساز.
- مبنا فقط **Code Truth همین برنچ** است؛ گزارش‌ها یا Project Memory قدیمی را به‌عنوان اثبات سلامت کد قبول نکن.

---

# مرحله ۱ — تثبیت وضعیت برنچ

ابتدا:

1. branch فعلی را دقیقاً بررسی کن.
2. HEAD و commit فعلی را ثبت کن.
3. مطمئن شو تست روی `arena/09bed010-giso4` انجام می‌شود.
4. وضعیت working tree را بررسی کن.
5. قبل از شروع تست، هیچ تغییر محلی ایجاد نکن.

در گزارش نهایی ثبت کن:

- Branch
- HEAD
- وضعیت working tree
- زمان شروع تست

---

# مرحله ۲ — بررسی تغییرات مربوط به ۱۰ مشکل

قبل از اجرای تست، برای هر ۱۰ مورد مسیر واقعی کد را پیدا کن.

برای هر مورد مشخص کن:

- فایل
- function / route / template مرتبط
- منطق اصلاح‌شده
- نقطه‌ای که باید تست شود

اگر اصلاحی واقعاً در کد وجود ندارد، آن مورد را FAIL کن؛ صرفاً به خاطر وجود comment یا documentation آن را PASS نکن.

---

# مرحله ۳ — تست امنیت Final Design و فایل‌های Mirror

## هدف

بررسی کن آیا کاربر بدون مجوز می‌تواند Final Design یا فایل عکس متعلق به کاربر دیگر را با ID/path حدس‌زدنی مشاهده یا دریافت کند یا خیر.

### تست‌ها

### 3.1 کاربر مهمان

با session بدون login:

- Final Design متعلق به user A را با ID مستقیم درخواست کن.
- مسیر عکس upload شده متعلق به user A را مستقیم درخواست کن.
- مسیر فایل final design متعلق به user A را مستقیم درخواست کن.

نتیجه مورد انتظار:

- دسترسی غیرمجاز نباید ممکن باشد.
- نباید اطلاعات خصوصی یا تصویر خصوصی user A برگردد.

### 3.2 کاربر B

با login به‌عنوان user B:

- Final Design user A را با ID مستقیم درخواست کن.
- upload user A را با filename/path مستقیم درخواست کن.
- final image user A را مستقیم درخواست کن.

نتیجه مورد انتظار:

- user B نباید هیچ‌کدام را ببیند.

### 3.3 مالک واقعی

با login به‌عنوان user A:

- Final Design خودش را باز کند.
- فایل‌های متعلق به خودش را دریافت کند.

نتیجه مورد انتظار:

- دسترسی مجاز و بدون خطا.

### مسیرهای مورد بررسی

حداقل این بخش‌ها را بررسی کن:

- `giso/buti_ai/routes.py`
- `giso/buti_ai/services.py`
- مسیرهای upload/final image مربوط به eyebrow
- مسیرهای generic service

در گزارش، برای هر تست نتیجه دقیق HTTP/redirect/error و علت PASS/FAIL را بنویس.

---

# مرحله ۴ — تست Reservation و خطای id=0

## هدف

اطمینان از اینکه reservation ناموفق دیگر به‌عنوان موفق گزارش نمی‌شود.

### تست 4.1 رزرو موفق

یک slot معتبر و آزاد را رزرو کن.

انتظار:

- reservation واقعی ساخته شود.
- ID معتبر و بزرگ‌تر از صفر برگردد.
- پیام/redirect موفقیت صحیح باشد.

### تست 4.2 slot اشغال‌شده

همان slot را دوباره رزرو کن.

انتظار:

- reservation جدید ساخته نشود.
- نتیجه SUCCESS نباشد.
- `id=0` نباید به معنی موفقیت تفسیر شود.

### تست 4.3 مرکز بسته / روز غیرکاری

رزرو در زمان غیرمجاز انجام بده.

انتظار:

- reservation ساخته نشود.
- نتیجه شکست واقعی باشد.

### تست 4.4 service نامعتبر یا غیرفعال

با service نامعتبر/غیرفعال تست کن.

انتظار:

- reservation ساخته نشود.
- نتیجه موفقیت نباشد.

### تست 4.5 JSON و HTML

اگر route هر دو حالت JSON و browser redirect دارد، هر دو را تست کن.

خصوصاً بررسی کن که:

`create_reservation() == 0`

دیگر به:

`{"ok": true, "id": 0}`

تبدیل نشود.

---

# مرحله ۵ — تست Mirror → Reservation با Service دقیق

## هدف

وقتی کاربر از Mirror برای یک خدمت مشخص وارد رزرو می‌شود، همان service باید رزرو شود؛ نه اولین service فعال مرکز.

### تست

حداقل یک مرکز با بیش از یک service فعال داشته باش.

مثلاً:

- eyebrow
- nail

از Mirror یک نتیجه با:

- `final_design_id`
- `service_key`
- service مربوطه

را وارد مسیر reservation کن.

بررسی کن:

1. service ID صحیح منتقل شود.
2. فرم reservation همان service را نگه دارد.
3. service دیگری به‌صورت fallback انتخاب نشود.
4. snapshot رزرو با Mirror هماهنگ باشد.

### تست منفی

عمداً service موردنظر را حذف/غیرفعال کن.

انتظار:

- سیستم نباید به‌صورت بی‌صدا اولین service دیگر را انتخاب کند.
- باید failure/عدم امکان رزرو مشخص باشد.

---

# مرحله ۶ — تست تب‌های Super Admin Beauty Centers

## هدف

بررسی کن تب‌هایی که قبلاً از route حذف/رد می‌شدند واقعاً قابل دسترسی هستند.

این تب‌ها را جداگانه تست کن:

- dashboard
- requests
- published
- paused
- services
- portfolio
- reservations
- mirror
- promotions
- feedback
- settings

### برای هر تب

1. با Super Admin وارد شو.
2. URL واقعی را باز کن.
3. status code / redirect را بررسی کن.
4. محتوای درست همان tab را بررسی کن.
5. مطمئن شو به `requests` fallback نمی‌کند.

### تست نقش غیر-Super

اگر محدودیت نقش برای برخی tabها وجود دارد، آن را نیز بررسی کن.

نتیجه مورد انتظار:

- Super Admin تب‌های مجاز را می‌بیند.
- role restriction خراب نشده باشد.

---

# مرحله ۷ — تست Listing Expiration

## هدف

یکپارچگی وضعیت انتشار و expiration مرکز را بررسی کن.

### تست 7.1 مرکز معتبر

مرکز:

- published
- active
- listing هنوز منقضی نشده

باید:

- در لیست عمومی دیده شود.
- صفحه جزئیات عمومی داشته باشد.
- در مسیر رزرو قابل استفاده باشد.

### تست 7.2 مرکز منقضی‌شده

`listing_expires_at` را در Test DB در گذشته قرار بده.

بررسی:

- در public list نباشد.
- direct detail عمومی قابل دسترسی نباشد.
- reservation عمومی برای آن امکان‌پذیر نباشد.

### تست 7.3 owner/admin

بررسی کن اگر طراحی فعلی اجازه مشاهده مدیریتی مرکز منقضی‌شده را می‌دهد، این دسترسی مدیریتی با public access قاطی نشده باشد.

اصل تست:

**Expired public listing نباید به‌صورت مستقیم قابل رزرو یا مشاهده عمومی باقی بماند.**

---

# مرحله ۸ — تست منبع Service در Beauty Center و Mirror

## هدف

بررسی کن Mirror و Beauty Center از دو منبع متناقض برای service استفاده نمی‌کنند.

مخصوصاً مقایسه کن:

- `beauty_center_services`
- `services_json`

### سناریو A

یک مرکز فقط از مسیر جدید service registration، service معتبر دارد.

بررسی:

- آیا در Mirror recommendation ظاهر می‌شود؟
- آیا service قابل رزرو است؟
- آیا همان service در detail نمایش داده می‌شود؟

### سناریو B

یک service در داده قدیمی وجود دارد ولی در registered services فعال نیست.

بررسی:

- آیا Mirror آن را اشتباه پیشنهاد می‌دهد؟
- آیا service غیرفعال یا غیرقابل رزرو نمایش داده می‌شود؟

### نتیجه مورد انتظار

منبع واقعی و فعال service باید با چیزی که Mirror پیشنهاد می‌دهد و چیزی که Reservation رزرو می‌کند سازگار باشد.

اگر هنوز دو منبع متفاوت در مسیرهای مختلف استفاده می‌شوند، دقیقاً گزارش کن کجا و چه اثری دارد.

---

# مرحله ۹ — تست User History و بازکردن همان Final Design

## هدف

وقتی کاربر از تاریخچه Mirror روی «مشاهده نتیجه» یا «رزرو همین خدمت» می‌زند، همان نتیجه قبلی باز شود.

### تست

1. user A یک Mirror result ایجاد کند.
2. `final_design_id` را ثبت کن.
3. از User Panel وارد history/analyses شو.
4. روی مشاهده نتیجه بزن.
5. ID نتیجه مقصد را بررسی کن.

انتظار:

- همان `final_design_id` قبلی باز شود.
- wizard جدید یا نتیجه session فعلی جایگزین نتیجه تاریخی نشود.

### تست Reservation

از history روی رزرو همان خدمت بزن.

بررسی:

- `final_design_id` حفظ شود.
- `service_key` حفظ شود.
- `selected_style` حفظ شود.
- service صحیح انتخاب شود.

---

# مرحله ۱۰ — تست Owner Dashboard و Mirror Linkage

## هدف

بررسی کن owner وقتی reservation حاصل از Mirror را می‌بیند، اطلاعات linkage لازم را از دست نداده باشد.

برای یک reservation دارای Mirror:

- `final_design_id`
- `service_key`
- `selected_style`

را بررسی کن.

در Owner Dashboard بررسی کن اطلاعات مرتبط با Mirror طبق اصلاح انجام‌شده قابل مشاهده/پیگیری است.

اگر UI عمداً فقط بخشی را نمایش می‌دهد، از روی code truth مشخص کن چه چیزی طراحی شده و آیا linkage backend سالم باقی مانده است.

---

# مرحله ۱۱ — تست Ownership و اعتبارسنجی Mirror در Reservation

## هدف

کاربر نتواند reservation خود را به Final Design کاربر دیگر یا یک ID جعلی وصل کند.

### تست 11.1

user A یک Final Design واقعی دارد.

user B تلاش کند reservation خودش را با:

`final_design_id = user A`

ثبت کند.

انتظار:

- رد شود.

### تست 11.2

با `final_design_id` جعلی تست کن.

انتظار:

- reservation نباید با linkage جعلی ثبت شود.

### تست 11.3

Final Design متعلق به user A ولی service_key متعلق به یک service نامرتبط.

انتظار:

- mismatch باید رد شود یا حداقل linkage ناسازگار ثبت نشود.

### تست 11.4

کاربر بدون login تلاش کند reservation را با final_design_id شخص دیگر بسازد.

انتظار:

- نباید امکان دستکاری linkage وجود داشته باشد.

---

# مرحله ۱۲ — Regression Test

بعد از ۱۰ مورد بالا، فقط regressionهای مرتبط را تست کن؛ نه کل پروژه را.

حداقل:

1. Eyebrow Mirror
2. Generic Mirror:
   - nail
   - hair_color
   - lip_shading
3. Beauty Center public list
4. Beauty Center detail
5. Reservation
6. User Panel history
7. Owner Dashboard
8. Super Admin Beauty Centers

هدف regression:

بررسی کن اصلاحات امنیتی و reservation باعث شکستن flowهای موجود نشده باشند.

---

# مرحله ۱۳ — تست Code Path و تست واقعی

برای هر مورد دو سطح را جدا کن:

## A. Code-level verification

بررسی static:

- route
- function
- query
- ownership check
- validation
- fallback
- redirect
- template parameter

## B. Runtime verification

تا جایی که محیط تست اجازه می‌دهد:

- درخواست واقعی
- session واقعی
- DB test
- response
- status code
- redirect
- returned JSON
- reservation row

را تست کن.

**فقط code review به‌تنهایی PASS محسوب نمی‌شود اگر runtime قابل تست باشد.**

اگر runtime به دلیل نبود dependency / DB / credential / service خارجی ممکن نیست، آن را صریحاً:

`NOT TESTED — ENVIRONMENT BLOCKED`

ثبت کن، نه PASS.

---

# مرحله ۱۴ — بررسی عدم Regression در فایل‌های حساس

بدون تغییر دادن آن‌ها، فقط بررسی کن که این تست‌ها باعث دستکاری یا تغییر ناخواسته این بخش‌ها نشده باشند:

- `main.py`
- `web`
- `bot_edu`
- `giso/bot.py`

اگر تغییر unrelated وجود دارد، گزارش کن.

---

# مرحله ۱۵ — ساخت گزارش نهایی

بعد از تمام تست‌ها، یک فایل گزارش Markdown در **همین branch** بساز.

نام فایل را خودت انتخاب کن، ولی نام باید واضح باشد؛ مثلاً:

`satrt1_test_report.md`

یا یک نام مشابه و معنادار.

گزارش باید شامل این بخش‌ها باشد:

## 1. Test Identity

- Repository
- Branch
- HEAD
- Date/time
- Test environment
- Runtime availability

## 2. Summary

یک جدول دقیق:

| # | مورد | نتیجه |
|---|---|---|
| 1 | Final Design / Mirror ownership | PASS / FAIL / PARTIAL / BLOCKED |
| 2 | Reservation id=0 | ... |
| 3 | Mirror service ID | ... |
| 4 | Super Admin tabs | ... |
| 5 | Listing expiration | ... |
| 6 | Service source consistency | ... |
| 7 | User history exact result | ... |
| 8 | Owner Mirror linkage | ... |
| 9 | Reservation ownership validation | ... |
| 10 | Project/Memory consistency | ... |

## 3. Evidence

برای هر مورد:

- فایل
- function/route
- test scenario
- expected
- actual
- result
- اگر ممکن است status code / DB evidence

## 4. Failed Tests

فقط موارد FAIL/PARTIAL/BLOCKED را با علت دقیق بیاور.

## 5. Regression

نتیجه regressionهای مرتبط را ثبت کن.

## 6. Final Verdict

یکی از این حالت‌ها:

- **PASS — هر ۱۰ مورد تأیید شد**
- **PASS WITH LIMITATIONS — موردی runtime قابل تست نبود**
- **FAIL — حداقل یک مشکل هنوز باقی است**

---

# قانون نهایی گزارش

گزارش باید بر اساس **نتیجه واقعی تست** باشد، نه حدس.

اگر یک مورد فقط از روی code قابل تأیید است، بنویس:

`CODE VERIFIED`

اگر runtime هم تست شده:

`RUNTIME VERIFIED`

اگر قابل تست نبوده:

`BLOCKED / NOT TESTED`

اگر مشکل هنوز وجود دارد:

`FAIL`

هیچ موردی را برای اینکه گزارش تمیزتر شود PASS اعلام نکن.

---

# خروجی نهایی مورد انتظار از Agent

در پایان فقط این موارد را به کاربر اعلام کن:

1. branch و HEAD تست‌شده
2. تعداد PASS / FAIL / PARTIAL / BLOCKED
3. خلاصه ۱۰ مورد
4. نام دقیق فایل گزارش ساخته‌شده
5. مسیر فایل گزارش در repository
6. commit SHA ایجادشده
7. اگر مشکلی باقی مانده، دقیقاً کدام مورد و کجاست

**هیچ کد پروژه را تغییر نده.**
