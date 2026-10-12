# -*- coding: utf-8 -*-
"""Stage 2: additive, moderated and service-aware center gallery."""
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_gallery_limit_and_metadata_validation():
    from giso.beauty_centers.services import (
        CENTER_GALLERY_MAX_IMAGES, normalize_gallery_metadata,
    )

    assert 6 <= CENTER_GALLERY_MAX_IMAGES <= 12
    assert CENTER_GALLERY_MAX_IMAGES == 12
    metadata = normalize_gallery_metadata(
        "eyebrow", "  ابروی طبیعی  ", " نمونه‌کار سالن ", {"brow", "hair_color"},
    )
    assert metadata == {"service_key": "brow", "alt_text": "ابروی طبیعی", "caption": "نمونه‌کار سالن"}
    try:
        normalize_gallery_metadata("nail", "متن", "", {"brow"})
    except ValueError as exc:
        assert "خدمات فعال همین مرکز" in str(exc)
    else:
        raise AssertionError("a non-owned service key must not be accepted")
    try:
        normalize_gallery_metadata("", "", "", {"brow"})
    except ValueError as exc:
        assert "متن جایگزین" in str(exc)
    else:
        raise AssertionError("alt text is required")


def test_gallery_schema_migration_is_additive_idempotent_and_keeps_old_images(monkeypatch):
    from giso.beauty_centers import schema
    import giso.beauty_centers.pricing.schema as pricing_schema

    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute(
        "CREATE TABLE beauty_center_images (id INTEGER PRIMARY KEY, center_id INTEGER NOT NULL, "
        "image_path TEXT NOT NULL, sort_order INTEGER NOT NULL DEFAULT 0, created_at TEXT DEFAULT '')"
    )
    conn.execute(
        "INSERT INTO beauty_center_images(id,center_id,image_path,sort_order,created_at) "
        "VALUES (1,7,'beauty_centers/old.jpg',1,'2026-01-01')"
    )
    conn.commit()
    monkeypatch.setattr(schema, "get_giso_db_conn", lambda: conn)
    monkeypatch.setattr(pricing_schema, "migrate_pricing_tables", lambda: None)

    schema.migrate_beauty_center_tables()
    schema.migrate_beauty_center_tables()
    columns = {row[1] for row in conn.execute("PRAGMA table_info(beauty_center_images)")}
    assert {"service_key", "alt_text", "caption", "status", "moderated_by", "moderated_at"} <= columns
    row = conn.execute("SELECT * FROM beauty_center_images WHERE id=1").fetchone()
    assert row["image_path"] == "beauty_centers/old.jpg"
    assert row["status"] == "visible"  # old approved gallery remains public-compatible
    assert row["service_key"] == ""
    conn.close()


def test_gallery_is_moderated_and_not_shared_as_before_after():
    owner_template = (ROOT / "giso/beauty_centers/templates/beauty_centers/owner_dashboard.html").read_text(encoding="utf-8")
    public_template = (ROOT / "giso/beauty_centers/templates/beauty_centers/detail.html").read_text(encoding="utf-8")
    routes = (ROOT / "giso/beauty_centers/routes.py").read_text(encoding="utf-8")
    panel_routes = (ROOT / "giso/panel/routes.py").read_text(encoding="utf-8")
    admin_template = (ROOT / "giso/beauty_centers/templates/beauty_centers/admin.html").read_text(encoding="utf-8")

    assert "حداکثر ۱۲ تصویر" in owner_template
    assert "name=\"alt_text\"" in owner_template
    assert "name=\"caption\"" in owner_template
    assert "status) \"" in routes and "'pending'" in routes
    assert "AND (?=1 OR status='visible')" in routes
    assert "image_status" in routes and "no-store" in routes
    assert "قبل/بعد فعلاً پشتیبانی نمی‌شود" in owner_template
    assert "نمایش قبل/بعد تا زمان پیاده‌سازی رضایت جداگانه فعال نیست" in routes
    assert "پس از بررسی مدیر" in public_template
    assert "beauty_center_gallery_status" in panel_routes
    assert "تأیید و انتشار" in admin_template
    assert "رد" in admin_template
    assert "تصویر آینهٔ هوش مصنوعی" in admin_template


def test_gallery_templates_compile_as_jinja():
    from jinja2 import Environment

    env = Environment(autoescape=True)
    for relative in (
        "giso/beauty_centers/templates/beauty_centers/owner_dashboard.html",
        "giso/beauty_centers/templates/beauty_centers/detail.html",
        "giso/beauty_centers/templates/beauty_centers/admin.html",
    ):
        env.from_string((ROOT / relative).read_text(encoding="utf-8"))
