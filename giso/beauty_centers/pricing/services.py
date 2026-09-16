# -*- coding: utf-8 -*-
"""Phase A pricing services: beauty center services and working hours.

Exactly the six documented functions:
  get_center_services, add_service, update_service, delete_service,
  get_working_hours, save_working_hours

Data access via get_giso_db_conn() only; absolute giso.* imports only.
The live DB still holds the legacy leftover columns (weekday/is_open on
working hours; updated_at + NOT NULL on services); they are kept in sync
so existing NOT NULL constraints and the original UNIQUE(center_id, weekday)
index stay satisfied without ever recreating a table.
"""
from __future__ import annotations

import logging
import re
from datetime import datetime

from giso.base import get_giso_db_conn

logger = logging.getLogger("giso_beauty_centers_pricing_services")

_TIME_RE = re.compile(r"^([01]?\d|2[0-3]):[0-5]\d$")

_SERVICE_SELECT = (
    "id,center_id,name,category,description,duration_minutes,price_min,price_max,"
    "is_active,sort_order,created_at"
)
_WORKING_HOURS_SELECT = (
    "id,center_id,day_of_week,open_time,close_time,is_closed,slot_minutes"
)


def _now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _coerce_int(value, *, field: str, default: int = 0,
                minimum: int = 0, maximum: int | None = None) -> int:
    if value is None or str(value).strip() == "":
        result = default
    else:
        try:
            result = int(float(str(value).strip()))
        except Exception:
            raise ValueError(f"{field} باید عدد باشد.") from None
    if result < minimum:
        raise ValueError(f"{field} باید حداقل {minimum} باشد.")
    if maximum is not None and result > maximum:
        raise ValueError(f"{field} باید حداکثر {maximum} باشد.")
    return result


def _coerce_flag(value, *, default: int = 1) -> int:
    if value is None:
        return default
    if isinstance(value, bool):
        return 1 if value else 0
    if isinstance(value, (int, float)):
        return 1 if int(value) else 0
    s = str(value).strip().lower()
    if s in ("1", "on", "yes", "true", "فعال"):
        return 1
    if s in ("0", "off", "no", "false", "غیرفعال"):
        return 0
    return default


def _coerce_time(value, field: str) -> str:
    s = " ".join(str(value or "").split())
    if not s:
        return ""
    if not _TIME_RE.match(s):
        raise ValueError(f"{field} باید ساعت معتبر (مثلا 09:30) باشد.")
    return s


def _clean_service(data: dict) -> dict:
    name = " ".join(str((data or {}).get("name") or "").split())
    if not name:
        raise ValueError("نام خدمت الزامی است.")
    category = " ".join(str(data.get("category") or "").split())[:100]
    description = " ".join(str(data.get("description") or "").split())[:500]
    duration_minutes = _coerce_int(
        data.get("duration_minutes"), field="مدت خدمت (دقیقه)", default=30,
        minimum=1, maximum=1440,
    )
    price_min = _coerce_int(data.get("price_min"), field="حداقل قیمت", default=0, minimum=0)
    price_max = _coerce_int(data.get("price_max"), field="حداکثر قیمت", default=0, minimum=0)
    if price_max < price_min:
        raise ValueError("حداقل قیمت نمی‌تواند از حداکثر قیمت بزرگ‌تر باشد.")
    return {
        "name": name,
        "category": category,
        "description": description,
        "duration_minutes": duration_minutes,
        "price_min": price_min,
        "price_max": price_max,
        "is_active": _coerce_flag(data.get("is_active"), default=1),
        "sort_order": _coerce_int(data.get("sort_order"), field="ترتیب نمایش", default=0, minimum=0),
    }


def _clean_working_day(data: dict) -> dict:
    raw_day = data.get("day_of_week")
    if raw_day is None:
        raw_day = data.get("weekday")
    try:
        day_of_week = int(str(raw_day).strip())
    except Exception:
        raise ValueError("روز هفته نامعتبر است.") from None
    if day_of_week < 0 or day_of_week > 6:
        raise ValueError("روز هفته باید بین ۰ (شنبه) تا ۶ (جمعه) باشد.")
    is_closed = _coerce_flag(data.get("is_closed"), default=0)
    open_time = "" if is_closed else _coerce_time(data.get("open_time"), "ساعت شروع")
    close_time = "" if is_closed else _coerce_time(data.get("close_time"), "ساعت پایان")
    if not is_closed and open_time and close_time and open_time >= close_time:
        raise ValueError("ساعت شروع باید قبل از ساعت پایان باشد.")
    slot_minutes = _coerce_int(
        data.get("slot_minutes"), field="بازه نوبت‌دهی (دقیقه)", default=30,
        minimum=5, maximum=1440,
    )
    return {
        "day_of_week": day_of_week,
        "open_time": open_time,
        "close_time": close_time,
        "is_closed": is_closed,
        "slot_minutes": slot_minutes,
    }


def get_center_services(center_id) -> list:
    """Return all services of a center, active first, then sort_order/id."""
    if not int(center_id or 0):
        return []
    with get_giso_db_conn() as conn:
        rows = conn.execute(
            f"SELECT {_SERVICE_SELECT} FROM beauty_center_services "
            "WHERE center_id=? ORDER BY is_active DESC, sort_order ASC, id ASC",
            (int(center_id),),
        ).fetchall()
    return [dict(row) for row in rows]


def add_service(center_id, data) -> int:
    """Create a service and return its new row id. Raises ValueError on invalid data."""
    center_id = int(center_id or 0)
    if not center_id:
        raise ValueError("مرکز نامعتبر است.")
    fields = _clean_service(data or {})
    stamp = _now()
    with get_giso_db_conn() as conn:
        cur = conn.execute(
            "INSERT INTO beauty_center_services "
            "(center_id,name,category,description,duration_minutes,price_min,price_max,"
            "is_active,sort_order,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (center_id, fields["name"], fields["category"], fields["description"],
             fields["duration_minutes"], fields["price_min"], fields["price_max"],
             fields["is_active"], fields["sort_order"], stamp, stamp),
        )
        conn.commit()
        return int(cur.lastrowid)


def update_service(service_id, center_id, data) -> bool:
    """Update a service owned by center_id. False when not found/not owned."""
    service_id = int(service_id or 0)
    center_id = int(center_id or 0)
    if not service_id or not center_id:
        return False
    fields = _clean_service(data or {})
    with get_giso_db_conn() as conn:
        cur = conn.execute(
            "UPDATE beauty_center_services SET name=?,category=?,description=?,"
            "duration_minutes=?,price_min=?,price_max=?,is_active=?,sort_order=?,updated_at=? "
            "WHERE id=? AND center_id=?",
            (fields["name"], fields["category"], fields["description"],
             fields["duration_minutes"], fields["price_min"], fields["price_max"],
             fields["is_active"], fields["sort_order"], _now(), service_id, center_id),
        )
        conn.commit()
        return cur.rowcount > 0


def delete_service(service_id, center_id) -> bool:
    """Soft-remove a service row owned by center_id."""
    with get_giso_db_conn() as conn:
        cur = conn.execute(
            "DELETE FROM beauty_center_services WHERE id=? AND center_id=?",
            (int(service_id or 0), int(center_id or 0)),
        )
        conn.commit()
        return cur.rowcount > 0


def get_working_hours(center_id) -> list:
    """Return working hours of a center ordered by day_of_week (0 = Saturday)."""
    if not int(center_id or 0):
        return []
    with get_giso_db_conn() as conn:
        rows = conn.execute(
            f"SELECT {_WORKING_HOURS_SELECT} FROM beauty_center_working_hours "
            "WHERE center_id=? ORDER BY day_of_week ASC",
            (int(center_id),),
        ).fetchall()
    return [dict(row) for row in rows]


def save_working_hours(center_id, hours) -> None:
    """Upsert working hours per day_of_week atomically. Raises ValueError on invalid data."""
    center_id = int(center_id or 0)
    if not center_id:
        raise ValueError("مرکز نامعتبر است.")
    cleaned = [_clean_working_day(item) for item in (hours or []) if isinstance(item, dict)]
    if not cleaned:
        raise ValueError("حداقل ساعات کاری یک روز را ثبت کنید.")
    with get_giso_db_conn() as conn:
        try:
            conn.execute("BEGIN IMMEDIATE")
            for day in cleaned:
                # Legacy weekday/is_open stay in sync (NOT NULL + UNIQUE(center_id, weekday)).
                row = conn.execute(
                    "SELECT id FROM beauty_center_working_hours "
                    "WHERE center_id=? AND day_of_week=?",
                    (center_id, day["day_of_week"]),
                ).fetchone()
                if row:
                    conn.execute(
                        "UPDATE beauty_center_working_hours SET weekday=?,is_open=?,is_closed=?,"
                        "open_time=?,close_time=?,slot_minutes=? WHERE id=?",
                        (day["day_of_week"], 0 if day["is_closed"] else 1, day["is_closed"],
                         day["open_time"], day["close_time"], day["slot_minutes"], int(row["id"])),
                    )
                else:
                    conn.execute(
                        "INSERT INTO beauty_center_working_hours "
                        "(center_id,day_of_week,weekday,is_open,is_closed,open_time,close_time,slot_minutes) "
                        "VALUES (?,?,?,?,?,?,?,?)",
                        (center_id, day["day_of_week"], day["day_of_week"], 0 if day["is_closed"] else 1,
                         day["is_closed"], day["open_time"], day["close_time"], day["slot_minutes"]),
                    )
            conn.commit()
        except Exception:
            conn.rollback()
            logger.exception("save_working_hours failed for center %s", center_id)
            raise


__all__ = [
    "get_center_services",
    "add_service",
    "update_service",
    "delete_service",
    "get_working_hours",
    "save_working_hours",
]

