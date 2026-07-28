"""第 1 章 · 最小 Agent Loop

只有一个 read_file 工具，跑通"模型请求工具 → 本地执行 → 结果回传"的循环。

运行方式：
    export LLM_API_KEY=sk-你的key
    cd openclaw
    python ../code/chapter-01/main.py "读取 src/tools/execution.ts，告诉我这个函数做了什么"
"""
import json
import sys

from llm_client import LLMClient
from tools import TOOLS, run_tool


def run_agent(task: str, max_turns: int = 10) -> str:
    llm = LLMClient()

    messages: list[dict] = [
        {
            "role": "system",
            "content": (
                "你是一个代码助手。需要本地文件内容时使用提供的工具，"
                "不要猜测文件内容。"
            ),
        },
        {
            "role": "user",
            "content": task,
        },
    ]

    for _ in range(max_turns):
        response = llm.chat(messages, tools=TOOLS)

        # assistant 的工具请求必须先进入历史
        messages.append(response)

        tool_calls = response.get("tool_calls")
        if not tool_calls:
            return response.get("content", "")

        for call in tool_calls:
            name = call["function"]["name"]

            try:
                args = json.loads(call["function"]["arguments"])
                result = run_tool(name, args)
            except json.JSONDecodeError as exc:
                result = f"Error: invalid tool arguments: {exc}"

            print(f"⏺ {name}({args})", file=sys.stderr)

            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": call["id"],
                    "content": result,
                }
            )

    return f"Error: 达到最大轮数 {max_turns}，任务仍未完成"


if __name__ == "__main__":
    if len(sys.argv) < 2:
        raise SystemExit('用法：python main.py "你的任务"')

    answer = run_agent(sys.argv[1])
    print(answer)
