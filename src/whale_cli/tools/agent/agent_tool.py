from __future__ import annotations

from typing import Any

from ...soul.approval import Approval
from ...subagents import SubagentRunner
from ..base import Tool, ok


class AgentTool(Tool):
    name = "Agent"
    description = "Run a focused subagent with a fresh context and return its compact summary."
    schema = {
        "type": "function",
        "function": {
            "name": name,
            "description": description,
            "parameters": {
                "type": "object",
                "properties": {
                    "description": {"type": "string", "description": "A short 3-5 word task description."},
                    "prompt": {"type": "string", "description": "The focused task for the subagent."},
                    "agent_type": {
                        "type": "string",
                        "enum": ["explore", "coder", "datawhale_learning"],
                        "default": "explore",
                    },
                },
                "required": ["description", "prompt"],
            },
        },
    }

    def __init__(self, *, llm: Any, approval: Approval, max_steps: int = 8):
        self.runner = SubagentRunner(llm=llm, approval=approval, max_steps=max_steps)

    def __call__(self, description: str, prompt: str, agent_type: str = "explore"):
        result = self.runner.run(prompt=prompt, agent_type=agent_type or "explore")
        text = result.summary or result.transcript[-2000:]
        return ok(f"[{agent_type}] {description}\n{text}")
