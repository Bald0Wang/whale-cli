import subprocess
from pathlib import Path

from ...security import WorkspaceViolation, parse_workspace_command, workspace_root
from ..base import Tool

class BashTool(Tool):
    name = "Bash"
    description = "Execute a shell command on the local machine."
    approval_action = "run command"

    def __init__(self, workspace: str | Path | None = None):
        self.workspace = workspace_root(workspace)

    schema = {
        "type": "function",
        "function": {
            "name": "Bash",
            "description": "Execute a shell command. Use this to explore filesystem or run scripts.",
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {
                        "type": "string",
                        "description": "The shell command to execute."
                    }
                },
                "required": ["command"]
            }
        }
    }

    def __call__(self, *, command: str) -> dict:
        print(f"\033[90m[System] Executing: {command}\033[0m")
        try:
            tokens = parse_workspace_command(command)
            result = subprocess.run(
                tokens,
                shell=False,
                cwd=self.workspace,
                capture_output=True, 
                text=True, 
                timeout=30,
                encoding='utf-8',
                errors='replace'
            )
            stdout = result.stdout or ""
            stderr = result.stderr or ""
            return {
                "stdout": stdout if stdout else "(No output)",
                "stderr": stderr,
                "exit_code": result.returncode,
                "changed_files": []
            }
        except WorkspaceViolation as e:
            return {
                "stdout": "",
                "stderr": f"Error: {e}",
                "exit_code": 1,
                "changed_files": []
            }
        except subprocess.TimeoutExpired:
            return {
                "stdout": "",
                "stderr": "Error: Command timed out.",
                "exit_code": 124,
                "changed_files": []
            }
        except Exception as e:
            return {
                "stdout": "",
                "stderr": f"Error: {str(e)}",
                "exit_code": 1,
                "changed_files": []
            }
