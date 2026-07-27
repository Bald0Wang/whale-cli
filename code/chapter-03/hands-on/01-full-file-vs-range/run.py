"""动手试 01：一次读完 vs 分段读。

对比整文件读取和分段读取的返回内容量。
"""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

from tools import ReadFileTool

read = ReadFileTool()
target = "src/system-agent/setup-inference.ts"

print("=" * 60)
print(f"目标文件：{target}")
print("=" * 60)

# 1. 整文件（模拟 ch01 的 read_text）
print("\n--- 整文件读取（不限行数）---")
result_full = read(path=target, start_line=1, end_line=99999)
stdout = result_full.get("stdout", "")
lines = stdout.splitlines()
print(f"返回 {len(lines)} 行，约 {len(stdout)} 字符")

# 2. 前 200 行
print("\n--- 分段读取：前 200 行 ---")
result_200 = read(path=target, start_line=1, end_line=200)
stdout_200 = result_200.get("stdout", "")
has_detect = "detectSetupInference" in stdout_200
print(f"返回 {len(stdout_200)} 字符")
print(f"包含 detectSetupInference？{'是' if has_detect else '否——目标在第 309 行，还没读到'}")

# 3. 201-400 行
print("\n--- 分段读取：201-400 行 ---")
result_300 = read(path=target, start_line=201, end_line=400)
stdout_300 = result_300.get("stdout", "")
has_detect_2 = "detectSetupInference" in stdout_300
print(f"返回 {len(stdout_300)} 字符")
print(f"包含 detectSetupInference？{'是——找到了！' if has_detect_2 else '否'}")

print(f"\n结论：整文件 {len(stdout)} 字符 vs 分段 {len(stdout_200)+len(stdout_300)} 字符（两次加起来），目标函数在第二段里。")
