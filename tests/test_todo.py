"""Unit tests for TodoStore and TodoWriteTool."""
from __future__ import annotations

import pytest

from whale_cli.soul.todo_store import Todo, TodoStore
from whale_cli.tools.todo.todo_tool import TodoWriteTool


# ---- TodoStore ------------------------------------------------------------

def test_todo_valid_statuses():
    Todo(title="a", status="pending")
    Todo(title="b", status="in_progress")
    Todo(title="c", status="done")


def test_todo_invalid_status():
    with pytest.raises(ValueError):
        Todo(title="a", status="completed")  # wrong word
    with pytest.raises(ValueError):
        Todo(title="a", status="whatever")


def test_todo_empty_title():
    with pytest.raises(ValueError):
        Todo(title="   ")


def test_store_replace_all():
    s = TodoStore()
    s.replace_all([Todo(title="t1"), Todo(title="t2", status="done")])
    assert len(s.all()) == 2
    assert s.all()[0].status == "pending"
    assert s.all()[1].status == "done"


def test_store_clear_and_render():
    s = TodoStore([Todo(title="x")])  # type: ignore[arg-type]
    s.clear()
    assert s.all() == []
    assert "no todos" in s.render().lower()


def test_store_summary():
    s = TodoStore()
    s.replace_all([
        Todo(title="done1", status="done"),
        Todo(title="doing", status="in_progress"),
        Todo(title="later", status="pending"),
    ])
    summary = s.summary_for_llm()
    assert "1/3" in summary
    assert "doing" in summary


def test_render_marks():
    s = TodoStore()
    s.replace_all([
        Todo(title="a", status="pending"),
        Todo(title="b", status="in_progress"),
        Todo(title="c", status="done"),
    ])
    out = s.render()
    assert "[ ]" in out  # pending
    assert "[~]" in out  # in_progress
    assert "[x]" in out  # done


# ---- TodoWriteTool --------------------------------------------------------

def test_todowrite_replaces_list():
    store = TodoStore()
    tool = TodoWriteTool(store)
    r = tool(todos=[{"title": "step1", "status": "pending"}, {"title": "step2", "status": "done"}])
    assert r["exit_code"] == 0
    assert len(store.all()) == 2


def test_todowrite_default_status_pending():
    store = TodoStore()
    tool = TodoWriteTool(store)
    tool(todos=[{"title": "only title, no status"}])
    assert store.all()[0].status == "pending"


def test_todowrite_query_mode():
    store = TodoStore()
    store.replace_all([Todo(title="existing")])
    tool = TodoWriteTool(store)
    r = tool()  # no todos arg
    assert r["exit_code"] == 0
    assert "existing" in r["stdout"]


def test_todowrite_empty_clears():
    store = TodoStore()
    store.replace_all([Todo(title="old")])
    tool = TodoWriteTool(store)
    r = tool(todos=[])
    assert r["exit_code"] == 0
    assert store.all() == []


def test_todowrite_invalid_status_rejected():
    store = TodoStore()
    tool = TodoWriteTool(store)
    r = tool(todos=[{"title": "x", "status": "bogus"}])
    assert r["exit_code"] == 1
    assert store.all() == []  # nothing written on failure


def test_todowrite_missing_title_rejected():
    store = TodoStore()
    tool = TodoWriteTool(store)
    r = tool(todos=[{"status": "pending"}])
    assert r["exit_code"] == 1


def test_todowrite_non_dict_item_rejected():
    store = TodoStore()
    tool = TodoWriteTool(store)
    r = tool(todos=["not a dict"])  # type: ignore[list-item]
    assert r["exit_code"] == 1


def test_todowrite_via_toolset_handle():
    """End-to-end through Toolset.handle (JSON path, like Soul uses it)."""
    import json
    from whale_cli.soul.toolset import Toolset
    store = TodoStore()
    ts = Toolset([TodoWriteTool(store)])
    args = json.dumps({"todos": [{"title": "from toolset", "status": "in_progress"}]})
    r = ts.handle("TodoWrite", args)
    assert r["exit_code"] == 0
    assert store.all()[0].title == "from toolset"
    assert store.all()[0].status == "in_progress"
