import sqlite3
from pathlib import Path

from giso import wallet
from giso import wallet_missions


def connect_factory(path):
    def connect():
        conn = sqlite3.connect(path)
        conn.row_factory = sqlite3.Row
        return conn
    return connect


def seed(path):
    with sqlite3.connect(path) as c:
        c.executescript("""
        CREATE TABLE giso_web_auth(id INTEGER PRIMARY KEY,phone TEXT);
        CREATE TABLE giso_users(bale_id TEXT,phone TEXT,contact_shared INTEGER);
        CREATE TABLE products(id INTEGER PRIMARY KEY,publish_status TEXT);
        CREATE TABLE wallet_missions(id INTEGER PRIMARY KEY,code TEXT UNIQUE,title TEXT,reward_amount INTEGER,reward_scope TEXT,reward_points INTEGER DEFAULT 0,mission_type TEXT DEFAULT 'once',is_active INTEGER,is_deleted INTEGER DEFAULT 0);
        CREATE TABLE wallet_mission_completions(id INTEGER PRIMARY KEY,mission_id INTEGER,user_id INTEGER,event_key TEXT,reward_amount INTEGER,reward_scope TEXT,reward_transaction_id INTEGER,completed_at TEXT,UNIQUE(mission_id,user_id));
        CREATE TABLE wallet_transactions(id INTEGER PRIMARY KEY,user_id INTEGER,kind TEXT,amount INTEGER,status TEXT,source_type TEXT,source_id INTEGER,balance_scope TEXT,idempotency_key TEXT UNIQUE,description TEXT,created_at TEXT);
        INSERT INTO giso_web_auth VALUES(1,'+989121234567');
        INSERT INTO giso_users VALUES('88','+989121234567',1);
        INSERT INTO products VALUES(1,'published'),(2,'published'),(3,'published'),(4,'draft');
        INSERT INTO wallet_missions VALUES(1,'product_explorer','محصولات',50000,'spend',0,'once',1,0);
        INSERT INTO wallet_missions VALUES(2,'bale_connected','بله',20000,'spend',0,'once',1,0);
        """)


def test_product_explorer_requires_distinct_published_and_elapsed_time(monkeypatch, tmp_path):
    db = tmp_path / "wallet.db"; seed(db)
    monkeypatch.setattr(wallet, "get_giso_db_conn", connect_factory(db))
    monkeypatch.setattr(wallet_missions, "get_giso_db_conn", connect_factory(db))
    assert wallet.record_product_mission_view(1, 1)[0]
    assert wallet.record_product_mission_view(1, 1)[0]  # duplicate does not advance
    assert wallet.record_product_mission_view(1, 4)[0] is False  # draft rejected
    wallet.record_product_mission_view(1, 2)
    wallet.record_product_mission_view(1, 3)
    with sqlite3.connect(db) as c:
        assert c.execute("SELECT COUNT(*) FROM wallet_mission_completions").fetchone()[0] == 0
        c.execute("UPDATE wallet_product_mission_views SET viewed_at=datetime('now','localtime','-31 seconds') WHERE product_id=1")
    wallet.record_product_mission_view(1, 3)
    with sqlite3.connect(db) as c:
        tx = c.execute("SELECT amount,balance_scope FROM wallet_transactions").fetchone()
        assert tx == (50000, "spend")


def test_verified_bale_connection_is_once_and_spend_only(monkeypatch, tmp_path):
    db = tmp_path / "wallet.db"; seed(db)
    monkeypatch.setattr(wallet, "get_giso_db_conn", connect_factory(db))
    monkeypatch.setattr(wallet_missions, "get_giso_db_conn", connect_factory(db))
    assert wallet.complete_bale_connection_mission("88")[0]
    assert wallet.complete_bale_connection_mission("88")[0]
    with sqlite3.connect(db) as c:
        assert c.execute("SELECT COUNT(*) FROM wallet_mission_completions WHERE mission_id=2").fetchone()[0] == 1
        assert c.execute("SELECT amount,balance_scope FROM wallet_transactions WHERE source_id=1").fetchone() == (20000, "spend")


def test_registry_defaults_and_real_event_hooks_exist():
    root = Path(__file__).resolve().parents[2]
    assert wallet.MISSION_EVENTS["product_explorer"][0]
    models = (root / "giso/models.py").read_text()
    assert "'product_explorer'" in models and "50000" in models
    assert "beauty_center_published" in (root / "giso/beauty_centers/services.py").read_text()
    assert "complete_bale_connection_mission" in (root / "giso/base.py").read_text()
    assert "review_submit" in (root / "giso/marketplace/routes.py").read_text()
