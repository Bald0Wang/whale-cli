---
name: whale-cli-help
description: Explain the Whale CLI project structure and where to start.
---

# Whale CLI Help

Use this skill when a user asks how Whale CLI is organized or where to begin.

Steps:

1. Start from `docs/新手入门/README.md`.
2. Read `docs/结构说明.md` for the module map.
3. Inspect `src/whale_cli/soul/soul.py` for the agent loop.
4. Inspect `src/whale_cli/soul/toolset.py` for tool dispatch.
5. Run `pytest` before changing behavior.
