# گزارش اجرا و ممیزی Buti AI — آپلود، تحلیل، پیشنهاد، خروجی و دانلود

**زمان:** 2026-10-12، منطقه زمانی کاربر Asia/Tehran
**برنچ:** `arena/7f567e47-giso4`
**HEAD پایه پیش از تغییر:** `1f96ffa` — `Document Buti AI upload analysis recommendation flow`
**محدودهٔ مجاز رعایت‌شده:** فقط `giso/buti_ai/`، تست‌های Buti AI و `project_memory/letta/`؛ هیچ تغییری در `web/`، `bot_edu/`، `main.py` یا `giso/bot.py` انجام نشد.

## 1. ترتیب منابع مطالعه‌شده

به ترتیبی که `AGENT_START_HERE.md` مشخص کرده بود:

1. `BOOTSTRAP_PROMPT.md`

1. `PROJECT_MEMORY.md`

1. `PROJECT_MEMORY.json`

1. `CODE_BOUNDARY_RULES_BUTI_AI.md`

1. `FINAL_IMPLEMENTATION_SCENARIO_BUTI_AI_2026-10-12.md`

1. `TECHNICAL_DESIGN_BUTI_AI_MVP.md`

1. `SCENARIO_BEAUTY_MIRROR_EYEBROW.md`

1. `SCENARIO_BEAUTY_MIRROR_SERVICE_EXPANSION.md`

1. `UPDATE_TEMPLATE.md`

1. `tools/letta/README.md`

1. سناریوی تکمیلی: `BUTI_AI_UPLOAD_ANALYSIS_RECOMMENDATION_IMPLEMENTATION_SCENARIO.md`

سپس routeها، flowها، promptها، قالب‌ها، JavaScript، service catalog و تست‌های واقعی بررسی شدند. ماتریس بازتولید و آزمون در [طرح آزمون](/home/ubuntu/giso4/project_memory/letta/BUTI_AI_UPLOAD_ANALYSIS_RECOMMENDATION_TEST_PLAN.md) ثبت است.

## 2. قرارداد اجراشده

```
انتخاب خدمت → انتخاب مدل/شدت → preview محلی فایل
→ POST validate با FormData + CSRF + same-origin credential
→ کیفیت و Vision analysis
→ پیشنهاد گیسو یا انتخاب اولیه کاربر
→ POST اول upload: 200 و candidate در session، بدون generation
→ POST دوم finalize با analysis_confirmed=1
→ generation با final_style تأییدشده
→ before/after + برچسب صادقانه AI/non-AI
→ دانلود محافظت‌شدهٔ تصویر و گزارش PDF
```

### تغییرات کد انجام‌شده

- **ابرو:** `eyebrow/flow.py` اکنون در upload کیفیت و تحلیل را انجام می‌دهد، ولی generation/mask را تا تأیید کاربر عقب می‌اندازد.

- **پیشنهاد AI:** `result.py` و `final_design.py` انتخاب اولیه، پیشنهاد AI و `final_style` تأییدشده را مستقل نگه می‌دارند؛ انتخاب AI هرگز بدون تأیید مدل نهایی نمی‌شود.

- **لب:** `generic_service.py` و routeهای generic قرارداد recommendation را فقط برای flow لب وارد کرده‌اند؛ مسیرهای ناخن و رنگ مو همان redirect و پیام قبلی را حفظ کرده‌اند.

- **اعتبارسنجی مرورگر:** `/eyebrow/validate-photo` و `/lip-shading/validate-photo` اکنون `recommendation` نرمال‌شده، وضعیت `ai_analyzed` یا `ai_unavailable` و reason برمی‌گردانند.

- **تأیید سرور:** finalize ابرو و لب بدون `analysis_confirmed=1` generation نمی‌کنند. `final_style` ورودی نرمال می‌شود و برای prompt/provider استفاده می‌شود.

- **دانلود:** routeهای session/owner-protected برای تصویر و PDF اضافه شدند:
  - `/analysis/mirror/eyebrow/download/image`
  - `/analysis/mirror/eyebrow/download/report.pdf`
  - `/analysis/mirror/lip-shading/download/image`
  - `/analysis/mirror/lip-shading/download/report.pdf`

- **PDF:** `giso/buti_ai/downloads.py` گزارش in-memory، راست‌به‌چپ، شامل summary و before/after می‌سازد؛ فایل خصوصی اضافه‌ای نگه نمی‌دارد.

- **UI:** دو کارت قابل انتخاب، وضعیت شفاف AI، preview، checkها، state loading، و cache-bust دارایی‌های JS/CSS به قالب ابرو و لب اضافه شد.

- **fallback صادقانه:** خروجی هدایت‌شده/غیر AI در صفحه final با «راهنمای غیر AI» معرفی می‌شود، نه خروجی AI.

## 3. وضعیت واقعی خدمات از روی کد و اجرای حاضر

| خدمت | وضعیت اعلام‌شده در `service_catalog.py` | واقعیت کد/flow | وضعیت واقعی در این اجرا |
| --- | --- | --- | --- |
| ابرو (`eyebrow`) | `active` | انتخاب، upload، validate، پیشنهاد، تأیید، final، before/after، دانلود تصویر/PDF وجود دارد | **جریان fallback تا خروجی نهایی در مرورگر اجرا شد. AI واقعی آماده/تأییدشده نیست**؛ log runtime `providers: 0` بود. |
| لب (`lip_shading`) | `active` | انتخاب، upload، validate، پیشنهاد، تأیید، final و دانلود تصویر/PDF وجود دارد | قرارداد route و دانلود با تست pass شد؛ provider واقعی به دلیل نبود provider پیکربندی‌شده تأیید نشد. |
| ناخن (`nail`) | `active` | flow staged قدیمی و final generic دارد | خارج از تغییر سناریوی حاضر؛ دانلود تصویر/PDF جدید ندارد؛ AI واقعی در این محیط تأیید نشد. |
| رنگ مو (`hair_color`) | `active` | flow staged قدیمی و final generic دارد | خارج از تغییر سناریوی حاضر؛ دانلود تصویر/PDF جدید ندارد؛ AI واقعی در این محیط تأیید نشد. |
| رژگونه (`blush`) | در مستندات هدف آمده، در catalog/runtime نیست | ماژول/route فعال برای آن پیدا نشد | **پیاده‌سازی/آماده اعلام نمی‌شود.** |
| خط چشم (`eyeliner`) | در مستندات هدف آمده، در catalog/runtime نیست | ماژول/route فعال برای آن پیدا نشد | **پیاده‌سازی/آماده اعلام نمی‌شود.** |
| Hoosha | مستندات آن را production-ready نمی‌دانند | اتصال رسمی server-to-server image edit/mask تأیید نشد | **آماده نیست.** |

> تناقض مستندشده: `FINAL_IMPLEMENTATION_SCENARIO...` چهار هدف brow/lip/blush/eyeliner را بیان می‌کند، ولی `service_catalog.py` در runtime eyebrow/nail/hair_color/lip_shading را با `status: active` ارائه می‌دهد. این تغییر آن را حدس‌وار حل نکرد؛ فقط سناریوی صریح upload/recommendation برای ابرو و لب را پیاده کرد.

## 4. اعتبارسنجی‌های واقعاً موفق

| آزمون | نتیجه |
| --- | --- |
| `node --check giso/buti_ai/static/buti_ai.js` | موفق |
| `python -m py_compile` برای route/flow/generic/downloads | موفق |
| `git diff --check` | موفق |
| `pytest -q test_buti_ai_phase1.py test_buti_ai_new_services.py test_buti_ai_upload_recommendation.py` | **53 passed** در 35.60s |
| اعتبارسنجی mock AI ابرو و لب | موفق؛ recommendation نرمال و `ai_analyzed` |
| provider unavailable | موفق؛ `ai_unavailable` صادقانه و انتخاب دستی فعال |
| POST اول بدون generation / POST دوم با تأیید | موفق |
| مالکیت candidate و دانلود بدون session | موفق؛ مالک 200 و client دیگر 404 |
| PDF in-memory و header دانلود | موفق برای ابرو و لب |
| smoke browser ابرو | موفق تا صفحه final: انتخاب مدل، upload، preview، validate، کارت `AI در دسترس نیست`، تأیید دستی، before/after و لینک‌های دانلود دیده شد |

## 5. محدودیت‌های تأیید و اشکالات باقی‌مانده

1. **AI/provider واقعی پیکربندی نشده است.** بررسی connector نتیجه‌ای برای Cloudflare/OpenAI/Vision نداشت و log مرورگر هنگام validate `Vision-capable: 0/0` را نشان داد. بنابراین تحلیل/generation واقعی، latency، خروجی mask و هزینهٔ provider در محیط فعلی تأیید نشده‌اند.

1. **در smoke browser، کلیک لینک دانلود پس از رسیدن به final با خطای ابزار مرورگر ****`Browser not available`**** قطع شد.** خود routeهای image/PDF برای ابرو و لب با تست‌های مالکیت و payload PDF تأیید شده‌اند، اما download از همان نشست مرورگر در ابزار فعلی قابل تکمیل نبود.

1. **گیت عمومی production هنوز آماده اعلام نمی‌شود.** اسناد فعلی cost ledger، provider attempt tracking، user charge، idempotency، quota، circuit breaker، رضایت صریح برای ارسال عکس و queue/worker را پیش‌نیاز public launch می‌دانند؛ این موارد در محدودهٔ سناریوی upload/recommendation حاضر پیاده نشده‌اند.

1. warnings تست شامل `datetime.utcnow()` deprecated در فایل‌های موجود است. این تغییر آن‌ها را ایجاد نکرد و فقط گزارش می‌کند؛ تبدیل به timezone-aware باید task جداگانه باشد.

## 6. گام بعدی پیشنهادی

1. یک provider Vision و image-edit server-to-server را در مدیریت AI پروژه پیکربندی و با عکس غیرحساس benchmark کنید.

1. سپس مسیر واقعی AI را با همان ماتریس [طرح آزمون](/home/ubuntu/giso4/project_memory/letta/BUTI_AI_UPLOAD_ANALYSIS_RECOMMENDATION_TEST_PLAN.md) دوباره اجرا کنید: quality، analysis، masked generation، provider failure و PDF/download.


1. پیش از public launch، پیش‌نیازهای ledger/quota/idempotency/queue/consent مستندشده را پیاده کنید.


## 7. دستور handoff برای ایجنت بعدی

این بخش از کار شامل پیاده‌سازی flow آپلود/تحلیل/پیشنهاد/تأیید، خروجی fallback، دانلود تصویر/PDF، تست‌های قرارداد و smoke test مرورگر **انجام‌شده محسوب می‌شود و نباید از ابتدا تکرار شود**. ایجنت بعدی ابتدا `PROJECT_MEMORY.md` و `PROJECT_MEMORY.json` را بخواند، سپس فقط این موارد را ادامه دهد:

1. یک provider واقعی و مجاز Vision/image-edit را در تنظیمات پروژه پیدا یا پیکربندی کند؛ بدون credential حدسی یا hard-code.
2. ماتریس real-provider در `BUTI_AI_UPLOAD_ANALYSIS_RECOMMENDATION_TEST_PLAN.md` را با تصویر غیرحساس اجرا کند و نتیجهٔ واقعی را به همین گزارش اضافه کند.
3. در صورت موفقیت provider، quality، analysis، mask، generation، before/after، image download و PDF download را دوباره در مسیر واقعی بررسی کند.
4. قبل از public launch، ledger هزینه، provider-attempt tracking، charge، idempotency، quota، circuit breaker، consent و queue/worker را طبق مستندات بررسی/پیاده کند.
5. تست‌های ثبت‌شده را دوباره اجرا کند؛ تغییرات فعلی را rollback یا بازطراحی نکند مگر اینکه تست یا مستندات تناقض مشخصی نشان دهد.


## 8. بازاجرای مستقل در workspace فعلی — 2026-10-12، حدود 14:39 Asia/Tehran

### وضعیت محیط و provider

- شاخهٔ فعال `arena/7f567e47-giso4` و `HEAD` پایه `cb53d58135bec2ab861be8ec3fc50bd00e5f8929` بود؛ شاخهٔ محلی با `origin/arena/7f567e47-giso4` همگام و working tree پیش از این ضمیمه پاک بود.
- checkout حاضر فاقد `giso/data/giso.db` و `giso/data/.env` است؛ بنابراین provider/assignment فعلی را نتوان از دیتابیس یا تنظیم محلی تأیید کرد. مسیر `/admin/ai` و readiness پنل به‌علت نبود نشست ورود سوپرادمین تأیید نشد و هیچ تنظیمی تغییر نکرد.
- در این نشست عکس واقعیِ کاربر برای آزمون Vision/inpainting ارائه نشده بود. در نتیجه هیچ فراخوانی زنده به Cloudflare، Vision یا image generation انجام نشد و credential دریافتی در هیچ آزمون یا درخواست خارجی استفاده/ذخیره نشد.
- موفقیت مستقیم env و وضعیت provider غیرفعال/بدون کلید که در prompt کاربر به‌عنوان سابقه ذکر شده‌اند، در این workspace دوباره راستی‌آزمایی نشدند و نباید به‌عنوان readiness فعلی پنل تعبیر شوند.

### آزمون‌ها و نتیجهٔ بازتولیدپذیر

آزمون‌ها در یک git worktree موقت و virtualenv خارج از checkout اصلی اجرا شدند؛ credentialهای محیطی حذف شده بودند. مفسر سیستم در تلاش نخست `pytest` نداشت؛ پس از نصب وابستگی‌های project/landmarks و pytest در `/tmp/giso4-test-env`، دور کامل با موفقیت اجرا شد:

| مرحله | نتیجه |
| --- | --- |
| `node --check giso/buti_ai/static/buti_ai.js` | موفق |
| `python -m py_compile` روی routeها، flowها، generation، downloads، panel AI، `ai_brain.py` و registry | موفق |
| upload/recommendation/download و output formats | 11 passed، 24 warning، 23.29s |
| eyebrow detector/inpainting request/mask/ROI/recolor | 22 passed، 17 warning، 5.14s |
| خدمات جدید، gating و flowهای چهار خدمت | 38 passed، 4 skipped، 72 warning، 36.51s |
| کل `giso/tests/test_buti_ai*.py` | **137 passed، 4 skipped، 153 warning، 88.02s** |
| تست‌های متمرکز Cloudflare Vision و provider registry: `test_ai_cloudflare_vision.py`, `test_ai_provider_admin_registry.py`, `test_ai_provider_ssrf.py`, `test_ai_clean_registry.py`, `test_ai_discovery.py` | **32 passed، 1.82s** |
| `git diff --check` در worktree آزمایشی | موفق |

چهار skip مربوط به آزمون‌هایی است که به عکس close-up واقعی لب یا مجموعه‌عکس واقعی مو نیاز دارند و در محیط موجود نبودند. mockهای Vision/provider و inpainting فقط قرارداد request/response و پردازش محلی را می‌سنجند؛ آن‌ها شاهد کیفیت خروجی مدل زنده نیستند.

در بررسی تکمیلیِ خارج از suite Buti AI، دو تست از `giso/tests/test_ai_runtime.py` ناموفق ماندند و در اجرای جداگانه نیز بازتولید شدند: `test_failover_cooldown_skips_recently_failed_provider` به‌علت نبودن `_PROVIDER_FAIL_COOLDOWNS` در `giso.ai_runtime` (خط 209 تست)، و `test_superadmin_ai_setting_actions_and_user_delete` به‌علت دریافت `mode='message'` به‌جای `'pending'` (خط 432 تست). این‌ها خارج از محدودهٔ مجاز Buti AI هستند و هیچ کدی برای رفعشان تغییر نکرد. مجموعهٔ متمرکز پنل/provider registry بالا جداگانه **32/32 pass** شد.

### وضعیت واقعی خدمات در این بازاجرا

- **ابرو:** flow، mask، request schema و اعتبارسنجی خروجی با تست محلی پوشش داده شد؛ Vision و inpainting زنده در این نشست اجرا نشد.
- **لب:** recommendation/finalize، مالکیت و دانلود پوشش تستی دارند؛ تست close-up واقعی FaceMesh به‌علت نبود عکس skip شد؛ آزمون مدل زنده اجرا نشد.
- **ناخن:** تست‌های flow و fail-closed برای mask نامعتبر و مسیر mock اجرا شدند؛ این نتیجه readiness مدل زنده یا detector روی عکس کاربر را ثابت نمی‌کند.
- **رنگ مو:** تست‌های segmentation/gating و fail-closed اجرا شدند؛ آزمون‌های عکس واقعی skip شدند؛ مدل زنده تأیید نشد.
- **تصویر/PDF:** routeهای محافظت‌شده و تولید PDF در تست‌های backend pass شدند؛ smoke دانلود در مرورگر این نشست انجام نشد.
- **پنل:** تست‌های registry/readiness با DB موقت و mock pass شدند؛ این‌ها جای login سوپرادمین یا بررسی تنظیمات واقعی `/admin/ai` نیستند.

### تغییر این نشست و ادامهٔ امن

- هیچ فایل Python/JavaScript یا تنظیم provider تغییر نکرد؛ این بازاجرا فقط برای راستی‌آزمایی بود. تغییرات این نشست محدود به همین audit و دو فایل Project Memory است.
- برای تکمیل live-provider matrix، نشست مجاز پنل `/admin/ai` و یک عکس آزمایشی غیرحساس لازم است. تا آن زمان، وضعیت Vision/image generation واقعی و readiness پنل **تأییدنشده** می‌ماند؛ fallback محلی نباید AI واقعی معرفی شود.
- اگر credential فرستاده‌شده در پیام، دسترسی production دارد، پس از این کار آن را rotate کنید؛ این نشست از آن استفاده نکرده است.


## 9. ادامهٔ آزمون زندهٔ Cloudflare Vision — 2026-10-12، حدود 16:14 Asia/Tehran

### موافقت مدل و محدودهٔ آزمون

- کاربر payload دقیق `{"prompt":"agree"}` را برای مدل Vision پیش‌فرض تأیید کرد. مستند رسمی Cloudflare همین درخواست آغازین را برای پذیرش شرایط Meta مشخص می‌کند. پاسخ نخست HTTP 403 با کد 5016 بود، اما متن Cloudflare صریحاً می‌گفت شرایط پذیرفته شده و مدل اکنون قابل استفاده است؛ payload توافق دوباره ارسال نشد.
- برای آزمون، provider فقط در دیتابیس موقت `/tmp/giso4-admin-preview/giso/data/giso.db` تنظیم شد؛ هیچ تنظیم production یا پنل واقعی تغییر نکرد. پس از پایان آزمون، API key این DB پاک و provider غیرفعال شد. مقدار credential در این گزارش ذخیره نشده است.
- فقط مدل پیش‌فرض Vision پروژه، `@cf/meta/llama-3.2-11b-vision-instruct`، آزمایش شد. ورودی یک PNG کاملاً مصنوعی 256×256 شامل دو مستطیل قرمز و یک دایرهٔ سبز بود؛ عکس کاربر یا چهره ارسال نشد. فراخوانی از `giso.ai_brain.ask_ai_vision` انجام شد و زنجیرهٔ fallback به مدل دیگر بسته بود.
- آزمون زنده از مسیر برنامه موفق شد: `request_format=prompt_image_byte_array`، زمان حدود 4.53 ثانیه، و پاسخ تعداد دو مستطیل قرمز و یک دایرهٔ سبز را درست گزارش کرد. پاسخ جملهٔ توضیحی نیز داشت؛ بنابراین تضمین JSON خالص در این آزمون ثابت نشد و باید در prompt/flow واقعی ابرو و لب جداگانه بررسی شود.

### اصلاح لازم در اتصال Cloudflare

- درخواست قبلی پروژه `prompt` و `messages` را هم‌زمان همراه تصویر می‌فرستاد؛ endpoint واقعی آن را با HTTP 400 و خطای schema رد کرد.
- schema رسمی REST برای مدل، `prompt` و تصویر به‌صورت آرایهٔ byte را می‌پذیرد. همین schema با درخواست زنده موفق شد. parser پاسخ نیز پیش‌تر خروجی ساختاریافتهٔ فهرستی را نادیده می‌گرفت.
- اصلاح محدود در `giso/ai_brain.py` انجام شد: payload به `prompt + image byte array` تغییر کرد و parser فهرست‌های `result` را به JSON متن تبدیل می‌کند. تست قرارداد در `giso/tests/test_ai_cloudflare_vision.py` نیز به‌روزرسانی شد. این تغییر عمومی provider حداقلی و برای اتصال Cloudflare لازم بود؛ منطق محصول Buti AI به فایل‌های عمومی منتقل نشد.

### اعتبارسنجی و وضعیت فعلی

| بررسی | نتیجه |
| --- | --- |
| آزمون زندهٔ synthetic Vision از مسیر `ask_ai_vision` با مدل پیش‌فرض | موفق؛ پاسخ count مطابق تصویر مصنوعی |
| `pytest -q giso/tests/test_ai_cloudflare_vision.py` | 2 passed |
| `py_compile` برای `giso/ai_brain.py` و تست مربوط | موفق |
| `git diff --check` | موفق |
| مجموعهٔ مرتبط AI/provider و flowها با `SECRET_KEY` موقت | 55 passed، 2 failed، 36 warnings |

دو تست ناموفق همان موارد خارج از این اصلاح در `giso/tests/test_ai_runtime.py` هستند: `test_failover_cooldown_skips_recently_failed_provider` به‌علت نبودن `_PROVIDER_FAIL_COOLDOWNS` و `test_superadmin_ai_setting_actions_and_user_delete` به‌علت دریافت `mode='message'` به‌جای `pending`. سایر تست‌های انتخاب‌شده در همان اجرا pass شدند. هشدارهای `datetime.utcnow()` و Pyparsing در فایل‌ها/وابستگی‌های موجود مشاهده شدند و در این تغییر رفع نشدند.

### مواردی که همچنان تأیید نشده‌اند

- ورود احراز‌شده به پنل `/admin/ai` و وضعیت provider در production بررسی نشد؛ دیتابیس و provider این آزمون صرفاً محلی و موقت بودند.
- مسیر کامل ابرو/لب از upload، تحلیل واقعی با prompt محصول، تأیید، generation، دانلود تصویر و PDF در این مرحله اجرا نشد. خروجی مصنوعی Vision به‌تنهایی کیفیت آینه، mask یا flow محصول را ثابت نمی‌کند.
- خطای قبلی ابزار مرورگر هنگام smoke دانلود هنوز با این آزمون حل نشده است.
- هزینه/ledger، provider-attempt audit، charge، idempotency، quota، circuit breaker، رضایت صریح و queue/worker همچنان پیش‌نیازهای production هستند.
- API key فقط برای آزمون در دیتابیس موقت بود؛ پس از آزمون پاک و provider غیرفعال شد. چون credential در گفت‌وگو به اشتراک گذاشته شده، چرخاندن/تعویض آن توصیه می‌شود.

**وضعیت Git این مرحله:** تغییرات کد و تست در `giso/ai_brain.py` و `giso/tests/test_ai_cloudflare_vision.py` محلی و هنوز commit نشده‌اند. پنل و تنظیمات production دست‌نخورده مانده‌اند.


## 9. Stage 3 مراکز زیبایی — Booking Bridge — 2026-10-12

- صفحهٔ مرکز برای هر خدمت فعال و پشتیبانی‌شده، CTA «پیش‌نمایش روی عکس من» دارد. مسیر preview ورود کاربر را لازم دارد، خدمت را از inventory واقعی و فعال سالن می‌خواند و context مقصد را به‌صورت session-bound (شناسهٔ کاربر/مرکز/خدمت، مهلت یک‌ساعته) نگه می‌دارد.
- در صفحهٔ نتیجه، مقصد رزرو همان مرکز فقط پس از بازبینی وضعیت انتشار مرکز، فعال‌بودن service، تطابق service key با Mirror و مالکیت `final_design_id` نشان داده می‌شود. لینک رزرو شناسهٔ واقعی `service_id` و `final_design_id` را می‌فرستد.
- در `beauty_centers/reservations/routes.py`، کنترل سروری در GET و POST تضمین می‌کند طراحی متعلق به کاربر واردشده باشد و نوع طراحی با خدمت فعال همان مرکز تطابق داشته باشد؛ ورودی جعلی، طرح کاربر دیگر و خدمت ناسازگار fail-closed می‌شوند. مراکز پیشنهادی از inventory فعال همان خدمت استفاده می‌کنند.
- تصویر شخصی کاربر به مرکز نمایش داده/ارسال نمی‌شود؛ فقط شناسهٔ داخلی طرح و metadata خدمت/استایل به رزرو پیوند می‌خورد. فرم رزرو این محدودیت را صریح می‌گوید. رزروهای معمولی بدون `final_design_id` مسیر قدیمی را حفظ می‌کنند.
- فایل تست جدید: `giso/tests/test_beauty_center_reservation_booking_bridge.py`. `py_compile` موفق؛ regressions مرتبط (booking bridge، `test_buti_ai_phase1.py`، CTA، گالری و کارت‌های مرکز): **51 passed، 132 warnings**. هشدارهای عمده از `datetime.utcnow()` و Pillow `getdata()` موجود در کد/وابستگی است و در این Stage تغییر داده نشد.
- full-suite نخست به‌علت نبودن dependency `python-telegram-bot==20.7` هنگام collection متوقف شد؛ dependency مطابق requirements نصب شد و اجرای دوبارهٔ full-suite جداگانه در حال انجام است. نتیجه تا دریافت نهایی اعلام نمی‌شود.
- Stage 4 (Instagram) آغاز نشده است؛ ادامه فقط پس از تأیید کاربر.


## 9. گزارش Stage 5 — آمار هوشمند و تقاضای خدمات (2026-10-12، حدود 19:50 Asia/Tehran)

- صفحهٔ فهرست مراکز: چهار KPI قبلی حفظ شدند؛ یک نوار تقاضای ۳۰روزه پیش از فیلترها اضافه شد. کارت‌های خدمت از `beauty_center_services` فعالِ مراکز منتشرشده/فعال ساخته می‌شوند. گروه‌بندی با `service_key` جاری و در نبود آن با نام جاری خدمت است؛ بنابراین فهرست ثابت ابرو/لب/مو نیست و با تغییر inventory تغییر می‌کند.
- تعریف سیگنال تقاضا: بازشدن فرم رزرو برای `service_id` معتبر؛ با `booking_start` در `beauty_center_events` ثبت می‌شود. هر خدمت/مرکز در نشست مرورگرِ امضاشده فقط یک بار در روز شمرده می‌شود؛ بازدیدهای مالک حذف می‌شوند. رویداد جدید `user_id=0` دارد و فقط center/service/campaign را نگه می‌دارد.
- آمار رویداد با کاربر یکتا یکی نیست؛ `booking_start` رزرو قطعی یا فروش نیست. درخواست‌های واقعی جداگانه از جدول رزرو، بر اساس تاریخ ایجاد و وضعیت فعلی خوانده می‌شوند.
- بخش عمومی مقادیر دقیق تقاضا را زیر حداقل نمونه نشان نمی‌دهد. پیش‌فرض `BEAUTY_SERVICE_DEMAND_MIN_SAMPLE=5` است و مقدار از طریق environment به بازهٔ ۱ تا ۱۰۰ قابل تنظیم است. این آمار فقط از مراکز/خدمات فعال منتشرشده aggregate می‌شود؛ PII، عکس و `final_design_id` در query/رویداد عمومی حضور ندارند.
- داشبورد مالک: تب «آمار هوشمند»، بازه‌های ۷/۳۰/۹۰ روز؛ همهٔ queryها با `center_id` مرکز دریافت‌شده از حساب مالک محدودند. شمار بازدید، نمایش Mirror، تماس/قیمت/Instagram، شروع فرم و وضعیت‌های رزرو و breakdown خدمت نمایش داده می‌شود؛ service names از داده جاری می‌آیند.
- داشبورد سوپرادمین: گزارش aggregate ۳۰روزهٔ شهر/خدمت و تعداد مرکز ارائه‌دهنده.
- اعتبارسنجی هدفمند روی کد Stage 5 نهایی: **65 passed, 132 warnings**. `py_compile`، compile سه قالب public/owner/admin و Flask smoke روی `/beauty-centers` با **HTTP 200** موفق بود.
- sweep گستردهٔ `test_beauty_center*.py` و `test_beauty_centers*.py`: **77 passed, 12 failed**. شکست‌ها در تست‌های موجود lifecycle/media، قراردادهای ثابت UI/SEO/navigation و admin hooks دیده شدند؛ هیچ‌کدام از تست‌های جدید Stage 5 fail نشدند. بااین‌حال پیش از pilot باید شکست‌ها triage و در صورت لزوم baseline بررسی شوند. Full suite کل مخزن پس از Stage 5 اجرا نشده است.
- فایل‌های Stage 4–5 و memory updates local/uncommitted مانده‌اند؛ push انجام نشد. Stage 6 (مقایسهٔ قیمت) هنوز شروع نشده و نیازمند تأیید کاربر است.

### بازبینی نمایشی و نتیجهٔ regression نهایی — 2026-10-12، حدود 20:02

صفحهٔ `/beauty-centers` با Flask test client دوباره رندر شد: status 200، هر چهار KPI قدیمی حاضر، و بخش تقاضا نیز در محیط فعلی بدون خدمت فعال به‌همراه empty-state واضح نمایش داده می‌شود. قالب‌های public، owner و admin هم compile شدند. نسخهٔ نهایی تست هدفمند **70 passed، 132 warnings** است. sweep گستردهٔ مراکز **80 passed، 10 failed**؛ شکست‌ها باقی‌ماندهٔ expectationهای Stage 7/10/12/13/14 و admin-bot هستند و در تست‌های Stage 5/booking bridge/gallery/CTA/Instagram fail دیده نشد. یک شکست media از fixtureی ناشی بود که مسیر تصویر می‌داد ولی فایل نمی‌ساخت؛ fixture اکنون تصویر موقت واقعی ایجاد و پاک می‌کند. یک assertion CSRF نیز اصلاح شد تا فقط فرم‌های POST را الزام کند و CSRF token را در URL فرم GET فیلتر قرار ندهد.

### انتشار Stage 4–5

درخواست کاربر برای ارسال همهٔ تغییرات اجرا شد: commit `e5512dc` با عنوان `Complete beauty center stages 4-5 analytics` به شاخهٔ `arena/7f567e47-giso4` push شد. بررسی پس از push تأیید کرد HEAD محلی و remote هر دو `e5512dc` هستند و working tree پاک است. Stage 6 آغاز نشده و منتظر تأیید بعدی است.
