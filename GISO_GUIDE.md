# راهنمای فنی گیسو (GISO_GUIDE) — نسخه بازنویسی‌شده مطابق کد جاری

<!-- updated 2026-09-26 -->
**آخرین همگام‌سازی با کد:** 2026-09-26 — ممیزی مجدد `giso/` روی شاخهٔ `giso-end` با تکیه بر کد واقعی و نقشهٔ Graphify؛ اصلاح شمارنده‌ها و وضعیت پنل کاربر، ثبت ۸ پروایدر واقعی، ثبت سرویس‌های جدیدِ استخراج‌شده از `app.py` و ماژول‌های شکسته‌شده، و ثبت دقیق وضعیت وابستگی‌ها/نقاط اتصال. `bot.py` در این commit **۷۴۲۲ خط** است. اعداد تست **۵۵۶ پاس / ۳۹ فیل** متعلق به snapshot تاریخی 2026-09-09 هستند و در این همگام‌سازی دوباره اجرا نشده‌اند؛ برای وضعیت فعلی باید تست runtime مستقل اجرا شود. Graphify فعلی روی commit `49e41dfd` با `--code-only` ساخته شده است. `beauty-preview` عمداً خارج از این راهنما و این ممیزی است.

> **هدف این سند:** مرجع واحد و دقیق برای هر عامل هوشمند/توسعه‌دهنده‌ای که روی `giso/` کار می‌کند.
> فقط **معماری جاری** مستند است — لاگ فازهای تاریخی، قابلیت‌های حذف‌شده و UI قدیمی حذف شدند.
> **مبدأ حقیقت (Source of Truth) کد است؛** اگر تضادی دیدی، کد را بازخوانی کن و این سند را اصلاح کن.
>
> **قوانین طلایی توسعه:**
> 1. `bot_edu/` و `web/` **LOCKED** هستند (تغییر فقط با دستور صریح کارفرما).
> 2. `giso/bot.py` را refactor/تقسیم نکن — فقط **فیکس موضعی** (قانون ثابت پروژه).
> 3. همه importها مطلق با پیشوند `giso.` (فقط `phoneutil` و `giso_admin` از `bot_edu` مجازند).
> 4. داده شبیه‌سازی‌شده ممنوع — همه آمار از دیتابیس واقعی.
> 5. تست‌ها: `python giso/tests/<name>.py` (هر سوئیت مستقل) — پیش از push رگرسیون سبز.

---

## ۱. معماری کلان (High-Level Architecture)

ریپو = **چهار سرویس اجرایی در سه دامنه محصولی** که با `main.py` ریشه بوت می‌شوند:

| سامانه | مسیر | نقش | وضعیت |
|---|---|---|---|
| ربات آموزش | `bot_edu/` | ربات بله آموزشی (دوره/امتیاز/منتور) + **پل مشترک گیسو** (`giso_admin.py`) | 🔒 LOCKED |
| سایت آموزش | `web/` | وب Flask آموزش — پورت **5000** | 🔒 LOCKED (محدوده گیسو نیست) |
| **سایت گیسو** | `giso/app.py`، پورت **5001** | پلتفرم زیبایی: AI، فروش مو، بازارچه، فروشگاه، مراکز و پنل‌ها | ✅ فعال |
| **ربات گیسو** | `giso/bot.py` | ربات بله نقش‌محور؛ توسط watcher فقط در صورت وجود توکن اجرا می‌شود | ✅ شرطی |

**استک فنی گیسو:**
- **وب:** Flask 3 + Flask-Login + Flask-SQLAlchemy (ORM فقط برای `giso_web_auth` و جداول بیزینس؛ بقیه با SQL خام روی `get_giso_db_conn`).
- **ربات:** python-telegram-bot **20.7** روی Base URL بله (`https://tapi.bale.ai/bot`) — بدون وابستگی به تلگرام.
- **دیتابیس:** SQLite در **حالت WAL** — `giso/data/giso.db` (SSOT بیزینس؛ سایت و ربات گیسو مشترک‌اند) + `bot_edu/data/bot.db` (جدول‌های مشترک ادمین/تنظیمات).
  - PRAGMAها در هر اتصال از `giso/base.py`: `journal_mode=WAL`, `synchronous=NORMAL`, `foreign_keys=ON` (فقط giso.db), `busy_timeout=5000`.
  - `get_giso_db_conn()` / `get_bot_db_conn()` = تنها راه‌های اتصال. **هرگز** `sqlite3.connect` دستی ننویس.
- **production:** `gunicorn giso.wsgi:application --bind 0.0.0.0:5001 --workers 2` (WSGI: `giso/wsgi.py`، در آن `analysis_final_override.install()` هم اجرا می‌شود). ربات گیسو جدا (systemd/subprocess) با توکن از env یا DB.
- **dev:** `python main.py` → ۴ سرویس: bot_edu bot، web (5000)، giso web (5001)، و **watcher ربات گیسو** (هر ۱۰s: اگر توکن `GISO_BOT_TOKEN` env یا `giso_config.bot_token` در bot.db وجود داشت → spawn/ریستارت instance؛ بدون توکن → stop).
- **env:** ریشه `.env` توسط `env_loader.py` لود می‌شود (اولویت: env سیستم > ریشه > زیرشاخه‌ها). `SECRET_KEY` **الزامی** در production (`RuntimeError` در `config.py` + هشدار کلید ضعیف در `security.security_startup_warnings`). `giso/data/.env` = **لایه دوم** ذخیره‌سازی AI (کلیدهای provider، `GISO_SUPER_ADMIN_ID/PHONE`، `GISO_BACKUP_MAX_FILES`).
- **checkpoint دوره‌ای:** ربات گیسو هر **۵ دقیقه** `wal_checkpoint(TRUNCATE)` + `atexit` هنگام خاموشی + قبل از هر backup/restore.

**نقشه ماژول‌ها (فایل → مسئولیت):**

| فایل | مسئولیت |
|---|---|
| `app.py` | Flask app factory: auth، step-up `/admin/verify`، داشبورد/legacy `/admin/*`، API poll اعلان، ویجت AI، routeهای عمومی |
| `bot.py` | ربات بله: منوها، ۱۵۳+ شاخه callback، backup/restore/ریستارت، تیکت، welcome هوشمند (⛔ refactor ممنوع — فقط فیکس موضعی) |
| `base.py` | `get_giso_db_conn`/`get_bot_db_conn`، `checkpoint_giso_db`، `normalize_phone`، `match_user_across_systems`، `notify_user_bot_by_order`، هویت ادمین |
| `config.py` | `Config` (Flask) + **هویت متمرکز سوپرادمین** `is_super_admin` |
| `models.py` | ORM + `migrate_giso_tables` (idempotent، افزایشی — هرگز حذف/تغییر ستون قدیمی) |
| `security.py` | CSRF سراسری، rate-limit در-پروس، audit log، security headers |
| `hair_sale.py` | جریان فروش مو (وب + ربات) + اعلان‌ها |
| `analysis.py` | آنالیز AI (وب) + پرامپت‌ها + گزارش آنلاین، برنامه و چک‌لیست |
| `ai_brain.py` / `ai_runtime.py` | providerها/فیلور/پلیسی نقش + ویجت سایت + pending actions |
| `wallet.py` | کیف پول واحد (اتومیک، دو دامنه cash/spend) |
| `consultant_cards.py` | ماژول مستقل کارت محصول برای مشاور: `build_product_cards()` → `list[ProductCard]` (≤۳ کارت با عکس/قیمت/دلیل/لینک خرید) + `build_cards_for_user(phone)`؛ در `analysis_plan` از آن استفاده می‌شود |
| `user_profile_service.py` | منبع مشترک پروفایل سایت/ربات: whitelist، validation، sync نام ربات و خلاصه فعالیت |
| `marketplace/` | بازارچه C2C (routes/services/schema/settings) |
| `beauty_centers/` | فهرست و ثبت مراکز زیبایی: schema/services/routes/templates/static/panel_admin/bot_handlers؛ مدل صرفاً معرفی |
| `shop/` | فروشگاه (routes, logic/checkout, logic/channel_bridge, bot/, panel/) |
| `channel_importer.py` | پست کانال بله → محصول pending |
| `panel/` | پنل ادمین/سوپر (`/admin`) — ۱۹ ماژول + ۲ بسته (`notifications/`، `backup/`) <!-- updated 2026-09-06 --> |
| `panel_user/` | پنل کاربر (`/dashboard`) — **۹ گزینهٔ اصلی منو** در `USER_MODULES` + قابلیت‌ها/routeهای جانبی مانند `notifications`, `marketplace`, `buyer_request`, `beauty_center`, `wishlist`, `reviews`, `shop`, `ai_assistant`, `center_chats`, `reservations`؛ **دیگر نباید «۱۵ ماژول» به‌عنوان شمارندهٔ canonical نوشته شود.** |
| `wallet_balepay.py` / `bot_balepay.py` | پرداخت آنی کیف پول با بازوی بله (§18) |
| `broadcasts_center/` | مرکز پیام سوپرادمین (صف، زمان‌بندی، گزارش تحویل — §21) |
| `perf.py` | میان‌افزار gzip پاسخ‌ها |
| `ai_credits.py` | اعتبار مصرفی کاربران برای چت/آنالیز (§14–§15) |
| `consultant_chat_service.py` | سرویس گفتگوی مشاور با توکن نشانه‌دار (§14) |
| `db_core.py` / `db_engine.py` / `db_pg_tools.py` | لایه اتصال و دوانجینگی SQLite/PostgreSQL (§20) |

---

## ۲. ساختار دیتابیس (Database Schema)

### ۲.۱ `giso/data/giso.db` — SSOT بیزینس (سایت + ربات گیسو مشترک)

جداول **فعال** (نام → نقش):

| دامنه | جداول |
|---|---|
| هویت | `giso_web_auth` (کاربر سایت: phone، رمز hash، `is_banned`؛ ستون‌های referral فقط تاریخی/inert) • `giso_users` (کاربر ربات: bale_id، phone، `is_admin`) • `giso_user_activity` |
| فروش مو | `hair_orders` (6 وضعیت: pending/reviewing/priced/approved/rejected/completed؛ `final_price`، `admin_note`) • `hair_messages` (چت دوطرفه) |
| آنالیز | `analyses` (report/plan/quick-solution JSON، checklist، chat تاریخچه) • `analysis_rate_limits` • `product_requests` • `consultant_requests`/`consultant_messages` • `giso_bot_consultant_chat` |
| فروشگاه | `products` (slug، `publish_status`، `channel_msg_id` یکتای partial، ستون‌های beauty) • `categories` • `product_orders` (tracking_code، checkout/invoice id) • `stock_notifies` • `discount_codes` • `shop_checkouts` • `shop_invoices` + `shop_invoice_items` (snapshot) • `giso_wishlist` |
| کیف پول | `wallet_transactions` (دفترکل؛ `balance_scope` cash/spend، `idempotency_key`) • `wallet_topup_requests` (رسید اجباری) • `wallet_missions` + `wallet_mission_completions` + `wallet_mission_tombstones` • `withdrawal_requests` • `customer_scores` • `referrals` فقط آرشیو تاریخی (هیچ رکورد/پورسانت جدیدی ساخته نمی‌شود) |
| مراکز زیبایی | `beauty_centers` (یک مرکز per owner؛ pending_review→reviewing→published/rejected/paused/closed؛ خدمات JSON، آمار واقعی) • `beauty_center_images` • `beauty_center_conversations` + `beauty_center_messages` • `beauty_center_feedback` • `beauty_center_promotions` • `beauty_center_discounts` • `beauty_center_events` • `beauty_center_expiry_notices` • `beauty_center_reports` + گزارش‌های تاریخی |
| بازارچه | `hair_listings` (pending_review→published→negotiating→sold؛ soft-delete `deleted_at`) • `buyer_profiles` (gate تأیید) • `buyer_offers` (pending→countered→accepted→sold) • `marketplace_messages` (چت per-offer، `chat_closed`) • `marketplace_reviews` + `marketplace_user_ratings` • `listing_reports` • `marketplace_policies` • `marketplace_event_stats` • **anti-fraud:** `marketplace_devices`/`marketplace_device_links`/`marketplace_listing_device_claims`/`marketplace_risk_events`/`marketplace_phone_observations` (فقط hash — token/IP خام ذخیره نمی‌شود) • `marketplace_price_stats`/`marketplace_price_history` • `marketplace_saved_searches` (**soft-deprecated** — جدول باقی است، UI فعال ندارد) |
| AI | `giso_ai_providers` (**۸ provider** + تنظیمات/پراکسی) • `giso_ai_settings` • `giso_ai_permissions` • `giso_ai_checks_log` • `giso_ai_usage_stats` • `giso_ai_pending_actions` (تأیید/rollback سوپر) • `giso_ai_action_logs` • `giso_proxy_settings` • `prompt_versions` |
| اعلان | `giso_notifications` (مرکز: category/subcategory/title/message/`target_role`/`source_type`/`source_id`/`recipient_id`/status) • `giso_notification_deliveries` (لاگ ارسال بله) |
| پشتیبانی | `giso_support_tickets` (ربات + وب مشترک) |
| مشترک/سیستم | `giso_config` (فقط کلیدهای محلی: `site_base_url`، `backup_interval_hours`) • `giso_audit_log` • `giso_demoted_admins` (لیست سیاه ادمین‌های تنزل‌یافته) • `giso_admin_permissions` (inert — permission per-admin حذف شد) |
| افزوده‌های بعدی <!-- updated 2026-09-06 --> | `giso_balepay_invoices` (پرداخت بله §18) • `giso_insights` + ستون‌های `ai_triage` روی `giso_system_errors` (§10) • `giso_super_visible_pass` (§17) • تاریخچه ورودها • `giso_bc_*` (صف/گزارش مرکز پیام §21) |

> جداول بازارچه/کیف‌پول جدید با `db.create_all()` + `migrate_marketplace_tables()` + `migrate_giso_tables()` در استارت **خودکار و idempotent** ساخته می‌شوند (فایلهای DB قدیمی در git، snapshot قبل از این جداول هستند — در اولین استارت تکمیل می‌شوند).

### ۲.۲ `bot_edu/data/bot.db` — جدول‌های مشترک (مالک: bot_edu)

| جدول | نقش |
|---|---|
| `giso_config` | تنظیمات کلید-مقدار: `bot_token`، `bot_username`، `site_theme`، `site_registration_enabled`، `site_logo_mode`/`site_logo_path`، `panel_idle_*`، `rate_limit_*`، `shop_publish_mode`، `bale_channel_id`، `admin_request_phrase`، `notif_category_settings_v2`، `notif_sound_on`؛ کلیدهای `referral_*` ممکن است تاریخی باشند ولی دیگر خوانش فعال محصول نیستند |
| `giso_admins` | **تک‌منبع ادمین‌های تأییدشده گیسو** (phone، bale_id، added_by) — دارای `UNIQUE(phone, bale_id)` (مهاجرت 2026-08-22) |
| `giso_admin_requests` | صف درخواست ادمینی (pending/approved/rejected) |

> ⚠️ `giso_config` در **دو دیتابیس** وجود دارد و **عمداً جداست** (کلیدهای مختلف): کلیدهای رباتی در bot.db، کلیدهای محلی گیسو (`site_base_url`، `backup_interval_hours`) در giso.db.

**مهاجرت/هماهنگی (مهم برای AI agents):**
- sync P10.4 در `bot_edu/giso_admin.py::init_giso_tables` **فقط** رکوردهای `giso_users.is_admin=1` را به `giso_admins` می‌آورد (با `ON CONFLICT DO NOTHING` + dedupe + unique index). **اصلاح P0 (2026-08-22):** قبل از این اصلاح، شرط `OR bale_id IS NOT NULL` هر کاربر ربات را خودکار ادمین می‌کرد.
- حذف ادمین: `giso_admins` + `giso_users.is_admin=0` + ثبت در `giso_demoted_admins` (ضد re-sync).

---

## ۳. احراز هویت و سطوح دسترسی (Auth & Roles)

### ۳.۱ سه نقش

| نقش | شناسه | منبع حقیقت |
|---|---|---|
| **User** | هر حساب `giso_web_auth` / کاربر ربات | — |
| **Admin** (گیسو) | ردیف در `giso_admins` (bot.db) | جریان درخواست → تأیید سوپر |
| **SuperAdmin** | **هویت متمرکز** `giso/config.py`: `SUPERADMIN_BALE_ID=1191639507` + رقم‌های موبایل `9156012931` (هر فرمت) | تابع `is_super_admin(uid, phone)` — **بدون وابستگی به env/DB** |

### ۳.۲ جریان ادمین‌شدن
1. کاربر ربات **کلمه ادمینی** را می‌فرستد (پیش‌فرض «درخواست ادمین گیسو»؛ کلید `admin_request_phrase` در bot.db، قابل تنظیم از ربات/پنل). مقایسه با `_normalize_admin_phrase` انجام می‌شود: Unicode NFKC، تبدیل `ي/ى→ی` و `ك→ک`، حذف اثر نیم‌فاصله و یکسان‌سازی فاصله‌ها. این Guard **پیش از AI فعال** و دوباره در مسیر عادی اجرا می‌شود؛ عبارت ادمینی هرگز نباید به مشاور AI برود.
2. `create_admin_request` → ردیف pending در `giso_admin_requests` + اعلان بله به سوپر (دکمه‌های ✅ تایید / ❌ رد).
3. سوپر تأیید می‌کند (ربات `adm_app|<id>` یا پنل `/admin/admins`) → درج در `giso_admins` + `giso_users.is_admin=1`.
4. حذف: `adm_del|<id>` / پنل → تنزل + **لیست سیاه** `giso_demoted_admins`.

### ۳.۳ احراز هویت سایت و Step-up
- **Login:** `giso_web_auth` + `pbkdf2:sha256` (werkzeug). Session **۱ ساعت**؛ کوکی `HttpOnly` + `SameSite=Lax` + `Secure` در production. کاربر `is_banned=1` لاگین نمی‌کند.
- **Step-up پنل ادمین (`/admin`):** ورود پنل فقط بعد از **کد یک‌بارمصرف بله** در `/admin/verify`:
  - ارسال: `_send_admin_panel_code_to_bot` (فقط به bale_id حساب؛ اگر bale_id نبود → ورود پنل ممکن نیست).
  - TTL کد **300s**، حداکثر **5 تلاش**، resend هر **45s**، hash کد در session (همراه SECRET_KEY).
  - session مدیریتی: `admin_panel_verified_until` (**1800s**) — تا آن‌جا همه `/admin/*` باز است.
- **ثبت‌نام/بازیابی رمز حساس:** اگر شماره متعلق به ادمین/سوپر باشد → مرحله کد ربات الزامی (register + forgot-password).
- **محدودیت نقش در پنل ادمین** (`giso/panel/permissions.py`):
  - Admin عادی: **نقش عملیاتی ثابت** = `REGULAR_ADMIN_MODULES` (dashboard, hair_sale, marketplace, shop_orders, reviews, consults, account) — بدون permission per-admin (قدیمی inert است).
  - `SUPER_ONLY_MODULES`: users, admins, settings, shop_super, reports, ai, ratelimit, referrals, wallet, channel, analyses, notifications, shop (تنظیمات).
  - هر route حساس POST دو لایه دارد: decorator `require_super` (panel/routes.py) + guard درون handler.
  - **شناسه بله سوپر (2026-09-01):** `get_admin_target` برای شمارهٔ سوپر `{"role":"super","bale_id": str(SUPERADMIN_BALE_ID), "phone": …}` برمی‌گرداند تا کد تأیید اقدام دستیار به بله برسد. قبلاً `bale_id=""` بود و `send_action_code` شکست می‌خورد.

---

## ۴. سیستم ربات بله (Bot Flows)

**ورود:** `giso/bot.py` → `run_bot` → `_run_async` (PTB 20.7). توکن: env `GISO_BOT_TOKEN` > `giso_config.bot_token` (bot.db). watcher `main.py` هر 10s وضعیت را چک می‌کند (تغییر توکن → ریستارت).
**اولویت handlerها:** `MessageHandler(ChatType.CHANNEL → channel_importer.on_channel_post)` **اول از همه** (پست کانال)، سپس `/start`، CONTACT، TEXT، COMMAND، Document (backup)، PHOTO (تعویض عکس محصول)، `CallbackQueryHandler(handle_callback)`.

### ۴.۱ منوی کاربر (6 دکمه root — `_user_kb`)

کیبورد reply کاربر **۶ دکمهٔ اصلی** است (`giso/bot.py::_user_kb`): `💰 کیف پول / 🎯 مأموریت / 💬 مشاور (تمام‌عرض) / 👤 پروفایل / 🎧 پشتیبانی / 📖 راهنما`. دکمه‌های قبلی (آنالیز/فروش مو/بازارچه/فروشگاه) از کیبورد حذف شده‌اند ولی handlerهای متنی آن‌ها برای کیبوردِ بازِ کاربران حفظ شده‌اند؛ دسترسی کامل از «⚡️ عملیات سریع من» و سایت ممکن است.

| دکمه | مدیریت‌کننده | خروجی |
|---|---|---|
| 💰 کیف پول | dispatch (bot.py) → `bot_user_actions.send_ua_view("ua|wallet|main")` → `wallet_main` | مانده Cash/Spend + رتبه + دکمه‌های شارژ/تسویه/تاریخچه/منو |
| 🎯 مأموریت | dispatch → `send_ua_view("ua|mission|main")` → `missions_view` | لیست مأموریت‌های فعال + وضعیت + امتیاز/رتبه + «🏆 رتبه‌بندی هفته» |
| 💬 مشاور | `_start_consultant_ai_chat` (CONSULTANT_AI_LABEL / «💬 مشاور» / «🤖 مشاور…») | شروع جلسه همراه هوشمند + گزارش کوتاه `consultant_report` («💬 سوال بپرس» → فلوی چت AI) |
| 👤 پروفایل | dispatch → `send_ua_view("ua|profile|main")` → `profile_main` | نام/شهر/رتبه/امتیاز + دکمه‌های ویرایش (`upro|*`) و «🏆 رتبه‌بندی» |
| 🎧 پشتیبانی | `handle_support_menu_text` («🎧 پشتیبانی»/«💬 پشتیبانی») | تیکت جدید (`support_new`) + تیکت‌های من؛ `giso_support_tickets` + اعلان ادمین |
| 📖 راهنما | `send_user_help` (hint: «📖 راهنما» ≈ `/help`/`/start_help`) | راهنمای ۶ دکمه؛ هر دکمه ۱–۲ خط توضیح + رتبه‌ها + دستورات `/wallet` `/support` `/help` |

### ۴.۲ منوی ادمین عادی (5 دکمه — `_admin_kb`)
`💇 خرید مو` • `🛍 فروشگاه` • `🏪 بازارچه` • `🏥 مراکز زیبایی` • `💬 مدیریت گفتگوها` (+ دکمه‌های مکمل «📬 صندوق اعلان کار من» / «✅ اقدام سریع»).
- **خرید مو** → منوی هوشمند `bot_hair_admin.py` (لیست تک‌به‌تک با عکس، اکشن‌های `hair_price|`/`hair_rej|`/`hair_review|`/`hair_msg|`، ویرایش با شماره، لیست کاربران، گزارش‌های شماره‌ای).
- **فروشگاه** → `shop/bot/admin_menu.py` (سفارش‌ها، محصولات، تأیید کانال `shop_ch_app|`، گزارش؛ بدون افزودن محصول/تنظیمات).
- **بازارچه** → `bot_market_admin.py` (صف آگهی‌های pending_review: تأیید/رد).
- **مراکز زیبایی** → `beauty_centers/bot_handlers.py` (درخواست‌ها/منتشرشده/متوقف/گزارش + کارت بررسی/انتشار/رد؛ ویژه/تنظیمات فقط سوپر و بدون عملیات مالی در MVP).
- **مدیریت گفتگوها** → `bot_chats_admin.py` (4 نوع: مو/فروشگاه/بازارچه/پشتیبانی؛ پاسخ/پایان/قبلی/بعدی).
- دکمه‌های حساس (`_SUPER_ONLY_ADMIN_TEXTS`: مدیریت کاربران/ادمین‌ها/کانال/تنظیمات/پشتیبان‌گیری/ریستارت/…) برای ادمین عادی = «⛔ فقط سوپرادمین».

### ۴.۳ منوی سوپرادمین (9 دکمه root)
`📊 پیشخوان` • `🛍 فروشگاه` • `💇 خرید مو` • `🔬 آنالیز` • `🏪 بازارچه` • `🏥 مراکز زیبایی` • `💬 مدیریت گفتگوها` • `🛠 مدیریت` • `⚙️ تنظیمات سایت`

| گروه | زیرگروه‌ها |
|---|---|
| 📊 پیشخوان | آمار زنده امروز + اولویت‌ها + «اخبار جدید امروز» از `giso_notifications` |
| 🔬 آنالیز | 📬 درخواست‌های آنالیز • 🔬 مدیریت آنالیز • 🛒 محصولات درخواستی (`prod_view_`/`prod_add_`/`prod_reject_`) |
| 🛠 مدیریت | 👥 مدیریت کاربران سایت (جستجو/حذف تک‌تک/با شماره/همه — با محافظت ادمین‌ها) • 👑 مدیریت ادمین‌ها (`adm_app|`/`adm_rej|`/`adm_del|`) • ⭐ نظرات (`rev_tgl|`) • 📢 مدیریت کانال • 🌐 مدیریت سایت • 💬 مدیریت ویجت • 🧩 مدیریت Providerها و پروکسی (`mair_*`) |
| 🌐 مدیریت سایت (زیرگروه) | 💾 پشتیبان‌گیری (`backup_menu`…) • 🔄 ریستارت ربات (`restart_menu` 5/10/30/60s + لغو) |
| ⚙️ تنظیمات سایت | ⏱ محدودیت زمان تحلیل (`rl_*`) • 🎨 انتخاب تم • 🌐 تنظیم آدرس سایت گیسو (`giso_url_*`) |
| منوی backup | `backup_now` (کپی + document) • `backup_set_interval` (1/3/6/12/24/0) • `backup_upload` → `backup_restore_manual` (document) / `backup_restore_list` → `giso_restore_pick_N`/`giso_restore_confirm_N` • `backup_list` |

### ۴.۴ جریان‌های کلیدی
- **`/start`:** درج `giso_users` → `_giso_lookup` (role: user/pending/admin) → welcome هوشمند (`giso_user_activity` + آمار) → منوی نقش.
- **رابطه ربات↔سایت:** همه داده‌ها در `giso.db` مشترک‌اند — عملیات ربات در لحظه در پنل‌های سایت دیده می‌شود و بالعکس (جزئیات در بخش ۷).
- **ریستارت:** flag `giso/data/giso-restart.flag` + SIGTERM به PID معتبر (چک cmdline `giso/bot.py`) → watcher `main.py` instance جدید spawn می‌کند (همیشه یک instance؛ `os.execv` ممنوع).

---

## ۵. پنل‌های وب (Web Panels)

دو Blueprint مستقل با layout جداگانه (هیچ‌کدام `base.html` را inherit نمی‌کنند؛ هر دو Bell اعلان خودشان را دارند):

### ۵.۱ پنل کاربر — `panel_user_bp`، prefix `/dashboard`
15 ماژول: `overview` (خلاصه من) • `profile` • `orders` • `hair-sale` • `marketplace` (+ `/hair/buyer-request`) • `analyses` (+ alias `analysis-history`) • `chats` (+ alias `conversations`، POST `/chats/support` و `/chats/bug-report`) • `assistant` (دستیار کاربر) • `center-conversations` (صندوق مستقل پرسش‌وپاسخ کاربر با مراکز) • `wallet` (POST `topup` با رسید اجباری، `balepay`/`balepay/follow` (§18)، `withdraw`) • `notifies` (اعلان موجودی) • `notifications` (GET/POST mark-read) • `wishlist` (GET/POST) • `reviews` • `shop` (فروشگاه من). <!-- updated 2026-09-06 -->
- guard: `panel_user_bp.before_request` پیش از ساخت هر context اجرا می‌شود؛ مهمان با `next` کامل (شامل query string) به Login/Registration می‌رود و پس از ورود به همان مقصد برمی‌گردد؛ ادمین/سوپر به `/admin` هدایت می‌شوند. این ترتیب مانع اجرای context با `AnonymousUser` و خطای 500 مسیر خریدار است.
- Bell: `user_topbar.html` + `user_notifications` (badge unread + drawer 5 اعلان + نگهداری اعلان اختصاصی کاربر به‌مدت ۷ روز).
- **پروفایل مشترک:** `giso_web_auth` منبع حقیقت است. سایت و ربات هر دو `user_profile_service.update_user_profile` را صدا می‌زنند؛ فیلدهای قابل ویرایش فقط `first_name,last_name,city,region,contact_time` و ویرایش آن‌ها هر ۱۵ روز یک‌بار است. شماره موبایل هویت مشترک و فقط‌خواندنی است. تغییر نام در `giso_users.first_name` نیز mirror می‌شود تا Welcome ربات فوری به‌روز شود.
- **پروفایل سایت:** اطلاعات حساب، اتصال بله، خلاصه واقعی آنالیز/Checkout/فروش مو/بازارچه/نظر/اعلان + فرم ۵ فیلد و تغییر رمز. تغییر رمز با رمز فعلی، حداقل ۸ کاراکتر، rate-limit پنج تلاش در ساعت، audit و اعلان امنیتی انجام می‌شود و cooldown ناامن ۲۴ساعته ندارد. شمارش خرید بر اساس Checkout است نه تعداد اقلام. اگر مرکز ندارد CTA «ثبت رایگان مرکز» دیده می‌شود؛ پس از اولین درخواست، منوی پویا `🏥 مرکز زیبایی من` در تمام صفحات پنل فعال می‌شود.
- **ویرایش‌های محدود کاربر:** درخواست فروش مستقیم، اطلاعات آگهی بازارچه و Buyer Profile هرکدام حداکثر دو بار و فقط پیش از قفل‌شدن جریان قابل ویرایش‌اند؛ حذف درخواست فروش مو به‌صورت انصراف/حفظ سابقه است. آگهی دارای پیشنهاد فعال قابل ویرایش نیست.
- **مرکز آنالیز پنل:** وضعیت کلی و تاریخچه داخل تب‌های جداگانه مو/پوست، متریک‌های واقعی، گزارش/برنامه/راهکار، محصولات و گفتگو را یکجا نمایش می‌دهد؛ حذف کاربر به‌صورت بایگانی امن است.
- هم‌ترازی ربات/سایت: ربات همان سرویس‌های اصلی را ارائه می‌کند ولی برای UIهای پیچیده بازارچه، سفارش و کیف پول deep-link سایت می‌دهد. کیف پول ربات از همان `get_wallet_balances` سایت استفاده می‌کند؛ Inbox سایت تاریخچه اعلان است و ربات Push بله + Inbox با دکمه خواندن تک/همه دارد.

### ۵.۲ پنل ادمین/سوپر — `panel_bp`، prefix `/admin`
ماژول‌ها (route → دسترسی):
`dashboard` (همه) • `hair-orders` (همه) • `marketplace` + `listings/reports/buyers` actions + `settings` (settings=سوپر) • `beauty-centers` (ادمین: درخواست/انتشار/توقف/گزارش؛ سوپر: +ویژه/تنظیمات) • `shop-orders` + delete (delete=سوپر) • `reviews` + toggle/delete (delete=سوپر) • `consults` + `reply/status/tickets/delete/thread` (delete=سوپر) • `products` (ادمین: محصولات کانال؛ سوپر: کامل) • `analyses` (سوپر) + `consultant reply/status`، `product status` (سوپر) • `channel` (سوپر) • `users` + ban/unban/update/wallet/delete (سوپر) • `admins` (سوپر) • `wallet` = «مرکز مالی گیسو» با نمای فقط‌خواندنی overview/users/shop/marketplace/beauty/AI/discrepancies + عملیات قبلی missions/topups/receipt/settlements/service-fees/settings + دو تب جدید **`ranks`** (تنظیمات ۴ رتبه + واریز فوری + گزارش روزانه + برترین‌های هفته) و **`service_credits`** (فعال‌سازی/هزینهٔ آنالیز/گزارش/مشاوره + گزارش کسرها) — همگی فراخوانِ موتورهای موجود `wallet_core.py`/`rank_daily.py` (سوپر) • `shop` (فروشگاه؛ تنظیمات=سوپر) • `reports` (سوپر) • `settings` + `backup-now/interval/upload/restore/delete`، `restart`/`restart-cancel` (سوپر) • `notifications` + `data`/`read`/`archive`/`read-all`/`archive-all`/`delete-all`/`settings`/`archive-days`/`sound`/`test` (سوپر) • `account` (همه: profile/password).
- guard دو لایه: `_guard()` (login + `_check_giso_admin_access` = target + **step-up 1800s**) و `@require_super` برای routeهای حساس.
- Bell: `topbar.html` (`data-unread` سروری) + `panel.js` fetch `/admin/notifications/data` (5 اعلان + unread + deep-link `notification_url`).

### ۵.۳ `base.html` (صفحات عمومی سایت)
ناوبری واحد و ریسپانسیو برای تمام تم‌ها (Glass container مشترک؛ در تم `smart_assistant` شیشه‌ای تیره مشکی/طلایی) + **Bell سایت** (فقط authenticated: badge + dropdown 5 اعلان + مشاهده همه) + **Toast** (محو خودکار 5s) + flash inline + ویجت AI (`components/ai_widget.html`) + `giso_idle.js` (خروج خودکار از `data-idle-minutes`، قابل تنظیم نقش‌دار از پنل).

### ۵.۴ مسیرهای عمومی سایت
`/` (home + آمار + نظرات visible) • `/login` `/register` `/forgot-password` `/logout` • `/dashboard` (redirect نقش‌محور) • `/hair-sale` (GET/POST 4-step + `/api/hair-estimate`) • `/analysis/*` (بخش ۶) • `/shop/*` (بخش ۶) • `/marketplace/*` (بخش ۶) • `/beauty-centers*` + `/dashboard/beauty-center` (بخش ۶) • `/api/ai-widget/*` (init/chat/feedback — token اختصاصی) • `/api/consultant-chat/*` • `/api/notifications/poll` (جدید — بخش ۷) • `/api/cart-count` • `/api/recommendations` • `/robots.txt` `/sitemap.xml`.
- مسیرهای legacy تک‌صفحه‌ای (`/admin/referrals`، `/admin/users/manage`، `/admin/withdrawals`، `/dashboard/analyses`، `/dashboard/chats`، `/admin/admins`، `/admin/analyses*`، `/admin/consultants*`، `/admin/product-requests`، `/admin/review/<id>/delete`، `/admin/config/*`، `/admin/shop-order/*`، `/admin/product/*`) یا **redirect** به پنل ماژولارند یا routeهای POST فعال برای فرم‌های قدیمی.

---

## ۶. ماژول‌های اصلی بیزینس (Core Business Logic)

### ۶.۱ خرید مو (Hair Sale)
**مسیر کاربر:** `/hair-sale` (فرم 4-step: عکس مو + تخمین قیمت زنده از تعرفه `calculate_hair_price` → مشخصات: طول/جنس/رنگ/وزن/سلامت → اطلاعات تماس → `sale_path`) → ردیف `hair_orders` (status `pending`).
- `sale_path`: `giso` (فقط فروش مستقیم) | `marketplace` (فقط آگهی — HairOrder ساخته نمی‌شود) | `both` (هر دو؛ هر صف دقیقاً یک اعلان).
- **اعلان ثبت:** `send_hair_order_notification_to_admins` = ارسال موازی بله (عکس + دکمه‌های workflow) به `{سوپر} ∪ ادمین‌های giso_admins` + `log_notification(hair_sale, request)`.
- **مسیر ادمین** (ربات منوی هوشمند و/یا پنل `/admin/hair-orders`): چرخه 6 وضعیت `pending → reviewing → priced(approve+final_price) → approved → completed` / `rejected`؛ هر تغییر → `notify_user_bot_by_order` (بله کاربر + **mirror سایت** `log_user_notification`)؛ چت در `hair_messages` (دو طرف مشترک ربات/سایت).
- برنامه معرفی/پورسانت از جریان فروش مو حذف شده است؛ هیچ hook تولید اعتبار Referral اجرا نمی‌شود. جدول‌ها و تراکنش‌های قدیمی فقط برای ممیزی حفظ می‌شوند.
- فروش مستقیم کامل → `close_listing_for_direct_sale` (آگهی متصل بسته/فروخته می‌شود).

### ۶.۲ بازارچه (Marketplace — C2C)
**نقش گیسو فقط واسطه است** (طرف معامله/ضامن نیست — قوانین در `marketplace/settings.py` قابل ویرایش سوپر).
- **فروشنده:** از جریان فروش مو (یا پنل) `HairListing` (pending_review) → تأیید ادمین (`published`) → مدیریت: pause/resume/close/withdraw/edit/delete (soft). `terms_version` + پذیرش الزامی. آگهی فعال می‌تواند با پرداخت اتمیک Spend→Cash یکی از ارتقاهای نردبان، فروش فوری ۲۴ساعته یا ویژه ۷روزه را فعال کند؛ ارتقا فقط ترتیب/نشان نمایش را تغییر می‌دهد و تضمین فروش نیست.
- **خریدار:** `BuyerProfile` (درخواست خرید مو از `/dashboard/hair/buyer-request` → **تأیید ادمین** `verification_status=verified` پیش‌شرط پیشنهاد) → `BuyerOffer` (سقف پایه ثابت ۵ پیشنهاد در ۲۴ ساعت، یک پیشنهاد فعال per آگهی، خودآگهی ممنوع). تب «امکانات خریدار» دو خرید اختیاری دارد: اعلان هوشمند آگهی ۳/۷/۳۰ روزه و بسته ۵ پیشنهاد اضافه برای ۲۴ ساعت؛ پرداخت اتمیک ابتدا از Spend و سپس Cash ثبت می‌شود.
- **مذاکره:** seller accept/reject/counter (`/marketplace/seller/offers/<id>/respond`) ↔ buyer respond (`/marketplace/offers/<id>/buyer-response`) → **فروش موفق** (`/marketplace/offers/<id>/sold`، فقط seller) → بسته شدن آگهی + منقضی‌شدن سایر پیشنهادها + چت read-only.
- **چت:** `marketplace_messages` per-offer؛ فقط طرفین (`is_offer_party`)؛ `chat_closed` یک‌طرفه.
- **اعتبار:** امتیاز 1-5 یک‌بار per طرف بعد از فروش/بستن چت (`marketplace_reviews` + کش تجمیعی `marketplace_user_ratings`)؛ ناشناس در UI عمومی.
- **anti-fraud:** device hash (HMAC token/IP خام نه)، device↔user links، claim اتمیک per آگهی، `marketplace_risk_events` برای ممیزی؛ گزارش کاربران `listing_reports` → پنل.
- **UI عمومی:** `marketplace_list.html` با Hero/راهنمای ۴مرحله‌ای، disclaimer و جست‌وجوی عمودی تمام‌عرض؛ Slider/Grid واقعاً RTL، کارت استاندارد 245–300px با تصویر مربع و آمار views/offers. `marketplace_detail.html` دو ستون است: قیمت/اقدام در راست RTL، تصویر استاندارد حداکثر 520×360 با `object-fit:cover` و Lightbox در چپ، سپس مشخصات تخت؛ اعتبار فروشنده برای مهمان مخفی است.
- **رسانه آگهی:** `GET /marketplace/media/<listing_id>` مسیرهای قدیمی `static/…` و مسیرهای منتقل‌شده uploads/temp/marketplace را امن resolve می‌کند، traversal را رد می‌کند و فقط آگهی عمومی/مالک/طرف معامله را سرو می‌کند. Templateهای list/detail/chat و پنل کاربر از این endpoint استفاده می‌کنند؛ فایل مفقود با fallback واقعی UI نمایش داده می‌شود.
- **پنل کاربر:** کارت «آگهی‌های من» افقی و فشرده با thumbnail 120×120، آمار views/offers و بدون نمایش شهر در خلاصه (شهر در فرم ویرایش/صفحه عمومی حفظ می‌شود).
- **اعلان:** `notify_marketplace_user` آینه سایت + Push بله را برای seller/buyer یکپارچه می‌کند؛ `notify_listing_created` / `notify_offer_created` / `notify_offer_status` / `notify_seller_offer_status` و فروش موفق هر دو طرف را پوشش می‌دهند (جزئیات بخش ۷).

### ۶.۳ فروشگاه (Shop)
- **کاتالوگ:** `products` با slug/SEO (JSON-LD، robots، sitemap، WebP lazy)؛ `publish_status` (`published` / `special_order` / pending). ستون `cost_price` (قیمت فاکتور/داخلی) برای ادمین است؛ فرم افزودن/ویرایش محصول فیلد «قیمت فاکتور» دارد و با ورود فاکتور، `price = sale_price_from_cost(cost)` (×۱٫۵، رند به بالا به ۱۰٬۰۰۰) خودکار محاسبه و `cost_price` ذخیره می‌شود — فاکتور برای کاربر فروشگاه نمایش داده نمی‌شود.
- **عکس کاتالوگ آرایشی (2026-09-01):** ۱۵ محصول `published` فایل واقعی در `giso/static/images/catalog/` دارند و HTML `/shop` از `images/catalog/` سرو می‌شود (پوشهٔ gitignored `static/uploads/` نیست). ۱۵ قلم تغذیه (`special_order`) هنوز `image_path` خالی دارند. API پیشنهاد: `GET /api/recommendations` فقط published برمی‌گرداند.
- **سبد:** session `giso_cart`؛ add فقط POST؛ qty 1-99؛ `/api/cart-count` برای شمارنده شناور.
- **Checkout اتمیک** (`wallet.py::create_shop_checkout_atomic`): در یک `BEGIN IMMEDIATE`: بازخوانی قیمت/موجودی/تأیید از DB → یک `shop_checkout` + یک `shop_invoice` + چند `product_orders`/`shop_invoice_items`؛ تمام اقلام Checkout یک `tracking_code` مشترک دارند و snapshot قیمت می‌گیرند. سپس debit کیف پول (`spend` → `cash`) و مصرف idempotent کد تخفیف؛ خطا → rollback کامل.
- **پرداخت:** COD (پیک) / کیف پول کامل / **ترکیبی** (مانده COD جدا: `payment_status` = cod_due/settled/split_due). سفارش قدیمی بدون فاکتور: backfill هنگام مشاهده.
- **ویرایش پس از ثبت:** فقط Checkout پرداخت‌درمحل، بدون تخفیف و با همه اقلام در وضعیت pending/new قابل ویرایش اتمیک است؛ تعداد صفر یعنی حذف قلم، حداقل یک قلم باید بماند و آدرس/زمان/یادداشت همراه با snapshot فاکتور و مبالغ به‌روزرسانی می‌شود. سفارش دارای برداشت کیف پول، تخفیف یا وضعیت پردازشی قفل است.
- **بعد از ثبت:** `/shop/order-success` فقط کدهای یکتا را نمایش می‌دهد (Legacy چندکدی حفظ می‌شود)؛ فاکتور نیز کد را dedupe می‌کند. پنل کاربر و ربات اقلام را با `checkout_id` گروه‌بندی می‌کنند و جست‌وجوی ربات با tracking تمام اقلام را برمی‌گرداند. اعلان: مرکز + بله ادمین‌های معمولی و سوپر با دکمه‌های وضعیت per-order + بله کاربر.
- **Import کانال بله** (`channel_importer.py`): پست کانال (`bale_channel_id`) → parse دو لایه (regex قیمت با ارقام فارسی → fallback AI `ask_ai_fast`) → عکس WebP → محصول `pending` با dedupe `channel_msg_id` → پیش‌نمایش بله به ادمین‌ها (`chimp|pub/del/edit/view`) یا انتشار مستقیم (auto اگر قیمت>۰).
- **موجودی:** `stock_notifies` (اعلان موجودی) → `notify_product_back_in_stock` هنگام toggle-stock.

### ۶.۴ توقف برنامه معرفی (Referral Retirement)
- تصمیم محصول: Referral/پورسانت **متوقف** است. فرم ثبت‌نام `referral_code` ندارد، پارامتر `?ref=` نادیده گرفته می‌شود، ثبت‌نام کد یا رابطه جدید نمی‌سازد و `register_referral` یک no-op سازگاری است.
- ربات کاربر هیچ وعده پاداش، کد یا لینک معرفی نمایش نمی‌دهد. منوها/تنظیمات پورسانت سایت و ربات غیرفعال یا به مرکز مالی هدایت شده‌اند.
- **عدم حذف داده:** ستون‌های `giso_web_auth`، جدول `referrals` و تراکنش‌های تاریخی باقی می‌مانند تا فاکتور/ممیزی قدیمی نشکند؛ هیچ migration مخرب یا پاک‌سازی تاریخچه انجام نمی‌شود.
- جایگزین پاداش: `wallet_missions` با مانده `spend`؛ مدیریت مالی جاری فقط از `wallet.py` و دفترکل Cash/Spend انجام می‌شود.

### ۶.۵ آنالیز (Analysis)
**جریان AI Vision** (`analysis.py` + پرامپت‌های `giso/prompts/*.txt`):
1. `/analysis` (انتخاب مو/پوست) → `/analysis/{hair,skin}` (آپلود 1 عکس + چک هوشمند `/analysis/validate-image`).
2. **initial:** `call_vision_with_fallback` (provider فعال + زنجیره فیلور + تشخیص refusal) → `hair/skin_initial_analysis.txt` → رکورد `analyses` (incomplete) + سوال‌های تکمیلی.
3. پاسخ‌ها → (مهمان: `/analysis/register` + **rate-limit** `analysis_rate_limits` — ip/phone/both، کلیدهای `rate_limit_*` در bot.db) → **final:** `hair/skin_final_analysis.txt` → گزارش ساختاریافته (metrics، main_problems با شدت، immediate_actions، avoid_list، timeline).
4. خروجی‌ها فقط آنلاین‌اند: `/analysis/{hair,skin}/report` (متریک‌ها با فرهنگ واژگان فارسی مشترک) • تب بایگانی و بازیابی امن • `/analysis/plan` (برنامه هفتگی) • `/analysis/quick-solution` • checklist (save/progress) • `request-consultant` / `request-product`. کدها، Routeها و وابستگی اختصاصی دانلود PDF/PNG آنالیز حذف شده‌اند.
- **چت مشاور:** سایت (`/api/consultant-chat/*` + `consultant_chat_history`) و ربات (`giso_bot_consultant_chat`)؛ پاسخ ادمین → اعلان کاربر (بله + mirror سایت).
- **کارت محصول مشاور (قابلیت C):** صفحهٔ `/analysis/plan` با `consultant_cards` (از `giso/consultant_cards.py::build_cards_for_user` که موتور `get_recommendation_for_user` را صدا می‌زند) حداکثر ۳ کارت با عکس/قیمت/دلیل و دکمهٔ «مشاهده و خرید» (یا «📦 سفارش خاص» برای دستهٔ ویژه) رندر می‌کند؛ بدون تطابق → بدون کارت، بدون ادعا.
- `analysis_final_override.py`: نسخه ایمن `_final_analysis` (session-first + بازیابی رکورد + تشخیص گزارش کامل) — در استارت (app + wsgi) با monkey-patch اعمال می‌شود.
- **AI runtime** (`ai_runtime.py`): providerها در `giso_ai_providers` + `giso/data/.env` (دو لایه)؛ failover chain؛ **role policy** (سطح 0-3 + sectionها + سقف روزانه per role)؛ **pending actions** سوپر (confirm/cancel/rollback با `giso_ai_action_logs`)؛ پیکربندی ویجت (position/welcome/color)؛ usage stats؛ پروکسی Gemini (`gemini_proxy_manager.py` + ProxyScrape).
- **حذف کاربر از دستیار سوپر (2026-09-01):** `_snapshot_user_bundle` روی جدول `giso_users` دیگر `ORDER BY id` اجباری ندارد. در `giso.db` این جدول با کلید `bale_id` است (ستون `id` ندارد). اگر `id` باشد مرتب می‌شود؛ اگر جدول/ستون نباشد snapshot خالی می‌ماند و آماده‌سازی اقدام نمی‌ترکد.

### ۶.۶ مراکز زیبایی (Beauty Centers — معرفی صرف)
- **مرزبندی:** گیسو فقط دایرکتوری معرفی است؛ رزرو، دریافت وجه خدمت، کمیسیون، تضمین مجوز/کیفیت/قیمت/نتیجه یا حل اختلاف ندارد. Disclaimer در list/detail/register/owner و پیش از نمایش تماس دیده می‌شود.
- **ماژول مستقل:** `giso/beauty_centers/` شامل Blueprint، migration افزایشی، services، public/owner routes، admin adapter، bot handlers، templates و static است. Login و User جدید ساخته نمی‌شود؛ `owner_user_id → giso_web_auth.id`.
- **صفحات:** `/beauty-centers` (SEO + ItemList + فیلتر شهر/نوع/خدمت و کارت‌های هم‌ارتفاع) • `/beauty-centers/<slug>` (LocalBusiness JSON-LD؛ خدمات کارت‌بندی‌شده، Carousel لمسی و Lightbox داخلی، تصویر جایگزین، CTA «گفتگوی آنلاین با مرکز»، دکمه مدیریت شرطی مالک، تماس فقط پس از Login/POST رضایت). قالب detail دارای تست تعادل Jinja است؛ حلقه قدیمی feedback و `endfor/endif` اضافی حذف شده‌اند. • `/beauty-centers/register` • `/dashboard/beauty-center` (تب status/edit/stats/promotion) • `/dashboard/center-conversations` (صندوق گفتگوی کاربر با مرکز و badge خوانده‌نشده) • media امن.
- **چرخه مرکز:** `pending_review → reviewing → published | rejected`؛ انتشار ۳۰ روز اعتبار دارد، یادآوری‌های idempotent در ۷/۳/۱ روز و زمان انقضا ارسال می‌شوند و مالک می‌تواند با کیف پول ۳۰ روز تمدید کند. مرکز منقضی از فهرست عمومی خارج می‌شود؛ مالک published را pause/resume می‌کند. شهر ثابت «مشهد» و منطقه/محله قابل ثبت است. تغییر نام/نوع/شماره کاری مرکز منتشرشده دوباره pending می‌شود. یک مرکز per owner در MVP.
- **پنل مالک:** قبل از درخواست فقط CTA در Profile؛ بعد از اولین درخواست، `🏥 مرکز زیبایی من` به منوی کل پنل اضافه می‌شود. درصد تکمیل، برچسب نمایشی روزهای باقی‌مانده، بنر شرطی ارتقا، فرم یکپارچه بخش‌بندی‌شده، پیش‌نمایش و مدیر تصاویر واحد دارد؛ حداکثر سه تصویر با افزودن/حذف امن مدیریت و همگی در اسلایدر عمومی نمایش داده می‌شوند. تب «ارتقای آگهی» نیز در همین پنل قرار دارد. خریدها nonce پایدار و کنترل اتمیک دوره دارند: نردبان از ۲۴ ساعت پس از انتشار و سپس هر ۲۴ ساعت یک‌بار؛ آگهی ویژه تا پایان ۷ روز غیرقابل خرید مجدد؛ «تخفیف خدمات» ثابت ۲۴ساعته؛ تمدید فقط از ۱۰ روز مانده و با افزودن ۳۰ روز به تاریخ فعلی. سوپر قیمت و فعال/غیرفعال‌بودن بسته‌ها را مدیریت می‌کند. «منتخب گیسو» نشان مدیریتی و غیرقابل خرید است. نشان‌های عمومی با اولویت ثابت «منتخب گیسو ← آگهی ویژه ← تخفیف خدمات» روی تصویر قرار می‌گیرند. رویدادهای واقعی ثبت می‌شوند؛ کاربر فقط پس از دریافت پاسخ در گفتگوی واقعی یکی از سه ارزیابی خوب/متوسط/ضعیف را بدون متن ثبت می‌کند. امتیاز قطعی ۵/۳/۱ و نمره عمومی فقط پس از حداقل سه ارزیابی نمایش داده می‌شود. نشان «منتخب گیسو» قابل خرید نیست و فقط توسط سوپرادمین مدیریت می‌شود.
- **مدیریت:** Admin و Super هر دو منوی سایت/ربات مراکز را دارند. Admin درخواست، انتشار، رد، توقف و گزارش را مدیریت می‌کند؛ Super علاوه بر آن تب featured/settings دارد. اعلان درخواست ربات دارای callback بررسی/انتشار/رد است.
- **POST پنل (2026-09-01):** تخفیف/بازخورد از `_beauty_centers.handle_discount/handle_feedback` می‌روند (alias ناموجود `_beauty_admin` حذف شد). بررسی گزارش باگ پایش (`monitoring_bug_review`) actor را از `current_user.phone` می‌گیرد، نه `flask.g`.
- **رسانه/امنیت:** تصویر ≤5MB/20MP با Pillow verify، resize و re-encode WebP با نام random؛ media route فقط public/owner؛ تمام POSTها CSRF، ownership و SQL پارامتری دارند. اطلاعات تماس روی کارت عمومی نیست و شمارنده تماس فقط با POST عضو افزایش می‌یابد.
- **اتصال آنالیز:** گزارش Hair/Skin، Plan و Quick Solution در انتها CTA مراکز دارند. matching قطعی = published+active، شهر و Service Tag استخراج‌شده از آنالیز؛ حداکثر ۳ نتیجه. Prompt مشاور فقط همین فهرست DB را می‌بیند و صریحاً از اختراع نام/خدمت و ادعای «بهترین» منع شده است.
- **SEO:** متن اصلی server-rendered، canonical/description/OG، `LocalBusiness` و `ItemList` JSON-LD، URL slug، sitemap مراکز و robots Allow؛ صفحات owner noindex هستند.
- **قابلیت‌های جدید اضافه‌شده (فاز A+B):** لیست خدمات و قیمت هر مرکز (`beauty_center_services`) • ساعات کاری هفتگی (`beauty_center_working_hours`) • سیستم رزرو نوبت آنلاین (`beauty_center_reservations`) • اعلان رزرو: بله + سایت (`safe_log`) • تأیید/رد رزرو توسط مالک از سایت و ربات • یادآوری ۲۴h و ۲h قبل از نوبت • مسیرهای جدید: `/beauty-centers/<slug>/reserve` • `/dashboard/beauty-center/reservations` • `/dashboard/my-reservations` • ربات: `rsv|confirm|<id>` / `rsv|reject|<id>`.

---

## ۷. سیستم اعلان‌ها (Notification System)

**مرکز واحد:** جدول `giso_notifications` (giso.db) + لاگ ارسال `giso_notification_deliveries`.

### ۷.۱ APIهای ثبت (بستهٔ `panel/modules/notifications/` — `core.py`/`helpers.py`) <!-- updated 2026-09-06 -->
- `log_notification(category, subcategory, title, message, target_role=None, source_type="", source_id=None, recipient_id="", destination=None)`:
  - **idempotent** با `source_type+source_id+recipient_id` (تکرار event → یک رکورد).
  - دسته غیرفعال (`enabled=0`) → ثبت نمی‌شود.
  - `target_role`: `super`/`admin`/`both`/`none` (پیش‌فرض = تنظیم دسته). `none` → رکورد `archived` (نمایش/ارسال ندارد).
  - `destination`: `site`/`bot`/`both` — اگر `bot` شامل شود → **پیام بله استایل‌دار** (آیکن + بخش + deep-link پنل) در **thread pool** (غیرمسدود) با 3 retry/backoff + `record_delivery` (audit ارسال).
- `safe_log(...)` = wrapper بدون-throw (استفاده در **همه هوک‌های بیزینس**؛ شکست اعلان هرگز جریان را نمی‌شکند).
- `log_user_notification(phone, ...)` = اعلان **اختصاصی کاربر** (`recipient_id=phone`، `target_role=user`) → Bell سایت/پنل کاربر؛ نگهداری **۷ روز** (`USER_NOTIFICATION_RETENTION_HOURS=168`). برای بازارچه، wrapper `notify_marketplace_user` علاوه بر mirror سایت، پیام بله غیرمسدودکننده می‌فرستد.

### ۷.۲ مدل ارسال بله (super-first)
دریافت‌کنندگان = **همیشه سوپر** + (اگر target `admin`/`both`) ادمین‌های `giso_admins` غیر-سوپر. `none` → فقط سوپر. بدون توکن → بی‌صدا + `record_delivery(failed, missing_token)`.

### ۷.۳ دسته‌ها و تنظیمات (کلید `notif_category_settings_v2` در bot.db — JSON)
`shop` • `hair_sale` • `marketplace` • `beauty_centers` • `analysis` • `users` • `wallet` • `channel` • `bot` • `security` • `system` — هر کدام `target_role`/`destination`/`enabled` (تنظیم از پنل `🔔 مدیریت اعلان‌ها`، فقط سوپر). + آرشیو خودکار (پیش‌فرض 7 روز، `notif_auto_archive_days` 1-60) + صدا (UI فقط) + «تست ارسال».
> ⚠️ برای AI agents: اگر در محیطی اعلان‌ها «در بله می‌روند ولی در پنل نیستند» → `target_role` آن دسته روی `none` است (رکورد archived). تنظیم را در پنل تغییر بده.

### ۷.۴ هوک‌های فعال (رویداد → اعلان)
| رویداد | مرکز/بله | کاربر (mirror) |
|---|---|---|
| سفارش جدید فروشگاه | center + بله ادمین‌های معمولی + عکس به سوپر + دکمه‌های ارسال/تحویل/رد per-order | بله «ثبت سفارش» + mirror سایت |
| تغییر وضعیت سفارش | — | بله + mirror |
| درخواست مو / پیام / اعتراض | center + بله موازی ادمین‌ها | — |
| تغییر وضعیت مو / پیام کارشناس | — | بله + mirror (`notify_user_bot_by_order`) |
| آنالیز جدید / درخواست مشاوره / وضعیت درخواست محصول | center | mirror (تأیید/رد محصول) |
| آگهی/پیشنهاد/Counter/فروش بازارچه | center + بله ادمین/سوپر طبق دسته | seller/buyer: Bell/Toast سایت + Push بله؛ فروش موفق برای هر دو طرف |
| درخواست/وضعیت/گزارش مرکز زیبایی | center + بله Admin/Super؛ درخواست جدید با دکمه بررسی/انتشار/رد | مالک: Bell/Toast + Push بله با deep-link مرکز من |
| شارژ/تسویه جدید (کیف پول) | center (سوپر) | — |
| تأیید/رد شارژ و تسویه | — | mirror (با مبلغ/یادداشت) |
| تیکت جدید (ربات **و** وب) | center (دسته `bot`) | — |
| پاسخ تیکت (ربات بله / پنل mirror) | — | بله + mirror |
| پست کانال / تأیید محصول کانال | center | — |
| ثبت‌نام / ورود سوپر / step-up / backup / restart / ban | center (security/system/users) | — |

### ۷.۵ UI سایت — Bell + Toast (جدید، 2026-08)
- **`base.html`:** بلوک Bell (فقط authenticated) = دکمه + badge فارسی + dropdown 5 اعلان آخر + «مشاهده همه»؛ `#gisoToastWrap` (toastهای بالای صفحه).
- **`giso/static/js/giso_notifications.js`** (vanilla، بدون وابستگی): **poll هر ۳۰ ثانیه** به `GET /api/notifications/poll` → به‌روزرسانی badge/dropdown + **toast برای اعلان‌های unread جدید** (dedup با sessionStorage، حداکثر 3 هم‌زمان، محو خودکار **5s**، کلیک = deep-link).
- **Flash → Toast:** flashهای هر صفحه (ثبت سفارش/شارژ/آنالیز/…) به‌صورت `gisoFlashData` JSON تزریق می‌شود و JS آن‌ها را toast می‌کند و alert inline را مخفی می‌کند (`giso-flash-toasted`)؛ بدون JS، alert inline قبلی دست‌نخورده می‌ماند.
- **API:** `GET /api/notifications/poll` — مهمان: `{ok,unread:0,items:[]}`؛ کاربر: 5 اعلان آخر + `unread` + `icon` + `url` (بازارچه → `/dashboard/marketplace`، بقیه → `/dashboard/notifications`).
- **پنل ادمین:** `GET /admin/notifications/data` (5 اعلان + unread نقش) + `panel.js` (badge زنده، dropdown، کلیک → `notification_url` صفحه دسته).

---

## ۸. زیرساخت و امنیت (Infra & Security)

### ۸.۱ Backup / Restore / Restart (فقط سوپر)
- **پوشه:** `giso/data/backup/` — `giso_backup_<ts>.db` (دستی) • `giso_auto_<ts>.db` (خودکار) • `giso_pre_restore_<ts>.db` (نسخه امن قبل از restore) • `giso_upload_<ts>_*.db`.
- **خودکار:** کلید `backup_interval_hours` در **giso.db** `giso_config` (0=غیرفعال)؛ job `run_repeating` در استارت ربات (تغییر از پنل با restart اعمال می‌شود — پیام flash اطلاع می‌دهد؛ تغییر از ربات زنده است). هر backup = **checkpoint → copy → prune** (حداکثر `GISO_BACKUP_MAX_FILES` از `giso/data/.env`، پیش‌فرض **5**، per-prefix).
- **Restore اتمیک (اصلاح 2026-08-22 — `bot.py::_giso_restore_from_path` و بستهٔ `panel/modules/backup/` :: `restore_backup`):** <!-- updated 2026-09-06 -->
  `integrity_check(source)` → کپی pre_restore → **کپی source به `{db}.restore-{pid}.tmp` → `os.replace` (اتومیک)** → **حذف `giso.db-wal`/`-shm` قدیمی** → `checkpoint_giso_db()` بعد از restore؛ خطا در میانه → rollback از pre_restore + حذف tmp.
- **مسیرها:** ربات (دستکی document یا لیست + تأیید دو مرحله؛ pre_restore از لیست restore فیلتر است) • پنل (`POST /admin/settings/backup-restore` دو مرحله `step=confirm`).
- **مدیریت راه دور از ربات آموزش:** منوی «مدیریت سایت» به «سایت اصلی» و «سایت گیسو» تفکیک شده است. بخش گیسو شامل مدیریت ربات، Maintenance و تصویر سفارشی، پشتیبان/بازگردانی، گزارش خواندنی هوش مصنوعی، سلامت کلی و پاک‌سازی امن دومرحله‌ای است. گزارش‌ها Secret نشان نمی‌دهند و پاک‌سازی فقط برای `ADMIN_IDS` و محدود به tempهای قدیمی/نسخه‌های اضافه پشتیبان است.
- **Restore خودکار استارت** (bot_edu): فقط وقتی DB **مفقود/خالی** باشد.
- **Restart ربات:** `POST /admin/settings/restart` (5/10/30/60s + pending قابل لغو با `O_EXCL` ضد race) → flag + SIGTERM به PID معتبر (چک `/proc/<pid>/cmdline` شامل `giso/bot.py`) → watcher spawn. GET تنظیمات **فقط‌خوان** است (قانون 5.2: هیچ side-effect در render).

### ۸.۲ امنیت
- **CSRF:** همه POSTها (به‌جز `/api/ai-widget/*` که token اختصاصی دارند) نیاز به `csrf_token` (form) یا header `X-GISO-CSRF`/`X-CSRF-Token` دارند — `security.py::install_security`.
- **Rate-limit در-پروس** (per bucket+client؛ در multi-worker N× می‌شود — برای production جدی Redis پیشنهاد می‌شود): login 10/300s • register 5/600s • forgot 5/600s • admin/verify 8/300s • validate-image 20/300s • consultant 30/300s • cart-add 30/60s • topup 8/3600s • withdraw 5/3600s • marketplace offer 12/300s، chat 60/300s. + **rate-limit آنالیز** جدا (per user/ip، `analysis_rate_limits` + `rate_limit_*`).
- **Session:** 1h؛ `HttpOnly` + `SameSite=Lax` + `Secure` (production)؛ `SECRET_KEY` الزامی production + هشدار کلید ضعیف در startup.
- **Upload:** `MAX_CONTENT_LENGTH=16MB`؛ `secure_filename`؛ **رسید کیف پول** سخت‌گیرانه‌تر: فقط JPG/PNG واقعی (Pillow verify + re-encode)، ≤5MB و ≤20MP، نام 32-hex رندم، `chmod 600`، **خارج از static** (`giso/data/wallet_receipts/`) و فقط route سوپر `…/topups/<id>/receipt` سرو می‌کند.
- **Audit:** `giso_audit_log` (actor/action/target/path/outcome/IP/UA) روی POSTهای حساس + انکارهای IDOR (مالکیت سفارش/آنالیز/چت/فاکتور).
- **Headers:** CSP + HSTS (prod) + `X-Frame-Options` + nosniff + Referrer-Policy + Permissions-Policy.
- **IDOR:** مالکیت در همه routeهای حساس (سفارش/آنالیز/چت/بازارچه/رسید) — انکار = 403/404 + audit.
- **افزوده‌های ۱۴۰۵-۰۶-۱۴/۱۵:** <!-- updated 2026-09-06 --> لایهٔ دوم محافظت پنل (`/_panel_csrf_guard` → 403 + ثبت پایش هنگام فقدان توکن؛ خطای ۵۰۰ «Bad Request» قدیمی حذف شد) • اعتبارسنجی ضد-SSRF برای آدرس پایهٔ پروایدرهای AI (فقط http/https + هوست عمومی، رد لوکال‌هاست/لینک‌لوکال/متادیتا) • صفحات خطای سفارشی 404/405/500 با برند و جستجو (به‌جای صفحهٔ خالی پیش‌فرض) • هدرهای کش برای `robots.txt` و `sitemap.xml`.
- **Git hygiene (P0، 2026-08-22):** دیتابیس‌ها **دیگر در git tracked نیستند** — `.gitignore`: `*.db`، `*.db-wal`، `*.db-shm`، `*.flag`، `bot_edu/data/`، `giso/data/backup/`، `giso/data/.env`، `manifest_latest.json`، `__pycache__/`. (دلیل: توکن بله زنده + کلیدهای AI + PII قبلاً در DBهای committed بودند — در deployment واقعی حتماً کلیدهای قبلی را rotate کن.)
- **Secrets:** توکن ربات در `giso_config.bot_token` (bot.db) یا env • کلیدهای AI در `giso_ai_providers` + `giso/data/.env` • هیچ‌کدام log نمی‌شوند (`httpx` روی WARNING).

### ۸.۳ تم‌های سایت (کلید `site_theme` در bot.db)
| کلید | نام برند جاری |
|---|---|
| `original` | 🎯 مسیر هوشمند گیسو (پیش‌فرض) |
| `smart_assistant` | ✦ دستیار هوشمند — خانه سناریومحور و هدر مشکی/کرم/طلایی |

فقط این دو تم در پنل و ربات قابل انتخاب‌اند. مقادیر تاریخی `simple`، `classic`، `hair_market`، `beauty_ai`، `modern` و `luxury3d` برای سازگاری به `smart_assistant` نگاشت می‌شوند و Selectorها و شرط‌های نمایشی اختصاصی آن‌ها حذف شده‌اند. تم `smart_assistant` از `home_original.css` و لایه محدودشده `theme_experiences.css` استفاده می‌کند. **Route، فرم، سرویس، پنل و چیدمان بیزینسی صفحات داخلی تغییر نمی‌کند.**

### ۸.۴ نکات عملیاتی
- **کلید اصلی پایش:** `monitoring_master` در تب تنظیمات، ثبت خطا/ورود/رفتار، پردازش کمپین و گزارش AI را یکجا متوقف می‌کند؛ داده تاریخی حذف نمی‌شود. تنظیمات ۴۵ ثانیه Cache می‌شوند، Schemaهای پرتکرار هر پردازش فقط یک‌بار آماده می‌شوند و Queue خالی هر ۶۰ ثانیه بررسی می‌شود. هر تب خطا/رفتار/امنیت/کمپین/AI بازنشانی مستقل Super-only با CSRF، تأیید صریح و Audit دارد؛ کمپین‌های queued/sending هرگز پاک نمی‌شوند.
- **نمای کلی و گزارش AI:** `monitoring_ai.py` آمار قطعی خطا، امنیت، رفتار، کمپین و سلامت Provider را تجمیع می‌کند. JobQueue هر ۳۰ دقیقه فقط شرایط را می‌سنجد و حداکثر یک گزارش در ۲۴ ساعت، در ساعت تنظیم‌شده و هنگام کمتر از ۵۰ رویداد در پنج دقیقه تولید می‌کند. ورودی AI فقط اعداد تجمیعی است و خروجی هیچ اقدامی اجرا نمی‌کند.
- **تحلیل رفتار:** `monitoring_events.py` فقط پنج رویداد page_view/action_click/form_start/form_error/form_submit را بدون query string، IP، مقدار فیلد، متن گفتگو یا تصویر ثبت می‌کند؛ مرورگر حداکثر ۲۰ رویداد را batch می‌فرستد و ربات فقط دکمه‌های منوی اصلی را ثبت می‌کند. نگهداری خام ۳۰ روز و گزارش تب رفتار شامل آمار ۲۴ساعته و صفحات/فرم‌های هفت‌روزه است.
- **پیام سراسری:** تب Broadcast در «پایش و گزارش هوشمند» فقط برای سوپرادمین است؛ مخاطب all/centers/buyers/sellers و کانال site/bot/both دارد. اعلان سایت فوری ثبت می‌شود و بله با صف SQLite، claim اتمیک، دسته‌های ۱۰تایی، سه retry و ادامه پس از Restart ارسال می‌شود. گزارش تحویل، بدون اتصال و خوانده‌شدن از داده واقعی است.
- **Maintenance:** فلگ‌های سایت آموزشی و گیسو مستقل‌اند. ربات اصلی فقط برای `ADMIN_IDS` و فقط هنگام Maintenance لینک Hash‌شده، یک‌بارمصرف و ۱۰دقیقه‌ای جدا برای هر سایت می‌سازد؛ لینک قبلی قابل ابطال است و پس از مصرف همچنان ورود عادی ادمین (و OTP گیسو) لازم است. مسیرهای خصوصی اختیاری `MAIN_MAINTENANCE_ADMIN_PATH` و `GISO_MAINTENANCE_ADMIN_PATH` فقط از env خوانده می‌شوند. مسیر گیسو یک پنجره ۱۰دقیقه‌ای برای ورود عادی + OTP باز می‌کند و خودش احراز هویت نیست؛ مسیر سایت اصلی bypass امضاشده HttpOnly با عمر ۱۵ دقیقه می‌سازد. بدون تنظیم env، رفتار سازگار قبلی حفظ می‌شود.
- **آدرس سایت:** `site_base_url` در giso.db `giso_config` — deep-link اعلان‌ها و لینک‌های ربات از آن می‌گیرند (پیش‌فرض `https://gisosadeghi.ir`)؛ تست زنده از ربات/پنل.
- **تست‌ها:** `python -m pytest -q giso/tests/<name>.py` (یا اجرای مستقل فایل‌های legacy). رگرسیون‌های جاری: `test_wallet_unified.py`، `test_p0_wallet_referral_retirement.py`، `test_admin_phrase_normalization.py`، `test_marketplace_notification_delivery.py`، `test_marketplace_phase2_static.py`، `test_marketplace_buyer_photo_ui.py`، `test_user_profile_site_bot_sync.py`، `test_beauty_centers_mvp.py`. تست مراکز schema/SEO/guest gate/register upload/lifecycle/matching/contact/owner/admin/bot/AI را پوشش می‌دهد؛ تست پروفایل، نوشتن مشترک سایت/ربات، whitelist، mirror نام، اتصال بله، مالکیت دکمه اعلان و قرارداد منوی ربات را پوشش می‌دهد؛ تست بازارچه Redirect مهمان، ورود عضو، media path، ابعاد UI و callbackها را کنترل می‌کند. ⚠️ بعضی سوئیت‌های قدیمی با CSRF یا قراردادهای حذف‌شده Referral ناهماهنگ‌اند و باید جدا به‌روزرسانی شوند.
- **Production:** `gunicorn giso.wsgi:application --bind 0.0.0.0:5001 --workers 2` + ربات گیسو جدا (systemd) + nginx برای static/TLS. WAL را روی NFS نگذار.

---

## ۹. وضعیت تحویل جاری و قراردادهای رگرسیون (2026-08-26)

### ۹.۱ خانه، تم و رابط عمومی
- صفحه خانه جدید مسیرمحور است: فروش/بازارچه مو و سلامت/زیبایی هوشمند را جدا می‌کند و سپس به فروشگاه، مراکز و مشاور وصل می‌شود. تصویر اصلی `static/images/giso-main-hero.png` و CSS اختصاصی `home_original.css` است. تم دستیار برای کارت‌های تیره، مراحل، Journey، آمار و CTA پایانی کنتراست صریح متن/پس‌زمینه دارد.
- تم `smart_assistant` مستقل و قابل انتخاب از تنظیمات سوپر است. فقط پوسته عمومی و پیام خانه را تغییر می‌دهد؛ سایر تم‌ها و صفحات داخلی حفظ می‌شوند.
- `responsive_guardrails.css` آخرین لایه محافظ موبایل/تبلت است. منوی عمومی از یک `base.html` می‌آید؛ پنل کاربر و پنل مدیریت layout مستقل دارند.
- `fa_display.js` اعداد انسانی و مبلغ‌های نمایشی را فارسی می‌کند؛ شماره تلفن، tracking code، ID فنی و value فرم برای دقت می‌توانند لاتین بمانند.

### ۹.۲ ربات و عبارت درخواست ادمین
- `httpx` روی WARNING است تا URL حاوی توکن در log عادی چاپ نشود. توکن افشاشده باید بیرون کد rotate شود؛ وضعیت rotation از سورس قابل اثبات نیست.
- Guard عبارت ادمینی در ابتدای `handle_text`، پس از شناسایی کاربر/اشتراک شماره و **پیش از همه stateها، Welcome و AI** اجرا می‌شود. مقایسه نرمال‌شده، cache کوتاه و invalidate پس از تغییر فعال‌اند.
- ثبت تکراری pending idempotent است؛ تأیید/رد callback ربات گیسو فقط سوپر، نتیجه‌محور و دارای پیام جدا برای `already_reviewed`/`request_not_found` است. ادمین تنزل‌یافته خودکار بازنمی‌گردد.
- profile service با SQL خام خارج Flask context نیز قابل استفاده است؛ import محلی shadowکننده `get_giso_db_conn` حذف شده و error handler سراسری PTB ثبت شده است.

### ۹.۳ پنل کاربر و تجربه‌های متصل
- فروش مو، بازارچه فروشنده و «خریدار مو» در یک گروه مفهومی‌اند، ولی workflow و جدول‌هایشان مستقل می‌ماند.
- مرکز آنالیز تب‌های overview/hair/skin/consultant و summary مشترک دارد. سفارش‌ها فقط در شرایط امن COD بدون wallet debit/discount قابل ویرایش‌اند.
- «مرکز زیبایی من» فقط برای مالک مرکز به‌صورت پویا ظاهر می‌شود. «پرسش از مراکز» برای همه کاربران صندوق مستقل، آخرین پیام، وضعیت، badge خوانده‌نشده و deep-link صفحه مرکز دارد.

### ۹.۴ اعتبار همراه هوشمند
- `giso/ai_credits.py` حساب و دفترکل مشترک اعتبار AI سایت/ربات را نگهداری می‌کند؛ اعتبار اولیه و هزینه هر درخواست موفق از پنل AI سوپر تنظیم می‌شود.
- برای کاربر عضو، اعتبار پیش از فراخوانی AI به‌صورت اتمیک رزرو می‌شود؛ خطای provider یا پاسخ fallback اعتبار را idempotent بازمی‌گرداند. سوپر می‌تواند مانده هر کاربر را در تب «اعتبار کاربران» اصلاح کند.
- مانده و مصرف در پروفایل سایت و «پروفایل من» ربات نمایش داده می‌شود. ادمین/سوپر از اعتبار کاربری کسر نمی‌شوند.

### ۹.۵ مدیریت راه دور، Maintenance و پاک‌سازی
- منوی ربات آموزش به `🌐 مدیریت سایت اصلی` و `💎 مدیریت سایت گیسو` تفکیک شده است. تغییر در `bot_edu/` و `web/` برای همین قابلیت مدیریت صریحاً مجاز شده بود؛ خارج این محدوده همچنان locked است.
- Maintenance هر سایت تصویر SVG پیش‌فرض یا تصویر سفارشی WebP دارد؛ ورودی با Pillow، سقف 5MB/20MP و جایگزینی اتمیک کنترل می‌شود. مسیر Login/تأیید ادمین گیسو از Maintenance مستثناست.
- پاک‌سازی مخرب فقط برای شناسه‌های اصلی `ADMIN_IDS`، با preview و تأیید دوم است؛ DB/WAL/SHM، uploads، رسید کیف پول، `.env`، prompts، جدیدترین backup و audit هرگز هدف پاک‌سازی نیستند.

### ۹.۶ Recovery مستقل گیسو
- پنل تنظیمات می‌تواند بسته ZIP مستقل شامل snapshot سازگار `giso.db`، رسیدهای کیف پول و تمام آپلودهای دائمی بسازد؛ `uploads/temp` حذف می‌شود.
- `giso-config.json` فقط تنظیمات غیرمحرمانه و فهرست ادمین‌های مرتبط را برای بازیابی دستی ثبت می‌کند. `bot.db`، توکن ربات، `.env` و کلیدهای API آن هرگز داخل بسته نیستند و Restore نیز `bot.db` را تغییر نمی‌دهد.
- پیش از Restore، مسیرهای ZIP، symlink، Manifest، اندازه، SHA-256 تک‌تک فایل‌ها و `PRAGMA integrity_check` بررسی می‌شوند. Restore فقط برای سوپرادمین، با CSRF، عبارت صریح `RECOVER` و روشن‌بودن Maintenance گیسو اجرا می‌شود.
- دیتابیس اتمیک جایگزین می‌شود؛ فایل‌های overwrite‌شده نسخه rollback دارند. شکست smoke check باعث Rollback دیتابیس و فایل‌ها می‌شود و snapshot اضطراری دیتابیس قبل از Restore در `giso/data/recovery` باقی می‌ماند.
- بسته هنوز باید طبق سیاست عملیاتی به فضای خارج سرور منتقل شود؛ کد داخلی به‌تنهایی Off-site Backup یا Restore Rehearsal دوره‌ای را تضمین نمی‌کند.

### ۹.۷ پروکسی اختصاصی Gemini
- تست سلامت Proxy با API واقعی Gemini و کلید ثبت‌شده انجام می‌شود؛ کلید در Header است و وارد URL/Log نمی‌شود. پاسخ‌های 401/403/429 و خطاهای 5xx سالم محسوب نمی‌شوند.
- نتیجه‌های موفق/ناموفق و latency ذخیره می‌شوند؛ انتخاب Auto ابتدا پایداری و سپس سرعت را در نظر می‌گیرد. سه خطای متوالی Circuit Breaker پانزده‌دقیقه‌ای فعال می‌کند و نتیجه واقعی درخواست‌های Gemini نیز این وضعیت را به‌روزرسانی می‌کند.
- مشخصات Proxy فعال در گزارش ربات Mask می‌شود و query/credential منبع Proxy نمایش داده نمی‌شود.
- Proxyهای عمومی دریافت‌شده از منبع هرگز برای عکس واقعی کاربران استفاده نمی‌شوند. در حالت Auto، Vision فقط Proxy دستی مورد اعتماد را می‌پذیرد و در نبود آن مستقیم متصل می‌شود. Providerهای دیگر و ترتیب Failover تغییری نکرده‌اند.

### ۹.۸ اعلان ورود مشکوک
- اولین ورود موفق هر حساب baseline دستگاه را می‌سازد و هشدار کاذب ایجاد نمی‌کند. ورود موفق بعدی از User-Agent جدید و دقیقاً پنجمین رمز ناموفق طی یک ساعت رویداد مشکوک می‌سازند؛ تلاش‌های بعدی همان موج دوباره Spam نمی‌شوند.
- رویداد پس از Commit و به‌صورت idempotent به اعلان سایت کاربر، پیام Plain Text بله برای حساب متصل و اعلان امنیتی سوپرادمین متصل می‌شود. خطای اعلان هرگز Login را متوقف نمی‌کند.
- متن اعلان IP، User-Agent، Device Hash و IP Hash را افشا نمی‌کند؛ شماره در اعلان سوپرادمین Mask می‌شود. کنترل‌های Master، تاریخچه ورود و تشخیص مشکوک پایش همچنان اعمال می‌شوند.

### ۹.۹ پیش‌فرض امن فرم‌های کاربر
- `safe_form_defaults` تنها نام، تلفن نرمال‌شده، شهر، منطقه و زمان تماس حساب احرازشده را برمی‌گرداند؛ رمز، پاسخ امنیتی، شناسه‌ها، تاریخچه ورود و آدرس دقیق هرگز وارد Context فرم نمی‌شوند.
- فرم ثبت مرکز، ثبت/تبدیل آگهی مو، اعلان ویژگی بازارچه و Checkout فروشگاه از همین منبع استفاده می‌کنند. مقدار POST کاربر در خطای اعتبارسنجی بر مقدار پروفایل اولویت دارد.
- آدرس دقیق سفارش عمداً از شهر/منطقه پروفایل ساخته نمی‌شود و باید برای هر سفارش توسط کاربر وارد شود. مهمان هیچ پیش‌فرض حسابی دریافت نمی‌کند و تمام ورودی‌ها همچنان سمت سرور اعتبارسنجی می‌شوند.

### ۹.۱۰ مأموریت‌های Spend
- سه مأموریت واقعی جدید به Seed قابل حذف پنل اضافه شده‌اند: انتشار اولین مرکز زیبایی (۳۰ هزار)، مشاهده واقعی محصولات (۵۰ هزار) و اتصال معتبر بله (۲۰ هزار تومان Spend). همه غیرقابل تسویه‌اند و مبلغ‌ها از پنل مالی قابل تغییر/غیرفعال‌سازی هستند.
- مأموریت مشاهده محصول فقط برای عضو واردشده، سه محصول منتشرشده متفاوت و گذشت حداقل ۳۰ ثانیه از اولین مشاهده تکمیل می‌شود؛ Refresh و محصول Draft پیشرفت ایجاد نمی‌کند.
- اتصال بله فقط پس از اشتراک شماره و تطبیق آن با حساب واقعی سایت پرداخت می‌شود. انتشار مرکز فقط بعد از تأیید مدیریت است. ثبت نظر بازارچه و آگهی بازارچه نیز به Eventهای موجودشان متصل شدند.
- فرم ایجاد/ویرایش مأموریت (پنل سوپر، تب مأموریت‌ها) سه فیلد تکمیلی دارد: **نوع اعتبار پاداش** (`reward_scope` = spend/cash)، **امتیاز رتبه** (`reward_points`) و **نوع مأموریت** (`mission_type` = once/daily/weekly). بک‌اند `wallet_missions.create_mission/update_mission` این‌ها را ذخیره می‌کند و در لیست نمایش داده می‌شود.
- پرداخت با `BEGIN IMMEDIATE`، Completion یکتا و Idempotency Key انجام می‌شود؛ هر مأموریت برای هر کاربر فقط یک بار و فقط در `balance_scope='spend'` پرداخت می‌شود. ⚠️ در حال حاضر `mission_type` فقط ذخیره/نمایش می‌شود و در `complete_mission` **هنوز اعمال نمی‌شود** (تکرار واقعی روزانه/هفتگی = کار E باقی‌مانده از سناریو).

### ۹.۱۱ گزارش باگ و تأیید پاداش
- فرم گزارش باگ داخل «پیام‌ها و پشتیبانی» عنوان، مسیر داخلی و مراحل بازتولید را ثبت می‌کند. ثبت فرم هیچ تراکنش مالی ایجاد نمی‌کند.
- Fingerprint نرمال‌شده گزارش‌های pending/approved مشابه را فقط برای بررسی به گزارش قبلی پیوند می‌دهد و تصمیم خودکار نمی‌گیرد. سوپرادمین گزارش‌های جدید را داخل تب خطاهای پایش به‌صورت دستی تأیید، رد یا تکراری می‌کند و تصمیم Audit می‌شود.
- فقط تصمیم `approved` مأموریت `bug_report_approved` را اجرا می‌کند؛ پاداش پیش‌فرض ۳۰ هزار تومان Spend، یک‌بار برای هر کاربر و قابل تغییر/غیرفعال‌سازی در مرکز مالی است. شکست پرداخت وضعیت را pending نگه می‌دارد تا گزارش تأییدشده بدون پاداش باقی نماند.

### ۹.۱۲ محدودیت‌ها و بدهی‌های شناخته‌شده (نباید به‌عنوان قابلیت کامل گزارش شوند)
1. JobQueue با `python-telegram-bot[job-queue]==20.7` در هر دو requirements فعال شده است.
2. خریدهای اعتباری مرکز و بازارچه (نردبان/ویژه/تمدید، اعلان خریدار و بسته پیشنهاد اضافه) nonce پایدار و بررسی replay دارند؛ تست فشار هم‌زمانی همچنان بخشی از چک‌لیست انتشار است.
3. Recovery مستقل پنل گیسو اتمیک و checksum‌دار است؛ مسیر restore آموزشی در `bot_edu/handlers.py` عمداً خارج از این Recovery مانده و هنوز بدهی جداگانه خود را دارد.
4. Recovery فایل‌های دائمی و رسیدها را پوشش می‌دهد، اما انتقال Off-site و تمرین زمان‌بندی‌شده Restore هنوز زیرساخت عملیاتی می‌خواهد.
5. rate-limit حافظه‌ای بین workerهای Gunicorn مشترک نیست. ظرفیت 100/500 کاربر بدون load test تأیید نشده است.
6. هویت سوپرادمین در `giso/config.py` ثابت است و باید در bootstrap امن آینده تعیین تکلیف شود.
7. `USER_MODULE_GROUPS` **خالی نیست**. در `giso/panel_user/permissions.py` چهار گروه `اصلی/خدمات/پشتیبانی/حساب کاربری` تعریف شده‌اند و `_menu_for_current_user()` از همین ساختار برای منوی گروه‌بندی‌شده استفاده می‌کند. `MODULES_META` نیز برای `marketplace`, `buyer_request`, `beauty_center`, `shop`, `notifications`, `reviews`, `wishlist`, `reservations`, `center_chats`, `ai_assistant` metadata دارد.

### ۹.۱۳ چک‌لیست تحویل و تست
1. پیش از migration از `giso/data/giso.db` موجود backup بگیر.
2. زنجیره هر قابلیت را کامل تست کن: `Button → JS/Form → Route → Service → DB/API → Response`.
3. تست‌های هدفمند جدید: `test_bot_runtime_regressions.py`، `test_center_detail_and_glass_nav.py`، `test_edu_giso_remote_management.py` و `test_phase1..6_*`.
4. تست استاتیک یا وجود route کافی نیست؛ نتیجه runtime را با برچسب **NOT VERIFIED — REQUIRES RUNTIME TEST** گزارش کن.
5. هیچ Secret، token، شماره کامل حساس یا محتوای `.env` را در log، commit message یا گزارش چاپ نکن.

---

## ۱۰. بازرس هوشمند و منوی جدید سوپر (2026-08-30)

### ۱۰.۱ بازرس هوشمند L0 — ماژول `giso/monitoring_insights.py`
موتور آفلاین و **بدون فشار روی سایت Flask** که فقط داخل شغل دوره‌ای ربات اجرا می‌شود:
- **عیب‌یاب باگ (`triage_open_errors`):** خطاهای باز ثبت‌شده در `giso_system_errors` را بر اساس `fingerprint` خوشه‌بندی می‌کند و حداکثر ۵ خوشهٔ داغ را با AI تحلیل می‌کند. خروجی JSON آزاد (علت ریشه‌ای/محل/شدت/نیاز به اقدام/راه‌حل پیشنهادی/`code_hint` متنی برچسب «تأییدنشده»/اطمینان) در ستون `ai_triage` خطا ذخیره می‌شود.
- **بازرس بهبود (`collect_improvement_insights`):** از اعداد تجمیعی محافظت‌شدهٔ حریم خصوصی (`monitoring_ai.aggregate` + `monitoring_events.report` + شمارش صف‌ها روی hair_orders/product_orders/giso_support_tickets/consultant_requests) حداکثر ۵ پیشنهاد با evidence عددی و confidence استخراج و در جدول جدید **`giso_insights`** ذخیره می‌کند (ضدتکرار بر اساس kind+title طی ۷ روز).
- **دادهٔ ورودی AI فقط اعداد تجمیعی و traceback ماسک‌شده است** (`_sanitize` توکن/شماره/secret را می‌پوشاند). AI هیچ کدی اجرا/ویرایش نمی‌کند؛ `code_hint` فقط متن ذخیره می‌شود.
- actor آفلاین (`monitoring:triage`/`monitoring:insights`/`monitoring:system`) فقط در جدول‌های خودش می‌نویسد و **نمی‌تواند اقدام معلق (pending action) بسازد**.

**اسکیمای افزایشی:** جدول `giso_insights` (kind/severity/title/detail/evidence/suggestion/code_hint/confidence/status/error_fp/source_run_at) + دو ستون `ai_triage`/`ai_triage_at` روی `giso_system_errors` (idempotent؛ اگر اتصال مشترک باشد اول `monitoring_errors.ensure` صدا زده می‌شود).

### ۱۰.۲ شغل آفلاین ربات
- در `giso/bot.py` تابع `_insights_job(context)` (دقیقاً بعد از `_monitoring_ai_job`) هر دو موتور را صدا می‌زند و داخل `_init_monitoring_ai` با `run_repeating(interval=900, first=420, name='giso_insights')` ثبت شده است.
- شغل **با سوییچ `monitoring_settings.enabled('ai_reports')` گیت می‌شود** — اگر خاموش باشد فوراً برمی‌گردد. شغل `giso_monitoring_ai` موجود (interval=1800) دست‌نخورده ماند.

### ۱۰.۳ سه گزارش قطعی دستیار (صفر تماس AI در لحظه)
در `giso/ai_runtime.py` سه اکشن سوپرادمین اضافه شد که فقط دادهٔ از پیش محاسبه‌شده را می‌خوانند:
- `report_incidents` (🐞 خطایابی) ← `monitoring_insights.incidents_report()`
- `report_insights` (💡 پیشنهاد بهبود) ← `improvements_report()`
- `report_health` (📊 سلامت) ← `health_report()`
- در `SUPPORTED_SUPER_ACTIONS` و `SECTION_TABLES` (همه section=`reports`، multiple tables) ثبت و در `execute_superadmin_report` دیسپچ می‌شوند.
- **کلیدواژه‌های نیت** در `_build_superadmin_action_plan` و **قبل از** early-return چت عمومی قرار گرفتند (وگرنه `_looks_like_general_management_chat` با سوزن «بهبود/پیشنهاد» آن‌ها را می‌بلعید). نیت‌ها: «خطایاب/عیب‌یاب/باگ/خطاها/گزارش خطا»، «پیشنهاد بهبود/بهبود سایت/بهبود ربات/توصیه بهبود/بازرس هوشمند»، «سلامت سرویس/سلامت سیستم/سالم بودن/همه چیز عادی».
- دکمه‌های سریع بالای چت (`SUGGESTED_PROMPTS` در `panel/modules/super_assistant.py`): سه آیتم اول همین گزارش‌ها.
- **جریان وضعیت یافته:** روت `POST /admin/super-assistant/insight-status` (فقط سوپر، CSRF) → `monitoring_insights.set_insight_status(id, status)` با مقادیر `new|seen|applied|dismissed`.

### ۱۰.۴ منوی جدید پنل سوپرادمین (بازچینش دیداری، صفر تغییر روت/داده)
در `giso/panel/permissions.py` فقط `MODULES_META` و `MODULE_GROUPS` تغییر کرد (منو صرفاً تولید لینک روی همین متادیتاست؛ روت/گارد/داده مستقل‌اند):
- ترتیب: **🤖 دستیار هوشمند (ردیف ۱)** • 📊 پیشخوان • گروه **📥 صندوق کارها** (hair_sale/marketplace/beauty_centers/analyses/shop/consults) • 💳 مرکز مالی • گروه **⚙️ تنظیمات پیشرفته** (users/admins/ai/settings).
- ماژول **`monitoring` از سایدبار حذف دیداری شد** ولی روت/صفحه‌اش فعال و با لینک مستقیم/بوکمارک و از داخل دستیار در دسترس است؛ `reports` و `backup`/`ratelimit`/`channel` نیز از سایدبار برداشته شدند (همه route فعال، SUPER_ONLY_MODULES گارد را می‌زند نه منو).

### ۱۰.۵ استقرار و هم‌زمانی (یافتهٔ تست بار)
- سایت‌های Flask با `app.run(threaded=True)` پیش‌فرض Flask 3 اجرا می‌شوند (نخ‌ها موازی‌اند ولی تک‌فرایند). تست بار واقعی: ۲۰۰ درخواست هم‌زمان بدون خطا پاسخ شد، اما هجوم یک‌جا روی رندر صفحه ~۱۲–۱۴s و بار پخش‌شده (~۲۰cc) ~۱s شد؛ مسیر سبک ~۷۰۰ req/s. گلوگاه، **سرور توسعه به‌جای WSGI production** است.
- نقطهٔ ورود production آماده است: `giso/wsgi.py` (برای gunicorn)؛ روی استقرار تولید باید به **waitress/gunicorn** مهاجرت شود. rate-limit فعلاً in-process است و با چند worker باید به Redis برود.


---

## ۱۱. قوانین توسعه و نگهداری (برگرفته از `docs/reports/GISO_PHASE_1_AUDIT_MODULAR_DB.md` + بازبینی 2026-08-31)

> این بخش «قانون» است و هر عاملِ هوشمند/توسعه‌دهنده باید پیش از هر تغییر آن را بخواند.
> هدف: جلوگیری از بازگشتِ فایل‌های بزرگ، حفظ ساختار ماژولار و عدم شکستن رفتار موجود.

### ۱۱.۱ قوانین غیرقابل‌تخطی (Non-negotiable)
1. **Audit قبل از refactor** — هر تغییر بزرگ اول با «بازخوانی کد + درک وابستگی‌ها» شروع شود.
2. **هیچ بازنویسیِ Big-Bang** — تغییرات کوچک و قابل بازبینی؛ بعد از هر تغییر منطقی، تستِ مربوطه.
3. **هیچ افزودن feature در حین refactor ساختاری** — ساختار را تغییر بده، نه رفتار را.
4. **هیچ حذف صامت (silent deletion)** — حذف هر چیز باید مستند و جایگزین داشته باشد.
5. **حفظ رفتار و importهای عمومی** — URL/JSON/قالب و نام‌های import شده تغییر نکنند مگر مستند.
6. **جلوگیری از circular import** — ارتباطات ماژول به ماژول یا lazy/local import داخل توابع.
7. **ممنوعیت فایل‌های عمومی بزرگ** — `utils.py` / `helpers.py` / `services.py` عمومی ساخته نشود؛ فقط ماژولِ دامنه‌دار (`feature/routes.py`، `feature/service.py`، …).
8. **نسخهٔ قابل بازگشت git** — پیش از کارِ پرریسک، checkpoint/backup.
9. **دست نزن `bot_edu/` و `web/`** — مگر با دلیلِ مستند + دستور صریح.

### ۱۱.۲ قانون طلایی «هر ماژول در پوشهٔ خودش» (هر کد در خانهٔ دامنه‌اش)
- کدِ مربوط به هر دامنه باید در **همان پوشه/ماژولِ دامنه** زیر `giso/` نوشته شود — نه در فایل‌های بزرگِ سراسری.
- **نقشهٔ خانهٔ هر کد:**

| دامنه | محل درست |
|---|---|
| ربات کاربر | `giso/bot_user_actions.py` |
| ربات ادمین | `giso/bot_admin_utils.py` |
| کمکی ربات | `giso/bot_helpers.py` |
| کیف پول/مأموریت | `giso/wallet_core.py` + `giso/wallet_missions.py` + `giso/wallet_receipts.py` |
| پنل سوپر (مالی/…) | `giso/panel/modules/` (هر ماژول یک فایل)؛ قالب در `giso/panel/templates/modules/` |
| پنل کاربر | `giso/panel_user/modules/` (هر ماژول یک فایل)؛ قالب در `giso/panel_user/templates/user_modules/` |
| فروشگاه | `giso/shop/` (routes / logic / bot / panel) |
| بازارچه | `giso/marketplace/` (routes / services / schema / settings) |
| مراکز زیبایی | `giso/beauty_centers/` (routes/services/schema/templates/…/bot_handlers) |
| آنالیز/AI | `giso/analysis.py` + `giso/ai_runtime.py` + `giso/ai_brain.py` + `giso/gemini_proxy_manager.py` |
| کارت محصول مشاور | `giso/consultant_cards.py` |
| چت مشاور / دستیار | `giso/ai_runtime.py` + `giso/special_assistant.py` |

- **اگر ماژول از آستانه گذشت → ماژول جدید با نام واضح** (نه فایل عمومی). الگوی نام: `<feature>_<action>.py`، re-export از فایل اصلی برای backward compatibility.

### ۱۱.۳ آستانه‌های عملی (Review Thresholds)
- `giso/bot.py` پیش‌فرض معمولاً **≤ ۷۵۷۷** خط؛ برای هر تغییر فقط `import`/`dispatch` (۱–۲ خط) — نه بدنه.
- `giso/app.py` سقف **≤ ۲۳۰۰** (وضعیت 2026-09-06: ۲۲۹۹)؛ `giso/wallet.py` **≤ ۷۲۳** (۶۹۹)؛ `giso/analysis.py` هدف **~۲۲۰۰** (۲۲۶۲). <!-- updated 2026-09-06 -->
- هر فایل جدید ترجیحاً زیر **~۵۰۰–۱۵۰۰** خط؛ اگر بیشتر شد، تقسیم کن.
- بدون کد تکراری: اگر تابع مشابهی هست، import کن، دوباره ننویس.
- قاعدهٔ فراخوان: «این تابع به کدام دامنه تعلق دارد؟» سپس ماژولِ همان دامنه را انتخاب کن. اگر شک داشتی، ماژول جدید با نام واضح بساز.

### ۱۱.۴ قراردادهای ثابت
- importها مطلق و با پیشوند `giso.`؛ فقط `phoneutil` و `giso_admin` از `bot_edu` مجازند.
- `get_giso_db_conn()` / `get_bot_db_conn()` تنها راه اتصال DB؛ هرگز `sqlite3.connect` دستی.
- داده شبیه‌سازی‌شده ممنوع؛ همهٔ آمار از DB واقعی.
- ری‌استارت فقط از مسیر flag پروژه؛ token/key در لاگ نمی‌آید.
- pre-push: `SECRET_KEY=... python -m pytest giso/tests/<name>.py` رگرسیون سبز.

---

## ۱۲. پنل کاربر — راهنمای جامع (ربات + سایت)

> اگر دربارهٔ هر بخشِ پنل کاربر سؤال داشتی، از همین بخش بخوان. هر مدخل: مقصد + روت/دکمه + کاری که انجام می‌دهد + منبع داده.

### ۱۲.۱ پنل کاربر **در ربات** (منوی کاربر)

کیبورد reply کاربر **۶ دکمهٔ اصلی** است (`giso/bot.py::_user_kb`):

| دکمه | دکمهٔ متنی | مسیر اجرا | محتوا |
|---|---|---|---|
| 💰 کیف پول | `ua\|wallet\|main` | `bot_user_actions.wallet_main` | مانده Cash/Spend + رتبه + دکمه‌های شارژ/تسویه/تاریخچه/منو |
| 🎯 مأموریت | `ua\|mission\|main` | `missions_view` | لیست مأموریت‌های فعال + وضعیت + امتیاز/رتبه + «🏆 رتبه‌بندی هفته» |
| 💬 مشاور | `_start_consultant_ai_chat` | چت AI | گزارش کوتاه `consultant_report` + «💬 سوال بپرس» |
| 👤 پروفایل | `ua\|profile\|main` | `profile_main` | نام/شهر/رتبه/امتیاز + ویرایش (`upro\|*`) |
| 🎧 پشتیبانی | `handle_support_menu_text` | تیکت | تیکت جدید + تیکت‌های من؛ `giso_support_tickets` |
| 📖 راهنما | `send_user_help` | راهنما | توضیح ۶ دکمه + رتبه‌ها + `/wallet` `/support` `/help` |

**«⚡️ عملیات سریع من»** (دکمهٔ reply/قدیمی، `home_menu` در `bot_user_actions.py`) داشبورد سریع با ۶ ورودی عملیات (آنالیز من / فروش مو / بازارچه من / سفارش‌ها / مرکز من / کیف پول + راهنما + داشبورد سایت) را نشان می‌دهد.

**همهٔ زیرمنوهای `ua|`** از `route(phone, data)` dispatch می‌شوند (`bot_user_actions._ROUTES` = **۲۸ کلید**): <!-- updated 2026-09-06 -->
| `ua|…` | |
|---|---|
| `ua\|home` | منوی عملیات سریع |
| `ua\|help` | راهنمای کاربر |
| `ua\|wallet\|main` | کیف پول |
| `ua\|wallet\|history` | تاریخچه تراکنش‌ها |
| `ua\|mission\|main` | مأموریت‌ها |
| `ua\|rank\|week` | رتبه‌بندی هفته |
| `ua\|profile\|main` | پروفایل |
| `ua\|consult\|report` | گزارش مشاور |
| `ua\|anal\|last` / `ua\|anal\|plan` / `ua\|anal\|check` / `ua\|anal\|consult` / `ua\|anal\|products` | وضعیت آنالیز / برنامه / چک‌لیست / درخواست مشاوره / محصولات پیشنهادی |
| `ua\|hair\|status` / `ua\|hair\|price` / `ua\|hair\|chatlist` / `ua\|hair\|chat` | وضعیت فروش مو / قیمت / لیست گفتگو / گفتگو با کارشناس |
| `ua\|mkt\|my` / `ua\|mkt\|offers` / `ua\|mkt\|chat` / `ua\|mkt\|stats` / `ua\|mkt\|statslist` | آگهی‌های من / پیشنهادها / گفتگو / آمار آگهی / لیست آمار |
| `ua\|shop\|orders` / `ua\|shop\|track` / `ua\|shop\|reorder` / `ua\|shop\|invoice` | سفارش‌های من / پیگیری / سفارش مجدد / فاکتور |
| `ua\|center\|stats` / `ua\|center\|msgs` / `ua\|center\|renew` | آمار مرکز / پیام‌های مرکز / تمدید مرکز |

- callbackها با پیشوند `ua|` در `handle_callback` → `_uact.handle_ua_callback` (نام‌فضای اختصاصی، بعد از همهٔ هندلرها) پردازش می‌شوند.
- همهٔ لینک‌ها از `get_site_url()` ساخته می‌شوند؛ بدون عددِ جعلی؛ منبع داده DB واقعی (`get_giso_db_conn` / `giso.wallet` / `giso.base`).

### ۱۲.۲ پنل کاربر **در سایت** (`panel_user_bp`، prefix `/dashboard`)

گارد: مهمان → Login/Register با `next`؛ ادمین/سوپر → `/admin`. همیشه `user_profile_service` منبع پروفایل مشترک سایت/ربات است.

**منوی سایدبار (متن `USER_MODULES` در `giso/panel_user/permissions.py`):**

| ماژول | روت | نقش |
|---|---|---|
| `overview` | `/dashboard` و `/dashboard/overview` | پیشخوان/خلاصه من؛ آمار، میانبرها، اعلان‌ها |
| `hair_sale` | `/dashboard/hair-sale` (+ زیر منو: «فروش مو به گیسو»، «بازارچه مو» → `/dashboard/marketplace`، «خریدار مو» → `/dashboard/hair/buyer-request`) | بررسی و فروش مو؛ ثبت درخواست، پیگیری وضعیت/قیمت |
| `orders` | `/dashboard/orders` (+ `/orders/<id>/edit` POST) | خریدهای من از فروشگاه؛ وضعیت، فاکتور، ویرایش امن COD |
| `analyses` | `/dashboard/analyses` (+ alias `/analysis-history`، restore/archive) | آنالیزها و برنامه من؛ گزارش/برنامه/راهکار |
| `wallet` | `/dashboard/wallet` (+ `topup`/`withdraw` POST) | کیف پول؛ موجودی نقدی/مصرفی، شارژ با رسید، تسویه، مأموریت |
| `chats` | `/dashboard/chats` (+ alias `/conversations`، POST `support` و `bug-report`) | پیام‌ها و پشتیبانی؛ تیکت + گزارش باگ |
| `profile` | `/dashboard/profile` | پروفایل؛ نام/شهر/خلاصه فعالیت + تغییر رمز (۵ تلاش/ساعت) |
| `beauty_center` | `beauty_centers.owner_dashboard` | فقط برای مالک مرکز (پویا به منو اضافه می‌شود)؛ `🏥 مرکز زیبایی من` |

**ساختارِ قابل‌مشاهدهٔ سایدبار** (از `giso/panel_user/templates/partials/user_sidebar.html`): برای هر آیتمِ درون‑حلقهٔ `menu` یک لینک ساخته می‌شود، به‌جز:

- `overview` → «پیشخوان (خلاصه من)» (اولین آیتم).
- `hair_sale` → به‌صورت **گروه برچسب‌دار «مدیریت مو»** رندر می‌شود و سه لینکِ زیرمجموعه دارد:
  [۱] **فروش مو به گیسو** → `panel_user.hair_sale` ✓
  [۲] **بازارچه مو** → `panel_user.marketplace` ✓
  [۳] **خریدار مو** → `panel_user.buyer_request` ✓
- `beauty_center` → فقط اگر کاربر مالکِ مرکز باشد اضافه می‌شود (`get_owner_center`) → `beauty_centers.owner_dashboard`.
- بقیه (`orders`, `analyses`, `wallet`, `chats`, `profile`) → لینک سادهٔ `panel_user.<m>`.

**پایِ سایدبار:** «راهنمای پنل» (`?tour=1`) + «بازگشت به سایت» + «خروج».

**آیتم‌های خارج از سایدبار** (روتِ فعال دارند ولی آیتمِ سایدبار نیستند و از لینک مستقیم/صفحهٔ مرتبط در دسترس‌اند): `shop`، `notifies`، `wishlist`، `notifications`، `reviews`، `center-conversations`. منوی سایدبار دقیقاً = حلقهٔ روی `_menu_for_current_user()` = `USER_MODULES` (۷) + `beauty_center` (پویا).

**مسیرهای سایتِ بیرون از پنل (پنل اصلی سمتِ راست/عمومی):**

| بخش | روت | نقش |
|---|---|---|
| فروش مو | `/hair-sale` | فرم ۴ مرحله‌ای: عکس + تخمین قیمت زنده (`calculate_hair_price`) → مشخصات → تماس → `sale_path`؛ ردیف `hair_orders` |
| آنالیز | `/analysis` → `/analysis/hair|skin` → گزارش | آپلود عکس + AI Vision + سوالات + گزارش/برنامه/راهکار + PDF فارسی + چت مشاور (`/api/consultant-chat/*`) |
| فروشگاه | `/shop` → `/shop/product/<id>` | کاتالوگ، سبد خرید (`giso_cart`)، پرداخت COD/کیف پول، فاکتور/کد پیگیری |
| بازارچه | `/marketplace` | آگهی‌های مو؛ `HairListing`/`BuyerProfile`/`BuyerOffer`؛ چت per-offer |
| مراکز زیبایی | `/beauty-centers` | دایرکتوری (معرفی صرف)؛ ثبت مرکز، گفتگو، تمدید/ارتقا |

**منبع دادهٔ مشترک:** همه از `giso/data/giso.db` (WAL)؛ پروفایل از `giso.user_profile_service`؛ کیف پول از `giso.wallet`؛ اعلان‌ها از `giso_notifications` + Bell/Toast سایت (`giso_notifications.js`).

---

## ۱۳. تحویل ۱ شهریور ۱۴۰۵ (2026-09-01)

تست زندهٔ پنج‌نقشه (سوپر / کاربر / طراح / دیباگر / سرعت) روی `create_app()` + `test_client`؛ سایت بدون `BOT_TOKEN` بالا می‌آید.

**بسته شد**
- عکس واقعی ۱۵ محصول آرایشی published در `giso/static/images/catalog/`؛ `/shop` و `/api/recommendations` (`count=2` روی آنالیز تست).
- NameError پنل: `_beauty_admin` → `_beauty_centers`؛ `monitoring_bug_review` از `current_user`.
- `get_admin_target` برای سوپر `bale_id=1191639507`.
- snapshot `delete_user_data` بدون `ORDER BY id` اجباری روی `giso_users`.
- CSRF پنل فعال (POST بدون توکن → ۴۰۰). کاربر عادی `/admin` → ۳۰۲ `/login`.
- SEO عمومی: Organization + WebSite schema، `og:locale=fa_IR`، `og:image` PNG (نه SVG)، `robots.txt` با `Allow: /marketplace`، sitemap محصول.
- سقف خط: `bot.py` ≤7577، `app.py` ≤2300، `analysis.py` ≤2400.

**باز (نباید کامل گزارش شود)**
- تغذیه `special_order` بدون عکس.
- ویجت چت بدون کلید AI → 503.
- عبارت کوتاه «درخواست‌های فروش مو» در دستیار ممکن است به چت آزاد برود.
- `giso/data/backup/*.db` خالی؛ recovery zip جداست.
- pytest: `/beauty-centers/media/<id>` در MVP ممکن است ۴۰۴ بدهد؛ import `telegram` برای قرارداد ربات مراکز در محیط بدون PTB می‌شکند.

**سرعت نمونه (test_client):** `/` ~۷۳ms، `/shop` ~۸۱ms، `/admin` ~۱۰۳ms.

---

## §14. تحویل ۱۰ شهریور ۱۴۰۵ (2026-09-01) — اجرای ۱۹ مورد `img/help.md`

**۱۹ مورد اسکرین‌شات کارفرما، ۱۸ مورد اصلاح شد (۱–۱۸) + تحلیل مورد ۱۹.** کیت کامل تست قبل/بعد: **۴۶۸ پاس / ۶۲ شکست** — بیس‌لاین عیناً حفظ شد، صفر رگرسیون. سقف‌ها رعایت شد (app ۲۱۷۸≤۲۳۰۰، wallet ۶۹۰≤۷۲۳، bot.py فقط خط‌های متنی، بدون ریفکتور).

| # | موضوع | اصلاح | محل |
|---|--------|------|------|
| 1 | «مشاهده لیست» فروشگاه خالی | ۲۴ محصول از `catalog/products.json` بذر شد | `giso/scripts/seed_catalog.py` (جدید) |
| 2 | فاصله نوار بالا تا محتوای داشبورد | `padding-bottom` در `--shell-pad` ادغام شد | `templates/base.html` + `style.css` |
| 3 | مأموریت‌ها جای دیگری | زنگولهٔ دوم «مأموریت‌ها» در هدر + کشو با مأموریت‌های در انتظار | `panel_user/templates/partials/user_topbar.html`، `user_layout.html`، `panel_user/routes.py`، `panel_user.css` |
| 4 | فونت نامتوازن در داشبورد | `font-weight:500` روی تیترهای داشبورد | `static/css/style.css` |
| 5 | «مشاهده لیست» فروشگاه خالی (تکراری ۱) | همان مورد ۱ | — |
| 6a | «نمایش چت» بدون چت | مسیر جدید `/consultant/<token>/chat/<cid>` با thread واقعی | `app.py` + **`giso/consultant_chat_service.py`** (دامنهٔ جدید؛ app.py به ۲۱۷۸ برگشت) |
| 6b | «گفتگو با کارشناس» بدون چت | «گفتگوها» در منوی ربات + صفحهٔ گفتگو با ورودی پیام؛ پاسخ از دستیار سوپرادمین (`/chat/<id>/reply`) | `app.py`، `bot_user_actions.py`، `templates/dashboard_consultant_chat.html` |
| 7 | «مشاهده لیست» خالی در پروفایل | لینک‌ها به `/hair-sale` با محتوای واقعی اصلاح شد | `panel_user/templates/user_modules/profile.html` |
| 8 | پیام خوش‌آمد/خروجی بی‌روح | ۶ سناریوی `get_smart_welcome_context` (خوش‌آمد + عضویت + جمع‌بندی وضعیت) و ۴ خروجی یکسان‌سازی شد؛ **فقط ai_runtime.py — bot.py دست‌نخورده** | `giso/ai_runtime.py` |
| 9 | زنگوله «۴ رو بخون» | متن «۴ مورد خوانده‌نشده داری» + badge فارسی «خوانده‌نشده» | `panel_user/routes.py` + `user_modules/notifications.html` |
| 10 | «موتور کسر اعتبار خدمات» | **کارت از پنل مالی حذف شد** (سازندهٔ کارمزد حذف شده بود). توابع `get_service_fees/save_service_fees/charge_service_fee` در `wallet.py` برای سازگاری ماندند؛ جای نظر در قالب با کامنت ثبت شد | `panel/templates/modules/wallet.html` |
| 11 | «اعتبار اولیه/اعتبار کاربر» | **بازنویسی `giso/ai_credits.py`:** اعتبار عددی جدا حذف؛ مانده = «اعتبار مصرفی» کیف پول، کسر/بازپرداخت روی `wallet_transactions` با scope=spend و کلید idempotency؛ ورودی «اعتبار اولیه» از فرم پنل حذف و برچسب هزینه «تومان» شد | `giso/ai_credits.py`، `panel/modules/ai.py`، `panel/templates/modules/ai.html` |
| 12 | پیام «اعتبار اولیه فعاله» | متن «اعتبار کاربر فعاله — هزینه هر درخواست موفق از اعتبار مصرفی کیف پول کسر می‌شه» | `ai.html` |
| 13 | «تنظیمات اعلان‌ها» | دو تب واقعی «اعلان‌های ربات / اعلان‌های سایت» با فرم‌های مجزا | `panel/templates/modules/notifications.html` + `panel/modules/notifications.py` |
| 14 | «تنظیمات مالی» | لینک درست به `panel.wallet?tab=settings` + تب `tab=notifications` | `panel/templates/modules/super_assistant.html` |
| 15 | «مشاهده لیست» خالی (پروفایل) | همان ۷ | — |
| 16 | «برو به بخش مربوطه» | راهنمای هر مأموریت + پیشرفت زنده (`wallet_product_mission_views`) + دکمهٔ رفتن به بخش مربوطه؛ هدر «🎁 اعتبار رایگان می‌خوای؟» | `panel_user/templates/user_modules/wallet.html`، `panel_user/modules/_base.py`، `giso/wallet_missions.py` |
| 17 | «حذف خوانده‌شده‌ها» | مسیر + دکمهٔ واقعی؛ «پاک‌کردن همهٔ ورودها» به `clear_login_history` وصل شد | `panel_user/routes.py` + `user_modules/notifications.html` |
| 18 | آدرس localhost در اعلان‌ها | گارد در ذخیره (`set_site_base_url`) + گارد در خواندن (`_site_base_url`) برای localhost/IP خصوصی؛ ارجاع اعلان‌ها فارسی شد («🔖 موضوع: …») | `panel/modules/settings.py`، `panel/modules/notifications.py` |
| 19 | Lighthouse ۶۶ | فقط تحلیل/گزارش — کد دست‌نخورده (گزارش جدا تحویل شد) | — |

**تغییرات رفتاری که باید بدانید:**
- `get_ai_credit` اکنون ماندهٔ «اعتبار مصرفی» کیف پول را برمی‌گرداند؛ ستون عددی `balance` در جدول کاربران فقط برای حسابرسی نمایش داده می‌شود و هیچ‌چیز را gate نمی‌کند. کلیدهای config `ai_user_initial_credit`/`ai_user_credit_enabled` همچنان خوانده می‌شوند (سازگاری عقب‌رو).
- ورودی «اعتبار اولیه» از فرم سیاست اعتبار پنل AI حذف شد؛ ذخیره فقط «هزینه هر درخواست» را می‌نویسد.
- `_site_base_url()` مقدار ذخیره‌شدهٔ localhost/خصوصی را نادیده می‌گیرد و به `https://gisosadeghi.ir` برمی‌گردد.
- DB توسعه (`giso/data/giso.db`) بعد از تست‌ها پاک و بازسازی شد (gitignore).

**مورد ۱۹ اجرا شد (۱۴۰۵-۰۶-۱۰):**
- Font Awesome و وزیرمتن **self-host** شدند: `static/vendor/fontawesome/` (فقط solid: `fontawesome.min.css` + `solid.min.css` + `fa-solid-900.woff2` از بستهٔ رسمی 6.6.0) و `static/fonts/Vazirmatn-{Regular,Bold}.woff2` (زیرمجموعهٔ فارسی/لاتین با fontTools از TTFهای موجود) + `static/css/vazirmatn.css` (@font-face با font-display:swap). هر سه layout (`templates/base.html`، `panel/templates/layout.html`، `panel_user/templates/user_layout.html`) از لینک‌های Google/cdnjs به منابع محلی + `preload` تغییر کردند.
- **gzip:** ماژول جدید `giso/perf.py` (میان‌افزار فشرده‌سازی متن، فقط وقتی لایهٔ دیگر Content-Encoding نگذاشته باشد)؛ اتصال ۲ خطی در `app.py` (۲۱۸۷ خط ≤ سقف ۲۳۰۰).
- دو آیکون خراب (از قبل در FA-free موجود نبودند) اصلاح شد: `fa-sparkles`→`fa-wand-sparkles` و `fa-grid-2`→`fa-table-cells-large` در قالب‌های shop/index/beauty_centers.
- باقی‌ماندهٔ مورد ۱۹ که **استقرار/infra** است (کد نیست): جایگزینی hero ۱.۶MB روی سرور با فایل ریپو، فعال‌سازی gzip/brotli و HTTP/2 در nginx. جزئیات: `docs/GISO_LIGHTHOUSE_19.md`.

**استقرار لینوکس/ایران (۱۴۰۵-۰۶-۱۰):**
- `GEMINI_BASE_URL` در `giso/config.py` (از env یا `/etc/giso/web.env`): وقتی تنظیم شود، **همهٔ** مسیرهای Gemini به آن آدرس (مثلاً ورکر کلودفلر `https://sadeghiai.uname1370.workers.dev`) می‌روند: چت/مدل‌ها در `ai_brain.py` (`_effective_base_url` — مقدار env بر سطر DB اولویت دارد، فقط برای پروایدر gemini) و تست‌های سلامت/ویژن در `gemini_proxy_manager.py` (`_gemini_native_base`). اگر خالی باشد، پیش‌فرض `generativelanguage.googleapis.com` است. اعتبارسنجی Base URL در پنل (`panel/modules/ai.py:_valid_base_url` — فقط http/https با هوست معتبر).
- فایل‌های جدید استقرار: `deploy/cloudflare-gemini-worker.js` (کد+مستند ورکر)، `deploy/nginx-giso.conf` (پروکسی ۵۰۰۱، gzip/brotli، HTTP/2، کش ۳۰ روزه static، HSTS، آماده certbot)، `deploy/UBUNTU_SETUP.md` (راهنمای ۷ گامی Ubuntu 24.04 + انتقال `giso/data` + چک‌لیست و عیب‌یابی).

**حالت «⚡ پروکسی فوری» (۱۴۰۵-۰۶-۱۱):** حالت اتصال جدید `worker` در `gemini_proxy_manager.py` (`MODE_WORKER` + `get/set_worker_base_url` با پیش‌فرض `https://sadeghiai.uname1370.workers.dev`): بدون نیاز به پروکسی، همهٔ مسیرهای Gemini (چت، تست، سلامت) خودکار به ورکر کلودفلر می‌روند و کاربر فقط API Key وارد می‌کند. اولویت آدرس: `GEMINI_BASE_URL` (env) ← حالت فوری (DB) ← گوگل. دکمهٔ «⚡ فوری — ورکر کلودفلر (بدون پروکسی)» در منوی «🔄 تغییر حالت اتصال» ربات اضافه شد و «📊 وضعیت پروکسی» در این حالت آدرس ورکر را نشان می‌دهد. `get_active_proxy` در حالت فوری `None` برمی‌گرداند (بدون پروکسی).

**بهینه‌سازی سرعت مدیریت پروکسی (۱۴۰۵-۰۶-۱۱):** در `gemini_proxy_manager.py`: تست اتصال و تشخیص کشور **هم‌زمان** اجرا می‌شوند (قبلاً پشت‌سرهم)؛ تایم‌اوت تست اتصال ۵→۴ ثانیه و تست Vision ۱۲→۵ ثانیه؛ لیست پروکسی‌های سالم **به ترتیب سریع‌ترین** ذخیره می‌شود تا همان اولین/سریع‌ترین پروکسی سالم بلافاصله فعال شود. دریافت از منبع همان سقف ۱۰ تایی (`MAX_FETCH`) و تست‌ها کاملاً موازی‌اند (`asyncio.gather` + Semaphore(10)) — بدترین حالت هر موج از ~۲۲s به ~۹s کاهش یافت.

## §15. اجرای ۸ مورد `img2/help2.md` (۱۴۰۵-۰۶-۱۱)

| # | خواسته | اجرا | فایل(ها) |
|---|--------|------|----------|
| 22 | فونت فارسی وزیرمتن در سایت خراب | فونت‌های محلی سالم‌اند (`static/fonts/Vazirmatn-*.woff2`، ۱۳۲۳ گلیف)؛ لینک async فونت Google به‌عنوان **fallback** بالای `vazirmatn.css?v=2` در هر سه layout اضافه شد — محلی برنده است و Google فقط وقتی محلی نیاید | `templates/base.html`، `panel/templates/layout.html`، `panel_user/templates/user_layout.html` |
| 1 | دکمهٔ «ورود» هدر سایت حاشیه/کادر زشت دارد | کلاس اختصاصی `giso-header-login` + قاعدهٔ style.css (بدون پس‌زمینه/حاشیه/سایه، رنگ ارثی، هاور ملایم)؛ علت اصلی override تم در `themes.css` بود که دست‌نخورده ماند | `templates/base.html`، `static/css/style.css` |
| 18 | اعلان بله بدون «موضوع» | خط «🔖 موضوع:» **همیشه** ارسال می‌شود؛ source_type ناشناخته → «اعلان سیستم» (قبلاً بی‌صدا حذف می‌شد) | `panel/modules/notifications.py` |
| 13 | سیاست رمز عبور: فقط حداقل ۴ کاراکتر + نمایش رمز | حداقل طول ۸→۴ بدون شرط پیچیدگی + پیام فارسی؛ چک‌باکس «نمایش رمز فعلی/جدید» در فرم پروفایل کاربر | `app.py` (`dashboard_password_change`)، `panel_user/templates/user_modules/profile.html`، تست `test_phase6_profile_security.py` به‌روزرسانی شد |
| 7 | سه کارت فوتر سایت کار نمی‌کنند | بررسی شد: هر سه از قبل سالم‌اند — «گفتگو با مشاور»→ویجت (`ai_widget.js:236`)، «ورود به ربات بله»→`{{_bale_url}}`، «نصب اپلیکیشن»→`pwa_install.js` با fallback. کد تغییر نکرد | — |
| 6 | چت مشاور: دکمهٔ تاریخچه/پاک‌کردن + دکمهٔ ارسال بزرگ | تاریخچه (`?history=1`) و پاک‌کردن (`action=clear_thread`) از قبل پیاده بودند؛ فقط دکمهٔ ارسال کوچک شد (padding/min-height/font) | `templates/dashboard_consultant_chat.html` |
| 9 | دستیار فوق‌العادهٔ پنل مثل تصویر ۲۱ (دو ستونه) | بازچینش کامل: گرید `250px + chat`، کارت کناری `.sassist-side` با چیپ‌های پیشنهادی **فعال** (قبلاً بدون هندلر/مرده بودند) + JS delegation؛ در ۸۲۰px به تک‌ستونه تبدیل می‌شود | `panel/templates/modules/super_assistant.html` |
| 11 | اعتبار AI: حذف «اصلاح اعتبار عددی»؛ کسر از نقدی یا مصرفی به انتخاب سوپرادمین؛ خط نرخ/مصرف/مانده در ویجت | ستون `deduct_scope` در `giso_ai_credit_accounts` (+ALTER با try/except)؛ `get/set_deduct_scope`؛ `reserve/refund` از حوزهٔ فعال کاربر کسر/برمی‌گردانند (پیام فارسی «اعتبار نقدی/مصرفی کافی نیست»)؛ جدول پنل: «اصلاح اعتبار» **حذف شد**، مانده=حوزهٔ فعال، انتخاب «کسر از» با route جدید `panel.ai_credit_scope`؛ پاسخ ویجت `ai_credit` می‌گیرد و خط کوچک «نرخ هر پیام • مصرف شما • مانده» فقط وقتی کسر فعال است نمایش می‌دهد | `ai_credits.py`، `panel/modules/ai.py`، `panel/routes.py`، `panel/templates/modules/ai.html`، `app.py` (`ai_widget_chat`)، `static/js/ai_widget.js` |

**تغییرات رفتاری §15:**
- فرم «اصلاح اعتبار عددی» از پنل AI حذف شد (route قدیمی `ai/credits/adjust` و `admin_adjust_credit` برای سازگاری باقی‌ماندند ولی UI ندارند).
- `reserve_ai_credit` به حوزهٔ پیش‌فرض `spend` وفادار است؛ کاربران بدون ردیف حساب، مصرفی کسر می‌شوند (بدون تغییر رفتار قبلی).
- تست `test_phase6_profile_security` با سیاست جدید (حداقل ۴) هم‌راستا شد؛ suite کامل: ۴۶۸ پاس / ۶۲ فیل = دقیقاً baseline.

## §16. راستی‌آزمایی و بهینه‌سازی (۱۴۰۵-۰۶-۱۱)

- **تست همهٔ مسیرها:** ۱۲۵ مسیر GET سایت در سه سطح (مهمان/کاربر/سوپرادمین) → صفر خطای ۵۰۰؛ ۵۰ مسیر `/admin` با نشست تأییدشده → ۳۱×۲۰۰ و بقیه ۳۰۲/۴۰۴ مشروع (رسید/فایل بکاپ ناموجود).
- **باگ قدیمی رفع شد:** `/admin/shop/stats` خطای ۵۰۰ می‌داد چون `admin_shop_stats` مثل بقیهٔ مسیرهای shop، `ensure_shop_template_paths` را صدا نمی‌زد (`giso/shop/panel/admin.py`).
- **بهینه‌سازی تصاویر:** `shop-ai-android.png` (۱.۶MB) → `shop-ai-android.webp` (۷۶KB) با به‌روزرسانی ارجاع‌ها در `shop.html`/`shop_layout.html`؛ `catalog/pedicure-henna-cedar.png` ۵۰۷KB → ۹۶KB (کوانتایز درجا؛ نام فایل حفظ شد چون seed/DB به آن اشاره دارد). مجموع تصاویر static: ۳.۶MB → ۱.۶MB. همهٔ `<img>`ها `alt` دارند (SEO ✓) و hero صفحهٔ اصلی `<picture>` با webp دارد.
- **وزن صفحات سالم است:** gzip فعال (۳–۸KB)، رندر ۱۱۰–۲۴۰ms. پیشنهادهای باقی‌مانده: ادغام/مینیفای ۱۱–۱۳ فایل CSS هر صفحه؛ زیرمجموعه‌کردن `fa-solid-900.woff2` (۱۵۶KB) به آیکون‌های مصرفی؛ brotli+HTTP/2 در nginx (طبق `deploy/UBUNTU_SETUP.md`).
- **ممیزی دستیار سوپرادمین:** معماری سالم است — گیت نقش (`resolve_actor_role` فقط super)، پارسر قطعی فارسی (عدد فارسی ✓)، ۹ گزارش + ۳ گزارش بازرس، هر تغییر داده = پیش‌نمایش + pending + کد تأیید بله + undo، چت آزاد با system-prompt اختصاصی super. تست زنده: گزارش ✓، pending با پیش‌نمایش ✓، رد دسترسی کاربر عادی ✓.

## §17. بهینه‌سازی وزن صفحات (۱۴۰۵-۰۶-۱۲)

| مورد | قبل | بعد |
|---|---|---|
| ۴ عکس آنالیز/نمونه (analysis_hair/skin, sample_hair/skin) | JPEG ۱۳۲–۱۹۰KB | **WebP ۷۷–۸۵KB** (زیر سقف ۹۰KB) |
| CLS کارت‌های آنالیز | بدون width/height | `width="768" height="1376"` روی همهٔ imgها (+`loading="lazy"` در hair_sale) |
| `fa-solid-900.woff2` | ۱۵۶KB (۱۹۵۵ کلاس) | **۱۶KB** — pyftsubset فقط ۱۴۹ کدپوینت مصرفی |
| `fontawesome.min.css` | ۷۲KB | **۱۳KB** — فقط قواعد پایه + ۱۵۹ کلاس مصرفی |
| `Vazirmatn-{Regular,Bold}.woff2` | ۷۷KB/فایل (۱۳۲۳ گلیف) | **۳۶KB/فایل** (۶۶۷ گلیف فارسی+لاتین+علائم) |
| ۱۷ فایل CSS مینیفای (style, themes, marketplace, panel, panel_user, …) | ~۴۴۰KB | **~۳۷۷KB** (رشته‌ها/data-URIها دست‌نخورده؛ تست سلامت بریس/رشته) |

- کش‌شکنی: `vazirmatn.css?v=4` و `fontawesome.min.css?v=6.6.0-2` در هر سه layout.
- **تنظیم «🌐 آدرس سایت» برای لینک‌های موقت به‌روزرسانی (۱۴۰۵-۰۶-۱۲):** منبع آدرس لینک یک‌بارمصرف ۱۰ دقیقه‌ای قبلاً env/پیش‌فرض سخت بود؛ حالا در منوی ربات → مدیریت سایت → 🚧 به‌روزرسانی (هر دو سایت اصلی و گیسو) دکمهٔ « آدرس سایت» اضافه شد: ادمین اصلی آدرس می‌فرستد (اعتبارسنجی http/https، بدون فاصله) و در `giso_config` با کلیدهای `site_base_url` / `main_site_base_url` ذخیره می‌شود؛ `_maint_base_url(scope)` اول این تنظیم، بعد env، بعد پیش‌فرض را برمی‌گرداند و بلوک ساخت لینک از آن استفاده می‌کند. (تغییر کوچک در `bot_edu/handlers.py` با اجازهٔ صریح کاربر برای همین بخش.) تست: `test_site_base_url.py`.
- **اعتبار مصرفی اولیهٔ رایگان + دو کارت اعتبار در هدر (۱۴۰۵-۰۶-۱۲):** در پنل سوپرادمین → مالی → «تنظیمات مالی، کارت و فاکتور» ورودی جدید «اعتبار مصرفی اولیهٔ کاربران جدید (تومان)» (کلید `wallet_initial_spend_credit`؛ ۰ = غیرفعال). تابع `wallet_core.grant_initial_spend_credit` یک‌بار و ایدمپوتنت (کلید یکتای `initial_spend_<uid>` در `wallet_transactions`) اعتبار «مصرفی» رایگان به هر کاربر هنگام اولین ورود به پنل کاربر می‌دهد؛ قابل تسویه نیست. هدر پنل کاربر حالا دو کارت جدا دارد: 💰 نقدی و 🌸 مصرفی (`user_topbar.html` + استایل کارت‌های جدید در `panel_user.css`). تست: `test_initial_spend_credit.py`.
- **بستهٔ درخواست‌های پنل کاربران/اعتبار (۱۴۰-۰۶-۲):** ۱) رمز کاربران: حداقل ۴ کاراکتر بدون پیچیدگی (سوپرادمین آزاد) + دکمهٔ « نمایش رمز» در مدیریت کاربران (جدول `giso_super_visible_pass` فقط آخرین رمز ست‌شده توسط سوپرادمین را نگه می‌دارد؛ با تغییر رمز توسط خود کاربر پاک می‌شود). ۲) سیاست اعتبار: select «کسر شود از: اعتبار مصرفی/نقدی» کنار هزینهٔ هر درخواست (تنظیم `ai_user_credit_scope`؛ fallback سراسری `get_deduct_scope`) + چیدمان flex بدون هم‌پوشانی دکمهٔ ذخیره. ۳) مبالغ: جداکنندهٔ هزارگان **فارسی «٬»** (money.py + ۳۲ قالب با فیلتر `fa_number` + ۴ فرمت‌کنندهٔ JS با `fa-IR`) — به درخواست کاربر: جداکننده باشد ولی هرگز شبیه نقطهٔ اعشار نشود؛ `fa_digits` فقط برای تلفن/تاریخ/شناسه بدون جداکننده؛ فیلترهای Jinja رسماً ثبت شدند. ۴) ورودی‌های تلفن: maxlength=11 در ۹ فرم.
- **ارتقای دستیار هوشمند سوپرادمین (۱۴۰-۰۶-۲، مرحله ۴ کاربر):** پرامپت نقش سوپرادمین (`DEFAULT_SUPER_CAPABILITIES`) تقویت شد: تحلیل عددی/ساختاریافته، ممنوعیت جواب ساختگی («دادهٔ زنده ندارم» صریح)، خطایابی مبتنی بر لاگ واقعی، اجازهٔ هر اقدام اجرایی با تأیید دومرحله‌ای. مهاجرت خودکار: سرورهایی که متن قدیمی دست‌نخورده در DB دارند با `init_ai_runtime_tables` ارتقا می‌یابند (متن سفارشی دست‌نخورده می‌ماند). چیدمان واکنش‌گرای دستورهای پرکاربرد grid دوستونه شد. تست: `test_super_capabilities_upgraded_with_migration`.
- **رفع باگ ۵۰۰ در افزودن پروایدر AI از پنل (۱۴۰۵-۰۶-۱۲):** در `giso/panel/modules/ai.py` تابع کمکی `_valid_base_url` وسط بدنهٔ `handle_provider_add` تعریف شده بود (باگ تورفتگی) → بقیهٔ منطق افزودن پروایدر unreachable و تابع `None` برمی‌گرداند → `POST /admin/ai/provider/add` همیشه ۵۰۰ می‌شد. تابع کمکی به سطح ماژول منتقل شد؛ تست رگرسیون `test_superadmin_can_add_ai_provider_from_web` اضافه شد. مسیر فعال‌سازی Gemini از پنل: `/admin/ai` → فرم «افزودن پروایدر» (نام، kind=openai، API Key، Base URL پیش‌فرض `https://generativelanguage.googleapis.com/v1beta/openai`، مدل) → سپس `set_active_provider` + روشن‌کردن چت.
- **یکدست‌سازی فونت فارسی (۱۴۰۵-۰۶-۱۲):** لینک async گوگل‌فونت از هر سه layout **حذف** شد — دو منبع فونت (محلی + گوگل) روی شبکهٔ ناپایدار باعث می‌شد بخشی از متن با وزیرمتن و بخشی با fallback رندر شود (همان «خانه» و تیترها در اسکرین‌شات). حالا **تک‌منبع**: فقط `static/fonts/Vazirmatn-*.woff2` via `vazirmatn.css?v=5`. دو قاعدهٔ تزئینی که `Georgia` را **قبل** از وزیرمتن می‌گذاشتند (`.home-path-number` در home_original.css و `.home-hero-signature strong` در theme_experiences.css) به وزیرمتن-اول تغییر کردند تا ارقام/متن فارسی یکدست شوند.
- **بازگشت به اصل (۱۴۰۵-۰۶-۱۲، به درخواست کاربر):** فایل‌های CSS و فونت‌ها (Vazirmatn + FA) به نسخهٔ اصلی پیش از فشرده‌سازی برگشتند — بررسی tinycss2 نشان داد مینیفای دست‌ساز ساختار/مقادیر را نشکسته بود، ولی برای حذف هر ریسک بصری (فونت/رنگ/استایل منو) نسخهٔ اصلی restore شد. بهینه‌سازی‌های بی‌ریسکِ §17 (تصاویر WebP آنالیز + width/height برای رفع CLS) حفظ شده‌اند.
- **هشدار برای توسعه:** اگر آیکون FA جدیدی به قالب اضافه شد که در لیست فعلی نیست، باید woff2/css دوباره subset شود (کدپوینت‌های فعلی از خود CSS قابل استخراج است؛ grep `fa-` در قالب‌ها).
- دو تست با فرمت قدیمی CSS نوشته شده بودند و با نسخهٔ مینیفای (استاندارد جدید) هم‌راستا شدند: `test_marketplace_buyer_photo_ui` (assertions بدون وابستگی به فاصله) و `test_center_detail_and_glass_nav` (نشانگر کامنتی → خود قاعدهٔ `.giso-navbar`).
- suite کامل: **۴۶۸ پاس / ۶۲ فیل = دقیقاً baseline** (صفر رگرسیون).

## §18. پرداخت آنی کیف پول با بازوی بله (۱۴۰۵-۰۶-۱۲)

بر پایهٔ مستندات رسمی docs.bale.ai (بخش پرداخت — فقط **کیف پول بله**؛ کارت‌به‌کارت حذف شده). جریان کامل:
`سایت: فاکتور pending + deep-link` → `ربات: sendInvoice (IRR)` → `pre_checkout_query (تأیید زیر ۱۰ ثانیه)` → `SuccessfulPayment` → `واریز idempotent به wallet_transactions (scope=cash, idempotency=balepay:<id>)` + اعلان کاربر.

| فایل | نقش |
|---|---|
| `giso/wallet_balepay.py` (جدید) | منطق مالی: تبدیل تومان↔ریال، جدول `giso_balepay_invoices`، payload `topup:<uid>:<inv_id>`، ساخت فاکتور/deep-link، `validate_pre_checkout`، `credit_payment` (idempotent)، `inquire_transaction`، `follow_pending` |
| `giso/bot_balepay.py` (جدید) | هندلرهای نازک PTB: `pay_<token>` deep-link، pre-checkout، SuccessfulPayment |
| `giso/bot.py` | فقط ۹ خط: import `PreCheckoutQueryHandler`، ثبت ۲ هندلر، deep-link در `start` (۷۵۱۷ ≤ سقف ۷۵۷۷) |
| `giso/config.py` | `BALE_PROVIDER_TOKEN` از env؛ پیش‌فرض = توکن تست رسمی `WALLET-TEST-1111111111111111` (هرگز لاگ نشود) |
| `giso/wallet_core.py` | تنظیم مالی جدید `wallet_topup_method`: `receipt`/`bale`/`both` (پیش‌فرض both) |
| پنل ادمین | سلکت «روش‌های افزایش موجودی» در کارت تنظیمات مالی (`panel.wallet?tab=settings`) |
| پنل کاربر | کارت «⚡ پرداخت آنی با بله» + «🔄 پیگیری پرداخت بله» در تب افزایش موجودی؛ فرم رسید فقط در روش receipt/both |

**نکات عملیاتی:**
- واحد API بله **ریال** است؛ همهٔ تبدیل‌ها فقط در `toman_to_rial/rial_to_toman`.
- پول آنی به **کیف پول بلهٔ صاحب بازو** می‌رود؛ برداشت به بانک از خود بله.
- ربات باید زنده باشد (مهلت ۱۰ ثانیه pre-checkout)؛ فاکتورهای بلاتکلیف با `inquireTransaction` و دکمهٔ پیگیری بسته می‌شوند.
- شناسهٔ ربات برای deep-link از config کلید `bale_bot_handle` (پیش‌فرض `1191639507`).
- تست‌ها: `giso/tests/test_wallet_balepay.py` (۶ تست — چرخهٔ کامل با mock، بدون شبکه). suite: **۴۷۴ پاس / ۶۲ فیل** (baseline + ۶ تست جدید، صفر رگرسیون).

**باز (از §13 قبل):** بکاپ خودکار روزانه؛ تست کامل خرید در محیط واقعی؛ بازبینی امنیت production (HTTPS-only، چرخش توکن‌ها).

## §19. وضعیت فعلی پروژه — داشبورد تغییرات (۱۴۰۵-۰۶-۱۲)

**سلامت مخزن:** اسنپ‌شات ۱۴۰۵-۰۶-۱۲ این بود: `bot.py` ۷۵۱۷، `app.py` ۲۱۹۵. <!-- updated 2026-09-06 --> وضعیت جاری 2026-09-06 روی شاخهٔ `arena/01a07668-giso2`: `bot.py` **۷۳۷۰**≤۷۵۷۷ (پس از پاک‌سازی ایمپورت §24)، `app.py` **۲۲۹۹**≤۲۳۰۰، `wallet.py` ۶۹۹≤۷۲۳؛ `bot_edu/` و `web/` دست‌نخورده. **کیت تست: ۵۵۶ پاس / ۳۹ فیل** (فیل‌ها از پیش موجود؛ §24).

**خلاصهٔ تحویل‌ها (جزئیات هرکدام در بخش خودش):**
| بخش | محتوا |
|---|---|
| §13 | تحویل شهریور: اعتبار AI کیف‌پولی، اعلان‌ها، Lighthouse |
| §14 | ۱۹ مورد `img/help.md` + self-host فونت/FA + gzip (`giso/perf.py`) + استقرار لینوکس (`deploy/`) + حالت «⚡ پروکسی فوری» ورکر کلودفلر + سرعت پروکسی |
| §15 | ۸ مورد `img2/help2.md`: فونت fallback، دکمه ورود، موضوع اعلان بله، رمز حداقل ۴+نمایش، چت مشاور، دستیار دو ستونه، **اعتبار AI با حوزهٔ نقدی/مصرفی** (`deduct_scope`) |
| §16 | تست ۱۲۵ مسیر سایت + ۵۰ مسیر پنل (صفر ۵۰۰)؛ رفع باگ `/admin/shop/stats`؛ تصاویر ۳.۶→۱.۶MB؛ ممیزی دستیار سوپرادمین |
| §17 | WebP عکس‌های آنالیز + width/height (رفع CLS)؛ FA subset ۱۵۶→۱۶KB و css ۷۲→۱۳KB؛ وزیرمتن ۷۷→۳۶KB؛ مینیفای ۱۷ فایل CSS |
| §18 | **پرداخت آنی بله**: `wallet_balepay.py` + `bot_balepay.py` + `BALE_PROVIDER_TOKEN` + تنظیم روش شارژ + دکمه پرداخت/پیگیری کاربر |

**ماژول‌های جدید این دوره (هر کد در خانهٔ خودش):** `giso/perf.py`، `giso/wallet_balepay.py`، `giso/bot_balepay.py`، `deploy/cloudflare-gemini-worker.js`، `deploy/nginx-giso.conf`، `deploy/UBUNTU_SETUP.md`، `giso/tests/test_wallet_balepay.py`.

**کلیدهای env برای استقرار:** `SECRET_KEY` (الزامی)، `BOT_TOKEN`، `GEMINI_BASE_URL` (اختیاری — ورکر)، `BALE_PROVIDER_TOKEN` (پرداخت بله؛ پیش‌فرض توکن تست). همه در `/etc/giso/web.env`.

**چک‌لیست استقرار سریع:** بکاپ `giso/data` → rsync کد → `pip install -r requirements.txt` → env → ساخت `giso/data/giso-restart.flag` → بررسی `/` و `/admin`.

*پایان راهنما — این سند باید بعد از هر تغییر معماری به‌روزرسانی شود (قانون: کد = حقیقت).*

## §20. معماری دوانجینه دیتابیس (SQLite و PostgreSQL) و راهنمای استقرار (۱۴۰۵-۰۶-۱۳)

> مرجع فنی: `giso/db_engine.py` (مرز دوانجینه) · `giso/db_pg_tools.py` (ابزار مهاجرت) ·
> `deploy/pg_backup.sh` (بکاپ) · گام ۸ در `deploy/UBUNTU_SETUP.md` (نصب سرور).
> وضعیت تست: مهاجرت به‌صورت end-to-end روی PostgreSQL 16.2 واقعی اجرا و راستی‌آزمایی شد؛
> کیت کامل پروژه ۴۸۰ پاس / ۶۰ شکست (عیناً baseline، صفر رگرسیون).

### ۲۰-۱) منطق معماری — چرا این‌طور است؟

**یک کلید، دو موتور.** تمام اتصالات دیتابیس پروژه از چهار گلوگاه عبور می‌کنند:

| گلوگاه | فایل | مصرف‌کننده |
|---|---|---|
| `get_giso_db_conn()` | `giso/db_core.py` | ماژول‌های سایت (کیف پول، فروشگاه، تحلیل، زیبایی…) |
| `get_bot_db_conn()` | `giso/db_core.py` | سمت سایت برای جدول‌های `giso_*` داخل bot.db |
| `SQLALCHEMY_DATABASE_URI` + `SQLALCHEMY_BINDS['bot']` | `giso/config.py` | مدل‌های ORM (User و…) |
| `init_db()` / `get_conn()` | `bot_edu/db.py` | کل ربات آموزش |

هر چهار نقطه یک متغیر محیطی را می‌خوانند: `GISO_DB_ENGINE`.
- **بدون env (پیش‌فرض):** همه‌چیز مثل روز اول روی SQLite — هیچ رفتار، سرعت یا ریسکی عوض نمی‌شود.
- **`GISO_DB_ENGINE=postgres`:** همان API با آداپتور `PgConn` روی PostgreSQL. آداپتور
  `?`→`%s`، `PRAGMA table_info`→`information_schema`، `lastrowid`→`RETURNING id`،
  `executescript`، و توابع سازگاری `datetime('now','localtime')` را شبیه‌سازی می‌کند،
  پس **رشته‌های SQL در کل کدبیس دوانجینه باقی مانده‌اند** (بدون بازنویسی ۳۶۸ نقطهٔ مصرف).

**چرا دو دیتابیس مجزا (`giso_db` و `bot_edu_db`) روی یک سرویس؟** محافظت سه‌لایه:
1. **دیتابیس جدا** — در PG حتی JOIN بین دو دیتابیس ممکن نیست؛ قاطی‌شدن رکوردها ساختاراً غیرممکن است.
2. **کلید جدا** — `giso_app` فقط مالک `giso_db` و `bot_app` فقط مالک `bot_edu_db` است؛
   کوئری اشتباه هم از سمت خودِ PG رد می‌شود (permission denied)، نه فقط انضباط کدنویسی.
3. **گلوگاه واحد در کد** — هیچ ماژولی مستقیم وصل نمی‌شود؛ DSN درست در همان چهار نقطه تزریق می‌شود.

نتیجه: تداخل صفر، بکاپ/بازگردانی مستقل هر دامنه، و امکان انتقال ربات به سرور جدا در آینده
فقط با تغییر مقدار `BOT_EDU_PG_DSN` (صفر خط کد). سرعت زیر بار نوشتن همزمان و امنیت
(رمز/سطح دسترسی/فقط localhost) مزیت مستقیم PG نسبت به فایل SQLite است.

**Fallback (بازگشت اضطراری به SQLite):** فایل‌های SQLite هیچ‌وقت حذف نمی‌شوند و در حالت
PG هم دست‌نخورده می‌مانند. اگر PG دچار مشکل شد: حذف یک خط `GISO_DB_ENGINE` از
`/etc/giso/web.env` + ری‌استارت سرویس‌ها ⇒ سایت و ربات فوراً روی SQLite برمی‌گردند.
(داده‌های نوشته‌شده در بازهٔ PG با بکاپ `pg_dump` قابل بازیابی/انتقال‌اند.)
تعمداً **failover نوشتاری خودکار نداریم** — دو نویسندهٔ هم‌زمان روی پول/سفارش ریسک
split-brain دارد؛ تصمیم مصوب: توقف موقت عملیات + بازیابی سریع.

### ۲۰-۲) ابزار مهاجرت `giso/db_pg_tools.py` — ریزبه‌ریز

خط لولهٔ هر دیتابیس (کاملاً idempotent نیست — برای اجرای مجدد، دیتابیس مقصد را drop/create کنید):

1. **ساخت schema:** خواندن DDL از `sqlite_master` و ترجمه با `translate_ddl_sqlite_to_pg`:
   `INTEGER PRIMARY KEY [AUTOINCREMENT]` → `BIGINT … GENERATED BY DEFAULT AS IDENTITY`،
   همهٔ `INTEGER` → `BIGINT` (SQLite هشت‌بایتی است؛ شناسه‌های بزرگ بله در INTEGER چهاربایتی
   سرریز می‌شدند)، `BLOB`→`BYTEA`، `REAL`→`DOUBLE PRECISION`. اول توابع سازگاری `datetime` نصب می‌شوند.
2. **حذف موقت FK از CREATE:** چرخهٔ FK (مثل `hair_listings ↔ buyer_offers`) با هیچ ترتیبی
   ساختنی نیست؛ FKها استخراج و بعداً با `ALTER TABLE … ADD CONSTRAINT` برگردانده می‌شوند.
3. **کپی ۱۰۰٪ داده:** دسته‌های ۵۰۰تایی با درج شناسهٔ صریح + هم‌ترازی نوع
   (۰/۱ → `boolean`، عدد → `text` در ستون‌های متنی). هنگام کپی، تریگرهای FK با
   `session_replication_role=replica` خاموش می‌شوند (نیاز به کاربر ادمین — به همین دلیل
   مهاجرت روی سرور با `sudo -u postgres` اجرا می‌شود).
4. **بازگردانی FK با اعتبارسنجی کل داده:** اگر دادهٔ قدیمی ردیف یتیم داشته باشد
   (SQLite هرگز FK را چک نمی‌کرد)، **هیچ داده‌ای حذف نمی‌شود**؛ آن FK به‌صورت `NOT VALID`
   ساخته می‌شود: روی نوشتن جدید فعال است، رکوردهای قدیمی دست‌نخورده می‌مانند و در گزارش با 🟡 فهرست می‌شوند.
5. **تنظیم دنباله‌ها:** `setval` روی همهٔ ستون‌های IDENTITY تا شناسهٔ جدید از `max+1` ادامه یابد.
6. **راستی‌آزمایی:** شمارش تک‌تک جدول‌ها در دو طرف؛ هر اختلاف ⇒ خروجی قرمز و کد بازگشت ۱.

خروجی اجرای واقعی (تست e2e این فاز):
`giso_db` = ۸۸ جدول / ۵۷ FK / ۳۹۷ رکورد 🟢 · `bot_edu_db` = ۵۲ جدول / ۷۰ رکورد 🟢 (یک FK با 🟡 NOT VALID).

**نکتهٔ ایمنی در `giso/config.py`:** اگر `GISO_DB_ENGINE=postgres` باشد ولی DSN فرمت URL
نداشته باشد، برنامه **با خطای صریح متوقف می‌شود** — هرگز بی‌صدا به SQLite برنمی‌گردد
(بازگشت بی‌صدا یعنی نوشتن روی دیتابیس اشتباه در پروداکشن).

### ۲۰-۳) اجرای عملی روی سرور لینوکس (Production)

خلاصهٔ گام ۸ در `deploy/UBUNTU_SETUP.md` (جزئیات کامل همان‌جا):
1. `sudo apt install postgresql` — سرویس systemd خودش بالا می‌ماند؛ فقط localhost، هیچ پورتی در فایروال باز نشود.
2. ساخت دو دیتابیس و سه کاربر با رمز جدا (دستور SQL کامل در گام ۸-۱).
3. افزودن به `/etc/giso/web.env`:
   `GISO_DB_ENGINE=postgres` + `GISO_PG_DSN=postgresql://giso_app:…@127.0.0.1:5432/giso_db` +
   `BOT_EDU_PG_DSN=postgresql://bot_app:…@127.0.0.1:5432/bot_edu_db`
4. مهاجرت یک‌باره با کاربر ادمین: `sudo -u postgres env … python -m giso.db_pg_tools --migrate-all`
   تا خروجی 🟢 راستی‌آزمایی برای هر دو دیتابیس.
5. بکاپ ساعتی: نصب `deploy/pg_backup.sh` در `/usr/local/bin` + cron (گام ۸-۴) —
   `pg_dump -Fc` هر دو دیتابیس، نگه‌داری ۳۰ روز.
6. `sudo systemctl restart giso-web giso-bot` و چک‌لیست گام ۷.

### ۲۰-۴) توسعه و تست روی کامپیوتر شخصی (VSCode / Local)

- **حالت پیش‌فرض: هیچ کاری لازم نیست.** بدون `GISO_DB_ENGINE` پروژه روی SQLite بالا می‌آید؛
  کیت تست هم کامل با SQLite می‌دود (`.env` لوکال را با PG پر نکنید مگر برای تست PG).
- برای تست PG در VSCode:
  1. نصب PostgreSQL ۱۶ از postgresql.org (ویندوز) یا `docker run -d -p 5432:5432 -e POSTGRES_PASSWORD=test postgres:16`.
  2. ساخت دیتابیس/کاربر (همان SQL گام ۸-۱).
  3. در `.env` لوکال: سه متغیر بالا با `localhost`.
  4. افزونهٔ **SQLTools** + درایور PostgreSQL در VSCode ⇒ مشاهدهٔ جدول‌ها و کوئری زنده.
  5. اجرای مهاجرت: `python -m giso.db_pg_tools --migrate-all` و مشاهدهٔ 🟢.
- قانون تیم: **کامیت‌ها هیچ‌وقت با env فعالِ PG انجام نشوند** — مسیر پیش‌فرض (SQLite) مسیر رسمی تست است.

### ۲۰-۵) ایدیوم‌های SQL پرتابل (قانون جدید توسعه)

هر SQL جدید باید روی هر دو موتور کار کند:
- مجاز: `ON CONFLICT (…) DO NOTHING / DO UPDATE SET col=excluded.col` (SQLite≥3.24 و PG) · `datetime('now','localtime')` (روی PG تابع سازگاری دارد).
- ممنوع: `INSERT OR IGNORE` · `INSERT OR REPLACE` · `AUTOINCREMENT` در کد جدید (مترجم DDL برای schemaهای قدیمی هست، ولی کد جدید تمیز نوشته شود).
- ۲۱ نقطهٔ `INSERT OR REPLACE` و ۲۲ نقطهٔ `INSERT OR IGNORE` قدیمی در فاز DB-۱ تا DB-۳ به الگوی پرتابل تبدیل شدند (کامیت‌های `05bd41c`، `667fc5d`، `4f81fe9`).

## §21. اجرای سناریوی GISO_MASTER_AGENT_GUIDE (۱۴۰۵-۰۶-۱۴)

هفت مرحلهٔ سناریوی مستر بدون شکستن ساختار و با کیت کامل پس از هر مرحله (۴۸۵ پاس / ۶۰ Known Issue ثابت) اجرا شد.

### جدول قبل / بعد

| بخش | قبل | بعد |
|---|---|---|
| §۱۰ مرکز پیام | ماژول نبود (فقط broadcasts.py قدیمی sqlite) | ماژول مستقل `giso/broadcasts_center/` با صف پس‌زمینه، ۵ گروه مخاطب، ۲ کانال (سایت+بله)، زمان‌بندی، گزارش Delivery و UI پنل |
| §۶ دستیار ادمین | دو ستون | ستون سوم «وضعیت سیستم» (Web/DB/AI/Bale/Queue) رنگی، کش ۲۰ث، رفرش ۳۰ث، timeout ۳ث، ریسپانسیو |
| §۱۵ تست‌ها | ۶۰ شکست بدون سند | `docs/GISO_KNOWN_ISSUES.md` با ۹ دسته و علت/تأثیر/راهکار |
| §۷ منوی کاربر | فهرست تخت | چهار گروه اصلی/خدمات/پشتیبانی/حساب |
| §۹ فوتر | بدون راه‌های ارتباط | ستون «راه‌های ارتباط» (تلفن/واتس‌اپ/اینستاگرام/ایمیل) قابل تنظیم از پنل |
| §۱۱ ویجت | پاسخ‌های بلند | قواعد «حدس نزن»، «حداکثر ۴ خط»، «پیشنهاد مرتبط با صفحه» |
| §۱۳ Production | بدون سند بار | `deploy/LOAD_TEST_REPORT.md` با اعداد واقعی |
| §۱ راهنما | ارجاع به پوشهٔ ناموجود start/ | ارجاع به «تصاویر پیوست کاربر» |

### فایل‌های تغییر یافته در این اجرای سناریو

- جدید: `giso/broadcasts_center/{__init__,core,worker,routes}.py`, `giso/tests/test_broadcasts_center.py`, `giso/panel/templates/modules/broadcasts_center.html`, `GISO_KNOWN_ISSUES.md` (بعداً به `docs/` منتقل شد)، `deploy/LOAD_TEST_REPORT.md`, `GISO_MASTER_AGENT_GUIDE.md` (بعداً به `docs/` منتقل شد)
- ویرایش: `giso/app.py` (ثبت ماژول)، `giso/panel/permissions.py` و `routes.py` (منو+روت health)، `giso/panel/modules/super_assistant.py` (get_system_health)، `giso/panel/templates/modules/super_assistant.html`، `giso/panel_user/{permissions,routes}.py` + `partials/user_sidebar.html`، `giso/panel/modules/settings.py` + قالب تنظیمات، `giso/templates/base.html`، `giso/ai_runtime.py`، دو تست قرارداد منو

### استقرار سرور لینوکس

1. `git pull && sudo systemctl restart giso-web giso-bot`
2. جداول جدید `giso_bc_*` خودکار (idempotent) ساخته می‌شوند؛ برای PG در صورت نیاز `deploy/pg_backup.sh` و مهاجرت موجود است.
3. سلامت: `/admin/super-assistant/health` (کش ۲۰ث) برای health-check خارجی.
4. مرجع کامل استقرار: `deploy/UBUNTU_SETUP.md` + گزارش بار `deploy/LOAD_TEST_REPORT.md`.

## §22. فاز سوپرادمین «دستیار هوشمند» — ۱۲ مرحله (۱۴۰۵-۰۶-۱۴ / 2026-09-05)

برنچ اجرا: `arena/01a06da0-giso2`. اسکیما DB عوض نشد. `bot.py` بازهٔ مانیتورینگ دست‌نخورده ماند (بدون بار اضافه). سئوی خودکار در لحظه اجرا نشد (امکان‌سنجی کم‌ریسک).

### از OTP تا این فاز (خلاصه زنجیره)

| موضوع | نتیجه |
|---|---|
| OTP / step-up ورود پنل ادمین | گارد `_panel_stepup_valid` در `super_assistant.py`؛ کد اقدام اجرایی جدا از OTP ورود، فقط به بلهٔ سوپر |
| پنل کاربر بله (۱۱ مرحله، همین نشست) | KB کیف‌پول/مأموریت/دستیار/پروفایل/پشتیبانی/راهنما + شارژ/تسویه داخل ربات |
| دستیار سوپرادمین سایت | ۱۲ مرحله زیر روی موتور موجود `ai_runtime` |

### ۱۲ مرحله

| # | کار | فایل / خطوط | تست |
|---|---|---|---|
| 1 | چیپ «تیکت‌های باز» فقط `new/reviewing/open`؛ «مشاوره معطل» فقط `new/reviewing/pending/active` | `ai_runtime.py` `_report_tickets` L2729، `_report_consultants` L2750، پلن L~3088 | `test_superadmin_open_tickets_and_pending_consults_filter` |
| 2 | حذف Gemini جعلی؛ AI فعال از `get_active_provider`؛ بج «آنلاین» از health واقعی | `super_assistant.py` `get_system_health` L590؛ HTML `#sassist-online` + `loadHealth` | health بدون ping اضافه (فقط `last_status` کش ۲۰ث) |
| 3 | پرامپت کوتاه سوپر + تزریق ~۱۰ خط آمار زنده قبل از چت آزاد | `ai_runtime_policy.py` `DEFAULT_SUPER_CAPABILITIES` L45؛ `build_super_live_stats_block` L902؛ `chat_with_managed_ai` L1066 | `test_super_capabilities_upgraded_with_migration` (باید «ساختگی» و «دادهٔ زنده» بماند) |
| 4 | `temperature=0.2` + `max_tokens` پویا (۲۸۰/۵۰۰/تا ۹۰۰) | `super_chat_generation_params` L890 | `test_force_refresh_and_generation_params_and_sanitize` |
| 5 | دکمه‌های insight: دیدم/اعمال شد/رد روی API موجود | HTML `data-url-insight` + JS؛ `handle_insight_status_post` L508 | API از قبل: `panel.super_assistant_insight_status` |
| 6 | نمایش `provider / model` زیر حباب دستیار | HTML `.sassist-meta`؛ JSON چت `provider`/`model` | ذخیرهٔ history با meta |
| 7 | مانیتورینگ: برجسته کردن خطاهای ۶۰ دقیقهٔ اخیر بدون job جدید | `monitoring_insights.py` ~L385 | بدون تغییر interval در `bot.py` |
| 8 | ممنوعیت عدد ساختگی + رد ادعای «اجرا شد» بدون pending | `_sanitize_ai_reply` L853 `_FAKE_EXEC_RE`/`_FAKE_STAT_RE` | همان تست sanitize |
| 9 | عبارات همین‌الان/دوباره بگیر/کش رو نادیده/از نو → `force_refresh` | `detect_force_refresh` L317؛ prefix «🔄 گزارش تازه…» | «سلام الان چطوری» = False |
| 10 | گزارش داشبورد عددی: امروز سفارش/تیکت/کاربر/فروش/آنالیز + سلامت AI | `_report_dashboard` L2641 | دستی: «گزارش سریع امروز رو بده» |
| 11 | سئو: فقط امکان‌سنجی (sitemap/robots/schema موجود؛ بازنویسی AI و پینگ GSC اجرا نشد) | `_report_seo_feasibility` L2771؛ action `report_seo` L2467 | «وضعیت سئو و sitemap چیست؟» |
| 12 | همین بند راهنما | `GISO_GUIDE.md` §22، `PROJECT_GUIDE.md` | — |

### تست اجراشده در sandbox (بدون flask_sqlalchemy)

`SECRET_KEY=…` روی مسیر runtime (نه کل `test_ai_runtime.py` به‌خاطر DummyDB.Float): فیلتر تیکت/مشاوره، force_refresh، temp/tokens، sanitize، SEO، داشبورد — **ALL STAGE TESTS OK**.

### استقرار

`git pull` روی `arena/01a06da0-giso2` سپس ری‌استارت وب. جدول جدید لازم نیست.

## §23. صفحهٔ به‌روزرسانی تایمردار + صفحهٔ ورود دوستونه (۱۴۰۵-۰۶-۱۵)

دو کار مستقل در یک کامیت (طبق دستورالعمل `se.md`):

### کار ۱ — صفحهٔ Maintenance با تایمر و عکس سفارشی
- `giso/templates/maintenance.html` — بازنویسی کامل: فونت وزیرمتن محلی، انیمیشن چرخان CSS خالص، نشانگر «در حال به‌روزرسانی»، پیام «سفارش‌ها، کیف پول و حساب شما سر جایشان می‌مانند»، تصویر سفارشی (`images/maintenance_custom.webp` + fallback با `onerror` به `maintenance-default.svg`)، **تایمر بزرگ زیر عکس** با شمارش معکوس فارسی و `location.reload()` در صفر.
- `giso/app.py` — مدت در کلید `giso_maintenance_duration` (گزینه‌های ۰/۵/۱۵/۳۰/۶۰/۱۲۰/۲۴۰ دقیقه؛ نامعتبر=بدون تایمر) و زمان شروع در `giso_maintenance_started_at` — هر دو در جدول `settings` همان bot.db که فلگ نگهداری از آن خوانده می‌شود. ثبتِ شروع فقط هنگام فعال‌بودن حالت و ایدمپوتنت است؛ گذار روشن→خاموش (با کش ۱۰ثانیه‌ای) زمان شروع را پاک می‌کند تا دور بعدی تایمر تازه داشته باشد. گیت اکنون `maintenance_until` را به قالب پاس می‌دهد. **رفتارهای قبلی حفظ شد:** بای‌پس ادمین، عبور استاتیک، مستثنی‌بودن `/login` و `/admin/verify`، HTTP 503.
- `giso/panel/modules/settings.py` — بخش `save_maintenance` در POST پنل سوپر: ذخیرهٔ مدت + آپلود تصویر سفارشی (Pillow verify، ≤5MB/20MP، تبدیل به WebP، جایگزینی اتمیک، بالارفتن `giso_maintenance_image_version`) + حذف تصویر.
- `giso/panel/templates/modules/settings.html` — تب جدید «🚧 به‌روزرسانی و ورود».

### کار ۲ — صفحهٔ ورود دوستونه با لوگوی قابل تنظیم
- `giso/templates/login.html` — بازنویسی کامل: ستون معرفی (لوگو + نام برند + شعار + سه آیتم اعتماد، پس‌زمینه تیره/طلایی) + ستون فرم؛ موبایل تک‌ستونه. دکمهٔ نمایش/پنهان رمز (فقط تغییر `type`؛ رمز لاگ نمی‌شود)، «ادامه در ربات بله» از `site_appearance.bale_url`. CSRF و فیلدها و رفتارهای قبلی (نرخ‌محدودیت، قفل شماره، `minlength=4`) حفظ شد.
- `giso/templates/register.html` — همان پوستهٔ دوستونه؛ **همهٔ فیلدها و منطق فرم دست‌نخورده**.
- لوگوی صفحهٔ ورود: کلید `login_logo_path` در `giso_config` (bot.db) با کش `cached_giso_config`؛ پیش‌فرض = لوگوی برند (`site_brand.logo`). آپلود از پنل سوپر (فقط PNG/WebP، ≤2MB، `uploads/logos/login_logo.<ext>`، جایگزینی اتمیک) + دکمهٔ حذف. `login_logo` از `context_processor` به همهٔ قالب‌ها تزریق می‌شود.
- `giso/static/css/style.css` — `.giso-auth-logo-img`، `.giso-pw-wrap/.giso-pw-toggle`، `.giso-auth-bale` + ریسپانسیو ۷۶۸px.

### تست‌ها
- `giso/tests/test_maintenance_timer_login_logo.py` (جدید، ۷ تست): ۵۰۳/اسپینر/تصویر، تایمر فقط با مدت>۰، عبور استاتیک و ورود حین به‌روزرسانی، گذار روشن→خاموش، مدت نامعتبر، چیدمان دوستونهٔ ورود/ثبت‌نام.
- `test_edu_giso_remote_management.py` — قرارداد متن صفحهٔ به‌روزرسانی به نسخهٔ جدید به‌روزرسانی شد.
- سقف‌ها: `app.py` دقیقاً ۲۳۰۰ خط (مطابق سقف) • `bot_edu/` و `web/` و `giso/bot.py` دست‌نخورده.

## §24. اجرای `1.md` — چهار باگ + ممیزی راهنماها (۱۴۰۵-۰۶-۱۵ / 2026-09-06) <!-- updated 2026-09-06 -->

بخش اول (باگ‌ها) روی شاخهٔ `arena/01a07668-giso2` انجام شد؛ کیت تست پس از هر مرحله **۵۵۶ پاس / ۳۹ فیل** (صفر رگرسیون؛ ۳۹ فیل همه از پیش موجود و در `docs/GISO_KNOWN_ISSUES.md` مستندند).

| # | مورد | اجرا | محل |
|---|------|------|-----|
| 1 🟡 | برش پاسخ ادمین در میانهٔ فرمول مارک‌داون | برش روی نزدیک‌ترین مرز خط (`\n`) در بازهٔ امن + فالبک: اگر در نقطهٔ برش هنوز کد/لینک مارک‌داون باز باشد → ارسال آن تکه به‌صورت متن خام (بدون `parse_mode`) | `giso/bot.py` (~L2587) |
| 2 🟢 | پاسخ‌های بلند ربات گاهی ارسال نمی‌شدند | اتصال `send_long_message` (از پیش موجود در `bot_helpers`) به ۴ نقطه: پاسخ ادمین، پاسخ سوپرادمین در حالت غیر-در انتظار، گزارش پایش `_wt()` (هر سه با `message=` برای حفظ reply) و پاسخ مشاور ادمین→کاربر؛ تابع به کلیدهای کیبورد دست نمی‌زند | `giso/bot.py` + پشتیبانی `message=` در `bot_helpers.send_long_message` |
| 3 🟢 | ۴۳ ایمپورت مرده در سر `bot.py` | حذف ۴۱ ایمپورت خط بالایی + ۲ `import html` محلی؛ ۹ باقی‌مانده همه تعمدی‌اند (۸ نام در بلوک‌های «نگه‌دار — مصرف‌شده توسط تست‌ها» + `import telegram` برای چک وابستگی) | `giso/bot.py` (۷۴۰۸→۷۳۷۰ خط) |
| 4 🟢 | تصاویر هیرو بدون ابعاد/لود تنبل | `width`/`height` (مطابق باکس ثابت CSS) برای ۱۴ تصویر + `loading="lazy"` فقط برای کارت‌های پلن آنالیز و گالری پنل مالک. سه استثنا با دلیل: دو لیت‌باکس جاوااسکریپتی (خطر تغییر نسبت تصویر) و تصویر سفارشی صفحهٔ به‌روزرسانی (فایل هنوز وجود ندارد) | قالب‌های `templates/`، `shop/templates/`، `beauty_centers/templates/` |

**چک‌لیست ممیزی راهنماها (مراحل ۵–۹ همین دستور):**
- جدول مغایرت `GISO_GUIDE.md` در §25 گزارش نهایی آمده است؛ همهٔ اعداد/مسیرهای نادرست بالا (هدر، §1، §2، §5.1، §7.1، §8.1، §8.2، §11.3، §12.1، §19) اصلاح شدند.
- `PROJECT_GUIDE.md` بازبینی و به‌روز شد (بخش‌های پورت/قوانین/ارجاعات).
- قانون نهایی ریشه: فقط `GISO_GUIDE.md` + `PROJECT_GUIDE.md` (+ `README.md`)؛ بقیهٔ سندنگاری‌های ریشه به `docs/` منتقل شدند.
- راهنمای مرجع ربات/پنل (`bot_edu/GUIDE.md`) چون داخل ناحیهٔ قفل `bot_edu/` است دست‌نخورده ماند.
- `1.md` (دستور کار همین نشست، ساختهٔ کارفرما) به‌عنوان استثنا در ریشه ماند؛ سایر ۱۲ سند تاریخی بدون حذف محتوا به `docs/` و `docs/reports/` منتقل شدند (۹ گزارش قدیمی + ۳ راهنمای وضعیت).

---

## §25. سیستم هوش مصنوعی نسخه ۲.۰ — راهنمای کامل (۱۴۰۵-۰۶-۱۸ / 2026-09-09) <!-- updated 2026-09-09 -->

سیستم AI گیسو در سه فاز بازنویسی شد (مأموریت `1.md`): رجیستری مستقل مدل‌ها، کشف پویا + پنل مدیریت، و سلامت مشترک + سقف زمانی. این بخش راهنمای کامل و به زبان ساده است.

**فایل‌های کلیدی سیستم جدید:**

| فایل | نقش |
|---|---|
| `giso/ai_models_registry.py` | رجیستری ۸ پروایدر با مدل‌های پیش‌فرض و متادیتا |
| `giso/ai_config.py` | همهٔ ثابت‌های قابل تنظیم (سقف‌ها، بک‌آف، کولداون، پرچم امنیت) |
| `giso/ai_health.py` | سلامت مشترک سه موتور + طبقه‌بندی خطا |
| `giso/ai_brain.py` | پروایدرها/کلیدها، کشف مدل، موتور سریع، لایه سازگاری |
| `giso/analysis.py` | موتور بینایی (`call_vision_with_fallback`) |
| `giso/ai_runtime.py` | موتور چت (`chat_with_failover`) |

### ۲۵.۱ نقشهٔ استفاده از AI در پروژه (۱۶ نقطه)

| # | بخش پروژه | کجای کد؟ | چه می‌کند؟ | کدام موتور؟ |
|:-:|---|---|---|---|
| ۱ | تحلیل اولیه مو | `analysis.py:_run_initial` | عکس → کارت‌ها و فلگ‌ها | بینایی |
| ۲ | تحلیل اولیه پوست | همان تابع، نوع `skin` | عکس → کارت‌ها و فلگ‌ها | بینایی |
| ۳ | تحلیل نهایی مو/پوست | `analysis_final_override.py:132` | عکس + پاسخ سوالات → امتیاز/مشکلات/روتین | بینایی |
| ۴ | اعتبارسنجی عکس آپلودی | `analysis.py:validate_image_route` | عکس → معتبر/نامعتبر | بینایی |
| ۵ | اعتبارسنجی عکس فروش مو | `hair_sale_steps.js` → همان endpoint | عکس فروش → معتبر/نامعتبر | بینایی |
| ۶ | برنامه اختصاصی | `analysis.py:analysis_plan` | نتیجه تحلیل → برنامه هفتگی | راه سریع |
| ۷ | راهکار سریع | `analysis.py:_generate_quick_solution` | متن → ۳ اقدام + هشدار | راه سریع |
| ۸ | چت مشاور صادقی (سایت) | `analysis.py:consultant_chat_message` | گفت‌وگوی کاربر با مشاور | چت |
| ۹ | خلاصه‌ساز تاریخچه چت | `analysis.py:_summarize_chat_history` | تاریخچه → خلاصه ≤۵۰۰ کاراکتر | راه سریع |
| ۱۰ | ویجت هوشمند سایت | `app.py:ai_widget_chat` | پرسش بازدیدکننده + پاسخ جایگزین قطعی | چت |
| ۱۱ | مشاور ربات (بله) | `bot_admin_utils.py:1079` | مشاوره در ربات با زمینه کامل کاربر | چت |
| ۱۲ | دستیار سوپرادمین | `panel/modules/super_assistant.py:337` | چت آزاد در پنل | چت |
| ۱۳ | دستیار ویژه «آقا رضا» | `special_assistant.py:261` | چت با آمار زنده | چت (مستقیم) |
| ۱۴ | پارس محصول کانال | `channel_importer.py:_ai_parse` | کپشن → نام/قیمت/دسته | راه سریع |
| ۱۵ | گزارش پایش و بینش | `monitoring_ai.py` و `monitoring_insights.py` | تحلیل خطاها و گزارش روزانه | چت (نقش سوپر) |
| ۱۶ | تولید متن سئو | `seo_jobs.py:_ask_meta_text` | متن متا برای صفحات | چت (مستقیم) |

### ۲۵.۲ موتور تحلیل عکس (بینایی)

**کجا استفاده می‌شود؟** اعتبارسنجی عکس فروش مو، آنالیز مو/پوست، اعتبارسنجی عکس آپلودی.

**چطور مدل انتخاب می‌شود؟**
1. پروایدرها به ترتیب زنجیره امتحان می‌شوند: `groq → openrouter → cloudflare → mistral → gemini → avalai → gapgpt` (اولویت رایگان‌ها؛ ۱۴۰۵-۰۶-۱۸ — جزئیات در §۲۷)
2. برای هر پروایدر منابع مدل به این اولویت خوانده می‌شوند: ۱) `selected_model` ۲) ستون `vision_models_json` ۳) `fallback_json` ۴) `models_json` ۵) رجیستری فایل
3. هر مدلی که در کولداون سلامت باشد از زنجیره حذف می‌شود (اگر همه در کولداون بودند، دوباره شانس می‌گیرند تا سیستم قفل نشود)

**سقف زمانی:** کل زنجیره **۴۵ ثانیه**؛ هر مدل **۸ ثانیه**.

**رفتار با خطاها:**
- 429 (سقف مصرف): پروایدر رایگان ← پرش فوری؛ پروایدر پولی ← ۲ ثانیه صبر و پرش
- 401/403/تایم‌اوت/شبکه ← مدل بعدی + ثبت کولداون ۵ دقیقه
- رد کردن عکس توسط مدل (refusal) ← مدل بعدی
- در پایان، پیام خطای کاربرپسند فارسی برمی‌گردد (نه متن فنی)

### ۲۵.۳ موتور چت (مشاور)

همهٔ نقاط چت (۸، ۱۰، ۱۱، ۱۲، ۱۳، ۱۵، ۱۶) از `chat_with_failover` در `ai_runtime.py` استفاده می‌کنند (نقاط ۱۳ و ۱۶ مستقیم، بقیه از طریق لایه مدیریت‌شده با نقش/سهمیه).

**سقف زمانی:** کل زنجیره **۳۰ ثانیه**؛ هر پروایدر **۶ ثانیه**. کولداون‌ها از جدول سلامت مشترک خوانده می‌شوند (جایگزین کولداون درون‌حافظه‌ای قدیمی).

### ۲۵.۴ موتور راه سریع

برای پاسخ‌های کوتاه و ساختاریافته (برنامه، راهکار، پارس محصول، خلاصه). **سقف زمانی:** کل **۱۵ ثانیه**؛ هر مدل **۴ ثانیه**. ترتیب: پروایدرهای خارجی اول، ایرانی‌ها بعد (حفظ رفتار قدیمی).

### ۲۵.۵ سیستم سلامت و کولداون (`giso_ai_health`)

- هر خطای موتور (بینایی/چت/سریع) با `mark_failure` ثبت می‌شود: نوع خطا (`timeout/429/auth/refused/http_error/network/json/unknown`)، شمارش شکست و پایان کولداون.
- کولداون پیش‌فرض **۵ دقیقه** (`HEALTH_COOLDOWN_MINUTES`). موفقیت با `mark_success` کولداون را پاک می‌کند.
- سطر با مدل خالی = کولداون سطح پروایدر و روی **همهٔ مدل‌هایش** اثر می‌گذارد.
- جدول بعد از ری‌استارت هم معتبر است (برخلاف کولداون قدیمی چت که در حافظه بود).
- همهٔ تلاش‌ها با فرمت `[AI_ATTEMPT] engine=… provider=… model=… result=… duration=…` لاگ می‌شوند (در وب از ۱۴۰۵-۰۶-۱۸ با `_ensure_ai_logging` در `app.py` قابل مشاهده‌اند).

### ۲۵.۶ پنل مدیریت هوش مصنوعی

مسیر: پنل سوپرادمین → تب «🤖 مدیریت هوش مصنوعی». همهٔ روت‌ها با پیشوند `/admin` و فقط برای سوپرادمین.

**چطور یک سرویس AI اضافه کنم؟**
1. روی «➕ افزودن سرویس» کلیک کنید.
2. فقط ۲ فیلد الزامی است: **نام سرویس** (از منوی ۸تایی رجیستری یا نام دلخواه در فیلد `custom_name`) و **کلید API**.
3. «💾 ذخیره و شناسایی خودکار مدل‌ها» را بزنید. سیستم خودکار: آدرس/نوع/تایم‌اوت را از رجیستری پر می‌کند، به `/models` وصل می‌شود، مدل‌های بینایی/متنی را جدا می‌کند و پیام «✅ سرویس اضافه شد — X مدل Vision + Y مدل Text شناسایی شد» را نشان می‌دهد.
4. اگر کلید پروایدری که کلید نداشت را از «✏️ ویرایش فیلد → api_key» پر کنید، پروایدر خودکار فعال و مدل‌هایش تازه می‌شود.

**چطور مدل‌ها را تازه کنم؟** دکمه **🔄 بروزرسانی مدل‌ها** کنار هر پروایدر — فقط لیست `/models` را می‌گیرد (بدون مصرف سهمیه؛ تفاوتش با دکمه «🔁 تست» همین است که تست یک پیام `Hi` می‌فرستد). مدل‌هایی که سرویس دیگر ارائه نمی‌دهد پرچم `disabled` می‌گیرند و جدیدها با منبع «کشف‌شده» اضافه می‌شوند.

**چطور چند مدل را یک‌جا اضافه کنم؟** فرم «📥 ورود دسته‌ای مدل‌ها» بالای صفحه با این فرمت:
```json
{
  "provider": "openrouter",
  "add_models": [
    {"id": "google/gemma-3-27b-it:free", "type": "vision", "is_free": true},
    {"id": "deepseek/deepseek-chat:free", "type": "text", "is_free": true}
  ]
}
```
`type` می‌تواند `vision`، `text` یا `both` باشد (`both` از ۱۴۰۵-۰۶-۱۸ به هر دو لیست می‌رود). مدل‌های موجود پاک نمی‌شوند و تکراری‌ها رد می‌شوند.

**چطور پروکسی تنظیم کنم؟** در فرم افزودن یا «✏️ ویرایش فیلد → پروکسی اختصاصی»:
- بدون احراز هویت: `socks5://127.0.0.1:1080` — با احراز هویت: `socks5://user:pass@ip:port` — HTTP: `http://proxy.example.com:8080`
- اولویت: ۱) `proxy_url` خود پروایدر ۲) استخر پروکسی جمینای (اگر `use_proxy` فعال باشد) ۳) اتصال مستقیم. خالی گذاشتن فیلد = حذف پروکسی.

### ۲۵.۷ راهنمای عیب‌یابی

| مشکل | علت احتمالی | راه حل |
|---|---|---|
| خطای 401 هنگام تست | کلید API نامعتبر/منقضی | کلید جدید از سایت سرویس بگیرید؛ ویرایش `api_key` در پنل |
| پاسخ خیلی کند | پروکسی کند یا سرویس شلوغ | پروکسی اختصاصی سریع‌تر تنظیم کنید؛ سقف‌ها مانع قفل‌شدن می‌شوند |
| «مدل بینایی پیدا نشد» | لیست مدل خالی یا همه غیرفعال | دکمه «🔄 بروزرسانی مدل‌ها» را بزنید |
| سرویس بعد از آپدیت مشکل دارد | تغییر ناسازگار | `FEATURE_FLAG_LEGACY_MODE = True` در `giso/ai_config.py` + ری‌استارت = بازگشت کامل رفتار قدیمی هر سه موتور |
| لاگ `[AI_ATTEMPT]` دیده نمی‌شود | لاگر ریشه تنظیم شده/هندلر ندارد | `_ensure_ai_logging` در `app.py` فقط وقتی هیچ هندلری نباشد فعال می‌شود؛ سطح لاگ استقرار را بررسی کنید |

### ۲۵.۸ تنظیمات پیشرفته (`giso/ai_config.py`)

```python
VISION_TOTAL_TIMEOUT_SECONDS = 45   # بودجه کل تحلیل عکس
VISION_PER_MODEL_TIMEOUT_SECONDS = 8
CHAT_TOTAL_TIMEOUT_SECONDS = 30     # بودجه کل چت
CHAT_PER_MODEL_TIMEOUT_SECONDS = 6
FAST_TOTAL_TIMEOUT_SECONDS = 15     # بودجه کل راه سریع
FAST_PER_MODEL_TIMEOUT_SECONDS = 4
BACKOFF_429_PAID_PROVIDER_SECONDS = 2  # صبر برای پروایدر پولیِ 429 گرفته
HEALTH_COOLDOWN_MINUTES = 5            # مدت کولداون بعد از خطا
FEATURE_FLAG_LEGACY_MODE = False       # True = رفتار قدیمی همه موتورهای بازنویسی‌شده
```
بعد از تغییر، سرویس را ری‌استارت کنید. ترتیب زنجیره چت در `giso/ai_runtime_policy.py` (`DEFAULT_ACTIVE_PROVIDER_ORDER`) تغییر می‌کند.

### ۲۵.۹ تاریخچه: بازبینی و تست واقعی (مأموریت `2.md`)

**یافته‌های بازبینی فنی (`docs/ai_review_findings.md` — ادغام‌شده در همین بخش):**
- 🔴 ویرایش پروکسی از پنل بی‌صدا ذخیره نمی‌شد (`proxy_url` در وایت‌لیست `_AI_EDITABLE` نبود) — **اصلاح شد**.
- 🟡 مدل `type=both` در ورود دسته‌ای فقط به لیست متن می‌رفت — **اصلاح شد** (به هر دو لیست می‌رود).
- 🟡 لاگ‌های `[AI_ATTEMPT]` در فرایند وب چاپ نمی‌شدند — **اصلاح شد** (`_ensure_ai_logging`).
- 🟢 ثبت برای آینده: پرچم غیرفعال روی مدل‌های خارج از صفحهٔ اول `/models` اگر سرویس صفحه‌بندی کند؛ پاک‌سازی دوتایی پاسخ چت؛ غیرفعال‌سازی `llm7` در هر استارتاپ (عمدی)؛ خواب مسدودکنندهٔ ۲ ثانیه‌ای بک‌آف؛ عبور احتمالی از بودجه کل به اندازه یک تایم‌اوت تک‌مدل.

**نتایج تست واقعی (`docs/ai_test_results.md` — ادغام‌شده در همین بخش):** ۱۴/۱۴ تست خودکار پاس (رجیستری، ستون‌ها، کشف با موک، ورود دسته‌ای، پروکسی، جدول سلامت، کولداون، سقف زمانی در سناریوی همه‌شکست، پرچم امنیت، و درخواست واقعی عکس به `/analysis/validate-image` روی وب‌سرور زنده با ۸ لاگ `[AI_ATTEMPT]`). دو مورد منوط به کلید/توکن واقعی: تست شبکه‌ای `refresh_models` و چت زندهٔ ربات. کیت کامل: **۵۵۶ پاس / ۳۹ فیل محیطی — صفر رگرسیون** در هر سه فاز.

---

## §26. ممیزی جامع ۱۲ بخش — snapshot تاریخی 2026-09-09 <!-- updated 2026-09-26 -->

اجرای کامل مأموریت `3.md` در سه مرحله با گزارش‌های `giso/docs/r2.md` (ساختار)، `r3.md` (عیب‌یابی) و `r4.md` (اصلاحات).

| مرحله | نتیجه |
|---|---|
| شناخت ساختار (r2) | ۱۲ بخش مستند شد: ۳۱۹ روت، ۹۱ جدول، ۱۶ نقطه اصلی استفاده از AI |
| عیب‌یابی (r3) | ۴۴ تست خودکار + بررسی‌های استاتیک/سئو/امنیت — ۲ مشکل 🟡 پیدا شد (۰ بحرانی) |
| اصلاح (r4) | هر ۲ مشکل حل شد: وایت‌لیست `target_table` در پلن اقدام سوپرادمین (`ai_runtime.py`) + پاک‌سازی ۲۶۷ رکورد یتیم کلید خارجی با اسکریپت `giso/scripts/fix_fk_orphans.py` (پیش‌فرض فقط گزارش؛ `--apply` برای اجرا) |

**نکته عملیاتی:** بعد از حذف کاربر، اسکریپت یتیم‌ها را روی دیتابیس تولید اجرا کنید (اول گزارش، بعد `--apply`). کیت تست پس از اصلاحات: **۵۵۶ پاس / ۳۹ فیل محیطی** — صفر رگرسیون.

---

## §27. لیست تمیز هوش مصنوعی + پراکسی زنده — snapshot تاریخی 2026-09-09 <!-- updated 2026-09-26 -->

اجرای مأموریت ۵ مرحله‌ای «لیست تمیز» (گزارش کامل: `r5.md` و این بخش): تحلیل مصرف، راستی‌آزمایی سرویس‌های رایگان، حذف سرویس‌های بی‌جواب، ثبت تک‌مرحله‌ای، و پراکسی فقط‌زنده.

### ۲۷.۱ نقشهٔ مصرف هوش مصنوعی پروژه

| نیاز پروژه | نقاط استفاده (§۲۵.۱) | نوع مدل لازم |
|---|---|---|
| تحلیل عکس مو/پوست و اعتبارسنجی عکس‌ها | ۱ تا ۵ | **بینایی رایگان** |
| چت مشاور، ویجت، دستیارها، سئو، پایش | ۸ تا ۱۶ | **متنی سریع و رایگان** |
| برنامه/راهکار و پارس محصول کانال | ۶، ۷، ۹، ۱۴ | متنی (راه سریع) |

### ۲۷.۲ لیست تمیز پروایدرها (رجیستری `giso/ai_models_registry.py`)

| پروایدر | رایگان | بینایی | مناسب پروژه برای | وضعیت |
|---|---|:---:|---|---|
| **Groq** | ✅ ۱۴٬۴۰۰ درخواست/روز | ✅ (llama-4-scout) | تحلیل عکس + چت سریع — اولویت اول | فعال |
| **OpenRouter** | ✅ ۵۰ تا ۱۰۰۰/روز | ✅ ۵ مدل (gemma-4، inkling، nemotron-omni) | تحلیل عکس + چت باکیفیت | فعال |
| **Mistral AI** | ✅ پلن Experiment | ✅ (mistral-small، pixtral-large) | پشتیبان بینایی/چت (~۱ درخواست/ثانیه) | جدید |
| **SambaNova** | ✅ ۶۰۰ درخواست/دقیقه | ❌ | پشتیبان چت متنی | جدید |
| **Cloudflare Workers AI** | ✅ ۱۰K نورون/روز | ✅ | پشتیبان بینایی (نیاز به `{account_id}` در آدرس) | فعال |
| **Gemini (ورکر کارفرما)** | ✅ | ✅ | مسیر اختصاصی از ورکر کلودفلر | فعال |
| **GapGPT / AvalAI** | پولی | ✅ | پشتیبان آخر (ایرانی) | بدون تغییر |

**حذف‌شده‌ها (دستور کارفرما):** `huggingface` و `cerebras` از رجیستری حذف شدند؛ ردیف‌های دیتابیس‌شان **حذف نمی‌شود** و در هر استارتاپ غیرفعال می‌مانند (`RETIRED_PROVIDERS` در `ai_brain.py` — همان الگوی `llm7`).

### ۲۷.۳ ثبت تک‌مرحله‌ای (ربات و پنل)

در ربات ادمین: فقط **نام پروایدر + API Key** بدهید — آدرس بیس، تایم‌اوت و کل مدل‌ها خودکار از رجیستری پر می‌شود (`add_ai_provider` + `default_models_for_provider`)، سپس تست سلامت اجرا می‌شود. نام‌های نمایشی هم قبول است («Mistral AI» ← `mistral`).

### ۲۷.۴ تازه‌سازی خودکار مدل‌ها در استارتاپ

`seed_registry_providers` در هر شروع سرور سه کار می‌کند:
1. **مهاجرت نام** ردیف‌های قدیمی (`_normalize_existing_provider_names`)؛
2. **تازه‌سازی مدل‌ها** فقط برای پنج پروایدر لیست تمیز و فقط اگر منبع مدل «رجیستری/خالی» باشد (`_refresh_registry_sourced_models`) — تنظیمات دستی/کشف‌شده و پروایدرهای ایرانی/جمینا هرگز لمس نمی‌شوند؛
3. **کاشت** ردیف خالی برای پروایدرهای جدید + **غیرفعال‌سازی** بازنشسته‌ها.

### ۲۷.۵ پراکسی فقط‌زنده

- منبع پیش‌فرض: آدرس v4 پروکسی‌اسکرپ با کشورهای غیرتحریمی (در `gemini_proxy_manager.py`).
- فقط پروکسی‌هایی که تست واقعی اتصال + کشور را پاس کنند وارد استخر می‌شوند.
- **حذف خودکار:** پروکسی که در استفادهٔ واقعی ۵ شکست پیاپی بخورد (`RUNTIME_EVICT_AFTER`) از استخر «سالم‌ها» حذف می‌شود و در لاگ `proxy eviction` ثبت می‌گردد.
- توصیه: برای کارکرد پایدار تحلیل عکس، حالت «ورکر» یا پروکسی دستی خصوصی مطمئن‌تر از لیست رایگان است.


---

## §28. وضعیت canonical پروژه در 2026-09-26 — ممیزی کد + Graphify

این بخش برای جلوگیری از دوباره‌کاری و مهم‌تر از آن، جلوگیری از باور کردن عددهای قدیمی نوشته شده است. **مرجع نهایی همیشه کد commit جاری است، نه عددی که در گزارش قدیمی آمده است.**

### ۲۸.۱ محدوده ممیزی

- شاخه: `giso-end`
- commit مبنا: `49e41dfd7535cfaa0c0319af1716ca1bd5844bcd`
- scope: کل هستهٔ `giso/`
- `beauty-preview`: **خارج از scope** و عمداً در این راهنما مستند نشده است.
- `bot_edu/` و `web/`: فقط در حد قراردادهای اتصال مشترک؛ این راهنما مالک تغییرات آن‌ها نیست.
- Graphify با `--code-only` اجرا شده تا وابستگی به LLM برای استخراج اسناد و تصاویر حذف شود.

### ۲۸.۲ snapshot نقشه Graphify

خروجی فعلی در `graphify-out/`:

| شاخص | مقدار |
|---|---:|
| فایل کد استخراج‌شده | 371 |
| node | 7,755 |
| edge | 24,200 |
| community | 226 |
| community نمایش‌داده‌شده | 197 |
| community باریک حذف‌شده از نمایش | 29 |
| EXTRACTED | 89% |
| INFERRED | 11% |
| edgeهای inferred | 2,738 |
| میانگین confidence برای inferred | 0.86 |
| commit گراف | `49e41dfd` |

**محدودیت مهم:** edgeهای `INFERRED` فرضیهٔ Graphify هستند، نه حقیقت کد. هر نتیجهٔ معماری که بر یک edge inferred تکیه کند باید با import/call واقعی در فایل تأیید شود.

### ۲۸.۳ هسته‌های اتصال مهم

Graphify در این snapshot بیشترین اتصال را برای این نقاط نشان می‌دهد:

1. `get_giso_db_conn()` — 561 edge
2. `create_app()` — 390 edge
3. `_run_async()` — 289 edge
4. `redirect()` — 287 edge
5. `url_for()` — 280 edge
6. `flash()` — 247 edge
7. `route()` — 223 edge
8. `button_handler()` — 191 edge
9. `User` — 181 edge
10. `handle_callback()` — 162 edge

نتیجهٔ معماری: `get_giso_db_conn()` و `create_app()` نقاط پراتصال هستند؛ تغییرات ساختاری در آن‌ها باید کوچک، قابل rollback و همراه با تست regression باشد. Graphify نباید بهانه‌ای برای refactor بزرگ `bot.py` یا شکستن لایه‌های پایدار شود.

### ۲۸.۴ نقشهٔ فعلی ماژول‌های مرکزی که باید در راهنما شناخته شوند

علاوه بر ماژول‌های قبلی، این فایل‌ها/لایه‌ها اکنون بخشی از معماری جاری‌اند و نباید در ممیزی‌های بعدی «وجود ندارند» فرض شوند:

| فایل | نقش فعلی | وضعیت مستندات |
|---|---|---|
| `recommendation_service.py` | موتور پیشنهاد چندسیگناله؛ اتصال Analysis → Recommendation → Products → Shop؛ دادهٔ واقعی DB و سقف 4 پیشنهاد صفحه/3 ویجت | **باید در مسیر تحلیل→فروشگاه ذکر شود** |
| `ai_discovery.py` | کشف مدل از `/models` providerها، انتخاب مدل‌های vision/text، refresh و گزارش برای پنل/ربات | **باید در AI architecture ذکر شود** |
| `analysis_report.py` | استخراج سازنده‌های pure برای گزارش نهایی آنالیز از `analysis.py` بدون وابستگی Flask/DB | **باید به decomposition آنالیز اضافه شود** |
| `analysis_labels.py` | لایهٔ برچسب‌گذاری/normalization خروجی تحلیل | **باید کنار analysis_report مستند شود** |
| `widget_service.py` | سرویس ویجت AI و اعلان‌های مشاور، استخراج‌شده از `app.py` با re-export برای سازگاری | **باید در AI/UI service map ذکر شود** |
| `seo_meta.py` | اعتبارسنجی و پرکردن meta description محصولات؛ طول 150–160 و فیلتر claimهای ممنوع | **باید در SEO jobs ذکر شود** |
| `seo_sitemap.py` | cache دیسکی sitemap؛ TTL پیش‌فرض 3 ساعت و فعال‌سازی پیش‌فرض production | **باید در SEO/runtime ذکر شود** |
| `site_jobs.py` | hookهای background best-effort سایت: digest روزانه، واریز اعتبار رتبه، تخلیه صف broadcast | **باید کنار app factory ذکر شود** |
| `security_alerts.py` | اعلان پایدار و privacy-safe رویدادهای ورود مشکوک، claim idempotent و ارسال best-effort | **باید در security/auth ذکر شود** |
| `account_password_vault.py` | خزانهٔ رمزگذاری‌شده برای نمایش رمز فعلی به superadmin با تطبیق hash؛ جایگزین hash یک‌طرفه نیست | **باید در امنیت/حساب ذکر شود** |
| `wallet_core.py` | ثابت‌ها، scopes cash/spend، قواعد دفترکل و تنظیمات مالی | **هستهٔ wallet** |
| `wallet_missions.py` | منطق مأموریت‌ها و reward scope | **زیرلایهٔ wallet** |
| `wallet_receipts.py` | ذخیرهٔ خصوصی رسید top-up، JPG/PNG، ≤5MB و ≤20MP، خارج static | **زیرلایهٔ wallet/security** |

### ۲۸.۵ پنل کاربر — وضعیت واقعی

**کانت اصلی منو ۹ مورد است**، نه ۱۵:

`overview, hair_sale, orders, analyses, reservations, center_chats, wallet, chats, profile`

در کنار آن‌ها metadata/route برای `notifications, marketplace, buyer_request, beauty_center, ai_assistant, shop, wishlist, reviews, notifies` وجود دارد. این تفاوت باید در هر مستندات بعدی حفظ شود:

- «۹ گزینهٔ اصلی» = منوی canonical فعلی.
- «قابلیت‌های پنل» = همهٔ route/module capabilityها.
- «۱۵ ماژول» = **عبارت قدیمی و غیرcanonical**.

گروه‌بندی فعلی `USER_MODULE_GROUPS` چهار گروه دارد:
`اصلی`، `خدمات`، `پشتیبانی`، `حساب کاربری`.
پس هر متن قدیمی که آن را «خالی» معرفی کند غلط است.

### ۲۸.۶ پنل ادمین

`giso/panel/modules/` دارای 19 ماژول فایل است و `notifications/` و `backup/` به‌صورت package در کنار آن‌ها هستند. این شمارنده همچنان با ساختار فعلی سازگار است.

در مقابل، نباید دسترسی ادمین را صرفاً از روی نام فایل‌ها نتیجه گرفت. قرارداد دسترسی در `giso/panel/permissions.py` و guardهای route تعیین می‌شود. برای عملیات حساس، هم guard عمومی و هم `require_super` را بررسی کنید.

### ۲۸.۷ AI — حقیقت فعلی

رجیستری کد `giso/ai_models_registry.py::PROVIDERS` دقیقاً **8 provider** دارد:

1. `groq`
2. `openrouter`
3. `mistral`
4. `sambanova`
5. `cloudflare`
6. `gemini`
7. `gapgpt`
8. `avalai`

بنابراین:
- «7 provider» در جدول قدیمی DB/schema **غلط** است.
- «8 provider» معیار فعلی است.
- زنجیرهٔ Vision می‌تواند فقط subset دارای vision باشد و این با «تعداد کل providerها» تناقضی ندارد.
- `ai_discovery.py` مکمل رجیستری است: برای providerهای دارای endpoint مدل، `GET /models` را بررسی می‌کند و لیست مدل‌ها را به‌روز می‌کند.
- `cloudflare` در discovery از `/models` مستثنی است و مدل‌هایش از رجیستری پایه مدیریت می‌شوند.

### ۲۸.۸ تحلیل و توصیه محصول

مسیر معماری را به شکل زیر در نظر بگیرید:

`analysis.py` → گزارش/normalization در `analysis_report.py` و `analysis_labels.py` → `recommendation_service.py` → `products`/Shop → UI

`recommendation_service.py` از دادهٔ واقعی کاربر مانند آخرین hair order، آخرین analysis و تاریخچهٔ تعامل/خرید استفاده می‌کند و سقف توصیه دارد؛ دادهٔ ساختگی نباید برای تکمیل این زنجیره اضافه شود.

### ۲۸.۹ امنیت و حساب

- `security.py`: CSRF، rate limit، audit، headers و guardهای امنیتی.
- `security_alerts.py`: رویدادهای ورود مشکوک و اعلان پایدار.
- `account_password_vault.py`: secret-backed encryption برای نگهداری رمز قابل نمایش به superadmin؛ این را با `password_hash` یکسان نگیرید.
- `wallet_receipts.py`: رسیدهای top-up خارج از static و فقط از route محافظت‌شده سرو می‌شوند.
- اصل مهم: وجود یک helper یا route به معنی «امن بودن runtime» نیست؛ سناریوی واقعی auth/IDOR/CSRF باید تست شود.

### ۲۸.۱۰ SEO و background jobs

- `seo_meta.py`: meta description را sanitize/validate می‌کند؛ بازهٔ 150–160 کاراکتر و banned claimها را کنترل می‌کند.
- `seo_sitemap.py`: cache sitemap با TTL پیش‌فرض 3 ساعت و production-only default.
- `site_jobs.py`: سه hook best-effort را از `create_app` جدا کرده و رفتار/نام threadهای قبلی را حفظ می‌کند؛ شامل digest بازاریابی، rank credit deposit و broadcast drain.

### ۲۸.۱۱ Wallet decomposition

`wallet.py` همچنان facade/compatibility surface مهم است، اما منطق اکنون در چند فایل تخصصی هم وجود دارد:
- `wallet_core.py`: scopes، ثابت‌ها، قواعد مالی و helperهای اصلی.
- `wallet_missions.py`: mission list/create/reward و completion.
- `wallet_receipts.py`: receipt validation/storage.
- `wallet_balepay.py` و `bot_balepay.py`: مسیر پرداخت بله.
- `rank_daily.py`: رتبه و اعتبار دوره‌ای.
این تفکیک باید در راهنمای معماری حفظ شود و نباید صرفاً `wallet.py` را کل سیستم فرض کرد.

### ۲۸.۱۲ Mission / Referral / Saved Search

- **Mission:** ساختار `once/daily/weekly` در داده/نمایش وجود دارد، اما semantics کامل روزانه/هفتگی در `complete_mission` هنوز باید با تست runtime و منطق فعلی تأیید شود؛ وضعیت مستنداتی: **PARTIAL**.
- **Referral:** جریان کسب‌وکار متوقف/retired است؛ `referrals` و ستون‌های قدیمی فقط برای سازگاری/ممیزی حفظ می‌شوند و نباید به‌عنوان قابلیت فعال تبلیغ شوند.
- **Saved Search:** جدول `marketplace_saved_searches` باقی است اما UI فعال canonical ندارد؛ وضعیت: **SOFT-DEPRECATED / RETAINED**.

### ۲۸.۱۳ قواعد وضعیت‌گذاری در این راهنما

برای هر قابلیت از برچسب زیر استفاده شود:

- **IMPLEMENTED**: کد و مسیر فعلی وجود دارد؛ اگر runtime تست نشده، همان را صریح بنویس.
- **PARTIAL**: بخشی از قرارداد/جریان وجود دارد ولی semantics یا runtime کامل نشده است.
- **LEGACY**: برای سازگاری نگه داشته شده و مسیر اصلی نیست.
- **SOFT-DEPRECATED**: داده/route هنوز وجود دارد ولی UI/استفادهٔ canonical ندارد.
- **RETIRED**: دیگر نباید به‌عنوان قابلیت فعال معرفی شود، ولی ممکن است داده/ردپا باقی بماند.
- **NOT VERIFIED**: فقط از static/code evidence می‌دانیم و runtime test لازم است.

قاعدهٔ مهم: **وجود route = اثبات وجود feature نیست؛ وجود table = اثبات فعال بودن business flow نیست؛ Graph edge = اثبات dependency نیست.**

### ۲۸.۱۴ چک‌لیست همگام‌سازی بعدی

هر بار که ساختار Giso تغییر کرد:

1. `git rev-parse HEAD` را ثبت کن.
2. `graphify update .` یا extraction مناسب اجرا کن.
3. تعداد providerها را از `ai_models_registry.py` بخوان، نه از متن قبلی.
4. منوی کاربر را از `panel_user/permissions.py::USER_MODULES` بخوان.
5. دسترسی‌ها را از `panel/permissions.py` و guardهای route تأیید کن.
6. routeهای canonical و legacy را جداگانه ثبت کن.
7. جداول active را از migration/schema واقعی تطبیق بده.
8. featureهای retired/soft-deprecated را از active جدا نگه دار.
9. اگر runtime تست نشده، **NOT VERIFIED** بنویس.
10. پس از تغییر این فایل، تاریخ و commit این راهنما را به‌روز کن.

### ۲۸.۱۵ نتیجهٔ canonical

در تاریخ 2026-09-26، این راهنما باید این موارد را به‌عنوان حقایق فعلی در نظر بگیرد:

- `giso-end` commit = `49e41dfd`
- `beauty-preview` خارج scope
- `bot.py` = 7422 خط
- Graphify = 7755 nodes / 24200 edges / 226 communities
- providerهای AI = 8
- user top-level menu = 9
- `USER_MODULE_GROUPS` = چهار گروه، **غیرخالی**
- admin panel = 19 module files + 2 packages
- Mission = PARTIAL
- Referral = RETIRED
- Saved Search = SOFT-DEPRECATED / RETAINED
- inferred Graphify edges = نیازمند تأیید با کد واقعی
