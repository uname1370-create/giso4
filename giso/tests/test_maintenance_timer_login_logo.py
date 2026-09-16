# -*- coding: utf-8 -*-
"""رگرسیون کار ۱ و ۲ دستورالعمل صفحهٔ به‌روزرسانی + صفحهٔ ورود.

پوشش:
  - صفحهٔ به‌روزرسانی: ۵۰۳، اسپینر، تصویر سفارشی/پیش‌فرض، تایمر فقط با مدت>۰
  - عبور استاتیک و مسیر ورود حین به‌روزرسانی (رفتار قبلی حفظ شود)
  - ثبت/پاک‌شدن زمان شروع تایمر در گذار روشن→خاموش
  - صفحهٔ ورود دوستونه: لوگو (پیش‌فرض برند)، تاگل نمایش رمز، فیلدهای امن
  - ثبت‌نام: پوستهٔ جدید + حفظ همهٔ فیلدهای فرم
"""
import os
import re
import sys
import time
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from giso.app import create_app  # noqa: E402
from giso import app as appmod  # noqa: E402
from giso.base import get_bot_db_conn  # noqa: E402


def _set_setting(key, value):
    conn = get_bot_db_conn()
    try:
        conn.execute(
            "INSERT INTO settings (key, value) VALUES (?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value", (key, str(value)))
        conn.commit()
    finally:
        conn.close()


def _get_setting(key):
    conn = get_bot_db_conn()
    try:
        row = conn.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
        return row[0] if row else None
    finally:
        conn.close()


class MaintenanceTimerAndLoginLogoTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = create_app()
        cls.app.config["WTF_CSRF_ENABLED"] = False
        cls.client = cls.app.test_client()

    def setUp(self):
        _set_setting("giso_maintenance", "off")
        _set_setting("giso_maintenance_duration", "0")
        appmod._BOT_FLAG_CACHE.clear()

    @classmethod
    def tearDownClass(cls):
        _set_setting("giso_maintenance", "off")
        _set_setting("giso_maintenance_duration", "0")
        conn = get_bot_db_conn()
        try:
            conn.execute("DELETE FROM settings WHERE key='giso_maintenance_started_at'")
            conn.commit()
        finally:
            conn.close()
        # کش ده‌ثانیه‌ای فلگ حتماً پاک شود تا تست‌های بعدیِ همین پروسس
        # مقدار «روشن» مانده از آخرین تست را نبینند (ضد تداخل بین‌تستی).
        appmod._BOT_FLAG_CACHE.clear()

    # ── صفحهٔ به‌روزرسانی ──
    def test_maintenance_503_without_timer_when_duration_zero(self):
        _set_setting("giso_maintenance", "on")
        appmod._BOT_FLAG_CACHE.clear()
        r = self.client.get("/")
        self.assertEqual(r.status_code, 503)
        body = r.get_data(as_text=True)
        self.assertIn("spinner", body)
        self.assertIn("maintenance_custom.webp", body)  # fallback با onerror به پیش‌فرض
        self.assertIn("maintenance-default.svg", body)
        self.assertNotIn("gisoMaintTimer", body)

    def test_maintenance_timer_rendered_when_duration_set(self):
        _set_setting("giso_maintenance", "on")
        _set_setting("giso_maintenance_duration", "15")
        appmod._BOT_FLAG_CACHE.clear()
        r = self.client.get("/")
        self.assertEqual(r.status_code, 503)
        body = r.get_data(as_text=True)
        self.assertIn("gisoMaintTimer", body)
        m = re.search(r'data-until="(\d+)"', body)
        self.assertIsNotNone(m)
        until = int(m.group(1))
        self.assertLessEqual(14 * 60, until - time.time())
        self.assertLessEqual(until - time.time(), 15 * 60 + 5)
        # started_at ذخیره شده است
        self.assertTrue(_get_setting("giso_maintenance_started_at"))

    def test_static_and_login_stay_open_during_maintenance(self):
        _set_setting("giso_maintenance", "on")
        appmod._BOT_FLAG_CACHE.clear()
        self.assertEqual(self.client.get("/static/css/style.css").status_code, 200)
        self.assertEqual(self.client.get("/login").status_code, 200)

    def test_off_transition_clears_started_at(self):
        _set_setting("giso_maintenance", "on")
        _set_setting("giso_maintenance_duration", "5")
        appmod._BOT_FLAG_CACHE.clear()
        self.assertEqual(self.client.get("/").status_code, 503)
        self.assertTrue(_get_setting("giso_maintenance_started_at"))
        # گذار روشن→خاموش با کش منقضی (رفتار واقعی)
        _set_setting("giso_maintenance", "off")
        appmod._BOT_FLAG_CACHE["giso_maintenance"] = (True, time.time() - 20)
        self.assertEqual(self.client.get("/").status_code, 200)
        self.assertIsNone(_get_setting("giso_maintenance_started_at"))

    def test_invalid_duration_falls_back_to_no_timer(self):
        _set_setting("giso_maintenance", "on")
        _set_setting("giso_maintenance_duration", "999")  # خارج از گزینه‌های مجاز
        appmod._BOT_FLAG_CACHE.clear()
        r = self.client.get("/")
        self.assertEqual(r.status_code, 503)
        self.assertNotIn("gisoMaintTimer", r.get_data(as_text=True))

    # ── صفحهٔ ورود/ثبت‌نام ──
    def test_login_two_column_layout_with_brand_logo(self):
        r = self.client.get("/login")
        self.assertEqual(r.status_code, 200)
        body = r.get_data(as_text=True)
        self.assertIn("giso-auth-wrapper", body)
        self.assertIn("giso-auth-hero", body)
        self.assertIn("giso-auth-logo-img", body)
        self.assertIn("images/logo-96.webp", body)  # پیش‌فرض: لوگوی برند
        self.assertIn("giso-pw-toggle", body)
        self.assertIn('name="phone"', body)
        self.assertIn('name="password"', body)
        self.assertIn("csrf", body)
        self.assertIn('minlength="4"', body)

    def test_register_keeps_new_shell_and_all_fields(self):
        r = self.client.get("/register")
        self.assertEqual(r.status_code, 200)
        body = r.get_data(as_text=True)
        self.assertIn("giso-auth-wrapper", body)
        for needle in ("security_question", "security_answer", "site_terms_accepted",
                       "password2", "action"):
            self.assertIn(f'name="{needle}"', body)


if __name__ == "__main__":
    unittest.main()
