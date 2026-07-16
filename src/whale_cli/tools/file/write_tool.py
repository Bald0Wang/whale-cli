from pathlib import Path

from ...security import WorkspaceViolation, resolve_workspace_path, workspace_root
from ..base import Tool

class WriteFileTool(Tool):
    name = "WriteFile"
    description = "Write content to a file."
    approval_action = "edit file"

    def __init__(self, workspace: str | Path | None = None):
        self.workspace = workspace_root(workspace)

    schema = {
        "type": "function",
        "function": {
            "name": "WriteFile",
            "description": "Write content to a file. Overwrites existing file by default. Use mode='append' to add to the end instead.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "The file path to write to."
                    },
                    "content": {
                        "type": "string",
                        "description": "The content to write."
                    },
                    "mode": {
                        "type": "string",
                        "enum": ["overwrite", "append"],
                        "description": "overwrite (default) replaces the file; append adds to the end.",
                    },
                },
                "required": ["path", "content"]
            }
        }
    }

    def __call__(self, *, path: str, content: str, mode: str = "overwrite") -> dict:
        print(f"\033[90m[System] Writing to file: {path} ({mode})\033[0m")
        try:
            target = resolve_workspace_path(path, self.workspace)

            if mode == "append":
                with target.open("a", encoding="utf-8") as f:
                    f.write(content)
                action = "Appended to"
            else:
                with target.open("w", encoding="utf-8") as f:
                    f.write(content)
                action = "Successfully wrote to"
            return {
                "stdout": f"{action} {target.relative_to(self.workspace)}",
                "stderr": "",
                "exit_code": 0,
                "changed_files": [str(target.relative_to(self.workspace))]
            }
        except WorkspaceViolation as e:
            return {
                "stdout": "",
                "stderr": f"Error: {e}",
                "exit_code": 1,
                "changed_files": []
            }
        except Exception as e:
            return {
                "stdout": "",
                "stderr": f"Error writing file: {str(e)}",
                "exit_code": 1,
                "changed_files": []
            }
