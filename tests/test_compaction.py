"""Unit tests for the compaction layer.

Uses a mock LLM so we verify the *plumbing* (trigger logic, message
restructuring, system-prompt preservation) without real model calls.
"""
from __future__ import annotations

from whale_cli.soul.compaction import (
    estimate_tokens,
    should_compact,
    compact,
)
from tests.conftest import MockLLM


def _make_messages(n: int):
    """n user/assistant pairs, preceded by a system prompt."""
    msgs = [{"role": "system", "content": "SYS"}]
    for i in range(n):
        msgs.append({"role": "user", "content": f"u{i} " + "x" * 200})
        msgs.append({"role": "assistant", "content": f"a{i} " + "y" * 200})
    return msgs


# ---- estimate_tokens ------------------------------------------------------

def test_estimate_tokens_basic():
    # content chars + role "user" length, integer-divided by 4
    msgs = [{"role": "user", "content": "a" * 40}]
    expected = (40 + len("user")) // 4
    assert estimate_tokens(msgs) == expected


def test_estimate_tokens_handles_non_string():
    msgs = [{"role": "assistant", "content": None, "tool_calls": [{"id": "1"}]}]
    # Should not crash; returns some non-negative int.
    assert estimate_tokens(msgs) >= 0


# ---- should_compact -------------------------------------------------------

def test_should_compact_below_threshold():
    assert not should_compact(100, 1000, 0.85)   # 100 < 850
    assert not should_compact(849, 1000, 0.85)


def test_should_compact_at_threshold():
    assert should_compact(850, 1000, 0.85)
    assert should_compact(900, 1000, 0.85)


def test_should_compact_zero_max_context():
    assert not should_compact(99999, 0)


# ---- compact() ------------------------------------------------------------

def test_compact_preserves_system_prompt():
    msgs = _make_messages(5)  # system + 10 msgs
    llm = MockLLM(["<current_focus>test</current_focus>"])
    result = compact(msgs, llm, preserve_recent=2)
    assert result[0]["role"] == "system"
    assert result[0]["content"] == "SYS"


def test_compact_reduces_message_count():
    msgs = _make_messages(5)  # system + 10 = 11 messages
    llm = MockLLM(["summary of the work so far"])
    result = compact(msgs, llm, preserve_recent=2)
    # system + summary + 2 preserved = 4 (down from 11)
    assert len(result) == 4
    roles = [m["role"] for m in result]
    # _make_messages ends with u4, a4 → preserved tail is [user, assistant]
    assert roles == ["system", "user", "user", "assistant"]


def test_compact_summary_message_wraps_model_output():
    msgs = _make_messages(3)
    llm = MockLLM(["MY_SUMMARY_TEXT"])
    result = compact(msgs, llm, preserve_recent=2)
    summary_msg = result[1]
    assert summary_msg["role"] == "user"
    assert "MY_SUMMARY_TEXT" in summary_msg["content"]
    assert "compacted" in summary_msg["content"].lower()


def test_compact_preserves_recent_verbatim():
    msgs = _make_messages(4)
    llm = MockLLM(["summary"])
    result = compact(msgs, llm, preserve_recent=2)
    # Last two original messages (a3, u4... actually order: u3,a3,u4... wait
    # our _make_messages appends u then a, so for n=4: u0,a0,u1,a1,u2,a2,u3,a3
    # last two = a2, u3? No: indices ...u2,a2,u3,a3 → last 2 = u3,a3? Let's
    # just assert the last assistant message is preserved.
    preserved = result[-2:]
    original_tail = msgs[-2:]
    for got, want in zip(preserved, original_tail):
        assert got["content"] == want["content"]


def test_compact_noop_when_too_few_messages():
    msgs = _make_messages(1)  # system + 2 messages = 3 total
    llm = MockLLM([])
    result = compact(msgs, llm, preserve_recent=2)
    # Not enough to compact → unchanged.
    assert result is msgs or result == msgs


def test_compact_fallback_on_llm_failure():
    """If the LLM call raises, compact should still return a usable list."""
    class _Boom:
        max_context_tokens = 1000
        def chat(self, *a, **k):
            raise RuntimeError("network down")
    msgs = _make_messages(5)
    result = compact(msgs, _Boom(), preserve_recent=2)
    # Should have produced a summary message (with the error note) + preserved.
    assert result[0]["role"] == "system"
    assert len(result) == 4
    assert "Compaction failed" in result[1]["content"]
