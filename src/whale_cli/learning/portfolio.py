"""Turn local learning evidence into a reviewable Markdown portfolio."""
from __future__ import annotations

from datetime import date

from .store import LearningStore


class LearningPortfolio:
    def __init__(self, store: LearningStore) -> None:
        self.store = store

    def add_evidence(
        self,
        *,
        title: str,
        detail: str,
        kind: str = "note",
        concepts: list[str] | None = None,
        outcome: str = "",
        artifact: str = "",
        next_action: str = "",
    ) -> dict[str, object]:
        if kind not in {"note", "exercise", "project", "reflection", "contribution"}:
            raise ValueError("unsupported evidence kind")
        if not title.strip() or not detail.strip():
            raise ValueError("title and detail cannot be empty")
        evidence = {
            "title": title.strip(),
            "detail": detail.strip(),
            "kind": kind,
            "concepts": self._clean_list(concepts),
            "outcome": outcome.strip(),
            "artifact": artifact.strip(),
            "next_action": next_action.strip(),
            "date": date.today().isoformat(),
        }

        def apply(state: dict) -> None:
            state["evidence"].append(evidence)

        self.store.update(apply)
        return evidence

    def report(self) -> str:
        state = self.store.read()
        profile = state["profile"]
        lines = ["# 我的学习档案", ""]
        if profile:
            lines.extend(["## 当前目标", f"- 基础：{profile['level']}", f"- 目标：{profile['goal']}", f"- 每周投入：{profile['weekly_hours']} 小时", ""])
        lines.extend(["## 知识地图"])
        for node in sorted(state["knowledge_nodes"].values(), key=lambda item: item["title"]):
            lines.append(f"- {node['title']}：掌握度 {node['mastery']}/5")
        if not state["knowledge_nodes"]:
            lines.append("- 尚未登记概念。")
        lines.extend(["", "## 项目陪学进展"])
        for project in state["projects"]:
            lines.extend([
                f"### {project['title']} · {project['status']}",
                f"- 学习价值：{project.get('learning_value') or project['goal']}",
                f"- 当前目标：{project['goal']}",
                f"- 前置条件：{'、'.join(project.get('prerequisites') or []) or '待确认'}",
                f"- 可验证产出：{'、'.join(project.get('outcomes') or []) or '待补充'}",
                f"- 下一步：{project.get('first_action') or '阅读 README，确认项目入口。'}",
            ])
        lines.extend(["", "## 能力与证据"])
        for evidence in state["evidence"]:
            lines.append(f"### [{evidence['kind']}] {evidence['title']} · {evidence['date']}")
            lines.append(f"- 事实：{evidence['detail']}")
            if evidence.get("concepts"):
                lines.append(f"- 关联知识：{'、'.join(evidence['concepts'])}")
            if evidence.get("outcome"):
                lines.append(f"- 能力变化：{evidence['outcome']}")
            if evidence.get("artifact"):
                lines.append(f"- 可回看产出：{evidence['artifact']}")
            if evidence.get("next_action"):
                lines.append(f"- 下一步：{evidence['next_action']}")
        if not state["projects"] and not state["evidence"]:
            lines.append("- 尚未记录项目或学习证据。")
        contributions = [item for item in state["evidence"] if item.get("kind") == "contribution"]
        lines.extend(["", "## 可贡献给社区的补充"])
        if contributions:
            for contribution in contributions:
                lines.extend([
                    f"### 草稿：{contribution['title']}",
                    f"- 观察到的问题：{contribution['detail']}",
                    f"- 关联知识：{'、'.join(contribution.get('concepts') or []) or '待补充'}",
                    f"- 建议补充：{contribution.get('outcome') or '待补充'}",
                    f"- 复现或资料：{contribution.get('artifact') or '待补充'}",
                    "- 状态：仅为本地草稿，需人工审阅后手动创建 issue 或 PR。",
                ])
        else:
            lines.append("- 选择一个已解决的卡点，说明前置条件、复现步骤和参考资料；将此草稿人工审阅后再提交 PR。")
        lines.append("")
        return "\n".join(lines)

    def snapshot(self) -> dict[str, object]:
        """Return a read-only WebUI view backed only by local learner records."""
        state = self.store.read()
        evidence = list(reversed(state["evidence"]))
        contributions = [item for item in evidence if item.get("kind") == "contribution"]
        return {
            "profile": state["profile"],
            "projects": state["projects"],
            "evidence": evidence,
            "contributions": contributions,
            "summary": {
                "project_count": len(state["projects"]),
                "evidence_count": len(evidence),
                "contribution_count": len(contributions),
                "concept_count": len(state["knowledge_nodes"]),
            },
            "report": self.report(),
            "source": ".whale_cli/learning/state.json",
        }

    @staticmethod
    def _clean_list(values: object) -> list[str]:
        if not isinstance(values, list):
            return []
        return list(dict.fromkeys(str(value).strip()[:160] for value in values if str(value).strip()))[:8]
