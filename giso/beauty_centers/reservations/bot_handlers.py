# -*- coding: utf-8 -*-
"""Phase B reservation bot callbacks: rsv|confirm|<id>, rsv|reject|<id>, rsv|view|<id>."""
from __future__ import annotations

import logging

from giso.base import get_giso_db_conn
from giso.beauty_centers.reservations.services import (
    confirm_reservation,
    reject_reservation,
)

logger = logging.getLogger("giso_beauty_reservations_bot")


def _get_reservation(reservation_id: int) -> dict:
    try:
        rid = int(reservation_id or 0)
    except (TypeError, ValueError):
        return {}
    if not rid:
        return {}
    try:
        with get_giso_db_conn() as conn:
            row = conn.execute(
                "SELECT id,center_id,user_id,user_phone,user_name,service_id,service_name,"
                "service_price_min,duration_minutes,reservation_date,reservation_time,status,"
                "user_note,center_note,reject_reason,reminded_24h,reminded_2h,created_at,"
                "confirmed_at,cancelled_at FROM beauty_center_reservations WHERE id=?",
                (rid,),
            ).fetchone()
    except Exception:
        logger.exception("rsv bot: load reservation %s failed", rid)
        return {}
    return dict(row) if row else {}


def _get_center(center_id: int) -> dict:
    try:
        cid = int(center_id or 0)
    except (TypeError, ValueError):
        return {}
    if not cid:
        return {}
    try:
        with get_giso_db_conn() as conn:
            row = conn.execute(
                "SELECT id,name,slug FROM beauty_centers WHERE id=?",
                (cid,),
            ).fetchone()
    except Exception:
        logger.exception("rsv bot: load center %s failed", cid)
        return {}
    return dict(row) if row else {}


def _fmt(reservation: dict, center: dict) -> str:
    return (
        "📅 نوبت #%s\n"
        "💇 %s\n"
        "📍 %s\n"
        "📅 %s ساعت %s\n"
        "👤 %s (%s)\n"
        "📌 وضعیت: %s"
    ) % (
        reservation.get("id", "-"),
        reservation.get("service_name") or "-",
        center.get("name") or "-",
        reservation.get("reservation_date") or "-",
        reservation.get("reservation_time") or "-",
        reservation.get("user_name") or "-",
        reservation.get("user_phone") or "-",
        reservation.get("status") or "-",
    )


async def handle_reservation_bot(update, context) -> bool:
    """Handle rsv|* callbacks. Returns True when the update was consumed."""
    query = getattr(update, "callback_query", None)
    if query is None:
        return False
    data = str(getattr(query, "data", "") or "")
    if not data.startswith("rsv|"):
        return False
    parts = data.split("|")
    action = parts[1] if len(parts) > 1 else ""
    try:
        rid = int(parts[2]) if len(parts) > 2 else 0
    except (TypeError, ValueError):
        rid = 0
    try:
        await query.answer()
    except Exception:
        pass
    if not rid:
        try:
            await query.edit_message_text("❌ شناسه نوبت نامعتبر است.")
        except Exception:
            pass
        return True
    reservation = _get_reservation(rid)
    if not reservation:
        try:
            await query.edit_message_text("❌ نوبت پیدا نشد.")
        except Exception:
            pass
        return True
    center = _get_center(reservation.get("center_id", 0))
    if action == "view":
        try:
            await query.edit_message_text(_fmt(reservation, center))
        except Exception:
            logger.exception("rsv bot: view %s failed", rid)
        return True
    if action == "confirm":
        ok = False
        try:
            ok = bool(confirm_reservation(rid, int(reservation.get("center_id") or 0)))
        except Exception:
            logger.exception("rsv bot: confirm %s failed", rid)
        try:
            await query.edit_message_text(
                ("✅ نوبت تأیید شد.\n" if ok else "⚠️ این نوبت قابل تأیید نیست (وضعیت فعلی اجازه نمی‌دهد).\n")
                + _fmt(_get_reservation(rid) or reservation, center)
            )
        except Exception:
            pass
        if ok:
            try:
                from giso.beauty_centers.reservations.notifications import (
                    notify_user_confirmed,
                )
                notify_user_confirmed(_get_reservation(rid) or reservation, center)
            except Exception:
                logger.exception("rsv bot: confirm notify %s failed", rid)
        return True
    if action == "reject":
        reason = ""
        if len(parts) > 3:
            reason = "|".join(parts[3:]).strip()
        ok = False
        try:
            ok = bool(reject_reservation(rid, int(reservation.get("center_id") or 0), reason or "رد توسط مرکز"))
        except Exception:
            logger.exception("rsv bot: reject %s failed", rid)
        try:
            await query.edit_message_text(
                ("❌ نوبت رد شد.\n" if ok else "⚠️ این نوبت قابل رد نیست (وضعیت فعلی اجازه نمی‌دهد).\n")
                + _fmt(_get_reservation(rid) or reservation, center)
            )
        except Exception:
            pass
        if ok:
            try:
                from giso.beauty_centers.reservations.notifications import (
                    notify_user_rejected,
                )
                notify_user_rejected(_get_reservation(rid) or reservation, center)
            except Exception:
                logger.exception("rsv bot: reject notify %s failed", rid)
        return True
    try:
        await query.edit_message_text("❌ دستور ناشناخته.")
    except Exception:
        pass
    return True


__all__ = ["handle_reservation_bot"]
