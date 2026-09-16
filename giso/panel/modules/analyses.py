# -*- coding: utf-8 -*-
"""panel/modules/analyses.py — مدیریت آنالیز + مشاوره + محصول درخواستی + خلاصه گفتگوها (فاز 4.7 + فاز 5).

فاز 5 (همان عملیات ربات روی همان جداول):
  - درخواست‌های مشاوره (consultant_requests + consultant_messages): پاسخ، تغییر وضعیت
  - محصولات درخواستی (product_requests): اضافه‌شدن/رد + یادداشت
  - خلاصه گفتگوهای مشاور (analyses.consultant_chat_history): فیلتر امروز/هفته/ماه/همه + مشاهده کامل
  - نمایش پروفایل خلاصه کاربر در جزئیات آنالیز (فاز 4.7)
"""
import json
import logging
from datetime import datetime, timedelta

from flask import request, redirect, url_for, flash

from giso.models import User
from giso.base import get_giso_db_conn
from giso.panel.permissions import current_role_and_perms

logger = logging.getLogger("giso_panel_analyses")

_FA_DIGITS = str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹")


def _fa_num(val) -> str:
    try:
        return str(int(val)).translate(_FA_DIGITS)
    except (TypeError, ValueError):
        return str(val)


def _require_analysis_perm():
    """ادمین باید permission آنالیز را داشته باشد (مثل ربات)."""
    role, perms, bale_id = current_role_and_perms()
    if role == "super":
        return None
    if perms.get("analysis_management"):
        return None
    flash("شما به مدیریت آنالیز دسترسی ندارید.", "warning")
    return redirect(url_for("panel.dashboard"))


def _user_summary(phone):
    """خلاصه پروفایل کاربر (همه از دیتابیس واقعی) — فاز 4.7."""
    try:
        u = User.query.filter_by(phone=phone).first()
        with get_giso_db_conn() as conn:
            n_an = conn.execute("SELECT COUNT(*) FROM analyses WHERE phone=?", (phone,)).fetchone()[0]
            n_orders = conn.execute("SELECT COUNT(*) FROM product_orders WHERE phone=?", (phone,)).fetchone()[0]
            n_hair = conn.execute("SELECT COUNT(*) FROM hair_orders WHERE phone=?", (phone,)).fetchone()[0]
        return {
            "name": (u.name if u else "") or "—",
            "phone": phone,
            "is_banned": bool(getattr(u, "is_banned", 0)) if u else False,
            "created_at": (u.created_at if u else "") or "—",
            "analyses": int(n_an or 0),
            "orders": int(n_orders or 0),
            "hair": int(n_hair or 0),
        }
    except Exception as e:
        logger.error(f"panel analyses user_summary: {e}")
        return None


# ───────────────────── درخواست‌های مشاوره / محصول ─────────────────────

def get_consultant_requests(limit=20):
    try:
        with get_giso_db_conn() as conn:
            rows = conn.execute(
                "SELECT id, customer_name, phone, initial_message, status, analysis_id, created_at "
                "FROM consultant_requests ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
            out = []
            for r in rows:
                d = dict(r)
                d["messages_count"] = conn.execute(
                    "SELECT COUNT(*) FROM consultant_messages WHERE request_id=?", (d["id"],)).fetchone()[0]
                out.append(d)
            return out
    except Exception as e:
        logger.error(f"panel consultant requests: {e}")
        return []


def get_consultant_messages(req_id):
    try:
        with get_giso_db_conn() as conn:
            return [dict(r) for r in conn.execute(
                "SELECT * FROM consultant_messages WHERE request_id=? ORDER BY id ASC", (req_id,)).fetchall()]
    except Exception:
        return []


def get_product_requests(limit=20):
    try:
        with get_giso_db_conn() as conn:
            return [dict(r) for r in conn.execute(
                "SELECT * FROM product_requests ORDER BY id DESC LIMIT ?", (limit,)).fetchall()]
    except Exception as e:
        logger.error(f"panel product requests: {e}")
        return []


def get_chat_summaries(filter_type="all", limit=15):
    """خلاصه گفتگوهای مشاور (analyses.consultant_chat_history) — مثل ربات."""
    try:
        date_filter = ""
        params = []
        if filter_type == "today":
            date_filter = "AND a.created_at >= ?"
            params.append(datetime.now().strftime("%Y-%m-%d"))
        elif filter_type == "week":
            date_filter = "AND a.created_at >= ?"
            params.append((datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d"))
        elif filter_type == "month":
            date_filter = "AND a.created_at >= ?"
            params.append((datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d"))
        with get_giso_db_conn() as conn:
            query = (
                "SELECT a.id, a.created_at, a.consultant_chat_history, "
                "       a.consultant_key_notes, a.chat_rating, "
                "       COALESCE(u.name, w.name, 'کاربر ناشناس') AS user_name, "
                "       COALESCE(u.phone, w.phone, '') AS phone, a.type "
                "FROM analyses a "
                "LEFT JOIN giso_web_auth u ON a.user_id = u.id "
                "LEFT JOIN giso_web_auth w ON a.phone = w.phone "
                "WHERE (a.consultant_chat_history IS NOT NULL AND a.consultant_chat_history != '' "
                "       AND a.consultant_chat_history != '[]') "
                + date_filter + " ORDER BY a.id DESC LIMIT ?"
            )
            params.append(limit)
            rows = conn.execute(query, params).fetchall()
        out = []
        for r in rows:
            d = dict(r)
            try:
                history = json.loads(d.get("consultant_chat_history") or "[]")
                d["message_count"] = len(history) if isinstance(history, list) else 0
            except Exception:
                d["message_count"] = 0
            out.append(d)
        return out
    except Exception as e:
        logger.error(f"panel chat summaries: {e}")
        return []


def get_chat_detail(analysis_id):
    try:
        with get_giso_db_conn() as conn:
            row = conn.execute(
                "SELECT a.id, a.consultant_chat_history, a.consultant_key_notes, a.chat_rating, "
                "COALESCE(u.name, w.name, 'کاربر ناشناس') AS user_name, "
                "COALESCE(u.phone, w.phone, '') AS phone, a.type, a.created_at "
                "FROM analyses a "
                "LEFT JOIN giso_web_auth u ON a.user_id = u.id "
                "LEFT JOIN giso_web_auth w ON a.phone = w.phone "
                "WHERE a.id=?", (int(analysis_id),)).fetchone()
        if not row:
            return None
        d = dict(row)
        try:
            history = json.loads(d.get("consultant_chat_history") or "[]")
            d["messages"] = history if isinstance(history, list) else []
        except Exception:
            d["messages"] = []
        return d
    except Exception as e:
        logger.error(f"panel chat detail: {e}")
        return None


# ───────────────────── handler ها (POST — مثل ربات) ─────────────────────

def handle_consultant_reply(req_id):
    """پاسخ ادمین به درخواست مشاوره — INSERT در consultant_messages + وضعیت chatting."""
    g = _require_analysis_perm()
    if g:
        return g
    text = (request.form.get("message") or "").strip()
    if not text:
        flash("متن پاسخ خالی است.", "warning")
        return redirect(url_for("panel.analyses", tab="consultants"))
    try:
        with get_giso_db_conn() as conn:
            conn.execute(
                "INSERT INTO consultant_messages (request_id, sender, message, is_read, created_at) "
                "VALUES (?, 'admin', ?, 0, ?)",
                (req_id, text, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
            conn.execute("UPDATE consultant_requests SET status='chatting', updated_at=? WHERE id=?",
                         (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), req_id))
            conn.commit()
        try:
            from giso.panel.modules.notifications import safe_log as _nlog
            _nlog("analysis", "consultant", "پاسخ به درخواست مشاوره",
                  f"درخواست #{req_id}", source_type="consultant_reply", source_id=req_id)
        except Exception:
            pass
        flash(f"پاسخ شما برای درخواست #{req_id} ثبت و در ربات هم اعمال شد.", "success")
    except Exception as e:
        logger.error(f"panel consultant reply: {e}")
        flash("خطا در ثبت پاسخ.", "danger")
    return redirect(url_for("panel.analyses", tab="consultants", cons=req_id))


def handle_consultant_status(req_id):
    """تغییر وضعیت درخواست مشاوره: new / reviewing / closed."""
    g = _require_analysis_perm()
    if g:
        return g
    status = (request.form.get("status") or "").strip().lower()
    if status not in ("new", "reviewing", "chatting", "closed"):
        flash("وضعیت نامعتبر است.", "warning")
        return redirect(url_for("panel.analyses", tab="consultants"))
    try:
        with get_giso_db_conn() as conn:
            conn.execute("UPDATE consultant_requests SET status=?, updated_at=? WHERE id=?",
                         (status, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), req_id))
            conn.commit()
        try:
            from giso.panel.modules.notifications import safe_log as _nlog
            _nlog("analysis", "consultant", "تغییر وضعیت مشاوره",
                  f"درخواست #{req_id} → {status}", source_type="consultant_status", source_id=req_id)
        except Exception:
            pass
        flash(f"وضعیت درخواست #{req_id} به «{status}» تغییر کرد.", "success")
    except Exception as e:
        logger.error(f"panel consultant status: {e}")
        flash("خطا در تغییر وضعیت.", "danger")
    return redirect(url_for("panel.analyses", tab="consultants", cons=req_id))


def handle_product_status(req_id):
    """تغییر وضعیت محصول درخواستی: added / rejected (+ یادداشت)."""
    g = _require_analysis_perm()
    if g:
        return g
    status = (request.form.get("status") or "").strip().lower()
    if status not in ("added", "rejected"):
        flash("وضعیت نامعتبر است.", "warning")
        return redirect(url_for("panel.analyses", tab="products"))
    note = (request.form.get("admin_note") or "").strip()
    try:
        with get_giso_db_conn() as conn:
            phone_row = conn.execute("SELECT phone FROM product_requests WHERE id=?", (req_id,)).fetchone()
            conn.execute("UPDATE product_requests SET status=?, admin_note=? WHERE id=?",
                         (status, note, req_id))
            conn.commit()
        user_phone = str(phone_row["phone"] or "") if phone_row else ""
        try:
            from giso.panel.modules.notifications import safe_log as _nlog
            _nlog("analysis", "product_request", "تغییر وضعیت درخواست محصول",
                  f"درخواست #{req_id} → {status}", source_type="product_req_status", source_id=req_id)
        except Exception:
            pass
        # اعلان به کاربر در پنل سایت (تأیید/رد درخواست محصول)
        if user_phone:
            try:
                from giso.panel.modules.notifications import log_user_notification
                _st_fa = "به محصولات اضافه شد ✅" if status == "added" else "رد شد ❌"
                _note_fa = f" — یادداشت: {note}" if note else ""
                log_user_notification(user_phone, "product_request_status", "وضعیت درخواست محصول",
                                      f"درخواست محصول #{req_id} شما: {_st_fa}{_note_fa}",
                                      source_type="product_req_user_status", source_id=req_id,
                                      category="analysis")
            except Exception:
                pass
        flash(f"وضعیت درخواست محصول #{req_id} تغییر کرد.", "success")
    except Exception as e:
        logger.error(f"panel product status: {e}")
        flash("خطا در تغییر وضعیت.", "danger")
    return redirect(url_for("panel.analyses", tab="products", prod=req_id))


# ───────────────────── context ─────────────────────

def context():
    rows = []
    stats = {"total": 0, "today": 0, "this_week": 0, "this_month": 0,
             "hair_count": 0, "skin_count": 0, "avg_rating": 0,
             "total_consultants": 0, "pending_consultants": 0,
             "total_products": 0, "pending_products": 0, "total_reviews": 0}
    try:
        with get_giso_db_conn() as conn:
            all_rows = [dict(r) for r in conn.execute(
                "SELECT a.*, w.name as user_name, w.city as user_city FROM analyses a "
                "LEFT JOIN giso_web_auth w ON a.phone=w.phone ORDER BY a.id DESC").fetchall()]
            stats["total"] = len(all_rows)
            today = datetime.now().strftime("%Y-%m-%d")
            week_ago = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
            month_ago = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
            stats["today"] = conn.execute("SELECT COUNT(*) FROM analyses WHERE created_at LIKE ?", (f"{today}%",)).fetchone()[0]
            stats["this_week"] = conn.execute("SELECT COUNT(*) FROM analyses WHERE created_at >= ?", (week_ago,)).fetchone()[0]
            stats["this_month"] = conn.execute("SELECT COUNT(*) FROM analyses WHERE created_at >= ?", (month_ago,)).fetchone()[0]
            stats["hair_count"] = conn.execute("SELECT COUNT(*) FROM analyses WHERE type='hair'").fetchone()[0]
            stats["skin_count"] = conn.execute("SELECT COUNT(*) FROM analyses WHERE type='skin'").fetchone()[0]
            stats["total_consultants"] = conn.execute("SELECT COUNT(*) FROM consultant_requests").fetchone()[0]
            stats["pending_consultants"] = conn.execute(
                "SELECT COUNT(*) FROM consultant_requests WHERE status IN ('new','reviewing')").fetchone()[0]
            stats["total_products"] = conn.execute("SELECT COUNT(*) FROM product_requests").fetchone()[0]
            stats["pending_products"] = conn.execute(
                "SELECT COUNT(*) FROM product_requests WHERE status='pending'").fetchone()[0]
            stats["total_reviews"] = conn.execute("SELECT COUNT(*) FROM reviews").fetchone()[0]
            try:
                stats["avg_rating"] = round(conn.execute(
                    "SELECT AVG(rating) FROM reviews WHERE rating>0").fetchone()[0] or 0, 1)
            except Exception:
                stats["avg_rating"] = 0
            for r in all_rows:
                rep = {}
                try:
                    rep = json.loads(r.get("ai_report_json") or "{}")
                except Exception:
                    rep = {}
                r["type_fa"] = "💇 آنالیز مو" if (r.get("type") or "hair") == "hair" else "✨ آنالیز پوست"
                r["score"] = rep.get("overall_score", 0)
                r["status"] = rep.get("status_label", "")
                rows.append(r)
    except Exception as e:
        logger.error(f"panel analyses: {e}")

    # فاز 4.7: پروفایل خلاصه کاربر در جزئیات آنالیز
    user_summary = None
    detail = None
    did = request.args.get("detail", "")
    if did:
        try:
            did = int(did)
            for a in rows:
                if a["id"] == did:
                    detail = a
                    break
            if detail:
                user_summary = _user_summary(detail.get("phone") or "")
        except Exception:
            pass

    # فاز 5: تب‌ها
    tab = (request.args.get("tab") or "analyses").strip().lower()
    consultants = get_consultant_requests() if tab in ("consultants", "all") else []
    products = get_product_requests() if tab in ("products", "all") else []
    chats_filter = (request.args.get("chats") or "all").strip().lower()
    if chats_filter not in ("today", "week", "month", "all"):
        chats_filter = "all"
    chat_summaries = get_chat_summaries(chats_filter) if tab in ("chats", "all") else []
    chat_detail = None
    cid = request.args.get("chat_view", "")
    if cid:
        try:
            chat_detail = get_chat_detail(int(cid))
        except Exception:
            pass
    cons_detail = None
    cons_id = request.args.get("cons", "")
    if cons_id and tab == "consultants":
        try:
            cons_id = int(cons_id)
            for c in consultants:
                if c["id"] == cons_id:
                    cons_detail = c
                    break
            if cons_detail:
                cons_detail["messages"] = get_consultant_messages(cons_id)
        except Exception:
            pass
    prod_detail = None
    prod_id = request.args.get("prod", "")
    if prod_id and tab == "products":
        try:
            prod_id = int(prod_id)
            for p in products:
                if p["id"] == prod_id:
                    prod_detail = p
                    break
        except Exception:
            pass

    # فاز جامع UX: تب «⏱ محدودیت زمانی» — همان دیتای ماژول ratelimit
    rl = {}
    try:
        from giso.panel.modules import ratelimit as _rl
        rl = _rl.context()
    except Exception:
        # fail-closed: در خطای خواندن، محدودیت پیش‌فرض محافظه‌کارانه فعال فرض می‌شود
        rl = {"rate_limit_enabled": True, "rate_limit_minutes": 5, "rate_limit_type": "both"}
    return {
        "rate_limit": rl,
        "analyses": rows,
        "stats": stats,
        "detail": detail,
        "user_summary": user_summary,
        "tab": tab,
        "consultants": consultants,
        "products": products,
        "chats_filter": chats_filter,
        "chat_summaries": chat_summaries,
        "chat_detail": chat_detail,
        "cons_detail": cons_detail,
        "prod_detail": prod_detail,
        "fa_num": _fa_num,
    }
