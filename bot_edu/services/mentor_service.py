# -*- coding: utf-8 -*-
"""
mentor_service — منطق مشترک «یار هوشمند شغلی / یار همراه من».

این فایل یک façade تمیز روی:
    • وضعیت وب (web_identity_career_state) تا زمان مهاجرت کامل به ai_mentor
    • جداول واقعی ai_mentor (user_profiles, career_paths, ai_certificates,
      interview_simulations, ai_chat_history, real_missions, ...)
    • ai_brain به‌عنوان موتور (نه به‌عنوان فلوی مستقیم)
    • ai_mentor.module_enabled() برای سنجش دردسترس‌بودن

نه وب و نه ربات مستقیماً ai_brain را برای گفتگوی عادی صدا نمی‌زنند؛ همه از
طریق این سرویس عمل می‌کنند تا یک فلوی واحد داشته باشیم.
"""
from __future__ import annotations
import json, logging, os, sqlite3, sys, time as _time
from pathlib import Path
from typing import Any

_BOT_DIR = Path(__file__).resolve().parent.parent
if str(_BOT_DIR) not in sys.path:
    sys.path.insert(0, str(_BOT_DIR))

from phoneutil import normalize_phone  # noqa: E402

logger = logging.getLogger(__name__)

_DB = _BOT_DIR / "data" / "bot.db"

_MCONN: sqlite3.Connection | None = None


def _conn() -> sqlite3.Connection:
    global _MCONN
    if _MCONN is not None:
        try:
            _MCONN.execute("SELECT 1").fetchone()
            return _MCONN
        except Exception:
            try: _MCONN.close()
            except Exception: pass
            _MCONN = None
    c = sqlite3.connect(str(_DB), check_same_thread=False)
    c.row_factory = sqlite3.Row
    try:
        c.execute("PRAGMA journal_mode=WAL")
        c.execute("PRAGMA foreign_keys=ON")
    except Exception:
        pass
    _MCONN = c
    _ensure_tables(c)
    return c


def _ensure_tables(c: sqlite3.Connection):
    # جدول‌های وضعیت وب (سازگاری با قبل)
    try:
        c.execute("""
            CREATE TABLE IF NOT EXISTS web_identity_career_state (
                id INTEGER PRIMARY KEY, phone TEXT DEFAULT '', user_id INTEGER NOT NULL UNIQUE,
                onboarding_completed INTEGER DEFAULT 0, career_goal TEXT DEFAULT '',
                experience_level TEXT DEFAULT '', daily_hours INTEGER DEFAULT 0,
                career_purpose TEXT DEFAULT '', current_step INTEGER DEFAULT 1,
                chat_history TEXT DEFAULT '[]', mentor_data TEXT DEFAULT '{}',
                updated_at TEXT DEFAULT ''
            )""")
        c.execute("""
            CREATE TABLE IF NOT EXISTS web_identity_auth (
                id INTEGER PRIMARY KEY, phone TEXT UNIQUE NOT NULL, user_id INTEGER,
                password_hash TEXT NOT NULL DEFAULT '', security_q_key TEXT DEFAULT '',
                security_answer_hash TEXT DEFAULT '', created_at TEXT DEFAULT '',
                last_login TEXT DEFAULT ''
            )""")
        c.commit()
    except Exception as e:
        logger.debug("ensure web tables: %s", e)


def _jloads(raw, default=None):
    if not raw:
        return {} if default is None else default
    if isinstance(raw, (dict, list)):
        return raw
    try: return json.loads(raw)
    except Exception: return {} if default is None else default


# --- فعال بودن AI/mentor -------------------------------------------------
def _ai_mentor_enabled() -> bool:
    """ماژول واقعی ai_mentor فعال است؟"""
    try:
        from ai_mentor.ai_handlers import module_enabled
        return bool(module_enabled())
    except Exception:
        try:
            from config import AI_MENTOR_ENABLED
            return bool(AI_MENTOR_ENABLED)
        except Exception:
            return False


def _ai_ready() -> bool:
    """آیا حداقل یک پرووایدر AI کلید دارد؟"""
    if not _ai_mentor_enabled():
        return False
    try:
        import ai_brain as _ab
        provs = _ab.list_ai_providers(only_enabled=True)
        for p in provs:
            if p.get("enabled") and p.get("api_key") and str(p.get("api_key")).strip():
                return True
        return False
    except Exception:
        return False


MENTOR_ONBOARDING_QUESTIONS = [
    {"step":1,"key":"career_goal","title":"هدف شغلی","hint":"مثلاً می‌خوام مهندس پایتون بشم"},
    {"step":2,"key":"experience_level","title":"سطح تجربه","hint":"مبتدی / متوسط / پیشرفته"},
    {"step":3,"key":"daily_hours","title":"ساعت مطالعه روزانه","hint":"عدد بنویس (مثلاً 2)"},
    {"step":4,"key":"career_purpose","title":"هدف نهایی","hint":"استخدام / فریلنس / ارتقا / علاقه"},
]


def get_mentor_state(user_id: int) -> dict:
    c = _conn()
    try:
        row = c.execute("SELECT * FROM web_identity_career_state WHERE user_id=?",
                        (int(user_id),)).fetchone()
        if row:
            return dict(row)
        from services import user_service
        u = user_service.get_user(user_id)
        phone = u["phone"] if u else ""
        now = _time.strftime("%Y-%m-%d %H:%M:%S")
        c.execute(
            "INSERT INTO web_identity_career_state (phone,user_id,onboarding_completed,current_step,updated_at) "
            "VALUES (?,?,0,1,?)", (phone, int(user_id), now))
        c.commit()
        return dict(c.execute("SELECT * FROM web_identity_career_state WHERE user_id=?",
                              (int(user_id),)).fetchone())
    finally:
        pass


def save_mentor_step(user_id: int, step: int, answer: str) -> dict:
    st = get_mentor_state(user_id)
    answer = (answer or "").strip()
    if step < 1 or step > 4:
        return {"completed": False, "next_step": st.get("current_step") or 1, "reply": "مرحله نامعتبر است."}
    updates: dict[str, Any] = {}
    if step == 1:
        if not answer:
            return {"completed": False, "next_step": 1, "reply": "لطفاً هدف خود را بنویسید."}
        updates["career_goal"] = answer; next_step, reply = 2, "عالی! چه سطح تجربه‌ای داری؟"
    elif step == 2:
        if not answer:
            return {"completed": False, "next_step": 2, "reply": "سطح تجربه را بنویسید."}
        updates["experience_level"] = answer; next_step, reply = 3, "چند ساعت در روز می‌تونی مطالعه کنی؟ (عدد بنویس)"
    elif step == 3:
        try:
            dh = max(0, int(answer))
        except Exception:
            return {"completed": False, "next_step": 3, "reply": "لطفاً یک عدد معتبر وارد کن (مثلاً 2)."}
        updates["daily_hours"] = dh; next_step, reply = 4, "هدف نهایی‌ات از این مسیر چیه؟"
    else:
        if not answer:
            return {"completed": False, "next_step": 4, "reply": "هدف نهایی را بنویسید."}
        updates["career_purpose"] = answer; next_step = 5
        updates["onboarding_completed"] = 1
        updates["current_step"] = 5
        _apply_updates(user_id, updates)
        # اگر ai_mentor واقعی پروفایل دارد، سعی در sync کردن داریم
        _bootstrap_into_ai_mentor(user_id)
        return {"completed": True, "next_step": 5,
                "reply": "✅ اطلاعاتت ثبت شد! یار همراه من الان برای تو آماده است."}
    updates["current_step"] = next_step
    _apply_updates(user_id, updates)
    return {"completed": False, "next_step": next_step, "reply": reply}


def _apply_updates(user_id: int, updates: dict):
    updates["updated_at"] = _time.strftime("%Y-%m-%d %H:%M:%S")
    sets = ", ".join(f"{k}=?" for k in updates)
    vals = list(updates.values()) + [int(user_id)]
    c = _conn()
    c.execute(f"UPDATE web_identity_career_state SET {sets} WHERE user_id=?", vals)
    c.commit()


def _bootstrap_into_ai_mentor(user_id: int):
    """در صورت فعال بودن ai_mentor، یک profile اولیه می‌سازد تا فلوی واقعی قابل ادامه باشد."""
    if not _ai_mentor_enabled():
        return
    try:
        from ai_mentor import ai_db
        st = get_mentor_state(user_id)
        prof = ai_db.get_user_profile(user_id)
        if prof:
            return
        ai_db.upsert_user_profile(user_id, name="", age=0, city="",
                                   goal=st.get("career_goal") or "",
                                   level=st.get("experience_level") or "",
                                   daily_hours=int(st.get("daily_hours") or 0))
    except Exception as e:
        logger.debug("bootstrap ai_mentor profile: %s", e)


# --- chat ---------------------------------------------------------------
def _call_ai(prompt: str, max_tokens: int = 600) -> str:
    """
    # TODO: محل پیاده‌سازی روش جدید ارتباط با موتور هوش مصنوعی طبق دستور کاربر
    """
    return ""


def mentor_chat(user_id: int, message: str) -> str:
    """
    گفتگو با یار هوشمند در وب‌سایت.
    # TODO: محل پیاده‌سازی روش جدید ارتباطی کاربر و سایت با هوش مصنوعی
    """
    st = get_mentor_state(user_id)
    reply_text = "سلام! پاسخ یار هوشمند (در انتظار پیاده‌سازی روش جدید ارتباط با AI طبق دستور کاربر)"
    _append_chat(user_id, message, reply_text)
    return reply_text


def _append_chat(user_id: int, user_msg: str, bot_reply: str):
    try:
        c = _conn()
        st = c.execute("SELECT chat_history FROM web_identity_career_state WHERE user_id=?",
                       (int(user_id),)).fetchone()
        h = _jloads(st["chat_history"] if st else "[]", default=[])
        h.append({"role":"user","text":user_msg,"ts":int(_time.time())})
        h.append({"role":"bot","text":bot_reply,"ts":int(_time.time())})
        if len(h) > 100: h = h[-100:]
        c.execute("UPDATE web_identity_career_state SET chat_history=? WHERE user_id=?",
                  (json.dumps(h, ensure_ascii=False), int(user_id)))
        c.commit()
    except Exception:
        pass


def _real_fallback(msg: str, st: dict) -> str:
    goal = st.get("career_goal") or "مسیر شغلی"
    return (
        f"خوش اومدی! هدفت «{goal}» ثبت شده.\n\n"
        "در حال حاضر می‌تونی از این بخش‌ها استفاده کنی:\n"
        "• 📚 دوره‌ها و 🎯 ماموریت‌ها از «پنل کاربری من» در دسترس‌اند.\n"
        "• 💎 گنجینه امتیازی برای خرج اعتبارها.\n"
        "• 📄 گواهینامه‌ها و گزارش‌های مسیر با فعال شدن کلید AI از همین‌جا قابل تولیدند.\n"
        "اگر سوال خاصی داری بپرس؛ با تنظیم کلید AI پاسخ هوشمند دقیق‌تر می‌گیری."
    )


# --- feature flags ------------------------------------------------------
def mentor_feature_flags(user_id: int) -> dict:
    ai_on = _ai_mentor_enabled()
    kbd = _ai_ready()
    prof = mentor_profile(user_id)
    return {
        "chat": True,
        "continue_path": bool(prof["paths"]),
        "trends": ai_on and kbd,
        "interview": ai_on and kbd,
        "missions": True,
        "wallet": True,
        "mentor_profile": True,
        "certs": bool(prof["certificates"]),
        "public": False,
        "team": False,
        "user_panel": True,
        "ai_enabled": ai_on,
        "ai_ready": kbd,
    }


# --- mentor profile -----------------------------------------------------
def mentor_profile(user_id: int) -> dict:
    """پروفایل شغلی/منتور — از جداول واقعی ai_mentor در صورت موجود بودن."""
    st = get_mentor_state(user_id)
    c = _conn()
    paths, certs, up = [], [], {}
    try:
        for r in c.execute(
            "SELECT id, target_job, status, created_at FROM career_paths WHERE user_id=? "
            "ORDER BY id DESC LIMIT 5", (int(user_id),)).fetchall():
            paths.append(dict(r))
        for r in c.execute(
            "SELECT id, target_job, readiness, created_at FROM ai_certificates WHERE user_id=? "
            "ORDER BY id DESC LIMIT 5", (int(user_id),)).fetchall():
            certs.append(dict(r))
        row = c.execute("SELECT * FROM user_profiles WHERE user_id=?", (int(user_id),)).fetchone()
        if row:
            up = dict(row)
    except Exception:
        pass
    return {
        "career_goal": (up.get("goal") if up else "") or st.get("career_goal") or "",
        "experience_level": (up.get("level") if up else "") or st.get("experience_level") or "",
        "daily_hours": int(up.get("daily_hours") if up else (st.get("daily_hours") or 0)),
        "career_purpose": st.get("career_purpose") or "",
        "paths": paths,
        "certificates": certs,
        "age": int(up.get("age") or 0) if up else 0,
        "city": (up.get("city") if up else "") or "",
    }


# --- public helpers re-exported for web ---------------------------------
def get_user_rank(user_id: int) -> int:
    from services import user_service
    return user_service.user_rank(user_id)


def list_courses():
    from services import user_service
    return user_service.list_courses()


def list_missions():
    from services import user_service
    return user_service.list_missions()


def list_shop_items():
    from services import user_service
    return user_service.list_shop_items()


def user_progress_summary(user_id: int) -> dict:
    from services import user_service
    return user_service.user_progress_summary(user_id)
