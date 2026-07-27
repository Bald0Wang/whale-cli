"""第 1 章 · 最小工具：只有一个 read_file。"""
from pathlib import Path
from typing import Any, Callable


TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": (
                "读取当前项目中的 UTF-8 文本文件。"
                "当回答问题需要知道本地文件内容时使用。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "相对于当前工作目录的文件路径",
                    }
                },
                "required": ["path"],
            },
        },
    }
]


def read_file(path: str) -> str:
    try:
        return Path(path).read_text(encoding="utf-8")
    except Exception as exc:
        return f"Error: {type(exc).__name__}: {exc}"


TOOL_FUNCTIONS: dict[str, Callable[..., str]] = {
    "read_file": read_file,
}


def run_tool(name: str, args: dict[str, Any]) -> str:
    fn = TOOL_FUNCTIONS.get(name)
    if fn is None:
        return f"Error: unknown tool '{name}'"

    try:
        return fn(**args)
    except Exception as exc:
        return f"Error: {type(exc).__name__}: {exc}"
