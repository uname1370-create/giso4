# -*- coding: utf-8 -*-
"""§18 پرداخت آنی بله: تبدیل واحد، payload، idempotency واریز، هندلرهای ربات (mock)."""
import asyncio

from giso.app import create_app
from giso.db_core import get_giso_db_conn
from giso import wallet_balepay as bp
from giso.wallet_core import get_wallet_balances

UID = 97301
PHONE = "+989003000001"


def _setup():
    app = create_app()
    with get_giso_db_conn() as conn:
        conn.execute("INSERT OR REPLACE INTO giso_web_auth(id,phone,password_hash) VALUES (?,?,?)", (UID, PHONE, "x"))
        conn.commit()
    return app


def _cleanup():
    with get_giso_db_conn() as conn:
        conn.execute("DELETE FROM giso_web_auth WHERE id=?", (UID,))
        conn.execute("DELETE FROM wallet_transactions WHERE user_id=?", (UID,))
        conn.execute("DELETE FROM giso_balepay_invoices WHERE user_id=?", (UID,))
        conn.commit()


def test_units_and_payload():
    assert bp.toman_to_rial(1500) == 15000
    assert bp.rial_to_toman(15000) == 1500
    assert bp.make_payload(7, 3) == "topup:7:3"
    assert bp.parse_payload("topup:7:3") == (7, 3)
    assert bp.parse_payload("bad::x") == (0, 0)
    assert bp.parse_payload("topup:a:b") == (0, 0)


def test_provider_token_default_is_official_test_token():
    from giso.config import Config
    assert Config.BALE_PROVIDER_TOKEN  # هرگز خالی نباشد
    assert len(Config.BALE_PROVIDER_TOKEN) >= 10


def test_invoice_lifecycle_and_idempotent_credit():
    _setup()
    try:
        ok, msg, link = bp.create_invoice(UID, PHONE, 30000)
        assert ok, msg
        assert link.startswith("https://ble.ir/") and "?start=pay_" in link
        inv = bp.list_user_invoices(UID)[0]
        assert inv["amount_rial"] == 300000
        assert inv["payload"] == bp.make_payload(UID, inv["id"])
        # مبلغ کم → رد
        ok2, _m, _l = bp.create_invoice(UID, PHONE, 1)
        assert not ok2
        # pre-checkout: مبلغ اشتباه رد، درست قبول
        assert not bp.validate_pre_checkout(inv["payload"], 100)[0]
        ok3, err = bp.validate_pre_checkout(inv["payload"], 300000, "tx-9")
        assert ok3, err
        # واریز اول انجام، دوم idempotent
        ok4, _m = bp.credit_payment(inv["payload"], 300000, "tx-9", "track-9")
        assert ok4
        ok5, _m = bp.credit_payment(inv["payload"], 300000, "tx-9", "track-9")
        assert ok5
        assert get_wallet_balances(UID)["cash"] == 30000
        # pre-checkout روی فاکتور پرداخت‌شده → رد
        assert not bp.validate_pre_checkout(inv["payload"], 300000)[0]
    finally:
        _cleanup()


def test_follow_pending_without_transactions():
    _setup()
    try:
        assert "پیدا نشد" in bp.follow_pending(UID)
    finally:
        _cleanup()


class _SP:
    def __init__(self, payload, amount):
        self.invoice_payload = payload
        self.total_amount = amount
        self.telegram_payment_charge_id = "tg-1"
        self.provider_payment_charge_id = "trk-1"


class _Msg:
    def __init__(self, sp):
        self.successful_payment = sp


class _Chat:
    id = 555


class _Update:
    def __init__(self, sp=None, args=None):
        self.message = _Msg(sp) if sp else None
        self.successful_payment = None
        self.effective_chat = _Chat()


class _Bot:
    def __init__(self):
        self.sent, self.invoices = [], []

    async def send_message(self, chat_id, text, **kw):
        self.sent.append((chat_id, text))

    async def send_invoice(self, **kw):
        self.invoices.append(kw)


class _Ctx:
    def __init__(self, args=None):
        self.bot = _Bot()
        self.args = args or []


def test_bot_successful_payment_handler_credits_once():
    import giso.bot_balepay as bb
    _setup()
    try:
        ok, _m, _l = bp.create_invoice(UID, PHONE, 12000)
        inv = bp.list_user_invoices(UID)[0]
        upd = _Update(sp=_SP(inv["payload"], 120000))
        ctx = _Ctx()
        asyncio.run(bb.handle_successful_payment(upd, ctx))
        assert get_wallet_balances(UID)["cash"] == 12000
        assert any("پرداخت موفق" in t for _c, t in ctx.bot.sent)
        # تکرار آپدیت → واریز دوباره رخ نمی‌دهد
        asyncio.run(bb.handle_successful_payment(upd, ctx))
        assert get_wallet_balances(UID)["cash"] == 12000
    finally:
        _cleanup()


def test_bot_pay_start_sends_invoice_in_rial():
    import giso.bot_balepay as bb
    _setup()
    try:
        ok, _m, link = bp.create_invoice(UID, PHONE, 25000)
        token = link.split("pay_")[1]
        upd = _Update(args=["pay_" + token])
        ctx = _Ctx(args=["pay_" + token])
        assert asyncio.run(bb.handle_pay_start(upd, ctx))
        assert len(ctx.bot.invoices) == 1
        inv_kw = ctx.bot.invoices[0]
        assert inv_kw["currency"] == "IRR"
        assert inv_kw["prices"][0].amount == 250000
        assert inv_kw["title"] == bb.INVOICE_TITLE
        # توکن نامعتبر → پیام خطا، بدون فاکتور
        ctx2 = _Ctx(args=["pay_deadbeef"])
        asyncio.run(bb.handle_pay_start(_Update(args=["pay_deadbeef"]), ctx2))
        assert not ctx2.bot.invoices and ctx2.bot.sent
    finally:
        _cleanup()
