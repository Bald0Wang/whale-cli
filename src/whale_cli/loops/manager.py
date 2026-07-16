"""Four small, explicit loop primitives for the Whale CLI runtime."""
from __future__ import annotations

import json
import threading
import uuid
from typing import Any, Callable, Dict, List, Optional

from ..hooks import HookEngine, HookResult
from .models import GoalEvaluation, LoopMode, LoopOutcome, LoopRecord, LoopStatus

Runner = Callable[[str], LoopOutcome]
GoalEvaluator = Callable[[str, LoopOutcome], GoalEvaluation]


class LoopManager:
    """Own turn, goal, time and proactive loop lifecycles.

    The manager deliberately knows nothing about LLM providers. A caller injects
    one runner for an agent attempt and, for goal loops, one evaluator for the
    completion condition. That keeps the lifecycle deterministic in tests and
    lets the shell decide how to run or evaluate a real model.
    """

    def __init__(self, runner: Runner):
        self._runner = runner
        self._records: Dict[str, LoopRecord] = {}
        self._lock = threading.RLock()
        self._run_lock = threading.RLock()

    def run_turn(self, task_prompt: str) -> LoopRecord:
        record = self._new_record(LoopMode.TURN, task_prompt)
        outcome = self._run_once(record, task_prompt)
        record.status = LoopStatus.COMPLETED if outcome.status == "completed" else LoopStatus.FAILED
        return record

    def run_goal(
        self,
        *,
        task_prompt: str,
        goal: str,
        max_turns: int,
        evaluator: GoalEvaluator,
    ) -> LoopRecord:
        if max_turns < 1:
            raise ValueError("max_turns must be at least 1")
        record = self._new_record(LoopMode.GOAL, task_prompt, goal=goal, max_turns=max_turns)
        self._run_goal_attempts(record, evaluator, keep_active=False)
        return record

    def create_time_loop(
        self,
        task_prompt: str,
        *,
        interval_seconds: float,
        max_runs: Optional[int] = None,
        autostart: bool = True,
    ) -> LoopRecord:
        if interval_seconds <= 0:
            raise ValueError("interval_seconds must be greater than 0")
        if max_runs is not None and max_runs < 1:
            raise ValueError("max_runs must be at least 1 when provided")
        record = self._new_record(
            LoopMode.TIME,
            task_prompt,
            interval_seconds=interval_seconds,
            max_runs=max_runs,
        )
        if autostart:
            thread = threading.Thread(target=self._time_worker, args=(record.loop_id,), name=f"whale-loop-{record.loop_id}", daemon=True)
            thread.start()
        return record

    def tick(self, loop_id: str) -> Optional[LoopRecord]:
        record = self.get(loop_id)
        if record is None or record.mode is not LoopMode.TIME or record.status is not LoopStatus.RUNNING:
            return record
        if record.max_runs is not None and record.run_count >= record.max_runs:
            record.status = LoopStatus.COMPLETED
            return record

        self._run_once(record, record.task_prompt)
        if record.max_runs is not None and record.run_count >= record.max_runs:
            record.status = LoopStatus.COMPLETED
        return record

    def register_proactive(
        self,
        hooks: HookEngine,
        *,
        event_name: str,
        task_prompt: str,
        goal: str,
        max_turns: int,
        evaluator: GoalEvaluator,
        background: bool = True,
    ) -> LoopRecord:
        if max_turns < 1:
            raise ValueError("max_turns must be at least 1")
        record = self._new_record(
            LoopMode.PROACTIVE,
            task_prompt,
            goal=goal,
            max_turns=max_turns,
            event_name=event_name,
        )

        def _on_event(payload: Dict[str, Any]) -> HookResult:
            self.trigger_proactive(record.loop_id, payload, evaluator=evaluator, background=background)
            return HookResult()

        hooks.on(event_name, _on_event)
        return record

    def trigger_proactive(
        self,
        loop_id: str,
        payload: Dict[str, Any],
        *,
        evaluator: GoalEvaluator,
        background: bool = True,
    ) -> Optional[LoopRecord]:
        record = self.get(loop_id)
        if record is None or record.mode is not LoopMode.PROACTIVE or record.status is not LoopStatus.RUNNING:
            return record
        with self._lock:
            if record.busy:
                return record
            record.busy = True

        def _run() -> None:
            try:
                payload_text = json.dumps(payload, ensure_ascii=False, default=str)
                event_prompt = (
                    f"{record.task_prompt}\n\nTriggered by event: {record.event_name}\n"
                    f"Event payload: {payload_text}"
                )
                self._run_goal_attempts(record, evaluator, keep_active=True, task_prompt=event_prompt)
            finally:
                with self._lock:
                    record.busy = False

        if background:
            thread = threading.Thread(target=_run, name=f"whale-proactive-{record.loop_id}", daemon=True)
            thread.start()
        else:
            _run()
        return record

    def cancel(self, loop_id: str) -> bool:
        record = self.get(loop_id)
        if record is None or record.status is not LoopStatus.RUNNING:
            return False
        record.cancel_event.set()
        record.status = LoopStatus.CANCELLED
        return True

    def get(self, loop_id: str) -> Optional[LoopRecord]:
        with self._lock:
            return self._records.get(loop_id)

    def list_active(self) -> List[LoopRecord]:
        with self._lock:
            return [record for record in self._records.values() if record.status is LoopStatus.RUNNING]

    def _new_record(self, mode: LoopMode, task_prompt: str, **kwargs: Any) -> LoopRecord:
        record = LoopRecord(loop_id=uuid.uuid4().hex[:8], mode=mode, task_prompt=task_prompt, **kwargs)
        with self._lock:
            self._records[record.loop_id] = record
        return record

    def _run_once(self, record: LoopRecord, prompt: str) -> LoopOutcome:
        if record.cancel_event.is_set():
            record.status = LoopStatus.CANCELLED
            return LoopOutcome(status="cancelled", summary="loop cancelled", steps=0)
        try:
            with self._run_lock:
                outcome = self._runner(prompt)
        except Exception as exc:
            outcome = LoopOutcome(status="failed", summary=str(exc), steps=0)
        record.run_count += 1
        record.last_outcome = outcome
        return outcome

    def _run_goal_attempts(
        self,
        record: LoopRecord,
        evaluator: GoalEvaluator,
        *,
        keep_active: bool,
        task_prompt: Optional[str] = None,
    ) -> None:
        feedback = ""
        for _ in range(record.max_turns):
            if record.cancel_event.is_set():
                record.status = LoopStatus.CANCELLED
                return
            prompt = self._goal_prompt(record, feedback, task_prompt=task_prompt)
            outcome = self._run_once(record, prompt)
            if outcome.status != "completed":
                record.last_feedback = outcome.summary or outcome.status
                record.status = LoopStatus.RUNNING if keep_active else LoopStatus.FAILED
                return
            evaluation = evaluator(record.goal, outcome)
            record.last_feedback = evaluation.feedback
            if evaluation.met:
                record.status = LoopStatus.RUNNING if keep_active else LoopStatus.COMPLETED
                return
            feedback = evaluation.feedback or "Goal is not met yet. Continue with a concrete verification step."

        record.status = LoopStatus.RUNNING if keep_active else LoopStatus.EXHAUSTED

    def _goal_prompt(self, record: LoopRecord, feedback: str, *, task_prompt: Optional[str] = None) -> str:
        prompt = f"Goal: {record.goal}\nTask: {task_prompt or record.task_prompt}"
        if feedback:
            prompt += f"\nEvaluator feedback: {feedback}\nContinue the task and verify the goal."
        return prompt

    def _time_worker(self, loop_id: str) -> None:
        while True:
            record = self.get(loop_id)
            if record is None or record.status is not LoopStatus.RUNNING:
                return
            if record.cancel_event.wait(record.interval_seconds or 0):
                return
            self.tick(loop_id)
