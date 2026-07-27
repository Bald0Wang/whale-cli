"""Edit tool — old_string/new_string 精确替换。"""

from __future__ import annotations

from pathlib import Path

from tools.base import Tool, err, ok


class EditTool(Tool):
    name = "Edit"
    description = "Replace an exact substring in a file (old_string → new_string)."

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

    def __call__(self, *, path: str, old_string: str, new_string: str, replace_all: bool = False) -> dict:
        target = Path(path).resolve()
        if not target.exists():
            return err(f"Error: file not found: {path}")

        content = target.read_text(encoding="utf-8")
        if old_string not in content:
            return err(f"Error: old_string not found in {path}.")

        occurrences = content.count(old_string)
        if replace_all:
            new_content = content.replace(old_string, new_string)
            count = occurrences
        else:
            new_content = content.replace(old_string, new_string, 1)
            count = 1

        target.write_text(new_content, encoding="utf-8")
        summary = f"replaced {count} occurrence(s)"
        if not replace_all:
            summary += f" of {occurrences} present"
        return ok(f"Edited {path}: {summary}.", changed_files=[path])
