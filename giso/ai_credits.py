# -*- coding: utf-8 -*-
"""اعتبار همراه هوشمند — بازطراحی تحویل ۱۴۰۵-۰۶-۱۰ (مورد ۱۱ img/help.md).

تغییر مدل طبق دستور کارفرما:
- «اعتبار عددی» جداگانه (اعتبار اولیهٔ ۲۰تایی) حذف شد؛ عددی دیگر کم نمی‌شود.
- gating و کسر هزینهٔ هر درخواست موفق از **اعتبار مصرفی** کیف پول (scope=spend) انجام می‌شود.
- ledger جدولِ حسابرسی می‌ماند (تاریخچهٔ کسرها) ولی ماندهٔ عددی نقش gating ندارد.
امضاهای عمومی (get_ai_credit / reserve_ai_credit / refund_ai_credit / admin_*) حفظ شده‌اند
تا سایت و ربات بدون تغییر شکسته شوند.
"""
from datetime import datetime

from giso.base import get_giso_db_conn, normalize_phone

SCHEMA = """
CREATE TABLE IF NOT EXISTS giso_ai_credit_accounts(
 user_id INTEGER PRIMARY KEY, phone TEXT DEFAULT '', balance INTEGER NOT NULL DEFAULT 0,
 total_used INTEGER NOT NULL DEFAULT 0, deduct_scope TEXT NOT NULL DEFAULT 'spend',
 created_at TEXT DEFAULT '', updated_at TEXT DEFAULT ''
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_ai_credit_phone ON giso_ai_credit_accounts(phone) WHERE phone<>'';
CREATE TABLE IF NOT EXISTS giso_ai_credit_ledger(
 id INTEGER PRIMARY KEY AUTOINCREMENT,user_id INTEGER NOT NULL,delta INTEGER NOT NULL,
 balance_after INTEGER NOT NULL,reason TEXT DEFAULT '',channel TEXT DEFAULT '',request_key TEXT UNIQUE NOT NULL,
 actor TEXT DEFAULT '',created_at TEXT DEFAULT ''
);
CREATE INDEX IF NOT EXISTS idx_ai_credit_ledger_user ON giso_ai_credit_ledger(user_id,id);
"""


def ensure_ai_credit_tables(conn=None):
    own = conn is None
    if own:
        conn = get_giso_db_conn()
    try:
        conn.executescript(SCHEMA)
        try:
            conn.execute("ALTER TABLE giso_ai_credit_accounts ADD COLUMN deduct_scope TEXT NOT NULL DEFAULT 'spend'")
        except Exception:
            pass  # ستون از قبل وجود دارد
        if own:
            conn.commit()
    finally:
        if own:
            conn.close()


def _cfg(key, default):
    try:
        from giso_admin import get_giso_config
        return get_giso_config(key, str(default)) or str(default)
    except Exception:
        return str(default)


def credit_settings():
    """«فعال»، «هزینهٔ هر درخواست موفق (تومان)» و «حوزهٔ پیش‌فرض کسر»؛ اعتبار اولیه حذف شده است."""
    scope = str(_cfg('ai_user_credit_scope', 'spend') or 'spend').strip().lower()
    return {"enabled": str(_cfg('ai_user_credit_enabled', '1')) == '1',
            "cost": max(1, int(_cfg('ai_user_request_cost', '1'))),
            "scope": scope if scope in _SCOPES else "spend"}


def _identity(phone: str):
    phone = normalize_phone(phone)
    if not phone:
        return 0, ""
    with get_giso_db_conn() as conn:
        row = conn.execute("SELECT id FROM giso_web_auth WHERE phone=? LIMIT 1", (phone,)).fetchone()
    return (int(row[0]), phone) if row else (0, phone)


def _now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


_SCOPES = ("spend", "cash")


def _spend_balance(user_id: int, conn=None) -> int:
    from giso.wallet_core import get_wallet_balances
    return int(get_wallet_balances(int(user_id), conn=conn).get("spend", 0))


def get_deduct_scope(user_id: int) -> str:
    """حوزهٔ کسر اعتبار کاربر: spend (مصرفی) یا cash (نقدی) — پیش‌فرض مصرفی."""
    try:
        with get_giso_db_conn() as conn:
            ensure_ai_credit_tables(conn)
            row = conn.execute("SELECT deduct_scope FROM giso_ai_credit_accounts WHERE user_id=?", (int(user_id),)).fetchone()
        if row and row[0] in _SCOPES:
            return str(row[0])
        scope = str(_cfg('ai_user_credit_scope', 'spend') or 'spend').strip().lower()
        return scope if scope in _SCOPES else "spend"
    except Exception:
        return "spend"


def set_deduct_scope(user_id: int, scope: str) -> bool:
    """تنظیم حوزهٔ کسر توسط سوپرادمین (مورد ۱۱ help2)."""
    scope = str(scope or "").strip().lower()
    if scope not in _SCOPES:
        return False
    with get_giso_db_conn() as conn:
        ensure_ai_credit_tables(conn)
        conn.execute("BEGIN IMMEDIATE")
        conn.execute(
            "INSERT INTO giso_ai_credit_accounts(user_id, deduct_scope, created_at, updated_at) VALUES (?,?,?,?) "
            "ON CONFLICT(user_id) DO UPDATE SET deduct_scope=excluded.deduct_scope, updated_at=excluded.updated_at",
            (int(user_id), scope, _now(), _now()))
        conn.commit()
    return True


def _scope_balance(user_id: int, scope: str, conn=None) -> int:
    from giso.wallet_core import get_wallet_balances
    return int(get_wallet_balances(int(user_id), conn=conn).get(scope, 0))


def _used_total(user_id: int, conn) -> int:
    row = conn.execute(
        "SELECT COALESCE(SUM(-delta),0) FROM giso_ai_credit_ledger WHERE user_id=? AND delta<0",
        (int(user_id),)).fetchone()
    return int(row[0] or 0)


def get_ai_credit(phone: str, create=True):
    """نمایش اعتبار: مانده = اعتبار مصرفی کیف پول؛ مصرف‌شده = مجموع کسرهای همراه هوشمند."""
    user_id, phone = _identity(phone)
    if not user_id:
        return {"user_id": 0, "phone": phone, "balance": 0, "total_used": 0, "available": False}
    with get_giso_db_conn() as conn:
        ensure_ai_credit_tables(conn)
        scope = get_deduct_scope(user_id)
        balance = _scope_balance(user_id, scope, conn)
        used = _used_total(user_id, conn)
    return {"user_id": user_id, "phone": phone, "balance": balance, "scope": scope,
            "total_used": used, "available": True, "settings": credit_settings()}


def reserve_ai_credit(phone: str, request_key: str, channel='site'):
    """گیت + کسر اتمیک هزینه از اعتبار مصرفی (spend) با کلید یکتا."""
    settings = credit_settings()
    if not settings['enabled']:
        return True, "", {"balance": -1, "cost": 0}
    user_id, phone = _identity(phone)
    if not user_id:
        return False, "برای استفاده از همراه هوشمند ابتدا وارد حساب شوید.", {}
    cost = settings['cost']
    key = f'ai-use:{request_key}'
    conn = get_giso_db_conn()
    try:
        conn.execute("BEGIN IMMEDIATE")
        ensure_ai_credit_tables(conn)
        old = conn.execute("SELECT balance_after FROM giso_ai_credit_ledger WHERE request_key=?", (key,)).fetchone()
        if old:
            conn.rollback()
            return True, "", {"balance": int(old[0]), "cost": cost}
        scope = get_deduct_scope(user_id)
        bal = _scope_balance(user_id, scope, conn)
        if bal < cost:
            conn.rollback()
            fa = "مصرفی" if scope == "spend" else "نقدی"
            return False, f"اعتبار {fa} کافی نیست؛ از کیف پول «افزایش موجودی» انجام بده.", {"balance": bal, "cost": cost}
        after = bal - cost
        conn.execute(
            "INSERT INTO wallet_transactions "
            "(user_id,kind,amount,status,source_type,source_id,balance_scope,idempotency_key,description,created_at) "
            "VALUES (?, 'ai_credit_use', ?, 'used', 'ai_credit_use', 0, ?, ?, ?, ?)",
            (int(user_id), -cost, scope, key, f"استفاده از همراه هوشمند ({channel})", _now()))
        conn.execute(
            "INSERT INTO giso_ai_credit_ledger(user_id,delta,balance_after,reason,channel,request_key,actor,created_at) "
            "VALUES (?,?,?,?,?,?,?,?) ON CONFLICT DO NOTHING",
            (int(user_id), -cost, after, 'کسر از اعتبار ' + ('مصرفی' if scope == 'spend' else 'نقدی'), channel, key, 'user', _now()))
        conn.commit()
        return True, "", {"balance": after, "cost": cost}
    except Exception:
        try:
            conn.rollback()
        except Exception:
            pass
        return False, "خطا در بررسی اعتبار مصرفی.", {}
    finally:
        conn.close()


def refund_ai_credit(phone: str, request_key: str, channel='site'):
    """بازگشت هزینه به حوزهٔ فعال کاربر (نقدی/مصرفی) وقتی پاسخ ناموفق بوده است."""
    user_id, phone = _identity(phone)
    if not user_id:
        return False
    use_key = f'ai-use:{request_key}'
    refund_key = f'ai-refund:{request_key}'
    conn = get_giso_db_conn()
    try:
        conn.execute("BEGIN IMMEDIATE")
        ensure_ai_credit_tables(conn)
        used = conn.execute("SELECT delta FROM giso_ai_credit_ledger WHERE request_key=?", (use_key,)).fetchone()
        refunded = conn.execute("SELECT id FROM giso_ai_credit_ledger WHERE request_key=?", (refund_key,)).fetchone()
        if not used or refunded:
            conn.rollback()
            return False
        amount = abs(int(used[0]))
        conn.execute(
            "INSERT INTO wallet_transactions "
            "(user_id,kind,amount,status,source_type,source_id,balance_scope,idempotency_key,description,created_at) "
            "VALUES (?, 'ai_credit_refund', ?, 'used', 'ai_credit_refund', 0, ?, ?, ?, ?)",
            (int(user_id), amount, get_deduct_scope(user_id), refund_key, 'بازگشت اعتبار پاسخ ناموفق', _now()))
        spend = _spend_balance(user_id, conn)
        conn.execute(
            "INSERT INTO giso_ai_credit_ledger(user_id,delta,balance_after,reason,channel,request_key,actor,created_at) "
            "VALUES (?,?,?,?,?,?,?,?) ON CONFLICT DO NOTHING",
            (int(user_id), amount, spend + amount, 'بازگشت اعتبار پاسخ ناموفق', channel, refund_key, 'system', _now()))
        conn.commit()
        return True
    except Exception:
        try:
            conn.rollback()
        except Exception:
            pass
        return False
    finally:
        conn.close()


def admin_credit_users(limit=200):
    """فهرست سوپرادمین: ماندهٔ حوزهٔ فعال کیف پول + مجموع مصرف همراه هوشمند."""
    with get_giso_db_conn() as conn:
        ensure_ai_credit_tables(conn)
        rows = conn.execute(
            "SELECT u.id,u.phone,u.name,u.first_name,COALESCE(a.deduct_scope,'spend') deduct_scope "
            "FROM giso_web_auth u LEFT JOIN giso_ai_credit_accounts a ON a.user_id=u.id ORDER BY u.id DESC LIMIT ?",
            (int(limit),)).fetchall()
        out = []
        for r in rows:
            d = dict(r)
            scope = d["deduct_scope"] if d["deduct_scope"] in _SCOPES else "spend"
            d["scope"] = scope
            d["balance"] = _scope_balance(d["id"], scope, conn)
            d["total_used"] = _used_total(d["id"], conn)
            out.append(d)
    return out


def admin_adjust_credit(user_id: int, delta: int, actor='super'):
    """اصلاح دستی ماندهٔ عددی قدیمی (حسابرسی) — دیگر روی gating اثر ندارد."""
    delta = max(-1000000, min(1000000, int(delta)))
    key = f'ai-admin:{int(user_id)}:{__import__("uuid").uuid4().hex}'
    with get_giso_db_conn() as conn:
        ensure_ai_credit_tables(conn)
        conn.execute("BEGIN IMMEDIATE")
        user = conn.execute("SELECT id,phone FROM giso_web_auth WHERE id=?", (int(user_id),)).fetchone()
        if not user:
            conn.rollback()
            return False, "کاربر پیدا نشد."
        row = conn.execute("SELECT balance FROM giso_ai_credit_accounts WHERE user_id=?", (int(user_id),)).fetchone()
        if not row:
            conn.execute(
                "INSERT INTO giso_ai_credit_accounts(user_id,phone,balance,total_used,created_at,updated_at) "
                "VALUES (?,?,0,0,?,?)", (int(user_id), user['phone'], _now(), _now()))
            balance = 0
        else:
            balance = int(row[0] or 0)
        after = max(0, balance + delta)
        actual = after - balance
        conn.execute("UPDATE giso_ai_credit_accounts SET balance=?,updated_at=? WHERE user_id=?",
                     (after, _now(), int(user_id)))
        conn.execute(
            "INSERT INTO giso_ai_credit_ledger(user_id,delta,balance_after,reason,channel,request_key,actor,created_at) "
            "VALUES (?,?,?,?,?,?,?,?)", (int(user_id), actual, after, 'تنظیم دستی اعتبار (حسابرسی)', 'admin', key, actor, _now()))
        conn.commit()
        return True, "اعتبار کاربر ذخیره شد."
