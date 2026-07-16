from __future__ import annotations

import time
from dataclasses import asdict, dataclass, field
from typing import Any, Literal

TaskStatus = Literal["created", "running", "completed", "failed", "killed"]


@dataclass
class TaskSpec:
    id: str
    command: str
    description: str
    cwd: str
    timeout_s: int = 300
    created_at: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "TaskSpec":
        return cls(**data)


@dataclass
class TaskRuntime:
    status: TaskStatus = "created"
    started_at: float | None = None
    updated_at: float = field(default_factory=time.time)
    finished_at: float | None = None
    exit_code: int | None = None
    failure_reason: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "TaskRuntime":
        return cls(**data)


@dataclass
class TaskView:
    spec: TaskSpec
    runtime: TaskRuntime
