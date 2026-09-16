#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
تست خودکفای واحدهای ماژولار فاز ۲ (U1–U5)
فقط توابع خالص/بدون DB — بدون نیاز به Flask / SECRET_KEY / دیتابیس.
"""
import os
import sys
from unittest.mock import patch

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if BASE_DIR not in sys.path:
    sys.path.append(BASE_DIR)

# ---------- U1: analysis_report ----------
from giso.analysis_report import (_normalize_report_data, _build_metric_cards,
                                  _build_radar_points, _status_for_value)

NEW = {"overall_score": 68,
       "metrics": {"hydration": 45, "strength": 70},
       "main_problems": [{"name": "خشکی", "description": "کوتیکل باز"}],
       "strengths": ["استحکام"]}


def test_u1_analysis_report():
    n = _normalize_report_data(NEW, "hair")
    assert n["radar_metrics"]["آبرسانی"] == 45
    assert "خشکی — کوتیکل باز" in n["concerns"]
    assert len(_build_metric_cards(n, "hair")) == 6
    assert len(_build_radar_points(n, "hair")["values"]) == 6
    assert _status_for_value(95) == ("عالی", "good")


# ---------- U2: phones / db_core ----------
from giso.phones import normalize_phone, display_phone, _phone_variants, to_shamsi
from giso.db_core import GISO_DB_PATH, BOT_DB_PATH


def test_u2_phones_and_db_paths():
    assert normalize_phone("09123456789") == "+989123456789"
    assert normalize_phone("۰۹۱۲۳۴۵۶۷۸۹") == "+989123456789"
    assert normalize_phone("bad") == ""
    assert display_phone("+989123456789") == "09123456789"
    assert len(_phone_variants("+989123456789")) >= 3
    assert to_shamsi("2026-08-30 12:00:00").startswith("۱۴۰۵")
    assert str(GISO_DB_PATH).endswith("giso/data/giso.db")
    assert str(BOT_DB_PATH).endswith("bot_edu/data/bot.db")


# ---------- U4: ai_runtime_policy ----------
from giso.ai_runtime_policy import (_clean_text, _text_lc, _extract_id_from_text,
                                    _extract_amount_from_text, _jloads,
                                    _is_smalltalk_request, _mark_provider_cooldown,
                                    _provider_in_cooldown, _clear_provider_cooldown,
                                    DEFAULT_SETTINGS, SECTION_LABELS, resolve_actor_role)


def test_u4_ai_runtime_policy():
    assert resolve_actor_role() == "user"
    assert resolve_actor_role(4711, is_admin=True) == "admin"
    assert _clean_text("يبک") == "یبک"
    assert _text_lc("A") == "a"
    assert _extract_id_from_text("درخواست 42") == 42
    assert _extract_amount_from_text("مبلغ 50000 تومن") == 50000
    assert _jloads('{"a":1}', {}) == {"a": 1}
    assert _is_smalltalk_request("سلام") is True
    _mark_provider_cooldown("gemini", seconds=60)
    assert _provider_in_cooldown("gemini") is True
    _clear_provider_cooldown("gemini")
    assert _provider_in_cooldown("gemini") is False
    assert "chat_enabled" in DEFAULT_SETTINGS
    assert "consultant_chat" in SECTION_LABELS


# ---------- U5: wallet_core ----------
from giso.wallet_core import (POSTED_STATUSES, SCOPES, MISSION_EVENTS,
                              SERVICE_FEE_KEYS, SETTINGS_DEFAULTS,
                              WalletCheckoutError, _positive_int, _now)


def test_u5_wallet_core():
    assert POSTED_STATUSES == ("available", "used", "pending", "paid")
    assert SCOPES == ("cash", "spend")
    assert "registration" in MISSION_EVENTS and "bug_report_approved" in MISSION_EVENTS
    assert SERVICE_FEE_KEYS["marketplace"][0] == "wallet_fee_marketplace"
    assert SETTINGS_DEFAULTS["wallet_min_topup"] == "10000"
    assert _positive_int("5000", 0) == 5000
    assert _positive_int("-3", 10) == 0       # copied behavior
    assert len(_now()) == 19
    assert issubclass(WalletCheckoutError, RuntimeError)


def test_u5_wallet_bool_setting():
    from giso import wallet_core as wc
    with patch.object(wc, "_setting", return_value="1"):
        assert wc._bool_setting("x") is True
    with patch.object(wc, "_setting", return_value="0"):
        assert wc._bool_setting("x") is False


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    for fn in fns:
        fn()
        print(f"PASS  {fn.__name__}")
    print(f"\nALL {len(fns)} PHASE-2 UNIT TESTS PASSED ✔")
