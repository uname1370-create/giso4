#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""مرحلهٔ ۲ se.md / BUG-002 — تست ولیدیشن SSRF پایهٔ URL پراوایدر AI."""
import os
import sys
import unittest

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if BASE_DIR not in sys.path:
    sys.path.append(BASE_DIR)

from giso.ai_brain import _validate_base_url, save_provider_to_env  # noqa: E402

OK = [
    "",
    "https://api.openai.com/v1",
    "https://api.avalai.ir/v1",
    "https://sadeghiai.uname1370.workers.dev/v1beta/openai",
]
BAD = [
    "http://127.0.0.1",
    "http://127.0.0.1:8080/v1",
    "https://192.168.1.1",
    "https://10.0.0.5/v1",
    "https://172.16.0.1",
    "https://172.31.255.255",
    "https://169.254.169.254/latest/meta-data/",
    "https://localhost",
    "https://localhost:5000",
    "https://0.0.0.0",
    "https:://broken",
    "http://example.com",
    "ftp://example.com",
]


class SsrfBaseUrlTests(unittest.TestCase):
    def test_valid_urls_pass(self):
        for u in OK:
            _validate_base_url(u)  # نباید exception بدهد

    def test_internal_urls_rejected(self):
        for u in BAD:
            with self.assertRaises(ValueError, msg=u):
                _validate_base_url(u)

    def test_save_provider_rejects_ssrf_url(self):
        with self.assertRaises(ValueError):
            save_provider_to_env(
                name="evil", api_key="k", base_url="http://169.254.169.254",
                model="m",
            )


if __name__ == "__main__":
    unittest.main()
