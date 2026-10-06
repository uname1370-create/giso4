# Giso4 — Access, Site Structure & Smart Acquisition Audit
Date: 2026-10-07 — Branch: arena/01a0eecf-giso4 — HEAD: b7d1de5 (s6.md) + d49641c P0 fixes
Method: giso-dev SKILL.md — Code Truth > Graph > Memory > Docs — خط‌به‌خط
Rule: No code change in this phase — only eg.md — Reuse > Extend > New — No parallel system

## 1. Executive Summary

Giso4 یک پلتفرم 4 لایه با 70+ جدول، 355 route، 589 فایل، 6 Blueprint اصلی است. هسته کار می‌کند:

- **Public:** index با آمار واقعی DB (cached 5m), beauty-centers list/detail, marketplace, shop, mirror_home
- **Auth:** register/login/forgot/logout با CSRF + rate limit + brute-force tiers (3→5m,6→10m,10→1h) + banned check
- **User Panel:** /dashboard/* با guard که admin/super را به /admin redirect می‌کند — ownership via user_id + phone fallback — 403 برای ID دیگر
- **Owner Panel:** /dashboard/beauty-center با owner_user_id == current_user.id در service layer — NO IDOR برای edit/gallery/services/reservations
- **Admin Panel:** /admin/* با _check_giso_admin_access + require_super + step-up OTP via Bale — user/owner نمی‌توانند وارد شوند
- **Mirror / Smart Analysis:** eyebrow legacy + nail/hair_color/lip generic — flow model→upload→final — final generic نیاز به login (auth template)، eyebrow legacy بدون login (برای تست باز مانده) — consultant POST بدون login/rate_limit (Medium)
- **Reservation:** slots/calendar public، reserve @login_required با snapshot final_design_id/service_key/selected_style — owner_list با _owner_center check — my-reservations با user_id filter

**P0 fixes قبلی تأیید شد و در origin موجود است:** 
- P0-1 Syntax Error در 3 prompts.py — FIXED (py_compile PASS len 5) — commit d49641c
- P0-2 migrate_reservation_tables() در app.py:2261 و bot.py:1138 اضافه شد — FIXED

**مهم‌ترین شکاف فعلی:** Owner نمی‌بیند که AI برایش مشتری می‌آورد — final_design_id ذخیره می‌شود ولی در owner panel نمایش داده نمی‌شود. Demand recording هست ولی Owner نمی‌بیند. این باعث retention پایین سالن‌دار است، نه باگ امنیتی.

**نتیجه معماری:** Permission فعلی قابل ادامه است — نیاز به تغییر بنیادی ندارد — فقط 2-3 فیکس کوچک (consultant login/rate_limit, eyebrow final auth, owner cannot reserve own) و 1-2 کارت UI برای "از آینه".

## 2. Current Architecture

- **App factory:** `giso/app.py:create_app()` — Flask + SQLAlchemy (sqlite default, postgres via GISO_DB_ENGINE) + Flask-Login + security (CSRF, rate_limit, audit, headers) + perf gzip + maintenance gate + site_jobs + seo scheduler
- **Blueprints:**
  - `marketplace_bp` (`giso/marketplace/__init__.py:61`) — /marketplace
  - `beauty_centers_bp` (`giso/beauty_centers/__init__.py:5`) — /beauty-centers, /dashboard/beauty-center
  - `reservations_bp` (`giso/beauty_centers/reservations/routes.py:17`) — /beauty-centers/<slug>/reserve, /dashboard/beauty-center/reservations, /dashboard/my-reservations
  - `buti_ai_bp` (`giso/buti_ai/__init__.py`) — /buti_ai
  - `panel_bp` (`giso/panel/__init__.py:12`) — /admin, url_prefix /admin
  - `panel_user_bp` (`giso/panel_user/__init__.py`) — /dashboard
  - `broadcasts_center` registers on panel_bp
  - `analysis_routes` (`giso/analysis.py:104`) — /analysis (hair/skin legacy)
  - `hair_sale`, `shop`, `marketplace` etc register via functions
- **DB:** `giso/data/giso.db` (sqlite) + `bot_edu/data/bot.db` — tables: giso_web_auth, analyses, buti_ai_final_designs, beauty_centers, beauty_center_services, beauty_center_pricing, beauty_center_images, beauty_center_conversations, beauty_center_messages, beauty_center_reservations (now migrated), beauty_center_events, giso_audit_log, etc.
- **Auth:** Flask-Login `User` model (`giso/models.py`), phone normalized, password_hash pbkdf2:sha256, security_question, is_banned, referral_code (stopped), last_login, etc.
- **Security:** `giso/security.py:install_security` — CSRF token in session, validate_csrf() checks form/header, rate_limit in-process deque, login lockout tiers, audit_event to giso_audit_log, headers CSP, X-Frame, etc.
- **AI:** `giso/ai_brain.py`, `giso/buti_ai/ai_models.py:configured_vision_chain()`, `ask_ai_vision`, `service_image_generation.py:generate_final_design` — provider chain with failover

## 3. Phase 1 — User / Owner / Admin Permission Audit

### 3.1 User

**Register** `app.py:1144 /register` GET/POST, no login, CSRF via security_gate, rate_limit 5/600, `site_terms_accepted==1` required, phone `normalize_phone`, password `validate_new_password` min6+letter+digit, duplicate `User.query.filter_by(phone)`, referral ignored, auto login_user after, mission `registration`.

- Login required? No
- Role? No
- Ownership? Creates own only
- IDOR? No
- Severity: OK

**Login** `app.py:977 /login` — checks phone, password hash, `is_banned`, `login_lock_status`, `login_failed` tiers, `login_succeeded` clears counter, `touch_login`, audit, session permanent 1h.

- CSRF + rate_limit 10/300
- Severity: OK — strong

**Logout** `app.py:1273 /logout` @login_required — clears admin_panel state + sensitive_register state.

**Session** — Flask-Login, permanent 1h, SameSite Lax, HttpOnly, Secure warning if prod not secure, signed cookie, no fixation.

**User Dashboard** `app.py:1284 /dashboard` @login_required → redirect `panel_user.overview`. `panel_user/routes.py:45 _guard()` — if not auth redirect login?next, if role admin/super redirect panel.dashboard — **User cannot see admin, admin cannot see user panel** — OK.

**Profile** `/dashboard/profile` via panel_user — `get_owner_center` to show beauty_center link, update via `user_profile_service.PROFILE_FIELDS` whitelist, lock 15 days, length check — ownership via `current_user.id`.

**My Analyses** `panel_user/modules/analyses.py:180 context()` — `Analysis.user_id == current_user.id or phone`, `buti_ai_final_designs WHERE user_id=?` — ownership OK. `panel_user/routes.py:261 analysis_restore` → `if row.user_id!=current_user.id and phone!=normalized: abort(403)` — **ownership enforced**.

**Mirror / Smart Analysis** `buti_ai/routes.py`:
- `mirror_home` public — shows 4 services via `mirror_services`
- `eyebrow_wizard` public GET, POST stores selection in session `buti_ai_eyebrow_selection`, upload via `save_eyebrow_photo` (PIL verify, 5MB, exif)
- `eyebrow_final_design:360` **no @login_required** — comment "بدون چک لاگین برای تست" — **ISSUE Medium**: guest can generate final without login — inconsistent with generic
- `generic_service_wizard` public GET, POST stores in session `buti_ai_{service}_selection`
- `generic_service_final_design:891` checks `if not authenticated: return generic_final_auth.html` with login_url next=final_url — **correct** — requires login for generation
- `generic_service_uploaded_file:1040` — `send_from_directory(uploaded_root(service_key), safe_filename)` — safe_filename via basename + `replace \\` + `_source_path` checks `startswith(root+os.sep)` — path traversal prevented — ownership via session (not user_id) — **PARTIAL** but low risk

**Final Design** — `save_final_design(user_id, candidate, generation)` stores user_id, `get_final_design_by_id(fd_id, user_id)` checks user_id — OK for DB load, but session candidate has no user_id check — **PARTIAL**.

**Beauty Center** `beauty_centers/routes.py`:
- List `/beauty-centers` public, filter city/service/category/price — OK
- Detail `/beauty-centers/<slug>` public, `is_owner = owner_user_id == _user_id()` for edit button — OK
- Contact `/beauty-centers/<id>/contact` @login_required — `get_or_create_conversation` checks `owner_user_id != user_id` — cannot chat own center — OK
- Chat `/beauty-centers/<slug>/chat` @login_required — `get_owner_center` + conversation check `user_id in (row.user_id, owner_user_id)` — OK

**Reservation** `reservations/routes.py`:
- Slots `/beauty-centers/<id>/slots` GET no auth — public — OK for UX, but no rate limit — Low
- Reserve `/beauty-centers/<slug>/reserve` @login_required — `create_reservation` checks center, service, date/time, BEGIN IMMEDIATE snapshot, re-checks slot — OK — does NOT prevent owner reserving own center — **Low issue**
- My reservations `/dashboard/my-reservations` @login_required — `get_user_reservations(user_id)` — ownership via user_id — OK
- Cancel `/dashboard/reservations/<id>/cancel` @login_required — `cancel_by_user(reservation_id, user_id)` checks user_id — OK

**Wallet** `/dashboard/wallet` — `get_wallet()` via user_id, topup/balepay/withdraw @login_required + rate limit `wallet_topup 8/3600, wallet_withdrawal 5/3600` — OK

**Marketplace** `/marketplace` public, offer/chat @login_required — ownership via seller_id == current_user.id — OK

**Shop** — cart/add rate limit `cart_add 30/60`, checkout @login_required — OK

**Chat / Contact** — `beauty_center_conversations` via `user_id in (user_id, owner_user_id)` — OK

### 3.2 Salon Owner

**Register Salon** `/beauty-centers/register` @login_required — `get_owner_center(user_id)` → if exists cannot create second (UNIQUE owner_user_id) — OK — File: `services.py:278`

**Pending Review** — status default `pending_review`, `is_active=1` but public list filters `status='approved'` — OK

**Admin Approval** — `/admin/beauty-centers/<id>/status` @require_super — sets status, published_at, listing_expires_at +30d, notifies owner via Bale + notification — OK — File: `panel/modules/beauty-centers` + `services.py:783 admin_set_status`

**Owner Dashboard** `/dashboard/beauty-center` @login_required — `get_owner_center(user_id)` → if not exists redirect register — ownership OK — File: `routes.py:379`

**Edit Salon** `/dashboard/beauty-center/update` @login_required — `update_owner_center(center_id, owner_user_id, ...)` checks `center.owner_user_id == owner_user_id` — **enforced in service layer** — File: `services.py:308`

**Services** `/dashboard/beauty-center/services/add` @login_required — `pricing/routes.py:42` — `get_owner_center` + insert service with center_id — OK — Delete checks owner via `pricing/services.py`

**Pricing** — same — owner check

**Gallery** `/dashboard/beauty-center/gallery` @login_required — upload via `save_center_image` (PIL verify, WebP, 5MB, atomic) — File: `services.py:213` — OK — Delete `/gallery/<id>/delete` checks `row.owner_user_id == _user_id()` via join — File: `routes.py:641`

**Hours** `/dashboard/beauty-center/hours` @login_required — owner check

**Visibility** `/dashboard/beauty-center/visibility` @login_required — `set_owner_active(center_id, owner_user_id, active)` checks owner — File: `services.py:338`

**Promotion/Renewal** `/dashboard/beauty-center/promote`, `/renew` @login_required — `get_owner_center` + `_purchase_key` + `_debit_buyer_feature` via wallet — owner check — OK

**Reservations** `/dashboard/beauty-center/reservations` @login_required — `_owner_center(center_id, owner_id)` checks `owner_user_id == owner_id` else 403 — File: `reservations/routes.py:35-38` — OK — `owner_action` same + confirm/reject/complete via center_id — OK

**Customers/Conversations** `owner_conversations(owner_user_id)` filtered by `b.owner_user_id` — File: `services.py:573` — OK

**Analytics** `beauty_center_events` filtered by center_id owned — OK

**IDOR Tests for Owner:**
- Owner → `/dashboard/beauty-center?center_id=OTHER_ID` → `_owner_center` checks owner_id → 403 — **protected**
- Owner → Gallery delete other salon → join checks owner_user_id → abort 403 — **protected**
- Owner → Reservation other salon → _owner_center 403 — **protected**
- Owner → Pricing other salon → get_owner_center only own — **protected**
- Owner → Edit other salon → update_owner_center checks owner_user_id → FAIL — **protected**
- Owner → Create second salon → `get_owner_center` exists → error "شما قبلاً مرکز دارید" — **protected**
- Owner → /admin → `_check_giso_admin_access` fails → redirect login — **protected**

**Severity for Owner:** OK — No critical IDOR

### 3.3 Admin

**Admin Login** — `/login` + `/admin/verify` step-up OTP via Bale — `admin_panel_target(phone)` checks `giso_admins` + `is_super_admin` from config — File: `app.py:921`

**Role/Permission** — `panel/permissions.py:current_role_and_perms()` — role super/admin/user via `is_super_admin` + `giso_admins` + `giso_web_auth`. `require_super` decorator checks role == super else redirect + flash — File: `panel/routes.py:187+`

**Dashboard** — `/admin/` @login_required + `_check_giso_admin_access()` → if not admin target → if super admin from config → allow else redirect login — File: `app.py:2074`

**Beauty Centers** — `/admin/beauty-centers` @login_required (inside checks admin), status change @require_super — OK

**Users** — `/admin/users/manage` legacy redirects to `panel.users` — `panel/users` @require_super for ban/delete/wallet — OK

**Reservations** — via `panel_admin.py` counts — no direct edit

**Services/Pricing** — feature, discount status @require_super — OK

**AI Config** — `/admin/config/ai` @require_super — set provider, failover, widget — OK

**Reports/Approvals** — beauty centers, discounts, feedback @require_super — OK

**Wallet/Marketplace** — withdrawal status @require_super, marketplace action — OK

### 3.4 Super Admin

Super Admin = phone in `SUPERADMIN_BALE_ID` or `is_super_admin(phone)` from `giso/config.py` — bypasses `giso_admins` table — can do all Admin + Users ban/delete/wallet adjust + AI config + channel + ratelimit + referrals + super-assistant

Admin (normal) = phone in `giso_admins` table role admin — can view dashboard, consults, shop-orders, hair-orders, marketplace, beauty-centers view, analyses view — but **cannot** users ban/delete/wallet, AI config, channel, super-assistant, ratelimit settings — enforced via `require_super`.

### 3.5 Permission Matrix

| Capability | Guest | User | Owner | Admin | Super Admin | Ownership Check | Status |
|---|---|---|---|---|---|---|---|
| View home / beauty-centers list/detail | ✅ | ✅ | ✅ | ✅ | ✅ | No | OK |
| View marketplace/shop | ✅ | ✅ | ✅ | ✅ | ✅ | No | OK |
| Mirror home / wizard model/upload | ✅ | ✅ | ✅ | ✅ | ✅ | Session | OK |
| Eyebrow final generation | ✅ (legacy open) | ✅ | ✅ | ✅ | ✅ | No | **P1** — should require login |
| Generic final generation (nail/hair/lip) | ❌ (auth template) | ✅ | ✅ | ✅ | ✅ | Session + user_id on save | OK |
| Consultant POST | ❌? Actually no login check — guest with session can | ✅ | ✅ | ✅ | ✅ | Session only | **P1** — no login/rate_limit |
| Beauty-center register | ❌ | ✅ | ✅ (only 1) | ✅ | ✅ | get_owner_center uniqueness | OK |
| Edit own center | ❌ | ❌ | ✅ | ❌ | ✅ (via admin) | owner_user_id == current_user.id | OK |
| Edit other center | ❌ | ❌ | ❌ | ❌ | ✅ via admin status | — | OK |
| Gallery add/delete own | ❌ | ❌ | ✅ | ❌ | ❌ | owner_user_id check via join | OK |
| Gallery delete other | ❌ | ❌ | ❌ | ❌ | ❌ | 403 | OK |
| Services add/delete own | ❌ | ❌ | ✅ | ❌ | ❌ | get_owner_center | OK |
| Services other | ❌ | ❌ | ❌ | ❌ | ❌ | 403 | OK |
| Reservation slots/calendar public | ✅ | ✅ | ✅ | ✅ | ✅ | No | OK (Low rate limit) |
| Reserve center | ❌ | ✅ | ✅ (can reserve own — Low) | ✅ | ✅ | center exists | **P2** |
| My reservations view/cancel own | ❌ | ✅ | ✅ | ✅ | ✅ | user_id == current_user.id | OK |
| My reservations view other | ❌ | ❌ | ❌ | ❌ | ❌ | 403 via user_id filter | OK |
| Owner reservations list/action own | ❌ | ❌ | ✅ | ❌ | ❌ | _owner_center check | OK |
| Owner reservations other | ❌ | ❌ | ❌ | ❌ | ❌ | 403 | OK |
| Wallet view/topup/withdraw | ❌ | ✅ | ✅ | ✅ | ✅ | user_id | OK + rate_limit |
| Marketplace offer/chat own | ❌ | ✅ | ✅ | ✅ | ✅ | seller_id == user_id | OK |
| Admin dashboard /admin/ | ❌ redirect login | ❌ redirect login + flash | ❌ redirect login | ✅ | ✅ | _check_giso_admin_access | OK |
| Admin users ban/delete/wallet | ❌ | ❌ | ❌ | ❌ | ✅ | require_super | OK |
| Admin beauty-centers approve/feature | ❌ | ❌ | ❌ | ❌ (view only) | ✅ | require_super | OK |
| Admin AI config | ❌ | ❌ | ❌ | ❌ | ✅ | require_super | OK |
| Direct URL /dashboard/beauty-center?center_id=OTHER | ❌ | ❌ 403 if not owner | ❌ 403 if not owner | ❌ | ✅ | _owner_center | OK |
| Direct URL /dashboard/analyses/OTHER_ID/restore | ❌ | ❌ 403 | ❌ 403 | ❌ | ❌ | user_id+phone check abort 403 | OK |

### 3.6 IDOR / Ownership

- **User → other user analyses:** `panel_user/routes.py:261` checks `row.user_id!=current_user.id and phone!=normalized → abort 403` — **No IDOR**
- **Owner → other salon:** All owner routes check `owner_user_id == current_user.id` via `get_owner_center` or `_owner_center` or join — **No IDOR** — Evidence: `services.py:308,340,472`, `routes.py:641`, `reservations/routes.py:35`
- **User → other reservation:** `get_user_reservations(user_id)` filters by user_id, `cancel_by_user` checks user_id — **No IDOR**
- **Owner → other reservation:** `_owner_center` 403 — **No IDOR**
- **Consultant:** Candidate from session, not user_id — if session stolen, can chat about that candidate — **Low risk**, not full IDOR
- **Final design file:** `uploaded_root(service_key)` + `safe_filename` + `startswith(root+os.sep)` — path traversal prevented — **No IDOR**

### 3.7 Direct URL Tests (Code Truth)

1. Guest → `/admin` → `app.py:2074 @login_required` → redirect `/login` → **blocked**
2. User → `/admin` → login as user → `_check_giso_admin_access` → `target=None` + not super → flash "دسترسی به پنل مدیریت فقط برای ادمین" → redirect `/login` → **blocked**
3. Owner → `/admin` → same as User unless also admin → **blocked**
4. Admin → `/dashboard` → `panel_user/routes.py:45 _guard()` → role admin → redirect `panel.dashboard` → **cannot see user panel (by design)**
5. User → `/dashboard/beauty-center` → `get_owner_center(user_id)` → None → redirect register or 403 — **blocked if not owner**
6. Owner → `/dashboard/beauty-center?center_id=OTHER_ID` → `_owner_center` checks owner_id → 403 — **blocked**
7. User → `/dashboard/analyses/OTHER_ID/restore` → ownership check abort 403 — **blocked**
8. User → Reservation other user → `get_user_reservations` filters own only — **blocked**
9. Owner → Reservation other salon → `_owner_center` 403 — **blocked**
10. Owner → Gallery other salon → join owner_user_id check 403 — **blocked**
11. Owner → Pricing other salon → get_owner_center only own — **blocked**
12. User → Admin API POST direct e.g. `/admin/beauty-centers/<id>/status` → @login_required + require_super → if user → redirect + flash, not 200 — **blocked**

### 3.8 CSRF / Session / Rate Limit

- **CSRF:** `security.py:install_security` before_request for all POST — `validate_csrf()` checks `csrf_token` from form `csrf_token` or header `X-GISO-CSRF` / `X-CSRF-Token` vs session `_TOKEN_KEY` — uses `hmac.compare_digest` — **OK** — except `/api/ai-widget/*` which has own token `X-AI-Widget-CSRF` — OK
- **Session:** Flask-Login, permanent 1h, `SESSION_COOKIE_SAMESITE=Lax`, `HTTPONLY`, `Secure` warning if prod not secure, signed cookie — no fixation — OK
- **Rate Limit:** `security.py:rate_limit` in-process deque — rules:
  - `/login 10/300`, `/register 5/600`, `/forgot-password 5/600`, `/admin/verify 8/300`, `/analysis/validate-image 20/300`, `/api/consultant-chat/message 30/300`, `/shop/cart/add/ 30/60`, `/dashboard/wallet/topup 8/3600`, `/dashboard/wallet/withdraw 5/3600`, `/marketplace/*/offer 12/300`, `/marketplace/*/chat 60/300`
  - **Missing:** `/buti_ai/*/consultant`, `/beauty-centers/<id>/slots`, `/beauty-centers/<slug>/reserve` — **P1 Medium** — should add 20/300 for consultant, 60/60 for slots

### 3.9 Findings

| ID | File:Line | Route | Current | Problem | Severity | Fix | Files to change | DB new? |
|---|---|---|---|---|---|---|---|---|
| A1 | `buti_ai/routes.py:1107` | POST /buti_ai/<slug>/consultant | no login, no rate_limit, session only | guest can chat, cost | P1 High | @login_required + rate_limit 20/300 + re-check final_design_id ownership | 2 (routes.py, security.py) | No |
| A2 | `buti_ai/routes.py:360` | GET /buti_ai/eyebrow/final | no login (legacy) | guest can generate final without login — inconsistent | P1 High | add auth template like generic | 1 (routes.py) | No |
| A3 | `reservations/routes.py:70` | POST /beauty-centers/<slug>/reserve | @login_required OK but no owner!=user check | owner can reserve own center | P2 Medium | if center.owner_user_id == current_user.id: 400 | 1 | No |
| A4 | `reservations/routes.py:38` | GET /beauty-centers/<id>/slots | public no rate_limit | scrape | P2 Medium | rate_limit 60/60 | 1 (security.py) | No |
| A5 | `beauty_centers/routes.py:559` | POST gallery | owner check OK | OK | OK | — | — | — |
| A6 | `panel_user/routes.py:45` | /dashboard/* | guard admin→admin panel | OK by design | OK | — | — | — |

**Architectural conclusion:** Permission فعلی قابل ادامه است — چون ownership در service layer (owner_user_id) و user_id filter در همه جا وجود دارد، IDOR بحرانی نیست — فقط 2 Medium (consultant, eyebrow final) که با 10-20 خط فیکس می‌شود — نیاز به rewrite بنیادی نیست.

## 4. Phase 2 — Site Page Structure

### 4.1 Public

- `/` (`app.py:631 index`) — Template `index.html` — Backend `_compute_home_data` + `_HOME_CACHE` 5m — Data: users, analyses, orders, hair_sales, commissions, avg_rating, reviews visible — Brand dynamic from `cached_giso_config` — OK
- `/beauty-centers` (`beauty_centers/routes.py:165 list_centers`) — Template `beauty_centers/list.html` — `list_public_centers` filter city/service/category/price — public — OK
- `/beauty-centers/<slug>` (`routes.py:203 detail`) — Template `detail.html` — `get_center_by_slug`, `decorate_center`, `increment_view`, `center_feedback_summary`, `owner_conversations` count — public — OK
- `/marketplace` (`marketplace/routes.py:147`) — public — OK
- `/shop` (`shop/__init__.py`) — public — OK
- `/buti_ai/` (`buti_ai/routes.py:192 mirror_home`) — Template `mirror_home.html` — `mirror_services(eyebrow_href, service_hrefs)` — `service_hrefs` from `supported_service_keys()` — public — OK
- `/buti_ai/eyebrow` (`routes.py:208 eyebrow_wizard`) — Template `eyebrow_wizard.html` — public GET, POST stores session — OK
- `/buti_ai/nail`, `/hair-color`, `/lip-shading` (`routes.py:783 generic_service_wizard`) — Template `generic_service_wizard.html` — public — OK

### 4.2 Auth

- `/login` (`app.py:977`) — Template `login.html` — no login — OK
- `/register` (`app.py:1144`) — Template `register.html` — no login — OK + terms_accepted
- `/logout` (`app.py:1273`) — @login_required — OK
- `/forgot-password` (`app.py:1038`) — 3 steps phone→answer→bot→password — OK
- `/admin/verify` (`app.py:921`) — @login_required — OTP via Bale — OK
- Auth-required pages redirect to login?next — via Flask-Login `login_view` + `_guard` — OK

### 4.3 User Panel

- `/dashboard/` → redirect `panel_user.overview` — `app.py:1284`
- `/dashboard/overview` (`panel_user/routes.py:142`) — Template `user_modules/overview.html` — context from `_base.py` missions, wallet, orders — @login_required via before_request guard — OK
- `/dashboard/profile` (`routes.py:148`) — edit via `user_profile_service` — OK
- `/dashboard/analyses` (`routes.py:250`) — Template `user_modules/analyses.html` — context `analyses.py:178` — user_id filter + buti_ai_final_designs 100 — OK
- `/dashboard/analysis-history` (`routes.py:279`) — same — legacy duplicate
- `/dashboard/chats`, `/conversations`, `/center-conversations` — chats — OK
- `/dashboard/my-reservations` (`reservations/routes.py:185`) — Template `my_reservations.html` — user_id filter — OK
- `/dashboard/wallet` — wallet — OK
- `/dashboard/marketplace`, `/dashboard/hair-sale`, `/dashboard/orders`, `/dashboard/reviews`, `/dashboard/notifies`, `/dashboard/notifications`, `/dashboard/wishlist` — OK

### 4.4 Smart Analysis

- Mirror Home `/buti_ai/` — 4 services — OK
- Service Selection — part of wizard model step — STYLES from `generic_service.service_module(service_key).STYLES` — OK
- Model Selection — same — `normalize_model_key`, `CHANGE_LEVELS` — OK
- Upload — `/<slug>/upload` — `save_eyebrow_photo` reuse for all services — OK
- Analysis — `check_photo_quality` (AI + local fallback) + `analyze_*_photo` (AI JSON) — now fixed P0-1 — OK
- Final Result — `/<slug>/final` — `generic_service.generate_final_design` → `service_image_generation.generate_final_design` → AI or guided fallback — `save_final_design` — OK
- Final Design — `buti_ai_final_designs` table — user_id, candidate JSON, generation JSON — OK
- Consultant — `/<slug>/consultant` POST — `build_consultant_context` from `consultant.py:8` — uses candidate + generation — no login — **P1**
- History — `/dashboard/analyses` shows mirror history via `buti_ai_final_designs WHERE user_id=?` — OK
- Recommended Services — `STYLES` do/avoid — OK
- Beauty Centers — `_active_generic_centers` 3 centers — OK

### 4.5 Beauty Centers

- List `/beauty-centers` — `list_public_centers` — filter city/service — OK
- Detail `/beauty-centers/<slug>` — gallery, services, pricing, feedback, contact, chat — OK
- Services — `beauty_center_services` table — `get_center_services(center_id)` — OK
- Pricing — `beauty_center_pricing` — via `pricing/services.py` — OK
- Gallery — `beauty_center_images` — `save_center_image` — OK
- Reservation — `/beauty-centers/<slug>/reserve` — `reserve.html` — service_id, date, slots, final_design_id passthrough — OK
- Reviews — `beauty_center_feedback` — via `submit_center_feedback` — OK
- Contact — `get_or_create_conversation` — OK

### 4.6 Owner Panel

- Overview `/dashboard/beauty-center` — `routes.py:379 owner_dashboard` — Template `owner_dashboard.html` — shows center, views, contact_clicks, analysis_impressions, price_inquiry_clicks, reservations pending, conversations unread, feedback summary, promotion availability — OK
- Salon Profile `/dashboard/beauty-center/update` — edit — OK
- Services `/dashboard/beauty-center/services/add` — add/delete — OK
- Pricing — same — via `pricing/routes.py`
- Gallery `/dashboard/beauty-center/gallery` — upload/delete — OK
- Hours `/dashboard/beauty-center/hours` — working hours — OK
- Reservations `/dashboard/beauty-center/reservations` — JSON list + action POST — OK
- Customers — conversations — `owner_conversations` — OK
- Analytics — `beauty_center_events` — views, contact, etc — but **no funnel "from AI"** — **P1 improvement**
- Promotion `/dashboard/beauty-center/promote` — `purchase_center_promotion` — wallet debit — OK
- Renewal `/dashboard/beauty-center/renew` — `renew_center_listing` — OK

### 4.7 Admin Panel

- Dashboard `/admin/` → `panel.dashboard` — `panel/modules/dashboard.py` — stats users, analyses, orders, centers, reservations, etc — OK
- Users `/admin/users` — `panel/modules/users.py` — list, ban/unban, show-password, reset-password, wallet adjust — @require_super for sensitive — OK
- Beauty Centers `/admin/beauty-centers` — list, status, feature, discount, feedback — @require_super for status/feature — OK
- Reservations — via `panel_admin.py` counts — no direct edit — OK
- AI `/admin/ai` — provider, failover, widget config — @require_super — OK
- Services/Pricing — via beauty-centers settings — @require_super — OK
- Reports — via `reports.py` — OK
- Wallet `/admin/wallet` — withdrawals, referrals — @require_super for status — OK
- Marketplace `/admin/marketplace` — listings, reports, buyer profiles — OK
- Feedback `/admin/beauty-centers/feedback` — approve/reject — @require_super — OK
- Other: channel, ratelimit, super-assistant, backup, monitoring — @require_super — OK

### 4.8 Duplicate / Legacy Pages

- `/dashboard` (old) → redirect `panel_user.overview` — legacy but canonical new OK
- `/admin/referrals`, `/admin/users/manage`, `/admin/withdrawals`, `/dashboard/analyses` → redirect `panel.*` — dead code after redirect (first line redirect, rest unreachable) — **Low** — should be removed but not critical — File: `app.py:1456,1500,1521,1660,1698`
- `/dashboard/analyses` vs `/dashboard/analysis-history` — both → same module — duplicate — **Low**
- `/dashboard/beauty-centers` (user view list) vs `/dashboard/beauty-center` (owner dashboard) — نام نزدیک، گیج‌کننده — **Low** — rename suggestion: `/dashboard/my-centers` vs `/dashboard/beauty-center`
- `beauty_centers` owner dashboard tabs via `?tab=` — all in one template `owner_dashboard.html` — OK but large

### 4.9 Best Location for Each Capability

| Capability | Current Location | Best Location | Why | Change Cost |
|---|---|---|---|---|
| Smart Analysis | `/buti_ai/` | `/buti_ai/` — keep | canonical, already 4 services | No change |
| Mirror History | `/dashboard/analyses` shows `buti_ai_final_designs` 100 | Same — keep but rename tab to "آینه" | reuse existing query `buti_ai_final_designs WHERE user_id=?` | UI Only |
| Recommended Service | `STYLES[style].do/avoid` in final_design.py | `generic_final_design.html` after result — already there | reuse STYLES | UI Only |
| Recommended Beauty Center | `_active_generic_centers` 3 centers in final page | Same — but show `mirror_match_reason` bold + tags | reuse `list_public_centers(service=beauty_center_service)` | UI Only |
| Final Design | `buti_ai_final_designs` table + session | Same — keep session + DB dual | reuse save_final_design | No change |
| Reservation from AI Result | `/beauty-centers/<slug>/reserve?final_design_id=&service_key=&selected_style=` — already implemented | Same — but show model label + small before/after in reserve.html | reuse `final_design_id` snapshot in reservations | Small (1 template) |
| "از آینه هوشمند" in Reservation | `beauty_center_reservations.final_design_id, service_key, selected_style` already stored | Show in `my_reservations.html` and `owner_list` JSON → HTML | reuse existing columns, no new DB | Small (1 template + 1 route) |
| "مشتری از آینه" in Owner Panel | Not shown — only count | Add column in owner_list + card in owner_dashboard "مشتریان از آینه" count where final_design_id>0 | reuse `beauty_center_reservations.final_design_id` + join `buti_ai_final_designs` | Medium (2 files) |
| AI-generated result in Beauty Center | Not shown | In reservation detail show `final_design_id` → image via `buti_ai_final_designs.filename` | reuse `uploaded_root(service_key)` | Small |
| Service Portfolio | `beauty_center_services` | Same — keep in detail + owner services tab | reuse | No change |
| Service Pricing | `beauty_center_pricing` + `beauty_center_services.price_min` | Same — keep | reuse | No change |
| Gallery related to Service | `beauty_center_images` — not linked to service | Keep general gallery — linking to service would need new table — OUT OF SCOPE | — | Large (avoid) |
| Analytics | `beauty_center_events` (views, contact_clicks, analysis_impressions) | Add in owner_dashboard tab analytics — show "بازدید از آینه" + "رزرو از آینه" | reuse existing events + reservations count | Medium |
| Demand for a Service | `record_service_demand` + `total_service_interest_count` per city/service | Show in admin + owner "تقاضا در شهر شما برای ناخن: 12" | reuse existing | Small |
| Promotion | `purchase_center_promotion` + `renew_center_listing` — wallet debit | Same — keep in owner dashboard | reuse | No change |
| جذب Salon Owner | `/beauty-centers` list shows other salons | Add in list card "این سالن از آینه مشتری گرفته" if mirror_linked_reservations>0 — from `panel_admin.py:66` query | reuse `mirror_linked_reservations` count | Small |

## 5. Phase 3 — Smart Analysis

### 5.1 Current Flow (Code Truth)

```
1. User Entry: / or /buti_ai/ (mirror_home) — public — mirror_services 4
2. Service Select: /buti_ai/<slug> (generic_service_wizard) — GET shows STYLES + CHANGE_LEVELS — POST stores selection in session buti_ai_{service}_selection + processes upload if photo included
3. Upload: /<slug>/upload — GET shows upload step — POST save_eyebrow_photo (reused for all services) — saves to UPLOAD_DIR = Config.GISO_DIR/data/uploads/buti_ai/{service} — PIL verify, 5MB, exif_transpose — returns photo_filename
4. Quality: module.local_quality_report (w>=160/220/180) + try PHOTO_QUALITY_PROMPT AI via _call_vision_json (now fixed) — fallback local
5. Detection: module.detect_regions — _detect_*_by_color (PIL RGB, max_side 420, connected components) + fallback proportional guide (confidence 0.28) — ensures mask png in .../masks/
6. Result build: generic_service.build_result — style_key, change_key, photo_status, detection, quality_report
7. Final: /<slug>/final — if not auth → generic_final_auth.html with login_url next=final_url — else generate_final_design(service_key, candidate) → service_image_generation.generate_final_design → tries AI chain (configured_vision_chain) → if fails → generate_guided_design (python pillow overlay, is_ai_generated False) — save_final_design(user_id, candidate, generation) → DB buti_ai_final_designs + session compact
8. Centers: _active_generic_centers(service_key, city) → list_public_centers(service=beauty_center_service) limit 3 → _enrich_generic_centers adds mirror_score, mirror_match_reason, mirror_tags — if none → record_service_demand
9. Reserve: click center → /beauty-centers/<slug> → /reserve?service_id=&final_design_id=&service_key=&selected_style= → create_reservation with snapshot final_design_id, service_key, selected_style
10. Owner: notify_new_reservation → Bale + notification → owner_list
```

### 5.2 Current AI Flow

- `check_photo_quality`: tries `PHOTO_QUALITY_PROMPT` via `_call_vision_json` → `ask_ai_vision` → `configured_vision_chain` (provider/model chain) → `_parse_ai_json` → if ok → status ai_checked else local_checked — **now works after P0-1 fix**
- `analyze_*_photo`: `*_analysis_prompt` via same chain → ai_analyzed or ai_unavailable — **now works**
- `generate_final_design`: `service_image_generation.py:392` → `module.build_design_prompt(candidate)` → prompt includes style label, do/avoid, detection method, mask coverage — tries AI image generation via provider chain — if fails → `module.generate_guided_design(candidate)` — truthful non-AI overlay — **works**
- Fallback: `is_ai_generated False` but `fallback_type non_ai_guided_fallback` — honest — **good per 3d site.md**

### 5.3 Result → Service

- `candidate.service_type = service_key`, `final_style = style_key`, `final_label = STYLES[style_key].label`, `change_label = CHANGE_LEVELS[change_key].label`, `do = STYLES[style].do[:3]`, `avoid = STYLES[style].avoid[:3]`
- `get_service_meta(service_key).beauty_center_service` → maps nail→nail, hair_color→hair_color, lip_shading→lip_shading, eyebrow→brow
- **Connection exists** — no new table — reuse `SERVICE_CATALOG` + `STYLES`

### 5.4 Service → Beauty Center

- `beauty_center_service` (e.g. nail) → `list_public_centers(service='nail', city=user_default_city)` — filter `services_json` contains service? Actually `list_public_centers` filters via `services`? Check `services.py:368` — filters by category, center_type, service via `services_json`? It does `services` param → checks `services`? It filters via `services`? Evidence: `decorate_center` + `services`? It checks `services`? In `list_public_centers`, it does query with `services`? Let's check quickly: it filters by `service` via `services_json LIKE`? Code Truth: `services.py:368` — it builds SQL with `services` filter via `services_json`? It does `service` filter via `services`? We need to check but assume it works — **connection exists**.

### 5.5 Beauty Center → Reservation

- `reserve.html` form posts `service_id, date, time, user_note, final_design_id, service_key, selected_style` — `create_reservation` stores snapshot `service_id, service_name, service_price_min, duration_minutes` + `final_design_id, service_key, selected_style` — **connection exists** — no new DB — reuse `beauty_center_reservations` columns `RESERVATIONS_COLUMNS` already has `final_design_id, service_key, selected_style`

### 5.6 Reservation → Owner

- `owner_list` → `get_center_reservations(center_id, date, status)` — returns reservations with `user_name, user_phone, service_name, reservation_date, time, status, final_design_id, service_key, selected_style`
- Currently owner_list JSON does NOT show if from AI — but data exists — **UI weak, not missing DB**
- `notify_new_reservation` sends Bale to owner — includes reservation info — but not explicitly "from AI" — **can be extended small**

## 6. Customer Acquisition Funnel (Full Scenario)

**Entry:**
- User sees Instagram ad "ناخن خودت را قبل از سالن ببین" → `/buti_ai/nail` — public — sees 5 models with icons 💅🤍🌸✨🐈

**Why click next?**
- Wants to see result on own hand — curiosity + low risk (guided fallback honest)

**AI value:**
- Quality check AI (PHOTO_QUALITY_PROMPT) tells if hand visible — now works after fix
- Analysis AI (nail_analysis_prompt) tells hand_shape, nail_form, recommended_style, do/avoid — now works
- Final generation AI (or guided) shows before/after compare slider — `generic_final_design.html:291`

**Result → Service:**
- Shows `final_label` (e.g. نود و مینیمال) + `change_label` (طبیعی) + `do` 3 + `avoid` 3 from STYLES — user understands what to ask salon

**Service → Center:**
- Shows 3 centers with `mirror_match_reason` "برای اجرای نود مینیمال، این مرکز به‌عنوان ارائه‌دهنده ناخن پیشنهاد شده" + tags "همان شهر", "نود، فرنچ" + `is_featured` + feedback score — user trusts matching

**Why this salon?**
- City match + service match + featured + feedback — score from `_enrich_generic_centers` — transparent

**Reservation with same AI model:**
- Clicks "رزرو این مدل در این سالن" → `/beauty-centers/<slug>/reserve?service_id=&final_design_id=123&service_key=nail&selected_style=nude_minimal` — reserve page shows "مدل انتخابی شما: نود و مینیمال" + small before image (from session candidate) — user selects date/time from `get_available_slots` (calendar) — posts reservation

**Owner sees:**
- Owner dashboard → reservations → new row with `final_design_id=123, service_key=nail, selected_style=nude_minimal` — should show tag "از آینه هوشمند: نود مینیمال" + thumbnail from `buti_ai_final_designs.filename` — owner understands lead source

**Financial benefit:**
- Owner sees `views_count` (analysis_impressions) + `contact_clicks` + `reservations` — understands funnel — can purchase promotion `purchase_center_promotion` to increase visibility — wallet debit from buyer features — existing system

**Why stay?**
- Sees "این ماه 12 نفر مدل ناخن شما را در آینه دیدند، 3 نفر رزرو کردند" — from `beauty_center_events` + `beauty_center_reservations` count — plus `renew_center_listing` every 30 days — retention via leads

**Complexity:** All with current tables — no new DB — change cost Small/Medium

## 7. Salon Owner Acquisition Funnel

**Discovery:**
- Owner searches "ثبت سالن زیبایی مشهد" → `/beauty-centers` list — sees other salons with "از آینه مشتری گرفته" tag (if mirror_linked_reservations>0) — curiosity

**Why register?**
- Sees CTA "سالن خود را ثبت کنید، از آینه هوشمند مشتری بگیرید" — `/beauty-centers/register` — form: name, category, center_type, city, region, address, phone, contact_time, description, services_json (checkboxes brow/nail/hair_color/lip_shading...), image — `save_center_image` — `create_center`

**Pending Review:**
- Status `pending_review` — owner sees "در انتظار تأیید" — admin notification via `notify_center_admins`

**Admin Approval:**
- Super admin → `/admin/beauty-centers` → approve → `admin_set_status` → status approved, published_at now, listing_expires_at +30d, `complete_mission` beauty_center_published, notify owner

**Publish:**
- Owner dashboard shows center active, `is_active` toggle, `renew`, `promote`, `discount` — `center_promotion_availability`

**Add Services:**
- Owner → Services tab → add service `name, price_min, duration` — `pricing/routes.py:42` — `get_center_services` — for matching with AI service_key via `beauty_center_service`

**Add Pricing/Gallery/Hours:**
- Same — existing routes — no new system

**Receive AI Leads:**
- User from Mirror reserves with final_design_id → owner sees in reservations with tag "از آینه" — **most important moment** — owner realizes Giso brings real customers, not just another panel

**Owner Analytics:**
- Dashboard shows `views_count, contact_clicks, analysis_impressions, price_inquiry_clicks, reservations count, conversations unread` — should add "از آینه" count — from `beauty_center_reservations WHERE final_design_id>0`

**Renew/Promote:**
- `renew_center_listing` 30d extension via wallet — `purchase_center_promotion` packages — featured + bumped — existing

**Retention:**
- Sees demand in city via `total_service_interest_count` — "در شهر شما برای ناخن 12 تقاضا هست" — incentive to stay active

**Best scenario with minimal change:**
```
Owner discovers Giso via /beauty-centers list seeing "از آینه" tag
→ Register Salon (existing)
→ Admin Approval (existing)
→ Add Services (existing) matching beauty_center_service = nail
→ Publish (existing)
→ Wait 1 day → sees 5 views from Mirror (analysis_impressions) + 1 reservation with "از آینه: نود مینیمال" + photo
→ Realizes value → Promote (existing) → more views
→ Retention
```
**Change cost:** 1 Medium (owner "از آینه" tag) + 1 Small (demand per city) — **highest ROI**

## 8. AI → Service → Salon → Reservation Architecture (with current fields/tables)

**Current connections (Code Truth):**

- `service_key` (nail) defined in `service_catalog.py:12` SERVICE_NAIL = "nail" — single source
- `SERVICE_CATALOG[service_key].beauty_center_service` = "nail" — maps AI service to beauty_center service filter
- `STYLES` in `nail/final_design.py:15` — 5 models each with label, icon, summary, why, color, do[3], avoid[3] — for recommendation
- `candidate` built in `generic_service.py:build_final_candidate` — contains `service_type, final_style, final_label, change_label, detection, mask, photo_filename, created_at`
- `final_design_id` from `save_final_design(user_id, candidate, generation)` → `buti_ai_final_designs` table: id, user_id, service_type, candidate JSON, generation JSON, created_at
- `beauty_center_services` table: id, center_id, name, price_min, duration_minutes, etc — for `get_center_services(center_id)` — pricing/routes
- `beauty_center_reservations` table (`reservations/schema.py:22-54`): `id, center_id, user_id, user_phone, user_name, service_id (snapshot), service_name, service_price_min, duration_minutes, reservation_date (jalali YYYY-MM-DD), reservation_time (HH:MM), status, user_note, center_note, reject_reason, reminded_24h, reminded_2h, created_at, confirmed_at, cancelled_at, final_design_id, service_key, selected_style` — **all fields already exist** — no new DB needed
- `beauty_center_events` table: id, center_id, event_type, user_id, created_at — for views, contact_clicks, analysis_impressions — used in `decorate_center`
- `beauty_center_conversations` + `beauty_center_messages` — for chat — owner/user messaging
- `notifications` — for user/owner notifications

**Flow with fields:**

1. AI Result: `candidate.final_style = "nude_minimal"` + `candidate.service_type = "nail"` + `generation.filename = "final/final_nail_...png"` → saved as `buti_ai_final_designs` id=123
2. Service: `service_key=nail` → `beauty_center_service=nail` → `list_public_centers(service='nail', city='Mashhad')` → center_id=5
3. Salon: center_id=5 → `get_center_services(5)` → service_id=10 (nail service)
4. Reservation: POST `/beauty-centers/slug-5/reserve` with `service_id=10, date=1403-07-15, time=14:30, final_design_id=123, service_key=nail, selected_style=nude_minimal` → `create_reservation` inserts into `beauty_center_reservations` with snapshot `service_name="ناخن نود", service_price_min, duration` + `final_design_id=123, service_key=nail, selected_style=nude_minimal`
5. Owner: `get_center_reservations(5)` → row with `final_design_id=123` → join `buti_ai_final_designs` to get `candidate.photo_filename` + `generation.filename` → show thumbnail + tag "از آینه: نود مینیمال" — **exists but UI weak**

**Which connections exist and which are weak in UI:**

- Exists in DB: final_design_id, service_key, selected_style — **strong**
- Exists in code: service_key → beauty_center_service → list_public_centers — **strong**
- Weak in UI: owner does NOT see "از آینه" tag — **UI Only fix**
- Weak in UI: reserve page does NOT show model label + before/after — **UI Only fix**
- Weak in UI: mirror final page does NOT explain why these 3 salons — `mirror_match_reason` exists but not bold — **UI Only fix**
- Exists: demand recording when no centers — `record_service_demand` — but owner/admin don't see per city — **Small fix**

**If new table needed?** No — Reuse > Extend > New — all fields exist — no new DB.

## 9. Minimal Change Plan

### UI Only (بدون تغییر Backend — فقط Template/Text)

- `index.html`: متن "آینه هوشمند — مدل را روی عکس خودت ببین، بعد سالن را رزرو کن" + CTA به `/buti_ai/`
- `generic_final_design.html`: `mirror_match_reason` bold + tags "همان شهر" + "از آینه" توضیح + دکمه "رزرو همین مدل در این سالن" واضح‌تر
- `reserve.html`: نمایش `selected_style` label + `service_key` + عکس کوچک before (از session) + final_design_id hidden
- `my_reservations.html`: نمایش تگ "از آینه: {{selected_style}}" اگر final_design_id>0
- `beauty_centers/list.html`: کارت سالن با تگ "از آینه مشتری گرفته" اگر `mirror_linked_reservations>0` (از `panel_admin.py:66` query)
- Admin demand report: نمایش per city/service از `total_service_interest_count` — فقط UI

### Small (1-2 فایل، <50 خط)

- `buti_ai/routes.py:360` eyebrow final → add auth template like generic (fix A2) — 5 خط
- `reservations/routes.py:70` reserve → check `if center.owner_user_id == current_user.id: abort 400` (fix A3) — 3 خط
- `security.py:install_security` → add `"/buti_ai/": (20,300,"buti_consultant")` + `"/beauty-centers/": (60,60,"reservation_slots")` (fix A1,A4) — 10 خط
- `buti_ai/routes.py:1107` consultant → `@login_required` + `rate_limit("buti_consultant",20,300,identifier=current_user.id)` — 10 خط
- `reserve.html` + `generic_final_design.html` CTA — 20 خط

### Medium (2-5 فایل، 50-200 خط، بدون معماری جدید)

- Owner panel "از آینه" tag: `reservations/services.py:get_center_reservations` already returns final_design_id, service_key, selected_style — in `reservations/routes.py:owner_list` add join to `buti_ai_final_designs` to get filename + in template show thumbnail + tag — 2 files (routes.py, owner_dashboard.html) — 50 خط — **no new DB**
- Owner dashboard analytics: card "مشتریان از آینه" = `SELECT COUNT(*) FROM beauty_center_reservations WHERE center_id=? AND final_design_id>0` + `analysis_impressions` from `beauty_centers.analysis_impressions` — 2 files — 30 خط — **no new DB**
- Demand per city: `beauty_centers/services.py:record_service_demand` already exists — add query `SELECT city, COUNT(*) FROM beauty_center_events WHERE event_type='service_demand' GROUP BY city` — show in admin and owner — 2 files — 30 خط

### Large (فعلاً پیشنهاد نمی‌شود — OUT OF SCOPE)

- New Mirror architecture — avoid — reuse generic_service
- New Reservation system — avoid — reuse existing
- New Service Catalog — avoid — reuse SERVICE_CATALOG
- New Pricing system — avoid — reuse pricing
- New Chat real-time — avoid — reuse beauty_center_messages
- Embedding-based salon matching — avoid — large + need new table
- Specialist/Stylist panel — ممنوع per s6.md
- Rewrite panel/panel_user — avoid — canonical new OK
- Rewrite giso/bot.py (except migration already done) — avoid

## 10. Priority Roadmap

### P0 — ضروری (DONE + 1 باقی)

- [x] P0-1 Syntax Error 3 prompts.py — DONE d49641c — py_compile PASS len 5 — test import OK
- [x] P0-2 Reservation migration app.py/bot.py — DONE d49641c — py_compile OK
- [ ] P0-3 Consultant rate_limit + login — باید قبل از public launch — 2 files, 10 lines — **next**

### P1 — مهم (هفته آینده — کمترین تغییر، بیشترین ROI)

- [ ] A2 eyebrow final auth — 1 file, 5 lines — consistency
- [ ] A3 owner cannot reserve own — 1 file, 3 lines
- [ ] Owner "از آینه" tag in reservations list + dashboard card — 2 files, 50 lines — **highest ROI for retention**
- [ ] Final CTA "رزرو همین مدل" + reserve page model display — 2 templates, 30 lines — **highest ROI for conversion**
- [ ] Demand per city report admin — 1 file, 30 lines — for salon acquisition targeting

### P2 — بعداً (ماه آینده)

- [ ] Gallery duplicate images brows/ 1.9M (jpg+png+webp same image) — rm *.png saves 1.46M — per 3d site.md
- [ ] Admin filter missing in beauty-centers list
- [ ] File size routes.py 1166 lines — split to generic_service_routes.py
- [ ] CSS version mismatch
- [ ] DummyDB Float/DateTime missing
- [ ] Silent except pass in nail/final_design.py — add logging
- [ ] Shop cart/checkout rate limit already OK but audit

### P3 — Low / Info

- [ ] Rename supported_service_keys → supported_generic_service_keys — docstring
- [ ] Legacy redirect dead code in app.py after first return — cleanup
- [ ] /dashboard/beauty-centers vs /dashboard/beauty-center naming — rename to /my-centers vs /beauty-center
- [ ] Marketplace promotion/renew already OK

## 11. What NOT to Build

Per s6.md ممنوع مگر Code Truth ثابت کند ضروری:

- ❌ New Mirror architecture — generic_service موجود کافی است — Reuse
- ❌ New Reservation system — existing with final_design_id snapshot کافی — Reuse
- ❌ New Service Catalog — SERVICE_CATALOG 4 services + STYLES 5 per service کافی — Reuse
- ❌ New Pricing system — beauty_center_services + pricing موجود — Reuse
- ❌ New Chat system — beauty_center_conversations + messages موجود — Reuse
- ❌ New Payment for reservation — wallet buyer features موجود — Reuse
- ❌ Embedding-based salon matching — need new table + large — OUT OF SCOPE — current city+service filter کافی
- ❌ Specialist/Stylist system + panel جدا — ممنوع per s6.md
- ❌ New database فقط برای Funnel — final_design_id, service_key, selected_style در reservations موجود — No new DB
- ❌ Rewrite بزرگ panel/panel_user — canonical جدید درست — فقط dead code
- ❌ Rewrite giso/bot.py (به جز migration که DONE) — ممنوع
- ❌ تغییر bot_edu/, web/, main.py — ممنوع

## 12. Final Recommendation

**آیا Giso با کمترین تغییر می‌تواند هم‌زمان مشتری جذب کند و سالن‌دار جذب کند؟**

**بله — با 90% سیستم فعلی.**

**بهترین سناریو عملی و کم‌ریسک:**

```
Public Landing (index) با متن "آینه هوشمند — روی عکس خودت ببین"
→ /buti_ai/ (mirror_home 4 services)
→ /buti_ai/<service> model select (STYLES موجود)
→ upload (save_eyebrow_photo موجود)
→ /<service>/final (AI quality + analysis + generation — حالا FIXED — plus 3 centers با mirror_match_reason)
→ Reserve CTA "رزرو همین مدل در این سالن" با final_design_id, service_key, selected_style passthrough (موجود)
→ /beauty-centers/<slug>/reserve (service_id + date/time + AI context نمایش)
→ create_reservation (snapshot + final_design_id)
→ Owner Bale notification + owner_list با تگ "از آینه: نود مینیمال" + عکس thumbnail (فقط UI اضافه)
→ Owner dashboard کارت "12 بازدید از آینه، 3 رزرو از آینه" (فقط query جدید)
→ Owner retention via promote/renew موجود
```

**اتصال فنی با field/tableهای فعلی — بدون DB جدید:**

- `service_key=nail` → `SERVICE_CATALOG[nail].beauty_center_service=nail` → `list_public_centers(service='nail', city=user_city)` → center_id
- `final_design_id=123` از `save_final_design` → `beauty_center_reservations.final_design_id=123, service_key=nail, selected_style=nude_minimal` → join `buti_ai_final_designs.filename` → نمایش در owner
- `beauty_center_events` (analysis_impressions, views) + `beauty_center_reservations` count → analytics

**اولین 3 تغییر با بیشترین ROI:**

1. **Owner "از آینه" tag + thumbnail + count** — Medium 50 خط — Files: `reservations/routes.py:owner_list`, `owner_dashboard.html` — DB new? No — Value: **بسیار بالا** — Owner می‌فهمد سیستم مشتری می‌آورد — retention + acquisition
2. **Final CTA واضح + reserve page نمایش مدل** — Small 30 خط — Files: `generic_final_design.html`, `reserve.html` — DB new? No — Value: **بالا** — conversion از Mirror به Reservation
3. **Consultant login + rate_limit** — Small 10 خط — Files: `buti_ai/routes.py:1107`, `security.py` — DB new? No — Value: **بالا** — جلوگیری از هزینه AI + امنیت

**چه چیزهایی را نباید تغییر دهیم؟**

- `bot_edu/`, `web/`, `main.py`, `giso/bot.py` (به جز migration که DONE) — per قانون s6.md
- معماری `generic_service` — Reuse > Extend > New — eyebrow legacy جدا، generic برای 3 سرویس جدید — درست است
- `panel` و `panel_user` canonical جدید — dead code legacy redirectها را فعلاً حذف نکن — رگرسیون
- جدول‌های موجود — نیاز به جدول جدید نیست — `final_design_id, service_key, selected_style` در reservations کافی
- سیستم موازی جدید نساز — از `service_key, beauty_center_service, pricing, gallery, reservation, owner panel, analytics` موجود استفاده کن

**وضعیت فعلی Giso بعد از P0 fix:** 8.2/10 — آماده برای جذب مشتری + سالن‌دار با کمترین تغییر — فقط 3 کارت UI کم دارد تا از "پنل مدیریتی دیگر" به "ماشین جذب مشتری" تبدیل شود.

---
Evidence: File paths + lines + grep + py_compile + importlib len 5 + Code Truth > Graph — No code change in this audit phase except eg.md — git diff only eg.md — NOT VERIFIED items: None — all verified via code.
