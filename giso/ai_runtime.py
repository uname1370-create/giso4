# -*- coding: utf-8 -*-
"""
giso/ai_runtime.py

لایهٔ مستقل مدیریت AI تعاملی گیسو.
این فایل فقط برای چت مشاور سایت/ربات و تست ادمین استفاده می‌شود و
نباید روی هستهٔ آنالیز مو/صورت، راه سریع، یا برنامه اختصاصی اثر بگذارد.
"""
from __future__ import annotations

import json
import logging
import re
import threading
import time
from datetime import datetime
from typing import Any

from giso.ai_runtime_policy import (
    PENDING_ACTION_TTL_MINUTES,
    OFF_MESSAGE,
    NO_ACCESS_MESSAGE,
    LIMIT_MESSAGE,
    PROVIDER_ERROR_MESSAGE,
    SOON_MESSAGE,
    OUT_OF_SCOPE_MESSAGE,
    NOT_DEFINED_MESSAGE,
    POLICY_DENIED_MESSAGE,
    NEED_MORE_DETAIL_MESSAGE,
    DEFAULT_DISPLAY_NAME,
    INSPECTOR_REPORT_ACTIONS,
    INSPECTOR_REPORT_SCOPES,
    detect_inspector_report,
    inspector_report,
    detect_force_refresh,
    _extract_name_candidate,
    _extract_provider_candidate,
    DEFAULT_ACTIVE_PROVIDER_ORDER,
    DEFAULT_USER_CAPABILITIES,
    DEFAULT_ADMIN_CAPABILITIES,
    DEFAULT_SUPER_CAPABILITIES,
    LEGACY_SUPER_CAPABILITIES,
    DEFAULT_SETTINGS,
    DEFAULT_ROLE_POLICIES,
    ROLE_LABELS,
    SECTION_LABELS,
    resolve_actor_role,
    _now_str,
    _today_prefix,
    _pending_expires_at_str,
    _mark_provider_cooldown,
    _clear_provider_cooldown,
    _apply_provider_cooldown,
    _jloads,
    _safe_dict,
    _clean_text,
    _text_lc,
    _extract_id_from_text,
    _extract_phone_from_text,
    _extract_amount_from_text,
    _is_smalltalk_request,
    _looks_like_general_management_chat,
)

# re-export گزارش‌های قطعی بازرس هوشمند (بدنه در ai_runtime_policy)
_report_incidents = lambda: inspector_report("report_incidents")
_report_insights = lambda: inspector_report("report_insights")
_report_health = lambda: inspector_report("report_health")

logger = logging.getLogger("giso_ai_runtime")

_RUNTIME_LOCK = threading.Lock()
_RUNTIME_READY = False
def _conn():
    from giso.base import get_giso_db_conn
    return get_giso_db_conn()

def _expire_stale_pending_actions(pending_id: int | None = None) -> None:
    try:
        now_str = _now_str()
        with _conn() as conn:
            if pending_id is None:
                conn.execute(
                    "UPDATE giso_ai_pending_actions SET status='expired' WHERE status='pending' AND expires_at != '' AND expires_at <= ?",
                    (now_str,),
                )
            else:
                conn.execute(
                    "UPDATE giso_ai_pending_actions SET status='expired' WHERE id=? AND status='pending' AND expires_at != '' AND expires_at <= ?",
                    (int(pending_id), now_str),
                )
            conn.commit()
    except Exception:
        pass

def _ensure_runtime_ready() -> None:
    global _RUNTIME_READY
    if _RUNTIME_READY:
        return
    with _RUNTIME_LOCK:
        if _RUNTIME_READY:
            return
        init_ai_runtime_tables()
        _RUNTIME_READY = True

def init_ai_runtime_tables() -> bool:
    try:
        with _conn() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS giso_ai_settings (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    key TEXT UNIQUE NOT NULL,
                    value TEXT DEFAULT '',
                    updated_at TEXT DEFAULT ''
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS giso_ai_permissions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    role TEXT UNIQUE NOT NULL,
                    access_level INTEGER DEFAULT 0,
                    sections TEXT DEFAULT '[]',
                    daily_limit INTEGER DEFAULT 0,
                    updated_at TEXT DEFAULT ''
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS giso_ai_usage_stats (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    actor_key TEXT DEFAULT '',
                    user_role TEXT DEFAULT 'user',
                    channel TEXT DEFAULT 'site',
                    action TEXT DEFAULT 'chat',
                    section TEXT DEFAULT 'consultant_chat',
                    tokens_used INTEGER DEFAULT 0,
                    provider_name TEXT DEFAULT '',
                    model_name TEXT DEFAULT '',
                    question_text TEXT DEFAULT '',
                    created_at TEXT DEFAULT ''
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS giso_user_activity (
                    user_id INTEGER PRIMARY KEY,
                    last_activity_at INTEGER DEFAULT 0,
                    last_welcome_shown_at INTEGER DEFAULT 0
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS giso_ai_pending_actions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    actor_key TEXT DEFAULT '',
                    actor_role TEXT DEFAULT 'super',
                    action_name TEXT NOT NULL,
                    target_table TEXT DEFAULT '',
                    target_id INTEGER DEFAULT 0,
                    args_json TEXT DEFAULT '{}',
                    snapshot_json TEXT DEFAULT '{}',
                    preview_text TEXT DEFAULT '',
                    request_text TEXT DEFAULT '',
                    status TEXT DEFAULT 'pending',
                    created_at TEXT DEFAULT '',
                    expires_at TEXT DEFAULT ''
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS giso_ai_action_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    actor_key TEXT DEFAULT '',
                    actor_role TEXT DEFAULT 'super',
                    action_name TEXT NOT NULL,
                    target_table TEXT DEFAULT '',
                    target_id INTEGER DEFAULT 0,
                    request_text TEXT DEFAULT '',
                    args_json TEXT DEFAULT '{}',
                    snapshot_json TEXT DEFAULT '{}',
                    result_json TEXT DEFAULT '{}',
                    status TEXT DEFAULT 'created',
                    approved INTEGER DEFAULT 0,
                    error_text TEXT DEFAULT '',
                    created_at TEXT DEFAULT '',
                    approved_at TEXT DEFAULT '',
                    executed_at TEXT DEFAULT ''
                )
                """
            )
            conn.execute("CREATE INDEX IF NOT EXISTS idx_giso_ai_usage_actor ON giso_ai_usage_stats(actor_key)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_giso_ai_usage_created ON giso_ai_usage_stats(created_at)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_giso_ai_usage_role ON giso_ai_usage_stats(user_role)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_giso_ai_usage_action ON giso_ai_usage_stats(action)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_giso_ai_pending_actor ON giso_ai_pending_actions(actor_key)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_giso_ai_pending_status ON giso_ai_pending_actions(status)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_giso_ai_logs_actor ON giso_ai_action_logs(actor_key)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_giso_ai_logs_status ON giso_ai_action_logs(status)")
            now = _now_str()
            for key, value in DEFAULT_SETTINGS.items():
                conn.execute(
                    "INSERT INTO giso_ai_settings (key, value, updated_at) VALUES (?,?,?) ON CONFLICT DO NOTHING",
                    (key, value, now),
                )
            # مهاجرت: پرامپت قدیمی سوپرادمین (LEGACY یا نسخهٔ پرحرف قبلی) به نسخهٔ کوتاه فعلی
            try:
                row = conn.execute(
                    "SELECT value FROM giso_ai_settings WHERE key='chat_capabilities_super'"
                ).fetchone()
                current_super = str((row["value"] if row else "") or "").strip()
                if current_super and current_super != DEFAULT_SUPER_CAPABILITIES.strip():
                    if (
                        current_super == LEGACY_SUPER_CAPABILITIES.strip()
                        or "سطح ۳ است" in current_super
                        or "هرگز نپرس سطح دسترسی" in current_super
                    ):
                        conn.execute(
                            "UPDATE giso_ai_settings SET value=?, updated_at=? WHERE key='chat_capabilities_super'",
                            (DEFAULT_SUPER_CAPABILITIES, now),
                        )
            except Exception:
                pass
            for role, policy in DEFAULT_ROLE_POLICIES.items():
                conn.execute(
                    "INSERT INTO giso_ai_permissions (role, access_level, sections, daily_limit, updated_at) VALUES (?,?,?,?,?) ON CONFLICT DO NOTHING",
                    (
                        role,
                        int(policy["access_level"]),
                        json.dumps(policy["sections"], ensure_ascii=False),
                        int(policy["daily_limit"]),
                        now,
                    ),
                )
            conn.commit()
        # اگر provider فعال خالی است، یک پیش‌فرض امن انتخاب کن
        try:
            with _conn() as conn:
                row = conn.execute("SELECT value FROM giso_ai_settings WHERE key='chat_active_provider'").fetchone()
                current_provider = str(row[0] or "").strip() if row else ""
                if not current_provider:
                    provider = _pick_default_provider_name()
                    if provider:
                        conn.execute(
                            "UPDATE giso_ai_settings SET value=?, updated_at=? WHERE key='chat_active_provider'",
                            (provider, now),
                        )
                        conn.commit()
        except Exception:
            pass
        return True
    except Exception as e:
        logger.error(f"init_ai_runtime_tables: {e}")
        return False

def get_setting(key: str, default: str | None = None) -> str | None:
    _ensure_runtime_ready()
    try:
        with _conn() as conn:
            row = conn.execute("SELECT value FROM giso_ai_settings WHERE key=?", (key,)).fetchone()
        if row and row[0] is not None:
            return str(row[0])
    except Exception as e:
        logger.error(f"get_setting({key}): {e}")
    return default

def set_setting(key: str, value: str) -> bool:
    _ensure_runtime_ready()
    try:
        with _conn() as conn:
            conn.execute(
                "INSERT INTO giso_ai_settings (key, value, updated_at) VALUES (?,?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_at=excluded.updated_at",
                (key, str(value), _now_str()),
            )
            conn.commit()
        return True
    except Exception as e:
        logger.error(f"set_setting({key}): {e}")
        return False

def get_display_name() -> str:
    return (get_setting("chat_display_name", DEFAULT_DISPLAY_NAME) or DEFAULT_DISPLAY_NAME).strip() or DEFAULT_DISPLAY_NAME

def set_display_name(name: str) -> tuple[bool, str]:
    name = (name or "").strip()
    if not name:
        return False, "اسم نمی‌تواند خالی باشد."
    if len(name) > 20:
        return False, "اسم نمایشی باید حداکثر ۲۰ کاراکتر باشد."
    ok = set_setting("chat_display_name", name)
    return ok, ("ذخیره شد." if ok else "خطا در ذخیره")

def is_chat_enabled() -> bool:
    raw = str(get_setting("chat_enabled", "1") or "1").strip().lower()
    return raw in ("1", "true", "on", "yes")

def set_chat_enabled(flag: bool) -> bool:
    return set_setting("chat_enabled", "1" if flag else "0")

def is_widget_enabled() -> bool:
    raw = str(get_setting("widget_enabled", "1") or "1").strip().lower()
    return raw in ("1", "true", "on", "yes")

def set_widget_enabled(flag: bool) -> bool:
    return set_setting("widget_enabled", "1" if flag else "0")

def get_widget_position() -> str:
    val = (get_setting("widget_position", "right-bottom") or "right-bottom").strip().lower()
    if val not in ("right-bottom", "left-bottom", "right-top", "left-top"):
        return "right-bottom"
    return val

def set_widget_position(position: str) -> tuple[bool, str]:
    pos = (position or "").strip().lower()
    if pos not in ("right-bottom", "left-bottom", "right-top", "left-top"):
        return False, "موقعیت نامعتبر است."
    ok = set_setting("widget_position", pos)
    return ok, ("موقعیت ذخیره شد." if ok else "خطا در ذخیره موقعیت")

def get_widget_welcome_message() -> str:
    return (get_setting("widget_welcome_message", DEFAULT_SETTINGS["widget_welcome_message"]) or DEFAULT_SETTINGS["widget_welcome_message"]).strip()

def set_widget_welcome_message(message: str) -> tuple[bool, str]:
    msg = (message or "").strip()
    if not msg:
        return False, "متن خوش‌آمد نمی‌تواند خالی باشد."
    ok = set_setting("widget_welcome_message", msg)
    return ok, ("متن خوش‌آمد ذخیره شد." if ok else "خطا در ذخیره متن خوش‌آمد")

def get_widget_primary_color() -> str:
    val = (get_setting("widget_primary_color", DEFAULT_SETTINGS["widget_primary_color"]) or DEFAULT_SETTINGS["widget_primary_color"]).strip()
    if re.fullmatch(r"#[0-9a-fA-F]{6}", val):
        return val
    return DEFAULT_SETTINGS["widget_primary_color"]

def set_widget_primary_color(color: str) -> tuple[bool, str]:
    val = (color or "").strip()
    if not re.fullmatch(r"#[0-9a-fA-F]{6}", val):
        return False, "رنگ باید به صورت #RRGGBB باشد."
    ok = set_setting("widget_primary_color", val)
    return ok, ("رنگ اصلی ذخیره شد." if ok else "خطا در ذخیره رنگ")

def get_widget_config() -> dict[str, Any]:
    return {
        "enabled": is_widget_enabled(),
        "position": get_widget_position(),
        "welcome_message": get_widget_welcome_message(),
        "primary_color": get_widget_primary_color(),
    }

def _valid_provider_names(only_enabled: bool = False) -> list[str]:
    rows = _provider_rows(only_enabled=only_enabled)
    out = []
    for r in rows:
        try:
            name = str(r["name"] or "").strip()
        except Exception:
            name = ""
        if name:
            out.append(name)
    return out

def get_failover_chain() -> list[str]:
    _ensure_runtime_ready()
    raw = get_setting("failover_chain", DEFAULT_SETTINGS["failover_chain"]) or DEFAULT_SETTINGS["failover_chain"]
    data = _jloads(raw, DEFAULT_ACTIVE_PROVIDER_ORDER)
    if not isinstance(data, list):
        data = list(DEFAULT_ACTIVE_PROVIDER_ORDER)
    enabled = set(_valid_provider_names(only_enabled=True))
    chain = []
    for name in data:
        s = str(name).strip()
        if s and s in enabled and s not in chain:
            chain.append(s)
    for name in _valid_provider_names(only_enabled=True):
        if name not in chain:
            chain.append(name)
    return chain

def set_failover_chain(chain_list: list[str]) -> tuple[bool, str]:
    _ensure_runtime_ready()
    enabled = set(_valid_provider_names(only_enabled=True))
    clean = []
    for item in chain_list or []:
        name = str(item).strip()
        if name and name in enabled and name not in clean:
            clean.append(name)
    if not clean:
        return False, "زنجیره failover معتبر نیست."
    ok = set_setting("failover_chain", json.dumps(clean, ensure_ascii=False))
    return ok, ("زنجیره failover ذخیره شد." if ok else "خطا در ذخیره زنجیره failover")

def _build_provider_attempt_chain(preferred_provider: str | None = None) -> list[str]:
    preferred = (preferred_provider or "").strip()
    chain = []
    if preferred:
        chain.append(preferred)
    active = get_active_provider()
    if active and active not in chain:
        chain.append(active)
    for name in get_failover_chain():
        if name not in chain:
            chain.append(name)
    return _apply_provider_cooldown(chain)

def _activity_row(user_id: int | str):
    _ensure_runtime_ready()
    try:
        with _conn() as conn:
            row = conn.execute(
                "SELECT user_id, last_activity_at, last_welcome_shown_at FROM giso_user_activity WHERE user_id=?",
                (int(user_id),),
            ).fetchone()
        return row
    except Exception as e:
        logger.error(f"_activity_row({user_id}): {e}")
        return None

def get_last_activity(user_id: int | str) -> int:
    row = _activity_row(user_id)
    try:
        return int(row[1] or 0) if row else 0
    except Exception:
        return 0

def get_last_welcome(user_id: int | str) -> int:
    row = _activity_row(user_id)
    try:
        return int(row[2] or 0) if row else 0
    except Exception:
        return 0

def touch_user_activity(user_id: int | str, ts: int | None = None) -> bool:
    _ensure_runtime_ready()
    user_id = int(user_id)
    stamp = int(ts if ts is not None else time.time())
    try:
        with _conn() as conn:
            conn.execute(
                """
                INSERT INTO giso_user_activity (user_id, last_activity_at, last_welcome_shown_at)
                VALUES (?, ?, 0)
                ON CONFLICT(user_id) DO UPDATE SET last_activity_at=excluded.last_activity_at
                """,
                (user_id, stamp),
            )
            conn.commit()
        return True
    except Exception as e:
        logger.error(f"touch_user_activity({user_id}): {e}")
        return False

def mark_welcome_shown(user_id: int | str, ts: int | None = None) -> bool:
    _ensure_runtime_ready()
    user_id = int(user_id)
    stamp = int(ts if ts is not None else time.time())
    last_activity = get_last_activity(user_id)
    if not last_activity:
        last_activity = stamp
    try:
        with _conn() as conn:
            conn.execute(
                """
                INSERT INTO giso_user_activity (user_id, last_activity_at, last_welcome_shown_at)
                VALUES (?, ?, ?)
                ON CONFLICT(user_id) DO UPDATE SET
                    last_activity_at=excluded.last_activity_at,
                    last_welcome_shown_at=excluded.last_welcome_shown_at
                """,
                (user_id, last_activity, stamp),
            )
            conn.commit()
        return True
    except Exception as e:
        logger.error(f"mark_welcome_shown({user_id}): {e}")
        return False

def get_welcome_inactive_hours() -> int:
    raw = str(get_setting("welcome_inactive_hours", "6") or "6").strip()
    try:
        return max(1, int(raw))
    except (TypeError, ValueError):
        return 6

def should_show_welcome(user_id: int | str, force: bool = False) -> bool:
    if force:
        return True
    now = int(time.time())
    last_activity = get_last_activity(user_id)
    last_welcome = get_last_welcome(user_id)
    if not last_activity:
        return True
    min_gap = get_welcome_inactive_hours() * 3600
    if (now - last_activity) < min_gap:
        return False
    if last_welcome and (now - last_welcome) < min_gap:
        return False
    return True

def _provider_rows(only_enabled: bool = False):
    from giso.ai_brain import list_ai_providers
    try:
        return list_ai_providers(only_enabled=only_enabled) or []
    except Exception as e:
        logger.error(f"_provider_rows: {e}")
        return []

def _pick_default_provider_name() -> str:
    rows = _provider_rows(only_enabled=True)
    if not rows:
        return ""
    by_name = {str(r["name"]): r for r in rows if r and r["name"]}
    for name in DEFAULT_ACTIVE_PROVIDER_ORDER:
        if name in by_name:
            return name
    return str(rows[0]["name"])

def get_active_provider() -> str:
    _ensure_runtime_ready()
    current = (get_setting("chat_active_provider", "") or "").strip()
    if current:
        rows = _provider_rows(only_enabled=True)
        if any(str(r["name"]) == current for r in rows):
            return current
    fallback = _pick_default_provider_name()
    if fallback:
        set_setting("chat_active_provider", fallback)
    return fallback

def set_active_provider(provider_name: str) -> tuple[bool, str]:
    _ensure_runtime_ready()
    provider_name = (provider_name or "").strip()
    if not provider_name:
        return False, "نام پروایدر نامعتبر است."
    rows = _provider_rows(only_enabled=True)
    if not any(str(r["name"]) == provider_name for r in rows):
        return False, "این پروایدر فعال نیست یا وجود ندارد."
    if set_setting("chat_active_provider", provider_name):
        return True, f"AI فعال به «{provider_name}» تغییر کرد."
    return False, "خطا در ذخیره AI فعال."

def list_provider_options() -> dict[str, list[dict[str, Any]]]:
    _ensure_runtime_ready()
    active_name = get_active_provider()
    rows = _provider_rows(only_enabled=False)
    out = {"iranian": [], "foreign": []}
    for row in rows:
        item = {
            "name": str(row["name"] or ""),
            "kind": str(row["kind"] or ""),
            "enabled": bool(row["enabled"]),
            "is_iranian": bool(row["is_iranian"]),
            "selected_model": str(row["selected_model"] or ""),
            "last_status": str(row["last_status"] or ""),
            "is_active": str(row["name"] or "") == active_name,
            "base_url": str(row["base_url"] or ""),
            "use_proxy": bool(row["use_proxy"]),
            "has_api_key": bool(str(row["api_key"] or "").strip()),
        }
        out["iranian" if item["is_iranian"] else "foreign"].append(item)
    return out

def get_role_capabilities(role: str) -> str:
    role = (role or "user").strip().lower()
    if role not in ("user", "admin", "super"):
        role = "user"
    defaults = {
        "user": DEFAULT_USER_CAPABILITIES,
        "admin": DEFAULT_ADMIN_CAPABILITIES,
        "super": DEFAULT_SUPER_CAPABILITIES,
    }
    return (get_setting(f"chat_capabilities_{role}", defaults[role]) or defaults[role]).strip()

def set_role_capabilities(role: str, text: str) -> tuple[bool, str]:
    role = (role or "user").strip().lower()
    if role not in ("user", "admin", "super"):
        return False, "نقش نامعتبر است."
    text = (text or "").strip()
    if not text:
        return False, "متن قابلیت‌ها نمی‌تواند خالی باشد."
    ok = set_setting(f"chat_capabilities_{role}", text)
    return ok, ("ذخیره شد." if ok else "خطا در ذخیره")

def get_role_policy(role: str) -> dict[str, Any]:
    _ensure_runtime_ready()
    role = (role or "user").strip().lower()
    if role == "super":
        return {
            "role": "super",
            "access_level": 3,
            "sections": ["*"],
            "daily_limit": 0,
            "read_only": True,
        }
    if role not in DEFAULT_ROLE_POLICIES:
        role = "user"
    try:
        with _conn() as conn:
            row = conn.execute(
                "SELECT access_level, sections, daily_limit FROM giso_ai_permissions WHERE role=?",
                (role,),
            ).fetchone()
        if row:
            return {
                "role": role,
                "access_level": int(row[0] or 0),
                "sections": _jloads(row[1], DEFAULT_ROLE_POLICIES[role]["sections"]),
                "daily_limit": int(row[2] or 0),
                "read_only": False,
            }
    except Exception as e:
        logger.error(f"get_role_policy({role}): {e}")
    base = DEFAULT_ROLE_POLICIES[role]
    return {
        "role": role,
        "access_level": int(base["access_level"]),
        "sections": list(base["sections"]),
        "daily_limit": int(base["daily_limit"]),
        "read_only": False,
    }

def set_role_policy(role: str, access_level: int | None = None,
                    sections: list[str] | None = None,
                    daily_limit: int | None = None) -> tuple[bool, str]:
    _ensure_runtime_ready()
    role = (role or "user").strip().lower()
    if role == "super":
        return False, "تنظیمات سوپرادمین ثابت و فقط نمایشی است."
    if role not in DEFAULT_ROLE_POLICIES:
        return False, "نقش نامعتبر است."
    current = get_role_policy(role)
    try:
        level = int(current["access_level"] if access_level is None else access_level)
    except (TypeError, ValueError):
        level = int(current["access_level"])
    level = max(0, min(3, level))
    sections_val = list(current["sections"] if sections is None else sections)
    daily = current["daily_limit"] if daily_limit is None else daily_limit
    try:
        daily = max(0, int(daily))
    except (TypeError, ValueError):
        daily = int(current["daily_limit"])
    try:
        with _conn() as conn:
            conn.execute(
                "INSERT INTO giso_ai_permissions (role, access_level, sections, daily_limit, updated_at) VALUES (?,?,?,?,?) ON CONFLICT(role) DO UPDATE SET access_level=excluded.access_level, sections=excluded.sections, daily_limit=excluded.daily_limit, updated_at=excluded.updated_at",
                (role, level, json.dumps(sections_val, ensure_ascii=False), daily, _now_str()),
            )
            conn.commit()
        return True, "تنظیمات ذخیره شد."
    except Exception as e:
        logger.error(f"set_role_policy({role}): {e}")
        return False, "خطا در ذخیره تنظیمات."

def check_role_access(role: str, section: str = "consultant_chat") -> dict[str, Any]:
    policy = get_role_policy(role)
    role_name = policy["role"]
    if role_name == "super":
        return {
            "allowed": True,
            "reason": "super",
            "message": "",
            "policy": policy,
            "access_level": 3,
        }
    access_level = int(policy.get("access_level", 0) or 0)
    if access_level <= 0:
        return {
            "allowed": False,
            "reason": "access_level_0",
            "message": NO_ACCESS_MESSAGE,
            "policy": policy,
            "access_level": access_level,
        }
    sections = policy.get("sections") or []
    if "*" not in sections and section and section not in sections:
        return {
            "allowed": False,
            "reason": "section_blocked",
            "message": NO_ACCESS_MESSAGE,
            "policy": policy,
            "access_level": access_level,
        }
    return {
        "allowed": True,
        "reason": "ok",
        "message": "",
        "policy": policy,
        "access_level": access_level,
    }

def get_context_scope(role: str, section: str = "consultant_chat") -> dict[str, Any]:
    check = check_role_access(role, section)
    policy = check["policy"]
    access_level = int(check.get("access_level", 0) or 0)
    sections = set(policy.get("sections") or [])
    all_sections = "*" in sections

    scope = {
        "allowed": bool(check["allowed"]),
        "message": check.get("message", ""),
        "access_level": access_level,
        "include_analysis": False,
        "include_plan": False,
        "include_products": False,
        "include_orders": False,
        "allow_actions": False,
    }
    if not scope["allowed"]:
        return scope

    if access_level >= 1:
        scope["include_analysis"] = all_sections or "analysis" in sections
        scope["include_plan"] = all_sections or "plan" in sections
    if access_level >= 2:
        scope["include_products"] = all_sections or "products" in sections
        scope["include_orders"] = all_sections or "orders" in sections
    if access_level >= 3:
        scope["allow_actions"] = all_sections or "actions" in sections
    return scope

def get_today_usage_count(actor_key: str, role: str, action: str = "chat") -> int:
    _ensure_runtime_ready()
    actor_key = str(actor_key or "").strip()
    if not actor_key:
        return 0
    try:
        with _conn() as conn:
            row = conn.execute(
                "SELECT COUNT(*) FROM giso_ai_usage_stats WHERE actor_key=? AND user_role=? AND action=? AND created_at LIKE ?",
                (actor_key, role, action, _today_prefix() + "%"),
            ).fetchone()
        return int(row[0] or 0) if row else 0
    except Exception as e:
        logger.error(f"get_today_usage_count: {e}")
        return 0

def check_daily_limit(actor_key: str, role: str, action: str = "chat") -> dict[str, Any]:
    policy = get_role_policy(role)
    if policy["role"] == "super":
        return {"allowed": True, "limit": 0, "used": 0, "remaining": None}
    limit = int(policy.get("daily_limit", 0) or 0)
    used = get_today_usage_count(actor_key, policy["role"], action=action)
    if limit <= 0:
        return {"allowed": True, "limit": 0, "used": used, "remaining": None}
    remaining = max(0, limit - used)
    return {
        "allowed": used < limit,
        "limit": limit,
        "used": used,
        "remaining": remaining,
    }

def record_usage(actor_key: str, role: str, channel: str, action: str,
                 tokens_used: int = 0, provider_name: str = "", model_name: str = "",
                 question_text: str = "", section: str = "consultant_chat") -> bool:
    _ensure_runtime_ready()
    try:
        with _conn() as conn:
            conn.execute(
                """
                INSERT INTO giso_ai_usage_stats
                (actor_key, user_role, channel, action, section, tokens_used,
                 provider_name, model_name, question_text, created_at)
                VALUES (?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    str(actor_key or ""),
                    str(role or "user"),
                    str(channel or "site"),
                    str(action or "chat"),
                    str(section or "consultant_chat"),
                    max(0, int(tokens_used or 0)),
                    str(provider_name or ""),
                    str(model_name or ""),
                    str(question_text or "")[:200],
                    _now_str(),
                ),
            )
            conn.commit()
        return True
    except Exception as e:
        logger.error(f"record_usage: {e}")
        return False

def _estimate_tokens(messages: list[dict[str, Any]], answer_text: str) -> int:
    try:
        in_chars = sum(len(str(m.get("content", "") or "")) for m in (messages or []))
        out_chars = len(answer_text or "")
        return max(1, (in_chars + out_chars) // 4)
    except Exception:
        return 0

def _extract_tokens_from_result(result: dict[str, Any], fallback_messages: list[dict[str, Any]]) -> int:
    raw = result.get("raw") or {}
    usage = raw.get("usage") if isinstance(raw, dict) else None
    if isinstance(usage, dict):
        for key in ("total_tokens", "tokens", "input_tokens"):
            val = usage.get(key)
            try:
                if val is not None:
                    return max(0, int(val))
            except (TypeError, ValueError):
                pass
    return _estimate_tokens(fallback_messages, result.get("text", "") or "")

def _is_capability_guide_request(text: str) -> bool:
    t = _text_lc(text)
    if not t:
        return False
    needles = [
        "راهنما", "چه کار", "چکار", "چه کمکی", "چی بلدی", "چه میتونی", "چه می تونی",
        "چه کاری", "قابلیت", "امکانات", "چه خدمات", "کمکم کن بدونم", "چه دسترسی",
        "چه کارهایی", "چه توانایی", "چه کارا", "help",
    ]
    return any(n in t for n in needles)

_FAKE_EXEC_RE = re.compile(
    r"(اقدام اجرا شد|تغییر اعمال شد|حذف کردم|ثبت کردم|انجام دادم|اعمال کردم"
    r"|executed successfully|I (have )?executed|applied the change)",
    re.IGNORECASE,
)
_FAKE_STAT_RE = re.compile(
    r"(طبق آمار گوگل|۱۰۰٪ کاربران|همه کاربران|بدون خطا ۱۰۰|حدس می‌زنم \d+)",
    re.IGNORECASE,
)

def _sanitize_ai_reply(text: str, role: str = "user") -> str:
    raw = str(text or "").strip()
    if not raw:
        return ""
    cleaned_lines = []
    skip_needles = [
        "system rules", "natural tone", "capabilities", "role:", "assistant:", "user:",
        "system prompt", "policy rules", "system:", "developer:",
    ]
    for line in raw.splitlines():
        s = line.strip()
        if not s:
            if cleaned_lines and cleaned_lines[-1] != "":
                cleaned_lines.append("")
            continue
        low = s.lower()
        if any(n in low for n in skip_needles):
            continue
        if low.startswith("**") and any(n in low for n in ("system", "assistant", "user", "rules")):
            continue
        cleaned_lines.append(s)
    cleaned = "\n".join(cleaned_lines).strip()
    if role == "super" and cleaned in (OUT_OF_SCOPE_MESSAGE, NOT_DEFINED_MESSAGE, POLICY_DENIED_MESSAGE):
        return "صادق جان، اگر منظورت یک کار مدیریتی مشخصه، جزئیات بیشتری بده تا دقیق جلو بریم؛ اگر هم فقط داری گپ می‌زنی من با کمال میل در خدمتم."
    if role == "super":
        notes = []
        if _FAKE_EXEC_RE.search(cleaned) and "پیش‌نمایش" not in cleaned and "pending" not in cleaned.lower():
            notes.append("⚠️ ادعای اجرای اقدام بدون تأیید دومرحله‌ای رد شد. هیچ تغییری روی دیتابیس اعمال نشده است.")
            cleaned = _FAKE_EXEC_RE.sub("", cleaned).strip()
        if _FAKE_STAT_RE.search(cleaned):
            notes.append("⚠️ عدد/آمار بدون منبع زنده حذف شد. فقط از بلوک آمار زنده استفاده کن.")
            cleaned = _FAKE_STAT_RE.sub("", cleaned).strip()
        if notes:
            cleaned = (cleaned + "\n\n" if cleaned else "") + "\n".join(notes)
    return cleaned or raw

def super_chat_generation_params(question_text: str, requested_max_tokens: int = 750) -> tuple[float, int]:
    """temperature ثابت ۰٫۲ + سقف توکن متناسب با طول سؤال."""
    qlen = len(str(question_text or "").strip())
    if qlen <= 40:
        tokens = 280
    elif qlen <= 120:
        tokens = 500
    else:
        tokens = min(900, max(500, int(requested_max_tokens or 750)))
    return 0.2, tokens

def build_super_live_stats_block() -> str:
    """حدود ۱۰ خط آمار زنده برای تزریق به چت آزاد سوپرادمین (بدون حدس)."""
    return _report_dashboard(for_inject=True)

def build_capability_guide(role: str) -> str:
    role = (role or "user").strip().lower()
    if role == "super":
        return (
            "صادق جان، این کارها رو می‌تونم برات انجام بدم:\n\n"
            "📊 گزارش و مشاهده مستقیم:\n"
            "• گزارش سریع مدیریتی\n"
            "• گزارش سفارش‌ها\n"
            "• گزارش کاربران\n"
            "• گزارش تیکت‌ها\n"
            "• گزارش درخواست‌های مشاوره\n"
            "• گزارش فروش مو\n"
            "• گزارش آنالیزها\n"
            "• گزارش وضعیت هوش مصنوعی\n"
            "• خلاصه یک کاربر با شماره\n\n"
            "⚙️ تغییر با تأیید دو مرحله‌ای:\n"
            "• تغییر وضعیت سفارش\n"
            "• تغییر وضعیت تیکت\n"
            "• تغییر وضعیت مشاوره\n"
            "• تغییر وضعیت فروش مو\n"
            "• تغییر قیمت محصول\n"
            "• تغییر موجودی محصول\n"
            "• حذف محصول\n"
            "• حذف اطلاعات کاربر\n"
            "• روشن/خاموش کردن مشاور هوشمند\n"
            "• تغییر اسم نمایشی مشاور\n"
            "• تغییر AI فعال\n\n"
            "برای هر تغییر واقعی، اول پیش‌نمایش می‌دم و بعد از تأییدت اجرا می‌کنم."
        )
    if role == "admin":
        return (
            "عزیزم، در سطح فعلی من برای تو نقش دستیار گزارش‌محور دارم 🌷\n\n"
            "می‌تونم این‌ها رو برات بیارم:\n"
            "• گزارش سفارش‌ها\n"
            "• گزارش تیکت‌ها\n"
            "• گزارش درخواست‌های مشاوره\n"
            "• گزارش فروش مو\n"
            "• آمار و خلاصه وضعیت امروز\n"
            "• اولویت‌های رسیدگی\n\n"
            "من در این سطح هیچ تغییری روی داده‌ها انجام نمی‌دم و فقط گزارش و جمع‌بندی می‌دم."
        )
    return (
        "من «دستیار هوشمند گیسو» هستم؛ یک همراه مهربون که به تمام اطلاعات خودت دسترسی دارم 🌸\n\n"
        "می‌تونم دربارهٔ این‌ها گزارش و پیشنهاد و تحلیل بدم:\n"
        "• تحلیل مو و پوستت و برنامه و چک‌لیستت\n"
        "• سفارش‌های فروشگاه و فروش مو\n"
        "• کیف پول و مأموریت‌ها\n"
        "• آگهی‌های بازارچه و پیشنهادها\n"
        "• مرکز زیبایی، تیکت‌ها و اعلان‌ها\n"
        "• معرفی محصول مناسب در حد مجاز\n\n"
        "من فقط گزارش‌دهنده و راهنما هستم؛ هیچ تغییری روی داده‌ها انجام نمی‌دم. "
        "اگر چیزی خارج از خدمات گیسو باشه، محترمانه می‌گم در محدوده من نیست."
    )

def _prepend_runtime_system_message(messages: list[dict[str, Any]], role: str,
                                    access_level: int, display_name: str,
                                    capabilities_text: str) -> list[dict[str, Any]]:
    policy_rules = [
        f"نام نمایشی شما در این گفتگو: {display_name}",
        f"نقش کاربر مقابل: {ROLE_LABELS.get(role, role)}",
        f"سطح دسترسی قطعی کاربر مقابل: {access_level}",
        capabilities_text or "",
        "لحن خشک، کوتاه و رباتی ممنوع است.",
        "مثل یک مشاور دلسوز، طبیعی، باحوصله و خوش‌بیان پاسخ بده.",
        "پاسخ را با توجه به نقش، نیاز، سابقه، روحیه، پیام فعلی و context واقعی تنظیم کن.",
    ]
    if role == "super":
        policy_rules.extend([
            "سوپرادمین است؛ سطح دسترسی نپرس. مثل کاربر عادی حرف نزن.",
            "ساختار: وضعیت → عدد از بلوک زنده → ریسک → یک اقدام.",
            "طول پاسخ را با طول سؤال هماهنگ کن. عدد ساختگی ممنوع.",
            "ادعای اجرا بدون pending واقعی ممنوع.",
        ])
    elif role == "admin":
        policy_rules.extend([
            "کاربر مقابل ادمین است؛ با لحن همکار حرفه‌ای، مؤدب و عملیاتی پاسخ بده.",
            "در اولویت پاسخ، گزارش کوتاه، جمع‌بندی وضعیت و پیشنهاد رسیدگی بعدی را بده.",
        ])
    else:
        policy_rules.extend([
            "کاربر مقابل کاربر عادی است؛ با لحن گرم، همراه و آرامش‌بخش پاسخ بده.",
            "اگر از پیام کاربر نگرانی یا سردرگمی حس کردی، با همدلی و قدم‌به‌قدم راهنمایی کن.",
        ])
    if access_level <= 1:
        policy_rules.append("در این سطح فقط راهنمایی شخصی‌سازی‌شده بده و هیچ محصولی معرفی نکن.")
    elif access_level == 2:
        policy_rules.append("می‌توانی محصولات را فقط معرفی کنی، ولی خرید مستقیم یا اقدام اجرایی نده.")
    else:
        policy_rules.append("اقدامات آینده را فقط در حد توضیح یا دکمهٔ نمایشی مطرح کن و بدون تأیید نهایی کاری انجام نده.")
    system_msg = {"role": "system", "content": "\n".join([x for x in policy_rules if x]).strip()}
    return [system_msg] + list(messages or [])

async def _ask_single_provider(provider_name: str, messages: list[dict[str, Any]], temperature: float = 0.7, max_tokens: int = 1200, timeout_override: int | None = None) -> dict[str, Any]:
    from giso.ai_brain import ask_ai, get_ai_provider
    row = get_ai_provider(provider_name)
    if row is None or not bool(row["enabled"]):
        return {"ok": False, "reason": "provider_inactive", "error": PROVIDER_ERROR_MESSAGE, "provider": provider_name, "model": ""}
    try:
        result = await ask_ai(
            provider_name,
            messages,
            model=(row["selected_model"] or "") or None,
            temperature=temperature,
            max_tokens=max_tokens,
            timeout_override=timeout_override,
        )
    except Exception as e:
        logger.error(f"_ask_single_provider({provider_name}): {e}")
        result = {"ok": False, "error": str(e), "provider": provider_name, "model": (row["selected_model"] or "")}
    if not result or not result.get("ok"):
        return {
            "ok": False,
            "reason": "provider_error",
            "error": (result or {}).get("error") or PROVIDER_ERROR_MESSAGE,
            "provider": provider_name,
            "model": (result or {}).get("model") or (row["selected_model"] or ""),
        }
    text = _sanitize_ai_reply((result.get("text") or "").strip(), role="user")
    if not text:
        return {"ok": False, "reason": "empty_answer", "error": PROVIDER_ERROR_MESSAGE, "provider": provider_name, "model": result.get("model") or (row["selected_model"] or "")}
    result["text"] = text
    result["provider"] = result.get("provider") or provider_name
    result["model"] = result.get("model") or (row["selected_model"] or "")
    return result

async def chat_with_failover(messages: list[dict[str, Any]], preferred_provider: str | None = None,
                             temperature: float = 0.7, max_tokens: int = 1200,
                             role: str = "user") -> dict[str, Any]:
    """موتور چت — فاز ۳: بودجه ۳۰ ثانیه / ۶ ثانیه هر پروایدر + سلامت مشترک.

    با پرچم امنیت، رفتار قدیمی (کو‌لوداؤن درون‌حافظه‌ای) اجرا می‌شود.
    """
    from giso.ai_config import (CHAT_TOTAL_TIMEOUT_SECONDS, CHAT_PER_MODEL_TIMEOUT_SECONDS,
                                FEATURE_FLAG_LEGACY_MODE)
    if FEATURE_FLAG_LEGACY_MODE:
        return await _legacy_chat_with_failover(messages, preferred_provider, temperature,
                                                max_tokens, role)
    import time as _time
    try:
        from giso import ai_health
    except Exception:
        ai_health = None

    _ensure_runtime_ready()
    chain = _build_provider_attempt_chain(preferred_provider)
    if not chain:
        return {"ok": False, "reason": "no_provider", "text": PROVIDER_ERROR_MESSAGE, "error": PROVIDER_ERROR_MESSAGE, "provider_errors": []}

    # فیلتر کولداون سلامت مشترک (سطح پروایدر)
    if ai_health is not None:
        filtered = [p for p in chain if not ai_health.is_in_cooldown(p)]
        skipped = len(chain) - len(filtered)
        if skipped:
            logger.info("[AI_ATTEMPT] engine=chat result=cooldown_skipped count=%d", skipped)
        chain = filtered or chain  # اگر همه در کولداون بودند، شانس دوباره بده

    start = _time.time()
    errors = []
    for provider_name in chain:
        if _time.time() - start > CHAT_TOTAL_TIMEOUT_SECONDS:
            logger.info("[AI_ATTEMPT] engine=chat result=budget_exceeded elapsed=%.1fs",
                        _time.time() - start)
            break
        attempt_start = _time.time()
        result = await _ask_single_provider(provider_name, messages, temperature=temperature,
                                            max_tokens=max_tokens,
                                            timeout_override=CHAT_PER_MODEL_TIMEOUT_SECONDS)
        duration = _time.time() - attempt_start
        model_name = (result or {}).get("model") or ""
        if result.get("ok"):
            _clear_provider_cooldown(provider_name)
            if ai_health is not None:
                ai_health.mark_success(provider_name, model_name)
            logger.info("[AI_ATTEMPT] engine=chat provider=%s model=%s result=success duration=%.1fs",
                        provider_name, model_name, duration)
            result["fallback_used"] = (provider_name != chain[0])
            result["provider_errors"] = errors
            result["text"] = _sanitize_ai_reply(result.get("text", ""), role=role)
            return result
        reason = result.get("reason") or "provider_error"
        err_text = result.get("error") or PROVIDER_ERROR_MESSAGE
        if ai_health is not None and reason in ("provider_error", "empty_answer"):
            etype = ai_health.classify_error_text(err_text) \
                if reason == "provider_error" else "unknown"
            ai_health.mark_failure(provider_name, model_name, etype, err_text)
            logger.info("[AI_ATTEMPT] engine=chat provider=%s model=%s result=%s duration=%.1fs",
                        provider_name, model_name, etype, duration)
        errors.append({
            "provider": provider_name,
            "reason": reason,
            "error": err_text,
        })
    return {
        "ok": False,
        "reason": "provider_error",
        "text": PROVIDER_ERROR_MESSAGE,
        "error": PROVIDER_ERROR_MESSAGE,
        "provider_errors": errors,
    }


async def _legacy_chat_with_failover(messages: list[dict[str, Any]], preferred_provider: str | None = None,
                                     temperature: float = 0.7, max_tokens: int = 1200,
                                     role: str = "user") -> dict[str, Any]:
    """رفتار قدیمی موتور چت (پرچم امنیت): کو‌لوداؤن درون‌حافظه‌ای، بدون سقف زمانی."""
    _ensure_runtime_ready()
    chain = _build_provider_attempt_chain(preferred_provider)
    if not chain:
        return {"ok": False, "reason": "no_provider", "text": PROVIDER_ERROR_MESSAGE, "error": PROVIDER_ERROR_MESSAGE, "provider_errors": []}
    errors = []
    for provider_name in chain:
        result = await _ask_single_provider(provider_name, messages, temperature=temperature, max_tokens=max_tokens)
        if result.get("ok"):
            _clear_provider_cooldown(provider_name)
            result["fallback_used"] = (provider_name != chain[0])
            result["provider_errors"] = errors
            result["text"] = _sanitize_ai_reply(result.get("text", ""), role=role)
            return result
        if result.get("reason") in ("provider_error", "empty_answer"):
            _mark_provider_cooldown(provider_name)
        errors.append({
            "provider": provider_name,
            "reason": result.get("reason") or "provider_error",
            "error": result.get("error") or PROVIDER_ERROR_MESSAGE,
        })
    return {
        "ok": False,
        "reason": "provider_error",
        "text": PROVIDER_ERROR_MESSAGE,
        "error": PROVIDER_ERROR_MESSAGE,
        "provider_errors": errors,
    }

async def chat_with_managed_ai(messages: list[dict[str, Any]], actor_key: str,
                               role: str = "user", channel: str = "site",
                               section: str = "consultant_chat",
                               question_text: str = "",
                               preferred_provider: str | None = None,
                               temperature: float = 0.7,
                               max_tokens: int = 1200,
                               bypass_disabled: bool = False,
                               action: str = "chat") -> dict[str, Any]:
    _ensure_runtime_ready()
    role = (role or "user").strip().lower()
    if role not in ("user", "admin", "super"):
        role = "user"

    if not bypass_disabled and not is_chat_enabled():
        return {"ok": False, "reason": "disabled", "text": OFF_MESSAGE, "error": OFF_MESSAGE}

    access = check_role_access(role, section=section)
    if not access["allowed"]:
        return {"ok": False, "reason": access["reason"], "text": access["message"], "error": access["message"]}

    limit = check_daily_limit(actor_key, role, action=action)
    if not limit["allowed"]:
        return {"ok": False, "reason": "daily_limit", "text": LIMIT_MESSAGE, "error": LIMIT_MESSAGE}

    display_name = get_display_name()
    capabilities = get_role_capabilities(role)

    if role == "super":
        temperature, max_tokens = super_chat_generation_params(question_text, requested_max_tokens=max_tokens)

    guide_text = question_text or ""
    if not guide_text and messages:
        try:
            guide_text = "\n".join(str(m.get("content", "") or "") for m in messages if isinstance(m, dict))
        except Exception:
            guide_text = question_text or ""
    if _is_capability_guide_request(guide_text):
        return {
            "ok": True,
            "text": _sanitize_ai_reply(build_capability_guide(role), role=role),
            "provider": "runtime-policy",
            "model": "deterministic-guide",
            "tokens_used": 0,
            "display_name": display_name,
            "reason": "capability_guide",
        }

    chat_messages = list(messages or [])
    if role == "super":
        try:
            live = build_super_live_stats_block()
            if live:
                chat_messages = [{"role": "system", "content": live}] + chat_messages
                if detect_force_refresh(question_text or guide_text or ""):
                    chat_messages = [{"role": "system", "content": "درخواست تازه است؛ کش/گزارش قدیمی را نادیده بگیر."}] + chat_messages
        except Exception:
            pass

    final_messages = _prepend_runtime_system_message(
        messages=chat_messages,
        role=role,
        access_level=int(access["access_level"] or 0),
        display_name=display_name,
        capabilities_text=capabilities,
    )

    result = await chat_with_failover(
        final_messages,
        preferred_provider=preferred_provider,
        temperature=temperature,
        max_tokens=max_tokens,
        role=role,
    )
    if not result or not result.get("ok"):
        return {
            "ok": False,
            "reason": result.get("reason") if result else "provider_error",
            "text": (result or {}).get("text") or PROVIDER_ERROR_MESSAGE,
            "error": (result or {}).get("error") or PROVIDER_ERROR_MESSAGE,
            "provider_errors": (result or {}).get("provider_errors", []),
        }

    answer_text = _sanitize_ai_reply((result.get("text") or "").strip(), role=role)
    if not answer_text:
        return {
            "ok": False,
            "reason": "empty_answer",
            "text": PROVIDER_ERROR_MESSAGE,
            "error": PROVIDER_ERROR_MESSAGE,
            "provider": result.get("provider") or "",
            "model": result.get("model") or "",
        }

    tokens_used = _extract_tokens_from_result(result, final_messages)
    record_usage(
        actor_key=actor_key,
        role=role,
        channel=channel,
        action=action,
        tokens_used=tokens_used,
        provider_name=result.get("provider") or "",
        model_name=result.get("model") or "",
        question_text=question_text,
        section=section,
    )
    return {
        "ok": True,
        "text": answer_text,
        "provider": result.get("provider") or "",
        "model": result.get("model") or "",
        "tokens_used": tokens_used,
        "display_name": display_name,
        "reason": "ok",
        "fallback_used": bool(result.get("fallback_used")),
        "provider_errors": result.get("provider_errors", []),
    }

async def admin_test_prompt(prompt_text: str, actor_key: str, role: str = "super") -> dict[str, Any]:
    return await chat_with_managed_ai(
        messages=[{"role": "user", "content": prompt_text}],
        actor_key=actor_key,
        role=role,
        channel="admin_test",
        section="admin_test",
        question_text=prompt_text,
        max_tokens=600,
        bypass_disabled=True,
        action="admin_test",
    )

def get_runtime_overview() -> dict[str, Any]:
    _ensure_runtime_ready()
    active_provider = get_active_provider()
    display_name = get_display_name()
    enabled = is_chat_enabled()
    provider_row = None
    try:
        from giso.ai_brain import get_ai_provider
        provider_row = get_ai_provider(active_provider) if active_provider else None
    except Exception:
        provider_row = None

    today_prefix = _today_prefix() + "%"
    stats = {
        "enabled": enabled,
        "active_provider": active_provider,
        "display_name": display_name,
        "selected_model": str(provider_row["selected_model"] or "—") if provider_row else "—",
        "today_users": 0,
        "today_chats": 0,
        "today_tokens": 0,
        "week_users": 0,
        "week_chats": 0,
        "week_tokens": 0,
        "top_questions": [],
    }
    try:
        with _conn() as conn:
            row = conn.execute(
                "SELECT COUNT(DISTINCT actor_key), COUNT(*), COALESCE(SUM(tokens_used),0) FROM giso_ai_usage_stats WHERE action='chat' AND created_at LIKE ?",
                (today_prefix,),
            ).fetchone()
            if row:
                stats["today_users"], stats["today_chats"], stats["today_tokens"] = int(row[0] or 0), int(row[1] or 0), int(row[2] or 0)
            row = conn.execute(
                "SELECT COUNT(DISTINCT actor_key), COUNT(*), COALESCE(SUM(tokens_used),0) FROM giso_ai_usage_stats WHERE action='chat' AND date(created_at) >= date('now', '-6 day')"
            ).fetchone()
            if row:
                stats["week_users"], stats["week_chats"], stats["week_tokens"] = int(row[0] or 0), int(row[1] or 0), int(row[2] or 0)
            qrows = conn.execute(
                """
                SELECT question_text, COUNT(*) AS c
                FROM giso_ai_usage_stats
                WHERE action='chat' AND question_text != ''
                GROUP BY question_text
                ORDER BY c DESC, question_text ASC
                LIMIT 5
                """
            ).fetchall()
            stats["top_questions"] = [(str(r[0]), int(r[1] or 0)) for r in qrows]
    except Exception as e:
        logger.error(f"get_runtime_overview: {e}")
    return stats

def get_provider_status_lines() -> list[str]:
    rows = _provider_rows(only_enabled=False)
    lines = ["🧩 وضعیت Providerها", "━━━━━━━━━━━━━━━━━━━━━━━"]
    if not rows:
        lines.append("هنوز providerی ثبت نشده است.")
        return lines
    active_name = get_active_provider()
    chain = get_failover_chain()
    for idx, row in enumerate(rows, start=1):
        name = str(row["name"] or "")
        status = str(row["last_status"] or "—")
        enabled = "✅" if row["enabled"] else "❌"
        selected = str(row["selected_model"] or "—")
        role_tag = []
        if name == active_name:
            role_tag.append("اصلی")
        if name in chain:
            role_tag.append(f"failover#{chain.index(name)+1}")
        suffix = f" ({' | '.join(role_tag)})" if role_tag else ""
        lines.append(f"{idx}. {enabled} {name}{suffix} — مدل: {selected} — سلامت: {status}")
    return lines

def build_provider_status_report() -> str:
    return "\n".join(get_provider_status_lines())

def get_recent_pending_actions(limit: int = 10) -> list[dict[str, Any]]:
    _ensure_runtime_ready()
    _expire_stale_pending_actions()
    try:
        with _conn() as conn:
            rows = conn.execute(
                "SELECT * FROM giso_ai_pending_actions WHERE status='pending' ORDER BY id DESC LIMIT ?",
                (int(limit),),
            ).fetchall()
        return [dict(r) for r in rows]
    except Exception as e:
        logger.error(f"get_recent_pending_actions: {e}")
        return []

def get_recent_action_logs(limit: int = 10) -> list[dict[str, Any]]:
    _ensure_runtime_ready()
    try:
        with _conn() as conn:
            rows = conn.execute(
                "SELECT * FROM giso_ai_action_logs ORDER BY id DESC LIMIT ?",
                (int(limit),),
            ).fetchall()
        return [dict(r) for r in rows]
    except Exception as e:
        logger.error(f"get_recent_action_logs: {e}")
        return []

def get_recent_rollback_logs(limit: int = 10) -> list[dict[str, Any]]:
    _ensure_runtime_ready()
    try:
        with _conn() as conn:
            rows = conn.execute(
                "SELECT * FROM giso_ai_action_logs WHERE action_name LIKE 'rollback:%' OR status='rolled_back' ORDER BY id DESC LIMIT ?",
                (int(limit),),
            ).fetchall()
        return [dict(r) for r in rows]
    except Exception as e:
        logger.error(f"get_recent_rollback_logs: {e}")
        return []

def build_status_report() -> str:
    stats = get_runtime_overview()
    status_label = "فعال ✅" if stats["enabled"] else "غیرفعال ❌"
    lines = [
        "🤖 مدیریت هوش مصنوعی گیسو",
        "━━━━━━━━━━━━━━━━━━━━━━━",
        f"🔛 وضعیت: {status_label}",
        f"🤖 AI فعال: {stats['active_provider'] or '—'}",
        f"🎯 مدل: {stats['selected_model']}",
        f"🏷 اسم نمایشی: {stats['display_name']}",
        f"🔁 زنجیره failover: {' ← '.join(get_failover_chain()[:5]) if get_failover_chain() else 'ندارد'}",
        "",
        "📈 آمار امروز:",
        f"👥 کاربران استفاده‌کننده: {stats['today_users']}",
        f"💬 کل گفتگوها: {stats['today_chats']}",
        f"🪙 توکن مصرفی: {stats['today_tokens']}",
        "",
        "📊 آمار این هفته:",
        f"👥 کاربران فعال: {stats['week_users']}",
        f"💬 کل گفتگوها: {stats['week_chats']}",
        f"🪙 توکن مصرفی: {stats['week_tokens']}",
        "",
        "🎯 پراستفاده‌ترین سوالات:",
    ]
    if stats["top_questions"]:
        for idx, (q, count) in enumerate(stats["top_questions"], start=1):
            lines.append(f"{idx}. {q[:80]} ({count} بار)")
    else:
        lines.append("هنوز داده‌ای ثبت نشده است.")
    return "\n".join(lines)

def get_widget_usage_stats() -> dict[str, Any]:
    _ensure_runtime_ready()
    stats = {"today_users": 0, "today_messages": 0, "pages": []}
    try:
        prefix = _today_prefix() + "%"
        with _conn() as conn:
            row = conn.execute(
                "SELECT COUNT(DISTINCT actor_key), COUNT(*) FROM giso_ai_usage_stats WHERE action='widget_chat' AND created_at LIKE ?",
                (prefix,),
            ).fetchone()
            if row:
                stats["today_users"] = int(row[0] or 0)
                stats["today_messages"] = int(row[1] or 0)
            rows = conn.execute(
                "SELECT channel, COUNT(*) AS c FROM giso_ai_usage_stats WHERE action='widget_chat' GROUP BY channel ORDER BY c DESC LIMIT 5"
            ).fetchall()
            pages = []
            for row in rows:
                ch = str(row[0] or "")
                page = ch.split("|", 1)[1] if "|" in ch else ch
                pages.append({"page": page or "/", "count": int(row[1] or 0)})
            stats["pages"] = pages
    except Exception as e:
        logger.error(f"get_widget_usage_stats: {e}")
    return stats

def _user_service_snapshot(phone: str = "", site_user_id: int | None = None) -> dict[str, Any]:
    snap = {
        "phone": phone or "",
        "site_user_id": int(site_user_id or 0),
        "analysis_count": 0,
        "order_count": 0,
        "hair_count": 0,
        "ticket_count": 0,
        "consultant_count": 0,
        "has_active_plan": False,
        "has_recent_analysis": False,
        "has_recent_order": False,
        "has_active_hair_order": False,
        "latest_analysis_problem": "",
        "latest_order_name": "",
        "latest_hair_status": "",
        "latest_analysis_id": 0,
        "latest_order_id": 0,
        "latest_hair_id": 0,
        "wallet_cash": 0,
        "wallet_spend": 0,
        "market_listing_count": 0,
        "market_offer_count": 0,
        "center_count": 0,
        "unread_notification_count": 0,
    }
    if not phone and not site_user_id:
        return snap
    try:
        with _conn() as conn:
            if not site_user_id and phone:
                row = conn.execute("SELECT id FROM giso_web_auth WHERE phone=? LIMIT 1", (phone,)).fetchone()
                if row:
                    site_user_id = int(row[0])
                    snap["site_user_id"] = site_user_id
            params = (site_user_id or 0, phone or "")
            snap["analysis_count"] = int((conn.execute("SELECT COUNT(*) FROM analyses WHERE user_id=? OR phone=?", params).fetchone() or [0])[0] or 0)
            snap["order_count"] = int((conn.execute("SELECT COUNT(*) FROM product_orders WHERE user_id=? OR phone=?", params).fetchone() or [0])[0] or 0)
            snap["hair_count"] = int((conn.execute("SELECT COUNT(*) FROM hair_orders WHERE user_id=? OR phone=?", params).fetchone() or [0])[0] or 0)
            snap["consultant_count"] = int((conn.execute("SELECT COUNT(*) FROM consultant_requests WHERE user_id=? OR phone=?", params).fetchone() or [0])[0] or 0)
            snap["ticket_count"] = int((conn.execute("SELECT COUNT(*) FROM giso_support_tickets WHERE phone=?", (phone or "",)).fetchone() or [0])[0] or 0)

            analysis_row = conn.execute(
                "SELECT ai_report_json, plan_json, created_at FROM analyses WHERE user_id=? OR phone=? ORDER BY id DESC LIMIT 1",
                params,
            ).fetchone()
            if analysis_row:
                snap["has_recent_analysis"] = True
                try:
                    aid_row = conn.execute("SELECT id FROM analyses WHERE user_id=? OR phone=? ORDER BY id DESC LIMIT 1", params).fetchone()
                    snap["latest_analysis_id"] = int(aid_row[0] or 0) if aid_row else 0
                except Exception:
                    snap["latest_analysis_id"] = 0
                snap["latest_analysis_problem"] = _extract_main_problem(analysis_row[0] or "{}")
                plan = _jloads(analysis_row[1], {})
                snap["has_active_plan"] = bool(plan)
            order_row = conn.execute(
                "SELECT p.name, po.created_at FROM product_orders po LEFT JOIN products p ON p.id=po.product_id WHERE po.user_id=? OR po.phone=? ORDER BY po.id DESC LIMIT 1",
                params,
            ).fetchone()
            if order_row:
                snap["has_recent_order"] = True
                snap["latest_order_name"] = str(order_row[0] or "")
                try:
                    oid_row = conn.execute("SELECT id FROM product_orders WHERE user_id=? OR phone=? ORDER BY id DESC LIMIT 1", params).fetchone()
                    snap["latest_order_id"] = int(oid_row[0] or 0) if oid_row else 0
                except Exception:
                    snap["latest_order_id"] = 0
            hair_row = conn.execute(
                "SELECT status FROM hair_orders WHERE (user_id=? OR phone=?) AND status NOT IN ('completed','rejected') ORDER BY id DESC LIMIT 1",
                params,
            ).fetchone()
            if hair_row:
                snap["has_active_hair_order"] = True
                snap["latest_hair_status"] = _format_hair_status(hair_row[0])
                try:
                    hid_row = conn.execute("SELECT id FROM hair_orders WHERE (user_id=? OR phone=?) AND status NOT IN ('completed','rejected') ORDER BY id DESC LIMIT 1", params).fetchone()
                    snap["latest_hair_id"] = int(hid_row[0] or 0) if hid_row else 0
                except Exception:
                    snap["latest_hair_id"] = 0
            # کیف پول
            try:
                from giso.wallet_core import get_wallet_balances
                bal = get_wallet_balances(site_user_id or 0) or {}
                snap["wallet_cash"] = int(bal.get("cash", 0) or 0)
                snap["wallet_spend"] = int(bal.get("spend", 0) or 0)
            except Exception:
                pass
            # بازارچه (آگهی‌های کاربر + پیشنهادها)
            try:
                snap["market_listing_count"] = int((conn.execute(
                    "SELECT COUNT(*) FROM hair_listings WHERE seller_user_id=? AND COALESCE(deleted_at, '')=''",
                    (site_user_id or 0,)).fetchone() or [0])[0] or 0)
                snap["market_offer_count"] = int((conn.execute(
                    "SELECT COUNT(*) FROM buyer_offers bo JOIN hair_listings hl ON hl.id=bo.listing_id WHERE hl.seller_user_id=?",
                    (site_user_id or 0,)).fetchone() or [0])[0] or 0)
            except Exception:
                pass
            # مرکز زیبایی
            try:
                snap["center_count"] = int((conn.execute(
                    "SELECT COUNT(*) FROM beauty_centers WHERE owner_user_id=?",
                    (site_user_id or 0,)).fetchone() or [0])[0] or 0)
            except Exception:
                pass
            # اعلان خوانده‌نشده
            try:
                snap["unread_notification_count"] = int((conn.execute(
                    "SELECT COUNT(*) FROM giso_notifications WHERE recipient_id=? AND status='unread'",
                    (site_user_id or 0,)).fetchone() or [0])[0] or 0)
            except Exception:
                pass
    except Exception as e:
        logger.error(f"_user_service_snapshot: {e}")
    return snap

def _recommend_user_next_steps(snapshot: dict[str, Any], role: str = "user") -> list[str]:
    suggestions = []
    if snapshot.get("hair_count", 0) > 0 and snapshot.get("analysis_count", 0) == 0:
        suggestions.append("اگر دوست داری، می‌تونم مسیر تحلیل مو رو هم برات باز کنم تا وضعیت موهات دقیق‌تر بررسی بشه.")
    if snapshot.get("analysis_count", 0) > 0 and snapshot.get("order_count", 0) == 0:
        suggestions.append("اگر بخوای می‌تونم محصولات متناسب با نتیجه تحلیلت رو معرفی کنم.")
    if snapshot.get("analysis_count", 0) > 0 and not snapshot.get("consultant_count", 0):
        suggestions.append("اگه روی برنامه‌ات سوال داری، می‌تونم قدم بعدی مناسب رو باهم مشخص کنیم.")
    if snapshot.get("order_count", 0) > 0 and snapshot.get("ticket_count", 0) == 0:
        suggestions.append("اگر درباره سفارش یا روش استفاده سوالی داری، همین‌جا ازم بپرس تا سریع راهنمایی‌ات کنم.")
    if not suggestions:
        suggestions = [
            "می‌تونم کمک کنم بهترین خدمت بعدی متناسب با وضعیتت را انتخاب کنی.",
            "اگر خواستی، اول خلاصه وضعیتت رو بگم و بعد پیشنهاد قدم بعدی بدم.",
        ]
    return suggestions[:4]

def _recommend_admin_next_steps(stats: dict[str, Any], role: str = "admin") -> list[str]:
    tasks = []
    if int(stats.get("pending_tickets", 0) or 0) > 0:
        tasks.append("اول از همه تیکت‌های بی‌پاسخ را بررسی کن تا backlog کمتر شود.")
    if int(stats.get("pending_consultants", 0) or 0) > 0:
        tasks.append("بعد از تیکت‌ها، درخواست‌های مشاوره در انتظار را اولویت‌بندی کن.")
    if int(stats.get("today_orders", 0) or 0) > 0:
        tasks.append("سفارش‌های جدید امروز را با وضعیت فعلی‌شان مرور کن تا مورد معطل نماند.")
    if int(stats.get("today_hair", 0) or 0) > 0:
        tasks.append("درخواست‌های فروش مو را از نظر وضعیت بررسی کن تا پرونده‌های قدیمی معطل نمانند.")
    if role == "super" and int(stats.get("today_new_users", 0) or 0) > 0:
        tasks.append("روی کاربران جدیدی که هنوز از خدمات استفاده نکرده‌اند تمرکز کن تا تبدیل بهتر شود.")
    if not tasks:
        tasks.append("فعلاً مورد بحرانی دیده نمی‌شود؛ اگر بخوای می‌تونم گزارش جزئی‌تر هم برات بسازم.")
    return tasks[:4]

def _build_user_cta_actions(snapshot: dict[str, Any], page_path: str = "/") -> list[dict[str, str]]:
    actions = []
    if snapshot.get("hair_count", 0) > 0 and snapshot.get("analysis_count", 0) == 0:
        actions.append({"label": "تحلیل مو را شروع کن", "url": "/analysis"})
    if snapshot.get("analysis_count", 0) > 0 and snapshot.get("has_active_plan"):
        aid = int(snapshot.get("latest_analysis_id") or 0)
        actions.append({"label": "برنامه‌ات را ادامه بده", "url": f"/analysis/plan?id={aid}" if aid else "/analysis/plan"})
    if snapshot.get("analysis_count", 0) > 0 and snapshot.get("order_count", 0) == 0:
        actions.append({"label": "محصولات مناسب را ببین", "url": "/shop"})
    if snapshot.get("order_count", 0) > 0:
        actions.append({"label": "سفارش‌ها و گفتگوها را ببین", "url": "/dashboard/chats"})
    if snapshot.get("analysis_count", 0) == 0 and snapshot.get("hair_count", 0) == 0:
        actions.append({"label": "از تحلیل هوشمند شروع کن", "url": "/analysis"})
        actions.append({"label": "اگر خواستی فروش مو را ثبت کن", "url": "/hair-sale"})
    if not actions:
        actions.append({"label": "وضعیت کلی‌ات را ببین", "url": "/dashboard"})
    # حذف تکراری‌ها
    uniq = []
    seen = set()
    for item in actions:
        key = (item["label"], item["url"])
        if key not in seen:
            uniq.append(item)
            seen.add(key)
    return uniq[:4]

def _build_admin_cta_actions(role: str = "admin") -> list[dict[str, str]]:
    actions = [
        {"label": "رفتن به پنل ادمین", "url": "/admin"},
        {"label": "درخواست‌های مشاوره", "url": "/admin/consultants"},
        {"label": "گزارش گفتگوها", "url": "/dashboard/chats"},
    ]
    if role == "super":
        actions.append({"label": "آنالیزهای اخیر", "url": "/admin/analyses"})
    return actions[:4]

def _page_bucket(page_path: str) -> str:
    path = _text_lc(page_path or "/")
    if "/admin" in path:
        return "admin"
    if "/analysis" in path:
        return "analysis"
    if "/shop" in path:
        return "shop"
    if "/hair" in path:
        return "hair"
    if "/support" in path or "/chat" in path:
        return "support"
    if "/dashboard" in path or path.startswith("/my"):
        return "dashboard"
    return "home"

def _page_bucket_label(bucket: str) -> str:
    return {
        "home": "صفحه اصلی",
        "analysis": "بخش تحلیل هوشمند",
        "shop": "فروشگاه",
        "hair": "بخش فروش مو",
        "dashboard": "پنل کاربری",
        "support": "بخش گفتگو و پشتیبانی",
        "admin": "پنل مدیریت",
    }.get(bucket or "home", "سایت گیسو")

def _widget_state_label(state: str) -> str:
    return {
        "guest_home": "مهمان در مسیر شروع",
        "guest_analysis": "مهمانِ علاقه‌مند به تحلیل",
        "guest_shop": "مهمانِ علاقه‌مند به فروشگاه",
        "guest_hair": "مهمانِ علاقه‌مند به فروش مو",
        "registered_no_activity": "ثبت‌نام‌شده بدون سابقه",
        "general_user": "کاربر در مسیر عمومی",
        "hair_only": "کاربر با سابقه فروش مو",
        "analysis_no_shop": "تحلیل انجام‌شده، خرید نشده",
        "shop_only": "سابقه سفارش بدون تحلیل",
        "active_plan": "برنامه فعال در حال پیگیری",
        "admin_operational": "نمای عملیاتی ادمین",
        "super_operational": "نمای مدیریتی سوپرادمین",
    }.get(str(state or "").strip(), "")

def _widget_focus_label(focus: str) -> str:
    return {
        "analysis": "تمرکز: تحلیل و نتیجه",
        "shop": "تمرکز: محصول و خرید",
        "hair": "تمرکز: فروش مو",
        "support": "تمرکز: پیگیری و پشتیبانی",
        "general": "تمرکز: انتخاب مسیر مناسب",
    }.get(str(focus or "").strip(), "")

def _widget_input_placeholder(role: str, page_bucket: str) -> str:
    role = (role or "guest").strip().lower()
    if role == "guest":
        return "مثلاً بپرس از کدام خدمت شروع کنم؟"
    if role == "admin":
        return "مثلاً بپرس اولویت رسیدگی امروز چیست؟"
    if role == "super":
        return "مثلاً بپرس خلاصه وضعیت امروز یا گلوگاه اصلی چیست؟"
    if page_bucket == "analysis":
        return "مثلاً بپرس بعد از تحلیل چه قدمی بهتره؟"
    if page_bucket == "shop":
        return "مثلاً بپرس کدام محصول برای من مناسب‌تره؟"
    if page_bucket == "hair":
        return "مثلاً بپرس برای فروش مو از کجا شروع کنم؟"
    return "پیامت را بنویس..."

def _page_seed_suggestions(role: str, page_bucket: str) -> list[str]:
    role = (role or "guest").strip().lower()
    if role == "guest":
        mapping = {
            "analysis": [
                "برای شروع، بگو تحلیل مو بهتره یا پوست؟",
                "اگر عجله دارم، سریع‌ترین مسیر استفاده از سایت چیه؟",
                "بعد از تحلیل دقیقاً چه کمکی می‌گیرم؟",
            ],
            "shop": [
                "اگر هنوز تحلیل ندارم، خرید را از کجا شروع کنم؟",
                "برای انتخاب محصول مناسب اول چه چیزی را باید بدانم؟",
                "فرق مشاوره با خرید مستقیم در گیسو چیه؟",
            ],
            "hair": [
                "برای فروش مو چه اطلاعاتی لازم دارم؟",
                "اگر هنوز مطمئن نیستم، اول شرایط کلی را بگو.",
                "بعد از ثبت درخواست فروش مو چه اتفاقی می‌افتد؟",
            ],
            "home": [
                "برای من کدام خدمت مناسب‌تر است؟",
                "اگر تازه وارد هستم از کجا شروع کنم؟",
                "خیلی کوتاه خدمات اصلی گیسو را بگو.",
            ],
        }
        return mapping.get(page_bucket, mapping["home"])
    if role in ("admin", "super"):
        mapping = {
            "admin": [
                "خلاصه وضعیت همین بخش را بگو.",
                "بگو الان کدام صف نیاز به رسیدگی دارد؟",
                "اگر بخواهم سریع تصمیم بگیرم از کجا شروع کنم؟",
            ],
            "support": [
                "مکالمه‌ها و تیکت‌های معطل را جمع‌بندی کن.",
                "بگو کدام گفتگوها نیاز به پاسخ سریع‌تر دارند.",
                "اولویت پیگیری امروز را از همین بخش بگو.",
            ],
            "dashboard": [
                "خلاصه وضعیت امروز را سریع بگو.",
                "مهم‌ترین گلوگاه عملیاتی الان چیست؟",
                "از کدام صف رسیدگی را شروع کنم؟",
            ],
        }
        return mapping.get(page_bucket, mapping["dashboard"])
    mapping = {
        "analysis": [
            "بعد از تحلیل چه قدمی برای من بهتره؟",
            "اگر نتیجه تحلیل را نفهمیدم، ساده توضیحش بده.",
            "اول برنامه را ادامه بدهم یا محصول مناسب ببینم؟",
        ],
        "shop": [
            "برای من بهتره اول محصول ببینم یا تحلیل انجام بدهم؟",
            "اگر محصول مناسب می‌خواهم، چه اطلاعاتی بدهم؟",
            "خرید من را با وضعیت مو یا پوستم هماهنگ کن.",
        ],
        "hair": [
            "برای فروش مو از کجا شروع کنم؟",
            "اگر هنوز تحلیل ندارم، قدم بعدی بهتر چیست؟",
            "شرایط ثبت درخواست فروش مو را خلاصه بگو.",
        ],
        "dashboard": [
            "خلاصه وضعیت حساب من را بگو.",
            "الان بهترین قدم بعدی برای من چیست؟",
            "اگر سوالی درباره سفارش یا برنامه‌ام دارم از کجا شروع کنم؟",
        ],
        "home": [
            "برای من مناسب‌ترین شروع کدام خدمت است؟",
            "خیلی کوتاه بگو الان بهتره چه کاری بکنم.",
            "نیازم را چطور سریع‌تر بهت بگویم؟",
        ],
    }
    return mapping.get(page_bucket, mapping["home"])

def _prioritize_actions_by_page(actions: list[dict[str, str]], page_bucket: str, role: str = "user", focus: str = "general") -> list[dict[str, str]]:
    preferred = {
        "analysis": ["/analysis", "/analysis/plan"],
        "shop": ["/shop"],
        "hair": ["/hair-sale"],
        "dashboard": ["/dashboard", "/dashboard/chats"],
        "support": ["/dashboard/chats", "/admin/consultants"],
        "admin": ["/admin", "/admin/consultants", "/admin/analyses"],
        "home": ["/analysis", "/shop", "/hair-sale"],
    }.get(page_bucket or "home", [])
    focus_preferred = {
        "analysis": ["/analysis", "/analysis/plan"],
        "shop": ["/shop"],
        "hair": ["/hair-sale"],
        "support": ["/dashboard/chats", "/admin/consultants"],
    }.get(focus or "general", [])
    ranked = []
    rest = []
    seen = set()
    for item in actions or []:
        if not item or not item.get("url"):
            continue
        key = (item.get("label", ""), item.get("url", ""))
        if key in seen:
            continue
        seen.add(key)
        if any(item["url"].startswith(url) for url in focus_preferred):
            ranked.insert(0, item)
        elif any(item["url"].startswith(url) for url in preferred):
            ranked.append(item)
        else:
            rest.append(item)
    return (ranked + rest)[:4]

def _build_widget_starter_prompts(role: str, page_bucket: str, focus: str = "general", state: str = "") -> list[str]:
    prompts = _page_seed_suggestions(role, page_bucket)
    if focus == "analysis":
        prompts.insert(0, "نتیجه یا قدم بعدی این بخش را ساده بگو.")
    elif focus == "shop":
        prompts.insert(0, "برای انتخاب محصول مناسب، اول چه چیزی را بدهم؟")
    elif focus == "hair":
        prompts.insert(0, "برای فروش مو همین حالا بهترین شروع چیست؟")
    elif focus == "support":
        prompts.insert(0, "اگر سوال یا پیگیری دارم، از کجا ادامه بدهم؟")
    if state == "active_plan":
        prompts.insert(0, "برای ادامه برنامه فعلی‌ام، امروز روی چه چیزی تمرکز کنم؟")
    clean = []
    seen = set()
    for item in prompts:
        s = str(item).strip()
        if s and s not in seen:
            clean.append(s)
            seen.add(s)
    return clean[:4]

def _infer_message_focus(text: str) -> str:
    t = _text_lc(text)
    if any(k in t for k in ("فروش مو", "موهامو بفروشم", "خرید مو")):
        return "hair"
    if any(k in t for k in ("سفارش", "خرید", "محصول", "فروشگاه", "شامپو", "سرم", "ماسک")):
        return "shop"
    if any(k in t for k in ("تیکت", "پشتیبانی", "مشاوره", "پیگیری", "ارتباط")):
        return "support"
    if any(k in t for k in ("تحلیل", "آنالیز", "برنامه", "چک", "مو", "پوست")):
        return "analysis"
    return "general"

def _contextualize_suggestions(base: list[str], role: str, focus: str, context: dict[str, Any]) -> list[str]:
    role = (role or "guest").strip().lower()
    page_bucket = context.get("page_bucket") or _page_bucket(context.get("page_path") or "/")
    state = context.get("state") or ""
    out = _page_seed_suggestions(role, page_bucket) + list(base or [])
    if role == "user":
        snapshot = context.get("snapshot") or {}
        if focus == "analysis" and snapshot.get("analysis_count", 0) == 0:
            out.insert(0, "اگر بخوای، اول از تحلیل هوشمند شروع کنیم تا مسیر مناسب‌ترت روشن شود.")
        elif focus == "shop" and snapshot.get("analysis_count", 0) > 0:
            out.insert(0, "می‌تونم اول محصولات متناسب با نتیجه تحلیلت را برایت مرور کنم.")
        elif focus == "hair":
            out.insert(0, "اگر فروش مو در اولویتته، می‌تونم قدم‌های ثبت درخواست و بعد از آن تحلیل مو را پیشنهاد بدهم.")
        elif state == "active_plan":
            out.insert(0, "اگر بخوای، قدم امروز برنامه‌ات را ساده و سریع جمع‌بندی می‌کنم.")
    elif role in ("admin", "super"):
        if focus == "support":
            out.insert(0, "اگر بخوای از تیکت‌های بی‌پاسخ شروع می‌کنیم و اولویت رسیدگی‌شان را مشخص می‌کنم.")
        elif focus == "shop":
            out.insert(0, "می‌تونم اول سفارش‌های معطل و وضعیت‌های حساس فروشگاه را جمع‌بندی کنم.")
        elif focus == "analysis":
            out.insert(0, "می‌تونم آنالیزهای اخیر و موارد نیازمند پیگیری را یک‌جا برات خلاصه کنم.")
        elif page_bucket == "admin":
            out.insert(0, "اگر بخوای وضعیت کلی این بخش را کوتاه و مدیریتی برات جمع‌بندی می‌کنم.")
    # حذف تکراری
    clean = []
    seen = set()
    for item in out:
        s = str(item).strip()
        if s and s not in seen:
            clean.append(s)
            seen.add(s)
    return clean[:4]

def build_widget_welcome(role: str = "guest", user_name: str = "", page_hint: str = "") -> str:
    role = (role or "guest").strip().lower()
    welcome = get_widget_welcome_message()
    page_label = _page_bucket_label(_page_bucket(page_hint or "/"))
    if role == "guest":
        return f"{welcome}\n\nمن اینجام تا خیلی کوتاه و روشن، بر اساس {page_label} مسیر مناسب رو نشونت بدم."
    if role == "admin":
        return f"سلام {user_name or 'دوست خوبم'} 🌷\nمن اینجام تا خیلی سریع گزارش‌ها، اولویت‌ها و کارهای مرتبط با {page_label} رو برات جمع‌بندی کنم."
    if role == "super":
        return f"سلام {user_name or 'دوست من'} 👑\nمن از همین‌جا می‌تونم وضعیت {page_label} و تصویر کلی گیسو رو مدیریتی برات جمع‌بندی کنم."
    return f"سلام {user_name or 'دوست عزیز'} 🌸\nمن می‌تونم بر اساس {page_label} وضعیتت رو مرور کنم، نیازت رو بفهمم و قدم بعدی مناسب رو پیشنهاد بدم."

def build_site_widget_context(role: str = "guest", phone: str = "", user_name: str = "", page_path: str = "/", user_message: str = "") -> dict[str, Any]:
    role = (role or "guest").strip().lower()
    page_bucket = _page_bucket(page_path or "/")
    focus = _infer_message_focus(user_message or "")
    ctx = {
        "role": role,
        "user_name": user_name or "",
        "phone": phone or "",
        "page_path": page_path or "/",
        "page_bucket": page_bucket,
        "page_title": _page_bucket_label(page_bucket),
        "focus": focus,
        "focus_label": _widget_focus_label(focus),
        "input_placeholder": _widget_input_placeholder(role, page_bucket),
    }
    try:
        with _conn() as conn:
            if role == "guest":
                guest_summaries = {
                    "analysis": "کاربر مهمان در بخش تحلیل است و احتمالاً می‌خواهد بداند از کجا شروع کند یا این خدمت برایش مناسب هست یا نه.",
                    "shop": "کاربر مهمان در فروشگاه است و هنوز نیاز به راهنمایی برای انتخاب مسیر مناسب یا شناخت محصول‌ها دارد.",
                    "hair": "کاربر مهمان در بخش فروش مو است و احتمالاً درباره شرایط، روند ثبت و قدم بعدی سؤال دارد.",
                    "home": "کاربر مهمان هنوز وارد حساب نشده و بیشتر به معرفی سریع خدمات و انتخاب شروع مناسب نیاز دارد.",
                }
                ctx["summary"] = guest_summaries.get(page_bucket, guest_summaries["home"])
                ctx["state"] = f"guest_{page_bucket}"
                ctx["state_label"] = _widget_state_label(ctx["state"])
                ctx["suggestions"] = _contextualize_suggestions([], role, focus or page_bucket, ctx)
                guest_actions = [
                    {"label": "ثبت‌نام", "url": "/register"},
                    {"label": "شروع تحلیل", "url": "/analysis"},
                    {"label": "فروش مو", "url": "/hair-sale"},
                    {"label": "فروشگاه", "url": "/shop"},
                ]
                ctx["actions"] = _prioritize_actions_by_page(guest_actions, page_bucket, role=role, focus=focus)
                ctx["starter_prompts"] = _build_widget_starter_prompts(role, page_bucket, focus=focus, state=ctx["state"])
                return ctx
            if role in ("admin", "super"):
                today = datetime.now().strftime('%Y-%m-%d')
                stats = {
                    "today_new_users": int((conn.execute('SELECT COUNT(*) FROM giso_web_auth WHERE created_at >= ?', (today,)).fetchone() or [0])[0] or 0),
                    "today_orders": int((conn.execute('SELECT COUNT(*) FROM product_orders WHERE created_at >= ?', (today,)).fetchone() or [0])[0] or 0),
                    "pending_tickets": int((conn.execute("SELECT COUNT(*) FROM giso_support_tickets WHERE status IN ('new','reviewing')").fetchone() or [0])[0] or 0),
                    "pending_consultants": int((conn.execute("SELECT COUNT(*) FROM consultant_requests WHERE status IN ('new','reviewing','pending','active')").fetchone() or [0])[0] or 0),
                    "today_hair": int((conn.execute('SELECT COUNT(*) FROM hair_orders WHERE created_at >= ?', (today,)).fetchone() or [0])[0] or 0),
                }
                ctx["summary"] = (
                    f"{ctx['page_title']} | کاربر جدید امروز: {stats['today_new_users']} | سفارش امروز: {stats['today_orders']} | "
                    f"تیکت باز: {stats['pending_tickets']} | مشاوره باز: {stats['pending_consultants']}"
                )
                ctx["state"] = "admin_operational" if role == "admin" else "super_operational"
                ctx["state_label"] = _widget_state_label(ctx["state"])
                ctx["suggestions"] = _contextualize_suggestions(_recommend_admin_next_steps(stats, role=role), role, focus or page_bucket, ctx)
                ctx["actions"] = _prioritize_actions_by_page(_build_admin_cta_actions(role=role), page_bucket, role=role, focus=focus)
                ctx["starter_prompts"] = _build_widget_starter_prompts(role, page_bucket, focus=focus, state=ctx["state"])
                ctx["decision_hints"] = [
                    "اگر بخوای، می‌تونم از همین‌جا گزارش سفارش‌ها یا تیکت‌ها را جمع‌بندی کنم.",
                    "اگر سؤال مبهم باشد، من گزینه‌های منطقی مرحله بعد را پیشنهاد می‌دهم.",
                ]
                return ctx
            web_user = conn.execute("SELECT id, name FROM giso_web_auth WHERE phone=? LIMIT 1", (phone,)).fetchone()
            if web_user:
                if not user_name:
                    ctx["user_name"] = str(web_user[1] or "دوست عزیز")
                uid = int(web_user[0])
                snapshot = _user_service_snapshot(phone=phone, site_user_id=uid)
                ctx["snapshot"] = snapshot
                ctx["summary"] = (
                    f"{ctx['page_title']} | آنالیزها: {snapshot['analysis_count']} | سفارش‌ها: {snapshot['order_count']} | "
                    f"فروش مو: {snapshot['hair_count']} | تیکت‌ها: {snapshot['ticket_count']}"
                )
                if snapshot['hair_count'] > 0 and snapshot['analysis_count'] == 0:
                    ctx["state"] = "hair_only"
                elif snapshot['analysis_count'] > 0 and snapshot['order_count'] == 0:
                    ctx["state"] = "analysis_no_shop"
                elif snapshot['order_count'] > 0 and snapshot['analysis_count'] == 0:
                    ctx["state"] = "shop_only"
                elif snapshot['analysis_count'] > 0 and snapshot['has_active_plan']:
                    ctx["state"] = "active_plan"
                else:
                    ctx["state"] = "general_user"
                ctx["state_label"] = _widget_state_label(ctx["state"])
                base_suggestions = _recommend_user_next_steps(snapshot, role=role)
                ctx["suggestions"] = _contextualize_suggestions(base_suggestions, role, focus or page_bucket, {**ctx, "snapshot": snapshot})
                ctx["actions"] = _prioritize_actions_by_page(_build_user_cta_actions(snapshot, page_path=page_path), page_bucket, role=role, focus=focus)
                ctx["starter_prompts"] = _build_widget_starter_prompts(role, page_bucket, focus=focus, state=ctx["state"])
            else:
                ctx["summary"] = f"{ctx['page_title']} | کاربر وارد شده ولی هنوز سابقه‌ای در گیسو ثبت نشده است."
                ctx["state"] = "registered_no_activity"
                ctx["state_label"] = _widget_state_label(ctx["state"])
                ctx["suggestions"] = _contextualize_suggestions([
                    "اگر بخوای، از تحلیل هوشمند شروع کنیم تا مسیر مناسب‌ترت مشخص بشه.",
                    "می‌تونی از بخش فروش مو یا فروشگاه هم شروع کنی و من راهنمایی‌ات می‌کنم.",
                ], role, focus or page_bucket, ctx)
                ctx["actions"] = _prioritize_actions_by_page([
                    {"label": "شروع تحلیل", "url": "/analysis"},
                    {"label": "فروش مو", "url": "/hair-sale"},
                    {"label": "فروشگاه", "url": "/shop"},
                    {"label": "پنل کاربری", "url": "/dashboard"},
                ], page_bucket, role=role, focus=focus)
                ctx["starter_prompts"] = _build_widget_starter_prompts(role, page_bucket, focus=focus, state=ctx["state"])
    except Exception as e:
        logger.error(f"build_site_widget_context: {e}")
        ctx["summary"] = "فعلاً خلاصه‌ای آماده نیست."
        ctx["suggestions"] = []
        ctx["actions"] = []
        ctx["starter_prompts"] = _build_widget_starter_prompts(role, page_bucket, focus=focus, state=ctx.get("state", ""))
    ctx.setdefault("actions", [])
    ctx.setdefault("state_label", _widget_state_label(ctx.get("state", "")))
    ctx.setdefault("focus_label", _widget_focus_label(ctx.get("focus", focus)))
    ctx.setdefault("starter_prompts", _build_widget_starter_prompts(role, page_bucket, focus=focus, state=ctx.get("state", "")))
    return ctx

def build_user_next_step_hints(phone: str = "", site_user_id: int | None = None) -> list[str]:
    return _recommend_user_next_steps(_user_service_snapshot(phone=phone, site_user_id=site_user_id), role="user")

def build_admin_task_hints(stats: dict[str, Any], role: str = "admin") -> list[str]:
    return _recommend_admin_next_steps(stats, role=role)

def build_site_widget_prompt(role: str, context: dict[str, Any], user_message: str, history: list[dict[str, Any]] | None = None) -> list[dict[str, Any]]:
    role = (role or "guest").strip().lower()
    history = history or []
    history_text = "\n".join(
        f"{'کاربر' if m.get('role') == 'user' else 'مشاور'}: {m.get('content', '')}" for m in history[-6:]
    )
    suggestions = context.get("suggestions") or []
    starters = context.get("starter_prompts") or []
    summary = context.get("summary") or ""
    page_path = context.get("page_path") or "/"
    page_bucket = context.get("page_bucket") or _page_bucket(page_path)
    state = context.get("state") or "unknown"
    focus = context.get("focus") or _infer_message_focus(user_message)
    name = context.get("user_name") or ("دوست من" if role == "super" else "دوست عزیز")
    role_text = {"guest": "مهمان سایت", "user": "کاربر سایت", "admin": "ادمین محدود سایت", "super": "سوپرادمین سایت"}.get(role, "کاربر سایت")
    intro = build_widget_welcome(role, name, page_path)
    profile_line = str(context.get("profile_line") or "").strip()
    personal_notices = [str(x).strip() for x in (context.get("personal_notices") or []) if str(x).strip()]
    if role == "guest":
        allowed = "فقط خدمات سایت را معرفی کن، برای ثبت‌نام و شروع مسیر درست راهنمایی بده و هیچ وعده خارج از گیسو نده."
    elif role == "user":
        allowed = "وضعیت کاربر را توضیح بده، نیازش را شناسایی کن، قدم بعدی را پیشنهاد بده و اگر لازم بود خدمات مرتبط مثل تحلیل، فروش مو یا فروشگاه را معرفی کن."
    elif role == "admin":
        allowed = "مثل یک دستیار مهربان و حرفه‌ای فقط گزارش و راهنمای پیگیری بده و هیچ تغییری روی داده‌ها انجام نده."
    else:
        allowed = "در سایت فقط گزارش و راهنمای مدیریتی بده؛ هیچ اقدام تغییردهنده‌ای از داخل سایت انجام نده و اگر لازم بود پیشنهاد بده در ربات ادامه دهد."
    action_labels = ' | '.join(a.get('label', '') for a in (context.get('actions') or [])) or 'ندارد'
    # شخصی‌سازی لحن بر اساس پروفایل دیتابیسی کاربر (نامداری/بی‌نام، باسابقه/تازه‌وارد)
    persona_hint = ""
    if profile_line:
        persona_hint += f"پروفایل تحلیلی کاربر: {profile_line}\n"
    if personal_notices and role == "user":
        persona_hint += f"نکات شخصی کاربر (در صورت ارتباط، محترمانه و با لحن خودت یادآوری کن): {' | '.join(personal_notices[:3])}\n"
    if profile_line and role == "user":
        persona_hint += "لحن را با سابقه کاربر در گیسو تنظیم کن: تازه‌وارد = ساده و راهنما؛ باسابقه = دقیق و همراه.\n"
    prompt = (
        f"نقش فعلی: {role_text}\n"
        f"نام مخاطب: {name}\n"
        f"صفحه فعلی سایت: {page_path}\n"
        f"دسته صفحه: {page_bucket}\n"
        f"تمرکز پیام: {focus or 'general'}\n"
        f"وضعیت تشخیصی کاربر: {state}\n"
        f"خلاصه وضعیت: {summary}\n"
        f"{persona_hint}"
        f"پیشنهادهای مناسب: {' | '.join(suggestions) if suggestions else 'ندارد'}\n"
        f"پرامپت‌های شروع مناسب: {' | '.join(starters) if starters else 'ندارد'}\n"
        f"اقدام‌های پیشنهادی: {action_labels}\n"
        f"قواعد رفتاری: {allowed}\n"
        "قوانین سخت:\n"
        "۱. فقط درباره خدمات گیسو صحبت کن\n"
        "۲. اگر سؤال خارج از این موضوعات بود:\n"
        "   «این سؤال خارج از حوزه گیسوست.\n"
        "   می‌تونم درباره مو، پوست، فروشگاه،\n"
        "   آنالیز یا کیف پولت کمک کنم.»\n"
        "۳. هرگز درمان قطعی ادعا نکن\n"
        "۴. هرگز اطلاعات شخصی کاربر را تکرار نکن\n"
        "۵. حدس نزن؛ اگر اطلاعات کافی نیست فقط یک سؤال کوتاه بپرس\n"
        "۶. پیشنهاد پایانی همیشه مرتبط با صفحه فعلی کاربر باشد\n"
        "لحن: دوستانه، انسانی، خوش‌بیان، مطمئن و کوتاه.\n"
        f"پیام خوش‌آمد مرجع: {intro}\n"
        "پاسخ را حداکثر در ۴ خط بده؛ اول نیاز کاربر را روشن کن، بعد اگر لازم بود یک سوال کوتاه بپرس، و در پایان فقط یک قدم بعدی واضح و مرتبط با صفحه فعلی پیشنهاد کن.\n"
        "اگر کاربر مردد بود، کمکش کن بین تحلیل، فروش مو، فروشگاه یا پیگیری، مسیر مناسب را انتخاب کند.\n"
        f"تاریخچه کوتاه:\n{history_text or 'شروع گفتگو'}\n\n"
        f"پیام جدید کاربر:\n{user_message}"
    )
    return [{"role": "user", "content": prompt}]

def build_site_widget_fallback_reply(role: str, context: dict[str, Any], user_message: str, reason: str = "") -> str:
    role = (role or "guest").strip().lower()
    focus = context.get("focus") or _infer_message_focus(user_message)
    page_bucket = context.get("page_bucket") or _page_bucket(context.get("page_path") or "/")
    page_title = context.get("page_title") or _page_bucket_label(page_bucket)
    suggestions = [str(x).strip() for x in (context.get("suggestions") or []) if str(x).strip()]
    actions = [a for a in (context.get("actions") or []) if isinstance(a, dict) and a.get("label")]
    opener = {
        "guest": f"برای اینکه معطل نشی، از روی {page_title} کوتاه راهنمایی‌ات می‌کنم.",
        "user": f"برای اینکه گفتگو قطع نشه، از روی وضعیت فعلی‌ات در {page_title} سریع جمع‌بندی می‌دم.",
        "admin": f"برای اینکه کارت عقب نیفته، از روی وضعیت {page_title} جمع‌بندی کوتاه می‌دم.",
        "super": f"برای اینکه روندت قطع نشه، از روی وضعیت {page_title} خلاصه مدیریتی می‌دم.",
    }.get(role, f"از روی {page_title} یک راهنمای کوتاه می‌دم.")
    lines = [opener]
    if role == "guest":
        if focus == "analysis":
            lines.append("اگر هدفت شناخت دقیق وضعیت مو یا پوستته، بهترین شروع تحلیل هوشمنده.")
        elif focus == "shop":
            lines.append("اگر هنوز مطمئن نیستی چه محصولی مناسبته، بهتره اول نیازت را مشخص کنیم و بعد وارد خرید شوی.")
        elif focus == "hair":
            lines.append("اگر روی فروش مو تمرکز داری، اول شرایط و روند ثبت را مرور کن و بعد درخواستت را ثبت کن.")
        else:
            lines.append("اگر هدفت را خیلی کوتاه بگویی، می‌توانم بین تحلیل، فروش مو و فروشگاه مسیر مناسب‌تر را پیشنهاد بدهم.")
    elif role == "user":
        state = context.get("state") or "general_user"
        if state == "active_plan":
            lines.append("الان بهترین استفاده از مشاور اینه که قدم بعدی برنامه‌ات را با وضعیت فعلی‌ات هماهنگ کنیم.")
        elif state == "analysis_no_shop":
            lines.append("چون سابقه تحلیل داری، مسیر مناسب اینه که نتیجه را به اقدام بعدی یا انتخاب محصول درست وصل کنیم.")
        elif state == "shop_only":
            lines.append("چون سابقه سفارش داری، می‌توانیم روی پیگیری، روش استفاده یا انتخاب مرحله بعدی تمرکز کنیم.")
        elif state == "hair_only":
            lines.append("چون فروش مو داشته‌ای، می‌توانیم هم درباره پیگیری آن حرف بزنیم و هم اگر خواستی مسیر تحلیل را باز کنیم.")
        else:
            lines.append("اگر هدفت را یک‌خطی بگویی، من سریع‌تر دقیق می‌گویم قدم بعدی‌ات چیست.")
    else:
        lines.append("در این بخش می‌توانم خلاصه وضعیت، اولویت رسیدگی و نزدیک‌ترین اقدام مفید را جمع‌بندی کنم.")
    if suggestions:
        lines.append(f"پیشنهاد من: {suggestions[0]}")
    elif actions:
        lines.append(f"پیشنهاد من: از «{actions[0].get('label')}» شروع کن.")
    if actions:
        lines.append(f"قدم بعدی واضح: «{actions[0].get('label')}»")
    return "\n".join(lines[:4])

def _format_elapsed(ts_text: str) -> str:
    if not ts_text:
        return "نامشخص"
    try:
        dt = datetime.strptime(str(ts_text)[:19], "%Y-%m-%d %H:%M:%S")
        diff = datetime.now() - dt
        hours = int(diff.total_seconds() // 3600)
        if hours < 1:
            minutes = max(1, int(diff.total_seconds() // 60))
            return f"{minutes} دقیقه"
        if hours < 24:
            return f"{hours} ساعت"
        days = max(1, diff.days)
        return f"{days} روز"
    except Exception:
        return str(ts_text)

def _extract_main_problem(report_json: str) -> str:
    data = _jloads(report_json, {})
    if not isinstance(data, dict):
        return "نیاز به بررسی بیشتر"
    for key in ("main_problem", "problem", "status_label", "summary"):
        val = data.get(key)
        if isinstance(val, str) and val.strip():
            return val.strip()[:80]
    problems = data.get("main_problems") or data.get("concerns") or []
    if isinstance(problems, list) and problems:
        first = problems[0]
        if isinstance(first, dict):
            return str(first.get("title") or first.get("problem") or first.get("name") or "نیاز به بررسی بیشتر")[:80]
        return str(first)[:80]
    return "نیاز به بررسی بیشتر"

def _extract_plan_progress(plan_json: str, checklist_json: str) -> tuple[str, str]:
    plan = _jloads(plan_json, {})
    progress = _jloads(checklist_json, {})
    week_text = ""
    checklist_text = ""
    if isinstance(plan, dict):
        total_weeks = 0
        if isinstance(plan.get("weekly_plan"), list):
            total_weeks = len(plan.get("weekly_plan") or [])
        elif isinstance(plan.get("weekly_plans"), list):
            total_weeks = len(plan.get("weekly_plans") or [])
        elif plan.get("duration_weeks"):
            try:
                total_weeks = int(plan.get("duration_weeks") or 0)
            except Exception:
                total_weeks = 0
        if total_weeks > 0:
            week_text = f"هفته 1 از {total_weeks}"
    if isinstance(progress, dict) and progress:
        total = len(progress)
        done = sum(1 for v in progress.values() if v)
        remaining = max(0, total - done)
        checklist_text = f"{remaining} کار مونده"
    return week_text, checklist_text

def _format_hair_status(status: str) -> str:
    mapping = {
        "pending": "در انتظار بررسی",
        "reviewing": "در حال بررسی",
        "priced": "قیمت‌گذاری شده",
        "approved": "تأیید شده",
        "rejected": "رد شده",
        "completed": "تکمیل شده",
    }
    return mapping.get(str(status or "").strip(), str(status or "نامشخص"))

def _get_user_scenario_payload(user_id: int) -> dict[str, Any]:
    payload = {
        "user_name": "دوست عزیز",
        "phone": "",
        "has_activity": False,
        "recent_order": None,
        "active_hair_order": None,
        "recent_analysis": None,
        "recent_support": 0,
    }
    try:
        with _conn() as conn:
            user_row = conn.execute(
                "SELECT phone, first_name FROM giso_users WHERE bale_id=? LIMIT 1",
                (str(user_id),),
            ).fetchone()
            if user_row:
                payload["phone"] = str(user_row[0] or "")
                if str(user_row[1] or "").strip():
                    payload["user_name"] = str(user_row[1]).strip()
            phone = payload["phone"]
            site_user_id = None
            if phone:
                web_row = conn.execute(
                    "SELECT id, name FROM giso_web_auth WHERE phone=? LIMIT 1",
                    (phone,),
                ).fetchone()
                if web_row:
                    site_user_id = web_row[0]
                    if str(web_row[1] or "").strip():
                        payload["user_name"] = str(web_row[1]).strip()

            query_params = []
            user_clause = []
            if site_user_id is not None:
                user_clause.append("user_id=?")
                query_params.append(site_user_id)
            if phone:
                user_clause.append("phone=?")
                query_params.append(phone)

            if user_clause:
                clause = " OR ".join(user_clause)
                payload["has_activity"] = bool(conn.execute(
                    f"SELECT 1 FROM analyses WHERE {clause} LIMIT 1",
                    query_params,
                ).fetchone())
                if not payload["has_activity"]:
                    payload["has_activity"] = bool(conn.execute(
                        f"SELECT 1 FROM product_orders WHERE {clause} LIMIT 1",
                        query_params,
                    ).fetchone())
                if not payload["has_activity"]:
                    payload["has_activity"] = bool(conn.execute(
                        f"SELECT 1 FROM hair_orders WHERE {clause} LIMIT 1",
                        query_params,
                    ).fetchone())

                order_row = conn.execute(
                    f"""
                    SELECT po.id, po.created_at, p.name
                    FROM product_orders po
                    LEFT JOIN products p ON p.id = po.product_id
                    WHERE ({clause}) AND datetime(po.created_at) >= datetime('now', '-1 day')
                    ORDER BY po.id DESC LIMIT 1
                    """,
                    query_params,
                ).fetchone()
                if order_row:
                    payload["recent_order"] = {
                        "id": int(order_row[0]),
                        "created_at": str(order_row[1] or ""),
                        "product_name": str(order_row[2] or "محصول"),
                    }

                hair_row = conn.execute(
                    f"""
                    SELECT id, status, created_at
                    FROM hair_orders
                    WHERE ({clause}) AND status NOT IN ('completed', 'rejected')
                    ORDER BY id DESC LIMIT 1
                    """,
                    query_params,
                ).fetchone()
                if hair_row:
                    payload["active_hair_order"] = {
                        "id": int(hair_row[0]),
                        "status": _format_hair_status(hair_row[1]),
                        "created_at": str(hair_row[2] or ""),
                    }

                analysis_row = conn.execute(
                    f"""
                    SELECT id, type, created_at, ai_report_json, plan_json, checklist_progress
                    FROM analyses
                    WHERE ({clause}) AND datetime(created_at) >= datetime('now', '-7 day')
                    ORDER BY id DESC LIMIT 1
                    """,
                    query_params,
                ).fetchone()
                if analysis_row:
                    week_text, checklist_text = _extract_plan_progress(analysis_row[4] or "", analysis_row[5] or "")
                    payload["recent_analysis"] = {
                        "id": int(analysis_row[0]),
                        "type": "مو" if str(analysis_row[1] or "hair") == "hair" else "صورت",
                        "created_at": str(analysis_row[2] or ""),
                        "main_problem": _extract_main_problem(analysis_row[3] or "{}"),
                        "week_text": week_text,
                        "checklist_text": checklist_text,
                    }

                try:
                    ticket_row = conn.execute(
                        f"SELECT COUNT(*) FROM giso_support_tickets WHERE ({clause})",
                        query_params,
                    ).fetchone()
                    payload["recent_support"] = int(ticket_row[0] or 0) if ticket_row else 0
                except Exception:
                    pass
    except Exception as e:
        logger.error(f"_get_user_scenario_payload({user_id}): {e}")
    return payload

def _get_admin_scenario_payload(user_id: int, role: str) -> dict[str, Any]:
    payload = {
        "name": "مدیر",
        "today_new_users": 0,
        "today_orders": 0,
        "today_hair": 0,
        "today_tickets": 0,
        "today_consultants": 0,
        "pending_tickets": 0,
        "pending_consultants": 0,
        "sales_today": 0,
        "assigned_tickets": 0,
    }
    try:
        with _conn() as conn:
            row = conn.execute("SELECT first_name FROM giso_users WHERE bale_id=? LIMIT 1", (str(user_id),)).fetchone()
            if row and str(row[0] or "").strip():
                payload["name"] = str(row[0]).strip()
            today = datetime.now().strftime('%Y-%m-%d')
            payload["today_new_users"] = int((conn.execute("SELECT COUNT(*) FROM giso_web_auth WHERE created_at >= ?", (today,)).fetchone() or [0])[0] or 0)
            payload["today_orders"] = int((conn.execute("SELECT COUNT(*) FROM product_orders WHERE created_at >= ?", (today,)).fetchone() or [0])[0] or 0)
            payload["today_hair"] = int((conn.execute("SELECT COUNT(*) FROM hair_orders WHERE created_at >= ?", (today,)).fetchone() or [0])[0] or 0)
            payload["today_tickets"] = int((conn.execute("SELECT COUNT(*) FROM giso_support_tickets WHERE created_at >= ?", (today,)).fetchone() or [0])[0] or 0)
            payload["today_consultants"] = int((conn.execute("SELECT COUNT(*) FROM consultant_requests WHERE created_at >= ?", (today,)).fetchone() or [0])[0] or 0)
            payload["pending_tickets"] = int((conn.execute("SELECT COUNT(*) FROM giso_support_tickets WHERE status IN ('new','reviewing')").fetchone() or [0])[0] or 0)
            payload["pending_consultants"] = int((conn.execute("SELECT COUNT(*) FROM consultant_requests WHERE status IN ('new','reviewing','pending','active')").fetchone() or [0])[0] or 0)
            payload["assigned_tickets"] = int((conn.execute("SELECT COUNT(*) FROM giso_support_tickets WHERE admin_bale_id=?", (str(user_id),)).fetchone() or [0])[0] or 0)
            sales_row = conn.execute(
                """
                SELECT COALESCE(SUM(COALESCE(p.price, 0)), 0)
                FROM product_orders po
                LEFT JOIN products p ON p.id = po.product_id
                WHERE po.created_at >= ?
                """,
                (today,),
            ).fetchone()
            payload["sales_today"] = int(sales_row[0] or 0) if sales_row else 0
    except Exception as e:
        logger.error(f"_get_admin_scenario_payload({user_id}, {role}): {e}")
    return payload

def get_smart_welcome_context(user_id: int | str, role: str) -> dict[str, Any]:
    _ensure_runtime_ready()
    role = (role or "user").strip().lower()
    uid = int(user_id)
    button_allowed = check_role_access("super" if role == "super" else ("admin" if role == "admin" else "user"), section="consultant_chat").get("allowed", False)

    if role == "super":
        info = _get_admin_scenario_payload(uid, role)
        next_steps = _recommend_admin_next_steps(info, role="super")
        lines = [
            "👑 سلام سوپرادمین!",
            "",
            "📊 گزارش سریع امروز:",
            "━━━━━━━━━━━━━━━",
            f"👥 کاربر جدید: {info['today_new_users']}",
            f"🛒 سفارش‌های جدید: {info['today_orders']}",
            f"💇 درخواست فروش مو: {info['today_hair']}",
            f"📮 تیکت جدید: {info['today_tickets']}",
            f"💰 فروش امروز: {info['sales_today']:,} تومان" if info['sales_today'] else "💰 فروش امروز: 0 تومان",
            "━━━━━━━━━━━━━━━",
        ]
        alerts = []
        if info['pending_consultants']:
            alerts.append(f"• {info['pending_consultants']} درخواست مشاور در انتظار")
        if info['pending_tickets']:
            alerts.append(f"• {info['pending_tickets']} تیکت اولویت‌دار")
        if alerts:
            lines += ["", "⚠️ نیاز به توجه:"] + alerts
        if next_steps:
            lines += ["", "🎯 پیشنهاد قدم بعدی:"] + [f"• {x}" for x in next_steps[:2]]
        lines += ["", "💬 می‌خوای گزارش دقیق‌تر بگیری؟"]
        return {"scenario": "super_admin", "text": "\n".join(lines), "show_button": button_allowed}

    if role == "admin":
        info = _get_admin_scenario_payload(uid, role)
        next_steps = _recommend_admin_next_steps(info, role="admin")
        lines = [
            f"👋 سلام {info['name'] or 'ادمین'}!",
            "",
            "📊 وضعیت کاری:",
            "━━━━━━━━━━━",
            f"📮 تیکت‌های واگذار شده: {info['assigned_tickets']}",
            f"   • {info['pending_tickets']} در انتظار پاسخ",
            f"📋 درخواست‌های امروز: {info['today_consultants']}",
            "━━━━━━━━━━━",
        ]
        if next_steps:
            lines += ["", "🎯 بهتره از اینجا شروع کنی:"] + [f"• {x}" for x in next_steps[:2]]
        lines += ["", "💬 دستیار هوشمند کمکت کنه؟"]
        return {"scenario": "admin", "text": "\n".join(lines), "show_button": button_allowed}

    info = _get_user_scenario_payload(uid)
    snap = _user_service_snapshot(phone=info.get("phone") or "")
    next_steps = _recommend_user_next_steps(snap, role="user")
    name = info.get("user_name") or "دوست عزیز"
    if not info.get("has_activity"):
        lines = [
            "🌸 سلام و خوش اومدی به گیسو!",
            "",
            "من مشاور هوشمند گیسو هستم 💫",
            "یک دستیار شخصی برای مراقبت از مو و پوستت.",
            "",
            "می‌تونم کمکت کنم:",
            "✨ آنالیز حرفه‌ای مو و پوست",
            "📋 برنامه اختصاصی مراقبت",
            "🛍 پیشنهاد محصولات مناسب",
            "💬 پاسخ به سوالاتت",
            "",
            "برای شروع، از منوی زیر انتخاب کن یا با من گفتگو کن 👇",
        ]
        return {"scenario": "new_user", "text": "\n".join(lines), "show_button": button_allowed}

    if info.get("recent_order"):
        order = info["recent_order"]
        lines = [
            f"سلام {name}! 🎁 خوش اومدی به گیسو",
            "",
            "✅ حساب کاربریت فعاله؛ اینم خلاصهٔ وضعیتت:",
            f"🛍 سفارش {order['product_name']} ثبت شد ✅",
            "",
            "💫 چند نکته مهم:",
            "• بهترین زمان استفاده",
            "• روش صحیح استفاده",
            "• ترکیب با محصولات دیگه",
        ]
        if next_steps:
            lines += ["", "🎯 پیشنهاد من:", f"• {next_steps[0]}"]
        lines += ["", "💬 هر سوالی داری از مشاور هوشمند گیسو بپرس؛ هوشمند و سریع جواب می‌گیره 👇"]
        return {"scenario": "recent_order", "text": "\n".join(lines), "show_button": button_allowed}

    if info.get("active_hair_order"):
        hair = info["active_hair_order"]
        lines = [
            f"سلام {name}! 🌸",
            "",
            "درخواست فروش موت در حال بررسی هست ⏳",
            f"وضعیت فعلی: {hair['status']}",
        ]
        if next_steps:
            lines += ["", "🎯 پیشنهاد من:", f"• {next_steps[0]}"]
        lines += ["", "💬 هر سوالی داری از مشاور هوشمند گیسو بپرس؛ هوشمند و سریع جواب می‌گیره 👇"]
        return {"scenario": "active_hair_order", "text": "\n".join(lines), "show_button": button_allowed}

    if info.get("recent_analysis"):
        ana = info["recent_analysis"]
        lines = [
            f"سلام {name}! 🌸",
            "",
            f"دیدم آنالیز {ana['type']}ت رو انجام دادی 👏",
            "",
            "📊 خلاصه:",
            f"• نتیجه: {ana['main_problem']}",
        ]
        if ana.get("week_text"):
            lines.append(f"• برنامه: {ana['week_text']}")
        if ana.get("checklist_text"):
            lines.append(f"• چک‌لیست امروز: {ana['checklist_text']}")
        if next_steps:
            lines += ["", "🎯 پیشنهاد قدم بعدی:", f"• {next_steps[0]}"]
        lines += ["", "💬 هر سوالی داری از مشاور هوشمند گیسو بپرس؛ هوشمند و سریع جواب می‌گیره 👇"]
        return {"scenario": "recent_analysis", "text": "\n".join(lines), "show_button": button_allowed}

    lines = [
        f"سلام {name}! 🌸 خوش برگشتی!",
        "",
        "✅ عضو سایت گیسو هستی؛ اینم خلاصهٔ وضعیتت:",
        "📊 وضعیت تو:",
    ]
    ana = info.get("recent_analysis")
    if ana:
        if ana.get("week_text"):
            lines.append(f"• برنامه: {ana['week_text']}")
        if ana.get("checklist_text"):
            lines.append(f"• چک‌لیست امروز: {ana['checklist_text']}")
        lines.append(f"• آخرین آنالیز: {_format_elapsed(ana.get('created_at') or '')} پیش")
    else:
        lines.append("• هنوز می‌تونی یک مسیر مراقبتی تازه شروع کنی")
    if next_steps:
        lines += ["", "🎯 پیشنهاد من برای الان:", f"• {next_steps[0]}"]
    lines += ["", "💬 هر سوالی داری از مشاور هوشمند گیسو بپرس؛ هوشمند و سریع جواب می‌گیره 👇"]
    return {"scenario": "returning_user", "text": "\n".join(lines), "show_button": button_allowed}

SUPPORTED_SUPER_ACTIONS = {
    "report_dashboard": {"kind": "report", "table": "multiple", "description": "گزارش سریع مدیریتی"},
    "report_orders": {"kind": "report", "table": "product_orders", "description": "گزارش سفارش‌ها"},
    "report_users": {"kind": "report", "table": "giso_web_auth", "description": "گزارش کاربران"},
    "report_tickets": {"kind": "report", "table": "giso_support_tickets", "description": "گزارش تیکت‌ها"},
    "report_consultants": {"kind": "report", "table": "consultant_requests", "description": "گزارش درخواست‌های مشاوره"},
    "report_hair_orders": {"kind": "report", "table": "hair_orders", "description": "گزارش فروش مو"},
    "report_analyses": {"kind": "report", "table": "analyses", "description": "گزارش آنالیزها"},
    "report_user_summary": {"kind": "report", "table": "multiple", "description": "خلاصه کاربر"},
    "report_ai_status": {"kind": "report", "table": "multiple", "description": "گزارش وضعیت هوش مصنوعی"},
    "report_seo": {"kind": "report", "table": "multiple", "description": "گزارش امکان‌سنجی سئو"},
    "update_order_status": {"kind": "action", "table": "product_orders", "reversible": True, "description": "تغییر وضعیت سفارش"},
    "update_ticket_status": {"kind": "action", "table": "giso_support_tickets", "reversible": True, "description": "تغییر وضعیت تیکت"},
    "update_consultant_status": {"kind": "action", "table": "consultant_requests", "reversible": True, "description": "تغییر وضعیت مشاوره"},
    "update_hair_order_status": {"kind": "action", "table": "hair_orders", "reversible": True, "description": "تغییر وضعیت فروش مو"},
    "update_product_price": {"kind": "action", "table": "products", "reversible": True, "description": "تغییر قیمت محصول"},
    "update_product_stock": {"kind": "action", "table": "products", "reversible": True, "description": "تغییر موجودی محصول"},
    "delete_product": {"kind": "action", "table": "products", "reversible": True, "description": "حذف محصول"},
    "delete_user_data": {"kind": "action", "table": "multiple", "reversible": True, "description": "حذف اطلاعات کاربر"},
    "set_chat_enabled": {"kind": "action", "table": "giso_ai_settings", "reversible": True, "description": "روشن/خاموش کردن مشاور هوشمند"},
    "set_display_name": {"kind": "action", "table": "giso_ai_settings", "reversible": True, "description": "تغییر اسم نمایشی مشاور"},
    "set_active_provider": {"kind": "action", "table": "giso_ai_settings", "reversible": True, "description": "تغییر AI فعال"},
}
SUPPORTED_SUPER_ACTIONS.update(INSPECTOR_REPORT_ACTIONS)

ACTION_SCOPE_HINTS = {
    "report_dashboard": "reports",
    "report_orders": "orders",
    "report_users": "users_edit",
    "report_tickets": "tickets",
    "report_consultants": "consultants",
    "report_hair_orders": "consultants",
    "report_analyses": "reports",
    "report_user_summary": "users_edit",
    "report_ai_status": "reports",
    "report_seo": "reports",
    "update_order_status": "orders",
    "update_ticket_status": "tickets",
    "update_consultant_status": "consultants",
    "update_hair_order_status": "consultants",
    "update_product_price": "products_edit",
    "update_product_stock": "products_edit",
    "delete_product": "products_edit",
    "delete_user_data": "users_edit",
    "set_chat_enabled": "reports",
    "set_display_name": "reports",
    "set_active_provider": "reports",
}
ACTION_SCOPE_HINTS.update(INSPECTOR_REPORT_SCOPES)

def _find_product_match(conn, text: str):
    text_l = _text_lc(text)
    rows = conn.execute("SELECT id, name, price, in_stock FROM products ORDER BY id DESC LIMIT 100").fetchall()
    for row in rows:
        name = _text_lc(row["name"] or "")
        if name and name in text_l:
            return row
    return None

def _status_from_text(text: str, table: str) -> str | None:
    t = _text_lc(text)
    mappings = {
        "product_orders": [
            ("در حال پردازش", "processing"),
            ("پردازش", "processing"),
            ("ارسال", "processing"),
            ("تکمیل", "completed"),
            ("در انتظار", "pending"),
            ("تایید", "processing"),
            ("تأیید", "processing"),
            ("لغو", "cancelled"),
            ("رد", "cancelled"),
        ],
        "giso_support_tickets": [
            ("ببند", "closed"), ("بسته", "closed"), ("حل", "closed"),
            ("پاسخ", "replied"), ("بررسی", "reviewing"), ("جدید", "new"),
        ],
        "consultant_requests": [
            ("ببند", "closed"), ("بسته", "closed"), ("چت", "chatting"),
            ("بررسی", "reviewing"), ("جدید", "new"),
        ],
        "hair_orders": [
            ("تکمیل", "completed"), ("رد", "rejected"), ("لغو", "rejected"),
            ("قیمت", "priced"), ("تایید", "approved"), ("تأیید", "approved"),
            ("بررسی", "reviewing"), ("در انتظار", "pending"),
        ],
    }
    for needle, value in mappings.get(table, []):
        if needle in t:
            return value
    return None

def _policy_for_action(action_name: str, role: str) -> tuple[bool, str]:
    role = (role or "user").strip().lower()
    if role != "super":
        return False, POLICY_DENIED_MESSAGE
    if action_name not in SUPPORTED_SUPER_ACTIONS:
        return False, NOT_DEFINED_MESSAGE
    scope = ACTION_SCOPE_HINTS.get(action_name, "")
    access = check_role_access(role, section=scope or "consultant_chat")
    if not access.get("allowed"):
        return False, access.get("message") or POLICY_DENIED_MESSAGE
    return True, ""

def _log_action(actor_key: str, actor_role: str, action_name: str, target_table: str = "",
                target_id: int = 0, request_text: str = "", args: dict | None = None,
                snapshot: dict | None = None, result: dict | None = None,
                status: str = "created", approved: bool = False, error_text: str = "",
                approved_at: str = "", executed_at: str = "") -> int:
    _ensure_runtime_ready()
    with _conn() as conn:
        cur = conn.execute(
            """
            INSERT INTO giso_ai_action_logs
            (actor_key, actor_role, action_name, target_table, target_id, request_text,
             args_json, snapshot_json, result_json, status, approved, error_text,
             created_at, approved_at, executed_at)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                actor_key, actor_role, action_name, target_table, int(target_id or 0), request_text,
                json.dumps(args or {}, ensure_ascii=False),
                json.dumps(snapshot or {}, ensure_ascii=False),
                json.dumps(result or {}, ensure_ascii=False),
                status, 1 if approved else 0, error_text or "", _now_str(), approved_at or "", executed_at or "",
            ),
        )
        conn.commit()
        return int(cur.lastrowid or 0)

def _create_pending_action(actor_key: str, actor_role: str, action_name: str, target_table: str,
                           target_id: int, args: dict, snapshot: dict, preview_text: str,
                           request_text: str) -> int:
    _ensure_runtime_ready()
    created_at = _now_str()
    expires_at = _pending_expires_at_str()
    with _conn() as conn:
        cur = conn.execute(
            """
            INSERT INTO giso_ai_pending_actions
            (actor_key, actor_role, action_name, target_table, target_id, args_json, snapshot_json,
             preview_text, request_text, status, created_at, expires_at)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                actor_key, actor_role, action_name, target_table, int(target_id or 0),
                json.dumps(args or {}, ensure_ascii=False),
                json.dumps(snapshot or {}, ensure_ascii=False),
                preview_text, request_text, "pending", created_at, expires_at,
            ),
        )
        conn.commit()
        return int(cur.lastrowid or 0)

def _get_pending_action(pending_id: int, actor_key: str = "") -> dict[str, Any]:
    _ensure_runtime_ready()
    _expire_stale_pending_actions(pending_id=int(pending_id))
    try:
        with _conn() as conn:
            row = conn.execute("SELECT * FROM giso_ai_pending_actions WHERE id=?", (int(pending_id),)).fetchone()
        data = _safe_dict(row)
        if actor_key and data and data.get("actor_key") != actor_key:
            return {}
        return data
    except Exception:
        return {}

def _set_pending_status(pending_id: int, status: str):
    try:
        with _conn() as conn:
            conn.execute("UPDATE giso_ai_pending_actions SET status=? WHERE id=?", (status, int(pending_id)))
            conn.commit()
    except Exception:
        pass

def _report_dashboard(for_inject: bool = False) -> str:
    header = "آمار زنده دیتابیس (حدس نزن؛ فقط همین اعداد):" if for_inject else "📊 گزارش سریع مدیریتی گیسو"
    lines = [header, "━━━━━━━━━━━━━━━━━━━━━━━"]
    try:
        with _conn() as conn:
            today = datetime.now().strftime('%Y-%m-%d')
            q = lambda sql, params=(): int((conn.execute(sql, params).fetchone() or [0])[0] or 0)
            open_tickets = q("SELECT COUNT(*) FROM giso_support_tickets WHERE status IN ('new','reviewing','open')")
            today_tickets = q("SELECT COUNT(*) FROM giso_support_tickets WHERE created_at >= ?", (today,))
            open_consultants = q("SELECT COUNT(*) FROM consultant_requests WHERE status IN ('new','reviewing','pending','active')")
            today_users = q("SELECT COUNT(*) FROM giso_web_auth WHERE created_at >= ?", (today,))
            today_orders = q("SELECT COUNT(*) FROM product_orders WHERE created_at >= ?", (today,))
            today_analyses = q("SELECT COUNT(*) FROM analyses WHERE created_at >= ?", (today,))
            today_hair = q("SELECT COUNT(*) FROM hair_orders WHERE created_at >= ?", (today,))
            sales_row = conn.execute(
                "SELECT COALESCE(SUM(COALESCE(p.price, 0)), 0) FROM product_orders po "
                "LEFT JOIN products p ON p.id = po.product_id WHERE po.created_at >= ?",
                (today,),
            ).fetchone()
            sales_today = int(sales_row[0] or 0) if sales_row else 0
            open_errors = 0
            try:
                open_errors = q("SELECT COUNT(*) FROM giso_system_errors WHERE status='open'")
            except Exception:
                open_errors = 0
            ai_name = get_active_provider() or "—"
            ai_model = "—"
            ai_health = "نامشخص"
            try:
                from giso.ai_brain import get_ai_provider
                prow = get_ai_provider(ai_name) if ai_name and ai_name != "—" else None
                if prow:
                    ai_model = str(prow["selected_model"] or "—")
                    st = str(prow["last_status"] or "").strip() or "نامشخص"
                    ai_health = st
            except Exception:
                pass
            lines.extend([
                f"👥 کاربران جدید امروز: {today_users}",
                f"🛒 سفارش‌های امروز: {today_orders}",
                f"💰 فروش امروز: {sales_today:,} تومان",
                f"🔬 آنالیزهای امروز: {today_analyses}",
                f"💇 فروش مو امروز: {today_hair}",
                f"🎫 تیکت امروز: {today_tickets} | تیکت باز: {open_tickets}",
                f"💬 مشاوره معطل: {open_consultants}",
                f"🐞 خطاهای باز سیستم: {open_errors}",
                f"🤖 AI فعال: {ai_name} / {ai_model} | سلامت: {ai_health}",
            ])
    except Exception as e:
        lines.append(f"⚠️ خطا در ساخت گزارش: {e}")
    return "\n".join(lines[:12] if for_inject else lines)

def _report_rows(title: str, rows: list[dict], formatter):
    lines = [title, "━━━━━━━━━━━━━━━━━━━━━━━"]
    if not rows:
        lines.append("موردی پیدا نشد.")
        return "\n".join(lines)
    for idx, row in enumerate(rows, start=1):
        lines.append(formatter(idx, row))
    return "\n".join(lines)

def _report_recent_orders(limit: int = 10) -> str:
    try:
        with _conn() as conn:
            rows = [dict(r) for r in conn.execute(
                "SELECT po.id, po.customer_name, po.phone, po.status, po.created_at, p.name AS product_name "
                "FROM product_orders po LEFT JOIN products p ON p.id=po.product_id ORDER BY po.id DESC LIMIT ?",
                (int(limit),),
            ).fetchall()]
        return _report_rows("🛒 سفارش‌های اخیر", rows, lambda i, r: f"{i}. سفارش #{r['id']} | {r.get('product_name') or '—'} | {r.get('customer_name') or '—'} | {r.get('status') or '—'}")
    except Exception as e:
        return f"⚠️ خطا در گزارش سفارش‌ها: {e}"

def _report_recent_users(limit: int = 10) -> str:
    try:
        with _conn() as conn:
            rows = [dict(r) for r in conn.execute(
                "SELECT id, phone, name, created_at FROM giso_web_auth ORDER BY id DESC LIMIT ?",
                (int(limit),),
            ).fetchall()]
        return _report_rows("👥 کاربران اخیر سایت", rows, lambda i, r: f"{i}. #{r['id']} | {r.get('name') or '—'} | {r.get('phone') or '—'}")
    except Exception as e:
        return f"⚠️ خطا در گزارش کاربران: {e}"

def _report_tickets(limit: int = 10, open_only: bool = False) -> str:
    try:
        with _conn() as conn:
            if open_only:
                rows = [dict(r) for r in conn.execute(
                    "SELECT id, user_name, phone, status, created_at FROM giso_support_tickets "
                    "WHERE status IN ('new','reviewing','open') ORDER BY id DESC LIMIT ?",
                    (int(limit),),
                ).fetchall()]
                title = "🎫 تیکت‌های باز"
            else:
                rows = [dict(r) for r in conn.execute(
                    "SELECT id, user_name, phone, status, created_at FROM giso_support_tickets ORDER BY id DESC LIMIT ?",
                    (int(limit),),
                ).fetchall()]
                title = "🎫 تیکت‌های پشتیبانی"
        return _report_rows(title, rows, lambda i, r: f"{i}. تیکت #{r['id']} | {r.get('user_name') or 'کاربر'} | {r.get('status') or '—'}")
    except Exception as e:
        return f"⚠️ خطا در گزارش تیکت‌ها: {e}"

def _report_consultants(limit: int = 10, pending_only: bool = False) -> str:
    try:
        with _conn() as conn:
            if pending_only:
                rows = [dict(r) for r in conn.execute(
                    "SELECT id, customer_name, phone, status, created_at FROM consultant_requests "
                    "WHERE status IN ('new','reviewing','pending','active') ORDER BY id DESC LIMIT ?",
                    (int(limit),),
                ).fetchall()]
                title = "💬 درخواست‌های مشاوره معطل"
            else:
                rows = [dict(r) for r in conn.execute(
                    "SELECT id, customer_name, phone, status, created_at FROM consultant_requests ORDER BY id DESC LIMIT ?",
                    (int(limit),),
                ).fetchall()]
                title = "💬 درخواست‌های مشاوره"
        return _report_rows(title, rows, lambda i, r: f"{i}. درخواست #{r['id']} | {r.get('customer_name') or 'کاربر'} | {r.get('status') or '—'}")
    except Exception as e:
        return f"⚠️ خطا در گزارش مشاوره: {e}"

def _report_seo_feasibility() -> str:
    """گزارش سئو کم‌ریسک: وضعیت فعلی بدون بازنویسی انبوه یا پینگ GSC."""
    lines = [
        "🔎 سئو — امکان‌سنجی و وضعیت فعلی",
        "━━━━━━━━━━━━━━━━━━━━━━━",
        "✅ از قبل فعال (بدون فشار اضافه):",
        "• /sitemap.xml از فروشگاه + بازارچه + مراکز زیبایی",
        "• /robots.txt با Disallow /admin و لینک Sitemap",
        "• JSON-LD/meta صفحات عمومی موجود",
        "",
        "⛔ اجرا نشده (ریسک/بار سرور بالا):",
        "• بازنویسی خودکار meta همهٔ صفحات با AI در لحظه",
        "• پینگ Search Console / ایندکس انبوه",
        "• کرالر کلیدواژهٔ زنده روی هر درخواست",
        "",
        "اقدام کم‌ریسک پیشنهادی: در ساعات کم‌ترافیک فقط از شغل دوره‌ای موجود برای پیشنهاد متن استفاده شود؛ روی صفحات عمومی چیزی را خودکار بازنویسی نکن.",
    ]
    return "\n".join(lines)

def _report_hair_orders(limit: int = 10) -> str:
    try:
        with _conn() as conn:
            rows = [dict(r) for r in conn.execute(
                "SELECT id, customer_name, phone, status, created_at FROM hair_orders ORDER BY id DESC LIMIT ?",
                (int(limit),),
            ).fetchall()]
        return _report_rows("💇 درخواست‌های فروش مو", rows, lambda i, r: f"{i}. درخواست #{r['id']} | {r.get('customer_name') or 'کاربر'} | {r.get('status') or '—'}")
    except Exception as e:
        return f"⚠️ خطا در گزارش فروش مو: {e}"

def _report_analyses(limit: int = 10) -> str:
    try:
        with _conn() as conn:
            rows = [dict(r) for r in conn.execute(
                "SELECT id, phone, type, created_at FROM analyses ORDER BY id DESC LIMIT ?",
                (int(limit),),
            ).fetchall()]
        return _report_rows("🔬 آنالیزهای اخیر", rows, lambda i, r: f"{i}. آنالیز #{r['id']} | {r.get('type') or '—'} | {r.get('phone') or '—'}")
    except Exception as e:
        return f"⚠️ خطا در گزارش آنالیزها: {e}"

def _report_user_summary(phone: str) -> str:
    phone = _extract_phone_from_text(phone)
    if not phone:
        return NEED_MORE_DETAIL_MESSAGE
    lines = [f"👤 خلاصه کاربر {phone}", "━━━━━━━━━━━━━━━━━━━━━━━"]
    try:
        with _conn() as conn:
            user = conn.execute("SELECT id, name, created_at FROM giso_web_auth WHERE phone=? LIMIT 1", (phone,)).fetchone()
            if not user:
                return "کاربری با این شماره پیدا نشد."
            uid = int(user[0])
            lines.append(f"نام: {user[1] or '—'}")
            lines.append(f"عضویت: {user[2] or '—'}")
            counts = {
                "analyses": int((conn.execute("SELECT COUNT(*) FROM analyses WHERE user_id=? OR phone=?", (uid, phone)).fetchone() or [0])[0] or 0),
                "orders": int((conn.execute("SELECT COUNT(*) FROM product_orders WHERE user_id=? OR phone=?", (uid, phone)).fetchone() or [0])[0] or 0),
                "hair": int((conn.execute("SELECT COUNT(*) FROM hair_orders WHERE user_id=? OR phone=?", (uid, phone)).fetchone() or [0])[0] or 0),
                "tickets": int((conn.execute("SELECT COUNT(*) FROM giso_support_tickets WHERE phone=?", (phone,)).fetchone() or [0])[0] or 0),
                "consultants": int((conn.execute("SELECT COUNT(*) FROM consultant_requests WHERE user_id=? OR phone=?", (uid, phone)).fetchone() or [0])[0] or 0),
            }
            lines.extend([
                f"آنالیزها: {counts['analyses']}",
                f"سفارش‌ها: {counts['orders']}",
                f"فروش مو: {counts['hair']}",
                f"تیکت‌ها: {counts['tickets']}",
                f"مشاوره‌ها: {counts['consultants']}",
            ])
    except Exception as e:
        return f"⚠️ خطا در گزارش کاربر: {e}"
    return "\n".join(lines)

def _report_ai_status() -> str:
    return build_status_report()

def _get_table_columns(conn, table: str) -> list[str]:
    return [r[1] for r in conn.execute(f"PRAGMA table_info({table})").fetchall()]

def _insert_snapshot_row(conn, table: str, row: dict[str, Any]) -> None:
    if not row:
        return
    cols = _get_table_columns(conn, table)
    use_cols = [c for c in cols if c in row]
    if not use_cols:
        return
    placeholders = ", ".join(["?" for _ in use_cols])
    conn.execute(
        f"INSERT INTO {table} ({', '.join(use_cols)}) VALUES ({placeholders})",
        [row.get(c) for c in use_cols],
    )

def _snapshot_user_bundle(conn, phone: str, site_user_id: int | None = None) -> dict[str, Any]:
    phone = _extract_phone_from_text(phone)
    site_user = None
    if site_user_id:
        site_user = conn.execute("SELECT * FROM giso_web_auth WHERE id=?", (int(site_user_id),)).fetchone()
    if site_user is None and phone:
        site_user = conn.execute("SELECT * FROM giso_web_auth WHERE phone=?", (phone,)).fetchone()
    if site_user:
        site_user_id = int(site_user["id"])
        phone = phone or str(site_user["phone"] or "")
    # سقف context دستیار: فقط ۲۰ رکورد آخر هر جدول (LIMIT + ORDER BY).
    # giso_users در دیتابیس سایت ستون id ندارد (کلید bale_id است).
    giso_users = []
    if phone:
        try:
            order = "ORDER BY id DESC" if "id" in _get_table_columns(conn, "giso_users") else ""
            giso_users = [dict(r) for r in conn.execute(
                f"SELECT * FROM giso_users WHERE phone=? {order} LIMIT 20", (phone,)
            ).fetchall()]
        except Exception:
            giso_users = []
    consultant_rows = [dict(r) for r in conn.execute("SELECT * FROM consultant_requests WHERE user_id=? OR phone=? ORDER BY id DESC LIMIT 20", (site_user_id or 0, phone or "")).fetchall()] if (site_user_id or phone) else []
    consultant_ids = [int(r["id"]) for r in consultant_rows]
    consultant_messages = []
    if consultant_ids:
        q = ",".join("?" for _ in consultant_ids)
        consultant_messages = [dict(r) for r in conn.execute(f"SELECT * FROM consultant_messages WHERE request_id IN ({q}) ORDER BY id DESC LIMIT 20", consultant_ids).fetchall()]
    bundle = {
        "phone": phone,
        "site_user_id": int(site_user_id or 0),
        "giso_web_auth": [dict(site_user)] if site_user else [],
        "giso_users": giso_users,
        "analyses": [dict(r) for r in conn.execute("SELECT * FROM analyses WHERE user_id=? OR phone=? ORDER BY id DESC LIMIT 20", (site_user_id or 0, phone or "")).fetchall()] if (site_user_id or phone) else [],
        "product_orders": [dict(r) for r in conn.execute("SELECT * FROM product_orders WHERE user_id=? OR phone=? ORDER BY id DESC LIMIT 20", (site_user_id or 0, phone or "")).fetchall()] if (site_user_id or phone) else [],
        "hair_orders": [dict(r) for r in conn.execute("SELECT * FROM hair_orders WHERE user_id=? OR phone=? ORDER BY id DESC LIMIT 20", (site_user_id or 0, phone or "")).fetchall()] if (site_user_id or phone) else [],
        "giso_support_tickets": [dict(r) for r in conn.execute("SELECT * FROM giso_support_tickets WHERE phone=? ORDER BY id DESC LIMIT 20", (phone,)).fetchall()] if phone else [],
        "consultant_requests": consultant_rows,
        "consultant_messages": consultant_messages,
        "product_requests": [dict(r) for r in conn.execute("SELECT * FROM product_requests WHERE user_id=? OR phone=? ORDER BY id DESC LIMIT 20", (site_user_id or 0, phone or "")).fetchall()] if (site_user_id or phone) else [],
        "reviews": [dict(r) for r in conn.execute("SELECT * FROM reviews WHERE user_id=? OR phone=? ORDER BY id DESC LIMIT 20", (site_user_id or 0, phone or "")).fetchall()] if (site_user_id or phone) else [],
    }
    return bundle

def _restore_user_bundle(conn, bundle: dict[str, Any]) -> None:
    phone = bundle.get("phone") or ""
    site_user_id = int(bundle.get("site_user_id") or 0)
    if phone:
        conn.execute("DELETE FROM giso_users WHERE phone=?", (phone,))
        conn.execute("DELETE FROM giso_support_tickets WHERE phone=?", (phone,))
    if site_user_id or phone:
        conn.execute("DELETE FROM analyses WHERE user_id=? OR phone=?", (site_user_id, phone))
        conn.execute("DELETE FROM product_orders WHERE user_id=? OR phone=?", (site_user_id, phone))
        conn.execute("DELETE FROM hair_orders WHERE user_id=? OR phone=?", (site_user_id, phone))
        conn.execute("DELETE FROM consultant_requests WHERE user_id=? OR phone=?", (site_user_id, phone))
        conn.execute("DELETE FROM product_requests WHERE user_id=? OR phone=?", (site_user_id, phone))
        conn.execute("DELETE FROM reviews WHERE user_id=? OR phone=?", (site_user_id, phone))
    if site_user_id:
        conn.execute("DELETE FROM giso_web_auth WHERE id=?", (site_user_id,))
    elif phone:
        conn.execute("DELETE FROM giso_web_auth WHERE phone=?", (phone,))

    for table in ("giso_web_auth", "giso_users", "analyses", "product_orders", "hair_orders", "giso_support_tickets", "consultant_requests", "consultant_messages", "product_requests", "reviews"):
        for row in bundle.get(table, []):
            _insert_snapshot_row(conn, table, row)

def _build_action_preview(plan: dict[str, Any]) -> str:
    action_name = plan.get("action_name") or "action"
    desc = SUPPORTED_SUPER_ACTIONS.get(action_name, {}).get("description") or action_name
    target_label = plan.get("target_label") or plan.get("target_table") or "مورد"
    details = plan.get("details_text") or ""
    return (
        f"⚠️ پیش‌نمایش اقدام هوشمند\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"اقدام: {desc}\n"
        f"هدف: {target_label}\n"
        f"جزئیات: {details}\n"
        f"اعتبار تأیید: {PENDING_ACTION_TTL_MINUTES} دقیقه\n\n"
        f"اگر تأیید کنی، این تغییر روی دیتابیس اعمال می‌شود."
    )

def _build_superadmin_action_plan(request_text: str) -> dict[str, Any]:
    text = _clean_text(request_text)
    text_l = text.lower()

    force_refresh = detect_force_refresh(text)

    if any(x in text_l for x in ("سئو", "sitemap", "robots", "کلمات کلیدی")):
        return {"kind": "report", "action_name": "report_seo", "force_refresh": force_refresh}

    if _insp := detect_inspector_report(text_l):
        return {"kind": "report", "action_name": _insp, "force_refresh": force_refresh}

    if _is_capability_guide_request(text) or _is_smalltalk_request(text) or _looks_like_general_management_chat(text):
        return {"kind": "chat"}

    # تنظیمات AI / مدیریت هوش مصنوعی
    if ("هوش مصنوعی" in text_l or "مشاور" in text_l or " ai " in f" {text_l} ") and any(x in text_l for x in ("وضعیت", "گزارش", "آمار")):
        return {"kind": "report", "action_name": "report_ai_status"}
    if ("هوش مصنوعی" in text_l or "مشاور" in text_l) and any(x in text_l for x in ("خاموش", "غیرفعال")):
        return {
            "kind": "action", "action_name": "set_chat_enabled", "target_table": "giso_ai_settings",
            "target_id": 0, "args": {"enabled": False}, "target_label": "مشاور هوشمند گیسو",
            "details_text": "غیرفعال کردن چت هوشمند",
        }
    if ("هوش مصنوعی" in text_l or "مشاور" in text_l) and any(x in text_l for x in ("روشن", "فعال")):
        return {
            "kind": "action", "action_name": "set_chat_enabled", "target_table": "giso_ai_settings",
            "target_id": 0, "args": {"enabled": True}, "target_label": "مشاور هوشمند گیسو",
            "details_text": "فعال کردن چت هوشمند",
        }
    if ("اسم" in text_l or "نام" in text_l) and ("مشاور" in text_l or "هوش مصنوعی" in text_l):
        new_name = _extract_name_candidate(text)
        if not new_name:
            return {"kind": "need_more_detail", "message": "اسم جدید را دقیق‌تر بگو تا برایت تنظیمش کنم."}
        return {
            "kind": "action", "action_name": "set_display_name", "target_table": "giso_ai_settings",
            "target_id": 0, "args": {"display_name": new_name}, "target_label": "اسم نمایشی مشاور",
            "details_text": f"تغییر اسم به {new_name}",
        }
    provider_name = _extract_provider_candidate(text)
    if provider_name and ("ai" in text_l or "هوش" in text_l or "پروایدر" in text_l or "مدل" in text_l):
        return {
            "kind": "action", "action_name": "set_active_provider", "target_table": "giso_ai_settings",
            "target_id": 0, "args": {"provider_name": provider_name}, "target_label": "AI فعال گفتگو",
            "details_text": f"تغییر AI فعال به {provider_name}",
        }

    # حذف داده کاربر
    if "حذف" in text_l and "کاربر" in text_l:
        phone = _extract_phone_from_text(text)
        target_id = _extract_id_from_text(text)
        if not phone and not target_id:
            return {"kind": "need_more_detail", "message": "برای حذف کاربر، شماره یا شناسه دقیق را بفرست تا اشتباه نشود."}
        return {
            "kind": "action", "action_name": "delete_user_data", "target_table": "multiple",
            "target_id": target_id or 0, "args": {"phone": phone, "site_user_id": target_id or 0},
            "target_label": phone or f"کاربر #{target_id}", "details_text": "حذف اطلاعات کاربر از دیتابیس گیسو",
        }

    # حذف محصول
    if "حذف" in text_l and "محصول" in text_l:
        target_id = _extract_id_from_text(text)
        return {
            "kind": "action", "action_name": "delete_product", "target_table": "products",
            "target_id": target_id or 0, "args": {"match_text": text},
            "target_label": f"محصول #{target_id}" if target_id else "محصول تشخیص‌داده‌شده", "details_text": "حذف محصول از فروشگاه",
        }

    # تغییر وضعیت سفارش فروشگاه
    if "سفارش" in text_l and any(x in text_l for x in ("تایید", "تأیید", "رد", "لغو", "ارسال", "پردازش", "تکمیل", "وضعیت")):
        target_id = _extract_id_from_text(text)
        status = _status_from_text(text, "product_orders")
        if not target_id or not status:
            return {"kind": "need_more_detail", "message": NEED_MORE_DETAIL_MESSAGE}
        return {
            "kind": "action", "action_name": "update_order_status", "target_table": "product_orders",
            "target_id": target_id, "args": {"status": status},
            "target_label": f"سفارش #{target_id}", "details_text": f"تغییر وضعیت به {status}",
        }

    # تیکت
    if "تیکت" in text_l and any(x in text_l for x in ("ببند", "بسته", "پاسخ", "بررسی", "وضعیت", "جدید")):
        target_id = _extract_id_from_text(text)
        status = _status_from_text(text, "giso_support_tickets")
        if not target_id or not status:
            return {"kind": "need_more_detail", "message": NEED_MORE_DETAIL_MESSAGE}
        return {
            "kind": "action", "action_name": "update_ticket_status", "target_table": "giso_support_tickets",
            "target_id": target_id, "args": {"status": status},
            "target_label": f"تیکت #{target_id}", "details_text": f"تغییر وضعیت به {status}",
        }

    # مشاوره
    if ("مشاوره" in text_l or "مشاور" in text_l) and any(x in text_l for x in ("ببند", "بسته", "چت", "بررسی", "جدید", "وضعیت")):
        target_id = _extract_id_from_text(text)
        status = _status_from_text(text, "consultant_requests")
        if not target_id or not status:
            return {"kind": "need_more_detail", "message": NEED_MORE_DETAIL_MESSAGE}
        return {
            "kind": "action", "action_name": "update_consultant_status", "target_table": "consultant_requests",
            "target_id": target_id, "args": {"status": status},
            "target_label": f"درخواست مشاوره #{target_id}", "details_text": f"تغییر وضعیت به {status}",
        }

    # فروش مو
    if "فروش مو" in text_l and any(x in text_l for x in ("تایید", "تأیید", "رد", "لغو", "بررسی", "قیمت", "تکمیل", "وضعیت")):
        target_id = _extract_id_from_text(text)
        status = _status_from_text(text, "hair_orders")
        if not target_id or not status:
            return {"kind": "need_more_detail", "message": NEED_MORE_DETAIL_MESSAGE}
        return {
            "kind": "action", "action_name": "update_hair_order_status", "target_table": "hair_orders",
            "target_id": target_id, "args": {"status": status},
            "target_label": f"درخواست فروش مو #{target_id}", "details_text": f"تغییر وضعیت به {status}",
        }

    # قیمت محصول
    if "محصول" in text_l and "قیمت" in text_l:
        target_id = _extract_id_from_text(text)
        amount = _extract_amount_from_text(text)
        return {
            "kind": "action", "action_name": "update_product_price", "target_table": "products",
            "target_id": target_id or 0, "args": {"new_price": amount or 0, "match_text": text},
            "target_label": f"محصول #{target_id}" if target_id else "محصول تشخیص‌داده‌شده", "details_text": f"تغییر قیمت به {amount or 'نامشخص'}",
        }

    # موجود/ناموجود محصول
    if "محصول" in text_l and any(x in text_l for x in ("ناموجود", "موجود", "موجودی")):
        target_id = _extract_id_from_text(text)
        in_stock = False if "ناموجود" in text_l else True
        return {
            "kind": "action", "action_name": "update_product_stock", "target_table": "products",
            "target_id": target_id or 0, "args": {"in_stock": in_stock, "match_text": text},
            "target_label": f"محصول #{target_id}" if target_id else "محصول تشخیص‌داده‌شده", "details_text": "تغییر وضعیت موجودی",
        }

    if any(x in text_l for x in ("گزارش", "آمار", "وضعیت", "لیست", "خلاصه")):
        if "کاربر" in text_l and _extract_phone_from_text(text):
            return {"kind": "report", "action_name": "report_user_summary", "phone": _extract_phone_from_text(text)}
        if "کاربر" in text_l:
            return {"kind": "report", "action_name": "report_users"}
        if "تیکت" in text_l:
            open_only = any(x in text_l for x in ("باز", "معطل", "بی‌پاسخ", "بي پاسخ"))
            return {"kind": "report", "action_name": "report_tickets", "open_only": open_only, "force_refresh": force_refresh}
        if "مشاور" in text_l or "مشاوره" in text_l:
            pending_only = any(x in text_l for x in ("معطل", "صف", "باز", "در انتظار", "pending"))
            return {"kind": "report", "action_name": "report_consultants", "pending_only": pending_only, "force_refresh": force_refresh}
        if ("مو" in text_l and "فروش" in text_l) or "hair" in text_l:
            return {"kind": "report", "action_name": "report_hair_orders", "force_refresh": force_refresh}
        if "آنالیز" in text_l or "تحلیل" in text_l:
            return {"kind": "report", "action_name": "report_analyses", "force_refresh": force_refresh}
        if "سفارش" in text_l or "خرید" in text_l:
            return {"kind": "report", "action_name": "report_orders", "force_refresh": force_refresh}
        return {"kind": "report", "action_name": "report_dashboard", "force_refresh": force_refresh}

    if any(x in text_l for x in ("کد تخفیف", "پیام گروهی")):
        return {"kind": "need_more_detail", "message": "این بخش را هنوز به action امن وصل نکرده‌ام؛ اگر بخوای می‌تونم فعلاً گزارش و پیش‌نیازهایش را برات جمع‌بندی کنم."}

    if any(x in text_l for x in ("بلاک", "مسدود")):
        return {"kind": "need_more_detail", "message": "در ساختار فعلی گیسو فیلد مسدودسازی مستقیم کاربر نداریم. اگر بخوای می‌تونم اطلاعات کاربر را بیارم یا حذف کاملش را با تأیید دو مرحله‌ای انجام بدهم."}

    if any(x in text_l for x in ("تحلیل", "خرید", "سفارش", "تیکت", "کاربر", "محصول", "فروش مو", "مشاوره", "گزارش", "آمار", "هوش مصنوعی", "مشاور")):
        return {"kind": "chat"}

    return {"kind": "chat"}

def process_superadmin_request(actor_id: int | str, actor_phone: str, request_text: str,
                               actor_key: str = "", channel: str = "bot") -> dict[str, Any]:
    role = resolve_actor_role(user_id=actor_id, phone=actor_phone, is_admin=True)
    if role != "super":
        return {"handled": True, "mode": "message", "text": POLICY_DENIED_MESSAGE}
    actor_key = str(actor_key or f"bot:{actor_id}").strip()[:120]

    plan = _build_superadmin_action_plan(request_text)
    kind = plan.get("kind")
    if kind == "chat":
        return {"handled": False}
    if kind == "need_more_detail":
        return {"handled": True, "mode": "message", "text": plan.get("message") or NEED_MORE_DETAIL_MESSAGE}
    if kind in ("outside_scope", "not_defined", "policy_denied"):
        return {"handled": False}

    action_name = plan.get("action_name") or ""
    allowed, err = _policy_for_action(action_name, role)
    if not allowed:
        return {"handled": True, "mode": "message", "text": err}

    if kind == "report":
        report_text = execute_superadmin_report(action_name, plan)
        extra = {}
        if plan.get("force_refresh"):
            extra["fresh"] = True
            if not report_text.startswith("🔄"):
                report_text = "🔄 گزارش تازه از دیتابیس زنده (کش نادیده گرفته شد)\n" + report_text
        if action_name == "report_insights":
            try:
                from giso.monitoring_insights import list_insights
                extra["insights"] = [
                    {"id": int(it["id"]), "title": str(it.get("title") or "")[:120], "severity": it.get("severity") or ""}
                    for it in (list_insights(status="new", limit=8) or [])
                ]
            except Exception:
                extra["insights"] = []
        _log_action(
            actor_key=actor_key, actor_role=role, action_name=action_name,
            target_table=SUPPORTED_SUPER_ACTIONS.get(action_name, {}).get("table", ""),
            request_text=request_text, args=plan, result={"text": report_text},
            status="report_ok", approved=True, approved_at=_now_str(), executed_at=_now_str(),
        )
        return {"handled": True, "mode": "report", "text": report_text, **extra}

    if kind == "action":
        snapshot, normalized_plan, err = prepare_superadmin_action_plan(plan)
        if err:
            return {"handled": True, "mode": "message", "text": err}
        preview_text = _build_action_preview(normalized_plan)
        pending_id = _create_pending_action(
            actor_key=actor_key, actor_role=role,
            action_name=normalized_plan["action_name"], target_table=normalized_plan.get("target_table", ""),
            target_id=int(normalized_plan.get("target_id") or 0), args=normalized_plan.get("args") or {},
            snapshot=snapshot, preview_text=preview_text, request_text=request_text,
        )
        return {"handled": True, "mode": "pending", "pending_id": pending_id, "text": preview_text}

    return {"handled": False}

def execute_superadmin_report(action_name: str, plan: dict[str, Any]) -> str:
    force = bool(plan.get("force_refresh"))
    if action_name == "report_dashboard":
        return _report_dashboard()
    if action_name == "report_orders":
        return _report_recent_orders()
    if action_name == "report_users":
        return _report_recent_users()
    if action_name == "report_tickets":
        return _report_tickets(open_only=bool(plan.get("open_only")))
    if action_name == "report_consultants":
        return _report_consultants(pending_only=bool(plan.get("pending_only")))
    if action_name == "report_hair_orders":
        return _report_hair_orders()
    if action_name == "report_analyses":
        return _report_analyses()
    if action_name == "report_ai_status":
        return _report_ai_status()
    if action_name == "report_user_summary":
        return _report_user_summary(plan.get("phone") or plan.get("request_text") or "")
    if action_name == "report_seo":
        return _report_seo_feasibility()
    if action_name in INSPECTOR_REPORT_ACTIONS:
        if force and action_name == "report_incidents":
            try:
                from giso.monitoring_errors import get_or_refresh_text_report
                get_or_refresh_text_report(force=True)
            except Exception:
                pass
        return inspector_report(action_name)
    return NOT_DEFINED_MESSAGE

def prepare_superadmin_action_plan(plan: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any], str]:
    action_name = plan.get("action_name") or ""
    target_id = int(plan.get("target_id") or 0)
    args = dict(plan.get("args") or {})
    # امنیت: جدول هدف فقط از وایت‌لیست اقدام‌های پشتیبانی‌شده می‌آید؛
    # مقدار پیشنهادی پلنِ تولیدشده توسط مدل زبانی اعتبارسنجی می‌شود تا در کوئری تزریق نشود.
    known_tables = {v.get("table", "") for v in SUPPORTED_SUPER_ACTIONS.values()}
    known_tables.discard("multiple")  # «multiple» جدول واقعی نیست
    table = str(plan.get("target_table") or "")
    if table not in known_tables:
        table = SUPPORTED_SUPER_ACTIONS.get(action_name, {}).get("table", "")
    try:
        with _conn() as conn:
            if action_name in ("update_order_status", "update_ticket_status", "update_consultant_status", "update_hair_order_status"):
                if not target_id:
                    return {}, {}, NEED_MORE_DETAIL_MESSAGE
                row = conn.execute(f"SELECT * FROM {table} WHERE id=?", (target_id,)).fetchone()
                if not row:
                    return {}, {}, "رکورد موردنظر پیدا نشد."
                snapshot = dict(row)
                normalized = dict(plan)
                normalized["target_id"] = target_id
                normalized["target_label"] = normalized.get("target_label") or f"#{target_id}"
                return snapshot, normalized, ""
            if action_name in ("update_product_price", "update_product_stock", "delete_product"):
                row = None
                if target_id:
                    row = conn.execute("SELECT * FROM products WHERE id=?", (target_id,)).fetchone()
                if row is None:
                    row = _find_product_match(conn, args.get("match_text") or "")
                if row is None:
                    return {}, {}, "محصول موردنظر پیدا نشد."
                snapshot = dict(row)
                normalized = dict(plan)
                normalized["target_id"] = int(row["id"])
                normalized["target_label"] = f"محصول #{row['id']} - {row['name']}"
                if action_name == "update_product_price" and not int(args.get("new_price") or 0):
                    return {}, {}, NEED_MORE_DETAIL_MESSAGE
                return snapshot, normalized, ""
            if action_name == "delete_user_data":
                phone = args.get("phone") or ""
                site_user_id = int(args.get("site_user_id") or 0)
                bundle = _snapshot_user_bundle(conn, phone, site_user_id=site_user_id)
                if not bundle.get("phone") and not bundle.get("site_user_id"):
                    return {}, {}, "کاربر موردنظر پیدا نشد."
                normalized = dict(plan)
                normalized["args"] = {"phone": bundle.get("phone") or "", "site_user_id": int(bundle.get("site_user_id") or 0)}
                normalized["target_label"] = normalized.get("target_label") or (bundle.get("phone") or f"کاربر #{bundle.get('site_user_id')}")
                return bundle, normalized, ""
            if action_name == "set_chat_enabled":
                snapshot = {"chat_enabled": get_setting("chat_enabled", "1")}
                normalized = dict(plan)
                normalized["target_label"] = "وضعیت مشاور هوشمند"
                return snapshot, normalized, ""
            if action_name == "set_display_name":
                new_name = _clean_text(args.get("display_name") or "")
                if not new_name:
                    return {}, {}, "اسم جدید را دقیق‌تر بگو."
                snapshot = {"chat_display_name": get_setting("chat_display_name", DEFAULT_DISPLAY_NAME)}
                normalized = dict(plan)
                normalized["args"] = {"display_name": new_name}
                normalized["target_label"] = "اسم نمایشی مشاور"
                return snapshot, normalized, ""
            if action_name == "set_active_provider":
                provider_name = _clean_text(args.get("provider_name") or "").lower()
                if not provider_name:
                    return {}, {}, "نام AI فعال را دقیق‌تر بگو."
                rows = _provider_rows(only_enabled=True)
                if not any(str(r["name"]) == provider_name for r in rows):
                    return {}, {}, "این پروایدر فعال نیست یا پیدا نشد."
                snapshot = {"chat_active_provider": get_active_provider()}
                normalized = dict(plan)
                normalized["args"] = {"provider_name": provider_name}
                normalized["target_label"] = "AI فعال گفتگو"
                return snapshot, normalized, ""
    except Exception as e:
        return {}, {}, f"خطا در آماده‌سازی اقدام: {e}"
    return {}, {}, NOT_DEFINED_MESSAGE

def execute_pending_action(pending_id: int, actor_id: int | str, actor_key: str = "") -> dict[str, Any]:
    actor_key = str(actor_key or f"bot:{actor_id}").strip()[:120]
    pending = _get_pending_action(pending_id, actor_key=actor_key)
    if not pending:
        return {"ok": False, "text": "درخواست اقدام پیدا نشد یا به شما تعلق ندارد."}
    if pending.get("status") == "expired":
        return {"ok": False, "text": "⏰ زمان تأیید این اقدام گذشته و درخواست منقضی شده است. لطفاً دوباره درخواست را ثبت کن."}
    if pending.get("status") != "pending":
        return {"ok": False, "text": "این درخواست قبلاً بررسی شده است."}
    action_name = pending.get("action_name") or ""
    allowed, err = _policy_for_action(action_name, pending.get("actor_role") or "super")
    if not allowed:
        return {"ok": False, "text": err}

    args = _jloads(pending.get("args_json"), {})
    snapshot = _jloads(pending.get("snapshot_json"), {})
    target_id = int(pending.get("target_id") or 0)
    target_table = str(pending.get("target_table") or "")
    result_payload = {}
    try:
        with _conn() as conn:
            if action_name == "update_order_status":
                conn.execute("UPDATE product_orders SET status=? WHERE id=?", (args.get("status"), target_id))
                result_payload = {"new_status": args.get("status")}
            elif action_name == "update_ticket_status":
                update_fields = ["status=?"]
                vals = [args.get("status")]
                if args.get("status") == "replied":
                    update_fields += ["replied_at=?"]
                    vals.append(_now_str())
                vals.append(target_id)
                conn.execute(f"UPDATE giso_support_tickets SET {', '.join(update_fields)} WHERE id=?", vals)
                result_payload = {"new_status": args.get("status")}
            elif action_name == "update_consultant_status":
                conn.execute("UPDATE consultant_requests SET status=?, updated_at=? WHERE id=?", (args.get("status"), _now_str(), target_id))
                result_payload = {"new_status": args.get("status")}
            elif action_name == "update_hair_order_status":
                conn.execute("UPDATE hair_orders SET status=?, updated_at=? WHERE id=?", (args.get("status"), _now_str(), target_id))
                result_payload = {"new_status": args.get("status")}
            elif action_name == "update_product_price":
                conn.execute("UPDATE products SET price=? WHERE id=?", (int(args.get("new_price") or 0), target_id))
                result_payload = {"new_price": int(args.get("new_price") or 0)}
            elif action_name == "update_product_stock":
                conn.execute("UPDATE products SET in_stock=? WHERE id=?", (1 if args.get("in_stock") else 0, target_id))
                result_payload = {"in_stock": bool(args.get("in_stock"))}
            elif action_name == "delete_product":
                conn.execute("DELETE FROM products WHERE id=?", (target_id,))
                result_payload = {"deleted": True}
            elif action_name == "delete_user_data":
                phone = args.get("phone") or snapshot.get("phone") or ""
                site_user_id = int(args.get("site_user_id") or snapshot.get("site_user_id") or 0)
                if phone:
                    conn.execute("DELETE FROM giso_users WHERE phone=?", (phone,))
                    conn.execute("DELETE FROM giso_support_tickets WHERE phone=?", (phone,))
                if site_user_id or phone:
                    conn.execute("DELETE FROM analyses WHERE user_id=? OR phone=?", (site_user_id, phone))
                    conn.execute("DELETE FROM product_orders WHERE user_id=? OR phone=?", (site_user_id, phone))
                    conn.execute("DELETE FROM hair_orders WHERE user_id=? OR phone=?", (site_user_id, phone))
                    conn.execute("DELETE FROM product_requests WHERE user_id=? OR phone=?", (site_user_id, phone))
                    conn.execute("DELETE FROM reviews WHERE user_id=? OR phone=?", (site_user_id, phone))
                    conn.execute("DELETE FROM consultant_requests WHERE user_id=? OR phone=?", (site_user_id, phone))
                if snapshot.get("consultant_requests"):
                    ids = [int(r.get("id") or 0) for r in snapshot.get("consultant_requests") if int(r.get("id") or 0)]
                    if ids:
                        q = ",".join("?" for _ in ids)
                        conn.execute(f"DELETE FROM consultant_messages WHERE request_id IN ({q})", ids)
                if site_user_id:
                    conn.execute("DELETE FROM giso_web_auth WHERE id=?", (site_user_id,))
                elif phone:
                    conn.execute("DELETE FROM giso_web_auth WHERE phone=?", (phone,))
                result_payload = {"deleted_user": phone or site_user_id}
            elif action_name == "set_chat_enabled":
                set_setting("chat_enabled", "1" if args.get("enabled") else "0")
                result_payload = {"chat_enabled": bool(args.get("enabled"))}
            elif action_name == "set_display_name":
                set_setting("chat_display_name", args.get("display_name") or DEFAULT_DISPLAY_NAME)
                result_payload = {"chat_display_name": args.get("display_name") or DEFAULT_DISPLAY_NAME}
            elif action_name == "set_active_provider":
                ok, msg = set_active_provider(args.get("provider_name") or "")
                if not ok:
                    raise ValueError(msg)
                result_payload = {"chat_active_provider": args.get("provider_name") or ""}
            else:
                return {"ok": False, "text": NOT_DEFINED_MESSAGE}
            conn.commit()
        _set_pending_status(pending_id, "approved")
        log_id = _log_action(
            actor_key=actor_key,
            actor_role=pending.get("actor_role") or "super",
            action_name=action_name,
            target_table=target_table,
            target_id=target_id,
            request_text=pending.get("request_text") or "",
            args=args,
            snapshot=snapshot,
            result=result_payload,
            status="executed",
            approved=True,
            approved_at=_now_str(),
            executed_at=_now_str(),
        )
        return {
            "ok": True,
            "text": f"✅ اقدام «{SUPPORTED_SUPER_ACTIONS.get(action_name, {}).get('description', action_name)}» با موفقیت انجام شد.",
            "log_id": log_id,
            "reversible": bool(SUPPORTED_SUPER_ACTIONS.get(action_name, {}).get("reversible")),
        }
    except Exception as e:
        _set_pending_status(pending_id, "failed")
        _log_action(
            actor_key=actor_key,
            actor_role=pending.get("actor_role") or "super",
            action_name=action_name,
            target_table=target_table,
            target_id=target_id,
            request_text=pending.get("request_text") or "",
            args=args,
            snapshot=snapshot,
            result={}, status="failed", approved=True, error_text=str(e), approved_at=_now_str(), executed_at=_now_str(),
        )
        return {"ok": False, "text": f"❌ اجرای اقدام ناموفق بود: {e}"}

def cancel_pending_action(pending_id: int, actor_id: int | str, actor_key: str = "") -> dict[str, Any]:
    actor_key = str(actor_key or f"bot:{actor_id}").strip()[:120]
    pending = _get_pending_action(pending_id, actor_key=actor_key)
    if not pending:
        return {"ok": False, "text": "درخواست اقدام پیدا نشد یا به شما تعلق ندارد."}
    if pending.get("status") != "pending":
        return {"ok": False, "text": "این درخواست قبلاً بررسی شده است."}
    _set_pending_status(pending_id, "cancelled")
    _log_action(
        actor_key=actor_key,
        actor_role=pending.get("actor_role") or "super",
        action_name=pending.get("action_name") or "",
        target_table=pending.get("target_table") or "",
        target_id=int(pending.get("target_id") or 0),
        request_text=pending.get("request_text") or "",
        args=_jloads(pending.get("args_json"), {}),
        snapshot=_jloads(pending.get("snapshot_json"), {}),
        result={}, status="cancelled", approved=False,
    )
    return {"ok": True, "text": "❌ اقدام لغو شد و هیچ تغییری اعمال نشد."}

def rollback_action_log(log_id: int, actor_id: int | str, actor_key: str = "") -> dict[str, Any]:
    actor_key = str(actor_key or f"bot:{actor_id}").strip()[:120]
    try:
        with _conn() as conn:
            row = conn.execute("SELECT * FROM giso_ai_action_logs WHERE id=? AND actor_key=?", (int(log_id), actor_key)).fetchone()
            if not row:
                return {"ok": False, "text": "لاگ اقدام پیدا نشد."}
            data = dict(row)
            action_name = data.get("action_name") or ""
            if not SUPPORTED_SUPER_ACTIONS.get(action_name, {}).get("reversible"):
                return {"ok": False, "text": "برای این اقدام امکان بازگردانی تعریف نشده است."}
            snapshot = _jloads(data.get("snapshot_json"), {})
            target_id = int(data.get("target_id") or 0)
            if not snapshot and action_name not in ("set_chat_enabled", "set_display_name", "set_active_provider"):
                return {"ok": False, "text": "اطلاعات کافی برای rollback وجود ندارد."}
            if action_name == "update_order_status":
                conn.execute("UPDATE product_orders SET status=? WHERE id=?", (snapshot.get("status"), target_id))
            elif action_name == "update_ticket_status":
                conn.execute("UPDATE giso_support_tickets SET status=?, admin_reply=?, replied_at=? WHERE id=?", (snapshot.get("status"), snapshot.get("admin_reply", ""), snapshot.get("replied_at", ""), target_id))
            elif action_name == "update_consultant_status":
                conn.execute("UPDATE consultant_requests SET status=?, updated_at=? WHERE id=?", (snapshot.get("status"), snapshot.get("updated_at", ""), target_id))
            elif action_name == "update_hair_order_status":
                conn.execute("UPDATE hair_orders SET status=?, updated_at=? WHERE id=?", (snapshot.get("status"), snapshot.get("updated_at", ""), target_id))
            elif action_name == "update_product_price":
                conn.execute("UPDATE products SET price=? WHERE id=?", (snapshot.get("price", 0), target_id))
            elif action_name == "update_product_stock":
                conn.execute("UPDATE products SET in_stock=? WHERE id=?", (snapshot.get("in_stock", 1), target_id))
            elif action_name == "delete_product":
                conn.execute("DELETE FROM products WHERE id=?", (target_id,))
                _insert_snapshot_row(conn, "products", snapshot)
            elif action_name == "delete_user_data":
                _restore_user_bundle(conn, snapshot)
            elif action_name == "set_chat_enabled":
                set_setting("chat_enabled", snapshot.get("chat_enabled", "1"))
            elif action_name == "set_display_name":
                set_setting("chat_display_name", snapshot.get("chat_display_name", DEFAULT_DISPLAY_NAME))
            elif action_name == "set_active_provider":
                prev = snapshot.get("chat_active_provider") or ""
                if prev:
                    set_active_provider(prev)
            else:
                return {"ok": False, "text": "rollback برای این اقدام پشتیبانی نمی‌شود."}
            conn.commit()
        _log_action(
            actor_key=actor_key,
            actor_role=data.get("actor_role") or "super",
            action_name=f"rollback:{action_name}",
            target_table=data.get("target_table") or "",
            target_id=target_id,
            request_text=f"rollback log #{log_id}",
            args={}, snapshot=snapshot, result={"rolled_back_log_id": log_id},
            status="rolled_back", approved=True, approved_at=_now_str(), executed_at=_now_str(),
        )
        return {"ok": True, "text": "↩️ آخرین تغییر با موفقیت بازگردانی شد."}
    except Exception as e:
        return {"ok": False, "text": f"❌ بازگردانی ناموفق بود: {e}"}

def get_superadmin_action_capabilities_text() -> str:
    return (
        "می‌تونم کنارت باشم برای گزارش‌گیری، جمع‌بندی مدیریتی، بررسی کاربران، سفارش‌ها، تیکت‌ها، "
        "درخواست‌های مشاوره، فروش مو، آنالیزها و وضعیت هوش مصنوعی. "
        "همچنین برای تغییرهای واقعی مثل تغییر وضعیت‌ها، قیمت یا موجودی محصول، حذف محصول، حذف اطلاعات کاربر، "
        "و بعضی تنظیمات AI، اول پیش‌نمایش می‌دم و بعد از تأییدت اجرا می‌کنم."
    )

__all__ = [
    "OFF_MESSAGE",
    "NO_ACCESS_MESSAGE",
    "LIMIT_MESSAGE",
    "PROVIDER_ERROR_MESSAGE",
    "SOON_MESSAGE",
    "OUT_OF_SCOPE_MESSAGE",
    "NOT_DEFINED_MESSAGE",
    "POLICY_DENIED_MESSAGE",
    "NEED_MORE_DETAIL_MESSAGE",
    "ROLE_LABELS",
    "SECTION_LABELS",
    "resolve_actor_role",
    "init_ai_runtime_tables",
    "get_setting",
    "set_setting",
    "get_display_name",
    "set_display_name",
    "is_chat_enabled",
    "set_chat_enabled",
    "get_last_activity",
    "get_last_welcome",
    "touch_user_activity",
    "mark_welcome_shown",
    "get_welcome_inactive_hours",
    "should_show_welcome",
    "get_active_provider",
    "set_active_provider",
    "list_provider_options",
    "get_role_capabilities",
    "set_role_capabilities",
    "get_role_policy",
    "set_role_policy",
    "check_role_access",
    "get_context_scope",
    "get_today_usage_count",
    "check_daily_limit",
    "record_usage",
    "chat_with_managed_ai",
    "admin_test_prompt",
    "is_widget_enabled",
    "set_widget_enabled",
    "get_widget_position",
    "set_widget_position",
    "get_widget_welcome_message",
    "set_widget_welcome_message",
    "get_widget_primary_color",
    "set_widget_primary_color",
    "get_widget_config",
    "get_widget_usage_stats",
    "get_failover_chain",
    "set_failover_chain",
    "chat_with_failover",
    "build_provider_status_report",
    "get_recent_pending_actions",
    "get_recent_action_logs",
    "get_recent_rollback_logs",
    "build_site_widget_context",
    "build_site_widget_prompt",
    "build_site_widget_fallback_reply",
    "build_widget_welcome",
    "build_user_next_step_hints",
    "build_admin_task_hints",
    "get_runtime_overview",
    "build_status_report",
    "get_smart_welcome_context",
    "process_superadmin_request",
    "execute_pending_action",
    "cancel_pending_action",
    "rollback_action_log",
    "get_superadmin_action_capabilities_text",
    "build_capability_guide",
]
