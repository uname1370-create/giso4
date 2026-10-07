# گزارش دقیق — انتخاب مدل ابرو و مقایسه با ۳ خدمت دیگر

## سایت الان بالا هست — 5001 → 200 OK — LIVE PREVIEW

---

## ۱. آینه ابرو گیسو — قسمت انتخاب مدل

**مسیر فایل‌ها:**
- `giso/buti_ai/templates/buti_ai/eyebrow_wizard.html` خط 40-75
- `giso/buti_ai/eyebrow/options.py` → ۵ مدل
- `giso/buti_ai/static/buti_ai.css` خط 3091-3213

### ساختار هر مدل (از options.py)

| کلید | عنوان | آیکون | خلاصه |
|---|---|---|---|
| `natural` | طبیعی و نچرال | 🌿 | تغییر کم، مرتب و شیک |
| `microblading` | میکروبلیدینگ ظریف | ✍️ | تاربه‌تار و طبیعی‌تر |
| `powder` | شیدینگ پودری | ☁️ | پرتر و منظم‌تر |
| `combination` | کامبینیشن | ✨ | تارهای ظریف + سایه ملایم |
| `giso_suggested` | گیسو پیشنهاد بدهد | 🪞 | عکس بده تا پیشنهاد کند |

هر مدل: `label`, `icon`, `summary`, `why`, `do[4]`, `avoid[3]`

### ساختار HTML کارت

```html
<label class="bti-style-choice is-style-{key} is-selected">
  <input type="radio" name="style" value="{key}" hidden>
  <span class="bti-style-info">
    <span class="bti-style-row-icon">{icon}</span>
    <span class="bti-style-row-copy">
      <b>{label}</b>
      <small>{summary}</small>
      <em class="bti-sample-badge">نمونه {label}</em>
      <em class="bti-safe-badge">انتخاب امن</em>
    </span>
  </span>
  <span class="bti-brow-sample is-wide-png">
    <picture>
      <source srcset="brows/{key}.webp" type="image/webp">
      <img src="brows/{key}.png" width=420 height=168 loading=lazy>
    </picture>
  </span>
</label>
```

### عکس چطوری
- مسیر: `static/brows/*.png + webp`
- اندازه کانتینر: `420px عرض × 168px ارتفاع`, `is-wide-png`
- عکس: `width:100%; height:150px; object-fit:contain`
- بک: `radial-gradient طلایی کم + #0e0e0e`, بوردر `rgba(255,255,255,.08)`, radius 15px
- picture: اول webp، fallback png

### انیمیشن چطوریه
- کارت: `transition: all .22s ease`, عادی `#101010`, هاور `border: rgba(255,173,18,.62)` + `linear-gradient طلایی کم` + `translateY(-1px)`
- عکس: `transition: transform .35s cubic-bezier(.4,0,.2,1)`, هاور `scale(1.14)`, انتخاب `scale(1.10)` + `box-shadow طلایی`
- موبایل <920px: `flex-direction:column`, عکس `100%` عرض

### کاربر چطوری می‌بینه
- ۵ کارت عمودی، راست متن، چپ عکس
- هاور: کارت بالا می‌آید، بوردر طلایی، عکس زوم
- کلیک هر جای کارت = انتخاب، سایه طلایی
- پایین: شدت تغییر ۳ گزینه + دکمه مرحله بعد

---

## ۲. بقیه خدمات — مثل ابرو هستند؟

**فایل مشترک:** `generic_service_wizard.html`

| خدمت | مدل‌ها | عکس‌ها |
|---|---|---|
| ناخن | نود مینیمال 💅, فرنچ 🤍, بیبی‌بومر 🌸, کروم ✨, کت‌آی 🐈 | `services/nail/*.jpg` |
| رنگ مو | کارامل بالیاژ, چاکلت نسکافه, فیس‌فریم... | `services/hair_color/*.jpg` |
| لب | شیدینگ طبیعی, کانتور, تینت... | `services/lip_shading/*.jpg` |

**ساختار کارت:** همین `bti-style-choice`, همین `bti-style-info`, همین `bti-brow-sample` (بدون is-wide-png), همین انیمیشن

**تفاوت‌ها:**
- عکس: JPG ساده، بدون webp، بدون is-wide-png، small "نمونه مدل" زیر عکس
- بج: فقط "انتخاب امن" برای اولین کارت، بدون "نمونه X"
- شدت: "تغییر متوسط" به جای "کمی تغییر"

**نتیجه:** بله، ۹۵٪ مثل ابرو — فقط عکس و بج فرق دارد. یکسان‌سازی = هر ۴ خدمت یک شکل.

## ۳. گزارش ساده
- کارت ابرو: 172px ارتفاع، متن راست، عکس چپ 420×168 PNG/WEBP، بج طلایی، زوم هاور
- ۳ خدمت دیگر: همین قالب، همین اندازه، همین انیمیشن، تم مشکی طلایی — فقط JPG و بج ساده‌تر
