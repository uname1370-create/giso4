# -*- coding: utf-8 -*-
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]

def test_owner_dashboard_has_only_three_simple_tabs():
    html=(ROOT/'giso/beauty_centers/templates/beauty_centers/owner_dashboard.html').read_text(encoding='utf-8')
    for label in ('وضعیت مرکز','ویرایش اطلاعات','پیام‌ها'):
        assert label in html
    assert "tab='stats'" not in html
    assert "tab='promotion'" not in html
    assert 'price_inquiry_clicks' in html
    assert 'analysis_impressions' in html
    assert 'به‌زودی' in html

def test_owner_route_accepts_only_three_tabs():
    source=(ROOT/'giso/beauty_centers/routes.py').read_text(encoding='utf-8')
    assert '("status", "edit", "messages")' in source
