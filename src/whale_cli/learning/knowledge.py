"""A transparent directed graph with reverse links computed at read time."""
from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any

from .store import LearningStore


def concept_id(title: str) -> str:
    value = re.sub(r"[^a-z0-9\u4e00-\u9fff]+", "-", title.strip().lower()).strip("-")
    if not value:
        raise ValueError("concept title cannot be empty")
    return value[:80]


class KnowledgeMap:
    """Store concepts once and expose both outgoing and incoming links."""

    def __init__(self, store: LearningStore) -> None:
        self.store = store

    def add_node(self, *, title: str, kind: str = "concept", mastery: int = 0, note: str = "") -> dict[str, Any]:
        if kind not in {"concept", "resource", "project", "note"}:
            raise ValueError("kind must be concept, resource, project, or note")
        if not 0 <= mastery <= 5:
            raise ValueError("mastery must be between 0 and 5")
        node_id = concept_id(title)

        def apply(state: dict[str, Any]) -> None:
            previous = state["knowledge_nodes"].get(node_id, {})
            state["knowledge_nodes"][node_id] = {
                "id": node_id,
                "title": title.strip(),
                "kind": kind,
                "mastery": mastery,
                "note": note.strip(),
                "updated_at": datetime.now(timezone.utc).isoformat(),
                "created_at": previous.get("created_at", datetime.now(timezone.utc).isoformat()),
            }

        return self.store.update(apply)["knowledge_nodes"][node_id]

    def link(self, *, source: str, target: str, relation: str = "prerequisite") -> dict[str, str]:
        if relation not in {"prerequisite", "related", "evidence_for"}:
            raise ValueError("relation must be prerequisite, related, or evidence_for")
        if source == target:
            raise ValueError("a concept cannot link to itself")

        def apply(state: dict[str, Any]) -> None:
            nodes = state["knowledge_nodes"]
            if source not in nodes or target not in nodes:
                raise ValueError("both source and target concepts must exist")
            edge = {"source": source, "target": target, "relation": relation}
            if edge not in state["knowledge_links"]:
                state["knowledge_links"].append(edge)

        self.store.update(apply)
        return {"source": source, "target": target, "relation": relation}

    def node(self, node_id: str) -> dict[str, Any]:
        state = self.store.read()
        node = state["knowledge_nodes"].get(node_id)
        if not node:
            raise ValueError(f"unknown concept: {node_id}")
        outgoing = [edge for edge in state["knowledge_links"] if edge["source"] == node_id]
        incoming = [edge for edge in state["knowledge_links"] if edge["target"] == node_id]
        return {**node, "links_to": outgoing, "linked_from": incoming}

    def overview(self) -> list[dict[str, Any]]:
        state = self.store.read()
        return [self.node(node_id) for node_id in sorted(state["knowledge_nodes"])]
