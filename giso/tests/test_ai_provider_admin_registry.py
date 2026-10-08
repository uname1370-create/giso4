# -*- coding: utf-8 -*-
"""Regression tests for the superadmin AI provider registry/database flow.

These tests use a temporary SQLite database and a temporary provider env file;
they never touch the repository or production database/configuration.
"""
from __future__ import annotations


def _isolate_provider_storage(tmp_path, monkeypatch):
    from giso import db_core
    import giso.ai_brain as brain

    from giso import ai_runtime

    monkeypatch.setattr(db_core, "GISO_DB_PATH", tmp_path / "giso-test.db")
    monkeypatch.setattr(brain, "_ENV_PATH", tmp_path / ".env")
    # ai_runtime caches its ready flag; keep that cache scoped to this temporary DB.
    monkeypatch.setattr(ai_runtime, "_RUNTIME_READY", False)
    brain.init_ai_tables()
    return brain


def test_all_registry_providers_are_seeded_and_listed(tmp_path, monkeypatch):
    brain = _isolate_provider_storage(tmp_path, monkeypatch)
    from giso.ai_models_registry import PROVIDERS
    from giso.ai_runtime import list_provider_options

    seeded = set(brain.seed_registry_providers())
    rows = brain.list_ai_providers()
    names = {str(row["name"]) for row in rows}
    assert set(PROVIDERS).issubset(names)
    assert set(PROVIDERS).issubset(seeded)
    assert all(not bool(brain.get_ai_provider(name)["enabled"]) for name in PROVIDERS)
    assert all(not str(brain.get_ai_provider(name)["api_key"] or "").strip() for name in PROVIDERS)

    grouped = list_provider_options()
    listed_names = {
        str(provider["name"])
        for bucket in grouped.values()
        for provider in (bucket or [])
    }
    assert set(PROVIDERS).issubset(listed_names)


def test_seed_provider_without_credentials_cannot_be_activated_from_panel(tmp_path, monkeypatch):
    brain = _isolate_provider_storage(tmp_path, monkeypatch)
    brain.seed_registry_providers()
    from flask import Flask
    from giso.panel.modules import ai as panel_ai

    app = Flask(__name__)
    app.secret_key = "test-only-session-key"
    monkeypatch.setattr(panel_ai, "_require_super", lambda: None)
    monkeypatch.setattr(panel_ai, "url_for", lambda *_args, **_kwargs: "/admin/ai")
    with app.test_request_context("/admin/ai/provider/groq/toggle", method="POST"):
        response = panel_ai.handle_provider_toggle("groq")
        assert response.status_code == 302

    assert not bool(brain.get_ai_provider("groq")["enabled"])


def test_deleted_registry_provider_stays_deleted_until_explicitly_readded(tmp_path, monkeypatch):
    brain = _isolate_provider_storage(tmp_path, monkeypatch)
    from giso.ai_models_registry import get_provider

    brain.seed_registry_providers()
    assert brain.get_ai_provider("groq") is not None
    brain.save_provider_to_env(
        name="groq", api_key="TEST_ONLY_PROVIDER_KEY", base_url=get_provider("groq")["base_url"],
        model="llama-3.3-70b-versatile", enabled=True,
    )

    from flask import Flask
    from giso.panel.modules import ai as panel_ai
    app = Flask(__name__)
    app.secret_key = "test-only-session-key"
    monkeypatch.setattr(panel_ai, "_require_super", lambda: None)
    monkeypatch.setattr(panel_ai, "url_for", lambda *_args, **_kwargs: "/admin/ai")
    with app.test_request_context(
        "/admin/ai/provider/groq/delete", method="POST", data={"step": "confirm"},
    ):
        response = panel_ai.handle_provider_delete("groq")
        assert response.status_code == 302
    assert brain.get_ai_provider("groq") is None
    assert "TEST_ONLY_PROVIDER_KEY" not in brain._ENV_PATH.read_text(encoding="utf-8")
    assert "groq" not in {provider["name"] for provider in brain.load_providers_from_env()}

    # Simulate a later bootstrap with an otherwise empty provider table.
    with brain.get_conn() as conn:
        conn.execute("DELETE FROM giso_ai_providers")
    brain.sync_env_providers_to_db()
    brain.seed_registry_providers()
    assert brain.get_ai_provider("groq") is None

    # An explicit add is an intentional restore and clears the tombstone.
    registry = get_provider("groq")
    assert brain.add_ai_provider(
        name="groq", kind=registry["kind"], api_key="TEST_ONLY_NEW_KEY",
        base_url=registry["base_url"], api_root=registry["api_root"],
        timeout=registry["timeout"], enabled=False, replace=True,
        vision_models_json="[]", text_models_json="[]", models_source="registry",
    ) is True
    brain.seed_registry_providers()
    assert brain.get_ai_provider("groq") is not None
    with brain.get_conn() as conn:
        tombstone = conn.execute(
            "SELECT 1 FROM giso_ai_provider_tombstones WHERE name='groq'"
        ).fetchone()
    assert tombstone is None


def test_superadmin_provider_endpoint_edit_keeps_cloudflare_urls_in_sync(tmp_path, monkeypatch):
    brain = _isolate_provider_storage(tmp_path, monkeypatch)
    from flask import Flask
    from giso.panel.modules import ai as panel_ai

    old_url = "https://api.cloudflare.com/client/v4/accounts/acct-old/ai/run"
    new_url = "https://api.cloudflare.com/client/v4/accounts/acct-new/ai/run"
    assert brain.add_ai_provider(
        name="cf1", kind="cloudflare", api_key="TEST_ONLY_CF_KEY",
        base_url=old_url, api_root=old_url, selected_model="@cf/meta/llama-3.2-11b-vision-instruct",
        enabled=True, replace=True,
    )

    app = Flask(__name__)
    app.secret_key = "test-only-session-key"
    monkeypatch.setattr(panel_ai, "_require_super", lambda: None)
    monkeypatch.setattr(panel_ai, "url_for", lambda *_args, **_kwargs: "/admin/ai")
    with app.test_request_context(
        "/admin/ai/provider/cf1/update", method="POST",
        data={"field": "base_url", "value": new_url},
    ):
        response = panel_ai.handle_provider_update("cf1")
        assert response.status_code == 302

    updated = brain.get_ai_provider("cf1")
    assert updated["base_url"] == new_url
    assert updated["api_root"] == new_url

    proxy_url = "socks5://proxy.example.test:1080"
    with app.test_request_context(
        "/admin/ai/provider/cf1/update", method="POST",
        data={"field": "proxy_url", "value": proxy_url},
    ):
        response = panel_ai.handle_provider_update("cf1")
        assert response.status_code == 302
    updated = brain.get_ai_provider("cf1")
    assert updated["proxy_url"] == proxy_url
    assert updated["proxy_type"] == "socks5"
    saved_env = next(provider for provider in brain.load_providers_from_env() if provider["name"] == "cf1")
    assert saved_env["proxy_url"] == proxy_url
    assert saved_env["proxy_type"] == "socks5"


def test_legacy_ai_credit_schema_is_migrated_before_panel_queries(tmp_path, monkeypatch):
    brain = _isolate_provider_storage(tmp_path, monkeypatch)
    brain.seed_registry_providers()
    from giso.base import get_giso_db_conn

    with get_giso_db_conn() as conn:
        conn.execute(
            "CREATE TABLE giso_ai_credit_ledger ("
            "id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL, "
            "delta INTEGER NOT NULL, balance_after INTEGER NOT NULL, reason TEXT DEFAULT '', "
            "channel TEXT DEFAULT '', request_key TEXT UNIQUE NOT NULL, actor TEXT DEFAULT '', "
            "created_at TEXT DEFAULT '')"
        )
        conn.execute(
            "CREATE TABLE giso_web_auth (id INTEGER PRIMARY KEY, phone TEXT DEFAULT '', "
            "name TEXT DEFAULT '', first_name TEXT DEFAULT '')"
        )
        conn.commit()

    from giso.ai_credits import admin_credit_users
    assert admin_credit_users() == []
    with get_giso_db_conn() as conn:
        columns = {row[1] for row in conn.execute("PRAGMA table_info(giso_ai_credit_ledger)")}
    assert {"service_key", "selected_style"}.issubset(columns)

    from flask import Flask
    from giso.panel.modules.ai import context
    app = Flask(__name__)
    with app.app_context():
        panel_data = context()["ai"]
    names = {str(row.get("name")) for row in panel_data.get("providers", [])}
    assert {"groq", "openrouter", "mistral", "sambanova", "cloudflare", "gemini", "gapgpt", "avalai"}.issubset(names)


def test_ai_provider_context_survives_optional_credit_query_error(tmp_path, monkeypatch):
    brain = _isolate_provider_storage(tmp_path, monkeypatch)
    brain.seed_registry_providers()
    from flask import Flask
    from giso.panel.modules.ai import context
    import giso.ai_credits as credits

    def fail_credit_query(*_args, **_kwargs):
        raise RuntimeError("legacy credit schema")

    monkeypatch.setattr(credits, "admin_credit_users", fail_credit_query)
    app = Flask(__name__)
    with app.app_context():
        provider_context = context()["ai"]

    names = {str(row.get("name")) for row in provider_context.get("providers", [])}
    assert {"groq", "openrouter", "mistral", "sambanova", "cloudflare", "gemini", "gapgpt", "avalai"}.issubset(names)
    assert provider_context["credit_users"] == []


def test_proxy_configuration_survives_env_backup_and_database_restore(tmp_path, monkeypatch):
    brain = _isolate_provider_storage(tmp_path, monkeypatch)
    proxy_url = "socks5://proxy.example.test:1080"
    brain.save_provider_to_env(
        name="proxy-check", api_key="TEST_ONLY_PROXY_KEY",
        base_url="https://proxy-check.example.test/v1", enabled=False,
        proxy_url=proxy_url, proxy_type="socks5",
    )

    # Ordinary provider updates that omit proxy arguments must preserve the backup.
    brain.save_provider_to_env(
        name="proxy-check", api_key="TEST_ONLY_PROXY_KEY",
        base_url="https://proxy-check.example.test/v1", enabled=False,
    )
    loaded = brain.load_providers_from_env()
    assert loaded[0]["proxy_url"] == proxy_url
    assert loaded[0]["proxy_type"] == "socks5"

    brain.sync_env_providers_to_db()
    restored = brain.get_ai_provider("proxy-check")
    assert restored["proxy_url"] == proxy_url
    assert restored["proxy_type"] == "socks5"
