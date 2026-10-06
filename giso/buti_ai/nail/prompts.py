# -*- coding: utf-8 -*-
"""Prompt library for آینه ناخن گیسو."""

PHOTO_QUALITY_PROMPT = """
تو یک بررسی‌کننده کیفیت عکس برای آینه ناخن گیسو هستی.
فقط بررسی کن آیا این عکس برای تحلیل و طراحی ناخن مناسب است یا نه.

قواعد:
- اگر دست قابل مشاهده نیست، ok=false
- اگر ناخن‌ها قابل مشاهده نیستند، ok=false
- اگر نور خیلی کم یا تصویر خیلی تار است، ok=false
- اگر زاویه دست خیلی کج یا ناخن‌ها خارج کادر هستند، ok=false
- اگر عکس مناسب است، ok=true
- پیام فارسی کوتاه و قابل فهم

فقط JSON معتبر برگردان:
{
  "ok": true,
  "hand_visible": true,
  "nails_visible": true,
  "lighting": "good | medium | poor",
  "angle": "good | bad_angle",
  "sharpness": "good | medium | blurry",
  "reasons": [],
  "message": "پیام کوتاه فارسی"
}
""".strip()


def nail_analysis_prompt(selected_style_label, change_level_label):
    return f"""
تو مشاور طراحی ناخن برای «آینه ناخن گیسو» هستی.
عکس دست کاربر را مثل یک ناخن‌کار حرفه‌ای بررسی کن.

انتخاب کاربر:
- مدل: {selected_style_label}
- شدت تغییر: {change_level_label}

بررسی کن:
- فرم ناخن‌ها (گرد، بادامی، مربعی)
- طول ناخن
- تعداد ناخن قابل مشاهده
- وضعیت پوست اطراف ناخن
- تناسب رنگ پوست با مدل انتخابی
- ریسک مصنوعی شدن

فقط JSON معتبر:
{{
  "hand_shape": "باریک | متوسط | پهن | نامشخص",
  "nail_form": "گرد | بادامی | مربعی | نامشخص",
  "nail_length": "کوتاه | متوسط | بلند | نامشخص",
  "visible_nails": 5,
  "skin_tone_match": "خوب | متوسط | نیاز به تنظیم",
  "recommended_style": "nude_minimal | classic_french | baby_boomer | glazed_chrome | cat_eye",
  "short_reason": "دلیل کوتاه",
  "do": ["حداکثر 3 مورد"],
  "avoid": ["حداکثر 3 مورد"],
  "confidence": "low | medium | high"
}}
""".strip()


NAIL_PROMPTS = {

NAIL_PROMPTS = {
    "nude_minimal": "Edit the original hand photo with nude minimal gel nails. Apply a clean nude polish only on the visible nail plates. Do not change skin, fingers, rings, background, hand shape, lighting, or shadows.",
    "classic_french": "Edit the original hand photo with classic French manicure. Keep the nail base natural pink-nude and add clean white French tips only on the nail plates. Do not change skin, fingers, rings, background, pose, or lighting.",
    "baby_boomer": "Edit the original hand photo with baby boomer ombre nails. Apply a soft pink-to-white gradient only on the nail plates. Preserve skin, fingers, jewelry, background, hand shape, and shadows.",
    "glazed_chrome": "Edit the original hand photo with soft glazed chrome nails. Apply a pearly chrome finish only on the nail plates. Reflections should match the photo lighting. Preserve the original hand and background.",
    "cat_eye": "Edit the original hand photo with cat-eye magnetic gel nails. Apply a deep glossy color with a subtle diagonal magnetic light streak on each nail. Only nail plates may change.",
}
