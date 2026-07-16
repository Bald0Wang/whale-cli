from __future__ import annotations

import json

from ...background import BackgroundTaskManager
from ...security import WorkspaceViolation
from ..base import Tool, err, ok


class BackgroundStartTool(Tool):
    name = "BackgroundStart"
    description = "Run a long shell command in the background and return a task id."
    approval_action = "run background command"
    schema = {
        "type": "function",
        "function": {
            "name": name,
            "description": description,
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {"type": "string"},
                    "description": {"type": "string"},
                    "timeout_s": {"type": "integer", "default": 300},
                },
                "required": ["command"],
            },
        },
    }

    def __init__(self, manager: BackgroundTaskManager):
        self.manager = manager

    def __call__(self, command: str, description: str = "", timeout_s: int = 300):
        try:
            view = self.manager.start(command=command, description=description, timeout_s=timeout_s)
        except WorkspaceViolation as e:
            return err(f"Error: {e}")
        return ok(json.dumps({"task_id": view.spec.id, "status": view.runtime.status}, ensure_ascii=False))


class BackgroundListTool(Tool):
    name = "BackgroundList"
    description = "List background tasks and their current status."
    schema = {
        "type": "function",
        "function": {
            "name": name,
            "description": description,
            "parameters": {"type": "object", "properties": {}},
        },
    }

    def __init__(self, manager: BackgroundTaskManager):
        self.manager = manager

    def __call__(self):
        rows = [
            {
                "id": v.spec.id,
                "description": v.spec.description,
                "status": v.runtime.status,
                "exit_code": v.runtime.exit_code,
            }
            for v in self.manager.list()
        ]
        return ok(json.dumps(rows, ensure_ascii=False))


class BackgroundOutputTool(Tool):
    name = "BackgroundOutput"
    description = "Read output from a background task."
    schema = {
        "type": "function",
        "function": {
            "name": name,
            "description": description,
            "parameters": {
                "type": "object",
                "properties": {
                    "task_id": {"type": "string"},
                    "offset": {"type": "integer", "default": 0},
                },
                "required": ["task_id"],
            },
        },
    }

    def __init__(self, manager: BackgroundTaskManager):
        self.manager = manager

    def __call__(self, task_id: str, offset: int = 0):
        try:
            text, next_offset, runtime = self.manager.output(task_id, offset)
        except FileNotFoundError:
            return err(f"Background task not found: {task_id}")
        payload = {
            "task_id": task_id,
            "status": runtime.status,
            "exit_code": runtime.exit_code,
            "next_offset": next_offset,
            "output": text,
        }
        return ok(json.dumps(payload, ensure_ascii=False))
