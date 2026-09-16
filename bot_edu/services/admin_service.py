# -*- coding: utf-8 -*-
"""
admin_service — منطق مشترک پنل ادمین وب/ربات (بخش آموزشی).

- لیست کاربران، آمار، درخواست‌های نقدی، تیکت‌ها از همین‌جا خوانده می‌شود.
- تشخیص نقش ادمین سایت بر اساس شماره موبایل در SITE_ADMIN_PHONES.
- هیچ وابستگی‌ای به گیسو ندارد.
"""
from __future__ import annotations
import os
import logging
import sqlite3
from pathlib import Path

_DB = Path(__file__).resolve().parent.parent / "data" / "bot.db"
logger = logging.getLogger(__name__)


def _conn() -> sqlite3.Connection:
    c = sqlite3.connect(str(_DB), check_same_thread=False)
    c.row_factory = sqlite3.Row
    try:
        c.execute("PRAGMA journal_mode=WAL")
        c.execute("PRAGMA foreign_keys=ON")
    except Exception:
        pass
    return c


def admin_stats() -> dict:
    c = _conn()
    try:
        def _c(t, w=""):
            try:
                r = c.execute(f"SELECT COUNT(*) AS c FROM {t} {('WHERE '+w) if w else ''}").fetchone()
                return int(r["c"] if r else 0)
            except Exception:
                return 0
        return {
            "users": _c("users"),
            "courses": _c("courses"),
            "missions": _c("missions", "COALESCE(active,1)=1"),
            "shop_items": _c("shop_items", "COALESCE(active,0)=1"),
            "open_tickets": _c("tickets", "COALESCE(replied,0)=0"),
            "pending_cash": _c("cash_sale_requests", "COALESCE(status,'pending')='pending'"),
            "banned_users": _c("users", "COALESCE(is_banned,0)=1"),
        }
    finally:
        c.close()


def list_all_users(limit: int = 0) -> list:
    from .env_service import site_admin_phones
    c = _conn()
    try:
        if int(limit or 0) > 0:
            rows = c.execute(
                "SELECT user_id AS id, first_name, username, phone, joined, credits, xp, is_banned "
                "FROM users ORDER BY joined DESC LIMIT ?", (int(limit),)).fetchall()
        else:
            rows = c.execute(
                "SELECT user_id AS id, first_name, username, phone, joined, credits, xp, is_banned "
                "FROM users ORDER BY joined DESC").fetchall()
        admins = {_norm_phone_safe(p) for p in site_admin_phones()}
        prot = protected_identities()
        out = []
        for r in rows:
            uid = int(r["id"])
            phone = r["phone"] or ""
            phone_norm = _norm_phone_safe(phone)
            is_protected = bool(uid in prot["user_ids"] or (phone_norm and phone_norm in prot["phones"]))
            out.append({
                "id": uid, "first_name": r["first_name"] or "",
                "username": r["username"] or "", "phone": phone,
                "joined": int(r["joined"] or 0), "credits": int(r["credits"] or 0),
                "xp": int(r["xp"] or 0), "is_banned": bool(r["is_banned"]),
                "is_site_admin": bool(phone_norm and phone_norm in admins),
                "is_protected_admin": is_protected,
            })
        return out
    finally:
        c.close()


def list_pending_cash_requests(limit: int = 100) -> list:
    c = _conn()
    try:
        try:
            rows = c.execute(
                "SELECT id, user_id, target_type, course_id, course_title, amount, "
                "payment_method, display_note, created_at, platform "
                "FROM cash_sale_requests WHERE COALESCE(status,'pending')='pending' "
                "ORDER BY id DESC LIMIT ?", (int(limit),)).fetchall()
        except Exception:
            return []
        out = []
        for r in rows:
            u = c.execute("SELECT first_name, phone FROM users WHERE user_id=?",
                          (int(r["user_id"]),)).fetchone()
            out.append({
                "id": int(r["id"]), "user_id": int(r["user_id"]),
                "first_name": u["first_name"] if u else "ناشناس",
                "phone": u["phone"] if u else "",
                "target_type": r["target_type"] or "course",
                "course_id": r["course_id"] or "", "course_title": r["course_title"] or "",
                "amount": int(r["amount"] or 0), "payment_method": r["payment_method"] or "",
                "note": r["display_note"] or "",
                "created_at": r["created_at"] or "", "platform": r["platform"] or "",
            })
        return out
    finally:
        c.close()


def count_open_tickets() -> int:
    c = _conn()
    try:
        r = c.execute("SELECT COUNT(*) AS c FROM tickets WHERE COALESCE(replied,0)=0").fetchone()
        return int(r["c"] if r else 0)
    except Exception:
        return 0
    finally:
        c.close()


# ==================== نگهداری سایت / گیسو ====================

def _maintenance_key(name: str) -> str:
    n = str(name or '').strip().lower()
    if n in ('web', 'site', 'main'):
        return 'site_maintenance'
    if n in ('giso', 'hair'):
        return 'giso_maintenance'
    if n in ('site_maintenance', 'giso_maintenance'):
        return n
    return ''


def get_maintenance_flag(name) -> bool:
    """خواندن live وضعیت maintenance از settings. خطا = off."""
    key = _maintenance_key(name)
    if not key:
        return False
    c = _conn()
    try:
        if not _table_exists(c, 'settings'):
            return False
        r = c.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
        return str((r['value'] if r else '') or '').strip().lower() == 'on'
    except Exception:
        return False
    finally:
        c.close()


def set_maintenance_flag(name, value: bool) -> bool:
    """تنظیم live وضعیت maintenance در settings."""
    key = _maintenance_key(name)
    if not key:
        return False
    c = _conn()
    try:
        c.execute("CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT DEFAULT '')")
        with c:
            c.execute(
                "INSERT INTO settings(key, value) VALUES(?, ?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                (key, 'on' if value else 'off')
            )
        try:
            cfg = _sys.modules.get('config')
            if cfg and hasattr(cfg, 'SETTINGS'):
                cfg.SETTINGS[key] = 'on' if value else 'off'
        except Exception:
            pass
        logger.info("maintenance flag changed: %s=%s", key, 'on' if value else 'off')
        return True
    except Exception as e:
        logger.warning("set maintenance flag failed: %s", e)
        return False
    finally:
        c.close()


def _setting_value(key: str, default: str = '') -> str:
    c = _conn()
    try:
        if not _table_exists(c, 'settings'):
            return default
        row = c.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
        return str((row['value'] if row else default) or default)
    except Exception:
        return default
    finally:
        c.close()


def set_setting_value(key: str, value: str) -> bool:
    c = _conn()
    try:
        c.execute("CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT DEFAULT '')")
        with c:
            c.execute("INSERT INTO settings(key, value) VALUES(?, ?) ON CONFLICT(key) DO UPDATE SET value=excluded.value", (str(key), str(value)))
        try:
            cfg = _sys.modules.get('config')
            if cfg and hasattr(cfg, 'SETTINGS'):
                cfg.SETTINGS[str(key)] = str(value)
        except Exception:
            pass
        return True
    except Exception as e:
        logger.warning("set setting failed: %s", e)
        return False
    finally:
        c.close()


def get_site_health_report() -> dict:
    """گزارش سبک سلامت سایت برای پنل ربات."""
    now = int(_time.time())
    start_today = now - (now % 86400)
    c = _conn()
    try:
        return {
            'ok': True,
            'users_total': _count_where(c, 'users'),
            'users_today': _count_where(c, 'users', 'COALESCE(joined,0) >= ?', (start_today,)),
            'consultant_total': _count_where(c, 'consultant_requests'),
            'consultant_pending': _count_where(c, 'consultant_requests', "COALESCE(status,'pending')='pending'"),
            'consultant_active': _count_where(c, 'consultant_requests', "COALESCE(status,'')='active'"),
            'site_maintenance': get_maintenance_flag('site'),
            'giso_maintenance': get_maintenance_flag('giso'),
            'last_backup_at': _setting_value('last_backup_at', '') or 'ثبت نشده',
            'generated_at': now,
        }
    except Exception as e:
        logger.warning("health report failed: %s", e)
        return {'ok': False, 'error': str(e), 'generated_at': now}
    finally:
        c.close()

# ==================== حذف امن کاربران (سایت + ربات آموزشی / فقط bot.db) ====================
import json as _json
import time as _time
import sys as _sys


def _norm_phone_safe(raw: str) -> str:
    try:
        from phoneutil import normalize_phone
        return normalize_phone(raw) or ""
    except Exception:
        return str(raw or "").strip()


def cleanup_server_sessions() -> dict:
    """Flask sessions are cookie-based unless a server-side table exists."""
    logger.info("quick cleanup requested: sessions")
    c = _conn()
    try:
        removed = 0
        for table in ('sessions', 'flask_sessions', 'server_sessions'):
            if _table_exists(c, table):
                with c:
                    cur = c.execute(f"DELETE FROM {table}")
                    removed += max(0, int(cur.rowcount or 0))
        return {'ok': True, 'removed': removed, 'message': 'sessionهای سرور یافت نشد؛ چیزی برای پاک‌سازی نبود.' if removed == 0 else f'{removed} session حذف شد.'}
    except Exception as e:
        logger.warning("cleanup sessions failed: %s", e)
        return {'ok': False, 'error': str(e), 'removed': 0}
    finally:
        c.close()


def cleanup_safe_caches() -> dict:
    """پاک‌سازی cacheهای سبک بدون پاک کردن state فعال کاربران."""
    logger.info("quick cleanup requested: caches")
    try:
        cfg = _sys.modules.get('config')
        counts = {}
        if cfg:
            for name in ('_USER_FP', '_PLINK_FP'):
                obj = getattr(cfg, name, None)
                if hasattr(obj, 'clear'):
                    counts[name] = len(obj)
                    obj.clear()
        return {'ok': True, 'counts': counts, 'total': sum(counts.values())}
    except Exception as e:
        logger.warning("cleanup caches failed: %s", e)
        return {'ok': False, 'error': str(e), 'counts': {}, 'total': 0}


def cleanup_incomplete_requests() -> dict:
    """پاک‌سازی درخواست‌های رهاشده/ناقص واضح و امن."""
    logger.info("quick cleanup requested: incomplete requests")
    now = int(_time.time())
    old_cash_ts = now - 30 * 86400
    counts = {'consultant_pending_old': 0, 'consultant_orphan_messages': 0, 'cash_pending_old': 0, 'guest_orphan_analysis': 0}
    c = _conn()
    try:
        with c:
            if _table_exists(c, 'consultant_messages') and _table_exists(c, 'consultant_requests'):
                cur = c.execute("DELETE FROM consultant_messages WHERE request_id NOT IN (SELECT id FROM consultant_requests)")
                counts['consultant_orphan_messages'] = max(0, int(cur.rowcount or 0))
            if _table_exists(c, 'consultant_requests'):
                cur = c.execute("DELETE FROM consultant_requests WHERE COALESCE(status,'pending')='pending' AND datetime(created_at) < datetime('now','-7 days')")
                counts['consultant_pending_old'] = max(0, int(cur.rowcount or 0))
            if _table_exists(c, 'cash_sale_requests'):
                cur = c.execute("DELETE FROM cash_sale_requests WHERE COALESCE(status,'pending')='pending' AND COALESCE(requested_at,0) > 0 AND requested_at < ?", (old_cash_ts,))
                counts['cash_pending_old'] = max(0, int(cur.rowcount or 0))
            if _table_exists(c, 'web_identity_career_state') and _table_exists(c, 'users'):
                rows = c.execute("SELECT id, mentor_data, user_id FROM web_identity_career_state WHERE mentor_data LIKE '%guest_try_analysis%'").fetchall()
                for row in rows:
                    exists = c.execute("SELECT 1 FROM users WHERE user_id=?", (row['user_id'],)).fetchone()
                    if exists:
                        continue
                    try:
                        data = _json.loads(row['mentor_data'] or '{}')
                        if 'guest_try_analysis' in data:
                            data.pop('guest_try_analysis', None)
                            data.pop('guest_try_imported_at', None)
                            c.execute("UPDATE web_identity_career_state SET mentor_data=? WHERE id=?", (_json.dumps(data, ensure_ascii=False), row['id']))
                            counts['guest_orphan_analysis'] += 1
                    except Exception:
                        pass
        return {'ok': True, 'counts': counts, 'total': sum(counts.values())}
    except Exception as e:
        logger.warning("cleanup incomplete failed: %s", e)
        return {'ok': False, 'error': str(e), 'counts': counts, 'total': sum(counts.values())}
    finally:
        c.close()


def _parse_env_ids(raw: str) -> set[int]:
    out = set()
    for part in str(raw or "").replace("،", ",").split(","):
        part = part.strip()
        if not part:
            continue
        try:
            out.add(int(part))
        except Exception:
            pass
    return out


def _parse_env_phones(raw: str) -> set[str]:
    out = set()
    for part in str(raw or "").replace("،", ",").split(","):
        phone = _norm_phone_safe(part.strip())
        if phone:
            out.add(phone)
    return out


def protected_identities() -> dict:
    """ادمین‌های اصلی غیرقابل حذف از env: ADMIN_IDS + SITE_ADMIN_PHONES."""
    ids = _parse_env_ids(os.getenv("ADMIN_IDS", ""))
    phones = _parse_env_phones(os.getenv("SITE_ADMIN_PHONES", ""))
    try:
        cfg = _sys.modules.get("config")
        if cfg:
            ids.update(int(x) for x in getattr(cfg, "ADMIN_IDS", []) if str(x).strip())
            phones.update(_norm_phone_safe(x) for x in getattr(getattr(cfg, "Config", object), "SITE_ADMIN_PHONES", []) if x)
    except Exception:
        pass
    try:
        from .env_service import site_admin_phones
        phones.update(_norm_phone_safe(x) for x in site_admin_phones() if x)
    except Exception:
        pass
    phones = {p for p in phones if p}
    return {"user_ids": ids, "phones": phones}


def _is_protected_user(c: sqlite3.Connection, user_id: int = 0, phone: str = "") -> bool:
    prot = protected_identities()
    uid = int(user_id or 0)
    if uid and uid in prot["user_ids"]:
        return True
    phone_norm = _norm_phone_safe(phone)
    if not phone_norm and uid and _table_exists(c, "users"):
        try:
            row = c.execute("SELECT phone FROM users WHERE user_id=?", (uid,)).fetchone()
            phone_norm = _norm_phone_safe(row["phone"] if row else "")
        except Exception:
            phone_norm = ""
    return bool(phone_norm and phone_norm in prot["phones"])


def is_protected_admin_user(user_id: int = 0, phone: str = "") -> bool:
    c = _conn()
    try:
        return _is_protected_user(c, user_id, phone)
    finally:
        c.close()


def _table_exists(c: sqlite3.Connection, table: str) -> bool:
    try:
        r = c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table,)).fetchone()
        return bool(r)
    except Exception:
        return False


def _count_where(c: sqlite3.Connection, table: str, where: str = "1=1", params: tuple = ()) -> int:
    if not _table_exists(c, table):
        return 0
    try:
        r = c.execute(f"SELECT COUNT(*) AS c FROM {table} WHERE {where}", params).fetchone()
        return int(r["c"] if r else 0)
    except Exception:
        return 0


def _delete_where(c: sqlite3.Connection, table: str, where: str, params: tuple, counts: dict) -> int:
    if not _table_exists(c, table):
        counts[table] = counts.get(table, 0)
        return 0
    cur = c.execute(f"DELETE FROM {table} WHERE {where}", params)
    n = max(0, int(cur.rowcount if cur.rowcount is not None else 0))
    counts[table] = counts.get(table, 0) + n
    return n


def _update_where(c: sqlite3.Connection, table: str, set_sql: str, where: str, params: tuple, counts: dict) -> int:
    if not _table_exists(c, table):
        counts[table] = counts.get(table, 0)
        return 0
    cur = c.execute(f"UPDATE {table} SET {set_sql} WHERE {where}", params)
    n = max(0, int(cur.rowcount if cur.rowcount is not None else 0))
    counts[table] = counts.get(table, 0) + n
    return n


def _ensure_deletion_log_table(c: sqlite3.Connection) -> None:
    c.execute("""
        CREATE TABLE IF NOT EXISTS user_deletion_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            deleted_user_id INTEGER DEFAULT 0,
            deleted_phone TEXT DEFAULT '',
            deleted_first_name TEXT DEFAULT '',
            deleted_username TEXT DEFAULT '',
            deleted_by_user_id INTEGER DEFAULT 0,
            deleted_by_phone TEXT DEFAULT '',
            mode TEXT DEFAULT 'single_user_id',
            include_admins INTEGER DEFAULT 0,
            affected_counts_json TEXT DEFAULT '{}',
            snapshot_json TEXT DEFAULT '{}',
            created_at INTEGER DEFAULT 0
        )
    """)
    c.execute("CREATE INDEX IF NOT EXISTS idx_user_deletion_logs_user ON user_deletion_logs(deleted_user_id)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_user_deletion_logs_created ON user_deletion_logs(created_at)")


def _deleted_by_parts(deleted_by) -> tuple[int, str]:
    if isinstance(deleted_by, dict):
        try:
            uid = int(deleted_by.get("user_id") or deleted_by.get("id") or 0)
        except Exception:
            uid = 0
        return uid, str(deleted_by.get("phone") or "")
    try:
        return int(deleted_by or 0), ""
    except Exception:
        return 0, ""


def _user_snapshot(c: sqlite3.Connection, user_id: int, phone: str = "") -> dict:
    snap = {
        "user_id": int(user_id or 0),
        "phone": phone or "",
        "first_name": "",
        "username": "",
        "joined": 0,
        "last_active": 0,
        "credits": 0,
        "points": 0,
        "xp": 0,
        "is_banned": 0,
        "is_muted": 0,
    }
    if _table_exists(c, "users") and user_id:
        row = c.execute(
            "SELECT user_id, first_name, username, phone, joined, last_active, credits, points, xp, is_banned, is_muted "
            "FROM users WHERE user_id=?", (int(user_id),)
        ).fetchone()
        if row:
            snap.update({
                "user_id": int(row["user_id"] or 0),
                "phone": row["phone"] or phone or "",
                "first_name": row["first_name"] or "",
                "username": row["username"] or "",
                "joined": int(row["joined"] or 0),
                "last_active": int(row["last_active"] or 0),
                "credits": int(row["credits"] or 0),
                "points": int(row["points"] or 0),
                "xp": int(row["xp"] or 0),
                "is_banned": int(row["is_banned"] or 0),
                "is_muted": int(row["is_muted"] or 0),
            })
    if not snap["phone"] and phone:
        snap["phone"] = phone
    return snap


def _log_blocked_protected(c: sqlite3.Connection, user_id: int, phone: str, deleted_by, snapshot: dict | None = None) -> None:
    _ensure_deletion_log_table(c)
    uid = int(user_id or 0)
    phone_norm = _norm_phone_safe(phone)
    snapshot = snapshot or _user_snapshot(c, uid, phone_norm)
    if not phone_norm:
        phone_norm = snapshot.get("phone") or ""
    deleted_by_uid, deleted_by_phone = _deleted_by_parts(deleted_by)
    c.execute(
        "INSERT INTO user_deletion_logs (deleted_user_id, deleted_phone, deleted_first_name, deleted_username, "
        "deleted_by_user_id, deleted_by_phone, mode, include_admins, affected_counts_json, snapshot_json, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?, 'blocked_protected', 0, ?, ?, ?)",
        (
            uid, phone_norm, snapshot.get("first_name") or "", snapshot.get("username") or "",
            deleted_by_uid, deleted_by_phone,
            _json.dumps({"blocked_protected": 1}, ensure_ascii=False),
            _json.dumps(snapshot, ensure_ascii=False),
            int(_time.time()),
        ),
    )


def resolve_user_id_by_phone(phone_norm: str) -> int:
    """یافتن user_id از phone در جدول‌های آموزشی bot.db (بدون گیسو)."""
    phone_norm = str(phone_norm or "").strip()
    if not phone_norm:
        return 0
    c = _conn()
    try:
        for table in ("users", "web_identity_auth", "web_identity_career_state"):
            if not _table_exists(c, table):
                continue
            row = c.execute(f"SELECT user_id FROM {table} WHERE phone=? ORDER BY user_id DESC LIMIT 1", (phone_norm,)).fetchone()
            if row and row["user_id"]:
                return int(row["user_id"])
        return 0
    finally:
        c.close()


def get_user_delete_footprint(user_id, phone="") -> dict:
    """شمارش ردیف‌هایی که برای حذف امن یک کاربر از bot.db تحت تاثیر قرار می‌گیرند."""
    uid = int(user_id or 0)
    phone = str(phone or "")
    c = _conn()
    try:
        c.execute("PRAGMA foreign_keys=ON")
        req_ids = []
        if _table_exists(c, "consultant_requests"):
            req_ids = [int(r["id"]) for r in c.execute(
                "SELECT id FROM consultant_requests WHERE user_id=? OR phone=?", (uid, phone)
            ).fetchall()]
        path_ids = []
        if _table_exists(c, "career_paths"):
            path_ids = [int(r["id"]) for r in c.execute(
                "SELECT id FROM career_paths WHERE user_id=?", (uid,)
            ).fetchall()]

        fp = {}
        if req_ids:
            qs = ",".join("?" for _ in req_ids)
            fp["consultant_messages"] = _count_where(c, "consultant_messages", f"request_id IN ({qs})", tuple(req_ids))
        else:
            fp["consultant_messages"] = 0
        fp["consultant_requests"] = _count_where(c, "consultant_requests", "user_id=? OR phone=?", (uid, phone))
        fp["web_identity_career_state"] = _count_where(c, "web_identity_career_state", "user_id=? OR phone=?", (uid, phone))
        fp["web_identity_auth"] = _count_where(c, "web_identity_auth", "user_id=? OR phone=?", (uid, phone))
        if path_ids:
            qs = ",".join("?" for _ in path_ids)
            fp["path_steps"] = _count_where(c, "path_steps", f"path_id IN ({qs})", tuple(path_ids))
        else:
            fp["path_steps"] = 0
        fp["career_paths"] = _count_where(c, "career_paths", "user_id=?", (uid,))
        for table in (
            "ai_chat_history", "ai_usage_logs", "ai_credit_purchases", "ai_career_reports",
            "ai_certificates", "interview_simulations", "ai_career_twin", "user_missions",
            "team_members", "public_profiles", "user_profiles", "completed_missions",
            "credits_paid", "progress", "purchases", "survey_votes", "user_feature_restrictions",
        ):
            fp[table] = _count_where(c, table, "user_id=?", (uid,))
        fp["real_missions_anonymize"] = _count_where(c, "real_missions", "created_by=?", (uid,))
        fp["tickets"] = _count_where(c, "tickets", "user_id=? OR canonical_user_id=?", (uid, uid))
        fp["cash_sale_requests"] = _count_where(c, "cash_sale_requests", "user_id=? OR canonical_user_id=?", (uid, uid))
        fp["platform_links"] = _count_where(c, "platform_links", "user_id=? OR platform_user_id=?", (uid, str(uid)))
        fp["link_codes"] = _count_where(c, "link_codes", "user_id=? OR used_by=?", (uid, str(uid)))
        fp["admin_link_codes_anonymize"] = _count_where(c, "admin_link_codes", "created_by=? OR used_by=?", (uid, str(uid)))
        fp["platform_admins"] = _count_where(c, "platform_admins", "user_id=? OR platform_user_id=?", (uid, str(uid)))
        fp["referrals"] = _count_where(c, "referrals", "referrer_id=? OR referred_id=?", (uid, uid))
        fp["users_referrer_anonymize"] = _count_where(c, "users", "referrer=?", (uid,))
        fp["users"] = _count_where(c, "users", "user_id=?", (uid,))
        return fp
    finally:
        c.close()


def _delete_user_in_open_tx(c: sqlite3.Connection, user_id: int, phone: str, deleted_by, mode: str, include_admins: bool = False) -> dict:
    uid = int(user_id or 0)
    phone = str(phone or "")
    counts = {}
    _ensure_deletion_log_table(c)
    snapshot = _user_snapshot(c, uid, phone)
    if not phone:
        phone = snapshot.get("phone") or ""

    req_ids = []
    if _table_exists(c, "consultant_requests"):
        req_ids = [int(r["id"]) for r in c.execute(
            "SELECT id FROM consultant_requests WHERE user_id=? OR phone=?", (uid, phone)
        ).fetchall()]
    if req_ids:
        qs = ",".join("?" for _ in req_ids)
        _delete_where(c, "consultant_messages", f"request_id IN ({qs})", tuple(req_ids), counts)
    else:
        counts["consultant_messages"] = 0
    _delete_where(c, "consultant_requests", "user_id=? OR phone=?", (uid, phone), counts)
    _delete_where(c, "web_identity_career_state", "user_id=? OR phone=?", (uid, phone), counts)
    _delete_where(c, "web_identity_auth", "user_id=? OR phone=?", (uid, phone), counts)

    path_ids = []
    if _table_exists(c, "career_paths"):
        path_ids = [int(r["id"]) for r in c.execute("SELECT id FROM career_paths WHERE user_id=?", (uid,)).fetchall()]
    if path_ids:
        qs = ",".join("?" for _ in path_ids)
        _delete_where(c, "path_steps", f"path_id IN ({qs})", tuple(path_ids), counts)
    else:
        counts["path_steps"] = 0
    _delete_where(c, "career_paths", "user_id=?", (uid,), counts)

    for table in (
        "ai_chat_history", "ai_usage_logs", "ai_credit_purchases", "ai_career_reports",
        "ai_certificates", "interview_simulations", "ai_career_twin", "user_missions",
        "team_members", "public_profiles", "user_profiles",
    ):
        _delete_where(c, table, "user_id=?", (uid,), counts)

    _update_where(c, "real_missions", "created_by=0", "created_by=?", (uid,), counts)

    for table in ("completed_missions", "credits_paid", "progress", "purchases", "survey_votes"):
        _delete_where(c, table, "user_id=?", (uid,), counts)
    _delete_where(c, "tickets", "user_id=? OR canonical_user_id=?", (uid, uid), counts)
    _delete_where(c, "cash_sale_requests", "user_id=? OR canonical_user_id=?", (uid, uid), counts)
    _delete_where(c, "user_feature_restrictions", "user_id=?", (uid,), counts)
    _delete_where(c, "platform_links", "user_id=? OR platform_user_id=?", (uid, str(uid)), counts)
    _delete_where(c, "link_codes", "user_id=? OR used_by=?", (uid, str(uid)), counts)

    # anonymize admin link codes instead of deleting them
    if _table_exists(c, "admin_link_codes"):
        cur = c.execute(
            "UPDATE admin_link_codes SET created_by=CASE WHEN created_by=? THEN 0 ELSE created_by END, "
            "used_by=CASE WHEN used_by=? THEN '0' ELSE used_by END WHERE created_by=? OR used_by=?",
            (uid, str(uid), uid, str(uid)),
        )
        counts["admin_link_codes"] = max(0, int(cur.rowcount if cur.rowcount is not None else 0))
    else:
        counts["admin_link_codes"] = 0

    _delete_where(c, "platform_admins", "user_id=? OR platform_user_id=?", (uid, str(uid)), counts)
    _delete_where(c, "referrals", "referrer_id=? OR referred_id=?", (uid, uid), counts)
    _update_where(c, "users", "referrer=NULL", "referrer=?", (uid,), counts)
    _delete_where(c, "users", "user_id=?", (uid,), counts)

    deleted_by_uid, deleted_by_phone = _deleted_by_parts(deleted_by)
    c.execute(
        "INSERT INTO user_deletion_logs (deleted_user_id, deleted_phone, deleted_first_name, deleted_username, "
        "deleted_by_user_id, deleted_by_phone, mode, include_admins, affected_counts_json, snapshot_json, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            uid, phone, snapshot.get("first_name") or "", snapshot.get("username") or "",
            deleted_by_uid, deleted_by_phone, mode, 1 if include_admins else 0,
            _json.dumps(counts, ensure_ascii=False),
            _json.dumps(snapshot, ensure_ascii=False),
            int(_time.time()),
        ),
    )
    return {"ok": True, "user": snapshot, "affected_counts": counts, "total_affected": sum(int(v or 0) for v in counts.values())}


def _sync_memory_user(user_id) -> bool:
    try:
        cfg = _sys.modules.get("config")
        if cfg and hasattr(cfg, "remove_user_from_memory"):
            return bool(cfg.remove_user_from_memory(user_id))
    except Exception:
        pass
    return False


def _sync_memory_all() -> bool:
    try:
        cfg = _sys.modules.get("config")
        if cfg and hasattr(cfg, "remove_all_users_from_memory"):
            return bool(cfg.remove_all_users_from_memory())
    except Exception:
        pass
    return False


def delete_user_everywhere(user_id, phone="", deleted_by=None, mode: str = "single_user_id") -> dict:
    """حذف کامل یک کاربر از bot.db آموزشی. گیسو عمداً دست‌نخورده می‌ماند."""
    uid = int(user_id or 0)
    if uid <= 0:
        return {"ok": False, "error": "invalid_user_id"}
    c = _conn()
    try:
        c.execute("PRAGMA foreign_keys=ON")
        c.execute("BEGIN IMMEDIATE")
        snapshot = _user_snapshot(c, uid, str(phone or ""))
        target_phone = str(phone or "") or snapshot.get("phone") or ""
        if _is_protected_user(c, uid, target_phone):
            _log_blocked_protected(c, uid, target_phone, deleted_by, snapshot)
            c.commit()
            return {
                "ok": False,
                "error": "protected_admin",
                "not_allowed": True,
                "protected": True,
                "user": snapshot,
                "affected_counts": {},
                "total_affected": 0,
                "memory_synced": False,
            }
        result = _delete_user_in_open_tx(c, uid, target_phone, deleted_by, mode=mode, include_admins=True)
        c.commit()
        result["memory_synced"] = _sync_memory_user(uid)
        return result
    except Exception as e:
        c.rollback()
        return {"ok": False, "error": str(e)}
    finally:
        c.close()


def delete_all_users(deleted_by=None, include_admins: bool = True) -> dict:
    """حذف گروهی کاربران از bot.db؛ ادمین‌های اصلی env همیشه محافظت می‌شوند. گیسو خارج از scope است."""
    deleted_by_uid, deleted_by_phone = _deleted_by_parts(deleted_by)

    c = _conn()
    try:
        c.execute("PRAGMA foreign_keys=ON")
        if not _table_exists(c, "users"):
            return {"ok": True, "deleted_count": 0, "affected_counts": {}, "users": [], "memory_synced": _sync_memory_all()}
        rows = c.execute("SELECT user_id, phone FROM users ORDER BY user_id ASC").fetchall()
        targets = []
        skipped = []
        c.execute("BEGIN IMMEDIATE")
        _ensure_deletion_log_table(c)
        for r in rows:
            uid = int(r["user_id"] or 0)
            phone = r["phone"] or ""
            if _is_protected_user(c, uid, phone):
                snap = _user_snapshot(c, uid, phone)
                _log_blocked_protected(c, uid, phone, {"user_id": deleted_by_uid, "phone": deleted_by_phone}, snap)
                skipped.append({"user_id": uid, "phone": phone, "reason": "protected_admin"})
                continue
            targets.append((uid, phone))

        total_counts = {}
        deleted_users = []
        for uid, phone in targets:
            res = _delete_user_in_open_tx(
                c, uid, phone, {"user_id": deleted_by_uid, "phone": deleted_by_phone},
                mode="bulk", include_admins=include_admins,
            )
            deleted_users.append(res.get("user") or {"user_id": uid, "phone": phone})
            for k, v in (res.get("affected_counts") or {}).items():
                total_counts[k] = total_counts.get(k, 0) + int(v or 0)
        c.commit()
        memory_synced = all(_sync_memory_user(uid) for uid, _phone in targets)
        return {
            "ok": True,
            "deleted_count": len(deleted_users),
            "skipped_count": len(skipped),
            "skipped_protected_count": len([s for s in skipped if s.get("reason") == "protected_admin"]),
            "skipped": skipped,
            "users": deleted_users,
            "affected_counts": total_counts,
            "total_affected": sum(int(v or 0) for v in total_counts.values()),
            "include_admins": bool(include_admins),
            "memory_synced": memory_synced,
        }
    except Exception as e:
        c.rollback()
        return {"ok": False, "error": str(e)}
    finally:
        c.close()
