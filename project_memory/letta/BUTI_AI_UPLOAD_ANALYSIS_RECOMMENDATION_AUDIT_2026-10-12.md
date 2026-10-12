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
