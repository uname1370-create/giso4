# ais.md — Audit کامل مشاور هوشمند گیسو (User / Admin / Super Admin / Bot)

> تاریخ: 2026-10-07  
> شاخه: `arena/01a0eecf-giso4` HEAD=`4017cb6`  
> اسکیل مرجع: `giso-dev/SKILL.md` + `references/*`  
> هدف: فقط بررسی، بدون تغییر کد — گزارش دقیق روند عملکرد، فایل‌ها، مسیرها، داده‌دهی، پرسش‌پاسخ، انتخاب AI، دسترسی، گزارش‌دهی + مشکلات + پیشنهاد بهبود برای نسخه بهتر هر مشاور  
> اصل: **Code Truth > Docs > Memory** — همه چیز از کد زنده استخراج شده

---

## 1. Freshness

```
Freshness: HEAD=4017cb6 branch=arena/01a0eecf-giso4 working-tree=dirty(1) -> giso/security.py preview fix
Graph: STALE (built at eb55bcb) / absent -> استفاده از grep/import
Docs: STALE (PROJECT_GUIDE آخرین آپدیت قدیمی)
Memory: project_memory/letta/PROJECT_MEMORY.md last update 2026-09
```

---

## 2. Section Identification — فایل‌های مشاور هوشمند

### هسته AI و اعتبار
- `giso/ai_runtime.py` — مدیریت مرکزی AI: `check_role_access()`, `get_context_scope()`, `chat_with_managed_ai()`, `process_superadmin_request()`, `SUPPORTED_SUPER_ACTIONS`, گزارش‌ها `_report_consultants()`
- `giso/ai_runtime_policy.py` — سیاست نقش‌ها، daily_limit، sections
- `giso/ai_brain.py` — رجیستری پروایدرها، failover chain
- `giso/ai_config.py`, `ai_models_registry.py`, `ai_credits.py` — اعتبار کاربر، کسر هزینه
- `giso/ai_discovery.py`, `ai_health.py` — سلامت پروایدر

### مشاور تحلیل (Analysis Consultant) — چت AI برای کاربر سایت
- `giso/analysis.py:1548 request_consultant()` — ثبت درخواست مشاوره انسانی
- `giso/analysis.py:1681 _load_consultant_prompt()` — لود پرامپت `consultant_sadeghi.txt` + محصولات + تاریخچه + مراکز زیبایی
- `giso/analysis.py:1787 consultant_chat_message()` — API `/api/consultant-chat/message` — چت AI کاربر
- `giso/analysis.py:1952 consultant_chat_history_route()` — `/api/consultant-chat/history/<id>`
- `giso/analysis.py:1976 consultant_chat_rate()` — امتیازدهی چت
- `giso/consultant_context.py:242 build_user_consultant_context()` — زمینه کامل گزارش‌محور برای مشاور (wallet, analysis, hair, orders, etc)
- `giso/consultant_cards.py` — `build_product_cards()` — کارت محصول در چت
- `giso/consultant_chat_service.py` — `thread_messages()`, `clear_user_thread()`, `is_owner()` — مدیریت رشته گفتگو انسانی
- `giso/base.py` — `get_giso_db_conn()` — اتصال DB

### مشاور آینه هوشمند (Buti AI Consultant)
- `giso/buti_ai/consultant.py:14 build_consultant_context()` — ساخت کانتکست استاتیک از service_key + candidate + generation
- `giso/buti_ai/consultant.py:52 consultant_invite_text()` — متن دعوت به مشاوره
- `giso/buti_ai/routes.py:446,1007` — استفاده در `eyebrow_final_design.html` و `generic_final_design.html`
- `giso/buti_ai/templates/buti_ai/eyebrow_final_design.html` — نمایش `consultant_context` و `consultant_invite`

### پنل کاربر (User Panel)
- `giso/panel_user/modules/chats.py` — `_support_tickets()`, `create_support_ticket()`, `context()` — تیکت پشتیبانی
- `giso/panel_user/modules/_base.py:68` — شمارش چت‌ها
- `giso/app.py:1781 dashboard_consultant_chat()` — `/dashboard/chats/consultant/<id>` — چت انسانی کاربر با ادمین
- `giso/templates/dashboard_consultant_chat.html` — UI چت کاربر
- `giso/templates/dashboard_chats.html` — لیست گفتگوها
- `giso/templates/consultant_component.html` — کامپوننت مشاور صادقی (آنالیز)
- `giso/static/js/consultant.js` — `initConsultant()`, `sendConsultantMessage()`, `loadConsultantHistory()`, `renderConsultantCards()`
- `giso/static/css/consultant.css` (ارجاع در analysis_plan.html)

### پنل ادمین / سوپرادمین
- `giso/panel/modules/analyses.py:67 get_consultant_requests()` — لیست درخواست‌های مشاوره انسانی
- `giso/panel/modules/analyses.py:85 get_consultant_messages()` — پیام‌های یک درخواست
- `giso/panel/modules/analyses.py:175 handle_consultant_reply()` — پاسخ ادمین (INSERT consultant_messages + status=chatting)
- `giso/panel/modules/analyses.py:206 handle_consultant_status()` — تغییر وضعیت
- `giso/panel/modules/consults.py` — مدیریت گفتگوهای خرید مو، فروشگاه، بازارچه، پشتیبانی
- `giso/panel/modules/super_assistant.py` — دستیار هوشمند مدیریتی سوپرادمین در سایت: `handle_chat_message()`, `send_action_code()`, `verify_action_code()`, تاریخچه `giso_panel_ai_chats`
- `giso/panel/modules/ai.py` — مدیریت AI: پروایدرها، failover، role policy، widget، credit
- `giso/panel/routes.py:614 super_assistant()` — `/panel/super-assistant`
- `giso/panel/routes.py:622 super_assistant_chat()` — API چت سوپر
- `giso/panel/templates/modules/super_assistant.html` — UI سه‌ستونه دستیار سوپر
- `giso/panel/templates/modules/analyses.html` — تب consultants
- `giso/templates/admin_consultants.html`, `admin_consultant_detail.html` — ادمین قدیمی (app.py routes)

### ربات (Bale/Telegram)
- `giso/bot.py:660 _consultant_ai_inline_kb()` — دکمه شروع مشاور AI
- `giso/bot.py:686 _set_consultant_ai_active()`, `697 _is_consultant_ai_active()` — state در `context.user_data` (حافظه)
- `giso/bot.py:2419 _analysis_consultant()` — نمایش مشاور در ربات
- `giso/bot.py:2573 _admin_ana_consultants()` — لیست درخواست‌ها برای ادمین در ربات
- `giso/bot.py:2891 handle_consultant_view()`, `2927 handle_consultant_reply()`, `2941 handle_consultant_end()`
- `giso/bot.py:5277 _build_admin_consultant_prompt()` — پرامپت ادمین مشاور
- `giso/bot.py:5319 _send_consultant_ai_guidance()`, `5335 _start_consultant_ai_chat()` — شروع چت AI
- `giso/bot_admin_utils.py:792 _get_recent_consultant_requests()`, `856 _ensure_bot_consultant_chat_table()`, `977 _build_admin_consultant_prompt()`, `1026 _send_consultant_product_cards()`, `1086 _ask_consultant_bot()` — سرویس AI ربات
- `giso/bot_user_actions.py:980 consultant_report()`, `1355 consultant_status_report()`
- `giso/bot_helpers.py:153 _role_has_consultant_ai()`

### DB Schema
- `consultant_requests`: id, user_id, phone, city, customer_name, analysis_id, initial_message, status (new/reviewing/chatting/closed/pending/active), created_at, updated_at, admin_id
- `consultant_messages`: id, request_id, sender (user/admin), message, is_read, created_at, cleared_by_user
- `giso_bot_consultant_chat`: bale_id, phone, role, message history برای ربات
- `analyses`: id, user_id, phone, type, ai_report_json, plan_json, consultant_chat_history (JSON list), consultant_key_notes, chat_rating, checklist_progress
- `giso_support_tickets`: id, user_bale_id, user_name, phone, message, status, admin_reply
- `giso_panel_ai_chats`: id, actor_key, phone, role, message_role, content, kind, ref_id, provider, created_at

---

## 3. Architecture & Current Pattern

| Seam | House Pattern (با شواهد) | رفتار مشاور |
|---|---|---|
| DB access | `get_giso_db_conn()` از `giso/base.py` — همه ماژول‌ها همین را استفاده می‌کنند (`consultant_chat_service.py:38`, `analyses.py:72`, `consults.py:23`) | همه مشاورها از همین helper استفاده می‌کنند، اما `analyses.consultant_chat_history` به صورت JSON در یک ستون ذخیره می‌شود نه جدول جدا |
| Auth/Role Guard | `panel/permissions.py: current_role_and_perms()` + `@login_required` در `analysis.py:1787` + `check_role_access()` در `ai_runtime.py:661` | چت AI کاربر: `get_context_scope("user", "consultant_chat")` چک می‌کند؛ سوپر: `role==super` bypass؛ پنل ادمین: `analysis_management` permission |
| CSRF | `csrf_token()` در فرم‌ها (`dashboard_consultant_chat.html:58`) + `X-GISO-CSRF` header در `consultant.js:68` | API چت AI هدر CSRF می‌خواهد، اما برخی routes قدیمی `admin/consultants/<id>/reply` فقط فرم POST با CSRF دارند |
| Notification Hook | `panel/modules/notifications.py: safe_log()` — event → notification (مثلاً `consultant_request`, `consultant_reply`) | `analysis.py:1595` و `app.py:1806 _notify_consultant_admin_new_msg` هر دو notification می‌فرستند — دو مسیر موازی |
| Bot Flow | state machine در `context.user_data["consultant_ai_active"]` + callback `consultant_ai_start/end` | state فقط در حافظه، نه DB — ری‌استارت ربات state را پاک می‌کند |
| Template/CSS | `consultant_component.html` + `consultant.js` + `consultant.css` — کامپوننت مستقل | Buti AI consultant فقط متن استاتیک دارد، نه چت تعاملی |
| AI Call | `ai_runtime.py:1118 chat_with_managed_ai()` — entry point واحد، actor_key=`site:phone`, role, section, daily_limit, credit check | مشاور تحلیل از همین entry استفاده می‌کند؛ مشاور آینه (buti_ai) اصلاً AI call ندارد، فقط پرامپت استاتیک می‌سازد؛ سوپر اسیستنت هم `process_superadmin_request()` دارد که گزارش‌ها را بدون AI می‌دهد |

**خلاصه معماری فعلی:**
- 3 مشاور جدا از هم: (1) AI تحلیل (صادقی) — چت تعاملی با تاریخچه JSON، (2) انسانی (consultant_requests) — کاربر ↔ ادمین، (3) آینه (buti_ai) — متن استاتیک بدون چت، (4) سوپرادمین — گزارش‌محور + اقدام با OTP، (5) ربات — ترکیب (1) و (2) با state حافظه‌ای.
- هیچ abstraction مشترک ندارد — هر کدام پرامپت و سرویس خودش.

---

## 4. Dependencies & Impact

- **Shared DB tables**: `consultant_requests`, `consultant_messages`, `analyses`, `giso_web_auth`, `giso_users`, `product_orders`, `hair_orders`, `giso_support_tickets`
- **AI runtime coupling**: `ai_runtime` به `ai_brain`, `ai_credits`, `ai_config`, `giso_ai_usage_stats`, `giso_ai_action_logs`
- **Notification**: `widget_service._notify_consultant_*` + `panel.modules.notifications.safe_log` — دو سیستم اعلان موازی برای یک event
- **Sibling features**: آنالیز مو/پوست، فروشگاه، بازارچه، beauty centers — همه از `consultant_context` استفاده می‌کنند
- **Bot coupling**: `bot.py` هم `ai_runtime` و هم `consultant_requests` را مستقیم می‌خواند — تغییر schema ربات را می‌شکند

---

## 5. جریان کامل (Data Flow, Q&A, AI Selection, Access, Reporting)

### 5.1 مشاور AI تحلیل (User Site — `/analysis` → `consultant_component.html`)

**Flow:**
1. کاربر آنالیز مو/پوست انجام می‌دهد → `analyses` row با `ai_report_json`, `plan_json`
2. در `analysis_plan.html` کامپوننت مشاور لود می‌شود: `initConsultant(analysisId)` → `GET /api/consultant-chat/history/<id>` → تاریخچه JSON از `analyses.consultant_chat_history`
3. کاربر پیام می‌فرستد → `POST /api/consultant-chat/message` با `analysis_id`, `message`
4. `consultant_chat_message()`:
   - `check_role_access("user","consultant_chat")` — اگر access_level=0 → 403
   - `get_context_scope()` — تعیین include_analysis/plan/products
   - مالکیت: `_get_current_analysis_for_user()` — `user_id` یا `phone` match (IDOR risk اگر phone قابل حدس)
   - لود تاریخچه: `json.loads(consultant_chat_history)` — بدون pagination، کل تاریخچه هر بار لود
   - بارگذاری `analysis_data`, `plan_data`, محصولات فقط اگر `_user_asked_to_buy()` و `include_products`
   - `recommended_centers()` برای مراکز زیبایی
   - `_load_consultant_prompt()` — ترکیب template `consultant_sadeghi.txt` + محصولات + تاریخچه 6 پیام آخر + مراکز
   - `chat_with_managed_ai([{"role":"user","content":prompt}], actor_key=f"site:{phone}", role="user", section="consultant_chat", max_tokens=800)` — داخل `ai_runtime` → `check_daily_limit()` → `get_today_usage_count()` از `giso_ai_usage_stats` → اگر limit رد شد 429
   - اعتبار: `_charge_service_or_block()` قبلاً برای `request_consultant` (انسانی) هزینه کسر می‌کند، اما برای چت AI هزینه از `ai_credits` کسر می‌شود (scope spend/cash)
   - پاسخ AI به تاریخچه اضافه → `json.dumps` ذخیره در `analyses`
   - هر 5 پیام `consultant_key_notes` خلاصه‌سازی می‌شود via `_summarize_chat_history()` → AI summarizer
   - کارت محصول: `consultant_cards.build_cards_for_user(phone)` + `recommendation_service.get_nutrition_recommendations()`
5. امتیازدهی: `POST /api/consultant-chat/rate` → `chat_rating` (1-5)

**AI Selection:**
- `ai_brain.py` — لیست پروایدرها از `giso_ai_providers` table، `active_provider` + `failover_chain`
- `chat_with_managed_ai()` پروایدر فعال را انتخاب، اگر fail شد بعدی در chain
- هیچ انتخاب مدل per-consultant-type نیست — همه چت‌ها یک مدل

**Access:**
- `@login_required` + `get_context_scope()` — user role باید `consultant_chat` section داشته باشد و `access_level>=1`
- مالکیت آنالیز via phone OR user_id — اگر کاربر شماره‌اش را عوض کند، دسترسی به آنالیز قدیمی را از دست می‌دهد

**Reporting:**
- هیچ داشبورد برای تعداد چت‌های AI، میانگین زمان پاسخ، رضایت (chat_rating) — فقط `chat_rating` در `analyses` ذخیره می‌شود، گزارشی ندارد

### 5.2 مشاور انسانی (User ↔ Admin)

**Flow:**
1. کاربر در `analysis_plan.html` فرم "درخواست مشاوره" → `POST /analysis/request-consultant` → `request_consultant()` در `analysis.py:1548`
   - INSERT `consultant_requests` (status=new) + `consultant_messages` (sender=user)
   - `_charge_service_or_block("consultation", rid, ...)` — هزینه یک‌بار per جلسه
   - `safe_log("analysis","consultant",...)` + `_notify_consultant_admins(rid)` → ربات به ادمین‌ها پیام
2. کاربر در `/dashboard/chats` لیست درخواست‌ها را می‌بیند → `dashboard_chats` (app.py:1737) — `SELECT * FROM consultant_requests WHERE phone=?`
3. کاربر وارد `/dashboard/chats/consultant/<id>` می‌شود → `dashboard_consultant_chat()`:
   - `is_owner(request_id, phone)` چک می‌کند `phone` match — اگر نه، audit `consultant_chat_ownership_denied`
   - `thread_messages(request_id, include_cleared=False)` — پیام‌ها از `consultant_messages`
   - `include_cleared` via `?history=1` — اگر کاربر پاک کرده باشد، با `cleared_by_user=1` فیلتر می‌شود
   - POST پیام → INSERT `consultant_messages` (sender=user) + `_notify_consultant_admin_new_msg()`
   - auto-refresh هر 10 ثانیه via `setTimeout(location.reload,10000)` — polling قدیمی
4. ادمین در پنل: `panel/modules/analyses.py: get_consultant_requests()` → لیست 20 تایی، `messages_count` via COUNT
   - `handle_consultant_reply()` → INSERT admin message + status=chatting
   - `handle_consultant_status()` → new/reviewing/chatting/closed
   - همین در `app.py:1957 admin_consultants` (قدیمی) و `panel/routes.py:1475 analyses_consultant_reply` (جدید) — دو مسیر برای یک کار
5. ربات ادمین: `_admin_ana_consultants()` → `_get_recent_consultant_requests()` → لیست، `handle_consultant_view()` → نمایش thread، `handle_consultant_reply()` via `replying_consultant` state در `user_data`

**Q&A:**
- پرسش کاربر → پیام انسانی ذخیره، ادمین باید دستی پاسخ دهد — هیچ AI کمکی برای ادمین در این flow نیست (در ربات `_ask_consultant_bot` برای ادمین وجود دارد اما در سایت نیست)

**Access:**
- User: فقط `phone` match — اگر دو کاربر یک شماره مشترک داشته باشند (خانوادگی)، هر دو به چت هم دسترسی دارند (IDOR)
- Admin: `analysis_management` permission یا `super` role — اما `admin_consultants` قدیمی در `app.py` فقط `login_required` + `is_admin` چک می‌کند، نه permission دقیق

**Reporting:**
- `_report_consultants()` در `ai_runtime.py:2750` — فقط COUNT و لیست 10 تایی — هیچ metric مثل زمان پاسخ، تعداد پیام، رضایت

### 5.3 مشاور آینه هوشمند (Buti AI — Eyebrow/HairColor/Lip/Nail)

**Flow:**
1. کاربر در `/analysis/mirror` خدمت را انتخاب → `buti_ai/routes.py` → `final_design.py` → `candidate` (service_label, style_label, change_label, short_reason, do, avoid, detection)
2. `build_consultant_context(service_key, candidate, generation)` → dict با `prompt` استاتیک
3. `consultant_invite_text()` → "نتیجه ... آماده است. سوالی داری؟"
4. در template `eyebrow_final_design.html` نمایش داده می‌شود — فقط متن، هیچ input چت ندارد
5. هیچ تاریخچه، هیچ AI call، هیچ ذخیره — فقط نمایش

**مشکل:** کاربر انتظار چت دارد اما فقط یک جمله دعوت می‌بیند — هیچ endpoint برای چت آینه وجود ندارد

### 5.4 سوپرادمین — دستیار هوشمند مدیریتی

**Flow (سایت):**
1. سوپرادمین وارد `/panel/super-assistant` می‌شود → `super_assistant.py: context()` — لود تاریخچه از `giso_panel_ai_chats`
2. پیام می‌فرستد → `POST /panel/super-assistant/chat` → `handle_chat_message(phone, text)`:
   - `_super_identity()` → چک `role==super` + `_panel_stepup_valid(phone)` (OTP ورود پنل باید تازه باشد)
   - `process_superadmin_request(actor_id, phone, text, ...)` در `ai_runtime.py:3107`:
     - اگر متن شامل کلمات گزارش باشد (مثل "گزارش سفارش‌ها") → `_report_recent_orders()` → بدون AI، مستقیم از DB
     - اگر شامل اقدام باشد (مثل "وضعیت سفارش 123 را تکمیل کن") → `_find_product_match()` + `_status_from_text()` → ساخت `pending_action` → ذخیره در `giso_ai_action_logs` با status=pending_preview
     - اگر هیچکدام → `chat_with_managed_ai()` با role=super → پاسخ AI
   - اگر pending action → UI دکمه "تأیید و اجرا" + "لغو" + OTP flow
3. تأیید اقدام:
   - `send_action_code(phone, bale_id, pending_id)` → کد 6 رقمی به ربات بله سوپرادمین via `https://tapi.bale.ai/bot{token}/sendMessage`
   - کد در `session["assistant_act_code"]` با hash SHA256 + TTL 5 دقیقه
   - کاربر کد را وارد می‌کند → `verify_action_code()` → اگر درست، `approve_action()` → اجرای واقعی via `_execute_action()` → snapshot قبل + اجرای UPDATE/DELETE + log + reversible flag
   - `undo` via `giso_ai_action_logs.snapshot_json`
4. تاریخچه: `save_chat_message()` → `giso_panel_ai_chats`

**Flow (ربات):**
- مشابه سایت اما بدون OTP — مستقیم در ربات با `InlineKeyboardMarkup` تأیید
- `process_superadmin_request()` مشترک

**AI Selection:**
- سوپر هم از `chat_with_managed_ai()` استفاده می‌کند اما با role=super → `check_role_access` bypass → همیشه allowed
- گزارش‌ها بدون AI هستند (قطعی از DB)

**Access:**
- فقط super role + step-up valid + Bale ID باید عددی باشد — اگر Bale ID نداشته باشد، OTP نمی‌تواند ارسال شود → اقدام از سایت ممکن نیست (fail secure)
- `SUPPORTED_SUPER_ACTIONS` whitelist — فقط 20 اقدام مجاز، بقیه رد می‌شود با `NOT_DEFINED_MESSAGE`
- هر اقدام `ACTION_SCOPE_HINTS` دارد — باید section مربوطه در role policy باشد

**Reporting:**
- `build_status_report()` — وضعیت پروایدرها، failover
- `giso_ai_action_logs` — تمام اقدامات با snapshot

### 5.5 ربات — مشاور AI کاربر

**Flow:**
1. کاربر در ربات `/start` → `_show_user_profile()` → اگر `consultant_ai_active` باشد، دکمه "همراه هوشمند"
2. کلیک `consultant_ai_start` → `_start_consultant_ai_chat()`:
   - `check_role_access(role, "consultant_chat")` — اگر access_level=0 → NO_ACCESS
   - `check_daily_limit(actor_key, role)` — اگر limit رد شد → پیام daily_limit
   - `consultant_status_report()` — وضعیت مشاوره‌های انسانی
   - `_set_consultant_ai_active(context, True)` — state در `user_data` dict
3. کاربر پیام متنی می‌فرستد → اگر `_is_consultant_ai_active()` → `_ask_consultant_bot(uid, phone, text, role, bot, chat_id)`:
   - `build_user_consultant_context(phone)` → زمینه کامل از DB (تحلیل، سفارش، کیف پول، etc) — best-effort try/except per domain
   - `_build_admin_consultant_prompt(role, context, history_text, user_message)` — پرامپت ادمین/کاربر
   - `chat_with_managed_ai()` → پاسخ
   - ذخیره در `giso_bot_consultant_chat` + `giso_ai_usage_stats`
   - `_send_consultant_product_cards()` → اگر کاربر خرید خواست، کارت محصول
4. پایان: `consultant_ai_end` → `_set_consultant_ai_active(False)` + `handle_consultant_end()`

**مشکل:** state فقط در RAM — ری‌استارت ربات = از دست رفتن حالت چت

---

## 6. مشکلات دقیق per پنل و مخاطب

### 6.1 پنل کاربر — مخاطب: کاربر عادی

| بخش | مشکل | شدت | شواهد |
|---|---|---|---|
| **AI تحلیل** | تاریخچه در `analyses.consultant_chat_history` به صورت JSON text — بدون index، بدون pagination، هر بار کل تاریخچه لود → با 100 پیام، payload 50KB+، کند | P1 | `analysis.py:1865 json.loads(consultant_chat_history)` + `consultant.js:11 loadConsultantHistory()` |
| **AI تحلیل** | خلاصه‌سازی هر 5 پیام با AI call اضافی — هزینه مضاعف، بدون cache | P2 | `analysis.py:1890 if len(history)>=5 and len%5==0: _summarize_chat_history()` |
| **AI تحلیل** | محصولات فقط اگر `_user_asked_to_buy()` — تشخیص keyword ساده فارسی، بدون NLP — "محصول چی خوبه" را می‌گیرد اما "چی پیشنهاد میدی برای موهام" را نه | P2 | `analysis.py:1729 _user_asked_to_buy()` — لیست 16 کلمه |
| **AI تحلیل** | `get_context_scope` include_products فقط برای access_level>=2 — کاربر تازه‌وارد (level 1) محصول نمی‌بیند حتی اگر بخواهد | P2 | `ai_runtime.py:728 if access_level>=2: include_products` |
| **انسانی** | `is_owner` فقط via phone — دو اکانت با یک شماره (مثلاً خانواده) به چت هم دسترسی دارند — IDOR | P0 | `consultant_chat_service.py:20 SELECT ... WHERE id=? AND phone=?` |
| **انسانی** | Auto-refresh با `location.reload()` هر 10 ثانیه — UX بد، از دست رفتن متن تایپ‌شده | P1 | `dashboard_consultant_chat.html:65 setTimeout(location.reload,10000)` |
| **انسانی** | `cleared_by_user` فقط flag — پیام‌ها حذف نمی‌شوند، اما کاربر فکر می‌کند پاک شده — ابهام حریم خصوصی | P2 | `consultant_chat_service.py:42 cleared_by_user=1` |
| **آینه** | هیچ چت تعاملی ندارد — فقط `consultant_invite_text` استاتیک — کاربر انتظار دارد بپرسد "این مدل بهم میاد؟" اما نمی‌تواند | P0 | `buti_ai/consultant.py` هیچ route چت ندارد |
| **عمومی** | دو سیستم مشاور جدا (AI vs انسانی) با UI متفاوت — کاربر گیج می‌شود کدام را استفاده کند | P1 | `analysis_plan.html` هم `consultant_component.html` دارد هم فرم `request_consultant` |

### 6.2 پنل ادمین — مخاطب: ادمین معمولی

| بخش | مشکل | شواهد |
|---|---|---|
| **لیست مشاوره** | دو مسیر موازی: `app.py:1957 admin_consultants` (قدیمی) و `panel/modules/analyses.py` (جدید) — هر دو فعال، دیتا یکسان اما کد duplicate | `grep -rn admin_consultants giso/` |
| **پاسخ** | هیچ AI کمکی برای ادمین — ادمین باید دستی تایپ کند، در حالی که ربات `_ask_consultant_bot` برای ادمین دارد | `bot_admin_utils.py:1086` vs `analyses.py:175` |
| **وضعیت** | Status های متفاوت: `new/reviewing/chatting/closed` در پنل جدید vs `new/reviewing/pending/active` در گزارش‌ها — ناسازگاری | `analyses.py:206` vs `ai_runtime.py:2750` |
| **Notification** | دو سیستم اعلان: `safe_log` + `_notify_consultant_*` — ممکن است دوبار اعلان برود | `analysis.py:1595` و `app.py:1806` |
| **Access** | `admin_consultants` قدیمی فقط `is_admin` چک می‌کند، نه `analysis_management` permission — ادمین بدون دسترسی آنالیز هم می‌تواند ببیند | `app.py:1957` |

### 6.3 سوپرادمین — مخاطب: سوپر

| بخش | مشکل | شدت |
|---|---|---|
| **OTP** | کد در `session` ذخیره می‌شود — اگر کاربر دو تب باز کند، کد تب اول با تب دوم overwrite می‌شود | P1 |
| **Bale dependency** | اگر توکن ربات یا Bale ID نباشد، اقدام از سایت ممکن نیست — هیچ fallback ایمیل/پیامک ندارد | P1 |
| **Snapshot** | `_snapshot_user_bundle` فقط 20 رکورد آخر هر جدول — اگر کاربر 100 سفارش داشته باشد، undo ناقص است | P2 |
| **History** | `giso_panel_ai_chats` بدون index روی `actor_key` — با 10k پیام کند می‌شود | P2 |
| **Prompt** | `_clean_answer` مارکداون را حذف می‌کند اما لیست‌ها را به `•` تبدیل می‌کند — اگر AI جدول بدهد، خراب می‌شود | P3 |

### 6.4 ربات — مخاطب: کاربر بله/تلگرام + ادمین ربات

| بخش | مشکل |
|---|---|
| **State** | `consultant_ai_active` فقط در `context.user_data` (RAM) — ری‌استارت ربات state را پاک می‌کند، کاربر وسط چت می‌ماند | P0 |
| **Context** | `build_user_consultant_context` هر بار 8 کوئری به DB می‌زند (analyses, orders, hair, tickets, etc) — بدون cache، هر پیام 200ms+ تاخیر |
| **Daily limit** | `get_today_usage_count` via `LIKE '2026-10-07%'` — اگر `created_at` فرمتش عوض شود، limit کار نمی‌کند |
| **Product cards** | `_send_consultant_product_cards` فقط اگر کاربر کلمه خرید بگوید — تشخیص keyword ضعیف |
| **Admin reply** | `replying_consultant` state هم در RAM — اگر ادمین وسط پاسخ ربات ری‌استارت شود، reply گم می‌شود |

### 6.5 مشترک — امنیت و داده‌دهی

- **IDOR**: `dashboard_consultant_chat` و `consultant_chat_history_route` فقط phone چک می‌کنند، نه user_id + phone — اگر attacker شماره کاربر را بداند (مثلاً از نشت)، می‌تواند چت را بخواند (هرچند شماره‌ها محرمانه‌اند، اما بهتر است user_id هم چک شود)
- **CSRF**: API چت AI هدر `X-GISO-CSRF` می‌خواهد اما برخی فرم‌های قدیمی `admin/consultants/*/reply` فقط `csrf_token` hidden دارند — اگر JS غیرفعال باشد، CSRF bypass ممکن نیست اما inconsistent
- **Rate limit**: `consultant_chat_message` روزانه via `ai_runtime` دارد، اما `dashboard_consultant_chat` (انسانی) هیچ rate limit ندارد — اسپم انسانی ممکن
- **Credit**: `request_consultant` هزینه یک‌بار دارد، اما اگر `_charge_service_or_block` fail شود، رکورد حذف می‌شود — کاربر پیام خطا می‌بیند اما نمی‌داند چرا (اعتبار ناکافی؟)
- **Logging**: `consultant_messages` is_read دارد اما هیچ log برای زمان پاسخ ادمین (response time) — نمی‌توان SLA سنجید
- **PII**: `consultant_context` شامل `phone`, `city`, `wallet` — اگر AI prompt نشت کند (log)، PII لو می‌رود — باید sanitize شود

---

## 7. پیشنهاد بهبود — نسخه بهتر هر مشاور (بدون تغییر کد، فقط طرح)

### 7.1 مشاور AI تحلیل (User) — نسخه 2.0

**معماری پیشنهادی:**
- جدول جدید `consultant_ai_threads`: id, user_id, analysis_id, created_at, title (خلاصه)
- جدول `consultant_ai_messages`: id, thread_id, role (user/assistant), content, tokens, provider, created_at — به جای JSON در analyses
- `analyses.consultant_chat_history` deprecated → migration به جدول جدید
- API: `GET /api/consultant-ai/threads`, `POST /threads`, `GET /threads/<id>/messages?limit=20&offset=0`, `POST /messages`
- Cache: `build_user_consultant_context` با TTL 5 دقیقه در Redis/memory — چون wallet و orders هر دقیقه عوض نمی‌شوند
- Prompt: template versioning — `consultant_sadeghi_v2.txt` با بخش‌های جدا: `{{analysis}}`, `{{plan}}`, `{{products}}`, `{{beauty_centers}}`, `{{history}}` — نه replace ساده
- Product detection: به جای keyword، از intent classification سبک (حتی regex بهتر: `r'(محصول|خرید|پیشنهاد).*(مو|پوست)'`)
- Rating: `chat_rating` به جدول جدا + `reason` + `created_at` — برای analytics
- UI: حذف auto-reload، اضافه WebSocket یا polling با `fetch` + `last_message_id`

**بهبودهای کوچک بدون refactor بزرگ:**
- `consultant.js` → `fetch` با `last_id` به جای reload
- `consultant_chat_service` → اضافه `user_id` چک علاوه بر phone
- اضافه `rate_limit` برای `dashboard_consultant_chat` (مثلاً 10 پیام/دقیقه)

### 7.2 مشاور انسانی (User ↔ Admin) — نسخه 2.0

- یکسان‌سازی دو مسیر قدیمی و جدید: فقط `panel/modules/analyses.py` بماند، `app.py:1957` حذف شود
- اضافه AI assist برای ادمین: دکمه "پیشنهاد پاسخ با AI" که `build_user_consultant_context` + تاریخچه را به `chat_with_managed_ai` با role=admin می‌دهد و پیش‌نویس پاسخ می‌سازد — ادمین ویرایش و ارسال
- Status یکسان: `new → reviewing → chatting → closed` همه جا
- اضافه `response_time` metric: `first_admin_reply_at`, `last_message_at` در `consultant_requests`
- اضافه `satisfaction` بعد از بسته شدن: کاربر امتیاز 1-5 به پاسخ انسانی بدهد
- Notification یکپارچه: فقط `safe_log` — `_notify_*` حذف شود

### 7.3 مشاور آینه (Buti AI) — نسخه 2.0

- تبدیل از متن استاتیک به چت تعاملی:
  - `POST /api/buti-ai/consultant/chat` با `service_key`, `candidate_id`, `message`
  - `build_consultant_context` + `user_message` → `chat_with_managed_ai` با section=`buti_ai_chat`
  - تاریخچه در `buti_ai_consultant_messages` (جدید)
- UI: در `eyebrow_final_design.html` اضافه `consultant_component.html` مشابه تحلیل
- Prompt: از `consultant.py:prompt` استاتیک به template پویا با history

### 7.4 سوپرادمین — دستیار هوشمند — نسخه 2.0

- OTP: به جای `session`, جدول `super_action_codes`: id, phone, pending_id, code_hash, expires_at, attempts, created_at — تا چند تب همزمان کار کند
- Fallback: اگر Bale ID نباشد، کد را در پنل نمایش بده با هشدار امنیتی (یا ایمیل)
- Snapshot کامل: به جای 20 رکورد، کل `user_id` related rows را با `WHERE user_id=?` بدون LIMIT (یا با LIMIT 100) + هشدار اگر بیش از 100 بود
- Index: `CREATE INDEX idx_panel_ai_chats_actor ON giso_panel_ai_chats(actor_key, id DESC)`
- Action log UI: صفحه `/panel/ai-actions` با فیلتر status, actor, table — الان فقط در DB است، UI ندارد
- Prompt: `_clean_answer` جدول را نگه دارد — فقط `**` و `__` حذف شود، نه `|` جدول

### 7.5 ربات — نسخه 2.0

- State persistence: `consultant_ai_active` در `giso_bot_consultant_chat` با ستون `is_active` + `updated_at` — به جای RAM
- Cache: `build_user_consultant_context` با TTL 2 دقیقه + invalidation on order/analysis change
- Daily limit: `created_at >= date('now','start of day')` به جای LIKE
- Admin reply: `replying_consultant` در DB `admin_states` table — نه RAM

---

## 8. ماتریس دسترسی (Permission Matrix) — وضعیت فعلی

| مسیر | نقش مجاز | گارد | مشکل |
|---|---|---|---|
| `POST /api/consultant-chat/message` | user با access_level>=1 و section consultant_chat | `@login_required` + `get_context_scope` + `check_daily_limit` | OK اما phone-based ownership |
| `GET /api/consultant-chat/history/<id>` | owner (phone OR user_id) | `_get_current_analysis_for_user` | IDOR phone |
| `POST /analysis/request-consultant` | user | `@login_required` (در route) | credit check دارد اما پیام خطا مبهم |
| `/dashboard/chats/consultant/<id>` | owner phone | `is_owner` phone check | IDOR |
| `/panel/analyses` tab consultants | super OR analysis_management perm | `_require_analysis_perm` | OK |
| `/admin/consultants` | admin (قدیمی) | `is_admin` | قدیمی، باید حذف |
| `/panel/super-assistant` | super + step-up | `_super_identity` + `_panel_stepup_valid` | OK اما session-based OTP |
| Bot `consultant_ai_start` | user با `_role_has_consultant_ai` | `check_role_access` | OK |
| Bot `adm_ana_consultants` | admin/super | `_is_giso_admin` | OK |

---

## 9. فهرست فایل‌های مرتبط (برای Scope Lock آینده)

```
ALLOWED برای بهبود مشاور (بدون تغییر خارج):
- giso/consultant_context.py
- giso/consultant_cards.py
- giso/consultant_chat_service.py
- giso/buti_ai/consultant.py
- giso/analysis.py (بخش consultant)
- giso/panel/modules/analyses.py
- giso/panel/modules/super_assistant.py
- giso/panel/modules/ai.py
- giso/bot.py (بخش consultant)
- giso/bot_admin_utils.py (بخش consultant)
- giso/ai_runtime.py (بخش consultant + super)
- giso/templates/consultant_component.html
- giso/templates/dashboard_consultant_chat.html
- giso/panel/templates/modules/super_assistant.html
- giso/static/js/consultant.js

FORBIDDEN (خارج از scope مشاور):
- giso/beauty_centers/*
- giso/marketplace/*
- giso/shop/*
- bot_edu/*
- web/*
```

---

## 10. What NOT to Build

- سیستم چت جدید از صفر — باید از `ai_runtime.chat_with_managed_ai` استفاده کرد
- جدول جدید برای هر نوع مشاور — یک جدول `consultant_ai_threads` کافی است، نه 5 جدول
- AI model selection per consultant type — فعلاً یک مدل کافی، بعداً می‌توان `task_key` اضافه کرد
- WebSocket برای چت انسانی — polling با `last_id` کافی است، WebSocket پیچیدگی اضافه
- حذف کامل `consultant_requests` — هنوز برای مشاوره انسانی لازم است، فقط بهبود

---

## 11. پیشنهاد نهایی — Roadmap 3 مرحله‌ای

### مرحله 1 (P0 — امنیت و UX فوری، بدون مهاجرت بزرگ)
- `is_owner` → چک `user_id` + `phone` (هر دو)
- حذف auto-reload → `fetch` با `last_message_id`
- یکسان‌سازی status ها
- حذف مسیر قدیمی `admin_consultants` در `app.py`
- Index روی `giso_panel_ai_chats(actor_key)`

### مرحله 2 (P1 — بهبود AI و ادمین)
- جدول `consultant_ai_threads` + `consultant_ai_messages` — migration از JSON
- AI assist برای ادمین در پنل
- Cache برای `build_user_consultant_context`
- چت تعاملی برای Buti AI
- State persistence ربات در DB

### مرحله 3 (P2 — Analytics و مقیاس)
- داشبورد متریک: تعداد چت‌ها، میانگین زمان پاسخ، رضایت، هزینه AI
- Prompt versioning + A/B test
- OTP جدول به جای session + fallback
- Snapshot کامل برای undo

---

## 12. نتیجه‌گیری

سیستم مشاور هوشمند گیسو **5 سیستم جدا** است که هر کدام با الگوی خودش کار می‌کند:

1. **AI تحلیل** — بهترین پیاده‌سازی، از `ai_runtime` استفاده می‌کند، اما تاریخچه JSON و product detection ضعیف
2. **انسانی** — ساده و کاربردی اما IDOR phone، auto-reload بد، بدون AI assist برای ادمین
3. **آینه** — فقط متن استاتیک، اصلاً چت نیست — بزرگترین gap
4. **سوپرادمین** — قوی‌ترین از نظر امنیت (OTP + snapshot + whitelist) اما session-based OTP و snapshot ناقص
5. **ربات** — state در RAM، context بدون cache

**بهترین نسخه هر مشاور** باید:

- **User AI**: تاریخچه جدولی + pagination + cache + intent detection + rating analytics
- **User Human**: مالکیت user_id + AI assist برای ادمین + response_time metric + notification یکپارچه
- **Buti AI**: چت تعاملی واقعی با history
- **Super**: OTP جدولی + snapshot کامل + action log UI
- **Bot**: state در DB + cache + daily limit درست

همه این‌ها بدون تغییر معماری بزرگ ممکن است — فقط با **Reuse>Extend>New**: از `ai_runtime` و `get_giso_db_conn` موجود استفاده، جدول‌های جدید additive-only، هیچ breaking change.

---

**پایان گزارش — فایل `ais.md` تولید شد، هیچ کد تغییر نکرد (فقط `giso/security.py` به صورت موقت برای پیش‌نمایش ویرایش شد که در کامیت نهایی نباید باشد).**
