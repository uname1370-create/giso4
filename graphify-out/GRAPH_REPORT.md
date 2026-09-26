# Graph Report - giso4  (2026-09-26)

## Corpus Check
- cluster-only mode — file stats not available

## Summary
- 7755 nodes · 24200 edges · 226 communities (197 shown, 29 thin omitted)
- Extraction: 89% EXTRACTED · 11% INFERRED · 0% AMBIGUOUS · INFERRED: 2738 edges (avg confidence: 0.86)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `49e41dfd`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- ai_db.py
- bot_edu/handlers.py
- mkb
- route
- redirect
- logging
- _run_async
- chart.umd.min.js
- button_handler
- giso/bot.py
- analysis.py
- render_template
- beauty_centers/routes.py
- format_toman
- giso/app.py
- giso/wallet.py
- gemini_proxy_manager.py
- an
- ai_runtime.py
- giso/ai_brain.py
- get_giso_db_conn
- beauty_centers/services.py
- ui.py
- base.py
- super_assistant.py
- s
- pathlib
- ns
- panel_user/routes.py
- test_bot_group_b.py
- bot_user_actions.py
- bot_admin_utils.py
- bot_edu/config.py
- proxy_manager.py
- seo_jobs.py
- create_app
- va
- test_ai_runtime.py
- giso/models.py
- wallet_balepay.py
- users.py
- test_security_permissions_fix.py
- test_ai_discovery.py
- enricher.py
- no
- giso_admin.py
- bn
- os
- Analysis
- referrals.py
- tn
- admin_service.py
- beauty_centers/bot_handlers.py
- _admin_kb
- hair_sale_steps.js
- bot_edu/bot.py
- test_checkpoint_backup.py
- ai_runtime_policy.py
- notifications/core.py
- bot_helpers.py
- test_panel_phase5.py
- bot_edu/ai_brain.py
- reservations/services.py
- channel_importer.py
- _base.py
- n
- bot_edu/mentor_service.py
- _send_db_backup
- ai_credits.py
- test_user_profile_site_bot_sync.py
- test_panel_phase52.py
- db.py
- test_bot_hair_phase_fix.py
- test_panel_authz_hair_shop.py
- _analysis_report
- test_notifications_module.py
- main.py
- test_panel_phase51.py
- test_ai_clean_registry.py
- .getContext
- web_ai/__init__.py
- get_bot_db_conn
- bot_hair_admin.py
- modules/settings.py
- recovery.py
- test_admin_ai_panel.py
- marketplace/routes.py
- zt
- db_pg_tools.py
- marketplace/services.py
- test_shop_phase_b.py
- consultant_context.py
- notifications/helpers.py
- panel/modules/marketplace.py
- User
- backup/core.py
- special_assistant.py
- _setup_db
- bug_reports.py
- bt
- guest_interviewer.py
- UserJourneyContext
- services/mentor_service.py
- set_setting
- pricing/services.py
- HairListing
- test_two_layer_storage.py
- ai_health.py
- test_fix_phase_ab.py
- test_wallet_unified.py
- safe_log
- to_shamsi
- CareerInterviewAgent
- monitoring_insights.py
- shop.js
- ai_widget.js
- platform_runtime.py
- env_loader.py
- backup/helpers.py
- test_shop_phase_a.py
- widget_service.py
- auth.py
- web/models.py
- test_edu_giso_remote_management.py
- reservations/routes.py
- panel/modules/analyses.py
- consults.py
- test_final_fixes.py
- learning_mentor.py
- test_bot_fix_group_a.py
- get_giso_site_config
- giso_handlers.py
- typing
- authz.py
- _handle_ai_state
- is_admin_demoted
- consultant.js
- guest_analyzer.py
- inject_helpers
- test_fix_phase_p0p1p2.py
- PgCursor
- maybe_send_daily_digest
- test_shop_phase_a2.py
- panel_tour.js
- unittest_mock
- clamp_int
- db_engine.py
- static/manifest.json
- Review
- reservations/schema.py
- get_pending_reminders
- test_hair_sale_back.py
- test_shop_ui_fix.py
- roadmap_builder.py
- marketplace_settings
- buti_ai/routes.py
- take_backup
- rank_daily.py
- recommendation_service.py
- rs
- DummyFlask
- PgConn
- ai_mentor/core.py
- ai_assistant.js
- giso_notifications.js
- e2e_check.py
- test_consultant.py
- test_marketplace_notification_delivery.py
- _ask_consultant_bot
- DummyDB
- handle_recovery_download
- test_report_dual_cta.py
- RoadmapBuilderAgent
- _MsgShim
- normalize_phone
- build_beauty_centers_prompt
- marketplace/__init__.py
- panel.js
- PanelCsrfGuardTests
- test_sensitive_register.py
- test_special_site_role.py
- get_calendar_month
- sqlite_ddls
- execute_pending_restart
- giso_idle.js
- HairSaleResultVisibilityTests
- test_p0_wallet_referral_retirement.py
- test_spend_mission_expansion.py
- reports.py
- invoices.py
- fa_display.js
- test_beauty_centers_stage10_analysis_integration.py
- test_beauty_centers_stage13_home_card.py
- test_display_checks.js
- test_direct_and_both_finalize_emit_each_admin_notification_once
- test_phase_broadcast_campaigns.py
- migrate_beauty_center_tables
- data/manifest.json
- _ManagedConnection
- context
- money_fa.js
- password_meter.js
- _SharedLock
- active_platform_bots
- _save_users
- sync_deleted_users_from_db
- AdminPermissions
- enrichment_final_report.py
- reset
- channel.py
- web/static/js/main.js
- _env_str_list
- invalidate_user_cache
- unregister_platform_bot
- AdminAddCheck
- services/__init__.py
- fetch
- pg_backup.sh
- _fetch_admin_request_identity

## God Nodes (most connected - your core abstractions)
1. `get_giso_db_conn()` - 561 edges
2. `create_app()` - 390 edges
3. `_run_async()` - 289 edges
4. `redirect()` - 287 edges
5. `url_for()` - 280 edges
6. `flash()` - 247 edges
7. `route()` - 223 edges
8. `button_handler()` - 191 edges
9. `User` - 181 edges
10. `handle_callback()` - 162 edges

## Surprising Connections (you probably didn't know these)
- `_get_config()` --calls--> `get_giso_config()`  [INFERRED]
  giso/panel/modules/ratelimit.py → bot_edu/giso_admin.py
- `set_archive_days()` --calls--> `set_giso_config()`  [INFERRED]
  giso/panel/modules/notifications/helpers.py → bot_edu/giso_admin.py
- `set_sound_on()` --calls--> `set_giso_config()`  [INFERRED]
  giso/panel/modules/notifications/helpers.py → bot_edu/giso_admin.py
- `button_handler()` --calls--> `InlineKeyboardButton`  [INFERRED]
  bot_edu/handlers.py → giso/bot.py
- `_edubot_restart_flow()` --calls--> `InlineKeyboardButton`  [INFERRED]
  bot_edu/handlers.py → giso/bot.py

## Import Cycles
- None detected.

## Communities (226 total, 29 thin omitted)

### Community 0 - "ai_db.py"
Cohesion: 0.02
Nodes (249): ambiguous_python_import_33afecff6bbf, handle_aim_admin_callback(), handle_aim_admin_state(), پردازش callbackهای aim_a_. خروجی True یعنی پردازش شد., add_trend_to_path(), analyze_trends_with_ai(), _ask(), can_afford() (+241 more)

### Community 1 - "bot_edu/handlers.py"
Cohesion: 0.03
Nodes (187): ambiguous_python_import_a49c75c2a539, ambiguous_python_import_c922423bfda3, ambiguous_python_import_de9c1ccb21fd, ambiguous_python_import_f14fed1f74cf, ثبت تمام handler‌ها روی یک Application (مشترک بین همه پلتفرم‌ها)., _register_handlers(), add_points(), add_user_credits() (+179 more)

### Community 2 - "mkb"
Cohesion: 0.03
Nodes (181): ambiguous_python_import_820962ad12bb, ambiguous_python_import_8a81d2d8f409, _edit(), _notify_user_purchase(), ai_admin.py — هندلرهای ادمینِ «یار هوشمند شغلی». پیشوند callback: aim_a_ |…, اطلاع نتیجهٔ فیش به کاربر — از ربات همان پلتفرمی که فیش را فرستاده. خروجی: True…, _animate(), _begin_interview() (+173 more)

### Community 3 - "route"
Cohesion: 0.04
Nodes (168): context_processor, data نمونه: 'ua|anal|last' یا 'ua|mkt|stats|12'. خروجی: (text, kb_rows)., route(), register(), broadcasts_center(), broadcasts_center_create(), broadcasts_center_status(), save() (+160 more)

### Community 4 - "redirect"
Cohesion: 0.04
Nodes (158): before_app_request, admin_analysis_note(), ثبت درخواست محصول (برای محصولاتی که در گیسو موجود نیستند)., request_product(), _check_giso_admin_access(), admin_admins(), admin_admins_permission(), admin_analyses() (+150 more)

### Community 5 - "logging"
Cohesion: 0.04
Nodes (128): datetime, Return only indexable center fields for sitemap generation., sitemap_centers(), giso/buti_ai/services.py — منطق ذخیره‌سازی نشست‌ها و ثبت در لیست انتظار آینه…, audit_fix_images(), backup_db(), build_report(), enrich_descs() (+120 more)

### Community 6 - "_run_async"
Cohesion: 0.04
Nodes (142): check_ai_provider(), get_ai_provider(), toggle_use_proxy(), is_chat_enabled(), _is_super_admin(), بررسی سوپرادمین اصلی گیسو (1191639507 یا 09156012931)., _ensure_support_tickets_table(), _get_admin_analysis_stats() (+134 more)

### Community 7 - "chart.umd.min.js"
Cohesion: 0.03
Nodes (65): ai(), ao(), average(), be(), beforeDatasetDraw(), beforeDatasetsDraw(), beforeDraw(), cn() (+57 more)

### Community 8 - "button_handler"
Cohesion: 0.03
Nodes (117): ambiguous_python_import_930292e873b7, ambiguous_python_import_f9282b2c380a, pricing_info_text(), _c(), متن تعرفه‌ها — از ai_settings خوانده می‌شود (فاز ۲، بهبود ۴)., _bale_active_recent(), fa_num(), get_platform_admins() (+109 more)

### Community 9 - "giso/bot.py"
Cohesion: 0.03
Nodes (114): get_superadmin_action_capabilities_text(), touch_user_activity(), _demote_giso_user_admin(), invalidate_giso_config_cache(), پاک‌کردن کش تنظیمات (در صورت None کل کش پاک می‌شود)., خواندن تنظیمات محدودیت تحلیل (rate_limit_*) از bot.db. حالت سالم: مقادیر واقعی…, read_rate_limit_config(), _admin_analysis_group_kb() (+106 more)

### Community 10 - "analysis.py"
Cohesion: 0.03
Nodes (112): analysis(), analysis_hair(), analysis_plan(), analysis_skin(), Blueprint, _build_plan_context(), _build_questions(), _call_text_ai() (+104 more)

### Community 11 - "render_template"
Cohesion: 0.04
Nodes (101): ambiguous_python_import_45d56ffcb377, ambiguous_python_import_a705073b9915, render_template(), _sa_reply(), mashhad_landing(), MarketplacePhase2StaticTests, mentor_service, panel_service (+93 more)

### Community 12 - "beauty_centers/routes.py"
Cohesion: 0.05
Nodes (99): center_chat(), center_chat_close(), center_chat_feedback(), center_chat_message(), center_contact(), center_detail(), _center_hours_for_display(), center_media() (+91 more)

### Community 13 - "format_toman"
Cohesion: 0.04
Nodes (99): handle_private_photo(), _download_photo_as_webp(), دانلود عکس پست کانال و ذخیره WebP در پوشه آپلود فروشگاه., format_toman(), قالب رسمی مبلغ در UI و اعلان‌ها: «۱۲۳,۴۵۶ تومان»., channel_pending_text(), get_pending_products(), new_orders_text() (+91 more)

### Community 14 - "giso/app.py"
Cohesion: 0.04
Nodes (86): collections, flask, flask_login, install(), جایگزینی _final_analysis در ماژول analysis (lookup در زمان فراخوانی)., Override امن برای _final_analysis — بدون بازنویسی کل analysis.py اعمال از…, _admin_panel_issue_code(), cleanup_temp_uploads() (+78 more)

### Community 15 - "giso/wallet.py"
Cohesion: 0.05
Nodes (92): set_giso_config(), _set_config_value(), context(), _rank_daily_report(), مرکز مالی سوپرادمین: مأموریت، شارژ، تسویه، رتبه‌ها، اعتبار خدمات و تنظیمات., گزارش خواندنی واریزهای روزانهٔ رتبه (تاریخ/تعداد/مبلغ) — بدون اجرای واریز., _cleanup(), اعتبار مصرفی اولیهٔ رایگان: تنظیم سوپرادمین + اعطای ایدمپوتنت + کارت‌های هدر. (+84 more)

### Community 16 - "gemini_proxy_manager.py"
Cohesion: 0.04
Nodes (83): asyncio, clear_manual_proxies(), _country_denied(), _detect_country(), _fa_num(), format_test_report(), _gemini_api_key(), _gemini_native_base() (+75 more)

### Community 17 - "an"
Cohesion: 0.05
Nodes (27): afterDatasetsUpdate(), an(), ct(), dataset(), fs(), ge(), generateLabels(), index() (+19 more)

### Community 18 - "ai_runtime.py"
Cohesion: 0.07
Nodes (90): admin_test_prompt(), _build_action_preview(), _build_admin_cta_actions(), build_admin_task_hints(), build_provider_status_report(), build_site_widget_context(), build_site_widget_fallback_reply(), build_site_widget_prompt() (+82 more)

### Community 19 - "giso/ai_brain.py"
Cohesion: 0.05
Nodes (84): add_ai_provider(), _ai_check_cloudflare(), _ai_check_openai(), _ai_err(), _ai_jloads(), _ai_now(), ai_pick_preferred_model(), ai_provider_count() (+76 more)

### Community 20 - "get_giso_db_conn"
Cohesion: 0.05
Nodes (80): ux_events_api(), campaign_list(), create_campaign(), ensure_tables(), process_site_bot_batch(), پردازش بخشِ بله‌ی صف پیام سراسری با send_bot_push سایت (بدون نیاز به ربات در…, Durable broadcast campaigns: site inbox immediately, Bale in batches of ten., _target_users() (+72 more)

### Community 21 - "beauty_centers/services.py"
Cohesion: 0.04
Nodes (68): concurrent_futures, _http_post(), _token_from_db(), _token_from_env(), Safety prompt for AI references to database-backed Beauty Centers., Beauty Centers: a modular, introduction-only directory for Giso., Phase A pricing: beauty center services and working hours., Idempotent additive schema for the introduction-only Beauty Centers MVP. (+60 more)

### Community 22 - "ui.py"
Cohesion: 0.04
Nodes (81): ambiguous_python_import_784aa9476e70, apply_lesson(), check_membership(), full_access_check(), get_cash_sale_setting(), get_completed_lids(), get_feature_rule(), _get_lesson_paid_key() (+73 more)

### Community 23 - "base.py"
Cohesion: 0.04
Nodes (67): get_persian_status(), match_user_across_systems(), notify_user_bot_by_order(), giso/base.py — لایه پایه و مشترک تمام ماژول‌های گیسو (دیتابیس، احراز هویت،…, تبدیل وضعیت انگلیسی مو به فارسی., بررسی و انطباق کاربر در دو جدول giso_web_auth (سایت) و giso_users (ربات)., ارسال اعلان کامل درخواست جدید فروش مو همراه با عکس برای ادمین‌ها در بله., ارسال پیام به کاربر ربات در بله + آینهٔ اعلان در پنل کاربر سایت (توسط ادمین یا… (+59 more)

### Community 24 - "super_assistant.py"
Cohesion: 0.06
Nodes (73): jsonify(), audience_users(), campaign_list(), create_campaign(), ensure_tables(), _now(), process_batch(), _push_site_notification() (+65 more)

### Community 25 - "s"
Cohesion: 0.04
Nodes (40): a(), aa(), Ae(), As(), b(), bo, _calculateBarIndexPixels(), determineDataLimits() (+32 more)

### Community 26 - "pathlib"
Cohesion: 0.03
Nodes (16): _feedback_label(), _default_db_path(), migrate_marketplace_tables(), Idempotent additive schema for the Giso hair marketplace MVP., Create only additive marketplace tables/indexes; safe to run repeatedly., Contracts for deterministic center score and discount-service promotion., test_score_mapping_is_deterministic(), سه باگ حیاتی دسترسی ادمین عادی: stub مرده، فروشگاه، آنالیز. (+8 more)

### Community 27 - "ns"
Cohesion: 0.05
Nodes (21): buildTicks(), ca(), _calculateBarValuePixels(), getBasePixel(), getLabelAndValue(), getLabelForValue(), getPixelForTick(), getPixelForValue() (+13 more)

### Community 28 - "panel_user/routes.py"
Cohesion: 0.05
Nodes (71): dashboard_consultant_chat(), dashboard_hair_chat(), فهرست پرسش‌وپاسخ کاربر با مراکز؛ فقط گفتگوهای متعلق به خود کاربر., user_center_conversations(), user_center_unread_count(), Wishlist, user_unread_count(), giso/panel_user/modules — ماژول‌های پنل کاربر عادی گیسو. (+63 more)

### Community 29 - "test_bot_group_b.py"
Cohesion: 0.06
Nodes (67): get_test_handlers(), _cleanup(), تست رفع نهایی مشکل «پیام /start بزنید» در بازگشت ادمین از زیرمنوها. ۱) بررسی:…, _send(), _setup_db(), test_limited_admin_back_only_allowed(), test_super_back_from_analysis_menu(), run() (+59 more)

### Community 30 - "bot_user_actions.py"
Cohesion: 0.08
Nodes (74): anal_check(), anal_consult(), anal_last(), anal_plan(), anal_products(), _btn(), center_msgs(), center_renew() (+66 more)

### Community 31 - "bot_admin_utils.py"
Cohesion: 0.05
Nodes (64): _get_giso_user(), _giso_lookup(), وضعیت کاربر در سیستم ادمین گیسو., _upsert_giso_user(), _build_smart_welcome_admin(), _build_smart_welcome_user(), _build_welcome_from_site(), _check_site_user_info() (+56 more)

### Community 32 - "bot_edu/config.py"
Cohesion: 0.06
Nodes (65): add_delivery_report(), clear_delivery_reports(), _env_int_list(), get_platform_bot(), _load_admin_link_codes(), _load_bot_commands(), _load_bot_groups(), _load_cash_sale_settings() (+57 more)

### Community 33 - "proxy_manager.py"
Cohesion: 0.05
Nodes (63): ambiguous_python_import_a24e1c8b4e02, age_text(), cache_age(), cache_file(), cache_is_fresh(), candidates_for_mode(), clear_manual_proxies(), clear_working() (+55 more)

### Community 34 - "seo_jobs.py"
Cohesion: 0.07
Nodes (51): fcntl, _ask_meta_text(), build_weekly_report(), _data_dir(), fill_empty_descriptions(), load_state(), lock_path(), main() (+43 more)

### Community 35 - "create_app"
Cohesion: 0.08
Nodes (45): create_app(), _ensure_ai_logging(), LoginManager, فاز ۳: لاگ‌های مشاهده‌پذیری موتورهای AI (مثل [AI_ATTEMPT]) در وب هم دیده شوند.…, status_fa(), Stage 12: responsive public navigation and uncluttered owner navigation., test_public_menu_link_is_server_rendered_and_marked_current_on_directory(), Stage 14: final indexability, metadata and sitemap contract. (+37 more)

### Community 36 - "va"
Cohesion: 0.07
Nodes (19): afterDraw(), afterEvent(), afterUpdate(), es(), f(), gs(), ki(), oa() (+11 more)

### Community 37 - "test_ai_runtime.py"
Cohesion: 0.08
Nodes (59): init_ai_tables(), _activity_row(), build_capability_guide(), chat_with_managed_ai(), check_daily_limit(), get_last_activity(), get_last_welcome(), get_role_capabilities() (+51 more)

### Community 38 - "giso/models.py"
Cohesion: 0.05
Nodes (55): metric_label(), Single Persian vocabulary for analysis metrics across site, bot and images., browser_fingerprint_hash(), current_device_token(), _device_correlation(), device_key_hash(), _hash_private(), ip_hash() (+47 more)

### Community 39 - "wallet_balepay.py"
Cohesion: 0.06
Nodes (48): _find_invoice_by_token(), handle_pay_start(), handle_pre_checkout(), handle_successful_payment(), ربات بله: پرداخت آنی کیف پول — هندلرهای نازک PTB. منطق مالی در…, Deep-link «/start pay_<token>» → ارسال فاکتور (sendInvoice)., باید زیر ۱۰ ثانیه پاسخ دهیم وگرنه بله پرداخت را لغو می‌کند., پرداخت قطعی → واریز idempotent کیف پول سایت + رسید در چت. (+40 more)

### Community 40 - "users.py"
Cohesion: 0.06
Nodes (54): normalize_phone(), current_password_if_matches(), _ensure_table(), load_stored_password(), فقط اگر candidate همان رمز فعلیِ هش‌شده روی حساب باشد برمی‌گردد., پس از هر نوشتن موفق رمز روی حساب، نسخهٔ رمزگذاری‌شده را برای سوپر نگه می‌دارد., remember_account_password(), analysis_register() (+46 more)

### Community 41 - "test_security_permissions_fix.py"
Cohesion: 0.09
Nodes (53): get_admin_sub_options(), Compatibility payload: all operational Hair actions are always enabled., can_access_option(), can_execute_callback(), get_visible_options(), is_regular_admin(), is_super_admin(), list_regular_admins() (+45 more)

### Community 42 - "test_ai_discovery.py"
Cohesion: 0.07
Nodes (45): _col(), _is_vision_model_id(), اجرای یک coroutine به‌صورت همگام (برای فراخوانی از کد غیر-async)., دسترسی امن به ستون ردیف (تحمل نبود ستون در دیتابیس‌های قدیمی)., run_async_sync(), _context_of(), discover_provider(), _drop_dated_duplicates() (+37 more)

### Community 43 - "enricher.py"
Cohesion: 0.07
Nodes (46): build_prompt(), call_ai_failover(), _conn(), _corpus_hit(), _download_validate(), extract_from_search_text(), _fa_tokens(), _first_block() (+38 more)

### Community 44 - "no"
Cohesion: 0.06
Nodes (17): beforeLayout(), buildLookupTable(), En, Fo(), _generate(), getDecimalForValue(), _getTimestampsForTable(), ia() (+9 more)

### Community 45 - "giso_admin.py"
Cohesion: 0.11
Nodes (45): add_giso_admin(), check_admin_candidate(), _connect(), create_admin_request(), delete_giso_admin(), find_giso_admin(), find_giso_admin_by_phone(), find_known_bale_id_by_phone() (+37 more)

### Community 46 - "bn"
Cohesion: 0.07
Nodes (16): bn, ce(), de, dn(), dt(), ei(), he(), je() (+8 more)

### Community 47 - "os"
Cohesion: 0.06
Nodes (28): base64, _derive_key(), رمز فعلی حساب برای نمایش سوپرادمین — رمزگذاری‌شده، فقط اگر با هش ورود یکی باشد.…, seal_password(), unseal_password(), _vault_secret(), مرحلهٔ ۲ se.md / BUG-002 — تست ولیدیشن SSRF پایهٔ URL پراوایدر AI., تست‌های منبعی: خزانهٔ رمز فعلی + ورکر Gemini (بدون Flask). (+20 more)

### Community 48 - "Analysis"
Cohesion: 0.09
Nodes (34): analysis_quick_solution(), _build_analysis_owner_conditions(), _default_quick_solution(), _generate_quick_solution(), _get_current_analysis_for_user(), ساخت شرط‌های مالکیت تحلیل برای کاربر جاری (فقط فیلدهای موجود)., پیدا کردن تحلیل متعلق به کاربر جاری (با id و شماره/شناسه کاربر)., محتوای پیش‌فرض اگر AI جواب نداد. (+26 more)

### Community 49 - "referrals.py"
Cohesion: 0.06
Nodes (44): رابطه معرف: کاربر معرفی‌شده + وضعیت + پورسانت., Referral, attach_referral_to_user(), _count_referrals(), create_withdrawal_request(), _credit_commission(), ensure_referral_code(), _find_referral_for_order() (+36 more)

### Community 50 - "tn"
Cohesion: 0.07
Nodes (12): addBox(), addElements(), at(), beforeUpdate(), configure(), initialize(), nn(), sn (+4 more)

### Community 51 - "admin_service.py"
Cohesion: 0.12
Nodes (42): admin_stats(), cleanup_incomplete_requests(), cleanup_server_sessions(), _conn(), count_open_tickets(), _count_where(), delete_all_users(), delete_user_everywhere() (+34 more)

### Community 52 - "beauty_centers/bot_handlers.py"
Cohesion: 0.07
Nodes (32): beauty_admin_menu_kb(), beauty_admin_menu_text(), _center_card(), _center_kb(), handle_beauty_admin_callback(), handle_beauty_admin_text(), handle_beauty_owner_callback(), Handle the isolated admin menu and fail closed for non-staff callers. (+24 more)

### Community 53 - "_admin_kb"
Cohesion: 0.07
Nodes (31): _admin_kb(), Admin keyboard with a fixed operational role and no per-admin switches., giso/panel — پنل ادمین ماژولار گیسو (فاز 4) - Blueprint: panel با…, Return the role-specific sidebar without changing superadmin output., visible_modules(), _cleanup(), Historical database switches cannot change the fixed normal-admin menu., تست جامع مشکل بازگشت پنل ادمین + حذف پیام «/start بزنید». سناریوها: ۱) خط… (+23 more)

### Community 54 - "hair_sale_steps.js"
Cohesion: 0.11
Nodes (40): applySalePath(), compressPhotoForValidation(), disableButton(), displayPhotoValidation(), formatPersianAmount(), getCsrfToken(), getElements(), getFileSignature() (+32 more)

### Community 55 - "bot_edu/bot.py"
Cohesion: 0.07
Nodes (41): ambiguous_python_import_81c6931d742e, atexit, _build_bale_app(), _build_telegram_app_with_proxy(), _collect_proxy_candidates(), _init_periodic_checkpoint_edubot(), main(), _mask_proxy() (+33 more)

### Community 56 - "test_checkpoint_backup.py"
Cohesion: 0.07
Nodes (39): خواندن فایل .env به صورت dict (بدون رندر متغیر)., _read_env_file(), _auto_backup_job(), _backup_dir(), _backup_max_files(), _get_backup_interval_hours(), _list_backup_files(), خواندن تنظیم backup خودکار از giso_config (۰ = غیرفعال). (+31 more)

### Community 57 - "ai_runtime_policy.py"
Cohesion: 0.10
Nodes (40): _ask_single_provider(), _build_provider_attempt_chain(), _build_superadmin_action_plan(), chat_with_failover(), _find_product_match(), _is_capability_guide_request(), _legacy_chat_with_failover(), _apply_provider_cooldown() (+32 more)

### Community 58 - "notifications/core.py"
Cohesion: 0.08
Nodes (41): notifications_poll(), archive_all(), auto_archive(), can_modify_notification(), context(), delete_all(), delete_read_user_notifications(), get_allowed_notification_roles_for_user() (+33 more)

### Community 59 - "bot_helpers.py"
Cohesion: 0.07
Nodes (29): _admin_request_phrase(), عبارت درخواست ادمین با کش کوتاه؛ از Migration تکراری در هر پیام جلوگیری می‌کند., _admin_request_phrase_terms(), _admin_section_allowed(), _admin_section_visible_for_bot(), _is_admin_request_phrase(), _is_legacy_ai_callback(), make_state_pruner() (+21 more)

### Community 60 - "test_panel_phase5.py"
Cohesion: 0.09
Nodes (38): get_site_base_url(), idle_minutes_for_role(), is_registration_enabled(), آدرس پایه‌ی سایت؛ اگر هنوز در تنظیمات ذخیره نشده باشد، آدرس رسمی گیسو…, get_stats(), گزارش کلی کاربران (دیتابیس واقعی) — فاز 5., Deprecated compatibility no-op; permission configuration was removed., set_admin_permission() (+30 more)

### Community 61 - "bot_edu/ai_brain.py"
Cohesion: 0.09
Nodes (39): add_ai_provider(), _ai_check_cloudflare(), _ai_check_openai(), _ai_err(), _ai_jloads(), _ai_now(), ai_pick_preferred_model(), ai_provider_count() (+31 more)

### Community 62 - "reservations/services.py"
Cohesion: 0.11
Nodes (39): _active_bookings(), _build_slots(), cancel_by_user(), _center_is_public(), _clean_text(), create_reservation(), _date_weekday_label(), get_available_slots() (+31 more)

### Community 63 - "channel_importer.py"
Cohesion: 0.08
Nodes (37): _ai_parse(), _channel_msg_exists(), _clean_name(), _fa2en(), _fa_num(), get_shop_channel_id(), _insert_pending_product(), _is_channel_admin() (+29 more)

### Community 64 - "_base.py"
Cohesion: 0.10
Nodes (31): سربرگ اتمیک یک checkout؛ منبع معتبر برای برداشت کیف پول سبد خرید., فاکتور رسمی و snapshot مالی هر checkout فروشگاه., ShopCheckout, ShopInvoice, get_analyses(), get_chats_count(), get_hair_orders(), get_reviews() (+23 more)

### Community 65 - "n"
Cohesion: 0.10
Nodes (11): Fn(), jn, n(), ne(), numeric(), parseArrayData(), parseObjectData(), parsePrimitiveData() (+3 more)

### Community 66 - "bot_edu/mentor_service.py"
Cohesion: 0.12
Nodes (32): get_or_create_user_by_phone(), mentor_service.py — (سازگاری با گذشته) re-export از services/ تمام فراخوان‌های…, برگرفته از user_service — برای سازگاری., panel_service — façade سازگار با import قدیمی. منطق واقعی در…, get_user_rank(), list_courses(), list_missions(), list_shop_items() (+24 more)

### Community 67 - "_send_db_backup"
Cohesion: 0.06
Nodes (35): backup_bot_db_safe(), checkpoint_db(), backup ایمن bot.db با SQLite Backup API — کاملاً سازگار با WAL. این روش حتی با…, انتقال اطلاعات WAL به دیتابیس اصلی. اول TRUNCATE (بهترین)؛ اگر به دلیل reader…, _auto_edubot_backup(), _backup_db_paths(), _edubot_backup_dir(), _edubot_cleanup_old_backups() (+27 more)

### Community 68 - "ai_credits.py"
Cohesion: 0.10
Nodes (33): admin_adjust_credit(), admin_credit_users(), _cfg(), credit_settings(), ensure_ai_credit_tables(), get_ai_credit(), get_deduct_scope(), _identity() (+25 more)

### Community 69 - "test_user_profile_site_bot_sync.py"
Cohesion: 0.09
Nodes (24): test_cod_pending_checkout_edit_is_atomic_and_wallet_checkout_is_blocked(), test_profile_edit_locks_for_fifteen_days_and_password_uses_min4_policy(), connect_factory(), seed(), test_guest_gets_no_profile_data(), test_safe_defaults_are_minimal_and_normalized(), _cleanup(), _csrf() (+16 more)

### Community 70 - "test_panel_phase52.py"
Cohesion: 0.10
Nodes (29): Deprecated compatibility shim for the removed admin-access editor. The approved…, get_admin_permissions(), Return the fixed normal-admin policy; stored legacy switches are inert., _check(), _cleanup(), _flag_file(), _login(), _make_super() (+21 more)

### Community 71 - "db.py"
Cohesion: 0.09
Nodes (33): ambiguous_python_import_27b05364409a, init_ai_tables(), init_chat_history_table(), init_payment_tables(), init_phase3_tables(), init_phase4_tables(), init_trend_history_table(), init_user_profiles_table() (+25 more)

### Community 72 - "test_bot_hair_phase_fix.py"
Cohesion: 0.13
Nodes (32): get_show_commission_site(), آیا بخش پورسانت در کیف پول سایت نمایش داده شود؟ (فاز 5.1 ربات — پیش‌فرض: نمایش)., _add_msg(), _add_order(), _cb_flat(), _check(), _cleanup(), _flat_kb() (+24 more)

### Community 73 - "test_panel_authz_hair_shop.py"
Cohesion: 0.18
Nodes (28): _client(), _fixtures(), _post(), _q1(), باگ واقعی: admin_note=NULL باعث AttributeError و شکست کل به‌روزرسانی می‌شد., تست سیاست مجوزدهی پنل وب برای «خرید مو» و «فروشگاه» + صفحه‌بندی + N+1 +…, _run(), _seed() (+20 more)

### Community 74 - "_analysis_report"
Cohesion: 0.12
Nodes (31): _analysis_report(), analysis_report_hair(), analysis_report_skin(), نمایش آخرین گزارش نهایی کاربر از جدول analyses., _build_concern_items(), _build_metric_cards(), _build_radar_points(), _build_routine_cards() (+23 more)

### Community 75 - "test_notifications_module.py"
Cohesion: 0.17
Nodes (30): category_settings(), _normalize_target_role(), Preserve the explicit super/admin/both routing contract., تنظیمات همه دسته‌ها: پیش‌فرض + ذخیره‌شده در giso_config (JSON)., ذخیره تنظیمات دسته‌ها (فقط سوپرادمین — در route گارد می‌شود)., save_category_settings(), test_financial_notifications_remain_superadmin_only(), _add_product() (+22 more)

### Community 76 - "main.py"
Cohesion: 0.11
Nodes (31): _check_giso_restart_flag(), _clear_pid(), _env(), _giso_bot_watcher(), _install_signal_handlers(), _sig(), main(), Path (+23 more)

### Community 77 - "test_panel_phase51.py"
Cohesion: 0.16
Nodes (29): _check(), _cleanup(), _flag_file(), _login(), _make_super(), _no_restart_artifacts(), _pending_file(), ورود به صفحه تنظیمات → نه pending نه flag ریستارت ساخته نمی‌شود. (+21 more)

### Community 78 - "test_ai_clean_registry.py"
Cohesion: 0.07
Nodes (25): _is_vision_model(), pick_active_vision_model(), _provider_active(), _provider_model_candidates(), _provider_vision_model(), دسترسی امن به فیلد row — پشتیبانی از sqlite3.Row و dict., تشخیص هوشمند اینکه آیا نام مدل قابلیت Vision دارد یا نه., لیست مدل‌های قابل استفادهٔ یک پروایدر — منابع به ترتیب اولویت (فاز ۲): 1.… (+17 more)

### Community 79 - ".getContext"
Cohesion: 0.12
Nodes (6): Bi(), Ci(), Do(), eo(), Fi(), Oe()

### Community 80 - "web_ai/__init__.py"
Cohesion: 0.13
Nodes (26): ambiguous_python_import_77c1afc03d5c, call_ai(), check_ai_status(), Any, بررسی وضعیت کلیدهای AI ثبت‌شده توسط ربات, web/web_ai/ai_engine.py پل ارتباطی امن وب‌سایت با موتور هوش مصنوعی ربات بدون…, ارسال پیام به موتور AI ربات و دریافت پاسخ, chat() (+18 more)

### Community 81 - "get_bot_db_conn"
Cohesion: 0.10
Nodes (20): _bot_setting_value(), giso_maintenance_gate(), _maint_duration_minutes(), _maint_resolve_until(), _maint_started_at(), _maint_started_at_write(), _maintenance_flag(), خواندن فلگ نگهداری از bot.db با کش کوتاه ده‌ثانیه‌ای. (+12 more)

### Community 82 - "bot_hair_admin.py"
Cohesion: 0.12
Nodes (28): admin_sub_allowed(), _clamp(), _get_order(), is_suboption_visible(), _list_active_users(), _list_request_ids(), _list_user_order_ids(), order_action_kb() (+20 more)

### Community 83 - "modules/settings.py"
Cohesion: 0.13
Nodes (29): _backup_context(), _clean_digits(), _clean_ga_id(), _clean_google_verify(), _clean_handle(), _clean_url(), context(), _get_bot_setting() (+21 more)

### Community 84 - "recovery.py"
Cohesion: 0.16
Nodes (27): create_recovery_package(), _durable_files(), _export_giso_config(), Path, Independent GISO recovery packages. A package contains a consistent giso.db…, Validate, replace GISO DB/files, and roll all changes back on failure., restore_recovery_package(), _safe_member() (+19 more)

### Community 85 - "test_admin_ai_panel.py"
Cohesion: 0.12
Nodes (26): get_display_name(), get_setting(), get_widget_config(), get_widget_position(), get_widget_primary_color(), get_widget_welcome_message(), is_widget_enabled(), ai_widget_chat() (+18 more)

### Community 86 - "marketplace/routes.py"
Cohesion: 0.13
Nodes (28): create_offer(), _listing_detail_url(), listing_slug(), listings(), _marketplace_sitemap_response(), _parse_page(), _public_query(), public_seller_profile() (+20 more)

### Community 87 - "zt"
Cohesion: 0.11
Nodes (11): color(), Ft(), It(), kt(), mt(), qt(), _t(), te() (+3 more)

### Community 88 - "db_pg_tools.py"
Cohesion: 0.15
Nodes (27): argparse, translate_ddl_sqlite_to_pg(), _adapt(), _coerce(), copy_all(), copy_table(), create_indexes(), create_tables() (+19 more)

### Community 89 - "marketplace/services.py"
Cohesion: 0.14
Nodes (27): build_listing_from_temp(), create_marketplace_listing(), _debit_buyer_feature(), _fa_number(), format_amount(), _market_purchase_key(), _move_marketplace_photo(), notify_listing_created() (+19 more)

### Community 90 - "test_shop_phase_b.py"
Cohesion: 0.14
Nodes (25): _add_products(), _check(), _cleanup(), _login(), _pending_id(), صفحات فروشگاه از پکیج جدید + سبد و تسویه., اعلان ادمین بدون خطا + channel_importer / get_publish_mode از پکیج., «🛍 فروشگاه» در پنل ادمین + «تنظیمات فروشگاه» در پنل سوپرادمین. (+17 more)

### Community 91 - "consultant_context.py"
Cohesion: 0.13
Nodes (25): decimal, _analysis_domain(), _analysis_notes(), build_user_consultant_context(), _center_domain(), _detailed_hair(), _detailed_orders(), _fa_num() (+17 more)

### Community 92 - "notifications/helpers.py"
Cohesion: 0.11
Nodes (24): _load_main_admin_ids(), log_notification(), ثبت event اعلان؛ recipient_id برای اعلان per-user استفاده می‌شود., giso/panel/modules/notifications.py — ماژول «🔔 مدیریت اعلان‌ها» (فاز جامع…, _exists(), get_sound_on(), notification_url(), _now() (+16 more)

### Community 93 - "panel/modules/marketplace.py"
Cohesion: 0.12
Nodes (26): public_reputation_profile(), listing_days_left(), marketplace_reputation(), notify_buyer_profile_status(), Anonymous star-only reputation; textual comments are intentionally ignored., Everything needed by the single user marketplace workspace. The returned…, Whole days of public display remaining (<=0 means expired)., seller_public_code() (+18 more)

### Community 94 - "User"
Cohesion: 0.13
Nodes (18): BuyerProfile, مجوز دامنه‌ای خریدار روی همان User موجود؛ سیستم auth/role جدید نیست., کاربر سایت گیسو (مستقل), User, _cleanup(), _login(), test_admin_panel_verify_flow_for_admin(), test_admin_panel_verify_flow_for_superadmin() (+10 more)

### Community 95 - "backup/core.py"
Cohesion: 0.11
Nodes (25): cancel_bot_restart(), context(), get_backup_interval_hours(), _giso_maintenance_enabled(), list_backup_files(), pending_restart_info(), بازه backup خودکار (ساعت؛ ۰ = غیرفعال) — همان کلید ربات در giso.db., ذخیره بازه backup خودکار (giso.db — همان کلید ربات). (+17 more)

### Community 96 - "special_assistant.py"
Cohesion: 0.13
Nodes (25): assistant_chat(), assistant_history(), _guard_special(), گارد اختصاصی: فقط ادمین اختصاصی (special). سوپر/ادمین عادی رد می‌شوند. خروجی:…, _wrapped(), actor_key_for(), answer(), answer_sync() (+17 more)

### Community 97 - "_setup_db"
Cohesion: 0.15
Nodes (27): _add_order(), _check(), _cleanup(), ادمین معمولی فقط مجازها؛ سوپرادمین همه گزینه‌ها (از جمله پورسانت در منوی فروش…, لیست درخواست‌ها + ۴ اکشن: رد / قیمت / بررسی / گفتگو., ثبت قیمت → پیام فوری کاربر؛ گفتگو دوطرفه (پاسخ کاربر → اعلان ادمین)., ویرایش با شماره کاربر + لیست کاربران فروش مو., گزارش ربات و پنل سایت از یک منبع داده — اعداد یکسان. (+19 more)

### Community 98 - "bug_reports.py"
Cohesion: 0.14
Nodes (21): _clean(), _ensure_reward_mission(), _fingerprint(), list_reports(), list_user_reports(), Claim once, then award through wallet's idempotent Spend transaction., تضمین وجود مأموریت پاداش گزارش باگ (idempotent، مستقل از مجوز فلَسک).…, Manual bug-bounty workflow; submission never pays automatically. (+13 more)

### Community 99 - "bt"
Cohesion: 0.13
Nodes (3): bt, Cs, os()

### Community 100 - "guest_interviewer.py"
Cohesion: 0.15
Nodes (25): api_mentor_try_chat(), ask(), سؤال ساده از هوش مصنوعی, _detect_contradiction(), _extract_profile_ai(), _fallback_profile_extract(), _final_message(), _had_soft_retry() (+17 more)

### Community 101 - "UserJourneyContext"
Cohesion: 0.09
Nodes (12): تاریخچهٔ گفتگو به شکل متن، برای تزریق به پرامپت., افزودن پیام به تاریخچهٔ چتِ یک گام مشخص., گام موردنظر از نقشه راه (بر اساس step_number) یا None., پاسخ‌های جمع‌آوری‌شده به شکل متن، برای تزریق به پرامپت., تبدیل به دیکشنری برای ذخیره در دیتابیس., ساخت از دیکشنری دیتابیس. هر مقدار خراب بی‌صدا نادیده می‌رود., ساخت مستقیم از ردیف career_paths (کلید journey داخل interview_data)., عنوان شغل هدف — از مسیر انتخابی یا پروفایل. (+4 more)

### Community 102 - "services/mentor_service.py"
Cohesion: 0.15
Nodes (24): _ai_mentor_enabled(), _ai_ready(), _append_chat(), _apply_updates(), _bootstrap_into_ai_mentor(), _call_ai(), _conn(), _ensure_tables() (+16 more)

### Community 103 - "set_setting"
Cohesion: 0.18
Nodes (22): set_active_provider(), set_chat_enabled(), set_display_name(), set_role_capabilities(), set_setting(), set_widget_enabled(), set_widget_position(), set_widget_primary_color() (+14 more)

### Community 104 - "pricing/services.py"
Cohesion: 0.16
Nodes (23): _back_to_services(), _owned_center(), owner_service_add(), owner_service_delete(), owner_working_hours(), login_required, Phase A pricing routes: owner-facing service and working-hour endpoints.…, _user_id() (+15 more)

### Community 105 - "HairListing"
Cohesion: 0.21
Nodes (25): buyer_respond_counter(), close_offer_chat(), complete_offer(), listing_photo(), _offer_action_redirect(), offer_chat(), login_required, Keep new panel forms in the panel while preserving every legacy redirect. (+17 more)

### Community 106 - "test_two_layer_storage.py"
Cohesion: 0.14
Nodes (19): load_providers_from_env(), خواندن اطلاعات AI providers از فایل .env فقط وقتی استفاده می‌شود که دیتابیس…, اگر دیتابیس خالی است، از .env بخوان و پر کن. سرعت خواندن عادی را تحت تأثیر قرار…, مرحلهٔ ۲ se.md / BUG-002 — جلوگیری از SSRF در base_url پراوایدر AI. فقط https؛…, ذخیره یا آپدیت یک provider در فایل .env. API Key در هیچ لاگی چاپ نمی‌شود., save_provider_to_env(), sync_env_providers_to_db(), _validate_base_url() (+11 more)

### Community 107 - "ai_health.py"
Cohesion: 0.13
Nodes (22): تنظیمات مرکزی سیستم AI - همه ثابت‌های قابل تنظیم اینجا (فاز ۳ بازنویسی)., classify_error_text(), _conn(), filter_available(), get_cooldown_remaining_seconds(), get_fail_count(), get_provider_is_free(), is_in_cooldown() (+14 more)

### Community 108 - "test_fix_phase_ab.py"
Cohesion: 0.17
Nodes (20): list_notifications(), لیست اعلان‌ها (ادمین → فقط دسته‌های مجاز؛ سوپر → همه)., _capture_send(), fake_post(), restore(), _check(), _cleanup(), _login() (+12 more)

### Community 109 - "test_wallet_unified.py"
Cohesion: 0.15
Nodes (20): fixture, _credit(), ledger(), connect(), Focused regression tests for the unified wallet ledger and atomic checkout., سپک جدید کاربر: مبلغ تومان بدون جداکنندهٔ هزارگانِ شبیه اعشار نمایش داده شود., test_balance_counts_used_debits_and_scopes(), test_checkout_is_atomic_and_cannot_reuse_spent_credit() (+12 more)

### Community 110 - "safe_log"
Cohesion: 0.15
Nodes (21): _fmt(), _get_center(), _get_reservation(), handle_reservation_bot(), Phase B reservation bot callbacks: rsv|confirm|<id>, rsv|reject|<id>,…, Handle rsv|* callbacks. Returns True when the update was consumed., notify_new_reservation(), notify_reminder() (+13 more)

### Community 111 - "to_shamsi"
Cohesion: 0.12
Nodes (22): _group_shop_order_rows(), آخرین سفارش‌های فروشگاه کاربر از giso.db (به تفکیک شماره نرمال‌شده)., گروه‌بندی اقلام یک checkout برای نمایش یک سفارش/کد پیگیری در ربات., _shop_order_rows(), chats_menu_kb(), chats_menu_text(), end_thread(), handle_gchat_callback() (+14 more)

### Community 112 - "CareerInterviewAgent"
Cohesion: 0.13
Nodes (10): CareerInterviewAgent, ایجنت ۱ — مصاحبه‌گر شغلی., خواندن پرامپت از ai_mentor/prompts/., مهارت‌های پرتقاضای فعلی از جدول market_trends., یک نوبت گفتگو با کاربر. ورودی user_message پاسخ کاربر به سؤال قبلی است (در شروع…, وقتی AI در دسترس نیست: سؤال بعدی از فهرست ثابت., حدس دستهٔ شغلی از روی متن پاسخ‌ها — فقط برای حالت fallback., ساخت JSON نهایی از داده‌های موجود، بدون فراخوانی AI. وقتی کاربر مسیر را انتخاب… (+2 more)

### Community 113 - "monitoring_insights.py"
Cohesion: 0.13
Nodes (21): safe(), _collect_improvement_data(), one(), collect_improvement_insights(), _collect_open_error_clusters(), ensure(), health_report(), _parse_json_loose() (+13 more)

### Community 114 - "shop.js"
Cohesion: 0.15
Nodes (16): applyCatalogState(), buildRecommendationCard(), cardMatches(), checkedValues(), csrfValue(), filterState(), loadRecommendations(), localWishlist() (+8 more)

### Community 115 - "ai_widget.js"
Cohesion: 0.21
Nodes (21): addMsg(), appendCreditLine(), applyData(), _attnClear(), autosize(), escapeHtml(), faNum(), loadInit() (+13 more)

### Community 116 - "platform_runtime.py"
Cohesion: 0.15
Nodes (20): ambiguous_python_import_4e433cba377b, apply_telegram_enabled(), current_proxy_label(), is_telegram_running(), mask_proxy(), platform_runtime.py — کنترل زندهٔ اتصال پلتفرم تلگرام (کار ۲) وابستگی مجاز:…, [کار ۲ — بند ۴] توقف واقعی اتصال تلگرام. خروجی: (ok: bool, message: str), [کار ۲ — بند ۵] برقراری واقعی اتصال تلگرام (با پروکسی و retry). خروجی: (ok:… (+12 more)

### Community 117 - "env_loader.py"
Cohesion: 0.20
Nodes (18): admin_ids(), bot_token(), env_service — دسترسی یکپارچه به env و نقش‌های سیستمی (با تکیه بر env_loader…, آیدی‌های ادمین ربات (ADMIN_IDS)., secret_key(), ensure_env_loaded(), env_bool(), env_int() (+10 more)

### Community 118 - "backup/helpers.py"
Cohesion: 0.12
Nodes (18): اجرای امن coroutineها از کد sync (روت‌های Flask، کد PTB sync، اسکریپت‌ها). چرا…, panel/modules/backup.py — پشتیبان‌گیری / بازگردانی / ریستارت ربات (فاز 5). همان…, build_recovery_package(), is_giso_bot_running(), maybe_auto_recovery(), _due(), _worker(), _prune_auto_recovery() (+10 more)

### Community 119 - "test_shop_phase_a.py"
Cohesion: 0.24
Nodes (19): _add_products(), _check(), _cleanup(), _login_user(), اعلان به ادمین بله بدون خطا — تست واقعی بدون توکن (باید بی‌صدا رد شود)., channel_importer دست‌نخورده — ماژول import و مسیر ثبت پست کانال سالم است., تست فاز A فروشگاه — بازطراحی UI (فقط ظاهر؛ منطق/route/فرم دست‌نخورده) پوشش…, ورود به عنوان کاربر عضو (فاز جامع: خرید فقط با عضویت). (+11 more)

### Community 120 - "widget_service.py"
Cohesion: 0.13
Nodes (20): _notify_consultant_admin_new_msg(), خلاصه زنده کاربر از دیتابیس: شمارش‌ها، اطلاعیه‌های شخصی (وضعیت سفارش/درخواست)،…, giso/widget_service.py — سرویس‌های ویجت هوشمند سایت و اعلان‌های مشاور (Phase 2,…, درک زمینه: آیا کاربر واقعاً دنبال محصول/خرید است؟ (نه هر جمله‌ای), پیشنهاد محصول مرتبط از دل صحبت کاربر (بر اساس نام/دسته/توضیح محصولات فروشگاه).…, چیپ‌های پیشنهادی پویا بعد از هر پاسخ: بر اساس آخرین پیام، تاریخچه، نقش و وضعیت…, دستورهای گزارش‌گیری زنده برای ادمین/سوپرادمین داخل چت ویجت. فقط وقتی پیام…, ثبت اعلان مشاوره در مرکز اعلان؛ چت تعاملی کاربر دست‌نخورده می‌ماند. (+12 more)

### Community 121 - "auth.py"
Cohesion: 0.15
Nodes (19): ambiguous_python_import_24843d50c7cf, ambiguous_python_import_b76df0ea1f6c, User, user_loader, _auth_extract_first_int(), _check_answer_hash(), _ensure_career_state(), forgot_password() (+11 more)

### Community 122 - "web/models.py"
Cohesion: 0.11
Nodes (16): flask_sqlalchemy, UserMixin, Config, ConsultantMessage, ConsultantRequest, پیام‌های سایت بین کاربر و ادمین برای یک درخواست مشاوره., مدل‌های وب‌سایت اصلی - مدل User روی جدول هستهٔ users ربات می‌نشیند (داده مشترک…, مدل کاربر سایت — نگاشتی روی جدول users ربات. (+8 more)

### Community 123 - "test_edu_giso_remote_management.py"
Cohesion: 0.11
Nodes (7): ast, _maintenance_key(), تنظیم live وضعیت maintenance در settings., set_maintenance_flag(), Regression guards for standalone Bale bot runtime failures., قرارداد منوی تفکیک‌شده و امنیت مدیریت راه دور گیسو., test_giso_maintenance_serves_branded_page_but_keeps_login_open()

### Community 124 - "reservations/routes.py"
Cohesion: 0.17
Nodes (17): get, get_center_services(), Return all services of a center, active first, then sort_order/id., calendar(), _center_by_id(), _center_by_slug(), my_reservations(), _owner_center() (+9 more)

### Community 125 - "panel/modules/analyses.py"
Cohesion: 0.17
Nodes (17): context(), _fa_num(), get_chat_detail(), get_chat_summaries(), get_consultant_messages(), get_consultant_requests(), get_product_requests(), خلاصه گفتگوهای مشاور (analyses.consultant_chat_history) — مثل ربات. (+9 more)

### Community 126 - "consults.py"
Cohesion: 0.20
Nodes (18): context(), _ensure_shop_messages(), handle_delete(), handle_reply(), handle_status(), handle_support_reply(), handle_support_status(), handle_thread_reply() (+10 more)

### Community 127 - "test_final_fixes.py"
Cohesion: 0.15
Nodes (15): _compress(), کمک‌های عملکرد HTTP — مورد ۱۹ img/help.md (تحویل ۱۴۰۵-۰۶-۱۰). فشرده‌سازی gzip…, در صورت صلاحیت، بدنهٔ پاسخ را gzip می‌کند (بی‌صدا خطا را نادیده می‌گیرد)., میان‌افزار gzip را روی اپلیکیشن فلاسک ثبت می‌کند., register(), _giso_gzip_text(), _cleanup(), تست رفع ۴ مشکل حیاتی نهایی ۱) باگ کیبورد ادمین محدود: بدون user_id → کیبورد… (+7 more)

### Community 128 - "learning_mentor.py"
Cohesion: 0.15
Nodes (10): agents — ایجنت‌های معماری چندعاملی «یار هوشمند شغلی». سه ایجنت، هرکدام دقیقاً…, LearningMentorAgent, _now_str(), learning_mentor.py — ایجنت ۳: منتور آموزشی. مسئولیت واحد: آموزش «گام فعال» و…, محتوای پایه از خود اسکلت گام — وقتی AI در دسترس نیست., ثبت نمره و به‌روزرسانی نقاط قوت/ضعف کاربر. نمره در ai_feedback همان گام ذخیره…, ایجنت ۳ — منتور آموزشی (تولید محتوا + داوری تمرین)., اجرای یک نوبت. task="teach" → تولید محتوای گام step_number task="grade" → داوری… (+2 more)

### Community 129 - "test_bot_fix_group_a.py"
Cohesion: 0.17
Nodes (15): _get_recent_analyses(), آخرین تحلیل‌ها با اطلاعات کامل کاربر., _extract_analysis_score(), _extract_analysis_topic(), _format_persian_date(), استخراج موضوع اصلی تحلیل., استخراج امتیاز کلی تحلیل., تبدیل تاریخ به فارسی خوانا. (+7 more)

### Community 130 - "get_giso_site_config"
Cohesion: 0.15
Nodes (16): _connect_giso_db(), get_giso_site_config(), _giso_db_config_table_ready(), _init_giso_db_config_table(), ساخت جدول giso_config در giso.db فقط وقتی وجود ندارد (بدون نوشتن اضافه)., خواندن کلید سایت از giso_config در giso.db (منبع اصلی)., اتصال به giso.db برای کلیدهای مشترک سایت — با busy_timeout/WAL., اگر جدول giso_config در giso.db هست True (بدون قفل‌گرفتن اضافه). (+8 more)

### Community 131 - "giso_handlers.py"
Cohesion: 0.24
Nodes (16): giso_button_handler(), giso_cancel_markup(), giso_inline_followup(), giso_menu_markup(), giso_request_view_markup(), giso_requests_markup(), giso_text_handler(), DEFAULT_TYPE (+8 more)

### Community 132 - "typing"
Cohesion: 0.18
Nodes (15): dataclasses, build_product_cards(), _category_name(), _image_url(), _is_special_order(), _normalize_one(), ProductCard, Any (+7 more)

### Community 133 - "authz.py"
Cohesion: 0.16
Nodes (16): functools, _action_meta(), _audit_denied(), can_admin_access_option(), can_admin_access_section(), can_execute_panel_action(), وضعیت اکشن‌های فروش مو برای قالب — تا UI و اجرا یکی باشند., Server-side action guards for operational Hair and Shop mutations. Approved… (+8 more)

### Community 134 - "_handle_ai_state"
Cohesion: 0.24
Nodes (17): check_all_ai_providers(), delete_ai_provider(), list_ai_providers(), _admin_ai_kb(), _admin_proxy_kb(), _has_provider_ai_management_access(), Provider/proxy administration remains superadmin-only., _ai_cmd_check_all() (+9 more)

### Community 135 - "is_admin_demoted"
Cohesion: 0.15
Nodes (15): clear_admin_demoted(), _ensure_demoted_admins_table(), erase_user_data(), is_admin_demoted(), mark_admin_demoted(), ثبت ادمین تنزل‌یافته در لیست سیاه تا sync ربات او را دوباره ادمین نکند., حذف از لیست سیاه (در تأیید مجدد درخواست ادمینی توسط سوپرادمین)., آیا این بله‌آیدی/شماره توسط سوپرادمین تنزل یافته است؟ (+7 more)

### Community 136 - "consultant.js"
Cohesion: 0.26
Nodes (14): appendMessage(), escapeHtml(), formatNumberFa(), handleConsultantEnter(), hideTyping(), initConsultant(), loadConsultantHistory(), renderConsultantCards() (+6 more)

### Community 137 - "guest_analyzer.py"
Cohesion: 0.26
Nodes (16): _analysis_unavailable_response(), analyze_guest_paths(), _build_analysis_prompt(), _call_analysis_ai(), _extract_context(), _extract_profile_ai(), _fallback_profile_extract(), _load_prompt() (+8 more)

### Community 138 - "inject_helpers"
Cohesion: 0.16
Nodes (14): _compute_home_data(), index(), _off(), inject_helpers(), _current_panel_role(), _get_login_logo(), _get_site_appearance(), _get_site_brand() (+6 more)

### Community 139 - "test_fix_phase_p0p1p2.py"
Cohesion: 0.24
Nodes (12): _send_preview_to_admins(), _add_product(), _admin(), _check(), _cleanup(), _login(), _mkuser(), تست‌های فاز اصلاحی P0/P1/P2 P0) رفع تداخل sidebar بین فروشگاه و پنل… (+4 more)

### Community 141 - "maybe_send_daily_digest"
Cohesion: 0.17
Nodes (14): daily_digest_text(), is_digest_enabled(), maybe_send_daily_digest(), _q1(), ارسال روزانه به بله سوپرادمین — حداکثر یک‌بار در روز (lazy، بدون scheduler). با…, giso/marketing.py — گزارش بازاریابی روزانه (فاز P2) یک منبع مشترک برای ساخت…, متن خلاصه بازاریابی یک روز — اعداد واقعی از دیتابیس., install_site_background_hooks() (+6 more)

### Community 142 - "test_shop_phase_a2.py"
Cohesion: 0.33
Nodes (14): _add_products(), _check(), _cleanup(), تست فاز A نسخه ۲ فروشگاه — بازطراحی کامل UI (فقط ظاهر؛ منطق/route/فرم…, test_10_mobile_css(), test_11_routes_and_forms_regression(), test_12_files_removed_and_new(), test_1_shop_page_new_structure() (+6 more)

### Community 143 - "panel_tour.js"
Cohesion: 0.25
Nodes (12): build(), dotsHtml(), finish(), isMobile(), markSeen(), next(), open(), placeRing() (+4 more)

### Community 144 - "unittest_mock"
Cohesion: 0.32
Nodes (13): _add_product(), _check(), _cleanup(), تست فاز layout اختصاصی فروشگاه — همه صفحات فروشگاه از shop_layout.html ارث…, _shop_marks(), test_12_13_channel_and_widget(), test_14_seo_robots_sitemap(), test_15_mobile() (+5 more)

### Community 145 - "clamp_int"
Cohesion: 0.20
Nodes (7): اعمال خروجی مدل روی context با اعتبارسنجی کامل., اعتبارسنجی JSON نهایی — قرارداد ورودی ایجنت ۲., پاک‌سازی خروجی مدل. محتوای آموزشی عمداً نگه داشته نمی‌شود., clamp_int(), pick(), تبدیل امن به عدد صحیح داخل بازه (اعداد فارسی هم پذیرفته می‌شوند)., اعتبارسنجی مقدار شمارشی (enum) از خروجی مدل.

### Community 146 - "db_engine.py"
Cohesion: 0.18
Nodes (11): URI دوانجینهٔ SQLAlchemy: پیش‌فرض sqlite؛ با GISO_DB_ENGINE=postgres روی PG.…, _sa_uri(), connect_pg(), dsn_for(), install_pg_compat(), is_pg(), is_pragma(), فقط وقتی true که صریحاً env ست شده باشد؛ پیش‌فرض مطلق sqlite. (+3 more)

### Community 147 - "static/manifest.json"
Cohesion: 0.14
Nodes (13): background_color, description, dir, display, icons, id, lang, name (+5 more)

### Community 148 - "Review"
Cohesion: 0.24
Nodes (12): submit_review(), مدل ثبت نظرات و رضایت کاربران (فروشگاه یا فروش مو) در giso.db, Review, context(), handle_delete(), handle_toggle(), panel/modules/reviews.py — مدیریت نظرات (فاز 4.6): مخفی/نمایش/حذف دومرحله‌ای., بازگشت query string فیلتر فعلی نظرات. (+4 more)

### Community 149 - "reservations/schema.py"
Cohesion: 0.21
Nodes (11): _columns_of(), _ensure_table(), migrate_pricing_tables(), Phase A pricing schema: additive-only migrations for beauty center services and…, Create table only if absent; otherwise add missing columns only., Idempotent additive schema for Phase A pricing., _columns_of(), _ensure_table() (+3 more)

### Community 150 - "get_pending_reminders"
Cohesion: 0.17
Nodes (13): get_pending_reminders(), get_user_reservations(), _jalali_to_datetime(), datetime, Jalali YYYY-MM-DD + HH:MM -> naive datetime on the local server clock., Row → dict plus status_label and starts_at (local timestamp, '' if unparsable)., Reservations of one user, newest created first (limit 200), with center info., Confirmed bookings with at least one reminder still unsent (bounded, oldest… (+5 more)

### Community 151 - "test_hair_sale_back.py"
Cohesion: 0.24
Nodes (10): _cleanup(), The normal-admin home keyboard always exposes the fixed Hair role., A legacy off-row cannot revoke the fixed Hair/Shop operational role., تست رفع مشکل بازگشت از زیرمنوی «فروش مو» برای ادمین محدود. قبل از رفع:…, _send(), _setup_db(), test_limited_admin_back_hair(), test_live_change_hair() (+2 more)

### Community 152 - "test_shop_ui_fix.py"
Cohesion: 0.42
Nodes (11): _add_products(), _check(), _cleanup(), تست فاز اصلاحی UI فروشگاه — هم‌سبک‌سازی گرم + رفع عملکرد گزینه‌ها پوشش: ۱)…, test_10_seo_routes_regression(), test_1_warm_style(), test_2_search_and_filters_wired(), test_3_4_drawer_real_content_and_count() (+3 more)

### Community 153 - "roadmap_builder.py"
Cohesion: 0.20
Nodes (9): ambiguous_python_import_dfef9368729a, collective_hint(), courses_brief(), roadmap_builder.py — ایجنت ۲: معمار نقشه راه. مسئولیت واحد: تبدیل JSON نهاییِ…, ورودی ایجنت ۲ — دقیقاً همان JSON خروجی ایجنت ۱ + زمینهٔ ربات., متن آماده از حافظهٔ جمعی برای تزریق به پرامپت معمار., فهرست فشردهٔ دوره‌های ربات — تا معمار course_id جعلی نسازد., jdump() (+1 more)

### Community 154 - "marketplace_settings"
Cohesion: 0.27
Nodes (9): app_context_processor, inject_marketplace_policy(), _get(), marketplace_settings(), _price(), Small stable marketplace settings surface using the existing config store., save_marketplace_settings(), Phase 2: isolated credit settings and role-facing tabs. (+1 more)

### Community 155 - "buti_ai/routes.py"
Cohesion: 0.21
Nodes (9): giso/buti_ai/__init__.py — ماژول بومی آینه جادویی گیسو (پیش‌نمایش چهره و…, mirror_home(), ping(), تست سلامت ماژول آینه جادویی گیسو., giso/buti_ai/routes.py — کنترلرهای وب و ای‌پی‌آی آینه جادویی گیسو., روت اصلی ورودی آینه جادویی گیسو., init_buti_ai_db(), giso/buti_ai/schema.py — جدول‌های پایگاه داده ماژول آینه جادویی در giso.db. (+1 more)

### Community 156 - "take_backup"
Cohesion: 0.18
Nodes (12): بازگردانی giso.db از نسخه (همان منطق امن ربات: checkpoint + integrity + safety)., ساخت نسخه پشتیبان (checkpoint + کپی + هرس) — مثل ربات., restore_backup(), take_backup(), _generate_manifest(), _max_files(), _pre_restore_check(), Path (+4 more)

### Community 157 - "rank_daily.py"
Cohesion: 0.26
Nodes (11): deposit_rank_credits_for_date(), _due_dates(), _worker(), _ran_key(), کارگرِ پس‌زمینه: برای هر تاریخِ سررسیده واریز را اجرا و فلگ تاریخ را ثبت می‌کند., واریز روزانه‌ی اعتبار خرید بر اساس رتبه‌ی کاربر (مرحله ۵، نسخه‌ی مقاوم در بار…, تاریخ‌هایی که اکنون باید واریز شوند: امروز (اگر ≥۲۳:۵۹) و/یا دیروز (جبران…, واریز اعتبار روزانه‌ی رتبه برای همه‌ی کاربران برای یک تاریخ مشخص. «اجراکننده‌ی… (+3 more)

### Community 158 - "recommendation_service.py"
Cohesion: 0.26
Nodes (10): _extract_profile_signals(), get_nutrition_recommendations(), _nutrition_match_score(), NutritionItem, Any, Phase 6+7+17+25 Scenario 2: Real Recommendation Engine - Multi-signal:…, استخراج سیگنال‌های تطبیق (نوع مو/پوست/نگرانی) از پروفایل + گزارش آنالیز (هر دو…, امتیاز تطبیقِ یک رکورد special_order با سیگنال‌های کاربر (۰ یعنی بی‌ارتباط). (+2 more)

### Community 161 - "PgConn"
Cohesion: 0.27
Nodes (3): PgConn, حداقل API مورد استفادهٔ کد فعلی: execute/executemany/commit/rollback/close +…, معادل sqlite3: اجرای چند دستور پشت‌هم (تفکیک ';' بیرون از لیترال‌ها).

### Community 162 - "ai_mentor/core.py"
Cohesion: 0.24
Nodes (8): career_interview.py — ایجنت ۱: مصاحبه‌گر شغلی. مسئولیت واحد: شناخت کاربر و…, ask_agent(), clear_prompt_cache(), extract_json(), core.py — هستهٔ مشترک معماری چندعاملی (Multi-Agent) «یار هوشمند شغلی». اینجا…, استخراج امن JSON از پاسخ مدل (همان منطق آزمودهٔ ai_core)., فراخوانی AI برای یک ایجنت. از ai_core._ask عبور می‌کند تا مسیریابی مدل، پرامپت…, پاک‌کردن کش — برای وقتی ادمین فایل پرامپت را دستی عوض می‌کند.

### Community 163 - "ai_assistant.js"
Cohesion: 0.42
Nodes (9): addMsg(), addNote(), esc(), init(), linkify(), renderHistory(), send(), setSend() (+1 more)

### Community 164 - "giso_notifications.js"
Cohesion: 0.36
Nodes (8): faNum(), poll(), renderBadge(), renderDrop(), saveSeen(), schedulePoll(), setDrop(), showToast()

### Community 165 - "e2e_check.py"
Cohesion: 0.27
Nodes (6): csrf(), post_form(), post_json(), E2E real-flow test: user / admin / superadmin / special; site + panel;…, step-up: GET /admin/verify issues code (sender mocked), then POST code., verify_admin()

### Community 166 - "test_consultant.py"
Cohesion: 0.33
Nodes (6): _cleanup(), _login(), _make_user_and_analysis(), تست مرحله ۳ از ۹: زیرساخت مشاور هوشمند صادقی ۱) پرامپت‌های مشاور و خلاصه‌ساز…, test_consultant_chat_api_flow(), test_consultant_chat_validation()

### Community 167 - "test_marketplace_notification_delivery.py"
Cohesion: 0.22
Nodes (4): ImmediatePool, Focused notification contract for Marketplace actors., test_marketplace_user_notification_records_site_and_queues_bale(), test_shop_order_notification_actions_are_scoped_per_order()

### Community 168 - "_ask_consultant_bot"
Cohesion: 0.22
Nodes (9): _ask_consultant_bot(), _build_admin_consultant_prompt(), _get_user_full_context(), فقط وقتی کاربر صریحاً خرید/سفارش می‌خواهد کارت محصول در ربات برود., ارسال کارت محصول (آرایشی: عکس+دکمه) و آیتم خوراکی (متن+دکمه سفارش) برای مشاور…, فراخوانی هوشمند مشاور گیسو در ربات با نقش و context متناسب., زمینه کامل گزارش‌محور کاربر برای مشاور هوشمند. فقط گزارش/پیشنهاد/تحلیل می‌سازد…, _send_consultant_product_cards() (+1 more)

### Community 170 - "handle_recovery_download"
Cohesion: 0.25
Nodes (9): _download_headers_response(), handle_backup_download(), handle_recovery_download(), Path, send_file with attachment disposition so the file leaves the server., Download a recovery ZIP from the server (off-site backup enabler). GET + super., Download a raw .db backup from the server. GET + super., Resolve a bare filename strictly inside `directory` (path-traversal safe). (+1 more)

### Community 171 - "test_report_dual_cta.py"
Cohesion: 0.39
Nodes (7): _assert_cta(), _login(), _make_report(), تست مرحله ۲ از ۹: دو دکمه (سریع / اصولی) در گزارش نهایی ۱) دو دکمه در پایین…, ساخت یک تحلیل با گزارش نهایی کامل برای تست رندر., test_hair_report_dual_cta(), test_skin_report_dual_cta()

### Community 172 - "RoadmapBuilderAgent"
Cohesion: 0.32
Nodes (4): ساخت اسکلت نقشه راه از JSON ایجنت ۱. خروجی: {ok, stage, roadmap, total_steps,…, اسکلت پایه وقتی AI در دسترس نیست — مسیر هرگز نیمه‌کاره نمی‌ماند., ایجنت ۲ — معمار نقشه راه (فقط اسکلت، بدون محتوا)., RoadmapBuilderAgent

### Community 173 - "_MsgShim"
Cohesion: 0.25
Nodes (5): _MsgShim, _open_ai_mentor(), شبیه‌ساز callback_query روی یک پیام معمولی. دکمهٔ «🧠 مسیر شغلی هوشمند» از نوع…, باز کردن منوی «یار هوشمند شغلی» از دکمهٔ متنیِ منوی کاربر. ctx به‌صورت صریح پاس…, show_career_path()

### Community 174 - "normalize_phone"
Cohesion: 0.32
Nodes (7): normalize_phone(), phone_display(), phone_equal(), phoneutil.py — ابزار مشترک نرمال‌سازی شماره موبایل ایران. همه بخش‌های پروژه…, نرمال‌سازی و اعتبارسنجی شماره موبایل ایران. خروجی در فرمت استاندارد…, مقایسهٔ دو شماره مستقل از فرمت ورودی., تبدیل فرمت استاندارد (+989...) به فرمت نمایشی 09...

### Community 175 - "build_beauty_centers_prompt"
Cohesion: 0.36
Nodes (6): build_beauty_centers_prompt(), Return strict instructions plus a small, untrusted database snapshot., Stage 11: AI safety policy for center recommendations., test_empty_database_forbids_inventing_a_center(), test_owner_content_is_serialized_as_untrusted_data_and_cannot_break_boundary(), test_prompt_has_full_intermediary_price_and_promotion_policy()

### Community 176 - "marketplace/__init__.py"
Cohesion: 0.29
Nodes (7): _install_sensitive_log_record_factory(), safe_factory(), Public and authenticated hair marketplace routes on the existing Giso app/auth., Remove common credentials and personal identifiers before log formatting., Install once so future application logs cannot emit common raw secrets/PII., redact_sensitive_log_text(), traceback

### Community 177 - "panel.js"
Cohesion: 0.39
Nodes (5): activate(), esc(), loadData(), setCount(), toggle()

### Community 179 - "test_sensitive_register.py"
Cohesion: 0.46
Nodes (6): _cleanup(), _csrf(), تست ثبت‌نام شماره‌های حساس با کد ربات ۱) ثبت‌نام شماره سوپرادمین بدون کد کامل…, _register_payload(), test_admin_sensitive_register_requires_bot_code(), test_super_sensitive_register_requires_bot_code()

### Community 180 - "test_special_site_role.py"
Cohesion: 0.39
Nodes (6): _load_permissions(), Site-only Special role: get_admin_target + sidebar + module allowlist. Loads…, test_get_admin_target_returns_special_for_sadeghi_phone(), test_regular_admin_and_super_menus_unchanged(), test_special_cannot_open_finance_users_security_ai(), test_special_sidebar_is_the_requested_nav()

### Community 181 - "get_calendar_month"
Cohesion: 0.33
Nodes (7): get_working_hours(), Return working hours of a center ordered by day_of_week (0 = Saturday)., get_calendar_month(), Day-by-day view of one Jalali month for a center (all services, generic…, _today_jalali(), gregorian_to_jalali(), تبدیل میلادی به شمسی بدون وابستگی خارجی.

### Community 182 - "sqlite_ddls"
Cohesion: 0.29
Nodes (7): add_fks(), extract_fks(), FKها بعد از کپی داده اضافه می‌شوند → کل داده یک‌جا اعتبارسنجی می‌شود. اگر دادهٔ…, CREATE TABLE را بدون FK برمی‌گرداند + لیست ALTER TABLE ADD CONSTRAINT. دلیل:…, [(نام، DDL بدون FK)] به ترتیب الفبا + همهٔ ALTERهای FK., _split_top_level(), sqlite_ddls()

### Community 183 - "execute_pending_restart"
Cohesion: 0.29
Nodes (7): execute_pending_restart(), اجرای ریستارتِ در انتظار اگر مهلتش رسیده باشد — فقط از thread ناشی از POST. -…, _do(), _kill_giso_bot_if_running(), _process_is_giso_bot(), آیا PID داده‌شده متعلق به فرایند «گیسوبات» است؟ (جلوگیری از کشتن فرایند اشتباه)…, اگر PID ربات موجود، زنده و متعلق به گیسوبات بود SIGTERM می‌فرستد تا watcher…

### Community 184 - "giso_idle.js"
Cohesion: 0.52
Nodes (6): goLogout(), onLightActivity(), remaining(), removeToast(), resetTimer(), showWarn()

### Community 186 - "test_p0_wallet_referral_retirement.py"
Cohesion: 0.43
Nodes (5): P0 regressions: retired referral UX and unified bot wallet., _source(), test_bot_wallet_uses_central_cash_spend_ledger_without_referral_claims(), test_register_form_has_no_referral_input(), test_registration_does_not_create_new_referral_data()

### Community 187 - "test_spend_mission_expansion.py"
Cohesion: 0.48
Nodes (4): connect_factory(), seed(), test_product_explorer_requires_distinct_published_and_elapsed_time(), test_verified_bale_connection_is_once_and_spend_only()

### Community 188 - "reports.py"
Cohesion: 0.53
Nodes (5): context(), _cnt(), _q1(), giso/panel/modules/reports.py — ماژول «📈 گزارشات» یک‌صفحه‌ای (فاز P0 سایت)…, _rows()

### Community 189 - "invoices.py"
Cohesion: 0.47
Nodes (5): _date_token(), ensure_invoice_for_order(), _payment_status(), فاکتور رسمی سفارش‌های فروشگاه و backfill ایمن سفارش‌های تاریخی., برگرداندن invoice_id؛ برای سفارش قدیمی فاقد snapshot، یک فاکتور legacy می‌سازد.

### Community 190 - "fa_display.js"
Cohesion: 0.80
Nodes (5): boot(), excluded(), localizeNode(), localizeText(), run()

### Community 192 - "test_beauty_centers_stage13_home_card.py"
Cohesion: 0.47
Nodes (4): _card_markup(), Stage 13: indexable and no-JavaScript Beauty Centers homepage card., test_card_contains_intermediary_disclosure_without_javascript(), test_homepage_card_is_server_rendered_with_real_direct_link()

### Community 193 - "test_display_checks.js"
Cohesion: 0.47
Nodes (5): extractFunction(), fs, makeEl(), runTest(), ref_fs

### Community 196 - "migrate_beauty_center_tables"
Cohesion: 0.40
Nodes (3): migrate_beauty_center_tables(), test_additive_migration_preserves_legacy_center(), test_pricing_migration_is_additive()

### Community 197 - "data/manifest.json"
Cohesion: 0.40
Nodes (4): created_at, files, format, version

### Community 199 - "context"
Cohesion: 0.60
Nodes (4): context(), _one(), Read-only financial aggregation over existing Giso ledgers and purchase tables., _rows()

### Community 200 - "money_fa.js"
Cohesion: 0.70
Nodes (4): bind(), normalize(), toWords(), triplet()

### Community 201 - "password_meter.js"
Cohesion: 0.60
Nodes (4): attach(), paint(), boot(), strength()

### Community 203 - "active_platform_bots"
Cohesion: 0.50
Nodes (4): active_platform_bots(), دیکشنری {platform: bot} از پلتفرم‌هایی که bot فعال دارند., یافتن یک گیرندهٔ دایرکت بر اساس آیدی عددی یا یوزرنیم. خروجی: (platform,…, resolve_direct_target()

### Community 204 - "_save_users"
Cohesion: 0.50
Nodes (4): ذخیرهٔ کاربران — فقط کاربرانی که واقعاً تغییر کرده‌اند نوشته می‌شوند. خروجی در…, اثر انگشت دقیقاً از فیلدهایی که _save_users در دیتابیس می‌نویسد. هر تغییر در…, _save_users(), _user_fingerprint()

### Community 205 - "sync_deleted_users_from_db"
Cohesion: 0.50
Nodes (4): حذف زندهٔ ردپای کاربر از حافظهٔ ربات، بدون نیاز به restart., Best-effort hook: اگر وب کاربری را از DB حذف کرده باشد، حافظهٔ ربات هم سبک sync…, remove_user_from_memory(), sync_deleted_users_from_db()

### Community 208 - "reset"
Cohesion: 0.67
Nodes (3): Explicit, superadmin-only reset operations for monitoring reports., reset(), _table_exists()

### Community 209 - "channel.py"
Cohesion: 0.67
Nodes (3): context(), _get_config(), panel/modules/channel.py — تنظیم کانال فروشگاه.

## Knowledge Gaps
- **29 isolated node(s):** `_RequestFallback`, `FakeHttpx`, `Category`, `GisoAdmin`, `GisoConfig` (+24 more)
  These have ≤1 connection - possible missing edges. (Counts symbols only; 2351 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **29 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `get_giso_db_conn()` connect `get_giso_db_conn` to `route`, `redirect`, `logging`, `_run_async`, `giso/bot.py`, `beauty_centers/routes.py`, `format_toman`, `giso/app.py`, `giso/wallet.py`, `gemini_proxy_manager.py`, `ai_runtime.py`, `giso/ai_brain.py`, `beauty_centers/services.py`, `base.py`, `super_assistant.py`, `panel_user/routes.py`, `test_bot_group_b.py`, `bot_user_actions.py`, `bot_admin_utils.py`, `seo_jobs.py`, `create_app`, `test_ai_runtime.py`, `wallet_balepay.py`, `users.py`, `test_security_permissions_fix.py`, `enricher.py`, `referrals.py`, `beauty_centers/bot_handlers.py`, `_admin_kb`, `test_checkpoint_backup.py`, `ai_runtime_policy.py`, `notifications/core.py`, `test_panel_phase5.py`, `reservations/services.py`, `channel_importer.py`, `_base.py`, `ai_credits.py`, `test_user_profile_site_bot_sync.py`, `test_panel_phase52.py`, `test_bot_hair_phase_fix.py`, `test_panel_authz_hair_shop.py`, `test_notifications_module.py`, `test_panel_phase51.py`, `get_bot_db_conn`, `bot_hair_admin.py`, `modules/settings.py`, `test_admin_ai_panel.py`, `marketplace/routes.py`, `marketplace/services.py`, `test_shop_phase_b.py`, `consultant_context.py`, `notifications/helpers.py`, `backup/core.py`, `special_assistant.py`, `_setup_db`, `bug_reports.py`, `set_setting`, `pricing/services.py`, `test_two_layer_storage.py`, `ai_health.py`, `test_fix_phase_ab.py`, `test_wallet_unified.py`, `safe_log`, `to_shamsi`, `monitoring_insights.py`, `backup/helpers.py`, `widget_service.py`, `reservations/routes.py`, `panel/modules/analyses.py`, `consults.py`, `test_final_fixes.py`, `test_bot_fix_group_a.py`, `is_admin_demoted`, `inject_helpers`, `test_fix_phase_p0p1p2.py`, `maybe_send_daily_digest`, `db_engine.py`, `reservations/schema.py`, `get_pending_reminders`, `test_hair_sale_back.py`, `buti_ai/routes.py`, `rank_daily.py`, `recommendation_service.py`, `get_calendar_month`, `reports.py`, `invoices.py`, `migrate_beauty_center_tables`, `context`, `reset`?**
  _High betweenness centrality (0.080) - this node is a cross-community bridge._
- **Why does `create_app()` connect `create_app` to `test_bot_fix_group_a.py`, `route`, `redirect`, `logging`, `giso/bot.py`, `analysis.py`, `inject_helpers`, `render_template`, `maybe_send_daily_digest`, `giso/app.py`, `giso/wallet.py`, `beauty_centers/routes.py`, `gemini_proxy_manager.py`, `ai_runtime.py`, `test_fix_phase_p0p1p2.py`, `Review`, `get_giso_db_conn`, `beauty_centers/services.py`, `base.py`, `super_assistant.py`, `test_hair_sale_back.py`, `pathlib`, `marketplace_settings`, `panel_user/routes.py`, `test_bot_group_b.py`, `test_shop_ui_fix.py`, `bot_admin_utils.py`, `seo_jobs.py`, `test_ai_runtime.py`, `e2e_check.py`, `test_consultant.py`, `users.py`, `wallet_balepay.py`, `test_report_dual_cta.py`, `Analysis`, `referrals.py`, `PanelCsrfGuardTests`, `test_sensitive_register.py`, `_admin_kb`, `test_checkpoint_backup.py`, `notifications/core.py`, `test_panel_phase5.py`, `test_beauty_centers_stage13_home_card.py`, `ai_credits.py`, `migrate_beauty_center_tables`, `test_user_profile_site_bot_sync.py`, `test_panel_phase52.py`, `test_bot_hair_phase_fix.py`, `test_panel_authz_hair_shop.py`, `test_notifications_module.py`, `test_shop_phase_a2.py`, `test_panel_phase51.py`, `get_bot_db_conn`, `modules/settings.py`, `test_admin_ai_panel.py`, `unittest_mock`, `test_shop_phase_b.py`, `User`, `_setup_db`, `set_setting`, `test_two_layer_storage.py`, `test_fix_phase_ab.py`, `test_shop_phase_a.py`, `widget_service.py`, `test_edu_giso_remote_management.py`, `test_final_fixes.py`?**
  _High betweenness centrality (0.032) - this node is a cross-community bridge._
- **Why does `url_for()` connect `redirect` to `route`, `authz.py`, `logging`, `analysis.py`, `render_template`, `beauty_centers/routes.py`, `giso/app.py`, `giso/ai_brain.py`, `Review`, `base.py`, `panel_user/routes.py`, `users.py`, `giso_admin.py`, `Analysis`, `notifications/core.py`, `_analysis_report`, `modules/settings.py`, `marketplace/routes.py`, `notifications/helpers.py`, `panel/modules/marketplace.py`, `special_assistant.py`, `set_setting`, `pricing/services.py`, `HairListing`, `auth.py`, `reservations/routes.py`, `consults.py`?**
  _High betweenness centrality (0.019) - this node is a cross-community bridge._
- **Are the 530 inferred relationships involving `get_giso_db_conn()` (e.g. with `load_stored_password()` and `remember_account_password()`) actually correct?**
  _`get_giso_db_conn()` has 530 INFERRED edges - model-reasoned connections that need verification._
- **Are the 6 inferred relationships involving `create_app()` (e.g. with `_maintenance_admin_entry()` and `Config`) actually correct?**
  _`create_app()` has 6 INFERRED edges - model-reasoned connections that need verification._
- **Are the 8 inferred relationships involving `_run_async()` (e.g. with `handle_callback()` and `handle_channel_post()`) actually correct?**
  _`_run_async()` has 8 INFERRED edges - model-reasoned connections that need verification._
- **Are the 249 inferred relationships involving `redirect()` (e.g. with `admin_analysis_note()` and `analysis_plan()`) actually correct?**
  _`redirect()` has 249 INFERRED edges - model-reasoned connections that need verification._