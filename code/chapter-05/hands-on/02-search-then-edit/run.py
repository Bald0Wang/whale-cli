"""动手试 02：不给路径，让模型自己搜索再修改。

直接调用 ch05 的 main.py，不给文件路径，看完整的 Grep → Read → Edit 链路。
运行后记得 git checkout -- src/tools/execution.ts 恢复。
"""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

from main import run_agent

print("任务：不给路径，让模型自己找到函数再改")
print("=" * 60)
run_agent("在 TypeScript 文件中搜索 formatToolExecutorRef 函数的定义，然后把冒号分隔符改成斜杠")
print()
print("记得恢复：git checkout -- src/tools/execution.ts")
