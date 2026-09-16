# -*- coding: utf-8 -*-
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]

def test_owner_tabs_are_consistent_and_message_aware():
    html=(ROOT/'giso/beauty_centers/templates/beauty_centers/owner_dashboard.html').read_text(encoding='utf-8')
    for label in ('نمای کلی','اطلاعات و تصاویر','پیام‌های مشتریان','افزایش دیده‌شدن آگهی'):
        assert label in html
    assert 'beauty_unread' in html
    css=(ROOT/'giso/beauty_centers/static/beauty_centers.css').read_text(encoding='utf-8')
    assert 'grid-template-columns:repeat(4' in css and '@media(max-width:780px)' in css

def test_owner_unread_uses_count_query_not_full_conversation_list():
    source=(ROOT/'giso/beauty_centers/services.py').read_text(encoding='utf-8')
    block=source[source.index('def owner_conversation_unread_count'):source.index('def owner_conversations')]
    assert 'SELECT COUNT(*)' in block
