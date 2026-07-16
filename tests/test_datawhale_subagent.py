from __future__ import annotations

import json

import pytest

from whale_cli.soul.approval import Approval
from whale_cli.subagents import DatawhaleKnowledgeBase, DatawhaleKnowledgeBaseUpdater, SubagentRunner
from whale_cli.tools.agent import AgentTool


def _document_line(*, title: str, url: str, text: str, tokens: list[str], tags: list[str]) -> str:
    return (
        json.dumps(
            {
                "title": title,
                "url": url,
                "text": text,
                "tokens": tokens,
                "tags": tags,
                "metadata": {"stars": 100},
            },
            ensure_ascii=False,
        )
        + "\n"
    )


def test_datawhale_kb_retrieves_local_project_evidence(tmp_path):
    corpus = tmp_path / "datawhale.jsonl"
    corpus.write_text(_document_line(
        title="datawhalechina/llm-deploy",
        url="https://example.test/llm-deploy",
        text="大模型 LLM 推理和部署理论与实践，覆盖量化与 LoRA。",
        tokens=["llm", "deploy", "量化", "lora", "部署"],
        tags=["llm", "llm-deploy", "quantization"],
    ), encoding="utf-8")
    with corpus.open("a", encoding="utf-8") as source:
        source.write(_document_line(
            title="datawhalechina/leetcode-notes",
            url="https://example.test/leetcode",
            text="算法、面试和刷题笔记。",
            tokens=["leetcode", "algorithms", "算法"],
            tags=["algorithms"],
        ))

    kb = DatawhaleKnowledgeBase(corpus)
    matches = kb.search("我想学习 LLM 部署和量化")

    assert matches[0].title == "datawhalechina/llm-deploy"
    assert "https://example.test/llm-deploy" in kb.context_for("LLM 部署")


def test_datawhale_kb_uses_bm25_length_normalization(tmp_path):
    corpus = tmp_path / "datawhale.jsonl"
    corpus.write_text(_document_line(
        title="long agent notes",
        url="https://example.test/long",
        text="long document",
        tokens=["agent", *["background" for _ in range(300)]],
        tags=[],
    ) + _document_line(
        title="short agent notes",
        url="https://example.test/short",
        text="short document",
        tokens=["agent"],
        tags=[],
    ), encoding="utf-8")

    matches = DatawhaleKnowledgeBase(corpus).search("agent")

    assert matches[0].title == "short agent notes"


def test_datawhale_kb_replaces_only_valid_jsonl_and_rebuilds_its_cache(tmp_path):
    corpus = tmp_path / "datawhale.jsonl"
    kb = DatawhaleKnowledgeBase(corpus)
    raw = _document_line(
        title="datawhalechina/new-project",
        url="https://example.test/new",
        text="新的 Agent 练习项目。",
        tokens=["agent", "练习"],
        tags=["agent"],
    ).encode("utf-8")

    assert kb.replace_corpus(raw) == 1
    assert kb.search("Agent")[0].title == "datawhalechina/new-project"
    with pytest.raises(ValueError, match="Invalid JSONL"):
        kb.replace_corpus(b"not-json\n")
    assert kb.search("Agent")[0].title == "datawhalechina/new-project"


def test_datawhale_kb_updater_imports_the_latest_completed_run(tmp_path):
    runs = tmp_path / "bm25_runs"
    old_run = runs / "20260707-120000"
    latest_run = runs / "20260708-151258"
    old_run.mkdir(parents=True)
    latest_run.mkdir(parents=True)
    (old_run / "datawhale_bm25_documents.jsonl").write_text(_document_line(
        title="old project", url="https://example.test/old", text="old corpus", tokens=["old"], tags=[]
    ), encoding="utf-8")
    (latest_run / "datawhale_bm25_documents.jsonl").write_text(_document_line(
        title="latest Agent project", url="https://example.test/latest", text="latest corpus", tokens=["agent"], tags=["agent"]
    ), encoding="utf-8")
    (latest_run / "datawhale_bm25_manifest.json").write_text(json.dumps({
        "documentCount": 1, "countsBySourceType": {"github_repo": 1}, "githubReadmeCount": 1,
    }), encoding="utf-8")
    kb = DatawhaleKnowledgeBase(tmp_path / ".whale_cli" / "datawhale_bm25_documents.jsonl")
    updater = DatawhaleKnowledgeBaseUpdater(kb, runs)

    preview = updater.preview()
    synced = updater.sync_latest()

    assert preview["latest_run"] == "20260708-151258"
    assert preview["source_document_count"] == 1
    assert preview["github_readme_count"] == 1
    assert kb.search("agent")[0].title == "latest Agent project"
    assert synced["last_update"]["source_run"] == "20260708-151258"
    assert json.loads(updater.state_path.read_text(encoding="utf-8"))["imported_count"] == 1


def test_datawhale_learning_subagent_plans_from_retrieved_context(mock_llm, tmp_path):
    corpus = tmp_path / "datawhale.jsonl"
    corpus.write_text(_document_line(
        title="datawhalechina/Agent-Learning-Hub",
        url="https://example.test/agent-hub",
        text="AI Agent 学习路线与资料库收集。",
        tokens=["agent", "learning", "学习", "路线"],
        tags=["agent", "tutorial"],
    ), encoding="utf-8")
    llm = mock_llm(["建议先完成 Agent-Learning-Hub，再做一个工具调用练习。"])
    runner = SubagentRunner(
        llm=llm,
        approval=Approval(yolo=True),
        datawhale_kb=DatawhaleKnowledgeBase(corpus),
    )

    result = runner.run("我是 Python 初学者，每周 6 小时，想学 Agent。", agent_type="datawhale_learning")

    assert "Agent-Learning-Hub" in llm.calls[0]["messages"][-1]["content"]
    assert llm.calls[0]["tools"] == []
    assert "建议先完成" in result.summary
    assert "datawhale_learning" in AgentTool.schema["function"]["parameters"]["properties"]["agent_type"]["enum"]
