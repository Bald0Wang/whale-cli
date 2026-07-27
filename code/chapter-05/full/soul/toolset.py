"""Toolset — 工具注册与调度中心。

注册所有 Tool 实例，提供 schema 列表给模型，按名字分发调用。
"""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from tools.base import Tool


class Toolset:
    def __init__(self, tools: Optional[List[Tool]] = None):
        self._tools: Dict[str, Tool] = {}
        for t in tools or []:
            self.register(t)

    def register(self, tool: Tool) -> None:
        if not tool.name:
            raise ValueError(f"Tool {tool!r} has empty name")
        self._tools[tool.name] = tool

    def all_schemas(self) -> List[Dict[str, Any]]:
        return [t.schema for t in self._tools.values()]

    def handle(self, name: str, args_str: str) -> Dict[str, Any]:
        tool = self._tools.get(name)
        if tool is None:
            return {"stdout": "", "stderr": f"Error: Tool {name!r} not found.", "exit_code": 1}

        try:
            args = json.loads(args_str) if args_str else {}
        except json.JSONDecodeError as e:
            return {"stdout": "", "stderr": f"Error: invalid JSON for {name}: {e}", "exit_code": 1}

        try:
            result = tool(**args)
        except Exception as e:
            return {"stdout": "", "stderr": f"Error executing {name}: {e}", "exit_code": 1}

        if isinstance(result, str):
            return {"stdout": result, "stderr": "", "exit_code": 0}
        if isinstance(result, dict):
            return {
                "stdout": result.get("stdout", ""),
                "stderr": result.get("stderr", ""),
                "exit_code": result.get("exit_code", 0),
            }
        return {"stdout": str(result), "stderr": "", "exit_code": 0}
