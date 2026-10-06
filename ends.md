# END — سناریوی ممیزی کامل و ریزبینانه Giso4

## مأموریت اصلی

پروژه زیر را **کامل، ریزبینانه و از ابتدا تا انتها** بررسی و تست کن:

Repository: uname1370-create/giso4
Branch: arena/01a0eecf-giso4

هدف این مأموریت پیدا کردن **تمام مشکلات واقعی و مهم پروژه** است؛ نه تأیید گزارش‌های قبلی.

ابتدا ساختار واقعی فعلی Giso4 را کاملاً بشناس، سپس بر اساس همان ساختار کل پروژه را بخش‌به‌بخش بررسی کن و در پایان مسیرهای اصلی را با تست واقعی Runtime/E2E تا جایی که محیط اجازه می‌دهد اجرا کن.

---

# قانون صفر — هیچ تغییر در پروژه

این مأموریت **فقط Audit / Analysis / Testing / Reporting** است.

حق نداری:
- کد پروژه را تغییر دهی
- refactor کنی
- migration بسازی یا تغییر دهی
- dependency نصب/حذف کنی
- معماری را تغییر دهی
- feature جدید بسازی
- bug را fix کنی
- فایل‌های پروژه را برای رفع مشکل تغییر دهی

فقط دو کار نوشتاری مجاز است:

1. همین فایل `ends.md` فقط به‌عنوان سناریوی مأموریت باقی بماند.
2. **پس از پایان کامل بررسی، خودت یک فایل جدید به نام دقیق `Endfiso.md` در همین Repository و همین Branch بساز و گزارش نهایی را فقط داخل آن قرار بده.**

**من از قبل Endfiso.md را نمی‌خواهم. خودت در پایان Audit آن را بساز.**

---

# مرحله 1 — اول ساختار واقعی فعلی را بشناس

قبل از هر تستی، یک Baseline کامل از ساختار فعلی بساز.

بررسی کن:

- entry points
- main application
- Flask/app structure
- blueprints/routes
- services
- models
- database
- migrations
- authentication
- authorization/permissions
- admin
- user panel
- public pages
- Buti AI / Mirror
- Beauty Centers
- Reservation
- Marketplace
- Wallet
- Orders
- Chat
- Reviews
- Hair Sale
- existing analysis
- Bale
- bot_edu
- web
- static
- templates
- shared utilities
- config
- error handling
- tests
- scripts
- background jobs

از اسم فایل یا پوشه نتیجه‌گیری نکن.
در صورت نیاز call chain، dependency و data flow را تا منبع واقعی دنبال کن.

---

# مرحله 2 — Giso-dev را مبنا قرار بده

تمام بررسی را با اصول Giso-dev انجام بده.

ترتیب:

Understand Request
→ Project Freshness
→ Section Identification
→ Pattern & Architecture Analysis
→ Dependency / Impact Analysis
→ Graph / Memory / Docs Check
→ Test Planning
→ Runtime/E2E Verification
→ Regression
→ Final Report

اصول اجباری:

- Code Truth > Graph > Memory > Docs > گزارش قبلی
- Reuse > Extend > New
- Route وجود دارد = Feature اثبات نشده
- Table وجود دارد = Business Flow اثبات نشده
- Graph edge = dependency اثبات نشده
- py_compile = Runtime اثبات نشده
- HTTP 200 = Business Success اثبات نشده

---

# مرحله 3 — Graph / Memory / Documentation

تمام منابع موجود را بررسی کن:

- Graphify / graph
- project_memory
- Letta memory
- GISO_GUIDE.md
- PROJECT_GUIDE.md
- finbuti.md
- rep01.md
- سایر اسناد مرتبط

اما اگر با Code Truth اختلاف داشتند، **Code Truth را مبنا قرار بده**.

برای هر اختلاف مهم ثبت کن:
- چه چیزی در Doc/Graph گفته شده؟
- Code Truth چه می‌گوید؟
- اختلاف چیست؟
- آیا روی نتیجه Audit اثر دارد؟

اگر Graph یا Memory stale است، آن را صریحاً اعلام کن؛ بدون اجازه آن‌ها را refresh نکن.

---

# مرحله 4 — تطبیق Scenario با Code Truth

به‌خصوص `finbuti.md` و `rep01.md` را بررسی کن.

برای هر قابلیت تعیین کن:

- IMPLEMENTED
- PARTIAL
- STATIC ONLY
- NOT VERIFIED
- MISSING
- OUT OF SCOPE
- ARCHITECTURE CONFLICT

هدف تأیید کورکورانه rep01.md نیست.

---

# مرحله 5 — کل پروژه را بخش‌به‌بخش Audit کن

## 5.1 Public / Entry

بررسی:
- Home
- Public pages
- navigation
- links
- 404/500
- templates
- static assets
- loading
- responsive
- RTL
- performance

## 5.2 Authentication / Authorization

بررسی:
- login/logout
- session
- protected routes
- permissions
- role guards
- unauthorized access
- object ownership
- IDOR
- CSRF
- session security

## 5.3 User Panel

بررسی:
- dashboard
- profile
- analyses
- history
- reservations
- beauty centers
- orders
- wallet
- chat
- reviews
- existing user features

## 5.4 Smart Analysis / Buti AI

مسیر واقعی را از ابتدا تا انتها دنبال و تا حد امکان E2E تست کن:

Login
→ Service Selection
→ Model/Style
→ Upload
→ Validation
→ Quality
→ Detection
→ Mask
→ AI Analysis
→ Provider
→ Fallback
→ Generation
→ Output Validation
→ Before/After
→ Final
→ History
→ Beauty Centers
→ Service Matching
→ Reservation
→ Final Design

برای هر مرحله بررسی کن:
- input
- output
- DB state
- session state
- ownership
- permission
- error path
- dependency
- state transition

به‌خصوص بررسی کن آیا موفقیت یک مرحله واقعاً state لازم برای مرحله بعد را ساخته است یا فقط ظاهراً صفحه بعد باز شده.

## 5.5 Beauty Center

بررسی:
- registration
- approval
- publishing
- profile
- services
- service_key
- featured service
- price
- duration
- hours
- gallery
- service-level portfolio
- public page
- ownership
- reservation
- chat
- reviews
- promotions
- analytics

## 5.6 Reservation

بررسی واقعی:
- center
- user
- service
- service_key
- selected style
- final_design_id
- price snapshot
- duration snapshot
- conflict/overlap
- duplicate booking
- invalid booking
- authorization
- ownership
- status transitions
- cancellation
- consistency with existing reservation system

**به دنبال ساخت یا وجود Reservation system دوم باش و اگر پیدا شد دقیق گزارش کن.**

## 5.7 Admin

بررسی:
- dashboard
- services
- portfolio
- reservations
- analytics
- filters
- permissions
- CSRF
- ownership
- destructive actions
- invalid IDs
- pagination/limits

## 5.8 Existing / Legacy / Regression

بررسی regression برای:
- Wallet
- Marketplace
- Orders
- Chat
- Reviews
- Hair Sale
- existing analysis
- Beauty Center existing paths
- Bale-related paths در صورت فعال بودن
- bot_edu
- web
- main launcher

اگر بخشی خارج از Scope است، بی‌دلیل feature test جدید نساز؛ فقط وضعیت آن را دقیق ثبت کن.

---

# مرحله 6 — نوع تست باید متناسب با نوع قابلیت باشد

## Backend
unit/integration، DB، transaction، error path، state transition.

## Business Flow
تست واقعی از ابتدا تا انتها.

## Browser/UI
اگر محیط اجرا اجازه می‌دهد:
- navigation
- form
- validation
- loading
- error
- success
- mobile
- tablet
- desktop
- RTL
- console errors
- broken assets

## Security
- auth bypass
- authorization bypass
- IDOR
- CSRF
- upload security
- path traversal
- injection
- XSS
- secret leakage
- sensitive data leakage
- unsafe errors

## Database
- schema
- relationships
- constraints
- duplicate data
- transactions
- migration safety
- data preservation

---

# مرحله 7 — Performance / Optimization

برای هر بخش بررسی کن:
- N+1
- repeated DB queries
- unnecessary queries
- missing pagination
- expensive image processing
- AI latency
- external provider bottleneck
- caching
- unnecessary computation
- heavy assets
- frontend loading

اگر measurement واقعی نداری، ادعای قطعی سرعت نکن.
در این حالت بنویس:
**NOT VERIFIED — measurement کافی وجود ندارد**
یا:
**RISK — از Code Truth مشاهده شد**

---

# مرحله 8 — Quality / Maintainability

بررسی:
- duplicate logic
- duplicate business rules
- circular dependency
- dead/orphan code
- unclear ownership
- hidden coupling
- fragile error handling
- inconsistent naming
- oversized files
- technical debt

بزرگ بودن فایل به‌تنهایی Bug نیست.

---

# مرحله 9 — SEO

فقط صفحات Public مرتبط را بررسی کن:
- title
- meta description
- canonical
- heading structure
- semantic HTML
- crawlability
- internal links
- robots
- sitemap
- Open Graph در صورت نیاز
- duplicate content
- URL quality
- image alt
- performance impact

---

# مرحله 10 — Accessibility / Responsive

برای User-facing/Public:
- RTL
- keyboard
- labels
- focus
- contrast
- semantic HTML
- mobile
- tablet
- desktop
- overflow
- touch target
- clear validation/error messages

---

# مرحله 11 — امتیاز هر بخش

هر بخش اصلی از 0 تا 10 امتیاز بگیرد.

بر اساس نوع بخش این موارد را ارزیابی کن:
- Functionality / Correctness
- Architecture
- Security
- Performance
- Quality / Maintainability
- UX / Responsive
- SEO در صورت relevance

اگر شواهد کافی برای امتیاز وجود ندارد، به زور عدد نده و **NOT ENOUGH EVIDENCE** ثبت کن.

---

# مرحله 12 — Severity

P0 = Critical
- data loss
- security breach جدی
- core system failure
- reservation خطرناک/اشتباه
- authorization bypass جدی

P1 = High
- business flow مهم خراب یا unreliable

P2 = Medium
- مشکل واقعی ولی محدود یا قابل دور زدن

P3 = Low
- UI
- maintainability
- SEO جزئی
- polish

---

# مرحله 13 — قانون بسیار سخت‌گیرانه PASS

این موارد به‌تنهایی PASS نیستند:

- Route پیدا شد
- Template وجود دارد
- Import موفق شد
- py_compile موفق شد
- HTTP 200
- test_client فقط status موفق داد
- جدول DB وجود دارد
- Graph edge وجود دارد

اگر فقط این شواهد وجود دارد:
**STATIC ONLY / PARTIAL / NOT VERIFIED**

PASS کامل فقط وقتی ثبت شود که شواهد متناسب با قابلیت وجود داشته باشد.

---

# مرحله 14 — Architecture Integrity

به‌طور خاص بررسی کن:

1. ساختار اصلی Giso حفظ شده؟
2. سیستم موازی ساخته شده؟
3. Service Catalog دوم وجود دارد؟
4. Reservation دوم وجود دارد؟
5. Mirror/Analysis دوم وجود دارد؟
6. Pricing دوم وجود دارد؟
7. duplicate business logic وجود دارد؟
8. restricted zones بی‌دلیل تغییر کرده‌اند؟
9. data preservation رعایت شده؟
10. migrationها additive/idempotent هستند؟
11. چیزی خارج از Scope اضافه شده؟
12. آیا تغییرات اخیر به بخش‌های قدیمی regression داده‌اند؟

---

# مرحله 15 — گزارش نهایی را خودت بساز

**فقط پس از پایان کامل Audit، فایل جدید زیر را خودت در GitHub بساز:**

`Endfiso.md`

این فایل باید در:
- Repository: uname1370-create/giso4
- Branch: arena/01a0eecf-giso4

ساخته شود.

گزارش نهایی را فقط داخل همین فایل قرار بده.

ساختار گزارش:

# Endfiso — Final Giso Audit Report

## 1. Executive Summary
## 2. Branch / HEAD / Commit
## 3. Audit Scope
## 4. Current Architecture Snapshot
## 5. Graph / Memory / Documentation Status
## 6. Scenario Compliance
## 7. Full Project Section-by-Section Audit
## 8. Smart Analysis E2E
## 9. Beauty Center E2E
## 10. Reservation E2E
## 11. Admin E2E
## 12. Regression
## 13. Security Audit
## 14. Performance / Optimization Audit
## 15. Quality / Maintainability
## 16. SEO
## 17. Accessibility / Responsive
## 18. Architecture Integrity
## 19. Score Table
## 20. Findings P0
## 21. Findings P1
## 22. Findings P2
## 23. Findings P3
## 24. NOT VERIFIED
## 25. Recommended Fix Priority
## 26. Final Verdict

برای هر مشکل واقعی دقیقاً بنویس:

### عنوان مشکل
- Section:
- Severity:
- Status:
- Evidence:
- Exact Location:
- Root Cause:
- Impact:
- Recommendation:
- Evidence Type:

Evidence Type:
Runtime E2E / Integration / Unit / Static Code / Graph / Documentation / Not Verified

---

# قانون مهم گزارش

گزارش را با حرف‌های کلی پر نکن.

هر ادعا باید Evidence داشته باشد.

اگر تست نشده:
**NOT VERIFIED**

اگر فقط Code Review:
**STATIC ONLY**

اگر بخشی تست شده:
**PARTIAL**

اگر مسیر واقعی کامل تست شده:
**PASS — E2E**

اگر خطا پیدا شد:
**FAIL**

مشکل واقعی را پنهان نکن.
مشکل خیالی هم نساز.

---

# مهم‌ترین هدف

این Audit باید مشخص کند:

**«اگر همین نسخه فعلی پروژه را تحویل بدهیم، دقیقاً چه مشکلاتی دارد؟»**

نه اینکه:
**«چطور گزارش قبلی را تأیید کنیم؟»**

پس دنبال مشکل واقعی باش، مخصوصاً:
- Bug
- Broken flow
- Wrong state
- Wrong DB relation
- Permission/security issue
- Performance bottleneck
- duplicate architecture
- regression
- SEO issue
- responsive/accessibility issue
- data integrity issue

اما خارج از Scope را Bug حساب نکن.

---

# پایان مأموریت

پس از تکمیل همه بررسی‌ها:

1. فایل `Endfiso.md` را خودت بساز.
2. گزارش کامل را داخل آن بنویس.
3. هیچ فایل دیگری از پروژه را تغییر نده.
4. هیچ Bug را fix نکن.
5. هیچ refactor انجام نده.
6. هیچ معماری جدیدی نساز.
7. در پاسخ نهایی فقط خلاصه بسیار کوتاه بده:
   - تعداد P0
   - تعداد P1
   - تعداد P2
   - تعداد P3
   - تعداد NOT VERIFIED
   - امتیاز کلی
   - مهم‌ترین 3 مشکل
   - لینک/نام فایل گزارش `Endfiso.md`

**مأموریت فقط با ساخته‌شدن و تکمیل واقعی Endfiso.md تمام می‌شود.**
