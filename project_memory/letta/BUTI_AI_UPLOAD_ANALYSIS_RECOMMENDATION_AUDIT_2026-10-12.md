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
