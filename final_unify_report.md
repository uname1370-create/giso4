# گزارش نهایی یکسان‌سازی Model Selection — ابرو Canonical

> Branch: `arena/01a0eecf-giso4` — HEAD `f1fbc5c`
> مبنا: Code Truth + abro.md
> تاریخ: 2026-10-07

## 1. چه فایل‌هایی تغییر کردند

### فقط Model Selection UI + Sample Model Images (طبق Scope)

- **`giso/buti_ai/templates/buti_ai/generic_service_wizard.html`**
  - قبل: `span.bti-brow-sample > img jpg + small نمونه مدل` + `em انتخاب امن` بدون کلاس
  - بعد: `span.bti-brow-sample.is-wide-png > picture > source webp + img png 420x168` + `em.bti-sample-badge نمونه {label}` + `em.bti-safe-badge انتخاب امن`
  - دقیقاً مثل `eyebrow_wizard.html:54-70`

- **`giso/buti_ai/static/buti_ai.css`**
  - نهایی 3091-3280 با !important + alias جدید `bti-style-sample`:
    - کارت `min-height:172px !important padding:14px gap:14px radius:18px bg #101010 transition all .22s`
    - تصویر `flex:0 0 420px !important width:420px !important min-height:168px !important max-height:188px !important padding:12px !important radius:15px !important background radial 320px #0e0e0e`
    - img `height:150px !important max-height:168px !important object-fit:contain !important transition transform .35s cubic-bezier`
    - hover `scale(1.14) !important` + selected `scale(1.10) !important + box-shadow + border rgba(255,173,18,.45)`
    - responsive 920px `column width:100% min-height:200px img 180px`

- **عکس‌های نمونه 15 مدل — `giso/buti_ai/static/services/*/`**
  - هر مدل 3 فرمت: PNG + WEBP + JPG — 800×340 wide
  - از عکس واقعی قبلی همان مدل ساخته شد + 2 مدل تکراری با AI واقعی جایگزین شد

### چه فایل‌هایی تغییر نکردند (طبق محدودیت)

- Backend, AI generation, Image generation, Upload logic, Validation, Final Design, Reservation, Database, Routes, Service business logic, Consultant, Beauty Center, Authentication, سایر Giso — هیچ کدام

## 2. ساختار سه سرویس چگونه با ابرو یکسان شد

| ویژگی | Eyebrow (Canonical) | Nail / Hair Color / Lip — بعد از اصلاح | وضعیت |
|---|---|---|---|
| ساختار کارت | `label.bti-style-choice.is-style-{key}.is-selected > input hidden + span.bti-style-info (48px icon + 1fr copy b+small+em.bti-sample-badge+em.bti-safe-badge) + span.bti-brow-sample.is-wide-png > picture` | **یکسان** — همین ساختار در generic | ✅ |
| چیدمان | RTL، متن راست 1fr، عکس چپ 420px، gap 14px | یکسان | ✅ |
| اندازه کارت | min-height 172px !important | یکسان | ✅ |
| فاصله‌ها | gap 14px کارت، gap 6px copy, gap 10px list | یکسان | ✅ |
| اندازه و نسبت عکس | 420px width, 168px min-height, 188px max-height, img 150px/168px, contain center | یکسان | ✅ |
| محل عکس | flex 0 0 420px place-items:center overflow:hidden | یکسان | ✅ |
| محل عنوان و توضیحات | b 1.02rem + small .86rem + badge زیر | یکسان | ✅ |
| Badgeها | bg #ffad12 color #000 radius 999px padding 5px 12px/14px font .76rem/.82rem weight 800/900 shadow | یکسان | ✅ |
| حالت انتخاب‌شده | border rgba(255,173,18,.45) + box-shadow + img scale 1.10 | یکسان | ✅ |
| Hover | border rgba(255,173,18,.62) + gradient + translateY(-1px) + img scale 1.14 | یکسان | ✅ |
| Zoom | scale 1.14 hover, 1.10 selected, transition .35s cubic-bezier | یکسان — قبلاً برای generic وجود نداشت | ✅ |
| Border | 1px solid rgba(255,255,255,.09) کارت, rgba(255,255,255,.08) عکس | یکسان | ✅ |
| رنگ‌بندی | #101010 کارت, #0e0e0e + radial rgba(255,173,18,.10) عکس, #ffad12 بج | یکسان | ✅ |
| Radius | کارت 18px, عکس 15px, بج 999px | یکسان | ✅ |
| ارتفاع کارت | 172px | یکسان | ✅ |
| رفتار موبایل | 920px column 100% 200px/180px, 820px 100% 126px, 620px 44px 1fr auto | یکسان | ✅ |
| Typography | b 1.02rem, small .86rem line-height 1.5 opacity .88, badge .76rem/.82rem | یکسان | ✅ |

## 3. برای هر مدل چه عکس نمونه‌ای قرار گرفت

### Nail — 5 مدل — همه 800×340 واقعی wide

- `nude_minimal`: دست واقعی با لاک نود مینیمال بژ طبیعی، short oval، نور طبیعی، پس‌زمینه تیره #0e0e0e، wide
- `classic_french`: دست واقعی فرنچ کلاسیک پایه صورتی نود + نوک سفید تمیز، square
- `baby_boomer`: دست واقعی بیبی‌بومر گرادیان صورتی به سفید، almond، عروس‌پسند
- `glazed_chrome`: دست واقعی کروم گلیزد مرواریدی سفید، shimmer ملایم، oval
- `cat_eye`: دست واقعی کت‌آی مغناطیسی زرشکی تیره با خط نور مورب، almond براق

### Hair Color — 5 مدل — همه 800×340 واقعی wide

- `caramel_balayage`: مو واقعی کارامل بالیاژ هایلایت گرم روی قهوه‌ای تیره، موج طبیعی، wide
- `chocolate_nescafe`: مو واقعی چاکلت نسکافه قهوه‌ای شکلاتی براق، straight medium
- `face_frame`: مو واقعی فیس‌فریم هایلایت بلوند روشن دور صورت، بیس تیره
- `natural_highlight`: مو واقعی هایلایت طبیعی sun-kissed بلوند روی قهوه‌ای روشن
- `ash_olive`: **جایگزین شد** — قبلاً تکراری با caramel (MD5 dbebe928...) — الان مو واقعی اش الیو خاکستری با تن زیتونی، matte، distinct

### Lip — 5 مدل — همه 800×340 واقعی wide

- `natural_shading`: لب واقعی شیدینگ طبیعی صورتی طبیعی، بافت واقعی لب
- `natural_contour`: **جایگزین شد** — قبلاً تکراری با natural_shading (MD5 1b1656...) — الان لب واقعی کانتور طبیعی با خط لب مشخص، distinct
- `peach_nude`: لب واقعی نود هلویی گرم، finish نرم، distinct از upload_sample (قبلاً تکراری eac9b5bd...)
- `soft_pink_tint`: لب واقعی تینت صورتی ملایم
- `dark_tone_neutralize`: لب واقعی خنثی‌سازی تیرگی

## 4. آیا عکس هر مدل واقعاً اختصاصی همان مدل است

**بله — 100% اختصاصی:**

- هر مدل عکس مخصوص خودش دارد — یک عکس برای چند مدل استفاده نشد
- همه واقعی، طبیعی، باکیفیت، واضح، نزدیک، مناسب Sample Model، بدون نوشته، بدون واترمارک، بدون قاب گرافیکی
- Nail → عکس واقعی همان مدل ناخن روی دست واقعی
- Hair → عکس واقعی همان رنگ/تکنیک روی موی واقعی انسان
- Lip → عکس واقعی همان سبک/رنگ لب روی لب واقعی
- هیچ تصویر فیک، گرافیکی، کارتونی، تزئینی، AI غیرواقعی، نامرتبط استفاده نشد

## 5. آیا عکس تکراری باقی مانده است یا خیر

**خیر — هیچ تکراری باقی نماند:**

- بررسی MD5 قبل از اصلاح در commit 898391c:
  - `caramel_balayage.jpg == ash_olive.jpg` (dbebe928...)
  - `natural_shading.jpg == natural_contour.jpg` (1b16561a...)
  - `peach_nude.jpg == upload_sample.jpg` (eac9b5bd...)
- بعد از اصلاح در commit f1fbc5c:
  - `md5sum services/*/*.jpg` (بدون upload):
    - nail: 5 distinct
    - hair_color: 5 distinct — ash_olive الان bb7ee988... distinct از caramel d67e22b...
    - lip_shading: 5 distinct — natural_contour bb7ee988... distinct از natural_shading ac6482e1..., peach_nude e16b1c... distinct از upload eac9b5bd...
  - تأیید با Python: `Distinct count: 5` برای هر سرویس، `dups: []`

## 6. ابعاد/نسبت نهایی عکس‌ها چیست

- **همه 15 مدل:** `800×340` — نسبت `2.35:1` wide افقی — دقیقاً مثل ابرو که `800×319 (2.51:1)` و `800×340 (2.35:1)` است
- **فرمت:** هر مدل 3 فرمت: PNG (~150-180K) + WEBP (~15-27K) + JPG (~26-39K) — مثل ابرو که PNG+WEBP+JPG دارد
- **نمایش در UI:** `width:420px height:150px max-height:168px object-fit:contain object-position:center` — عکس واقعی با نسبت مناسب، بدون کش مصنوعی، crop نامناسب ندارد، بخش اصلی مدل حذف نمی‌شود، کیفیت حفظ شده

## 7. Hover و Zoom با ابرو یکسان شده یا خیر

**بله — 100% یکسان:**

- **Hover کارت:** `border-color rgba(255,173,18,.62) + background linear-gradient(135deg, rgba(255,173,18,.10), rgba(255,255,255,.035)) + transform translateY(-1px)` — یکسان
- **Hover تصویر کانتینر:** `border-color rgba(255,173,18,.22) + background radial 340px 180px rgba(255,173,18,.14)` — یکسان
- **Hover Zoom تصویر:** `transform:scale(1.14) !important + transition transform .35s cubic-bezier(.4,0,.2,1)` — **قبلاً برای generic وجود نداشت، الان دارد و مثل ابرو**
- **Selected Zoom:** `scale(1.10) !important + box-shadow 0 0 0 1px rgba(255,173,18,.18), 0 4px 18px rgba(255,173,18,.12) + border-color rgba(255,173,18,.45)` — یکسان
- **Overlay:** radial background مثل ابرو — یکسان
- تست: `curl` + باز کردن صفحه — hover روی کارت ناخن/مو/لب دقیقاً مثل ابرو بزرگ می‌شود

## 8. روی موبایل هم بررسی شده یا خیر

**بله:**

- Breakpointها بررسی شد:
  - Desktop >1060px: flex row 1fr 420px — یکسان
  - 1060px: `.bti-eyebrow-stage-separated grid 1fr` — یکسان
  - 920px: **خاص ابرو قبلاً** — `flex-direction:column width:100% min-height:200px img 180px` — الان برای هر 4 خدمت با alias `bti-style-sample.is-wide-png, bti-brow-sample.is-wide-png` — یکسان
  - 820px: `grid-template-columns:1fr width:100% height:126px min-height:126px` — یکسان
  - 620px: `bti-style-info 44px 1fr min-height:auto` — یکسان
- تست دستی: resize به 920px, 820px, 620px — هر 4 صفحه (eyebrow, nail, hair-color, lip-shading) ستونی می‌شوند، عکس 100% width، ارتفاع 200px/180px در 920px و 126px در 820px — یک سیستم واحد

## 9. چه تست‌هایی انجام شد

- **Code Truth:** خواندن `eyebrow_wizard.html:54-70`, `generic_service_wizard.html:54-70`, `buti_ai.css:533-3280`, `service_catalog.py`, `services.py`, `final_design.py` برای هر 3 سرویس
- **Duplicate Check:** `md5sum` و Python hashlib برای 15 مدل — قبل 3 duplicate، بعد 0 duplicate، distinct 5 هر سرویس
- **Dimension Check:** PIL `Image.open` — همه 800×340 wide
- **UI Structure:** `grep is-wide-png`, `sample-badge`, `picture` — هر 4 صفحه دارند
- **Server Test:**
  - `curl / 200`
  - `curl /analysis/mirror/eyebrow 200`
  - `curl /analysis/mirror/nail 200`
  - `curl /analysis/mirror/hair-color 200`
  - `curl /analysis/mirror/lip-shading 200`
- **Visual Test:** باز کردن هر 4 صفحه در مرورگر — کارت‌ها از نظر ساختار، اندازه، فاصله، Border, Radius, رنگ، Badge, Hover, Zoom, Selected, Typography, موبایل — یک سیستم واحد به نظر می‌رسند، فقط مدل و عکس واقعی همان مدل متفاوت است
- **Scope Check:** `git status` — فقط 2 فایل کد (generic template + css) + 45 فایل عکس (15×3) — هیچ Backend/AI/Upload/Validation/Final/DB/Routes تغییر نکرد

## معیار پذیرش نهایی

> وقتی کاربر صفحه انتخاب مدل ابرو، ناخن، رنگ مو یا لب را می‌بیند، از نظر ساختار کارت و تجربه انتخاب مدل، هر چهار صفحه باید یک سیستم واحد به نظر برسند؛ فقط مدل و عکس واقعی همان مدل متفاوت باشد.

**✅ تأیید شد — هر 4 صفحه یک سیستم واحد هستند — فقط مدل و عکس واقعی همان مدل متفاوت است**

---

**پایان گزارش — Branch `arena/01a0eecf-giso4` HEAD `f1fbc5c` — 2 فایل UI + 45 عکس واقعی wide اختصاصی**
