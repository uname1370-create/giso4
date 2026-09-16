# -*- coding: utf-8 -*-
"""Stage 1 contract: only hair, skin/face and beauty services may be registered."""
import sqlite3
from pathlib import Path

from giso.beauty_centers import schema, services

ROOT = Path(__file__).resolve().parents[2]


def test_exact_three_categories_and_no_other_escape_hatch():
    assert services.CENTER_CATEGORIES == {
        "hair": "مو", "skin_face": "پوست و صورت", "beauty": "آرایش و زیبایی",
    }
    assert set(services.CATEGORY_SERVICES) == set(services.CENTER_CATEGORIES)
    assert set(services.CATEGORY_CENTER_TYPES) == set(services.CENTER_CATEGORIES)
    assert "other" not in services.CENTER_TYPES


def test_backend_rejects_cross_category_services_and_types():
    valid, error = services._normalize_fields({
        "name": "مرکز مو", "category": "hair", "center_type": "hair_center",
        "city": "مشهد", "business_phone": "09120000000", "services": ["haircut", "hair_repair"],
    })
    assert not error and valid["category"] == "hair"
    _fields, error = services._normalize_fields({
        "name": "نامرتبط", "category": "hair", "center_type": "hair_center",
        "city": "مشهد", "business_phone": "09120000000", "services": ["facial"],
    })
    assert "مرتبط نیست" in error
    _fields, error = services._normalize_fields({
        "name": "نوع نامرتبط", "category": "beauty", "center_type": "licensed_clinic",
        "city": "مشهد", "business_phone": "09120000000", "services": ["makeup"],
    })
    assert "سازگار نیست" in error


def test_forms_and_filters_are_category_aware():
    register = (ROOT / "giso/beauty_centers/templates/beauty_centers/register.html").read_text(encoding="utf-8")
    owner = (ROOT / "giso/beauty_centers/templates/beauty_centers/owner_dashboard.html").read_text(encoding="utf-8")
    listing = (ROOT / "giso/beauty_centers/templates/beauty_centers/list.html").read_text(encoding="utf-8")
    for source in (register, owner):
        assert 'name="category"' in source
        assert "category_services" in source
        assert 'data-category=' in source
    assert 'name="category"' in listing
    assert "center_categories" in listing


def test_additive_migration_preserves_legacy_center(tmp_path, monkeypatch):
    path = tmp_path / "legacy.db"
    conn = sqlite3.connect(path)
    conn.executescript("""
    CREATE TABLE beauty_centers(id INTEGER PRIMARY KEY,status TEXT,is_active INTEGER,city TEXT,
      center_type TEXT,is_featured INTEGER,sort_order INTEGER);
    CREATE TABLE beauty_center_reports(id INTEGER PRIMARY KEY,center_id INTEGER,status TEXT,created_at TEXT);
    INSERT INTO beauty_centers VALUES(1,'pending_review',1,'مشهد','hair_center',0,0);
    """)
    conn.commit(); conn.close()
    def connect():
        db = sqlite3.connect(path); db.row_factory = sqlite3.Row; return db
    monkeypatch.setattr(schema, "get_giso_db_conn", connect)
    schema.migrate_beauty_center_tables()
    with connect() as db:
        columns = {row[1] for row in db.execute("PRAGMA table_info(beauty_centers)")}
        row = db.execute("SELECT id,category FROM beauty_centers WHERE id=1").fetchone()
    assert "category" in columns
    assert (row["id"], row["category"]) == (1, "hair")
