# -*- coding: utf-8 -*-
"""
giso/wallet_missions.py — مأموریت‌های کیف پول (Spend) (Phase 2, Unit U5)
استخراج‌شده از giso/wallet.py بدون تغییر رفتار؛ همه نام‌ها در giso.wallet re-export می‌شوند.
"""
import logging
import sqlite3

from giso.base import get_giso_db_conn
from giso.money import format_toman
from giso.wallet_core import (MISSION_EVENTS, SCOPES, WalletCheckoutError, _now,
                              _positive_int, is_financial_superadmin)

logger = logging.getLogger("giso_wallet_missions")

def list_missions_for_user(user_id: int) -> list:
    try:
        with get_giso_db_conn() as conn:
            rows = conn.execute(
                "SELECT m.*,c.completed_at,c.reward_transaction_id "
                "FROM wallet_missions m LEFT JOIN wallet_mission_completions c "
                "ON c.mission_id=m.id AND c.user_id=? "
                "WHERE COALESCE(m.is_deleted,0)=0 AND (m.is_active=1 OR c.id IS NOT NULL) "
                "ORDER BY m.sort_order,m.id",
                (int(user_id),),
            ).fetchall()
            out = []
            for row in rows:
                item = dict(row)
                item["completed"] = bool(item.get("completed_at"))
                out.append(item)
            return out
    except Exception as exc:
        logger.warning("user missions failed: %s", exc)
        return []


def list_missions_admin() -> list:
    try:
        with get_giso_db_conn() as conn:
            rows = conn.execute(
                "SELECT m.*,COUNT(c.id) AS completions_count "
                "FROM wallet_missions m LEFT JOIN wallet_mission_completions c ON c.mission_id=m.id "
                "WHERE COALESCE(m.is_deleted,0)=0 GROUP BY m.id ORDER BY m.sort_order,m.id"
            ).fetchall()
            return [dict(row) for row in rows]
    except Exception:
        return []


def _mission_reward_scope(values: dict) -> str:
    """نوع اعتبار پاداش مأموریت: 'spend' (مصرفی، پیش‌فرض) یا 'cash' (نقدی)."""
    scope = str(values.get("reward_scope") or "spend").strip().lower()
    return "cash" if scope == "cash" else "spend"


def create_mission(values: dict) -> tuple:
    """ساخت/بازگردانی یکی از eventهای واقعی و پشتیبانی‌شده سامانه.

    پاداش سه‌گانه: اعتبار مصرفی (spend) / نقدی (cash) / امتیاز رتبه (reward_points).
    """
    if not is_financial_superadmin():
        return False, "فقط سوپرادمین می‌تواند مأموریت مالی ایجاد کند."
    code = str(values.get("code") or "").strip().lower()
    if code not in MISSION_EVENTS:
        return False, "رویداد مأموریت نامعتبر است."
    default_title, sort_order = MISSION_EVENTS[code]
    title = str(values.get("title") or default_title).strip()[:160]
    description = str(values.get("description") or "").strip()[:1000]
    reward = _positive_int(values.get("reward_amount"))
    reward_points = _positive_int(values.get("reward_points"))
    reward_scope = _mission_reward_scope(values)
    mission_type = str(values.get("mission_type") or "once").strip().lower()
    if mission_type not in ("once", "daily", "weekly"):
        mission_type = "once"
    if not title:
        return False, "عنوان مأموریت الزامی است."
    conn = get_giso_db_conn()
    try:
        conn.execute("BEGIN IMMEDIATE")
        existing = conn.execute("SELECT id,is_deleted FROM wallet_missions WHERE code=?", (code,)).fetchone()
        now = _now()
        if existing and not int(existing["is_deleted"] or 0):
            raise WalletCheckoutError("برای این رویداد قبلاً مأموریت ساخته شده است.")
        if existing:
            conn.execute(
                "UPDATE wallet_missions SET title=?,description=?,reward_amount=?,reward_scope=?,"
                "reward_points=?,mission_type=?,"
                "is_active=?,is_deleted=0,sort_order=?,updated_at=? WHERE id=?",
                (title, description, reward, reward_scope, reward_points, mission_type,
                 1 if values.get("is_active", True) else 0,
                 sort_order, now, int(existing["id"])),
            )
        else:
            conn.execute(
                "INSERT INTO wallet_missions "
                "(code,title,description,reward_amount,reward_scope,reward_points,mission_type,"
                "is_active,is_deleted,sort_order,created_at,updated_at) "
                "VALUES (?,?,?,?,?,?,?,?,0,?,?,?)",
                (code, title, description, reward, reward_scope, reward_points, mission_type,
                 1 if values.get("is_active", True) else 0,
                 sort_order, now, now),
            )
        conn.execute("DELETE FROM wallet_mission_tombstones WHERE code=?", (code,))
        conn.commit()
        return True, "مأموریت با موفقیت ایجاد شد."
    except WalletCheckoutError as exc:
        conn.rollback()
        return False, str(exc)
    except sqlite3.IntegrityError:
        conn.rollback()
        return False, "برای این رویداد قبلاً مأموریت ساخته شده است."
    except Exception as exc:
        conn.rollback()
        logger.exception("create mission failed: %s", exc)
        return False, "ساخت مأموریت ناموفق بود."
    finally:
        conn.close()


def delete_mission(mission_id: int) -> tuple:
    """حذف ایمن؛ completionهای مالی حفظ و رکورد دارای سابقه soft-delete می‌شود."""
    if not is_financial_superadmin():
        return False, "فقط سوپرادمین می‌تواند مأموریت مالی را حذف کند."
    conn = get_giso_db_conn()
    try:
        conn.execute("BEGIN IMMEDIATE")
        mission = conn.execute(
            "SELECT id,code,title FROM wallet_missions WHERE id=? AND COALESCE(is_deleted,0)=0",
            (int(mission_id),),
        ).fetchone()
        if not mission:
            raise WalletCheckoutError("مأموریت پیدا نشد.")
        conn.execute(
            "INSERT INTO wallet_mission_tombstones(code,deleted_at) VALUES (?,?) ON CONFLICT(code) DO UPDATE SET deleted_at=excluded.deleted_at",
            (mission["code"], _now()),
        )
        count = conn.execute(
            "SELECT COUNT(*) FROM wallet_mission_completions WHERE mission_id=?", (int(mission_id),)
        ).fetchone()[0]
        if int(count or 0):
            conn.execute(
                "UPDATE wallet_missions SET is_active=0,is_deleted=1,updated_at=? WHERE id=?",
                (_now(), int(mission_id)),
            )
        else:
            conn.execute("DELETE FROM wallet_missions WHERE id=?", (int(mission_id),))
        conn.commit()
        return True, "مأموریت حذف شد؛ سوابق پاداش کاربران دست‌نخورده باقی ماند."
    except WalletCheckoutError as exc:
        conn.rollback()
        return False, str(exc)
    except Exception as exc:
        conn.rollback()
        logger.exception("delete mission failed: %s", exc)
        return False, "حذف مأموریت ناموفق بود."
    finally:
        conn.close()


def update_mission(mission_id: int, values: dict) -> tuple:
    if not is_financial_superadmin():
        return False, "فقط سوپرادمین می‌تواند مأموریت مالی را تغییر دهد."
    reward = _positive_int(values.get("reward_amount"))
    reward_points = _positive_int(values.get("reward_points"))
    reward_scope = _mission_reward_scope(values)
    mission_type = str(values.get("mission_type") or "once").strip().lower()
    if mission_type not in ("once", "daily", "weekly"):
        mission_type = "once"
    title = str(values.get("title") or "").strip()[:160]
    description = str(values.get("description") or "").strip()[:1000]
    if not title:
        return False, "عنوان مأموریت الزامی است."
    try:
        with get_giso_db_conn() as conn:
            cur = conn.execute(
                "UPDATE wallet_missions SET title=?,description=?,reward_amount=?,reward_scope=?,"
                "reward_points=?,mission_type=?,"
                "is_active=?,updated_at=? WHERE id=? AND COALESCE(is_deleted,0)=0",
                (title, description, reward, reward_scope, reward_points, mission_type,
                 1 if values.get("is_active") else 0, _now(), int(mission_id)),
            )
            conn.commit()
            if cur.rowcount != 1:
                return False, "مأموریت پیدا نشد."
        return True, "تنظیمات مأموریت ذخیره شد."
    except Exception as exc:
        logger.exception("update mission failed: %s", exc)
        return False, "ذخیره مأموریت ناموفق بود."


def complete_mission(user_id: int, mission_code: str, event_key: str = "") -> tuple:
    """تکمیل و پرداخت spend در یک transaction؛ unique از دوباره‌پرداخت جلوگیری می‌کند."""
    conn = get_giso_db_conn()
    try:
        conn.execute("BEGIN IMMEDIATE")
        mission = conn.execute(
            "SELECT * FROM wallet_missions WHERE code=? AND is_active=1 AND COALESCE(is_deleted,0)=0",
            (str(mission_code or "").strip(),),
        ).fetchone()
        if not mission:
            conn.rollback()
            return False, "مأموریت فعال نیست."
        existing = conn.execute(
            "SELECT id FROM wallet_mission_completions WHERE mission_id=? AND user_id=?",
            (int(mission["id"]), int(user_id)),
        ).fetchone()
        if existing:
            conn.rollback()
            return True, "مأموریت قبلاً تکمیل شده است."
        reward = max(0, int(mission["reward_amount"] or 0))
        points = max(0, int(mission["reward_points"] or 0))
        scope = str(mission["reward_scope"] or "spend").strip().lower()
        if scope not in SCOPES:
            scope = "spend"
        now = _now()
        cur = conn.execute(
            "INSERT INTO wallet_mission_completions "
            "(mission_id,user_id,event_key,reward_amount,reward_scope,completed_at) "
            "VALUES (?,?,?,?,?,?)",
            (int(mission["id"]), int(user_id), str(event_key or "")[:120], reward, scope, now),
        )
        completion_id = int(cur.lastrowid)
        tx_id = None
        if reward:
            tx = conn.execute(
                "INSERT INTO wallet_transactions "
                "(user_id,kind,amount,status,source_type,source_id,balance_scope,idempotency_key,description,created_at) "
                "VALUES (?, 'mission_reward', ?, 'available', 'mission_completion', ?, ?, ?, ?, ?)",
                (int(user_id), reward, completion_id, scope,
                 f"mission:{int(mission['id'])}:user:{int(user_id)}",
                 f"پاداش مأموریت «{mission['title']}»", now),
            )
            tx_id = int(tx.lastrowid)
            conn.execute(
                "UPDATE wallet_mission_completions SET reward_transaction_id=? WHERE id=?",
                (tx_id, completion_id),
            )
        conn.commit()
        parts = []
        if reward:
            parts.append(f"{format_toman(reward)} اعتبار {'نقدی' if scope == 'cash' else 'مصرفی'}")
        if points:
            parts.append(f"{points} امتیاز رتبه")
        reward_text = " و ".join(parts) if parts else "این مأموریت پاداش اعتباری نداشت"
        return True, f"مأموریت تکمیل شد؛ {reward_text} دریافت کردید."
    except sqlite3.IntegrityError:
        conn.rollback()
        return True, "مأموریت قبلاً تکمیل شده است."
    except Exception as exc:
        conn.rollback()
        logger.exception("complete mission failed: %s", exc)
        return False, "ثبت پاداش مأموریت ناموفق بود."
    finally:
        conn.close()


def record_product_mission_view(user_id: int, product_id: int) -> tuple:
    """Anti-abuse progress: three distinct published products over at least 30 seconds."""
    try:
        with get_giso_db_conn() as conn:
            conn.execute("""CREATE TABLE IF NOT EXISTS wallet_product_mission_views(
                user_id INTEGER NOT NULL,product_id INTEGER NOT NULL,viewed_at TEXT NOT NULL,
                PRIMARY KEY(user_id,product_id))""")
            published = conn.execute(
                "SELECT 1 FROM products WHERE id=? AND COALESCE(publish_status,'published') IN ('','published')",
                (int(product_id),)).fetchone()
            if not published:
                return False, "محصول منتشرشده نیست."
            conn.execute("INSERT INTO wallet_product_mission_views(user_id,product_id,viewed_at) "
                         "VALUES(?,?,datetime('now','localtime')) ON CONFLICT DO NOTHING", (int(user_id), int(product_id)))
            progress = conn.execute(
                "SELECT COUNT(*) count,MIN(viewed_at) first_at,MAX(viewed_at) last_at "
                "FROM wallet_product_mission_views WHERE user_id=?", (int(user_id),)).fetchone()
            elapsed = conn.execute(
                "SELECT CAST((julianday('now','localtime')-julianday(?))*86400 AS INTEGER)",
                (progress["first_at"],)).fetchone()[0] if progress["first_at"] else 0
            conn.commit()
        count = int(progress["count"] or 0)
        if count >= 3 and int(elapsed or 0) >= 30:
            return complete_mission(user_id, "product_explorer", event_key=f"products:{user_id}")
        return True, f"پیشرفت مشاهده محصولات: {min(count, 3)} از ۳"
    except Exception as exc:
        logger.warning("product mission view failed: %s", exc)
        return False, "پیشرفت مأموریت ثبت نشد."


def complete_bale_connection_mission(bale_id) -> tuple:
    """Award only after shared contact maps to a real GISO web account."""
    try:
        with get_giso_db_conn() as conn:
            row = conn.execute(
                "SELECT a.id FROM giso_users b JOIN giso_web_auth a ON a.phone=b.phone "
                "WHERE b.bale_id=? AND b.contact_shared=1 AND COALESCE(b.phone,'')<>'' LIMIT 1",
                (str(bale_id),)).fetchone()
        if not row:
            return False, "حساب بله هنوز به حساب سایت متصل نیست."
        return complete_mission(int(row["id"]), "bale_connected", event_key=f"bale:{bale_id}")
    except Exception:
        return False, "بررسی اتصال بله ناموفق بود."



def mission_progress(user_id: int, code: str) -> dict:
    """پیشرفت نمایشی مأموریت‌های چندمرحله‌ای (مورد ۱۶ help.md).

    خروجی ``{done, target, label}`` یا دیکت خالی وقتی مأموریت تک‌مرحله است.
    """
    if str(code or "") != "product_explorer":
        return {}
    try:
        with get_giso_db_conn() as conn:
            conn.execute("""CREATE TABLE IF NOT EXISTS wallet_product_mission_views(
                user_id INTEGER NOT NULL,product_id INTEGER NOT NULL,viewed_at TEXT NOT NULL,
                PRIMARY KEY(user_id,product_id))""")
            row = conn.execute(
                "SELECT COUNT(*) c FROM wallet_product_mission_views WHERE user_id=?",
                (int(user_id),)).fetchone()
        done = min(3, int(row["c"] or 0))
        return {"done": done, "target": 3,
                "label": f"{done} از ۳ محصول مشاهده شده" + (" — مانده: کمتر از ۳۰ ثانیه از نخستین مشاهده" if done >= 3 else "")}
    except Exception as exc:
        logger.warning("mission_progress failed: %s", exc)
        return {}
