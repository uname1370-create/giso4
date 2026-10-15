#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os
import sys

os.environ.setdefault("SECRET_KEY", "arena-test-secret-for-buti-ai-tests-32chars")
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if BASE_DIR not in sys.path:
    sys.path.append(BASE_DIR)

"""کشف خودکار اسلات‌ها: فقط اسلات خالی پر می‌شود؛ اسلات دستی ادمین بازنویسی نمی‌شود."""
import giso.buti_ai.ai_models as ai_models  # noqa: E402
import giso.ai_models_registry as registry  # noqa: E402


def test_ai_autofill_slots(monkeypatch):
    saved = []

    def fake_save(task_key, priority, provider_name, model_name, **kwargs):
        saved.append((task_key, int(priority), provider_name, model_name))
        return True, "ok"

    monkeypatch.setattr(ai_models, "save_model_assignment", fake_save)
    monkeypatch.setattr(registry, "get_best_vision_model", lambda family: "auto-vision")
    monkeypatch.setattr(registry, "get_image_models", lambda family: [])

    # الف) اسلات تحلیل عکس پر است: با overwrite=False دست نمی‌خورد
    monkeypatch.setattr(ai_models, "_slot_is_empty", lambda task_key, priority: False)
    saved.clear()
    ai_models.auto_configure_for_provider("openai", overwrite=False)
    assert not [s for s in saved if s[0] == ai_models.TASK_EYEBROW_ANALYSIS]

    # ب) اسلات خالی است: پر می‌شود
    monkeypatch.setattr(ai_models, "_slot_is_empty", lambda task_key, priority: True)
    saved.clear()
    ai_models.auto_configure_for_provider("openai", overwrite=False)
    assert [s for s in saved if s[0] == ai_models.TASK_EYEBROW_ANALYSIS and s[3] == "auto-vision"]
    # داور خروجی هنگام افزودن پروایدر خودکار پر نمی‌شود (تصمیم ادمین)
    assert not [s for s in saved if s[0] == ai_models.TASK_MIRROR_OUTPUT_VALIDATION]

    # ج) بازنویسی فقط با overwrite=True صریح انجام می‌شود
    monkeypatch.setattr(ai_models, "_slot_is_empty", lambda task_key, priority: False)
    saved.clear()
    ai_models.auto_configure_for_provider("openai", overwrite=True)
    assert [s for s in saved if s[0] == ai_models.TASK_EYEBROW_ANALYSIS]
