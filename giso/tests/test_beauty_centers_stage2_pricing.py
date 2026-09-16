# -*- coding: utf-8 -*-
"""Stage 2: optional, non-guaranteed starting price and cost level."""
import sqlite3
from pathlib import Path

from giso.beauty_centers import schema, services

ROOT = Path(__file__).resolve().parents[2]


def test_price_levels_and_normalization():
    assert services.PRICE_LEVELS == {
        "economic": "اقتصادی", "standard": "متعادل", "premium": "ممتاز",
        "on_request": "قیمت پس از بررسی",
    }
    fields, error = services._normalize_fields({
        "name":"مرکز مو", "category":"hair", "center_type":"hair_center",
        "city":"مشهد", "business_phone":"09120000000", "services":["haircut"],
        "price_level":"economic", "starting_price":"۵۰۰,۰۰۰ تومان",
    })
    assert not error
    assert fields["price_level"] == "economic"
    assert fields["starting_price"] == 500000
    _fields, error = services._normalize_fields({
        "name":"مرکز", "category":"hair", "center_type":"hair_center", "city":"مشهد",
        "business_phone":"09120000000", "services":["haircut"], "price_level":"fake",
    })
    assert "سطح هزینه" in error


def test_forms_and_filter_have_optional_starting_price():
    register = (ROOT/"giso/beauty_centers/templates/beauty_centers/register.html").read_text(encoding="utf-8")
    owner = (ROOT/"giso/beauty_centers/templates/beauty_centers/owner_dashboard.html").read_text(encoding="utf-8")
    listing = (ROOT/"giso/beauty_centers/templates/beauty_centers/list.html").read_text(encoding="utf-8")
    for source in (register, owner):
        assert 'name="price_level"' in source
        assert 'name="starting_price"' in source
        assert "قیمت نهایی نیست" in source or "اختیاری" in source
    assert 'name="price_level"' in listing


def test_pricing_migration_is_additive(tmp_path, monkeypatch):
    path=tmp_path/"legacy.db"; db=sqlite3.connect(path)
    db.executescript("""CREATE TABLE beauty_centers(id INTEGER PRIMARY KEY,status TEXT,is_active INTEGER,city TEXT,center_type TEXT,is_featured INTEGER,sort_order INTEGER,category TEXT);CREATE TABLE beauty_center_reports(id INTEGER PRIMARY KEY,center_id INTEGER,status TEXT,created_at TEXT);INSERT INTO beauty_centers VALUES(1,'published',1,'مشهد','hair_center',0,0,'hair');""")
    db.commit();db.close()
    def connect():
        conn=sqlite3.connect(path);conn.row_factory=sqlite3.Row;return conn
    monkeypatch.setattr(schema,"get_giso_db_conn",connect);schema.migrate_beauty_center_tables()
    with connect() as conn:
        cols={r[1] for r in conn.execute("PRAGMA table_info(beauty_centers)")}
        row=conn.execute("SELECT id,price_level,starting_price,price_inquiry_clicks FROM beauty_centers").fetchone()
    assert {"price_level","starting_price","price_inquiry_clicks"} <= cols
    assert tuple(row) == (1,"on_request",0,0)
