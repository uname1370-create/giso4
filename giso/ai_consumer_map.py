# -*- coding: utf-8 -*-
"""نقشهٔ مصرف‌کننده‌های AI پروژه و دستهٔ پنل مدیریت AI که هرکدام از آن استفاده می‌کنند.

این فایل فقط داده است (بدون اثر جانبی) تا تست‌ها بتوانند اتصال هر بخش به پنل را بررسی کنند.
دسته‌ها همان چهار دستهٔ پنل هستند:
- text: مدل متنی (زنجیره failover پروایدرها)
- image_analysis: تحلیل عکس ورودی (TASK_EYEBROW_ANALYSIS)
- image_generation: طراحی تصویر (TASK_MIRROR_IMAGE_DESIGN)
- output_evaluation: ارزیابی خروجی (TASK_MIRROR_OUTPUT_VALIDATION)
"""
from __future__ import annotations

from typing import Dict, List

CATEGORY_TEXT = "text"
CATEGORY_IMAGE_ANALYSIS = "image_analysis"
CATEGORY_IMAGE_GENERATION = "image_generation"
CATEGORY_OUTPUT_EVALUATION = "output_evaluation"

CATEGORIES = (CATEGORY_TEXT, CATEGORY_IMAGE_ANALYSIS, CATEGORY_IMAGE_GENERATION, CATEGORY_OUTPUT_EVALUATION)

# هر مصرف‌کننده: کلید، برچسب فارسی، فایل، دسته، و نوع اتصال به پنل
# connection: panel_chain (زنجیره پنل) | panel_slots (اسلات‌های پنل) | separate_provider_table (جدول پروایدر جدا، خارج از پنل) | pixel_only (بدون AI)
CONSUMERS: List[Dict[str, str]] = [
    # --- متنی ---
    {"key": "text.general_chat", "label": "گفتگوی عمومی با مدل", "file": "giso/ai_runtime.py", "category": CATEGORY_TEXT, "connection": "panel_chain"},
    {"key": "text.site_consultant", "label": "مشاور سایت (special assistant)", "file": "giso/special_assistant.py", "category": CATEGORY_TEXT, "connection": "panel_chain"},
    {"key": "text.seo_jobs", "label": "کارهای SEO", "file": "giso/seo_jobs.py", "category": CATEGORY_TEXT, "connection": "panel_chain"},
    {"key": "text.shop_enricher", "label": "غنی‌سازی محصول فروشگاه", "file": "giso/shop/logic/enricher.py", "category": CATEGORY_TEXT, "connection": "panel_chain"},
    {"key": "text.channel_importer", "label": "واردکنندهٔ کانال", "file": "giso/channel_importer.py", "category": CATEGORY_TEXT, "connection": "panel_chain"},
    {"key": "text.analysis_text", "label": "تحلیل متنی آینه گیسو", "file": "giso/analysis.py", "category": CATEGORY_TEXT, "connection": "panel_chain"},
    {"key": "text.panel_test", "label": "تست مدل از پنل", "file": "giso/panel/modules/ai.py", "category": CATEGORY_TEXT, "connection": "panel_chain"},
    {"key": "text.bot_edu_chat", "label": "چت ربات آموزش", "file": "bot_edu/ai_brain.py", "category": CATEGORY_TEXT, "connection": "separate_provider_table"},
    {"key": "text.bot_edu_mentor", "label": "منتور ربات آموزش", "file": "bot_edu/ai_mentor/ai_core.py", "category": CATEGORY_TEXT, "connection": "separate_provider_table"},
    {"key": "text.bot_edu_handlers", "label": "هندلر هوش مصنوعی ربات آموزش", "file": "bot_edu/handlers_ai.py", "category": CATEGORY_TEXT, "connection": "separate_provider_table"},
    # --- تحلیل عکس ---
    {"key": "analysis.eyebrow_vision", "label": "تحلیل عکس ابرو", "file": "giso/buti_ai/eyebrow/ai.py", "category": CATEGORY_IMAGE_ANALYSIS, "connection": "panel_slots"},
    {"key": "analysis.hair_color_vision", "label": "تحلیل عکس رنگ مو", "file": "giso/buti_ai/hair_color/final_design.py", "category": CATEGORY_IMAGE_ANALYSIS, "connection": "panel_slots"},
    {"key": "analysis.lip_vision", "label": "تحلیل عکس لب", "file": "giso/buti_ai/lip/final_design.py", "category": CATEGORY_IMAGE_ANALYSIS, "connection": "panel_slots"},
    {"key": "analysis.nail_vision", "label": "تحلیل عکس ناخن", "file": "giso/buti_ai/nail/final_design.py", "category": CATEGORY_IMAGE_ANALYSIS, "connection": "panel_slots"},
    {"key": "analysis.photo_pipeline", "label": "خط تحلیل عکس آینه گیسو", "file": "giso/analysis.py", "category": CATEGORY_IMAGE_ANALYSIS, "connection": "panel_slots"},
    {"key": "analysis.hair_sale", "label": "فروش مو (تحلیل عکس)", "file": "giso/hair_sale.py", "category": CATEGORY_IMAGE_ANALYSIS, "connection": "panel_slots"},
    # --- طراحی تصویر ---
    {"key": "generation.eyebrow_image", "label": "طراحی تصویر ابرو", "file": "giso/buti_ai/eyebrow/image_generation.py", "category": CATEGORY_IMAGE_GENERATION, "connection": "panel_slots"},
    {"key": "generation.service_image", "label": "طراحی تصویر خدمات (ناخن، لب، رنگ مو)", "file": "giso/buti_ai/service_image_generation.py", "category": CATEGORY_IMAGE_GENERATION, "connection": "panel_slots"},
    # --- ارزیابی خروجی ---
    {"key": "evaluation.eyebrow_output", "label": "داور خروجی ابرو", "file": "giso/buti_ai/output_judge.py", "category": CATEGORY_OUTPUT_EVALUATION, "connection": "panel_slots"},
    {"key": "evaluation.lip_output", "label": "داور خروجی لب", "file": "giso/buti_ai/output_judge.py", "category": CATEGORY_OUTPUT_EVALUATION, "connection": "panel_slots"},
]

# بدون AI: بررسی خروجی ناخن و رنگ مو فقط پیکسلی/ماسکی است (validate_masked_output) و در پنل نیست.
PIXEL_ONLY: List[Dict[str, str]] = [
    {"key": "pixel.nail_output_check", "label": "بررسی پیکسلی خروجی ناخن (بدون AI)", "file": "giso/buti_ai/image_validation.py", "category": "", "connection": "pixel_only"},
    {"key": "pixel.hair_output_check", "label": "بررسی پیکسلی خروجی رنگ مو (بدون AI)", "file": "giso/buti_ai/image_validation.py", "category": "", "connection": "pixel_only"},
]


def consumers_by_category() -> Dict[str, List[Dict[str, str]]]:
    out: Dict[str, List[Dict[str, str]]] = {c: [] for c in CATEGORIES}
    for item in CONSUMERS:
        out[item["category"]].append(item)
    return out


def consumer_counts() -> Dict[str, int]:
    return {cat: len(items) for cat, items in consumers_by_category().items()}
