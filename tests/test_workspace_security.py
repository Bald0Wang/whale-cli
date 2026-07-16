"""Tests for workspace boundaries and the conservative command policy."""
from __future__ import annotations

from pathlib import Path

import pytest

from whale_cli.background import BackgroundTaskManager
from whale_cli.security import WorkspaceViolation
from whale_cli.tools.bash.bash_tool import BashTool
from whale_cli.tools.file.edit_tool import EditTool
from whale_cli.tools.file.write_tool import WriteFileTool


def test_writefile_rejects_absolute_path_outside_workspace(tmp_path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    outside = tmp_path / "outside.txt"

    result = WriteFileTool(workspace)(path=str(outside), content="nope")

    assert result["exit_code"] == 1
    assert "escapes workspace" in result["stderr"]
    assert not outside.exists()


def test_writefile_allows_absolute_path_inside_workspace(tmp_path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    target = workspace / "safe.txt"

    result = WriteFileTool(workspace)(path=str(target), content="safe")

    assert result["exit_code"] == 0
    assert target.read_text(encoding="utf-8") == "safe"


def test_writefile_rejects_symlink_escape(tmp_path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    (workspace / "link").symlink_to(outside, target_is_directory=True)

    result = WriteFileTool(workspace)(path="link/escaped.txt", content="nope")

    assert result["exit_code"] == 1
    assert not (outside / "escaped.txt").exists()


def test_edit_rejects_parent_path(tmp_path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    outside = tmp_path / "outside.txt"
    outside.write_text("before", encoding="utf-8")

    result = EditTool(workspace)(path="../outside.txt", old_string="before", new_string="after")

    assert result["exit_code"] == 1
    assert outside.read_text(encoding="utf-8") == "before"


def test_bash_runs_in_configured_workspace(tmp_path):
    result = BashTool(tmp_path)(command="pwd")

    assert result["exit_code"] == 0
    assert result["stdout"].strip() == str(tmp_path.resolve())


@pytest.mark.parametrize(
    "command",
    [
        "rm file.txt",
        "printf hi > output.txt",
        "cat ../outside.txt",
        "cat /etc/hosts",
        "git reset --hard",
    ],
)
def test_bash_blocks_dangerous_or_outside_commands(tmp_path, command):
    result = BashTool(tmp_path)(command=command)

    assert result["exit_code"] == 1
    assert "policy" in result["stderr"].lower() or "not allowed" in result["stderr"].lower()


def test_background_manager_rejects_cwd_outside_workspace(tmp_path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    manager = BackgroundTaskManager(tmp_path / "tasks", workspace=workspace)

    with pytest.raises(WorkspaceViolation):
        manager.start("printf blocked", cwd=str(tmp_path))
