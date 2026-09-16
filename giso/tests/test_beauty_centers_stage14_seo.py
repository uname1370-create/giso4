# -*- coding: utf-8 -*-
"""Stage 14: final indexability, metadata and sitemap contract."""
from pathlib import Path

from giso.app import create_app
from giso.beauty_centers import services

ROOT = Path(__file__).resolve().parents[2]


def test_directory_has_complete_server_rendered_metadata():
    app = create_app()
    with app.test_client() as client:
        response = client.get("/beauty-centers?city=تهران")
    assert response.status_code == 200
    page = response.get_data(as_text=True)
    assert '<meta name="robots" content="index, follow">' in page
    assert '<link rel="canonical" href="http://localhost/beauty-centers">' in page
    assert '<meta property="og:url" content="http://localhost/beauty-centers">' in page
    assert '<meta name="twitter:card" content="summary">' in page
    assert '"@type":"ItemList"' in page


def test_sitemap_uses_module_indexability_query_without_old_hundred_item_cap(monkeypatch):
    rows = [{
        "slug": f"مرکز-{index}", "updated_at": "2026-08-24 10:00:00", "published_at": "",
    } for index in range(101)]
    monkeypatch.setattr(services, "sitemap_centers", lambda: rows)
    app = create_app()
    with app.test_client() as client:
        response = client.get("/sitemap.xml")
    xml = response.get_data(as_text=True)
    assert response.status_code == 200
    assert response.mimetype == "application/xml"
    assert xml.count("<url><loc>") >= 106  # five static URLs plus all 101 centers
    assert xml.count("<changefreq>weekly</changefreq><priority>0.7</priority>") >= 101
    assert "<lastmod>2026-08-24</lastmod>" in xml
    assert "%D9%85%D8%B1%DA%A9%D8%B2-100" in xml


def test_sitemap_query_and_detail_schema_only_allow_public_active_centers():
    service = (ROOT / "giso/beauty_centers/services.py").read_text(encoding="utf-8")
    detail = (ROOT / "giso/beauty_centers/templates/beauty_centers/detail.html").read_text(encoding="utf-8")
    sitemap = (ROOT / "giso/shop/routes.py").read_text(encoding="utf-8")
    assert "WHERE status='published' AND is_active=1 AND slug<>''" in service
    assert "from giso.beauty_centers.services import sitemap_centers" in sitemap
    assert "list_public_centers(limit=100)" not in sitemap
    assert "{% if center.status=='published' and center.is_active %}" in detail
    assert '"@type":"LocalBusiness"' in detail
    assert '"@type":"BreadcrumbList"' in detail
    assert "request.url|tojson" not in detail
    assert "aggregateRating" not in detail and "priceRange" not in detail


def test_robots_exposes_public_directory_but_blocks_private_center_panel():
    app = create_app()
    with app.test_client() as client:
        robots = client.get("/robots.txt").get_data(as_text=True)
    assert "Allow: /beauty-centers" in robots
    assert "Disallow: /dashboard/" in robots
    assert "Sitemap: http://localhost/sitemap.xml" in robots
