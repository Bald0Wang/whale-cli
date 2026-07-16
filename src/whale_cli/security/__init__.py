"""Small, explicit guardrails for tools that can mutate the local machine.

These helpers enforce a workspace boundary for Whale CLI's own file APIs and
apply a conservative command policy. They are intentionally not presented as
an operating-system sandbox.
"""

from .workspace import WorkspaceViolation, parse_workspace_command, resolve_workspace_path, workspace_root

__all__ = [
    "WorkspaceViolation",
    "parse_workspace_command",
    "resolve_workspace_path",
    "workspace_root",
]
