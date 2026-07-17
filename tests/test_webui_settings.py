"""Focused tests for the local WebUI configuration bridge."""
from __future__ import annotations

import importlib.util
import json
import os
import sys
import tempfile
from pathlib import Path

import pytest

from whale_cli.learning import KnowledgeMap


def _load_webui_server():
    path = Path(__file__).resolve().parents[1] / "src" / "whale_cli" / "web" / "server.py"
    spec = importlib.util.spec_from_file_location("whale_webui_server_test", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    previous_home = os.environ.get("WHALE_HOME")
    os.environ["WHALE_HOME"] = tempfile.mkdtemp(prefix="whale-webui-test-")
    try:
        spec.loader.exec_module(module)
    finally:
        if previous_home is None:
            os.environ.pop("WHALE_HOME", None)
        else:
            os.environ["WHALE_HOME"] = previous_home
    return module


def test_web_settings_masks_key_and_persists_model(tmp_path, monkeypatch):
    monkeypatch.delenv("STEP_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("MOONSHOT_API_KEY", raising=False)
    server = _load_webui_server()
    settings = server.WebSettings(tmp_path / "config.json")

    snapshot = settings.update(
        {
            "api_key": "test-secret-key-1234",
            "model": "step-3.7-flash",
            "base_url": "https://example.test/v1",
            "max_context_tokens": 4096,
            "vision_enabled": True,
            "vision_detail": "high",
        }
    )

    assert snapshot["api_key_configured"] is True
    assert snapshot["api_key_hint"] == "••••1234"
    assert "secret" not in str(snapshot)
    assert snapshot["model"] == "step-3.7-flash"
    assert snapshot["vision_enabled"] is True
    assert snapshot["vision_detail"] == "high"
    assert "test-secret-key-1234" in (tmp_path / "config.json").read_text(encoding="utf-8")


def test_web_settings_selects_step_explore_defaults_and_disables_vision(tmp_path, monkeypatch):
    monkeypatch.setenv("STEPFUN_API_KEY", "explore-key-1234")
    server = _load_webui_server()
    settings = server.WebSettings(tmp_path / "config.json")

    snapshot = settings.update({"model": "step-explore", "base_url": "https://api.stepfun.com/v1"})

    assert snapshot["api_key_source"] == "STEPFUN_API_KEY"
    assert snapshot["base_url"] == "https://api.stepfun.com/v1"
    assert snapshot["vision_enabled"] is False
    with pytest.raises(ValueError, match="does not support"):
        settings.update({"vision_enabled": True})


def test_web_settings_switches_legacy_base_url_when_only_model_changes(tmp_path):
    server = _load_webui_server()
    config = tmp_path / "config.json"
    config.write_text(
        json.dumps({"llm": {"api_key": "key", "model": "step-3.7-flash", "base_url": "https://api.stepfun.com/step_plan/v1"}}),
        encoding="utf-8",
    )
    settings = server.WebSettings(config)

    snapshot = settings.update({"model": "step-explore"})

    assert snapshot["base_url"] == "https://api.stepfun.com/v1"


def test_tutorial_catalog_exposes_only_numbered_learning_files():
    server = _load_webui_server()

    catalog = server._tutorial_catalog()
    first = server._tutorial_payload("00-为什么要做这个CLI")

    assert len(catalog) >= 28
    assert [item["order"] for item in catalog] == list(range(len(catalog)))
    assert catalog[0]["filename"] == "00-为什么要做这个CLI.md"
    assert catalog[-1]["filename"] == "27-学习档案与社区反馈-把进步留下来.md"
    assert first is not None
    assert first["content"].startswith("# 00.")
    assert first["previous_id"] is None
    assert first["next_id"] == "01-5分钟体验-能帮你做什么"
    assert server._tutorial_payload("../../README") is None


def test_overview_lists_vertical_learning_tools():
    server = _load_webui_server()

    overview = server._overview_payload()

    assert "LearnerProfile" in overview["tools"]
    assert "KnowledgeMap" in overview["tools"]
    assert "LearningPortfolio" in overview["tools"]
    assert "LearningWiki" in overview["tools"]


def test_learning_wiki_api_mirrors_local_graph_without_export(tmp_path, monkeypatch):
    server = _load_webui_server()
    monkeypatch.setattr(server, "PROJECT_ROOT", tmp_path)
    knowledge_map = KnowledgeMap(server.LearningStore(tmp_path))
    python = knowledge_map.add_node(title="Python 基础", mastery=4)
    agent = knowledge_map.add_node(title="Agent Loop", mastery=1, note="模型与工具循环协作。")
    knowledge_map.link(source=python["id"], target=agent["id"])

    graph = server._learning_wiki_graph_payload()
    page = server._learning_wiki_page_payload("agent-loop")

    assert graph["ready"] is True
    assert graph["source"] == "local_learning_wiki_outline"
    assert graph["nodes"][0]["title"] == "Agent Loop"
    assert all("mastery" not in node for node in graph["nodes"])
    assert "[[python-基础|Python 基础]]" in page["content"]
    assert not (tmp_path / "learning-wiki" / ".whale-graph.json").exists()
    with pytest.raises(ValueError):
        server._learning_wiki_page_payload("../../README")


def test_learning_wiki_settings_reports_the_local_auto_capture_flag(tmp_path, monkeypatch):
    server = _load_webui_server()
    monkeypatch.setattr(server, "PROJECT_ROOT", tmp_path)
    wiki = server.ObsidianLearningWiki(server.LearningStore(tmp_path), tmp_path)
    wiki.set_auto_capture(enabled=True)

    payload = server._learning_wiki_settings_payload()

    assert payload["auto_capture"] is True
    assert payload["conversation_count"] == 0


def test_learning_portfolio_api_exposes_projects_evidence_and_local_contribution_drafts(tmp_path, monkeypatch):
    server = _load_webui_server()
    monkeypatch.setattr(server, "PROJECT_ROOT", tmp_path)
    store = server.LearningStore(tmp_path)
    portfolio = server.LearningPortfolio(store)
    store.update(lambda state: state["projects"].append({"title": "Agent Hub", "goal": "理解工具调用", "learning_value": "把 Agent Loop 变成项目实践。", "prerequisites": ["Python 基础"], "outcomes": ["完成最小改动"], "first_action": "阅读 README", "status": "planned"}))
    portfolio.add_evidence(title="工具调用验证", detail="验证只读工具输出。", kind="exercise", concepts=["Agent Loop"], outcome="能解释观察回填。", artifact="README.md", next_action="补一个测试。")
    portfolio.add_evidence(title="补充教程前置", detail="教程没有说明环境准备。", kind="contribution", concepts=["Python 基础"], outcome="增加环境准备段落。", artifact="复现命令记录")

    payload = server._learning_portfolio_payload()

    assert payload["summary"] == {"project_count": 1, "evidence_count": 2, "contribution_count": 1, "concept_count": 0}
    assert payload["projects"][0]["learning_value"] == "把 Agent Loop 变成项目实践。"
    assert payload["evidence"][1]["concepts"] == ["Agent Loop"]
    assert payload["contributions"][0]["title"] == "补充教程前置"
    assert "# 我的学习档案" in payload["report"]


def test_learning_roadmaps_api_reads_json_archives(tmp_path, monkeypatch):
    server = _load_webui_server()
    monkeypatch.setattr(server, "PROJECT_ROOT", tmp_path)
    store = server.LearningStore(tmp_path)
    profile = server.LearnerProfileService(store)
    profile.update(level="初学者", goal="完成 Agent 项目", weekly_hours=6)
    KnowledgeMap(store).add_node(title="Agent Loop", mastery=1)
    items = server.RoadmapPlanner(store, profile).generate(weeks=1)

    listing = server._learning_roadmaps_payload()
    route = server._learning_roadmap_payload(items[0]["route_id"])

    assert listing["storage"] == ".whale_cli/learning/roadmaps"
    assert listing["routes"][0]["id"] == items[0]["route_id"]
    assert route["items"][0]["title"] == "掌握 Agent Loop"


def test_learning_roadmap_web_api_previews_then_confirms_and_completes(tmp_path, monkeypatch):
    server = _load_webui_server()
    monkeypatch.setattr(server, "PROJECT_ROOT", tmp_path)
    store = server.LearningStore(tmp_path)
    server.LearnerProfileService(store).update(level="初学者", goal="完成 Agent 项目", weekly_hours=6)
    KnowledgeMap(store).add_node(title="Agent Loop", mastery=1)

    preview = server._learning_roadmap_preview_payload(1)
    assert not (tmp_path / ".whale_cli" / "learning" / "roadmaps").exists()
    saved = server._confirm_learning_roadmap(1)
    completed = server._roadmap_planner().mark_done(saved["items"][0]["id"])

    assert preview["requires_confirmation"] is True
    assert len(server._roadmap_planner().history()) == 1
    assert saved["items"][0]["status"] == "todo"
    assert completed["status"] == "done"


def test_learning_review_api_scans_local_sessions_into_a_schedule(tmp_path, monkeypatch):
    server = _load_webui_server()
    monkeypatch.setattr(server, "PROJECT_ROOT", tmp_path)
    sessions = server.SessionStore(str(tmp_path / ".whale_cli"))
    monkeypatch.setattr(server, "SESSIONS", sessions)
    node = KnowledgeMap(server.LearningStore(tmp_path)).add_node(title="Agent Loop", mastery=1)
    session_id = sessions.create_session(title="Agent Loop")
    sessions.append_message(session_id, {"role": "user", "content": "复习一下 Agent Loop", "timestamp": "2026-01-01T10:00:00+00:00"})

    schedule = server._learning_review_schedule_payload()
    feedback = server._learning_review_feedback_payload()
    detail = server._learning_review_detail_payload(node["id"])

    assert schedule["due"][0]["concept_id"] == node["id"]
    assert schedule["table_path"] == ".whale_cli/learning/review-schedule.json"
    assert feedback["path"] == ".whale_cli/learning/review-feedback.md"
    assert "- [ ] Agent Loop" in feedback["content"]
    assert detail["title"] == "Agent Loop"
    assert detail["material_count"] == 1
    assert detail["memory"]["mode"] == "baseline"


def test_web_session_delete_uses_the_shared_store_and_rejects_running_work(tmp_path, monkeypatch):
    server = _load_webui_server()
    sessions = server.SessionStore(str(tmp_path / ".whale_cli"))
    monkeypatch.setattr(server, "SESSIONS", sessions)
    monkeypatch.setattr(server, "RUNS", server.RunStore())
    session_id = sessions.create_session(title="delete me")
    sessions.append_message(session_id, {"role": "user", "content": "temporary"})

    assert server._delete_session_payload(session_id) == {"deleted": session_id}
    assert sessions.get_session_info(session_id) is None

    active_id = sessions.create_session(title="active")
    server.RUNS.create("work", "safe", active_id)
    with pytest.raises(RuntimeError, match="running task"):
        server._delete_session_payload(active_id)


def test_web_session_list_hides_empty_sessions(tmp_path, monkeypatch):
    server = _load_webui_server()
    sessions = server.SessionStore(str(tmp_path / ".whale_cli"))
    monkeypatch.setattr(server, "SESSIONS", sessions)
    empty_id = sessions.create_session()
    populated_id = sessions.create_session(title="有内容的会话")
    sessions.append_message(populated_id, {"role": "user", "content": "hello"})

    payload = server._session_list_payload()

    assert [item["session_id"] for item in payload["sessions"]] == [populated_id]
    assert empty_id not in [item["session_id"] for item in payload["sessions"]]


def test_web_datawhale_kb_reports_and_replaces_the_project_corpus(tmp_path, monkeypatch):
    server = _load_webui_server()
    monkeypatch.setattr(server, "PROJECT_ROOT", tmp_path)
    knowledge_base = server.DatawhaleKnowledgeBase(tmp_path / ".whale_cli" / "datawhale_bm25_documents.jsonl")
    monkeypatch.setattr(
        server,
        "DATAWHALE_KB",
        knowledge_base,
    )
    monkeypatch.setattr(server, "DATAWHALE_UPDATER", server.DatawhaleKnowledgeBaseUpdater(knowledge_base, tmp_path / "bm25_runs"))
    raw = json.dumps({
        "title": "Datawhale Agent 101", "url": "https://example.test/agent", "text": "Agent 学习项目",
        "tokens": ["agent", "学习"], "tags": ["agent"], "metadata": {"stars": 1},
    }, ensure_ascii=False).encode("utf-8") + b"\n"

    payload = server._replace_datawhale_kb(name="datawhale.jsonl", raw=raw)

    assert payload["available"] is True
    assert payload["document_count"] == 1
    assert payload["algorithm"] == "Okapi BM25"
    with pytest.raises(ValueError, match=".jsonl"):
        server._replace_datawhale_kb(name="datawhale.csv", raw=raw)


def test_workspace_browser_is_read_only_and_stays_in_project_root():
    server = _load_webui_server()

    listing = server._workspace_entries()
    preview = server._workspace_file("pyproject.toml")

    assert any(item["path"] == "src" and item["kind"] == "directory" for item in listing["entries"])
    assert all(not item["name"].startswith(".") for item in listing["entries"])
    assert preview["name"] == "pyproject.toml"
    assert "whale-cli" in preview["content"]
    with pytest.raises(ValueError):
        server._workspace_entries("../../")
    with pytest.raises(ValueError):
        server._workspace_file(".git/config")


def test_attachment_store_validates_files_and_builds_agent_context(tmp_path):
    server = _load_webui_server()
    store = server.AttachmentStore(tmp_path / "uploads")

    payload = store.add(
        name="notes.md",
        mime_type="text/markdown",
        raw=b"# Meeting notes\n\n- Confirm the MCP test plan.\n",
    )
    pdf = store.add(name="diagram.pdf", mime_type="application/pdf", raw=b"%PDF-1.7\n(Architecture diagram)\n")
    image = store.add(name="screen.png", mime_type="image/png", raw=b"\x89PNG\r\n\x1a\nimage-bytes")
    items = store.get_many([payload["id"], pdf["id"], image["id"]])
    context = store.context_for("Summarize the attachments.", items, vision_enabled=True)
    parts = store.vision_content(context, items, "high")

    assert payload["extension"] == ".md"
    assert "Confirm the MCP test plan" in payload["excerpt"]
    assert "Architecture diagram" in context
    assert "作为视觉输入" in context
    assert parts and parts[1]["type"] == "image_url"
    assert parts[1]["image_url"]["detail"] == "high"
    assert parts[1]["image_url"]["url"].startswith("data:image/png;base64,")
    assert (tmp_path / "uploads" / f"{payload['id']}.md").is_file()
    restored = server.AttachmentStore(tmp_path / "uploads").get(image["id"])
    assert restored is not None
    assert server.AttachmentStore(tmp_path / "uploads").payload(restored)["preview_url"].endswith("/content")
    assert server._message_payload({"role": "user", "content": "see image", "metadata": {"attachments": [image]}})["attachments"] == [image]
    assert store.delete(payload["id"]) is True
    with pytest.raises(ValueError):
        store.add(name="archive.zip", mime_type="application/zip", raw=b"not allowed")
