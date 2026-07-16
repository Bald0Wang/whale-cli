"""Tiny hook system used by the teaching harness.

Production CLI agents often support server-side and client-side hooks. Whale
CLI keeps the core idea: the loop exposes named events, and callbacks can
allow, block, or append a note without being hard-coded into the loop.
"""

from .engine import HookEngine, HookResult

__all__ = ["HookEngine", "HookResult"]
