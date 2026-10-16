#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""تب «🧠 مدیریت مدل‌های هوش مصنوعی» (pane-models) در پنل AI.

بررسی می‌کند:
- تب و پنل مستقل وجود دارند، یکتا هستند و کلیدها با هم تطابق دارند؛
- کارت مدل‌ها فقط در تب مدل‌ها است و در تب پروایدرها تکرار نشده؛
- سه دسته واقعی و routeها/نام فیلدهای فرم بدون تغییر مانده‌اند؛
- redirectها به تب مدل‌ها می‌روند و دکمهٔ به‌روزرسانی فقط از همان تب آن را نگه می‌دارد.

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


def _read(path):
    with open(path, encoding="utf-8") as f:
        return f.read()


def test_models_tab_and_pane_exist_once():
    src = _read(TEMPLATE)
    assert src.count('data-pane="models"') == 1
    assert src.count('id="pane-models"') == 1


def test_every_tab_key_has_exactly_one_matching_pane():
    src = _read(TEMPLATE)
    keys = re.findall(r'data-pane="([a-z-]+)"', src)
    assert "models" in keys and "providers" in keys
    for key in keys:
        assert src.count(f'id="pane-{key}"') == 1, key


def test_model_card_lives_only_in_models_pane():
    src = _read(TEMPLATE)
    assert src.count('id="model-section"') == 1
    prov = src.index('id="pane-providers"')
    models = src.index('id="pane-models"')
    card = src.index('id="model-section"')
    status = src.index('id="pane-status"')
    assert prov < models < card < status


def test_providers_pane_has_no_model_selection_controls():
    src = _read(TEMPLATE)
    prov = src.index('id="pane-providers"')
    models = src.index('id="pane-models"')
    providers_pane = src[prov:models]
    for marker in ("ms-form-", "slot_{{", "ai_model_section_save", "ai_model_section_test"):
        assert marker not in providers_pane, marker


def test_model_routes_and_form_fields_unchanged():
    src = _read(TEMPLATE)
    for endpoint in ("panel.ai_model_section_save", "panel.ai_model_section_test",
                     "panel.ai_provider_refresh_all_models"):
        assert endpoint in src, endpoint
    assert 'name="slot_{{ slot.priority }}"' in src
    assert 'name="category" value="{{ cat.key }}"' in src or 'name="category"' in src
    assert 'name="provider" value="{{ slot.provider }}"' in src
    assert 'name="model" value="{{ slot.model }}"' in src


def test_exactly_three_model_categories():
    from giso.buti_ai.ai_models import MODEL_SECTION_CATEGORIES

    assert list(MODEL_SECTION_CATEGORIES.keys()) == ["text", "image_analysis", "image_generation"]


def test_model_redirects_point_to_models_tab_only():
    src = _read(AI_PY)
    assert "#model-section" not in src
    assert src.count('"#pane-models"') == 4  # save, test x2, refresh helper


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
