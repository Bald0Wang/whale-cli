"""TodoStore — in-memory todo list attached to a Soul instance.

Todo list design:
- The list is replaced wholesale on each write (not patched item-by-item).
- Three statuses: pending / in_progress / done.
- Passing None to the tool means "query current list" (read mode).

This store lives on the Soul so the REPL can render it via `/todo`, and so the
compaction layer can include it in summaries.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional

VALID_STATUSES = ("pending", "in_progress", "done")


@dataclass
class Todo:
    title: str
    status: str = "pending"

    def __post_init__(self):
        if self.status not in VALID_STATUSES:
            raise ValueError(f"invalid todo status {self.status!r}; must be one of {VALID_STATUSES}")
        if not self.title or not self.title.strip():
            raise ValueError("todo title must be non-empty")

    def to_dict(self) -> dict:
        return {"title": self.title, "status": self.status}


@dataclass
class TodoStore:
    _todos: List[Todo] = field(default_factory=list)

    def replace_all(self, items: List[Todo]) -> None:
        # Validate statuses up front; if any fails the constructor raises.
        self._todos = list(items)

    def clear(self) -> None:
        self._todos = []

    def all(self) -> List[Todo]:
        return list(self._todos)

    def render(self) -> str:
        """Human-readable rendering for the REPL /todo view."""
        if not self._todos:
            return "(no todos)"
        lines = []
        for i, t in enumerate(self._todos, 1):
            mark = {"pending": "[ ]", "in_progress": "[~]", "done": "[x]"}[t.status]
            lines.append(f"  {i}. {mark} {t.title}")
        return "\n".join(lines)

    def summary_for_llm(self) -> str:
        """Compact one-liner summary for the compaction / system context."""
        if not self._todos:
            return "no todos"
        done = sum(1 for t in self._todos if t.status == "done")
        total = len(self._todos)
        in_prog = [t.title for t in self._todos if t.status == "in_progress"]
        head = f"{done}/{total} done"
        if in_prog:
            head += f"; in_progress: {in_prog[0]}"
        return head

    def to_dict_list(self) -> List[dict]:
        return [t.to_dict() for t in self._todos]
