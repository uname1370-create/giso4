# -*- coding: utf-8 -*-
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]

def test_center_detail_has_single_disclosure_and_online_chat_cta():
    html=(ROOT/'giso/beauty_centers/templates/beauty_centers/detail.html').read_text(encoding='utf-8')
    assert 'گفتگوی آنلاین با مرکز' in html
    assert html.count('{{ disclaimer }}')==1
    assert 'LocalBusiness' in html and 'BreadcrumbList' in html
    assert 'bc-service-grid' in html and 'نمایش شماره تماس' in html

def test_public_nav_uses_one_glass_shell_and_mobile_keeps_cards():
    # §17→بازگشت به CSS اصلی: assertions مستقل از فاصله (با هر دو فرمت اصلی/فشرده پاس می‌شود)
    import re as _re
    css=_re.sub(r"\s+","",(ROOT/'giso/static/css/theme_experiences.css').read_text(encoding='utf-8'))
    responsive=_re.sub(r"\s+","",(ROOT/'giso/static/css/responsive_guardrails.css').read_text(encoding='utf-8'))
    assert '.giso-navbar{' in css and 'backdrop-filter:blur(16px)' in css
    assert '.giso-nav-links>a' in responsive and 'min-height:48px' in responsive
