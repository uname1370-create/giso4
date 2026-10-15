#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os
import sys

os.environ.setdefault("SECRET_KEY", "arena-test-secret-for-buti-ai-tests-32chars")
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if BASE_DIR not in sys.path:
    sys.path.append(BASE_DIR)

"""داور خروجی ابرو و لب: فقط تغییر صریح ناخواسته رد می‌کند؛ خطا یا نبود مدل باعث رد نمی‌شود."""
import asyncio  # noqa: F401,E402

from PIL import Image  # noqa: E402

import giso.buti_ai.output_judge as judge  # noqa: E402
import giso.buti_ai.ai_models as ai_models  # noqa: E402
import giso.ai_brain as brain  # noqa: E402


def _img(color=(10, 10, 10)):
    return Image.new("RGB", (32, 32), color)


def _fake_vision(text=None, ok=True, error="boom"):
    async def fake(provider_name, image_path, prompt, model=None, max_tokens=1200, timeout_override=None):
        if not ok:
            return {"ok": False, "error": error}
        return {"ok": True, "text": text}
    return fake


def test_ai_output_judge(monkeypatch):
    # خدمت خارج از دامنه (ناخن) داور AI ندارد
    res = judge.judge_output("nail", _img(), _img())
    assert res["checked"] is False and res["reason"] == "service_out_of_scope"

    # بدون مدل ارزیابی: بررسی AI انجام نمی‌شود، رد نمی‌شود
    monkeypatch.setattr(ai_models, "configured_vision_chain", lambda task_key=None: [])
    res = judge.judge_output("eyebrow", _img(), _img())
    assert res["checked"] is False and res["ok"] is None

    chain = [{"provider_name": "p1", "model_name": "m1"}]
    monkeypatch.setattr(ai_models, "configured_vision_chain", lambda task_key=None: chain)

    # تغییر ناخواسته تأیید شد: رد
    monkeypatch.setattr(brain, "ask_ai_vision", _fake_vision('{"only_target_changed": false, "unwanted_changes": "skin"}'))
    res = judge.judge_output("lip_shading", _img(), _img((200, 10, 10)))
    assert res["checked"] is True and res["ok"] is False and res["provider"] == "p1"

    # فقط ناحیهٔ هدف تغییر کرده: پذیرفته
    monkeypatch.setattr(brain, "ask_ai_vision", _fake_vision('{"only_target_changed": true, "unwanted_changes": ""}'))
    res = judge.judge_output("eyebrow", _img(), _img())
    assert res["checked"] is True and res["ok"] is True

    # خطای مدل: بررسی انجام نشده، خروجی رد نمی‌شود
    monkeypatch.setattr(brain, "ask_ai_vision", _fake_vision(ok=False))
    res = judge.judge_output("eyebrow", _img(), _img())
    assert res["checked"] is False and res["reason"] == "all_output_validation_models_failed"
    assert res["errors"]

    # پاسخ نامفهوم: بررسی انجام نشده
    monkeypatch.setattr(brain, "ask_ai_vision", _fake_vision("not json at all"))
    res = judge.judge_output("eyebrow", _img(), _img())
    assert res["checked"] is False

    # نسخهٔ فایلی: بدون تصویر قبل یا فایل خواندنی، بی‌اثر
    res = judge.judge_saved_file("eyebrow", None, "/nonexistent.png")
    assert res["checked"] is False and res["reason"] == "no_before_image"
    res = judge.judge_saved_file("eyebrow", _img(), "/nonexistent.png")
    assert res["checked"] is False and res["reason"].startswith("after_unreadable")
