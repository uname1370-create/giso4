# طرح بازتولید و آزمون — جریان آپلود، تحلیل، پیشنهاد و خروجی Buti AI

**تاریخ:** 2026-10-12  
**برنچ:** `arena/7f567e47-giso4`  
**منبع قرارداد:** `BUTI_AI_UPLOAD_ANALYSIS_RECOMMENDATION_IMPLEMENTATION_SCENARIO.md`، بخش تکمیلی `FINAL_IMPLEMENTATION_SCENARIO_BUTI_AI_2026-10-12.md` و مرزهای `CODE_BOUNDARY_RULES_BUTI_AI.md`

## محدودهٔ این تغییر

- فقط خدمات **ابرو** و **لب/شیدینگ لب** در `giso/buti_ai/`.
- هیچ تغییر در `web/`، `bot_edu/`، `main.py` یا `giso/bot.py` مجاز نیست.
- مسیرهای ناخن و رنگ مو خارج از سناریوی حاضر هستند و نباید تغییر رفتار دهند.
- هیچ fallback محلی نباید با عنوان خروجی AI واقعی نشان داده شود.

## سناریوی بازتولید قرارداد

```text
انتخاب خدمت
→ انتخاب مدل و شدت تغییر (session)
→ انتخاب فایل JPG/PNG/WebP و preview محلی فوری
→ POST validate با FormData + CSRF، همان‌مبدأ و credential
→ بررسی فرمت، اندازه و decode در سرور
→ quality check و Vision analysis
→ کارت «پیشنهاد گیسو» و «انتخاب خودم»
→ POST اول upload با عکس: 200 و حفظ candidate، بدون generation/redirect به final
→ POST دوم finalize با analysis_confirmed=1 و final_style معتبر: 302 به final
→ تولید با final_style تأییدشده
→ نمایش before/after، برچسب صادقانه AI/non-AI، دانلود محافظت‌شدهٔ تصویر و PDF
```

## آزمون‌های backend لازم

1. validate ابرو با عکس معتبر و mock تحلیل موفق: پاسخ `ai_checked` و recommendation با `ai_analyzed`، style معتبر و reason.
2. validate لب با عکس معتبر و mock تحلیل موفق: پاسخ recommendation با style نرمال‌شده از `STYLES` لب.
3. validate عکس خراب: پاسخ 400/422؛ هیچ فایل موقتی باقی نماند.
4. validate با provider غیرقابل‌دسترس: انتخاب دستی باقی بماند و status `ai_unavailable` صادقانه باشد.
5. POST اول upload ابرو: `200`، کارت recommendation، candidate شامل عکس، selected/recommended style، analysis، change و مالک نشست؛ هیچ generation ایجاد نشود.
6. POST اول upload لب: همان قرارداد بالا و بدون اثر روی مسیرهای ناخن/رنگ مو.
7. POST دوم `analysis_confirmed=1` با پیشنهاد AI: redirect به final و `final_style` همان پیشنهاد باشد.
8. POST دوم با انتخاب دستی: redirect به final و `final_style` همان انتخاب اولیه باشد.
9. finalize بدون candidate یا بدون `analysis_confirmed=1`: generation انجام نشود و کاربر به wizard بازگردد.
10. candidate دارای مالک دیگر: رد شود؛ فایل و خروجی خصوصی باز نشوند.
11. مقدار `final_style` نامعتبر: server آن را با option همان service نرمال کند، نه با مقدار ارسال‌شدهٔ خام.
12. generation/prompt/provider برای ابرو و لب، `final_style` تأییدشده را دریافت کند.
13. صفحهٔ final در خروجی AI واقعی و fallback، before/after و برچسب درست را نشان دهد؛ fallback هرگز AI معرفی نشود.
14. دانلود تصویر و PDF فقط برای candidate/طرح متعلق به همان نشست یا کاربر مجاز ممکن باشد؛ path traversal و filename دلخواه رد شود.

## آزمون‌های frontend/browser لازم

برای ابرو و سپس لب:

1. بازکردن service، انتخاب مدل و شدت تغییر.
2. رفتن به upload و انتخاب عکس معتبر.
3. دیدن preview بلافاصله، loading تحلیل و checkها.
4. دیدن هر دو گزینهٔ پیشنهاد/انتخاب دستی.
5. انتخاب گزینهٔ دیگر و تأیید؛ بررسی انتقال به final.
6. بررسی before/after، برچسب status، لینک دانلود تصویر و PDF.
7. تکرار با provider unavailable؛ انتخاب دستی باید کار کند و متن AI-success دیده نشود.

## ترتیب اجرای آزمون

1. `node --check giso/buti_ai/static/buti_ai.js`
2. `python3 -m py_compile` برای فایل‌های Python تغییرکرده
3. تست‌های route/flow جدید با mock provider
4. suite کامل Buti AI
5. `git diff --check`
6. اجرای Flask و smoke browser روی URL عمومی Sandbox
7. live provider فقط در صورت وجود credential؛ بدون credential، وضعیت «تأییدنشده» گزارش می‌شود.
