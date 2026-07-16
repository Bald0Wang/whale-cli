"""Workspace path validation and conservative local-command policy.

The policy gives the teaching CLI predictable, testable guardrails. It cannot
confine arbitrary native programs or interpreters; production isolation still
needs OS permissions, a container, or a dedicated sandbox runtime.
"""
from __future__ import annotations

import os
import re
import shlex
from pathlib import Path


class WorkspaceViolation(ValueError):
    """Raised when a tool request crosses the configured workspace boundary."""


_SHELL_CONTROL_TOKENS = {";", "&&", "||", "|", "&", ">", ">>", "<", "<<"}
_DESTRUCTIVE_COMMANDS = {"rm", "rmdir", "del", "erase", "rd", "shred"}
_NESTED_SHELLS = {"sh", "bash", "zsh", "fish", "cmd", "powershell", "pwsh"}
_WINDOWS_ABSOLUTE_PATH = re.compile(r"^[A-Za-z]:[\\/]")


def workspace_root(workspace: str | Path | None = None) -> Path:
    """Return the canonical workspace root, defaulting to the current directory."""
    return Path(workspace or os.getcwd()).resolve()


def resolve_workspace_path(path: str | Path, workspace: str | Path | None = None) -> Path:
    """Resolve ``path`` and require its real location to remain in ``workspace``.

    ``Path.resolve(strict=False)`` follows every existing symlink component,
    including a symlink parent of a new target. That closes the common
    ``workspace/link -> /outside`` escape without relying on textual ``..``
    checks.
    """
    root = workspace_root(workspace)
    requested = Path(path).expanduser()
    candidate = requested if requested.is_absolute() else root / requested
    resolved = candidate.resolve(strict=False)
    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise WorkspaceViolation(f"Path escapes workspace {root}: {path}") from exc
    return resolved


def parse_workspace_command(command: str) -> list[str]:
    """Parse one workspace-local command or raise a clear policy violation.

    Commands are later executed with ``shell=False``. Refusing shell control
    operators keeps the policy readable and prevents redirection or command
    chaining from silently expanding the command's effect.
    """
    if not command or not command.strip():
        raise WorkspaceViolation("Command cannot be empty.")

    try:
        tokens = shlex.split(command, posix=os.name != "nt")
    except ValueError as exc:
        raise WorkspaceViolation(f"Invalid command syntax: {exc}") from exc
    if not tokens:
        raise WorkspaceViolation("Command cannot be empty.")
    if any(token in _SHELL_CONTROL_TOKENS for token in tokens):
        raise WorkspaceViolation("Shell control operators and redirection are not allowed.")

    executable = Path(tokens[0]).name.lower()
    if executable in _DESTRUCTIVE_COMMANDS:
        raise WorkspaceViolation(f"Destructive command '{executable}' is blocked by workspace policy.")
    if executable in _NESTED_SHELLS:
        raise WorkspaceViolation(f"Nested shell '{executable}' is blocked by workspace policy.")
    if executable == "git" and _is_destructive_git(tokens[1:]):
        raise WorkspaceViolation("Destructive git operation is blocked by workspace policy.")

    for token in tokens[1:]:
        if _looks_like_external_path(token):
            raise WorkspaceViolation(f"External or parent path is not allowed in commands: {token}")
    return tokens


def _is_destructive_git(arguments: list[str]) -> bool:
    normalized = [argument.lower() for argument in arguments]
    return (
        normalized[:2] == ["reset", "--hard"]
        or normalized[:2] == ["clean", "-f"]
        or normalized[:2] == ["clean", "-fd"]
        or normalized[:2] == ["checkout", "--"]
    )


def _looks_like_external_path(token: str) -> bool:
    if token.startswith(("/", "~", "\\\\")) or _WINDOWS_ABSOLUTE_PATH.match(token):
        return True
    normalized = token.replace("\\", "/")
    return normalized == ".." or normalized.startswith("../") or "/../" in normalized
