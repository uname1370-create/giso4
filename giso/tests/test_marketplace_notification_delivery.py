# -*- coding: utf-8 -*-
"""Focused notification contract for Marketplace actors."""
from pathlib import Path
from unittest.mock import patch

from giso.marketplace import services


class ImmediatePool:
    def __init__(self):
        self.calls = []

    def submit(self, fn, *args):
        self.calls.append((fn, args))
        return None


def test_marketplace_user_notification_records_site_and_queues_bale():
    pool = ImmediatePool()
    with patch.object(services, "_MARKETPLACE_NOTIFY_POOL", pool), \
         patch("giso.panel.modules.notifications.log_user_notification") as log_user:
        services.notify_marketplace_user(
            "+989121111111", "offer_status", "پاسخ پیشنهاد", "پیشنهاد پذیرفته شد",
            "marketplace_offer_accepted", 77,
        )
    log_user.assert_called_once_with(
        "+989121111111", "offer_status", "پاسخ پیشنهاد", "پیشنهاد پذیرفته شد",
        source_type="marketplace_offer_accepted", source_id=77, category="marketplace",
    )
    assert len(pool.calls) == 1
    assert pool.calls[0][1] == ("+989121111111", "پاسخ پیشنهاد", "پیشنهاد پذیرفته شد")


def test_all_marketplace_actor_hooks_use_unified_user_delivery():
    source = (Path(__file__).resolve().parents[1] / "marketplace" / "services.py").read_text(encoding="utf-8")
    for start_name, end_name in (
        ("def notify_listing_created", "def notify_listing_status"),
        ("def notify_listing_status", "def notify_offer_created"),
        ("def notify_offer_created", "def notify_offer_status"),
        ("def notify_offer_status", "def notify_seller_offer_status"),
        ("def notify_seller_offer_status", "def notify_buyer_request_created"),
        ("def notify_buyer_profile_status", "def daily_offer_count"),
    ):
        block = source[source.index(start_name):source.index(end_name)]
        assert "notify_marketplace_user(" in block, start_name


def test_successful_deal_notifies_buyer_and_seller():
    source = (Path(__file__).resolve().parents[1] / "marketplace" / "routes.py").read_text(encoding="utf-8")
    sold = source[source.index("def complete_offer"):source.index("def submit_review")]
    assert 'notify_offer_status(offer, title="فروش موفق بازارچه")' in sold
    assert 'notify_seller_offer_status(offer, title="فروش موفق بازارچه")' in sold


def test_user_notification_history_is_kept_for_seven_days():
    from giso.panel.modules import notifications

    assert notifications.USER_NOTIFICATION_RETENTION_HOURS == 168


def test_shop_order_notification_actions_are_scoped_per_order():
    from giso.shop.logic.checkout import _shop_order_action_markup

    markup = _shop_order_action_markup([11, 12])
    callbacks = [button["callback_data"] for row in markup["inline_keyboard"] for button in row]
    assert "shop_ord_st|11|shipped" in callbacks
    assert "shop_ord_st|11|delivered" in callbacks
    assert "shop_ord_st|11|rejected" in callbacks
    assert "shop_ord_st|12|shipped" in callbacks
