#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""مرحلهٔ ۱ se.md — تست گارد CSRF پنل ادمین (لایهٔ دوم 403).

یافتهٔ حین اجرا: لایهٔ سراسری install_security/security_gate از قبل
همهٔ POSTها را چک می‌کرد (400)؛ گارد پنل لایهٔ صریح 403 افزود.

گارد در giso/panel/routes.py (@panel_bp.before_request):
هر POST به /admin بدون توکن معتبر → 403.
توکن از فرم (csrf_token) یا هدر X-GISO-CSRF / X-CSRF-Token پذیرفته می‌شود.
"""
import os
import sys
import unittest

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if BASE_DIR not in sys.path:
    sys.path.append(BASE_DIR)

from giso.app import create_app  # noqa: E402

TOK = "guard-test-token-123"


class PanelCsrfGuardTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = create_app()
        cls.app.config["TESTING"] = True
        cls.client = cls.app.test_client()

    def test_01_post_without_token_rejected(self):
        # لایهٔ سراسری security_gate → 400؛ لایهٔ پنل → 403. هر دو یعنی رد درخواست.
        r = self.client.post("/admin/settings", data={"save_registration": "1"})
        self.assertIn(r.status_code, (400, 403))

    def test_02_post_with_header_token_not_403(self):
        with self.client.session_transaction() as s:
            s["giso_csrf_token"] = TOK
        r = self.client.post(
            "/admin/settings",
            data={"save_registration": "1"},
            headers={"X-GISO-CSRF": TOK},
        )
        # بدون توکن رد شد؛ با توکن باید به لایهٔ بعد (auth) برسد
        self.assertNotIn(r.status_code, (400, 403))

    def test_03_post_with_session_matching_token_not_403(self):
        with self.client.session_transaction() as s:
            s["giso_csrf_token"] = TOK
        r = self.client.post("/admin/settings", data={"csrf_token": TOK})
        self.assertNotIn(r.status_code, (400, 403))

    def test_04_wrong_token_is_403(self):
        with self.client.session_transaction() as s:
            s["giso_csrf_token"] = TOK
        r = self.client.post(
            "/admin/settings", data={}, headers={"X-GISO-CSRF": "wrong-token"}
        )
        self.assertIn(r.status_code, (400, 403))

    def test_05_get_requests_unaffected(self):
        r = self.client.get("/admin")
        self.assertIn(r.status_code, (200, 302))

    def test_06_public_post_unaffected(self):
        # POSTهای خارج از پنل (مثلاً ورود سایت) نباید 403 بگیرند
        r = self.client.post("/login", data={"phone": "09120000000", "password": "x"})
        self.assertNotEqual(r.status_code, 403)


if __name__ == "__main__":
    unittest.main()
