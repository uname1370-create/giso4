# -*- coding: utf-8 -*-
"""Prompt library for آینه لب و شیدینگ گیسو."""

PHOTO_QUALITY_PROMPT = """
تو یک بررسی‌کننده کیفیت عکس برای آینه لب و شیدینگ گیسو هستی.
فقط بررسی کن آیا این عکس برای تحلیل لب مناسب است یا نه.

قواعد:
- اگر صورت قابل مشاهده نیست، ok=false
- اگر لب بالا و پایین قابل مشاهده نیستند، ok=false
- اگر نور خیلی کم یا تصویر تار است، ok=false
- اگر زاویه خیلی کج است، ok=false
- اگر مناسب است، ok=true

فقط JSON:
{
  "ok": true,
  "face_visible": true,
  "lips_visible": true,
  "upper_lip_visible": true,
  "lower_lip_visible": true,
  "lighting": "good | medium | poor",
  "angle": "front | slight_angle | bad_angle",
  "sharpness": "good | medium | blurry",
  "reasons": [],
  "message": "پیام کوتاه فارسی"
}
""".strip()


def lip_analysis_prompt(selected_style_label, change_level_label):
    return f"""
تو مشاور لب و شیدینگ برای «آینه لب گیسو» هستی.
عکس کاربر را مثل یک پی‌ام‌یو آرتیست بررسی کن.

انتخاب کاربر:
- مدل: {selected_style_label}
- شدت: {change_level_label}

بررسی کن:
- لب بالا و پایین قابل تشخیص
- فرم لب (نازک، متوسط، حجیم)
- تقارن لب‌ها
- رنگ فعلی لب (روشن، متوسط، تیره، نامتوازن)
- مرز لب (واضح، محو)
- تطبیق مدل انتخابی با فرم فعلی

فقط JSON:
{{
  "upper_lip_visible": true,
  "lower_lip_visible": true,
  "lip_form": "نازک | متوسط | حجیم | نامشخص",
  "symmetry": "خوب | متوسط | نیاز به اصلاح | نامشخص",
  "current_color": "روشن | متوسط | تیره | نامتوازن | نامشخص",
  "border_clarity": "واضح | محو | نامشخص",
  "recommended_style": "natural_shading | soft_pink_tint | peach_nude | natural_contour | dark_tone_neutralize",
  "short_reason": "دلیل کوتاه",
  "do": ["حداکثر 3 مورد"],
  "avoid": ["حداکثر 3 مورد"],
  "confidence": "low | medium | high"
}}
""".strip()


LIP_SHADING_PROMPTS = {

LIP_SHADING_PROMPTS = {
    "natural_shading": "Edit the original face/lip photo with natural lip shading. Apply a soft natural pigment only within the lips. Preserve teeth, skin, face shape, makeup, lighting, and background.",
    "soft_pink_tint": "Edit the original face/lip photo with a soft pink lip tint only within the lip area. Keep texture realistic and preserve teeth, skin, face, lighting, and background.",
    "peach_nude": "Edit the original face/lip photo with a warm peach-nude lip color only inside the lips. Preserve lip texture, teeth, surrounding skin, face, and background.",
    "natural_contour": "Edit the original face/lip photo with a very natural lip contour. Slightly define the lip border without enlarging the lips. Preserve teeth, skin, face shape, lighting, and background.",
    "dark_tone_neutralize": "Edit the original face/lip photo by softly neutralizing uneven dark tones only inside the lips. Keep the result natural and preserve skin, teeth, face, and background.",
}
