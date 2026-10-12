# -*- coding: utf-8 -*-
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_owner_dashboard_preserves_existing_tabs_and_adds_smart_analytics():
    html = (ROOT / "giso/beauty_centers/templates/beauty_centers/owner_dashboard.html").read_text(encoding="utf-8")
    for label in ("نمای کلی", "اطلاعات و تصاویر", "خدمات و ساعات", "پیام‌های مشتریان", "نوبت‌ها", "آمار هوشمند"):
        assert label in html
    assert "price_inquiry_clicks" in html
    assert "analysis_impressions" in html


def test_owner_route_accepts_analytics_tab_and_only_whitelisted_periods():
    source = (ROOT / "giso/beauty_centers/routes.py").read_text(encoding="utf-8")
    assert '"analytics"' in source
    assert "analytics_days not in (7, 30, 90)" in source
