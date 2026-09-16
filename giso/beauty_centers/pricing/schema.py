# -*- coding: utf-8 -*-
"""Phase A pricing schema: additive-only migrations for beauty center services and working hours.

Rules:
- NEVER recreate or drop tables.
- Only add missing columns (SQLite has no ADD COLUMN IF NOT EXISTS -> PRAGMA check first).
- All access via get_giso_db_conn().
"""
import logging

from giso.base import get_giso_db_conn

logger = logging.getLogger("giso_beauty_centers_pricing_schema")

SERVICES_COLUMNS = {
    "id": "INTEGER PRIMARY KEY AUTOINCREMENT",
    "center_id": "INTEGER NOT NULL",
    "name": "TEXT NOT NULL",
    "category": "TEXT DEFAULT ''",
    "description": "TEXT DEFAULT ''",
    "duration_minutes": "INTEGER NOT NULL DEFAULT 30",
    "price_min": "INTEGER NOT NULL DEFAULT 0",
    "price_max": "INTEGER NOT NULL DEFAULT 0",
    "is_active": "INTEGER NOT NULL DEFAULT 1",
    "sort_order": "INTEGER NOT NULL DEFAULT 0",
    "created_at": "TEXT DEFAULT ''",
}

WORKING_HOURS_COLUMNS = {
    "id": "INTEGER PRIMARY KEY AUTOINCREMENT",
    "center_id": "INTEGER NOT NULL",
    # SQLite refuses «ADD COLUMN ... NOT NULL» without a default even on an empty
    # table, so day_of_week carries DEFAULT 0 to keep the migration additive.
    "day_of_week": "INTEGER NOT NULL DEFAULT 0",  # 0 = Saturday
    "open_time": "TEXT DEFAULT ''",
    "close_time": "TEXT DEFAULT ''",
    "is_closed": "INTEGER NOT NULL DEFAULT 0",
    "slot_minutes": "INTEGER NOT NULL DEFAULT 30",
}


def _columns_of(conn, table: str) -> set[str]:
    return {row[1] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()}


def _ensure_table(conn, table: str, columns: dict[str, str]):
    """Create table only if absent; otherwise add missing columns only."""
    exists = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table,)
    ).fetchone()
    if not exists:
        cols = ",\n  ".join(f"{name} {ddl}" for name, ddl in columns.items())
        conn.execute(f"CREATE TABLE IF NOT EXISTS {table} (\n  {cols}\n)")
        logger.info("pricing table created: %s", table)
        return
    existing = _columns_of(conn, table)
    added = []
    for name, ddl in columns.items():
        if name not in existing and name != "id":
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {name} {ddl}")
            added.append(name)
    if added:
        logger.info("pricing table %s: added columns %s", table, ", ".join(added))


def migrate_pricing_tables():
    """Idempotent additive schema for Phase A pricing."""
    try:
        with get_giso_db_conn() as conn:
            _ensure_table(conn, "beauty_center_services", SERVICES_COLUMNS)
            _ensure_table(conn, "beauty_center_working_hours", WORKING_HOURS_COLUMNS)
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_beauty_center_services_center "
                "ON beauty_center_services(center_id,is_active,sort_order)"
            )
            try:
                conn.execute(
                    "CREATE UNIQUE INDEX IF NOT EXISTS idx_beauty_working_hours_center_day "
                    "ON beauty_center_working_hours(center_id,day_of_week)"
                )
            except Exception:
                logger.warning("working hours unique index skipped (likely duplicate rows); data preserved")
            conn.commit()
    except Exception as exc:
        logger.exception("pricing schema migration failed: %s", exc)
        raise


__all__ = ["migrate_pricing_tables"]
