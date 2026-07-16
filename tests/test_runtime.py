from __future__ import annotations

from pathlib import Path

from whale_cli.doctor import collect_checks
from whale_cli.runtime import resolve_runtime_paths


def test_runtime_paths_separate_home_and_workspace(tmp_path, monkeypatch):
    home = tmp_path / "runtime"
    workspace = tmp_path / "workspace"
    static = tmp_path / "static"
    tutorials = tmp_path / "tutorials"
    monkeypatch.setenv("WHALE_HOME", str(home))
    monkeypatch.setenv("WHALE_WORKSPACE", str(workspace))
    monkeypatch.setenv("WHALE_WEB_STATIC", str(static))
    monkeypatch.setenv("WHALE_TUTORIALS_DIR", str(tutorials))

    paths = resolve_runtime_paths()

    assert paths.home == home
    assert paths.workspace == workspace
    assert paths.uploads == home / "uploads"
    assert paths.datawhale_kb == workspace / ".whale_cli" / "datawhale_bm25_documents.jsonl"
    assert paths.config_file == home / "config.json"


def test_doctor_requires_web_assets_only_when_requested(tmp_path, monkeypatch):
    monkeypatch.setenv("WHALE_HOME", str(tmp_path / "home"))
    monkeypatch.setenv("WHALE_WORKSPACE", str(tmp_path / "workspace"))
    monkeypatch.setenv("WHALE_WEB_STATIC", str(tmp_path / "missing-static"))

    assert collect_checks(require_web=False)["status"] == "ok"
    assert collect_checks(require_web=True)["status"] == "fail"


def test_doctor_accepts_built_web_assets(tmp_path, monkeypatch):
    static = tmp_path / "static"
    static.mkdir()
    (static / "index.html").write_text("<main>Whale</main>", encoding="utf-8")
    monkeypatch.setenv("WHALE_HOME", str(tmp_path / "home"))
    monkeypatch.setenv("WHALE_WORKSPACE", str(tmp_path / "workspace"))
    monkeypatch.setenv("WHALE_WEB_STATIC", str(static))

    report = collect_checks(require_web=True)

    assert report["status"] == "ok"
    assert Path(report["paths"]["static_root"]) == static
