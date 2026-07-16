"""Small local JSON store shared by the learning modules."""
from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any, Callable


def _empty_state() -> dict[str, Any]:
    return {
        "profile": {},
        "knowledge_nodes": {},
        "knowledge_links": [],
        "roadmap": [],
        "reviews": {},
        "review_sync": {},
        "projects": [],
        "evidence": [],
        "wiki": {},
        "wiki_outlines": {},
    }


class LearningStore:
    """Persist the learner's state without coupling domain logic to JSON I/O."""

    def __init__(self, workspace: str | Path) -> None:
        self.workspace = Path(workspace).resolve()
        self.path = self.workspace / ".whale_cli" / "learning" / "state.json"

    def read(self) -> dict[str, Any]:
        if not self.path.exists():
            return _empty_state()
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            raw = {}
        state = _empty_state()
        if isinstance(raw, dict):
            for key in state:
                if key in raw and isinstance(raw[key], type(state[key])):
                    state[key] = raw[key]
        return state

    def update(self, change: Callable[[dict[str, Any]], None]) -> dict[str, Any]:
        state = deepcopy(self.read())
        change(state)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(".tmp")
        temporary.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        temporary.replace(self.path)
        return state
