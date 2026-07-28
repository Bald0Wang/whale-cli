"""第 2 章 · 工具的统一管理

和 ch01 的差异：
- 不再用手动 tool_map 字典，改用 Toolset（register + get + all_schemas + run）
- 新增 ListDirTool
- 引入 Rich 彩色终端输出

运行方式：
    export LLM_API_KEY=sk-你的key
    cd openclaw
    python ../code/chapter-02/main.py "列出 src/tools 下的文件，读取 index.ts"
"""
import json
import sys

from llm_client import LLMClient
from registry import Toolset
from tools import ReadFileTool, ListDirTool
from rich_output import (
    print_tool_call,
    print_tool_result,
    print_tool_error,
    print_agent_answer,
)


def run_agent(task: str, max_turns: int = 10) -> None:
    llm = LLMClient()

    toolset = Toolset()
    toolset.register(ReadFileTool())
    toolset.register(ListDirTool())

    messages: list[dict] = [
        {
            "role": "system",
            "content": (
                "你是一个代码助手。需要本地文件内容时使用提供的工具，"
                "不要猜测文件内容。"
            ),
        },
        {"role": "user", "content": task},
    ]

    for _ in range(max_turns):
        response = llm.chat(messages, tools=toolset.all_schemas())
        messages.append(response)

        tool_calls = response.get("tool_calls")
        if not tool_calls:
            print_agent_answer(response.get("content", ""))
            return

        for call in tool_calls:
            name = call["function"]["name"]
            try:
                args = json.loads(call["function"]["arguments"])
            except json.JSONDecodeError:
                args = {}

            print_tool_call(name, args)
            result = toolset.run(name, args)

            if result.startswith("Error"):
                print_tool_error(result)
            else:
                print_tool_result(result)

            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": call["id"],
                    "content": result,
                }
            )

    print_tool_error(f"已到 max-turns={max_turns}，退出")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        raise SystemExit('用法：python main.py "你的任务"')
    run_agent(sys.argv[1])
