"""LLM client: the bridge to the model API.

Design notes
------------
- OpenAI-compatible: works with any endpoint that speaks the Chat Completions
  schema (Moonshot, Step Fun / Step Plan, local vLLM/Ollama, etc.).
- Configuration precedence (highest first):
    1. explicit constructor args
    2. environment variables  (STEP_API_KEY / OPENAI_API_KEY / MOONSHOT_API_KEY)
    3. ~/.whale/config.json
                               (llm.api_key / llm.base_url / llm.model /
                                llm.max_context_tokens)
    4. interactive prompt     (getpass) — last resort
- `chat()` returns the raw OpenAI SDK message object so callers can access
  `.tool_calls`, `.content` directly. `_normalize_assistant_message()` in
  :mod:`whale_cli.soul.soul` converts it to a plain dict for persistence.
"""

from __future__ import annotations

import getpass
import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

from openai import OpenAI

from whale_cli.runtime import resolve_runtime_paths

# Default endpoint / model. These are overridden by config.json or constructor.
DEFAULT_BASE_URL = "https://api.stepfun.com/step_plan/v1"
DEFAULT_MODEL = "step-3.7-flash"
DEFAULT_MAX_CONTEXT_TOKENS = 256_000
DEFAULT_TEMPERATURE = 0.3
DEFAULT_REQUEST_TIMEOUT = 120.0


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


def get_api_key() -> str:
    """Resolve the API key with the documented precedence.

    Order: STEP_API_KEY → OPENAI_API_KEY → MOONSHOT_API_KEY (legacy) →
    ~/.whale/config.json → interactive prompt.
    """
    for env_var in ("STEP_API_KEY", "OPENAI_API_KEY", "MOONSHOT_API_KEY"):
        key = os.getenv(env_var)
        if key:
            return key

    cfg_key = _llm_config_section().get("api_key")
    if cfg_key:
        return str(cfg_key)

    print("\033[33m[Warning] No API key found in env vars or ~/.whale/config.json.\033[0m")
    print("Set STEP_API_KEY or add {\"llm\":{\"api_key\":\"...\"}} to ~/.whale/config.json")
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
    return _llm_config_section().get("base_url") or DEFAULT_BASE_URL


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
    """A thin wrapper over the OpenAI SDK.

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
        self.api_key = api_key or get_api_key()
        self.base_url = resolve_base_url(base_url)
        self.model = resolve_model(model)
        self.max_context_tokens = resolve_max_context_tokens(max_context_tokens)
        self.temperature = temperature
        self.request_timeout = request_timeout
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
        """Run one Chat Completions turn.

        ``tools`` is a list of tool objects exposing a ``.schema`` attribute
        (see :class:`whale_cli.tools.base.Tool`). Returns the raw assistant
        message object from the SDK so ``.tool_calls`` is accessible.
        """
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
            response = self.client.chat.completions.create(**kwargs)
            return response.choices[0].message
        except Exception as e:
            print(f"\033[31m[Error] LLM Call Failed: {e}\033[0m")
            raise
