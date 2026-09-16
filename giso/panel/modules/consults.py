# -*- coding: utf-8 -*-
"""مدیریت گفتگوها: خرید مو، فروشگاه، بازارچه، پشتیبانی — تک‌به‌تک با ادامه/پایان."""
import logging
from datetime import datetime

from flask import request, redirect, url_for, flash

from giso.base import get_giso_db_conn

logger = logging.getLogger("giso_panel_consults")

STATUS_LABELS = {
    "new": "🆕 جدید",
    "reviewing": "👀 در حال بررسی",
    "chatting": "💬 در حال گفتگو",
    "pending": "⏳ در انتظار",
    "active": "✅ فعال",
    "closed": "🔒 بسته‌شده",
    "replied": "✉️ پاسخ داده شد",
}
KINDS = ("hair", "shop", "market", "support")
KIND_LABELS = {
    "hair": "خرید مو",
    "shop": "فروشگاه",
    "market": "بازارچه",
    "support": "پشتیبانی",
}


def _now():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _ensure_shop_messages():
    try:
        with get_giso_db_conn() as conn:
            conn.execute(
                "CREATE TABLE IF NOT EXISTS shop_order_messages ("
                "id INTEGER PRIMARY KEY AUTOINCREMENT,"
                "order_id INTEGER NOT NULL,"
                "sender TEXT DEFAULT 'admin',"
                "message TEXT DEFAULT '',"
                "created_at TEXT DEFAULT '')"
            )
            conn.execute("CREATE INDEX IF NOT EXISTS idx_shop_msg_order ON shop_order_messages(order_id)")
            conn.commit()
    except Exception as exc:
        logger.debug("ensure shop messages: %s", exc)


def _ids_hair():
    try:
        with get_giso_db_conn() as conn:
            rows = conn.execute(
                "SELECT DISTINCT order_id FROM hair_messages ORDER BY order_id DESC LIMIT 200"
            ).fetchall()
            return [int(r[0]) for r in rows if r[0]]
    except Exception:
        return []


def _ids_shop():
    _ensure_shop_messages()
    ids = []
    try:
        with get_giso_db_conn() as conn:
            rows = conn.execute(
                "SELECT DISTINCT order_id FROM shop_order_messages ORDER BY order_id DESC LIMIT 200"
            ).fetchall()
            ids.extend(int(r[0]) for r in rows if r[0])
            extra = conn.execute(
                "SELECT id FROM product_orders ORDER BY id DESC LIMIT 80"
            ).fetchall()
            for r in extra:
                oid = int(r[0])
                if oid not in ids:
                    ids.append(oid)
    except Exception:
        pass
    return ids[:200]


def _ids_market():
    try:
        with get_giso_db_conn() as conn:
            rows = conn.execute(
                "SELECT DISTINCT offer_id FROM marketplace_messages ORDER BY offer_id DESC LIMIT 200"
            ).fetchall()
            return [int(r[0]) for r in rows if r[0]]
    except Exception:
        return []


def _ids_support():
    ids = []
    try:
        with get_giso_db_conn() as conn:
            for r in conn.execute("SELECT id FROM giso_support_tickets ORDER BY id DESC LIMIT 120").fetchall():
                ids.append(int(r[0]))
            for r in conn.execute("SELECT id FROM consultant_requests ORDER BY id DESC LIMIT 80").fetchall():
                ids.append(int(r[0]) + 1000000)
    except Exception:
        pass
    return ids


def _kind_ids(kind):
    return {
        "hair": _ids_hair,
        "shop": _ids_shop,
        "market": _ids_market,
        "support": _ids_support,
    }.get(kind, lambda: [])()


def _load_thread(kind, cid):
    cid = int(cid or 0)
    if not cid:
        return None, []
    try:
        with get_giso_db_conn() as conn:
            if kind == "hair":
                order = conn.execute("SELECT * FROM hair_orders WHERE id=?", (cid,)).fetchone()
                msgs = conn.execute(
                    "SELECT sender, message, created_at FROM hair_messages WHERE order_id=? ORDER BY id ASC",
                    (cid,),
                ).fetchall()
                if not order:
                    return None, []
                closed = (order["status"] or "") in ("completed", "rejected")
                return {
                    "id": cid, "kind": kind, "closed": closed,
                    "title": f"درخواست مو #{cid} — {order['customer_name'] or 'کاربر'}",
                    "subtitle": order["phone"] or "",
                    "status": order["status"] or "",
                }, [dict(m) for m in msgs]
            if kind == "shop":
                _ensure_shop_messages()
                order = conn.execute("SELECT * FROM product_orders WHERE id=?", (cid,)).fetchone()
                msgs = conn.execute(
                    "SELECT sender, message, created_at FROM shop_order_messages WHERE order_id=? ORDER BY id ASC",
                    (cid,),
                ).fetchall()
                if not order:
                    return None, []
                out_msgs = [dict(m) for m in msgs]
                if order["courier_note"]:
                    out_msgs.insert(0, {"sender": "user", "message": order["courier_note"], "created_at": order["created_at"]})
                closed = (order["status"] or "") in ("delivered", "completed", "cancelled", "rejected")
                return {
                    "id": cid, "kind": kind, "closed": closed,
                    "title": f"سفارش #{cid} — {order['customer_name'] or 'کاربر'}",
                    "subtitle": f"{order['phone'] or ''} · {order['tracking_code'] or ''}",
                    "status": order["status"] or "",
                }, out_msgs
            if kind == "market":
                offer = conn.execute("SELECT * FROM buyer_offers WHERE id=?", (cid,)).fetchone()
                msgs = conn.execute(
                    "SELECT sender_role AS sender, message_text AS message, created_at "
                    "FROM marketplace_messages WHERE offer_id=? ORDER BY id ASC",
                    (cid,),
                ).fetchall()
                if not offer:
                    return None, []
                closed = bool(int(offer["chat_closed"] or 0)) or (offer["status"] or "") in ("sold", "rejected", "withdrawn")
                return {
                    "id": cid, "kind": kind, "closed": closed,
                    "title": f"پیشنهاد بازارچه #{cid}",
                    "subtitle": f"آگهی #{offer['listing_id']}",
                    "status": offer["status"] or "",
                }, [{"sender": m["sender"], "message": m["message"], "created_at": m["created_at"]} for m in msgs]
            if kind == "support":
                if cid >= 1000000:
                    req_id = cid - 1000000
                    req = conn.execute("SELECT * FROM consultant_requests WHERE id=?", (req_id,)).fetchone()
                    msgs = conn.execute(
                        "SELECT sender, message, created_at FROM consultant_messages WHERE request_id=? ORDER BY id ASC",
                        (req_id,),
                    ).fetchall()
                    if not req:
                        return None, []
                    closed = (req["status"] or "") == "closed"
                    return {
                        "id": cid, "kind": kind, "closed": closed, "real_id": req_id, "support_type": "consultant",
                        "title": f"مشاوره #{req_id} — {req['customer_name'] or 'کاربر'}",
                        "subtitle": req["phone"] or "",
                        "status": req["status"] or "",
                    }, [dict(m) for m in msgs]
                ticket = conn.execute("SELECT * FROM giso_support_tickets WHERE id=?", (cid,)).fetchone()
                if not ticket:
                    return None, []
                msgs = [{"sender": "user", "message": ticket["message"], "created_at": ticket["created_at"]}]
                if ticket["admin_reply"]:
                    msgs.append({"sender": "admin", "message": ticket["admin_reply"], "created_at": ticket["replied_at"] or ""})
                closed = (ticket["status"] or "") in ("closed",)
                return {
                    "id": cid, "kind": kind, "closed": closed, "real_id": cid, "support_type": "ticket",
                    "title": f"تیکت #{cid} — {ticket['user_name'] or 'کاربر'}",
                    "subtitle": ticket["phone"] or "",
                    "status": ticket["status"] or "",
                }, msgs
    except Exception as exc:
        logger.error("load thread %s/%s: %s", kind, cid, exc)
    return None, []


def context():
    kind = (request.args.get("kind") or "hair").strip().lower()
    if kind not in KINDS:
        kind = "hair"
    try:
        cid = int(request.args.get("cid") or 0)
    except (TypeError, ValueError):
        cid = 0
    ids = _kind_ids(kind)
    if not cid and ids:
        cid = ids[0]
    detail, messages = _load_thread(kind, cid) if cid else (None, [])
    prev_id = next_id = 0
    if cid and ids:
        try:
            idx = ids.index(cid)
        except ValueError:
            idx = -1
        if idx > 0:
            prev_id = ids[idx - 1]
        if 0 <= idx < len(ids) - 1:
            next_id = ids[idx + 1]
    counts = {k: len(_kind_ids(k)) for k in KINDS}
    return {
        "chat_kind": kind,
        "chat_kinds": KINDS,
        "chat_kind_labels": KIND_LABELS,
        "chat_ids": ids,
        "chat_counts": counts,
        "thread": detail,
        "thread_messages": messages,
        "thread_id": cid,
        "prev_id": prev_id,
        "next_id": next_id,
        "cons_status_labels": STATUS_LABELS,
        # سازگاری قالب قدیمی
        "consults": [],
        "support_tickets": [],
        "support_open_count": counts.get("support", 0),
        "cons_detail": None,
        "cons_messages": [],
        "cons_sel": 0,
        "cons_open_count": 0,
    }


def _redirect_thread(kind, cid):
    return redirect(url_for("panel.consults", kind=kind, cid=cid))


def handle_thread_reply():
    kind = (request.form.get("kind") or "hair").strip().lower()
    if kind not in KINDS:
        kind = "hair"
    try:
        cid = int(request.form.get("cid") or 0)
    except (TypeError, ValueError):
        cid = 0
    text = (request.form.get("message") or "").strip()
    if not text or not cid:
        flash("متن پاسخ خالی است.", "warning")
        return _redirect_thread(kind, cid)
    try:
        with get_giso_db_conn() as conn:
            if kind == "hair":
                conn.execute(
                    "INSERT INTO hair_messages (order_id, sender, message, is_read, created_at) VALUES (?, 'admin', ?, 0, ?)",
                    (cid, text, _now()),
                )
            elif kind == "shop":
                _ensure_shop_messages()
                conn.execute(
                    "INSERT INTO shop_order_messages (order_id, sender, message, created_at) VALUES (?, 'admin', ?, ?)",
                    (cid, text, _now()),
                )
            elif kind == "market":
                from flask_login import current_user
                uid = int(getattr(current_user, "id", 0) or 0)
                conn.execute(
                    "INSERT INTO marketplace_messages (offer_id, sender_user_id, sender_role, message_text, created_at) "
                    "VALUES (?, ?, 'admin', ?, ?)",
                    (cid, uid, text, _now()),
                )
            elif kind == "support":
                if cid >= 1000000:
                    req_id = cid - 1000000
                    conn.execute(
                        "INSERT INTO consultant_messages (request_id, sender, message, is_read, created_at) "
                        "VALUES (?, 'admin', ?, 0, ?)",
                        (req_id, text, _now()),
                    )
                    conn.execute(
                        "UPDATE consultant_requests SET status='chatting', updated_at=? WHERE id=?",
                        (_now(), req_id),
                    )
                else:
                    conn.execute(
                        "UPDATE giso_support_tickets SET admin_reply=?, status='replied', replied_at=? WHERE id=?",
                        (text[:2000], _now(), cid),
                    )
            conn.commit()
        flash("پیام ثبت شد.", "success")
    except Exception as exc:
        logger.error("thread reply: %s", exc)
        flash("خطا در ثبت پیام.", "danger")
    return _redirect_thread(kind, cid)


def handle_thread_status():
    kind = (request.form.get("kind") or "hair").strip().lower()
    action = (request.form.get("action") or "").strip().lower()
    try:
        cid = int(request.form.get("cid") or 0)
    except (TypeError, ValueError):
        cid = 0
    continue_chat = action in ("continue", "open", "chatting")
    try:
        with get_giso_db_conn() as conn:
            if kind == "hair":
                conn.execute(
                    "UPDATE hair_orders SET status=?, updated_at=? WHERE id=?",
                    ("reviewing" if continue_chat else "completed", _now(), cid),
                )
            elif kind == "shop":
                conn.execute(
                    "UPDATE product_orders SET status=? WHERE id=?",
                    ("approved" if continue_chat else "completed", cid),
                )
            elif kind == "market":
                conn.execute(
                    "UPDATE buyer_offers SET chat_closed=?, chat_closed_at=? WHERE id=?",
                    (0 if continue_chat else 1, "" if continue_chat else _now(), cid),
                )
            elif kind == "support":
                if cid >= 1000000:
                    conn.execute(
                        "UPDATE consultant_requests SET status=?, updated_at=? WHERE id=?",
                        ("chatting" if continue_chat else "closed", _now(), cid - 1000000),
                    )
                else:
                    conn.execute(
                        "UPDATE giso_support_tickets SET status=? WHERE id=?",
                        ("reviewing" if continue_chat else "closed", cid),
                    )
            conn.commit()
        flash("گفتگو ادامه یافت." if continue_chat else "گفتگو پایان یافت.", "success")
    except Exception as exc:
        logger.error("thread status: %s", exc)
        flash("خطا در تغییر وضعیت گفتگو.", "danger")
    return _redirect_thread(kind, cid)


# ── سازگاری با routeهای قبلی مشاوره ──
def handle_reply(req_id: int):
    text = (request.form.get("message") or "").strip()
    if not text:
        flash("متن پاسخ خالی است.", "warning")
        return redirect(url_for("panel.consults", kind="support", cid=req_id + 1000000))
    try:
        with get_giso_db_conn() as conn:
            conn.execute(
                "INSERT INTO consultant_messages (request_id, sender, message, is_read, created_at) "
                "VALUES (?, 'admin', ?, 0, ?)",
                (req_id, text, _now()))
            conn.execute(
                "UPDATE consultant_requests SET status='chatting', updated_at=? WHERE id=?",
                (_now(), req_id))
            conn.commit()
            phone_row = conn.execute(
                "SELECT phone FROM consultant_requests WHERE id=?", (req_id,)
            ).fetchone()
        user_phone = str(phone_row["phone"] or "") if phone_row else ""
        # اعلان به کاربر (بله + پنل کاربر) — دقیقاً مثل مسیر legacy /admin
        if user_phone:
            try:
                from giso.app import _notify_consultant_user_new_msg
                _notify_consultant_user_new_msg(req_id, text)
            except Exception as e_bale:
                logger.debug(f"consults reply bale notify: {e_bale}")
            try:
                from giso.panel.modules.notifications import log_user_notification
                log_user_notification(user_phone, "consultant_reply", "پاسخ مشاور گیسو", text,
                                      source_type="consultant_reply", source_id=req_id)
            except Exception as e_site:
                logger.debug(f"consults reply user notification: {e_site}")
        flash(f"پاسخ شما برای درخواست #{req_id} ثبت شد.", "success")
    except Exception as e:
        logger.error(f"consults reply: {e}")
        flash("خطا در ثبت پاسخ.", "danger")
    return redirect(url_for("panel.consults", kind="support", cid=req_id + 1000000))


def handle_status(req_id: int):
    status = (request.form.get("status") or "").strip().lower()
    valid = ("new", "reviewing", "chatting", "closed")
    if status not in valid:
        flash("وضعیت نامعتبر است.", "warning")
        return redirect(url_for("panel.consults", kind="support", cid=req_id + 1000000))
    try:
        with get_giso_db_conn() as conn:
            conn.execute("UPDATE consultant_requests SET status=?, updated_at=? WHERE id=?",
                         (status, _now(), req_id))
            conn.commit()
        flash(f"وضعیت گفتگوی #{req_id} تغییر کرد.", "success")
    except Exception as e:
        logger.error(f"consults status: {e}")
        flash("خطا در تغییر وضعیت.", "danger")
    return redirect(url_for("panel.consults", kind="support", cid=req_id + 1000000))


def handle_support_reply(ticket_id: int):
    message = (request.form.get("message") or "").strip()
    if not message:
        flash("متن پاسخ خالی است.", "warning")
        return redirect(url_for("panel.consults", kind="support", cid=ticket_id))
    try:
        with get_giso_db_conn() as conn:
            conn.execute(
                "UPDATE giso_support_tickets SET admin_reply=?, status='replied', replied_at=? WHERE id=?",
                (message[:2000], _now(), ticket_id),
            )
            conn.commit()
            trow = conn.execute(
                "SELECT phone FROM giso_support_tickets WHERE id=?", (int(ticket_id),)
            ).fetchone()
        user_phone = str(trow["phone"] or "") if trow else ""
        # اعلان به کاربر در پنل سایت (بله از مسیر ربات ارسال می‌شود)
        if user_phone:
            try:
                from giso.panel.modules.notifications import log_user_notification
                log_user_notification(user_phone, "support_reply", "پاسخ پشتیبانی گیسو",
                                      f"تیکت #{int(ticket_id)}: {message[:300]}",
                                      source_type="support_reply", source_id=int(ticket_id))
            except Exception as e_notif:
                logger.debug(f"support reply user notify: {e_notif}")
        flash(f"پاسخ تیکت #{ticket_id} ثبت شد.", "success")
    except Exception as e:
        logger.error("support ticket reply: %s", e)
        flash("خطا در ثبت پاسخ تیکت.", "danger")
    return redirect(url_for("panel.consults", kind="support", cid=ticket_id))


def handle_support_status(ticket_id: int):
    status = (request.form.get("status") or "").strip()
    if status not in ("new", "reviewing", "closed"):
        flash("وضعیت تیکت نامعتبر است.", "warning")
        return redirect(url_for("panel.consults", kind="support", cid=ticket_id))
    try:
        with get_giso_db_conn() as conn:
            conn.execute("UPDATE giso_support_tickets SET status=? WHERE id=?", (status, ticket_id))
            conn.commit()
        flash(f"وضعیت تیکت #{ticket_id} تغییر کرد.", "success")
    except Exception as e:
        logger.error("support ticket status: %s", e)
        flash("خطا در تغییر وضعیت تیکت.", "danger")
    return redirect(url_for("panel.consults", kind="support", cid=ticket_id))


def handle_delete(req_id: int):
    try:
        with get_giso_db_conn() as conn:
            conn.execute("DELETE FROM consultant_messages WHERE request_id=?", (req_id,))
            conn.execute("DELETE FROM consultant_requests WHERE id=?", (req_id,))
            conn.commit()
        flash(f"💬 گفتگوی #{req_id} حذف شد.", "success")
    except Exception as e:
        logger.error(f"consults delete: {e}")
        flash("خطا در حذف گفتگو.", "danger")
    return redirect(url_for("panel.consults", kind="support"))
