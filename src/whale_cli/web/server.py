#!/usr/bin/env python3
"""Installable local WebUI for Whale CLI.

Run with ``whale-web`` and open http://127.0.0.1:8765.
The UI intentionally uses only the Python standard library so learners can
inspect the complete transport boundary without a second build toolchain.
"""
from __future__ import annotations

import argparse
import base64
import binascii
import io
import json
import mimetypes
import os
import re
import sys
import threading
import time
import uuid
import zipfile
from dataclasses import dataclass, field
from email import policy
from email.parser import BytesParser
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, unquote, urlparse
from xml.etree import ElementTree

from whale_cli import __version__
from whale_cli.hooks import HookEngine  # noqa: E402
from whale_cli.learning import LearnerProfileService, LearningPortfolio, LearningStore, ObsidianLearningWiki, ReviewScheduler, RoadmapPlanner  # noqa: E402
from whale_cli.llm.client import LLMClient  # noqa: E402
from whale_cli.runtime import resolve_runtime_paths  # noqa: E402
from whale_cli.soul.approval import Approval  # noqa: E402
from whale_cli.soul.soul import Soul  # noqa: E402
from whale_cli.storage.session_store import SessionStore  # noqa: E402
from whale_cli.subagents import DatawhaleKnowledgeBase, DatawhaleKnowledgeBaseUpdater  # noqa: E402


PATHS = resolve_runtime_paths()
PROJECT_ROOT = PATHS.workspace
STATIC_ROOT = PATHS.static_root
TUTORIALS_ROOT = PATHS.tutorials_root
LEARNING_WIKI_ROOT = PATHS.learning_wiki
UPLOAD_ROOT = PATHS.uploads


@dataclass
class RunState:
    id: str
    prompt: str
    mode: str
    session_id: str
    attachment_ids: list[str] = field(default_factory=list)
    status: str = "queued"
    summary: str = ""
    steps: int = 0
    events: list[dict[str, Any]] = field(default_factory=list)
    messages: list[dict[str, str]] = field(default_factory=list)
    pending_approval: dict[str, str] | None = None
    approval_decision: str | None = None
    created_at: float = field(default_factory=time.time)
    condition: threading.Condition = field(default_factory=threading.Condition, repr=False)

    def add_event(self, kind: str, title: str, detail: str = "", **extra: Any) -> None:
        with self.condition:
            self.events.append(
                {
                    "id": uuid.uuid4().hex[:8],
                    "kind": kind,
                    "title": title,
                    "detail": detail,
                    "at": time.strftime("%H:%M:%S"),
                    **extra,
                }
            )
            self.condition.notify_all()

    def snapshot(self) -> dict[str, Any]:
        with self.condition:
            return {
                "id": self.id,
                "prompt": self.prompt,
                "mode": self.mode,
                "session_id": self.session_id,
                "attachment_ids": list(self.attachment_ids),
                "status": self.status,
                "summary": self.summary,
                "steps": self.steps,
                "events": list(self.events),
                "messages": list(self.messages),
                "pending_approval": self.pending_approval,
            }


class WebApproval(Approval):
    """Approval bridge that pauses an Agent thread until the browser answers."""

    def __init__(self, state: RunState, *, yolo: bool) -> None:
        super().__init__(prompt_fn=lambda _action, _description: "reject", yolo=yolo)
        self._state = state

    def request(self, action: str, description: str) -> bool:
        if self.is_yolo:
            self._state.add_event("approval", "YOLO mode allowed tool", description, action=action)
            return True

        with self._state.condition:
            self._state.pending_approval = {"action": action, "description": description}
            self._state.approval_decision = None
            self._state.events.append(
                {
                    "id": uuid.uuid4().hex[:8],
                    "kind": "approval",
                    "title": "Approval required",
                    "detail": description,
                    "action": action,
                    "at": time.strftime("%H:%M:%S"),
                }
            )
            self._state.condition.notify_all()
            self._state.condition.wait_for(
                lambda: self._state.approval_decision is not None,
                timeout=120,
            )
            decision = self._state.approval_decision or "reject"
            self._state.pending_approval = None
            self._state.approval_decision = None

        if decision == "approve_for_session":
            self._auto_approve_actions.add(action)
            return True
        return decision == "approve"


class RunStore:
    def __init__(self) -> None:
        self._runs: dict[str, RunState] = {}
        self._lock = threading.RLock()

    def create(self, prompt: str, mode: str, session_id: str, attachment_ids: list[str] | None = None) -> RunState:
        state = RunState(
            id=f"run_{uuid.uuid4().hex[:8]}",
            prompt=prompt,
            mode=mode,
            session_id=session_id,
            attachment_ids=attachment_ids or [],
        )
        with self._lock:
            self._runs[state.id] = state
        return state

    def get(self, run_id: str) -> RunState | None:
        with self._lock:
            return self._runs.get(run_id)

    def has_active_session(self, session_id: str) -> bool:
        with self._lock:
            return any(
                state.session_id == session_id and state.status in {"queued", "running"}
                for state in self._runs.values()
            )


RUNS = RunStore()


def _session_base_dir() -> str:
    return str(PATHS.home)


SESSIONS = SessionStore(base_dir=_session_base_dir())


SUPPORTED_UPLOAD_EXTENSIONS = {
    ".pdf", ".doc", ".docx", ".xls", ".xlsx", ".csv", ".json", ".txt", ".md",
    ".png", ".jpg", ".jpeg", ".ppt", ".pptx",
}
IMAGE_UPLOAD_EXTENSIONS = {".png", ".jpg", ".jpeg"}
TEXT_UPLOAD_EXTENSIONS = {".csv", ".json", ".txt", ".md"}
MAX_UPLOAD_BYTES = 24 * 1024 * 1024
MAX_DATAWHALE_KB_BYTES = 64 * 1024 * 1024
MAX_UPLOADS_PER_RUN = 8
MAX_ATTACHMENT_EXCERPT = 12_000
DATAWHALE_KB = DatawhaleKnowledgeBase(PATHS.datawhale_kb)
DATAWHALE_UPDATER = DatawhaleKnowledgeBaseUpdater(DATAWHALE_KB)


def _safe_upload_name(name: str) -> str:
    safe = Path(name).name.strip()
    if not safe or safe in {".", ".."}:
        raise ValueError("Attachment name is invalid.")
    if len(safe) > 180:
        raise ValueError("Attachment name is too long.")
    return safe


def _truncate_attachment_text(text: str) -> str:
    cleaned = "\n".join(line.rstrip() for line in text.replace("\x00", "").splitlines()).strip()
    if len(cleaned) <= MAX_ATTACHMENT_EXCERPT:
        return cleaned
    return cleaned[:MAX_ATTACHMENT_EXCERPT] + "\n\n[内容已截断]"


def _xml_text(raw: bytes) -> str:
    try:
        return " ".join(part.strip() for part in ElementTree.fromstring(raw).itertext() if part.strip())
    except ElementTree.ParseError:
        return ""


def _extract_zip_text(raw: bytes, extension: str) -> str:
    try:
        with zipfile.ZipFile(io.BytesIO(raw)) as archive:
            names = archive.namelist()
            if extension == ".docx":
                return _xml_text(archive.read("word/document.xml")) if "word/document.xml" in names else ""
            if extension == ".pptx":
                slides = sorted(name for name in names if re.fullmatch(r"ppt/slides/slide\d+\.xml", name))
                return "\n\n".join(_xml_text(archive.read(name)) for name in slides)
            if extension == ".xlsx":
                sheets = sorted(name for name in names if re.fullmatch(r"xl/worksheets/sheet\d+\.xml", name))
                shared = _xml_text(archive.read("xl/sharedStrings.xml")) if "xl/sharedStrings.xml" in names else ""
                values = "\n".join(_xml_text(archive.read(name)) for name in sheets)
                return "\n".join(part for part in (shared, values) if part)
    except (KeyError, OSError, zipfile.BadZipFile):
        return ""
    return ""


def _extract_pdf_text(raw: bytes) -> str:
    """Best-effort extraction without a third-party PDF dependency."""
    fragments = re.findall(rb"\(([^()]{2,500})\)", raw)
    return "\n".join(fragment.decode("latin-1", errors="ignore") for fragment in fragments)


def _attachment_excerpt(raw: bytes, extension: str) -> str:
    if extension in TEXT_UPLOAD_EXTENSIONS:
        return _truncate_attachment_text(raw.decode("utf-8", errors="replace"))
    if extension in {".docx", ".pptx", ".xlsx"}:
        return _truncate_attachment_text(_extract_zip_text(raw, extension))
    if extension == ".pdf":
        return _truncate_attachment_text(_extract_pdf_text(raw))
    return ""


class AttachmentStore:
    """Session-local upload metadata with files retained under Whale's runtime data."""

    def __init__(self, root: Path = UPLOAD_ROOT) -> None:
        self.root = root
        self._items: dict[str, dict[str, Any]] = {}
        self._lock = threading.RLock()

    def _metadata_path(self, attachment_id: str) -> Path:
        return self.root / f"{attachment_id}.meta.json"

    def _write_metadata(self, item: dict[str, Any]) -> None:
        metadata = {key: value for key, value in item.items() if key != "path"}
        metadata["stored_file"] = Path(item["path"]).name
        temporary = self._metadata_path(item["id"]).with_suffix(".tmp")
        temporary.write_text(json.dumps(metadata, ensure_ascii=False), encoding="utf-8")
        temporary.replace(self._metadata_path(item["id"]))

    def add(self, *, name: str, mime_type: str, raw: bytes) -> dict[str, Any]:
        filename = _safe_upload_name(name)
        extension = Path(filename).suffix.lower()
        if extension not in SUPPORTED_UPLOAD_EXTENSIONS:
            raise ValueError(f"Unsupported attachment type: {extension or 'unknown'}.")
        if not raw:
            raise ValueError("Attachment is empty.")
        if len(raw) > MAX_UPLOAD_BYTES:
            raise ValueError("Attachment exceeds the 24 MB limit.")
        attachment_id = f"att_{uuid.uuid4().hex[:12]}"
        self.root.mkdir(parents=True, exist_ok=True)
        path = self.root / f"{attachment_id}{extension}"
        path.write_bytes(raw)
        item = {
            "id": attachment_id,
            "name": filename,
            "extension": extension,
            "mime_type": mime_type or mimetypes.guess_type(filename)[0] or "application/octet-stream",
            "size": len(raw),
            "kind": "image" if extension in IMAGE_UPLOAD_EXTENSIONS else "file",
            "excerpt": _attachment_excerpt(raw, extension),
            "path": path,
        }
        self._write_metadata(item)
        with self._lock:
            self._items[attachment_id] = item
        return self.payload(item)

    def get(self, attachment_id: str) -> dict[str, Any] | None:
        with self._lock:
            item = self._items.get(attachment_id)
        if item is not None:
            return item
        metadata_path = self._metadata_path(attachment_id)
        try:
            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
            if not isinstance(metadata, dict) or metadata.get("id") != attachment_id:
                return None
            stored_file = str(metadata.pop("stored_file"))
            path = (self.root / stored_file).resolve()
            path.relative_to(self.root.resolve())
            if not path.is_file():
                return None
            item = {**metadata, "path": path}
        except (KeyError, OSError, ValueError, json.JSONDecodeError):
            return None
        with self._lock:
            self._items[attachment_id] = item
        return item

    def get_many(self, attachment_ids: list[str]) -> list[dict[str, Any]]:
        if len(attachment_ids) > MAX_UPLOADS_PER_RUN:
            raise ValueError(f"At most {MAX_UPLOADS_PER_RUN} attachments can be sent at once.")
        items = []
        for attachment_id in attachment_ids:
            item = self.get(attachment_id)
            if item is None:
                raise ValueError("Attachment no longer exists. Upload it again.")
            items.append(item)
        return items

    def list(self) -> list[dict[str, Any]]:
        with self._lock:
            return [self.payload(item) for item in self._items.values()]

    def delete(self, attachment_id: str) -> bool:
        with self._lock:
            item = self._items.pop(attachment_id, None)
        if item is None:
            item = self.get(attachment_id)
            with self._lock:
                self._items.pop(attachment_id, None)
        if item is None:
            return False
        try:
            Path(item["path"]).unlink(missing_ok=True)
            self._metadata_path(attachment_id).unlink(missing_ok=True)
        except OSError:
            pass
        return True

    def payload(self, item: dict[str, Any]) -> dict[str, Any]:
        return {
            "id": item["id"],
            "name": item["name"],
            "extension": item["extension"],
            "mime_type": item["mime_type"],
            "size": item["size"],
            "kind": item["kind"],
            "excerpt": item["excerpt"],
            "preview_url": f"/api/uploads/{item['id']}/content" if item["kind"] == "image" else "",
        }

    def context_for(self, prompt: str, items: list[dict[str, Any]], *, vision_enabled: bool = False) -> str:
        if not items:
            return prompt
        lines = [prompt, "", "## 本次任务附件"]
        for item in items:
            lines.append(f"- `{item['name']}` ({item['mime_type']}, {item['size']} bytes)")
            if item["excerpt"]:
                lines.append("  已提取的内容摘要：")
                lines.append(item["excerpt"])
            elif item["kind"] == "image":
                if vision_enabled:
                    lines.append("  图片将作为视觉输入发送给当前模型。")
                else:
                    lines.append("  图片已附加，但视觉输入当前关闭；请开启模型设置中的视觉输入，或让用户补充图片中的关键文字。")
            else:
                lines.append("  文件已附加，但该格式没有可安全提取的文本摘要。请根据文件名和用户目标处理。")
        return "\n".join(lines)

    def vision_content(self, text: str, items: list[dict[str, Any]], detail: str) -> list[dict[str, Any]] | None:
        parts: list[dict[str, Any]] = [{"type": "text", "text": text}]
        for item in items:
            if item["kind"] != "image":
                continue
            path = Path(item["path"])
            if not path.is_file():
                continue
            encoded = base64.b64encode(path.read_bytes()).decode("ascii")
            parts.append(
                {
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:{item['mime_type']};base64,{encoded}",
                        "detail": detail,
                    },
                }
            )
        return parts if len(parts) > 1 else None


ATTACHMENTS = AttachmentStore()


def _tutorial_paths() -> list[Path]:
    """Return the numbered tutorial files in their learning order."""
    if not TUTORIALS_ROOT.is_dir():
        return []
    return sorted(
        path
        for path in TUTORIALS_ROOT.glob("*.md")
        if len(path.name) >= 3 and path.name[:2].isdigit() and path.name[2] == "-"
    )


def _tutorial_title(content: str, fallback: str) -> str:
    for line in content.splitlines():
        if line.startswith("# "):
            return line[2:].strip()
    return fallback


def _tutorial_summary(content: str) -> str:
    for line in content.splitlines():
        text = line.strip()
        if text and not text.startswith(("#", "-", "|", "```", "!", "[")):
            return text[:96]
    return "打开本章，查看概念、代码映射与验证方式。"


def _tutorial_catalog() -> list[dict[str, Any]]:
    tutorials = []
    for order, path in enumerate(_tutorial_paths()):
        content = path.read_text(encoding="utf-8")
        tutorials.append(
            {
                "id": path.stem,
                "filename": path.name,
                "order": order,
                "title": _tutorial_title(content, path.stem),
                "summary": _tutorial_summary(content),
            }
        )
    return tutorials


def _tutorial_payload(tutorial_id: str) -> dict[str, Any] | None:
    catalog = _tutorial_catalog()
    for tutorial in catalog:
        if tutorial["id"] != tutorial_id:
            continue
        path = TUTORIALS_ROOT / tutorial["filename"]
        payload = {**tutorial, "content": path.read_text(encoding="utf-8")}
        order = tutorial["order"]
        payload["previous_id"] = catalog[order - 1]["id"] if order else None
        payload["next_id"] = catalog[order + 1]["id"] if order + 1 < len(catalog) else None
        return payload
    return None


_HIDDEN_WORKSPACE_PARTS = {".git", ".whale_cli", ".venv", "node_modules", "dist", "__pycache__"}
_MAX_PREVIEW_BYTES = 200_000


def _workspace_target(relative_path: str) -> Path:
    """Resolve a readable workspace path without permitting an escape."""
    target = (PROJECT_ROOT / relative_path).resolve()
    try:
        relative = target.relative_to(PROJECT_ROOT)
    except ValueError as exc:
        raise ValueError("Path is outside the workspace.") from exc
    if any(part.startswith(".") or part in _HIDDEN_WORKSPACE_PARTS for part in relative.parts):
        raise ValueError("Path is not available in the workspace browser.")
    if not target.exists():
        raise ValueError("Path does not exist.")
    return target


def _workspace_path(path: Path) -> str:
    relative = path.relative_to(PROJECT_ROOT)
    return "" if relative == Path(".") else relative.as_posix()


def _workspace_entries(relative_path: str = "") -> dict[str, Any]:
    target = _workspace_target(relative_path)
    if not target.is_dir():
        raise ValueError("Path is not a directory.")
    entries = []
    for child in sorted(target.iterdir(), key=lambda item: (not item.is_dir(), item.name.lower())):
        try:
            _workspace_target(_workspace_path(child))
        except ValueError:
            continue
        entries.append(
            {
                "name": child.name,
                "path": _workspace_path(child),
                "kind": "directory" if child.is_dir() else "file",
                "size": child.stat().st_size if child.is_file() else None,
            }
        )
    return {
        "path": _workspace_path(target),
        "parent": _workspace_path(target.parent) if target != PROJECT_ROOT else None,
        "entries": entries[:240],
    }


def _workspace_file(relative_path: str) -> dict[str, Any]:
    target = _workspace_target(relative_path)
    if not target.is_file():
        raise ValueError("Path is not a file.")
    raw = target.read_bytes()
    truncated = len(raw) > _MAX_PREVIEW_BYTES
    try:
        content = raw[:_MAX_PREVIEW_BYTES].decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ValueError("Only UTF-8 text files can be previewed.") from exc
    return {
        "path": _workspace_path(target),
        "name": target.name,
        "extension": target.suffix.lower(),
        "content": content,
        "truncated": truncated,
    }


def _learning_wiki_graph_payload() -> dict[str, Any]:
    """Expose a read-only, live view of the project's KnowledgeMap."""
    wiki = ObsidianLearningWiki(LearningStore(PROJECT_ROOT), PROJECT_ROOT)
    snapshot = wiki.graph_snapshot()
    status = wiki.status()
    if not snapshot["nodes"]:
        return {
            "ready": False,
            "vault_dir": status["vault_dir"],
            "nodes": [],
            "edges": [],
            "source": snapshot["source"],
            "reason": "本地 KnowledgeMap 还没有节点。先在对话中记录一个学习概念。",
        }
    return {
        "ready": True,
        "vault_dir": status["vault_dir"],
        "title": snapshot["title"],
        "generated_at": snapshot["generated_at"],
        "source": snapshot["source"],
        "nodes": snapshot["nodes"],
        "edges": snapshot["edges"],
    }


def _learning_wiki_settings_payload() -> dict[str, Any]:
    return ObsidianLearningWiki(LearningStore(PROJECT_ROOT), PROJECT_ROOT).status()


def _learning_wiki_page_payload(node_id: str) -> dict[str, Any]:
    return ObsidianLearningWiki(LearningStore(PROJECT_ROOT), PROJECT_ROOT).render_node_page(node_id)


def _learning_portfolio_payload() -> dict[str, Any]:
    return LearningPortfolio(LearningStore(PROJECT_ROOT)).snapshot()


def _roadmap_planner() -> RoadmapPlanner:
    store = LearningStore(PROJECT_ROOT)
    return RoadmapPlanner(store, LearnerProfileService(store))


def _learning_roadmaps_payload() -> dict[str, Any]:
    planner = _roadmap_planner()
    routes = planner.history()
    return {
        "storage": ".whale_cli/learning/roadmaps",
        "routes": routes,
        "current": planner.current(),
    }


def _learning_roadmap_payload(route_id: str) -> dict[str, Any]:
    return _roadmap_planner().route(route_id)


def _learning_roadmap_preview_payload(weeks: int) -> dict[str, Any]:
    planner = _roadmap_planner()
    state = planner.store.read()
    return {
        "weeks": weeks,
        "profile": state["profile"],
        "items": planner.preview(weeks=weeks),
        "requires_confirmation": True,
    }


def _confirm_learning_roadmap(weeks: int) -> dict[str, Any]:
    planner = _roadmap_planner()
    items = planner.generate(weeks=weeks)
    route_id = items[0]["route_id"] if items else ""
    return planner.route(route_id)


def _review_scheduler() -> ReviewScheduler:
    return ReviewScheduler(LearningStore(PROJECT_ROOT))


def _learning_review_schedule_payload() -> dict[str, Any]:
    scheduler = _review_scheduler()
    scheduler.sync_from_conversations(session_store=SESSIONS, force=False)
    return scheduler.schedule()


def _learning_review_feedback_payload() -> dict[str, Any]:
    scheduler = _review_scheduler()
    scheduler.sync_from_conversations(session_store=SESSIONS, force=False)
    return scheduler.feedback()


def _learning_review_detail_payload(concept_id: str) -> dict[str, Any]:
    return _review_scheduler().detail(concept_id, session_store=SESSIONS)


def _refresh_learning_reviews_in_background() -> None:
    """Refresh today's local review table without delaying WebUI startup."""
    def refresh() -> None:
        try:
            _review_scheduler().sync_from_conversations(session_store=SESSIONS, force=False)
        except (OSError, ValueError):
            # Review refresh is optional; an unavailable session directory must
            # never prevent the local UI from opening.
            return

    threading.Thread(target=refresh, name="whale-review-refresh", daemon=True).start()


class WebSettings:
    """A local, write-only configuration bridge for the browser UI.

    The API never returns the raw key. Explicit values are passed to
    ``LLMClient`` so a WebUI selection takes precedence over the process
    environment without mutating that environment.
    """

    def __init__(self, config_path: Path | None = None) -> None:
        self.path = config_path or PATHS.config_file
        self._lock = threading.RLock()

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            llm = self._load_llm()
            key, source = self._effective_api_key(llm)
            model = str(llm.get("model") or os.getenv("LLM_MODEL") or "step-3.7-flash")
            base_url = str(llm.get("base_url") or os.getenv("LLM_BASE_URL") or "https://api.stepfun.com/step_plan/v1")
            vision_default = model.startswith("step-3.7")
            return {
                "api_key_configured": bool(key),
                "api_key_hint": self._mask_key(key),
                "api_key_source": source,
                "model": model,
                "base_url": base_url,
                "max_context_tokens": int(llm.get("max_context_tokens") or 256_000),
                "vision_enabled": bool(llm.get("vision_enabled", vision_default)),
                "vision_detail": str(llm.get("vision_detail") or "low"),
            }

    def update(self, payload: dict[str, Any]) -> dict[str, Any]:
        with self._lock:
            data = self._load_data()
            llm = data.setdefault("llm", {})
            if not isinstance(llm, dict):
                llm = {}
                data["llm"] = llm
            for key in ("model", "base_url"):
                if key in payload:
                    value = str(payload[key]).strip()
                    if not value:
                        raise ValueError(f"{key} cannot be empty.")
                    llm[key] = value
            if "max_context_tokens" in payload:
                value = int(payload["max_context_tokens"])
                if value <= 0:
                    raise ValueError("max_context_tokens must be positive.")
                llm["max_context_tokens"] = value
            if "vision_enabled" in payload:
                if not isinstance(payload["vision_enabled"], bool):
                    raise ValueError("vision_enabled must be a boolean.")
                llm["vision_enabled"] = payload["vision_enabled"]
            if "vision_detail" in payload:
                detail = str(payload["vision_detail"])
                if detail not in {"low", "high"}:
                    raise ValueError("vision_detail must be low or high.")
                llm["vision_detail"] = detail
            if "api_key" in payload:
                value = str(payload["api_key"]).strip()
                if value:
                    llm["api_key"] = value
            self._write_data(data)
            return self.snapshot()

    def build_client(self) -> LLMClient:
        with self._lock:
            llm = self._load_llm()
            key, _ = self._effective_api_key(llm)
            if not key:
                raise ValueError("No API key configured. Open settings and add an API key first.")
            return LLMClient(
                api_key=key,
                base_url=str(llm.get("base_url") or os.getenv("LLM_BASE_URL") or "https://api.stepfun.com/step_plan/v1"),
                model=str(llm.get("model") or os.getenv("LLM_MODEL") or "step-3.7-flash"),
                max_context_tokens=int(llm.get("max_context_tokens") or 256_000),
            )

    def _load_data(self) -> dict[str, Any]:
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            return data if isinstance(data, dict) else {}
        except (OSError, ValueError):
            return {}

    def _load_llm(self) -> dict[str, Any]:
        llm = self._load_data().get("llm", {})
        return llm if isinstance(llm, dict) else {}

    def _effective_api_key(self, llm: dict[str, Any]) -> tuple[str, str]:
        config_key = str(llm.get("api_key") or "").strip()
        if config_key:
            return config_key, "config"
        for name in ("STEP_API_KEY", "OPENAI_API_KEY", "MOONSHOT_API_KEY"):
            value = os.getenv(name)
            if value:
                return value, name
        return "", "none"

    def _write_data(self, data: dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(".tmp")
        temporary.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        temporary.replace(self.path)

    @staticmethod
    def _mask_key(value: str) -> str:
        if not value:
            return ""
        return f"••••{value[-4:]}" if len(value) > 4 else "••••"


SETTINGS = WebSettings()


def _session_payload(session_id: str) -> dict[str, Any] | None:
    info = SESSIONS.get_session_info(session_id)
    if info is None:
        return None
    messages = SESSIONS.load_messages(session_id)
    return {
        "session_id": info.session_id,
        "title": info.title or "未命名会话",
        "created_at": info.created_at,
        "updated_at": info.updated_at,
        "message_count": len([message for message in messages if message.get("role") != "system"]),
        "messages": [_message_payload(message) for message in messages if message.get("role") != "system"],
    }


def _datawhale_kb_payload() -> dict[str, Any]:
    path = DATAWHALE_KB.path
    return {
        "path": str(path.relative_to(PROJECT_ROOT)),
        "available": DATAWHALE_KB.available,
        "document_count": len(DATAWHALE_KB.documents()),
        "size": path.stat().st_size if path.is_file() else 0,
        "algorithm": "Okapi BM25",
        "update": DATAWHALE_UPDATER.preview(),
    }


def _replace_datawhale_kb(*, name: str, raw: bytes) -> dict[str, Any]:
    if Path(name).suffix.lower() != ".jsonl":
        raise ValueError("Datawhale knowledge base must be a .jsonl file.")
    if len(raw) > MAX_DATAWHALE_KB_BYTES:
        raise ValueError("Datawhale knowledge base exceeds the 64 MB limit.")
    DATAWHALE_KB.replace_corpus(raw)
    return _datawhale_kb_payload()


def _sync_latest_datawhale_kb() -> dict[str, Any]:
    DATAWHALE_UPDATER.sync_latest()
    return _datawhale_kb_payload()


def _session_list_payload() -> dict[str, list[dict[str, Any]]]:
    """Return only persisted conversations that contain a real message."""
    sessions = []
    for item in SESSIONS.list_sessions(limit=40):
        payload = _session_payload(item.session_id)
        if payload is not None and payload["message_count"] > 0:
            payload.pop("messages", None)
            sessions.append(payload)
    return {"sessions": sessions}


def _delete_session_payload(session_id: str) -> dict[str, Any] | None:
    if RUNS.has_active_session(session_id):
        raise RuntimeError("This session has a running task and cannot be deleted yet.")
    if not SESSIONS.delete_session(session_id):
        return None
    return {"deleted": session_id}


def _message_payload(message: dict[str, Any]) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "role": str(message.get("role", "assistant")),
        "content": str(message.get("content", "")),
        "name": str(message.get("name", "")),
    }
    metadata = message.get("metadata")
    if isinstance(metadata, dict) and isinstance(metadata.get("attachments"), list):
        payload["attachments"] = metadata["attachments"]
    return payload


def _event_hook(state: RunState, event_name: str):
    def capture(payload: dict[str, Any]):
        tool_name = payload.get("tool_name")
        if event_name == "PreToolUse":
            state.add_event("tool", f"Tool requested: {tool_name}", json.dumps(payload.get("tool_input", {}), ensure_ascii=False))
        elif event_name == "PostToolUse":
            output = payload.get("tool_output", {})
            state.add_event("result", f"Tool finished: {tool_name}", f"exit_code={output.get('exit_code', 0)}")
        elif event_name == "PostToolUseFailure":
            state.add_event("error", f"Tool failed: {tool_name}", str(payload.get("error", "")))
        elif event_name == "UserPromptSubmit":
            state.add_event("input", "Prompt submitted", str(payload.get("prompt", "")))
        return None

    return capture


def _start_run(state: RunState) -> None:
    def worker() -> None:
        state.status = "running"
        state.add_event("thinking", "Agent loop started", "Soul.run() is preparing the first model turn.")
        hooks = HookEngine()
        for event in ("UserPromptSubmit", "PreToolUse", "PostToolUse", "PostToolUseFailure"):
            hooks.on(event, _event_hook(state, event))
        approval = WebApproval(state, yolo=state.mode == "yolo")

        try:
            settings = SETTINGS.snapshot()
            saved_messages = SESSIONS.load_messages(state.session_id)
            soul = Soul(
                llm=SETTINGS.build_client(),
                approval=approval,
                hook_engine=hooks,
                session_store=SESSIONS,
                session_id=state.session_id,
                initial_messages=saved_messages or None,
            )
            attachments = ATTACHMENTS.get_many(state.attachment_ids)
            prompt = ATTACHMENTS.context_for(state.prompt, attachments, vision_enabled=settings["vision_enabled"])
            vision_content = (
                ATTACHMENTS.vision_content(prompt, attachments, settings["vision_detail"])
                if settings["vision_enabled"]
                else None
            )
            attachment_payloads = [ATTACHMENTS.payload(item) for item in attachments]
            outcome = soul.run(
                prompt,
                multimodal_content=vision_content,
                user_metadata={"attachments": attachment_payloads},
            )
            state.status = outcome.status
            state.summary = outcome.summary
            state.steps = outcome.steps
            state.messages = [
                _message_payload(message)
                for message in soul.messages
                if message.get("role") != "system"
            ]
            state.add_event("complete", f"Run {outcome.status}", outcome.summary, steps=outcome.steps)
            soul.close()
        except Exception as exc:  # Surface setup failures in the UI instead of killing the server thread.
            state.status = "failed"
            state.summary = str(exc)
            state.add_event("error", "Run failed", str(exc))

    threading.Thread(target=worker, name=f"whale-web-{state.id}", daemon=True).start()


def _overview_payload() -> dict[str, Any]:
    """Keep the WebUI overview aligned with the built-in runtime tools."""
    settings = SETTINGS.snapshot()
    return {
        "project": "Whale CLI",
        "workspace": str(PROJECT_ROOT),
        "model_ready": settings["api_key_configured"],
        "model": settings["model"],
        "tools": [
            "ReadFile", "Glob", "Grep", "WriteFile", "Edit", "Bash", "SearchWeb", "FetchURL",
            "TodoWrite", "GetDate", "Agent", "LearnerProfile", "KnowledgeMap", "LearningRoadmap",
            "LearningReview", "LearningProjectPlan", "CloneLearningProject", "LearningPortfolio", "LearningWikiStatus", "LearningWiki", "OpenLearningWiki", "SyncToObsidianVault",
            "BackgroundStart", "BackgroundList", "BackgroundOutput",
        ],
        "session_count": len(SESSIONS.list_sessions(limit=10_000)),
        "tutorial_count": len(_tutorial_paths()),
    }


class WebUIHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, directory=str(STATIC_ROOT), **kwargs)

    def log_message(self, fmt: str, *args: Any) -> None:
        print(f"[webui] {self.address_string()} - {fmt % args}")

    def do_GET(self) -> None:  # noqa: N802
        request = urlparse(self.path)
        path = request.path
        query = parse_qs(request.query)
        if path in {"/health", "/api/health"}:
            self._send_json(
                HTTPStatus.OK,
                {"status": "ok", "service": "whale-web", "version": __version__},
            )
            return
        if path in {"/ready", "/api/ready"}:
            checks = {
                "static": (STATIC_ROOT / "index.html").is_file(),
                "workspace": PROJECT_ROOT.is_dir() and os.access(PROJECT_ROOT, os.W_OK),
                "home": PATHS.home.is_dir() and os.access(PATHS.home, os.W_OK),
            }
            ready = all(checks.values())
            self._send_json(
                HTTPStatus.OK if ready else HTTPStatus.SERVICE_UNAVAILABLE,
                {"status": "ready" if ready else "not_ready", "checks": checks},
            )
            return
        if path == "/api/overview":
            self._send_json(HTTPStatus.OK, _overview_payload())
            return
        if path == "/api/settings":
            self._send_json(HTTPStatus.OK, SETTINGS.snapshot())
            return
        if path == "/api/datawhale-kb":
            self._send_json(HTTPStatus.OK, _datawhale_kb_payload())
            return
        if path == "/api/uploads":
            self._send_json(HTTPStatus.OK, {"uploads": ATTACHMENTS.list()})
            return
        if path == "/api/learning-wiki/graph":
            self._send_json(HTTPStatus.OK, _learning_wiki_graph_payload())
            return
        if path == "/api/learning-wiki/settings":
            self._send_json(HTTPStatus.OK, _learning_wiki_settings_payload())
            return
        if path == "/api/learning-wiki/page":
            try:
                self._send_json(HTTPStatus.OK, _learning_wiki_page_payload(query.get("id", [""])[0]))
            except (OSError, ValueError) as exc:
                self._send_json(HTTPStatus.BAD_REQUEST, {"error": str(exc)})
            return
        if path == "/api/learning-portfolio":
            self._send_json(HTTPStatus.OK, _learning_portfolio_payload())
            return
        if path == "/api/learning-roadmaps":
            self._send_json(HTTPStatus.OK, _learning_roadmaps_payload())
            return
        if path.startswith("/api/learning-roadmaps/"):
            try:
                self._send_json(HTTPStatus.OK, _learning_roadmap_payload(unquote(path.rsplit("/", 1)[-1])))
            except (OSError, ValueError) as exc:
                self._send_json(HTTPStatus.NOT_FOUND, {"error": str(exc)})
            return
        if path == "/api/learning-review/schedule":
            self._send_json(HTTPStatus.OK, _learning_review_schedule_payload())
            return
        if path == "/api/learning-review/feedback":
            self._send_json(HTTPStatus.OK, _learning_review_feedback_payload())
            return
        if path == "/api/learning-review/detail":
            try:
                self._send_json(HTTPStatus.OK, _learning_review_detail_payload(query.get("id", [""])[0]))
            except (OSError, ValueError) as exc:
                self._send_json(HTTPStatus.BAD_REQUEST, {"error": str(exc)})
            return
        if path.startswith("/api/uploads/") and path.endswith("/content"):
            attachment_id = path.split("/")[-2]
            item = ATTACHMENTS.get(attachment_id)
            if item is None:
                self._send_json(HTTPStatus.NOT_FOUND, {"error": "Attachment not found."})
                return
            self._serve_upload(item)
            return
        if path == "/api/tutorials":
            self._send_json(HTTPStatus.OK, {"tutorials": _tutorial_catalog()})
            return
        if path.startswith("/api/tutorials/"):
            tutorial_id = unquote(path.rsplit("/", 1)[-1])
            payload = _tutorial_payload(tutorial_id)
            if payload is None:
                self._send_json(HTTPStatus.NOT_FOUND, {"error": "Tutorial not found."})
                return
            self._send_json(HTTPStatus.OK, payload)
            return
        if path == "/api/workspace":
            try:
                self._send_json(HTTPStatus.OK, _workspace_entries(query.get("path", [""])[0]))
            except (OSError, ValueError) as exc:
                self._send_json(HTTPStatus.BAD_REQUEST, {"error": str(exc)})
            return
        if path == "/api/workspace/file":
            try:
                self._send_json(HTTPStatus.OK, _workspace_file(query.get("path", [""])[0]))
            except (OSError, ValueError) as exc:
                self._send_json(HTTPStatus.BAD_REQUEST, {"error": str(exc)})
            return
        if path == "/api/sessions":
            self._send_json(HTTPStatus.OK, _session_list_payload())
            return
        if path.startswith("/api/sessions/"):
            payload = _session_payload(path.rsplit("/", 1)[-1])
            if payload is None:
                self._send_json(HTTPStatus.NOT_FOUND, {"error": "Session not found."})
                return
            self._send_json(HTTPStatus.OK, payload)
            return
        if path.startswith("/api/runs/"):
            state = RUNS.get(path.rsplit("/", 1)[-1])
            if state is None:
                self._send_json(HTTPStatus.NOT_FOUND, {"error": "Run not found."})
                return
            self._send_json(HTTPStatus.OK, state.snapshot())
            return
        if path.startswith("/project-assets/"):
            self._serve_project_asset(path[len("/project-assets/") :])
            return
        super().do_GET()

    def do_POST(self) -> None:  # noqa: N802
        path = urlparse(self.path).path
        if path == "/api/datawhale-kb/upload":
            upload = self._read_upload(max_bytes=MAX_DATAWHALE_KB_BYTES)
            if upload is None:
                return
            try:
                self._send_json(
                    HTTPStatus.OK,
                    _replace_datawhale_kb(name=upload["name"], raw=upload["raw"]),
                )
            except (OSError, ValueError) as exc:
                self._send_json(HTTPStatus.BAD_REQUEST, {"error": str(exc)})
            return
        if path == "/api/datawhale-kb/update":
            try:
                self._send_json(HTTPStatus.OK, _sync_latest_datawhale_kb())
            except (OSError, ValueError) as exc:
                self._send_json(HTTPStatus.BAD_REQUEST, {"error": str(exc)})
            return
        if path == "/api/uploads":
            upload = self._read_upload()
            if upload is None:
                return
            try:
                payload = ATTACHMENTS.add(
                    name=upload["name"],
                    mime_type=upload["mime_type"],
                    raw=upload["raw"],
                )
                self._send_json(HTTPStatus.CREATED, payload)
            except (ValueError, OSError) as exc:
                self._send_json(HTTPStatus.BAD_REQUEST, {"error": str(exc)})
            return
        body = self._read_json_body()
        if body is None:
            return
        if path == "/api/runs":
            prompt = str(body.get("prompt", "")).strip()
            mode = str(body.get("mode", "safe"))
            session_id = str(body.get("session_id", "")).strip()
            attachment_ids = body.get("attachment_ids", [])
            if not isinstance(attachment_ids, list) or not all(isinstance(item, str) for item in attachment_ids):
                self._send_json(HTTPStatus.BAD_REQUEST, {"error": "attachment_ids must be a string list."})
                return
            if not prompt and not attachment_ids:
                self._send_json(HTTPStatus.BAD_REQUEST, {"error": "Prompt cannot be empty."})
                return
            if mode not in {"safe", "yolo"}:
                self._send_json(HTTPStatus.BAD_REQUEST, {"error": "Unknown approval mode."})
                return
            if not SETTINGS.snapshot()["api_key_configured"]:
                self._send_json(
                    HTTPStatus.PRECONDITION_REQUIRED,
                    {"error": f"No API key found. Set STEP_API_KEY or configure {SETTINGS.path} first."},
                )
                return
            if session_id and SESSIONS.get_session_info(session_id) is None:
                self._send_json(HTTPStatus.NOT_FOUND, {"error": "Session not found."})
                return
            try:
                ATTACHMENTS.get_many(attachment_ids)
            except ValueError as exc:
                self._send_json(HTTPStatus.BAD_REQUEST, {"error": str(exc)})
                return
            state = RUNS.create(
                prompt or "请分析我附加的文件。",
                mode,
                session_id or SESSIONS.create_session(),
                attachment_ids,
            )
            _start_run(state)
            self._send_json(HTTPStatus.ACCEPTED, state.snapshot())
            return
        if path == "/api/sessions":
            title = str(body.get("title", "")).strip()
            session_id = SESSIONS.create_session(title=title)
            self._send_json(HTTPStatus.CREATED, _session_payload(session_id) or {"session_id": session_id})
            return
        if path == "/api/settings":
            try:
                self._send_json(HTTPStatus.OK, SETTINGS.update(body))
            except (OSError, ValueError) as exc:
                self._send_json(HTTPStatus.BAD_REQUEST, {"error": str(exc)})
            return
        if path == "/api/learning-wiki/settings":
            enabled = body.get("auto_capture")
            if not isinstance(enabled, bool):
                self._send_json(HTTPStatus.BAD_REQUEST, {"error": "auto_capture must be a boolean."})
                return
            self._send_json(
                HTTPStatus.OK,
                ObsidianLearningWiki(LearningStore(PROJECT_ROOT), PROJECT_ROOT).set_auto_capture(enabled=enabled),
            )
            return
        if path == "/api/learning-review/refresh":
            self._send_json(HTTPStatus.OK, _review_scheduler().sync_from_conversations(session_store=SESSIONS, force=True))
            return
        if path == "/api/learning-review/rate":
            concept_id = str(body.get("concept_id", "")).strip()
            rating = body.get("rating")
            if not concept_id or not isinstance(rating, int) or isinstance(rating, bool):
                self._send_json(HTTPStatus.BAD_REQUEST, {"error": "concept_id and integer rating are required."})
                return
            try:
                scheduler = _review_scheduler()
                reviewed = scheduler.review(concept_id=concept_id, rating=rating)
                self._send_json(HTTPStatus.OK, {"reviewed": reviewed, "schedule": scheduler.schedule()})
            except ValueError as exc:
                self._send_json(HTTPStatus.BAD_REQUEST, {"error": str(exc)})
            return
        if path == "/api/learning-roadmaps/preview":
            weeks = body.get("weeks", 4)
            if not isinstance(weeks, int) or isinstance(weeks, bool):
                self._send_json(HTTPStatus.BAD_REQUEST, {"error": "weeks must be an integer."})
                return
            try:
                self._send_json(HTTPStatus.OK, _learning_roadmap_preview_payload(weeks))
            except ValueError as exc:
                self._send_json(HTTPStatus.BAD_REQUEST, {"error": str(exc)})
            return
        if path == "/api/learning-roadmaps/confirm":
            weeks = body.get("weeks", 4)
            if not isinstance(weeks, int) or isinstance(weeks, bool):
                self._send_json(HTTPStatus.BAD_REQUEST, {"error": "weeks must be an integer."})
                return
            try:
                self._send_json(HTTPStatus.CREATED, _confirm_learning_roadmap(weeks))
            except ValueError as exc:
                self._send_json(HTTPStatus.BAD_REQUEST, {"error": str(exc)})
            return
        if path == "/api/learning-roadmaps/complete":
            roadmap_id = str(body.get("roadmap_id", "")).strip()
            if not roadmap_id:
                self._send_json(HTTPStatus.BAD_REQUEST, {"error": "roadmap_id is required."})
                return
            try:
                completed = _roadmap_planner().mark_done(roadmap_id)
                self._send_json(HTTPStatus.OK, {"completed": completed, "current": _roadmap_planner().current()})
            except ValueError as exc:
                self._send_json(HTTPStatus.BAD_REQUEST, {"error": str(exc)})
            return
        if path.startswith("/api/runs/") and path.endswith("/approval"):
            run_id = path.split("/")[-2]
            state = RUNS.get(run_id)
            decision = str(body.get("decision", ""))
            if state is None:
                self._send_json(HTTPStatus.NOT_FOUND, {"error": "Run not found."})
                return
            if decision not in {"approve", "approve_for_session", "reject"}:
                self._send_json(HTTPStatus.BAD_REQUEST, {"error": "Unknown approval decision."})
                return
            with state.condition:
                if state.pending_approval is None:
                    self._send_json(HTTPStatus.CONFLICT, {"error": "No approval is pending."})
                    return
                state.approval_decision = decision
                state.condition.notify_all()
            self._send_json(HTTPStatus.OK, state.snapshot())
            return
        self._send_json(HTTPStatus.NOT_FOUND, {"error": "Unknown API route."})

    def do_DELETE(self) -> None:  # noqa: N802
        path = urlparse(self.path).path
        if path.startswith("/api/sessions/"):
            session_id = unquote(path.rsplit("/", 1)[-1])
            try:
                payload = _delete_session_payload(session_id)
            except (RuntimeError, ValueError) as exc:
                self._send_json(HTTPStatus.CONFLICT, {"error": str(exc)})
                return
            if payload is None:
                self._send_json(HTTPStatus.NOT_FOUND, {"error": "Session not found."})
                return
            self._send_json(HTTPStatus.OK, payload)
            return
        if path.startswith("/api/uploads/"):
            attachment_id = path.rsplit("/", 1)[-1]
            if not ATTACHMENTS.delete(attachment_id):
                self._send_json(HTTPStatus.NOT_FOUND, {"error": "Attachment not found."})
                return
            self._send_json(HTTPStatus.OK, {"deleted": attachment_id})
            return
        self._send_json(HTTPStatus.NOT_FOUND, {"error": "Unknown API route."})

    def _read_json_body(self, *, max_bytes: int = 65_536) -> dict[str, Any] | None:
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if length > max_bytes:
                raise ValueError("Request body is too large.")
            data = json.loads(self.rfile.read(length) or b"{}")
            if not isinstance(data, dict):
                raise ValueError("JSON body must be an object.")
            return data
        except (ValueError, json.JSONDecodeError) as exc:
            self._send_json(HTTPStatus.BAD_REQUEST, {"error": str(exc)})
            return None

    def _read_upload(self, *, max_bytes: int = MAX_UPLOAD_BYTES) -> dict[str, Any] | None:
        """Read one direct multipart file, retaining JSON for older clients."""
        content_type = self.headers.get("Content-Type", "")
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if length <= 0 or length > max_bytes + 512 * 1024:
                raise ValueError("Request body is too large.")
            if content_type.startswith("multipart/form-data"):
                raw_body = self.rfile.read(length)
                header = f"Content-Type: {content_type}\r\nMIME-Version: 1.0\r\n\r\n".encode("latin-1")
                message = BytesParser(policy=policy.default).parsebytes(header + raw_body)
                field = next(
                    (
                        part
                        for part in message.walk()
                        if part.get_content_disposition() == "form-data"
                        and part.get_param("name", header="content-disposition") == "file"
                    ),
                    None,
                )
                if field is None or not field.get_filename():
                    raise ValueError("A file field is required.")
                raw = field.get_payload(decode=True) or b""
                if len(raw) > max_bytes:
                    raise ValueError("Uploaded file exceeds the size limit.")
                return {
                    "name": str(field.get_filename()),
                    "mime_type": str(field.get_content_type() or ""),
                    "raw": raw,
                }

            body = self._read_json_body(max_bytes=max_bytes * 2)
            if body is None:
                return None
            encoded = body.get("data", "")
            if not isinstance(encoded, str):
                raise ValueError("Attachment data must be a base64 string.")
            return {
                "name": str(body.get("name", "")),
                "mime_type": str(body.get("mime_type", "")),
                "raw": base64.b64decode(encoded, validate=True),
            }
        except (KeyError, ValueError, OSError, binascii.Error) as exc:
            self._send_json(HTTPStatus.BAD_REQUEST, {"error": str(exc)})
            return None

    def _serve_project_asset(self, raw_path: str) -> None:
        try:
            target = (PROJECT_ROOT / unquote(raw_path)).resolve()
            target.relative_to(PROJECT_ROOT)
        except ValueError:
            self.send_error(HTTPStatus.FORBIDDEN)
            return
        if not target.is_file():
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        self.path = "/" + str(target.relative_to(PROJECT_ROOT))
        self.directory = str(PROJECT_ROOT)
        super().do_GET()

    def _serve_upload(self, item: dict[str, Any]) -> None:
        path = Path(item["path"])
        if not path.is_file():
            self._send_json(HTTPStatus.NOT_FOUND, {"error": "Attachment file not found."})
            return
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", item["mime_type"])
        self.send_header("Content-Length", str(path.stat().st_size))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        with path.open("rb") as source:
            self.wfile.write(source.read())

    def _send_json(self, status: HTTPStatus, payload: dict[str, Any]) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the local Whale CLI WebUI.")
    parser.add_argument("--host", default=os.environ.get("WHALE_HOST", "127.0.0.1"))
    parser.add_argument("--port", type=int, default=int(os.environ.get("WHALE_PORT", "8765")))
    args = parser.parse_args()

    PATHS.ensure_writable_directories()
    if not (STATIC_ROOT / "index.html").is_file():
        parser.error("React build not found. Run `make web` in the source checkout or install a release wheel.")
    os.chdir(PROJECT_ROOT)
    _refresh_learning_reviews_in_background()
    server = ThreadingHTTPServer((args.host, args.port), WebUIHandler)
    print(f"Whale CLI WebUI: http://{args.host}:{args.port}")
    print(f"Workspace: {PROJECT_ROOT}")
    print(f"Runtime home: {PATHS.home}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nWebUI stopped.")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
