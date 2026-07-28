"""动手试 2b：tool result 不带 tool_call_id。

预期：API 报错——tool 消息必须带 tool_call_id 才能和请求配对。
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

resp = client.chat.completions.create(model=model, messages=messages, tools=TOOLS)
msg = resp.choices[0].message

if msg.tool_calls:
    call = msg.tool_calls[0]
    path = json.loads(call.function.arguments).get("path", "")
    content = Path(path).read_text(encoding="utf-8") if Path(path).exists() else "文件不存在"

    # 正确保存 assistant message
    messages.append(msg.model_dump(exclude_none=True))

    # ❌ 故意不带 tool_call_id
    messages.append({
        "role": "tool",
        "content": content,
    })

    try:
        resp2 = client.chat.completions.create(model=model, messages=messages, tools=TOOLS)
        print("居然没报错？", resp2.choices[0].message.content[:100])
    except Exception as e:
        print(f"报错了（预期）：{e}")
        print("\n原因：tool 消息缺少 tool_call_id，API 不知道这个结果对应哪次工具调用。")
