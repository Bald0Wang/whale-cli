"""动手试 03：路径未知时模型会怎样。

给一个模糊问题，不告诉路径，看模型能不能靠猜找到答案。
"""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

from main import run_agent

print("任务：这个项目怎么启动？（不给路径）")
print("观察模型会猜哪些文件名：")
print("=" * 60)
result = run_agent("这个项目怎么启动？")
print(result)
