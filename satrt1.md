# ⚠️ دستور اجرایی اجباری Agent — قبل از اجرای کل سناریو

> اگر Agent فقط این فایل را بخواند، باید کل مأموریت را بدون سؤال از کاربر و بدون نیاز به دستور مرحله‌ای اجرا کند.

## A) اجرای کامل و مستقل
- این فایل دستور کامل اجراست؛ از کاربر هیچ تأیید، انتخاب، اجازه یا سؤال مرحله‌ای نپرس.
- کل سناریو را از ابتدا تا انتها اجرا کن.
- هیچ Domain یا تست اجباری را حذف نکن.
- اگر چیزی واقعاً قابل اجرا نیست، علت فنی را خودت پیدا کن، آن را BLOCKED یا NOT VERIFIED ثبت کن و ادامه بده.
- بررسی سطحی، چند فایل، grep ساده یا گزارش‌سازی به‌جای تست واقعی ممنوع است.
- هرجا Runtime ممکن است، واقعاً Runtime Test انجام بده.
- هرجا End-to-End ممکن است، Flow را کامل اجرا کن.
- هیچ PASS را با حدس اعلام نکن.

## B) استاندارد دقت
برای هر Domain این زنجیره اجباری است:

**Freshness → Map → Entry Point → Call Chain → Data Flow → Dependency → Security → Runtime → Failure Path → Regression → Evidence → Finding**

برای مسیرهای حساس دو Pass انجام بده:
1. Discovery: ساختار، Entry Point، وابستگی و نقاط حساس.
2. Verification: اثبات با Code / Runtime / DB / API / Test / Graph.

هر Finding باید Evidence داشته باشد. Duplicate و False Positive را قبل از گزارش نهایی دوباره بررسی کن.

اولویت:
**Security → Data Integrity → Auth/Authorization → Financial/Reservation → AI Runtime → Core Runtime → Bugs → Architecture → SEO → Code Quality**

## C) عدم تغییر پروژه
در این مأموریت:
- هیچ Code Fix، Refactor، Feature، Migration، DB Schema Change، UI Redesign یا Architecture Change انجام نده.
- تست را برای PASS شدن دستکاری نکن.
- رفتار سیستم را برای پنهان کردن مشکل تغییر نده.
- فقط فایل گزارش نهایی مجاز به ایجاد/تغییر است.

**هدف Audit کشف وضعیت واقعی فعلی است، نه سبز کردن تست‌ها.**

## D) عدم سؤال از کاربر
در طول مأموریت از کاربر سؤال نکن.

اگر مانعی وجود داشت:
1. Repository را بررسی کن.
2. Runtime و Configuration را بررسی کن.
3. giso-dev را بررسی کن.
4. Graphify و Memory را بررسی کن.
5. راه موجود برای ادامه را خودت پیدا کن.
6. اگر واقعاً غیرممکن بود، BLOCKED با دلیل فنی دقیق ثبت کن و ادامه سناریو را اجرا کن.

## E) Memory / Graphify / giso-dev
قبل از Domain Testing:
- giso-dev را طبق منابع همین فایل بررسی کن.
- graphify-out را برای Map و Dependency Navigation استفاده کن.
- project_memory/letta را بررسی کن.
- Branch و HEAD واقعی را ثبت کن.
- Freshness را مشخص کن.
- اگر Memory یا Graphify مربوط به Commit دیگری است، STALE ثبت کن.
- **Code فعلی مرجع وضعیت واقعی سیستم است.**
- Memory برای Intent/Architecture و Graphify برای Navigation است، نه اثبات وضعیت فعلی.

## F) تست عمیق بخش‌های حساس
با بالاترین دقت این موارد را بررسی کن:

### Security
Auth bypass، Authorization bypass، IDOR، User A → User B، privilege escalation، file ownership، sensitive result access، path traversal، SQL injection، XSS، CSRF، unsafe redirect، arbitrary file read/write، upload abuse، secret exposure، sensitive API exposure، rate limit و error leakage.

### Reservation / Financial
Wrong service/user/center، duplicate، race condition، occupied slot، closed day، inactive/expired center، invalid service، invalid final_design_id، id=0، success-on-failure، duplicate callback/payment، idempotency، negative balance، double spending، refund و authorization.

### Buti AI / AI Runtime
Provider، model، task assignment، Vision، Text، Image، inpainting، mask، composite، outside-mask protection، final result، retry، ownership، credits، fallback، failover و اینکه fallback اشتباهاً به‌عنوان AI success گزارش نشود.

### Data Integrity
برای Flowهای حساس این مسیر را trace کن:

**Input → Validation → Transformation → DB → External Service → DB → Output**

## G) Credential تست Cloudflare
اگر برای اثبات واقعی AI/Cloudflare نیاز به Credential داشتی، فقط از Credentialی که کاربر خارج از Repository در اختیار تست قرار داده استفاده کن.

**مقدار Credential را در این فایل، Code، Comment، Log، Screenshot، Report یا Git Commit ننویس.**

Credential فقط به‌صورت Environment Variable/Secret Runtime مصرف شود.

بعد از تست:
- Secret را از محیط تست پاک/Unset کن.
- با git status و git diff و ابزار مناسب بررسی کن که هیچ Secret وارد Repository نشده باشد.
- مقدار Secret را هرگز در گزارش نهایی نمایش نده.

اگر تست بدون Credential ممکن است، ابتدا همان را انجام بده.

## H) معیار اتمام
مأموریت فقط وقتی تمام است که:
- Project Map کامل ساخته شده باشد.
- همه Domainهای سناریو بررسی شده باشند.
- Minimum Testهای هر Domain اجرا شده باشند.
- Runtime تا حد امکان واقعی تست شده باشد.
- Security، Data Integrity، Regression و SEO بررسی شده باشند.
- Graphify + giso-dev + Memory استفاده شده باشند.
- ۱۰ مشکل قبلی دوباره Verify شده باشند.
- Critical/High Findings دوباره Re-test شده باشند.
- Final Report ساخته و در همان Branch Commit شده باشد.
- هیچ Secret وارد Repository نشده باشد.
- هیچ Code Fix انجام نشده باشد.

**تا قبل از این وضعیت، مأموریت را تمام‌شده اعلام نکن.**

---

# SATRT1 — سناریوی جامع تست و Audit دو ساعته کل Giso4

## 0) هدف اصلی
این فایل سناریوی جامع تست ۲ ساعته کل پروژه Giso4 است؛ نه فقط تست ۱۰ اصلاحیه قبلی.

هدف این است که Agent در حدود ۲ ساعت، پروژه را مثل QA/Code Auditor ارشد از ابتدا تا انتها بررسی کند و مشخص کند:
- ساختار و startup سالم است یا نه.
- هر بخش اصلی واقعاً کار می‌کند یا فقط در کد وجود دارد.
- اتصال بین بخش‌ها درست است یا نه.
- Bug، Security، Permission، Data Integrity، AI، SEO، Runtime، Error Handling، Regression و Code/Architecture مشکل دارند یا نه.
- هر مشکل دقیقاً با عنوان، محل، علت، اثر، شدت و روش رفع گزارش شود.
- برای هر Domain گزارش مستقل و در پایان یک گزارش جامع ساخته شود.

**Repository:** `uname1370-create/giso4`  
**Branch:** `arena/09bed010-giso4`

## 1) قانون قطعی: فقط Audit/Test
در این اجرای ۲ ساعته:
- هیچ کد پروژه را اصلاح نکن.
- refactor، feature، migration یا architecture change انجام نده.
- UI را redesign نکن.
- bug را fix نکن؛ فقط اثبات و گزارش کن.
- فقط فایل گزارش را بساز.
- هیچ PASS را بر اساس حدس اعلام نکن.
- برای داده موقت فقط Test DB/Test Environment استفاده کن.
- **Code Truth بر همه چیز مقدم است.**

## 2) منابع اجباری
روش بررسی را از کل `giso-dev/` بگیر، مخصوصاً:
- `giso-dev/SKILL.md`
- `giso-dev/references/phase-0-freshness.md`
- `giso-dev/references/discovery-method.md`
- `giso-dev/references/patterns-extraction.md`
- `giso-dev/references/council-checklists.md`
- `giso-dev/references/test-regression.md`
- `giso-dev/references/stale-handling.md`

برای **هر Domain** این Scale را اجرا کن:
> Freshness → Section Identification → Pattern/Architecture → Dependency/Impact → Graph/Memory/Docs → Architect → Domain → Security → Regression → Runtime/Test → Finding

از `graphify-out/` و مخصوصاً `GRAPH_REPORT.md`, `graph.json`, communityها، God Nodes، dependencyها و test hubs برای ساخت نقشه تست استفاده کن. Graphify فقط navigation است؛ اگر Built-from commit با HEAD فرق دارد STALE اعلام کن و Code Truth را ملاک قرار بده.

## 3) مرحله صفر — Freshness
ثبت کن:
- branch
- HEAD
- working tree
- Python/runtime
- dependencies
- test framework
- DB
- external AI/provider availability
- Graph freshness
- Guide freshness
- Project Memory freshness

خروجی:
```
HEAD=
Branch=
WorkingTree=
Graph=
Docs=
Memory=
Runtime=
```

اگر Graph/Memory stale بود، تست را متوقف نکن؛ ساختار را از code دوباره استخراج کن.

## 4) ساخت نقشه کامل پروژه
قبل از flow test، کل tree را به Domain/Subsystem تقسیم کن. حداقل این‌ها را پیدا کن و اگر Domain دیگری وجود داشت اضافه کن:

### Core / Runtime
`main.py`, `giso/app.py`, `giso/base.py`, DB/core helpers، config/env، auth/session، models، startup.

### Authentication / Authorization
login/register، Flask-Login، roles، admin/super admin، permission helpers، ownership، CSRF، sensitive routes.

### User Panel
dashboard، profile، analyses/history، reservations، wallet، messages/notifications، marketplace/shop، center interactions.

### Admin / Super Admin
dashboard، users، AI management، Beauty Centers، analyses، wallet/finance، settings، notifications، reports، marketplace/shop، permissions.

### Beauty Centers
registration، review/approval، publication، detail، services، pricing، portfolio/images، reservations، owner dashboard، messages، promotions، Mirror linkage.

### Reservation
center، service، date/time، availability، collision، status، ownership، cancellation/management، Mirror linkage.

### Buti AI / Mirror
eyebrow، nail، hair_color، lip_shading، upload، validation، analysis، model/style، provider، image generation، mask/composite، final design، retry، history، center recommendation، reservation handoff.

### AI Provider / AI Runtime
provider registry/DB، startup sync، health، failover، credits، model selection، Vision، text، image generation، Cloudflare/proxy/external providers، admin assignment، task assignment.

### Analysis
hair/skin/other analysis routes، result generation، validation، history، AI dependency، reports.

### Marketplace / Shop / Hair Sale
products، inventory، orders، payment، notifications، seller/owner/admin، user history.

### Wallet / Payment / Financial
balance، credit، spend، refund، idempotency، callbacks، invoices، financial integrity.

### Notifications / Messaging
site، bot، center، admin notifications، duplicate prevention.

### Bot Integration
Giso Bale bot، shared DB/config، handlers، admin/user actions، notification bridges.

### SEO / Public Web
public routes، sitemap، robots، canonical، metadata، structured data، indexability، public centers/services، 404/redirect، duplicate URLs، internal links.

### Deployment / Operations
services، nginx، ports، startup، environment، backup/restore، logs، health، recovery.

## 5) Scale ثابت برای تک‌تک Domainها
برای **هر Domain/Section**:

### S1 — Structure
Blueprint، routes، services، schema، templates، static، tests و فایل‌های واقعی را inventory کن.

### S2 — Entry Point
از نقطه ورود واقعی user/admin/bot شروع کن.

### S3 — End-to-End
هر جا ممکن است:
`UI → Route → Auth → Service → DB → AI/External → Result → UI/Notification`

### S4 — Data Integrity
ID، relations، ownership، status، duplicates، null/empty، transaction، rollback، idempotency، stale records.

### S5 — Security
Authentication، Authorization، IDOR، ownership، privilege escalation، CSRF، XSS، SQL injection، path traversal، upload abuse، unsafe redirect، secret leakage، sensitive data exposure، rate limit، error leakage.

### S6 — Runtime/Error
startup، exception، timeout، missing dependency، external failure، DB failure، malformed input، retry/fallback، user-facing error.

### S7 — Architecture/Code
Reuse > Extend > New، duplicate logic، parallel systems، wrong layer dependency، cycles، direct DB misuse، dead/unreachable code، inconsistent source of truth، unsafe global state، swallowed exceptions، hard-coded config.

### S8 — SEO
اگر public است: indexability، canonical، title/meta، robots، sitemap، structured data، duplicate URLs، status/redirect، internal links.

### S9 — Regression
sibling features و shared symbols را تست کن.

### S10 — Verdict
PASS / PASS WITH LIMITATIONS / PARTIAL / FAIL / BLOCKED

## 6) Startup و اجرای سیستم
بررسی کن:
- importها
- app creation
- DB connection
- table initialization
- blueprint registration
- startup exceptions
- config/env
- health endpoints
- component contracts

برای تست، در صورت امکان app را in-process اجرا کن؛ `main.py` را فقط برای تستی اجرا نکن که botهای واقعی را spawn کند.

## 7) Auth / Permission
سناریوهای اجباری:
- Guest → public/private/direct URL
- User A → own resources
- User B → تلاش برای resource A
- Admin → admin-only / user-only
- Super Admin → super-only
- IDOR، role escalation، forged IDs، CSRF، unsafe redirect

## 8) User Panel
حداقل flow:
`Register/Login → Dashboard → Profile → Analysis → Mirror → History → Reservation → Wallet → Notifications`
برای هر مرحله route/auth/DB/ownership/state/error/regression را بررسی کن.

## 9) Beauty Center
Flow:
`Register → Pending → Review → Publish → Public Detail → Services → Pricing → Portfolio → Reservation → Owner Dashboard`

تست:
- ثبت/validation
- approval/publish/pause
- expiry
- services/inactive services
- images
- public detail
- reservation
- owner/admin/user permissions
- Mirror linkage

تعارض بین `beauty_center_services`, `services_json` یا هر source دیگر را گزارش کن.

## 10) Reservation
اجباری:
1. success
2. occupied slot
3. inactive/invalid service
4. inactive center
5. expired listing
6. closed day
7. duplicate submit
8. User B vs User A
9. invalid `final_design_id`
10. wrong service
11. concurrent/duplicate booking
12. JSON
13. browser redirect

خصوصاً `create_reservation() == 0` نباید success شود.

## 11) Buti AI / Mirror
برای هر چهار سرویس جداگانه:
- eyebrow
- nail
- hair_color
- lip_shading

Flow:
`Landing → Selection → Upload → Validate → Analysis → Style/Model → AI → Final → Retry → History → Center → Reservation`

### Eyebrow
upload، photo validation، detection، mask، generation، inpainting، composite، outside-mask protection، final image، retry.

### Generic
بررسی کن Vision واقعاً اجرا می‌شود، خروجی analysis وارد generation می‌شود، prompt/service_key درست است و final متعلق به همان service است.

## 12) AI Provider / Runtime
کل chain:
`Super Admin UI → Route → Handler → Provider DB → Startup Sync → Provider Selection → Model → Task → Vision/Text/Image → Credits → Failover → Result`

تست:
- list/add/edit/disable/delete
- persistence
- startup sync
- canonical/duplicates
- API key/base URL
- health
- text
- Vision
- image
- failover/circuit breaker
- credits/refund
- ordering
- task assignment

**Text health به‌تنهایی اثبات Vision/Image نیست.**

## 13) Analysis
تمام analysisها را پیدا کن و route/input/AI/schema/output/validator/history/ownership/failure را بررسی کن. Prompt، schema و validator باید واقعاً سازگار باشند.

## 14) Marketplace / Shop / Hair Sale
برای هر زیرسیستم browse/detail/order/inventory/payment/order-state/notification/admin/user-history/duplicate/unauthorized را بررسی کن.

## 15) Wallet / Payment
balance، credit، debit، refund، payment، callback، invoice، duplicate callback، idempotency، negative balance، concurrent spend، authorization، audit trail.

## 16) Notifications / Messaging
event، recipient، permission، duplicate، failure/retry، read/unread، isolation، admin، center، bot. اگر event چند بار emit می‌شود، علت را trace کن.

## 17) Bot / Site / Giso Integration
بدون تغییر:
- `bot_edu/`
- `web/`
- `giso/bot.py`
- `main.py`

قراردادهای integration، shared config/DB، identity mapping، admin mapping، notification bridge، callbacks، site↔bot data flow و startup dependency را بررسی کن. مشکل خارج از Giso را گزارش کن، اصلاح نکن.

## 18) SEO Audit
برای تمام public surface:
- sitemap
- robots
- canonical
- status/redirect/404
- trailing slash
- duplicate URLs
- index/noindex
- title/meta
- headings
- alt
- internal links/breadcrumbs
- structured data
- public center/service pages
- expired/inactive center indexability
- public/private leakage

SEO را جدا از Security گزارش کن.

## 19) Security Audit عمیق
### P0/P1
auth bypass، authz bypass، IDOR، privilege escalation، arbitrary file read/write، RCE، secret exposure، financial manipulation.

### P1/P2
CSRF، XSS، SQL injection، path traversal، unsafe upload، sensitive API exposure.

### P2/P3
error leakage، weak validation، missing rate limit، insecure logging، predictable sensitive IDs.

هر finding:
**عنوان دقیق + path + function/route/class + exploit condition + اثر + روش رفع**

## 20) Bug / Logic Audit
کل پروژه را برای:
wrong fallback، silent failure، success-on-failure، wrong user/resource، stale state، duplicate record، race condition، missing transaction، swallowed exception، dead route، unreachable branch، wrong redirect، inconsistent parameter، wrong service، wrong DB source، broken history، missing validation
بررسی کن.

## 21) Code / Architecture Audit
با giso-dev بررسی:
- domain boundaries
- duplicated systems/helpers
- parallel implementations
- shared DB misuse
- dependency direction/cycles
- God nodes
- overly coupled functions
- giant routes
- dead code
- hard-coded values
- hidden side effects
- inconsistent naming
- missing/outdated tests

وجود کد زیاد به‌تنهایی finding نیست؛ فقط مشکل فنی اثبات‌شده را گزارش کن.

## 22) Graphify به‌عنوان نقشه تست
برای هر Domain:
1. community را پیدا کن.
2. hub/God Nodeها را ثبت کن.
3. ورودی/خروجی را trace کن.
4. shared symbols را پیدا کن.
5. cross-domain dependencies را ثبت کن.
6. testهای مرتبط را پیدا کن.
7. همان dependencyها را در regression تست کن.

اگر Domain به `get_giso_db_conn()`, `create_app()`, `User`, `ai_runtime`, `notifications` یا سایر God Nodeها وصل است، اثر آن را روی siblingها بررسی کن.

## 23) قالب گزارش هر Domain
برای هر قسمت پروژه یک بخش مستقل:

### [Domain]
**Scope:** فایل‌ها/routes/services  
**Entry Points:**  
**Flow:**  
**Runtime Tests:**  
**Security:**  
**Bugs:**  
**SEO:**  
**Code/Architecture:**  
**Regression:**  

| ID | Severity | عنوان دقیق | محل | مشکل چیست | اثر | روش رفع |
|---|---|---|---|---|---|---|

**Verdict:** PASS / PASS WITH LIMITATIONS / PARTIAL / FAIL / BLOCKED

## 24) Severity
- **P0/Critical:** امنیت بحرانی، RCE، داده حساس گسترده، financial corruption جدی.
- **P1/High:** security bypass، IDOR، financial/reservation integrity، data corruption، core flow broken.
- **P2/Medium:** bug/regression/state/SEO مهم.
- **P3/Low:** UX، validation ضعیف، cleanup، minor SEO/code quality.

## 25) برنامه زمانی دقیق ۲ ساعت
**0–10 دقیقه:** Freshness + tree map + Graphify + runtime.  
**10–25:** Core + Auth + Permissions + DB.  
**25–40:** User Panel + Public + SEO.  
**40–60:** Beauty Centers + Services + Pricing.  
**60–75:** Reservation + Ownership + Data Integrity.  
**75–100:** Buti AI چهار سرویس + AI Runtime.  
**100–112:** Analysis + Marketplace/Shop/Hair Sale + Wallet/Payment.  
**112–120:** Notifications + Bot/Site integration + global Security/Regression + report.

روی یک فایل گیر نکن. اگر یک Domain کامل در زمان موجود نشد، آن را PARTIAL/BLOCKED ثبت کن؛ از وقت Domainهای بعدی کم نکن.

## 26) حداقل تست اجباری هر Domain
حتی با کمبود وقت:
1. Happy Path
2. Invalid Input
3. Unauthorized Access
4. Ownership/Permission
5. Failure/Exception
6. Data Integrity
7. Regression

Auth/Reservation/Wallet/AI/Upload باید عمیق‌تر تست شوند.

## 27) تعریف نتیجه
- **CODE VERIFIED:** code path بررسی شده، runtime نشده.
- **RUNTIME VERIFIED:** واقعاً اجرا و evidence ثبت شده.
- **PASS:** معیار واقعاً تأیید شده.
- **PARTIAL:** بخشی سالم/بخشی مشکل‌دار.
- **BLOCKED:** محیط اجازه تست نداده.
- **FAIL:** مشکل واقعی با evidence.

BLOCKED هرگز PASS نیست.

## 28) ۱۰ اصلاحیه قبلی هم باید جداگانه verify شوند
این ۱۰ مورد در همین تست جامع دوباره بررسی شوند:
1. Final Design/Mirror ownership
2. reservation `id=0`
3. Mirror → exact service ID
4. Super Admin Beauty Center tabs
5. listing expiration consistency
6. service source consistency
7. exact user history/final design
8. owner Mirror linkage
9. reservation final-design ownership/service validation
10. Project/Memory consistency

برای هرکدام CODE/RUNTIME evidence بده.

## 29) گزارش نهایی اجباری
در همان Branch یک فایل مثل:
`satrt1_full_test_report.md`

بساز و شامل این‌ها کن:
- Executive Summary
- Freshness
- Architecture Map
- Domain-by-Domain Results
- 10 اصلاحیه قبلی
- Security Findings
- Bug/Logic Findings
- SEO Findings
- Code/Architecture Findings
- Runtime Failures
- Regression Results
- Cross-Domain Findings
- Final Verdict

### Exact Fix Plan
برای **هر مشکل**:
1. عنوان
2. Severity
3. فایل
4. function/route/class
5. مشکل دقیق
6. علت
7. اثر
8. روش رفع دقیق
9. چه چیزی نباید تغییر کند
10. تست بعد از رفع

**هیچ fix در این مرحله انجام نده.**

## 30) Final Verdict
یکی از:
- **GREEN:** هیچ P0/P1 و Core flow failure در محدوده تست وجود ندارد.
- **YELLOW:** قابل اجراست ولی مشکلات مشخص باقی است.
- **RED:** P0/P1 یا Core flow شکسته وجود دارد.
- **BLOCKED:** محیط اجازه ارزیابی کافی نداده.

## 31) خروجی نهایی Agent
در پاسخ نهایی فقط:
- Branch
- HEAD
- مدت تست
- تعداد Domainهای بررسی‌شده
- PASS / PARTIAL / FAIL / BLOCKED
- تعداد P0/P1/P2/P3
- ۵ مشکل مهم
- نام و path گزارش
- commit SHA گزارش
- آیا کد پروژه تغییر کرده یا خیر

**کد پروژه نباید تغییر کند؛ فقط گزارش تست ساخته شود.**
