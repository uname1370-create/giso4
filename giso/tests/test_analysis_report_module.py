#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
تست مستقل ماژول giso/analysis_report.py (Phase 2 Unit U1)
بدون نیاز به Flask / SQLAlchemy / DB — فقط استاندارد lib.
"""
import sys
import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if BASE_DIR not in sys.path:
    sys.path.append(BASE_DIR)

from giso.analysis_report import (
    _normalize_report_data, _status_for_value,
    _build_metric_cards, _build_strength_items, _build_concern_items,
    _build_routine_cards, _build_radar_points,
)

NEW_REPORT = {
    "overall_score": 68,
    "metrics": {"hydration": 45, "elasticity": 55, "strength": 70,
                "shine": 60, "scalp_health": 75, "growth_rate": 65},
    "main_problems": [{"name": "خشکی و شکنندگی", "severity": "متوسط",
                       "description": "کوتیکل مو باز شده و رطوبت کم است."}],
    "weaknesses": ["موخوره"],
    "strengths": ["استحکام خوب", "سلامت پوست سر"],
    "routine": {"morning": "آبرسانی", "evening": "ماسک هفتگی"},
}


def test_normalize_new_structure():
    n = _normalize_report_data(NEW_REPORT, "hair")
    assert n["radar_metrics"]["آبرسانی"] == 45
    assert n["radar_metrics"]["استحکام"] == 70
    assert "خشکی و شکنندگی — کوتیکل مو باز شده و رطوبت کم است." in n["concerns"]
    assert n["strengths"] == ["استحکام خوب", "سلامت پوست سر"]
    assert n["status_label"] == "متوسط"


def test_normalize_legacy_structure():
    legacy = {"overall_score": 75, "radar_metrics": {"رطوبت": 80, "انعطاف": 70},
              "concerns": ["ریزش مو"]}
    n = _normalize_report_data(legacy, "hair")
    assert n["radar_metrics"]["آبرسانی"] == 80
    assert n["radar_metrics"]["انعطاف‌پذیری"] == 70
    assert n["concerns"] == ["ریزش مو"]


def test_status_for_value():
    assert _status_for_value(95) == ("عالی", "good")
    assert _status_for_value(80) == ("خوب", "ok")
    assert _status_for_value(60) == ("متوسط", "mid")
    assert _status_for_value(30) == ("نیاز به توجه", "low")


def test_build_metric_cards():
    n = _normalize_report_data(NEW_REPORT, "hair")
    cards = _build_metric_cards(n, "hair")
    assert len(cards) == 6
    assert cards[0]["key"] == "آبرسانی" and cards[0]["value"] == 45
    assert cards[0]["status_label"] == "نیاز به توجه"


def test_strength_and_concern_items():
    n = _normalize_report_data(NEW_REPORT, "hair")
    st = _build_strength_items(n, "hair")
    assert st[0]["text"] == "استحکام خوب" and st[0]["action"]
    cn = _build_concern_items(n)
    assert cn[0]["text"].startswith("خشکی") and cn[0]["solution"]


def test_routine_cards_filters_empty():
    n = _normalize_report_data(NEW_REPORT, "hair")
    cards = _build_routine_cards(n, "hair")
    assert len(cards) == 2  # فقط صبح و شب (ظهر/هفتگی خالی → حذف)


def test_radar_points():
    n = _normalize_report_data(NEW_REPORT, "hair")
    pts = _build_radar_points(n, "hair")
    assert len(pts["values"]) == 6
    assert len(pts["rings"]) == 3
    assert len(pts["labels"]) == 6
    assert len(pts["pts_str"].split()) == 6
    pts_skin = _build_radar_points(n, "skin")
    assert pts_skin["values"][0][0] == "هیدراسیون"


def test_return_contract_of_normalize():
    # ورودی نامعتبر نباید کرش کند
    n = _normalize_report_data(None, "hair")
    assert isinstance(n, dict) and n["radar_metrics"] == {}
    n2 = _normalize_report_data("not-a-dict", "hair")
    assert isinstance(n2, dict)


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn()
        print(f"PASS  {fn.__name__}")
    print(f"\nALL {len(fns)} TESTS PASSED (no Flask/DB needed)")
