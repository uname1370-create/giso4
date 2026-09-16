# -*- coding: utf-8 -*-
"""ربات بله: پرداخت آنی کیف پول — هندلرهای نازک PTB.

منطق مالی در giso/wallet_balepay.py است (هر کد در خانهٔ خودش)؛
این ماژول فقط updateهای پرداخت را به آن وصل می‌کند.
"""
from __future__ import annotations

import logging

logger = logging.getLogger("giso.bot_balepay")

INVOICE_TITLE = "شارژ کیف پول گیسو"


def _find_invoice_by_token(token: str):
    from giso.db_core import get_giso_db_conn
    from giso import wallet_balepay as bp
    with get_giso_db_conn() as conn:
        bp.ensure_balepay_tables(conn)
        row = conn.execute("SELECT * FROM giso_balepay_invoices WHERE token=?", (str(token),)).fetchone()
    return dict(row) if row else None


async def handle_pay_start(update, context) -> bool:
    """Deep-link «/start pay_<token>» → ارسال فاکتور (sendInvoice)."""
    try:
        arg = str((getattr(context, "args", None) or [""])[0] or "")
        if not arg.startswith("pay_"):
            return False
        chat_id = update.effective_chat.id if update.effective_chat else None
        inv = _find_invoice_by_token(arg[4:])
        if not inv or not chat_id:
            if chat_id:
                await context.bot.send_message(chat_id, "❌ فاکتور پیدا نشد؛ از سایت دوباره اقدام کن.")
            return True
        if inv["status"] == "paid":
            await context.bot.send_message(chat_id, "✅ این فاکتور قبلاً پرداخت شده است.")
            return True
        from telegram import LabeledPrice
        from giso.config import Config
        await context.bot.send_invoice(
            chat_id=chat_id,
            title=INVOICE_TITLE,
            description=f"افزایش موجودی کیف پول گیسو — {inv['amount_toman']} تومان",
            payload=inv["payload"],
            provider_token=Config.BALE_PROVIDER_TOKEN,
            currency="IRR",
            prices=[LabeledPrice("افزایش موجودی", int(inv["amount_rial"]))],
            start_parameter="pay",
        )
        return True
    except Exception:
        logger.exception("balepay pay_start failed")
        try:
            await context.bot.send_message(update.effective_chat.id, "⚠️ ارسال فاکتور ناموفق بود؛ دوباره تلاش کن.")
        except Exception:
            pass
        return True


async def handle_pre_checkout(update, context) -> None:
    """باید زیر ۱۰ ثانیه پاسخ دهیم وگرنه بله پرداخت را لغو می‌کند."""
    pcq = getattr(update, "pre_checkout_query", None)
    if not pcq:
        return
    try:
        from giso import wallet_balepay as bp
        ok, err = bp.validate_pre_checkout(pcq.invoice_payload, pcq.total_amount, str(pcq.id or ""))
        if ok:
            await pcq.answer(ok=True)
        else:
            await pcq.answer(ok=False, error_message=err or "پرداخت تأیید نشد.")
    except Exception:
        logger.exception("balepay pre_checkout failed")
        try:
            await pcq.answer(ok=False, error_message="خطای داخلی؛ دوباره تلاش کن.")
        except Exception:
            pass


async def handle_successful_payment(update, context) -> None:
    """پرداخت قطعی → واریز idempotent کیف پول سایت + رسید در چت."""
    sp = getattr(getattr(update, "message", None), "successful_payment", None)
    if not sp:
        return
    tracking = str(getattr(sp, "provider_payment_charge_id", "") or "")
    try:
        from giso import wallet_balepay as bp
        ok, msg = bp.credit_payment(
            sp.invoice_payload, sp.total_amount,
            str(getattr(sp, "telegram_payment_charge_id", "") or ""), tracking)
        chat_id = update.effective_chat.id if update.effective_chat else None
        if chat_id:
            if ok:
                await context.bot.send_message(
                    chat_id, f"✅ پرداخت موفق — {msg}\n🧾 کد پیگیری: {tracking or '—'}")
            else:
                await context.bot.send_message(
                    chat_id, f"⚠️ {msg}\nاگر مبلغ از کیف پولت کسر شده، با پشتیبانی تماس بگیر.")
    except Exception:
        logger.exception("balepay successful_payment failed")
