# testgiso.md — دستور تست زنده گیسو (برای ایجنت روی کامپیوتر کاربر)

ایجنت این فایل را از اول تا آخر بخواند، سپس دستورها را به ترتیب اجرا کند. در پایان فهرست آنچه تأیید شد را بدهد.

## ۰. قوانین (اجباری)

1. **دیتابیس زنده را تغییر نده.** روی کپی کار کن:
   ```bash
   cp -r . ../giso_test && cd ../giso_test
   ```
   اگر کلیدهای AI داخل دیتابیس‌اند، فایل DB را کپی کن و حذف نکن.
2. **کلید API را هیچ‌جا چاپ، ذخیره یا commit نکن.** کلیدها از `.env` یا پنل AI گیسو خوانده می‌شوند.
3. **commit و push نکن** مگر کاربر صریحاً بگوید.
4. **`selected_model` را تغییر نده.** باز کردن پنل یا Discovery هیچ state را عوض نمی‌کند.
5. **تست رنگ مو انجام نشود.**
6. **بعد از هر مرحله گزارش کوتاه فارسی بده و منتظر تأیید کاربر بمان.** مرحله‌ی بعد را شروع نکن.

## ۱. بودجه‌ی توکن

- کل تماس‌های زنده با AI: **حداکثر ۱۵**.
- متن: برای هر provider فعال **یک** تماس، `max_tokens` ≤ ۱۶، پیام `ping`.
- تصویر: **یک** عکس، **یک** استایل (`natural`)، حداکثر **یک** retry.
- ویجت یا مشاور: **یک** پیام کوتاه (≤ ۲۰ کلمه) برای هر کدام.
- pytest را **بدون** کلید AI اجرا کن. اگر تستی تماس شبکه‌ای زد، متوقف شو و گزارش بده.
- فایل‌های بزرگ را نخوان: `graphify-out/` (به‌ویژه `graph.json`) و لاگ‌های کامل. از `grep` و `pytest -q --tb=line` استفاده کن.
- حلقه یا retry بی‌نهایت نزن.

## ۲. راه‌اندازی

- Python **3.11**.
  ```bash
  python -m venv .venv
  .venv/bin/pip install -r requirements.txt
  .venv/bin/pip install -r requirements-landmarks.txt
  .venv/bin/pip install --no-deps mediapipe==0.10.21
  ```
  `--no-deps` برای mediapipe اجباری است (طبق `requirements-landmarks.txt`).
- `.env` در ریشه: `SECRET_KEY` اجباری است.
- اجرای سایت گیسو (پورت ۵۰۰۱):
  ```bash
  SECRET_KEY=... GISO_BOT_ENABLED=0 PYTHONPATH=. python -m giso.app
  ```
  `python giso/app.py` مستقیم کار نمی‌کند. سلامت: `GET /` و `GET /api/ai-widget/init` باید ۲۰۰ بدهند.
- ربات بله: اگر توکن ندارد، تست ربات را انجام نده و در گزارش بنویس.

## ۳. اولویت ۱: مدیریت هوش مصنوعی و اتصال providerها

**بررسی‌ها:**
- پنل ادمین، تب مدل‌ها. دسته‌ها: `text`، `image_analysis`، `image_generation`، `output_evaluation`.
- ذخیره‌ی اسلات، فعال/غیرفعال، `image_kind`، `endpoint_override`، کارت وضعیت آمادگی.
- **آدرس GapGPT را تأیید کن قبل از تماس.** در کد دو آدرس است:
  - `giso/ai_models_registry.py` خط ۱۵۱: `https://api.gapgpt.com/v1`
  - `bot_edu/config.py` خط ۱۵۵: `https://api.gapgpt.app/v1`
  هیچ‌کدام را بدون تأیید کاربر تغییر نده.

**تست زنده:**
- برای هر provider فعال یک تماس متنی کوتاه.
- ثبت کن: نام provider، کد پاسخ، متن خطا (حداکثر ۳۰۰ کاراکتر).

**نشانه‌ی خرابی:**
- اسلات ذخیره شده ولی runtime از provider دیگری استفاده می‌کند.
- کارت «آماده» است ولی کلید ندارد.

**کد مرتبط:** `giso/ai_models_registry.py`، `giso/ai_runtime_policy.py`، `giso/buti_ai/ai_models.py`.

## ۴. اولویت ۲: آنالیز ابرو و لب (خروجی تصویر)

**مسیر:** عکس → تشخیص ماسک با mediapipe → inpainting → تصویر خروجی.

**دستور (یک عکس، یک استایل):**
```bash
SECRET_KEY=... PYTHONPATH=bot_edu:. python tools/eyebrow_live_check.py --photo path/to/face.jpg --out eyebrow_live_out
```
- **انتظار:** خط `REAL AI RESULT SAVED` و `exit 0`.
- اگر `NOT A REAL AI RESULT` بود: کد خطا و متن خطای provider را دقیق گزارش کن.

**بررسی‌های دستی:**
- تصویر خروجی واقعاً تغییر کرده باشد.
- fallback تناسبی به‌عنوان نتیجه‌ی AI قبول نشود.
- لب: یک تماس از مسیر سایت.
- provider از اسلات مدیریت AI گرفته شود. متغیر محیطی فقط وقتی اسلات خالی است.

**کد مرتبط:** `giso/buti_ai/eyebrow/image_generation.py`، `giso/buti_ai/eyebrow/landmarks.py`.

**بعد از اولویت ۱ و ۲ گزارش بده و منتظر تأیید بمان.**

## ۵. مراحل بعدی (فقط بعد از تأیید کاربر)

- **مرحله ۳:** خروجی نهایی، ویجت، آنالیز مو و پوست، مشاور سوپرادمین. رنگ مو تست نشود.
  - ویجت: `GET /api/ai-widget/init` باید `actions` برابر `[]` داشته باشد و `starter_prompts` نداشته باشد.
  - ویجت چت بدون ورود، وقتی اعتبار روشن است: باید **۴۰۲** بدهد.
  - آنالیز پوست و مو (بدون رنگ): هر کدام یک عکس، یک تماس.
  - مشاور: یک سؤال کوتاه با حساب سوپرادمین.
- **مرحله ۴:** صفحه‌های سایت و ادمین.
  - کاربر عادی: تب‌های «سالن زیبایی من» (سالن‌ها، رزروها، گفتگوی مرکز، آنالیزها، مدیریت سالن). ۲۰۰ برای صفحه‌های مجاز؛ ۳۰۲ یا ۴۰۳ برای غیرمجاز.
  - سوپرادمین: `/admin/*` با ۲۰۰ و بدون ۵۰۰ یا خطای قالب.
  - صفحه‌ی آنالیزها: دکمه‌ی «🛒 محصولات پیشنهادی من» باید در **بات** باشد، نه در صفحه‌ی سایت.
  - بات: منوی آنالیز فقط برای سوپرادمین (`_admin_has_analysis_access` در `giso/bot.py`).
- **مرحله ۵:** کل تست‌ها روی کپی تازه:
  ```bash
  SECRET_KEY=test-only-secret-key python -m pytest -q -p no:cacheprovider giso/tests
  ```
  انتظار: **۲۷ رد، ۹۰۹ قبول، ۴ رد شده**. هر رد که در فهرست زیر نیست، شکست جدید است.

## ۶. روش بررسی و اصلاح

1. خطا را دقیق ثبت کن: درخواست، پاسخ، خط لاگ، متن خطای provider، `فایل:خط`.
2. قبل از تغییر، کد را خط به خط با تست مقایسه کن. کدام درست است: تست یا کد؟
3. تست غلط است: تست را کوچک اصلاح کن.
4. کد خراب است: اصلاح حداقلی. ساختار را عوض نکن. وابستگی جدید نصب نکن. mediapipe را جز دستور بالا نصب نکن.
5. فقط تست مربوط را روی کپی تازه اجرا کن، بعد کل مجموعه.
6. هر تغییر را با نام فایل و خط گزارش کن.

## ۷. فهرست شکست‌های پایه (۲۷ مورد)

**ابرو (۴، نیاز به mediapipe):**
- `giso/tests/test_buti_ai_eyebrow_inpainting_request.py` (۳ مورد)
- `giso/tests/test_buti_ai_eyebrow_real_detector.py::test_project_eyebrow_sample_produces_trusted_real_mask`

**سالن زیبایی (۱۰):**
- `test_beauty_centers_stage10_analysis_integration.py::test_recommendations_use_owned_analysis_and_only_published_real_centers`
- `test_beauty_centers_stage12_site_menu.py::test_public_link_uses_the_same_responsive_navigation_container`
- `test_beauty_centers_stage13_home_card.py` (۳ مورد)
- `test_beauty_centers_stage14_seo.py::test_sitemap_query_and_detail_schema_only_allow_public_active_centers`
- `test_beauty_centers_stage7_notifications.py::test_center_request_status_report_and_message_hooks_exist`
- `test_beauty_centers_stage8_admin_bot.py` (۲ مورد)
- `test_phase4_beauty_owner_ui.py::test_owner_tabs_are_consistent_and_message_aware`

**بات، فروشگاه، پنل و متفرقه (۱۳):**
- `test_bot_permission_fix.py` (۴ مورد)
- `test_button_collision.py::test_hair_sale_report_new_name`
- `test_marketplace_buyer_photo_ui.py::test_listing_media_route_normalizes_legacy_static_prefix`
- `test_panel_authz_hair_shop.py::test_2b_normal_admin_can_only_moderate_pending_channel_imports`
- `test_panel_phase5.py` (۲ مورد)
- `test_panel_phase52.py::test_8_bot_compatibility_and_live_sync`
- `test_phase2_maintenance_admin_entry.py::test_env_documents_distinct_paths`
- `test_shop_buy_phase.py::test_9_admin_approve_flow`
- `test_shop_phase_b.py::test_6_7_admin_and_super_panel_shop`

## ۸. فرمت گزارش (فارسی، کوتاه)

- فهرست بررسی‌شده (مرحله و مورد)
- نتیجه‌ی هر تست زنده: قبول یا رد، با نام تست یا دستور
- نتیجه‌ی pytest: تعداد رد، قبول، رد شده، و شکست‌های جدید
- خرابی‌های واقعی و اصلاح‌ها (با نام فایل)
- آنچه فقط با چشم یا تست زنده قابل تأیید است (مثلاً کیفیت تصویر)
- آنچه انجام نشد و دلیلش
- تعداد تماس‌های زنده (از ۱۵)
