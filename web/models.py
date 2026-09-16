# -*- coding: utf-8 -*-
"""
مدل‌های وب‌سایت اصلی

- مدل User روی جدول هستهٔ users ربات می‌نشیند (داده مشترک با ربات).
- جدول‌های احراز هویت با پیشوند web_identity_* در همان دیتابیس اصلی (bot.db)
  ساخته می‌شوند — بنابراین وب و ربات یک هویت مشترک دارند ولی جدول‌های هسته
  دست‌نخورده باقی می‌مانند.
- وضعیت onboarding یار همراه من (AI mentor) در جدول web_identity_career_state
  ذخیره می‌شود (از طریق سرویس مشترک mentor_service خوانده/نوشته می‌شود).
"""
from datetime import datetime
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin

db = SQLAlchemy()


class User(UserMixin, db.Model):
    """مدل کاربر سایت — نگاشتی روی جدول users ربات."""
    __tablename__ = 'users'

    id = db.Column('user_id', db.Integer, primary_key=True)
    first_name = db.Column(db.String(100), default='')
    username = db.Column(db.String(100), default='')
    phone = db.Column(db.String(20), default='', index=True)
    joined = db.Column(db.Integer, default=0)
    last_active = db.Column(db.Integer, default=0)
    credits = db.Column(db.Integer, default=0)
    points = db.Column(db.Integer, default=0)
    xp = db.Column(db.Integer, default=0)
    is_banned = db.Column(db.Integer, default=0)
    is_muted = db.Column(db.Integer, default=0)
    mute_until = db.Column(db.Integer, default=0)
    referrer = db.Column(db.Integer)

    def get_id(self):
        """شناسه Flask-Login از phone نرمال استفاده می‌کند."""
        return str(self.phone or self.id)

    @property
    def is_main_admin(self):
        """ادمین وب‌سایت آموزشی — فقط بر اساس شماره موبایل در SITE_ADMIN_PHONES.
        هیچ ارتباطی با ADMIN_IDS ربات یا با نقش گیسو ندارد.
        تشخیص به‌شکل ثابت و از روی متغیر ایستا انجام می‌شود تا حتی در خارج از
        اپ-کانتکست فلاسک هم درست کار کند."""
        try:
            from web.config import Config as _WebCfg
            return bool(self.phone and self.phone in getattr(_WebCfg, "SITE_ADMIN_PHONES", []))
        except Exception:
            try:
                from config import Config as _WebCfg
                return bool(self.phone and self.phone in getattr(_WebCfg, "SITE_ADMIN_PHONES", []))
            except Exception:
                return False

    def touch_login(self):
        import time as _time
        self.last_active = int(_time.time())
        try:
            db.session.commit()
        except Exception:
            db.session.rollback()


class WebIdentityAuth(db.Model):
    """جدول احراز هویت وب — رمز عبور هش‌شده + سوال امنیتی."""
    __tablename__ = 'web_identity_auth'

    id = db.Column(db.Integer, primary_key=True)
    phone = db.Column(db.String(20), unique=True, nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.user_id'), nullable=True, index=True)
    password_hash = db.Column(db.String(256), nullable=False)
    security_q_key = db.Column(db.String(50), nullable=False, default='')
    security_answer_hash = db.Column(db.String(256), nullable=False, default='')
    created_at = db.Column(db.String(50), default=lambda: datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
    last_login = db.Column(db.String(50), default='')


class WebIdentityCareerState(db.Model):
    """وضعیت onboarding و چت یار همراه من (وب) برای هر کاربر."""
    __tablename__ = 'web_identity_career_state'

    id = db.Column(db.Integer, primary_key=True)
    phone = db.Column(db.String(20), default='', index=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.user_id'), nullable=False, unique=True, index=True)
    onboarding_completed = db.Column(db.Boolean, default=False)
    career_goal = db.Column(db.String(300), default='')
    experience_level = db.Column(db.String(50), default='')
    daily_hours = db.Column(db.Integer, default=0)
    career_purpose = db.Column(db.String(100), default='')
    current_step = db.Column(db.Integer, default=1)
    chat_history = db.Column(db.Text, default='[]')
    mentor_data = db.Column(db.Text, default='{}')
    updated_at = db.Column(db.String(50), default=lambda: datetime.now().strftime('%Y-%m-%d %H:%M:%S'))


class ConsultantRequest(db.Model):
    """درخواست مشاوره انسانی سایت برای مسیر منتور."""
    __tablename__ = 'consultant_requests'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.user_id'), nullable=False, index=True)
    name = db.Column(db.String(120), default='')
    phone = db.Column(db.String(30), default='', index=True)
    city = db.Column(db.String(120), default='')
    main_problem = db.Column(db.Text, default='')
    selected_route_title = db.Column(db.String(300), default='')
    intro_message = db.Column(db.Text, default='')
    status = db.Column(db.String(30), default='pending', index=True)
    last_turn = db.Column(db.String(20), default='')
    free_user_messages_used = db.Column(db.Integer, default=0)
    paused_at = db.Column(db.String(50), default='')
    resumed_at = db.Column(db.String(50), default='')
    admin_chat_id = db.Column(db.String(50), default='')
    created_at = db.Column(db.String(50), default=lambda: datetime.now().strftime('%Y-%m-%d %H:%M:%S'), index=True)
    approved_at = db.Column(db.String(50), default='')
    closed_at = db.Column(db.String(50), default='')


class ConsultantMessage(db.Model):
    """پیام‌های سایت بین کاربر و ادمین برای یک درخواست مشاوره."""
    __tablename__ = 'consultant_messages'

    id = db.Column(db.Integer, primary_key=True)
    request_id = db.Column(db.Integer, db.ForeignKey('consultant_requests.id'), nullable=False, index=True)
    sender = db.Column(db.String(20), default='user', index=True)
    text = db.Column(db.Text, default='')
    created_at = db.Column(db.String(50), default=lambda: datetime.now().strftime('%Y-%m-%d %H:%M:%S'), index=True)
