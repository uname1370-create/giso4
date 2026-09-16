# -*- coding: utf-8 -*-
"""پرداخت آنی کیف پول با بازوی بله (docs.bale.ai — بخش پرداخت).

جریان: سایت فاکتور pending می‌سازد → کاربر با deep-link به ربات می‌رود →
ربات sendInvoice می‌فرستد → pre_checkout_query (زیر ۱۰ ثانیه تأیید) →
SuccessfulPayment → واریز idempotent به دفترکل کیف پول سایت.
هر کد در خانهٔ خودش: منطق مالی اینجا، هندلرهای PTB در bot_balepay.py.
"""
from __future__ import annotations

import json
import logging
import secrets
import urllib.parse
import urllib.request
from datetime import datetime

from giso.db_core import get_giso_db_conn

logger = logging.getLogger("giso.wallet_balepay")

SCHEMA = """
CREATE TABLE IF NOT EXISTS giso_balepay_invoices (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    phone TEXT DEFAULT '',
    amount_toman INTEGER NOT NULL,
    amount_rial INTEGER NOT NULL,
    payload TEXT NOT NULL UNIQUE,
    token TEXT NOT NULL UNIQUE,
    status TEXT NOT NULL DEFAULT 'pending',
    transaction_id TEXT DEFAULT '',
    tracking_code TEXT DEFAULT '',
    created_at TEXT DEFAULT '',
    paid_at TEXT DEFAULT ''
);
"""

BALE_API = "https://tapi.bale.ai/bot"


def _now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def ensure_balepay_tables(conn=None) -> None:
    own = conn is None
    if own:
        conn = get_giso_db_conn()
    try:
        conn.executescript(SCHEMA)
        if own:
            conn.commit()
    finally:
        if own:
            conn.close()


def _provider_token() -> str:
    from giso.config import Config
    return str(getattr(Config, "BALE_PROVIDER_TOKEN", "") or "").strip()


def toman_to_rial(amount_toman: int) -> int:
    """واحد مبلغ در API پرداخت بله ریال (IRR) است؛ سایت تومانی است."""
    return int(amount_toman) * 10


def rial_to_toman(amount_rial: int) -> int:
    return int(amount_rial) // 10


def topup_method() -> str:
    """روش فعال افزایش موجودی: receipt | bale | both (از تنظیمات مالی)."""
    try:
        from giso.wallet_core import get_financial_settings
        return str(get_financial_settings().get("topup_method") or "both")
    except Exception:
        return "both"


def balepay_enabled() -> bool:
    return topup_method() in ("bale", "both")


def make_payload(user_id: int, invoice_id: int) -> str:
    return f"topup:{int(user_id)}:{int(invoice_id)}"


def parse_payload(payload: str) -> tuple[int, int]:
    parts = str(payload or "").split(":")
    if len(parts) != 3 or parts[0] != "topup":
        return 0, 0
    try:
        return int(parts[1]), int(parts[2])
    except (TypeError, ValueError):
        return 0, 0


def _bot_handle() -> str:
    try:
        from giso_admin import get_giso_config
        return str(get_giso_config("bale_bot_handle", "1191639507") or "1191639507").strip().lstrip("@")
    except Exception:
        return "1191639507"


def create_invoice(user_id: int, phone: str, amount_toman) -> tuple[bool, str, str]:
    """ثبت فاکتور pending و ساخت deep-link ربات. خروجی: (ok, پیام, لینک)."""
    if not balepay_enabled():
        return False, "پرداخت آنی با بله فعلاً غیرفعال است.", ""
    try:
        from giso.wallet_core import get_financial_settings
        settings = get_financial_settings()
        if not settings.get("topup_enabled"):
            return False, "درخواست افزایش موجودی فعلاً غیرفعال است.", ""
        amount = int(amount_toman)
        if amount < int(settings.get("min_topup") or 0):
            return False, f"حداقل مبلغ افزایش موجودی {settings.get('min_topup')} تومان است.", ""
    except (TypeError, ValueError):
        return False, "مبلغ نامعتبر است.", ""
    token = secrets.token_hex(16)
    with get_giso_db_conn() as conn:
        ensure_balepay_tables(conn)
        cur = conn.execute(
            "INSERT INTO giso_balepay_invoices(user_id,phone,amount_toman,amount_rial,payload,token,status,created_at) "
            "VALUES (?,?,?,?,?,?,'pending',?)",
            (int(user_id), str(phone or ""), amount, toman_to_rial(amount),
             f"tmp:{token}", token, _now()))
        invoice_id = int(cur.lastrowid)
        conn.execute("UPDATE giso_balepay_invoices SET payload=? WHERE id=?",
                     (make_payload(user_id, invoice_id), invoice_id))
        conn.commit()
    link = f"https://ble.ir/{_bot_handle()}?start=pay_{token}"
    return True, f"فاکتور #{invoice_id} ساخته شد؛ پرداخت را در بله ادامه بده.", link


def validate_pre_checkout(invoice_payload: str, total_amount_rial: int, transaction_id: str = "") -> tuple[bool, str]:
    """بررسی فاکتور پیش از نهایی‌شدن پرداخت (باید زیر ۱۰ ثانیه پاسخ داده شود)."""
    with get_giso_db_conn() as conn:
        ensure_balepay_tables(conn)
        row = conn.execute("SELECT * FROM giso_balepay_invoices WHERE payload=?", (str(invoice_payload),)).fetchone()
        if not row:
            return False, "فاکتور معتبر نیست."
        if row["status"] == "paid":
            return False, "این فاکتور قبلاً پرداخت شده است."
        if int(row["amount_rial"]) != int(total_amount_rial):
            return False, "مبلغ پرداخت با فاکتور مطابقت ندارد."
        if transaction_id:
            conn.execute("UPDATE giso_balepay_invoices SET transaction_id=? WHERE id=?",
                         (str(transaction_id), int(row["id"])))
            conn.commit()
    return True, ""


def credit_payment(invoice_payload: str, total_amount_rial: int,
                   transaction_id: str = "", tracking_code: str = "") -> tuple[bool, str]:
    """واریز idempotent به دفترکل کیف پول پس از SuccessfulPayment."""
    with get_giso_db_conn() as conn:
        ensure_balepay_tables(conn)
        try:
            conn.execute("BEGIN IMMEDIATE")
            row = conn.execute("SELECT * FROM giso_balepay_invoices WHERE payload=?", (str(invoice_payload),)).fetchone()
            if not row:
                conn.rollback()
                return False, "فاکتور معتبر نیست."
            if row["status"] == "paid":
                conn.rollback()
                return True, "این فاکتور قبلاً واریز شده است."
            if int(row["amount_rial"]) != int(total_amount_rial):
                conn.rollback()
                return False, "مبلغ پرداخت با فاکتور مطابقت ندارد."
            invoice_id = int(row["id"])
            conn.execute(
                "UPDATE giso_balepay_invoices SET status='paid', transaction_id=?, tracking_code=?, paid_at=? WHERE id=?",
                (str(transaction_id), str(tracking_code), _now(), invoice_id))
            conn.execute(
                "INSERT INTO wallet_transactions "
                "(user_id,kind,amount,status,source_type,source_id,balance_scope,idempotency_key,description,created_at) "
                "VALUES (?, 'topup', ?, 'available', 'wallet_balepay', ?, 'cash', ?, ?, ?)",
                (int(row["user_id"]), int(row["amount_toman"]), invoice_id,
                 f"balepay:{invoice_id}", f"پرداخت آنی بله — فاکتور #{invoice_id}", _now()))
            conn.commit()
        except Exception:
            conn.rollback()
            logger.exception("balepay credit failed for payload=%s", invoice_payload)
            return False, "واریز ناموفق بود."
    try:
        if row["phone"]:
            from giso.panel.modules.notifications import log_user_notification
            log_user_notification(row["phone"], "topup_status", "شارژ کیف پول (پرداخت آنی بله)",
                                  f"فاکتور #{invoice_id} پرداخت شد و {int(row['amount_toman'])} تومان به کیف پول شما اضافه شد.",
                                  source_type="wallet_balepay", source_id=invoice_id, category="wallet")
    except Exception as e:
        logger.debug("balepay notify failed: %s", e)
    return True, f"{int(row['amount_toman'])} تومان به کیف پول شما اضافه شد."


def list_user_invoices(user_id: int, limit: int = 20) -> list:
    with get_giso_db_conn() as conn:
        ensure_balepay_tables(conn)
        rows = conn.execute(
            "SELECT * FROM giso_balepay_invoices WHERE user_id=? ORDER BY id DESC LIMIT ?",
            (int(user_id), int(limit))).fetchall()
    return [dict(r) for r in rows]


def inquire_transaction(transaction_id: str) -> dict:
    """استعلام وضعیت تراکنش از بله (inquireTransaction)."""
    token = _provider_token()
    if not token or not transaction_id:
        return {}
    url = f"{BALE_API}{token}/inquireTransaction"
    data = urllib.parse.urlencode({"transaction_id": str(transaction_id)}).encode()
    req = urllib.request.Request(url, data=data, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            body = json.loads(resp.read().decode("utf-8"))
        return body.get("result") or {} if body.get("ok") else {}
    except Exception as e:
        logger.warning("inquireTransaction failed: %s", e)
        return {}


def follow_pending(user_id: int) -> str:
    """پیگیری فاکتورهای بلاتکلیف کاربر با استعلام تراکنش."""
    done, pending = 0, 0
    for inv in list_user_invoices(user_id, 30):
        if inv["status"] != "pending" or not inv["transaction_id"]:
            continue
        pending += 1
        tx = inquire_transaction(inv["transaction_id"])
        if str(tx.get("status")) == "paid" and int(tx.get("amount") or 0) == int(inv["amount_rial"]):
            ok, _msg = credit_payment(inv["payload"], int(inv["amount_rial"]),
                                      inv["transaction_id"], str(tx.get("id") or ""))
            done += 1 if ok else 0
    if pending == 0:
        return "پرداخت در جریانی برای پیگیری پیدا نشد."
    return f"{done} از {pending} فاکتور در جریان، واریز شد." if done else "پرداختی هنوز توسط بله تأیید نشده؛ کمی بعد دوباره پیگیری کن."
