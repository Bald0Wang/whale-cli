"""Unit tests for LLMClient — no real network calls.

We monkeypatch the OpenAI SDK constructor so the client never opens a socket,
then assert that chat() assembles the right kwargs and proxies .schema
attributes from tools.
"""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from whale_cli.llm import client as client_mod


# ---- config resolution -----------------------------------------------------

def test_resolve_defaults_to_step_plan(monkeypatch):
    """With no env and no config.json, we land on Step Plan defaults."""
    monkeypatch.delenv("LLM_BASE_URL", raising=False)
    monkeypatch.delenv("LLM_MODEL", raising=False)
    monkeypatch.setattr(client_mod, "_load_config_file", lambda: {})
    assert client_mod.resolve_base_url() == "https://api.stepfun.com/step_plan/v1"
    assert client_mod.resolve_model() == "step-3.7-flash"
    assert client_mod.resolve_max_context_tokens() == 256_000


def test_resolve_reads_config_file(monkeypatch):
    monkeypatch.setattr(
        client_mod,
        "_load_config_file",
        lambda: {"llm": {"base_url": "https://example.test/v1", "model": "m1", "max_context_tokens": 12345}},
    )
    monkeypatch.delenv("LLM_BASE_URL", raising=False)
    monkeypatch.delenv("LLM_MODEL", raising=False)
    assert client_mod.resolve_base_url() == "https://example.test/v1"
    assert client_mod.resolve_model() == "m1"
    assert client_mod.resolve_max_context_tokens() == 12345


def test_get_api_key_env_precedence(monkeypatch):
    monkeypatch.setenv("STEP_API_KEY", "step-key")
    monkeypatch.setenv("MOONSHOT_API_KEY", "moon-key")
    monkeypatch.setattr(client_mod, "_load_config_file", lambda: {"llm": {"api_key": "cfg-key"}})
    # STEP wins over MOONSHOT wins over config.
    assert client_mod.get_api_key() == "step-key"
    monkeypatch.delenv("STEP_API_KEY")
    assert client_mod.get_api_key() == "moon-key"
    monkeypatch.delenv("MOONSHOT_API_KEY")
    assert client_mod.get_api_key() == "cfg-key"


# ---- chat() request assembly ----------------------------------------------

class _FakeTool:
    """Minimal tool stub exposing .schema like the real Tool base class."""
    schema = {"type": "function", "function": {"name": "Echo", "parameters": {"type": "object"}}}


def _patch_openai_sdk(monkeypatch, captured):
    """Replace openai.OpenAI so LLMClient can be built without network."""
    fake_create = MagicMock(return_value=SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content="hi", role="assistant", tool_calls=None))]
    ))
    fake_client = SimpleNamespace(
        chat=SimpleNamespace(completions=SimpleNamespace(create=fake_create))
    )
    captured["create"] = fake_create

    def _fake_openai(api_key=None, base_url=None, **kw):
        captured["api_key"] = api_key
        captured["base_url"] = base_url
        captured.update(kw)
        return fake_client

    monkeypatch.setattr(client_mod, "OpenAI", _fake_openai)


def test_chat_forwards_schema_and_temperature(monkeypatch):
    captured: dict = {}
    _patch_openai_sdk(monkeypatch, captured)

    monkeypatch.setattr(client_mod, "_load_config_file", lambda: {})
    monkeypatch.setattr(client_mod, "get_api_key", lambda: "k")
    monkeypatch.setattr(client_mod, "resolve_base_url", lambda explicit=None: "https://x/v1")
    monkeypatch.setattr(client_mod, "resolve_model", lambda explicit=None: "m")
    monkeypatch.setattr(client_mod, "resolve_max_context_tokens", lambda explicit=None: 1000)

    c = client_mod.LLMClient(temperature=0.7)
    c.chat(messages=[{"role": "user", "content": "hi"}], tools=[_FakeTool()])

    _, kwargs = captured["create"].call_args
    assert kwargs["model"] == "m"
    assert kwargs["temperature"] == 0.7
    # tools come from .schema
    assert kwargs["tools"] == [_FakeTool.schema]
    assert kwargs["messages"] == [{"role": "user", "content": "hi"}]
    assert captured["timeout"] == client_mod.DEFAULT_REQUEST_TIMEOUT


def test_chat_optional_params_forwarded(monkeypatch):
    captured: dict = {}
    _patch_openai_sdk(monkeypatch, captured)
    monkeypatch.setattr(client_mod, "_load_config_file", lambda: {})
    monkeypatch.setattr(client_mod, "get_api_key", lambda: "k")
    monkeypatch.setattr(client_mod, "resolve_base_url", lambda explicit=None: "https://x/v1")
    monkeypatch.setattr(client_mod, "resolve_model", lambda explicit=None: "m")
    monkeypatch.setattr(client_mod, "resolve_max_context_tokens", lambda explicit=None: 1000)

    c = client_mod.LLMClient()
    c.chat(
        messages=[],
        tools=None,
        max_tokens=128,
        tool_choice="auto",
        temperature=0.1,
    )
    _, kwargs = captured["create"].call_args
    assert kwargs["max_tokens"] == 128
    assert kwargs["tool_choice"] == "auto"
    assert kwargs["temperature"] == 0.1
    assert kwargs["tools"] is None


def test_from_config_passes_overrides(monkeypatch):
    captured: dict = {}
    _patch_openai_sdk(monkeypatch, captured)
    monkeypatch.setattr(client_mod, "_load_config_file", lambda: {})
    monkeypatch.setattr(client_mod, "get_api_key", lambda: "k")
    # Real resolver honors `explicit` — mock must too, so overrides win.
    monkeypatch.setattr(client_mod, "resolve_base_url", lambda explicit=None: explicit or "https://x/v1")
    monkeypatch.setattr(client_mod, "resolve_model", lambda explicit=None: explicit or "default-m")
    monkeypatch.setattr(client_mod, "resolve_max_context_tokens", lambda explicit=None: explicit or 1000)

    c = client_mod.LLMClient.from_config(model="override-m")
    assert c.model == "override-m"
    # Without override, falls back to default.
    c2 = client_mod.LLMClient.from_config()
    assert c2.model == "default-m"


def test_request_timeout_can_be_overridden(monkeypatch):
    captured: dict = {}
    _patch_openai_sdk(monkeypatch, captured)
    monkeypatch.setattr(client_mod, "get_api_key", lambda: "k")
    monkeypatch.setattr(client_mod, "resolve_base_url", lambda explicit=None: "https://x/v1")
    monkeypatch.setattr(client_mod, "resolve_model", lambda explicit=None: "m")
    monkeypatch.setattr(client_mod, "resolve_max_context_tokens", lambda explicit=None: 1000)

    client_mod.LLMClient(request_timeout=15)

    assert captured["timeout"] == 15
