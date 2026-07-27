"""Runtime paths shared by the CLI, WebUI, and deployment tooling."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def _expanded_path(value: str | Path) -> Path:
    return Path(value).expanduser().resolve()


def _source_project_root() -> Path | None:
    for parent in Path(__file__).resolve().parents:
        if (parent / "pyproject.toml").is_file() and (parent / "src" / "whale_cli").is_dir():
            return parent
    return None


def _first_directory(*candidates: Path) -> Path:
    for candidate in candidates:
        if candidate.is_dir():
            return candidate
    return candidates[0]


@dataclass(frozen=True)
class RuntimePaths:
    """Resolved writable and read-only locations for one Whale process."""

    home: Path
    workspace: Path
    config_file: Path
    uploads: Path
    static_root: Path
    tutorials_root: Path
    learning_wiki: Path
    datawhale_kb: Path

    def ensure_writable_directories(self) -> None:
        self.home.mkdir(parents=True, exist_ok=True)
        self.uploads.mkdir(parents=True, exist_ok=True)
        self.workspace.mkdir(parents=True, exist_ok=True)


def resolve_runtime_paths() -> RuntimePaths:
    """Resolve deployment paths without assuming Whale runs from its source tree.

    ``WHALE_CLI_HOME`` and ``WHALE_CLI_UPLOAD_DIR`` remain supported as legacy
    aliases. New deployments should use ``WHALE_HOME`` and ``WHALE_WORKSPACE``.
    """

    package_root = Path(__file__).resolve().parent
    source_root = _source_project_root()
    workspace = _expanded_path(os.environ.get("WHALE_WORKSPACE") or Path.cwd())
    home = _expanded_path(
        os.environ.get("WHALE_HOME")
        or os.environ.get("WHALE_CLI_HOME")
        or Path.home() / ".whale"
    )
    config_file = _expanded_path(os.environ.get("WHALE_CONFIG") or home / "config.json")
    uploads = _expanded_path(
        os.environ.get("WHALE_UPLOAD_DIR")
        or os.environ.get("WHALE_CLI_UPLOAD_DIR")
        or home / "uploads"
    )

    packaged_static = package_root / "web" / "static"
    source_static = source_root / "webui" / "dist" if source_root else packaged_static
    static_root = _expanded_path(
        os.environ.get("WHALE_WEB_STATIC")
        or _first_directory(source_static, packaged_static)
    )

    packaged_tutorials = package_root / "web" / "tutorials"
    source_tutorials = source_root / "docs" / "新手入门" if source_root else packaged_tutorials
    tutorials_root = _expanded_path(
        os.environ.get("WHALE_TUTORIALS_DIR")
        or _first_directory(source_tutorials, packaged_tutorials)
    )

    return RuntimePaths(
        home=home,
        workspace=workspace,
        config_file=config_file,
        uploads=uploads,
        static_root=static_root,
        tutorials_root=tutorials_root,
        learning_wiki=workspace / "learning-wiki",
        datawhale_kb=workspace / ".whale_cli" / "datawhale_bm25_documents.jsonl",
    )
