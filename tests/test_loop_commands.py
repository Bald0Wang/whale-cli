from __future__ import annotations

import pytest

from whale_cli.ui.shell.loop_commands import (
    parse_duration,
    parse_goal_command,
    parse_proactive_command,
    parse_time_command,
)


def test_parse_goal_command_uses_turn_budget_goal_and_task():
    command = parse_goal_command("/goal 3 :: all tests pass :: fix the failing test")

    assert command.max_turns == 3
    assert command.goal == "all tests pass"
    assert command.task_prompt == "fix the failing test"


def test_parse_time_command_accepts_minutes_and_run_budget():
    command = parse_time_command("/loop 5m 4 :: check the review queue")

    assert command.interval_seconds == 300
    assert command.max_runs == 4
    assert command.task_prompt == "check the review queue"


def test_parse_proactive_command_binds_event_goal_and_task():
    command = parse_proactive_command(
        "/routine PostToolUseFailure 2 :: recovery proposed :: inspect the failed command"
    )

    assert command.event_name == "PostToolUseFailure"
    assert command.max_turns == 2
    assert command.goal == "recovery proposed"
    assert command.task_prompt == "inspect the failed command"


@pytest.mark.parametrize(
    ("text", "seconds"),
    [("30s", 30), ("5m", 300), ("1h", 3600)],
)
def test_parse_duration_supports_seconds_minutes_and_hours(text, seconds):
    assert parse_duration(text) == seconds


def test_parse_duration_rejects_missing_unit():
    with pytest.raises(ValueError, match="30s"):
        parse_duration("30")
