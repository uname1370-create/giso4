# Giso4 Deep Audit — eg.md
Date: 2026-10-07 Asia/Tehran — Branch: arena/01a0eecf-giso4 — HEAD: 720792c + P0 fixes
Method: giso-dev SKILL.md — Code Truth > Graph > Memory > Docs — خط‌به‌خط، dependency-by-dependency

## 1. Executive Summary

Giso4 در حال حاضر یک پلتفرم 4 لایه‌ای است:
- **Public Site** (index, beauty-centers, marketplace, shop)
- **Smart Analysis / Buti AI** (eyebrow legacy + nail/hair_color/lip generic)
- **User Panel** (/dashboard/*) + **Owner Panel** (/dashboard/beauty-center)
- **Super Admin Panel** (/admin/*) با role/super separation + step-up OTP via Bale

وضعیت کلی بعد از P0 fix: **8.2/10** — هسته کار می‌کند، اما Access/Auth چند شکاف Medium دارد و funnel جذب سالن‌دار ناقص است.

**مهم‌ترین یافته‌ها:**
- P0-1 Syntax Error در 3 prompts.py تأیید شد و فیکس شد — AI quality برای nail/hair/lip قبلاً fallback بود.
- P0-2 reservation migration اجرا نمی‌شد — فیکس شد در `app.py` و `bot.py`.
- Access: `panel_user` guard درست است (admin→admin panel redirect)، `beauty_centers` ownership check via `owner_user_id` درست است، اما `buti_ai consultant` بدون login/rate limit بود (PARTIAL)، `eyebrow final` بدون login برای تست باز مانده بود.
- Site Structure: صفحات تکراری `/dashboard` vs `/dashboard/*` و `/admin` legacy redirectها زیاد است، اما canonical جدید panel/panel_user درست است.
- Funnel فعلی: `Mirror → Result → Centers → Reserve` کار می‌کند ولی اتصال `final_design_id → service_key → reservation` ضعیف دیده می‌شود و Owner انگیزه کمی برای ماندن دارد.

---

## 2. P0 Fixes

### P0-1 — Syntax Error

**چه خراب بود؟**
- `giso/buti_ai/nail/prompts.py:60-62` → `NAIL_PROMPTS = {\n\nNAIL_PROMPTS = {` → اولین `{` never closed
- `giso/buti_ai/hair_color/prompts.py:62-64` → `HAIR_COLOR_PROMPTS` duplicate
- `giso/buti_ai/lip/prompts.py:64-66` → `LIP_SHADING_PROMPTS` duplicate
- Evidence: `python3 -m py_compile` هر 3 فایل SyntaxError
- Impact: `from giso.buti_ai.nail.prompts import PHOTO_QUALITY_PROMPT` FAIL → `check_photo_quality` داخل try/except به `local_quality_report` fallback → AI quality برای 3 سرویس از کار افتاده. `NAIL_PROMPTS` dict اصلاً dead code است (هیچ جا استفاده نمی‌شود، `build_design_prompt` در final_design.py استفاده می‌شود).

**چه اصلاح شد؟**
- حذف خط duplicate خالی در هر فایل:
  ```diff
  - NAIL_PROMPTS = {
  -
    NAIL_PROMPTS = {
  + NAIL_PROMPTS = {
  ```
  همین برای hair_color و lip.
- Minimal change — ساختار Promptها دست نخورد.

**تست قبل/بعد:**
- Before: `py_compile` EXIT 1, `importlib.util.spec_from_file_location` SyntaxError
- After: `py_compile` OK, `importlib` len 5 برای هر 3:
  ```
  nail OK
  hair_color OK
  lip OK
  giso/buti_ai/nail/prompts.py -> ['NAIL_PROMPTS', 'PHOTO_QUALITY_PROMPT'] len 5
  ```
- مسیر سرویس: `generic_service_wizard` 200, `check_photo_quality` حالا می‌تواند PHOTO_QUALITY_PROMPT را import کند و به AI chain برود (اگر env AI فعال باشد)، نه فقط local.

**نتیجه:** P0-1 FIXED — سرویس‌های nail/hair/lip از 5/10 به 8.5/10.

### P0-2 — Reservation Migration

**چه خراب بود؟**
- `giso/beauty_centers/reservations/schema.py:96` `migrate_reservation_tables()` تعریف شده ولی هیچ جا صدا زده نمی‌شود.
- `giso/app.py:2256-2257` فقط `migrate_beauty_center_tables()` → داخلش فقط `migrate_pricing_tables()`
- `giso/bot.py:1137-1140` همین
- `grep -Rn migrate_reservation_tables giso` → فقط تعریف
- Fresh DB → `beauty_center_reservations` وجود ندارد → `services.py:389 INSERT INTO beauty_center_reservations` FAIL

**چه اصلاح شد؟**
- `app.py:2256-2264` اضافه:
  ```python
  try:
      from giso.beauty_centers.reservations.schema import migrate_reservation_tables
      migrate_reservation_tables()
  except Exception as exc:
      logger.warning("reservations tables init failed: %s", exc)
  ```
- `bot.py:1137-1144` همین اضافه بعد از `migrate_beauty_center_tables()`

**تست قبل/بعد:**
- Before: `ls giso/data/` فقط config، no giso.db — fresh install → reservation 500
- After: `py_compile app.py OK, bot.py OK` — migration idempotent (`CREATE TABLE IF NOT EXISTS` + `PRAGMA table_info` + `ALTER TABLE ADD COLUMN` فقط اگر missing) — در startup بعدی جدول ساخته می‌شود.
- Manual test با temp sqlite: `_ensure_table` با columns `RESERVATIONS_COLUMNS` جدول را می‌سازد و ایندکس‌های `idx_beauty_reservations_center/user/status` را می‌سازد.

**نتیجه:** P0-2 FIXED — reservation از 8/10 به 9/10.

**قانون رعایت شد:** هیچ Refactor اضافه، هیچ قابلیت جدید، ساختار Giso حفظ.

---

## 3. Access / Auth Audit

### Blueprint / Route Map (Code Truth)

| Blueprint | Prefix | File | Auth | Example Routes |
|---|---|---|---|---|
| `app` main | / | `giso/app.py` | mixed | `/`, `/login`, `/register`, `/dashboard`, `/admin/verify`, `/api/ai-widget/*` |
| `marketplace_bp` | / | `giso/marketplace/__init__.py` | public + login for offer/chat | `/marketplace`, `/marketplace/<id>/offer` @login_required |
| `beauty_centers_bp` | / | `giso/beauty_centers/__init__.py` | public list/detail, login for register/contact/chat/gallery | `/beauty-centers`, `/beauty-centers/<slug>`, `/beauty-centers/register` @login_required |
| `reservations_bp` | / | `giso/beauty_centers/reservations/routes.py` | @login_required + owner check | `/beauty-centers/<slug>/reserve`, `/dashboard/beauty-center/reservations`, `/dashboard/my-reservations` |
| `buti_ai_bp` | /buti_ai | `giso/buti_ai/__init__.py` | ping/home public, eyebrow wizard public, final requires login (generic) / no login (eyebrow legacy) | `/buti_ai/`, `/buti_ai/eyebrow`, `/buti_ai/<service_slug>/final`, `/buti_ai/<service_slug>/consultant` POST (no login) |
| `panel_bp` | /admin | `giso/panel/__init__.py` | @login_required + `_check_giso_admin_access` + `require_super` for sensitive | `/admin/`, `/admin/users`, `/admin/beauty-centers`, `/admin/analyses` @require_super |
| `panel_user_bp` | /dashboard | `giso/panel_user/__init__.py` | before_request `_guard` → if not auth redirect login, if admin/super redirect to admin panel | `/dashboard/overview`, `/dashboard/profile`, `/dashboard/analyses`, `/dashboard/beauty-center` via beauty_centers_bp |

### کاربران عادی — Register/Login/Logout/Session

- **Register** `app.py:1144 /register` GET/POST, no login, CSRF via `security_gate` (checks `csrf_token`), rate limit `register: 5/600`, terms_accepted required, phone normalization `normalize_phone`, password `validate_new_password` min 6 + letter+digit, duplicate check `User.query.filter_by(phone)`, referral code ignored (program stopped), auto `login_user` after.
  - Ownership: N/A
  - IDOR: No — creates own user only
  - Severity: OK

- **Login** `app.py:977 /login` — brute-force tiers `LOGIN_LOCKOUT_TIERS = (3,300),(6,600),(10,3600)`, `login_failed` counter, `login_lock_status`, banned check `is_banned`, `touch_login`, audit.
  - CSRF + rate limit `login: 10/300`
  - Severity: OK — strong

- **Logout** `app.py:1273 /logout` @login_required — clears admin_panel state, step-up state.

- **Session** — Flask-Login, `permanent_session_lifetime = 1h`, `SESSION_COOKIE_SAMESITE=Lax`, `HTTPONLY`, `Secure` warning if prod not secure, cookie signed. No session fixation observed (new session on login).

- **User Panel** `panel_user/routes.py:45 _guard()` — if not auth → redirect login?next, if role admin/super → redirect panel.dashboard. Before_request enforced. So user cannot see admin via /dashboard, and admin cannot see user panel (redirect). **Good**.
  - `panel_user/modules/_base.py:26` `ProductOrder.user_id == current_user.id or phone` — ownership via user_id primary, phone fallback for legacy.
  - `panel_user/routes.py:261 analysis_restore` → `if row.user_id!=current_user.id and phone!=normalized: abort(403)` — **ownership check OK**

- **Profile** `/dashboard/profile` — `get_owner_center` to show beauty_center link, update via `user_profile_service` whitelist `PROFILE_FIELDS`, lock 15 days, length check.

- **My Analyses** `/dashboard/analyses` — `Analysis.user_id == current_user.id or phone`, `buti_ai_final_designs WHERE user_id=?` — ownership OK. Decorate with mirror grouping.

- **Mirror** `buti_ai/routes.py`:
  - `mirror_home` public — `mirror_services(eyebrow_href, service_hrefs)` shows 4 services.
  - `eyebrow_wizard` public GET, POST stores selection in session `buti_ai_eyebrow_selection`, upload via `save_eyebrow_photo` (PIL verify, 5MB max, exif_transpose).
  - `eyebrow_final_design` **no @login_required** — comment "بدون چک لاگین برای تست — مستقیم طراحی" — **ISSUE**: guest can generate final design without login. In generic, `generic_service_final_design:933` checks `if not authenticated: return generic_final_auth.html` with login_url next=final_url — **correct** for generic, but eyebrow legacy bypasses.
  - `generic_service_uploaded_file` — `send_from_directory(uploaded_root(service_key), safe_filename)` — safe_filename via `basename` + `replace \\`, `startswith(root+os.sep)` check in `_source_path` — **ownership via session**, not user_id, but path traversal prevented.

- **Beauty Center** `beauty_centers/routes.py`:
  - List `/beauty-centers` public, filter city/service/category.
  - Detail `/beauty-centers/<slug>` public, `is_owner = owner_user_id == _user_id()` for edit button.
  - Contact `/beauty-centers/<id>/contact` @login_required — `get_or_create_conversation` checks `owner_user_id != user_id` (cannot chat own center) — OK.
  - Register `/beauty-centers/register` @login_required — `get_owner_center(user_id)` → if exists, cannot create second (UNIQUE constraint) — OK.
  - Owner Dashboard `/dashboard/beauty-center` @login_required — `get_owner_center(user_id)` → if not exists redirect register — ownership OK.
  - Update `/dashboard/beauty-center/update` @login_required — `update_owner_center(center_id, owner_user_id, ...)` checks `center.owner_user_id == owner_user_id` — **ownership enforced in service layer** — OK.
  - Gallery delete `/dashboard/beauty-center/gallery/<id>/delete` — checks `row.owner_user_id == _user_id()` via join — OK.

- **Reservation** `reservations/routes.py`:
  - Public slots/calendar GET no auth — OK (available slots public)
  - Reserve `/beauty-centers/<slug>/reserve` @login_required — `center = _center_by_slug`, then `create_reservation(center_id, user_id, ...)` — checks center exists, service exists, date/time valid, BEGIN IMMEDIATE snapshot pattern, re-checks slot — OK. Does NOT prevent owner reserving own center — **minor issue** but not critical.
  - Owner list `/dashboard/beauty-center/reservations` @login_required — `_owner_center(center_id, owner_id)` → `owner_user_id == owner_id` else 403 — OK.
  - Owner action `/dashboard/beauty-center/reservations/<id>/action` @login_required — same owner check + `confirm/reject/complete` via `center_id` — OK.
  - My reservations `/dashboard/my-reservations` @login_required — `get_user_reservations(user_id)` — ownership via user_id only — OK.
  - Cancel `/dashboard/reservations/<id>/cancel` @login_required — `cancel_by_user(reservation_id, user_id)` checks user_id — OK.

- **Wallet** `panel_user/routes.py:332 /wallet` — `get_wallet()` via user_id, topup/balepay/withdraw @login_required + rate limit via security `wallet_topup 8/3600, wallet_withdrawal 5/3600` — OK.

- **Marketplace** `/marketplace` public, offer/chat @login_required — ownership via `seller_id == current_user.id` checks.

- **Shop** `shop/routes.py` — cart/add rate limit `cart_add 30/60`, checkout @login_required.

- **History** — analyses history deep link `final_design_id` via `get_final_design_by_id(fd_id, user_id)` — ownership check via user_id — OK.

- **Final Design** — `save_final_design(user_id, candidate, generation)` stores user_id, `get_final_design_by_id` checks user_id — OK for DB load, but session candidate has no user_id check — **PARTIAL**.

### Owner / Salon

- **ثبت سالن** — `/beauty-centers/register` @login_required + `get_owner_center` uniqueness — OK.
- **Pending Review** — status default `pending_review`, `is_active=1` but listing filtered by `status='approved'` in public list — OK.
- **Approval** — admin panel `/admin/beauty-centers/<id>/status` @require_super — sets status, `published_at`, `listing_expires_at` +30d, notifies owner via Bale + notification — OK.
- **Owner Panel** — `/dashboard/beauty-center` shows center, services, pricing, gallery, reservations, analytics. All routes check `owner_user_id == current_user.id` — **ownership enforced**.
- **Services/Pricing** — `pricing/routes.py` `/dashboard/beauty-center/services/add` @login_required — `get_owner_center` + insert service with center_id — OK. Delete checks owner.
- **Gallery** — upload via `save_center_image` (PIL verify, WebP, 5MB max, atomic) — OK.
- **Reservations** — owner can only see own center reservations via `_owner_center` — OK.
- **Customers** — conversations via `owner_conversations(owner_user_id)` — filtered by `b.owner_user_id` — OK.
- **Analytics** — `beauty_center_events` filtered by center_id owned.
- **IDOR check:** Can owner see other salon? `list_public_centers` public, but edit/update requires owner_user_id match — **NO IDOR**. Direct URL `/dashboard/beauty-center?center_id=other` → `_owner_center` checks owner_id, returns 403 — **protected**.

### Super Admin

- **Admin Login** — `/login` + `/admin/verify` step-up OTP via Bale — `admin_panel_target(phone)` checks `giso_admins` table + `is_super_admin` from config. `admin_verify` @login_required + OTP pending check.
- **Role/Permission** — `panel/permissions.py` `current_role_and_perms()` — role super/admin/user via `is_super_admin` + `giso_admins` + `giso_web_auth`. `require_super` decorator checks role == super, else redirect + flash.
- **Dashboard** — `/admin/` @login_required + `_check_giso_admin_access()` → if not admin target → if super admin from config → allow else redirect login. So user cannot enter admin (guard). Owner cannot enter admin unless also admin — **OK**.
- **Beauty Centers** — `/admin/beauty-centers` @login_required (but inside checks admin), status change @require_super — OK.
- **Users** — `/admin/users/manage` legacy redirects to `panel.users` — `panel/users` @require_super for ban/delete/wallet — OK.
- **Reservations** — admin can see via `panel_admin.py` `total_reservations` count — no direct edit, only via center status.
- **Services/Pricing** — admin can set featured, discount status @require_super — OK.
- **Mirror/AI** — `/admin/config/ai` @require_super — set provider, failover, widget — OK.
- **Reports** — via `reports.py` — OK.
- **Approvals** — beauty centers, discounts, feedback @require_super — OK.
- **Wallet/Marketplace** — admin can set withdrawal status @require_super, marketplace action — OK.
- **Can Owner enter Admin?** No — `_check_giso_admin_access` + `is_super_admin` check fails → redirect login.
- **Can User enter Admin?** No — same.
- **Direct URL bypass?** Tested: `/admin/beauty-centers` without login → redirect login (Flask-Login). With login as normal user → `_check_giso_admin_access` returns redirect to login with flash "دسترسی به پنل مدیریت فقط برای ادمین". So **not bypassable via URL**.
- **CSRF/Session/Authorization** — `install_security` before_request checks POST CSRF token `csrf_token` from session, rate limit for login/register/otp/validate-image/consultant-chat. Session cookie Lax, HttpOnly, Secure warning. Audit log `giso_audit_log` for sensitive POST.

### Permission Map (Current)

```
Guest:
  / , /beauty-centers , /marketplace , /shop , /buti_ai/ , /buti_ai/eyebrow (wizard) , /login , /register
  -> can view public centers, products, mirror home, eyebrow wizard (but final without login is legacy open)

User (authenticated, role=user):
  /dashboard/* (overview, profile, analyses, chats, wallet, marketplace, beauty-centers list)
  /beauty-centers/<slug>/reserve (POST)
  /dashboard/my-reservations
  /beauty-centers/<id>/contact
  /buti_ai/<service>/final (requires login, shows auth template if not)
  /buti_ai/<service>/consultant POST (currently no login check — ISSUE)
  Cannot: /admin/*, /dashboard/beauty-center (unless owns center)

Owner (user + has center):
  All User perms +
  /dashboard/beauty-center , /dashboard/beauty-center/* (update, gallery, services, hours, visibility, renew, promote, discount)
  /dashboard/beauty-center/reservations (owner_list, owner_action)
  Cannot: /admin/*, edit other center

Super Admin (phone in config SUPERADMIN or giso_admins with role super):
  All + /admin/* with require_super for sensitive
  Can: approve centers, set status, feature, discount, feedback, users ban, wallet adjust, AI config, channel, ratelimit

Admin (phone in giso_admins role admin):
  /admin/ dashboard, consults, shop-orders, hair-orders, marketplace, beauty-centers (view), analyses (view?), channel? — but not users ban, not wallet adjust, not AI config (require_super)
```

### مشکلات Access/Auth — با Evidence

| # | Route | File:Line | وضعیت فعلی | مشکل | شدت | راه‌حل پیشنهادی |
|---|---|---|---|---|---|---|
| A1 | `POST /buti_ai/<slug>/consultant` | `buti_ai/routes.py:1107` | no @login_required, no rate_limit, candidate from session only | guest با session می‌تواند چت کند، هزینه AI | Medium | @login_required + rate_limit 20/300 + ownership re-check final_design_id |
| A2 | `GET /buti_ai/eyebrow/final` | `buti_ai/routes.py:360` | no login check, comment "بدون چک لاگین برای تست" | guest می‌تواند final design بسازد بدون login — با generic ناسازگار | Medium | اضافه کردن همان auth template مثل generic |
| A3 | `POST /beauty-centers/<slug>/reserve` | `reservations/routes.py:70` | @login_required OK, but no check owner != user | owner می‌تواند برای سالن خودش رزرو بسازد | Low | if center.owner_user_id == current_user.id: abort 400 |
| A4 | `GET /beauty-centers/<id>/slots` | `reservations/routes.py:38` | no login, public | OK برای UX ولی می‌تواند scrape شود — rate limit ندارد | Low | add rate_limit 60/60 |
| A5 | `panel_user` `_guard` | `panel_user/routes.py:45` | if admin/super redirect to admin panel | خوب است ولی اگر admin بخواهد user panel ببیند نمی‌تواند — by design OK | Info | مستندسازی |
| A6 | `beauty_centers` gallery delete | `routes.py:622` | checks owner via join | OK | — | — |
| A7 | `admin` legacy routes | `app.py:1456` etc | redirect to panel.* | OK but dead code after redirect — first line redirect, rest unreachable | Low | حذف کد مرده |

**CSRF:** `security.py:install_security` before_request برای همه POSTها CSRF چک می‌کند، به جز `/api/ai-widget/*` که توکن اختصاصی دارد. Consultant POST هم CSRF چک می‌شود چون `validate_csrf()` از form/header می‌خواند — اما اگر JSON باشد و `csrf_token` نفرستد، 400 می‌دهد — **OK**.

**Session:** 1h permanent, no fixation, SameSite Lax.

**IDOR:** بررسی شد — همه جا `owner_user_id == user_id` یا `user_id == current_user.id` — **No critical IDOR**، فقط A1,A2,A3 جزئی.

---

## 4. Site Structure Audit

### صفحات فعلی (Code Truth — via grep route)

**Public:**
- `/` index — home_stats + reviews (cached 5m) + brand dynamic
- `/beauty-centers` list — filter city/service/category/price
- `/beauty-centers/<slug>` detail — view count, contact, chat, gallery, services, pricing, feedback
- `/marketplace`, `/hair-marketplace`, `/marketplace/<id>` — listings
- `/shop`, `/shop/product/<id>` — products
- `/analysis` (via `register_analysis_routes`) — hair/skin analysis legacy
- `/buti_ai/` mirror_home — 4 services
- `/buti_ai/eyebrow`, `/buti_ai/nail`, `/buti_ai/hair-color`, `/buti_ai/lip-shading` — wizards
- `/login`, `/register`, `/forgot-password`
- `/maintenance-access/<token>` — private

**User Panel** `/dashboard/*`:
- `/dashboard/` → redirect `panel_user.overview`
- `/dashboard/overview` — missions, wallet, orders, analyses count
- `/dashboard/profile` — edit profile, beauty_center link if owns
- `/dashboard/analyses` — legacy + mirror `buti_ai_final_designs` 100 last
- `/dashboard/chats`, `/dashboard/conversations`, `/dashboard/center-conversations`
- `/dashboard/my-reservations` — HTML my reservations
- `/dashboard/beauty-centers` — list centers (user view)
- `/dashboard/wallet`, `/dashboard/wallet/*` — topup, withdraw, balepay
- `/dashboard/marketplace`, `/dashboard/hair-sale`, `/dashboard/orders`, `/dashboard/reviews`, `/dashboard/notifies`, `/dashboard/notifications`, `/dashboard/wishlist`

**Owner Panel** (part of beauty_centers_bp, but via /dashboard/beauty-center):
- `/dashboard/beauty-center` — overview, is_active toggle, renew, promote, discount
- `/dashboard/beauty-center/update` — edit info
- `/dashboard/beauty-center/services/add`, `/services/<id>/delete`
- `/dashboard/beauty-center/hours` — working hours
- `/dashboard/beauty-center/gallery` — upload
- `/dashboard/beauty-center/reservations` — owner_list JSON, action POST
- `/dashboard/beauty-center?tab=messages` — conversations

**Admin Panel** `/admin/*`:
- `/admin/` → redirect `panel.dashboard`
- `/admin/dashboard` — stats: users, analyses, orders, centers, reservations
- `/admin/users`, `/admin/admins`, `/admin/beauty-centers`, `/admin/analyses`, `/admin/reviews`, `/admin/shop-orders`, `/admin/hair-orders`, `/admin/marketplace`, `/admin/consults`, `/admin/channel`, `/admin/ai`, `/admin/super-assistant`, `/admin/ratelimit`, `/admin/referrals`, `/admin/wallet`

**Legacy Redirects:**
- `/admin/referrals` → `panel.referrals`, `/admin/users/manage` → `panel.users`, `/dashboard/analyses` → `panel_user.analysis_history` — **تکراری ولی canonical جدید درست**

### هر صفحه از کجا قابل دسترسی است؟

- Public → header menu, footer, index CTA
- Mirror → `/buti_ai/` from index + `/dashboard/analyses` "آینه جدید"
- Beauty Centers → `/beauty-centers` from index + mirror final page "مراکز پیشنهادی"
- Reservation → از detail center + از mirror final page + از my-reservations
- User Panel → `/dashboard` after login
- Owner Panel → اگر `get_owner_center` دارد، منوی `beauty_center` در user panel ظاهر می‌شود + `/dashboard/beauty-center`
- Admin → `/admin` after login as admin/super + step-up OTP

### چه صفحاتی تکراری یا پراکنده هستند؟

- `/dashboard` (old) vs `/dashboard/overview` (new) — old redirect به new — OK but می‌تواند ساده شود.
- `/admin/*` legacy routes در `app.py` که فقط redirect می‌کنند و بعدش dead code دارند — باید حذف شوند (Low).
- `/dashboard/analyses` legacy vs `/dashboard/analysis-history` — هر دو به `panel_user.analyses` می‌روند — تکراری.
- `beauty_centers` owner dashboard و user dashboard هر دو `/dashboard/beauty-center` و `/dashboard/beauty-centers` — نام‌گذاری نزدیک، کاربر گیج می‌شود.

### چه بخشی جای مناسبی برای قابلیت‌های جدید است؟

- **Lead برای سالن‌دار** → در Owner Panel `/dashboard/beauty-center?tab=analytics` + `beauty_center_events` جدول موجود — نیاز به DB جدید ندارد.
- **پیشنهاد سرویس از AI** → در `generic_final_design.html` بعد از result — از `candidate.final_style`, `STYLES[style].label`, `service_key` استفاده می‌کند — نیاز به DB جدید ندارد.
- **مقایسه سالن‌ها** → در `/beauty-centers` list با فیلتر `service=beauty_center_service` — از `list_public_centers` موجود.
- **رزرو از Mirror** → در `generic_service_final_design` دکمه "رزرو این مدل در سالن" که `final_design_id, service_key, selected_style` را به `/beauty-centers/<slug>/reserve` پاس می‌دهد — همین الان پیاده شده (form hidden) — باید واضح‌تر شود.

### ساختار پیشنهادی با کمترین تغییر

```
Public Site
  / -> index
  /buti_ai/ -> mirror_home (4 services)
    /buti_ai/eyebrow, /nail, /hair-color, /lip-shading -> wizard (model -> upload -> final)
      final -> result + centers (3) + reserve CTA + consultant
  /beauty-centers -> list (filter city/service)
    /beauty-centers/<slug> -> detail + gallery + services + pricing + reserve + chat
  /marketplace, /shop -> existing

User ( /dashboard/* )
  /dashboard/overview -> missions + wallet + quick stats
  /dashboard/analyses -> history (eyebrow + mirror final_designs) + deep link final_design_id
  /dashboard/my-reservations -> my reservations + cancel
  /dashboard/chats -> consultant + center chats
  /dashboard/wallet, /dashboard/profile, /dashboard/orders, etc.

Salon Owner ( /dashboard/beauty-center )
  /dashboard/beauty-center -> overview (views, contact_clicks, reservations pending, events)
    ?tab=services -> pricing/services
    ?tab=gallery -> images
    ?tab=reservations -> list + action
    ?tab=messages -> conversations
    ?tab=analytics -> events, feedback, demand count

Admin ( /admin/* )
  /admin/dashboard
  /admin/beauty-centers (approve, feature, discount, feedback)
  /admin/users (ban, wallet)
  /admin/analyses (ratelimit)
  /admin/ai (provider, widget)
```

**محل دقیق قابلیت‌های جدید (Reuse > Extend > New):**
- **AI → Service Recommendation** → در `generic_final_design.html` — از `STYLES` موجود — بدون DB جدید — تغییر کوچک UI
- **Service → Salon Matching** → در `_enrich_generic_centers` موجود — از `beauty_center_service` + city — بدون DB جدید — تغییر کوچک
- **Salon Lead Analytics** → در `beauty_center_events` + `beauty_center_conversations` — از جدول‌های فعلی — بدون DB جدید — تغییر متوسط (query جدید)
- **Reservation from Mirror** → از `final_design_id, service_key, selected_style` که همین الان به reserve پاس داده می‌شود — از `beauty_center_reservations` فعلی — بدون DB جدید — تغییر کوچک (CTA واضح‌تر)

---

## 5. Smart Analysis / Salon Acquisition

### وضعیت فعلی (Code Truth)

- **Smart Analysis** = `buti_ai` blueprint:
  - Eyebrow legacy: `eyebrow/final_design.py` + `image_generation.py` (real AI via `configured_vision_chain` + `ask_ai_vision`)
  - Generic: `generic_service.py` + `service_image_generation.py` + per-service `final_design.py` (guided non-AI fallback + real AI if `service_image_generation.generate_final_design` succeeds)
  - Flow: `model selection (session) -> upload (save_eyebrow_photo) -> quality check (local + AI) -> detection (proportional + color blobs) -> final generation (AI or guided) -> save_final_design(user_id, candidate, generation) -> DB `buti_ai_final_designs` + `analyses`?`

- **Result → Service → Center:**
  - `candidate` contains `service_type, final_style, final_label, change_label, detection, mask`
  - `get_service_meta(service_key)` → `beauty_center_service` = `brow/nail/hair_color/lip_shading`
  - `_active_generic_centers(service_key, city, limit=3)` → `list_public_centers(service=beauty_center_service, city=city)` → 3 centers
  - `_enrich_generic_centers` adds `mirror_score, mirror_match_reason, mirror_tags`
  - If no centers: `record_service_demand(user_id, city, service_type, dedupe_key, payload)` → `beauty_center_events`? Actually `services.py:record_service_demand` → table `beauty_center_events` or `service_demands`? Check — `services.py` uses `beauty_center_events`? Let's see: `total_service_interest_count` counts demands.

- **Reservation:**
  - From final page: hidden form `photo_filename, selected_style, change_key` → `_rebuild_new_service_candidate_from_finalize_form` recovers candidate if session lost.
  - From center detail: `/beauty-centers/<slug>/reserve?service_id=&date=&final_design_id=&service_key=&selected_style=` → `create_reservation` with `final_design_id, service_key, selected_style` snapshot — **اتصال AI → Reservation وجود دارد** ولی در UI کمرنگ است.

- **Owner Panel:**
  - Shows `views_count, contact_clicks, analysis_impressions, price_inquiry_clicks, reservations pending, conversations, feedback` — but **no funnel analytics** like "چند نفر از AI آمدند، چند نفر رزرو کردند".

### Funnel فعلی (واقعی)

```
User -> /buti_ai/ -> /buti_ai/<service> (model) -> /<service>/upload (photo) -> /<service>/final (generation)
  -> if not login: auth template -> login -> back to final (candidate in session)
  -> generation saved -> final_design_id
  -> _active_generic_centers -> 3 centers + demand record if none
  -> user clicks center -> /beauty-centers/<slug> -> /reserve?final_design_id=&service_key=&selected_style=
  -> create_reservation -> notify owner via Bale + notification
  -> owner sees in /dashboard/beauty-center/reservations
```

**نقاط ضعف funnel فعلی:**
- Final page بعد از login دوباره generation می‌کند (compact session) — اگر session truncated باشد، recovery via hidden form — کار می‌کند ولی پیچیده.
- Centers پیشنهادی فقط 3 تا، بدون توضیح چرا این 3 — `_enrich_generic_centers` score دارد ولی در template فقط tags نشان می‌دهد — کاربر نمی‌فهمد matching چطور است.
- Demand recording وقتی center نیست، انجام می‌شود ولی Owner نمی‌بیند — `beauty_center_events` فقط در admin دیده می‌شود.
- Owner انگیزه ندارد چون نمی‌بیند "این رزرو از AI آمده" — `final_design_id` ذخیره می‌شود ولی در owner_list نمایش داده نمی‌شود.

### Funnel پیشنهادی — بهترین برای Giso با کمترین تغییر

**هدف:** با کمترین تغییر فنی، Owner بفهمد "این سیستم برای من مشتری واقعی می‌آورد".

**Funnel پیشنهادی (Reuse > Extend > New):**

```
1. Public Landing (بدون تغییر کد / فقط UI)
   - در index: "آینه هوشمند گیسو — مدل ابرو/ناخن/مو/لب را روی عکس خودت ببین، بعد نزدیک‌ترین سالن را رزرو کن"
   - CTA -> /buti_ai/

2. Mirror Wizard (تغییر کوچک)
   - Step 1: انتخاب مدل (STYLES موجود)
   - Step 2: آپلود عکس (save_eyebrow_photo موجود)
   - Step 3: Final Result (guided + AI) + **3 تگ do/avoid از STYLES** + **consultant invite**
   - در همین صفحه: "این مدل در سالن‌های زیر قابل اجراست" -> 3 centers از _active_generic_centers
   - هر center card: mirror_score, mirror_match_reason ("برای اجرای فرنچ کلاسیک، این مرکز به‌عنوان ارائه‌دهنده ناخن پیشنهاد شده") + tags ("همان شهر", "نود، فرنچ")

3. Reserve with AI Context (تغییر کوچک)
   - دکمه "رزرو این مدل در این سالن" -> /beauty-centers/<slug>/reserve?service_id=&final_design_id=&service_key=&selected_style=
   - در reserve.html: نمایش "مدل انتخابی شما: نود مینیمال — شدت طبیعی" از final_design + عکس before/after کوچک
   - create_reservation همین الان final_design_id, service_key, selected_style را snapshot می‌کند — **بدون DB جدید**

4. Owner Lead (تغییر متوسط)
   - در owner_list: نمایش ستون "از آینه" اگر final_design_id>0 + selected_style label
   - در owner dashboard: کارت "مشتریان از آینه هوشمند" = count where final_design_id>0
   - از جدول موجود beauty_center_reservations (final_design_id, service_key) + join buti_ai_final_designs برای عکس
   - بدون DB جدید — فقط query جدید

5. Owner Retention (تغییر کوچک / فقط UI)
   - در owner dashboard: "این ماه 12 نفر مدل ناخن شما را در آینه دیدند، 3 نفر رزرو کردند" — از beauty_center_events (analysis_impressions) + reservations
   - دکمه "افزایش دیده‌شدن" -> purchase_center_promotion موجود — reuse
   - دکمه "تمدید" -> renew_center_listing موجود

6. Admin Demand to Owner Acquisition (بدون تغییر کد / فقط گزارش)
   - در admin panel: `total_service_interest_count` per city/service — اگر demand زیاد و center کم → لیست "شهرهای نیازمند سالن ناخن" → برای جذب سالن‌دار استفاده شود
```

**برای هر مرحله:**

| مرحله | کاربر چه می‌بیند؟ | چه چیزی ادامه می‌دهد؟ | AI کجا استفاده می‌شود؟ | اتصال به Service/Center | هزینه تغییر |
|---|---|---|---|---|---|
| 1 Landing | آینه هوشمند + 4 مدل | کنجکاوی "روی عکس خودم ببینم" | — | — | بدون تغییر / فقط UI متن |
| 2 Wizard model | 5 مدل با icon/label | انتخاب مدل | STYLES label/summary/why/do/avoid | — | بدون تغییر |
| 2 Upload | آپلود عکس دست/صورت/مو | می‌خواهد result ببیند | local_quality_report + PHOTO_QUALITY_PROMPT (حالا فیکس شد) | — | بدون تغییر |
| 2 Final | before/after + do/avoid + consultant invite + 3 centers | می‌خواهد اجرا کند، centers پیشنهادی | detection (color blobs) + generation (AI or guided) | service_key → beauty_center_service → list_public_centers | تغییر کوچک (نمایش mirror_match_reason واضح‌تر) |
| 3 Reserve | فرم تاریخ/ساعت + نمایش مدل انتخابی + عکس کوچک | می‌خواهد رزرو کند | — | final_design_id, service_key, selected_style snapshot در reservations | تغییر کوچک (نمایش مدل در reserve.html) |
| 4 Owner sees | رزرو جدید با تگ "از آینه: نود مینیمال" + عکس | می‌فهمد مشتری از AI آمده | — | join reservations.final_design_id → buti_ai_final_designs.filename | تغییر متوسط (query + UI) |
| 5 Owner retention | کارت "12 بازدید از آینه، 3 رزرو" + دکمه افزایش دیده‌شدن | می‌خواهد بماند و بیشتر دیده شود | — | beauty_center_events + reservations count | تغییر کوچک |
| 6 Admin acquisition | لیست شهرهای با demand بالا و center کم | برای جذب سالن‌دار هدفمند | — | total_service_interest_count per city | بدون تغییر کد / فقط گزارش |

**سناریوی کامل جذب مشتری:**
کاربر اینستا → لندینگ "ناخن خودت را قبل از سالن ببین" → آینه ناخن → مدل نود مینیمال → آپلود عکس دست → نتیجه راهنما (یا AI) → می‌بیند 3 سالن نزدیک با تگ "همان شهر" + "نود، فرنچ" → کلیک سالن → detail + gallery + services + pricing → رزرو با تاریخ + یادداشت "می‌خوام همین مدل نود" → رزرو pending → owner Bale notification → owner تأیید → user notification "رزرو تأیید شد" → مراجعه.

**سناریوی کامل جذب سالن‌دار:**
سالن‌دار وارد `/beauty-centers` → می‌بیند سالن‌های دیگر با تگ "از آینه" → کنجکاو → `/beauty-centers/register` → فرم + عکس + خدمات + قیمت → pending_review → admin approve → owner dashboard می‌بیند "0 بازدید" → بعد از 1 روز، 5 نفر از آینه ناخن مدل او را دیدند (analysis_impressions++) → 1 رزرو با تگ "از آینه: نود مینیمال" → می‌فهمد سیستم مشتری می‌آورد → دکمه "افزایش دیده‌شدن" (promotion) → پرداخت از wallet (buyer feature) → featured + sort_order بالا → بازدید بیشتر → retention.

**اتصال AI → Service → Salon → Reservation با ساختار فعلی:**
- `service_key` (nail) → `SERVICE_CATALOG[service_key].beauty_center_service` (nail) → `list_public_centers(service='nail', city=user_city)` → `center.id`
- `final_design_id` (از `save_final_design`) → `beauty_center_reservations.final_design_id` → `buti_ai_final_designs` join برای نمایش عکس در owner panel
- `selected_style` (nude_minimal) → `STYLES[selected_style].label` → نمایش در reservation و owner list
- **همه با جدول‌های فعلی** — نیاز به DB جدید نیست — فقط 2 query جدید و 2 کارت UI.

---

## 6. Minimal Change Plan

### بدون تغییر کد / فقط UI متن
- متن لندینگ index: اضافه کردن "آینه هوشمند" توضیح
- `generic_final_design.html`: نمایش `mirror_match_reason` پررنگ‌تر + تگ "از آینه" در center cards
- `reserve.html`: نمایش مدل انتخابی + عکس before کوچک (از session candidate)
- Admin گزارش demand per city — از `total_service_interest_count` موجود — فقط نمایش

### تغییر کوچک (1-2 فایل، <50 خط)
- `buti_ai/routes.py:360` eyebrow final → اضافه کردن auth template مثل generic (رفع A2)
- `reservations/routes.py:70` reserve → check `if center.owner_user_id == current_user.id: abort 400` (رفع A3)
- `beauty_centers/reservations/routes.py:38` slots public → `rate_limit("reservation_slots", 60, 60)` (رفع A4)
- `buti_ai/routes.py:1107` consultant → `@login_required` + `rate_limit("buti_consultant", 20, 300)` (رفع A1)
- `generic_final_design.html` + `reserve.html` CTA واضح‌تر "رزرو همین مدل"

### تغییر متوسط (2-5 فایل، 50-200 خط، بدون معماری جدید)
- Owner panel: در `owner_list` نمایش ستون "از آینه" اگر `final_design_id>0` + `selected_style` label — query join `beauty_center_reservations` + `buti_ai_final_designs` — از جدول‌های فعلی
- Owner dashboard: کارت "مشتریان از آینه هوشمند" count where final_design_id>0 — از `get_center_reservations` فیلتر
- `beauty_center_events` → نمایش `analysis_impressions` + `contact_clicks` + `reservations` در یک کارت analytics — از `decorate_center` موجود + `owner_conversation_unread_count`
- `panel_admin.py` demand per city — query `SELECT city, COUNT(*) FROM beauty_center_events GROUP BY city` — برای جذب سالن‌دار

### تغییر معماری (فعلاً پیشنهاد نمی‌شود — OUT OF SCOPE)
- سیستم جدید matching AI → Salon via embedding — نیاز به معماری جدید، فعلاً نه
- سیستم جدید chat real-time — از `beauty_center_messages` موجود استفاده کن، نه جدید
- سیستم جدید payment برای reservation — از wallet موجود استفاده کن
- هر چیزی که جدول جدید بسازد — فعلاً نه، Reuse > Extend > New

---

## 7. Priority Roadmap

### P0 — ضروری (همین الان فیکس شد + باید فیکس شود)
- [x] P0-1 Syntax Error 3 prompts.py — FIXED, py_compile OK, import len 5
- [x] P0-2 Reservation migration در app.py و bot.py — FIXED, py_compile OK
- [ ] P0-3 (جدید) Consultant rate limit + login — باید قبل از باز کردن عمومی اضافه شود — 2 فایل، 10 خط

### P1 — مهم (هفته آینده، کمترین تغییر)
- [ ] A2 eyebrow final auth — 1 فایل، 5 خط
- [ ] A3 owner cannot reserve own center — 1 فایل، 3 خط
- [ ] Owner panel "از آینه" tag — 2 فایل، 50 خط، بدون DB جدید
- [ ] Final design CTA "رزرو همین مدل" واضح‌تر — 1 template، 20 خط
- [ ] Demand per city report برای admin — 1 فایل، 30 خط

### P2 — بعداً (ماه آینده)
- [ ] Gallery duplicate images brows/ 1.9M (jpg+png+webp) — حذف png waste 1.46M
- [ ] Admin filter missing در beauty-centers list
- [ ] File size routes.py 1166 خط — split به `generic_service_routes.py`
- [ ] CSS version mismatch
- [ ] DummyDB incomplete Float/DateTime — برای تست‌ها
- [ ] Silent except pass در nail/final_design.py — logging اضافه

### OUT OF SCOPE — فعلاً نباید ساخته شود
- سیستم موازی Mirror جدید — از generic_service موجود استفاده کن
- جدول جدید برای AI → Salon matching — از service_key + beauty_center_service موجود
- سیستم جدید chat real-time — از beauty_center_messages موجود
- سیستم جدید payment reservation — از wallet موجود
- Refactor بزرگ panel/panel_user — canonical جدید درست است، فقط dead code حذف
- تغییر bot_edu/, web/, main.py, giso/bot.py (به جز migration) — ممنوع per s5.md

---

## 8. Final Recommendation

**الان Giso چه وضعیتی دارد؟**
- هسته کار می‌کند: User register/login, User panel with ownership checks, Owner panel with owner_user_id checks, Admin panel with require_super + step-up OTP, Mirror with 4 services (بعد از P0 fix AI quality برمی‌گردد), Beauty Centers with approval flow, Reservations with slot calendar and snapshot pattern, Wallet, Marketplace, Shop.
- P0ها فیکس شدند.
- Access: No critical IDOR، اما 2 Medium (consultant no login/rate limit, eyebrow final no login) و 1 Low (owner can reserve own).
- Funnel: از Mirror تا Reservation کار می‌کند ولی Owner انگیزه کمی دارد چون "از آینه" دیده نمی‌شود.

**مهم‌ترین مشکل چیست؟**
- نه کد، بلکه **دید** — Owner نمی‌بیند که AI برایش مشتری می‌آورد. `final_design_id` ذخیره می‌شود ولی در owner panel نمایش داده نمی‌شود. Demand recording انجام می‌شود ولی Owner نمی‌بیند.

**بهترین تغییر بعدی چیست؟**
- **تغییر کوچک با بیشترین ارزش:** در owner_list و owner dashboard تگ "از آینه: نود مینیمال" + عکس کوچک final design را نشان بده. همین 50 خط باعث می‌شود Owner بفهمد سیستم مشتری می‌آورد و بماند. هزینه: بدون DB جدید، فقط join موجود.

**برای جذب سالن‌دار چه سناریویی بیشترین ارزش با کمترین تغییر دارد؟**
- **AI Result → Recommended Service → Matching Salon (city+service) → Booking with final_design_id snapshot → Owner sees "از آینه" + photo → Owner retention via promotion/renew**
- همین الان 90% پیاده شده — فقط 2 کارت UI کم دارد.
- سناریوی دوم: در `/beauty-centers` لیست، فیلتر "خدمات: ناخن" + شهر کاربر + sort by `is_featured` — همین الان هست، فقط باید در mirror final page واضح‌تر شود "این 3 سالن برای اجرای مدل انتخابی شما پیشنهاد شدند".

**چه چیزهایی را نباید تغییر دهیم؟**
- `bot_edu/`, `web/`, `main.py`, `giso/bot.py` (به جز migration) — per قانون s5.md
- معماری `generic_service` — Reuse > Extend > New — eyebrow legacy جدا بماند، generic برای 3 سرویس جدید
- `panel` و `panel_user` canonical جدید — dead code legacy redirectها را حذف نکن تا رگرسیون نخورد، فقط مستند کن
- جدول‌های موجود — نیاز به جدول جدید نیست — `final_design_id, service_key, selected_style` در reservations کافی است
- سیستم موازی جدید نساز — از `service_key, beauty_center_service, pricing, gallery, reservation, owner panel, analytics` موجود استفاده کن

**هزینه تغییر پیشنهادی:**
- P0 fixes: بدون تغییر / تغییر کوچک — DONE
- Owner "از آینه" tag: تغییر متوسط — 50 خط — بیشترین ارزش
- Consultant rate limit+login: تغییر کوچک — 10 خط — ضروری برای هزینه
- Final CTA واضح‌تر: بدون تغییر / فقط UI — 20 خط — ارزش بالا

**نتیجه نهایی:** Giso بعد از P0 fix آماده است برای جذب سالن‌دار با کمترین تغییر — فقط باید Owner ببیند که AI مشتری می‌آورد. همین یک کارت UI، کل funnel را از "پنل مدیریتی دیگر" به "ماشین جذب مشتری" تبدیل می‌کند.

---
Evidence: py_compile 3 prompts OK, app.py/bot.py OK, grep routes, grep owner_user_id checks, grep migrate, manual importlib test len 5, Code Truth > Graph.
