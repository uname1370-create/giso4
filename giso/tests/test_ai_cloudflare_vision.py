# -*- coding: utf-8 -*-
"""رگرسیون payload تحلیل تصویر Cloudflare Workers AI."""
import json
import sqlite3
from pathlib import Path

from PIL import Image


def test_cloudflare_vision_uses_workers_ai_image_payload_and_skips_flux(tmp_path, monkeypatch):
    import giso.ai_brain as brain

    db_path = tmp_path / "ai.db"

    def connect():
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        return conn

    monkeypatch.setattr(brain, "get_conn", connect)
    brain.init_ai_tables()

    root = "https://api.cloudflare.com/client/v4/accounts/acct/ai/run"
    brain.add_ai_provider(
        name="cf1",
        kind="cloudflare",
        api_key="FAKE_TOKEN",
        base_url=root,
        api_root=root,
        selected_model="@cf/black-forest-labs/flux-2-klein-4b",
        vision_models_json=json.dumps([
            {"id": "@cf/meta/llama-3.2-11b-vision-instruct", "is_free": True},
        ]),
        fallback_json=json.dumps([
            "@cf/black-forest-labs/flux-2-klein-4b",
            "@cf/meta/llama-3.2-11b-vision-instruct",
        ]),
        enabled=True,
        replace=True,
    )

    image_path = tmp_path / "face.jpg"
    Image.new("RGB", (32, 32), (220, 180, 160)).save(image_path, "JPEG")

    calls = []

    class FakeResponse:
        status_code = 200
        text = '{"result":{"response":"{\\"ok\\":true}"}}'

        def json(self):
            return {"result": {"response": '{"ok":true}'}}

    class FakeClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def post(self, url, headers=None, json=None):
            calls.append({"url": url, "headers": headers or {}, "json": json or {}})
            return FakeResponse()

    monkeypatch.setattr(brain, "_make_client", lambda timeout, proxy=None: FakeClient())

    result = brain.run_async_sync(brain.ask_ai_vision("cf۱", str(image_path), "فقط JSON بده", max_tokens=77))

    assert result["ok"] is True
    assert result["model"] == "@cf/meta/llama-3.2-11b-vision-instruct"
    assert calls, "Cloudflare باید فراخوانی شود"
    call = calls[0]
    assert call["url"].endswith("/ai/run/@cf/meta/llama-3.2-11b-vision-instruct")
    assert "flux" not in call["url"].lower()
    assert call["headers"]["Authorization"] == "Bearer FAKE_TOKEN"
    payload = call["json"]
    assert payload["prompt"] == "فقط JSON بده"
    assert payload["messages"][1]["content"] == "فقط JSON بده"
    assert payload["image"].startswith("data:image/jpeg;base64,")
    assert payload["max_tokens"] == 77
    assert result["request_format"] == "messages_image_data_uri"


def test_cloudflare_text_parser_accepts_official_string_result():
    from giso.ai_brain import _ai_text_cloudflare

    assert _ai_text_cloudflare({"result": "متن پاسخ"}) == "متن پاسخ"
    assert _ai_text_cloudflare({"result": {"response": "ok"}}) == "ok"
