# -*- coding: utf-8 -*-
"""
مدل‌های دیتابیس گیسو
- giso.db (پیش‌فرض): جدول‌های بومی گیسو + giso_web_auth (احراز هویت سایت گیسو)
- bot.db (bind='bot'): giso_config و giso_admins (توسط bot_edu مدیریت می‌شود)
"""
import os
import sqlite3
import logging
from pathlib import Path
from datetime import datetime

logger = logging.getLogger("giso_models")

try:
    from flask_sqlalchemy import SQLAlchemy
    from flask_login import UserMixin
    db = SQLAlchemy()
except ImportError:
    class DummyDB:
        def __init__(self):
            self.Model = object
            self.Column = lambda *a, **kw: None
            self.Integer = None
            self.String = lambda *a, **kw: None
            self.Text = None
            self.Boolean = None
            self.ForeignKey = lambda *a, **kw: None
            self.UniqueConstraint = lambda *a, **kw: None
            self.relationship = lambda *a, **kw: None
        def init_app(self, app): pass
        def create_all(self, *a, **kw): pass
        @property
        def session(self):
            class S:
                def add(self, x): pass
                def commit(self): pass
                def delete(self, x): pass
                def rollback(self): pass
            return S()
    db = DummyDB()
    class UserMixin:
        pass

# ==================== احراز هویت گیسو ====================
class User(UserMixin, db.Model):
    """کاربر سایت گیسو (مستقل)"""
    __tablename__ = 'giso_web_auth'
    id = db.Column(db.Integer, primary_key=True)
    phone = db.Column(db.String(20), unique=True, nullable=False, index=True)
    name = db.Column(db.String(150), default='')
    first_name = db.Column(db.String(100), default='')   # نام (قابل ویرایش در پنل کاربری)
    last_name = db.Column(db.String(100), default='')    # نام خانوادگی (قابل ویرایش در پنل کاربری)
    region = db.Column(db.String(200), default='')
    contact_time = db.Column(db.String(100), default='')
    city = db.Column(db.String(100), default='')
    password_hash = db.Column(db.String(256), nullable=False)
    security_question = db.Column(db.String(200), default='')
    security_answer = db.Column(db.String(200), default='')
    created_at = db.Column(db.String(50), default=lambda: datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
    last_login = db.Column(db.String(50), default='')
    last_profile_edit_at = db.Column(db.String(50), default='')
    # ─── برنامه معرفی و کیف پول ───
    referral_code = db.Column(db.String(30), default='')        # کد اختصاصی معرفی کاربر
    referred_by_code = db.Column(db.String(30), default='')     # کدی که با آن ثبت‌نام شده
    referred_by_user_id = db.Column(db.Integer, default=0)      # معرف این کاربر
    # ─── فاز 4.5: وضعیت کاربر ───
    is_banned = db.Column(db.Integer, default=0)                # 1 = بن‌شده (نمی‌تواند لاگین کند)
    ban_reason = db.Column(db.String(200), default='')

    def get_id(self):
        return str(self.phone)

    def touch_login(self):
        self.last_login = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        db.session.commit()

# ==================== تنظیمات گیسو از bot.db ====================
class GisoConfig(db.Model):
    __bind_key__ = 'bot'
    __tablename__ = 'giso_config'
    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(100), unique=True, nullable=False)
    value = db.Column(db.Text, default='')
    updated_at = db.Column(db.String(50), default='')

class GisoAdmin(db.Model):
    __bind_key__ = 'bot'
    __tablename__ = 'giso_admins'
    id = db.Column(db.Integer, primary_key=True)
    phone = db.Column(db.String(20), default='')
    telegram_id = db.Column(db.String(50), default='')
    bale_id = db.Column(db.String(50), default='')
    added_by = db.Column(db.Integer, default=0)
    added_at = db.Column(db.String(50), default='')

# ==================== داده‌های بومی گیسو (giso.db) ====================
class HairOrder(db.Model):
    __tablename__ = 'hair_orders'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, nullable=True)
    phone = db.Column(db.String(20), default='', index=True)
    customer_name = db.Column(db.String(100), default='')
    photo_path = db.Column(db.String(300), nullable=False)
    length_cm = db.Column(db.Integer, nullable=False)
    hair_type = db.Column(db.String(100), default='')  # حفظ جهت سازگاری با کد موجود
    hair_color = db.Column(db.String(100), default='')
    color_history = db.Column(db.String(200), default='')  # سابقه رنگ/دکلره
    hair_weight = db.Column(db.String(100), default='')  # وزن تقریبی
    hair_health = db.Column(db.String(100), default='')  # سلامت مو
    region = db.Column(db.String(100), default='')
    contact_time = db.Column(db.String(100), default='')
    description = db.Column(db.Text, default='')
    estimated_price = db.Column(db.String(100), default='')
    final_price = db.Column(db.String(100), default='')  # قیمت نهایی ادمین
    admin_note = db.Column(db.Text, default='')  # یادداشت ادمین
    # وضعیت‌های مجاز: pending, reviewing, priced, approved, rejected, completed
    status = db.Column(db.String(30), default='pending', index=True)
    created_at = db.Column(db.String(50), default=lambda: datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
    updated_at = db.Column(db.String(50), default=lambda: datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
    user_edit_count = db.Column(db.Integer, default=0)

# ==================== بازارچه موی گیسو (MVP) ====================
class HairListing(db.Model):
    """آگهی مستقل بازارچه؛ از HairOrder فروش مستقیم جدا نگه داشته می‌شود."""
    __tablename__ = 'hair_listings'
    id = db.Column(db.Integer, primary_key=True)
    # مسیر عمومی SEO؛ مقداردهی در سرویس بازارچه و migration کاملاً افزایشی است.
    slug = db.Column(db.String(220), default='', index=True)
    seller_user_id = db.Column(db.Integer, db.ForeignKey('giso_web_auth.id'), nullable=False, index=True)
    source_hair_order_id = db.Column(db.Integer, db.ForeignKey('hair_orders.id'), nullable=True, index=True)
    photo_path = db.Column(db.String(300), nullable=False)
    hair_type = db.Column(db.String(100), default='')
    length_cm = db.Column(db.Integer, nullable=False)
    hair_health = db.Column(db.String(100), default='')
    hair_weight = db.Column(db.String(100), default='')
    city = db.Column(db.String(100), default='', index=True)
    region = db.Column(db.String(150), default='')
    seller_asking_price = db.Column(db.Integer, default=0, index=True)
    seller_note = db.Column(db.Text, default='')
    estimated_price_snapshot = db.Column(db.String(100), default='')
    status = db.Column(db.String(30), default='pending_review', index=True)
    views_count = db.Column(db.Integer, default=0)
    offers_count = db.Column(db.Integer, default=0)
    highest_offer_amount = db.Column(db.Integer, default=0)
    admin_note = db.Column(db.Text, default='')
    reject_reason = db.Column(db.Text, default='')
    terms_version = db.Column(db.String(30), default='marketplace-v1')
    terms_accepted_at = db.Column(db.String(50), default='')
    created_at = db.Column(db.String(50), default=lambda: datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
    updated_at = db.Column(db.String(50), default=lambda: datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
    published_at = db.Column(db.String(50), default='')
    # حذف کامل در UI به‌صورت soft-delete انجام می‌شود تا سابقه ممیزی حفظ شود.
    deleted_at = db.Column(db.String(50), default='', index=True)
    sold_at = db.Column(db.String(50), default='', index=True)
    sold_offer_id = db.Column(db.Integer, db.ForeignKey('buyer_offers.id'), nullable=True)
    edit_count = db.Column(db.Integer, default=0)
    promotion_type = db.Column(db.String(30), default='', index=True)
    promotion_expires_at = db.Column(db.String(50), default='')
    promotion_bumped_at = db.Column(db.String(50), default='')
    # مهلت ۳۰روزه‌ی نمایش عمومی آگهی (هم‌الگوی آگهی مرکز زیبایی). مقدار خاموش
    # '' یعنی بدون محدودیت؛ پس ستون جدید هیچ داده‌ی قدیمی را از فهرست حذف نمی‌کند.
    listing_expires_at = db.Column(db.String(50), default='', index=True)

class MarketplaceDevice(db.Model):
    """شناسه privacy-aware مرورگر؛ token خام و IP خام هرگز ذخیره نمی‌شوند."""
    __tablename__ = 'marketplace_devices'
    id = db.Column(db.Integer, primary_key=True)
    device_key_hash = db.Column(db.String(64), unique=True, nullable=False, index=True)
    fingerprint_hash = db.Column(db.String(64), default='', index=True)
    last_ip_hash = db.Column(db.String(64), default='', index=True)
    first_seen_at = db.Column(db.String(50), default=lambda: datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
    last_seen_at = db.Column(db.String(50), default=lambda: datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
    linked_user_count = db.Column(db.Integer, default=0)
    linked_phone_count = db.Column(db.Integer, default=0)
    risk_level = db.Column(db.String(40), default='clean', index=True)
    correlation_flags = db.Column(db.Text, default='')
    correlation_evidence = db.Column(db.Text, default='')
    correlated_device_count = db.Column(db.Integer, default=0)

class MarketplaceDeviceLink(db.Model):
    """ارتباط چندبه‌چند device و حساب برای کشف چندحسابی بدون تغییر auth."""
    __tablename__ = 'marketplace_device_links'
    id = db.Column(db.Integer, primary_key=True)
    device_id = db.Column(db.Integer, db.ForeignKey('marketplace_devices.id'), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey('giso_web_auth.id'), nullable=False, index=True)
    phone_snapshot = db.Column(db.String(20), default='', index=True)
    first_seen_at = db.Column(db.String(50), default=lambda: datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
    last_seen_at = db.Column(db.String(50), default=lambda: datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
    last_event = db.Column(db.String(40), default='visit')
    __table_args__ = (db.UniqueConstraint('device_id', 'user_id', name='uq_market_device_user'),)

class MarketplacePhoneObservation(db.Model):
    """تاریخچه append-like شماره‌های دیده‌شده روی هر device/user."""
    __tablename__ = 'marketplace_phone_observations'
    id = db.Column(db.Integer, primary_key=True)
    device_id = db.Column(db.Integer, db.ForeignKey('marketplace_devices.id'), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey('giso_web_auth.id'), nullable=False, index=True)
    phone_snapshot = db.Column(db.String(20), nullable=False, index=True)
    first_seen_at = db.Column(db.String(50), default=lambda: datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
    last_seen_at = db.Column(db.String(50), default=lambda: datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
    observation_count = db.Column(db.Integer, default=1)
    last_event = db.Column(db.String(40), default='visit')
    __table_args__ = (
        db.UniqueConstraint('device_id', 'user_id', 'phone_snapshot', name='uq_market_device_user_phone'),
    )

class MarketplaceListingDeviceClaim(db.Model):
    """مالک اتمیک device روی یک آگهی؛ یک device/listing فقط یک buyer identity."""
    __tablename__ = 'marketplace_listing_device_claims'
    id = db.Column(db.Integer, primary_key=True)
    listing_id = db.Column(db.Integer, db.ForeignKey('hair_listings.id'), nullable=False, index=True)
    device_id = db.Column(db.Integer, db.ForeignKey('marketplace_devices.id'), nullable=False, index=True)
    buyer_user_id = db.Column(db.Integer, db.ForeignKey('giso_web_auth.id'), nullable=False, index=True)
    phone_snapshot = db.Column(db.String(20), default='')
    created_at = db.Column(db.String(50), default=lambda: datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
    updated_at = db.Column(db.String(50), default=lambda: datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
    __table_args__ = (
        db.UniqueConstraint('listing_id', 'device_id', name='uq_market_listing_device_claim'),
    )

class MarketplaceRiskEvent(db.Model):
    """رویداد قابل ممیزی برای flag/block شدن device یا تلاش پیشنهاد."""
    __tablename__ = 'marketplace_risk_events'
    id = db.Column(db.Integer, primary_key=True)
    event_type = db.Column(db.String(50), nullable=False, index=True)
    status = db.Column(db.String(20), default='flagged', index=True)
    listing_id = db.Column(db.Integer, db.ForeignKey('hair_listings.id'), nullable=True, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey('giso_web_auth.id'), nullable=True, index=True)
    phone_snapshot = db.Column(db.String(20), default='', index=True)
    device_id = db.Column(db.Integer, db.ForeignKey('marketplace_devices.id'), nullable=True, index=True)
    device_hash_short = db.Column(db.String(16), default='')
    fingerprint_hash = db.Column(db.String(64), default='')
    ip_hash = db.Column(db.String(64), default='')
    risk_level = db.Column(db.String(50), default='clean', index=True)
    reason = db.Column(db.String(100), default='', index=True)
    reason_detail = db.Column(db.Text, default='')
    offer_amount = db.Column(db.Integer, default=0)
    offer_note = db.Column(db.Text, default='')
    correlation_evidence = db.Column(db.Text, default='')
    created_at = db.Column(db.String(50), default=lambda: datetime.now().strftime('%Y-%m-%d %H:%M:%S'), index=True)

class BuyerProfile(db.Model):
    """مجوز دامنه‌ای خریدار روی همان User موجود؛ سیستم auth/role جدید نیست."""
    __tablename__ = 'buyer_profiles'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('giso_web_auth.id'), unique=True, nullable=False, index=True)
    phone_snapshot = db.Column(db.String(20), default='', index=True)
    latest_device_key = db.Column(db.String(64), default='', index=True)
    verification_status = db.Column(db.String(30), default='pending', index=True)
    risk_flags = db.Column(db.Text, default='')
    admin_note = db.Column(db.Text, default='')
    verified_at = db.Column(db.String(50), default='')
    terms_version = db.Column(db.String(30), default='marketplace-v1')
    terms_accepted_at = db.Column(db.String(50), default='')
    # درخواست خرید مو در پنل کاربر → فروش مو (افزایشی و بدون auth موازی)
    request_name = db.Column(db.String(150), default='')
    request_phone = db.Column(db.String(20), default='')
    request_city = db.Column(db.String(100), default='')
    buyer_type = db.Column(db.String(30), default='personal')
    request_description = db.Column(db.Text, default='')
    budget_min = db.Column(db.Integer, default=0)
    budget_max = db.Column(db.Integer, default=0)
    edit_count = db.Column(db.Integer, default=0)
    created_at = db.Column(db.String(50), default=lambda: datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
    updated_at = db.Column(db.String(50), default=lambda: datetime.now().strftime('%Y-%m-%d %H:%M:%S'))

class BuyerOffer(db.Model):
    __tablename__ = 'buyer_offers'
    id = db.Column(db.Integer, primary_key=True)
    listing_id = db.Column(db.Integer, db.ForeignKey('hair_listings.id'), nullable=False, index=True)
    buyer_user_id = db.Column(db.Integer, db.ForeignKey('giso_web_auth.id'), nullable=False, index=True)
    buyer_profile_id = db.Column(db.Integer, db.ForeignKey('buyer_profiles.id'), nullable=False, index=True)
    device_id = db.Column(db.Integer, db.ForeignKey('marketplace_devices.id'), nullable=True, index=True)
    offer_amount = db.Column(db.Integer, nullable=False)
    offer_note = db.Column(db.Text, default='')
    status = db.Column(db.String(30), default='pending', index=True)
    seller_response_note = db.Column(db.Text, default='')
    seller_counter_amount = db.Column(db.Integer, default=0)
    risk_snapshot = db.Column(db.String(100), default='clean')
    accepted_at = db.Column(db.String(50), default='')
    rejected_at = db.Column(db.String(50), default='')
    sold_at = db.Column(db.String(50), default='')
    # بستن گفتگو سابقه را حذف نمی‌کند و فقط نوشتن پیام تازه را متوقف می‌سازد.
    chat_closed = db.Column(db.Integer, default=0, index=True)
    chat_closed_at = db.Column(db.String(50), default='')
    chat_closed_by_user_id = db.Column(db.Integer, db.ForeignKey('giso_web_auth.id'), nullable=True)
    created_at = db.Column(db.String(50), default=lambda: datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
    updated_at = db.Column(db.String(50), default=lambda: datetime.now().strftime('%Y-%m-%d %H:%M:%S'))

class MarketplaceReview(db.Model):
    """نظر ناشناس معامله؛ شناسه‌ها فقط برای مجوز و جلوگیری از ثبت تکراری نگه‌داری می‌شوند."""
    __tablename__ = 'marketplace_reviews'
    id = db.Column(db.Integer, primary_key=True)
    listing_id = db.Column(db.Integer, db.ForeignKey('hair_listings.id'), nullable=False, index=True)
    offer_id = db.Column(db.Integer, db.ForeignKey('buyer_offers.id'), nullable=False, index=True)
    reviewer_user_id = db.Column(db.Integer, db.ForeignKey('giso_web_auth.id'), nullable=False, index=True)
    reviewee_user_id = db.Column(db.Integer, db.ForeignKey('giso_web_auth.id'), nullable=False, index=True)
    reviewer_role = db.Column(db.String(20), nullable=False)
    rating = db.Column(db.Integer, nullable=False)
    comment = db.Column(db.Text, default='')
    status = db.Column(db.String(20), default='visible', index=True)
    created_at = db.Column(db.String(50), default=lambda: datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
    __table_args__ = (
        db.UniqueConstraint('offer_id', 'reviewer_user_id', name='uq_market_review_offer_reviewer'),
    )

class MarketplaceUserRating(db.Model):
    """کش تجمیعی اعتبار؛ منبع حقیقت همچنان نظرهای visible است."""
    __tablename__ = 'marketplace_user_ratings'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('giso_web_auth.id'), unique=True, nullable=False, index=True)
    rating_avg = db.Column(db.Float, default=0.0)
    rating_count = db.Column(db.Integer, default=0)
    updated_at = db.Column(db.String(50), default=lambda: datetime.now().strftime('%Y-%m-%d %H:%M:%S'))

class MarketplacePriceStat(db.Model):
    __tablename__ = 'marketplace_price_stats'
    id = db.Column(db.Integer, primary_key=True)
    city = db.Column(db.String(100), nullable=False, index=True)
    hair_type = db.Column(db.String(50), default='all', index=True)
    length_range = db.Column(db.String(40), default='all', index=True)
    min_price = db.Column(db.Integer, default=0)
    max_price = db.Column(db.Integer, default=0)
    avg_price = db.Column(db.Integer, default=0)
    sample_count = db.Column(db.Integer, default=0)
    source = db.Column(db.String(30), default='internal', index=True)
    updated_at = db.Column(db.String(50), default=lambda: datetime.now().strftime('%Y-%m-%d %H:%M:%S'), index=True)
    __table_args__ = (
        db.UniqueConstraint('city', 'hair_type', 'length_range', name='uq_market_price_city_type_length'),
    )

class MarketplacePriceHistory(db.Model):
    __tablename__ = 'marketplace_price_history'
    id = db.Column(db.Integer, primary_key=True)
    city = db.Column(db.String(100), nullable=False, index=True)
    date = db.Column(db.String(50), nullable=False, index=True)
    avg_price = db.Column(db.Integer, default=0)
    max_price = db.Column(db.Integer, default=0)
    __table_args__ = (db.UniqueConstraint('city', 'date', name='uq_market_price_history_city_date'),)

class MarketplaceSavedSearch(db.Model):
    __tablename__ = 'marketplace_saved_searches'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('giso_web_auth.id'), nullable=False, index=True)
    filters = db.Column(db.Text, default='{}')
    alert_enabled = db.Column(db.Integer, default=1, index=True)
    created_at = db.Column(db.String(50), default=lambda: datetime.now().strftime('%Y-%m-%d %H:%M:%S'))

class MarketplacePolicy(db.Model):
    __tablename__ = 'marketplace_policies'
    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(100), unique=True, nullable=False, index=True)
    value = db.Column(db.Text, default='')
    updated_at = db.Column(db.String(50), default=lambda: datetime.now().strftime('%Y-%m-%d %H:%M:%S'))

class MarketplaceEventStat(db.Model):
    __tablename__ = 'marketplace_event_stats'
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.String(20), unique=True, nullable=False, index=True)
    listings_count = db.Column(db.Integer, default=0)
    offers_count = db.Column(db.Integer, default=0)
    deals_count = db.Column(db.Integer, default=0)
    active_users_count = db.Column(db.Integer, default=0)
    views_count = db.Column(db.Integer, default=0)
    updated_at = db.Column(db.String(50), default=lambda: datetime.now().strftime('%Y-%m-%d %H:%M:%S'))

class MarketplacePriceJobLog(db.Model):
    __tablename__ = 'marketplace_price_job_logs'
    id = db.Column(db.Integer, primary_key=True)
    status = db.Column(db.String(30), default='started', index=True)
    source = db.Column(db.String(30), default='internal')
    sample_count = db.Column(db.Integer, default=0)
    ai_provider = db.Column(db.String(80), default='')
    fallback_level = db.Column(db.String(30), default='internal')
    error_message = db.Column(db.Text, default='')
    started_at = db.Column(db.String(50), default='')
    finished_at = db.Column(db.String(50), default='', index=True)

class MarketplaceMessage(db.Model):
    __tablename__ = 'marketplace_messages'
    id = db.Column(db.Integer, primary_key=True)
    offer_id = db.Column(db.Integer, db.ForeignKey('buyer_offers.id'), nullable=False, index=True)
    sender_user_id = db.Column(db.Integer, db.ForeignKey('giso_web_auth.id'), nullable=False, index=True)
    sender_role = db.Column(db.String(20), nullable=False)
    message_text = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.String(50), default=lambda: datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
    is_reported = db.Column(db.Integer, default=0)
    is_deleted_for_moderation = db.Column(db.Integer, default=0)

class ListingReport(db.Model):
    __tablename__ = 'listing_reports'
    id = db.Column(db.Integer, primary_key=True)
    listing_id = db.Column(db.Integer, db.ForeignKey('hair_listings.id'), nullable=False, index=True)
    offer_id = db.Column(db.Integer, db.ForeignKey('buyer_offers.id'), nullable=True, index=True)
    reporter_user_id = db.Column(db.Integer, db.ForeignKey('giso_web_auth.id'), nullable=False, index=True)
    target_type = db.Column(db.String(20), default='listing', index=True)
    reason = db.Column(db.String(100), default='')
    message = db.Column(db.Text, default='')
    status = db.Column(db.String(30), default='open', index=True)
    created_at = db.Column(db.String(50), default=lambda: datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
    updated_at = db.Column(db.String(50), default=lambda: datetime.now().strftime('%Y-%m-%d %H:%M:%S'))

class Analysis(db.Model):
    __tablename__ = 'analyses'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, nullable=True)
    phone = db.Column(db.String(20), default='')
    type = db.Column(db.String(20), nullable=False)
    photo_path = db.Column(db.String(300), nullable=False)
    ai_report_json = db.Column(db.Text, default='{}')
    plan_json = db.Column(db.Text, default='')
    quick_solution_json = db.Column(db.Text, default='')
    checklist_progress = db.Column(db.Text, default='{}')
    review_submitted = db.Column(db.Integer, default=0)
    review_rating = db.Column(db.Integer, default=0)
    review_text = db.Column(db.Text, default='')
    review_issue = db.Column(db.Text, default='')
    duration_weeks = db.Column(db.Integer, default=4)
    image_paths = db.Column(db.Text, default='[]')
    questions_answers = db.Column(db.Text, default='{}')
    admin_note = db.Column(db.Text, default='')  # یادداشت دستی ادمین
    # فیلدهای مشاور هوشمند صادقی
    consultant_chat_history = db.Column(db.Text, default='[]')  # JSON لیست پیام‌ها
    consultant_key_notes = db.Column(db.Text, default='')       # خلاصه ۵۰۰ کاراکتری
    report_type_viewed = db.Column(db.String(20), default='')   # quick / full / both
    chat_rating = db.Column(db.Integer, default=0)              # امتیاز مشاور در پایان
    created_at = db.Column(db.String(50), default=lambda: datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
    updated_at = db.Column(db.String(50), default='')
    archived_at = db.Column(db.String(50), default='', index=True)

class Product(db.Model):
    __tablename__ = 'products'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    slug = db.Column(db.String(260), default='')
    description = db.Column(db.Text, default='')
    short_description = db.Column(db.String(500), default='')
    category = db.Column(db.String(100), default='')
    subcategory = db.Column(db.String(100), default='')
    brand = db.Column(db.String(100), default='')
    price = db.Column(db.Integer, default=0)
    old_price = db.Column(db.Integer, default=0)
    # قیمت تمام‌شده/فاکتور (داخلی — هیچ‌جا به مشتری نشان داده نمی‌شود؛ مبنای محاسبهٔ قیمت فروش)
    cost_price = db.Column(db.Integer, default=0)
    image_path = db.Column(db.String(300), default='')
    in_stock = db.Column(db.Boolean, default=True)
    # E1 fix (checkout stock): موجودی عددی؛ NULL = سقف نامحدود با رفتار قدیمی in_stock
    stock = db.Column(db.Integer, nullable=True)
    views = db.Column(db.Integer, default=0)
    source = db.Column(db.String(20), default='site')
    channel_msg_id = db.Column(db.String(40), default='')
    publish_status = db.Column(db.String(20), default='published')
    # Phase 2 S2: Beauty Product fields
    usage = db.Column(db.Text, default='')
    ingredients = db.Column(db.Text, default='')
    warnings = db.Column(db.Text, default='')
    suitable_for = db.Column(db.String(300), default='')
    hair_type = db.Column(db.String(100), default='')
    skin_type = db.Column(db.String(100), default='')
    concerns = db.Column(db.Text, default='')
    status = db.Column(db.String(20), default='active')
    created_at = db.Column(db.String(50), default=lambda: datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
    updated_at = db.Column(db.String(50), default='')

class ShopCheckout(db.Model):
    """سربرگ اتمیک یک checkout؛ منبع معتبر برای برداشت کیف پول سبد خرید."""
    __tablename__ = 'shop_checkouts'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('giso_web_auth.id'), nullable=False, index=True)
    gross_amount = db.Column(db.Integer, default=0)
    discount_amount = db.Column(db.Integer, default=0)
    wallet_used = db.Column(db.Integer, default=0)
    cash_wallet_used = db.Column(db.Integer, default=0)
    spend_wallet_used = db.Column(db.Integer, default=0)
    cod_amount = db.Column(db.Integer, default=0)
    discount_code = db.Column(db.String(80), default='')
    status = db.Column(db.String(30), default='placed', index=True)
    created_at = db.Column(db.String(50), default=lambda: datetime.now().strftime('%Y-%m-%d %H:%M:%S'))

class ShopInvoice(db.Model):
    """فاکتور رسمی و snapshot مالی هر checkout فروشگاه."""
    __tablename__ = 'shop_invoices'
    id = db.Column(db.Integer, primary_key=True)
    invoice_number = db.Column(db.String(50), unique=True, nullable=False, index=True)
    checkout_id = db.Column(db.Integer, db.ForeignKey('shop_checkouts.id'), unique=True, nullable=True, index=True)
    # Nullable only for backfilling very old orders that predate user_id linkage.
    user_id = db.Column(db.Integer, db.ForeignKey('giso_web_auth.id'), nullable=True, index=True)
    customer_name = db.Column(db.String(100), default='')
    customer_phone = db.Column(db.String(20), default='')
    customer_address = db.Column(db.Text, default='')
    gross_amount = db.Column(db.Integer, default=0)
    discount_amount = db.Column(db.Integer, default=0)
    payable_amount = db.Column(db.Integer, default=0)
    wallet_paid_amount = db.Column(db.Integer, default=0)
    cod_amount = db.Column(db.Integer, default=0)
    payment_status = db.Column(db.String(30), default='cod_due', index=True)
    created_at = db.Column(db.String(50), default=lambda: datetime.now().strftime('%Y-%m-%d %H:%M:%S'))

class ShopInvoiceItem(db.Model):
    """اقلام snapshot فاکتور؛ تغییر بعدی قیمت محصول روی فاکتور اثر ندارد."""
    __tablename__ = 'shop_invoice_items'
    id = db.Column(db.Integer, primary_key=True)
    invoice_id = db.Column(db.Integer, db.ForeignKey('shop_invoices.id'), nullable=False, index=True)
    order_id = db.Column(db.Integer, db.ForeignKey('product_orders.id'), nullable=True, index=True)
    product_id = db.Column(db.Integer, nullable=False)
    product_name = db.Column(db.String(200), default='')
    unit_price = db.Column(db.Integer, default=0)
    quantity = db.Column(db.Integer, default=1)
    line_total = db.Column(db.Integer, default=0)

class ProductOrder(db.Model):
    __tablename__ = 'product_orders'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, nullable=True)
    phone = db.Column(db.String(20), default='')
    customer_name = db.Column(db.String(100), default='')
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=False)
    checkout_id = db.Column(db.Integer, db.ForeignKey('shop_checkouts.id'), nullable=True, index=True)
    invoice_id = db.Column(db.Integer, db.ForeignKey('shop_invoices.id'), nullable=True, index=True)
    address = db.Column(db.Text, nullable=False)
    quantity = db.Column(db.Integer, default=1)
    status = db.Column(db.String(30), default='pending')
    tracking_code = db.Column(db.String(40), default='', index=True)
    shipping_cost = db.Column(db.Integer, default=0)
    courier_note = db.Column(db.Text, default='')
    delivery_time = db.Column(db.String(200), default='')
    created_at = db.Column(db.String(50), default=lambda: datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
    product = db.relationship('Product', backref='orders')

class Wishlist(db.Model):
    __tablename__ = 'giso_wishlist'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, nullable=False, index=True)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=False, index=True)
    created_at = db.Column(db.String(50), default=lambda: datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
    product = db.relationship('Product')

# Phase 3 S2: Beauty Categories
class Category(db.Model):
    __tablename__ = 'categories'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False, unique=True)
    slug = db.Column(db.String(120), default='')
    description = db.Column(db.Text, default='')
    parent_id = db.Column(db.Integer, default=0)
    is_active = db.Column(db.Boolean, default=True)
    sort_order = db.Column(db.Integer, default=0)
    created_at = db.Column(db.String(50), default=lambda: datetime.now().strftime('%Y-%m-%d %H:%M:%S'))

class StockNotify(db.Model):
    __tablename__ = 'stock_notifies'
    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=False)
    phone = db.Column(db.String(20), nullable=False)
    created_at = db.Column(db.String(50), default=lambda: datetime.now().strftime('%Y-%m-%d %H:%M:%S'))

class Review(db.Model):
    """مدل ثبت نظرات و رضایت کاربران (فروشگاه یا فروش مو) در giso.db"""
    __tablename__ = 'reviews'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, nullable=True)
    phone = db.Column(db.String(20), default='', index=True)
    review_type = db.Column(db.String(30), nullable=False)  # 'shop_order' یا 'hair_order'
    order_id = db.Column(db.Integer, nullable=False, index=True)
    rating = db.Column(db.Integer, default=5)  # عدد 1 تا 5
    comment = db.Column(db.Text, default='')
    created_at = db.Column(db.String(50), default=lambda: datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
    # فاز 4.6: وضعیت نمایش نظر
    status = db.Column(db.String(20), default='visible')  # visible / hidden / deleted

# ==================== برنامه معرفی و کیف پول (فاز ۳) ====================
class Referral(db.Model):
    """رابطه معرف: کاربر معرفی‌شده + وضعیت + پورسانت."""
    __tablename__ = 'referrals'
    id = db.Column(db.Integer, primary_key=True)
    referrer_user_id = db.Column(db.Integer, nullable=False, index=True)  # کاربر معرف
    referred_user_id = db.Column(db.Integer, nullable=False, index=True)  # کاربر معرفی‌شده
    referral_code = db.Column(db.String(30), default='')
    referred_phone = db.Column(db.String(20), default='', index=True)
    # وضعیت: registered → hair_request_submitted → commission_credited | rejected
    status = db.Column(db.String(30), default='registered', index=True)
    hair_order_id = db.Column(db.Integer, default=0)
    sale_amount = db.Column(db.String(100), default='')    # final_price سفارش (رشته چون متن تومانی است)
    commission_percent = db.Column(db.Integer, default=0)
    commission_amount = db.Column(db.Integer, default=0)   # مبلغ پورسانت به تومان
    created_at = db.Column(db.String(50), default=lambda: datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
    updated_at = db.Column(db.String(50), default='')
    notes = db.Column(db.Text, default='')

class WalletTransaction(db.Model):
    """دفترکل واحد کیف پول؛ balance_scope مصرف/تسویه را تعیین می‌کند."""
    __tablename__ = 'wallet_transactions'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, nullable=False, index=True)
    kind = db.Column(db.String(30), default='adjustment')
    amount = db.Column(db.Integer, default=0)               # + اعتبار / - مصرف یا رزرو
    # available/used/pending/paid در مانده مؤثرند؛ reversed/failed مؤثر نیستند.
    status = db.Column(db.String(20), default='available', index=True)
    source_type = db.Column(db.String(40), default='')
    source_id = db.Column(db.Integer, default=0)
    # cash: قابل مصرف و تسویه؛ spend: فقط قابل مصرف داخل سایت.
    balance_scope = db.Column(db.String(10), default='cash', nullable=False, index=True)
    # برای پاداش، شارژ و برداشت/checkout از ثبت دوباره جلوگیری می‌کند.
    idempotency_key = db.Column(db.String(120), default='', index=True)
    description = db.Column(db.Text, default='')
    created_at = db.Column(db.String(50), default=lambda: datetime.now().strftime('%Y-%m-%d %H:%M:%S'))

class WalletTopupRequest(db.Model):
    """درخواست شارژ دستی با رسید خصوصی اجباری؛ بدون درگاه آنلاین."""
    __tablename__ = 'wallet_topup_requests'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('giso_web_auth.id'), nullable=False, index=True)
    amount = db.Column(db.Integer, default=0)
    payment_reference = db.Column(db.String(120), default='')
    receipt_path = db.Column(db.String(120), default='')
    user_note = db.Column(db.Text, default='')
    status = db.Column(db.String(20), default='pending', index=True)
    admin_note = db.Column(db.Text, default='')
    created_at = db.Column(db.String(50), default=lambda: datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
    reviewed_at = db.Column(db.String(50), default='')
    reviewed_by_user_id = db.Column(db.Integer, default=0)

class WalletMission(db.Model):
    """تعریف مأموریت مالی؛ سه event MVP با code پایدار seed می‌شوند."""
    __tablename__ = 'wallet_missions'
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(60), unique=True, nullable=False, index=True)
    title = db.Column(db.String(160), default='')
    description = db.Column(db.Text, default='')
    reward_amount = db.Column(db.Integer, default=0)
    reward_scope = db.Column(db.String(10), default='spend')
    is_active = db.Column(db.Integer, default=1, index=True)
    is_deleted = db.Column(db.Integer, default=0, index=True)
    sort_order = db.Column(db.Integer, default=0)
    created_at = db.Column(db.String(50), default=lambda: datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
    updated_at = db.Column(db.String(50), default='')

class WalletMissionCompletion(db.Model):
    """ثبت یک‌بارهٔ تکمیل مأموریت؛ unique مانع دوباره‌پرداخت می‌شود."""
    __tablename__ = 'wallet_mission_completions'
    id = db.Column(db.Integer, primary_key=True)
    mission_id = db.Column(db.Integer, db.ForeignKey('wallet_missions.id'), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey('giso_web_auth.id'), nullable=False, index=True)
    event_key = db.Column(db.String(120), default='')
    reward_amount = db.Column(db.Integer, default=0)
    reward_scope = db.Column(db.String(10), default='spend')
    reward_transaction_id = db.Column(db.Integer, db.ForeignKey('wallet_transactions.id'), nullable=True)
    completed_at = db.Column(db.String(50), default=lambda: datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
    __table_args__ = (
        db.UniqueConstraint('mission_id', 'user_id', name='uq_wallet_mission_user'),
    )

class WithdrawalRequest(db.Model):
    """درخواست تسویه کیف پول کاربر."""
    __tablename__ = 'withdrawal_requests'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, nullable=False, index=True)
    amount = db.Column(db.Integer, default=0)
    card_holder_name = db.Column(db.String(150), default='')
    card_number = db.Column(db.String(30), default='')
    sheba = db.Column(db.String(40), default='')
    # وضعیت: pending / paid / rejected
    status = db.Column(db.String(20), default='pending', index=True)
    admin_note = db.Column(db.Text, default='')
    created_at = db.Column(db.String(50), default=lambda: datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
    updated_at = db.Column(db.String(50), default='')

# ==================== مهاجرت ایمن اسکیما (بدون حذف داده) ====================
def get_giso_db_path() -> str:
    base = Path(__file__).resolve().parent
    db_dir = base / 'data'
    db_dir.mkdir(parents=True, exist_ok=True)
    return str(db_dir / 'giso.db')

def migrate_giso_tables(db_path: str = None):
    """
    مهاجرت ایمن ستون‌های جدید و جداول گیسو در giso.db بدون حذف یا دستکاری داده‌های قدیمی
    """
    if db_path is None:
        db_path = get_giso_db_path()
    if not os.path.exists(db_path):
        return  # اگر فایل دیتابیس هنوز وجود ندارد، create_all کل اسکیما را ایجاد می‌کند
    try:
        conn = sqlite3.connect(db_path)
        try:
            # جدول تاریخی دسترسی‌ها برای سازگاری تست/نسخه‌های قدیمی؛ سیاست جاری آن را نمی‌خواند.
            conn.execute("""
                CREATE TABLE IF NOT EXISTS giso_admin_permissions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    admin_bale_id TEXT NOT NULL,
                    section TEXT NOT NULL,
                    is_allowed INTEGER NOT NULL DEFAULT 0,
                    sub_options TEXT DEFAULT '{}',
                    created_at TEXT DEFAULT '',
                    UNIQUE(admin_bale_id, section)
                )
            """)
            # ۱. بررسی و ایجاد جدول reviews (در صورت عدم وجود)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS reviews (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    phone TEXT DEFAULT '',
                    review_type TEXT NOT NULL,
                    order_id INTEGER NOT NULL,
                    rating INTEGER DEFAULT 5,
                    comment TEXT DEFAULT '',
                    created_at TEXT DEFAULT ''
                )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_reviews_order_id ON reviews(order_id)")

            # ۱-ب. افزودن ستون‌های جدید فروشگاه (سئو + ایمپورت کانال) به products
            tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
            if 'products' in tables:
                pcols = {r[1] for r in conn.execute("PRAGMA table_info(products)").fetchall()}
                prod_new_cols = [
                    ('slug', "ALTER TABLE products ADD COLUMN slug TEXT DEFAULT ''"),
                    ('views', "ALTER TABLE products ADD COLUMN views INTEGER DEFAULT 0"),
                    # E1 fix: موجودی عددی checkout — NULL = نامحدود (رفتار قبلی)، idempotent
                    ('stock', "ALTER TABLE products ADD COLUMN stock INTEGER"),
                    ('source', "ALTER TABLE products ADD COLUMN source TEXT DEFAULT 'site'"),
                    ('channel_msg_id', "ALTER TABLE products ADD COLUMN channel_msg_id TEXT DEFAULT ''"),
                    ('publish_status', "ALTER TABLE products ADD COLUMN publish_status TEXT DEFAULT 'published'"),
                    ('updated_at', "ALTER TABLE products ADD COLUMN updated_at TEXT DEFAULT ''"),
                    ('subcategory', "ALTER TABLE products ADD COLUMN subcategory TEXT DEFAULT ''"),
                    ('old_price', "ALTER TABLE products ADD COLUMN old_price INTEGER DEFAULT 0"),
                ]
                for col_name, stmt in prod_new_cols:
                    if col_name not in pcols:
                        try:
                            conn.execute(stmt)
                        except Exception as e:
                            logger.warning(f"migrate products add col {col_name}: {e}")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_products_publish ON products(publish_status)")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_products_channel_msg ON products(channel_msg_id)")
                # یکتایی فقط برای شناسه‌های واقعی کانال (رشته‌های خالی محصولات سایت مستثنا)
                conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS ux_products_channel_msg ON products(channel_msg_id) WHERE channel_msg_id != ''")

            # ۱-ج. ستون‌های سفارش و سربرگ اتمیک checkout فروشگاه
            conn.execute("""
                CREATE TABLE IF NOT EXISTS shop_checkouts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    gross_amount INTEGER DEFAULT 0,
                    discount_amount INTEGER DEFAULT 0,
                    wallet_used INTEGER DEFAULT 0,
                    cash_wallet_used INTEGER DEFAULT 0,
                    spend_wallet_used INTEGER DEFAULT 0,
                    cod_amount INTEGER DEFAULT 0,
                    discount_code TEXT DEFAULT '',
                    status TEXT DEFAULT 'placed',
                    created_at TEXT DEFAULT '',
                    FOREIGN KEY(user_id) REFERENCES giso_web_auth(id)
                )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_shop_checkout_user ON shop_checkouts(user_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_shop_checkout_status ON shop_checkouts(status)")
            # فاکتور رسمی فروشگاه: سربرگ و اقلام snapshot؛ فقط migration افزایشی.
            conn.execute("""
                CREATE TABLE IF NOT EXISTS shop_invoices (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    invoice_number TEXT NOT NULL UNIQUE,
                    checkout_id INTEGER UNIQUE,
                    user_id INTEGER,
                    customer_name TEXT DEFAULT '',
                    customer_phone TEXT DEFAULT '',
                    customer_address TEXT DEFAULT '',
                    gross_amount INTEGER DEFAULT 0,
                    discount_amount INTEGER DEFAULT 0,
                    payable_amount INTEGER DEFAULT 0,
                    wallet_paid_amount INTEGER DEFAULT 0,
                    cod_amount INTEGER DEFAULT 0,
                    payment_status TEXT DEFAULT 'cod_due',
                    created_at TEXT DEFAULT '',
                    FOREIGN KEY(checkout_id) REFERENCES shop_checkouts(id),
                    FOREIGN KEY(user_id) REFERENCES giso_web_auth(id)
                )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_shop_invoice_user ON shop_invoices(user_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_shop_invoice_checkout ON shop_invoices(checkout_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_shop_invoice_status ON shop_invoices(payment_status)")
            conn.execute("""
                CREATE TABLE IF NOT EXISTS shop_invoice_items (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    invoice_id INTEGER NOT NULL,
                    order_id INTEGER,
                    product_id INTEGER NOT NULL,
                    product_name TEXT DEFAULT '',
                    unit_price INTEGER DEFAULT 0,
                    quantity INTEGER DEFAULT 1,
                    line_total INTEGER DEFAULT 0,
                    FOREIGN KEY(invoice_id) REFERENCES shop_invoices(id),
                    FOREIGN KEY(order_id) REFERENCES product_orders(id)
                )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_shop_invoice_item_invoice ON shop_invoice_items(invoice_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_shop_invoice_item_order ON shop_invoice_items(order_id)")
            if 'product_orders' in tables:
                ocols = {r[1] for r in conn.execute("PRAGMA table_info(product_orders)").fetchall()}
                for col_name, stmt in (
                    ('quantity', "ALTER TABLE product_orders ADD COLUMN quantity INTEGER DEFAULT 1"),
                    ('tracking_code', "ALTER TABLE product_orders ADD COLUMN tracking_code TEXT DEFAULT ''"),
                    ('shipping_cost', "ALTER TABLE product_orders ADD COLUMN shipping_cost INTEGER DEFAULT 0"),
                    ('checkout_id', "ALTER TABLE product_orders ADD COLUMN checkout_id INTEGER"),
                    ('invoice_id', "ALTER TABLE product_orders ADD COLUMN invoice_id INTEGER"),
                    ('courier_note', "ALTER TABLE product_orders ADD COLUMN courier_note TEXT DEFAULT ''"),
                    ('delivery_time', "ALTER TABLE product_orders ADD COLUMN delivery_time TEXT DEFAULT ''"),
                ):
                    if col_name not in ocols:
                        try:
                            conn.execute(stmt)
                        except Exception as e:
                            logger.warning(f"migrate product_orders add {col_name}: {e}")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_product_orders_tracking ON product_orders(tracking_code)")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_product_orders_checkout ON product_orders(checkout_id)")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_product_orders_invoice ON product_orders(invoice_id)")

            # Phase 2 S2: Beauty Product fields (idempotent)
            if 'products' in tables:
                pcols2 = {r[1] for r in conn.execute("PRAGMA table_info(products)").fetchall()}
                beauty_cols = [
                    ('short_description', "ALTER TABLE products ADD COLUMN short_description TEXT DEFAULT ''"),
                    ('brand', "ALTER TABLE products ADD COLUMN brand TEXT DEFAULT ''"),
                    ('usage', "ALTER TABLE products ADD COLUMN usage TEXT DEFAULT ''"),
                    ('ingredients', "ALTER TABLE products ADD COLUMN ingredients TEXT DEFAULT ''"),
                    ('warnings', "ALTER TABLE products ADD COLUMN warnings TEXT DEFAULT ''"),
                    ('suitable_for', "ALTER TABLE products ADD COLUMN suitable_for TEXT DEFAULT ''"),
                    ('hair_type', "ALTER TABLE products ADD COLUMN hair_type TEXT DEFAULT ''"),
                    ('skin_type', "ALTER TABLE products ADD COLUMN skin_type TEXT DEFAULT ''"),
                    ('concerns', "ALTER TABLE products ADD COLUMN concerns TEXT DEFAULT ''"),
                    ('status', "ALTER TABLE products ADD COLUMN status TEXT DEFAULT 'active'"),
                    # قیمت فاکتور داخلی (محاسبه قیمت فروش)؛ دسته و وضعیت خوراکی/سفارش خاص
                    ('cost_price', "ALTER TABLE products ADD COLUMN cost_price INTEGER DEFAULT 0"),
                ]
                for col_name, stmt in beauty_cols:
                    if col_name not in pcols2:
                        try:
                            conn.execute(stmt)
                        except Exception as e:
                            logger.warning(f"migrate products beauty col {col_name}: {e}")

            # Phase 3 S2: Categories table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS categories (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL UNIQUE,
                    slug TEXT DEFAULT '',
                    description TEXT DEFAULT '',
                    parent_id INTEGER DEFAULT 0,
                    is_active INTEGER DEFAULT 1,
                    sort_order INTEGER DEFAULT 0,
                    created_at TEXT DEFAULT ''
                )
            """)

            # Phase 20 S2: Customer Score table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS customer_scores (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER DEFAULT 0,
                    phone TEXT DEFAULT '',
                    score INTEGER DEFAULT 0,
                    level TEXT DEFAULT 'cold',
                    analysis_count INTEGER DEFAULT 0,
                    order_count INTEGER DEFAULT 0,
                    hair_sale_count INTEGER DEFAULT 0,
                    last_activity TEXT DEFAULT '',
                    created_at TEXT DEFAULT '',
                    updated_at TEXT DEFAULT '',
                    UNIQUE(user_id, phone)
                )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_cust_score_user ON customer_scores(user_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_cust_score_phone ON customer_scores(phone)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_cust_score_level ON customer_scores(level)")

            # Discount codes table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS discount_codes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    code TEXT NOT NULL UNIQUE,
                    discount_type TEXT DEFAULT 'percent',
                    discount_value INTEGER DEFAULT 0,
                    min_order_amount INTEGER DEFAULT 0,
                    max_uses INTEGER DEFAULT 0,
                    used_count INTEGER DEFAULT 0,
                    is_active INTEGER DEFAULT 1,
                    expires_at TEXT DEFAULT '',
                    created_at TEXT DEFAULT ''
                )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_discount_code ON discount_codes(code)")

            conn.execute("""
                CREATE TABLE IF NOT EXISTS giso_wishlist (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    product_id INTEGER NOT NULL,
                    created_at TEXT DEFAULT '',
                    UNIQUE(user_id, product_id)
                )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_wishlist_user ON giso_wishlist(user_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_wishlist_product ON giso_wishlist(product_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_reviews_phone ON reviews(phone)")

            # ۲. بررسی و افزودن ستون‌های جدید جدول hair_orders
            tables = [r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
            if 'hair_orders' in tables:
                cols = {r[1] for r in conn.execute("PRAGMA table_info(hair_orders)").fetchall()}
                additions = [
                    ('hair_color', "ALTER TABLE hair_orders ADD COLUMN hair_color TEXT DEFAULT ''"),
                    ('color_history', "ALTER TABLE hair_orders ADD COLUMN color_history TEXT DEFAULT ''"),
                    ('hair_weight', "ALTER TABLE hair_orders ADD COLUMN hair_weight TEXT DEFAULT ''"),
                    ('hair_health', "ALTER TABLE hair_orders ADD COLUMN hair_health TEXT DEFAULT ''"),
                    ('final_price', "ALTER TABLE hair_orders ADD COLUMN final_price TEXT DEFAULT ''"),
                    ('admin_note', "ALTER TABLE hair_orders ADD COLUMN admin_note TEXT DEFAULT ''"),
                    ('updated_at', "ALTER TABLE hair_orders ADD COLUMN updated_at TEXT DEFAULT ''"),
                    ('user_edit_count', "ALTER TABLE hair_orders ADD COLUMN user_edit_count INTEGER DEFAULT 0"),
                ]
                for col_name, sql in additions:
                    if col_name not in cols:
                        try:
                            conn.execute(sql)
                        except Exception as e:
                            logger.warning(f"migrate hair_orders add col {col_name}: {e}")

            # ۳. ایجاد ایندکس‌های تکمیلی روی ستون‌های پرکاربرد (ایمن)
            try:
                conn.execute("CREATE INDEX IF NOT EXISTS idx_hair_orders_phone ON hair_orders(phone)")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_hair_orders_status ON hair_orders(status)")
            except Exception:
                pass

            # ۴. بررسی و افزودن ستون یادداشت ادمین به جدول analyses
            if 'analyses' in tables:
                cols_ana = {r[1] for r in conn.execute("PRAGMA table_info(analyses)").fetchall()}
                if 'admin_note' not in cols_ana:
                    try:
                        conn.execute("ALTER TABLE analyses ADD COLUMN admin_note TEXT DEFAULT ''")
                    except Exception as e:
                        logger.warning(f"migrate analyses add col admin_note: {e}")
                ana_new_cols = [
                    ('plan_json', "ALTER TABLE analyses ADD COLUMN plan_json TEXT DEFAULT ''"),
                    ('checklist_progress', "ALTER TABLE analyses ADD COLUMN checklist_progress TEXT DEFAULT '{}'"),
                    ('review_submitted', "ALTER TABLE analyses ADD COLUMN review_submitted INTEGER DEFAULT 0"),
                    ('review_rating', "ALTER TABLE analyses ADD COLUMN review_rating INTEGER DEFAULT 0"),
                    ('review_text', "ALTER TABLE analyses ADD COLUMN review_text TEXT DEFAULT ''"),
                    ('review_issue', "ALTER TABLE analyses ADD COLUMN review_issue TEXT DEFAULT ''"),
                    ('duration_weeks', "ALTER TABLE analyses ADD COLUMN duration_weeks INTEGER DEFAULT 4"),
                    ('image_paths', "ALTER TABLE analyses ADD COLUMN image_paths TEXT DEFAULT '[]'"),
                    ('questions_answers', "ALTER TABLE analyses ADD COLUMN questions_answers TEXT DEFAULT '{}'"),
                    ('consultant_chat_history', "ALTER TABLE analyses ADD COLUMN consultant_chat_history TEXT DEFAULT '[]'"),
                    ('consultant_key_notes', "ALTER TABLE analyses ADD COLUMN consultant_key_notes TEXT DEFAULT ''"),
                    ('report_type_viewed', "ALTER TABLE analyses ADD COLUMN report_type_viewed TEXT DEFAULT ''"),
                    ('chat_rating', "ALTER TABLE analyses ADD COLUMN chat_rating INTEGER DEFAULT 0"),
                    ('quick_solution_json', "ALTER TABLE analyses ADD COLUMN quick_solution_json TEXT DEFAULT ''"),
                    ('updated_at', "ALTER TABLE analyses ADD COLUMN updated_at TEXT DEFAULT ''"),
                    ('archived_at', "ALTER TABLE analyses ADD COLUMN archived_at TEXT DEFAULT ''"),
                ]
                for col_name, sql in ana_new_cols:
                    if col_name not in cols_ana:
                        try:
                            conn.execute(sql)
                        except Exception as e:
                            logger.warning(f"migrate analyses add col {col_name}: {e}")

            # ۵. بررسی و افزودن ستون‌های نام، منطقه و ساعت تماس به جدول giso_web_auth
            if 'giso_web_auth' in tables:
                cols_auth = {r[1] for r in conn.execute("PRAGMA table_info(giso_web_auth)").fetchall()}
                add_auth_cols = [
                    ('name', "ALTER TABLE giso_web_auth ADD COLUMN name TEXT DEFAULT ''"),
                    ('region', "ALTER TABLE giso_web_auth ADD COLUMN region TEXT DEFAULT ''"),
                    ('contact_time', "ALTER TABLE giso_web_auth ADD COLUMN contact_time TEXT DEFAULT ''"),
                    ('city', "ALTER TABLE giso_web_auth ADD COLUMN city TEXT DEFAULT ''"),
                ]
                for col_name, sql in add_auth_cols:
                    if col_name not in cols_auth:
                        try:
                            conn.execute(sql)
                        except Exception as e:
                            logger.warning(f"migrate giso_web_auth add col {col_name}: {e}")

            # ۶. جدول محدودیت زمان تحلیل
            conn.execute("""
                CREATE TABLE IF NOT EXISTS analysis_rate_limits (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ip TEXT DEFAULT '',
                    phone TEXT DEFAULT '',
                    analysis_type TEXT DEFAULT 'hair',
                    created_at TEXT NOT NULL
                )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_analysis_rate_ip ON analysis_rate_limits(ip)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_analysis_rate_phone ON analysis_rate_limits(phone)")

            # ۷. جدول درخواست‌های محصول (برای محصولات نایاب)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS product_requests (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    phone TEXT NOT NULL DEFAULT '',
                    city TEXT DEFAULT '',
                    analysis_id INTEGER,
                    problem_summary TEXT DEFAULT '',
                    status TEXT DEFAULT 'pending',
                    admin_note TEXT DEFAULT '',
                    created_at TEXT DEFAULT ''
                )
            """)
            # ۸. جدول درخواست‌های مشاوره
            conn.execute("""
                CREATE TABLE IF NOT EXISTS consultant_requests (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    phone TEXT NOT NULL DEFAULT '',
                    city TEXT DEFAULT '',
                    customer_name TEXT DEFAULT '',
                    analysis_id INTEGER,
                    initial_message TEXT DEFAULT '',
                    status TEXT DEFAULT 'new',
                    admin_id INTEGER DEFAULT 0,
                    created_at TEXT DEFAULT '',
                    updated_at TEXT DEFAULT ''
                )
            """)
            # ۹. جدول پیام‌های مشاوره
            conn.execute("""
                CREATE TABLE IF NOT EXISTS consultant_messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    request_id INTEGER NOT NULL,
                    sender TEXT DEFAULT 'user',
                    message TEXT DEFAULT '',
                    is_read INTEGER DEFAULT 0,
                    created_at TEXT DEFAULT ''
                )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_consultant_messages_req ON consultant_messages(request_id)")

            # ۱۰. جدول چت مشاور صادقی در ربات
            conn.execute("""
                CREATE TABLE IF NOT EXISTS giso_bot_consultant_chat (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    bale_id TEXT NOT NULL,
                    role TEXT NOT NULL,
                    message TEXT NOT NULL,
                    created_at TEXT DEFAULT ''
                )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_bot_cons_chat_bale ON giso_bot_consultant_chat(bale_id)")

            # ۱۱. جدول تیکت‌های پشتیبانی
            conn.execute("""
                CREATE TABLE IF NOT EXISTS giso_support_tickets (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_bale_id TEXT NOT NULL,
                    user_name TEXT DEFAULT '',
                    phone TEXT DEFAULT '',
                    message TEXT NOT NULL,
                    status TEXT DEFAULT 'new',
                    admin_reply TEXT DEFAULT '',
                    admin_bale_id TEXT DEFAULT '',
                    created_at TEXT DEFAULT '',
                    replied_at TEXT DEFAULT ''
                )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_support_tickets_user ON giso_support_tickets(user_bale_id)")

            # ۱۲. لاگ گفتگوهای ویجت سایت (برای تحلیل شخصیت کاربر و آنالیز مدیریتی)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS giso_widget_chats (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    actor_key TEXT DEFAULT '',
                    role TEXT DEFAULT 'guest',
                    phone TEXT DEFAULT '',
                    user_name TEXT DEFAULT '',
                    page_path TEXT DEFAULT '/',
                    message_role TEXT DEFAULT 'user',
                    content TEXT DEFAULT '',
                    created_at TEXT DEFAULT ''
                )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_widget_chats_actor ON giso_widget_chats(actor_key)")

            # ۱۳. بازخورد پاسخ‌های ویجت (👍/👎)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS giso_widget_feedback (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    actor_key TEXT DEFAULT '',
                    rating INTEGER DEFAULT 0,
                    page_path TEXT DEFAULT '/',
                    created_at TEXT DEFAULT ''
                )
            """)

            # ۱۴. نام و نام خانوادگی کاربران سایت (ویرایش اطلاعات شخصی در پنل کاربری)
            try:
                wtables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
                if 'giso_web_auth' in wtables:
                    wcols = {r[1] for r in conn.execute("PRAGMA table_info(giso_web_auth)").fetchall()}
                    for col_name, stmt in (
                        ('first_name', "ALTER TABLE giso_web_auth ADD COLUMN first_name TEXT DEFAULT ''"),
                        ('last_name', "ALTER TABLE giso_web_auth ADD COLUMN last_name TEXT DEFAULT ''"),
                        ('last_profile_edit_at', "ALTER TABLE giso_web_auth ADD COLUMN last_profile_edit_at TEXT DEFAULT ''"),
                    ):
                        if col_name not in wcols:
                            try:
                                conn.execute(stmt)
                            except Exception as e:
                                logger.warning(f"migrate giso_web_auth add col {col_name}: {e}")
            except Exception as e:
                logger.warning(f"migrate giso_web_auth name cols: {e}")

            # ۱۵. برنامه معرفی و کیف پول: ستون‌های referral در giso_web_auth
            try:
                rcols = {r[1] for r in conn.execute("PRAGMA table_info(giso_web_auth)").fetchall()}
                for col_name, stmt in (
                    ('referral_code', "ALTER TABLE giso_web_auth ADD COLUMN referral_code TEXT DEFAULT ''"),
                    ('referred_by_code', "ALTER TABLE giso_web_auth ADD COLUMN referred_by_code TEXT DEFAULT ''"),
                    ('referred_by_user_id', "ALTER TABLE giso_web_auth ADD COLUMN referred_by_user_id INTEGER DEFAULT 0"),
                ):
                    if col_name not in rcols:
                        try:
                            conn.execute(stmt)
                        except Exception as e:
                            logger.warning(f"migrate giso_web_auth add referral col {col_name}: {e}")
                conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS ux_giso_web_auth_referral_code ON giso_web_auth(referral_code) WHERE referral_code != ''")
            except Exception as e:
                logger.warning(f"migrate giso_web_auth referral cols: {e}")

            # ۱۵-ب. فاز 4.5: ستون‌های بن کاربر در giso_web_auth
            try:
                bcols = {r[1] for r in conn.execute("PRAGMA table_info(giso_web_auth)").fetchall()}
                for col_name, stmt in (
                    ('is_banned', "ALTER TABLE giso_web_auth ADD COLUMN is_banned INTEGER DEFAULT 0"),
                    ('ban_reason', "ALTER TABLE giso_web_auth ADD COLUMN ban_reason TEXT DEFAULT ''"),
                ):
                    if col_name not in bcols:
                        try:
                            conn.execute(stmt)
                        except Exception as e:
                            logger.warning(f"migrate giso_web_auth add {col_name}: {e}")
            except Exception as e:
                logger.warning(f"migrate giso_web_auth ban cols: {e}")

            # ۱۵-ج. فاز 4.6: ستون status روی reviews
            try:
                rtables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
                if 'reviews' in rtables:
                    rcols = {r[1] for r in conn.execute("PRAGMA table_info(reviews)").fetchall()}
                    if 'status' not in rcols:
                        try:
                            conn.execute("ALTER TABLE reviews ADD COLUMN status TEXT DEFAULT 'visible'")
                        except Exception as e:
                            logger.warning(f"migrate reviews add status: {e}")
            except Exception as e:
                logger.warning(f"migrate reviews status: {e}")

            # ۱۶. جدول referrals (معرفی‌ها)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS referrals (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    referrer_user_id INTEGER NOT NULL,
                    referred_user_id INTEGER NOT NULL,
                    referral_code TEXT DEFAULT '',
                    referred_phone TEXT DEFAULT '',
                    status TEXT DEFAULT 'registered',
                    hair_order_id INTEGER DEFAULT 0,
                    sale_amount TEXT DEFAULT '',
                    commission_percent INTEGER DEFAULT 0,
                    commission_amount INTEGER DEFAULT 0,
                    created_at TEXT DEFAULT '',
                    updated_at TEXT DEFAULT '',
                    notes TEXT DEFAULT ''
                )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_referrals_referrer ON referrals(referrer_user_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_referrals_referred ON referrals(referred_user_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_referrals_phone ON referrals(referred_phone)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_referrals_status ON referrals(status)")

            # ۱۷. جدول wallet_transactions (تراکنش‌های کیف پول)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS wallet_transactions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    kind TEXT DEFAULT 'commission',
                    amount INTEGER DEFAULT 0,
                    status TEXT DEFAULT 'available',
                    source_type TEXT DEFAULT '',
                    source_id INTEGER DEFAULT 0,
                    description TEXT DEFAULT '',
                    created_at TEXT DEFAULT ''
                )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_wallet_tx_user ON wallet_transactions(user_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_wallet_tx_status ON wallet_transactions(status)")
            # دفترکل واحد: migration افزایشی؛ سوابق قدیمی نقدی محسوب می‌شوند.
            wallet_cols = {r[1] for r in conn.execute("PRAGMA table_info(wallet_transactions)").fetchall()}
            if 'balance_scope' not in wallet_cols:
                conn.execute("ALTER TABLE wallet_transactions ADD COLUMN balance_scope TEXT NOT NULL DEFAULT 'cash'")
            if 'idempotency_key' not in wallet_cols:
                conn.execute("ALTER TABLE wallet_transactions ADD COLUMN idempotency_key TEXT DEFAULT ''")
            conn.execute("UPDATE wallet_transactions SET balance_scope='cash' WHERE balance_scope IS NULL OR balance_scope='' OR balance_scope NOT IN ('cash','spend')")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_wallet_tx_scope ON wallet_transactions(user_id, balance_scope)")
            conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS ux_wallet_tx_idempotency ON wallet_transactions(idempotency_key) WHERE idempotency_key != ''")

            # ۱۷-ب. درخواست شارژ و مأموریت‌های کیف پول (کاملاً افزایشی)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS wallet_topup_requests (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    amount INTEGER DEFAULT 0,
                    payment_reference TEXT DEFAULT '',
                    receipt_path TEXT DEFAULT '',
                    user_note TEXT DEFAULT '',
                    status TEXT DEFAULT 'pending',
                    admin_note TEXT DEFAULT '',
                    created_at TEXT DEFAULT '',
                    reviewed_at TEXT DEFAULT '',
                    reviewed_by_user_id INTEGER DEFAULT 0,
                    FOREIGN KEY(user_id) REFERENCES giso_web_auth(id)
                )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_wallet_topup_user ON wallet_topup_requests(user_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_wallet_topup_status ON wallet_topup_requests(status)")
            topup_cols = {r[1] for r in conn.execute("PRAGMA table_info(wallet_topup_requests)").fetchall()}
            if 'receipt_path' not in topup_cols:
                conn.execute("ALTER TABLE wallet_topup_requests ADD COLUMN receipt_path TEXT DEFAULT ''")
            conn.execute("""
                CREATE TABLE IF NOT EXISTS wallet_missions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    code TEXT NOT NULL UNIQUE,
                    title TEXT DEFAULT '',
                    description TEXT DEFAULT '',
                    reward_amount INTEGER DEFAULT 0,
                    reward_scope TEXT DEFAULT 'spend',
                    is_active INTEGER DEFAULT 1,
                    is_deleted INTEGER DEFAULT 0,
                    sort_order INTEGER DEFAULT 0,
                    created_at TEXT DEFAULT '',
                    updated_at TEXT DEFAULT ''
                )
            """)
            mission_cols = {r[1] for r in conn.execute("PRAGMA table_info(wallet_missions)").fetchall()}
            if 'is_deleted' not in mission_cols:
                conn.execute("ALTER TABLE wallet_missions ADD COLUMN is_deleted INTEGER DEFAULT 0")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_wallet_mission_active ON wallet_missions(is_active, is_deleted, sort_order)")
            conn.execute("""
                CREATE TABLE IF NOT EXISTS wallet_mission_tombstones (
                    code TEXT PRIMARY KEY,
                    deleted_at TEXT DEFAULT ''
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS wallet_mission_completions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    mission_id INTEGER NOT NULL,
                    user_id INTEGER NOT NULL,
                    event_key TEXT DEFAULT '',
                    reward_amount INTEGER DEFAULT 0,
                    reward_scope TEXT DEFAULT 'spend',
                    reward_transaction_id INTEGER,
                    completed_at TEXT DEFAULT '',
                    UNIQUE(mission_id, user_id),
                    FOREIGN KEY(mission_id) REFERENCES wallet_missions(id),
                    FOREIGN KEY(user_id) REFERENCES giso_web_auth(id),
                    FOREIGN KEY(reward_transaction_id) REFERENCES wallet_transactions(id)
                )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_wallet_completion_user ON wallet_mission_completions(user_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_wallet_completion_mission ON wallet_mission_completions(mission_id)")
            mission_now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            mission_defaults = (
                ('registration', 'ثبت‌نام موفق', 'ساخت موفق حساب کاربری گیسو', 10000, 10),
                ('first_purchase', 'اولین خرید موفق', 'ثبت موفق اولین سفارش فروشگاه', 20000, 20),
                ('profile_complete', 'تکمیل پروفایل', 'ثبت نام و نام خانوادگی در حساب کاربری', 10000, 30),
                ('beauty_center_published', 'انتشار اولین مرکز زیبایی', 'تأیید و انتشار اولین مرکز توسط مدیریت', 30000, 120),
                ('product_explorer', 'مشاهده واقعی محصولات', 'مشاهده حداقل سه محصول متفاوت در بازه معتبر', 50000, 130),
                ('bale_connected', 'اتصال معتبر حساب بله', 'اشتراک شماره و اتصال حساب بله به حساب سایت', 20000, 140),
                ('bug_report_approved', 'گزارش باگ تأییدشده', 'تأیید دستی یک گزارش باگ مفید توسط سوپرادمین', 30000, 150),
            )
            for code, title, description, reward, sort_order in mission_defaults:
                # حذف صریح مأموریت (حتی built-in) باید در startup بعدی حفظ شود.
                tombstoned = conn.execute(
                    "SELECT 1 FROM wallet_mission_tombstones WHERE code=?", (code,)
                ).fetchone()
                if not tombstoned:
                    conn.execute(
                        "INSERT INTO wallet_missions "
                        "(code,title,description,reward_amount,reward_scope,is_active,is_deleted,sort_order,created_at,updated_at) "
                        "VALUES (?,?,?,?, 'spend',1,0,?,?,?) ON CONFLICT DO NOTHING",
                        (code, title, description, reward, sort_order, mission_now, mission_now),
                    )

            # ── مرحله ۲ پنل کاربر: ستون‌های امتیاز مأموریت + دفتر رتبه (کاملاً افزایشی) ──
            # reward_points: امتیاز رتبه‌بندی (مستقل از reward_amount که اعتبار تومانی است)
            mission_cols2 = {r[1] for r in conn.execute("PRAGMA table_info(wallet_missions)").fetchall()}
            if 'reward_points' not in mission_cols2:
                conn.execute("ALTER TABLE wallet_missions ADD COLUMN reward_points INTEGER NOT NULL DEFAULT 0")
            if 'mission_type' not in mission_cols2:
                conn.execute("ALTER TABLE wallet_missions ADD COLUMN mission_type TEXT NOT NULL DEFAULT 'once'")
            # مقدار پیش‌فرض امتیاز برای مأموریت‌های built-in که از قبل INSERT شده‌اند (fallback)
            _mission_point_defaults = {
                'registration': 10, 'first_purchase': 20, 'profile_complete': 10,
                'beauty_center_published': 40, 'product_explorer': 50,
                'bale_connected': 20, 'bug_report_approved': 60,
            }
            for _mcode, _mpts in _mission_point_defaults.items():
                conn.execute(
                    "UPDATE wallet_missions SET reward_points=? WHERE code=? AND COALESCE(reward_points,0)=0",
                    (_mpts, _mcode),
                )
            # دفتر رتبه‌ی کاربران: برای تشخیص تغییر رتبه و واریز روزانه (مرحله بعد) استفاده می‌شود.
            conn.execute("""
                CREATE TABLE IF NOT EXISTS user_ranks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    rank_level INTEGER DEFAULT 4,
                    rank_name TEXT DEFAULT 'برنزی',
                    score INTEGER DEFAULT 0,
                    daily_credit INTEGER DEFAULT 0,
                    last_credit_date TEXT DEFAULT '',
                    updated_at TEXT DEFAULT '',
                    UNIQUE(user_id),
                    FOREIGN KEY(user_id) REFERENCES giso_web_auth(id)
                )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_user_ranks_level ON user_ranks(rank_level)")

            # ۱۸. جدول withdrawal_requests (درخواست‌های تسویه)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS withdrawal_requests (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    amount INTEGER DEFAULT 0,
                    card_holder_name TEXT DEFAULT '',
                    card_number TEXT DEFAULT '',
                    sheba TEXT DEFAULT '',
                    status TEXT DEFAULT 'pending',
                    admin_note TEXT DEFAULT '',
                    created_at TEXT DEFAULT '',
                    updated_at TEXT DEFAULT ''
                )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_withdraw_user ON withdrawal_requests(user_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_withdraw_status ON withdrawal_requests(status)")

            try:
                from giso.hair_sale import init_hair_tables
                init_hair_tables(conn)
            except Exception:
                pass

            conn.commit()
        finally:
            conn.close()
    except Exception as e:
        logger.warning(f"migrate_giso_tables error: {e}")
# Phase 2.5 Indexes: proposed indexes on user_id/status/created_at (not executed to avoid risk)
# Phase 5.3 Read Status: verify DB read_status update on click
