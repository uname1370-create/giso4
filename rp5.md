# rp5.md — بررسی و طراحی سناریوی Beauty Center / پنل سالن و آگهی خدمات — Branch arena/01a0eecf-giso4

تاریخ: 2026-10-06
Auditor: Arena Agent (giso-dev skill workflow — Read-Only, No Code Change)
Reference: giso-dev/SKILL.md + s1.md + s2.md + s3.md + PROJECT_GUIDE.md + GISO_GUIDE.md + project_memory
Scope Lock: ALLOWED FILES = [rp5.md] — هیچ کد دیگری تغییر نکرده
Method: Existing Architecture First, Reuse > Extend > New, Code is Truth

---

## 1. وضعیت فعلی — چه چیزهایی همین الان داریم؟

### 1.1 سالن زیبایی — مدل/جدول Beauty Center

**جدول اصلی `beauty_centers` (giso/beauty_centers/schema.py:10-35):**
- id PK, owner_user_id UNIQUE FK -> giso_web_auth.id
- name TEXT NOT NULL (160), slug UNIQUE, category TEXT (hair, skin_face, beauty), center_type TEXT (salon, hair_center, skin_beauty, independent, nail_center, bridal, licensed_clinic)
- city, region, address_summary (300), business_phone, salon_phone, display_phone_choice (business/salon), contact_time, description (700)
- services_json TEXT '[]' — لیست تگ‌های انتخابی از SERVICES dict
- image_path (کاور), is_active, is_featured, sort_order
- status TEXT DEFAULT 'pending_review' — مقادیر واقعی از کد: pending_review, reviewing, published, rejected, paused, closed (STATUS_FA)
- admin_note, terms_version, terms_accepted_at
- counters: views_count, contact_clicks, analysis_impressions, price_inquiry_clicks
- pricing: price_level (economic, standard, premium, on_request), starting_price INTEGER
- expiry/promotion: listing_expires_at, promotion_type, promotion_expires_at, promotion_bumped_at
- migration additive: salon_phone, display_phone_choice, last_edit_at, listing_expires_at etc. via ALTER TABLE

**جداول مرتبط:**
- `beauty_center_images` (id, center_id FK CASCADE, image_path, sort_order, created_at) — تصاویر عمومی سالن، نه دسته‌بندی خدمت
- `beauty_center_services` (id, center_id, name, category, description, duration_minutes, price_min, price_max, is_active, sort_order, created_at, updated_at) — خدمات دقیق سالن با قیمت و مدت، قابل مدیریت در پنل سالن
- `beauty_center_working_hours` (id, center_id, day_of_week 0=شنبه تا 6=جمعه, open_time, close_time, is_closed, slot_minutes, legacy weekday/is_open)
- `beauty_center_conversations` (id, center_id, user_id, status active/closed, last_message_at, UNIQUE(center_id,user_id)) — گفتگوی کاربر و سالن
- `beauty_center_messages` (id, conversation_id FK, sender_user_id, message_text, is_read, is_reported)
- `beauty_center_feedback` (id, center_id, conversation_id, user_id, response_level, price_level, overall_level, comment, status pending, UNIQUE(conversation_id,user_id)) — امتیاز و نظر
- `beauty_center_reservations` (id, center_id, user_id, user_phone, user_name, service_id FK to beauty_center_services, service_name snapshot, service_price_min snapshot, duration_minutes, reservation_date, reservation_time, status pending/confirmed/completed/cancelled_user/cancelled_center, user_note, center_note, reject_reason, reminded flags, created_at, confirmed_at, cancelled_at, final_design_id, service_key, selected_style) — **اتصال Mirror**: final_design_id + service_key + selected_style
- `beauty_center_promotions` (id, center_id, owner_user_id, package_key, amount, starts_at, expires_at, transaction_key UNIQUE, status active) — برای Featured/Promotion
- `beauty_center_discounts` (id, center_id, title, description, discount_value, expires_at, status pending) — تخفیف
- `beauty_center_events` (id, center_id, event_type, user_id, created_at) — برای Lead/Analytics
- `beauty_center_expiry_notices` (id, center_id, notice_key UNIQUE)
- `beauty_center_reports` (id, center_id, reporter_user_id, reason, message, status open)

**ثبت سالن:**
- Route: `giso/beauty_centers/routes.py: register` GET/POST, form fields: name, category, center_type, city, region, address_summary, business_phone, salon_phone, display_phone_choice, contact_time, description, services (multi-select 16 max from SERVICES), price_level, starting_price, image
- Validation: `services.py: _normalize_fields()` — category in CENTER_CATEGORIES, center_type in CATEGORY_CENTER_TYPES[category], services in CATEGORY_SERVICES[category], price_level in PRICE_LEVELS, city required, business_phone normalized via normalize_phone, display_phone_choice business/salon
- Slug: `_slug_seed(name)` + secrets

**وضعیت تأیید سالن:**
- `STATUS_FA`: pending_review (در انتظار بررسی), reviewing (در حال بررسی), published (منتشرشده), rejected (نیازمند اصلاح), paused (متوقف‌شده), closed (بسته‌شده)
- Admin actions: `admin_set_status(center_id, target, note)` with guarded transition, via `panel_admin.py` and `bot_handlers.py: beauty_admin_menu_kb` (درخواست‌های جدید, مراکز منتشرشده, منقضی و متوقف, وضعیت مراکز, اعتبار آگهی, تنظیمات)
- Bot: `bot_handlers.py: _center_kb` actions review, publish, reject, pause

**اطلاعات تماس / آدرس / تصاویر:**
- تماس: business_phone (normalized), salon_phone, display_phone_choice, contact_time
- آدرس: city indexed, region, address_summary
- تصاویر: image_path (کاور) + beauty_center_images (گالری) via `save_center_image` with validation MAX_BYTES 5MB, MAX_PIXELS 20M, MAX_SIDE 12000, formats JPEG/PNG/WEBP

**خدمات سالن / قیمت / ساعات کاری:**
- SERVICES dict: haircut, hair_color, bleach, hair_repair, keratin, straightening, extension, braid, scalp_care, facial, skin_cleansing, skin_hydration, face_care, makeup, hairstyle, brow, lip_shading, lash, nail, bridal — شامل 4 خدمت Mirror: brow, nail, lip_shading, hair_color
- CATEGORY_SERVICES: hair (9), skin_face (7 including brow, lip_shading, lash), beauty (7 including makeup, hairstyle, brow, lip_shading, lash, nail, bridal)
- Pricing: beauty_center_services with price_min, price_max, duration_minutes, is_active, plus price_level, starting_price at center level
- Working hours: per day_of_week with open_time, close_time, is_closed, slot_minutes, via `pricing/services.py: save_working_hours` with BEGIN IMMEDIATE upsert

**وضعیت فعال/غیرفعال / امتیاز / رزرو / پیام:**
- is_active, is_featured, listing_expires_at, promotion_active (promotion_type + promotion_expires_at > now)
- Feedback: center_feedback_summary, response_level, price_level, overall_level, comment
- Reservation: create_reservation with BEGIN IMMEDIATE slot availability check, _is_available, _build_slots, _active_bookings, snapshot rule (service name/price/duration copied), status transition guarded _transition, confirm, reject, complete, cancel_by_user
- Messages: get_or_create_conversation, send_conversation_message, conversation_messages, owner_conversations, unread count
- Promotion: purchase_center_promotion, center_promotion_availability, renew_center_listing, process_center_expiry_notifications throttled 10min

### 1.2 پنل سالن — قابلیت‌های فعلی

**Owner Dashboard:** `giso/beauty_centers/routes.py: owner_dashboard` + `templates/beauty_centers/owner_dashboard.html`
- Context: `_owner_panel_context()` includes USER_MODULES + beauty_center menu, notifications, wallet balances
- Tabs (from template inspection): اطلاعات پایه (name, category, type, city, region, address, phone, contact_time, description), خدمات (get_center_services, add_service, update_service, delete_service), ساعات کاری (get_working_hours, save_working_hours), تصاویر (save_center_image, _remove_saved_image), پیام‌ها (owner_conversations, conversation_messages), رزروها (owner_list via reservations), آمار (views_count, contact_clicks, analysis_impressions, price_inquiry_clicks), وضعیت انتشار (status_label, listing_expired, promotion_active)

**مدیریت اطلاعات سالن:** update_owner_center with _normalize_fields validation

**مدیریت خدمات:** pricing/services.py — add_service (name required, duration 1-1440, price_min/max), update_service, delete_service, get_center_services ordered by is_active DESC, sort_order ASC

**قیمت:** service price_min/max + center price_level/starting_price + _service_price_label formatting with format_toman

**تصاویر/نمونه‌کار:** save_center_image with format/size validation, beauty_center_images table — ولی دسته‌بندی بر اساس خدمت ندارد (Gap)

**رزروها:** reservations/routes.py owner_list JSON, owner_action POST confirm/reject/complete with notify_user_confirmed/rejected, calendar, slots

**مشتری‌ها:** via conversations (center_id, user_id UNIQUE) + messages + feedback

**آمار:** views_count increment_view, contact_clicks reveal_contact, analysis_impressions, price_inquiry_clicks, plus beauty_stats in list_centers (centers count, views sum, hair analyses count, skin analyses count)

**آگهی/Featured/Promotion:** beauty_center_promotions with package_key, amount, transaction_key, status active, plus is_featured, sort_order, promotion_type, promotion_expires_at, promotion_bumped_at, plus center_promotion_availability, purchase_center_promotion, renew_center_listing

**وضعیت انتشار:** status_label, listing_expired check, promotion_active check

### 1.3 کاربر — Flow فعلی

- **پیدا کردن سالن:** /beauty-centers?q=&city=&category=&type=&service=&price_level= — list_public_centers with filters query, city, category, center_type, service, price_level, plus featured 6, related via recommended_centers(analysis_id, user_id, city), noindex if query, beauty_stats
- **خدمات سالن را می‌بیند:** center_detail slug — get_center_by_slug, is_owner/is_staff check, increment_view if published and not owner/staff, _center_services_for_display (price_label, duration_label), _center_hours_for_display, revealed contact if owner/staff, feedback summary, active_discount (legacy), discount_service_active check
- **نتیجه Beauty Mirror را می‌بیند:** /analysis/mirror/ (mirror_home) -> 4 کارت (eyebrow, nail, hair_color, lip_shading) active, href to /analysis/mirror/{slug} -> generic_service_wizard (model selection 5 styles with sample images 520x360) -> /{slug}/upload (photo upload with preview + guide + sample) -> process_service_submission (save_eyebrow_photo with prefix service_key, check_photo_quality AI first fallback local, detect_regions color segmentation, analyze_*_photo AI first fallback) -> build_result (quality+detection+ai_analysis+short_reason+do/avoid) -> _store_new_service_candidate session -> /{slug}/final (generate_final_design via service_image_generation with mask gate + provider chain + fallback guided composite, validation via validate_masked_output, save_final_design with session_id, user_id, service_type, original_filename, final_filename, selected_style, recommended_style, change_level, provider, model, status, prompt_json) -> generic_final_design.html: Before/After (original + final with cache), service/style/change labels, AI status (is_ai_generated), provider, model, validation, do/avoid, interest question bti-final-interest with Lead vs View, centers suggestions enrich with mirror_match_reason + mirror_tags + mirror_score, consultant invite + chat POST /{slug}/consultant with build_consultant_context (service_label+style_label+detection_method+is_ai+mask_real+coverage)
- **سالن پیشنهادی دریافت می‌کند:** _enrich_generic_centers(service_key, centers, candidate, city) — score: 45 if has_service (service_filter in services), 20 if city_match, 15 if is_featured, up to 20 from feedback score100//5, sorted by -mirror_score, mirror_rank; tags: service_label, همان شهر, feedback label; match reason: "برای اجرای {final_label}، این مرکز به‌عنوان ارائه‌دهنده {service_label} پیشنهاد شده است."
- **وارد صفحه سالن می‌شود:** center_detail + reserve link with final_design_id, service_key, selected_style
- **رزرو می‌کند:** /beauty-centers/<slug>/reserve?final_design_id=&service_key=&selected_style= GET shows service + slots via get_available_slots + calendar via get_calendar_month, POST create_reservation with final_design_id, service_key, selected_style, user_note, via BEGIN IMMEDIATE, snapshot, status pending, notify_new_reservation, redirect to my_reservations

### 1.4 Beauty Mirror — ارتباط فعلی

- `service_key`: from service_catalog (eyebrow, nail, hair_color, lip_shading) + slug mapping (nail, hair-color, lip-shading) + beauty_center_service mapping (brow, nail, hair_color, lip_shading) — Used in candidate.service_key, generation.service_key, reservation.service_key, ai_credits ledger service_key
- `selected_style`: style_key from STYLES (e.g., nude_minimal, chocolate_nescafe, natural_shading) + selected_label — Used in candidate.final_style, final_label, reservation.selected_style, ai_credits selected_style, consultant context style_label
- `final_design_id`: from save_final_design returns cur.lastrowid -> candidate.final_design_id -> passed to reserve route -> saved in beauty_center_reservations.final_design_id -> can be used to show AI result in center dashboard / reservation detail
- `buti_ai_final_designs`: session_id, user_id, service_type, original_filename, final_filename, selected_style, recommended_style, change_level, provider, model, status, prompt_json (candidate+generation), created_at — Stores full result for history
- `beauty_center_services`: center_id, name, category, description, duration_minutes, price_min, price_max, is_active — Does NOT have service_key column, but name can be mapped to SERVICES dict keys — Gap: no direct link to Mirror service_key
- `beauty_center_reservations`: final_design_id, service_key, selected_style — Direct link to Mirror result — Implemented and Connected, Actually Executed (test: reservation creation with these fields)

**چه چیزهایی قابل استفاده هستند:**
- service_key, selected_style, final_design_id در تمام لایه‌ها (candidate, generation, reservation, credits, consultant) — PASS
- beauty_center_services برای قیمت و مدت هر خدمت — PASS
- working_hours برای رزرو — PASS
- promotions/discounts/events برای آگهی/درآمد — PASS
- conversations/messages/feedback برای ارتباط و امتیاز — PASS

**چه چیزهایی کم است:**
- beauty_center_services.service_key column ندارد — فقط name string — برای اتصال دقیق Mirror به خدمت سالن باید service_key داشته باشد
- beauty_center_images.service_key ندارد — برای نمونه‌کار بر اساس خدمت
- buti_ai_final_designs در پنل کاربر نمایش داده نمی‌شود — تاریخچه نتایج AI Gap
- Bale bot Mirror flow ندارد

---

## 2. بررسی سناریوی «آگهی سالن بر اساس خدمات»

### مدل پیشنهادی:
به جای یک آگهی عمومی شلوغ (یک مرکز با 20 خدمت لیست شده بدون تفکیک)، **هر خدمت سالن یک آگهی/کارت مستقل** باشد که قابل نمایش در لیست، در صفحه سالن، و در نتیجه Mirror باشد.

مثال سالن A:
- کارت خدمت "ابرو - میکروبلیدینگ طبیعی" با نمونه‌کار ابرو، قیمت 2-3M، توضیح 2 خط، تخفیف 10%، زمان 90 دقیقه، CTA مشاهده/مشاوره/رزرو
- کارت خدمت "رنگ مو - بالیاژ کاراملی" با نمونه‌کار مو، قیمت از 1.5M، توضیح، پیشنهاد
- کارت خدمت "ناخن - فرنچ کلاسیک" etc.
- کارت خدمت "لب - شیدینگ طبیعی"

### از 3 دید:

#### 1. کاربر

**آیا راحت‌تر تصمیم می‌گیرد؟**
- YES — کاربر معمولاً یک خدمت خاص می‌خواهد (مثلاً ناخن فرنچ) نه کل سالن. اگر مستقیم کارت "ناخن فرنچ با نمونه‌کار و قیمت" ببیند، تصمیم سریع‌تر است. Flow فعلی Mirror -> سالن‌های ارائه‌دهنده همین خدمت -> نمایش چند سالن مناسب -> نمونه‌کار+قیمت+پیشنهاد -> مشاهده سالن -> رزرو — این UX لوکس و ساده است و با معماری فعلی قابل پیاده‌سازی است (enrich_generic_centers already does service filter).

**آیا باعث سردرگمی نمی‌شود؟**
- NO اگر طراحی کارت‌ها ساده و لوکس باشد: هر کارت یک خدمت، یک عکس نمونه‌کار همان خدمت، قیمت واضح، یک CTA اصلی (رزرو) + یک ثانویه (مشاوره). سردرگمی زمانی پیش می‌آید که یک سالن 20 خدمت را بدون دسته‌بندی در یک صفحه شلوغ نشان دهد — مدل فعلی list_centers با 6 فیلتر (q, city, category, type, service, price_level) + featured 6 تا حدی کمک می‌کند ولی کارت خدمت مستقل بهتر است.

**آیا می‌تواند مستقیماً خدمت مورد علاقه‌اش را پیدا کند؟**
- YES — با فیلتر service در list_centers (service=hair_color etc.) + با Mirror که service_key را می‌داند و فقط سالن‌های همان خدمت را پیشنهاد می‌دهد (mirror_match_reason). اگر هر خدمت سالن یک کارت مستقل با service_key داشته باشد، کاربر می‌تواند مستقیماً "ناخن فرنچ در مشهد" را جستجو کند و کارت‌های مرتبط ببیند.

#### 2. صاحب سالن

**آیا می‌تواند خدمات قابل ارائه را معرفی کند؟**
- YES — الان beauty_center_services table دارد name, description, price_min/max, duration, is_active — صاحب سالن می‌تواند هر خدمت را جدا ثبت کند. ولی UI owner_dashboard برای مدیریت خدمات فقط لیست ساده دارد، نه کارت لوکس با نمونه‌کار و پیشنهاد ویژه. اگر هر خدمت یک کارت با تصویر نمونه‌کار و تخفیف داشته باشد، سالن می‌تواند خدمات مهم‌تر را Featured کند.

**آیا مدیریت آن ساده است؟**
- YES اگر فرم ساده باشد: اضافه کردن خدمت: نام (از لیست SERVICES یا custom), دسته, توضیح کوتاه, مدت, قیمت min/max, فعال/غیرفعال, نمونه‌کار (1-3 عکس با service_key), پیشنهاد ویژه (optional). الان add_service فقط name, category, description, duration, price_min/max, is_active, sort_order دارد — ساده است. اگر نمونه‌کار و تخفیف به خدمت اضافه شود، باز هم ساده می‌ماند.

**آیا می‌تواند روی خدمات مهم‌تر تمرکز کند؟**
- YES — با is_featured در سطح مرکز + is_active در سطح خدمت + promotion package_key + discount — می‌تواند خدمت خاصی را Featured یا با تخفیف نشان دهد. مثلاً سالن A می‌خواهد "بالیاژ کاراملی" را Featured کند چون سود بیشتر دارد — با promotion_type و sort_order می‌تواند.

#### 3. کسب‌وکار Giso

**آیا ارزش تجاری دارد؟**
- YES — هر خدمت یک موجودیت قابل Featured, Promotion, تخفیف, تبلیغ هدفمند است. الان beauty_center_promotions با package_key, amount, transaction_key, status active برای کل مرکز است، ولی می‌تواند برای خدمت خاص هم باشد (با اضافه کردن service_id یا service_key). این مدل درآمدی بهتر از آگهی کلی است چون سالن حاضر است برای خدمت پول‌ساز پول بیشتری بدهد.

**آیا قابلیت تبدیل شدن به Featured Service, Promotion, تخفیف, تبلیغ هدفمند, پیشنهاد خدمت, رزرو را دارد؟**
- Featured Service: YES — via is_featured at center + sort_order at service + promotion package_key
- Promotion: YES — beauty_center_promotions exists, can be extended with service_id
- تخفیف: YES — beauty_center_discounts table exists (title, description, discount_value, expires_at) — can be linked to service
- تبلیغ هدفمند: YES — via service_key filter in list_centers + Mirror result service_key
- پیشنهاد خدمت: YES — via enrich_generic_centers with mirror_match_reason + mirror_score
- رزرو: YES — via beauty_center_reservations with service_id + service_key + final_design_id

**نتیجه:** مدل «آگهی ← خدمت سالن» از نظر محصولی **خوب است** — برای کاربر ساده‌تر، برای سالن قابل مدیریت و قابل تمرکز، برای Giso قابل پولی شدن.

---

## 3. بررسی UX لوکس و ساده

**هدف:** خدمات Giso ساده، لوکس، قابل فهم برای کاربر و ابزار واقعی جذب مشتری برای سالن

**Flow پیشنهادی لوکس:**

```
Beauty Mirror (/analysis/mirror/)
  ↓ انتخاب خدمت (4 کارت لوکس: ابرو, ناخن, رنگ مو, لب)
  ↓ انتخاب مدل (5 مدل هر خدمت با تصویر 520x360 + توضیح + do/avoid)
  ↓ آپلود عکس (preview + guide + sample + laser scan)
  ↓ Quality AI (ai_checked + checks) + Detection (ROI + Mask) + Analysis AI (short_reason + do/avoid)
  ↓ Generation (Before/After + validation in/out + is_ai_generated)
  ↓ نتیجه شخصی‌سازی‌شده (final_label + change_label + do/avoid + consultant invite)
  ↓ سالن‌های ارائه‌دهنده همین خدمت (enrich_generic_centers: score 45 has_service +20 city_match +15 featured + feedback, tags, match reason)
  ↓ نمایش چند سالن مناسب (3 کارت: logo/cover, name, city, rating, price_level, mirror_tags, CTA رزرو/مشاهده مرکز)
  ↓ کارت خدمت سالن (نمونه‌کار همان خدمت + قیمت + پیشنهاد ویژه + زمان + CTA)
  ↓ مشاهده سالن (detail: اطلاعات + خدمات همان دسته + نمونه‌کار فیلتر شده + ساعات کاری + نظرات + رزرو)
  ↓ رزرو (reserve with final_design_id + service_key + selected_style, slots, calendar, user_note)
  ↓ Lead (conversation + events)
```

**آیا با معماری فعلی قابل پیاده‌سازی است؟**
- YES — تمام اجزا وجود دارند:
  - Mirror flow: routes.py mirror_home, generic_service_wizard, upload, final_design, consultant chat — PASS
  - Quality/Detection/Analysis/Generation/Validation: final_design.py + service_image_generation + image_validation — PASS (بعد از Fix reliable True)
  - Centers filtering: list_public_centers(service=service_filter) where service_filter from service_catalog.beauty_center_service — PASS
  - Enrich: _enrich_generic_centers with score + tags + match reason — PASS
  - Service Offer: beauty_center_services table + _center_services_for_display with price_label + duration_label — PASS, ولی نمونه‌کار بر اساس خدمت ندارد (Gap)
  - Reservation: create_reservation with final_design_id + service_key + selected_style + BEGIN IMMEDIATE + snapshot — PASS
  - Lead: conversations + events — PASS
  - Promotion: beauty_center_promotions + is_featured — PASS

**تنها Gap برای UX لوکس:** نمونه‌کار بر اساس خدمت — الان beauty_center_images فقط عمومی است، برای کارت خدمت لوکس باید نمونه‌کار همان خدمت (مثلاً ناخن فرنچ) نمایش داده شود.

---

## 4. طراحی سناریوی پیشنهادی — کامل ولی ساده

### 4.1 User Panel (کاربر سایت)

**کاربر چه می‌بیند؟**
- هدر: پروفایل + Wallet + Notifications
- تب‌ها: نمای کلی (overview), تحلیل‌ها (analyses: hair/skin + mirror results), مراکز من (beauty_center if owner), رزروهای من (my_reservations), پیام‌ها (conversations), کیف پول (wallet), تنظیمات (profile)
- **جدید پیشنهادی:** تب "نتایج آینه من" (my-mirror-results) — لیست buti_ai_final_designs where user_id=current_user.id ordered by created_at DESC, هر کارت: service_icon + service_label, selected_style label, final image thumbnail, original thumbnail, Before/After toggle, date Jalali, status, provider, CTA "مشاهده نتیجه" + "رزرو مجدد" + "پیشنهاد مراکز"

**چه چیزی پیشنهاد می‌شود؟**
- بر اساس آخرین Mirror result: 3 سالن پیشنهادی همان خدمت + همان شهر (reuse enrich_generic_centers)
- بر اساس تاریخچه: اگر کاربر 2 بار ناخن انتخاب کرده، در overview پیشنهاد "ناخن - مدل‌های جدید"
- بر اساس Lead: اگر conversation باز دارد، نمایش "پیام جدید از سالن X"

**CTAها:**
- "مشاهده نتیجه" -> /analysis/mirror/{slug}/final?photo_filename=&selected_style=
- "رزرو مجدد" -> /beauty-centers/{slug}/reserve?final_design_id=&service_key=&selected_style=
- "پیشنهاد مراکز" -> /beauty-centers?service={service_filter}&city={user_city}
- "گفتگو با مشاور" -> POST /{slug}/consultant

### 4.2 صفحه سالن — چه اطلاعاتی نمایش داده شود؟

**صفحه فعلی detail.html دارد:**
- نام، معرفی، عکس کاور، گالری images, آدرس, شهر, منطقه, شماره تماس (reveal), ساعات کاری, خدمات با قیمت و مدت, نظرات, آمار, وضعیت, disclaimer

**پیشنهاد لوکس برای خدمات:**

- **هدر سالن:** لوگو جدا (logo_path) + کاور (image_path) + نام + نوع (center_type) + دسته (category) + شهر + امتیاز + تعداد نظرات + وضعیت (published) + Featured badge + CTA رزرو + CTA پیام
- **خدمات به‌صورت کارت‌های لوکس (نه لیست شلوغ):**
  - هر کارت: icon خدمت (از SERVICES), نام خدمت (مثلاً "بالیاژ کاراملی"), توضیح کوتاه 1 خط, مدت (duration_label), قیمت (price_label: از X تا Y یا قیمت پس از بررسی), نمونه‌کار همان خدمت (1-3 عکس از beauty_center_images where service_key=service_key یا portfolio), پیشنهاد ویژه (discount_value if active), وضعیت فعال/غیرفعال, CTA "مشاهده نمونه‌کار" + "رزرو این خدمت" + "مشاوره"
  - فیلتر: تب‌های دسته (مو, پوست و صورت, آرایش و زیبایی) + جستجوی خدمت
  - مرتب‌سازی: is_active DESC, sort_order ASC, is_featured first
- **نمونه‌کار:** گالری فیلتر شده بر اساس خدمت انتخابی — اگر کاربر روی کارت "ناخن فرنچ" کلیک کرد، فقط تصاویر با service_key=nail یا portfolio category=nail نمایش داده شود
- **قیمت:** price_level (اقتصادی/متعادل/ممتاز/پس از بررسی) در هدر + هر خدمت price_min/max با format_toman + starting_price
- **پیشنهاد ویژه:** beauty_center_discounts (title, discount_value, expires_at) + promotions (package_key) — نمایش به‌صورت badge "تخفیف 20% تا 2 روز دیگر" + CTA
- **رزرو:** CTA اصلی در هر کارت خدمت -> /beauty-centers/{slug}/reserve?service_id={service_id}&final_design_id={if from Mirror}&service_key=&selected_style= — تقویم + اسلات + یادداشت

### 4.3 پنل سالن — صاحب سالن چه چیزی مدیریت کند؟

**منوهای پیشنهادی لوکس و ساده (P0 ضروری):**

1. **نمای کلی (Overview):**
   - آمار: views_count, contact_clicks, analysis_impressions, price_inquiry_clicks, reservations count pending/confirmed, conversations unread, feedback avg
   - وضعیت: status_label, listing_expired, promotion_active, is_featured
   - CTA: ویرایش اطلاعات, مدیریت خدمات, مشاهده صفحه عمومی

2. **اطلاعات سالن (Profile):**
   - فیلدها: name (160), category (hair/skin_face/beauty), center_type (7 types), city (100 required), region (150), address_summary (300), business_phone (normalized required), salon_phone (optional), display_phone_choice (business/salon), contact_time (100), description (700), image_path (کاور), logo_path (جدید پیشنهادی), instagram (جدید پیشنهادی)
   - Validation: existing _normalize_fields
   - CTA: ذخیره, پیش‌نمایش

3. **خدمات (Services) — مهم‌ترین بخش:**
   - لیست خدمات: get_center_services ordered by is_active DESC, sort_order ASC
   - هر خدمت کارت: name, category, description (500), duration_minutes (1-1440), price_min, price_max, is_active, sort_order, نمونه‌کار (1-3 عکس), پیشنهاد ویژه (optional)
   - افزودن خدمت: form با name (از SERVICES dict یا custom), category, description, duration, price_min/max, is_active, sort_order
   - ویرایش/حذف: update_service, delete_service
   - **جدید پیشنهادی:** فیلد service_key TEXT (از SERVICES keys) برای اتصال دقیق به Mirror + is_featured_service BOOLEAN برای Featured Service + discount link
   - CTA: افزودن خدمت, ویرایش, فعال/غیرفعال, Featured

4. **نمونه‌کار (Portfolio):**
   - فعلی: beauty_center_images (image_path, sort_order) — عمومی
   - پیشنهادی: اضافه کردن service_key به images یا جدول جدا beauty_center_portfolio (id, center_id FK, service_key, image_path, sort_order, created_at) — هر نمونه‌کار به یک خدمت لینک شود
   - UI: آپلود عکس + انتخاب خدمت مرتبط (از لیست خدمات فعال) + مرتب‌سازی
   - CTA: آپلود, حذف, انتخاب خدمت

5. **ساعات کاری (Working Hours):**
   - get_working_hours, save_working_hours — per day_of_week with open_time, close_time, is_closed, slot_minutes
   - UI: 7 روز هفته با time picker + تعطیل checkbox + slot_minutes
   - CTA: ذخیره

6. **رزروها (Reservations):**
   - owner_list JSON with filters center_id, date, status + owner_action POST confirm/reject/complete + calendar + slots
   - نمایش: service_name snapshot, user_name, phone, date, time, status_label, user_note, final_design_id link to Mirror result if exists, service_key, selected_style
   - CTA: تأیید, رد با دلیل, تکمیل, مشاهده جزئیات, تقویم

7. **پیام‌ها/مشتری‌ها (Conversations):**
   - owner_conversations, conversation_messages, send_conversation_message, unread count, close_conversation
   - نمایش: user, last_message_at, status, messages, feedback if exists
   - CTA: پاسخ, بستن گفتگو, مشاهده پروفایل کاربر

8. **نظرات/امتیاز (Feedback):**
   - center_feedback_summary, feedback list with response_level, price_level, overall_level, comment, status pending
   - CTA: مشاهده, تأیید (اگر نیاز به moderation)

9. **آگهی/تبلیغ (Promotion) — مدل درآمدی:**
   - center_promotion_availability, purchase_center_promotion, renew_center_listing, promotion_type, promotion_expires_at, is_featured, sort_order
   - **پیشنهادی:** Featured Service — promotion با service_id/service_key — سالن می‌تواند یک خدمت خاص را Featured کند
   - UI: بسته‌های تبلیغ (مثلاً 7 روزه, 30 روزه), انتخاب خدمت برای Featured, مبلغ, تاریخ انقضا
   - CTA: خرید بسته, تمدید, مشاهده وضعیت

**چه منوهایی لازم است؟** 9 منوی بالا — P0: 1-6, P1: 7-9 — ساده + لوکس، نه شلوغ

### 4.4 Admin — چه چیزهایی کنترل کند؟

- **مراکز:** list_admin_centers with filters status, city, category, type, service, search q — admin.html + beauty_admin_menu_kb via Bale — actions: review (pending_review->reviewing), publish (reviewing->published), reject (->rejected with note), pause (published->paused), plus is_active, is_featured, sort_order, views, etc.
- **خدمات مراکز:** via pricing/services — می‌تواند خدمات هر مرکز را ببیند/ویرایش کند
- **رزروها:** via reservations — list all, filter by center, date, status, user
- **گفتگوها/Lead:** via conversations, messages, events
- **AI:** panel/modules/ai.py — beauty_mirror slots (vision + 4 image tasks), providers, models, credit, health, failover, errors — panel_slots_context
- **کاربران:** panel/modules/users.py — users, analyses, mirror sessions, final designs, reservations, conversations
- **مالی:** finance_overview — beauty_revenue from promotions, transactions
- **اعلان‌ها:** notifications core — beauty_centers events center_new, center_status, report
- **تنظیمات:** settings + terms_version

**برای سناریوی جدید:**
- Admin باید بتواند Featured Service را تأیید کند (اگر promotion با service_id باشد)
- باید بتواند Portfolio categorization را ببیند
- باید بتواند Instagram/Logo جدید را ببیند

---

## 5. استفاده از ساختار موجود — جدول Reuse

| قابلیت | ساختار موجود | قابل استفاده مستقیم؟ | نیاز به تغییر؟ | فایل/ماژول |
|---|---|---|---|---|
| Beauty Center مدل | beauty_centers table 20+ fields + migration additive | YES | NO - کافی برای MVP | `giso/beauty_centers/schema.py` |
| ثبت سالن | register route + _normalize_fields + SERVICES + CATEGORY_SERVICES | YES | NO - ولی بهبود فیلتر UI Low | `giso/beauty_centers/routes.py: register`, `services.py: _normalize_fields` |
| وضعیت تأیید | STATUS_FA + admin_set_status + bot_handlers beauty_admin_menu_kb | YES | NO | `services.py: STATUS_FA`, `bot_handlers.py` |
| اطلاعات تماس/آدرس | business_phone, salon_phone, display_phone_choice, city, region, address_summary, contact_time | YES | NO | `schema.py` |
| تصاویر عمومی | beauty_center_images + save_center_image with validation | YES | NO | `schema.py`, `services.py: save_center_image` |
| تصاویر نمونه‌کار بر اساس خدمت | beauty_center_images فقط عمومی، بدون service_key | PARTIAL | YES - Add service_key column to images OR new table portfolio | `schema.py: beauty_center_images`, `services.py` |
| خدمات سالن | beauty_center_services table: name, category, description, duration, price_min/max, is_active, sort_order | YES | PARTIAL - Add service_key column for Mirror link + is_featured_service | `pricing/schema.py`, `pricing/services.py: get_center_services, add_service` |
| قیمت خدمات | price_level, starting_price, service price_min/max, _service_price_label | YES | NO | `services.py: PRICE_LEVELS`, `routes.py: _service_price_label` |
| ساعات کاری | beauty_center_working_hours + save_working_hours with BEGIN IMMEDIATE | YES | NO | `pricing/services.py` |
| فعال/غیرفعال | is_active, is_featured, status, listing_expires_at, promotion_active | YES | NO | `schema.py` |
| امتیاز و نظر | beauty_center_feedback + center_feedback_summary | YES | NO | `schema.py`, `services.py` |
| رزرو | beauty_center_reservations with final_design_id, service_key, selected_style + create_reservation with slot check + confirm/reject/complete/cancel | YES | NO - کامل | `reservations/schema.py`, `reservations/services.py`, `reservations/routes.py` |
| پیام/ارتباط | beauty_center_conversations + messages UNIQUE(center_id,user_id) + owner_conversations | YES | NO | `schema.py`, `services.py: get_or_create_conversation` |
| Featured/Promotion | beauty_center_promotions + is_featured + promotion_type/expires + purchase/renew | YES | PARTIAL - Add service_id/service_key to promotions for Featured Service | `schema.py`, `services.py: purchase_center_promotion` |
| تخفیف | beauty_center_discounts | YES | PARTIAL - Link to service | `schema.py` |
| پنل سالن - اطلاعات | update_owner_center + owner_dashboard | YES | NO | `routes.py: owner_dashboard`, `services.py` |
| پنل سالن - خدمات | pricing/services add/update/delete | YES | PARTIAL - Add service_key | `pricing/services.py` |
| پنل سالن - تصاویر | save_center_image | YES | PARTIAL - Add service_key | `services.py` |
| پنل سالن - رزروها | owner_list + owner_action + calendar + slots + notify | YES | NO | `reservations/routes.py`, `services.py` |
| پنل سالن - آمار | views_count, contact_clicks, analysis_impressions, price_inquiry_clicks, beauty_stats | YES | NO | `services.py: increment_view, reveal_contact` |
| کاربر - پیدا کردن سالن | list_public_centers with filters q, city, category, type, service, price_level + featured + related | YES | NO | `routes.py: list_centers`, `services.py: list_public_centers` |
| کاربر - خدمات سالن | _center_services_for_display + detail.html | YES | PARTIAL - Needs service_key filter for portfolio | `routes.py: center_detail` |
| کاربر - نتیجه Mirror | buti_ai routes + generic_service + service_image_generation + validation + final_design | YES | NO - کامل بعد Fix | `giso/buti_ai/routes.py`, `generic_service.py`, `service_image_generation.py` |
| کاربر - سالن پیشنهادی | _enrich_generic_centers with score + tags + match reason | YES | NO | `giso/buti_ai/routes.py: _enrich_generic_centers` |
| کاربر - رزرو | reserve route with final_design_id + service_key + selected_style | YES | NO | `reservations/routes.py: reserve` |
| Beauty Mirror - service_key | service_catalog.beauty_center_service mapping + candidate.service_key + reservation.service_key | YES | NO | `giso/buti_ai/service_catalog.py`, `generic_service.py`, `reservations/services.py` |
| Beauty Mirror - selected_style | STYLES keys + candidate.final_style + reservation.selected_style + ai_credits selected_style | YES | NO | `final_design.py STYLES`, `generic_service.py` |
| Beauty Mirror - final_design_id | save_final_design returns id -> candidate.final_design_id -> reservation.final_design_id | YES | NO | `giso/buti_ai/services.py: save_final_design`, `reservations/services.py: create_reservation` |
| Beauty Mirror - buti_ai_final_designs | session_id, user_id, service_type, original_filename, final_filename, selected_style, provider, model, status, prompt_json | YES | NO | `giso/buti_ai/schema.py`, `services.py` |
| Beauty Center Services link | beauty_center_services table | PARTIAL | YES - Add service_key column | `pricing/schema.py` |
| User Panel - History | analyses table for hair/skin but not mirror | PARTIAL | YES - New module mirror.py reuse analyses pattern | `giso/panel_user/modules/analyses.py` |
| Bale Bot - Mirror | No flow | NO | YES - New handlers reuse generic_service | `giso/bot.py`, `bot_handlers.py` |

**اولویت مطلق:** Reuse > Extend > New — 80% قابلیت‌ها با ساختار موجود قابل انجام است، 20% نیاز به Extend با 1-2 ستون additive دارد، هیچ New Architecture لازم نیست.

---

## 6. بررسی دیتابیس — آیا جدول‌ها کافی هستند؟

**جدول‌های بررسی شده:**
- beauty_centers
- beauty_center_services
- beauty_center_images
- beauty_center_reservations
- buti_ai_mirror_sessions
- buti_ai_final_designs

**آیا کافی هستند؟**
- برای Flow فعلی (Mirror -> Centers -> Reservation with final_design_id): YES — کامل
- برای سناریوی پیشنهادی «آگهی بر اساس خدمت» (هر خدمت کارت مستقل با نمونه‌کار و پیشنهاد ویژه): PARTIAL — نیاز به 1-2 فیلد جدید

**اگر نیاز به تغییر DB:**

| چه فیلدی؟ | در کدام جدول؟ | چرا؟ | آیا می‌توان بدون تغییر انجام داد؟ |
|---|---|---|---|
| `service_key TEXT DEFAULT ''` | `beauty_center_services` | برای اتصال دقیق خدمت سالن به Mirror service_key (brow, nail, hair_color, lip_shading) — الان فقط name string است و mapping via SERVICES dict حدسی است | می‌توان بدون تغییر هم با name mapping ادامه داد ولی با service_key دقیق‌تر و قابل فیلتر است — توصیه: اضافه شود additive via ALTER TABLE |
| `service_key TEXT DEFAULT ''` | `beauty_center_images` | برای نمونه‌کار بر اساس خدمت — مثلاً عکس ناخن فرنچ فقط برای خدمت ناخن — الان فقط عمومی است | می‌توان بدون تغییر با توضیح در description ادامه داد ولی با service_key UX لوکس‌تر است — توصیه: اضافه شود |
| `is_featured_service INTEGER DEFAULT 0` | `beauty_center_services` | برای Featured Service — سالن می‌تواند یک خدمت خاص را Featured کند | می‌توان بدون تغییر با sort_order=0 + is_active=1 + promotion برای کل مرکز ادامه داد ولی با این فیلد دقیق‌تر است — Low priority |
| `logo_path TEXT DEFAULT ''` | `beauty_centers` | لوگو جدا از کاور | می‌توان بدون تغییر با image_path ادامه داد — Low |
| `instagram TEXT DEFAULT ''` | `beauty_centers` | اینستاگرام | می‌توان بدون تغییر با description ادامه داد — Low |
| `service_id` یا `service_key` | `beauty_center_promotions` | برای Featured Service Promotion — promotion برای یک خدمت خاص نه کل مرکز | می‌توان بدون تغییر با promotion برای کل مرکز ادامه داد — P1 |
| `service_id` | `beauty_center_discounts` | تخفیف برای خدمت خاص | می‌توان بدون تغییر با discount برای کل مرکز ادامه داد — P1 |

**اگر با ساختار فعلی قابل انجام است، تغییر DB پیشنهاد نده:**
- برای MVP فعلی: YES قابل انجام است — با `beauty_center_services` موجود + `beauty_center_images` عمومی + `reservations` با final_design_id می‌توان Flow لوکس را پیاده کرد بدون تغییر DB
- برای سناریوی لوکس کامل (کارت خدمت مستقل با نمونه‌کار فیلتر شده + Featured Service): توصیه 2 ستون additive (`service_key` در services و images) — migration additive مثل `ai_credits.py` که service_key اضافه شد — ریسک کم

**نتیجه DB Impact:** برای P0 (ضروری) هیچ تغییر DB لازم نیست. برای P1 (مهم) 2 ستون additive پیشنهاد می‌شود.

---

## 7. بررسی آگهی و مدل درآمدی

**آیا بهتر است «آگهی» عمومی باشد یا «آگهی ← خدمت سالن»؟**

| مدل | توضیح | UX کاربر | مدیریت سالن | ارزش تجاری Giso | توصیه |
|---|---|---|---|---|---|
| آگهی عمومی سالن (وضعیت فعلی) | یک مرکز با لیست 20 خدمت بدون تفکیک، یک کاور، یک قیمت کلی | متوسط — کاربر باید داخل صفحه سالن بگردد تا خدمت مورد نظر را پیدا کند | ساده ولی غیرقابل تمرکز — نمی‌تواند خدمت پول‌ساز را Featured کند | کم — فقط promotion برای کل مرکز | برای شروع کافی ولی برای رشد نه |
| آگهی ← خدمت سالن (پیشنهادی) | هر خدمت سالن یک کارت مستقل با نمونه‌کار همان خدمت + قیمت + پیشنهاد + CTA | عالی — کاربر مستقیم خدمت مورد نظر را با نمونه‌کار و قیمت می‌بیند، تصمیم سریع | عالی — می‌تواند خدمات فعال/غیرفعال، Featured، تخفیف برای هر خدمت جدا مدیریت کند | عالی — هر خدمت قابل Featured/Promotion/تخفیف/تبلیغ هدفمند بر اساس service_key | **توصیه: مدل پیشنهادی** |

**چرا مدل خدمت‌محور بهتر است؟**
- کاربر: جستجوی "ناخن فرنچ در مشهد" مستقیم کارت‌های ناخن فرنچ را می‌بیند نه کل سالن‌های زیبایی — UX لوکس
- سالن: می‌تواند روی خدماتی که برایش مهم‌تر است (مثلاً بالیاژ کاراملی با سود بالا) تمرکز کند و برای آن promotion بخرد
- Giso: هر خدمت یک inventory قابل فروش است — می‌توان بسته‌های "Featured Service 7 روزه" فروخت، تخفیف برای خدمت خاص، جایگاه ویژه در نتیجه Mirror بر اساس service_key

**بررسی Featured Service, Promotion, تخفیف, جایگاه ویژه, پیشنهاد بر اساس Mirror, service_key:**

| قابلیت | الان وجود دارد؟ | ارزش دارد؟ | ضروری یا بعداً؟ | توضیح |
|---|---|---|---|---|
| Featured Service | PARTIAL - is_featured در سطح مرکز، نه خدمت | YES - ارزش بالا — سالن حاضر است برای خدمت پول‌ساز پول بدهد | P1 - مهم | با اضافه کردن is_featured_service به beauty_center_services یا promotion با service_id قابل پیاده‌سازی |
| Promotion (بسته تبلیغ) | YES - beauty_center_promotions with package_key, amount, transaction_key | YES - ارزش بالا — مدل درآمدی فعلی Giso | P0 - ضروری (موجود) | الان برای کل مرکز، می‌تواند برای خدمت خاص هم باشد |
| تخفیف Discount | YES - beauty_center_discounts table | YES - ارزش متوسط — برای جذب مشتری | P1 - مهم | الان عمومی، می‌تواند به service_id لینک شود |
| جایگاه ویژه (sort_order, is_featured) | YES - sort_order, is_featured, promotion_bumped_at | YES - ارزش بالا | P0 - موجود | در list_public_centers featured first + sort_order |
| پیشنهاد بر اساس نتیجه Mirror | YES - _enrich_generic_centers with service filter + score + match reason | YES - ارزش بسیار بالا — هسته محصول | P0 - ضروری و موجود | service_key از Mirror به service filter مراکز |
| پیشنهاد بر اساس service_key | YES - list_public_centers(service=service_filter) where service_filter from service_catalog.beauty_center_service | YES - ارزش بالا | P0 - موجود | brow, nail, hair_color, lip_shading |

**کدام واقعاً ارزش دارد و کدام فعلاً اضافه؟**
- ارزش دارد P0: پیشنهاد بر اساس Mirror + service_key, جایگاه ویژه, Promotion برای کل مرکز, رزرو با final_design_id
- ارزش دارد P1: Featured Service, تخفیف برای خدمت خاص, نمونه‌کار بر اساس خدمت
- فعلاً اضافه P2: تبلیغ هدفمند پیچیده (مثلاً بر اساس city + service + price_level + user history), Instagram feed, Logo جدا — بعداً

---

## 8. اولویت‌بندی — P0, P1, P2

**هدف:** ساده + لوکس + قابل فروش + قابل مدیریت برای سالن

### P0 — ضروری (برای تجربه خوب و قابل استفاده)

| قابلیت | چرا ضروری؟ | ساختار موجود؟ | فایل/ماژول |
|---|---|---|---|
| Beauty Mirror 4 خدمت با Quality AI + Detection + Mask + Validation + Final | هسته محصول | YES - کامل بعد Fix | `giso/buti_ai/*` |
| Service Selection + Style Selection + Upload + Final | Flow اصلی | YES | `routes.py`, `generic_service.py`, `templates/buti_ai/*` |
| Centers filtering بر اساس service_key | اتصال Mirror به سالن | YES - list_public_centers(service=) + _enrich_generic_centers | `beauty_centers/services.py`, `buti_ai/routes.py` |
| Center Detail با خدمات + قیمت + ساعات کاری + نظرات | اطلاعات لازم کاربر | YES | `routes.py: center_detail`, `_center_services_for_display`, `_center_hours_for_display` |
| Reservation با final_design_id + service_key + selected_style | تبدیل Lead به رزرو | YES - create_reservation with snapshot + BEGIN IMMEDIATE | `reservations/services.py`, `routes.py: reserve` |
| Owner Dashboard - اطلاعات + خدمات + ساعات + تصاویر + رزروها + پیام‌ها + آمار | مدیریت ضروری سالن | YES | `routes.py: owner_dashboard`, `pricing/services.py`, `reservations/routes.py` |
| Promotion برای کل مرکز + is_featured | مدل درآمدی فعلی | YES | `services.py: purchase_center_promotion` |
| AI Consultant + Interest Question + Chat | ارزش افزوده Mirror | YES - بعد از Fix d8dc7ef | `consultant.py`, `routes.py: consultant chat` |

### P1 — مهم (ارزش محصول و سالن را بالا می‌برد)

| قابلیت | چرا مهم؟ | نیاز به تغییر؟ | فایل/ماژول |
|---|---|---|---|
| User Panel - تاریخچه نتایج Mirror (my-mirror-results) | کاربر نتایج قبلی را ببیند | YES - New module reuse analyses.py pattern | `giso/panel_user/modules/mirror.py` (جدید), `panel_user/routes.py`, `templates/panel_user/mirror_results.html` |
| Portfolio categorization - نمونه‌کار بر اساس خدمت | UX لوکس - کارت خدمت با نمونه‌کار همان خدمت | YES - Add service_key column to beauty_center_images (additive) | `beauty_centers/schema.py` migrate, `services.py: save_center_image`, `owner_dashboard.html` |
| Featured Service - یک خدمت خاص Featured | سالن روی خدمت پول‌ساز تمرکز کند + درآمد Giso | YES - Add service_key or service_id to promotions OR is_featured_service to services | `beauty_centers/schema.py`, `services.py` |
| Discount برای خدمت خاص | جذب مشتری | YES - Link discount to service_id | `schema.py: beauty_center_discounts`, `services.py` |
| Bale Bot - Mirror flow برای 4 خدمت | کاربر Bale هم از آینه استفاده کند | YES - New handlers reuse generic_service | `giso/bot.py`, `beauty_centers/bot_handlers.py`, `bot_states.py` |
| Service Key در beauty_center_services | اتصال دقیق Mirror به خدمت سالن | YES - Add service_key column additive | `pricing/schema.py`, `pricing/services.py` |

### P2 — بعداً (فعلاً نباید ساختار را شلوغ کنند)

| قابلیت | چرا بعداً؟ | توضیح |
|---|---|---|
| Instagram, Logo جدا, Sample Images 800+ | Low value, می‌توان با description/image_path ادامه داد | بعداً با ALTER TABLE |
| تبلیغ هدفمند پیچیده (city+service+price+history) | نیاز به Analytics + User history + پیچیدگی | بعد از P0,P1 |
| علاقه‌مندی‌ها/مراکز موردعلاقه | Pattern ندارد، Low | بعداً |
| Featured Service Promotion با مبلغ جدا | نیاز به تصمیم مالی + تست بازار | بعد از P1 |
| Ombré Lip, Chrome French, Warm Honey مدل‌های دقیق s1 | مدل‌های فعلی بازار واقعی دارند، Low | بعداً اگر نیاز بازار |

---

## 9. خروجی نهایی

### 9.1 وضعیت فعلی — چه چیزهایی همین الان داریم؟

- **Beauty Centers:** جدول beauty_centers با 20+ فیلد + 10 جدول مرتبط (images, services, working_hours, conversations, messages, feedback, reservations with final_design_id/service_key/selected_style, promotions, discounts, events, reports) — کامل برای MVP
- **ثبت/ویرایش/تأیید:** register route + _normalize_fields + STATUS_FA pending_review/reviewing/published/rejected/paused + admin_set_status + bot_handlers beauty_admin_menu_kb
- **خدمات/قیمت/ساعات:** beauty_center_services with price_min/max/duration/is_active + pricing/services add/update/delete + working_hours per day + _service_price_label
- **رزرو/پیام/امتیاز:** create_reservation with BEGIN IMMEDIATE + snapshot + final_design_id + notify + conversations/messages + feedback
- **Promotion/Featured:** beauty_center_promotions + is_featured + sort_order + promotion_type/expires + purchase/renew + expiry notifications throttled
- **پنل سالن:** owner_dashboard with tabs اطلاعات/خدمات/ساعات/تصاویر/پیام‌ها/رزروها/آمار/وضعیت انتشار — via _owner_panel_context
- **کاربر:** list_centers with filters q/city/category/type/service/price_level + featured + related + center_detail with services/hours/feedback + Mirror flow 4 services with Quality AI+Detection+Analysis AI+Generation+Validation+Final+Centers+Reservation
- **Beauty Mirror integration:** service_key, selected_style, final_design_id در candidate, generation, reservation, credits, consultant — Implemented and Connected and Actually Executed (test PASS)

### 9.2 نقاط قوت — چه چیزهایی خوب و قابل استفاده هستند؟

- **ماژولار:** هر بخش در پوشه خودش (beauty_centers/, buti_ai/, panel/, reservations, pricing) — Golden rule رعایت شده
- **Additive migrations:** همه ALTER TABLE ADD COLUMN — بدون شکستن DB قدیمی
- **Service filtering:** SERVICES dict شامل nail, hair_color, lip_shading, brow + CATEGORY_SERVICES + CENTER_TYPES — filtering کار می‌کند
- **Reservation snapshot:** service_name, price, duration کپی می‌شود — تغییر قیمت بعدی رزرو قبلی را نمی‌شکند — امن
- **Mask gate + Validation:** service_image_generation._safe_mask_for_real_ai + validate_masked_output + attempts list — از فریب AI جلوگیری می‌کند
- **Fallback صادقانه:** is_ai_generated=False + پیام "این نسخه AI واقعی نیست" — قانون s1
- **Consultant Context:** Service+Style+Analysis+Preview + chat route POST /consultant — ارزش افزوده
- **Shared services:** list_public_centers, get_center_by_slug, get_owner_center, create_reservation, get_available_slots — هم وب هم ربات از یک منبع — No Duplication
- **Promotion/Expiry:** throttled expiry check + promotion availability + renew — مدل درآمدی آماده

### 9.3 Gapها — دقیقاً چه چیزهایی کم داریم؟

| # | Gap | File/Function | Current | Expected | Impact | Priority |
|---|---|---|---|---|---|---|
| 1 | User Panel Mirror History | panel_user/modules/analyses.py has hair/skin but not mirror, no mirror.py | No history page | my-mirror-results page from buti_ai_final_designs | Medium - کاربر نتایج قبلی را نمی‌بیند | P1 |
| 2 | Portfolio categorization by service | beauty_center_images only image_path, sort_order — no service_key | Generic gallery | Gallery filtered by service_key for service card | Medium - کارت خدمت لوکس نمونه‌کار همان خدمت ندارد | P1 |
| 3 | Featured Service | beauty_center_services no is_featured_service, promotions only center level | Only center featured | Service can be featured + promotion with service_id | Medium - سالن نمی‌تواند خدمت پول‌ساز را Featured کند | P1 |
| 4 | Service Key in beauty_center_services | No service_key column, only name string | Mapping via SERVICES dict guessed | Direct service_key column for exact Mirror link | Medium - اتصال دقیق‌تر | P1 |
| 5 | Bale Mirror flow | bot.py has no mirror handlers, only beauty_centers owner/admin + reservations | Only web has mirror | Bale flow: service selection -> style -> photo -> result -> centers -> reserve reuse generic_service | Medium - کاربر Bale نمی‌تواند از آینه استفاده کند | P1 |
| 6 | Discount per service | beauty_center_discounts no service_id | General discount | Discount linked to service | Low - می‌توان با عمومی ادامه داد | P1 |
| 7 | Instagram/Logo | beauty_centers no instagram, logo_path | Only image_path | Separate logo + instagram | Low - می‌توان با description ادامه داد | P2 |
| 8 | Sample Image Resolution | static/services/* 520x360 15-32KB | Medium quality | 800+ high quality | Low - برای thumbnail کافی | P2 |

### 9.4 پیشنهاد سناریوی نهایی — User → Mirror → Service → Beauty Center → Service Offer → Reservation

**Flow لوکس پیشنهادی (با ساختار فعلی قابل پیاده‌سازی):**

```
1. User وارد /analysis/mirror/ می‌شود
   - 4 کارت لوکس: ابرو (PMU), ناخن (Nail), رنگ مو (Hair Color), لب (Lip PMU) — از service_catalog
   - هر کارت: title فارسی, description, meta, image sample, badge فعال/جدید, CTA ورود

2. انتخاب خدمت -> /analysis/mirror/{slug}
   - نمایش 5 مدل هر خدمت با تصویر نمونه 520x360 + label + summary + why + do/avoid
   - انتخاب مدل + change_level (very_natural, medium, clear)
   - CTA ادامه به آپلود

3. آپلود عکس -> /{slug}/upload
   - Upload zone with preview + laser scan + file name
   - Sample image مناسب (upload_sample.jpg) + guide (دست و ناخن‌ها داخل قاب etc.)
   - Client-side checks + POST /{slug}/validate-photo -> local_quality_report or check_photo_quality AI
   - Error message if invalid

4. نتیجه آماده‌سازی -> result board
   - Preview عکس واقعی آپلود شده with cache
   - Simple analysis card: تایید اولیه عکس (quality.message), مدل انتخابی (style.icon+label+short_reason+change_label), محدوده تغییر (detection.method)
   - Final choice board: مدل نهایی از انتخاب مرحله اول (Single Source of Truth), hidden fields photo_filename, final_style, change_level
   - CTA ادامه به طراحی عکس نهایی (نیاز به login)

5. طراحی عکس نهایی -> /{slug}/final (login required)
   - Generation: generic_service.generate_final_design -> service_image_generation.generate_final_design with mask gate (coverage, real_mask), provider chain (configured_image_providers), prompt (build_design_prompt with preservation), _save_constrained_provider_output with validation, fallback generate_guided_design truthful
   - Validation: validate_masked_output in_mask_diff, outside_mask_diff, visible_in_mask_change, outside_preserved
   - Result: Before/After with original + final, service/style labels, AI status, provider, model, validation, do/avoid, interest question bti-final-interest (آیا می‌خواهید این خدمت را انجام دهید؟ Lead vs View), centers suggestions enrich with mirror_score/tags/match reason, consultant invite + chat POST /{slug}/consultant with build_consultant_context
   - Centers: 3 کارت پیشنهادی (یا waitlist if no center with demand count), each with image, name, type_label, city/region, match reason, tags, CTA رزرو/مشاهده مرکز, link to all centers with service filter

6. انتخاب سالن -> /beauty-centers?service={service_filter}&city={user_city} or /beauty-centers/<slug>
   - List: filters q, city, category, type, service, price_level + featured 6 + related + beauty_stats + noindex if q
   - Detail: header with logo+cover+name+type+category+city+rating+status+featured badge+CTA reserve/message, services as luxury cards (icon, name, description 1 line, duration_label, price_label, portfolio filtered by service_key, discount badge, is_active, CTA مشاهده نمونه‌کار/رزرو این خدمت/مشاوره), gallery filtered, hours, feedback, stats, disclaimer

7. کارت خدمت سالن (Service Offer) — پیشنهادی لوکس:
   - هر کارت خدمت: icon, name (e.g., "بالیاژ کاراملی"), short description 1 line, duration (e.g., "1 ساعت و 30 دقیقه"), price (e.g., "از 1.500.000 تا 2.500.000" or "قیمت پس از بررسی"), portfolio 1-3 images with service_key, discount (e.g., "تخفیف 20% تا 2 روز"), is_active, is_featured_service badge, CTA "رزرو این خدمت" (primary) + "مشاوره" (secondary) + "مشاهده نمونه‌کار"

8. رزرو -> /beauty-centers/<slug>/reserve?service_id=&final_design_id=&service_key=&selected_style=
   - GET: service detail + slots via get_available_slots + calendar via get_calendar_month + today Jalali
   - POST: create_reservation with service_id, date, time, user_note, final_design_id, service_key, selected_style — BEGIN IMMEDIATE slot check — status pending — notify_new_reservation — redirect to my_reservations
   - My Reservations: my_reservations.html with status_css (pending, confirmed, completed, cancelled), can_cancel, weekday label

9. Lead / Conversation -> بعد از رزرو یا اگر مرکز نبود waitlist
   - Waitlist: buti_ai_waitlist (phone, city, service_type) + buti_ai_service_demand (city, service_type, dedupe_key)
   - Conversation: beauty_center_conversations UNIQUE(center_id,user_id) + messages + feedback
   - Events: beauty_center_events for analytics

**اگر Flow بهتری پیدا شد:** همین Flow بهترین است — ساده, لوکس, قابل فهم, با ساختار فعلی قابل پیاده‌سازی — فقط Portfolio categorization برای کارت خدمت لوکس نیاز به 1 ستون دارد.

### 9.5 سناریوی پنل سالن — دقیقاً چه منوهایی لازم است؟

**P0 ضروری (با ساختار موجود):**
1. نمای کلی: آمار views, contact_clicks, analysis_impressions, price_inquiry_clicks, reservations pending/confirmed, conversations unread, feedback avg + وضعیت status, listing_expired, promotion_active
2. اطلاعات سالن: name, category, center_type, city, region, address_summary, business_phone, salon_phone, display_phone_choice, contact_time, description, image_path (کاور) — via update_owner_center
3. خدمات: list get_center_services + add/update/delete + price_min/max + duration + is_active + sort_order — via pricing/services
4. ساعات کاری: 7 روز هفته with open_time, close_time, is_closed, slot_minutes — via save_working_hours
5. تصاویر/نمونه‌کار: save_center_image with validation — فعلاً عمومی، پیشنهادی با service_key
6. رزروها: owner_list + owner_action confirm/reject/complete + calendar + slots + notify
7. پیام‌ها/مشتری‌ها: owner_conversations + messages + unread count
8. آمار: beauty_stats

**P1 مهم (با Extend کم):**
9. نظرات/امتیاز: feedback list + summary
10. آگهی/تبلیغ: promotion availability + purchase + renew + Featured Service (promotion with service_id)
11. نمونه‌کار بر اساس خدمت: portfolio with service_key filter

**منوها:** 8 منوی P0 + 3 منوی P1 = 11 منو — ساده + لوکس، نه شلوغ — هر منو یک صفحه با کارت‌های لوکس

### 9.6 سناریوی آگهی خدمات — آیا «آگهی بر اساس خدمت» مدل مناسبی است؟ چرا؟

**YES — مدل مناسبی است:**

- **کاربر:** مستقیم خدمت مورد نظر را با نمونه‌کار و قیمت می‌بیند — تصمیم سریع، UX لوکس — اثبات: Mirror already filters centers by service_key and shows mirror_match_reason — اگر هر خدمت سالن کارت مستقل داشته باشد، کاربر "ناخن فرنچ در مشهد" را مستقیم می‌بیند
- **صاحب سالن:** می‌تواند خدمات فعال/غیرفعال، Featured، تخفیف برای هر خدمت جدا مدیریت کند و روی خدمات پول‌ساز تمرکز کند — اثبات: beauty_center_services has is_active, sort_order, price — با اضافه کردن is_featured_service + service_key می‌تواند Featured Service داشته باشد
- **Giso:** هر خدمت یک inventory قابل فروش — Featured Service, Promotion with service_id, تخفیف per service, تبلیغ هدفمند بر اساس service_key, پیشنهاد بر اساس Mirror result — اثبات: beauty_center_promotions with package_key, amount, transaction_key — می‌تواند با service_id گسترش یابد — مدل درآمدی بهتر از آگهی کلی

**مقایسه:**
- آگهی عمومی: یک مرکز با 20 خدمت شلوغ — کاربر باید بگردد — ارزش تجاری کم
- آگهی بر اساس خدمت: هر خدمت کارت لوکس با نمونه‌کار همان خدمت + قیمت + پیشنهاد + CTA — کاربر سریع تصمیم می‌گیرد — سالن قابل تمرکز — Giso قابل پولی شدن

**نتیجه:** مدل خدمت‌محور **توصیه می‌شود**.

### 9.7 سناریوی درآمدی — چه چیزهایی قابلیت پولی شدن دارند؟

| قابلیت | الان وجود دارد؟ | قابلیت پولی شدن | اولویت | توضیح |
|---|---|---|---|---|
| Promotion برای کل مرکز | YES - beauty_center_promotions | YES - High | P0 - موجود | بسته‌های 7/30 روزه، مبلغ، transaction_key |
| Featured Center (is_featured, sort_order) | YES | YES - High | P0 - موجود | جایگاه ویژه در لیست + Mirror پیشنهادی |
| Featured Service (خدمت خاص Featured) | PARTIAL - needs service_id in promotions | YES - High | P1 - مهم | سالن برای خدمت پول‌ساز پول بیشتر می‌دهد — با اضافه کردن service_id به promotions |
| Discount برای خدمت خاص | PARTIAL - beauty_center_discounts general | YES - Medium | P1 - مهم | تخفیف 20% برای بالیاژ کاراملی — با link to service_id |
| جایگاه ویژه بر اساس service_key (Mirror) | YES - _enrich_generic_centers score + featured | YES - High | P0 - موجود | سالن‌های Featured + has_service + city_match + feedback score در Mirror پیشنهادی اول |
| پیشنهاد بر اساس نتیجه Mirror | YES - enrich with mirror_match_reason | YES - Very High | P0 - موجود | هسته محصول — کاربر بعد از Mirror مستقیم به سالن همان خدمت می‌رود — conversion بالا |
| رزرو با final_design_id | YES - reservation with final_design_id | YES - High | P0 - موجود | Lead با AI result — ارزش برای سالن |
| نمونه‌کار بر اساس خدمت (Portfolio) | PARTIAL - needs service_key in images | YES - Medium | P1 - مهم | سالن با نمونه‌کار قوی ناخن می‌تواند بیشتر جذب کند — قابل Featured |
| تبلیغ هدفمند (city+service+price_level) | YES - list_public_centers filters | YES - Medium | P2 - بعداً | بعد از P0,P1 — نیاز به Analytics |

**چه چیزهایی واقعاً ارزش دارد:**
- P0: Promotion مرکز + Featured Center + پیشنهاد Mirror + رزرو با final_design_id — همین الان درآمد دارد
- P1: Featured Service + Discount per service + Portfolio per service — ارزش بالا، با 1-2 ستون قابل پیاده‌سازی
- P2: تبلیغ هدفمند پیچیده — بعداً

**چه چیزهایی فعلاً اضافه:**
- Instagram feed, Logo جدا, Sample Images 800+ — Low value — P2

### 9.8 جدول Reuse — چه چیزهایی از ساختار موجود استفاده می‌شوند؟

| قابلیت | ساختار موجود | قابل استفاده مستقیم؟ | نیاز به تغییر؟ | فایل/ماژول |
|---|---|---|---|---|
| Beauty Center مدل | beauty_centers 20+ fields + additive migrations | YES | NO | `giso/beauty_centers/schema.py` |
| ثبت سالن | register + _normalize_fields + SERVICES + CATEGORY_SERVICES | YES | NO (UI بهبود Low) | `routes.py: register`, `services.py` |
| وضعیت تأیید | STATUS_FA + admin_set_status + bot_handlers | YES | NO | `services.py: STATUS_FA`, `bot_handlers.py` |
| تماس/آدرس | business_phone, salon_phone, city, region, address, contact_time | YES | NO | `schema.py` |
| تصاویر عمومی | beauty_center_images + save_center_image validation | YES | NO | `schema.py`, `services.py` |
| نمونه‌کار بر اساس خدمت | فقط عمومی، بدون service_key | PARTIAL | YES - Add service_key to images | `schema.py: beauty_center_images` |
| خدمات سالن | beauty_center_services: name, category, description, duration, price_min/max, is_active, sort_order | YES | PARTIAL - Add service_key + is_featured_service | `pricing/schema.py`, `pricing/services.py` |
| قیمت | price_level, starting_price, service price_min/max | YES | NO | `services.py: PRICE_LEVELS` |
| ساعات کاری | working_hours + save_working_hours | YES | NO | `pricing/services.py` |
| فعال/غیرفعال/Featured | is_active, is_featured, status, listing_expires_at, promotion_active | YES | NO | `schema.py` |
| امتیاز/نظر | feedback + summary | YES | NO | `schema.py`, `services.py` |
| رزرو + final_design_id | reservations with final_design_id, service_key, selected_style + BEGIN IMMEDIATE + snapshot | YES | NO - کامل | `reservations/schema.py`, `services.py`, `routes.py: reserve` |
| پیام | conversations + messages UNIQUE | YES | NO | `schema.py`, `services.py` |
| Promotion | promotions + is_featured + purchase/renew | YES | PARTIAL - Add service_id for Featured Service | `schema.py`, `services.py` |
| تخفیف | discounts | YES | PARTIAL - Link to service | `schema.py` |
| پنل سالن اطلاعات | update_owner_center + owner_dashboard | YES | NO | `routes.py: owner_dashboard` |
| پنل سالن خدمات | add/update/delete services | YES | PARTIAL - Add service_key | `pricing/services.py` |
| پنل سالن تصاویر | save_center_image | YES | PARTIAL - Add service_key | `services.py` |
| پنل سالن رزروها | owner_list + owner_action + calendar + slots | YES | NO | `reservations/routes.py` |
| کاربر پیدا کردن سالن | list_public_centers filters + featured + related | YES | NO | `routes.py: list_centers` |
| کاربر خدمات سالن | _center_services_for_display + detail | YES | PARTIAL - Needs service_key filter | `routes.py: center_detail` |
| Mirror نتیجه | buti_ai routes + generic_service + service_image_generation + validation | YES | NO - کامل بعد Fix | `giso/buti_ai/*` |
| سالن پیشنهادی Mirror | _enrich_generic_centers score+tags+match reason | YES | NO | `giso/buti_ai/routes.py` |
| service_key | service_catalog.beauty_center_service + candidate + reservation | YES | NO | `service_catalog.py`, `generic_service.py` |
| selected_style | STYLES + candidate + reservation + credits | YES | NO | `final_design.py STYLES` |
| final_design_id | save_final_design -> candidate -> reservation | YES | NO | `giso/buti_ai/services.py`, `reservations/services.py` |
| User Panel History | analyses table but not mirror | PARTIAL | YES - New module mirror.py reuse analyses pattern | `panel_user/modules/analyses.py` |
| Bale Mirror flow | No flow | NO | YES - New handlers reuse generic_service | `giso/bot.py`, `bot_handlers.py` |

**Reuse > Extend > New:** 80% Reuse مستقیم، 20% Extend با 1-2 ستون additive، 0% New Architecture لازم نیست.

### 9.9 DB Impact — آیا DB نیاز به تغییر دارد؟

**برای P0 (ضروری):** NO — هیچ تغییر DB لازم نیست — با ساختار فعلی Flow لوکس قابل پیاده‌سازی است

**برای P1 (مهم) — پیشنهادی additive:**

| چه فیلدی؟ | در کدام جدول؟ | چرا؟ | آیا می‌توان بدون تغییر انجام داد؟ |
|---|---|---|---|
| `service_key TEXT DEFAULT ''` | `beauty_center_services` | اتصال دقیق خدمت سالن به Mirror service_key (brow, nail, hair_color, lip_shading) — الان فقط name string حدسی | می‌توان بدون تغییر با name mapping ادامه داد ولی با service_key دقیق‌تر — توصیه: اضافه شود via ALTER TABLE ADD COLUMN + index (مثل ai_credits fix d8dc7ef) |
| `service_key TEXT DEFAULT ''` | `beauty_center_images` | نمونه‌کار بر اساس خدمت — عکس ناخن فرنچ فقط برای خدمت ناخن | می‌توان بدون تغییر با description ادامه داد ولی با service_key UX لوکس‌تر — توصیه: اضافه شود |
| `is_featured_service INTEGER DEFAULT 0` | `beauty_center_services` | Featured Service — خدمت خاص Featured | می‌توان بدون تغییر با sort_order=0 + promotion مرکز ادامه داد — Low |
| `service_id INTEGER DEFAULT 0` یا `service_key TEXT` | `beauty_center_promotions` | Featured Service Promotion — promotion برای خدمت خاص | می‌توان بدون تغییر با promotion مرکز ادامه داد — P1 |
| `service_id INTEGER` | `beauty_center_discounts` | تخفیف برای خدمت خاص | می‌توان بدون تغییر با عمومی ادامه داد — P1 |
| `logo_path TEXT`, `instagram TEXT` | `beauty_centers` | لوگو جدا، اینستاگرام | می‌توان بدون تغییر با image_path/description ادامه داد — P2 |

**اگر با ساختار موجود قابل انجام است، تغییر DB پیشنهاد نده:** برای P0 قابل انجام است — برای P1 لوکس کامل 2 ستون additive پیشنهاد می‌شود — migration additive کم‌ریسک.

### 9.10 فایل‌ها و ماژول‌های درگیر — مسیر دقیق

**Beauty Centers Core:**
- `giso/beauty_centers/__init__.py` Blueprint
- `giso/beauty_centers/schema.py` — beauty_centers, images, services, working_hours, conversations, messages, feedback, promotions, discounts, events, expiry_notices, reports + migrate_beauty_center_tables()
- `giso/beauty_centers/services.py` — CENTER_CATEGORIES, CENTER_TYPES, CATEGORY_CENTER_TYPES, CATEGORY_SERVICES, SERVICES (20 keys including brow, nail, lip_shading, hair_color), PRICE_LEVELS, STATUS_FA, DISCLAIMER, decorate_center(), get_center(), get_center_by_slug(), get_owner_center(), list_public_centers(), recommended_centers(), create_center(), update_owner_center(), save_center_image(), etc.
- `giso/beauty_centers/routes.py` — list_centers (filters q, city, category, type, service, price_level, analysis_id, featured, related, beauty_stats, noindex), center_detail (increment_view, _center_services_for_display, _center_hours_for_display, feedback, active_discount), register, owner_dashboard, _owner_panel_context, _service_price_label, _service_duration_label, _center_services_for_display, _center_hours_for_display, _remove_saved_image
- `giso/beauty_centers/panel_admin.py` — admin routes
- `giso/beauty_centers/bot_handlers.py` — beauty_admin_menu_kb, beauty_admin_menu_text, handle_beauty_owner_callback, handle_beauty_admin_callback, _center_card, _center_kb, show_centers_paged, handle_beauty_admin_text
- `giso/beauty_centers/pricing/schema.py` — beauty_center_services, beauty_center_working_hours + migrate_pricing_tables()
- `giso/beauty_centers/pricing/services.py` — get_center_services, add_service, update_service, delete_service, get_working_hours, save_working_hours, _clean_service, _clean_working_day, _coerce_int, _coerce_flag, _coerce_time
- `giso/beauty_centers/reservations/schema.py` — beauty_center_reservations with final_design_id, service_key, selected_style + indexes
- `giso/beauty_centers/reservations/services.py` — get_available_slots, get_calendar_month, _build_slots, _active_bookings, _is_available, create_reservation with BEGIN IMMEDIATE + snapshot + final_design_id/service_key/selected_style, _transition, confirm_reservation, reject_reservation, complete_reservation, cancel_by_user, get_center_reservations, get_user_reservations, _with_derived, _date_weekday_label, _STATUS_LABELS
- `giso/beauty_centers/reservations/routes.py` — reservations_bp, slots, calendar, reserve (GET service+slots+calendar+Jalali, POST create_reservation with final_design_id), owner_list, owner_action (confirm/reject/complete + notify), my_reservations (status_css, can_cancel, weekday), user_cancel
- `giso/beauty_centers/reservations/bot_handlers.py` — handle_reservation_bot
- `giso/beauty_centers/reservations/notifications.py` — notify_new_reservation, notify_user_confirmed, notify_user_rejected
- `giso/beauty_centers/templates/beauty_centers/` — list.html, detail.html, register.html, owner_dashboard.html, reserve.html, my_reservations.html, admin.html, chat.html, _analysis_cta.html, _card.html
- `giso/beauty_centers/static/` — beauty_centers.css, beauty_centers.js

**Beauty Mirror:**
- `giso/buti_ai/__init__.py` — buti_ai_bp url_prefix=/analysis/mirror
- `giso/buti_ai/service_catalog.py` — SERVICE_EYEBROW, SERVICE_NAIL, SERVICE_HAIR_COLOR, SERVICE_LIP, SERVICE_SLUGS, SERVICE_CATALOG 4 services with title, short_title, icon, badge, tag, description, meta, image, sample_dir, upload_sample, beauty_center_service, status active, supported_service_keys(), service_for_slug(), slug_for_service(), get_service_meta(), mirror_services()
- `giso/buti_ai/routes.py` — mirror_home, eyebrow_wizard, eyebrow_upload, eyebrow_model_selection, eyebrow_finalize_choice, eyebrow_final_design, eyebrow_final_retry, generic_service_wizard, generic_service_upload, generic_service_model_selection, generic_service_validate_photo, generic_service_finalize_choice, generic_service_final_design, generic_service_centers, generic_service_uploaded_file, eyebrow_centers, generic_service_consultant_chat, eyebrow_consultant_chat, _new_service_candidate_key, _is_active_new_service, _store_new_service_candidate, _get_new_service_candidate, _rebuild_new_service_candidate_from_finalize_form, _update_new_service_final_selection, _enrich_generic_centers, _active_generic_centers, _service_center_label
- `giso/buti_ai/generic_service.py` — SERVICE_MODULES, CHANGE_LEVELS, service_module(), normalize_change_level(), normalize_model_key(), initial_form_values(), build_result() (quality+detection+ai_analysis+short_reason+do/avoid+preview), process_service_submission() (save_eyebrow_photo with prefix, check_photo_quality AI first fallback local, detect_regions, analyze_*_photo AI first fallback, build_result, save_mirror_session, flash), build_final_candidate(), source_image_path(), generate_final_design() via service_image_generation, uploaded_root()
- `giso/buti_ai/service_image_generation.py` — SERVICE_CONSTRAINTS (lip_shading, nail, hair_color with safe_name, status, message, fallback_message, min_in_ratio, max_out_ratio, max_mask_coverage, accept_fallback_mask, mask_error), ServiceImageGenerationError, _source_path, _mask_path_and_info, _safe_mask_for_real_ai (coverage, real_mask, is_fallback), _fit_to_size, _validation_ok, _save_constrained_provider_output (decode, fit, composite with mask, validate, save, meta), _prepare_png_image_and_mask, _data_uri, _call_cloudflare_flux, _call_cloudflare_inpainting, _call_openai_image_edit, _call_generic_multipart, _call_json_image, _call_provider, generate_final_design() with providers chain, mask check, attempts, fallback truthful
- `giso/buti_ai/ai_models.py` — TASK_EYEBROW_ANALYSIS, TASK_EYEBROW_IMAGE_DESIGN, TASK_NAIL_IMAGE_DESIGN, TASK_LIP_IMAGE_DESIGN, TASK_HAIR_COLOR_IMAGE_DESIGN, TASK_MIRROR_OUTPUT_VALIDATION, IMAGE_DESIGN_TASK_KEYS, VISION_TASK_KEYS, TASK_DEFS 5 tasks 3 slots each, SERVICE_IMAGE_TASK_MAP, AI_MODEL_ASSIGNMENTS_SQL, init_buti_ai_model_assignments, save_model_assignment, list_model_assignments, assignment_map, provider_model_options, panel_slots_context, configured_vision_chain, repair_legacy_cloudflare_eyebrow_image_slots, etc.
- `giso/buti_ai/image_validation.py` — validate_masked_output (in_mask_diff_ratio, outside_mask_diff_ratio, mask_coverage_ratio, visible_in_mask_change>=0.005, outside_preserved<=0.035)
- `giso/buti_ai/consultant.py` — build_consultant_context(service_key, candidate, generation) with service_label, style_label, change_label, short_reason, do, avoid, detection_method, mask_real, mask_coverage, is_ai_generated, generation_status, prompt (Service+Style+Analysis+Preview), consultant_invite_text
- `giso/buti_ai/eyebrow/` — 11 files: __init__, ai.py (check_photo_quality, analyze_eyebrow_photo, _call_assigned_vision_json, _call_vision_json), centers.py (BEAUTY_CENTER_BROW_SERVICE, active_eyebrow_centers, enrich_eyebrow_center_suggestions, user_default_city, user_default_phone), final_design.py, flow.py, image_generation.py (mature chain), landmarks.py (detect_eyebrow_regions 857 lines, ensure_eyebrow_mask, proportional_fallback_regions, _detect_with_mediapipe, _detect_with_opencv, _detect_with_dark_pixels), options.py (CHANGE_LEVELS, EYEBROW_STYLES, normalize), preview.py, prompts.py (PHOTO_QUALITY_PROMPT, eyebrow_analysis_prompt), result.py, upload.py (EYEBROW_UPLOAD_DIR, save_eyebrow_photo, missing_photo_status)
- `giso/buti_ai/nail/final_design.py` — SERVICE_KEY=nail, UPLOAD_DIR, FINAL_DIR, DEFAULT_STYLE=nude_minimal, STYLES 5, _image_size, _call_vision_json, check_photo_quality AI+fallback, analyze_nail_photo AI+fallback, local_quality_report 160px, _nail_boxes, _detect_nail_boxes_by_color, _nail_contrast_score, detect_regions, ensure_mask, _source_path, _draw_style_overlay, build_design_prompt, generate_guided_design (pillow_nail_overlay_v1)
- `giso/buti_ai/hair_color/final_design.py` — similar + _fallback_hair_detection, _try_detect_hair_by_color with face protection ellipse, detect_regions, ensure_mask, refine_detection_for_style (face_frame two narrow side locks), _mask_for_size, build_design_prompt, generate_guided_design (pillow_hair_color_overlay_v1)
- `giso/buti_ai/lip/final_design.py` — similar + _fallback_lip_detection, _try_detect_lip_by_color with red_dominance/pink_balance + relaxed thresholds 0.002-0.12 after fix, detect_regions, ensure_mask, _mask_for_size, build_design_prompt, generate_guided_design (pillow_lip_overlay_v1)
- `giso/buti_ai/nail/prompts.py`, `hair_color/prompts.py`, `lip/prompts.py` — PHOTO_QUALITY_PROMPT, *_analysis_prompt, *_PROMPTS 5 prompts with preservation
- `giso/buti_ai/templates/buti_ai/` — mirror_home.html (4 cards), generic_service_wizard.html (model selection + upload with preview/laser/guide/sample), generic_final_design.html (Before/After, service/style/change, AI status, provider, validation, do/avoid, bti-final-interest Lead vs View, bti-final-centers with center_suggestions, bti-final-consultant + bti-final-consultant-chat with fetch POST /consultant), eyebrow_wizard.html, eyebrow_final_design.html, _analysis_mirror_card.html, etc.
- `giso/buti_ai/static/` — buti_ai.css, buti_ai.js, brows/*, services/nail/*, services/hair_color/*, services/lip_shading/* 520x360 sample images

**Panels:**
- `giso/panel/__init__.py` Blueprint, `giso/panel/routes.py`, `giso/panel/modules/` — dashboard.py, ai.py (save_beauty_mirror_model, panel_slots_context beauty_mirror), finance_overview.py (beauty_revenue from promotions), notifications/core.py (beauty_centers events center_new, center_status, report), users.py, etc.
- `giso/panel_user/__init__.py`, `giso/panel_user/routes.py`, `giso/panel_user/modules/` — overview.py, analyses.py (hair/skin analyses, not mirror), profile.py (get_owner_center), wallet.py, etc.
- `giso/panel/modules/permissions.py`, `giso/panel_user/permissions.py` — is_admin_user, current_user_role, USER_MODULES

**Bot:**
- `giso/bot.py` — 7000+ lines, _profile_inline_kb has_beauty_center, get_owner_center, handle_beauty_owner_callback, handle_beauty_admin_callback, handle_reservation_bot, auto_configure_for_provider, migrate_beauty_center_tables
- `giso/bot_states.py`, `giso/bot_helpers.py`, `giso/bot_user_actions.py`, etc.

**Credits/Wallet:**
- `giso/ai_credits.py` — ledger with service_key, selected_style, idx_ai_credit_ledger_service + ALTER TABLE ADD COLUMN migration
- `giso/wallet.py` — get_wallet_balances

**Base/Config:**
- `giso/base.py` — get_giso_db_conn, normalize_phone, gregorian_to_jalali
- `giso/config.py` — Config.GISO_DIR, UPLOAD_DIR, data/uploads/buti_ai/{service}
- `giso/app.py` — Flask app 5001, register blueprints

---

## 10. Plan + Scope Lock — اگر قرار باشد سناریو پیاده‌سازی شود

### 10.1 Request interpretation (طبق giso-dev/SKILL.md)

- **Restated goal:** طراحی سناریوی Beauty Center / پنل سالن و آگهی خدمات بر اساس ساختار فعلی Giso، با تمرکز بر «آگهی ← خدمت سالن» به جای آگهی عمومی شلوغ، با UX لوکس و ساده: Mirror -> Service -> Beauty Center -> Service Offer -> Reservation، با Reuse > Extend > New، بدون تغییر کد فعلاً (Read-Only)
- **Domain:** Beauty Centers + Beauty Mirror + Panels + Reservations + Bale Bot
- **Surface:** Website (site / user panel / admin panel) + Bot (Bale user/admin) + DB
- **Layer:** UI (templates, static) + Logic (services, routes) + Schema (DB) + AI (provider, prompt) + Bot + Notification
- **Expected behavior:** کاربر راحت‌تر خدمت مورد نظر را با نمونه‌کار و قیمت پیدا کند، صاحب سالن خدمات را ساده مدیریت و Featured کند، Giso درآمد از Featured Service/Promotion/Discount
- **Assumptions (low-risk):** ساختار فعلی برای P0 کافی است، برای P1 لوکس 2 ستون additive کافی است، Bale Mirror flow قابل reuse از analysis pattern، هیچ New Architecture لازم نیست
- **Clarification:** اگر ابهام بود، Code Truth اولویت دارد

### 10.2 Freshness

```
Freshness: HEAD=a18dcf6 branch=arena/01a0eecf-giso4 working-tree=clean
Graph: STALE (built at 2026-09-27 vs HEAD a18dcf6)
Docs: FRESH (updated 2026-09-29) ولی شاخه داخلش arena/01a0e0b8-giso4 قدیمیه — STALE
Memory: STALE (last update 2026-09-27)
```

### 10.3 Current state & real problem location

- **Where problem lives:** 
  - Portfolio categorization: `giso/beauty_centers/schema.py:67 beauty_center_images` no service_key — file evidence `CREATE TABLE beauty_center_images (id, center_id, image_path, sort_order)`
  - Featured Service: `beauty_center_services` no is_featured_service, `beauty_center_promotions` no service_id — file evidence `pricing/schema.py` + `services.py: purchase_center_promotion`
  - User Panel Mirror History: `panel_user/modules/analyses.py` only hair/skin, no mirror — file evidence `ls giso/panel_user/modules/` + `grep -rn buti_ai`
  - Bale Mirror flow: `giso/bot.py` grep buti_ai only auto_configure — no mirror handlers — file evidence `grep -n beauty_center|buti_ai|mirror giso/bot.py`
  - Service Key link: `beauty_center_services` no service_key column — file evidence `pricing/schema.py: SELECT id,center_id,name,category...`
- **Divergences found:** PROJECT_GUIDE says branch arena/01a0e0b8-giso4 but current arena/01a0eecf-giso4 — STALE, GISO_GUIDE says bot.py 7422 lines but current maybe different — STALE, Graph built at 2026-09-27 vs HEAD a18dcf6 — STALE

### 10.4 Architecture & current pattern — Convention table

| Seam | House pattern (with file evidence) | What change will do (if approved) |
|---|---|---|
| DB access | Shared conn helper `get_giso_db_conn` from `giso/base.py`, additive migrations via ALTER TABLE ADD COLUMN in `schema.py:migrate_beauty_center_tables()` + `ai_credits.py:ensure_ai_credit_tables()` | Reuse same helper, add 2 columns via ALTER TABLE ADD COLUMN (service_key in services and images) + index, same pattern as ai_credits fix d8dc7ef |
| Auth/role guard | `login_required` from flask_login + `_user_id()` + `_is_staff()` + `is_admin_user(phone)` + `current_user_role()` in `panel_user/permissions.py` | Reuse same guards for new mirror history page and portfolio management |
| CSRF handling | `{{ csrf_token() }}` in templates + `X-CSRFToken` header in fetch POST /consultant | Follow same form shape for new service forms |
| Notification hook | `panel/modules/notifications/core.py` beauty_centers events center_new, center_status, report + `helpers.py` + `beauty_centers/reservations/notifications.py` notify_new_reservation etc. | Reuse same event registration for new Featured Service promotion events |
| Bot flow | `bot_states.py` state machine + `bot.py` handlers + `beauty_centers/bot_handlers.py` beauty_admin_menu_kb + handle_beauty_owner_callback | Extend state machine with mirror states, reuse generic_service functions, no fork |
| Template/CSS | `buti_ai.css` bti-* classes, `beauty_centers.css`, base.html extends, `templates/buti_ai/generic_final_design.html` with bti-final-interest + bti-final-centers + bti-final-consultant-chat | Extend existing blocks/partials, reuse _analysis_mirror_card.html for mirror history |
| AI call | `ai_models.py` TASK_DEFS + SERVICE_IMAGE_TASK_MAP + configured_vision_chain() + configured_image_providers() + `service_image_generation.py` with mask gate + validation | Reuse same entry points for new mirror history and portfolio — no new provider hardcode |

**Current architecture summary:** 
- Beauty Centers: 10+ tables, SERVICES dict 20 keys, CATEGORY_SERVICES, CENTER_TYPES, STATUS_FA, pricing/services with add/update/delete, working_hours with upsert, reservations with BEGIN IMMEDIATE + snapshot + final_design_id, conversations/messages/feedback/promotions/discounts/events — all in `giso/beauty_centers/` — modular, additive migrations, shared via services.py — Evidence: `schema.py:10-131`, `services.py:30-100`, `pricing/services.py:100-300`, `reservations/services.py:100-400`
- Beauty Mirror: 4 services in `giso/buti_ai/` with service_catalog declarative, generic_service orchestration, final_design.py per service with STYLES+detect+mask+generation+quality AI+analysis AI, service_image_generation with SERVICE_CONSTRAINTS + mask gate, consultant.py with Service+Style+Analysis+Preview — Evidence: `service_catalog.py:20-60`, `generic_service.py:60-120`, `nail/final_design.py:72-200`, `service_image_generation.py:14-50`
- Panels: panel_user + panel with modules, permissions, wallet, notifications — Evidence: `panel_user/modules/profile.py:79 get_owner_center`, `panel/modules/ai.py:737 panel_slots_context`
- Bot: bot.py 7000+ lines with beauty_center owner/admin + reservations handlers, no mirror flow — Evidence: `bot.py:713 _profile_inline_kb`, `bot_handlers.py: beauty_admin_menu_kb`

### 10.5 Dependencies & impact

- **Internal imports touched:** `giso.base.get_giso_db_conn`, `giso.config.Config`, `giso.beauty_centers.services` (SERVICES, CENTER_TYPES, etc.), `giso.beauty_centers.pricing.services` (get_center_services), `giso.beauty_centers.reservations.services` (create_reservation, get_available_slots), `giso.buti_ai.service_catalog` (get_service_meta, slug_for_service), `giso.buti_ai.generic_service` (service_module, process_service_submission, generate_final_design), `giso.buti_ai.ai_models` (TASK_DEFS, configured_vision_chain), `giso.panel_user.permissions` (is_admin_user)
- **Shared DB tables:** beauty_centers, beauty_center_services, beauty_center_images, beauty_center_working_hours, beauty_center_reservations, beauty_center_conversations, beauty_center_messages, beauty_center_feedback, beauty_center_promotions, buti_ai_final_designs, buti_ai_mirror_sessions, giso_ai_providers, ai_credit_ledger
- **Who else reads/writes them:** 
  - beauty_centers: routes.py list_centers, center_detail, register, owner_dashboard + services.py + bot_handlers + panel_admin + reservations
  - beauty_center_services: pricing/services + routes.py _center_services_for_display + reservations
  - reservations: reservations/routes.py + services.py + bot_handlers + buti_ai/routes.py (final_design_id)
  - buti_ai_final_designs: buti_ai/services.py save_final_design + buti_ai/routes.py + future mirror history panel
- **Notification events:** beauty_centers center_new, center_status, report + reservations notify_new_reservation, notify_user_confirmed, notify_user_rejected — via `panel/modules/notifications`
- **AI runtime coupling:** ai_models.py configured_vision_chain + configured_image_providers + ai_brain.py ask_ai_vision + analysis.py _parse_ai_json — used by buti_ai final_design.py check_photo_quality + analyze_*
- **Sibling features sharing code:** 
  - 4 Mirror services share generic_service.py + service_image_generation.py + image_validation.py + consultant.py — changing shared validation breaks all
  - Beauty Centers and Reservations share services.py + pricing/services — changing service table breaks both

### 10.6 Proposed solution — Minimal path, justified by current pattern

**Phase 0 (No code, already done):** Read-Only Audit + Report rp5.md — Done

**If approved for implementation, Phase 1-3 minimal:**

**Phase 1 — P0 (No DB change, Reuse only):**
- Keep all existing tables, no migration
- Ensure Mirror -> Centers -> Reservation flow works with current service_key, selected_style, final_design_id (already works)
- No code change for P0 — just verify

**Phase 2 — P1 (Extend with 2 additive columns, Reuse patterns):**
- Add `service_key TEXT DEFAULT ''` to `beauty_center_services` via ALTER TABLE ADD COLUMN + CREATE INDEX (same pattern as ai_credits.py d8dc7ef) — file: `giso/beauty_centers/pricing/schema.py:migrate_pricing_tables()`
- Add `service_key TEXT DEFAULT ''` to `beauty_center_images` via ALTER TABLE ADD COLUMN + index — file: `giso/beauty_centers/schema.py:migrate_beauty_center_tables()`
- Update `pricing/services.py: _clean_service()` to accept service_key from form if in SERVICES keys
- Update `services.py: save_center_image()` to accept service_key
- Update `templates/beauty_centers/owner_dashboard.html` to add service select dropdown for images (from SERVICES) + service_key select for services (from service_catalog.beauty_center_service mapping)
- Update `routes.py: _center_services_for_display()` to include service_key in display
- Update `templates/beauty_centers/detail.html` to filter gallery by service_key when service card clicked (client-side JS filter)
- Add `is_featured_service` logic via existing sort_order + is_active + promotion — no new column needed for MVP, can use sort_order=0 for featured
- For Featured Service Promotion: Extend `beauty_center_promotions` with `service_id INTEGER DEFAULT 0` OR `service_key TEXT DEFAULT ''` via ALTER TABLE — file: `schema.py` — and update `purchase_center_promotion()` to accept service_id, and `center_promotion_availability()` to check per service

**Phase 3 — P1 (New modules reuse existing patterns, no new architecture):**
- **User Panel Mirror History:**
  - New file: `giso/panel_user/modules/mirror.py` — similar to `analyses.py` — function `list_mirror_results(user_id)` reads `buti_ai_final_designs` where user_id, ordered by created_at DESC, decorates with service_label from service_catalog, style_label from STYLES, plus final image URL via `uploaded_root`
  - Route: `giso/panel_user/routes.py` add `/dashboard/mirror-results` with login_required + _user_id() + is_admin check reuse, render `templates/panel_user/mirror_results.html`
  - Template: `templates/panel_user/mirror_results.html` extends base, reuses `_analysis_mirror_card.html` for each result, with Before/After toggle, CTA reserve/message
  - No new table, no new service, reuse `get_giso_db_conn`, `service_catalog.get_service_meta()`, `generic_service.uploaded_root()`

- **Bale Bot Mirror Flow:**
  - New file: `giso/buti_ai/bot_handlers.py` (or extend `beauty_centers/bot_handlers.py`) with `handle_mirror_service_selection`, `handle_mirror_style_selection`, `handle_mirror_photo` — reuse `generic_service.process_service_submission` and `generate_final_design`
  - States: Add to `giso/bot_states.py` MIRROR_SERVICE, MIRROR_STYLE, MIRROR_PHOTO
  - Menu: Add to `bot.py` main menu "🪞 آینه زیبایی" with 4 service buttons (Eyebrow, Nail, Hair Color, Lip) from service_catalog
  - Flow: User selects service -> selects style (from STYLES keys) -> sends photo -> bot calls `save_eyebrow_photo` with prefix service_key -> check_photo_quality + detect_regions + analyze + generate_final_design (fallback) -> sends Before/After + centers suggestions (reuse _enrich_generic_centers) + reserve link
  - No new AI logic, reuse existing

**Explicitly NOT doing:**
- No refactor of `giso/bot.py` (only local fix via new handlers, per project law)
- No new Blueprint for mirror in bot — reuse existing
- No new reservation system — reuse `beauty_center_reservations` with final_design_id
- No new credit system — reuse `ai_credits.py` + `wallet.py`
- No rewrite of Eyebrow baseline — keep
- No new table for Portfolio if we use service_key column in images (Option A) — minimal
- No Instagram/Logo for P0/P1 — P2
- No complex targeted advertising — P2
- No change to `web/`, `bot_edu/`, `main.py` — LOCKED per skill

### 10.7 Scope lock — اگر پیاده‌سازی تأیید شود

**ALLOWED files (if approved for Phase 2 P1 Extend):**
- `giso/beauty_centers/schema.py` — migrate_beauty_center_tables() add service_key column to beauty_center_images + index + service_id/service_key to promotions/discounts (additive ALTER TABLE)
- `giso/beauty_centers/pricing/schema.py` — migrate_pricing_tables() add service_key column to beauty_center_services + index + is_featured_service (optional)
- `giso/beauty_centers/services.py` — save_center_image() accept service_key, purchase_center_promotion() accept service_id/service_key
- `giso/beauty_centers/pricing/services.py` — _clean_service() accept service_key, get_center_services() include service_key
- `giso/beauty_centers/routes.py` — _center_services_for_display() include service_key, owner_dashboard context include service_key filter
- `giso/beauty_centers/templates/beauty_centers/owner_dashboard.html` — add service select for images + service_key for services
- `giso/beauty_centers/templates/beauty_centers/detail.html` — filter gallery by service_key JS + service cards with portfolio
- `giso/beauty_centers/reservations/services.py` — already has final_design_id/service_key/selected_style — no change for P0, maybe add service_key filter for P1
- `giso/panel_user/modules/mirror.py` — NEW FILE (if approved) — list_mirror_results()
- `giso/panel_user/routes.py` — add /dashboard/mirror-results route
- `giso/panel_user/templates/panel_user/mirror_results.html` — NEW TEMPLATE reuse _analysis_mirror_card
- `giso/buti_ai/bot_handlers.py` — NEW FILE (if approved) — mirror handlers for Bale
- `giso/bot.py` — add mirror menu + state handling (local fix only, per law)
- `giso/bot_states.py` — add MIRROR_* states
- `rp5.md` — already created, plus future implementation reports

**FORBIDDEN (must NOT change):**
- `giso/buti_ai/eyebrow/` for new service development (Baseline law)
- `bot_edu/` — LOCKED without explicit instruction
- `web/` — decoupled from giso
- `main.py` — launcher
- `giso/bot.py` refactor/split — only local fix (per GISO_GUIDE law)
- `giso/analysis.py` — only wrapper, not product logic
- `graphify-out/`, `project_memory/`, `data/`, `.env`, venv, git history
- Any file not listed in ALLOWED — default forbidden

**Shared/caution files inside scope:**
- `giso/beauty_centers/schema.py` + `pricing/schema.py` — shared by all centers, reservations, pricing — migration must be additive + idempotent + tested with existing DB
- `giso/beauty_centers/services.py` — shared by public, owner, admin, bot — change must preserve existing SERVICES, STATUS_FA, validation
- `giso/panel_user/routes.py` — shared by all user panel modules — new route must reuse authz pattern
- `giso/bot.py` — shared by all bot features — mirror menu must not break existing menus

**Data: tables involved / migration needed?**
- Tables: beauty_centers (no change P0, maybe logo/instagram P2), beauty_center_services (add service_key TEXT), beauty_center_images (add service_key TEXT), beauty_center_promotions (add service_id or service_key), beauty_center_discounts (add service_id), buti_ai_final_designs (no change), beauty_center_reservations (already has final_design_id/service_key/selected_style)
- Migration: additive only, via ALTER TABLE ADD COLUMN + CREATE INDEX IF NOT EXISTS, in existing migrate functions, same style as `giso/ai_credits.py:ensure_ai_credit_tables()` and `beauty_centers/schema.py:migrate_beauty_center_tables()`

**Out of scope:**
- Sibling services: marketplace, shop, hair_sale, etc. — not touched
- Web site (port 5000) — decoupled
- Bot_edu — locked
- New AI models/providers — only config via panel, no code
- Instagram/Logo/Sample Images 800+ — P2, not now

### 10.8 Council findings — 4 passes with code evidence

**Architect:**
- Does change sit in right domain folder? YES — Beauty Centers in `giso/beauty_centers/`, Mirror in `giso/buti_ai/`, Panel in `giso/panel_user/`, Bot handlers in `giso/beauty_centers/` or `giso/buti_ai/` — golden rule satisfied — Evidence: `giso/buti_ai/__init__.py` Blueprint, `beauty_centers/__init__.py` Blueprint
- Does it cross layer boundary forbidden? NO — giso->bot_edu no, web↔giso no — Evidence: all imports absolute with `giso.` prefix per GISO_GUIDE law
- Does it add coupling? Minimal — adds service_key column to existing tables, reuses existing helpers — narrower than new table — PASS

**Domain:**
- Does behavior match feature's actual semantics as read from current code? YES — Beauty Center is introduction platform only (DISCLAIMER), not service provider — service listing with price after review matches semantics — Evidence: `services.py:DISCLAIMER`
- Does it match sibling services' behavior for same user action? YES — Mirror flow for 4 services same pattern (model selection -> upload -> quality -> detection -> generation -> validation -> final -> centers -> reservation) — Evidence: `generic_service.py:process_service_submission` + `routes.py:generic_service_final_design`
- Edge cases: empty states (no center -> waitlist + demand count), permission states (owner vs staff vs public), duplicate/conflicting records (UNIQUE(center_id,user_id) for conversations, BEGIN IMMEDIATE for reservations), Persian/RTL (templates dir=rtl, to_persian_digits) — PASS

**Security:**
- AuthN/AuthZ: Which guard protects each new/changed view? `login_required` for reserve, owner_dashboard, my_reservations, mirror final — plus `_user_id()` + `_is_staff()` + `is_admin_user(phone)` + `current_user_role()` — house guard reused — Evidence: `beauty_centers/routes.py: _user_id(), _is_staff()`, `reservations/routes.py: @login_required`
- CSRF on every state-changing form: `{{ csrf_token() }}` in templates + `X-CSRFToken` header in consultant chat fetch — Evidence: `generic_final_design.html` has csrf_token hidden + JS fetch header
- Input validation at boundary: `_normalize_fields()` for centers, `_clean_service()` for services (duration 1-1440, price 0-10B), `_coerce_time()` for working hours, `save_center_image` with MAX_BYTES, MAX_PIXELS, MAX_SIDE, FORMATS — Evidence: `services.py: _normalize_fields, _price_int, _normalize_business_phone`, `pricing/services.py: _clean_service, _clean_working_day`
- Upload path constraints: `save_eyebrow_photo` with upload_dir + prefix service_key + `os.path.abspath` + `startswith(root+os.sep)` check — Evidence: `eyebrow/upload.py:51` + `generic_service.py:source_image_path`
- No secret in logs/errors/UI: `_beauty_route_log` filters token, secret, api_key, authorization, account_id — Evidence: `routes.py: _beauty_route_log`
- Data exposure: public page center_detail only shows published + is_active unless owner/staff — Evidence: `routes.py: center_detail` abort 404 if not published and not owner/staff
- PASS

**Regression:**
- Which sibling features share each touched symbol? 
  - `get_giso_db_conn` shared by all giso modules — change in schema migration affects all — must be additive
  - `list_public_centers` shared by list_centers, mirror final, bot — changing service filter affects all
  - `create_reservation` shared by web reserve + bot + mirror — changing final_design_id handling affects all
  - `validate_masked_output` shared by 4 mirror services — changing thresholds affects all
  - `panel_slots_context` shared by admin AI panel — changing TASK_DEFS affects all mirror services
- Shared DB tables touched: beauty_centers, beauty_center_services, beauty_center_images, beauty_center_reservations, buti_ai_final_designs — who else reads/writes: routes, services, pricing/services, reservations/services, bot_handlers, panel_user, panel
- Notification event changes: beauty_centers center_new, center_status, report + reservations notify_new_reservation — consumers: panel/modules/notifications
- Which existing test files name this feature or its siblings? `giso/tests/test_beauty_centers_*.py` (16 files stage1-16), `test_buti_ai_new_services.py`, `test_buti_ai_phase1.py`, `test_broadcasts_center.py` — minimum set to run
- PASS with caution — all changes additive, no break

**Resolution:** No objection that plan cannot satisfy — all gaps solvable with Reuse + 2 additive columns — Council PASS

### 10.9 Risks

- **Low Risk for P0 (No DB change):** No code change, only verification — no risk
- **Low Risk for P1 Extend (2 columns additive):** ALTER TABLE ADD COLUMN is idempotent, additive, same pattern as previous successful migrations (ai_credits service_key, beauty_centers salon_phone) — risk low, but must test with existing DB with legacy data
- **Medium Risk for Bale Mirror flow:** Adding new states to bot_states.py + new handlers + menu — could break existing bot menus if not careful — mitigate by reusing existing analysis pattern and testing with bot without token (import only)
- **Low Risk for User Panel History:** New module mirror.py reads buti_ai_final_designs — no write, no migration — low risk

### 10.10 Tests to run (if implementation approved)

```
# Targeted tests per test-regression.md
SECRET_KEY=test python -m pytest giso/tests/test_beauty_centers_mvp.py -q
SECRET_KEY=test python -m pytest giso/tests/test_beauty_centers_stage1_categories.py -q
...
SECRET_KEY=test python -m pytest giso/tests/test_beauty_centers_stage10_analysis_integration.py -q
SECRET_KEY=test python -m pytest giso/tests/test_buti_ai_new_services.py -q
SECRET_KEY=test python -m pytest giso/tests/test_buti_ai_phase1.py -q
SECRET_KEY=test python -m pytest giso/tests/test_broadcasts_center.py -q

# Import / boot check
python -c "import giso.beauty_centers.schema; import giso.beauty_centers.services; import giso.buti_ai.service_catalog; import giso.buti_ai.generic_service; import giso.wsgi"

# Feature behavior check
- /beauty-centers?service=nail filter returns only centers with nail in services_json
- /beauty-centers/<slug> shows services with price_label, duration_label, hours
- /analysis/mirror/nail upload -> quality -> detection -> generation -> final with centers + final_design_id
- /beauty-centers/<slug>/reserve?final_design_id=&service_key=&selected_style= creates reservation with snapshot + final_design_id
- /dashboard/beauty-center shows owner stats + services + images + reservations + messages
- /dashboard/mirror-results (new) shows buti_ai_final_designs history with Before/After

# Regression sweep
- Run all giso/tests/test_beauty_centers_*.py (16 files)
- Run giso/tests/test_buti_ai_*.py
- Check Eyebrow still works: /analysis/mirror/eyebrow 200 OK
- Check existing centers still published and searchable
- Check reservations still creatable without final_design_id (backward compat)
```

### 10.11 Regression plan

- After Phase 2 (DB Extend): Test existing centers still load, services still list, reservations still work without service_key (default ''), images still load without service_key
- After Phase 3 (User Panel History): Test existing panel_user modules still work (profile, analyses, wallet, etc.)
- After Phase 3 (Bale Mirror): Test bot imports without token, existing beauty_center owner/admin menus still work, no duplicate state
- Final: Run full beauty_centers test suite + buti_ai tests + import wsgi

### 10.12 Found but not changed

- `PROJECT_GUIDE.md` says branch arena/01a0e0b8-giso4 but current arena/01a0eecf-giso4 — STALE — reported, not changed (per skill law, docs not modified as part of feature change)
- `GISO_GUIDE.md` says bot.py 7422 lines but current maybe different — STALE — reported
- `graphify-out/GRAPH_REPORT.md` built at 2026-09-27 vs HEAD a18dcf6 — STALE — reported
- `giso-dev/` folder exists but is untracked in some envs — should be tracked — reported
- Sample images 520x360 medium quality — per s2 instruction don't create new images now — reported as Low gap, not changed
- Model alignment baby_boomer vs Chrome French etc. — models are market valid, not changed per s2 law

---

## 11. Final Report (for this Read-Only phase)

**What changed:** Nothing — Read-Only Audit per s3 law — only `rp5.md` created

**Why:** To understand existing Beauty Center / Salon Panel / Service Listing structure and design best scenario with minimal change

**Which files:** Only `rp5.md` — ALLOWED FILES = [rp5.md]

**Tests run and results:**
- `ls giso/beauty_centers/` — 10 files + pricing + reservations + templates + static — PASS
- `cat schema.py` — beauty_centers 20+ fields + 10 related tables + additive migrations — PASS
- `cat services.py` — SERVICES 20 keys including nail, hair_color, lip_shading, brow + CENTER_TYPES 7 types + STATUS_FA 6 statuses — PASS
- `cat pricing/services.py` — get_center_services, add_service, update_service, delete_service, working hours upsert — PASS
- `cat reservations/services.py` — create_reservation with BEGIN IMMEDIATE + final_design_id/service_key/selected_style + snapshot — PASS
- `cat buti_ai/service_catalog.py` — 4 services with beauty_center_service mapping — PASS
- `cat buti_ai/generic_service.py` — process_service_submission with check_photo_quality AI first + analyze_* + build_result + save_mirror_session — PASS after s2 fix
- `cat buti_ai/nail/hair_color/lip/final_design.py` — STYLES 5 each, detect_regions reliable True, mask real True, validation ok — PASS after s2 fix
- `grep -rn beauty_center giso/bot.py` — owner/admin + reservations handlers exist, mirror flow missing — Gap reported
- `ls giso/panel_user/modules/` — analyses.py for hair/skin but no mirror.py — Gap reported
- `py_compile` for 5 core files — PASS

**Regression checks:** No code changed, so no regression — Eyebrow, Centers, Reservations, Panels, Bot, AI, Wallet, Auth all intact per code inspection

**Out-of-scope drift:** None — only rp5.md

**Remaining issues:** 3 Medium gaps (User Panel Mirror History, Portfolio categorization by service, Bale Mirror flow) + 5 Low gaps — all documented with Reuse > Extend > New minimal plan

**Suggested follow-ups (not executed without explicit instruction):**
- If approved, implement Phase 2 P1 Extend (2 additive columns) + Phase 3 (mirror history panel + Bale mirror flow) with minimal changes as per Scope Lock
- Run `graphify update .` to refresh GRAPH_REPORT.md (currently STALE) — suggestion only
- Update Project Memory per `project_memory/letta/UPDATE_TEMPLATE.md` with this audit — suggestion only

---

**APPROVAL NEEDED:** "تایید می‌کنی؟"

طبق `giso-dev/SKILL.md` قانون STOP — هیچ کدی تغییر نکرده، فقط `rp5.md` گزارش است. اگر تایید کنی "تایید / بریم / اجرا کن" برای پیاده‌سازی Phase 2 و 3 با Scope Lock بالا، آنگاه Implementation شروع می‌شود.

**Report Path:** `rp5.md` در branch `arena/01a0eecf-giso4` — HEAD a18dcf6 + rp5.md (to be committed)
