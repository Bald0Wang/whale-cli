"""Soul: the agent brain — a single ReAct loop turn.

Refactored in Phase 1:
- Tool dispatch is now delegated to :class:`Toolset` (no more if/elif chains).
- The system prompt is generated dynamically from the registered toolset,
  so new tools appear in the prompt automatically.
- OS info is injected cross-platform (no more Windows-only wording).

The message persistence / LLM-projection split (``_append_message`` vs
``_to_llm_message``) is preserved unchanged.
"""
import json
import os
import platform
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional

from ..agents import load_agent_spec, render_system_prompt
from ..background import BackgroundTaskManager
from ..context import load_agents_md
from ..hooks import HookEngine
from ..hooks import events as hook_events
from ..llm.client import LLMClient
from ..learning import LearningStore, ObsidianLearningWiki
from ..plugin import load_plugin_tools
from ..skill import discover_skills, format_skills_for_prompt
from ..tools.base import Tool
from ..tools.agent.agent_tool import AgentTool
from ..tools.background import BackgroundListTool, BackgroundOutputTool, BackgroundStartTool
from ..tools.bash.bash_tool import BashTool
from ..tools.file.write_tool import WriteFileTool
from ..tools.file.read_tool import ReadFileTool
from ..tools.file.glob_tool import GlobTool
from ..tools.file.grep_tool import GrepTool
from ..tools.file.edit_tool import EditTool
from ..tools.learning import (
    CloneLearningProjectTool,
    KnowledgeMapTool,
    LearnerProfileTool,
    LearningPortfolioTool,
    LearningProjectPlanTool,
    LearningReviewTool,
    LearningRoadmapTool,
    LearningWikiStatusTool,
    LearningWikiTool,
    OpenLearningWikiTool,
    SyncToObsidianVaultTool,
)
from ..tools.web.search_tool import SearchWebTool, FetchURLTool
from ..tools.time.getdate_tool import GetDateTool
from ..tools.todo.todo_tool import TodoWriteTool
from ..storage.session_store import SessionStore
from ..loops import LoopOutcome
from ..mcp import MCPLifecycle, load_mcp_tools_with_lifecycle
from .toolset import Toolset
from .todo_store import TodoStore
from .compaction import estimate_tokens, should_compact, compact as compact_messages
from .approval import Approval


def _default_tools(
    todo_store: TodoStore,
    llm: LLMClient,
    approval: Approval,
    background: BackgroundTaskManager,
) -> tuple[List[Tool], MCPLifecycle]:
    tools: List[Tool] = [
        # read-only
        ReadFileTool(), GlobTool(), GrepTool(),
        # mutating
        WriteFileTool(), EditTool(), BashTool(),
        # web
        SearchWebTool(), FetchURLTool(),
        # task tracking (shares the Soul's store)
        TodoWriteTool(todo_store),
        # utility
        GetDateTool(),
        # focused child context
        AgentTool(llm=llm, approval=approval),
        # vertical learning experience (all state stays in .whale_cli/learning)
        LearnerProfileTool(), KnowledgeMapTool(), LearningRoadmapTool(), LearningReviewTool(),
        LearningProjectPlanTool(), CloneLearningProjectTool(), LearningPortfolioTool(), LearningWikiStatusTool(), LearningWikiTool(), OpenLearningWikiTool(), SyncToObsidianVaultTool(),
        # slow commands
        BackgroundStartTool(background), BackgroundListTool(background), BackgroundOutputTool(background),
    ]
    tools.extend(load_plugin_tools())
    mcp_lifecycle, mcp_tools = load_mcp_tools_with_lifecycle()
    tools.extend(mcp_tools)
    return tools, mcp_lifecycle


def _shell_hint() -> str:
    """A short, platform-neutral description of the user's shell."""
    sysname = platform.system()
    if sysname == "Windows":
        return "PowerShell/CMD"
    if sysname == "Darwin":
        return "zsh/bash on macOS"
    if sysname == "Linux":
        return "bash/sh on Linux"
    return "the local shell"


class Soul:
    """The agent core. One instance per session."""

    def __init__(
        self,
        session_store: Optional[SessionStore] = None,
        session_id: Optional[str] = None,
        initial_messages: Optional[List[Dict[str, Any]]] = None,
        *,
        llm: Optional[LLMClient] = None,
        tools: Optional[List[Tool]] = None,
        max_steps: int = 15,
        approval: Optional[Approval] = None,
        hook_engine: Optional[HookEngine] = None,
        background: Optional[BackgroundTaskManager] = None,
    ):
        self.llm = llm or LLMClient()
        # TodoStore lives on the Soul so both the tool and the REPL share it.
        self.todos = TodoStore()
        # Approval gates dangerous tools (Bash/Edit/WriteFile). The toolset
        # consults this approver before calling any tool with approval_action.
        self.approval = approval or Approval()
        self.hooks = hook_engine or HookEngine()
        self.background = background or BackgroundTaskManager(workspace=os.getcwd())
        self._mcp_lifecycle = MCPLifecycle()
        if tools is not None:
            self.toolset = Toolset(tools, hook_engine=self.hooks, session_id=session_id, cwd=os.getcwd())
        else:
            default_tools, self._mcp_lifecycle = _default_tools(
                self.todos,
                self.llm,
                self.approval,
                self.background,
            )
            self.toolset = Toolset(
                default_tools,
                hook_engine=self.hooks,
                session_id=session_id,
                cwd=os.getcwd(),
            )
        self.toolset.set_approver(self.approval.as_approver())
        self.session_store = session_store
        self.session_id = session_id
        self.max_steps = max_steps
        self._conversation_wiki = ObsidianLearningWiki(LearningStore(os.getcwd()), os.getcwd())
        self._session_titled = False
        if self.session_store and self.session_id:
            info = self.session_store.get_session_info(self.session_id)
            self._session_titled = bool(info and info.title)

        os_info = f"{platform.system()} {platform.release()}"
        # Snapshot the current time once at agent startup, for the system
        # prompt. Long sessions may let this drift, but the date (the common
        # need) barely changes; for exact/second-precision needs the model
        # still has GetDate / Bash(date) for a fresh value.
        self._started_at = datetime.now().astimezone().isoformat()

        self.messages: List[Dict[str, Any]] = []
        if initial_messages:
            self.messages = initial_messages
        else:
            self._append_message({"role": "system", "content": self._build_system_prompt(os_info, self._started_at)})

    def close(self) -> None:
        """Release MCP clients owned by this agent instance.

        The REPL may replace a ``Soul`` when clearing or switching sessions.
        Closing here releases MCP transport resources without changing the
        behavior of caller-supplied tools.
        """
        self._mcp_lifecycle.close()

    # -- system prompt -----------------------------------------------------

    def _build_system_prompt(self, os_info: str, now_iso: str) -> str:
        """Generate the system prompt from the registered toolset.

        Tools describe themselves; we just enumerate them. This keeps the
        prompt in sync with the code automatically. ``now_iso`` is injected
        as a date/time reference so the model doesn't have to guess what
        "today" means.
        """
        tool_lines = []
        for tool in self.toolset:
            # schema.function.description is what the model also sees in the
            # tools array; echoing it in the system prompt reinforces usage.
            desc = ""
            fn = tool.schema.get("function", {}) if isinstance(tool.schema, dict) else {}
            desc = fn.get("description", tool.description)
            tool_lines.append(f"- {tool.name}: {desc}")

        provider_constraints = ""
        if not getattr(self.llm, "supports_tools", True):
            provider_constraints = (
                "\nProvider constraint (highest priority): the selected step-explore "
                "model uses a text-only Messages API in Whale CLI. Do not claim to call "
                "tools, read files, execute commands, create plans, or modify state. "
                "Give a direct text answer, or tell the user to switch to a tool-capable "
                "model such as step-3.7-flash for agent actions.\n"
            )

        todo_hint = ""
        if "TodoWrite" in self.toolset:
            todo_hint = (
                "Task tracking (TodoWrite):\n"
                "- For multi-step tasks (3+ steps): create a todo list up front, mark one "
                "item 'in_progress' as you start it, and 'done' when complete.\n"
                "- Don't create todos for trivial single-step requests.\n"
                "- Don't edit todos without making real progress on the work."
            )

        agents_md = load_agents_md(os.getcwd()) or "No project instructions found."
        skills = format_skills_for_prompt(discover_skills()) or "No skills found."
        try:
            spec = load_agent_spec()
            return render_system_prompt(
                spec,
                {
                    "os_info": os_info,
                    "tools": chr(10).join(tool_lines),
                    "todo_hint": todo_hint,
                    "agents_md": agents_md,
                    "skills": skills,
                    "now": now_iso,
                    "shell_hint": _shell_hint(),
                    "provider_constraints": provider_constraints,
                },
            )
        except Exception:
            return f"""You are Whale, a helpful coding agent running in the terminal on {os_info}.
You work step by step: explore first, then act, then verify. You have access to these tools:

{chr(10).join(tool_lines)}

Guidelines:
- Explore before assuming: use read/grep/glob/list tools to ground yourself in the real repo.
- When a task is multi-step, track it with the todo tool, then work each item.

{todo_hint}

Project instructions:
{agents_md}

Available skills:
{skills}

Date and time:
- The current date and time (at session start) is `{now_iso}` (ISO 8601, local timezone).

Shell: commands run via Bash in {_shell_hint()}. Prefer non-destructive commands.
{provider_constraints}
"""

    # -- message helpers (unchanged contract) ------------------------------

    @staticmethod
    def _format_tool_result(result: Any) -> str:
        if isinstance(result, dict):
            payload = {
                "stdout": result.get("stdout", ""),
                "stderr": result.get("stderr", ""),
                "exit_code": result.get("exit_code", 0),
                "changed_files": result.get("changed_files", []),
            }
            return json.dumps(payload, ensure_ascii=False)
        return str(result)

    def _append_message(self, message: Dict[str, Any]) -> None:
        if "timestamp" not in message:
            message["timestamp"] = datetime.now(timezone.utc).isoformat()
        if "metadata" not in message:
            message["metadata"] = {}

        self.messages.append(message)
        if self.session_store and self.session_id:
            if (
                not self._session_titled
                and message.get("role") == "user"
                and isinstance(message.get("content"), str)
            ):
                raw = (message.get("content") or "").strip()
                if raw:
                    one_line = " ".join(raw.split())
                    title = one_line[:60]
                    self.session_store.set_session_title(self.session_id, title=title)
                    self._session_titled = True
            self.session_store.append_message(self.session_id, message)

    def _capture_completed_turn(self, user_input: str, assistant_output: str) -> None:
        """Best-effort local Wiki capture after an explicit learner opt-in."""
        try:
            captured = self._conversation_wiki.capture_conversation_turn(
                user_message=user_input,
                assistant_message=assistant_output,
                session_id=self.session_id or "",
                model=str(getattr(self.llm, "model", "")),
            )
            if captured:
                print(f"\033[36m[Wiki captured] {captured['relative_path']}\033[0m")
        except Exception as exc:
            # A note-taking failure must not turn a completed agent turn into a failed one.
            print(f"\033[33m[Wiki capture skipped: {exc}]\033[0m")

    @staticmethod
    def _normalize_assistant_message(response_msg: Any) -> Dict[str, Any]:
        if isinstance(response_msg, dict):
            return response_msg
        if hasattr(response_msg, "model_dump"):
            try:
                return response_msg.model_dump(mode="json")
            except TypeError:
                return response_msg.model_dump()
        if hasattr(response_msg, "to_dict"):
            return response_msg.to_dict()
        return {
            "role": getattr(response_msg, "role", "assistant"),
            "content": getattr(response_msg, "content", "") or "",
        }

    @staticmethod
    def _to_llm_message(message: Dict[str, Any]) -> Dict[str, Any]:
        allowed_keys = {"role", "content", "name", "tool_call_id", "tool_calls", "function_call"}
        return {k: v for k, v in message.items() if k in allowed_keys and v is not None}

    # -- compaction --------------------------------------------------------

    def _maybe_compact(self) -> None:
        """If the conversation is too long, compact it in place.

        Uses the LLMClient's max_context_tokens (256000 for step-3.7-flash)
        and a conservative 0.85 ratio. The compact call itself hits the
        model with tools=None (pure summarization).
        """
        max_ctx = getattr(self.llm, "max_context_tokens", 0) or 0
        if max_ctx <= 0:
            return
        current = estimate_tokens(self.messages)
        if not should_compact(current, max_ctx):
            return

        before = current
        try:
            self.hooks.trigger(
                "PreCompact",
                hook_events.pre_compact(session_id=self.session_id, cwd=os.getcwd(), trigger="auto", token_count=before),
            )
            self.messages = compact_messages(self.messages, self.llm)
            after = estimate_tokens(self.messages)
            self.hooks.trigger(
                "PostCompact",
                hook_events.post_compact(
                    session_id=self.session_id,
                    cwd=os.getcwd(),
                    trigger="auto",
                    estimated_token_count=after,
                ),
            )
            print(f"\033[35m[Compacted] {before} → {after} tokens\033[0m")
        except Exception as e:
            # Never let compaction kill the run.
            print(f"\033[33m[Compaction skipped: {e}]\033[0m")

    # -- the agent loop ----------------------------------------------------

    def run(
        self,
        user_input: str,
        pause_hook: Optional[Callable[[], bool]] = None,
        *,
        multimodal_content: Optional[List[Dict[str, Any]]] = None,
        user_metadata: Optional[Dict[str, Any]] = None,
    ) -> LoopOutcome:
        """Run a single user request through the ReAct loop.

        ``pause_hook``: checked at safe points; returning True aborts the run.
        ``multimodal_content``: optional OpenAI-compatible content parts for
        this user turn. The text ``user_input`` remains the persisted record;
        image data is kept in memory for the current run only.
        ``user_metadata``: small display metadata such as attachment preview
        URLs. It is persisted with the textual user message, never as image
        base64 data.
        """
        self.hooks.trigger(
            "UserPromptSubmit",
            hook_events.user_prompt_submit(session_id=self.session_id, cwd=os.getcwd(), prompt=user_input),
        )
        user_message: Dict[str, Any] = {"role": "user", "content": user_input}
        if user_metadata:
            user_message["metadata"] = user_metadata
        self._append_message(user_message)

        step = 0
        while step < self.max_steps:
            step += 1

            if pause_hook and pause_hook():
                print("[System] Run aborted.")
                return LoopOutcome(status="aborted", summary="run aborted", steps=step)

            # Context compaction: if we're nearing the context window, compress.
            self._maybe_compact()

            print(f"\033[94m[Thinking...]\033[0m")
            try:
                llm_messages = [self._to_llm_message(m) for m in self.messages]
                if multimodal_content:
                    for message in reversed(llm_messages):
                        if message.get("role") == "user" and message.get("content") == user_input:
                            message["content"] = multimodal_content
                            break
                response_msg = self.llm.chat(llm_messages, list(self.toolset))
            except Exception as e:
                print(f"[Fatal Error] {e}")
                return LoopOutcome(status="failed", summary=str(e), steps=step)

            self._append_message(self._normalize_assistant_message(response_msg))

            tool_calls = getattr(response_msg, "tool_calls", None)
            if not tool_calls:
                # Some endpoints return tool_calls as None when content present.
                content = getattr(response_msg, "content", None)
                if content is None and isinstance(response_msg, dict):
                    content = response_msg.get("content")
                print(f"\n\033[1;37mWhale:\033[0m {content}")
                summary = str(content or "")
                self._capture_completed_turn(user_input, summary)
                return LoopOutcome.completed(summary, steps=step)

            for tool_call in tool_calls:
                if pause_hook and pause_hook():
                    print("[System] Run aborted.")
                    return LoopOutcome(status="aborted", summary="run aborted", steps=step)

                # Support both SDK objects and dicts.
                if hasattr(tool_call, "function"):
                    func_name = tool_call.function.name
                    args_str = tool_call.function.arguments
                    call_id = tool_call.id
                else:
                    func_name = tool_call["function"]["name"]
                    args_str = tool_call["function"]["arguments"]
                    call_id = tool_call.get("id")

                print(f"\033[32m[Tool Call] {func_name}({args_str})\033[0m")

                result = self.toolset.handle(func_name, args_str)

                result_str = self._format_tool_result(result)
                if len(result_str) > 1000:
                    result_str = result_str[:1000] + "... (truncated)"

                print(f"\033[90m[Tool Result] {result_str[:100]}...\033[0m")

                self._append_message({
                    "role": "tool",
                    "tool_call_id": call_id,
                    "name": func_name,
                    "content": result_str,
                })
            # loop continues: feed tool results back to the model

        print("[System] Max steps reached.")
        return LoopOutcome(status="max_steps", summary="max steps reached", steps=step)
