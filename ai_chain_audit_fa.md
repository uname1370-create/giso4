# گزارش ممیزی زنجیرهٔ AI (فارسی)

**تاریخ:** ۲۰۲۶-۱۰-۰۷
**شاخهٔ هدف بررسی:** `arena/01a0eecf-giso4`
**هدف Fetch‌شده:** `FETCH_HEAD=98173df95ce8eb97be89c27c27e3de8551fb2856`
**شاخهٔ checkout این جلسه:** `arena/09bed010-giso4` — `HEAD=898391cfb1476fbc37aa1eafaf1a8e462aa8f34d`

## دامنه و روش

این بررسی فقط‌خواندنی بود. فایل‌های Python بین `HEAD` و شاخهٔ هدف diff ندارند؛ اختلاف‌های شاخهٔ هدف در مستندات، CSS، قالب `generic_service_wizard.html` و دارایی‌های تصویری است. تغییر قالب مشاهده‌شده برچسب نمونه و روش نمایش تصویر را تغییر می‌دهد، نه منطق backend. Graphify از commit قدیمی‌تر است و صرفاً برای جهت‌یابی به کار رفت؛ مرجع نتیجه‌گیری، کد واقعی شاخهٔ هدف است.

**هیچ تست، درخواست API، اتصال DB زنده یا رزرو واقعی انجام نشد. در جریان بررسی، کد و DB تغییر نکردند؛ این فایل صرفاً مستند نتیجهٔ Audit است.**

- **CODE VERIFIED:** مسیر یا منطق از روی کد بررسی شده است؛ به معنی موفقیت runtime نیست.
- **NOT PROVEN — نیاز به Runtime Test:** رفتار وابسته به محیط واقعی است و باید در staging آزمایش شود.
- **NOT TESTED:** در این Audit عملاً اجرا نشده است.

## مرحلهٔ ۱ — Registry، startup و DB

**وضعیت:** منطق startup و schema: `CODE VERIFIED`؛ DB واقعی و ماندگاری: `NOT TESTED`.

- `giso/base.py:328–350` جدول‌های AI را آماده می‌کند، Providerهای `.env` را فقط در صورت خالی بودن جدول Providerها وارد می‌کند و سپس seed رجیستری را اجرا می‌کند.
- `giso/ai_brain.py:1191–1224` Providerهای رجیستریِ غایب را بدون API Key و غیرفعال می‌سازد؛ مدل‌های رجیستری را تازه می‌کند و Providerهای بازنشسته را غیرفعال می‌کند.
- schema در `giso/ai_brain.py:34–51` کلید را در ستون `TEXT` نگه می‌دارد و مسیر افزودن/به‌روزرسانی آن را به `.env` هم می‌نویسد (`ai_brain.py:1715+`). رمزگذاری در سطح کد مشاهده نشد؛ حفاظت فایل/دیسک خارج از این بررسی است.

**اثر عملی:** ردیف Provider در DB یا Registry به‌تنهایی به معنی فعال‌بودن، داشتن کلید یا کارکردن سرویس نیست.

## مرحلهٔ ۲ — مدیریت Provider در Super Admin

**وضعیت:** مسیرهای کد: `CODE VERIFIED`؛ عملیات و persistence واقعی: `NOT PROVEN — نیاز به Runtime Test`.

- handler افزودن Provider در `giso/panel/modules/ai.py:200–310` برای Provider شناخته‌شده Base URL رجیستری را پیش‌فرض می‌گیرد؛ برای Provider ناشناخته Base URL الزامی است (`:237–241`). فرم در `giso/panel/templates/modules/ai.html:63–66` ممکن است خالی‌بودن آن را اختیاری جلوه دهد.
- افزودن با `replace=True` انجام می‌شود (`panel/modules/ai.py:291–300`)، پس افزودن دوبارهٔ همان نام می‌تواند تنظیمات موجود را جایگزین کند. فهرست فیلدهای update شامل نام Provider نیست (`:375–382`).
- حذف Provider در `giso/ai_brain.py:292–299` فقط ردیف Provider را پاک می‌کند؛ پاک‌سازی `.env` یا assignmentهای وابسته در همان مسیر دیده نشد. Sync از `.env` فقط وقتی DB خالی باشد انجام می‌شود.
- **ریسک مشروط SQLite:** `giso/db_core.py:44–56` خطای SQLite هنگام `commit/rollback` در خروج از context را می‌بلعد. `add_ai_provider()` نتیجه را پس از آن از روی `rowcount` می‌دهد (`ai_brain.py:278–289`)، پس خطای commit می‌تواند در آن مسیر به false-success منجر شود. DB engine محیط واقعی بررسی نشده است.

**اثر عملی:** پیام موفقیت در پنل ماندگاری واقعی را ثابت نمی‌کند؛ حذف ردیف هم الزاماً secret فایل یا slotهای مدل را پاک نمی‌کند.

## مرحلهٔ ۳ — اتصال، Health Check و کشف مدل

**وضعیت:** منطق: `CODE VERIFIED`؛ API زنده: `NOT TESTED`.

- آزمون OpenAI-compatible در `giso/ai_brain.py:617–672` ابتدا `/models` را می‌خواند و سپس برای حداکثر شش مدل درخواست متنی `chat/completions` با پیام `Hi` می‌فرستد.
- موفقیت آزمون متنی، قابلیت Vision، تولید تصویر یا inpainting را اثبات نمی‌کند.
- `giso/ai_discovery.py:233–348` مدل‌ها را می‌گیرد، با metadata/heuristic به text و vision دسته‌بندی و در DB ادغام می‌کند. Cloudflare از کشف عمومی رد می‌شود و از Registry ثابت مدیریت می‌شود؛ این مسیر قابلیت image-generation را اثبات نمی‌کند.

**اثر عملی:** `Health=OK` یا مدل کشف‌شده را نباید معادل تأیید قابلیت همان مدل برای ورودی تصویری یا تولید تصویر دانست.

## مرحلهٔ ۴ — Model Assignment و Taskها

**وضعیت:** ساختار Task و readiness: `CODE VERIFIED`؛ assignmentهای DB واقعی: `NOT TESTED`.

- `giso/buti_ai/ai_models.py:20–80` یک Task مشترک Vision، چهار Task تولید تصویر و Task جداگانهٔ `mirror_output_validation` تعریف می‌کند؛ assignmentها بر پایهٔ `task_key` و `priority` ذخیره می‌شوند (`:218+`).
- `readiness_status()` در `ai_models.py:596–720` وجود assignment، فعال‌بودن Provider، کلید و endpoint را می‌سنجد؛ این بررسی، درخواست واقعی به مدل و اثبات قابلیت نیست. برای Cloudflare بخشی از مدل‌های تصویر با allowlist بررسی می‌شود.
- ساخت context پنل می‌تواند `repair_legacy_cloudflare_eyebrow_image_slots()` را اجرا کند (`ai_models.py:382–415, 469–531`) و assignment را اصلاح یا غیرفعال کند. افزودن Cloudflare نیز مسیر auto-configure با `overwrite=True` را فعال می‌کند (`panel/modules/ai.py:309+`, `ai_models.py:786+`).

**اثر عملی:** Provider فعال در بخش عمومی AI به‌تنهایی slotهای اختصاصی Mirror را تنظیم نمی‌کند؛ پنل نیز می‌تواند هنگام خواندن اطلاعات assignmentها را تغییر دهد.

## مرحلهٔ ۵ — Vision و اثر Analysis بر تولید چهار خدمت

**وضعیت:** مسیرهای کد: `CODE VERIFIED`؛ اجرای مدل: `NOT TESTED`.

- زنجیرهٔ Vision آینه از assignmentهای Task مشترک ساخته می‌شود (`ai_models.py:421–437`) و فقط Providerهای assignment‌شده و فعال را می‌گیرد. این مسیر با انتخاب‌گر Vision عمومی سایت متفاوت است.
- در `giso/buti_ai/generic_service.py:124–144` تحلیل Vision برای **ناخن، رنگ مو و لب** هنگام submission فراخوانی می‌شود. شکست تحلیل جذب می‌شود و submission با analysis خالی ادامه پیدا می‌کند.
- `build_final_candidate()` در `generic_service.py:171–201`، `ai_analysis` را به candidate نهایی منتقل نمی‌کند. Promptهای `nail/final_design.py:443–456`، `hair_color/final_design.py:437–451` و `lip/final_design.py:336–350` از style ثابت، انتخاب کاربر و detection/mask ساخته می‌شوند، نه از تحلیل Vision.
- در **ابرو**، `check_photo_quality()` بررسی عکس با Vision و fallback عمومی دارد (`eyebrow/ai.py:85–110`). `analyze_eyebrow_photo()` تعریف شده است (`eyebrow/ai.py:129–145`)، اما call site تولیدی برای تحلیل کامل پیدا نشد. Prompt تولید ابرو بر قرارداد style و انتخاب کاربر تکیه دارد (`eyebrow/final_design.py:380–416`).

| خدمت | مسیر Vision | اثر Analysis بر prompt نهایی |
|---|---|---|
| ابرو | بررسی کیفیت؛ call site تولیدی برای تحلیل کامل پیدا نشد | پیدا نشد |
| ناخن | تحلیل عکس فراخوانی می‌شود | پیدا نشد؛ عمدتاً برای توضیح/نمایش است |
| رنگ مو | تحلیل عکس فراخوانی می‌شود | پیدا نشد؛ عمدتاً برای توضیح/نمایش است |
| لب | تحلیل عکس فراخوانی می‌شود | پیدا نشد؛ عمدتاً برای توضیح/نمایش است |

**اثر عملی:** نتیجهٔ تحلیل می‌تواند توضیح کاربر را غنی کند، اما در مسیر بررسی‌شده مبنای prompt تولید نهایی نیست؛ خروجی واقعی مدل آزمایش نشده است.

## مرحلهٔ ۶ — Image Generation، Inpainting و اعتبارسنجی خروجی

**وضعیت:** منطق کد: `CODE VERIFIED`؛ کیفیت/قابلیت Provider در runtime: `NOT PROVEN — نیاز به Runtime Test`.

- `giso/buti_ai/service_image_generation.py:392–458` Providerهای تصویر را به‌ترتیب امتحان می‌کند، خروجی را داخل mask روی عکس اصلی composite می‌کند و `validate_masked_output()` را اجرا می‌کند (`:120–162`; منطق pixel-diff در `image_validation.py:15–70`).
- اگر Providerها شکست بخورند یا mask برای AI آماده نباشد، guided output محلی برمی‌گردد و `is_ai_generated=False` ثبت می‌شود (`service_image_generation.py:463–477`).
- در مسیر ابرو `ai_inpainting=True` فقط برای kindهای مشخص Cloudflare inpainting برمی‌گردد (`eyebrow/image_generation.py:1295, 1393–1411`); خروجی Flux معمولی را نباید خودکار inpainting واقعی محسوب کرد.
- Task `mirror_output_validation` تعریف شده، اما call site آن در مسیر تولید نهایی پیدا نشد. اعتبارسنجی مشاهده‌شده local pixel-diff/mask check است، نه داوری یک مدل Vision؛ validation می‌تواند در readiness صرفاً warning باشد (`ai_models.py:25, 77, 596–720`).

**اثر عملی:** خروجی راهنمای محلی ممکن است تصویر نهایی قابل‌نمایش باشد، اما کد آن را AI-generated معرفی نمی‌کند. هیچ خروجی واقعی مدل یا mask آزمایش نشده است.

## مرحلهٔ ۷ — Final Design تا Reservation

**وضعیت:** مسیر کد و ایراد route: `CODE VERIFIED`؛ ثبت رزرو واقعی: `NOT TESTED`.

- پس از تولید موفق، مسیر ابرو و خدمات عمومی `save_final_design()` را فراخوانی می‌کند (`giso/buti_ai/routes.py:397–401, 955–960`; ذخیره‌سازی در `giso/buti_ai/services.py:32+`). نمایش مرکز و ثبت رزرو دو مرحلهٔ جدا هستند.
- route رزرو در `giso/beauty_centers/reservations/routes.py:70–116`، `final_design_id`, `service_key` و `selected_style` را می‌پذیرد. `create_reservation()` در `services.py:321–408` slot را داخل تراکنش دوباره بررسی می‌کند و در صورت نامعتبر/پر بودن مقدار `0` می‌دهد.
- **ایراد مهم:** route مقدار `rid` را بررسی نمی‌کند؛ در JSON همچنان `{"ok": true, "id": 0}` می‌دهد (`routes.py:119–129`) و در فرم HTML redirect انجام می‌دهد.

**اثر عملی:** ردشدن رزرو می‌تواند به‌صورت موفقیت ظاهری گزارش شود. این ایراد از روی کد تأیید شد، اما رزرو واقعی/هم‌زمان تست نشده است.

## مرحلهٔ ۸ — مسیر جداگانهٔ تحلیل پوست سایت

این مسیر جزو چهار خدمت Mirror نیست، اما دو ناسازگاری کدی دارد:

- `giso/prompts/skin_final_analysis.txt:27–63` خروجی `radar_metrics` و `concerns` می‌خواهد؛ validator در `giso/analysis.py:301–332, 1078–1085` برای پوست `metrics`, `main_problems`, `summary` را الزامی می‌داند. پاسخ مطابق prompt وارد مسیر fallback می‌شود و ممکن است summary عمومی بگیرد. Normalizer در `giso/analysis_report.py:21–70` ساختار `radar_metrics/concerns` را نیز می‌پذیرد، بنابراین از این ناسازگاری به‌تنهایی نمی‌توان شکست کل صفحه را نتیجه گرفت.
- Prompt اعتبارسنجی عکس پوست فیلد `checks.no_heavy_makeup` را تعریف می‌کند، اما mapping نمایشی در `giso/templates/analysis_skin.html:438–445` آن را مصرف نمی‌کند.

**اثر عملی:** schema prompt و validator هم‌راستا نیستند و یک check در نمایش جزئی UI نادیده می‌ماند؛ رفتار زنده بررسی نشده است.

## جمع‌بندی

| حلقه | نتیجهٔ ایستا | Runtime |
|---|---|---|
| Provider/DB | Seed و CRUD موجود؛ حذف، `.env` و assignmentهای جانبی را پاک نمی‌کند؛ ریسک مشروط بلع خطای commit در SQLite | `NOT TESTED` |
| Health/Discovery | آزمون اتصال متنی است؛ image-generation را اثبات نمی‌کند | `NOT TESTED` |
| Assignment | slotهای Mirror جدا هستند؛ readiness آزمون واقعی قابلیت مدل نیست؛ بعضی مسیرهای پنل DB را تغییر می‌دهند | `NOT TESTED` |
| Vision/Analysis | سه خدمت عمومی تحلیل می‌شوند اما Analysis به prompt تولید نمی‌رسد؛ تحلیل کامل ابرو call site تولیدی ندارد | `NOT TESTED` |
| تصویر/Validation | mask و pixel-diff محلی؛ fallback صریحاً غیر-AI؛ Task مدل اعتبارسنجی در مسیر تولید مصرف نشد | `NOT TESTED` |
| Reservation | اگر `create_reservation()` صفر بدهد، route هنوز موفقیت اعلام می‌کند | `NOT TESTED` |
| پوست سایت | prompt و validator schema متفاوت دارند؛ `no_heavy_makeup` در checkMap نمایشی نیست | `NOT TESTED` |

**جمع‌بندی نهایی:** زنجیرهٔ کدی از Provider تا رزرو قابل‌ردیابی است، اما اتصال زنده، persistence، قابلیت واقعی مدل‌ها، کیفیت خروجی تصویر و رزرو از این Audit ایستا اثبات نمی‌شوند. مهم‌ترین ایرادهای کدیِ مشاهده‌شده: false-success رزرو با `id=0`، واردنشدن تحلیل Vision به prompt تولید نهایی خدمات عمومی، و mismatch بین prompt و validator تحلیل پوست.
