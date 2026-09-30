# پرامپت برای VSCode + Cline — بررسی مشکل پیش‌نمایش آپلود عکس ابرو

## پرامپت آماده (فارسی) - کپی کن به Cline بده

```
تو یک دیباگر ارشد Flask + JS هستی. پروژه گیسو مسیر: /home/user/giso4 یا همین ریپازیتوری که باز کردی.

مشکل: تو آینه ابرو گیسو، مرحله ۳ آپلود عکس، وقتی کاربر عکس انتخاب می‌کنه (input#btiEyebrowPhoto)، پیش‌نمایش عکس تو کادر نشون داده نمیشه. باید تو همون قاب یک اسکن لیزری بیاد و عکس قشنگ مشخص باشه.

وظیفه تو: فقط و فقط همین Flow رو دیباگ کن، بدون تغییر فایل‌های نامربوط.

Scope Lock (فقط این فایل‌ها رو بخون و اگه لازم شد تغییر بده):
- giso/buti_ai/templates/buti_ai/eyebrow_wizard.html
- giso/buti_ai/static/buti_ai.js
- giso/buti_ai/static/buti_ai.css
- giso/buti_ai/eyebrow/upload.py
- giso/buti_ai/eyebrow/flow.py
- giso/buti_ai/routes.py (فقط متد eyebrow_upload و eyebrow_validate_photo)

مطلقاً تغییر نده:
- giso/analysis.py, ai_brain.py, gemini_proxy_manager.py, bot, panel, marketplace, shop, hair_sale, notifications, referral, wallet, withdrawals, beauty_centers, reservation, user/auth/payment, unrelated DBs, no new deps, no migration, no nginx.

مراحل بررسی:

1. HTML: تو eyebrow_wizard.html چک کن:
   - input#btiEyebrowPhoto وجود داره؟ accept="image/jpeg,image/png,image/webp" required
   - #btiUploadZone, #btiUploadPlaceholder, #btiUploadPreview, #btiUploadPreviewFrame, #btiChangePhotoBtn, #btiUploadText, #btiUploadFileName, #btiAnalyzeBtn
   - فرم data-bti-upload-form و csrf_token داره؟
   - <picture> برای نمونه‌ها تداخل ID نکرده؟

2. JS: تو buti_ai.js ready():
   - input change listener وصله؟ file = input.files[0] خونده میشه؟
   - typeOk, extOk, size < 8MB چک
   - URL.createObjectURL و FileReader fallback
   - preview.src, display block, hidden removal, previewFrame hidden=false, placeholder hidden=true, zone has-preview, setAnalyzeEnabled(true)
   - validateEyebrowPhoto با X-GISO-CSRF header از input[name="csrf_token"].value
   - console.log بذار

3. CSS: تو buti_ai.css:
   - .bti-upload-preview, .bti-upload-preview-frame[hidden], .bti-upload-zone.has-preview display
   - final override برای .bti-brow-sample.is-wide-png فقط همونو هدف گرفته نه .bti-upload-preview
   - .bti-laser-scan animation btiLaserScan

4. Flask routes.py:
   - eyebrow_upload GET باید flow_step=upload برگردونه
   - POST csrf_token چک (security.py) — اگه 400 CSRF میده چرا؟
   - validate-photo POST X-GISO-CSRF می‌خونه

5. تست curl + cookie برای CSRF

6. خروجی: #btiUploadPreviewFrame visible، placeholder hidden، changeBtn visible، analyzeBtn enabled. اگه نشد بگو کدوم خط fail، کدوم element null، کدوم CSS display:none.

فقط همین پیش‌نمایش رو فیکس کن. با venv و SECRET_KEY=test... روی 5001 تست کن.
```

## مسیر دقیق فایل‌ها

```
/home/user/giso4/giso/buti_ai/templates/buti_ai/eyebrow_wizard.html (99-140)
/home/user/giso4/giso/buti_ai/static/buti_ai.js (94-170)
/home/user/giso4/giso/buti_ai/static/buti_ai.css (2741+, 2847+, 3080+)
/home/user/giso4/giso/buti_ai/eyebrow/upload.py
/home/user/giso4/giso/buti_ai/eyebrow/flow.py
/home/user/giso4/giso/buti_ai/routes.py (240-280)
```

## اجرای سرور

```bash
python3 -m venv /tmp/venv
/tmp/venv/bin/pip install -r requirements.txt
PYTHONPATH=/home/user/giso4 SECRET_KEY=test123456789012345678901234567890 /tmp/venv/bin/python giso/app.py
# http://127.0.0.1:5001/analysis/mirror/eyebrow
```
