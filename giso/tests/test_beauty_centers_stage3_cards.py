# -*- coding: utf-8 -*-
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]

def test_public_card_shows_category_cost_and_starting_price_disclaimer():
    card=(ROOT/'giso/beauty_centers/templates/beauty_centers/_card.html').read_text(encoding='utf-8')
    for marker in ('category_label','price_level_label','starting_price','شروع خدمات از','اطلاعات هزینه توسط مرکز اعلام شده است','مشاهده مرکز'):
        assert marker in card

def test_card_pricing_has_scoped_visual_style():
    css=(ROOT/'giso/beauty_centers/static/beauty_centers.css').read_text(encoding='utf-8')
    assert '.bc-cost{' in css
    assert '.bc-cost strong' in css
