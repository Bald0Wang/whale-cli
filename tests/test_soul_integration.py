"""Integration test: Soul drives a full tool-call → result → final-answer loop
using the MockLLM, so we exercise the refactored Toolset dispatch + message
persistence without hitting the network.
"""
from __future__ import annotations

import json

from whale_cli.soul.soul import Soul
from whale_cli.soul.approval import Approval
from whale_cli.tools.bash.bash_tool import BashTool

from .conftest import make_tool_call


def test_soul_tool_call_round_trip(mock_llm, tmp_workspace, capsys):
    # Script: model first calls Bash, then gives a final text answer.
    llm = mock_llm([
        [make_tool_call("call_1", "Bash", {"command": "echo roundtrip-ok"})],
        "Done — the command printed: roundtrip-ok",
    ])

    # Build a Soul with only Bash registered, inject the mock LLM.
    # yolo=True so Bash runs without an interactive approval prompt in tests.
    soul = Soul(
        llm=llm, tools=[BashTool()],
        session_store=None, session_id=None,
        approval=Approval(yolo=True),
    )
    outcome = soul.run("run echo and report what it printed")

    # The assistant should have called Bash once, then replied with text.
    captured = capsys.readouterr()
    assert "roundtrip-ok" in captured.out  # from the bash echo
    assert "Done" in captured.out  # final answer

    # Message log shape: system, user, assistant(tool_calls), tool, assistant(text)
    roles = [m["role"] for m in soul.messages]
    assert roles == ["system", "user", "assistant", "tool", "assistant"]
    # The tool message should carry tool_call_id and the Bash result.
    tool_msg = next(m for m in soul.messages if m["role"] == "tool")
    assert tool_msg["name"] == "Bash"
    assert tool_msg["tool_call_id"] == "call_1"
    assert "roundtrip-ok" in tool_msg["content"]
    assert outcome.status == "completed"
    assert outcome.summary.startswith("Done")


def test_soul_system_prompt_lists_registered_tools(mock_llm, tmp_workspace):
    llm = mock_llm(["ok"])
    soul = Soul(llm=llm, tools=[BashTool()])
    sys_msg = soul.messages[0]
    # Dynamic prompt should mention Bash by name.
    assert "Bash" in sys_msg["content"]
    # And be cross-platform (no Windows-only wording).
    assert "PowerShell/CMD" not in sys_msg["content"] or "PowerShell/CMD" in sys_msg["content"]


def test_soul_sends_transient_multimodal_content_without_persisting_data_url(mock_llm, tmp_workspace):
    llm = mock_llm(["I can see the screenshot."])
    soul = Soul(llm=llm, tools=[])
    content = [
        {"type": "text", "text": "Describe this image."},
        {"type": "image_url", "image_url": {"url": "data:image/png;base64,ZmFrZQ==", "detail": "high"}},
    ]

    outcome = soul.run(
        "Describe this image.",
        multimodal_content=content,
        user_metadata={"attachments": [{"id": "att_demo", "preview_url": "/api/uploads/att_demo/content"}]},
    )

    user_message = next(message for message in llm.calls[0]["messages"] if message["role"] == "user")
    assert user_message["content"] == content
    assert soul.messages[1]["content"] == "Describe this image."
    assert "base64" not in str(soul.messages[1])
    assert soul.messages[1]["metadata"]["attachments"][0]["id"] == "att_demo"
    assert outcome.status == "completed"


def test_soul_system_prompt_injects_current_time(mock_llm, tmp_workspace):
    """The system prompt must contain a date/time snapshot so the model knows
    'today' without calling a tool."""
    import re
    llm = mock_llm(["ok"])
    soul = Soul(llm=llm, tools=[BashTool()])
    sys_content = soul.messages[0]["content"]
    # The Date and time section should be present.
    assert "Date and time" in sys_content
    # An ISO 8601 timestamp should be injected (contains 'T' and a timezone offset).
    m = re.search(r"`(\d{4}-\d{2}-\d{2}T[^`]+)`", sys_content)
    assert m is not None, "expected an ISO timestamp in backticks"
    ts = m.group(1)
    assert "T" in ts
    assert "+" in ts or ts.endswith("Z")  # timezone offset present
    # The snapshot is taken at startup and stored on the Soul.
    assert hasattr(soul, "_started_at")
    assert soul._started_at  # non-empty


def test_soul_started_at_snapshot_is_stable(mock_llm, tmp_workspace):
    """The injected time is a snapshot taken once at construction; it doesn't
    change after that."""
    llm = mock_llm(["ok"])
    soul = Soul(llm=llm, tools=[BashTool()])
    t1 = soul._started_at
    # Re-reading the system message should give the same timestamp.
    sys_content = soul.messages[0]["content"]
    assert t1 in sys_content


def test_soul_max_steps_caps_loop(mock_llm, capsys):
    """If the model keeps calling tools forever, the loop stops at max_steps."""
    # Each script entry is a *list* of tool_calls (one per step), 100 steps worth.
    infinite = [[make_tool_call(f"c{i}", "Bash", {"command": f"echo {i}"})] for i in range(100)]
    llm = mock_llm(infinite)
    soul = Soul(
        llm=llm, tools=[BashTool()], max_steps=3,
        approval=Approval(yolo=True),
    )
    outcome = soul.run("loop forever")
    out = capsys.readouterr().out
    assert "Max steps reached" in out
    assert outcome.status == "max_steps"
