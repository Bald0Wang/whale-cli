"""动手试 01：Write 和 Edit 各自适合什么场景。

先用 Write 创建一个新文件，再用 Edit 修改已有文件中的一行。
"""
import os, sys, tempfile, shutil
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

from tools import WriteFileTool, EditFileTool, ReadFileTool

write = WriteFileTool()
edit = EditFileTool()
read = ReadFileTool()

# 用临时目录，不污染 OpenClaw
tmpdir = tempfile.mkdtemp(prefix="whale-ch04-")
test_file = os.path.join(tmpdir, "hello.py")

print("=" * 50)
print("场景 1：用 Write 创建新文件")
print("=" * 50)
result = write(path=test_file, content='def greet(name):\n    return f"hello, {name}"\n')
print(f"  {result['stdout']}")

content = read(path=test_file)
print(f"  文件内容：")
for line in content["stdout"].splitlines()[:5]:
    print(f"    {line}")

print()
print("=" * 50)
print("场景 2：用 Edit 修改其中一行")
print("=" * 50)
result = edit(path=test_file, old_string="hello,", new_string="hi,")
print(f"  {result['stdout']}")

content = read(path=test_file)
print(f"  修改后：")
for line in content["stdout"].splitlines()[:5]:
    print(f"    {line}")

print()
print("=" * 50)
print("场景 3：如果用 Write 去改已有文件呢？")
print("=" * 50)
print("  模型得把整个文件重新输出一遍。")
print("  如果文件有 100 行，模型需要输出 100 行，只为了改 1 行。")
print("  而且可能漏掉某一行——Write 不知道'其余行必须保留'。")

shutil.rmtree(tmpdir)
print(f"\n临时文件已清理。")
