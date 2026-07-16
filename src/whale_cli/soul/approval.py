"""Approval layer — gate dangerous tool calls behind user confirmation.

Approval design, simplified for teaching:
- Three responses: approve / approve_for_session / reject.
- ``approve_for_session`` adds the action to ``auto_approve_actions`` so the
  same action never asks again this session.
- Action matching is by *action label string* (e.g. "run command", "edit file"),
  NOT by command regex, which keeps the policy surface easy to explain.
- The ``request`` call is synchronous and blocking (uses input()), because
  this teaching CLI is single-threaded. The Toolset's approver hook calls this.

A ``yolo`` mode short-circuits every request to approved. ``/yolo`` and
``/safe`` in the REPL toggle it.
"""
from __future__ import annotations

import threading
from typing import Callable, Optional, Set

# The approver signature expected by Toolset.set_approver.
Approver = Callable[[str, str], bool]


class Approval:
    """Holds approval state for one session and answers requests.

    Parameters
    ----------
    prompt_fn:
        A callable that displays a yes/no prompt and returns one of
        "approve" / "approve_for_session" / "reject". Defaults to a stdin-based
        prompt; tests inject a scripted one.
    yolo:
        If True, every request is auto-approved (no prompt).
    """

    def __init__(
        self,
        prompt_fn: Optional[Callable[[str, str], str]] = None,
        yolo: bool = False,
    ):
        self._prompt_fn = prompt_fn or _default_prompt
        self._yolo = yolo
        self._auto_approve_actions: Set[str] = set()

    # -- state toggles -----------------------------------------------------

    def set_yolo(self, on: bool) -> None:
        self._yolo = on

    @property
    def is_yolo(self) -> bool:
        return self._yolo

    @property
    def auto_approve_actions(self) -> Set[str]:
        return set(self._auto_approve_actions)

    # -- the gate ----------------------------------------------------------

    def request(self, action: str, description: str) -> bool:
        """Return True if the action may proceed, False if rejected."""
        if self._yolo:
            return True
        if threading.current_thread() is not threading.main_thread():
            # Timed and event-driven loops cannot safely compete with the REPL
            # for stdin. Explicit /yolo is required for unattended actions.
            return False
        if action in self._auto_approve_actions:
            return True
        response = self._prompt_fn(action, description)
        if response == "approve":
            return True
        if response == "approve_for_session":
            self._auto_approve_actions.add(action)
            return True
        return False  # reject or anything unknown

    # -- Toolset-compatible wrapper ---------------------------------------

    def as_approver(self) -> Approver:
        """Return a callable matching Toolset's approver signature."""
        def _approver(action: str, description: str) -> bool:
            return self.request(action, description)
        return _approver


def _default_prompt(action: str, description: str) -> str:
    """The default interactive prompt. Reads one line from stdin."""
    print(f"\n\033[33m[Approval needed] action={action}\033[0m")
    print(f"  {description}")
    print("  Options: [y]es this time, [a]lways for this session, [n]o")
    try:
        answer = input("Approve? (y/a/n): ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        return "reject"
    if answer in ("y", "yes"):
        return "approve"
    if answer in ("a", "always"):
        return "approve_for_session"
    return "reject"
