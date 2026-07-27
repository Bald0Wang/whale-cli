"""Tool base class and shared conventions.

Every tool is a plain class with three class attributes
(``name``, ``description``, ``schema``) and a ``__call__`` that accepts the
parsed arguments as keyword args and returns the standard result dict:

    {
        "stdout": str,
        "stderr": str,
        "exit_code": int,        # 0 = success, non-zero = failure
        "changed_files": list[str],
    }

This mirrors the original tool contract so all existing tools and
``Soul._format_tool_result`` keep working, while letting new tools be added
without touching ``Soul`` (see :class:`whale_cli.soul.toolset.Toolset`).
"""
from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional


class Tool:
    """Base class. Subclasses set ``name``/``description``/``schema`` and
    implement ``__call__(self, **kwargs) -> dict``.

    ``approval_action`` is optional — when set, the toolset will ask the
    approval layer to confirm before invoking the tool. Phase 5 wires this up.
    """

    name: str = ""
    description: str = ""
    schema: Dict[str, Any] = {}
    # If set, this action label is sent to the Approval layer before __call__.
    approval_action: Optional[str] = None

    def approval_action_for(self, args: Dict[str, Any]) -> Optional[str]:
        """Optionally select an approval label from validated tool arguments."""
        return self.approval_action

    def __call__(self, **kwargs: Any) -> Dict[str, Any]:
        raise NotImplementedError


def ok(stdout: str = "", changed_files: Optional[List[str]] = None) -> Dict[str, Any]:
    """Shorthand for a successful tool result."""
    return {"stdout": stdout, "stderr": "", "exit_code": 0, "changed_files": changed_files or []}


def err(stderr: str, exit_code: int = 1) -> Dict[str, Any]:
    """Shorthand for a failed tool result (no changed_files)."""
    return {"stdout": "", "stderr": stderr, "exit_code": exit_code, "changed_files": []}
