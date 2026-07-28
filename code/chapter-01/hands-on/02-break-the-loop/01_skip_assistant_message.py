"""动手试 2a：不保存模型的 assistant message，直接追加 tool result。

预期：API 报错——tool 消息前面没有对应的 assistant 工具请求。
"""
import os, json
from pathlib import Path
from openai import OpenAI

client = OpenAI(
    api_key=os.getenv("LLM_API_KEY"),
    base_url=os.getenv("LLM_BASE_URL", "https://api.deepseek.com/v1"),
)
model = os.getenv("LLM_MODEL", "deepseek-chat")

TOOLS = [{
    "type": "function",
    "function": {
        "name": "read_file",
        "description": "读取文件",
        "parameters": {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]},
    },
}]

messages = [{"role": "user", "content": "读取 src/tools/execution.ts"}]

# 第一次调用
resp = client.chat.completions.create(model=model, messages=messages, tools=TOOLS)
msg = resp.choices[0].message

if msg.tool_calls:
    call = msg.tool_calls[0]
    path = json.loads(call.function.arguments).get("path", "")
    content = Path(path).read_text(encoding="utf-8") if Path(path).exists() else "文件不存在"

    # ❌ 故意跳过 messages.append(response)
    # 直接加 tool result
    messages.append({
        "role": "tool",
        "tool_call_id": call.id,
        "content": content,
    })

    try:
        resp2 = client.chat.completions.create(model=model, messages=messages, tools=TOOLS)
        print("居然没报错？", resp2.choices[0].message.content[:100])
    except Exception as e:
        print(f"报错了（预期）：{e}")
        print("\n原因：tool 消息前面没有对应的 assistant 工具请求，协议不允许。")
