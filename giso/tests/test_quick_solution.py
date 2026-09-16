#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
تست مرحله ۴ از ۹: راه سریع (Quick Solution)

۱) پرامپت quick_solution.txt ساخته شده.
۲) _generate_quick_solution با AI mock محتوای JSON برمی‌گرداند.
۳) _default_quick_solution در صورت خطای AI fallback می‌دهد.
۴) صفحه /analysis/quick-solution رندر می‌شود و شامل: خلاصه وضعیت، ۳ قدم،
۵) report_type_viewed روی quick علامت‌گذاری می‌شود.
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
from giso.base import normalize_phone  # noqa: E402
from giso.analysis import _generate_quick_solution, _default_quick_solution  # noqa: E402

PHONE = "0919000066665"

QUICK_DATA = {
    "situation_summary": "موهات نیاز به آبرسانی داره.",
    "quick_steps": [
        {"step_number": 1, "title": "🧴 شامپوی مناسب", "description": "شامپوی بدون سولفات استفاده کن."},
        {"step_number": 2, "title": "💧 آبرسانی", "description": "ماسک آبرسان بزن."},
        {"step_number": 3, "title": "🚫 پرهیز", "description": "از اتو کمتر استفاده کن."},
    ],
    "consultant_intro": "سلام زهرا عزیز 🌸 خوشحالم که می‌خوای مشکلت رو حل کنی."
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


def _setup(app):
    with app.app_context():
        user = User.query.filter_by(phone=normalize_phone(PHONE)).first()
        if not user:
            user = User(phone=normalize_phone(PHONE),
                        password_hash="pbkdf2:sha256:260000$test$hash", name="زهرا")
            db.session.add(user)
            db.session.commit()
        a = Analysis(phone=normalize_phone(PHONE), user_id=user.id, type="hair",
                     photo_path="analysis/", ai_report_json=json.dumps(
                         {"status_label": "خوب", "overall_score": 75, "concerns": ["خشکی"]},
                         ensure_ascii=False))
        db.session.add(a)
        db.session.commit()
        return a.id


def _login(app, client):
    with client.session_transaction() as s:
        s["_user_id"] = normalize_phone(PHONE)


def test_prompt_exists():
    path = os.path.join(BASE_DIR, "giso", "prompts", "quick_solution.txt")
    assert os.path.exists(path)
    content = open(path, encoding="utf-8").read()
    for needle in ("summary_message", "quick_diagnosis", "three_actions", "consultant_intro",
                   "warning_signs", "{analysis_data}"):
        assert needle in content, needle
    print("PASS  پرامپت quick_solution.txt ساخته شد")


def test_generate_quick_solution_with_ai():
    app = create_app()
    with app.app_context():
        a = Analysis.query.filter_by(type="hair").first()
        if not a:
            a = Analysis(phone=normalize_phone(PHONE), type="hair", photo_path="analysis/",
                         ai_report_json="{}")
            db.session.add(a)
            db.session.commit()
        with patch("giso.analysis._call_text_ai",
                   return_value={"ok": True, "data": QUICK_DATA}):
            result = _generate_quick_solution(a)
    assert result is not None
    assert result["situation_summary"] == QUICK_DATA["situation_summary"]
    assert len(result["quick_steps"]) == 3
    assert result["consultant_intro"].startswith("سلام زهرا")
    print("PASS  _generate_quick_solution با AI محتوای JSON تولید می‌کند")


def test_default_quick_solution():
    d = _default_quick_solution({}, "زهرا", "hair")
    assert d["situation_summary"]
    assert len(d["quick_steps"]) == 3
    d2 = _default_quick_solution({}, "زهرا", "skin")
    assert len(d2["quick_steps"]) == 3
    print("PASS  _default_quick_solution fallback برای hair و skin")


def test_quick_solution_page_renders():
    app = create_app()
    client = app.test_client()
    _cleanup(app)
    aid = _setup(app)
    _login(app, client)

    with patch("giso.analysis._call_text_ai",
               return_value={"ok": True, "data": QUICK_DATA}):
        resp = client.get(f"/analysis/quick-solution?id={aid}")
    assert resp.status_code == 200, resp.status_code
    html = resp.get_data(as_text=True)

    assert "راه سریع رفع مشکل" in html
    assert QUICK_DATA["situation_summary"] in html
    assert QUICK_DATA["quick_steps"][0]["title"] in html
    # مشاور صادقی
    assert "مشاور هوشمند صادقی" in html
    assert "consultantChatBody" in html
    assert "consultant_avatar.jpg" in html
    assert "initConsultant" in html
    # لینک‌ها
    assert f"/analysis/plan?id={aid}" in html
    print("PASS  صفحه راه سریع رندر + خلاصه + ۳ قدم + مشاور + لینک‌ها")


def test_report_type_viewed_marked():
    app = create_app()
    client = app.test_client()
    _cleanup(app)
    aid = _setup(app)
    _login(app, client)
    with patch("giso.analysis._call_text_ai",
               return_value={"ok": True, "data": QUICK_DATA}):
        client.get(f"/analysis/quick-solution?id={aid}")
    with app.app_context():
        a = Analysis.query.get(aid)
        assert 'quick' in (a.report_type_viewed or '')
    print("PASS  report_type_viewed روی quick علامت‌گذاری شد")




def test_quick_solution_no_analysis_redirects():
    app = create_app()
    client = app.test_client()
    _cleanup(app)
    with app.app_context():
        user = User(phone=normalize_phone(PHONE),
                    password_hash="pbkdf2:sha256:260000$test$hash", name="زهرا")
        db.session.add(user)
        db.session.commit()
    _login(app, client)
    resp = client.get("/analysis/quick-solution", follow_redirects=False)
    # بدون تحلیل → redirect به analysis
    assert resp.status_code in (301, 302, 303, 307, 308)
    print("PASS  بدون تحلیل، به صفحه آنالیز ریدایرکت می‌شود")


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
