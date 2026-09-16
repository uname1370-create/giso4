# -*- coding: utf-8 -*-
"""
giso/widget_service.py — سرویس‌های ویجت هوشمند سایت و اعلان‌های مشاور (Phase 2, Unit U3)
استخراج‌شده از giso/app.py بدون تغییر رفتار؛ همه نام‌ها در giso.app re-export می‌شوند.
"""
import json
import logging
import secrets
from datetime import datetime
from flask import session
from flask_login import current_user

from giso.base import (get_giso_db_conn, normalize_phone,
                       _token_from_env, _token_from_db)
from giso.stepup import _admin_panel_is_verified, _admin_panel_target

logger = logging.getLogger("giso_widget")

def _resolve_site_ai_role() -> str:
    try:
        if not current_user or not current_user.is_authenticated:
            return "guest"
        phone_norm = normalize_phone(getattr(current_user, "phone", "") or "")
        target = _admin_panel_target(phone_norm)
        if target and _admin_panel_is_verified(phone_norm):
            return "super" if target.get("role") == "super" else "admin"
    except Exception:
        pass
    return "user"


def _widget_actor_key(role: str) -> str:
    role = (role or "guest").strip().lower()
    if role == "guest":
        guest_id = session.get("ai_widget_guest_id")
        if not guest_id:
            guest_id = secrets.token_hex(8)
            session["ai_widget_guest_id"] = guest_id
        return f"widget:guest:{guest_id}"
    phone = normalize_phone(getattr(current_user, "phone", "") or "")
    if phone:
        return f"widget:{role}:{phone}"
    return f"widget:{role}:{getattr(current_user, 'id', 'anon')}"


def _widget_history_get() -> list:
    """تاریخچه ویجت از دیتابیس giso_widget_chats (به‌جای کوکی session) — سبک و پایدار."""
    try:
        role = _resolve_site_ai_role()
        actor = _widget_actor_key(role)
        with get_giso_db_conn() as conn:
            rows = conn.execute(
                "SELECT message_role, content FROM giso_widget_chats "
                "WHERE actor_key=? ORDER BY id DESC LIMIT 12",
                (actor,),
            ).fetchall()
        return [{"role": r["message_role"], "content": r["content"]} for r in reversed(rows)]
    except Exception:
        return []


def _widget_history_set(history: list[dict]):
    """تاریخچه به‌صورت پایدار در giso_widget_chats ذخیره می‌شود؛ کوکی session سبک می‌ماند."""
    return None


def _widget_log_chat(role: str, phone: str, user_name: str, page_path: str, user_msg: str, assistant_msg: str):
    """ثبت دائمی هر گفتگوی ویجت برای تحلیل شخصیت کاربر و آنالیز مدیریتی."""
    try:
        actor = _widget_actor_key(role)
        with get_giso_db_conn() as conn:
            for mrole, content in (("user", user_msg), ("assistant", assistant_msg)):
                conn.execute(
                    "INSERT INTO giso_widget_chats (actor_key, role, phone, user_name, page_path, message_role, content, created_at)"
                    " VALUES (?,?,?,?,?,?,?,datetime('now','localtime'))",
                    (actor, role, phone or "", user_name or "", (page_path or "/")[:300], mrole, (content or "")[:4000]),
                )
            conn.commit()
    except Exception:
        pass


def _widget_fa_hair_status(status: str) -> str:
    return {
        "pending": "در انتظار بررسی", "reviewing": "در حال بررسی", "priced": "قیمت‌گذاری شده",
        "approved": "تأیید و آماده هماهنگی", "rejected": "رد شده", "completed": "تکمیل شده",
    }.get((status or "").strip(), status or "نامشخص")


def _widget_fa_order_status(status: str) -> str:
    return {
        "pending": "در حال بررسی", "completed": "تکمیل شده", "cancelled": "لغو شده",
    }.get((status or "").strip(), status or "نامشخص")


def _widget_q1(conn, sql: str, params=()) -> int:
    """اجرای امن کوئری شمارشی؛ هر خطا = صفر."""
    try:
        row = conn.execute(sql, params).fetchone()
        return int((row[0] if row else 0) or 0)
    except Exception:
        return 0


def _widget_user_brief(role: str, phone: str, user_name: str) -> dict:
    """
    خلاصه زنده کاربر از دیتابیس: شمارش‌ها، اطلاعیه‌های شخصی (وضعیت سفارش/درخواست)،
    خط شخصی‌سازی پرامپت، و برای ادمین تأییدشده آخرین گزارش مدیریتی.
    """
    import time as _t
    brief = {"counts": {}, "notices": [], "notice_text": "", "profile_line": "", "staff_report": ""}
    today = _t.strftime('%Y-%m-%d')
    try:
        with get_giso_db_conn() as conn:
            if role in ("admin", "super"):
                s = {
                    "today_users": _widget_q1(conn, 'SELECT COUNT(*) FROM giso_web_auth WHERE created_at >= ?', (today,)),
                    "total_users": _widget_q1(conn, 'SELECT COUNT(*) FROM giso_web_auth'),
                    "today_orders": _widget_q1(conn, 'SELECT COUNT(*) FROM product_orders WHERE created_at >= ?', (today,)),
                    "pending_orders": _widget_q1(conn, "SELECT COUNT(*) FROM product_orders WHERE status='pending'"),
                    "today_hair": _widget_q1(conn, 'SELECT COUNT(*) FROM hair_orders WHERE created_at >= ?', (today,)),
                    "pending_hair": _widget_q1(conn, "SELECT COUNT(*) FROM hair_orders WHERE status IN ('pending','reviewing')"),
                    "open_tickets": _widget_q1(conn, "SELECT COUNT(*) FROM giso_support_tickets WHERE status IN ('new','reviewing')"),
                    "open_consult": _widget_q1(conn, "SELECT COUNT(*) FROM consultant_requests WHERE status IN ('new','reviewing','pending','active')"),
                }
                crown = "👑" if role == "super" else "🛡"
                brief["staff_report"] = (
                    f"📊 گزارش امروز ({today}): {s['today_users']} کاربر جدید | "
                    f"{s['today_orders']} سفارش فروشگاه ({s['pending_orders']} در انتظار) | "
                    f"{s['today_hair']} درخواست فروش مو ({s['pending_hair']} در انتظار بررسی) | "
                    f"{s['open_tickets']} تیکت باز | {s['open_consult']} مشاوره فعال"
                )
                brief["notice_text"] = f"{crown} خوش اومدی {user_name or ''}!\n{brief['staff_report']}"
                brief["profile_line"] = "دسترسی مدیریتی فعال است؛ آمار زنده سایت برای این کاربر قابل ارائه است."
                brief["counts"] = s
                return brief
            if not phone:
                return brief
            row = conn.execute("SELECT id, name, first_name, created_at FROM giso_web_auth WHERE phone=? LIMIT 1", (phone,)).fetchone()
            uid = int(row[0]) if row else 0
            db_name = (str(row[2] or "") if row else "") or (str(row[1] or "") if row else "") or user_name or ""
            since = str(row[3] or "")[:10] if row else ""
            params = (uid, phone)
            cnt = {
                "analyses": _widget_q1(conn, "SELECT COUNT(*) FROM analyses WHERE user_id=? OR phone=?", params),
                "orders": _widget_q1(conn, "SELECT COUNT(*) FROM product_orders WHERE user_id=? OR phone=?", params),
                "hair": _widget_q1(conn, "SELECT COUNT(*) FROM hair_orders WHERE user_id=? OR phone=?", params),
                "reviews": _widget_q1(conn, "SELECT COUNT(*) FROM reviews WHERE phone=?", (phone,)),
            }
            brief["counts"] = cnt
            notices = []
            try:
                for r in conn.execute(
                    "SELECT id, status FROM hair_orders WHERE (user_id=? OR phone=?) AND status IN ('pending','reviewing','priced','approved') ORDER BY id DESC LIMIT 2",
                    params,
                ).fetchall():
                    notices.append(f"درخواست فروش مو #{r[0]}: «{_widget_fa_hair_status(r[1])}»")
            except Exception:
                pass
            try:
                for r in conn.execute(
                    "SELECT id, status FROM product_orders WHERE (user_id=? OR phone=?) AND status='pending' ORDER BY id DESC LIMIT 2",
                    params,
                ).fetchall():
                    notices.append(f"سفارش فروشگاه #{r[0]}: «{_widget_fa_order_status(r[1])}»")
            except Exception:
                pass
            try:
                ready = conn.execute(
                    "SELECT p.name FROM stock_notifies sn JOIN products p ON p.id=sn.product_id WHERE sn.phone=? AND p.in_stock=1 ORDER BY sn.id DESC LIMIT 1",
                    (phone,),
                ).fetchone()
                if ready and ready[0]:
                    notices.append(f"«{ready[0]}» که منتظرش بودی موجود شد 🌸")
            except Exception:
                pass
            brief["notices"] = notices[:3]
            if notices:
                greet = f"سلام {db_name or 'دوست عزیز'} 🌸" if db_name else "سلام دوست عزیز 🌸"
                brief["notice_text"] = greet + "\n" + "\n".join(notices[:3])
            brief["profile_line"] = (
                f"نام: {db_name or 'نامشخص'} | عضویت: {since or 'نامشخص'} | آنالیز: {cnt['analyses']} | "
                f"سفارش فروشگاه: {cnt['orders']} | فروش مو: {cnt['hair']} | نظر: {cnt['reviews']}"
            )
    except Exception as e:
        logger.warning(f"_widget_user_brief: {e}")
    return brief


_WIDGET_STOPWORDS = {
    "سلام", "وقت", "بخیر", "میخوام", "می‌خوام", "میخواهم", "لطفا", "لطفاً", "ممنون", "مرسی",
    "برای", "خیلی", "یکی", "یک", "چیه", "چی", "چه", "آیا", "ایا", "کدام", "کدوم", "چطور",
    "بگو", "بگه", "بده", "داره", "دارم", "هست", "هستش", "نیست", "باشه", "شود", "بشه",
    "قیمت", "قیمتش", "چند", "تومان", "خرید", "خر", "هم", "اون", "این", "ممنونم", "راستی",
}


# نشانه‌های قصد واقعی محصول/خرید — پیشنهاد محصول فقط وقتی کاربر خودش وارد این فضا شده
_WIDGET_PRODUCT_INTENT_KWS = (
    "محصول", "محصولی", "پیشنهاد", "خرید", "بخرم", "بخر", "شامپو", "ماسک", "سرم",
    "کرم", "روغن", "نرم‌کننده", "نرم کننده", "ضدریزش", "ضد ریزش", "آبرسان",
    "تقویت", "مراقبت", "چی بزنم", "چی خوبه", "معرفی کن", "فروشگاه",
)


def _widget_has_product_intent(text: str) -> bool:
    """درک زمینه: آیا کاربر واقعاً دنبال محصول/خرید است؟ (نه هر جمله‌ای)"""
    t = str(text or "")
    return any(k in t for k in _WIDGET_PRODUCT_INTENT_KWS)


def _widget_product_suggestions(text: str, limit: int = 2) -> list:
    """پیشنهاد محصول مرتبط از دل صحبت کاربر (بر اساس نام/دسته/توضیح محصولات فروشگاه).

    فیکس UX: فقط وقتی قصد محصول/خرید در پیام هست پیشنهاد بده؛ قبلاً هر کلمه‌ی
    ۳+ حرفی با نام محصولات match می‌شد و وسط هر گفتگویی چیپ محصول می‌آمد.
    """
    if not _widget_has_product_intent(text):
        return []
    try:
        import re as _re
        tokens = [
            t for t in _re.split(r"[^\w‌\u200c]+", str(text or ""))
            if len(t) >= 3 and t not in _WIDGET_STOPWORDS
        ]
    except Exception:
        tokens = []
    if not tokens:
        return []
    try:
        with get_giso_db_conn() as conn:
            rows = conn.execute(
                "SELECT name, category, description, in_stock FROM products"
                " WHERE (publish_status='published' OR publish_status='' OR publish_status IS NULL)"
            ).fetchall()
    except Exception:
        return []
    scored = []
    for r in rows:
        try:
            hay = f"{r[0] or ''} {r[1] or ''} {str(r[2] or '')[:300]}"
            score = sum(1 for t in tokens if t in hay)
            if score > 0 and r[3]:
                scored.append((score, str(r[0] or "")))
        except Exception:
            pass
    scored.sort(key=lambda x: -x[0])
    out = []
    for score, name in scored:
        chip = f"🛍 معرفی «{name}»"
        if chip not in out:
            out.append(chip)
        if len(out) >= limit:
            break
    return out


def _widget_staff_suggestion_chips(msg_text: str) -> list:
    t = str(msg_text or "")
    chips = []
    if any(k in t for k in ("فروش مو", "فروش موی", "درخواست مو")):
        chips.append("💇 گزارش فروش مو")
    if any(k in t for k in ("فروشگاه", "سفارش", "محصول")):
        chips.append("🛍 گزارش فروشگاه")
    if "تیکت" in t:
        chips.append("🎫 گزارش تیکت‌ها")
    if "مشاوره" in t:
        chips.append("💬 گزارش مشاوره‌ها")
    if any(k in t for k in ("ویجت", "چت سایت", "گفتگو")):
        chips.append("🤖 آمار ویجت سایت")
    if any(k in t for k in ("کاربر", "عضو", "ثبت")):
        chips.append("👥 گزارش کاربران")
    if any(k in t for k in ("بازاریابی", "مارکتینگ", "روزانه")):
        chips.append("📣 گزارش بازاریابی امروز")
    # فیکس UX: اگر پیام ادمین اصلاً کاری/گزارشی نیست (گپ شخصی)، هیچ چیپی نده؛
    # قبلاً همیشه ۳ چیپ ثابت گزارش وسط هر گفتگویی می‌آمد.
    if not chips:
        _work_hint = any(k in t for k in ("گزارش", "آمار", "وضعیت", "امروز", "پنل", "چند"))
        return ["📊 گزارش کلی امروز"] if _work_hint else []
    if "📊 گزارش کلی امروز" not in chips:
        chips.append("📊 گزارش کلی امروز")
    return chips[:3]


def _widget_dynamic_suggestions(role: str, context: dict, history: list, user_message: str) -> list:
    """
    چیپ‌های پیشنهادی پویا بعد از هر پاسخ: بر اساس آخرین پیام، تاریخچه، نقش و وضعیت کاربر.
    برای کاربر عادی: اول محصول مرتبط (اگر ذکر شده)، بعد قدم‌های بعدی وضعیت او.
    برای ادمین: میان‌برهای گزارش.
    """
    sugs = []
    if role in ("admin", "super"):
        sugs.extend(_widget_staff_suggestion_chips(user_message))
    else:
        try:
            recent = [h.get("content", "") for h in (history or [])[-4:] if isinstance(h, dict) and h.get("role") == "user"]
        except Exception:
            recent = []
        sugs.extend(_widget_product_suggestions(" ".join([user_message or ""] + recent), limit=2))
    for b in (context.get("suggestions") or []):
        b = str(b).strip()
        if b and b not in sugs:
            sugs.append(b)
    return sugs[:3]


def _widget_staff_report(text: str) -> str | None:
    """
    دستورهای گزارش‌گیری زنده برای ادمین/سوپرادمین داخل چت ویجت.
    فقط وقتی پیام «دستوری» باشد (گزارش/آمار/تعداد/...) پاسخ قطعی دیتابیسی می‌دهد؛
    در غیر این‌صورت None برمی‌گردد تا هوش مصنوعی جواب دهد.
    """
    import time as _t
    t = str(text or "").strip()
    if not t:
        return None
    cmdish = any(k in t for k in ("گزارش", "آمار", "خلاصه", "جمع‌بندی", "جمع بندی", "چند ", "تعداد", "لیست"))
    if not cmdish:
        return None
    today = _t.strftime('%Y-%m-%d')
    # فاز P2: دستور «گزارش بازاریابی» برای ادمین — خلاصه بازاریابی روزانه (منبع مشترک giso.marketing)
    if any(k in t for k in ("بازاریابی", "مارکتینگ", "گزارش روزانه", "خلاصه روزانه")):
        try:
            from giso.marketing import daily_digest_text
            return daily_digest_text(today, html=False)
        except Exception:
            return None
    try:
        week = _t.strftime('%Y-%m-%d', _t.localtime(_t.time() - 6 * 86400))
    except Exception:
        week = today
    if any(k in t for k in ("فروش مو", "فروش موی", "درخواست‌های مو", "درخواست مو")):
        scope = "hair"
    elif any(k in t for k in ("فروشگاه", "سفارش", "محصول")):
        scope = "shop"
    elif "تیکت" in t:
        scope = "tickets"
    elif "مشاوره" in t:
        scope = "consult"
    elif any(k in t for k in ("ویجت", "چت سایت", "گفتگو", "مشاور هوشمند")):
        scope = "widget"
    elif any(k in t for k in ("رضایت", "نظرات", "نظر ")):
        scope = "reviews"
    elif any(k in t for k in ("کاربر", "عضو", "ثبت‌نام", "ثبت نام")):
        scope = "users"
    else:
        scope = "overall"
    SQL_PENDING_ORDERS = "SELECT COUNT(*) FROM product_orders WHERE status='pending'"
    SQL_COMPLETED_ORDERS = "SELECT COUNT(*) FROM product_orders WHERE status='completed'"
    SQL_CANCELLED_ORDERS = "SELECT COUNT(*) FROM product_orders WHERE status='cancelled'"
    SQL_PENDING_PUB = "SELECT COUNT(*) FROM products WHERE publish_status='pending'"
    SQL_HAIR_WAIT = "SELECT COUNT(*) FROM hair_orders WHERE status IN ('pending','reviewing')"
    SQL_HAIR_PRICED = "SELECT COUNT(*) FROM hair_orders WHERE status='priced'"
    SQL_HAIR_DONE = "SELECT COUNT(*) FROM hair_orders WHERE status='completed'"
    SQL_HAIR_REJECTED = "SELECT COUNT(*) FROM hair_orders WHERE status='rejected'"
    SQL_TICKETS_OPEN = "SELECT COUNT(*) FROM giso_support_tickets WHERE status IN ('new','reviewing')"
    SQL_CONSULT_OPEN = "SELECT COUNT(*) FROM consultant_requests WHERE status IN ('new','reviewing','pending','active')"
    try:
        with get_giso_db_conn() as conn:
            if scope == "shop":
                rev = 0
                try:
                    row = conn.execute(
                        "SELECT SUM(p.price * o.quantity) FROM product_orders o JOIN products p ON p.id=o.product_id WHERE o.status='completed'"
                    ).fetchone()
                    rev = int((row[0] if row else 0) or 0)
                except Exception:
                    rev = 0
                return "\n".join([
                    f"🛍 گزارش فروشگاه | امروز {today}",
                    f"سفارش امروز: {_widget_q1(conn, 'SELECT COUNT(*) FROM product_orders WHERE created_at >= ?', (today,))} | ۷ روز اخیر: {_widget_q1(conn, 'SELECT COUNT(*) FROM product_orders WHERE created_at >= ?', (week,))} | کل: {_widget_q1(conn, 'SELECT COUNT(*) FROM product_orders')}",
                    f"در انتظار: {_widget_q1(conn, SQL_PENDING_ORDERS)} | تکمیل: {_widget_q1(conn, SQL_COMPLETED_ORDERS)} | لغو: {_widget_q1(conn, SQL_CANCELLED_ORDERS)}",
                    f"مبلغ سفارش‌های تکمیل‌شده: {rev:,} تومان",
                    f"محصول ناموجود: {_widget_q1(conn, 'SELECT COUNT(*) FROM products WHERE in_stock=0')} | در انتظار انتشار: {_widget_q1(conn, SQL_PENDING_PUB)}",
                ])
            if scope == "hair":
                last_pending = ""
                try:
                    rows = conn.execute(
                        "SELECT id, customer_name, length_cm, created_at FROM hair_orders WHERE status IN ('pending','reviewing') ORDER BY id DESC LIMIT 3"
                    ).fetchall()
                    if rows:
                        last_pending = "آخرین در انتظار: " + " ، ".join(
                            f"#{r[0]} {r[1] or ''} ({r[2]}cm)" for r in rows
                        )
                except Exception:
                    last_pending = ""
                lines = [
                    f"💇 گزارش فروش مو | امروز {today}",
                    f"کل درخواست‌ها: {_widget_q1(conn, 'SELECT COUNT(*) FROM hair_orders')} | امروز: {_widget_q1(conn, 'SELECT COUNT(*) FROM hair_orders WHERE created_at >= ?', (today,))}",
                    f"در انتظار بررسی: {_widget_q1(conn, SQL_HAIR_WAIT)} | قیمت‌گذاری‌شده: {_widget_q1(conn, SQL_HAIR_PRICED)} | تکمیل: {_widget_q1(conn, SQL_HAIR_DONE)} | رد: {_widget_q1(conn, SQL_HAIR_REJECTED)}",
                ]
                if last_pending:
                    lines.append(last_pending)
                return "\n".join(lines)
            if scope == "users":
                last_user = ""
                try:
                    row = conn.execute("SELECT phone, created_at FROM giso_web_auth ORDER BY id DESC LIMIT 1").fetchone()
                    if row:
                        last_user = f"آخرین عضو: {row[0]} ({str(row[1])[:16]})"
                except Exception:
                    pass
                lines = [
                    f"👥 گزارش کاربران سایت | امروز {today}",
                    f"کل اعضا: {_widget_q1(conn, 'SELECT COUNT(*) FROM giso_web_auth')} | امروز: {_widget_q1(conn, 'SELECT COUNT(*) FROM giso_web_auth WHERE created_at >= ?', (today,))} | ۷ روز اخیر: {_widget_q1(conn, 'SELECT COUNT(*) FROM giso_web_auth WHERE created_at >= ?', (week,))}",
                ]
                if last_user:
                    lines.append(last_user)
                return "\n".join(lines)
            if scope == "tickets":
                return "\n".join([
                    f"🎫 گزارش تیکت‌ها | امروز {today}",
                    f"باز (جدید/در حال بررسی): {_widget_q1(conn, SQL_TICKETS_OPEN)} | کل: {_widget_q1(conn, 'SELECT COUNT(*) FROM giso_support_tickets')}",
                    f"امروز: {_widget_q1(conn, 'SELECT COUNT(*) FROM giso_support_tickets WHERE created_at >= ?', (today,))}",
                ])
            if scope == "consult":
                return "\n".join([
                    f"💬 گزارش مشاوره‌ها | امروز {today}",
                    f"فعال/در انتظار: {_widget_q1(conn, SQL_CONSULT_OPEN)} | کل: {_widget_q1(conn, 'SELECT COUNT(*) FROM consultant_requests')}",
                ])
            if scope == "widget":
                chat_users = _widget_q1(
                    conn,
                    "SELECT COUNT(*) FROM giso_widget_chats WHERE message_role='user' AND created_at >= ?",
                    (week,),
                )
                chat_ai = _widget_q1(
                    conn,
                    "SELECT COUNT(*) FROM giso_widget_chats WHERE message_role='assistant' AND created_at >= ?",
                    (week,),
                )
                return "\n".join([
                    f"🤖 گزارش ویجت مشاور سایت | ۷ روز اخیر",
                    f"پیام کاربران: {chat_users} | پاسخ مشاور: {chat_ai}",
                    f"بازخورد 👍: {_widget_q1(conn, 'SELECT COUNT(*) FROM giso_widget_feedback WHERE rating=1')} | 👎: {_widget_q1(conn, 'SELECT COUNT(*) FROM giso_widget_feedback WHERE rating=-1')}",
                ])
            if scope == "reviews":
                avg = 0.0
                try:
                    row = conn.execute("SELECT AVG(rating) FROM reviews").fetchone()
                    avg = round(float(row[0] or 0), 1)
                except Exception:
                    avg = 0.0
                return "\n".join([
                    f"⭐ گزارش رضایت کاربران",
                    f"کل نظرات: {_widget_q1(conn, 'SELECT COUNT(*) FROM reviews')} | میانگین امتیاز: {avg} از ۵",
                    f"نظرات ویجت 👍/👎: {_widget_q1(conn, 'SELECT COUNT(*) FROM giso_widget_feedback WHERE rating=1')} / {_widget_q1(conn, 'SELECT COUNT(*) FROM giso_widget_feedback WHERE rating=-1')}",
                ])
            return "\n".join([
                f"📊 گزارش کلی گیسو | امروز {today}",
                f"👥 کاربر جدید امروز: {_widget_q1(conn, 'SELECT COUNT(*) FROM giso_web_auth WHERE created_at >= ?', (today,))} | کل کاربران: {_widget_q1(conn, 'SELECT COUNT(*) FROM giso_web_auth')}",
                f"🛍 سفارش امروز: {_widget_q1(conn, 'SELECT COUNT(*) FROM product_orders WHERE created_at >= ?', (today,))} | در انتظار: {_widget_q1(conn, SQL_PENDING_ORDERS)}",
                f"💇 فروش مو امروز: {_widget_q1(conn, 'SELECT COUNT(*) FROM hair_orders WHERE created_at >= ?', (today,))} | در انتظار بررسی: {_widget_q1(conn, SQL_HAIR_WAIT)}",
                f"🎫 تیکت باز: {_widget_q1(conn, SQL_TICKETS_OPEN)} | 💬 مشاوره فعال: {_widget_q1(conn, SQL_CONSULT_OPEN)}",
            ])
    except Exception as e:
        logger.warning(f"_widget_staff_report: {e}")
    return None


def _widget_csrf_token() -> str:
    token = session.get("ai_widget_csrf")
    if not token:
        token = secrets.token_hex(16)
        session["ai_widget_csrf"] = token
        session.modified = True
    return token


def _notify_consultant_admin_new_msg(request_id, message):
    """ثبت اعلان مشاوره در مرکز اعلان؛ چت تعاملی کاربر دست‌نخورده می‌ماند."""
    try:
        from giso.panel.modules.notifications import log_notification
        log_notification(
            "analysis", "consultant", "پیام جدید مشاوره",
            f"پیام جدید مشاوره #{request_id}: {message[:300]}",
            source_type="consultant_user_message", source_id=request_id,
        )
    except Exception as exc:
        logger.exception("consultant admin notification center failed: %s", exc)

def _notify_consultant_user_new_msg(request_id, message):
    """وقتی ادمین در پنل سایت پاسخ می‌دهد، به کاربر در ربات اعلان شود."""
    try:
        from giso.base import _token_from_env, _token_from_db
        import requests as _req
        token = _token_from_env() or _token_from_db() or ""
        if not token:
            return
        with get_giso_db_conn() as conn:
            row = conn.execute("SELECT phone FROM consultant_requests WHERE id=?", (request_id,)).fetchone()
            if not row:
                return
            user_row = conn.execute("SELECT bale_id FROM giso_users WHERE phone=?", (row["phone"],)).fetchone()
            if not (user_row and str(user_row["bale_id"]).isdigit()):
                return
            cid = int(user_row["bale_id"])
        _req.post(f"https://tapi.bale.ai/bot{token}/sendMessage",
                  json={"chat_id": cid, "text": f"💬 مشاور گیسو پاسخ داد:\n{message[:300]}"},
                  timeout=10)
    except Exception as e:
        logger.warning(f"_notify_consultant_user_new_msg: {e}")


