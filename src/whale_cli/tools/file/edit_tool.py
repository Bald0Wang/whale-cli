"""Edit tool — old_string/new_string exact replacement.

Exact string replacement: you give an exact `old_string` that must appear in the
file (multi-line OK), and it's replaced with `new_string`. By default only the
first occurrence is replaced; set replace_all=True for every occurrence. If
old_string isn't found, the tool errors out — this is a feature: it prevents
silent no-ops.
"""
from __future__ import annotations

from pathlib import Path

from ...security import WorkspaceViolation, resolve_workspace_path, workspace_root
from ..base import Tool, err, ok


class EditTool(Tool):
    name = "Edit"
    description = "Replace an exact substring in a file (old_string → new_string)."
    approval_action = "edit file"

    def __init__(self, workspace: str | Path | None = None):
        self.workspace = workspace_root(workspace)
    schema = {
        "type": "function",
        "function": {
            "name": "Edit",
            "description": (
                "Replace an exact substring in a file. old_string must be unique unless "
                "replace_all=true. Multi-line strings are supported. Errors if old_string "
                "is not found (no silent no-op)."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "File to edit."},
                    "old_string": {"type": "string", "description": "Exact text to find (must exist)."},
                    "new_string": {"type": "string", "description": "Text to replace it with."},
                    "replace_all": {"type": "boolean", "description": "Replace every occurrence (default false)."},
                },
                "required": ["path", "old_string", "new_string"],
            },
        },
    }

    def __call__(
        self,
        *,
        path: str,
        old_string: str,
        new_string: str,
        replace_all: bool = False,
    ) -> dict:
        try:
            target = resolve_workspace_path(path, self.workspace)
        except WorkspaceViolation as e:
            return err(f"Error: {e}")
        if not target.exists():
            return err(f"Error: file not found: {path}")
        if target.is_dir():
            return err(f"Error: path is a directory: {path}")

        try:
            with target.open("r", encoding="utf-8") as f:
                content = f.read()
        except Exception as e:
            return err(f"Error reading file: {e}")

        if old_string not in content:
            return err(
                f"Error: old_string not found in {path}. "
                "Refusing to edit — check whitespace/exact text."
            )

        if replace_all:
            count = content.count(old_string)
            new_content = content.replace(old_string, new_string)
        else:
            # First-match replacement. Report how many existed, so the model
            # knows whether a follow-up replace_all is needed.
            occurrences = content.count(old_string)
            new_content = content.replace(old_string, new_string, 1)
            count = 1

        try:
            with target.open("w", encoding="utf-8") as f:
                f.write(new_content)
        except Exception as e:
            return err(f"Error writing file: {e}")

        summary = f"replaced {count} occurrence(s)"
        if not replace_all:
            summary += f" of {occurrences} present"
        relative_path = target.relative_to(self.workspace)
        return ok(f"Edited {relative_path}: {summary}.", changed_files=[str(relative_path)])
