from __future__ import annotations

import contextlib
import io
from dataclasses import dataclass
from typing import Any, Callable, List

from ..soul.approval import Approval
from ..tools.base import Tool
from ..tools.bash.bash_tool import BashTool
from ..tools.file.edit_tool import EditTool
from ..tools.file.glob_tool import GlobTool
from ..tools.file.grep_tool import GrepTool
from ..tools.file.read_tool import ReadFileTool
from ..tools.file.write_tool import WriteFileTool
from ..tools.time.getdate_tool import GetDateTool
from .datawhale import DatawhaleKnowledgeBase


@dataclass
class SubagentResult:
    summary: str
    transcript: str


def default_subagent_tools(agent_type: str) -> List[Tool]:
    if agent_type == "datawhale_learning":
        return []
    base: List[Tool] = [ReadFileTool(), GlobTool(), GrepTool(), GetDateTool()]
    if agent_type == "coder":
        base.extend([WriteFileTool(), EditTool(), BashTool()])
    return base


class SubagentRunner:
    """Run a focused child Soul with a fresh message list."""

    def __init__(
        self,
        *,
        llm: Any,
        approval: Approval,
        tool_factory: Callable[[str], List[Tool]] = default_subagent_tools,
        max_steps: int = 8,
        datawhale_kb: DatawhaleKnowledgeBase | None = None,
    ):
        self.llm = llm
        self.approval = approval
        self.tool_factory = tool_factory
        self.max_steps = max_steps
        self.datawhale_kb = datawhale_kb or DatawhaleKnowledgeBase()

    def run(self, prompt: str, agent_type: str = "explore") -> SubagentResult:
        if agent_type == "datawhale_learning":
            return self._run_datawhale_learning(prompt)
        from ..soul.soul import Soul

        tools = self.tool_factory(agent_type)
        child = Soul(
            llm=self.llm,
            tools=tools,
            max_steps=self.max_steps,
            approval=self.approval,
        )
        # Add a small role hint without sharing parent messages.
        child.messages[0]["content"] += (
            f"\n\nSubagent role: {agent_type}. Work in a focused context and return a compact summary."
        )
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            child.run(prompt)
        transcript = buf.getvalue()
        summary = ""
        for message in reversed(child.messages):
            if message.get("role") == "assistant" and isinstance(message.get("content"), str):
                summary = message["content"] or ""
                if summary:
                    break
        return SubagentResult(summary=summary, transcript=transcript)

    def _run_datawhale_learning(self, prompt: str) -> SubagentResult:
        if not self.datawhale_kb.available:
            return SubagentResult(
                summary=(
                    "Datawhale knowledge base is unavailable. Set DATAWHALE_KB_PATH "
                    "to datawhale_bm25_documents.jsonl before requesting a learning plan."
                ),
                transcript="",
            )

        from ..soul.soul import Soul

        evidence = self.datawhale_kb.context_for(prompt)
        child = Soul(
            llm=self.llm,
            tools=self.tool_factory("datawhale_learning"),
            max_steps=self.max_steps,
            approval=self.approval,
        )
        child.messages[0]["content"] += (
            "\n\nYou are the Datawhale learning-planning subagent. Use only the supplied local "
            "Datawhale project evidence for project recommendations. Do not invent project URLs or "
            "claim a project teaches material not shown in the evidence. Return a Chinese learning plan "
            "with: learner assumptions, 3-5 ranked projects with URLs and reasons, a staged route, "
            "practice milestones, and one question that would improve the next plan."
        )
        grounded_prompt = f"Learner request:\n{prompt}\n\nLocal Datawhale evidence:\n{evidence}"
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            child.run(grounded_prompt)
        summary = ""
        for message in reversed(child.messages):
            if message.get("role") == "assistant" and isinstance(message.get("content"), str):
                summary = message["content"] or ""
                if summary:
                    break
        return SubagentResult(summary=summary, transcript=buf.getvalue())
