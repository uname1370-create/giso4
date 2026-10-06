# END — Full Giso Project Audit & E2E Verification

## مأموریت
این فایل سناریوی اجرایی برای ممیزی کامل، ریزبینانه و واقعی پروژه Giso4 است.

Repository: uname1370-create/giso4
Branch: arena/01a0eecf-giso4

هدف فقط بررسی Route یا فایل نیست. ابتدا ساختار واقعی فعلی پروژه را بفهم، سپس کل پروژه را متناسب با نوع هر بخش از نظر معماری، منطق، Runtime، امنیت، سرعت، کیفیت، SEO و در صورت امکان E2E واقعی بررسی کن تا مشکلات واقعی مشخص شوند.

## قانون بسیار مهم
هیچ کدی را تغییر نده. این مأموریت فقط Audit، Verification، Testing و Reporting است.
مجاز نیستی برای رفع مشکل کد، refactor، migration، dependency، معماری یا ساختار را تغییر دهی.
تنها خروجی‌های مجاز، همین ends.md و گزارش نهایی Endfiso.md هستند.

# مرحله 0 — Freshness و Baseline
ابتدا دقیقاً مشخص کن:
1. Branch، HEAD و آخرین commit.
2. وضعیت Repository.
3. وجود و وضعیت rep01.md، finbuti.md، GISO_GUIDE.md، PROJECT_GUIDE.md و Memory/Letta.
4. وضعیت Graphify/Graph/Project Memory.
5. آیا Graph و Memory با HEAD فعلی همخوان هستند یا stale.

Code Truth منبع اصلی است. هر اختلاف بین Code، Graph، Memory، Docs و Report را ثبت کن و Code Truth را مبنا قرار بده.

# مرحله 1 — شناخت کامل ساختار واقعی
کل ساختار را بشناس:
entry points، app modules، routes، blueprints، services، models، DB، migrations، auth، permissions، admin، user panel، public pages، AI/Buti، Beauty Center، Reservation، Marketplace، Wallet، Orders، Chat، Reviews، Hair Sale، existing analysis، Bale، web، bot_edu، utilities، config، errors، static، templates، tests و scripts.

از نام فایل حدس نزن. dependency و call chain را تا حد لازم دنبال کن.
از Graph برای dependency/impact analysis استفاده کن، ولی Graph edge را بدون Code Truth اثبات قطعی ندان.

# مرحله 2 — Giso-dev
تمام بررسی را با اصول Giso-dev انجام بده:
Understand Request → Project Freshness → Section Identification → Pattern & Architecture Analysis → Dependency / Impact Analysis → Graph / Memory / Docs Check → Test Plan → Runtime/E2E Verification → Regression Review → Final Report

اصول:
- Code Truth > Graph > Memory > Docs > User description
- Reuse > Extend > New
- Route وجود دارد = Feature اثبات نشده
- Table وجود دارد = Business Flow اثبات نشده
- Graph edge = dependency اثبات نشده
- py_compile = Runtime اثبات نشده
- HTTP 200 = Business Success اثبات نشده

# مرحله 3 — تطبیق با سناریو
finbuti.md، rep01.md، GISO_GUIDE.md، PROJECT_GUIDE.md و اسناد مرتبط را با Code Truth تطبیق بده.
برای هر ادعا تعیین کن:
IMPLEMENTED / PARTIAL / STATIC ONLY / NOT VERIFIED / MISSING / OUT OF SCOPE / ARCHITECTURE CONFLICT

# مرحله 4 — Full Project Audit
کل پروژه را از ابتدا تا انتها بررسی کن.

## A. Public / Entry
Home، Public pages، navigation، responsive، broken links، 404/500، assets و performance.

## B. Authentication / Authorization
login، logout، session، protected routes، guards، unauthorized access، IDOR/object ownership، CSRF و session security.

## C. User Panel
dashboard، profile، analyses، history، reservations، centers، orders، wallet، chat، reviews و قابلیت‌های موجود.

## D. Smart Analysis / Buti AI
مسیر واقعی را از ابتدا تا انتها دنبال کن:
Login → Service Selection → Model/Style → Upload → Validation → Quality → Detection → Mask → AI Analysis → Provider → Fallback → Generation → Output Validation → Before/After → Final → History → Beauty Centers → Service Matching → Reservation → Final Design

برای هر مرحله input، output، DB state، session state، ownership، error handling و dependency را بررسی کن.

## E. Beauty Centers
registration، approval، publishing، profile، services، service_key، featured service، price، duration، hours، gallery، service-level portfolio، public page، ownership، reservation، chat، reviews، promotions و analytics.

## F. Reservation
service، service_key، center، user، selected style، final_design_id، price snapshot، duration snapshot، overlap/conflict، ownership، authorization، status transitions، cancellation، duplicate/invalid booking و consistency با سیستم رزرو موجود.

سیستم رزرو دوم را فرض یا پیشنهاد نکن.

## G. Admin
dashboard، services، portfolio، reservations، analytics، filters، permissions، CSRF، ownership، destructive actions، invalid IDs و pagination/limits.

## H. Existing / Legacy
Wallet، Marketplace، Orders، Chat، Reviews، Hair Sale، existing analysis، Beauty Center existing paths، Bale-related paths در صورت active بودن، bot_edu، web و main launcher را برای regression بررسی کن.

# مرحله 5 — تست متناسب با نوع بخش

## Backend / Logic
unit، integration، DB behavior، transaction، error path، state transition و duplicate/race cases در صورت امکان.

## Web / UI
اگر محیط قابل اجراست: browser/runtime، navigation، forms، validation، loading/error، mobile/responsive، RTL، console errors، broken assets و visual defects.

## Business Flow
فقط با Route نتیجه نگیر. حداقل یک مسیر واقعی را از ابتدا تا انتها اجرا کن.

## Security
authentication bypass، authorization bypass، IDOR، CSRF، unsafe upload، path traversal، injection، XSS، secrets، sensitive leakage، unsafe errors و abuse-sensitive endpoints.

## Database
schema، relations، nullability، duplicate records، transactions، migration safety، backward compatibility و data preservation.

# مرحله 6 — Performance / Optimization
برای هر مشکل مشخص کن bottleneck کجاست و علت چیست:
N+1، repeated DB، heavy assets، image processing، external AI، cache، pagination، unnecessary computation.
اگر measurement واقعی نداری، ادعای قطعی درباره سرعت نکن؛ Risk یا NOT VERIFIED ثبت کن.

# مرحله 7 — Quality / Maintainability
duplicate logic، oversized files، unclear ownership، circular dependency، dead/orphan code، inconsistent naming، repeated business rules، hidden coupling و fragile error handling را بررسی کن.
بزرگ بودن فایل به‌تنهایی Bug نیست؛ maintainability issue را جدا ثبت کن.

# مرحله 8 — SEO
برای Public pages مرتبط:
title، meta description، canonical، headings، semantic HTML، crawlability، internal links، robots، sitemap، Open Graph در صورت relevance، duplicate content، URL quality، alt و performance impact.

# مرحله 9 — Accessibility / Responsive
RTL، keyboard، labels، contrast، focus، semantic elements، mobile/tablet/desktop، overflow، touch targets و form error clarity.

# مرحله 10 — امتیازدهی
هر قسمت امتیاز 0 تا 10 بگیرد.
ابعاد متناسب با نوع بخش:
- Correctness / Functionality
- Architecture
- Security
- Performance
- Quality / Maintainability
- UX / Responsive
- SEO در صورت relevance

اگر شواهد کافی نیست: NOT ENOUGH EVIDENCE و از نمره قطعی‌سازی خودداری کن.

# مرحله 11 — Severity
P0 Critical: امنیت جدی، از کار افتادن core، data loss یا reservation خطرناک.
P1 High: business flow مهم خراب یا unreliable.
P2 Medium: مشکل واقعی ولی محدود/قابل دور زدن.
P3 Low: UI، maintainability، SEO جزئی یا polish.

# مرحله 12 — قالب هر مشکل
برای هر مشکل واقعی:
### عنوان
### بخش
### Severity
### وضعیت
### Evidence
### محل دقیق
### Root Cause
### Impact
### Recommendation
### Evidence Type

Evidence Type فقط یکی از این‌ها باشد:
Runtime E2E / Integration / Unit / Static Code / Graph / Documentation / Not Verified

# مرحله 13 — PASS سخت‌گیرانه
وجود route، template، import، py_compile یا HTTP 200 به‌تنهایی PASS کامل نیست.
در این حالت PARTIAL یا NOT VERIFIED بده.
PASS کامل فقط با evidence کافی.

# مرحله 14 — Architecture Integrity
بررسی کن:
1. ساختار اصلی Giso حفظ شده؟
2. سیستم موازی ساخته شده؟
3. Service Catalog دوم؟
4. Reservation دوم؟
5. Mirror/Analysis دوم؟
6. Pricing دوم؟
7. duplicate business logic؟
8. restricted zones بی‌دلیل تغییر کرده؟
9. data preservation؟
10. migration additive/idempotent؟
11. out-of-scope additions؟

# مرحله 15 — گزارش نهایی
گزارش نهایی فقط در Endfiso.md قرار بگیرد و شامل:
1. Executive Summary
2. Commit / Branch / Scope
3. Current Architecture Snapshot
4. Scenario Compliance
5. Full Project Section-by-Section Results
6. Smart Analysis E2E
7. Beauty Center E2E
8. Reservation
9. Admin
10. Regression
11. Security
12. Performance
13. Quality / Maintainability
14. SEO
15. Accessibility / Responsive
16. Architecture Integrity
17. Score Table
18. Findings P0 → P3
19. NOT VERIFIED
20. Recommended Fix Priority
21. Final Verdict

# قانون نهایی
هدف پیدا کردن مشکلات واقعی است، نه تأیید rep01.md.
اگر سالم است، ایراد نساز.
اگر مشکل دارد، پنهان نکن.
اگر خارج از Scope است، Bug حساب نکن.
اگر evidence کافی نیست، NOT VERIFIED بنویس.
هیچ اصلاحی انجام نده.

در پایان:
1. Endfiso.md را کامل کن.
2. هیچ کد پروژه را تغییر نده.
3. پاسخ نهایی را بسیار کوتاه بده و فقط نتیجه کلی و تعداد P0/P1/P2/P3 و NOT VERIFIED را اعلام کن.
