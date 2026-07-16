from __future__ import annotations

import os
from pathlib import Path
from typing import Iterable, List, Tuple

MAX_AGENTS_MD_BYTES = 32 * 1024


def find_project_root(work_dir: str | os.PathLike[str] | None = None) -> Path:
    """Return nearest git root, or ``work_dir`` when no repo marker exists."""
    current = Path(work_dir or os.getcwd()).resolve()
    if current.is_file():
        current = current.parent
    for candidate in (current, *current.parents):
        if (candidate / ".git").exists():
            return candidate
    return current


def _dirs_root_to_leaf(work_dir: Path, root: Path) -> List[Path]:
    dirs: List[Path] = []
    current = work_dir.resolve()
    root = root.resolve()
    while True:
        dirs.append(current)
        if current == root or current.parent == current:
            break
        current = current.parent
    dirs.reverse()
    return dirs


def _candidate_files(directory: Path) -> Iterable[Path]:
    # Whale CLI project-local override plus plain AGENTS.md files.
    for path in (
        directory / ".whale_cli" / "AGENTS.md",
    ):
        yield path
    # Uppercase wins over lowercase in the same directory.
    upper = directory / "AGENTS.md"
    lower = directory / "agents.md"
    yield upper if upper.exists() else lower


def _read_discovered(work_dir: Path) -> List[Tuple[Path, str]]:
    root = find_project_root(work_dir)
    discovered: List[Tuple[Path, str]] = []
    for directory in _dirs_root_to_leaf(work_dir, root):
        for path in _candidate_files(directory):
            if not path.is_file():
                continue
            text = path.read_text(encoding="utf-8").strip()
            if text:
                discovered.append((path, text))
    return discovered


def load_agents_md(
    work_dir: str | os.PathLike[str] | None = None,
    *,
    max_bytes: int = MAX_AGENTS_MD_BYTES,
) -> str:
    """Merge project instruction files root-to-leaf with leaf-first budget.

    Source annotations are included so the model can tell which rule came from
    which directory. When content is too large, deeper files keep priority.
    """
    cwd = Path(work_dir or os.getcwd()).resolve()
    discovered = _read_discovered(cwd)
    if not discovered:
        return ""

    remaining = max_bytes
    budgeted: List[Tuple[Path, str]] = [(p, "") for p, _ in discovered]
    for i in reversed(range(len(discovered))):
        path, text = discovered[i]
        annotation = f"<!-- From: {path} -->\n"
        separator_cost = len(b"\n\n") if i < len(discovered) - 1 else 0
        overhead = len(annotation.encode("utf-8")) + separator_cost
        remaining -= overhead
        if remaining <= 0:
            budgeted[i] = (path, "")
            remaining = 0
            continue
        encoded = text.encode("utf-8")
        if len(encoded) > remaining:
            text = encoded[:remaining].decode("utf-8", errors="ignore").strip()
        remaining -= len(text.encode("utf-8"))
        budgeted[i] = (path, text)

    parts = [f"<!-- From: {path} -->\n{text}" for path, text in budgeted if text]
    return "\n\n".join(parts)
