"""Offline behavior tests for the four loop modes."""
from __future__ import annotations

from whale_cli.hooks import HookEngine
from whale_cli.loops import GoalEvaluation, LoopManager, LoopMode, LoopOutcome, LoopStatus


def test_turn_loop_runs_one_user_triggered_attempt():
    prompts: list[str] = []
    manager = LoopManager(lambda prompt: prompts.append(prompt) or LoopOutcome.completed("answered"))

    record = manager.run_turn("inspect the repository")

    assert record.mode is LoopMode.TURN
    assert record.status is LoopStatus.COMPLETED
    assert record.run_count == 1
    assert prompts == ["inspect the repository"]


def test_goal_loop_retries_until_evaluator_accepts_result():
    prompts: list[str] = []
    outcomes = iter([LoopOutcome.completed("tests still fail"), LoopOutcome.completed("all tests pass")])
    manager = LoopManager(lambda prompt: prompts.append(prompt) or next(outcomes))

    record = manager.run_goal(
        task_prompt="fix the failing test",
        goal="all tests pass",
        max_turns=3,
        evaluator=lambda goal, outcome: GoalEvaluation(
            met=outcome.summary == goal,
            feedback="the test output still has failures",
        ),
    )

    assert record.mode is LoopMode.GOAL
    assert record.status is LoopStatus.COMPLETED
    assert record.run_count == 2
    assert "Goal: all tests pass" in prompts[0]
    assert "Evaluator feedback" in prompts[1]


def test_goal_loop_stops_at_turn_budget_when_goal_is_not_met():
    manager = LoopManager(lambda prompt: LoopOutcome.completed("not yet"))

    record = manager.run_goal(
        task_prompt="try a repair",
        goal="green build",
        max_turns=2,
        evaluator=lambda goal, outcome: GoalEvaluation(met=False, feedback="keep working"),
    )

    assert record.status is LoopStatus.EXHAUSTED
    assert record.run_count == 2


def test_time_loop_ticks_on_interval_driver_and_stops_at_run_budget():
    prompts: list[str] = []
    manager = LoopManager(lambda prompt: prompts.append(prompt) or LoopOutcome.completed("checked"))
    record = manager.create_time_loop(
        task_prompt="check the queue",
        interval_seconds=60,
        max_runs=2,
        autostart=False,
    )

    manager.tick(record.loop_id)
    manager.tick(record.loop_id)

    updated = manager.get(record.loop_id)
    assert updated is not None
    assert updated.mode is LoopMode.TIME
    assert updated.status is LoopStatus.COMPLETED
    assert updated.run_count == 2
    assert prompts == ["check the queue", "check the queue"]


def test_proactive_loop_runs_when_registered_hook_event_arrives():
    hooks = HookEngine()
    prompts: list[str] = []
    manager = LoopManager(lambda prompt: prompts.append(prompt) or LoopOutcome.completed("recovered"))
    record = manager.register_proactive(
        hooks,
        event_name="PostToolUseFailure",
        task_prompt="inspect the failed tool call and propose a recovery",
        goal="recovery proposed",
        max_turns=1,
        evaluator=lambda goal, outcome: GoalEvaluation(met=True),
        background=False,
    )

    hooks.trigger("PostToolUseFailure", {"tool_name": "Bash", "error": "exit 1"})

    updated = manager.get(record.loop_id)
    assert updated is not None
    assert updated.mode is LoopMode.PROACTIVE
    assert updated.run_count == 1
    assert updated.status is LoopStatus.RUNNING
    assert "PostToolUseFailure" in prompts[0]


def test_proactive_loop_stays_active_after_one_failed_event_attempt():
    hooks = HookEngine()
    manager = LoopManager(lambda prompt: LoopOutcome(status="failed", summary="model unavailable"))
    record = manager.register_proactive(
        hooks,
        event_name="PostToolUseFailure",
        task_prompt="inspect the failed tool call",
        goal="recovery proposed",
        max_turns=1,
        evaluator=lambda goal, outcome: GoalEvaluation(met=False),
        background=False,
    )

    hooks.trigger("PostToolUseFailure", {"tool_name": "Bash"})

    updated = manager.get(record.loop_id)
    assert updated is not None
    assert updated.status is LoopStatus.RUNNING
    assert updated.last_feedback == "model unavailable"


def test_cancel_marks_active_time_loop_as_cancelled():
    manager = LoopManager(lambda prompt: LoopOutcome.completed("checked"))
    record = manager.create_time_loop("check", interval_seconds=60, autostart=False)

    assert manager.cancel(record.loop_id) is True

    updated = manager.get(record.loop_id)
    assert updated is not None
    assert updated.status is LoopStatus.CANCELLED
