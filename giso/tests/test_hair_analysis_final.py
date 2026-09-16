#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
تست مرحله ۸ نهایی - آنالیز مو کامل

۱) پرامپت‌های سه‌گانه (hair_final_analysis / quick_solution / plan_generator) بروز شده‌اند
   و ساختار JSON جدید را دارند.
۲) _normalize_report_data ساختار جدید (metrics/main_problems/weaknesses) را به
   قالب گزارش نرمال می‌کند (رادار/کارت‌ها/نگرانی‌ها).
۳) صفحه گزارش نهایی با ساختار جدید رندر می‌شود (مشکلات اصلی + اقدامات فوری + خلاصه).
۴) _generate_quick_solution با ساختار جدید (three_actions) کار می‌کند.
۵) ستون‌های جدید analyses (quick_solution_json / updated_at) وجود دارند.
۶) validate_hair انعطاف‌پذیر است (عکس متوسط قابل قبول).
"""
import json
import os
import sys
from unittest.mock import patch

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if BASE_DIR not in sys.path:
    sys.path.append(BASE_DIR)

from giso.app import create_app  # noqa: E402
from giso.models import db, User, Analysis  # noqa: E402
from giso.base import normalize_phone, get_giso_db_conn  # noqa: E402
from giso.analysis import (
    _normalize_report_data, _build_metric_cards, _build_radar_points,
    _generate_quick_solution, _default_quick_solution,
)  # noqa: E402

PHONE = "09190007777"

NEW_REPORT = {
    "overall_score": 68,
    "hair_type": "خشک",
    "condition": "موها به دلیل شرایط اخیر کمی خشک شده‌اند.",
    "main_problems": [
        {"name": "خشکی و شکنندگی", "severity": "متوسط",
         "description": "کوتیکل مو باز شده و رطوبت کم است."},
        {"name": "موخوره انتها", "severity": "کم",
         "description": "دو شاخه شدن انتهای موها."},
    ],
    "metrics": {"hydration": 45, "elasticity": 55, "strength": 70,
                "shine": 60, "scalp_health": 75, "growth_rate": 65},
    "strengths": ["استحکام خوب", "سلامت پوست سر"],
    "weaknesses": ["خشکی", "موخوره"],
    "immediate_actions": ["آبرسانی فوری", "قطع حرارت"],
    "avoid_list": ["سشوار داغ", "رنگ‌های شیمیایی"],
    "expected_timeline": "با ۶ هفته برنامه، بهبود محسوس می‌بینی.",
    "summary": "عزیز، موهات ذاتاً قوی هستن ولی کمی خشک شدن. با یک برنامه منظم به حالت قبل برمی‌گردن.",
    "status_label": "متوسط",
}


def _cleanup(app):
    try:
        with app.app_context():
            for u in User.query.filter(User.phone == normalize_phone(PHONE)).all():
                for a in Analysis.query.filter_by(phone=u.phone).all():
                    db.session.delete(a)
                db.session.delete(u)
            db.session.commit()
    except Exception:
        try:
            with app.app_context():
                db.session.rollback()
        except Exception:
            pass


def _setup(app, report=None):
    with app.app_context():
        user = User.query.filter_by(phone=normalize_phone(PHONE)).first()
        if not user:
            user = User(phone=normalize_phone(PHONE),
                        password_hash="pbkdf2:sha256:260000$test$hash", name="نگار")
            db.session.add(user)
            db.session.commit()
        a = Analysis(phone=normalize_phone(PHONE), user_id=user.id, type="hair",
                     photo_path="analysis/",
                     ai_report_json=json.dumps(report or NEW_REPORT, ensure_ascii=False))
        db.session.add(a)
        db.session.commit()
        return a.id


# ── ۱) پرامپت‌ها بروز شده‌اند ───────────────────────────────
def test_prompts_updated():
    files = {
        "hair_final_analysis.txt": ["main_problems", '"metrics"', "immediate_actions",
                                    "avoid_list", "expected_timeline", '"summary"'],
        "quick_solution.txt": ["summary_message", "quick_diagnosis", "three_actions",
                               "warning_signs"],
        "plan_generator.txt": ["weekly_plans", "nutrition_dos", "nutrition_donts",
                               "lifestyle_tips", "checklist"],
    }
    for fname, needles in files.items():
        path = os.path.join(BASE_DIR, "giso", "prompts", fname)
        assert os.path.exists(path), f"{fname} وجود ندارد"
        content = open(path, encoding="utf-8").read()
        for n in needles:
            assert n in content, f"{fname} فاقد {n}"
    print("PASS  پرامپت‌های سه‌گانه بروز شده و ساختار جدید دارند")


# ── ۲) نرمال‌سازی گزارش ساختار جدید ─────────────────────────
def test_normalize_report_new():
    norm = _normalize_report_data(dict(NEW_REPORT), "hair")
    # radar_metrics باید کلیدهای فارسی یکسان داشته باشد
    radar = norm.get("radar_metrics") or {}
    assert "آبرسانی" in radar and radar["آبرسانی"] == 45
    assert "سرعت رشد" in radar and radar["سرعت رشد"] == 65
    # کارت‌ها و رادار ساخته می‌شوند
    cards = _build_metric_cards(norm, "hair")
    assert len(cards) == 6
    radar_pts = _build_radar_points(norm, "hair")
    assert len(radar_pts["values"]) == 6
    # concerns از main_problems + weaknesses
    assert len(norm["concerns"]) == 4  # 2 مشکل + 2 ضعف
    # وضعیت از امتیاز
    assert norm.get("status_label")
    print("PASS  _normalize_report_data ساختار جدید را نرمال می‌کند")


# ── ۳) نرمال‌سازی گزارش ساختار قدیمی ────────────────────────
def test_normalize_report_legacy():
    legacy = {
        "overall_score": 80,
        "radar_metrics": {"رطوبت": 70, "درخشش": 75, "سلامت پوست سر": 80},
        "strengths": ["موی سالم"],
        "concerns": ["خشکی"],
        "routine": {"daily_morning": "شامپو", "daily_evening": "ماسک"},
    }
    norm = _normalize_report_data(legacy, "hair")
    radar = norm.get("radar_metrics") or {}
    assert "آبرسانی" in radar and radar["آبرسانی"] == 70  # رطوبت → آبرسانی
    assert radar["درخشش"] == 75
    assert norm["concerns"] == ["خشکی"]
    print("PASS  _normalize_report_data ساختار قدیمی را حفظ می‌کند")


# ── ۴) صفحه گزارش با ساختار جدید رندر می‌شود ────────────────
def test_report_page_new_structure():
    app = create_app()
    client = app.test_client()
    _cleanup(app)
    aid = _setup(app)
    with client.session_transaction() as s:
        s["_user_id"] = normalize_phone(PHONE)
    resp = client.get(f"/analysis/hair/report?id={aid}")
    assert resp.status_code == 200, resp.status_code
    html = resp.get_data(as_text=True)
    # مشکلات اصلی + اقدامات فوری + خلاصه
    assert "مشکلات اصلی" in html
    assert "خشکی و شکنندگی" in html
    assert "شدت: متوسط" in html
    assert "اقداماتی که فوراً" in html
    assert "آبرسانی فوری" in html
    assert "سشوار داغ" in html  # avoid_list
    assert "زمان نتیجه" in html  # expected_timeline
    assert "به حالت قبل" in html  # summary
    # کارت‌های متریک
    assert "آبرسانی" in html
    print("PASS  صفحه گزارش نهایی با ساختار جدید رندر می‌شود")
    _cleanup(app)


# ── ۵) _generate_quick_solution با ساختار جدید ──────────────
def test_quick_solution_new_structure():
    app = create_app()
    with app.app_context():
        a = Analysis.query.filter_by(type="hair").first()
        if not a:
            a = Analysis(phone=normalize_phone(PHONE), type="hair",
                         photo_path="analysis/", ai_report_json=json.dumps(NEW_REPORT))
            db.session.add(a)
            db.session.commit()
        new_data = {
            "summary_message": "سلام نگار عزیز! یه راهکار سریع برات آماده کردم.",
            "quick_diagnosis": "مهم‌ترین مشکلت خشکی موئه.",
            "three_actions": [
                {"title": "آبرسانی", "description": "ماسک بزن", "time_frame": "این هفته"},
                {"title": "روتین", "description": "شامپو ملایم", "time_frame": "۲ هفته"},
                {"title": "بلندمدت", "description": "ترمیم", "time_frame": "۱ ماه"},
            ],
            "consultant_intro": "سلام نگار!",
            "warning_signs": ["ریزش ناگهانی"],
        }
        with patch("giso.analysis._call_text_ai",
                   return_value={"ok": True, "data": new_data}):
            result = _generate_quick_solution(a)
    assert result is not None
    assert result["situation_summary"] == new_data["summary_message"]
    assert result["quick_diagnosis"] == new_data["quick_diagnosis"]
    assert len(result["three_actions"]) == 3
    assert result["three_actions"][0]["time_frame"] == "این هفته"
    assert result["warning_signs"] == ["ریزش ناگهانی"]
    print("PASS  _generate_quick_solution ساختار جدید (three_actions) را می‌پذیرد")


# ── ۶) ستون‌های جدید analyses ───────────────────────────────
def test_new_db_columns():
    app = create_app()
    try:
        with app.app_context():
            a = Analysis(phone=normalize_phone(PHONE), type="hair", photo_path="analysis/",
                         quick_solution_json="{}", updated_at="2026-08-05")
            db.session.add(a)
            db.session.commit()
            a2 = Analysis.query.get(a.id)
            assert a2.quick_solution_json == "{}"
            assert a2.updated_at == "2026-08-05"
            db.session.delete(a2)
            db.session.commit()
        print("PASS  ستون‌های quick_solution_json و updated_at در analyses وجود دارند")
    finally:
        pass


# ── ۷) validate_hair انعطاف‌پذیر ─────────────────────────────
def test_validate_hair_flexible():
    path = os.path.join(BASE_DIR, "giso", "prompts", "validate_hair.txt")
    content = open(path, encoding="utf-8").read()
    for n in ("انعطاف", "valid=true", "warnings", "قابل تشخیصه"):
        assert n in content, n
    print("PASS  validate_hair انعطاف‌پذیر است (عکس متوسط قابل قبول)")


def _run():
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    passed = 0
    for t in tests:
        try:
            t()
            passed += 1
        except AssertionError as e:
            print(f"FAIL  {t.__name__}: {e}")
        except Exception as e:  # noqa: BLE001
            print(f"ERROR {t.__name__}: {type(e).__name__}: {e}")
    print(f"\n{passed}/{len(tests)} passed")
    return passed == len(tests)


if __name__ == "__main__":
    sys.exit(0 if _run() else 1)
