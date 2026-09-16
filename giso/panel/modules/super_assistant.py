# -*- coding: utf-8 -*-
"""panel/modules/super_assistant.py — دستیار هوشمند مدیریتیِ سوپرادمین در سایت.

همان موتوری که در ربات بله برای سوپرادمین کار می‌کند (giso.ai_runtime)
از پنل سایت هم در دسترس می‌شود:
  • گزارش‌های زنده و قطعی از دیتابیس (بدون AI برای دستورهای گزارش)
  • اقدامات اجرایی فقط با تأیید دو مرحله‌ای:
      ۱) پیش‌نمایش اقدام  ۲) کد ۶ رقمی که به ربات بله ارسال می‌شود
  • snapshot قبل از تغییر + امکان بازگردانی (Undo)
  • همهٔ محدودیت‌های whitelist (SUPPORTED_SUPER_ACTIONS) عیناً اعمال می‌شود

این ماژول هیچ منطق موازی نمی‌سازد و فقط پلِ سایت ↔ ai_runtime است.
"""
import asyncio
import hashlib
import logging
import re
import secrets
import time

from flask import request, jsonify, session, flash, redirect, url_for

from giso.panel.permissions import current_role_and_perms

logger = logging.getLogger("giso_panel_assistant")

# ── تنظیمات کد تأیید اقدام (step-up دومرحله‌ای داخل پنل) ──
_ACTION_CODE_TTL_SECONDS = 300      # ۵ دقیقه
_ACTION_CODE_RESEND_GAP = 45        # فاصلهٔ ارسال مجدد
_ACTION_CODE_MAX_ATTEMPTS = 5
_ACTION_CODE_LEN = 6

SUGGESTED_PROMPTS = [
    "🐞 خطایابی: چه باگ‌ها و خطاهایی هست؟",
    "💡 پیشنهادهای بهبود سایت و ربات چیه؟",
    "📊 سلامت سرویس‌ها و وضعیت کلی سیستم",
    "📦 گزارش سریع امروز رو بده",
    "🛍 وضعیت سفارش‌ها و فروشگاه",
    "💇 درخواست‌های فروش مو در انتظار چنده؟",
    "🎫 تیکت‌های باز رو لیست کن",
    "💬 درخواست‌های مشاوره معطل رو لیست کن",
    "👥 چند کاربر جدید امروز ثبت کرده؟",
    "🤖 وضعیت هوش مصنوعی و پروایدرها",
]


# ───────────────────── دسترسی ─────────────────────

def _super_identity() -> tuple[str, str, str] | None:
    """(phone, role, bale_id) فقط برای سوپرادمینِ تأییدشدهٔ پنل."""
    try:
        role, _perms, bale_id = current_role_and_perms()
        if role != "super":
            return None
        from flask_login import current_user
        phone = str(getattr(current_user, "phone", "") or "").strip()
        if not phone:
            return None
        from giso.base import normalize_phone
        phone = normalize_phone(phone)
        # نشست step-up ورود پنل باید تازه باشد (همان گارد OTP ورود ادمین)
        if not _panel_stepup_valid(phone):
            return None
        return phone, role, str(bale_id or "")
    except Exception as e:
        logger.debug(f"assistant identity: {e}")
        return None


def _panel_stepup_valid(phone: str) -> bool:
    try:
        from giso.app import _admin_panel_is_verified
        return bool(_admin_panel_is_verified(phone))
    except Exception:
        # fallback نباید امنیت را تضعیف کند: فقط اگر import شکست خورد،
        # سرویس در حالت امن بسته می‌ماند.
        return False


def _actor_key(phone: str) -> str:
    return f"panel:{phone}"[:120]


# ───────────────────── تاریخچه چت (سبک، دیتابیس) ─────────────────────

_HISTORY_SCHEMA = (
    "CREATE TABLE IF NOT EXISTS giso_panel_ai_chats ("
    "id INTEGER PRIMARY KEY AUTOINCREMENT,"
    "actor_key TEXT DEFAULT '',"
    "phone TEXT DEFAULT '',"
    "role TEXT DEFAULT 'super',"
    "message_role TEXT DEFAULT 'user',"
    "content TEXT DEFAULT '',"
    "kind TEXT DEFAULT 'chat',"
    "ref_id INTEGER DEFAULT 0,"
    "provider TEXT DEFAULT '',"
    "created_at TEXT DEFAULT '')"
)


def _hist_conn():
    from giso.base import get_giso_db_conn
    return get_giso_db_conn()


def _hist_ensure(conn):
    try:
        conn.execute(_HISTORY_SCHEMA)
        conn.commit()
    except Exception:
        pass


def save_chat_message(phone: str, message_role: str, content: str,
                      kind: str = "chat", ref_id: int = 0, provider: str = ""):
    try:
        with _hist_conn() as conn:
            _hist_ensure(conn)
            conn.execute(
                "INSERT INTO giso_panel_ai_chats(actor_key,phone,role,message_role,content,kind,ref_id,provider,created_at) "
                "VALUES(?,?,?,?,?,?,?,?,datetime('now','localtime'))",
                (_actor_key(phone), phone, "super", message_role, str(content or "")[:8000],
                 kind, int(ref_id or 0), str(provider or "")[:80]),
            )
            conn.commit()
    except Exception as e:
        logger.warning(f"save_chat_message: {e}")


def load_chat_history(phone: str, limit: int = 40) -> list[dict]:
    try:
        with _hist_conn() as conn:
            _hist_ensure(conn)
            rows = conn.execute(
                "SELECT * FROM giso_panel_ai_chats WHERE actor_key=? ORDER BY id DESC LIMIT ?",
                (_actor_key(phone), int(limit)),
            ).fetchall()
            out = [dict(r) for r in reversed(rows)]
            return out
    except Exception as e:
        logger.warning(f"load_chat_history: {e}")
        return []


def clear_chat_history(phone: str):
    try:
        with _hist_conn() as conn:
            conn.execute("DELETE FROM giso_panel_ai_chats WHERE actor_key=?", (_actor_key(phone),))
            conn.commit()
    except Exception as e:
        logger.warning(f"clear_chat_history: {e}")


# ───────────────────── کد تأیید اقدام (OTP داخل پنل) ─────────────────────

def _code_hash(phone: str, code: str) -> str:
    return hashlib.sha256(f"assistant|{phone}|{code}".encode("utf-8")).hexdigest()


def _action_code_state(phone: str) -> dict:
    raw = session.get("assistant_act_code") or {}
    if not isinstance(raw, dict) or raw.get("phone") != phone:
        return {}
    return raw


def send_action_code(phone: str, bale_id: str, pending_id: int) -> tuple[bool, str]:
    """کد ۶ رقمیِ تأییدِ اجرای اقدام را فقط به ربات بلهٔ همین سوپرادمین می‌فرستد."""
    now_ts = int(time.time())
    st = _action_code_state(phone)
    try:
        last_sent = int(st.get("last_sent_at") or 0)
    except (TypeError, ValueError):
        last_sent = 0
    if st and st.get("pending_id") != int(pending_id):
        st = {}
    if not st or st.get("pending_id") != int(pending_id):
        last_sent = 0
    if last_sent and (now_ts - last_sent) < _ACTION_CODE_RESEND_GAP:
        wait = _ACTION_CODE_RESEND_GAP - (now_ts - last_sent)
        return False, f"کد قبلاً ارسال شده؛ {wait} ثانیه دیگر می‌توانی کد جدید بگیری."
    bid = str(bale_id or "").strip()
    if not bid.isdigit():
        return False, "برای این حساب شناسه رباتی ثبت نشده؛ تأیید اقدام از سایت ممکن نیست."
    code = f"{secrets.randbelow(10 ** _ACTION_CODE_LEN - 10 ** (_ACTION_CODE_LEN - 1)) + 10 ** (_ACTION_CODE_LEN - 1)}"
    try:
        import requests as _req
        from giso.base import _token_from_env, _token_from_db
        token = _token_from_env() or _token_from_db() or ""
        if not token:
            return False, "توکن ربات برای ارسال کد در دسترس نیست."
        text = (
            "🔐 کد تأیید اجرای اقدام مدیریتی در پنل سایت گیسو\n\n"
            f"کد: {code}\n"
            f"اعتبار: {_ACTION_CODE_TTL_SECONDS // 60} دقیقه\n"
            f"شماره درخواست اقدام: #{pending_id}\n\n"
            "اگر خودت این اقدام را در پنل تأیید نکردی، کد را به هیچ‌کس نده."
        )
        resp = _req.post(
            f"https://tapi.bale.ai/bot{token}/sendMessage",
            json={"chat_id": int(bid), "text": text},
            timeout=12,
        )
        if int(getattr(resp, "status_code", 500) or 500) >= 400:
            return False, "ارسال کد به ربات ناموفق بود. کمی بعد دوباره تلاش کن."
    except Exception as e:
        logger.warning(f"send_action_code: {e}")
        return False, "در ارسال کد به ربات خطا رخ داد."
    session["assistant_act_code"] = {
        "phone": phone,
        "pending_id": int(pending_id),
        "hash": _code_hash(phone, code),
        "expires_at": now_ts + _ACTION_CODE_TTL_SECONDS,
        "attempts": 0,
        "last_sent_at": now_ts,
    }
    session.modified = True
    return True, "کد تأیید به ربات بله ارسال شد."


def verify_action_code(phone: str, pending_id: int, code: str) -> tuple[bool, str]:
    now_ts = int(time.time())
    st = _action_code_state(phone)
    if not st or st.get("pending_id") != int(pending_id):
        return False, "ابتدا باید کد تأیید را به ربات بفرستم."
    code = str(code or "").strip()
    if not code:
        return False, "کد تأیید را وارد کن."
    try:
        expires_at = int(st.get("expires_at") or 0)
        attempts = int(st.get("attempts") or 0)
    except (TypeError, ValueError):
        expires_at, attempts = 0, 0
    if not expires_at or expires_at <= now_ts:
        session.pop("assistant_act_code", None)
        session.modified = True
        return False, "⏰ مهلت کد تمام شده. دوباره درخواست کد بده."
    if attempts >= _ACTION_CODE_MAX_ATTEMPTS:
        session.pop("assistant_act_code", None)
        session.modified = True
        return False, "تعداد تلاش مجاز تمام شد. دوباره کد بگیر."
    st["attempts"] = attempts + 1
    session["assistant_act_code"] = st
    session.modified = True
    if st.get("hash") != _code_hash(phone, code):
        return False, "کد واردشده صحیح نیست."
    # کد درست بود → پاک می‌شود (یک‌بار مصرف)
    session.pop("assistant_act_code", None)
    session.modified = True
    return True, "کد تأیید شد."


# ───────────────────── پاک‌سازی پاسخ برای نمایش تمیز در چت ─────────────────────

_RE_EMPHASIS = re.compile(r"\*\*(.+?)\*\*")
_RE_SINGLE_STAR = re.compile(r"(?<!\*)\*(?!\*)([^*]+?)(?<!\*)\*(?!\*)")
_RE_BULLET = re.compile(r"(?m)^\s*[-*•]\s+")
_RE_DECO = re.compile(r"(?m)^\s*[━—=\-~*]{3,}\s*$")
_RE_BLANK = re.compile(r"\n{3,}")


def _clean_answer(text: str) -> str:
    """حذف علامت‌های خام مارکداون (`**`, `*`, جداکننده‌های `━━`) و فشرده‌سازی خطوطِ خالی.

    هدف: نمایشِ روان و خوانا در حباب چت، بدون تکرارِ نشانگرهای زشتِ خروجیِ گزارش/AI.
    """
    s = (text or "").strip()
    if not s:
        return s
    s = _RE_EMPHASIS.sub(r"\1", s)
    s = _RE_SINGLE_STAR.sub(r"\1", s)
    s = _RE_DECO.sub("", s)
    s = _RE_BULLET.sub("• ", s)
    s = s.replace("**", "").replace("__", "")
    s = _RE_BLANK.sub("\n\n", s)
    return s.strip()


# ───────────────────── پردازش پیام چت ─────────────────────

def _run_async(coro):
    from giso.async_compat import run_async_safe
    try:
        return run_async_safe(coro)
    except Exception:
        return None


def handle_chat_message(phone: str, text: str) -> dict:
    """یک پیام سوپرادمین را پردازش می‌کند.

    خروجی: dict با ok/text/mode/pending_id/log_id/reversible/provider
    """
    text = (text or "").strip()
    if not text:
        return {"ok": False, "text": "پیام خالی است."}
    if len(text) > 1500:
        return {"ok": False, "text": "پیام خیلی طولانی است (حداکثر ۱۵۰۰ نویسه)."}
    from giso.ai_runtime import (
        process_superadmin_request, chat_with_managed_ai,
    )
    actor_key = _actor_key(phone)
    save_chat_message(phone, "user", text, kind="user_text")
    try:
        result = process_superadmin_request(phone, phone, text,
                                            actor_key=actor_key, channel="panel")
    except Exception as e:
        logger.exception("assistant process_superadmin_request failed")
        result = {"handled": False, "text": f"خطای داخلی در پردازش درخواست: {e}"}

    if result.get("handled"):
        mode = result.get("mode") or "message"
        answer = _clean_answer(result.get("text") or "—")
        provider = "deterministic"
        if mode == "pending":
            save_chat_message(phone, "assistant", answer,
                              kind="pending_preview", ref_id=int(result.get("pending_id") or 0))
            return {"ok": True, "text": answer, "mode": "pending",
                    "pending_id": int(result.get("pending_id") or 0), "provider": provider}
        save_chat_message(phone, "assistant", answer, kind=mode, provider=provider)
        out = {"ok": True, "text": answer, "mode": mode, "provider": provider, "model": ""}
        if result.get("insights"):
            out["insights"] = result.get("insights") or []
        if result.get("fresh"):
            out["fresh"] = True
        return out

    # گزارش/اقدام تشخیص داده نشد → گفتگوی آزاد مدیریت با AI
    # (system message و capabilities خودِ chat_with_managed_ai تزریق می‌شود)
    history = load_chat_history(phone, limit=20)
    messages = []
    for row in history[-10:]:
        if row.get("kind") in ("user_text", "chat", "report", "message", "ai_chat"):
            role = "user" if row.get("message_role") == "user" else "assistant"
            messages.append({"role": role, "content": (row.get("content") or "")[:1200]})
    messages.append({"role": "user", "content": text})
    ai = _run_async(chat_with_managed_ai(
        messages, actor_key=actor_key, role="super", channel="panel",
        section="consultant_chat", question_text=text, action="panel_assistant",
        max_tokens=750,
    )) or {}
    if ai.get("ok"):
        answer = _clean_answer(ai.get("text") or "")
        prov = str(ai.get("provider") or "")
        model = str(ai.get("model") or "")
        meta = " / ".join(x for x in (prov, model) if x)
        save_chat_message(phone, "assistant", answer, kind="ai_chat", provider=meta)
        return {"ok": True, "text": answer, "mode": "ai_chat",
                "provider": prov, "model": model}
    answer = _clean_answer(ai.get("text") or ai.get("error") or "مشاور هوشمند موقتاً در دسترس نیست.")
    save_chat_message(phone, "assistant", answer, kind="error")
    return {"ok": False, "text": answer, "mode": "error"}


def execute_with_code(phone: str, pending_id: int, code: str) -> dict:
    """تأیید دو مرحله‌ای: کد رباتی درست باشد بعد اقدام اجرا می‌شود."""
    from giso.ai_runtime import execute_pending_action
    ok, msg = verify_action_code(phone, pending_id, code)
    if not ok:
        return {"ok": False, "text": msg}
    try:
        result = execute_pending_action(int(pending_id), phone, actor_key=_actor_key(phone))
    except Exception as e:
        logger.exception("assistant execute failed")
        result = {"ok": False, "text": f"خطای داخلی اجرا: {e}"}
    answer = _clean_answer(result.get("text") or "—")
    kind = "action_done" if result.get("ok") else "action_error"
    save_chat_message(phone, "assistant", answer,
                      kind=kind, ref_id=int(pending_id))
    return {
        "ok": bool(result.get("ok")),
        "text": answer,
        "mode": "action_done",
        "log_id": int(result.get("log_id") or 0),
        "reversible": bool(result.get("reversible")),
    }


def cancel_pending(phone: str, pending_id: int) -> dict:
    from giso.ai_runtime import cancel_pending_action
    try:
        result = cancel_pending_action(int(pending_id), phone, actor_key=_actor_key(phone))
    except Exception as e:
        result = {"ok": False, "text": f"خطا: {e}"}
    answer = _clean_answer(result.get("text") or "—")
    save_chat_message(phone, "assistant", answer,
                      kind="action_cancelled", ref_id=int(pending_id))
    return {"ok": bool(result.get("ok")), "text": answer}


def undo_action(phone: str, log_id: int) -> dict:
    from giso.ai_runtime import rollback_action_log
    try:
        result = rollback_action_log(int(log_id), phone, actor_key=_actor_key(phone))
    except Exception as e:
        result = {"ok": False, "text": f"خطا: {e}"}
    answer = _clean_answer(result.get("text") or "—")
    save_chat_message(phone, "assistant", answer,
                      kind="action_rolled_back", ref_id=int(log_id))
    return {"ok": bool(result.get("ok")), "text": answer}


# ───────────────────── handlerهای route ─────────────────────

def _csrf_ok() -> bool:
    try:
        from giso.security import validate_csrf
        return bool(validate_csrf())
    except Exception:
        return False


def _forbidden():
    return jsonify({"ok": False, "error": "درخواست امنیتی نامعتبر است؛ صفحه را تازه‌سازی کنید."}), 400


def handle_chat_post():
    if not _csrf_ok():
        return _forbidden()
    ident = _super_identity()
    if not ident:
        return jsonify({"ok": False, "error": "دسترسی مجاز نیست یا نشست پنل منقضی شده؛ یک‌بار با کد ورود پنل را باز کن."}), 403
    phone, _role, bale_id = ident
    data = request.get_json(silent=True) or {}
    message = (data.get("message") or "").strip()
    try:
        out = handle_chat_message(phone, message)
    except Exception as e:
        logger.exception("assistant chat post failed")
        out = {"ok": False, "text": f"خطای داخلی: {e}"}
    return jsonify(out)


def handle_code_send_post():
    if not _csrf_ok():
        return _forbidden()
    ident = _super_identity()
    if not ident:
        return jsonify({"ok": False, "error": "دسترسی مجاز نیست."}), 403
    phone, _role, bale_id = ident
    data = request.get_json(silent=True) or {}
    try:
        pending_id = int(data.get("pending_id") or 0)
    except (TypeError, ValueError):
        return jsonify({"ok": False, "error": "شناسه اقدام نامعتبر است."}), 400
    ok, msg = send_action_code(phone, bale_id, pending_id)
    return jsonify({"ok": ok, "text": msg})


def handle_action_confirm_post():
    if not _csrf_ok():
        return _forbidden()
    ident = _super_identity()
    if not ident:
        return jsonify({"ok": False, "error": "دسترسی مجاز نیست."}), 403
    phone, _role, _bid = ident
    data = request.get_json(silent=True) or {}
    try:
        pending_id = int(data.get("pending_id") or 0)
    except (TypeError, ValueError):
        return jsonify({"ok": False, "error": "شناسه اقدام نامعتبر است."}), 400
    code = (data.get("code") or "").strip()
    out = execute_with_code(phone, pending_id, code)
    return jsonify(out)


def handle_action_cancel_post():
    if not _csrf_ok():
        return _forbidden()
    ident = _super_identity()
    if not ident:
        return jsonify({"ok": False, "error": "دسترسی مجاز نیست."}), 403
    phone, _role, _bid = ident
    data = request.get_json(silent=True) or {}
    try:
        pending_id = int(data.get("pending_id") or 0)
    except (TypeError, ValueError):
        return jsonify({"ok": False, "error": "شناسه اقدام نامعتبر است."}), 400
    return jsonify(cancel_pending(phone, pending_id))


def handle_undo_post():
    if not _csrf_ok():
        return _forbidden()
    ident = _super_identity()
    if not ident:
        return jsonify({"ok": False, "error": "دسترسی مجاز نیست."}), 403
    phone, _role, _bid = ident
    data = request.get_json(silent=True) or {}
    try:
        log_id = int(data.get("log_id") or 0)
    except (TypeError, ValueError):
        return jsonify({"ok": False, "error": "شناسه لاگ نامعتبر است."}), 400
    return jsonify(undo_action(phone, log_id))


def handle_clear_post():
    if not _csrf_ok():
        return _forbidden()
    ident = _super_identity()
    if not ident:
        return jsonify({"ok": False, "error": "دسترسی مجاز نیست."}), 403
    phone, _role, _bid = ident
    clear_chat_history(phone)
    return jsonify({"ok": True, "text": "تاریخچه گفتگو پاک شد."})


def handle_insight_status_post():
    """تغییر وضعیت یک یافتهٔ بازرس (دیدم/اعمال شد/رد) — فقط سوپرادمین."""
    if not _csrf_ok():
        return _forbidden()
    if not _super_identity():
        return jsonify({"ok": False, "error": "دسترسی مجاز نیست."}), 403
    data = request.get_json(silent=True) or {}
    try:
        insight_id = int(data.get("id") or 0)
    except Exception:
        insight_id = 0
    status = str(data.get("status") or "").strip()
    if status not in ("seen", "applied", "dismissed", "new"):
        return jsonify({"ok": False, "error": "وضعیت نامعتبر."}), 400
    try:
        from giso.monitoring_insights import set_insight_status
        ok = set_insight_status(insight_id, status)
    except Exception as e:
        logger.exception("insight status failed")
        ok = False
    return jsonify({"ok": bool(ok)})


# ───────────────────── context صفحه ─────────────────────

def _pending_ids_for(phone: str) -> set:
    """شناسه‌های اقدامِ معلق (هنوز تأیید/لغو/انقضا نشده) همین کاربر — برای دکمه‌های تاریخچه."""
    ids = set()
    try:
        from giso.ai_runtime import _conn
        with _conn() as conn:
            rows = conn.execute(
                "SELECT id FROM giso_ai_pending_actions WHERE actor_key=? AND status='pending'",
                (_actor_key(phone),),
            ).fetchall()
            ids = {int(r[0]) for r in rows}
    except Exception as e:
        logger.debug(f"pending ids: {e}")
    return ids


def context():
    ident = _super_identity()
    if not ident:
        return {"assistant": {"authorized": False, "history": [], "suggestions": SUGGESTED_PROMPTS,
                              "pending_ids": set()}}
    phone, role, bale_id = ident
    display_name = ""
    try:
        with _hist_conn() as conn:
            row = conn.execute("SELECT name FROM giso_web_auth WHERE phone=? LIMIT 1", (phone,)).fetchone()
            if row and str(row[0] or "").strip():
                display_name = str(row[0]).strip()
    except Exception:
        display_name = ""
    if not display_name:
        display_name = "دوست عزیز"
    return {
        "assistant": {
            "authorized": True,
            "phone": phone,
            "history": load_chat_history(phone, limit=50),
            "suggestions": SUGGESTED_PROMPTS,
            "display_name": display_name,
            "bale_connected": bool(str(bale_id or "").isdigit()),
            "pending_ids": _pending_ids_for(phone),
        }
    }

# ───────────────────────────── ستون وضعیت سیستم ─────────────────────────────
_HEALTH_CACHE = {"at": 0.0, "data": None}


def _http_ping(url, timeout=3):
    import urllib.request
    try:
        with urllib.request.urlopen(url, timeout=timeout) as r:
            return 200 <= int(r.status) < 400
    except Exception:
        return False


def get_system_health():
    """وضعیت لحظه‌ای ۵ سرویس با کد رنگ (green/yellow/red) — کش ۲۰ ثانیه، timeout ۳ ثانیه."""
    now = time.time()
    if _HEALTH_CACHE["data"] is not None and now - _HEALTH_CACHE["at"] < 20:
        return _HEALTH_CACHE["data"]
    items = [{"key": "web", "name": "وب‌سایت", "icon": "🌐",
              "state": "green", "note": "در حال سرویس‌دهی"}]
    try:
        from giso.base import get_giso_db_conn
        with get_giso_db_conn() as c:
            c.execute("SELECT 1")
        items.append({"key": "db", "name": "دیتابیس", "icon": "🗄", "state": "green", "note": "اتصال برقرار"})
    except Exception as e:
        items.append({"key": "db", "name": "دیتابیس", "icon": "🗄", "state": "red", "note": type(e).__name__[:40]})
    ai_name, ai_model, ai_note, ai_state = "AI فعال", "—", "نامشخص", "yellow"
    try:
        from giso.ai_runtime import get_active_provider
        from giso.ai_brain import get_ai_provider
        ai_name = (get_active_provider() or "").strip() or "AI فعال"
        prow = get_ai_provider(ai_name) if ai_name else None
        if prow:
            ai_model = str(prow["selected_model"] or "—")
            st = str(prow["last_status"] or "").strip()
            enabled = bool(prow["enabled"])
            low = st.lower()
            if not enabled:
                ai_state, ai_note = "red", "غیرفعال"
            elif low in ("ok", "ready", "online", "سالم", "موفق", "success", "up"):
                ai_state, ai_note = "green", st or "سالم"
            elif st:
                ai_state, ai_note = "yellow", st[:48]
            else:
                ai_state, ai_note = "yellow", "وضعیت ثبت‌نشده"
        else:
            ai_state, ai_note = "red", "پروایدر فعال پیدا نشد"
    except Exception as e:
        ai_state, ai_note = "yellow", type(e).__name__[:40]
    items.append({
        "key": "ai",
        "name": f"هوش مصنوعی ({ai_name})",
        "icon": "🧠",
        "state": ai_state,
        "note": f"{ai_model} — {ai_note}",
    })
    try:
        from giso.base import _token_from_env, _token_from_db
        token = _token_from_env() or _token_from_db() or ""
    except Exception:
        token = ""
    if not token:
        items.append({"key": "bale", "name": "ربات بله", "icon": "🐋", "state": "red", "note": "توکن تنظیم نشده"})
    elif _http_ping("https://tapi.bale.ai/bot%s/getMe" % token):
        items.append({"key": "bale", "name": "ربات بله", "icon": "🐋", "state": "green", "note": "آنلاین"})
    else:
        items.append({"key": "bale", "name": "ربات بله", "icon": "🐋", "state": "yellow", "note": "عدم پاسخ (۳ ثانیه)"})
    try:
        from giso.broadcasts_center import worker as _bcw
        alive, q = _bcw.alive(), _bcw.queue_size()
        items.append({"key": "queue", "name": "صف پیام‌ها", "icon": "📨",
                      "state": "green" if alive and q < 50 else ("yellow" if alive else "red"),
                      "note": "worker فعال — صف %d" % q if alive else "worker غیرفعال"})
    except Exception:
        items.append({"key": "queue", "name": "صف پیام‌ها", "icon": "📨", "state": "red", "note": "خطا"})
    _HEALTH_CACHE["at"] = now
    _HEALTH_CACHE["data"] = items
    return items

