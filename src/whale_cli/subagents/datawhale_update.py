"""Import a completed Datawhale BM25 run into Whale's local corpus."""
from __future__ import annotations

import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .datawhale import DatawhaleKnowledgeBase


DEFAULT_BM25_RUNS_DIR = Path("/Volumes/拓展/workspace/datawhaledata/outputs/bm25_runs")
CORPUS_FILENAME = "datawhale_bm25_documents.jsonl"
MANIFEST_FILENAME = "datawhale_bm25_manifest.json"
RUN_ID_PATTERN = re.compile(r"^\d{8}-\d{6}$")


def default_bm25_runs_dir() -> Path:
    configured = os.getenv("DATAWHALE_BM25_RUNS_DIR")
    return Path(configured).expanduser() if configured else DEFAULT_BM25_RUNS_DIR


class DatawhaleKnowledgeBaseUpdater:
    """Discover completed source runs and safely import their full JSONL corpus."""

    def __init__(self, knowledge_base: DatawhaleKnowledgeBase, runs_dir: str | Path | None = None) -> None:
        self.knowledge_base = knowledge_base
        self.runs_dir = Path(runs_dir) if runs_dir else default_bm25_runs_dir()
        self.state_path = knowledge_base.path.parent / "datawhale_bm25_update.json"

    def latest_run(self) -> Path | None:
        if not self.runs_dir.is_dir():
            return None
        candidates = [
            path for path in self.runs_dir.iterdir()
            if path.is_dir() and (path / CORPUS_FILENAME).is_file()
        ]
        timestamped = [path for path in candidates if RUN_ID_PATTERN.fullmatch(path.name)]
        return max(timestamped or candidates, key=lambda path: path.name, default=None)

    @staticmethod
    def _manifest(run: Path) -> dict[str, Any]:
        try:
            payload = json.loads((run / MANIFEST_FILENAME).read_text(encoding="utf-8"))
            return payload if isinstance(payload, dict) else {}
        except (OSError, json.JSONDecodeError):
            return {}

    def _stored_state(self) -> dict[str, Any]:
        try:
            payload = json.loads(self.state_path.read_text(encoding="utf-8"))
            return payload if isinstance(payload, dict) else {}
        except (OSError, json.JSONDecodeError):
            return {}

    def preview(self) -> dict[str, Any]:
        run = self.latest_run()
        state = self._stored_state()
        if run is None:
            return {
                "source_available": False,
                "runs_dir": str(self.runs_dir),
                "latest_run": "",
                "last_update": state,
            }
        manifest = self._manifest(run)
        source = run / CORPUS_FILENAME
        return {
            "source_available": True,
            "runs_dir": str(self.runs_dir),
            "latest_run": run.name,
            "source_path": str(source),
            "source_size": source.stat().st_size,
            "source_document_count": int(manifest.get("documentCount") or 0),
            "counts_by_source_type": manifest.get("countsBySourceType") or {},
            "github_readme_count": int(manifest.get("githubReadmeCount") or 0),
            "generated_at": str(manifest.get("generatedAt") or ""),
            "last_update": state,
        }

    def sync_latest(self) -> dict[str, Any]:
        run = self.latest_run()
        if run is None:
            raise FileNotFoundError(f"No completed BM25 run found in {self.runs_dir}.")
        source = run / CORPUS_FILENAME
        imported_count = self.knowledge_base.replace_corpus(source.read_bytes())
        state = {
            "source_run": run.name,
            "source_path": str(source),
            "imported_count": imported_count,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.state_path.with_suffix(".tmp")
        temporary.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        temporary.replace(self.state_path)
        return {**self.preview(), "last_update": state}
