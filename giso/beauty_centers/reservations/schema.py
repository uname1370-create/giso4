# -*- coding: utf-8 -*-
"""Phase B reservations schema: additive-only migration for beauty center reservations.

Rules:
- NEVER recreate or drop tables.
- Create the table only when absent; otherwise add missing columns only
  (SQLite has no ADD COLUMN IF NOT EXISTS -> PRAGMA check first).
- Every NOT NULL column carries a DEFAULT: SQLite refuses «ADD COLUMN ... NOT NULL»
  without a default even on an empty table, so the migration stays additive.
- All access via get_giso_db_conn().
- service_id / service_name / service_price_min / duration_minutes are snapshots of
  the service at booking time, deliberately WITHOUT a foreign key to
  beauty_center_services so that later edits or deletions of a service never break
  or rewrite past reservations.
"""
import logging

from giso.base import get_giso_db_conn

logger = logging.getLogger("giso_beauty_centers_reservations_schema")

RESERVATIONS_TABLE = "beauty_center_reservations"

# وضعیت‌های مجاز رزرو. اعتبارسنجی در سطح کد انجام می‌شود (نه CHECK) تا افزودن
# وضعیت‌های آینده بدون مهاجرت مخرب روی جدول موجود ممکن باشد.
RESERVATION_STATUSES = (
    "pending",
    "confirmed",
    "completed",
    "cancelled_user",
    "cancelled_center",
)

RESERVATIONS_COLUMNS = {
    "id": "INTEGER PRIMARY KEY AUTOINCREMENT",
    # DEFAULT 0 فقط برای اینکه مسیر افزودن ستون روی جدولِ دارای ردیف هم کار کند
    # (SQLite: ADD COLUMN NOT NULL بدون DEFAULT رد می‌شود). مقدار واقعی همیشه از
    # کد ارسال می‌شود و قید FOREIGN KEY مقدار جعلی ۰ را رد می‌کند.
    "center_id": "INTEGER NOT NULL DEFAULT 0",
    "user_id": "INTEGER NOT NULL DEFAULT 0",
    "user_phone": "TEXT DEFAULT ''",
    "user_name": "TEXT DEFAULT ''",
    "service_id": "INTEGER NOT NULL DEFAULT 0",
    "service_name": "TEXT NOT NULL DEFAULT ''",
    "service_price_min": "INTEGER NOT NULL DEFAULT 0",
    "duration_minutes": "INTEGER NOT NULL DEFAULT 30",
    "reservation_date": "TEXT NOT NULL DEFAULT ''",  # تاریخ شمسی YYYY-MM-DD
    "reservation_time": "TEXT NOT NULL DEFAULT ''",  # ساعت HH:MM
    "status": "TEXT NOT NULL DEFAULT 'pending'",
    "user_note": "TEXT DEFAULT ''",
    "center_note": "TEXT DEFAULT ''",
    "reject_reason": "TEXT DEFAULT ''",
    "reminded_24h": "INTEGER NOT NULL DEFAULT 0",
    "reminded_2h": "INTEGER NOT NULL DEFAULT 0",
    "created_at": "TEXT DEFAULT ''",
    "confirmed_at": "TEXT DEFAULT ''",
    "cancelled_at": "TEXT DEFAULT ''",
}

RESERVATIONS_CONSTRAINTS = (
    "FOREIGN KEY(center_id) REFERENCES beauty_centers(id)",
    "FOREIGN KEY(user_id) REFERENCES giso_web_auth(id)",
)


def _columns_of(conn, table: str) -> set[str]:
    return {row[1] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()}


def _ensure_table(conn, table: str, columns: dict[str, str], constraints: tuple = ()):
    """Create table only if absent; otherwise add missing columns only."""
    exists = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table,)
    ).fetchone()
    if not exists:
        parts = [f"{name} {ddl}" for name, ddl in columns.items()]
        parts.extend(constraints)
        cols = ",\n  ".join(parts)
        conn.execute(f"CREATE TABLE IF NOT EXISTS {table} (\n  {cols}\n)")
        logger.info("reservations table created: %s", table)
        return
    existing = _columns_of(conn, table)
    added = []
    for name, ddl in columns.items():
        if name not in existing and name != "id":
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {name} {ddl}")
            added.append(name)
    if added:
        logger.info("reservations table %s: added columns %s", table, ", ".join(added))


def migrate_reservation_tables():
    """Idempotent additive schema for Phase B reservations."""
    try:
        with get_giso_db_conn() as conn:
            _ensure_table(
                conn, RESERVATIONS_TABLE, RESERVATIONS_COLUMNS, RESERVATIONS_CONSTRAINTS
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_beauty_reservations_center "
                "ON beauty_center_reservations(center_id,reservation_date,reservation_time)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_beauty_reservations_user "
                "ON beauty_center_reservations(user_id,created_at)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_beauty_reservations_status "
                "ON beauty_center_reservations(status,reservation_date)"
            )
            conn.commit()
    except Exception as exc:
        logger.exception("reservations schema migration failed: %s", exc)
        raise


__all__ = ["migrate_reservation_tables", "RESERVATION_STATUSES"]
