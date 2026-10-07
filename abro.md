# گزارش ساده — آینه ابرو گیسو و ۳ خدمت دیگر

> بررسی فقط UI انتخاب مدل — بدون تغییر کد

## ۱. آینه ابرو گیسو — قسمت انتخاب مدل

**فایل:** `giso/buti_ai/templates/buti_ai/eyebrow_wizard.html` + `giso/buti_ai/static/buti_ai.css` + `giso/buti_ai/eyebrow/options.py`

### چیدمان نکات مدل‌ها
- لیست عمودی: `div.bti-style-list` با `display:grid; gap:10px`
- هر مدل یک `label.bti-style-choice` که کل کارت قابل کلیک است (radio مخفی)
- داخل کارت: `display:flex; gap:14px; min-height:172px; padding:14px; border-radius:18px`
- سمت راست (RTL): اطلاعات متن، سمت چپ: عکس نمونه — در موبایل `flex-direction:column` می‌شود

### نمونه عکس
- فایل‌ها: `giso/buti_ai/static/brows/*.png` + `*.webp` — مثل `natural.png`, `microblading.png`
- اندازه: `420px عرض × 168px ارتفاع` — کلاس `is-wide-png`
- تگ `picture`: اول `webp` لود، fallback `png`
- افکت: hover → `scale(1.14)` + border طلایی، انتخاب شده → `scale(1.10)`

### اندازه کاردها
- کارت: `min-height:172px`, `padding:14px`, `radius:18px`
- بخش متن: `flex:1`, grid `48px (آیکون) + 1fr (متن)`
- بخش عکس: `flex:0 0 420px; width:420px; min-height:168px; max-height:188px`
- موبایل: عکس `width:100%; min-height:200px`

### متن کجا قرار گرفته
- `bti-style-info` → آیکون + `bti-style-row-copy` → `b` عنوان + `small` خلاصه + زیرش `em.bti-sample-badge` → "نمونه X"
- اگر `giso_suggested` باشد، بج "انتخاب امن"
- شدت تغییر در پنل جدا: خیلی طبیعی / کمی تغییر / تغییر واضح‌تر

### تم هر کارد
- پس‌زمینه: `#101010` تیره
- بوردر: `rgba(255,255,255,.09)`
- هاور: `border: rgba(255,173,18,.62)` طلایی + گرادیان + `translateY(-1px)`
- بج‌ها: `#ffad12` طلایی، متن مشکی، `radius:999px`
- تم کلی: `bti-page` → بک‌گراند `#070707` با گرادیان طلایی کم

## ۲. آیا ۳ خدمت دیگر همین قالب را دارند؟

**فایل مشترک:** `giso/buti_ai/templates/buti_ai/generic_service_wizard.html`
**کاتالوگ:** `service_catalog.py` → ابرو، ناخن، رنگ مو، لب

| مورد | ابرو | ناخن / رنگ مو / لب |
|---|---|---|
| wizard | `eyebrow_wizard.html` | `generic_service_wizard.html` |
| کارت | `is-style-{key}` + `is-wide-png` | همین، اما عکس بدون `is-wide-png` |
| عکس | `brows/{key}.png + webp`, 420×168, picture | `services/{service}/{key}.jpg`, jpg ساده, "نمونه مدل" |
| متن | عنوان + خلاصه + بج "نمونه X" + "انتخاب امن" | عنوان + خلاصه + "انتخاب امن" برای اولین آیتم |
| شدت | خیلی طبیعی / کمی تغییر / واضح‌تر | خیلی طبیعی / متوسط / واضح‌تر |
| آپلود | `brows/upload_face_only.jpg` | `services/{service}/upload_sample.jpg` + راهنما متفاوت |
| تم | مشکی طلایی | دقیقاً همین تم مشکی طلایی |

**نتیجه:** بله، ۳ خدمت دیگر دقیقاً همین قالب را دارند — فقط عکس‌ها و متن‌ها عوض شده.

### ۳ خدمت دیگر
- **ناخن** (`nail/final_design.py`): نود مینیمال 💅, فرنچ کلاسیک 🤍, بیبی‌بومر 🌸, کروم ✨, کت‌آی 🐈 — عکس‌ها `services/nail/*.jpg`
- **رنگ مو** (`hair_color`): کارامل بالیاژ, چاکلت نسکافه, فیس‌فریم, هایلایت طبیعی — عکس‌ها `services/hair_color/*.jpg`
- **لب** (`lip`): شیدینگ طبیعی, کانتور, تینت صورتی, نود هلویی — عکس‌ها `services/lip_shading/*.jpg`

## ۳. مشکلات کوچک
1. ابرو PNG+WEBP دارد، بقیه فقط JPG — بهتر همه WEBP داشته باشند
2. بج "نمونه X" فقط در ابرو، در بقیه "نمونه مدل"
3. "انتخاب امن" در ابرو فقط برای giso_suggested، در بقیه برای اولین مدل
4. ارتفاع کارت 172px min اما خلاصه‌ها طول متفاوت — کارت‌ها ناهمسان
5. تم تیره برای عکس‌های روشن ناخن/مو کنتراست زیاد

## ۴. پیشنهاد یکسان‌سازی
- همه عکس‌ها 420×168 PNG+WEBP مثل ابرو
- بج یکسان: "نمونه {label}" + "انتخاب امن"
- `is-wide-png` برای همه
- شدت تغییر یکسان

**خلاصه:** کارت ابرو افقی 172px با متن راست و عکس 420×168 چپ، بج طلایی، زوم هاور. ۳ خدمت دیگر همین قالب را از `generic_service_wizard.html` دارند — فقط عکس JPG و بج فرق دارد. یکسان‌سازی عکس و بج = هر ۴ خدمت یک شکل.
