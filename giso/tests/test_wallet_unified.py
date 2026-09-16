# -*- coding: utf-8 -*-
"""Focused regression tests for the unified wallet ledger and atomic checkout."""
import sqlite3

import pytest

from giso import wallet
from giso import wallet_core, wallet_missions


SCHEMA = """
PRAGMA foreign_keys=ON;
CREATE TABLE giso_web_auth (id INTEGER PRIMARY KEY, phone TEXT, name TEXT);
CREATE TABLE products (
 id INTEGER PRIMARY KEY, name TEXT, price INTEGER, in_stock INTEGER DEFAULT 1,
 publish_status TEXT DEFAULT 'published'
);
CREATE TABLE product_orders (
 id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, phone TEXT, customer_name TEXT,
 product_id INTEGER, checkout_id INTEGER, invoice_id INTEGER, address TEXT, quantity INTEGER, status TEXT,
 tracking_code TEXT, shipping_cost INTEGER, courier_note TEXT, delivery_time TEXT, created_at TEXT
);
CREATE TABLE shop_checkouts (
 id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, gross_amount INTEGER,
 discount_amount INTEGER, wallet_used INTEGER, cash_wallet_used INTEGER,
 spend_wallet_used INTEGER, cod_amount INTEGER, discount_code TEXT, status TEXT, created_at TEXT
);
CREATE TABLE shop_invoices (
 id INTEGER PRIMARY KEY AUTOINCREMENT, invoice_number TEXT UNIQUE NOT NULL, checkout_id INTEGER UNIQUE,
 user_id INTEGER, customer_name TEXT, customer_phone TEXT, customer_address TEXT, gross_amount INTEGER,
 discount_amount INTEGER, payable_amount INTEGER, wallet_paid_amount INTEGER, cod_amount INTEGER,
 payment_status TEXT, created_at TEXT
);
CREATE TABLE shop_invoice_items (
 id INTEGER PRIMARY KEY AUTOINCREMENT, invoice_id INTEGER, order_id INTEGER, product_id INTEGER,
 product_name TEXT, unit_price INTEGER, quantity INTEGER, line_total INTEGER
);
CREATE TABLE wallet_transactions (
 id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL, kind TEXT, amount INTEGER,
 status TEXT, source_type TEXT, source_id INTEGER, balance_scope TEXT DEFAULT 'cash',
 idempotency_key TEXT DEFAULT '', description TEXT, created_at TEXT
);
CREATE UNIQUE INDEX ux_test_wallet_idempotency ON wallet_transactions(idempotency_key) WHERE idempotency_key != '';
CREATE TABLE discount_codes (
 id INTEGER PRIMARY KEY AUTOINCREMENT, code TEXT UNIQUE, discount_type TEXT,
 discount_value INTEGER, min_order_amount INTEGER DEFAULT 0, max_uses INTEGER DEFAULT 0,
 used_count INTEGER DEFAULT 0, is_active INTEGER DEFAULT 1, expires_at TEXT, created_at TEXT
);
CREATE TABLE withdrawal_requests (
 id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, amount INTEGER, card_holder_name TEXT,
 card_number TEXT, sheba TEXT, status TEXT, admin_note TEXT, created_at TEXT, updated_at TEXT
);
CREATE TABLE wallet_topup_requests (
 id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, amount INTEGER, payment_reference TEXT,
 receipt_path TEXT, user_note TEXT, status TEXT, admin_note TEXT, created_at TEXT, reviewed_at TEXT,
 reviewed_by_user_id INTEGER DEFAULT 0
);
CREATE TABLE wallet_missions (
 id INTEGER PRIMARY KEY AUTOINCREMENT, code TEXT UNIQUE, title TEXT, description TEXT,
 reward_amount INTEGER, reward_scope TEXT, reward_points INTEGER DEFAULT 0, mission_type TEXT DEFAULT 'once', is_active INTEGER, is_deleted INTEGER DEFAULT 0, sort_order INTEGER,
 created_at TEXT, updated_at TEXT
);
CREATE TABLE wallet_mission_tombstones (code TEXT PRIMARY KEY, deleted_at TEXT);
CREATE TABLE wallet_mission_completions (
 id INTEGER PRIMARY KEY AUTOINCREMENT, mission_id INTEGER, user_id INTEGER, event_key TEXT,
 reward_amount INTEGER, reward_scope TEXT, reward_transaction_id INTEGER, completed_at TEXT,
 UNIQUE(mission_id,user_id)
);
"""


@pytest.fixture()
def ledger(tmp_path, monkeypatch):
    path = tmp_path / "wallet.db"
    conn = sqlite3.connect(path)
    conn.executescript(SCHEMA)
    conn.execute("INSERT INTO giso_web_auth(id,phone,name) VALUES (1,'+989121111111','test')")
    conn.execute("INSERT INTO products(id,name,price,in_stock,publish_status) VALUES (1,'product',120,1,'published')")
    conn.commit()
    conn.close()

    def connect():
        db = sqlite3.connect(path, check_same_thread=False)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys=ON")
        return db

    monkeypatch.setattr(wallet, "get_giso_db_conn", connect)
    # U5: مأموریتها/هسته در ماژولهای جدید؛ اتصال تست را آنجا هم وصل کن.
    monkeypatch.setattr(wallet_missions, "get_giso_db_conn", connect)
    monkeypatch.setattr(wallet_core, "get_giso_db_conn", connect)
    return path, connect


def _credit(connect, amount, scope="cash"):
    with connect() as conn:
        conn.execute(
            "INSERT INTO wallet_transactions "
            "(user_id,kind,amount,status,source_type,source_id,balance_scope,description,created_at) "
            "VALUES (1,'test',?,'available','test',0,?,'test','now')",
            (amount, scope),
        )
        conn.commit()


def test_balance_counts_used_debits_and_scopes(ledger):
    _path, connect = ledger
    _credit(connect, 100, "cash")
    _credit(connect, 80, "spend")
    with connect() as conn:
        conn.execute(
            "INSERT INTO wallet_transactions "
            "(user_id,kind,amount,status,source_type,source_id,balance_scope,description,created_at) "
            "VALUES (1,'purchase',-35,'used','shop_checkout',1,'cash','used','now')"
        )
        conn.execute(
            "INSERT INTO wallet_transactions "
            "(user_id,kind,amount,status,source_type,source_id,balance_scope,description,created_at) "
            "VALUES (1,'purchase',-20,'used','shop_checkout',1,'spend','used','now')"
        )
        conn.commit()
    assert wallet.get_wallet_balances(1) == {
        "cash": 65, "spend": 60, "usable": 125, "settleable": 65,
        "balance": 125, "cash_raw": 65, "spend_raw": 60,
    }


def test_checkout_is_atomic_and_cannot_reuse_spent_credit(ledger):
    _path, connect = ledger
    _credit(connect, 100, "cash")
    _credit(connect, 50, "spend")
    customer = {"name": "buyer", "phone": "09121111111", "address": "Mashhad"}
    first = wallet.create_shop_checkout_atomic(
        1, [{"product_id": 1, "quantity": 1, "tracking_code": "A"}],
        customer, pay_with_wallet=True,
    )
    assert first["spend_wallet_used"] == 50
    assert first["cash_wallet_used"] == 70
    assert first["cod_amount"] == 0
    assert first["payment_status"] == "settled"
    assert wallet.get_wallet_balances(1)["usable"] == 30
    with connect() as conn:
        invoice = conn.execute("SELECT * FROM shop_invoices WHERE id=?", (first["invoice_id"],)).fetchone()
        assert invoice["gross_amount"] == 120  # full total is never zero after wallet settlement
        assert invoice["wallet_paid_amount"] == 120
        assert invoice["cod_amount"] == 0
        assert conn.execute("SELECT COUNT(*) FROM shop_invoice_items WHERE invoice_id=?", (first["invoice_id"],)).fetchone()[0] == 1

    second = wallet.create_shop_checkout_atomic(
        1, [{"product_id": 1, "quantity": 1, "tracking_code": "B"}],
        customer, pay_with_wallet=True,
    )
    assert second["wallet_used"] == 30
    assert second["cod_amount"] == 90
    assert second["payment_status"] == "split_due"
    assert wallet.get_wallet_balances(1)["usable"] == 0
    with connect() as conn:
        invoice = conn.execute("SELECT * FROM shop_invoices WHERE id=?", (second["invoice_id"],)).fetchone()
        assert (invoice["payable_amount"], invoice["wallet_paid_amount"], invoice["cod_amount"]) == (120, 30, 90)
    with connect() as conn:
        assert conn.execute("SELECT COUNT(*) FROM product_orders").fetchone()[0] == 2
        sources = conn.execute(
            "SELECT DISTINCT source_id FROM wallet_transactions WHERE source_type='shop_checkout'"
        ).fetchall()
        assert {row[0] for row in sources} == {first["checkout_id"], second["checkout_id"]}


def test_multi_item_checkout_uses_one_invoice_and_one_tracking_code(ledger):
    _path, connect = ledger
    with connect() as conn:
        conn.execute("INSERT INTO products(id,name,price,in_stock,publish_status) VALUES (2,'product-2',80,1,'published')")
        conn.commit()
    customer = {"name": "buyer", "phone": "09121111111", "address": "Mashhad"}
    result = wallet.create_shop_checkout_atomic(
        1,
        [
            {"product_id": 1, "quantity": 1, "tracking_code": "GSO-SHARED"},
            {"product_id": 2, "quantity": 2, "tracking_code": "SHOULD-NOT-BE-USED"},
        ],
        customer,
    )
    with connect() as conn:
        orders = conn.execute(
            "SELECT checkout_id,invoice_id,tracking_code FROM product_orders ORDER BY id"
        ).fetchall()
        assert len(orders) == 2
        assert {row["checkout_id"] for row in orders} == {result["checkout_id"]}
        assert {row["invoice_id"] for row in orders} == {result["invoice_id"]}
        assert {row["tracking_code"] for row in orders} == {"GSO-SHARED"}
        assert conn.execute(
            "SELECT COUNT(*) FROM shop_invoice_items WHERE invoice_id=?", (result["invoice_id"],)
        ).fetchone()[0] == 2


def test_failed_checkout_rolls_back_order_and_wallet(ledger):
    _path, connect = ledger
    _credit(connect, 100, "cash")
    customer = {"name": "buyer", "phone": "09121111111", "address": "Mashhad"}
    with pytest.raises(wallet.WalletCheckoutError):
        wallet.create_shop_checkout_atomic(
            1, [{"product_id": 999, "quantity": 1, "tracking_code": "X"}],
            customer, pay_with_wallet=True,
        )
    assert wallet.get_wallet_balances(1)["cash"] == 100
    with connect() as conn:
        assert conn.execute("SELECT COUNT(*) FROM shop_checkouts").fetchone()[0] == 0
        assert conn.execute("SELECT COUNT(*) FROM product_orders").fetchone()[0] == 0


def test_settlement_uses_cash_only_and_reserves_atomically(ledger, monkeypatch):
    _path, connect = ledger
    _credit(connect, 50, "cash")
    _credit(connect, 100, "spend")
    monkeypatch.setattr(wallet, "get_financial_settings", lambda: {
        "withdrawal_enabled": True, "min_withdrawal": 1,
    })
    ok, _message, _wid = wallet.create_withdrawal_request(
        1, 60, "holder", card="6037991234567890"
    )
    assert not ok  # total wallet is 150, but settleable cash is only 50.
    ok, _message, wid = wallet.create_withdrawal_request(
        1, 40, "holder", card="6037991234567890"
    )
    assert ok and wid
    balances = wallet.get_wallet_balances(1)
    assert balances["cash"] == 10
    assert balances["spend"] == 100


def test_mission_reward_is_spend_and_once_only(ledger):
    _path, connect = ledger
    with connect() as conn:
        conn.execute(
            "INSERT INTO wallet_missions(code,title,description,reward_amount,reward_scope,is_active,sort_order) "
            "VALUES ('registration','register','',25,'spend',1,1)"
        )
        conn.commit()
    assert wallet.complete_mission(1, "registration", "user:1")[0]
    assert wallet.complete_mission(1, "registration", "user:1")[0]
    assert wallet.get_wallet_balances(1)["spend"] == 25
    with connect() as conn:
        assert conn.execute("SELECT COUNT(*) FROM wallet_mission_completions").fetchone()[0] == 1
        assert conn.execute("SELECT COUNT(*) FROM wallet_transactions WHERE kind='mission_reward'").fetchone()[0] == 1


def test_topup_approval_is_cash_and_idempotent(ledger, monkeypatch):
    _path, connect = ledger
    monkeypatch.setattr(wallet, "get_financial_settings", lambda: {
        "topup_enabled": True, "min_topup": 1,
    })
    ok, _message, request_id = wallet.create_topup_request(
        1, 75, "", receipt_path="a" * 32 + ".jpg"
    )
    assert ok and request_id
    monkeypatch.setattr(wallet, "is_financial_superadmin", lambda: True)
    monkeypatch.setattr(wallet_missions, "is_financial_superadmin", lambda: True)
    assert wallet.review_topup(request_id, "approved")[0]
    assert not wallet.review_topup(request_id, "approved")[0]
    assert wallet.get_wallet_balances(1)["cash"] == 75
    with connect() as conn:
        assert conn.execute("SELECT COUNT(*) FROM wallet_transactions WHERE kind='topup'").fetchone()[0] == 1


def test_financial_admin_pages_and_actions_use_require_super():
    from pathlib import Path
    source = (Path(__file__).resolve().parents[1] / "panel" / "routes.py").read_text(encoding="utf-8")
    # فاز پنل سوپرادمین: صفحاتِ «مشاهده» برای special باز و با @require_manage
    # محافظت می‌شوند؛ عملیات حساس مالی همچنان @require_super می‌مانند.
    view_pages = (
        'def users():',
        'def wallet():',
        'def wallet_topup_receipt(request_id):',
    )
    for signature in view_pages:
        before = source[:source.index(signature)].rstrip().splitlines()
        assert before[-1].strip() == "@require_manage", signature
    sensitive = (
        'def user_wallet(user_id):',
        'def wallet_mission_create():',
        'def wallet_mission_update(mission_id):',
        'def wallet_mission_delete(mission_id):',
        'def wallet_topup_status(request_id):',
        'def wallet_settlement_status(withdrawal_id):',
        'def wallet_settings():',
    )
    for signature in sensitive:
        before = source[:source.index(signature)].rstrip().splitlines()
        assert before[-1].strip() == "@require_super", signature
    legacy = (Path(__file__).resolve().parents[1] / "app.py").read_text(encoding="utf-8")
    for signature in (
        "def admin_referral_settings():",
        "def admin_user_wallet(user_id):",
        "def admin_withdrawal_status(withdrawal_id):",
    ):
        before = legacy[:legacy.index(signature)].rstrip().splitlines()
        assert before[-1].strip() == "@require_super", signature


def test_management_service_denies_non_super(ledger, monkeypatch):
    monkeypatch.setattr(wallet, "is_financial_superadmin", lambda: False)
    assert not wallet.manual_adjust(1, 10, "cash", "denied")[0]
    assert not wallet.review_topup(1, "approved")[0]
    assert not wallet.review_withdrawal(1, "paid")[0]


def test_production_user_deletion_preserves_financial_history():
    from pathlib import Path
    root = Path(__file__).resolve().parents[1]
    production = (root / "app.py").read_text(encoding="utf-8")
    production += (root / "panel" / "modules" / "users.py").read_text(encoding="utf-8")
    assert "DELETE FROM wallet_transactions" not in production
    assert "DELETE FROM referrals" not in production


def test_topup_requires_receipt_but_reference_is_optional(ledger, monkeypatch):
    monkeypatch.setattr(wallet, "get_financial_settings", lambda: {
        "topup_enabled": True, "min_topup": 1,
    })
    assert not wallet.create_topup_request(1, 20, "optional-reference")[0]
    ok, _message, request_id = wallet.create_topup_request(
        1, 20, "", receipt_path="b" * 32 + ".png"
    )
    assert ok and request_id


def test_mission_create_edit_delete_and_restore_builtin(ledger, monkeypatch):
    _path, connect = ledger
    monkeypatch.setattr(wallet, "is_financial_superadmin", lambda: True)
    monkeypatch.setattr(wallet_missions, "is_financial_superadmin", lambda: True)
    ok, _ = wallet.create_mission({
        "code": "registration", "title": "عضویت", "description": "ثبت نام",
        "reward_amount": "۱۲۵۰۰", "is_active": True,
    })
    assert ok
    with connect() as conn:
        mission_id = conn.execute("SELECT id FROM wallet_missions WHERE code='registration'").fetchone()[0]
    assert wallet.update_mission(mission_id, {
        "title": "عضویت موفق", "description": "شرح تازه", "reward_amount": 15000,
        "is_active": True,
    })[0]
    assert wallet.delete_mission(mission_id)[0]
    assert wallet.list_missions_admin() == []
    with connect() as conn:
        assert conn.execute("SELECT 1 FROM wallet_mission_tombstones WHERE code='registration'").fetchone()
    # create is also the supported restore path for a deleted built-in mission.
    assert wallet.create_mission({
        "code": "registration", "title": "ثبت‌نام دوباره", "reward_amount": 9000,
        "is_active": True,
    })[0]
    assert wallet.list_missions_admin()[0]["title"] == "ثبت‌نام دوباره"


def test_cod_checkout_also_has_invoice(ledger):
    _path, connect = ledger
    result = wallet.create_shop_checkout_atomic(
        1, [{"product_id": 1, "quantity": 2, "tracking_code": "COD"}],
        {"name": "buyer", "phone": "09121111111", "address": "Mashhad"},
        pay_with_wallet=False,
    )
    assert result["payment_status"] == "cod_due"
    assert (result["gross_amount"], result["wallet_used"], result["cod_amount"]) == (240, 0, 240)
    with connect() as conn:
        invoice = conn.execute("SELECT * FROM shop_invoices WHERE id=?", (result["invoice_id"],)).fetchone()
        assert (invoice["gross_amount"], invoice["payable_amount"], invoice["cod_amount"]) == (240, 240, 240)
        order = conn.execute("SELECT invoice_id FROM product_orders WHERE id=?", (result["order_ids"][0],)).fetchone()
        assert order["invoice_id"] == result["invoice_id"]


def test_persian_toman_format_no_ambiguous_separator():
    """سپک جدید کاربر: مبلغ تومان بدون جداکنندهٔ هزارگانِ شبیه اعشار نمایش داده شود."""
    from pathlib import Path
    from giso.money import format_toman, to_persian_digits
    sep = "٬"  # جداکنندهٔ هزارگان فارسی — هرگز شبیه نقطهٔ اعشار
    assert format_toman(1234567) == to_persian_digits("1,234,567").replace(",", sep) + " تومان"
    assert format_toman(-5000) == "-" + to_persian_digits("5,000").replace(",", sep) + " تومان"
    assert format_toman("١,٢٣٤") == to_persian_digits("1,234").replace(",", sep) + " تومان"
    assert to_persian_digits("IR١٢-34") == "IR" + to_persian_digits(12) + "-" + to_persian_digits(34)
    cart = (Path(__file__).resolve().parents[1] / "shop" / "templates" / "cart.html").read_text()
    assert "toLocaleString('en-US')" not in cart



def test_receipt_validation_accepts_real_jpeg_and_rejects_spoof(tmp_path, monkeypatch):
    from io import BytesIO
    from PIL import Image
    from werkzeug.datastructures import FileStorage
    from giso import wallet_receipts

    monkeypatch.setattr(wallet_receipts, "receipt_directory", lambda: tmp_path)
    data = BytesIO()
    Image.new("RGB", (80, 60), "white").save(data, "JPEG")
    data.seek(0)
    stored = wallet_receipts.save_topup_receipt(FileStorage(stream=data, filename="receipt.jpeg"), 1)
    assert stored.endswith(".jpg") and (tmp_path / stored).is_file()

    with pytest.raises(wallet_receipts.ReceiptValidationError):
        wallet_receipts.save_topup_receipt(
            FileStorage(stream=BytesIO(b"not an image"), filename="receipt.jpg"), 1
        )
    with pytest.raises(wallet_receipts.ReceiptValidationError):
        wallet_receipts.save_topup_receipt(
            FileStorage(stream=BytesIO(b"anything"), filename="receipt.gif"), 1
        )
