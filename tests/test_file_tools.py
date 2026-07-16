"""Unit tests for the new read-only and editing file tools.
All tests run against a tmp_workspace fixture — no network, no real LLM.
"""
from __future__ import annotations

import os

import pytest

from whale_cli.tools.file.read_tool import ReadFileTool
from whale_cli.tools.file.glob_tool import GlobTool
from whale_cli.tools.file.grep_tool import GrepTool
from whale_cli.tools.file.edit_tool import EditTool


# ---- ReadFile -------------------------------------------------------------

def test_read_file_with_line_numbers(tmp_workspace):
    (tmp_workspace / "a.txt").write_text("alpha\nbeta\ngamma\n", encoding="utf-8")
    r = ReadFileTool()(path="a.txt")
    assert r["exit_code"] == 0
    assert "     1\talpha" in r["stdout"]
    assert "     2\tbeta" in r["stdout"]
    assert "total lines: 3" in r["stdout"]


def test_read_file_offset_and_pagination(tmp_workspace):
    (tmp_workspace / "b.txt").write_text("\n".join(f"line{i}" for i in range(1, 11)) + "\n", encoding="utf-8")
    # read lines 3..5
    r = ReadFileTool()(path="b.txt", line_offset=3, n_lines=3)
    assert r["exit_code"] == 0
    assert "line3" in r["stdout"] and "line5" in r["stdout"]
    assert "line2" not in r["stdout"]
    assert "from line 3" in r["stdout"]


def test_read_file_negative_offset_from_end(tmp_workspace):
    (tmp_workspace / "c.txt").write_text("\n".join(f"n{i}" for i in range(1, 21)) + "\n", encoding="utf-8")
    r = ReadFileTool()(path="c.txt", line_offset=-3)
    assert r["exit_code"] == 0
    assert "n18" in r["stdout"] and "n20" in r["stdout"]
    assert "n17" not in r["stdout"]


def test_read_file_missing():
    r = ReadFileTool()(path="nope.xyz")
    assert r["exit_code"] == 1
    assert "not found" in r["stderr"].lower()


def test_read_file_directory(tmp_workspace):
    (tmp_workspace / "sub").mkdir()
    r = ReadFileTool()(path="sub")
    assert r["exit_code"] == 1
    assert "directory" in r["stderr"].lower()


def test_read_file_binary_refused(tmp_workspace):
    p = tmp_workspace / "bin.dat"
    p.write_bytes(b"\x00\x01\x02\x00binary\x00")
    r = ReadFileTool()(path=str(p))
    assert r["exit_code"] == 1
    assert "binary" in r["stderr"].lower()


# ---- Glob -----------------------------------------------------------------

def test_glob_finds_py_files(tmp_workspace):
    (tmp_workspace / "x.py").write_text("# x")
    (tmp_workspace / "sub").mkdir()
    (tmp_workspace / "sub" / "y.py").write_text("# y")
    (tmp_workspace / "z.txt").write_text("z")
    r = GlobTool()(pattern="**/*.py")
    assert r["exit_code"] == 0
    assert "x.py" in r["stdout"]
    assert "y.py" in r["stdout"]
    assert "z.txt" not in r["stdout"]


def test_glob_no_matches(tmp_workspace):
    r = GlobTool()(pattern="*.nonexistent-ext")
    assert r["exit_code"] == 0
    assert "no files matched" in r["stdout"].lower()


# ---- Grep -----------------------------------------------------------------

def test_grep_files_with_matches(tmp_workspace):
    (tmp_workspace / "m.py").write_text("TODO: fix\nprint('x')\n", encoding="utf-8")
    (tmp_workspace / "n.py").write_text("print('y')\n", encoding="utf-8")
    r = GrepTool()(pattern="TODO", path=".")
    assert r["exit_code"] == 0
    assert "m.py" in r["stdout"]
    assert "n.py" not in r["stdout"]


def test_grep_content_mode(tmp_workspace):
    (tmp_workspace / "m.py").write_text("alpha\nbeta\ngamma\n", encoding="utf-8")
    r = GrepTool()(pattern="beta", path="m.py", output_mode="content")
    assert r["exit_code"] == 0
    assert "beta" in r["stdout"]
    # rg shows line number; single-file mode may omit the path prefix
    assert "2:" in r["stdout"]


def test_grep_count_mode(tmp_workspace):
    (tmp_workspace / "m.py").write_text("x\nx\nx\n", encoding="utf-8")
    r = GrepTool()(pattern="x", path="m.py", output_mode="count_matches")
    assert r["exit_code"] == 0
    # rg -c on a single file prints the count; on a dir it prints path:count
    assert "3" in r["stdout"]


def test_grep_ignore_case(tmp_workspace):
    (tmp_workspace / "m.py").write_text("Hello\nHELLO\n", encoding="utf-8")
    r = GrepTool()(pattern="hello", path="m.py", output_mode="count_matches", ignore_case=True)
    assert r["exit_code"] == 0
    # both lines match when case-insensitive
    assert "2" in r["stdout"]


# ---- Edit -----------------------------------------------------------------

def test_edit_replaces_first_occurrence(tmp_workspace):
    p = tmp_workspace / "e.txt"
    p.write_text("a\nb\na\nc\n", encoding="utf-8")
    r = EditTool()(path="e.txt", old_string="a", new_string="Z")
    assert r["exit_code"] == 0
    assert r["changed_files"] == ["e.txt"]
    content = p.read_text(encoding="utf-8")
    assert content == "Z\nb\na\nc\n"  # only first 'a' replaced


def test_edit_replace_all(tmp_workspace):
    p = tmp_workspace / "e.txt"
    p.write_text("a\nb\na\n", encoding="utf-8")
    r = EditTool()(path="e.txt", old_string="a", new_string="Z", replace_all=True)
    assert r["exit_code"] == 0
    assert p.read_text(encoding="utf-8") == "Z\nb\nZ\n"


def test_edit_multiline(tmp_workspace):
    p = tmp_workspace / "e.txt"
    p.write_text("def foo():\n    return 1\n", encoding="utf-8")
    r = EditTool()(
        path="e.txt",
        old_string="def foo():\n    return 1",
        new_string="def foo():\n    return 2",
    )
    assert r["exit_code"] == 0
    assert "return 2" in p.read_text(encoding="utf-8")


def test_edit_old_string_not_found(tmp_workspace):
    p = tmp_workspace / "e.txt"
    p.write_text("hello\n", encoding="utf-8")
    r = EditTool()(path="e.txt", old_string="nonexistent", new_string="x")
    assert r["exit_code"] == 1
    assert "not found" in r["stderr"].lower()
    # file unchanged
    assert p.read_text(encoding="utf-8") == "hello\n"


def test_edit_missing_file():
    r = EditTool()(path="nope.txt", old_string="a", new_string="b")
    assert r["exit_code"] == 1
