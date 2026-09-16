# -*- coding: utf-8 -*-
"""giso/bot_user_actions.py — عملیات کاربر در ربات (۲۴ نمای درون‌باتی + همگام با سایت).

طراحی:
  * فقط خواندنی/آینه‌ای است؛ هیچ رفتار مالی یا مسیر سایت را تغییر نمی‌دهد.
  * هر تابع کاملاً در try/except است؛ هر خطا پیام کوتاه «خطا/ناموجود» می‌دهد و جریان اصلی نمی‌شکند.
  * اتصال سایت/ربات از طریق شماره موبایل (giso_users.phone ↔ giso_web_auth.phone) روی giso.db مشترک.
  * callback_data ها همه پیشوند منحصر‌به‌فرد «ua|» دارند و با هیچ callback فعلی تداخل ندارند.
  * عملیات نوشتنیِ مالی/حساس (تأیید قیمت، قبول معامله، تمدید مرکز، چت) عمداً در ربات اجرا نمی‌شوند
    و با دکمه‌ی لینک به پنل امن سایت هدایت می‌شوند (طبق قاعده‌ی تغییرندادن رفتار مالی).

هیچ import زمان‌بارگذاری از telegram ندارد؛ دکمه‌ها lazy ساخته می‌شوند تا ماژول بدون تلگرام هم import شود.
"""
import json
import logging
import time

from giso.base import (
    get_giso_db_conn, get_site_url, normalize_phone, to_shamsi, display_phone, _fa_num,
)
from giso.money import format_toman
from giso.bot_admin_utils import (
    _shop_order_rows, _group_shop_order_rows, _get_giso_site_url,
)

logger = logging.getLogger("giso_bot_user_actions")

# وضعیت‌های فارسی انسانی برای جداول مختلف
_HAIR_STATUS_FA = {
    "pending": "در انتظار بررسی ⏳",
    "reviewing": "در حال بررسی 🔍",
    "priced": "قیمت‌گذاری شده 💰",
    "approved": "تأیید شده ✅",
    "rejected": "رد شده ❌",
    "completed": "تکمیل شده 🎉",
}
_ORDER_STATUS_FA = {
    "pending": "در انتظار ⏳", "new": "در انتظار ⏳", "approved": "تأیید شد ✅",
    "shipped": "ارسال شد 🚚", "delivered": "تحویل داده شد 📦",
    "completed": "تکمیل شد ✅", "cancelled": "لغو شد ⛔", "rejected": "رد شد ❌",
}
_LISTING_STATUS_FA = {
    "pending_review": "در حال بررسی 🔍", "published": "منتشرشده 🟢",
    "rejected": "رد شده ❌", "negotiating": "در حال مذاکره 💬",
    "paused": "متوقف ⏸", "sold": "فروخته‌شده 🔴",
}
_OFFER_STATUS_FA = {
    "pending": "در انتظار پاسخ ⏳", "countered": "پیشنهاد متقابل ↩️",
    "accepted": "پذیرفته‌شده ✅", "rejected": "رد شده ❌", "sold": "معامله شد 🎉",
}


# ───────────────────────── کمک‌سازه‌ها ─────────────────────────
def _site_url() -> str:
    """آدرس پایه‌ی سایت؛ همیشه از giso_config (site_base_url) از طریق base.get_site_url.

    هیچ آدرس hardcode‌ای در این ماژول استفاده نمی‌شود؛ fallback داخل get_site_url است.
    """
    return get_site_url()


def _safe(value):
    return str("" if value is None else value).replace("<", "‹").replace(">", "›").replace("&", "و")


def _short(value, n=60):
    value = _safe(value)
    return value if len(value) <= n else value[:n] + "…"


def _hair_price_text(raw):
    """قیمت فروش مو در DB ممکن است عدد خام یا متن فارسی باشد؛ اگر عدد بود به تومان قالب می‌دهیم."""
    raw = (raw or "").strip()
    if not raw:
        return ""
    digits = "".join(ch for ch in raw.translate(str.maketrans("۰۱۲۳۴۵۶۷۸۹", "0123456789")) if ch.isdigit())
    if digits and len(digits) >= 4 and digits == raw.replace(",", "").replace(" ", ""):
        try:
            return format_toman(int(digits))
        except Exception:
            return raw
    return raw


_CENTER_STATUS_FA = {
    "pending_review": "در حال بررسی 🔍", "published": "منتشرشده 🟢",
    "rejected": "رد شده ❌", "paused": "متوقف ⏸", "closed": "بسته‌شده ⚫",
    "reviewing": "در حال بررسی 🔍",
}


def _btn(text, data=None, url=None):
    """ساخت دکمه‌ی inline (lazy) — dict ساده برمی‌گرداند؛ در dispatch به InlineKeyboardButton تبدیل می‌شود."""
    return {"t": text, "d": data, "u": url}


def _kb(rows):
    """rows: لیست لیست‌های dict دکمه."""
    return rows


def _site_user_id(conn, phone):
    np = normalize_phone(phone or "")
    if not np:
        return None, ""
    row = conn.execute(
        "SELECT id FROM giso_web_auth WHERE phone=? LIMIT 1", (np,)
    ).fetchone()
    return (int(row[0]) if row else None), np


def _first_plan_day_items(plan):
    """استخراج آیتم‌های چک‌لیست از plan_json (سازگار با چند ساختار)."""
    items = []
    if not plan:
        return items
    try:
        data = plan if isinstance(plan, dict) else json.loads(plan or "{}")
        cl = data.get("checklist")
        if isinstance(cl, dict):
            for w in cl.get("weeks", []) or []:
                wn = w.get("week_number", 1) if isinstance(w, dict) else 1
                for i, txt in enumerate(w.get("items", []) or [] if isinstance(w, dict) else []):
                    items.append({"id": f"w{wn}-{i}", "text": str(txt)})
        elif isinstance(cl, list):
            for i, it in enumerate(cl):
                if isinstance(it, dict):
                    items.append({"id": str(it.get("id", i)), "text": str(it.get("text", ""))})
                else:
                    items.append({"id": str(i), "text": str(it)})
        elif isinstance(data.get("weeks"), list):
            for wi, w in enumerate(data["weeks"]):
                for di, txt in enumerate((w.get("items") or []) if isinstance(w, dict) else []):
                    items.append({"id": f"w{wi+1}-{di}", "text": str(txt)})
    except Exception as e:
        logger.debug(f"plan parse: {e}")
    return items[:15]


# ───────────────────────── A: آنالیز ─────────────────────────
def _latest_analysis(conn, uid, np):
    return conn.execute(
        "SELECT id, type, ai_report_json, plan_json, created_at FROM analyses "
        "WHERE (user_id=? OR phone=?) ORDER BY id DESC LIMIT 1",
        (uid if uid is not None else -1, np),
    ).fetchone()


def anal_last(phone):
    try:
        with get_giso_db_conn() as conn:
            uid, np = _site_user_id(conn, phone)
            a = _latest_analysis(conn, uid, np)
            site = _site_url()
            if not a:
                return ("🔬 هنوز تحلیلی ثبت نکردی.\nبرای تحلیل مو/پوست از سایت اقدام کن:",
                        _kb([[_btn("🌐 انجام تحلیل", url=f"{site}/analysis")]]))
            report = {}
            try:
                report = json.loads(a["ai_report_json"] or "{}")
            except Exception:
                report = {}
            type_fa = "مو 💇" if (a["type"] or "hair") == "hair" else "پوست ✨"
            lines = [f"🔬 آخرین آنالیز تو ({type_fa} — {to_shamsi(a['created_at'], with_time=False)}):",
                     "━━━━━━━━━━━━━━━━"]
            score = report.get("overall_score") or report.get("score")
            if score:
                lines.append(f"📊 امتیاز سلامت: {_fa_num(score)}/100")
            if report.get("overall_status"):
                lines.append(f"📌 وضعیت: {_short(report['overall_status'], 80)}")
            problems = report.get("main_problems") or report.get("problems") or []
            if problems:
                plist = []
                for p in problems[:3]:
                    if isinstance(p, dict):
                        plist.append(_short(p.get("name") or p.get("title") or "", 30))
                    else:
                        plist.append(_short(p, 30))
                if plist:
                    lines.append("⚠️ مشکلات اصلی: " + " | ".join(x for x in plist if x))
            actions = report.get("immediate_actions") or report.get("actions") or report.get("recommendations") or []
            if actions and isinstance(actions, list):
                first = actions[0]
                txt = first.get("text") if isinstance(first, dict) else first
                if txt:
                    lines.append(f"✅ اقدام فوری: {_short(txt, 70)}")
            lines.append("━━━━━━━━━━━━━━━━")
            rows = [
                [_btn("📋 برنامه هفتگی", "ua|anal|plan"),
                 _btn("✅ چک‌لیست", "ua|anal|check")],
                [_btn("🛒 محصولات پیشنهادی", "ua|anal|products"),
                 _btn("💬 درخواست مشاور", "ua|anal|consult")],
                [_btn("🌐 گزارش کامل در سایت", url=f"{site}/analysis/{a['type']}/report?id={a['id']}")],
            ]
            return "\n".join(lines), _kb(rows)
    except Exception as e:
        logger.warning(f"anal_last: {e}")
        return "⚠️ دریافت آخرین آنالیز ممکن نشد.", _kb([])


def anal_plan(phone):
    try:
        with get_giso_db_conn() as conn:
            uid, np = _site_user_id(conn, phone)
            a = _latest_analysis(conn, uid, np)
            site = _site_url()
            if not a or not (a["plan_json"] or "").strip() or a["plan_json"] in ("{}", ""):
                return ("📋 برنامه‌ی هفتگی هنوز برای تو ساخته نشده.",
                        _kb([[_btn("🌐 ساخت برنامه در سایت", url=f"{site}/analysis")]]))
            plan = json.loads(a["plan_json"] or "{}")
            weeks = plan.get("weeks") if isinstance(plan, dict) else None
            lines = ["📋 برنامه‌ی هفتگی آنالیز تو:", "━━━━━━━━━━━━━━━━"]
            if isinstance(weeks, list):
                for w in weeks[:7]:
                    if not isinstance(w, dict):
                        continue
                    wn = w.get("week_number") or w.get("week") or "؟"
                    goal = _short(w.get("goal") or w.get("title") or "", 50)
                    items = w.get("items") or []
                    head = f"هفته {_fa_num(wn)}" + (f": {goal}" if goal else "")
                    lines.append(f"🗓 {head}")
                    for it in items[:2]:
                        lines.append(f"   • {_short(it if isinstance(it, str) else (it.get('text') if isinstance(it, dict) else ''), 55)}")
            else:
                # ساختار تخت: همان چک‌لیست
                for it in _first_plan_day_items(plan)[:7]:
                    lines.append(f"• {_short(it['text'], 60)}")
            lines.append("━━━━━━━━━━━━━━━━")
            lines.append("تیک‌زدن پیشرفت در پنل سایت انجام می‌شود.")
            rows = [[_btn("✅ چک‌لیست", "ua|anal|check"), _btn("🔙 آخرین آنالیز", "ua|anal|last")],
                    [_btn("🌐 برنامه کامل در سایت", url=f"{site}/analysis/plan?id={a['id']}")]]
            return "\n".join(lines), _kb(rows)
    except Exception as e:
        logger.warning(f"anal_plan: {e}")
        return "⚠️ دریافت برنامه ممکن نشد.", _kb([])


def anal_check(phone):
    """نمایش فقط‌خواندنی چک‌لیست؛ تیک‌زدن در سایت (جلوگیری از ناسازگاری وضعیت)."""
    try:
        with get_giso_db_conn() as conn:
            uid, np = _site_user_id(conn, phone)
            a = _latest_analysis(conn, uid, np)
            site = _site_url()
            if not a:
                return ("✅ چک‌لیستی موجود نیست.", _kb([[_btn("🌐 تحلیل در سایت", url=f"{site}/analysis")]]))
            # پیشرفت واقعی از ستون checklist_progress در جدول analyses
            done = set()
            try:
                cp_row = conn.execute(
                    "SELECT checklist_progress FROM analyses WHERE id=?", (a["id"],)
                ).fetchone()
                cp = json.loads((cp_row["checklist_progress"] if cp_row else "") or "{}")
                if isinstance(cp, dict):
                    done = {k for k, v in cp.items() if v}
            except Exception:
                done = set()
            try:
                plan_obj = json.loads(a["plan_json"] or "{}")
            except Exception:
                plan_obj = {}
            items = _first_plan_day_items(plan_obj)
            if not items:
                return ("✅ چک‌لیستی برای این تحلیل تعریف نشده.",
                        _kb([[_btn("🔙 آخرین آنالیز", "ua|anal|last")]]))
            total = len(items)
            completed = sum(1 for it in items if it["id"] in done)
            pct = int(completed / total * 100) if total else 0
            lines = [f"✅ چک‌لیست پیشرفت: {_fa_num(completed)}/{_fa_num(total)} ({_fa_num(pct)}٪)",
                     "━━━━━━━━━━━━━━━━"]
            for it in items:
                lines.append(f"{'✅' if it['id'] in done else '⬜'} {_short(it['text'], 55)}")
            lines.append("━━━━━━━━━━━━━━━━")
            lines.append("برای تیک‌زدن، پنل سایت را باز کن.")
            rows = [[_btn("📋 برنامه هفتگی", "ua|anal|plan"), _btn("🔙 آخرین آنالیز", "ua|anal|last")],
                    [_btn("🌐 مدیریت چک‌لیست در سایت", url=f"{site}/analysis/plan?id={a['id']}")]]
            return "\n".join(lines), _kb(rows)
    except Exception as e:
        logger.warning(f"anal_check: {e}")
        return "⚠️ دریافت چک‌لیست ممکن نشد.", _kb([])


def anal_consult(phone):
    """A4: ثبت درخواست مشاور (INSERT در consultant_requests) — عملیات نوشتنیِ غیرمالی و
    هم‌مسیر با منطق سایت؛ idempotent نیست ولی فقط یک رکورد درخواست می‌سازد و به ادمین‌ها اعلان می‌دهد."""
    try:
        with get_giso_db_conn() as conn:
            uid, np = _site_user_id(conn, phone)
            if not uid:
                site = _site_url()
                return ("برای درخواست مشاور ابتدا در سایت حساب بساز.",
                        _kb([[_btn("🌐 ثبت‌نام در سایت", url=f"{site}/register")]]))
            a = _latest_analysis(conn, uid, np)
            # یک درخواست باز مشابه امروز دوباره نساز
            existing = conn.execute(
                "SELECT id FROM consultant_requests WHERE phone=? AND status IN ('new','reviewing','chatting') "
                "ORDER BY id DESC LIMIT 1", (np,)
            ).fetchone()
            if existing:
                return ("💬 درخواست مشاوره‌ی باز قبلی‌ات در حال پیگیری است.\nکارشناس به‌زودی پاسخ می‌دهد.",
                        _kb([[_btn("💬 گفتگوهای مشاوره در سایت", url=f"{_site_url()}/dashboard/chats")]]))
            name_row = conn.execute("SELECT name FROM giso_web_auth WHERE id=?", (uid,)).fetchone()
            cur = conn.execute(
                "INSERT INTO consultant_requests (user_id, phone, city, customer_name, analysis_id, "
                "initial_message, status, created_at, updated_at) VALUES (?,?,?,?,?,?,?,datetime('now','localtime'),datetime('now','localtime'))",
                (uid, np, "", _short(name_row["name"] if name_row else "", 60),
                 a["id"] if a else None, "درخواست مشاور از ربات گیسو", "new"),
            )
            conn.commit()
            rid = cur.lastrowid
        # اعلان به ادمین‌ها (best-effort، از طریق مرکز اعلان سایت)
        try:
            from giso.panel.modules.notifications import safe_log
            safe_log("analysis", "consultant_request", "درخواست مشاوره جدید",
                     f"درخواست مشاور #{rid} از {np}", source_type="consultant_request", source_id=int(rid))
        except Exception:
            pass
        return ("✅ درخواست مشاوره ثبت شد. کارشناس به‌زودی از همین ربات یا سایت پاسخ می‌دهد 🌸",
                _kb([[_btn("💬 گفتگوهای مشاوره", url=f"{_site_url()}/dashboard/chats")],
                     [_btn("🔙 منوی عملیات", "ua|consult|report")]]))
    except Exception as e:
        logger.warning(f"anal_consult: {e}")
        return "⚠️ ثبت درخواست مشاور ممکن نشد؛ لطفاً از سایت اقدام کن.", _kb([])


def anal_products(phone):
    """A5: محصولات پیشنهادی (۳ محصول فعال فروشگاه) + لینک خرید."""
    try:
        with get_giso_db_conn() as conn:
            uid, np = _site_user_id(conn, phone)
            rows = conn.execute(
                "SELECT id, name, price FROM products "
                "WHERE COALESCE(in_stock,1)=1 AND COALESCE(publish_status,'published')='published' "
                "ORDER BY id DESC LIMIT 3"
            ).fetchall()
            site = _site_url()
            if not rows:
                return ("🛒 فعلاً محصول پیشنهادی فعالی نیست.",
                        _kb([[_btn("🔙 منوی عملیات", "ua|consult|report")]]))
            lines = ["🛒 محصولات پیشنهادی فروشگاه گیسو:", "━━━━━━━━━━━━━━━━"]
            for p in rows:
                lines.append(f"• {_short(p['name'], 40)} — {format_toman(p['price'] or 0)}")
            lines.append("━━━━━━━━━━━━━━━━")
            lines.append("خرید و پرداخت در محل از سایت انجام می‌شود.")
            rows_kb = [[_btn("🌐 ورود به فروشگاه", url=f"{site}/shop")],
                       [_btn("🔙 منوی عملیات", "ua|consult|report")]]
            return "\n".join(lines), _kb(rows_kb)
    except Exception as e:
        logger.warning(f"anal_products: {e}")
        return "⚠️ دریافت محصولات ممکن نشد.", _kb([])


# ───────────────────────── B: فروش مو ─────────────────────────
def hair_status(phone):
    try:
        with get_giso_db_conn() as conn:
            _, np = _site_user_id(conn, phone)
            if not np:
                return ("برای دیدن درخواست‌ها ابتدا شماره‌ات را به اشتراک بگذار.", _kb([]))
            orders = conn.execute(
                "SELECT id, status, final_price, estimated_price, length_cm, created_at "
                "FROM hair_orders WHERE phone=? ORDER BY id DESC LIMIT 6", (np,)
            ).fetchall()
            site = _site_url()
            if not orders:
                return ("💇 هنوز درخواست فروش مویی ثبت نکردی.",
                        _kb([[_btn("🌐 ثبت درخواست فروش مو", url=f"{site}/hair-sale")],
                             [_btn("🔙 منوی عملیات", "ua|consult|report")]]))
            lines = ["💇 درخواست‌های فروش موی تو:", "━━━━━━━━━━━━━━━━"]
            order_rows = []
            for o in orders:
                st = _HAIR_STATUS_FA.get(o["status"], o["status"])
                price = _hair_price_text(o["final_price"] or o["estimated_price"])
                lines.append(f"#{_fa_num(o['id'])} — {st}")
                lines.append(f"   طول: {_fa_num(o['length_cm'] or '—')} سانت | {to_shamsi(o['created_at'], with_time=False)}")
                if price:
                    lines.append(f"   💰 قیمت: {price}")
                # دکمه‌ی «قیمت» فقط برای درخواستی که واقعاً قیمت‌گذاری شده؛
                # برای درخواست ردشده/بی‌قیمت دکمه‌ای که به پیام «قیمت ثبت نشده» بخورد ساخته نمی‌شود.
                if (o["final_price"] or "").strip() and o["status"] not in ("rejected", "cancelled"):
                    order_rows.append([_btn(f"💰 قیمت درخواست #{_fa_num(o['id'])}", f"ua|hair|price|{o['id']}")])
            lines.append("━━━━━━━━━━━━━━━━")
            rows = order_rows + [
                [_btn("💬 چت با کارشناس", "ua|hair|chatlist")],
                [_btn("🌐 ثبت درخواست جدید", url=f"{site}/hair-sale")],
                [_btn("🔙 منوی عملیات", "ua|consult|report")],
            ]
            return "\n".join(lines), _kb(rows)
    except Exception as e:
        logger.warning(f"hair_status: {e}")
        return "⚠️ دریافت وضعیت درخواست‌ها ممکن نشد.", _kb([])


def hair_price(phone, order_id):
    try:
        with get_giso_db_conn() as conn:
            _, np = _site_user_id(conn, phone)
            o = conn.execute(
                "SELECT id, final_price, admin_note, status FROM hair_orders WHERE id=? AND phone=?",
                (int(order_id), np),
            ).fetchone()
            site = _site_url()
            if not o:
                return ("درخواستی با این شماره پیدا نشد.", _kb([[_btn("🔙 وضعیت‌ها", "ua|hair|status")]]))
            if not (o["final_price"] or "").strip():
                return (f"⏳ برای درخواست #{_fa_num(o['id'])} هنوز قیمت نهایی ثبت نشده است.",
                        _kb([[_btn("🔙 وضعیت‌ها", "ua|hair|status")]]))
            _p = _hair_price_text(o["final_price"])
            lines = [f"💰 قیمت پیشنهادی کارشناس برای درخواست #{_fa_num(o['id'])}:",
                     "━━━━━━━━━━━━━━━━",
                     f"💎 {_p or '—'}",
                     "━━━━━━━━━━━━━━━━"]
            if o["admin_note"]:
                lines.append(f"📝 یادداشت کارشناس: {_short(o['admin_note'], 120)}")
            # تأیید/اعتراض عملیات واجد اثر وضعیت است → به پنل سایت هدایت می‌شود (تغییر رفتار مالی ندهیم)
            lines.append("برای تأیید یا ثبت اعتراض، از پنل سایت اقدام کن.")
            rows = [[_btn("📝 ثبت اعتراض در سایت", url=f"{site}/dashboard/hair")],
                    [_btn("💬 گفتگو با کارشناس", "ua|hair|chatlist")],
                    [_btn("🔙 وضعیت‌ها", "ua|hair|status")]]
            return "\n".join(lines), _kb(rows)
    except Exception as e:
        logger.warning(f"hair_price: {e}")
        return "⚠️ دریافت قیمت ممکن نشد.", _kb([])


def hair_chat_list(phone):
    """لیست درخواست‌هایی که گفتگو دارند → ورود به چت در سایت (خواندن آخرین پیام در ربات)."""
    try:
        with get_giso_db_conn() as conn:
            _, np = _site_user_id(conn, phone)
            orders = conn.execute(
                "SELECT DISTINCT h.id, h.status FROM hair_messages m "
                "JOIN hair_orders h ON h.id=m.order_id WHERE h.phone=? "
                "ORDER BY m.id DESC LIMIT 8", (np,)
            ).fetchall()
            site = _site_url()
            if not orders:
                return ("💬 گفتگوی فعالی با کارشناس نداری.\nبا ثبت یا باز کردن درخواست می‌توانی پیام بفرستی.",
                        _kb([[_btn("🔙 وضعیت‌ها", "ua|hair|status")]]))
            lines = ["💬 گفتگوهای فروش موی تو:", "━━━━━━━━━━━━━━━━"]
            rows = []
            for o in orders:
                last = conn.execute(
                    "SELECT sender, message, created_at FROM hair_messages WHERE order_id=? ORDER BY id DESC LIMIT 1",
                    (o["id"],),
                ).fetchone()
                who = "کارشناس" if (last and last["sender"] == "admin") else "شما"
                lines.append(f"#{_fa_num(o['id'])} — آخرین پیام {who}: {_short(last['message'] if last else '', 50)}")
                rows.append([_btn(f"💬 ادامه گفتگوی #{_fa_num(o['id'])}", url=f"{site}/dashboard/hair")])
            rows.append([_btn("🔙 وضعیت‌ها", "ua|hair|status")])
            lines.append("━━━━━━━━━━━━━━━━")
            lines.append("ادامه و ارسال پیام در پنل سایت انجام می‌شود.")
            return "\n".join(lines), _kb(rows)
    except Exception as e:
        logger.warning(f"hair_chat_list: {e}")
        return "⚠️ دریافت گفتگوها ممکن نشد.", _kb([])


# ───────────────────────── C: بازارچه ─────────────────────────
def mkt_my(phone):
    try:
        with get_giso_db_conn() as conn:
            uid, np = _site_user_id(conn, phone)
            site = _site_url()
            if not uid:
                return ("برای دیدن آگهی‌ها ابتدا در سایت حساب بساز.",
                        _kb([[_btn("🌐 ثبت‌نام", url=f"{site}/register")]]))
            listings = conn.execute(
                "SELECT id, length_cm, city, status, views_count, offers_count, highest_offer_amount "
                "FROM hair_listings WHERE seller_user_id=? AND COALESCE(deleted_at,'')='' "
                "ORDER BY id DESC LIMIT 8", (uid,)
            ).fetchall()
            if not listings:
                return ("🏪 هنوز آگهی فروشی در بازارچه ثبت نکردی.",
                        _kb([[_btn("🌐 ثبت آگهی در بازارچه", url=f"{site}/marketplace/new")],
                             [_btn("🏪 مشاهده بازارچه", url=f"{site}/marketplace")],
                             [_btn("🔙 منوی عملیات", "ua|consult|report")]]))
            lines = ["🏪 آگهی‌های تو:", "━━━━━━━━━━━━━━━━"]
            for l in listings:
                st = _LISTING_STATUS_FA.get(l["status"], l["status"])
                title = f"موی {_fa_num(l['length_cm'] or '—')} سانتی"
                lines.append(f"#{_fa_num(l['id'])} {title} — {st}")
                lines.append(f"   👁 {_fa_num(l['views_count'] or 0)} بازدید | 📨 {_fa_num(l['offers_count'] or 0)} پیشنهاد"
                             + (f" | بالاترین {format_toman(l['highest_offer_amount'] or 0)}" if l["highest_offer_amount"] else ""))
            lines.append("━━━━━━━━━━━━━━━━")
            rows = [[_btn("📬 پیشنهادهای رسیده", "ua|mkt|offers"),
                     _btn("📊 آمار آگهی", "ua|mkt|statslist")],
                    [_btn("🌐 مدیریت آگهی‌ها در سایت", url=f"{site}/dashboard/marketplace")],
                    [_btn("🔙 منوی عملیات", "ua|consult|report")]]
            return "\n".join(lines), _kb(rows)
    except Exception as e:
        logger.warning(f"mkt_my: {e}")
        return "⚠️ دریافت آگهی‌ها ممکن نشد.", _kb([])


def mkt_offers(phone):
    """پیشنهادهای رسیده برای آگهی‌های این فروشنده. قبول/رد در سایت (اثر معامله/مالی)."""
    try:
        with get_giso_db_conn() as conn:
            uid, np = _site_user_id(conn, phone)
            site = _site_url()
            if not uid:
                return ("حساب سایت یافت نشد.", _kb([[_btn("🔙 منو", "ua|consult|report")]]))
            offers = conn.execute(
                "SELECT o.id, o.offer_amount, o.status, o.listing_id, l.length_cm, "
                "bp.request_name AS buyer_name "
                "FROM buyer_offers o JOIN hair_listings l ON l.id=o.listing_id "
                "LEFT JOIN buyer_profiles bp ON bp.id=o.buyer_profile_id "
                "WHERE l.seller_user_id=? ORDER BY o.id DESC LIMIT 8", (uid,)
            ).fetchall()
            pendings = [o for o in offers if o["status"] == "pending"]
            if not offers:
                return ("📬 هنوز پیشنهادی برای آگهی‌هایت ثبت نشده است.",
                        _kb([[_btn("🔙 آگهی‌های من", "ua|mkt|my")]]))
            lines = [f"📬 {_fa_num(len(pendings))} پیشنهاد در انتظار پاسخ:", "━━━━━━━━━━━━━━━━"]
            offer_rows = []
            for o in offers:
                st = _OFFER_STATUS_FA.get(o["status"], o["status"])
                name = _short(o["buyer_name"] or "خریدار", 20)
                lines.append(f"#{_fa_num(o['id'])} • آگهی #{_fa_num(o['listing_id'])} • {name}")
                lines.append(f"   {format_toman(o['offer_amount'] or 0)} — {st}")
                # دکمه‌ی «مشاهده گفتگو» فقط برای پیشنهادهای زنده (نه ردشده/معامله‌شده).
                if o["status"] not in ("rejected", "sold", "cancelled"):
                    offer_rows.append([_btn(f"💬 گفتگوی پیشنهاد #{_fa_num(o['id'])}", f"ua|mkt|chat|{o['id']}")])
            lines.append("━━━━━━━━━━━━━━━━")
            lines.append("قبول/رد/مذاکره در پنل سایت (به‌دلیل اثر روی معامله) انجام می‌شود.")
            rows = offer_rows + [
                [_btn("✅ پاسخ به پیشنهادها در سایت", url=f"{site}/dashboard/marketplace?tab=offers")],
                [_btn("💬 گفتگوها در سایت", url=f"{site}/dashboard/marketplace?tab=conversations")],
                [_btn("🔙 آگهی‌های من", "ua|mkt|my")],
            ]
            return "\n".join(lines), _kb(rows)
    except Exception as e:
        logger.warning(f"mkt_offers: {e}")
        return "⚠️ دریافت پیشنهادها ممکن نشد.", _kb([])


def mkt_chat(phone, offer_id):
    """نمایش ۵ پیام آخر یک گفتگوی بازارچه (فقط خواندنی)؛ ادامه در سایت."""
    try:
        with get_giso_db_conn() as conn:
            uid, np = _site_user_id(conn, phone)
            site = _site_url()
            offer = conn.execute(
                "SELECT o.id, o.listing_id, l.seller_user_id, o.buyer_user_id "
                "FROM buyer_offers o JOIN hair_listings l ON l.id=o.listing_id WHERE o.id=?",
                (int(offer_id),),
            ).fetchone()
            if not offer or uid not in (offer["seller_user_id"], offer["buyer_user_id"]):
                return ("گفتگویی پیدا نشد یا به شما تعلق ندارد.", _kb([[_btn("🔙 پیشنهادها", "ua|mkt|offers")]]))
            msgs = conn.execute(
                "SELECT sender_role, message_text, created_at FROM marketplace_messages "
                "WHERE offer_id=? ORDER BY id DESC LIMIT 5", (int(offer_id),)
            ).fetchall()
            lines = [f"💬 گفتگوی پیشنهاد #{_fa_num(offer['id'])} (آگهی #{_fa_num(offer['listing_id'])}):",
                     "━━━━━━━━━━━━━━━━"]
            if not msgs:
                lines.append("هنوز پیامی رد و بدل نشده.")
            else:
                for m in reversed(msgs):
                    who = "خریدار" if m["sender_role"] in ("buyer", "user") else "فروشنده"
                    lines.append(f"{who}: {_short(m['message_text'], 60)}")
            lines.append("━━━━━━━━━━━━━━━━")
            rows = [[_btn("💬 ادامه گفتگو در سایت", url=f"{site}/dashboard/marketplace?tab=conversations")],
                    [_btn("🔙 پیشنهادها", "ua|mkt|offers")]]
            return "\n".join(lines), _kb(rows)
    except Exception as e:
        logger.warning(f"mkt_chat: {e}")
        return "⚠️ دریافت گفتگو ممکن نشد.", _kb([])


def mkt_stats(phone, listing_id):
    try:
        with get_giso_db_conn() as conn:
            uid, np = _site_user_id(conn, phone)
            l = conn.execute(
                "SELECT id, length_cm, status, views_count, offers_count FROM hair_listings "
                "WHERE id=? AND seller_user_id=?", (int(listing_id), uid if uid else -1)
            ).fetchone()
            if not l:
                return ("آگهی پیدا نشد.", _kb([[_btn("🔙 آگهی‌های من", "ua|mkt|my")]]))
            msg_count = conn.execute(
                "SELECT COUNT(*) FROM marketplace_messages mm JOIN buyer_offers bo ON bo.id=mm.offer_id "
                "WHERE bo.listing_id=?", (int(listing_id),)
            ).fetchone()[0]
            lines = [f"📊 آمار آگهی #{_fa_num(l['id'])} (موی {_fa_num(l['length_cm'] or '—')} سانتی):",
                     "━━━━━━━━━━━━━━━━",
                     f"👁 بازدید: {_fa_num(l['views_count'] or 0)}",
                     f"📨 پیشنهاد: {_fa_num(l['offers_count'] or 0)}",
                     f"💬 پیام: {_fa_num(msg_count)}",
                     f"📌 وضعیت: {_LISTING_STATUS_FA.get(l['status'], l['status'])}"]
            rows = [[_btn("🔙 آگهی‌های من", "ua|mkt|my")]]
            return "\n".join(lines), _kb(rows)
    except Exception as e:
        logger.warning(f"mkt_stats: {e}")
        return "⚠️ دریافت آمار ممکن نشد.", _kb([])


def mkt_stats_list(phone):
    """لیست آگهی‌ها برای انتخاب آمار."""
    try:
        with get_giso_db_conn() as conn:
            uid, np = _site_user_id(conn, phone)
            rows = conn.execute(
                "SELECT id, length_cm FROM hair_listings WHERE seller_user_id=? "
                "AND COALESCE(deleted_at,'')='' ORDER BY id DESC LIMIT 8", (uid if uid else -1,)
            ).fetchall()
            if not rows:
                return ("آگهی‌ای نداری.", _kb([[_btn("🔙 آگهی‌های من", "ua|mkt|my")]]))
            kb = [[_btn(f"📊 آمار آگهی #{_fa_num(r['id'])}", f"ua|mkt|stats|{r['id']}")] for r in rows]
            kb.append([_btn("🔙 آگهی‌های من", "ua|mkt|my")])
            return "کدام آگهی؟", _kb(kb)
    except Exception as e:
        logger.warning(f"mkt_stats_list: {e}")
        return "⚠️ خطا.", _kb([])


# ───────────────────────── D: فروشگاه ─────────────────────────
def shop_orders(phone):
    try:
        with get_giso_db_conn() as conn:
            _, np = _site_user_id(conn, phone)
            rows = conn.execute(
                "SELECT po.id, po.checkout_id, po.tracking_code, po.quantity, po.status, po.created_at, "
                "COALESCE(p.name,'محصول #'||po.product_id) AS pname, COALESCE(p.price,0) AS price "
                "FROM product_orders po LEFT JOIN products p ON p.id=po.product_id "
                "WHERE po.phone=? ORDER BY po.id DESC LIMIT 40", (np,)
            ).fetchall()
            site = _site_url()
            if not rows:
                return ("🛍 هنوز سفارشی از فروشگاه نداری.",
                        _kb([[_btn("🌐 ورود به فروشگاه", url=f"{site}/shop")],
                             [_btn("🔙 منوی عملیات", "ua|consult|report")]]))
            # گروه‌بندی بر اساس checkout
            groups, by_key = [], {}
            for r in rows:
                key = r["checkout_id"] or r["id"]
                g = by_key.get(key)
                if g is None:
                    g = {"checkout": r["checkout_id"], "oid": r["id"], "track": r["tracking_code"] or f"#{r['id']}",
                         "status": r["status"], "date": r["created_at"], "items": [], "total": 0}
                    by_key[key] = g
                    groups.append(g)
                g["items"].append(r["pname"])
                g["total"] += int(r["price"] or 0) * int(r["quantity"] or 1)
            lines = ["🛍 سفارش‌های تو:", "━━━━━━━━━━━━━━━━"]
            action_rows = []
            # وضعیت‌های پایانی/بسته: دکمه‌ی «پیگیری» (که برای سفارش باز معنا دارد) حذف می‌شود.
            _CLOSED = {"delivered", "completed", "cancelled", "rejected"}
            for g in groups[:6]:
                st = _ORDER_STATUS_FA.get(g["status"], g["status"])
                lbl = f"سفارش #{_fa_num(g['checkout'])}" if g["checkout"] else f"سفارش قدیمی ({g['track']})"
                lines.append(f"• {lbl} — {st}")
                lines.append(f"   {_fa_num(len(g['items']))} قلم | {format_toman(g['total'])} | {to_shamsi(g['date'], with_time=False)}")
                if g["track"]:
                    lines.append(f"   🔑 کد پیگیری: {g['track']}")
                # ── دکمه‌های عملیاتی هر سفارش (وضعیت‌محور) ──
                status = (g["status"] or "").lower()
                # شناسه‌ی دکمه‌ها: برای سفارش دارای checkout از همان، در غیر این صورت از id ردیف.
                gid = g["checkout"] or g["oid"]
                btn_row = []
                if status not in _CLOSED:
                    # سفارش فعال/در جریان: پیگیری معنا دارد.
                    btn_row.append(_btn(f"📦 پیگیری {lbl}", f"ua|shop|track|{gid}"))
                if status not in ("cancelled", "rejected"):
                    # سفارش معتبر (چه بسته چه فعال): فاکتور و سفارش مجدد در دسترس‌اند.
                    btn_row.append(_btn(f"🧾 فاکتور {lbl}", f"ua|shop|invoice|{gid}"))
                    btn_row.append(_btn(f"🔄 سفارش مجدد {lbl}", f"ua|shop|reorder|{gid}"))
                if btn_row:
                    action_rows.append(btn_row)
            lines.append("━━━━━━━━━━━━━━━━")
            rows_kb = action_rows + [
                [_btn("📦 پیگیری کامل در سایت", url=f"{site}/dashboard/orders")],
                [_btn("🌐 فروشگاه", url=f"{site}/shop")],
                [_btn("🔙 منوی عملیات", "ua|consult|report")],
            ]
            return "\n".join(lines), _kb(rows_kb)
    except Exception as e:
        logger.warning(f"shop_orders: {e}")
        return "⚠️ دریافت سفارش‌ها ممکن نشد.", _kb([])


def shop_track(phone, order_id):
    try:
        with get_giso_db_conn() as conn:
            _, np = _site_user_id(conn, phone)
            # دکمه‌ها بر اساس گروهِ checkout ساخته می‌شوند؛ پس هم id ردیف و هم checkout_id را بپذیر.
            r = conn.execute(
                "SELECT id, checkout_id, tracking_code, status FROM product_orders "
                "WHERE (id=? OR checkout_id=?) AND phone=? ORDER BY id DESC LIMIT 1",
                (int(order_id), int(order_id), np),
            ).fetchone()
            if not r:
                return ("سفارشی پیدا نشد.", _kb([[_btn("🔙 سفارش‌ها", "ua|shop|orders")]]))
            code = r["tracking_code"] or "—"
            st = _ORDER_STATUS_FA.get(r["status"], r["status"])
            lines = [f"📦 کد پیگیری سفارش #{_fa_num(r['checkout_id'] or r['id'])}:",
                     "━━━━━━━━━━━━━━━━",
                     f"🔑 {code}",
                     f"📌 وضعیت: {st}"]
            return "\n".join(lines), _kb([[_btn("🔙 سفارش‌ها", "ua|shop|orders")]])
    except Exception as e:
        logger.warning(f"shop_track: {e}")
        return "⚠️ خطا.", _kb([])


def shop_reorder(phone, checkout_id):
    """سفارش مجدد: اقلام فاکتور را نشان می‌دهد و برای تکمیل به سایت می‌فرستد (سبد خرید عملیات سایت است)."""
    try:
        with get_giso_db_conn() as conn:
            _, np = _site_user_id(conn, phone)
            inv = conn.execute(
                "SELECT i.id FROM shop_invoices i WHERE i.checkout_id=? AND i.customer_phone=?",
                (int(checkout_id), np),
            ).fetchone()
            site = _site_url()
            if not inv:
                return ("فاکتور این سفارش پیدا نشد.", _kb([[_btn("🔙 سفارش‌ها", "ua|shop|orders")]]))
            items = conn.execute(
                "SELECT product_name, quantity, line_total FROM shop_invoice_items WHERE invoice_id=? ORDER BY id",
                (inv["id"],),
            ).fetchall()
            total = sum(int(x["line_total"] or 0) for x in items)
            lines = [f"🔄 سفارش مجدد #{_fa_num(checkout_id)}:", "━━━━━━━━━━━━━━━━"]
            for it in items:
                lines.append(f"• {_short(it['product_name'], 40)} × {_fa_num(it['quantity'])} — {format_toman(it['line_total'] or 0)}")
            lines.append("━━━━━━━━━━━━━━━━")
            lines.append(f"🧾 جمع: {format_toman(total)}")
            lines.append("افزودن به سبد و تکمیل خرید در سایت انجام می‌شود.")
            rows = [[_btn("🛒 تکمیل سفارش مجدد در سایت", url=f"{site}/shop")],
                    [_btn("🔙 سفارش‌ها", "ua|shop|orders")]]
            return "\n".join(lines), _kb(rows)
    except Exception as e:
        logger.warning(f"shop_reorder: {e}")
        return "⚠️ خطا.", _kb([])


def shop_invoice(phone, checkout_id):
    try:
        with get_giso_db_conn() as conn:
            _, np = _site_user_id(conn, phone)
            inv = conn.execute(
                "SELECT id, invoice_number, gross_amount, discount_amount, payable_amount, payment_status, created_at "
                "FROM shop_invoices WHERE checkout_id=? AND customer_phone=?",
                (int(checkout_id), np),
            ).fetchone()
            if not inv:
                return ("فاکتوری پیدا نشد.", _kb([[_btn("🔙 سفارش‌ها", "ua|shop|orders")]]))
            items = conn.execute(
                "SELECT product_name, quantity, unit_price, line_total FROM shop_invoice_items WHERE invoice_id=? ORDER BY id",
                (inv["id"],),
            ).fetchall()
            lines = [f"🧾 فاکتور {_safe(inv['invoice_number'])} — {to_shamsi(inv['created_at'], with_time=False)}",
                     "━━━━━━━━━━━━━━━━"]
            for it in items:
                lines.append(f"• {_short(it['product_name'], 38)} × {_fa_num(it['quantity'])} = {format_toman(it['line_total'] or 0)}")
            lines.append("━━━━━━━━━━━━━━━━")
            lines.append(f"جمع کل: {format_toman(inv['gross_amount'] or 0)}")
            if inv["discount_amount"]:
                lines.append(f"تخفیف: {format_toman(inv['discount_amount'] or 0)}")
            lines.append(f"💳 مبلغ قابل‌پرداخت: {format_toman(inv['payable_amount'] or 0)}")
            return "\n".join(lines), _kb([[_btn("🔙 سفارش‌ها", "ua|shop|orders")]])
    except Exception as e:
        logger.warning(f"shop_invoice: {e}")
        return "⚠️ خطا.", _kb([])


# ───────────────────────── E: مرکز زیبایی ─────────────────────────
def _owner_center(conn, uid):
    if not uid:
        return None
    return conn.execute(
        "SELECT id, name, slug, status, views_count, listing_expires_at, city, region "
        "FROM beauty_centers WHERE owner_user_id=? ORDER BY id DESC LIMIT 1", (uid,)
    ).fetchone()


def center_stats(phone):
    try:
        with get_giso_db_conn() as conn:
            uid, np = _site_user_id(conn, phone)
            site = _site_url()
            c = _owner_center(conn, uid)
            if not c:
                return ("🏥 هنوز مرکزی ثبت نکردی.",
                        _kb([[_btn("🌐 ثبت مرکز زیبایی", url=f"{site}/beauty-centers/register")],
                             [_btn("🔙 منوی عملیات", "ua|consult|report")]]))
            convos = conn.execute(
                "SELECT COUNT(*) FROM beauty_center_conversations WHERE center_id=? AND status='active'",
                (c["id"],),
            ).fetchone()[0]
            unread = conn.execute(
                "SELECT COUNT(*) FROM beauty_center_messages m JOIN beauty_center_conversations cv "
                "ON cv.id=m.conversation_id WHERE cv.center_id=? AND m.is_read=0 "
                "AND m.sender_user_id != ?", (c["id"], uid)
            ).fetchone()[0]
            remaining = "—"
            try:
                row = conn.execute(
                    "SELECT CAST(ROUND(julianday(listing_expires_at)-julianday(datetime('now','localtime'))) AS INT) "
                    "FROM beauty_centers WHERE id=?", (c["id"],)
                ).fetchone()
                if row and row[0] is not None and (c["listing_expires_at"] or ""):
                    remaining = f"{_fa_num(max(0, int(row[0])))} روز"
            except Exception:
                pass
            lines = [f"🏥 مرکز «{_short(c['name'], 30)}»",
                     "━━━━━━━━━━━━━━━━",
                     f"📌 وضعیت: {_CENTER_STATUS_FA.get(c['status'], c['status'])}",
                     f"👁 بازدید: {_fa_num(c['views_count'] or 0)}",
                     f"💬 گفتگوی فعال: {_fa_num(convos)} | 📩 پیام خوانده‌نشده: {_fa_num(unread)}",
                     f"⏳ اعتبار آگهی: {remaining}"]
            rows = [[_btn("📬 پیام‌های دریافتی", "ua|center|msgs"),
                     _btn("🔄 تمدید آگهی", "ua|center|renew")],
                    [_btn("🌐 پنل مرکز در سایت", url=f"{site}/dashboard/beauty-center")],
                    [_btn("🔙 منوی عملیات", "ua|consult|report")]]
            return "\n".join(lines), _kb(rows)
    except Exception as e:
        logger.warning(f"center_stats: {e}")
        return "⚠️ دریافت آمار مرکز ممکن نشد.", _kb([])


def center_msgs(phone):
    try:
        with get_giso_db_conn() as conn:
            uid, np = _site_user_id(conn, phone)
            site = _site_url()
            c = _owner_center(conn, uid)
            if not c:
                return ("مرکزی یافت نشد.", _kb([[_btn("🔙 منو", "ua|consult|report")]]))
            rows = conn.execute(
                "SELECT cv.id AS cvid, COUNT(m.id) AS unread, MAX(m.created_at) AS last_at "
                "FROM beauty_center_conversations cv LEFT JOIN beauty_center_messages m "
                "ON m.conversation_id=cv.id AND m.is_read=0 AND m.sender_user_id != ? "
                "WHERE cv.center_id=? AND cv.status='active' GROUP BY cv.id ORDER BY cv.last_message_at DESC LIMIT 8",
                (uid, c["id"]),
            ).fetchall()
            total_unread = sum(int(r["unread"] or 0) for r in rows)
            lines = [f"📬 پیام‌های دریافتی مرکز — {_fa_num(total_unread)} خوانده‌نشده:",
                     "━━━━━━━━━━━━━━━━"]
            if not rows:
                lines.append("گفتگوی فعالی نیست.")
            else:
                for r in rows:
                    mark = "🔴" if r["unread"] else "⚪️"
                    lines.append(f"{mark} گفتگو #{_fa_num(r['cvid'])} — {_fa_num(r['unread'] or 0)} پیام جدید")
            lines.append("━━━━━━━━━━━━━━━━")
            lines.append("خواندن و پاسخ در پنل سایت انجام می‌شود.")
            rows_kb = [[_btn("💬 ورود به پیام‌ها در سایت", url=f"{site}/dashboard/beauty-center?tab=messages")],
                       [_btn("🔙 آمار مرکز", "ua|center|stats")]]
            return "\n".join(lines), _kb(rows_kb)
    except Exception as e:
        logger.warning(f"center_msgs: {e}")
        return "⚠️ دریافت پیام‌ها ممکن نشد.", _kb([])


def center_renew(phone):
    """E4: تمدید آگهی عملیات مالی است؛ در ربات فقط راهنما + لینک امن سایت (هیچ کسر/تغییری اینجا رخ نمی‌دهد)."""
    try:
        site = _site_url()
        lines = ["🔄 تمدید آگهی مرکز زیبایی",
                 "━━━━━━━━━━━━━━━━",
                 "تمدید آگهی و پرداخت/کسر هزینه از کیف پول در پنل امن سایت انجام می‌شود "
                 "تا دفتر مالی دقیق و یکدست بماند.",
                 "از دکمه‌ی زیر وارد شو:"]
        rows = [[_btn("🌐 تمدید در پنل مرکز", url=f"{site}/dashboard/beauty-center?tab=credits")],
                [_btn("🔙 آمار مرکز", "ua|center|stats")]]
        return "\n".join(lines), _kb(rows)
    except Exception as e:
        logger.warning(f"center_renew: {e}")
        return "⚠️ خطا.", _kb([])


# ───────────────────────── F: کیف پول ─────────────────────────
def wallet_history(phone):
    try:
        with get_giso_db_conn() as conn:
            uid, np = _site_user_id(conn, phone)
            site = _site_url()
            if not uid:
                return ("برای کیف پول ابتدا در سایت حساب بساز.",
                        _kb([[_btn("🌐 ثبت‌نام", url=f"{site}/register")]]))
            rows = conn.execute(
                "SELECT amount, balance_scope, description, kind, created_at "
                "FROM wallet_transactions WHERE user_id=? ORDER BY id DESC LIMIT 8", (uid,)
            ).fetchall()
            if not rows:
                return ("💰 هنوز تراکنشی نداری.",
                        _kb([[_btn("🌐 کیف پول من", url=f"{site}/dashboard/wallet")],
                             [_btn("🔙 منوی عملیات", "ua|consult|report")]]))
            lines = ["💰 آخرین تراکنش‌های تو:", "━━━━━━━━━━━━━━━━"]
            for r in rows:
                amount = int(r["amount"] or 0)
                sign = "➕" if amount >= 0 else "➖"
                scope = "🎁 اعتبار" if (r["balance_scope"] or "cash") == "spend" else "💵 نقدی"
                desc = _short(r["description"] or r["kind"] or "تراکنش", 34)
                lines.append(f"{sign} {scope} • {format_toman(abs(amount))}")
                lines.append(f"   {desc} — {to_shamsi(r['created_at'], with_time=False)}")
            lines.append("━━━━━━━━━━━━━━━━")
            rows_kb = [[_btn("🌐 مدیریت کیف پول در سایت", url=f"{site}/dashboard/wallet?tab=summary")],
                       [_btn("🎯 مأموریت‌ها", url=f"{site}/dashboard/wallet?tab=missions")],
                       [_btn("🔙 منوی عملیات", "ua|consult|report")]]
            return "\n".join(lines), _kb(rows_kb)
    except Exception as e:
        logger.warning(f"wallet_history: {e}")
        return "⚠️ دریافت تراکنش‌ها ممکن نشد.", _kb([])


# ───────────────────────── راهنما ─────────────────────────
def help_menu(phone):
    """راهنمای پنل ۶‌دکمه‌ای کاربر: هر دکمه ۱-۲ خط توضیح + رتبه‌ها + دستورات."""
    try:
        lines = [
            "📖 راهنمای گیسو",
            "━━━━━━━━━━━━━━━━",
            "🤖 مشاور — وضعیت آنالیز/سفارش خودت را می‌خواند و فقط درباره خدمات گیسو جواب می‌دهد",
            "💰 کیف پول — دو نوع اعتبار داری:",
            "  • 💵 نقدی (Cash): از تسویه/پاداش نقدی مأموریت؛ قابل تسویه به کارت",
            "  • 🎁 مصرفی (Spend): هدیه/پاداش مأموریت؛ فقط خرید خدمات و محصول در گیسو",
            "  موقع پرداخت اول مصرفی بعد نقدی خرج می‌شود.",
            "🎯 مأموریت — کار انجام بده، امتیاز و اعتبار (مصرفی یا نقدی) بگیر",
            "👤 پروفایل — اطلاعات تو، رتبه؛ نام/نام‌خانوادگی/شهر فقط یک‌بار قابل ویرایش",
            "💬 پشتیبانی — پیام بده، مستقیم به ادمین می‌رسد و جواب push می‌شود",
            "━━━━━━━━━━━━━━━━",
            "🏆 رتبه و امتیاز چطور حساب می‌شود؟",
            "امتیاز از پاداش امتیازیِ مأموریت‌های تکمیل‌شده جمع می‌شود؛",
            "هرچه امتیاز بیشتر، رتبه بالاتر و اعتبار مصرفی روزانه بیشتر:",
            "🥉 برنزی: تا ۹۹ امتیاز",
            "🥈 نقره‌ای: ۱۰۰ تا ۴۹۹",
            "🥇 طلایی: ۵۰۰ تا ۱۹۹۹",
            "👑 الماسی: ۲۰۰۰ به بالا",
            "رتبه در «🏆 رتبه‌بندی هفته» و پروفایل دیده می‌شود.",
            "━━━━━━━━━━━━━━━━",
            "📌 /wallet — کیف پول • /support — پشتیبانی • /help — راهنما",
        ]
        rows = [
            [_btn("🤖 مشاور", "ua|consult|report"), _btn("💰 کیف پول", "ua|wallet|main")],
            [_btn("🎯 مأموریت", "ua|mission|main"), _btn("👤 پروفایل", "ua|profile|main")],
            [_btn("🏆 رتبه‌بندی هفته", "ua|rank|week")],
        ]
        return "\n".join(lines), _kb(rows)
    except Exception as e:
        logger.warning(f"help_menu: {e}")
        return "📖 راهنما در حال حاضر در دسترس نیست.", _kb([])


def welcome_text(first_name=""):
    """پیام خوش‌آمد کوتاه بار اول."""
    name = (first_name or "دوست عزیز").strip() or "دوست عزیز"
    return (
        f"سلام {name} عزیز! 🌸\n"
        "به گیسو خوش اومدی — دستیار هوشمند زیبایی و سلامت.\n"
        "از منوی پایین استفاده کن، یا هر سوالی داری بپرس.\n"
        "برای آشنایی با بخش‌ها، راهنمای پایین را بخوان 👇"
    )


# ───────────────────────── منوی اصلی عملیات ─────────────────────────
def home_menu(phone):
    """پس از حذف هابِ مخفی «منوها» — همهٔ امور از طریق مشاور یا دکمه‌های اصلی.

    دیگر محتویات هاب (آنالیز/فروش مو/بازارچه/سفارش/مرکز/کیف پول-هاب/داشبورد) نمایش داده
    نمی‌شود؛ فقط یک مسیرِ امنِ بازگشت به مشاور است.
    """
    try:
        site = _site_url()
        lines = [
            "برای همهٔ امورت همین‌جا از مشاور بپرس یا از دکمه‌های اصلیِ پایین استفاده کن 👇",
            "مشاور به تمام اطلاعات تو (کیف پول، فروش مو، بازارچه، مرکز، سفارش‌ها و…) دسترسی دارد.",
        ]
        rows = [
            [_btn("💬 مشاور", "ua|consult|report")],
            [_btn("🌐 پنل کاربری", url=f"{site}/dashboard")],
        ]
        return "\n".join(lines), _kb(rows)
    except Exception as e:
        logger.warning(f"home_menu: {e}")
        return "⚡️ منوی عملیات در دسترس نیست.", _kb([])

def consultant_report(phone):
    """🤖 گزارش کوتاه وضعیت کاربر از دیتابیس واقعی (sync، ≤۱۰ خط) + دکمه ورود به چت.

    چت واقعی AI با دکمه‌ی «💬 سوال بپرس» (consultant_ai_start) در bot.py اجرا می‌شود؛
    این تابع فقط گزارش اولیه را می‌سازد تا عدد جعلی ساخته نشود.
    """
    try:
        with get_giso_db_conn() as conn:
            uid, np = _site_user_id(conn, phone)
            site = _site_url()
            if not np:
                return ("🤖 برای گزارش شخصی، ابتدا شماره‌ات را از منوی اصلی به اشتراک بگذار.",
                        _kb([]))
            # آنالیز
            a = conn.execute(
                "SELECT ai_report_json, type, created_at FROM analyses WHERE user_id=? OR phone=? ORDER BY id DESC LIMIT 1",
                (uid if uid is not None else -1, np),
            ).fetchone()
            n_anal = conn.execute(
                "SELECT COUNT(*) FROM analyses WHERE user_id=? OR phone=?",
                (uid if uid is not None else -1, np),
            ).fetchone()[0]
            # فروش مو
            n_hair = conn.execute("SELECT COUNT(*) FROM hair_orders WHERE phone=?", (np,)).fetchone()[0]
            hlast = conn.execute("SELECT status FROM hair_orders WHERE phone=? ORDER BY id DESC LIMIT 1", (np,)).fetchone()
            # سفارش فروشگاه
            n_shop = conn.execute("SELECT COUNT(*) FROM product_orders WHERE phone=?", (np,)).fetchone()[0]
            # آگهی
            n_list = 0
            if uid is not None:
                n_list = conn.execute(
                    "SELECT COUNT(*) FROM hair_listings WHERE seller_user_id=? AND COALESCE(deleted_at,'')=''", (uid,)
                ).fetchone()[0]
        from giso.wallet import get_wallet_balances, get_user_rank
        bal = get_wallet_balances(uid) if uid else {"cash": 0, "spend": 0}
        rank = get_user_rank(phone)
        lines = ["🤓 مشاور هوشمند گیسو", "━━━━━━━━━━━━━━━━",
                 f"🔬 آنالیز: {_fa_num(n_anal)}",
                 f"💇 درخواست فروش مو: {_fa_num(n_hair)}",
                 f"🛍 سفارش فروشگاه: {_fa_num(n_shop)}",
                 f"🏪 آگهی بازارچه: {_fa_num(n_list)}",
                 f"💰 {format_toman(int(bal.get('cash', 0)) + int(bal.get('spend', 0)))} • {rank['emoji']} {rank['name']}"]
        # پیشنهاد قدم بعدی بر اساس داده
        if hlast and hlast["status"] in ("priced", "approved"):
            lines.append("💡 درخواستت قیمت خورده؛ برای دیدن قیمت دکمه‌ی 💰 کیف پول→مأموریت یا از سایت اقدام کن.")
        elif n_anal == 0:
            lines.append("💡 می‌تونی با یک آنالیز رایگان شروع کنی.")
        else:
            lines.append("💡 هر سوالی داری، دکمه‌ی «سوال بپرس» را بزن.")
        # «سوال بپرس» همان فلوی موجود چت AI را راه می‌اندازد (consultant_ai_start در bot.py)
        rows = [[_btn("💬 سوال بپرس", "consultant_ai_start")],
                [_btn("🔬 آنالیز جدید", url=f"{site}/analysis")],
                [_btn("🔙 منو", "ua|consult|report")]]
        return "\n".join(lines), _kb(rows)
    except Exception as e:
        logger.warning(f"consultant_report: {e}")
        return "⚠️ گزارش مشاور در حال حاضر در دسترس نیست.", _kb([])


def wallet_main(phone):
    """💰 کیف پول: مانده نقدی/مصرفی + رتبه + لینک شارژ/تسویه (حداکثر ۱۰ خط)."""
    try:
        from giso.wallet import get_wallet_balances, get_user_rank
        with get_giso_db_conn() as conn:
            uid, np = _site_user_id(conn, phone)
            site = _site_url()
            if not uid:
                return ("💰 برای کیف پول ابتدا در سایت حساب بساز.",
                        _kb([[_btn("🌐 ثبت‌نام", url=f"{site}/register")]]))
            bal = get_wallet_balances(uid)
            rank = get_user_rank(phone)
        lines = ["💰 کیف پول", "━━━━━━━━━━━━━━━━",
                 f"💵 نقدی (قابل تسویه): {format_toman(bal['cash'])}",
                 f"🎁 مصرفی (خدمات): {format_toman(bal['spend'])}",
                 "━━━━━━━━━━━━━━━━",
                 f"{rank['emoji']} رتبه: {rank['name']} • {_fa_num(rank['score'])} امتیاز"]
        if rank.get("next_rank_score"):
            lines.append(f"تا رتبه بعد: {_fa_num(rank['next_rank_score'] - rank['score'])} امتیاز")
        rows = [[_btn("💵 شارژ", url=f"{site}/dashboard/wallet?tab=topup"),
                 _btn("📤 تسویه", url=f"{site}/dashboard/wallet?tab=settlement")],
                [_btn("📊 تاریخچه تراکنش", "ua|wallet|history")],
                [_btn("🔙 منو", "ua|consult|report")]]
        return "\n".join(lines), _kb(rows)
    except Exception as e:
        logger.warning(f"wallet_main: {e}")
        return "⚠️ دریافت کیف پول ممکن نشد.", _kb([])


def missions_view(phone):
    """🎯 مأموریت: لیست مأموریت‌های فعال + وضعیت + امتیاز/رتبه (حداکثر ۱۰ خط)."""
    try:
        from giso.wallet import list_missions_for_user, get_user_rank
        with get_giso_db_conn() as conn:
            uid, np = _site_user_id(conn, phone)
            site = _site_url()
            if not uid:
                return ("🎯 برای مأموریت ابتدا در سایت حساب بساز.",
                        _kb([[_btn("🌐 ثبت‌نام", url=f"{site}/register")]]))
            missions = list_missions_for_user(uid)
            rank = get_user_rank(phone)
        active = [m for m in missions if m.get("is_active")]
        done = sum(1 for m in active if m.get("completed"))
        lines = [f"🎯 مأموریت‌ها — {_fa_num(done)}/{_fa_num(len(active))} انجام‌شده",
                 "━━━━━━━━━━━━━━━━"]
        for m in active[:6]:
            mark = "✅" if m.get("completed") else "⬜"
            pt = m.get("reward_points") or 0
            tail = f" • {_fa_num(pt)} امتیاز" if pt else ""
            lines.append(f"{mark} {_short(m.get('title') or 'مأموریت', 34)}{tail}")
        lines.append("━━━━━━━━━━━━━━━━")
        lines.append(f"⭐ {_fa_num(rank['score'])} امتیاز • {rank['emoji']} {rank['name']}")
        if rank.get("next_rank_score"):
            lines.append(f"{_fa_num(rank['next_rank_score'] - rank['score'])} امتیاز تا رتبه بعد")
        rows = [[_btn("🏆 رتبه‌بندی هفته", "ua|rank|week")],
                [_btn("📋 همه مأموریت‌ها", url=f"{site}/dashboard/wallet?tab=missions")],
                [_btn("🔙 منو", "ua|consult|report")]]
        return "\n".join(lines), _kb(rows)
    except Exception as e:
        logger.warning(f"missions_view: {e}")
        return "⚠️ دریافت مأموریت ممکن نشد.", _kb([])


def rank_week(phone):
    """🏆 ۱۰ کاربر برتر هفته (فقط خواندنی، کوتاه)."""
    try:
        from giso.wallet import get_weekly_leaderboard, get_user_rank
        board = get_weekly_leaderboard(10)
        rank = get_user_rank(phone)
        medals = {1: "🥇", 2: "🥈", 3: "🥉"}
        lines = ["🏆 برترین‌های هفته", "━━━━━━━━━━━━━━━━"]
        if not board:
            lines.append("هنوز امتیازی ثبت نشده؛ اولین نفر باش!")
        for r in board:
            ic = medals.get(r["rank"], f"{_fa_num(r['rank'])}.")
            lines.append(f"{ic} {_short(r['name'], 24)} — {_fa_num(r['score'])} امتیاز")
        lines.append("━━━━━━━━━━━━━━━━")
        lines.append(f"رتبه تو: {rank['emoji']} {rank['name']} ({_fa_num(rank['score'])} امتیاز)")
        rows = [[_btn("🔙 مأموریت‌ها", "ua|mission|main")]]
        return "\n".join(lines), _kb(rows)
    except Exception as e:
        logger.warning(f"rank_week: {e}")
        return "⚠️ رتبه‌بندی در حال حاضر در دسترس نیست.", _kb([])


def profile_main(phone):
    """👤 پروفایل کوتاه: نام/شهر/رتبه/امتیاز + خلاصه + دکمه ویرایش (حداکثر ۸ خط)."""
    try:
        from giso.user_profile_service import get_user_profile, get_user_activity_summary
        from giso.wallet import get_user_rank, get_wallet_balances
        with get_giso_db_conn() as conn:
            uid, np = _site_user_id(conn, phone)
            site = _site_url()
        if not uid:
            return ("👤 برای پروفایل ابتدا در سایت حساب بساز.",
                    _kb([[_btn("🌐 ثبت‌نام", url=f"{site}/register")]]))
        profile = get_user_profile(phone) or {}
        activity = get_user_activity_summary(phone) or {}
        rank = get_user_rank(phone)
        bal = get_wallet_balances(uid)
        name = " ".join([str(profile.get("first_name") or ""), str(profile.get("last_name") or "")]).strip() or "—"
        lines = [f"👤 {_short(name, 30)} • {rank['emoji']} {rank['name']}",
                 f"📱 {display_phone(profile.get('phone') or phone)} • 🏙️ {profile.get('city') or '—'}",
                 f"⭐ {_fa_num(rank['score'])} امتیاز",
                 "━━━━━━━━━━━━━━━━",
                 f"🔬 {_fa_num(activity.get('analyses', 0))} آنالیز | 💇 {_fa_num(activity.get('hair_orders', 0))} فروش مو",
                 f"🛍 {_fa_num(activity.get('shop_checkouts', 0))} سفارش | 🏪 {_fa_num(activity.get('market_listings', 0))} آگهی",
                 f"💰 مجموع دارایی: {format_toman(int(bal.get('cash', 0)) + int(bal.get('spend', 0)))}"]
        try:
            from giso.user_profile_service import is_bot_profile_edit_locked
            edit_locked = is_bot_profile_edit_locked(phone)
        except Exception:
            edit_locked = False
        if edit_locked:
            lines.append("━━━━━━━━━━━━━━━━")
            lines.append("🔒 نام/نام‌خانوادگی/شهر یک‌بار قابل ویرایش بود و الان قفل است.")
            rows = [[_btn("🏆 رتبه‌بندی", "ua|rank|week")],
                    [_btn("🌐 پروفایل کامل", url=f"{site}/dashboard/profile")]]
        else:
            rows = [[_btn("✏️ ویرایش نام", "upro|edit|first_name"), _btn("✏️ نام خانوادگی", "upro|edit|last_name")],
                    [_btn("✏️ شهر", "upro|edit|city"), _btn("🏆 رتبه‌بندی", "ua|rank|week")],
                    [_btn("🌐 پروفایل کامل", url=f"{site}/dashboard/profile")]]
        return "\n".join(lines), _kb(rows)
    except Exception as e:
        logger.warning(f"profile_main: {e}")
        return "⚠️ دریافت پروفایل ممکن نشد.", _kb([])


# ───────────────────────── روتر ─────────────────────────
# هر کلید: (تابع, تعداد آرگمان‌های شناسه)
_ROUTES = {
    "help": (help_menu, 0),
    "wallet|main": (wallet_main, 0),
    "mission|main": (missions_view, 0),
    "profile|main": (profile_main, 0),
    "rank|week": (rank_week, 0),
    "consult|report": (consultant_report, 0),
    "anal|last": (anal_last, 0),
    "anal|plan": (anal_plan, 0),
    "anal|check": (anal_check, 0),
    "anal|consult": (anal_consult, 0),
    "anal|products": (anal_products, 0),
    "hair|status": (hair_status, 0),
    "hair|price": (hair_price, 1),
    "hair|chatlist": (hair_chat_list, 0),
    "hair|chat": (hair_chat_list, 0),  # گفتگوی فروش مو از طریق لیست/سایت
    "mkt|my": (mkt_my, 0),
    "mkt|offers": (mkt_offers, 0),
    "mkt|chat": (mkt_chat, 1),
    "mkt|stats": (mkt_stats, 1),
    "mkt|statslist": (mkt_stats_list, 0),
    "shop|orders": (shop_orders, 0),
    "shop|track": (shop_track, 1),
    "shop|reorder": (shop_reorder, 1),
    "shop|invoice": (shop_invoice, 1),
    "center|stats": (center_stats, 0),
    "center|msgs": (center_msgs, 0),
    "center|renew": (center_renew, 0),
    "wallet|history": (wallet_history, 0),
}


def route(phone, data: str):
    """data نمونه: 'ua|anal|last' یا 'ua|mkt|stats|12'. خروجی: (text, kb_rows)."""
    try:
        parts = (data or "").split("|")
        # parts[0] == 'ua'
        key = "|".join(parts[1:3]) if len(parts) >= 3 else (parts[1] if len(parts) > 1 else "home")
        fn, nargs = _ROUTES.get(key, (None, 0))
        if fn is None:
            return home_menu(phone)
        args = []
        if nargs:
            arg = parts[3] if len(parts) > 3 else parts[-1]
            args.append(arg)
        return fn(phone, *args)
    except Exception as e:
        logger.warning(f"ua route error data={data!r}: {e}")
        return "⚠️ این بخش暂时 در دسترس نیست.", _kb([])


def entry_text_kb(phone):
    """برای دکمه‌ی reply «⚡️ عملیات سریع من»: همان home_menu."""
    return home_menu(phone)


# ══════════════════════════════════════════════════════════════════════════
# P5 — Telegram-flavored adapters + user views moved out of bot.py
# (no business logic change; re-exported from giso.bot)
# ══════════════════════════════════════════════════════════════════════════

_SHOP_STATUS_FA = {"pending": "⏳ در انتظار", "completed": "✅ تکمیل‌شده", "cancelled": "⛔ لغو"}


def _user_fallback_kb():
    """کیبورد reply اصلی کاربر (lazy تا سیکل import با giso.bot نشکند)."""
    from giso import bot as _bot
    return _bot._user_kb()


async def send_ua_view(msg, phone: str, data: str):
    """نمایش یک ویوی کاربر از این ماژول (پیشوند ua|) در پاسخ به دکمه‌ی reply.

    مسیر واحد برای دکمه‌های اصلی کاربر تا هیچ دکمه‌ای دو مسیر متفاوت اجرا نکند؛
    همه‌ی لینک‌ها داخل ویو از get_site_url() ساخته می‌شوند.
    """
    from telegram import InlineKeyboardButton as _vb, InlineKeyboardMarkup as _vm
    try:
        _t, _rows = route(phone, data)
        _mk = _vm([
            [_vb(b["t"], callback_data=b.get("d"), url=b.get("u"))
             for b in row if b.get("d") or b.get("u")]
            for row in (_rows or [])
        ])
        await msg.reply_text(_t, reply_markup=_mk)
    except Exception as _e:
        logger.warning(f"ua view error {data}: {_e}")
        await msg.reply_text("⚠️ این بخش در حال حاضر در دسترس نیست.", reply_markup=_user_fallback_kb())


async def send_ua_entry(msg, phone: str):
    """دکمه‌ی reply «⚡️ عملیات سریع من» → entry_text_kb همان ماژول."""
    try:
        _u_text, _u_rows = entry_text_kb(phone)
        from telegram import InlineKeyboardButton as _uib, InlineKeyboardMarkup as _uim
        _u_markup = _uim([
            [_uib(b["t"], callback_data=b.get("d"), url=b.get("u"))
             for b in row if b.get("d") or b.get("u")]
            for row in (_u_rows or [])
        ])
        await msg.reply_text(_u_text, reply_markup=_u_markup)
    except Exception as _u_e:
        logger.warning(f"ua entry error: {_u_e}")
        await msg.reply_text("⚠️ منوی عملیات سریع در حال حاضر در دسترس نیست.", reply_markup=_user_fallback_kb())


async def handle_ua_callback(query, phone: str, data: str) -> bool:
    """شاخه‌ی callback نام‌فضای اختصاصی «ua|» — بعد از همه‌ی هندلرهای موجود.

    فقط برای پیشوند خودش فعال می‌شود تا چیزی نشکند؛ True اگر هندل شد.
    """
    if not str(data or "").startswith("ua|"):
        return False
    try:
        await query.answer()
    except Exception:
        pass
    try:
        _u_text, _u_rows = route(phone, data)
        _markup = None
        try:
            from telegram import InlineKeyboardButton, InlineKeyboardMarkup
            _markup = InlineKeyboardMarkup([
                [InlineKeyboardButton(b["t"], callback_data=b.get("d"), url=b.get("u"))
                 for b in row if b.get("d") or b.get("u")]
                for row in (_u_rows or [])
            ])
        except Exception:
            _markup = None
        try:
            await query.edit_message_text(_u_text, reply_markup=_markup)
        except Exception:
            await query.message.reply_text(_u_text, reply_markup=_markup)
    except Exception as _u_e:
        logger.warning(f"ua callback error: {_u_e}")
        try:
            await query.message.reply_text("⚠️ این بخش در حال حاضر در دسترس نیست.")
        except Exception:
            pass
    return True


async def send_user_help(msg, phone: str, first_name: str = ""):
    """پیام راهنمای کامل کاربر (دکمه 📖) با میانبرها و بازگشت؛ مستقل و امن."""
    try:
        from telegram import InlineKeyboardButton as _hkb, InlineKeyboardMarkup as _hkm
        _h_text, _h_rows = help_menu(phone)
        _h_markup = _hkm([
            [_hkb(b["t"], callback_data=b.get("d"), url=b.get("u"))
             for b in row if b.get("d") or b.get("u")]
            for row in (_h_rows or [])
        ])
        await msg.reply_text(_h_text, reply_markup=_h_markup)
    except Exception as _h_e:
        logger.warning(f"help menu error: {_h_e}")
        await msg.reply_text("📖 راهنما در حال حاضر در دسترس نیست.", reply_markup=_user_fallback_kb())


async def send_first_contact_welcome(msg, phone: str, first_name: str, pending: bool = False):
    """راهنمای بار اول کاربر عادی: خوش‌آمد + معرفی کوتاه دکمه‌های منوی اصلی + راهنما."""
    from giso import bot as _bot
    _fname = first_name or "عزیز"
    try:
        await msg.reply_text(
            f"💇‍♀️ سلام {_fname} عزیز! به گیسو خوش آمدید 🌸\n\n"
            "یکی دو دقیقه با ربات آشنا شوید تا راحت‌تر از خدمات استفاده کنید:\n\n"
            "🔍 آنالیز هوشمند — هر سؤالی درباره مو، پوست، تحلیل، محصول یا "
            "وضعیت سفارش‌ها/درخواست‌هایتان دارید همین‌جا بپرسید؛ اول وضعیت شما را جمع‌بندی می‌کند.\n"
            "💰 کیف پول من — موجودی نقدی (برای خرید و تسویه) و اعتبار مصرفی (برای خرید در سایت)؛ "
            "شارژ، مأموریت‌ها و تسویه در همین بخش و در سایت.\n"
            "👤 پروفایل من — مشخصات شما (نام، شهر) و خلاصه فعالیت‌هایتان.\n"
            "💬 پشتیبانی — ارتباط مستقیم با تیم گیسو برای پیگیری‌ها و گزارش مشکل.\n"
            "🔔 اعلان‌های من — سفارش‌ها، تأییدها و خبرهای مربوط به شما.\n\n"
            "یادتان باشد: ارزیابی/فروش مو، آنالیز هوشمند و خرید محصول از «سایت گیسو» انجام می‌شود "
            "و پیگیری وضعیت را می‌توانید همین‌جا از مشاور بپرسید.\n"
            "برای شروع، یکی از دکمه‌های پایین را لمس کنید 👇",
            reply_markup=_bot._user_kb(pending=pending),
        )
    except Exception as _e_wel:
        logger.debug(f"first-contact welcome: {_e_wel}")
    try:
        await send_user_help(msg, phone, first_name)
    except Exception as _e_fh:
        logger.debug(f"first-contact help: {_e_fh}")


def consultant_status_report(uid, phone: str) -> str:
    """گزارش وضعیت کاربر برای کارت خوش‌آمدِ مشاور هوشمند (best-effort)."""
    try:
        from giso.user_profile_service import build_user_status_report
        from giso.bot_admin_utils import _get_user_phone
        _uphone = _get_user_phone(uid) or phone or ""
        return build_user_status_report(_uphone) or ""
    except Exception as _e_rep:
        logger.debug(f"user status report: {_e_rep}")
        return ""


async def _msg_user_orders(msg, phone):
    """📦 سفارش‌های من: نمایش آخرین ۵ سفارش فروشگاه کاربر با استایل بهتر."""
    rows = _shop_order_rows(phone, limit=50)
    if not rows:
        await msg.reply_text(
            "📦 هنوز سفارشی از فروشگاه ثبت نکردی.\n"
            f"🌐 {_get_giso_site_url()}/shop"
        )
        return
    lines = [
        "📦 سفارش‌های فروشگاه تو",
        "━━━━━━━━━━━━━━━━",
    ]
    for group in _group_shop_order_rows(rows)[:5]:
        st = _SHOP_STATUS_FA.get(group["status"], group["status"])
        st_icon = {
            "pending": "⏳", "approved": "✅", "shipped": "🚚",
            "delivered": "📦", "rejected": "❌", "completed": "✅",
            "cancelled": "⛔",
        }.get(group["status"], "📌")
        item_lines = "\n".join(
            f"  • {item['pname']} × {_fa_num(item['quantity'] or 1)}"
            for item in group["items"]
        )
        label = f"checkout #{_fa_num(group['checkout_id'])}" if group["checkout_id"] else "سفارش قدیمی"
        lines.append(
            f"\n🛍 {label}\n"
            f"{item_lines}\n"
            f"💰 جمع اقلام: {format_toman(group['total'])}\n"
            f"{st_icon} وضعیت: {st}\n"
            f"🔑 کد پیگیری: {group['tracking_code']}\n"
            f"📅 {to_shamsi(group['created_at'],with_time=False)}"
        )
    lines.append("\n━━━━━━━━━━━━━━━━")
    lines.append(f"🌐 پیگیری کامل: {_get_giso_site_url()}/dashboard/shop")
    await msg.reply_text("\n".join(lines))


async def _msg_user_review_picker(msg, phone):
    """⭐ ثبت نظر: انتخاب سفارش فروشگاه برای امتیازدهی."""
    from telegram import InlineKeyboardButton, InlineKeyboardMarkup
    rows = _shop_order_rows(phone, limit=5)
    if not rows:
        await msg.reply_text(
            "⭐ برای ثبت نظر، اول باید از فروشگاه سفارش داشته باشی.\n"
            f"🌐 {_get_giso_site_url()}/shop"
        )
        return
    kb_rows = [[InlineKeyboardButton(
        f"⭐ سفارش #{r['id']} — {r['pname'][:26]}",
        callback_data=f"srev|sel|{r['id']}"
    )] for r in rows]
    await msg.reply_text(
        "⭐ کدام سفارش فروشگاه را ارزیابی می‌کنی؟",
        reply_markup=InlineKeyboardMarkup(kb_rows),
    )


async def _handle_shop_review_state(msg, text, uid, phone, user_states) -> bool:
    """ثبت متن نظر سفارش فروشگاه در reviews (review_type='shop_order')."""
    state = str(user_states.get(uid, ""))
    if not state.startswith("waiting_shop_rev_txt_"):
        return False
    parts = state.split("_")
    order_id, rating = int(parts[4]), int(parts[5])
    user_states.pop(uid, None)
    try:
        with get_giso_db_conn() as conn:
            conn.execute(
                "INSERT INTO reviews (user_id, phone, review_type, order_id, rating, comment, created_at) "
                "VALUES (?, ?, 'shop_order', ?, ?, ?, ?)",
                (uid, phone or "", order_id, rating, text, time.strftime("%Y-%m-%d %H:%M:%S")),
            )
            conn.commit()
        await msg.reply_text(
            "✅ نظر و رضایت شما برای سفارش فروشگاه ثبت شد. از همراهی‌ات سپاسگزاریم 🌸",
            reply_markup=_user_fallback_kb(),
        )
    except Exception as e:
        logger.error(f"shop review save error: {e}")
        await msg.reply_text("❌ خطا در ثبت نظر.", reply_markup=_user_fallback_kb())
    return True
