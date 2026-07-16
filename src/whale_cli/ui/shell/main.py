import sys
import os
from pathlib import Path
from typing import Optional

# 确保能导入 whale_cli 包
# 在实际项目中，这通常通过安装包或设置 PYTHONPATH 来解决
# 这里为了简单，我们动态添加 src 目录到 sys.path
current_dir = os.path.dirname(os.path.abspath(__file__))
# current: src/whale_cli/ui/shell
# need: src
src_dir = os.path.dirname(os.path.dirname(os.path.dirname(current_dir)))
sys.path.insert(0, src_dir)

from whale_cli.soul.soul import Soul
from whale_cli.learning import LearningStore, ReviewScheduler
from whale_cli.storage.session_store import SessionStore
from whale_cli.loops import GoalEvaluation, LoopManager
from whale_cli.runtime import resolve_runtime_paths
from whale_cli.ui.shell.loop_commands import parse_goal_command, parse_proactive_command, parse_time_command

import threading
import time

try:
    import msvcrt  # Windows-only, used for ESC-to-exit key handling
except Exception:
    msvcrt = None

_TOP_LEVEL_COMMANDS: dict[str, str] = {
    "/help": "Show help",
    "/exit": "Exit",
    "/clear": "Start a new session (keeps history on disk)",
    "/session": "Show current session + recent sessions",
    "/todo": "Show the agent's current task list (read-only)",
    "/yolo": "Auto-approve ALL tool calls (skip prompts)",
    "/safe": "Re-enable approval prompts for dangerous tools",
    "/goal": "Run until a checked goal is met or the turn budget ends",
    "/loop": "Create or cancel a time-based loop",
    "/loops": "Show active time and proactive loops",
    "/routine": "Run a goal loop when a hook event arrives",
}

_SESSION_SUBCOMMANDS: dict[str, str] = {
    "load": "Load a specific session: /session load <id>",
    "delete": "Delete a saved session: /session delete <id>",
}

def _print_banner():
    banner = r"""
 __        ___           _        ____ _     ___
 \ \      / / |__   __ _| | ___  / ___| |   |_ _|
  \ \ /\ / /| '_ \ / _` | |/ _ \| |   | |    | |
   \ V  V / | | | | (_| | |  __/| |___| |___ | |
    \_/\_/  |_| |_|\__,_|_|\___| \____|_____|___|

Whale CLI — your terminal coding sidekick
"""
    print(banner.rstrip("\n"))

def _print_suggestions(title: str, options: list[str]) -> None:
    if not options:
        return
    print(f"\n{title}")
    for opt in options:
        print(f"  {opt}")

def _suggest_for_buffer(buf: str) -> list[str]:
    """
    Return a list of suggested completions given the current input buffer.
    Suggestions are meant to be displayed to the user (not necessarily full expansions).
    """
    raw = buf.strip()
    if not raw.startswith("/"):
        return []

    # Split into command + optional args
    parts = raw.split()
    cmd = parts[0]

    if len(parts) == 1:
        # Suggest top-level commands based on prefix.
        return [c for c in _TOP_LEVEL_COMMANDS.keys() if c.startswith(cmd)]

    # Subcommand suggestions
    if cmd == "/session":
        sub_prefix = parts[1]
        return [s for s in _SESSION_SUBCOMMANDS.keys() if s.startswith(sub_prefix)]

    return []

def _apply_autocomplete(buf: str) -> str:
    """
    Apply autocomplete behavior:
    - If there is exactly one completion, expand the buffer.
    - If multiple completions, print suggestions and keep buffer unchanged.
    """
    raw = buf
    suggestions = _suggest_for_buffer(raw)
    if not suggestions:
        return raw

    stripped = raw.rstrip("\n")
    parts = stripped.split()

    if len(suggestions) == 1:
        completion = suggestions[0]
        if len(parts) <= 1:
            # Replace the command token.
            return completion + " "
        # Subcommand completion (only for /session currently)
        if parts[0] == "/session":
            return f"/session {completion} "
        return raw

    # Multiple suggestions: show them.
    if raw.strip().startswith("/session ") and len(parts) >= 2:
        _print_suggestions("[Suggestions] /session subcommands:", suggestions)
    else:
        _print_suggestions("[Suggestions] Commands:", suggestions)
    return raw

def _pause_ui() -> None:
    """
    Pause the CLI and wait for user input.

    Notes:
    - Press Enter to resume.
    - Type 'abort' to stop the current agent run and return to the prompt.
    - Type 'exit' to exit the CLI.
    """
    print("\n[Paused] Press Enter to continue. Type 'abort' to stop current run. Type 'exit' to quit.")

def _handle_pause_interaction() -> str:
    _pause_ui()
    text = input("Paused> ").strip().lower()
    if text == "exit":
        raise KeyboardInterrupt
    if text == "abort":
        return "abort"
    return "resume"

def _run_with_esc_pause(agent: Soul, user_input: str):
    """
    Run the agent with an ESC-triggered pause mechanism.

    Limitations:
    - ESC won't interrupt an in-flight LLM request or a running subprocess.
      It will pause at the next safe checkpoint inside the agent loop.
    """
    if msvcrt is None:
        return agent.run(user_input)

    pause_event = threading.Event()
    stop_event = threading.Event()

    def _watch_esc():
        while not stop_event.is_set():
            try:
                if msvcrt.kbhit():
                    ch = msvcrt.getwch()
                    # ESC
                    if ch == "\x1b":
                        pause_event.set()
                        continue
                    # Arrow/function keys: skip the second code.
                    if ch in ("\x00", "\xe0"):
                        _ = msvcrt.getwch()
                        continue
            except Exception:
                # Best-effort; don't crash the main run.
                pass
            time.sleep(0.05)

    watcher = threading.Thread(target=_watch_esc, name="whale-cli-esc-watcher", daemon=True)
    watcher.start()

    def _pause_hook() -> bool:
        if not pause_event.is_set():
            return False
        pause_event.clear()
        action = _handle_pause_interaction()
        if action == "abort":
            return True
        return False

    try:
        return agent.run(user_input, pause_hook=_pause_hook)
    finally:
        stop_event.set()
        try:
            watcher.join(timeout=0.2)
        except Exception:
            pass

def _read_line(prompt: str) -> Optional[str]:
    """
    Read a line of input.

    - On Windows, supports pressing ESC to exit immediately.
    - Returns None when ESC is pressed.
    """
    if msvcrt is None:
        # Fallback: no ESC handling, but keeps the CLI usable on non-Windows.
        return input(prompt)

    sys.stdout.write(prompt)
    sys.stdout.flush()

    buf: list[str] = []
    while True:
        ch = msvcrt.getwch()

        # ESC: pause menu (doesn't exit)
        if ch == "\x1b":
            sys.stdout.write("\n")
            sys.stdout.flush()
            return "__PAUSE__"

        # Enter
        if ch in ("\r", "\n"):
            sys.stdout.write("\n")
            sys.stdout.flush()
            return "".join(buf)

        # Ctrl+C
        if ch == "\x03":
            raise KeyboardInterrupt

        # Backspace
        if ch == "\b":
            if buf:
                buf.pop()
                # Erase last char from console.
                sys.stdout.write("\b \b")
                sys.stdout.flush()
            continue

        # Tab: autocomplete for slash commands.
        if ch == "\t":
            current = "".join(buf)
            new_value = _apply_autocomplete(current)
            if new_value != current:
                # Replace entire current line content.
                # Clear current input: backspace the whole buffer.
                for _ in range(len(buf)):
                    sys.stdout.write("\b \b")
                sys.stdout.flush()

                buf = list(new_value)
                sys.stdout.write("".join(buf))
                sys.stdout.flush()
            else:
                # If we printed suggestions, we must redraw prompt + current buffer.
                # Heuristic: suggestions printing starts with a newline.
                # Re-print prompt and buffer so the input line remains visible.
                sys.stdout.write(prompt)
                sys.stdout.write("".join(buf))
                sys.stdout.flush()
            continue

        # Arrow/function keys: msvcrt emits a prefix then a second code.
        if ch in ("\x00", "\xe0"):
            _ = msvcrt.getwch()
            continue

        # Ignore other control chars.
        if ord(ch) < 32:
            continue

        buf.append(ch)
        sys.stdout.write(ch)
        sys.stdout.flush()

def _print_help():
    print(
        "\nCommands:\n"
        "  /help                Show this help\n"
        "  /exit                Exit\n"
        "  (ESC)                Pause (during agent run) and wait for input\n"
        "  (TAB)                Autocomplete / show command suggestions\n"
        "  /clear               Start a new session (keeps history on disk)\n"
        "  /session             Show current session + recent sessions\n"
        "  /session load <id>   Load a specific session\n"
        "  /todo                Show the agent's current task list\n"
        "  /yolo                Auto-approve ALL tool calls (no prompts)\n"
        "  /safe                Re-enable approval prompts for dangerous tools\n"
        "  /goal N :: goal :: task\n"
        "                       Repeat a task until an evaluator accepts it or N turns end\n"
        "  /loop 5m N :: task   Run a task every interval, at most N times\n"
        "  /loop cancel <id>    Cancel a time or proactive loop\n"
        "  /loops               Show active time and proactive loops\n"
        "  /routine EVENT N :: goal :: task\n"
        "                       Run a goal loop when EVENT arrives (for example PostToolUseFailure)\n"
        "                       Background loops reject dangerous tools unless /yolo is enabled\n"
    )


def _get_store() -> SessionStore:
    return SessionStore(base_dir=str(resolve_runtime_paths().home))


def _refresh_learning_reviews_in_background(store: SessionStore) -> None:
    """Update today's local review files without holding up the terminal REPL."""
    def refresh() -> None:
        try:
            ReviewScheduler(LearningStore(Path.cwd())).sync_from_conversations(session_store=store, force=False)
        except (OSError, ValueError):
            return

    threading.Thread(target=refresh, name="whale-review-refresh", daemon=True).start()


def _start_new_session(store: SessionStore) -> tuple[Soul, str]:
    session_id = store.create_session(title="")
    agent = Soul(session_store=store, session_id=session_id)
    return agent, session_id


def _restore_latest_session(store: SessionStore) -> tuple[Optional[Soul], Optional[str]]:
    session_id = store.get_latest_session_id()
    if not session_id:
        return None, None
    messages = store.load_messages(session_id=session_id)
    if not messages:
        return None, None
    agent = Soul(session_store=store, session_id=session_id, initial_messages=messages)
    return agent, session_id


def _evaluate_goal(agent: Soul, goal: str, outcome) -> GoalEvaluation:
    """Use a tool-free model turn to evaluate a goal after one agent attempt."""
    if outcome.status != "completed":
        return GoalEvaluation(met=False, feedback=outcome.summary or outcome.status)
    try:
        response = agent.llm.chat(
            [
                {
                    "role": "system",
                    "content": "You are a strict goal evaluator. Reply with PASS or CONTINUE, then one short reason.",
                },
                {
                    "role": "user",
                    "content": f"Goal:\n{goal}\n\nAgent result:\n{outcome.summary}\n\nDid the result meet the goal?",
                },
            ],
            tools=None,
            temperature=0,
        )
    except Exception as exc:
        return GoalEvaluation(met=False, feedback=f"goal evaluator failed: {exc}")

    content = getattr(response, "content", "") or ""
    if isinstance(response, dict):
        content = response.get("content", content) or ""
    text = str(content).strip()
    return GoalEvaluation(met=text.upper().startswith("PASS"), feedback=text or "evaluator returned no text")


def _print_active_loops(loop_manager: LoopManager) -> None:
    records = loop_manager.list_active()
    if not records:
        print("[Loops] No active time or proactive loops.")
        return
    print("[Loops] Active:")
    for record in records:
        detail = ""
        if record.mode.value == "time":
            detail = f" every {record.interval_seconds:g}s, max_runs={record.max_runs}"
        elif record.mode.value == "proactive":
            detail = f" event={record.event_name}, goal={record.goal!r}"
        print(f"  {record.loop_id}  {record.mode.value}{detail}  runs={record.run_count}")


def main():
    paths = resolve_runtime_paths()
    paths.ensure_writable_directories()
    if os.environ.get("WHALE_WORKSPACE"):
        os.chdir(paths.workspace)
    _print_banner()
    print("Type '/help' for commands. Type 'exit' or 'quit' to leave.\n")

    store = _get_store()
    _refresh_learning_reviews_in_background(store)
    agent, session_id = _restore_latest_session(store)
    if agent and session_id:
        print(f"[Session] Restored: {session_id} ({len(agent.messages)} messages)")
    else:
        agent, session_id = _start_new_session(store)
        print(f"[Session] New: {session_id}")

    def _loop_runner(prompt: str):
        if threading.current_thread() is threading.main_thread():
            return _run_with_esc_pause(agent, prompt)
        return agent.run(prompt)

    loop_manager = LoopManager(_loop_runner)

    def _cancel_active_loops() -> None:
        for record in loop_manager.list_active():
            loop_manager.cancel(record.loop_id)

    while True:
        try:
            user_input = _read_line("\n\033[1;36mUser>\033[0m ")
            if user_input == "__PAUSE__":
                _handle_pause_interaction()
                continue
            if user_input.lower() in ["exit", "quit"]:
                _cancel_active_loops()
                agent.close()
                break
            if not user_input.strip():
                continue

            if user_input.startswith("/"):
                parts = user_input.strip().split()
                cmd = parts[0].lower()

                if cmd in ["/help", "/?"]:
                    _print_help()
                    continue

                if cmd == "/exit":
                    _cancel_active_loops()
                    agent.close()
                    break

                if cmd == "/clear":
                    _cancel_active_loops()
                    agent.close()
                    agent, session_id = _start_new_session(store)
                    print(f"[Session] New: {session_id}")
                    continue

                if cmd == "/todo":
                    todos = getattr(agent, "todos", None)
                    if todos is None:
                        print("[Todo] No task list available on this agent.")
                    else:
                        print(f"[Todo]\n{todos.render()}")
                    continue

                if cmd == "/yolo":
                    approval = getattr(agent, "approval", None)
                    if approval is None:
                        print("[Approval] Not available on this agent.")
                    else:
                        approval.set_yolo(True)
                        print("[Approval] YOLO mode ON — all tool calls auto-approved.")
                    continue

                if cmd == "/safe":
                    approval = getattr(agent, "approval", None)
                    if approval is None:
                        print("[Approval] Not available on this agent.")
                    else:
                        approval.set_yolo(False)
                        print("[Approval] Safe mode ON — dangerous tools will prompt.")
                    continue

                if cmd == "/goal":
                    try:
                        spec = parse_goal_command(user_input.strip())
                        record = loop_manager.run_goal(
                            task_prompt=spec.task_prompt,
                            goal=spec.goal,
                            max_turns=spec.max_turns,
                            evaluator=lambda goal, outcome: _evaluate_goal(agent, goal, outcome),
                        )
                        print(
                            f"[Goal] {record.status.value}: turns={record.run_count}/{record.max_turns} "
                            f"feedback={record.last_feedback or '(none)'}"
                        )
                    except ValueError as exc:
                        print(f"[Goal] {exc}")
                    continue

                if cmd == "/loop":
                    if len(parts) == 3 and parts[1].lower() == "cancel":
                        cancelled = loop_manager.cancel(parts[2])
                        print("[Loop] Cancelled." if cancelled else "[Loop] Not found or already stopped.")
                        continue
                    try:
                        spec = parse_time_command(user_input.strip())
                        record = loop_manager.create_time_loop(
                            spec.task_prompt,
                            interval_seconds=spec.interval_seconds,
                            max_runs=spec.max_runs,
                        )
                        print(
                            f"[Loop] Started {record.loop_id}: every {record.interval_seconds:g}s, "
                            f"max_runs={record.max_runs}. Use /loop cancel {record.loop_id} to stop it."
                        )
                    except ValueError as exc:
                        print(f"[Loop] {exc}")
                    continue

                if cmd == "/loops":
                    _print_active_loops(loop_manager)
                    continue

                if cmd == "/routine":
                    try:
                        spec = parse_proactive_command(user_input.strip())
                        record = loop_manager.register_proactive(
                            agent.hooks,
                            event_name=spec.event_name,
                            task_prompt=spec.task_prompt,
                            goal=spec.goal,
                            max_turns=spec.max_turns,
                            evaluator=lambda goal, outcome: _evaluate_goal(agent, goal, outcome),
                        )
                        print(
                            f"[Routine] Started {record.loop_id}: event={record.event_name}, "
                            f"max_turns={record.max_turns}. Use /loop cancel {record.loop_id} to stop it."
                        )
                    except ValueError as exc:
                        print(f"[Routine] {exc}")
                    continue

                if cmd == "/session":
                    if len(parts) == 1:
                        # Helpful hint for discovery.
                        _print_suggestions(
                            "[Suggestions] /session subcommands:",
                            [f"{k}  # {_SESSION_SUBCOMMANDS[k]}" for k in _SESSION_SUBCOMMANDS.keys()],
                        )

                    if len(parts) >= 3 and parts[1].lower() == "delete":
                        target_id = parts[2].strip()
                        try:
                            deleted = store.delete_session(target_id)
                        except ValueError:
                            print("[Session] Invalid session id.")
                            continue
                        if not deleted:
                            print(f"[Session] Not found: {target_id}")
                            continue
                        print(f"[Session] Deleted: {target_id}")
                        if target_id == session_id:
                            _cancel_active_loops()
                            agent.close()
                            agent, session_id = _start_new_session(store)
                            print(f"[Session] New: {session_id}")
                        continue

                    if len(parts) >= 3 and parts[1].lower() == "load":
                        target_id = parts[2].strip()
                        messages = store.load_messages(session_id=target_id)
                        if not messages:
                            print(f"[Session] Not found or empty: {target_id}")
                            continue
                        _cancel_active_loops()
                        agent.close()
                        agent = Soul(session_store=store, session_id=target_id, initial_messages=messages)
                        session_id = target_id
                        print(f"[Session] Loaded: {session_id} ({len(agent.messages)} messages)")
                        continue

                    print(f"[Session] Current: {session_id} ({len(agent.messages)} messages)")
                    recent = store.list_sessions(limit=5)
                    if recent:
                        print("[Session] Recent:")
                        for s in recent:
                            title = f" - {s.title}" if s.title else ""
                            print(f"  {s.session_id}{title}  updated={s.updated_at}")
                    continue

                # Unknown command: show suggestions based on prefix (e.g. /s -> /session)
                suggestions = _suggest_for_buffer(user_input.strip())
                if suggestions:
                    _print_suggestions("[Suggestions] Commands:", suggestions)
                print(f"[Unknown Command] {user_input.strip()} (try /help)")
                continue
                
            loop_manager.run_turn(user_input)
            
        except KeyboardInterrupt:
            print("\nGoodbye!")
            _cancel_active_loops()
            agent.close()
            break
        except Exception as e:
            print(f"Error: {e}")

if __name__ == "__main__":
    main()
