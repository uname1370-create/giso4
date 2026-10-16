# تحلیل انتقال «مدیریت و انتخاب مدل‌ها» به تب مستقل «🧠 مدیریت مدل‌های هوش مصنوعی»

تاریخ: 2026-10-16 · شاخه: `arena/7f567e47-giso4` · پایه: `bd59dc5` (HEAD = origin)

## ۱. وضعیت Git قبل از تغییر
- شاخه تمیز، HEAD = origin = `bd59dc5`، stash خالی. هیچ تغییر محلی از قبل وجود نداشت.

## ۲. ساختار فعلی (از کد خوانده شد)
| بخش | فایل و محل |
|---|---|
| نوار تب‌ها | `giso/panel/templates/modules/ai.html` خط ۲۱–۳۱ (`data-tabs`) |
| تب پروایدرها | همان فایل، `pane-providers` خط ۳۶ تا ۲۶۲ |
| کارت مدل‌ها (فعلی داخل پروایدرها) | همان فایل، `id="model-section"` خط ۸۷ تا ۱۶۸ |
| کارت پروایدرها (بعد از کارت مدل‌ها) | همان فایل، از خط ۱۷۰؛ **می‌ماند** |
| سه دسته | `giso/buti_ai/ai_models.py` `MODEL_SECTION_CATEGORIES` (خط ۸۴) |
| برچسب‌ها و راهنما | `giso/panel/modules/ai.py` `_MODEL_SECTION_LABELS` (خط ۹۱۸) |
| داده صفحه | `giso/panel/modules/ai.py` `build_model_section()` (خط ۹۳۳)، از بارگذاری صفحه AI (خط ۸۶۲) فراخوانی می‌شود |
| ذخیره دسته | route `POST /ai/model-section/<category>/save` (`giso/panel/routes.py` ۱۵۵۸) → `handle_model_section_save` (`ai.py` ۱۰۲۳) → `save_model_section` (`ai_models.py` ۶۱۲) |
| تست مدل | route `POST /ai/model-section/test` (`routes.py` ۱۵۶۶) → `handle_model_section_test` (`ai.py` ۱۰۴۵) |
| به‌روزرسانی فهرست مدل‌ها | endpoint `ai_provider_refresh_all_models` (`routes.py` ۱۶۴۰) → `handle_refresh_all_models` (`ai.py` ۶۴۰) |

### کلیدهای واقعی دسته‌ها (از `MODEL_SECTION_CATEGORIES`)
| کلید داخلی | task_key | capability | برچسب فعلی در کد |
|---|---|---|---|
| `text` | `TASK_TEXT_CHAT` | `text` | متن |
| `image_analysis` | `TASK_EYEBROW_ANALYSIS` | `vision` | تحلیل عکس |
| `image_generation` | `TASK_MIRROR_IMAGE_DESIGN` | `image_gen` | ساخت/ویرایش تصویر |

کلیدها و برچسب‌ها بدون تغییر حفظ می‌شوند (دستور: نام‌های داخلی حفظ شوند).

### جریان داده (DB → انتخاب → اجرا)
- ذخیره: سه فیلد `slot_1..slot_3` با قالب `provider|model` → `save_model_section` → جدول `buti_ai_model_assignments` بر اساس `task_key` و `priority`.
- خواندن: `build_model_section` → `list_model_assignments(task_key)` → کارت.
- اجرا: همان ردیف‌ها توسط زنجیره‌های اجرایی (`configured_text_chain`، `configured_vision_chain`، تولید تصویر) خوانده می‌شوند. این مسیر تغییر نمی‌کند.

## ۳. مسیرهای redirect و تب‌ها
- `panel.js` (خط ۱۴۷–۱۹۰): تب‌ها با `location.hash` (`#pane-<key>`) فعال می‌شوند؛ کلیک تب `replaceState` می‌کند.
- **مشکل:** سه redirect مدل‌ها (`#model-section`، در `ai.py` خط‌های ۱۰۴۲، ۱۰۵۷، ۱۰۷۶) به یک id داخل تب پروایدرها اشاره می‌کنند. بعد از انتقال، این hash تب را فعال نمی‌کند و کاربر بعد از ذخیره/تست به تب پروایدرها برمی‌گردد. پس باید به تب مدل‌ها هدایت شوند.
- `handle_refresh_all_models` (خط ۶۴۰) به `panel.ai` بدون hash برمی‌گردد. این handler دو جا استفاده می‌شود: دکمه کارت مدل‌ها (`ai.html` خط ۹۵) و دکمه تب «وضعیت و تست» (`ai.html` خط ۲۷۴). اگر redirect آن به تب مدل‌ها تغییر کند، دکمه وضعیت هم کاربر را جابه‌جا می‌کند؛ این تغییر تب دیگری است و مجاز نیست.
- JS به هر فرم POST فیلد `_back_tab` (کلید تب فعال) اضافه می‌کند. پیش از این هیچ handler هوش مصنوعی آن را نمی‌خواند؛ اکنون فقط `_refresh_redirect()` آن را می‌خواند.

### تصمیم redirect (پیاده‌سازی‌شده)
- ذخیره و تست مدل‌ها: مقصد ثابت `#pane-models`. این دو فرم فقط در تب مدل‌ها وجود دارند.
- به‌روزرسانی فهرست مدل‌ها: helper جدید `_refresh_redirect()` فقط اگر `_back_tab == "models"` باشد به `#pane-models` می‌رود؛ در غیر این صورت رفتار قبلی (`panel.ai` بدون hash) حفظ می‌شود. بنابراین دکمهٔ تب «وضعیت و تست» تغییری نمی‌کند.

## ۴. تب آینه گیسو (بررسی وابستگی)
- `pane-beauty-mirror` (خط ۳۵۰–۴۷۵) فرم‌های اسلات دارد با `ai_action=save_beauty_mirror_model` (`ai.py` ۱۲۵) که همان `task_key`های دسته‌های متن/تحلیل/تولید تصویر را می‌نویسد.
- این فرم‌ها فیلدهایی دارند که کارت عمومی ندارد: `image_kind`، `endpoint_override` و `enabled`. بنابراین کپی مستقیم مدیریت عمومی نیستند.
- همچنین فهرست چهارتایی `CATEGORY_DEFS` (`ai_categories.py`، شامل «ارزیابی خروجی») فقط در همین تب استفاده می‌شود.
- **تصمیم:** این تب دست‌نخورده می‌ماند (دستور: تنظیمات تخصصی آینه گیسو در تب خودش بماند). همپوشانی نوشتن روی همان `task_key`‌ها به‌عنوان ریسک گزارش می‌شود.

## ۵. تغییرات پیشنهادی (حداقلی)
1. `ai.html`: افزودن تب `data-pane="models"` با برچسب `🧠 مدیریت مدل‌های هوش مصنوعی` بعد از تب پروایدرها.
2. `ai.html`: **انتقال** (نه کپی) بلوک `id="model-section"` (خط ۸۷–۱۶۸) به یک بخش جدید `<section id="pane-models">` بین پایان `pane-providers` و شروع `pane-status`. عنوان کارت از «🧭 مدیریت و انتخاب مدل‌ها» به عنوان تب تغییر می‌کند.
3. `ai.py`: سه redirect `#model-section` → `#pane-models`؛ helper `_refresh_redirect()` برای دو return تابع `handle_refresh_all_models` (فقط برای `_back_tab == "models"` هدایت می‌کند).
4. تست جدید `giso/tests/test_ai_models_tab.py`: بررسی ساختار قالب (یکتایی تب، قرارگیری کارت، تطابق `data-pane` و id) و helper redirect (بدون DB و بدون شبکه).

### آنچه تغییر نمی‌کند
- نام routeها، endpointها، نام فیلدهای فرم (`slot_1..3`، `category`، `provider`، `model`، `csrf_token`)، `save_model_section`، `build_model_section`، `MODEL_SECTION_CATEGORIES`، جدول دیتابیس، رجیستری پروایدرها، منطق failover، تحلیل و تولید تصویر، تب آینه گیسو، تب وضعیت، کارت پروایدرها.
- `selected_model` در کارت پروایدر (خط ۱۸۰) فقط نمایش است و انتخاب نیست؛ در تب پروایدرها می‌ماند.

## ۶. ریسک‌ها و محدودیت‌ها
- JS مرورگر تست نشد (در محیط مرورگر یا jsdom نیست و نصب مجاز نیست). ادعای رفتار مرورگر ثابت نمی‌شود؛ فقط منطق و ساختار بررسی می‌شوند.
- ظاهر موبایل فقط از روی CSS موجود (`.pnl-tabs` با اسکرول افقی) بررسی شد؛ مشاهده بصری انجام نشد.
- فایل‌های `ai.html` و `ai.py` خطوط ترکیبی CRLF/LF دارند؛ ویرایش باید بایت‌به‌بایت انجام شود.
- همپوشانی تب آینه گیسو با کارت عمومی باقی می‌ماند (بخش ۴).
- تست‌های موجود `test_admin_ai_panel.py` دیتابیس واقعی را استفاده می‌کنند؛ فقط روی کپی اجرا می‌شوند.
