"""Glob tool — find files by pattern.

Uses pathlib.Path.glob. Caps the result count and warns on overly broad
patterns (leading **) that would walk huge trees like node_modules.
"""
from __future__ import annotations

import os

from ..base import Tool, err, ok

MAX_MATCHES = 200


class GlobTool(Tool):
    name = "Glob"
    description = "Find files matching a glob pattern."
    schema = {
        "type": "function",
        "function": {
            "name": "Glob",
            "description": (
                "List files matching a glob pattern (e.g. '**/*.py', 'src/*.ts'). "
                f"At most {MAX_MATCHES} matches are returned, sorted."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "pattern": {"type": "string", "description": "Glob pattern, e.g. '**/*.py'."},
                    "directory": {"type": "string", "description": "Root directory (default: current dir)."},
                },
                "required": ["pattern"],
            },
        },
    }

    def __call__(self, *, pattern: str, directory: str = ".") -> dict:
        if ".." in pattern:
            return err("Error: pattern cannot contain '..'")
        if ".." in directory.split(os.sep):
            return err("Error: directory cannot contain '..'")

        if not os.path.isdir(directory):
            return err(f"Error: not a directory: {directory}")

        # Discourage leading ** which commonly walks node_modules/.git.
        if pattern.startswith("**/") or pattern == "**":
            # Still run it, but warn in stdout.
            warn = "Warning: leading '**' may scan large trees (node_modules/.git).\n"
        else:
            warn = ""

        try:
            from pathlib import Path
            root = Path(directory)
            matches = sorted(p for p in root.glob(pattern) if p.is_file())
        except Exception as e:
            return err(f"Error during glob: {e}")

        if not matches:
            return ok(warn + f"No files matched {pattern!r} under {directory!r}.")

        capped = matches[:MAX_MATCHES]
        lines = [str(p) for p in capped]
        summary = warn + f"Found {len(matches)} matches"
        if len(matches) > MAX_MATCHES:
            summary += f" (showing first {MAX_MATCHES})"
        summary += ":\n" + "\n".join(lines)
        return ok(summary)
