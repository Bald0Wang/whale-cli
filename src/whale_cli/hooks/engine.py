from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Literal

HookAction = Literal["allow", "block", "append"]
HookCallback = Callable[[Dict[str, Any]], "HookResult | None"]


@dataclass(frozen=True)
class HookResult:
    action: HookAction = "allow"
    reason: str = ""
    append: str = ""


class HookEngine:
    """Synchronous callback-based hook engine.

    It is intentionally small: no shell commands, no config loader, no async
    wire hooks. The important invariant is already here: new behavior can hang
    off events without editing the main loop.
    """

    def __init__(self) -> None:
        self._hooks: Dict[str, List[HookCallback]] = {}

    def on(self, event: str, callback: HookCallback) -> None:
        self._hooks.setdefault(event, []).append(callback)

    def has_hooks_for(self, event: str) -> bool:
        return bool(self._hooks.get(event))

    def trigger(self, event: str, payload: Dict[str, Any]) -> List[HookResult]:
        results: List[HookResult] = []
        for callback in self._hooks.get(event, []):
            try:
                result = callback(dict(payload))
            except Exception as exc:
                results.append(HookResult(action="block", reason=f"Hook failed: {exc}"))
                continue
            if result is None:
                results.append(HookResult())
            elif isinstance(result, HookResult):
                results.append(result)
            else:
                results.append(HookResult(action="block", reason=f"Invalid hook result: {result!r}"))
        return results

    @staticmethod
    def first_block(results: List[HookResult]) -> HookResult | None:
        for result in results:
            if result.action == "block":
                return result
        return None

    @staticmethod
    def appended_text(results: List[HookResult]) -> str:
        parts = [r.append or r.reason for r in results if r.action == "append" and (r.append or r.reason)]
        return "\n".join(parts)
