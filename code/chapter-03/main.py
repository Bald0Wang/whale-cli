"""第 3 章 · 读文件：Read

和 ch02 的差异：ReadFileTool 升级为完整版（行范围、行号、二进制检测、长行截断）。
工具返回值从 str 改为 dict（ok/err），main 通过 exit_code 判断成败。

运行方式：
    export LLM_API_KEY=sk-你的key
    cd openclaw
    python ../code/chapter-03/main.py "读取 src/system-agent/setup-inference.ts 的前 200 行"
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
                "不要猜测文件内容。读取大文件时应优先分段读取。"
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
            tool_result = toolset.run(name, args)

            if tool_result.get("exit_code", 0) != 0:
                result = tool_result.get("stderr", "")
                print_tool_error(result)
            else:
                result = tool_result.get("stdout", "")
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
