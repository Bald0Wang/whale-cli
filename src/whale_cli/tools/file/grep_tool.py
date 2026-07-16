"""Grep tool — search file contents for a pattern.

Prefers ripgrep (`rg`) when available (fast, respects .gitignore by default);
falls back to a pure-Python re-based scan over text files. Supports three
output modes: files_with_matches / content / count_matches.
"""
from __future__ import annotations

import os
import re
import shutil
import subprocess

from ..base import Tool, err, ok

MAX_FILES = 200
MAX_CONTENT_LINES = 200
HEAD_LIMIT_DEFAULT = 50


def _has_rg() -> bool:
    return shutil.which("rg") is not None


def _grep_with_rg(pattern: str, path: str, output_mode: str, ignore_case: bool) -> dict:
    cmd = ["rg"]
    if ignore_case:
        cmd.append("-i")
    cmd += ["--color=never", "--no-heading", "-n"]
    if output_mode == "files_with_matches":
        cmd.append("-l")
    elif output_mode == "count_matches":
        cmd.append("-c")
    cmd += ["--", pattern, path]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=20)
    except subprocess.TimeoutExpired:
        return err("Error: grep timed out (>20s).")
    except Exception as e:
        return err(f"Error running rg: {e}")

    stdout = proc.stdout or ""
    lines = stdout.splitlines()
    if output_mode == "files_with_matches":
        shown = lines[:MAX_FILES]
        body = "\n".join(shown)
        header = f"{len(lines)} files match (showing {len(shown)})"
    elif output_mode == "count_matches":
        body = stdout.rstrip("\n")
        header = f"{len(lines)} files counted"
    else:  # content
        shown = lines[:MAX_CONTENT_LINES]
        body = "\n".join(shown)
        header = f"{len(lines)} matching lines (showing {len(shown)})"
    return ok(f"{header}\n{body}" if body else f"{header}\n(no content)")


def _grep_fallback(pattern: str, path: str, output_mode: str, ignore_case: bool) -> dict:
    """Pure-Python fallback when rg is missing."""
    flags = re.IGNORECASE if ignore_case else 0
    try:
        regex = re.compile(pattern, flags)
    except re.error as e:
        return err(f"Error: invalid regex {pattern!r}: {e}")

    root = path if os.path.isdir(path) else os.path.dirname(path) or "."
    files_matched = []
    content_lines = []
    counts = {}

    skip_dirs = {".git", "node_modules", "__pycache__", ".venv", "venv", "dist", "build"}
    walk_root = path if os.path.isdir(path) else "."
    for dirpath, dirnames, filenames in os.walk(walk_root):
        dirnames[:] = [d for d in dirnames if d not in skip_dirs]
        for fn in filenames:
            fp = os.path.join(dirpath, fn)
            try:
                with open(fp, "r", encoding="utf-8", errors="ignore") as f:
                    text = f.read()
            except OSError:
                continue
            matches = regex.findall(text)
            if not matches:
                continue
            files_matched.append(fp)
            counts[fp] = len(matches)
            if output_mode == "content":
                for ln_no, line in enumerate(text.splitlines(), 1):
                    if regex.search(line):
                        content_lines.append(f"{fp}:{ln_no}:{line}")
                        if len(content_lines) >= MAX_CONTENT_LINES:
                            break
            if len(files_matched) >= MAX_FILES:
                break
        if len(files_matched) >= MAX_FILES:
            break

    if output_mode == "files_with_matches":
        body = "\n".join(files_matched[:MAX_FILES])
        header = f"{len(files_matched)} files match"
    elif output_mode == "count_matches":
        body = "\n".join(f"{fp}:{counts[fp]}" for fp in files_matched[:MAX_FILES])
        header = f"{len(files_matched)} files counted"
    else:
        body = "\n".join(content_lines)
        header = f"{len(files_matched)} files, {len(content_lines)} lines"
    return ok(f"{header}\n{body}" if body else f"{header}\n(no matches)")


class GrepTool(Tool):
    name = "Grep"
    description = "Search file contents for a regex pattern."
    schema = {
        "type": "function",
        "function": {
            "name": "Grep",
            "description": (
                "Search file contents for a regex pattern. By default returns the list of files "
                "that contain matches (output_mode='files_with_matches'). Use 'content' to see "
                "matching lines with line numbers, or 'count_matches' for per-file counts. "
                "Uses ripgrep if available; otherwise falls back to a Python scan."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "pattern": {"type": "string", "description": "Regular expression to search for."},
                    "path": {"type": "string", "description": "File or directory to search (default: '.')."},
                    "output_mode": {
                        "type": "string",
                        "enum": ["files_with_matches", "content", "count_matches"],
                        "description": "files_with_matches (default) / content / count_matches.",
                    },
                    "ignore_case": {"type": "boolean", "description": "Case-insensitive match (default false)."},
                },
                "required": ["pattern"],
            },
        },
    }

    def __call__(
        self,
        *,
        pattern: str,
        path: str = ".",
        output_mode: str = "files_with_matches",
        ignore_case: bool = False,
    ) -> dict:
        if not pattern:
            return err("Error: empty pattern")
        if output_mode not in ("files_with_matches", "content", "count_matches"):
            return err(f"Error: invalid output_mode {output_mode!r}")

        target = path or "."
        if not os.path.exists(target):
            return err(f"Error: path not found: {target}")

        runner = _grep_with_rg if _has_rg() else _grep_fallback
        return runner(pattern, target, output_mode, ignore_case)
