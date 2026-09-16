# -*- coding: utf-8 -*-
"""Regression tests for admin-request phrase routing before consultant AI."""
from pathlib import Path
from unittest.mock import patch

from giso.bot import _normalize_admin_phrase, _is_admin_request_phrase


def test_arabic_and_persian_letters_are_equivalent():
    assert _normalize_admin_phrase("درخواست ادمين گيسو") == "درخواست ادمین گیسو"
    assert _normalize_admin_phrase("درخواست ادمين گيسو").replace("ک", "ك") != ""
    assert _normalize_admin_phrase("كلمه ادميني") == "کلمه ادمینی"


def test_spacing_and_half_space_are_normalized():
    assert _normalize_admin_phrase("  درخواست   ادمین‌  گیسو  ") == "درخواست ادمین گیسو"


def test_configured_phrase_matches_normalized_user_input():
    with patch("giso.bot_helpers._admin_request_phrase", return_value="درخواست ادمین گیسو"):
        assert _is_admin_request_phrase("درخواست ادمين گيسو")
        assert _is_admin_request_phrase(" درخواست   ادمین‌ گیسو ")
        assert not _is_admin_request_phrase("درخواست مدیریت")


def test_phrase_guard_exists_before_ai_and_in_normal_user_route():
    source = (Path(__file__).resolve().parents[1] / "bot.py").read_text(encoding="utf-8")
    ai_guard = "if _is_consultant_ai_active(context) and _is_admin_request_phrase(text):"
    normal_guard = "if _is_admin_request_phrase(text):"
    ai_dispatch = "if _is_consultant_ai_active(context):"
    assert ai_guard in source
    ai_guard_index = source.index(ai_guard)
    assert ai_guard_index < source.index(ai_dispatch, ai_guard_index)
    assert source.index(normal_guard, ai_guard_index + len(ai_guard)) > ai_guard_index


def test_priority_guard_precedes_all_message_states_and_welcome():
    source = (Path(__file__).resolve().parents[1] / "bot.py").read_text(encoding="utf-8")
    start = source.index("async def handle_text")
    end = source.index("async def handle_error", start)
    block = source[start:end]
    priority = 'if existing and existing.get("contact_shared") and _is_admin_request_phrase(text):'
    assert priority in block
    assert block.index(priority) < block.index('waiting_shop_rev_txt_')
    assert block.index(priority) < block.index('should_show_rewelcome')


def test_admin_approval_is_super_only_and_result_driven():
    source = (Path(__file__).resolve().parents[1] / "bot.py").read_text(encoding="utf-8")
    block = source[source.index('elif data.startswith("adm_app|")'):source.index('elif data.startswith("adm_rej|")')]
    assert 'if not _is_super_admin(uid, phone)' in block
    assert 'result = review_admin_request' in block
    assert 'if not result or not result.get("ok")' in block
    assert 'پیام موفقیت کاذبی' in block
