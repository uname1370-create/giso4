#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
تست حذف «ثبت نظر اجباری»:

۱) کاربری که تحلیل قبلی بدون نظر دارد، باید بلافاصله بتواند تحلیل جدید را شروع کند
   (صفحه /analysis/hair بدون redirect به analysis_plan).
۲) حلقه redirect نباید وجود داشته باشد.
۳) روت /analysis/submit-review دیگر ثبت نشده و 404 می‌دهد.
۴) صفحه plan بدون بخش ثبت نظر درست رندر می‌شود.
"""
import os
import sys

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if BASE_DIR not in sys.path:
    sys.path.append(BASE_DIR)

from giso.app import create_app  # noqa: E402
from giso.models import db, User, Analysis  # noqa: E402
from giso.base import normalize_phone  # noqa: E402


def _cleanup(app):
    try:
        with app.app_context():
            for u in User.query.filter(User.phone.like("+98919000%")).all():
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


def test_new_analysis_starts_immediately_with_unreviewed_previous():
    """کاربر با تحلیل قبلیِ بدون نظر، مستقیم به صفحه آنالیز می‌رود (بدون redirect حلقه)."""
    app = create_app()
    client = app.test_client()
    phone = "09190000TESTREVIEW".replace("TESTREVIEW", "")  # placeholder
    _cleanup(app)
    try:
        with app.app_context():
            # ساخت کاربر
            phone = "09190000" + "1" + "2345"
            user = User.query.filter_by(phone=normalize_phone(phone)).first()
            if not user:
                user = User(phone=normalize_phone(phone), password_hash="pbkdf2:sha256:260000$test$hash")
                db.session.add(user)
                db.session.commit()
            uid = user.id
            # تحلیل قبلی با review_submitted=0 (بدون نظر)
            a = Analysis(phone=normalize_phone(phone), user_id=uid, type="hair", photo_path="analysis/",
                         review_submitted=0, ai_report_json="{}")
            db.session.add(a)
            db.session.commit()

        # لاگین کاربر
        with client.session_transaction() as s:
            s["_user_id"] = normalize_phone(phone)
        # درخواست صفحه آنالیز مو
        resp = client.get("/analysis/hair", follow_redirects=False)
        status = resp.status_code
        location = resp.headers.get("Location", "")
        is_redirect_to_plan = (status in (301, 302, 303, 307, 308)
                               and "analysis_plan" in location)
        assert not is_redirect_to_plan, \
            f"کاربر به analysis_plan ریدایرکت شد (حلقه redirect): {status} -> {location}"
        assert status == 200, f"expected 200, got {status} -> {location}"
        assert "آنالیز تخصصی مو" in resp.get_data(as_text=True)
        print("PASS  کاربرِ دارای تحلیلِ بدون نظر، مستقیم به آنالیز جدید می‌رود")
    finally:
        _cleanup(app)


def test_submit_review_route_removed():
    """روت /analysis/submit-review حذف شده و 404 می‌دهد."""
    app = create_app()
    client = app.test_client()
    resp = client.post("/analysis/submit-review", data={})
    assert resp.status_code == 404, f"expected 404, got {resp.status_code}"
    print("PASS  روت /analysis/submit-review حذف شده (404)")


def test_plan_page_renders_without_review_section():
    """صفحه plan بدون بخش ثبت نظر رندر می‌شود."""
    app = create_app()
    client = app.test_client()
    phone = "0919000012345"
    _cleanup(app)
    try:
        with app.app_context():
            user = User.query.filter_by(phone=normalize_phone(phone)).first()
            if not user:
                user = User(phone=normalize_phone(phone), password_hash="pbkdf2:sha256:260000$test$hash")
                db.session.add(user)
                db.session.commit()
            uid = user.id
            a = Analysis(phone=normalize_phone(phone), user_id=uid, type="hair", photo_path="analysis/",
                         review_submitted=0, plan_json="{}", ai_report_json="{}")
            db.session.add(a)
            db.session.commit()
            aid = a.id

        with client.session_transaction() as s:
            s["_user_id"] = normalize_phone(phone)
        resp = client.get(f"/analysis/plan?id={aid}", follow_redirects=False)
        assert resp.status_code == 200, f"expected 200, got {resp.status_code}"
        html = resp.get_data(as_text=True)
        assert "review-section" not in html, "بخش review هنوز وجود دارد"
        assert "thank-you-section" not in html, "بخش thank-you هنوز وجود دارد"
        assert "submit_analysis_review" not in html, "فرم ثبت نظر هنوز هست"
        assert "نظرت درباره تحلیل ما" not in html, "متن ثبت نظر هنوز هست"
        print("PASS  صفحه plan بدون بخش ثبت نظر رندر می‌شود")
    finally:
        _cleanup(app)


def test_no_redirect_loop_on_hair_and_skin():
    """هر دو صفحه hair و skin بدون حلقه redirect باز می‌شوند."""
    app = create_app()
    client = app.test_client()
    phone = "0919000012345"
    _cleanup(app)
    try:
        with app.app_context():
            user = User.query.filter_by(phone=normalize_phone(phone)).first()
            if not user:
                user = User(phone=normalize_phone(phone), password_hash="pbkdf2:sha256:260000$test$hash")
                db.session.add(user)
                db.session.commit()
            uid = user.id
            a = Analysis(phone=normalize_phone(phone), user_id=uid, type="hair", photo_path="analysis/",
                         review_submitted=0, ai_report_json="{}")
            db.session.add(a)
            db.session.commit()
        with client.session_transaction() as s:
            s["_user_id"] = normalize_phone(phone)
        for path in ("/analysis/hair", "/analysis/skin"):
            resp = client.get(path, follow_redirects=False)
            loc = resp.headers.get("Location", "")
            assert "analysis_plan" not in loc, f"redirect to plan on {path}"
            assert resp.status_code == 200, f"{path} -> {resp.status_code}"
        print("PASS  بدون حلقه redirect روی hair و skin")
    finally:
        _cleanup(app)


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
