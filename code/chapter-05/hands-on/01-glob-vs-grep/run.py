"""动手试 01：Glob 和 Grep 各找什么。

Glob 按文件名找，Grep 按内容找。分别跑一次。
"""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

from tools import GlobTool, GrepTool

glob = GlobTool()
grep = GrepTool()

print("=" * 50)
print("Glob：按文件名找测试文件")
print("=" * 50)
result = glob(pattern="src/**/*.test.ts")
for line in result["stdout"].splitlines()[:10]:
    print(f"  {line}")

print()
print("=" * 50)
print("Grep：按内容找 formatToolExecutorRef")
print("=" * 50)
result = grep(pattern="formatToolExecutorRef", **{"glob": "**/*.ts"})
for line in result["stdout"].splitlines()[:10]:
    print(f"  {line}")

print()
print("Glob 返回的是路径列表，不打开文件。")
print("Grep 返回的是 文件:行号:匹配内容，可以直接给 Read 用。")
