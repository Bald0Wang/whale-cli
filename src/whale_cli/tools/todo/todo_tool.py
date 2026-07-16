"""TodoWrite tool — the model manages its own task list.

Todo list contract:
- Passing a list of {title, status} replaces the whole list.
- Passing None / empty (omitting todos) queries the current list.
- status ∈ {pending, in_progress, done}.

The tool is wired to the Soul's TodoStore via constructor injection; the
Toolset does not do this injection automatically, so Soul builds TodoWrite
with a reference to its own store (see Soul.__init__).
"""
from __future__ import annotations

from typing import Any, List, Optional

from ..base import Tool, err, ok
from ...soul.todo_store import Todo, TodoStore


class TodoWriteTool(Tool):
    name = "TodoWrite"
    description = "Create or update the agent's task list (wholesale replace)."
    schema = {
        "type": "function",
        "function": {
            "name": "TodoWrite",
            "description": (
                "Set the full task list. Pass an array of {title, status} to replace the "
                "current list, or omit/empty it to read the current list back. "
                "Use this for multi-step tasks: create todos at the start, flip a todo to "
                "'in_progress' when you begin it, and to 'done' when finished. Don't over-use "
                "it for trivial single-step requests."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "todos": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "title": {"type": "string", "description": "Short task description."},
                                "status": {
                                    "type": "string",
                                    "enum": ["pending", "in_progress", "done"],
                                    "description": "Task status (default: pending).",
                                },
                            },
                            "required": ["title"],
                        },
                        "description": "Full task list (replaces existing). Omit to query.",
                    },
                },
                "required": [],
            },
        },
    }

    def __init__(self, store: TodoStore):
        self.store = store

    def __call__(self, *, todos: Optional[List[dict]] = None) -> dict:
        # Query mode: todos is None or absent.
        if todos is None:
            current = self.store.to_dict_list()
            return ok(
                f"Current todo list ({len(current)} items):\n" + self.store.render()
                if current
                else "Todo list is empty."
            )

        if not isinstance(todos, list):
            return err("Error: todos must be an array.")

        # Empty list = clear.
        if len(todos) == 0:
            self.store.clear()
            return ok("Cleared the todo list.")

        # Validate + replace.
        try:
            new_items = []
            for i, item in enumerate(todos):
                if not isinstance(item, dict):
                    return err(f"Error: todos[{i}] must be an object, got {type(item).__name__}")
                title = item.get("title")
                status = item.get("status", "pending")
                if not title or not str(title).strip():
                    return err(f"Error: todos[{i}].title is required and non-empty")
                new_items.append(Todo(title=str(title), status=status))
        except ValueError as e:
            return err(f"Error: {e}")

        self.store.replace_all(new_items)
        return ok(f"Updated todo list ({len(new_items)} items):\n" + self.store.render())
