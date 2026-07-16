"""Unit tests for the Approval layer."""
from __future__ import annotations

import json
import threading

from whale_cli.soul.approval import Approval
from whale_cli.soul.toolset import Toolset
from whale_cli.tools.base import Tool
from whale_cli.tools.bash.bash_tool import BashTool


class _RecordingPrompt:
    """A scripted prompt_fn that returns a queue of answers and records calls."""

    def __init__(self, answers):
        self.answers = list(answers)
        self.calls = []

    def __call__(self, action, description):
        self.calls.append((action, description))
        return self.answers.pop(0) if self.answers else "reject"


# ---- core request logic ---------------------------------------------------

def test_approve_single_time():
    # Two "approve" answers because approve (single) doesn't remember.
    p = _RecordingPrompt(["approve", "approve"])
    a = Approval(prompt_fn=p)
    assert a.request("run command", "Bash(echo)") is True
    assert len(p.calls) == 1
    # approve does NOT remember → second call prompts again
    assert a.request("run command", "Bash(echo)") is True
    assert len(p.calls) == 2


def test_approve_for_session_remembers():
    p = _RecordingPrompt(["approve_for_session", "approve_for_session"])
    a = Approval(prompt_fn=p)
    assert a.request("edit file", "Edit(f)") is True
    # second time: should NOT prompt, auto-approved from the set
    assert a.request("edit file", "Edit(f)") is True
    assert len(p.calls) == 1  # only prompted once
    assert "edit file" in a.auto_approve_actions


def test_reject_returns_false():
    p = _RecordingPrompt(["reject"])
    a = Approval(prompt_fn=p)
    assert a.request("run command", "rm -rf") is False


def test_unknown_answer_treated_as_reject():
    p = _RecordingPrompt(["garbage"])
    a = Approval(prompt_fn=p)
    assert a.request("run command", "x") is False


# ---- yolo mode ------------------------------------------------------------

def test_yolo_skips_prompt():
    p = _RecordingPrompt([])  # never expected to be called
    a = Approval(prompt_fn=p, yolo=True)
    assert a.request("run command", "anything") is True
    assert p.calls == []
    assert a.is_yolo is True


def test_set_yolo_toggle():
    p = _RecordingPrompt(["approve"])
    a = Approval(prompt_fn=p)
    a.set_yolo(True)
    assert a.request("run command", "x") is True
    assert p.calls == []  # no prompt in yolo
    a.set_yolo(False)
    assert a.request("run command", "x") is True
    assert len(p.calls) == 1  # prompts again after toggling off


def test_background_request_is_rejected_without_prompting_user():
    prompt = _RecordingPrompt(["approve"])
    approval = Approval(prompt_fn=prompt)
    outcome: list[bool] = []

    thread = threading.Thread(target=lambda: outcome.append(approval.request("run command", "Bash(...)")))
    thread.start()
    thread.join(timeout=1)

    assert outcome == [False]
    assert prompt.calls == []


# ---- Toolset integration --------------------------------------------------

def test_toolset_calls_approver_for_dangerous_tool():
    """BashTool has approval_action='run command'; toolset must consult approver."""
    p = _RecordingPrompt(["approve"])
    a = Approval(prompt_fn=p)
    ts = Toolset([BashTool()])
    ts.set_approver(a.as_approver())

    result = ts.handle("Bash", json.dumps({"command": "echo hi"}))
    assert result["exit_code"] == 0
    assert "hi" in result["stdout"]
    assert len(p.calls) == 1
    assert p.calls[0][0] == "run command"


def test_toolset_blocks_on_reject():
    p = _RecordingPrompt(["reject"])
    a = Approval(prompt_fn=p)
    ts = Toolset([BashTool()])
    ts.set_approver(a.as_approver())

    result = ts.handle("Bash", json.dumps({"command": "echo hi"}))
    assert result["exit_code"] == 126  # permission-denied sentinel
    assert "rejected" in result["stderr"].lower()
    # command was NOT run — stdout empty
    assert result["stdout"] == ""


def test_readonly_tool_skips_approval():
    """Tools without approval_action never consult the approver."""

    class _Read(Tool):
        name = "Read"
        description = "read-only"
        schema = {"type": "function", "function": {"name": "Read", "parameters": {"type": "object", "properties": {"x": {"type": "string"}}}}}
        def __call__(self, *, x):
            return {"stdout": f"read {x}", "stderr": "", "exit_code": 0, "changed_files": []}

    p = _RecordingPrompt([])  # would record if called
    a = Approval(prompt_fn=p, yolo=False)
    ts = Toolset([_Read()])
    ts.set_approver(a.as_approver())

    result = ts.handle("Read", json.dumps({"x": "data"}))
    assert result["exit_code"] == 0
    assert p.calls == []  # approver never consulted


def test_yolo_through_toolset():
    p = _RecordingPrompt([])
    a = Approval(prompt_fn=p, yolo=True)
    ts = Toolset([BashTool()])
    ts.set_approver(a.as_approver())
    result = ts.handle("Bash", json.dumps({"command": "echo yolo"}))
    assert result["exit_code"] == 0
    assert p.calls == []
