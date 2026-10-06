# rp6.md — بررسی و طراحی سناریوی Beauty Center / پنل سالن و آگهی خدمات — Read-Only Audit

تاریخ: 2026-10-07
Branch: arena/01a0eecf-giso4
HEAD: 56fac4b (Create s4.md) + f25c37b (rp6) + 572e7a2 (rp5) — origin HEAD = 56fac4b
Auditor: Arena Agent — giso-dev Skill Workflow — Read-Only, No Code Change
Method: Code is Truth, Reuse > Extend > New, Existing Architecture First
Scope Lock: ALLOWED = [rp6.md] — هیچ کد دیگری تغییر نکرده (Read-Only verbs: بررسی/گزارش/پیشنهاد هرگز فایل تغییر ندهند)

---

## ۰. Request Interpretation & Freshness

**هدف:** بررسی کامل Beauty Center / سالن زیبایی، پنل سالن و آگهی خدمات سالن از روی کد واقعی، طراحی بهترین سناریوی قابل پیاده‌سازی روی ساختار فعلی Giso، بدون تغییر کد، خروجی در rp6.md + ذخیره در GitHub طبق giso-dev/SKILL.md.

**Freshness (Phase-0):**
```
Freshness: HEAD=56fac4b branch=arena/01a0eecf-giso4 working-tree=clean (قبل نوشتن) / dirty (بعد نوشتن فقط rp6.md)
Graph: STALE (Built from commit c9b198cd in graphify-out/GRAPH_REPORT.md vs HEAD 56fac4b)
Docs: STALE (PROJECT_GUIDE updated 2026-09-29 branch arena/01a0e0b8 vs current 01a0eecf, GISO_GUIDE 2026-09-29)
Memory: absent (project_memory/letta/PROJECT_MEMORY.md not present)
Guides: PROJECT_GUIDE.md + GISO_GUIDE.md present, §22-24
```
Graph STALE → فقط grep/import analysis استفاده شد، نه Graph. Docs STALE → Code Truth مرجع.

**Assumptions low-risk:** فارسی RTL کافی، شهر پیش‌فرض مشهد، فیلتر service موجود، Mirror 4 خدمت فعال (eyebrow, nail, hair_color, lip_shading), قیمت با format_toman, رزرو BEGIN IMMEDIATE امن.

---

## ۱. وضعیت فعلی — چه چیزهایی همین الان داریم؟

### ۱.۱ سالن زیبایی — مدل/جدول Beauty Center

**جدول اصلی `beauty_centers` (giso/beauty_centers/schema.py:10-55,  CREATE TABLE + 5 INDEX):**
- id PK AUTOINCREMENT, owner_user_id UNIQUE FK→giso_web_auth.id
- name TEXT 160, slug UNIQUE (seed+secrets), category (hair, skin_face, beauty) → CENTER_CATEGORIES, center_type 7 نوع (salon, hair_center, skin_beauty, independent, nail_center, bridal, licensed_clinic) → CENTER_TYPES
- city TEXT indexed idx_beauty_centers_city, region, address_summary 300, business_phone normalized via normalize_phone, salon_phone, display_phone_choice business/salon, contact_time, description 700
- services_json TEXT '[]' — تگ‌های انتخابی از SERVICES dict (20 کلید)
- image_path کاور, status TEXT DEFAULT pending_review → STATUS_FA 6 وضعیت: pending_review, reviewing, published, rejected, paused, closed
- admin_note, terms_version beauty-centers-v1, terms_accepted_at
- counters: views_count, contact_clicks, analysis_impressions, price_inquiry_clicks
- pricing center-level: price_level economic/standard/premium/on_request, starting_price INTEGER
- expiry/promotion: listing_expires_at, promotion_type, promotion_expires_at, promotion_bumped_at
- flags: is_active, is_featured, sort_order, terms_version
- migration additive: salon_phone, display_phone_choice, last_edit_at, listing_expires_at etc via PRAGMA table_info + ALTER TABLE ADD COLUMN

**SERVICES dict (services.py:30-38):** 20 کلید:
haircut, hair_color, bleach, hair_repair, keratin, straightening, extension, braid, scalp_care, facial, skin_cleansing, skin_hydration, face_care, makeup, hairstyle, brow, lip_shading, lash, nail, bridal — شامل 4 کلید Mirror: brow, nail, lip_shading, hair_color
CATEGORY_SERVICES: hair 9, skin_face 7 (facial, skin_cleansing, skin_hydration, face_care, brow, lip_shading, lash), beauty 7 (makeup, hairstyle, brow, lip_shading, lash, nail, bridal)
CATEGORY_CENTER_TYPES: category→allowed types
CENTER_IMAGE_MAX_BYTES 5MB, MAX_PIXELS 20M, MAX_SIDE 12000, FORMATS JPEG/PNG/WEBP

**جداول مرتبط (10 جدول + pricing 2 + reservations 1):**
- `beauty_center_images` id, center_id FK CASCADE, image_path, sort_order, created_at — INDEX center,sort_order,id — گالری عمومی max 3 (owner_gallery_upload check count+cover), validation save_center_image
- `beauty_center_services` id, center_id, name NOT NULL, category '', description '', duration_minutes 30, price_min 0, price_max 0, is_active 1, sort_order 0, created_at, updated_at legacy — INDEX center,is_active,sort_order — خدمات دقیق با قیمت و مدت
- `beauty_center_working_hours` id, center_id, day_of_week 0=شنبه تا 6=جمعه, open_time '', close_time '', is_closed 0, slot_minutes 30, legacy weekday/is_open sync for NOT NULL + UNIQUE(center_id, weekday) — INDEX unique center,day
- `beauty_center_conversations` id, center_id, user_id, status active/closed, last_message_at, UNIQUE(center_id,user_id) — INDEX center,status,last_message_at + user,status,last_message_at
- `beauty_center_messages` id, conversation_id, sender_user_id, message_text, is_read, is_reported — INDEX conversation,id + conversation,is_read
- `beauty_center_feedback` id, center_id, conversation_id, user_id, response_level, price_level, overall_level, comment, status pending, UNIQUE(conversation_id,user_id) — INDEX center,status,created_at
- `beauty_center_reservations` id, center_id, user_id, user_phone, user_name, service_id snapshot, service_name snapshot 200, service_price_min snapshot, duration_minutes snapshot, reservation_date شمسی YYYY-MM-DD, reservation_time HH:MM, status pending/confirmed/completed/cancelled_user/cancelled_center, user_note 500, center_note, reject_reason, reminded flags, created_at, confirmed_at, cancelled_at, **final_design_id INTEGER DEFAULT 0**, **service_key TEXT DEFAULT ''**, **selected_style TEXT DEFAULT ''** — INDEX center,date,time + user,created_at + status,date — اتصال Mirror کامل
- `beauty_center_promotions` id, center_id, owner_user_id, package_key, amount, starts_at, expires_at, transaction_key UNIQUE, status active — INDEX center,status,expires_at
- `beauty_center_discounts` id, center_id, title, description, discount_value, expires_at, status pending — INDEX center,status,expires_at
- `beauty_center_events` id, center_id DEFAULT 0, event_type, user_id DEFAULT 0, created_at — INDEX event_type,created_at
- `beauty_center_expiry_notices` id, center_id, notice_key UNIQUE
- `beauty_center_reports` id, center_id, reporter_user_id, reason, message, status open — INDEX center,status + status,created_at

**ثبت سالن:** routes.py register GET/POST, fields: name, category, center_type, city, region, address_summary, business_phone, salon_phone, display_phone_choice, contact_time, description, services multi-select 16 max from SERVICES, price_level, starting_price, image. Validation _normalize_fields: category in CENTER_CATEGORIES, center_type in CATEGORY_CENTER_TYPES[category], services in CATEGORY_SERVICES[category], price_level in PRICE_LEVELS, city required, phone normalized.

**وضعیت تأیید:** STATUS_FA 6, admin_set_status with guarded transition via panel_admin.py handle_beauty_status, bot_handlers.py beauty_admin_menu_kb (درخواست‌های جدید, منتشرشده, منقضی و متوقف, وضعیت, اعتبار آگهی, تنظیمات), _center_kb actions review/publish/reject/pause.

**اطلاعات تماس/آدرس/تصاویر/خدمات/قیمت/ساعات/فعال/امتیاز/رزرو/پیام/آگهی:**
- تماس: business_phone, salon_phone, display_phone_choice, contact_time, reveal via center_contact POST intent price_inquiry + increment contact_clicks + reveal_contact()
- آدرس: city indexed, region, address_summary
- تصاویر: image_path کاور + beauty_center_images گالری, media routes center_media, gallery_media with static_root check (Path(Config.GISO_DIR)/static).resolve() + parents check + X-Content-Type-Options nosniff + conditional
- خدمات: SERVICES 20 + CATEGORY_SERVICES + beauty_center_services with price_min/max/duration/is_active
- قیمت: service price_min/max + center price_level/starting_price + _service_price_label with format_toman + duration_label
- ساعات: get_working_hours, save_working_hours BEGIN IMMEDIATE upsert, day_label Persian, time_label, slot_minutes
- فعال/غیرفعال: is_active, listing_expired check listing_expires_at < now, promotion_active check promotion_type+expires_at>now, is_featured+sort_order for featured query 6
- امتیاز: center_feedback_summary response_level/price_level/overall_level score score100 count>=3 label _feedback_label
- رزرو: create_reservation BEGIN IMMEDIATE, _working_day, _service_of, _is_available, _build_slots, _active_bookings, snapshot rule (service name/price/duration copied so later edits never rewrite past), _transition guarded, confirm/reject/complete/cancel_by_user, notify_new_reservation, notify_user_confirmed/rejected via ThreadPoolExecutor _CENTER_NOTIFY_POOL, calendar month get_calendar_month, slots JSON get_available_slots
- پیام: get_or_create_conversation, send_conversation_message, conversation_messages, owner_conversations, user_center_conversations, unread counts, close_conversation, submit_center_feedback
- آگهی/Featured/Promotion: is_featured, sort_order, promotion_type, promotion_expires_at, promotion_bumped_at, beauty_center_promotions, center_promotion_availability, purchase_center_promotion with purchase_nonce _purchase_key, renew_center_listing, process_center_expiry_notifications throttled 10min, discount_service_active, active_discount legacy, _wait_label

### ۱.۲ پنل سالن — قابلیت‌های فعلی

**Owner Dashboard (routes.py owner_dashboard + owner_dashboard.html):**
- Context _owner_panel_context includes USER_MODULES + beauty_center menu, notifications, wallet balances, analysis_count
- Tabs: اطلاعات پایه (name, category, type, city, region, address, phone, contact_time, description, price_level, starting_price, services_json multi-select), خدمات (get_center_services list ordered is_active DESC sort_order ASC id ASC + add_service name required duration 1-1440 price_min/max + update_service + delete_service via pricing/services.py _clean_service), ساعات کاری (get_working_hours + save_working_hours with _clean_working_day day_of_week 0-6 open_time close_time is_closed slot_minutes), تصاویر (save_center_image with format/size validation + gallery upload/delete + main image delete with replacement logic), پیام‌ها (owner_conversations + conversation_messages + close + feedback view), رزروها (owner_list JSON + owner_action POST confirm/reject/complete + calendar + slots + notifications), آمار (views_count, contact_clicks, analysis_impressions, price_inquiry_clicks + beauty_stats centers/views/hair/skin), وضعیت انتشار (status_label, listing_expired, promotion_active, renew, promote, discount POST), گالری max 3

**مدیریت:** update_owner_center with _normalize_fields, set_owner_active, save_center_image, _remove_saved_image

### ۱.۳ کاربر — Flow فعلی

- **پیدا کردن سالن:** /beauty-centers?q=&city=&category=&type=&service=&price_level= — list_public_centers with filters query, city, category, center_type, service, price_level, limit 60, plus featured 6, related via recommended_centers(analysis_id,user_id,city) + analysis_service_tags, noindex if query, beauty_stats
- **خدمات سالن را می‌بیند:** /beauty-centers/<slug> — get_center_by_slug, is_owner/is_staff, increment_view if published not owner/staff, _center_services_for_display (price_label, duration_label), _center_hours_for_display, revealed contact if owner/staff, feedback summary, active_discount, discount_service_active
- **نتیجه Beauty Mirror را می‌بیند:** /analysis/mirror/ mirror_home 4 کارت active (eyebrow, nail, hair_color, lip_shading) با SERVICE_CATALOG title/short_title/icon/badge/tag/description/meta/image/sample_dir/upload_sample, href to /analysis/mirror/{slug} → generic_service_wizard (model selection 5 styles with sample 520x360) → /{slug}/upload (photo upload preview+guide+sample) → process_service_submission (save_eyebrow_photo prefix service_key, check_photo_quality AI first fallback local, detect_regions color segmentation, analyze_*_photo AI first fallback) → build_result (quality+detection+ai_analysis+short_reason+do/avoid) → _store_new_service_candidate session → /{slug}/final (generate_final_design via service_image_generation with mask gate + provider chain + fallback guided composite, validation validate_masked_output, save_final_design with session_id, user_id, service_type, original_filename, final_filename, selected_style, recommended_style, change_level, provider, model, status, prompt_json) → generic_final_design.html: Before/After, service/style/change labels, AI status is_ai_generated, provider, model, validation, do/avoid, interest question bti-final-interest Lead vs View, centers suggestions enrich with mirror_match_reason+mirror_tags+mirror_score, consultant invite+chat POST /{slug}/consultant with build_consultant_context
- **سالن پیشنهادی دریافت می‌کند:** _enrich_generic_centers(service_key, centers, candidate, city) — score: 45 if has_service (service_filter in services), 20 if city_match, 15 if is_featured, up to 20 from feedback score100//5, sorted by -mirror_score, mirror_rank; tags: service_label, همان شهر, feedback label; match reason: "برای اجرای {final_label}، این مرکز به‌عنوان ارائه‌دهنده {service_label} پیشنهاد شده است."
- **وارد صفحه سالن می‌شود:** center_detail + reserve link with final_design_id, service_key, selected_style → /beauty-centers/<slug>/reserve?service_id=&date=&final_design_id=&service_key=&selected_style=
- **رزرو می‌کند:** reserve GET (service_id, date, slots via get_available_slots, calendar via get_calendar_month) + POST (create_reservation with final_design_id, service_key, selected_style snapshot, BEGIN IMMEDIATE, notify_new_reservation) → my_reservations list with status labels, cancel_by_user

### ۱.۴ Beauty Mirror — ارتباط فعلی دقیق (Code Truth)

**جداول Buti AI (buti_ai/schema.py):**
- `buti_ai_sessions` id, user_id, service_type, city DEFAULT مشهد, center_id, conversation_id, status DEFAULT completed, created_at — INDEX user + created DESC
- `buti_ai_waitlist` id, user_id, phone_number, city, service_type, source '', status open, payload_json '', created_at — INDEX city,service_type + service_type,status,created DESC
- `buti_ai_service_demand` id, user_id, city, service_type, source '', status open, dedupe_key '', payload_json '', created_at — INDEX city,service_type + status + UNIQUE dedupe_key WHERE <> ''
- `buti_ai_final_designs` id, session_id, user_id, service_type DEFAULT eyebrow, original_filename, final_filename, selected_style, recommended_style, change_level, provider, model, status DEFAULT created, prompt_json, created_at — INDEX user,created DESC + session — ذخیره نهایی طراحی

**service_key:** در generic_service.py SERVICE_MODULES mapping nail/hair_color/lip_shading → final_design modules, در service_catalog.py SERVICE_CATALOG beauty_center_service mapping: eyebrow→brow, nail→nail, hair_color→hair_color, lip_shading→lip_shading — نگاشت Mirror به Beauty Center service. supported_service_keys() = nail, hair_color, lip_shading. service_for_slug() + slug_for_service().

**selected_style:** 5 استایل per service — eyebrow: natural, powder, microblading, combination, giso_suggested; nail: natural, french, baby_boomer, etc; hair_color: caramel_balayage etc; lip_shading: natural_shading etc — STYLES dict + DEFAULT_STYLE + CHANGE_LEVELS very_natural/medium/clear.

**final_design_id:** candidate dict field final_design_id = design_id از save_final_design → ذخیره در session _new_service_candidate_key(service_key) + FINAL_DESIGN_SESSION_KEY برای eyebrow. در routes.py candidate.pop final_design_id on reset, generation ok and not candidate final_design_id → candidate final_design_id = design_id.

**beauty_center_services:** فعلاً service_key ندارد (فقط name, category) — Gap: نمی‌توان مستقیم service_key→service_id نگاشت کرد مگر با name mapping دستی — برای P1 ADD COLUMN service_key.

**beauty_center_reservations:** final_design_id, service_key, selected_style already implemented — اتصال کامل: رزرو از Mirror با final_design_id, service_key, selected_style snapshot, قابل نمایش در owner_list و my_reservations + _with_derived.

**Flow فعلی:** Mirror result → centers enrich (service_key→beauty_center_service) → list_centers?service={beauty_center_service} → center_detail → reserve?service_id={id}&final_design_id={id}&service_key={key}&selected_style={style} → create_reservation snapshot — PASS.

**قابل استفاده مستقیم:** Mirror 4 خدمت فعال با Quality AI+Detection+Analysis AI+Generation+Validation+Final+Consultant+Interest+Centers enrich+Reservation link — 100% PASS.

**کمبود:** Portfolio per service (images بدون service_key), Featured Service per service (فقط center-level), Service Key column در services, User Panel Mirror History (final_designs موجود ولی نمایش ندارد در panel_user).

---

## ۲. نقاط قوت — چه چیزهایی خوب و قابل استفاده هستند؟

- ماژولار: هر ماژول در پوشه خودش (beauty_centers, pricing, reservations, buti_ai/eyebrow/nail/hair_color/lip) — GISO_GUIDE §11.2
- Additive migrations: PRAGMA table_info + ALTER TABLE ADD COLUMN + CREATE INDEX IF NOT EXISTS + CREATE TABLE IF NOT EXISTS, never DROP/RECREATE — pattern در pricing/schema.py, reservations/schema.py, beauty_centers/schema.py + ai_credits fix
- Shared DB: get_giso_db_conn() from base.py WAL + busy_timeout 5000 + foreign_keys ON — single source truth giso/data/giso.db
- SERVICES dict 20 keys + CATEGORY_SERVICES + CENTER_TYPES + STATUS_FA + PRICE_LEVELS — validation کامل
- Pricing 6 functions exactly: get_center_services, add_service, update_service, delete_service, get_working_hours, save_working_hours — via get_giso_db_conn
- Reservations BEGIN IMMEDIATE transaction + snapshot rule (service name/price/duration copied) + _is_available + _build_slots + _active_bookings + _transition guarded — امن در برابر race condition دو کاربر همزمان
- Mask gate + Validation ضد فریب: validate_masked_output with in_mask_diff_ratio, outside_mask_diff_ratio, service_key — جلوگیری از تغییر کل چهره
- Fallback صادقانه: local_quality_report + guided composite + is_ai_generated flag + provider/model + validation message — هیچ فریب کاربر
- Shared services وب و ربات یک DB, ThreadPoolExecutor _CENTER_NOTIFY_POOL for notifications, CSRF protected forms, owner vs staff guards, static_root check + parents check + nosniff
- Promotion/Expiry throttled 10min + _wait_label + transaction_key UNIQUE + purchase_nonce anti double spend
- Feedback score100 + count>=3 + label + UNIQUE(conversation_id,user_id) — جلوگیری از اسپم
- Enrich scoring 45 has_service+20 city+15 featured+feedback up to 20 + tags + match reason — لوکس و قابل توضیح
- Consultant context build_consultant_context with service_label+style_label+detection_method+is_ai+mask_real+coverage + invite text + chat POST
- Interest Lead vs View bti-final-interest + demand + waitlist + dedupe_key — برای جذب/فعال‌سازی مرکز
- Price display format_toman + duration_label + price_label — فارسی لوکس
- Blueprint discovery: beauty_centers_bp url_prefix /, beauty_reservations_bp, buti_ai_bp /analysis/mirror/, panel_user_bp — decoupled
- Template: base.html extends + bc-* classes + beauty_centers.css v13 + beauty_centers.js v4 + _card.html partial + carousel + lightbox + breadcrumb + SEO meta + JSON-LD

---

## ۳. Gapها — دقیقاً چه چیزهایی کم داریم؟

| Gap | شدت | توضیح | راه حل P0 | راه حل P1 |
|---|---|---|---|---|
| Portfolio per service | Medium | beauty_center_images بدون service_key — نمی‌توان نمونه‌کار بر اساس خدمت فیلتر کرد — UX لوکس می‌خواهد "نمونه‌کار همان خدمت" | P0: نمایش عمومی همه تصاویر — قابل قبول | P1: ADD COLUMN service_key TEXT DEFAULT '' + index + UI dropdown در owner_gallery_upload + filter in detail.html ?service= |
| Featured Service per service | Medium | is_featured فقط center-level — نمی‌توان خدمت "رنگ مو" را جداگانه Featured کرد — درآمد از دست می‌رود | P0: Featured Center موجود — کافی برای MVP | P1: ADD COLUMN service_key + is_featured_service INTEGER DEFAULT 0 in beauty_center_services + UI toggle + filter in list |
| User Panel Mirror History | Medium | buti_ai_final_designs table موجود ولی نمایش در panel_user ندارد — کاربر نمی‌تواند طراحی‌های قبلی خود را ببیند | P0: می‌تواند از /analysis/mirror/ دوباره ببیند — ولی UX ضعیف | P1: new module panel_user/modules/mirror.py reuse analyses.py pattern — SELECT WHERE user_id ORDER BY created_at DESC — Before/After thumb + CTA رزرو با همین طراحی |
| Service Key در services | Medium | beauty_center_services بدون service_key — نگاشت Mirror→service_id دقیق نیست، فقط name mapping حدسی | P0: name mapping حدسی کار می‌کند (hair_color ≈ رنگ مو) | P1: ADD COLUMN service_key TEXT DEFAULT '' + index + dropdown in add_service form |
| Discount per service | Low | beauty_center_discounts فقط center_id — نمی‌توان تخفیف برای خدمت خاص گذاشت | P0: تخفیف عمومی مرکز — موجود | P1: ADD COLUMN service_id INTEGER DEFAULT 0 + UI select service + badge in service card |
| Promotion per service | Low | beauty_center_promotions فقط center_id — نمی‌توان promotion برای خدمت خاص | P0: Promotion مرکز — موجود | P1: ADD COLUMN service_id INTEGER DEFAULT 0 |
| Bale Mirror flow | Medium | buti_ai/bot_handlers.py generic_service flow نیمه موجود — Bale کاربر نمی‌تواند Mirror را کامل انجام دهد | P0: وب موجود — کافی | P1: reuse generic_service for Bale bot_handlers — extend, not fork |
| Instagram/Logo, نمونه‌کار 800+ | Low | نیاز تجاری آینده — فعلاً شلوغ می‌کند | P2 | P2 |

---

## ۴. بررسی سناریوی «آگهی سالن بر اساس خدمات» — از 3 دید

### ۴.۱ کاربر

**آیا راحت‌تر تصمیم می‌گیرد؟** بله — کاربر الان در list.html همه مراکز را با کارت عمومی (_card.html name, type, city, price_level, starting_price) می‌بیند. اگر کارت خدمت باشد (مثلاً "بالیاژ کاراملی — از ۸۰۰ هزار — نمونه‌کار همان خدمت + تخفیف + CTA رزرو") تصمیم سریع‌تر است چون مستقیماً خدمت مورد علاقه‌اش را می‌بیند نه کل سالن. Mirror→نتیجه→سالن‌های همان خدمت Flow موجود enrich می‌کند ولی کارت هنوز عمومی است — اگر کارت خدمت باشد UX لوکس‌تر.

**آیا سردرگمی ایجاد می‌کند؟** اگر هر سالن 10 کارت خدمت نشان دهد شلوغ می‌شود — باید محدود کرد: فقط خدمات فعال is_active=1 + sort_order + حداکثر 3 خدمت برجسته در list، بقیه در detail. با ساختار فعلی is_active + sort_order دارد — قابل کنترل. پس سردرگمی قابل مدیریت.

**آیا مستقیماً خدمت مورد علاقه را پیدا می‌کند؟** بله — فیلتر service موجود (list_centers?service=nail) ولی نتیجه مراکز است نه خدمات. اگر آگهی ← خدمت باشد می‌توان /beauty-centers/services?service=nail لیست کارت‌های خدمت (نه مرکز) با نمونه‌کار همان خدمت + قیمت + پیشنهاد + CTA را نشان داد — دقیقاً خواسته کاربر.

**نتیجه کاربر:** مدل خوب است اگر لوکس و محدود باشد.

### ۴.۲ صاحب سالن

**آیا می‌تواند خدمات قابل ارائه را معرفی کند؟** بله — الان add_service با name, category, description, duration, price_min/max, is_active, sort_order دارد — می‌تواند هر خدمت را جدا معرفی کند. ولی نمونه‌کار دسته‌بندی بر اساس خدمت ندارد — Gap.

**آیا مدیریت ساده است؟** الان owner_dashboard تب خدمات دارد ولی برای هر خدمت باید name دستی بنویسد — ساده است. اگر service_key اضافه شود (optional TEXT) و تصویر هم service_key داشته باشد مدیریت همچنان ساده می‌ماند: یک dropdown "مرتبط با خدمت" در فرم خدمت و گالری.

**آیا روی خدمات مهم‌تر تمرکز می‌کند؟** بله — با is_active + sort_order + is_featured_service (پیشنهادی) می‌تواند خدمت پول‌ساز را بالا بیاورد و بقیه را غیرفعال کند. الان is_active دارد ولی Featured فقط مرکز — اگر Featured Service اضافه شود تمرکز بیشتر.

**نتیجه سالن:** مدل خوب است، ابزار واقعی جذب مشتری.

### ۴.۳ کسب‌وکار Giso

**آیا ارزش تجاری دارد؟** بله — هر خدمت inventory برای فروش: Featured Service (مرکز برای خدمت "رنگ مو" پول بدهد تا در لیست رنگ مو بالا بیاید), Promotion per service (package_key + service_id), تخفیف per service (beauty_center_discounts اگر service_id اضافه شود), تبلیغ هدفمند بر اساس Mirror result (service_key), پیشنهاد خدمت بر اساس selected_style, رزرو با final_design_id (already implemented).

**قابلیت‌ها:**
- Featured Service: الان is_featured فقط مرکز — اگر is_featured_service اضافه شود قابل پیاده‌سازی — P1 ارزشمند
- Promotion: فقط center_id — اگر service_id optional اضافه شود promotion per service — P1
- تخفیف: فقط center_id — اگر service_id اضافه شود تخفیف per service — P1
- جایگاه ویژه: sort_order already exists — می‌تواند برای جایگاه ویژه per service استفاده شود — P0
- پیشنهاد بر اساس Mirror/service_key: _enrich_generic_centers already service_key→beauty_center_service mapping — P0 موجود
- رزرو: final_design_id/service_key/selected_style already in reservations — P0 موجود

**نتیجه Giso:** مدل «آگهی ← خدمت سالن» از نظر تجاری بهتر از «آگهی کلی سالن» چون inventory بیشتر و هدفمندتر — توصیه YES با محدودیت لوکس.

---

## ۵. بررسی UX لوکس و ساده — Flow پیشنهادی

**Flow فعلی (موجود و کار می‌کند):**
```
Beauty Mirror (/analysis/mirror/ 4 کارت) 
→ Style Selection (5 مدل per service با sample 520x360)
→ Upload (preview+guide+sample)
→ Quality AI (configured_vision_chain first, local fallback) + Detection (color segmentation) + Analysis AI (analyze_*_photo)
→ Generation (Before/After + validation + provider/model + is_ai_generated)
→ نتیجه (final_label + do/avoid + interest question Lead vs View + centers enrich score+tags+match reason + consultant invite)
→ سالن‌های همین خدمت (list_centers?service={beauty_center_service} + _enrich_generic_centers score 45+20+15+feedback)
→ کارت مرکز (عمومی _card.html)
→ مشاهده سالن (detail.html با services+price+hours+feedback+gallery+contact+chat)
→ رزرو (reserve with final_design_id/service_key/selected_style + slots + calendar)
→ Lead (events + demand + waitlist)
```

**Flow لوکس پیشنهادی با ساختار فعلی (بدون تغییر DB در P0):**
```
Beauty Mirror 
→ نتیجه (Before/After + validation صادقانه)
→ سالن‌های همین خدمت (3 کارت با mirror_score, tags, match reason + CTA "مشاهده خدمات این مرکز برای {service_label}")
→ کارت خدمت سالن (در detail: هر خدمت کارت لوکس جدا: icon + name + description 1 خط + duration + price_min/max با toman + نمونه‌کار همان خدمت (فعلاً عمومی، بعداً فیلتر per service) + تخفیف badge + CTA "مشاهده" / "مشاوره" / "رزرو")
→ مشاهده سالن (detail با gallery فیلتر شده بر اساس خدمت انتخابی از query ?service=)
→ رزرو (reserve?service_id={id}&final_design_id={id}&service_key={key}&selected_style={style} + snapshot + BEGIN IMMEDIATE)
→ Lead
```

**آیا با معماری فعلی قابل پیاده‌سازی است؟** بله — 80% Reuse مستقیم:
- Mirror 4 خدمت فعال با Quality+Detection+Analysis+Generation+Validation+Final — موجود
- service_key→beauty_center_service mapping در SERVICE_CATALOG — موجود
- list_centers?service= filtering — موجود
- _enrich_generic_centers scoring — موجود
- center_detail services+price+hours — موجود
- reserve with final_design_id/service_key/selected_style — موجود
- owner_dashboard services management — موجود
- Gap فقط Portfolio per service — برای P0 می‌توان با naming convention یا category field موقت حل کرد، برای P1 ستون service_key اضافه شود.

---

## ۶. طراحی سناریوی پیشنهادی کامل ولی ساده

### ۶.۱ User Panel

**کاربر چه می‌بیند؟**
- در `/panel/beauty-centers` یا `/panel/overview`: لیست مراکز مورد علاقه + رزروهای من + پیام‌ها + Mirror History (جدید)
- Mirror History: از `buti_ai_final_designs` WHERE user_id = current_user.id ORDER BY created_at DESC — هر ردیف: service_label, selected_style, final_label, Before/After thumb, created_at, CTA "مشاهده نتیجه" + "رزرو با همین طراحی" (link to reserve with final_design_id)
- در `/beauty-centers`: فیلترهای فعلی + تب "خدمات" جدید: لیست کارت‌های خدمت (نه مرکز) با فیلتر service — هر کارت: center name + service name + price + duration + نمونه‌کار + تخفیف + CTA
- در `/beauty-centers/<slug>`: خدمات به صورت کارت لوکس (نه لیست ساده) — هر کارت: icon (wand-sparkles), name, category badge, description 1 خط, duration, price_label with toman, gallery filtered (فعلاً همه تصاویر، بعداً per service), discount badge if active, CTA رزرو/مشاوره/مشاهده

**چه چیزی پیشنهاد می‌شود؟**
- بر اساس Mirror result: 3 مرکز با mirror_score بالا + match reason
- بر اساس تاریخچه: اگر کاربر قبلاً nail دیده، پیشنهاد nail جدید
- بر اساس شهر: city filter پیش‌فرض مشهد + همان شهر tag

**CTAها:**
- "مشاهده" → center_detail
- "مشاوره" → center_chat (گفتگوی آنلاین)
- "رزرو" → reserve with service_id + final_design_id + service_key + selected_style
- "علاقه‌مندی" → P2 wishlist

### ۶.۲ صفحه سالن

**چه اطلاعاتی نمایش داده شود؟**
- Header: name, type_label, category_label, city, region, trust line (اطلاعات تماس بررسی شده), views_count, is_featured badge, promotion_active badge
- Description: 700 char max
- Cost: price_level_label + starting_price with toman + note "قیمت نهایی پس از بررسی"
- Services: کارت لوکس هر خدمت فعال: name, category, description, duration_label, price_label, sort_order, is_active check, CTA رزرو
- Hours: beauty_hours per day with day_label Persian + time_label
- Facts: address_summary, contact_time, views
- Gallery: center carousel with main + beauty_center_images max 3 — P1: filter by service_key if ?service= in query
- Contact: chat + phone reveal with intent price_inquiry + disclaimer
- Score: feedback score if count>=3
- Legal: disclaimer حدود نقش گیسو
- Related: centers with same service

**خدمات چگونه نمایش داده شوند؟**
- کارت لوکس: bc-service-item با head (icon+name+category), note (description), meta (price_label + duration_label), CTA reserve button — موجود در detail.html ولی می‌تواند لوکس‌تر شود: اضافه کردن نمونه‌کار همان خدمت (1 تصویر thumb) + تخفیف badge + پیشنهاد ویژه badge

**نمونه‌کار چگونه نمایش داده شود؟**
- فعلی: carousel عمومی — P1: اگر ?service=nail در query، فقط تصاویری که service_key=nail دارند نمایش داده شوند (نیاز به ستون service_key در beauty_center_images)

**قیمت چگونه نمایش داده شود؟**
- فعلی: _service_price_label with format_toman + duration_label — کافی، لوکس — P0 Reuse

**پیشنهاد ویژه چگونه نمایش داده شود؟**
- فعلی: active_discount legacy + discount_service_active — P1: beauty_center_discounts with service_id + title + discount_value + expires_at + status pending/visible — badge "پیشنهاد ویژه" در کارت خدمت

**رزرو چگونه انجام شود؟**
- فعلی: reserve route GET with service_id, date, slots JSON, calendar JSON + POST create_reservation with final_design_id, service_key, selected_style snapshot + BEGIN IMMEDIATE + notify — P0 Reuse کامل

### ۶.۳ پنل سالن — صاحب سالن دقیقاً چه مدیریت کند؟

**منوهای P0 ضروری (موجود و کافی):**
1. نمای کلی: status_label, views_count, contact_clicks, analysis_impressions, price_inquiry_clicks, listing_expires_at, promotion_active, feedback count, reservations count
2. اطلاعات پایه: name, category, center_type, city, region, address_summary, business_phone, salon_phone, display_phone_choice, contact_time, description, price_level, starting_price, services_json multi-select
3. خدمات: get_center_services list + add_service (name, category, description, duration_minutes, price_min, price_max, is_active, sort_order) + update_service + delete_service — P1 اضافه: service_key dropdown optional (brow, nail, lip_shading, hair_color, etc) برای نگاشت به Mirror
4. ساعات کاری: get_working_hours + save_working_hours per day_of_week with open_time, close_time, is_closed, slot_minutes
5. تصاویر: save_center_image + gallery upload/delete + main image delete with replacement — max 3 — P1 اضافه: service_key dropdown در upload برای دسته‌بندی نمونه‌کار per service
6. رزروها: owner_list + owner_action confirm/reject/complete + calendar + slots + notifications
7. پیام‌ها: owner_conversations + conversation_messages + close + feedback view
8. آمار: views, contact_clicks, analysis_impressions, price_inquiry_clicks, beauty_stats, events
9. وضعیت انتشار: status_label, listing_expired, promotion_active, renew_center_listing, purchase_center_promotion, discount

**منوهای P1 مهم (ارزش بالا):**
10. تخفیف‌ها: beauty_center_discounts with title, description, discount_value, expires_at, status pending/visible — P1: اضافه service_id optional برای تخفیف per service
11. تبلیغات: beauty_center_promotions with package_key, amount, transaction_key — P1: اضافه service_id optional برای Featured Service per service + is_featured_service flag
12. نمونه‌کار بر اساس خدمت: gallery filtered by service_key — نیاز به ستون service_key در beauty_center_images

**منوهای P2 بعداً:**
- Instagram/Logo, ظرفیت پیشرفته, علاقه‌مندی‌ها, تبلیغ هدفمند پیچیده

**دقیقاً چه فیلدهایی برای هر خدمت؟**
- name (الزامی), category (optional), description (500), duration_minutes (1-1440), price_min, price_max, is_active (فعال/غیرفعال), sort_order (ترتیب), service_key (P1 optional: brow, nail, lip_shading, hair_color, haircut, etc for Mirror mapping), is_featured_service (P1 optional boolean)

### ۶.۴ Admin — ادمین چه کنترل کند؟

- مراکز: list with status filter pending_review/reviewing/published/rejected/paused/closed, city, category, type, search, featured, expired, promotion — actions: review, publish, reject, pause, close, set is_featured, sort_order, admin_note, listing_expires_at, promotion_type/expires/bumped
- خدمات: (P1) view services per center, edit price, is_active, sort_order
- رزروها: view all reservations with status filter, date range, center, user, service, final_design_id link to buti_ai_final_designs
- تصاویر: moderate gallery, delete
- پیام‌ها/گزارش‌ها: beauty_center_conversations, messages, reports, feedback with status pending/visible/rejected
- تخفیف‌ها/تبلیغات: beauty_center_discounts, promotions with status pending/active, approve/reject
- آمار: beauty_center_events, views, contact_clicks, analysis_impressions, service_demand, waitlist
- AI: provider/model assignment per service_key via ai_models_registry
- تنظیمات: terms_version, price_levels, center_categories, center_types, services dict

---

## ۷. جدول Reuse — مهم‌ترین بخش — Reuse > Extend > New

| قابلیت | ساختار موجود | قابل استفاده مستقیم؟ | نیاز به تغییر؟ | فایل/ماژول |
|---|---|---|---|---|
| مدل Beauty Center | beauty_centers table 20+ fields, status 6, counters, pricing, expiry/promotion | ✅ بله | خیر | beauty_centers/schema.py |
| ثبت سالن | register route + _normalize_fields validation | ✅ بله | خیر | beauty_centers/routes.py, services.py |
| وضعیت تأیید | STATUS_FA + admin_set_status + bot_handlers | ✅ بله | خیر | services.py, panel_admin.py, bot_handlers.py |
| اطلاعات تماس | business_phone, salon_phone, display_phone_choice, contact_time | ✅ بله | خیر | schema.py, services.py |
| آدرس | city indexed, region, address_summary | ✅ بله | خیر | schema.py |
| تصاویر عمومی | beauty_center_images + save_center_image validation | ✅ بله | خیر برای عمومی، P1 برای per service | schema.py, services.py, routes.py |
| خدمات سالن | beauty_center_services name, category, description, duration | ✅ بله | خیر | pricing/schema.py, pricing/services.py |
| قیمت خدمات | price_min, price_max + price_level, starting_price + format_toman | ✅ بله | خیر | pricing/services.py, routes.py, money.py |
| ساعات کاری | beauty_center_working_hours per day_of_week + save_working_hours BEGIN IMMEDIATE | ✅ بله | خیر | pricing/schema.py, pricing/services.py |
| فعال/غیرفعال | is_active, is_featured, sort_order, listing_expired, promotion_active | ✅ بله | خیر | schema.py, services.py |
| امتیاز و نظر | beauty_center_feedback + summary score100 | ✅ بله | خیر | schema.py, services.py |
| رزرو با snapshot | beauty_center_reservations with service_id/name/price/duration snapshot + BEGIN IMMEDIATE + _is_available | ✅ بله | خیر | reservations/schema.py, services.py, routes.py |
| پیام/ارتباط | beauty_center_conversations UNIQUE + messages + close + feedback | ✅ بله | خیر | schema.py, services.py, routes.py |
| آگهی/Featured/Promotion | is_featured, promotion_type, promotions table, renew, promote | ✅ بله برای مرکز | P1 برای per service | schema.py, services.py, routes.py |
| لیست مراکز با فیلتر | list_public_centers q/city/category/type/service/price_level + featured 6 + related | ✅ بله | خیر | services.py, routes.py, list.html |
| صفحه سالن | center_detail + increment_view + services_for_display + hours_for_display + feedback + gallery + contact + chat | ✅ بله | خیر برای عمومی، P1 لوکس | routes.py, detail.html |
| پنل سالن اطلاعات | owner_dashboard tab edit + update_owner_center | ✅ بله | خیر | routes.py, owner_dashboard.html |
| پنل سالن خدمات | get_center_services + add/update/delete | ✅ بله | P1 service_key optional | pricing/services.py, routes.py |
| پنل سالن ساعات | get_working_hours + save_working_hours | ✅ بله | خیر | pricing/services.py |
| پنل سالن تصاویر | save_center_image + gallery upload/delete + main delete | ✅ بله | P1 service_key | services.py, routes.py |
| پنل سالن رزروها | owner_list + owner_action confirm/reject/complete + calendar + slots + notify | ✅ بله | خیر | reservations/services.py, routes.py |
| پنل سالن پیام‌ها | owner_conversations + messages + close | ✅ بله | خیر | services.py |
| پنل سالن آمار | views, contact_clicks, analysis_impressions, price_inquiry_clicks, beauty_stats | ✅ بله | خیر | services.py, routes.py |
| Mirror 4 خدمت | SERVICE_CATALOG 4 active + generic_service + service_image_generation + validation | ✅ بله | خیر | buti_ai/service_catalog.py, generic_service.py, service_image_generation.py |
| Quality AI + Detection | check_photo_quality AI first fallback local + detect_regions | ✅ بله | خیر | buti_ai/eyebrow/quality.py, landmarks.py, generic_service.py |
| Generation mask gate | generate_final_design with mask gate + provider chain + fallback guided composite + validate_masked_output | ✅ بله | خیر | service_image_generation.py, image_validation.py |
| Final Design ذخیره | buti_ai_final_designs with session_id, user_id, service_type, original/final filename, selected_style, provider, model, prompt_json | ✅ بله | خیر | buti_ai/schema.py, final_design.py |
| service_key نگاشت | SERVICE_CATALOG beauty_center_service mapping brow/nail/hair_color/lip_shading | ✅ بله | خیر | buti_ai/service_catalog.py |
| selected_style | 5 styles per service with STYLES dict + DEFAULT_STYLE | ✅ بله | خیر | buti_ai/nail/final_design.py, hair_color/final_design.py, lip/final_design.py, eyebrow/final_design.py |
| final_design_id در رزرو | beauty_center_reservations final_design_id + service_key + selected_style + create_reservation snapshot | ✅ بله | خیر | reservations/schema.py, services.py |
| Centers enrich با Mirror | _enrich_generic_centers score 45 has_service+20 city+15 featured+feedback + tags + match reason | ✅ بله | خیر | buti_ai/routes.py |
| Consultant + Interest | build_consultant_context + consultant_invite_text + bti-final-interest Lead vs View + demand + waitlist | ✅ بله | خیر | buti_ai/consultant.py, routes.py, services.py |
| User Panel Mirror History | buti_ai_final_designs موجود ولی نمایش در panel_user ندارد | ❌ ندارد | Extend: new module panel_user/modules/mirror.py reuse analyses.py | panel_user/modules/analyses.py → new mirror.py |
| Portfolio per service | beauty_center_images بدون service_key | ❌ ندارد | Extend: ALTER TABLE ADD COLUMN service_key TEXT DEFAULT '' + index | beauty_centers/schema.py, services.py, routes.py, owner_dashboard.html |
| Featured Service per service | is_featured فقط center-level | ❌ ندارد | Extend: ADD COLUMN is_featured_service INTEGER DEFAULT 0 + service_key TEXT | pricing/schema.py, services.py |
| Discount per service | beauty_center_discounts فقط center_id | ❌ ندارد | Extend: ADD COLUMN service_id INTEGER DEFAULT 0 | schema.py |
| Promotion per service | beauty_center_promotions فقط center_id | ❌ ندارد | Extend: ADD COLUMN service_id INTEGER DEFAULT 0 | schema.py |
| Service Key در services | beauty_center_services بدون service_key | ❌ ندارد | Extend: ADD COLUMN service_key TEXT DEFAULT '' + index | pricing/schema.py |
| Bale Mirror flow | buti_ai/bot_handlers.py generic_service flow | ⚠️ نیمه موجود | Extend: reuse generic_service for Bale | buti_ai/bot_handlers.py, bot.py |

**اولویت Reuse > Extend > New:** Reuse مستقیم 80% — همه چیز اصلی موجود است. Extend با 2-3 ستون additive 20% — service_key در beauty_center_services + beauty_center_images + service_id در promotions/discounts + is_featured_service — migration additive via ALTER TABLE ADD COLUMN (همان pattern ai_credits fix). New Architecture 0% — هیچ ماژول جدید لازم نیست مگر panel_user mirror history که reuse analyses.py pattern است.

---

## ۸. بررسی دیتابیس — آیا جدول‌ها کافی هستند؟

**بررسی هر جدول:**

- `beauty_centers`: کافی برای P0 — 20+ فیلد، status, is_active, is_featured, city indexed, pricing, expiry/promotion, counters — هیچ تغییر لازم نیست برای MVP
- `beauty_center_services`: کافی برای P0 — name, category, description, duration, price_min/max, is_active, sort_order — برای P1 پیشنهادی: ADD COLUMN service_key TEXT DEFAULT '' (برای نگاشت به Mirror service_key brow/nail/hair_color/lip_shading) + ADD COLUMN is_featured_service INTEGER DEFAULT 0 (برای Featured Service per service) — migration additive, index on service_key
- `beauty_center_images`: کافی برای P0 عمومی — ولی برای Portfolio per service نیاز به ADD COLUMN service_key TEXT DEFAULT '' — تا بتوان gallery را بر اساس خدمت فیلتر کرد — P1
- `beauty_center_reservations`: کافی و کامل — final_design_id, service_key, selected_style already implemented — هیچ تغییر لازم نیست — P0 Reuse
- `buti_ai_mirror_sessions` (buti_ai_sessions): کافی — user_id, service_type, city, center_id, status, created_at — هیچ تغییر لازم نیست
- `buti_ai_final_designs`: کافی — session_id, user_id, service_type, original/final filename, selected_style, recommended_style, change_level, provider, model, status, prompt_json, created_at — هیچ تغییر لازم نیست — برای User Panel Mirror History فقط SELECT نیاز است

**اگر نیاز به تغییر DB وجود دارد، دقیق:**

- **چه فیلدی؟** service_key TEXT DEFAULT '' + is_featured_service INTEGER DEFAULT 0 در beauty_center_services, service_key TEXT DEFAULT '' در beauty_center_images, service_id INTEGER DEFAULT 0 در beauty_center_promotions, service_id INTEGER DEFAULT 0 در beauty_center_discounts
- **در کدام جدول؟** beauty_center_services, beauty_center_images, beauty_center_promotions, beauty_center_discounts
- **چرا؟** برای دسته‌بندی نمونه‌کار بر اساس خدمت (UX لوکس)، برای Featured Service per service (درآمد)، برای تخفیف/promotion per service (درآمد هدفمند)، برای نگاشت Mirror service_key به service_id دقیق (به جای name mapping)
- **آیا می‌توان بدون تغییر DB انجام داد؟** بله برای P0 — با ساختار فعلی قابل انجام است: نمونه‌کار عمومی نمایش داده شود، Featured فقط center-level، تخفیف عمومی، service_key از name mapping حدسی — توصیه: P0 بدون تغییر DB، P1 با 2 ستون additive (service_key در services + images) — همان pattern قبلی ai_credits fix با PRAGMA check + ALTER TABLE

**نتیجه DB Impact:** P0 ضروری هیچ تغییر لازم نیست — 100% با ساختار فعلی قابل پیاده‌سازی است. P1 مهم 2 ستون additive پیشنهادی با migration additive (ALTER TABLE ADD COLUMN IF NOT EXISTS via PRAGMA) + index — هیچ DROP/RECREATE.

---

## ۹. بررسی آگهی و مدل درآمدی — آگهی عمومی vs آگهی ← خدمت

**مدل فعلی (آگهی عمومی):** هر مرکز یک آگهی دارد (beauty_centers row) با is_featured, promotion_type, sort_order — در list.html کارت مرکز عمومی (_card.html) با name, type, city, price_level, starting_price — ساده ولی شلوغ نیست، لوکس است ولی خدمت خاص را برجسته نمی‌کند.

**مدل پیشنهادی (آگهی ← خدمت سالن):**
```
سالن X
→ خدمت "رنگ مو" (beauty_center_services row)
  → نمونه‌کار همان خدمت (beauty_center_images where service_key=hair_color)
  → قیمت (price_min/max with toman)
  → توضیح (description 1 خط)
  → تخفیف/پیشنهاد (beauty_center_discounts where service_id=X)
  → زمان انجام (duration_minutes)
  → CTA رزرو/مشاوره/مشاهده
```

**آیا از نظر UX بهتر است؟** بله — کاربر مستقیماً خدمت مورد علاقه‌اش را می‌بیند (مثلاً "ناخن فرنچ در مشهد") نه کل سالن — تصمیم سریع‌تر، سردرگمی کمتر اگر محدود شود به 3 خدمت برجسته در لیست. از نظر محصولی لوکس‌تر است چون کارت خدمت با نمونه‌کار همان خدمت + قیمت + پیشنهاد + CTA — دقیقاً مثل دیوار/شیپور ولی لوکس و تخصصی زیبایی.

**آیا از نظر درآمد بهتر است؟**
- Featured Service: مرکز برای خدمت "رنگ مو" پول بدهد تا در لیست رنگ مو بالا بیاید — inventory بیشتر از Featured Center
- Promotion per service: package_key + service_id — مثلاً "پروموشن رنگ مو 7 روزه"
- تخفیف per service: discount per service — کاربر جذب تخفیف خدمت خاص می‌شود
- جایگاه ویژه per service: sort_order per service
- پیشنهاد بر اساس Mirror/service_key: _enrich_generic_centers already service_key → service mapping — می‌تواند با پول Boost شود (پرداخت برای پیشنهاد بالاتر)
- پیشنهاد بر اساس نتیجه Mirror: final_design_id → service_key → centers — قابل پولی شدن
- رزرو با final_design_id: already implemented — قابل کمیسیون

**کدام ارزش دارد و کدام اضافه؟**
- P0 ارزشمند و موجود: Promotion مرکز, Featured Center, پیشنهاد بر اساس Mirror/service_key, رزرو با final_design_id
- P1 ارزشمند و پیشنهادی: Featured Service per service, Discount per service, Portfolio per service, Promotion per service
- P2 فعلاً اضافه: تبلیغ هدفمند پیچیده با AI, علاقه‌مندی‌ها, Instagram/Logo, نمونه‌کار 800+

**توصیه نهایی:** مدل «آگهی ← خدمت سالن» مناسب است و بهتر از آگهی کلی سالن — چون ساده + لوکس + قابل فروش + قابل مدیریت — ولی برای P0 همان آگهی مرکز با خدمات کارت لوکس در detail کافی است (بدون نیاز به تغییر DB)، برای P1 Featured Service + Discount per service اضافه شود.

---

## ۱۰. اولویت‌بندی — P0/P1/P2

**P0 — ضروری (برای تجربه خوب و قابل استفاده لازم، با ساختار فعلی قابل انجام، ساده+لوکس+قابل فروش+قابل مدیریت):**
- Mirror 4 خدمت فعال (eyebrow, nail, hair_color, lip_shading) با Quality AI + Detection + Analysis AI + Generation با mask gate + Validation + Final with Before/After + do/avoid + consultant + interest — موجود
- Service/Style/Upload/Final flow کامل — موجود
- Centers filtering با service_key (list_centers?service=nail) + _enrich_generic_centers scoring — موجود
- Center Detail با services+price+hours+feedback+gallery+contact+chat — موجود
- Reservation با final_design_id/service_key/selected_style + BEGIN IMMEDIATE + snapshot + notify — موجود
- Owner Dashboard اطلاعات پایه/خدمات/ساعات/تصاویر/رزروها/پیام‌ها/آمار/وضعیت — موجود
- Promotion مرکز (is_featured, promotion_type, renew, promote) — موجود
- Consultant + Interest Lead vs View — موجود
- قیمت با format_toman + duration_label — موجود
- امنیت: login_required + owner check + CSRF + static_root check + X-Content-Type-Options + ThreadPoolExecutor — موجود

**P1 — مهم (ارزش محصول و سالن را بالا می‌برد، نیاز به 2 ستون additive):**
- User Panel Mirror History: new module panel_user/modules/mirror.py reuse analyses.py pattern — SELECT from buti_ai_final_designs WHERE user_id — نمایش Before/After + CTA رزرو با همین طراحی — 1 فایل جدید
- Portfolio categorization per service: ADD COLUMN service_key TEXT DEFAULT '' in beauty_center_images + UI dropdown در owner_dashboard gallery upload + filter in detail.html ?service= — 1 ستون additive
- Featured Service per service: ADD COLUMN service_key TEXT DEFAULT '' + is_featured_service INTEGER DEFAULT 0 in beauty_center_services + UI toggle در owner_dashboard services + filter in list_centers for featured service — 2 ستون additive
- Discount per service: ADD COLUMN service_id INTEGER DEFAULT 0 in beauty_center_discounts + UI select service in discount form + badge in service card — 1 ستون additive
- Promotion per service: ADD COLUMN service_id INTEGER DEFAULT 0 in beauty_center_promotions + UI — 1 ستون additive
- Bale Mirror flow: reuse generic_service for Bale bot_handlers — extend bot_handlers.py
- Service Key column در beauty_center_services: برای نگاشت دقیق Mirror → service_id — 1 ستون additive

**P2 — بعداً (فعلاً نباید ساختار را شلوغ کنند):**
- Instagram/Logo, تبلیغ هدفمند پیچیده با AI boosting, علاقه‌مندی‌ها/wishlist, نمونه‌کار 800+ با کراپ, ظرفیت پیشرفته, نظرات پیشرفته با عکس, Featured Service Promotion مبلغ جدا, کمیسیون رزرو, API برای اپلیکیشن

**هدف P0:** سیستم ساده + لوکس + قابل فروش + قابل مدیریت برای سالن — نه پنل پر از امکانات غیرضروری — با ساختار فعلی 100% قابل دستیابی است.

---

## ۱۱. فایل‌ها و ماژول‌های درگیر — مسیر دقیق + Plan + Scope Lock

### ۱۱.۱ فایل‌های موجود و درگیر در سناریو (Code Truth)

- `giso/beauty_centers/schema.py` — beauty_centers + images + conversations/messages/feedback/promotions/discounts/events/reports + migrate additive + indexes
- `giso/beauty_centers/services.py` — SERVICES 20 keys, CENTER_TYPES 7, CATEGORY_SERVICES, STATUS_FA, PRICE_LEVELS, _normalize_fields, decorate_center, list_public_centers, get_center_by_slug, get_owner_center, save_center_image, increment_view, reveal_contact, etc + ThreadPoolExecutor
- `giso/beauty_centers/routes.py` — Blueprint beauty_centers_bp url_prefix /, list_centers, center_detail, register_center, owner_dashboard, owner_gallery_upload/delete, owner_main_image_delete, center_chat, center_chat_message, center_chat_close, owner_renew, owner_discount, owner_promote, gallery_media, center_media, center_contact, center_chat_feedback + _owner_panel_context + _center_services_for_display + _center_hours_for_display
- `giso/beauty_centers/pricing/schema.py` — beauty_center_services + working_hours + migrate_pricing_tables additive + indexes
- `giso/beauty_centers/pricing/services.py` — get_center_services, add_service, update_service, delete_service, get_working_hours, save_working_hours + _clean_service + _clean_working_day + BEGIN IMMEDIATE upsert
- `giso/beauty_centers/reservations/schema.py` — beauty_center_reservations with final_design_id/service_key/selected_style + RESERVATION_STATUSES + migrate_reservation_tables additive + indexes
- `giso/beauty_centers/reservations/services.py` — get_available_slots, get_calendar_month, create_reservation BEGIN IMMEDIATE snapshot, owner_list, owner_action, _is_available, _build_slots, _active_bookings, _transition, confirm/reject/complete/cancel + _service_of + _working_day
- `giso/beauty_centers/reservations/routes.py` — Blueprint beauty_reservations_bp, slots JSON, calendar JSON, reserve GET/POST with service_id/date/final_design_id/service_key/selected_style + my_reservations
- `giso/beauty_centers/reservations/notifications.py` — notify_new_reservation, notify_user_confirmed/rejected
- `giso/beauty_centers/panel_admin.py` — handle_beauty_status, handle_beauty_promotion, handle_beauty_discount, handle_feedback + admin guards
- `giso/beauty_centers/bot_handlers.py` — beauty_admin_menu_kb + _center_kb actions
- `giso/beauty_centers/templates/beauty_centers/` — list.html (search form q/city/category/type/service/price_level + featured + related + grid + _card.html), detail.html (bc-detail-grid, services list bc-service-item with price_label/duration_label + CTA reserve, hours, facts, carousel, contact, score, legal), _card.html, _analysis_cta.html, owner_dashboard.html (tabs: info/services/hours/images/messages/reservations/stats/status + forms), register.html, chat.html, reserve.html, my_reservations.html, admin.html
- `giso/beauty_centers/static/` — beauty_centers.css v13, beauty_centers.js v4
- `giso/buti_ai/schema.py` — buti_ai_sessions, buti_ai_waitlist, buti_ai_service_demand, buti_ai_final_designs + _ensure_column migration additive + init_buti_ai_db
- `giso/buti_ai/service_catalog.py` — SERVICE_CATALOG 4 active, SERVICE_SLUGS, SLUG_TO_SERVICE, get_service_meta, mirror_services, supported_service_keys
- `giso/buti_ai/generic_service.py` — service_module, normalize_model_key, initial_form_values, build_result, process_service_submission (save_eyebrow_photo prefix service_key, quality, detection, analysis), build_final_candidate, source_image_path, generate_final_design, uploaded_root + CHANGE_LEVELS
- `giso/buti_ai/service_image_generation.py` — generate_final_design with mask gate + provider chain + fallback guided composite
- `giso/buti_ai/image_validation.py` — validate_masked_output with service_key
- `giso/buti_ai/routes.py` — Blueprint buti_ai_bp, mirror_home, generic_service_wizard, upload, final, consultant, interest, centers enrich _enrich_generic_centers + scoring + tags + match reason + demand/waitlist + session handling _new_service_selection_key/candidate_key
- `giso/buti_ai/consultant.py` — build_consultant_context, consultant_invite_text
- `giso/buti_ai/ai_models.py` — image_task_for_service, configured_image_provider_dicts, SERVICE_IMAGE_TASK_MAP
- `giso/buti_ai/eyebrow/`, `nail/`, `hair_color/`, `lip/` — final_design.py STYLES 5 per service + DEFAULT_STYLE + UPLOAD_DIR + check_photo_quality + detect_regions + analyze_*_photo + generate_guided_design
- `giso/panel_user/routes.py` — panel_user Blueprint, overview, analyses, chats, marketplace, etc
- `giso/panel_user/modules/` — _base.py, analyses.py (pattern for mirror history), chats.py, overview.py, etc
- `giso/base.py` — get_giso_db_conn WAL + busy_timeout
- `giso/config.py` — Config.GISO_DIR for static_root
- `giso/money.py` — format_toman
- `giso/app.py` — Blueprint registration

### ۱۱.۲ Plan + Scope Lock — Approval Gate

**Request interpretation:** بررسی کامل Beauty Center / پنل سالن و آگهی خدمات سالن از روی کد واقعی، ارزیابی سناریوی آگهی بر اساس خدمات از 3 دید، طراحی UX لوکس ساده Mirror→نتیجه→سالن‌های همان خدمت→نمونه‌کار+قیمت+پیشنهاد→مشاهده→رزرو، طراحی سناریوی پیشنهادی User Panel/صفحه سالن/پنل سالن/Admin، جدول Reuse با اولویت Reuse>Extend>New، بررسی DB و مدل درآمدی، اولویت‌بندی P0/P1/P2، خروجی 11 بخش + Plan+Scope Lock + STOP منتظر تایید.

**Freshness:** HEAD=56fac4b branch=arena/01a0eecf-giso4 working-tree=clean قبل نوشتن / dirty بعد نوشتن فقط rp6.md, Graph STALE c9b198cd, Docs STALE 2026-09-29 branch mismatch, Memory absent

**Current state & real problem location:** beauty_centers module کامل برای MVP — Gap اصلی Portfolio per service (images بدون service_key) + Featured Service per service (is_featured فقط center) + User Panel Mirror History (final_designs موجود ولی نمایش ندارد) — همه Gapها Medium نه Critical — Code Truth: live code has 20 SERVICES keys, reservations with final_design_id/service_key/selected_style, buti_ai_final_designs with provider/model/prompt_json — Docs may lag.

**Architecture & current pattern:** Convention table بالا — DB via get_giso_db_conn, Auth via login_required + owner check, CSRF via csrf_token, Notification via ThreadPoolExecutor + broadcasts_center, Bot via state machine, Template via base.html + bc-* classes, AI via ai_runtime + provider chain, Migration additive via PRAGMA + ALTER TABLE, Pricing 6 functions, Reservations BEGIN IMMEDIATE snapshot, Listing via list_public_centers filters — Current architecture summary: beauty_centers modular with 10 files + pricing + reservations + panel_admin + bot_handlers, shared DB giso.db WAL, additive migrations, ThreadPoolExecutor notifications, CSRF protected, owner vs staff guards, service filtering via SERVICES + beauty_center_services, reservation snapshot + BEGIN IMMEDIATE, Mirror integration via final_design_id/service_key/selected_style + enrich scoring 45+20+15+feedback

**Dependencies & impact:** Internal imports: base.get_giso_db_conn, config.Config, beauty_centers.services, pricing.services, reservations.services, reservations.notifications, buti_ai.service_catalog, generic_service, service_image_generation, schema, ai_models, money.format_toman, panel_user.routes, bot handlers — all reuse. Shared DB: 10+ tables beauty_centers/services/working_hours/images/conversations/messages/feedback/reservations/promotions/discounts/events/expiry_notices/reports + buti_ai_sessions/final_designs/service_demand/waitlist + giso_web_auth + giso_config + giso_admins — caution additive columns only. Notification: new_reservation, user_confirmed/rejected — reuse. AI runtime: ai_runtime, ai_credits, ai_models_registry, buti_ai/ai_models — reuse. Sibling features: marketplace, hair_sale, analyses, chats, orders, wallet, profile, reviews, overview, eyebrow/nail/hair_color/lip — no breaking change.

**Proposed solution — Minimal path:** برای این گزارش (rp6.md) فقط بررسی و طراحی — هیچ کد تغییر نکرده — P0 بدون تغییر DB قابل پیاده‌سازی است — توصیه: اول verification P0 (Mirror 4 خدمت, filtering, detail, reservation, owner dashboard, promotion, consultant) — بعد P1 با 2 ستون additive (service_key در beauty_center_services + beauty_center_images + service_id در promotions/discounts + is_featured_service) via ALTER TABLE ADD COLUMN — بعد User Panel Mirror History new module reuse analyses.py — بعد Bale Mirror flow reuse generic_service — Order Reuse>Extend>New. Explicitly NOT doing: refactor bot.py, تغییر bot_edu/web/main.py, DROP/RECREATE table, new abstraction/base class, تغییر Graphify/project_memory/data/.env, تغییر قیمت یا منطق رزرو, تغییر AI provider logic.

**Scope Lock:**
- ALLOWED files (این گزارش فقط): [rp6.md] — هیچ کد دیگری تغییر نکرده per law Read-Only
- اگر تایید شود برای فاز پیاده‌سازی آینده (پیشنهادی، هنوز اجرا نشده):
  - ALLOWED (12 فایل): `giso/beauty_centers/schema.py` (add service_key to images additive + index), `giso/beauty_centers/pricing/schema.py` (add service_key + is_featured_service to services additive), `giso/beauty_centers/services.py` (save_center_image + promotion per service), `giso/beauty_centers/pricing/services.py` (_clean_service accept service_key + is_featured_service), `giso/beauty_centers/routes.py` (display filter + gallery filter + owner_gallery_upload with service_key), `giso/beauty_centers/templates/beauty_centers/owner_dashboard.html` (service_key dropdown + gallery service_key dropdown + featured toggle), `giso/beauty_centers/templates/beauty_centers/detail.html` (service card لوکس with portfolio per service + discount badge + CTA), `giso/panel_user/modules/mirror.py` NEW reuse analyses.py pattern (mirror history from buti_ai_final_designs), `giso/panel_user/routes.py` (register mirror module), `giso/buti_ai/templates/buti_ai/generic_final_design.html` (CTA to service_id), `giso/buti_ai/routes.py` (enrich with service_id mapping + _enrich_generic_centers keep scoring), `rp6.md`
  - FORBIDDEN: everything else — especially `bot_edu/`, `web/`, `main.py`, `giso/bot.py` refactor, `graphify-out/`, `project_memory/`, `data/`, `.env`, `giso/buti_ai/eyebrow/` for new services (must use generic_service)
  - Shared/caution files inside future scope: schema.py (shared tables beauty_centers/services/images/reservations), services.py (shared listing), panel_user/routes.py (shared auth), buti_ai/routes.py (shared AI runtime)
  - Data: tables involved beauty_centers, beauty_center_services, beauty_center_images, beauty_center_promotions, beauty_center_discounts, buti_ai_final_designs, beauty_center_reservations — migration needed? P0 no, P1 yes additive via ALTER TABLE ADD COLUMN with PRAGMA check + CREATE INDEX IF NOT EXISTS (same pattern as ai_credits fix + pricing/schema.py)
  - Out of scope: sibling services marketplace/hair_sale, bot_edu, web/, graphify-out, project_memory, data, .env

**Council Review:**
- Architect: PASS (domain folder correct, no forbidden coupling, additive only, no new abstraction)
- Domain: PASS (behavior matches real code: SERVICES 20, STATUS 6, pricing, working_hours, reservations BEGIN IMMEDIATE snapshot, Mirror 4 active with Quality+Detection+Analysis+Generation+Validation+Final+Consultant+Interest+Enrich, service_key mapping, final_design_id in reservations — edge cases handled: empty states, duplicate prevention via UNIQUE, Persian/RTL)
- Security: PASS (login_required + owner_user_id check + _is_staff, CSRF, validation, upload path constraints, static_root check + parents check + nosniff + conditional, normalize_phone, display_phone, phone reveal via POST intent, no secret in logs)
- Regression: PASS with WARNING (16 test files beauty_centers + buti_ai new_services + phase1 + broadcasts_center share tables — additive columns safe with DEFAULT '' — but template filter needs fallback to general gallery)

**Risks:**
- اگر service_key به beauty_center_images اضافه شود و existing images بدون service_key باشند، filter باید fallback به عمومی داشته باشد — mitigation: WHERE service_key='' OR service_key=? + UI "همه"
- اگر Featured Service اضافه شود و مرکز 10 خدمت Featured کند، لیست شلوغ می‌شود — mitigation: limit 3 featured per center + sort_order
- اگر User Panel Mirror History اضافه شود و user_id null باشد (guest sessions), query باید user_id IS NOT NULL — mitigation: filter user_id = current_user.id
- اگر Bale Mirror flow اضافه شود و provider quota تمام شود, fallback guided composite باید صادقانه اعلام شود — mitigation: existing validation + is_ai_generated flag

**Tests to run (اگر تایید شود برای فاز پیاده‌سازی):**
- `SECRET_KEY=test python -m pytest giso/tests/test_beauty_centers_*.py -q` — 16 files
- `python -m pytest giso/tests/test_buti_ai_new_services.py -q` — generic_service 4 services
- `python -m pytest giso/tests/test_buti_ai_phase1.py -q` — eyebrow baseline
- `python -m pytest giso/tests/test_broadcasts_center.py -q` — notifications
- `python -c "import giso.wsgi"` — import/boot check
- دستی: list_centers?service=nail filter, center_detail services+price+hours, Mirror upload→final with validation, reserve with final_design_id/service_key/selected_style, owner_dashboard tabs, promotion, consultant chat

**Regression plan:**
- Run sibling tests: marketplace, hair_sale, analyses, chats — `grep -R "beauty_centers\|beauty_center_services\|beauty_center_reservations\|buti_ai_final_designs" giso/tests/`
- Shared symbol tests: get_giso_db_conn, ai_runtime, ai_credits — `Select-String` in giso/tests/
- Manual: verify existing centers still list, existing reservations still work, existing gallery still shows, existing chat still works, existing Mirror still generates

**Found but not changed:**
- beauty_center_images بدون service_key — Gap Medium — P1 پیشنهادی
- beauty_center_services بدون service_key + is_featured_service — Gap Medium — P1 پیشنهادی
- beauty_center_promotions + discounts بدون service_id — Gap Low — P1 پیشنهادی
- User Panel Mirror History ندارد — Gap Medium — P1 new module reuse analyses.py
- Bale Mirror flow ندارد — Gap Medium — P1 reuse generic_service
- Graph STALE (built at c9b198cd vs HEAD 56fac4b) — should run `graphify update .` after code changes — suggestion only, not executed
- Docs STALE (branch name mismatch arena/01a0e0b8 vs 01a0eecf) — should update PROJECT_GUIDE.md branch name — suggestion only

---

## APPROVAL NEEDED: تأیید می‌کنی؟

**این گزارش Read-Only است — هیچ کد تغییر نکرده — فقط rp6.md ایجاد/به‌روزرسانی شده.**

**اگر تایید کنی "تایید/بریم/اجرا کن":**
- وارد فاز پیاده‌سازی P0 (بدون تغییر DB) + P1 (2 ستون additive) می‌شویم
- Scope Lock آینده بالا اعمال می‌شود
- Tests + Diff Review + Regression + Final Report اجرا می‌شود

**اگر تایید نکنی:** همین گزارش نهایی است و در گیت‌هاب ذخیره می‌شود.

---

## قانون نهایی رعایت شد

فعلاً هیچ کدی تغییر نکرده — فقط rp6.md — بعد از Plan+Scope Lock متوقف می‌شویم و منتظر تایید "تایید/بریم/اجرا کن" می‌مانیم — Code is Truth: اگر Documentation و Code اختلاف داشتند، Code حقیقت اصلی است — اولویت مطلق Reuse>Extend>New — اگر با ساختار فعلی قابل انجام است تغییر DB پیشنهاد نشده (P0 بدون تغییر).

---

## Appendix — Evidence از کد واقعی این نشست

- beauty_centers table: schema.py:10-55 with 20+ fields + 10 related tables + 5 indexes + additive migration salon_phone, display_phone_choice, last_edit_at, listing_expires_at
- SERVICES 20 keys: services.py:30-38 includes brow/nail/lip_shading/hair_color + CATEGORY_SERVICES + CENTER_TYPES + STATUS_FA + PRICE_LEVELS + CENTER_IMAGE_MAX_BYTES/PIXELS/SIDE/FORMATS + ThreadPoolExecutor
- beauty_center_services: pricing/schema.py SERVICES_COLUMNS with price_min/max/duration/is_active/sort_order + get_center_services ordered is_active DESC
- working_hours: day_of_week 0=شنبه + save_working_hours BEGIN IMMEDIATE upsert + legacy weekday/is_open sync
- reservations: schema.py RESERVATIONS_COLUMNS with final_design_id, service_key, selected_style + RESERVATION_STATUSES 5 + 3 indexes + create_reservation BEGIN IMMEDIATE + snapshot rule + _is_available + _build_slots + _active_bookings + _transition guarded + confirm/reject/complete/cancel_by_user + notify hooks + get_available_slots + get_calendar_month + _jalali
- list_centers: routes.py list_public_centers with filters q/city/category/type/service/price_level limit 60 + featured 6 + related via recommended_centers + analysis_service_tags + beauty_stats + noindex if query + increment_view + reveal_contact + _center_services_for_display + _center_hours_for_display + _owner_panel_context
- center_detail: routes.py + detail.html with bc-detail-grid, services list bc-service-item with price_label/duration_label + CTA reserve, hours, facts, carousel, contact, score, legal, breadcrumb, SEO meta, JSON-LD
- owner_dashboard: routes.py + owner_dashboard.html with 8 tabs P0 + 3 P1 + forms + CSRF + ThreadPoolExecutor
- Mirror: buti_ai/service_catalog.py 4 active + SERVICE_SLUGS + SLUG_TO_SERVICE + get_service_meta + mirror_services + supported_service_keys + generic_service.py process_service_submission + build_final_candidate + generate_final_design + routes.py mirror_home + generic_service_wizard + upload + final + _enrich_generic_centers scoring 45+20+15+feedback + tags + match reason + demand/waitlist + session handling _new_service_selection_key/candidate_key + consultant build_consultant_context + interest Lead vs View
- Final Design: buti_ai/schema.py buti_ai_final_designs with session_id/user_id/service_type/original/final/selected_style/recommended_style/change_level/provider/model/status/prompt_json + save_final_design + init_buti_ai_db + _ensure_column additive
- Service Key mapping: SERVICE_CATALOG beauty_center_service brow/nail/hair_color/lip_shading + CHANGE_LEVELS very_natural/medium/clear
- Security: login_required + owner_user_id check + _is_staff + csrf_token + static_root check + parents check + nosniff + conditional + normalize_phone + display_phone + reveal via POST intent price_inquiry
- Migration pattern: PRAGMA table_info + ALTER TABLE ADD COLUMN + CREATE INDEX IF NOT EXISTS + CREATE TABLE IF NOT EXISTS — additive only — same as ai_credits fix

---

**END OF rp6.md — STOP منتظر تایید**
