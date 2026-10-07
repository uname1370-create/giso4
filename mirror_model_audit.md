# Audit UI انتخاب مدل — Eyebrow به عنوان مرجع vs Nail / Lip / Hair Color

> تاریخ: 2026-10-07
> شاخه: `arena/01a0eecf-giso4` HEAD=`392cd5e` (با ais.md, abro.md)
> اصل: Code Truth — فقط کد زنده

## نتیجه اولیه (یکی از سه گزینه)

**گزینه B — ساختار مشترک است ولی چند تفاوت UI وجود دارد**

**دلیل:** کارت‌ها از نظر HTML و CSS پایه ۹۰٪ یکسان هستند (همه `bti-style-choice` + `bti-brow-sample` از `buti_ai.css` مشترک)، اما در اندازه تصویر نمونه، بج‌ها، فرمت عکس و یک breakpoint تفاوت ساختاری وجود دارد. Generic فعلی ۱۰۰٪ UI ابرو را منتقل نکرده — ۴۰px اختلاف عرض + بج متفاوت + picture vs img.

---

## ۱. UI انتخاب مدل ابرو — مرجع

### مسیر واقعی
- Template: `giso/buti_ai/templates/buti_ai/eyebrow_wizard.html` (176 خط) — نسخه CSS `v=19`
- CSS: `giso/buti_ai/static/buti_ai.css` — کلاس‌های اصلی خط 533-650 (پایه) + 959-1010 (override 380/420) + 3091-3220 (override نهایی !important)
- JS: `giso/buti_ai/static/buti_ai.js` خط 134-141 → `querySelectorAll('.bti-style-choice')` → رویداد `change` → `is-selected` کلاس
- عکس نمونه: `giso/buti_ai/static/brows/{key}.png + .webp` via `url_for('buti_ai.static', filename='brows/' ~ key ~ '.webp')` — تگ `picture`

### کارت مدل — استخراج دقیق (final override با !important)

| ویژگی | مقدار نهایی (بعد از override) | منبع |
|---|---|---|
| **کلاس** | `bti-style-choice is-style-{key} is-selected` | eyebrow_wizard.html:48 |
| **display** | `flex !important` | buti_ai.css:3092 |
| **align-items** | `stretch !important` | 3093 |
| **gap** | `14px !important` | 3094 |
| **padding** | `14px !important` | 3095 |
| **min-height** | `172px !important` | 3096 |
| **height** | auto (بدون height ثابت) | inherited |
| **margin** | 0 (از `bti-style-list gap:10px` می‌آید) | 347 |
| **border** | `1px solid rgba(255,255,255,.09) !important` | 3098 |
| **border-radius** | `18px !important` | 3099 |
| **background** | `#101010 !important` | 3100 |
| **transition** | `all .22s ease !important` | 3101 |
| **hover transform** | `translateY(-1px)` | 551 + 3091 override |
| **hover border** | `rgba(255,173,18,.62)` | 549 |
| **hover background** | `linear-gradient(135deg, rgba(255,173,18,.10), rgba(255,255,255,.035))` | 550 |
| **selected state** | همان hover + `is-selected` کلاس — border طلایی + background گرادیان | 548-549 + JS 138 |
| **selected border** | `rgba(255,173,18,.62)` (پایه) — برای عکس کانتینر `rgba(255,173,18,.45) !important` + box-shadow | 3193 |

### عکس نمونه — ابرو

| ویژگی | مقدار نهایی | منبع |
|---|---|---|
| **کلاس** | `bti-brow-sample is-wide-png` | eyebrow_wizard.html:58 |
| **width** | `420px !important` | buti_ai.css:3156 |
| **flex** | `0 0 420px !important` | 3155 |
| **min-height** | `168px !important` | 3157 |
| **max-height** | `188px !important` | 3158 |
| **height** | auto (img داخل 150px) | - |
| **aspect-ratio** | ندارد (از img می‌آید) | - |
| **object-fit (img)** | `contain !important` | 3177 |
| **object-position (img)** | `center !important` | 3178 |
| **border-radius (container)** | `15px !important` | 3163 |
| **border-radius (img)** | `0 !important` (transparent) | 3180 |
| **overflow** | `hidden !important` | 3164 |
| **padding (container)** | `12px !important` | 3162 |
| **background (container)** | `radial-gradient(320px 160px at 50% 50%, rgba(255,173,18,.10), transparent 70%), #0e0e0e !important` | 3159 |
| **filter (img)** | `none !important` | 3179 |
| **overlay** | ندارد — فقط background radial | - |
| **img width** | `100% !important` | 3175 |
| **img height** | `150px !important`, `max-height:168px !important` | 3176-3177 |

### افکت‌ها — ابرو

- **Hover کارت:** border طلایی + background گرادیان طلایی کم + translateY(-1px) — `transition: all .22s ease`
- **Hover تصویر کانتینر:** `border-color: rgba(255,173,18,.22) !important` + background هاله بزرگتر `rgba(255,173,18,.14)`
- **Hover Zoom تصویر:** **وجود دارد** — `transform: scale(1.14) !important` — `transition: transform .35s cubic-bezier(.4,0,.2,1) !important` — buti_ai.css:3191
- **Selected Transform تصویر:** `scale(1.10) !important` — 3198
- **Selected Shadow:** `box-shadow: 0 0 0 1px rgba(255,173,18,.18), 0 4px 18px rgba(255,173,18,.12) !important` + `0 0 30px rgba(255,173,18,.38)` در حالت active b
- **Badge:** `em.bti-sample-badge` → "نمونه {label}" — `background:#ffad12`, `color:#000`, `padding:5px 12px`, `radius:999px`, `font-size:.76rem`, `font-weight:800`, `box-shadow:0 2px 8px rgba(255,173,18,.22)` — 3139-3152
- **Badge دوم:** `em.bti-safe-badge` → "انتخاب امن" فقط برای `giso_suggested` — `padding:5px 14px`, `font-size:.82rem`, `font-weight:900`
- **متن «نمونه مدل»:** در ابرو وجود ندارد — به جایش «نمونه {label}» دارد
- **انیمیشن:** transform + border-color + background + scale — همه با cubic-bezier

### JS مرتبط
- `buti_ai.js:134-141` → هر `.bti-style-choice` → `input[type=radio]` change → حذف `is-selected` از همه، اضافه به انتخاب شده — همین برای generic هم کار می‌کند

### نحوه دریافت و نمایش عکس نمونه
- Backend: `eyebrow/options.py` → `EYEBROW_STYLES` ۵ کلید
- Template: `url_for('buti_ai.static', filename='brows/' ~ key ~ '.webp')` + fallback png — `width=420 height=168 loading=lazy`

---

## ۲. هر سه خدمت جداگانه — مقایسه با ابرو

### مسیر مشترک ۳ خدمت
- Template: `giso/buti_ai/templates/buti_ai/generic_service_wizard.html` — CSS `v=24` (vs v19 ابرو — فقط cache bust)
- CSS: همان `buti_ai.css` — کلاس‌ها `bti-style-choice` + `bti-brow-sample` (بدون is-wide-png)
- JS: همان `buti_ai.js` v24 (همان کد)
- عکس: `giso/buti_ai/static/services/{service}/{key}.jpg` via `service_meta.sample_dir ~ '/' ~ key ~ '.jpg'`

### Nail — `nail`

- **Template خط 46-58:** `label.bti-style-choice is-style-{key}` + `span.bti-brow-sample` (بدون is-wide-png) + `img src="{sample_dir}/{key}.jpg"` + `small>نمونه مدل`
- **CSS کارت:** همان `min-height:172px !important` (چون override 3091 برای همه) — پس کارت یکسان
- **CSS تصویر:** از 968 → `flex-basis:380px; min-height:132px; background: radial 220px 120px rgba(255,173,18,.08), #0e0e0e; border: rgba(255,255,255,.06); radius:16px; padding:8px` — **نه 420px**
- **img:** `min-height:124px; width:100%; height:auto; max-height:132px; object-fit:contain; object-position:center` — **نه 150px/168px**
- **Hover Zoom:** **وجود ندارد برای generic** — چون selector `is-wide-png img` فقط برای ابرو است — generic هیچ `transform:scale` ندارد در hover (فقط border)
- **Badge:** `em` بدون کلاس → "انتخاب امن" فقط برای `loop.first` — نه `bti-sample-badge`
- **متن نمونه مدل:** `small` داخل `bti-brow-sample` → "نمونه مدل" — `position:absolute; bottom:10px; right:50%; transform:translateX(50%); background:rgba(255,173,18,.92)` — در ابرو این small وجود ندارد

### Lip — `lip_shading`

- دقیقاً مثل Nail — همین `generic_service_wizard.html` — همین CSS 380px — همین JPG — همین small
- مدل‌ها: ۵ تا (natural_shading, natural_contour, peach_nude, soft_pink_tint, dark_tone_neutralize)

### Hair Color — `hair_color`

- دقیقاً مثل Nail و Lip — همین template، همین CSS 380px، همین JPG
- مدل‌ها: ۵ تا (caramel_balayage, chocolate_nescafe, face_frame, natural_highlight, ash_olive)

---

## ۳. جدول مقایسه دقیق و عددی

| مورد | Eyebrow (مرجع) | Nail | Lip | Hair Color | تفاوت |
|---|---|---|---|---|---|
| **ساختار HTML** | `label.bti-style-choice.is-style-{key}.is-selected > input[radio] + span.bti-style-info + span.bti-brow-sample.is-wide-png > picture > source(webp) + img(png)` | `label.bti-style-choice.is-style-{key} > input + span.bti-style-info + span.bti-brow-sample > img(jpg) + small` | مثل Nail | مثل Nail | **ساختاری:** picture vs img, is-wide-png vs ساده, small داخل vs em بیرون |
| **کلاس کارت** | `bti-style-choice is-style-{key} is-wide-png` | `bti-style-choice is-style-{key}` | مثل Nail | مثل Nail | کلاس is-wide-png فقط ابرو |
| **عرض کارت** | 100% - 32px (از `bti-shell width:min(1120px, calc(100% - 32px))`) — کارت خودش 100% داخل | همین | همین | همین | یکسان |
| **ارتفاع کارت** | `min-height:172px !important` (override نهایی) | همین 172px (چون override 3091 برای همه) | همین | همین | **یکسان** — از 3091 |
| **Padding کارت** | `14px !important` | همین 14px | همین | همین | یکسان |
| **Margin کارت** | 0 + gap 10px از parent `bti-style-list` | همین | همین | همین | یکسان |
| **Gap کارت داخلی** | `14px !important` (بین متن و عکس) | همین 14px (چون flex gap از 3091) | همین | همین | یکسان |
| **Border کارت** | `1px solid rgba(255,255,255,.09) !important` | همین | همین | همین | یکسان |
| **Border Radius کارت** | `18px !important` | همین | همین | همین | یکسان |
| **Background کارت** | `#101010 !important` | همین | همین | همین | یکسان |
| **Transition کارت** | `all .22s ease !important` | همین | همین | همین | یکسان |
| **Hover Transform کارت** | `translateY(-1px)` | همین | همین | همین | یکسان |
| **Hover Border کارت** | `rgba(255,173,18,.62)` | همین | همین | همین | یکسان |
| **Selected State کارت** | `is-selected` + `:has(input:checked)` → border طلایی + gradient | همین (JS یکسان) | همین | همین | یکسان |
| **تصویر — کلاس** | `bti-brow-sample is-wide-png` | `bti-brow-sample` | مثل Nail | مثل Nail | تفاوت کلاس |
| **عرض تصویر کانتینر** | `420px !important` + `flex:0 0 420px !important` | `380px` (flex-basis:380px) — از 973 | 380px | 380px | **ساختاری: 40px اختلاف** |
| **ارتفاع تصویر کانتینر** | `min-height:168px !important`, `max-height:188px !important` | `min-height:132px` (یا 124px base) | 132px | 132px | **ساختاری: 36px اختلاف** |
| **Aspect Ratio کانتینر** | ندارد | ندارد | ندارد | ندارد | یکسان |
| **Object Fit img** | `contain !important` | `contain` (بدون !important) | contain | contain | یکسان از نظر مقدار، ولی !important فقط ابرو |
| **Object Position img** | `center !important` | `center` | center | center | یکسان |
| **Border Radius عکس کانتینر** | `15px !important` | `16px` | 16px | 16px | **1px اختلاف** |
| **Border Radius img** | `0 !important` | ندارد (img خودش radius ندارد) | - | - | - |
| **Overflow** | `hidden !important` | `hidden` (از base) | hidden | hidden | یکسان |
| **Padding عکس کانتینر** | `12px !important` | `8px` | 8px | 8px | **4px اختلاف** |
| **Background عکس کانتینر** | `radial-gradient(320px 160px, rgba(255,173,18,.10)), #0e0e0e !important` | `radial-gradient(220px 120px, rgba(255,173,18,.08)), #0e0e0e` | همین | همین | اندازه radial فرق |
| **Overlay** | ندارد | ندارد | ندارد | ندارد | یکسان |
| **Filter img** | `none !important` | `none` | none | none | یکسان |
| **عرض img** | `100% !important` | `100%` | 100% | 100% | یکسان |
| **ارتفاع img** | `150px !important`, `max-height:168px !important` | `auto`, `max-height:132px`, `min-height:124px` | همین | همین | **ساختاری: 18-36px اختلاف** |
| **Hover Zoom** | **وجود دارد** `scale(1.14) !important` + transition `.35s cubic-bezier` | **وجود ندارد** — هیچ scale برای generic | ندارد | ندارد | **ساختاری مهم** |
| **Selected Transform** | `scale(1.10) !important` + box-shadow | ندارد | ندارد | ندارد | **ساختاری مهم** |
| **Badge** | `em.bti-sample-badge` → "نمونه {label}" + `em.bti-safe-badge` → "انتخاب امن" (فقط giso_suggested) | `em` بدون کلاس → "انتخاب امن" فقط loop.first + `small` داخل عکس → "نمونه مدل" | مثل Nail | مثل Nail | **ساختاری: بج متفاوت + small vs em** |
| **متن نمونه مدل** | em بیرون از عکس، زیر عنوان | small داخل عکس، absolute bottom 10px | مثل Nail | مثل Nail | **جای متفاوت** |
| **فاصله‌ها (gap)** | 14px بین متن و عکس, 6px بین عنوان و خلاصه | همین 14px (از override) | همین | همین | یکسان |
| **Mobile (920px)** | `flex-direction:column`, عکس `width:100%`, `min-height:200px`, img `height:180px` — فقط برای is-wide-png | در 820px → `flex-direction:column`, عکس `width:100%`, `min-height:130px` — breakpoint متفاوت | مثل Nail | مثل Nail | **ساختاری: breakpoint 920 vs 820 + ارتفاع 200 vs 130** |

---

## ۴. تفاوت محتوایی vs ساختاری

### تفاوت محتوایی (مشکل نیست)

- عکس متفاوت: ابرو عکس ابرو، ناخن عکس دست، مو عکس مو، لب عکس لب — طبیعی
- نام مدل متفاوت: طبیعی/میکروبلیدینگ vs نود/فرنچ vs کارامل بالیاژ — طبیعی
- توضیح متفاوت: summary متفاوت — طبیعی
- تعداد مدل‌ها: هر ۴ خدمت ۵ مدل — یکسان، پس محتوایی نیست

### تفاوت UI / ساختاری (باید گزارش شود)

1. **عرض تصویر کانتینر:** 420px (ابرو) vs 380px (۳ خدمت) → 40px اختلاف — ساختاری
2. **ارتفاع تصویر:** 168px vs 132px → 36px اختلاف — ساختاری
3. **ارتفاع img:** 150px vs auto/132px → 18px اختلاف — ساختاری
4. **Padding عکس:** 12px vs 8px → 4px اختلاف — ساختاری
5. **Border Radius کانتینر:** 15px vs 16px → 1px اختلاف — ساختاری جزئی
6. **Hover Zoom:** وجود دارد در ابرو (scale 1.14) vs ندارد در ۳ خدمت — **ساختاری مهم**
7. **Selected Zoom:** scale 1.10 + box-shadow در ابرو vs ندارد — **ساختاری مهم**
8. **Badge:** em.bti-sample-badge + bti-safe-badge (ابرو) vs em بدون کلاس + small داخل عکس (۳ خدمت) — ساختاری + جای متفاوت
9. **متن نمونه مدل:** em بیرون (ابرو) vs small داخل absolute (۳ خدمت) — ساختاری
10. **Breakpoint Responsive:** 920px برای ابرو (is-wide-png) vs 820px برای generic — ساختاری
11. **Mobile ارتفاع:** 200px/180px (ابرو) vs 130px/118px (generic) — ساختاری
12. **Background radial:** 320px 160px vs 220px 120px — cosmetic اما ساختاری جزئی

---

## ۵. آیا Generic واقعاً ۱۰۰٪ UI ابرو را منتقل کرده؟

**فایل:** `giso/buti_ai/templates/buti_ai/generic_service_wizard.html`

- **آیا دقیقاً همان ساختار را reuse کرده؟** خیر — ۹۰٪ reuse:
  - reuse: `bti-style-choice`, `bti-style-info`, `bti-style-row-icon`, `bti-style-row-copy`, `bti-change-panel`, `bti-upload-layout-redesigned`, JS `is-selected`
  - not reuse: `is-wide-png` کلاس، `picture` tag، `bti-sample-badge`, `bti-safe-badge` منطق، `small` داخل عکس
- **فقط بعضی کلاس‌ها؟** بله — `bti-style-choice` و `bti-brow-sample` reuse شده، اما `is-wide-png` فقط ابرو
- **آیا نام کلاس `bti-brow-sample` باعث وابستگی به ابرو شده؟** بله — نام `brow` برای ناخن/مو/لب معنایی ندارد — باید `bti-style-sample` یا `bti-service-sample` عمومی شود — الان ۳ خدمت وابسته به نام ابرو هستند
- **آیا بهتر است به کلاس عمومی تبدیل شود؟** بله — پیشنهاد: `bti-style-sample` به عنوان کلاس عمومی + `is-wide-png` به عنوان modifier عمومی — تغییر لازم است چون نام فعلی گمراه‌کننده و باعث می‌شود توسعه‌دهنده فکر کند این فقط برای ابرو است
- **آیا تغییر لازم است یا cosmetic؟** **لازم است** — چون:
  1. نام کلاس اشتباه (brow برای nail)
  2. باعث شده generic نتواند ۱۰۰٪ UI ابرو را بگیرد (چون override فقط برای is-wide-png)
  3. اگر بخواهیم Reuse > Extend > New، باید کلاس عمومی بسازیم و ابرو هم از همان استفاده کند

---

## ۶. عکس‌های نمونه

| خدمت | مسیر | فرمت | ابعاد واقعی | نسبت |
|---|---|---|---|---|
| ابرو natural.png | `static/brows/natural.png` | PNG | 800×319 | 2.51:1 (wide) |
| ابرو natural.jpg | `static/brows/natural.jpg` | JPG | 512×341 | 1.50:1 |
| ابرو natural.webp | `static/brows/natural.webp` | WEBP | 800×319 | 2.51:1 |
| ابرو giso_suggested.png | `static/brows/giso_suggested.png` | PNG | 800×340 | 2.35:1 |
| ناخن nude_minimal.jpg | `services/nail/nude_minimal.jpg` | JPG | 520×360 | 1.44:1 |
| ناخن baby_boomer.jpg | `services/nail/baby_boomer.jpg` | JPG | 520×360 | 1.44:1 |
| مو caramel_balayage.jpg | `services/hair_color/caramel_balayage.jpg` | JPG | 520×360 | 1.44:1 |
| لب natural_shading.jpg | `services/lip_shading/natural_shading.jpg` | JPG | 520×360 | 1.44:1 |

- **فرمت:** ابرو PNG+JPG+WEBP (۳ فرمت)، ۳ خدمت دیگر فقط JPG — ابرو بهینه‌تر
- **ابعاد:** ابرو PNG 800×319 wide، ۳ خدمت دیگر 520×360 — نسبت متفاوت
- **نسبت یکسان؟** خیر — ابرو 2.5:1، بقیه 1.44:1 — اگر `object-fit:cover` بود، ابرو crop می‌شد، اما چون `contain` است، فرقی نمی‌کند — عکس کامل دیده می‌شود با بک تیره
- **object-fit:** همه `contain` — پس نسبت خود عکس باعث تفاوت UI نمی‌شود، چون contain کل عکس را جا می‌دهد
- **object-position:** همه `center` — یکسان
- **آیا خود تصاویر باعث حس تفاوت UI شده؟** بله، کمی — چون عکس ابرو wide (ابرو افقی) و عکس ناخن مربعی‌تر، حتی با contain، فضای خالی داخل کانتینر متفاوت است — اما تفاوت اصلی از CSS (420 vs 380) است، نه از خود عکس

---

## ۷. Responsive دقیق

| Breakpoint | Eyebrow | Nail / Lip / Hair Color | تفاوت |
|---|---|---|---|
| **Desktop (>1060px)** | کارت flex row, عکس 420px, متن 1fr | کارت flex row, عکس 380px, متن 1fr | 40px عرض |
| **1060px** | `.bti-eyebrow-stage-separated grid 1fr` — فقط layout کلی، کارت‌ها همچنان row | همین | یکسان |
| **980px** | `.bti-uploaded-preview-card` grid 1fr — مربوط به result، نه model | همین | یکسان |
| **920px** | **خاص ابرو:** `.bti-style-choice flex-direction:column`, `.bti-brow-sample.is-wide-png width:100%, min-height:200px, img height:180px` | ندارد — در 920px همچنان row با 380px | **ساختاری: ابرو در 920px ستونی می‌شود، ۳ خدمت در 820px** |
| **900px** | هیچ rule خاص برای کارت مدل | هیچ | یکسان |
| **820px** | `.bti-style-choice flex-direction:column`, `.bti-brow-sample min-height:130px, flex-basis:auto, width:100%`, `.bti-upload-layout grid 1fr` | همین 820px برای generic هم اعمال می‌شود (چون .bti-style-choice و .bti-brow-sample مشترک) | **یکسان در 820px**، اما ابرو قبلاً در 920px ستونی شده |
| **720px** | `.bti-style-choice grid 1fr 132px` — override قدیمی (الان با !important خنثی شده) | همین قدیمی، اما override جدید 172px آن را می‌پوشاند | override جدید غالب — یکسان |
| **620px** | `.bti-style-info grid 44px 1fr`, `.bti-style-choice min-height:auto` | همین | یکسان |
| **Mobile <620px** | کارت min-height auto، عکس 100%، متن 44px آیکون | همین | یکسان |

**خلاصه Responsive:** ابرو یک breakpoint اضافه 920px دارد که ۳ خدمت ندارند — پس در تبلت 820-920px، ابرو ستونی و ۳ خدمت افقی — **تفاوت ساختاری**.

---

## ۸. نتیجه واضح

**گزینه B — ساختار مشترک است ولی چند تفاوت UI وجود دارد**

**چرا B نه A و نه C:**
- نه A (کاملاً یکسان) چون: عرض 420 vs 380، ارتفاع 168 vs 132، padding 12 vs 8، hover zoom دارد vs ندارد، badge متفاوت، breakpoint 920 vs 820
- نه C (کاملاً متفاوت) چون: HTML پایه `bti-style-choice`, `bti-style-info`, `bti-brow-sample`, `bti-change-panel`, JS `is-selected`, تم مشکی طلایی، transition, border, radius, gap, padding کارت — همه ۹۰٪ یکسان — فقط اندازه عکس و افکت‌ها فرق

---

## ۹. راهکار دقیق برای هر تفاوت (بدون تغییر کد الان — فقط پیشنهاد)

### تفاوت ۱: عرض تصویر کانتینر

```
فایل:
giso/buti_ai/static/buti_ai.css

کلاس:
.bti-brow-sample (generic) vs .bti-brow-sample.is-wide-png (eyebrow)

وضعیت ابرو:
flex: 0 0 420px !important; width:420px !important

وضعیت ۳ خدمت:
flex-basis:380px; (از 973) یا flex:0 0 190px (base 533)

راهکار:
کلاس عمومی .bti-style-sample بساز با width:420px و is-wide-png را حذف یا عمومی کن
.bti-style-sample { flex:0 0 420px !important; width:420px !important; ... }
.bti-brow-sample را به .bti-style-sample alias کن برای سازگاری

اثر: هر ۳ خدمت
```

### تفاوت ۲: ارتفاع تصویر

```
فایل: buti_ai.css

کلاس: .bti-brow-sample.is-wide-png vs .bti-brow-sample

ابرو: min-height:168px !important; max-height:188px !important; img height:150px !important
۳ خدمت: min-height:132px; img max-height:132px, min-height:124px

راهکار: یکسان کن به 168px/150px برای همه
.bti-style-sample { min-height:168px !important; }
.bti-style-sample img { height:150px !important; max-height:168px !important; }

اثر: هر ۳ خدمت
```

### تفاوت ۳: Hover Zoom

```
فایل: buti_ai.css خط 3190-3191

ابرو: .bti-style-choice:hover .bti-brow-sample.is-wide-png img { transform: scale(1.14) !important; }

۳ خدمت: هیچ rule برای .bti-brow-sample (بدون is-wide-png) — zoom ندارد

راهکار:
.bti-style-choice:hover .bti-style-sample img,
.bti-style-choice:hover .bti-brow-sample img { transform: scale(1.14) !important; }

اثر: هر ۳ خدمت — اضافه شدن zoom مثل ابرو
```

### تفاوت ۴: Selected Zoom + Shadow

```
فایل: buti_ai.css 3193-3198

ابرو: border-color rgba(255,173,18,.45) + box-shadow + img scale(1.10)

۳ خدمت: ندارد

راهکار: همان selector را برای generic هم اضافه
.bti-style-choice.is-selected .bti-style-sample,
.bti-style-choice.is-selected .bti-brow-sample { border-color: rgba(255,173,18,.45) !important; box-shadow: ... }

اثر: هر ۳ خدمت
```

### تفاوت ۵: Badge

```
فایل: eyebrow_wizard.html:52-53 vs generic_service_wizard.html:52

ابرو: <em class="bti-sample-badge">نمونه {label}</em> + <em class="bti-safe-badge">انتخاب امن</em> (فقط giso_suggested)
۳ خدمت: <em>انتخاب امن</em> (loop.first) + <small>نمونه مدل</small> داخل عکس

راهکار:
در generic_service_wizard.html هم مثل ابرو:
<em class="bti-sample-badge">نمونه {{ item.label }}</em>
{% if loop.first %}<em class="bti-safe-badge">انتخاب امن</em>{% endif %}
و small داخل عکس را حذف کن

فایل: generic_service_wizard.html:46-58
اثر: هر ۳ خدمت
```

### تفاوت ۶: Responsive breakpoint 920px

```
فایل: buti_ai.css 3200-3213

ابرو: @media (max-width:920px) { .bti-style-choice flex-direction:column; .bti-brow-sample.is-wide-png width:100%; min-height:200px; img height:180px }

۳ خدمت: این media query فقط is-wide-png را هدف می‌گیرد — generic در 920px همچنان row

راهکار:
@media (max-width:920px) {
  .bti-style-choice { flex-direction:column !important; }
  .bti-style-sample, .bti-brow-sample, .bti-brow-sample.is-wide-png { width:100% !important; min-height:200px !important; }
  .bti-style-sample img, .bti-brow-sample img { height:180px !important; }
}

اثر: هر ۳ خدمت — رفتار تبلت یکسان با ابرو
```

### تفاوت ۷: Padding و Border Radius جزئی

```
فایل: buti_ai.css 3155-3163 vs 968-973

ابرو: padding:12px !important; radius:15px !important; background radial 320px
۳ خدمت: padding:8px; radius:16px; background radial 220px

راهکار: یکسان به 12px و 15px و radial 320px برای همه

اثر: هر ۳ خدمت — cosmetic اما برای یکسان‌سازی کامل
```

### تفاوت ۸: نام کلاس bti-brow-sample

```
فایل: buti_ai.css + هر دو template

وضعیت: کلاس نامش brow (ابرو) اما برای ناخن/مو/لب استفاده می‌شود — گمراه‌کننده

راهکار (Reuse > Extend):
.bti-style-sample, .bti-brow-sample { ... } — هر دو selector یک استایل
یا alias: .bti-brow-sample = .bti-style-sample
سپس در templateها به تدریج به bti-style-sample مهاجرت

آیا لازم است؟ بله — برای معماری تمیز و Reuse — ولی اگر فقط cosmetic می‌خواهی، می‌توان با همان bti-brow-sample ادامه داد و فقط is-wide-png را عمومی کرد

اثر: هر ۴ خدمت (شامل ابرو) — معماری بهتر
```

---

## ۱۰. اصل معماری Reuse > Extend > New

- **Reuse:** از `buti_ai.css` موجود و کلاس `bti-style-choice` استفاده کن — همین الان ۹۰٪ reuse شده
- **Extend:** کلاس عمومی `bti-style-sample` بساز که `bti-brow-sample` را extend کند (یا alias) + `is-wide-png` را به modifier عمومی تبدیل کن — نه template جدا
- **New نساز:** برای Nail/Lip/Hair Color template جدا نساز — همین `generic_service_wizard.html` کافی است — فقط HTML داخلش را مثل ابرو کن (picture + em badge)

**نباید تغییر کند:**
- Backend `generic_service.py`, `final_design.py`, `service_catalog.py` — flow همان بماند
- Upload/Final routes — همان بماند
- AI logic — همان بماند
- JS `buti_ai.js` — همین `is-selected` کافی است

**فقط UI انتخاب مدل** باید یکسان شود.

---

## ۱۱. پیشنهاد نهایی — بهترین روش برای Eyebrow = Nail = Lip = Hair Color

### فایل‌هایی که باید تغییر کنند (اگر بخواهی یکسان‌سازی واقعی)

1. **`giso/buti_ai/static/buti_ai.css`**
   - کلاس عمومی جدید:
     ```css
     .bti-style-sample,
     .bti-brow-sample {
       flex: 0 0 420px !important;
       width: 420px !important;
       min-height: 168px !important;
       max-height: 188px !important;
       padding: 12px !important;
       border-radius: 15px !important;
       background: radial-gradient(320px 160px at 50% 50%, rgba(255,173,18,.10), transparent 70%), #0e0e0e !important;
       ...
     }
     .bti-style-sample img,
     .bti-brow-sample img {
       width:100% !important;
       height:150px !important;
       max-height:168px !important;
       object-fit:contain !important;
       object-position:center !important;
       transition: transform .35s cubic-bezier(.4,0,.2,1) !important;
     }
     .bti-style-choice:hover .bti-style-sample img,
     .bti-style-choice:hover .bti-brow-sample img {
       transform: scale(1.14) !important;
     }
     .bti-style-choice.is-selected .bti-style-sample img,
     .bti-style-choice.is-selected .bti-brow-sample img {
       transform: scale(1.10) !important;
     }
     @media (max-width:920px) {
       .bti-style-choice { flex-direction:column !important; }
       .bti-style-sample, .bti-brow-sample { width:100% !important; min-height:200px !important; }
       .bti-style-sample img, .bti-brow-sample img { height:180px !important; }
     }
     ```
   - `bti-brow-sample` را نگه دار برای سازگاری، ولی `bti-style-sample` را اصلی کن

2. **`giso/buti_ai/templates/buti_ai/generic_service_wizard.html`**
   - خط 52-58 را مثل ابرو کن:
     ```html
     <span class="bti-brow-sample is-wide-png">  <!-- اضافه is-wide-png -->
       <picture>
         <source srcset="{{ url_for('buti_ai.static', filename=service_meta.sample_dir ~ '/' ~ key ~ '.webp') }}" type="image/webp">
         <img src="{{ url_for('buti_ai.static', filename=service_meta.sample_dir ~ '/' ~ key ~ '.png') }}" alt="نمونه {{ item.label }}" width="420" height="168" loading="lazy">
       </picture>
     </span>
     ```
   - و بج‌ها:
     ```html
     <em class="bti-sample-badge">نمونه {{ item.label }}</em>
     {% if loop.first %}<em class="bti-safe-badge">انتخاب امن</em>{% endif %}
     ```
   - حذف `small>نمونه مدل` داخل عکس

3. **عکس‌های نمونه (optional ولی برای یکسان‌سازی کامل):**
   - برای ۳ خدمت دیگر هم نسخه PNG + WEBP 800×~320 بساز مثل ابرو — الان فقط JPG 520×360 دارند
   - اگر نسازی، با `object-fit:contain` فعلی هم کار می‌کند، ولی فضای خالی متفاوت است

### چه چیزهایی نباید تغییر کنند
- `generic_service.py`, `service_catalog.py`, `final_design.py` هر ۳ خدمت
- `routes.py`, upload/finalize logic
- `buti_ai.js` — همین JS کافی است

### آیا Template مشترک کافی است؟
بله — همین `generic_service_wizard.html` با اصلاح بالا کافی است — نیازی به template جدا برای هر خدمت نیست (Reuse)

### آیا CSS مشترک کافی است؟
بله — فقط با اضافه کردن alias `bti-style-sample` و تعمیم `is-wide-png` + hover/selected به generic، CSS مشترک کافی است

### آیا JS لازم است تغییر کند؟
خیر — همین `buti_ai.js:134` که `is-selected` اضافه می‌کند برای هر ۴ خدمت کار می‌کند

---

## ۱۲. آیا واقعاً نیاز به تغییر کد هست؟

**بله — برای گزینه B به A رسیدن، نیاز به تغییر کد هست، ولی خیلی کوچک:**

- **CSS:** ~15 خط (alias + تعمیم width/height/hover/selected + media query 920px)
- **Template generic:** ~8 خط (اضافه is-wide-png + picture + بج‌ها)
- **عکس (optional):** ساخت PNG/WEBP برای ۳ خدمت (۱۵ فایل)

بدون این تغییرات، ۳ خدمت **۹۰٪ مثل ابرو** هستند ولی **۱۰۰٪ یکسان نیستند** — تفاوت 40px عرض، 36px ارتفاع، بدون زوم، بج متفاوت، breakpoint متفاوت.

اگر همین ۹۰٪ برایت کافی است، می‌توان گفت **بدون تغییر کد هم قابل قبول است** — چون کاربر عادی تفاوت 40px را حس نمی‌کند. ولی اگر می‌خواهی **دقیقاً مطابق UI ابرو** (همان درخواست تو)، **باید ۲ فایل بالا تغییر کند**.

---

**پایان Audit — هیچ فایلی تغییر نکرد — فقط گزارش `mirror_model_audit.md` تولید شد**
