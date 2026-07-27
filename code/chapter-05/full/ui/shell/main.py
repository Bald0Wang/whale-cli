"""Whale CLI 交互式 Shell — 入门篇（Ch00-Ch05）版本。

启动方式：
    cd your-project
    python -m ui.shell.main

或：
    cd your-project
    python /path/to/full/ui/shell/main.py
"""

import json
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.text import Text

from llm.client import LLMClient
from soul.toolset import Toolset
from tools.file.read_tool import ReadFileTool
from tools.file.write_tool import WriteFileTool
from tools.file.edit_tool import EditTool
from tools.file.glob_tool import GlobTool
from tools.file.grep_tool import GrepTool

console = Console()


def print_banner():
    banner = r"""
 __        ___           _        ____ _     ___
 \ \      / / |__   __ _| | ___  / ___| |   |_ _|
  \ \ /\ / /| '_ \ / _` | |/ _ \| |   | |    | |
   \ V  V / | | | | (_| | |  __/| |___| |___ | |
    \_/\_/  |_| |_|\__,_|_|\___| \____|_____|___|
"""
    console.print(Text(banner, style="cyan"))
    console.print("  Whale CLI — 入门篇 (Ch00-Ch05)", style="dim")
    console.print(f"  模型: {os.getenv('LLM_MODEL', 'deepseek-v4-flash')}", style="dim")
    console.print(f"  工作目录: {os.getcwd()}", style="dim")
    console.print()


def print_tool_call(name: str, args: dict):
    args_short = json.dumps(args, ensure_ascii=False)
    if len(args_short) > 120:
        args_short = args_short[:120] + "..."
    console.print(f"  ╭─ {name}", style="bold yellow")
    console.print(f"  │  {args_short}", style="yellow")


def print_tool_result(result: str):
    lines = result.split("\n")
    shown = lines[:8]
    console.print(f"  ╰─ ", style="green", end="")
    console.print(shown[0] if shown else "(empty)", style="green")
    for line in shown[1:]:
        console.print(f"     {line}", style="dim green")
    if len(lines) > 8:
        console.print(f"     ... ({len(lines) - 8} more lines)", style="dim")


def print_tool_error(error: str):
    console.print(f"  ╰─ {error}", style="red")


def print_answer(content: str):
    console.print()
    console.print(Panel(Markdown(content), title="Whale", border_style="cyan"))


def run_turn(llm: LLMClient, toolset: Toolset, messages: list, max_steps: int = 20):
    for _ in range(max_steps):
        response = llm.chat(messages, tools=list(toolset._tools.values()))

        assistant_msg = {"role": "assistant", "content": response.content or ""}
        if response.tool_calls:
            assistant_msg["tool_calls"] = [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {"name": tc.function.name, "arguments": tc.function.arguments},
                }
                for tc in response.tool_calls
            ]
        messages.append(assistant_msg)

        if not response.tool_calls:
            print_answer(response.content or "")
            return

        for tc in response.tool_calls:
            name = tc.function.name
            args_str = tc.function.arguments
            try:
                args = json.loads(args_str)
            except json.JSONDecodeError:
                args = {}

            print_tool_call(name, args)
            result = toolset.handle(name, args_str)

            if result.get("exit_code", 0) != 0:
                output = result.get("stderr", "")
                print_tool_error(output)
            else:
                output = result.get("stdout", "")
                print_tool_result(output)

            messages.append({
                "role": "tool",
                "tool_call_id": tc.id,
                "content": output,
            })

    console.print("[dim]达到最大步数，退出本轮[/dim]")


def main():
    print_banner()

    llm = LLMClient()
    toolset = Toolset()
    toolset.register(ReadFileTool())
    toolset.register(WriteFileTool())
    toolset.register(EditTool())
    toolset.register(GlobTool())
    toolset.register(GrepTool())

    messages = [
        {
            "role": "system",
            "content": (
                "你是 Whale CLI，一个终端里的代码助手。"
                "需要文件内容时使用工具，不要猜测。"
                "不知道路径时先用 Glob 或 Grep 搜索。"
            ),
        }
    ]

    while True:
        try:
            console.print()
            user_input = console.input("[bold cyan]User>[/bold cyan] ").strip()
            if not user_input:
                continue
            if user_input.lower() in ("exit", "quit", "/exit"):
                break

            messages.append({"role": "user", "content": user_input})
            run_turn(llm, toolset, messages)

        except (KeyboardInterrupt, EOFError):
            console.print("\nBye!")
            break


if __name__ == "__main__":
    main()
