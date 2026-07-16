from __future__ import annotations

from typing import Any, Dict


def user_prompt_submit(*, session_id: str | None, cwd: str, prompt: str) -> Dict[str, Any]:
    return {"hook_event_name": "UserPromptSubmit", "session_id": session_id or "", "cwd": cwd, "prompt": prompt}


def pre_tool_use(*, session_id: str | None, cwd: str, tool_name: str, tool_input: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "hook_event_name": "PreToolUse",
        "session_id": session_id or "",
        "cwd": cwd,
        "tool_name": tool_name,
        "tool_input": tool_input,
    }


def post_tool_use(
    *,
    session_id: str | None,
    cwd: str,
    tool_name: str,
    tool_input: Dict[str, Any],
    tool_output: Dict[str, Any],
) -> Dict[str, Any]:
    return {
        "hook_event_name": "PostToolUse",
        "session_id": session_id or "",
        "cwd": cwd,
        "tool_name": tool_name,
        "tool_input": tool_input,
        "tool_output": tool_output,
    }


def post_tool_use_failure(
    *,
    session_id: str | None,
    cwd: str,
    tool_name: str,
    tool_input: Dict[str, Any],
    error: str,
) -> Dict[str, Any]:
    return {
        "hook_event_name": "PostToolUseFailure",
        "session_id": session_id or "",
        "cwd": cwd,
        "tool_name": tool_name,
        "tool_input": tool_input,
        "error": error,
    }


def pre_compact(*, session_id: str | None, cwd: str, trigger: str, token_count: int) -> Dict[str, Any]:
    return {
        "hook_event_name": "PreCompact",
        "session_id": session_id or "",
        "cwd": cwd,
        "trigger": trigger,
        "token_count": token_count,
    }


def post_compact(*, session_id: str | None, cwd: str, trigger: str, estimated_token_count: int) -> Dict[str, Any]:
    return {
        "hook_event_name": "PostCompact",
        "session_id": session_id or "",
        "cwd": cwd,
        "trigger": trigger,
        "estimated_token_count": estimated_token_count,
    }
