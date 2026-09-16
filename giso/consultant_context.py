# -*- coding: utf-8 -*-
"""giso/consultant_context.py — زمینه کاملِ گزارش-محورِ کاربر برای مشاور هوشمند گیسو.

طراحی (وفق تصمیم 2026-08-31):
  * فقط «گزارش / پیش‌نهاد / تحلیل» می‌سازد؛ **هیچ اقدام یا تغییر داده‌ای انجام نمی‌دهد**.
  * هر دامنه در try مستقل است تا خطای یک جدول کل پروفایل را خراب نکند (best-effort).
  * اگر کاربر در یک دامنه **فعالیت دارد** → گزارش واقعیِ همان بخش می‌آید.
  * اگر **فعال نیست** → به‌جای داده، یک متن «راهنمایی برای شروع» برای همان بخش تعبیه می‌شود
    و مشاور بر اساس آن کاربر را راهنمایی می‌کند (نه اینکه چیزی بی‌دلیل بیاورد).

هیچ import زمان‌بارگذاری از telegram / flask ندارد؛ فقط giso.base / giso.wallet_* / giso.money.
"""
from __future__ import annotations

import json
import logging

from giso.base import get_giso_db_conn, normalize_phone, to_shamsi
from giso.money import format_toman

logger = logging.getLogger("giso_consultant_context")

_HAIR_STATUS_FA = {
    "pending": "در انتظار بررسی", "reviewing": "در حال بررسی", "priced": "قیمت‌گذاری‌شده",
    "approved": "تأییدشده", "rejected": "ردشده", "completed": "تکمیل‌شده",
}
_ORDER_STATUS_FA = {
    "pending": "در انتظار", "new": "در انتظار", "approved": "تأییدشده",
    "shipped": "ارسال‌شده", "delivered": "تحویل‌شده", "completed": "تکمیل‌شده",
    "cancelled": "لغوشده", "rejected": "ردشده",
}
_LISTING_STATUS_FA = {
    "pending_review": "در حال بررسی", "published": "منتشرشده", "rejected": "ردشده",
    "negotiating": "در حال مذاکره", "paused": "متوقف", "sold": "فروخته‌شده",
}
_OFFER_STATUS_FA = {
    "pending": "در انتظار پاسخ", "countered": "پیشنهاد متقابل", "accepted": "پذیرفته‌شده",
    "rejected": "ردشده", "sold": "معامله‌شده",
}


def _fa_num(v):
    try:
        return str(int(v or 0)).translate(str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹"))
    except Exception:
        return str(v or "")


def _site_user_id(conn, phone: str):
    try:
        row = conn.execute("SELECT id, first_name, city, name FROM giso_web_auth WHERE phone=? LIMIT 1",
                           (phone,)).fetchone()
        if not row:
            return None, None
        return int(row[0]), row
    except Exception as e:
        logger.debug(f"site user: {e}")
        return None, None


# ───────────────────── دامنه‌ها ─────────────────────

def _analysis_domain(conn, user_id: int):
    row = conn.execute(
        "SELECT id, type, created_at, ai_report_json, plan_json FROM analyses WHERE user_id=? "
        "ORDER BY id DESC LIMIT 1", (user_id,)).fetchone()
    if not row:
        return None, "تحلیل هنوز انجام نشده؛ برای شروع از بخش «انجام تحلیل» در سایت استفاده کن."
    aid, kind, date = row[0], ("مو" if row[1] == "hair" else "پوست"), (row[2] or "").split("T")[0]
    txt = f"تحلیل {kind} - #{aid} - {date}"
    try:
        report = json.loads(row[3] or "{}")
        score = report.get("overall_score") or report.get("score")
        if score:
            txt += f" - امتیاز: {score}"
    except Exception:
        pass
    plan = json.loads(row[4] or "{}") if row[4] else {}
    if isinstance(plan, dict) and plan.get("duration_weeks"):
        txt += f" | برنامه {plan['duration_weeks']} هفته‌ای"
    return txt, ""


def _detailed_hair(conn, phone: str, user_id: int):
    rows = conn.execute(
        "SELECT id, status, length_cm, estimated_price, final_price, created_at "
        "FROM hair_orders WHERE (user_id=? OR phone=?) ORDER BY id DESC LIMIT 5",
        (user_id, phone)).fetchall()
    if not rows:
        return None, "هنوز درخواست فروش مو ثبت نکردی؛ از بخش «فروش مو» در سایت شروع کن و بعدش همین‌جا وضعیتش را بپرس."
    lines = []
    for r in rows:
        st = _HAIR_STATUS_FA.get(r[1], r[1])
        price = r[4] or r[3]
        lines.append(f"#{r[0]} {r[2]}سانتی {st} - {price or 'قیمت‌نامشخص'} تومان ({to_shamsi(r[5], with_time=False)})")
    return " - ".join(lines), ""


def _detailed_orders(conn, phone: str, user_id: int):
    rows = conn.execute(
        "SELECT po.id, po.status, po.quantity, po.tracking_code, po.shipping_cost, po.created_at, p.name "
        "FROM product_orders po LEFT JOIN products p ON p.id=po.product_id "
        "WHERE (po.user_id=? OR po.phone=?) ORDER BY po.id DESC LIMIT 5",
        (user_id, phone)).fetchall()
    if not rows:
        return None, "خریدی از فروشگاه نداری؛ برای شروع به فروشگاه گیسو سر بزن."
    lines = []
    for r in rows:
        st = _ORDER_STATUS_FA.get(r[1], r[1])
        name = r[6] or "محصول"
        line = f"#{r[0]} {name} x{r[2]} {st}"
        if r[3]:
            line += f" (پیگیری: {r[3]})"
        lines.append(line)
    return " - ".join(lines), ""


def _wallet_domain(uid: int, phone: str):
    try:
        from giso.wallet_core import get_wallet_balances, get_user_rank, get_user_transactions
        from giso.wallet_missions import list_missions_for_user
    except Exception as e:
        logger.debug(f"wallet import: {e}")
        return None, ""
    bal = get_wallet_balances(uid) or {}
    cash = int(bal.get("cash", 0) or 0)
    spend = int(bal.get("spend", 0) or 0)
    rank = get_user_rank(phone) or {}
    tx = get_user_transactions(uid, limit=3) or []
    missions = list_missions_for_user(uid) or []
    done = sum(1 for m in missions if _is_mission_done(m)) if missions else 0
    if cash <= 0 and spend <= 0 and not tx and not done:
        return None, "هنوز کیف پولت فعال نشده؛ با انجام مأموریت‌ها یا خرید، اعتبار می‌گیری."
    parts = [
        f"موجودی نقدی {format_toman(cash)} | اعتبار مصرفی {format_toman(spend)}",
        f"رتبه {rank.get('emoji', '')} {rank.get('name')} | {_fa_num(rank.get('score', 0))} امتیاز",
    ]
    if missions:
        parts.append(f"مأموریت‌ها: {_fa_num(done)} از {_fa_num(len(missions))} تکمیل")
    if tx:
        latest = tx[0]
        parts.append(f"آخرین تراکنش: {latest.get('title') or latest.get('amount') or '—'}")
    return " | ".join(parts), ""


def _is_mission_done(m) -> bool:
    try:
        return bool(m.get("completed")) or bool(m.get("done"))
    except Exception:
        return False


def _marketplace_domain(conn, phone: str, user_id: int):
    # ستون views_count و offers_count به‌صورت کامل لو می‌رود تا مشاور بتواند به
    # «چند تا بازدید داشته؟» پاسخ واقعی-با-عدد بدهد (نه اینکه بگوید در دسترس نیست).
    listings = conn.execute(
        "SELECT id, hair_type, length_cm, seller_asking_price, status, "
        "views_count, offers_count, city FROM hair_listings "
        "WHERE seller_user_id=? AND COALESCE(deleted_at, '')='' ORDER BY id DESC LIMIT 4",
        (user_id,)).fetchall()
    offers = conn.execute(
        "SELECT bo.id, bo.offer_amount, bo.status, hl.hair_type, hl.length_cm "
        "FROM buyer_offers bo JOIN hair_listings hl ON hl.id=bo.listing_id "
        "WHERE hl.seller_user_id=? ORDER BY bo.id DESC LIMIT 4",
        (user_id,)).fetchall()
    if not listings and not offers:
        return None, "در بازارچه هنوز آگهی یا پیشنهادی نداری؛ برای فروش مو از «بازارچه مو» در سایت شروع کن."
    parts = []
    if listings:
        lparts = []
        for r in listings:
            _views = _fa_num(r[5])
            _offers = _fa_num(r[6])
            _city = (r[7] or "").strip()
            _city_txt = f" ({_city})" if _city else ""
            lparts.append(
                f"#{r[0]} {r[1]} {r[2]}سانتی{_city_txt} {_LISTING_STATUS_FA.get(r[4], r[4])} "
                f"({r[3] or '—'}تومان) - {_views} بازدید / {_offers} پیشنهاد"
            )
        parts.append("آگهی‌های تو: " + " | ".join(lparts))
    if offers:
        oparts = [f"#{r[0]} روی آگهی {r[3]} {r[4]}سانتی {_OFFER_STATUS_FA.get(r[2], r[2])} ({r[1]}تومان)"
                  for r in offers]
        parts.append("پیشنهادها: " + " | ".join(oparts))
    return " | ".join(parts), ""


def _center_domain(conn, user_id: int):
    center = conn.execute(
        "SELECT id, name, city, category, status FROM beauty_centers WHERE owner_user_id=? ORDER BY id DESC LIMIT 1",
        (user_id,)).fetchone()
    if not center:
        return None, "هنوز مرکز زیبایی ثبت نکردی؛ از «ثبت مرکز زیبایی» در سایت اقدام کن و بعد اینجا وضعیت و پیام‌هایش را بپرس."
    txt = f"{center[1]}، {center[2]} ({center[4] or 'فعال'})"
    try:
        convo = conn.execute(
            "SELECT id FROM beauty_center_conversations WHERE center_id=? ORDER BY id DESC LIMIT 1",
            (center[0],)).fetchone()
        if convo:
            unread = conn.execute(
                "SELECT COUNT(*) FROM beauty_center_messages WHERE conversation_id=? AND is_read=0",
                (convo[0],)).fetchone()
            if unread and unread[0]:
                txt += f" | {_fa_num(unread[0])} پیام خوانده‌نشده"
    except Exception:
        pass
    return txt, ""


def _tickets_domain(conn, phone: str):
    rows = conn.execute(
        "SELECT id, status, COALESCE(NULLIF(admin_reply,''),'') FROM giso_support_tickets "
        "WHERE phone=? OR user_bale_id=? ORDER BY id DESC LIMIT 3", (phone, 0)).fetchall()
    if not rows:
        return None, "تیکت پشتیبانی باز نداری؛ اگر سؤالی داری از دکمه «پشتیبانی» استفاده کن."
    parts = []
    for r in rows:
        st = "پاسخ‌داده‌شده" if r[2] else "در انتظار پاسخ"
        parts.append(f"#{r[0]} {st}")
    return " - ".join(parts), ""


def _notifications_domain(conn, user_id: int):
    rows = conn.execute(
        "SELECT COUNT(*) FROM giso_notifications WHERE recipient_id=? AND status='unread'",
        (user_id,)).fetchone()
    unread = int(rows[0]) if rows else 0
    if unread == 0:
        return None, "اعلان خوانده‌نشده‌ای نداری؛ هر خبر مهمی باشد اینجا نمایش داده می‌شود."
    try:
        sample = conn.execute(
            "SELECT title FROM giso_notifications WHERE recipient_id=? AND status='unread' "
            "ORDER BY id DESC LIMIT 2", (user_id,)).fetchall()
        titles = "، ".join(r[0] for r in sample)
        return f"{_fa_num(unread)} اعلان خوانده‌نشده ({titles})", ""
    except Exception:
        return f"{_fa_num(unread)} اعلان خوانده‌نشده", ""


# ───────────────────── سازنده اصلی ─────────────────────

def build_user_consultant_context(phone: str, user_bale_id=None) -> dict:
    """زمینه کامل گزارش-محور کاربر برای مشاور هوشمند (فقط گزارش/پیشنهاد/تحلیل).

    خروجی dict با کلیدهای هم‌نام placeholders قالب `consultant_bot.txt` به‌علاوه:
      * `inactive_guidance` — متن راهنماییِ بخش‌های غیرفعال (برای وقتی کاربر درباره‌شان پرسید).
    برای هر دامنه: اگر فعال → مقدار؛ اگر غیرفعال → رشتهٔ راهنمایی.
    """
    phone = normalize_phone(phone or "") or phone or ""
    ctx = {
        "user_name": "دوست عزیز", "user_phone": phone or "", "user_city": "",
        "last_analysis_info": "تحلیلی ثبت نشده", "active_plan_info": "برنامه فعالی نیست",
        "checklist_info": "چک‌لیست فعالی نیست", "product_requests_info": "درخواست محصولی نیست",
        "hair_orders_info": "سفارش فروش مو ثبت نشده", "shop_orders_info": "خریدی از فروشگاه نیست",
        "key_notes": "گفتگوی جدید",
        # جدید (report-only)
        "wallet_info": "", "marketplace_info": "", "center_info": "",
        "tickets_info": "", "notifications_info": "",
        "inactive_guidance": "",
    }
    inactive = []
    try:
        with get_giso_db_conn() as conn:
            uid, user = _site_user_id(conn, phone)
            if not uid:
                # کاربر هنوز حساب سایت ندارد → همه‌چیز را با راهنمایی پر کن
                return {**ctx, "inactive_guidance":
                        "این کاربر هنوز حساب سایت ندارد؛ از «ثبت‌نام» در سایت شروع کند."}
            ctx["user_name"] = str((user[1] or user[3] or "دوست عزیز").strip() or "دوست عزیز")
            ctx["user_city"] = str(user[2] or "").strip()

            # تحلیل
            a, a_g = _analysis_domain(conn, uid)
            if a:
                ctx["last_analysis_info"] = a
                ctx["active_plan_info"], ctx["checklist_info"] = _plan_from_analysis(conn, uid)
                ctx["key_notes"] = _analysis_notes(conn, uid)
            else:
                inactive.append("تحلیل")

            # فروش مو
            h, h_g = _detailed_hair(conn, phone, uid)
            ctx["hair_orders_info"] = h or h_g
            if not h:
                inactive.append("فروش مو")

            # سفارش‌ها
            o, o_g = _detailed_orders(conn, phone, uid)
            ctx["shop_orders_info"] = o or o_g
            if not o:
                inactive.append("خرید از فروشگاه")

            # بازارچه
            m, m_g = _marketplace_domain(conn, phone, uid)
            ctx["marketplace_info"] = m or m_g
            if not m:
                inactive.append("بازارچه")

            # مرکز
            ce, ce_g = _center_domain(conn, uid)
            ctx["center_info"] = ce or ce_g
            if not ce:
                inactive.append("مرکز زیبایی")

            # تیکت‌ها
            t, t_g = _tickets_domain(conn, phone)
            ctx["tickets_info"] = t or t_g
            if not t:
                inactive.append("پشتیبانی")

            # اعلان‌ها
            n, n_g = _notifications_domain(conn, uid)
            ctx["notifications_info"] = n or n_g
            if not n:
                inactive.append("اعلان‌ها")

            ctx["product_requests_info"] = _product_requests(conn, uid, phone)

    except Exception as e:
        logger.warning(f"build_user_consultant_context: {e}")

    # کیف پول (خارج از همان conn تا از سرویس اختصاصی استفاده شود)
    try:
        with get_giso_db_conn() as conn:
            uid2, _ = _site_user_id(conn, phone)
            if uid2:
                w, w_g = _wallet_domain(uid2, phone)
                ctx["wallet_info"] = w or w_g
                if not w:
                    inactive.append("کیف پول")
    except Exception as e:
        logger.debug(f"wallet (separate): {e}")

    guides = []
    if "مرکز زیبایی" in inactive:
        guides.append("مرکز زیبایی: هنوز ثبت نکردی. از /dashboard/beauty-center می‌تونی شروع کنی.")
    if "تحلیل" in inactive:
        guides.append("آنالیز: هنوز انجام ندادی. از /analysis شروع کن.")
    if "خرید از فروشگاه" in inactive:
        guides.append("فروشگاه: هنوز خریدی نداری.")
    extra = ("\n".join(guides) + "\n") if guides else ""
    ctx["inactive_guidance"] = extra + (
        "بخش‌هایی که هنوز فعال نشده‌اند: " + "، ".join(inactive) + ". "
        "برای شروع هر کدام، راهنمایی‌اش را در گزارش همان بخش ببین و به کاربر پیشنهاد بده."
        if inactive else "کاربر در همهٔ بخش‌ها فعالیت دارد."
    )
    return ctx


def _plan_from_analysis(conn, user_id: int):
    row = conn.execute(
        "SELECT plan_json, checklist_progress FROM analyses WHERE user_id=? ORDER BY id DESC LIMIT 1",
        (user_id,)).fetchone()
    try:
        plan = json.loads(row[0] or "{}") if row and row[0] else {}
        weeks = plan.get("duration_weeks") if isinstance(plan, dict) else None
        plan_txt = f"برنامه {weeks} هفته‌ای فعال" if weeks else "برنامه فعالی نیست"
    except Exception:
        plan_txt = "برنامه فعالی نیست"
    # چک‌لیست: «done از total تیک خورده» (سبک ASCII برای سازگاری)
    try:
        progress = json.loads(row[1] or "{}") if row and row[1] else {}
        done = sum(1 for v in progress.values() if v) if isinstance(progress, dict) else 0
        try:
            checklist = plan.get("checklist") if isinstance(plan, dict) else {}
            if isinstance(checklist, dict):
                total = len(checklist.get("weeks") or [])
            elif isinstance(checklist, list):
                total = len(checklist)
            else:
                total = 0
        except Exception:
            total = 0
        check_txt = f"{done} از {total} تیک خورده" if total else "چک‌لیست فعالی نیست"
    except Exception:
        check_txt = "چک‌لیست فعالی نیست"
    return plan_txt, check_txt


def _analysis_notes(conn, user_id: int) -> str:
    row = conn.execute(
        "SELECT consultant_key_notes FROM analyses WHERE user_id=? ORDER BY id DESC LIMIT 1",
        (user_id,)).fetchone()
    return str(row[0] or "").strip()[:500] or "گفتگوی جدید" if row else "گفتگوی جدید"


def _product_requests(conn, user_id: int, phone: str):
    row = conn.execute(
        "SELECT COUNT(*) FROM product_requests WHERE user_id=? OR phone=?",
        (user_id, phone)).fetchone()
    if row and row[0]:
        return f"{int(row[0])} درخواست ثبت شده"
    return "درخواست محصولی نیست"
