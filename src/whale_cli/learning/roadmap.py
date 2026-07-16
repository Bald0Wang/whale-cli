"""Rule-based next-step planning over an explicit knowledge graph."""
from __future__ import annotations

import json
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from .profile import LearnerProfileService
from .store import LearningStore


class RoadmapPlanner:
    def __init__(self, store: LearningStore, profiles: LearnerProfileService) -> None:
        self.store = store
        self.profiles = profiles

    def preview(self, *, weeks: int = 4) -> list[dict[str, Any]]:
        """Build a route proposal without changing learner state or files."""
        if not 1 <= weeks <= 16:
            raise ValueError("weeks must be between 1 and 16")
        missing = self.profiles.missing_fields()
        if missing:
            raise ValueError(f"learning profile is incomplete: {', '.join(missing)}")
        state = self.store.read()
        nodes = state["knowledge_nodes"]
        prerequisites = {
            edge["target"]: edge["source"]
            for edge in state["knowledge_links"]
            if edge["relation"] == "prerequisite"
        }
        candidates = sorted(nodes.values(), key=lambda node: (node["mastery"], node["title"]))
        profile = state["profile"]
        hours = profile["weekly_hours"]
        items: list[dict[str, Any]] = []
        for node in candidates:
            if node["mastery"] >= 4:
                continue
            required = prerequisites.get(node["id"])
            if required and nodes[required]["mastery"] < 2:
                continue
            week = min(len(items) + 1, weeks)
            item = {
                "id": f"roadmap-{node['id']}",
                "week": week,
                "concept_id": node["id"],
                "title": f"掌握 {node['title']}",
                "estimated_hours": min(max(1, round(hours * 0.6, 1)), 8),
                "status": "todo",
                "reason": "当前掌握度较低，且已满足已记录的前置条件。",
            }
            item["subtasks"] = self._build_subtasks(item)
            items.append(item)
            if len(items) >= weeks:
                break
        if not items:
            item = {
                "id": "roadmap-reflect",
                "week": 1,
                "concept_id": "",
                "title": "复盘已完成主题并选择一个应用项目",
                "estimated_hours": min(max(1, round(hours * 0.4, 1)), 4),
                "status": "todo",
                "reason": "现有概念已达到较高掌握度，下一步应该以输出和项目验证为主。",
            }
            item["subtasks"] = self._build_subtasks(item)
            items.append(item)

        return items

    def generate(self, *, weeks: int = 4) -> list[dict[str, Any]]:
        """Persist a route only after its preview has been accepted."""
        items = self.preview(weeks=weeks)
        state = self.store.read()
        profile = state["profile"]
        generated_at = datetime.now(timezone.utc).isoformat()
        route_id = f"route-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')}-{uuid4().hex[:8]}"
        for item in items:
            item["route_id"] = route_id
            for subtask in item["subtasks"]:
                subtask["parent_id"] = item["id"]

        def apply(current: dict[str, Any]) -> None:
            current["roadmap"] = [
                *items,
                {"generated_at": generated_at, "profile_goal": profile["goal"], "route_id": route_id},
            ]

        self.store.update(apply)
        self._write_snapshot(
            {
                "version": 1,
                "id": route_id,
                "generated_at": generated_at,
                "profile": deepcopy(profile),
                "items": deepcopy(items),
                "summary": self._summary(items),
            }
        )
        return items

    def mark_done(self, roadmap_id: str) -> dict[str, Any]:
        completed_id = ""

        def apply(state: dict[str, Any]) -> None:
            nonlocal completed_id
            metadata = next((item for item in state["roadmap"] if not item.get("id")), {})
            target_id = roadmap_id
            if roadmap_id and roadmap_id == metadata.get("route_id"):
                pending = [item for item in state["roadmap"] if item.get("id") and item.get("status") != "done"]
                if len(pending) != 1:
                    raise ValueError("route id can be completed only when exactly one roadmap item is unfinished")
                target_id = str(pending[0]["id"])
            for item in state["roadmap"]:
                if not item.get("id"):
                    continue
                self._ensure_subtasks(item)
                if item["id"] == target_id:
                    # Retain the CLI's existing whole-goal completion action while
                    # letting the WebUI normally close individual learning steps.
                    for subtask in item["subtasks"]:
                        subtask["status"] = "done"
                        subtask.setdefault("completed_at", datetime.now(timezone.utc).isoformat())
                    self._refresh_parent_status(item)
                    completed_id = target_id
                    return
                for subtask in item["subtasks"]:
                    if subtask["id"] == target_id:
                        subtask["status"] = "done"
                        subtask["completed_at"] = datetime.now(timezone.utc).isoformat()
                        self._refresh_parent_status(item)
                        completed_id = target_id
                        return
            raise ValueError(f"unknown roadmap item: {roadmap_id}")

        state = self.store.update(apply)
        completed = self._find_item_or_subtask(state["roadmap"], completed_id)
        route_id = next((item.get("route_id", "") for item in state["roadmap"] if not item.get("id")), "")
        if route_id:
            self._refresh_snapshot(route_id, state)
        return completed

    def current(self) -> dict[str, Any]:
        """Expose the active route before changing its completion state."""
        state = self.store.read()
        metadata = next((item for item in state["roadmap"] if not item.get("id")), {})
        return {
            "route_id": metadata.get("route_id", ""),
            "generated_at": metadata.get("generated_at", ""),
            "profile_goal": metadata.get("profile_goal", ""),
            "items": [self._normalise_item(item) for item in state["roadmap"] if item.get("id")],
        }

    def history(self, *, limit: int = 30) -> list[dict[str, Any]]:
        """Return saved roadmap JSON snapshots, newest first."""
        if limit < 1:
            return []
        snapshots = [self._read_snapshot(path) for path in self._archive_root().glob("*.json")]
        routes = [self._normalise_snapshot(snapshot) for snapshot in snapshots if snapshot is not None]
        routes.sort(key=lambda route: (str(route.get("generated_at", "")), str(route.get("id", ""))), reverse=True)
        return routes[:limit]

    def route(self, route_id: str) -> dict[str, Any]:
        """Read one saved route by its persisted identifier."""
        route_id = route_id.strip()
        for route in self.history(limit=200):
            if route.get("id") == route_id:
                return route
        raise ValueError("unknown learning roadmap")

    def _archive_root(self) -> Path:
        return self.store.path.parent / "roadmaps"

    def _snapshot_path(self, route_id: str) -> Path:
        return self._archive_root() / f"{route_id}.json"

    def _write_snapshot(self, snapshot: dict[str, Any]) -> None:
        route_id = str(snapshot.get("id", ""))
        if not route_id.startswith("route-") or "/" in route_id or "\\" in route_id:
            raise ValueError("invalid learning roadmap id")
        target = self._snapshot_path(route_id)
        target.parent.mkdir(parents=True, exist_ok=True)
        temporary = target.with_suffix(".tmp")
        temporary.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        temporary.replace(target)

    def _read_snapshot(self, path: Path) -> dict[str, Any] | None:
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None
        if not isinstance(raw, dict) or not isinstance(raw.get("id"), str) or not isinstance(raw.get("items"), list):
            return None
        return raw

    def _refresh_snapshot(self, route_id: str, state: dict[str, Any]) -> None:
        path = self._snapshot_path(route_id)
        snapshot = self._read_snapshot(path)
        if snapshot is None:
            return
        items = [self._normalise_item(item) for item in state["roadmap"] if item.get("id")]
        snapshot["items"] = items
        snapshot["summary"] = self._summary(items)
        snapshot["updated_at"] = datetime.now(timezone.utc).isoformat()
        self._write_snapshot(snapshot)

    @classmethod
    def _summary(cls, items: list[dict[str, Any]]) -> dict[str, Any]:
        normalised = [cls._normalise_item(item) for item in items]
        subtasks = [subtask for item in normalised for subtask in item["subtasks"]]
        return {
            "item_count": len(normalised),
            "done_count": sum(item.get("status") == "done" for item in normalised),
            "subtask_count": len(subtasks),
            "subtask_done_count": sum(subtask.get("status") == "done" for subtask in subtasks),
            "estimated_hours": round(sum(float(item.get("estimated_hours", 0)) for item in normalised), 1),
        }

    @classmethod
    def _normalise_snapshot(cls, snapshot: dict[str, Any]) -> dict[str, Any]:
        result = deepcopy(snapshot)
        result["items"] = [cls._normalise_item(item) for item in result["items"]]
        result["summary"] = cls._summary(result["items"])
        return result

    @classmethod
    def _normalise_item(cls, item: dict[str, Any]) -> dict[str, Any]:
        result = deepcopy(item)
        existing = result.get("subtasks")
        if not isinstance(existing, list) or not existing:
            result["subtasks"] = cls._build_subtasks(result, completed=result.get("status") == "done")
        else:
            result["subtasks"] = [
                {
                    **subtask,
                    "parent_id": subtask.get("parent_id") or result.get("id", ""),
                    "status": subtask.get("status", "todo"),
                }
                for subtask in existing
                if isinstance(subtask, dict) and subtask.get("id")
            ]
            if not result["subtasks"]:
                result["subtasks"] = cls._build_subtasks(result, completed=result.get("status") == "done")
        cls._refresh_parent_status(result)
        return result

    @classmethod
    def _ensure_subtasks(cls, item: dict[str, Any]) -> None:
        normalised = cls._normalise_item(item)
        item.clear()
        item.update(normalised)

    @classmethod
    def _build_subtasks(cls, item: dict[str, Any], *, completed: bool = False) -> list[dict[str, Any]]:
        total = max(0.6, float(item.get("estimated_hours", 1)))
        first = round(total * 0.25, 1)
        second = round(total * 0.55, 1)
        third = round(max(0.1, total - first - second), 1)
        focus = str(item.get("title", "学习任务")).removeprefix("掌握 ")
        status = "done" if completed else "todo"
        completed_at = item.get("completed_at") if completed else None
        definitions = [
            ("understand", f"明确 {focus} 的核心概念", "阅读入口材料，写下 3 个关键词和 1 个待解决的问题。", first),
            ("practice", f"完成 {focus} 的最小练习", "完成一次可验证的输入、过程和结果，不追求做大。", second),
            ("reflect", f"沉淀 {focus} 的学习记录", "记录产出、卡点和下一次需要复习的内容。", third),
        ]
        subtasks: list[dict[str, Any]] = []
        for suffix, title, detail, hours in definitions:
            subtask = {
                "id": f"{item.get('id', 'roadmap-task')}-{suffix}",
                "parent_id": item.get("id", ""),
                "title": title,
                "detail": detail,
                "estimated_hours": hours,
                "status": status,
            }
            if completed_at:
                subtask["completed_at"] = completed_at
            subtasks.append(subtask)
        return subtasks

    @staticmethod
    def _refresh_parent_status(item: dict[str, Any]) -> None:
        subtasks = item.get("subtasks", [])
        if subtasks and all(subtask.get("status") == "done" for subtask in subtasks):
            item["status"] = "done"
            item.setdefault("completed_at", datetime.now(timezone.utc).isoformat())
        elif any(subtask.get("status") == "done" for subtask in subtasks):
            item["status"] = "in_progress"
            item.pop("completed_at", None)
        else:
            item["status"] = "todo"
            item.pop("completed_at", None)

    @staticmethod
    def _find_item_or_subtask(items: list[dict[str, Any]], item_id: str) -> dict[str, Any]:
        for item in items:
            if item.get("id") == item_id:
                return item
            for subtask in item.get("subtasks", []):
                if subtask.get("id") == item_id:
                    return subtask
        raise ValueError(f"unknown roadmap item: {item_id}")
