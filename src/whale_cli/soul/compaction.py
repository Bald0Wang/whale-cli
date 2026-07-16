"""Context compaction — compress long conversation history.

Simple compaction design:
- Trigger: estimated token count >= max_context * ratio (default 0.85).
- Estimate: total chars / 4 (rough, no tokenizer dependency; English-skewed
  but good enough for a teaching project).
- Compact: keep the most recent N messages verbatim (default 2), feed the rest
  to the model with a compact prompt, and replace them with a single summary
  message. Result: [summary] + [recent N].

The compact prompt (see prompts/compact.md) asks the model to emit a
structured summary with XML tags (current_focus / environment /
completed_tasks / active_issues / code_state), which doubles as the
"session note" from the docs.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

PROMPT_PATH = Path(__file__).resolve().parent.parent / "prompts" / "compact.md"

# How many trailing messages to preserve verbatim.
PRESERVE_RECENT = 2
DEFAULT_RATIO = 0.85


def estimate_tokens(messages: List[Dict[str, Any]]) -> int:
    """Rough token estimate: sum of stringified message content / 4."""
    total_chars = 0
    for m in messages:
        content = m.get("content")
        if isinstance(content, str):
            total_chars += len(content)
        elif content is not None:
            # tool_calls / lists etc.
            try:
                total_chars += len(json.dumps(content, ensure_ascii=False))
            except Exception:
                total_chars += len(str(content))
        # tool_call_id / name add a little
        total_chars += len(str(m.get("name", ""))) + len(str(m.get("role", "")))
    return total_chars // 4


def should_compact(
    token_count: int,
    max_context_tokens: int,
    ratio: float = DEFAULT_RATIO,
) -> bool:
    if max_context_tokens <= 0:
        return False
    return token_count >= int(max_context_tokens * ratio)


def _load_compact_prompt() -> str:
    try:
        return PROMPT_PATH.read_text(encoding="utf-8")
    except OSError:
        # Fallback inline prompt if the file is missing.
        return (
            "Summarize the following agent conversation, preserving: the current task, "
            "any errors and their solutions, final code state, and pending TODOs. "
            "Be concise.\n\nConversation:\n{conversation}"
        )


def _format_history_for_compaction(messages: List[Dict[str, Any]]) -> str:
    """Render messages into the labeled block the compact prompt expects."""
    parts = []
    for i, m in enumerate(messages):
        role = m.get("role", "unknown")
        content = m.get("content", "")
        parts.append(f"## Message {i}\nRole: {role}\nContent:\n{content}")
    return "\n\n".join(parts)


def compact(
    messages: List[Dict[str, Any]],
    llm,
    *,
    preserve_recent: int = PRESERVE_RECENT,
) -> List[Dict[str, Any]]:
    """Run one compaction pass.

    Returns a new message list: ``[summary_message] + [recent N]``. The
    summary message is a user-role message wrapping the model's compact
    output (so it survives as context). The original system prompt is
    **preserved** as messages[0] and not compacted.

    ``llm`` is expected to expose ``.chat(messages, tools=None)``.
    """
    if len(messages) <= preserve_recent + 1:
        # Not enough to compact (keep system + at least preserve_recent).
        return messages

    # Always keep the system prompt (messages[0]) intact.
    system_msg = messages[0] if messages and messages[0].get("role") == "system" else None
    rest = messages[1:] if system_msg else messages[:]

    if len(rest) <= preserve_recent:
        return messages

    to_compact = rest[:-preserve_recent] if preserve_recent > 0 else rest
    preserved = rest[-preserve_recent:] if preserve_recent > 0 else []

    prompt_template = _load_compact_prompt()
    history = _format_history_for_compaction(to_compact)
    # The compact prompt has a {conversation} placeholder.
    user_content = prompt_template.replace("{conversation}", history) if "{conversation}" in prompt_template else (
        prompt_template + "\n\n" + history
    )

    compact_request = [
        {"role": "system", "content": "You are a helpful assistant that compacts conversation context."},
        {"role": "user", "content": user_content},
    ]
    try:
        response = llm.chat(compact_request, tools=None)
        summary_text = getattr(response, "content", None) or ""
        if not summary_text and isinstance(response, dict):
            summary_text = response.get("content", "")
    except Exception as e:
        # If compaction fails, fall back to truncating the oldest messages
        # rather than crashing the agent loop.
        summary_text = f"[Compaction failed: {e}. Oldest messages dropped.]"

    summary_message = {
        "role": "user",
        "content": (
            "Previous context has been compacted. Here is the compaction output:\n\n"
            + summary_text
        ),
        "metadata": {"compacted": True},
    }

    result: List[Dict[str, Any]] = []
    if system_msg:
        result.append(system_msg)
    result.append(summary_message)
    result.extend(preserved)
    return result
