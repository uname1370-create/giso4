#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
تست مرحله ۲ از ۹: دو دکمه (سریع / اصولی) در گزارش نهایی

۱) دو دکمه در پایین گزارش نهایی نمایش داده می‌شوند.
۲) رنگ‌بندی (سبز روشن cta-quick / طلایی روشن cta-complete) در CSS هست.
۳) انیمیشن gentle-pulse روی دکمه سریع هست.
۴) در موبایل دو دکمه زیر هم (grid-template-columns:1fr در media query).
۵) دکمه اصولی به /analysis/plan لینک می‌شود.
۶) دکمه سریع به /analysis/quick-solution لینک می‌شود.
۷) بخش summary-cta و cta-button-large قدیمی حذف شده.
"""
import json
import os
import sys

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if BASE_DIR not in sys.path:
    sys.path.append(BASE_DIR)

from giso.app import create_app  # noqa: E402
from giso.models import db, User, Analysis  # noqa: E402
from giso.base import normalize_phone  # noqa: E402

PHONE = "0919000099998"


def _make_report(app, atype, aid):
    """ساخت یک تحلیل با گزارش نهایی کامل برای تست رندر."""
    with app.app_context():
        rep = {
            "status_label": "خوب",
            "overall_score": 78,
            "consultant_message": "سلام، تحلیل شما آماده است.",
            "radar_metrics": {"بافت": 80, "رطوبت": 70, "درخشش": 75, "تراکم": 60,
                              "سلامت پوست سر": 65, "سلامت رنگ": 72},
            "strengths": ["موی سالم", "رنگ طبیعی"],
            "concerns": ["کمی خشکی", "تار شدن انتها"],
            "routine": {"daily_morning": "شامپو ملایم", "daily_evening": "ماسک رطوبت"},
        }
        a = Analysis.query.get(aid)
        a.ai_report_json = json.dumps(rep, ensure_ascii=False)
        a.type = atype
        db.session.commit()


def _login(app, client):
    with app.app_context():
        user = User.query.filter_by(phone=normalize_phone(PHONE)).first()
        if not user:
            user = User(phone=normalize_phone(PHONE),
                        password_hash="pbkdf2:sha256:260000$test$hash")
            db.session.add(user)
            db.session.commit()
        a = Analysis(phone=normalize_phone(PHONE), user_id=user.id, type="hair",
                     photo_path="analysis/", ai_report_json="{}")
        db.session.add(a)
        db.session.commit()
        aid = a.id
    with client.session_transaction() as s:
        s["_user_id"] = normalize_phone(PHONE)
    return aid


def _assert_cta(html, label, href, cls):
    # بررسی وجود دکمه با کلاس و لینک درست
    assert f'class="cta-choice {cls}"' in html, f"دکمه {label} با کلاس {cls} پیدا نشد"
    assert f'<a href="{href}" class="cta-choice {cls}"' in html, \
        f"دکمه {label} به {href} لینک نشده"


def test_hair_report_dual_cta():
    app = create_app()
    client = app.test_client()
    aid = _login(app, client)
    _make_report(app, "hair", aid)
    resp = client.get(f"/analysis/hair/report?id={aid}")
    assert resp.status_code == 200, resp.status_code
    html = resp.get_data(as_text=True)

    _assert_cta(html, "سریع", "/analysis/quick-solution", "cta-quick")
    _assert_cta(html, "اصولی", "/analysis/plan", "cta-complete")

    # هر دو متن دکمه
    assert "می‌خوام مشکل رو سریع رفع کنم" in html
    assert "می‌خوام مشکل رو اصولی و کامل رفع کنم" in html

    # انیمیشن gentle-pulse
    assert "gentle-pulse" in html
    assert ".cta-quick { animation: gentle-pulse" in html.replace("\n", " ") or "@keyframes gentle-pulse" in html

    # موبایل: دو دکمه زیر هم
    assert ".dual-cta-section{grid-template-columns:1fr;" in html.replace(" ", "").replace("\n", "")

    # حذف بخش قدیمی
    assert "summary-cta" not in html
    assert "cta-button-large" not in html

    # نکته ذخیره هر دو گزارش
    assert "هر دو گزارش در پروفایلتون ذخیره می‌شه" in html
    print("PASS  گزارش مو: دو دکمه درست + رنگ‌بندی + پالس + موبایل + لینک‌ها")


def test_skin_report_dual_cta():
    app = create_app()
    client = app.test_client()
    aid = _login(app, client)
    _make_report(app, "skin", aid)
    resp = client.get(f"/analysis/skin/report?id={aid}")
    assert resp.status_code == 200, resp.status_code
    html = resp.get_data(as_text=True)

    _assert_cta(html, "سریع", "/analysis/quick-solution", "cta-quick")
    _assert_cta(html, "اصولی", "/analysis/plan", "cta-complete")

    assert "می‌خوام مشکل رو سریع رفع کنم" in html
    assert "می‌خوام مشکل رو اصولی و کامل رفع کنم" in html
    assert "@keyframes gentle-pulse" in html
    assert "summary-cta" not in html
    assert "cta-button-large" not in html
    print("PASS  گزارش پوست: دو دکمه درست + لینک‌ها + بدون بخش قدیمی")


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
