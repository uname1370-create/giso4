# -*- coding: utf-8 -*-
"""مدیریت گفتگوها در ربات: خرید مو / فروشگاه / بازارچه / پشتیبانی."""
import logging
import time

from giso.base import get_giso_db_conn, _fa_num, display_phone, to_shamsi

logger = logging.getLogger("giso_bot_chats_admin")

KINDS = ("hair", "shop", "market", "support")
KIND_LABEL = {
    "hair": "💇 گفتگوی خرید مو",
    "shop": "🛍 گفتگوی فروشگاه",
    "market": "🏪 گفتگوی بازارچه",
    "support": "💬 پشتیبانی",
}


def chats_menu_kb():
    from telegram import KeyboardButton, ReplyKeyboardMarkup
    return ReplyKeyboardMarkup(
        [
            [KeyboardButton("💇 گفتگوی خرید مو"), KeyboardButton("🛍 گفتگوی فروشگاه")],
            [KeyboardButton("🏪 گفتگوی بازارچه"), KeyboardButton("💬 پشتیبانی")],
            [KeyboardButton("🔙 بازگشت")],
        ],
        resize_keyboard=True,
    )


def chats_menu_text() -> str:
    return (
        "💬 مدیریت گفتگوها\n"
        "━━━━━━━━━━━━━━━━\n"
        "هر بخش را بزن تا گفتگوها تک‌به‌تک بیاید.\n"
        "برای هر گفتگو: پاسخ، پایان، قبلی، بعدی، بازگشت."
    )


def _kind_from_text(text: str):
    return {
        "💇 گفتگوی خرید مو": "hair",
        "🛍 گفتگوی فروشگاه": "shop",
        "🏪 گفتگوی بازارچه": "market",
        "💬 پشتیبانی": "support",
    }.get(text)


def _ids(kind):
    try:
        with get_giso_db_conn() as conn:
            if kind == "hair":
                rows = conn.execute(
                    "SELECT DISTINCT order_id AS id FROM hair_messages ORDER BY id DESC LIMIT 150"
                ).fetchall()
            elif kind == "shop":
                try:
                    conn.execute(
                        "CREATE TABLE IF NOT EXISTS shop_order_messages ("
                        "id INTEGER PRIMARY KEY AUTOINCREMENT, order_id INTEGER NOT NULL,"
                        "sender TEXT DEFAULT 'admin', message TEXT DEFAULT '', created_at TEXT DEFAULT '')"
                    )
                    conn.commit()
                except Exception:
                    pass
                rows = conn.execute(
                    "SELECT DISTINCT order_id AS id FROM shop_order_messages ORDER BY id DESC LIMIT 80"
                ).fetchall()
                extra = conn.execute(
                    "SELECT id FROM product_orders WHERE status IN ('pending','approved','shipped') "
                    "ORDER BY id DESC LIMIT 40"
                ).fetchall()
                seen = {int(r["id"]) for r in rows}
                out = [int(r["id"]) for r in rows]
                for r in extra:
                    if int(r["id"]) not in seen:
                        out.append(int(r["id"]))
                return out[:150]
            elif kind == "market":
                rows = conn.execute(
                    "SELECT DISTINCT offer_id AS id FROM marketplace_messages ORDER BY id DESC LIMIT 150"
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT id FROM giso_support_tickets WHERE status IN ('new','reviewing','replied') "
                    "ORDER BY id DESC LIMIT 150"
                ).fetchall()
        return [int(r["id"]) for r in rows]
    except Exception as exc:
        logger.error("gchat ids %s: %s", kind, exc)
        return []


def _load(kind, cid):
    cid = int(cid or 0)
    try:
        with get_giso_db_conn() as conn:
            if kind == "hair":
                head = conn.execute("SELECT * FROM hair_orders WHERE id=?", (cid,)).fetchone()
                msgs = conn.execute(
                    "SELECT sender, message, created_at FROM hair_messages WHERE order_id=? ORDER BY id ASC",
                    (cid,),
                ).fetchall()
                if not head:
                    return None, []
                head = dict(head)
                title = f"گفتگوی خرید مو #{_fa_num(cid)} — {head.get('customer_name') or 'کاربر'}"
                sub = display_phone(head.get("phone") or "")
                closed = (head.get("status") or "") in ("completed", "rejected")
            elif kind == "shop":
                head = conn.execute("SELECT * FROM product_orders WHERE id=?", (cid,)).fetchone()
                try:
                    msgs = conn.execute(
                        "SELECT sender, message, created_at FROM shop_order_messages WHERE order_id=? ORDER BY id ASC",
                        (cid,),
                    ).fetchall()
                except Exception:
                    msgs = []
                if not head:
                    return None, []
                head = dict(head)
                title = f"گفتگوی فروشگاه #{_fa_num(cid)} — {head.get('customer_name') or 'کاربر'}"
                sub = f"{display_phone(head.get('phone') or '')} · {head.get('tracking_code') or ''}"
                closed = (head.get("status") or "") in ("delivered", "completed", "cancelled", "rejected")
            elif kind == "market":
                head = conn.execute("SELECT * FROM buyer_offers WHERE id=?", (cid,)).fetchone()
                msgs = conn.execute(
                    "SELECT sender_role AS sender, message_text AS message, created_at "
                    "FROM marketplace_messages WHERE offer_id=? ORDER BY id ASC",
                    (cid,),
                ).fetchall()
                if not head:
                    return None, []
                head = dict(head)
                title = f"گفتگوی بازارچه — پیشنهاد #{_fa_num(cid)}"
                sub = f"آگهی #{head.get('listing_id')}"
                closed = bool(int(head.get("chat_closed") or 0))
            else:
                head = conn.execute("SELECT * FROM giso_support_tickets WHERE id=?", (cid,)).fetchone()
                if not head:
                    return None, []
                head = dict(head)
                msgs = [{"sender": "user", "message": head.get("message"), "created_at": head.get("created_at")}]
                if head.get("admin_reply"):
                    msgs.append({"sender": "admin", "message": head.get("admin_reply"), "created_at": head.get("replied_at") or ""})
                title = f"تیکت پشتیبانی #{_fa_num(cid)} — {head.get('user_name') or 'کاربر'}"
                sub = display_phone(head.get("phone") or "")
                closed = (head.get("status") or "") == "closed"
                return {"id": cid, "kind": kind, "title": title, "sub": sub, "closed": closed}, msgs
        return {
            "id": cid, "kind": kind, "title": title, "sub": sub, "closed": closed,
        }, [dict(m) for m in msgs]
    except Exception as exc:
        logger.error("gchat load: %s", exc)
        return None, []


def _thread_text(detail, messages, idx, total):
    lines = [
        f"{detail['title']}",
        "━━━━━━━━━━━━━━━━",
        f"📄 {_fa_num(idx + 1)} از {_fa_num(total)}",
        f"{detail['sub']}",
        "━━━━━━━━━━━━━━━━",
    ]
    if not messages:
        lines.append("هنوز پیامی نیست.")
    else:
        for m in messages[-8:]:
            who = "🧑‍💼 کارشناس" if m.get("sender") in ("admin", "seller") else "👤 کاربر"
            lines.append(f"{who} · {to_shamsi(m.get('created_at'))}\n{(m.get('message') or '')[:400]}")
            lines.append("")
    return "\n".join(lines)


def _kb(kind, cid, idx, total, closed=False):
    from telegram import InlineKeyboardButton, InlineKeyboardMarkup
    rows = []
    if not closed:
        rows.append([
            InlineKeyboardButton("✉️ پاسخ به پیام", callback_data=f"gchat_reply|{kind}|{cid}|{idx}"),
            InlineKeyboardButton("⏹ پایان", callback_data=f"gchat_end|{kind}|{cid}|{idx}"),
        ])
    else:
        rows.append([InlineKeyboardButton("▶️ ادامه گفتگو", callback_data=f"gchat_open|{kind}|{cid}|{idx}")])
    nav = []
    if idx > 0:
        nav.append(InlineKeyboardButton("◀️ قبلی", callback_data=f"gchat_pg|{kind}|{idx - 1}"))
    if idx < total - 1:
        nav.append(InlineKeyboardButton("بعدی ▶️", callback_data=f"gchat_pg|{kind}|{idx + 1}"))
    if nav:
        rows.append(nav)
    rows.append([InlineKeyboardButton("🔙 بازگشت", callback_data="gchat_back")])
    return InlineKeyboardMarkup(rows)


async def show_kind_paged(message, kind, idx=0):
    ids = _ids(kind)
    if not ids:
        await message.reply_text(
            f"📭 گفتگویی در «{KIND_LABEL.get(kind, kind)}» نیست.",
            reply_markup=chats_menu_kb(),
        )
        return 0
    idx = max(0, min(int(idx or 0), len(ids) - 1))
    detail, messages = _load(kind, ids[idx])
    if not detail:
        await message.reply_text("گفتگو پیدا نشد.", reply_markup=chats_menu_kb())
        return 0
    await message.reply_text(
        _thread_text(detail, messages, idx, len(ids)),
        reply_markup=_kb(kind, detail["id"], idx, len(ids), detail.get("closed")),
    )
    return len(ids)


def save_reply(kind, cid, text):
    now = time.strftime("%Y-%m-%d %H:%M:%S")
    cid = int(cid)
    text = (text or "").strip()
    if not text:
        return False
    try:
        with get_giso_db_conn() as conn:
            if kind == "hair":
                conn.execute(
                    "INSERT INTO hair_messages (order_id, sender, message, is_read, created_at) "
                    "VALUES (?, 'admin', ?, 0, ?)",
                    (cid, text, now),
                )
            elif kind == "shop":
                conn.execute(
                    "CREATE TABLE IF NOT EXISTS shop_order_messages ("
                    "id INTEGER PRIMARY KEY AUTOINCREMENT, order_id INTEGER NOT NULL,"
                    "sender TEXT DEFAULT 'admin', message TEXT DEFAULT '', created_at TEXT DEFAULT '')"
                )
                conn.execute(
                    "INSERT INTO shop_order_messages (order_id, sender, message, created_at) VALUES (?, 'admin', ?, ?)",
                    (cid, text, now),
                )
            elif kind == "market":
                conn.execute(
                    "INSERT INTO marketplace_messages (offer_id, sender_user_id, sender_role, message_text, created_at) "
                    "VALUES (?, 0, 'admin', ?, ?)",
                    (cid, text, now),
                )
            else:
                conn.execute(
                    "UPDATE giso_support_tickets SET admin_reply=?, status='replied', replied_at=? WHERE id=?",
                    (text[:2000], now, cid),
                )
            conn.commit()
        return True
    except Exception as exc:
        logger.error("gchat save reply: %s", exc)
        return False


def end_thread(kind, cid, reopen=False):
    now = time.strftime("%Y-%m-%d %H:%M:%S")
    cid = int(cid)
    try:
        with get_giso_db_conn() as conn:
            if kind == "hair":
                conn.execute(
                    "UPDATE hair_orders SET status=?, updated_at=? WHERE id=?",
                    ("reviewing" if reopen else "completed", now, cid),
                )
            elif kind == "shop":
                conn.execute(
                    "UPDATE product_orders SET status=? WHERE id=?",
                    ("approved" if reopen else "completed", cid),
                )
            elif kind == "market":
                conn.execute(
                    "UPDATE buyer_offers SET chat_closed=?, chat_closed_at=? WHERE id=?",
                    (0 if reopen else 1, "" if reopen else now, cid),
                )
            else:
                conn.execute(
                    "UPDATE giso_support_tickets SET status=? WHERE id=?",
                    ("reviewing" if reopen else "closed", cid),
                )
            conn.commit()
        return True
    except Exception as exc:
        logger.error("gchat end: %s", exc)
        return False


async def handle_gchat_callback(query, data, user_states):
    msg = query.message
    uid = query.from_user.id if query.from_user else None
    if data == "gchat_back":
        if uid is not None:
            user_states.pop(uid, None)
        await msg.reply_text(chats_menu_text(), reply_markup=chats_menu_kb())
        return
    parts = data.split("|")
    action = parts[0]
    if action == "gchat_pg" and len(parts) >= 3:
        await show_kind_paged(msg, parts[1], int(parts[2]))
        return
    if action in ("gchat_end", "gchat_open") and len(parts) >= 4:
        kind, cid, idx = parts[1], parts[2], int(parts[3])
        end_thread(kind, cid, reopen=(action == "gchat_open"))
        await show_kind_paged(msg, kind, idx)
        return
    if action == "gchat_reply" and len(parts) >= 4:
        kind, cid, idx = parts[1], parts[2], parts[3]
        if uid is not None:
            user_states[uid] = f"gchat_reply|{kind}|{cid}|{idx}"
        await msg.reply_text("✉️ متن پاسخ را بفرستید (برای انصراف: لغو)")
        return
