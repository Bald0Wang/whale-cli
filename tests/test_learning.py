from __future__ import annotations

from datetime import date
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from whale_cli.learning import KnowledgeMap, LearnerProfileService, LearningPortfolio, LearningStore, ObsidianLearningWiki, ProjectCompanion, ReviewScheduler, RoadmapPlanner
from whale_cli.soul.approval import Approval
from whale_cli.soul.soul import Soul
from whale_cli.soul import soul as soul_module
from whale_cli.soul.toolset import Toolset
from whale_cli.storage.session_store import SessionStore
from whale_cli.tools.learning import CloneLearningProjectTool, KnowledgeMapTool, LearnerProfileTool, LearningReviewTool, LearningRoadmapTool, LearningWikiTool, OpenLearningWikiTool, SyncToObsidianVaultTool

from .conftest import make_tool_call


def _services(tmp_path):
    store = LearningStore(tmp_path)
    profile = LearnerProfileService(store)
    graph = KnowledgeMap(store)
    return store, profile, graph


def test_profile_is_explicit_and_persists_locally(tmp_path):
    store, profile, _ = _services(tmp_path)
    assert profile.missing_fields() == ["level", "goal", "weekly_hours"]

    saved = profile.update(level="Python 初学者", goal="完成 Agent 项目", weekly_hours=6, topics=["Agent", "Python", "Agent"])

    assert saved["topics"] == ["Agent", "Python"]
    assert LearnerProfileService(store).get()["weekly_hours"] == 6
    assert (tmp_path / ".whale_cli" / "learning" / "state.json").is_file()


def test_knowledge_map_exposes_reverse_links_without_duplicate_edges(tmp_path):
    _, _, graph = _services(tmp_path)
    python = graph.add_node(title="Python 基础", mastery=3)
    agent = graph.add_node(title="Agent Loop", mastery=1)

    graph.link(source=python["id"], target=agent["id"])
    graph.link(source=python["id"], target=agent["id"])

    assert len(graph.node(python["id"])["links_to"]) == 1
    assert graph.node(agent["id"])["linked_from"] == [{"source": python["id"], "target": agent["id"], "relation": "prerequisite"}]


def test_roadmap_only_unlocks_concepts_with_ready_prerequisites(tmp_path):
    store, profile, graph = _services(tmp_path)
    profile.update(level="初学者", goal="学习 Agent", weekly_hours=5)
    basic = graph.add_node(title="Python 基础", mastery=0)
    advanced = graph.add_node(title="Agent Loop", mastery=0)
    graph.link(source=basic["id"], target=advanced["id"])

    items = RoadmapPlanner(store, profile).generate(weeks=4)

    assert [item["concept_id"] for item in items] == [basic["id"]]
    assert RoadmapPlanner(store, profile).current()["items"][0]["id"] == items[0]["id"]
    completed = RoadmapPlanner(store, profile).mark_done(items[0]["id"])
    assert completed["status"] == "done"


def test_roadmap_preview_does_not_write_until_generation_is_confirmed(tmp_path):
    store, profile, graph = _services(tmp_path)
    profile.update(level="初学者", goal="学习 Agent", weekly_hours=5)
    graph.add_node(title="Agent Loop", mastery=1)
    planner = RoadmapPlanner(store, profile)

    preview = planner.preview(weeks=1)

    assert preview[0]["title"] == "掌握 Agent Loop"
    assert not (tmp_path / ".whale_cli" / "learning" / "roadmaps").exists()

    planner.generate(weeks=1)
    assert len(planner.history()) == 1


def test_roadmap_splits_weekly_goals_into_steps_and_tracks_parent_progress(tmp_path):
    store, profile, graph = _services(tmp_path)
    profile.update(level="初学者", goal="学习 Agent", weekly_hours=6)
    graph.add_node(title="Agent Loop", mastery=1)
    planner = RoadmapPlanner(store, profile)

    item = planner.generate(weeks=1)[0]
    subtasks = item["subtasks"]

    assert [subtask["id"] for subtask in subtasks] == [
        "roadmap-agent-loop-understand",
        "roadmap-agent-loop-practice",
        "roadmap-agent-loop-reflect",
    ]
    assert sum(subtask["estimated_hours"] for subtask in subtasks) == pytest.approx(item["estimated_hours"])

    first = planner.mark_done(subtasks[0]["id"])
    current = planner.current()
    route = planner.route(item["route_id"])

    assert first["status"] == "done"
    assert current["items"][0]["status"] == "in_progress"
    assert route["summary"]["done_count"] == 0
    assert route["summary"]["subtask_done_count"] == 1

    planner.mark_done(subtasks[1]["id"])
    planner.mark_done(subtasks[2]["id"])

    assert planner.current()["items"][0]["status"] == "done"
    assert planner.route(item["route_id"])["summary"]["done_count"] == 1


def test_roadmap_archives_each_generation_as_a_json_snapshot(tmp_path):
    store, profile, graph = _services(tmp_path)
    profile.update(level="初学者", goal="完成 Agent 项目", weekly_hours=6)
    graph.add_node(title="Agent Loop", mastery=1)
    planner = RoadmapPlanner(store, profile)

    first = planner.generate(weeks=1)
    second = planner.generate(weeks=1)
    saved = planner.history()
    completed = planner.mark_done(second[0]["id"])
    refreshed = planner.route(second[0]["route_id"])

    assert len(saved) == 2
    assert saved[0]["profile"]["goal"] == "完成 Agent 项目"
    assert (tmp_path / ".whale_cli" / "learning" / "roadmaps" / f"{first[0]['route_id']}.json").is_file()
    assert completed["status"] == "done"
    assert refreshed["summary"]["done_count"] == 1


def test_roadmap_accepts_a_route_id_only_for_one_remaining_item(tmp_path):
    store, profile, graph = _services(tmp_path)
    profile.update(level="初学者", goal="完成 Agent 项目", weekly_hours=6)
    graph.add_node(title="Agent Loop", mastery=1)
    planner = RoadmapPlanner(store, profile)
    items = planner.generate(weeks=1)

    completed = planner.mark_done(items[0]["route_id"])

    assert completed["id"] == items[0]["id"]


def test_review_scheduler_uses_shorter_interval_after_low_recall(tmp_path):
    store, _, graph = _services(tmp_path)
    node = graph.add_node(title="Prompt 模板", mastery=1)
    scheduler = ReviewScheduler(store)

    first = scheduler.review(concept_id=node["id"], rating=5, today=date(2026, 1, 1))
    second = scheduler.review(concept_id=node["id"], rating=1, today=date(2026, 1, 2))

    assert first["due_on"] == "2026-01-04"
    assert second["stage"] == 0
    assert second["due_on"] == "2026-01-03"
    assert scheduler.due(today=date(2026, 1, 3))[0]["concept_id"] == node["id"]


def test_review_scheduler_builds_a_local_table_from_known_conversation_mentions(tmp_path):
    store, _, graph = _services(tmp_path)
    node = graph.add_node(title="Agent Loop", mastery=1, note="模型决定是否调用工具，并把工具结果回填到下一轮。")
    sessions = SessionStore(str(tmp_path / ".whale_cli"))
    session_id = sessions.create_session(title="学习 Agent Loop")
    sessions.append_message(session_id, {"role": "user", "content": "请解释 Agent Loop 如何回填工具结果。", "timestamp": "2026-01-01T10:00:00+00:00"})
    sessions.append_message(session_id, {"role": "assistant", "content": "Agent Loop 会把工具输出作为下一轮模型的上下文。", "timestamp": "2026-01-01T10:01:00+00:00"})
    sessions.append_message(session_id, {"role": "tool", "content": "Agent Loop 的内部工具轨迹不应出现在复习资料中。", "timestamp": "2026-01-01T10:02:00+00:00"})

    scheduler = ReviewScheduler(store)
    synced = scheduler.sync_from_conversations(session_store=sessions, force=True, today=date(2026, 1, 2))
    table = scheduler.schedule(today=date(2026, 1, 2))
    skipped = scheduler.sync_from_conversations(session_store=sessions, force=False, today=date(2026, 1, 2))

    assert synced["scanned"] is True
    assert table["due"][0]["concept_id"] == node["id"]
    assert table["due"][0]["rating"] is None
    assert (tmp_path / ".whale_cli" / "learning" / "review-schedule.json").is_file()
    feedback = scheduler.feedback(today=date(2026, 1, 2))
    feedback_path = tmp_path / ".whale_cli" / "learning" / "review-feedback.md"
    assert feedback["path"] == ".whale_cli/learning/review-feedback.md"
    assert "- [ ] Agent Loop" in feedback["content"]
    assert feedback_path.read_text(encoding="utf-8") == feedback["content"]
    detail = scheduler.detail(node["id"], session_store=sessions)
    assert detail["summary"] == "模型决定是否调用工具，并把工具结果回填到下一轮。"
    assert detail["material_count"] == 2
    assert detail["materials"][0]["role"] == "assistant"
    assert detail["memory"]["mode"] == "baseline"
    scheduler.review(concept_id=node["id"], rating=4, today=date(2026, 1, 2))
    estimated = scheduler.detail(node["id"], session_store=sessions, today=date(2026, 1, 3))["memory"]
    assert estimated["mode"] == "estimate"
    assert estimated["interval_days"] == 3
    assert estimated["current_retention"] == pytest.approx(79.4)
    assert skipped["scanned"] is False


def test_learning_review_tool_writes_markdown_feedback_for_cli(tmp_path):
    _, _, graph = _services(tmp_path)
    graph.add_node(title="Agent Loop", mastery=1)
    sessions = SessionStore(str(tmp_path / ".whale_cli"))
    session_id = sessions.create_session(title="学习 Agent Loop")
    sessions.append_message(session_id, {"role": "user", "content": "我想复习 Agent Loop", "timestamp": "2026-01-01T10:00:00+00:00"})
    toolset = Toolset([LearningReviewTool(tmp_path)])

    synced = toolset.handle("LearningReview", '{"action":"sync"}')
    feedback = toolset.handle("LearningReview", '{"action":"feedback"}')

    assert synced["exit_code"] == 0
    assert feedback["exit_code"] == 0
    assert "# Whale 间隔复习反馈" in feedback["stdout"]
    assert (tmp_path / ".whale_cli" / "learning" / "review-feedback.md").is_file()


def test_project_companion_rejects_non_repository_url_and_clones_in_workspace(tmp_path, monkeypatch):
    store = LearningStore(tmp_path)
    companion = ProjectCompanion(store, tmp_path)
    with pytest.raises(ValueError, match="direct GitHub"):
        companion.plan(title="bad", url="https://example.com/doc", goal="test")

    plan = companion.plan(
        title="Agent 练习",
        url="https://github.com/datawhalechina/demo.git",
        goal="理解并改造一个工具调用示例",
        learning_value="把 Agent Loop 从抽象概念变成可观察的项目流程。",
        prerequisites=["Python 基础", "Agent Loop"],
        outcomes=["解释工具结果如何回填", "完成一次最小改动"],
        first_action="只读 README，标出示例入口。",
    )
    assert plan["learning_value"].startswith("把 Agent Loop")
    assert plan["prerequisites"] == ["Python 基础", "Agent Loop"]
    assert plan["milestones"][0]["evidence"]

    calls = []
    monkeypatch.setattr(
        "whale_cli.learning.projects.subprocess.run",
        lambda args, **kwargs: calls.append((args, kwargs)) or SimpleNamespace(returncode=0, stdout="cloned", stderr=""),
    )
    result = companion.clone(url="https://github.com/datawhalechina/demo.git", directory="projects/demo")

    assert result["directory"] == "projects/demo"
    assert result["next_action"]
    assert store.read()["projects"][0]["status"] == "ready"
    assert calls[0][0][:3] == ["git", "clone", "--depth"]
    with pytest.raises(ValueError, match="escapes workspace"):
        companion.clone(url="https://github.com/datawhalechina/demo.git", directory="../outside")


def test_portfolio_collects_evidence_without_creating_a_pr(tmp_path):
    store, profile, graph = _services(tmp_path)
    profile.update(level="初学者", goal="完成项目", weekly_hours=4)
    graph.add_node(title="工具调用", mastery=2)
    portfolio = LearningPortfolio(store)
    portfolio.add_evidence(
        title="完成工具调用",
        detail="调用本地只读工具并写下复盘。",
        kind="exercise",
        concepts=["工具调用", "Agent Loop"],
        outcome="能解释工具结果为何需要回填给下一轮。",
        artifact="learning-wiki/concepts/agent-loop.md",
        next_action="为失败分支补一个测试。",
    )

    report = portfolio.report()

    assert "# 我的学习档案" in report
    assert "完成工具调用" in report
    assert "关联知识：工具调用、Agent Loop" in report
    assert "能力变化：能解释工具结果为何需要回填给下一轮。" in report
    assert "下一步：为失败分支补一个测试。" in report
    assert "自动提交" not in report


def test_learning_tools_share_local_contract_and_clone_requires_approval(tmp_path):
    profile = LearnerProfileTool(tmp_path)
    updated = profile(action="update", level="初学者", goal="学 Agent", weekly_hours=6)
    assert updated["exit_code"] == 0

    graph = KnowledgeMapTool(tmp_path)
    added = graph(action="add_node", title="Agent Loop", mastery=0)
    assert "agent-loop" in added["stdout"]

    clone = CloneLearningProjectTool(tmp_path)
    assert clone.approval_action == "clone learning project"


def test_learning_roadmap_requires_approval_only_when_saving(tmp_path):
    profile = LearnerProfileTool(tmp_path)
    profile(action="update", level="初学者", goal="学习 Agent", weekly_hours=5)
    KnowledgeMapTool(tmp_path)(action="add_node", title="Agent Loop", mastery=1)
    actions = []
    toolset = Toolset([LearningRoadmapTool(tmp_path)])
    toolset.set_approver(lambda action, _: actions.append(action) or True)

    preview = toolset.handle("LearningRoadmap", '{"action":"preview","weeks":1}')
    saved = toolset.handle("LearningRoadmap", '{"action":"generate","weeks":1}')

    assert preview["exit_code"] == 0
    assert saved["exit_code"] == 0
    assert actions == ["save learning roadmap"]


def test_obsidian_wiki_sync_exports_frontmatter_wikilinks_and_graph_manifest(tmp_path):
    store, _, graph = _services(tmp_path)
    python = graph.add_node(title="Python 基础", mastery=4)
    agent = graph.add_node(title="Agent Loop", mastery=1, note="工具结果会回填给下一轮模型。")
    graph.link(source=python["id"], target=agent["id"])

    result = ObsidianLearningWiki(store, tmp_path).sync(title="小陈的 Agent Wiki")
    vault = tmp_path / "learning-wiki"
    agent_page = (vault / "concepts" / "agent-loop.md").read_text(encoding="utf-8")
    manifest = (vault / ".whale-graph.json").read_text(encoding="utf-8")

    assert result["ready"] is True
    assert (vault / ".wiki-schema.md").is_file()
    assert (vault / "purpose.md").is_file()
    assert "generated_by: whale-cli" in agent_page
    assert "[[python-基础|Python 基础]]" in agent_page
    assert '"source": "python-基础"' in manifest
    assert ObsidianLearningWiki(store, tmp_path).status()["node_count"] == 2


def test_obsidian_wiki_live_snapshot_and_preview_do_not_require_export(tmp_path):
    store, _, graph = _services(tmp_path)
    python = graph.add_node(title="Python 基础", mastery=4)
    agent = graph.add_node(title="Agent Loop", mastery=1, note="模型与工具循环协作。")
    graph.link(source=python["id"], target=agent["id"])

    wiki = ObsidianLearningWiki(store, tmp_path)
    snapshot = wiki.graph_snapshot()
    preview = wiki.render_node_page("agent-loop")

    assert snapshot["source"] == "local_learning_wiki_outline"
    assert {node["id"] for node in snapshot["nodes"] if node["kind"] == "topic"} == {"python-基础", "agent-loop"}
    assert all("mastery" not in node for node in snapshot["nodes"])
    assert "[[python-基础|Python 基础]]" in preview["content"]
    assert not (tmp_path / "learning-wiki" / ".whale-graph.json").exists()


def test_learning_wiki_outline_builds_a_semantic_subgraph_and_markdown_sections(tmp_path):
    store, _, graph = _services(tmp_path)
    agent = graph.add_node(title="Agent Loop", mastery=1)
    wiki = ObsidianLearningWiki(store, tmp_path)

    outline = wiki.save_outline(
        concept_id=agent["id"],
        positioning="完成 Python 基础后，用它理解 Agent 的控制流程。",
        learning_value="它把模型回答从一次性输出变成可观察、可验证的任务过程。",
        outcomes=["解释一次工具调用为何不是完整循环", "实现一个最小的观察回填流程"],
        definition="让模型、工具与观察结果持续协作的控制循环。",
        mechanism="模型决定下一步；工具返回观察；观察回填到下一轮上下文。",
        key_terms=["工具调用", "观察", "上下文回填"],
        practice="让一个只读工具调用后再根据输出回答问题。",
        pitfalls=["把一次工具调用误当作完整循环"],
        questions=["何时应该停止循环？"],
        sources=["Whale CLI 第 03 章"],
    )
    snapshot = wiki.graph_snapshot()
    page = wiki.render_node_page("agent-loop--model")

    assert outline["concept_id"] == "agent-loop"
    assert {node["kind"] for node in snapshot["nodes"] if node["topic_id"] == "agent-loop"} == {
        "topic", "positioning", "value", "model", "outcome", "action", "reflection",
    }
    assert {edge["relation"] for edge in snapshot["edges"] if edge["source"] == "agent-loop"} >= {"contains"}
    assert "## 为什么值得学" in page["content"]
    assert "## 学完能做什么" in page["content"]
    assert "## 核心模型" in page["content"]
    assert "上下文回填" in page["content"]
    assert "mastery:" not in page["content"]


def test_learning_wiki_auto_capture_is_explicit_and_keeps_a_conversation_index(tmp_path):
    store = LearningStore(tmp_path)
    wiki = ObsidianLearningWiki(store, tmp_path)

    assert wiki.capture_conversation_turn(user_message="解释 Agent Loop", assistant_message="它会循环调用模型和工具。") is None
    enabled = wiki.set_auto_capture(enabled=True)
    captured = wiki.capture_conversation_turn(
        user_message="解释 Agent Loop",
        assistant_message="它会循环调用模型和工具。",
        session_id="session_demo",
        model="step-3.7-flash",
    )

    assert enabled["auto_capture"] is True
    assert captured is not None
    page = Path(captured["path"]).read_text(encoding="utf-8")
    conversation_index = (tmp_path / "learning-wiki" / "conversations" / "index.md").read_text(encoding="utf-8")
    assert "type: conversation" in page
    assert "解释 Agent Loop" in page
    assert "它会循环调用模型和工具。" in page
    assert captured["title"] in conversation_index
    assert wiki.status()["conversation_count"] == 1

    wiki.set_auto_capture(enabled=False)
    assert wiki.capture_conversation_turn(user_message="第二轮", assistant_message="不会写入") is None
    assert wiki.status()["conversation_count"] == 1


def test_learning_wiki_tool_requires_approval_before_writing(tmp_path):
    toolset = Toolset([LearningWikiTool(tmp_path)])
    toolset.set_approver(lambda _action, _description: False)

    result = toolset.handle("LearningWiki", '{"action":"init"}')

    assert result["exit_code"] == 126
    assert not (tmp_path / "learning-wiki").exists()


def test_learning_wiki_tool_can_explicitly_enable_auto_capture(tmp_path):
    toolset = Toolset([LearningWikiTool(tmp_path)])
    toolset.set_approver(lambda _action, _description: True)

    result = toolset.handle("LearningWiki", '{"action":"set_auto_capture","enabled":true}')

    assert result["exit_code"] == 0
    assert ObsidianLearningWiki(LearningStore(tmp_path), tmp_path).status()["auto_capture"] is True


def test_learning_wiki_tool_saves_a_llm_outline_after_approval(tmp_path):
    KnowledgeMapTool(tmp_path)(action="add_node", title="Agent Loop", mastery=1)
    toolset = Toolset([LearningWikiTool(tmp_path)])
    toolset.set_approver(lambda action, _description: action == "write learning wiki")

    result = toolset.handle(
        "LearningWiki",
        json.dumps({
            "action": "outline",
            "concept_id": "agent-loop",
            "positioning": "Python 基础后的控制循环主题。",
            "learning_value": "让学习者理解 Agent 如何把一次回答变成可验证任务。",
            "outcomes": ["实现一次观察回填"],
            "definition": "模型与工具协作的循环。",
            "mechanism": "调用工具并回填观察。",
            "key_terms": ["工具调用"],
            "practice": "运行一次只读工具调用。",
        }, ensure_ascii=False),
    )

    assert result["exit_code"] == 0
    snapshot = ObsidianLearningWiki(LearningStore(tmp_path), tmp_path).graph_snapshot()
    assert next(node for node in snapshot["nodes"] if node["id"] == "agent-loop--value")["summary"] == "让学习者理解 Agent 如何把一次回答变成可验证任务。"


def test_learning_wiki_can_open_managed_vault_and_mirror_to_explicit_obsidian_vault(tmp_path, monkeypatch):
    store, _, graph = _services(tmp_path)
    graph.add_node(title="Agent Loop", mastery=1)
    wiki = ObsidianLearningWiki(store, tmp_path)
    wiki.sync()
    config_path = tmp_path / "obsidian" / "obsidian.json"
    config_path.parent.mkdir()
    config_path.write_text('{"vaults": {}}\n', encoding="utf-8")
    monkeypatch.setattr(ObsidianLearningWiki, "_obsidian_config_path", staticmethod(lambda: config_path))
    launched = []
    monkeypatch.setattr(
        "whale_cli.learning.wiki.subprocess.run",
        lambda command, **kwargs: launched.append(command) or SimpleNamespace(returncode=0, stdout="", stderr=""),
    )

    opened = wiki.open_in_obsidian(node_id="agent-loop")
    vault = tmp_path / "my-obsidian"
    (vault / ".obsidian").mkdir(parents=True)
    mirrored = wiki.sync_to_existing_vault(vault_path=str(vault))

    assert opened["target"].endswith("concepts/agent-loop.md")
    assert launched == [["open", opened["uri"]]]
    assert opened["vault_id"]
    registered = json.loads(config_path.read_text(encoding="utf-8"))
    assert registered["vaults"][opened["vault_id"]]["path"] == str((tmp_path / "learning-wiki").resolve())
    assert (tmp_path / "learning-wiki" / ".obsidian" / "app.json").is_file()
    assert (vault / "Whale Learning Wiki" / "concepts" / "agent-loop.md").is_file()
    assert not (vault / "Whale Learning Wiki" / ".obsidian").exists()
    assert mirrored["copied_files"]
    external_tool = SyncToObsidianVaultTool(tmp_path)
    assert external_tool.approval_action == "write external Obsidian vault"
    assert OpenLearningWikiTool(tmp_path).approval_action == "register and open Obsidian wiki"


def test_default_soul_registers_and_calls_learner_profile_tool(mock_llm, tmp_workspace, monkeypatch):
    monkeypatch.setattr(soul_module, "load_mcp_tools_with_lifecycle", lambda: (soul_module.MCPLifecycle(), []))
    llm = mock_llm([
        [make_tool_call("profile_1", "LearnerProfile", {
            "action": "update", "level": "Python 初学者", "goal": "学习 Agent", "weekly_hours": 6,
        })],
        "已保存学习档案。",
    ])
    soul = Soul(llm=llm, approval=Approval(yolo=True))

    outcome = soul.run("帮我建立学习档案")

    assert "LearnerProfile" in soul.toolset.names
    assert "KnowledgeMap" in soul.toolset.names
    assert "LearningWiki" in soul.toolset.names
    assert "SyncToObsidianVault" in soul.toolset.names
    assert outcome.status == "completed"
    assert (tmp_workspace / ".whale_cli" / "learning" / "state.json").is_file()


def test_soul_auto_captures_only_completed_conversation_turns(mock_llm, tmp_workspace):
    ObsidianLearningWiki(LearningStore(tmp_workspace), tmp_workspace).set_auto_capture(enabled=True)
    soul = Soul(llm=mock_llm(["这里是最终回复。"]), tools=[])

    outcome = soul.run("请保存这轮学习讨论。")

    pages = [path for path in (tmp_workspace / "learning-wiki" / "conversations").glob("*.md") if path.name != "index.md"]
    assert outcome.status == "completed"
    assert len(pages) == 1
    content = pages[0].read_text(encoding="utf-8")
    assert "请保存这轮学习讨论。" in content
    assert "这里是最终回复。" in content
