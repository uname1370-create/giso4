# سناریوی محصول/فنی: گسترش آینه زیبایی گیسو پس از ابرو

آخرین به‌روزرسانی: 2026-09-29 — Asia/Tehran
Branch ثابت Arena: `arena/01a0e0b8-giso4`

این سند برای Project Memory و handoff به ایجنت بعدی است. هدفش این است که ایجنت بعدی دقیقاً بداند:

- چه کاری تا الان انجام شده است؛
- لیست نهایی خدمات آینه زیبایی چیست؛
- کدام ۳ خدمت بعد از ابرو باید ساخته شوند؛
- هر خدمت چه مدل‌هایی دارد؛
- خروجی قبل/بعد واقعاً چگونه باید ساخته و validate شود؛
- کارها در چه گراف/ترتیبی باید اجرا شوند؛
- چه چیزهایی نباید خراب یا جابه‌جا شوند.

---

## 1. وضعیت فعلی قبل از شروع ۳ خدمت جدید

### کدهای فعلی مربوط به ابرو

آخرین commitهای مهم روی همین branch:

```text
1241f4a Preserve final eyebrow image pixels
  - خروجی نهایی AI ابرو به PNG تغییر کرد تا بیرون از mask به‌خاطر فشرده‌سازی JPG دست نخورد.
  - فایل ذخیره‌شده نهایی دوباره خوانده و validate می‌شود.
  - اگر بعد از ذخیره، ROI ابرو تغییر واقعی نداشته باشد یا بیرون mask دست بخورد، خروجی AI رد می‌شود.

dd86553 Validate eyebrow AI final output
  - Preview بعد از upload واقعی شد.
  - success فقط با HTTP 200 نیست؛ visible ROI diff داخل mask لازم شد.
  - mask واقعی ابرو لازم است؛ fallback/proportional mask برای AI واقعی قبول نمی‌شود.
  - Beauty-AI-only logs اضافه شد: [EYEBROW_PREVIEW], [EYEBROW_MASK], [AI], [AI_OUTPUT], [COMPOSITE], [FINAL].

4a1f1e5 Add Cloudflare vision failover slots
  - cf1/cf2/cf3 به‌عنوان Cloudflareهای جداگانه در AI Management کار می‌کنند.
  - analysis fallback chain برای ابرو با ۳ اسلات vision کامل شد.
```

### وضعیت تست آخرین کد

آخرین اعتبارسنجی انجام‌شده بعد از commit `1241f4a`:

```text
python -m py_compile giso/buti_ai/routes.py giso/buti_ai/eyebrow/final_design.py giso/buti_ai/eyebrow/image_generation.py giso/buti_ai/eyebrow/landmarks.py giso/buti_ai/eyebrow/flow.py
node --check giso/buti_ai/static/buti_ai.js
pytest giso/tests/test_ai_discovery.py giso/tests/test_ai_clean_registry.py giso/tests/test_buti_ai_phase1.py giso/tests/test_ai_cloudflare_vision.py giso/tests/test_admin_ai_panel.py -q
git diff --check

Result: 63 passed, 1 warning
```

Preview smoke:

```text
/analysis/mirror/eyebrow -> 200 OK
/admin/ai -> 302 /login unauthenticated, expected
upload -> server-side preview contains عکس واقعی شما and /analysis/mirror/eyebrow/uploads/...
```

### قانون مهم

فعلاً فقط مسیر ابرو پیاده‌سازی واقعی دارد. برای ۳ خدمت جدید هنوز feature code ساخته نشده و این سند برنامه اجرایی/سناریوی دقیق است.

---

## 2. تصمیم محصول نهایی: ۴ خدمت آینه زیبایی

هدف کاربر: خدماتی انتخاب شوند که:

- بازار واقعی در ایران/مشهد داشته باشند؛
- برای کاربر جذاب و قابل فهم باشند؛
- سالن‌دار بتواند با آن‌ها جذب شود؛
- خروجی قبل/بعد روی عکس واقعی کاربر قابل تولید باشد؛
- از نظر فنی خیلی اذیت‌کننده نباشند؛
- mask/ROI مشخص داشته باشند تا ادعای AI واقعی کنترل‌پذیر باشد.

لیست نهایی:

```text
1. آینه ابرو گیسو          — موجود و پایه‌اش ساخته شده
2. آینه ناخن گیسو          — خدمت جدید اول
3. آینه رنگ و لایت مو گیسو — خدمت جدید دوم
4. آینه لب و شیدینگ گیسو   — خدمت جدید سوم
```

خدماتی که فعلاً به فاز بعد منتقل می‌شوند:

```text
مژه، میکاپ کامل، پوست/فیشیال کامل، عروس، اکستنشن مو، خدمات درمانی پوست
```

دلیل انتقال:

- مژه نزدیک چشم است و ریسک تغییر چشم/پلک/چهره بالاتر دارد.
- پوست/فیشیال ممکن است به فیلتر زیبایی یا ادعای درمانی تبدیل شود.
- میکاپ کامل کل صورت را تغییر می‌دهد و کنترل هویت سخت‌تر است.
- خدمات عروس برای MVP بیش از حد بزرگ است.

---

## 3. مدل‌های نهایی هر خدمت

### 3.1 ابرو — موجود

```text
1. طبیعی و نچرال
2. میکروبلیدینگ ظریف
3. شیدینگ پودری
4. کامبینیشن
5. متعادل پیشنهادی گیسو
```

نکته: در کد فعلی گزینه پنجم با `giso_suggested` آمده است. طبق تصمیم قبلی کاربر، حتی گزینه پیشنهادی هم نباید انتخاب کاربر را مخفیانه جایگزین کند؛ selected model منبع حقیقت است.

### 3.2 ناخن — خدمت جدید اول

```text
1. نود و مینیمال
2. فرنچ کلاسیک
3. بیبی‌بومر
4. کروم / گلیزد
5. کت‌آی
```

### 3.3 رنگ و لایت مو — خدمت جدید دوم

```text
1. قهوه‌ای شکلاتی / نسکافه‌ای
2. بالیاژ کاراملی
3. هایلایت طبیعی
4. فیس‌فریم / مانی‌پیس
5. دودی زیتونی ملایم
```

### 3.4 لب و شیدینگ — خدمت جدید سوم

```text
1. شیدینگ لب طبیعی
2. تینت صورتی ملایم
3. نود گلبهی
4. کانتور لب طبیعی
5. رفع تیرگی و یکدست‌سازی رنگ لب
```

---

## 4. گراف کل کارهای انجام‌شده تا الان

```text
Project Memory setup
  -> Buti AI modular boundary rules
  -> SCENARIO_BEAUTY_MIRROR_EYEBROW.md
  -> TECHNICAL_DESIGN_BUTI_AI_MVP.md
  -> CODE_BOUNDARY_RULES_BUTI_AI.md

Buti AI / آینه ابرو implementation
  -> Phase 1: base mirror route/card/wizard
  -> Phase 1.5: move eyebrow logic under giso/buti_ai/eyebrow/
  -> Phase 2: quality check + analysis + guided preview
  -> Phase 2.x: UI/UX redesigns, samples, upload UX
  -> Phase 3: structured eyebrow analysis/scoring
  -> Phase 4.1: final candidate/auth/final design page
  -> Phase 4.2: image provider chain
  -> Phase 4.3: no active center/waitlist
  -> Phase 4.4: inline centers and smart guidance
  -> AI Management cf1/cf2/cf3 fallback slots
  -> Final-output fixes:
       - real upload preview after upload
       - real eyebrow mask required for AI success
       - visible ROI diff validation
       - saved-file validation
       - final AI output saved as PNG
       - no false AI success message
       - Beauty AI logs

New requested expansion
  -> Final service catalog selected:
       ابرو + ناخن + رنگ/لایت مو + لب/شیدینگ
  -> This document defines exact scenario, prompts, stages, and implementation graph
  -> Next coding stages should implement the three new services under giso/buti_ai/
```

---

## 5. گراف اجرایی برای ۳ خدمت جدید

برای جلوگیری از ساخت سیستم موازی، مسیر جدید باید روی معماری Buti AI فعلی سوار شود.

### گراف سطح بالا

```text
/analysis/mirror
  -> service selection
     -> eyebrow        -> existing eyebrow flow
     -> nail           -> new nail flow
     -> hair_color     -> new hair-color flow
     -> lip_shading    -> new lip flow

Each service flow:
  model selection
  -> upload
  -> validate photo quality for that service
  -> detect service ROI/mask
  -> store final candidate
  -> final auth gate if needed
  -> final design generation
       -> AI Management provider chain
       -> inpainting if selected/configured
       -> normal image edit if selected/configured
       -> composite constrained to service mask
       -> original-vs-final ROI diff validation
       -> outside-mask preservation validation
       -> saved file readable/dimensions validation
       -> success or non-AI fallback
  -> final before/after comparator
  -> matching centers/reservation/waitlist
```

### گراف فایل/ماژول پیشنهادی

نباید همه چیز داخل `routes.py` بریزد. پیشنهاد:

```text
giso/buti_ai/
  services_catalog.py        # فهرست ۴ خدمت و metadata مشترک UI
  routes.py                  # controller thin only
  templates/buti_ai/
    mirror_home.html
    service_wizard.html      # اگر generic شد
    final_auth.html          # اگر generic شد
    final_design.html        # اگر generic شد
  static/
    buti_ai.css
    buti_ai.js
    services/<service>/<model>.jpg

  eyebrow/                   # موجود؛ نباید بی‌دلیل بازنویسی شود

  nail/
    __init__.py
    options.py
    upload.py or shared upload adapter
    flow.py
    result.py
    prompts.py
    landmarks.py             # nail/hand ROI + mask
    final_design.py
    image_generation.py      # یا shared generator with service config
    centers.py

  hair_color/
    __init__.py
    options.py
    flow.py
    result.py
    prompts.py
    landmarks.py             # hair segmentation/mask
    final_design.py
    image_generation.py
    centers.py

  lip/
    __init__.py
    options.py
    flow.py
    result.py
    prompts.py
    landmarks.py             # lip ROI/mask
    final_design.py
    image_generation.py
    centers.py
```

پیاده‌سازی سریع‌تر می‌تواند با shared generic modules شروع شود، اما owner باید همچنان `giso/buti_ai/` باشد. اگر generic route/template ساخته شد، نباید منطق service-specific در template پخش شود؛ config باید از service modules بیاید.

---

## 6. AI Management و provider policy برای خدمات جدید

قانون قبلی کاربر همچنان برقرار است:

- AI Management منبع provider/model است.
- provider/model hard-code نشود.
- Cloudflare FLUX default را خودکار به inpainting تغییر نده.
- اگر مدل inpainting در AI Management تنظیم شده باشد، image+mask در فرمت درست همان provider ارسال شود.
- اگر مدل normal image edit باشد، adapter خودش استفاده شود و خروجی بعداً با mask محدود و validate شود.
- HTTP 200 هرگز success نیست.

### پیشنهاد task keys جدید در AI Management

برای جلوگیری از قاطی شدن با ابرو، اسلات‌های تصویر هر خدمت بهتر است جدا باشد:

```text
TASK_NAIL_IMAGE_DESIGN
TASK_HAIR_COLOR_IMAGE_DESIGN
TASK_LIP_IMAGE_DESIGN
```

یا اگر معماری عمومی‌تر انتخاب شد:

```text
TASK_BUTI_AI_IMAGE_DESIGN
with service_key = eyebrow/nail/hair_color/lip_shading
```

اما تصمیم نهایی باید با کد فعلی `giso/buti_ai/ai_models.py` هماهنگ شود. قبل از coding باید exact structure آن فایل بررسی شود.

---

## 7. Success gate مشترک برای همه خدمات

برای هر ۳ خدمت جدید، success فقط وقتی true است که:

```text
1. uploaded source image exists
2. service model selected by user is preserved
3. service ROI/mask exists and has safe coverage
4. provider returned image bytes/data URL/URL
5. image decoded successfully
6. output fitted to original dimensions
7. provider output constrained to mask
8. inside-mask visible diff passes threshold
9. outside-mask preservation passes threshold
10. final file saved
11. saved final file re-opened and validated
12. final URL points to saved file
13. is_ai_generated=True only when all gates pass
```

اگر هرکدام fail شد:

```text
is_ai_generated=False
fallback_type=non_ai_guided_fallback
message must be accurate
no false "AI آماده شد" claim
```

---

## 8. سناریو و prompt دقیق: ناخن

### 8.1 ورودی و validation

ورودی مناسب:

```text
عکس واضح از دست و ناخن‌ها
نور کافی
ناخن‌ها در کادر و فوکوس باشند
ترجیحاً کف دست/روی میز یا دست مقابل دوربین
بدون فیلتر رنگی سنگین
```

رد یا warning:

```text
ناخن‌ها خارج کادرند
عکس خیلی تار است
نور خیلی کم است
دست با اشیای زیاد پوشیده شده
ناخن مصنوعی/طرح فعلی آنقدر شلوغ است که ROI نامطمئن می‌شود
```

### 8.2 ROI/mask ناخن

روش پیشنهادی MVP:

```text
1. MediaPipe Hands اگر موجود باشد
   -> landmarks انگشت‌ها و nail-tip approximations
2. OpenCV/skin+edge heuristic برای hand/fingertip fallback
3. proportional fallback فقط برای non-AI guide، نه AI واقعی
```

mask مجاز:

```text
فقط nail plates و در صورت نیاز امتداد منطقی خیلی نزدیک ناخن
نه پوست دست، نه انگشتر، نه پس‌زمینه
```

### 8.3 مدل‌ها و prompts

#### نود و مینیمال

```text
Edit the original hand photo with nude minimal gel nails.
Apply a clean nude polish only on the visible nail plates.
Keep the natural nail length and shape unless minor smoothing is needed.
Use a soft beige-pink nude tone with realistic glossy reflection.
Do not change skin, fingers, rings, background, hand shape, lighting, or shadows.
Only nail surfaces may change.
The result must look like a real salon nail preview on the same hand.
```

#### فرنچ کلاسیک

```text
Edit the original hand photo with classic French manicure.
Keep the nail base natural pink-nude and add clean white French tips.
Apply the design only on the nail plates.
Respect the existing nail shape and perspective.
Do not change skin, fingers, rings, background, hand pose, lighting, or shadows.
The French line should be realistic, not cartoonish, and follow each nail curve.
Photorealistic salon preview.
```

#### بیبی‌بومر

```text
Edit the original hand photo with baby boomer ombre nails.
Apply a soft pink-to-white gradient only on the nail plates.
Keep the design elegant, clean, and realistic.
The gradient should follow the natural nail perspective and lighting.
Do not change skin tone, fingers, jewelry, background, hand shape, or shadows.
Only the nails should be edited.
Photorealistic salon nail preview.
```

#### کروم / گلیزد

```text
Edit the original hand photo with soft glazed chrome nails.
Apply a pearly chrome finish only on the nail plates.
Keep the color elegant and wearable, not overly metallic or fake.
Preserve the original hand, skin, fingers, rings, background, lighting, and pose.
Reflections should match the photo lighting.
Only nails may change.
Realistic beauty salon preview.
```

#### کت‌آی

```text
Edit the original hand photo with cat-eye magnetic gel nails.
Apply a deep glossy color with a subtle diagonal magnetic light streak on each nail.
The cat-eye reflection must follow each nail perspective.
Edit only the nail plates.
Do not alter skin, fingers, hand shape, jewelry, background, lighting, or shadows.
The final image must look like a real salon nail design preview.
```

### 8.4 fallback ناخن

اگر AI fail شد:

```text
Pillow/non-AI guided overlay روی nail mask
label واضح: راهنمای غیر AI
رنگ/فرنچ ساده قابل نمایش، نه ادعای اجرای واقعی
```

---

## 9. سناریو و prompt دقیق: رنگ و لایت مو

### 9.1 ورودی و validation

ورودی مناسب:

```text
عکس واضح صورت و مو
موها بخش قابل توجهی از کادر را داشته باشند
بدون فیلتر رنگی شدید
نور طبیعی/کافی
```

رد یا warning:

```text
مو معلوم نیست یا زیر روسری/کلاه پوشیده است
نور رنگی شدید دارد
صورت/مو خیلی تار است
فقط چهره بدون مو دیده می‌شود
```

### 9.2 ROI/mask مو

روش پیشنهادی:

```text
1. MediaPipe Selfie Segmentation / hair segmentation اگر موجود باشد
2. face detection + color/texture segmentation around head
3. SAM/vision provider only if configured and safe
4. proportional fallback فقط برای non-AI guide، نه AI واقعی
```

mask مجاز:

```text
فقط مو
نه صورت، نه ابرو، نه چشم، نه پوست، نه لباس، نه پس‌زمینه
```

### 9.3 مدل‌ها و prompts

#### قهوه‌ای شکلاتی / نسکافه‌ای

```text
Edit the original customer photo by changing only the hair color to a natural chocolate-nescafe brown.
Preserve the original face, skin, eyes, eyebrows, lips, clothes, background, lighting, and identity.
The hair texture, shine, volume, and shadows must remain realistic.
Do not change hairstyle or haircut.
Apply color only inside the hair mask.
Avoid flat paint; keep natural highlights and depth.
Photorealistic salon hair color preview.
```

#### بالیاژ کاراملی

```text
Edit the original customer photo with soft caramel balayage.
Apply warm caramel highlights mainly through mid-lengths and ends of the hair.
Keep roots natural and softly blended.
Preserve original hairstyle, hair volume, face, skin, eyes, eyebrows, lips, clothes, background, lighting, and identity.
Only hair pixels may change.
The balayage should look salon-realistic with natural depth and soft transition.
Do not over-blonde or bleach the entire hair.
```

#### هایلایت طبیعی

```text
Edit the original customer photo with subtle natural highlights.
Add fine, realistic lighter strands only within the hair mask.
Keep the base color mostly unchanged.
Preserve hairstyle, face, skin, eyes, eyebrows, lips, clothes, background, lighting, and identity.
The highlights should follow the natural hair direction and lighting.
Do not create harsh stripes or unrealistic blonde blocks.
Photorealistic salon consultation preview.
```

#### فیس‌فریم / مانی‌پیس

```text
Edit the original customer photo with soft face-frame highlights, also called money piece.
Lighten only the front hair strands around the face, inside the hair mask.
Keep the rest of the hair close to the original color.
Do not change face, skin, eyes, eyebrows, lips, makeup, clothes, background, or identity.
The front highlights must look blended and salon-realistic.
Do not cover the face or alter facial features.
Only hair pixels may change.
```

#### دودی زیتونی ملایم

```text
Edit the original customer photo by applying a soft ash-olive brown tone only to the hair.
Keep the result wearable and realistic, not green or gray.
Preserve original hair texture, shadows, hairstyle, face, skin, eyes, eyebrows, lips, clothes, background, lighting, and identity.
Only hair pixels may change.
Maintain natural highlights and depth.
Photorealistic salon hair tone preview.
```

### 9.4 fallback مو

مو از نظر فنی سخت‌تر است. fallback باید محافظه‌کار باشد:

```text
color tint فقط داخل hair mask اگر mask قابل قبول است
اگر mask واقعی نیست، فقط متن/نمونه مدل نمایش داده شود؛ ادعای before/after روی عکس نشود
```

---

## 10. سناریو و prompt دقیق: لب و شیدینگ

### 10.1 ورودی و validation

ورودی مناسب:

```text
عکس واضح صورت یا نیم‌رخ نزدیک
لب‌ها مشخص باشند
دندان/لب blur نباشد
بدون فیلتر سنگین
نور کافی
```

رد یا warning:

```text
لب‌ها پوشیده/خارج کادرند
کیفیت خیلی پایین است
لب خیلی باز است و دندان غالب است
فیلتر زیبایی سنگین دارد
```

### 10.2 ROI/mask لب

روش پیشنهادی:

```text
1. MediaPipe FaceMesh lip landmarks اگر موجود باشد
2. OpenCV/face landmark fallback اگر موجود باشد
3. color segmentation around mouth فقط با confidence پایین
4. proportional fallback فقط برای non-AI guide، نه AI واقعی
```

mask مجاز:

```text
فقط upper lip و lower lip
نه دندان، نه پوست اطراف لب، نه بینی، نه چانه
```

### 10.3 مدل‌ها و prompts

#### شیدینگ لب طبیعی

```text
Edit the original customer face photo with natural lip shading.
Apply a soft, even, natural rosy tint only inside the lip mask.
Keep the original lip shape and natural texture.
Do not overline or enlarge the lips.
Do not change teeth, skin around lips, nose, chin, face shape, eyes, eyebrows, hair, lighting, background, or identity.
The result should look like a realistic PMU lip shading consultation preview.
```

#### تینت صورتی ملایم

```text
Edit the original customer face photo with a soft pink lip tint.
Apply a gentle pink color only inside the lip mask.
Keep the lip texture, natural highlights, and original lip shape.
Do not change teeth, skin, face shape, nose, chin, eyes, eyebrows, hair, background, lighting, or identity.
The tint should be wearable, fresh, and realistic.
No heavy lipstick, no overlining.
```

#### نود گلبهی

```text
Edit the original customer face photo with a nude peach lip tone.
Apply a warm nude-peach color only inside the lip mask.
Keep the lips natural, soft, and realistic.
Preserve original lip shape and texture.
Do not change teeth, skin around lips, nose, chin, face, eyes, eyebrows, hair, background, or lighting.
No heavy makeup outside the lips.
Photorealistic PMU/salon preview.
```

#### کانتور لب طبیعی

```text
Edit the original customer face photo with natural lip contour.
Softly define the lip border only within the lip mask.
Improve visible symmetry slightly without changing the actual face or mouth structure.
Keep the center of the lips softly tinted and natural.
Do not enlarge lips unrealistically.
Do not change teeth, surrounding skin, nose, chin, face shape, eyes, eyebrows, hair, background, lighting, or identity.
The result must look like a realistic PMU lip contour preview.
```

#### رفع تیرگی و یکدست‌سازی رنگ لب

```text
Edit the original customer face photo to softly neutralize dark or uneven lip tone.
Apply correction only inside the lip mask.
Keep the lips natural and realistic with preserved texture and highlights.
Do not make the lips unnaturally bright or flat.
Do not change teeth, skin around the lips, nose, chin, face shape, eyes, eyebrows, hair, lighting, background, or identity.
The output should look like a realistic lip neutralization consultation preview.
```

### 10.4 fallback لب

```text
Pillow/non-AI color overlay روی lip mask با alpha کم
label: راهنمای غیر AI
اگر mask واقعی لب نبود، خروجی روی عکس ادعا نشود
```

---

## 11. مراحل coding پیشنهادی برای ایجنت بعدی

### Stage A — Catalog/Navigation بدون AI جدید

هدف: صفحه آینه زیبایی ۴ خدمت را نشان دهد و هر خدمت مدل‌های خودش را داشته باشد.

کارها:

```text
1. Add shared service catalog for eyebrow/nail/hair/lip.
2. Update mirror_home service cards.
3. Add service routes or generic service route.
4. Keep eyebrow route backward-compatible.
5. Add tests: service cards and model lists render.
```

بدون این مرحله سراغ AI generation جدید نرو.

### Stage B — Nail MVP

چرا اول ناخن: mask/ROI آسان‌تر و ریسک چهره ندارد.

```text
1. Build nail options/prompts/flow.
2. Upload hand photo.
3. Basic photo validation.
4. Nail ROI/mask detection.
5. Non-AI guided fallback.
6. Provider generation chain with mask validation.
7. Final before/after comparator.
8. Center matching by service=nail.
```

### Stage C — Lip MVP

```text
1. Build lip options/prompts/flow.
2. Face/lip photo validation.
3. Lip mask via FaceMesh/OpenCV fallback.
4. AI/fallback with strict lip-only validation.
5. Center matching: PMU/lip/brow service where available.
```

### Stage D — Hair Color MVP

چرا بعد از لب: hair mask سخت‌تر است.

```text
1. Build hair options/prompts/flow.
2. Hair photo validation.
3. Hair mask/segmentation.
4. Start with conservative models only.
5. If real mask not reliable, show non-AI/textual fallback.
6. AI success only with hair-mask diff and face preservation.
```

### Stage E — Admin/Salon handoff

```text
1. Demand/waitlist by service.
2. Center cards filtered by service.
3. Reservation handoff with final design context.
4. Owner dashboard lead visibility later.
```

---

## 12. Things not to do

```text
- Do not build a parallel app outside giso/buti_ai/.
- Do not put new service business logic into giso/analysis.py.
- Do not change legacy /analysis hair/skin flows.
- Do not touch bot_edu, web, main.py, or giso/bot.py.
- Do not hard-code provider/model outside AI Management.
- Do not claim AI success from HTTP 200 alone.
- Do not show before/after AI output if mask/ROI diff failed.
- Do not use fallback/proportional mask for real AI success.
- Do not edit whole face/body/image when the service mask is missing.
```

---

## 13. Handoff summary for next coding agent

The user now wants the three remaining Beauty Mirror services implemented after updating Project Memory:

```text
1. Nail Mirror
2. Hair Color/Light Mirror
3. Lip/Shading Mirror
```

Before coding:

```text
- read this file
- read PROJECT_MEMORY.md
- read CODE_BOUNDARY_RULES_BUTI_AI.md
- inspect current giso/buti_ai code at HEAD
- keep branch arena/01a0e0b8-giso4
- preserve existing eyebrow behavior
```

Implementation priority:

```text
1. Catalog/navigation for all 4 services
2. Nail MVP
3. Lip MVP
4. Hair Color MVP
```

Acceptance principle:

```text
The user wants real, marketable before/after outputs that can be shown to customers and sold to salon owners. Accuracy and truthful labeling are more important than overclaiming. If service mask is not reliable, do not produce/claim AI final image.
```
