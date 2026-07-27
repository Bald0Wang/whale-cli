"""动手试 01：写了 list_dir 函数但没注册到 Toolset。

模型不知道这个工具存在，会怎样？
"""
import os, sys, json
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

from llm_client import LLMClient
from tools import ReadFileTool, ListDirTool
from registry import Toolset

llm = LLMClient()

# ❌ 只注册 ReadFileTool，故意不注册 ListDirTool
toolset = Toolset()
toolset.register(ReadFileTool())
# toolset.register(ListDirTool())  ← 注释掉了

messages = [
    {"role": "system", "content": "你是一个代码助手。"},
    {"role": "user", "content": "看看 src/tools 目录下有哪些文件"},
]

print("只注册了 read_file，没注册 list_dir")
print("模型会怎样回应"看看目录下有哪些文件"？")
print("=" * 60)

response = llm.chat(messages, tools=toolset.all_schemas())
tool_calls = response.get("tool_calls")

if tool_calls:
    for tc in tool_calls:
        name = tc["function"]["name"]
        args = json.loads(tc["function"]["arguments"])
        print(f"模型请求：{name}({args})")
        tool = toolset.get(name)
        if tool is None:
            print(f"  → Toolset 找不到 '{name}'！")
        else:
            print(f"  → 执行成功")
else:
    print(f"模型回答：{response.get('content', '')[:200]}")
