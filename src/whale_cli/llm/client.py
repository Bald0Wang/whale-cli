"""LLM client: the bridge to the model API.

Design notes
------------
- OpenAI-compatible: works with any endpoint that speaks the Chat Completions
  schema (Moonshot, Step Fun / Step Plan, local vLLM/Ollama, etc.).
- StepFun ``step-explore``: uses its separate Anthropic Messages endpoint.
- Configuration precedence (highest first):
    1. explicit constructor args
    2. environment variables  (STEP_API_KEY / OPENAI_API_KEY / MOONSHOT_API_KEY)
    3. ~/.whale/config.json
                               (llm.api_key / llm.base_url / llm.model /
                                llm.max_context_tokens)
    4. interactive prompt     (getpass) — last resort
- `chat()` returns an object exposing `.tool_calls` and `.content` for both
  provider paths. `_normalize_assistant_message()` in :mod:`whale_cli.soul.soul`
  converts it to a plain dict for persistence.
"""

from __future__ import annotations

import getpass
import json
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from openai import OpenAI

from whale_cli.runtime import resolve_runtime_paths

# Default endpoint / model. These are overridden by config.json or constructor.
DEFAULT_BASE_URL = "https://api.stepfun.com/step_plan/v1"
DEFAULT_MODEL = "step-3.7-flash"
DEFAULT_MAX_CONTEXT_TOKENS = 256_000
DEFAULT_TEMPERATURE = 0.3
DEFAULT_REQUEST_TIMEOUT = 120.0
DEFAULT_MAX_OUTPUT_TOKENS = 4096
STEP_EXPLORE_MODEL = "step-explore"
STEP_EXPLORE_BASE_URL = "https://api.stepfun.com/v1"
STEP_EXPLORE_ANTHROPIC_VERSION = "2023-06-01"
STEP_EXPLORE_MAX_RETRIES = 3
STEP_EXPLORE_RETRY_BACKOFF_SECONDS = 0.5


@dataclass
class AssistantMessage:
    """Provider-neutral result used by the Anthropic Messages adapter."""

    content: str
    role: str = "assistant"
    tool_calls: None = None


def is_step_explore_model(model: str) -> bool:
    return model.strip().lower() == STEP_EXPLORE_MODEL


def default_base_url_for_model(model: str) -> str:
    return STEP_EXPLORE_BASE_URL if is_step_explore_model(model) else DEFAULT_BASE_URL


def _config_candidates() -> List[Path]:
    configured = resolve_runtime_paths().config_file
    legacy = Path.home() / ".whale" / "config.json"
    return [configured] if configured == legacy else [configured, legacy]


def _load_config_file() -> Dict[str, Any]:
    """Read ~/.whale/config.json."""
    try:
        config_path = next((p for p in _config_candidates() if p.exists()), None)
        if config_path is None:
            return {}
        if config_path.exists():
            with open(config_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, dict):
                    return data
    except Exception:
        # Best-effort: never crash on config read.
        pass
    return {}


def _llm_config_section() -> Dict[str, Any]:
    data = _load_config_file()
    section = data.get("llm") if isinstance(data, dict) else None
    return section if isinstance(section, dict) else {}


def get_api_key(model: Optional[str] = None) -> str:
    """Resolve the API key with the documented precedence.

    ``step-explore`` prefers the key name from its provider guide:
    STEPFUN_API_KEY → STEP_API_KEY. Other models retain the existing
    STEP_API_KEY-first order.
    """
    key_names = (
        ("STEPFUN_API_KEY", "STEP_API_KEY", "OPENAI_API_KEY", "MOONSHOT_API_KEY")
        if is_step_explore_model(model or resolve_model())
        else ("STEP_API_KEY", "STEPFUN_API_KEY", "OPENAI_API_KEY", "MOONSHOT_API_KEY")
    )
    for env_var in key_names:
        key = os.getenv(env_var)
        if key:
            return key

    cfg_key = _llm_config_section().get("api_key")
    if cfg_key:
        return str(cfg_key)

    print("\033[33m[Warning] No API key found in env vars or ~/.whale/config.json.\033[0m")
    print("Set STEP_API_KEY / STEPFUN_API_KEY or add {\"llm\":{\"api_key\":\"...\"}} to ~/.whale/config.json")
    api_key = getpass.getpass("Please enter your API Key: ")
    if not api_key:
        raise ValueError("API Key is required to run Whale CLI.")
    return api_key


def resolve_base_url(explicit: Optional[str] = None) -> str:
    if explicit:
        return explicit
    env = os.getenv("LLM_BASE_URL")
    if env:
        return env
    return _llm_config_section().get("base_url") or default_base_url_for_model(resolve_model())


def resolve_model(explicit: Optional[str] = None) -> str:
    if explicit:
        return explicit
    env = os.getenv("LLM_MODEL")
    if env:
        return env
    return _llm_config_section().get("model") or DEFAULT_MODEL


def resolve_max_context_tokens(explicit: Optional[int] = None) -> int:
    if explicit:
        return explicit
    env = os.getenv("LLM_MAX_CONTEXT_TOKENS")
    if env and env.isdigit():
        return int(env)
    val = _llm_config_section().get("max_context_tokens")
    if isinstance(val, int) and val > 0:
        return val
    return DEFAULT_MAX_CONTEXT_TOKENS


class LLMClient:
    """A thin provider adapter over OpenAI Chat Completions and Step Explore.

    Parameters
    ----------
    api_key, base_url, model:
        Explicit overrides. When None, fall back to the resolution helpers.
    max_context_tokens:
        Used by the compaction layer to decide when to compress. Does not
        affect the HTTP request itself.
    temperature:
        Sampling temperature forwarded to the API.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
        max_context_tokens: Optional[int] = None,
        temperature: float = DEFAULT_TEMPERATURE,
        request_timeout: float = DEFAULT_REQUEST_TIMEOUT,
    ):
        self.model = resolve_model(model)
        self.api_key = api_key or get_api_key(self.model)
        self.base_url = resolve_base_url(base_url)
        if not (base_url or os.getenv("LLM_BASE_URL") or _llm_config_section().get("base_url")):
            self.base_url = default_base_url_for_model(self.model)
        self.max_context_tokens = resolve_max_context_tokens(max_context_tokens)
        self.temperature = temperature
        self.request_timeout = request_timeout
        self.supports_tools = not is_step_explore_model(self.model)
        self.supports_vision = not is_step_explore_model(self.model)
        self.client = None
        if self.supports_tools:
            self.client = OpenAI(
                api_key=self.api_key,
                base_url=self.base_url,
                timeout=request_timeout,
            )

    @classmethod
    def from_config(cls, **overrides: Any) -> "LLMClient":
        """Build a client, letting config.json / env provide the defaults.

        Any keyword argument overrides the resolved value.
        """
        return cls(**overrides)

    def chat(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Any]] = None,
        *,
        max_tokens: Optional[int] = None,
        tool_choice: Optional[str] = None,
        temperature: Optional[float] = None,
    ):
        """Run one provider-specific model turn.

        ``tools`` is a list of tool objects exposing a ``.schema`` attribute
        (see :class:`whale_cli.tools.base.Tool`). Returns the raw assistant
        message object from the SDK so ``.tool_calls`` is accessible.
        """
        if not self.supports_tools:
            return self._chat_step_explore(messages, max_tokens=max_tokens)

        api_tools = [t.schema for t in tools] if tools else None

        kwargs: Dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "tools": api_tools,
            "temperature": self.temperature if temperature is None else temperature,
        }
        if max_tokens is not None:
            kwargs["max_tokens"] = max_tokens
        if tool_choice is not None:
            kwargs["tool_choice"] = tool_choice

        try:
            assert self.client is not None
            response = self.client.chat.completions.create(**kwargs)
            return response.choices[0].message
        except Exception as e:
            print(f"\033[31m[Error] LLM Call Failed: {e}\033[0m")
            raise

    def _chat_step_explore(
        self,
        messages: List[Dict[str, Any]],
        *,
        max_tokens: Optional[int],
    ) -> AssistantMessage:
        """Call Step Explore's Anthropic Messages API.

        Step Explore does not accept the OpenAI Chat Completions route,
        OpenAI tool schemas, OpenAI image parts, or a ``thinking`` field.
        The adapter deliberately sends only the documented Messages fields.
        """
        system, api_messages = self._prepare_step_explore_messages(messages)
        payload: Dict[str, Any] = {
            "model": self.model,
            "max_tokens": max_tokens or DEFAULT_MAX_OUTPUT_TOKENS,
            "messages": api_messages,
        }
        if system:
            payload["system"] = system

        request = Request(
            f"{self.base_url.rstrip('/')}/messages",
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers={
                "x-api-key": self.api_key,
                "anthropic-version": STEP_EXPLORE_ANTHROPIC_VERSION,
                "content-type": "application/json",
            },
            method="POST",
        )
        response_data = self._open_step_explore_request(request)
        return AssistantMessage(content=self._step_explore_text(response_data))

    def _open_step_explore_request(self, request: Request) -> Dict[str, Any]:
        for attempt in range(STEP_EXPLORE_MAX_RETRIES + 1):
            try:
                with urlopen(request, timeout=self.request_timeout) as response:
                    payload = json.loads(response.read().decode("utf-8"))
                if not isinstance(payload, dict):
                    raise ValueError("Step Explore returned a non-object JSON response.")
                return payload
            except HTTPError as exc:
                if exc.code != 429 or attempt >= STEP_EXPLORE_MAX_RETRIES:
                    raise
                retry_after = exc.headers.get("retry-after") if exc.headers else None
                try:
                    delay = float(retry_after) if retry_after else 0.0
                except ValueError:
                    delay = 0.0
                time.sleep(delay or STEP_EXPLORE_RETRY_BACKOFF_SECONDS * (2**attempt))

        raise RuntimeError("Step Explore retry loop ended unexpectedly.")

    @staticmethod
    def _prepare_step_explore_messages(messages: List[Dict[str, Any]]) -> tuple[str, List[Dict[str, str]]]:
        system_parts: List[str] = []
        api_messages: List[Dict[str, str]] = []

        def append_message(role: str, content: str) -> None:
            # Anthropic-style histories alternate user and assistant turns.
            # A resumed OpenAI tool history can contain several tool results
            # in a row, so retain them while merging adjacent same-role turns.
            if api_messages and api_messages[-1]["role"] == role:
                api_messages[-1]["content"] += f"\n\n{content}"
            else:
                api_messages.append({"role": role, "content": content})

        for message in messages:
            role = str(message.get("role") or "user")
            content = LLMClient._step_explore_content(message.get("content"))
            if role == "system":
                if content:
                    system_parts.append(content)
                continue
            if role == "tool":
                name = str(message.get("name") or "tool")
                append_message("user", f"Tool result from {name}:\n{content}")
                continue
            if role not in {"user", "assistant"}:
                role = "user"
            append_message(role, content)
        if not api_messages:
            api_messages.append({"role": "user", "content": "Continue."})
        return "\n\n".join(system_parts), api_messages

    @staticmethod
    def _step_explore_content(content: Any) -> str:
        if isinstance(content, str):
            return content
        if not isinstance(content, list):
            return "" if content is None else str(content)

        text_parts: List[str] = []
        for part in content:
            if not isinstance(part, dict):
                text_parts.append(str(part))
                continue
            if part.get("type") == "text":
                text_parts.append(str(part.get("text") or ""))
                continue
            if part.get("type") == "image_url":
                raise ValueError(
                    "step-explore does not accept Whale's OpenAI-compatible image input. "
                    "Disable vision input or switch to step-3.7-flash."
                )
            text_parts.append(str(part.get("text") or ""))
        return "\n".join(part for part in text_parts if part)

    @staticmethod
    def _step_explore_text(payload: Dict[str, Any]) -> str:
        blocks = payload.get("content")
        if not isinstance(blocks, list):
            return ""
        return "\n".join(
            str(block.get("text") or "")
            for block in blocks
            if isinstance(block, dict) and block.get("type") == "text"
        ).strip()
