# -*- coding: utf-8 -*-
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]

def test_detail_displays_non_guaranteed_cost_and_inquiry_action():
    html=(ROOT/'giso/beauty_centers/templates/beauty_centers/detail.html').read_text(encoding='utf-8')
    for marker in ('price_level_label','starting_price','قیمت نهایی نیست','intent','price_inquiry','گفتگوی آنلاین با مرکز','{{ disclaimer }}'):
        assert marker in html

def test_contact_service_tracks_price_inquiry_separately():
    source=(ROOT/'giso/beauty_centers/services.py').read_text(encoding='utf-8')
    assert 'price_inquiry: bool = False' in source
    assert 'price_inquiry_clicks=price_inquiry_clicks+1' in source

def test_detail_cost_is_responsive_scoped_component():
    css=(ROOT/'giso/beauty_centers/static/beauty_centers.css').read_text(encoding='utf-8')
    assert '.bc-detail-cost{' in css
