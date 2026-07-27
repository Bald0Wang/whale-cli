"""动手试 02：改一句描述，模型就换了选择。

同一个 list_dir 工具，换三种 description 跑同一个任务。
"""
import os, json, copy
from openai import OpenAI

client = OpenAI(
    api_key=os.getenv("LLM_API_KEY"),
    base_url=os.getenv("LLM_BASE_URL", "https://api.deepseek.com/v1"),
)
model = os.getenv("LLM_MODEL", "deepseek-chat")

BASE_SCHEMA = {
    "type": "function",
    "function": {
        "name": "list_dir",
        "description": "",  # 每次替换
        "parameters": {
            "type": "object",
            "properties": {"path": {"type": "string"}},
        },
    },
}

READ_SCHEMA = {
    "type": "function",
    "function": {
        "name": "read_file",
        "description": "读取文本文件。",
        "parameters": {
            "type": "object",
            "properties": {"path": {"type": "string"}},
            "required": ["path"],
        },
    },
}

descriptions = [
    ("清晰", "列出指定目录下的文件和子目录。当不知道文件的准确路径时使用。"),
    ("含糊", "处理目录。"),
    ("误导", "删除目录中的所有文件。"),
]

messages = [{"role": "user", "content": "看看 src/tools 目录下有哪些文件"}]

for label, desc in descriptions:
    schema = copy.deepcopy(BASE_SCHEMA)
    schema["function"]["description"] = desc

    print(f"\n{'='*50}")
    print(f"描述：「{desc}」（{label}）")
    print('='*50)

    resp = client.chat.completions.create(
        model=model,
        messages=messages,
        tools=[READ_SCHEMA, schema],
    )
    msg = resp.choices[0].message

    if msg.tool_calls:
        for tc in msg.tool_calls:
            print(f"  模型选择了：{tc.function.name}({tc.function.arguments})")
    else:
        print(f"  模型没调工具：{msg.content[:100]}")
