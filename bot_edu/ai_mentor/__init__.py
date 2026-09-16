"""
ai_mentor — ماژول «یار هوشمند شغلی و مسیر یادگیری»

این پکیج کاملاً جداست و کدهای اصلی ربات را دست‌نخورده نگه می‌دارد.
اتصال به ربات فقط از سه نقطه انجام می‌شود:
  1. db.py        → صدا زدن init_ai_tables() داخل init_db()
  2. ui.py        → دو دکمهٔ جدید (کاربر + ادمین)
  3. handlers.py  → مسیریابی callbackهای aim_ و stateهای wait_aim_

وابستگی: db، config، core، ui و stdlib. هرگز از handlers.py import نکنید.

━━━ معماری چندعاملی «شروع مسیر جدید» ━━━
    agents/career_interview.py  ← ایجنت ۱: مصاحبه‌گر شغلی
    agents/roadmap_builder.py   ← ایجنت ۲: معمار نقشه راه
    agents/learning_mentor.py   ← ایجنت ۳: منتور آموزشی
    prompts/*.txt               ← پرامپت هر ایجنت (خارج از کد)
    core.py                     ← UserJourneyContext و توابع مشترک

⚠️ ai_mentor/core.py با core.py ریشهٔ پروژه فرق دارد. چون این پکیج
absolute import می‌کند (`from core import ...`)، پایتون همچنان core.py
ریشه را می‌بیند. برای فایل داخلی باید نوشت: `from . import core`.
"""
__all__ = [
    "ai_db",
    "ai_core",
    "ai_ui",
    "ai_prompts",
    "ai_market",
    "ai_handlers",
    "ai_admin",
    "core",
    "agents",
]
