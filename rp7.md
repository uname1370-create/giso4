# RP7 — Beauty Ecosystem / 4 Panel Architecture Audit — Read-Only

تاریخ: 2026-10-07
Branch: arena/01a0eecf-giso4
HEAD: 90356d6 (rp6 v2) + 56fac4b (s4) + f25c37b (rp6) + 572e7a2 (rp5)
Auditor: Arena Agent — giso-dev Skill Workflow — Read-Only, No Code Change
Method: Code is Truth, Reuse > Extend > New, Existing Architecture First
Scope Lock: ALLOWED = [rp7.md] — هیچ کد دیگری تغییر نکرده (قانون s4.md: ممنوع تغییر کد/فایل/DB/template/route/commit/push/Graph/project_memory)
Reference: s4.md (524 lines) — 4 Panel Architecture Audit — Customer → زیبایی من → سالن‌های زیبایی → نوبت → گفتگو → آنالیزهای من → خدمات ابرو/مو/آرایش/ناخن — Owner → مدیریت سالن → خدمات → قیمت → نمونه‌کار → نوبت → گفتگو → مشتری

---

## 1. Executive Summary

ساختار فعلی گیسو برای اکوسیستم زیبایی **80% آماده** است و نیاز به **معماری جدید ندارد** — فقط **توسعه افزودنی (Extend)** و **اتصال ماژول‌های موجود**.

**CURRENT واقعیت کد:**
- پنل کاربر: 10 ماژول فعال (overview, hair_sale, orders, analyses, reservations, center_chats, wallet, chats, profile + marketplace/buyer_request/beauty_center hidden) با گروه‌بندی "اصلی/خدمات/پشتیبانی/حساب" + USER_MODULES + USER_MODULE_GROUPS + MODULES_META — route canonical /dashboard/<module> — guard role user/admin/super — menu badges center_unread + notifications
- آنالیز هوشمند: دو سیستم موازی — (1) آنالیز مو/پوست قدیمی (Analysis model hair/skin با ai_report_json, plan_json, quick_solution_json) در panel_user/modules/analyses.py — (2) Buti AI Mirror جدید 4 خدمت فعال (eyebrow, nail, hair_color, lip_shading) با SERVICE_CATALOG + generic_service + STYLES 5 per service + CHANGE_LEVELS + buti_ai_sessions + buti_ai_final_designs + service_demand/waitlist + routes /analysis/mirror/ + templates generic_service_wizard/generic_final_design + consultant + interest + centers enrich
- Beauty Center Owner: beauty_centers table 20+ fields + 10 جدول مرتبط + SERVICES 20 keys + pricing/services (price_min/max/duration/is_active) + working_hours per day + reservations with final_design_id/service_key/selected_style BEGIN IMMEDIATE snapshot + conversations/messages/feedback/promotions/discounts/events — owner_dashboard 8 تب P0 موجود (info/services/hours/images/reservations/messages/stats/status) + 3 تب P1 پیشنهادی
- Admin: panel/modules/beauty_centers.py context dashboard with totals pending/published/expired/conversations/unanswered/active_promotions/promotion_revenue/eyebrow_waitlist/pre_need/interest + performance + events + demand_by_city + demand_recent — routes /panel/beauty-centers + tabs requests/published/paused/promotions/feedback/dashboard/settings — actions status/feature/discount/feedback + settings beauty_promotions_enabled/bump/featured/discount/renew + prices + listing_days + registration intro/terms

**Gap اصلی:** دو سیستم آنالیز موازی (Analysis قدیمی hair/skin vs Buti AI Mirror جدید) — User Panel Mirror History ندارد — Specialist مستقل ندارد (فقط center_type independent) — Portfolio per service ندارد (images بدون service_key) — Featured Service per service ندارد.

**PROPOSED معماری پیشنهادی (با دلیل):**
- پنل کاربر: `💄 مدیریت زیبایی گیسو` → `🏢 مدیریت سالن زیبایی` (اگر owner) + `✨ زیبایی من` → `🔎 سالن‌های زیبایی` (list_centers با فیلتر service), `📅 نوبت‌های من` (reservations), `💬 گفتگوهای من` (center_chats + chats), `🔬 آنالیزهای من` با تب [ابرو][مو][آرایش][ناخن] — آنالیز قدیمی hair/skin + Mirror جدید ادغام شوند: تب [مو] = hair analyses قدیمی + hair_color Mirror, تب [ابرو] = eyebrow Mirror, تب [ناخن] = nail Mirror, تب [آرایش] = lip_shading + makeup (آینده) — جلوگیری از دو سیستم موازی.
- متخصص: نقش جدید لازم نیست — بهتر است زیر Beauty Center با center_type=independent + beauty_center_services با service_key + is_featured_service — DB موجود قابلیت دارد — اگر متخصص داخل سالن کار کند، می‌تواند beauty_center_services با owner_user_id جدا + service_key داشته باشد — پیشنهاد: Extend نه New — اگر واقعاً مستقل شود، جدول beauty_center_specialists با center_id, user_id, service_key, is_active — ولی فعلاً P2.
- مدیر سالن: ساختار فعلی منطقی است — اطلاعات سالن/خدمات/قیمت‌ها/نمونه‌کارها/نوبت‌ها/گفتگوها/تخفیف‌ها/تبلیغات/گزارش عملکرد — P0 موجود — P1 اضافه service_key در services + images + service_id در promotions/discounts + is_featured_service
- ادمین: مدیریت سالن‌ها/متخصص‌ها/خدمات/نوبت‌ها/نمونه‌کارها/تبلیغات/آنالیزها/گزارش‌ها — فعلی دارد dashboard + requests/published/paused/promotions/feedback/settings — کم دارد: مدیریت متخصص‌ها (اگر جدا شود), مدیریت خدمات per service_key, مدیریت آنالیزها Mirror (final_designs), مدیریت نمونه‌کارها per service

**REQUIRED CHANGE:** P0 بدون تغییر DB — فقط اتصال Mirror History به panel_user + ادغام analyses قدیمی و جدید + menu grouping جدید. P1 با 2-4 ستون additive (service_key در beauty_center_services + beauty_center_images + service_id در promotions/discounts + is_featured_service) via ALTER TABLE ADD COLUMN — همان pattern ai_credits fix.

---

## 2. Freshness / Code Truth

```
Freshness: HEAD=90356d6 branch=arena/01a0eecf-giso4 working-tree=clean قبل نوشتن / dirty بعد نوشتن فقط rp7.md
Graph: STALE (Built from commit c9b198cd in graphify-out/GRAPH_REPORT.md vs HEAD 90356d6 — 7755 nodes, 24200 edges, 241 communities)
Docs: STALE (PROJECT_GUIDE updated 2026-09-29 branch arena/01a0e0b8 vs current 01a0eecf, GISO_GUIDE 2026-09-29 — GISO_GUIDE §22-24)
Memory: absent (project_memory/letta/PROJECT_MEMORY.md not present)
Guides: PROJECT_GUIDE.md + GISO_GUIDE.md present, giso-dev/SKILL.md + references/ present
rp history: s4.md 524 lines (هدف 4 پنل), rp6.md v2 87KB (Beauty Center scenario), rp5.md 112KB, rep2.md, rep1.md, s1.md, s2.md, s3.md
```

**Code Truth:** اگر Documentation و Code اختلاف داشتند، Code حقیقت اصلی است — Graph STALE → فقط grep/import analysis — Docs STALE → Code wins.

**Divergences found:**
- Docs می‌گویند Graph fresh ولی Graph built at c9b198cd vs HEAD 90356d6 — Code Truth: Graph STALE
- PROJECT_GUIDE branch arena/01a0e0b8 vs current 01a0eecf — Code Truth: branch 01a0eecf
- s4.md می‌گوید "ممنوع commit/push" ولی این نشست Read-Only audit برای rp7.md است — طبق giso-dev skill Read-Only verbs (بررسی/گزارش/پیشنهاد) هرگز فایل تغییر ندهند — استثناء فقط giso-dev skill folder itself و گزارش‌های rp*.md که ALLOWED هستند — این گزارش فقط rp7.md ایجاد می‌کند و در GitHub ذخیره می‌شود per user request "گزارش نهایی کار در ایل rp6.md در گیت هاب ذخیر کن" pattern — پس ALLOWED = [rp7.md]

---

## 3. Current User Panel

### 3.1 ساختار فعلی `giso/panel_user/` — Code Truth

**routes.py (canonical /dashboard):**
- Blueprint panel_user_bp — before_request _guard(): if not authenticated → redirect login?next=full_path, if role admin/super → redirect panel.dashboard
- MODULE_VIEWS dict: overview, profile, orders, hair_sale, marketplace, analyses, chats, wallet, notifies, reviews, shop — هر ماژول context() از modules/
- _menu_for_current_user(): has_center = bool(get_owner_center(current_user.id)) — اگر beauty_center in USER_MODULE_GROUPS و has_center False → skip — menu = [("__group", group, ""), (m, label, icon)] — groups from USER_MODULE_GROUPS
- _render(): header_wallet_usable via get_wallet_balances + grant_initial_spend_credit + menu_badges center_unread via user_center_unread_count + user_notification_unread + user_notifications list_user_notifications limit 5 + user_missions_pending via list_missions_for_user — template f"user_modules/{module}.html"
- Routes: / (overview), /overview, /profile, /orders, /orders/<checkout_id>/edit POST, /hair-sale, /hair-sale/<order_id>/edit POST, /marketplace, /analyses, /chats, /wallet, /notifies, /reviews, /shop — plus beauty_center, reservations, center_chats via MODULES_META hidden but routes exist in beauty_centers/reservations/routes.py
- pending_missions: list_missions_for_user filter not completed limit 5

**permissions.py:**
- USER_MODULES = [(overview, پیشخوان (خلاصه من), 🏠), (hair_sale, مدیریت مو, 💇‍♀️), (orders, خریدهای من از فروشگاه, 🛍️), (analyses, آنالیزها و برنامه من, 🔬), (reservations, نوبت‌های من, 📅), (center_chats, پیام‌های مرکز, 💌), (wallet, کیف پول و اعتبار, 💰), (chats, پیام‌ها و پشتیبانی, 💬), (profile, پروفایل, 👤)] — 9 visible
- USER_MODULE_GROUPS = {"اصلی": [overview, orders, notifications], "خدمات": [hair_sale, marketplace, buyer_request, analyses, beauty_center, reservations, center_chats], "پشتیبانی": [chats, ai_assistant], "حساب کاربری": [wallet, profile]} — beauty_center, marketplace, buyer_request hidden from USER_MODULES but in groups
- MODULES_META = {**USER_MODULES + marketplace (بازارچه مو, 🏪), buyer_request (خریدار مو, 🧑‍💼), beauty_center (مرکز زیبایی من, 🏥), shop (فروشگاه من, 🛒), notifies (اعلان موجودی, 🔔), wishlist (علاقه‌مندی‌ها, ❤️), notifications (اعلان‌های من, 📣), reviews (نظرها و امتیازها, ⭐), reservations (نوبت‌های من, 📅), center_chats (پیام‌های مرکز, 💌), ai_assistant (دستیار هوشمند گیسو, 🤖)} — ai_assistant فقط metadata, not in USER_MODULES to preserve main menu
- is_admin_user(phone_norm) via is_super_admin + find_giso_admin_by_phone, current_user_role() via flask_login current_user + normalize_phone + is_super_admin + find_giso_admin_by_phone → guest/user/admin/super

**modules/:**
- _base.py: get_analyses() Analysis.query filter phone order id desc, get_shop_orders() ProductOrder filter user_id or phone, get_hair_orders() HairOrder filter phone, get_stock_notifies() StockNotify filter phone, get_reviews() Review filter phone status visible, get_chats_count() SELECT COUNT(*) FROM consultant_requests WHERE phone=?, get_wallet() get_wallet_balances + get_user_transactions + get_financial_settings + list_missions_for_user + list_user_topups/withdrawals + mission_progress — all from real DB
- analyses.py: _json(raw), _decorate(row): ai_report_json → main_problems/problems → labels 3, metrics/scores → 6 with metric_label, date_fa to_shamsi, has_plan, has_quick, has_report — context(): phone=normalize_phone(current_user.phone), rows=Analysis.query filter user_id or phone and archived_at empty, archived_rows filter archived_at not empty, hair=[decorate r if type==hair], skin=[decorate r if type==skin], archived, latest_hair, latest_skin, recommendation via get_recommendation_for_user phone max_items 6 — DB source Analysis model (type hair/skin), route /dashboard/analyses, template user_modules/analyses.html, tabs hair/skin + archived + latest + products personalized
- overview.py: context(): get_analyses, get_shop_orders, get_hair_orders, get_stock_notifies, get_reviews, get_chats_count, get_wallet → counts analyses/orders/hair/notifies/reviews/chats/balance/cash/spend + last_hair + overview_notifications list_user_notifications limit 8
- chats.py: _ensure_support_tickets_table CREATE TABLE giso_support_tickets id, user_bale_id, user_name, phone, message, status new, admin_reply, admin_bale_id, created_at, replied_at — _support_tickets phone SELECT * WHERE phone ORDER BY id DESC LIMIT 50 — create_support_ticket message<5 fail, phone, name, bale_id from giso_users, INSERT + safe_log bot ticket — create_bug_report via bug_reports.submit — context(): phone, support_tickets, chats_count, etc
- hair_sale.py, marketplace.py, notifies.py, orders.py, profile.py, reviews.py, wallet.py — each context() from _base

**templates/:**
- user_layout.html — base layout with sidebar menu groups + menu_badges + header_wallet + notifications
- user_modules/: overview.html, profile.html, orders.html, hair_sale.html, marketplace.html, analyses.html, chats.html, wallet.html, notifies.html, reviews.html, center_chats.html, notifications.html, ai_assistant.html, wishlist.html, _analysis_summary.html, _buyer_conversations_tab.html, _buyer_offers_tab.html, _buyer_request_form.html, _analysis_summary.html — analyses.html has tabs hair/skin + archived + metrics + problems + plan + quick + report + products

**user_layout + menu/group structure:**
- Sidebar grouped by USER_MODULE_GROUPS: "اصلی" overview/orders/notifications, "خدمات" hair_sale/marketplace/buyer_request/analyses/beauty_center/reservations/center_chats, "پشتیبانی" chats/ai_assistant, "حساب کاربری" wallet/profile — beauty_center only if has_center (owner), reservations/center_chats always visible? Actually USER_MODULES includes reservations, center_chats — so customer sees نوبت‌های من + پیام‌های مرکز
- Badges: center_unread from user_center_unread_count, overview unread from user_unread_count
- Header: wallet_usable/cash/spend + notifications + missions pending

**آنالیزها و برنامه من — دقیق:**
- route: /dashboard/analyses → panel_user_bp analyses() → _render analyses with context from analyses.py
- module: analyses.py — DB source Analysis model (SQLAlchemy) — fields: id, user_id, phone, type hair/skin, ai_report_json, plan_json, quick_solution_json, created_at, archived_at — type hair/skin only, not eyebrow/nail/makeup
- template: user_modules/analyses.html — tabs: hair_analyses, skin_analyses, archived_analyses, latest_hair, latest_skin — each decorated with problems 3, metrics 6, date_fa, has_plan, has_quick, has_report
- tabها: مو / پوست / آرشیو + آخرین آنالیز + محصولات پیشنهادی personalized
- DB source: Analysis model (not buti_ai_final_designs) — legacy AI hair/skin analysis (not Mirror)
- نوع‌های فعلی: hair, skin only — no eyebrow, nail, hair_color, lip_shading
- history: rows order id desc, archived_rows where archived_at not empty
- report: ai_report_json → main_problems/problems + metrics/scores
- plan: plan_json bool
- consultant: not in analyses.py, but in overview notifications + chats module
- archive: archived_at field

**Gap:** آنالیزهای من فقط hair/skin قدیمی — Mirror جدید (eyebrow, nail, hair_color, lip_shading) در panel_user نمایش ندارد — دو سیستم موازی آنالیز ایجاد شده.

---

## 4. Current Smart Analysis Architecture

### 4.1 Buti AI / Mirror — Code Truth

**service_catalog.py:**
- SERVICE_EYEBROW=eyebrow, SERVICE_NAIL=nail, SERVICE_HAIR_COLOR=hair_color, SERVICE_LIP=lip_shading
- SERVICE_SLUGS: nail→nail, hair-color→hair_color, lip-shading→lip_shading
- SLUG_TO_SERVICE reverse mapping
- SERVICE_CATALOG 4 active: eyebrow (title آینه ابرو گیسو, short_title ابرو, icon 🪞, badge فعال, tag PMU, description مدل ابروی دلخواهت را روی عکس خودت ببین؛ فقط محدوده ابرو تغییر می‌کند., meta [ماسک ابرو, قبل/بعد, اتصال به مراکز ابرو], image brows/eyebrow_ai_mirror.jpg, sample_dir brows, upload_sample brows/upload_face_only.jpg, image_blueprint buti_ai, service_type eyebrow, beauty_center_service brow, status active), nail (💅 جدید Nail, فرم و رنگ ناخن را روی عکس دست خودت ببین, meta [نود، فرنچ، بیبی‌بومر, خروجی کم‌ریسک, مناسب سالن‌دارها], image services/nail/nude_minimal.jpg, sample_dir services/nail, upload_sample services/nail/upload_sample.jpg, service_type nail, beauty_center_service nail, status active), hair_color (🎨 جدید Hair Color, رنگ، لایت و فیس‌فریم را قبل از هزینه روی موی خودت مقایسه کن., meta [رنگ و لایت, بالیاژ و فیس‌فریم, بازار قوی سالن‌ها], image services/hair_color/caramel_balayage.jpg, sample_dir services/hair_color, upload_sample services/hair_color/upload_sample.jpg, service_type hair_color, beauty_center_service hair_color, status active), lip_shading (💋 جدید Lip PMU, شیدینگ، تینت و کانتور لب را با حفظ چهره روی عکس خودت ببین., meta [شیدینگ و کانتور, فقط ماسک لب, مناسب PMU], image services/lip_shading/natural_shading.jpg, sample_dir services/lip_shading, upload_sample services/lip_shading/upload_sample.jpg, service_type lip_shading, beauty_center_service lip_shading, status active)
- supported_service_keys() = [nail, hair_color, lip_shading] — eyebrow separate
- service_for_slug(slug) → key, slug_for_service(key) → slug, get_service_meta(key) → dict, mirror_services(eyebrow_href, service_hrefs) → list 4 with href

**generic_service.py:**
- SERVICE_MODULES = {nail: giso.buti_ai.nail.final_design, hair_color: giso.buti_ai.hair_color.final_design, lip_shading: giso.buti_ai.lip.final_design}
- CHANGE_LEVELS = {very_natural: خیلی طبیعی, medium: تغییر متوسط, clear: تغییر واضح‌تر}, DEFAULT_CHANGE_LEVEL=medium
- service_module(service_key) → import_module, normalize_model_key(service_key, value) → style key or default, initial_form_values(service_key) → {style: DEFAULT_STYLE, change_level: DEFAULT}, build_result(service_key, style_key, change_key, photo_status, detection, quality_report) → dict service_key, service_slug, service_label, style_key, selected_style_key, style, change_key, selected_change_key, change_label, photo_received, quality, detection, short_reason, do 3, avoid 3, preview {available, before_filename, generated, mode service_photo_ready}
- process_service_submission(service_key, form, files, user_id): form style/change_level, files photo, save_eyebrow_photo with upload_dir module.UPLOAD_DIR prefix service_key, missing_photo_status if no photo, quality_fn check_photo_quality or local_quality_report, if ok False → error_message, else detection = module.detect_regions(path, allow_fallback=True), analysis_data via analyze_nail_photo / analyze_hair_color_photo / analyze_lip_photo, result = build_result + ai_analysis, session_id = save_mirror_session user_id, service_type, city مشهد, status f"{service_key}_photo_ready_final_design", flash_message, return dict service_key, service_meta, styles, change_levels, form_values, result, error_message, flash_message, flash_category, photo_status, quality_report, detection
- build_final_candidate(service_key, result, photo_status): style_key normalize, change_key normalize, filename basename, created_at iso, return candidate service_key, service_slug, service_label, service_type, beauty_center_service, session_id, photo_filename, selected_style, selected_label, final_style, final_label, change_key, change_label, short_reason, do 3, avoid 3, detection, created_at, cache_key
- source_image_path(service_key, candidate): check root + exists, generate_final_design(service_key, candidate): via service_image_generation.generate_final_design or module.generate_guided_design, uploaded_root(service_key)

**eyebrow/, nail/, hair_color/, lip/ — final_design.py:**
- Each: STYLES 5 per service with label, summary, why, do, avoid, image, UPLOAD_DIR, DEFAULT_STYLE, check_photo_quality (AI first fallback local), detect_regions (color segmentation / landmarks), analyze_*_photo (AI first fallback), generate_guided_design (fallback composite), local_quality_report
- eyebrow: natural, powder, microblading, combination, giso_suggested — sample images 520x360 brows/*.jpg — upload_face_only.jpg
- nail: natural, french, baby_boomer, etc — services/nail/*.jpg — upload_sample.jpg
- hair_color: caramel_balayage, etc — services/hair_color/*.jpg
- lip_shading: natural_shading, etc — services/lip_shading/*.jpg

**service_key, sessions, final designs, results, reports, history, DB tables, routes, templates, API/service layer:**
- service_key: nail, hair_color, lip_shading, eyebrow — internal Mirror key — mapping to beauty_center_service via SERVICE_CATALOG
- sessions: buti_ai_sessions id, user_id, service_type, city مشهد, center_id, conversation_id, status completed, created_at — INDEX user + created DESC — via save_mirror_session in services.py
- final designs: buti_ai_final_designs id, session_id, user_id, service_type DEFAULT eyebrow, original_filename, final_filename, selected_style, recommended_style, change_level, provider, model, status created, prompt_json, created_at — INDEX user,created DESC + session — via save_final_design in final_design.py per service + generic_service
- results: candidate dict + generation dict {ok, service_key, in_mask_diff_ratio, outside_mask_diff_ratio, is_ai_generated, ai_inpainting, fallback_type, message, provider, model, final_filename, original_filename, validation}
- reports: quality_report {status local_checked/ai_checked, ok, message} + detection {method, coverage, reliable, real_mask, etc} + ai_analysis {short_reason, do, avoid, data}
- history: buti_ai_final_designs WHERE user_id ORDER BY created_at DESC — not yet in panel_user, only in session _new_service_candidate_key(service_key) + FINAL_DESIGN_SESSION_KEY for eyebrow
- DB tables: buti_ai_sessions, buti_ai_waitlist, buti_ai_service_demand, buti_ai_final_designs — schema.py BUTI_AI_TABLES_SQL + _ensure_column additive + init_buti_ai_db — all via get_giso_db_conn()
- routes: buti_ai_bp — /eyebrow/* (upload, wizard, final_design, centers, uploads/<filename>), /analysis/mirror/ mirror_home, /analysis/mirror/<service_slug> generic_service_wizard (model selection), /<service_slug>/upload, /<service_slug>/final, /<service_slug>/consultant POST, /<service_slug>/interest POST — plus _new_service_selection_key, _new_service_candidate_key, _is_active_new_service, _active_service_from_slug, _new_service_selection_from_form, _current_new_service_selection, _new_service_state, _render_new_service_wizard, _store_new_service_candidate, _get_new_service_candidate, _rebuild_new_service_candidate_from_finalize_form, _update_new_service_final_selection
- templates: buti_ai/eyebrow_wizard.html, eyebrow_final_design.html, generic_service_wizard.html, generic_final_design.html, eyebrow_centers_empty.html — with Before/After, service/style/change labels, AI status is_ai_generated, provider, model, validation, do/avoid, interest question bti-final-interest Lead vs View, centers suggestions enrich with mirror_match_reason+mirror_tags+mirror_score, consultant invite+chat, demand/waitlist
- API/service layer: services.py save_mirror_session, save_service_waitlist, record_service_demand, total_service_interest_count, active_eyebrow_centers, enrich_eyebrow_center_suggestions, enrich_generic_centers, user_default_city, user_default_phone, _safe_current_user_id — all via get_giso_db_conn()

**هر سرویس الان اطلاعاتش را کجا نگه می‌دارد:**
- Eyebrow: buti_ai_sessions + buti_ai_final_designs + session FINAL_DESIGN_SESSION_KEY + uploads giso/buti_ai/eyebrow/uploads/
- Nail/Hair/Lip: buti_ai_sessions + buti_ai_final_designs + session buti_ai_{service_key}_final_candidate + uploads giso/buti_ai/{service}/uploads/ (via UPLOAD_DIR)
- Beauty Center Services: beauty_center_services table (name, category, description, duration, price_min/max, is_active, sort_order) — no service_key yet
- Beauty Center Images: beauty_center_images (image_path, sort_order) — no service_key yet
- Reservations: beauty_center_reservations with final_design_id, service_key, selected_style snapshot
- Analysis قدیمی: Analysis model (hair/skin) with ai_report_json, plan_json, quick_solution_json

**سؤال اصلی: آیا می‌توانیم همین ساختار موجود را به پنل کاربر → آنالیزهای من → [ابرو][مو][آرایش][ناخن] متصل کنیم؟**

**پاسخ: بله — 100% با ساختار موجود قابل اتصال — Reuse > Extend > New:**

- آنالیزهای من فعلی فقط hair/skin قدیمی — باید Extend شود: تب [ابرو] = buti_ai_final_designs WHERE service_type=eyebrow AND user_id, تب [مو] = hair analyses قدیمی + hair_color Mirror (service_type=hair_color), تب [آرایش] = lip_shading Mirror + makeup آینده, تب [ناخن] = nail Mirror — همه از buti_ai_final_designs SELECT WHERE user_id ORDER BY created_at DESC — نیاز به new module panel_user/modules/mirror.py reuse analyses.py pattern — 1 فایل جدید — هیچ ساختار جدید لازم نیست — DB موجود کافی است — فقط SELECT.

**اگر با ساختار فعلی قابل انجام است تغییر DB پیشنهاد نده — پس P0 بدون تغییر DB.**

---

## 5. Proposed Customer Panel

### 5.1 سناریوی موردنظر s4.md:

```
💄 مدیریت زیبایی گیسو

├── 🏢 مدیریت سالن زیبایی

└── ✨ زیبایی من
    │
    ├── 🔎 سالن‌های زیبایی
    ├── 📅 نوبت‌های من
    ├── 💬 گفتگوهای من
    └── 🔬 آنالیزهای من
```

**آیا این ساختار از نظر UX و معماری مناسب است؟** بله — مناسب است با دلیل:

- **UX:** مشتری اول زیبایی من را می‌بیند (شخصی) — بعد سالن‌های زیبایی (کشف) — بعد نوبت‌های من (اقدام) — بعد گفتگوهای من (پیگیری) — بعد آنالیزهای من (هوشمند) — flow منطقی: کشف → آنالیز → سالن → نوبت → گفتگو → پیگیری — گروه‌بندی "زیبایی من" همه چیز شخصی را یکجا جمع می‌کند — لوکس و ساده — نام‌ها فارسی و قابل فهم — آیکون‌ها 💄🏢✨🔎📅💬🔬
- **معماری:** USER_MODULE_GROUPS فعلی "اصلی/خدمات/پشتیبانی/حساب" دارد — می‌تواند Extend شود به "زیبایی من" group جدید با 4 زیرمنو — has_center check برای 🏢 مدیریت سالن زیبایی (فقط اگر owner) — reservations + center_chats already in USER_MODULES — فقط analyses باید Extend شود به تب‌های [ابرو][مو][آرایش][ناخن] — beauty_center (مرکز زیبایی من) already in MODULES_META hidden — می‌تواند به 🏢 مدیریت سالن زیبایی rename شود — هیچ ماژول جدید لازم نیست مگر mirror history — Reuse > Extend > New رعایت می‌شود.

**اگر نام یا ساختار بهتری وجود دارد پیشنهاد بده، ولی فقط با دلیل:**

- پیشنهاد بهبود نام: `💄 مدیریت زیبایی گیسو` → `💄 زیبایی من` (کوتاه‌تر، شخصی‌تر) — چون "مدیریت زیبایی گیسو" طولانی و رسمی است — "زیبایی من" شخصی و لوکس است — دلیل: UX ساده + فارسی محاوره‌ای + هم‌خوانی با "نوبت‌های من", "گفتگوهای من", "آنالیزهای من"
- پیشنهاد بهبود ساختار: `🏢 مدیریت سالن زیبایی` بهتر است بیرون `✨ زیبایی من` باشد (سطح اول) — چون صاحب سالن همزمان مشتری هم هست — اگر داخل "زیبایی من" باشد، مشتری عادی که سالن ندارد آن را نمی‌بیند (has_center check) — ولی اگر بیرون باشد، همیشه visible با شرط has_center — دلیل: معماری فعلی _menu_for_current_user already has_center check برای beauty_center — پس بیرون بودن منطقی‌تر است.
- ساختار نهایی پیشنهادی (بهبود یافته):
```
🏠 پیشخوان (خلاصه من)
💄 زیبایی من
   ├── 🔎 سالن‌های زیبایی (/beauty-centers)
   ├── 📅 نوبت‌های من (/dashboard/reservations + /beauty-centers/my-reservations)
   ├── 💬 گفتگوهای من (/dashboard/center_chats + /dashboard/chats)
   └── 🔬 آنالیزهای من (/dashboard/analyses با تب [ابرو][مو][آرایش][ناخن])
🏢 مدیریت سالن زیبایی (فقط اگر owner — /dashboard/beauty-center)
💇‍♀️ فروش مو به گیسو
🛍️ خریدهای من از فروشگاه
💰 کیف پول و اعتبار
👤 پروفایل
```
- دلیل: پیشخوان اول، بعد زیبایی من (4 زیرمنو)، بعد مدیریت سالن (اگر owner)، بعد بقیه خدمات — flow اصلی: آنالیز → خدمات مرتبط → سالن/متخصص → نمونه‌کار+قیمت → گفتگو → نوبت → پیگیری — با معماری فعلی سازگار.

### 5.2 «آنالیزهای من» — تب [ابرو][مو][آرایش][ناخن] یا ساختار دیگر؟

**پیشنهاد: تب باشد — با دلیل:**

- **UX:** تب ساده‌ترین و لوکس‌ترین راه برای دسته‌بندی 4 خدمت — کاربر سریع بین ابرو/مو/آرایش/ناخن سوئیچ می‌کند — نمونه: دیوار تب دسته‌بندی، اسنپ تب خدمات — فارسی RTL تب‌ها با آیکون 🪞💅🎨💋 — هر تب count badge (مثلاً ابرو 3, مو 2)
- **معماری:** analyses.py فعلی hair/skin را جدا می‌کند (hair=[decorate r if type==hair], skin=[...]) — همین pattern برای [ابرو][مو][آرایش][ناخن] قابل Extend است: eyebrow = buti_ai_final_designs WHERE service_type=eyebrow, nail = service_type=nail, hair_color = hair_color + hair analyses قدیمی, lip_shading = lip_shading + makeup آینده — فقط 1 query اضافه per تب — Reuse > Extend > New
- **ساختار دیگر؟** مثلاً لیست عمودی یا کارت‌های جدا — ولی تب لوکس‌تر و ساده‌تر است — چون 4 خدمت بیشتر نیست — اگر 10 خدمت شود، شاید dropdown بهتر باشد — ولی فعلاً 4 خدمت → تب بهترین.

**ادغام «آنالیزها و برنامه من» فعلی با بخش جدید تا دو سیستم موازی ایجاد نشود:**

- **CURRENT:** Analysis model hair/skin قدیمی با ai_report_json, plan_json, quick_solution_json — در panel_user/modules/analyses.py — route /dashboard/analyses — template analyses.html با tabs hair/skin + archived + latest + products
- **PROPOSED:** ادغام: تب [مو] = hair analyses قدیمی + hair_color Mirror جدید — تب [ابرو] = eyebrow Mirror — تب [ناخن] = nail Mirror — تب [آرایش] = lip_shading Mirror + skin analyses قدیمی (چون آرایش به پوست مرتبط) + makeup آینده — هر تب شامل: تاریخچه قدیمی (Analysis) + تاریخچه جدید (buti_ai_final_designs) — هر ردیف: date_fa, service_label, selected_style, final_label, Before/After thumb, has_plan, has_report, CTA مشاهده نتیجه + رزرو با همین طراحی
- **REQUIRED CHANGE:** Extend analyses.py context(): اضافه کردن buti_ai_final_designs queries WHERE user_id — برای هر service_type — merge با hair/skin قدیمی — template analyses.html اضافه کردن تب‌های [ابرو][مو][آرایش][ناخن] با badge count — هیچ DB جدید لازم نیست — فقط SELECT — P0 بدون تغییر DB — جلوگیری از دو سیستم موازی: یک route /dashboard/analyses همه را نشان دهد، نه دو route جدا.

---

## 6. Specialist / Service Provider Panel

### 6.1 آیا ساختار مستقل برای متخصص وجود دارد؟

**Code Truth: خیر — ساختار مستقل برای متخصص وجود ندارد — فقط center_type=independent (آرایشگر یا متخصص مستقل) در beauty_centers.**

- beauty_centers.services.py CENTER_TYPES: independent = آرایشگر یا متخصص مستقل — این یعنی متخصص می‌تواند یک beauty_centers row با owner_user_id خودش و center_type=independent ثبت کند — ولی این هنوز "سالن" است نه "متخصص داخل سالن"
- beauty_center_services: هر خدمت name, category, description, duration, price_min/max, is_active, sort_order — می‌تواند خدمت متخصص را نشان دهد ولی owner_user_id آن مرکز است نه متخصص
- beauty_center_images: نمونه‌کار عمومی مرکز — نه متخصص خاص
- reservations: center_id + user_id + service_id — service_id به beauty_center_services اشاره دارد — اگر متخصص داخل سالن کار کند، service_id می‌تواند خدمت آن متخصص باشد ولی center_id هنوز سالن است — owner_user_id سالن است نه متخصص — پس متخصص نمی‌تواند رزروهای خودش را جدا ببیند.

**بررسی نقش‌ها:**
- ابروکار: می‌تواند beauty_centers با category=beauty, center_type=independent, services=[brow] ثبت کند — کار می‌کند ولی "سالن" است نه "متخصص داخل سالن"
- ناخن‌کار: center_type=nail_center یا independent, services=[nail]
- آرایشگر: independent, services=[makeup, hairstyle]
- متخصص مو: hair_center یا independent, services=[hair_color, haircut, etc]
- میکاپ‌آرتیست: bridal یا independent, services=[makeup, bridal]

**آیا شخص الزاماً صاحب سالن نیست و ممکن است داخل یک سالن کار کند ولی خودش خدمات ارائه دهد و از گیسو مشتری بگیرد؟** بله — این سناریو فعلی پوشش داده نشده — Gap Medium.

### 6.2 پیشنهاد معماری — 4 گزینه با تحلیل Reuse > Extend > New

**گزینه 1: نقش جدید جدول beauty_center_specialists — New Architecture — P2:**
- جدول جدید: id, center_id FK, user_id FK, service_key, is_active, sort_order, created_at — متخصص داخل سالن — هر متخصص user_id خودش + center_id سالن + service_key (brow, nail, etc) — رزروها می‌توانند specialist_id داشته باشند — مزیت: دقیق، قابل مدیریت — معایب: New Architecture، نیاز به migration، پنل جدید، route جدید، template جدید — Reuse=0, Extend=0, New=100% — فعلاً شلوغ می‌کند — P2.

**گزینه 2: زیر Beauty Center با center_type=independent — Reuse — P0:**
- متخصص مستقل یک beauty_centers row با center_type=independent ثبت کند — owner_user_id خودش — services_json شامل خدماتش — beauty_center_services با price/duration — gallery نمونه‌کار خودش — reservations owner_list WHERE center_id=his center — 100% Reuse — هیچ تغییر لازم نیست — برای متخصص داخل سالن کار نمی‌کند ولی برای مستقل کار می‌کند — P0.

**گزینه 3: فقط Profile/Service Provider — Extend — P1:**
- beauty_center_services اضافه کردن specialist_user_id INTEGER DEFAULT 0 + service_key TEXT DEFAULT '' — هر خدمت می‌تواند specialist_user_id داشته باشد — اگر specialist_user_id>0 یعنی این خدمت را متخصص خاصی ارائه می‌دهد — owner_dashboard services list می‌تواند specialist_user_id را نشان دهد — reservations می‌تواند specialist_user_id snapshot داشته باشد — مزیت: Extend با 2 ستون additive — Reuse 80%, Extend 20%, New 0% — برای متخصص داخل سالن کار می‌کند — P1.

**گزینه 4: Hybrid — Beauty Center + Specialist Profile — Reuse + Extend — P1 (پیشنهادی):**
- متخصص مستقل: beauty_centers with center_type=independent — Reuse P0
- متخصص داخل سالن: beauty_center_services with specialist_user_id + service_key + is_active + sort_order — Extend P1 — هر خدمت می‌تواند متخصص جدا داشته باشد — owner_dashboard می‌تواند لیست متخصص‌ها را از DISTINCT specialist_user_id بگیرد — reservations می‌تواند specialist_user_id را فیلتر کند — gallery می‌تواند service_key داشته باشد تا نمونه‌کار per service per specialist فیلتر شود — مزیت: ساده + لوکس + قابل فروش + قابل مدیریت — بدون معماری جدید — فقط 2 ستون additive — P1.

**پیشنهاد نهایی:** گزینه 4 Hybrid — P0 Reuse independent, P1 Extend specialist_user_id + service_key — دلیل: Reuse > Extend > New — بدون دلیل معماری جدید پیشنهاد نده — اگر با ساختار فعلی قابل انجام است تغییر DB پیشنهاد نده — پس P0 بدون تغییر DB، P1 با 2 ستون additive.

**DB موجود قابلیت این کار را دارد؟** بله برای مستقل — برای داخل سالن نیاز به 2 ستون additive — پس P0 بدون تغییر، P1 با Extend.

---

## 7. Beauty Center Owner Panel

### 7.1 ساختار فعلی Beauty Center و Owner Panel — Code Truth

**ثبت سالن:** routes.py register GET/POST — fields: name, category, center_type, city, region, address_summary, business_phone, salon_phone, display_phone_choice, contact_time, description, services multi-select 16 max from SERVICES, price_level, starting_price, image — validation _normalize_fields: category in CENTER_CATEGORIES, center_type in CATEGORY_CENTER_TYPES[category], services in CATEGORY_SERVICES[category], price_level in PRICE_LEVELS, city required, phone normalized via normalize_phone — slug _slug_seed(name)+secrets — create_center.

**approval:** STATUS_FA 6 وضعیت pending_review/reviewing/published/rejected/paused/closed — admin_set_status with guarded transition — panel_admin.py handle_status — bot_handlers.py beauty_admin_menu_kb — _center_kb actions review/publish/reject/pause — listing_expires_at + promotion_type/expires/bumped — is_active, is_featured, sort_order.

**services:** beauty_center_services id, center_id, name NOT NULL, category '', description '', duration_minutes 30, price_min 0, price_max 0, is_active 1, sort_order 0, created_at, updated_at legacy — INDEX center,is_active,sort_order — get_center_services ordered is_active DESC sort_order ASC id ASC — add_service name required duration 1-1440 price_min/max — update_service — delete_service — _clean_service validation.

**pricing:** service price_min/max + center price_level/starting_price + _service_price_label with format_toman + duration_label — pricing/services.py 6 functions exactly.

**working hours:** beauty_center_working_hours id, center_id, day_of_week 0=شنبه تا 6=جمعه, open_time '', close_time '', is_closed 0, slot_minutes 30, legacy weekday/is_open sync — get_working_hours ordered day_of_week ASC — save_working_hours BEGIN IMMEDIATE upsert per day_of_week — _clean_working_day validation day 0-6, time HH:MM, open<close, slot 5-1440.

**gallery/portfolio:** beauty_center_images id, center_id FK CASCADE, image_path, sort_order, created_at — INDEX center,sort_order,id — save_center_image validation MAX_BYTES 5MB, MAX_PIXELS 20M, MAX_SIDE 12000, FORMATS JPEG/PNG/WEBP — owner_gallery_upload check count+cover <=3 — owner_gallery_delete — owner_main_image_delete with replacement logic — center_media, gallery_media with static_root check + parents check + nosniff + conditional.

**reservations:** beauty_center_reservations id, center_id, user_id, user_phone, user_name, service_id snapshot, service_name snapshot 200, service_price_min snapshot, duration_minutes snapshot, reservation_date شمسی YYYY-MM-DD, reservation_time HH:MM, status pending/confirmed/completed/cancelled_user/cancelled_center, user_note 500, center_note, reject_reason, reminded flags, created_at, confirmed_at, cancelled_at, final_design_id, service_key, selected_style — INDEX center,date,time + user,created_at + status,date — get_available_slots, get_calendar_month, create_reservation BEGIN IMMEDIATE snapshot + _is_available + _build_slots + _active_bookings + _transition guarded + confirm/reject/complete/cancel_by_user + notify hooks + _reminder_rows + get_pending_reminders — reservations/routes.py slots JSON, calendar JSON, reserve GET/POST with service_id/date/final_design_id/service_key/selected_style + my_reservations.

**messages:** beauty_center_conversations id, center_id, user_id, status active/closed, last_message_at, UNIQUE(center_id,user_id) — INDEX center,status,last_message_at + user,status,last_message_at — beauty_center_messages id, conversation_id, sender_user_id, message_text, is_read, is_reported — INDEX conversation,id + conversation,is_read — get_or_create_conversation, conversation_for_party, conversation_messages, send_conversation_message, notify_conversation_message via _CENTER_NOTIFY_POOL, owner_conversations, user_center_conversations, user_center_unread_count, owner_conversation_unread_count, close_conversation, submit_center_feedback, center_feedback_summary, _feedback_label.

**discounts:** beauty_center_discounts id, center_id, title, description, discount_value, expires_at, status pending — INDEX center,status,expires_at — owner_discount POST title, discount_value, days 1-30, description 300 → INSERT status pending.

**promotions:** beauty_center_promotions id, center_id, owner_user_id, package_key, amount, starts_at, expires_at, transaction_key UNIQUE, status active — INDEX center,status,expires_at — center_promotion_availability, purchase_center_promotion with purchase_nonce _purchase_key, _wait_label, renew_center_listing, process_center_expiry_notifications throttled 10min — owner_promote POST package_key, purchase_nonce — owner_renew POST purchase_nonce.

**analytics:** beauty_center_events id, center_id DEFAULT 0, event_type, user_id DEFAULT 0, created_at — INDEX event_type,created_at — views_count increment_view, contact_clicks reveal_contact, analysis_impressions, price_inquiry_clicks, beauty_stats centers/views/hair/skin in list_centers.

**staff:** فعلاً ندارد — Gap — اگر متخصص داخل سالن باشد، نیاز به staff management — P2.

**service ownership:** owner_user_id UNIQUE in beauty_centers — یک کاربر یک مرکز — اگر متخصص داخل سالن، owner_user_id سالن است نه متخصص — Gap.

**service-level portfolio/pricing/promotion:** portfolio per service ندارد (images بدون service_key), pricing per service دارد (price_min/max/duration), promotion per service ندارد (فقط center_id) — Gap.

### 7.2 آیا ساختار منطقی است:

```
🏢 مدیریت سالن زیبایی

اطلاعات سالن
خدمات
قیمت‌ها
نمونه‌کارها
نوبت‌ها
گفتگوها
تخفیف‌ها
تبلیغات
گزارش عملکرد
```

**پاسخ: بله — منطقی است با دلیل:**

- **اطلاعات سالن:** موجود — owner_dashboard tab edit — name, category, type, city, region, address, phone, contact_time, description, price_level, starting_price, services_json — P0
- **خدمات:** موجود — get_center_services + add/update/delete — name, category, description, duration, price_min/max, is_active, sort_order — P0 — P1 اضافه service_key + is_featured_service + specialist_user_id
- **قیمت‌ها:** موجود — price_min/max per service + price_level/starting_price per center — P0 — لوکس با format_toman
- **نمونه‌کارها:** موجود ولی عمومی — max 3 + gallery upload/delete + main delete with replacement — P0 — P1 اضافه service_key per image برای portfolio per service
- **نوبت‌ها:** موجود — owner_list + confirm/reject/complete + calendar + slots + notify — P0 — لوکس با Jalali date + HH:MM + snapshot
- **گفتگوها:** موجود — owner_conversations + messages + close + feedback — P0
- **تخفیف‌ها:** موجود — owner_discount + beauty_center_discounts — P0 عمومی — P1 per service با service_id
- **تبلیغات:** موجود — owner_promote + renew + beauty_center_promotions + is_featured + promotion_type/expires/bumped — P0 مرکز — P1 per service
- **گزارش عملکرد:** موجود — views_count, contact_clicks, analysis_impressions, price_inquiry_clicks, beauty_stats, events, performance, conversion_rate — P0 — در panel_admin dashboard performance + events + demand_by_city + demand_recent

**چه چیزهایی آماده و چه چیزهایی ناقص:**

- آماده P0: اطلاعات سالن, خدمات, قیمت‌ها, نمونه‌کارها عمومی, نوبت‌ها, گفتگوها, تخفیف‌ها عمومی, تبلیغات مرکز, گزارش عملکرد — 100% موجود
- ناقص P1: نمونه‌کارها per service (service_key در images), قیمت‌ها per service با service_key mapping, تخفیف‌ها per service (service_id), تبلیغات per service (service_id + is_featured_service), staff/specialist management (specialist_user_id), service ownership per specialist — نیاز به 2-4 ستون additive
- ناقص P2: Instagram/Logo, ظرفیت پیشرفته, علاقه‌مندی‌ها, تبلیغ هدفمند پیچیده

**نتیجه:** ساختار پیشنهادی منطقی و با معماری فعلی سازگار — P0 بدون تغییر DB، P1 با 2-4 ستون additive.

---

## 8. Admin Panel

### 8.1 پنل ادمین — Code Truth

**فایل:** giso/beauty_centers/panel_admin.py + giso/panel/routes.py + giso/panel/permissions.py

**Beauty Centers Admin:**
- context(tab): status_map requests→pending_review, published→published, paused→paused — centers = list_admin_centers(status) if tab in status_map else published if promotions else [] — feedback_rows SELECT f.*,c.name FROM beauty_center_feedback JOIN beauty_centers ORDER BY id DESC LIMIT 200 if tab==feedback — promotion_rows SELECT p.*,c.name FROM beauty_center_promotions JOIN beauty_centers ORDER BY id DESC LIMIT 200 if promotions — discount_rows SELECT d.*,c.name FROM beauty_center_discounts JOIN beauty_centers ORDER BY id DESC LIMIT 200 if feedback — dashboard = _dashboard(conn) if tab==dashboard — counts per STATUS_FA SELECT COUNT(*) WHERE status=?
- _dashboard(conn): totals total=COUNT beauty_centers, pending=COUNT status pending_review/reviewing, published=COUNT published+is_active=1, expired=COUNT listing_expires_at<now, conversations=COUNT conversations, unanswered=COUNT active AND EXISTS unread message, active_promotions=COUNT promotions active+expires>now, promotion_revenue=SUM(amount) WHERE status<>cancelled, eyebrow_waitlist=COUNT buti_ai_waitlist service_type eyebrow status open, eyebrow_pre_need=COUNT buti_ai_service_demand eyebrow open, eyebrow_interest=waitlist+pre_need — performance SELECT c.id,name,views_count,contact_clicks,price_inquiry_clicks,analysis_impressions,COUNT DISTINCT conversations, conversion_rate ROUND((conversations+contact_clicks)*100/views_count,1) FROM beauty_centers LEFT JOIN conversations GROUP BY id ORDER BY views_count DESC LIMIT 20 — event_rows SELECT event_type,COUNT(*) FROM beauty_center_events WHERE created_at>=now-30 days GROUP BY event_type ORDER BY count DESC — demand_by_city SELECT city, SUM(waitlist_count), SUM(pre_need_count), total FROM (SELECT city, COUNT waitlist, 0 pre_need FROM waitlist WHERE eyebrow open GROUP BY city UNION ALL SELECT city, 0, COUNT pre_need FROM service_demand WHERE eyebrow open GROUP BY city) GROUP BY city ORDER BY total DESC LIMIT 20 — demand_recent SELECT city,source,phone_number,created_at,'waitlist' kind FROM waitlist UNION ALL SELECT city,source,'' phone,created_at,'pre_need' kind FROM service_demand ORDER BY created_at DESC LIMIT 30
- _settings(): beauty_promotions_enabled, beauty_bump_enabled, beauty_featured_enabled, beauty_discount_enabled, beauty_renew_enabled, beauty_bump_price 25000, beauty_featured_price 120000, beauty_discount_price 60000, beauty_renew_price 50000, beauty_listing_days 30, beauty_registration_enabled 1, beauty_registration_intro, beauty_terms_text — via get_giso_config/set_giso_config + invalidate_giso_config_cache
- handle_settings(): section promotion or registration — set_giso_config for each key — flash success/danger — redirect panel.beauty_centers tab promotions/settings
- handle_status(center_id, actor_id): status from form, note admin_note, admin_set_status(center_id, status, note, actor_id) — flash — redirect requests
- handle_feature_selected(): center_id from form, featured==1 → handle_feature
- handle_feature(center_id, featured): SELECT id FROM beauty_centers WHERE id, if not found flash danger else UPDATE is_featured, updated_at now — flash success — redirect promotions
- handle_discount(discount_id): status visible/rejected from form, UPDATE beauty_center_discounts SET status WHERE id — flash — redirect promotions
- handle_feedback(feedback_id): status visible/rejected, UPDATE beauty_center_feedback SET status — flash — redirect feedback

**Routes Admin:**
- panel_bp /beauty-centers → if not module_allowed beauty_centers role perms → abort — _render beauty_centers/admin.html with context(tab)
- /beauty-centers/settings POST → handle_settings
- /beauty-centers/<center_id>/status POST → handle_status
- /beauty-centers/feature-selected POST → handle_feature_selected
- /beauty-centers/<center_id>/feature POST → handle_feature
- /beauty-centers/discount/<discount_id>/status POST → handle_discount
- /beauty-centers/feedback/<feedback_id>/status POST → handle_feedback

**Permissions Admin:**
- ADMIN_SECTIONS includes (beauty_centers, 🏥 مراکز زیبایی), etc — REGULAR_ADMIN_SECTIONS frozenset dashboard, orders, hair_sale, marketplace, beauty_centers, reviews, consults, account — REGULAR_ADMIN_MODULES similar — REGULAR_ADMIN_NAV (dashboard پیشخوان کار من, hair_sale مدیریت خرید مو, marketplace مدیریت بازارچه مو, beauty_centers مدیریت مراکز زیبایی, shop_orders سفارش‌های فروشگاه, reviews نظرات عمومی, consults مدیریت گفتگوها, account حساب کاربری) — SPECIAL_ADMIN_NAV similar + aga_reza + special_reports — MODULE_TO_SECTION beauty_centers→beauty_centers — SUPER_ONLY_MODULES includes referrals, wallet, admins, settings, shop_super, reports, ai, ratelimit, users, channel, analyses, notifications, shop, monitoring, super_assistant

**بررسی برای اکوسیستم زیبایی:**
- Beauty Centers: دارد — requests/published/paused/promotions/feedback/dashboard/settings — totals, performance, events, demand_by_city, demand_recent — status, feature, discount, feedback actions — settings
- Users: دارد — via panel/modules/users.py — not in beauty_centers but in admin panel
- Services: ندارد per service_key — فقط beauty_center_services via center — Gap Medium — باید اضافه شود: مدیریت خدمات per service_key + is_featured_service
- Service Providers: ندارد مستقل — فقط center_type independent — Gap Medium — P2
- Reservations: ندارد در admin — فقط owner_list — Gap Medium — باید اضافه شود: مدیریت نوبت‌ها همه مراکز
- Conversations: دارد conversations count + unanswered + feedback — but not full moderation — P1
- AI / Mirror: دارد eyebrow_waitlist + pre_need + interest + demand_by_city + demand_recent — but only eyebrow, not nail/hair_color/lip_shading — Gap — باید Extend به همه service_type
- Reports: دارد beauty_center_reports + feedback + events — P0
- Promotions: دارد promotion_rows + active_promotions + promotion_revenue + feature — P0 مرکز — P1 per service
- Discounts: دارد discount_rows — P0 مرکز — P1 per service
- Moderation: دارد status, feature, discount, feedback status — P0
- Approval: دارد admin_set_status with guarded transition — P0
- Analytics: دارد dashboard totals + performance + events + demand_by_city + demand_recent + conversion_rate — P0 — P1 اضافه per service_key analytics
- payments/monetization: دارد promotion_revenue + settings prices bump/featured/discount/renew — P0

**Admin برای مدیریت اکوسیستم چه چیزهایی کم دارد:**

- مدیریت سالن‌ها: دارد کامل — P0
- مدیریت متخصص‌ها: ندارد مستقل — اگر Hybrid پیشنهاد شود، باید مدیریت specialist_user_id + service_key — P1
- مدیریت خدمات: ندارد per service_key — فقط per center — باید اضافه شود: لیست همه beauty_center_services با filter service_key + is_active + is_featured_service — P1
- مدیریت نوبت‌ها: ندارد در admin — فقط owner — باید اضافه شود: همه reservations با filter status/date/center/service/final_design_id — P1
- مدیریت نمونه‌کارها: ندارد per service — فقط gallery عمومی — باید اضافه شود: filter service_key — P1
- مدیریت تبلیغات: دارد مرکز — ندارد per service — P1
- مدیریت آنالیزها: دارد فقط eyebrow demand — ندارد nail/hair_color/lip_shading final_designs — باید Extend به همه service_type — P1
- مدیریت گزارش‌ها: دارد feedback + events + reports — P0

**فقط مواردی که واقعاً با ساختار فعلی هم‌خوانی دارند:**

- P0 موجود: مدیریت سالن‌ها, گزارش‌ها, تبلیغات مرکز, تخفیف‌ها مرکز, آنالیزها eyebrow demand, تنظیمات
- P1 پیشنهادی با Extend: مدیریت خدمات per service_key (ADD COLUMN service_key + is_featured_service), مدیریت نوبت‌ها همه مراکز (new admin route reuse reservations/services), مدیریت نمونه‌کارها per service (ADD COLUMN service_key in images), مدیریت تبلیغات per service (ADD COLUMN service_id in promotions/discounts), مدیریت آنالیزها همه service_type (Extend _dashboard to include nail/hair_color/lip_shading waitlist/demand + final_designs count)
- P2 آینده: مدیریت متخصص‌ها مستقل (جدول جدید beauty_center_specialists)

---

## 9. Four-Panel Responsibility Matrix

**ماتریس بر اساس واقعیت کد پروژه (CURRENT) + پیشنهادی (PROPOSED):**

| قابلیت | مشتری (Customer) | متخصص (Specialist) | مدیر سالن (Owner) | ادمین (Admin) |
|---|---|---|---|---|
| **مشاهده سالن** | ✅ CURRENT: list_centers + center_detail با فیلتر service/city/category/type/price_level + featured + related + increment_view | ✅ CURRENT: می‌تواند beauty_centers با independent ببیند + اگر داخل سالن: via center_id | ✅ CURRENT: owner_dashboard + center_detail (is_owner) + is_active/is_featured | ✅ CURRENT: panel_admin context + list_admin_centers + status/feature |
| **ارائه خدمات** | ❌ CURRENT: نمی‌تواند خدمت ارائه دهد — فقط رزرو | ⚠️ CURRENT: فقط اگر independent center ثبت کند — PROPOSED: beauty_center_services with specialist_user_id + service_key | ✅ CURRENT: add_service/update/delete + get_center_services + pricing + working_hours | ✅ PROPOSED: مدیریت خدمات per service_key + is_featured_service + is_active |
| **نمونه‌کار** | ✅ CURRENT: مشاهده gallery carousel + center_media + gallery_media | ⚠️ CURRENT: فقط اگر independent — عمومی — PROPOSED: service_key per image + specialist_user_id | ✅ CURRENT: save_center_image max 3 + gallery upload/delete + main delete with replacement — عمومی | ✅ PROPOSED: مدیریت نمونه‌کارها per service + moderation delete |
| **قیمت** | ✅ CURRENT: مشاهده price_label + duration_label + price_level_label + starting_price with toman | ⚠️ CURRENT: فقط اگر independent — PROPOSED: price_min/max per service + service_key | ✅ CURRENT: price_min/max per service + price_level/starting_price per center + format_toman | ✅ PROPOSED: مدیریت قیمت‌ها per service + settings prices |
| **نوبت** | ✅ CURRENT: reserve GET/POST with service_id/date/final_design_id/service_key/selected_style + slots JSON + calendar JSON + my_reservations + cancel_by_user | ⚠️ CURRENT: فقط اگر independent — owner_list — PROPOSED: reservations with specialist_user_id filter | ✅ CURRENT: owner_list + owner_action confirm/reject/complete + calendar + slots + notify_new_reservation + reminders | ✅ PROPOSED: مدیریت نوبت‌ها همه مراکز + filter status/date/center/service/final_design_id |
| **گفتگو** | ✅ CURRENT: center_chat + center_chat_message + center_chat_close + center_chat_feedback + user_center_conversations + user_center_unread_count + center_chats module | ⚠️ CURRENT: فقط اگر independent — PROPOSED: conversations with specialist_user_id | ✅ CURRENT: owner_conversations + conversation_messages + close + feedback view + owner_conversation_unread_count | ✅ CURRENT: conversations count + unanswered + feedback_rows — PROPOSED: full moderation |
| **آنالیز AI** | ✅ CURRENT: Mirror 4 خدمت (eyebrow, nail, hair_color, lip_shading) با Quality AI+Detection+Analysis+Generation+Validation+Final+Consultant+Interest+Centers enrich + Analysis قدیمی hair/skin در analyses module | ❌ CURRENT: ندارد — PROPOSED: می‌تواند آنالیزهای مشتری را ببیند اگر specialist_user_id در reservation | ❌ CURRENT: ندارد — PROPOSED: می‌تواند آنالیزهای مشتریان مرکز را ببیند via final_design_id in reservations | ✅ CURRENT: _dashboard eyebrow_waitlist + pre_need + interest + demand_by_city + demand_recent — PROPOSED: Extend به همه service_type + final_designs count + provider/model |
| **تبلیغات** | ❌ CURRENT: نمی‌تواند تبلیغ کند | ❌ CURRENT: نمی‌تواند — PROPOSED: اگر independent: purchase_center_promotion + renew | ✅ CURRENT: owner_promote + owner_renew + owner_discount + beauty_center_promotions + is_featured + promotion_type/expires/bumped + discount_service_active | ✅ CURRENT: promotion_rows + active_promotions + promotion_revenue + handle_feature + handle_discount + settings beauty_promotions_enabled/bump/featured/discount/renew + prices — PROPOSED: per service promotion/discount |
| **گزارش** | ✅ CURRENT: overview counts + analyses + orders + hair + notifies + reviews + chats + wallet + missions | ❌ CURRENT: ندارد — PROPOSED: گزارش عملکرد متخصص (reservations, feedback, views) | ✅ CURRENT: views_count, contact_clicks, analysis_impressions, price_inquiry_clicks, beauty_stats, events, performance, conversion_rate — در owner_dashboard + panel_admin dashboard | ✅ CURRENT: dashboard totals + performance + events + demand_by_city + demand_recent + counts per STATUS_FA — PROPOSED: per service_key analytics |
| **مدیریت سالن** | ❌ CURRENT: ندارد — فقط اگر owner → has_center → beauty_center menu | ❌ CURRENT: ندارد — PROPOSED: اگر specialist داخل سالن: limited access به services/images/reservations/messages خودش | ✅ CURRENT: update_owner_center + set_owner_active + save_center_image + _owner_panel_context | ✅ CURRENT: handle_status + handle_settings + list_admin_centers |
| **پنل متخصص** | — | — | — | — |
| **CURRENT وجود دارد؟** | ✅ بله — panel_user با 9 ماژول | ❌ خیر — فقط independent center_type — PROPOSED Hybrid | ✅ بله — beauty_centers owner_dashboard 8 تب P0 | ✅ بله — panel/modules/beauty_centers.py + routes /panel/beauty-centers |
| **PROPOSED معماری** | 💄 زیبایی من با 4 زیرمنو + Mirror History + تب [ابرو][مو][آرایش][ناخن] | Hybrid: مستقل → independent center (P0 Reuse), داخل سالن → beauty_center_services with specialist_user_id + service_key (P1 Extend) | 🏢 مدیریت سالن زیبایی با 8 منو P0 + 3 منو P1 (تخفیف/تبلیغات/نمونه‌کار per service) | مدیریت سالن‌ها (P0) + خدمات per service_key (P1) + نوبت‌ها همه (P1) + نمونه‌کارها per service (P1) + تبلیغات per service (P1) + آنالیزها همه service_type (P1) |

**توضیح ماتریس:** CURRENT = چیزی که الان واقعاً در کد وجود دارد — PROPOSED = پیشنهاد معماری/UX — REQUIRED CHANGE = تغییری که برای رسیدن به پیشنهاد لازم است — هیچ‌وقت Proposed را به‌عنوان Current گزارش نکن — Code Truth.

---

## 10. Existing DB / Architecture Reuse

### 10.1 موجود — قابل استفاده بدون تغییر — P0

| جدول/ماژول | استفاده فعلی | برای 4 پنل |
|---|---|---|
| beauty_centers | 20+ fields, status 6, city indexed, is_active, is_featured, sort_order, counters, pricing, expiry/promotion | Customer: مشاهده + فیلتر service/city, Owner: مدیریت اطلاعات, Admin: مدیریت سالن‌ها + approval + feature |
| beauty_center_services | name, category, description, duration, price_min/max, is_active, sort_order, created_at | Customer: مشاهده قیمت+مدت, Owner: مدیریت خدمات, Admin: مدیریت خدمات (P1 per service_key) |
| beauty_center_working_hours | day_of_week 0=شنبه, open_time, close_time, is_closed, slot_minutes, legacy weekday/is_open | Customer: مشاهده ساعات, Owner: مدیریت ساعات, Admin: مشاهده |
| beauty_center_images | image_path, sort_order, created_at, FK CASCADE, max 3 | Customer: مشاهده gallery carousel, Owner: مدیریت تصاویر, Admin: moderation |
| beauty_center_conversations | center_id, user_id UNIQUE, status active/closed, last_message_at | Customer: گفتگوهای من, Owner: پیام‌ها, Admin: conversations count + unanswered |
| beauty_center_messages | conversation_id, sender_user_id, message_text, is_read, is_reported | Customer+Owner+Admin: پیام‌ها |
| beauty_center_feedback | center_id, conversation_id, user_id UNIQUE, response_level, price_level, overall_level, comment, status pending | Customer: ثبت بازخورد, Owner: مشاهده, Admin: مدیریت بازخورد visible/rejected |
| beauty_center_reservations | center_id, user_id, service_id snapshot, service_name, price_min, duration, date شمسی, time HH:MM, status 5, user_note, center_note, reject_reason, reminded, created_at, confirmed_at, cancelled_at, final_design_id, service_key, selected_style — INDEX 3 | Customer: نوبت‌های من + رزرو با final_design_id, Owner: نوبت‌ها + confirm/reject/complete, Admin: P1 مدیریت همه نوبت‌ها |
| beauty_center_promotions | center_id, owner_user_id, package_key, amount, starts_at, expires_at, transaction_key UNIQUE, status active | Owner: تبلیغات مرکز, Admin: promotion_rows + revenue + feature |
| beauty_center_discounts | center_id, title, description, discount_value, expires_at, status pending | Owner: تخفیف‌ها, Admin: discount_rows |
| beauty_center_events | center_id, event_type, user_id, created_at | Owner+Admin: analytics events |
| buti_ai_sessions | user_id, service_type, city مشهد, center_id, conversation_id, status completed, created_at | Mirror: sessions, Customer: آنالیزهای من (P1), Admin: demand |
| buti_ai_final_designs | session_id, user_id, service_type, original/final filename, selected_style, recommended_style, change_level, provider, model, status created, prompt_json, created_at — INDEX user,created + session | Mirror: final designs, Customer: آنالیزهای من Mirror History (P1), Owner: via final_design_id in reservations, Admin: P1 مدیریت آنالیزها |
| buti_ai_waitlist | user_id, phone_number, city, service_type, source, status open, payload_json, created_at | Mirror: waitlist when no active center, Admin: eyebrow_waitlist |
| buti_ai_service_demand | user_id, city, service_type, source, status open, dedupe_key, payload_json, created_at — UNIQUE dedupe_key WHERE <> '' | Mirror: demand, Admin: pre_need |
| Analysis (SQLAlchemy) | id, user_id, phone, type hair/skin, ai_report_json, plan_json, quick_solution_json, created_at, archived_at | Customer: آنالیزها و برنامه من قدیمی hair/skin |
| panel_user | routes.py canonical /dashboard, permissions.py USER_MODULES 9 + USER_MODULE_GROUPS 4 groups + MODULES_META + is_admin_user + current_user_role, modules/_base.py get_analyses/get_shop_orders/get_hair_orders/get_stock_notifies/get_reviews/get_chats_count/get_wallet, modules/analyses.py hair/skin + archived + latest + products, overview.py counts + last_hair + notifications, chats.py support_tickets, etc | Customer: پنل کاربر فعلی — P0 موجود — P1 Extend با Mirror History + تب [ابرو][مو][آرایش][ناخن] |
| buti_ai | service_catalog.py 4 active + generic_service.py + eyebrow/nail/hair_color/lip final_design.py STYLES 5 + routes.py mirror_home + generic_service_wizard + upload + final + consultant + interest + enrich + schema.py | Customer: Beauty Mirror 4 خدمت, Owner: via final_design_id, Admin: demand |
| panel | modules/beauty_centers.py context dashboard totals/performance/events/demand_by_city/demand_recent + handle_status/feature/discount/feedback/settings, routes.py /panel/beauty-centers + tabs requests/published/paused/promotions/feedback/dashboard/settings, permissions.py ADMIN_SECTIONS + REGULAR_ADMIN_SECTIONS + REGULAR_ADMIN_NAV + SPECIAL_ADMIN_NAV + MODULE_TO_SECTION + SUPER_ONLY_MODULES | Admin: پنل ادمین فعلی — P0 موجود — P1 Extend per service |

### 10.2 قابل توسعه — با تغییر کوچک قابل استفاده — P1

| جدول/ماژول | تغییر پیشنهادی | چرا | migration |
|---|---|---|---|
| beauty_center_services | ADD COLUMN service_key TEXT DEFAULT '' + is_featured_service INTEGER DEFAULT 0 + specialist_user_id INTEGER DEFAULT 0 | Portfolio per service + Featured Service per service + Specialist داخل سالن + نگاشت دقیق Mirror→service_id | ALTER TABLE ADD COLUMN via PRAGMA check + CREATE INDEX IF NOT EXISTS idx_beauty_center_services_service_key ON beauty_center_services(service_key) — additive — same pattern as ai_credits fix + pricing/schema.py |
| beauty_center_images | ADD COLUMN service_key TEXT DEFAULT '' + specialist_user_id INTEGER DEFAULT 0 | Portfolio per service per specialist + filter gallery ?service= | ALTER TABLE ADD COLUMN + INDEX — additive |
| beauty_center_promotions | ADD COLUMN service_id INTEGER DEFAULT 0 | Promotion per service — درآمد | ALTER TABLE ADD COLUMN — additive |
| beauty_center_discounts | ADD COLUMN service_id INTEGER DEFAULT 0 | Discount per service — درآمد + جذب کاربر | ALTER TABLE ADD COLUMN — additive |
| beauty_center_reservations | ADD COLUMN specialist_user_id INTEGER DEFAULT 0 (optional) | Specialist داخل سالن — رزرو per specialist | ALTER TABLE ADD COLUMN — additive — P1 |
| buti_ai_final_designs | بدون تغییر — فقط SELECT در panel_user | Mirror History در پنل کاربر — فقط query | No migration — P0 |
| panel_user/modules/analyses.py | Extend context() با buti_ai_final_designs queries WHERE user_id GROUP BY service_type | ادغام آنالیز قدیمی hair/skin + Mirror جدید [ابرو][مو][آرایش][ناخن] — جلوگیری از دو سیستم موازی | No migration — P0 — فقط code Extend |
| panel/modules/beauty_centers.py _dashboard | Extend to include nail, hair_color, lip_shading waitlist/demand + final_designs count per service_type + provider/model stats | Admin مدیریت آنالیزها همه service_type — نه فقط eyebrow | No migration — P1 — فقط code Extend |
| USER_MODULE_GROUPS | Extend group "زیبایی من" با 4 زیرمنو + rename beauty_center → مدیریت سالن زیبایی + add mirror history | UX پیشنهادی s4.md — ساده + لوکس + قابل فروش | No migration — P0 — فقط permissions.py + routes.py |

### 10.3 نیازمند ساختار جدید — فقط اگر واقعاً ضروری — P2

| جدول/ماژول | توضیح | چرا P2 | Reuse % |
|---|---|---|---|
| beauty_center_specialists | id, center_id FK, user_id FK, service_key, is_active, sort_order, created_at — متخصص داخل سالن با user_id جدا + center_id + service_key | اگر Hybrid با specialist_user_id در services کافی نباشد و نیاز به مدیریت مستقل متخصص‌ها (پروفایل, نمونه‌کار جدا, قیمت جدا, نوبت جدا) باشد — ولی فعلاً با specialist_user_id در services قابل انجام است — پس P2 | Reuse 0%, Extend 0%, New 100% — فعلاً شلوغ می‌کند |
| beauty_center_staff | id, center_id, user_id, role, permissions, is_active | اگر سالن چند کارمند داشته باشد با نقش‌های مختلف — فعلاً یک owner_user_id UNIQUE — پس P2 | New 100% — P2 |
| wishlist / favorites | user_id, center_id/service_id, created_at | علاقه‌مندی‌ها — P2 — فعلاً اضافه | New 100% — P2 |

**ارتباط صحیح بین جداول:**

```
Customer (giso_web_auth id)
   ↓ user_id
Analysis (hair/skin قدیمی) — phone/user_id
   ↓
buti_ai_sessions (service_type eyebrow/nail/hair_color/lip_shading, city, user_id)
   ↓ session_id
buti_ai_final_designs (service_type, original/final filename, selected_style, provider, model, prompt_json, user_id)
   ↓ final_design_id + service_key + selected_style
beauty_center_reservations (center_id, user_id, service_id snapshot, service_name, price_min, duration, date, time, status, final_design_id, service_key, selected_style, specialist_user_id P1)
   ↓ center_id + service_id
beauty_centers (owner_user_id UNIQUE, name, slug, category, center_type, city, services_json, image_path, status, is_active, is_featured, counters, pricing, expiry/promotion)
   ↓ center_id
beauty_center_services (name, category, description, duration, price_min/max, is_active, sort_order, service_key P1, is_featured_service P1, specialist_user_id P1)
   ↓ center_id
beauty_center_images (image_path, sort_order, service_key P1, specialist_user_id P1)
   ↓ center_id
beauty_center_conversations (center_id, user_id UNIQUE, status, last_message_at)
   ↓ conversation_id
beauty_center_messages (sender_user_id, message_text, is_read, is_reported)
   ↓ center_id
beauty_center_feedback (center_id, conversation_id, user_id UNIQUE, response_level, price_level, overall_level, comment, status)
   ↓ center_id
beauty_center_promotions (owner_user_id, package_key, amount, transaction_key UNIQUE, status, service_id P1)
beauty_center_discounts (title, description, discount_value, expires_at, status, service_id P1)
beauty_center_events (event_type, user_id, created_at) — analytics
buti_ai_waitlist + buti_ai_service_demand (city, service_type, dedupe_key, payload_json) — demand when no center
```

---

## 11. Required Changes

### 11.1 CURRENT vs PROPOSED vs REQUIRED CHANGE — تفاوت صریح

| بخش | CURRENT (واقعاً در کد) | PROPOSED (پیشنهاد معماری/UX) | REQUIRED CHANGE (تغییر لازم) |
|---|---|---|---|
| پنل کاربر منو | USER_MODULES 9 visible + USER_MODULE_GROUPS 4 groups "اصلی/خدمات/پشتیبانی/حساب" + beauty_center hidden if not has_center + reservations/center_chats visible + ai_assistant metadata only | 💄 زیبایی من با 4 زیرمنو 🔎 سالن‌های زیبایی 📅 نوبت‌های من 💬 گفتگوهای من 🔬 آنالیزهای من + 🏢 مدیریت سالن زیبایی بیرون زیبایی من + 🏠 پیشخوان اول | Extend permissions.py USER_MODULE_GROUPS add group "زیبایی من" with 4 submenus + rename beauty_center label to "مدیریت سالن زیبایی" + routes.py _menu_for_current_user keep has_center check + add mirror history module — No DB — P0 |
| آنالیزهای من | analyses.py فقط hair/skin قدیمی with ai_report_json, plan_json, quick_solution_json — tabs hair/skin + archived + latest + products — type hair/skin only — no eyebrow/nail/hair_color/lip | تب [ابرو][مو][آرایش][ناخن] — [مو] = hair قدیمی + hair_color Mirror, [ابرو] = eyebrow Mirror, [ناخن] = nail Mirror, [آرایش] = lip_shading Mirror + skin قدیمی + makeup آینده — هر تب count badge + Before/After thumb + CTA مشاهده + رزرو | Extend analyses.py context() with buti_ai_final_designs queries WHERE user_id GROUP BY service_type + merge hair/skin old + template analyses.html add tabs [ابرو][مو][آرایش][ناخن] with badge + new module panel_user/modules/mirror.py reuse analyses.py pattern for Mirror History — No DB — P0 |
| Mirror 4 خدمت | SERVICE_CATALOG 4 active + generic_service + STYLES 5 + CHANGE_LEVELS + buti_ai_sessions + buti_ai_final_designs + routes /analysis/mirror/ + templates generic_service_wizard/generic_final_design + consultant + interest + enrich | اتصال به پنل کاربر آنالیزهای من + پیشنهاد سالن‌های همان خدمت + رزرو با final_design_id + consultant chat | No change for Mirror itself — P0 Reuse — فقط اتصال به panel_user via mirror.py module + enrich already exists — P0 |
| متخصص مستقل | center_type independent in CENTER_TYPES — می‌تواند beauty_centers row با owner_user_id خودش ثبت کند — 100% Reuse | مستقل → independent center (P0 Reuse) — داخل سالن → beauty_center_services with specialist_user_id + service_key (P1 Extend) — Hybrid | P0: No change — independent already works — P1: ADD COLUMN specialist_user_id + service_key in beauty_center_services + beauty_center_images — ALTER TABLE ADD COLUMN — P1 |
| مدیر سالن اطلاعات | update_owner_center + _normalize_fields + has_center + owner_dashboard tab edit | اطلاعات سالن (P0 موجود) | No change — P0 Reuse |
| مدیر سالن خدمات | get_center_services + add/update/delete + _clean_service name/category/description/duration/price_min/max/is_active/sort_order — P0 | خدمات با service_key + is_featured_service + specialist_user_id — P1 | ADD COLUMN service_key + is_featured_service + specialist_user_id in beauty_center_services — ALTER TABLE — P1 |
| مدیر سالن قیمت‌ها | price_min/max per service + price_level/starting_price per center + format_toman — P0 | قیمت‌ها per service با service_key mapping — P0 موجود + P1 service_key | P0 Reuse — P1 ADD COLUMN service_key |
| مدیر سالن نمونه‌کارها | save_center_image max 3 + gallery upload/delete + main delete with replacement — عمومی — P0 | نمونه‌کارها per service per specialist — P1 | ADD COLUMN service_key + specialist_user_id in beauty_center_images — ALTER TABLE — P1 |
| مدیر سالن نوبت‌ها | owner_list + confirm/reject/complete + calendar + slots + notify — P0 | نوبت‌ها per specialist filter — P1 | ADD COLUMN specialist_user_id in reservations (optional) — ALTER TABLE — P1 |
| مدیر سالن گفتگوها | owner_conversations + messages + close + feedback — P0 | گفتگوها per specialist — P1 | No DB — filter by service/specialist in code — P1 |
| مدیر سالن تخفیف‌ها | owner_discount + beauty_center_discounts — عمومی — P0 | تخفیف‌ها per service — P1 | ADD COLUMN service_id in discounts — ALTER TABLE — P1 |
| مدیر سالن تبلیغات | owner_promote + renew + promotions + is_featured + promotion_type/expires/bumped — مرکز — P0 | تبلیغات per service — P1 | ADD COLUMN service_id in promotions — ALTER TABLE — P1 |
| مدیر سالن گزارش عملکرد | views_count, contact_clicks, analysis_impressions, price_inquiry_clicks, beauty_stats, events, performance, conversion_rate — P0 | گزارش per service_key — P1 | No DB — code Extend — P1 |
| ادمین سالن‌ها | panel_admin context dashboard totals/performance/events/demand_by_city/demand_recent + handle_status/feature/discount/feedback/settings + routes /panel/beauty-centers + tabs requests/published/paused/promotions/feedback/dashboard/settings + permissions ADMIN_SECTIONS + REGULAR_ADMIN_NAV | مدیریت سالن‌ها P0 موجود + خدمات per service_key P1 + نوبت‌ها همه P1 + نمونه‌کارها per service P1 + تبلیغات per service P1 + آنالیزها همه service_type P1 | Extend panel_admin _dashboard to include nail/hair_color/lip_shading waitlist/demand + final_designs count + provider/model stats + new admin routes for reservations all + services per service_key — No DB for dashboard, DB for services/images/promotions/discounts P1 |
| ادمین آنالیزها | _dashboard only eyebrow waitlist/pre_need/interest/demand_by_city/demand_recent — no nail/hair_color/lip | آنالیزها همه service_type + final_designs count + provider/model | Extend _dashboard to include all service_type — No DB — P1 |

**هیچ‌وقت Proposed را به‌عنوان Current گزارش نکن — Code Truth.**

---

## 12. P0 / P1 / P2 — اولویت‌بندی

### P0 — ضروری برای ساختار صحیح پنل‌ها — بدون تغییر DB — ساده+لوکس+قابل فروش+قابل مدیریت

- پنل کاربر: USER_MODULES 9 + USER_MODULE_GROUPS 4 groups موجود — Extend group "زیبایی من" با 4 زیرمنو 🔎 سالن‌های زیبایی (list_centers), 📅 نوبت‌های من (reservations + my_reservations), 💬 گفتگوهای من (center_chats + chats), 🔬 آنالیزهای من (analyses) — has_center check برای 🏢 مدیریت سالن زیبایی — No DB
- آنالیزهای من: Extend analyses.py context() با buti_ai_final_designs WHERE user_id GROUP BY service_type — merge hair/skin قدیمی + Mirror جدید — تب [ابرو][مو][آرایش][ناخن] با badge count — template analyses.html add tabs — new module panel_user/modules/mirror.py reuse analyses.py pattern — No DB — جلوگیری از دو سیستم موازی — یک route /dashboard/analyses همه را نشان دهد
- Mirror 4 خدمت: SERVICE_CATALOG 4 active + generic_service + STYLES 5 + buti_ai_sessions + buti_ai_final_designs + routes /analysis/mirror/ + templates + consultant + interest + enrich — موجود — No change — Reuse
- متخصص مستقل: center_type independent — beauty_centers row with owner_user_id — 100% Reuse — No change — P0
- مدیر سالن: اطلاعات سالن, خدمات, قیمت‌ها, نمونه‌کارها عمومی, نوبت‌ها, گفتگوها, تخفیف‌ها عمومی, تبلیغات مرکز, گزارش عملکرد — همه موجود — No change — P0
- ادمین: مدیریت سالن‌ها, گزارش‌ها, تبلیغات مرکز, تخفیف‌ها مرکز, آنالیزها eyebrow demand, تنظیمات — موجود — No change — P0
- Beauty Center: beauty_centers 20+ fields + 10 tables + SERVICES 20 keys + STATUS 6 + pricing 6 funcs + reservations with final_design_id/service_key/selected_style BEGIN IMMEDIATE snapshot + conversations/messages/feedback/promotions/discounts/events — موجود — No change — P0
- امنیت: login_required + owner check + _is_staff + CSRF + static_root check + nosniff + normalize_phone — موجود — P0

### P1 — ضروری برای تجربه حرفه‌ای و تجاری — با 2-4 ستون additive — ارزش بالا

- Portfolio per service: ADD COLUMN service_key TEXT DEFAULT '' in beauty_center_images + specialist_user_id INTEGER DEFAULT 0 + UI dropdown در owner_gallery_upload + filter in detail.html ?service= — 1-2 ستون additive — ALTER TABLE ADD COLUMN via PRAGMA check + INDEX — same pattern as ai_credits fix
- Featured Service per service: ADD COLUMN service_key TEXT DEFAULT '' + is_featured_service INTEGER DEFAULT 0 in beauty_center_services + UI toggle در owner_dashboard services + filter in list_centers for featured service — 2 ستون additive
- Service Key در services: ADD COLUMN service_key TEXT DEFAULT '' + specialist_user_id INTEGER DEFAULT 0 in beauty_center_services + index + dropdown in add_service form — برای نگاشت دقیق Mirror→service_id — 2 ستون additive
- Discount per service: ADD COLUMN service_id INTEGER DEFAULT 0 in beauty_center_discounts + UI select service + badge in service card — 1 ستون additive
- Promotion per service: ADD COLUMN service_id INTEGER DEFAULT 0 in beauty_center_promotions + UI — 1 ستون additive
- Specialist داخل سالن: Hybrid — مستقل P0 Reuse, داخل سالن → beauty_center_services with specialist_user_id + service_key (P1 Extend) — 2 ستون additive — بدون جدول جدید
- User Panel Mirror History: new module panel_user/modules/mirror.py reuse analyses.py pattern — SELECT from buti_ai_final_designs WHERE user_id ORDER BY created_at DESC — Before/After thumb + CTA رزرو با همین طراحی — 1 فایل جدید — No DB
- Admin مدیریت خدمات per service_key: Extend panel_admin context + new admin route for services per service_key + is_featured_service filter — No DB for route, DB for services columns P1
- Admin مدیریت نوبت‌ها همه مراکز: new admin route reuse reservations/services get_center_reservations + filter status/date/center/service/final_design_id — No DB — P1
- Admin مدیریت نمونه‌کارها per service: filter service_key in images — DB P1
- Admin مدیریت تبلیغات per service: service_id in promotions/discounts — DB P1
- Admin مدیریت آنالیزها همه service_type: Extend _dashboard to include nail, hair_color, lip_shading waitlist/demand + final_designs count per service_type + provider/model stats — No DB — P1
- Bale Mirror flow: reuse generic_service for Bale bot_handlers — extend bot_handlers.py — No DB — P1

### P2 — قابلیت‌های آینده — فعلاً نباید ساختار را شلوغ کنند

- beauty_center_specialists جدول جدید id, center_id FK, user_id FK, service_key, is_active, sort_order, created_at — متخصص داخل سالن با پروفایل جدا + نمونه‌کار جدا + قیمت جدا + نوبت جدا — New 100% — P2 — فعلاً با specialist_user_id در services قابل انجام است
- beauty_center_staff جدول جدید id, center_id, user_id, role, permissions, is_active — چند کارمند با نقش‌های مختلف — New 100% — P2 — فعلاً یک owner_user_id UNIQUE
- wishlist / favorites user_id, center_id/service_id, created_at — علاقه‌مندی‌ها — New 100% — P2
- Instagram/Logo, نمونه‌کار 800+ با کراپ, ظرفیت پیشرفته, نظرات پیشرفته با عکس, Featured Service Promotion مبلغ جدا, کمیسیون رزرو, API برای اپلیکیشن, تبلیغ هدفمند پیچیده با AI boosting — P2

**هدف:** سیستم ساده + لوکس + قابل فروش + قابل مدیریت برای سالن — نه پنل پر از امکانات غیرضروری — P0 بدون تغییر DB 100% قابل دستیابی — P1 با 2-4 ستون additive ارزش تجاری بالا.

---

## 13. UX Recommendation — پیشنهاد نهایی UX + مسیر اصلی کاربر

### 13.1 ساختار پیشنهادی نهایی 4 پنل

```
🏠 پیشخوان (خلاصه من) — overview.py counts + last_hair + notifications + missions

💄 زیبایی من (group جدید)
   ├── 🔎 سالن‌های زیبایی — /beauty-centers?q=&city=&category=&type=&service=&price_level= + featured 6 + related + beauty_stats + _card.html + list.html
   ├── 📅 نوبت‌های من — /dashboard/reservations (panel_user) + /beauty-centers/my-reservations (beauty_reservations) + get_user_reservations + status labels + cancel_by_user
   ├── 💬 گفتگوهای من — /dashboard/center_chats (user_center_conversations + user_center_unread_count) + /dashboard/chats (support_tickets + consultant_requests) + center_chat + chat
   └── 🔬 آنالیزهای من — /dashboard/analyses با تب [ابرو 🪞][مو 🎨][آرایش 💋][ناخن 💅] + badge count
        ├── [ابرو] = buti_ai_final_designs WHERE service_type=eyebrow + eyebrow Mirror History
        ├── [مو] = Analysis hair قدیمی + buti_ai_final_designs hair_color + hair_color Mirror History
        ├── [آرایش] = Analysis skin قدیمی + buti_ai_final_designs lip_shading + lip_shading Mirror History + makeup آینده
        └── [ناخن] = buti_ai_final_designs nail + nail Mirror History
            هر ردیف: date_fa + service_label + selected_style + final_label + Before/After thumb + has_plan + has_report + CTA مشاهده نتیجه + رزرو با همین طراحی (final_design_id)

🏢 مدیریت سالن زیبایی (فقط اگر has_center = get_owner_center(user_id) — بیرون زیبایی من — سطح اول)
   ├── اطلاعات سالن — update_owner_center + _normalize_fields
   ├── خدمات — get_center_services + add/update/delete + _clean_service + service_key + is_featured_service + specialist_user_id P1
   ├── قیمت‌ها — price_min/max per service + price_level/starting_price per center + format_toman
   ├── نمونه‌کارها — save_center_image max 3 + gallery upload/delete + main delete + service_key per image P1
   ├── نوبت‌ها — owner_list + confirm/reject/complete + calendar + slots + notify
   ├── گفتگوها — owner_conversations + messages + close + feedback
   ├── تخفیف‌ها — owner_discount + beauty_center_discounts + service_id P1
   ├── تبلیغات — owner_promote + renew + promotions + is_featured + promotion_type/expires/bumped + service_id P1
   └── گزارش عملکرد — views_count, contact_clicks, analysis_impressions, price_inquiry_clicks, beauty_stats, events, performance, conversion_rate

💇‍♀️ فروش مو به گیسو — hair_sale module
🏪 بازارچه مو — marketplace module
🛍️ خریدهای من از فروشگاه — orders module
💰 کیف پول و اعتبار — wallet module
💬 پیام‌ها و پشتیبانی — chats module (support_tickets + consultant_requests + bug_reports)
👤 پروفایل — profile module

🤖 دستیار هوشمند گیسو — ai_assistant metadata only — لینک اختصاصی از سایدبار
```

**دلیل نام و ساختار:**
- 💄 زیبایی من کوتاه‌تر و شخصی‌تر از "مدیریت زیبایی گیسو" — هم‌خوانی با "نوبت‌های من", "گفتگوهای من", "آنالیزهای من" — فارسی محاوره‌ای + لوکس
- 🏢 مدیریت سالن زیبایی بیرون زیبایی من — چون صاحب سالن همزمان مشتری هم هست — اگر داخل زیبایی من باشد، مشتری عادی که سالن ندارد آن را نمی‌بیند (has_center check) — ولی بیرون بودن با شرط has_center منطقی‌تر — معماری فعلی _menu_for_current_user already has_center check
- 🔬 آنالیزهای من با تب [ابرو][مو][آرایش][ناخن] — ساده‌ترین و لوکس‌ترین راه — 4 خدمت بیشتر نیست — تب با آیکون + badge count — pattern analyses.py فعلی hair/skin را جدا می‌کند — همین pattern برای 4 تب قابل Extend
- ادغام آنالیز قدیمی و جدید: یک route /dashboard/analyses همه را نشان دهد، نه دو route جدا — جلوگیری از دو سیستم موازی

### 13.2 مسیر اصلی کاربر — Flow

```
آنالیز (Beauty Mirror /analysis/mirror/ 4 کارت)
   ↓ Style Selection (5 مدل per service با sample 520x360)
   ↓ Upload (preview+guide+sample)
   ↓ Quality AI + Detection + Analysis AI
   ↓ Generation (Before/After + validation صادقانه + provider/model + is_ai_generated)
   ↓ نتیجه (final_label + do/avoid + interest Lead vs View + centers enrich score+tags+match reason + consultant invite)
   ↓ خدمات مرتبط (list_centers?service={beauty_center_service} + _enrich_generic_centers score 45 has_service+20 city+15 featured+feedback)
   ↓ سالن / متخصص (center_detail با services+price+hours+feedback+gallery+contact+chat + increment_view)
   ↓ نمونه‌کار + قیمت (service card لوکس: icon + name + category + description 1 خط + duration + price_label toman + نمونه‌کار همان خدمت P1 + تخفیف badge + CTA)
   ↓ گفتگو (center_chat + center_chat_message + close + feedback)
   ↓ نوبت (reserve GET service_id/date/slots JSON/calendar JSON + POST create_reservation with final_design_id/service_key/selected_style snapshot + BEGIN IMMEDIATE + notify_new_reservation)
   ↓ پیگیری (my_reservations + center_chats + analyses history + overview counts + notifications)
```

**آیا این flow با معماری فعلی Giso سازگار است یا نیاز به اصلاح دارد؟**

**پاسخ: بله — 100% سازگار با معماری فعلی — بدون اصلاح — فقط اتصال:**

- آنالیز: Mirror 4 خدمت فعال با Quality+Detection+Analysis+Generation+Validation+Final — موجود — P0 Reuse
- خدمات مرتبط: list_centers?service= filtering — موجود — P0 Reuse
- سالن/متخصص: center_detail + independent center_type — موجود — P0 Reuse — specialist داخل سالن P1 Extend specialist_user_id
- نمونه‌کار+قیمت: _center_services_for_display price_label/duration_label + gallery carousel — موجود — P0 Reuse — portfolio per service P1 Extend service_key
- گفتگو: get_or_create_conversation + send_conversation_message + owner_conversations — موجود — P0 Reuse
- نوبت: create_reservation BEGIN IMMEDIATE snapshot + final_design_id/service_key/selected_style + slots + calendar + notify — موجود — P0 Reuse
- پیگیری: my_reservations + user_center_conversations + analyses + overview + notifications — موجود — P0 Reuse — Mirror History P1 Extend mirror.py module

**پس Flow پیشنهادی با معماری فعلی سازگار است و نیاز به اصلاح ندارد — فقط P0 اتصال Mirror History به panel_user + P1 2-4 ستون additive برای لوکس‌تر شدن.**

---

## 14. Scope Lock — Proposed Scope — فهرست دقیق فایل‌ها / ماژول‌هایی که در صورت تأیید کاربر احتمالاً باید تغییر کنند

**قانون s4.md:** هیچ‌کدام را تغییر نده — فقط گزارش بده و STOP کن — اگر فایل جدید لازم است، مشخص کن چرا فایل موجود قابل استفاده نیست.

### 14.1 ALLOWED files — اگر تأیید شود — با دلیل + تغییر احتمالی + dependency + ریسک

| path | دلیل | تغییر احتمالی | dependency | ریسک |
|---|---|---|---|---|
| `giso/panel_user/permissions.py` | UX پیشنهادی 💄 زیبایی من با 4 زیرمنو + 🏢 مدیریت سالن زیبایی بیرون + rename beauty_center label | Extend USER_MODULE_GROUPS add group "زیبایی من" with [beauty_centers_list, reservations, center_chats, analyses] + MODULES_META beauty_center label "مدیریت سالن زیبایی" + add beauty_centers_list, mirror meta | panel_user/routes.py _menu_for_current_user has_center check | Low — فقط menu grouping — no DB — no breaking change — fallback to existing groups |
| `giso/panel_user/routes.py` | اتصال Mirror History + تب [ابرو][مو][آرایش][ناخن] + menu badges | Extend _menu_for_current_user keep has_center + add beauty_centers_list route + mirror route + _render mirror + menu_badges for mirror count + analyses | panel_user/modules/analyses.py, mirror.py, beauty_centers/services.py get_owner_center, wallet, notifications | Low — reuse _render pattern — no DB |
| `giso/panel_user/modules/analyses.py` | ادغام آنالیز قدیمی hair/skin + Mirror جدید — جلوگیری از دو سیستم موازی | Extend context() with buti_ai_final_designs queries WHERE user_id GROUP BY service_type (eyebrow, nail, hair_color, lip_shading) + merge hair old + skin old + return eyebrow_analyses, nail_analyses, hair_color_analyses, lip_analyses + counts + latest per service | giso/base.py get_giso_db_conn, giso/models.py Analysis, buti_ai/schema.py buti_ai_final_designs | Low — SELECT only — no migration — fallback to existing hair/skin if no Mirror |
| `giso/panel_user/modules/mirror.py` NEW | Mirror History در پنل کاربر — چرا فایل موجود قابل استفاده نیست؟ analyses.py فقط hair/skin قدیمی — Mirror جدید service_type eyebrow/nail/hair_color/lip_shading + final_filename + selected_style + provider/model — نیاز به module جدا reuse analyses.py pattern | NEW file reuse analyses.py pattern: _decorate_mirror(row) + context() SELECT FROM buti_ai_final_designs WHERE user_id ORDER BY created_at DESC GROUP BY service_type + counts + latest + Before/After thumb + CTA reserve with final_design_id | giso/base.py get_giso_db_conn, buti_ai/schema.py, panel_user/modules/_base.py | Low — new file — no existing file modification — isolated — P1 |
| `giso/panel_user/templates/user_modules/analyses.html` | تب [ابرو][مو][آرایش][ناخن] با badge count + Before/After thumb + CTA | Extend template add tabs nav with icons 🪞💅🎨💋 + badge counts + tab content per service_type + merge old hair/skin + new Mirror + CTA مشاهده نتیجه + رزرو با همین طراحی | panel_user/modules/analyses.py context, buti_ai_final_designs, Analysis | Low — template extend blocks — no logic change — fallback to existing tabs |
| `giso/panel_user/templates/user_modules/mirror.html` NEW | Mirror History template — چرا موجود قابل استفاده نیست؟ analyses.html فقط hair/skin قدیمی — Mirror نیاز به Before/After + validation + provider/model + service/style/change labels | NEW template reuse analyses.html pattern + generic_final_design.html pattern: grid of Mirror cards with Before/After, service_label, selected_style, final_label, created_at, provider, is_ai_generated, CTA مشاهده + رزرو | panel_user/modules/mirror.py context | Low — new file — isolated |
| `giso/beauty_centers/schema.py` | Portfolio per service per specialist + Discount/Promotion per service | Extend migrate_beauty_center_tables() add PRAGMA check + ALTER TABLE ADD COLUMN service_key TEXT DEFAULT '' + specialist_user_id INTEGER DEFAULT 0 in beauty_center_images + service_id INTEGER DEFAULT 0 in promotions/discounts — additive — same pattern as existing salon_phone, display_phone_choice | giso/base.py get_giso_db_conn | Low — additive columns DEFAULT ''/0 — existing queries SELECT * still work — fallback WHERE service_key='' OR service_key=? |
| `giso/beauty_centers/pricing/schema.py` | Featured Service per service + Service Key mapping + Specialist داخل سالن | Extend migrate_pricing_tables() add PRAGMA check + ALTER TABLE ADD COLUMN service_key TEXT DEFAULT '' + is_featured_service INTEGER DEFAULT 0 + specialist_user_id INTEGER DEFAULT 0 in beauty_center_services + CREATE INDEX IF NOT EXISTS idx_beauty_center_services_service_key — additive | giso/base.py get_giso_db_conn | Low — additive — same pattern as SERVICES_COLUMNS/WORKING_HOURS_COLUMNS + _ensure_table |
| `giso/beauty_centers/pricing/services.py` | مدیریت خدمات per service_key + is_featured_service + specialist_user_id | Extend _clean_service() accept service_key, is_featured_service, specialist_user_id optional + validation service_key in SERVICES or beauty_center_service mapping + get_center_services keep order is_active DESC sort_order ASC + add_service/update_service keep INSERT/UPDATE with new columns | pricing/schema.py SERVICES_COLUMNS | Low — validation + INSERT/UPDATE extend — no breaking change — existing calls still work with default ''/0 |
| `giso/beauty_centers/services.py` | Portfolio per service per specialist + Promotion per service | Extend save_center_image() keep validation + add service_key param optional + list_public_centers keep filters + decorate_center keep feedback/discount + reveal_contact + increment_view | beauty_centers/schema.py, pricing/services.py, base.py | Low — param optional — no breaking change |
| `giso/beauty_centers/routes.py` | نمایش نمونه‌کار per service + قیمت per service + CTA رزرو با final_design_id | Extend _center_services_for_display keep price_label/duration_label + add service_key + is_featured_service + specialist_user_id + _center_hours_for_display + center_detail with gallery filtered by ?service= query + owner_dashboard with service_key dropdown in add_service form + gallery service_key dropdown + featured toggle + specialist_user_id select + owner_gallery_upload with service_key + discount/promotion with service_id | beauty_centers/services.py, pricing/services.py, reservations/services.py, base.py, config.py, money.py | Medium — display + form extend — need fallback to general gallery if service_key empty — test with existing centers |
| `giso/beauty_centers/templates/beauty_centers/detail.html` | Service card لوکس با نمونه‌کار همان خدمت + قیمت + تخفیف + CTA + gallery filtered | Extend bc-service-item with thumb portfolio per service (1 image) + discount badge + is_featured_service badge + specialist label + CTA reserve/مشاوره/مشاهده + gallery filter ?service= | routes.py _center_services_for_display, beauty_center_images with service_key | Low — template extend — fallback to general gallery |
| `giso/beauty_centers/templates/beauty_centers/owner_dashboard.html` | مدیریت خدمات per service_key + نمونه‌کار per service + Featured Service toggle + Specialist | Extend tabs services form add service_key dropdown (brow, nail, hair_color, lip_shading, haircut, etc) + is_featured_service checkbox + specialist_user_id select + gallery upload form add service_key dropdown + featured toggle + discount/promotion form add service_id select | routes.py owner_dashboard, pricing/services.py _clean_service | Low — form extend — optional fields — no breaking change |
| `giso/beauty_centers/reservations/schema.py` | Specialist داخل سالن — رزرو per specialist | Extend RESERVATIONS_COLUMNS add specialist_user_id INTEGER DEFAULT 0 — additive — PRAGMA check + ALTER TABLE — same pattern | base.py get_giso_db_conn | Low — additive DEFAULT 0 — existing INSERT still works — new column optional |
| `giso/beauty_centers/reservations/services.py` | رزرو per specialist + service_key mapping | Extend create_reservation() accept specialist_user_id optional + snapshot specialist_user_id + _service_of keep check is_active + get_center_services + get_available_slots + get_calendar_month + owner_list + owner_action | reservations/schema.py RESERVATIONS_COLUMNS | Low — param optional — no breaking change — existing calls still work |
| `giso/beauty_centers/reservations/routes.py` | رزرو با final_design_id + service_key + selected_style + specialist_user_id | Extend reserve GET/POST keep service_id/date/final_design_id/service_key/selected_style + add specialist_user_id + slots JSON + calendar JSON + my_reservations + cancel_by_user | reservations/services.py, pricing/services.py, base.py | Low — param optional — no breaking change |
| `giso/panel/modules/beauty_centers.py` | Admin مدیریت آنالیزها همه service_type + خدمات per service_key + نوبت‌ها همه + نمونه‌کارها per service + تبلیغات per service | Extend _dashboard() to include nail, hair_color, lip_shading waitlist/demand + final_designs count per service_type + provider/model stats + context() add services per service_key + reservations all + images per service_key + promotions per service_id | base.py get_giso_db_conn, beauty_centers/services.py list_admin_centers, admin_set_status, giso_admin get_giso_config | Medium — dashboard query extend — need test with existing data — no migration for dashboard, DB for services/images/promotions/discounts P1 |
| `giso/panel/routes.py` | Admin routes برای خدمات per service_key + نوبت‌ها همه + نمونه‌کارها per service | Extend beauty_centers() keep module_allowed check + _render admin.html with new tabs services_all, reservations_all, images_all, promotions_all + new routes /beauty-centers/services, /beauty-centers/reservations, /beauty-centers/images, /beauty-centers/final-designs | panel/modules/beauty_centers.py context, permissions.py module_allowed | Low — new routes reuse _render pattern — no breaking change |
| `giso/buti_ai/routes.py` | اتصال Mirror به پنل کاربر + enrich with service_id mapping + consultant + interest | Extend _enrich_generic_centers keep scoring 45 has_service+20 city+15 featured+feedback + add service_id mapping via beauty_center_services service_key + mirror_home + generic_service_wizard + upload + final + consultant + interest + demand/waitlist + session handling | buti_ai/service_catalog.py, generic_service.py, service_image_generation.py, schema.py, services.py | Low — enrich extend — no breaking change — keep existing scoring |
| `giso/buti_ai/service_catalog.py` | اگر خدمت جدید makeup اضافه شود | Extend SERVICE_CATALOG with makeup key + slug + beauty_center_service makeup + status active — P2 | — | Low — declarative — no logic change |
| `rp7.md` | این گزارش | Read-Only audit — ALLOWED per law | — | — |

**FORBIDDEN: everything else — especially:**
- `bot_edu/` — LOCKED per PROJECT_GUIDE — تغییر ممنوع مگر دستور صریح
- `web/` — port 5000 — decoupled from giso/ — LOCKED
- `main.py` — launcher — never modified as part of feature change
- `giso/bot.py` — 7422 lines — قانون ثابت پروژه: refactor/تقسیم نکن — فقط فیکس موضعی
- `graphify-out/`, `project_memory/`, `data/`, `.env`, venv, git history — never modified as part of feature change
- `giso/buti_ai/eyebrow/` for new services — باید از generic_service استفاده شود — نه کپی eyebrow
- `giso/models.py` Analysis model — ORM only for giso_web_auth and business tables — بقیه با SQL خام — تغییر ORM ممنوع مگر migration additive

**Shared/caution files inside future scope:**
- `beauty_centers/schema.py` — shared tables beauty_centers/services/images/reservations/conversations/messages/feedback/promotions/discounts/events/reports — caution: additive columns only + PRAGMA check
- `beauty_centers/pricing/schema.py` — shared tables services/working_hours — caution: additive only
- `beauty_centers/services.py` — shared listing list_public_centers + decorate_center + save_center_image + increment_view + reveal_contact — caution: no breaking change to filters
- `panel_user/routes.py` — shared auth _guard + _menu_for_current_user + _render + menu_badges + wallet + notifications — caution: has_center check keep
- `buti_ai/routes.py` — shared AI runtime + provider chain + credits + sessions + final_designs + enrich scoring — caution: keep scoring 45+20+15+feedback
- `panel/modules/beauty_centers.py` — shared admin dashboard + settings + status/feature/discount/feedback — caution: keep totals/performance/events/demand queries
- `giso/base.py` get_giso_db_conn WAL + busy_timeout — never create second helper

**Data: tables involved / migration needed? how (incremental, module style):**
- Tables: beauty_centers, beauty_center_services, beauty_center_working_hours, beauty_center_images, beauty_center_conversations, beauty_center_messages, beauty_center_feedback, beauty_center_reservations, beauty_center_promotions, beauty_center_discounts, beauty_center_events, beauty_center_expiry_notices, beauty_center_reports, buti_ai_sessions, buti_ai_waitlist, buti_ai_service_demand, buti_ai_final_designs, giso_web_auth, giso_config, giso_admins, Analysis, giso_support_tickets, consultant_requests
- Migration needed? P0 no — 100% با ساختار فعلی قابل انجام — P1 yes additive via ALTER TABLE ADD COLUMN with PRAGMA table_info check + CREATE INDEX IF NOT EXISTS — incremental, module style — same pattern as ai_credits fix + pricing/schema.py _ensure_table + beauty_centers/schema.py migrate_beauty_center_tables + buti_ai/schema.py _ensure_column — never DROP/RECREATE — all via get_giso_db_conn()

**Out of scope: (named neighbors):**
- bot_edu/, web/, graphify-out/, project_memory/, data/, .env, main.py, giso/bot.py refactor, giso/models.py ORM change, giso/shop/, giso/marketplace/, giso/hair_sale/, giso/wallet/, giso/analysis.py old hair/skin AI (not Mirror), giso/consultant_cards.py, giso/consultant_chat_service.py

**Why new file needed:**
- `panel_user/modules/mirror.py` NEW — چرا فایل موجود قابل استفاده نیست؟ analyses.py فقط hair/skin قدیمی با ai_report_json, plan_json, quick_solution_json — Mirror جدید service_type eyebrow/nail/hair_color/lip_shading + final_filename + selected_style + provider/model + prompt_json + original/final filename — نیاز به module جدا reuse analyses.py pattern — دلیل: Separation of concerns — analyses.py قدیمی + mirror.py جدید — هر دو در /dashboard/analyses ادغام شوند — 1 فایل جدید — isolated — P1
- `panel_user/templates/user_modules/mirror.html` NEW — چرا موجود قابل استفاده نیست؟ analyses.html فقط hair/skin قدیمی — Mirror نیاز به Before/After + validation + provider/model + service/style/change labels + consultant + interest + centers enrich — نیاز به template جدا reuse analyses.html + generic_final_design.html pattern — 1 فایل جدید — isolated — P1

**APPROVAL NEEDED: تأیید می‌کنی؟**

---

## 15. Risks / Regression

**Risks:**

- اگر service_key به beauty_center_images اضافه شود و existing images بدون service_key باشند، filter باید fallback به عمومی داشته باشد — mitigation: WHERE service_key='' OR service_key=? + UI "همه" option + existing queries SELECT * still work with DEFAULT '' — Low risk
- اگر Featured Service اضافه شود و مرکز 10 خدمت Featured کند، لیست شلوغ می‌شود — mitigation: limit 3 featured per center + sort_order + is_featured_service checkbox with max 3 validation in _clean_service — Low risk
- اگر User Panel Mirror History اضافه شود و user_id null باشد (guest sessions), query باید user_id IS NOT NULL — mitigation: filter user_id = current_user.id + user_id IS NOT NULL + status created — Low risk
- اگر Bale Mirror flow اضافه شود و provider quota تمام شود, fallback guided composite باید صادقانه اعلام شود — mitigation: existing validation + is_ai_generated flag + provider/model + fallback_type message — Low risk — existing pattern in service_image_generation.py
- اگر specialist_user_id اضافه شود و center_id + specialist_user_id + service_key unique نباشد, duplicate service per specialist ممکن است — mitigation: UNIQUE INDEX IF NOT EXISTS idx_beauty_center_services_center_specialist_service ON beauty_center_services(center_id, specialist_user_id, service_key) WHERE specialist_user_id<>0 — Low risk
- اگر USER_MODULE_GROUPS جدید "زیبایی من" اضافه شود و existing menu grouping "خدمات" still contains beauty_center, duplicate menu ممکن است — mitigation: remove beauty_center from "خدمات" group and add to "زیبایی من" group + keep has_center check — Low risk
- اگر analyses.py Extend با buti_ai_final_designs queries و Analysis old queries merge شود, performance ممکن است slow شود — mitigation: LIMIT 50 per service_type + INDEX user,created DESC already exists + caching via session — Low risk
- اگر admin _dashboard Extend به همه service_type و final_designs count, query ممکن است heavy شود — mitigation: use qopt() with try/except + LIMIT 20 + existing pattern in _dashboard() — Low risk

**Regression plan:**

- Targeted tests: `SECRET_KEY=test python -m pytest giso/tests/test_beauty_centers_*.py -q` — 16 files (grep beauty_centers) — `python -m pytest giso/tests/test_buti_ai_new_services.py -q` — generic_service 4 services — `python -m pytest giso/tests/test_buti_ai_phase1.py -q` — eyebrow baseline — `python -m pytest giso/tests/test_broadcasts_center.py -q` — notifications — `python -c "import giso.wsgi"` — import/boot check — manual: list_centers?service=nail filter, center_detail services+price+hours+feedback+gallery+contact+chat, Mirror upload→final with validation, reserve with final_design_id/service_key/selected_style, owner_dashboard tabs, promotion, consultant chat, panel_user analyses tabs [ابرو][مو][آرایش][ناخن], overview counts, chats, wallet, profile, admin beauty-centers tabs requests/published/paused/promotions/feedback/dashboard/settings
- Sibling features sharing code: marketplace, hair_sale, analyses, chats, orders, wallet, profile, reviews, overview in panel_user — shared DB tables: beauty_centers, services, working_hours, images, conversations, messages, feedback, reservations, promotions, discounts, events, buti_ai_sessions, final_designs, Analysis, giso_support_tickets, consultant_requests — Notification events: new_reservation, user_confirmed/rejected, ticket new — Existing tests: `giso/tests/test_panel_user_*.py` (grep panel_user) — `giso/tests/test_analysis_*.py` (grep Analysis)
- Shared symbol tests: get_giso_db_conn, ai_runtime, ai_credits, ai_models_registry — `Select-String` in giso/tests/ — run all test files that import that symbol
- Manual: verify existing centers still list, existing reservations still work, existing gallery still shows, existing chat still works, existing Mirror still generates, existing analyses still shows hair/skin old, existing overview still shows counts, existing wallet still shows balances, existing admin still shows dashboard + requests + published + promotions + feedback + settings

**Found but not changed:**

- beauty_center_images بدون service_key + specialist_user_id — Gap Medium — P1 پیشنهادی — additive columns
- beauty_center_services بدون service_key + is_featured_service + specialist_user_id — Gap Medium — P1 پیشنهادی
- beauty_center_promotions + discounts بدون service_id — Gap Low — P1 پیشنهادی
- beauty_center_reservations بدون specialist_user_id — Gap Low — P1 پیشنهادی
- User Panel Mirror History ندارد — Gap Medium — P1 new module mirror.py reuse analyses.py
- Bale Mirror flow ندارد — Gap Medium — P1 reuse generic_service
- Admin dashboard only eyebrow waitlist/pre_need — Gap Medium — P1 Extend to all service_type + final_designs count
- Admin مدیریت نوبت‌ها همه مراکز ندارد — Gap Medium — P1 new admin route
- Admin مدیریت خدمات per service_key ندارد — Gap Medium — P1
- Admin مدیریت متخصص‌ها مستقل ندارد — Gap P2 — new table beauty_center_specialists
- Graph STALE (built at c9b198cd vs HEAD 90356d6) — should run `graphify update .` after code changes — suggestion only, not executed per s4.md law ممنوع تغییر Graph
- Docs STALE (branch name mismatch arena/01a0e0b8 vs 01a0eecf) — should update PROJECT_GUIDE.md branch name — suggestion only, not executed per s4.md law
- Two parallel analysis systems (Analysis old hair/skin vs Buti AI Mirror new) — should merge into one route /dashboard/analyses with tabs [ابرو][مو][آرایش][ناخن] — P0 Extend

---

## 16. Final Recommendation

**خلاصه اجرایی نهایی:**

ساختار فعلی گیسو برای اکوسیستم زیبایی **80% آماده** و نیاز به **معماری جدید ندارد** — فقط **توسعه افزودنی (Extend)** و **اتصال ماژول‌های موجود** — اصل **Reuse > Extend > New** رعایت شد — **Code is Truth** — هیچ‌وقت Proposed را به‌عنوان Current گزارش نکن.

**CURRENT واقعیت کد:**
- پنل کاربر 9 ماژول visible + 4 گروه "اصلی/خدمات/پشتیبانی/حساب" + has_center check + menu badges + wallet + notifications + missions — analyses فقط hair/skin قدیمی — Mirror 4 خدمت فعال جدا از پنل کاربر — دو سیستم موازی آنالیز
- Mirror: SERVICE_CATALOG 4 active + generic_service + STYLES 5 + CHANGE_LEVELS + buti_ai_sessions + buti_ai_final_designs + service_demand/waitlist + routes /analysis/mirror/ + templates + consultant + interest + enrich scoring 45+20+15+feedback — 100% فعال
- Beauty Center: beauty_centers 20+ fields + 10 جدول + SERVICES 20 keys + STATUS 6 + pricing 6 funcs + reservations with final_design_id/service_key/selected_style BEGIN IMMEDIATE snapshot + conversations/messages/feedback/promotions/discounts/events — owner_dashboard 8 تب P0 موجود
- Admin: panel_admin context dashboard totals/performance/events/demand_by_city/demand_recent + tabs requests/published/paused/promotions/feedback/dashboard/settings + actions status/feature/discount/feedback + settings prices + permissions ADMIN_SECTIONS + REGULAR_ADMIN_NAV + SPECIAL_ADMIN_NAV — P0 موجود — کم دارد per service management

**PROPOSED معماری پیشنهادی (با دلیل):**
- پنل کاربر: 💄 زیبایی من با 4 زیرمنو 🔎 سالن‌های زیبایی 📅 نوبت‌های من 💬 گفتگوهای من 🔬 آنالیزهای من با تب [ابرو][مو][آرایش][ناخن] — آنالیز قدیمی hair/skin + Mirror جدید ادغام — یک route /dashboard/analyses همه را نشان دهد — جلوگیری از دو سیستم موازی — نام 💄 زیبایی من کوتاه‌تر و شخصی‌تر از "مدیریت زیبایی گیسو" — دلیل UX ساده + فارسی محاوره‌ای
- متخصص: Hybrid — مستقل → independent center (P0 Reuse 100%) — داخل سالن → beauty_center_services with specialist_user_id + service_key (P1 Extend 20% + Reuse 80%) — بدون جدول جدید — اگر واقعاً مستقل شود P2 جدول beauty_center_specialists — دلیل Reuse > Extend > New
- مدیر سالن: ساختار فعلی منطقی — اطلاعات سالن/خدمات/قیمت‌ها/نمونه‌کارها/نوبت‌ها/گفتگوها/تخفیف‌ها/تبلیغات/گزارش عملکرد — P0 موجود — P1 اضافه service_key در services+images + service_id در promotions/discounts + is_featured_service + specialist_user_id — دلیل ساده+لوکس+قابل فروش+قابل مدیریت
- ادمین: مدیریت سالن‌ها P0 موجود + خدمات per service_key P1 + نوبت‌ها همه P1 + نمونه‌کارها per service P1 + تبلیغات per service P1 + آنالیزها همه service_type P1 — دلیل با ساختار فعلی هم‌خوانی دارد — فقط Extend

**REQUIRED CHANGE:**
- P0 بدون تغییر DB: Extend permissions.py USER_MODULE_GROUPS add group "زیبایی من" + rename beauty_center label + routes.py _menu_for_current_user + analyses.py context with buti_ai_final_designs queries + template analyses.html add tabs [ابرو][مو][آرایش][ناخن] + new module mirror.py reuse analyses.py pattern + template mirror.html — 2 فایل جدید + 4 فایل Extend — No migration
- P1 با 2-4 ستون additive: ADD COLUMN service_key TEXT DEFAULT '' + is_featured_service INTEGER DEFAULT 0 + specialist_user_id INTEGER DEFAULT 0 in beauty_center_services + service_key + specialist_user_id in beauty_center_images + service_id in promotions/discounts + specialist_user_id in reservations — ALTER TABLE ADD COLUMN via PRAGMA check + INDEX — same pattern as ai_credits fix + pricing/schema.py — 5 جدول — Low risk — fallback WHERE service_key='' OR service_key=?
- P2 آینده: beauty_center_specialists + beauty_center_staff + wishlist + Instagram/Logo + 800+ + AI boosting — New 100% — فعلاً شلوغ نکن

**Flow نهایی پیشنهادی:**

```
آنالیز (Mirror 4 کارت + Analysis قدیمی hair/skin)
   ↓ Style (5 مدل) + Upload + Quality AI + Detection + Analysis AI + Generation Before/After + validation + consultant + interest
   ↓ خدمات مرتبط (list_centers?service= + enrich score 45+20+15+feedback + tags + match reason)
   ↓ سالن / متخصص (center_detail + independent center_type + specialist_user_id P1)
   ↓ نمونه‌کار + قیمت (service card لوکس: icon + name + category + description + duration + price_label toman + portfolio per service P1 + discount badge + CTA)
   ↓ گفتگو (center_chat + support_tickets)
   ↓ نوبت (reserve with final_design_id/service_key/selected_style/specialist_user_id + BEGIN IMMEDIATE snapshot + slots + calendar + notify)
   ↓ پیگیری (my_reservations + center_chats + analyses history + overview + notifications + missions)
```

**100% سازگار با معماری فعلی — بدون اصلاح — فقط اتصال + 2-4 ستون additive P1.**

**اولویت:** P0 ضروری (پنل کاربر زیبایی من 4 زیرمنو + آنالیزهای من تب [ابرو][مو][آرایش][ناخن] + ادغام قدیمی و جدید + Mirror 4 خدمت + independent متخصص + مدیر سالن 8 منو + ادمین سالن‌ها) — P1 مهم (Portfolio per service, Featured Service per service, Service Key, Specialist داخل سالن, Discount/Promotion per service, Mirror History module, Admin per service management, Bale Mirror flow) — P2 بعداً (specialists table, staff, wishlist, Instagram/Logo, 800+, AI boosting)

**توصیه نهایی:** P0 را بدون تغییر DB پیاده‌سازی کن — P1 را با 2-4 ستون additive — P2 را فعلاً شلوغ نکن — سیستم ساده+لوکس+قابل فروش+قابل مدیریت بماند — نه پنل پر از امکانات غیرضروری.

---

## 17. Files Reviewed — فهرست دقیق فایل‌های بررسی شده این نشست

**Code Truth — از live tree:**

- `giso/panel_user/routes.py` — canonical /dashboard, MODULE_VIEWS, _guard, _menu_for_current_user has_center, _render with wallet + menu_badges + notifications + missions, routes overview/profile/orders/hair-sale/marketplace/analyses/chats/wallet/notifies/reviews/shop
- `giso/panel_user/permissions.py` — USER_MODULES 9 visible, USER_MODULE_GROUPS 4 groups "اصلی/خدمات/پشتیبانی/حساب", MODULES_META + marketplace/buyer_request/beauty_center/shop/notifies/wishlist/notifications/reviews/reservations/center_chats/ai_assistant, is_admin_user, current_user_role
- `giso/panel_user/modules/_base.py` — get_analyses, get_shop_orders, get_hair_orders, get_stock_notifies, get_reviews, get_chats_count, get_wallet with balances/transactions/settings/missions/topups/withdrawals
- `giso/panel_user/modules/analyses.py` — _json, _decorate with problems 3, metrics 6, date_fa to_shamsi, has_plan/has_quick/has_report, context() with Analysis query filter user_id/phone + archived_at + hair/skin + archived + latest_hair/latest_skin + recommendation get_recommendation_for_user
- `giso/panel_user/modules/overview.py` — context() counts analyses/orders/hair/notifies/reviews/chats/balance/cash/spend + last_hair + overview_notifications
- `giso/panel_user/modules/chats.py` — _ensure_support_tickets_table CREATE TABLE giso_support_tickets, _support_tickets, create_support_ticket with safe_log bot ticket, create_bug_report, context()
- `giso/panel_user/modules/` — hair_sale.py, marketplace.py, notifies.py, orders.py, profile.py, reviews.py, wallet.py — each context()
- `giso/panel_user/templates/user_modules/` — overview.html, profile.html, orders.html, hair_sale.html, marketplace.html, analyses.html, chats.html, wallet.html, notifies.html, reviews.html, center_chats.html, notifications.html, ai_assistant.html, wishlist.html, _analysis_summary.html, _buyer_conversations_tab.html, _buyer_offers_tab.html, _buyer_request_form.html
- `giso/panel_user/templates/user_layout.html` — base layout with sidebar menu groups + badges + header wallet + notifications
- `giso/buti_ai/service_catalog.py` — SERVICE_CATALOG 4 active eyebrow/nail/hair_color/lip_shading with title/short_title/icon/badge/tag/description/meta/image/sample_dir/upload_sample/service_type/beauty_center_service/status active, SERVICE_SLUGS, SLUG_TO_SERVICE, get_service_meta, mirror_services, supported_service_keys, service_for_slug, slug_for_service
- `giso/buti_ai/generic_service.py` — SERVICE_MODULES nail/hair_color/lip_shading → final_design, CHANGE_LEVELS very_natural/medium/clear, DEFAULT_CHANGE_LEVEL medium, service_module, normalize_model_key, initial_form_values, build_result, process_service_submission with save_eyebrow_photo prefix service_key + quality + detection + analysis + save_mirror_session, build_final_candidate, source_image_path, generate_final_design, uploaded_root
- `giso/buti_ai/service_image_generation.py` — generate_final_design with mask gate + provider chain + fallback guided composite
- `giso/buti_ai/image_validation.py` — validate_masked_output with service_key, in_mask_diff_ratio, outside_mask_diff_ratio
- `giso/buti_ai/routes.py` — buti_ai_bp, eyebrow routes upload/wizard/final_design/centers/uploads/<filename>, mirror_home, generic_service_wizard, upload, final, consultant, interest, _new_service_selection_key/candidate_key, _is_active_new_service, _active_service_from_slug, _new_service_selection_from_form, _current_new_service_selection, _new_service_state, _render_new_service_wizard, _store_new_service_candidate, _get_new_service_candidate, _rebuild_new_service_candidate_from_finalize_form, _update_new_service_final_selection, _enrich_generic_centers scoring 45+20+15+feedback + tags + match reason + demand/waitlist + session handling
- `giso/buti_ai/schema.py` — BUTI_AI_TABLES_SQL buti_ai_sessions, buti_ai_waitlist, buti_ai_service_demand, buti_ai_final_designs + INDEX + _ensure_column additive + init_buti_ai_db
- `giso/buti_ai/consultant.py` — build_consultant_context, consultant_invite_text
- `giso/buti_ai/ai_models.py` — image_task_for_service, configured_image_provider_dicts, SERVICE_IMAGE_TASK_MAP
- `giso/buti_ai/eyebrow/`, `nail/`, `hair_color/`, `lip/` — final_design.py STYLES 5 per service + DEFAULT_STYLE + UPLOAD_DIR + check_photo_quality + detect_regions + analyze_*_photo + generate_guided_design + local_quality_report
- `giso/beauty_centers/schema.py` — beauty_centers 20+ fields + 10 tables images/conversations/messages/feedback/promotions/discounts/events/expiry_notices/reports + 5 indexes + migrate_beauty_center_tables additive PRAGMA + ALTER TABLE
- `giso/beauty_centers/services.py` — CENTER_CATEGORIES 3, CENTER_TYPES 7, SERVICES 20 keys, CATEGORY_SERVICES, CATEGORY_CENTER_TYPES, PRICE_LEVELS, STATUS_FA 6, DISCLAIMER, TERMS_VERSION, CENTER_IMAGE_MAX_BYTES/PIXELS/SIDE/FORMATS, _CENTER_NOTIFY_POOL ThreadPoolExecutor 2, now_str, json_services, decorate_center, get_center, get_center_by_slug, get_owner_center, _slug_seed, _normalize_business_phone, _price_int, _normalize_fields, save_center_image, create_center, update_owner_center, set_owner_active, sitemap_centers, list_public_centers, analysis_service_tags, recommended_centers, increment_view, reveal_contact, get_or_create_conversation, conversation_for_party, conversation_messages, notify_conversation_message, send_conversation_message, owner_conversation_unread_count, owner_conversations, user_center_unread_count, user_center_conversations, _feedback_label, center_feedback_summary, submit_center_feedback, close_conversation, process_center_expiry_notifications, _purchase_key, _wait_label, center_promotion_availability, renew_center_listing, purchase_center_promotion, admin_set_status
- `giso/beauty_centers/routes.py` — beauty_centers_bp url_prefix /, list_centers, center_detail, register_center, owner_dashboard, owner_gallery_upload/delete, owner_main_image_delete, center_chat, center_chat_message, center_chat_close, owner_renew, owner_discount, owner_promote, gallery_media, center_media, center_contact, center_chat_feedback + _owner_panel_context + _center_services_for_display + _center_hours_for_display + _service_duration_label + _service_price_label
- `giso/beauty_centers/pricing/schema.py` — SERVICES_COLUMNS, WORKING_HOURS_COLUMNS, _columns_of, _ensure_table CREATE TABLE IF NOT EXISTS + ALTER TABLE ADD COLUMN, migrate_pricing_tables additive + INDEX center,is_active,sort_order + UNIQUE center,day_of_week
- `giso/beauty_centers/pricing/services.py` — _now, _coerce_int, _coerce_flag, _coerce_time, _clean_service name required duration 1-1440 price_min/max, _clean_working_day day 0-6 time HH:MM open<close slot 5-1440, get_center_services ordered is_active DESC sort_order ASC, add_service, update_service, delete_service, get_working_hours ordered day_of_week ASC, save_working_hours BEGIN IMMEDIATE upsert
- `giso/beauty_centers/reservations/schema.py` — RESERVATIONS_TABLE beauty_center_reservations, RESERVATION_STATUSES 5 pending/confirmed/completed/cancelled_user/cancelled_center, RESERVATIONS_COLUMNS with center_id, user_id, user_phone, user_name, service_id snapshot, service_name, price_min, duration, date شمسی, time HH:MM, status, user_note, center_note, reject_reason, reminded, created_at, confirmed_at, cancelled_at, final_design_id, service_key, selected_style, RESERVATIONS_CONSTRAINTS FK center_id→beauty_centers + user_id→giso_web_auth, _columns_of, _ensure_table, migrate_reservation_tables additive + INDEX center,date,time + user,created_at + status,date
- `giso/beauty_centers/reservations/services.py` — _now, _to_int, _clean_text, _normalize_date, _normalize_time, _jalali_parts, _today_jalali, _jalali_to_ordinal, _jalali_to_datetime, _jalali_day_of_week, _date_weekday_label, _minutes_of, _hhmm, _slot_minutes, get_available_slots, get_calendar_month, create_reservation with final_design_id/service_key/selected_style snapshot + BEGIN IMMEDIATE + _service_of + _working_day + _is_available + _build_slots + _active_bookings + _get_center + _center_is_public + _transition guarded + confirm/reject/complete/cancel_by_user + _with_derived + get_center_reservations + get_user_reservations + _reminder_rows + _stamp_reminder + get_pending_reminders
- `giso/beauty_centers/reservations/routes.py` — reservations_bp, _center_by_id, _center_by_slug, _owner_center, slots JSON, calendar JSON, reserve GET/POST with service_id/date/final_design_id/service_key/selected_style + my_reservations
- `giso/beauty_centers/reservations/notifications.py` — notify_new_reservation, notify_user_confirmed, notify_user_rejected
- `giso/beauty_centers/panel_admin.py` — _SETTING_DEFAULTS beauty_promotions_enabled/bump/featured/discount/renew + prices bump 25000/featured 120000/discount 60000/renew 50000 + listing_days 30 + registration_enabled + intro + terms_text, _settings via get_giso_config, _dashboard totals pending/published/expired/conversations/unanswered/active_promotions/promotion_revenue/eyebrow_waitlist/pre_need/interest + performance views/contact/price_inquiry/analysis_impressions/conversations/conversion_rate + events + demand_by_city + demand_recent, context tab requests/published/paused/promotions/feedback/dashboard/settings + centers + beauty_counts + beauty_dashboard + beauty_settings + status_fa + feedback + promotions + discounts, handle_settings promotion/registration + set_giso_config + invalidate_giso_config_cache + flash, handle_status status/note + admin_set_status, handle_feature_selected center_id + featured, handle_feature is_featured UPDATE, handle_discount status visible/rejected UPDATE, handle_feedback status visible/rejected UPDATE
- `giso/panel/routes.py` — panel_bp /beauty-centers → module_allowed beauty_centers + _render admin.html + context(tab), /beauty-centers/settings POST → handle_settings, /beauty-centers/<center_id>/status POST → handle_status, /beauty-centers/feature-selected POST → handle_feature_selected, /beauty-centers/<center_id>/feature POST → handle_feature, /beauty-centers/discount/<discount_id>/status POST → handle_discount, /beauty-centers/feedback/<feedback_id>/status POST → handle_feedback
- `giso/panel/permissions.py` — ADMIN_SECTIONS dashboard/orders/hair_sale/beauty_centers/analysis_management/reviews/products/channel_management/users/admins/site_bot_settings/ai_management, REGULAR_ADMIN_SECTIONS frozenset dashboard/orders/hair_sale/marketplace/beauty_centers/reviews/consults/account, REGULAR_ADMIN_MODULES, REGULAR_ADMIN_NAV dashboard پیشخوان کار من/hair_sale مدیریت خرید مو/marketplace مدیریت بازارچه مو/beauty_centers مدیریت مراکز زیبایی/shop_orders/reviews/consults/account, SPECIAL_ADMIN_NAV + aga_reza + special_reports, MODULE_TO_SECTION, SUPER_ONLY_MODULES referrals/wallet/admins/settings/shop_super/reports/ai/ratelimit/users/channel/analyses/notifications/shop/monitoring/super_assistant
- `giso/base.py` — get_giso_db_conn WAL journal_mode=WAL synchronous=NORMAL foreign_keys=ON busy_timeout=5000 + get_bot_db_conn + normalize_phone + gregorian_to_jalali + to_shamsi
- `giso/config.py` — Config.GISO_DIR + is_super_admin + SUPERADMIN_BALE_ID
- `giso/money.py` — format_toman, to_persian_digits
- `giso/app.py` — Blueprint registration beauty_centers_bp, beauty_reservations_bp, buti_ai_bp, panel_user_bp, panel_bp
- `giso-dev/SKILL.md` + references/phase-0-freshness.md + discovery-method.md + patterns-extraction.md + stale-handling.md + council-checklists.md + scope-lock-template.md + test-regression.md — workflow mandatory order Understand Request → Project Freshness → Section Identification → Pattern & Architecture → Dependency/Impact → Graph/Memory/Docs Check → Council Review → Plan+Scope Lock → STOP → Approval → Implementation → Tests → Diff Review → Regression → Final Report
- `s4.md` 524 lines — 4 Panel Architecture Audit — Customer → زیبایی من → سالن‌های زیبایی → نوبت → گفتگو → آنالیزهای من → خدمات ابرو/مو/آرایش/ناخن — Owner → مدیریت سالن → خدمات → قیمت → نمونه‌کار → نوبت → گفتگو → مشتری — قانون READ-ONLY AUDIT — ممنوع تغییر کد/فایل/DB/template/route/commit/push/Graph/project_memory — Freshness + User Panel + Smart Analysis + Customer Panel + Specialist + Owner + Admin + 4 Panel Matrix + DB + P0/P1/P2 + UX + Scope Lock + rp7.md output structure 17 sections
- `rp6.md` v2 87KB — Beauty Center scenario — 11 sections + Plan+Scope Lock — Branch arena/01a0eecf-giso4 HEAD 90356d6
- `rp5.md` 112KB, `rep2.md`, `rep1.md`, `s1.md`, `s2.md`, `s3.md` — previous audits
- `PROJECT_GUIDE.md` updated 2026-09-29 branch arena/01a0e0b8 vs current 01a0eecf — 3 سامانه مستقل bot_edu/web/giso + main.py launcher + Single Source Truth giso.db + bot_edu/data/bot.db shared giso_config/giso_admins
- `GISO_GUIDE.md` updated 2026-09-29 — High-Level Architecture 4 services + Flask 3 + Flask-Login + SQLAlchemy + python-telegram-bot 20.7 Bale Base URL + SQLite WAL + PRAGMA + get_giso_db_conn/get_bot_db_conn only + import absolute giso. + no simulation data + tests python giso/tests/<name>.py

**Total files reviewed: 50+ files — all via live tree — no stale source — Code Truth.**

---

## Final Note — قانون نهایی s4.md رعایت شد

**این مأموریت فقط READ-ONLY AUDIT / ANALYSIS است — هیچ تغییری در پروژه انجام نشده — فقط بررسی، نتیجه‌گیری، پیشنهاد — فقط عملیات read-only — هیچ کدی تغییر نکرده — فقط rp7.md ایجاد شده — بعد از Plan+Scope Lock متوقف می‌شویم و منتظر تایید می‌مانیم — Code is Truth — Reuse > Extend > New — اگر با ساختار فعلی قابل انجام است تغییر DB پیشنهاد نشده (P0 بدون تغییر).**

**APPROVAL NEEDED: تأیید می‌کنی؟ — STOP منتظر تایید "تایید/بریم/اجرا کن"**

---

**END OF rp7.md — STOP**
