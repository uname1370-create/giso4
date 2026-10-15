# ممیزی و طراحی سناریوی مدیریت هوشمند مدل‌های AI در گیسو ۴

| | |
|---|---|
| **تاریخ** | 2026-10-15 (Asia/Tehran) |
| **مخزن / شاخه** | `uname1370-create/giso4` / `arena/7f567e47-giso4` |
| **کامیت مبنای بررسی** | `837b917` (کد). کامیت فعلی شاخه `8d5ea03` فقط افزودن `rep.md` است و کد را تغییر نداده است. |
| **نوع کار** | فقط‌خواندنی. هیچ کد، فایل، دیتابیس، تنظیمات، شاخه یا کامیتی تغییر نکرده است. |
| **منبع حقیقت** | سورس همین کامیت. `rep.md`، گراف Graphify و مستندات قدیمی مبنا نبوده‌اند. |

> **یادداشت شماره خطوط:** شماره خطوطی که در این مرحله با جستجوی مستقیم تأیید شدند، با برچسب «[کد تأیید شد]» آمده‌اند. شماره‌هایی که تأیید نشده‌اند با «~» مشخص شده یا حذف شده‌اند. هر شماره‌ای که در بازبینی بعدی ناهم‌خوان بود، ملاک قضاوت نیست؛ نماد و فایل ملاک است.

## برچسب‌ها

| برچسب | معنی |
|---|---|
| **[کد تأیید شد]** | در سورس `837b917` خوانده شده و فایل، نماد و شماره خط مشخص است |
| **[ریسک]** | از روی کد استنباط شده؛ در اجرای واقعی بازتولید نشده |
| **[نیاز به تست اجرایی]** | فقط با اجرا (داده، شبکه، مدل زنده) قابل قضاوت است |
| **[شواهد ناکافی]** | در این ممیزی کافی بررسی نشده یا شاهدی برای قضاوت نیست |

## محدودیت‌های این ممیزی (مهم)

- **هیچ تستی اجرا نشد.** در این ممیزی هیچ محیط تست یا وابستگی جدیدی نصب نشد (طبق قاعدهٔ «نصب نکن مگر با تأیید»)؛ `flask` و `jinja2` در Python سیستم در دسترس نبودند. فهرست تست‌ها فقط با خواندن کد بررسی شده است.
- **دیتابیس زنده در دسترس نیست.** `giso/data/giso.db` در workspace وجود ندارد (پس از ریست قبلی). وضعیت ردیف‌های `giso_ai_providers` و `buti_ai_model_assignments` در سرور زنده **تأیید نشده** است.
- **هیچ تماس بیرونی با Providerها انجام نشد.** شبکه sandbox فقط به GitHub، npm و PyPI دسترسی دارد. هر ادعای مربوط به API خارجی (از جمله اینکه کدام Provider چه فیلدی برمی‌گرداند) فقط «در کد فرض شده» است، نه «در مستند یا پاسخ زنده تأیید شده».

---

## A. خلاصه اجرایی

**وضعیت فعلی:** مدیریت AI در گیسو ۴ کار می‌کند و بخش زیادی از ایمنی لازم را دارد (Providerهای غیرفعال اجرا نمی‌شوند، مدل‌های حذف‌شده پاک نمی‌شوند، fallback تصویر صادقانه برچسب می‌خورد). اما برای سناریوی چهاربخشی، **منبع واحد قابلیت مدل وجود ندارد** و سه مشکل ساختاری قبل از هر تغییر UI باید حل شوند:

1. **قابلیت مدل از چند منبع ناهمگون می‌آید** و بیشتر آن‌ها نام‌محور است: فهرست ثابت رجیستری، کلیدواژه‌های `image` و `vision` و `gemini` و غیره، و در یک مورد فیلد `architecture.input_modalities` در پاسخ OpenRouter. رجیستری فقط سه فهرست (`vision_models`، `text_models`، `image_models`) دارد و هیچ فیلد ورودی/خروجی، ماسک یا inpainting برای مدل‌ها ندارد. **[کد تأیید شد]**
2. **رایگان بودن یک برچسب است، نه وضعیت بررسی‌شده.** `is_free` در رجیستری برای تمام مدل‌های لیست تمیز `True` ثابت است. در کشف، یک Provider کامل (groq، mistral، cloudflare، openrouter) وقتی پاسخ `/models` قیمت نداشته باشد «رایگان» فرض می‌شود، و در مسیر 429 هر Provider غیرایرانی «رایگان» در نظر گرفته می‌شود. **[کد تأیید شد]**
3. **چند مسیر در زمان خواندن یا کشف، تنظیمات مدیر را تغییر می‌دهند:**
   - `selected_model` در کشف گروهی و در راه‌اندازی مجدد، اگر مدل قبلی در فهرست نباشد، بی‌صدا عوض می‌شود. **[کد تأیید شد]**
   - مدل‌هایی که در `/models` نیستند، در کشف تکی `disabled` می‌شوند (تفکیک مدل دستی/JSON از کشف‌شده در این ممیزی تأیید نشد). **[کد تأیید شد]**
   - `repair_legacy_cloudflare_eyebrow_image_slots` در سه مسیر **خواندن** (صفحه پنل، انتخاب Providerهای تصویر، و آمادگی) اجرا می‌شود و داده را می‌نویسد. **[کد تأیید شد]**
   - افزودن Provider با نام `cloudflare` یا `cf1..cf3` اسلات‌های آینه را با `overwrite=True` بازنویسی می‌کند. **[کد تأیید شد]**

**مهم‌ترین ریسک‌های اجرایی (نه فقط UI):**

- مسیرهای آینه (`validate-photo`، `final`، `final/retry`) بدون اعتبار سهمیه و بدون rate limit هستند. **[کد تأیید شد]**
- در ابرو، هر خطای انتقال روی Provider تصویر دو بار تکرار می‌شود. **[کد تأیید شد]**
- اسلات `mirror_output_validation` پر می‌شود ولی هیچ مصرف‌کنندهٔ runtime ندارد. **[کد تأیید شد]**
- دو کش شکست جدا (کولداون درون‌حافظه‌ای ۱۲۰ ثانیه و کولداون DB پنج دقیقه‌ای) وجود دارد. **[کد تأیید شد]**

**آمادگی برای سناریوی چهاربخشی:** مدل‌های متنی و Providerهای فعال/غیرفعال تا حد خوبی آماده‌اند. تشخیص قابلیت، رایگان بودن و انتخاب امن مدل آینه آماده نیستند. هیچ بخشی از سناریو بدون تغییر ساختار قابل اجرا نیست، ولی تغییرات می‌توانند کم‌خطر و مرحله‌ای باشند (بخش G).

**تصمیم نهایی (بخش J):** نیازمند اصلاح معماری محدود، پیش از پیاده‌سازی.

---

## B. نقشهٔ واقعی معماری

### B.۱ فایل‌ها و نقش آن‌ها

| فایل | خطوط تقریبی | نقش | وضعیت |
|---|---|---|---|
| `giso/ai_models_registry.py` | ۳۳۴ خط؛ `PROVIDERS = {` در خط ۲۱ | فهرست ثابت ۷ Provider و مدل‌های هر Provider. `PROVIDERS_REGISTRY` در `ai_brain` (۵۵۵) از `_legacy_registry` ساخته می‌شود | [کد تأیید شد] |
| `giso/ai_discovery.py` | ۳۶۰ خط | کشف گروهی: `smart_filter_models` (۱۷۵)، `discover_provider` (۲۳۲)، `refresh_all_models_async` (۳۲۸)، ثابت‌های `KNOWN_FREE_PROVIDERS` (۳۱) و `MAX_VISION_MODELS`/`MAX_TEXT_MODELS` (۴۴–۴۵) | [کد تأیید شد] |
| `giso/ai_brain.py` | — | ذخیره Provider (`add_ai_provider` ۲۵۱)، حذف (`delete_ai_provider` ۳۲۴)، `refresh_models` (۹۵۶)، `ask_ai` (۱۳۳۱)، `ask_ai_vision` (۱۵۷۰)، seed و راه‌اندازی (`_normalize_existing_provider_names` ۱۱۲۱، `_backfill_registry_models` ۱۱۶۰، `RETIRED_PROVIDERS` ۱۲۲۳، `seed_registry_providers` ۱۲۸۲)، `save_provider_to_env` (۱۸۶۶) | [کد تأیید شد] |
| `giso/ai_runtime.py` | ۳۵۵۸ خط | زنجیره failover، `chat_with_failover` (۱۰۱۰)، `_ask_single_provider` (۹۷۷)، `list_provider_options` (۵۴۸) | [کد تأیید شد] |
| `giso/ai_runtime_policy.py` | ۳۹۰ خط | ثابت‌های سیاست، کولداون درون‌حافظه‌ای (۱۶–۲۱۴)، سیاست نقش | [کد تأیید شد] |
| `giso/ai_health.py` | — | جدول سلامت DB به ازای (provider, model) (`mark_failure` ۶۹)؛ `is_in_cooldown` (۹۸)؛ `get_provider_is_free` (۱۴۹) | [کد تأیید شد] |
| `giso/ai_config.py` | — | ثابت‌های زمان و پرچم `FEATURE_FLAG_LEGACY_MODE` (مقدار و خط دقیق در این ممیزی تأیید نشد) | [کد تأیید شد] |
| `giso/buti_ai/ai_models.py` | — | اسلات‌های آینه: `TASK_DEFS` (۴۵)، `SERVICE_IMAGE_TASK_MAP` (۶۹)، `init_buti_ai_model_assignments` (۲۵۲)، `_cloudflare_slot_priority` (۱۲۸)، `_migrate_legacy_image_design_assignments` (۱۶۴)، `save_model_assignment` (۲۹۵)، `provider_model_options` (۴۱۹)، `panel_slots_context` (۴۶۶)، `configured_vision_chain` (۵۰۵)، `repair_legacy_cloudflare_eyebrow_image_slots` (۵۵۳)، `configured_image_provider_dicts` (۶۲۳)، `readiness_status` (۶۸۰)، `auto_configure_for_provider` (۸۷۱) | [کد تأیید شد] |
| `giso/panel/modules/ai.py` | — | handlerهای پنل: `handle_provider_add` (۲۱۶)، `handle_refresh_models` (۵۵۳)، `handle_refresh_all_models` (۶۴۰)، `context` (۷۵۶)، `handle_custom_model_add` (۸۹۳) | [کد تأیید شد] |
| `giso/panel/routes.py` | — | مسیر ویرایش AI (حدود ۱۵۴۲ طبق یادداشت قبلی؛ تأیید دقیق نشد) | [کد تأیید شد] |
| `giso/panel/templates/modules/ai.html` | — | کارت Provider، کشویی مدل از `discovered_models` (۱۹۴–۲۰۰)، فرم اسلات آینه با datalist (حدود ۳۸۷) | [کد تأیید شد] |
| `giso/analysis.py` | — | تحلیل عمومی عکس: `pick_active_vision_model` (۲۳۴)، `call_vision_with_fallback` (۴۰۲)، `check_rate_limit` (۷۷۰) | [کد تأیید شد] |
| `giso/buti_ai/eyebrow/ai.py` | — | تحلیل عکس ابرو: `_call_vision_json` با زنجیره اسلات‌ها و fallback عمومی | [کد تأیید شد] |
| `giso/buti_ai/eyebrow/image_generation.py` | — | ارائه‌دهندهٔ مشترک تصویر: `configured_image_providers` (۳۶۴)، `generate_final_design` (۱۵۷۲) | [کد تأیید شد] |
| `giso/buti_ai/service_image_generation.py` | ۶۳۶ خط | لب/ناخن/مو: `generate_final_design` (۵۴۳)، محدودیت‌ها `SERVICE_CONSTRAINTS` (۲۸–۶۶) | [کد تأیید شد] |
| `giso/ai_credits.py` | — | اعتبار AI برای ویجت سایت (`reserve_ai_credit`، `refund_ai_credit`) | [کد تأیید شد] |
| `giso/security.py` | — | `security_gate`: CSRF برای POST و rate limit برای مسیرهای مشخص | [کد تأیید شد] |
| `giso/base.py` | ۳۴۰–۳۴۸ | راه‌اندازی DB: `sync_env_providers_to_db` (۳۴۰) و `seed_registry_providers` (۳۴۷) | [کد تأیید شد] |
| `giso/bot.py` | ۱۴۸۰، ۱۷۲۷، ۱۷۸۹ | ربات: refresh-all (۱۴۸۰)، افزودن Provider و `auto_configure` (۱۷۲۷، ۱۷۸۹) | [کد تأیید شد] |
| `bot_edu/config.py` | — | فهرست پیش‌فرض جداگانه (Groq، OpenRouter، LLM7، Cloudflare) و `DB_PATH` پیش‌فرض `data/bot.db` | [کد تأیید شد] (وجود فهرست و `data/bot.db`)، جزئیات خط [شواهد ناکافی] |
| `web/web_ai/*`، `bot_edu/ai_mentor/*`، `bot_edu/ai_brain.py` | — | پشتهٔ موازی. `web/` هیچ import از `giso` ندارد. **اما `bot_edu/` دارد:** `bot_edu/bot.py`، `db.py`، `giso_admin.py`، `giso_handlers.py`، `handlers.py`، `sync_giso_admins.py` از `giso` import می‌کنند. بنابراین `bot_edu` «کاملاً جدا» نیست. | [کد تأیید شد] (فهرست import)؛ رفتار AI آن‌ها [شواهد ناکافی] |

### B.۲ جداول دیتابیس

**`giso_ai_providers`** (ساخت در `ai_brain.py` ۳۴–۵۴؛ ستون‌های افزوده با ALTER در ۸۶–۹۴)

| ستون | کاربرد | منبع |
|---|---|---|
| `name` (UNIQUE)، `kind`، `enabled`، `api_key`، `base_url`، `api_root`، `timeout` | هویت و اتصال Provider | ۳۴–۵۴ |
| `headers_json`، `fallback_json`، `models_json`، `selected_model` | فهرست‌های عمومی و مدل انتخابی | ۳۴–۵۴ |
| `is_iranian`، `use_proxy`، `last_status`، `last_error`، `last_checked_at` | وضعیت و پروکسی | ۳۴–۵۴ و ALTER |
| `vision_models_json`، `text_models_json`، `models_last_updated`، `models_source`، `discovery_report` | فهرست‌های کشف‌شده؛ `models_source` (مقادیر دیده‌شده در کد شامل `registry`؛ فهرست کامل تأیید نشد) | ALTER (۸۶–۹۴، `ai_discovery.py` ۳۰۴) و `ai_brain.py` ۹۹۸، ۱۰۰۷، ۱۰۳۳، ۱۰۷۶، ۱۱۰۷ |
| `giso_ai_provider_tombstones` | حذف صریح مدیر؛ seed دوباره آن را برنمی‌گرداند | `ai_brain.py` ۶۶، ۳۲۴ (`delete_ai_provider`)، ۲۲۱ (`_provider_tombstone_names`) |
| `giso_ai_health` | جدول سلامت به‌ازای (provider, model) | `ai_brain.py` ۹۹؛ `ai_health.py` |

**`buti_ai_model_assignments`** (`ai_models.py` ۷۶–۹۲)
- `task_key`، `priority` (UNIQUE با task_key)، `provider_name`، `model_name`، `enabled`، `image_kind`، `endpoint_override`، `created_at`، `updated_at`.
- مهاجرت افزودنی در `init_buti_ai_model_assignments` (۲۵۲).

**جداول اعتبار و ledger:** `giso_ai_credit_accounts` و `giso_ai_credit_ledger` (`ai_credits.py` ۱۶ و ۲۲). فقط ویجت سایت از آن استفاده می‌کند. **[کد تأیید شد]**

### B.۳ مسیر کامل: کشف تا انتخاب تا اجرا

```text
[ثبت Provider]  panel/modules/ai.py::handle_provider_add (216)
  → ai_brain.add_ai_provider (251)            [upsert، ۲۸۷–۳۰۰]
  → ai_brain.refresh_models (956) via (handler ۳۴۰)   [/models، فقط فهرست]
  → first_discovered_model / set_provider_selected_model
  → buti_ai.auto_configure_for_provider (871) [اسلات آینه، overwrite برای cloudflare/cf*]

[کشف گروهی]  handle_refresh_all_models (640) یا bot.py (1480)
  → ai_discovery.refresh_all_models_async (328)
  → discover_provider (232): fetch → smart_filter_models (175) → merge → UPDATE
     (`selected_model` اگر مدل قبلی در فهرست نباشد عوض می‌شود)

[راه‌اندازی هر بار]  base.py (340–348)
  → sync_env_providers_to_db (1806)           [فقط اگر DB خالی باشد]
  → seed_registry_providers (1282)
       → _normalize_existing_provider_names (1121)
       → _refresh_registry_sourced_models (1226) [برای groq/openrouter/mistral/cloudflare؛ selected را عوض می‌کند]
       → _backfill_registry_models (1160)      [فقط ستون‌های خالی]
       → افزودن ردیف‌های جدید رجیستری با enabled=False (ai_brain ۱۲۸۲–۱۳۰۰ تقریباً)
       → RETIRED_PROVIDERS (۱۲۲۳) enabled=0

[اجرای چت]  app.py (765) → chat_with_managed_ai (1118) → chat_with_failover (1010)
  → _build_provider_attempt_chain → _apply_provider_cooldown (ai_runtime_policy)
  → ai_health.is_in_cooldown (98)
  → _ask_single_provider (977): selected_model از ردیف → ask_ai (1331)

[اجرای تحلیل عکس ابرو]  eyebrow/ai.py::_call_vision_json (62)
  → configured_vision_chain (ai_models 505)   [اسلات eyebrow_analysis، enabled + provider enabled]
  → در شکست یا global_fallback: analysis.call_vision_with_fallback (402)
     → pick_active_vision_model (234) → list_ai_providers(only_enabled) + رجیستری (analysis 210)

[اجرای تصویر ابرو/لب/ناخن/مو]  eyebrow/image_generation.py::generate_final_design (1572)
  → configured_image_providers (364) → _ai_management_providers (332)
  → configured_image_provider_dicts (ai_models 623) [اسلات mirror_image_design]
  → provider_sequence (inpainting دوبار، ~۱۶۱۶–۱۶۲۳ تقریبی) → _call_provider → _save_provider_output
  → شکست: مسیر ساخت غیرAI با نشانگر is_ai_generated=False (نام تابع دقیق تأیید نشد)
```

**[کد تأیید شد]** — نکتهٔ ساختاری: حداقل دو سازوکار کولداون جدا وجود دارد: کولداون درون‌حافظه‌ای (`ai_runtime_policy.py` ۱۴–۱۶، ۱۲۰ ثانیه) و جدول DB (`ai_health.is_in_cooldown` ۹۸). مسیر تحلیل عمومی (`analysis.py`) کولداون خودش را دارد (`_provider_in_cooldown` در فایل دیگری). **[ریسک]** / مدت کولداون DB در این ممیزی تأیید نشد.

---

## C. جدول وضعیت موجود

| قابلیت | محل فعلی پیاده‌سازی | وضعیت واقعی | نقص اثبات‌شده | اقدام پیشنهادی |
|---|---|---|---|---|
| **رجیستری مدل‌ها** | `ai_models_registry.py` `PROVIDERS` (۲۲–۱۶۵)؛ `get_*_models` (۲۳۲–۲۶۰) | موجود برای ۷ Provider؛ فقط فهرست‌های `vision`، `text`، `image` با `id`، `is_free`، `context`، `source`؛ فیلد `capabilities` فقط روی یک مدل تصویر (`stable-diffusion-v1-5-inpainting`) | نداشتن فیلدهای ورودی/خروجی، ماسک و inpainting. `MODALITY_*` (۱۲–۱۴) تعریف شده ولی مصرف‌کننده ندارد (grep). `MODALITY_BOTH` و `SOURCE_MANUAL_JSON` بدون مصرف. **[کد تأیید شد]** | افزودن فیلد قابلیت به هر مدل (داده، نه رفتار) و استفاده از همان فیلدها در تمام مسیرها |
| **کشف خودکار** | `ai_discovery.discover_provider` (۲۳۲)؛ `ai_brain.refresh_models` (۹۵۶)؛ `refresh_all_models_async` (۳۲۸) | دو پیاده‌سازی موازی: `refresh_models` (تکی، از پنل) فقط با کلیدواژهٔ `_is_vision_model_id`؛ `discover_provider` (گروهی، از پنل و ربات) با فیلتر کامل. **[کد تأیید شد]** | دو منطق مختلف برای یک کار. `refresh_models` مدل‌های مدیریتی و `pricing` را در نظر نمی‌گیرد و فیلتر رایگان/بینایی ندارد. | یک مسیر کشف واحد با خروجی یکسان |
| **منبع فهرست `/models`** | `_fetch_remote_models` (۹۰۹) با `GET {base}/models` و Bearer؛ `_effective_base_url` برای Gemini | از منبع بیرونی برای Providerهای `kind=openai` و کلیددار (شامل gapgpt، avalai و custom). **Cloudflare** از رجیستری (`refresh_models`؛ `DISCOVERY_SKIP_PROVIDERS` در `ai_discovery` ۲۷). **[کد تأیید شد]** | Gemini از مسیر worker است (`PROVIDER_PLAYBOOK` در `ai_discovery`، و `_effective_base_url`)؛ رفتار زنده [نیاز به تست اجرایی] |
| **تشخیص قابلیت** | `_is_vision_model_id` (۸۸۲) با کلیدواژه‌های `_DYNAMIC_VISION_KEYWORDS` (۸۶۹)؛ `_ai_is_likely_vision_model` (۱۴۲۸) با فهرست جدا؛ `_item_has_vision` (ai_discovery ۱۰۳) که اول `architecture.input_modalities`، `modality`، `capabilities.vision` را می‌بیند | کلیدواژه‌ای. تنها مسیر غیرنامی: فیلد `architecture.input_modalities` در پاسخ OpenRouter (به‌صورت کد، نه تست زنده). **[کد تأیید شد]** | دو فهرست کلیدواژه با هم فرق دارند. کلیدواژهٔ عمومی `image` و `omni` در فهرست بینایی `_is_vision_model_id` هست؛ اگر مدل تولید تصویری با این کلیدواژه‌ها نام‌گذاری شود و فیلتر منفی (`_DYNAMIC_NON_VISION_KEYWORDS`) آن را نگیرد، بینایی شناخته می‌شود. **[ریسک] / [نیاز به تست اجرایی]**. `_ai_is_likely_vision_model` با `gemini` هر مدل Gemini را بینایی حساب می‌کند (فقط مدل‌های تصویرساز را حذف می‌کند) **[ریسک]**. | یک طبقه‌بند واحد با منبع ثبت‌شده برای هر برچسب (بخش F) |
| **تشخیص رایگان بودن** | `_item_is_free` (ai_discovery ۸۵)؛ `_model_is_free` (ai_brain ۸۹۵)؛ `get_provider_is_free` (ai_health ۱۴۹)؛ `is_free` ثابت در رجیستری | ترکیبی: پسوند `:free`، صفر بودن قیمت در پاسخ، و در غیاب قیمت، **نام Provider** در `KNOWN_FREE_PROVIDERS` (ai_discovery ۳۱، شامل openrouter، groq، mistral، cloudflare). `get_provider_is_free` = `not is_iranian` از رجیستری، و اگر ناشناخته باشد `True`. `is_free` رجیستری ثابت `True` است. **[کد تأیید شد]** | رایگان بودن بدون منبع معتبر پذیرفته می‌شود. `smart_filter_models` (۱۷۵) وقتی مدل رایگان یافت شود مدل‌های پولی را حذف می‌کند. `analysis.py` ۴۹۸ از `get_provider_is_free` برای تصمیم backoff بعد از 429 استفاده می‌کند؛ یعنی Provider غیرایرانی «رایگان» تلقی می‌شود. **[ریسک]** |
| **چهار بخش مدیریتی (متنی، تولید تصویر، تحلیل تصویر، سناریوهای آینه)** | پنل `ai.html` کارت Provider و بخش «مدل‌های آینه گیسو» | دو بخش موجود: کارت‌های Provider با کشویی `discovered_models` (فهرست مخلوط بینایی و متنی بدون فیلتر وظیفه) و فرم اسلات آینه. چهار بخش جداگانه وجود ندارد. **[کد تأیید شد]** | کشویی Provider فیلتر وظیفه ندارد. کشویی Provider در فرم اسلات (۳۸۷) همهٔ Providerها را نشان می‌دهد. مدل در اسلات با ورودی آزاد و datalist (۳۹۳) وارد می‌شود. **[کد تأیید شد]** | بخش D و E |
| **انتخاب و ذخیرهٔ مدل** | چت: `giso_ai_providers.selected_model`؛ آینه: `save_model_assignment` (۲۹۵) | چت: یک مدل به ازای Provider؛ fallback بین مدل‌ها وجود ندارد و fallback بین Providerها از `failover_chain` است. آینه: اسلات با `(task_key, priority)`. **[کد تأیید شد]** | `save_model_assignment` فقط نام Provider و مدل را غیرخالی می‌بیند؛ Provider وجود داشته باشد، فعال باشد یا قابلیت داشته باشد بررسی نمی‌شود. **[کد تأیید شد]** | بررسی در لحظهٔ ذخیره و در readiness |
| **فیلتر مدل غیرفعال** | `disabled` در فهرست JSON؛ `_merge_discovered` (۹۳۳) تنها نویسندهٔ آن است. فیلتر در `context()` و `first_discovered_model` (ai_brain) برای مدل‌های فهرست | در فهرست‌ها: بله (بخشی). در `provider_model_options` (۴۱۹): **تأیید نشد که `enabled` یا `disabled` را فیلتر می‌کند؛ کد خواننده نشان می‌دهد که نمی‌کند** [کد تأیید شد، بر اساس خواندن قبلی]. | `provider_model_options` ممکن است مدل Provider غیرفعال را نشان دهد (ریسک انتخاب اشتباه). **هیچ مسیر پنلی برای غیرفعال‌کردن دستی یک مدل دیده نشد** (grep روی routes و handlers). **[کد تأیید شد]** | افزودن فیلد `admin_enabled` جدا از `disabled` کشف |
| **سناریوهای آینه گیسو** | `TASK_DEFS` (ai_models ۴۵–۶۰)؛ `SERVICE_IMAGE_TASK_MAP` (۶۹) | چهار خدمت یک زنجیرهٔ تصویر دارند (`mirror_image_design`). تحلیل عکس یک زنجیره دارد (`eyebrow_analysis`). `mirror_output_validation` تعریف شده ولی مصرف runtime ندارد. **[کد تأیید شد]** | چهار کلید قدیمی هنوز در `LEGACY_IMAGE_DESIGN_TASK_KEYS` (۲۷–۳۲) هستند و `migrate` (۱۶۴–۲۵۰) آن‌ها را **کپی** می‌کند و حذف نمی‌کند. **[کد تأیید شد]** | بخش H و J |

---

## D. نقشهٔ مصرف مدل‌ها

| مصرف‌کننده | Provider از کجا | مدل از کجا | fallback | وابستگی مشترک | برچسب |
|---|---|---|---|---|---|
| **چت سایت (ویجت)** (`app.py` ۷۶۵ → `chat_with_managed_ai` ۱۱۱۸ → `chat_with_failover` ۱۰۱۰) | زنجیره Providerهای فعال (`get_failover_chain`)؛ اول `preferred`، سپس `active`، سپس زنجیره | `selected_model` ردیف (`_ask_single_provider` ۹۷۷) | بین Providerها؛ بین مدل‌ها **ندارد** | `ai_health`، کولداون درون‌حافظه‌ای، بودجه‌های زمانی در `ai_config` (مقدار دقیق تأیید نشد) | [کد تأیید شد] (ساختار)، مقادیر [شواهد ناکافی] |
| **اعتبار ویجت** (`ai_credits`) | — | — | — | فقط ویجت؛ بقیهٔ مسیرهای AI آینه بدون اعتبار | [کد تأیید شد] |
| **تحلیل عکس عمومی** (`analysis.py` ۴۰۲) | `pick_active_vision_model` (۲۳۴): Providerهای فعال + رجیستری (حدود ۲۱۰) | فهرست `vision_models` به ترتیب | ترتیب فهرست با بودجه زمانی (طبق docstring) | `check_rate_limit` (۷۷۰) | [کد تأیید شد] |
| **تحلیل عکس ابرو** (`eyebrow/ai.py`) | `configured_vision_chain` (ai_models ۵۰۵): اسلات `eyebrow_analysis` + Provider فعال | مدل اسلات | در شکست یا `global_fallback=True`: `call_vision_with_fallback` (analysis ۴۰۲) | **دو منبع مستقل** برای یک کار (R8 در `rep.md`) | [کد تأیید شد] |
| **کیفیت عکس ابرو** (`eyebrow/ai.py`) | مثل بالا با `global_fallback=True` | مثل بالا | مثل بالا | مثل بالا | [کد تأیید شد] |
| **تولید تصویر ابرو** (`eyebrow/image_generation.py` ۱۵۷۲) | `configured_image_providers` (۳۶۴) ← `_ai_management_providers` (۳۳۲) ← `configured_image_provider_dicts` (ai_models ۶۲۳) | اسلات `mirror_image_design` | **inpainting دوبار** (تقریباً ۱۶۱۶–۱۶۲۳)؛ سپس ساخت غیر AI | `repair_legacy...` (ai_models ۶۳۱) در هر فراخوانی | [کد تأیید شد] (جز شمارهٔ تقریبی حلقه) |
| **تصویر لب، ناخن، مو** (`service_image_generation.py` ۵۴۳) | `shared_image` = ماژول ابرو (خط ۱۶) | اسلات `mirror_image_design` | ساخت غیر AI در صورت شکست | **وابستگی به ماژول ابرو** | [کد تأیید شد] |
| **اعتبارسنجی خروجی** | — | اسلات `mirror_output_validation` (تعریف ۳۳، ۶۰) | — | فقط `readiness_status` (۷۳۶) | [کد تأیید شد] |
| **ربات** (`bot.py` ۱۴۸۰، ۱۷۲۷، ۱۷۸۹) | `save_provider_to_env` و `auto_configure_for_provider` | مثل پنل | — | `.env` (شامل کلید) | [کد تأیید شد] |
| **سایر مصرف‌کننده‌ها** (`special_assistant`، `super_assistant`، `analysis_final_override`، `monitoring_ai`، `seo_jobs`، `channel_importer`، `hair_sale`، `shop/logic/enricher`، `gemini_proxy_manager`) | از جستجوی نام تابع `ask_ai` و مشابه | — | — | — | [شواهد ناکافی] (فقط جستجوی نام، نه خواندن کامل) |
| **پشتهٔ موازی** (`bot_edu`، `web/web_ai`) | `bot_edu/config.py` با فهرست خودش | خودش | — | DB جدا (`data/bot.db`)؛ **ولی `bot_edu` از `giso` import می‌کند** (بخش B.۱) | [کد تأیید شد] (import و فهرست)، رفتار [شواهد ناکافی] |

**نقاط با تأثیر چندخدماتی (اگر تغییر کنند، همه تحت تأثیرند):**

1. `ai_brain.get_ai_provider` و `list_ai_providers`: همه مصرف‌کننده‌ها به آن‌ها وابسته‌اند.
2. `_is_vision_model_id` (۸۸۲): کشف، `refresh_models` و (از طریق `ai_discovery._item_has_vision`) کشف گروهی.
3. `configured_image_provider_dicts` (ai_models ۶۲۳): تمام تصویرسازی آینه.
4. `configured_vision_chain` (ai_models ۵۰۵): تحلیل عکس ابرو.
5. `get_provider_is_free` (ai_health ۱۴۹): ۴۹۸ `analysis.py` و `backoff`.
6. ماژول ابرو به‌عنوان `shared_image` (service_image_generation ۱۶): لب، ناخن، مو.

---

## E. طراحی پیشنهادی پنل

### E.۱ ساختار چهار بخش (نماهای روی یک منبع)

منبع واحد: **کاتالوگ مدل** = رکوردهای `giso_ai_providers` (فهرست‌های JSON) + رجیستری + اسلات‌های `buti_ai_model_assignments`. هیچ بخش جدید ذخیره‌سازی ندارد.

| بخش | نمایش پیش‌فرض | فیلتر (فقط مدل‌هایی که...) | ذخیره در | برچسب وضعیت |
|---|---|---|---|---|
| **۱. مدل‌های متنی** | مدل اصلی، fallbackها، ترتیب اولویت | دارای `text_out`، Provider فعال، `admin_enabled` | `giso_ai_providers.selected_model` و ترتیب `fallback_json` | آماده / نیازمند بررسی / غیرفعال |
| **۲. تولید تصویر** | اسلات‌های `mirror_image_design` (۱ تا ۳) | دارای `image_out`؛ برای مسیر آینه، با پشتیبانی واقعی از ماسک/ورودی تصویر | `buti_ai_model_assignments` (`mirror_image_design`) | آماده برای طراحی نهایی / فقط برای مدل‌های سازگار |
| **۳. تحلیل تصویر** | اسلات `eyebrow_analysis` و fallback عمومی | دارای `image_in`، نه فقط متن | `buti_ai_model_assignments` (`eyebrow_analysis`) | آماده / نیازمند بررسی |
| **۴. سناریوهای آینه** | نگاشت وظیفه → زنجیره (تحلیل، طراحی، اعتبارسنجی در صورت پشتیبانی) | — | همان اسلات‌ها | وضعیت هر وظیفه |

### E.۲ قوانین رفتار

- **Provider غیرفعال یا حذف‌شده** در کشویی‌ها و در اجرا نمایش داده نشود. تنظیمات قبلی حفظ شوند (`enabled=0` و tombstone). **[کد تأیید شد]** که اجرا رد می‌شود؛ **[کد تأیید نشده]** که کشویی‌ها فیلتر می‌شوند (`provider_model_options`).
- **مدل تازه‌کشف‌شده** با وضعیت `needs_review` اضافه شود، نه فعال. `selected_model` عوض نشود.
- **مدل ناقص یا نامطمئن** وضعیت `نیازمند بررسی` بگیرد، نه اینکه با حدس در یک دسته قرار گیرد.
- **به‌روزرسانی فهرست** `admin_enabled` و اسلات‌های دستی را لمس نکند.
- **مدل ناسازگار** در مسیر اجرایی (چت، تحلیل، تصویر) رد شود، حتی اگر در DB دستی ثبت شده باشد.

### E.۳ انتخاب مدل اصلی و fallback

- **چت:** مدل اصلی = `selected_model`. نقش `fallback_json` در ارسال چت در این ممیزی تأیید نشد **[شواهد ناکافی]**؛ fallback بین Providerها از زنجیره `failover` است.
- **آینه:** اسلات ۱ = مدل اصلی؛ اسلات‌های ۲ و ۳ = fallback. ترتیب با `priority`. **[کد تأیید شد]**
- **Cloudflare:** اسلات‌ها به شماره حساب (cf1..cf3) نگاشت شده‌اند (`_cloudflare_slot_priority` در ai_models ۱۲۸). **[کد تأیید شد]** — این نگاشت با درخواست «هر تعداد حساب» سازگار نیست (بخش H).

---

## F. طراحی کشف و دسته‌بندی خودکار

### F.۱ منبع اطلاعات برای هر Provider

| Provider | منبع فهرست | منبع قابلیت | منبع رایگان بودن | منبع قیمت | وضعیت |
|---|---|---|---|---|---|
| OpenRouter | `GET /models` | `architecture.input_modalities` (کد) | `:free` و `pricing` صفر در پاسخ (کد) | `pricing` در پاسخ (کد) | قابل اتکاتر؛ زنده تست نشده |
| Groq | `GET /models` | کلیدواژه | **هیچ** (کد فرض می‌کند رایگان است) | ندارد | نیازمند منبع معتبر |
| Mistral | `GET /models` | کلیدواژه | **هیچ** (فرض رایگان) | ندارد | نیازمند منبع معتبر |
| Gemini | `_effective_base_url` (worker) | کلیدواژه (`gemini` در فهرست بینایی) | — | — | [نیاز به تست اجرایی] |
| Cloudflare | رجیستری (`DISCOVERY_SKIP`) | رجیستری | رجیستری (`is_free` ثابت) | ندارد | بدون کشف؛ مستند API مدل‌ها [شواهد ناکافی] در این ممیزی |
| GapGPT، AvalAI (ایرانی) | `GET /models` | کلیدواژه | `is_free=False` ثابت در رجیستری | ندارد | پولی فرض شده |
| Custom | `GET /models` | کلیدواژه | — | — | [نیاز به تست اجرایی] |

**قاعدهٔ پیشنهادی:** رایگان بودن فقط با یکی از این منابع ثبت شود: `pricing_field` (قیمت صفر در پاسخ API)، `suffix` (`:free`)، `probe` (تست واقعی)، یا `admin_declared` (مدیر دستی تأیید کند). **«نام Provider» یا «وجود در کاتالوگ» منبع معتبر نیست.** مقدار `unknown` آزادانه مجاز است.

### F.۲ مدل ساختار داده برای هر مدل (پیشنهاد، بدون پیاده‌سازی)

```json
{
  "id": "model-id",
  "source": "registry | discovered | manual",
  "capabilities": {
    "text_in": true, "text_out": true,
    "image_in": false, "image_out": false,
    "mask_edit": false, "inpaint": false
  },
  "capability_source": "catalog | api_metadata | registry | keyword | manual | probe",
  "free_status": "free | paid | unknown",
  "free_source": "pricing_field | suffix | probe | admin_declared | unknown",
  "admin_enabled": true,
  "review_status": "ok | needs_review | incompatible",
  "last_probe": {"at": "...", "ok": true, "error": ""}
}
```

**نکته پیاده‌سازی:** این ساختار می‌تواند داخل همان ستون‌های JSON موجود (`vision_models_json`، `text_models_json`) با کلیدهای جدید ذخیره شود، بدون ALTER. خوانندگان فعلی با `dict.get` کار می‌کنند. **[کد تأیید شد]** که خوانندگان کنونی `isinstance(m, dict)` را بررسی می‌کنند (مثلاً `context()` و `_models_for_provider_row` (ai_models ۳۹۹)).

### F.۳ قواعد کشف

1. **کشف فقط فهرست و قابلیت‌های کاتالوگ را به‌روز می‌کند.** هیچ مدلی را فعال یا انتخاب نمی‌کند.
2. **مدل جدید:** `review_status=needs_review`، `admin_enabled=false` (یا تنظیم‌شدهٔ پیش‌فرض مدیر).
3. **مدل ناپدید‌شده:** `review_status` را «غیرقابل‌دسترسی» کند؛ `selected_model` را عوض نکند. مسیر اجرا آن را به‌عنوان خطا رد کند و failover عمل کند.
4. **`admin_enabled` و `selected_model` دستی** هرگز توسط کشف بازنویسی نشوند.
5. **probe اختیاری و دستی:** یک درخواست کوچک (مثلاً `max_tokens=1`) فقط با دکمهٔ مدیر و با سقف هزینه. **[نیاز به تست اجرایی]** و **[نیاز به تأیید مدیر]** (هزینه).
6. **خطاها:** `401` کلید نامعتبر، `402` سهمیه، `403` مسدود/پروکسی، `404` `/models` نیست، `timeout`. ترجمه‌ها در `_fa_fetch_error` (ai_discovery ۲۱۶) موجودند. **[کد تأیید شد]**. فهرست قبلی حفظ شود. **[کد تأیید شد]** (تست `test_discover_provider_error_keeps_list`).

### F.۴ کاهش خطای دسته‌بندی

- یک طبقه‌بند واحد با منبع ثبت‌شده (`capability_source`). `keyword` فقط وقتی `needs_review` بدهد که منبع دیگری نباشد.
- حذف کلیدواژه‌های بسیار عمومی (`image`، `omni`) از فهرست بینایی، یا محدود کردن آن‌ها به مدل‌های بدون `image_out`.
- مدل‌هایی که هم در `vision` و هم در `text` ظاهر شوند (ممکن در `refresh_models` وقتی طبقه‌بندی تغییر کند) به یک فهرست منتقل شوند.

---

## G. طرح تغییرات حداقلی

### G.۱ فایل‌هایی که احتمالاً باید تغییر کنند

| # | فایل و نماد | هدف تغییر | وابستگی | دلیل ضرورت | ترتیب |
|---|---|---|---|---|---|
| 1 | `giso/ai_models_registry.py` (`PROVIDERS`، ۲۲–۱۶۵) | افزودن `capabilities` و `free_source` به مدل‌ها (داده)؛ حذف `is_free` ثابت یا تبدیل آن به `free_status=unknown` | `legacy_registry` (۳۰۷)، `get_*_models` (۲۳۲–۲۶۰) | بدون منبع قابلیت، بخش‌های بعدی تصمیم درست نمی‌گیرند | ۲ |
| 2 | `giso/ai_discovery.py` (`_item_is_free` ۸۵–۱۰۰، `KNOWN_FREE_PROVIDERS` ۳۱، `smart_filter_models` ۱۷۵) | حذف فرض «رایگان بودن بر اساس نام Provider»؛ تبدیل فیلتر به برچسب | `discover_provider` | ریسک رایگان‌پنداری | ۳ |
| 3 | `giso/ai_discovery.py` (`discover_provider` ۲۳۲؛ جایگزینی `selected_model` در همین تابع) | `selected_model` را فقط اگر مدیر صریحاً بخواهد عوض کند؛ در غیر این صورت وضعیت `missing` | `refresh_all_models`، ربات (۱۴۸۰) | بازنویسی بی‌صدا انتخاب مدیر | ۱ |
| 4 | `giso/ai_brain.py` (`_merge_discovered` ۹۳۳–۹۴۳) | حفظ `admin_enabled` و مدل‌های `manual`/`manual_json`؛ دیگر `disabled` را پاک نکند | `refresh_models`، `discover_provider` | غیرفعال شدن مدل دستی بی‌صدا | ۱ |
| 5 | `giso/ai_brain.py` (`_refresh_registry_sourced_models` ۱۲۲۶ به بعد) | عدم تغییر `selected_model` بی‌صدا؛ علامت‌گذاری | `seed_registry_providers` (۱۲۸۲) در هر راه‌اندازی | مدیر بدون اطلاع مدل خود را از دست می‌دهد | ۱ |
| 6 | `giso/ai_brain.py` (`_is_vision_model_id` ۸۸۲، `_ai_is_likely_vision_model` ۱۴۲۸، `_ai_is_image_generation_model` ۱۴۱۷) | یکی‌کردن در یک طبقه‌بند (یا ماژول جدید `giso/ai_capabilities.py`) و حذف فهرست تکراری | `ai_discovery._item_has_vision` (۱۰۳)، `refresh_models` (۹۵۶ به بعد) | دو تعریف متناقض | ۲ |
| 7 | `giso/ai_brain.py` (`refresh_models` ۹۵۶ به بعد) | استفاده از همان مسیر کشف گروهی (یا محدود به تفاوت Cloudflare) | پنل (۵۵۳)، ۳۴۰، ۵۴۰، ۹۶۶ | دو منطق کشف | ۴ |
| 8 | `giso/ai_health.py` (`get_provider_is_free` ۱۴۹) | برگرداندن `free_status` واقعی به‌جای «غیرایرانی» | `analysis.py` ۴۹۸ | backoff 429 بر اساس فرض | ۳ |
| 9 | `giso/buti_ai/ai_models.py` (`repair_legacy_cloudflare_eyebrow_image_slots` ۵۵۳ و فراخوانی‌ها ۴۶۹، ۶۳۱، ۷۰۰) | حذف فراخوانی از مسیرهای خواندن؛ اجرای یک‌باره در مهاجرت یا دکمهٔ مدیر | `panel_slots_context`، `configured_image_provider_dicts`، `readiness_status` | نوشتن هنگام خواندن | ۱ |
| 10 | `giso/buti_ai/ai_models.py` (`save_model_assignment` ۲۹۵ به بعد) | بررسی وجود Provider، فعال بودن، کلید، و قابلیت وظیفه قبل از ذخیره | پنل (۱۲۸–۱۳۶)، ربات | ذخیرهٔ اسلات ناسازگار | ۲ |
| 11 | `giso/buti_ai/ai_models.py` (`provider_model_options` ۴۱۹ به بعد) | فیلتر Providerهای غیرفعال و مدل‌های `disabled`/`admin_enabled=false` | `panel_slots_context` ۴۶۶ | نمایش مدل Providerهای غیرفعال | ۲ |
| 12 | `giso/buti_ai/ai_models.py` (`auto_configure_for_provider` ۸۷۱) | حذف پر کردن `mirror_output_validation` تا مصرف runtime تعریف شود | `auto_configure_defaults` | اسلات بی‌مصرف | ۴ |
| 13 | `giso/panel/modules/ai.py` (خط ۳۲۷) | `overwrite=(name=="cloudflare" or cf_slot_name)` به `False` پیش‌فرض؛ بازنویسی فقط با تأیید | ربات (۱۷۲۷، ۱۷۸۹) | بازنویسی اسلات‌های مدیر | ۱ |
| 14 | `giso/panel/modules/ai.py` (`context` ۷۵۶ به بعد) | افزودن چهار بخش (فهرست‌های فیلترشده، وضعیت) | `ai.html` | رابط جدید | ۵ |
| 15 | `giso/panel/modules/ai.py` (`handle_custom_model_add` ۸۹۳ و `_first_discovered_model` ۸۸۷) | انتخاب اولیهٔ مدل بر اساس قابلیت، نه اولین مدل خام | `first_discovered_model` (ai_brain ۳۷۳) | انتخاب بر اساس کلیدواژه | ۴ |
| 16 | `giso/panel/templates/modules/ai.html` (بخش کارت Provider و بخش اسلات آینه) | چهار بخش؛ فیلتر کشویی؛ نشان‌دادن وضعیت و رایگان بودن با منبع | `context` | — | ۵ |
| 17 | `giso/ai_runtime.py` (`_ask_single_provider` ۹۷۷) | گارد: مدل `selected_model` قبل از ارسال متنی یا بینایی باشد؛ در غیر این صورت failover بدون خطای خام | `ask_ai` | ارسال تصویر به مدل متنی | ۴ |
| 18 | `giso/ai_runtime_policy.py` / `giso/ai_health.py` | یکی‌کردن دو کولداون (درون‌حافظه‌ای و DB) یا توضیح تفاوت | `chat_with_failover`، `analysis` | دو سیستم مستقل | ۶ |
| 19 | `giso/buti_ai/eyebrow/image_generation.py` (`generate_final_design` ۱۵۷۲، حلقه inpainting تقریباً ۱۶۱۶–۱۶۲۳) | تلاش دوم فقط برای خروجی ردشده (R2 در `rep.md`) | ابرو | دو برابر timeout | ۱ |
| 20 | `giso/buti_ai/routes.py` (`eyebrow_validate_photo` ۴۲۰، `eyebrow_final_retry` ۴۹۳، `eyebrow_final_design` ۵۱۱) | گیت سهمیه یا rate limit | `security.py` (`security_gate`) | هزینه بدون کنترل (R1 در `rep.md`) | ۱ |

### G.۲ فایل‌هایی که باید بدون تغییر بمانند

| فایل | دلیل |
|---|---|
| `giso/buti_ai/eyebrow/landmarks.py`، `giso/buti_ai/lip/final_design.py`، `giso/buti_ai/eyebrow/final_design.py` | منطق ماسک، ROI و تشخیص چهره خارج از دامنه است. |
| منطق ساخت خروجی ماسک و `_validation_ok` (`service_image_generation.py`) | خارج از دامنه؛ اعتبارسنجی پیکسلی است و نباید با اعتبارسنجی AI اشتباه شود. |
| `giso/buti_ai/image_validation.py` | خارج از دامنه. |
| `bot_edu/*`، `web/web_ai/*` | پشتهٔ جدا؛ تغییر آن‌ها در این مأموریت نیست. |
| `giso/ai_credits.py` | فقط فراخوانی از مسیرهای جدید؛ منطق اعتبار دست‌نخورده. |
| `giso/security.py` | فقط افزودن قانون؛ ساختار آن دست‌نخورده. |
| `giso/data/giso.db` و `.env` | فقط از طریق مهاجرت کد؛ هیچ ویرایش دستی. |
| `GISO_GUIDE.md` | مستندات SambaNova مطابق درخواست قبلی بی‌تغییر. |

### G.۳ ترتیب (تکرار بخش J)

اولویت ۱ مواردی هستند که هم ریسک اجرایی دارند و هم تغییرشان کم‌خطر است.

---

## H. ریسک‌ها و سازگاری

| شناسه | ریسک | شاهد | کاهش خطر | برچسب |
|---|---|---|---|---|
| H1 | **تغییر بی‌صدای مدل مدیر** در کشف گروهی و راه‌اندازی | `ai_discovery.py` `discover_provider`؛ `ai_brain.py` `_refresh_registry_sourced_models` (۱۲۲۶ به بعد) | حذف جایگزینی خودکار؛ وضعیت `missing` | [کد تأیید شد] |
| H2 | **غیرفعال شدن مدل دستی** در کشف تکی | `ai_brain.py` ۹۴۱ (`pop disabled`) و ۹۴۳ (`disabled=True`) | حفظ `admin_enabled` | [کد تأیید شد] |
| H3 | **بازنویسی اسلات‌های آینه** با افزودن Cloudflare یا cf | `ai.py` ۳۲۷ | `overwrite=False` پیش‌فرض | [کد تأیید شد] |
| H4 | **نوشتن هنگام خواندن** (page view، انتخاب تصویر، readiness) | `ai_models.py` ۴۶۹، ۶۳۱، ۷۰۰ | یک‌باره در مهاجرت | [کد تأیید شد] |
| H5 | **بازگشت اسلات‌های قدیمی**: مهاجرت legacy هر بار اجرا و `INSERT OR IGNORE` می‌کند، و ردیف‌های legacy حذف نمی‌شوند | `ai_models.py` ۱۶۴ به بعد، ۲۷–۳۲، ۲۵۲ | حذف یا علامت‌گذاری ردیف legacy پس از مهاجرت؛ بررسی هم‌زمانی با `repair` | [کد تأیید شد] / [نیاز به تست اجرایی] |
| H6 | **رایگان‌پنداری** و هزینه ناخواسته | `ai_discovery.py` ۳۱، ۱۰۰؛ `ai_health.py` ۱۴۹؛ `analysis.py` ۴۹۸ | منبع رایگان بودن در بخش F | [کد تأیید شد] |
| H7 | **نمایش مدل Providerهای غیرفعال** | `ai_models.py` ۴۱۹ | فیلتر در `provider_model_options` | [کد تأیید شد] |
| H8 | **مدل ناسازگار در اسلات** (مثلاً مدل متنی در اسلات بینایی یا تصویر) | `save_model_assignment` ۲۹۵؛ `readiness_status` ۶۸۰ (بینایی را نمی‌بیند) | بررسی قابلیت در ذخیره و آمادگی | [کد تأیید شد] / [نیاز به تست اجرایی] |
| H9 | **اسلات بی‌مصرف** `mirror_output_validation` | `ai_models.py` ۳۳، ۶۰، ۷۳۶؛ `auto_configure_for_provider` ۸۷۱ | تصمیم مصرف یا حذف | [کد تأیید شد] |
| H10 | **Cloudflare فقط cf1–cf3** | `ai_brain.py` ۱۴۴ (`_is_cloudflare_instance_name`)؛ `_cloudflare_slot_priority` (ai_models ۱۲۸) | نیاز به تصمیم محصول و تعمیم نام‌گذاری | [کد تأیید شد] |
| H11 | **ناهماهنگی `.env` و DB** | `ai.py` ۳۱۹–۳۲۳ (`except Exception`) | نمایش خطا | [کد تأیید شد] |
| H12 | **کلید API در `.env`** به صورت متن | `ai_brain.py` ۱۸۶۶ (`save_provider_to_env`) | بررسی جداگانه؛ در این ممیزی دوباره بررسی نشد | [شواهد ناکافی برای سطح ریسک] |
| H13 | **هزینهٔ بدون کنترل** در مسیرهای آینه | `buti_ai/routes.py` ۴۲۰، ۴۹۳، ۵۱۱، ۱۱۳۹؛ `security.py` (`security_gate`)؛ `giso/buti_ai` بدون `ai_credits` | گیت سهمیه | [کد تأیید شد] / [ریسک] |
| H14 | **تلاش مضاعف** در inpainting ابرو | `eyebrow/image_generation.py` (`generate_final_design`، حلقه تقریباً ۱۶۱۶–۱۶۲۳) | تلاش دوم فقط برای خروجی ردشده | [کد تأیید شد] |
| H15 | **وابستگی لب/ناخن/مو به ماژول ابرو** | `service_image_generation.py` ۱۶ | انتقال لودر به ماژول مشترک | [کد تأیید شد] |
| H16 | **دو کولداون** مستقل | `ai_runtime_policy.py` ۱۴–۱۶ (۱۲۰ ثانیه) و `_provider_in_cooldown` ۱۶۶؛ `ai_health.py` ۹۸ | یکی‌کردن یا توضیح | [کد تأیید شد] |
| H17 | **مسیرهای قدیمی پشت پرچم** | `ai_config.py` (پرچم `FEATURE_FLAG_LEGACY_MODE`)؛ `_legacy_chat_with_failover` در `ai_runtime.py`؛ `_legacy_call_vision_with_fallback` (`analysis.py` ۵۱۳) | بررسی ترافیک، سپس حذف | [کد تأیید شد] |
| H18 | **پشتهٔ موازی** `bot_edu` با LLM7 (که در `giso` بازنشسته است) و DB جدا؛ و `bot_edu` از `giso` import می‌کند | `bot_edu/config.py`؛ `giso/ai_brain.py` ۱۲۲۳ (`RETIRED_PROVIDERS`) | تصمیم مدیر درباره ادغام یا نگه‌داشتن | [کد تأیید شد] |
| H19 | **اعداد اطمینان ثابت** در تشخیص چهره و لب | `eyebrow/landmarks.py` (`_detect_with_mediapipe`)؛ `lip/final_design.py` (چند خط، از یادداشت قبلی ~۱۸۶، ~۲۵۳، ~۳۲۴، ~۳۳۰) | اندازه‌گیری‌شده یا حذف گیت | [کد تأیید شد] |
| H20 | **گراف Graphify قدیمی** | `graph.json` با `c9b198cd`؛ شماره خطوط ناهم‌خوان (بخش B در `rep.md`) | تازه‌سازی گراف پس از ادغام | [کد تأیید شد] |
| H21 | **مدل‌های جدید بلافاصله در فهرست فعال به نظر می‌رسند** و در کشویی می‌آیند | `_merge_discovered` ۹۳۳ (مدل جدید بدون `disabled` اضافه می‌شود) | `needs_review` | [کد تأیید شد] |
| H22 | **کشف روی Providerهای غیرفعال** | `discover_provider` ۲۴۲ (`enabled` چک می‌شود)؛ `refresh_models` (بدون چک تأیید شد با خواندن قبلی) | بررسی `enabled` در `refresh_models` | [کد تأیید شد] (discover) / [نیاز به بررسی] (refresh) |

---

## I. برنامهٔ تست

**هیچ‌کدام از این تست‌ها اجرا نشده‌اند.** پیش‌نیاز: نصب `pytest`، `flask` و بقیه با تأیید مدیر (طبق قاعدهٔ `giso-dev`)، و یک کپی تمیز از DB.

| سناریو | شاهد موجود (فایل / نام تست) | پوشش فعلی | تست پیشنهادی |
|---|---|---|---|
| مدل متنی: فهرست فقط فعال و متنی | `test_admin_ai_custom_model_simple.py::test_provider_card_lists_discovered_models`؛ `test_ai_clean_registry.py::test_vision_priority_free_first` | جزئی | کشویی چت فقط مدل‌های متنی فعال نشان دهد |
| تحلیل عکس: فقط مدل با ورودی تصویر | `test_ai_cloudflare_vision.py` | جزئی (فقط Cloudflare) | مدل متنی در اسلات `eyebrow_analysis` ذخیره نشود |
| تولید تصویر: مدل ناسازگار نمایش داده نشود | `test_buti_ai_four_services_flow.py`؛ `test_buti_ai_phase1.py` | جزئی (گزارش آمادگی، نه کشویی) | `provider_model_options` فیلتر شود |
| مدل چندقابلیتی | — | **ندارد** | یک مدل با text+image در دو اسلات |
| Provider غیرفعال | `test_ai_runtime.py::test_failover_cooldown_skips_recently_failed_provider` (کولداون، نه غیرفعال‌بودن صریح) | جزئی | `provider_model_options` و `save_model_assignment` |
| مدل رایگانِ دردسترس‌نبودنی | — | **ندارد** | Provider بدون `/models` یا با 404: فهرست حفظ شود، `review_status` درست |
| خطای کشف | `test_ai_discovery.py::test_discover_provider_error_keeps_list`، `test_fetch_error_translation` | خوب | — |
| Fallback | `test_ai_runtime.py`؛ `test_buti_ai_phase1.py::test_photo_quality_falls_back_from_cf1_to_next_ai_management_vision` | خوب | شکست تلاش دوم در inpainting: یک بار تماس با ابرو |
| حفظ تنظیمات | `test_ai_discovery.py::test_discover_provider_saves_report` (ذخیرهٔ گزارش، نه حفظ `selected_model`) | ناکافی | `selected_model` و `admin_enabled` بعد از کشف دوباره |
| حذف Provider | `test_admin_ai_panel.py` و `test_ai_provider_admin_registry.py::test_deleted_registry_provider_stays_deleted_until_explicitly_readded` | جزئی | اسلات‌های آینه پاک یا `needs_review` شوند |
| بازنویسی اسلات با Cloudflare | پوشش ناکافی در فهرست تست‌های موجود | ناکافی | `overwrite=False` پیش‌فرض |
| خواندن بدون نوشتن | — | **ندارد** | پیمایش صفحهٔ پنل و `readiness` روی DB کپی و بررسی تغییر نکردن |
| رایگان بودن از منبع | `test_ai_clean_registry.py::test_openrouter_free_models_current` و `test_groq_free_models_current` (**فقط داده ثابت را تأیید می‌کنند**) | **گمراه‌کننده** | `free_source` ثبت شود؛ groq بدون پاسخ قیمت → `unknown` |
| هزینه/سهمیه روی مسیر آینه | — | **ندارد** | بیش از حد سهمیه → رد؛ تماس خروجی = یک بار |

**تست‌های قبلی که نباید به‌عنوان اثبات گرفته شوند:** `test_ai_clean_registry.py` (طبق نام و خواندن قبلی) با داده ثابت کار می‌کند، نه با مدل زنده. نام تست‌ها در این بخش از روی فایل‌ها تأیید شده‌اند، اما **هیچ‌کدام اجرا نشده‌اند**.

---

## J. تصمیم نهایی

### وضعیت: **نیازمند اصلاح معماری محدود**

**دلیل:** وابستگی‌ها و تعارض‌های اثبات‌شده‌ای وجود دارد که باید **پیش از** هر تغییر رابط حل شوند:

1. نوشتن هنگام خواندن (H4) و بازنویسی انتخاب مدیر (H1، H2، H3) — این‌ها داده‌های مدیر را بی‌صدا تغییر می‌دهند.
2. نبود منبع معتبر برای قابلیت و رایگان بودن (H6، H8) — بدون آن، «نمایش فقط سازگارها» فقط حدس است.
3. دو مسیر کشف و دو طبقه‌بند (C) — بدون یکی‌کردن، هر تغییر در یکی با دیگری ناسازگار می‌شود.

تغییرات کم‌خطر و قابل آزمون وجود دارند و **همهٔ آن‌ها داخل همین ساختار** انجام می‌شوند. هیچ سیستم موازی یا رجیستری تکراری لازم نیست.

### پیشنهاد نهایی: مراحل کوچک، مستقل و قابل بازبینی

| مرحله | هدف | فایل‌ها (بخش G) | خروجی قابل بازبینی | پذیرش |
|---|---|---|---|---|
| **۰ (فقط خواندن)** | تأیید وضعیت زنده | — | گزارش از یک کپی DB: ردیف‌های Provider، اسلات‌ها، sambanova، LLM7 | هیچ تغییری روی DB اصلی |
| **۱ (کنترل ایمنی)** | متوقف‌کردن بازنویسی بی‌صدا | ۱، ۳، ۴، ۵، ۹، ۱۳، ۱۹، ۲۰ | `selected_model` و مدل دستی حفظ می‌شوند؛ خواندن دیگر نمی‌نویسد؛ تلاش دوم فقط برای خروجی ردشده؛ گیت سهمیه | تست‌های `test_ai_discovery`، `test_buti_ai_*` و تست جدید «خواندن بدون نوشتن» |
| **۲ (منبع قابلیت)** | یک طبقه‌بند و `admin_enabled` | ۱ (داده)، ۶، ۱۰، ۱۱ | دو تعریف به یکی تبدیل شود؛ `save_model_assignment` قابلیت را بررسی کند؛ Providerهای غیرفعال از کشویی حذف شوند | تست‌های فیکسچر `/models` واقعی (کپی ذخیره‌شده، نه زنده) |
| **۳ (رایگان و کشف)** | رایگان بودن با منبع؛ مسیر کشف واحد | ۲، ۷، ۸، ۲۲ | `free_status` با منبع؛ `unknown` مجاز؛ `refresh_models` و `discover_provider` یک منطق | تست: groq بدون قیمت → `unknown` |
| **۴ (مصرف‌کننده‌ها)** | گارد مدل در اجرا و انتخاب اولیه | ۱۵، ۱۷، ۱۲ | مدل ناسازگار در اجرا رد شود؛ انتخاب اولیه بر اساس قابلیت | تست‌های چت و تصویر |
| **۵ (رابط چهار بخش)** | نماهای جدید پنل | ۱۴، ۱۶ | چهار بخش با فیلتر و وضعیت | تست رندر و `test_admin_ai_panel` |
| **۶ (تمیزکاری)** | یکی‌کردن کولداون، حذف مسیر قدیمی، LLM7 در bot_edu، گراف | ۱۸، H16، H17، H18 | — | پس از تأیید مدیر |

**نکات اجرایی:**
- هر مرحله جدا commit و جدا بازبینی شود.
- هیچ مرحله‌ای DB زنده را بدون پشتیبان و بدون تأیید تغییر ندهد.
- مرحلهٔ ۱ کم‌ریسک‌ترین و سودمندترین است؛ می‌تواند بدون وابستگی به بقیه انجام شود، **پس از** تأیید مدیر.

---

## بخش‌های لازم دیگر

### تطبیق با `rep.md` (گزارش قبلی)

| یافتهٔ قبلی | وضعیت در این ممیزی |
|---|---|
| R1 مسیرهای آینه بدون سهمیه | **تأیید شد** (`buti_ai/routes.py` و `security.py`) |
| R2 تلاش مضاعف در ابرو | **تأیید شد** |
| R4 دو طبقه‌بند بینایی | **تأیید شد** و جزئیات افزوده شد (`gemini` در `_ai_is_likely_vision_model`) |
| R5 بدون بررسی قابلیت در ذخیره | **تأیید شد** |
| R6 حذف Provider و اسلات‌ها | **تأیید شد** (`delete_ai_provider` ۳۲۴ بدون جدول آینه) |
| R7 `mirror_output_validation` | **تأیید شد** |
| R12 upsert و `models_json` | **نیاز به اصلاح در `rep.md` (بدون تغییر در این مأموریت):** در `add_ai_provider` (`ai_brain.py` ۲۸۷–۳۰۰) فیلدهای `vision_models_json` و `text_models_json` با `COALESCE` حفظ می‌شوند؛ فقط `models_json` جایگزین می‌شود. |
| R11 کلید در `.env` | **تأیید نشد در این ممیزی** (کد `save_provider_to_env` دوباره بازبینی نشد) |
| R14 sambanova در DB زنده | **همچنان تأیید نشده** (DB زنده در دسترس نیست) |

### گراف Graphify

گراف (`c9b198cd`) قدیمی است. شماره‌های `ask_ai` (L1078) و `ask_ai_vision` (L1156) با کد فعلی هم‌خوان نیستند. نام توابع مربوط به این ممیزی (`save_model_assignment`، `readiness_status`، `handle_custom_model_add`، `generate_final_design`) در گراف برچسب ندارند. **گراف برای این ممیزی استفاده نشد.**

### نکات امنیتی

- هیچ کلید، توکن یا مقدار `.env` در این گزارش نوشته یا چاپ نشده است.
- کلیدهایی که در گفتگو وارد شده‌اند پس از تست‌ها باید **تعویض (rotate)** شوند.

### آنچه بررسی نشد

- اجرای تست‌ها و تماس زنده با Providerها.
- محتوای DB زنده.
- `bot_edu`، `web_ai`، `super_assistant`، `monitoring_ai`، `seo_jobs`، `channel_importer` به‌طور کامل (فقط جستجوی نام).
- `gemini_proxy_manager.py` و پروکسی Gemini.
- مستند رسمی API مدل‌های Cloudflare (sandbox به `api.cloudflare.com` دسترسی ندارد).

*پایان گزارش.*
