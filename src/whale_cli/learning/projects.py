"""Project companionship: record a plan and clone only after runtime approval."""
from __future__ import annotations

import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from ..security import WorkspaceViolation, resolve_workspace_path
from .store import LearningStore


_PROJECT_URL = re.compile(r"^https://(?:github\.com|gitee\.com)/[^/]+/[^/]+/?(?:\.git)?$")


class ProjectCompanion:
    def __init__(self, store: LearningStore, workspace: str | Path) -> None:
        self.store = store
        self.workspace = Path(workspace).resolve()

    def plan(
        self,
        *,
        title: str,
        url: str,
        goal: str,
        learning_value: str = "",
        prerequisites: list[str] | None = None,
        outcomes: list[str] | None = None,
        first_action: str = "",
    ) -> dict[str, Any]:
        if not title.strip() or not goal.strip():
            raise ValueError("title and goal cannot be empty")
        if not _PROJECT_URL.match(url.strip()):
            raise ValueError("project URL must be a direct GitHub or Gitee repository URL")
        parsed = urlparse(url)
        suggested_directory = Path(parsed.path.rstrip("/")).name.removesuffix(".git")
        required = self._clean_list(prerequisites)
        expected_outcomes = self._clean_list(outcomes)
        first_step = first_action.strip() or "阅读 README，标出运行入口、输入输出和一个想验证的问题。"
        record = {
            "id": f"project-{suggested_directory}",
            "title": title.strip(),
            "url": url.strip(),
            "goal": goal.strip(),
            "learning_value": learning_value.strip() or goal.strip(),
            "prerequisites": required,
            "outcomes": expected_outcomes or ["完成一个可复现的最小改动，并能解释它解决的问题。"],
            "first_action": first_step,
            "directory": suggested_directory,
            "status": "planned",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "milestones": [
                {"id": "understand", "title": "理解项目定位", "purpose": "确认它与当前学习目标的关系。", "evidence": "写下 README 中最关键的一个输入、输出或设计选择。", "status": "pending"},
                {"id": "verify", "title": "验证最小闭环", "purpose": "只验证一个最小示例，不执行未理解的脚本。", "evidence": "保留命令、预期结果与实际观察。", "status": "pending"},
                {"id": "adapt", "title": "完成一次有解释的改动", "purpose": "把项目知识转化为自己的能力。", "evidence": "说明改动、验证结果与仍未解决的问题。", "status": "pending"},
            ],
        }

        def apply(state: dict[str, Any]) -> None:
            state["projects"] = [item for item in state["projects"] if item.get("id") != record["id"]]
            state["projects"].append(record)

        self.store.update(apply)
        return record

    def clone(self, *, url: str, directory: str) -> dict[str, Any]:
        if not _PROJECT_URL.match(url.strip()):
            raise ValueError("project URL must be a direct GitHub or Gitee repository URL")
        try:
            target = resolve_workspace_path(directory, self.workspace)
        except WorkspaceViolation as exc:
            raise ValueError(str(exc)) from exc
        if target.exists():
            raise ValueError(f"target directory already exists: {target.relative_to(self.workspace)}")
        result = subprocess.run(
            ["git", "clone", "--depth", "1", url.strip(), str(target)],
            cwd=self.workspace,
            capture_output=True,
            text=True,
            timeout=120,
            encoding="utf-8",
            errors="replace",
        )
        if result.returncode != 0:
            raise RuntimeError(result.stderr.strip() or "git clone failed")
        relative_directory = str(target.relative_to(self.workspace))

        def apply(state: dict[str, Any]) -> None:
            for project in state["projects"]:
                if project.get("url") == url.strip() or project.get("directory") == directory.strip():
                    project["directory"] = relative_directory
                    project["status"] = "ready"
                    project["cloned_at"] = datetime.now(timezone.utc).isoformat()

        self.store.update(apply)
        return {"directory": relative_directory, "stdout": result.stdout.strip(), "next_action": "先完成“理解项目定位”，再决定是否运行最小示例。"}

    @staticmethod
    def _clean_list(values: object) -> list[str]:
        if not isinstance(values, list):
            return []
        return list(dict.fromkeys(str(value).strip()[:240] for value in values if str(value).strip()))[:8]
