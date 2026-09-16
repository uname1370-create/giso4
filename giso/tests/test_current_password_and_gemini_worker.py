# -*- coding: utf-8 -*-
"""تست‌های منبعی: خزانهٔ رمز فعلی + ورکر Gemini (بدون Flask)."""
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


class SealRoundtrip(unittest.TestCase):
    def test_seal_unseal(self):
        from giso.account_password_vault import seal_password, unseal_password
        secret = b"unit-test-secret-key"
        blob = seal_password("رمز-فعلی-1370", secret)
        self.assertTrue(blob.startswith("v1."))
        self.assertNotIn("1370", blob)
        self.assertEqual(unseal_password(blob, secret), "رمز-فعلی-1370")

    def test_wrong_secret_yields_empty(self):
        from giso.account_password_vault import seal_password, unseal_password
        blob = seal_password("secret-pass", b"aaa")
        self.assertEqual(unseal_password(blob, b"bbb"), "")

    def test_legacy_plaintext_passthrough(self):
        from giso.account_password_vault import unseal_password
        self.assertEqual(unseal_password("plain-old", b"any"), "plain-old")

    def test_stale_candidate_does_not_match_empty_hash(self):
        from giso.account_password_vault import current_password_if_matches
        self.assertEqual(current_password_if_matches("", "admin-set"), "")


class GeminiWorkerUrl(unittest.TestCase):
    def test_googleapis_rewritten_to_worker(self):
        from giso.ai_brain import (
            GEMINI_DEFAULT_BASE_URL, _effective_base_url, _normalize_gemini_base_url,
        )
        google = "https://generativelanguage.googleapis.com/v1beta/openai"
        self.assertEqual(_normalize_gemini_base_url(google), GEMINI_DEFAULT_BASE_URL)
        self.assertEqual(_normalize_gemini_base_url(""), GEMINI_DEFAULT_BASE_URL)
        with patch("giso.ai_brain._gemini_env_root", return_value=""):
            self.assertEqual(_effective_base_url("gemini", google), GEMINI_DEFAULT_BASE_URL)
            self.assertEqual(_effective_base_url("groq", google), google.rstrip("/"))

    def test_custom_worker_kept(self):
        from giso.ai_brain import _normalize_gemini_base_url
        custom = "https://sadeghiai.uname1370.workers.dev/v1beta/openai"
        self.assertEqual(_normalize_gemini_base_url(custom), custom)


class WorkerModeSummary(unittest.TestCase):
    def test_status_summary_keeps_worker(self):
        from giso import gemini_proxy_manager as pm
        data = {
            "proxy_mode": "worker",
            "manual_proxies": "[]",
            "working_proxies": "[]",
            "last_checked": "—",
            "source_url": pm.DEFAULT_PROXY_SOURCE,
            "worker_base_url": pm.DEFAULT_WORKER_URL,
        }
        with patch.object(pm, "_get_all_settings", return_value=data), \
             patch.object(pm, "get_active_proxy", return_value=None):
            summary = pm.status_summary()
        self.assertEqual(summary["mode"], "worker")
        self.assertTrue(summary["is_worker"])
        self.assertIn("workers.dev", summary["worker_url"])


if __name__ == "__main__":
    os.environ.setdefault("SECRET_KEY", "test-secret")
    unittest.main()
