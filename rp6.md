# rp6.md — بررسی و طراحی سناریوی Beauty Center / پنل سالن و آگهی خدمات — Branch arena/01a0eecf-giso4

تاریخ: 2026-10-06
Auditor: Arena Agent (giso-dev skill workflow — Read-Only, No Code Change)
Reference: giso-dev/SKILL.md pipeline کامل — Freshness → Discovery → Patterns → Impact → Council → Plan+Scope Lock → STOP
Scope Lock: ALLOWED FILES = [rp6.md] — هیچ کد دیگری تغییر نکرده (قانون Read-Only verbs: بررسی/گزارش/پیشنهاد هرگز فایل تغییر ندهند)
Method: Code is Truth, Reuse > Extend > New, Existing Architecture First
Branch: arena/01a0eecf-giso4 HEAD=f9a7fb0feaba9a604ab38712c675d90618127d12 (clean قبل نوشتن، dirty بعد نوشتن فقط rp6.md)

---

## ۱. Request interpretation

- Restated goal: بررسی کامل ساختار موجود Beauty Center / سالن زیبایی، پنل سالن و آگهی خدمات سالن از روی کد واقعی (نه داک)، ارزیابی سناریوی «آگهی بر اساس خدمات» از 3 دید کاربر/صاحب سالن/Giso، طراحی UX لوکس ساده Mirror→نتیجه→سالن‌های همان خدمت→نمونه‌کار+قیمت+پیشنهاد→مشاهده→رزرو، طراحی سناریوی پیشنهادی User Panel/صفحه سالن/پنل سالن/Admin، جدول Reuse با اولویت Reuse>Extend>New، بررسی DB و مدل درآمدی، اولویت‌بندی P0/P1/P2، خروجی 11 بخش + Plan+Scope Lock + STOP منتظر تایید.
- Assumptions low-risk: زبان فارسی RTL موجود کافی است، شهر پیش‌فرض مشهد، فیلتر service موجود در list_centers، Mirror 4 خدمت (eyebrow, nail, hair_color, lip_shading) فعال، قیمت با format_toman نمایش داده می‌شود، رزرو با BEGIN IMMEDIATE امن است.
- Clarification needed: none — task صراحتاً Read-Only است.

## ۲. Freshness (Phase-0)

```
Freshness: HEAD=f9a7fb0 branch=arena/01a0eecf-giso4 working-tree=dirty(16 modified + 9 untracked incl rp5.md) قبل reset
Graph: STALE (built at c9b198cd vs HEAD f9a7fb0)
Docs: STALE (PROJECT_GUIDE updated 2026-09-29 branch arena/01a0e0b8 vs current 01a0eecf)
Memory: absent (project_memory/letta/PROJECT_MEMORY.md not present in this checkout)
```
بعد از reset hard قبلی و نوشتن rp5.md: working-tree دوباره dirty فقط rp6.md (جدید) + rp5.md موجود. Graph STALE پس فقط grep/import analysis استفاده شد، نه Graph.

## ۳. Current state & real problem location — وضعیت فعلی دقیق از روی کد

### ۳.۱ سالن زیبایی — مدل/جدول Beauty Center

**جدول اصلی `beauty_centers` (schema.py:10-55):**
- id PK, owner_user_id UNIQUE FK→giso_web_auth.id, name 160, slug UNIQUE (seed+secrets), category (hair, skin_face, beauty) → CENTER_CATEGORIES, center_type 7 نوع (salon, hair_center, skin_beauty, independent, nail_center, bridal, licensed_clinic) → CENTER_TYPES
- city indexed, region, address_summary 300, business_phone normalized via normalize_phone, salon_phone, display_phone_choice business/salon, contact_time, description 700
- services_json '[]' — تگ‌های انتخابی از SERVICES dict (20 کلید)
- image_path کاور, status pending_review/reviewing/published/rejected/paused/closed → STATUS_FA, admin_note, terms_version beauty-centers-v1, terms_accepted_at
- counters: views_count, contact_clicks, analysis_impressions, price_inquiry_clicks
- pricing center-level: price_level economic/standard/premium/on_request, starting_price INTEGER
- expiry/promotion: listing_expires_at, promotion_type, promotion_expires_at, promotion_bumped_at
- flags: is_active, is_featured, sort_order
- migration additive: salon_phone, display_phone_choice, last_edit_at, listing_expires_at etc via PRAGMA check + ALTER TABLE

**SERVICES dict (services.py):** 20 کلید: haircut, hair_color, bleach, hair_repair, keratin, straightening, extension, braid, scalp_care, facial, skin_cleansing, skin_hydration, face_care, makeup, hairstyle, brow, lip_shading, lash, nail, bridal — شامل 4 کلید Mirror: brow, nail, lip_shading, hair_color. CATEGORY_SERVICES: hair 9, skin_face 7 (facial, skin_cleansing, skin_hydration, face_care, brow, lip_shading, lash), beauty 7 (makeup, hairstyle, brow, lip_shading, lash, nail, bridal). CATEGORY_CENTER_TYPES mapping category→allowed types.

**جداول مرتبط (schema.py + pricing/schema.py + reservations/schema.py):**
- `beauty_center_images` id, center_id FK CASCADE, image_path, sort_order, created_at — گالری عمومی 3 تصویر max (owner_gallery_upload check count+1 if cover else), validation MAX_BYTES 5MB, MAX_PIXELS 20M, MAX_SIDE 12000, JPEG/PNG/WEBP via save_center_image
- `beauty_center_services` id, center_id, name NOT NULL, category '', description '', duration_minutes 30, price_min 0, price_max 0, is_active 1, sort_order 0, created_at, updated_at (legacy) — خدمات دقیق با قیمت و مدت، قابل مدیریت در پنل سالن، ordered is_active DESC, sort_order ASC
- `beauty_center_working_hours` id, center_id, day_of_week 0=شنبه تا 6=جمعه, open_time '', close_time '', is_closed 0, slot_minutes 30, legacy weekday/is_open sync for NOT NULL + UNIQUE(center_id, weekday)
- `beauty_center_conversations` id, center_id, user_id, status active/closed, last_message_at, UNIQUE(center_id,user_id) — گفتگوی کاربر و سالن
- `beauty_center_messages` id, conversation_id, sender_user_id, message_text, is_read, is_reported
- `beauty_center_feedback` id, center_id, conversation_id, user_id, response_level, price_level, overall_level, comment, status pending, UNIQUE(conversation_id,user_id) — امتیاز و نظر
- `beauty_center_reservations` id, center_id, user_id, user_phone, user_name, service_id snapshot, service_name snapshot 200, service_price_min snapshot, duration_minutes snapshot, reservation_date شمسی YYYY-MM-DD, reservation_time HH:MM, status pending/confirmed/completed/cancelled_user/cancelled_center, user_note 500, center_note, reject_reason, reminded flags, created_at, confirmed_at, cancelled_at, **final_design_id INTEGER DEFAULT 0**, **service_key TEXT DEFAULT ''**, **selected_style TEXT DEFAULT ''** — اتصال Mirror کامل پیاده شده
- `beauty_center_promotions` id, center_id, owner_user_id, package_key, amount, starts_at, expires_at, transaction_key UNIQUE, status active — برای Featured/Promotion
- `beauty_center_discounts` id, center_id, title, description, discount_value, expires_at, status pending — تخفیف
- `beauty_center_events` id, center_id DEFAULT 0, event_type, user_id DEFAULT 0, created_at — برای Lead/Analytics
- `beauty_center_expiry_notices` id, center_id, notice_key UNIQUE
- `beauty_center_reports` id, center_id, reporter_user_id, reason, message, status open

**ثبت سالن:** routes.py register GET/POST, form fields: name, category, center_type, city, region, address_summary, business_phone, salon_phone, display_phone_choice, contact_time, description, services multi-select 16 max from SERVICES, price_level, starting_price, image. Validation _normalize_fields: category in CENTER_CATEGORIES, center_type in CATEGORY_CENTER_TYPES[category], services in CATEGORY_SERVICES[category], price_level in PRICE_LEVELS, city required, phone normalized.

**وضعیت تأیید:** STATUS_FA 6 وضعیت, admin_set_status with guarded transition via panel_admin.py handle_beauty_status, bot_handlers.py beauty_admin_menu_kb (درخواست‌های جدید, مراکز منتشرشده, منقضی و متوقف, وضعیت مراکز, اعتبار آگهی, تنظیمات). Bot actions review, publish, reject, pause.

**اطلاعات تماس/آدرس/تصاویر/خدمات/قیمت/ساعات/فعال/امتیاز/رزرو/پیام/آگهی:**
- تماس: business_phone, salon_phone, display_phone_choice, contact_time, reveal via center_contact POST intent price_inquiry + increment contact_clicks
- آدرس: city indexed idx_beauty_centers_city, region, address_summary
- تصاویر: image_path کاور + beauty_center_images گالری, media routes center_media, gallery_media with static_root check, X-Content-Type-Options nosniff
- خدمات: SERVICES 20 + CATEGORY_SERVICES + beauty_center_services with price_min/max/duration/is_active
- قیمت: service price_min/max + center price_level/starting_price + _service_price_label with format_toman + duration_label
- ساعات: get_working_hours, save_working_hours BEGIN IMMEDIATE upsert, day_label Persian, time_label
- فعال/غیرفعال: is_active, listing_expired check (listing_expires_at < now), promotion_active (promotion_type + promotion_expires_at > now), is_featured + sort_order for featured query 6
- امتیاز: feedback summary response_level, price_level, overall_level, score, score100, count>=3, label
- رزرو: create_reservation BEGIN IMMEDIATE, _working_day, _service_of, _is_available, _build_slots, _active_bookings, snapshot rule, _transition guarded, confirm/reject/complete/cancel_by_user, notify_new_reservation, notify_user_confirmed/rejected, calendar month, slots JSON
- پیام: get_or_create_conversation, send_conversation_message, conversation_messages, owner_conversations, unread count, close_conversation, feedback submission
- آگهی/Featured/Promotion: is_featured, sort_order, promotion_type, promotion_expires_at, promotion_bumped_at, beauty_center_promotions, center_promotion_availability, purchase_center_promotion with purchase_nonce, renew_center_listing, process_center_expiry_notifications throttled 10min, discount_service_active check, active_discount legacy

### ۳.۲ پنل سالن — قابلیت‌های فعلی

**Owner Dashboard (routes.py owner_dashboard + owner_dashboard.html):**
- Context _owner_panel_context includes USER_MODULES + beauty_center menu, notifications, wallet balances, analysis_count
- Tabs فعلی از template: اطلاعات پایه (name, category, type, city, region, address, phone, contact_time, description, price_level, starting_price, services_json multi-select), خدمات (get_center_services, add_service, update_service, delete_service via pricing/services.py with _clean_service validation name required, duration 1-1440, price_min/max), ساعات کاری (get_working_hours, save_working_hours with _clean_working_day), تصاویر (save_center_image, gallery upload/delete, main image delete with replacement), پیام‌ها (owner_conversations, conversation_messages, close), رزروها (owner_list JSON, owner_action POST confirm/reject/complete, calendar, slots), آمار (views_count, contact_clicks, analysis_impressions, price_inquiry_clicks + beauty_stats), وضعیت انتشار (status_label, listing_expired, promotion_active, renew, promote, discount POST), گالری (max 3 images)
- مدیریت اطلاعات: update_owner_center with _normalize_fields
- مدیریت خدمات: add_service, update_service, delete_service, get_center_services
- قیمت: service price_min/max + center price_level/starting_price + toman
- تصاویر/نمونه‌کار: save_center_image with format/size validation, beauty_center_images — ولی دسته‌بندی بر اساس خدمت ندارد (Gap اصلی)
- رزروها: reservations/routes.py reserve GET/POST with service_id, date, slots, user_note, final_design_id, service_key, selected_style from query; owner_list, owner_action; notifications via broadcasts_center
- مشتری‌ها: conversations + messages + feedback
- آمار: views, contact_clicks, analysis_impressions, price_inquiry_clicks, beauty_stats
- آگهی: promotions, discounts, is_featured, promotion_type, renew, promote
- وضعیت انتشار: status, listing_expired, promotion_active

### ۳.۳ کاربر — Flow فعلی

- پیدا کردن سالن: /beauty-centers?q=&city=&category=&type=&service=&price_level= — list_public_centers with filters query, city, category, center_type, service, price_level, plus featured 6, related via recommended_centers(analysis_id, user_id, city), noindex if query, beauty_stats (centers, views, hair, skin)
- خدمات سالن را می‌بیند: /beauty-centers/<slug> — get_center_by_slug, is_owner/is_staff, increment_view if published not owner/staff, _center_services_for_display (price_label, duration_label), _center_hours_for_display, revealed contact if owner/staff, feedback summary, active_discount, discount_service_active
- نتیجه Beauty Mirror را می‌بیند: /analysis/mirror/ mirror_home 4 کارت active (eyebrow, nail, hair_color, lip_shading) با icon/badge/tag/description/meta, href to /analysis/mirror/{slug} → generic_service_wizard (model selection 5 styles with sample 520x360) → /{slug}/upload (photo upload preview+guide+sample) → process_service_submission (save_eyebrow_photo prefix service_key, check_photo_quality AI first fallback local, detect_regions color segmentation, analyze_*_photo AI first fallback) → build_result (quality+detection+ai_analysis+short_reason+do/avoid) → _store_new_service_candidate session → /{slug}/final (generate_final_design via service_image_generation with mask gate + provider chain + fallback guided composite, validation validate_masked_output, save_final_design with session_id, user_id, service_type, original_filename, final_filename, selected_style, recommended_style, change_level, provider, model, status, prompt_json) → generic_final_design.html: Before/After, service/style/change labels, AI status is_ai_generated, provider, model, validation, do/avoid, interest question bti-final-interest Lead vs View, centers suggestions enrich with mirror_match_reason+mirror_tags+mirror_score, consultant invite+chat POST /{slug}/consultant with build_consultant_context
- سالن پیشنهادی دریافت می‌کند: _enrich_generic_centers(service_key, centers, candidate, city) — score: 45 if has_service (service_filter in services), 20 if city_match, 15 if is_featured, up to 20 from feedback score100//5, sorted by -mirror_score, mirror_rank; tags: service_label, همان شهر, feedback label; match reason: "برای اجرای {final_label}، این مرکز به‌عنوان ارائه‌دهنده {service_label} پیشنهاد شده است."
- وارد صفحه سالن می‌شود: center_detail + reserve link with final_design_id, service_key, selected_style → /beauty-centers/<slug>/reserve?service_id=&date=&final_design_id=&service_key=&selected_style=
- رزرو می‌کند: reserve GET (service_id, date, slots via get_available_slots, calendar via get_calendar_month) + POST (create_reservation with final_design_id, service_key, selected_style snapshot, BEGIN IMMEDIATE, notify_new_reservation) → my_reservations list with status labels, cancel_by_user

### ۳.۴ Beauty Mirror — ارتباط فعلی دقیق

**Code truth (buti_ai/schema.py + routes.py + generic_service.py + reservations/schema.py):**
- `buti_ai_sessions` id, user_id, service_type, city, center_id, conversation_id, status, created_at — Mirror session
- `buti_ai_final_designs` id, session_id, user_id, service_type (eyebrow, nail, hair_color, lip_shading), original_filename, final_filename, selected_style, recommended_style, change_level, provider, model, status, prompt_json, created_at — index user+created, session — ذخیره نهایی طراحی
- `buti_ai_service_demand` + `buti_ai_waitlist` برای وقتی مرکز فعال نیست: city, service_type, dedupe_key, payload_json, status
- `service_key` در generic_service: nail, hair_color, lip_shading, eyebrow — کلید داخلی Mirror، در SERVICE_CATALOG mapping beauty_center_service: brow, nail, hair_color, lip_shading — نگاشت Mirror به Beauty Center service
- `selected_style` در candidate: final_style, selected_style, selected_label, final_label — 5 استایل هر خدمت (nail: natural, french, baby_boomer, etc; hair_color: caramel_balayage, etc; lip_shading: natural_shading, etc; eyebrow: natural, powder, microblading, combination, giso_suggested)
- `final_design_id` در candidate: design_id از save_final_design → ذخیره در session _new_service_candidate_key(service_key) + FINAL_DESIGN_SESSION_KEY برای eyebrow
- `beauty_center_reservations` final_design_id, service_key, selected_style — اتصال کامل: رزرو از Mirror با final_design_id, service_key, selected_style snapshot، قابل نمایش در owner_list و my_reservations
- `beauty_center_services` — هنوز service_key ندارد (فقط name, category) — Gap: نمی‌توان مستقیم service_key را به service_id نگاشت کرد مگر با name mapping دستی
- `beauty_center_images` — هنوز service_key ندارد — Gap: نمونه‌کار بر اساس خدمت قابل فیلتر نیست
- Flow فعلی: Mirror result → centers enrich (service_key→beauty_center_service mapping) → list_centers?service={beauty_center_service} → center_detail → reserve?service_id={id}&final_design_id={id}&service_key={key}&selected_style={style} → create_reservation snapshot
- قابل استفاده مستقیم: Mirror 4 خدمت فعال با Quality AI+Detection+Analysis AI+Generation+Validation+Final+Consultant+Interest+Centers enrich+Reservation link — PASS
- کمبود: Portfolio per service (beauty_center_images بدون service_key), Featured Service per service (فقط center-level is_featured), Service Key column در beauty_center_services, User Panel Mirror History (buti_ai_final_designs موجود ولی نمایش داده نمی‌شود در panel_user)

## ۴. Architecture & current pattern

**Convention table (از کد واقعی این نشست):**

| Seam | House pattern (file evidence) | What change will do (اگر تایید شود) |
|---|---|---|
| DB access | `get_giso_db_conn()` from `giso/base.py` with WAL, busy_timeout 5000, foreign_keys ON — همه جا استفاده می‌شود: beauty_centers/schema.py, pricing/schema.py, reservations/schema.py, services.py, buti_ai/schema.py, routes.py | reuse same helper, no new helper |
| Auth/role guard | `@login_required` from flask_login + `_user_id()` + `_is_staff()` check giso_admins, owner check owner_user_id == _user_id() | reuse same guards for owner_dashboard, reserve, chat |
| CSRF handling | `csrf_token()` hidden input in all POST forms (owner_dashboard.html, reserve.html, chat.html) | follow same form shape |
| Notification hook | `panel/modules/notifications` event → notification, plus `beauty_centers/reservations/notifications.py` notify_new_reservation, notify_user_confirmed/rejected via ThreadPoolExecutor _CENTER_NOTIFY_POOL | reuse same notification pattern |
| Bot flow | `giso/buti_ai/bot_handlers.py` state machine with buti_ai generic_service, plus `beauty_centers/bot_handlers.py` beauty_admin_menu_kb | extend bot_handlers with new service flow if needed, not fork |
| Template/CSS | `templates/beauty_centers/` extends base.html, bc-* classes, beauty_centers.css v13, beauty_centers.js v4, card partial _card.html | extend existing blocks, add service-card partial reuse _card |
| AI call | `giso/ai_runtime*` + proxy manager + credits via `ai_credits.py`, provider/model from `ai_models_registry.py` + `buti_ai/ai_models.py` configured_image_provider_dicts with task_key image_task_for_service(service_key) | reuse same entry points for new services |
| Migration | Additive only: PRAGMA table_info check + ALTER TABLE ADD COLUMN + CREATE INDEX IF NOT EXISTS + CREATE TABLE IF NOT EXISTS, never DROP/RECREATE — see pricing/schema.py, reservations/schema.py, beauty_centers/schema.py | same pattern for new columns service_key |
| Pricing services | 6 functions exactly: get_center_services, add_service, update_service, delete_service, get_working_hours, save_working_hours — via get_giso_db_conn | extend _clean_service to accept service_key optional |
| Reservations | BEGIN IMMEDIATE transaction, snapshot rule, _is_available, _build_slots, _active_bookings, _transition guarded, notify hooks | reuse same transaction pattern |
| Center listing | list_public_centers with filters q/city/category/type/service/price_level, plus featured 6, related via recommended_centers, beauty_stats, increment_view, reveal_contact, decorate_center | reuse same listing with service filter |

**Current architecture summary:** ماژول beauty_centers با 10 فایل + pricing + reservations + panel_admin + bot_handlers + routes + services + schema + templates + static — Flask Blueprint beauty_centers_bp url_prefix / + beauty_reservations_bp + buti_ai_bp /analysis/mirror/. Shared DB giso.db single source truth, WAL mode, additive migrations, ThreadPoolExecutor for notifications, CSRF protected forms, owner vs staff guards, service filtering via SERVICES dict + beauty_center_services table, reservation snapshot + BEGIN IMMEDIATE, Mirror integration via final_design_id/service_key/selected_style in reservations + buti_ai_final_designs, enrich scoring 45 has_service+20 city+15 featured+feedback.

## ۵. Dependencies & impact

- Internal imports: `giso.base.get_giso_db_conn`, `giso.config.Config`, `giso.beauty_centers.services` (SERVICES, CENTER_TYPES, STATUS_FA, decorate_center, list_public_centers, save_center_image, etc), `giso.beauty_centers.pricing.services` (get_center_services, add_service, update_service, delete_service, get_working_hours, save_working_hours), `giso.beauty_centers.reservations.services` (get_available_slots, get_calendar_month, create_reservation, owner_list, etc), `giso.beauty_centers.reservations.notifications`, `giso.buti_ai.service_catalog` (SERVICE_CATALOG, get_service_meta, supported_service_keys), `giso.buti_ai.generic_service` (process_service_submission, build_final_candidate, generate_final_design), `giso.buti_ai.service_image_generation`, `giso.buti_ai.schema` (init_buti_ai_db), `giso.buti_ai.ai_models` (configured_image_provider_dicts, image_task_for_service), `giso.money.format_toman`, `giso.panel_user.routes`, `giso.bot` for handlers
- Shared DB tables: beauty_centers, beauty_center_services, beauty_center_working_hours, beauty_center_images, beauty_center_conversations, beauty_center_messages, beauty_center_feedback, beauty_center_reservations, beauty_center_promotions, beauty_center_discounts, beauty_center_events, beauty_center_expiry_notices, beauty_center_reports, buti_ai_sessions, buti_ai_final_designs, buti_ai_service_demand, buti_ai_waitlist, giso_web_auth, giso_config, giso_admins
- Notification events: new_reservation, user_confirmed, user_rejected via broadcasts_center, plus panel/modules/notifications
- AI runtime coupling: ai_runtime, ai_credits, ai_models_registry, buti_ai/ai_models provider chain
- Sibling features sharing code: marketplace, hair_sale, analyses, chats, orders, wallet, profile, reviews, overview in panel_user; eyebrow, nail, hair_color, lip in buti_ai; broadcasts_center
- Out of scope neighbors: bot_edu/, web/, graphify-out/, project_memory/, data/, .env, main.py

## ۶. بررسی سناریوی «آگهی سالن بر اساس خدمات» — از 3 دید

### ۶.۱ کاربر

- **آیا راحت‌تر تصمیم می‌گیرد؟** بله — کاربر الان در list.html همه مراکز را با فیلتر service می‌بیند ولی کارت مرکز عمومی است (_card.html فقط name, type, city, price_level, starting_price). اگر کارت خدمت باشد (مثلاً "بالیاژ کاراملی — از ۸۰۰ هزار — نمونه‌کار همان خدمت + تخفیف + CTA رزرو")، تصمیم سریع‌تر است چون مستقیماً خدمت مورد علاقه‌اش را می‌بیند نه کل سالن. Mirror→نتیجه→سالن‌های همان خدمت Flow موجود enrich می‌کند ولی کارت هنوز عمومی است — اگر کارت خدمت باشد، UX لوکس‌تر می‌شود.
- **آیا سردرگمی ایجاد می‌کند؟** اگر هر سالن 10 کارت خدمت نشان دهد، شلوغ می‌شود — باید محدود کرد: فقط خدمات فعال (is_active=1) + sort_order + حداکثر 3 خدمت برجسته در list، بقیه در detail. با ساختار فعلی beauty_center_services already is_active + sort_order دارد — قابل کنترل است. پس سردرگمی قابل مدیریت است.
- **آیا مستقیماً خدمت مورد علاقه را پیدا می‌کند؟** بله — فیلتر service موجود است (list_centers?service=nail) ولی نتیجه مراکز است نه خدمات. اگر آگهی ← خدمت باشد، می‌توان /beauty-centers/services?service=nail لیست کارت‌های خدمت (نه مرکز) با نمونه‌کار همان خدمت + قیمت + پیشنهاد + CTA را نشان داد — این دقیقاً خواسته کاربر است.

### ۶.۲ صاحب سالن

- **آیا می‌تواند خدمات قابل ارائه را معرفی کند؟** بله — الان add_service با name, category, description, duration, price_min/max, is_active, sort_order دارد — می‌تواند هر خدمت را جدا معرفی کند. ولی نمونه‌کار (beauty_center_images) دسته‌بندی بر اساس خدمت ندارد — Gap: اگر سالن 5 خدمت دارد و 3 تصویر، نمی‌داند کدام تصویر مربوط به کدام خدمت است.
- **آیا مدیریت ساده است؟** الان owner_dashboard تب خدمات دارد ولی برای هر خدمت باید name دستی بنویسد، category انتخاب کند، قیمت و مدت وارد کند — ساده است. اگر service_key اضافه شود (optional TEXT) و تصویر هم service_key داشته باشد، مدیریت همچنان ساده می‌ماند: یک dropdown "مرتبط با خدمت" در فرم خدمت و گالری.
- **آیا روی خدمات مهم‌تر تمرکز می‌کند؟** بله — با is_active + sort_order + is_featured per service (پیشنهادی) می‌تواند خدمت پول‌ساز را بالا بیاورد و بقیه را غیرفعال کند. الان is_active دارد ولی Featured فقط در سطح مرکز است — اگر Featured Service اضافه شود، تمرکز بیشتر می‌شود.

### ۶.۳ کسب‌وکار Giso

- **آیا ارزش تجاری دارد؟** بله — هر خدمت inventory برای فروش است: Featured Service (مرکز برای خدمت "رنگ مو" پول بدهد تا در لیست رنگ مو بالا بیاید)، Promotion per service (package_key + service_id)، تخفیف per service (beauty_center_discounts الان فقط center_id دارد، اگر service_id اضافه شود می‌تواند تخفیف برای خدمت خاص باشد)، تبلیغ هدفمند بر اساس Mirror result (service_key)، پیشنهاد خدمت بر اساس selected_style, رزرو با final_design_id (already implemented).
- **قابلیت تبدیل به Featured/Promotion/تخفیف/تبلیغ هدفمند/پیشنهاد/رزرو؟** 
  - Featured Service: الان is_featured فقط مرکز — اگر is_featured_service یا featured_service_id اضافه شود، قابل پیاده‌سازی است — P1 ارزشمند
  - Promotion: beauty_center_promotions الان فقط center_id — اگر service_id optional اضافه شود، promotion per service ممکن می‌شود — P1
  - تخفیف: beauty_center_discounts الان فقط center_id — اگر service_id اضافه شود، تخفیف per service — P1
  - جایگاه ویژه: sort_order در beauty_center_services already exists — می‌تواند برای جایگاه ویژه per service استفاده شود — P0
  - پیشنهاد بر اساس Mirror/service_key: _enrich_generic_centers already service_key → beauty_center_service mapping دارد — P0 موجود
  - رزرو: final_design_id/service_key/selected_style already in reservations — P0 موجود
- **نتیجه:** مدل «آگهی ← خدمت سالن» از نظر محصولی خوب است و از نظر تجاری بهتر از «آگهی کلی سالن» است چون inventory بیشتر و هدفمندتر است. توصیه: YES، ولی با محدودیت لوکس: هر مرکز حداکثر 3 خدمت برجسته در لیست عمومی، بقیه در صفحه detail.

## ۷. بررسی UX لوکس و ساده — Flow پیشنهادی

**Flow فعلی (موجود و کار می‌کند):**
```
Beauty Mirror (/analysis/mirror/ 4 کارت) 
→ Style Selection (5 مدل per service با sample 520x360)
→ Upload (preview+guide+sample)
→ Quality AI (configured_vision_chain first, local fallback) + Detection (color segmentation) + Analysis AI (analyze_*_photo)
→ Generation (Before/After + validation + provider/model + is_ai_generated)
→ نتیجه (final_label + do/avoid + interest question Lead vs View + centers enrich score+tags+match reason + consultant invite)
→ سالن‌های همین خدمت (list_centers?service={beauty_center_service} + _enrich_generic_centers score 45 has_service+20 city+15 featured+feedback)
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
- Gap فقط Portfolio per service (beauty_center_images بدون service_key) — برای P0 می‌توان با naming convention یا category field موقت حل کرد، برای P1 ستون service_key اضافه شود (additive).

## ۸. طراحی سناریوی پیشنهادی کامل ولی ساده

### ۸.۱ User Panel

**کاربر چه می‌بیند؟**
- در `/panel/beauty-centers` (اگر موجود نیست، جدید) یا در `/panel/overview`: لیست مراکز مورد علاقه + رزروهای من + پیام‌ها + Mirror History (جدید)
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
- "علاقه‌مندی" → (P2) save to wishlist

### ۸.۲ صفحه سالن

**چه اطلاعاتی نمایش داده شود؟**
- Header: name, type_label, category_label, city, region, trust line (اطلاعات تماس بررسی شده), views_count, is_featured badge, promotion_active badge
- Description: 700 char max
- Cost: price_level_label + starting_price with toman + note "قیمت نهایی پس از بررسی"
- Services: کارت لوکس هر خدمت فعال: name, category, description, duration_label, price_label, sort_order, is_active check, CTA رزرو
- Hours: beauty_hours per day with day_label Persian + time_label
- Facts: address_summary, contact_time, views
- Gallery: center carousel with main + beauty_center_images (max 3) — P1: filter by service_key if ?service= in query
- Contact: chat + phone reveal with intent price_inquiry + disclaimer
- Score: feedback score if count>=3
- Legal: disclaimer حدود نقش گیسو
- Related: centers with same service

**خدمات چگونه نمایش داده شوند؟**
- کارت لوکس: bc-service-item با head (icon+name+category), note (description), meta (price_label + duration_label), CTA reserve button — موجود در detail.html ولی می‌تواند لوکس‌تر شود: اضافه کردن نمونه‌کار همان خدمت (1 تصویر thumb) + تخفیف badge + پیشنهاد ویژه badge

**نمونه‌کار چگونه نمایش داده شود؟**
- فعلی: carousel عمومی — P1: اگر ?service=nail در query، فقط تصاویری که service_key=nail دارند نمایش داده شوند (نیاز به ستون service_key در beauty_center_images)

**قیمت چگونه نمایش داده شود؟**
- فعلی: _service_price_label with format_toman + duration_label — کافی است، لوکس است — P0 Reuse

**پیشنهاد ویژه چگونه نمایش داده شود؟**
- فعلی: active_discount legacy + discount_service_active — P1: beauty_center_discounts with service_id + title + discount_value + expires_at + status pending/visible — badge "پیشنهاد ویژه" در کارت خدمت

**رزرو چگونه انجام شود؟**
- فعلی: reserve route GET with service_id, date, slots JSON, calendar JSON + POST create_reservation with final_design_id, service_key, selected_style snapshot + BEGIN IMMEDIATE + notify — P0 Reuse کامل

### ۸.۳ پنل سالن — صاحب سالن دقیقاً چه مدیریت کند؟

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

**منوهای P2 بعداً (فعلاً شلوغ نکن):**
- Instagram/Logo, ظرفیت پیشرفته, علاقه‌مندی‌ها, تبلیغ هدفمند پیچیده

**دقیقاً چه فیلدهایی برای هر خدمت؟**
- name (الزامی), category (optional), description (500), duration_minutes (1-1440), price_min, price_max, is_active (فعال/غیرفعال), sort_order (ترتیب), service_key (P1 optional: brow, nail, lip_shading, hair_color, haircut, etc for Mirror mapping), is_featured_service (P1 optional boolean for Featured Service)

### ۸.۴ Admin — ادمین چه کنترل کند؟

- مراکز: list with status filter pending_review/reviewing/published/rejected/paused/closed, city, category, type, search, featured, expired, promotion — actions: review, publish, reject, pause, close, set is_featured, sort_order, admin_note, listing_expires_at, promotion_type/expires/bumped
- خدمات: (P1) view services per center, edit price, is_active, sort_order
- رزروها: view all reservations with status filter, date range, center, user, service, final_design_id link to buti_ai_final_designs
- تصاویر: moderate gallery, delete
- پیام‌ها/گزارش‌ها: beauty_center_conversations, messages, reports, feedback with status pending/visible/rejected
- تخفیف‌ها/تبلیغات: beauty_center_discounts, promotions with status pending/active, approve/reject
- آمار: beauty_center_events, views, contact_clicks, analysis_impressions, service_demand, waitlist
- AI: provider/model assignment per service_key via ai_models_registry
- تنظیمات: terms_version, price_levels, center_categories, center_types, services dict

## ۹. جدول Reuse — مهم‌ترین بخش

| قابلیت | ساختار موجود | قابل استفاده مستقیم؟ | نیاز به تغییر؟ | فایل/ماژول |
|---|---|---|---|---|
| مدل Beauty Center | beauty_centers table 20+ fields, status 6, counters, pricing, expiry/promotion | ✅ بله | خیر | beauty_centers/schema.py |
| ثبت سالن | register route + _normalize_fields validation | ✅ بله | خیر | beauty_centers/routes.py, services.py |
| وضعیت تأیید | STATUS_FA + admin_set_status + bot_handlers | ✅ بله | خیر | beauty_centers/services.py, panel_admin.py, bot_handlers.py |
| اطلاعات تماس | business_phone, salon_phone, display_phone_choice, contact_time | ✅ بله | خیر | schema.py, services.py |
| آدرس | city indexed, region, address_summary | ✅ بله | خیر | schema.py |
| تصاویر عمومی | beauty_center_images + save_center_image validation | ✅ بله | خیر برای عمومی، P1 برای per service | schema.py, services.py, routes.py |
| خدمات سالن (نام/توضیح/مدت) | beauty_center_services name, category, description, duration | ✅ بله | خیر | pricing/schema.py, pricing/services.py |
| قیمت خدمات | price_min, price_max + price_level, starting_price + format_toman | ✅ بله | خیر | pricing/services.py, routes.py, money.py |
| ساعات کاری | beauty_center_working_hours per day_of_week + save_working_hours BEGIN IMMEDIATE | ✅ بله | خیر | pricing/schema.py, pricing/services.py |
| فعال/غیرفعال | is_active, is_featured, sort_order, listing_expired, promotion_active | ✅ بله | خیر | schema.py, services.py |
| امتیاز و نظر | beauty_center_feedback + summary score100 | ✅ بله | خیر | schema.py, services.py |
| رزرو با snapshot | beauty_center_reservations with service_id/name/price/duration snapshot + BEGIN IMMEDIATE + _is_available | ✅ بله | خیر | reservations/schema.py, services.py, routes.py |
| پیام/ارتباط | beauty_center_conversations UNIQUE + messages + close + feedback | ✅ بله | خیر | schema.py, services.py, routes.py |
| آگهی/Featured/Promotion | is_featured, promotion_type, promotions table, renew, promote | ✅ بله برای مرکز | P1 برای per service | schema.py, services.py, routes.py |
| لیست مراکز با فیلتر | list_public_centers q/city/category/type/service/price_level + featured 6 + related | ✅ بله | خیر | services.py, routes.py, list.html |
| صفحه سالن | center_detail + increment_view + services_for_display + hours_for_display + feedback + gallery + contact + chat | ✅ بله | خیر برای عمومی، P1 برای لوکس کارت خدمت | routes.py, detail.html |
| پنل سالن اطلاعات | owner_dashboard tab edit + update_owner_center | ✅ بله | خیر | routes.py, owner_dashboard.html |
| پنل سالن خدمات | get_center_services + add/update/delete | ✅ بله | P1 service_key optional | pricing/services.py, routes.py |
| پنل سالن ساعات | get_working_hours + save_working_hours | ✅ بله | خیر | pricing/services.py |
| پنل سالن تصاویر | save_center_image + gallery upload/delete + main delete | ✅ بله | P1 service_key | services.py, routes.py |
| پنل سالن رزروها | owner_list + owner_action confirm/reject/complete + calendar + slots + notify | ✅ بله | خیر | reservations/services.py, routes.py |
| پنل سالن پیام‌ها | owner_conversations + messages + close | ✅ بله | خیر | services.py |
| پنل سالن آمار | views, contact_clicks, analysis_impressions, price_inquiry_clicks, beauty_stats | ✅ بله | خیر | services.py, routes.py |
| Mirror 4 خدمت | SERVICE_CATALOG 4 active + generic_service + service_image_generation + validation | ✅ بله | خیر | buti_ai/service_catalog.py, generic_service.py, service_image_generation.py |
| Quality AI + Detection | check_photo_quality AI first fallback local + detect_regions color segmentation | ✅ بله | خیر | buti_ai/eyebrow/quality.py, landmarks.py, generic_service.py |
| Generation با mask gate | generate_final_design with mask gate + provider chain + fallback guided composite + validate_masked_output | ✅ بله | خیر | buti_ai/service_image_generation.py, image_validation.py |
| Final Design ذخیره | buti_ai_final_designs with session_id, user_id, service_type, original/final filename, selected_style, provider, model, prompt_json | ✅ بله | خیر | buti_ai/schema.py, final_design.py |
| service_key نگاشت | SERVICE_CATALOG beauty_center_service mapping brow/nail/hair_color/lip_shading | ✅ بله | خیر | buti_ai/service_catalog.py |
| selected_style | 5 styles per service with STYLES dict + DEFAULT_STYLE | ✅ بله | خیر | buti_ai/nail/final_design.py, hair_color/final_design.py, lip/final_design.py, eyebrow/final_design.py |
| final_design_id در رزرو | beauty_center_reservations final_design_id + service_key + selected_style + create_reservation snapshot | ✅ بله | خیر | reservations/schema.py, services.py |
| Centers enrich با Mirror | _enrich_generic_centers score 45 has_service+20 city+15 featured+feedback + tags + match reason | ✅ بله | خیر | buti_ai/routes.py |
| Consultant + Interest | build_consultant_context + consultant_invite_text + bti-final-interest Lead vs View + demand + waitlist | ✅ بله | خیر | buti_ai/consultant.py, routes.py, services.py |
| User Panel Mirror History | buti_ai_final_designs table موجود ولی نمایش در panel_user ندارد | ❌ ندارد | Extend: new module panel_user/modules/mirror.py reuse analyses.py pattern | panel_user/modules/analyses.py → new mirror.py |
| Portfolio per service | beauty_center_images بدون service_key | ❌ ندارد | Extend: ALTER TABLE ADD COLUMN service_key TEXT DEFAULT '' + index + UI dropdown | beauty_centers/schema.py, services.py, routes.py, owner_dashboard.html |
| Featured Service per service | is_featured فقط center-level | ❌ ندارد | Extend: ALTER TABLE beauty_center_services ADD COLUMN is_featured_service INTEGER DEFAULT 0 + service_key TEXT | pricing/schema.py, services.py |
| Discount per service | beauty_center_discounts فقط center_id | ❌ ندارد | Extend: ALTER TABLE ADD COLUMN service_id INTEGER DEFAULT 0 | schema.py |
| Promotion per service | beauty_center_promotions فقط center_id | ❌ ندارد | Extend: ALTER TABLE ADD COLUMN service_id INTEGER DEFAULT 0 | schema.py |
| Service Key در services | beauty_center_services بدون service_key | ❌ ندارد | Extend: ADD COLUMN service_key TEXT DEFAULT '' + index | pricing/schema.py |
| Bale Mirror flow | buti_ai/bot_handlers.py generic_service flow | ⚠️ نیمه موجود | Extend: reuse generic_service for Bale | buti_ai/bot_handlers.py, bot.py |

**اولویت Reuse > Extend > New:**
- Reuse مستقیم 80% — همه چیز اصلی موجود است
- Extend با 2-3 ستون additive 20% — service_key در beauty_center_services + beauty_center_images + service_id در promotions/discounts + is_featured_service — migration additive via ALTER TABLE ADD COLUMN (همان pattern ai_credits fix)
- New Architecture 0% — هیچ ماژول جدید لازم نیست مگر panel_user mirror history که reuse analyses.py pattern است

## ۱۰. بررسی دیتابیس — آیا جدول‌ها کافی هستند؟

**بررسی هر جدول:**

- `beauty_centers`: کافی است برای P0 — 20+ فیلد، status, is_active, is_featured, city indexed, pricing, expiry/promotion, counters — هیچ تغییر لازم نیست برای MVP
- `beauty_center_services`: کافی برای P0 — name, category, description, duration, price_min/max, is_active, sort_order — برای P1 پیشنهادی: ADD COLUMN service_key TEXT DEFAULT '' (برای نگاشت به Mirror service_key brow/nail/hair_color/lip_shading) + ADD COLUMN is_featured_service INTEGER DEFAULT 0 (برای Featured Service per service) — migration additive, index on service_key
- `beauty_center_images`: کافی برای P0 عمومی — ولی برای Portfolio per service نیاز به ADD COLUMN service_key TEXT DEFAULT '' — تا بتوان gallery را بر اساس خدمت فیلتر کرد — P1
- `beauty_center_reservations`: کافی و کامل — final_design_id, service_key, selected_style already implemented — هیچ تغییر لازم نیست — P0 Reuse
- `buti_ai_mirror_sessions` (buti_ai_sessions): کافی — user_id, service_type, city, center_id, status, created_at — هیچ تغییر لازم نیست
- `buti_ai_final_designs`: کافی — session_id, user_id, service_type, original/final filename, selected_style, recommended_style, change_level, provider, model, status, prompt_json, created_at — هیچ تغییر لازم نیست — برای User Panel Mirror History فقط SELECT نیاز است

**اگر نیاز به تغییر DB وجود دارد، دقیق:**

- **چه فیلدی؟** service_key TEXT DEFAULT '' + is_featured_service INTEGER DEFAULT 0 در beauty_center_services, service_key TEXT DEFAULT '' در beauty_center_images, service_id INTEGER DEFAULT 0 در beauty_center_promotions, service_id INTEGER DEFAULT 0 در beauty_center_discounts
- **در کدام جدول؟** beauty_center_services, beauty_center_images, beauty_center_promotions, beauty_center_discounts
- **چرا؟** برای دسته‌بندی نمونه‌کار بر اساس خدمت (UX لوکس)، برای Featured Service per service (درآمد)، برای تخفیف/promotion per service (درآمد هدفمند)، برای نگاشت Mirror service_key به service_id دقیق (به جای name mapping)
- **آیا می‌توان بدون تغییر DB انجام داد؟** بله برای P0 — با ساختار فعلی قابل انجام است: نمونه‌کار عمومی نمایش داده شود، Featured فقط center-level، تخفیف عمومی، service_key از name mapping حدسی — توصیه: P0 بدون تغییر DB، P1 با 2 ستون additive (service_key در services + images) — همان pattern قبلی `ai_credits` fix با PRAGMA check + ALTER TABLE

**نتیجه DB Impact:** P0 ضروری هیچ تغییر لازم نیست — 100% با ساختار فعلی قابل پیاده‌سازی است. P1 مهم 2 ستون additive پیشنهادی با migration additive (ALTER TABLE ADD COLUMN IF NOT EXISTS via PRAGMA) + index — هیچ DROP/RECREATE.

## ۱۱. بررسی آگهی و مدل درآمدی — آگهی عمومی vs آگهی ← خدمت

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

## ۱۲. اولویت‌بندی — P0/P1/P2

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

## ۱۳. فایل‌ها و ماژول‌های درگیر — مسیر دقیق

**موجود و درگیر در سناریو (Code Truth):**
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
- `giso/beauty_centers/templates/beauty_centers/` — list.html (search form q/city/category/type/service/price_level + featured + related + grid + _card.html), detail.html (bc-detail-grid, services list bc-service-item with price_label/duration_label + CTA reserve, hours, facts, carousel, contact, score, legal), _card.html (center card), _analysis_cta.html, owner_dashboard.html (tabs: info/services/hours/images/messages/reservations/stats/status + forms), register.html, chat.html, reserve.html, my_reservations.html, admin.html
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
- `giso/panel_user/routes.py` — panel_user Blueprint, overview, analyses, chats, marketplace, etc — برای اضافه کردن mirror history
- `giso/panel_user/modules/` — _base.py, analyses.py (pattern for mirror history), chats.py, overview.py, etc
- `giso/base.py` — get_giso_db_conn WAL + busy_timeout
- `giso/config.py` — Config.GISO_DIR for static_root
- `giso/money.py` — format_toman
- `giso/app.py` — Blueprint registration beauty_centers_bp, beauty_reservations_bp, buti_ai_bp, panel_user_bp

**اگر تایید شود و وارد فاز پیاده‌سازی شویم (Scope Lock پیشنهادی برای آینده):**
- ALLOWED (12 فایل): `beauty_centers/schema.py` (add service_key column to images additive), `beauty_centers/pricing/schema.py` (add service_key + is_featured_service to services), `beauty_centers/services.py` (save_center_image + promotion per service), `beauty_centers/pricing/services.py` (_clean_service accept service_key), `beauty_centers/routes.py` (display filter + gallery filter + owner_gallery_upload with service_key), `beauty_centers/templates/beauty_centers/owner_dashboard.html` (service_key dropdown + gallery service_key dropdown), `beauty_centers/templates/beauty_centers/detail.html` (service card لوکس with portfolio per service + discount badge + CTA), `panel_user/modules/mirror.py` NEW reuse analyses.py pattern (mirror history), `panel_user/routes.py` (register mirror module), `buti_ai/templates/buti_ai/generic_final_design.html` (service card CTA to service_id), `giso/buti_ai/routes.py` (enrich with service_id mapping), `rp6.md` (این گزارش)
- FORBIDDEN: `bot_edu/`, `web/`, `main.py`, `giso/bot.py` refactor, `graphify-out/`, `project_memory/`, `data/`, `.env`, `giso/buti_ai/eyebrow/` for new services (باید از generic_service استفاده شود)
- Shared/caution: schema.py (shared tables), services.py (shared listing), panel_user/routes.py (shared auth), buti_ai/routes.py (shared AI runtime)

## ۱۴. Council Review — 4 دیدگاه

**Architect:** PASS — تغییر در domain folder درست (beauty_centers + pricing + reservations + panel_user + buti_ai) — golden rule module in its own folder رعایت می‌شود — هیچ coupling جدید بین giso↔bot_edu یا web↔giso اضافه نمی‌شود — فقط additive columns + new module reuse pattern — هیچ new abstraction بی‌دلیل — تابع در ماژول موجود ترجیح داده شده.

**Domain:** PASS — رفتار مطابق semantics واقعی کد: SERVICES dict شامل brow/nail/lip_shading/hair_color — CATEGORY_SERVICES mapping درست — STATUS_FA 6 وضعیت — pricing with price_min/max/duration/is_active — working_hours per day_of_week 0=شنبه — reservations BEGIN IMMEDIATE + snapshot rule — Mirror 4 خدمت فعال با Quality AI+Detection+Analysis+Generation+Validation — service_key mapping در SERVICE_CATALOG — final_design_id/service_key/selected_style در reservations — enrich scoring 45 has_service+20 city+15 featured — همه از کد واقعی این نشست — Edge: empty states (no service, no image, no center) handled with fallback messages — Persian/RTL handled — duplicate prevention via UNIQUE(center_id,user_id) conversations + UNIQUE(conversation_id,user_id) feedback + transaction_key UNIQUE promotions + dedupe_key in service_demand.

**Security:** PASS — AuthN/AuthZ: login_required + owner_user_id == _user_id() + _is_staff() check giso_admins — CSRF on every POST via csrf_token() hidden input — Input validation at boundary: _normalize_fields, _clean_service, _clean_working_day, _coerce_int, _coerce_flag, _coerce_time, save_center_image MAX_BYTES/PIXELS/SIDE + format check — Upload path constraints: static_root check + candidate.parents check + X-Content-Type-Options nosniff + conditional send_file — No secret in logs/errors/UI: business_phone normalized, display_phone via display_phone(), phone reveal via POST intent — Data exposure: center_detail only published or owner/staff, gallery_media check status/is_active or owner/staff, center_media same.

**Regression:** PASS with WARNING — Sibling features sharing code: marketplace, hair_sale, analyses, chats, orders, wallet, profile, reviews, overview in panel_user — shared DB tables: beauty_centers, beauty_center_services, working_hours, images, conversations, messages, feedback, reservations, promotions, discounts, events, buti_ai_sessions, final_designs — Notification events: new_reservation, user_confirmed/rejected — Existing tests: `giso/tests/test_beauty_centers_*.py` 16 files (grep) — `test_buti_ai_new_services.py`, `test_buti_ai_phase1.py`, `test_broadcasts_center.py` — اگر 2 ستون additive اضافه شود، migration باید idempotent باشد (PRAGMA check) مثل ai_credits fix — WARNING: اگر beauty_center_images service_key اضافه شود، existing queries SELECT * still work (new column DEFAULT ''), ولی template filter باید fallback به عمومی داشته باشد.

## ۱۵. Plan + Scope Lock — Approval Gate

### ۱۵.۱ Request interpretation
- Restated goal: طراحی سناریوی Beauty Center / پنل سالن و آگهی خدمات سالن روی ساختار فعلی Giso — Read-Only — خروجی rp6.md
- Assumptions: فارسی RTL کافی، شهر پیش‌فرض مشهد، فیلتر service موجود، Mirror 4 خدمت فعال، format_toman موجود، BEGIN IMMEDIATE امن
- Clarification: none — Read-Only per law

### ۱۵.۲ Freshness
- HEAD=f9a7fb0 branch=arena/01a0eecf-giso4 working-tree=dirty(rp5.md+rp6.md) بعد نوشتن
- Graph: STALE (built at c9b198cd)
- Docs: STALE (last 2026-09-29 branch mismatch)
- Memory: absent

### ۱۵.۳ Current state & real problem location
- Where problem lives: beauty_centers module کامل برای MVP — Gap اصلی Portfolio per service (beauty_center_images بدون service_key) + Featured Service per service (is_featured فقط center) + User Panel Mirror History (buti_ai_final_designs موجود ولی نمایش ندارد) — همه Gapها Medium نه Critical
- Divergences found: Docs (PROJECT_GUIDE, GISO_GUIDE) می‌گویند Graph fresh ولی Graph STALE است — Code wins: Graph built at c9b198cd vs HEAD f9a7fb0 — Docs branch name arena/01a0e0b8 vs current 01a0eecf — Code Truth: live code has 20 SERVICES keys including brow/nail/lip_shading/hair_color, reservations with final_design_id/service_key/selected_style, buti_ai_final_designs with provider/model/prompt_json — Docs may lag

### ۱۵.۴ Architecture & current pattern
- Convention table بالا — DB via get_giso_db_conn, Auth via login_required + owner check, CSRF via csrf_token, Notification via ThreadPoolExecutor + broadcasts_center, Bot via state machine, Template via base.html + bc-* classes, AI via ai_runtime + provider chain, Migration additive via PRAGMA + ALTER TABLE, Pricing 6 functions, Reservations BEGIN IMMEDIATE snapshot, Listing via list_public_centers filters
- Current architecture summary: beauty_centers modular with 10 files + pricing + reservations + panel_admin + bot_handlers, shared DB giso.db WAL, additive migrations, ThreadPoolExecutor notifications, CSRF protected, owner vs staff guards, service filtering via SERVICES + beauty_center_services, reservation snapshot + BEGIN IMMEDIATE, Mirror integration via final_design_id/service_key/selected_style + enrich scoring 45+20+15+feedback

### ۱۵.۵ Dependencies & impact
- Internal imports: base.get_giso_db_conn, config.Config, beauty_centers.services, pricing.services, reservations.services, reservations.notifications, buti_ai.service_catalog, generic_service, service_image_generation, schema, ai_models, money.format_toman, panel_user.routes, bot handlers — all reuse
- Shared DB: beauty_centers, services, working_hours, images, conversations, messages, feedback, reservations, promotions, discounts, events, expiry_notices, reports, buti_ai_sessions, final_designs, service_demand, waitlist, giso_web_auth, giso_config, giso_admins — caution: additive columns only
- Notification: new_reservation, user_confirmed/rejected — reuse
- AI runtime: ai_runtime, ai_credits, ai_models_registry, buti_ai/ai_models — reuse
- Sibling features: marketplace, hair_sale, analyses, chats, orders, wallet, profile, reviews, overview, eyebrow/nail/hair_color/lip — no breaking change

### ۱۵.۶ Proposed solution — Minimal path
- **برای این گزارش (rp6.md):** فقط بررسی و طراحی — هیچ کد تغییر نکرده — P0 بدون تغییر DB قابل پیاده‌سازی است — توصیه: اول verification P0 (Mirror 4 خدمت, filtering, detail, reservation, owner dashboard, promotion, consultant) — بعد P1 با 2 ستون additive (service_key در beauty_center_services + beauty_center_images + service_id در promotions/discounts + is_featured_service) via ALTER TABLE ADD COLUMN — بعد User Panel Mirror History new module reuse analyses.py — بعد Bale Mirror flow reuse generic_service — Order Reuse>Extend>New
- **Explicitly NOT doing:** refactor bot.py, تغییر bot_edu/web/main.py, DROP/RECREATE table, new abstraction/base class, تغییر Graphify/project_memory/data/.env, تغییر قیمت یا منطق رزرو, تغییر AI provider logic

### ۱۵.۷ Scope Lock

- **ALLOWED files (این گزارش فقط):** [rp6.md] — هیچ کد دیگری تغییر نکرده per law Read-Only
- **اگر تایید شود برای فاز پیاده‌سازی آینده (پیشنهادی، هنوز اجرا نشده):**
  - ALLOWED (12 فایل): `giso/beauty_centers/schema.py` (add service_key to images additive + index), `giso/beauty_centers/pricing/schema.py` (add service_key + is_featured_service to services additive), `giso/beauty_centers/services.py` (save_center_image + promotion per service), `giso/beauty_centers/pricing/services.py` (_clean_service accept service_key + is_featured_service), `giso/beauty_centers/routes.py` (display filter + gallery filter + owner_gallery_upload with service_key), `giso/beauty_centers/templates/beauty_centers/owner_dashboard.html` (service_key dropdown + gallery service_key dropdown + featured toggle), `giso/beauty_centers/templates/beauty_centers/detail.html` (service card لوکس with portfolio per service + discount badge + CTA), `giso/panel_user/modules/mirror.py` NEW reuse analyses.py pattern (mirror history from buti_ai_final_designs), `giso/panel_user/routes.py` (register mirror module), `giso/buti_ai/templates/buti_ai/generic_final_design.html` (CTA to service_id), `giso/buti_ai/routes.py` (enrich with service_id mapping + _enrich_generic_centers keep scoring)
  - FORBIDDEN: everything else — especially `bot_edu/`, `web/`, `main.py`, `giso/bot.py` refactor, `graphify-out/`, `project_memory/`, `data/`, `.env`, `giso/buti_ai/eyebrow/` for new services (must use generic_service)
  - Shared/caution files inside future scope: schema.py (shared tables beauty_centers/services/images/reservations), services.py (shared listing), panel_user/routes.py (shared auth), buti_ai/routes.py (shared AI runtime)
  - Data: tables involved beauty_centers, beauty_center_services, beauty_center_images, beauty_center_promotions, beauty_center_discounts, buti_ai_final_designs, beauty_center_reservations — migration needed? P0 no, P1 yes additive via ALTER TABLE ADD COLUMN with PRAGMA check + CREATE INDEX IF NOT EXISTS (same pattern as ai_credits fix + pricing/schema.py)
  - Out of scope: sibling services marketplace/hair_sale, bot_edu, web/, graphify-out, project_memory, data, .env

### ۱۵.۸ Council findings
- Architect: PASS (domain folder correct, no forbidden coupling, additive only, no new abstraction)
- Domain: PASS (behavior matches real code: SERVICES 20, STATUS 6, pricing, working_hours, reservations BEGIN IMMEDIATE snapshot, Mirror 4 active with Quality+Detection+Analysis+Generation+Validation+Final+Consultant+Interest+Enrich, service_key mapping, final_design_id in reservations — edge cases handled)
- Security: PASS (login_required + owner check + _is_staff, CSRF, validation, upload path constraints, static_root check, nosniff, no secret in logs)
- Regression: PASS with WARNING (16 test files beauty_centers + buti_ai new_services + phase1 + broadcasts_center share tables — additive columns safe with DEFAULT '' — but template filter needs fallback to general gallery)

### ۱۵.۹ Risks
- اگر service_key به beauty_center_images اضافه شود و existing images بدون service_key باشند، filter باید fallback به عمومی داشته باشد — mitigation: WHERE service_key='' OR service_key=? + UI "همه" option
- اگر Featured Service اضافه شود و مرکز 10 خدمت Featured کند، لیست شلوغ می‌شود — mitigation: limit 3 featured per center + sort_order
- اگر User Panel Mirror History اضافه شود و user_id null باشد (guest sessions), query باید user_id IS NOT NULL — mitigation: filter user_id = current_user.id
- اگر Bale Mirror flow اضافه شود و provider quota تمام شود, fallback guided composite باید صادقانه اعلام شود — mitigation: existing validation + is_ai_generated flag

### ۱۵.۱۰ Tests to run (اگر تایید شود برای فاز پیاده‌سازی)
- `SECRET_KEY=test python -m pytest giso/tests/test_beauty_centers_*.py -q` — 16 files
- `python -m pytest giso/tests/test_buti_ai_new_services.py -q` — generic_service 4 services
- `python -m pytest giso/tests/test_buti_ai_phase1.py -q` — eyebrow baseline
- `python -m pytest giso/tests/test_broadcasts_center.py -q` — notifications
- `python -c "import giso.wsgi"` — import/boot check
- دستی: list_centers?service=nail filter, center_detail services+price+hours, Mirror upload→final with validation, reserve with final_design_id/service_key/selected_style, owner_dashboard tabs, promotion, consultant chat

### ۱۵.۱۱ Regression plan
- Run sibling tests: marketplace, hair_sale, analyses, chats — `grep -R "beauty_centers\|beauty_center_services\|beauty_center_reservations\|buti_ai_final_designs" giso/tests/`
- Shared symbol tests: get_giso_db_conn, ai_runtime, ai_credits — `Select-String` in giso/tests/
- Manual: verify existing centers still list, existing reservations still work, existing gallery still shows, existing chat still works, existing Mirror still generates

### ۱۵.۱۲ Found but not changed
- `beauty_center_images` بدون service_key — Gap Medium — P1 پیشنهادی
- `beauty_center_services` بدون service_key + is_featured_service — Gap Medium — P1 پیشنهادی
- `beauty_center_promotions` + `discounts` بدون service_id — Gap Low — P1 پیشنهادی
- User Panel Mirror History ندارد — Gap Medium — P1 new module reuse analyses.py
- Bale Mirror flow ندارد — Gap Medium — P1 reuse generic_service
- Graph STALE (built at c9b198cd vs HEAD f9a7fb0) — should run `graphify update .` after code changes — suggestion only, not executed
- Docs STALE (branch name mismatch arena/01a0e0b8 vs 01a0eecf) — should update PROJECT_GUIDE.md branch name — suggestion only

---

## APPROVAL NEEDED: تأیید می‌کنی؟

**این گزارش Read-Only است — هیچ کد تغییر نکرده — فقط rp6.md ایجاد شده.**

**اگر تایید کنی "تایید/بریم/اجرا کن":**
- وارد فاز پیاده‌سازی P0 (بدون تغییر DB) + P1 (2 ستون additive) می‌شویم
- Scope Lock آینده بالا اعمال می‌شود
- Tests + Diff Review + Regression + Final Report اجرا می‌شود

**اگر تایید نکنی:** همین گزارش نهایی است و در گیت‌هاب ذخیره می‌شود.

---

## ۱۶. خروجی نهایی 11 بخش — خلاصه اجرایی

### ۱. وضعیت فعلی
چه چیزهایی همین الان داریم؟ — beauty_centers 20+ fields + 10 جدول مرتبط + SERVICES 20 keys شامل brow/nail/lip_shading/hair_color + STATUS 6 + pricing/services with price_min/max/duration/is_active + working_hours per day + reservations with final_design_id/service_key/selected_style BEGIN IMMEDIATE snapshot + conversations/messages/feedback/promotions/discounts/events/reports + Mirror 4 services PASS with Quality AI+Detection+Analysis AI+Generation with mask gate+Validation+Final+Consultant+Interest+Centers enrich score+tags+match reason + panel_user modules + bot_handlers

### ۲. نقاط قوت
چه چیزهایی خوب و قابل استفاده هستند؟ — ماژولار (هر پوشه خودش), Additive migrations via PRAGMA+ALTER TABLE, Shared get_giso_db_conn WAL, SERVICES dict + CATEGORY_SERVICES, STATUS_FA 6, Pricing 6 functions, Reservations BEGIN IMMEDIATE + snapshot rule, Mask gate+Validation ضد فریب, Fallback صادقانه, Shared services وب و ربات یک DB, Promotion/Expiry throttled, Feedback score100, Enrich scoring 45 has_service+20 city+15 featured+feedback, Consultant context, Interest Lead vs View, CSRF+owner check+static_root check

### ۳. Gapها
دقیقاً چه چیزهایی کم داریم؟ — Portfolio per service (beauty_center_images بدون service_key) Medium, Featured Service per service (is_featured فقط center) Medium, User Panel Mirror History (buti_ai_final_designs موجود ولی نمایش ندارد) Medium, Bale Mirror flow (generic_service موجود ولی bot handler ندارد) Medium, Discount/Promotion per service (فقط center_id) Low, Service Key در beauty_center_services (بدون ستون) Medium

### ۴. پیشنهاد سناریوی نهایی
User → Mirror → Service → Beauty Center → Service Offer → Reservation — Flow لوکس پیشنهادی: Mirror (4 کارت) → Style (5 مدل) → Upload (preview+guide+sample) → Quality AI + Detection + Analysis AI → Generation (Before/After + validation صادقانه) → نتیجه (final_label+do/avoid+interest Lead vs View + centers enrich score+tags+match reason + consultant) → سالن‌های همین خدمت (list_centers?service= + _enrich_generic_centers) → کارت خدمت سالن (نمونه‌کار همان خدمت+قیمت+پیشنهاد+CTA) → مشاهده سالن (gallery فیلتر شده) → رزرو (reserve with final_design_id/service_key/selected_style + BEGIN IMMEDIATE + snapshot + notify) → Lead — با معماری فعلی 100% قابل پیاده‌سازی در P0 (فقط نمونه‌کار عمومی)، با 2 ستون additive در P1 لوکس‌تر

### ۵. سناریوی پنل سالن
دقیقاً چه منوهایی لازم است؟ — P0: نمای کلی (status, views, contact_clicks, analysis_impressions, price_inquiry_clicks, listing_expires, promotion_active, feedback, reservations), اطلاعات پایه (name, category, type, city, region, address, phone, contact_time, description, price_level, starting_price, services_json), خدمات (get_center_services + add/update/delete with name/category/description/duration/price_min/max/is_active/sort_order), ساعات کاری (per day open/close/is_closed/slot), تصاویر (max 3 + gallery upload/delete + main delete with replacement), رزروها (owner_list + confirm/reject/complete + calendar/slots + notify), پیام‌ها (conversations+messages+close), آمار (views, clicks, impressions, events), وضعیت انتشار (renew, promote, discount) — P1: تخفیف‌ها (per service), تبلیغات (per service), نمونه‌کار per service (service_key dropdown), Featured Service toggle

### ۶. سناریوی آگهی خدمات
آیا «آگهی بر اساس خدمت» مدل مناسبی است؟ چرا؟ — بله — از 3 دید: کاربر مستقیم خدمت با نمونه‌کار+قیمت می‌بیند سریع‌تر تصمیم می‌گیرد (UX لوکس) اگر محدود به 3 خدمت برجسته باشد سردرگمی ندارد؛ صاحب سالن می‌تواند خدمات فعال/غیرفعال/Featured/تخفیف جدا مدیریت و روی پول‌ساز تمرکز؛ Giso هر خدمت inventory برای Featured/Promotion/تخفیف/تبلیغ هدفمند بر اساس service_key/Mirror suggestion/reservation (درآمد بهتر از آگهی کلی) — توصیه: P0 آگهی مرکز با خدمات کارت لوکس در detail، P1 آگهی ← خدمت با Featured Service per service

### ۷. سناریوی درآمدی
چه چیزهایی قابلیت پولی شدن دارند؟ — P0 موجود: Promotion مرکز (package_key + amount + transaction_key), Featured Center (is_featured+sort_order), پیشنهاد بر اساس Mirror/service_key (enrich scoring + می‌تواند Boost پولی شود), رزرو با final_design_id (قابل کمیسیون) — P1 پیشنهادی ارزشمند: Featured Service per service (مرکز برای خدمت "رنگ مو" پول بدهد), Promotion per service (package_key+service_id), Discount per service (جذب کاربر), Portfolio per service (ارزش نمایشی), جایگاه ویژه per service (sort_order) — P2 فعلاً اضافه: تبلیغ هدفمند پیچیده با AI, علاقه‌مندی‌ها, Instagram/Logo

### ۸. جدول Reuse
چه چیزهایی از ساختار موجود استفاده می‌شوند؟ — 80% Reuse مستقیم (beauty_centers table, register, status, contact/address, images عمومی, services, price, working_hours, active/featured, feedback, reservation with final_design_id/service_key/selected_style, message, promotion, panels, Mirror result, service_key mapping, selected_style, enrich scoring, consultant, interest), 20% Extend با 2-4 ستون additive (service_key در beauty_center_services + beauty_center_images, service_id در promotions/discounts, is_featured_service), 0% New Architecture (فقط 1 فایل جدید panel_user mirror history reuse analyses.py pattern)

### ۹. DB Impact
آیا DB نیاز به تغییر دارد؟ — P0 ضروری هیچ تغییر لازم نیست — 100% با ساختار فعلی قابل انجام است — P1 مهم 2 ستون additive پیشنهادی: service_key TEXT DEFAULT '' در beauty_center_services + beauty_center_images + optional service_id INTEGER DEFAULT 0 در promotions/discounts + is_featured_service INTEGER DEFAULT 0 — migration additive via ALTER TABLE ADD COLUMN with PRAGMA check + CREATE INDEX IF NOT EXISTS مثل ai_credits fix + pricing/schema.py pattern — هیچ DROP/RECREATE

### ۱۰. فایل‌ها و ماژول‌های درگیر
مسیر دقیق فایل‌ها را بده — موجود: beauty_centers/schema.py, services.py, routes.py, pricing/schema.py, pricing/services.py, reservations/schema.py, services.py, routes.py, notifications.py, panel_admin.py, bot_handlers.py, templates/beauty_centers/list.html, detail.html, _card.html, owner_dashboard.html, register.html, chat.html, reserve.html, my_reservations.html, admin.html, static/beauty_centers.css/js, buti_ai/schema.py, service_catalog.py, generic_service.py, service_image_generation.py, image_validation.py, routes.py, consultant.py, ai_models.py, eyebrow/nail/hair_color/lip/final_design.py, panel_user/routes.py, modules/_base.py/analyses.py/etc, base.py, config.py, money.py, app.py — آینده اگر تایید شود: 12 فایل ALLOWED بالا + FORBIDDEN bot_edu/web/main.py/graphify-out/project_memory/data/.env

### ۱۱. Plan + Scope Lock
در پایان دقیقاً مشخص کن اگر قرار باشد این سناریو پیاده‌سازی شود: چه فایل‌هایی باید تغییر کنند (12 فایل پیشنهادی بالا), چه فایل‌هایی نباید تغییر کنند (bot_edu, web, main.py, bot.py refactor, graphify-out, project_memory, data, .env, eyebrow for new services), چه تست‌هایی باید انجام شوند (16 beauty_centers tests + buti_ai new_services + phase1 + broadcasts_center + import wsgi + دستی filter service=nail, center_detail, Mirror upload→final, reserve with final_design_id, owner_dashboard), ترتیب اجرای کار چیست (Reuse>Extend>New: اول verification P0 بدون تغییر DB, بعد DB Extend 2 columns additive, بعد User Panel Mirror History + Portfolio per service + Featured Service + Bale Mirror flow)

---

## قانون نهایی رعایت شد

فعلاً هیچ کدی تغییر نکرده — فقط rp6.md — بعد از Plan+Scope Lock متوقف می‌شویم و منتظر تایید "تایید/بریم/اجرا کن" می‌مانیم — Code is Truth: اگر Documentation و Code اختلاف داشتند، Code حقیقت اصلی است — اولویت مطلق Reuse>Extend>New — اگر با ساختار فعلی قابل انجام است تغییر DB پیشنهاد نشده (P0 بدون تغییر).

---

## Appendix — Evidence از کد واقعی این نشست

- beauty_centers table: schema.py:10-55 with 20+ fields + 10 related tables
- SERVICES 20 keys: services.py includes brow/nail/lip_shading/hair_color + CATEGORY_SERVICES
- beauty_center_services: pricing/schema.py SERVICES_COLUMNS with price_min/max/duration/is_active/sort_order + get_center_services ordered is_active DESC
- working_hours: day_of_week 0=شنبه + save_working_hours BEGIN IMMEDIATE upsert
- reservations: schema.py RESERVATIONS_COLUMNS with final_design_id, service_key, selected_style + create_reservation BEGIN IMMEDIATE + snapshot rule + _is_available + _build_slots
- list_centers: routes.py with filters q/city/category/type/service/price_level + featured 6 + related + beauty_stats + noindex if query
- center_detail: routes.py + detail.html with services+price+hours+feedback+gallery+contact+chat + increment_view + reveal_contact
- owner_dashboard: routes.py + owner_dashboard.html with 8 tabs P0 + 3 P1
- Mirror: buti_ai/service_catalog.py 4 active + generic_service.py process_service_submission + build_final_candidate + generate_final_design + routes.py mirror_home + generic_service_wizard + upload + final + _enrich_generic_centers scoring 45+20+15+feedback
- Final Design: buti_ai/schema.py buti_ai_final_designs with session_id/user_id/service_type/original/final/selected_style/provider/model/status/prompt_json + save_final_design
- Service Key mapping: SERVICE_CATALOG beauty_center_service brow/nail/hair_color/lip_shading
- Consultant: build_consultant_context + consultant_invite_text + interest Lead vs View + demand/waitlist
- Security: login_required + owner_user_id check + _is_staff + csrf_token + static_root check + nosniff + normalize_phone
- Migration pattern: PRAGMA table_info + ALTER TABLE ADD COLUMN + CREATE INDEX IF NOT EXISTS — additive only — same as ai_credits fix

---

**END OF rp6.md — STOP منتظر تایید**
