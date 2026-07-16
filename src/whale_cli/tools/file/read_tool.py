"""ReadFile tool — read a text file with cat -n style line numbers.

Bounded by MAX_LINES and MAX_LINE_LENGTH, reports total file line count so the
model can plan follow-up reads, and refuses to dump binary content (sniffs the
first chunk for NUL bytes).
"""
from __future__ import annotations

import os

from ..base import Tool, err, ok

MAX_LINES = 2000
MAX_LINE_LENGTH = 2000
BINARY_SNIFF_BYTES = 2048


def _looks_binary(path: str) -> bool:
    try:
        with open(path, "rb") as f:
            chunk = f.read(BINARY_SNIFF_BYTES)
        return b"\x00" in chunk
    except OSError:
        return False


class ReadFileTool(Tool):
    name = "ReadFile"
    description = "Read a text file with line numbers (cat -n style)."
    schema = {
        "type": "function",
        "function": {
            "name": "ReadFile",
            "description": (
                "Read up to N lines of a text file, formatted with line numbers. "
                "Use line_offset to paginate (1-based; negative means from end). "
                "Reports the total line count so you can plan further reads."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Absolute or relative file path."},
                    "line_offset": {
                        "type": "integer",
                        "description": "1-based first line to read (default 1). Negative reads from the end, e.g. -100 = last 100 lines.",
                    },
                    "n_lines": {
                        "type": "integer",
                        "description": f"Maximum lines to return (default {MAX_LINES}).",
                    },
                },
                "required": ["path"],
            },
        },
    }

    def __call__(self, *, path: str, line_offset: int = 1, n_lines: int = MAX_LINES) -> dict:
        if ".." in path.split(os.sep):
            return err("Error: path cannot contain '..'")
        if not os.path.exists(path):
            return err(f"Error: file not found: {path}")
        if os.path.isdir(path):
            return err(f"Error: path is a directory, not a file: {path}")
        if _looks_binary(path):
            return err(f"Error: {path} appears to be a binary file; refuse to dump.")

        try:
            with open(path, "r", encoding="utf-8", errors="replace") as f:
                all_lines = f.readlines()
        except Exception as e:
            return err(f"Error reading file: {e}")

        total = len(all_lines)

        # Resolve offset: negative = from end.
        if line_offset < 0:
            start = max(0, total + line_offset)
        else:
            start = max(0, line_offset - 1)  # 1-based → 0-based
        n = max(1, min(n_lines, MAX_LINES))
        selected = all_lines[start:start + n]

        out_parts = []
        truncated_lines = []
        for i, raw in enumerate(selected):
            lineno = start + i + 1  # 1-based
            line = raw.rstrip("\n")
            if len(line) > MAX_LINE_LENGTH:
                line = line[:MAX_LINE_LENGTH] + "..."
                truncated_lines.append(lineno)
            out_parts.append(f"{lineno:6d}\t{line}")

        body = "\n".join(out_parts)
        header = f"[{path}] total lines: {total}, showing {len(selected)} from line {start + 1}"
        if truncated_lines:
            header += f"; lines truncated at {MAX_LINE_LENGTH} chars: {truncated_lines[:10]}"
        out = header + "\n" + body if body else header + "\n(empty range)"
        return ok(out)
