from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from ..base import Tool


class GetDateTool(Tool):
    name = "GetDate"
    description = "Get current date/time from the local machine."

    schema = {
        "type": "function",
        "function": {
            "name": "GetDate",
            "description": "Get the current local date/time. Useful for generating timestamps or logging.",
            "parameters": {
                "type": "object",
                "properties": {
                    "format": {
                        "type": "string",
                        "description": "Optional strftime format, e.g. '%Y-%m-%d %H:%M:%S'. If omitted, returns ISO 8601.",
                    },
                    "utc": {
                        "type": "boolean",
                        "description": "If true, return time in UTC. Defaults to false (local time).",
                    },
                },
                "required": [],
            },
        },
    }

    def __call__(self, *, format: Optional[str] = None, utc: bool = False) -> dict:
        try:
            if utc:
                now = datetime.now(timezone.utc)
            else:
                now = datetime.now().astimezone()

            if format:
                value = now.strftime(format)
            else:
                value = now.isoformat()

            return {
                "stdout": value,
                "stderr": "",
                "exit_code": 0,
                "changed_files": [],
            }
        except Exception as e:
            return {
                "stdout": "",
                "stderr": f"Error: {e}",
                "exit_code": 1,
                "changed_files": [],
            }

