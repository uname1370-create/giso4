# -*- coding: utf-8 -*-
"""Stage 13: indexable and no-JavaScript Beauty Centers homepage card."""
from pathlib import Path

from giso.app import create_app

ROOT = Path(__file__).resolve().parents[2]


def _card_markup(page: str) -> str:
    start = page.index('data-testid="beauty-centers-home-card"')
    end = page.index("</div>", start)
    # The first closing div is the icon; keep enough markup through the card CTA.
    return page[start:page.index("</a>", end) + 4]


def test_homepage_card_is_server_rendered_with_real_direct_link():
    app = create_app()
    with app.test_client() as client:
        response = client.get("/")
    assert response.status_code == 200
    page = response.get_data(as_text=True)
    card = _card_markup(page)
    assert "مراکز زیبایی گیسو" in card
    assert "براساس شهر و خدمات" in card
    assert 'href="/beauty-centers"' in card
    assert "مشاهده مراکز" in card


def test_card_contains_intermediary_disclosure_without_javascript():
    source = (ROOT / "giso/templates/index.html").read_text(encoding="utf-8")
    card = _card_markup(source)
    assert "گیسو فقط بستر معرفی است" in card
    assert "قیمت، پرداخت و ارائه خدمت خارج از گیسو انجام می‌شود" in card
    assert "url_for('beauty_centers.list_centers')" in card
    assert "بهترین مرکز" not in card


def test_interactive_detail_repeats_disclosure_and_has_no_fake_statistics():
    source = (ROOT / "giso/templates/index.html").read_text(encoding="utf-8")
    start = source.index("centers: {")
    end = source.index("\n    }", start)
    detail = source[start:end]
    assert "گیسو فقط بستر معرفی است" in detail
    assert "در قیمت، پرداخت یا نتیجه خدمت نقشی ندارد" in detail
    assert "معرفی مرتبط پس از آنالیز" in detail
    assert "بهترین" not in detail
    assert "تضمین" not in detail
