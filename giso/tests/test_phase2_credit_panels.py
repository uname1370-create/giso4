# -*- coding: utf-8 -*-
"""Phase 2: isolated credit settings and role-facing tabs."""
from pathlib import Path
from giso.app import create_app
from giso.marketplace.settings import marketplace_settings, save_marketplace_settings

ROOT=Path(__file__).resolve().parents[2]


def test_credit_save_does_not_disable_marketplace_or_chat():
    create_app()
    before=marketplace_settings()
    ok,_=save_marketplace_settings({
        "seller_features_enabled":False,"buyer_features_enabled":True,
        "buyer_alert_3_price":31000,"buyer_alert_7_price":71000,"buyer_alert_30_price":301000,
        "buyer_bonus_price":41000,"promo_bump_price":21000,"promo_urgent_price":81000,"promo_featured_price":201000,
    })
    assert ok
    after=marketplace_settings()
    assert after["enabled"]==before["enabled"] and after["chat_enabled"]==before["chat_enabled"]
    assert after["buyer_alert_3_price"]==31000 and after["seller_features_enabled"] is False
    # restore feature switch for other tests
    save_marketplace_settings({"seller_features_enabled":True,"buyer_features_enabled":True})


def test_credit_tabs_and_three_day_bundle_are_server_rendered():
    user=(ROOT/'giso/panel_user/templates/user_modules/marketplace.html').read_text(encoding='utf-8')
    admin=(ROOT/'giso/panel/templates/modules/marketplace.html').read_text(encoding='utf-8')
    assert "ارتقای آگهی" in user and "marketplace.seller_promote_selected" in user
    assert "۳ روز" in user and "افزایش سهمیه پیشنهاد" in user
    assert "tab='credits'" in admin and "seller_features_enabled" in admin and "buyer_features_enabled" in admin
    assert "buyer_alert_3_price" in admin
