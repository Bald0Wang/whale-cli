"""动手试 02：Edit 写错了 old_string 会怎样。

故意给一个和文件内容不完全一致的 old_string，看相似度提示。
"""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

from tools import EditFileTool

edit = EditFileTool()
target = "src/tools/execution.ts"

print("=" * 50)
print("故意写错 old_string，看 Edit 怎么报错")
print("=" * 50)

# 实际内容是 core:${ref.executorId}，故意写成 core.${ref.executorId}
print("\n--- 尝试 1：冒号写成了点号 ---")
result = edit(
    path=target,
    old_string='return `core.${ref.executorId}`;',
    new_string='return `core/${ref.executorId}`;',
)
if result["exit_code"] != 0:
    print(result["stderr"])
    print("\n工具拒绝了修改，并告诉我们文件里最接近的内容在哪。")
    print("模型看到这个提示后，通常能一次修正 old_string。")
else:
    print("居然成功了？文件内容可能已经被之前的实验改过。")
    print("运行 git checkout -- src/tools/execution.ts 恢复后再试。")

print()
print("--- 尝试 2：用正确的 old_string ---")
result2 = edit(
    path=target,
    old_string='return `core:${ref.executorId}`;',
    new_string='return `core/${ref.executorId}`;',
)
if result2["exit_code"] == 0:
    print(f"  {result2['stdout']}")
    print("\n记得恢复文件：git checkout -- src/tools/execution.ts")
else:
    print(f"  {result2['stderr']}")
