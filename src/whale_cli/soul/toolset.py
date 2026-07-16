"""Toolset: a registry that replaces the old if/elif dispatch in Soul.

Usage::

    ts = Toolset()
    ts.register(BashTool())
    ts.register(WriteFileTool())
    ...
    schemas = ts.all_schemas()          # -> list, pass to LLM as `tools=`
    result = ts.handle("Bash", '{"command":"ls"}')   # -> result dict

``handle`` does the JSON parse, looks the tool up by name, invokes it with
the parsed args as kwargs, and wraps any exception into a failure result so
the agent loop never crashes on a single bad tool call.

Approval hook (Phase 5): if a tool sets ``approval_action`` and a
``approver`` is attached to the toolset, the approver is consulted before
the tool runs. ``approver(action, description) -> bool``.
"""
from __future__ import annotations

import json
from typing import Any, Callable, Dict, List, Optional

from ..hooks import HookEngine
from ..hooks import events as hook_events
from ..tools.base import Tool


class Toolset:
    def __init__(self, tools: Optional[List[Tool]] = None, *, hook_engine: Optional[HookEngine] = None, session_id: Optional[str] = None, cwd: Optional[str] = None):
        self._tools: Dict[str, Tool] = {}
        self._approver: Optional[Callable[[str, str], bool]] = None
        self._hook_engine = hook_engine
        self._session_id = session_id
        self._cwd = cwd or "."
        for t in tools or []:
            self.register(t)

    # -- registration ------------------------------------------------------

    def register(self, tool: Tool) -> None:
        if not tool.name:
            raise ValueError(f"Tool {tool!r} has empty name")
        if tool.name in self._tools:
            raise ValueError(f"Tool {tool.name!r} already registered")
        self._tools[tool.name] = tool

    def get(self, name: str) -> Optional[Tool]:
        return self._tools.get(name)

    def __contains__(self, name: str) -> bool:
        return name in self._tools

    def __iter__(self):
        return iter(self._tools.values())

    @property
    def names(self) -> List[str]:
        return list(self._tools.keys())

    # -- approver wiring (Phase 5) ----------------------------------------

    def set_approver(self, approver: Optional[Callable[[str, str], bool]]) -> None:
        self._approver = approver

    def set_hook_engine(self, hook_engine: Optional[HookEngine], *, session_id: Optional[str] = None, cwd: Optional[str] = None) -> None:
        self._hook_engine = hook_engine
        self._session_id = session_id
        if cwd is not None:
            self._cwd = cwd

    # -- LLM-facing schema list -------------------------------------------

    def all_schemas(self) -> List[Dict[str, Any]]:
        return [t.schema for t in self._tools.values()]

    # -- dispatch ----------------------------------------------------------

    def handle(self, name: str, args_str: str) -> Dict[str, Any]:
        """Invoke tool ``name`` with JSON ``args_str``.

        Returns the standard result dict. Unknown tools, bad JSON, and tool
        exceptions are all caught and surfaced as ``exit_code != 0`` results
        so the agent loop keeps running.
        """
        tool = self._tools.get(name)
        if tool is None:
            return {
                "stdout": "",
                "stderr": f"Error: Tool {name!r} not found.",
                "exit_code": 1,
                "changed_files": [],
            }

        try:
            args = json.loads(args_str) if args_str else {}
        except json.JSONDecodeError as e:
            return {
                "stdout": "",
                "stderr": f"Error: invalid JSON arguments for {name}: {e}",
                "exit_code": 1,
                "changed_files": [],
            }
        if not isinstance(args, dict):
            return {
                "stdout": "",
                "stderr": f"Error: arguments for {name} must be a JSON object, got {type(args).__name__}",
                "exit_code": 1,
                "changed_files": [],
            }

        if self._hook_engine is not None:
            pre_results = self._hook_engine.trigger(
                "PreToolUse",
                hook_events.pre_tool_use(
                    session_id=self._session_id,
                    cwd=self._cwd,
                    tool_name=name,
                    tool_input=args,
                ),
            )
            blocked = self._hook_engine.first_block(pre_results)
            if blocked is not None:
                return {
                    "stdout": "",
                    "stderr": blocked.reason or f"{name} blocked by hook.",
                    "exit_code": 125,
                    "changed_files": [],
                }

        # Approval gate (no-op until Phase 5 attaches an approver).
        approval_action = tool.approval_action_for(args)
        if approval_action and self._approver is not None:
            description = f"{name}({args_str})"
            allowed = self._approver(approval_action, description)
            if not allowed:
                return {
                    "stdout": "",
                    "stderr": f"Error: {name} was rejected by the user (action: {approval_action}).",
                    "exit_code": 126,  # 126 = "command found but not executable" — permission denied
                    "changed_files": [],
                }

        try:
            result = tool(**args)
        except TypeError as e:
            result = {
                "stdout": "",
                "stderr": f"Error: bad arguments for {name}: {e}",
                "exit_code": 1,
                "changed_files": [],
            }
            self._trigger_tool_failure(name, args, result["stderr"])
            return result
        except Exception as e:
            result = {
                "stdout": "",
                "stderr": f"Error executing {name}: {e}",
                "exit_code": 1,
                "changed_files": [],
            }
            self._trigger_tool_failure(name, args, result["stderr"])
            return result

        # Normalize: tools may return a plain string or the full dict.
        if isinstance(result, str):
            normalized = {"stdout": result, "stderr": "", "exit_code": 0, "changed_files": []}
            self._trigger_tool_success(name, args, normalized)
            return normalized
        if not isinstance(result, dict):
            normalized = {"stdout": str(result), "stderr": "", "exit_code": 0, "changed_files": []}
            self._trigger_tool_success(name, args, normalized)
            return normalized
        # Ensure all four keys exist.
        normalized = {
            "stdout": result.get("stdout", ""),
            "stderr": result.get("stderr", ""),
            "exit_code": result.get("exit_code", 0),
            "changed_files": result.get("changed_files", []),
        }
        if normalized["exit_code"] == 0:
            self._trigger_tool_success(name, args, normalized)
        else:
            self._trigger_tool_failure(name, args, normalized.get("stderr", ""))
        return normalized

    def _trigger_tool_success(self, name: str, args: Dict[str, Any], result: Dict[str, Any]) -> None:
        if self._hook_engine is None:
            return
        self._hook_engine.trigger(
            "PostToolUse",
            hook_events.post_tool_use(
                session_id=self._session_id,
                cwd=self._cwd,
                tool_name=name,
                tool_input=args,
                tool_output=result,
            ),
        )

    def _trigger_tool_failure(self, name: str, args: Dict[str, Any], error: str) -> None:
        if self._hook_engine is None:
            return
        self._hook_engine.trigger(
            "PostToolUseFailure",
            hook_events.post_tool_use_failure(
                session_id=self._session_id,
                cwd=self._cwd,
                tool_name=name,
                tool_input=args,
                error=error,
            ),
        )
