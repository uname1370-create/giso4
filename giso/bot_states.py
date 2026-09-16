# -*- coding: utf-8 -*-
"""giso/bot_states.py — State و Callback Constants (مرکزی).

⚠️ اصلاح R9 (2026-08-14):
این فایل قبلاً الگوهایی داشت که با کد زنده و با `GISO_GUIDE.md` در تضاد بودند و
چون هیچ ماژولی آن را import نمی‌کرد، این تضاد بی‌صدا باقی مانده بود. اگر روزی
import می‌شد، صفحه‌بندی گزارش‌ها می‌شکست.

موارد اصلاح‌شده:
  • REPORT_PHONES: «hair_pg|rep|{scope}|{page}» ← الگوی نادرست، در runtime وجود نداشت.
    مقدار درست طبق GISO_GUIDE §۲۳.۳ و `bot_hair_admin.py:497` = «hair_rep|{scope}|{page}»
  • CHAT_LIST: «hair_pg|chat|{page}» حذف شد — هیچ handlerی برای آن ثبت نشده و
    GISO_GUIDE §۲۳.۴ هم صفحه‌بندی گفتگوها را الزام نکرده است.
  • Stateهای منویی که در رجیستری رسمی §۵.۱۲ نبودند (in_hair_admin_menu /
    in_hair_user_menu / in_hair_report_menu) حذف شدند و state واقعی
    `in_hair_status` که در کد استفاده می‌شود جایگزین شد.

همه مقادیر زیر با کد زنده راستی‌آزمایی شده‌اند. مرجع: GISO_GUIDE §۵.۱۱، §۵.۱۲، §۲۳.
"""


class HairStates:
    """State stringهای واقعی جریان فروش مو (مطابق GISO_GUIDE §۵.۱۲).

    Stateهای پارامتری با `_{order_id}` (و برای نظر با `_{order_id}_{rating}`)
    ادامه می‌یابند؛ مقادیر زیر «پیشوند» هستند، دقیقاً همان‌طور که کد با
    `state.startswith(...)` بررسی می‌کند.
    """

    # منوی وضعیت درخواست‌ها (تنها state منویی واقعی — bot.py:_admin_hair_status_kb)
    STATUS_MENU = "in_hair_status"

    # جستجو
    PHONE_SEARCH = "waiting_hair_phone_search"

    # ورودی‌های اکشن (پیشوند + شناسه سفارش)
    PRICE_INPUT = "waiting_hair_price"
    APPROVE_PRICE_INPUT = "waiting_hair_approve_price"
    NOTE_INPUT = "waiting_hair_note"
    ADMIN_MSG_INPUT = "waiting_admin_msg"
    USER_MSG_REPLY = "waiting_user_msg_reply"
    OBJECTION_INPUT = "waiting_hair_objection"

    # نظر و امتیاز (پیشوند + «_{order_id}_{rating}»)
    REVIEW_TEXT = "waiting_hair_rev_txt"

    # پورسانت (فقط سوپرادمین — bot.py)
    COMMISSION_PERCENT = "waiting_commission_percent"
    COMMISSION_FIXED = "waiting_commission_fixed"


class CallbackPatterns:
    """الگوهای callback زندهٔ فروش مو (مطابق GISO_GUIDE §۵.۱۱ و §۲۳)."""

    # صفحه‌بندی — GISO_GUIDE §۲۳.۱
    REQ_PAGE = "hair_pg|req|{idx}"
    USER_LIST = "hair_pg|usr|{idx}"
    USER_ORDERS = "hair_pg|uo|{phone}|{idx}"
    MENU_BACK = "hair_pg|menu"

    # گزارش‌ها — GISO_GUIDE §۲۳.۳ (ریشه `hair_rep`، نه `hair_pg|rep`)
    REPORT_PAGE = "hair_rep|{scope}|{page}"
    REPORT_MENU = "hair_rep|menu"
    REPORT_VIEW = "hair_rep_view|{scope}|{phone}"

    # اکشن‌های درخواست — GISO_GUIDE §۵.۱۱
    REVIEW = "hair_review|{order_id}"
    REJECT = "hair_rej|{order_id}"
    PRICE = "hair_price|{order_id}"
    NOTE = "hair_note|{order_id}"
    MESSAGE = "hair_msg|{order_id}"
    APPROVE = "hair_approve|{order_id}"
    COMPLETE = "hair_complete|{order_id}"

    # کاربر
    VIEW_MESSAGES = "hair_view_msgs|{order_id}"
    USER_REPLY = "hair_user_reply|{order_id}"
    OBJECTION = "hair_objection|{order_id}"
    REVIEW_SELECT = "hair_rev_sel|{order_id}"
    REVIEW_RATE = "hair_rev_rate|{order_id}|{rating}"

    # aliasهای legacy (هنوز در bot.py پذیرفته می‌شوند — deprecated)
    LEGACY_REVIEW = "hair_app|{order_id}"
    LEGACY_REJECT = "hair_reject|{order_id}"


class AdminPermissions:
    """کلیدهای زیرگزینه بخش فروش مو.

    منبع واحد حقیقت = `giso.bot_hair_admin.HAIR_SUBOPTIONS`.
    مقادیر اینجا صرفاً برای خوانایی‌اند و باید با آن هم‌گام بمانند.
    کلید نمایش در ربات: `bot_<key>_visible` (قرارداد فاز ۴۸).
    """

    APPROVE = "approve"
    REJECT = "reject"
    PRICE = "price"
    NOTE = "note"
    MESSAGE = "message"
    REPORTS = "reports"
    OBJECTIONS = "objections"
    COMMISSION = "commission"
    REVIEW = "review"  # افزوده در رفع R3

    @staticmethod
    def bot_visibility_key(subkey: str) -> str:
        return f"bot_{subkey}_visible"

    @staticmethod
    def site_visibility_key(subkey: str) -> str:
        return f"site_{subkey}_visible"


__all__ = ["HairStates", "CallbackPatterns", "AdminPermissions"]
