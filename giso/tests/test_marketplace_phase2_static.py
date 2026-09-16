#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Dependency-free regression checks for the Marketplace core and Phase 4 UI."""
import importlib.util
import sqlite3
import tempfile
from pathlib import Path
import unittest


GISO = Path(__file__).resolve().parents[1]
ROOT = GISO.parent


class MarketplacePhase2StaticTests(unittest.TestCase):
    def text(self, relative):
        return (ROOT / relative).read_text(encoding="utf-8")

    def test_required_models_are_independent(self):
        models = self.text("giso/models.py")
        for name, table in (
            ("HairListing", "hair_listings"), ("BuyerProfile", "buyer_profiles"),
            ("BuyerOffer", "buyer_offers"), ("MarketplaceMessage", "marketplace_messages"),
            ("ListingReport", "listing_reports"), ("MarketplaceDevice", "marketplace_devices"),
            ("MarketplacePhoneObservation", "marketplace_phone_observations"),
            ("MarketplaceListingDeviceClaim", "marketplace_listing_device_claims"),
            ("MarketplaceRiskEvent", "marketplace_risk_events"),
        ):
            self.assertIn(f"class {name}(db.Model):", models)
            self.assertIn(f"__tablename__ = '{table}'", models)
        hair_order = models[models.index("class HairOrder"):models.index("class HairListing")]
        self.assertNotIn("seller_asking_price", hair_order)
        self.assertNotIn("marketplace", hair_order.lower())

    def test_hair_sale_branches_without_turning_listing_into_order(self):
        source = self.text("giso/hair_sale.py")
        block = source[source.index("def _finalize_selected_path"):source.index("def _hair_sale_duplicate_guard")]
        self.assertIn('selected_path == "marketplace"', block)
        self.assertIn("create_marketplace_listing", block)
        self.assertIn('selected_path == "both"', block)
        self.assertIn("linked_listing=listing", block)
        marketplace_branch = block[block.index('selected_path == "marketplace"'):block.index('selected_path == "both"')]
        self.assertNotIn("_finalize_hair_order", marketplace_branch)

    def test_public_and_authenticated_routes_exist(self):
        source = self.text("giso/marketplace/routes.py")
        for route in (
            '/marketplace")', '/hair-marketplace")', '/marketplace/<int:listing_id>")',
            '/marketplace/<int:listing_id>/offer", methods=["POST"]',
            '/marketplace/offers/<int:offer_id>/chat", methods=["GET", "POST"]',
            '/marketplace/seller/listings/<int:listing_id>/status", methods=["POST"]',
        ):
            self.assertIn(route, source)
        chat_block = source[source.index("def offer_chat"): ]
        self.assertIn("is_offer_party(offer, current_user.id)", chat_block)
        self.assertIn('offer.status not in ("pending", "countered", "accepted", "sold")', chat_block)
        self.assertIn("chat_read_only", chat_block)
        self.assertIn("chat_read_only_reason", chat_block)

    def test_schema_is_idempotent_and_enforces_one_active_offer(self):
        schema_path = GISO / "marketplace" / "schema.py"
        spec = importlib.util.spec_from_file_location("giso_market_schema_test", schema_path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "market.db"
            conn = sqlite3.connect(db_path)
            conn.executescript("CREATE TABLE giso_web_auth(id INTEGER PRIMARY KEY); CREATE TABLE hair_orders(id INTEGER PRIMARY KEY);")
            conn.close()
            self.assertTrue(module.migrate_marketplace_tables(str(db_path)))
            self.assertTrue(module.migrate_marketplace_tables(str(db_path)))
            conn = sqlite3.connect(db_path)
            tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            self.assertTrue({
                "hair_listings", "buyer_profiles", "buyer_offers", "marketplace_messages",
                "listing_reports", "marketplace_phone_observations",
                "marketplace_listing_device_claims", "marketplace_risk_events",
            } <= tables)
            buyer_columns = {row[1] for row in conn.execute("PRAGMA table_info(buyer_profiles)")}
            self.assertTrue({"terms_version", "terms_accepted_at"} <= buyer_columns)
            conn.execute("INSERT INTO giso_web_auth(id) VALUES (1)")
            conn.execute("INSERT INTO giso_web_auth(id) VALUES (2)")
            conn.execute("INSERT INTO hair_listings(id,seller_user_id,photo_path,length_cm) VALUES (1,1,'x.jpg',50)")
            conn.execute("INSERT INTO buyer_profiles(id,user_id) VALUES (1,1)")
            conn.execute("INSERT INTO buyer_offers(listing_id,buyer_user_id,buyer_profile_id,offer_amount,status) VALUES (1,1,1,100,'pending')")
            with self.assertRaises(sqlite3.IntegrityError):
                conn.execute("INSERT INTO buyer_offers(listing_id,buyer_user_id,buyer_profile_id,offer_amount,status) VALUES (1,1,1,200,'countered')")
            conn.execute("UPDATE buyer_offers SET status='rejected' WHERE listing_id=1 AND buyer_user_id=1")
            conn.execute("INSERT INTO buyer_offers(listing_id,buyer_user_id,buyer_profile_id,offer_amount,status) VALUES (1,1,1,200,'pending')")
            active_count = conn.execute("SELECT COUNT(*) FROM buyer_offers WHERE listing_id=1 AND buyer_user_id=1 AND status IN ('pending','countered','accepted')").fetchone()[0]
            self.assertEqual(active_count, 1)

            conn.execute("INSERT INTO marketplace_devices(id,device_key_hash) VALUES (1,'device-one')")
            conn.execute("INSERT INTO marketplace_listing_device_claims(listing_id,device_id,buyer_user_id) VALUES (1,1,1)")
            with self.assertRaises(sqlite3.IntegrityError):
                conn.execute("INSERT INTO marketplace_listing_device_claims(listing_id,device_id,buyer_user_id) VALUES (1,1,2)")
            conn.execute("INSERT INTO marketplace_phone_observations(device_id,user_id,phone_snapshot) VALUES (1,1,'09120000001')")
            conn.execute("INSERT INTO marketplace_phone_observations(device_id,user_id,phone_snapshot) VALUES (1,1,'09120000002')")
            phone_count = conn.execute("SELECT COUNT(*) FROM marketplace_phone_observations WHERE device_id=1").fetchone()[0]
            self.assertEqual(phone_count, 2)
            conn.execute("INSERT INTO marketplace_risk_events(event_type,status,listing_id,user_id,device_id,reason,offer_amount) VALUES ('offer_blocked','blocked',1,2,1,'device_claimed_by_other_user',300)")
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM marketplace_risk_events").fetchone()[0], 1)
            conn.close()

    def test_panels_remain_single_modules_with_required_tabs(self):
        user = self.text("giso/panel_user/templates/user_modules/marketplace.html")
        admin = self.text("giso/panel/templates/modules/marketplace.html")
        for label in ("آگهی‌های من", "پیشنهادهای من", "گفتگوهای من", "معاملات موفق من", "اعتبار من"):
            self.assertIn(label, user)
        for label in ("داشبورد بازارچه", "آگهی‌ها", "پروفایل خریداران", "امتیازها", "تنظیمات بازارچه"):
            self.assertIn(label, admin)
        self.assertIn("marketTrendChart", admin)
        self.assertNotIn("Device Risk", admin)
        self.assertNotIn("تلاش‌های Block", admin)

    def test_device_storage_is_hashed_and_cookie_based(self):
        source = self.text("giso/marketplace/device.py")
        models = self.text("giso/models.py")
        self.assertIn('COOKIE_NAME = "giso_device_id"', source)
        self.assertIn("hmac.new", source)
        self.assertIn("httponly=True", source)
        self.assertIn("samesite=\"Lax\"", source)
        self.assertIn("device_key_hash", models)
        self.assertIn("last_ip_hash", models)
        self.assertNotIn("raw_ip", models)

    def test_public_templates_do_not_render_private_identity_fields(self):
        public = self.text("giso/templates/marketplace_list.html") + self.text("giso/templates/marketplace_detail.html")
        for private_expression in ("seller.phone", "seller.name", "buyer.phone", "buyer.name"):
            self.assertNotIn(private_expression, public)
        detail = self.text("giso/templates/marketplace_detail.html")
        hair_sale = self.text("giso/templates/hair_sale.html")
        buyer_form = self.text("giso/panel_user/templates/user_modules/_buyer_request_form.html")
        routes = self.text("giso/marketplace/routes.py")
        self.assertIn("هویت کاربران و مبلغ نهایی معامله عمومی نمی", detail)
        self.assertIn("marketplace_terms_accepted", hair_sale)
        self.assertIn('name="buyer_terms"', buyer_form)
        hair_backend = self.text("giso/hair_sale.py")
        self.assertIn("profile.terms_accepted_at", hair_backend)

    def test_offer_state_notifications_and_highest_semantics(self):
        routes = self.text("giso/marketplace/routes.py")
        services = self.text("giso/marketplace/services.py")
        user_ui = self.text("giso/panel_user/templates/user_modules/marketplace.html")
        seller_block = routes[routes.index("def seller_respond_offer"):routes.index("def buyer_respond_counter")]
        self.assertIn('offer.status != "pending"', seller_block)
        self.assertGreaterEqual(routes.count("notify_seller_offer_status"), 3)
        self.assertNotIn("notify_buyer_activation(profile)", routes)
        admin_module = self.text("giso/panel/modules/marketplace.py")
        self.assertIn("notify_buyer_profile_status(profile)", admin_module)
        notifications = (self.text("giso/panel/modules/notifications/helpers.py")
                      + self.text("giso/panel/modules/notifications/core.py"))
        self.assertIn('"marketplace": {"target_role": "both"', notifications)
        self.assertIn("قیمت متقابل", user_ui)
        self.assertIn("بستن آگهی", user_ui)
        self.assertIn("فروش موفق", user_ui)
        stats = services[services.index("def refresh_listing_offer_stats"):services.index("def notify_listing_created")]
        self.assertIn("OFFER_ACTIVE_STATUSES", stats)
        self.assertIn("row.offer_amount", stats)
        self.assertNotIn("seller_counter_amount", stats)


if __name__ == "__main__":
    unittest.main()
