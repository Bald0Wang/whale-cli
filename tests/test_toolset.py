"""Unit tests for the Toolset registry and the refactored tools."""
from __future__ import annotations

import json

import pytest

from whale_cli.tools.base import Tool, err, ok
from whale_cli.tools.bash.bash_tool import BashTool
from whale_cli.tools.file.write_tool import WriteFileTool
from whale_cli.tools.time.getdate_tool import GetDateTool
from whale_cli.soul.toolset import Toolset


# ---- Toolset basics -------------------------------------------------------

class _StubTool(Tool):
    name = "Echo"
    description = "echo the text"
    schema = {"type": "function", "function": {"name": "Echo", "description": "echo", "parameters": {"type": "object", "properties": {"text": {"type": "string"}}, "required": ["text"]}}}

    def __call__(self, *, text: str):
        return ok(f"echo:{text}")


class _CrashTool(Tool):
    name = "Crash"
    description = "always raises"
    schema = {"type": "function", "function": {"name": "Crash", "parameters": {"type": "object"}}}

    def __call__(self, **kwargs):
        raise RuntimeError("boom")


def test_register_and_get():
    ts = Toolset([_StubTool()])
    assert "Echo" in ts
    assert ts.get("Echo") is not None
    assert ts.get("Nope") is None
    assert ts.names == ["Echo"]


def test_duplicate_register_raises():
    ts = Toolset([_StubTool()])
    with pytest.raises(ValueError):
        ts.register(_StubTool())


def test_all_schemas_shape():
    ts = Toolset([_StubTool()])
    schemas = ts.all_schemas()
    assert schemas == [_StubTool.schema]


# ---- handle() dispatch ----------------------------------------------------

def test_handle_normal():
    ts = Toolset([_StubTool()])
    result = ts.handle("Echo", json.dumps({"text": "hi"}))
    assert result["exit_code"] == 0
    assert result["stdout"] == "echo:hi"
    assert result["changed_files"] == []


def test_handle_unknown_tool():
    ts = Toolset([_StubTool()])
    result = ts.handle("Missing", "{}")
    assert result["exit_code"] == 1
    assert "not found" in result["stderr"].lower()


def test_handle_bad_json():
    ts = Toolset([_StubTool()])
    result = ts.handle("Echo", "not-json{")
    assert result["exit_code"] == 1
    assert "invalid json" in result["stderr"].lower()


def test_handle_exception_wrapped():
    ts = Toolset([_CrashTool()])
    result = ts.handle("Crash", "{}")
    assert result["exit_code"] == 1
    assert "boom" in result["stderr"]


def test_handle_wrong_args_wrapped():
    ts = Toolset([_StubTool()])
    # Echo requires `text`; omitting it → TypeError → wrapped
    result = ts.handle("Echo", "{}")
    assert result["exit_code"] == 1
    assert "bad arguments" in result["stderr"].lower()


def test_handle_string_result_normalized():
    class _StrTool(Tool):
        name = "Str"
        description = "returns a bare string"
        schema = {"type": "function", "function": {"name": "Str", "parameters": {"type": "object"}}}
        def __call__(self, **kw):
            return "bare-string"
    ts = Toolset([_StrTool()])
    result = ts.handle("Str", "{}")
    assert result["stdout"] == "bare-string"
    assert result["exit_code"] == 0


# ---- approval gate (Phase 5 will use this; verify wiring now) -------------

def test_approval_blocks_when_rejected():
    class _Danger(Tool):
        name = "Danger"
        description = "needs approval"
        approval_action = "danger"
        schema = {"type": "function", "function": {"name": "Danger", "parameters": {"type": "object"}}}
        def __call__(self, **kw):
            return ok("ran")
    ts = Toolset([_Danger()])
    ts.set_approver(lambda action, desc: False)  # deny
    result = ts.handle("Danger", "{}")
    assert result["exit_code"] == 126
    assert "rejected" in result["stderr"].lower()


def test_approval_allows_when_approved():
    class _Danger(Tool):
        name = "Danger"
        description = "needs approval"
        approval_action = "danger"
        schema = {"type": "function", "function": {"name": "Danger", "parameters": {"type": "object"}}}
        def __call__(self, **kw):
            return ok("ran")
    ts = Toolset([_Danger()])
    ts.set_approver(lambda action, desc: True)
    result = ts.handle("Danger", "{}")
    assert result["exit_code"] == 0
    assert result["stdout"] == "ran"


def test_no_approval_action_skips_gate():
    # _StubTool has approval_action = None, so approver is never consulted.
    ts = Toolset([_StubTool()])
    ts.set_approver(lambda action, desc: False)  # would deny if consulted
    result = ts.handle("Echo", json.dumps({"text": "x"}))
    assert result["exit_code"] == 0


# ---- real tools: kwarg-only interface -------------------------------------

def test_bash_tool_runs_echo():
    t = BashTool()
    result = t(command="echo hello-phase1")
    assert result["exit_code"] == 0
    assert "hello-phase1" in result["stdout"]


def test_bash_tool_missing_kwarg():
    """BashTool now requires keyword `command`; positional no longer works."""
    t = BashTool()
    with pytest.raises(TypeError):
        t("echo hi")  # type: ignore[arg-type]


def test_writefile_overwrite_and_append(tmp_workspace):
    t = WriteFileTool()
    r1 = t(path="f.txt", content="line1\n")
    assert r1["exit_code"] == 0
    assert r1["changed_files"] == ["f.txt"]
    # append adds, overwrite replaces
    r2 = t(path="f.txt", content="line2\n", mode="append")
    assert r2["exit_code"] == 0
    content = (tmp_workspace / "f.txt").read_text(encoding="utf-8")
    assert content == "line1\nline2\n"
    r3 = t(path="f.txt", content="only\n", mode="overwrite")
    assert (tmp_workspace / "f.txt").read_text(encoding="utf-8") == "only\n"


def test_getdate_tool():
    t = GetDateTool()
    result = t()
    assert result["exit_code"] == 0
    assert len(result["stdout"]) > 0
    # utc flag accepted
    r2 = t(utc=True)
    assert r2["exit_code"] == 0
