"""End-to-end tests against the real Step Plan step-3.7-flash model.

These are SKIPPED by default (they need a real API key + network + money).
Run them explicitly by setting RUN_E2E=1::

    RUN_E2E=1 pytest tests/test_e2e.py -v

They exercise the full agent loop: LLM call → tool_calls dispatch → real tool
execution → result fed back → final answer. A live failure here usually means
either the model/regression changed tool-calling behavior, or a tool broke.

Prerequisites:
- ~/.whale/config.json with llm.api_key / base_url / model for Step Plan, OR
- STEP_API_KEY env var set.
- RUN_E2E=1 in the environment (otherwise skipped).
"""
from __future__ import annotations

import os
import pytest

from whale_cli.llm.client import _llm_config_section
from whale_cli.soul.soul import Soul
from whale_cli.soul.approval import Approval


@pytest.fixture
def live_workspace(tmp_path, monkeypatch):
    """An empty temp dir we chdir into, so file tools don't touch the repo."""
    monkeypatch.chdir(tmp_path)
    return tmp_path


def _has_api_key() -> bool:
    if os.getenv("STEP_API_KEY") or os.getenv("OPENAI_API_KEY") or os.getenv("MOONSHOT_API_KEY"):
        return True
    return bool(_llm_config_section().get("api_key"))


_RUN_E2E = os.getenv("RUN_E2E", "0") == "1"
_HAS_KEY = _has_api_key() if _RUN_E2E else False

# Skip the whole module unless explicitly opted in AND a key is present.
pytestmark = [
    pytest.mark.e2e,
    pytest.mark.skipif(
        not (_RUN_E2E and _HAS_KEY),
        reason="set RUN_E2E=1 and provide an API key to run e2e tests",
    ),
]


def test_e2e_basic_tool_call(live_workspace, capsys):
    """The agent calls Bash once and reports the output."""
    soul = Soul(approval=Approval(yolo=True))
    soul.run("Run this exact shell command: echo e2e-marker-12345. Then report the output in one line.")
    out = capsys.readouterr().out
    assert "e2e-marker-12345" in out
    assert "Tool Call" in out


def test_e2e_file_lifecycle(live_workspace, capsys):
    """The agent uses Glob/WriteFile/ReadFile/Edit end to end."""
    soul = Soul(approval=Approval(yolo=True))
    soul.run(
        "1. Write a file named greet.txt with the content 'hello world'. "
        "2. Then read it back to confirm. "
        "3. Tell me whether the file contains 'hello world'."
    )
    out = capsys.readouterr().out
    # File should actually exist on disk (WriteFile ran for real).
    assert os.path.exists("greet.txt")
    assert "hello world" in open("greet.txt").read()
    # The agent should have reported success.
    assert "true" in out.lower() or "yes" in out.lower() or "confirm" in out.lower()


def test_e2e_todo_tracking(live_workspace, capsys):
    """The agent creates a todo list for a multi-step task."""
    soul = Soul(approval=Approval(yolo=True))
    soul.run(
        "Do these 3 steps and track them with your todo tool: "
        "(a) create dir 'work', (b) create file work/a.txt with 'A', "
        "(c) create file work/b.txt with 'B'. Update the todo list as you go."
    )
    # Files should exist.
    assert os.path.isdir("work")
    assert os.path.exists("work/a.txt")
    assert os.path.exists("work/b.txt")
    # The todo store should reflect the work.
    todos = soul.todos.all()
    assert len(todos) >= 3
    # All should be done by the end.
    assert all(t.status == "done" for t in todos)


def test_e2e_knows_current_date_without_tool(live_workspace, capsys):
    """Because the date is injected into the system prompt, the agent should
    know today's date WITHOUT calling any tool. Verifies the runtime date
    injection actually works end to end."""
    from datetime import datetime
    soul = Soul(approval=Approval(yolo=True))
    today_iso = datetime.now().astimezone().strftime("%Y-%m-%d")
    soul.run(
        f"What is today's date? Answer in one short line, just the date. "
        f"Do NOT call any tool — just tell me the date directly."
    )
    out = capsys.readouterr().out
    assert today_iso in out, f"expected today {today_iso} in output, got: {out[-300:]}"
    # And it should NOT have called a tool.
    assert "Tool Call" not in out
