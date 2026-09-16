# 📘 راهنمای فنی ربات آموزشی صادقی

مرجع کامل توسعه و نگهداری — نسخهٔ بازنویسی‌شده بر اساس کد بهینه‌شده.

---

## فهرست

| # | بخش |
|---|---|
| ۱ | [نمای کلی](#۱-نمای-کلی) |
| ۲ | [راه‌اندازی](#۲-راهاندازی) |
| ۳ | [معماری و زنجیرهٔ Import](#۳-معماری-و-زنجیرهٔ-import) |
| ۴ | [ساختار دیتابیس](#۴-ساختار-دیتابیس) |
| ۵ | [ذخیره‌سازی هدفمند](#۵-ذخیرهسازی-هدفمند) |
| ۶ | [چرخهٔ یک Update](#۶-چرخهٔ-یک-update) |
| ۷ | [Stateها](#۷-stateها) |
| ۸ | [Callbackها](#۸-callbackها) |
| ۹ | [پنل کاربر](#۹-پنل-کاربر) |
| ۱۰ | [پنل ادمین](#۱۰-پنل-ادمین) |
| ۱۱ | [چندپلتفرمی](#۱۱-چندپلتفرمی) |
| ۱۲ | [پروکسی](#۱۲-پروکسی) |
| ۱۳ | [هوش مصنوعی](#۱۳-هوش-مصنوعی) |
| ۱۴ | [راهنمای توسعه](#۱۴-راهنمای-توسعه) |
| ۱۵ | [یار هوشمند شغلی](#۱۵-یار-هوشمند-شغلی) |
| ۱۶ | [معماری چندعاملی (Multi-Agent)](#۱۶-معماری-چندعاملی-multi-agent) |
| ۱۷ | [عیب‌یابی](#۱۷-عیبیابی) |

---

## ۱. نمای کلی

ربات آموزشی چندپلتفرمی روی **بله** (پایه) و **تلگرام** (ثانویه) با یک پایگاه کد مشترک.

| ویژگی | توضیح |
|---|---|
| پلتفرم پایه | بله — `https://tapi.bale.ai/bot` |
| پلتفرم ثانویه | تلگرام — با پشتیبانی پروکسی |
| کتابخانه | `python-telegram-bot==20.7` |
| دیتابیس | SQLite یکپارچه — `data/bot.db` (۴۸ جدول) |
| زبان رابط | فارسی |
| حجم کد | ۱۲ ماژول اصلی + پکیج `ai_mentor` — حدود ۲۲٬۰۰۰ خط |

**قابلیت‌ها:** دوره و سرفصل چندرسانه‌ای • سطح‌بندی XP و اعتبار • ماموریت • دعوت دوستان • گنجینه امتیازی • تیکت پشتیبانی • فروش نقدی • مرکز پیام‌رسانی • نظرسنجی • مدیریت پروایدرهای AI.

**یار هوشمند شغلی (`ai_mentor`):** مسیر شغلی با [معماری چندعاملی](#۱۶-معماری-چندعاملی-multi-agent) • یادگیری خُرد با محتوای Lazy • ترند بازار • گزارش آمادگی • گواهینامهٔ PDF • شبیه‌ساز مصاحبه • همزاد شغلی • مأموریت واقعی • یادگیری تیمی • پروفایل عمومی B2B • شارژ اعتبار با فیش.

---

## ۲. راه‌اندازی

```bash
git clone https://github.com/uname1370-create/bot-Edu.git
cd bot-Edu
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env      # مقادیر را ویرایش کنید
python bot.py
```

### متغیرهای `.env`

| متغیر | الزامی | توضیح |
|---|:---:|---|
| `BOT_TOKEN` | ✅ | توکن ربات بله |
| `ADMIN_IDS` | ✅ | شناسه‌های ادمین، جداشده با کاما |
| `SUPPORT_GROUP` | — | شناسهٔ گروه پشتیبانی |
| `BOT_USERNAME` | — | نام کاربری ربات (برای لینک دعوت) |
| `DB_PATH` | — | پیش‌فرض `data/bot.db` |
| `TELEGRAM_PROXY` | — | پروکسی تکی تلگرام |
| `TELEGRAM_PROXY_LIST` | — | چند پروکسی، جداشده با کاما |
| `AI_GROQ_API_KEY` | — | کلید Groq |
| `AI_OPENROUTER_API_KEY` | — | کلید OpenRouter |
| `AI_GAPGPT_API_KEY` | — | کلید GapGPT (ایرانی) |
| `AI_AVALAI_API_KEY` | — | کلید AvalAI (ایرانی) |
| `AI_CLOUDFLARE_API_KEY` | — | کلید Cloudflare |
| `AI_CLOUDFLARE_API_ROOT` | — | آدرس حساب Cloudflare |

> ⚠️ **هیچ توکن یا کلیدی نباید داخل کد پایتون نوشته شود.** `.env` در `.gitignore` است.

**توکن تلگرام** از داخل ربات ثبت می‌شود: پنل مدیریت ← تنظیمات عمومی ← مدیریت پلتفرم‌ها.

---

## ۳. معماری و زنجیرهٔ Import

زنجیره یک‌طرفه است — هیچ import حلقوی وجود ندارد:

```
ai_brain.py                (stdlib + httpx — مغز هوش مصنوعی)
  └── db.py                (جدول‌ها و اتصال SQLite + re-export توابع AI)
        └── config.py      (داده‌های جهانی + بارگذاری/ذخیره)
              └── core.py  (منطق کسب‌وکار + re-export ask_ai)
                    └── ui.py    (کیبوردها و صفحات)
                          ├── proxy_manager.py
                          ├── platform_runtime.py
                          ├── handlers_ai.py
                          ├── handlers_admin.py
                          ├── handlers_messaging.py
                          ├── ai_mentor/        (یار هوشمند شغلی)
                          │     ├── core.py     (UserJourneyContext)
                          │     ├── agents/     (سه ایجنت)
                          │     └── prompts/    (پرامپت‌های txt)
                          └── handlers.py
                                └── bot.py     (نقطهٔ ورود)
```

| ماژول | خط | مسئولیت |
|---|---:|---|
| `ai_brain.py` | ۵۸۱ | 🧠 مغز AI: جدول‌ها، پروایدرها، `ask_ai`/`ask_ai_fast` |
| `db.py` | ۴۶۰ | تعریف جدول‌ها، اتصال SQLite، re-export توابع AI |
| `config.py` | ۱۵۱۶ | دیکشنری‌های جهانی، `_load_*`/`_save_*`، `setup_data()` |
| `core.py` | ۱۸۷۵ | کاربر، XP، دسترسی، چندپلتفرمی، re-export `ask_ai` |
| `ui.py` | ۲۱۶۲ | کیبوردها و توابع `show_*` |
| `handlers.py` | ۵۱۶۹ | `button_handler`، `handle_text`، `handle_media` |
| `handlers_ai.py` | ۴۶۶ | پنل مدیریت پروایدرهای AI |
| `handlers_messaging.py` | ۷۸۹ | مرکز پیام‌رسانی و ارسال گروهی |
| `handlers_admin.py` | ۱۷۹ | پاسخ تیکت، تأیید خرید نقدی |
| `proxy_manager.py` | ۵۴۲ | تهیه، تست و ذخیرهٔ پروکسی |
| `platform_runtime.py` | ۲۲۶ | روشن/خاموش کردن زندهٔ تلگرام |
| `bot.py` | ۳۴۱ | ساخت Application و اجرای هر دو پلتفرم |

### ⚠️ تله: `ai_mentor/core.py` با `core.py` ریشه فرق دارد

از معماری چندعاملی به بعد، **دو فایل به نام `core.py`** در پروژه وجود دارد:

| فایل | نقش |
|---|---|
| `core.py` (ریشه) | منطق کسب‌وکار ربات — کاربر، XP، `ask_ai` |
| `ai_mentor/core.py` | `UserJourneyContext` و توابع مشترک ایجنت‌ها |

این تداخل ایجاد نمی‌کند چون پکیج `ai_mentor` از **absolute import** استفاده می‌کند:

```python
from core import ask_ai          # ✅ core.py ریشه را می‌گیرد
from . import core               # ✅ ai_mentor/core.py را می‌گیرد
from .core import UserJourneyContext   # ✅ همان فایل داخلی
```

⛔ هرگز داخل `ai_mentor` ننویسید `import core` با انتظار گرفتن فایل داخلی — نتیجه فایل ریشه است.

### ماژول متمرکز مغز هوش مصنوعی (ai_brain)

پیش‌تر منطق AI بین دو فایل بزرگ پخش بود: تعریف جدول‌ها و توابع دیتابیسِ پروایدرها در `db.py` و منطق فراخوانی مدل‌ها در انتهای `core.py`. این پراکندگی باعث می‌شد فایل‌های اصلی شلوغ شوند و پیدا کردن یا تغییر منطق AI دشوار باشد.

در بازآرایی، همهٔ این کدها به فایل واحد **`ai_brain.py`** منتقل شدند تا اصل **تفکیک مسئولیت‌ها (Separation of Concerns)** رعایت شود: `db.py` فقط مسئول اتصال و جدول‌های عمومی است، `core.py` فقط منطق کسب‌وکار، و کل «مغز هوش مصنوعی» در یک نقطهٔ مشخص قرار دارد.

**هیچ نامی تغییر نکرد و هیچ قابلیتی اضافه یا حذف نشد** — فقط محل نگهداری کد عوض شد. نتیجه: `db.py` از ۶۰۱ به ۴۴۴ و `core.py` از ۲۱۵۰ به ۱۸۷۵ خط کاهش یافت.

محتویات `ai_brain.py`:

| بخش | مبدأ |
|---|---|
| جدول‌های `ai_providers` و `ai_checks_log` + `init_ai_tables()` | `db.py` |
| `get_ai_provider`، `list_ai_providers`، `add_ai_provider`، `delete_ai_provider`، `toggle_ai_provider`، `update_ai_provider_field`، `save_ai_check_result`، `ai_provider_count`، `_ai_now`، `_AI_EDITABLE` | `db.py` |
| `ask_ai`، `ask_ai_fast`، `check_ai_provider`، `check_all_ai_providers`، `ai_pick_preferred_model` و ۶ تابع کمکی | `core.py` |

### سازگاری عقب‌رو با Re-export

`db.py` و `core.py` همان نام‌ها را دوباره export می‌کنند، پس **هیچ importی در پروژه نیاز به تغییر نداشت**:

```python
from db import get_ai_provider, list_ai_providers   # ✅ کار می‌کند
from core import ask_ai, ask_ai_fast                # ✅ کار می‌کند (ai_mentor و handlers_ai)
```

این نام‌ها **همان شیء** هستند، نه کپی — یعنی `db.get_ai_provider is ai_brain.get_ai_provider`. بنابراین ماژول `ai_mentor` و `handlers_ai` بدون یک خط تغییر کار می‌کنند.

⚠️ **قاعدهٔ جلوگیری از حلقهٔ import:** `ai_brain.py` هیچ چیزی را در سطح فایل از `db` نمی‌گیرد؛ `get_conn()` و قفل نوشتن با import داخل تابع حل شده‌اند. قفل هم پراکسی به `db._lock` است تا همان قفل مشترک بماند و هماهنگی نوشتن نشکند.

### قاعدهٔ مرجع مشترک

`config.py` دیکشنری‌های جهانی را نگه می‌دارد. ماژول‌های دیگر با `from config import USERS` به **همان شیء** اشاره می‌کنند. بنابراین `setup_data()` باید از `update()` و `extend()` استفاده کند، نه انتساب مجدد:

```python
USERS.update(_load_users())     # ✅ مرجع حفظ می‌شود
USERS = _load_users()           # ❌ مرجع سایر ماژول‌ها می‌شکند
```

---

## ۴. ساختار دیتابیس

فایل یکپارچه `data/bot.db` — SQLite با `journal_mode=WAL` و `synchronous=NORMAL`.

### ۴۸ جدول

| گروه | جدول‌ها |
|---|---|
| کاربران | `users`، `referrals`، `completed_missions`، `credits_paid` |
| آموزش | `courses`، `lessons`، `progress` |
| ماموریت و فروشگاه | `missions`، `shop_items`، `purchases` |
| پشتیبانی و فروش | `tickets`، `cash_sale_requests`، `cash_sale_settings` |
| دسترسی | `feature_access`، `user_feature_restrictions` |
| چندپلتفرمی | `platform_links`، `platform_admins`، `link_codes`، `admin_link_codes`، `bot_groups` |
| سیستم | `settings`، `bot_commands`، `survey_votes`، `delivery_reports` |
| هوش مصنوعی (مغز) | `ai_providers`، `ai_checks_log` |
| یار هوشمند — مسیر | `career_paths`، `path_steps`، `user_profiles` |
| یار هوشمند — بازار | `market_trends`، `market_trend_history` |
| یار هوشمند — مالی | `ai_settings`، `ai_usage_logs`، `ai_credit_packages`، `ai_credit_purchases`، `admin_payment_info` |
| یار هوشمند — AI | `ai_model_routing`، `ai_chat_history` |
| یار هوشمند — فاز ۳ | `ai_career_reports`، `ai_certificates`، `interview_simulations`، `ai_career_twin` |
| یار هوشمند — فاز ۴ | `real_missions`، `user_missions`، `learning_teams`، `team_members`، `public_profiles` |
| داخلی | `sqlite_sequence` |

### جدول‌های AI

> 📌 پس از بازآرایی، تعریف این دو جدول در **`ai_brain.py`** است (نه `db.py`). تابع `init_db()` هنگام راه‌اندازی `ai_brain.init_ai_tables(conn)` را صدا می‌زند، پس جدول‌ها در همان `data/bot.db` ساخته می‌شوند.

**`ai_providers`** — ۱۷ ستون. کلید اصلی `name`. مهم‌ترین‌ها: `kind` (`openai` یا `cloudflare`)، `api_key`، `base_url`، `api_root`، `timeout`، `fallback_models` (JSON)، `headers` (JSON)، `enabled`، `is_iranian`، `last_ok`، `last_model`.

**`ai_checks_log`** — تاریخچهٔ تست پروایدرها. به‌صورت خودکار روی **۱۰۰ رکورد آخر** هرس می‌شود.

### مهاجرت ستون

`_migrate_columns()` در `db.py:50` ستون‌های جدید را با `ALTER TABLE` به دیتابیس‌های قدیمی اضافه می‌کند — بدون از دست رفتن داده. برای افزودن ستون جدید، یک سطر به لیست `migrations` اضافه کنید.

### هرس خودکار

| جدول | سقف |
|---|---|
| `delivery_reports` | `MAX_DELIVERY_REPORTS` |
| `ai_checks_log` | ۱۰۰ رکورد |

---

## ۵. ذخیره‌سازی هدفمند

> بهینه‌سازی کلیدی نسخهٔ فعلی.

### مسئله

نسخهٔ قبلی `_save_users()` در هر فراخوانی **همهٔ** کاربران را بازنویسی می‌کرد: ۴ دستور SQL برای هر کاربر. با ۲۰۰۰ کاربر حدود ۷۵۰ms — و چون نوشتن‌ها همگام‌اند، کل event loop قفل می‌شد و ربات به هیچ کاربری پاسخ نمی‌داد.

### راهکار

`config.py` برای هر کاربر یک **اثر انگشت** (`_user_fingerprint`) از دقیقاً همان فیلدهایی می‌سازد که در دیتابیس نوشته می‌شوند. در ذخیرهٔ بعدی فقط رکوردهایی که اثر انگشتشان تغییر کرده نوشته می‌شوند.

```python
_USER_FP  = {}   # {uid_str: fingerprint}
_PLINK_FP = {}   # {(platform, platform_user_id): fingerprint}
```

همین الگو روی `_save_platform_links()` هم اعمال شده، چون `touch_platform_activity()` آن را با هر پیام تلگرام صدا می‌زند.

### نتیجه

| کاربران | قبل | بعد |
|---:|---:|---:|
| ۵۰۰ | ۱۴٫۱ ms | ۱٫۱ ms |
| ۲۰۰۰ | ۵۳٫۹ ms | ۳٫۰ ms |
| ۵۰۰۰ | ۱۴۳٫۶ ms | ۸٫۲ ms |

### تضمین‌های ایمنی

- **هیچ نقطهٔ فراخوانی تغییر نکرده** — `save("users")` دقیقاً مثل قبل استفاده می‌شود.
- اثر انگشت‌ها **فقط پس از commit موفق** به‌روز می‌شوند؛ اگر تراکنش rollback شود، رکورد در دور بعد دوباره نوشته می‌شود.
- در اولین ذخیره پس از راه‌اندازی، حافظهٔ اثر انگشت خالی است ⇒ همه نوشته می‌شوند (رفتار قبلی).
- `_save_users` هرگز ردیفی را حذف نمی‌کرد؛ این رفتار عیناً حفظ شده. برای `platform_links` منطق حذف با تفاضل مجموعه‌ها بازسازی شده است.
- خروجی دیتابیس با نسخهٔ قبلی **بیت‌به‌بیت یکسان** است (۱۶ سناریوی متوالی تأیید شد).

### ابطال دستی

اگر کاربری را از `USERS` حذف کردید، حتماً اثر انگشتش را باطل کنید:

```python
USERS.pop(str(uid), None)
config.invalidate_user_cache(uid)     # بدون آرگومان = ابطال کامل
save("users")
```

### توابعی که از قبل هدفمند بودند

`_save_tickets`، `_save_cash_sales` (با `_db_id` و `UPDATE`)، `_save_progress` و `_save_courses` (با تفاضل مجموعه‌ها) — تغییری نکرده‌اند.

---

## ۶. چرخهٔ یک Update

```
Update
  └── bot.py:_register_handlers   ثبت روی هر دو Application
        ├── group 0  CommandHandler("start")   → handlers.start
        ├── group 0  CommandHandler("myid")
        ├── group 1  CallbackQueryHandler      → handlers.button_handler
        ├── group 2  MessageHandler(CONTACT)   → handlers.handle_contact
        ├── group 2  MessageHandler(PHOTO|VIDEO|DOCUMENT) → handlers.handle_media
        ├── group 3  MessageHandler(TEXT)      → handlers.handle_text
        └── group 4  MessageHandler(NEW_CHAT_MEMBERS) → handlers.handle_new_member
```

### تشخیص پلتفرم

`core.py` از `contextvars.ContextVar` با پیش‌فرض `"bale"` استفاده می‌کند. هر update در یک task جدا پردازش می‌شود، پس پلتفرم جاری بین دو ربات قاطی نمی‌شود.

- `get_current_platform()` — پلتفرم update فعلی
- `platform_raw_id(user)` — شناسهٔ واقعی در آن پلتفرم
- `canonical_user_id(platform, raw_id)` — نگاشت به کاربر اصلی (بله)
- `effective_user(user)` — کاربر اصلی با نام نمایشی پلتفرم مبدأ

### پاک‌سازی خودکار state

در ابتدای `button_handler`، اگر callback با هیچ‌کدام از `_STATE_KEEPING_PREFIXES` شروع نشود، state کاربر پاک می‌شود. این از «تلهٔ state» جلوگیری می‌کند — حالتی که کاربر وسط یک فلو دکمهٔ دیگری می‌زند و ورودی بعدی‌اش اشتباه تفسیر می‌شود.

۱۰ پیشوند مستثنا (ادامهٔ فلوی چندمرحله‌ای):

```
ai_kind|  src|  a_cmd_type|  a_cmd_scope|  a_cmd_match|
a_cmd_adminonly|  a_cmd_action|  a_item_kind|
a_mission_type|  a_mission_plat|
```

---

## ۷. Stateها

state در `ctx.user_data["state"]` نگه داشته می‌شود و در `handle_text` (و برای AI در `handlers_ai.handle_ai_state`) خوانده می‌شود. مجموعاً **۷۳ state**.

| گروه | Stateها |
|---|---|
| دوره | `wait_course_title` `wait_ctitle` `wait_cdesc` `wait_cjoin` `wait_cref` `wait_ccredit` |
| سرفصل | `wait_ltitle` `wait_lt_edit` `wait_ljoin` `wait_lref` `wait_lcredit` |
| منبع سرفصل | `wait_src_text` `wait_src_link` `wait_src_file` `wait_src_forward` |
| ماموریت | `wait_mission_title` `wait_mission_desc` `wait_mission_type_select` `wait_mission_content` `wait_mission_xp` `wait_mission_credits` |
| گنجینه | `wait_item_name` `wait_item_kind` `wait_item_description` `wait_item_content` `wait_item_price` `wait_item_stock` |
| کاربر (ادمین) | `wait_user_search_id` `wait_user_xp_value` `wait_user_xp_delta` `wait_user_credit_value` `wait_user_credit_delta` `wait_user_mute_duration` |
| دسترسی | `wait_feature_value` `wait_feat_block_duration` |
| تنظیمات کلی | `wait_global_join` `wait_global_ref` `wait_global_credit` |
| دستورات | `wait_cmd_trigger` `wait_cmd_type` `wait_cmd_text_response` |
| فروش نقدی | `wait_cash_sale_price` `wait_cash_sale_note` `wait_cash_sale_method` `wait_cash_sale_xpreward` `wait_cash_sale_creditreward` `wait_cash_card_number` `wait_cash_card_holder` `wait_cash_bank_name` `wait_cash_fiche` `wait_pay_fiche` |
| پیام‌رسانی | `wait_bc_title` `wait_bc_desc` `wait_bc_content` `wait_bc_delay` `wait_bc_direct_target` |
| پلتفرم | `wait_platform_token` `wait_platform_uname` `wait_platform_support` |
| پروکسی | `wait_proxy_source` `wait_proxy_manual` |
| پشتیبانی | `wait_ticket` `wait_ticket_reply` |
| تلفن | `wait_phone` `wait_phone_secondary` |
| هوش مصنوعی | `wait_ai_name` `wait_ai_base_url` `wait_ai_api_key` `wait_ai_api_root` `wait_ai_timeout` `wait_ai_field` `wait_ai_prompt` |

> stateهای ماژول «یار هوشمند شغلی» (`wait_aim_*` و `wait_aima_*`) جدا هستند و در [بخش ۱۵](#۱۵-یار-هوشمند-شغلی) فهرست شده‌اند.

---

## ۸. Callbackها

`button_handler` شامل **۱۷۲ شاخه** و **۱۸۷ پیشوند یکتا** است. الگوی نام‌گذاری:

| پیشوند | دامنه |
|---|---|
| بدون پیشوند | کاربر عادی — `main` `courses` `profile` `missions` `shop` `referral` `support` `leaderboard` `latest_events` `career_path` |
| `course\|` `lesson\|` `lock\|` | مشاهدهٔ دوره و سرفصل |
| `checkaccess\|` `checkjoin\|` `checkref\|` | بررسی شرط دسترسی |
| `mission_view\|` `mission_done\|` | ماموریت |
| `shop_item\|` | خرید از گنجینه |
| `rate_course\|` | نظرسنجی پایان دوره |
| `a_*` | پنل ادمین (~۹۷ پیشوند) |
| `bc_*` | مرکز پیام‌رسانی |
| `ai_*` | مدیریت AI |
| `src\|` | انتخاب نوع منبع سرفصل |

### قالب پارامتر

پارامترها با `|` جدا می‌شوند:

```
a_item_view|s3              → یک پارامتر
ai_field|Groq|timeout       → دو پارامتر
a_users_list|0              → شمارهٔ صفحه
```

### حذف دومرحله‌ای

عملیات حذف با یک callback تأیید جداگانه انجام می‌شود (`*_yes` یا `ai_delok|`) تا حذف تصادفی رخ ندهد.

---

## ۹. پنل کاربر

### منوی اصلی (`ui.main_kb`)

```
📚 لیست دوره‌ها
🏆 پروفایل من        🎯 ماموریت‌ها
💎 گنجینه امتیازی    📰 آخرین اتفاقات
👥 دعوت دوستان
📞 پشتیبانی
```

ادمین منوی کوتاه‌شده می‌بیند: «📚 لیست دوره‌ها» و «👑 پنل مدیریت».

### سطح‌بندی

هفت سطح بر اساس XP: 🌱 تازه‌کار (۰) • 📗 یادگیرنده (۵۰) • 📘 کوشا (۱۵۰) • 📕 حرفه‌ای (۳۵۰) • 🎓 متخصص (۶۰۰) • 🏅 استاد (۱۰۰۰) • 💎 نخبه (۱۵۰۰).

ارتقاء سطح یک‌بار اعلام می‌شود (`level_announced`) و پیام تبریک به‌صورت غیرهمگام ارسال می‌گردد.

### شرط‌های دسترسی

`core.full_access_check()` به ترتیب بررسی می‌کند: عضویت اجباری ← دعوت اجباری ← اعتبار کلی ← اعتبار دوره ← اعتبار سرفصل. اعتبار کسرشده در `credits_paid` ثبت می‌شود تا دوباره کسر نشود.

---

## ۱۰. پنل ادمین

### منوی اصلی (`ui.admin_panel`)

```
📚 مدیریت دوره‌ها
🎯 مدیریت ماموریت‌ها
💎 مدیریت گنجینه
👥 مدیریت کاربران
🔑 دسترسی بخش‌ها
💵 درخواست‌های نقدی
📊 گزارشات و آمار
📣 مرکز پیام‌رسانی
⚙️ تنظیمات عمومی
```

### تنظیمات عمومی

```
🔒 تنظیم عضویت اجباری
👥 تنظیم دعوت اجباری
💰 تنظیم اعتبار اجباری
🤖 مدیریت دستورات ربات
📊 مدیریت نظرسنجی پایان دوره
🌐 مدیریت پلتفرم‌ها
🤖 مدیریت AI
```

### مرکز پیام‌رسانی

مسیرهای ارسال: **کاربران** (همه / دارای شماره) • **گروه‌ها و کانال‌ها** • **ربات‌های هر پلتفرم** • **مستقیم** به یک کاربر.

- تأخیر بین ارسال‌ها با `get_send_delay()` قابل تنظیم است (رعایت rate limit).
- نوار پیشرفت هر ۲۰ ارسال به‌روز می‌شود.
- عکس و ویدیو هنگام ارسال بین‌پلتفرمی دانلود و دوباره آپلود می‌شوند، چون `file_id` بین بله و تلگرام مشترک نیست.
- گزارش هر ارسال در `delivery_reports` ذخیره می‌شود.

### محل هندلرهای پنل ادمین

| پنل | فایل هندلر |
|---|---|
| پاسخ تیکت، تأیید خرید نقدی | `handlers_admin.py` |
| مدیریت پروایدرهای AI (`a_ai_panel`، `ai_*`) | `handlers_ai.py` |
| مدیریت یار هوشمند (`aim_a_*`) | `ai_mentor/ai_admin.py` |
| بقیهٔ شاخه‌های `a_*` | `handlers.py` |

📌 **دربارهٔ مدیریت AI:** منطق دیتابیس و فراخوانی مدل‌ها از `db.py` و `core.py` به **`ai_brain.py`** منتقل شد. اما لایهٔ نمایش تفکیک‌شده باقی ماند: هندلرهای پنل در `handlers_ai.py` و کیبوردهای آن (`ai_admin_kb`، `ai_providers_kb`، `ai_edit_fields_kb`، `ai_kind_kb`، `show_ai_panel`، `show_ai_list`، `show_ai_status`) در `ui.py` هستند. این تفکیک عمدی است: `ai_brain.py` فقط «مغز» است و هیچ پیامی به کاربر نمی‌فرستد.

### دسترسی ادمین

`core.is_admin(user, platform=None)` چهار مسیر را می‌پذیرد: حضور در `ADMIN_IDS` • شناسهٔ خام پلتفرم در `ADMIN_IDS` • ثبت در `platform_admins` • نگاشت canonical به یک ادمین.

---

## ۱۱. چندپلتفرمی

### مدل هویت

بله پلتفرم پایه است و شناسهٔ کاربر بله همان شناسهٔ اصلی (canonical) است. کاربر تلگرام از دو راه به حساب اصلی وصل می‌شود:

1. **کد اتصال** — کاربر در بله کد می‌گیرد و در تلگرام وارد می‌کند (`link_codes`، اعتبار ۲۴ ساعت).
2. **شمارهٔ تلفن** — اگر شماره قبلاً ثبت شده باشد، حساب‌ها ادغام می‌شوند (`via="phone"`).

نگاشت در `platform_links` با کلید `"{platform}:{platform_user_id}"` نگهداری می‌شود.

### روشن/خاموش کردن تلگرام

`platform_runtime.py` امکان کنترل زنده بدون ری‌استارت را می‌دهد:

| تابع | کار |
|---|---|
| `start_telegram()` | ساخت Application و شروع polling |
| `stop_telegram()` | توقف کامل و قطع اتصال |
| `apply_telegram_enabled(bool)` | اعمال وضعیت از پنل |
| `reload_telegram()` | راه‌اندازی مجدد با تنظیمات جدید |
| `telegram_status()` | وضعیت فعلی و پروکسی |

### ایزوله‌سازی خطا

در `bot.py:_run_all`، خرابی تلگرام نباید بله را بخواباند. هر پلتفرم در task جدا اجرا می‌شود و `asyncio.CancelledError` مهار می‌گردد.

---

## ۱۲. پروکسی

فقط برای تلگرام لازم است (بله در ایران فیلتر نیست).

### سه حالت

| حالت | رفتار |
|---|---|
| 🟢 `auto` | استفاده از لیست پروکسی دریافتی از منبع |
| 🟡 `manual` | فقط پروکسی‌هایی که ادمین وارد کرده |
| 🔴 `direct` | بدون پروکسی |

### پروتکل‌های پشتیبانی‌شده

| پروتکل | وضعیت |
|---|:---:|
| HTTP / HTTPS | ✅ |
| SOCKS5 | ✅ (نیازمند `httpx[socks]`) |
| MTProto | ❌ |

> **MTProto با Bot API کار نمی‌کند.** درخواست‌های Bot API روی HTTPS به `api.telegram.org` می‌روند و MTProxy فقط برای کلاینت رسمی تلگرام است. `httpx.Proxy("mtproto://…")` با `ValueError: Unknown scheme` رد می‌شود.

### ترتیب انتخاب

`bot.py:_collect_proxy_candidates()` به ترتیب بررسی می‌کند: پروکسی‌های ذخیره‌شدهٔ سالم ← `TELEGRAM_PROXY` ← `TELEGRAM_PROXY_LIST` ← اتصال مستقیم. اولین موردی که `getMe` را با موفقیت پاسخ دهد انتخاب می‌شود.

---

## ۱۳. هوش مصنوعی

### پروایدرهای پیش‌فرض

| نام | نوع | ایرانی |
|---|---|:---:|
| Groq | `openai` | — |
| OpenRouter | `openai` | — |
| LLM7 | `openai` | — |
| Cloudflare | `cloudflare` | — |
| GapGPT | `openai` | ✅ |
| AvalAI | `openai` | ✅ |

پروایدرها در `config.AI_DEFAULT_PROVIDERS` **بدون کلید** تعریف شده‌اند. کلیدها فقط از `.env` خوانده می‌شوند:

- `seed_ai_providers()` — ثبت اولیهٔ پروایدرها در دیتابیس
- `sync_ai_keys_from_env()` — همگام‌سازی کلیدها در هر راه‌اندازی

هر دو در `setup_data()` صدا زده می‌شوند.

### توابع core

| تابع | کار |
|---|---|
| `ask_ai(prompt, provider=None)` | پرسش از یک پروایدر مشخص |
| `ask_ai_fast(prompt)` | امتحان پروایدرها به ترتیب تا اولین پاسخ موفق |
| `check_ai_provider(name)` | تست سلامت یک پروایدر |
| `check_all_ai_providers()` | تست همه (موازی با `asyncio.gather`) |
| `ai_pick_preferred_model(p)` | انتخاب مدل از `fallback_models` |

### پنل مدیریت

مسیر: پنل مدیریت ← تنظیمات عمومی ← 🤖 مدیریت AI (فقط ادمین)

```
📋 فهرست پروایدرها
➕ افزودن پروایدر    ✏️ ویرایش پروایدر
⏯ فعال/غیرفعال      🗑 حذف پروایدر
🔄 بررسی یک پروایدر  🔁 بررسی همه
📊 گزارش وضعیت
💬 تست گفتگو
```

### امنیت ویرایش

`db._AI_EDITABLE` یک whitelist از ستون‌های مجاز است. هر نام ستون خارج از این فهرست رد می‌شود — جلوگیری از SQL injection در `update_ai_provider_field`.

---

## ۱۴. راهنمای توسعه

### افزودن دکمهٔ جدید

۱. دکمه را در کیبورد مربوطه در `ui.py` اضافه کنید:
```python
[btn("🆕 قابلیت جدید", "a_new_feature")]
```
۲. شاخه‌اش را در `handlers.button_handler` بنویسید:
```python
elif d == "a_new_feature":
    if not is_admin(user): return
    await show_new_feature(q)
```
۳. اگر ورودی متنی می‌خواهد، state ست کنید و در `handle_text` بخوانید.

> نام callback باید **یکتا** باشد. پیشوند ادمین همیشه `a_`.

### افزودن فیلد به کاربر

۱. ستون را به `_migrate_columns` در `db.py` اضافه کنید.
۲. در `_load_users` بخوانید و در `_save_users` بنویسید.
۳. **فیلد را به `_user_fingerprint` اضافه کنید** — در غیر این صورت تغییراتش ذخیره نمی‌شود.
۴. مقدار پیش‌فرض را در `core._migrate_user` بگذارید.

### افزودن جدول جدید

۱. `CREATE TABLE` را در `db._create_tables` بنویسید (به‌همراه ایندکس لازم).
۲. `_load_x()` و `_save_x()` را در `config.py` اضافه کنید.
۳. کلید را به `_SAVE_MAP` اضافه کنید.
۴. بارگذاری را به `setup_data()` اضافه کنید.

> اگر جدول **مربوط به AI** است، به‌جای `db.py` آن را در `ai_brain.AI_SCHEMA` بنویسید تا مغز هوش مصنوعی یکجا بماند.

### افزودن پروایدر AI

از پنل: مدیریت AI ← ➕ افزودن پروایدر. برای پروایدر پیش‌فرض، یک ورودی به `config.AI_DEFAULT_PROVIDERS` با `env_key` اضافه کنید و متغیرش را در `.env.example` مستند کنید.

### قواعد الزامی

| # | قاعده |
|---|---|
| ۱ | هیچ دکمه یا قابلیت موجودی نباید خراب شود — فقط افزودن. |
| ۲ | دیتابیس یکپارچه در `data/bot.db`. فایل جانبی نسازید. |
| ۳ | هیچ توکن یا کلیدی داخل کد پایتون نوشته نشود. |
| ۴ | پس از حذف کاربر، `invalidate_user_cache(uid)` را صدا بزنید. |
| ۵ | در `setup_data` از `update`/`extend` استفاده کنید، نه انتساب. |
| ۶ | نوشتن در دیتابیس داخل حلقهٔ ارسال گروهی ممنوع. |
| ۷ | ⛔ `ai_brain.py` را تغییر ندهید — فقط مغز AI آنجاست. |
| ۸ | کد ماژول یار هوشمند فقط داخل `ai_mentor/` نوشته شود. |
| ۹ | `ai_mentor` برای AI فقط `ask_ai`/`ask_ai_fast` را از `core.py` می‌گیرد، نه مستقیم از `ai_brain`. |
| ۱۰ | پیشوند callback: `aim_` (کاربر) و `aim_a_` (ادمین). پیشوند state: `wait_aim_` و `wait_aima_`. |
| ۱۱ | پرامپت ایجنت‌ها در فایل `.txt` باشد، نه داخل کد. |
| ۱۲ | هر ایجنت فقط یک مسئولیت. |
| ۱۳ | قبل از خواندن گام/مسیر، مالکیت را بررسی کنید (`get_owned_step`) — ضد IDOR. |
| ۱۴ | اعتبار را در لحظهٔ ارائهٔ خدمت کسر کنید (`can_afford` سپس `check_and_deduct_credits`)، و در خطا `refund()`. |
| ۱۵ | پرامپت حاوی نمونهٔ JSON را با `.replace()` پر کنید، نه `.format()`. |

### تست پیش از commit

```bash
python -m py_compile *.py ai_mentor/*.py ai_mentor/agents/*.py
python -m pyflakes  *.py ai_mentor/*.py ai_mentor/agents/*.py
```

برای تغییرات ماژول یار هوشمند، این موارد را هم دستی بررسی کنید:

| بررسی | چرا |
|---|---|
| هر `btn(...)` یک شاخهٔ هندلر دارد | دکمهٔ مرده = کلیک بی‌اثر برای کاربر |
| هر state هم ست می‌شود هم خوانده | state یتیم = ورودی کاربر بلعیده می‌شود |
| حداکثر ۲ دکمه در هر ردیف | خوانایی در موبایل |
| مسیر قدیمی و دیتابیس قدیمی هنوز کار می‌کنند | کاربران فعلی نباید مسیرشان را از دست بدهند |

> سندباکس توسعه اینترنت ندارد؛ برای تست فلوی AI تابع `ai_core._ask` را mock کنید و پاسخ‌های آماده به آن بدهید.

---

## ۱۵. یار هوشمند شغلی

ماژول جدا در پوشهٔ `ai_mentor/`. کدهای اصلی ربات دست‌نخورده‌اند و اتصال فقط از سه نقطه انجام می‌شود.

### ⚠️ نکتهٔ حیاتی: پیشوند `aim_` نه `ai_`

پیشوند `ai_` از قبل کاملاً توسط **پنل مدیریت پروایدرهای AI** گرفته شده و در `handlers.py` با شرط زیر مستقیم به مسیر ادمین می‌رود:

```python
elif d == "a_ai_panel" or d.startswith(("ai_", "a_ai_")):
    if not is_admin(user): return      # ← کاربر عادی همین‌جا بلاک می‌شود
```

اگر این ماژول هم از `ai_` استفاده می‌کرد، **همهٔ دکمه‌های کاربر عادی کار نمی‌کردند**. به همین دلیل:

| بخش | پیشوند callback | پیشوند state |
|---|---|---|
| کاربر | `aim_` | `wait_aim_` |
| ادمین | `aim_a_` | `wait_aima_` |

به همین ترتیب stateها `wait_aim_*` هستند تا با `wait_ai_*` پنل پروایدر قاطی نشوند.

### فایل‌ها

| فایل | خط | نقش |
|---|---:|---|
| `ai_db.py` | ۲۱۰۹ | ۳۴ جدول + توابع دیتابیس + مهاجرت ستون |
| `ai_handlers.py` | ۲۲۸۱ | هندلر کاربر + FSM + ارکستراسیون ایجنت‌ها |
| `ai_core.py` | ۱۱۰۰ | اعتبار، مسیریابی مدل، گزارش، گواهینامه، شبیه‌سازها |
| `ai_admin.py` | ۷۷۵ | هندلر ادمین |
| `ai_ui.py` | ۵۶۶ | کیبوردها |
| `ai_prompts.py` | ۲۰۴ | پرامپت قابلیت‌های جانبی (نه ایجنت‌ها) |
| `ai_market.py` | ۱۲۸ | اسکن ترند بازار |
| `core.py` | ۳۰۹ | `UserJourneyContext` + توابع مشترک ایجنت‌ها |
| `agents/career_interview.py` | ۵۴۳ | 🤖 ایجنت ۱ — مصاحبه‌گر شغلی |
| `agents/learning_mentor.py` | ۲۹۵ | 🤖 ایجنت ۳ — منتور آموزشی |
| `agents/roadmap_builder.py` | ۲۵۷ | 🤖 ایجنت ۲ — معمار نقشه راه |
| `prompts/*.txt` | ۲۴۷ | پرامپت سه ایجنت — **خارج از کد** |

> جزئیات کامل سه ایجنت در [بخش ۱۶](#۱۶-معماری-چندعاملی-multi-agent).

### جدول‌های ماژول (۳۴ جدول)

| جدول | ستون‌های کلیدی |
|---|---|
| `career_paths` | `id`، `user_id`، `target_job`، `interview_data`(JSON)، `status`(active/completed/archived)، **`interview_data_json`**(خروجی ایجنت ۱)، **`roadmap_json`**(خروجی ایجنت ۲) |
| `path_steps` | `id`، `path_id`(FK)، `step_number`، `step_type`(lesson/course/ai_challenge/resource)، `title`، `content`(JSON)، **`content_json`**(محتوای Lazy)، `status`(locked/active/completed)، `ai_feedback`(JSON) |
| `user_profiles` | `user_id`(PK)، `first_name`، `last_name`، `age`، `city` |
| `market_trends` | `skill_name`(UNIQUE)، `demand_count`، `source`، `reason` |
| `market_trend_history` | تاریخچهٔ ماهانه برای نمودار رشد |
| `ai_settings` | `setting_key`(PK)، `setting_value` — تعرفه‌ها و کلیدها |
| `ai_usage_logs` | `user_id`، `action_type`، `cost_credits`، `ai_model_used` — هرس روی ۵۰۰ رکورد |
| `ai_model_routing` | `action_type`(PK)، `primary_model`، `fallback_models`(JSON)، `cost_per_request` |
| `ai_chat_history` | `user_id`، `path_id`، `step_id`، `role`، `content` |
| `ai_credit_packages` | `amount`، `price`، `is_active` — بسته‌های شارژ داینامیک |
| `ai_credit_purchases` | فیش واریزی و وضعیت تأیید |
| `admin_payment_info` | تک‌ردیفی — شمارهٔ کارت و نام صاحب حساب |
| `ai_career_reports` | گزارش آمادگی شغلی هر مسیر |
| `ai_certificates` | گواهینامهٔ PDF + `certificate_id` یکتا |
| `interview_simulations` | شبیه‌ساز مصاحبه — ۱۰ سؤال + نمره |
| `ai_career_twin` | شبیه‌سازی همزاد شغلی |
| `real_missions` / `user_missions` | مأموریت واقعی و ارسال کاربر |
| `learning_teams` / `team_members` | یادگیری تیمی |
| `public_profiles` | پروفایل عمومی B2B + کد استعلام |

#### مهاجرت ستون‌های چندعاملی

سه ستون `interview_data_json`، `roadmap_json` و `content_json` با تابع `_migrate_agent_columns()` به دیتابیس‌های قدیمی اضافه می‌شوند. چون SQLite برای ستون تکراری خطا می‌دهد، اول `PRAGMA table_info` خوانده می‌شود:

```python
cols = {r[1] for r in c.execute(f"PRAGMA table_info({table})").fetchall()}
if column not in cols:
    c.execute(f"ALTER TABLE {table} ADD COLUMN {column} {decl}")
```

روی دیتابیس قدیمی تست شده: ستون‌ها اضافه می‌شوند و **دادهٔ قبلی دست‌نخورده می‌ماند**.

> `content` و `content_json` هم‌زمان نوشته می‌شوند و در خواندن با هم ادغام می‌گردند (`_step_row`). دلیل: کد قدیمی `content` را می‌خواند و معماری جدید `content_json` را؛ این‌طور هر دو یک دادهٔ واحد می‌بینند.

### Callbackها

**کاربر (۶۳ عدد):**

| گروه | Callbackها |
|---|---|
| مسیر (چندعاملی) | `aim_start` `aim_pick_path\|{n}` `aim_paths_again` `aim_confirm_path` `aim_continue` `aim_step\|{id}` `aim_answer\|{id}` `aim_done\|{id}` `aim_locked` |
| منو و پروفایل | `aim_menu` `aim_profile` `aim_edit_profile` `aim_edit_field\|{f}` `aim_guide_pricing` `aim_settings` `aim_balance` `aim_noop` |
| مدیریت مسیرها | `aim_paths` `aim_path_view\|{id}` `aim_path_archive\|{id}` `aim_path_activate\|{id}` `aim_path_delete\|{id}` |
| ترند بازار | `aim_trends` `aim_trends\|{view}` `aim_trends_refresh` `aim_add_trend\|{skill}` |
| یادگیری و کمک | `aim_learn` `aim_chat` `aim_chat_help\|{id}` `aim_help_clear\|{id}` `aim_history` |
| گزارش و گواهینامه | `aim_report` `aim_reports` `aim_report_path\|{id}` `aim_report_new\|{id}` `aim_report_list\|{id}` `aim_report_view\|{id}` `aim_certs` `aim_cert_get\|{id}` |
| شبیه‌ساز مصاحبه | `aim_interview_sim` `aim_sim_custom` `aim_sim_go\|{id}` `aim_sim_resume` `aim_sim_skip` `aim_sim_stop` `aim_sim_history` |
| همزاد شغلی | `aim_career_twin` `aim_career_twin_run` |
| مأموریت واقعی | `aim_real_missions` `aim_mission_view\|{id}` `aim_mission_do\|{id}` `aim_my_missions` |
| یادگیری تیمی | `aim_team_learning` `aim_team_join` `aim_team_members\|{id}` `aim_team_feedback\|{id}` `aim_team_leave\|{id}` |
| پروفایل عمومی | `aim_public_profile` `aim_pub_toggle` `aim_pub_bio` `aim_pub_preview` |
| شارژ اعتبار | `aim_buy` `aim_pack\|{id}` `aim_fiche\|{id}` |

**ادمین (۳۰ عدد):** `aim_a_menu` `aim_a_core` `aim_a_toggle` `aim_a_pricing` `aim_a_set|{key}` `aim_a_trends` `aim_a_trend_add` `aim_a_trend_del|{skill}` `aim_a_trend_ai` `aim_a_content` `aim_a_monitor` `aim_a_reports` `aim_a_packs` `aim_a_pack_add` `aim_a_pack_tog|{id}` `aim_a_pack_del|{id}` `aim_a_payment_info` `aim_a_pay_set|{f}` `aim_a_pending_purchases` `aim_a_pur_view|{id}` `aim_a_pur_ok|{id}` `aim_a_pur_no|{id}` `aim_a_model_routing` `aim_a_route_view|{a}` `aim_a_route_set|{a}` `aim_a_route_tog|{a}` `aim_a_missions` `aim_a_mission_add` `aim_a_mission_tog|{id}` `aim_a_mission_del|{id}`

### Stateها

**کاربر — ۱۳ عدد (`AIM_STATES`):**

| گروه | Stateها |
|---|---|
| اطلاعات اولیه | `wait_aim_profile_name` → `wait_aim_profile_age` → `wait_aim_profile_city` |
| 🤖 معماری چندعاملی | **`wait_aim_interview`** (گفتگو با ایجنت ۱) • **`wait_aim_exercise_answer`** (داوری ایجنت ۳) |
| شبیه‌ساز مصاحبه | `wait_aim_sim_job` • `wait_aim_sim_answer` |
| سایر | `wait_aim_chat` • `wait_aim_help` • `wait_aim_fiche` • `wait_aim_mission_submission` • `wait_aim_pub_bio` • `wait_aim_edit_profile` |

`AIM_MEDIA_STATES = ("wait_aim_fiche",)` — تنها stateای که عکس می‌پذیرد.

**ادمین — ۷ عدد (`AIMA_STATES`):** `wait_aima_value` `wait_aima_trend` `wait_aima_pack` `wait_aima_pay` `wait_aima_reject` `wait_aima_route` `wait_aima_mission`

> ⚠️ **باگ رفع‌شده:** پیش‌تر شبیه‌ساز مصاحبه و ایجنت ۱ هر دو از `wait_aim_interview` استفاده می‌کردند و پاسخ کاربر به سؤال مصاحبهٔ شغلی به شبیه‌ساز می‌رفت. شبیه‌ساز به `wait_aim_sim_answer` منتقل شد.

### تعرفه (قابل تغییر از پنل)

| اکشن | کلید | پیش‌فرض |
|---|---|---|
| نقشه راه | `price_roadmap` | ۱۰۰ |
| تصحیح تمرین | `price_challenge` | ۵۰ |
| گزارش شغلی | `price_report` | ۲۰۰ |
| کمک در گام | `price_help` | ۱۰ |
| شبیه‌ساز مصاحبه | `price_interview_sim` | ۱۰۰ |
| همزاد شغلی | `price_twin` | ۳۰۰ |
| چت منتور | `price_chat` | ۰ |
| ترندها | `price_trends` | ۰ |
| سهمیهٔ رایگان اولیه | `free_quota` | ۳ |

کلیدهای غیرقیمتی: `enabled` (روشن/خاموش کل ماژول)، `model` (مدل اجباری ادمین)، `system_prompt` (پرامپت سفارشی).

#### قاعدهٔ طلایی اقتصاد: کسر در لحظهٔ خدمت

دو تابع مکمل وجود دارد:

| تابع | کاربرد |
|---|---|
| `can_afford(uid, action)` | فقط **بررسی** موجودی — ابتدای فلوهای چندمرحله‌ای |
| `check_and_deduct_credits(uid, action)` | بررسی + **کسر واقعی** — لحظهٔ ارائهٔ خدمت |
| `refund(uid, amount, reason)` | بازگرداندن اعتبار وقتی خدمت ارائه نشد |

ترتیب بررسی: ادمین → تعرفهٔ صفر → سهمیهٔ رایگان → موجودی کافی → رد.

**مثال عملی:** در `aim_start` فقط `can_afford` صدا زده می‌شود. کسر واقعی در `aim_confirm_path` (لحظهٔ ساخت نقشه راه) انجام می‌گیرد. نتیجه: اگر کاربر وسط مصاحبهٔ ۸ سؤالی منصرف شود، **یک اعتبار هم نمی‌سوزد**.

> اگر فراخوانی AI شکست بخورد، `refund()` اعتبار را برمی‌گرداند و به کاربر اطلاع می‌دهد.

### نکات پیاده‌سازی

- **پروژه aiogram نیست.** این ربات با python-telegram-bot و یک dispatcher مرکزی کار می‌کند؛ `dp.include_router()` وجود ندارد. ماژول این توابع را در اختیار `handlers.py` می‌گذارد: `handle_aim_callback()`، `handle_aim_state()`، `handle_aim_media()`، `try_verification_code()`.
- هفت تابع `init_*` ماژول داخل `db.init_db()` صدا زده می‌شوند، با import داخل تابع تا حلقهٔ import ایجاد نشود.
- دکمهٔ کاربر فقط وقتی نمایش داده می‌شود که ماژول فعال باشد (`config.AI_MENTOR_ENABLED` + کلید `enabled` در دیتابیس).
- خروجی مدل با `_extract_json()` پاک‌سازی می‌شود (پشتیبانی از بلوک ```json و متن اضافه).
- `course_id` تولیدشده توسط AI اعتبارسنجی می‌شود؛ اگر در `COURSES` نباشد حذف می‌گردد تا لینک شکسته نسازد.
- `ai_market` بدون اینترنت هم کار می‌کند: منبع بیرونی → فهرست پایه → ذخیرهٔ خام.
- **ضد IDOR:** شناسهٔ گام عددیِ قابل‌حدس است. هر جا گام یا مسیر خوانده می‌شود، `get_owned_step(step_id, user_id)`، `set_path_status(pid, uid, …)` یا بررسی صریح `path["user_id"] == user.id` انجام می‌گیرد.
- **پرامپت‌های حاوی JSON با `.replace()` پر می‌شوند، نه `.format()`** — چون `{` و `}` داخل نمونهٔ JSON باعث `KeyError` می‌شد.
- گواهینامهٔ PDF فارسی با `DejaVuSans` + `arabic-reshaper` + `python-bidi` رندر می‌شود (`/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf`).

---

## ۱۶. معماری چندعاملی (Multi-Agent)

فلوی «شروع مسیر جدید» با سه ایجنت تک‌مسئولیتی ساخته می‌شود. هر ایجنت **دقیقاً یک کار** انجام می‌دهد و پرامپتش در فایل `.txt` جدا از کد است.

### چرا سه ایجنت؟

فلوی قدیمی (۴ سؤال ثابت → یکجا نقشه راه با محتوا) سه مشکل داشت:

| مشکل | راه‌حل چندعاملی |
|---|---|
| سؤال‌های ثابت، بدون درک کاربر | ایجنت ۱ مکالمه‌ای می‌پرسد و به پاسخ قبلی واکنش نشان می‌دهد |
| کاربر مسیر را انتخاب نمی‌کرد | ایجنت ۱ سه مسیر بازار را معرفی و گزارش کامل می‌دهد |
| تولید محتوای ۱۰ گام در یک درخواست = کند و گران | ایجنت ۲ فقط اسکلت می‌سازد؛ محتوا Lazy تولید می‌شود |

### فلوچارت

```
کاربر «🚀 شروع مسیر جدید» را می‌زند
   │
   ├─ [ایجنت ۱] questioning ── ۶ تا ۸ سؤال مکالمه‌ای، یکی‌یکی
   │       state: wait_aim_interview
   │
   ├─ [ایجنت ۱] suggestion ─── تحلیل بازار → ۳ مسیر پیشنهادی
   │       دکمه: aim_pick_path|{n}
   │
   ├─ [ایجنت ۱] report ─────── گزارش کامل مسیر انتخابی
   │       دکمه: aim_confirm_path  |  aim_paths_again
   │
   ├─ [ایجنت ۱] done ───────── خروجی JSON نهایی
   │       ذخیره: career_paths.interview_data_json
   │       💰 کسر اعتبار دقیقاً همین‌جا
   │
   ├─ [ایجنت ۲] ─── اسکلت ۱۰ تا ۱۵ گامی، بدون محتوا
   │       ذخیره: career_paths.roadmap_json + path_steps (content خالی)
   │
   └─ کاربر وارد گام می‌شود (aim_step|{id})
           │
           ├─ [ایجنت ۳] teach ── محتوا در همان لحظه (Lazy Loading)
           │       ذخیره: path_steps.content_json → بار بعد صفر فراخوانی AI
           │
           └─ [ایجنت ۳] grade ── داوری تمرین
                   state: wait_aim_exercise_answer
                   درست → گام بعدی باز می‌شود
                   غلط  → فقط Hint، هرگز جواب
```

### سه ایجنت

| # | کلاس | فایل | پرامپت | مسئولیت |
|---|---|---|---|---|
| ۱ | `CareerInterviewAgent` | `agents/career_interview.py` | `prompts/career_interview.txt` | مصاحبه، تحلیل بازار، معرفی مسیر، گزارش، JSON نهایی |
| ۲ | `RoadmapBuilderAgent` | `agents/roadmap_builder.py` | `prompts/roadmap_builder.txt` | فقط اسکلت نقشه راه — **بدون محتوا** |
| ۳ | `LearningMentorAgent` | `agents/learning_mentor.py` | `prompts/learning_mentor.txt` | محتوای گام (Lazy) + داوری تمرین |

قرارداد مشترک هر ایجنت:

```python
class SomeAgent:
    name = "..."
    prompt_file = "....txt"

    def __init__(self):
        self.prompt = self._load_prompt(self.prompt_file)   # از فایل txt
        self.stage = "..."

    async def run(self, context, user_message=""):
        ...                       # فراخوانی AI با پرامپت + زمینه
        return {"ok": True, "stage": "...", ...}   # وضعیت برای FSM
```

ایجنت‌ها **بدون حالت وابسته به کاربر** هستند؛ همهٔ وضعیت در `UserJourneyContext` است. پس یک نمونهٔ سراسری برای همهٔ کاربران کافی است:

```python
_AGENT1 = CareerInterviewAgent()
_AGENT2 = RoadmapBuilderAgent()
_AGENT3 = LearningMentorAgent()
```

### ایجنت ۱ — ماشین حالت

`stage` در هر پاسخ برمی‌گردد و FSM بر اساس آن تصمیم می‌گیرد:

| stage | کار | خروجی کلیدی |
|---|---|---|
| `questioning` | یک سؤال مکالمه‌ای | `message`، `hint`، `answer_key` |
| `suggestion` | ۳ مسیر بازار | `paths[]` با `fit_percent`، `demand`، `salary_range`، `difficulty` |
| `report` | گزارش کامل مسیر | `report{summary, key_skills, tools, ai_tools, duration, opportunities, challenges}` |
| `done` | JSON نهایی | `final_json{user_profile, selected_path, market_analysis, recommended_tools}` |

**ضدلغزش:** اگر مدل زودتر از `MIN_QUESTIONS`(۶) بخواهد به `suggestion` بپرد، کد آن را به `questioning` برمی‌گرداند. سقف هم `MAX_QUESTIONS`(۸) است.

**بهینه‌سازی:** مرحلهٔ `done` بدون فراخوانی AI انجام می‌شود — `build_final_json()` از دادهٔ موجود در context می‌سازد. یعنی کل فلو یک درخواست کمتر دارد.

### ایجنت ۲ — فقط اسکلت

خروجی هر گام: `step_number`، `title`، `objective`، `skills_to_learn`، `project`، `exercise`، `expected_output`، `estimated_hours`، `difficulty`، `tools_needed`، `ai_tools`.

⚠️ **هیچ متن آموزشی تولید نمی‌کند.** `_clean_roadmap()` حتی اگر مدل محتوا بفرستد آن را دور می‌ریزد. ستون `content` گام‌ها عمداً خالی می‌ماند.

**حافظهٔ جمعی:** `MOCK_COLLECTIVE_MEMORY` (۵ دسته) تجربهٔ کاربران مشابه را به پرامپت تزریق می‌کند تا معمار بداند کدام گام‌ها معمولاً سخت‌اند و آن‌ها را بشکند:

```python
"programmer": {"avg_completion_rate": 0.78,
               "hard_steps": ["OOP", "Django", "Async", "الگوریتم"], ...}
```

### ایجنت ۳ — Lazy Loading و حافظهٔ فردی

**دو حالت کاری:**

| task | ورودی | خروجی |
|---|---|---|
| `teach` | گام + پروفایل + نقشه راه + نقاط ضعف/قوت | `content_text`، `exercise_question`، `hint`، `estimated_minutes` |
| `grade` | پاسخ کاربر | `status`(pass/fail)، `score`، `feedback`، `hint`، `xp_reward` |

**Lazy Loading:** در `show_step()` اگر `content` خالی باشد ایجنت ۳ صدا زده می‌شود و نتیجه در `content_json` ذخیره می‌گردد. **بار دوم صفر فراخوانی AI** — تست‌شده.

**اعتبارسنجی داوری:** اگر مدل خروجی متناقض بدهد (مثلاً `status="pass"` با `score=10`) کد اصلاح می‌کند. در حالت `pass` مقدار `hint` پاک می‌شود تا جواب لو نرود.

**حافظهٔ فردی:** `update_learning_profile()` نمره را ثبت و عنوان گام را دسته‌بندی می‌کند:

| نمره | نتیجه |
|---|---|
| زیر ۵۰ (`WEAK_SCORE`) | به `weak_topics` |
| بالای ۸۰ (`STRONG_SCORE`) | به `strong_topics` |

این فهرست‌ها (سقف ۲۰ مورد) در `interview_data` ذخیره و به پرامپت گام‌های بعدی تزریق می‌شوند — یعنی محتوا با پیشرفت کاربر تطبیق می‌یابد.

### UserJourneyContext

حافظهٔ کل سفر که بین سه ایجنت دست‌به‌دست می‌شود (`ai_mentor/core.py`):

```python
class UserJourneyContext:
    user_id, user_profile, selected_path, market_analysis,
    recommended_tools, roadmap, current_step, chat_histories,
    stage, answers, conversation, suggested_paths, report,
    weak_topics, strong_topics, path_id
```

| متد | کاربرد |
|---|---|
| `to_dict()` / `from_dict()` | ذخیره و بازیابی (رفت‌وبرگشت بدون افت داده — تست‌شده) |
| `from_path(path)` | بازسازی از ردیف `career_paths` |
| `profile_text()` / `answers_text()` / `conversation_text()` | تبدیل به متن برای پرامپت |
| `add_message()` / `add_step_message()` | ثبت گفتگو با **سقف خودکار** (۴۰ و ۱۲ پیام) |
| `target_job()` | عنوان شغل هدف |

**محل نگهداری:**

| مرحله | محل |
|---|---|
| حین مصاحبه | `ctx.user_data["aim_journey"]` (حافظهٔ نشست) |
| پس از تأیید | `career_paths.interview_data["journey"]` (دیتابیس) |

### پرامپت‌ها در فایل txt

هر سه ایجنت پرامپت را با `load_prompt()` از `ai_mentor/prompts/` می‌خوانند. فایل **یک بار** خوانده و در `_PROMPT_CACHE` نگه داشته می‌شود.

مزیت: برای تغییر رفتار یک ایجنت **نیازی به دست‌زدن به کد نیست** — فقط فایل txt را ویرایش و ربات را ری‌استارت کنید. (یا `clear_prompt_cache()` را صدا بزنید.)

اگر فایل پیدا نشود، رشتهٔ خالی برمی‌گردد و ایجنت به fallback داخلی می‌افتد؛ ربات هرگز کرش نمی‌کند.

### مقاومت در برابر خطا (Fallback)

هر سه ایجنت بدون AI هم کار می‌کنند — سندباکس/سرور بدون اینترنت یا پروایدر خاموش، فلو را متوقف نمی‌کند:

| ایجنت | رفتار بدون AI |
|---|---|
| ۱ | ۸ سؤال ثابت `FALLBACK_QUESTIONS` + ۳ مسیر از `_FALLBACK_PATHS` بر اساس دستهٔ حدس‌زده‌شده |
| ۲ | اسکلت ۱۰ گامی از `key_skills` مسیر انتخابی |
| ۳ | محتوای پایه از `objective` و `project` خود گام |

حدس دسته با تطبیق کلیدواژه روی پاسخ‌های کاربر انجام می‌شود (`_guess_category`).

### افزودن ایجنت چهارم

۱. پرامپت را در `ai_mentor/prompts/my_agent.txt` بنویسید.
۲. کلاس را در `ai_mentor/agents/my_agent.py` بسازید (قرارداد بالا).
۳. در `agents/__init__.py` آن را export کنید.
۴. در `ai_handlers.py` یک نمونهٔ سراسری بسازید و در فلو صدا بزنید.

⛔ ایجنت نباید مستقیم `ai_brain` را import کند — فقط `ask_agent()` از `ai_mentor/core.py` که خودش از `ai_core._ask` و در نهایت `core.ask_ai` عبور می‌کند.

---

## ۱۷. عیب‌یابی

### عمومی

| نشانه | علت محتمل | راه‌حل |
|---|---|---|
| ربات بالا نمی‌آید | `BOT_TOKEN` تنظیم نشده | `.env` را بررسی کنید |
| بله وصل نمی‌شود | دسترسی به `tapi.bale.ai` | اتصال شبکه را تست کنید |
| تلگرام وصل نمی‌شود | فیلترینگ | پروکسی HTTP یا SOCKS5 تنظیم کنید |
| خطای SOCKS | نبود `socksio` | `pip install "httpx[socks]"` |
| ادمین شناخته نمی‌شود | `ADMIN_IDS` اشتباه | با `/myid` شناسه را بگیرید |
| ورودی متنی اشتباه تفسیر می‌شود | state باقی‌مانده | `/start` بزنید |
| تغییر کاربر ذخیره نمی‌شود | فیلد در `_user_fingerprint` نیست | فیلد را اضافه کنید |
| پاسخ AI نمی‌آید | کلید ثبت نشده | «🔁 بررسی همه» را بزنید |
| گروه در مقاصد نیست | ربات ادمین نیست | ربات را ادمین کنید و در گروه پیام بفرستید |

### یار هوشمند و معماری چندعاملی

| نشانه | علت محتمل | راه‌حل |
|---|---|---|
| دکمهٔ «یار هوشمند» نیست | ماژول خاموش است | پنل ادمین ← مدیریت یار هوشمند ← تنظیمات هسته |
| «ساخت نقشه راه ناموفق» | هیچ پروایدر AI فعالی نیست | کلید API را در `.env` بگذارید — اعتبار خودکار برگشته است |
| مصاحبه سؤال‌های ثابت می‌پرسد | AI در دسترس نیست، fallback فعال شده | لاگ را ببینید؛ پروایدر را تست کنید |
| ایجنت پرامپت را نمی‌خواند | فایل `prompts/*.txt` جابه‌جا یا حذف شده | وجود پوشهٔ `ai_mentor/prompts/` را بررسی کنید |
| تغییر فایل txt اثر ندارد | پرامپت در `_PROMPT_CACHE` مانده | ربات را ری‌استارت کنید یا `clear_prompt_cache()` |
| محتوای گام هر بار دوباره ساخته می‌شود | `update_step_content` ناموفق بوده | لاگ `content_json` و دسترسی نوشتن دیتابیس را بررسی کنید |
| «این گام پیدا نشد» با وجود مسیر فعال | گام متعلق به کاربر دیگری است (ضد IDOR) | رفتار درست است؛ از مسیر خودتان وارد شوید |
| پاسخ مصاحبه به شبیه‌ساز می‌رود | نسخهٔ قدیمی با state مشترک | به‌روزرسانی کنید (`wait_aim_sim_answer` جدا شد) |
| `no such column: content_json` | مهاجرت اجرا نشده | ربات را یک بار کامل بالا بیاورید تا `init_db()` مهاجرت کند |
| گواهینامهٔ PDF فارسی خراب | فونت `DejaVuSans` نیست | `apt install fonts-dejavu` |

### لاگ

خروجی روی stdout است. برای جزئیات بیشتر سطح را در `bot.py` به `DEBUG` تغییر دهید.

برای دنبال‌کردن فلوی چندعاملی، این پیام‌ها را جست‌وجو کنید:

```
مصاحبه‌گر: AI در دسترس نبود …      ← ایجنت ۱ به fallback رفت
معمار نقشه راه: خروجی معتبر نبود … ← ایجنت ۲ به fallback رفت
منتور: محتوای معتبر تولید نشد …    ← ایجنت ۳ به fallback رفت
🧩 ستون … اضافه شد                  ← مهاجرت دیتابیس اجرا شد
```

---

*آخرین به‌روزرسانی: بازسازی «شروع مسیر جدید» با معماری چندعاملی (Multi-Agent) — کامیت `7f398ff`.*
