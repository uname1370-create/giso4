# تحلیل: حفظ تنظیمات مدیریت مرکزی AI (2026-10-16)

وضعیت شروع: شاخه `arena/7f567e47-giso4` و `origin` هر دو روی `d3ff22f`، درخت کاری تمیز، بدون stash. هیچ reset انجام نشده است.

## ۱. فراخوانی‌های `add_ai_provider`

| محل | حالت | نکته |
|---|---|---|
| `giso/ai_brain.py` `seed_registry_providers` (~1463) | `replace=False` (فقط INSERT) | فقط برای ردیف‌های جدید؛ `enabled=False` |
| `giso/ai_brain.py` `sync_env_providers_to_db` (~1997) | `replace=True` | فقط وقتی جدول خالی است (`return` زودهنگام)، پس عملاً INSERT |
| `giso/bot.py` ۱۷۰۴ (پروایدر نام‌دار) | `replace=True`, `enabled=True`, `timeout`, `is_iranian`, `use_proxy` از رجیستری | مسیر واقعی زمان اجرا |
| `giso/bot.py` ۱۷۶۷ (cloudflare) | همان الگو | |
| `giso/bot.py` ۱۸۱۹ (custom) | همان الگو با مقادیر ثابت | |

پنل وب از `add_ai_provider` استفاده نمی‌کند (`create_provider_instance` / `finalize_provider_instance` مسیر جدا دارند).

## ۲. آنچه `replace=True` روی ردیف موجود می‌نویسد

`ON CONFLICT(name) DO UPDATE` این ستون‌ها را با مقدار پارامتر بازنویسی می‌کند:

| ستون | مقدار نوشته‌شده هنگام bot re-add | وضعیت |
|---|---|---|
| `kind`, `api_key`, `base_url`, `api_root` | مقدار ورودی | **قصد صریح** (کلید/آدرس جدید) — حفظ می‌شود |
| `enabled` | `True` ثابت | **مشکل**: پروایدر غیرفعال را بی‌صدا فعال می‌کند |
| `selected_model` | ورودی خالی → `_stored_selected_model` یا پیش‌فرض رجیستری | اصلاح قبلی (`d3ff22f`) ✅ |
| `fallback_json` | ورودی پیش‌فرض `[]` → **فهرست رجیستری** | **مشکل**: ترتیب fallback مدیر پاک می‌شود |
| `models_json` | ورودی پیش‌فرض `[]` → فهرست رجیستری | **مشکل**: فهرست مدل‌های مدیر پاک می‌شود |
| `timeout` | رجیستری | **مشکل**: تنظیم دستی مدیر پاک می‌شود |
| `headers_json` | ورودی پیش‌فرض `"{}"` | **مشکل**: هدرهای سفارشی پاک می‌شوند |
| `is_iranian`, `use_proxy` | رجیستری / `False` | **مشکل**: تنظیم پروکسی/ایرانی مدیر پاک می‌شود (`proxy_url` با COALESCE حفظ می‌شود) |
| `vision_models_json`, `text_models_json`, `proxy_url`, `proxy_type`, `models_source` | COALESCE / خالی | حفظ می‌شود |

نتیجه: هر بار که مدیر از ربات «افزودن» را برای نامی که وجود دارد اجرا می‌کند، ترتیب fallback، فهرست مدل‌ها، timeout، هدرها، پروکسی و وضعیت فعال بودن بازنشانی می‌شوند. این با سیاست «هیچ داده‌ای بدون دستور صریح بازنویسی نشود» در تضاد است.

## ۳. مسیرهای دیگر که بدون add_ai_provider تنظیم مدیر را بازنویسی می‌کنند

این مسیرها مستقل از `add_ai_provider` هستند و باید بررسی شوند:

1. **`_refresh_registry_sourced_models`** (`ai_brain.py` ~1388) — در **هر** بار اجرای `seed_registry_providers` (که از `base.py` در `_giso_init_db` صدا زده می‌شود، یعنی هر راه‌اندازی) برای `groq`، `openrouter`، `mistral`، `cloudflare` اجرا می‌شود. اگر `models_source` ردیف `''` یا `registry` باشد، `fallback_json` را با **ترتیب رجیستری** بازنویسی می‌کند.
   - واقعیت کد: ویرایش دستی fallback از پنل (`update_ai_provider_field("fallback")`) فیلد `models_source` را تغییر نمی‌دهد. پس ترتیب دستی مدیر برای این چهار پروایدر در راه‌اندازی بعدی از بین می‌رود.
   - `selected_model` در این مسیر حفظ می‌شود ✅.
2. **`discover_provider`** (`ai_discovery.py` ~347) — `fallback_json` را با ترتیب کشف‌شده (`all_ids`) بازنویسی می‌کند. `selected_model` حفظ می‌شود ✅ (قانون «کشف هرگز انتخاب را تغییر نمی‌دهد» رعایت شده).
3. **`refresh_models` (Cloudflare)** (`ai_brain.py` ~1118–1135) — همین الگو؛ `selected` حفظ می‌شود ✅، `fallback_json` با ترتیب رجیستری نوشته می‌شود.
4. `_backfill_registry_models` — فقط وقتی فهرست خالی است پر می‌کند ✅ (بی‌خطر).

## ۴. مسیر خواندن تا اجرا (تنظیم ذخیره‌شده → انتخاب → اجرا)

- **زنجیرهٔ مرکزی متن** (`configured_text_chain` → `configured_vision_chain(TASK_TEXT_CHAT)`): مدل از **اسلات‌های تخصیص** (`buti_ai_model_assignments`) می‌آید؛ فقط بررسی می‌کند که پروایدر `enabled` باشد. `selected_model` و `fallback_json` پروایدر در این مسیر خوانده نمی‌شوند.
- **مسیر قدیمی** (`_legacy_chat_with_failover` → `_ask_single_provider` → `ask_ai`): مدل = `model_name` یا **`selected_model` ردیف** یا `fallback_json[0]`. یعنی تنظیم مدیر در این مسیر مستقیم اثر دارد. این مسیر وقتی زنجیرهٔ مرکزی خالی است اجرا می‌شود.
- **زنجیرهٔ مرکزی تصویر/بینایی** (`configured_vision_chain`): فقط `enabled` پروایدر را بررسی می‌کند. **مدل ناسازگار (`incompatible`) فیلتر نمی‌شود**؛ فیلتر فقط در زمان ذخیرهٔ اسلات (`validate_slot_selection`) انجام می‌شود. این یک شکاف واقعی در اجرا است: اگر وضعیت یک مدل بعداً به `incompatible` تغییر کند، همچنان در زنجیره می‌ماند.
- **تست اتصال** (`check_ai_provider`): فقط روی `selected_model` امتحان می‌کند؛ اگر خالی باشد از `fallback` و سپس فهرست. نتیجه هرگز `selected_model` را تغییر نمی‌دهد ✅.

## ۵. پاسخ به پرسش «آیا رجیستری واقعاً تنظیم مدیر را بازنویسی می‌کند؟»

- **بله**، در دو نقطهٔ واقعی زمان اجرا:
  - bot re-add (`add_ai_provider(replace=True)`): `fallback_json`، `models_json`، `enabled`، `timeout`، `headers_json`، `is_iranian`، `use_proxy`.
  - راه‌اندازی مجدد (`_refresh_registry_sourced_models`): `fallback_json` (ترتیب) و `models_json` برای چهار پروایدر با `models_source` غیر-دستی.
  - کشف دستی (`discover_provider`): `fallback_json` (ترتیب).
- **`selected_model`** در هیچ‌کدام از مسیرهای بالا بازنویسی نمی‌شود (پس از اصلاح `d3ff22f`) ✅.
- بازنویسی رجیستری در مواردی ضروری است: ردیف خالی، ردیف جدید، یا فهرست «مرده» که باید حذف شود. این موارد باید حفظ شوند، ولی بازنویسی بدون شرط نباید انجام شود.

## ۶. راهکار (حداقل تغییر، سازگار با معماری)

الف) **`add_ai_provider`** (`giso/ai_brain.py`):
- پارامترهای `enabled`، `timeout`، `headers_json`، `fallback_json`، `models_json`، `is_iranian`، `use_proxy` پیش‌فرض `None` می‌گیرند یعنی «ارسال نشده».
- ردیف جدید یا `replace=False`: `None` به پیش‌فرض قبلی تبدیل می‌شود (`enabled=True`، `timeout`/`is_iranian` از رجیستری یا ۲۰/False، `use_proxy=False`، `headers="{}"`، فهرست‌ها از رجیستری). رفتار قبلی برای seed و env حفظ می‌شود.
- ردیف موجود با `replace=True`: `None` یعنی مقدار فعلی ردیف. برای فهرست‌ها: اگر مقدار فعلی خالی است از رجیستری پر می‌شود (رفتار قبلی برای ردیف خالی). مقدار صریح غیرخالی همچنان اعمال می‌شود.
- `selected_model` مثل قبل: ورودی صریح > انتخاب ذخیره‌شده > پیش‌فرض رجیستری.
- `kind`، `api_key`، `base_url`، `api_root`، `proxy_url`، `proxy_type` بدون تغییر.

ب) **`giso/bot.py`** (سه فراخوانی `replace=True`): حذف آرگومان‌های `enabled=True`، `timeout`، `is_iranian`، `use_proxy` تا تنظیمات ذخیره‌شدهٔ مدیر حفظ شوند. برای ردیف جدید همان مقادیر از رجیستری گرفته می‌شوند (`PROVIDERS` همان منبع `legacy_registry` است و `use_proxy` همیشه `False` است)؛ بنابراین رفتار ردیف جدید تغییر نمی‌کند. `enabled` ردیف جدید `True` است.
   - تصمیم: پروایدر غیرفعال با افزودن مجدد از ربات **غیرفعال می‌ماند**؛ فعال‌سازی باید صریح از پنل انجام شود (طبق «وضعیت فعال بودن باید طبق سیاست ذخیره‌شده حفظ شود»).

ج) **ترتیب fallback در مسیرهای خودکار** (`giso/ai_brain.py` `_refresh_registry_sourced_models` و `refresh_models`؛ `giso/ai_discovery.py` `discover_provider`): ترتیب موجود حفظ شود. ابتدا آیتم‌های قبلی که هنوز در فهرست جدید هستند (به همان ترتیب)، سپس آیتم‌های جدید. اگر ترتیب قبلی خالی باشد، فهرست جدید استفاده می‌شود. این تابع کمکی `_merge_fallback_order` نام دارد. آیتم‌های «مرده» که از فهرست جدید حذف شده‌اند همچنان حذف می‌شوند (هدف اصلی این مسیر).

د) **فیلتر ناسازگار در زنجیرهٔ مرکزی** (`giso/buti_ai/ai_models.py` `configured_vision_chain`): اسلاتی که وضعیت قابلیت آن برای همان کاربرد `STATUS_INCOMPATIBLE` است، کنار گذاشته می‌شود. وضعیت `unknown` و `probable` دست‌نخورده می‌ماند (تغییر سیاست نمایش «unknown = ready» ندارد). فقط ناسازگاری صریح مانع اجرا می‌شود. کاربرد: `model_capability_for_provider`.

## ۷. آزمون‌های هدفمند (فیک و دیتابیس موقت)

1. انتخاب ذخیره‌شده با `replace=True` و بدون مدل حفظ می‌شود (پوشش دارد ✅، تست موجود).
2. فهرست مدل‌ها، fallback، timeout، headers، proxy، enabled با `replace=True` بدون مقدار صریح حفظ می‌شوند.
3. تغییر صریح: مقدار صریح `enabled`/`fallback_json` ذخیره و اعمال می‌شود.
4. ردیف جدید و ردیف قدیمی (seed، `replace=False`) همچنان پیش‌فرض رجیستری می‌گیرند.
5. `_refresh_registry_sourced_models` ترتیب fallback مدیر را نگه می‌دارد و مدل‌های مرده را حذف می‌کند؛ `discover_provider` ترتیب را نگه می‌دارد.
6. مدل ناسازگار در `configured_vision_chain` نیامده و مدل غیرفعال (پروایدر) هم نیامده است.
7. `bot` re-add: پروایدر غیرفعال غیرفعال می‌ماند (تست مستقیم روی `add_ai_provider` با همان آرگومان‌های جدید bot).

## ۸. محدوده و آنچه اصلاح نمی‌شود

- مشکلات غیرمرتبط (import‌های `notify_risk`، `review_mission_award`، `DEFAULT_SITE_BASE_URL`) اصلاح نمی‌شوند.
- `save_provider_to_env` هنگام افزودن از ربات هنوز `enabled=True` را در `.env` می‌نویسد. این مسیر در زمان اجرا از `.env` نمی‌خواند (sync فقط روی جدول خالی)، ولی ناسازگاری ذخیره‌سازی باقی می‌ماند. گزارش می‌شود.
- تست زنده اجرا نمی‌شود؛ فقط آزمون‌های فیک.
- فیلتر `unknown` در زنجیرهٔ تصویر اعمال نمی‌شود (تصمیم سیاستی جدا لازم است).

## ۹. نتیجهٔ اجرا (پس از اصلاح)

تغییرات اعمال‌شده (بدون commit و push):
- `giso/ai_brain.py`: `add_ai_provider` با پارامترهای «ارسال‌نشده» (`None`) برای `enabled`، `timeout`، `headers_json`، `fallback_json`، `models_json`، `is_iranian`، `use_proxy`؛ ردیف موجود با `replace=True` مقدار ذخیره‌شده را نگه می‌دارد. تابع `_merge_fallback_order` اضافه شد و در `_refresh_registry_sourced_models` و `refresh_models` (Cloudflare) استفاده می‌شود.
- `giso/ai_discovery.py` (`discover_provider`): ترتیب fallback ذخیره‌شده را نگه می‌دارد؛ `selected_model` دست‌نخورده است.
- `giso/buti_ai/ai_models.py` (`configured_vision_chain`): اسلات با وضعیت صریح `incompatible` برای همان کاربرد اجرا نمی‌شود؛ `unknown` و `probable` بدون تغییر، و خطای بررسی اسلات را حذف نمی‌کند.
- `giso/bot.py` (۳ فراخوانی `replace=True`): حذف `enabled=True`، `timeout`، `is_iranian`، `use_proxy` از آرگومان‌ها. ردیف جدید همچنان مقادیر رجیستری را می‌گیرد.
- `giso/tests/test_ai_selection_and_consultant.py`: ۸ تست جدید (مجموع ۱۱).

آزمون‌ها (فیک و دیتابیس موقت؛ کپی مستقل `final3`):
- `test_ai_selection_and_consultant.py`: ۱۱/۱۱ پاس.
- مقایسه با پایه (`mut_head` = HEAD `d3ff22f` برای ۴ فایل منبع): ۵ تست سیاست‌محور روی کد قبلی رد می‌شوند (حفظ تنظیمات ربات، ترتیب fallback در کشف و راه‌اندازی، فیلتر ناسازگار). ۶ تست دیگر آزمون‌های سازگاری یا حفاظ‌اند و روی کد قبلی هم پاس می‌شوند.
- مجموعهٔ کامل `giso/tests`: ۸۴۱ پاس / ۴۵ فیل / ۴ skip. مجموعهٔ ۴۵ فیل و دلایل خطا دقیقاً مثل پایه (`d3ff22f`، ۸۳۳ پاس / ۴۵ فیل) است؛ فیل جدیدی وجود ندارد.
- render و CSRF و بخش‌های مدل، ربات/ثبت پروایدر و کشف: ۶۴/۶۴ پاس.
- تست زنده: NOT RUN (کلید معتبر و دسترسی به پروایدرها در ساندباکس نیست).

## ۱۰. ریسک‌های باقی‌مانده

1. `save_provider_to_env` هنوز هنگام افزودن از ربات `enabled=True` را در `.env` می‌نویسد. زمان اجرا از دیتابیس می‌خواند و `.env` فقط وقتی جدول خالی است sync می‌شود، پس اثر فوری ندارد؛ ولی فایل با وضعیت دیتابیس هم‌خوان نیست.
2. پروایدر غیرفعال با افزودن مجدد از ربات غیرفعال می‌ماند. فعال‌سازی باید از پنل انجام شود. این رفتار عمدی است (سیاست «حفظ وضعیت ذخیره‌شده») و باید تأیید شود.
3. `_refresh_registry_sourced_models` هنوز `models_json` را با فهرست رجیستری جایگزین می‌کند (فقط برای ردیف‌های با منبع «رجیستری/خالی»). مدل‌های دستی که مدیر در فهرست اضافه کرده ولی منبعشان ثبت نشده، ممکن است حذف شوند. ترتیب fallback حفظ می‌شود، ولی آیتم‌های غیررجیستری در `fallback_json` هم با این مسیر حذف می‌شوند (همان رفتار حذف مدل‌های مرده).
4. `configured_vision_chain` فقط `incompatible` را فیلتر می‌کند. `unknown` همچنان در زنجیره می‌ماند (تصمیم سیاستی جدا).
5. مسیر قدیمی `ask_ai` هنوز از `selected_model` و `fallback_json[0]` استفاده می‌کند؛ این مسیر فقط وقتی زنجیرهٔ مرکزی خالی است اجرا می‌شود و با این تغییر رفتارش عوض نشده است.
6. `create_provider_instance` (مسیر adopt روی ردیف seed‌شده و تأیید‌نشده) همچنان مقدار فرم را روی ردیف می‌نویسد؛ از محدودهٔ این مرحله خارج است.
7. مشکلات غیرمرتبط (`notify_risk`، `review_mission_award`، `DEFAULT_SITE_BASE_URL`) اصلاح نشده‌اند.
