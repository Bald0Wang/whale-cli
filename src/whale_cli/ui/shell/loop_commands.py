"""Strict parsers for the shell's long-running loop commands."""
from __future__ import annotations

from dataclasses import dataclass
import re


@dataclass(frozen=True)
class GoalCommand:
    max_turns: int
    goal: str
    task_prompt: str


@dataclass(frozen=True)
class TimeCommand:
    interval_seconds: float
    max_runs: int
    task_prompt: str


@dataclass(frozen=True)
class ProactiveCommand:
    event_name: str
    max_turns: int
    goal: str
    task_prompt: str


def parse_duration(text: str) -> float:
    match = re.fullmatch(r"(\d+(?:\.\d+)?)([smh])", text.strip().lower())
    if match is None:
        raise ValueError("duration must look like 30s, 5m, or 1h")
    value = float(match.group(1))
    if value <= 0:
        raise ValueError("duration must be greater than 0")
    return value * {"s": 1, "m": 60, "h": 3600}[match.group(2)]


def parse_goal_command(raw: str) -> GoalCommand:
    header, goal, task_prompt = _split_three(raw, "/goal")
    parts = header.split()
    if len(parts) != 2:
        raise ValueError("usage: /goal <max_turns> :: <goal> :: <task>")
    return GoalCommand(max_turns=_positive_int(parts[1], "max_turns"), goal=goal, task_prompt=task_prompt)


def parse_time_command(raw: str) -> TimeCommand:
    header, task_prompt = _split_two(raw, "/loop")
    parts = header.split()
    if len(parts) != 3:
        raise ValueError("usage: /loop <interval> <max_runs> :: <task>")
    return TimeCommand(
        interval_seconds=parse_duration(parts[1]),
        max_runs=_positive_int(parts[2], "max_runs"),
        task_prompt=task_prompt,
    )


def parse_proactive_command(raw: str) -> ProactiveCommand:
    header, goal, task_prompt = _split_three(raw, "/routine")
    parts = header.split()
    if len(parts) != 3:
        raise ValueError("usage: /routine <event> <max_turns> :: <goal> :: <task>")
    return ProactiveCommand(
        event_name=parts[1],
        max_turns=_positive_int(parts[2], "max_turns"),
        goal=goal,
        task_prompt=task_prompt,
    )


def _split_two(raw: str, command: str) -> tuple[str, str]:
    pieces = [piece.strip() for piece in raw.split("::")]
    if len(pieces) != 2 or not pieces[1]:
        raise ValueError(f"usage: {command} <...> :: <task>")
    return pieces[0], pieces[1]


def _split_three(raw: str, command: str) -> tuple[str, str, str]:
    pieces = [piece.strip() for piece in raw.split("::")]
    if len(pieces) != 3 or not pieces[1] or not pieces[2]:
        raise ValueError(f"usage: {command} <...> :: <goal> :: <task>")
    return pieces[0], pieces[1], pieces[2]


def _positive_int(text: str, name: str) -> int:
    try:
        value = int(text)
    except ValueError as exc:
        raise ValueError(f"{name} must be a positive integer") from exc
    if value < 1:
        raise ValueError(f"{name} must be a positive integer")
    return value
