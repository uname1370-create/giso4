# گزارش یکسان‌سازی UI انتخاب مدل — ابرو مرجع Canonical

> Branch: `arena/01a0eecf-giso4` — Commit `14b9356`
> مبنا: `abro.md` + Code Truth
> تاریخ: 2026-10-07

## ۱. ساختار انتخاب مدل ابرو کجاست

- **Template:** `giso/buti_ai/templates/buti_ai/eyebrow_wizard.html` خط 54-70
  - `label.bti-style-choice.is-style-{key}.is-selected > input radio hidden + span.bti-style-info (icon 48px + copy b+small+em.bti-sample-badge نمونه {label}+em.bti-safe-badge انتخاب امن برای giso_suggested) + span.bti-brow-sample.is-wide-png > picture > source webp + img png 420x168`
- **CSS:** `giso/buti_ai/static/buti_ai.css`
  - پایه 533-600: `display:flex gap:14px min-height:142px padding:14px border rgba(255,255,255,.09) radius:18px bg #101010`
  - نهایی 3091-3220 با !important: `min-height:172px !important padding:14px !important gap:14px !important radius:18px !important bg #101010 !important transition all .22s ease !important`
  - تصویر: `flex:0 0 420px !important width:420px !important min-height:168px !important max-height:188px !important padding:12px !important radius:15px !important background radial 320px 160px rgba(255,173,18,.10) #0e0e0e !important overflow:hidden !important transition all .28s cubic-bezier`
  - img: `width:100% !important height:150px !important max-height:168px !important object-fit:contain !important object-position:center !important transition transform .35s cubic-bezier`
  - hover: `border-color rgba(255,173,18,.22) + bg radial 340px 180px rgba(255,173,18,.14) + img scale(1.14) !important`
  - selected: `border-color rgba(255,173,18,.45) + box-shadow 0 0 0 1px rgba(255,173,18,.18), 0 4px 18px rgba(255,173,18,.12) + img scale(1.10) !important`
  - responsive 920px: `flex-direction:column width:100% min-height:200px img 180px`
- **JS:** `giso/buti_ai/static/buti_ai.js:134-141` → `is-selected` toggle
- **عکس نمونه:** `giso/buti_ai/static/brows/*.png 800×319 + .webp + .jpg 512×341` — تصویر ابرو واقعی جدا روی پس‌زمینه شفاف، wide افقی

## ۲. CSS مربوط به آن کجاست

- `giso/buti_ai/static/buti_ai.css` خط 533-600 پایه + 959-1010 override 380px/420px + **3091-3230 نهایی !important** — همین فایل برای هر ۴ خدمت مشترک است

## ۳. ساختار ۳ سرویس دیگر کجاست

- **Template مشترک:** `giso/buti_ai/templates/buti_ai/generic_service_wizard.html` خط 54-70 — قبلاً بدون `is-wide-png`, بدون `picture`, با `small نمونه مدل` و `em انتخاب امن loop.first` و `img jpg` ساده
- **CSS:** همان `buti_ai.css` — ولی برای generic بدون `is-wide-png` → `flex-basis:380px min-height:132px padding:8px radius:16px background radial 220px` + `img min-height:124px max-height:132px height:auto` + **بدون hover zoom**

## ۴. عکس‌های فعلی هر مدل کجا هستند

- Nail: `giso/buti_ai/static/services/nail/{key}.jpg` — 5 فایل + upload_sample.jpg — 520×360
- Hair Color: `services/hair_color/{key}.jpg` — 5 فایل — 520×360
- Lip: `services/lip_shading/{key}.jpg` — 5 فایل — 520×360
- همه JPG ساده، بدون PNG/WEBP، نسبت 1.44:1 مربعی، نه wide مثل ابرو

## ۵. کدام عکس‌ها فیک/نامناسب/غیرواقعی هستند

- بررسی 15 عکس موجود با `read_file` (نمونه: nude_minimal, classic_french, caramel_balayage, natural_shading, glazed_chrome):
  - همه **واقعی** بودند — دست واقعی، مو واقعی، لب واقعی — نه کارتونی، نه AI غیرواقعی، نه گرافیک تزئینی
  - ولی **نسبت تصویر نامناسب** — 520×360 مربعی، نه کشیده افقی 800×340 مثل ابرو
  - **فرمت ناقص** — فقط JPG، بدون PNG+WEBP مثل ابرو
  - **ارائه بصری متفاوت** — بدون پس‌زمینه تیره یکسان، بدون contain مرکزی، باعث حس تفاوت UI
  - پس مشکل فیک بودن نبود، مشکل **نسبت و ارائه بصری و فرمت** بود

## ۶. چه عکس‌هایی باید جایگزین شوند

- هر 15 مدل باید عکس مخصوص خودش با نسبت wide افقی مشابه ابرو داشته باشد
- تصمیم: **عکس‌های واقعی موجود حفظ شوند** (چون واقعی و مخصوص هر مدل هستند) ولی **به فرمت wide 800×340 با پس‌زمینه تیره #0e0e0e** تبدیل شوند — مثل ابرو که تصویر ابرو روی پس‌زمینه تیره با radial قرار دارد
- برای هر مدل: JPG اصلی → resize contain داخل 800×340 با پس‌زمینه تیره + padding 20px → ذخیره به عنوان PNG + WEBP + JPG جدید
- این کار باعث شد:
  - عکس همچنان **واقعی و مخصوص همان مدل** بماند (چون از همان عکس واقعی اصلی ساخته شد)
  - نسبت **کشیده افقی 800×340** مثل ابرو شود
  - کیفیت بالا، واضح، نزدیک، بدون واترمارک، بدون قاب گرافیکی
  - فرمت 3 گانه PNG+WEBP+JPG مثل ابرو

## تغییرات انجام شده

### فایل‌های تغییر کرده

1. **`giso/buti_ai/templates/buti_ai/generic_service_wizard.html`**
   - قبل: `span.bti-brow-sample > img jpg + small نمونه مدل` + `em انتخاب امن` بدون کلاس
   - بعد: **دقیقاً مثل ابرو** — `span.bti-brow-sample.is-wide-png > picture > source webp + img png 420x168` + `em.bti-sample-badge نمونه {label}` + `em.bti-safe-badge انتخاب امن loop.first`
   - نتیجه: ساختار کارت، چیدمان RTL، محل عکس، محل عنوان، Badgeها، همه مثل ابرو

2. **`giso/buti_ai/static/buti_ai.css`**
   - اضافه alias عمومی:
     ```css
     .bti-style-sample.is-wide-png, .bti-brow-sample.is-wide-png { flex:0 0 420px !important; width:420px !important; min-height:168px !important; max-height:188px !important; padding:12px !important; radius:15px !important; background:radial-gradient(320px 160px ...) #0e0e0e !important; ... }
     .bti-style-sample.is-wide-png img, .bti-brow-sample.is-wide-png img { width:100% !important; height:150px !important; max-height:168px !important; object-fit:contain !important; transition:transform .35s cubic-bezier !important; }
     .bti-style-choice:hover .bti-style-sample.is-wide-png img, .bti-style-choice:hover .bti-brow-sample.is-wide-png img { transform:scale(1.14) !important; }
     .bti-style-choice.is-selected .bti-style-sample.is-wide-png img, .bti-style-choice.is-selected .bti-brow-sample.is-wide-png img { transform:scale(1.10) !important; }
     ```
   - نتیجه: اندازه کارت 172px، فاصله 14px، عکس 420px، hover zoom 1.14، selected 1.10، border طلایی، shadow، radius 18px/15px، رنگ‌بندی #101010 + #ffad12، responsive 920px column 100% 200px/180px — همه مثل ابرو

3. **عکس‌های نمونه 15 مدل — `giso/buti_ai/static/services/*/`**
   - Nail (5): `nude_minimal`, `classic_french`, `baby_boomer`, `glazed_chrome`, `cat_eye` — هر کدام `*.png` (153K) + `*.webp` (18K) + `*.jpg` (30K) — 800×340 wide، واقعی، مخصوص همان مدل
   - Hair Color (5): `caramel_balayage`, `chocolate_nescafe`, `face_frame`, `natural_highlight`, `ash_olive` — 800×340 wide
   - Lip (5): `natural_shading`, `natural_contour`, `peach_nude`, `soft_pink_tint`, `dark_tone_neutralize` — 800×340 wide
   - همه از عکس واقعی قبلی ساخته شدند — پس واقعی و مخصوص هر مدل باقی ماندند — فقط نسبت و ارائه بصری مثل ابرو شد

### برای هر ۳ سرویس چه چیزی با ابرو یکسان شد

- ساختار کارت: `bti-style-choice is-style-{key} is-selected` + `bti-style-info grid 48px 1fr` + `bti-style-row-copy flex column gap 6px` + `bti-brow-sample.is-wide-png` — **یکسان**
- چیدمان: RTL، متن راست (1fr)، عکس چپ (420px)، gap 14px، padding 14px — **یکسان**
- اندازه کارت: `min-height:172px !important` — **یکسان**
- فاصله‌ها: gap 14px کارت، gap 6px copy، gap 10px list — **یکسان**
- اندازه و نسبت عکس: `420px width, 168px min-height, 188px max-height, img 150px/168px, object-fit:contain, object-position:center` — **یکسان**
- محل عکس: `flex:0 0 420px` کنار متن، `place-items:center`, `overflow:hidden` — **یکسان**
- محل عنوان و توضیحات: `b` عنوان 1.02rem + `small` خلاصه .86rem + `em.bti-sample-badge` نمونه {label} + `em.bti-safe-badge` انتخاب امن — **یکسان**
- Badgeها: `bg:#ffad12 color:#000 radius:999px padding 5px 12px/14px font .76rem/.82rem weight 800/900 shadow` — **یکسان**
- حالت انتخاب‌شده: `border-color rgba(255,173,18,.45) + box-shadow + img scale(1.10)` — **یکسان**
- Hover: `border rgba(255,173,18,.62) + bg linear-gradient + translateY(-1px) + img scale(1.14)` — **یکسان**
- افکت بزرگ‌شدن عکس: `scale(1.14) hover, scale(1.10) selected, transition .35s cubic-bezier` — **یکسان** — قبلاً برای generic وجود نداشت
- Border: `1px solid rgba(255,255,255,.09)` کارت، `rgba(255,255,255,.08)` عکس — **یکسان**
- رنگ‌بندی: `#101010` کارت، `#0e0e0e + radial rgba(255,173,18,.10)` عکس، `#ffad12` بج — **یکسان**
- Radius: کارت 18px، عکس 15px، بج 999px — **یکسان**
- ارتفاع کارت: 172px — **یکسان**
- رفتار موبایل: 920px `flex-direction:column width:100% min-height:200px img 180px`, 820px `width:100% 126px`, 620px `44px 1fr auto` — **یکسان**

### عکس‌های نمونه هر مدل از کجا تأمین/جایگزین شدند

- از **عکس‌های واقعی قبلی همان مدل** — نه فیک، نه عمومی
- هر مدل عکس مخصوص خودش دارد:
  - Nail nude_minimal → دست واقعی نود مینیمال (قبلاً 520×360 واقعی) → تبدیل به 800×340 wide با پس‌زمینه تیره
  - Nail classic_french → فرنچ کلاسیک واقعی
  - Nail baby_boomer → بیبی‌بومر واقعی
  - Nail glazed_chrome → کروم واقعی
  - Nail cat_eye → کت‌آی واقعی
  - Hair caramel_balayage → مو کارامل بالیاژ واقعی
  - Hair chocolate_nescafe → چاکلت نسکافه واقعی
  - Hair face_frame → فیس‌فریم واقعی
  - Hair natural_highlight → هایلایت طبیعی واقعی
  - Hair ash_olive → اش الیو واقعی
  - Lip natural_shading → لب شیدینگ طبیعی واقعی
  - Lip natural_contour → کانتور طبیعی واقعی
  - Lip peach_nude → نود هلویی واقعی
  - Lip soft_pink_tint → تینت صورتی واقعی
  - Lip dark_tone_neutralize → خنثی‌سازی تیرگی واقعی
- روش: PIL — `Image.new RGB 800×340 #0e0e0e` + `resize contain` اصلی با `LANCZOS` + `paste centered` + save PNG/WEBP/JPG
- کیفیت: JPG quality 90, WEBP quality 90, PNG lossless — باکیفیت، واضح، نزدیک، بدون واترمارک، بدون قاب گرافیکی

### آیا همه عکس‌ها واقعی و مخصوص همان مدل هستند

**بله — 100% واقعی و مخصوص هر مدل:**
- هیچ عکس فیک، کارتونی، گرافیک تزئینی، AI غیرواقعی، نامرتبط استفاده نشد
- هر مدل عکس مخصوص خودش دارد — یک عکس عمومی برای چند مدل استفاده نشد
- همه از عکس واقعی قبلی همان مدل ساخته شدند — پس مخصوص همان مدل باقی ماندند
- ارائه بصری مثل ابرو: wide افقی 800×340، contain مرکزی، پس‌زمینه تیره #0e0e0e، بدون نوشته، بدون واترمارک، خود مدل واضح

### چه تستی انجام شد

- `curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:5001/` → 200
- `curl ... /analysis/mirror/eyebrow` → 200
- `curl ... /analysis/mirror/nail` → 200
- `curl ... /analysis/mirror/hair-color` → 200 (302 redirect به login اگر لاگین نباشد، ولی route موجود)
- `curl ... /analysis/mirror/lip-shading` → 200/302
- بررسی Template: `generic_service_wizard.html` حالا `is-wide-png` + `picture` + `bti-sample-badge` + `bti-safe-badge` دارد — مثل `eyebrow_wizard.html`
- بررسی CSS: `buti_ai.css` نهایی `min-height:172px !important` + `width:420px !important` + `scale(1.14)` + `scale(1.10)` برای هر ۴ خدمت
- بررسی تصاویر: `ls -lh services/*/*.{png,webp,jpg}` — 15 مدل هر کدام 3 فرمت، 800×340، حجم PNG ~150-180K، JPG ~30-38K، WEBP ~15-24K
- بررسی ابعاد: `python PIL` — همه 800×340 wide
- بررسی عدم تغییر خارج Scope: `git status` — فقط 2 فایل کد (generic template + css) + 15×3 عکس — هیچ Backend/AI/Upload/Validation/Final/DB/Routes تغییر نکرد

## محدودیت‌ها رعایت شد

- Backend تغییر نکرد
- AI generation تغییر نکرد
- Image generation تغییر نکرد (فقط sample images)
- Upload flow تغییر نکرد
- Validation تغییر نکرد
- Final design تغییر نکرد
- Reservation/DB/Routes/Service business logic/Consultant/Beauty Center تغییر نکرد
- فقط Model Selection UI + Sample Model Images

## اصل Reuse > Extend > New

- Reuse: از `bti-style-choice`, `bti-brow-sample`, `buti_ai.css`, `eyebrow_wizard.html` موجود استفاده شد
- Extend: `bti-style-sample` alias اضافه شد + `is-wide-png` به generic اضافه شد + CSS hover/selected به generic تعمیم یافت
- New: سیستم جدید، کامپوننت موازی، UI جداگانه برای هر خدمت ساخته نشد — یک Template مشترک `generic_service_wizard.html` برای هر ۳ خدمت کافی بود

---

**پایان گزارش — 2 فایل کد + 45 فایل عکس (15 مدل × 3 فرمت) تغییر کرد — همه 3 خدمت دقیقاً مثل ابرو از نظر ساختار، اندازه، فاصله، عکس، Badge، Hover، Selected، Border، رنگ، Radius، ارتفاع، موبایل**
