"""第 2 章 · Rich 终端输出。

本章引入 Rich，给终端输出加颜色：
- 工具名绿色
- 参数青色
- 结果灰色
- 错误红色
- 最终回答白色
"""
from rich.console import Console

console = Console()


def print_tool_call(name: str, args: dict) -> None:
    args_str = ", ".join(
        f'{k}="{v}"' if isinstance(v, str) else f"{k}={v}"
        for k, v in args.items()
    )
    console.print(f"[green]⏺ {name}[/green]([cyan]{args_str}[/cyan])")


def print_tool_result(result: str, max_lines: int = 15) -> None:
    lines = result.splitlines()
    preview = "\n    ".join(lines[:max_lines])
    console.print(f"[dim]  ⎿ {preview}[/dim]")
    if len(lines) > max_lines:
        console.print(f"[dim]    ... ({len(lines) - max_lines} more lines)[/dim]")


def print_tool_error(error: str) -> None:
    console.print(f"[red]  ⎿ {error}[/red]")


def print_agent_answer(text: str) -> None:
    console.print(f"\n{text}")
