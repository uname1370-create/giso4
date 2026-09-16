"""
agents — ایجنت‌های معماری چندعاملی «یار هوشمند شغلی».

سه ایجنت، هرکدام دقیقاً یک مسئولیت:

  ۱. CareerInterviewAgent (career_interview.py)
     گفتگوی مکالمه‌ای با کاربر → تحلیل بازار → معرفی ۳ مسیر →
     گزارش کامل مسیر انتخابی → خروجی JSON نهایی.

  ۲. RoadmapBuilderAgent (roadmap_builder.py)
     دریافت JSON ایجنت ۱ → ساخت **اسکلت** نقشه راه (بدون محتوا).

  ۳. LearningMentorAgent (learning_mentor.py)
     تولید محتوای هر گام در لحظهٔ باز شدن (Lazy Loading) + داوری تمرین.

قرارداد مشترک هر ایجنت:
  • پرامپت خود را از ai_mentor/prompts/*.txt می‌خواند (نه از داخل کد).
  • متد async run(context, user_message) دارد.
  • خروجی را در همان UserJourneyContext ذخیره می‌کند.
  • دیکشنری‌ای با کلید stage برمی‌گرداند تا FSM بداند کجاست.

وابستگی: فقط ai_mentor.core و ai_mentor.ai_db — هرگز handlers.py.
"""
from .career_interview import CareerInterviewAgent
from .learning_mentor import LearningMentorAgent
from .roadmap_builder import RoadmapBuilderAgent

__all__ = [
    "CareerInterviewAgent",
    "RoadmapBuilderAgent",
    "LearningMentorAgent",
]
