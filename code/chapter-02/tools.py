"""第 2 章 · 工具定义：ReadFile + ListDir。"""
from pathlib import Path

from registry import Tool


class ReadFileTool(Tool):
    name = "read_file"
    description = (
        "读取当前项目中的 UTF-8 文本文件。"
        "当回答问题需要知道文件内容时使用。"
    )
    schema = {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": (
                "读取当前项目中的 UTF-8 文本文件。"
                "当回答问题需要知道文件内容时使用。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "要读取的文件路径",
                    }
                },
                "required": ["path"],
            },
        },
    }

    def __call__(self, *, path: str) -> str:
        try:
            return Path(path).read_text(encoding="utf-8")
        except Exception as exc:
            return f"Error: {type(exc).__name__}: {exc}"


class ListDirTool(Tool):
    name = "list_dir"
    description = (
        "列出指定目录下的文件和子目录。"
        "当不知道文件路径，需要先查看目录结构时使用。"
    )
    schema = {
        "type": "function",
        "function": {
            "name": "list_dir",
            "description": (
                "列出指定目录下的文件和子目录。"
                "当不知道文件路径，需要先查看目录结构时使用。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "要查看的目录，默认是当前目录",
                    }
                },
            },
        },
    }

    def __call__(self, *, path: str = ".") -> str:
        try:
            items = sorted(Path(path).iterdir())
        except Exception as exc:
            return f"Error: {type(exc).__name__}: {exc}"

        return "\n".join(
            item.name + ("/" if item.is_dir() else "")
            for item in items
        )
