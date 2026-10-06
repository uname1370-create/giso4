# FINBUTI — سناریوی نهایی Beauty Ecosystem / Buti AI / Beauty Center

تاریخ: 2026-10-07
Branch: arena/01a0eecf-giso4
منابع: rp7.md + rp6.md + rp5.md + rep2.md + rep1.md
Design Skill: 3d site.md
Implementation Skill: giso-dev

## 0. قانون اصلی

این فایل سناریوی نهایی اجرای بخش باقی‌مانده است.
اصل معماری: Reuse > Extend > New
Code Truth بر گزارش و مستندات قدیمی اولویت دارد.
هیچ تغییر خارج از Scope بدون توقف و تأیید مجدد انجام نشود.
هدف: سیستم جدید ساخته نشود؛ فقط اجزای موجود به هم متصل و در صورت نیاز Extend شوند.

## 1. نتیجه بررسی پنج گزارش

### انجام‌شده و سالم
- Buti AI چهار خدمت فعال: eyebrow, nail, hair_color, lip_shading
- برای Nail / Hair Color / Lip: انتخاب خدمت، مدل، آپلود، Quality، Detection/Mask، Analysis، Generation، Validation، Before/After، Consultant، Centers و Reservation متصل و تست‌شده‌اند.
- Eyebrow Baseline کامل است و نباید برای توسعه سرویس‌های جدید دستکاری شود.
- Beauty Center ثبت، تأیید، انتشار، خدمات، قیمت، ساعات، گالری، رزرو، پیام، بازخورد، Promotion و Analytics دارد.
- Reservation از final_design_id، service_key، selected_style و snapshot قیمت/مدت استفاده می‌کند.
- اتصال Mirror به مراکز و رزرو از قبل وجود دارد.
- AI Provider و fallback صادقانه وجود دارد؛ fallback نباید به‌عنوان AI واقعی معرفی شود.

### باقی‌مانده واقعی
P0:
1. اتصال Mirror History به پنل کاربر.
2. تبدیل «آنالیزهای من» به یک صفحه واحد برای نتایج قدیمی و Mirror.
3. تب‌های ابرو، مو، آرایش، ناخن.
4. ساخت منوی «زیبایی من».
5. صفحه عمومی سالن با UX خدمت‌محور و لوکس.

P1:
1. service_key در beauty_center_services.
2. is_featured_service در beauty_center_services.
3. service_key در beauty_center_images.
4. اتصال Portfolio هر خدمت به همان خدمت.
5. مدیریت خدمت‌محور در Admin.
6. مدیریت رزروها در Admin.
7. Analytics همه سرویس‌های Mirror.
9. Bale Mirror Flow در صورت فعال شدن این Scope.

P2 و فعلاً خارج از Scope:
staff table، wishlist، Instagram/Logo مستقل، AI boosting، تصاویر 800+، معماری جدید و بازنویسی Bot.

## 2. معماری نهایی چهار پنل

### Customer
پیشخوان
→ زیبایی من
→ سالن‌های زیبایی
→ نوبت‌های من
→ گفتگوهای من
→ آنالیزهای من

### Owner
مدیریت سالن زیبایی
→ اطلاعات
→ خدمات
→ ساعات
→ نمونه‌کار
→ پیام‌ها
→ رزروها
→ آمار
→ وضعیت انتشار
→ Promotion/Featured در صورت فعال بودن

### Admin
مدیریت مراکز
→ درخواست‌ها
→ منتشرشده
→ متوقف
→ خدمات
→ نمونه‌کار
→ رزروها
→ بازخورد
→ تبلیغات
→ Analytics
→ Mirror Demand


## 3. پنل کاربر — زیبایی من

منوی پیشنهادی نهایی:
- پیشخوان
- زیبایی من
  - سالن‌های زیبایی
  - نوبت‌های من
  - گفتگوهای من
  - آنالیزهای من
- مدیریت سالن زیبایی، فقط برای مالک سالن
- فروش مو
- خریدها / بازارچه
- کیف پول
- پیام‌ها و پشتیبانی
- پروفایل
- دستیار هوشمند، در صورت فعال بودن

مدیریت سالن زیبایی باید از زیبایی من جدا باشد؛ زیرا مالک سالن هم‌زمان Customer نیز هست.

فایل‌های مسئول:
giso/panel_user/permissions.py
giso/panel_user/routes.py
giso/panel_user/modules/analyses.py
giso/panel_user/templates/user_modules/analyses.html
giso/panel_user/templates/user_layout.html

## 4. آنالیزهای من — سناریوی نهایی

Route اصلی:
 /dashboard/analyses

یک صفحه واحد؛ سیستم Analysis جدید دیگری ساخته نشود.

تب‌ها:
[ابرو] [مو] [آرایش] [ناخن]

Mapping:
- ابرو = buti_ai_final_designs با service_type=eyebrow
- مو = Analysis قدیمی type=hair + Mirror hair_color
- آرایش = lip_shading و محل توسعه آینده makeup
- ناخن = Mirror nail
- داده قدیمی پوست حذف نشود؛ در صورت نیاز به‌صورت Legacy داخل همان تجربه نمایش داده شود.

کارت نتیجه:
- تصویر Before
- تصویر After
- نام خدمت
- مدل انتخابی
- تاریخ
- خلاصه تحلیل
- وضعیت AI
- مشاهده نتیجه
- رزرو همین خدمت

اگر final image وجود نداشت، کارت باید graceful fallback داشته باشد و نباید تصویر جعلی تولید شود.

اولویت: Extend analyses.py و analyses.html.
mirror.py فقط در صورتی ساخته شود که پس از Audit مشخص شود منطق History واقعاً باعث سنگینی analyses.py می‌شود؛ در غیر این صورت ماژول موازی ساخته نشود.

## 5. مسیر اصلی Customer

### بدون Mirror
سالن‌های زیبایی
→ فیلتر خدمت/شهر
→ صفحه سالن
→ خدمات
→ انتخاب خدمت
→ قیمت + مدت
→ نمونه‌کار
→ اعتماد/امتیاز
→ ساعات/آدرس
→ گفتگو یا رزرو
→ پیگیری

### با Mirror
Mirror
→ انتخاب ابرو/مو/آرایش/ناخن
→ مدل
→ Upload
→ Quality
→ Detection
→ Analysis
→ Generation
→ Validation
→ Before/After
→ «این خدمت را می‌خواهم»
→ سالن‌های همان service_key
→ صفحه سالن
→ همان خدمت
→ نمونه‌کار + قیمت
→ رزرو
→ final_design_id + service_key + selected_style
→ پیگیری

## 6. صفحه عمومی آگهی سالن — مهم‌ترین طراحی

صفحه نباید فقط صفحه اطلاعات تماس باشد.
باید یک صفحه معرفی برند + اعتماد + خدمات + نمونه‌کار + قیمت + رزرو باشد.

ساختار:
Hero
→ معرفی سالن
→ خدمات
→ خدمت انتخاب‌شده
→ نمونه‌کار
→ نظرات/اعتماد
→ ساعات و موقعیت
→ گفتگو / رزرو

Hero:
- تصویر اصلی
- نام سالن
- شهر/منطقه
- امتیاز
- تأیید گیسو در صورت واقعی بودن
- توضیح کوتاه
- CTA اصلی رزرو
- CTA دوم گفتگو

## 7. طراحی با 3d site.md

برای صفحه سالن، Agent باید 3d site.md را Skill طراحی بداند، نه یک متن تزئینی.

ترتیب تصمیم:
Understand
→ Experience Architecture
→ Art Direction
→ Performance-aware Design
→ Technology
→ Build
→ Run
→ Inspect
→ Measure
→ Audit
→ Optimize
→ Verify
→ Regression
→ Deliver

اولویت طراحی:
1. Visual quality
2. Art direction
3. UX
4. Persian/RTL
5. Technical correctness
6. Performance
7. Responsive
8. Accessibility
9. SEO
10. Security/maintainability

اصل کلیدی:
Maximum perceived quality per unit of technical cost

یعنی ظاهر بسیار لوکس، اما بدون 3D یا JavaScript سنگین غیرضروری.

3D فقط زمانی مجاز است که ارزش بصری واقعی ایجاد کند.
اگر CSS/SVG/تصویر همان نتیجه را ارزان‌تر و سریع‌تر می‌دهد، همان راه انتخاب شود.

## 8. Art Direction صفحه سالن

Agent باید Creative Direction مستقل اما هماهنگ با Giso تعیین کند:
- مینیمال
- لوکس
- فضای تنفس
- hierarchy روشن
- typography فارسی حرفه‌ای
- تصویر قوی
- motion محدود و هدفمند
- CTA واضح
- بدون شلوغی

3D در صورت استفاده:
- selective
- سبک
- progressive enhancement
- mobile fallback
- reduced-motion
- بدون وابستگی عملکرد اصلی به 3D

## 9. Service Cards

بخش «خدمات سالن» قلب صفحه است.

هر کارت:
- icon
- نام خدمت
- category
- توضیح
- duration
- price
- discount در صورت واقعی بودن
- Featured در صورت واقعی بودن
- CTA

خدمت انتخاب‌شده باید به:
Portfolio همان خدمت
+
Price همان خدمت
+
Reservation همان خدمت
متصل باشد.

نمونه:
ابرو
→ قیمت
→ مدت
→ نمونه‌کار ابرو
→ رزرو ابرو

## 10. Service-Level Advertisement

مدل نهایی آگهی:
Center
+
Service Offers

نه فقط:
Center Profile

مثلاً:
سالن X
[ابرو] [مو] [آرایش] [ناخن]

انتخاب ابرو:
قیمت...
مدت...
توضیح...
نمونه‌کار ابرو...
[رزرو ابرو]

این مدل مستقیماً با Mirror service_key هماهنگ است.

## 11. Portfolio

وضعیت فعلی: تصاویر عمومی‌اند و service_key ندارند.

P1:
افزودن service_key به beauty_center_images.

رفتار:
- service_key مشخص = نمونه‌کار همان خدمت
- service_key خالی = تصویر عمومی

هیچ تصویر قدیمی حذف نشود.

در Owner:
آپلود تصویر + انتخاب خدمت اختیاری.

در Public:
انتخاب خدمت → اولویت نمایش نمونه‌کار همان خدمت.

## 12. Services / Pricing

beauty_center_services منبع اصلی خدمات باقی می‌ماند.

P1:
- service_key
- is_featured_service
فیلدهای موجود حفظ شوند:
- name
- category
- description
- duration
- price_min
- price_max
- is_active
- sort_order

Reservation همچنان snapshot قیمت، نام و مدت را ذخیره کند.

هیچ سیستم Pricing جدید ساخته نشود.

## 13. Owner Panel

ساختار موجود حفظ شود:
1. اطلاعات سالن
2. خدمات
3. ساعات کاری
4. تصاویر/نمونه‌کار
5. پیام‌ها
6. رزروها
7. آمار
8. وضعیت انتشار

تکمیل:
- service_key هنگام تعریف خدمت
- Featured برای خدمت
- service_key هنگام آپلود نمونه‌کار
- فیلتر نمونه‌کار بر اساس خدمت
- حفظ همه Guardهای مالکیت و CSRF

## 14. Admin Panel

P0 فعلی دست‌نخورده:
requests
published
paused
promotions
feedback
dashboard
settings
status
feature
discount

P1:
- مدیریت خدمات بر اساس center/service_key/is_active/featured
- مدیریت Portfolio بر اساس center/service_key
- مدیریت رزرو بر اساس center/service/status/date
- Mirror analytics برای eyebrow/nail/hair_color/lip_shading
- demand و interest و final_design count
- moderation بدون دسترسی غیرمجاز

## 15. Bale Mirror

اگر این Phase فعال شود:
Bale
→ انتخاب خدمت
→ مدل
→ عکس
→ Quality
→ Analysis
→ Result
→ Centers
→ Reservation

Bale فقط Adapter باشد.
منطق Mirror دوباره نوشته نشود.

Reuse:
service_catalog
generic_service
service_image_generation
beauty_centers
reservations

giso/bot.py نباید refactor یا split شود.

## 16. Database Rules

Migration فقط additive و idempotent:
PRAGMA table_info
→ اگر ستون نیست ALTER TABLE ADD COLUMN
→ index در صورت نیاز

هیچ داده‌ای حذف یا بازنویسی نشود.

Migration احتمالی:
beauty_center_services:
service_key
is_featured_service

beauty_center_images:
service_key

promotion/discount:
service_id یا service_key فقط اگر UI و logic واقعاً آن را مصرف کنند.

اگر Code Truth نشان داد ستونی از قبل وجود دارد، migration تکراری ممنوع.

## 17. File Ownership

Beauty Center:
giso/beauty_centers/
giso/beauty_centers/pricing/
giso/beauty_centers/reservations/

Mirror:
giso/buti_ai/
giso/buti_ai/eyebrow/
giso/buti_ai/nail/
giso/buti_ai/hair_color/
giso/buti_ai/lip/

User Panel:
giso/panel_user/

Admin:
giso/panel/

Bale:
فقط handler/state مورد نیاز؛ بدون refactor کلی.

هر منطق در پوشه مسئول خودش قرار گیرد.

## 18. ممنوعیت‌ها

- Beauty Center جدید
- Reservation جدید
- Mirror جدید
- Analysis موازی جدید
- Service Catalog دوم
- Pricing دوم
- duplicate center matching
- duplicate reservation logic
- تغییر Eyebrow Baseline
- بازنویسی bot.py
- تغییر bot_edu
- تغییر web
- تغییر main.py
- تغییر Graphify برای Feature
- hard-code API key
- معرفی fallback به‌عنوان AI واقعی
- فایل جدید بدون دلیل معماری و Scope Lock

## 19. Security

بررسی و حفظ:
- authentication
- authorization
- owner checks
- CSRF
- path traversal protection
- safe filename
- MIME/type validation
- image byte/pixel limits
- XSS protection
- parameterized SQL
- final_design ownership
- service_key whitelist
- secret خارج از source

## 20. Performance

صفحه سالن:
- Hero image بهینه
- lazy loading تصاویر غیر Hero
- responsive images
- جلوگیری از N+1 query
- JavaScript حداقلی
- CSS animation محدود
- 3D فقط selective
- mobile fallback
- reduced motion
- graceful loading/error/empty states

هدف:
لوکس بودن بدون هزینه فنی بی‌دلیل.

## 21. Accessibility / SEO

Accessibility:
- RTL واقعی
- semantic headings
- keyboard
- focus
- contrast
- alt
- aria labels
- reduced motion
- touch friendly
- hover تنها روش تعامل نباشد

SEO:
- title یکتا
- meta description
- canonical
- semantic content
- service/location text واقعی
- crawlable content
- structured data فقط با داده واقعی

## 22. مراحل اجرای Agent

### Phase 0 — Freshness Audit
قبل از تغییر:
- branch HEAD
- status/diff
- rp1 تا rp7
- 3d site.md
- فایل‌های واقعی

اگر گزارش و Code اختلاف داشت:
Code Truth.

### Phase 1 — P0 User Panel
- زیبایی من
- آنالیزهای من
- چهار تب
- Mirror History
- old Analysis + Mirror
- لینک مشاهده
- لینک رزرو

### Phase 2 — P0 Public Beauty Center Design
- Hero
- Services
- Service selection
- Pricing
- Portfolio
- Trust
- CTA
- responsive
- luxury art direction طبق 3d site.md

### Phase 3 — P1 Service-Level Data
فقط migration لازم:
service_key
featured service
portfolio mapping
و فقط در صورت اثبات نیاز promotion fields.

### Phase 4 — P1 Owner/Admin
- service management
- portfolio management
- reservation management
- Mirror analytics

### Phase 5 — P1 Bale
فقط اگر Scope فعال باشد.

### Phase 6 — QA
Run
→ Inspect
→ Test
→ Security
→ Performance
→ Accessibility
→ SEO
→ Responsive
→ Regression

## 23. Test Matrix

Mirror:
- eyebrow regression
- nail
- hair_color
- lip_shading
- style propagation
- upload
- quality
- mask
- provider fallback
- validation
- final
- consultant
- centers
- reservation

User Panel:
- customer
- owner/customer
- unauthenticated
- old Analysis
- Mirror history
- four tabs
- empty state
- missing final image
- reservation

Beauty Center:
- list
- filter
- detail
- service
- price
- portfolio
- chat
- reservation
- mobile

Owner:
- add/edit service
- service_key
- featured
- upload portfolio
- linked portfolio
- reservation
- messages

Admin:
- approval
- services
- portfolio
- reservations
- Mirror analytics

Regression:
hair_sale
marketplace
orders
wallet
chats
profile
reviews
overview
existing Beauty Center
existing reservations
existing Mirror
existing Admin
existing Bale beauty-center features

## 24. Visual QA صفحه سالن

Agent باید صفحه واقعی را Run کند و فقط source code را قضاوت نکند.

بررسی:
- desktop
- mobile
- Hero
- services
- typography
- spacing
- image crop
- portfolio
- CTA
- motion
- loading
- empty/error
- reduced motion
- keyboard
- reservation flow

سؤال نهایی:
آیا صفحه واقعاً لوکس، ساده و قابل فروش است؟
نه اینکه فقط CSS زیادی داشته باشد.

## 25. 3D QA

اگر 3D استفاده شد:
- ارزش بصری واقعی دارد؟
- performance مناسب است؟
- mobile fallback دارد؟
- loading مناسب است؟
- reduced motion دارد؟
- CTA و readability را خراب نمی‌کند؟
- آیا CSS/SVG/image نتیجه مشابه را ارزان‌تر می‌دهد؟

اگر بله، 3D ساده یا حذف شود.

## 26. Completion Gate

Feature فقط وقتی Complete است که:
- Code Truth verified
- Scope رعایت شده
- architecture سالم مانده
- old data preserved
- migrations idempotent
- auth/security PASS
- Mirror regression PASS
- Beauty Center regression PASS
- Reservation regression PASS
- User Panel regression PASS
- Admin regression PASS
- responsive PASS
- visual QA PASS
- performance reviewed
- accessibility reviewed
- SEO reviewed
- business CTA verified

گزارش نهایی باید دقیقاً بگوید:
چه فایل‌هایی تغییر کردند،
چه تست‌هایی PASS/FAIL شدند،
چه چیزی عمداً تغییر نکرد،
چه چیزی P2 باقی ماند.

## 27. دستور نهایی به Agent

این فایل را به‌عنوان سناریوی نهایی اجرا کن.

ابتدا giso-dev workflow را اجرا کن:
Understand Request
→ Freshness
→ Section Identification
→ Architecture
→ Dependency/Impact
→ Graph/Docs/Memory check
→ Council
→ Plan + Scope Lock

برای طراحی صفحه سالن:
3d site.md را مبنا قرار بده.

برای Mirror:
ساختار فعلی Buti AI را reuse کن.

برای Beauty Center:
ساختار فعلی beauty_centers را reuse کن.

برای Reservation:
ساختار فعلی reservations را reuse کن.

برای User Panel:
ساختار فعلی panel_user را extend کن.

برای Admin:
ساختار فعلی panel را extend کن.

هر قسمت کد فقط در فایل/پوشه مسئول خودش نوشته شود.
از تغییرات cross-module غیرضروری جلوگیری شود.
هر تغییر shared ابتدا dependency و regression آن بررسی شود.

اصل نهایی:
Reuse > Extend > New

و:
Maximum perceived quality per unit of technical cost

و:
No implementation is complete until it is run, inspected, tested, audited, optimized and regression-verified.
