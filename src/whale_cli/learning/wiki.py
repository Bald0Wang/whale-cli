"""Export the local learning graph as an Obsidian-compatible Markdown vault."""
from __future__ import annotations

import json
import os
import platform
import secrets
import shutil
import subprocess
import tempfile
import time
from hashlib import sha256
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import quote

from ..security import WorkspaceViolation, resolve_workspace_path
from .store import LearningStore


DEFAULT_VAULT_DIR = "learning-wiki"
GRAPH_FILENAME = ".whale-graph.json"


class ObsidianLearningWiki:
    """Maintain a transparent local vault from the learner's graph state.

    The Markdown layout intentionally follows the portable part of the
    llm-wiki pattern: a purpose page, schema, index, log, YAML frontmatter,
    and Obsidian ``[[wikilinks]]``. The graph JSON is a portable cache next to
    the export; Obsidian ignores it, while the WebUI reads the live local map.
    """

    _SECTION_LABELS = {
        "positioning": "学习定位",
        "value": "为什么值得学",
        "model": "核心模型",
        "outcome": "学完能做什么",
        "action": "下一步行动",
        "reflection": "学习提醒",
    }

    def __init__(self, store: LearningStore, workspace: str | Path) -> None:
        self.store = store
        self.workspace = Path(workspace).resolve()

    def status(self) -> dict[str, Any]:
        state = self.store.read()
        vault_dir = str(state["wiki"].get("vault_dir") or DEFAULT_VAULT_DIR)
        try:
            root = self._resolve_vault(vault_dir)
        except ValueError:
            return {"ready": False, "vault_dir": vault_dir, "reason": "vault path is outside the workspace"}
        graph_path = root / GRAPH_FILENAME
        graph = self._read_graph(graph_path)
        conversations_root = root / "conversations"
        conversation_pages = [path for path in conversations_root.glob("*.md") if path.name != "index.md"] if conversations_root.is_dir() else []
        graph_nodes = (graph or {}).get("nodes", [])
        topic_count = sum(isinstance(node, dict) and node.get("kind") == "topic" for node in graph_nodes)
        if graph_nodes and not topic_count:
            topic_count = len(graph_nodes)
        return {
            "ready": graph is not None,
            "vault_dir": vault_dir,
            "vault_path": str(root),
            "node_count": topic_count,
            "structure_node_count": max(0, len(graph_nodes) - topic_count),
            "edge_count": len((graph or {}).get("edges", [])),
            "index_path": str(root / "index.md"),
            "auto_capture": bool(state["wiki"].get("auto_capture", False)),
            "conversation_count": len(conversation_pages),
            "conversation_index_path": str(conversations_root / "index.md"),
        }

    def initialize(self, *, vault_dir: str = DEFAULT_VAULT_DIR, title: str = "Whale 学习 Wiki") -> dict[str, Any]:
        root = self._resolve_vault(vault_dir)
        root.mkdir(parents=True, exist_ok=True)
        (root / "concepts").mkdir(exist_ok=True)
        (root / "conversations").mkdir(exist_ok=True)
        (root / "sources").mkdir(exist_ok=True)
        # A vault-local marker lets Obsidian treat this generated folder as a vault.
        (root / ".obsidian").mkdir(exist_ok=True)
        self._write_if_missing(root / ".obsidian" / "app.json", "{}\n")
        self._write_if_missing(root / ".wiki-schema.md", self._schema(title))
        self._write_if_missing(root / "purpose.md", self._purpose(title))
        self._write_if_missing(root / "index.md", self._index(title, []))
        self._write_if_missing(root / "log.md", "# Whale 学习 Wiki 操作记录\n\n")
        self._write_if_missing(root / "conversations" / "index.md", self._conversation_index([]))
        self._remember_vault(vault_dir, title)
        return self.status()

    def sync(self, *, vault_dir: str = "", title: str = "") -> dict[str, Any]:
        state = self.store.read()
        configured = str(state["wiki"].get("vault_dir") or DEFAULT_VAULT_DIR)
        selected_dir = vault_dir.strip() or configured
        selected_title = title.strip() or str(state["wiki"].get("title") or "Whale 学习 Wiki")
        self.initialize(vault_dir=selected_dir, title=selected_title)
        root = self._resolve_vault(selected_dir)
        nodes = state["knowledge_nodes"]
        edges = state["knowledge_links"]
        outlines = state["wiki_outlines"]
        for node_id, node in sorted(nodes.items()):
            path = root / "concepts" / f"{node_id}.md"
            path.write_text(self._node_page(node, edges, nodes, outlines), encoding="utf-8")
        graph = self.graph_snapshot(title=selected_title)
        topic_nodes = [node for node in graph["nodes"] if node["kind"] == "topic"]
        (root / GRAPH_FILENAME).write_text(json.dumps(graph, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        (root / "index.md").write_text(self._index(selected_title, topic_nodes), encoding="utf-8")
        with (root / "log.md").open("a", encoding="utf-8") as log:
            log.write(f"- {graph['generated_at']}: 同步 {len(topic_nodes)} 个主题、{len(graph['edges'])} 条关系。\n")
        self._remember_vault(selected_dir, selected_title)
        return {**self.status(), "changed_files": self._changed_paths(root, topic_nodes)}

    def graph_snapshot(self, *, title: str = "") -> dict[str, Any]:
        """Return a live LLM-Wiki-style topic graph without exporting first."""
        state = self.store.read()
        selected_title = title.strip() or str(state["wiki"].get("title") or "Whale 学习 Wiki")
        nodes = state["knowledge_nodes"]
        graph_nodes: list[dict[str, Any]] = []
        graph_edges: list[dict[str, str]] = []
        for node_id, node in sorted(nodes.items()):
            outline = self._outline_for(state, node_id)
            graph_nodes.append({
                "id": node_id,
                "topic_id": node_id,
                "title": node["title"],
                "kind": "topic",
                "badge": "主题",
                "summary": outline["learning_value"] or outline["positioning"] or outline["definition"] or node.get("note", "") or "尚未拆解；可通过对话说明它在路线中的价值。",
                "path": f"concepts/{node_id}.md",
                "outline_status": "ready" if node_id in state["wiki_outlines"] else "needs_outline",
            })
            for section, title, content in self._outline_cards(outline):
                card_id = f"{node_id}--{section}"
                graph_nodes.append({
                    "id": card_id,
                    "topic_id": node_id,
                    "title": title,
                    "kind": section,
                    "badge": self._SECTION_LABELS[section],
                    "summary": content,
                    "path": f"concepts/{node_id}.md",
                    "section": section,
                    "outline_status": "ready" if node_id in state["wiki_outlines"] else "needs_outline",
                })
                graph_edges.append({"source": node_id, "target": card_id, "relation": "contains"})
        graph_edges.extend(
            edge
            for edge in state["knowledge_links"]
            if edge["source"] in nodes and edge["target"] in nodes
        )
        return {
            "version": 2,
            "title": selected_title,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "source": "local_learning_wiki_outline",
            "nodes": graph_nodes,
            "edges": graph_edges,
        }

    def render_node_page(self, node_id: str) -> dict[str, Any]:
        """Render the current concept page without requiring a file export."""
        state = self.store.read()
        graph = self.graph_snapshot()
        graph_node = next((item for item in graph["nodes"] if item["id"] == node_id), None)
        if not graph_node:
            raise ValueError("学习图谱中不存在这个节点。")
        topic_id = str(graph_node["topic_id"])
        node = state["knowledge_nodes"][topic_id]
        return {
            "node": graph_node,
            "content": self._node_page(node, state["knowledge_links"], state["knowledge_nodes"], state["wiki_outlines"]),
            "path": graph_node["path"],
            "source": "local_learning_wiki_outline",
        }

    def save_outline(
        self,
        *,
        concept_id: str,
        positioning: str = "",
        learning_value: str = "",
        outcomes: list[str] | None = None,
        definition: str = "",
        mechanism: str = "",
        key_terms: list[str] | None = None,
        practice: str = "",
        pitfalls: list[str] | None = None,
        questions: list[str] | None = None,
        sources: list[str] | None = None,
    ) -> dict[str, Any]:
        """Persist one LLM-produced, learner-reviewable topic decomposition."""
        concept_id = concept_id.strip()
        if not concept_id:
            raise ValueError("concept_id is required")
        fields = {
            "positioning": positioning.strip(),
            "learning_value": learning_value.strip(),
            "outcomes": self._clean_list(outcomes),
            "definition": definition.strip(),
            "mechanism": mechanism.strip(),
            "key_terms": self._clean_list(key_terms),
            "practice": practice.strip(),
            "pitfalls": self._clean_list(pitfalls),
            "questions": self._clean_list(questions),
            "sources": self._clean_list(sources),
        }
        if not any(fields.values()):
            raise ValueError("at least one outline field is required")

        def apply(state: dict[str, Any]) -> None:
            if concept_id not in state["knowledge_nodes"]:
                raise ValueError("unknown concept")
            state["wiki_outlines"][concept_id] = {
                "concept_id": concept_id,
                **fields,
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }

        return self.store.update(apply)["wiki_outlines"][concept_id]

    def set_auto_capture(self, *, enabled: bool) -> dict[str, Any]:
        """Explicitly opt in or out of storing future completed turns locally."""
        state = self.store.read()
        vault_dir = str(state["wiki"].get("vault_dir") or DEFAULT_VAULT_DIR)
        title = str(state["wiki"].get("title") or "Whale 学习 Wiki")

        def apply(next_state: dict[str, Any]) -> None:
            wiki = next_state["wiki"]
            wiki["vault_dir"] = vault_dir
            wiki["title"] = title
            wiki["auto_capture"] = bool(enabled)
            wiki["updated_at"] = datetime.now(timezone.utc).isoformat()

        self.store.update(apply)
        if enabled:
            self.initialize(vault_dir=vault_dir, title=title)
        return self.status()

    def capture_conversation_turn(
        self,
        *,
        user_message: str,
        assistant_message: str,
        session_id: str = "",
        model: str = "",
    ) -> dict[str, Any] | None:
        """Persist one completed turn when the learner explicitly enabled it.

        This intentionally stores only the user text and final assistant text.
        Tool transcripts, hidden reasoning, attachments, and multimodal binary
        content remain outside the Wiki.
        """
        state = self.store.read()
        if not bool(state["wiki"].get("auto_capture", False)):
            return None
        prompt = user_message.strip()
        reply = assistant_message.strip()
        if not prompt or not reply:
            return None

        vault_dir = str(state["wiki"].get("vault_dir") or DEFAULT_VAULT_DIR)
        title = str(state["wiki"].get("title") or "Whale 学习 Wiki")
        self.initialize(vault_dir=vault_dir, title=title)
        root = self._resolve_vault(vault_dir)
        captured_at = datetime.now(timezone.utc)
        page_id = f"{captured_at.strftime('%Y%m%dT%H%M%SZ')}-{sha256(f'{session_id}|{prompt}|{reply}'.encode('utf-8')).hexdigest()[:10]}"
        relative_path = Path("conversations") / f"{page_id}.md"
        page_path = root / relative_path
        page_title = self._conversation_title(prompt)
        page_path.write_text(
            self._conversation_page(
                title=page_title,
                captured_at=captured_at,
                session_id=session_id,
                model=model,
                prompt=prompt,
                reply=reply,
            ),
            encoding="utf-8",
        )
        conversation_index = root / "conversations" / "index.md"
        existing = conversation_index.read_text(encoding="utf-8") if conversation_index.exists() else self._conversation_index([])
        entry = f"- [[{page_id}|{page_title}]] · {captured_at.astimezone().strftime('%Y-%m-%d %H:%M')}\n"
        if entry not in existing:
            conversation_index.write_text(existing.rstrip() + "\n" + entry, encoding="utf-8")
        with (root / "log.md").open("a", encoding="utf-8") as log:
            log.write(f"- {captured_at.isoformat()}: 自动收录一轮对话：{page_title}\n")
        return {
            "path": str(page_path),
            "relative_path": str(relative_path),
            "title": page_title,
            "captured_at": captured_at.isoformat(),
        }

    def open_in_obsidian(self, *, node_id: str = "") -> dict[str, str]:
        """Ask the operating system to open the managed vault or one note.

        Writing stays inside the workspace. This method only opens the
        already-generated local files, and its Tool adapter requires approval.
        """
        status = self.status()
        if not status["ready"]:
            raise ValueError("学习 Wiki 尚未生成，请先执行 LearningWiki sync。")
        state = self.store.read()
        self.initialize(
            vault_dir=status["vault_dir"],
            title=str(state["wiki"].get("title") or "Whale 学习 Wiki"),
        )
        root = self._resolve_vault(status["vault_dir"])
        target = root / "index.md"
        if node_id:
            graph = self._read_graph(root / GRAPH_FILENAME) or {}
            node = next((item for item in graph.get("nodes", []) if item.get("id") == node_id), None)
            if not isinstance(node, dict):
                raise ValueError(f"学习 Wiki 中不存在这个节点：{node_id}")
            relative = Path(str(node.get("path") or ""))
            if relative.is_absolute() or ".." in relative.parts:
                raise ValueError("学习 Wiki 节点路径无效。")
            target = (root / relative).resolve()
            try:
                target.relative_to(root)
            except ValueError as exc:
                raise ValueError("学习 Wiki 节点路径超出 vault。") from exc
        vault_id = self._register_managed_vault(root)
        relative_target = target.relative_to(root).as_posix()
        if vault_id:
            uri = f"obsidian://open?vault={quote(vault_id)}&file={quote(relative_target)}"
        else:
            uri = f"obsidian://open?path={quote(str(target))}"
        system = platform.system()
        if system == "Darwin":
            command = ["open", uri]
        elif system == "Windows":
            command = ["cmd", "/c", "start", "", uri]
        else:
            command = ["xdg-open", uri]
        try:
            result = subprocess.run(command, capture_output=True, text=True, timeout=10, check=False)
        except OSError as exc:
            raise RuntimeError(f"无法启动 Obsidian：{exc}") from exc
        if result.returncode != 0:
            detail = (result.stderr or result.stdout).strip() or "系统未能打开 Obsidian。"
            raise RuntimeError(detail)
        return {
            "target": str(target),
            "uri": uri,
            "launcher": command[0],
            "vault_id": vault_id or "",
            "note": "已登记 Whale 学习 Wiki 并请求 Obsidian 打开 index.md。",
        }

    def sync_to_existing_vault(self, *, vault_path: str = "") -> dict[str, Any]:
        """Mirror the managed export into a named folder of an explicit vault.

        An existing vault lives outside Whale's workspace policy, so callers
        must opt in with a concrete path (or OBSIDIAN_VAULT_PATH) and pass a
        separate approval gate. The mirror never overwrites arbitrary vault
        notes: all generated files stay below ``Whale Learning Wiki/``.
        """
        configured = vault_path.strip() or os.getenv("OBSIDIAN_VAULT_PATH", "").strip()
        if not configured:
            raise ValueError("请提供已有 Obsidian vault 路径，或设置 OBSIDIAN_VAULT_PATH。")
        external_root = Path(configured).expanduser().resolve()
        if not external_root.is_dir() or not (external_root / ".obsidian").is_dir():
            raise ValueError("指定路径不是已有 Obsidian vault：未找到 .obsidian 目录。")
        status = self.status()
        if not status["ready"]:
            self.sync()
            status = self.status()
        source = self._resolve_vault(status["vault_dir"])
        destination = external_root / "Whale Learning Wiki"
        resolved_destination = destination.resolve(strict=False)
        try:
            resolved_destination.relative_to(external_root)
        except ValueError as exc:
            raise ValueError("Obsidian 导出目录超出指定 vault。") from exc
        destination.mkdir(parents=True, exist_ok=True)
        copied: list[str] = []
        for source_path in source.rglob("*"):
            if not source_path.is_file():
                continue
            relative = source_path.relative_to(source)
            if relative.parts and relative.parts[0] == ".obsidian":
                continue
            target = destination / relative
            resolved_target = target.resolve(strict=False)
            try:
                resolved_target.relative_to(external_root)
            except ValueError as exc:
                raise ValueError("Obsidian 导出文件路径超出指定 vault。") from exc
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source_path, target)
            copied.append(str(target.relative_to(external_root)))
        return {
            "vault_path": str(external_root),
            "export_path": str(destination),
            "copied_files": copied,
            "note": "已同步到独立的 Whale Learning Wiki 子目录，未修改 vault 中其他笔记。",
        }

    def _resolve_vault(self, vault_dir: str) -> Path:
        try:
            return resolve_workspace_path(vault_dir, self.workspace)
        except WorkspaceViolation as exc:
            raise ValueError(str(exc)) from exc

    def _remember_vault(self, vault_dir: str, title: str) -> None:
        def apply(state: dict[str, Any]) -> None:
            wiki = state["wiki"]
            wiki["vault_dir"] = vault_dir
            wiki["title"] = title
            wiki["updated_at"] = datetime.now(timezone.utc).isoformat()

        self.store.update(apply)

    @staticmethod
    def _obsidian_config_path() -> Path | None:
        system = platform.system()
        if system == "Darwin":
            return Path.home() / "Library" / "Application Support" / "obsidian" / "obsidian.json"
        if system == "Windows":
            app_data = os.getenv("APPDATA")
            return Path(app_data) / "Obsidian" / "obsidian.json" if app_data else None
        config_home = os.getenv("XDG_CONFIG_HOME")
        return (Path(config_home) if config_home else Path.home() / ".config") / "obsidian" / "obsidian.json"

    def _register_managed_vault(self, root: Path) -> str | None:
        """Register the generated vault before using Obsidian's vault URI.

        Obsidian's ``path`` URI only resolves within a vault already known to
        the desktop app. Registration adds one isolated entry to its global
        vault list and uses an atomic replace to avoid a partial config file.
        """
        config_path = self._obsidian_config_path()
        if config_path is None or not config_path.parent.is_dir():
            return None
        try:
            payload = json.loads(config_path.read_text(encoding="utf-8")) if config_path.exists() else {}
        except (OSError, json.JSONDecodeError) as exc:
            raise RuntimeError(f"无法读取 Obsidian Vault 配置：{exc}") from exc
        if not isinstance(payload, dict):
            raise RuntimeError("Obsidian Vault 配置格式无效，已停止写入以保护原有配置。")
        vaults = payload.get("vaults")
        if vaults is None:
            vaults = {}
            payload["vaults"] = vaults
        if not isinstance(vaults, dict):
            raise RuntimeError("Obsidian Vault 列表格式无效，已停止写入以保护原有配置。")

        normalized_root = str(root.resolve())
        for vault_id, item in vaults.items():
            if isinstance(item, dict) and str(item.get("path") or "") == normalized_root:
                return str(vault_id)

        vault_id = secrets.token_hex(8)
        while vault_id in vaults:
            vault_id = secrets.token_hex(8)
        vaults[vault_id] = {"path": normalized_root, "ts": int(time.time() * 1000), "open": True}
        self._atomic_json_write(config_path, payload)
        return vault_id

    @staticmethod
    def _atomic_json_write(path: Path, payload: dict[str, Any]) -> None:
        try:
            fd, temporary_path = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump(payload, handle, ensure_ascii=False, separators=(",", ":"))
                handle.write("\n")
            os.replace(temporary_path, path)
        except OSError as exc:
            raise RuntimeError(f"无法登记 Obsidian Vault：{exc}") from exc

    @staticmethod
    def _write_if_missing(path: Path, content: str) -> None:
        if not path.exists():
            path.write_text(content, encoding="utf-8")

    @staticmethod
    def _read_graph(path: Path) -> dict[str, Any] | None:
        if not path.is_file():
            return None
        try:
            graph = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None
        return graph if isinstance(graph, dict) else None

    @staticmethod
    def _link(node: dict[str, Any]) -> str:
        return f"[[{node['id']}|{node['title']}]]"

    def _node_page(
        self,
        node: dict[str, Any],
        edges: list[dict[str, str]],
        nodes: dict[str, dict[str, Any]],
        outlines: dict[str, dict[str, Any]],
    ) -> str:
        incoming = [edge for edge in edges if edge["target"] == node["id"]]
        outgoing = [edge for edge in edges if edge["source"] == node["id"]]
        prerequisites = [self._link(nodes[edge["source"]]) for edge in incoming if edge["relation"] == "prerequisite"]
        unlocks = [self._link(nodes[edge["target"]]) for edge in outgoing if edge["relation"] == "prerequisite"]
        related = [
            self._link(nodes[edge["target"] if edge["source"] == node["id"] else edge["source"]])
            for edge in edges
            if edge["relation"] in {"related", "evidence_for"} and node["id"] in {edge["source"], edge["target"]}
        ]
        prerequisite_lines = [f"- {item}" for item in prerequisites] or ["- 无"]
        unlock_lines = [f"- {item}" for item in unlocks] or ["- 无"]
        related_lines = [f"- {item}" for item in related] or ["- 无"]
        outline = self._outline_for({"wiki_outlines": outlines}, node["id"])
        term_lines = [f"- {item}" for item in outline["key_terms"]] or ["- 待补充"]
        outcome_lines = [f"- {item}" for item in outline["outcomes"]] or ["- 待通过对话补充：学完后可以完成什么可观察的任务。"]
        pitfall_lines = [f"- {item}" for item in outline["pitfalls"]] or ["- 待补充"]
        question_lines = [f"- {item}" for item in outline["questions"]] or ["- 暂无"]
        source_lines = [f"- {item}" for item in outline["sources"]] or ["- 暂无；当前内容需要由学习者或可信资料补充。"]
        sections = [
            "---",
            f"title: {json.dumps(node['title'], ensure_ascii=False)}",
            "type: learning-topic",
            f"whale_id: {node['id']}",
            "generated_by: whale-cli",
            "outline: llm-wiki",
            "---",
            "",
            f"# {node['title']}",
            "",
            "## 学习定位",
            outline["positioning"] or "待通过对话补充：它处在当前学习路线的哪一段，需要先具备什么理解。",
            "",
            "## 为什么值得学",
            outline["learning_value"] or "待通过对话补充：它解决哪个真实问题，为什么现在值得投入时间。",
            "",
            "## 学完能做什么",
            *outcome_lines,
            "",
            "## 核心模型",
            outline["definition"] or "待通过对话补充：它是什么，解决什么问题，边界在哪里。",
            "",
            outline["mechanism"] or "待通过对话补充：按步骤描述输入、处理、输出与反馈。",
            "",
            "## 关键术语",
            *term_lines,
            "",
            "## 下一步行动",
            outline["practice"] or "待通过对话补充一个可验证的最小练习。",
            "",
            "## 学习提醒",
            "### 常见误区",
            *pitfall_lines,
            "",
            "### 待解问题",
            *question_lines,
            "",
            "## 前置知识",
            *prerequisite_lines,
            "",
            "## 可以解锁",
            *unlock_lines,
            "",
            "## 相关内容",
            *related_lines,
            "",
            "## 来源与证据",
            *source_lines,
            "",
        ]
        return "\n".join(sections)

    @classmethod
    def _outline_for(cls, state: dict[str, Any], concept_id: str) -> dict[str, Any]:
        saved = state.get("wiki_outlines", {}).get(concept_id, {})
        if not isinstance(saved, dict):
            saved = {}
        return {
            "positioning": str(saved.get("positioning") or "").strip(),
            "learning_value": str(saved.get("learning_value") or "").strip(),
            "outcomes": cls._clean_list(saved.get("outcomes")),
            "definition": str(saved.get("definition") or "").strip(),
            "mechanism": str(saved.get("mechanism") or "").strip(),
            "key_terms": cls._clean_list(saved.get("key_terms")),
            "practice": str(saved.get("practice") or "").strip(),
            "pitfalls": cls._clean_list(saved.get("pitfalls")),
            "questions": cls._clean_list(saved.get("questions")),
            "sources": cls._clean_list(saved.get("sources")),
        }

    @classmethod
    def _outline_cards(cls, outline: dict[str, Any]) -> list[tuple[str, str, str]]:
        return [
            ("positioning", "学习定位", outline["positioning"] or "待拆解：它在当前学习路线的哪一段，进入它前应具备什么理解。"),
            ("value", "为什么值得学", outline["learning_value"] or "待拆解：它解决什么问题，为什么值得在此刻学习。"),
            ("model", "核心模型", " ".join(item for item in [outline["definition"], outline["mechanism"]] if item) or "待拆解：用一个心智模型解释它怎样工作。"),
            ("outcome", "学完能做什么", " · ".join(outline["outcomes"]) or "待拆解：完成后可独立完成的可验证任务。"),
            ("action", "下一步行动", outline["practice"] or "待拆解：一个可以立即开始、能够验证结果的练习。"),
            ("reflection", "学习提醒", " · ".join(outline["pitfalls"] + outline["questions"]) or "待拆解：容易误解的地方，以及还需要追问的问题。"),
        ]

    @staticmethod
    def _clean_list(values: object) -> list[str]:
        if not isinstance(values, list):
            return []
        return list(dict.fromkeys(str(value).strip()[:240] for value in values if str(value).strip()))[:12]

    @staticmethod
    def _schema(title: str) -> str:
        return (
            f"# {title} 结构规则\n\n"
            "语言：中文\n\n"
            "- `concepts/` 存放由 Whale 学习图谱导出的概念页。\n"
            "- `conversations/` 存放用户明确开启后自动收录的对话页。\n"
            "- 每页使用 YAML frontmatter 和 Obsidian `[[wikilink]]`。\n"
            "- `index.md` 是导航入口，`log.md` 记录每次同步。\n"
            "- `.whale-graph.json` 是随导出携带的图谱缓存；WebUI 直接读取本地 KnowledgeMap，Obsidian 可以忽略它。\n"
        )

    @staticmethod
    def _purpose(title: str) -> str:
        return (
            f"# {title}\n\n"
            "目标：把 Datawhale 学习过程中的概念、前置条件、练习和项目证据整理为可回顾的本地 Wiki。\n\n"
            "使用方式：先在 Whale 中维护学习档案和知识地图，再同步到此目录；最后用 Obsidian 打开这个文件夹浏览链接与 Graph View。\n"
            "若开启自动收录，Whale 会把每轮用户提问与最终回复写到 `conversations/`，但不会保存工具原始输出、附件或隐藏推理。\n"
        )

    def _index(self, title: str, nodes: list[dict[str, Any]]) -> str:
        lines = [f"# {title}", "", "## 概念导航"]
        lines.extend(f"- [[{node['id']}|{node['title']}]]" for node in nodes)
        if not nodes:
            lines.append("- 暂无概念。先在 Whale 中使用 KnowledgeMap 创建节点，再执行同步。")
        return "\n".join([*lines, "", "## 对话沉淀", "- [[conversations/index|已收录的对话]]", ""])

    @staticmethod
    def _conversation_title(prompt: str) -> str:
        compact = " ".join(prompt.split())
        return compact[:60] + ("..." if len(compact) > 60 else "")

    @staticmethod
    def _conversation_index(entries: list[str]) -> str:
        lines = ["# 对话沉淀", "", "这里保存启用自动收录后，每轮对话的用户输入和最终回复。", ""]
        lines.extend(entries)
        return "\n".join([*lines, ""])

    @staticmethod
    def _conversation_page(
        *,
        title: str,
        captured_at: datetime,
        session_id: str,
        model: str,
        prompt: str,
        reply: str,
    ) -> str:
        return "\n".join(
            [
                "---",
                f"title: {json.dumps(title, ensure_ascii=False)}",
                "type: conversation",
                f"recorded_at: {captured_at.isoformat()}",
                f"session_id: {json.dumps(session_id, ensure_ascii=False)}",
                f"model: {json.dumps(model, ensure_ascii=False)}",
                "auto_captured: true",
                "generated_by: whale-cli",
                "---",
                "",
                f"# {title}",
                "",
                "## 用户输入",
                prompt,
                "",
                "## Whale 最终回复",
                reply,
                "",
                "## 导航",
                "- [学习 Wiki 首页](../index.md)",
                "- [[conversations/index|全部已收录对话]]",
                "",
            ]
        )

    @staticmethod
    def _changed_paths(root: Path, nodes: list[dict[str, Any]]) -> list[str]:
        return [
            str(root / ".wiki-schema.md"), str(root / "purpose.md"), str(root / "index.md"), str(root / "log.md"), str(root / GRAPH_FILENAME),
            *(str(root / node["path"]) for node in nodes),
        ]
