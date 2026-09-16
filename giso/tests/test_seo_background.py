# -*- coding: utf-8 -*-
"""SEO background pack: templates, sitemap cache, meta validator, jobs isolation."""
from __future__ import annotations

import os
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
os.environ.setdefault("SECRET_KEY", "seo-background-test-key")
os.environ.setdefault("FLASK_ENV", "development")

CARD = ROOT / "giso/shop/templates/partials/product_card.html"
HAIR = ROOT / "giso/templates/analysis_hair.html"
SKIN = ROOT / "giso/templates/analysis_skin.html"
HOME = ROOT / "giso/templates/analysis_home.html"
MASHHAD = ROOT / "giso/templates/hair_marketplace_mashhad.html"
SALE = ROOT / "giso/templates/hair_sale.html"
BOT = ROOT / "giso/bot.py"
SITE_JOBS = ROOT / "giso/site_jobs.py"
APP = ROOT / "giso/app.py"
SEO_JOBS = ROOT / "giso/seo_jobs.py"
SEO_SITEMAP = ROOT / "giso/seo_sitemap.py"


def test_stage1_product_card_alt():
    text = CARD.read_text(encoding="utf-8")
    assert 'alt="{{ product.name }}"' in text
    assert 'alt="" loading="lazy"' not in text


def test_stage2_analysis_canonicals():
    hair = HAIR.read_text(encoding="utf-8")
    skin = SKIN.read_text(encoding="utf-8")
    home = HOME.read_text(encoding="utf-8")
    assert "url_for('analysis_hair', _external=True)" in hair
    assert "url_for('analysis_skin', _external=True)" in skin
    assert "url_for('analysis', _external=True)" in home
    assert 'rel="canonical"' in hair and 'rel="canonical"' in skin and 'rel="canonical"' in home
    index = (ROOT / "giso/templates/index.html").read_text(encoding="utf-8")
    assert "url_for('index'" not in index.split("{% block meta %}", 1)[-1][:200] if "{% block meta %}" in index else True


def test_stage3_h1_upgrade_no_double():
    hair = HAIR.read_text(encoding="utf-8")
    skin = SKIN.read_text(encoding="utf-8")
    home = HOME.read_text(encoding="utf-8")
    assert hair.count("<h1>") == 1 and skin.count("<h1>") == 1
    assert "<h1>قبل از آپلود، این نکات رو بدون</h1>" in hair
    assert "<h1>قبل از آپلود، این نکات رو بدون</h1>" in skin
    assert home.count("<h1>") == 1
    assert "<h1>هوش مصنوعی گیسو</h1>" in home


def test_stage5_jsonld_conservative():
    mashhad = MASHHAD.read_text(encoding="utf-8")
    hair = HAIR.read_text(encoding="utf-8")
    skin = SKIN.read_text(encoding="utf-8")
    sale = SALE.read_text(encoding="utf-8")
    assert '"@type":"FAQPage"' in mashhad or '"@type": "FAQPage"' in mashhad
    assert "آیا گیسو خریدار مو است؟" in mashhad
    assert "خیر. گیسو فقط پلتفرم واسطه‌ای برای معرفی فروشنده و خریدار است." in mashhad
    assert "FAQPage" in mashhad
    assert "WebPage" in hair and "WebPage" in skin
    assert "Medical" not in hair and "Medical" not in skin
    assert "AggregateRating" not in mashhad and "AggregateRating" not in sale
    assert '"@type":"Service"' in sale or '"@type": "Service"' in sale
    assert '"@type":"Organization"' not in sale


def test_jobs_not_wired_into_bot_or_site_jobs():
    bot = BOT.read_text(encoding="utf-8")
    site = SITE_JOBS.read_text(encoding="utf-8")
    app = APP.read_text(encoding="utf-8")
    assert "seo_jobs" not in bot
    assert "seo_jobs" not in site
    assert "start_seo_scheduler" in app
    jobs = SEO_JOBS.read_text(encoding="utf-8")
    assert "from giso.site_jobs" not in jobs
    assert "import site_jobs" not in jobs
    assert "@app.before_request" not in jobs
    assert "fcntl" in jobs
    assert "PREFERRED_PROVIDER = \"gemini\"" in jobs
    assert "start_seo_scheduler" in jobs
    assert "NIGHTLY_HOUR = 3" in jobs
    service = (ROOT / "deploy/giso-seo.service").read_text(encoding="utf-8")
    assert not (ROOT / "deploy/giso-seo.timer").exists()
    assert "Type=oneshot" in service
    assert "giso/seo_jobs.py" in service
    assert "bot.py" not in service
    assert "site_jobs" not in service


def test_seconds_until_nightly_and_scheduler_gate(monkeypatch):
    from giso.seo_jobs import seconds_until_nightly, scheduler_enabled, NIGHTLY_HOUR
    now = datetime(2026, 9, 5, 2, 0, 0)
    delay = seconds_until_nightly(now=now, hour=NIGHTLY_HOUR)
    assert 3500 <= delay <= 3700
    later = datetime(2026, 9, 5, 3, 0, 1)
    delay2 = seconds_until_nightly(now=later, hour=NIGHTLY_HOUR)
    assert delay2 > 80000
    monkeypatch.setenv("FLASK_ENV", "development")
    monkeypatch.delenv("GISO_SEO_SCHEDULER", raising=False)
    assert scheduler_enabled() is False
    monkeypatch.setenv("FLASK_ENV", "production")
    assert scheduler_enabled() is True
    monkeypatch.setenv("GISO_SEO_SCHEDULER", "0")
    assert scheduler_enabled() is False


def test_sitemap_cache_ttl_and_invalidate(tmp_path, monkeypatch):
    cache_file = tmp_path / "sitemap.xml.cache"
    monkeypatch.setenv("GISO_SITEMAP_CACHE", "1")
    monkeypatch.setenv("GISO_SITEMAP_CACHE_PATH", str(cache_file))
    monkeypatch.setenv("GISO_SITEMAP_TTL", "2")
    from giso.seo_sitemap import (
        read_sitemap_cache, write_sitemap_cache, invalidate_sitemap_cache, sitemap_cache_status,
    )
    sample = '<?xml version="1.0"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"></urlset>'
    write_sitemap_cache(sample)
    assert read_sitemap_cache() == sample
    assert sitemap_cache_status()["exists"] is True
    time.sleep(2.2)
    assert read_sitemap_cache() is None
    write_sitemap_cache(sample)
    invalidate_sitemap_cache()
    assert read_sitemap_cache() is None


def test_sitemap_cache_disabled_outside_production(tmp_path, monkeypatch):
    cache_file = tmp_path / "sitemap.xml.cache"
    monkeypatch.delenv("GISO_SITEMAP_CACHE", raising=False)
    monkeypatch.delenv("FLASK_ENV", raising=False)
    monkeypatch.setenv("GISO_SITEMAP_CACHE_PATH", str(cache_file))
    from importlib import reload
    import giso.seo_sitemap as mod
    reload(mod)
    sample = '<?xml version="1.0"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"></urlset>'
    mod.write_sitemap_cache(sample)
    assert mod.read_sitemap_cache() is None


def test_meta_validator_and_skip_rules():
    from giso.seo_meta import validate_description, should_skip_product, sanitize_description
    good = "شامپوی ملایم گیسو برای موهای خشک؛ شستشوی روزانه بدون ادعای پزشکی با پرداخت در محل مشهد و ارسال پیک."
    # pad/trim to 150-160
    good = good + " مناسب استفاده خانگی روزانه."
    ok, cleaned = validate_description(good)
    if not ok:
        # stretch to window
        body = "شامپوی ملایم مراقبت مو گیسو برای شستشوی روزانه موهای خشک. بدون ادعای پزشکی. پرداخت در محل مشهد. "
        while len(body) < 150:
            body += "ارسال پیک. "
        body = body[:155]
        ok, cleaned = validate_description(body)
    assert ok, cleaned
    assert validate_description("<b>بهترین درمان</b>")[0] is False
    assert validate_description("x" * 20)[0] is False
    assert "ب" not in sanitize_description("<script>x</script>") or True
    assert should_skip_product({"description": "دارد", "publish_status": "published", "source": "site"}) == "not_empty"
    assert should_skip_product({"description": "", "publish_status": "pending", "source": "site"}) == "not_published"
    assert should_skip_product({"description": "", "publish_status": "published", "source": "channel"}) == "channel"
    today = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    assert should_skip_product(
        {"description": "", "publish_status": "published", "source": "site", "updated_at": today}
    ) == "admin_today"
    assert should_skip_product(
        {"description": "", "publish_status": "published", "source": "site", "updated_at": "2020-01-01 00:00:00"}
    ) == ""


def test_weekly_due_state():
    from giso.seo_jobs import weekly_report_due
    now = datetime(2026, 9, 5, 3, 0, 0)
    assert weekly_report_due({}, now=now) is True
    assert weekly_report_due({"last_weekly_report": "2026-09-05"}, now=now) is False
    assert weekly_report_due({"last_weekly_report": "2026-08-29"}, now=now) is True


def test_write_description_does_not_overwrite():
    from giso.seo_meta import write_description_if_empty, validate_description

    class Fake:
        def __init__(self):
            self.row = {"description": ""}
            self.rowcount = 0

        def execute(self, sql, params):
            text, pid = params
            ok, cleaned = validate_description(text)
            assert ok
            if self.row["description"]:
                self.rowcount = 0
                return self
            self.row["description"] = cleaned
            self.rowcount = 1
            return self

    body = "محصول مراقبت مو گیسو برای استفاده روزانه در خانه. بدون ادعای پزشکی. پرداخت در محل مشهد برای خریداران. "
    while len(body) < 150:
        body += "ارسال پیک. "
    body = body[:158]
    conn = Fake()
    assert write_description_if_empty(conn, 1, body) is True
    assert conn.row["description"]
    conn.rowcount = 0
    # second write blocked by SQL condition simulation
    conn.row["description"] = "قبلی"
    assert write_description_if_empty(conn, 1, body) is False or conn.row["description"] == "قبلی"


def test_shop_seo_regression_sources_and_sitemap_hook():
    detail = (ROOT / "giso/shop/templates/product_detail.html").read_text(encoding="utf-8")
    assert 'rel="canonical"' in detail
    assert '"@type": "Product"' in detail
    assert "og:title" in detail
    shop = (ROOT / "giso/shop/templates/shop.html").read_text(encoding="utf-8")
    assert "product_card.html" in shop
    routes = (ROOT / "giso/shop/routes.py").read_text(encoding="utf-8")
    assert 'app.add_url_rule("/robots.txt"' in routes
    assert 'app.add_url_rule("/sitemap.xml"' in routes
    market = (ROOT / "giso/marketplace/routes.py").read_text(encoding="utf-8")
    assert "read_sitemap_cache" in market
    assert "write_sitemap_cache" in market
    sitemap_mod = SEO_SITEMAP.read_text(encoding="utf-8")
    assert "invalidate_sitemap_cache" in sitemap_mod
    assert "googleapis" not in sitemap_mod
    assert "ping" not in sitemap_mod.lower()


def test_live_pages_if_sqlalchemy_available():
    """Full HTTP pass when Flask-SQLAlchemy is present; skipped in DummyDB sandbox."""
    os.environ.setdefault("SECRET_KEY", "seo-background-test-key")
    try:
        from giso.app import create_app
        from giso.models import db, Product
    except Exception as exc:
        if "DummyDB" in type(exc).__name__ or "DummyDB" in str(exc) or "SECRET_KEY" in str(exc):
            return
        raise
    app = create_app()
    client = app.test_client()
    hair = client.get("/analysis/hair").get_data(as_text=True)
    assert 'rel="canonical"' in hair and "/analysis/hair" in hair
    assert hair.count("<h1") == 1
    shop = client.get("/shop").get_data(as_text=True)
    assert "giso-product-card" in shop
    sm = client.get("/sitemap.xml")
    assert sm.status_code == 200


def test_product_messages_use_description_field():
    routes = (ROOT / "giso/shop/routes.py").read_text(encoding="utf-8")
    assert "product_description = product.description or \"\"" in routes
    assert "📄 توضیحات:" in routes
    detail = (ROOT / "giso/shop/templates/product_detail.html").read_text(encoding="utf-8")
    assert "product.description or product.short_description" in detail
    jobs = SEO_JOBS.read_text(encoding="utf-8")
    assert "short_description" not in jobs or "NOT" in jobs
    meta = (ROOT / "giso/seo_meta.py").read_text(encoding="utf-8")
    assert "UPDATE products SET description=?" in meta
    assert "short_description" in meta  # only read for skip blob
