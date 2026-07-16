"""Shared pytest fixtures for whale_cli.

Tests must NOT hit the real model by default. The ``mock_llm`` fixture returns
a fake LLMClient whose ``chat()`` yields a scripted sequence of responses,
so tool-routing / compaction / todo logic can be exercised offline.

For real-model tests, mark them with ``@pytest.mark.e2e`` (see test_e2e.py).
"""
from __future__ import annotations

import json as _json
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Dict, List, Optional
from unittest.mock import MagicMock

import pytest

# Make `src/` importable without installing the package.
ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


class _ScriptedResponse:
    """A stand-in for the OpenAI SDK ``ChatCompletionMessage`` object.

    Supports attribute access (.content / .tool_calls / .role) and
    ``model_dump(mode="json")`` so Soul._normalize_assistant_message treats it
    like a real SDK message.
    """

    def __init__(self, content: Optional[str] = None, tool_calls: Optional[List[Dict[str, Any]]] = None):
        self.content = content
        self.role = "assistant"
        self.tool_calls = tool_calls or None

    def model_dump(self, mode: str = "python"):
        d: Dict[str, Any] = {"role": "assistant", "content": self.content}
        if self.tool_calls:
            d["tool_calls"] = self.tool_calls
        return d

    def to_dict(self):  # pragma: no cover - parity with SDK fallback path
        return self.model_dump()


def make_tool_call(call_id: str, name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
    """Build a tool_calls entry shaped like the OpenAI SDK."""
    return {
        "id": call_id,
        "type": "function",
        "function": {"name": name, "arguments": _json.dumps(arguments)},
    }


class MockLLM:
    """Fake LLMClient. ``script`` is consumed in order; each entry is either a
    content string or a list of tool_calls (as built by make_tool_call)."""

    def __init__(self, script: List[Any]):
        self.script = list(script)
        self.calls: List[Dict[str, Any]] = []
        self.model = "mock-model"
        self.max_context_tokens = 256_000

    def chat(self, messages, tools=None, **kwargs):
        # Record what Soul asked for, so tests can assert on it.
        self.calls.append({
            "messages": messages,
            "tools": tools,
            "kwargs": kwargs,
        })
        if not self.script:
            raise AssertionError("MockLLM script exhausted — add more responses")
        item = self.script.pop(0)
        if isinstance(item, str):
            return _ScriptedResponse(content=item)
        # assume list of tool_call dicts
        return _ScriptedResponse(tool_calls=item)


@pytest.fixture
def mock_llm():
    """Factory fixture: call as mock_llm([resp1, resp2, ...])."""
    def _make(script):
        return MockLLM(script)
    return _make


@pytest.fixture
def tmp_workspace(tmp_path, monkeypatch):
    """A throwaway working directory, chdir'd into, for file-tool tests."""
    monkeypatch.chdir(tmp_path)
    return tmp_path
