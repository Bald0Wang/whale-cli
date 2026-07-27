"""动手试 2c：max_turns 设为 1，循环只跑一圈。

预期：模型读完第一个文件后想继续，但程序没有下一轮了。
"""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

from main import run_agent

print("max_turns=1，看看模型能不能完成任务：")
print("=" * 60)
result = run_agent(
    "这个项目怎么启动？",
    max_turns=1,
)
print(result)
print()
print("如果任务需要多轮工具调用，1 轮是不够的。")
