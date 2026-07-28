"""Write tool — 把完整内容写入文件。"""

from pathlib import Path

from tools.base import Tool, ok, err


class WriteFileTool(Tool):
    name = "WriteFile"
    description = "Write content to a file."

    schema = {
        "type": "function",
        "function": {
            "name": "WriteFile",
            "description": "Write content to a file. Overwrites existing file by default.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "The file path to write to."},
                    "content": {"type": "string", "description": "The content to write."},
                },
                "required": ["path", "content"],
            },
        },
    }

    def __call__(self, *, path: str, content: str) -> dict:
        target = Path(path).resolve()
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        return ok(f"Successfully wrote to {path}", changed_files=[path])
