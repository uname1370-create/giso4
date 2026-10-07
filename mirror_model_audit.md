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
- **عکس:** `giso/buti_ai/static/brows/{key}.jpg`

### کارت مدل — استخراج نهایی (آخرین rule بدون !important)

| ویژگی | مقدار نهایی HEAD | منبع |
|---|---|---|
| کلاس | `bti-style-choice is-style-{key} is-selected` | eyebrow_wizard.html:54 |
| display | `grid` | buti_ai.css:2338 |
| grid-template-columns | `minmax(0, 1fr) 132px` | 2339 |
| min-height | `106px` | 2340 |
| padding | `12px` | 2342 |
| gap | `12px` | 2341 |
| border | `1px solid rgba(255,255,255,.09)` | 538 |
| border-radius | `18px` | 539 |
| background | `#101010` | 540 |
| transition | `border-color .18s, background .18s, transform .18s` | 541 |
| hover transform | `translateY(-1px)` | 551 |
| hover border | `rgba(255,173,18,.62)` | 549 |
| selected | `:has(input:checked)` + `.is-selected` | 548 + JS |

### عکس نمونه — HEAD

| ویژگی | مقدار نهایی | منبع |
|---|---|---|
| کلاس | `bti-brow-sample` | 64 |
| width | `132px` | 2352 |
| height | `86px` | 2353 |
| min-height | `86px` | 2354 |
| object-fit | `cover` | 2360 |
| object-position | `center 34%` | 2361 |
| border-radius | `16px` کانتینر، `15px` img | 590, 778 |
| overflow | `hidden` | 587 |
| background | radial + linear | 591-593 |
| filter | `saturate(.96) contrast(1.04) brightness(.94)` | 781 |
| overlay | `::after linear-gradient(90deg, rgba(0,0,0,.08), rgba(0,0,0,.45))` | 785-790 |
| small | `left:10px bottom:10px absolute` | 794-799 |

### افکت‌ها — HEAD

- Hover کارت: border طلایی + gradient + translateY(-1px)
- Hover تصویر: **Zoom واقعی وجود ندارد** — صریحاً هیچ scale hover نیست، فقط scale(1.01) ثابت
- Overlay: دارد
- Badge: `em` grid-column:2 padding 5px 8px bg var(--bti-gold) .72rem
- نمونه مدل: small absolute
- انیمیشن: فقط transition

---

## ۲. سه خدمت جداگانه

### Nail / Lip / Hair Color
- Template: `generic_service_wizard.html` خط 54-70 — v=24
- CSS: همان `buti_ai.css` — همان 132×86
- JS: همان
- عکس: `services/{service}/{key}.jpg`
- **نتیجه:** هر سه 100% یکسان با ابرو

---

## ۳. جدول مقایسه دقیق

| مورد | Eyebrow | Nail | Lip | Hair Color | تفاوت |
|---|---|---|---|---|---|
| ساختار HTML | `label.bti-style-choice > input + span.bti-style-info + span.bti-brow-sample > img + small` | یکسان | یکسان | یکسان | محتوایی |
| کلاس کارت | `bti-style-choice` | یکسان | یکسان | یکسان | یکسان |
| عرض کارت | 100% | یکسان | یکسان | یکسان | یکسان |
| ارتفاع کارت | 106px | یکسان | یکسان | یکسان | یکسان |
| Padding | 12px | یکسان | یکسان | یکسان | یکسان |
| Gap | 12px | یکسان | یکسان | یکسان | یکسان |
| Border | 1px solid rgba(255,255,255,.09) | یکسان | یکسان | یکسان | یکسان |
| Radius | 18px | یکسان | یکسان | یکسان | یکسان |
| تصویر عرض | 132px | یکسان | یکسان | یکسان | یکسان |
| تصویر ارتفاع | 86px | یکسان | یکسان | یکسان | یکسان |
| Aspect | ندارد | یکسان | یکسان | یکسان | یکسان |
| Object Fit | cover | یکسان | یکسان | یکسان | یکسان |
| Object Position | center 34% | یکسان | یکسان | یکسان | یکسان |
| Radius عکس | 16px/15px | یکسان | یکسان | یکسان | یکسان |
| Overlay | gradient 90deg | یکسان | یکسان | یکسان | یکسان |
| Filter | saturate/contrast/brightness | یکسان | یکسان | یکسان | یکسان |
| Hover Zoom | **وجود ندارد** | وجود ندارد | وجود ندارد | وجود ندارد | یکسان |
| Selected | border طلایی | یکسان | یکسان | یکسان | یکسان |
| Transform | translateY(-1px) | یکسان | یکسان | یکسان | یکسان |
| Badge | em انتخاب امن | یکسان (loop.first vs giso_suggested) | یکسان | یکسان | محتوایی |
| نمونه مدل | small left10 bottom10 | یکسان | یکسان | یکسان | یکسان |
| فاصله‌ها | 12px/10px | یکسان | یکسان | یکسان | یکسان |
| Mobile 820px | 1fr width100% 126px | یکسان | یکسان | یکسان | یکسان |

---

## ۴. محتوایی vs ساختاری

- محتوایی: عکس، نام، توضیح، تعداد (۵)، badge منطق — مشکل نیست
- ساختاری: **هیچ تفاوت ساختاری در HEAD وجود ندارد**

---

## ۵. Generic 100% UI ابرو را منتقل کرده؟

- **بله — 100%** — `generic_service_wizard.html` دقیقاً همان ساختار ابرو را reuse کرده
- `bti-brow-sample` نامش brow است ولی وابستگی ندارد — فقط نام — cosmetic
- بهتر است به `bti-style-sample` تبدیل شود؟ cosmetic، برای خوانایی — لازم نیست

---

## ۶. عکس‌های نمونه

| خدمت | مسیر | فرمت | ابعاد | نسبت |
|---|---|---|---|---|
| ابرو | `brows/natural.jpg` | JPG | 512×341 | 1.5 |
| ناخن | `services/nail/nude_minimal.jpg` | JPG | 520×360 | 1.44 |
| مو | `services/hair_color/caramel_balayage.jpg` | JPG | 520×360 | 1.44 |
| لب | `services/lip_shading/natural_shading.jpg` | JPG | 520×360 | 1.44 |

- فرمت همه JPG، ابعاد تقریباً یکسان، object-fit cover یکسان، position center 34% یکسان — حس تفاوت ایجاد نمی‌کند

---

## ۷. Responsive

| Breakpoint | Eyebrow | Nail/Lip/Hair | تفاوت |
|---|---|---|---|
| Desktop >1060 | 1fr 132px 106px | یکسان | یکسان |
| 1060px | grid 1fr | یکسان | یکسان |
| 900px | هیچ | یکسان | یکسان |
| 820px | 1fr width100% 126px | یکسان | یکسان |
| 620px | 44px 1fr auto | یکسان | یکسان |

---

## ۸. نتیجه

**گزینه A — کاملاً یکسان هستند**

---

## ۹. راهکار

در HEAD نیازی به تغییر کد نیست. برای بهبود معماری (optional):

```
فایل: buti_ai.css
کلاس: .bti-brow-sample
وضعیت فعلی: نام brow گمراه‌کننده
راهکار: alias .bti-style-sample, .bti-brow-sample { ... }
اثر: هر ۴ خدمت — cosmetic
```

---

## ۱۰. Reuse > Extend > New

- Reuse رعایت شده — یک CSS/Template برای هر ۴ خدمت
- New نساز — درست
- Backend/Flow/AI/Upload تغییر نده — رعایت شده

---

## ۱۱. پیشنهاد نهایی

**هیچ تغییری لازم نیست — Eyebrow = Nail = Lip = Hair Color از نظر UI انتخاب مدل**

- فایل‌های تغییر: هیچ (optional cosmetic alias)
- کلاس عمومی: می‌توان bti-style-sample alias ساخت
- Template مشترک کافی است: بله
- CSS مشترک کافی است: بله
- JS تغییر لازم؟ خیر

**پایان — هیچ فایلی تغییر نکرد جز گزارش**
