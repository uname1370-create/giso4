# Audit UI انتخاب مدل — Eyebrow مرجع vs Nail / Lip / Hair Color — Code Truth

> Branch: `arena/01a0eecf-giso4` HEAD=`f9a7fb0` (clean, no local changes)
> تاریخ: 2026-10-07
> اصل: فقط کد زنده — Template + CSS + JS + تصاویر

## نتیجه نهایی — یکی از سه گزینه

### گزینه A — کاملاً یکسان هستند

**دلیل:** در HEAD فعلی `f9a7fb0`، هر چهار خدمت از **یک Template ساختار** و **یک CSS مشترک** استفاده می‌کنند. تفاوت‌ها فقط محتوایی (نام مدل، عکس، توضیح) هستند، نه ساختاری. هیچ تفاوت UI ساختاری بین ابرو و سه خدمت دیگر وجود ندارد.

---

## ۱. UI انتخاب مدل ابرو — مرجع دقیق (Code Truth)

### مسیر واقعی
- **Template:** `giso/buti_ai/templates/buti_ai/eyebrow_wizard.html` خط 54-70 — CSS `v=19`
- **CSS:** `giso/buti_ai/static/buti_ai.css`
  - پایه: خط 533-600
  - overrideها: 760-820 (230px/144px), 959-973 (198px/124px), 2220-2240 (154px/92px), **نهایی 2337-2365 (132px/86px)** — آخرین rule غالب است
- **JS:** `giso/buti_ai/static/buti_ai.js` خط 134-141 — `querySelectorAll('.bti-style-choice')` → `change` → `is-selected`
- **عکس:** `giso/buti_ai/static/brows/{key}.jpg` — `url_for('buti_ai.static', filename='brows/' ~ key ~ '.jpg')`

### کارت مدل — استخراج نهایی (آخرین rule در CSS بدون !important)

| ویژگی | مقدار نهایی (HEAD) | منبع |
|---|---|---|
| کلاس | `bti-style-choice is-style-{key} is-selected` | eyebrow_wizard.html:54 |
| display | `grid` | buti_ai.css:2338 (نهایی) |
| grid-template-columns | `minmax(0, 1fr) 132px` | 2339 |
| min-height / height | `min-height:106px`, `height:auto` | 2340 |
| padding | `12px` | 2342 |
| margin | `0` + `gap:10px` از parent `bti-style-list` | 347 |
| gap (داخلی) | `12px` | 2341 |
| border | `1px solid rgba(255,255,255,.09)` | 538 (پایه) |
| border-radius | `18px` | 539 |
| background | `#101010` | 540 |
| transition | `border-color .18s ease, background .18s ease, transform .18s ease` | 541 |
| hover transform | `translateY(-1px)` | 551 |
| hover border | `rgba(255,173,18,.62)` | 549 |
| hover background | `linear-gradient(135deg, rgba(255,173,18,.10), rgba(255,255,255,.035))` | 550 |
| selected | `:has(input:checked)` + `.is-selected` → همان hover + JS اضافه `is-selected` | 548 + buti_ai.js:138 |

### عکس نمونه — HEAD

| ویژگی | مقدار نهایی HEAD | منبع |
|---|---|---|
| کلاس | `bti-brow-sample` (بدون is-wide-png در HEAD) | eyebrow_wizard.html:64 |
| width | `132px` | 2352 |
| height | `86px` | 2353 |
| min-height | `86px` | 2354 |
| flex | `none` | 2355 |
| aspect-ratio | ندارد | - |
| object-fit (img) | `cover` | 2360 |
| object-position | `center 34%` | 2361 |
| border-radius کانتینر | `16px` | 590 (پایه) |
| border-radius img | `15px` (از 778) ولی override نهایی 2360 ندارد، پس 15px از 778 | 778 |
| overflow | `hidden` | 587 |
| padding کانتینر | `0` (از 766) | 766 |
| background کانتینر | `radial-gradient(circle at 50% 44%, rgba(255,205,130,.24), transparent 38%), linear-gradient(135deg, #1b1512, #0b0b0b 68%)` | 591-593 |
| filter img | `saturate(.96) contrast(1.04) brightness(.94)` | 781 |
| overlay | `::after` gradient `linear-gradient(90deg, rgba(0,0,0,.08), rgba(0,0,0,.45))` | 785-790 |
| جای عکس در کارت | `grid-column:2` (ستون دوم grid) | 2351 |
| small نمونه | `position:absolute; left:10px; bottom:10px; z-index:2; padding:4px 8px; background:rgba(255,173,18,.92); radius:999px; font-size:.70rem` | 596-605 + 794-799 |

### افکت‌ها — HEAD

- **Hover کارت:** border طلایی + background گرادیان + translateY(-1px) — transition .18s
- **Hover تصویر:** **Zoom واقعی وجود ندارد** — صریحاً هیچ `transform:scale` برای hover در HEAD نیست. فقط `transform:scale(1.01)` ثابت روی img (از 782) — نه hover
- **Zoom تصویر:** **وجود ندارد** در HEAD — نه در ابرو، نه در ۳ خدمت دیگر
- **Transform:** فقط `translateY(-1px)` کارت + `scale(1.01)` ثابت img
- **Overlay:** `::after` گرادیان مشکی 90deg — وجود دارد
- **Border تغییر رنگ:** بله — hover `rgba(255,173,18,.62)`
- **Shadow:** ندارد در HEAD (فقط در نسخه local با final override بود)
- **Selected state:** `is-selected` کلاس + `:has(input:checked)` — border طلایی
- **Badge:** `em` داخل `bti-style-info` — `grid-column:2; width:fit-content; padding:5px 8px; radius:999px; bg:var(--bti-gold); font:.72rem; font-weight:950` — برای ابرو فقط `key=='giso_suggested'`
- **متن نمونه مدل:** `small` داخل `bti-brow-sample` — absolute left 10px bottom 10px
- **انیمیشن:** فقط transition border/background/transform — بدون keyframe خاص برای کارت

### JS مرتبط
- `buti_ai.js:134-141` — هر `.bti-style-choice` → `input[type=radio]` change → حذف `is-selected` از همه، اضافه به انتخاب شده — برای هر ۴ خدمت یکسان

### نحوه دریافت و نمایش عکس
- Backend: `giso/buti_ai/eyebrow/options.py` → `EYEBROW_STYLES` ۵ کلید
- Template: `url_for('buti_ai.static', filename='brows/' ~ key ~ '.jpg')` — `alt="نمونه {{ item.label }}"`

---

## ۲. هر سه خدمت جداگانه — مقایسه با ابرو (HEAD)

### مسیر مشترک ۳ خدمت
- Template: `giso/buti_ai/templates/buti_ai/generic_service_wizard.html` خط 54-70 — CSS `v=24`
- CSS: همان `buti_ai.css` — همان `bti-style-choice` + `bti-brow-sample`
- JS: همان `buti_ai.js`
- عکس: `giso/buti_ai/static/services/{service}/{key}.jpg`

### Nail — `nail`
- Template خط 54: `label.bti-style-choice is-style-{key}` + `span.bti-style-info` (icon+copy+em loop.first) + `span.bti-brow-sample > img jpg + small`
- CSS: **دقیقاً همان** 132px/86px/106px — چون selector مشترک است، هیچ override جدا برای nail نیست
- Badge: `em` بدون کلاس → "انتخاب امن" فقط `loop.first` — استایل همان em پایه
- small: همان "نمونه مدل" left 10px bottom 10px
- **نتیجه:** UI 100% یکسان با ابرو

### Lip — `lip_shading`
- دقیقاً مثل Nail — همین template، همین CSS، همین ساختار
- مدل‌ها: ۵ تا (natural_shading, natural_contour, peach_nude, soft_pink_tint, dark_tone_neutralize)
- **نتیجه:** UI 100% یکسان

### Hair Color — `hair_color`
- دقیقاً مثل Nail و Lip
- مدل‌ها: ۵ تا (caramel_balayage, chocolate_nescafe, face_frame, natural_highlight, ash_olive)
- **نتیجه:** UI 100% یکسان

---

## ۳. جدول مقایسه دقیق و عددی — HEAD f9a7fb0

| مورد | Eyebrow (مرجع) | Nail | Lip | Hair Color | تفاوت | منبع inherited |
|---|---|---|---|---|---|---|
| **ساختار HTML** | `label.bti-style-choice > input[radio] + span.bti-style-info (icon+copy+em) + span.bti-brow-sample > img + small` | **یکسان** — فقط `sample_dir` متفاوت | یکسان | یکسان | **محتوایی** | template |
| **کلاس کارت** | `bti-style-choice is-style-{key}` | یکسان | یکسان | یکسان | یکسان | - |
| **عرض کارت** | 100% داخل `bti-shell width:min(1120px, calc(100% - 32px))` | یکسان | یکسان | یکسان | یکسان | shell |
| **ارتفاع کارت** | `min-height:106px` (نهایی 2337) — پایه 142px → 138px → 172px → 116px → **106px نهایی** | یکسان 106px | یکسان | یکسان | یکسان | buti_ai.css:2337 |
| **Padding کارت** | `12px` | یکسان | یکسان | یکسان | یکسان | 2342 |
| **Margin کارت** | 0 + gap 10px از `bti-style-list` | یکسان | یکسان | یکسان | یکسان | 347 |
| **Gap داخلی کارت** | `12px` (بین متن و عکس) | یکسان | یکسان | یکسان | یکسان | 2341 |
| **Border کارت** | `1px solid rgba(255,255,255,.09)` | یکسان | یکسان | یکسان | یکسان | 538 |
| **Border Radius کارت** | `18px` | یکسان | یکسان | یکسان | یکسان | 539 |
| **تصویر — کلاس** | `bti-brow-sample` | یکسان | یکسان | یکسان | یکسان | - |
| **عرض تصویر کانتینر** | `132px` (width) + `flex:none` + `grid-column:2` | یکسان 132px | یکسان | یکسان | یکسان | 2352 |
| **ارتفاع تصویر کانتینر** | `86px` height, `86px` min-height | یکسان | یکسان | یکسان | یکسان | 2353-2354 |
| **Aspect Ratio** | ندارد — از height ثابت | یکسان | یکسان | یکسان | یکسان | - |
| **Object Fit img** | `cover` | یکسان | یکسان | یکسان | یکسان | 2360 |
| **Object Position img** | `center 34%` | یکسان | یکسان | یکسان | یکسان | 2361 |
| **Border Radius عکس کانتینر** | `16px` | یکسان | یکسان | یکسان | یکسان | 590 |
| **Border Radius img** | `15px` | یکسان | یکسان | یکسان | یکسان | 778 |
| **Overflow** | `hidden` | یکسان | یکسان | یکسان | یکسان | 587 |
| **Padding کانتینر** | `0` | یکسان | یکسان | یکسان | یکسان | 766 |
| **Background کانتینر** | `radial-gradient(...) + linear-gradient(135deg, #1b1512, #0b0b0b)` | یکسان | یکسان | یکسان | یکسان | 591-593 |
| **Overlay** | `::after linear-gradient(90deg, rgba(0,0,0,.08), rgba(0,0,0,.45))` | یکسان | یکسان | یکسان | یکسان | 785-790 |
| **Filter img** | `saturate(.96) contrast(1.04) brightness(.94)` | یکسان | یکسان | یکسان | یکسان | 781 |
| **عرض img** | `100%` | یکسان | یکسان | یکسان | یکسان | 777 |
| **ارتفاع img** | `86px` + `min-height:86px` | یکسان | یکسان | یکسان | یکسان | 2359-2360 |
| **Hover Zoom** | **وجود ندارد** — فقط `scale(1.01)` ثابت | وجود ندارد | وجود ندارد | وجود ندارد | یکسان — هیچ کدام zoom ندارند | 782 |
| **Selected Transform** | **وجود ندارد** — فقط border | یکسان | یکسان | یکسان | یکسان | - |
| **Badge** | `em` → "انتخاب امن" فقط `key=='giso_suggested'` — `grid-column:2; padding:5px 8px; bg:var(--bti-gold); .72rem` | `em` → "انتخاب امن" فقط `loop.first` — **همان استایل** | یکسان | یکسان | **محتوایی** — منطق badge متفاوت ولی استایل یکسان | 571-579 |
| **متن نمونه مدل** | `small` → "نمونه مدل" — `left:10px; bottom:10px; z-index:2; padding:4px 8px; bg:rgba(255,173,18,.92); .70rem` | یکسان | یکسان | یکسان | یکسان | 596-605 |
| **فاصله‌ها** | gap 12px کارت، gap 12px info، gap 10px list | یکسان | یکسان | یکسان | یکسان | - |
| **Mobile (820px)** | `grid-template-columns:1fr; .bti-brow-sample width:100%; height:126px; min-height:126px` | یکسان | یکسان | یکسان | یکسان | 2521-2528 |

---

## ۴. تفاوت محتوایی vs ساختاری — HEAD

### تفاوت محتوایی (مشکل نیست)

- عکس متفاوت: ابرو `brows/natural.jpg`، ناخن `services/nail/nude_minimal.jpg` — طبیعی
- نام مدل متفاوت: "طبیعی/میکروبلیدینگ" vs "نود مینیمال/فرنچ کلاسیک" vs "کارامل بالیاژ" — طبیعی
- توضیح متفاوت: summary متفاوت — طبیعی
- تعداد مدل‌ها: هر ۴ خدمت ۵ مدل — یکسان
- Badge منطق: ابرو `giso_suggested`، ۳ خدمت `loop.first` — محتوایی، استایل یکسان
- sample_dir: `brows/` vs `services/nail/` etc — محتوایی

### تفاوت UI / ساختاری (باید گزارش شود)

**در HEAD هیچ تفاوت ساختاری وجود ندارد.**

- اندازه کارت: 106px همه
- عرض تصویر: 132px همه
- ارتفاع تصویر: 86px همه
- Padding/Gap/Border/Radius/Background/Transition/Hover/Selected: همه یکسان
- Hover Zoom: هیچ کدام ندارند — یکسان
- Responsive: همه 1060/820/620 یکسان

---

## ۵. آیا Generic واقعاً 100٪ UI ابرو را منتقل کرده؟

**فایل:** `giso/buti_ai/templates/buti_ai/generic_service_wizard.html`

- **آیا دقیقاً همان ساختار را reuse کرده؟** **بله — 100٪**
  - همان `bti-style-choice`, `bti-style-info`, `bti-style-row-icon`, `bti-style-row-copy`, `bti-brow-sample`, `small`, `em`
  - همان `bti-change-panel`, `bti-upload-layout-redesigned`, JS `is-selected`
- **فقط بعضی کلاس‌ها؟** نه — همه کلاس‌ها
- **آیا نام کلاس `bti-brow-sample` باعث وابستگی شده؟** نام `brow` برای ناخن/مو/لب از نظر معنایی گمراه‌کننده است، ولی از نظر فنی هیچ وابستگی منطقی ندارد — فقط نام است. در HEAD هیچ `is-wide-png` یا منطق خاص ابرو در CSS برای این کلاس وجود ندارد — پس وابستگی وجود ندارد
- **آیا بهتر است به `bti-style-sample` تبدیل شود؟** از نظر معماری تمیز، بله — پیشنهاد می‌شود به `bti-style-sample` یا `bti-service-sample` عمومی شود تا نام با همه خدمات هماهنگ باشد — ولی **cosmetic** است، نه لازم برای یکسان‌سازی UI، چون همین الان UI یکسان است
- **آیا تغییر لازم است یا cosmetic؟** **فقط cosmetic** — برای خوانایی و Reuse بهتر — نه برای رفع تفاوت UI، چون تفاوتی نیست

---

## ۶. عکس‌های نمونه — HEAD

| خدمت | مسیر | فرمت | ابعاد واقعی | نسبت |
|---|---|---|---|---|
| ابرو natural.jpg | `static/brows/natural.jpg` | JPG | 512×341 | 1.50:1 |
| ابرو powder.jpg | `static/brows/powder.jpg` | JPG | 512×341 | 1.50:1 |
| ناخن nude_minimal.jpg | `services/nail/nude_minimal.jpg` | JPG | 520×360 | 1.44:1 |
| ناخن baby_boomer.jpg | `services/nail/baby_boomer.jpg` | JPG | 520×360 | 1.44:1 |
| مو caramel_balayage.jpg | `services/hair_color/caramel_balayage.jpg` | JPG | 520×360 | 1.44:1 |
| لب natural_shading.jpg | `services/lip_shading/natural_shading.jpg` | JPG | 520×360 | 1.44:1 |

- **فرمت:** همه JPG در HEAD (PNG/WEBP فقط در working dir محلی قبلی بود که پاک شد)
- **ابعاد:** ابرو 512×341، ۳ خدمت دیگر 520×360 — تقریباً یکسان (اختلاف 8px عرض، 19px ارتفاع)
- **نسبت یکسان؟** تقریباً بله — 1.50 vs 1.44 — اختلاف 0.06
- **object-fit:** همه `cover` — پس crop کمی دارد، ولی چون نسبت‌ها نزدیک است، تفاوت ظاهری ندارد
- **object-position:** همه `center 34%` (یا 32% در override قدیمی، نهایی 34%) — یکسان
- **آیا خود تصاویر باعث حس تفاوت UI شده‌اند؟** خیر — چون ابعاد و نسبت تقریباً یکسان و object-fit/position یکسان است — کارت‌ها یکسان دیده می‌شوند

---

## ۷. Responsive دقیق — HEAD

| Breakpoint | Eyebrow | Nail / Lip / Hair Color | تفاوت |
|---|---|---|---|
| **Desktop >1060px** | کارت `grid 1fr 132px`, عکس 132×86, `min-height:106px` | یکسان | یکسان |
| **1060px** | `.bti-eyebrow-stage-separated grid 1fr` — فقط layout کلی، کارت‌ها همچنان `1fr 132px` | یکسان | یکسان |
| **900px** | هیچ rule خاص برای کارت مدل | یکسان | یکسان |
| **820px** | `.bti-style-choice grid-template-columns:1fr`, `.bti-brow-sample width:100% height:126px min-height:126px`, `.bti-brow-sample img width:100% height:126px` — ستونی می‌شود | یکسان — همین media query برای generic هم اعمال می‌شود (selector مشترک) | یکسان |
| **620px** | `.bti-style-info grid 44px 1fr`, `.bti-style-choice min-height:auto` | یکسان | یکسان |
| **Mobile <620px** | کارت min-height auto، عکس 100%×126px | یکسان | یکسان |

**خلاصه:** در HEAD، هیچ breakpoint جداگانه برای ابرو vs ۳ خدمت وجود ندارد — همه از یک CSS مشترک استفاده می‌کنند.

---

## ۸. نتیجه واضح — HEAD

**گزینه A — کاملاً یکسان هستند**

**چرا A:**
- HTML ساختار: `bti-style-choice` + `bti-brow-sample` + `img + small + em` — یکسان
- CSS کارت: 106px, 12px padding, 12px gap, 18px radius, 1px border — یکسان
- CSS تصویر: 132px width, 86px height, cover, center 34%, 16px radius, overlay gradient — یکسان
- Hover: border طلایی + gradient + translateY(-1px) — یکسان، **zoom ندارد** در هیچ کدام
- Selected: is-selected + :has(checked) — یکسان
- Badge/small: em + small — یکسان (فقط منطق انتخاب badge متفاوت محتوایی)
- Responsive: 1060/820/620 — یکسان
- تصاویر: ابعاد و نسبت تقریباً یکسان — حس تفاوت ایجاد نمی‌کند

---

## ۹. اگر تفاوت وجود داشت — راهکار (در HEAD تفاوتی نیست، ولی برای بهبود معماری)

### تفاوت محتوایی Badge منطق

```
فایل:
giso/buti_ai/templates/buti_ai/eyebrow_wizard.html:60 vs generic_service_wizard.html:60

کلاس:
em (badge انتخاب امن)

وضعیت ابرو:
{% if key == 'giso_suggested' %}<em>انتخاب امن</em>{% endif %}

وضعیت ۳ خدمت:
{% if loop.first %}<em>انتخاب امن</em>{% endif %}

راهکار:
اگر می‌خواهی منطق 100% یکسان باشد، هر دو را به یک منطق تبدیل کن — مثلاً همیشه giso_suggested یا همیشه loop.first
یا برای generic هم giso_suggested را تعریف کن در service_catalog.py

اثر: هر ۳ خدمت — محتوایی، نه UI
```

### بهبود معماری — نام کلاس

```
فایل:
giso/buti_ai/static/buti_ai.css + هر دو template

کلاس:
.bti-brow-sample

وضعیت فعلی:
نام brow برای nail/lip/hair گمراه‌کننده

وضعیت پیشنهادی:
.bti-style-sample, .bti-brow-sample { ... } — alias برای سازگاری
یا rename به bti-style-sample

راهکار:
.bti-style-sample را کلاس اصلی کن، bti-brow-sample را alias نگه دار:
.bti-style-sample,
.bti-brow-sample { ... }

اثر: هر ۴ خدمت — cosmetic، برای Reuse بهتر — لازم نیست برای یکسان‌سازی UI
```

---

## ۱۰. اصل معماری Reuse > Extend > New

- **Reuse:** همین الان رعایت شده — یک CSS (`buti_ai.css`) و یک ساختار HTML (`bti-style-choice` + `bti-brow-sample`) برای هر ۴ خدمت
- **Extend:** نیازی نیست — چون همین reuse کافی است
- **New نساز:** برای Nail/Lip/Hair Template جدا نساخته — درست — همین `generic_service_wizard.html` کافی است

**نباید تغییر کند:**
- Backend `generic_service.py`, `service_catalog.py`, `final_design.py`
- Upload/Final routes
- AI logic
- JS `buti_ai.js`

**فقط UI انتخاب مدل:** همین الان یکسان است — نیازی به تغییر نیست

---

## ۱۱. پیشنهاد نهایی — Eyebrow = Nail = Lip = Hair Color

### در HEAD فعلی f9a7fb0:

**بهترین روش: هیچ تغییری لازم نیست — UI همین الان یکسان است.**

اگر می‌خواهی معماری تمیزتر شود (optional):

- **فایل‌هایی که می‌توانند تغییر کنند (cosmetic):**
  1. `giso/buti_ai/static/buti_ai.css` — اضافه alias:
     ```css
     .bti-style-sample,
     .bti-brow-sample { /* همان استایل فعلی */ }
     ```
  2. `giso/buti_ai/templates/buti_ai/eyebrow_wizard.html` + `generic_service_wizard.html` — به تدریج `bti-brow-sample` → `bti-style-sample`
  3. `giso/buti_ai/service_catalog.py` — اگر می‌خواهی badge منطق یکسان شود، برای ۳ خدمت هم `giso_suggested` تعریف کن

- **چه چیزهایی نباید تغییر کنند:**
  - هیچ Backend، Flow، AI، Upload/Final
  - هیچ Template جدا برای هر خدمت
  - هیچ CSS جدا

- **آیا Template مشترک کافی است؟** بله — همین `generic_service_wizard.html` برای ۳ خدمت + `eyebrow_wizard.html` برای ابرو — ولی حتی می‌توان eyebrow را هم به generic برد (چون الان ساختار 100% یکسان است) — ولی فعلاً همین جدا بودن هم مشکلی ندارد چون UI یکسان است

- **آیا CSS مشترک کافی است؟** بله — همین `buti_ai.css` با یک selector مشترک کافی است

- **آیا JS لازم است تغییر کند؟** خیر — همین `buti_ai.js` کافی است

### آیا واقعاً نیاز به تغییر کد هست؟

**خیر — در HEAD فعلی f9a7fb0، هیچ تغییری لازم نیست برای یکسان شدن UI انتخاب مدل.**

- گزینه A تایید می‌شود
- اگر بخواهی در آینده Zoom یا افکت جدید اضافه کنی، فقط یک جا (`buti_ai.css: .bti-brow-sample img`) تغییر بده — روی هر ۴ خدمت اثر می‌گذارد — Reuse رعایت می‌شود

---

**یادداشت:** در working dir قبلی (قبل از reset) یک نسخه local با `is-wide-png` و `420px` و `scale(1.14)` وجود داشت که باعث گزینه B شده بود — آن نسخه local بود، نه HEAD — در HEAD فعلی آن overrideها وجود ندارد، پس گزینه A است.

**پایان Audit — هیچ فایلی تغییر نکرد — فقط گزارش `mirror_model_audit.md` تولید شد**
