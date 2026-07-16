"""Data contracts shared by Whale CLI's loop modes."""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from threading import Event
from typing import Optional


class LoopMode(str, Enum):
    TURN = "turn"
    GOAL = "goal"
    TIME = "time"
    PROACTIVE = "proactive"


class LoopStatus(str, Enum):
    RUNNING = "running"
    COMPLETED = "completed"
    EXHAUSTED = "exhausted"
    CANCELLED = "cancelled"
    FAILED = "failed"


@dataclass(frozen=True)
class LoopOutcome:
    """Result returned by one ``Soul.run()`` attempt."""

    status: str
    summary: str = ""
    steps: int = 0

    @classmethod
    def completed(cls, summary: str = "", steps: int = 0) -> "LoopOutcome":
        return cls(status="completed", summary=summary, steps=steps)


@dataclass(frozen=True)
class GoalEvaluation:
    met: bool
    feedback: str = ""


@dataclass
class LoopRecord:
    loop_id: str
    mode: LoopMode
    task_prompt: str
    status: LoopStatus = LoopStatus.RUNNING
    goal: str = ""
    max_turns: int = 1
    interval_seconds: Optional[float] = None
    max_runs: Optional[int] = None
    event_name: str = ""
    run_count: int = 0
    last_outcome: Optional[LoopOutcome] = None
    last_feedback: str = ""
    cancel_event: Event = field(default_factory=Event, repr=False)
    busy: bool = field(default=False, repr=False)
