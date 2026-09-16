#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
تست مرحله ۳ از ۹: زیرساخت مشاور هوشمند صادقی

۱) پرامپت‌های مشاور و خلاصه‌ساز ساخته شده‌اند و محتوای لازم را دارند.
۲) فیلدهای جدید دیتابیس (consultant_chat_history, consultant_key_notes,
   report_type_viewed, chat_rating) اضافه شده‌اند.
۳) _load_consultant_prompt پرامپت را با جای‌گذاری داده‌ها می‌سازد.
۴) _summarize_chat_history با تاریخچه کوتاه چیزی برنمی‌گرداند.
۵) APIهای چت (message, history, rate) با AI mock کار می‌کنند و تاریخچه ذخیره می‌شود.
"""
import json
import os
import sys
from unittest.mock import patch

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if BASE_DIR not in sys.path:
    sys.path.append(BASE_DIR)

from giso.app import create_app  # noqa: E402
from giso.models import db, User, Analysis, Product  # noqa: E402
from giso.base import normalize_phone  # noqa: E402
from giso.analysis import (_load_consultant_prompt, _summarize_chat_history,
                           _call_text_ai_raw)  # noqa: E402

PHONE = "0919000077776"


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


def _make_user_and_analysis(app):
    with app.app_context():
        user = User.query.filter_by(phone=normalize_phone(PHONE)).first()
        if not user:
            user = User(phone=normalize_phone(PHONE),
                        password_hash="pbkdf2:sha256:260000$test$hash", name="تستکاربر")
            db.session.add(user)
            db.session.commit()
        a = Analysis(phone=normalize_phone(PHONE), user_id=user.id, type="hair",
                     photo_path="analysis/", ai_report_json=json.dumps(
                         {"status_label": "خوب", "overall_score": 75}, ensure_ascii=False),
                     plan_json="{}")
        db.session.add(a)
        db.session.commit()
        aid = a.id
    return aid


def _login(app, client):
    with client.session_transaction() as s:
        s["_user_id"] = normalize_phone(PHONE)


# ── ۱) پرامپت‌ها ─────────────────────────────────────────────
def test_prompts_exist():
    for fn, needle in [("consultant_sadeghi.txt", "مشاور هوشمند صادقی"),
                       ("consultant_summarizer.txt", "حداکثر 500 کاراکتر")]:
        path = os.path.join(BASE_DIR, "giso", "prompts", fn)
        assert os.path.exists(path), f"{fn} ساخته نشده"
        content = open(path, encoding="utf-8").read().strip()
        assert needle in content, f"{fn} محتوای لازم را ندارد"
        assert len(content) > 100
        print(f"PASS  پرامپت {fn} ساخته شد")


# ── ۲) فیلدهای دیتابیس ────────────────────────────────────────
def test_db_columns_added():
    app = create_app()
    with app.app_context():
        # اجرای migration
        from giso.models import migrate_giso_tables
        migrate_giso_tables()
        cols = {c.name for c in Analysis.__table__.columns}
    for col in ("consultant_chat_history", "consultant_key_notes",
                "report_type_viewed", "chat_rating"):
        assert col in cols, f"ستون {col} در مدل نیست"
    print("PASS  فیلدهای جدید دیتابیس اضافه شدند")


# ── ۳) _load_consultant_prompt ────────────────────────────────
def test_load_consultant_prompt():
    products = [{"name": "شامپو", "price": 120000, "description": "شامپو گیاهی"}]
    chat = [{"role": "user", "content": "سلام"}, {"role": "assistant", "content": "سلام عزیز"}]
    prompt = _load_consultant_prompt(
        user_name="مریم", analysis_data={"status_label": "خوب"}, plan_data={},
        products=products, key_notes="کاربر نگران خشکی مو", chat_history=chat,
        user_message="چه شامپویی خوبه؟")
    assert prompt is not None
    assert "مریم" in prompt
    assert "شامپو" in prompt
    assert "چه شامپویی خوبه؟" in prompt
    assert "{user_name}" not in prompt and "{products_list}" not in prompt
    assert "کاربر نگران خشکی مو" in prompt
    print("PASS  _load_consultant_prompt پرامپت را با جای‌گذاری کامل می‌سازد")


# ── ۴) _summarize_chat_history کوتاه ─────────────────────────
def test_summarize_short_history_returns_empty():
    assert _summarize_chat_history([]) == ""
    assert _summarize_chat_history([{"role": "user", "content": "a"},
                                    {"role": "assistant", "content": "b"}]) == ""
    print("PASS  خلاصه‌ساز برای تاریخچه کوتاه چیزی برنمی‌گرداند")


def test_summarize_with_mock_ai():
    chat = [
        {"role": "user", "content": "من نگران خشکی موهام هستم"},
        {"role": "assistant", "content": "سلام عزیز، بررسی می‌کنم"},
        {"role": "user", "content": "شامپو طبیعی می‌خوام"},
        {"role": "assistant", "content": "شامپو گیاهی گیسو مناسب شماست"},
    ]
    with patch("giso.analysis._call_text_ai_raw",
               return_value={"ok": True, "text": "کاربر نگران خشکی مو و علاقه‌مند به محصولات طبیعی است."}):
        summary = _summarize_chat_history(chat)
    assert summary
    assert "خشکی" in summary
    assert len(summary) <= 500
    print("PASS  خلاصه‌ساز با AI mock کار می‌کند و ۵۰۰ کاراکتری است")


# ── ۵) API چت ─────────────────────────────────────────────────
def test_consultant_chat_api_flow():
    app = create_app()
    client = app.test_client()
    _cleanup(app)
    aid = _make_user_and_analysis(app)
    _login(app, client)

    # تاریخچه اولیه خالی
    r = client.get(f"/api/consultant-chat/history/{aid}")
    assert r.status_code == 200, r.status_code
    data = r.get_json()
    assert data["ok"] is True
    assert data["history"] == []

    # ارسال پیام (AI mock)
    fake_response = "سلام عزیز 🌸 بر اساس تحلیل شما، شامپوی مرطوب‌کننده مناسب است."
    async def _fake_chat(*args, **kwargs):
        return {"ok": True, "text": fake_response, "provider": "llm7", "model": "gpt-4o-mini"}
    with patch("giso.analysis.chat_with_managed_ai", side_effect=_fake_chat):
        r = client.post("/api/consultant-chat/message",
                        json={"analysis_id": aid, "message": "سلام"})
    assert r.status_code == 200, r.status_code
    data = r.get_json()
    assert data["ok"] is True
    assert data["response"] == fake_response
    assert data["message_count"] == 2

    # تاریخچه ذخیره شد
    r = client.get(f"/api/consultant-chat/history/{aid}")
    hist = r.get_json()["history"]
    assert len(hist) == 2
    assert hist[0]["role"] == "user" and hist[1]["role"] == "assistant"

    # امتیازدهی
    r = client.post("/api/consultant-chat/rate",
                    json={"analysis_id": aid, "rating": 5})
    assert r.status_code == 200, r.status_code
    assert r.get_json()["ok"] is True
    with app.app_context():
        a = Analysis.query.get(aid)
        assert a.chat_rating == 5
        assert a.consultant_chat_history is not None

    # امتیاز نامعتبر
    r = client.post("/api/consultant-chat/rate",
                    json={"analysis_id": aid, "rating": 9})
    assert r.status_code == 400
    print("PASS  API چت: تاریخچه ذخیره، پاسخ AI، امتیازدهی و اعتبارسنجی")


def test_consultant_chat_validation():
    app = create_app()
    client = app.test_client()
    _cleanup(app)
    aid = _make_user_and_analysis(app)
    _login(app, client)

    # پیام خالی
    r = client.post("/api/consultant-chat/message",
                    json={"analysis_id": aid, "message": "   "})
    assert r.status_code == 400, r.status_code
    print("PASS  API چت: پیام خالی رد می‌شود")


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
