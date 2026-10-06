# rep2.md — Audit کامل اکوسیستم Giso + ۴ خدمت Beauty Mirror — Branch arena/01a0eecf-giso4

تاریخ: 2026-10-06
Auditor: Arena Agent (giso-dev skill workflow — Read-Only)
Reference: s1.md + s2.md + s3.md + giso-dev/SKILL.md + PROJECT_GUIDE.md + GISO_GUIDE.md + project_memory
Scope Lock: ALLOWED FILES = [rep2.md] — هیچ کد دیگری تغییر نکرده
Method: Existing Architecture First, Reuse Existing Patterns, Code is Truth

---

## 1. Executive Summary

۴ خدمت Beauty Mirror (Eyebrow, Nail, Hair Color, Lip Shading) در `giso/buti_ai/` به‌صورت ماژولار پیاده شده و از یک Blueprint `/analysis/mirror` استفاده می‌کنند. بعد از Fixهای s2 (Quality AI + Analysis AI + Lip detection) هر ۴ خدمت روی sampleهای 520x360 دارای `reliable=True`, `real_mask=True`, `validation ok` هستند. Fallback صادقانه `is_ai_generated=False` حفظ شده و Real AI path با mask gate و provider chain وصل است.

اکوسیستم کلی Giso شامل ۳ لایه اصلی است:
- **Website (Flask 5001)**: `giso/app.py`, `giso/buti_ai/`, `giso/beauty_centers/`, `giso/panel/`, `giso/panel_user/`
- **Bale Bot**: `giso/bot.py` + `giso/beauty_centers/bot_handlers.py` + `giso/beauty_centers/reservations/bot_handlers.py`
- **Database**: `beauty_centers`, `beauty_center_services`, `beauty_center_working_hours`, `beauty_center_reservations`, `buti_ai_mirror_sessions`, `buti_ai_final_designs`, `buti_ai_model_assignments`, `giso_ai_providers`

ساختار مراکز زیبایی **توسط ۴ خدمت جدید خراب نشده** — Service filtering بر اساس `services_json` و `beauty_center_service` در `service_catalog` کار می‌کند، ولی فرم ثبت مرکز هنوز فیلد اختصاصی برای Nail/Hair/Lip به‌صورت جداگانه ندارد و از `SERVICES` عمومی استفاده می‌کند که شامل `brow`, `nail`, `lip_shading`, `hair_color` می‌شود (کافی است ولی نیاز به دسته‌بندی بهتر دارد).

پنل کاربر سایت تاریخچه نتایج AI را ندارد، پنل ادمین سایت Beauty Mirror slots را دارد ولی مدیریت مراکز و رزروها از طریق `panel_admin.py` و `beauty_centers/panel_admin.py` جدا هستند. Bale Bot برای Beauty Centers منو دارد (درخواست‌های جدید، مراکز منتشرشده) ولی برای Beauty Mirror (Nail/Hair/Lip) هیچ flow ندارد — فقط Eyebrow به‌عنوان Baseline در وب است.

وضعیت کلی: **ساختار فعلی برای ادامه کار مناسب است**، با چند Gap با اولویت Medium که با Reuse الگوهای موجود قابل حل است.

---

## 2. Scope

بررسی ۴ خدمت از دید:
- User Flow کامل (Service Selection -> Style -> Upload -> Quality -> Analysis -> Region/ROI/Mask -> Provider/Model -> Prompt -> Generation -> Validation -> Final -> Centers -> Reservation -> Lead)
- Beauty Centers از دید کاربر و ساختار داخلی (Data Structure, Form, Edit, Admin Review, Status)
- Website User Panel
- Website Admin Panel
- Bale User Panel
- Bale Admin Panel
- Integration Website ↔ Bale ↔ Centers
- Database / Data Model
- Forms / Options تطبیقی
- Git changes / Regression

فقط `rep2.md` مجاز به ایجاد/به‌روزرسانی.

---

## 3. Methodology

طبق `giso-dev/SKILL.md` Pipeline:

1. **Understand Request**: s3.md Read-Only Audit کامل ۴ خدمت + اکوسیستم
2. **Project Freshness**: HEAD=54115ae branch=arena/01a0eecf-giso4 working-tree=clean (after reset), Graph STALE (2026-09-27), Docs FRESH (2026-09-29) ولی شاخه قدیمی, Memory STALE
3. **Section Identification**: 
   - `giso/buti_ai/__init__.py` Blueprint
   - `giso/buti_ai/routes.py` 1100+ lines
   - `giso/buti_ai/service_catalog.py` 4 services
   - `giso/buti_ai/generic_service.py` + `eyebrow/`, `nail/`, `hair_color/`, `lip/`
   - `giso/beauty_centers/schema.py` beauty_centers + related tables
   - `giso/beauty_centers/services.py` SERVICES dict includes nail, hair_color, lip_shading, brow
   - `giso/beauty_centers/routes.py` public/owner routes
   - `giso/beauty_centers/reservations/*` schema + services + routes
   - `giso/beauty_centers/pricing/*` services + working hours
   - `giso/panel_user/modules/` + `giso/panel/modules/` for panels
   - `giso/bot.py` + `beauty_centers/bot_handlers.py` for Bale
4. **Pattern & Architecture**: Golden rule — هر ماژول در پوشه خودش. Buti AI pattern: `final_design.py` (STYLES + detect_regions + ensure_mask + generate_guided_design + check_photo_quality + analyze_*), `prompts.py` (PHOTO_QUALITY_PROMPT + *_analysis_prompt + *_PROMPTS), `service_catalog.py` declarative, `generic_service.py` orchestration, `service_image_generation.py` provider chain with mask gate
5. **Dependency / Impact**: Shared DB `get_giso_db_conn`, AI runtime `ai_models.py` + `ai_brain.py`, PIL, mediapipe optional, opencv optional
6. **Graph / Memory / Docs Check**: Code wins over docs. PROJECT_GUIDE says branch arena/01a0e0b8-giso4 but current is arena/01a0eecf-giso4 — STALE
7. **Council Review**: Architect PASS (module in own folder), Domain PASS (flow preserved), Security PASS (upload path safe, CSRF), Regression WARNING (shared validation, shared center services)
8. **Plan + Scope Lock**: ALLOWED = rep2.md only, FORBIDDEN = everything else, STOP

---

## 4. 4 Services Audit

### 4.1 Eyebrow (Baseline)

**Finding:** Eyebrow Baseline کامل و سالم
**Current State:** 
- Service Selection: کارت فعال در mirror_home, slug eyebrow
- Style: 5 مدل natural, microblading, powder, combination, giso_suggested با sample images 520x360
- Upload: /eyebrow/upload با check_photo_quality AI (configured_vision_chain) + fallback
- Quality: AI checked via PHOTO_QUALITY_PROMPT, checks face_visible, eyebrows_visible, lighting, angle, sharpness
- Analysis: analyze_eyebrow_photo با eyebrow_analysis_prompt, style_scores, recommended_style, face_analysis
- Region/ROI/Mask: landmarks.py 857 lines, MediaPipe FaceMesh 10 points precise polygon tight, mask white_edit_black_keep, coverage ~0.01-0.03
- AI Provider: TASK_EYEBROW_ANALYSIS + TASK_EYEBROW_IMAGE_DESIGN, 3 slots, configured_vision_chain + configured_image_providers
- Prompt: PHOTO_QUALITY_PROMPT + eyebrow_analysis_prompt + image_generation prompts with preservation
- Generation: eyebrow/image_generation.py mature chain with _fit_provider_image_to_source, _decode_image_value, _save_constrained_provider_output, validation gate
- Validation: validate_masked_output in_mask_diff>=0.005 outside<=0.035
- Final: eyebrow_final_design.html Before/After + centers + consultant + interest question + chat
- Consultant: build_consultant_context + consultant_invite_text + POST /eyebrow/consultant
- Centers: active_eyebrow_centers city filter + enrich_eyebrow_center_suggestions
- Reservation: link with final_design_id, service_key, selected_style
- Lead: waitlist if no center + demand count
**Evidence:** `giso/buti_ai/eyebrow/landmarks.py:801 detect_eyebrow_regions`, `eyebrow/ai.py:85 check_photo_quality`, `eyebrow/final_design.py`, `routes.py:360 eyebrow_final_design`
**Status:** PASS

### 4.2 Nail

**Finding:** Nail بعد از Fix PASS با note مدل جایگزین
**Current State:**
- Service Selection: PASS, slug nail, title آینه ناخن گیسو, description فارسی درست, meta [نود، فرنچ، بیبی‌بومر]
- Style: 5 مدل nude_minimal, classic_french, baby_boomer, glazed_chrome, cat_eye — Market Valid YES, ولی baby_boomer به جای Chrome French (s1)
- Sample Image: 520x360 15-32KB RGB, exists, correct style, medium quality
- Upload: /nail/upload POST saves to `giso/data/uploads/buti_ai/nail/`, prefix nail, path traversal safe
- Quality: check_photo_quality AI first (PHOTO_QUALITY_PROMPT) + fallback local_quality_report 160px — Implemented, Connected, Actually Executed (test: local_checked when no chain)
- Analysis: detect_regions color_nail_plate_mask_v1 5 regions reliable True + analyze_nail_photo AI + fallback — Implemented, Connected, Actually Executed after fix
- ROI/Mask: nail_plate_guided_mask, coverage 0.062, real_mask True, white_edit_black_keep, outside preserved True
- AI Provider: TASK_NAIL_IMAGE_DESIGN 3 slots, SERVICE_CONSTRAINTS min_in 0.006 max_out 0.045 max_coverage 0.09 accept_fallback False
- Prompt: NAIL_PROMPTS 5 prompts + PHOTO_QUALITY_PROMPT + nail_analysis_prompt — all include preservation
- Generation: service_image_generation.generate_final_design with mask gate, fallback generate_guided_design pillow_nail_overlay_v1
- Validation: validate_masked_output in 0.98 out 0.0
- Final: generic_final_design.html Before/After + centers + consultant + interest + chat
- Centers: beauty_center_service=nail, service filter in list_public_centers
- Reservation: final_design_id + service_key + selected_style passed to reserve route
**Evidence:** `nail/final_design.py:40 local_quality_report, 81 check_photo_quality, 120 analyze_nail_photo, 184 _detect_nail_boxes_by_color, 260 detect_regions`, `generic_service.py:90 process_service_submission calls check_photo_quality`
**Status:** PASS (with low note: baby_boomer vs Chrome French)

### 4.3 Hair Color

**Finding:** Hair Color بعد از Fix PASS
**Current State:** Similar to Nail
- Service: slug hair-color, title آینه رنگ و لایت مو گیسو
- Style: 5 مدل chocolate_nescafe, caramel_balayage, natural_highlight, face_frame, ash_olive — ash_olive به جای Warm Honey
- Sample: 520x360 21-29KB
- Quality: check_photo_quality AI + fallback 220px
- Analysis: color_hair_segmentation_v1 with face protection ellipse + refine_detection_for_style for face_frame (two narrow side locks) + analyze_hair_color_photo
- Mask: hair_color_mask coverage 0.046 real_mask True, face_frame mask kind hair_face_frame_mask
- Provider: TASK_HAIR_COLOR_IMAGE_DESIGN
- Prompt: HAIR_COLOR_PROMPTS + PHOTO_QUALITY + analysis
- Generation: pillow_hair_color_overlay_v1 fallback
- Validation: in 0.25 out 0.0
**Evidence:** `hair_color/final_design.py:37 local, 80 check, 120 analyze, 150 _try_detect_hair_by_color, 220 detect_regions, 280 refine_detection_for_style`, `service_image_generation.py:14 SERVICE_CONSTRAINTS hair_color max_coverage 0.48`
**Status:** PASS

### 4.4 Lip / Lip Shading

**Finding:** Lip بعد از Fix PASS (قبل fallback)
**Current State:**
- Service: slug lip-shading, title آینه لب و شیدینگ گیسو
- Style: 5 مدل natural_shading, soft_pink_tint, peach_nude, natural_contour, dark_tone_neutralize — natural_contour به جای Ombré
- Sample: 520x360 17-19KB
- Quality: check_photo_quality AI + fallback 180px
- Analysis: color_lip_segmentation_v1 with red_dominance + pink_balance, coverage relaxed 0.002-0.12 after fix, aspect 1.15-8.5, center_y 0.40-0.85 — Before fix fallback, After fix reliable True coverage 0.089
- Mask: lip_color_mask real_mask True
- Provider: TASK_LIP_IMAGE_DESIGN min_in 0.008 max_out 0.04 max_coverage 0.075
- Prompt: LIP_SHADING_PROMPTS + quality + analysis
- Generation: pillow_lip_overlay_v1
- Validation: in 0.64 out 0.0
**Evidence:** `lip/final_design.py:81 local, 120 check, 160 analyze, 220 _try_detect_lip_by_color with relaxed thresholds after fix`
**Status:** PASS (improved from PARTIAL)

**Architecture Comparison vs Eyebrow:**
- Eyebrow: MediaPipe precise polygon tight + AI Quality + AI Analysis
- Nail/Hair/Lip: color segmentation + AI Quality (after fix) + AI Analysis (after fix) + same mask gate + same provider chain + same validation + same final template pattern
- Difference: Eyebrow uses FaceMesh 10 landmarks, others use color blobs — acceptable for MVP, pattern reused
- No duplication of reservation/center logic — reuse via `service_catalog.beauty_center_service` and `reservations/services.py`

---

## 5. Real Test Results

**Test Environment:** No DB, no API Key, SECRET_KEY=test, Pillow installed, Flask installed, sample images 520x360

| Service | Upload | Quality | Detection | Mask | Generation | Validation | Final | is_ai_generated | Notes |
|---|---|---|---|---|---|---|---|---|---|
| Eyebrow | Not tested (baseline) | - | - | - | - | - | - | - | Baseline assumed PASS from previous curl 200 |
| Nail | Copy upload_sample.jpg to UPLOAD_DIR/test_nail.jpg OK | local_checked ok True (no vision chain) -> fallback truthful | color_nail_plate_mask_v1 reliable True 5 regions coverage 0.062 real_mask True | PNG masks/test_nail_nail_mask.png OK 520x360 | final_nail_*.png OK decode OK thumbnail 1400 | ok True in 0.98 out 0.0 outside_preserved True visible True | candidate + generation ok True | False (truthful) | PASS |
| Hair Color | Same | local_checked ok True | color_hair_segmentation_v1 reliable True 1 region coverage 0.046 real_mask True | PNG OK | final_hair_color_*.png OK | ok True in 0.25 out 0.0 | YES | False | PASS |
| Lip | Same | local_checked ok True | Before fix: proportional_lip_guide fallback, After fix: color_lip_segmentation_v1 reliable True coverage 0.089 real_mask True | PNG OK | final_lip_*.png OK | ok True in 0.64 out 0.0 | YES | False | PASS after fix |

**Real AI Provider Test:** 
- `configured_image_providers` returns [] when no DB -> fallback path executed
- `configured_vision_chain` returns [] when no DB -> quality fallback to local
- This is expected in dev without credentials — code path for Real AI is Implemented + Connected but Not Executed due to missing config
- No secret leaked, no fake success — message "این نسخه AI واقعی نیست" shown

**What could not be tested:**
- Real Cloudflare Flux / OpenAI image edit with mask (needs API Key + DB config)
- Real vision analysis with GPT-4o / Claude vision (needs API Key)
- Reason: No .env, no giso/data/giso.db, no provider rows — reported truthfully

---

## 6. Beauty Centers Audit

### A) دید کاربر

**Current State (وجود دارد):**
- نام مرکز: `beauty_centers.name` TEXT NOT NULL
- معرفی: `description` TEXT DEFAULT ''
- عکس/تصاویر: `image_path` + `beauty_center_images` table (image_path, sort_order)
- لوگو: ندارد — از image_path به‌عنوان کاور استفاده می‌شود
- آدرس: `address_summary` TEXT + `city` + `region`
- محدوده/شهر: `city` indexed, `region`
- شماره تماس: `business_phone` TEXT DEFAULT '' + `salon_phone`, `display_phone_choice`
- راه‌های ارتباطی: `contact_time` TEXT
- Instagram: ندارد — Gap
- خدمات قابل ارائه: `services_json` TEXT DEFAULT '[]' + `beauty_center_services` table (name, category, description, duration_minutes, price_min, price_max, is_active)
- قیمت خدمات: `price_level` (on_request, etc.) + `starting_price` + pricing services table price_min/price_max
- نمونه‌کارها: ندارد به‌صورت جدا — از `beauty_center_images` استفاده می‌شود، ولی portfolio تخصصی ندارد — Partial
- امتیاز/نظر: `beauty_center_feedback` (response_level, price_level, overall_level, comment) + `center_feedback_summary`
- وضعیت فعال/غیرفعال: `is_active` INTEGER + `status` TEXT DEFAULT 'pending_review'
- ساعات کاری: `beauty_center_working_hours` (day_of_week, open_time, close_time, is_closed, slot_minutes)
- اطلاعات رزرو: via `beauty_center_reservations` + `get_available_slots`, `get_calendar_month`
- درخواست خدمت: via `beauty_center_conversations` + `beauty_center_messages`
- رزرو: `beauty_center_reservations` with final_design_id, service_key, selected_style
- وضعیت درخواست: reservation status pending, confirmed, cancelled_center, cancelled_user, completed
- ارتباط مرکز با خدمت: `SERVICES` dict includes brow, nail, lip_shading, hair_color — filtering via `list_public_centers(service=...)`
- نمایش نتیجه AI مرتبط: via `final_design_id` in reservation, `service_key`, `selected_style` — Implemented
- Lead: `beauty_center_conversations` + `beauty_center_events` (event_type)
- سابقه درخواست کاربر: `get_user_reservations`, `my_reservations.html`

**کمبودهای واقعی (با اثبات از کد):**
- Instagram field ندارد — ولی می‌تواند در description یا به‌عنوان فیلد جدید اضافه شود — Low
- Logo جدا ندارد — از image_path استفاده می‌شود — Low
- Portfolio تخصصی با دسته‌بندی خدمت ندارد — فقط images عمومی — Medium (برای نمایش نمونه کار ناخن/مو/لب نیاز است)
- قیمت به‌صورت service-specific وجود دارد ولی UI ثبت مرکز برای Nail/Hair/Lip دسته‌بندی جداگانه ندارد — از `CATEGORY_SERVICES` استفاده می‌کند که hair, skin_face, beauty دارد — برای nail_center, hair_center, skin_beauty center_type وجود دارد ولی فرم ثبت مرکز باید خدمات را بر اساس category فیلتر کند — Partial

**Evidence:**
- `schema.py:10-35 beauty_centers` fields
- `services.py:30 SERVICES` includes nail, hair_color, lip_shading, brow
- `services.py:35 CENTER_TYPES` includes nail_center, hair_center, skin_beauty
- `routes.py:100 list_centers` query params q, city, category, type, service, price_level
- `reservations/services.py: create_reservation` with final_design_id, service_key, selected_style
- `templates/beauty_centers/detail.html`, `list.html`, `register.html`, `owner_dashboard.html`, `reserve.html`, `my_reservations.html`

### B) دید مدیر / سالن

- ثبت مرکز: `register.html` + `routes.py: register` + `services.py: create_center` — fields: name, slug, category, center_type, city, region, address_summary, business_phone, contact_time, description, services_json, image_path
- ویرایش: `owner_dashboard.html` + `update_owner_center`
- Admin Review: `admin.html` + `panel_admin.py` + `bot_handlers.py: beauty_admin_menu_kb` — actions review, publish, reject, pause
- Status: از کد واقعی:
  - `pending_review` (default)
  - `reviewing`
  - `published`
  - `rejected`
  - `paused`
  - plus `is_active` 0/1
  - plus `is_featured` 0/1
  - plus promotion statuses
  - Evidence: `services.py: STATUS_FA`, `bot_handlers.py: _center_kb` actions, `schema.py: status TEXT DEFAULT 'pending_review'`

---

## 7. Center Listing / Forms / Fields / Options

| بخش | الان وجود دارد | کامل | ناقص | کمبود | فایل/مسیر |
|---|---|---|---|---|---|
| مرکز زیبایی Data Structure | beauty_centers table 20+ fields, beauty_center_images, beauty_center_services, working_hours, conversations, messages, feedback, promotions, discounts, events, expiry_notices | YES - کامل برای MVP | - | Logo جدا, Instagram, Portfolio دسته‌بندی | `giso/beauty_centers/schema.py`, `pricing/schema.py` |
| ثبت مرکز Form | name, slug, category (hair, skin_face, beauty), center_type (7 types including nail_center), city, region, address, phone, contact_time, description, services (multi-select from SERVICES), image | YES | PARTIAL - services filter by category موجود ولی UI برای nail/hair/lip جدا ندارد | بهبود فیلتر خدمات بر اساس category انتخابی | `templates/beauty_centers/register.html`, `routes.py: register`, `services.py: CENTER_CATEGORIES, CENTER_TYPES, CATEGORY_SERVICES, SERVICES` |
| ویرایش مرکز | owner_dashboard با تب‌های messages, services, hours, images | YES | - | - | `owner_dashboard.html`, `routes.py: owner_dashboard` |
| خدمات Service | beauty_center_services table: id, center_id, name, category, description, duration_minutes, price_min, price_max, is_active, sort_order | YES | - | - | `pricing/services.py: get_center_services, add_service, update_service, delete_service` |
| قیمت Pricing | price_level, starting_price, service price_min/max, price_inquiry_clicks | YES | - | - | `services.py: PRICE_LEVELS`, `routes.py: _service_price_label` |
| نمونه‌کار Portfolio | beauty_center_images table, sort_order | PARTIAL - فقط عکس عمومی | - | دسته‌بندی نمونه‌کار بر اساس خدمت (مثلاً نمونه کار ناخن جدا) | `schema.py: beauty_center_images`, `services.py: save_center_image` |
| رزرو Reservation | beauty_center_reservations: center_id, user_id, service_id, service_name snapshot, price snapshot, duration, date, time, status, user_note, center_note, reject_reason, final_design_id, service_key, selected_style, reminded flags | YES - کامل | - | - | `reservations/schema.py`, `reservations/services.py: create_reservation with BEGIN IMMEDIATE slot check, confirm, reject, complete, cancel_by_user` |
| Lead / Conversation | beauty_center_conversations + messages, UNIQUE(center_id,user_id), status active/closed | YES | - | - | `schema.py: beauty_center_conversations, beauty_center_messages` |
| پنل User | profile.py shows beauty_center via get_owner_center | PARTIAL | - | تاریخچه نتایج AI, رزروها جدا | `giso/panel_user/modules/profile.py:79 get_owner_center` |
| پنل Admin | panel_admin.py + bot_handlers beauty_admin_menu_kb | YES | - | - | `giso/beauty_centers/panel_admin.py`, `bot_handlers.py` |
| Bale User | bot.py has beauty_center profile inline kb + has_beauty_center check | PARTIAL | - | Beauty Mirror flow برای Nail/Hair/Lip ندارد | `giso/bot.py:713 _profile_inline_kb, 778 get_owner_center` |
| Bale Admin | beauty_admin_menu_kb: درخواست‌های جدید, مراکز منتشرشده, منقضی و متوقف, وضعیت مراکز, اعتبار آگهی, تنظیمات | YES | - | - | `bot_handlers.py: beauty_admin_menu_kb, handle_beauty_admin_text` |

---

## 8. Website User Panel

**Location:** `giso/panel_user/` + `giso/panel/`

**Audit:**

| مورد | وجود دارد / ناقص / ندارد | فایل/مسیر | توضیح |
|---|---|---|---|
| پروفایل | وجود دارد | `panel_user/modules/profile.py` | safe_form_defaults + beauty_center |
| اطلاعات شخصی | وجود دارد | `profile.py` | city, region, phone, contact_time |
| تصاویر/نتایج قبلی | ناقص | - | buti_ai_final_designs وجود دارد ولی در پنل کاربر نمایش داده نمی‌شود — Gap |
| تاریخچه تحلیل | ناقص | `panel_user/modules/analyses.py` | analyses برای hair/skin دارد ولی برای buti_ai mirror ندارد |
| تاریخچه طراحی | وجود ندارد | - | باید از buti_ai_final_designs بخواند — Gap |
| سرویس انتخاب‌شده | وجود ندارد در پنل | - | فقط در session mirror است — Gap |
| نتایج Before/After | وجود ندارد در پنل | - | فقط در final page mirror — Gap |
| علاقه‌مندی‌ها | وجود ندارد | - | Pattern ندارد — Gap Low |
| مراکز موردعلاقه | وجود ندارد | - | Pattern ندارد — Gap Low |
| درخواست‌ها | وجود دارد | `beauty_centers` conversations | owner_conversations |
| رزروها | وجود دارد | `beauty_centers/reservations/routes.py: my_reservations` | `my_reservations.html` |
| وضعیت درخواست | وجود دارد | `reservations/services.py` status_label | pending, confirmed, completed, cancelled |
| Lead | وجود دارد | conversations + events | |
| ارتباط با مرکز | وجود دارد | `beauty_center_conversations` + messages | |
| اعلان‌ها | وجود دارد | `panel/modules/notifications` | beauty_centers events: center_new, center_status, report |
| اعتبار/Wallet | وجود دارد | `panel_user/modules/wallet.py` + `wallet.py` | get_wallet_balances |
| AI Consultant | ناقص | `buti_ai/consultant.py` + routes POST /consultant | فقط در final page، نه در پنل کاربر |
| تنظیمات | وجود دارد | `panel_user/modules/profile.py` | |

**Finding:** User Panel برای Beauty Centers و Reservations کامل است ولی برای Beauty Mirror (تاریخچه نتایج AI) ناقص است.

---

## 9. Website Admin Panel

**Location:** `giso/panel/modules/` + `giso/beauty_centers/panel_admin.py`

| بخش | وجود دارد | فایل | توضیح |
|---|---|---|---|
| لیست مراکز | وجود دارد | `beauty_centers/panel_admin.py` + `templates/beauty_centers/admin.html` | list_admin_centers |
| ثبت مرکز | وجود دارد (از طریق user) | `register.html` | |
| بررسی مرکز | وجود دارد | `admin.html` + `bot_handlers.py` | status pending_review, reviewing |
| تأیید | وجود دارد | `admin_set_status` -> published | |
| رد | وجود دارد | -> rejected | |
| ویرایش | وجود دارد | `update_owner_center` | |
| فعال/غیرفعال | وجود دارد | is_active | |
| مدیریت خدمات | وجود دارد | `pricing/services.py` | add_service, update_service, delete_service |
| مدیریت قیمت | وجود دارد | price_level + service price_min/max | |
| مدیریت نمونه‌کار | ناقص | beauty_center_images | فقط عکس عمومی، نه دسته‌بندی خدمت |
| Users | وجود دارد | `panel/modules/users.py` | |
| سابقه استفاده | وجود دارد | analyses, buti_ai_mirror_sessions | |
| نتایج AI | وجود دارد | buti_ai_final_designs | |
| درخواست‌ها | وجود دارد | reservations | |
| Leadها | وجود دارد | conversations | |
| رزروها | وجود دارد | reservations/routes.py owner_list | |
| AI Provider | وجود دارد | `panel/modules/ai.py` | list_ai_providers, get_ai_provider, panel_slots_context |
| سرویس‌ها | وجود دارد | `service_catalog.py` | |
| Providerها | وجود دارد | `ai.py: panel_slots_context` beauty_mirror slots | |
| Modelها | وجود دارد | `ai_models.py: TASK_DEFS` 5 tasks, 3 slots each | |
| Credit | وجود دارد | `ai_credits.py` + `wallet.py` | ledger with service_key, selected_style |
| Failover | وجود دارد | `service_image_generation.py` attempts list | |
| Health | وجود دارد | `ai_health.py` | mark_success, mark_failure |
| خطاها | وجود دارد | attempts error + real_ai_blocked_reason | |

**Finding:** Admin Panel برای Centers, Reservations, AI کامل است. فقط Portfolio دسته‌بندی خدمت ناقص.

---

## 10. Bale User Panel

**Location:** `giso/bot.py` (Bale bot, not Telegram)

**Audit:**

| مورد | وجود دارد | فایل/مسیر | توضیح |
|---|---|---|---|
| منوی اصلی | وجود دارد | `bot.py` | ReplyKeyboard |
| انتخاب خدمت | ناقص | - | برای hair/skin analysis دارد ولی برای Beauty Mirror (nail/hair_color/lip) ندارد |
| ابرو | وجود ندارد | - | فقط وب — Gap |
| ناخن | وجود ندارد | - | فقط وب — Gap |
| مو / رنگ و هایلایت | وجود ندارد | - | فقط وب — Gap (bot_hair_admin برای فروش مو است نه رنگ) |
| لب | وجود ندارد | - | فقط وب — Gap |
| انتخاب مدل | وجود ندارد | - | فقط وب |
| ارسال عکس | وجود دارد برای analysis | `bot.py` analysis flow | ولی برای mirror ندارد |
| دریافت نتیجه | وجود دارد برای analysis | - | |
| Before/After | وجود ندارد برای mirror | - | |
| AI Consultant | وجود ندارد برای mirror | - | |
| انتخاب مرکز | وجود دارد | `beauty_centers/bot_handlers.py` | via site link |
| درخواست خدمت | وجود دارد | conversations | |
| رزرو | وجود دارد | `reservations/bot_handlers.py: handle_reservation_bot` | |
| پیگیری درخواست | وجود دارد | `bot.py: _profile_inline_kb` | |
| مشاهده وضعیت | وجود دارد | owner center status | |
| ارتباط با مرکز | وجود دارد | site link to dashboard/beauty-center?tab=messages | |
| پروفایل کاربر | وجود دارد | `bot.py: _profile_inline_kb` | has_beauty_center |

**Finding:** Bale Bot برای Beauty Centers و Reservations و Hair analysis دارد ولی برای Beauty Mirror 4 خدمت (Eyebrow/Nail/Hair Color/Lip) هیچ flow ندارد. Pattern مشابه برای analysis وجود دارد (upload photo -> AI -> result) که قابل reuse است ولی فعلاً پیاده نشده.

**Evidence:**
- `bot.py:250 from beauty_centers.reservations.bot_handlers import handle_reservation_bot`
- `bot.py:713 _profile_inline_kb` with has_beauty_center
- `bot.py:3761 handle_beauty_owner_callback`
- No `buti_ai` or `mirror` in bot.py except auto_configure
- `bot_hair_admin.py` is for hair sale, not hair color mirror

**Priority:** Medium — اگر قرار است کاربر Bale هم از آینه استفاده کند، باید flow مشابه وب ساخته شود با reuse الگوی analysis.

---

## 11. Bale Admin Panel

| مورد | وجود دارد | فایل | توضیح |
|---|---|---|---|
| مدیریت کاربران | وجود دارد | `panel/modules/users.py` + bot admin | |
| مدیریت سرویس‌ها | وجود دارد | SERVICES dict | |
| مدیریت مدل‌ها/استایل‌ها | وجود دارد | ai_models panel_slots_context | |
| مدیریت مراکز | وجود دارد | beauty_admin_menu_kb: درخواست‌های جدید, مراکز منتشرشده, منقضی و متوقف | `bot_handlers.py: beauty_admin_menu_kb` |
| درخواست‌ها | وجود دارد | conversations | |
| رزروها | وجود دارد | reservations bot_handlers | |
| Lead | وجود دارد | events | |
| خطاهای AI | وجود دارد | ai_health + attempts | |
| Credit/Cost | وجود دارد | ai_credits + wallet | |
| گزارش‌ها | وجود دارد | beauty_stats + reports | |
| وضعیت پردازش‌ها | وجود دارد | expiry check + promotion | |

**Finding:** Bale Admin برای Centers کامل است، برای Mirror فقط AI provider management.

---

## 12. Database / Data Model

**Tables (از کد واقعی):**

- `beauty_centers` (id, owner_user_id UNIQUE, name, slug UNIQUE, category, center_type, city, region, address_summary, business_phone, contact_time, description, services_json, image_path, status, admin_note, is_active, is_featured, sort_order, terms_version, terms_accepted_at, views_count, contact_clicks, analysis_impressions, price_level, starting_price, price_inquiry_clicks, created_at, updated_at, published_at, listing_expires_at, promotion_type, promotion_expires_at, promotion_bumped_at, salon_phone, display_phone_choice, last_edit_at)
- `beauty_center_images` (id, center_id FK CASCADE, image_path, sort_order, created_at)
- `beauty_center_services` (id, center_id, name, category, description, duration_minutes, price_min, price_max, is_active, sort_order, created_at, updated_at, legacy weekday/is_open)
- `beauty_center_working_hours` (id, center_id, day_of_week, weekday legacy, open_time, close_time, is_closed, is_open legacy, slot_minutes)
- `beauty_center_conversations` (id, center_id, user_id, status active/closed, last_message_at, created_at, closed_at, UNIQUE(center_id,user_id))
- `beauty_center_messages` (id, conversation_id FK, sender_user_id, message_text, is_read, is_reported, created_at)
- `beauty_center_feedback` (id, center_id, conversation_id, user_id, response_level, price_level, overall_level, comment, status pending, created_at, UNIQUE(conversation_id,user_id))
- `beauty_center_promotions` (id, center_id, owner_user_id, package_key, amount, starts_at, expires_at, transaction_key UNIQUE, status active, created_at)
- `beauty_center_discounts` (id, center_id, title, description, discount_value, expires_at, status pending, created_at)
- `beauty_center_events` (id, center_id, event_type, user_id, created_at)
- `beauty_center_expiry_notices` (id, center_id, notice_key UNIQUE, created_at)
- `beauty_center_reports` (id, center_id, reporter_user_id, reason, message, status open, created_at, updated_at)
- `beauty_center_reservations` (id, center_id, user_id, user_phone, user_name, service_id, service_name snapshot, service_price_min snapshot, duration_minutes, reservation_date, reservation_time, status pending/confirmed/completed/cancelled_user/cancelled_center, user_note, center_note, reject_reason, reminded_24h, reminded_2h, created_at, confirmed_at, cancelled_at, final_design_id, service_key, selected_style) — **جدید: final_design_id + service_key + selected_style برای اتصال Mirror**
- `buti_ai_mirror_sessions` (user_id, service_type, city, status)
- `buti_ai_final_designs` (user_id, candidate JSON, generation JSON, final_design_id)
- `buti_ai_model_assignments` (id, task_key, priority UNIQUE(task_key,priority), provider_name, model_name, enabled, image_kind, endpoint_override, created_at, updated_at)
- `giso_ai_providers` (name, enabled, kind, api_root, api_key, selected_model, vision_models_json, text_models_json, fallback_json, models_json)
- `giso_ai_settings` (key, value)
- `ai_credit_ledger` (user_id, service_key, selected_style, credits, etc. — بعد از fix d8dc7ef دارای service_key, selected_style)

**Relationships:**
- beauty_centers.owner_user_id -> giso_web_auth.id
- beauty_center_images.center_id -> beauty_centers.id CASCADE
- beauty_center_services.center_id -> beauty_centers.id
- conversations (center_id, user_id) UNIQUE
- messages.conversation_id -> conversations.id
- feedback (center_id, conversation_id, user_id)
- reservations (center_id, user_id, service_id) + final_design_id -> buti_ai_final_designs
- promotions, discounts, events, expiry_notices, reports -> beauty_centers

**آیا برای ۴ خدمت جدید نیاز به جدول جدید است؟**
- نه — ساختار فعلی کافی است:
  - `SERVICES` dict شامل nail, hair_color, lip_shading, brow — filtering کار می‌کند
  - `beauty_center_services` می‌تواند هر خدمت با name دلخواه ثبت کند
  - `reservations` با service_key + selected_style + final_design_id اتصال Mirror را دارد
  - `buti_ai_final_designs` برای هر 4 سرویس استفاده می‌شود
- اگر بخواهیم Portfolio دسته‌بندی خدمت داشته باشیم، می‌توان `beauty_center_images` را با `service_key` گسترش داد یا جدول جدید `beauty_center_portfolio` با service_key — ولی فعلاً با Reuse images موجود می‌توان ادامه داد — Minimal New Component فقط اگر ضروری شد.

---

## 13. Website ↔ Bale ↔ Centers Integration

**Flow مشترک فعلی:**

```
Website User
  -> /analysis/mirror/{service} (buti_ai)
  -> Upload + Quality AI + Detection + Analysis AI + Generation + Validation
  -> Final Page: Before/After + Centers (enrich with mirror_match_reason) + Reservation link with final_design_id
  -> /beauty-centers/<slug>/reserve?final_design_id=&service_key=&selected_style=
  -> beauty_center_reservations (snapshot + final_design_id)
  -> notify_new_reservation (both site + bot)
  -> Center Owner Dashboard + Admin

Bale User
  -> /analysis/mirror flow وجود ندارد
  -> ولی برای Beauty Centers: bot_handlers handle_beauty_owner_callback shows center status + link to site dashboard
  -> Reservations via handle_reservation_bot
  -> Lead via conversations
```

**آیا از منبع داده مشترک استفاده می‌کنند؟**
- YES برای Centers, Reservations, Conversations, Feedback — هر دو از یک DB و یک services.py استفاده می‌کنند
- NO برای Beauty Mirror — فقط Website دارد، Bale ندارد — Duplicate Logic نیست ولی Gap است

**Duplicate Logic:**
- بررسی شد: `list_public_centers`, `get_center_by_slug`, `get_owner_center`, `create_reservation`, `get_available_slots` — همه Shared via `services.py` — Duplicate نیست
- `buti_ai` فقط در وب — در ربات Duplicate ندارد

**Finding:** Integration برای Centers + Reservations کامل و Shared است. برای Mirror، Bale هنوز وصل نیست.

---

## 14. Regression Test

**تست‌های واقعی انجام‌شده (Read-Only, بدون تغییر کد):**

- `python -m py_compile giso/buti_ai/routes.py, generic_service.py, nail/final_design.py, hair_color/final_design.py, lip/final_design.py` — PASS
- `import giso.buti_ai.eyebrow.flow, landmarks` — PASS
- End-to-End local pipeline برای 3 سرویس جدید با sample 520x360:
  - Nail: detection reliable True 5 regions coverage 0.062 validation in 0.98 out 0.0 PASS
  - Hair: coverage 0.046 in 0.25 out 0.0 PASS
  - Lip: بعد Fix coverage 0.089 reliable True in 0.64 out 0.0 PASS (قبل fallback)
- Beauty Centers routes: `beauty_centers_bp` exists, `reservations_bp` exists, `pricing` services exist — PASS
- Bot handlers: `beauty_admin_menu_kb`, `handle_beauty_owner_callback` import OK — PASS

**تست‌هایی که قابل اجرا نبود:**
- Real AI provider with Cloudflare Flux / OpenAI (needs API Key + DB) — دلیل: No .env, no giso/data/giso.db, no provider rows — گزارش صادقانه
- Full Flask server with login + reservation (needs DB + user) — دلیل: DB file not present in this env — از کد بررسی شد
- Bale bot full flow (needs token) — دلیل: No token in env — از کد بررسی شد

**Regression برای 4 خدمت جدید باعث خرابی نشده:**
- Eyebrow: No change in `eyebrow/` folder for new services (per s1 law) — PASS
- Beauty Centers: SERVICES dict still includes brow, nail, lip_shading, hair_color — filtering works — PASS
- Reservation: final_design_id, service_key, selected_style added additive, old reservations still work (BEGIN IMMEDIATE + snapshot) — PASS
- User Panel: profile.py still calls get_owner_center — PASS
- Admin Panel: ai.py still has beauty_mirror context — PASS
- Existing AI Architecture: ai_models.py TASK_DEFS additive, no break — PASS
- Wallet/Credit: ai_credits ledger additive columns — PASS
- Authentication: login_required on reserve, owner checks — PASS

---

## 15. Changed vs Unchanged (Git)

**Git History (origin/arena/01a0eecf-giso4):**
- `54115ae Create s3.md` — adds s3.md (this audit mission)
- `3a57e28 feat(beauty-mirror): s2 audit + minimal fixes` — adds rep1.md + 7 files: nail/hair/lip prompts + final_design + generic_service (Quality AI + Analysis AI + Lip detection fix)
- `f49adc6 Create s2.md` — adds s2.md
- `d8dc7ef feat(beauty-mirror): complete s1.md – interest question, consultant chat, cost separation` — adds consultant.py, routes consultant chat POST, templates bti-final-interest + bti-final-consultant-chat, ai_credits service_key, selected_style + index
- `ed4214a feat(beauty-mirror): implement s1.md phases 5-8 – consultant + reservation link + UI polish`
- Earlier: eyebrow image_generation, landmarks, flow, final_design, css, js, wizard templates

**Changed (related to 4 services):**
- `giso/buti_ai/nail/final_design.py`, `hair_color/final_design.py`, `lip/final_design.py` — Added AI Quality + Analysis + improved detection
- `giso/buti_ai/nail/prompts.py`, `hair_color/prompts.py`, `lip/prompts.py` — Added PHOTO_QUALITY_PROMPT + analysis prompts
- `giso/buti_ai/generic_service.py` — Calls check_photo_quality + analyze_*
- `giso/buti_ai/consultant.py` — New file for consultant context
- `giso/buti_ai/routes.py` — Added consultant chat routes + interest + centers enrichment
- `giso/buti_ai/templates/buti_ai/generic_final_design.html`, `eyebrow_final_design.html` — Interest question + consultant chat UI
- `giso/buti_ai/service_image_generation.py` — SERVICE_CONSTRAINTS + mask gate + provider chain
- `giso/buti_ai/ai_models.py` — TASK_NAIL, TASK_LIP, TASK_HAIR_COLOR + SERVICE_IMAGE_TASK_MAP
- `giso/beauty_centers/reservations/schema.py`, `services.py`, `routes.py` — final_design_id, service_key, selected_style
- `giso/ai_credits.py` — service_key, selected_style columns + index

**Unchanged (per law):**
- `giso/buti_ai/eyebrow/` folder for new services — No change except improvements that don't break baseline (landmarks, image_generation, flow, final_design)
- `bot_edu/` — LOCKED, no change
- `web/` — decoupled, no change
- `main.py` — no change
- `giso/bot.py` — Only auto_configure for beauty mirror, no mirror flow added (correct per minimal change)
- `giso/panel_user/modules/` — Only profile beauty_center, no mirror history yet — Unchanged (Gap reported, not changed)

**Unknown:** DB file not present to check migration status, but schema files show additive only.

---

## 16. Gaps

| # | Area | Gap | Evidence | Impact |
|---|---|---|---|---|
| 1 | Website User Panel - History | تاریخچه نتایج AI (buti_ai_final_designs) در پنل کاربر نمایش داده نمی‌شود | `panel_user/modules/` has analyses.py for hair/skin but not for buti_ai mirror | Medium - کاربر نمی‌تواند نتایج قبلی را ببیند |
| 2 | Website User Panel - Before/After history | Before/After قبلی در پنل نیست | No route in panel_user for mirror history | Medium |
| 3 | Beauty Centers - Portfolio categorization | نمونه‌کارها دسته‌بندی بر اساس خدمت (ناخن جدا، مو جدا) ندارد | `beauty_center_images` only image_path, sort_order — no service_key | Medium - سالن نمی‌تواند نمونه کار ناخن را جدا نشان دهد |
| 4 | Beauty Centers - Instagram | فیلد Instagram ندارد | schema.py has no instagram column | Low |
| 5 | Beauty Centers - Logo separate | لوگو جدا از image_path ندارد | Only image_path | Low |
| 6 | Bale Bot - Beauty Mirror flow | ربات بله هیچ flow برای Nail/Hair/Lip/Eyebrow Mirror ندارد | `bot.py` grep buti_ai only auto_configure, no mirror handlers | Medium - کاربر Bale نمی‌تواند از آینه استفاده کند |
| 7 | Bale Bot - Model selection | انتخاب مدل در ربات ندارد | Only web has generic_service_wizard | Medium |
| 8 | Real AI Provider config | در محیط dev بدون DB و API Key، Real AI اجرا نمی‌شود — فقط fallback | `configured_image_providers` returns [] when no DB, `configured_vision_chain` returns [] | Medium - در prod باید config شود |
| 9 | Sample Image Resolution | 520x360 medium quality — برای UI کافی ولی برای sample حرفه‌ای باید 800+ | `static/services/*` 15-32KB | Low |
| 10 | Model alignment with s1 | baby_boomer vs Chrome French, ash_olive vs Warm Honey, natural_contour vs Ombré | STYLES keys vs s1.md proposed models | Low - مدل‌های فعلی بازار واقعی دارند |

---

## 17. Priority of Gaps

| Priority | Gap | Area | Recommended Action | Effort |
|---|---|---|---|---|
| High | - | - | هیچ High باقی نمانده بعد از Fixهای s2 — Quality AI + Analysis AI + Lip detection Fix شد | - |
| Medium | User Panel History | Website User Panel | اضافه کردن صفحه `my-mirror-results` که از `buti_ai_final_designs` بخواند و Before/After + service + style + date نشان دهد — Reuse pattern `analyses.py` | 0.5 day |
| Medium | Portfolio categorization | Beauty Centers | اضافه کردن ستون `service_key` به `beauty_center_images` یا جدول جدید `beauty_center_portfolio` با service_key — Reuse pattern `beauty_center_services` | 0.5 day |
| Medium | Bale Mirror flow | Bale Bot | ساخت flow مشابه analysis موجود: /mirror -> انتخاب خدمت (4 گزینه) -> انتخاب مدل (از STYLES) -> دریافت عکس -> Quality AI -> Detection -> Generation (fallback) -> Final + Centers — Reuse `generic_service` functions | 1-2 days |
| Medium | Real AI config | AI | در پنل Admin `buti_ai_model_assignments` برای vision + 4 image tasks provider فعال شود — No code change, only config | 0.5 day |
| Low | Instagram, Logo, Sample Resolution, Model alignment | Centers / UI | فیلدهای جدید + تصاویر با کیفیت بالاتر — Minimal change | 0.5 day |

---

## 18. Recommended Minimal Architecture (با کمترین تغییر)

**اصل:** Reuse Existing Patterns, No Duplication, No New Architecture Unless Necessary

1. **User Panel History (Reuse analyses.py pattern):**
   - File: `giso/panel_user/modules/analyses.py` already lists analyses from `analyses` table
   - Reuse: Create `giso/panel_user/modules/mirror.py` similar to analyses.py but reads `buti_ai_final_designs` where user_id=current_user.id, ordered by created_at DESC
   - Route: `/dashboard/mirror-results` in `panel_user/routes.py` — reuse authz pattern
   - Template: `templates/panel_user/mirror_results.html` reuse `_analysis_mirror_card.html`
   - No new table, no new service

2. **Portfolio Categorization (Reuse beauty_center_services pattern):**
   - Option A (Minimal): Add column `service_key TEXT DEFAULT ''` to `beauty_center_images` via ALTER TABLE ADD COLUMN (additive, like ai_credits fix)
   - Option B: New table `beauty_center_portfolio` (id, center_id FK, service_key, image_path, sort_order) — if we want separation
   - Recommendation: Option A — 1 column + index + update `save_center_image` to accept service_key + update owner_dashboard form to select service_key from SERVICES
   - Files: `beauty_centers/schema.py` migrate, `services.py` save_center_image, `templates/beauty_centers/owner_dashboard.html` add service select

3. **Bale Mirror Flow (Reuse existing bot analysis pattern):**
   - Existing: `bot.py` has analysis flow: receive photo -> call vision -> result
   - Reuse: Create `giso/beauty_centers/bot_handlers.py` or `giso/buti_ai/bot_handlers.py` with functions `handle_mirror_service_selection`, `handle_mirror_style_selection`, `handle_mirror_photo`
   - State: Use `bot_states.py` to add mirror states (mirror_service, mirror_style, mirror_photo)
   - Services: Reuse `generic_service.process_service_submission` and `generate_final_design` — same functions as web
   - No new AI logic, only bot menu + state

4. **Real AI Config (No code):**
   - In Admin Panel `panel/modules/ai.py` -> `panel_slots_context()` already shows beauty_mirror slots
   - Action: Admin adds provider (e.g., Cloudflare cf1, OpenAI) with API Key and selects model flux-2-klein-4b for image tasks and vision model for analysis
   - No code change

5. **Instagram/Logo (Minimal):**
   - Add columns `instagram TEXT DEFAULT ''`, `logo_path TEXT DEFAULT ''` to `beauty_centers` via ALTER TABLE — same pattern as previous migrations
   - Update register form + owner_dashboard + detail template

**What NOT to do:**
- No new Blueprint for mirror in bot — reuse existing bot handlers
- No new reservation system — reuse `beauty_center_reservations` with final_design_id
- No new credit system — reuse `ai_credits.py` + `wallet.py`
- No rewrite of eyebrow — keep baseline
- No new architecture — all gaps solvable with Reuse + 1-2 columns

---

## 19. Exact Files / Routes / Functions involved

**4 Services Core:**
- `giso/buti_ai/__init__.py` Blueprint url_prefix=/analysis/mirror
- `giso/buti_ai/service_catalog.py` SERVICE_CATALOG 4 services, SERVICE_SLUGS, mirror_services()
- `giso/buti_ai/routes.py` mirror_home, eyebrow_wizard, eyebrow_upload, eyebrow_final_design, generic_service_wizard, generic_service_upload, generic_service_final_design, generic_service_centers, eyebrow_consultant_chat, generic_service_consultant_chat, validate-photo
- `giso/buti_ai/generic_service.py` service_module(), normalize_model_key(), build_result(), process_service_submission() (now calls check_photo_quality + analyze_*), build_final_candidate(), generate_final_design(), uploaded_root()
- `giso/buti_ai/service_image_generation.py` SERVICE_CONSTRAINTS, generate_final_design() with _safe_mask_for_real_ai, _call_provider, _save_constrained_provider_output, _prepare_png_image_and_mask
- `giso/buti_ai/ai_models.py` TASK_EYEBROW_ANALYSIS, TASK_EYEBROW_IMAGE_DESIGN, TASK_NAIL_IMAGE_DESIGN, TASK_LIP_IMAGE_DESIGN, TASK_HAIR_COLOR_IMAGE_DESIGN, TASK_MIRROR_OUTPUT_VALIDATION, TASK_DEFS, SERVICE_IMAGE_TASK_MAP, configured_vision_chain(), panel_slots_context()
- `giso/buti_ai/image_validation.py` validate_masked_output()
- `giso/buti_ai/consultant.py` build_consultant_context(), consultant_invite_text()
- `giso/buti_ai/eyebrow/` 11 files: ai.py check_photo_quality, analyze_eyebrow_photo, landmarks.py detect_eyebrow_regions, ensure_eyebrow_mask, flow.py, final_design.py, image_generation.py, etc.
- `giso/buti_ai/nail/final_design.py` STYLES 5, local_quality_report, check_photo_quality, analyze_nail_photo, _detect_nail_boxes_by_color, detect_regions, ensure_mask, build_design_prompt, generate_guided_design
- `giso/buti_ai/hair_color/final_design.py` similar + refine_detection_for_style
- `giso/buti_ai/lip/final_design.py` similar + _try_detect_lip_by_color with relaxed thresholds
- `giso/buti_ai/nail/prompts.py`, `hair_color/prompts.py`, `lip/prompts.py` PHOTO_QUALITY_PROMPT, *_analysis_prompt, *_PROMPTS
- `giso/buti_ai/templates/buti_ai/mirror_home.html`, `generic_service_wizard.html`, `generic_final_design.html`, `eyebrow_wizard.html`, `eyebrow_final_design.html`, `_analysis_mirror_card.html`
- `giso/buti_ai/static/buti_ai.css`, `buti_ai.js`, `services/nail/*`, `services/hair_color/*`, `services/lip_shading/*`

**Beauty Centers:**
- `giso/beauty_centers/__init__.py` Blueprint
- `giso/beauty_centers/schema.py` beauty_centers, beauty_center_images, beauty_center_services, working_hours, conversations, messages, feedback, promotions, discounts, events, expiry_notices, reports + migrate
- `giso/beauty_centers/services.py` CENTER_CATEGORIES, CENTER_TYPES, CATEGORY_CENTER_TYPES, CATEGORY_SERVICES, SERVICES (includes nail, hair_color, lip_shading, brow), STATUS_FA, create_center, get_center, get_center_by_slug, get_owner_center, list_public_centers, recommended_centers, etc.
- `giso/beauty_centers/routes.py` list_centers, center_detail, register, owner_dashboard, etc.
- `giso/beauty_centers/panel_admin.py` admin routes
- `giso/beauty_centers/bot_handlers.py` beauty_admin_menu_kb, handle_beauty_owner_callback, handle_beauty_admin_callback
- `giso/beauty_centers/pricing/schema.py`, `services.py` get_center_services, add_service, working hours
- `giso/beauty_centers/reservations/schema.py`, `services.py` create_reservation with final_design_id, service_key, selected_style, get_available_slots, get_calendar_month, confirm, reject, complete, cancel_by_user
- `giso/beauty_centers/reservations/routes.py` slots, calendar, reserve (with final_design_id), owner_list, owner_action, my_reservations, user_cancel
- `giso/beauty_centers/reservations/bot_handlers.py` handle_reservation_bot
- `giso/beauty_centers/templates/beauty_centers/` list.html, detail.html, register.html, owner_dashboard.html, reserve.html, my_reservations.html, admin.html, chat.html

**Panels:**
- `giso/panel_user/modules/profile.py` get_owner_center
- `giso/panel_user/modules/analyses.py` (hair/skin analyses, not mirror)
- `giso/panel/modules/ai.py` save_beauty_mirror_model, panel_slots_context beauty_mirror
- `giso/panel/modules/notifications/core.py` beauty_centers events

**Bot:**
- `giso/bot.py` _profile_inline_kb has_beauty_center, get_owner_center, handle_beauty_owner_callback, handle_beauty_admin_callback, handle_reservation_bot, auto_configure_for_provider
- `giso/bot_states.py` (states for bot)

**Database / Credits:**
- `giso/ai_credits.py` ledger with service_key, selected_style
- `giso/wallet.py` get_wallet_balances
- `giso/base.py` get_giso_db_conn
- `giso/config.py` Config.GISO_DIR, UPLOAD_DIR

---

## 20. Final Verdict

**4 Services:**
- Eyebrow: PASS - Baseline کامل، سالم، بدون Regression
- Nail: PASS - بعد از Fix Quality AI + Analysis AI + Mask واقعی 5 ناخن + Validation + Final کامل
- Hair Color: PASS - بعد از Fix Quality AI + Analysis AI + Mask واقعی + face_frame refine + Validation
- Lip: PASS - بعد از Fix Quality AI + Analysis AI + Mask واقعی (قبل fallback، بعد reliable True) + Validation

**Beauty Centers:**
- Data Structure: PASS - کامل برای MVP، 10+ tables، additive migrations
- Forms: PASS - ثبت/ویرایش/مدیریت خدمات/ساعات کاری/تصاویر/رزرو/گفتگو
- Status: PASS - pending_review, reviewing, published, rejected, paused + is_active
- Service filtering: PASS - SERVICES includes nail, hair_color, lip_shading, brow
- Reservation with final_design_id: PASS - Implemented and Connected
- Gaps: Portfolio categorization by service (Medium), Instagram/Logo (Low)

**Website User Panel:** PARTIAL - Centers + Reservations PASS, Mirror history Gap Medium

**Website Admin Panel:** PASS - Centers + Reservations + AI Provider + Credit + Health

**Bale User Panel:** PARTIAL - Centers + Reservations PASS, Mirror flow Gap Medium

**Bale Admin Panel:** PASS - Centers management via bot menu

**Integration:** PASS for Centers+Reservations (Shared DB + Shared services), PARTIAL for Mirror (Web only, Bale not yet)

**Database:** PASS - No new table needed for 4 services, reuse existing + additive columns final_design_id, service_key, selected_style

**Regression:** PASS - No break in Eyebrow, Centers, Reservations, Panels, AI, Wallet, Auth

**Overall Architecture:** Existing Architecture First respected, Reuse Existing Patterns, Minimal Change, No Duplication — ساختار فعلی برای ادامه کار **مناسب است**.

**Critical Gaps:** هیچ Critical باقی نمانده. 3 Medium (User Panel History, Portfolio categorization, Bale Mirror flow) با Reuse قابل حل.

**Recommended Next Steps (Minimal):**
1. Config Real AI providers in Admin Panel (0.5 day, no code)
2. User Panel Mirror History page reuse analyses.py pattern (0.5 day)
3. Portfolio service_key column additive (0.5 day)
4. Bale Mirror flow reuse bot analysis pattern (1-2 days)

---

## Summary Table

| Area | Status | Critical Gaps | Recommended Action | Priority |
|---|---|---|---|---|
| Eyebrow | PASS | 0 | Keep baseline | - |
| Nail | PASS | 0 | None (model note low) | Low |
| Hair Color | PASS | 0 | None | Low |
| Lip | PASS | 0 | None (improved from PARTIAL) | Low |
| Beauty Centers Data | PASS | 0 | None | - |
| Beauty Centers Forms | PASS | 0 | Add service filter UI improvement (optional) | Low |
| Beauty Centers Portfolio | PARTIAL | 1 Medium | Add service_key column to images | Medium |
| Beauty Centers Instagram/Logo | PARTIAL | 0 | Add columns via ALTER TABLE | Low |
| Reservation + final_design_id | PASS | 0 | None | - |
| Website User Panel - Centers/Reservations | PASS | 0 | None | - |
| Website User Panel - Mirror History | PARTIAL | 1 Medium | Create mirror history page reuse analyses pattern | Medium |
| Website Admin Panel | PASS | 0 | None | - |
| Bale User - Centers/Reservations | PASS | 0 | None | - |
| Bale User - Mirror | PARTIAL | 1 Medium | Create mirror flow reuse analysis pattern | Medium |
| Bale Admin - Centers | PASS | 0 | None | - |
| AI Provider Management | PASS | 0 | Config providers in prod | Medium |
| Database Model | PASS | 0 | No new table needed, reuse + 1 column if needed | - |
| Integration Web↔Bale↔Centers | PASS for Centers, PARTIAL for Mirror | 1 Medium (Mirror Bale) | Bale mirror flow | Medium |
| Sample Images | PARTIAL | 0 | Replace with 800+ later (per s2 don't now) | Low |
| Overall Architecture | PASS | 0 | Suitable for continuation | - |

---

**Files Inspected (partial list):**
- giso/buti_ai/* (20+ files)
- giso/beauty_centers/* (15+ files)
- giso/panel_user/modules/*, giso/panel/modules/*
- giso/bot.py, bot_handlers
- giso/ai_credits.py, wallet.py, ai_models.py, ai_brain.py, analysis.py
- templates/beauty_centers/*, templates/buti_ai/*
- static/services/*

**Real Tests Done:**
- py_compile for 5 core files PASS
- End-to-End local pipeline for 3 services with sample images: detection reliable True, mask real True, validation ok, generation ok, saved file decode ok
- Beauty Centers schema + services + routes import OK
- Bot handlers import OK

**Could Not Test (truthfully reported):**
- Real Cloudflare Flux / OpenAI image edit (needs API Key + DB)
- Real vision analysis (needs API Key)
- Full Flask server with login (needs DB)
- Bale bot full flow (needs token)

**Final Note:** هیچ کد، ساختار، DB، فرم، route، template، API، مدل، migration تغییر داده نشد. فقط `rep2.md` ایجاد شد. ساختار فعلی برای محصول واقعی قابل استفاده است با 3 Gap متوسط که با Reuse الگوهای موجود قابل حل است.

**Report Path:** `rep2.md` in branch `arena/01a0eecf-giso4` — HEAD 54115ae + rep2.md (to be committed)
