# -*- coding: utf-8 -*-
"""
user_service — منطق مشترک حساب/کاربر/پنل کاربری.

وب و ربات هر دو از این سرویس استفاده می‌کنند تا عملیات کاربری و لیست‌ها
duplicate نشود. توابع این فایل فقط به shared DB (bot.db) و phoneutil متکی هستند.
"""
from __future__ import annotations
import sqlite3, time as _time
from pathlib import Path
from typing import Optional

_BOT_DB = Path(__file__).resolve().parent.parent / "data" / "bot.db"


def _conn() -> sqlite3.Connection:
    c = sqlite3.connect(str(_BOT_DB), check_same_thread=False)
    c.row_factory = sqlite3.Row
    try:
        c.execute("PRAGMA journal_mode=WAL")
        c.execute("PRAGMA foreign_keys=ON")
    except Exception:
        pass
    return c


def get_user(user_id: int) -> Optional[dict]:
    c = _conn()
    try:
        r = c.execute("SELECT * FROM users WHERE user_id=?", (int(user_id),)).fetchone()
        return dict(r) if r else None
    finally:
        c.close()


def get_user_by_phone(phone_norm: str) -> Optional[dict]:
    c = _conn()
    try:
        r = c.execute("SELECT * FROM users WHERE phone=?", (phone_norm,)).fetchone()
        return dict(r) if r else None
    finally:
        c.close()


def create_user(phone_norm: str, first_name: str = "کاربر") -> dict:
    """ساخت کاربر در صورت نبود. برمی‌گرداند دیکشنری کاربر."""
    existing = get_user_by_phone(phone_norm)
    if existing:
        return existing
    c = _conn()
    try:
        now = int(_time.time())
        cur = c.execute(
            "INSERT INTO users (first_name, phone, joined, last_active, credits, points, xp) "
            "VALUES (?,?,?,?,0,0,0)",
            (first_name, phone_norm, now, now),
        )
        c.commit()
        uid = cur.lastrowid
        return get_user(uid)
    finally:
        c.close()


def touch_user(user_id: int) -> None:
    c = _conn()
    try:
        c.execute("UPDATE users SET last_active=? WHERE user_id=?",
                  (int(_time.time()), int(user_id)))
        c.commit()
    finally:
        c.close()


def list_courses() -> list:
    c = _conn()
    try:
        rows = c.execute("SELECT course_id, title, description FROM courses ORDER BY course_id").fetchall()
        out = []
        for r in rows:
            lc = c.execute("SELECT COUNT(*) AS c FROM lessons WHERE course_id=?", (r["course_id"],)).fetchone()
            out.append({"id": r["course_id"], "title": r["title"] or r["course_id"],
                        "desc": r["description"] or "",
                        "lessons": int(lc["c"] if lc else 0)})
        return out
    finally:
        c.close()


def list_shop_items() -> list:
    c = _conn()
    try:
        rows = c.execute(
            "SELECT item_id, title, description, price FROM shop_items "
            "WHERE COALESCE(active,0)=1 ORDER BY price"
        ).fetchall()
        return [{"id": r["item_id"], "title": r["title"] or r["item_id"],
                 "desc": r["description"] or "", "price": int(r["price"] or 0)} for r in rows]
    finally:
        c.close()


def list_missions() -> list:
    c = _conn()
    try:
        rows = c.execute("""
            SELECT id, title, description, reward_credits AS credits, required_skills AS skills, status
            FROM real_missions WHERE COALESCE(status,'active')='active' ORDER BY id DESC
        """).fetchall()
        if rows:
            return [{"id": f"real_{r['id']}", "title": r["title"],
                     "desc": r["description"], "credits": int(r["credits"] or 0),
                     "xp": 0, "real": True} for r in rows]
        rows = c.execute("""
            SELECT mission_id AS id, title, description, xp_reward, credits_reward
            FROM missions WHERE COALESCE(active,1)=1
        """).fetchall()
        return [{"id": r["id"], "title": r["title"], "desc": r["description"],
                 "xp": int(r["xp_reward"] or 0), "credits": int(r["credits_reward"] or 0),
                 "real": False} for r in rows]
    finally:
        c.close()


def user_progress_summary(user_id: int) -> dict:
    c = _conn()
    try:
        u = c.execute("SELECT xp, credits, phone, first_name FROM users WHERE user_id=?",
                      (int(user_id),)).fetchone()
        cm = c.execute("SELECT COUNT(*) AS c FROM completed_missions WHERE user_id=?",
                       (int(user_id),)).fetchone()
        lp = c.execute("SELECT COUNT(*) AS c FROM progress WHERE user_id=?",
                       (int(user_id),)).fetchone()
        cp = c.execute("SELECT COUNT(*) AS c FROM career_paths WHERE user_id=?",
                       (int(user_id),)).fetchone()
        tk = c.execute(
            "SELECT COUNT(*) AS c FROM tickets WHERE user_id=? AND COALESCE(replied,0)=0",
            (int(user_id),)).fetchone()
        return {
            "xp": int(u["xp"] or 0) if u else 0,
            "credits": int(u["credits"] or 0) if u else 0,
            "first_name": u["first_name"] if u else "",
            "phone": u["phone"] if u else "",
            "missions_done": int(cm["c"] if cm else 0),
            "lessons_done": int(lp["c"] if lp else 0),
            "paths_count": int(cp["c"] if cp else 0),
            "open_tickets": int(tk["c"] if tk else 0),
        }
    finally:
        c.close()


def get_user_rank(user_id: int) -> int:
    """Alias برای سازگاری."""
    return user_rank(user_id)


def user_rank(user_id: int) -> int:
    c = _conn()
    try:
        rows = c.execute("SELECT user_id FROM users ORDER BY xp DESC").fetchall()
        for i, r in enumerate(rows, 1):
            if r["user_id"] == int(user_id):
                return i
        return 0
    finally:
        c.close()


def is_site_admin(user_id: int) -> bool:
    """ادمین سایت بر اساس تطابق phone با SITE_ADMIN_PHONES."""
    from .env_service import site_admin_phones
    u = get_user(user_id)
    return bool(u and u.get("phone") and u["phone"] in site_admin_phones())
