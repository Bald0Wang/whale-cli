"""Unit tests for LLMClient — no real network calls.

We monkeypatch the OpenAI SDK constructor so the client never opens a socket,
then assert that chat() assembles the right kwargs and proxies .schema
attributes from tools.
"""
from __future__ import annotations

import io
import json
from types import SimpleNamespace
from unittest.mock import MagicMock
from urllib.error import HTTPError

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


def test_step_explore_uses_its_messages_api_default(monkeypatch):
    monkeypatch.setattr(client_mod, "_load_config_file", lambda: {})
    monkeypatch.delenv("LLM_BASE_URL", raising=False)
    monkeypatch.setenv("LLM_MODEL", "step-explore")
    assert client_mod.resolve_base_url() == "https://api.stepfun.com/v1"
    assert client_mod.default_base_url_for_model("step-explore") == "https://api.stepfun.com/v1"


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


def test_step_explore_prefers_stepfun_api_key(monkeypatch):
    monkeypatch.setenv("LLM_MODEL", "step-explore")
    monkeypatch.setenv("STEP_API_KEY", "plan-key")
    monkeypatch.setenv("STEPFUN_API_KEY", "explore-key")
    monkeypatch.setattr(client_mod, "_load_config_file", lambda: {})
    assert client_mod.get_api_key() == "explore-key"


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
    monkeypatch.setattr(client_mod, "get_api_key", lambda model=None: "k")
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
    monkeypatch.setattr(client_mod, "get_api_key", lambda model=None: "k")
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
    monkeypatch.setattr(client_mod, "get_api_key", lambda model=None: "k")
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
    monkeypatch.setattr(client_mod, "get_api_key", lambda model=None: "k")
    monkeypatch.setattr(client_mod, "resolve_base_url", lambda explicit=None: "https://x/v1")
    monkeypatch.setattr(client_mod, "resolve_model", lambda explicit=None: "m")
    monkeypatch.setattr(client_mod, "resolve_max_context_tokens", lambda explicit=None: 1000)

    client_mod.LLMClient(request_timeout=15)

    assert captured["timeout"] == 15


class _FakeHTTPResponse:
    def __init__(self, payload: dict):
        self._payload = payload

    def read(self) -> bytes:
        return json.dumps(self._payload).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False


def test_step_explore_uses_anthropic_messages_shape(monkeypatch):
    captured: dict = {}
    monkeypatch.setattr(client_mod, "_load_config_file", lambda: {})

    def _fake_urlopen(request, timeout):
        captured["url"] = request.full_url
        captured["headers"] = {key.lower(): value for key, value in request.header_items()}
        captured["payload"] = json.loads(request.data.decode("utf-8"))
        captured["timeout"] = timeout
        return _FakeHTTPResponse({"content": [{"type": "text", "text": "hello from explore"}]})

    monkeypatch.setattr(client_mod, "urlopen", _fake_urlopen)
    client = client_mod.LLMClient(api_key="explore-key", model="step-explore", request_timeout=9)
    response = client.chat(
        [
            {"role": "system", "content": "You are concise."},
            {"role": "user", "content": "hello"},
        ],
        tools=[_FakeTool()],
    )

    assert client.supports_tools is False
    assert client.supports_vision is False
    assert response.content == "hello from explore"
    assert response.tool_calls is None
    assert captured["url"] == "https://api.stepfun.com/v1/messages"
    assert captured["headers"]["x-api-key"] == "explore-key"
    assert captured["headers"]["anthropic-version"] == "2023-06-01"
    assert captured["timeout"] == 9
    assert captured["payload"] == {
        "model": "step-explore",
        "max_tokens": client_mod.DEFAULT_MAX_OUTPUT_TOKENS,
        "system": "You are concise.",
        "messages": [{"role": "user", "content": "hello"}],
    }


def test_step_explore_retries_rate_limit_with_backoff(monkeypatch):
    monkeypatch.setattr(client_mod, "_load_config_file", lambda: {})
    responses = [
        HTTPError("https://api.stepfun.com/v1/messages", 429, "rate limited", {"retry-after": "0"}, io.BytesIO()),
        _FakeHTTPResponse({"content": [{"type": "text", "text": "recovered"}]}),
    ]
    sleeps: list[float] = []

    def _fake_urlopen(_request, timeout):
        assert timeout == client_mod.DEFAULT_REQUEST_TIMEOUT
        next_response = responses.pop(0)
        if isinstance(next_response, Exception):
            raise next_response
        return next_response

    monkeypatch.setattr(client_mod, "urlopen", _fake_urlopen)
    monkeypatch.setattr(client_mod.time, "sleep", sleeps.append)
    client = client_mod.LLMClient(api_key="explore-key", model="step-explore")

    assert client.chat([{"role": "user", "content": "retry"}]).content == "recovered"
    assert sleeps == [client_mod.STEP_EXPLORE_RETRY_BACKOFF_SECONDS]


def test_step_explore_rejects_openai_image_parts(monkeypatch):
    monkeypatch.setattr(client_mod, "_load_config_file", lambda: {})
    client = client_mod.LLMClient(api_key="explore-key", model="step-explore")
    with pytest.raises(ValueError, match="OpenAI-compatible image input"):
        client.chat([{"role": "user", "content": [{"type": "image_url", "image_url": {"url": "data:image/png;base64,x"}}]}])


def test_step_explore_merges_adjacent_tool_history_into_valid_turns():
    system, messages = client_mod.LLMClient._prepare_step_explore_messages(
        [
            {"role": "system", "content": "system"},
            {"role": "user", "content": "start"},
            {"role": "assistant", "content": ""},
            {"role": "tool", "name": "ReadFile", "content": "first"},
            {"role": "tool", "name": "Glob", "content": "second"},
        ]
    )

    assert system == "system"
    assert [message["role"] for message in messages] == ["user", "assistant", "user"]
    assert "Tool result from ReadFile" in messages[-1]["content"]
    assert "Tool result from Glob" in messages[-1]["content"]
