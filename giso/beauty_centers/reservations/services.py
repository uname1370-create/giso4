# -*- coding: utf-8 -*-
"""Phase B reservations services: booking flow for beauty centers.

Exactly the ten documented functions:
  get_available_slots, get_calendar_month, create_reservation,
  confirm_reservation, reject_reservation, cancel_by_user,
  complete_reservation, get_center_reservations, get_user_reservations,
  get_pending_reminders

Rules
-----
- All data access goes through get_giso_db_conn() only.
- Working hours and services/prices come from the Phase A pricing module
  (giso.beauty_centers.pricing.services); nothing about hours or pricing is
  duplicated here.
- reservation_date is a Jalali date "YYYY-MM-DD" and reservation_time is "HH:MM",
  exactly as the reservation schema stores them. Working-hours day_of_week is
  Saturday-based (0 = شنبه), so every Jalali date is mapped to its weekday through
  its Gregorian equivalent (giso.phones.gregorian_to_jalali is used for verification).
- Every status change is a single guarded UPDATE: the allowed source statuses sit in
  the WHERE clause, so a repeated or concurrent call can never double-apply a
  transition (second call simply returns False).
- create_reservation re-checks the center, the user and the slot inside
  BEGIN IMMEDIATE, which is what makes double-booking impossible.
- Times are local server time (same clock as now_str()/save_working_hours()).
"""
from __future__ import annotations

import logging
import re
from datetime import date as _date, datetime, timedelta

from giso.base import _DIGIT_MAP, get_giso_db_conn, gregorian_to_jalali
from giso.beauty_centers.pricing.services import get_center_services, get_working_hours
from giso.beauty_centers.reservations.schema import RESERVATION_STATUSES

logger = logging.getLogger("giso_beauty_centers_reservations_services")

# وضعیت‌هایی که یک بازهٔ زمانی را «اشغال‌شده» می‌کنند.
_ACTIVE_STATUSES = ("pending", "confirmed")

_DEFAULT_DURATION = 30
_MINUTES_PER_DAY = 24 * 60
_REMINDER_24H_MINUTES = 24 * 60
_REMINDER_2H_MINUTES = 2 * 60

_DATE_RE = re.compile(r"^(\d{4})-(\d{1,2})-(\d{1,2})$")
_TIME_RE = re.compile(r"^([01]?\d|2[0-3]):([0-5]\d)$")

_COLUMNS = (
    "id,center_id,user_id,user_phone,user_name,service_id,service_name,"
    "service_price_min,duration_minutes,reservation_date,reservation_time,status,"
    "user_note,center_note,reject_reason,reminded_24h,reminded_2h,created_at,"
    "confirmed_at,cancelled_at"
)
_SELECT_COLS = _COLUMNS  # ردیف میانی/درون‌تراکنشی (بدون JOIN)
_SELECT_COLS_R = ", ".join(f"r.{name}" for name in _COLUMNS.split(","))

_ZWNJ = "\u200c"  # نیم‌فاصله
# Same labels as routes.BEAUTY_WEEKDAYS (built with the escape because the ZWNJ is
# stripped from literals by some editors); index 0 = شنبه.
_WEEKDAY_LABELS = ("شنبه", "یکشنبه", "دوشنبه", "سه" + _ZWNJ + "شنبه", "چهارشنبه",
                   "پنجشنبه", "جمعه")


# برچسب‌های نمایشی وضعیت‌ها؛ کلیدها با schema.RESERVATION_STATUSES هم‌راستا هستند.
_STATUS_LABELS = {
    "pending": "در انتظار تأیید",
    "confirmed": "تأیید شده",
    "completed": "انجام شده",
    "cancelled_user": "لغو توسط کاربر",
    "cancelled_center": "لغو توسط مرکز",
}
# اگر روزی وضعیت تازه‌ای به schema اضافه شود و برچسبش جا بماند، در لاگ دیده می‌شود.
_MISSING_STATUS_LABELS = [code for code in RESERVATION_STATUSES if code not in _STATUS_LABELS]
if _MISSING_STATUS_LABELS:
    logger.warning("reservation statuses without a label: %s", ",".join(_MISSING_STATUS_LABELS))
_CENTER_JOIN = "LEFT JOIN beauty_centers c ON c.id=r.center_id"
_CENTER_FIELDS = (
    "c.name AS center_name,c.slug AS center_slug,"
    "COALESCE(NULLIF(c.business_phone,''),c.salon_phone,'') AS center_phone"
)


def _now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _to_int(value, default: int = 0) -> int:
    """Coerce anything to int without raising (read paths stay fault tolerant)."""
    try:
        text = str(value).strip().translate(_DIGIT_MAP)
        return int(float(text)) if text else default
    except (TypeError, ValueError):
        return default


def _clean_text(value, limit: int) -> str:
    return " ".join(str(value or "").split())[:limit]


# ---------------------------------------------------------------------------
# تاریخ/ساعت (شمسی برای ورودیها، میلادی فقط برای محاسبهٔ روز هفته)
# ---------------------------------------------------------------------------

def _normalize_date(value) -> str:
    """Accept 1404-05-20, 1404/5/20 or Persian digits → 'YYYY-MM-DD'. '' if invalid."""
    text = str(value or "").strip().translate(_DIGIT_MAP).replace("/", "-").replace(".", "-")
    match = _DATE_RE.match(text)
    if not match:
        return ""
    year, month, day = (int(part) for part in match.groups())
    if year < 1300 or year > 1500 or not 1 <= month <= 12 or not 1 <= day <= 31:
        return ""
    return f"{year:04d}-{month:02d}-{day:02d}"


def _normalize_time(value) -> str:
    """Accept 9:30, 09:30 or Persian digits → 'HH:MM'. '' if invalid."""
    text = str(value or "").strip().translate(_DIGIT_MAP)
    match = _TIME_RE.match(text)
    if not match:
        return ""
    return f"{int(match.group(1)):02d}:{int(match.group(2)):02d}"


def _jalali_parts(date_str: str) -> tuple | None:
    normalized = _normalize_date(date_str)
    if not normalized:
        return None
    return tuple(int(part) for part in normalized.split("-"))


def _today_jalali() -> str:
    gy, gm, gd = datetime.now().date().timetuple()[:3]
    jy, jm, jd = gregorian_to_jalali(gy, gm, gd)
    return f"{jy:04d}-{jm:02d}-{jd:02d}"


def _jalali_to_ordinal(date_str: str) -> int | None:
    """Jalali YYYY-MM-DD -> Gregorian ordinal, by bisection over 2000-2100.

    gregorian_to_jalali is monotone, so bisection lands exactly on the target
    without a leap-year table and without stepping day by day, and costs about
    16 lookups no matter how far away the date is.
    """
    target = _jalali_parts(date_str)
    if target is None:
        return None
    try:
        low = _date(2000, 1, 1).toordinal()
        high = _date(2100, 1, 1).toordinal()
        while low <= high:
            mid = (low + high) // 2
            day = _date.fromordinal(mid)
            current = gregorian_to_jalali(day.year, day.month, day.day)
            if current == target:
                return mid
            if current < target:
                low = mid + 1
            else:
                high = mid - 1
    except Exception:
        return None
    return None


def _jalali_to_datetime(date_str: str, time_str: str = "00:00") -> datetime | None:
    """Jalali YYYY-MM-DD + HH:MM -> naive datetime on the local server clock."""
    ordinal = _jalali_to_ordinal(date_str)
    if ordinal is None:
        return None
    time_str = _normalize_time(time_str) or "00:00"
    return datetime.fromordinal(ordinal).replace(hour=int(time_str[:2]), minute=int(time_str[3:5]))


def _jalali_day_of_week(date_str: str) -> int:
    """Jalali YYYY-MM-DD -> Saturday-based day_of_week (0 = shanbe) or -1."""
    ordinal = _jalali_to_ordinal(date_str)
    return -1 if ordinal is None else (_date.fromordinal(ordinal).weekday() + 2) % 7


def _date_weekday_label(date_str: str) -> str:
    index = _jalali_day_of_week(date_str)
    return _WEEKDAY_LABELS[index] if 0 <= index < 7 else ""


def _minutes_of(time_str: str) -> int:
    return int(time_str[:2]) * 60 + int(time_str[3:5])


def _hhmm(minutes: int) -> str:
    return f"{minutes // 60:02d}:{minutes % 60:02d}"


def _slot_minutes(day: dict) -> int:
    """Slot step of a day: explicit slot_minutes, else the service duration, else 30."""
    value = _to_int((day or {}).get("slot_minutes"))
    return value if value > 0 else _DEFAULT_DURATION


# ---------------------------------------------------------------------------
# تقویم و بازه‌های آزاد
# ---------------------------------------------------------------------------

def get_available_slots(center_id, date, service_id=0) -> dict:
    """Free booking slots of one center/day for one service.

    date is Jalali 'YYYY-MM-DD' (Persian digits and '/' are accepted) and slots are
    absolute clock times 'HH:MM' — per-slot start times, whatever the slot step is.

    Returns a dict so a template can render day state without a second call:
      {"date", "weekday", "day_of_week", "is_closed", "is_working_day",
       "duration_minutes", "slot_minutes", "service_id", "service_name",
       "service_price_min", "service_duration_minutes", "slots": ["09:00", ...]}
    Every missing/invalid input degrades to an empty "slots" list, never to an error.
    """
    center_id = _to_int(center_id)
    date = _normalize_date(date)
    service = _service_of(center_id, service_id)
    duration = _to_int((service or {}).get("duration_minutes")) or _DEFAULT_DURATION
    result = {
        "date": date,
        "weekday": _date_weekday_label(date),
        "day_of_week": _jalali_day_of_week(date),
        "is_closed": True,
        "is_working_day": False,
        "duration_minutes": duration,
        "slot_minutes": duration,
        "service_id": _to_int((service or {}).get("id")),
        "service_name": str((service or {}).get("name") or ""),
        "service_price_min": _to_int((service or {}).get("price_min")),
        "service_duration_minutes": _to_int((service or {}).get("duration_minutes")),
        "slots": [],
    }
    if not center_id or not date or not service:
        return result
    day = _working_day(center_id, date)
    if not day:
        return result
    with get_giso_db_conn() as conn:
        bookings = _active_bookings(conn, center_id, date)
    result["is_closed"] = False
    result["is_working_day"] = True
    result["slot_minutes"] = _slot_minutes(day)
    result["open_time"] = _normalize_time(day.get("open_time"))
    result["close_time"] = _normalize_time(day.get("close_time"))
    result["slots"] = _build_slots(day, bookings, duration, date)
    return result


def get_calendar_month(center_id, year, month) -> list:
    """Day-by-day view of one Jalali month for a center (all services, generic duration).

    Returns one dict per day of the month:
      {"date", "day", "weekday", "day_of_week", "is_closed", "is_past", "is_today",
       "slot_minutes", "open_time", "close_time", "total", "available"}
    total = active (pending/confirmed) reservations of that day.
    available = how many generic free slots the day still has (0 when closed/past).
    """
    center_id = _to_int(center_id)
    year, month = _to_int(year), _to_int(month)
    if not center_id or not 1 <= month <= 12 or year < 1300 or year > 1500:
        return []
    first = _jalali_to_datetime(f"{year:04d}-{month:02d}-01")
    if first is None:
        return []
    hours = {_to_int(row.get("day_of_week"), -1): row for row in get_working_hours(center_id)}
    today = _today_jalali()
    days, cursor = [], first
    while len(days) < 31:
        gy, gm, gd = gregorian_to_jalali(cursor.year, cursor.month, cursor.day)
        if gm != month or gy != year:
            break
        date_str = f"{gy:04d}-{gm:02d}-{gd:02d}"
        index = (cursor.weekday() + 2) % 7  # Sat=0 … Fri=6 (شنبه = 0)
        day = hours.get(index)
        is_closed = day is None or _to_int(day.get("is_closed"), 1) == 1
        days.append({
            "date": date_str,
            "day": gd,
            "weekday": _WEEKDAY_LABELS[index],
            "day_of_week": index,
            "is_closed": bool(is_closed),
            "is_past": date_str < today,
            "is_today": date_str == today,
            "slot_minutes": _slot_minutes(day),
            "open_time": str((day or {}).get("open_time") or ""),
            "close_time": str((day or {}).get("close_time") or ""),
            "total": 0,
            "available": 0,
        })
        cursor += timedelta(days=1)
    if not days:
        return []
    counts: dict[str, list] = {item["date"]: [] for item in days}
    with get_giso_db_conn() as conn:
        rows = conn.execute(
            f"SELECT {_SELECT_COLS} FROM beauty_center_reservations "
            "WHERE center_id=? AND reservation_date>=? AND reservation_date<=? "
            "AND status IN (?,?) ORDER BY reservation_time ASC",
            (center_id, days[0]["date"], days[-1]["date"],
             _ACTIVE_STATUSES[0], _ACTIVE_STATUSES[1]),
        ).fetchall()
    for row in rows:
        record = dict(row)
        counts.get(str(record.get("reservation_date")), []).append(record)
    for item in days:
        bookings = counts.get(item["date"], [])
        item["total"] = len(bookings)
        if not item["is_closed"] and not item["is_past"]:
            day = hours.get(item["day_of_week"])
            item["available"] = len(_build_slots(day, bookings, _DEFAULT_DURATION, item["date"]))
    return days


# ---------------------------------------------------------------------------
# ثبت رزرو
# ---------------------------------------------------------------------------

def create_reservation(center_id, user_id, user_phone="", user_name="", service_id=0,
                       reservation_date="", reservation_time="", user_note="",
                       duration_minutes=None) -> int:
    """Book a slot and return the new reservation id (0 when it could not be booked).

    Snapshot rule: center/service name, price and duration are copied into the row, so
    a later price or service edit never rewrites an existing reservation.

    The insert runs inside BEGIN IMMEDIATE and re-checks the center, the user, the
    working day and the slot inside that same transaction — two users asking for the
    same slot at the same moment cannot both succeed (the loser gets 0).

    Because a "no" is reported as 0, callers should re-read get_available_slots() to
    explain a failed attempt (closed day, taken slot, invalid service, missing user).
    """
    center_id, user_id = _to_int(center_id), _to_int(user_id)
    service_id = _to_int(service_id)
    reservation_date = _normalize_date(reservation_date)
    reservation_time = _normalize_time(reservation_time)
    if not center_id or not user_id:
        logger.warning("create_reservation: invalid center_id/user_id (%s/%s)", center_id, user_id)
        return 0
    if not reservation_date or not reservation_time:
        logger.warning("create_reservation: invalid date/time (%s/%s)",
                       reservation_date, reservation_time)
        return 0
    service = _service_of(center_id, service_id)
    if not service:
        logger.warning("create_reservation: no active service %s for center %s",
                       service_id, center_id)
        return 0
    day = _working_day(center_id, reservation_date)
    if not day:
        logger.info("create_reservation: center %s is closed on %s", center_id, reservation_date)
        return 0
    duration = _to_int(duration_minutes) or _to_int(service.get("duration_minutes")) or _DEFAULT_DURATION
    duration = max(1, duration)
    open_time = _normalize_time(day.get("open_time"))
    close_time = _normalize_time(day.get("close_time"))
    if not open_time or not close_time:
        return 0
    start = _minutes_of(reservation_time)
    if start < _minutes_of(open_time) or start + duration > _minutes_of(close_time):
        logger.info("create_reservation: %s %s is outside working hours (%s-%s)",
                    reservation_date, reservation_time, open_time, close_time)
        return 0
    with get_giso_db_conn() as conn:
        try:
            conn.execute("BEGIN IMMEDIATE")
            center = _get_center(conn, center_id)
            if not _center_is_public(center):
                conn.rollback()
                logger.info("create_reservation: center %s is not published/active", center_id)
                return 0
            user = conn.execute(
                "SELECT id,phone,name FROM giso_web_auth WHERE id=?", (user_id,)
            ).fetchone()
            if not user:
                conn.rollback()
                logger.info("create_reservation: unknown user %s", user_id)
                return 0
            if not _is_available(_active_bookings(conn, center_id, reservation_date),
                                 reservation_time, duration):
                conn.rollback()
                logger.info("create_reservation: slot %s %s taken at center %s",
                            reservation_date, reservation_time, center_id)
                return 0
            cursor = conn.execute(
                "INSERT INTO beauty_center_reservations "
                "(center_id,user_id,user_phone,user_name,service_id,service_name,"
                "service_price_min,duration_minutes,reservation_date,reservation_time,"
                "status,user_note,center_note,reject_reason,reminded_24h,reminded_2h,"
                "created_at,confirmed_at,cancelled_at) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,'pending',?,'','',0,0,?,'','')",
                (center_id, user_id, _clean_text(user_phone or user["phone"], 20),
                 _clean_text(user_name or user["name"], 100), _to_int(service.get("id")),
                 _clean_text(service.get("name"), 200), _to_int(service.get("price_min")),
                 duration, reservation_date, reservation_time,
                 _clean_text(user_note, 500), _now()),
            )
            reservation_id = int(cursor.lastrowid or 0)
            conn.commit()
            return reservation_id
        except Exception:
            conn.rollback()
            logger.exception("create_reservation failed for center %s user %s", center_id, user_id)
            return 0


# ---------------------------------------------------------------------------
# تغییر وضعیت (هر تغییر یک UPDATE با شرط وضعیت فعلی = بدون اعمال مضاعف)
# ---------------------------------------------------------------------------

def _transition(reservation_id, center_id, sources, new_status, *, reason="",
                stamp_column="", reason_column="") -> bool:
    """Guarded status change; True only when this call actually flipped the row."""
    reservation_id, center_id = _to_int(reservation_id), _to_int(center_id)
    if not reservation_id or not center_id or not sources:
        return False
    sets, params = ["status=?"], [new_status]
    if stamp_column:
        sets.append(f"{stamp_column}=?")
        params.append(_now())
    if reason_column:
        sets.append(f"{reason_column}=?")
        params.append(_clean_text(reason, 500))
    params.extend([reservation_id, center_id, *sources])
    sql = (
        f"UPDATE beauty_center_reservations SET {', '.join(sets)} "
        "WHERE id=? AND center_id=? AND status IN ("
        + ",".join("?" * len(sources)) + ")"
    )
    with get_giso_db_conn() as conn:
        try:
            cursor = conn.execute(sql, tuple(params))
            changed = cursor.rowcount > 0
            conn.commit()
        except Exception:
            conn.rollback()
            logger.exception("status change to %s failed for reservation %s",
                             new_status, reservation_id)
            return False
    if not changed:
        logger.info("reservation %s of center %s: %s not allowed from its current status",
                    reservation_id, center_id, new_status)
    return changed


def confirm_reservation(reservation_id, center_id) -> bool:
    """pending → confirmed, stamping confirmed_at. Only the owning center can confirm."""
    return _transition(reservation_id, center_id, ("pending",), "confirmed",
                       stamp_column="confirmed_at")


def reject_reservation(reservation_id, center_id, reason="") -> bool:
    """pending → cancelled_center, storing the center's reason. Owning center only."""
    return _transition(reservation_id, center_id, ("pending",), "cancelled_center",
                       reason=reason, reason_column="reject_reason",
                       stamp_column="cancelled_at")


def complete_reservation(reservation_id, center_id) -> bool:
    """confirmed → completed. A pending booking must be confirmed first; center only."""
    return _transition(reservation_id, center_id, ("confirmed",), "completed")


def cancel_by_user(reservation_id, user_id) -> bool:
    """pending|confirmed → cancelled_user. Only the owner can cancel; confirmed_at kept."""
    reservation_id, user_id = _to_int(reservation_id), _to_int(user_id)
    if not reservation_id or not user_id:
        return False
    with get_giso_db_conn() as conn:
        try:
            cursor = conn.execute(
                "UPDATE beauty_center_reservations SET status='cancelled_user',cancelled_at=? "
                "WHERE id=? AND user_id=? AND status IN ('pending','confirmed')",
                (_now(), reservation_id, user_id),
            )
            changed = cursor.rowcount > 0
            conn.commit()
        except Exception:
            conn.rollback()
            logger.exception("cancel_by_user failed for reservation %s", reservation_id)
            return False
    if not changed:
        logger.info("reservation %s of user %s cannot be cancelled in its current status",
                    reservation_id, user_id)
    return changed


# ---------------------------------------------------------------------------
# خواندن رزروها
# ---------------------------------------------------------------------------

def _with_derived(row) -> dict:
    """Row → dict plus status_label and starts_at (local timestamp, '' if unparsable)."""
    record = dict(row)
    record["status_label"] = _STATUS_LABELS.get(str(record.get("status")), str(record.get("status") or ""))
    moment = _jalali_to_datetime(record.get("reservation_date"), record.get("reservation_time"))
    record["starts_at"] = moment.strftime("%Y-%m-%d %H:%M:%S") if moment else ""
    return record


def get_center_reservations(center_id, date=None, status=None) -> list:
    """Reservations of one center, newest date/time first (limit 500).

    Every center booking, whatever its status. Passing a Jalali `date` restricts the
    list to that day; passing a known `status` restricts it to that status. Anything
    blank or unrecognised simply means "no such filter" rather than an error.
    An empty center_id returns an empty list.
    """
    center_id = _to_int(center_id)
    if not center_id:
        return []
    where, params = ["r.center_id=?"], [center_id]
    date = _normalize_date(date)
    if date:
        where.append("r.reservation_date=?")
        params.append(date)
    status = str(status or "").strip()
    if status in RESERVATION_STATUSES:
        where.append("r.status=?")
        params.append(status)
    sql = (
        f"SELECT {_SELECT_COLS_R},{_CENTER_FIELDS} FROM beauty_center_reservations r "
        f"{_CENTER_JOIN} WHERE {' AND '.join(where)} "
        "ORDER BY r.reservation_date DESC, r.reservation_time DESC, r.id DESC LIMIT 500"
    )
    with get_giso_db_conn() as conn:
        rows = conn.execute(sql, tuple(params)).fetchall()
    return [_with_derived(row) for row in rows]


def get_user_reservations(user_id) -> list:
    """Reservations of one user, newest created first (limit 200), with center info."""
    user_id = _to_int(user_id)
    if not user_id:
        return []
    sql = (
        f"SELECT {_SELECT_COLS_R},{_CENTER_FIELDS} FROM beauty_center_reservations r "
        f"{_CENTER_JOIN} WHERE r.user_id=? ORDER BY r.created_at DESC, r.id DESC LIMIT 200"
    )
    with get_giso_db_conn() as conn:
        rows = conn.execute(sql, (user_id,)).fetchall()
    return [_with_derived(row) for row in rows]


def _reminder_rows(conn) -> list:
    """Confirmed bookings with at least one reminder still unsent (bounded, oldest first)."""
    rows = conn.execute(
        f"SELECT {_SELECT_COLS_R},{_CENTER_FIELDS} FROM beauty_center_reservations r "
        f"{_CENTER_JOIN} WHERE r.status='confirmed' AND (r.reminded_24h=0 OR r.reminded_2h=0) "
        "ORDER BY r.reservation_date ASC, r.reservation_time ASC LIMIT 500"
    ).fetchall()
    return [dict(row) for row in rows]


def _stamp_reminder(conn, reservation_id, kind: str) -> bool:
    """Mark a reminder as sent; True only for the caller that wins the race.

    The 2h reminder also closes the 24h slot, so a late booking is never told twice.
    """
    if kind == "2h":
        cursor = conn.execute(
            "UPDATE beauty_center_reservations SET reminded_2h=1,reminded_24h=1 "
            "WHERE id=? AND reminded_2h=0",
            (reservation_id,),
        )
    else:
        cursor = conn.execute(
            "UPDATE beauty_center_reservations SET reminded_24h=1 "
            "WHERE id=? AND reminded_24h=0",
            (reservation_id,),
        )
    return cursor.rowcount > 0


def get_pending_reminders() -> list:
    """Confirmed reservations whose reminder is due right now (one row per booking).

    Due means: start time ≤ now + 24h for the 24h reminder and ≤ now + 2h for the 2h
    reminder, with a 10-minute grace window after the start so a restart does not lose
    the message. The 2h reminder wins when both are due, so a booking made a couple of
    hours ahead is announced once, not twice.

    Flags are claimed with a guarded UPDATE before the row is returned, so a second
    call (or a second process) gets an empty list instead of sending duplicates.
    Rows carry "reminder": "24h"|"2h", plus starts_at and minutes_until.
    """
    now = datetime.now()
    result = []
    with get_giso_db_conn() as conn:
        try:
            for row in _reminder_rows(conn):
                moment = _jalali_to_datetime(row.get("reservation_date"),
                                             row.get("reservation_time"))
                if moment is None:
                    continue
                minutes_until = int((moment - now).total_seconds() // 60)
                if minutes_until < -10 or minutes_until > _REMINDER_24H_MINUTES:
                    continue
                kind = "2h" if (minutes_until <= _REMINDER_2H_MINUTES and not _to_int(row.get("reminded_2h"))) else "24h"
                if kind == "24h" and _to_int(row.get("reminded_24h")):
                    continue
                if not _stamp_reminder(conn, _to_int(row.get("id")), kind):
                    continue
                record = _with_derived(row)
                record["reminder"] = kind
                record["minutes_until"] = minutes_until
                result.append(record)
            conn.commit()
        except Exception:
            conn.rollback()
            logger.exception("get_pending_reminders failed")
            return []
    return result


# ---------------------------------------------------------------------------
# خواندن داده‌های پایه: مرکز، خدمت، ساعات کاری، رزروهای روز
# ---------------------------------------------------------------------------

def _get_center(conn, center_id) -> dict | None:
    row = conn.execute(
        "SELECT id,owner_user_id,name,city,status,is_active FROM beauty_centers WHERE id=?",
        (center_id,),
    ).fetchone()
    return dict(row) if row else None


def _center_is_public(center: dict) -> bool:
    return bool(center) and str(center.get("status")) == "published" and _to_int(center.get("is_active")) == 1


def _service_of(center_id, service_id) -> dict | None:
    """Active service of this center; an empty service_id picks the first (sort_order)."""
    services = [
        item for item in (get_center_services(center_id) or [])
        if _to_int(item.get("is_active"), 1)
    ]
    if not services:
        return None
    wanted = _to_int(service_id)
    if not wanted:
        return services[0]
    for item in services:
        if _to_int(item.get("id")) == wanted:
            return item
    return None


def _working_day(center_id, date_str: str) -> dict | None:
    """Working-hours row of the Jalali date's weekday, or None when closed/unset."""
    index = _jalali_day_of_week(date_str)
    if index < 0:
        return None
    for row in get_working_hours(center_id):
        if _to_int(row.get("day_of_week"), -1) == index:
            if _to_int(row.get("is_closed"), 1):
                return None
            return row
    return None


def _active_bookings(conn, center_id, date_str: str) -> list:
    """Active (pending/confirmed) reservations of one center/date, ordered by time."""
    rows = conn.execute(
        f"SELECT {_SELECT_COLS} FROM beauty_center_reservations "
        "WHERE center_id=? AND reservation_date=? AND status IN (?,?) "
        "ORDER BY reservation_time ASC",
        (center_id, date_str, _ACTIVE_STATUSES[0], _ACTIVE_STATUSES[1]),
    ).fetchall()
    return [dict(row) for row in rows]


def _is_available(bookings, time_str: str, duration: int) -> bool:
    """True when [start, start+duration) touches no active reservation."""
    if not time_str:
        return False
    start = _minutes_of(time_str)
    end = start + duration
    for booking in bookings:
        other = _normalize_time(booking.get("reservation_time"))
        if not other:
            continue
        other_start = _minutes_of(other)
        other_end = other_start + max(_DEFAULT_DURATION, _to_int(booking.get("duration_minutes")))
        if start < other_end and other_start < end:  # نیمه‌باز = دقیقاً چسبیده مجاز است
            return False
    return True


def _build_slots(day, bookings, duration: int, date_str: str = "") -> list:
    """Free HH:MM slots of one working day, skipping overlaps and (today) past hours."""
    open_time = _normalize_time((day or {}).get("open_time"))
    close_time = _normalize_time((day or {}).get("close_time"))
    if not open_time or not close_time:
        return []
    cursor = _minutes_of(open_time)
    last_start = _minutes_of(close_time) - max(1, duration)
    if last_start < cursor:
        return []
    step = _slot_minutes(day)
    today = date_str == _today_jalali()
    now_minutes = datetime.now().hour * 60 + datetime.now().minute
    slots = []
    while cursor <= last_start:
        label = _hhmm(cursor)
        if not (today and cursor <= now_minutes) and _is_available(bookings, label, duration):
            slots.append(label)
        cursor += step
    return slots
__all__ = [
    "get_available_slots",
    "get_calendar_month",
    "create_reservation",
    "confirm_reservation",
    "reject_reservation",
    "cancel_by_user",
    "complete_reservation",
    "get_center_reservations",
    "get_user_reservations",
    "get_pending_reminders",
]
