# SS2 — سناریوی ممیزی کامل پروژه Giso

## هدف
ممیزی کامل پروژه Giso بر اساس Graphify و Code Truth؛ برای هر بخش مشخص شود چه چیزی واقعاً کار می‌کند، چه چیزی تست شده، چه چیزی فقط از روی کد بررسی شده و چه چیزی اصلاً تست نشده است.

Repository: uname1370-create/giso4
Branch: arena/09bed010-giso4

## قوانین
- این مرحله فقط AUDIT است؛ هیچ کد، تست، migration یا config را اصلاح نکن.
- فقط فایل‌های گزارش مجاز به ایجاد/ویرایش هستند.
- تست‌ها را برای سبز شدن دستکاری نکن.
- Reuse > Extend > New.
- اگر چیزی اثبات نشده: NOT VERIFIED.
- اگر تست اجرا نشده: NOT TESTED.
- اگر محیط یا credential مانع شد: BLOCKED با علت دقیق.
- Secret/API Key/Token هرگز در فایل، log یا report نوشته نشود.
- هر بخش باید با giso-dev skill بررسی شود. اگر skill واقعاً در محیط موجود نیست، جعل استفاده از آن ممنوع و وضعیت BLOCKED ثبت شود.

## مرحله 0 — اعتبارسنجی Graphify
ابتدا HEAD واقعی branch را ثبت کن و این موارد را بررسی کن:
- graphify-out/graph.json
- graphify-out/GRAPH_REPORT.md
- graphify-out/manifest.json
- graphify-out/.graphify_analysis.json
- graphify-out/stat-index.json
- graphify-out/.graphify_root

نکته مهم: graph.json فعلی مقدار built_at_commit قدیمی‌تری از commit ادعاشده در GRAPH_REPORT دارد. این اختلاف باید ابتدا بررسی شود. اگر Graph stale است، با روش واقعی پروژه refresh شود و سپس commit Graph با HEAD تطبیق داده شود. تا قبل از این تأیید، Graph فقط reference تاریخی است.

## مرحله 1 — تحلیل کامل Graph
پس از معتبر شدن Graph:
- تمام Nodeها
- تمام Edgeها
- calls
- imports/imports_from
- contains
- references
- re_exports
- inherits
- indirect_call
- rationale_for
- uses
- Communityها
- God Nodes
- Cross-module dependencies
را بررسی کن.

Graph را برای ساختن نقشه پوشش ممیزی استفاده کن؛ فقط به چند Community معروف اکتفا نکن.

## ساختار گزارش
برای هر بخش یک گزارش مستقل بساز:
1. audit_reports/ss2/01_runtime_bootstrap.md
2. audit_reports/ss2/02_auth_permissions.md
3. audit_reports/ss2/03_database_integrity.md
4. audit_reports/ss2/04_user_panel.md
5. audit_reports/ss2/05_admin_panel.md
6. audit_reports/ss2/06_beauty_centers.md
7. audit_reports/ss2/07_reservations.md
8. audit_reports/ss2/08_mirror_buti_ai.md
9. audit_reports/ss2/09_ai_runtime.md
10. audit_reports/ss2/10_marketplace_shop_hair_sale.md
11. audit_reports/ss2/11_wallet_payment_referral.md
12. audit_reports/ss2/12_bale_bot_bot_edu.md
13. audit_reports/ss2/13_analysis_consulting_notifications.md
14. audit_reports/ss2/14_backup_restore_files.md
15. audit_reports/ss2/15_seo_public_web_security.md
16. audit_reports/ss2/16_cross_module_integration.md
17. audit_reports/ss2/17_tests_coverage_untested.md

در پایان:
ss2_final_report.md

## قالب اجباری هر گزارش
- Status: PASS / PARTIAL / FAIL / BLOCKED / NOT VERIFIED
- Confidence
- Tested: YES / PARTIAL / NO
- Scope
- Graph findings
- Code Truth
- مسیر واقعی اجرا
- تست‌های موجود
- تست‌های اجراشده و نتیجه
- تست‌های انجام‌نشده
- مشکلات با Severity P0/P1/P2/P3
- Evidence شامل فایل، تابع، Route و تست
- Root Cause
- Impact
- نتیجه نهایی

## 01 — Runtime / Bootstrap
بررسی main.py، giso/app.py، create_app، startup/shutdown، Blueprintها، config، env، maintenance، async bridge، proxy و provider initialization.
تست import، app creation، route registration و failure path.

## 02 — Authentication / Authorization
بررسی login/logout/session، Flask-Login، guest/user/admin/super-admin/beauty-owner، permission matrix، callback authorization، direct URL access، object ownership و IDOR/privilege escalation.
برای هر Role تست عملی انجام شود.

## 03 — Database / Data Integrity
بررسی get_giso_db_conn، models، schema، migration، SQLite/Postgres، WAL، transaction، lock، rollback، foreign key، unique constraint و atomicity.
برای جدول‌های مهم Source of Truth، owner، writer، reader و integrity rule مشخص شود.

## 04 — User Panel
بررسی dashboard، profile، history، analyses، consultation، notifications، wallet، marketplace، beauty center و Mirror history/result.
Cross-user access حتماً تست شود.

## 05 — Admin Panel
بررسی admin/super-admin routes، tabs، permissions، users، analyses، AI providers، beauty centers، services، portfolio، reservations، mirror، marketplace، wallet، broadcasts، notifications و backup/restore.
هر لینک Template باید Route واقعی داشته باشد و هر Route permission واقعی.

## 06 — Beauty Centers
بررسی registration، pending review، approval، owner access، profile، services، pricing، portfolio، images، service_key، featured service، public listing/detail، chat و owner/admin panel.
Consistency بین services_json، beauty_center_services، service_key و service_id بررسی شود.

## 07 — Reservations
بررسی creation، service/center/owner validation، working hours، availability، overlap، duration، status، cancellation، final_design linkage و Mirror-to-reservation.
مسیر check → transaction → insert → commit و race condition حتماً بررسی و تست شود.
Failure هرگز success گزارش نشود.

## 08 — Mirror / Buti AI
تمام مسیر entry → upload → validation → analysis → style → provider → generation → mask → composite → final design → retry → history → centers → reservation بررسی شود.
Eyebrow، hair، makeup، nail و generic services بررسی شوند.
Ownership، guessed IDs، file access، final_design_id، service_id، service_key و selected_style بررسی شوند.
برای image generation فقط prompt را معیار ندان؛ محدودیت واقعی mask/composite و حفظ pixels خارج از mask تست شود.

## 09 — AI Runtime / Providers
بررسی provider registry، order/failover، health، circuit breaker، credits، Cloudflare، OpenAI، Gemini، vision/image provider، proxy، timeout، retry و error mapping.
ثبت provider در DB به‌تنهایی اثبات اجرای آن نیست.
Credential فقط runtime secret/env.

## 10 — Marketplace / Shop / Hair Sale
بررسی products، listings، expiration، detail، purchase، stock، orders، notifications، seller/buyer، hair sale و pricing.
Expired listing باید در list/detail/reservation/purchase رفتار درست داشته باشد.

## 11 — Wallet / Payment / Referral
بررسی balance، ledger، credit/debit، refund، idempotency، BalePay، invoice، callback، referral، reward و mission.
Double-spend و double-credit و replay callback تست شوند.

## 12 — Bale Bot / bot_edu
بررسی giso/bot.py، bot_edu/bot.py، handlers، callbacks، identity، phone mapping، admin mapping، platform sync، proxy، backup، payment، AI mentor و website integration.
مرز واقعی Giso Bot و bot_edu مشخص شود.

## 13 — Analysis / Consulting / Notifications
بررسی analysis، hair/skin analysis، reports، consulting، consultant chat، notifications، broadcasts، campaigns و reminders.
Delivery correctness و cross-user isolation تست شود.

## 14 — Backup / Restore / Files
بررسی DB backup/restore، uploads، generated images، temp files، cleanup، file ownership، unauthorized download، path traversal و filename injection.
Restore آزمایشی روی DB واقعی ممنوع؛ failure-safe بودن بررسی شود.

## 15 — SEO / Public Routes / Web Security
بررسی public routes، sitemap، Host، cache، redirects، next، open redirect، canonical، robots، rate limiting، CSRF، XSS، SSRF و path traversal.
برای URL fetchها scheme، hostname، IP، DNS rebinding، redirects، private/loopback network و cloud metadata بررسی شود.

## 16 — Cross Module Integration
مسیرهای واقعی User↔Bot، User↔Web، Web↔Bot، Mirror↔Beauty Center، Mirror↔Reservation، Center↔Reservation، Shop↔Wallet، Payment↔Wallet، Analysis↔CRM، AI↔Credits و Notification↔Modules بررسی و تست شوند.

## 17 — Tests / Coverage / Untested Map
تمام تست‌ها inventory شوند.
برای هر قابلیت مشخص شود:
- test exists؟
- executable؟
- passed؟
- integration؟
- E2E؟
- security؟
- concurrency؟
- external provider؟
- runtime واقعی؟

جدول نهایی:
Capability | Code | Unit | Integration | E2E | Security | Concurrency | Status

در پایان دقیقاً سه لیست بده:
1. واقعاً تست شده
2. فقط از روی Code/Unit Test بررسی شده
3. اصلاً تست نشده
و موارد BLOCKED را جدا کن.

## معیار PASS
قابلیت فقط وقتی PASS است که مسیر واقعی، permission، side effect، happy path، failure path، regression test و dependencyهای مهم بررسی شده باشند.
صرف وجود کد یا تست به معنی PASS نیست.

## روش اجباری هر بخش
1. Graph context
2. giso-dev skill
3. Code Truth
4. مسیر اجرا
5. تست‌های موجود
6. اجرای تست مرتبط
7. مسیرهای بدون تست
8. گزارش مستقل
9. عبور به بخش بعد

نتیجه یک بخش نباید جای بخش دیگر حساب شود.

## ss2_final_report.md
گزارش نهایی باید شامل:
- Executive Summary
- HEAD و Graph commit
- Graph freshness
- ماتریس 17 بخش
- PASS/PARTIAL/FAIL/BLOCKED/NOT VERIFIED
- P0/P1/P2/P3
- Critical Findings
- Untested Map
- Security Map
- Data Integrity Map
- AI Integrity Map
- Graph Architecture Summary
- God Nodes و Communities مهم
- Cross-module risks
- Test Coverage Matrix
- ترتیب پیشنهادی اصلاحات بدون انجام اصلاح

## Git Discipline
قبل از شروع git status.
بعد از پایان git status و diff.
در مرحله Audit هیچ فایل کد یا تست نباید تغییر کند.
فقط ss2.md، audit_reports/ss2/*.md و ss2_final_report.md مجازند.
در پایان commit و push انجام شود و SHA دقیق گزارش شود.

## قانون نهایی
بعد از این ممیزی باید برای هر قابلیت Giso جواب روشن داشته باشیم:
کجاست؟ از کجا اجرا می‌شود؟ به چه چیزی وصل است؟ چه کسی دسترسی دارد؟ چه داده‌ای می‌خواند/می‌نویسد؟ چه تستی دارد؟ واقعاً تست شده؟ چه چیزی هنوز اثبات نشده؟

اگر جواب قطعی نداریم، همان را ثبت کن و هرگز PASS فرض نکن.
