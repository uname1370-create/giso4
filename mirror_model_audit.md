# Audit UI انتخاب مدل — Eyebrow مرجع vs Nail / Lip / Hair Color — Code Truth

> Branch: `arena/01a0eecf-giso4` — HEAD `a37b272` (origin/arena/01a0eecf-giso4) — با final override
> تاریخ: 2026-10-07
> اصل: فقط کد زنده Template + CSS + JS + تصاویر

## نتیجه نهایی

### گزینه B — ساختار مشترک است ولی چند تفاوت UI وجود دارد

**چرا B نه A و نه C:**
- نه A چون: عرض تصویر 420px vs 380px، ارتفاع 168px vs 132px، padding 12px vs 8px، hover zoom scale(1.14) فقط ابرو، badge کلاس متفاوت، breakpoint 920px فقط ابرو
- نه C چون: 90% مشترک — کارت `bti-style-choice` با `min-height:172px !important`, `padding:14px`, `gap:14px`, `radius:18px`, `border rgba(255,255,255,.09)`, `bg #101010`, `transition all .22s ease`, `hover translateY(-1px) border rgba(255,173,18,.62)`, JS `is-selected` — همه یکسان

---

## ۱. UI انتخاب مدل ابرو — مرجع دقیق

### مسیر واقعی
- **Template:** `giso/buti_ai/templates/buti_ai/eyebrow_wizard.html` خط 54-70 — CSS `v=19`
  ```html
  label.bti-style-choice.is-style-{key}.is-selected > input[radio] + span.bti-style-info (icon+copy+b+small+em.bti-sample-badge+em.bti-safe-badge) + span.bti-brow-sample.is-wide-png > picture > source(webp) + img(png 420x168)
  ```
- **CSS:** `giso/buti_ai/static/buti_ai.css`
  - پایه 533-600: `min-height:142px, flex, gap:14px, padding:14px, border rgba(255,255,255,.09), radius:18px, bg:#101010`
  - override 959-1010: `min-height:168px, flex-basis:380px/420px, min-height:132px/140px, img min-height:124px max-height:132px/148px`
  - **نهایی 3091-3220 با !important** (غالب):
    - `.bti-style-choice { display:flex !important; align-items:stretch !important; gap:14px !important; padding:14px !important; min-height:172px !important; border:1px solid rgba(255,255,255,.09) !important; radius:18px !important; bg:#101010 !important; transition:all .22s ease !important; }`
    - `.bti-brow-sample.is-wide-png { flex:0 0 420px !important; width:420px !important; min-height:168px !important; max-height:188px !important; background:radial-gradient(320px 160px at 50% 50%, rgba(255,173,18,.10), transparent 70%), #0e0e0e !important; border:1px solid rgba(255,255,255,.08) !important; display:grid !important; place-items:center !important; padding:12px !important; radius:15px !important; overflow:hidden !important; transition:all .28s cubic-bezier(.4,0,.2,1) !important; }`
    - `.bti-brow-sample.is-wide-png img { width:100% !important; height:150px !important; max-height:168px !important; object-fit:contain !important; object-position:center !important; filter:none !important; transform:none !important; background:transparent !important; radius:0 !important; transition:transform .35s cubic-bezier(.4,0,.2,1) !important; }`
    - hover: `.bti-style-choice:hover .bti-brow-sample.is-wide-png img { transform:scale(1.14) !important; }`
    - selected: `.bti-style-choice.is-selected .bti-brow-sample.is-wide-png { border-color:rgba(255,173,18,.45) !important; box-shadow:0 0 0 1px rgba(255,173,18,.18), 0 4px 18px rgba(255,173,18,.12) !important; }` + `img scale(1.10) !important`
- **JS:** `giso/buti_ai/static/buti_ai.js:134-141` → `querySelectorAll('.bti-style-choice')` → change → `is-selected`
- **عکس:** `giso/buti_ai/static/brows/{key}.png + .webp` — `width=420 height=168 loading=lazy` via `url_for('buti_ai.static', filename='brows/' ~ key ~ '.webp')`

### کارت مدل — دقیق

- width: 100% داخل `bti-shell min(1120px, calc(100% - 32px))`
- min-height: `172px !important` (نهایی 3091) — پایه 142px → 168px → نهایی 172px
- height: auto
- padding: `14px !important`
- margin: 0 + gap 10px از `bti-style-list`
- gap داخلی: `14px !important`
- border: `1px solid rgba(255,255,255,.09) !important`
- border-radius: `18px !important`
- background: `#101010 !important`
- transition: `all .22s ease !important`
- hover transform: `translateY(-1px)` (پایه 551) + border `rgba(255,173,18,.62)` + bg `linear-gradient(135deg, rgba(255,173,18,.10), rgba(255,255,255,.035))`
- selected: `:has(input:checked)` + `.is-selected` → همان hover + JS

### عکس نمونه — ابرو

- width: `420px !important`, flex `0 0 420px !important`
- height: container `min-height:168px !important max-height:188px !important`, img `height:150px !important max-height:168px !important`
- min-height: 168px
- aspect-ratio: ندارد
- object-fit: `contain !important`
- object-position: `center !important`
- border-radius: container `15px !important`, img `0 !important`
- filter: `none !important`
- overflow: `hidden !important`
- padding: `12px !important`
- جای عکس: `flex` کنار متن، `gap:14px`، order بعد از `bti-style-info`, `display:grid place-items:center`

### افکت‌ها — ابرو

- Hover کارت: border طلایی + bg gradient + translateY(-1px) — transition .22s
- Hover تصویر کانتینر: border `rgba(255,173,18,.22)` + bg radial بزرگتر `rgba(255,173,18,.14)`
- Hover Zoom تصویر: **وجود دارد** — `scale(1.14) !important` + `transition transform .35s cubic-bezier(.4,0,.2,1)`
- Transform: کارت translateY, عکس scale
- Overlay: ندارد — فقط radial background
- Border تغییر رنگ: بله
- Shadow: selected `box-shadow:0 0 0 1px rgba(255,173,18,.18), 0 4px 18px rgba(255,173,18,.12)`
- Selected: scale(1.10) + shadow + border طلایی
- Badge: `em.bti-sample-badge` → "نمونه {label}" — `bg:#ffad12 color:#000 padding:5px 12px radius:999px font:.76rem weight:800 shadow:0 2px 8px rgba(255,173,18,.22)` + `em.bti-safe-badge` → "انتخاب امن" فقط `giso_suggested` — `padding:5px 14px font:.82rem weight:900`
- متن نمونه مدل: em بیرون عکس، زیر عنوان
- انیمیشن: transform .35s cubic-bezier + all .22s ease + all .28s cubic-bezier برای کانتینر

---

## ۲. هر سه خدمت جداگانه

### مسیر مشترک
- Template: `giso/buti_ai/templates/buti_ai/generic_service_wizard.html` خط 54-70 — CSS `v=24`
- CSS: همان `buti_ai.css` — ولی بدون `is-wide-png` → 380px
- JS: همان
- عکس: `services/{service}/{key}.jpg` — 520×360 JPG

### Nail
- HTML: `label.bti-style-choice > input + span.bti-style-info (icon+copy+b+small) + em (انتخاب امن loop.first) + span.bti-brow-sample (بدون is-wide-png) > img jpg + small نمونه مدل`
- CSS کارت: همان `172px !important` — یکسان (چون 3091 برای همه)
- CSS تصویر: `flex-basis:380px; min-height:132px; background:radial 220px 120px rgba(255,173,18,.08), #0e0e0e; border rgba(255,255,255,.06); radius:16px; padding:8px` — **نه 420px**
- img: `min-height:124px; width:100%; height:auto; max-height:132px; object-fit:contain; object-position:center` — **نه 150px**
- Hover Zoom: **وجود ندارد** — selector فقط `is-wide-png img` — generic هیچ scale ندارد
- Badge: `em` بدون کلاس + `small` داخل عکس absolute bottom 10px right 50% translateX(50%) bg rgba(255,173,18,.92)

### Lip (lip_shading)
- دقیقاً مثل Nail — همین template, همین CSS 380px, همین JPG, همین small
- مدل‌ها: ۵ تا (natural_shading, natural_contour, peach_nude, soft_pink_tint, dark_tone_neutralize)

### Hair Color
- دقیقاً مثل Nail/Lip — همین template, همین CSS 380px
- مدل‌ها: ۵ تا (caramel_balayage, chocolate_nescafe, face_frame, natural_highlight, ash_olive)

---

## ۳. جدول مقایسه دقیق و عددی — Branch فعلی با final override

| مورد | Eyebrow (مرجع) | Nail | Lip | Hair Color | تفاوت | inherited از کجا |
|---|---|---|---|---|---|---|
| **ساختار HTML** | `label.bti-style-choice.is-style-{key} + span.bti-style-info + span.bti-brow-sample.is-wide-png > picture > source(webp)+img(png 420x168)` | `label.bti-style-choice + span.bti-style-info + span.bti-brow-sample (بدون is-wide-png) > img(jpg) + small` | مثل Nail | مثل Nail | **ساختاری:** picture vs img, is-wide-png vs ساده, small داخل vs em بیرون | template |
| **کلاس کارت** | `bti-style-choice is-style-{key} is-wide-png` | `bti-style-choice is-style-{key}` | مثل Nail | مثل Nail | کلاس is-wide-png فقط ابرو | - |
| **عرض کارت** | 100% | یکسان | یکسان | یکسان | یکسان | shell |
| **ارتفاع کارت** | `172px !important` | همین 172px | همین | همین | یکسان | buti_ai.css:3091 نهایی |
| **Padding کارت** | `14px !important` | یکسان | یکسان | یکسان | یکسان | 3091 |
| **Gap کارت** | `14px !important` | یکسان | یکسان | یکسان | یکسان | 3091 |
| **Border کارت** | `1px solid rgba(255,255,255,.09) !important` | یکسان | یکسان | یکسان | یکسان | 3091 |
| **Radius کارت** | `18px !important` | یکسان | یکسان | یکسان | یکسان | 3091 |
| **تصویر — کلاس** | `bti-brow-sample is-wide-png` | `bti-brow-sample` | یکسان | یکسان | تفاوت کلاس | - |
| **عرض تصویر کانتینر** | `420px !important` + `flex:0 0 420px !important` | `380px` (flex-basis:380px) | 380px | 380px | **ساختاری: 40px اختلاف** | eyebrow 3155-3156 vs generic 968 |
| **ارتفاع کانتینر** | `min-height:168px !important max-height:188px !important` | `min-height:132px` | 132px | 132px | **36px اختلاف** | 3157-3158 vs 969 |
| **Aspect Ratio** | ندارد | ندارد | ندارد | ندارد | یکسان | - |
| **Object Fit img** | `contain !important` | `contain` | یکسان | یکسان | یکسان مقدار، !important فقط ابرو | 3177 vs 976 |
| **Object Position** | `center !important` | `center` | یکسان | یکسان | یکسان | 3178 |
| **Radius کانتینر** | `15px !important` | `16px` | 16px | 16px | **1px اختلاف** | 3163 vs 971 |
| **Radius img** | `0 !important` | ندارد | - | - | - | 3180 |
| **Overflow** | `hidden !important` | `hidden` | یکسان | یکسان | یکسان | 3164 vs base |
| **Padding کانتینر** | `12px !important` | `8px` | 8px | 8px | **4px اختلاف** | 3162 vs 971 |
| **Background کانتینر** | `radial 320px 160px rgba(255,173,18,.10), #0e0e0e !important` | `radial 220px 120px rgba(255,173,18,.08), #0e0e0e` | یکسان | یکسان | اندازه radial فرق | 3159 vs 970 |
| **Overlay** | ندارد | ندارد | ندارد | ندارد | یکسان | - |
| **Filter img** | `none !important` | `none` | یکسان | یکسان | یکسان | 3179 |
| **عرض img** | `100% !important` | `100%` | یکسان | یکسان | یکسان | 3175 |
| **ارتفاع img** | `150px !important max-height:168px !important` | `auto max-height:132px min-height:124px` | یکسان | یکسان | **ساختاری: 18-36px اختلاف** | 3176-3177 vs 974-976 |
| **Hover Zoom** | **وجود دارد** `scale(1.14) !important` + transition .35s cubic-bezier | **وجود ندارد** | ندارد | ندارد | **ساختاری مهم** | 3190-3191 فقط is-wide-png |
| **Selected Transform** | `scale(1.10) !important` + box-shadow | ندارد | ندارد | ندارد | **ساختاری مهم** | 3197-3198 |
| **Badge** | `em.bti-sample-badge` نمونه {label} + `em.bti-safe-badge` انتخاب امن (فقط giso_suggested) | `em` بدون کلاس انتخاب امن (loop.first) + `small` نمونه مدل داخل عکس | مثل Nail | مثل Nail | **ساختاری: بج متفاوت + small vs em** | eyebrow_wizard 52-53 vs generic 52 |
| **متن نمونه مدل** | em بیرون عکس | small داخل absolute bottom 10px right 50% translateX(50%) | یکسان | یکسان | جای متفاوت | - |
| **فاصله‌ها** | gap 14px بین متن و عکس، 6px بین عنوان و خلاصه | یکسان 14px/6px | یکسان | یکسان | یکسان | 3094 + 3114 |
| **Mobile 920px** | `flex-direction:column`, عکس `width:100% min-height:200px img height:180px` — فقط is-wide-png | ندارد — در 820px ستونی | مثل Nail | مثل Nail | **ساختاری: breakpoint 920 vs 820 + ارتفاع 200 vs 130** | 3200-3213 فقط is-wide-png |
| **Mobile 820px** | `flex-direction:column, width:100% min-height:130px` | یکسان | یکسان | یکسان | یکسان در 820px، ولی ابرو قبلاً در 920px ستونی شده | 729-737 |

---

## ۴. تفاوت محتوایی vs ساختاری

### محتوایی (مشکل نیست)
- عکس متفاوت: ابرو ابرو، ناخن دست، مو مو، لب لب — طبیعی
- نام مدل متفاوت: طبیعی/میکروبلیدینگ vs نود/فرنچ vs کارامل — طبیعی
- توضیح متفاوت: summary متفاوت — طبیعی
- تعداد مدل‌ها: هر ۴ خدمت ۵ مدل — یکسان

### ساختاری (باید گزارش شود)
1. عرض کانتینر: 420px vs 380px → 40px — ساختاری — `buti_ai.css:3156 vs 968`
2. ارتفاع کانتینر: 168px vs 132px → 36px — ساختاری
3. ارتفاع img: 150px vs auto/132px → 18px — ساختاری
4. Padding: 12px vs 8px → 4px — ساختاری
5. Radius: 15px vs 16px → 1px — جزئی
6. Hover Zoom: scale(1.14) دارد vs ندارد — **مهم** — `3190`
7. Selected: scale(1.10)+shadow دارد vs ندارد — **مهم** — `3193`
8. Badge: bti-sample-badge + bti-safe-badge vs em بدون کلاس + small داخل — ساختاری
9. نمونه مدل جای: em بیرون vs small داخل absolute — ساختاری
10. Breakpoint: 920px برای ابرو vs 820px برای generic — ساختاری
11. Mobile ارتفاع: 200px/180px vs 130px — ساختاری
12. Background radial: 320px vs 220px — cosmetic جزئی

---

## ۵. Generic واقعاً 100٪ UI ابرو را منتقل کرده؟

**فایل:** `giso/buti_ai/templates/buti_ai/generic_service_wizard.html`

- آیا دقیقاً همان ساختار را reuse کرده؟ **خیر — 90% reuse**
  - reuse: `bti-style-choice`, `bti-style-info`, `bti-style-row-icon`, `bti-style-row-copy`, `bti-change-panel`, `bti-upload-layout-redesigned`, JS `is-selected`
  - not reuse: `is-wide-png`, `picture`, `bti-sample-badge`, `bti-safe-badge`, `small` داخل vs em بیرون
- آیا فقط بعضی کلاس‌ها؟ بله — `bti-style-choice` و `bti-brow-sample` reuse، ولی `is-wide-png` فقط ابرو
- آیا نام `bti-brow-sample` وابستگی ایجاد کرده؟ **بله** — نام brow برای ناخن/مو/لب بی‌معنا — باعث شده generic نتواند 100% UI ابرو را بگیرد چون override فقط برای is-wide-png است
- آیا بهتر است به `bti-style-sample` تبدیل شود؟ **بله** — پیشنهاد `bti-style-sample` عمومی + `is-wide-png` به modifier عمومی — تغییر **لازم** است، نه فقط cosmetic، چون نام فعلی گمراه‌کننده و مانع reuse کامل است
- آیا تغییر لازم است یا cosmetic؟ **لازم** — برای Reuse > Extend > New و تمیز شدن معماری

---

## ۶. عکس‌های نمونه

| خدمت | مسیر | فرمت | ابعاد واقعی | نسبت |
|---|---|---|---|---|
| ابرو natural.png | `static/brows/natural.png` | PNG | 800×319 | 2.51:1 wide |
| ابرو natural.jpg | `static/brows/natural.jpg` | JPG | 512×341 | 1.50:1 |
| ابرو natural.webp | `static/brows/natural.webp` | WEBP | 800×319 | 2.51:1 |
| ابرو giso_suggested.png | `static/brows/giso_suggested.png` | PNG | 800×340 | 2.35:1 |
| ناخن nude_minimal.jpg | `services/nail/nude_minimal.jpg` | JPG | 520×360 | 1.44:1 |
| مو caramel_balayage.jpg | `services/hair_color/caramel_balayage.jpg` | JPG | 520×360 | 1.44:1 |
| لب natural_shading.jpg | `services/lip_shading/natural_shading.jpg` | JPG | 520×360 | 1.44:1 |

- فرمت: ابرو PNG+JPG+WEBP (۳ فرمت بهینه)، ۳ خدمت دیگر فقط JPG
- ابعاد: ابرو PNG 800×319 wide، بقیه 520×360 مربعی‌تر — نسبت متفاوت
- نسبت یکسان؟ خیر — ابرو 2.5:1 vs بقیه 1.44:1 — اگر cover بود crop می‌شد، ولی چون contain است، فرقی نمی‌کند — فضای خالی داخل کانتینر متفاوت است
- object-fit: ابرو `contain !important` (نهایی)، generic `contain` — یکسان مقدار
- object-position: همه `center` — یکسان
- آیا خود تصاویر باعث حس تفاوت UI شده‌اند؟ بله کمی — چون عکس ابرو wide و عکس ناخن مربعی، حتی با contain فضای خالی متفاوت است — ولی تفاوت اصلی از CSS (420 vs 380) است

---

## ۷. Responsive دقیق

| Breakpoint | Eyebrow | Nail / Lip / Hair Color | تفاوت |
|---|---|---|---|
| **Desktop >1060px** | کارت flex row, عکس 420px, متن 1fr | کارت flex row, عکس 380px, متن 1fr | 40px عرض |
| **1060px** | `.bti-eyebrow-stage-separated grid 1fr` | یکسان | یکسان |
| **980px** | `.bti-uploaded-preview-card grid 1fr` | یکسان | یکسان |
| **920px** | **خاص ابرو:** `flex-direction:column, width:100%, min-height:200px, img height:180px` — فقط is-wide-png | ندارد — همچنان row 380px | **ساختاری: ابرو در 920px ستونی، ۳ خدمت در 820px** |
| **900px** | هیچ | هیچ | یکسان |
| **820px** | `flex-direction:column, min-height:130px, flex-basis:auto, width:100%, upload grid 1fr` | همین 820px برای generic هم (چون .bti-style-choice مشترک) | یکسان در 820px، ولی ابرو قبلاً در 920px ستونی شده |
| **720px** | قدیمی grid 1fr 132px (با !important خنثی شده) | همین | override جدید غالب |
| **620px** | `bti-style-info 44px 1fr, bti-style-choice min-height:auto` | یکسان | یکسان |

---

## ۸. نتیجه واضح — تکرار

**گزینه B — ساختار مشترک است ولی چند تفاوت UI وجود دارد**

نه A چون 40px عرض، 36px ارتفاع، بدون زوم، بج متفاوت، breakpoint 920 vs 820
نه C چون 90% یکسان — کارت، تم مشکی طلایی، transition، border، radius، gap، JS همه یکسان

---

## ۹. راهکار دقیق برای هر تفاوت

### تفاوت ۱: عرض تصویر

```
فایل: giso/buti_ai/static/buti_ai.css
کلاس: .bti-brow-sample vs .bti-brow-sample.is-wide-png
وضعیت ابرو: flex:0 0 420px !important; width:420px !important (3155-3156)
وضعیت ۳ خدمت: flex-basis:380px; (968) — 40px کمتر
راهکار: کلاس عمومی .bti-style-sample بساز با width:420px و is-wide-png را عمومی کن
.bti-style-sample, .bti-brow-sample { flex:0 0 420px !important; width:420px !important; }
اثر: هر ۳ خدمت
```

### تفاوت ۲: ارتفاع تصویر

```
فایل: buti_ai.css
کلاس: .bti-brow-sample.is-wide-png vs .bti-brow-sample
ابرو: min-height:168px !important max-height:188px !important img 150px !important (3157-3176)
۳ خدمت: min-height:132px img max-height:132px min-height:124px (969-976)
راهکار: یکسان به 168px/150px
.bti-style-sample { min-height:168px !important; } .bti-style-sample img { height:150px !important; max-height:168px !important; }
اثر: هر ۳ خدمت
```

### تفاوت ۳: Hover Zoom

```
فایل: buti_ai.css:3190-3191
ابرو: .bti-style-choice:hover .bti-brow-sample.is-wide-png img { transform:scale(1.14) !important; }
۳ خدمت: هیچ rule — zoom ندارد
راهکار: .bti-style-choice:hover .bti-style-sample img, .bti-style-choice:hover .bti-brow-sample img { transform:scale(1.14) !important; }
اثر: هر ۳ خدمت — اضافه شدن zoom مثل ابرو
```

### تفاوت ۴: Selected Zoom + Shadow

```
فایل: buti_ai.css:3193-3198
ابرو: border-color rgba(255,173,18,.45) + box-shadow + img scale(1.10)
۳ خدمت: ندارد
راهکار: .bti-style-choice.is-selected .bti-style-sample, .bti-style-choice.is-selected .bti-brow-sample { border-color:rgba(255,173,18,.45) !important; box-shadow:... } + img scale(1.10)
اثر: هر ۳ خدمت
```

### تفاوت ۵: Badge

```
فایل: eyebrow_wizard.html:52-53 vs generic_service_wizard.html:52-64
ابرو: <em class="bti-sample-badge">نمونه {label}</em> + <em class="bti-safe-badge">انتخاب امن</em> (giso_suggested)
۳ خدمت: <em>انتخاب امن</em> loop.first + <small>نمونه مدل</small> داخل عکس
راهکار: در generic هم مثل ابرو:
<em class="bti-sample-badge">نمونه {{ item.label }}</em>
{% if loop.first %}<em class="bti-safe-badge">انتخاب امن</em>{% endif %}
و small داخل عکس حذف
فایل: generic_service_wizard.html:46-58
اثر: هر ۳ خدمت
```

### تفاوت ۶: Responsive 920px

```
فایل: buti_ai.css:3200-3213
ابرو: @media (max-width:920px) { .bti-style-choice flex-direction:column; .bti-brow-sample.is-wide-png width:100% min-height:200px img 180px }
۳ خدمت: این media فقط is-wide-png — generic در 920px row می‌ماند
راهکار: @media (max-width:920px) { .bti-style-choice { flex-direction:column !important; } .bti-style-sample, .bti-brow-sample { width:100% !important; min-height:200px !important; } img height:180px !important; }
اثر: هر ۳ خدمت — رفتار تبلت یکسان
```

### تفاوت ۷: Padding و Radius جزئی

```
فایل: buti_ai.css 3155-3163 vs 968-973
ابرو: padding:12px !important radius:15px !important radial 320px
۳ خدمت: padding:8px radius:16px radial 220px
راهکار: یکسان به 12px و 15px و radial 320px برای همه
اثر: هر ۳ خدمت — cosmetic ولی برای یکسان‌سازی کامل
```

### تفاوت ۸: نام کلاس bti-brow-sample

```
فایل: buti_ai.css + هر دو template
وضعیت: کلاس نامش brow ولی برای ناخن/مو/لب استفاده می‌شود
راهکار (Reuse>Extend): .bti-style-sample, .bti-brow-sample { ... } alias + is-wide-png عمومی
لازم است؟ بله — برای معماری تمیز و Reuse
اثر: هر ۴ خدمت
```

---

## ۱۰. اصل معماری Reuse > Extend > New

- Reuse: از buti_ai.css و bti-style-choice استفاده کن — همین الان 90% reuse
- Extend: کلاس عمومی bti-style-sample بساز که bti-brow-sample را extend کند + is-wide-png را عمومی کن — نه template جدا
- New نساز: برای Nail/Lip/Hair template جدا نساز — همین generic_service_wizard.html کافی است — فقط HTML داخلش مثل ابرو کن
- نباید تغییر کند: Backend generic_service.py, service_catalog.py, final_design.py, routes.py, upload/finalize, AI logic, JS is-selected

---

## ۱۱. پیشنهاد نهایی — Eyebrow = Nail = Lip = Hair Color

### فایل‌هایی که باید تغییر کنند (اگر بخواهی A شود)

1. **giso/buti_ai/static/buti_ai.css**
   - alias عمومی:
     ```css
     .bti-style-sample,
     .bti-brow-sample {
       flex:0 0 420px !important; width:420px !important; min-height:168px !important; max-height:188px !important;
       padding:12px !important; border-radius:15px !important;
       background:radial-gradient(320px 160px at 50% 50%, rgba(255,173,18,.10), transparent 70%), #0e0e0e !important;
     }
     .bti-style-sample img,
     .bti-brow-sample img {
       width:100% !important; height:150px !important; max-height:168px !important;
       object-fit:contain !important; object-position:center !important;
       transition:transform .35s cubic-bezier(.4,0,.2,1) !important;
     }
     .bti-style-choice:hover .bti-style-sample img,
     .bti-style-choice:hover .bti-brow-sample img { transform:scale(1.14) !important; }
     .bti-style-choice.is-selected .bti-style-sample img,
     .bti-style-choice.is-selected .bti-brow-sample img { transform:scale(1.10) !important; }
     @media (max-width:920px) {
       .bti-style-choice { flex-direction:column !important; }
       .bti-style-sample, .bti-brow-sample { width:100% !important; min-height:200px !important; }
       .bti-style-sample img, .bti-brow-sample img { height:180px !important; }
     }
     ```

2. **giso/buti_ai/templates/buti_ai/generic_service_wizard.html**
   - خط 64: `span.bti-brow-sample is-wide-png` اضافه + picture webp/png 420×168:
     ```html
     <span class="bti-brow-sample is-wide-png">
       <picture>
         <source srcset="{{ url_for('buti_ai.static', filename=service_meta.sample_dir ~ '/' ~ key ~ '.webp') }}" type="image/webp">
         <img src="{{ url_for('buti_ai.static', filename=service_meta.sample_dir ~ '/' ~ key ~ '.png') }}" alt="نمونه {{ item.label }}" width="420" height="168" loading="lazy">
       </picture>
     </span>
     ```
   - بج‌ها:
     ```html
     <em class="bti-sample-badge">نمونه {{ item.label }}</em>
     {% if loop.first %}<em class="bti-safe-badge">انتخاب امن</em>{% endif %}
     ```
   - حذف `small>نمونه مدل`

3. **عکس‌ها (optional):** برای ۳ خدمت هم PNG+WEBP 800×~320 مثل ابرو بساز — الان فقط JPG 520×360

### چه چیزهایی نباید تغییر کنند
- `generic_service.py`, `service_catalog.py`, `final_design.py`, `routes.py`, upload/finalize, AI
- `buti_ai.js` — همین is-selected کافی است

### آیا Template مشترک کافی است؟
بله — همین generic_service_wizard.html با اصلاح بالا کافی است — نیاز به template جدا نیست

### آیا CSS مشترک کافی است؟
بله — فقط با alias bti-style-sample + تعمیم is-wide-png + hover/selected + media 920px

### آیا JS لازم است تغییر کند؟
خیر

---

## آیا واقعاً نیاز به تغییر کد هست؟

**بله — برای رسیدن از B به A، نیاز به تغییر کد هست، ولی خیلی کوچک:**

- CSS: ~15 خط (alias + تعمیم width/height/hover/selected + media 920px)
- Template generic: ~8 خط (is-wide-png + picture + بج‌ها)
- عکس optional: 15 فایل PNG/WEBP

بدون این تغییرات، ۳ خدمت **90% مثل ابرو** هستند ولی **100% یکسان نیستند** — تفاوت 40px عرض، 36px ارتفاع، بدون زوم، بج متفاوت، breakpoint متفاوت.

اگر همین 90% برایت کافی است، می‌توان گفت بدون تغییر هم قابل قبول است — ولی اگر می‌خواهی **دقیقاً مطابق UI ابرو**، باید ۲ فایل بالا تغییر کند.

---

**پایان Audit — هیچ فایلی تغییر نکرد — فقط گزارش `mirror_model_audit.md` تولید شد — Branch فعلی `a37b272` با final override**
