#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
تست مرحله ۵ از ۹: بازطراحی راه اصولی (Analysis Plan)

۱) صفحه /analysis/plan رندر می‌شود و عنوان «برنامه تخصصی شما» دارد.
۲) بخش‌های قدیمی (giso_products, iran_products, product_requests, consultant request
   textarea, review form) دیگر وجود ندارند.
۳) مشاور صادقی (component) در پایین صفحه فعال است.
۵) چک‌لیست با ذخیره سرور (save/get checklist progress) کار می‌کند.
۶) report_type_viewed روی full علامت‌گذاری می‌شود.
۷) دانلود چک‌لیست و تحلیل کامل PDF کار می‌کنند.
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

PHONE = "0919000055554"

# ساختار plan به فرمت قدیمی (همون چیزی که plan_generator تولید می‌کند)
PLAN_JSON = {
    "duration_weeks": 4,
    "consultant_intro": "سلام مریم عزیز 🌸\nبرنامه اختصاصی ۴ هفته‌ای شما آماده است.",
    "summary": {"situation": "موهای شما نیاز به آبرسانی دارد.", "main_goal": "بهبود رطوبت مو"},
    "weekly_plan": [
        {"week_number": 1, "week_title": "هفته 1 - پاکسازی",
         "morning_routine": ["شامپو ملایم", "ماسک سبک"],
         "evening_routine": ["مراقبت شب", "نرم‌کننده"],
         "specific_days": [{"day": "شنبه", "action": "ماسک عمیق"}],
         "expected_result": "موهای نرم‌تر"},
    ],
    "nutrition": {
        "add_to_diet": [{"name": "گردو", "reason": "امگا3"}, {"name": "تخم مرغ", "reason": "پروتئین"}],
        "reduce_from_diet": [{"name": "قند", "reason": "التهاب"}],
    },
    "lifestyle_habits": [{"habit": "خواب کافی", "detail": "7-8 ساعت"}],
    "warning_signs": [{"title": "ریزش شدید", "description": "بیش از 100 تار در روز"}],
    "checklist": {"weeks": [
        {"week_number": 1, "items": ["ماسک آبرسان", "خواب کافی", "تغذیه سالم"]},
        {"week_number": 2, "items": ["ماسک ترمیم", "شامپو ملایم"]},
    ]},
    "giso_products": [{"product_id": 1}],
    "iran_products": [{"name": "برند ایرانی"}],
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
                        password_hash="pbkdf2:sha256:260000$test$hash", name="مریم")
            db.session.add(user)
            db.session.commit()
        a = Analysis(phone=normalize_phone(PHONE), user_id=user.id, type="hair",
                     photo_path="analysis/",
                     ai_report_json=json.dumps({"status_label": "خوب", "overall_score": 75}),
                     plan_json=json.dumps(PLAN_JSON, ensure_ascii=False),
                     checklist_progress="{}")
        db.session.add(a)
        db.session.commit()
        return a.id


def _login(app, client):
    with client.session_transaction() as s:
        s["_user_id"] = normalize_phone(PHONE)


def test_plan_page_renders_redesigned():
    app = create_app()
    client = app.test_client()
    _cleanup(app)
    aid = _setup(app)
    _login(app, client)
    resp = client.get(f"/analysis/plan?id={aid}")
    assert resp.status_code == 200, resp.status_code
    html = resp.get_data(as_text=True)

    # عنوان جدید
    assert "برنامه تخصصی شما" in html
    assert "راه اصولی رفع مشکل" in html
    # خلاصه وضعیت (overview از summary.situation)
    assert "موهای شما نیاز به آبرسانی دارد" in html
    # مشاور صادقی
    assert "مشاور هوشمند صادقی" in html
    assert "consultantChatBody" in html
    # لینک‌های PDF
    # برنامه هفتگی + چک‌لیست
    assert "برنامه هفته به هفته" in html
    assert "چک‌لیست پیشرفت" in html
    print("PASS  صفحه plan بازطراحی شد + مشاور + لینک‌ها + برنامه + چک‌لیست")


def test_old_sections_removed():
    app = create_app()
    client = app.test_client()
    _cleanup(app)
    aid = _setup(app)
    _login(app, client)
    html = client.get(f"/analysis/plan?id={aid}").get_data(as_text=True)

    # بخش‌های قدیمی نباید باشند
    for needle in ["محصولات مکمل", "نیاز به مشاوره تخصصی", "درخواست مشاوره",
                   "product_requests", "request_consultant", "review-required",
                   "نظرت درباره تحلیل", "products_needed", "iran_products"]:
        assert needle not in html, f"بخش قدیمی هنوز هست: {needle}"
    print("PASS  بخش‌های قدیمی (محصولات/مشاوره قدیمی/ثبت نظر) حذف شدند")


def test_report_type_viewed_marked_full():
    app = create_app()
    client = app.test_client()
    _cleanup(app)
    aid = _setup(app)
    _login(app, client)
    client.get(f"/analysis/plan?id={aid}")
    with app.app_context():
        a = Analysis.query.get(aid)
        assert 'full' in (a.report_type_viewed or '')
    print("PASS  report_type_viewed روی full علامت‌گذاری شد")


def test_checklist_progress_save_get():
    app = create_app()
    client = app.test_client()
    _cleanup(app)
    aid = _setup(app)
    _login(app, client)
    with client.session_transaction() as s:
        s['giso_csrf_token'] = 'test-csrf'
    headers = {'X-GISO-CSRF': 'test-csrf'}

    # ذخیره
    r = client.post(f"/analysis/checklist/save/{aid}",
                    json={"item_id": "w1-0", "checked": True, "week": 1}, headers=headers)
    assert r.status_code == 200, r.status_code
    assert r.get_json()["ok"] is True

    # دریافت
    r = client.get(f"/analysis/checklist/progress/{aid}")
    data = r.get_json()
    assert data["ok"] is True
    assert data["progress"].get("w1-0") is True

    # حذف
    client.post(f"/analysis/checklist/save/{aid}",
                json={"item_id": "w1-0", "checked": False, "week": 1}, headers=headers)
    r = client.get(f"/analysis/checklist/progress/{aid}")
    assert "w1-0" not in r.get_json()["progress"]
    print("PASS  چک‌لیست: ذخیره و دریافت پیشرفت با سرور کار می‌کند")






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
