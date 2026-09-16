# -*- coding: utf-8 -*-
"""
panel_service.py — ساختار منبع واحد (source of truth) برای همهٔ پنل‌های منو

وب و ربات هر دو از این سرویس استفاده می‌کنند تا دکمه‌ها و سکشن‌ها همیشه با هم
هم‌راستا باشند. هر section دارای کلید، آیکون، برچسب فارسی، توضیح، مسیر وب/بات
و پرچم دسترسی است.

دسترسی‌ها:
  - public     → بدون ورود (فقط صفحه اصلی و /tools)
  - auth       → نیاز به ورود (برای همه کاربران واردشده)
  - user       → پنل کاربری عادی (همه کاربران واردشده و غیرادمین)
  - mentor     → مخصوص حوزهٔ «یار همراه من»
  - admin      → فقط ادمین وب‌سایت آموزشی (تطابق شماره با SITE_ADMIN_PHONES)
  - bot_admin  → مخصوص ادمین ربات (ADMIN_IDS)

فیلدهای هر آیتم:
  key         کلید یکتا
  icon        آیکون fontawesome (یا اموجی برای منوی بات)
  label       متن نمایشی فارسی
  desc        توضیح کوتاه
  route       مسیر وب (مثلاً /courses یا /admin/courses)
  bot_cb      callback_data در ربات (مثلاً courses / a_panel / ...)
  access      یکی از دسترسی‌های بالا
  web_ready   True یعنی صفحهٔ وب کامل پیاده‌سازی شده
  group       دسته‌بندی (public/home/user/mentor/admin/bot_admin)
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import List, Optional


@dataclass
class PanelItem:
    key: str
    label: str
    icon: str = ""
    desc: str = ""
    route: str = ""
    bot_cb: str = ""
    access: str = "user"        # public / auth / user / mentor / admin
    group: str = "user"         # public / user / mentor / admin
    web_ready: bool = True
    bot_only: bool = False

    def to_dict(self) -> dict:
        return asdict(self)


# ---------- Public (before login) ----------
PUBLIC_ITEMS: List[PanelItem] = [
    PanelItem(key="home", label="خانه", icon="fas fa-home", route="/",
              access="public", group="public"),
    PanelItem(key="tools", label="ابزارها", icon="fas fa-tools", route="/tools",
              access="public", group="public"),
]


# ---------- User panel (normal non-admin user) ----------
# mirrors bot's main_kb (non-admin): courses, profile, missions, shop, events, referral, support
USER_PANEL_ITEMS: List[PanelItem] = [
    PanelItem(key="dashboard", label="پیشخوان", icon="fas fa-chart-line", route="/dashboard",
              bot_cb="main", access="user", group="user"),
    PanelItem(key="courses", label="دوره‌های آموزشی", icon="fas fa-book", route="/courses",
              bot_cb="courses", access="user", group="user"),
    PanelItem(key="missions", label="ماموریت‌ها", icon="fas fa-bullseye", route="/missions",
              bot_cb="missions", access="user", group="user"),
    PanelItem(key="shop", label="گنجینه امتیازی", icon="fas fa-gem", route="/shop",
              bot_cb="shop", access="user", group="user"),
    PanelItem(key="latest_events", label="آخرین اتفاقات", icon="fas fa-newspaper", route="/",
              bot_cb="latest_events", access="user", group="user",
              web_ready=False, bot_only=True, desc="در حال حاضر از داخل ربات پیگیری کنید."),
    PanelItem(key="referral", label="دعوت دوستان", icon="fas fa-user-plus", route="/",
              bot_cb="referral", access="user", group="user",
              web_ready=False, bot_only=True, desc="سیستم دعوت از داخل ربات فعال است."),
    PanelItem(key="support", label="پشتیبانی", icon="fas fa-headset", route="/support",
              bot_cb="support", access="user", group="user"),
    PanelItem(key="profile", label="پروفایل کاربری", icon="fas fa-user-circle", route="/profile",
              bot_cb="profile", access="user", group="user"),
]


# ---------- Mentor (یار همراه من) — career/smart domain ONLY ----------
MENTOR_ITEMS: List[PanelItem] = [
    PanelItem(key="mentor_dashboard", label="داشبورد یار همراه من",
              icon="fas fa-robot", route="/mentor",
              bot_cb="aim_menu", access="mentor", group="mentor"),
    PanelItem(key="mentor_chat", label="گفتگو با یار هوشمند",
              icon="fas fa-comments", route="/mentor#chat",
              access="mentor", group="mentor"),
    PanelItem(key="mentor_profile", label="پروفایل شغلی من",
              icon="fas fa-user-tie", route="/mentor/profile",
              access="mentor", group="mentor"),
    PanelItem(key="mentor_path", label="نقشهٔ راه اختصاصی",
              icon="fas fa-route", route="/mentor/path",
              bot_cb="aim_path", access="mentor", group="mentor", web_ready=False),
    PanelItem(key="mentor_trends", label="ترندهای بازار کار",
              icon="fas fa-chart-column", route="/mentor/trends",
              bot_cb="aim_trends", access="mentor", group="mentor", web_ready=False),
    PanelItem(key="mentor_interview", label="شبیه‌ساز مصاحبه",
              icon="fas fa-microphone", route="/mentor/interview",
              bot_cb="aim_interview", access="mentor", group="mentor", web_ready=False),
    PanelItem(key="mentor_certs", label="گواهینامه‌های من",
              icon="fas fa-certificate", route="/mentor/certs",
              access="mentor", group="mentor"),
]


# ---------- Site admin (educational website admin = SITE_ADMIN_PHONES) ----------
# mirrors bot's admin_panel keys but for web.
SITE_ADMIN_ITEMS: List[PanelItem] = [
    PanelItem(key="admin_home", label="پیشخوان مدیریت", icon="fas fa-crown",
              route="/admin", access="admin", group="admin"),
    PanelItem(key="admin_courses", label="مدیریت دوره‌ها", icon="fas fa-book-open",
              route="/admin/courses", bot_cb="a_courses_menu",
              access="admin", group="admin"),
    PanelItem(key="admin_missions", label="مدیریت ماموریت‌ها", icon="fas fa-bullseye",
              route="/admin/missions", bot_cb="a_missions",
              access="admin", group="admin"),
    PanelItem(key="admin_shop", label="مدیریت گنجینه", icon="fas fa-gem",
              route="/admin/shop", bot_cb="a_shop",
              access="admin", group="admin"),
    PanelItem(key="admin_users", label="مدیریت کاربران", icon="fas fa-users-cog",
              route="/admin/users", bot_cb="a_users_manage",
              access="admin", group="admin"),
    PanelItem(key="admin_feature_access", label="دسترسی بخش‌ها", icon="fas fa-key",
              route="/admin/features", bot_cb="a_feature_access",
              access="admin", group="admin", web_ready=False,
              desc="در حال حاضر از ربات مدیریت می‌شود."),
    PanelItem(key="admin_cash", label="درخواست‌های خرید نقدی", icon="fas fa-money-bill-wave",
              route="/admin/cash", bot_cb="a_cash_sales",
              access="admin", group="admin"),
    PanelItem(key="admin_reports", label="گزارشات و آمار", icon="fas fa-chart-bar",
              route="/admin/reports", bot_cb="a_reports",
              access="admin", group="admin"),
    PanelItem(key="admin_messaging", label="مرکز پیام‌رسانی", icon="fas fa-bullhorn",
              route="/admin/messaging", bot_cb="a_messaging",
              access="admin", group="admin"),
    PanelItem(key="admin_ai", label="مدیریت یار هوشمند", icon="fas fa-brain",
              route="/admin/ai", bot_cb="aim_a_menu",
              access="admin", group="admin", web_ready=False,
              desc="بخش AI از پنل ربات مدیریت می‌شود."),
    PanelItem(key="admin_settings", label="تنظیمات عمومی", icon="fas fa-cog",
              route="/admin/settings", bot_cb="a_global_settings",
              access="admin", group="admin", web_ready=False,
              desc="تنظیمات پیشرفته از ربات اعمال می‌شوند."),
    PanelItem(key="admin_giso", label="مدیریت ربات گیسو", icon="fas fa-ribbon",
              route="/admin/giso", bot_cb="a_giso_management",
              access="admin", group="admin", web_ready=False,
              desc="تنظیمات گیسو از ربات اصلی مدیریت می‌شود."),
]


def public_items() -> List[PanelItem]:
    return list(PUBLIC_ITEMS)


def user_panel_items() -> List[PanelItem]:
    return list(USER_PANEL_ITEMS)


def mentor_items() -> List[PanelItem]:
    return list(MENTOR_ITEMS)


def site_admin_items() -> List[PanelItem]:
    return list(SITE_ADMIN_ITEMS)


def find_item(key: str) -> Optional[PanelItem]:
    for it in (PUBLIC_ITEMS + USER_PANEL_ITEMS + MENTOR_ITEMS + SITE_ADMIN_ITEMS):
        if it.key == key:
            return it
    return None
