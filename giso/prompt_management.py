# -*- coding: utf-8 -*-
"""
Phase 24 S2: Prompt Management — Versioning, Active Selection, Rollback
DB-based prompt storage with version tracking.
"""
import json
import logging
from datetime import datetime

logger = logging.getLogger("giso_prompt_mgmt")

PROMPT_MGMT_SCHEMA = """
CREATE TABLE IF NOT EXISTS prompt_versions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    prompt_name TEXT NOT NULL,
    version INTEGER NOT NULL DEFAULT 1,
    content TEXT NOT NULL DEFAULT '',
    is_active INTEGER DEFAULT 0,
    notes TEXT DEFAULT '',
    created_at TEXT DEFAULT '',
    created_by TEXT DEFAULT 'system'
);
CREATE INDEX IF NOT EXISTS idx_prompt_name ON prompt_versions(prompt_name);
CREATE INDEX IF NOT EXISTS idx_prompt_active ON prompt_versions(prompt_name, is_active);
CREATE UNIQUE INDEX IF NOT EXISTS ux_prompt_name_version ON prompt_versions(prompt_name, version);
"""


def init_prompt_tables(conn):
    """Initialize prompt versioning tables."""
    try:
        conn.executescript(PROMPT_MGMT_SCHEMA)
        conn.commit()
    except Exception as e:
        logger.error(f"init_prompt_tables: {e}")


def get_active_prompt(prompt_name: str) -> str:
    """Get the active version of a prompt. Falls back to file if no DB version."""
    try:
        from giso.base import get_giso_db_conn
        with get_giso_db_conn() as conn:
            row = conn.execute(
                "SELECT content FROM prompt_versions WHERE prompt_name=? AND is_active=1 ORDER BY version DESC LIMIT 1",
                (prompt_name,)
            ).fetchone()
            if row and row[0]:
                return row[0]
    except Exception as e:
        logger.debug(f"get_active_prompt DB fallback: {e}")
    # Fallback to file
    try:
        import os
        from giso.config import Config
        path = os.path.join(Config.GISO_DIR, "prompts", prompt_name)
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    except Exception as e:
        logger.error(f"get_active_prompt file: {e}")
        return ""


def save_prompt_version(prompt_name: str, content: str, notes: str = "", created_by: str = "admin") -> dict:
    """Save a new version of a prompt and make it active."""
    try:
        from giso.base import get_giso_db_conn
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        with get_giso_db_conn() as conn:
            max_ver = conn.execute(
                "SELECT MAX(version) FROM prompt_versions WHERE prompt_name=?", (prompt_name,)
            ).fetchone()
            next_ver = (max_ver[0] or 0) + 1
            conn.execute("UPDATE prompt_versions SET is_active=0 WHERE prompt_name=?", (prompt_name,))
            conn.execute(
                "INSERT INTO prompt_versions (prompt_name, version, content, is_active, notes, created_at, created_by) VALUES (?,?,?,?,?,?,?)",
                (prompt_name, next_ver, content, 1, notes, now, created_by)
            )
            conn.commit()
            return {"ok": True, "version": next_ver}
    except Exception as e:
        logger.error(f"save_prompt_version: {e}")
        return {"ok": False, "error": str(e)}


def rollback_prompt(prompt_name: str, target_version: int) -> dict:
    """Rollback to a specific version."""
    try:
        from giso.base import get_giso_db_conn
        with get_giso_db_conn() as conn:
            row = conn.execute(
                "SELECT id FROM prompt_versions WHERE prompt_name=? AND version=?",
                (prompt_name, target_version)
            ).fetchone()
            if not row:
                return {"ok": False, "error": f"Version {target_version} not found"}
            conn.execute("UPDATE prompt_versions SET is_active=0 WHERE prompt_name=?", (prompt_name,))
            conn.execute("UPDATE prompt_versions SET is_active=1 WHERE prompt_name=? AND version=?",
                         (prompt_name, target_version))
            conn.commit()
            return {"ok": True, "version": target_version}
    except Exception as e:
        logger.error(f"rollback_prompt: {e}")
        return {"ok": False, "error": str(e)}


def list_prompt_versions(prompt_name: str) -> list:
    """List all versions of a prompt."""
    try:
        from giso.base import get_giso_db_conn
        with get_giso_db_conn() as conn:
            rows = conn.execute(
                "SELECT version, is_active, notes, created_at, created_by FROM prompt_versions WHERE prompt_name=? ORDER BY version DESC",
                (prompt_name,)
            ).fetchall()
            return [
                {"version": r[0], "is_active": bool(r[1]), "notes": r[2], "created_at": r[3], "created_by": r[4]}
                for r in rows
            ]
    except Exception as e:
        logger.error(f"list_prompt_versions: {e}")
        return []


def list_all_prompts() -> list:
    """List all prompt names with their active version."""
    try:
        from giso.base import get_giso_db_conn
        with get_giso_db_conn() as conn:
            rows = conn.execute(
                "SELECT prompt_name, MAX(version), SUM(CASE WHEN is_active=1 THEN version ELSE 0 END) "
                "FROM prompt_versions GROUP BY prompt_name ORDER BY prompt_name"
            ).fetchall()
            return [
                {"name": r[0], "latest_version": r[1], "active_version": r[2]}
                for r in rows
            ]
    except Exception as e:
        logger.error(f"list_all_prompts: {e}")
        return []
