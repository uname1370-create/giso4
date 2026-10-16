#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""تست‌های بخش «مدیریت و انتخاب مدل‌ها» — بدون هیچ فراخوانی زنده به AI.

همهٔ دیتابیس‌ها موقت‌اند (tmp_path) و همهٔ تماس‌های HTTP با فیک جایگزین شده‌اند.
"""
import os
import sys

os.environ.setdefault("SECRET_KEY", "arena-test-secret-for-buti-ai-tests-32chars")
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if BASE_DIR not in sys.path:
    sys.path.append(BASE_DIR)

import asyncio  # noqa: E402
import json  # noqa: E402
import sqlite3  # noqa: E402

import pytest  # noqa: E402

from giso import ai_brain  # noqa: E402
from giso import ai_discovery as disc  # noqa: E402
from giso import ai_runtime  # noqa: E402
from giso.ai_models_registry import official_capability_hints  # noqa: E402
from giso.buti_ai import ai_models as bam  # noqa: E402


# ---------------------------------------------------------------- فیکسچر دیتابیس موقت
@pytest.fixture
def temp_db(tmp_path, monkeypatch):
    path = str(tmp_path / "section.db")

    def _connect():
        conn = sqlite3.connect(path)
        conn.row_factory = sqlite3.Row
        return conn

    class _Ctx:
        def __enter__(self):
            self.conn = _connect()
            return self.conn

        def __exit__(self, *exc):
            self.conn.commit()
            self.conn.close()
            return False

    monkeypatch.setattr(ai_brain, "get_conn", lambda: _connect())
    monkeypatch.setattr(bam, "get_giso_db_conn", lambda: _Ctx())
    init = _connect()
    ai_brain.init_ai_tables(init)
    init.commit()
    init.close()
    setup = _connect()
    bam.init_buti_ai_model_assignments(setup)
    setup.commit()
    setup.close()
    return path


def _add_provider(name, *, enabled=1, api_key="sk-test-key-123456", kind="openai",
                  vision=None, text=None):
    conn = ai_brain.get_conn()
    with conn:
        conn.execute(
            """INSERT INTO giso_ai_providers (name, kind, enabled, api_key, base_url,
               vision_models_json, text_models_json, models_json)
               VALUES (?, ?, ?, ?, ?, ?, ?, '[]')""",
            (name, kind, enabled, api_key, "https://example.invalid/v1",
             json.dumps(vision or [], ensure_ascii=False),
             json.dumps(text or [], ensure_ascii=False)),
        )
    conn.close()


# ---------------------------------------------------------------- ۱. شاهد فراداده رسمی
def test_official_hints_read_only_explicit_fields():
    openrouter_like = {"id": "a", "architecture": {"input_modalities": ["text", "image"],
                                                   "output_modalities": ["text"]}}
    hints = official_capability_hints(openrouter_like)
    assert hints["vision"] is True and hints["text"] is True and hints["image_gen"] is False
    assert hints["source"] == "api_metadata"
    mistral_like = {"id": "b", "capabilities": {"vision": False}}
    assert official_capability_hints(mistral_like)["vision"] is False
    # بدون فیلد صریح، هیچ حدسی از نام زده نمی‌شود
    assert official_capability_hints({"id": "llava-vision-model"}) == {}


# ---------------------------------------------------------------- ۲. وضعیت قابلیت
def _catalog(vision=None, text=None):
    return {"vision": {m["id"]: m for m in (vision or [])},
            "text": {m["id"]: m for m in (text or [])}}


def test_name_in_vision_list_is_probable_not_confirmed():
    cat = _catalog(vision=[{"id": "vis-x"}])
    info = disc.resolve_model_capability("vis-x", "vision", catalog=cat, checks={})
    assert info["status"] == disc.STATUS_PROBABLE


def test_text_model_is_never_unknown_for_vision_without_evidence():
    cat = _catalog(text=[{"id": "txt-only"}])
    info = disc.resolve_model_capability("txt-only", "vision", catalog=cat, checks={})
    assert info["status"] == disc.STATUS_UNKNOWN
    assert info["status"] not in disc.COMPATIBLE_STATUSES


def test_metadata_false_is_incompatible_and_true_is_confirmed():
    cat = _catalog(text=[{"id": "m1", "caps": {"vision": False, "source": "api_metadata"}},
                         {"id": "m2", "caps": {"vision": True, "source": "api_metadata"}}])
    assert disc.resolve_model_capability("m1", "vision", catalog=cat, checks={})["status"] == disc.STATUS_INCOMPATIBLE
    assert disc.resolve_model_capability("m2", "vision", catalog=cat, checks={})["status"] == disc.STATUS_CONFIRMED


def test_failed_check_is_never_recorded_as_confirmed():
    cat = _catalog(text=[{"id": "m1"}])
    checks = {("m1", "text"): {"result": disc.CHECK_FAILED, "stage": "model_run",
                               "detail": "timeout", "checked_at": "now"}}
    info = disc.resolve_model_capability("m1", "text", catalog=cat, checks=checks)
    assert info["status"] != disc.STATUS_CONFIRMED
    assert "ناموفق" in info["last_note"]


def test_image_generation_is_not_confirmed_without_real_generation():
    cat = _catalog(vision=[{"id": "@cf/black-forest-labs/flux-2-klein-4b"}])
    info = disc.resolve_model_capability("@cf/black-forest-labs/flux-2-klein-4b", "image_gen",
                                         catalog=cat, checks={})
    assert info["status"] == disc.STATUS_PROBABLE


# ---------------------------------------------------------------- ۳. پاک‌سازی خطا
def test_redact_removes_key_and_bearer_tokens():
    text = "HTTP 401: invalid key sk-abcdef1234567890 and Authorization: Bearer my.Secret-Token"
    out = disc.redact_secrets(text, secrets=("sk-abcdef1234567890",))
    assert "sk-abcdef" not in out and "my.Secret-Token" not in out
    assert "[پنهان]" in out


def test_classify_check_errors_split_connection_from_model_run():
    assert disc._classify_check_error("HTTP 401: nope", "text")[1] == "auth"
    assert disc._classify_check_error("HTTP 404: model missing", "text")[1] == "model_missing"
    assert disc._classify_check_error("ReadTimeout: slow", "text")[1] == "timeout"
    assert disc._classify_check_error("ConnectError: TLS/SSL connection has been closed", "text")[1] == "network"
    assert disc._classify_check_error("HTTP 429: slow down", "text")[1] == "transient"
    # خطای ناشناخته نتیجهٔ نامشخص است، نه ناسازگاری
    assert disc._classify_check_error("weird", "text")[0] == disc.CHECK_INCONCLUSIVE
    result, _, _ = disc._classify_check_error("HTTP 400: image input not supported", "vision")
    assert result == disc.CHECK_INCOMPATIBLE


# ---------------------------------------------------------------- ۴. تست واقعی (فیک‌شده)
def _patch_check_env(monkeypatch, reply_factory, calls):
    monkeypatch.setattr(ai_brain, "get_ai_provider", lambda name: {
        "name": name, "enabled": 1, "api_key": "sk-test-key-123456", "kind": "openai",
        "base_url": "https://example.invalid/v1", "api_root": "", "selected_model": "",
        "timeout": 20, "headers_json": "{}", "fallback_json": "[]",
        "vision_models_json": "[]", "text_models_json": "[]",
    } if name == "groq" else None)

    async def fake_ask(provider, messages, **kw):
        calls.append(("text", provider, kw.get("model")))
        return reply_factory(kw.get("model"))

    async def fake_vision(provider, path, prompt, **kw):
        calls.append(("vision", provider, kw.get("model")))
        return reply_factory(kw.get("model"))

    monkeypatch.setattr(ai_brain, "ask_ai", fake_ask)
    monkeypatch.setattr(ai_brain, "ask_ai_vision", fake_vision)
    saved = {}
    monkeypatch.setattr(disc, "_save_check", lambda p, m, c, r, s, d: saved.update(
        {(p, m, c): (r, s, d)}))
    return saved


def test_text_check_success_only_when_answering_model_matches(monkeypatch):
    calls = []
    saved = _patch_check_env(monkeypatch, lambda model: {"ok": True, "model": model, "text": "OK"}, calls)
    res = asyncio.run(disc.run_model_check("groq", "llama-a", "text"))
    assert res["ok"] is True and res["stage"] == "ok"
    assert saved[("groq", "llama-a", "text")][0] == disc.CHECK_OK
    assert calls == [("text", "groq", "llama-a")]


def test_check_reports_other_model_answer_as_failure(monkeypatch):
    calls = []
    saved = _patch_check_env(monkeypatch, lambda model: {"ok": True, "model": "fallback-z", "text": "OK"}, calls)
    res = asyncio.run(disc.run_model_check("groq", "llama-a", "text"))
    assert res["ok"] is False
    # پاسخ از مدل دیگر، ثابت نمی‌کند این مدل کار می‌کند؛ نتیجه نامشخص است
    assert saved[("groq", "llama-a", "text")][0] == disc.CHECK_INCONCLUSIVE
    assert res["stage"] == "inconclusive"


def test_auth_error_is_connection_failure_and_key_is_redacted(monkeypatch):
    calls = []
    saved = _patch_check_env(
        monkeypatch,
        lambda model: {"ok": False, "model": model,
                       "error": "HTTP 401: bad key sk-test-key-123456 Bearer abc.def"},
        calls)
    res = asyncio.run(disc.run_model_check("groq", "llama-a", "text"))
    assert res["ok"] is False and res["stage"] == "auth"
    assert res["provider_connection"] is False
    stored = saved[("groq", "llama-a", "text")][2]
    assert "sk-test-key" not in stored and "abc.def" not in stored


def test_image_generation_is_not_called_and_marked_not_tested(monkeypatch):
    calls = []
    saved = _patch_check_env(monkeypatch, lambda model: {"ok": True, "model": model, "text": "x"}, calls)
    res = asyncio.run(disc.run_model_check("groq", "flux-x", "image_gen"))
    assert calls == []
    assert res["stage"] == "not_tested" and res["ok"] is False
    assert saved[("groq", "flux-x", "image_gen")][0] == disc.CHECK_NOT_TESTED


def test_vision_check_uses_probe_and_removes_temp_file(monkeypatch):
    calls = []
    seen_paths = []

    def reply(model):
        return {"ok": True, "model": model, "text": "OK"}

    saved = _patch_check_env(monkeypatch, reply, calls)
    original_vision = ai_brain.ask_ai_vision

    async def spy(provider, path, prompt, **kw):
        seen_paths.append(path)
        assert os.path.exists(path)
        return await original_vision(provider, path, prompt, **kw)

    monkeypatch.setattr(ai_brain, "ask_ai_vision", spy)
    res = asyncio.run(disc.run_model_check("groq", "vis-x", "vision"))
    assert res["ok"] is True
    assert seen_paths and not os.path.exists(seen_paths[0])
    assert saved[("groq", "vis-x", "vision")][0] == disc.CHECK_OK


# ---------------------------------------------------------------- ۵. زنجیرهٔ متنی
def _fake_attempts(monkeypatch, plan):
    """plan: لیست نتیجه‌ها به ترتیب تماس؛ هر عنصر dict پاسخ `_ask_single_provider`."""
    calls = []

    async def fake_single(provider_name, messages, temperature=0.7, max_tokens=1200,
                          timeout_override=None, model_name=None):
        calls.append((provider_name, model_name))
        item = dict(plan[len(calls) - 1])
        item.setdefault("provider", provider_name)
        item.setdefault("model", model_name)
        return item

    monkeypatch.setattr(ai_runtime, "_ask_single_provider", fake_single)
    return calls


CHAIN = [{"provider_name": "p1", "model_name": "m1"},
         {"provider_name": "p2", "model_name": "m2"},
         {"provider_name": "p3", "model_name": "m3"}]


def test_chain_moves_to_next_model_on_rate_limit(monkeypatch):
    calls = _fake_attempts(monkeypatch, [
        {"ok": False, "reason": "provider_error", "error": "HTTP 429: slow down"},
        {"ok": True, "text": "سلام", "model": "m2"},
    ])
    res = asyncio.run(ai_runtime._chat_with_text_model_chain(CHAIN, [], 0.7, 100, "user"))
    assert res["ok"] is True and res["fallback_used"] is True
    assert calls == [("p1", "m1"), ("p2", "m2")]


def test_chain_stops_on_auth_error_without_trying_others(monkeypatch):
    calls = _fake_attempts(monkeypatch, [
        {"ok": False, "reason": "provider_error", "error": "HTTP 401: invalid key"},
    ])
    res = asyncio.run(ai_runtime._chat_with_text_model_chain(CHAIN, [], 0.7, 100, "user"))
    assert res["ok"] is False
    assert calls == [("p1", "m1")]
    assert "HTTP 401" in res["error"]


def test_chain_tries_each_model_once_and_returns_real_last_error(monkeypatch):
    calls = _fake_attempts(monkeypatch, [
        {"ok": False, "reason": "provider_error", "error": "ReadTimeout: slow"},
        {"ok": False, "reason": "provider_error", "error": "HTTP 503: busy"},
        {"ok": False, "reason": "provider_error", "error": "HTTP 429: limit"},
    ])
    res = asyncio.run(ai_runtime._chat_with_text_model_chain(CHAIN, [], 0.7, 100, "user"))
    assert res["ok"] is False
    assert calls == [("p1", "m1"), ("p2", "m2"), ("p3", "m3")]
    assert res["error"] == "HTTP 429: limit"
    assert res["text"] == ai_runtime.PROVIDER_ERROR_MESSAGE


def test_config_error_text_is_not_recoverable():
    assert ai_runtime._chain_error_is_recoverable("ReadTimeout: x") is True
    assert ai_runtime._chain_error_is_recoverable("HTTP 500: x") is True
    assert ai_runtime._chain_error_is_recoverable("API Key تنظیم نشده") is False
    assert ai_runtime._chain_error_is_recoverable("HTTP 400: bad") is False


# ---------------------------------------------------------------- ۶. ذخیرهٔ اسلات‌ها
def test_save_accepts_compatible_and_rejects_bad_selections(temp_db):
    _add_provider("groq", vision=[{"id": "vis-x"}], text=[{"id": "llama-a"}, {"id": "txt-bad", "caps": {"text": False, "source": "api_metadata"}}])
    _add_provider("off", enabled=0, text=[{"id": "off-m"}])

    ok, _ = bam.save_model_section("text", [("groq", "llama-a"), None, None])
    assert ok
    assert [r["model_name"] for r in bam.list_model_assignments(bam.TASK_TEXT_CHAT)] == ["llama-a"]
    assert [p["provider_name"] for p in bam.configured_text_chain()] == ["groq"]

    for bad_category, selections in [
        ("text", [("groq", "vis-x"), None, None]),          # بینایی بدون شاهد برای متن
        ("text", [("groq", "txt-bad"), None, None]),        # ناسازگار با متن
        ("text", [("off", "off-m"), None, None]),           # پروایدر غیرفعال
        ("text", [("groq", "llama-a"), ("groq", "llama-a"), None]),  # تکراری
        ("image_analysis", [("groq", "llama-a"), None, None]),      # متنی در دستهٔ تحلیل عکس
    ]:
        ok, msg = bam.save_model_section(bad_category, selections)
        assert ok is False, msg
    # ردّ شدن نباید اسلات قبلی را پاک کند
    assert [r["model_name"] for r in bam.list_model_assignments(bam.TASK_TEXT_CHAT)] == ["llama-a"]


def test_text_section_does_not_touch_mirror_slots(temp_db):
    _add_provider("groq", vision=[{"id": "vis-x"}], text=[{"id": "llama-a"}])
    bam.save_model_section("image_analysis", [("groq", "vis-x"), None, None])
    before = [dict(r) for r in bam.list_model_assignments(bam.TASK_EYEBROW_ANALYSIS)]
    bam.save_model_section("text", [("groq", "llama-a"), None, None])
    bam.save_model_section("text", [None, None, None])
    after = [dict(r) for r in bam.list_model_assignments(bam.TASK_EYEBROW_ANALYSIS)]
    assert before == after and len(after) == 1
    assert bam.list_model_assignments(bam.TASK_TEXT_CHAT) == []


def test_clear_only_affects_that_slot(temp_db):
    _add_provider("groq", text=[{"id": "a"}, {"id": "b"}])
    bam.save_model_section("text", [("groq", "a"), ("groq", "b"), None])
    bam.save_model_section("text", [("groq", "a"), None, None])
    rows = bam.list_model_assignments(bam.TASK_TEXT_CHAT)
    assert [(r["priority"], r["model_name"]) for r in rows] == [(1, "a")]


def test_slot_count_of_mirror_tab_is_unchanged(temp_db):
    from giso.buti_ai.ai_models import TASK_DEFS, panel_slots_context
    keys = {s["task_key"] for s in panel_slots_context()["slots"]}
    assert bam.TASK_TEXT_CHAT not in keys
    assert set(TASK_DEFS) == {bam.TASK_EYEBROW_ANALYSIS, bam.TASK_MIRROR_IMAGE_DESIGN,
                              bam.TASK_MIRROR_OUTPUT_VALIDATION}


def test_panel_section_builds_four_categories_with_compatible_options(temp_db):
    from giso.panel.modules import ai as panel_ai
    _add_provider("groq", vision=[{"id": "vis-x"}], text=[{"id": "llama-a"}])
    section = panel_ai.build_model_section()
    names = [c["key"] for c in section["categories"]]
    assert names == ["text", "image_analysis", "image_generation", "output_evaluation"]
    text_cat = section["categories"][0]
    values = [o["value"] for g in text_cat["option_groups"] for o in g["options"]]
    assert "groq|llama-a" in values and "groq|vis-x" not in values
    assert len(text_cat["slots"]) == 3
    img_cat = section["categories"][1]
    img_values = [o["value"] for g in img_cat["option_groups"] for o in g["options"]]
    assert "groq|vis-x" in img_values and "groq|llama-a" not in img_values


def test_build_section_makes_no_network_calls(temp_db, monkeypatch):
    from giso.panel.modules import ai as panel_ai

    def boom(*a, **k):
        raise AssertionError("network call on page open")

    monkeypatch.setattr(ai_brain, "_fetch_remote_models", boom)
    monkeypatch.setattr(ai_brain, "ask_ai", boom)
    monkeypatch.setattr(ai_brain, "ask_ai_vision", boom)
    _add_provider("groq", text=[{"id": "llama-a"}])
    panel_ai.build_model_section()


# ---------------------------------------------------------------- ۷. کشف و مسیر کامل چت
def test_refresh_models_stores_official_hints_and_drops_stale(temp_db, monkeypatch):
    _add_provider("groq", text=[{"id": "stale-x"}])

    async def fake_fetch(row):
        return {"ok": True, "items": [
            {"id": "llama-a", "architecture": {"input_modalities": ["text"], "output_modalities": ["text"]}},
            {"id": "plain-b"},
        ]}

    monkeypatch.setattr(ai_brain, "_fetch_remote_models", fake_fetch)
    res = ai_brain.refresh_models("groq")
    assert res["ok"] is True
    row = ai_brain.get_ai_provider("groq")
    text = {m["id"]: m for m in json.loads(row["text_models_json"])}
    assert text["llama-a"]["caps"]["text"] is True
    assert "caps" not in text["plain-b"]
    assert text["stale-x"].get("disabled") is True
    assert "caps" not in text["stale-x"]


def test_chat_engine_reads_configured_text_models_only(temp_db, monkeypatch):
    _add_provider("groq", text=[{"id": "llama-a"}, {"id": "llama-b"}])
    _add_provider("other", text=[{"id": "other-m"}])
    assert bam.save_model_section("text", [("groq", "llama-b"), ("groq", "llama-a"), None])[0]
    calls = []

    async def fake_single(provider_name, messages, temperature=0.7, max_tokens=1200,
                          timeout_override=None, model_name=None):
        calls.append((provider_name, model_name))
        if len(calls) == 1:
            return {"ok": False, "reason": "provider_error", "error": "HTTP 503: busy"}
        return {"ok": True, "text": "پاسخ", "model": model_name, "provider": provider_name}

    monkeypatch.setattr(ai_runtime, "_ensure_runtime_ready", lambda: None)
    monkeypatch.setattr(ai_runtime, "_ask_single_provider", fake_single)
    res = asyncio.run(ai_runtime.chat_with_failover([{"role": "user", "content": "سلام"}]))
    assert res["ok"] is True and res["fallback_used"] is True
    assert calls == [("groq", "llama-b"), ("groq", "llama-a")]


# ---------------------------------------------------------------- ۵. سیاست مرکزی زنجیره (فیک)
def test_recoverable_policy_stops_on_auth_and_request_errors_only():
    for text in ["HTTP 401: bad", "HTTP 403: no", "HTTP 402: pay", "HTTP 400: bad req", "HTTP 422: bad",
                 "API key تنظیم نشده است", "مدلی انتخاب نشده"]:
        assert bam.is_recoverable_chain_error(text) is False, text
    for text in ["ReadTimeout: slow", "HTTP 429: busy", "HTTP 503: down", "HTTP 404: model missing",
                 "ConnectError: boom", "خطای ناشناخته"]:
        assert bam.is_recoverable_chain_error(text) is True, text
    assert ai_runtime._chain_error_is_recoverable("HTTP 401: x") is False


def test_cloudflare_vision_candidates_never_use_image_or_unselected_model():
    llama = "@cf/meta/llama-3.2-11b-vision-instruct"
    flux = "@cf/black-forest-labs/flux-2-klein-4b"
    row = {"name": "cf1", "selected_model": flux, "vision_models_json": json.dumps([{"id": llama}])}
    assert ai_brain._cloudflare_vision_candidates(row, "") == []
    assert ai_brain._cloudflare_vision_candidates(row, llama) == [llama]
    assert ai_brain._cloudflare_vision_candidates(row, flux) == []
    row2 = {"name": "cf1", "selected_model": llama}
    assert ai_brain._cloudflare_vision_candidates(row2, "") == [llama]


def test_ask_ai_fast_uses_central_text_chain(monkeypatch):
    from giso.ai_config import FAST_TOTAL_TIMEOUT_SECONDS, FAST_PER_MODEL_TIMEOUT_SECONDS
    seen = {}

    async def fake_chain(chain, messages, temperature, max_tokens, role,
                         total_timeout=None, per_model_timeout=None):
        seen.update(chain=chain, total=total_timeout, per=per_model_timeout)
        return {"ok": True, "text": "سلام", "provider": "p", "model": "m"}

    monkeypatch.setattr(bam, "configured_text_chain",
                        lambda: [{"provider_name": "p", "model_name": "m", "priority": 1}])
    monkeypatch.setattr(ai_runtime, "_chat_with_text_model_chain", fake_chain)
    res = asyncio.run(ai_brain.ask_ai_fast([{"role": "user", "content": "hi"}]))
    assert res["ok"] is True
    assert seen["chain"][0]["model_name"] == "m"
    assert seen["total"] == FAST_TOTAL_TIMEOUT_SECONDS and seen["per"] == FAST_PER_MODEL_TIMEOUT_SECONDS


def _two_slot_chain(monkeypatch):
    import giso.analysis as an
    monkeypatch.setattr(an, "pick_active_vision_model", lambda: [
        {"provider_name": "p1", "model_name": "m1"}, {"provider_name": "p2", "model_name": "m2"}])
    calls = []
    return an, calls


def test_vision_engine_stops_on_non_recoverable_error(monkeypatch):
    an, calls = _two_slot_chain(monkeypatch)

    async def fake_vision(pname, path, prompt, model=None, max_tokens=0, timeout_override=None):
        calls.append((pname, model))
        return {"ok": False, "error": "HTTP 401: invalid key sk-abcdef1234567890"}

    monkeypatch.setattr(ai_brain, "ask_ai_vision", fake_vision)
    res = an.call_vision_with_fallback(["x.jpg"], "prompt")
    assert res["ok"] is False and calls == [("p1", "m1")]
    assert "sk-abcdef" not in res.get("last_error", "")


def test_vision_engine_moves_to_next_model_on_recoverable_error(monkeypatch):
    an, calls = _two_slot_chain(monkeypatch)

    async def fake_vision(pname, path, prompt, model=None, max_tokens=0, timeout_override=None):
        calls.append((pname, model))
        if pname == "p1":
            return {"ok": False, "error": "ReadTimeout: slow"}
        return {"ok": True, "text": '{"a": 1}', "model": model}

    monkeypatch.setattr(ai_brain, "ask_ai_vision", fake_vision)
    res = an.call_vision_with_fallback(["x.jpg"], "prompt")
    assert res["ok"] is True and calls == [("p1", "m1"), ("p2", "m2")]


def test_eyebrow_vision_without_global_fallback_and_empty_chain_makes_no_call(monkeypatch):
    import giso.analysis as an
    from giso.buti_ai.eyebrow import ai as eye
    monkeypatch.setattr(bam, "configured_vision_chain", lambda task_key=None: [])
    called = []
    monkeypatch.setattr(an, "call_vision_with_fallback", lambda *a, **k: called.append(1) or {"ok": False})
    res = eye._call_vision_json("x.jpg", "p", global_fallback=False)
    assert res == {"ok": False, "error": "assigned_vision_unavailable"}
    assert called == []


def test_manual_slot_save_is_validated_server_side(monkeypatch):
    monkeypatch.setattr(bam, "validate_slot_selection",
                        lambda *a, **k: "«x» برای این دسته پذیرفته نشد")
    ok, message = bam.save_model_assignment(bam.TASK_EYEBROW_ANALYSIS, 1, "groq", "x", validate=True)
    assert ok is False and "پذیرفته نشد" in message


def test_central_image_slots_win_over_env_sources(monkeypatch):
    from giso.buti_ai.eyebrow import image_generation as ig
    sentinel = object()
    monkeypatch.setattr(ig, "_ai_management_providers", lambda service_key="eyebrow": [sentinel])

    def env_must_not_run(env):
        raise AssertionError("منبع محیطی نباید وقتی مدیریت AI اسلات دارد اجرا شود")

    monkeypatch.setattr(ig, "_cloudflare_providers", env_must_not_run)
    assert ig.configured_image_providers(None) == [sentinel]

    monkeypatch.setattr(ig, "_ai_management_providers", lambda service_key="eyebrow": [])
    monkeypatch.setattr(ig, "_cloudflare_providers", lambda env: [sentinel])
    monkeypatch.setattr(ig, "_numbered_model_providers", lambda env: [])
    monkeypatch.setattr(ig, "_json_configured_providers", lambda env: [])
    monkeypatch.setattr(ig, "_provider_order", lambda providers, env: providers)
    assert ig.configured_image_providers(None) == [sentinel]


# ---------------------------------------------------------------- ۱۱. انتقال از تب آینه گیسو
def test_output_evaluation_saves_vision_model_and_rejects_text_only(temp_db):
    _add_provider("groq", vision=[{"id": "vis-x"}], text=[{"id": "llama-a"}])
    ok, msg = bam.save_model_section("output_evaluation", [("groq", "vis-x"), None, None])
    assert ok, msg
    assert [r["model_name"] for r in bam.list_model_assignments(bam.TASK_MIRROR_OUTPUT_VALIDATION)] == ["vis-x"]
    ok, _ = bam.save_model_section("output_evaluation", [("groq", "llama-a"), None, None])
    assert ok is False
    # ردّ شدن نباید اسلات قبلی داور را پاک کند
    assert [r["model_name"] for r in bam.list_model_assignments(bam.TASK_MIRROR_OUTPUT_VALIDATION)] == ["vis-x"]


def test_disabled_slot_is_stored_but_not_used_and_not_validated(temp_db):
    _add_provider("groq", text=[{"id": "a"}, {"id": "b"}])
    ok, msg = bam.save_model_section(
        "text", [("groq", "a"), ("groq", "not-a-real-model"), None],
        [{"enabled": True}, {"enabled": False}, None],
    )
    assert ok, msg
    rows = {r["priority"]: r for r in bam.list_model_assignments(bam.TASK_TEXT_CHAT)}
    assert rows[1]["enabled"] == 1 and rows[2]["enabled"] == 0
    active = [r["model_name"] for r in bam.list_model_assignments(bam.TASK_TEXT_CHAT, only_enabled=True)]
    assert active == ["a"]


def test_enabled_slot_with_bad_model_is_still_rejected(temp_db):
    _add_provider("groq", text=[{"id": "a"}])
    ok, msg = bam.save_model_section("text", [("groq", "missing"), None, None], [{"enabled": True}])
    assert ok is False and "اسلات 1" in msg


def test_image_slot_stores_kind_and_endpoint_from_models_tab(temp_db, monkeypatch):
    monkeypatch.setattr(bam, "validate_slot_selection", lambda *a, **k: "")
    ok, msg = bam.save_model_section(
        "image_generation", [("myimg", "custom-edit-v1"), None, None],
        [{"enabled": True, "image_kind": "openai_image_edit",
          "endpoint_override": "https://img.example.invalid/v1/images/edits"}, None, None],
    )
    assert ok, msg
    row = bam.list_model_assignments(bam.TASK_MIRROR_IMAGE_DESIGN)[0]
    assert row["image_kind"] == "openai_image_edit"
    assert row["endpoint_override"] == "https://img.example.invalid/v1/images/edits"
    assert row["enabled"] == 1


def test_without_extras_same_model_keeps_previous_image_settings(temp_db, monkeypatch):
    monkeypatch.setattr(bam, "validate_slot_selection", lambda *a, **k: "")
    bam.save_model_section("image_generation", [("myimg", "m1"), None, None],
                           [{"enabled": True, "image_kind": "multipart", "endpoint_override": "https://e.invalid/x"}, None, None])
    ok, _ = bam.save_model_section("image_generation", [("myimg", "m1"), None, None])
    assert ok
    row = bam.list_model_assignments(bam.TASK_MIRROR_IMAGE_DESIGN)[0]
    assert row["image_kind"] == "multipart" and row["endpoint_override"] == "https://e.invalid/x"


def test_handler_parses_enabled_and_image_fields_per_slot(monkeypatch):
    """فرم بخش مدل‌ها: فعال بودن و فیلدهای تصویر فقط برای دستهٔ طراحی تصویر به ذخیره می‌رسند."""
    from flask import Flask
    from giso.panel.modules import ai as panel_ai
    from giso.buti_ai import ai_models as models_mod

    captured = {}

    def _fake_save(category, selections, extras=None):
        captured.update(category=category, selections=selections, extras=extras)
        return True, "ok"

    monkeypatch.setattr(panel_ai, "_require_super", lambda: None)
    monkeypatch.setattr(models_mod, "save_model_section", _fake_save)
    monkeypatch.setattr(panel_ai, "flash", lambda *a, **k: None)
    monkeypatch.setattr(panel_ai, "url_for", lambda endpoint, **kw: "/admin/ai")
    app = Flask("handler_parse_test")
    form = {
        "slot_1": "groq|vis-x", "enabled_1": "1",
        "slot_2": "", "enabled_2": "",
        "slot_3": "", "image_kind_3": "multipart", "endpoint_3": "https://e.invalid/x",
    }
    with app.test_request_context("/admin/ai/model-section/image_generation/save", method="POST", data=form):
        panel_ai.handle_model_section_save("image_generation")
    assert captured["category"] == "image_generation"
    assert captured["selections"] == [("groq", "vis-x"), None, None]
    assert captured["extras"][0] == {"enabled": True, "image_kind": "", "endpoint_override": ""}
    assert captured["extras"][1] == {"enabled": False, "image_kind": "", "endpoint_override": ""}
    assert captured["extras"][2]["image_kind"] == "multipart"
    assert captured["extras"][2]["endpoint_override"] == "https://e.invalid/x"

    # دستهٔ متن فیلد تصویر ندارد؛ extras نباید کلید تصویر داشته باشد
    with app.test_request_context("/admin/ai/model-section/text/save", method="POST",
                                  data={"slot_1": "groq|llama-a", "enabled_1": "1"}):
        panel_ai.handle_model_section_save("text")
    assert captured["extras"][0] == {"enabled": True}
