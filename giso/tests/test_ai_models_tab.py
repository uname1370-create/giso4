#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""تب‌های مدیریت هوش مصنوعی پس از خلوت‌سازی و انتقال تب آینه گیسو.

بررسی می‌کند:
- دقیقاً چهار تب نهایی و ترتیب آن‌ها؛ تب‌های حذف‌شده (وضعیت، رفتار، زنجیره، نقش‌ها، عملیات، آینه گیسو) در قالب نیستند؛
- «مدیریت مدل‌ها» چهار دسته دارد و کنترل‌های اسلات (فعال، نوع فراخوانی، endpoint) در آن هستند؛
- وضعیت آمادگی و دکمه‌های پرکردن خودکار/اصلاح در «مدیریت مدل‌ها» هستند؛
- کنترل‌های روشن/خاموش مشاور و نام نمایشی در تب ویجت هستند و redirect آن‌ها به همان تب می‌رود؛
- routeها و handlerهای مخصوص تب‌های حذف‌شده از وب حذف شده‌اند.

این تست DB و شبکه را لمس نمی‌کند. رفتار واقعی JS مرورگر در اینجا بررسی نمی‌شود.
"""
import os
import re
import sys

import pytest

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if BASE_DIR not in sys.path:
    sys.path.append(BASE_DIR)

TEMPLATE = os.path.join(BASE_DIR, "giso", "panel", "templates", "modules", "ai.html")
AI_PY = os.path.join(BASE_DIR, "giso", "panel", "modules", "ai.py")
ROUTES_PY = os.path.join(BASE_DIR, "giso", "panel", "routes.py")
APP_PY = os.path.join(BASE_DIR, "giso", "app.py")

FINAL_TABS = ["providers", "models", "widget", "credits"]


def _read(path):
    with open(path, encoding="utf-8") as f:
        return f.read()


def _pane(src, key):
    start = src.index(f'id="pane-{key}"')
    end = src.find('<section class="pnl-pane', start + 1)
    return src[start:end if end != -1 else len(src)]


def test_exactly_the_final_tabs_in_order():
    src = _read(TEMPLATE)
    keys = re.findall(r'data-pane="([a-z-]+)"', src)
    assert keys == FINAL_TABS


def test_removed_tabs_and_beauty_pane_are_gone():
    src = _read(TEMPLATE)
    for removed in ("status", "behavior", "failover", "roles", "ops", "beauty-mirror"):
        assert f'id="pane-{removed}"' not in src, removed
        assert f'data-pane="{removed}"' not in src, removed
    assert "🪞" not in src


def test_each_final_tab_has_exactly_one_pane():
    src = _read(TEMPLATE)
    for key in FINAL_TABS:
        assert src.count(f'id="pane-{key}"') == 1, key


def test_model_card_lives_only_in_models_pane():
    src = _read(TEMPLATE)
    assert src.count('id="model-section"') == 1
    models = src.index('id="pane-models"')
    card = src.index('id="model-section"')
    widget = src.index('id="pane-widget"')
    assert models < card < widget


def test_models_pane_has_readiness_and_bulk_actions():
    models = _pane(_read(TEMPLATE), "models")
    assert "وضعیت آمادگی آینه گیسو" in models
    assert 'value="seed_model_slots"' in models
    assert 'value="repair_image_model_slots"' in models
    assert "panel.ai_provider_refresh_all_models" in models


def test_model_slots_have_enabled_and_image_controls():
    models = _pane(_read(TEMPLATE), "models")
    assert 'name="enabled_{{ slot.priority }}"' in models
    assert 'name="image_kind_{{ slot.priority }}"' in models
    assert 'name="endpoint_{{ slot.priority }}"' in models
    # فقط دستهٔ طراحی تصویر فیلدهای نوع فراخوانی دارد
    assert "cat.capability == 'image_gen'" in models


def test_providers_pane_has_no_model_selection_controls():
    providers_pane = _pane(_read(TEMPLATE), "providers")
    for marker in ("ms-form-", "slot_{{", "ai_model_section_save", "ai_model_section_test"):
        assert marker not in providers_pane, marker


def test_model_routes_and_form_fields_unchanged():
    src = _read(TEMPLATE)
    for endpoint in ("panel.ai_model_section_save", "panel.ai_model_section_test",
                     "panel.ai_provider_refresh_all_models"):
        assert endpoint in src, endpoint
    assert 'name="slot_{{ slot.priority }}"' in src
    assert 'name="category"' in src
    assert 'name="provider" value="{{ slot.provider }}"' in src
    assert 'name="model" value="{{ slot.model }}"' in src


def test_four_model_categories_including_output_evaluation():
    from giso.buti_ai.ai_models import MODEL_SECTION_CATEGORIES, TASK_MIRROR_OUTPUT_VALIDATION

    assert list(MODEL_SECTION_CATEGORIES.keys()) == [
        "text", "image_analysis", "image_generation", "output_evaluation",
    ]
    assert MODEL_SECTION_CATEGORIES["output_evaluation"]["task_key"] == TASK_MIRROR_OUTPUT_VALIDATION


def test_moved_advisor_controls_are_in_widget_pane():
    src = _read(TEMPLATE)
    widget = _pane(src, "widget")
    assert 'value="set_display_name"' in widget
    assert 'value="set_chat_enabled"' in widget
    assert "اسم نمایشی مشاور هوشمند" in widget
    assert "وضعیت مشاور هوشمند" in widget
    assert src.count('value="set_chat_enabled"') == 1
    assert src.count('value="set_display_name"') == 1


def test_config_redirect_maps_each_moved_action_to_its_tab():
    src = _read(AI_PY)
    assert '"set_chat_enabled": "#pane-widget"' in src
    assert '"set_display_name": "#pane-widget"' in src
    assert '"seed_model_slots": "#pane-models"' in src
    assert '"repair_image_model_slots": "#pane-models"' in src
    assert "anchors.get(action" in src


def test_beauty_web_actions_and_context_are_gone():
    src = _read(AI_PY)
    for name in ("save_beauty_mirror_model", "seed_beauty_mirror_models",
                 "repair_beauty_mirror_image_models", "build_category_view", 'data["beauty_mirror"]'):
        assert name not in src, name


def test_removed_routes_are_gone():
    src = _read(ROUTES_PY)
    for path in ("/ai/test-all", "/ai/chat-test", "/ai/pending/", "/ai/log/"):
        assert path not in src, path
    for fn in ("ai_test_all", "ai_chat_test", "ai_pending_execute",
               "ai_pending_cancel", "ai_log_rollback"):
        assert f"def {fn}(" not in src, fn


def test_removed_handlers_and_actions_are_gone():
    src = _read(AI_PY)
    for fn in ("handle_test_all", "handle_chat_test", "handle_pending_execute",
               "handle_pending_cancel", "handle_rollback"):
        assert f"def {fn}(" not in src, fn
    for action in ("set_active_provider", "promote_failover", "reset_failover", "save_role_policy"):
        assert f'action == "{action}"' not in src, action
    legacy = _read(APP_PY)
    for action in ("set_active_provider", "promote_failover", "reset_failover", "save_role_policy"):
        assert f'action == "{action}"' not in legacy, action


@pytest.mark.parametrize("form, expected_suffix", [
    ({"_back_tab": "models"}, "#pane-models"),
    ({"_back_tab": "status"}, ""),
    ({"_back_tab": "models#x"}, ""),
    ({}, ""),
])
def test_refresh_redirect_stays_on_models_tab_only(monkeypatch, form, expected_suffix):
    from flask import Flask

    import giso.panel.modules.ai as ai_mod

    monkeypatch.setattr(ai_mod, "url_for", lambda endpoint, **kw: "/admin/ai")
    app = Flask("models_tab_test")
    with app.test_request_context("/admin/ai/refresh", method="POST", data=form):
        resp = ai_mod._refresh_redirect()
    location = resp.headers["Location"]
    assert location.endswith("/admin/ai" + expected_suffix), location
