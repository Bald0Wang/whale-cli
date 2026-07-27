"""动手试 01：不传 tools vs 传 tools

同一个问题发两次，观察模型行为的变化。
"""
import os
import json
from openai import OpenAI

client = OpenAI(
    api_key=os.getenv("LLM_API_KEY"),
    base_url=os.getenv("LLM_BASE_URL", "https://api.deepseek.com/v1"),
)
model = os.getenv("LLM_MODEL", "deepseek-chat")

question = "读取 src/tools/execution.ts，告诉我 formatToolExecutorRef 函数的逻辑"

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "读取当前项目中的 UTF-8 文本文件。",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "文件路径"}
                },
                "required": ["path"],
            },
        },
    }
]

messages = [{"role": "user", "content": question}]

# ── 第一次：不传 tools ──
print("=" * 60)
print("第一次请求：没有 tools")
print("=" * 60)
resp1 = client.chat.completions.create(model=model, messages=messages)
msg1 = resp1.choices[0].message
print(f"模型回答：{msg1.content[:200]}...")
print()

# ── 第二次：传 tools ──
print("=" * 60)
print("第二次请求：加上 read_file")
print("=" * 60)
resp2 = client.chat.completions.create(model=model, messages=messages, tools=TOOLS)
msg2 = resp2.choices[0].message

if msg2.tool_calls:
    for tc in msg2.tool_calls:
        print(f"模型请求工具：{tc.function.name}({tc.function.arguments})")
else:
    print(f"模型回答：{msg2.content[:200]}...")

print()
print("结论：同一句话，加不加 tools，模型的行为完全不同。")
